"""Cataloghi e tabelle: lettura, colonne di posizione, ricerca, regole di disegno.

Specifica: ``mdfiles/13-core-cataloghi.md`` (stato ``approvato``).

Il modulo si scrive in 6 parti (decisione del proprietario del 2026-10-10):
P1 lettura da file locale, formati, colonne di posizione, limiti (questa);
P2 ASTRORES; P3 ``search`` e regole di disegno; P4 colonne calcolate e
strumenti di tabella; P5 epoca e moto proprio; P6 servizi e URL (dopo il 14).
"""

from __future__ import annotations

import dataclasses
import os
import re
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import astropy
import astropy.units as u
from astropy.io import ascii as astropy_ascii
from astropy.io import fits
from astropy.io.votable import parse as parse_votable
from astropy.table import Table

from astrotwo.core.coordinates_wcs import supported_frames

__all__ = [
    "CatalogTable",
    "CatalogsError",
    "PositionColumns",
    "PositionSuggestion",
    "TABLE_FORMATS",
    "TableInfo",
    "TableLimits",
    "confirm_position_columns",
    "detect_table_format",
    "list_tables",
    "read_table",
    "suggest_position_columns",
]


class CatalogsError(Exception):
    """Errore del modulo 13 con identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


# --------------------------------------------------------------------------
# P1 — Lettura da file locale, formati, colonne di posizione, limiti
# --------------------------------------------------------------------------

#: Formati riconosciuti (H22); ``format`` esplicito accetta solo i testi.
TABLE_FORMATS: tuple[str, ...] = ("votable", "fits", "csv", "tsv", "bsv", "ipac", "sextractor", "astrores")
_TEXT_FORMATS: tuple[str, ...] = ("csv", "tsv", "bsv", "ipac", "sextractor")
_ASCII_READERS = {"csv": dict(format="csv"), "tsv": dict(format="tab"), "bsv": dict(format="basic", delimiter=" "),
                  "ipac": dict(format="ipac"), "sextractor": dict(format="sextractor")}
_SNIFF_LINES = 20
_PROVENANCE = f"astropy {astropy.__version__} (astropy.io.votable, astropy.io.fits, astropy.io.ascii)"


@dataclass(frozen=True)
class TableLimits:
    """Tetto di righe (D13-4) e limite delle operazioni (4 GB, come D11-11); configurabili."""

    max_rows: int = 1_000_000
    operation_bytes: int = 4_000_000_000

    def __post_init__(self) -> None:
        if min(self.max_rows, self.operation_bytes) <= 0:
            raise ValueError("i limiti devono essere positivi")


@dataclass(frozen=True)
class TableInfo:
    """Tabella di un file (per la scelta dell'utente)."""

    index: int
    name: str
    rows: int
    columns: int


@dataclass(frozen=True)
class PositionColumns:
    """Colonne di posizione da UCD e metadati, o confermate dall'utente; mai dai nomi."""

    lon: str
    lat: str
    frame: str | None  # nome del frame di astropy (modulo 10) o None se non dichiarato
    equinox: str | None = None
    epoch: str | None = None  # epoca del COOSYS, se dichiarata (per P5)
    source: str = "ucd"  # "ucd" o "confirmed"
    system: str | None = None  # sistema come scritto nei metadati (es. "eq_FK5")


@dataclass(frozen=True)
class PositionSuggestion:
    """Coppia di colonne candidata dal nome: solo un suggerimento, da confermare."""

    lon: str
    lat: str
    frame_hint: str | None
    reason: str
    kind: str = "suggestion"


@dataclass(frozen=True, eq=False)
class CatalogTable:
    """Tabella con provenienza, colonne di posizione, corpo e avvisi."""

    table: Table
    source: str
    origin: str
    retrieved_at: datetime
    file_modified: datetime | None
    format: str
    table_index: int
    table_name: str
    positions: PositionColumns | None
    body: str | None
    limits: TableLimits
    warnings: tuple[tuple[str, str], ...] = ()
    history: tuple[str, ...] = ()
    provenance: str = field(default=_PROVENANCE)

    @property
    def rows(self) -> int:
        return len(self.table)

    @property
    def colnames(self) -> list[str]:
        return list(self.table.colnames)

    def describe_columns(self) -> list[dict[str, object]]:
        """Nome, tipo, unità (o stringa non riconosciuta), UCD e descrizione di ogni colonna."""
        out = []
        for name in self.table.colnames:
            col = self.table[name]
            out.append({
                "name": name,
                "dtype": str(col.dtype),
                "unit": col.unit.to_string() if col.unit is not None else None,
                "unit_unrecognized": col.meta.get("unit_unrecognized"),
                "ucd": col.meta.get("ucd"),
                "description": col.description,
            })
        return out


# --- riconoscimento del formato ---------------------------------------------


def _read_head(path: str, size: int = 65536) -> bytes:
    try:
        with open(path, "rb") as handle:
            return handle.read(size)
    except OSError as exc:
        raise CatalogsError("TABLE_UNREADABLE", f"file non leggibile: {path} ({exc})", path=path) from exc


def _sniff_lines(text: str) -> list[str]:
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    return lines[:_SNIFF_LINES]


def _delimited_format(lines: list[str]) -> str | None:
    """Regola di §3 per CSV, TSV e BSV; ``None`` se il testo è ambiguo."""
    if not lines:
        return None
    tabs = [("\t" in line) for line in lines]
    commas = [line.count(",") for line in lines]
    if all(tabs) and not any(commas):
        return "tsv"
    if not any(tabs) and commas[0] >= 1 and len(set(commas)) == 1:
        return "csv"
    if not any(tabs) and not any(commas):
        fields = {len(line.split()) for line in lines}
        if len(fields) == 1 and fields.pop() >= 2:
            return "bsv"
    return None


def detect_table_format(source) -> str:
    """Formato dal contenuto (H22): mai dall'estensione; testo ambiguo → ``FORMAT_AMBIGUOUS``."""
    path = os.fspath(source)
    head = _read_head(path)
    if head.startswith(b"SIMPLE  ="):
        return "fits"
    text = head.decode("latin-1")
    stripped = text.lstrip("﻿ \t\r\n")
    if stripped.startswith("<"):
        match = re.search(r"<(?![?!])([A-Za-z_][\w.:-]*)", stripped)
        root = match.group(1).split(":")[-1] if match else ""
        if root == "VOTABLE":
            return "votable"
        if root == "ASTRO":
            return "astrores"
        raise CatalogsError("FORMAT_UNSUPPORTED", f"{path}: XML con radice {root!r}; formati: {', '.join(TABLE_FORMATS)}")
    nonempty = [line for line in text.splitlines() if line.strip()]
    if nonempty and nonempty[0].lstrip()[:1] in ("\\", "|"):
        return "ipac"
    if nonempty and re.match(r"^#\s+\d+\s+\S+", nonempty[0]):
        return "sextractor"
    if b"\x00" in head:
        raise CatalogsError("FORMAT_UNSUPPORTED", f"{path}: file binario non riconosciuto; formati: {', '.join(TABLE_FORMATS)}")
    fmt = _delimited_format(_sniff_lines(text))
    if fmt is None:
        raise CatalogsError(
            "FORMAT_AMBIGUOUS",
            f"{path}: testo delimitato non classificabile (regola di §3): indicare format "
            f"({', '.join(_TEXT_FORMATS)})",
            path=path,
        )
    return fmt


# --- unità -------------------------------------------------------------------


def _unit_string(unit) -> str | None:
    if unit is None:
        return None
    if isinstance(unit, u.UnrecognizedUnit):
        return unit.name
    if isinstance(unit, str):
        return unit
    return unit.to_string()


def _standard_unit(text: str):
    """Unità se la stringa è valida nel formato FITS o VOUnit di astropy.units (come D18-2)."""
    for fmt in ("fits", "vounit"):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return u.Unit(text, format=fmt)
        except (ValueError, TypeError):
            continue
    return None


def _normalize_units(table: Table) -> list[tuple[str, str]]:
    """Unità standard alle colonne; stringhe non valide conservate con avviso, mai convertite."""
    notes = []
    for name in table.colnames:
        col = table[name]
        text = _unit_string(col.unit)
        if not text or not text.strip():
            col.unit = None
            continue
        unit = _standard_unit(text)
        if unit is None:
            col.unit = None
            col.meta["unit_unrecognized"] = text
            notes.append(("UNIT_UNRECOGNIZED", f"colonna {name!r}: unità {text!r} non valida in FITS né in VOUnit, non convertita"))
        else:
            col.unit = unit
    return notes


# --- colonne di posizione e corpo ----------------------------------------------

_UCD_PAIRS = (
    ("pos.eq.ra", "pos.eq.dec", None),
    ("pos.galactic.lon", "pos.galactic.lat", "galactic"),
    ("pos.ecliptic.lon", "pos.ecliptic.lat", None),
)
_PLANETARY_UCD = "pos.bodyrc"


def _ucd_words(ucd: str | None) -> list[str]:
    return [w.strip().lower() for w in (ucd or "").split(";") if w.strip()]


def _coosys_frame(coosys) -> tuple[str | None, str | None, str | None, str | None]:
    """(frame, equinox, epoca, sistema) dal COOSYS; frame None se la corrispondenza non è univoca."""
    if coosys is None:
        return None, None, None, None
    system = coosys.system
    equinox = str(coosys.equinox) if coosys.equinox else None
    epoch = str(coosys.epoch) if coosys.epoch else None
    frames = {"ICRS": "icrs", "eq_FK5": "fk5", "eq_FK4": "fk4", "galactic": "galactic", "supergalactic": "supergalactic"}
    frame = frames.get(system)
    if frame is not None and frame not in supported_frames():
        frame = None
    return frame, equinox, epoch, system


def _positions_from_ucd(table: Table, coosys_by_id: dict) -> tuple[PositionColumns | None, list[tuple[str, str]]]:
    notes: list[tuple[str, str]] = []
    for lon_ucd, lat_ucd, implied in _UCD_PAIRS:
        lons = [n for n in table.colnames if lon_ucd in _ucd_words(table[n].meta.get("ucd"))]
        lats = [n for n in table.colnames if lat_ucd in _ucd_words(table[n].meta.get("ucd"))]
        if not lons or not lats:
            continue
        if len(lons) > 1 or len(lats) > 1:
            lons = [n for n in lons if "meta.main" in _ucd_words(table[n].meta.get("ucd"))]
            lats = [n for n in lats if "meta.main" in _ucd_words(table[n].meta.get("ucd"))]
            if len(lons) != 1 or len(lats) != 1:
                notes.append(("NO_COORD_COLUMNS", f"più coppie {lon_ucd}/{lat_ucd} senza un'unica meta.main: nessuna scelta"))
                continue
        lon, lat = lons[0], lats[0]
        ref = table[lon].meta.get("ref") or table[lat].meta.get("ref")
        frame, equinox, epoch, system = _coosys_frame(coosys_by_id.get(ref))
        if frame is None and implied is not None:
            frame = implied
        if frame is None:
            notes.append(("FRAME_UNKNOWN", f"colonne {lon!r}/{lat!r}: sistema di riferimento non dichiarato"
                          + (f" o non univoco ({system})" if system else "")))
        return PositionColumns(lon=lon, lat=lat, frame=frame, equinox=equinox, epoch=epoch, source="ucd",
                               system=system), notes
    return None, notes


def _celestial_body(positions: PositionColumns | None, table: Table) -> str | None:
    if positions is None:
        return None
    words = _ucd_words(table[positions.lon].meta.get("ucd"))
    if any(w.startswith(_PLANETARY_UCD) for w in words):
        return None  # coordinate planetarie: corpo secondo il 19, mai assunto
    return "celestial"


_NAME_PAIRS = (
    ("ra", "dec", None), ("raj2000", "dej2000", None), ("_raj2000", "_dej2000", None), ("ra_icrs", "de_icrs", "icrs"),
    ("ra_icrs", "dec_icrs", "icrs"), ("radeg", "dedeg", None), ("ra_deg", "dec_deg", None), ("alpha", "delta", None),
    ("glon", "glat", "galactic"), ("gal_lon", "gal_lat", "galactic"), ("lii", "bii", "galactic"),
    ("elon", "elat", None), ("ecl_lon", "ecl_lat", None),
)


def suggest_position_columns(table: CatalogTable) -> tuple[PositionSuggestion, ...]:
    """Colonne candidate **dal nome**, marcate come suggerimento: l'utente deve confermare."""
    lower = {name.lower(): name for name in table.colnames}
    out = []
    for lon, lat, hint in _NAME_PAIRS:
        if lon in lower and lat in lower:
            out.append(PositionSuggestion(
                lon=lower[lon], lat=lower[lat], frame_hint=hint,
                reason=f"nomi {lower[lon]!r}/{lower[lat]!r}: ipotesi dal nome, da confermare con il sistema",
            ))
    return tuple(out)


def confirm_position_columns(table: CatalogTable, lon: str, lat: str, frame: str, equinox=None, unit=None) -> CatalogTable:
    """Nuova tabella con le colonne di posizione confermate dall'utente (scritto nella provenienza).

    ``unit`` (angolare) serve solo se le colonne non hanno un'unità: non si assume mai.
    """
    for name in (lon, lat):
        if name not in table.table.colnames:
            raise CatalogsError("NO_COORD_COLUMNS", f"colonna {name!r} inesistente")
        col = table.table[name]
        if col.dtype.kind not in "iuf":
            raise CatalogsError("COLUMN_TYPE_UNSUPPORTED", f"colonna {name!r} di tipo {col.dtype}: servono valori numerici")
        if col.unit is None and unit is None:
            raise CatalogsError("COORD_UNIT_MISSING", f"colonna {name!r} senza unità: indicare unit (angolare)")
        used = col.unit if col.unit is not None else u.Unit(unit)
        if not used.is_equivalent(u.deg):
            raise CatalogsError("COORD_UNIT_MISSING", f"colonna {name!r} in unità {used}, non angolare")
    if frame not in supported_frames():
        raise CatalogsError("FRAME_UNKNOWN", f"frame {frame!r} non supportato; frame: {', '.join(supported_frames())}")
    new = table.table.copy()
    notes = []
    for name in (lon, lat):
        if new[name].unit is None:
            new[name].unit = u.Unit(unit)
            notes.append(("UNIT_DECLARED", f"colonna {name!r}: unità {u.Unit(unit)} dichiarata dall'utente"))
    positions = PositionColumns(lon=lon, lat=lat, frame=frame, equinox=None if equinox is None else str(equinox),
                                source="confirmed", system=frame)
    kept = tuple(w for w in table.warnings if w[0] not in ("NO_COORD_COLUMNS", "BODY_UNKNOWN", "FRAME_UNKNOWN"))
    return dataclasses.replace(
        table, table=new, positions=positions, body="celestial",
        warnings=kept + tuple(notes),
        history=table.history + (f"colonne di posizione confermate dall'utente: {lon}/{lat}, frame {frame}"
                                 + (f", equinozio {equinox}" if equinox is not None else ""),),
    )


# --- limiti --------------------------------------------------------------------


def _check_rows(rows: int, limits: TableLimits, path: str) -> None:
    if rows > limits.max_rows:
        raise CatalogsError("TABLE_TOO_LARGE", f"{path}: {rows} righe, oltre il tetto di {limits.max_rows}",
                            rows=rows, max_rows=limits.max_rows)


def _check_memory(what: str, needed: int, limits: TableLimits) -> None:
    if needed > limits.operation_bytes:
        raise CatalogsError(
            "MEMORY_LIMIT_EXCEEDED",
            f"{what}: servono circa {needed} byte, oltre il limite delle operazioni di {limits.operation_bytes} byte",
            needed_bytes=needed, limit_bytes=limits.operation_bytes,
        )


def _table_bytes(table: Table) -> int:
    return int(sum(table[name].nbytes for name in table.colnames))


def _count_text_rows(path: str, fmt: str) -> tuple[int, int]:
    """(righe di dati, colonne) di un testo, con una lettura in sequenza che non conserva nulla."""
    rows, columns, header_seen = 0, 0, False
    with open(path, encoding="latin-1") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if fmt == "ipac" and stripped[:1] in ("\\", "|"):
                if stripped.startswith("|") and not columns:
                    columns = stripped.strip("|").count("|") + 1
                continue
            if fmt == "sextractor" and stripped.startswith("#"):
                columns += 1
                continue
            if stripped.startswith("#"):
                continue
            if fmt in ("csv", "tsv", "bsv") and not header_seen:
                header_seen = True
                sep = {"csv": ",", "tsv": "\t", "bsv": None}[fmt]
                columns = len(stripped.split(sep))
                continue
            rows += 1
    return rows, columns


# --- lettura -------------------------------------------------------------------


def _fits_tables(hdul) -> list[int]:
    return [k for k, hdu in enumerate(hdul) if isinstance(hdu, (fits.BinTableHDU, fits.TableHDU))]


def _choose(available: list[TableInfo], table, path: str) -> TableInfo:
    listing = "; ".join(f"{t.index}: {t.name or '(senza nome)'} {t.rows}×{t.columns}" for t in available)
    if not available:
        raise CatalogsError("FORMAT_UNSUPPORTED", f"{path}: nessuna tabella nel file")
    if table is None:
        if len(available) == 1:
            return available[0]
        raise CatalogsError("TABLE_CHOICE_REQUIRED", f"{path}: più tabelle, indicare table ({listing})",
                            tables=tuple(available))
    for info in available:
        if info.index == table:
            return info
    raise CatalogsError("TABLE_CHOICE_REQUIRED", f"{path}: tabella {table!r} inesistente ({listing})",
                        tables=tuple(available))


def _votable_infos(vot) -> list[TableInfo]:
    return [TableInfo(index=k, name=t.name or t.ID or "", rows=t.nrows, columns=len(t.fields))
            for k, t in enumerate(vot.iter_tables())]


def _parse_votable(path: str):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return parse_votable(path, verify="ignore")
    except Exception as exc:
        raise CatalogsError("TABLE_UNREADABLE", f"{path}: VOTable non leggibile ({exc})", path=path) from exc


def list_tables(source) -> tuple[TableInfo, ...]:
    """Tabelle del file (indice, nome, righe, colonne), per la scelta dell'utente."""
    path = str(Path(os.fspath(source)).expanduser().resolve())
    fmt = detect_table_format(path)
    if fmt == "votable":
        return tuple(_votable_infos(_parse_votable(path)))
    if fmt == "fits":
        with fits.open(path) as hdul:
            return tuple(TableInfo(index=k, name=hdul[k].name, rows=int(hdul[k].header.get("NAXIS2", 0)),
                                   columns=int(hdul[k].header.get("TFIELDS", 0))) for k in _fits_tables(hdul))
    if fmt == "astrores":
        raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: lettore ASTRORES non ancora disponibile (P2)")
    rows, columns = _count_text_rows(path, fmt)
    return (TableInfo(index=0, name="", rows=rows, columns=columns),)


def _read_votable(path: str, table, limits: TableLimits):
    _check_memory(f"lettura di {path}", os.path.getsize(path), limits)  # stima prima della lettura (XML)
    vot = _parse_votable(path)
    info = _choose(_votable_infos(vot), table, path)
    _check_rows(info.rows, limits, path)
    vtable = list(vot.iter_tables())[info.index]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = vtable.to_table(use_names_over_ids=True)
    for f in vtable.fields:
        name = f.name if f.name in result.colnames else f.ID
        if name in result.colnames:
            if f.ref:
                result[name].meta["ref"] = f.ref
            if f.ucd:
                result[name].meta["ucd"] = f.ucd
    coosys = {c.ID: c for c in vot.iter_coosys() if c.ID}
    return result, info, coosys


def _read_fits(path: str, table, limits: TableLimits):
    with fits.open(path) as hdul:
        infos = [TableInfo(index=k, name=hdul[k].name, rows=int(hdul[k].header.get("NAXIS2", 0)),
                           columns=int(hdul[k].header.get("TFIELDS", 0))) for k in _fits_tables(hdul)]
        info = _choose(infos, table, path)
        header = hdul[info.index].header
        _check_rows(info.rows, limits, path)
        _check_memory(f"lettura di {path}", int(header.get("NAXIS1", 0)) * info.rows, limits)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = Table.read(hdul[info.index])
    return result, info, {}


def _read_text(path: str, fmt: str, table, limits: TableLimits):
    rows, columns = _count_text_rows(path, fmt)
    info = _choose([TableInfo(index=0, name="", rows=rows, columns=columns)], table, path)
    _check_rows(rows, limits, path)
    # Prima della lettura: numeri in float64 più il testo del file (§3).
    _check_memory(f"lettura di {path}", rows * columns * 8 + os.path.getsize(path), limits)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = astropy_ascii.read(path, guess=False, **_ASCII_READERS[fmt])
    except Exception as exc:
        raise CatalogsError("TABLE_UNREADABLE", f"{path}: tabella {fmt} non leggibile ({exc})", path=path) from exc
    return result, info, {}


def read_table(source, *, table=None, format=None, limits: TableLimits | None = None) -> CatalogTable:
    """Legge una tabella da file locale (H22, P1) con formato, limiti, unità, posizioni e corpo."""
    limits = TableLimits() if limits is None else limits
    text = os.fspath(source)
    if text.startswith(("http://", "https://")):
        raise CatalogsError("FORMAT_UNSUPPORTED", "le tabelle da URL passano dal modulo 14 (P6)")
    path = str(Path(text).expanduser().resolve())
    retrieved_at = datetime.now(UTC)
    if format is not None:
        if format not in _TEXT_FORMATS:
            raise CatalogsError("FORMAT_UNSUPPORTED", f"format {format!r}: ammessi {', '.join(_TEXT_FORMATS)}")
        _read_head(path, 1)  # file assente → TABLE_UNREADABLE
        fmt = format
    else:
        fmt = detect_table_format(path)
    if fmt == "votable":
        result, info, coosys = _read_votable(path, table, limits)
    elif fmt == "fits":
        result, info, coosys = _read_fits(path, table, limits)
    elif fmt == "astrores":
        raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: lettore ASTRORES non ancora disponibile (P2)")
    else:
        result, info, coosys = _read_text(path, fmt, table, limits)
    # Dopo la lettura: righe e memoria esatte (per l'XML è il primo controllo esatto).
    _check_rows(len(result), limits, path)
    _check_memory(f"tabella {path}", _table_bytes(result), limits)
    notes: list[tuple[str, str]] = []
    if format is not None:
        notes.append(("FORMAT_DECLARED", f"formato {format} indicato dall'utente, nessun riconoscimento"))
    notes.extend(_normalize_units(result))
    positions, position_notes = _positions_from_ucd(result, coosys)
    notes.extend(position_notes)
    body = _celestial_body(positions, result)
    if positions is None:
        notes.append(("NO_COORD_COLUMNS", "nessuna colonna di posizione da UCD o metadati: confermare con "
                      "confirm_position_columns (suggerimenti da suggest_position_columns)"))
    if body is None:
        notes.append(("BODY_UNKNOWN", "corpo non ricavabile: il dato non si sovrappone né si combina con altri"))
    return CatalogTable(
        table=result,
        source=text,
        origin=path,
        retrieved_at=retrieved_at,
        file_modified=datetime.fromtimestamp(os.path.getmtime(path), tz=UTC),
        format=fmt,
        table_index=info.index,
        table_name=info.name,
        positions=positions,
        body=body,
        limits=limits,
        warnings=tuple(notes),
    )

