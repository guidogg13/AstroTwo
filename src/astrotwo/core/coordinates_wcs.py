"""Coordinate celesti, WCS, sistemi ed epoche di riferimento.

Specifica: ``mdfiles/10-core-coordinate-wcs.md`` (stato ``approvato``).

Regole applicate in tutto il modulo:

- ogni conversione passa da ``astropy.coordinates`` / ``astropy.wcs``
  (ERFA, WCSLIB): nessuna formula scritta a mano;
- nessun angolo senza unità, nessuna coordinata senza frame;
- le epoche non si assumono mai (D10-2): equinozio e ``obstime`` dei frame
  che li prevedono vanno dati in modo esplicito;
- coordinate pixel interne in convenzione numpy (origine 0); la conversione
  da e verso la convenzione FITS avviene solo in
  :func:`convert_pixel_convention` (DC7 di ``02-convenzioni.md``).

``resolve_name`` usa la cache comune di ``mdfiles/04-cache.md`` (prima la
cache, poi SIMBAD) e i timeout di rete comuni.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

import astropy
import astropy.units as u
import numpy as np
import pyvo
import requests
from astropy.coordinates import (
    BaseCoordinateFrame,
    SkyCoord,
    frame_transform_graph,
)
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS, FITSFixedWarning
from astropy.wcs.utils import (
    fit_wcs_from_points,
    proj_plane_pixel_scales,
    wcs_to_celestial_frame,
)

from astrotwo.core.cache import NETWORK_TIMEOUTS, NetworkTimeouts, SharedCache

__all__ = [
    "SUPPORTED_PROJECTIONS",
    "PIXEL_CONVENTIONS",
    "CoordinatesWcsError",
    "PixelPosition",
    "SkyFrame",
    "SkyPositions",
    "PixelPositions",
    "PropagatedPosition",
    "ResolvedName",
    "WcsSolution",
    "CalibrationThresholds",
    "CalibrationSolution",
    "GridLine",
    "GridLines",
    "GridSpacing",
    "GRID_STEPS_ARC",
    "GRID_STEPS_TIME",
    "supported_frames",
    "convert_pixel_convention",
    "convert_coordinates",
    "resolve_name",
    "propagate_position",
    "wcs_from_header",
    "pixel_to_sky",
    "sky_to_pixel",
    "astrometric_calibration",
    "compute_grid_lines",
    "choose_grid_spacing",
    "choose_projection",
]

#: Proiezioni dell'elenco D10-4 (manuale di Aladin, ed. giugno 2022, sez. 5.14).
SUPPORTED_PROJECTIONS: tuple[str, ...] = ("SIN", "TAN", "AIT", "ZEA", "STG", "CAR", "NCP", "ZPN")

#: Convenzioni dei pixel ammesse (DC7).
PIXEL_CONVENTIONS: tuple[str, ...] = ("fits", "numpy")

PixelConvention = Literal["fits", "numpy"]

# Frame esclusi: richiedono una posizione dell'osservatore (``location``) o
# una distanza per definire la trasformazione.
_EXCLUDED_FRAMES = frozenset({"galactocentric"})

# Attributi di frame che sono epoche e non si assumono mai (D10-2).
_EPOCH_ATTRIBUTES = ("equinox", "obstime")

# Chiavi che identificano una soluzione astrometrica storica delle lastre DSS.
_DSS_KEYS = ("AMDX1", "AMDY1", "PLTRAH")

_PROVENANCE = f"astropy {astropy.__version__}"


# --------------------------------------------------------------------------
# Errori
# --------------------------------------------------------------------------


class CoordinatesWcsError(Exception):
    """Errore del modulo 10 con identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


# --------------------------------------------------------------------------
# Convenzione dei pixel (DC7)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PixelPosition:
    """Coordinate pixel con la convenzione dichiarata."""

    x: np.ndarray
    y: np.ndarray
    convention: PixelConvention


def _check_convention(value: object) -> PixelConvention:
    if value not in PIXEL_CONVENTIONS:
        raise CoordinatesWcsError(
            "PIXEL_CONVENTION_UNKNOWN",
            f"convenzione dei pixel {value!r} non ammessa; ammesse: {', '.join(PIXEL_CONVENTIONS)}",
        )
    return value  # type: ignore[return-value]


def convert_pixel_convention(x, y, from_convention, to_convention) -> PixelPosition:
    """Unico punto di conversione FITS (indice da 1) ↔ numpy (indice da 0).

    ``x_fits = x_numpy + 1``, ``y_fits = y_numpy + 1`` e inverso, per valori
    anche non interi. L'indice di array è ``array[y_numpy, x_numpy]``.
    """
    source = _check_convention(from_convention)
    target = _check_convention(to_convention)
    xa = np.array(x, dtype=np.float64)
    ya = np.array(y, dtype=np.float64)
    if source != target:
        offset = 1.0 if target == "fits" else -1.0
        xa = xa + offset
        ya = ya + offset
    return PixelPosition(x=xa, y=ya, convention=target)


def _to_numpy_pixels(x, y, convention) -> tuple[np.ndarray, np.ndarray]:
    pos = convert_pixel_convention(x, y, convention, "numpy")
    return pos.x, pos.y


# --------------------------------------------------------------------------
# Frame, epoche, unità
# --------------------------------------------------------------------------


def supported_frames() -> tuple[str, ...]:
    """Frame di ``astropy.coordinates`` accettati dal modulo."""
    names = []
    for name in frame_transform_graph.get_names():
        cls = frame_transform_graph.lookup_name(name)
        if name in _EXCLUDED_FRAMES or "location" in cls.frame_attributes:
            continue
        names.append(name)
    return tuple(sorted(names))


def _frame_class(name: object) -> type[BaseCoordinateFrame]:
    if not isinstance(name, str) or name not in supported_frames():
        raise CoordinatesWcsError(
            "FRAME_UNSUPPORTED",
            f"frame {name!r} non supportato; frame supportati: {', '.join(supported_frames())}",
        )
    return frame_transform_graph.lookup_name(name)


def _to_epoch(value: object, what: str) -> Time:
    """Converte un'epoca dichiarata in ``Time`` senza assumere scale."""
    if isinstance(value, Time):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        # Anno giuliano (§6): l'epoca giuliana è definita in TT.
        return Time(float(value), format="jyear", scale="tt")
    if isinstance(value, str) and value[:1] in ("J", "B"):
        try:
            return Time(value)
        except ValueError:
            pass
    raise CoordinatesWcsError(
        "EPOCH_REQUIRED",
        f"{what} {value!r} non valido: usare un oggetto Time con scala dichiarata, "
        "un anno giuliano (es. 2000.0) o un'epoca 'J2000.0'/'B1950.0'",
    )


def _frame_instance(name: str, equinox=None, obstime=None) -> BaseCoordinateFrame:
    cls = _frame_class(name)
    given = {"equinox": equinox, "obstime": obstime}
    kwargs = {}
    for attr in _EPOCH_ATTRIBUTES:
        if attr in cls.frame_attributes:
            if given[attr] is None:
                raise CoordinatesWcsError(
                    "EPOCH_REQUIRED",
                    f"il frame {name!r} richiede {attr} esplicito: l'epoca non si assume mai (D10-2)",
                )
            kwargs[attr] = _to_epoch(given[attr], attr)
        elif given[attr] is not None:
            raise CoordinatesWcsError(
                "FRAME_UNSUPPORTED", f"il frame {name!r} non ha l'attributo {attr}"
            )
    return cls(**kwargs)


