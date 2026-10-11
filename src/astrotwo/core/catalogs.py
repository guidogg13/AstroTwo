"""Cataloghi e tabelle: lettura, colonne di posizione, ricerca, regole di disegno.

Specifica: ``mdfiles/13-core-cataloghi.md`` (stato ``approvato``).

Il modulo si scrive in 6 parti (decisione del proprietario del 2026-10-10):
P1 lettura da file locale, formati, colonne di posizione, limiti (questa);
P2 ASTRORES; P3 ``search`` e regole di disegno; P4 colonne calcolate e
strumenti di tabella; P5 epoca e moto proprio; P6 servizi e URL (dopo il 14).
"""

from __future__ import annotations

import ast
import dataclasses
import functools
import math
import os
import re
import tempfile
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import astropy
import astropy.units as u
import numpy as np
from astropy.io import ascii as astropy_ascii
from astropy.io import fits
from astropy.coordinates import angular_separation
from astropy.io.votable import from_table as votable_from_table
from astropy.io.votable import parse as parse_votable
from astropy.io.votable.tree import CooSys, Info
from astropy.table import MaskedColumn, Table
from astropy.time import Time
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import parse as safe_parse_xml

from astrotwo.core.coordinates_wcs import (
    CoordinatesWcsError,
    SkyFrame,
    parse_sexagesimal,
    propagate_position,
    supported_frames,
)

__all__ = [
    "CONSTANTS",
    "DataLinkColumn",
    "ALPHABETICAL_NOTE",
    "ASTRORES_LINK_TYPES",
    "CollectionNode",
    "CollectionTree",
    "FIXED_COLLECTIONS",
    "FixedCollection",
    "POPULARITY_NOTE",
    "collection_tree",
    "datalink_column",
    "load_catalog",
    "load_table",
    "CatalogTable",
    "CatalogsError",
    "ColumnStatistics",
    "FUNCTIONS",
    "Histogram",
    "XYData",
    "PLOT_SHAPES",
    "PlotRule",
    "PlotStyle",
    "SizeScale",
    "TimeSelection",
    "UCD1_TRANSLATIONS",
    "PositionColumns",
    "Propagation",
    "ProperMotionArrows",
    "PositionSuggestion",
    "TABLE_FORMATS",
    "TableInfo",
    "TableLimits",
    "confirm_position_columns",
    "detect_table_format",
    "list_tables",
    "propagate",
    "proper_motion_arrows",
    "calculated_column",
    "column_statistics",
    "histogram",
    "read_table",
    "record_view",
    "save_subset",
    "skydist",
    "subset",
    "xy_plot",
    "search",
    "set_plot_rules",
    "suggest_position_columns",
    "time_filter",
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
TABLE_FORMATS: tuple[str, ...] = ("votable", "fits", "csv", "tsv", "bsv", "ipac", "sextractor", "ecsv", "astrores")
_TEXT_FORMATS: tuple[str, ...] = ("csv", "tsv", "bsv", "ipac", "sextractor", "ecsv")
# Le righe che iniziano con "#" sono commenti nei testi delimitati (§3), anche per astropy.
_ASCII_READERS = {"csv": dict(format="csv", comment="#"), "tsv": dict(format="tab", comment="#"),
                  "bsv": dict(format="basic", delimiter=" ", comment="#"),
                  "ipac": dict(format="ipac"), "sextractor": dict(format="sextractor"),
                  "ecsv": dict(format="ecsv")}  # ECSV di astropy (D14-10): unità e UCD nell'intestazione
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
    request: object | None = None  # RequestRecord del modulo 14 per i dati da rete (P6), altrimenti None
    descriptors: tuple = ()  # descrittori di servizio del VOTable (ServiceDescriptor del 14, P6)

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
    if nonempty and nonempty[0].startswith("# %ECSV"):  # prima riga dichiarata dallo standard ECSV
        return "ecsv"
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
            if fmt in ("csv", "tsv", "bsv", "ecsv") and not header_seen:
                header_seen = True
                sep = {"csv": ",", "tsv": "\t", "bsv": None}.get(fmt, "," if "," in stripped else None)
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
    # ``nrows`` è un attributo facoltativo del VOTable (assente → None): si contano le righe lette.
    return [TableInfo(index=k, name=t.name or t.ID or "", rows=t.nrows if t.nrows is not None else len(t.array),
                      columns=len(t.fields))
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
        return tuple(_astrores_infos(_parse_astrores(path)))
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
            if f.utype:
                result[name].meta["utype"] = f.utype
    coosys = {c.ID: c for c in vot.iter_coosys() if c.ID}
    timesys = {t.ID: t for t in vot.iter_timesys() if t.ID}
    for name in result.colnames:
        ref = result[name].meta.get("ref")
        if ref in timesys:
            ts = timesys[ref]
            result[name].meta["timesys"] = {"timeorigin": None if ts.timeorigin is None else str(ts.timeorigin),
                                            "timescale": ts.timescale, "refposition": ts.refposition}
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
        # UCD e utype delle colonne (parole chiave TUCDn e TUTYPn, convenzione diffusa nei FITS del VO).
        for k, name in enumerate(result.colnames, start=1):
            for keyword, meta in (("TUCD", "ucd"), ("TUTYP", "utype")):
                value = header.get(f"{keyword}{k}")
                if isinstance(value, str) and value.strip():
                    result[name].meta[meta] = value.strip()
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
    """Legge una tabella da file locale (H22, P1) con formato, limiti, unità, posizioni e corpo.

    Senza rete: un ASTRORES con i dati in un ``LINK`` esterno si legge con ``load_table`` (D13-17)."""
    return _read_table(source, table=table, format=format, limits=limits)


def _read_table(source, *, table=None, format=None, limits: TableLimits | None = None, fetch_link=None,
                base: str | None = None) -> CatalogTable:
    """``read_table`` con, per i ``LINK`` ASTRORES (D13-17), la funzione di rete del 14 e l'URL di base."""
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
        result, info, coosys, astrores_notes = _read_astrores(path, table, limits, fetch_link, base)
    else:
        result, info, coosys = _read_text(path, fmt, table, limits)
    # Dopo la lettura: righe e memoria esatte (per l'XML è il primo controllo esatto).
    _check_rows(len(result), limits, path)
    _check_memory(f"tabella {path}", _table_bytes(result), limits)
    notes: list[tuple[str, str]] = list(astrores_notes) if fmt == "astrores" else []
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



# --------------------------------------------------------------------------
# P2 — ASTRORES (DTD pubblica del CDS v0.9; D13-7, D13-14)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _CooSys:
    """COOSYS di ASTRORES con gli stessi attributi di quello di astropy.io.votable."""

    ID: str
    system: str | None
    equinox: str | None
    epoch: str | None


_ASTRORES_FLOAT = ("F", "D", "E")
#: UCD1 tradotti (D13-14b): solo le parole scritte nella raccomandazione IVOA sugli UCD (REC 2005-08-12, §3.1:
#: POS_EQ_RA_MAIN, POS_EQ_RA, POS_EQ_DEC_MAIN, POS_EQ_DEC, scomposte in POS_EQ_RA, POS_EQ_DEC e MAIN;
#: appendice A: POS_EQ_DEC_MAIN = pos.eq.dec;meta.main).
UCD1_TRANSLATIONS: dict[str, str] = {
    "POS_EQ_RA_MAIN": "pos.eq.ra;meta.main",
    "POS_EQ_RA": "pos.eq.ra",
    "POS_EQ_DEC_MAIN": "pos.eq.dec;meta.main",
    "POS_EQ_DEC": "pos.eq.dec",
}
_REF_FORM = re.compile(r"^#id\(\$?([^)]*)\)$")


def _astrores_year(value: str | None, system: str | None) -> str | None:
    """Equinozio o epoca scritti come numero (es. ``2000.``): giuliani per FK5 e ICRS, besseliani per FK4."""
    if value is None or not value.strip():
        return None
    text = value.strip()
    if text[:1] in ("J", "B"):
        return text
    try:
        year = float(text)
    except ValueError:
        return text
    return f"{'B' if system == 'eq_FK4' else 'J'}{year:g}"


def _astrores_text(element, tag: str) -> str | None:
    child = element.find(tag)
    return None if child is None or child.text is None else child.text.strip()


def _parse_astrores(path: str):
    try:
        tree = safe_parse_xml(path)
    except DefusedXmlException as exc:
        raise CatalogsError("XML_UNSAFE", f"{path}: costrutto XML pericoloso ({type(exc).__name__}), nulla caricato",
                            path=path) from exc
    except Exception as exc:
        raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: XML non leggibile ({exc})", path=path) from exc
    root = tree.getroot()
    if root.tag != "ASTRO":
        raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: radice {root.tag!r}, attesa ASTRO")
    return root


def _astrores_rows(table_el, n_fields: int, path: str) -> list[list[str | None]]:
    data = table_el.find("DATA")
    if data is None:
        return []
    csv = data.find("CSV")
    if csv is not None:
        colsep = csv.get("colsep") or "\t"
        recsep = csv.get("recsep") or "\n"
        headlines = int(csv.get("headlines") or 0)
        records = [r for r in (csv.text or "").split(recsep) if r.strip()][headlines:]
        rows = [[cell.strip() for cell in record.split(colsep)] for record in records]
    else:
        tabledata = data.find("TABLEDATA")
        if tabledata is None:
            raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: DATA senza CSV, TABLEDATA o LINK")
        headlines = int(tabledata.get("headlines") or 0)
        rows = [[(c.text or "").strip() for c in row.findall("CELL")] for row in tabledata.findall("ROW")][headlines:]
    for k, row in enumerate(rows):
        if len(row) != n_fields:
            raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: riga {k} con {len(row)} valori per {n_fields} campi")
    return [[cell if cell != "" else None for cell in row] for row in rows]


def _astrores_column(name: str, values: list[str | None], field_el, notes: list[tuple[str, str]], table: Table,
                     ucd: str | None):
    datatype = (field_el.get("datatype") or "A").upper()
    unit = field_el.get("unit")
    missing = [v is None for v in values]
    present = [v for v in values if v is not None]

    def put(data, dtype=None):
        column = MaskedColumn(data, mask=missing, dtype=dtype, name=name)
        table[name] = column

    if datatype in _ASTRORES_FLOAT or datatype == "I":
        cast = float if datatype in _ASTRORES_FLOAT else int
        try:
            parsed = [cast(v) for v in present]
            filled = iter(parsed)
            put([next(filled) if not m else 0 for m in missing], np.float64 if cast is float else np.int64)
        except ValueError:
            words = _ucd_words(ucd)
            hours = "pos.eq.ra" in words
            degrees = "pos.eq.dec" in words
            angular = unit is not None and _standard_unit(unit) is not None and _standard_unit(unit).is_equivalent(u.deg)
            converted = None
            if angular and (hours or degrees):
                try:
                    converted = parse_sexagesimal(present, hours=hours).to_value(_standard_unit(unit))
                except CoordinatesWcsError:
                    converted = None
            put([v if v is not None else "" for v in values], str)
            table[name + "_text"] = table[name]
            if converted is not None:
                filled = iter(converted)
                put([next(filled) if not m else 0.0 for m in missing], np.float64)
                notes.append(("ASTRORES_TYPE_MISMATCH", f"campo {name!r}: dichiarato {datatype} ma i dati sono "
                              f"sessagesimali; convertiti in gradi ({'ore' if hours else 'gradi'}) con il modulo 10, "
                              f"testo originale in {name + '_text'!r}"))
            else:
                del table[name + "_text"]
                notes.append(("ASTRORES_TYPE_MISMATCH", f"campo {name!r}: dichiarato {datatype} ma i dati non sono "
                              "numerici; letto come testo"))
    elif datatype == "L":
        mapping = {"t": True, "true": True, "1": True, "f": False, "false": False, "0": False}
        if all(v.lower() in mapping for v in present):
            filled = iter([mapping[v.lower()] for v in present])
            put([next(filled) if not m else False for m in missing], bool)
        else:
            put([v if v is not None else "" for v in values], str)
            notes.append(("ASTRORES_TYPE_MISMATCH", f"campo {name!r}: dichiarato L ma i dati non sono booleani; testo"))
    else:
        put([v if v is not None else "" for v in values], str)
    column = table[name]
    if unit:
        column.unit = u.Unit(unit, parse_strict="silent")  # validata poi come le altre (FITS o VOUnit)
    if ucd:
        column.meta["ucd"] = ucd
    description = _astrores_text(field_el, "DESCRIPTION")
    if description:
        column.description = " ".join(description.split())


def _astrores_infos(root) -> list[TableInfo]:
    out = []
    for k, table_el in enumerate(root.iter("TABLE")):
        data = table_el.find("DATA")
        rows = 0
        if data is not None and data.find("TABLEDATA") is not None:
            tabledata = data.find("TABLEDATA")
            rows = max(0, len(tabledata.findall("ROW")) - int(tabledata.get("headlines") or 0))
        elif data is not None and data.find("CSV") is not None:
            csv = data.find("CSV")
            rows = max(0, len([r for r in (csv.text or "").split(csv.get("recsep") or "\n") if r.strip()])
                       - int(csv.get("headlines") or 0))
        name = _astrores_text(table_el, "NAME") or table_el.get("ID") or ""
        out.append(TableInfo(index=k, name=name, rows=rows, columns=len(table_el.findall("FIELD"))))
    return out


#: Content-type dei dati in un LINK ASTRORES e lettore del modulo che li legge (D13-17): nessun altro.
ASTRORES_LINK_TYPES = {"text/csv": "csv", "text/tab-separated-values": "tsv",
                       "application/x-votable+xml": "votable", "application/fits": "fits"}


def _link_format(link, path: str) -> str:
    declared = link.get("content-type")
    if not declared or not declared.strip():
        raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: LINK senza content-type: il formato dei dati "
                            "collegati non si indovina (D13-17)")
    media, *params = [part.strip().lower() for part in declared.split(";")]
    fmt = ASTRORES_LINK_TYPES.get(media)
    if fmt is None:
        raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: LINK con content-type {declared!r} non letto; "
                            f"ammessi: {', '.join(ASTRORES_LINK_TYPES)} (D13-17)")
    if fmt == "csv" and "header=absent" in [p.replace(" ", "") for p in params]:
        raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: LINK {declared!r}: il lettore CSV del modulo vuole "
                            "la riga dei nomi delle colonne (header=absent, RFC 4180)")
    return fmt


