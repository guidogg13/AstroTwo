# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Misure angolari e strumenti di misura.

Specifica: ``mdfiles/17-core-misure.md`` (stato ``approvato``).

Il modulo si scrive in 4 parti (decisione del proprietario del 2026-10-12):
P1 misure angolari (distanza, angolo di posizione, offset e calcolo inverso),
P2 lettura dei pixel e profili, P3 forme e tag (D17-7: poligoni con
``spherical-geometry``, ellisse sferica, cerchio con Astropy; ``distance_to``
con D17-8 e D17-9: freccia e tracciato aperto come archi di cerchio massimo,
ellisse con il minimo numerico sul bordo e precisione dichiarata, testo
escluso), P4 distanza automatica tra due sorgenti di catalogo.

Regole applicate in tutto il modulo:

- ogni numero viene da ``astropy`` (distanza: ``skydist`` del 13, unica
  implementazione, D13-10), da ``numpy``/``scipy`` per i pixel, mai da
  formule scritte qui;
- le misure sono nel frame del primo punto; un secondo punto in un altro
  frame si converte con il modulo 10 e la conversione è scritta nel report;
- nessuna misura senza unità e, per le misure celesti, senza frame; ogni
  risultato porta il suo :class:`MeasureReport`;
- questo modulo non disegna e non scrive su disco (41, 24).
"""

from __future__ import annotations

import importlib.metadata
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

import astropy
import astropy.units as u
import numpy as np
import scipy
from astropy.coordinates import Angle, SkyCoord, offset_by
from astropy.coordinates import position_angle as astropy_position_angle
from astropy.table import Table
from astropy.time import Time
from scipy.ndimage import map_coordinates
from scipy.optimize import brentq, minimize, minimize_scalar
from spherical_geometry import great_circle_arc as sg_arc
from spherical_geometry import vector as sg_vector
from spherical_geometry.polygon import SphericalPolygon

from astrotwo.core import catalogs
from astrotwo.core.catalogs import CatalogsError, CatalogTable, skydist
from astrotwo.core.coordinates_wcs import (
    CoordinatesWcsError,
    PixelPosition,
    SkyFrame,
    _to_epoch,
    convert_coordinates,
    convert_pixel_convention,
    pixel_to_sky,
    sky_to_pixel,
)
from astrotwo.core.images_fits import ImagesFitsError, LargeImageLimits

__all__ = [
    "DISTANCE_UNITS",
    "UNDECLARED_UNIT",
    "MeasuresError",
    "MeasureReport",
    "Segment",
    "AngularDistance",
    "PositionAngle",
    "AngularOffsets",
    "OffsetPosition",
    "angular_distance",
    "position_angle",
    "angular_offsets",
    "apply_offsets",
    "offset_position",
    "PixelReading",
    "Profile",
    "DistanceWithProfile",
    "read_pixel",
    "profile_along_line",
    "distance_with_profile",
    "ELLIPSE_DEFINITION",
    "ELLIPSE_DISTANCE_ATOL",
    "ShapeMeasure",
    "Shape",
    "Circle",
    "Ellipse",
    "Polygon",
    "Freehand",
    "Arrow",
    "Text",
    "Tag",
    "tag",
    "CatalogSource",
    "AutoDistance",
    "auto_distance",
]

_PROVENANCE = f"astropy {astropy.__version__}"

#: Unità di uscita ammesse per le distanze angolari (§6).
DISTANCE_UNITS: dict[str, u.UnitBase] = {"arcsec": u.arcsec, "arcmin": u.arcmin, "deg": u.deg, "degree": u.deg}


# --------------------------------------------------------------------------
# Errori e report
# --------------------------------------------------------------------------


class MeasuresError(Exception):
    """Errore del modulo 17 con identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


@dataclass(frozen=True)
class MeasureReport:
    """Report di una misura (§9): punti, unità, frame, immagine, data, passaggi e avvisi."""

    operation: str
    points: tuple[str, ...]
    frame: str | None
    unit: str
    image: str | None = None
    notes: tuple[str, ...] = ()
    warnings: tuple[tuple[str, str], ...] = ()
    measured_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    provenance: str = _PROVENANCE

    @property
    def description(self) -> str:
        lines = [f"{self.operation} ({self.measured_at.isoformat()}, {self.provenance})",
                 f"frame: {self.frame or 'pixel space'}; unità: {self.unit}"]
        if self.image is not None:
            lines.append(f"immagine: {self.image}")
        lines.extend(f"punto: {p}" for p in self.points)
        lines.extend(f"nota: {n}" for n in self.notes)
        lines.extend(f"avviso {code}: {text}" for code, text in self.warnings)
        return "\n".join(lines)


def _describe(point: SkyFrame) -> str:
    epoch = "non nota" if point.epoch is None else f"{point.epoch.jyear_str} ({point.epoch.scale})"
    attrs = []
    if point.equinox is not None:
        attrs.append(f"equinozio {point.equinox}")
    if point.obstime is not None:
        attrs.append(f"obstime {point.obstime.isot} ({point.obstime.scale})")
    extra = f", {', '.join(attrs)}" if attrs else ""
    return (f"{point.frame_name} ({point.lon.to_value(u.deg)!r}°, {point.lat.to_value(u.deg)!r}°){extra}, "
            f"epoca delle posizioni {epoch}")


# --------------------------------------------------------------------------
# Punti, frame e linee
# --------------------------------------------------------------------------


def _from_10(exc: CoordinatesWcsError, what: str) -> MeasuresError:
    return MeasuresError(exc.code, f"{what}: {exc.message}")


def _as_point(value: object, what: str) -> SkyFrame:
    """Un punto celeste come ``SkyFrame`` del 10; numeri senza frame → ``FRAME_UNKNOWN``."""
    if isinstance(value, SkyCoord):
        try:
            value = SkyFrame(coord=value)
        except CoordinatesWcsError as exc:
            raise _from_10(exc, what) from exc
    if not isinstance(value, SkyFrame):
        raise MeasuresError("FRAME_UNKNOWN", f"{what}: serve uno SkyFrame (modulo 10) o uno SkyCoord con il frame, "
                            f"non {type(value).__name__}: il frame non si assume")
    if value.coord.size != 1:
        raise ValueError(f"{what}: un solo punto per misura, non {value.coord.size}")
    if not value.coord.isscalar:
        value = SkyFrame(coord=value.coord.reshape(()), epoch=value.epoch, provenance=value.provenance,
                         frame_defaults_note=value.frame_defaults_note)
    return value


def _in_frame_of(first: SkyFrame, other: SkyFrame, what: str) -> tuple[SkyFrame, tuple[str, ...]]:
    """``other`` nel frame di ``first`` (modulo 10), con la nota della conversione."""
    if first.coord.frame.is_equivalent_frame(other.coord.frame):
        return other, ()
    try:
        converted = convert_coordinates(other, first.frame_name, equinox=first.equinox, obstime=first.obstime)
    except CoordinatesWcsError as exc:
        raise _from_10(exc, what) from exc
    note = f"{what} convertito da {other.frame_name} a {first.frame_name} con il modulo 10 (convert_coordinates)"
    return converted, (note,)


def _epoch_notes(points: tuple[SkyFrame, ...]) -> tuple[str, ...]:
    epochs = {p.epoch.jyear_str if p.epoch is not None else None for p in points}
    if len(epochs) > 1:
        return ("epoche delle posizioni diverse tra i punti (scritte sopra): nessuna propagazione in questa misura",)
    return ()


@dataclass(frozen=True)
class Segment:
    """Linea tra due punti (PA lungo una linea, profilo, estremi della distanza automatica)."""

    start: object
    end: object


def _pair(p1, p2) -> tuple[object, object]:
    if isinstance(p1, Segment):
        if p2 is not None:
            raise TypeError("con un Segment non si passa il secondo punto")
        return p1.start, p1.end
    if p2 is None:
        raise TypeError("servono due punti o un Segment")
    return p1, p2


def _points(p1, p2) -> tuple[SkyFrame, SkyFrame, tuple[str, ...]]:
    a = _as_point(p1, "p1")
    b, notes = _in_frame_of(a, _as_point(p2, "p2"), "p2")
    return a, b, notes + _epoch_notes((a, b))


def _separation_deg(a: SkyFrame, b: SkyFrame) -> float:
    """Separazione in gradi con ``skydist`` del 13 (implementazione unica, D13-10)."""
    return float(skydist(a.lon, a.lat, b.lon, b.lat))


# --------------------------------------------------------------------------
# P1 — distanza, angolo di posizione, offset e calcolo inverso
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AngularDistance:
    """Distanza angolare (F1) nel frame del primo punto."""

    value: u.Quantity
    p1: SkyFrame
    p2: SkyFrame  # nel frame del primo punto
    report: MeasureReport


@dataclass(frozen=True)
class PositionAngle:
    """Angolo di posizione (F2) da nord verso est, in [0°, 360°), nel frame del primo punto."""

    value: Angle
    p1: SkyFrame
    p2: SkyFrame
    report: MeasureReport


@dataclass(frozen=True)
class AngularOffsets:
    """Offset Δα·cos δ e Δδ da ``p1`` a ``p2`` nel frame di ``p1``."""

    d_lon: u.Quantity
    d_lat: u.Quantity
    p1: SkyFrame
    p2: SkyFrame
    report: MeasureReport


@dataclass(frozen=True)
class OffsetPosition:
    """Posizione calcolata da un punto di partenza (offset o distanza + angolo di posizione)."""

    position: SkyFrame
    start: SkyFrame
    report: MeasureReport


def _distance_unit(unit: object) -> u.UnitBase:
    if isinstance(unit, str) and unit in DISTANCE_UNITS:
        return DISTANCE_UNITS[unit]
    if isinstance(unit, u.UnitBase) and any(unit == v for v in DISTANCE_UNITS.values()):
        return unit
    raise ValueError(f"unità {unit!r} non ammessa: {', '.join(DISTANCE_UNITS)}")


def angular_distance(p1, p2, unit) -> AngularDistance:
    """Separazione angolare (F1) con ``skydist`` del 13, nell'unità richiesta (obbligatoria)."""
    target = _distance_unit(unit)
    a, b, notes = _points(p1, p2)
    value = (np.float64(_separation_deg(a, b)) * u.deg).to(target)
    report = MeasureReport(
        operation="angular_distance", points=(_describe(a), _describe(b)), frame=a.frame_name,
        unit=target.to_string(), notes=notes + ("calcolo: skydist del modulo 13 (astropy angular_separation)",))
    return AngularDistance(value=value, p1=a, p2=b, report=report)