def _require_angle(value, what: str) -> u.Quantity:
    if not isinstance(value, u.Quantity):
        raise CoordinatesWcsError(
            "COORD_UNIT_MISSING", f"{what} senza unità: nessun angolo senza unità"
        )
    if not value.unit.is_equivalent(u.deg):
        raise CoordinatesWcsError(
            "COORD_UNIT_MISSING", f"{what} in unità {value.unit}, non angolare"
        )
    return value.to(u.deg).astype(np.float64)


def _check_epochs_explicit(frame: BaseCoordinateFrame) -> None:
    for attr in _EPOCH_ATTRIBUTES:
        if attr in frame.frame_attributes and frame.is_frame_attr_default(attr):
            raise CoordinatesWcsError(
                "EPOCH_REQUIRED",
                f"il frame {frame.name!r} ha {attr} di default di Astropy: l'epoca non si assume mai (D10-2)",
            )


@dataclass(frozen=True)
class SkyFrame:
    """Coordinate celesti con sistema, epoche e unità sempre dichiarati.

    ``epoch`` è l'epoca delle posizioni letta dai metadati (``None`` se non
    nota: non si assume). Non si possono creare coordinate senza unità.
    """

    coord: SkyCoord
    epoch: Time | None = None
    provenance: str = _PROVENANCE
    #: Valorizzato solo per coordinate da una WCS letta da header: lì valgono
    #: le regole di default dello standard FITS WCS (Paper II), dichiarate qui.
    frame_defaults_note: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.coord, SkyCoord):
            raise CoordinatesWcsError("COORD_UNIT_MISSING", "serve un SkyCoord con unità e frame")
        _frame_class(self.coord.frame.name)
        if self.frame_defaults_note is None:
            _check_epochs_explicit(self.coord.frame)
        if self.epoch is not None and not isinstance(self.epoch, Time):
            raise CoordinatesWcsError("EPOCH_REQUIRED", "epoch deve essere un oggetto Time")

    @classmethod
    def from_lonlat(cls, lon, lat, frame: str, *, equinox=None, obstime=None, epoch=None) -> SkyFrame:
        """Crea coordinate da longitudine/latitudine con unità esplicite."""
        lon_deg = _require_angle(lon, "longitudine")
        lat_deg = _require_angle(lat, "latitudine")
        lon_v = np.atleast_1d(lon_deg.value)
        lat_v = np.atleast_1d(lat_deg.value)
        if not (np.all(np.isfinite(lon_v)) and np.all(np.isfinite(lat_v))):
            raise CoordinatesWcsError("COORD_OUT_OF_RANGE", "coordinate non finite")
        if np.any((lat_v < -90.0) | (lat_v > 90.0)):
            raise CoordinatesWcsError(
                "COORD_OUT_OF_RANGE", "latitudine fuori da [-90°, +90°]", values=lat_v[(lat_v < -90) | (lat_v > 90)]
            )
        if np.any((lon_v < 0.0) | (lon_v >= 360.0)):
            raise CoordinatesWcsError(
                "COORD_OUT_OF_RANGE", "longitudine fuori da [0°, 360°)", values=lon_v[(lon_v < 0) | (lon_v >= 360)]
            )
        frame_obj = _frame_instance(frame, equinox=equinox, obstime=obstime)
        epoch_t = None if epoch is None else _to_epoch(epoch, "epoch")
        coord = SkyCoord(lon_deg, lat_deg, frame=frame_obj)
        return cls(coord=coord, epoch=epoch_t)

    @property
    def frame_name(self) -> str:
        return self.coord.frame.name

    @property
    def lon(self) -> u.Quantity:
        return self.coord.spherical.lon.to(u.deg)

    @property
    def lat(self) -> u.Quantity:
        return self.coord.spherical.lat.to(u.deg)

    @property
    def equinox(self) -> Time | None:
        return getattr(self.coord.frame, "equinox", None)

    @property
    def obstime(self) -> Time | None:
        return getattr(self.coord.frame, "obstime", None)

    def to(self, frame: str, *, equinox=None, obstime=None) -> SkyFrame:
        """Converte verso un altro frame (vedi :func:`convert_coordinates`)."""
        return convert_coordinates(self, frame, equinox=equinox, obstime=obstime)


def convert_coordinates(coords: SkyFrame, to_frame: str, *, equinox=None, obstime=None) -> SkyFrame:
    """Converte coordinate tra frame ed epoche con ``astropy.coordinates``.

    Il frame di partenza è quello di ``coords``; le epoche del frame di
    arrivo vanno date se il frame le prevede.
    """
    if not isinstance(coords, SkyFrame):
        raise CoordinatesWcsError("COORD_UNIT_MISSING", "coords deve essere uno SkyFrame")
    target = _frame_instance(to_frame, equinox=equinox, obstime=obstime)
    try:
        converted = coords.coord.transform_to(target)
    except Exception as exc:  # trasformazione non definita per questi dati
        raise CoordinatesWcsError(
            "FRAME_UNSUPPORTED",
            f"conversione {coords.frame_name} → {to_frame} non eseguibile: {exc}",
        ) from exc
    return SkyFrame(coord=converted, epoch=coords.epoch, frame_defaults_note=coords.frame_defaults_note)


# --------------------------------------------------------------------------
# Risoluzione dei nomi (SIMBAD; cache comune di 04-cache.md, D10-3)
# --------------------------------------------------------------------------

_NAME_TABLE = "name_resolution"
_NAME_COLUMNS = {
    "main_id": "TEXT",
    "ra_deg": "REAL",
    "dec_deg": "REAL",
    "coo_err_maj_mas": "REAL",
    "coo_err_min_mas": "REAL",
    "coo_err_angle_deg": "REAL",
    "coo_bibcode": "TEXT",
}
_SIMBAD_EPOCH_NOTE = "coordinate SIMBAD: ICRS all'epoca J2000 (documentazione di SIMBAD)"
_NETWORK_ERRORS = (requests.exceptions.RequestException, pyvo.dal.DALServiceError, OSError)


@dataclass(frozen=True)
class ResolvedName:
    """Nome risolto: coordinate ICRS con fonte, origine, data e incertezza."""

    name: str
    main_id: str
    coords: SkyFrame
    source: str
    origin: str
    retrieved_at: datetime
    from_cache: bool
    coo_err_maj: u.Quantity | None
    coo_err_min: u.Quantity | None
    coo_err_angle: u.Quantity | None
    coo_bibcode: str | None
    notes: tuple[str, ...] = ()