def _link_url(link, path: str, base: str | None) -> str:
    from urllib.parse import urljoin

    if link.get("href") is None:
        kind = "gref (sistema GLU)" if link.get("gref") is not None else (
            "action" if link.get("action") is not None else "nessun indirizzo")
        raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: LINK con {kind}: si leggono solo i LINK con href "
                            "(D13-17)")
    href = link.get("href").strip()
    url = urljoin(base, href) if base and base.startswith(("http://", "https://")) else href
    if not url.startswith(("http://", "https://")):
        raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: LINK href {href!r}: serve un URL http(s) "
                            "(relativo solo in un documento scaricato da URL)")
    return url


def _link_conflicts(fields, names: list[str], linked: Table, ucds: list[str | None]) -> list[str]:
    """Differenze tra le definizioni FIELD dell'ASTRORES e la tabella collegata (nessuna scelta tra le due)."""
    if linked.colnames != names:
        return [f"colonne {linked.colnames} invece dei FIELD {names}"]
    problems = []
    for field_el, name, ucd in zip(fields, names, ucds):
        col = linked[name]
        text = field_el.get("unit")
        mine = _standard_unit(text) if text else None
        theirs = _unit_string(col.unit)
        if text and theirs:
            other = _standard_unit(theirs)
            if mine is None or other is None or mine != other:
                problems.append(f"{name}: unità {text!r} nel FIELD e {theirs!r} nei dati collegati")
        if ucd and col.meta.get("ucd") and col.meta["ucd"].strip().lower() != ucd.strip().lower():
            problems.append(f"{name}: UCD {ucd!r} nel FIELD e {col.meta['ucd']!r} nei dati collegati")
        datatype = (field_el.get("datatype") or "A").upper()
        if datatype in _ASTRORES_FLOAT + ("I",) and col.dtype.kind not in "iuf":
            problems.append(f"{name}: FIELD numerico ({datatype}) ma dati collegati di tipo {col.dtype}")
        if datatype == "L" and col.dtype.kind != "b":
            problems.append(f"{name}: FIELD booleano ma dati collegati di tipo {col.dtype}")
    return problems


def _read_link(table_el, fields, names: list[str], ucds: list[str | None], path: str, limits: TableLimits,
               fetch_link, base: str | None):
    """Dati in un LINK esterno (D13-17): solo href, formato dal content-type dichiarato, lettori del modulo."""
    link = table_el.find("DATA").find("LINK")
    fmt = _link_format(link, path)
    url = _link_url(link, path, base)
    if fetch_link is None:
        raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: dati in un LINK esterno ({url}): servono la rete e "
                            "la cache del modulo 14, usare load_table (D13-17)")
    payload, note = fetch_link(url)
    _check_memory(f"dati collegati {url}", len(payload), limits)
    fd, tmp = tempfile.mkstemp(prefix="astrotwo-link-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        try:
            readers = {"votable": _read_votable, "fits": _read_fits}
            if fmt in readers:
                linked, _, linked_coosys = readers[fmt](tmp, None, limits)
            else:
                linked, _, linked_coosys = _read_text(tmp, fmt, None, limits)
        except CatalogsError as exc:
            if exc.code in ("TABLE_TOO_LARGE", "MEMORY_LIMIT_EXCEEDED"):
                raise
            raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: dati collegati {url} non leggibili come {fmt} "
                                f"(content-type dichiarato): {exc.message}") from exc
        except (OSError, ValueError) as exc:  # es. dati che non sono del formato dichiarato
            raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: dati collegati {url} non leggibili come {fmt} "
                                f"(content-type dichiarato): {exc}") from exc
    finally:
        os.unlink(tmp)
    problems = _link_conflicts(fields, names, linked, ucds)
    if problems:
        raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: FIELD e dati collegati {url} non coincidono: "
                            + "; ".join(problems), conflicts=tuple(problems))
    return linked, linked_coosys, [note, ("ASTRORES_LINK", f"dati letti dal LINK {url} come {fmt} "
                                          f"(content-type dichiarato {link.get('content-type')!r})")]


def _read_astrores(path: str, table, limits: TableLimits, fetch_link=None, base: str | None = None):
    _check_memory(f"lettura di {path}", os.path.getsize(path), limits)  # stima prima della lettura (XML)
    root = _parse_astrores(path)
    info = _choose(_astrores_infos(root), table, path)
    _check_rows(info.rows, limits, path)
    table_el = list(root.iter("TABLE"))[info.index]
    fields = table_el.findall("FIELD")
    if not fields:
        raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: tabella {info.index} senza FIELD")
    notes: list[tuple[str, str]] = []
    names, ucds = [], []
    for k, field_el in enumerate(fields):
        name = _astrores_text(field_el, "NAME") or field_el.get("name") or field_el.get("ID") or f"col{k}"
        if name in names:
            raise CatalogsError("ASTRORES_UNREADABLE", f"{path}: due campi con lo stesso nome {name!r}")
        original_ucd = field_el.get("ucd")
        ucd = UCD1_TRANSLATIONS.get((original_ucd or "").strip().upper(), original_ucd)
        if ucd != original_ucd:
            notes.append(("UCD1_TRANSLATED", f"campo {name!r}: UCD1 {original_ucd!r} tradotto in {ucd!r} "
                          "(raccomandazione IVOA sugli UCD, §3.1 e appendice A)"))
        names.append(name)
        ucds.append(ucd)
    data_el = table_el.find("DATA")
    linked_coosys: dict = {}
    if data_el is not None and data_el.find("LINK") is not None:
        result, linked_coosys, link_notes = _read_link(table_el, fields, names, ucds, path, limits, fetch_link, base)
        notes.extend(link_notes)
        for field_el, name, ucd in zip(fields, names, ucds):
            column = result[name]
            if field_el.get("unit") and column.unit is None:
                column.unit = u.Unit(field_el.get("unit"), parse_strict="silent")
            if ucd:
                column.meta["ucd"] = ucd
            description = _astrores_text(field_el, "DESCRIPTION")
            if description and not column.description:
                column.description = " ".join(description.split())
    else:
        rows = _astrores_rows(table_el, len(fields), path)
        result = Table()
        for k, (field_el, name, ucd) in enumerate(zip(fields, names, ucds)):
            _astrores_column(name, [row[k] for row in rows], field_el, notes, result, ucd)
    for field_el, name, ucd in zip(fields, names, ucds):
        original_ucd = field_el.get("ucd")
        if ucd != original_ucd:
            result[name].meta["ucd_original"] = original_ucd
        ref = field_el.get("ref")
        if ref:
            match = _REF_FORM.match(ref)
            if match:
                notes.append(("ASTRORES_NONCONFORMING_REF", f"campo {name!r}: ref {ref!r} non è un IDREF (DTD): "
                              f"accettato come {match.group(1)!r}"))
                ref = match.group(1)
            result[name].meta["ref"] = ref
    coosys = dict(linked_coosys)
    for el in root.iter("COOSYS"):
        if el.get("ID"):
            system = el.get("system") or "eq_FK5"  # default della DTD
            coosys[el.get("ID")] = _CooSys(el.get("ID"), system, _astrores_year(el.get("equinox"), system),
                                           _astrores_year(el.get("epoch"), system))
    untranslated = [n for n in result.colnames if (result[n].meta.get("ucd") or "") and "." not in result[n].meta["ucd"]]
    if untranslated:
        notes.append(("UCD1_NOT_TRANSLATED", f"UCD1 fuori dalla raccomandazione IVOA, non tradotti (D13-14b) nei "
                      f"campi {untranslated}: colonne di posizione da confermare con confirm_position_columns"))
    return result, info, coosys, notes