def position_angle(p1, p2=None) -> PositionAngle:
    """Angolo di posizione da nord verso est (F2) tra due punti o lungo un ``Segment``.

    Casi in cui la direzione non è definita (controlli esatti, prima di Astropy, che darebbe comunque un
    numero): punti coincidenti, punti antipodali, primo punto al polo → ``PA_UNDEFINED``.
    """
    first, second = _pair(p1, p2)
    a, b, notes = _points(first, second)
    separation = _separation_deg(a, b)
    if separation == 0.0:
        raise MeasuresError("PA_UNDEFINED", "punti coincidenti: direzione non definita")
    if separation == 180.0:
        raise MeasuresError("PA_UNDEFINED", "punti antipodali: ogni direzione porta al secondo punto")
    if abs(a.lat.to_value(u.deg)) == 90.0:
        raise MeasuresError("PA_UNDEFINED", "primo punto al polo: il nord locale non è definito")
    value = Angle(a.coord.position_angle(b.coord)).to(u.deg).wrap_at(360 * u.deg)
    report = MeasureReport(
        operation="position_angle", points=(_describe(a), _describe(b)), frame=a.frame_name, unit="deg",
        notes=notes + ("da nord verso est; calcolo: SkyCoord.position_angle (astropy)",)
        + (("misura lungo un segmento",) if isinstance(p1, Segment) else ()))
    return PositionAngle(value=value, p1=a, p2=b, report=report)


def angular_offsets(p1, p2) -> AngularOffsets:
    """Offset Δα·cos δ e Δδ da ``p1`` a ``p2`` nel frame di ``p1`` (``SkyCoord.spherical_offsets_to``)."""
    a, b, notes = _points(p1, p2)
    d_lon, d_lat = a.coord.spherical_offsets_to(b.coord)
    report = MeasureReport(
        operation="angular_offsets", points=(_describe(a), _describe(b)), frame=a.frame_name, unit="deg",
        notes=notes + ("offset sferici nel frame del primo punto; calcolo: SkyCoord.spherical_offsets_to",))
    return AngularOffsets(d_lon=d_lon.to(u.deg), d_lat=d_lat.to(u.deg), p1=a, p2=b, report=report)


def _offset_angle(value: object, what: str) -> u.Quantity:
    if not isinstance(value, u.Quantity) or not value.unit.is_equivalent(u.deg):
        raise MeasuresError("OFFSET_INVALID", f"{what}: serve un angolo con unità, non {value!r}")
    if value.size != 1 or not np.isfinite(value.value):
        raise MeasuresError("OFFSET_INVALID", f"{what}: un solo valore finito, non {value!r}")
    return value.to(u.deg).astype(np.float64)


def _moved(start: SkyFrame, coord: SkyCoord) -> SkyFrame:
    return SkyFrame(coord=coord, epoch=start.epoch, frame_defaults_note=start.frame_defaults_note)


def apply_offsets(p, d_lon, d_lat) -> OffsetPosition:
    """Posizione ottenuta applicando a ``p`` gli offset Δα·cos δ e Δδ (``SkyCoord.spherical_offsets_by``)."""
    start = _as_point(p, "p")
    dl, db = _offset_angle(d_lon, "d_lon"), _offset_angle(d_lat, "d_lat")
    coord = start.coord.spherical_offsets_by(dl, db)
    report = MeasureReport(
        operation="apply_offsets", points=(_describe(start),), frame=start.frame_name, unit="deg",
        notes=(f"offset Δα·cos δ = {dl.value!r}°, Δδ = {db.value!r}°; calcolo: SkyCoord.spherical_offsets_by",
               "posizione nel frame e all'epoca del punto di partenza"))
    return OffsetPosition(position=_moved(start, coord), start=start, report=report)


def offset_position(p, distance, position_angle) -> OffsetPosition:
    """Calcolo inverso: posizione a ``distance`` e ``position_angle`` (nord → est) da ``p``."""
    start = _as_point(p, "p")
    d = _offset_angle(distance, "distance")
    pa = _offset_angle(position_angle, "position_angle")
    if d.value < 0.0 or d.value > 180.0:
        raise MeasuresError("OFFSET_INVALID", f"distance {d!r}: serve un valore in [0°, 180°]")
    coord = start.coord.directional_offset_by(pa, d)
    report = MeasureReport(
        operation="offset_position", points=(_describe(start),), frame=start.frame_name, unit="deg",
        notes=(f"distanza {d.value!r}°, angolo di posizione {pa.value!r}° (nord → est); "
               "calcolo: SkyCoord.directional_offset_by", "posizione nel frame e all'epoca del punto di partenza"))
    return OffsetPosition(position=_moved(start, coord), start=start, report=report)


# --------------------------------------------------------------------------
# P2 — lettura dei pixel, profili, distanza con profilo (D17-5)
# --------------------------------------------------------------------------

_PIXEL_PROVENANCE = f"{_PROVENANCE}, numpy {np.__version__}, scipy {scipy.__version__}"
#: Byte per campione del profilo: x, y, offset, valore e coordinate di lavoro in ``float64``.
_SAMPLE_BYTES = 6 * 8


def _from_11(exc: ImagesFitsError, what: str) -> MeasuresError:
    return MeasuresError(exc.code, f"{what}: {exc.message}")


def _image_name(image) -> str:
    return f"{image.source} (HDU {image.hdu_index})"


#: Etichetta dell'unità di un'immagine senza ``BUNIT``: l'unità non è nota, non "adimensionale".
UNDECLARED_UNIT = "non dichiarata"


def _unit_label(image) -> str:
    return image.bunit if image.bunit else UNDECLARED_UNIT


def _pixel_xy(image, position, what: str) -> tuple[float, float, SkyFrame | None, tuple[str, ...]]:
    """Posizione in pixel (convenzione numpy) da un punto celeste (con il WCS) o da una ``PixelPosition``."""
    if isinstance(position, PixelPosition):
        pos = convert_pixel_convention(position.x, position.y, position.convention, "numpy")
        if pos.x.size != 1 or pos.y.size != 1:
            raise ValueError(f"{what}: un solo punto per misura")
        x, y = float(pos.x.ravel()[0]), float(pos.y.ravel()[0])
        if not (np.isfinite(x) and np.isfinite(y)):
            raise MeasuresError("POINT_OUT_OF_IMAGE", f"{what}: posizione non finita")
        note = f"{what}: pixel dati in convenzione {position.convention}" + (
            ", convertiti in numpy con convert_pixel_convention (modulo 10)" if position.convention != "numpy" else "")
        return x, y, None, (note,)
    if isinstance(position, (SkyFrame, SkyCoord)):
        point = _as_point(position, what)
        if image.wcs is None:
            raise MeasuresError("NO_WCS", f"{what}: l'immagine non ha WCS; dare la posizione in pixel "
                                "(PixelPosition) o calibrare l'immagine")
        try:
            pixels = sky_to_pixel(image.wcs, point, convention="numpy").pixels
        except CoordinatesWcsError as exc:
            raise _from_10(exc, what) from exc
        x, y = float(np.ravel(pixels.x)[0]), float(np.ravel(pixels.y)[0])
        if not (np.isfinite(x) and np.isfinite(y)):
            raise MeasuresError("POINT_OUT_OF_IMAGE", f"{what}: posizione fuori dal dominio del WCS")
        return x, y, point, (f"{what}: {_describe(point)} → pixel con sky_to_pixel (modulo 10)",)
    raise TypeError(f"{what}: serve un punto celeste (SkyFrame/SkyCoord) o una PixelPosition con la convenzione")


def _bbox_error(what: str, x: float, y: float, nx: int, ny: int, allowed: str) -> MeasuresError:
    return MeasuresError("POINT_OUT_OF_IMAGE", f"{what}: pixel ({x!r}, {y!r}) (numpy) fuori da {allowed} "
                         f"dell'immagine {nx}×{ny}", bbox=((0, nx - 1), (0, ny - 1)), position=(x, y))


def _region(image, x0: int, x1: int, y0: int, y1: int) -> np.ndarray:
    try:
        return np.asarray(image.read_region(x0, x1, y0, y1), dtype=np.float64)
    except ImagesFitsError as exc:
        raise _from_11(exc, "lettura dei pixel") from exc


@dataclass(frozen=True, eq=False)
class PixelReading:
    """Valore di un pixel (F3) letto dai pixel originali, in ``float64``, mai modificato."""

    value: np.float64
    window: np.ndarray  # (2·half_size + 1)², centrata sul pixel; 1×1 con half_size = 0
    x: int  # colonna (numpy, indice da 0)
    y: int  # riga (numpy, indice da 0)
    position: PixelPosition  # posizione richiesta, in convenzione numpy
    sky: SkyFrame | None  # punto celeste richiesto (None: richiesta in pixel, "pixel space")
    bunit: str | None
    unit: u.UnitBase | None
    unit_label: str  # BUNIT come scritta, o "non dichiarata" (UNDECLARED_UNIT)
    report: MeasureReport


def read_pixel(image, position, *, half_size: int = 0) -> PixelReading:
    """Valore del pixel che contiene ``position`` (indice ``floor(x + 0,5)``) e, con ``half_size``, i vicini."""
    if isinstance(half_size, bool) or not isinstance(half_size, (int, np.integer)) or half_size < 0:
        raise ValueError(f"half_size {half_size!r}: serve un intero ≥ 0")
    x, y, sky, notes = _pixel_xy(image, position, "position")
    ny, nx = image.shape
    if not (-0.5 <= x < nx - 0.5 and -0.5 <= y < ny - 0.5):
        raise _bbox_error("position", x, y, nx, ny, "[−0,5, n − 0,5)")
    ix, iy = int(np.floor(x + 0.5)), int(np.floor(y + 0.5))
    h = int(half_size)
    if ix - h < 0 or iy - h < 0 or ix + h > nx - 1 or iy + h > ny - 1:
        raise MeasuresError("POINT_OUT_OF_IMAGE", f"finestra di {2 * h + 1}×{2 * h + 1} pixel attorno a "
                            f"({ix}, {iy}) fuori dall'immagine {nx}×{ny}", bbox=((0, nx - 1), (0, ny - 1)))
    window = _region(image, ix - h, ix + h + 1, iy - h, iy + h + 1)
    value = np.float64(window[h, h])
    warnings_ = []
    if not np.all(np.isfinite(window)):
        warnings_.append(("NONFINITE_PIXELS", f"{int(np.count_nonzero(~np.isfinite(window)))} valori non finiti "
                          "restituiti come tali, mai sostituiti"))
    report = MeasureReport(
        operation="read_pixel", points=(f"pixel ({ix}, {iy}) numpy da ({x!r}, {y!r})",),
        frame=None if sky is None else sky.frame_name, unit=_unit_label(image), image=_image_name(image),
        notes=notes + (f"finestra half_size = {h}; pixel originali (read_region del modulo 11) in float64",),
        warnings=tuple(warnings_), provenance=_PIXEL_PROVENANCE)
    return PixelReading(value=value, window=window, x=ix, y=iy,
                        position=PixelPosition(x=np.float64(x), y=np.float64(y), convention="numpy"), sky=sky,
                        bunit=image.bunit, unit=image.unit, unit_label=_unit_label(image), report=report)


