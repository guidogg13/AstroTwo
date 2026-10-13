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

import dataclasses
import hashlib
import importlib.metadata
import re
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
    "LATITUDE_TYPES",
    "LONGITUDE_DIRECTIONS",
    "PlanetaryPosition",
    "convert_planetary_coordinates",
    "PlanetaryCollections",
    "list_planetary_collections",
    "EPNTAP_CONVENTIONS",
    "query_epntap",
    "PdsImage",
    "load_pds_image",
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
    if isinstance(layer, PdsImage):
        if layer.body is None:
            return None, f"{name}: corpo non dichiarato o non normalizzabile nell'etichetta PDS"
        return (layer.body,), f"{name}: corpo dall'etichetta PDS"
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


# --------------------------------------------------------------------------
# P2 — posizioni planetarie e conversioni di convenzione (spiceypy)
# --------------------------------------------------------------------------

LATITUDE_TYPES = ("planetocentric", "planetographic")
LONGITUDE_DIRECTIONS = ("east", "west")


def _convention(value: object, allowed: tuple[str, ...], what: str) -> str:
    if value not in allowed:
        raise PlanetaryDataError("PLANETARY_CONVENTION_REQUIRED", f"{what} {value!r}: la convenzione non si assume "
                                 f"mai; valori: {', '.join(allowed)}")
    return value


def _angle_deg(value: object, what: str) -> np.float64:
    if not isinstance(value, u.Quantity) or not value.unit.is_equivalent(u.deg) or value.size != 1:
        raise TypeError(f"{what}: serve un angolo con unità (Quantity), non {value!r}")
    number = np.float64(value.to_value(u.deg))
    if not np.isfinite(number):
        raise PlanetaryDataError("COORD_OUT_OF_RANGE", f"{what} {value!r}: non finita")
    return number


@dataclass(frozen=True)
class PlanetaryPosition:
    """Posizione sulla superficie di un corpo, con corpo e convenzioni sempre dichiarati (§6).

    ``lon`` in [0°, 360°) nel verso ``longitude_direction`` (in ingresso ammessa [−180°, 360°], riportata in
    [0°, 360°)), ``lat`` in [−90°, +90°] del tipo ``latitude_type``; ``body`` = ``PlanetaryBody`` o nome.
    """

    lon: u.Quantity
    lat: u.Quantity
    body: PlanetaryBody
    latitude_type: str
    longitude_direction: str
    notes: tuple[str, ...] = ()
    library: str | None = None
    command: PlanetaryCommand | None = None

    def __post_init__(self) -> None:
        _require_enabled("PlanetaryPosition")
        _convention(self.latitude_type, LATITUDE_TYPES, "latitude_type")
        _convention(self.longitude_direction, LONGITUDE_DIRECTIONS, "longitude_direction")
        if isinstance(self.body, str):
            object.__setattr__(self, "body", PlanetaryBody.from_name(self.body))
        if not isinstance(self.body, PlanetaryBody):
            raise TypeError("body: serve un PlanetaryBody o il nome del corpo (il corpo non si assume)")
        lon, lat = _angle_deg(self.lon, "lon"), _angle_deg(self.lat, "lat")
        if not -90.0 <= lat <= 90.0:
            raise PlanetaryDataError("COORD_OUT_OF_RANGE", f"latitudine {lat!r}° fuori da [−90°, +90°]")
        if not -180.0 <= lon <= 360.0:
            raise PlanetaryDataError("COORD_OUT_OF_RANGE", f"longitudine {lon!r}° fuori da [−180°, 360°]")
        object.__setattr__(self, "lon", np.float64(lon % 360.0) * u.deg)
        object.__setattr__(self, "lat", lat * u.deg)

    @property
    def text(self) -> str:
        return (f"{self.body.name}: longitudine {float(self.lon.value)!r}° ({self.longitude_direction}, [0°, 360°)), "
                f"latitudine {float(self.lat.value)!r}° ({self.latitude_type})")


def _flip(lon_deg: np.float64) -> np.float64:
    """Cambio di verso della longitudine: λ' = (360° − λ) mod 360° (definizione delle due convenzioni)."""
    return np.float64((360.0 - lon_deg) % 360.0)


