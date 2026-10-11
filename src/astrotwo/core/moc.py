"""Mappe di copertura MOC: spaziali, temporali e spazio-temporali.

Specifica: ``mdfiles/16-core-moc.md`` (stato ``approvato``).

Il modulo si scrive in 5 parti (decisione del proprietario del 2026-10-11):
P1 classe ``Moc``, lettura/scrittura FITS IVOA, JSON e testo, operazioni
insiemistiche; P2 creazione da cerchio, poligono, catalogo, immagine;
P3 ``filter_by_moc`` e mappe HEALPix; P4 MOC temporali e mappe di
probabilità; P5 ``query_mocserver`` e ``build_moc``.

Calcolo: ``mocpy`` (MOC) e ``astropy-healpix`` (mappe); ``healpy`` è escluso
(licenza GPL). I MOC spaziali sono sempre in ICRS (standard IVOA MOC 2.0),
i temporali in TCB (standard 2.0 §4.2).
"""

from __future__ import annotations

import io
import json
import math
import re
from dataclasses import dataclass, replace
from pathlib import Path

import astropy.units as u
import mocpy
import numpy as np
from astropy.io import fits
from mocpy import MOC, STMOC, TimeMOC

import astrotwo

__all__ = [
    "CircleRegion",
    "MOC_KINDS",
    "PolygonRegion",
    "SPACE_MAX_ORDER",
    "FilterResult",
    "HealpixGrid",
    "HealpixMap",
    "ProbabilityMap",
    "MocServerResult",
    "SUPPORTED_VERSIONS",
    "TIME_MAX_ORDER",
    "Moc",
    "MocError",
    "build_moc",
    "filter_by_moc",
    "healpix_grid",
    "healpix_map",
    "moc_from_catalog",
    "moc_from_probability",
    "moc_from_times",
    "moc_space_time",
    "query_mocserver",
    "read_probability_map",
    "moc_from_image",
    "moc_from_region",
    "read_moc",
    "write_moc",
]

#: Tipi di MOC (§3): spaziale, temporale, spazio-temporale.
MOC_KINDS: tuple[str, ...] = ("space", "time", "space-time")
#: Ordini massimi dello standard IVOA MOC 2.0 (spazio: 29, tempo: 61).
SPACE_MAX_ORDER = 29
TIME_MAX_ORDER = 61
#: Versioni pubblicate dello standard lette dal modulo (verifica del 2026-10-11; 2.1 ferma su D16-6).
SUPPORTED_VERSIONS: tuple[str, ...] = ("1.0", "1.1", "2.0")
#: Versione scritta (standard corrente, D16-2).
WRITTEN_VERSION = "2.0"
VERSION_NOT_DECLARED = "non dichiarata nel formato"
VERSION_ASSUMED_11 = "1.1, assunta dallo standard (MOCVERS assente; 1.0 ha le stesse intestazioni)"

_CLASSES = {"space": MOC, "time": TimeMOC, "space-time": STMOC}
_DIMS = {"SPACE": "space", "TIME": "time", "TIME.SPACE": "space-time"}
_SYSTEMS = {"space": "ICRS", "time": "TCB", "space-time": "TCB + ICRS"}
_PROVENANCE = f"mocpy {mocpy.__version__}"
_TOOL = f"AstroTwo {astrotwo.__version__}"