class _TimeoutSession(requests.Session):
    """Sessione HTTP che applica i timeout comuni (04-cache.md, CA1) a ogni richiesta."""

    def __init__(self, timeouts: NetworkTimeouts) -> None:
        super().__init__()
        self.timeouts = timeouts.as_requests()

    def request(self, method, url, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self.timeouts
        return super().request(method, url, **kwargs)


def _simbad_with_timeouts(timeouts: NetworkTimeouts):
    """``SimbadClass`` le cui richieste HTTP usano i timeout comuni di ``04-cache.md``.

    **Unico punto del codice che usa un campo interno di astroquery**
    (``_session``), verificato con astroquery 0.4.11 il 2026-10-10:

    - ``conf.timeout`` di ``astroquery.simbad`` (pubblico) è il limite di
      esecuzione lato server delle query asincrone, non un timeout HTTP;
    - ``query_object`` legge sempre ``hardlimit`` dalle capacità del servizio
      (anche con ``get_query_payload=True``) tramite la sessione interna, e le
      query sincrone di pyvo non passano alcun timeout a ``requests``.

    Per questo la sessione HTTP di astroquery si sostituisce con una che
    applica i timeout a ogni richiesta. Se astroquery cambiasse questo campo,
    il test ``test_t5_timeouts_reach_the_http_session`` fallirebbe.
    """
    from astroquery.simbad import SimbadClass

    simbad = SimbadClass()
    session = _TimeoutSession(timeouts)
    session.headers.update(simbad._session.headers)  # stesso User-Agent di astroquery
    simbad._session = session
    return simbad


def _query_simbad(name: str, timeouts: NetworkTimeouts):
    """Interroga SIMBAD (TAP) con ``astroquery``; restituisce (tabella, URL del servizio)."""
    simbad = _simbad_with_timeouts(timeouts)
    return simbad.query_object(name), simbad.tap.baseurl


def _column_value(table, column: str, target_unit) -> float | None:
    """Valore della prima riga convertito con l'unità dichiarata dalla colonna."""
    if column not in table.colnames:
        return None
    value = table[column][0]
    if np.ma.is_masked(value) or not np.isfinite(float(value)):
        return None
    unit = table[column].unit
    if unit is None:
        raise CoordinatesWcsError("COORD_UNIT_MISSING", f"colonna SIMBAD {column!r} senza unità")
    return float((float(value) * u.Unit(unit)).to_value(target_unit))


def _name_result(name: str, values: dict, origin: str, retrieved_at: datetime, from_cache: bool, notes=()) -> ResolvedName:
    def quantity(key, unit):
        value = values.get(key)
        return None if value is None else value * unit

    coords = SkyFrame.from_lonlat(
        values["ra_deg"] * u.deg, values["dec_deg"] * u.deg, "icrs", epoch=Time("J2000.0")
    )
    return ResolvedName(
        name=name,
        main_id=values["main_id"],
        coords=coords,
        source=f"SIMBAD (CDS) via astroquery; {_SIMBAD_EPOCH_NOTE}",
        origin=origin,
        retrieved_at=retrieved_at,
        from_cache=from_cache,
        coo_err_maj=quantity("coo_err_maj_mas", u.mas),
        coo_err_min=quantity("coo_err_min_mas", u.mas),
        coo_err_angle=quantity("coo_err_angle_deg", u.deg),
        coo_bibcode=values.get("coo_bibcode"),
        notes=tuple(notes),
    )


def resolve_name(
    name: str,
    *,
    source: str = "simbad",
    cache: SharedCache | None = None,
    refresh: bool = False,
    timeouts: NetworkTimeouts = NETWORK_TIMEOUTS,
) -> ResolvedName:
    """Risolve un nome di oggetto in coordinate ICRS con SIMBAD.

    Politica (D10-3 e decisione del 2026-10-09): **prima la cache** — un nome
    già risolto viene dalla cache comune, dichiarato tale con origine e data;
    ``refresh=True`` interroga di nuovo SIMBAD. Se la rete non risponde si usa
    la copia in cache, se c'è, dichiarandolo; altrimenti ``NET_TIMEOUT``.
    """
    if not isinstance(name, str) or not name.strip():
        raise CoordinatesWcsError("NAME_NOT_FOUND", "nome vuoto")
    if source != "simbad":
        raise CoordinatesWcsError("NAME_NOT_FOUND", f"fonte {source!r} non prevista: unica fonte 'simbad'")
    clean = " ".join(name.split())
    key = f"simbad:{clean}"
    cache = SharedCache() if cache is None else cache
    table = cache.table("10", _NAME_TABLE, _NAME_COLUMNS)

    cached = table.get(key)
    if cached is not None and not refresh:
        return _name_result(clean, cached.data, cached.origin, cached.retrieved_at, from_cache=True)

    try:
        result, origin = _query_simbad(clean, timeouts)
    except _NETWORK_ERRORS as exc:
        if cached is not None:
            return _name_result(
                clean, cached.data, cached.origin, cached.retrieved_at, from_cache=True,
                notes=(f"SIMBAD non raggiungibile ({type(exc).__name__}): copia in cache",),
            )
        raise CoordinatesWcsError(
            "NET_TIMEOUT",
            f"SIMBAD non raggiungibile per {clean!r} (timeout {timeouts.connect:g} s connessione, "
            f"{timeouts.read:g} s lettura): {exc}",
        ) from exc

    if result is None or len(result) == 0:
        raise CoordinatesWcsError("NAME_NOT_FOUND", f"{clean!r} non trovato in SIMBAD")
    if len({str(r["main_id"]) for r in result}) > 1:
        raise CoordinatesWcsError(
            "NAME_NOT_FOUND", f"{clean!r} è ambiguo in SIMBAD: nessun nome risolto approssimativamente"
        )
    ra, dec = _column_value(result, "ra", u.deg), _column_value(result, "dec", u.deg)
    if ra is None or dec is None:
        raise CoordinatesWcsError("NAME_NOT_FOUND", f"{clean!r} è in SIMBAD ma senza coordinate")
    row = result[0]
    bibcode = None if "coo_bibcode" not in result.colnames or np.ma.is_masked(row["coo_bibcode"]) else str(row["coo_bibcode"])
    values = {
        "main_id": str(row["main_id"]),
        "ra_deg": ra,
        "dec_deg": dec,
        "coo_err_maj_mas": _column_value(result, "coo_err_maj", u.mas),
        "coo_err_min_mas": _column_value(result, "coo_err_min", u.mas),
        "coo_err_angle_deg": _column_value(result, "coo_err_angle", u.deg),
        "coo_bibcode": bibcode,
    }
    retrieved_at = datetime.now(UTC)
    table.put(key, values, origin=origin, retrieved_at=retrieved_at)
    return _name_result(clean, values, origin, retrieved_at, from_cache=False)


# --------------------------------------------------------------------------
# Propagazione con moto proprio
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PropagatedPosition:
    """Posizione propagata, con epoca di origine ed epoca usata dichiarate."""

    position: SkyFrame
    source_epoch: Time
    target_epoch: Time
    radial_velocity: u.Quantity | None
    notes: tuple[str, ...]
    provenance: str = _PROVENANCE


def propagate_position(
    position: SkyFrame,
    *,
    pm_ra_cosdec,
    pm_dec,
    parallax,
    target_epoch,
    radial_velocity=None,
) -> PropagatedPosition:
    """Propaga una posizione all'epoca richiesta con ``SkyCoord.apply_space_motion``.

    Epoca di origine (``position.epoch``), moto proprio e parallasse sono
    obbligatori: mancano → ``EPOCH_REQUIRED`` (D10-2).
    """
    if position.epoch is None:
        raise CoordinatesWcsError(
            "EPOCH_REQUIRED", "epoca di origine della posizione non nota: l'epoca non si assume mai"
        )
    for name, value in (("pm_ra_cosdec", pm_ra_cosdec), ("pm_dec", pm_dec), ("parallax", parallax)):
        if value is None:
            raise CoordinatesWcsError("EPOCH_REQUIRED", f"{name} mancante: serve per la propagazione")
        if not isinstance(value, u.Quantity):
            raise CoordinatesWcsError("COORD_UNIT_MISSING", f"{name} senza unità")
    if target_epoch is None:
        raise CoordinatesWcsError("EPOCH_REQUIRED", "epoca di arrivo mancante")
    target = _to_epoch(target_epoch, "target_epoch")
    if np.any(parallax <= 0 * u.mas):
        raise CoordinatesWcsError("COORD_OUT_OF_RANGE", "parallasse non positiva: distanza non definita")
    frame = position.coord.frame
    if "ra" not in frame.representation_component_names:
        raise CoordinatesWcsError(
            "FRAME_UNSUPPORTED",
            f"propagazione con pm_ra_cosdec/pm_dec: serve un frame equatoriale, non {frame.name!r}",
        )
    kwargs = dict(
        ra=position.coord.spherical.lon,
        dec=position.coord.spherical.lat,
        pm_ra_cosdec=pm_ra_cosdec,
        pm_dec=pm_dec,
        distance=parallax.to(u.pc, equivalencies=u.parallax()),
        obstime=position.epoch,
        frame=frame.replicate_without_data(),
    )
    notes = []
    if radial_velocity is not None:
        if not isinstance(radial_velocity, u.Quantity):
            raise CoordinatesWcsError("COORD_UNIT_MISSING", "radial_velocity senza unità")
        kwargs["radial_velocity"] = radial_velocity
    else:
        notes.append(
            "velocità radiale non fornita: ERFA la tratta come 0 km/s (effetto prospettico radiale non applicato)"
        )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        moved = SkyCoord(**kwargs).apply_space_motion(new_obstime=target)
    notes.extend(str(w.message) for w in caught)
    result = SkyCoord(moved.spherical.lon, moved.spherical.lat, frame=frame.replicate_without_data())
    return PropagatedPosition(
        position=SkyFrame(coord=result, epoch=target),
        source_epoch=position.epoch,
        target_epoch=target,
        radial_velocity=radial_velocity,
        notes=tuple(notes),
    )


# --------------------------------------------------------------------------
# WCS
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class WcsSolution:
    """Parte celeste di una WCS con le informazioni per dichiararne l'uso."""

    wcs: WCS
    projection: str
    frame_name: str
    equinox: Time | None
    pixel_shape: tuple[int, int] | None
    image_epoch: Time | None
    legacy: str | None
    fixes: tuple[str, ...]
    provenance: str = _PROVENANCE


def _build_wcs(header) -> tuple[WCS, tuple[str, ...]]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        w = WCS(header)
    fixes = tuple(str(c.message).strip() for c in caught if issubclass(c.category, FITSFixedWarning))
    return w, fixes


def _image_epoch(w: WCS) -> Time | None:
    mjd = w.wcs.mjdobs
    if mjd is None or not np.isfinite(mjd):
        return None
    scale = (w.wcs.timesys or "UTC").strip().lower() or "utc"
    return Time(mjd, format="mjd", scale=scale)


def _celestial_frame_info(w: WCS) -> tuple[str, Time | None]:
    frame = wcs_to_celestial_frame(w)
    return frame.name, getattr(frame, "equinox", None)


def _check_internal_consistency(w: WCS) -> None:
    matrix = w.pixel_scale_matrix
    if not np.all(np.isfinite(matrix)) or abs(np.linalg.det(matrix)) == 0.0:
        raise CoordinatesWcsError("WCS_INVALID", "matrice di scala dei pixel singolare o non finita")
    if w.pixel_shape is not None:
        cx, cy = (w.pixel_shape[0] - 1) / 2.0, (w.pixel_shape[1] - 1) / 2.0
    else:
        cx, cy = w.wcs.crpix[0] - 1.0, w.wcs.crpix[1] - 1.0
    world = w.pixel_to_world(cx, cy)
    bx, by = w.world_to_pixel(world)
    if not (np.isfinite(bx) and np.isfinite(by)) or math.hypot(bx - cx, by - cy) > 1e-6:
        raise CoordinatesWcsError(
            "WCS_INVALID", "la WCS non è coerente: andata e ritorno al centro oltre 1e-6 pixel"
        )


def _projection_code(header, w: WCS) -> str:
    lng = w.wcs.lng
    key = f"CTYPE{lng + 1}"
    ctype = header.get(key) if hasattr(header, "get") else None
    if isinstance(ctype, str) and len(ctype) >= 8:
        return ctype[5:8].strip("-").upper()
    return w.wcs.ctype[lng][5:8].strip("-").upper()


def _is_cd_key(key: str) -> bool:
    if not key.startswith("CD") or "_" not in key:
        return False
    i, _, j = key[2:].partition("_")
    return i.isdigit() and j.isdigit()


def wcs_from_header(header) -> WcsSolution:
    """Costruisce e valida la WCS celeste di un header FITS (``astropy.wcs``).

    Restituisce la parte celeste con le correzioni applicate da WCSLIB
    (es. ``NCP`` → ``SIN``, DSS → TPD, regole di default di ``RADESYS``).
    """
    if not isinstance(header, fits.Header):
        if isinstance(header, Mapping):
            header = fits.Header(header)
        else:
            raise CoordinatesWcsError("WCS_MISSING", "serve un header FITS")
    legacy = "DSS" if any(k in header for k in _DSS_KEYS) else None
    cd_values = [header[k] for k in header if isinstance(k, str) and _is_cd_key(k)]
    if cd_values and all(float(v) == 0.0 for v in cd_values):
        # WCSLIB sostituirebbe in silenzio una CD tutta nulla con l'identità.
        raise CoordinatesWcsError("WCS_INVALID", "matrice CD tutta nulla: soluzione non definita")
    try:
        w, fixes = _build_wcs(header)
    except Exception as exc:
        if legacy:
            raise CoordinatesWcsError(
                "WCS_LEGACY_UNSUPPORTED", f"soluzione storica {legacy} non supportata dalla libreria: {exc}"
            ) from exc
        raise CoordinatesWcsError("WCS_INVALID", f"WCS non costruibile: {exc}") from exc
    if not w.has_celestial:
        if legacy:
            raise CoordinatesWcsError(
                "WCS_LEGACY_UNSUPPORTED", f"soluzione storica {legacy} non tradotta dalla libreria"
            )
        raise CoordinatesWcsError("WCS_MISSING", "l'header non contiene una WCS celeste")
    cel = w.celestial
    _check_internal_consistency(cel)
    frame_name, equinox = _celestial_frame_info(cel)
    notes = list(fixes)
    if "RADESYS" not in header and "RADECSYS" not in header and frame_name in ("icrs", "fk5", "fk4"):
        notes.append(
            f"RADESYS assente: sistema '{frame_name}' dalle regole di default dello standard FITS WCS (Paper II)"
        )
    if equinox is not None and "EQUINOX" not in header and "EPOCH" not in header:
        notes.append(
            f"EQUINOX assente: equinozio {equinox} dalle regole di default dello standard FITS WCS (Paper II)"
        )
    shape = tuple(int(n) for n in cel.pixel_shape) if cel.pixel_shape is not None else None
    return WcsSolution(
        wcs=cel,
        projection=_projection_code(header, w),
        frame_name=frame_name,
        equinox=equinox,
        pixel_shape=shape,
        image_epoch=_image_epoch(w),
        legacy=legacy,
        fixes=tuple(notes),
    )


def _as_wcs(wcs) -> WCS:
    if isinstance(wcs, WcsSolution):
        return wcs.wcs
    if isinstance(wcs, WCS):
        if not wcs.has_celestial:
            raise CoordinatesWcsError("WCS_MISSING", "la WCS non è celeste")
        return wcs.celestial if wcs.naxis != 2 else wcs
    raise CoordinatesWcsError("WCS_MISSING", "serve una WCS (astropy.wcs.WCS o WcsSolution)")


def _out_of_field(w: WCS, x: np.ndarray, y: np.ndarray) -> np.ndarray | None:
    if w.pixel_shape is None:
        return None
    nx, ny = w.pixel_shape
    finite = np.isfinite(x) & np.isfinite(y)
    inside = finite & (x >= -0.5) & (x <= nx - 0.5) & (y >= -0.5) & (y <= ny - 0.5)
    return ~inside


@dataclass(frozen=True)
class SkyPositions:
    """Risultato di :func:`pixel_to_sky`."""

    coords: SkyFrame
    out_of_field: np.ndarray | None
    warnings: tuple[str, ...]
    display_epoch: Time
    display_epoch_source: str


@dataclass(frozen=True)
class PixelPositions:
    """Risultato di :func:`sky_to_pixel`."""

    pixels: PixelPosition
    out_of_field: np.ndarray | None
    warnings: tuple[str, ...]


def pixel_to_sky(wcs, x, y, *, convention) -> SkyPositions:
    """Pixel → cielo con ``astropy.wcs``; convenzione dei pixel obbligatoria.

    I punti fuori dall'immagine sono restituiti con l'avviso ``OUT_OF_FIELD``.
    """
    w = _as_wcs(wcs)
    xn, yn = _to_numpy_pixels(x, y, convention)
    coord = w.pixel_to_world(xn, yn)
    outside = _out_of_field(w, xn, yn)
    nonfinite = ~(np.isfinite(coord.spherical.lon.value) & np.isfinite(coord.spherical.lat.value))
    if outside is None:
        outside_any = bool(np.any(nonfinite))
    else:
        outside = outside | nonfinite
        outside_any = bool(np.any(outside))
    epoch = _image_epoch(w)
    if epoch is not None:
        display, source = epoch, "epoca dell'immagine (DATE-OBS/MJD-OBS)"
    else:
        display, source = Time("J2000.0"), "epoca dell'immagine non nota: visualizzazione a J2000 (D10-2)"
    defaults = [a for a in _EPOCH_ATTRIBUTES if a in coord.frame.frame_attributes and coord.frame.is_frame_attr_default(a)]
    note = (
        f"{', '.join(defaults)} del frame {coord.frame.name!r} dalle regole di default dello standard FITS WCS"
        if defaults
        else None
    )
    return SkyPositions(
        coords=SkyFrame(coord=coord, epoch=epoch, frame_defaults_note=note),
        out_of_field=outside,
        warnings=("OUT_OF_FIELD",) if outside_any else (),
        display_epoch=display,
        display_epoch_source=source,
    )


def sky_to_pixel(wcs, coords: SkyFrame, *, convention) -> PixelPositions:
    """Cielo → pixel con ``astropy.wcs``; restituisce la convenzione richiesta."""
    target = _check_convention(convention)
    if not isinstance(coords, SkyFrame):
        raise CoordinatesWcsError("COORD_UNIT_MISSING", "coords deve essere uno SkyFrame")
    w = _as_wcs(wcs)
    xn, yn = w.world_to_pixel(coords.coord)
    xn = np.asarray(xn, dtype=np.float64)
    yn = np.asarray(yn, dtype=np.float64)
    outside = _out_of_field(w, xn, yn)
    nonfinite = ~(np.isfinite(xn) & np.isfinite(yn))
    outside = nonfinite if outside is None else outside | nonfinite
    pixels = convert_pixel_convention(xn, yn, "numpy", target)
    return PixelPositions(
        pixels=pixels,
        out_of_field=outside,
        warnings=("OUT_OF_FIELD",) if np.any(outside) else (),
    )


# --------------------------------------------------------------------------
# Calibrazione astrometrica (H6; D10-1, D10-7, D10-8)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationThresholds:
    """Soglie dei controlli di D10-7 (configurabili, scritte nel risultato)."""

    min_stars_tan_stg: int = 6
    min_stars_other: int = 10
    max_rms_px: float = 1.0
    max_residual_px: float = 3.0
    coherence_factor: float = 5.0  # × RMS dei residui della soluzione TAN

    def __post_init__(self) -> None:
        if self.min_stars_tan_stg < 3 or self.min_stars_other < 3:
            raise ValueError("il minimo di stelle non può essere sotto 3")
        for name in ("max_rms_px", "max_residual_px", "coherence_factor"):
            value = getattr(self, name)
            if not (math.isfinite(value) and value > 0):
                raise ValueError(f"soglia {name} non positiva")

    def min_stars(self, projection: str) -> int:
        return self.min_stars_tan_stg if projection in ("TAN", "STG") else self.min_stars_other


@dataclass(frozen=True)
class CalibrationSolution:
    """Una soluzione astrometrica con metodo, qualità e soglie usate."""

    method: str
    wcs: WCS
    projection: str
    n_stars: int | None = None
    rms_px: float | None = None
    max_residual_px: float | None = None
    rms_arcsec: float | None = None
    max_residual_arcsec: float | None = None
    tan_rms_px: float | None = None
    center_deviation_px: float | None = None
    worst_stars: tuple[tuple[int, float], ...] = ()
    thresholds: CalibrationThresholds | None = None
    fixes: tuple[str, ...] = ()
    provenance: str = field(default=_PROVENANCE)


def _check_projection(projection: object, projection_parameters) -> dict[int, float]:
    if projection not in SUPPORTED_PROJECTIONS:
        raise CoordinatesWcsError(
            "PROJECTION_UNSUPPORTED",
            f"proiezione {projection!r} non supportata; supportate: {', '.join(SUPPORTED_PROJECTIONS)}",
        )
    params = {} if projection_parameters is None else {int(k): float(v) for k, v in projection_parameters.items()}
    if projection == "ZPN" and not params:
        raise CoordinatesWcsError(
            "PROJECTION_PARAMETERS_MISSING",
            "ZPN richiede i coefficienti PV2_m espliciti: non si adattano e non si assumono",
        )
    return params


def _template_header(projection: str, crval_deg, crpix_fits, pixel_shape, params: dict[int, float]) -> fits.Header:
    header = fits.Header()
    header["NAXIS"] = 2
    header["NAXIS1"] = int(pixel_shape[0])
    header["NAXIS2"] = int(pixel_shape[1])
    header["CTYPE1"] = f"RA---{projection}"
    header["CTYPE2"] = f"DEC--{projection}"
    header["RADESYS"] = "ICRS"
    header["CUNIT1"] = "deg"
    header["CUNIT2"] = "deg"
    header["CRVAL1"] = float(crval_deg[0])
    header["CRVAL2"] = float(crval_deg[1])
    header["CRPIX1"] = float(crpix_fits[0])
    header["CRPIX2"] = float(crpix_fits[1])
    for m, value in sorted(params.items()):
        header[f"PV2_{m}"] = value
    return header


def _check_pixel_shape(pixel_shape) -> tuple[int, int]:
    if pixel_shape is None or len(pixel_shape) != 2 or min(pixel_shape) < 1:
        raise CoordinatesWcsError("WCS_INVALID", "pixel_shape (nx, ny) obbligatorio e positivo")
    return int(pixel_shape[0]), int(pixel_shape[1])


def _calibrate_parameters(
    *, reference, reference_pixel, convention, scale, rotation, projection, east_left, pixel_shape,
    projection_parameters,
) -> CalibrationSolution:
    params = _check_projection(projection, projection_parameters)
    shape = _check_pixel_shape(pixel_shape)
    if not isinstance(reference, SkyFrame) or reference.coord.size != 1:
        raise CoordinatesWcsError("COORD_UNIT_MISSING", "reference deve essere uno SkyFrame con un solo punto")
    if not isinstance(east_left, bool):
        raise CoordinatesWcsError("WCS_INVALID", "east_left (verso dell'ascensione retta) va dichiarato: True o False")
    scale_deg = _require_angle(scale, "scala (per pixel)")
    rot_deg = _require_angle(rotation, "rotazione")
    if not scale_deg.value > 0:
        raise CoordinatesWcsError("WCS_INVALID", "scala non positiva")
    ref_icrs = reference.coord.icrs
    crpix = convert_pixel_convention(reference_pixel[0], reference_pixel[1], convention, "fits")
    header = _template_header(
        projection,
        (ref_icrs.ra.deg.item(), ref_icrs.dec.deg.item()),
        (float(crpix.x), float(crpix.y)),
        shape,
        params,
    )
    # Scala e rotazione nella forma CDELTi + CROTA2 dello standard FITS WCS (Paper II).
    header["CDELT1"] = -scale_deg.value.item() if east_left else scale_deg.value.item()
    header["CDELT2"] = scale_deg.value.item()
    header["CROTA2"] = rot_deg.value.item()
    w, fixes = _build_wcs(header)
    _check_internal_consistency(w)
    return CalibrationSolution(method="parameters", wcs=w, projection=projection, fixes=fixes)


def _residuals(w: WCS, sky: SkyCoord, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    px, py = w.world_to_pixel(sky)
    r_px = np.hypot(np.asarray(px) - x, np.asarray(py) - y)
    r_arcsec = sky.separation(w.pixel_to_world(x, y)).arcsec
    return r_px, np.asarray(r_arcsec)


def _rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))