# --------------------------------------------------------------------------
# P3 — search (grammatica di §3, D13-1) e regole di disegno (D4)
# --------------------------------------------------------------------------

_OPERATORS = ("!=", "<=", ">=", "=", "<", ">")
_WORD_STOP = set(" \t\r\n()|&=!<>\"'")
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_COMPARE = {"=": np.equal, "!=": np.not_equal, "<": np.less, ">": np.greater, "<=": np.less_equal,
            ">=": np.greater_equal}


@dataclass(frozen=True)
class _Token:
    kind: str  # COL, WORD, STRING, OP, AND, OR, ABS, LPAREN, RPAREN, END
    text: str
    pos: int


def _invalid(message: str, pos: int, expression: str) -> CatalogsError:
    return CatalogsError("EXPRESSION_INVALID", f"{message} (carattere {pos}): {expression!r}", position=pos)


def _tokenize(text: str, offset: int, expression: str) -> list[_Token]:
    tokens: list[_Token] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        pos = offset + i
        if c in " \t\r\n":
            i += 1
        elif text.startswith("${", i):
            end = text.find("}", i + 2)
            if end < 0:
                raise _invalid("nome di colonna ${...} senza '}'", pos, expression)
            tokens.append(_Token("COL", text[i + 2:end], pos))
            i = end + 1
        elif text.startswith("&&", i):
            tokens.append(_Token("AND", "&&", pos))
            i += 2
        elif text.startswith("||", i):
            tokens.append(_Token("OR", "||", pos))
            i += 2
        elif c == "|":
            tokens.append(_Token("ABS", "|", pos))
            i += 1
        elif c in "()":
            tokens.append(_Token("LPAREN" if c == "(" else "RPAREN", c, pos))
            i += 1
        elif any(text.startswith(op, i) for op in _OPERATORS):
            op = next(op for op in _OPERATORS if text.startswith(op, i))
            tokens.append(_Token("OP", op, pos))
            i += len(op)
        elif c in "\"'":
            j, chars = i + 1, []
            while j < n and text[j] != c:
                if text[j] == "\\" and j + 1 < n and text[j + 1] == c:
                    chars.append(c)
                    j += 2
                else:
                    chars.append(text[j])
                    j += 1
            if j >= n:
                raise _invalid("stringa senza virgolette di chiusura", pos, expression)
            tokens.append(_Token("STRING", "".join(chars), pos))
            i = j + 1
        elif c in "&!":
            raise _invalid(f"simbolo {c!r} non previsto", pos, expression)
        else:
            j = i
            while j < n and text[j] not in _WORD_STOP:
                j += 1
            tokens.append(_Token("WORD", text[i:j], pos))
            i = j
    tokens.append(_Token("END", "", offset + n))
    return tokens


def _text_kind(column) -> bool:
    kind = np.asarray(column).dtype.kind
    return kind in "USO"


def _numeric_kind(column) -> bool:
    return np.asarray(column).dtype.kind in "iufb"


def _valid_mask(column) -> np.ndarray:
    mask = np.asarray(getattr(column, "mask", np.zeros(len(column), dtype=bool)), dtype=bool)
    if mask.shape != (len(column),):
        mask = np.zeros(len(column), dtype=bool) | np.broadcast_to(mask, (len(column),))
    return ~mask


def _text_values(column) -> np.ndarray:
    data = np.asarray(getattr(column, "data", column))
    if data.dtype.kind == "S":
        data = np.char.decode(data, "latin-1")
    return np.array([str(v).rstrip(" ") for v in data], dtype=object)


def _pattern(text: str, case_sensitive: bool) -> re.Pattern:
    parts, i = [], 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text) and text[i + 1] in "*?\\":
            parts.append(re.escape(text[i + 1]))
            i += 2
            continue
        parts.append(".*" if c == "*" else "." if c == "?" else re.escape(c))
        i += 1
    return re.compile("".join(parts), 0 if case_sensitive else re.IGNORECASE | re.DOTALL)


def _match_text(column, pattern: re.Pattern) -> np.ndarray:
    values = _text_values(column)
    uniques, inverse = np.unique(values.astype(str), return_inverse=True)
    hits = np.array([pattern.fullmatch(v) is not None for v in uniques], dtype=bool)
    return hits[inverse.reshape(-1)] if len(values) else np.zeros(0, dtype=bool)


class _Parser:
    def __init__(self, tokens: list[_Token], table: Table, expression: str, case_sensitive: bool) -> None:
        self.tokens, self.i, self.table = tokens, 0, table
        self.expression, self.case_sensitive = expression, case_sensitive

    def peek(self, k: int = 0) -> _Token:
        return self.tokens[min(self.i + k, len(self.tokens) - 1)]

    def take(self, kind: str) -> _Token:
        tok = self.peek()
        if tok.kind != kind:
            raise _invalid(f"atteso {kind}, trovato {tok.text or 'fine'!r}", tok.pos, self.expression)
        self.i += 1
        return tok

    def parse(self):
        node = self.disjunction()
        if self.peek().kind != "END":
            raise _invalid(f"simbolo inatteso {self.peek().text!r}", self.peek().pos, self.expression)
        return node

    def disjunction(self):
        node = self.conjunction()
        while self.peek().kind == "OR":
            self.i += 1
            node = ("or", node, self.conjunction())
        return node

    def conjunction(self):
        node = self.term()
        while self.peek().kind == "AND":
            self.i += 1
            node = ("and", node, self.term())
        return node

    def column(self, tok: _Token) -> str:
        if tok.text not in self.table.colnames:
            raise _invalid(f"colonna {tok.text!r} inesistente", tok.pos, self.expression)
        return tok.text

    def term(self):
        tok = self.peek()
        if tok.kind == "LPAREN":
            self.i += 1
            node = self.disjunction()
            self.take("RPAREN")
            return node
        if tok.kind == "ABS":
            self.i += 1
            name_tok = self.peek()
            if name_tok.kind not in ("COL", "WORD"):
                raise _invalid("dopo '|' serve una colonna", name_tok.pos, self.expression)
            self.i += 1
            self.take("ABS")
            return self.comparison(self.column(name_tok), name_tok, absolute=True)
        if tok.kind == "COL" or (tok.kind == "WORD" and self.peek(1).kind == "OP"):
            self.i += 1
            return self.comparison(self.column(tok), tok, absolute=False)
        if tok.kind in ("WORD", "STRING"):
            self.i += 1
            if not any(_text_kind(self.table[c]) for c in self.table.colnames):
                raise _invalid("testo da cercare, ma la tabella non ha colonne di testo", tok.pos, self.expression)
            return ("text", _pattern(tok.text, self.case_sensitive))
        raise _invalid(f"atteso un termine, trovato {tok.text or 'fine'!r}", tok.pos, self.expression)

    def comparison(self, name: str, tok: _Token, absolute: bool):
        op = self.take("OP")
        value = self.peek()
        if value.kind not in ("WORD", "STRING"):
            raise _invalid("dopo l'operatore serve un valore", value.pos, self.expression)
        self.i += 1
        column = self.table[name]
        if _numeric_kind(column):
            if value.kind != "WORD" or not _NUMBER.match(value.text):
                raise _invalid(f"colonna numerica {name!r}: serve un numero", value.pos, self.expression)
            return ("num", name, op.text, float(value.text), absolute)
        if _text_kind(column):
            if absolute:
                raise _invalid(f"|{name}|: il valore assoluto vale solo per le colonne numeriche", tok.pos,
                               self.expression)
            if op.text not in ("=", "!="):
                raise _invalid(f"colonna di testo {name!r}: ammessi solo = e !=", op.pos, self.expression)
            return ("str", name, op.text, _pattern(value.text, self.case_sensitive))
        raise _invalid(f"colonna {name!r} di tipo {column.dtype} non confrontabile", tok.pos, self.expression)


def _evaluate(node, table: Table) -> np.ndarray:
    kind = node[0]
    if kind == "and":
        return _evaluate(node[1], table) & _evaluate(node[2], table)
    if kind == "or":
        return _evaluate(node[1], table) | _evaluate(node[2], table)
    if kind == "num":
        _, name, op, value, absolute = node
        column = table[name]
        data = np.asarray(getattr(column, "data", column), dtype=np.float64)
        if absolute:
            data = np.abs(data)
        valid = _valid_mask(column) & np.isfinite(data)
        with np.errstate(invalid="ignore"):
            return np.asarray(_COMPARE[op](data, value), dtype=bool) & valid
    if kind == "str":
        _, name, op, pattern = node
        column = table[name]
        hit = _match_text(column, pattern)
        return (hit if op == "=" else ~hit) & _valid_mask(column)
    if kind == "text":
        out = np.zeros(len(table), dtype=bool)
        for name in table.colnames:
            if _text_kind(table[name]):
                out |= _match_text(table[name], node[1]) & _valid_mask(table[name])
        return out
    raise AssertionError(kind)


def _parse_expression(table: Table, expression: str, case_sensitive: bool):
    if not isinstance(expression, str):
        raise CatalogsError("EXPRESSION_INVALID", "l'espressione deve essere una stringa", position=0)
    stripped = expression.lstrip()
    offset = len(expression) - len(stripped)
    prefix = None
    if stripped[:1] in ("+", "-"):
        prefix, stripped, offset = stripped[0], stripped[1:], offset + 1
    tokens = _tokenize(stripped, offset, expression)
    if tokens[0].kind == "END":
        raise _invalid("espressione vuota", offset, expression)
    return prefix, _Parser(tokens, table, expression, case_sensitive).parse()