def _latitude(body: PlanetaryBody, lat_deg: np.float64, source: str, target: str) -> np.float64:
    """Latitudine sullo sferoide del kernel (a = RADII[0], c = RADII[2]) con ``spiceypy`` (§3 scelta 5).

    Sullo sferoide la relazione tra le latitudini non dipende dalla longitudine: si calcola al meridiano 0.
    """
    if source == target:
        return lat_deg
    a = body.equatorial_radius.to_value(u.km)
    c = body.polar_radius.to_value(u.km)
    f = float(body.flattening)
    lat = np.deg2rad(lat_deg)
    if source == "planetocentric":
        direction = spiceypy.latrec(1.0, 0.0, float(lat))
        point = spiceypy.surfpt([0.0, 0.0, 0.0], direction, a, a, c)
        point = point[0] if isinstance(point, tuple) else point
        _, out, _ = spiceypy.recpgr(body.name, point, a, f)
    else:
        point = spiceypy.pgrrec(body.name, 0.0, float(lat), 0.0, a, f)
        _, _, out = spiceypy.reclat(point)
    return np.float64(np.rad2deg(out))


@_registered
def convert_planetary_coordinates(position: PlanetaryPosition, latitude_type: str,
                                  longitude_direction: str) -> PlanetaryPosition:
    """Cambia convenzione di latitudine e/o di longitudine; restituisce una nuova ``PlanetaryPosition``."""
    _require_enabled("convert_planetary_coordinates")
    if not isinstance(position, PlanetaryPosition):
        raise TypeError("position: serve una PlanetaryPosition (corpo e convenzioni dichiarati)")
    _convention(latitude_type, LATITUDE_TYPES, "latitude_type")
    _convention(longitude_direction, LONGITUDE_DIRECTIONS, "longitude_direction")
    _load_kernel()
    body = position.body
    lat = _latitude(body, np.float64(position.lat.to_value(u.deg)), position.latitude_type, latitude_type)
    lon = np.float64(position.lon.to_value(u.deg))
    if longitude_direction != position.longitude_direction:
        lon = _flip(lon)
    notes = [f"da: {position.text}"]
    if latitude_type != position.latitude_type:
        notes.append(f"latitudine {position.latitude_type} → {latitude_type} con spiceypy (surfpt/recpgr o "
                     f"pgrrec/reclat) sullo sferoide del kernel: raggio equatoriale {float(body.radii[0].value)!r} km "
                     f"(RADII[0]), polare {float(body.radii[2].value)!r} km (RADII[2]), schiacciamento "
                     f"{float(body.flattening)!r}"
                     + ("; corpo triassiale: RADII[1] non usato" if body.radii[0] != body.radii[1] else ""))
    if longitude_direction != position.longitude_direction:
        notes.append(f"longitudine {position.longitude_direction} → {longitude_direction}: (360° − λ) mod 360° "
                     "(definizione delle due convenzioni)")
    if len(notes) == 1:
        notes.append("convenzioni uguali: nessuna conversione")
    command = PlanetaryCommand("convert_planetary_coordinates", (
        ("position", position), ("latitude_type", latitude_type), ("longitude_direction", longitude_direction)))
    return PlanetaryPosition(lon=lon * u.deg, lat=lat * u.deg, body=body, latitude_type=latitude_type,
                             longitude_direction=longitude_direction, notes=tuple(notes), library=_library(),
                             command=command)


# --------------------------------------------------------------------------
# P3 — collezioni per corpo (12) ed EPN-TAP (14)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanetaryCollections:
    """Collezioni HiPS per corpo (ramo "Sistema solare"), dalla copia locale delle collezioni del 12."""

    by_body: dict[str, tuple[dict, ...]]
    unknown: tuple[tuple[dict, str], ...]  # collezioni non celesti con corpo ignoto, con il motivo
    origin: str | None
    synced_at: datetime | None
    command: PlanetaryCommand

    def for_body(self, body: str) -> tuple[dict, ...]:
        return self.by_body.get(normalize_body_name(body), ())


def _record_values(record: dict, key: str) -> tuple[str, ...]:
    value = record.get(key)
    if value is None:
        return ()
    return tuple(str(v) for v in value) if isinstance(value, list) else (str(value),)


def list_planetary_collections(body: str | None = None, *, index) -> PlanetaryCollections:
    """Collezioni planetarie per corpo dalla copia locale ``CollectionIndex`` del 12 (nessuna rete qui).

    Il corpo di ogni collezione segue la regola del 12 (``hips_frame`` non celeste e ``hips_body`` uguale, poi la
    tabella dei nomi, D12-6); con ``body`` si restituiscono solo le collezioni di quel corpo.
    """
    from astrotwo.core.hips import CollectionIndex, _body

    _require_enabled("list_planetary_collections")
    if not isinstance(index, CollectionIndex):
        raise TypeError("index: serve un CollectionIndex del modulo 12")
    if index.synced_at is None:
        raise ValueError("index: copia locale delle collezioni non sincronizzata (CollectionIndex.sync del 12)")
    wanted = None if body is None else normalize_body_name(body)
    by_body: dict[str, list[dict]] = {}
    unknown = []
    for record in index.records:
        frames = _record_values(record, "hips_frame")
        if len(frames) != 1:
            continue
        props = {key: _record_values(record, key) for key in ("hips_body",)}
        found, notes = _body(props, frames[0], record["ID"])
        if found == CELESTIAL:
            continue
        if found is None:
            unknown.append((record, "; ".join(text for code, text in notes if code != "HIPS_BODY_DRAFT")))
            continue
        if wanted is None or found == wanted:
            by_body.setdefault(found, []).append(record)
    command = PlanetaryCommand("list_planetary_collections", (("body", body),))
    return PlanetaryCollections({k: tuple(v) for k, v in sorted(by_body.items())},
                                tuple(unknown) if wanted is None else (), index.origin, index.synced_at, command)