def _step_pixels(step: object) -> float:
    if isinstance(step, u.Quantity):
        if step.unit != u.pix or step.size != 1:
            raise MeasuresError("PROFILE_STEP_INVALID", f"passo {step!r}: serve un valore in pixel (u.pix)")
        value = float(step.value)
    elif isinstance(step, (int, float, np.integer, np.floating)) and not isinstance(step, bool):
        value = float(step)
    else:
        raise MeasuresError("PROFILE_STEP_INVALID", f"passo {step!r}: serve un numero di pixel (obbligatorio, D17-5)")
    if not np.isfinite(value) or value <= 0.0:
        raise MeasuresError("PROFILE_STEP_INVALID", f"passo {value!r}: serve un valore finito > 0")
    return value


@dataclass(frozen=True, eq=False)
class Profile:
    """Profilo di intensità lungo un segmento in pixel (D17-5: bilineare, passo dichiarato)."""

    offsets: u.Quantity  # distanza di ogni campione dal primo estremo, in pixel
    x: np.ndarray  # convenzione numpy
    y: np.ndarray
    values: np.ndarray  # float64; NaN se un vicino non è finito
    sky: SkyFrame | None  # posizione celeste dei campioni (immagine con WCS)
    step: u.Quantity
    start: PixelPosition
    end: PixelPosition
    bunit: str | None
    unit: u.UnitBase | None
    unit_label: str
    report: MeasureReport

    def to_table(self) -> Table:
        """Tabella esportabile (D17-6): offset, x, y (numpy), valore e, con il WCS, posizione celeste."""
        table = Table()
        table["offset"] = self.offsets
        table["x"] = self.x
        table["y"] = self.y
        table["value"] = self.values * self.unit if self.unit is not None else self.values
        if self.sky is not None:
            table[f"lon_{self.sky.frame_name}"] = self.sky.lon
            table[f"lat_{self.sky.frame_name}"] = self.sky.lat
        table.meta.update({"pixel_convention": "numpy", "unit": self.unit_label, "step_pix": float(self.step.value),
                           "interpolation": "bilinear (scipy.ndimage.map_coordinates, order=1)",
                           "report": self.report.description})
        return table


def _profile(image, x1, y1, x2, y2, step, notes, frame) -> Profile:
    ny, nx = image.shape
    for what, (x, y) in (("p1", (x1, y1)), ("p2", (x2, y2))):
        if not (0.0 <= x <= nx - 1 and 0.0 <= y <= ny - 1):
            raise _bbox_error(what, x, y, nx, ny, "[0, n − 1] (centri dei pixel del bordo)")
    length = float(np.hypot(x2 - x1, y2 - y1))
    n = int(np.floor(length / step)) + 1
    bx0, bx1 = int(np.floor(min(x1, x2))), min(int(np.ceil(max(x1, x2))) + 1, nx)
    by0, by1 = int(np.floor(min(y1, y2))), min(int(np.ceil(max(y1, y2))) + 1, ny)
    limits = image.limits if isinstance(getattr(image, "limits", None), LargeImageLimits) else LargeImageLimits()
    needed = n * _SAMPLE_BYTES + (bx1 - bx0) * (by1 - by0) * 8
    if needed > limits.operation_bytes:
        raise MeasuresError("MEMORY_LIMIT_EXCEEDED", f"profilo di {n} campioni e regione di {bx1 - bx0}×{by1 - by0} "
                            f"pixel: {needed} byte oltre il limite delle operazioni ({limits.operation_bytes})")
    region = _region(image, bx0, bx1, by0, by1)
    offsets = np.arange(n, dtype=np.float64) * step
    fraction = offsets / length if length > 0 else np.zeros(n)
    xs, ys = x1 + (x2 - x1) * fraction, y1 + (y2 - y1) * fraction
    values = map_coordinates(region, np.vstack([ys - by0, xs - bx0]), order=1, prefilter=False, mode="constant",
                             cval=np.nan, output=np.float64)
    warnings_ = []
    if not np.all(np.isfinite(values)):
        warnings_.append(("NONFINITE_PIXELS", f"{int(np.count_nonzero(~np.isfinite(values)))} campioni con un vicino "
                          "non finito: NaN, mai sostituiti"))
    sky = None
    if image.wcs is not None:
        try:
            sky = pixel_to_sky(image.wcs, xs, ys, convention="numpy").coords
        except CoordinatesWcsError as exc:
            raise _from_10(exc, "posizioni celesti dei campioni") from exc
    report = MeasureReport(
        operation="profile_along_line",
        points=(f"pixel ({x1!r}, {y1!r}) numpy", f"pixel ({x2!r}, {y2!r}) numpy"), frame=frame,
        unit=_unit_label(image), image=_image_name(image),
        notes=notes + (f"segmento rettilineo in pixel di lunghezza {length!r}; passo {step!r} pixel; {n} campioni "
                       "a k·passo dal primo estremo", "interpolazione bilineare: scipy.ndimage.map_coordinates "
                       "(order=1, prefilter=False) sui pixel originali (D17-5)"),
        warnings=tuple(warnings_), provenance=_PIXEL_PROVENANCE)
    return Profile(offsets=offsets * u.pix, x=xs, y=ys, values=values, sky=sky, step=step * u.pix,
                   start=PixelPosition(x=np.float64(x1), y=np.float64(y1), convention="numpy"),
                   end=PixelPosition(x=np.float64(x2), y=np.float64(y2), convention="numpy"), bunit=image.bunit,
                   unit=image.unit, unit_label=_unit_label(image), report=report)


def _endpoints(image, p1, p2):
    if len({isinstance(p, (SkyFrame, SkyCoord)) for p in (p1, p2)}) != 1:
        raise ValueError("estremi entrambi celesti o entrambi in pixel")
    x1, y1, s1, n1 = _pixel_xy(image, p1, "p1")
    x2, y2, s2, n2 = _pixel_xy(image, p2, "p2")
    return x1, y1, x2, y2, s1, s2, n1 + n2


def profile_along_line(image, p1, p2, step) -> Profile:
    """Profilo di intensità lungo il segmento ``p1``–``p2`` (in pixel), passo obbligatorio in pixel (D17-5)."""
    step_px = _step_pixels(step)
    x1, y1, x2, y2, s1, _, notes = _endpoints(image, p1, p2)
    return _profile(image, x1, y1, x2, y2, step_px, notes, None if s1 is None else s1.frame_name)


@dataclass(frozen=True, eq=False)
class DistanceWithProfile:
    """Misura H11: distanza (angolare o in pixel) e profilo lungo il segmento."""

    distance: u.Quantity  # gradi per estremi celesti, u.pix per estremi in pixel ("pixel space")
    angular: AngularDistance | None
    profile: Profile
    report: MeasureReport

    def to_table(self) -> Table:
        """Tabella del profilo con la distanza e il report nei metadati (grafico esportabile, D17-6)."""
        table = self.profile.to_table()
        table.meta["distance"] = f"{self.distance.value!r} {self.distance.unit}"
        table.meta["report"] = self.report.description
        return table


def distance_with_profile(image, p1, p2, step) -> DistanceWithProfile:
    """Distanza tra due punti con il profilo di intensità lungo il segmento (H11, D17-6)."""
    step_px = _step_pixels(step)
    x1, y1, x2, y2, s1, s2, notes = _endpoints(image, p1, p2)
    profile = _profile(image, x1, y1, x2, y2, step_px, notes, None if s1 is None else s1.frame_name)
    if s1 is not None:
        angular = angular_distance(s1, s2, "deg")
        distance, frame = angular.value, angular.report.frame
        what = "distanza angolare con angular_distance (skydist del 13)"
    else:
        angular, frame = None, None
        distance = np.float64(np.hypot(x2 - x1, y2 - y1)) * u.pix
        what = "distanza in pixel (pixel space, nessuna conversione implicita)"
    report = MeasureReport(
        operation="distance_with_profile", points=profile.report.points, frame=frame, unit=distance.unit.to_string(),
        image=profile.report.image, notes=(what,) + profile.report.notes, warnings=profile.report.warnings,
        provenance=_PIXEL_PROVENANCE)
    return DistanceWithProfile(distance=distance, angular=angular, profile=profile, report=report)


# --------------------------------------------------------------------------
# P3 — forme e tag (D17-7)
# --------------------------------------------------------------------------

_SG_PROVENANCE = f"spherical-geometry {importlib.metadata.version('spherical-geometry')}, {_PROVENANCE}"

#: Definizione dell'ellisse usata da AstroTwo, scritta in ogni risultato (D17-7).
ELLIPSE_DEFINITION = ("ellisse sferica: punti la cui somma delle distanze angolari dai due fuochi è ≤ 2a "
                      "(definizione intrinseca sulla sfera; per ellissi grandi differisce dall'ellisse nel piano "
                      "tangente al centro)")
#: Campioni massimi della regola dei trapezi per l'area dell'ellisse (scelta minore 3 di P3).
ELLIPSE_MAX_SAMPLES = 2**16
_FULL_SKY_SR = 4.0 * np.pi


@dataclass(frozen=True)
class ShapeMeasure:
    """Risultato di ``contains`` (``bool``) o ``area`` (``Quantity`` in sr) di una forma, con il report."""

    value: object
    shape: str
    report: MeasureReport
    error: u.Quantity | None = None  # stima dell'errore (solo ellisse: area o distanza, calcolo numerico)
    samples: int | None = None  # campioni del calcolo numerico (solo ellisse)


def _unsupported(kind: str, what: str) -> MeasuresError:
    return MeasuresError("OPERATION_UNSUPPORTED", f"{what} non definito per {kind} (D17-7)")


