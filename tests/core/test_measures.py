"""Test del modulo 17 (``mdfiles/17-core-misure.md`` §12).

I valori attesi si ricalcolano nel test con ``astropy`` (e ``numpy``/``scipy`` per i pixel), mai copiati
da altri programmi (regola d'oro n. 8).
"""

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord, angular_separation

from astrotwo.core.coordinates_wcs import SkyFrame
from astrotwo.core.measures import (
    MeasuresError,
    Segment,
    angular_distance,
    angular_offsets,
    apply_offsets,
    offset_position,
    position_angle,
)


def icrs(lon, lat, epoch=None) -> SkyFrame:
    return SkyFrame.from_lonlat(lon * u.deg, lat * u.deg, "icrs", epoch=epoch)


# =============================================================================
# P1 — misure angolari (T1, T2, T8, T9, T13–T15)


def test_t1_known_distance():
    result = angular_distance(icrs(0, 0), icrs(1, 0), "deg")
    expected = angular_separation(0 * u.deg, 0 * u.deg, 1 * u.deg, 0 * u.deg).to_value(u.deg)
    assert result.value.unit == u.deg
    assert abs(result.value.value - expected) < 1e-12
    assert abs(result.value.value - 1.0) < 1e-12
    assert result.report.frame == "icrs" and result.report.unit == "deg"
    # Unità di uscita esplicite.
    assert abs(angular_distance(icrs(0, 0), icrs(1, 0), "arcsec").value.to_value(u.arcsec) - 3600.0) < 1e-8
    assert angular_distance(icrs(0, 0), icrs(1, 0), u.arcmin).value.unit == u.arcmin
    with pytest.raises(ValueError):
        angular_distance(icrs(0, 0), icrs(1, 0), "rad")


def test_t1_random_pairs_match_astropy():
    rng = np.random.default_rng(17)
    for _ in range(50):
        lon1, lon2 = rng.uniform(0, 360, 2)
        lat1, lat2 = np.degrees(np.arcsin(rng.uniform(-1, 1, 2)))
        got = angular_distance(icrs(lon1, lat1), icrs(lon2, lat2), "deg").value.to_value(u.deg)
        expected = SkyCoord(lon1 * u.deg, lat1 * u.deg).separation(SkyCoord(lon2 * u.deg, lat2 * u.deg)).deg
        assert abs(got - expected) < 1e-12


def test_t2_position_angle_north_east():
    north = position_angle(icrs(0, 0), icrs(0, 1))
    east = position_angle(icrs(0, 0), icrs(1, 0))
    origin = SkyCoord(0 * u.deg, 0 * u.deg)
    assert abs(north.value.deg - origin.position_angle(SkyCoord(0 * u.deg, 1 * u.deg)).deg) < 1e-12
    assert abs(east.value.deg - origin.position_angle(SkyCoord(1 * u.deg, 0 * u.deg)).deg) < 1e-12
    assert abs(north.value.deg) < 1e-12 and abs(east.value.deg - 90.0) < 1e-12
    west = position_angle(icrs(10, 0), icrs(9, 0))
    assert abs(west.value.deg - 270.0) < 1e-9  # intervallo [0°, 360°)


def test_t2_second_point_at_pole_is_defined():
    assert abs(position_angle(icrs(100, 80), icrs(250, 90)).value.deg) < 1e-9
    assert abs(position_angle(icrs(100, -80), icrs(0, -90)).value.deg - 180.0) < 1e-9


def test_t8_position_angle_undefined():
    with pytest.raises(MeasuresError) as exc:
        position_angle(icrs(12, 34), icrs(12, 34))
    assert exc.value.code == "PA_UNDEFINED"
    with pytest.raises(MeasuresError) as exc:
        position_angle(icrs(30, 90), icrs(100, 80))  # primo punto al polo: nord locale non definito
    assert exc.value.code == "PA_UNDEFINED"
    with pytest.raises(MeasuresError) as exc:
        position_angle(icrs(0, -90), icrs(0, 90))
    assert exc.value.code == "PA_UNDEFINED"
    with pytest.raises(MeasuresError) as exc:
        position_angle(icrs(10, 20), icrs(190, -20))  # antipodali
    assert exc.value.code == "PA_UNDEFINED"
    # La distanza tra punti identici resta definita (0).
    assert angular_distance(icrs(12, 34), icrs(12, 34), "arcsec").value.value == 0.0


def test_t9_position_angle_along_segment():
    a, b = icrs(45.3, -12.7), icrs(46.1, -11.9)
    assert position_angle(Segment(a, b)).value == position_angle(a, b).value
    with pytest.raises(TypeError):
        position_angle(Segment(a, b), b)
    with pytest.raises(TypeError):
        position_angle(a)