class MocError(Exception):
    """Errore del modulo 16 con identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


def _check_kind(kind: object) -> str:
    if kind not in MOC_KINDS:
        raise ValueError(f"kind {kind!r}: ammessi {', '.join(MOC_KINDS)}")
    return kind  # type: ignore[return-value]


def _check_order(order: object, limit: int, what: str) -> int:
    """Ordine obbligatorio, intero in [0, limite dello standard] (``HEALPIX_ORDER_INVALID``)."""
    if isinstance(order, bool) or not isinstance(order, (int, np.integer)) or not 0 <= int(order) <= limit:
        raise MocError("HEALPIX_ORDER_INVALID", f"{what} {order!r}: serve un intero in [0, {limit}] "
                       "(standard IVOA MOC 2.0), senza default")
    return int(order)


@dataclass(frozen=True)
class Moc:
    """MOC con tipo, sistema, ordini massimi, corpo, origine e versione letta (§7, §9).

    ``body`` è obbligatorio per i MOC spaziali e spazio-temporali (D19-3); per i MOC solo temporali è
    ``None`` = "non applicabile" (un TMOC non ha posizioni, scelta di P1)."""

    moc: object  # mocpy.MOC, mocpy.TimeMOC o mocpy.STMOC
    kind: str
    body: str | None
    origin: str
    version: str | None = None  # versione del formato letto; None per un MOC creato
    history: tuple[str, ...] = ()
    warnings: tuple[tuple[str, str], ...] = ()
    provenance: str = _PROVENANCE

    def __post_init__(self) -> None:
        _check_kind(self.kind)
        if not isinstance(self.moc, _CLASSES[self.kind]):
            raise TypeError(f"MOC {self.kind}: atteso {_CLASSES[self.kind].__name__}, "
                            f"ricevuto {type(self.moc).__name__}")
        if self.kind != "time" and not (isinstance(self.body, str) and self.body):
            raise MocError("BODY_UNKNOWN", f"MOC {self.kind} senza corpo (body): un MOC senza corpo è un errore")

    # -- descrizione -------------------------------------------------------
    @property
    def system(self) -> str:
        """Sistema di riferimento: ICRS (spazio), TCB (tempo), entrambi (spazio-tempo)."""
        return _SYSTEMS[self.kind]

    @property
    def space_order(self) -> int | None:
        if self.kind == "space":
            return int(self.moc.max_order)
        if self.kind == "space-time":
            return int(self.moc.max_depth[1])
        return None

    @property
    def time_order(self) -> int | None:
        if self.kind == "time":
            return int(self.moc.max_order)
        if self.kind == "space-time":
            return int(self.moc.max_depth[0])
        return None

    @property
    def is_empty(self) -> bool:
        return bool(self.moc.is_empty() if self.kind == "space-time" else self.moc.empty())

    @property
    def sky_fraction(self) -> float | None:
        """Frazione di cielo coperta (solo MOC spaziali; calcolo di ``mocpy``)."""
        return float(self.moc.sky_fraction) if self.kind == "space" else None

    @property
    def area(self) -> u.Quantity | None:
        """Superficie coperta in steradianti (solo MOC spaziali): frazione di cielo × 4π."""
        return None if self.kind != "space" else self.sky_fraction * 4 * math.pi * u.sr

    @property
    def duration(self) -> u.Quantity | None:
        """Durata coperta in secondi (solo MOC temporali, scala TCB)."""
        return None if self.kind != "time" else float(self.moc.total_duration.to_value(u.s)) * u.s

    @property
    def n_cells(self) -> int | None:
        """Numero di celle (NUNIQ) del MOC spaziale o temporale; ``None`` per gli spazio-temporali."""
        if self.kind == "space":
            return int(len(self.moc.uniq_hpx))
        if self.kind == "time":
            return int(len(self.moc.uniq_gen))
        return None

    def describe(self) -> str:
        """Tipo, sistema, ordini, corpo, area o durata, celle, origine e versione (``describe_moc``, §11)."""
        parts = [f"MOC {self.kind}", f"sistema {self.system}"]
        if self.space_order is not None:
            parts.append(f"ordine spaziale massimo {self.space_order}")
        if self.time_order is not None:
            parts.append(f"ordine temporale massimo {self.time_order}")
        parts.append(f"corpo {self.body}" if self.body is not None else "corpo non applicabile (MOC temporale)")
        if self.kind == "space":
            parts.append(f"area {self.area.value!r} sr (frazione di cielo {self.sky_fraction!r})")
        if self.kind == "time":
            parts.append(f"durata {self.duration.value!r} s (TCB)")
        if self.n_cells is not None:
            parts.append(f"{self.n_cells} celle")
        if self.is_empty:
            parts.append("vuoto")
        parts.append(f"origine {self.origin}")
        if self.version is not None:
            parts.append(f"versione letta {self.version}")
        return "; ".join(parts) + f" (calcolo: {self.provenance})"

    # -- operazioni insiemistiche (§3, §9) ---------------------------------
    def _check_other(self, other: Moc, force_body: bool) -> list[tuple[str, str]]:
        if not isinstance(other, Moc):
            raise TypeError("operazione tra MOC: serve un Moc")
        if other.kind != self.kind:
            raise MocError("MOC_TYPE_MISMATCH", f"operazione tra un MOC {self.kind} e un MOC {other.kind}: tipi "
                           "diversi (unità diverse)")
        if self.kind == "time" or self.body == other.body:
            return []
        if not force_body:
            raise MocError("BODY_MISMATCH", f"corpi diversi: {self.body!r} e {other.body!r}; forzabile solo con "
                           "force_body=True (citato nel risultato)")
        return [("BODY_FORCED", f"operazione tra corpi diversi forzata: {self.body!r} e {other.body!r}; il "
                 f"risultato porta il corpo del primo operando ({self.body!r})")]

    def _derived(self, result, op: str, notes: list[tuple[str, str]], others: tuple[Moc, ...] = ()) -> Moc:
        origin = f"{op}(" + ", ".join(m.origin for m in (self, *others)) + ")"
        history = tuple(dict.fromkeys(self.history + sum((m.history for m in others), ())))
        moc = Moc(moc=result, kind=self.kind, body=self.body, origin=origin, history=history, warnings=())
        orders = []
        if moc.space_order is not None:
            orders.append(f"ordine spaziale {moc.space_order}")
        if moc.time_order is not None:
            orders.append(f"ordine temporale {moc.time_order}")
        step = f"{op} con mocpy ({', '.join(orders)}" + (": il massimo degli operandi)" if others else ")")
        if moc.is_empty:
            notes = notes + [("MOC_EMPTY", f"risultato di {op} vuoto")]
        return replace(moc, history=history + (step,), warnings=tuple(notes))

    def union(self, other: Moc, *, force_body: bool = False) -> Moc:
        notes = self._check_other(other, force_body)
        return self._derived(self.moc.union(other.moc), "unione", notes, (other,))

    def intersection(self, other: Moc, *, force_body: bool = False) -> Moc:
        notes = self._check_other(other, force_body)
        return self._derived(self.moc.intersection(other.moc), "intersezione", notes, (other,))

    def difference(self, other: Moc, *, force_body: bool = False) -> Moc:
        """Celle di questo MOC non coperte da ``other``."""
        notes = self._check_other(other, force_body)
        return self._derived(self.moc.difference(other.moc), "differenza", notes, (other,))

    def complement(self) -> Moc:
        if self.kind == "space-time":  # mocpy 0.20.0: "Complement not implemented (yet) for ST-MOCs" (D16-7)
            raise MocError("MOC_OPERATION_UNSUPPORTED", "complemento di un MOC spazio-temporale non disponibile in "
                           f"{_PROVENANCE} (D16-7)")
        return self._derived(self.moc.complement(), "complemento", [])

    def contains(self, coords) -> np.ndarray:
        """Maschera booleana delle posizioni (``SkyFrame``, sistema dichiarato) che cadono nel MOC spaziale;
        le posizioni si convertono in ICRS con il modulo 10."""
        if self.kind != "space":
            raise MocError("MOC_TYPE_MISMATCH", f"contains su posizioni: serve un MOC spaziale, non {self.kind}")
        lon, lat, _ = _to_icrs(coords, "posizioni")
        return np.asarray(self.moc.contains_lonlat(lon=lon * u.deg, lat=lat * u.deg), dtype=bool)

    @property
    def time_range(self):
        """Primo e ultimo istante coperti (``astropy.time.Time`` in TCB) di un MOC temporale o spazio-temporale."""
        if self.kind == "space" or self.is_empty:
            return None
        return self.moc.min_time.tcb, self.moc.max_time.tcb

    def contains_times(self, times) -> np.ndarray:
        """Maschera degli istanti (``astropy.time.Time``, scala dichiarata) coperti dal MOC temporale; gli
        istanti si convertono in TCB con ``astropy.time``."""
        if self.kind != "time":
            raise MocError("MOC_TYPE_MISMATCH", f"contains_times: serve un MOC temporale, non {self.kind}")
        return np.asarray(self.moc.contains(_tcb(times, "istanti")), dtype=bool)

    def space_during(self, during: Moc) -> Moc:
        """Copertura spaziale di un MOC spazio-temporale negli intervalli del MOC temporale ``during``."""
        if self.kind != "space-time" or not isinstance(during, Moc) or during.kind != "time":
            raise MocError("MOC_TYPE_MISMATCH", "space_during: MOC spazio-temporale e MOC temporale")
        result = Moc(moc=self.moc.query_by_time(during.moc), kind="space", body=self.body,
                     origin=f"spazio di {self.origin} durante {during.origin}", history=self.history)
        return replace(result, history=result.history + ("proiezione sullo spazio con mocpy.STMOC.query_by_time",))

    def time_within(self, within: Moc, *, force_body: bool = False) -> Moc:
        """Copertura temporale di un MOC spazio-temporale nelle zone del MOC spaziale ``within``."""
        if self.kind != "space-time" or not isinstance(within, Moc) or within.kind != "space":
            raise MocError("MOC_TYPE_MISMATCH", "time_within: MOC spazio-temporale e MOC spaziale")
        notes = []
        if within.body != self.body:
            if not force_body:
                raise MocError("BODY_MISMATCH", f"corpi diversi: {self.body!r} e {within.body!r}; forzabile solo con "
                               "force_body=True")
            notes.append(("BODY_FORCED", f"corpi diversi forzati: {self.body!r} e {within.body!r}"))
        result = Moc(moc=self.moc.query_by_space(within.moc), kind="time", body=None,
                     origin=f"tempo di {self.origin} in {within.origin}", history=self.history)
        return replace(result, history=result.history + ("proiezione sul tempo con mocpy.STMOC.query_by_space",),
                       warnings=tuple(notes))

    def __eq__(self, other: object) -> bool:  # stesse celle, stesso tipo e stesso corpo
        if not isinstance(other, Moc):
            return NotImplemented
        return self.kind == other.kind and self.body == other.body and self.moc == other.moc

    __hash__ = None  # type: ignore[assignment]


# --------------------------------------------------------------------------
# P1 — Lettura e scrittura (H22, D16-2)
# --------------------------------------------------------------------------

def _detect_format(head: bytes) -> str:
    if head.startswith(b"SIMPLE"):
        return "fits"
    text = head.lstrip()
    return "json" if text[:1] in (b"{", b"[") else "ascii"


def _unreadable(path: Path, reason: object) -> MocError:
    return MocError("MOC_UNREADABLE", f"{path}: MOC non leggibile ({reason})", path=str(path))


def _read_fits(path: Path, kind: str | None) -> tuple[object, str, str, list[tuple[str, str]]]:
    try:
        with fits.open(path, memmap=False) as hdul:
            tables = [h for h in hdul if isinstance(h, fits.BinTableHDU)]
            if not tables:
                raise _unreadable(path, "nessuna tabella binaria")
            header = tables[0].header
    except MocError:
        raise
    except (OSError, ValueError) as exc:
        raise _unreadable(path, exc) from exc
    raw_version = header.get("MOCVERS")
    if raw_version is None:
        version = VERSION_ASSUMED_11
    else:
        version = str(raw_version).strip()
        if version not in SUPPORTED_VERSIONS:
            extra = " (D16-6: una versione 2.1 dello standard non esiste tra i documenti IVOA)" \
                if version == "2.1" else ""
            raise MocError("MOC_VERSION_UNSUPPORTED", f"{path}: versione MOC {version!r} non supportata; "
                           f"lette: {', '.join(SUPPORTED_VERSIONS)}{extra}", version=version)
    dim = str(header.get("MOCDIM", "SPACE")).strip()  # senza MOCDIM: SPACE (standard 2.0)
    if dim not in _DIMS:
        raise _unreadable(path, f"MOCDIM {dim!r} non previsto dallo standard")
    found = _DIMS[dim]
    if kind is not None and kind != found:
        raise MocError("MOC_TYPE_MISMATCH", f"{path}: MOC {found} nel file, richiesto {kind}")
    notes = []
    if found != "time" and str(header.get("COORDSYS", "")).strip() != "C":
        raise _unreadable(path, f"COORDSYS {header.get('COORDSYS')!r}: lo standard prevede 'C' (ICRS)")
    if found != "space" and str(header.get("TIMESYS", "")).strip() != "TCB":
        raise MocError("MOC_VERSION_UNSUPPORTED", f"{path}: TIMESYS {header.get('TIMESYS')!r}; lo standard 2.0 "
                       "prevede TCB (i MOC temporali precedenti, Note STMOC 2019, non sono letti)",
                       version=str(raw_version))
    try:
        if version == "1.0":
            # mocpy 0.20.0 accetta MOCVERS 1.1, 2.0 e 2.1, non "1.0": lo standard 1.0 non ha MOCVERS e le sue
            # intestazioni sono quelle di 1.1, quindi si passa a mocpy una copia in memoria senza la parola chiave.
            with fits.open(path, memmap=False) as hdul:
                for hdu in hdul:
                    hdu.header.remove("MOCVERS", ignore_missing=True)
                buffer = io.BytesIO()
                hdul.writeto(buffer)
            buffer.seek(0)
            moc = _CLASSES[found].from_fits(buffer)
        else:
            moc = _CLASSES[found].load(path, format="fits")
    except Exception as exc:  # mocpy: OSError/ValueError dal lettore in Rust
        raise _unreadable(path, exc) from exc
    if raw_version is None:
        notes.append(("MOC_VERSION_ASSUMED", f"{path}: MOCVERS assente, versione {VERSION_ASSUMED_11}"))
    return moc, found, version, notes


def _json_cells(value: object, path: Path) -> dict:
    if not isinstance(value, dict) or not all(
            isinstance(k, str) and k.isdigit() and isinstance(v, list) and all(
                isinstance(i, int) and not isinstance(i, bool) and i >= 0 for i in v) for k, v in value.items()):
        raise _unreadable(path, "JSON: atteso {\"ordine\": [indici interi], ...}")
    return value


def _read_json(path: Path, text: str, kind: str | None) -> tuple[object, str]:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise _unreadable(path, exc) from exc
    if isinstance(data, list):  # STMOC: lista di coppie {"t": …}, {"s": …} (standard 2.0, appendice F)
        found = "space-time"
        if not all(isinstance(d, dict) and len(d) == 1 and next(iter(d)) in ("t", "s") for d in data):
            raise _unreadable(path, "JSON di un MOC spazio-temporale: attesa una lista di {\"t\": …} e {\"s\": …}")
        for d in data:
            _json_cells(next(iter(d.values())), path)
        payload: object = data
    elif isinstance(data, dict) and len(data) == 1 and next(iter(data)) in ("s", "t"):
        found = "space" if "s" in data else "time"
        payload = _json_cells(data["s" if found == "space" else "t"], path)
    else:
        if kind is None:
            raise MocError("MOC_TYPE_REQUIRED", f"{path}: JSON senza prefisso \"s\"/\"t\": il tipo si determina dal "
                           "contesto d'uso (standard 2.0); indicarlo con kind='space' o kind='time'")
        found = kind
        payload = _json_cells(data, path)
    if kind is not None and kind != found:
        raise MocError("MOC_TYPE_MISMATCH", f"{path}: MOC {found} nel file, richiesto {kind}")
    if found == "space-time" and not isinstance(payload, list):
        raise _unreadable(path, "un MOC spazio-temporale in JSON è una lista di coppie t/s")
    try:
        return _CLASSES[found].from_json(payload), found
    except Exception as exc:
        raise _unreadable(path, exc) from exc


def _read_ascii(path: Path, text: str, kind: str | None) -> tuple[object, str]:
    tokens = text.split()
    if not tokens:
        raise _unreadable(path, "testo vuoto")
    has_t = any(t.startswith("t") for t in tokens)
    has_s = any(t.startswith("s") for t in tokens)
    if has_t and has_s:
        found, value = "space-time", text
    elif has_t or has_s:  # prefisso su un MOC a una dimensione: mocpy non lo legge, si toglie
        found = "time" if has_t else "space"
        value = " ".join(t[1:] if t[:1] in ("t", "s") else t for t in tokens)
    else:
        if kind is None:
            raise MocError("MOC_TYPE_REQUIRED", f"{path}: testo senza prefisso t/s: il tipo si determina dal "
                           "contesto d'uso (standard 2.0); indicarlo con kind='space' o kind='time'")
        found, value = kind, text
    if kind is not None and kind != found:
        raise MocError("MOC_TYPE_MISMATCH", f"{path}: MOC {found} nel file, richiesto {kind}")
    try:
        return _CLASSES[found].from_string(value, format="ascii"), found
    except Exception as exc:
        raise _unreadable(path, exc) from exc


def read_moc(source, *, format: str | None = None, kind: str | None = None, cache=None, refresh: bool = False,
             timeouts=None) -> Moc:
    """Legge un MOC FITS IVOA, JSON o testo (H22), da file o da URL, e ne dichiara la versione.

    FITS: versione da ``MOCVERS`` (1.0, 1.1, 2.0; assente → 1.1 assunta dallo standard), tipo da ``MOCDIM``.
    JSON e testo non portano la versione; senza prefisso ``s``/``t`` il tipo si indica con ``kind``.
    I MOC spaziali sono in ICRS per lo standard: corpo ``celestial``. Da URL: prima la cache comune (04), dove
    il MOC si conserva in FITS IVOA (D16-2), con origine e data."""
    if kind is not None:
        _check_kind(kind)
    if isinstance(source, str) and source.split("://", 1)[0].lower() in ("http", "https"):
        return _read_url(source, format, kind, cache, refresh, timeouts)
    return _read_path(Path(source), format, kind)


def _read_path(path: Path, format: str | None, kind: str | None) -> Moc:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise _unreadable(path, exc) from exc
    fmt = format if format is not None else _detect_format(raw[:80])
    if fmt not in ("fits", "json", "ascii"):
        raise ValueError(f"format {format!r}: ammessi fits, json, ascii")
    notes: list[tuple[str, str]] = []
    if fmt == "fits":
        moc, found, version, notes = _read_fits(path, kind)
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise _unreadable(path, exc) from exc
        moc, found = _read_json(path, text, kind) if fmt == "json" else _read_ascii(path, text, kind)
        version = VERSION_NOT_DECLARED
    body = None if found == "time" else "celestial"  # ICRS per lo standard (COORDSYS='C'), D19-3
    step = f"letto da {path} ({fmt}, versione {version})"
    result = Moc(moc=moc, kind=found, body=body, origin=str(path), version=version, history=(step,))
    if result.is_empty:
        notes.append(("MOC_EMPTY", f"{path}: MOC vuoto"))
    return replace(result, warnings=tuple(notes))


def _json_payload(moc: Moc) -> object:
    data = moc.moc.serialize("json")
    if moc.kind == "space-time":
        return data
    return {"s" if moc.kind == "space" else "t": data}


def write_moc(moc: Moc, path, format: str = "fits", overwrite: bool = False) -> Path:
    """Scrive un MOC in FITS IVOA 2.0 (spaziali in ``NUNIQ`` con ``MOCORDER``, altri in ``RANGE``), JSON (con
    prefisso ``s``/``t``) o testo (D16-2). Solo MOC celesti: lo standard è solo ICRS."""
    if not isinstance(moc, Moc):
        raise TypeError("write_moc: serve un Moc")
    if format not in ("fits", "json", "ascii"):
        raise ValueError(f"format {format!r}: ammessi fits, json, ascii")
    if moc.kind != "time" and moc.body != "celestial":
        raise MocError("MOC_BODY_UNSUPPORTED", f"MOC del corpo {moc.body!r}: il formato IVOA MOC è solo per il cielo "
                       "(ICRS)")
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target} esiste già (overwrite=True per sostituirlo)")
    if format == "fits":
        moc.moc.save(target, format="fits", overwrite=True, pre_v2=moc.kind == "space",
                     fits_keywords={"MOCTOOL": _TOOL})
    elif format == "json":
        target.write_text(json.dumps(_json_payload(moc)), encoding="utf-8")
    else:
        target.write_text(moc.moc.to_string("ascii"), encoding="utf-8")
    return target


# --------------------------------------------------------------------------
# P2 — Creazione da cerchio, poligono, catalogo, immagine (E6)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class CircleRegion:
    """Cerchio sulla sfera: centro (una posizione ``SkyFrame``, sistema dichiarato) e raggio angolare."""

    center: object
    radius: u.Quantity


@dataclass(frozen=True)
class PolygonRegion:
    """Poligono con lati su cerchi massimi: vertici ``SkyFrame`` (almeno 3, sistema dichiarato)."""

    vertices: object


def _to_icrs(coords, what: str):
    """Coordinate ``SkyFrame`` del modulo 10 convertite in ICRS (i MOC spaziali sono sempre ICRS)."""
    from astropy.coordinates import SkyCoord

    from astrotwo.core.coordinates_wcs import CoordinatesWcsError, SkyFrame

    if isinstance(coords, SkyCoord):
        coords = SkyFrame(coords)
    if not isinstance(coords, SkyFrame):
        raise TypeError(f"{what}: servono coordinate SkyFrame/SkyCoord con il sistema dichiarato (modulo 10)")
    try:
        icrs = coords if coords.frame_name == "icrs" else coords.to("icrs")
    except CoordinatesWcsError as exc:
        raise MocError("REGION_INVALID", f"{what}: {exc.message}") from exc
    lon = np.atleast_1d(icrs.lon.to_value(u.deg))
    lat = np.atleast_1d(icrs.lat.to_value(u.deg))
    if not (np.all(np.isfinite(lon)) and np.all(np.isfinite(lat))):
        raise MocError("REGION_INVALID", f"{what}: coordinate non finite")
    note = "" if coords.frame_name == "icrs" else f" (convertite da {coords.frame_name} in ICRS con il modulo 10)"
    return lon, lat, note


def _created(moc, origin: str, step: str, notes=(), body: str = "celestial") -> Moc:
    result = Moc(moc=moc, kind="space", body=body, origin=origin, history=(step,))
    notes = list(notes)
    if result.is_empty:
        notes.append(("MOC_EMPTY", f"{origin}: MOC vuoto"))
    return replace(result, warnings=tuple(notes))


def _cell_size(order: int) -> u.Quantity:
    return MOC.order_to_spatial_resolution(order).to(u.deg)


def moc_from_region(region, order_max: int, *, complement: bool = False) -> Moc:
    """MOC da un cerchio o da un poligono con lati su cerchi massimi (E6), all'ordine ``order_max`` (obbligatorio).

    Cerchio: ``mocpy.MOC.from_cone`` (celle che toccano il cerchio, calcolo a ``order_max`` + 2).
    Poligono: ``mocpy.MOC.from_polygon``; interno = la più piccola delle due regioni, la complementare con
    ``complement=True`` (verificato in mocpy il 2026-10-11)."""
    order = _check_order(order_max, SPACE_MAX_ORDER, "order_max")
    resolution = f"ordine {order} (lato delle celle {_cell_size(order).value!r}°)"
    if isinstance(region, CircleRegion):
        lon, lat, note = _to_icrs(region.center, "centro del cerchio")
        if lon.size != 1:
            raise MocError("REGION_INVALID", "il centro del cerchio è una sola posizione")
        radius = region.radius
        if not isinstance(radius, u.Quantity) or not radius.isscalar or not radius.unit.is_equivalent(u.deg):
            raise MocError("REGION_INVALID", f"raggio {radius!r}: serve un angolo con unità")
        r = float(radius.to_value(u.deg))
        if not (math.isfinite(r) and 0.0 < r <= 180.0):
            raise MocError("REGION_INVALID", f"raggio {r!r}°: ammesso in (0°, 180°]")
        if complement:
            raise ValueError("complement vale solo per i poligoni")
        moc = MOC.from_cone(lon=lon[0] * u.deg, lat=lat[0] * u.deg, radius=r * u.deg, max_depth=order,
                            delta_depth=2)
        origin = f"cerchio di centro ICRS ({lon[0]!r}°, {lat[0]!r}°) e raggio {r!r}°{note}"
        step = (f"MOC da cerchio con mocpy.MOC.from_cone, {resolution}: celle che toccano il cerchio, "
                "calcolo all'ordine + 2")
        return _created(moc, origin, step)
    if isinstance(region, PolygonRegion):
        lon, lat, note = _to_icrs(region.vertices, "vertici del poligono")
        if lon.size < 3:
            raise MocError("REGION_INVALID", f"poligono con {lon.size} vertici: ne servono almeno 3")
        try:
            moc = MOC.from_polygon(lon=lon * u.deg, lat=lat * u.deg, complement=bool(complement), max_depth=order)
        except Exception as exc:  # mocpy rifiuta i poligoni non validi (es. lati che si incrociano)
            raise MocError("REGION_INVALID", f"poligono non valido per mocpy: {exc}") from exc
        side = "regione complementare (complement=True)" if complement else "regione più piccola delle due"
        origin = f"poligono di {lon.size} vertici ICRS{note}"
        step = (f"MOC da poligono con mocpy.MOC.from_polygon, {resolution}: lati su cerchi massimi, interno = "
                f"{side}")
        return _created(moc, origin, step)
    raise TypeError("region: CircleRegion o PolygonRegion")


def _catalog_positions(table, what: str):
    """(lon ICRS, lat ICRS, righe escluse, nota) dalle colonne di posizione del 13, convertite con il 10."""
    from astrotwo.core.coordinates_wcs import CoordinatesWcsError, SkyFrame

    pos = table.positions
    if pos is None:
        raise MocError("NO_COORD_COLUMNS", f"{what} ({table.origin}): nessuna colonna di posizione (modulo 13)")
    if pos.frame is None:
        raise MocError("FRAME_UNKNOWN", f"{what}: colonne {pos.lon}/{pos.lat} senza sistema dichiarato")
    lon_col, lat_col = table.table[pos.lon], table.table[pos.lat]
    if lon_col.unit is None or lat_col.unit is None or not (
            lon_col.unit.is_equivalent(u.deg) and lat_col.unit.is_equivalent(u.deg)):
        raise MocError("NO_COORD_COLUMNS", f"{what}: colonne {pos.lon}/{pos.lat} senza unità angolare")
    lon_v = np.ma.filled(np.ma.asarray(lon_col, dtype=float), np.nan)
    lat_v = np.ma.filled(np.ma.asarray(lat_col, dtype=float), np.nan)
    valid = np.isfinite(lon_v) & np.isfinite(lat_v)
    if not np.any(valid):
        return np.zeros(0), np.zeros(0), valid, ""
    try:
        coords = SkyFrame.from_lonlat((lon_v[valid] * lon_col.unit).to(u.deg) % (360 * u.deg),
                                      (lat_v[valid] * lat_col.unit).to(u.deg), pos.frame, equinox=pos.equinox,
                                      obstime=pos.epoch if pos.frame == "fk4" else None)
        lon, lat, note = _to_icrs(coords, what)
    except CoordinatesWcsError as exc:
        raise MocError(exc.code, f"{what}: {exc.message}") from exc
    return lon, lat, valid, note


def _check_celestial(body: str | None, what: str) -> str:
    if body is None:
        raise MocError("BODY_UNKNOWN", f"{what}: corpo non ricavabile, nessun MOC")
    if body != "celestial":
        raise MocError("MOC_BODY_UNSUPPORTED", f"{what}: corpo {body!r}; i MOC spaziali sono in ICRS (solo cielo)")
    return body


def moc_from_catalog(table, order_max: int) -> Moc:
    """MOC da un catalogo (E6): una cella per sorgente all'ordine ``order_max`` (obbligatorio), senza raggio.

    Posizioni dalle colonne del 13 convertite in ICRS con il 10; righe senza posizione escluse e contate;
    l'epoca delle posizioni è riportata, mai propagata."""
    order = _check_order(order_max, SPACE_MAX_ORDER, "order_max")
    _check_celestial(table.body, f"catalogo {table.origin}")
    lon, lat, valid, note = _catalog_positions(table, f"catalogo {table.origin}")
    moc = MOC.from_lonlat(lon=lon * u.deg, lat=lat * u.deg, max_norder=order) if lon.size else MOC.new_empty(order)
    notes = []
    excluded = int(np.count_nonzero(~valid))
    if excluded:
        notes.append(("ROWS_EXCLUDED", f"{excluded} righe senza posizione escluse"))
    epoch = table.positions.epoch
    step = (f"MOC da catalogo con mocpy.MOC.from_lonlat, ordine {order}: una cella per sorgente, senza raggio; "
            f"{lon.size} sorgenti{note}; epoca delle posizioni {epoch if epoch else 'non dichiarata'}")
    return _created(moc, f"catalogo {table.origin}", step, notes)