def _shape_angle(value: object, what: str) -> u.Quantity:
    if not isinstance(value, u.Quantity) or not value.unit.is_equivalent(u.deg):
        raise MeasuresError("SHAPE_INVALID", f"{what}: serve un angolo con unità, non {value!r}", field=what)
    if value.size != 1 or not np.isfinite(value.value):
        raise MeasuresError("SHAPE_INVALID", f"{what}: un solo valore finito, non {value!r}", field=what)
    return value.to(u.deg).astype(np.float64).reshape(())


def _shape_points(points: object, what: str) -> tuple[tuple[SkyFrame, ...], tuple[str, ...]]:
    """Punti di una forma nel frame del primo (modulo 10), con le note delle conversioni."""
    if isinstance(points, SkyCoord) and not points.isscalar:
        points = list(points.ravel())
    if isinstance(points, (SkyFrame, SkyCoord)) or not isinstance(points, Sequence):
        raise TypeError(f"{what}: serve una sequenza di punti (SkyFrame/SkyCoord)")
    if not points:
        raise MeasuresError("SHAPE_INVALID", f"{what}: nessun punto", field=what)
    first = _as_point(points[0], f"{what}[0]")
    result, notes = [first], []
    for i, point in enumerate(points[1:], start=1):
        converted, note = _in_frame_of(first, _as_point(point, f"{what}[{i}]"), f"{what}[{i}]")
        result.append(converted)
        notes.extend(note)
    return tuple(result), tuple(notes)


def _lonlat_deg(point: SkyFrame) -> tuple[float, float]:
    return float(point.lon.to_value(u.deg)), float(point.lat.to_value(u.deg))


@dataclass(frozen=True)
class _DistanceGeometry:
    """Forma ridotta per ``distance_to`` (D17-8, D17-9).

    ``cap``: calotta (cerchio, punto con raggio 0); ``polygon``: poligono sferico chiuso; ``path``: sequenza
    aperta di archi di cerchio massimo (freccia, tracciato aperto); ``ellipse``: ellisse sferica (fuochi e ``a``).
    """

    kind: str  # "cap", "polygon", "path" o "ellipse"
    reference: SkyFrame  # punto di riferimento del frame (centro, primo vertice o primo punto)
    radius: float = 0.0  # gradi (calotta)
    vertices: np.ndarray | None = None  # (n, 2) lon, lat in gradi (poligono, tracciato)
    polygon: object = None  # SingleSphericalPolygon con l'interno scelto (poligono)
    foci: tuple | None = None  # ((lon, lat), (lon, lat)) dei fuochi (ellisse)
    a: float = 0.0  # semiasse maggiore in gradi (ellisse)

    @classmethod
    def cap(cls, center: SkyFrame, radius: float) -> _DistanceGeometry:
        return cls("cap", center, radius)


def _unit_vectors(lon_deg, lat_deg) -> np.ndarray:
    return np.stack(sg_vector.lonlat_to_vector(lon_deg, lat_deg, degrees=True), axis=-1)


def _points_to_arcs_deg(lon, lat, start: np.ndarray, end: np.ndarray) -> np.ndarray:
    """Distanza minima (gradi) di ogni punto da un insieme di archi di cerchio massimo ``start[i]``–``end[i]``.

    Per ogni arco AB: se la proiezione del punto sul cerchio massimo di AB cade dentro l'arco, la distanza è
    quella dal cerchio massimo, atan2(|P·n|, |P − (P·n) n|) con n polo di AB; altrimenti è la distanza dal
    più vicino dei due estremi (``skydist`` del 13).
    """
    lon, lat = np.atleast_1d(np.asarray(lon, dtype=np.float64)), np.atleast_1d(np.asarray(lat, dtype=np.float64))
    a, b = _unit_vectors(start[:, 0], start[:, 1]), _unit_vectors(end[:, 0], end[:, 1])
    p = _unit_vectors(lon, lat)  # (k, 3)
    n = np.cross(a, b)
    norm = np.linalg.norm(n, axis=1)
    defined = norm > 0.0  # arco nullo o con estremi antipodali: nessun cerchio massimo unico, solo gli estremi
    n /= np.where(defined, norm, 1.0)[:, None]
    pn = p @ n.T  # (k, archi)
    q = p[:, None, :] - pn[..., None] * n[None, :, :]
    q_norm = np.linalg.norm(q, axis=2)
    within = ((np.einsum("kij,ij->ki", np.cross(a[None, :, :], q), n) >= 0.0)
              & (np.einsum("kij,ij->ki", np.cross(q, b[None, :, :]), n) >= 0.0) & (q_norm > 0.0) & defined)
    perpendicular = np.rad2deg(np.arctan2(np.abs(pn), q_norm))
    ends = np.minimum(skydist(lon[:, None], lat[:, None], start[None, :, 0], start[None, :, 1]),
                      skydist(lon[:, None], lat[:, None], end[None, :, 0], end[None, :, 1]))
    return np.min(np.where(within, perpendicular, ends), axis=1)


def _arcs(geometry: _DistanceGeometry) -> tuple[np.ndarray, np.ndarray]:
    """Archi di una forma ridotta: lati chiusi del poligono o archi consecutivi del tracciato aperto."""
    vertices = geometry.vertices
    if geometry.kind == "polygon":
        return vertices, np.roll(vertices, -1, axis=0)
    return vertices[:-1], vertices[1:]


def _point_to_edges_deg(lon: float, lat: float, vertices: np.ndarray) -> float:
    """Distanza minima (gradi) di un punto dai lati (archi di cerchio massimo) di un poligono chiuso."""
    return float(_points_to_arcs_deg(lon, lat, vertices, np.roll(vertices, -1, axis=0))[0])


def _point_to_polygon_deg(lon: float, lat: float, geometry: _DistanceGeometry) -> float:
    if geometry.polygon.contains_lonlat(lon, lat, degrees=True):
        return 0.0
    return _point_to_edges_deg(lon, lat, geometry.vertices)


def _arcs_cross(first: _DistanceGeometry, second: _DistanceGeometry) -> bool:
    """Vero se un arco della prima forma incrocia un arco della seconda (``great_circle_arc.intersects``)."""
    def usable(start, end):
        a, b = _unit_vectors(start[:, 0], start[:, 1]), _unit_vectors(end[:, 0], end[:, 1])
        keep = np.linalg.norm(np.cross(a, b), axis=1) > 0.0  # archi nulli o antipodali: bastano gli estremi
        return a[keep], b[keep]

    a1, b1 = usable(*_arcs(first))
    a2, b2 = usable(*_arcs(second))
    if not len(a2):
        return False
    return any(bool(np.any(sg_arc.intersects(a, b, a2, b2))) for a, b in zip(a1, b1))


# --- ellisse (D17-9): minimo numerico sul bordo con precisione dichiarata ---

#: Precisione assoluta di default di ``distance_to`` quando c'è un'ellisse (D17-9, configurabile).
ELLIPSE_DISTANCE_ATOL = 1e-9 * u.deg
_DISTANCE_START_SAMPLES = 128
_DISTANCE_MAX_SAMPLES_2D = 2**10  # ellisse–ellisse: griglia n × n
_DISTANCE_CANDIDATES = 8
_THETA_XATOL = 1e-10  # gradi, raffinamento della direzione θ


def _ellipse_boundary_radius(center_lon, center_lat, foci, a_deg: float, theta_deg: np.ndarray) -> np.ndarray:
    """Distanza (gradi) del bordo dell'ellisse sferica dal centro nelle direzioni ``theta`` (bisezione fino a
    ``float64`` sulla funzione "somma delle distanze dai fuochi − 2a" lungo il raggio)."""
    limit = 2.0 * a_deg
    (l1, b1), (l2, b2) = foci
    lo, hi = np.zeros_like(theta_deg), np.full_like(theta_deg, limit)  # a 2a la somma è già > 2a
    theta = theta_deg * u.deg
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        lon, lat = offset_by(center_lon, center_lat, theta, mid * u.deg)
        inside = skydist(lon, lat, l1, b1) + skydist(lon, lat, l2, b2) <= limit
        lo, hi = np.where(inside, mid, lo), np.where(inside, hi, mid)
        if np.all(hi - lo <= 2.0 * np.finfo(np.float64).eps * hi):
            break
    return 0.5 * (lo + hi)


def _ellipse_boundary(geometry: _DistanceGeometry, theta_deg) -> tuple[np.ndarray, np.ndarray]:
    """Punti del bordo (lon, lat in gradi) nelle direzioni ``theta`` dal centro.

    Molte direzioni: bisezione vettoriale (:func:`_ellipse_boundary_radius`); una sola (raffinamenti):
    ``scipy.optimize.brentq`` sulla stessa funzione, alla stessa precisione ``float64`` con meno passi.
    """
    theta_deg = np.atleast_1d(np.asarray(theta_deg, dtype=np.float64))
    center = geometry.reference
    if theta_deg.size == 1:
        (l1, b1), (l2, b2) = geometry.foci
        theta = theta_deg[0] * u.deg

        def excess(rho: float) -> float:
            lon, lat = offset_by(center.lon, center.lat, theta, rho * u.deg)
            return float(skydist(lon, lat, l1, b1) + skydist(lon, lat, l2, b2)) - 2.0 * geometry.a

        rho = np.array([brentq(excess, 0.0, 2.0 * geometry.a, xtol=1e-300, rtol=4 * np.finfo(np.float64).eps)])
    else:
        rho = _ellipse_boundary_radius(center.lon, center.lat, geometry.foci, geometry.a, theta_deg)
    lon, lat = offset_by(center.lon, center.lat, theta_deg * u.deg, rho * u.deg)
    return lon.to_value(u.deg), lat.to_value(u.deg)


def _focal_excess(geometry: _DistanceGeometry, lon, lat) -> np.ndarray:
    """Somma delle distanze dai fuochi − 2a (gradi): ≤ 0 dentro l'ellisse, funzione liscia fuori dai fuochi."""
    (l1, b1), (l2, b2) = geometry.foci
    return np.asarray(skydist(lon, lat, l1, b1) + skydist(lon, lat, l2, b2) - 2.0 * geometry.a)


def _in_ellipse(geometry: _DistanceGeometry, lon, lat) -> np.ndarray:
    return _focal_excess(geometry, lon, lat) <= 0.0


_ARC_SAMPLES = 64