#: Convenzioni delle coordinate EPN-TAP 2.0 con ``spatial_frame_type = body`` (Raccomandazione IVOA 2022-08-22).
EPNTAP_CONVENTIONS = {"latitude_type": "planetocentric", "longitude_direction": "east",
                      "longitude_range": "0-360 deg", "source": "EPN-TAP 2.0 (IVOA REC 2022-08-22), "
                      "spatial_frame_type = body: c1 longitudine, c2 latitudine"}
_EPN_CORE = re.compile(r"\bepn_core\b", re.IGNORECASE)


def _column(table, name: str):
    lower = {c.lower(): c for c in table.colnames}
    return table[lower[name]] if name in lower else None


def _distinct(column) -> set[str]:
    values = set()
    for value in column:
        if value is np.ma.masked or value is None:
            values.add("")
            continue
        text = value.decode() if isinstance(value, bytes) else str(value)
        values.add(text.strip())
    return values


def _epntap_body(table) -> tuple[str | None, list[tuple[str, str]], dict]:
    """Corpo della tabella EPN-TAP (§3 scelta 8) e convenzioni da dichiarare nei metadati."""
    frames_col, targets_col = _column(table, "spatial_frame_type"), _column(table, "target_name")
    if frames_col is None or targets_col is None:
        missing = [n for n, c in (("spatial_frame_type", frames_col), ("target_name", targets_col)) if c is None]
        return None, [("BODY_UNKNOWN", f"colonne EPN-TAP mancanti nel risultato ({', '.join(missing)}): corpo non "
                       "ricavabile, la tabella si apre da sola")], {}
    frames = {f.lower() for f in _distinct(frames_col)}
    if frames == {"celestial"}:
        return CELESTIAL, [], {}
    targets = _distinct(targets_col)
    if frames != {"body"} or len(targets) != 1 or "" in targets or any("#" in t for t in targets):
        return None, [("BODY_UNKNOWN", f"spatial_frame_type {sorted(frames)} e target_name {sorted(targets)[:5]}: "
                       "un solo corpo con spatial_frame_type = body è richiesto per dichiararlo; la tabella si apre "
                       "da sola")], {}
    target = targets.pop()
    try:
        canonical = normalize_body_name(target)
    except PlanetaryDataError as exc:
        return None, [("BODY_UNKNOWN", f"target_name {target!r}: {exc.message}; la tabella si apre da sola")], {}
    return canonical, [("BODY_NORMALIZED", f"target_name {target!r} → {canonical!r} (tabella dei nomi, D12-6)"),
                       ("PLANETARY_CONVENTIONS", "coordinate planetocentriche, longitudine positiva verso est in "
                        "0–360° (EPN-TAP 2.0, spatial_frame_type = body)")], dict(EPNTAP_CONVENTIONS)


def query_epntap(service: str, adql: str, **tap_options):
    """Query ADQL su una tabella ``epn_core`` eseguita con ``tap_query`` del 14; tabella con corpo e convenzioni.

    ``tap_options``: le opzioni di ``tap_query`` (``max_rows``, ``mode``, ``cache``, ``refresh``, ``timeouts``…).
    """
    from astrotwo.core import vo_protocols as vo

    _require_enabled("query_epntap")
    if not isinstance(adql, str) or not _EPN_CORE.search(adql):
        raise PlanetaryDataError("ADQL_INVALID", "query EPN-TAP: serve una tabella <schema>.epn_core (EPN-TAP 2.0)")
    try:
        result = vo.tap_query(service, adql, **tap_options)
    except vo.VoProtocolsError as exc:
        raise PlanetaryDataError(exc.code, f"EPN-TAP {service}: {exc.message}") from exc
    body, notes, conventions = _epntap_body(result.table.table)
    table = result.table
    table.table.meta.update({"body": body, **{f"planetary_{k}": v for k, v in conventions.items()}})
    previous = table.warnings if body is None else tuple(w for w in table.warnings if w[0] != "BODY_UNKNOWN")
    table = dataclasses.replace(table, body=body, warnings=previous + tuple(notes))
    return dataclasses.replace(result, table=table)


