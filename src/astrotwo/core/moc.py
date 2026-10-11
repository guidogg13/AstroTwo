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
from dataclasses import dataclass, replace
from pathlib import Path

import astropy.units as u
import mocpy
import numpy as np
from astropy.io import fits
from mocpy import MOC, STMOC, TimeMOC

import astrotwo

__all__ = [
    "MOC_KINDS",
    "SPACE_MAX_ORDER",
    "SUPPORTED_VERSIONS",
    "TIME_MAX_ORDER",
    "Moc",
    "MocError",
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


def read_moc(source, *, format: str | None = None, kind: str | None = None) -> Moc:
    """Legge un MOC FITS IVOA, JSON o testo (H22) e ne dichiara la versione.

    FITS: versione da ``MOCVERS`` (1.0, 1.1, 2.0; assente → 1.1 assunta dallo standard), tipo da ``MOCDIM``.
    JSON e testo non portano la versione; senza prefisso ``s``/``t`` il tipo si indica con ``kind``.
    I MOC spaziali sono in ICRS per lo standard: corpo ``celestial``."""
    if kind is not None:
        _check_kind(kind)
    if isinstance(source, str) and source.split("://", 1)[0].lower() in ("http", "https"):
        raise MocError("MOC_UNREADABLE", f"{source}: la lettura da URL passa dalla rete (parte P5 del modulo)")
    path = Path(source)
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
