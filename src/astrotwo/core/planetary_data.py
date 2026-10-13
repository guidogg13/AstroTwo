"""Dati planetari: corpi, sistemi di riferimento planetari, collezioni, EPN-TAP e immagini PDS.

Specifica: ``mdfiles/19-core-dati-planetari.md`` (stato ``approvato``).

Il modulo si scrive in parti (decisione del proprietario del 2026-10-13): P0 verifiche, P1 corpi, tabella dei
nomi (D12-6), ``body_of``, ``check_overlay`` e opzione D19-5; P2 conversioni di convenzione con ``spiceypy``;
P3 collezioni (12) ed EPN-TAP (14); P4 immagini PDS4 con ``pds4_tools``.

Regole applicate in tutto il modulo:

- il corpo non si assume mai: si legge dai metadati e si normalizza con la tabella dei nomi (``spiceypy.bodn2c``
  → identificativo NAIF → nome canonico); ``celestial`` non è un corpo (D19-3);
- costanti dei corpi dal kernel PCK della NAIF incluso nel progetto (``pck00011.tpc``, controllato con SHA-256),
  mai scritte a mano; nessun accesso alla rete in questo modulo (rete e cache dei moduli 12 e 14);
- con l'opzione dei dati planetari spenta (default, D19-5) le funzioni sui dati planetari danno
  ``PLANETARY_DATA_DISABLED``; il livello 1 celeste funziona come sempre;
- ogni risultato porta il comando con cui si riesegue (regola d'oro n. 6).
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import astropy.units as u
import numpy as np
import spiceypy
from spiceypy.utils.exceptions import SpiceyError

__all__ = [
    "BODY_TABLE",
    "CELESTIAL",
    "KERNEL_PATH",
    "KERNEL_SHA256",
    "PlanetaryDataError",
    "PlanetaryCommand",
    "run_command",
    "set_planetary_data_enabled",
    "planetary_data_enabled",
    "normalize_body_name",
    "PlanetaryBody",
    "body_of",
    "OverlayCheck",
    "check_overlay",
]

#: Valore del campo ``body`` per i dati astronomici (D19-3): non è un corpo.
CELESTIAL = "celestial"

#: Kernel PCK generico della NAIF incluso senza modifiche (§3, P0 punto 2).
KERNEL_PATH = Path(__file__).resolve().parent / "data" / "naif" / "pck00011.tpc"
KERNEL_SHA256 = "3dff7b1dbeceaa01f25467767d3fa25816051c85d162d1edf04acb310ee28bb1"

#: Tabella dei nomi dei corpi (D12-6, approvata il 2026-10-13): identificativo NAIF → nome canonico IAU in inglese
#: con l'iniziale maiuscola. Solo i corpi con un HiPS nel MocServer e presenti nel kernel PCK (D19-6).
BODY_TABLE: dict[int, str] = {
    10: "Sun", 199: "Mercury", 299: "Venus", 399: "Earth", 301: "Moon", 499: "Mars", 2000001: "Ceres",
    501: "Io", 502: "Europa", 503: "Ganymede", 504: "Callisto", 599: "Jupiter",
    601: "Mimas", 602: "Enceladus", 603: "Tethys", 604: "Dione", 605: "Rhea", 606: "Titan", 608: "Iapetus",
    701: "Ariel", 702: "Umbriel", 703: "Titania", 704: "Oberon", 705: "Miranda",
    801: "Triton", 899: "Neptune", 901: "Charon", 999: "Pluto",
}


# --------------------------------------------------------------------------
# Errori, comandi registrati, opzione D19-5
# --------------------------------------------------------------------------


class PlanetaryDataError(Exception):
    """Errore del modulo 19 con identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


@dataclass(frozen=True)
class PlanetaryCommand:
    """Comando registrato e rieseguibile (regola d'oro n. 6); il formato del registro è del modulo 24."""

    function: str
    arguments: tuple[tuple[str, object], ...]

    @property
    def text(self) -> str:
        return f"{self.function}({', '.join(f'{name}={value!r}' for name, value in self.arguments)})"


_COMMANDS: dict[str, object] = {}


def _registered(function):
    _COMMANDS[function.__name__] = function
    return function


def run_command(command: PlanetaryCommand):
    """Riesegue un comando registrato (T10): solo le funzioni di questo modulo, nessun altro codice."""
    if not isinstance(command, PlanetaryCommand) or command.function not in _COMMANDS:
        raise ValueError(f"comando non riconosciuto: {command!r}")
    return _COMMANDS[command.function](**dict(command.arguments))


_ENABLED = False


def set_planetary_data_enabled(flag: bool) -> None:
    """Accende o spegne i dati planetari (preferenza del modulo 40; spenti all'avvio, D19-5)."""
    global _ENABLED
    if not isinstance(flag, bool):
        raise TypeError("flag: serve True o False")
    _ENABLED = flag


def planetary_data_enabled() -> bool:
    return _ENABLED


def _require_enabled(what: str) -> None:
    if not _ENABLED:
        raise PlanetaryDataError("PLANETARY_DATA_DISABLED", f"{what}: dati planetari disattivati; attivarli nelle "
                                 "preferenze (opzione dei dati planetari, D19-5)")