def _worst(r_px: np.ndarray, n: int = 5) -> tuple[tuple[int, float], ...]:
    order = np.argsort(r_px)[::-1][: min(n, r_px.size)]
    return tuple((int(i), float(r_px[i])) for i in order)


def _check_coherence(
    tan_wcs: WCS, final_wcs: WCS, pixel_shape: tuple[int, int], tan_rms_px: float, factor: float
) -> float:
    """Controllo (3) di D10-7: scostamento al centro ≤ factor × RMS della TAN."""
    cx, cy = (pixel_shape[0] - 1) / 2.0, (pixel_shape[1] - 1) / 2.0
    sep = tan_wcs.pixel_to_world(cx, cy).separation(final_wcs.pixel_to_world(cx, cy))
    scale = float(np.mean(proj_plane_pixel_scales(final_wcs)))  # gradi per pixel
    deviation_px = float(sep.deg) / scale
    limit = factor * tan_rms_px
    if not np.isfinite(deviation_px) or deviation_px > limit:
        raise CoordinatesWcsError(
            "CALIB_INCONSISTENT",
            f"al centro del campo la soluzione si scosta dalla TAN di {deviation_px:.3g} pixel "
            f"(limite {factor:g} × RMS TAN = {limit:.3g} pixel)",
            center_deviation_px=deviation_px,
            limit_px=limit,
        )
    return deviation_px