# --------------------------------------------------------------------------
# P4 — immagini PDS4 (pds4_tools); PDS3 fermo su D19-8, URL fermi su D19-9
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PdsImage:
    """Immagine PDS4: valori fisici in ``float64`` (NaN per le costanti speciali), etichetta e corpo."""

    data: np.ndarray
    origin: str  # percorso dell'etichetta
    structure: str
    structure_type: str
    body: str | None
    targets: tuple[str, ...]
    element_array: dict
    special_pixels: int
    warnings: tuple[tuple[str, str], ...]
    library: str
    command: PlanetaryCommand
    read_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _pds_unreadable(source: str, reason: str) -> PlanetaryDataError:
    return PlanetaryDataError("PDS_UNREADABLE", f"{source}: {reason}; nessuna immagine aperta")


@_registered
def load_pds_image(source: str, *, structure: str | None = None) -> PdsImage:
    """Legge un'immagine PDS4 (etichetta ``.xml`` locale) con ``pds4_tools`` (D19-2, D19-2b; §3 scelta 9)."""
    import pds4_tools

    _require_enabled("load_pds_image")
    if not isinstance(source, str) or not source.strip():
        raise TypeError("source: serve il percorso dell'etichetta PDS4")
    if re.match(r"^[a-z][a-z0-9+.-]*://", source, re.IGNORECASE):
        raise _pds_unreadable(source, "lettura da URL ferma su D19-9 (da decidere): scaricare il prodotto e "
                              "aprire l'etichetta locale")
    path = Path(source)
    try:
        head = path.read_bytes()[:200]
    except OSError as exc:
        raise _pds_unreadable(source, f"file non leggibile ({exc})") from exc
    if b"PDS_VERSION_ID" in head:
        raise _pds_unreadable(source, "etichetta PDS3: lettura PDS3 ferma su D19-8 (libreria pdr da decidere)")
    try:
        products = pds4_tools.read(str(path), quiet=True, lazy_load=True)
        arrays = [st for st in products.structures if st.is_array() and st.type.startswith("Array_2D")]
    except Exception as exc:  # pds4_tools segnala con eccezioni generiche
        raise _pds_unreadable(source, f"etichetta PDS4 non leggibile con pds4_tools ({exc})") from exc
    names = [st.id for st in arrays]
    if not arrays:
        raise _pds_unreadable(source, "nessuna immagine Array_2D nel prodotto")
    if structure is None:
        if len(arrays) > 1:
            raise PlanetaryDataError("PDS_STRUCTURE_CHOICE_REQUIRED", f"{source}: più immagini nel prodotto "
                                     f"({', '.join(names)}): indicare structure", structures=tuple(names))
        chosen = arrays[0]
    elif structure in names:
        chosen = arrays[names.index(structure)]
    else:
        raise PlanetaryDataError("PDS_STRUCTURE_CHOICE_REQUIRED", f"{source}: struttura {structure!r} assente; "
                                 f"immagini: {', '.join(names)}", structures=tuple(names))
    try:
        masked = np.ma.masked_array(chosen.as_masked().data)
    except Exception as exc:
        raise _pds_unreadable(source, f"dati di {chosen.id!r} non leggibili ({exc})") from exc
    data = np.ma.filled(masked.astype(np.float64), np.nan)
    special = int(np.ma.count_masked(masked))
    targets = tuple(e.text.strip() for e in products.label.findall(".//Target_Identification/name")
                    if e.text and e.text.strip())
    notes: list[tuple[str, str]] = []
    body = None
    if len(set(targets)) == 1:
        try:
            body = normalize_body_name(targets[0])
            notes.append(("BODY_NORMALIZED", f"Target_Identification {targets[0]!r} → {body!r} (D12-6)"))
        except PlanetaryDataError as exc:
            notes.append(("BODY_UNKNOWN", f"Target_Identification {targets[0]!r}: {exc.message}; l'immagine si "
                          "apre da sola"))
    else:
        notes.append(("BODY_UNKNOWN", f"Target_Identification {list(targets)}: serve un solo corpo; l'immagine "
                      "si apre da sola"))
    if special:
        notes.append(("PDS_SPECIAL_CONSTANTS", f"{special} pixel con costanti speciali dell'etichetta → NaN"))
    element = dict(chosen.meta_data.get("Element_Array", {}))
    library = f"pds4_tools {importlib.metadata.version('pds4-tools')}"
    command = PlanetaryCommand("load_pds_image", (("source", source), ("structure", structure)))
    return PdsImage(data=data, origin=str(path), structure=chosen.id, structure_type=chosen.type, body=body,
                    targets=targets, element_array=element, special_pixels=special, warnings=tuple(notes),
                    library=library, command=command)