# --------------------------------------------------------------------------
# Kernel PCK e tabella dei nomi (D12-6)
# --------------------------------------------------------------------------

_KERNEL_LOCK = threading.Lock()
_KERNEL_LOADED = False


def _library() -> str:
    return (f"spiceypy {importlib.metadata.version('spiceypy')} (CSPICE {spiceypy.tkvrsn('TOOLKIT')}), "
            f"kernel {KERNEL_PATH.name} della NAIF (SHA-256 {KERNEL_SHA256[:12]}…)")


def _load_kernel() -> None:
    """Carica il PCK una volta sola, dopo il controllo dell'impronta (kernel non modificato, regole NAIF)."""
    global _KERNEL_LOADED
    with _KERNEL_LOCK:
        if _KERNEL_LOADED:
            return
        try:
            digest = hashlib.sha256(KERNEL_PATH.read_bytes()).hexdigest()
        except OSError as exc:
            raise PlanetaryDataError("PLANETARY_KERNEL_INVALID", f"{KERNEL_PATH}: non leggibile ({exc})") from exc
        if digest != KERNEL_SHA256:
            raise PlanetaryDataError("PLANETARY_KERNEL_INVALID", f"{KERNEL_PATH.name}: SHA-256 {digest}, atteso "
                                     f"{KERNEL_SHA256}: kernel alterato, nessuna costante dei corpi")
        spiceypy.furnsh(str(KERNEL_PATH))
        _KERNEL_LOADED = True


def _supported() -> str:
    return ", ".join(BODY_TABLE[k] for k in sorted(BODY_TABLE, key=BODY_TABLE.get))


def normalize_body_name(name: object) -> str:
    """Nome canonico della tabella (D12-6): ``spiceypy.bodn2c`` → identificativo NAIF → nome canonico.

    ``celestial`` non è un corpo (D19-3); nome senza codice NAIF o fuori tabella → ``BODY_UNSUPPORTED``.
    Funziona anche con l'opzione dei dati planetari spenta (serve a leggere i metadati del 12).
    """
    if not isinstance(name, str) or not name.strip():
        raise PlanetaryDataError("BODY_UNSUPPORTED", f"corpo {name!r}: serve un nome; corpi supportati: "
                                 f"{_supported()}")
    text = name.strip()
    if text.lower() == CELESTIAL:
        raise PlanetaryDataError("BODY_UNSUPPORTED", "'celestial' indica i dati astronomici, non è un corpo (D19-3)")
    try:
        code = int(spiceypy.bodn2c(text))
    except SpiceyError as exc:
        raise PlanetaryDataError("BODY_UNSUPPORTED", f"corpo {text!r} senza codice NAIF; corpi supportati: "
                                 f"{_supported()}") from exc
    if code not in BODY_TABLE:
        raise PlanetaryDataError("BODY_UNSUPPORTED", f"corpo {text!r} (NAIF {code}) non nella tabella dei corpi "
                                 f"(D19-6); corpi supportati: {_supported()}", naif_id=code)
    return BODY_TABLE[code]


@dataclass(frozen=True)
class PlanetaryBody:
    """Corpo della tabella con identificativo NAIF e raggi del kernel PCK; si crea solo con ``from_name``."""

    name: str
    naif_id: int
    radii: u.Quantity  # (a, b, c) in km, float64, dal kernel (BODYnnn_RADII)
    source: str

    @classmethod
    def from_name(cls, name: str) -> PlanetaryBody:
        _require_enabled("PlanetaryBody")
        canonical = normalize_body_name(name)
        _load_kernel()
        naif_id = next(k for k, v in BODY_TABLE.items() if v == canonical)
        _, radii = spiceypy.bodvcd(naif_id, "RADII", 3)
        return cls(canonical, naif_id, np.asarray(radii, dtype=np.float64) * u.km,
                   f"{_library()}, BODY{naif_id}_RADII")

    @property
    def equatorial_radius(self) -> u.Quantity:
        return self.radii[0]

    @property
    def polar_radius(self) -> u.Quantity:
        return self.radii[2]

    @property
    def flattening(self) -> np.float64:
        """(a − c) / a dello sferoide usato da ``pgrrec``/``recpgr`` (§3 scelta 5)."""
        a, c = self.radii[0].to_value(u.km), self.radii[2].to_value(u.km)
        return np.float64((a - c) / a)


# --------------------------------------------------------------------------
# Corpo di un dato e controllo delle sovrapposizioni (D19-3, D19-4)
# --------------------------------------------------------------------------


def _describe_layer(layer) -> str:
    for attr in ("hips_id", "origin", "source"):
        value = getattr(layer, attr, None)
        if isinstance(value, str) and value:
            return f"{type(layer).__name__} {value}"
    return type(layer).__name__