def _calibrate_stars(
    *, pixel_x, pixel_y, convention, sky, projection, pixel_shape, projection_parameters, thresholds,
) -> CalibrationSolution:
    params = _check_projection(projection, projection_parameters)
    shape = _check_pixel_shape(pixel_shape)
    if not isinstance(thresholds, CalibrationThresholds):
        raise TypeError("thresholds deve essere CalibrationThresholds")
    if not isinstance(sky, SkyFrame):
        raise CoordinatesWcsError("COORD_UNIT_MISSING", "sky deve essere uno SkyFrame")
    x, y = _to_numpy_pixels(pixel_x, pixel_y, convention)
    x, y = np.atleast_1d(x), np.atleast_1d(y)
    sky_icrs = sky.coord.icrs
    n = int(x.size)
    if y.size != n or sky_icrs.size != n:
        raise CoordinatesWcsError("CALIB_TOO_FEW_STARS", "numero diverso di posizioni pixel e celesti")
    minimum = thresholds.min_stars(projection)
    if n < minimum:
        raise CoordinatesWcsError(
            "CALIB_TOO_FEW_STARS",
            f"{n} stelle date, minimo {minimum} per la proiezione {projection}",
            n_stars=n,
            minimum=minimum,
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FITSFixedWarning)
            # Avviso atteso: fit_wcs_from_points imposta CDELT = 1 su un modello
            # che ha già la matrice CD (il punto di partenza di D10-7).
            warnings.filterwarnings("ignore", message="cdelt will be ignored since cd is present")
            tan = fit_wcs_from_points((x, y), sky_icrs, projection="TAN")
            tan.pixel_shape = shape
            tan_r_px, _ = _residuals(tan, sky_icrs, x, y)
            tan_rms = _rms(tan_r_px)
            if projection == "TAN":
                final, fixes = tan, ()
            else:
                crval = (float(tan.wcs.crval[0]), float(tan.wcs.crval[1]))
                template, fixes = _build_wcs(
                    _template_header(projection, crval, tan.wcs.crpix, shape, params)
                )
                template.wcs.cd = tan.wcs.cd
                template.wcs.crpix = tan.wcs.crpix
                final = fit_wcs_from_points(
                    (x, y),
                    sky_icrs,
                    proj_point=SkyCoord(crval[0] * u.deg, crval[1] * u.deg, frame="icrs"),
                    projection=template,
                )
                final.pixel_shape = shape
    except CoordinatesWcsError:
        raise
    except Exception as exc:
        raise CoordinatesWcsError("CALIB_FIT_FAILED", f"adattamento non riuscito: {exc}") from exc
    r_px, r_arcsec = _residuals(final, sky_icrs, x, y)
    rms_px = _rms(r_px)
    max_px = float(np.max(r_px))
    worst = _worst(r_px)
    if not (np.isfinite(rms_px) and rms_px <= thresholds.max_rms_px and max_px <= thresholds.max_residual_px):
        raise CoordinatesWcsError(
            "CALIB_RESIDUALS_TOO_LARGE",
            f"RMS {rms_px:.3g} pixel (soglia {thresholds.max_rms_px:g}), massimo {max_px:.3g} pixel "
            f"(soglia {thresholds.max_residual_px:g}); stelle peggiori (indice, pixel): {worst}",
            rms_px=rms_px,
            max_residual_px=max_px,
            worst_stars=worst,
        )
    deviation = _check_coherence(tan, final, shape, tan_rms, thresholds.coherence_factor)
    return CalibrationSolution(
        method="stars",
        wcs=final,
        projection=projection,
        n_stars=n,
        rms_px=rms_px,
        max_residual_px=max_px,
        rms_arcsec=_rms(r_arcsec),
        max_residual_arcsec=float(np.max(r_arcsec)),
        tan_rms_px=tan_rms,
        center_deviation_px=deviation,
        worst_stars=worst,
        thresholds=thresholds,
        fixes=tuple(fixes),
    )


