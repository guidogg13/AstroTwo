"""Misure angolari e strumenti di misura.

Specifica: ``mdfiles/17-core-misure.md`` (stato ``approvato``).

Il modulo si scrive in 4 parti (decisione del proprietario del 2026-10-12):
P1 misure angolari (distanza, angolo di posizione, offset e calcolo inverso),
P2 lettura dei pixel e profili, P3 forme e tag (ferma su D17-7), P4 distanza
automatica tra due sorgenti di catalogo.

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

from dataclasses import dataclass, field
from datetime import UTC, datetime

import astropy
import astropy.units as u
import numpy as np
from astropy.coordinates import Angle, SkyCoord

from astrotwo.core.catalogs import skydist
from astrotwo.core.coordinates_wcs import CoordinatesWcsError, SkyFrame, convert_coordinates

__all__ = [
    "DISTANCE_UNITS",
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