def _valid_pixels(image) -> np.ndarray:
    """Pixel validi: valori finiti, non mascherati e diversi da ``BLANK`` per i dati interi."""
    data = image.data
    valid = ~np.ma.getmaskarray(data)
    values = np.ma.getdata(data)
    if values.dtype.kind == "f":
        valid &= np.isfinite(values)
    elif values.dtype.kind in "iu" and image.header.get("BLANK") is not None:
        valid &= values != image.header["BLANK"]
    return valid


def _sample_axis(n: int, k: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Punti di campionamento su un asse di ``n`` pixel con ``k`` passi per pixel (bordi compresi), convenzione
    numpy (centri interi, bordi a ±0.5): (coordinate, pixel prima, pixel dopo) con indici spostati di 1 per il
    bordo di guardia."""
    a = np.arange(k * n + 1)
    coord = a / k - 0.5
    after = a // k  # pixel che contiene il punto (o che inizia sul punto)
    before = np.where(a % k == 0, after - 1, after)  # sul bordo tra due pixel il punto appartiene a entrambi
    return coord, before + 1, np.minimum(after, n) + 1


def moc_from_image(image, order_max: int, *, block_rows: int = 512) -> Moc:
    """MOC da un'immagine (E6): dai **pixel validi** con il WCS dell'11 (non solo i quattro angoli).

    Per ogni pixel valido si campionano angoli e punti interni a passo non più grande di metà del lato di una
    cella all'ordine ``order_max`` (obbligatorio); i punti si convertono in ICRS con il WCS (modulo 10) e il MOC
    contiene ogni cella che contiene un punto. Lo scarto dal contorno vero è limitato alle celle di bordo."""
    from astropy.wcs.utils import proj_plane_pixel_scales

    from astrotwo.core.coordinates_wcs import pixel_to_sky

    order = _check_order(order_max, SPACE_MAX_ORDER, "order_max")
    if getattr(image, "is_preview", False):
        raise MocError("PREVIEW_NOT_MEASURABLE", "MOC da immagine: l'immagine è aperta a due livelli e i dati in "
                       "memoria sono solo l'anteprima")
    if getattr(image, "color", False):
        raise MocError("OPERATION_UNSUPPORTED", "MOC da immagine: immagine a colori, solo presentazione")
    if image.wcs is None:
        raise MocError("WCS_MISSING", f"immagine {image.origin}: nessun WCS, nessuna posizione sul cielo")
    valid = _valid_pixels(image)
    ny, nx = valid.shape
    pixel = float(np.max(proj_plane_pixel_scales(image.wcs.wcs.celestial)))  # gradi per pixel
    cell = float(_cell_size(order).value)
    k = max(1, math.ceil(2.0 * pixel / cell))
    xs, x_before, x_after = _sample_axis(nx, k)
    ys, y_before, y_after = _sample_axis(ny, k)
    padded = np.zeros((ny + 2, nx + 2), dtype=bool)
    padded[1:-1, 1:-1] = valid
    result = MOC.new_empty(order)
    points = outside = 0
    step_rows = max(1, block_rows * k)
    for start in range(0, ys.size, step_rows):
        sl = slice(start, start + step_rows)
        yb, ya = y_before[sl][:, None], y_after[sl][:, None]
        keep = (padded[yb, x_before] | padded[yb, x_after] | padded[ya, x_before] | padded[ya, x_after])
        rows, cols = np.nonzero(keep)
        if rows.size == 0:
            continue
        sky = pixel_to_sky(image.wcs, xs[cols], ys[sl][rows], convention="numpy").coords
        lon, lat, _ = _to_icrs_finite(sky)
        outside += rows.size - lon.size
        points += lon.size
        if lon.size:
            result = result.union(MOC.from_lonlat(lon=lon * u.deg, lat=lat * u.deg, max_norder=order))
    notes = []
    if outside:
        notes.append(("POINTS_OUTSIDE_PROJECTION", f"{outside} punti di campionamento senza posizione sul cielo "
                      "(fuori dalla proiezione) esclusi"))
    invalid = int(valid.size - np.count_nonzero(valid))
    step = (f"MOC da immagine all'ordine {order}: {int(np.count_nonzero(valid))} pixel validi ({invalid} non validi: "
            f"NaN, mascherati o BLANK), {k} passi per pixel (pixel {pixel!r}°, cella {cell!r}°), {points} punti "
            f"convertiti con il WCS dell'11 ({image.wcs.projection}, {image.wcs.frame_name}) e il modulo 10; "
            "celle che contengono almeno un punto (mocpy.MOC.from_lonlat)")
    return _created(result, f"immagine {image.origin}", step, notes)


def _to_icrs_finite(coords):
    """Come ``_to_icrs`` ma scarta i punti senza posizione (fuori dalla proiezione) invece di rifiutarli."""
    lon_all = np.atleast_1d(coords.lon.to_value(u.deg))
    lat_all = np.atleast_1d(coords.lat.to_value(u.deg))
    finite = np.isfinite(lon_all) & np.isfinite(lat_all)
    if coords.frame_name == "icrs" or not np.any(finite):
        return lon_all[finite], lat_all[finite], ""
    from astrotwo.core.coordinates_wcs import SkyFrame

    kept = SkyFrame(coord=coords.coord[finite], epoch=coords.epoch, frame_defaults_note=coords.frame_defaults_note)
    return _to_icrs(kept, "punti dell'immagine")


# --------------------------------------------------------------------------
# P3 — Filtro per MOC, mappe e griglie HEALPix (E6, H12)
# --------------------------------------------------------------------------

#: Schema e sistema delle mappe e griglie HEALPix (decisione del proprietario del 2026-10-11).
HEALPIX_SCHEME = "NESTED"
HEALPIX_FRAME = "ICRS"
#: Celle massime di una griglia senza MOC che la limiti (tutto il cielo fino all'ordine 7).
GRID_MAX_CELLS = 12 * 4 ** 7


def _healpix(order: int):
    from astropy.coordinates import ICRS
    from astropy_healpix import HEALPix

    return HEALPix(nside=2 ** order, order="nested", frame=ICRS())


def _healpix_provenance() -> str:
    import astropy_healpix

    return f"astropy-healpix {astropy_healpix.__version__}"


def _check_bodies(table, moc: Moc, force_body: bool) -> list[tuple[str, str]]:
    if table.body is None:
        raise MocError("BODY_UNKNOWN", f"tabella {table.origin}: corpo non ricavabile, nessun filtro")
    if table.body == moc.body:
        return []
    if not force_body:
        raise MocError("BODY_MISMATCH", f"corpi diversi: tabella {table.body!r}, MOC {moc.body!r}; forzabile solo "
                       "con force_body=True (citato nel risultato)")
    return [("BODY_FORCED", f"filtro tra corpi diversi forzato: tabella {table.body!r}, MOC {moc.body!r}")]


@dataclass(frozen=True)
class FilterResult:
    """Selezione per MOC (E6): solo indici, la tabella non cambia (§9)."""

    mask: np.ndarray  # booleana, una voce per riga della tabella
    inside: bool
    excluded: int  # righe senza posizione: né dentro né fuori, mai selezionate
    moc_origin: str
    table_origin: str
    description: str
    warnings: tuple[tuple[str, str], ...] = ()

    @property
    def indices(self) -> np.ndarray:
        return np.flatnonzero(self.mask)

    @property
    def count(self) -> int:
        return int(np.count_nonzero(self.mask))


def filter_by_moc(table, moc: Moc, inside: bool = True, *, force_body: bool = False) -> FilterResult:
    """Righe della tabella (``CatalogTable`` del 13) dentro (``inside=True``) o fuori dal MOC spaziale (E6).

    Posizioni convertite in ICRS con il 10; righe senza posizione mai selezionate e contate. Restituisce indici,
    la tabella non cambia. Calcolo: ``mocpy.MOC.contains_lonlat``."""
    if not isinstance(moc, Moc):
        raise TypeError("filter_by_moc: serve un Moc")
    if moc.kind != "space":
        raise MocError("MOC_TYPE_MISMATCH", f"filtro di posizioni con un MOC {moc.kind}: serve un MOC spaziale")
    notes = _check_bodies(table, moc, force_body)
    lon, lat, valid, note = _catalog_positions(table, f"tabella {table.origin}")
    mask = np.zeros(len(valid), dtype=bool)
    if lon.size:
        mask[valid] = np.asarray(moc.moc.contains_lonlat(lon=lon * u.deg, lat=lat * u.deg, keep_inside=bool(inside)),
                                 dtype=bool)
    excluded = int(np.count_nonzero(~valid))
    if excluded:
        notes.append(("ROWS_EXCLUDED", f"{excluded} righe senza posizione: mai selezionate"))
    epoch = table.positions.epoch
    description = (f"righe {'dentro' if inside else 'fuori da'}l MOC {moc.origin}: {int(np.count_nonzero(mask))} su "
                   f"{len(mask)}{note}; epoca delle posizioni {epoch if epoch else 'non dichiarata'}, non propagata "
                   f"(calcolo: {moc.provenance}, contains_lonlat)")
    return FilterResult(mask=mask, inside=bool(inside), excluded=excluded, moc_origin=moc.origin,
                        table_origin=table.origin, description=description, warnings=tuple(notes))


@dataclass(frozen=True)
class HealpixMap:
    """Mappa HEALPix: un valore per cella, schema NESTED in ICRS, ordine dichiarato (H12)."""

    values: np.ndarray  # lunghezza 12 × 4**order, indice = cella NESTED
    order: int
    quantity: str  # "count" o "sum:<colonna>"
    unit: object | None
    scheme: str
    frame: str
    origin: str
    description: str
    warnings: tuple[tuple[str, str], ...] = ()

    @property
    def nside(self) -> int:
        return 2 ** self.order


def healpix_map(table, order: int, *, column: str | None = None) -> HealpixMap:
    """Mappa HEALPix di una tabella (H12): conteggi per cella, o somma della colonna ``column`` (es. flussi).

    Schema NESTED in ICRS, ``order`` obbligatorio; posizioni convertite con il 10; righe senza posizione o con
    valore mancante escluse e contate. Calcolo: ``astropy-healpix`` (``lonlat_to_healpix``) e ``numpy``."""
    order = _check_order(order, SPACE_MAX_ORDER, "order")
    hp = _healpix(order)
    if hp.npix > 12 * 4 ** 12:
        raise MocError("HEALPIX_ORDER_INVALID", f"order {order}: mappa di {hp.npix} celle oltre il limite di questa "
                       "funzione (ordine 12)")
    _check_celestial(table.body, f"tabella {table.origin}")
    lon, lat, valid, note = _catalog_positions(table, f"tabella {table.origin}")
    weights, unit, quantity = None, None, "count"
    notes = []
    if column is not None:
        if column not in table.table.colnames:
            raise ValueError(f"colonna {column!r} inesistente")
        col = table.table[column]
        if col.dtype.kind not in "iuf":
            raise ValueError(f"colonna {column!r}: servono valori numerici")
        raw = np.ma.filled(np.ma.asarray(col, dtype=float), np.nan)[valid]
        good = np.isfinite(raw)
        if not np.all(good):
            notes.append(("VALUES_EXCLUDED", f"{int(np.count_nonzero(~good))} righe con {column} mancante escluse"))
        lon, lat, weights = lon[good], lat[good], raw[good]
        unit, quantity = col.unit, f"sum:{column}"
    excluded = int(np.count_nonzero(~valid))
    if excluded:
        notes.append(("ROWS_EXCLUDED", f"{excluded} righe senza posizione escluse"))
    cells = hp.lonlat_to_healpix(lon * u.deg, lat * u.deg) if lon.size else np.zeros(0, dtype=np.int64)
    values = np.bincount(cells, weights=weights, minlength=hp.npix)
    if weights is None:
        values = values.astype(np.int64)
    description = (f"mappa HEALPix {HEALPIX_SCHEME} in {HEALPIX_FRAME}, ordine {order} (nside {hp.nside}), "
                   f"{'conteggi' if column is None else 'somma di ' + column}"
                   f"{'' if unit is None else ' [' + str(unit) + ']'} per cella, {lon.size} righe{note} "
                   f"(calcolo: {_healpix_provenance()})")
    return HealpixMap(values=values, order=order, quantity=quantity, unit=unit, scheme=HEALPIX_SCHEME,
                      frame=HEALPIX_FRAME, origin=f"tabella {table.origin}", description=description,
                      warnings=tuple(notes))


@dataclass(frozen=True)
class HealpixGrid:
    """Griglia HEALPix di riferimento: celle NESTED e loro contorni in ICRS (gradi), per il disegno (41)."""

    order: int
    cells: np.ndarray
    lon: np.ndarray  # (celle, 4 × step) gradi ICRS
    lat: np.ndarray
    scheme: str
    frame: str
    description: str


def healpix_grid(order: int, *, within: Moc | None = None, step: int = 1) -> HealpixGrid:
    """Griglia HEALPix all'ordine dato (obbligatorio): contorni delle celle in ICRS, NESTED.

    ``within`` (MOC spaziale) limita le celle a quelle che lo toccano all'ordine dato; senza ``within`` la
    griglia di tutto il cielo è ammessa fino a ``GRID_MAX_CELLS`` celle (``GRID_TOO_LARGE``).
    Calcolo: ``astropy-healpix`` (``boundaries_lonlat``)."""
    order = _check_order(order, SPACE_MAX_ORDER, "order")
    if isinstance(step, bool) or not isinstance(step, int) or step < 1:
        raise ValueError("step: intero ≥ 1 (punti per lato del contorno)")
    hp = _healpix(order)
    if within is None:
        if hp.npix > GRID_MAX_CELLS:
            raise MocError("GRID_TOO_LARGE", f"griglia di tutto il cielo all'ordine {order}: {hp.npix} celle, oltre "
                           f"{GRID_MAX_CELLS}; indicare within=MOC")
        cells = np.arange(hp.npix, dtype=np.int64)
        where = "tutto il cielo"
    else:
        if not isinstance(within, Moc) or within.kind != "space":
            raise MocError("MOC_TYPE_MISMATCH", "healpix_grid: within deve essere un MOC spaziale")
        _check_celestial(within.body, f"MOC {within.origin}")
        # mocpy: refine_to_order modifica il MOC sul posto (verificato), l'unione con un MOC vuoto no.
        target = within.moc.degrade_to_order(order) if within.space_order > order \
            else within.moc.union(MOC.new_empty(order))
        cells = np.asarray(target.flatten(), dtype=np.int64)
        if cells.size > GRID_MAX_CELLS:
            raise MocError("GRID_TOO_LARGE", f"griglia di {cells.size} celle oltre {GRID_MAX_CELLS}")
        where = f"celle che toccano il MOC {within.origin}"
    lon, lat = hp.boundaries_lonlat(cells, step=step)
    description = (f"griglia HEALPix {HEALPIX_SCHEME} in {HEALPIX_FRAME}, ordine {order}: {cells.size} celle, "
                   f"{where} (calcolo: {_healpix_provenance()})")
    return HealpixGrid(order=order, cells=cells, lon=lon.to_value(u.deg), lat=lat.to_value(u.deg),
                       scheme=HEALPIX_SCHEME, frame=HEALPIX_FRAME, description=description)


# --------------------------------------------------------------------------
# P4 — MOC temporali e spazio-temporali; mappe di probabilità (D16-3, D16-4)
# --------------------------------------------------------------------------

def _tcb(times, what: str):
    """Istanti ``astropy.time.Time`` (la scala è parte dell'oggetto) convertiti in TCB, la scala dello standard."""
    from astropy.time import Time

    if not isinstance(times, Time):
        raise TypeError(f"{what}: servono istanti astropy.time.Time con la scala dichiarata")
    jd = np.atleast_1d(times.jd)
    if not np.all(np.isfinite(jd)):
        raise MocError("TIME_RANGE_INVALID", f"{what}: istanti non finiti")
    if np.any(jd < 0):
        raise MocError("TIME_RANGE_INVALID", f"{what}: istanti prima di JD 0, fuori dai MOC temporali (standard 2.0)")
    return Time(np.atleast_1d(times.tcb.jd1), np.atleast_1d(times.tcb.jd2), format="jd", scale="tcb")


def _time_note(times) -> str:
    return f"scala d'ingresso {times.scale.upper()}, convertiti in TCB con astropy.time"


def moc_from_times(start, end=None, *, order_max: int) -> Moc:
    """MOC temporale (D16-3) da istanti (``end=None``) o intervalli [start, end], all'ordine ``order_max``
    (obbligatorio, 0–61; 61 = 1 μs). Tempi convertiti in TCB (scala dello standard 2.0) con ``astropy.time``."""
    order = _check_order(order_max, TIME_MAX_ORDER, "order_max")
    begin = _tcb(start, "inizio")
    if end is None:
        moc = TimeMOC.from_times(begin, order=order)
        what = f"{begin.size} istanti"
    else:
        stop = _tcb(end, "fine")
        if stop.shape != begin.shape:
            raise MocError("TIME_RANGE_INVALID", "inizio e fine con numeri di valori diversi")
        if np.any(stop.jd < begin.jd):
            raise MocError("TIME_RANGE_INVALID", "intervallo con fine prima dell'inizio")
        moc = TimeMOC.from_time_ranges(begin, stop, order=order)
        what = f"{begin.size} intervalli"
    resolution = TimeMOC.order_to_time_resolution(order).to(u.s)
    step = (f"MOC temporale da {what} con mocpy.TimeMOC, ordine {order} (risoluzione {resolution.value!r} s), "
            f"{_time_note(start)}")
    result = Moc(moc=moc, kind="time", body=None, origin=f"tempi ({what})", history=(step,))
    return replace(result, warnings=(("MOC_EMPTY", "MOC vuoto"),) if result.is_empty else ())


def moc_space_time(start, end, coords, *, time_order: int, space_order: int) -> Moc:
    """MOC spazio-temporale da osservazioni: istanti (``end=None``) o intervalli con una posizione ciascuno
    (``SkyFrame``, convertita in ICRS con il 10); ordini obbligatori. Calcolo: ``mocpy.STMOC``."""
    t_order = _check_order(time_order, TIME_MAX_ORDER, "time_order")
    s_order = _check_order(space_order, SPACE_MAX_ORDER, "space_order")
    begin = _tcb(start, "inizio")
    lon, lat, note = _to_icrs(coords, "posizioni")
    if lon.size != begin.size:
        raise MocError("TIME_RANGE_INVALID", f"{begin.size} tempi e {lon.size} posizioni: serve una posizione per "
                       "osservazione")
    if end is None:
        moc = STMOC.from_times_positions(begin, t_order, lon * u.deg, lat * u.deg, s_order)
    else:
        stop = _tcb(end, "fine")
        if stop.shape != begin.shape or np.any(stop.jd < begin.jd):
            raise MocError("TIME_RANGE_INVALID", "intervalli non validi (numeri diversi o fine prima dell'inizio)")
        moc = STMOC.from_time_ranges_positions(begin, stop, lon * u.deg, lat * u.deg, time_depth=t_order,
                                               spatial_depth=s_order)
    step = (f"MOC spazio-temporale con mocpy.STMOC, ordini tempo {t_order} e spazio {s_order}, {lon.size} "
            f"osservazioni, {_time_note(start)}{note}")
    result = Moc(moc=moc, kind="space-time", body="celestial", origin=f"osservazioni ({lon.size})", history=(step,))
    return replace(result, warnings=(("MOC_EMPTY", "MOC vuoto"),) if result.is_empty else ())


#: Tolleranza della somma delle probabilità (decisione del proprietario del 2026-10-11): 1e-6 relativo.
PROBABILITY_SUM_TOLERANCE = 1e-6


@dataclass(frozen=True)
class ProbabilityMap:
    """Mappa di probabilità HEALPix (D16-4) come celle NUNIQ e densità di probabilità per steradiante."""

    uniq: np.ndarray  # uint64, celle NUNIQ (ICRS, NESTED)
    density: np.ndarray  # float64, probabilità per sr
    layout: str  # "flat" o "multi-order"
    max_order: int
    total: float  # somma delle probabilità, verificata = 1 entro PROBABILITY_SUM_TOLERANCE
    origin: str
    description: str

    @property
    def probability(self) -> np.ndarray:
        """Probabilità per cella = densità × area della cella."""
        return self.density * _uniq_area(self.uniq)


_UNIQ_STARTS = np.array([4 * 4 ** k for k in range(SPACE_MAX_ORDER + 1)], dtype=np.uint64)


def _uniq_order(uniq: np.ndarray) -> np.ndarray:
    """Ordine di ogni cella NUNIQ (uniq = 4·4^ordine + indice), calcolato con interi."""
    return np.searchsorted(_UNIQ_STARTS, np.asarray(uniq, dtype=np.uint64), side="right").astype(np.int64) - 1


def _uniq_area(uniq: np.ndarray) -> np.ndarray:
    return 4.0 * math.pi / (12.0 * 4.0 ** _uniq_order(uniq))


def _invalid_map(path, reason: str) -> MocError:
    return MocError("PROBABILITY_MAP_INVALID", f"{path}: mappa di probabilità non valida ({reason})")


def read_probability_map(path) -> ProbabilityMap:
    """Legge una mappa di probabilità LIGO/Virgo/KAGRA in FITS (D16-4): **piatta** (colonna ``PROB``,
    ``NSIDE``, ``ORDERING`` RING o NESTED) o **multi-ordine** (``UNIQ`` e ``PROBDENSITY`` in sr⁻¹,
    ``ORDERING='NUNIQ'``); ``COORDSYS='C'``. Probabilità in [0, 1], somma = 1 entro 10⁻⁶ relativo."""
    from astropy.table import Table

    path = Path(path)
    try:
        with fits.open(path, memmap=False) as hdul:
            tables = [h for h in hdul if isinstance(h, fits.BinTableHDU)]
            if not tables:
                raise _invalid_map(path, "nessuna tabella binaria")
            header = tables[0].header
            table = Table.read(tables[0], unit_parse_strict="silent")
    except MocError:
        raise
    except (OSError, ValueError) as exc:
        raise _invalid_map(path, exc) from exc
    if str(header.get("COORDSYS", "")).strip() != "C":
        raise _invalid_map(path, f"COORDSYS {header.get('COORDSYS')!r}: serve 'C' (equatoriale, ICRS)")
    ordering = str(header.get("ORDERING", "")).strip().upper()
    if "UNIQ" in table.colnames and "PROBDENSITY" in table.colnames:
        col = table["PROBDENSITY"]
        if col.unit is None or not col.unit.is_equivalent(1 / u.sr):
            raise _invalid_map(path, f"PROBDENSITY con unità {col.unit!r}: serve una densità per steradiante")
        density = np.asarray(col.quantity.to_value(1 / u.sr), dtype=np.float64)
        uniq = np.asarray(table["UNIQ"], dtype=np.uint64)
        layout = "multi-order"
    elif "PROB" in table.colnames:
        if ordering not in ("RING", "NESTED"):
            raise _invalid_map(path, f"ORDERING {ordering!r}: serve RING o NESTED")
        nside = int(header.get("NSIDE", 0))
        prob = np.asarray(table["PROB"], dtype=np.float64).ravel()  # anche colonne vettoriali (righe da 1024)
        if nside < 1 or nside & (nside - 1) or prob.size != 12 * nside * nside:
            raise _invalid_map(path, f"NSIDE {nside} e {prob.size} valori non coerenti")
        order = nside.bit_length() - 1
        cells = np.arange(prob.size, dtype=np.int64)
        if ordering == "RING":  # conversione nell'ordine NESTED con astropy-healpix
            nested = _healpix(order).ring_to_nested(cells)
            reordered = np.empty_like(prob)
            reordered[nested] = prob
            prob = reordered
        if np.any(~np.isfinite(prob)) or np.any(prob < 0) or np.any(prob > 1):
            raise MocError("PROBABILITY_OUT_OF_RANGE", f"{path}: probabilità per cella fuori da [0, 1]")
        uniq = (4 * 4 ** order + cells).astype(np.uint64)
        density = prob / (4.0 * math.pi / prob.size)
        layout = "flat"
    else:
        raise _invalid_map(path, "attese le colonne PROB (mappa piatta) o UNIQ e PROBDENSITY (multi-ordine)")
    if np.any(~np.isfinite(density)) or np.any(density < 0):
        raise MocError("PROBABILITY_OUT_OF_RANGE", f"{path}: densità di probabilità negative o non finite")
    probability = density * _uniq_area(uniq)
    if np.any(probability > 1):
        raise MocError("PROBABILITY_OUT_OF_RANGE", f"{path}: probabilità per cella oltre 1")
    total = float(np.sum(probability))
    if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise MocError("PROBABILITY_SUM_INVALID", f"{path}: somma delle probabilità {total!r}, attesa 1 entro "
                       f"{PROBABILITY_SUM_TOLERANCE:g} relativo")
    orders = _uniq_order(uniq)
    if uniq.size == 0 or np.any(orders < 0) or np.any(uniq >= 16 * _UNIQ_STARTS[orders]):
        raise _invalid_map(path, "celle UNIQ non valide")
    max_order = int(np.max(orders))
    description = (f"mappa di probabilità {layout} ({ordering}), ordine massimo {max_order}, {uniq.size} celle, "
                   f"somma delle probabilità {total!r} (= 1 entro {PROBABILITY_SUM_TOLERANCE:g} relativo), ICRS")
    return ProbabilityMap(uniq=uniq, density=density, layout=layout, max_order=max_order, total=total,
                          origin=str(path), description=description)


def moc_from_probability(pmap: ProbabilityMap, level: float, order_max: int) -> Moc:
    """Regione di credibilità (D16-4): la più piccola insieme di celle intere, prese per densità decrescente,
    con probabilità ≥ ``level`` (``mocpy.MOC.from_valued_healpix_cells`` con ``strict=False, no_split=True``).
    La probabilità contenuta è ricalcolata con ``mocpy`` e dichiarata."""
    from astropy.table import Table

    if not isinstance(pmap, ProbabilityMap):
        raise TypeError("moc_from_probability: serve una ProbabilityMap (read_probability_map)")
    order = _check_order(order_max, SPACE_MAX_ORDER, "order_max")
    if isinstance(level, bool) or not isinstance(level, (int, float)) or not 0.0 < float(level) <= 1.0:
        raise MocError("PROBABILITY_OUT_OF_RANGE", f"livello di credibilità {level!r}: ammesso in (0, 1]")
    depth = max(order, pmap.max_order)  # mocpy: il MOC è almeno profondo quanto la cella più piccola
    moc = MOC.from_valued_healpix_cells(pmap.uniq, pmap.density, max_depth=depth, values_are_densities=True,
                                        cumul_from=0.0, cumul_to=float(level), asc=False, strict=False,
                                        no_split=True)
    notes = []
    if depth > order:
        moc = moc.degrade_to_order(order)
        notes.append(("ORDER_DEGRADED", f"mappa all'ordine {pmap.max_order}: regione portata all'ordine {order} per "
                      "eccesso (celle più grandi che contengono la regione)"))
    contained = float(moc.probability_in_multiordermap(Table({"UNIQ": pmap.uniq,
                                                               "PROBDENSITY": pmap.density / u.sr})))
    step = (f"regione di credibilità {float(level)!r} da {pmap.origin} con mocpy.MOC.from_valued_healpix_cells "
            f"(densità decrescente, celle intere, strict=False, no_split=True), ordine {order}; probabilità "
            f"contenuta {contained!r} (mocpy.probability_in_multiordermap); {pmap.description}")
    result = Moc(moc=moc, kind="space", body="celestial", origin=f"mappa di probabilità {pmap.origin}",
                 history=(step,))
    return replace(result, warnings=tuple(notes) + (("CREDIBLE_PROBABILITY", f"{contained!r}"),))


# --------------------------------------------------------------------------
# P5 — Lettura da URL, MocServer (H26), build_moc (H9)
# --------------------------------------------------------------------------

_CACHE_MODULE = "16"


def _download(url: str, timeouts) -> bytes:
    """Scarica tutto il contenuto o niente (nessun dato parziale), con i timeout comuni di 04."""
    import requests

    with requests.get(url, timeout=timeouts.as_requests(), stream=True) as response:
        response.raise_for_status()
        return b"".join(response.iter_content(chunk_size=1 << 16))


def _read_bytes(payload: bytes, format: str | None, kind: str | None, suffix: str) -> Moc:
    import os
    import tempfile

    fd, tmp = tempfile.mkstemp(prefix="astrotwo-moc-", suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        return _read_path(Path(tmp), format, kind)
    finally:
        os.unlink(tmp)


def _fits_bytes(moc: Moc) -> bytes:
    import os
    import tempfile

    fd, tmp = tempfile.mkstemp(prefix="astrotwo-moc-", suffix=".fits")
    os.close(fd)
    try:
        write_moc(moc, tmp, overwrite=True)
        return Path(tmp).read_bytes()
    finally:
        os.unlink(tmp)


def _read_url(url: str, format: str | None, kind: str | None, cache, refresh: bool, timeouts) -> Moc:
    from datetime import UTC, datetime

    import requests

    from astrotwo.core.cache import NETWORK_TIMEOUTS, CacheError, SharedCache

    timeouts = NETWORK_TIMEOUTS if timeouts is None else timeouts
    cache = SharedCache() if cache is None else cache
    keys = {"fits": f"url:{url}", "json": f"url-from-json:{url}", "ascii": f"url-from-ascii:{url}"}
    cached, cached_fmt = None, None
    for fmt, key in keys.items():
        cached = cache.get(_CACHE_MODULE, key)
        if cached is not None:
            cached_fmt = fmt
            break
    notes: list[tuple[str, str]] = []
    if cached is None or refresh:
        try:
            payload = _download(url, timeouts)
        except requests.exceptions.RequestException as exc:
            if cached is None:
                raise MocError("NET_TIMEOUT", f"{url} non raggiungibile (timeout {timeouts.connect:g} s connessione, "
                               f"{timeouts.read:g} s lettura): {exc}", url=url) from exc
            notes.append(("FROM_CACHE", f"rete non disponibile ({type(exc).__name__}): copia in cache del "
                          f"{cached.retrieved_at.isoformat()}"))
        else:
            fmt = format if format is not None else _detect_format(payload[:80])
            moc = _read_bytes(payload, fmt, kind, f".{fmt}")
            retrieved_at = datetime.now(UTC)
            stored = payload if fmt == "fits" else _fits_bytes(moc)  # in cache sempre FITS IVOA (D16-2)
            try:
                cache.put(_CACHE_MODULE, keys[fmt], stored, origin=url, retrieved_at=retrieved_at)
            except CacheError as exc:  # es. CACHE_FULL: il MOC si usa comunque
                notes.append((exc.code, exc.message))
            step = f"letto da {url} ({fmt}, versione {moc.version}), scaricato il {retrieved_at.isoformat()}"
            return replace(moc, origin=url, history=(step,), warnings=tuple(notes) + moc.warnings)
    moc = _read_bytes(cached.data, "fits", kind, ".fits")
    version = moc.version if cached_fmt == "fits" else f"{VERSION_NOT_DECLARED} ({cached_fmt} originale)"
    if not notes:
        notes.append(("FROM_CACHE", f"copia in cache di {url}, scaricata il {cached.retrieved_at.isoformat()}"
                      + ("" if cached_fmt == "fits" else f", conservata in FITS IVOA (originale {cached_fmt})")))
    step = f"letto da {url} (copia in cache, versione {version})"
    return replace(moc, origin=url, version=version, history=(step,), warnings=tuple(notes) + moc.warnings)


#: Valori ammessi di ``intersect`` del MocServer (verificati il 2026-10-11 sul modulo del servizio).
MOCSERVER_INTERSECT: tuple[str, ...] = ("overlaps", "enclosed", "covers")
_MOCSERVER_RESERVED = {"ra", "dec", "sr", "time", "stc", "moc", "url", "intersect", "spacesys", "timesys", "get",
                       "fields", "fmt", "casesensitive", "maxrec", "expr", "op", "order"}
_PROPERTY_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.*?]*$")


@dataclass(frozen=True)
class MocServerResult:
    """Collezioni che coprono la regione (H26), con la richiesta registrata (origine e data della risposta)."""

    records: tuple[dict, ...]
    request: object  # RequestRecord del modulo 14
    description: str
    warnings: tuple[tuple[str, str], ...] = ()

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(str(r.get("ID")) for r in self.records)


def query_mocserver(region, *, properties: dict | None = None, intersect: str = "overlaps",
                    fields: tuple[str, ...] = ("ID", "obs_title"), cache=None, refresh: bool = False,
                    timeouts=None) -> MocServerResult:
    """Collezioni del MocServer del CDS che coprono la regione (H26): cerchio (cono ``RA``/``DEC``/``SR`` in ICRS)
    o MOC spaziale (``moc=`` in testo, POST); i poligoni si passano come MOC (``moc_from_region``). Filtri
    sulle proprietà del servizio con ``properties``. Rete e cache del 14; senza rete ``MOCSERVER_UNAVAILABLE``."""
    from astrotwo.core import vo_protocols as vo
    from astrotwo.core.cache import NETWORK_TIMEOUTS

    timeouts = NETWORK_TIMEOUTS if timeouts is None else timeouts
    if intersect not in MOCSERVER_INTERSECT:
        raise ValueError(f"intersect {intersect!r}: ammessi {', '.join(MOCSERVER_INTERSECT)} (il servizio ignora in "
                         "silenzio un valore sconosciuto)")
    params: dict[str, str] = {"get": "record", "fmt": "json", "intersect": intersect, "spacesys": "C"}
    if isinstance(region, CircleRegion):
        lon, lat, note = _to_icrs(region.center, "centro del cerchio")
        radius = region.radius
        if not isinstance(radius, u.Quantity) or not radius.isscalar or not radius.unit.is_equivalent(u.deg) \
                or not 0 < float(radius.to_value(u.deg)) <= 180:
            raise MocError("REGION_INVALID", f"raggio {radius!r}: serve un angolo con unità in (0°, 180°]")
        params.update({"RA": repr(float(lon[0])), "DEC": repr(float(lat[0])),
                       "SR": repr(float(radius.to_value(u.deg)))})
        method, where = "GET", f"cerchio ICRS ({lon[0]!r}°, {lat[0]!r}°) raggio {float(radius.to_value(u.deg))!r}°{note}"
    elif isinstance(region, Moc):
        if region.kind != "space":
            raise MocError("MOC_TYPE_MISMATCH", f"filtro spaziale del MocServer con un MOC {region.kind}")
        _check_celestial(region.body, f"MOC {region.origin}")
        params["moc"] = region.moc.to_string("ascii")
        method, where = "POST", f"MOC {region.origin} (ordine {region.space_order})"
    elif isinstance(region, PolygonRegion):
        raise TypeError("poligono: crearne prima il MOC con moc_from_region (il servizio non accetta lo STC con il "
                        "sistema ICRS dichiarato, verifica del 2026-10-11)")
    else:
        raise TypeError("region: CircleRegion o Moc spaziale")
    for name, value in (properties or {}).items():
        if not isinstance(name, str) or not _PROPERTY_NAME.match(name) or name.lower() in _MOCSERVER_RESERVED:
            raise ValueError(f"proprietà {name!r} non ammessa come filtro")
        params[name] = str(value)
    if not fields or not all(isinstance(f, str) and _PROPERTY_NAME.match(f) for f in fields):
        raise ValueError("fields: nomi di proprietà del MocServer")
    params["fields"] = ",".join(fields)
    try:
        response = vo._http("mocserver", vo.MOCSERVER_URL, params, method=method, cache=cache, refresh=refresh,
                            timeouts=timeouts)
    except vo.VoProtocolsError as exc:
        if exc.code == "NET_TIMEOUT":
            raise MocError("MOCSERVER_UNAVAILABLE", f"MocServer non raggiungibile, nessun filtro spaziale: "
                           f"{exc.message}") from exc
        raise MocError(exc.code, exc.message) from exc
    try:
        records = json.loads(response.payload.decode("utf-8"))
        if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
            raise ValueError("attesa una lista di record")
    except (UnicodeDecodeError, ValueError) as exc:
        text = response.payload[:200].decode("utf-8", "replace")
        raise MocError("SERVICE_ERROR", f"{vo.MOCSERVER_URL}: risposta non leggibile ({exc}): {text!r}") from exc
    notes = response.notes + vo._store(response, "mocserver", cache)
    arguments = {"region": where, "properties": dict(properties or {}), "intersect": intersect,
                 "fields": list(fields)}
    record = vo._record("mocserver", "query_mocserver", arguments, response, len(records))
    description = (f"{len(records)} collezioni del MocServer ({intersect}) per {where}"
                   + (f", filtri {dict(properties)}" if properties else "")
                   + f"; risposta del {response.retrieved_at.isoformat()}"
                   + (" (dalla cache)" if response.from_cache else ""))
    return MocServerResult(records=tuple(records), request=record, description=description, warnings=tuple(notes))


_BUILD_KINDS = ("image", "catalog", "moc")


def build_moc(sources, *, order_max: int, output=None, format: str = "fits", overwrite: bool = False) -> Moc:
    """Generazione di un MOC senza interfaccia (H9): unione dei MOC delle sorgenti, scritta in ``output`` se dato.

    Sorgenti: ``CircleRegion``/``PolygonRegion``, ``CatalogTable`` (13), ``FitsImage`` (11), ``Moc``, oppure
    coppie esplicite ``("image", percorso)``, ``("catalog", percorso)``, ``("moc", percorso)`` (il tipo di un
    file non si indovina). Per ora solo funzione: la riga di comando arriverà con il 24."""
    from astrotwo.core.catalogs import CatalogTable, read_table
    from astrotwo.core.images_fits import FitsImage, load_image

    order = _check_order(order_max, SPACE_MAX_ORDER, "order_max")
    items = list(sources)
    if not items:
        raise ValueError("build_moc: nessuna sorgente")
    mocs = []
    for item in items:
        if isinstance(item, tuple) and len(item) == 2 and item[0] in _BUILD_KINDS:
            what, path = item
            item = load_image(path) if what == "image" else read_table(path) if what == "catalog" \
                else read_moc(path, kind="space")
        if isinstance(item, (CircleRegion, PolygonRegion)):
            mocs.append(moc_from_region(item, order))
        elif isinstance(item, CatalogTable):
            mocs.append(moc_from_catalog(item, order))
        elif isinstance(item, FitsImage):
            mocs.append(moc_from_image(item, order))
        elif isinstance(item, Moc):
            if item.kind != "space":
                raise MocError("MOC_TYPE_MISMATCH", f"build_moc: MOC {item.kind}, attesi MOC spaziali")
            mocs.append(item)
        else:
            raise TypeError(f"build_moc: sorgente non riconosciuta {item!r}; i file vanno indicati come "
                            "('image'|'catalog'|'moc', percorso)")
    result = mocs[0]
    for other in mocs[1:]:
        result = result.union(other)
    steps = tuple(dict.fromkeys(sum((m.history for m in mocs), ())))
    result = replace(result, origin=f"build_moc di {len(mocs)} sorgenti",
                     history=steps + (f"build_moc: unione di {len(mocs)} MOC, ordine richiesto {order}",))
    if output is not None:
        write_moc(result, output, format=format, overwrite=overwrite)
        result = replace(result, history=result.history + (f"scritto in {output} ({format})",))
    return result