def _arcs_enter_ellipse(ellipse: _DistanceGeometry, other: _DistanceGeometry) -> bool:
    """Vero se un arco dell'altra forma entra nell'ellisse: minimo della funzione liscia "somma delle distanze
    dai fuochi − 2a" lungo l'arco (punti con ``offset_by``, minimi locali raffinati con ``minimize_scalar``) ≤ 0.

    Così l'incrocio dei bordi si riconosce senza cercare uno zero della distanza, che è uno spigolo e non si
    raggiunge con la precisione dichiarata.
    """
    fractions = np.linspace(0.0, 1.0, _ARC_SAMPLES + 1)
    for (lon1, lat1), (lon2, lat2) in zip(*_arcs(other)):
        length = float(skydist(lon1, lat1, lon2, lat2))
        if length == 0.0 or length >= 180.0:  # arco nullo o antipodale: bastano gli estremi, già controllati
            continue
        pa = astropy_position_angle(lon1 * u.deg, lat1 * u.deg, lon2 * u.deg, lat2 * u.deg)

        def excess(f, pa=pa, lon1=lon1, lat1=lat1, length=length):
            lon, lat = offset_by(lon1 * u.deg, lat1 * u.deg, pa, np.asarray(f) * length * u.deg)
            return _focal_excess(ellipse, lon, lat)

        values = excess(fractions)
        if np.any(values <= 0.0):
            return True
        local = np.flatnonzero((values <= np.r_[np.inf, values[:-1]]) & (values <= np.r_[values[1:], np.inf]))
        for i in local:
            bounds = (fractions[max(i - 1, 0)], fractions[min(i + 1, _ARC_SAMPLES)])
            refined = minimize_scalar(lambda f: float(excess(f)), bounds=bounds, method="bounded",
                                      options={"xatol": 1e-12})
            if refined.fun <= 0.0:
                return True
    return False


def _precision_not_reached(value: float, error: float, samples: int, atol: float) -> MeasuresError:
    return MeasuresError("DISTANCE_PRECISION_NOT_REACHED", f"distanza {value!r}° con stima dell'errore {error!r}° "
                         f"dopo {samples} campioni: precisione {atol!r}° non raggiunta",
                         value=value, error=error, samples=samples)


def _cyclic_minima(values: np.ndarray, threshold: float) -> list[tuple[int, ...]]:
    """Indici dei minimi locali (vicini ciclici) con valore ≤ ``threshold``, i migliori per primi."""
    is_min = values <= threshold
    for axis in range(values.ndim):
        for shift in (1, -1):
            is_min &= values <= np.roll(values, shift, axis=axis)
    indices = np.argwhere(is_min)
    order = np.argsort(values[tuple(indices.T)])
    return [tuple(int(i) for i in indices[k]) for k in order[:_DISTANCE_CANDIDATES]]


def _ellipse_minimum(geometry: _DistanceGeometry, g, atol: float) -> tuple[float, float, int]:
    """Minimo di ``g`` (distanza in gradi, vettoriale in lon, lat) sul bordo dell'ellisse.

    Campioni di θ raddoppiati da 128 finché due stime consecutive differiscono meno di ``atol`` (la differenza
    è la stima dell'errore); a ogni passo i minimi locali dei campioni vicini al minimo (entro la massima
    distanza tra campioni consecutivi del bordo) si raffinano con ``scipy.optimize.minimize_scalar``.
    """
    def estimate(n: int) -> float:
        step = 360.0 / n
        theta = np.arange(n, dtype=np.float64) * step
        lon, lat = _ellipse_boundary(geometry, theta)
        values = g(lon, lat)
        spacing = float(np.max(skydist(lon, lat, np.roll(lon, -1), np.roll(lat, -1))))
        best = float(values.min())
        for (i,) in _cyclic_minima(values, best + spacing):
            refined = minimize_scalar(lambda t: float(g(*_ellipse_boundary(geometry, t))[0]),
                                      bounds=(theta[i] - step, theta[i] + step), method="bounded",
                                      options={"xatol": _THETA_XATOL})
            best = min(best, float(refined.fun))
        return best

    n, previous = _DISTANCE_START_SAMPLES, estimate(_DISTANCE_START_SAMPLES)
    while True:
        n *= 2
        current = estimate(n)
        error = abs(current - previous)
        if error <= atol:
            return current, error, n
        if n >= ELLIPSE_MAX_SAMPLES:
            raise _precision_not_reached(current, error, n, atol)
        previous = current


def _ellipses_minimum(first: _DistanceGeometry, second: _DistanceGeometry, atol: float) -> tuple[float, float, int]:
    """Minimo della distanza tra i bordi di due ellissi: griglia n × n di direzioni (θ₁, θ₂) raddoppiata come in
    :func:`_ellipse_minimum`, minimi locali raffinati con ``scipy.optimize.minimize`` (Nelder-Mead)."""
    def pair_distance(x) -> float:
        lon1, lat1 = _ellipse_boundary(first, x[0])
        lon2, lat2 = _ellipse_boundary(second, x[1])
        return float(skydist(lon1, lat1, lon2, lat2)[0])

    def estimate(n: int) -> float:
        step = 360.0 / n
        theta = np.arange(n, dtype=np.float64) * step
        (lon1, lat1), (lon2, lat2) = _ellipse_boundary(first, theta), _ellipse_boundary(second, theta)
        values = skydist(lon1[:, None], lat1[:, None], lon2[None, :], lat2[None, :])
        spacing = sum(float(np.max(skydist(lo, la, np.roll(lo, -1), np.roll(la, -1))))
                      for lo, la in ((lon1, lat1), (lon2, lat2)))
        best = float(values.min())
        for i, j in _cyclic_minima(values, best + spacing):
            start = np.array([theta[i], theta[j]])
            refined = minimize(pair_distance, start, method="Nelder-Mead", options={
                "xatol": _THETA_XATOL, "fatol": 1e-15,
                "initial_simplex": [start, start + [step, 0.0], start + [0.0, step]]})
            best = min(best, float(refined.fun))
        return best

    n, previous = _DISTANCE_START_SAMPLES, estimate(_DISTANCE_START_SAMPLES)
    while True:
        n *= 2
        current = estimate(n)
        error = abs(current - previous)
        if error <= atol:
            return current, error, n
        if n >= _DISTANCE_MAX_SAMPLES_2D:
            raise _precision_not_reached(current, error, n, atol)
        previous = current


_KIND_ORDER = {"cap": 0, "polygon": 1, "path": 2, "ellipse": 3}


def _geometry_distance(first: _DistanceGeometry, second: _DistanceGeometry,
                       atol: float) -> tuple[float, str, float | None, int | None]:
    """Distanza minima (gradi) tra due forme ridotte, con la descrizione del calcolo, la stima dell'errore e i
    campioni (solo con un'ellisse: calcolo numerico, D17-9)."""
    first, second = sorted((first, second), key=lambda g: _KIND_ORDER[g.kind])
    pair = (first.kind, second.kind)
    if pair == ("cap", "cap"):
        lon1, lat1 = _lonlat_deg(first.reference)
        lon2, lat2 = _lonlat_deg(second.reference)
        separation = float(skydist(lon1, lat1, lon2, lat2))
        return max(0.0, separation - first.radius - second.radius), (
            f"calotte: separazione dei centri {separation!r}° (skydist del 13) − raggi {first.radius!r}° e "
            f"{second.radius!r}°, minimo 0; esatta"), None, None
    if pair == ("polygon", "polygon"):
        if first.polygon.intersects_poly(second.polygon):
            return 0.0, "poligoni sovrapposti (SphericalPolygon.intersects_poly): 0", None, None
        distance = min(min(_point_to_edges_deg(lon, lat, second.vertices) for lon, lat in first.vertices),
                       min(_point_to_edges_deg(lon, lat, first.vertices) for lon, lat in second.vertices))
        return distance, ("poligoni disgiunti: minimo delle distanze vertice–arco di cerchio massimo nei due versi "
                          "(il minimo tra due archi disgiunti cade in un estremo)"), None, None
    if pair == ("cap", "polygon"):
        lon, lat = _lonlat_deg(first.reference)
        to_polygon = _point_to_polygon_deg(lon, lat, second)
        return max(0.0, to_polygon - first.radius), (
            f"calotta e poligono: distanza del centro dal poligono {to_polygon!r}° (0 se dentro, "
            f"SphericalPolygon.contains_lonlat; altrimenti distanza punto–arco di cerchio massimo) − raggio "
            f"{first.radius!r}°, minimo 0"), None, None
    if pair == ("cap", "path"):
        lon, lat = _lonlat_deg(first.reference)
        to_path = float(_points_to_arcs_deg(lon, lat, *_arcs(second))[0])
        return max(0.0, to_path - first.radius), (
            f"calotta e archi di cerchio massimo (D17-9): distanza punto–arco del centro {to_path!r}° − raggio "
            f"{first.radius!r}°, minimo 0"), None, None
    if pair in (("polygon", "path"), ("path", "path")):
        inside = (pair == ("polygon", "path")
                  and any(first.polygon.contains_lonlat(lon, lat, degrees=True) for lon, lat in second.vertices))
        if inside or _arcs_cross(first, second):
            return 0.0, ("archi di cerchio massimo (D17-9) che incrociano l'altra forma (great_circle_arc.intersects)"
                         " o con un punto dentro il poligono: 0"), None, None
        distance = min(float(np.min(_points_to_arcs_deg(first.vertices[:, 0], first.vertices[:, 1],
                                                         *_arcs(second)))),
                       float(np.min(_points_to_arcs_deg(second.vertices[:, 0], second.vertices[:, 1],
                                                        *_arcs(first)))))
        return distance, ("archi di cerchio massimo (D17-9) disgiunti: minimo delle distanze estremo–arco nei due "
                          "versi (il minimo tra due archi disgiunti cade in un estremo)"), None, None
    return _ellipse_distance(first, second, atol)