def astrometric_calibration(
    method: str,
    *,
    previous_solutions: Sequence[CalibrationSolution] = (),
    pixel_shape=None,
    header=None,
    reference: SkyFrame | None = None,
    reference_pixel=None,
    scale=None,
    rotation=None,
    east_left: bool | None = None,
    pixel_x=None,
    pixel_y=None,
    sky: SkyFrame | None = None,
    convention=None,
    projection: str | None = None,
    projection_parameters: Mapping[int, float] | None = None,
    thresholds: CalibrationThresholds | None = None,
) -> list[CalibrationSolution]:
    """Calibrazione astrometrica (H6) con uno dei tre metodi di D10-1.

    - ``"parameters"``: ``reference`` (SkyFrame), ``reference_pixel`` +
      ``convention``, ``scale`` (angolo per pixel), ``rotation`` (CROTA2),
      ``projection``, ``east_left``, ``pixel_shape``;
    - ``"stars"``: ``pixel_x``/``pixel_y`` + ``convention`` (posizioni dal
      centroide del modulo 11), ``sky`` (SkyFrame), ``projection``,
      ``pixel_shape``, ``thresholds`` (default D10-7);
    - ``"header"``: ``header``.

    Restituisce ``previous_solutions`` con la nuova soluzione in coda (il
    modulo non conserva stato; annulla/ripeti stanno nei moduli 24 e 40).
    """
    if method == "parameters":
        solution = _calibrate_parameters(
            reference=reference, reference_pixel=reference_pixel, convention=convention,
            scale=scale, rotation=rotation, projection=projection, east_left=east_left,
            pixel_shape=pixel_shape, projection_parameters=projection_parameters,
        )
    elif method == "stars":
        solution = _calibrate_stars(
            pixel_x=pixel_x, pixel_y=pixel_y, convention=convention, sky=sky, projection=projection,
            pixel_shape=pixel_shape, projection_parameters=projection_parameters,
            thresholds=CalibrationThresholds() if thresholds is None else thresholds,
        )
    elif method == "header":
        parsed = wcs_from_header(header)
        solution = CalibrationSolution(
            method="header", wcs=parsed.wcs, projection=parsed.projection, fixes=parsed.fixes
        )
    else:
        raise CoordinatesWcsError(
            "WCS_INVALID", f"metodo {method!r} non previsto; metodi: parameters, stars, header"
        )
    return [*previous_solutions, solution]