def search(table: CatalogTable, expression: str, selection=None, case_sensitive: bool = False) -> np.ndarray:
    """Maschera dei record che soddisfano l'espressione (D6, D13-1); validata per intero prima di eseguire."""
    prefix, node = _parse_expression(table.table, expression, case_sensitive)
    if prefix is not None:
        if selection is None:
            raise CatalogsError("EXPRESSION_INVALID", f"prefisso {prefix!r}: serve la selezione corrente (selection)",
                                position=0)
        selection = np.asarray(selection, dtype=bool)
        if selection.shape != (len(table.table),):
            raise CatalogsError("EXPRESSION_INVALID", f"selection: serve una maschera di {len(table.table)} valori",
                                position=0)
    found = _evaluate(node, table.table)
    if prefix == "+":
        return selection | found
    if prefix == "-":
        return selection & ~found
    return found


#: Forme ammesse per le regole di disegno (§3, D4).
PLOT_SHAPES: tuple[str, ...] = ("circle", "square", "diamond", "triangle", "cross", "plus", "dot")
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class SizeScale:
    """Dimensione lineare in una colonna: ``vmin``→``size_min``, ``vmax``→``size_max`` (anche invertita)."""

    column: str
    vmin: float
    vmax: float
    size_min: float
    size_max: float


@dataclass(frozen=True)
class PlotRule:
    """Regola di disegno: a quali record (espressione di search, assente = tutti), forma, colore, dimensione."""

    shape: str
    color: str
    size: float | SizeScale
    selection: str | None = None


@dataclass(frozen=True, eq=False)
class PlotStyle:
    """Esito delle regole per ogni record; la tabella non cambia."""

    rule: np.ndarray  # indice della regola applicata, -1 se nessuna
    shape: np.ndarray  # forma ("" se non disegnato)
    color: np.ndarray  # colore ("" se non disegnato)
    size: np.ndarray  # dimensione in pixel (NaN se non disegnato)
    drawn: np.ndarray
    counts: tuple[int, ...]  # record disegnati per regola
    missing_size: tuple[int, ...]  # record selezionati ma senza valore per la dimensione, per regola
    not_selected: int


def _rule_invalid(k: int, message: str) -> CatalogsError:
    return CatalogsError("PLOT_RULE_INVALID", f"regola {k}: {message}", rule=k)


def _positive(value) -> bool:
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool) and \
        np.isfinite(value) and value > 0


def set_plot_rules(table: CatalogTable, rules) -> PlotStyle:
    """Applica regole di disegno ordinate: ogni record prende la prima regola che lo seleziona (D4)."""
    rules = list(rules)
    n = len(table.table)
    masks = []
    for k, rule in enumerate(rules):
        if not isinstance(rule, PlotRule):
            raise _rule_invalid(k, "serve un PlotRule")
        if rule.shape not in PLOT_SHAPES:
            raise _rule_invalid(k, f"forma {rule.shape!r} fuori elenco ({', '.join(PLOT_SHAPES)})")
        if not isinstance(rule.color, str) or not _COLOR.match(rule.color):
            raise _rule_invalid(k, f"colore {rule.color!r}: serve #RRGGBB")
        if isinstance(rule.size, SizeScale):
            scale = rule.size
            if scale.column not in table.table.colnames or not _numeric_kind(table.table[scale.column]):
                raise _rule_invalid(k, f"dimensione: colonna numerica {scale.column!r} inesistente")
            if not (np.isfinite(scale.vmin) and np.isfinite(scale.vmax) and scale.vmin < scale.vmax):
                raise _rule_invalid(k, "dimensione: serve vmin < vmax, entrambi finiti")
            if not (_positive(scale.size_min) and _positive(scale.size_max)):
                raise _rule_invalid(k, "dimensione: size_min e size_max devono essere positivi")
        elif not _positive(rule.size):
            raise _rule_invalid(k, f"dimensione {rule.size!r}: serve un numero positivo o una SizeScale")
        if rule.selection is None:
            masks.append(np.ones(n, dtype=bool))
        else:
            prefix, node = _parse_expression(table.table, rule.selection, False)
            if prefix is not None:
                raise _rule_invalid(k, "la selezione di una regola non ammette i prefissi + e -")
            masks.append(_evaluate(node, table.table))
    applied = np.full(n, -1, dtype=int)
    for k in range(len(rules) - 1, -1, -1):  # la prima regola che seleziona vince
        applied[masks[k]] = k
    shape = np.full(n, "", dtype=object)
    color = np.full(n, "", dtype=object)
    size = np.full(n, np.nan)
    counts, missing = [], []
    for k, rule in enumerate(rules):
        rows = applied == k
        if isinstance(rule.size, SizeScale):
            scale = rule.size
            column = table.table[scale.column]
            values = np.asarray(getattr(column, "data", column), dtype=np.float64)
            ok = rows & _valid_mask(column) & np.isfinite(values)
            t = (np.clip(values[ok], scale.vmin, scale.vmax) - scale.vmin) / (scale.vmax - scale.vmin)
            size[ok] = scale.size_min + t * (scale.size_max - scale.size_min)
            missing.append(int(np.count_nonzero(rows & ~ok)))
        else:
            ok = rows
            size[ok] = float(rule.size)
            missing.append(0)
        shape[ok] = rule.shape
        color[ok] = rule.color
        counts.append(int(np.count_nonzero(ok)))
    return PlotStyle(rule=applied, shape=shape, color=color, size=size, drawn=np.isfinite(size),
                     counts=tuple(counts), missing_size=tuple(missing),
                     not_selected=int(np.count_nonzero(applied < 0)))


# --------------------------------------------------------------------------
# P4 — tabella delle funzioni (D13-8, D13-10), sottoinsiemi, statistiche,
# istogramma, grafico x-y, vista a record. Le colonne calcolate attendono la
# decisione sui numeri accanto a colonne con unità (D13-15).
# --------------------------------------------------------------------------


def skydist(ra1, dec1, ra2, dec2):
    """Distanza sferica in gradi tra posizioni in gradi (D13-10): ``astropy.coordinates.angular_separation``.

    Implementazione unica, usata anche dal modulo 17 (``angular_distance``).
    """
    values = [v.to(u.deg) if isinstance(v, u.Quantity) else np.asarray(v, dtype=np.float64) * u.deg
              for v in (ra1, dec1, ra2, dec2)]
    return angular_separation(*values).to_value(u.deg)


def _sind(x):
    return np.sin(np.deg2rad(x))


#: Tabella delle funzioni condivisa con la calcolatrice del 18 (D13-8): nome → (numero di argomenti, funzione).
#: Valori ``float64`` senza unità; trigonometriche senza ``d`` in radianti, con ``d`` in gradi.
#: ``min``/``max`` accettano due o più argomenti (``None`` = variabile); ``round`` è ``numpy.round``.
FUNCTIONS: dict[str, tuple[int | None, object]] = {
    "exp": (1, np.exp),
    "ln": (1, np.log),
    "log": (1, np.log10),
    "sqrt": (1, np.sqrt),
    "ceil": (1, np.ceil),
    "floor": (1, np.floor),
    "round": (1, np.round),
    "abs": (1, np.abs),
    "min": (None, lambda *xs: functools.reduce(np.minimum, xs)),
    "max": (None, lambda *xs: functools.reduce(np.maximum, xs)),
    "sin": (1, np.sin),
    "cos": (1, np.cos),
    "tan": (1, np.tan),
    "asin": (1, np.arcsin),
    "acos": (1, np.arccos),
    "atan": (1, np.arctan),
    "atan2": (2, np.arctan2),
    "sind": (1, _sind),
    "cosd": (1, lambda x: np.cos(np.deg2rad(x))),
    "tand": (1, lambda x: np.tan(np.deg2rad(x))),
    "asind": (1, lambda x: np.rad2deg(np.arcsin(x))),
    "acosd": (1, lambda x: np.rad2deg(np.arccos(x))),
    "atand": (1, lambda x: np.rad2deg(np.arctan(x))),
    "atan2d": (2, lambda y, x: np.rad2deg(np.arctan2(y, x))),
    "sinh": (1, np.sinh),
    "cosh": (1, np.cosh),
    "tanh": (1, np.tanh),
    "rad2deg": (1, np.rad2deg),
    "deg2rad": (1, np.deg2rad),
    "dist": (4, lambda x1, y1, x2, y2: np.hypot(np.subtract(x2, x1), np.subtract(y2, y1))),
    "skydist": (4, skydist),
}
#: Costanti della calcolatrice (D18-1).
CONSTANTS: dict[str, float] = {"pi": math.pi, "e": math.e}


def _selection_mask(table: CatalogTable, selection) -> np.ndarray:
    mask = np.asarray(selection)
    if mask.dtype != bool or mask.shape != (len(table.table),):
        raise CatalogsError("COLUMN_TYPE_UNSUPPORTED", f"selezione: serve una maschera booleana di {len(table.table)} valori")
    return mask


def subset(table: CatalogTable, selection, inplace: bool = False) -> CatalogTable:
    """Sottoinsieme dei record selezionati: nuova tabella; con ``inplace=True`` modifica quella data (citato)."""
    mask = _selection_mask(table, selection)
    kept = int(np.count_nonzero(mask))
    _check_memory("sottoinsieme", int(_table_bytes(table.table) * kept / max(len(table.table), 1)), table.limits)
    step = f"sottoinsieme: {kept} record su {len(table.table)}"
    if inplace:
        table.table.remove_rows(np.flatnonzero(~mask))
        note = ("INPLACE", f"{step}: tabella data modificata in posto (inplace=True)")
        object.__setattr__(table, "history", table.history + (f"{step} (in posto, inplace=True)",))
        object.__setattr__(table, "warnings", table.warnings + (note,))
        return table
    return dataclasses.replace(table, table=table.table[mask], history=table.history + (step,))


_FRAME_TO_COOSYS = {"icrs": "ICRS", "fk5": "eq_FK5", "fk4": "eq_FK4", "galactic": "galactic",
                    "supergalactic": "supergalactic"}