def _ellipse_distance(other: _DistanceGeometry, ellipse: _DistanceGeometry,
                      atol: float) -> tuple[float, str, float | None, int | None]:
    """Distanza tra un'ellisse (D17-9) e un'altra forma ridotta: 0 se un punto dell'una è dentro l'altra,
    altrimenti minimo numerico sul bordo dell'ellisse, 0 se non supera la precisione (forme che si toccano o
    i cui bordi si incrociano)."""
    method = ("ellisse (D17-9): minimo numerico sul bordo (bordo per bisezione in float64 con offset_by e "
              "skydist del 13; campioni di θ raddoppiati da 128, minimi locali raffinati con scipy.optimize; "
              f"precisione assoluta richiesta {atol!r}°, stima dell'errore = differenza tra due stime consecutive)")
    center = _lonlat_deg(ellipse.reference)
    if other.kind == "cap":
        point = _lonlat_deg(other.reference)
        if _in_ellipse(ellipse, *point):
            return 0.0, "centro della calotta dentro l'ellisse: 0", None, None
        value, error, samples = _ellipse_minimum(ellipse, lambda lon, lat: skydist(lon, lat, *point), atol)
        value -= other.radius
        method += f"; meno il raggio della calotta {other.radius!r}°"
    elif other.kind in ("polygon", "path"):
        vertices = other.vertices
        if np.any(_in_ellipse(ellipse, vertices[:, 0], vertices[:, 1])) or (
                other.kind == "polygon" and other.polygon.contains_lonlat(*center, degrees=True)):
            return 0.0, "un vertice dentro l'ellisse o il centro dell'ellisse dentro il poligono: 0", None, None
        if _arcs_enter_ellipse(ellipse, other):
            return 0.0, ("un arco entra nell'ellisse (minimo di \"somma delle distanze dai fuochi − 2a\" lungo "
                         "l'arco ≤ 0, scipy.optimize.minimize_scalar): 0"), None, None
        value, error, samples = _ellipse_minimum(
            ellipse, lambda lon, lat: _points_to_arcs_deg(lon, lat, *_arcs(other)), atol)
        method += "; distanza di ogni punto del bordo dagli archi di cerchio massimo dell'altra forma"
    else:
        if _in_ellipse(ellipse, *_lonlat_deg(other.reference)) or _in_ellipse(other, *center):
            return 0.0, "centro di un'ellisse dentro l'altra: 0", None, None
        excess, _, _ = _ellipse_minimum(other, lambda lon, lat: _focal_excess(ellipse, lon, lat), atol)
        if excess <= 0.0:
            return 0.0, ("il bordo di un'ellisse entra nell'altra (minimo di \"somma delle distanze dai fuochi − 2a\" "
                         "lungo il bordo ≤ 0): 0"), None, None
        value, error, samples = _ellipses_minimum(other, ellipse, atol)
        method += "; ellisse–ellisse: griglia di coppie di direzioni (θ₁, θ₂), raffinata con Nelder-Mead"
    if value <= atol:
        return 0.0, method + "; minimo entro la precisione: le forme si toccano o si sovrappongono, 0", error, samples
    return value, method, error, samples


class Shape:
    """Forma H11 con coordinate celesti (D17-2: solo geometria, il disegno è del 41)."""

    kind = "shape"
    frame: str

    def contains(self, point) -> ShapeMeasure:
        raise _unsupported(self.kind, "contains")

    def area(self) -> ShapeMeasure:
        raise _unsupported(self.kind, "area")

    def describe(self) -> dict:
        raise NotImplementedError

    def _distance_geometry(self, reference: SkyFrame | None) -> tuple[_DistanceGeometry, tuple[str, ...]]:
        raise NotImplementedError

    def distance_to(self, other, *, atol: u.Quantity = ELLIPSE_DISTANCE_ATOL) -> ShapeMeasure:
        """Distanza angolare minima (D17-8, D17-9) da un'altra forma o da un punto, in gradi.

        0 se le forme si sovrappongono o se il punto è dentro; cerchi esatti con Astropy (separazione − raggi),
        poligoni, frecce e tracciati con la distanza punto–arco di cerchio massimo; con un'ellisse minimo
        numerico sul bordo con precisione assoluta ``atol`` (stima dell'errore e campioni nel risultato). Il
        testo non ha distanza (``OPERATION_UNSUPPORTED``). Nel frame di questa forma.
        """
        if not isinstance(atol, u.Quantity) or not atol.unit.is_equivalent(u.deg) or atol.size != 1:
            raise ValueError(f"atol {atol!r}: serve un angolo positivo con unità")
        atol_deg = float(atol.to_value(u.deg))
        if not 0.0 < atol_deg < 1.0:
            raise ValueError(f"atol {atol!r}: serve un angolo in (0°, 1°)")
        mine, notes = self._distance_geometry(None)
        if isinstance(other, Shape):
            theirs, other_notes = other._distance_geometry(mine.reference)
            other_kind = other.kind
        else:
            point, other_notes = self._point(mine.reference, other)
            theirs, other_kind = _DistanceGeometry.cap(point, 0.0), "point"
        value, method, error, samples = _geometry_distance(mine, theirs, atol_deg)
        kinds = {mine.kind, theirs.kind}
        provenance = _SG_PROVENANCE if kinds & {"polygon", "path"} else _PROVENANCE
        if "ellipse" in kinds:
            provenance += f", scipy {scipy.__version__}"
        return ShapeMeasure(
            value=np.float64(value) * u.deg, shape=self.kind,
            error=None if error is None else np.float64(error) * u.deg, samples=samples, report=self._report(
                "distance_to", (f"{self.kind}: {_describe(mine.reference)}",
                                f"{other_kind}: {_describe(theirs.reference)}"),
                "deg", notes + other_notes + (
                    "distanza angolare minima tra le forme (D17-8, D17-9): 0 se si sovrappongono o se il punto è "
                    "dentro", method), provenance))

    def _point(self, reference: SkyFrame, point) -> tuple[SkyFrame, tuple[str, ...]]:
        converted, notes = _in_frame_of(reference, _as_point(point, "point"), "point")
        return converted, notes + _epoch_notes((reference, converted))

    def _report(self, operation: str, points: tuple[str, ...], unit: str, notes: tuple[str, ...],
                provenance: str = _PROVENANCE) -> MeasureReport:
        return MeasureReport(operation=f"{self.kind}.{operation}", points=points, frame=self.frame, unit=unit,
                             notes=notes, provenance=provenance)


class Circle(Shape):
    """Cerchio sulla sfera (calotta): centro e raggio angolare 0 < r < 180°; calcolo esatto con Astropy."""

    kind = "circle"

    def __init__(self, center, radius) -> None:
        self.center = _as_point(center, "center")
        self.radius = _shape_angle(radius, "radius")
        if not 0.0 < self.radius.value < 180.0:
            raise MeasuresError("SHAPE_INVALID", f"radius {self.radius!r}: serve 0° < r < 180°", field="radius")
        self.frame = self.center.frame_name

    def contains(self, point) -> ShapeMeasure:
        p, notes = self._point(self.center, point)
        separation = float(skydist(self.center.lon, self.center.lat, p.lon, p.lat))
        inside = bool(separation <= self.radius.value)
        return ShapeMeasure(value=inside, shape=self.kind, report=self._report(
            "contains", (_describe(self.center), _describe(p)), "bool", notes + (
                f"separazione dal centro {separation!r}° (skydist del 13) ≤ raggio {self.radius.value!r}°: "
                f"{inside}",)))

    def area(self) -> ShapeMeasure:
        # Calotta sferica: 2π(1 − cos r) = 4π sin²(r/2), forma senza cancellazione per raggi piccoli.
        value = np.float64(_FULL_SKY_SR * np.sin(self.radius.to_value(u.rad) / 2.0) ** 2) * u.sr
        return ShapeMeasure(value=value, shape=self.kind, report=self._report(
            "area", (_describe(self.center),), "sr", (f"raggio {self.radius.value!r}°; area della calotta "
                                                      "2π(1 − cos r), esatta",)))

    def describe(self) -> dict:
        return {"shape": self.kind, "frame": self.frame, "center": _describe(self.center), "radius": self.radius}

    def _distance_geometry(self, reference: SkyFrame | None) -> tuple[_DistanceGeometry, tuple[str, ...]]:
        center, notes = (self.center, ()) if reference is None else _in_frame_of(reference, self.center,
                                                                                 "centro del cerchio")
        return _DistanceGeometry.cap(center, float(self.radius.value)), notes