# --------------------------------------------------------------------------
# Griglia di coordinate (A6) e scelta della proiezione
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GridLine:
    """Meridiano o parallelo: valore della coordinata e tratti visibili."""

    kind: Literal["meridian", "parallel"]
    value: u.Quantity
    segments: tuple[tuple[np.ndarray, np.ndarray], ...]
    convention: PixelConvention = "numpy"


@dataclass(frozen=True)
class GridLines:
    """Geometria della griglia (il disegno è del modulo 41)."""

    frame_name: str
    equinox: Time | None
    lon_spacing: u.Quantity
    lat_spacing: u.Quantity
    samples_per_line: int
    lines: tuple[GridLine, ...]
    provenance: str = _PROVENANCE


def _check_spacing(value, what: str) -> float:
    if not isinstance(value, u.Quantity) or not value.unit.is_equivalent(u.deg):
        raise CoordinatesWcsError("GRID_SPACING_INVALID", f"{what} senza unità angolare")
    deg = float(value.to_value(u.deg))
    if not (math.isfinite(deg) and 0 < deg <= 360):
        raise CoordinatesWcsError("GRID_SPACING_INVALID", f"{what} deve essere in (0°, 360°]")
    return deg


def _segments(x: np.ndarray, y: np.ndarray, nx: int, ny: int) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    inside = np.isfinite(x) & np.isfinite(y) & (x >= -0.5) & (x <= nx - 0.5) & (y >= -0.5) & (y <= ny - 0.5)
    segments = []
    start = None
    for i, flag in enumerate(np.append(inside, False)):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            if i - start >= 2:
                segments.append((x[start:i].copy(), y[start:i].copy()))
            start = None
    return tuple(segments)


@dataclass(frozen=True)
class _FieldExtent:
    lon0: float  # longitudine del pixel più vicino al centro (gradi)
    rel_min: float  # longitudini relative a lon0, in (-180, 180]
    rel_max: float
    lat_min: float
    lat_max: float
    north_pole_inside: bool
    south_pole_inside: bool

    @property
    def full_lon(self) -> bool:
        return self.north_pole_inside or self.south_pole_inside

    @property
    def lon_extent(self) -> float:
        return 360.0 if self.full_lon else self.rel_max - self.rel_min

    @property
    def lat_extent(self) -> float:
        return self.lat_max - self.lat_min


def _field_extent(w: WCS, nx: int, ny: int, target: BaseCoordinateFrame) -> _FieldExtent:
    """Estensione del campo nel frame della griglia, da un campionamento dei pixel."""
    gx, gy = np.meshgrid(np.linspace(-0.5, nx - 0.5, 65), np.linspace(-0.5, ny - 0.5, 65))
    sky = w.pixel_to_world(gx.ravel(), gy.ravel()).transform_to(target)
    lon = sky.spherical.lon.deg
    lat = sky.spherical.lat.deg
    ok = np.isfinite(lon) & np.isfinite(lat)
    if not np.any(ok):
        raise CoordinatesWcsError("WCS_INVALID", "nessun pixel dell'immagine ha coordinate celesti valide")
    lon, lat = lon[ok], lat[ok]
    poles = SkyCoord([0.0, 0.0] * u.deg, [90.0, -90.0] * u.deg, frame=target)
    px, py = w.world_to_pixel(poles)
    inside = np.isfinite(px) & np.isfinite(py) & (px >= -0.5) & (px <= nx - 0.5) & (py >= -0.5) & (py <= ny - 0.5)
    lon0 = float(lon[np.argmin(np.hypot(gx.ravel()[ok] - (nx - 1) / 2, gy.ravel()[ok] - (ny - 1) / 2))])
    rel = (lon - lon0 + 180.0) % 360.0 - 180.0
    return _FieldExtent(
        lon0=lon0,
        rel_min=float(rel.min()),
        rel_max=float(rel.max()),
        lat_min=-90.0 if inside[1] else float(lat.min()),
        lat_max=90.0 if inside[0] else float(lat.max()),
        north_pole_inside=bool(inside[0]),
        south_pole_inside=bool(inside[1]),
    )


def _round_steps(values, unit) -> tuple[u.Quantity, ...]:
    return tuple((v * unit).to(u.deg) for v in values)