def _catalog_votable(table: CatalogTable, part: Table):
    """VOTable di ``part`` con UCD e ``COOSYS`` delle colonne di posizione di ``table``.

    Usato da ``save_subset`` e dall'esportazione del modulo 14 (un solo scrittore).
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        vot = votable_from_table(part)
    resource = vot.resources[0]
    vtable = vot.get_first_table()
    for field_, name in zip(vtable.fields, part.colnames, strict=True):
        ucd = part[name].meta.get("ucd")
        if ucd:
            field_.ucd = ucd
    notes = []
    pos = table.positions
    if pos is not None and pos.frame in _FRAME_TO_COOSYS:
        coosys = CooSys(ID="a2_coosys", system=_FRAME_TO_COOSYS[pos.frame],
                        equinox=pos.equinox, epoch=pos.epoch)
        resource.coordinate_systems.append(coosys)
        for field_ in vtable.fields:
            if field_.name in (pos.lon, pos.lat):
                field_.ref = "a2_coosys"
    elif pos is not None:
        notes.append(f"sistema {pos.frame!r} senza COOSYS standard: colonne di posizione non marcate nel file")
    return vot, notes


def save_subset(table: CatalogTable, selection, path, overwrite: bool = False) -> Path:
    """Salva il sottoinsieme in un VOTable scelto dall'utente, con provenienza (D13-13); mai nella cache."""
    target = Path(os.fspath(path)).expanduser()
    if target.exists() and not overwrite:
        raise CatalogsError("FILE_EXISTS", f"{target}: esiste già; usare overwrite=True")
    mask = _selection_mask(table, selection)
    vot, notes = _catalog_votable(table, table.table[mask])
    resource = vot.resources[0]
    pos = table.positions
    saved_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    info = {
        "A2ORIGIN": table.origin,
        "A2DATE": table.retrieved_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "A2SAVED": saved_at,
        "A2SELECTED": f"{int(mask.sum())} record su {len(table.table)}",
        "A2HISTORY": " | ".join(table.history) or "nessuna operazione",
    }
    if pos is not None:
        info["A2POSITIONS"] = f"{pos.lon}/{pos.lat}, frame {pos.frame}, fonte {pos.source}"
    for note in notes:
        info.setdefault("A2NOTE", note)
    for name, value in info.items():
        resource.infos.append(Info(name=name, value=str(value)))
    vot.to_xml(str(target))
    return target


@dataclass(frozen=True)
class ColumnStatistics:
    """Statistiche dei valori validi (non mascherati e finiti) di una colonna."""

    column: str
    minimum: float | None
    maximum: float | None
    mean: float | None
    std: float | None  # deviazione standard di numpy (ddof = 0), scritta nel risultato
    valid: int
    missing: int
    unit: object
    ddof: int = 0


def _numeric_values(table: CatalogTable, name: str) -> tuple[np.ndarray, np.ndarray]:
    if name not in table.table.colnames:
        raise CatalogsError("COLUMN_TYPE_UNSUPPORTED", f"colonna {name!r} inesistente")
    column = table.table[name]
    if not _numeric_kind(column):
        raise CatalogsError("COLUMN_TYPE_UNSUPPORTED", f"colonna {name!r} di tipo {column.dtype}: serve una colonna numerica")
    values = np.asarray(getattr(column, "data", column), dtype=np.float64)
    return values, _valid_mask(column) & np.isfinite(values)


def column_statistics(table: CatalogTable, column: str) -> ColumnStatistics:
    """Minimo, massimo, media, deviazione standard e conteggi dei valori validi e mancanti."""
    values, valid = _numeric_values(table, column)
    good = values[valid]
    stats = (float(good.min()), float(good.max()), float(good.mean()), float(good.std())) if good.size else (None,) * 4
    return ColumnStatistics(column, *stats, valid=int(good.size), missing=int(values.size - good.size),
                            unit=table.table[column].unit)


@dataclass(frozen=True, eq=False)
class Histogram:
    counts: np.ndarray
    edges: np.ndarray
    unit: object
    excluded: int  # valori mancanti o non finiti, non contati


def histogram(table: CatalogTable, column: str, bins) -> Histogram:
    """Istogramma dei valori validi con ``numpy.histogram``; ``bins`` obbligatorio (numero o bordi)."""
    if bins is None:
        raise CatalogsError("COLUMN_TYPE_UNSUPPORTED", "istogramma: bins obbligatorio (numero o bordi)")
    values, valid = _numeric_values(table, column)
    if np.ndim(bins) == 0:
        if isinstance(bins, bool) or not isinstance(bins, (int, np.integer)) or bins <= 0:
            raise CatalogsError("COLUMN_TYPE_UNSUPPORTED", f"bins {bins!r}: serve un intero positivo o bordi crescenti")
    else:
        edges = np.asarray(bins, dtype=np.float64)
        if edges.size < 2 or not np.all(np.diff(edges) > 0):
            raise CatalogsError("COLUMN_TYPE_UNSUPPORTED", "bins: bordi strettamente crescenti, almeno due")
    counts, edges = np.histogram(values[valid], bins=bins)
    return Histogram(counts=counts, edges=edges, unit=table.table[column].unit,
                     excluded=int(values.size - np.count_nonzero(valid)))


@dataclass(frozen=True, eq=False)
class XYData:
    x: np.ndarray
    y: np.ndarray
    valid: np.ndarray  # True dove entrambi i valori sono validi
    x_unit: object
    y_unit: object


def xy_plot(table: CatalogTable, x: str, y: str) -> XYData:
    """Dati del grafico x-y: valori ``float64`` e maschera dei punti validi; il disegno è della UI."""
    xv, xok = _numeric_values(table, x)
    yv, yok = _numeric_values(table, y)
    return XYData(x=xv, y=yv, valid=xok & yok, x_unit=table.table[x].unit, y_unit=table.table[y].unit)


def record_view(table: CatalogTable, index: int) -> list[dict[str, object]]:
    """Tutti i valori di un record con unità, UCD e stato di mancante."""
    if isinstance(index, bool) or not isinstance(index, (int, np.integer)) or not 0 <= index < len(table.table):
        raise CatalogsError("COLUMN_TYPE_UNSUPPORTED", f"record {index!r} fuori da 0…{len(table.table) - 1}")
    out = []
    for name in table.table.colnames:
        column = table.table[name]
        missing = bool(np.asarray(getattr(column, "mask", np.zeros(len(column), dtype=bool)))[index])
        out.append({"name": name, "value": None if missing else column[index], "unit": column.unit,
                    "unit_unrecognized": column.meta.get("unit_unrecognized"), "ucd": column.meta.get("ucd"),
                    "missing": missing})
    return out


# --------------------------------------------------------------------------
# P5 — epoca e moto proprio (calcolo: modulo 10). Il filtro temporale
# (time_filter) attende la decisione D13-16.
# --------------------------------------------------------------------------

_PM_UNIT = u.mas / u.yr


@dataclass(frozen=True, eq=False)
class Propagation:
    """Nuova tabella con ``<lon>_prop``, ``<lat>_prop``, ``<lon>_prop_mode`` e il report (§3)."""

    table: CatalogTable
    target_epoch: Time
    source_epoch: str  # epoca di origine e sua fonte
    pm_ra_includes_cosdec: bool
    counts: dict[str, int]  # righe per modo: full, pm_only, missing
    notes: tuple[str, ...]


@dataclass(frozen=True, eq=False)
class ProperMotionArrows:
    """Frecce del moto proprio: dalla posizione all'epoca della tabella a quella dopo ``scale`` anni."""

    lon_start: np.ndarray
    lat_start: np.ndarray
    lon_end: np.ndarray  # mascherato (NaN) per le righe senza moto proprio
    lat_end: np.ndarray
    mode: np.ndarray
    scale: u.Quantity
    counts: dict[str, int]
    notes: tuple[str, ...]


def _quantity_column(table: Table, name: str, unit, what: str):
    if name not in table.colnames:
        raise CatalogsError("PROPER_MOTION_MISSING" if what.startswith("moto") else "COLUMN_TYPE_UNSUPPORTED",
                            f"{what}: colonna {name!r} inesistente")
    column = table[name]
    if not _numeric_kind(column):
        raise CatalogsError("COLUMN_TYPE_UNSUPPORTED", f"{what}: colonna {name!r} non numerica")
    if column.unit is None or not column.unit.is_equivalent(unit):
        raise CatalogsError("UNIT_INCOMPATIBLE", f"{what}: colonna {name!r} in unità {column.unit}, serve {unit}")
    values = np.asarray(getattr(column, "data", column), dtype=np.float64)
    valid = _valid_mask(column) & np.isfinite(values)
    return (values * column.unit).to(unit), valid


def _source_epochs(table: CatalogTable, source_epoch) -> tuple[np.ndarray, str]:
    """Epoca di origine per riga: colonna con UCD ``time.epoch``, COOSYS o parametro; mai assunta."""
    t = table.table
    columns = [n for n in t.colnames if "time.epoch" in _ucd_words(t[n].meta.get("ucd"))]
    coosys_epoch = table.positions.epoch if table.positions is not None else None
    from_metadata = bool(columns) or coosys_epoch is not None
    if from_metadata and source_epoch is not None:
        raise CatalogsError("EPOCH_INVALID", "l'epoca di origine è già nei metadati: source_epoch non si usa")
    if len(columns) > 1:
        raise CatalogsError("EPOCH_INVALID", f"più colonne con UCD time.epoch {columns}: nessuna scelta")
    if columns:
        name = columns[0]
        column = t[name]
        if column.unit is None or not column.unit.is_equivalent(u.yr):
            raise CatalogsError("EPOCH_INVALID", f"colonna d'epoca {name!r} in unità {column.unit}: servono anni "
                                "giuliani; altrimenti source_epoch")
        values = np.asarray(getattr(column, "data", column), dtype=np.float64) * column.unit
        out = np.array([None if not ok else float(v) for v, ok in
                        zip(values.to_value(u.yr), _valid_mask(column) & np.isfinite(values.value), strict=True)],
                       dtype=object)
        return out, f"colonna {name!r} (UCD time.epoch, anni giuliani)"
    if coosys_epoch is not None:
        return np.full(len(t), coosys_epoch, dtype=object), f"COOSYS (epoca {coosys_epoch})"
    if source_epoch is None:
        raise CatalogsError("EPOCH_INVALID", "epoca di origine non nei metadati: indicare source_epoch (mai assunta)")
    return np.full(len(t), source_epoch, dtype=object), f"parametro source_epoch ({source_epoch})"