def _bodies_of(layer) -> tuple[tuple[str, ...] | None, str]:
    """(corpi del livello — ``("celestial",)`` per i dati astronomici — oppure None se ignoto, motivo)."""
    from astrotwo.core.catalogs import CatalogTable
    from astrotwo.core.hips import HiPSService
    from astrotwo.core.images_fits import FitsImage
    from astrotwo.core.moc import MIXED_BODY, Moc

    name = _describe_layer(layer)
    if isinstance(layer, FitsImage):
        if layer.wcs is not None:
            return (CELESTIAL,), f"{name}: WCS celeste"
        return None, f"{name}: immagine senza WCS celeste, corpo non ricavabile"
    if isinstance(layer, Moc):
        if layer.body is None:
            return None, f"{name}: MOC temporale, nessun corpo"
        raw = layer.bodies if layer.body == MIXED_BODY else (layer.body,)
    elif isinstance(layer, (HiPSService, CatalogTable)):
        value = layer.body
        if value is None:
            return None, f"{name}: corpo non dichiarato nei metadati"
        raw = (value,)
    else:
        raise TypeError(f"body_of: tipo {type(layer).__name__} non previsto (HiPS, tabella, MOC, immagine)")
    bodies = []
    for value in raw:
        if value == CELESTIAL:
            bodies.append(CELESTIAL)
            continue
        try:
            bodies.append(normalize_body_name(value))
        except PlanetaryDataError as exc:
            return None, f"{name}: {exc.message}"
    return tuple(dict.fromkeys(bodies)), f"{name}: corpo dai metadati"


def body_of(dataset) -> str:
    """Corpo dichiarato nei metadati: ``celestial`` o il nome canonico; ignoto → ``BODY_UNKNOWN``."""
    bodies, reason = _bodies_of(dataset)
    if bodies is None:
        raise PlanetaryDataError("BODY_UNKNOWN", f"{reason}: il dato si apre da solo, non si sovrappone")
    if len(bodies) > 1:
        raise PlanetaryDataError("BODY_MISMATCH", f"{reason}: più corpi in un solo livello ({', '.join(bodies)})",
                                 bodies=bodies)
    if bodies[0] != CELESTIAL:
        _require_enabled("body_of")
    return bodies[0]


@dataclass(frozen=True)
class OverlayCheck:
    """Esito di ``check_overlay``: livelli sovrapponibili, corpi, forzatura e comando registrato."""

    body: str | None  # corpo comune; None se forzata tra corpi diversi
    bodies: tuple[str, ...]
    forced: bool
    layers: tuple[str, ...]
    warnings: tuple[tuple[str, str], ...]
    command: PlanetaryCommand
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def check_overlay(layers, force: bool = False) -> OverlayCheck:
    """Controlla che i livelli abbiano lo stesso corpo o siano tutti celesti (D19-4).

    Un solo livello è sempre compatibile (si apre da solo). Corpo ignoto con altri livelli → ``BODY_UNKNOWN``
    (non forzabile); corpi diversi o celeste + planetario → ``BODY_MISMATCH``, oppure con ``force=True`` esito
    con l'avviso ``BODY_MISMATCH_FORCED`` e la forzatura nel comando registrato.
    """
    if not isinstance(force, bool):
        raise TypeError("force: serve True o False")
    if isinstance(layers, (str, bytes)) or not isinstance(layers, Sequence) or not layers:
        raise TypeError("layers: serve una sequenza non vuota di livelli")
    names = tuple(_describe_layer(layer) for layer in layers)
    command = PlanetaryCommand("check_overlay", (("layers", names), ("force", force)))
    found = [_bodies_of(layer) for layer in layers]
    if len(layers) == 1:
        bodies, reason = found[0]
        if bodies is not None and any(b != CELESTIAL for b in bodies):
            _require_enabled("check_overlay")
        notes = () if bodies is not None else (("BODY_UNKNOWN", f"{reason}: il dato si apre da solo"),)
        common = bodies[0] if bodies is not None and len(bodies) == 1 else None
        return OverlayCheck(common, bodies or (), False, names, notes, command)
    unknown = [reason for bodies, reason in found if bodies is None]
    if unknown:
        raise PlanetaryDataError("BODY_UNKNOWN", "; ".join(unknown) + ": il dato non si sovrappone ad altri "
                                 "(si apre da solo)")
    all_bodies = tuple(dict.fromkeys(b for bodies, _ in found for b in bodies))
    if any(b != CELESTIAL for b in all_bodies):
        _require_enabled("check_overlay")
    involved = ", ".join(f"{n} → {'/'.join(bodies)}" for n, (bodies, _) in zip(names, found))
    if len(all_bodies) == 1:
        return OverlayCheck(all_bodies[0], all_bodies, False, names, (), command)
    if not force:
        raise PlanetaryDataError("BODY_MISMATCH", f"livelli di corpi diversi ({involved}): sovrapposizione "
                                 "rifiutata; forzabile solo con force=True, citato nel risultato", bodies=all_bodies)
    warning = ("BODY_MISMATCH_FORCED", f"sovrapposizione forzata dall'utente tra corpi diversi ({involved}): la "
               "coerenza della vista non è garantita")
    return OverlayCheck(None, all_bodies, True, names, (warning,), command)