#: Valori "tondi" in arco (latitudini; longitudini dei frame non equatoriali), §9.
GRID_STEPS_ARC: tuple[u.Quantity, ...] = (
    _round_steps((0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30), u.arcsec)
    + _round_steps((1, 2, 5, 10, 15, 30), u.arcmin)
    + _round_steps((1, 2, 5, 10, 15, 30, 45, 90), u.deg)
)

#: Valori "tondi" in tempo per l'ascensione retta dei frame equatoriali, §9.
GRID_STEPS_TIME: tuple[u.Quantity, ...] = (
    _round_steps((0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30), u.hourangle / 3600)
    + _round_steps((1, 2, 5, 10, 15, 30), u.hourangle / 60)
    + _round_steps((1, 2, 3, 4, 6), u.hourangle)
)


@dataclass(frozen=True)
class GridSpacing:
    """Passi della griglia scelti in automatico, con le misure che li motivano."""

    frame_name: str
    lon_spacing: u.Quantity
    lat_spacing: u.Quantity
    lon_extent: u.Quantity
    lat_extent: u.Quantity
    target_lines: int
    lon_steps: Literal["time", "arc"]
    provenance: str = _PROVENANCE


def _pick_step(extent_deg: float, target_lines: int, steps: tuple[u.Quantity, ...]) -> u.Quantity:
    wanted = extent_deg / target_lines
    for step in steps:
        if step.to_value(u.deg) >= wanted:
            return step
    return steps[-1]


def choose_grid_spacing(
    wcs,
    *,
    frame: str,
    pixel_shape=None,
    equinox=None,
    obstime=None,
    target_lines: int = 5,
) -> GridSpacing:
    """Passo automatico della griglia in base al campo visibile (come Aladin).

    Per ogni asse: il più piccolo valore tondo ≥ estensione / ``target_lines``
    (elenchi :data:`GRID_STEPS_TIME` per l'ascensione retta dei frame
    equatoriali, :data:`GRID_STEPS_ARC` per tutto il resto).
    """
    if isinstance(target_lines, bool) or not isinstance(target_lines, int) or target_lines < 1:
        raise CoordinatesWcsError("GRID_SPACING_INVALID", "target_lines deve essere un intero ≥ 1")
    w = _as_wcs(wcs)
    shape = pixel_shape if pixel_shape is not None else w.pixel_shape
    nx, ny = _check_pixel_shape(shape)
    target = _frame_instance(frame, equinox=equinox, obstime=obstime)
    extent = _field_extent(w, nx, ny, target)
    equatorial = "ra" in target.representation_component_names
    lon_steps = GRID_STEPS_TIME if equatorial else GRID_STEPS_ARC
    return GridSpacing(
        frame_name=target.name,
        lon_spacing=_pick_step(extent.lon_extent, target_lines, lon_steps),
        lat_spacing=_pick_step(extent.lat_extent, target_lines, GRID_STEPS_ARC),
        lon_extent=extent.lon_extent * u.deg,
        lat_extent=extent.lat_extent * u.deg,
        target_lines=target_lines,
        lon_steps="time" if equatorial else "arc",
    )


def compute_grid_lines(
    wcs,
    *,
    frame: str,
    lon_spacing=None,
    lat_spacing=None,
    pixel_shape=None,
    equinox=None,
    obstime=None,
    samples_per_line: int = 200,
) -> GridLines:
    """Meridiani e paralleli del frame richiesto visibili nell'immagine.

    I tratti sono coordinate pixel in convenzione numpy dentro l'immagine;
    ogni punto sta esattamente sulla linea (calcolato con ``astropy.wcs``).
    Se i due passi sono omessi li sceglie :func:`choose_grid_spacing`.
    """
    w = _as_wcs(wcs)
    shape = pixel_shape if pixel_shape is not None else w.pixel_shape
    nx, ny = _check_pixel_shape(shape)
    if lon_spacing is None and lat_spacing is None:
        auto = choose_grid_spacing(w, frame=frame, pixel_shape=(nx, ny), equinox=equinox, obstime=obstime)
        lon_spacing, lat_spacing = auto.lon_spacing, auto.lat_spacing
    elif lon_spacing is None or lat_spacing is None:
        raise CoordinatesWcsError(
            "GRID_SPACING_INVALID", "dare entrambi i passi oppure nessuno (scelta automatica)"
        )
    dlon = _check_spacing(lon_spacing, "passo in longitudine")
    dlat = _check_spacing(lat_spacing, "passo in latitudine")
    if samples_per_line < 2:
        raise CoordinatesWcsError("GRID_SPACING_INVALID", "servono almeno 2 campioni per linea")
    target = _frame_instance(frame, equinox=equinox, obstime=obstime)

    extent = _field_extent(w, nx, ny, target)
    lat_min = -90.0 if extent.south_pole_inside else max(-90.0, extent.lat_min - dlat)
    lat_max = 90.0 if extent.north_pole_inside else min(90.0, extent.lat_max + dlat)
    full_lon = extent.full_lon or extent.rel_max - extent.rel_min + 2 * dlon >= 360.0
    if full_lon:
        lon_start, lon_stop = 0.0, 360.0
    else:
        lon_start = extent.lon0 + extent.rel_min - dlon
        lon_stop = extent.lon0 + extent.rel_max + dlon

    def to_pixels(lons: np.ndarray, lats: np.ndarray):
        coords = SkyCoord(lons * u.deg, lats * u.deg, frame=target)
        xs, ys = w.world_to_pixel(coords)
        return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)

    lines: list[GridLine] = []
    k0, k1 = math.ceil(lon_start / dlon - 1e-12), math.floor(lon_stop / dlon + 1e-12)
    meridians = sorted({round((k * dlon) % 360.0, 12) for k in range(k0, k1 + 1)})
    lats = np.linspace(lat_min, lat_max, samples_per_line)
    for value in meridians:
        xs, ys = to_pixels(np.full(lats.shape, value), lats)
        segs = _segments(xs, ys, nx, ny)
        if segs:
            lines.append(GridLine("meridian", value * u.deg, segs))
    lons = np.linspace(lon_start, lon_stop, samples_per_line) % 360.0
    k0, k1 = math.ceil(lat_min / dlat - 1e-12), math.floor(lat_max / dlat + 1e-12)
    for k in range(k0, k1 + 1):
        value = k * dlat
        if abs(value) >= 90.0:
            continue
        xs, ys = to_pixels(lons, np.full(lons.shape, value))
        segs = _segments(xs, ys, nx, ny)
        if segs:
            lines.append(GridLine("parallel", value * u.deg, segs))
    return GridLines(
        frame_name=target.name,
        equinox=getattr(target, "equinox", None),
        lon_spacing=dlon * u.deg,
        lat_spacing=dlat * u.deg,
        samples_per_line=samples_per_line,
        lines=tuple(lines),
    )


def choose_projection(field_of_view, *, threshold) -> str:
    """``TAN`` se il campo di vista è minore della soglia, ``AIT`` altrimenti.

    La soglia è obbligatoria finché la decisione D10-9 non ne fissa il valore.
    """
    fov = _require_angle(field_of_view, "campo di vista")
    limit = _require_angle(threshold, "soglia")
    if not (np.isfinite(fov.value) and fov.value > 0 and np.isfinite(limit.value) and limit.value > 0):
        raise CoordinatesWcsError("COORD_OUT_OF_RANGE", "campo di vista e soglia devono essere positivi")
    return "TAN" if fov < limit else "AIT"