def _move(table: CatalogTable, target, *, pm_ra, pm_dec, pm_ra_includes_cosdec, parallax, radial_velocity,
          source_epoch, years=None):
    """Calcolo comune di propagate e delle frecce: gruppi di righe con la stessa epoca e lo stesso modo."""
    if not isinstance(pm_ra_includes_cosdec, bool):
        raise CatalogsError("PROPER_MOTION_MISSING", "pm_ra_includes_cosdec obbligatorio (True o False): mai assunto")
    pos = table.positions
    if pos is None:
        raise CatalogsError("NO_COORD_COLUMNS", "nessuna colonna di posizione: confermarle prima")
    if pos.frame is None:
        raise CatalogsError("FRAME_UNKNOWN", "sistema delle colonne di posizione non dichiarato")
    t = table.table
    lon, lon_ok = _quantity_column(t, pos.lon, u.deg, "posizione")
    lat, lat_ok = _quantity_column(t, pos.lat, u.deg, "posizione")
    pmra, pmra_ok = _quantity_column(t, pm_ra, _PM_UNIT, "moto proprio")
    pmde, pmde_ok = _quantity_column(t, pm_dec, _PM_UNIT, "moto proprio")
    plx_ok = np.zeros(len(t), dtype=bool)
    if parallax is not None:
        plx, plx_ok = _quantity_column(t, parallax, u.mas, "parallasse")
        plx_ok &= plx.value > 0
    rv_ok = np.zeros(len(t), dtype=bool)
    if radial_velocity is not None:
        rv, rv_ok = _quantity_column(t, radial_velocity, u.km / u.s, "velocità radiale")
    epochs, epoch_source = _source_epochs(table, source_epoch)
    if not pm_ra_includes_cosdec:
        pmra = pmra * np.cos(lat)  # moto proprio in RA portato a pm_ra·cos δ, dichiarato
    present = lon_ok & lat_ok & pmra_ok & pmde_ok & np.array([e is not None for e in epochs])
    mode = np.where(~present, "missing", np.where(plx_ok, "full", "pm_only")).astype(object)
    end_lon, end_lat = np.full(len(t), np.nan), np.full(len(t), np.nan)
    notes: list[str] = []
    target_time = None
    groups: dict[tuple, list[int]] = {}
    for k in np.flatnonzero(present):
        key = (str(epochs[k]), mode[k], bool(rv_ok[k]) if mode[k] == "full" else False)
        groups.setdefault(key, []).append(int(k))
    for (epoch_key, row_mode, with_rv), rows in groups.items():
        idx = np.array(rows)
        try:
            start = SkyFrame.from_lonlat(lon[idx], lat[idx], pos.frame, equinox=pos.equinox,
                                         epoch=epochs[idx[0]])
            group_target = target if years is None else start.epoch + years
            kwargs = dict(pm_ra_cosdec=pmra[idx], pm_dec=pmde[idx], target_epoch=group_target)
            if row_mode == "full":
                kwargs["parallax"] = plx[idx]
                kwargs["radial_velocity"] = rv[idx] if with_rv else None
            else:
                kwargs.update(parallax=None, proper_motion_only=True)
            moved = propagate_position(start, **kwargs)
        except CoordinatesWcsError as exc:
            raise CatalogsError(exc.code, f"propagazione: {exc.message}") from exc
        end_lon[idx] = moved.position.lon.to_value(u.deg)
        end_lat[idx] = moved.position.lat.to_value(u.deg)
        target_time = moved.target_epoch if years is None else target_time
        notes.extend(f"[{row_mode}, epoca {epoch_key}] {n}" for n in moved.notes if
                     f"[{row_mode}, epoca {epoch_key}] {n}" not in notes)
    counts = {m: int(np.count_nonzero(mode == m)) for m in ("full", "pm_only", "missing")}
    if not pm_ra_includes_cosdec:
        notes.append("moto proprio in RA senza cos δ nella colonna: moltiplicato per cos δ della posizione")
    return lon, lat, end_lon, end_lat, mode, counts, epoch_source, target_time, notes


def propagate(table: CatalogTable, epoch, *, pm_ra: str, pm_dec: str, pm_ra_includes_cosdec, parallax=None,
              radial_velocity=None, source_epoch=None) -> Propagation:
    """Posizioni all'epoca richiesta (D9, P5) con il modulo 10; nuove colonne, originali intatte."""
    pos = table.positions
    if pos is None:
        raise CatalogsError("NO_COORD_COLUMNS", "nessuna colonna di posizione: confermarle prima")
    names = (f"{pos.lon}_prop", f"{pos.lat}_prop", f"{pos.lon}_prop_mode")
    existing = [n for n in names if n in table.table.colnames]
    if existing:
        raise CatalogsError("COLUMN_NAME_EXISTS", f"colonne già presenti: {existing}")
    if epoch is None:
        raise CatalogsError("EPOCH_INVALID", "epoca di arrivo obbligatoria")
    lon, lat, end_lon, end_lat, mode, counts, source, target, notes = _move(
        table, epoch, pm_ra=pm_ra, pm_dec=pm_dec, pm_ra_includes_cosdec=pm_ra_includes_cosdec, parallax=parallax,
        radial_velocity=radial_velocity, source_epoch=source_epoch)
    if target is None:
        target = SkyFrame.from_lonlat(0 * u.deg, 0 * u.deg, "icrs", epoch=epoch).epoch  # solo per dichiararla
    new = table.table.copy()
    missing = mode == "missing"
    for name, values, original in ((names[0], end_lon, pos.lon), (names[1], end_lat, pos.lat)):
        column = MaskedColumn((values * u.deg).to_value(table.table[original].unit), mask=missing,
                              unit=table.table[original].unit)
        column.meta["epoch"] = target.isot + f" ({target.scale})"
        new[name] = column
    new[names[2]] = mode.astype(str)
    warnings_ = list(table.warnings)
    if counts["missing"]:
        warnings_.append(("PROPER_MOTION_ROW_MISSING", f"{counts['missing']} righe senza moto proprio (o posizione o "
                          "epoca): posizione propagata mancante, mai moto proprio nullo assunto"))
    step = (f"propagazione a {target.isot} ({target.scale}) da {source}; cos δ "
            f"{'incluso' if pm_ra_includes_cosdec else 'non incluso'}; righe full {counts['full']}, "
            f"pm_only {counts['pm_only']}, missing {counts['missing']}")
    result = dataclasses.replace(table, table=new, warnings=tuple(warnings_), history=table.history + (step,))
    return Propagation(table=result, target_epoch=target, source_epoch=source,
                       pm_ra_includes_cosdec=pm_ra_includes_cosdec, counts=counts, notes=tuple(notes))


def proper_motion_arrows(table: CatalogTable, scale, *, pm_ra: str, pm_dec: str, pm_ra_includes_cosdec,
                         parallax=None, radial_velocity=None, source_epoch=None) -> ProperMotionArrows:
    """Dati delle frecce del moto proprio (D10): ``scale`` anni obbligatorio; il disegno è della UI."""
    if not isinstance(scale, u.Quantity) or not scale.unit.is_equivalent(u.yr) or not np.isfinite(scale.value) \
            or scale.value == 0:
        raise CatalogsError("EPOCH_INVALID", "scale obbligatoria: un intervallo di tempo non nullo (es. 1000 * u.yr)")
    lon, lat, end_lon, end_lat, mode, counts, source, _, notes = _move(
        table, None, pm_ra=pm_ra, pm_dec=pm_dec, pm_ra_includes_cosdec=pm_ra_includes_cosdec, parallax=parallax,
        radial_velocity=radial_velocity, source_epoch=source_epoch, years=scale.to(u.yr))
    return ProperMotionArrows(lon_start=lon.to_value(u.deg), lat_start=lat.to_value(u.deg), lon_end=end_lon,
                              lat_end=end_lat, mode=mode.astype(str), scale=scale.to(u.yr), counts=counts,
                              notes=tuple(notes) + (f"epoca di origine da {source}",))


# --------------------------------------------------------------------------
# P4 — colonne calcolate (H8; D13-15): analizzatore ``ast`` a elenco chiuso
# (D18-1), nessuna esecuzione di codice; ``^`` è la potenza.
# --------------------------------------------------------------------------

_BINARY = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Mod: "%", ast.Pow: "^"}
#: Operazioni in cui un numero scritto prende l'unità dell'altro operando (D13-15, come in search).
_UNIT_FOLLOWING = ("+", "-", "%")


@dataclass(frozen=True)
class _Value:
    """Valore intermedio: array (con o senza unità) e se viene solo da numeri scritti e costanti."""

    data: object
    literal: bool


def _column_invalid(message: str, position: int, expression: str) -> CatalogsError:
    return CatalogsError("COLUMN_EXPRESSION_INVALID", f"{message} (carattere {position}): {expression!r}",
                         position=position)


def _translate_expression(expression: str, table: Table) -> tuple[str, list[int], dict[str, str]]:
    """Sostituisce ``${nome}`` con segnaposto e ``^`` con ``**``; mappa le posizioni sul testo originale."""
    out: list[str] = []
    origin: list[int] = []
    names: dict[str, str] = {}
    i = 0
    while i < len(expression):
        if expression.startswith("**", i):
            raise _column_invalid("'**' non previsto: la potenza si scrive '^'", i, expression)
        if expression.startswith("${", i):
            end = expression.find("}", i + 2)
            if end < 0:
                raise _column_invalid("riferimento ${...} senza '}'", i, expression)
            name = expression[i + 2:end]
            if name not in table.colnames:
                raise _column_invalid(f"colonna {name!r} inesistente", i, expression)
            key = next((k for k, v in names.items() if v == name), f"_c{len(names)}")
            names[key] = name
            out.extend(key)
            origin.extend([i] * len(key))
            i = end + 1
        elif expression[i] == "^":
            out.extend("**")
            origin.extend([i, i])
            i += 1
        else:
            out.append(expression[i])
            origin.append(i)
            i += 1
    return "".join(out), origin, names