def test_frames_converted_with_module_10():
    a = SkyFrame.from_lonlat(10 * u.deg, 20 * u.deg, "icrs")
    b = SkyFrame.from_lonlat(120 * u.deg, 30 * u.deg, "galactic")
    result = angular_distance(a, b, "deg")
    expected = SkyCoord(10 * u.deg, 20 * u.deg).separation(SkyCoord(120 * u.deg, 30 * u.deg, frame="galactic")).deg
    assert abs(result.value.value - expected) < 1e-9
    assert result.p2.frame_name == "icrs"
    assert any("galactic" in n and "modulo 10" in n for n in result.report.notes)
    # SkyCoord accettato; numeri senza frame no.
    assert angular_distance(SkyCoord(0 * u.deg, 0 * u.deg), icrs(1, 0), "deg").value.unit == u.deg
    with pytest.raises(MeasuresError) as exc:
        angular_distance((0.0, 0.0), icrs(1, 0), "deg")
    assert exc.value.code == "FRAME_UNKNOWN"
    # Frame con equinozio di default di Astropy: l'epoca non si assume (regola del 10).
    with pytest.raises(MeasuresError) as exc:
        angular_distance(SkyCoord(0 * u.deg, 0 * u.deg, frame="fk5"), icrs(1, 0), "deg")
    assert exc.value.code == "EPOCH_REQUIRED"


def test_report_declares_points_and_epochs():
    result = position_angle(icrs(1, 2, epoch=2000.0), icrs(1.5, 2.5, epoch=2016.0))
    text = result.report.description
    assert "icrs" in text and "J2000.000" in text and "J2016.000" in text
    assert any("epoche delle posizioni diverse" in n for n in result.report.notes)
    assert result.report.measured_at.tzinfo is not None


def test_single_point_only():
    many = SkyFrame.from_lonlat([1, 2] * u.deg, [3, 4] * u.deg, "icrs")
    with pytest.raises(ValueError):
        angular_distance(many, icrs(0, 0), "deg")


def test_t13_offsets_round_trip():
    rng = np.random.default_rng(1713)
    for _ in range(20):
        lon1, lon2 = rng.uniform(0, 360, 2)
        lat1, lat2 = rng.uniform(-80, 80, 2)
        a, b = icrs(lon1, lat1), icrs(lon2, lat2)
        result = angular_offsets(a, b)
        dl, db = SkyCoord(lon1 * u.deg, lat1 * u.deg).spherical_offsets_to(SkyCoord(lon2 * u.deg, lat2 * u.deg))
        assert abs((result.d_lon - dl).to_value(u.deg)) < 1e-12 and abs((result.d_lat - db).to_value(u.deg)) < 1e-12
        back = apply_offsets(a, result.d_lon, result.d_lat).position
        assert back.coord.separation(b.coord).deg < 1e-9
    galactic = SkyFrame.from_lonlat(10 * u.deg, 5 * u.deg, "galactic")
    moved = apply_offsets(galactic, 1 * u.arcmin, -2 * u.arcmin).position
    assert moved.frame_name == "galactic"


def test_t14_inverse_calculation():
    start = icrs(150.0, 2.2, epoch=2016.0)
    result = offset_position(start, 30 * u.arcmin, 135 * u.deg)
    expected = SkyCoord(150.0 * u.deg, 2.2 * u.deg).directional_offset_by(135 * u.deg, 30 * u.arcmin)
    assert result.position.coord.separation(expected).deg < 1e-12
    assert result.position.epoch == start.epoch and result.position.frame_name == "icrs"
    assert abs(angular_distance(start, result.position, "deg").value.value - 0.5) < 1e-9
    assert abs(position_angle(start, result.position).value.deg - 135.0) < 1e-9


def test_t15_invalid_offsets():
    p = icrs(10, 10)
    for args in ((-1 * u.deg, 0 * u.deg), (1.0, 0 * u.deg), (1 * u.deg, 0.0), (181 * u.deg, 0 * u.deg),
                 (1 * u.m, 0 * u.deg), (np.nan * u.deg, 0 * u.deg)):
        with pytest.raises(MeasuresError) as exc:
            offset_position(p, *args)
        assert exc.value.code == "OFFSET_INVALID"
    for args in ((1.0, 1 * u.deg), (1 * u.deg, np.inf * u.deg)):
        with pytest.raises(MeasuresError) as exc:
            apply_offsets(p, *args)
        assert exc.value.code == "OFFSET_INVALID"