class Ellipse(Shape):
    """Ellisse sferica (D17-7): punti con somma delle distanze angolari dai fuochi ≤ 2a.

    ``a``, ``b``: semiassi (distanze angolari dal centro dei vertici degli assi), 0 < b ≤ a < 90°;
    ``position_angle``: angolo di posizione dell'asse maggiore, da nord verso est.
    """

    kind = "ellipse"

    def __init__(self, center, a, b, position_angle) -> None:
        self.center = _as_point(center, "center")
        self.a = _shape_angle(a, "a")
        self.b = _shape_angle(b, "b")
        self.position_angle = _shape_angle(position_angle, "position_angle")
        if not 0.0 < self.b.value <= self.a.value < 90.0:
            raise MeasuresError("SHAPE_INVALID", f"semiassi a = {self.a!r}, b = {self.b!r}: serve 0° < b ≤ a < 90°",
                                field="a" if self.a.value >= 90.0 else "b")
        self.frame = self.center.frame_name
        # Fuochi sull'asse maggiore a distanza c dal centro, cos c = cos a / cos b (Pitagora sferico), scritta
        # senza cancellazione: sin²(c/2) = (cos b − cos a) / (2 cos b) = sin((a+b)/2)·sin((a−b)/2) / cos b.
        a_rad, b_rad = self.a.to_value(u.rad), self.b.to_value(u.rad)
        half = np.sin((a_rad + b_rad) / 2.0) * np.sin((a_rad - b_rad) / 2.0) / np.cos(b_rad)
        self.focal_distance = (np.float64(2.0 * np.arcsin(np.sqrt(half))) * u.rad).to(u.deg)
        lon, lat = self.center.lon, self.center.lat
        self._foci = tuple(offset_by(lon, lat, self.position_angle + turn, self.focal_distance)
                           for turn in (0 * u.deg, 180 * u.deg))

    @property
    def foci(self) -> tuple[SkyFrame, SkyFrame]:
        """I due fuochi, nel frame e all'epoca del centro."""
        return tuple(SkyFrame(coord=SkyCoord(lon, lat, frame=self.center.coord.frame), epoch=self.center.epoch,
                              frame_defaults_note=self.center.frame_defaults_note) for lon, lat in self._foci)

    def _focal_sum(self, lon, lat):
        (l1, b1), (l2, b2) = self._foci
        return skydist(lon, lat, l1, b1) + skydist(lon, lat, l2, b2)

    def contains(self, point) -> ShapeMeasure:
        p, notes = self._point(self.center, point)
        total = float(self._focal_sum(p.lon, p.lat))
        limit = 2.0 * float(self.a.value)
        inside = bool(total <= limit)
        return ShapeMeasure(value=inside, shape=self.kind, report=self._report(
            "contains", (_describe(self.center), _describe(p)), "bool", notes + (
                ELLIPSE_DEFINITION, f"somma delle distanze dai fuochi {total!r}° (skydist del 13) ≤ 2a = {limit!r}°: "
                f"{inside}")))

    def _boundary_radius(self, theta_deg: np.ndarray) -> np.ndarray:
        """Distanza (gradi) del bordo dal centro nelle direzioni ``theta`` (bisezione fino a ``float64``)."""
        return _ellipse_boundary_radius(self.center.lon, self.center.lat, self._foci, float(self.a.value), theta_deg)

    def _trapezoid(self, n: int) -> float:
        theta = np.arange(n, dtype=np.float64) * (360.0 / n)
        rho = np.deg2rad(self._boundary_radius(theta))
        return float(2.0 * np.pi / n * np.sum(2.0 * np.sin(rho / 2.0) ** 2))  # ∫ (1 − cos ρ) dθ

    def area(self, *, rtol: float = 1e-10) -> ShapeMeasure:
        """Area in sr per integrazione numerica (trapezi in θ), con la stima dell'errore dichiarata."""
        if isinstance(rtol, bool) or not isinstance(rtol, (int, float)) or not 0.0 < rtol < 1.0:
            raise ValueError(f"rtol {rtol!r}: serve un numero in (0, 1)")
        n, previous = 32, self._trapezoid(32)
        while True:
            n *= 2
            current = self._trapezoid(n)
            error = abs(current - previous)
            if error <= rtol * current:
                break
            if n >= ELLIPSE_MAX_SAMPLES:
                raise MeasuresError("AREA_PRECISION_NOT_REACHED", f"area {current!r} sr con stima dell'errore "
                                    f"{error!r} sr dopo {n} campioni: rtol {rtol!r} non raggiunta",
                                    value=current, error=error, samples=n)
            previous = current
        return ShapeMeasure(value=np.float64(current) * u.sr, shape=self.kind, error=np.float64(error) * u.sr,
                            samples=n, report=self._report(
                                "area", (_describe(self.center),), "sr", (
                                    ELLIPSE_DEFINITION,
                                    f"a = {self.a.value!r}°, b = {self.b.value!r}°, angolo di posizione "
                                    f"{self.position_angle.value!r}°, distanza dei fuochi {self.focal_distance.value!r}°",
                                    "area = ∫ (1 − cos ρ(θ)) dθ, ρ(θ) per bisezione (offset_by, skydist del 13), "
                                    f"regola dei trapezi con {n} campioni; stima dell'errore {error!r} sr "
                                    f"(rtol richiesta {rtol!r})")))

    def describe(self) -> dict:
        return {"shape": self.kind, "frame": self.frame, "center": _describe(self.center), "a": self.a, "b": self.b,
                "position_angle": self.position_angle, "focal_distance": self.focal_distance,
                "definition": ELLIPSE_DEFINITION}

    def _distance_geometry(self, reference: SkyFrame | None) -> tuple[_DistanceGeometry, tuple[str, ...]]:
        # L'ellisse sferica dipende solo dai fuochi e da a: in un altro frame si convertono centro e fuochi.
        if reference is None or reference.coord.frame.is_equivalent_frame(self.center.coord.frame):
            center, foci, notes = self.center, self._foci, ()
        else:
            center = _in_frame_of(reference, self.center, "centro dell'ellisse")[0]
            converted = [_in_frame_of(reference, f, "fuoco dell'ellisse")[0] for f in self.foci]
            foci = tuple((f.lon, f.lat) for f in converted)
            notes = (f"ellisse convertita da {self.frame} a {reference.frame_name} con il modulo 10 "
                     "(convert_coordinates): centro e fuochi, stesso a",)
        return _DistanceGeometry("ellipse", center, foci=foci, a=float(self.a.value)), notes


def _distinct_vertices(points: tuple[SkyFrame, ...]) -> tuple[tuple[SkyFrame, ...], tuple[str, ...]]:
    kept = [points[0]]
    for point in points[1:]:
        if _lonlat_deg(point) != _lonlat_deg(kept[-1]):
            kept.append(point)
    if len(kept) > 1 and _lonlat_deg(kept[-1]) == _lonlat_deg(kept[0]):
        kept.pop()
    removed = len(points) - len(kept)
    return tuple(kept), ((f"{removed} vertici ripetuti (consecutivi o di chiusura) tolti",) if removed else ())


class Polygon(Shape):
    """Poligono sferico (D17-7): lati di cerchio massimo, calcolo con ``spherical-geometry``.

    Interno: la regione che contiene ``inside`` se dato, altrimenti la più piccola delle due (area < 2π sr).
    """

    kind = "polygon"

    def __init__(self, vertices, *, inside=None) -> None:
        points, notes = _shape_points(vertices, "vertices")
        points, removed = _distinct_vertices(points)
        if len(points) < 3:
            raise MeasuresError("SHAPE_INVALID", f"vertices: {len(points)} vertici distinti, ne servono almeno 3",
                                field="vertices")
        self.vertices = points
        self.frame = points[0].frame_name
        self._notes = notes + removed
        lon, lat = np.array([_lonlat_deg(p) for p in points]).T
        x, y, z = sg_vector.lonlat_to_vector(np.r_[lon, lon[0]], np.r_[lat, lat[0]], degrees=True)
        if SphericalPolygon.self_intersect(np.dstack((x, y, z))[0]):
            raise MeasuresError("SHAPE_INVALID", "vertices: il poligono si interseca da solo", field="vertices")
        self.inside = None
        if inside is not None:
            self.inside, inside_notes = _in_frame_of(points[0], _as_point(inside, "inside"), "inside")
            self._notes += inside_notes
            polygon = SphericalPolygon.from_lonlat(lon, lat, center=_lonlat_deg(self.inside), degrees=True)
            rule = "interno: la regione che contiene il punto inside"
        else:
            polygon = SphericalPolygon.from_lonlat(lon, lat, degrees=True)
        area = float(polygon.area())
        if not np.isfinite(area) or area <= 0.0 or area >= _FULL_SKY_SR:
            raise MeasuresError("SHAPE_INVALID", f"vertices: poligono degenere (area {area!r} sr; vertici su un "
                                "cerchio massimo?)", field="vertices")
        if inside is None:
            if abs(area - _FULL_SKY_SR / 2.0) <= 1e-12 * _FULL_SKY_SR:
                raise MeasuresError("SHAPE_INVALID", "le due regioni delimitate dal bordo hanno la stessa area: "
                                    "serve il punto inside", field="inside")
            if area > _FULL_SKY_SR / 2.0:
                polygon = SphericalPolygon([next(iter(polygon.polygons)).invert_polygon()])
                area = float(polygon.area())
            rule = "interno: la più piccola delle due regioni delimitate dal bordo (area < 2π sr)"
        self._polygon = polygon
        self._area = area
        self._notes += (rule, "lati: archi di cerchio massimo tra vertici consecutivi (spherical-geometry)")

    def contains(self, point) -> ShapeMeasure:
        p, notes = self._point(self.vertices[0], point)
        inside = bool(self._polygon.contains_lonlat(*_lonlat_deg(p), degrees=True))
        return ShapeMeasure(value=inside, shape=self.kind, report=self._report(
            "contains", (f"{len(self.vertices)} vertici", _describe(p)), "bool",
            self._notes + notes + ("calcolo: SphericalPolygon.contains_lonlat; bordo in float64 non garantito",),
            _SG_PROVENANCE))

    def area(self) -> ShapeMeasure:
        return ShapeMeasure(value=np.float64(self._area) * u.sr, shape=self.kind, report=self._report(
            "area", tuple(_describe(v) for v in self.vertices), "sr",
            self._notes + ("calcolo: SphericalPolygon.area (teorema di Girard generalizzato)",), _SG_PROVENANCE))

    def describe(self) -> dict:
        return {"shape": self.kind, "frame": self.frame, "vertices": tuple(_describe(v) for v in self.vertices),
                "inside": None if self.inside is None else _describe(self.inside)}

    def _distance_geometry(self, reference: SkyFrame | None) -> tuple[_DistanceGeometry, tuple[str, ...]]:
        polygon, notes = self, ()
        if reference is not None and not reference.coord.frame.is_equivalent_frame(self.vertices[0].coord.frame):
            converted = [_in_frame_of(reference, v, "vertice del poligono")[0] for v in self.vertices]
            inside = None if self.inside is None else _in_frame_of(reference, self.inside, "inside")[0]
            polygon = Polygon(converted, inside=inside)
            notes = (f"poligono convertito da {self.frame} a {reference.frame_name} con il modulo 10 "
                     "(convert_coordinates), stessa regola per l'interno",)
        vertices = np.array([_lonlat_deg(v) for v in polygon.vertices])
        return _DistanceGeometry("polygon", polygon.vertices[0], vertices=vertices,
                                 polygon=next(iter(polygon._polygon.polygons))), notes


class Freehand(Shape):
    """Tracciato libero: come poligono solo se ``closed`` (D17-7), altrimenti nessuna area né "contiene"."""

    kind = "freehand"

    def __init__(self, points, *, closed: bool = False, inside=None) -> None:
        if not isinstance(closed, bool):
            raise TypeError("closed: serve True o False")
        self.closed = closed
        if closed:
            self._polygon = Polygon(points, inside=inside)
            self.points, self.frame = self._polygon.vertices, self._polygon.frame
        else:
            self._polygon = None
            self.points, _ = _shape_points(points, "points")
            self.frame = self.points[0].frame_name

    def contains(self, point) -> ShapeMeasure:
        if self._polygon is None:
            raise _unsupported("un tracciato aperto", "contains")
        result = self._polygon.contains(point)
        return replace(result, shape=self.kind)

    def area(self) -> ShapeMeasure:
        if self._polygon is None:
            raise _unsupported("un tracciato aperto", "area")
        return replace(self._polygon.area(), shape=self.kind)

    def describe(self) -> dict:
        return {"shape": self.kind, "frame": self.frame, "closed": self.closed,
                "points": tuple(_describe(p) for p in self.points)}

    def _distance_geometry(self, reference: SkyFrame | None) -> tuple[_DistanceGeometry, tuple[str, ...]]:
        if self._polygon is None:
            return _path_geometry(self.points, reference, "tracciato aperto")
        return self._polygon._distance_geometry(reference)