class _ColumnEvaluator:
    def __init__(self, expression: str, text: str, origin: list[int], names: dict[str, str], table: Table) -> None:
        self.expression, self.text, self.origin, self.names, self.table = expression, text, origin, names, table
        self.used: set[str] = set()

    def position(self, node) -> int:
        offset = getattr(node, "col_offset", 0)
        return self.origin[offset] if offset < len(self.origin) else len(self.expression)

    def fail(self, message: str, node) -> CatalogsError:
        return _column_invalid(message, self.position(node), self.expression)

    def check(self, node) -> None:
        """Validazione completa prima del calcolo: solo i nodi dell'elenco chiuso."""
        if isinstance(node, ast.Expression):
            return self.check(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            self.check(node.left)
            return self.check(node.right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return self.check(node.operand)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return None
        if isinstance(node, ast.Name):
            if node.id in self.names or node.id in CONSTANTS:
                return None
            raise self.fail(f"nome {node.id!r} non previsto (colonne come ${{nome}}; costanti {', '.join(CONSTANTS)})",
                            node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            if node.func.id not in FUNCTIONS:
                raise self.fail(f"funzione {node.func.id!r} non prevista", node)
            arity = FUNCTIONS[node.func.id][0]
            if (arity is None and len(node.args) < 2) or (arity is not None and len(node.args) != arity):
                raise self.fail(f"{node.func.id}: numero di argomenti errato", node)
            for arg in node.args:
                if isinstance(arg, ast.Starred):
                    raise self.fail("argomenti con '*' non previsti", arg)
                self.check(arg)
            return None
        raise self.fail(f"costrutto {type(node).__name__} non previsto", node)

    def column(self, key: str) -> _Value:
        name = self.names[key]
        self.used.add(name)
        column = self.table[name]
        if not _numeric_kind(column):
            raise CatalogsError("COLUMN_TYPE_UNSUPPORTED", f"colonna {name!r} di tipo {column.dtype}: serve un numero")
        if column.meta.get("unit_unrecognized"):
            raise CatalogsError("UNIT_INCOMPATIBLE", f"colonna {name!r}: unità {column.meta['unit_unrecognized']!r} "
                                "non riconosciuta, nessun calcolo con unità ignote")
        data = np.asarray(getattr(column, "data", column), dtype=np.float64)
        return _Value(data * column.unit if column.unit is not None else data, literal=False)

    @staticmethod
    def adopt(literal: _Value, other: _Value) -> _Value:
        """Un numero scritto prende l'unità dell'altro operando (D13-15)."""
        if literal.literal and not other.literal and isinstance(other.data, u.Quantity) \
                and not isinstance(literal.data, u.Quantity):
            return _Value(literal.data * other.data.unit, literal=True)
        return literal

    def evaluate(self, node) -> _Value:
        if isinstance(node, ast.Expression):
            return self.evaluate(node.body)
        if isinstance(node, ast.Constant):
            return _Value(float(node.value), literal=True)
        if isinstance(node, ast.Name):
            if node.id in CONSTANTS:
                return _Value(CONSTANTS[node.id], literal=True)
            return self.column(node.id)
        if isinstance(node, ast.UnaryOp):
            value = self.evaluate(node.operand)
            return _Value(-value.data if isinstance(node.op, ast.USub) else value.data, value.literal)
        if isinstance(node, ast.BinOp):
            op = _BINARY[type(node.op)]
            left, right = self.evaluate(node.left), self.evaluate(node.right)
            if op in _UNIT_FOLLOWING:
                left, right = self.adopt(left, right), self.adopt(right, left)
            function = {"+": np.add, "-": np.subtract, "*": np.multiply, "/": np.divide, "%": np.mod,
                        "^": np.power}[op]
            with np.errstate(divide="ignore", invalid="ignore"):
                return _Value(function(left.data, right.data), left.literal and right.literal)
        if isinstance(node, ast.Call):
            name = node.func.id
            args = [self.evaluate(a) for a in node.args]
            if name in ("min", "max"):
                args = [functools.reduce(lambda acc, other: self.adopt(acc, other), args[:k] + args[k + 1:], a)
                        for k, a in enumerate(args)]
            with np.errstate(divide="ignore", invalid="ignore"):
                result = FUNCTIONS[name][1](*[a.data for a in args])
            if name == "skydist":
                result = np.asarray(result, dtype=np.float64) * u.deg  # skydist: gradi
            return _Value(result, all(a.literal for a in args))
        raise AssertionError(type(node).__name__)


def calculated_column(table: CatalogTable, name: str, expression: str, unit=None, ucd: str | None = None,
                      decimals: int | None = None, inplace: bool = False) -> CatalogTable:
    """Nuova colonna da un'espressione con ``${colonna}`` (H8): ``float64``, unità da ``astropy.units``."""
    if not isinstance(name, str) or not name.strip():
        raise CatalogsError("COLUMN_EXPRESSION_INVALID", "nome della colonna obbligatorio", position=0)
    if name in table.table.colnames:
        raise CatalogsError("COLUMN_NAME_EXISTS", f"colonna {name!r} già presente: nessuna sovrascrittura")
    if decimals is not None and (isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0):
        raise CatalogsError("COLUMN_EXPRESSION_INVALID", f"decimals {decimals!r}: intero ≥ 0", position=0)
    if not isinstance(expression, str) or not expression.strip():
        raise CatalogsError("COLUMN_EXPRESSION_INVALID", "espressione vuota", position=0)
    text, origin, names = _translate_expression(expression, table.table)
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as exc:
        # Il parser di Python non sempre indica dove (offset 0): allora l'errore è alla fine dell'espressione.
        offset = (exc.offset or 0) - 1 + (len(text) - len(text.lstrip()))
        position = origin[offset] if 0 <= offset < len(origin) and exc.offset else len(expression)
        raise _column_invalid("sintassi non valida", position, expression) from exc
    evaluator = _ColumnEvaluator(expression, text.strip(), origin[len(text) - len(text.lstrip()):], names, table.table)
    evaluator.check(tree)
    _check_memory(f"colonna calcolata {name!r}", len(table.table) * 8 * (len(names) + 2), table.limits)
    try:
        value = evaluator.evaluate(tree).data
        if unit is not None:
            target = u.Unit(unit)
            value = value.to(target) if isinstance(value, u.Quantity) else value * target
    except (u.UnitsError, u.UnitTypeError, u.UnitConversionError, TypeError, ValueError) as exc:
        raise CatalogsError("UNIT_INCOMPATIBLE", f"colonna calcolata {name!r}: {exc}") from exc
    values = np.broadcast_to(np.asarray(getattr(value, "value", value), dtype=np.float64), (len(table.table),))
    missing = np.zeros(len(table.table), dtype=bool)
    for used in evaluator.used:
        missing |= ~_valid_mask(table.table[used])
    column = MaskedColumn(values.copy(), mask=missing, name=name,
                          unit=value.unit if isinstance(value, u.Quantity) else None)
    column.meta.update({"calculated": True, "expression": expression})
    if ucd:
        column.meta["ucd"] = ucd
    if decimals is not None:
        column.format = f".{decimals}f"
    step = f"colonna calcolata {name!r} = {expression}" + (f" [{column.unit}]" if column.unit is not None else "")
    if inplace:
        table.table[name] = column
        object.__setattr__(table, "history", table.history + (f"{step} (in posto, inplace=True)",))
        object.__setattr__(table, "warnings", table.warnings + (("INPLACE", f"{step}: tabella data modificata"),))
        return table
    new = table.table.copy()
    new[name] = column
    return dataclasses.replace(table, table=new, history=table.history + (step,))


# --------------------------------------------------------------------------
# P5 — filtro temporale (H3; D13-16)
# --------------------------------------------------------------------------

_TIMESCALES = {"TT": "tt", "TDB": "tdb", "TCB": "tcb", "TCG": "tcg", "TAI": "tai", "UTC": "utc", "UT": "ut1",
               "UT1": "ut1"}


@dataclass(frozen=True, eq=False)
class TimeSelection:
    """Record con epoca osservativa in ``[start, end]`` (intervallo chiuso), con formato e scala dichiarati."""

    mask: np.ndarray
    column: str
    time_format: str
    scale: str
    source: str  # "TIMESYS" o "parametri"
    excluded_missing: int


def time_filter(table: CatalogTable, start: Time, end: Time, *, column: str, time_format: str | None = None,
                scale: str | None = None) -> TimeSelection:
    """Selezione per epoca osservativa (H3): colonna indicata dall'utente, formato e scala dal TIMESYS o dichiarati."""
    if column not in table.table.colnames:
        raise CatalogsError("COLUMN_TYPE_UNSUPPORTED", f"colonna {column!r} inesistente")
    if not isinstance(start, Time) or not isinstance(end, Time):
        raise CatalogsError("EPOCH_INVALID", "start ed end devono essere oggetti Time con scala dichiarata")
    if start > end:
        raise CatalogsError("EPOCH_INVALID", "intervallo vuoto: start > end")
    col = table.table[column]
    valid = _valid_mask(col)
    timesys = col.meta.get("timesys")
    if timesys is not None:
        if time_format is not None or scale is not None:
            raise CatalogsError("EPOCH_INVALID", "formato e scala sono già nel TIMESYS: non si passano")
        astropy_scale = _TIMESCALES.get((timesys.get("timescale") or "").upper())
        if astropy_scale is None:
            raise CatalogsError("EPOCH_INVALID", f"scala {timesys.get('timescale')!r} del TIMESYS non supportata")
        origin = timesys.get("timeorigin")
        values = np.asarray(getattr(col, "data", col), dtype=np.float64)
        if origin is not None:
            jd0 = {"MJD-origin": 2400000.5, "JD-origin": 0.0}.get(origin)
            if jd0 is None:
                try:
                    jd0 = float(origin)
                except ValueError as exc:
                    raise CatalogsError("EPOCH_INVALID", f"timeorigin {origin!r} non valido") from exc
            if col.unit is None or not col.unit.is_equivalent(u.d):
                raise CatalogsError("EPOCH_INVALID", f"colonna {column!r}: con timeorigin servono tempi con unità")
            days = (values * col.unit).to_value(u.d)
            times, fmt = Time(jd0 + np.where(valid & np.isfinite(days), days, 0.0), format="jd",
                              scale=astropy_scale), f"jd (origine {origin})"
        elif col.unit is not None and col.unit.is_equivalent(u.yr):
            years = (values * col.unit).to_value(u.yr)
            times, fmt = Time(np.where(valid & np.isfinite(years), years, 2000.0), format="jyear",
                              scale=astropy_scale), "jyear"
        else:
            raise CatalogsError("EPOCH_INVALID", f"colonna {column!r}: TIMESYS senza timeorigin e valori non in anni")
        valid &= np.isfinite(values)
        source, used_scale = "TIMESYS", astropy_scale
    else:
        if time_format is None or scale is None:
            raise CatalogsError("EPOCH_INVALID", f"colonna {column!r} senza TIMESYS: time_format e scale obbligatori "
                                "(mai assunti)")
        raw = np.asarray(getattr(col, "data", col))
        if raw.dtype.kind in "iuf":
            raw = raw.astype(np.float64)
            valid &= np.isfinite(raw)
            filler = raw[valid][0] if valid.any() else 0.0
        else:
            raw = np.array([str(v) for v in raw], dtype=str)
            filler = raw[valid][0] if valid.any() else None
        if not valid.any():
            return TimeSelection(np.zeros(len(col), dtype=bool), column, time_format, scale, "parametri", len(col))
        try:
            times = Time(np.where(valid, raw, filler), format=time_format, scale=scale)
        except (ValueError, TypeError) as exc:
            raise CatalogsError("EPOCH_INVALID", f"colonna {column!r}: valori non leggibili come {time_format} "
                                f"({exc})") from exc
        fmt, source, used_scale = time_format, "parametri", scale
    mask = valid & (times >= start) & (times <= end)
    return TimeSelection(mask=np.asarray(mask, dtype=bool), column=column, time_format=fmt, scale=used_scale,
                         source=source, excluded_missing=int(np.count_nonzero(~valid)))



# --------------------------------------------------------------------------
# P6 — Cataloghi da servizio e da URL, colonna DataLink (tramite il modulo 14)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FixedCollection:
    """Collezione del gruppo fisso (D13-3): servizio TAP dell'elenco del 14 e tabella."""

    id: str
    title: str
    server: str  # voce dell'elenco dei server del modulo 14
    table: str  # nome della tabella nel servizio TAP


#: Gruppo fisso (D13-3), identificativi verificati il 2026-10-10 sui servizi del CDS (MocServer, TAPVizieR,
#: colonne di SIMBAD); l'albero dinamico ordinato per popolarità attende D13-18.
FIXED_COLLECTIONS: tuple[FixedCollection, ...] = (
    FixedCollection("simbad", "SIMBAD (oggetti, tabella basic)", "cds-simbad-tap", "basic"),
    FixedCollection("I/355/gaiadr3", "Gaia DR3 Part 1. Main source (Gaia Collaboration, 2022)", "cds-vizier-tap",
                    "I/355/gaiadr3"),
    FixedCollection("II/246/out", "2MASS All-Sky Catalog of Point Sources (Cutri+ 2003)", "cds-vizier-tap",
                    "II/246/out"),
)
_CATALOG_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+/-]*$")


def _from_vo_result(result) -> CatalogTable:
    """``CatalogTable`` del risultato del 14 con la richiesta registrata, i descrittori e gli avvisi."""
    table = result.table
    return dataclasses.replace(table, request=result.request, descriptors=result.descriptors,
                               warnings=tuple(result.warnings) + table.warnings)


def load_table(source, *, table=None, format=None, limits: TableLimits | None = None, cache=None,
               refresh: bool = False, timeouts=None) -> CatalogTable:
    """Come ``read_table``; un URL (D3) passa da ``download_table`` del modulo 14 (prima la cache)."""
    from astrotwo.core import vo_protocols as vo

    text = os.fspath(source)
    kwargs = {} if timeouts is None else {"timeouts": timeouts}
    if not text.startswith(("http://", "https://")):
        # Un ASTRORES con i dati in un LINK esterno li scarica con il 14 (D13-17).
        fetch = vo._link_fetcher(cache=cache, refresh=refresh, **kwargs)
        result = _read_table(text, table=table, format=format, limits=limits, fetch_link=fetch)
        if result.format == "votable":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                payload = Path(result.origin).read_bytes()
                descriptors = vo._descriptors(parse_votable(result.origin, verify="ignore"), payload)
            result = dataclasses.replace(result, descriptors=descriptors)
        return result
    return _from_vo_result(vo.download_table(text, table=table, format=format, limits=limits, cache=cache,
                                             refresh=refresh, **kwargs))


def load_catalog(catalog_id: str, *, max_rows: int | None = None, limits: TableLimits | None = None, cache=None,
                 refresh: bool = False, timeouts=None) -> CatalogTable:
    """Catalogo per identificatore (D1): VizieR (es. ``"II/246/out"``) tramite TAP VizieR del 14, o una
    voce del gruppo fisso (``FIXED_COLLECTIONS``); righe oltre ``max_rows`` → ``ROW_LIMIT_EXCEEDED`` dichiarato."""
    from astrotwo.core import vo_protocols as vo

    if not isinstance(catalog_id, str) or not _CATALOG_ID.match(catalog_id):
        raise CatalogsError("CATALOG_UNKNOWN", f"identificativo di catalogo non valido: {catalog_id!r}")
    fixed = {c.id: c for c in FIXED_COLLECTIONS}
    server, name = (fixed[catalog_id].server, fixed[catalog_id].table) if catalog_id in fixed \
        else ("cds-vizier-tap", catalog_id)
    kwargs = {} if timeouts is None else {"timeouts": timeouts}
    try:
        result = vo.tap_query(server, f'SELECT * FROM "{name}"',
                              max_rows=vo.DEFAULT_MAX_ROWS if max_rows is None else max_rows,
                              limits=limits, cache=cache, refresh=refresh, **kwargs)
    except vo.VoProtocolsError as exc:
        if exc.code == "ADQL_INVALID":  # il servizio rifiuta la tabella: catalogo sconosciuto
            raise CatalogsError("CATALOG_UNKNOWN", f"catalogo {catalog_id!r} non trovato su {server}: "
                                f"{exc.details.get('service_message', exc.message)}") from exc
        raise
    return dataclasses.replace(_from_vo_result(result), history=(f"catalogo {catalog_id} da {server}",))


#: Dichiarazione dell'ordine dell'albero (D13-18): la proprietà non è descritta dalla documentazione del MocServer.
POPULARITY_NOTE = "ordine per vizier_popularity, proprietà non documentata del MocServer"
ALPHABETICAL_NOTE = "ordine alfabetico degli identificativi (vizier_popularity assente)"


@dataclass(frozen=True)
class CollectionNode:
    """Nodo dell'albero delle collezioni: un livello dell'identificativo VizieR (es. ``I``, ``I/355``,
    ``I/355/gaiadr3``); ``table`` vero se l'identificativo è una collezione del MocServer (per ``load_catalog``)."""

    id: str
    title: str | None
    popularity: int | None  # massimo del sottoalbero; None se la proprietà manca in tutto il sottoalbero
    table: bool
    children: tuple[CollectionNode, ...] = ()

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass(frozen=True)
class CollectionTree:
    """Albero dinamico delle collezioni VizieR (D13-3, D13-18) con l'ordine usato dichiarato."""

    roots: tuple[CollectionNode, ...]
    ordering: str
    source: str
    retrieved_at: datetime
    request: object  # RequestRecord del 14
    warnings: tuple[tuple[str, str], ...] = ()

    def find(self, node_id: str) -> CollectionNode | None:
        for root in self.roots:
            for node in root.walk():
                if node.id == node_id:
                    return node
        return None


def _popularity(value) -> int | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if math.isfinite(number) and number == int(number) else None


def collection_tree(*, cache=None, refresh: bool = False, timeouts=None) -> CollectionTree:
    """Albero delle collezioni VizieR dal MocServer del CDS (client nel 14), ordinato per ``vizier_popularity``
    (decrescente, a pari valore in ordine alfabetico) e dichiarato come proprietà non documentata; senza la
    proprietà, ordine alfabetico (D13-18). Il gruppo fisso è ``FIXED_COLLECTIONS``."""
    from astrotwo.core import vo_protocols as vo

    kwargs = {} if timeouts is None else {"timeouts": timeouts}
    fetched = vo.vizier_collections(cache=cache, refresh=refresh, **kwargs)
    notes = list(fetched.warnings)
    nodes: dict[str, dict] = {}
    skipped, invalid = [], 0
    for record in fetched.records:
        parts = record["ID"].split("/")
        if len(parts) < 3 or parts[0] != "CDS" or not all(parts[1:]):
            skipped.append(record["ID"])  # es. CDS/Simbad: non è una collezione VizieR
            continue
        popularity = _popularity(record.get("vizier_popularity"))
        if popularity is None and record.get("vizier_popularity") is not None:
            invalid += 1
        for depth in range(2, len(parts) + 1):
            node_id = "/".join(parts[1:depth])
            node = nodes.setdefault(node_id, {"title": None, "popularity": None, "table": False, "children": set()})
            if depth > 2:
                nodes["/".join(parts[1:depth - 1])]["children"].add(node_id)
            if popularity is not None:
                node["popularity"] = max(popularity, node["popularity"] or popularity)
        leaf = nodes["/".join(parts[1:])]
        leaf["table"] = True
        leaf["title"] = record.get("obs_title")
    any_popularity = any(n["popularity"] is not None for n in nodes.values())

    def key(node_id: str):
        pop = nodes[node_id]["popularity"]
        if not any_popularity:
            return (0, 0, node_id)
        return (pop is None, -(pop or 0), node_id)

    def build(node_id: str) -> CollectionNode:
        n = nodes[node_id]
        return CollectionNode(node_id, n["title"], n["popularity"], n["table"],
                              tuple(build(c) for c in sorted(n["children"], key=key)))

    roots = tuple(build(r) for r in sorted((i for i in nodes if "/" not in i), key=key))
    if skipped:
        notes.append(("COLLECTION_SKIPPED", f"record non VizieR esclusi dall'albero: {', '.join(skipped[:10])}"
                      + (" …" if len(skipped) > 10 else "")))
    if invalid:
        notes.append(("POPULARITY_INVALID", f"{invalid} record con vizier_popularity non intera: trattati come assenti"))
    missing = sum(1 for n in nodes.values() if n["table"] and n["popularity"] is None)
    if any_popularity and missing:
        notes.append(("POPULARITY_MISSING", f"{missing} collezioni senza vizier_popularity: dopo le altre, in "
                      "ordine alfabetico"))
    ordering = POPULARITY_NOTE if any_popularity else ALPHABETICAL_NOTE
    return CollectionTree(roots=roots, ordering=ordering, source=f"MocServer del CDS ({vo.MOCSERVER_URL})",
                          retrieved_at=fetched.request.retrieved_at, request=fetched.request, warnings=tuple(notes))


_DATALINK_MIME = "application/x-votable+xml;content=datalink"


@dataclass(frozen=True)
class DataLinkColumn:
    """Colonna DataLink riconosciuta (D14-9 punto 14): la risoluzione dei link è del modulo 14."""

    column: str
    source: str  # "descriptor" (descrittore di servizio DataLink) o "content_type"
    descriptor: object | None = None  # ServiceDescriptor del 14
    format_column: str | None = None
    rows: np.ndarray | None = None  # righe con content-type DataLink (solo per "content_type")


def _single(table: Table, ucd_word: str, name: str) -> str | None:
    by_ucd = [n for n in table.colnames if (table[n].meta.get("ucd") or "").split(";")[0].strip() == ucd_word]
    if len(by_ucd) == 1:
        return by_ucd[0]
    return name if not by_ucd and name in table.colnames else None


def datalink_column(table: CatalogTable) -> DataLinkColumn | None:
    """Colonna DataLink: quella citata da un descrittore di servizio DataLink del VOTable, oppure la colonna
    degli URL di accesso (UCD ``meta.ref.url``) le cui righe dichiarano, nella colonna del formato (UCD
    ``meta.code.mime``), il content-type DataLink; nessuna → ``None``."""
    for desc in table.descriptors:
        if getattr(desc, "is_datalink", False):
            columns = [p.ref_column for p in desc.params if p.ref_column in table.table.colnames]
            if len(columns) == 1:
                return DataLinkColumn(columns[0], "descriptor", descriptor=desc)
    data = table.table
    fmt, url = _single(data, "meta.code.mime", "access_format"), _single(data, "meta.ref.url", "access_url")
    if fmt is None or url is None:
        return None
    values = np.array([str(v).replace(" ", "").lower() for v in data[fmt]])
    mask = ~np.ma.getmaskarray(data[fmt]) & (values == _DATALINK_MIME)
    if not mask.any():
        return None
    return DataLinkColumn(url, "content_type", format_column=fmt, rows=mask)