def _path_geometry(points: tuple[SkyFrame, ...], reference: SkyFrame | None,
                   what: str) -> tuple[_DistanceGeometry, tuple[str, ...]]:
    """Archi di cerchio massimo tra punti consecutivi (D17-9), nel frame di ``reference`` se dato."""
    notes = ()
    if reference is not None and not reference.coord.frame.is_equivalent_frame(points[0].coord.frame):
        points = tuple(_in_frame_of(reference, p, f"punto del {what}")[0] for p in points)
        notes = (f"{what} convertito a {reference.frame_name} con il modulo 10 (convert_coordinates)",)
    vertices = np.array([_lonlat_deg(p) for p in points])
    return _DistanceGeometry("path", points[0], vertices=vertices), notes + (
        f"{what}: archi di cerchio massimo tra punti consecutivi (D17-9)",)


class Arrow(Shape):
    """Freccia da ``start`` a ``end``: solo geometria (area e "contiene" non definiti, D17-7)."""

    kind = "arrow"

    def __init__(self, start, end) -> None:
        (self.start, self.end), self._notes = _shape_points([start, end], "arrow")
        self.frame = self.start.frame_name

    def describe(self) -> dict:
        return {"shape": self.kind, "frame": self.frame, "start": _describe(self.start), "end": _describe(self.end)}

    def _distance_geometry(self, reference: SkyFrame | None) -> tuple[_DistanceGeometry, tuple[str, ...]]:
        return _path_geometry((self.start, self.end), reference, "freccia")


class Text(Shape):
    """Testo in una posizione: solo geometria e attributi (area e "contiene" non definiti, D17-7)."""

    kind = "text"

    def __init__(self, position, text: str) -> None:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text: serve un testo non vuoto")
        self.position, self.text = _as_point(position, "position"), text
        self.frame = self.position.frame_name

    def describe(self) -> dict:
        return {"shape": self.kind, "frame": self.frame, "position": _describe(self.position), "text": self.text}

    def _distance_geometry(self, reference: SkyFrame | None) -> tuple[_DistanceGeometry, tuple[str, ...]]:
        raise MeasuresError("OPERATION_UNSUPPORTED", "distance_to non definita per un testo: un'etichetta non è "
                            "una regione (D17-9)")


@dataclass(frozen=True)
class Tag:
    """Marcatura (H11): punto celeste ed etichetta; la persiste la sessione del 24 (D17-3)."""

    point: SkyFrame
    label: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def tag(point, label: str) -> Tag:
    """Marcatura di un punto d'interesse con etichetta (nessuna scrittura su disco)."""
    if not isinstance(label, str) or not label.strip():
        raise ValueError("label: serve un'etichetta non vuota")
    return Tag(point=_as_point(point, "point"), label=label)


# --------------------------------------------------------------------------
# P4 — distanza automatica tra due sorgenti di catalogo (F1)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CatalogSource:
    """Una sorgente selezionata: riga di una tabella del 13, con le colonne del moto proprio se servono."""

    table: CatalogTable
    row: int
    pm_ra: str | None = None
    pm_dec: str | None = None
    pm_ra_includes_cosdec: bool | None = None  # obbligatorio con pm_ra: mai assunto (regola del 13)
    parallax: str | None = None
    radial_velocity: str | None = None
    source_epoch: object = None  # solo se l'epoca non è nei metadati (stessa regola del 13)


@dataclass(frozen=True)
class AutoDistance:
    """Distanza automatica (F1): distanza, estremi del segmento ed epoca usata."""

    distance: u.Quantity
    segment: Segment  # estremi = posizioni delle due sorgenti all'epoca usata (SkyFrame)
    epoch: Time
    epoch_from_first_source: bool  # True: nessuna epoca richiesta, usata quella della prima sorgente
    measure: AngularDistance
    report: MeasureReport


def _from_13(exc: CatalogsError, what: str) -> MeasuresError:
    code = "EPOCH_REQUIRED" if exc.code == "EPOCH_INVALID" else exc.code
    return MeasuresError(code, f"{what}: {exc.message}")


def _single_row(source: CatalogSource, what: str) -> CatalogTable:
    table = source.table
    if not isinstance(table, CatalogTable):
        raise TypeError(f"{what}: serve una CatalogTable del modulo 13")
    if isinstance(source.row, bool) or not isinstance(source.row, (int, np.integer)) \
            or not 0 <= source.row < table.rows:
        raise ValueError(f"{what}: riga {source.row!r} fuori dalla tabella di {table.rows} righe")
    if table.positions is None:
        raise MeasuresError("NO_COORD_COLUMNS", f"{what}: tabella senza colonne di posizione (confermarle nel 13)")
    if table.positions.frame is None:
        raise MeasuresError("FRAME_UNKNOWN", f"{what}: sistema delle colonne di posizione non dichiarato")
    mask = np.zeros(table.rows, dtype=bool)
    mask[int(source.row)] = True
    try:
        return catalogs.subset(table, mask)
    except CatalogsError as exc:
        raise _from_13(exc, what) from exc


def _row_position(single: CatalogTable, lon: str, lat: str, epoch, what: str) -> SkyFrame:
    pos = single.positions
    try:
        lon_q, lon_ok = catalogs._quantity_column(single.table, lon, u.deg, "posizione")
        lat_q, lat_ok = catalogs._quantity_column(single.table, lat, u.deg, "posizione")
    except CatalogsError as exc:
        raise _from_13(exc, what) from exc
    if not (lon_ok[0] and lat_ok[0]):
        raise MeasuresError("NO_COORD_COLUMNS", f"{what}: posizione mancante nella riga")
    try:
        return SkyFrame.from_lonlat(lon_q[0], lat_q[0], pos.frame, equinox=pos.equinox, epoch=epoch)
    except CoordinatesWcsError as exc:
        raise _from_10(exc, what) from exc


def _source_point(source: CatalogSource, what: str) -> tuple[CatalogTable, SkyFrame, str]:
    single = _single_row(source, what)
    try:
        epochs, epoch_source = catalogs._source_epochs(single, source.source_epoch)
    except CatalogsError as exc:
        raise _from_13(exc, what) from exc
    if epochs[0] is None:
        raise MeasuresError("EPOCH_REQUIRED", f"{what}: epoca della riga mancante ({epoch_source}): mai assunta")
    point = _row_position(single, single.positions.lon, single.positions.lat, epochs[0], what)
    return single, point, epoch_source


def _same_epoch(a: Time, b: Time) -> bool:
    return (a.tt - b.tt).to_value(u.s) == 0.0


def _propagated(source: CatalogSource, single: CatalogTable, target: Time, what: str) -> tuple[SkyFrame, str]:
    """Posizione all'epoca ``target`` con ``propagate`` del 13 (che usa ``propagate_position`` del 10)."""
    if source.pm_ra is None or source.pm_dec is None or source.pm_ra_includes_cosdec is None:
        raise MeasuresError("EPOCH_REQUIRED", f"{what}: epoca diversa da {target.jyear_str} e colonne del moto "
                            "proprio non indicate (pm_ra, pm_dec, pm_ra_includes_cosdec): l'epoca non si assume")
    try:
        result = catalogs.propagate(single, target, pm_ra=source.pm_ra, pm_dec=source.pm_dec,
                                    pm_ra_includes_cosdec=source.pm_ra_includes_cosdec, parallax=source.parallax,
                                    radial_velocity=source.radial_velocity, source_epoch=source.source_epoch)
    except CatalogsError as exc:
        raise _from_13(exc, what) from exc
    pos = single.positions
    mode = str(result.table.table[f"{pos.lon}_prop_mode"][0])
    if mode == "missing":
        raise MeasuresError("EPOCH_REQUIRED", f"{what}: moto proprio, posizione o epoca mancanti nella riga: "
                            "nessuna propagazione, mai moto proprio nullo assunto")
    point = _row_position(result.table, f"{pos.lon}_prop", f"{pos.lat}_prop", target, what)
    notes = "; ".join(result.notes)
    return point, f"{what} propagata a {target.jyear_str} ({mode}) da {result.source_epoch}" + (
        f": {notes}" if notes else "")


def auto_distance(selection, unit, *, epoch=None) -> AutoDistance:
    """Distanza tra le due sorgenti di catalogo selezionate (F1), alla stessa epoca e sullo stesso corpo.

    Epoca comune: ``epoch`` se dato, altrimenti quella della prima sorgente; le altre si propagano con il 13/10.
    """
    sources = tuple(selection)
    if len(sources) != 2:
        raise MeasuresError("SELECTION_NOT_TWO_SOURCES", f"selezionate {len(sources)} sorgenti: ne servono 2",
                            selected=len(sources))
    if not all(isinstance(s, CatalogSource) for s in sources):
        raise TypeError("selection: servono due CatalogSource")
    bodies = [s.table.body for s in sources]
    if any(b is None for b in bodies):
        raise MeasuresError("BODY_UNKNOWN", "corpo non dichiarato in una delle tabelle: nessuna misura")
    if bodies[0] != bodies[1]:
        raise MeasuresError("BODY_MISMATCH", f"sorgenti di corpi diversi ({bodies[0]!r}, {bodies[1]!r})")
    names = ("sorgente 1", "sorgente 2")
    rows = [_source_point(s, name) for s, name in zip(sources, names, strict=True)]
    if epoch is None:
        target = rows[0][1].epoch
        target_note = ("nessuna epoca richiesta (epoch non dato): usata l'epoca della prima sorgente selezionata; "
                       "per un'altra epoca comune passare epoch")
    else:
        try:
            target = _to_epoch(epoch, "epoch")
        except CoordinatesWcsError as exc:
            raise _from_10(exc, "epoch") from exc
        target_note = "epoca richiesta (epoch)"
    points, notes = [], [f"epoca usata {target.jyear_str} ({target.scale}): {target_note}"]
    for source, (single, point, epoch_source), name in zip(sources, rows, names, strict=True):
        notes.append(f"{name}: {single.source}, riga {int(source.row)}, epoca da {epoch_source}")
        if _same_epoch(point.epoch, target):
            points.append(point)
        else:
            moved, note = _propagated(source, single, target, name)
            points.append(moved)
            notes.append(note)
    measure = angular_distance(points[0], points[1], unit)
    report = MeasureReport(
        operation="auto_distance", points=measure.report.points, frame=measure.report.frame,
        unit=measure.report.unit, notes=tuple(notes) + measure.report.notes + (f"corpo {bodies[0]}",))
    return AutoDistance(distance=measure.value, segment=Segment(points[0], points[1]), epoch=target,
                        epoch_from_first_source=epoch is None, measure=measure, report=report)
