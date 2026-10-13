"""Test del modulo 17 (``mdfiles/17-core-misure.md`` §12).

I valori attesi si ricalcolano nel test con ``astropy`` (e ``numpy``/``scipy`` per i pixel), mai copiati
da altri programmi (regola d'oro n. 8).
"""

import dataclasses
import warnings

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import Distance, SkyCoord, angular_separation, offset_by
from astropy.io import fits
from astropy.table import Table
from astropy.time import Time
from astropy.wcs import WCS
from scipy.ndimage import map_coordinates
from scipy.optimize import brentq
from spherical_geometry.polygon import SphericalPolygon

from astrotwo.core.catalogs import confirm_position_columns, read_table
from astrotwo.core.coordinates_wcs import PixelPosition, SkyFrame, pixel_to_sky
from astrotwo.core.images_fits import load_image
from astrotwo.core.measures import (
    ELLIPSE_DEFINITION,
    Arrow,
    CatalogSource,
    Circle,
    Ellipse,
    Freehand,
    MeasuresError,
    Polygon,
    Segment,
    Text,
    angular_distance,
    angular_offsets,
    apply_offsets,
    auto_distance,
    distance_with_profile,
    offset_position,
    position_angle,
    profile_along_line,
    read_pixel,
    tag,
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


# =============================================================================
# P2 — lettura dei pixel, profili, distanza con profilo (T3–T6)

def write_image(tmp_path, data, *, wcs=True, bunit="Jy/beam", name="img.fits"):
    header = fits.Header()
    if wcs:
        ny, nx = data.shape
        header.update({"CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN", "CRVAL1": 150.0, "CRVAL2": 2.0,
                       "CRPIX1": (nx + 1) / 2, "CRPIX2": (ny + 1) / 2, "CDELT1": -1 / 3600, "CDELT2": 1 / 3600,
                       "CUNIT1": "deg", "CUNIT2": "deg", "RADESYS": "ICRS"})
    if bunit is not None:
        header["BUNIT"] = bunit
    path = tmp_path / name
    fits.PrimaryHDU(data, header).writeto(path)
    return load_image(str(path))


def numpy_px(x, y):
    return PixelPosition(x=np.float64(x), y=np.float64(y), convention="numpy")


def test_t3_read_pixel(tmp_path):
    data = np.arange(100, dtype=np.float32).reshape(10, 10) * 1.5
    image = write_image(tmp_path, data)
    reading = read_pixel(image, numpy_px(5, 4))
    assert reading.value == np.float64(data[4, 5]) and reading.value.dtype == np.float64
    assert (reading.x, reading.y) == (5, 4) and reading.unit_label == "Jy/beam"
    # Convenzione FITS (indice da 1): stesso pixel; posizione frazionaria dentro il pixel.
    assert read_pixel(image, PixelPosition(x=np.float64(6), y=np.float64(5), convention="fits")).value == data[4, 5]
    assert read_pixel(image, numpy_px(5.49, 3.51)).value == data[4, 5]
    # Posizione celeste con il WCS: pixel ricalcolato nel test con astropy.wcs.
    sky = pixel_to_sky(image.wcs, 2.2, 7.8, convention="numpy").coords
    assert read_pixel(image, sky).value == data[8, 2]
    window = read_pixel(image, numpy_px(5, 4), half_size=1).window
    assert np.array_equal(window, data[3:6, 4:7].astype(np.float64))
    for x, y in ((-0.6, 0), (9.5, 0), (0, 10)):
        with pytest.raises(MeasuresError) as exc:
            read_pixel(image, numpy_px(x, y))
        assert exc.value.code == "POINT_OUT_OF_IMAGE"
    with pytest.raises(MeasuresError) as exc:
        read_pixel(image, numpy_px(0, 0), half_size=1)
    assert exc.value.code == "POINT_OUT_OF_IMAGE"
    with pytest.raises(TypeError):
        read_pixel(image, (5, 4))


def test_t3_undeclared_unit_and_nonfinite(tmp_path):
    data = np.ones((5, 5))
    data[2, 2] = np.nan
    image = write_image(tmp_path, data, bunit=None)
    reading = read_pixel(image, numpy_px(2, 2))
    assert np.isnan(reading.value) and reading.unit_label == "non dichiarata" and reading.unit is None
    assert "NONFINITE_PIXELS" in dict(reading.report.warnings)


def test_t4_profile_on_gradient(tmp_path):
    yy, xx = np.mgrid[0:20, 0:30]
    data = 3.0 * xx + 7.0 * yy + 1.0  # gradiente noto: la bilineare è esatta
    image = write_image(tmp_path, data)
    profile = profile_along_line(image, numpy_px(2, 3), numpy_px(26, 13), 0.7)
    length = np.hypot(24, 10)
    n = int(np.floor(length / 0.7)) + 1
    t = np.arange(n) * 0.7 / length
    xs, ys = 2 + 24 * t, 3 + 10 * t
    assert len(profile.values) == n
    assert np.allclose(profile.values, 3.0 * xs + 7.0 * ys + 1.0, rtol=0, atol=1e-10)
    # Ricalcolo indipendente con scipy su tutta l'immagine.
    expected = map_coordinates(data.astype(np.float64), np.vstack([ys, xs]), order=1, prefilter=False)
    assert np.allclose(profile.values, expected, rtol=0, atol=1e-12)
    assert profile.offsets.unit == u.pix and profile.sky is not None and len(profile.sky.coord) == n
    table = profile.to_table()
    assert table["value"].unit == u.Unit("Jy/beam") and "interpolation" in table.meta


def test_t4_profile_step_and_bounds(tmp_path):
    image = write_image(tmp_path, np.zeros((10, 10)))
    for step in (0, -1, np.nan, None, "1", 1 * u.arcsec):
        with pytest.raises(MeasuresError) as exc:
            profile_along_line(image, numpy_px(1, 1), numpy_px(5, 5), step)
        assert exc.value.code == "PROFILE_STEP_INVALID"
    with pytest.raises(MeasuresError) as exc:
        profile_along_line(image, numpy_px(1, 1), numpy_px(9.2, 5), 1)
    assert exc.value.code == "POINT_OUT_OF_IMAGE"
    # Il secondo estremo è un campione solo se la lunghezza è multipla del passo; estremi sul bordo ammessi.
    assert len(profile_along_line(image, numpy_px(0, 0), numpy_px(9, 0), 1 * u.pix).values) == 10
    assert len(profile_along_line(image, numpy_px(0, 0), numpy_px(9, 0), 2).values) == 5


def test_t5_distance_with_profile(tmp_path):
    yy, xx = np.mgrid[0:40, 0:40]
    image = write_image(tmp_path, (xx + yy).astype(np.float64))
    a = pixel_to_sky(image.wcs, 5.0, 5.0, convention="numpy").coords
    b = pixel_to_sky(image.wcs, 30.0, 20.0, convention="numpy").coords
    result = distance_with_profile(image, a, b, 1.0)
    assert result.distance == angular_distance(a, b, "deg").value
    length = np.hypot(result.profile.end.x - result.profile.start.x, result.profile.end.y - result.profile.start.y)
    assert len(result.profile.values) == int(np.floor(length)) + 1
    assert abs(length - np.hypot(25, 15)) < 1e-6
    pixels = distance_with_profile(image, numpy_px(5, 5), numpy_px(30, 20), 1.0)
    assert pixels.distance.unit == u.pix and abs(pixels.distance.value - np.hypot(25, 15)) < 1e-12
    assert pixels.report.frame is None and "pixel space" in pixels.report.description
    assert "distance" in result.to_table().meta
    with pytest.raises(ValueError):
        distance_with_profile(image, a, numpy_px(30, 20), 1.0)


def test_t6_image_without_wcs(tmp_path):
    data = np.arange(25, dtype=np.float64).reshape(5, 5)
    image = write_image(tmp_path, data, wcs=False)
    for call in (lambda: read_pixel(image, icrs(150, 2)),
                 lambda: distance_with_profile(image, icrs(150, 2), icrs(150.001, 2), 1.0),
                 lambda: profile_along_line(image, icrs(150, 2), icrs(150.001, 2), 1.0)):
        with pytest.raises(MeasuresError) as exc:
            call()
        assert exc.value.code == "NO_WCS"
    assert read_pixel(image, numpy_px(1, 3)).value == data[3, 1]
    assert distance_with_profile(image, numpy_px(0, 0), numpy_px(4, 0), 1).profile.sky is None


# =============================================================================
# P3 — forme e tag (T7, T16–T19)


def test_t7_circle_contains():
    center = icrs(83.6, 22.0)
    circle = Circle(center, 30 * u.arcmin)
    rng = np.random.default_rng(7)
    for _ in range(40):
        lon, lat = 83.6 + rng.uniform(-1, 1), 22.0 + rng.uniform(-1, 1)
        expected = SkyCoord(83.6 * u.deg, 22.0 * u.deg).separation(SkyCoord(lon * u.deg, lat * u.deg)) <= 30 * u.arcmin
        assert circle.contains(icrs(lon, lat)).value == bool(expected)
    # Punti a 29,9' e 30,1' dal centro (calcolo inverso di Astropy).
    for distance, expected in ((29.9, True), (30.1, False)):
        lon, lat = offset_by(83.6 * u.deg, 22.0 * u.deg, 40 * u.deg, distance * u.arcmin)
        assert circle.contains(icrs(lon.deg, lat.deg)).value is expected
    area = circle.area()
    assert area.value.unit == u.sr
    assert abs(area.value.value / (2 * np.pi * (1 - np.cos(np.radians(0.5)))) - 1) < 1e-12
    # Punto in un altro frame: convertito con il modulo 10, nota nel report.
    galactic = SkyFrame(coord=SkyCoord(83.6 * u.deg, 22.0 * u.deg).galactic)
    result = circle.contains(galactic)
    assert result.value and any("modulo 10" in n for n in result.report.notes)
    for radius in (0 * u.deg, 180 * u.deg, 1.0, np.nan * u.deg, 1 * u.m):
        with pytest.raises(MeasuresError) as exc:
            Circle(center, radius)
        assert exc.value.code == "SHAPE_INVALID"


def test_t16_spherical_polygon():
    octant = Polygon([icrs(0, 0), icrs(90, 0), icrs(0, 90)])
    assert abs(octant.area().value.to_value(u.sr) - 4 * np.pi / 8) < 1e-12
    assert octant.contains(icrs(30, 30)).value and not octant.contains(icrs(120, 30)).value
    assert not octant.contains(icrs(30, -10)).value
    assert "spherical-geometry" in octant.area().report.provenance
    # Interno di default: la regione più piccola; con inside, la regione che lo contiene.
    ring = [icrs(lon, -30) for lon in range(0, 360, 45)]
    small = Polygon(ring)
    assert small.contains(icrs(0, -90)).value and not small.contains(icrs(0, 90)).value
    large = Polygon(ring, inside=icrs(0, 90))
    assert large.contains(icrs(0, 90)).value
    assert abs(small.area().value.value + large.area().value.value - 4 * np.pi) < 1e-9
    # Vertici ripetuti tolti e dichiarati; stesso risultato.
    repeated = Polygon([icrs(0, 0), icrs(10, 0), icrs(10, 0), icrs(10, 10), icrs(0, 10), icrs(0, 0)])
    plain = Polygon([icrs(0, 0), icrs(10, 0), icrs(10, 10), icrs(0, 10)])
    assert repeated.area().value == plain.area().value
    assert any("ripetuti" in n for n in repeated.area().report.notes)
    # Ricalcolo indipendente con la libreria.
    expected = SphericalPolygon.from_lonlat([0, 10, 10, 0], [0, 0, 10, 10]).area()
    assert abs(plain.area().value.value - expected) < 1e-15
    for vertices in ([icrs(0, 0), icrs(10, 10), icrs(0, 10), icrs(10, 0)],  # si interseca
                     [icrs(0, 0), icrs(10, 0)],  # meno di 3 vertici
                     [icrs(0, 0), icrs(1, 0), icrs(2, 0)]):  # su un cerchio massimo
        with pytest.raises(MeasuresError) as exc:
            Polygon(vertices)
        assert exc.value.code == "SHAPE_INVALID"
    with pytest.raises(MeasuresError) as exc:
        Polygon([(0.0, 0.0), icrs(1, 0), icrs(1, 1)])
    assert exc.value.code == "FRAME_UNKNOWN"


def test_t16_freehand():
    points = [icrs(0, 0), icrs(5, 0), icrs(6, 4), icrs(1, 6)]
    closed = Freehand(points, closed=True)
    assert closed.area().value == Polygon(points).area().value and closed.area().shape == "freehand"
    assert closed.contains(icrs(3, 2)).value
    opened = Freehand(points)
    for call in (opened.area, lambda: opened.contains(icrs(3, 2))):
        with pytest.raises(MeasuresError) as exc:
            call()
        assert exc.value.code == "OPERATION_UNSUPPORTED"


def tangent_plane_contains(center, a_deg, b_deg, pa_deg, lon, lat):
    """Ellisse nel piano tangente (proiezione gnomonica TAN di astropy.wcs), solo per il confronto di T17."""
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = center
    wcs.wcs.crpix = [0, 0]
    wcs.wcs.cdelt = [1, 1]  # coordinate intermedie in gradi sul piano tangente
    x, y = wcs.wcs_world2pix([[lon, lat]], 0)[0]
    east, north = -x, y  # asse x di RA---TAN crescente verso ovest con CDELT1 > 0
    pa = np.radians(pa_deg)
    major = north * np.cos(pa) + east * np.sin(pa)
    minor = -north * np.sin(pa) + east * np.cos(pa)
    return (major / a_deg) ** 2 + (minor / b_deg) ** 2 <= 1


def test_t17_spherical_versus_tangent_plane_ellipse():
    center = (40.0, 10.0)
    ellipse = Ellipse(icrs(*center), 30 * u.deg, 10 * u.deg, 25 * u.deg)
    lon, lat = offset_by(40 * u.deg, 10 * u.deg, 25 * u.deg, 0.99 * 30 * u.deg)
    point = icrs(lon.wrap_at(360 * u.deg).deg, lat.deg)
    result = ellipse.contains(point)
    assert result.value is True
    assert not tangent_plane_contains(center, 30.0, 10.0, 25.0, lon.deg, lat.deg)
    assert ELLIPSE_DEFINITION in result.report.notes
    area = ellipse.area()
    assert ELLIPSE_DEFINITION in area.report.notes
    planar = np.pi * np.radians(30) * np.radians(10)
    assert abs(area.value.value - planar) / planar > 0.01
    # Ellisse piccola: le definizioni coincidono quasi (differenza relativa dell'ordine di a², qui ~1e-9).
    small = Ellipse(icrs(*center), 10 * u.arcsec, 5 * u.arcsec, 25 * u.deg).area()
    planar_small = np.pi * np.radians(10 / 3600) * np.radians(5 / 3600)
    assert abs(small.value.value - planar_small) / planar_small < 1e-8


def test_t17_ellipse_vertices_and_foci():
    ellipse = Ellipse(icrs(200, -35), 2 * u.deg, 1 * u.deg, 70 * u.deg)
    for pa, distance in ((70, 2.0), (250, 2.0), (160, 1.0), (340, 1.0)):
        for factor, expected in ((1 - 1e-9, True), (1 + 1e-9, False)):
            lon, lat = offset_by(200 * u.deg, -35 * u.deg, pa * u.deg, factor * distance * u.deg)
            assert ellipse.contains(icrs(lon.deg, lat.deg)).value is expected
    f1, f2 = ellipse.foci
    c = np.degrees(np.arccos(np.cos(np.radians(2)) / np.cos(np.radians(1))))  # cos c = cos a / cos b
    assert abs(SkyCoord(200 * u.deg, -35 * u.deg).separation(f1.coord).deg - c) < 1e-9
    assert abs(position_angle(icrs(200, -35), f1).value.deg - 70) < 1e-9
    for a, b in ((1 * u.deg, 2 * u.deg), (90 * u.deg, 1 * u.deg), (1 * u.deg, 0 * u.deg), (1.0, 0.5 * u.deg)):
        with pytest.raises(MeasuresError) as exc:
            Ellipse(icrs(0, 0), a, b, 0 * u.deg)
        assert exc.value.code == "SHAPE_INVALID"


def test_t18_ellipse_area():
    # a = b: calotta 2π(1 − cos a), entro la precisione dichiarata.
    for radius in (0.01, 5.0, 60.0):
        circle_like = Ellipse(icrs(10, 20), radius * u.deg, radius * u.deg, 0 * u.deg).area()
        cap = 4 * np.pi * np.sin(np.radians(radius) / 2) ** 2  # 2π(1 − cos a) senza cancellazione
        assert abs(circle_like.value.value - cap) <= circle_like.error.value + 1e-13 * cap
    # Ellisse generica: poligono di molti punti del bordo trovati qui con brentq (ricalcolo indipendente).
    a, b, pa = 20.0, 8.0, 30.0
    ellipse = Ellipse(icrs(150, 40), a * u.deg, b * u.deg, pa * u.deg)
    result = ellipse.area()
    assert result.error.value <= 1e-10 * result.value.value and result.samples >= 64
    c = np.arccos(np.cos(np.radians(a)) / np.cos(np.radians(b)))
    foci = [offset_by(150 * u.deg, 40 * u.deg, (pa + turn) * u.deg, c * u.rad) for turn in (0, 180)]

    def excess(theta, rho):
        lon, lat = offset_by(150 * u.deg, 40 * u.deg, theta * u.rad, rho * u.rad)
        return sum(angular_separation(lon, lat, *f).to_value(u.rad) for f in foci) - 2 * np.radians(a)

    def polygon_area(n):
        thetas = np.linspace(0, 2 * np.pi, n, endpoint=False)
        rhos = np.array([brentq(lambda r, t=t: excess(t, r), 0, 2 * np.radians(a), xtol=1e-15) for t in thetas])
        lon, lat = offset_by(150 * u.deg, 40 * u.deg, thetas * u.rad, rhos * u.rad)
        return SphericalPolygon.from_lonlat(lon.deg, lat.deg, center=(150, 40)).area()

    # Lati di cerchio massimo: errore in 1/n² e 1/n⁴, tolti con due passi di estrapolazione di Richardson.
    areas = [polygon_area(n) for n in (150, 300, 600)]
    assert abs(areas[2] - result.value.value) / result.value.value < 1e-4
    first = [(4 * areas[i + 1] - areas[i]) / 3 for i in range(2)]
    extrapolated = (16 * first[1] - first[0]) / 15
    assert abs(extrapolated - result.value.value) / result.value.value < 1e-9
    assert any("trapezi" in n and "stima dell'errore" in n for n in result.report.notes)
    # Ellisse molto allungata: precisione non raggiunta → errore, nessun numero.
    with pytest.raises(MeasuresError) as exc:
        Ellipse(icrs(0, 0), 89 * u.deg, 0.01 * u.deg, 0 * u.deg).area()
    assert exc.value.code == "AREA_PRECISION_NOT_REACHED" and "error" in exc.value.details


def test_t19_arrow_text_tag():
    arrow = Arrow(icrs(1, 1), icrs(2, 2))
    text = Text(icrs(1, 1), "M1")
    for shape in (arrow, text):
        for call in (shape.area, lambda s=shape: s.contains(icrs(1, 1))):
            with pytest.raises(MeasuresError) as exc:
                call()
            assert exc.value.code == "OPERATION_UNSUPPORTED"
        assert shape.describe()["shape"] in ("arrow", "text")
    with pytest.raises(ValueError):
        Text(icrs(1, 1), " ")
    marker = tag(icrs(83.6, 22.0), "Crab")
    assert marker.label == "Crab" and marker.point.frame_name == "icrs" and marker.created_at.tzinfo is not None
    with pytest.raises(ValueError):
        tag(icrs(1, 1), "")
    with pytest.raises(MeasuresError) as exc:
        tag((1.0, 1.0), "x")
    assert exc.value.code == "FRAME_UNKNOWN"


# =============================================================================
# P3 — distance_to (D17-8, decisa il 2026-10-13)


def _brute_distance_to_polygon(lon, lat, vertices):
    """Minimo ricalcolato con Astropy: punti degli archi con offset_by, raffinato con scipy (indipendente)."""
    from scipy.optimize import minimize_scalar

    point = SkyCoord(lon * u.deg, lat * u.deg)
    best = np.inf
    for (l1, b1), (l2, b2) in zip(vertices, vertices[1:] + vertices[:1]):
        start = SkyCoord(l1 * u.deg, b1 * u.deg)
        end = SkyCoord(l2 * u.deg, b2 * u.deg)
        pa, length = start.position_angle(end), start.separation(end)

        def along(f):
            lo, la = offset_by(start.ra, start.dec, pa, f * length)
            return angular_separation(lo, la, point.ra, point.dec).to_value(u.deg)

        grid = np.linspace(0.0, 1.0, 2001)
        values = along(grid)
        i = int(np.argmin(values))
        refined = minimize_scalar(along, bounds=(grid[max(i - 1, 0)], grid[min(i + 1, 2000)]), method="bounded",
                                  options={"xatol": 1e-14})
        best = min(best, values.min(), float(refined.fun))
    return best


def test_t20_distance_circles_exact():
    c1, c2 = Circle(icrs(10, 20), 1 * u.deg), Circle(icrs(14, 22), 0.5 * u.deg)
    separation = SkyCoord(10 * u.deg, 20 * u.deg).separation(SkyCoord(14 * u.deg, 22 * u.deg)).to_value(u.deg)
    result = c1.distance_to(c2)
    assert result.value.unit == u.deg
    assert result.value.value == pytest.approx(separation - 1.5, abs=1e-12)
    assert "D17-8" in result.report.description
    assert c2.distance_to(c1).value.value == pytest.approx(separation - 1.5, abs=1e-12)
    assert c1.distance_to(Circle(icrs(11, 20), 1 * u.deg)).value.value == 0.0  # sovrapposti
    assert c1.distance_to(icrs(10.2, 20.1)).value.value == 0.0  # punto dentro
    far = icrs(30, -10)
    expected = SkyCoord(10 * u.deg, 20 * u.deg).separation(SkyCoord(30 * u.deg, -10 * u.deg)).to_value(u.deg) - 1
    assert c1.distance_to(far).value.value == pytest.approx(expected, abs=1e-12)


def test_t20_distance_polygon_point_matches_brute_force():
    vertices = [(10, -5), (25, -3), (22, 12), (8, 6)]
    polygon = Polygon([icrs(*v) for v in vertices])
    for lon, lat in [(0, 0), (40, 30), (16, -20), (17, 40), (5, 5)]:
        result = polygon.distance_to(icrs(lon, lat))
        assert result.value.value == pytest.approx(_brute_distance_to_polygon(lon, lat, vertices), abs=1e-9)
        assert "SphericalPolygon" in result.report.description
    assert polygon.distance_to(icrs(15, 2)).value.value == 0.0  # punto dentro


def test_t20_distance_between_polygons_and_circle_polygon():
    a_vertices = [(0, 0), (10, 0), (10, 10), (0, 10)]
    b_vertices = [(20, 2), (30, 4), (25, 15)]
    a, b = Polygon([icrs(*v) for v in a_vertices]), Polygon([icrs(*v) for v in b_vertices])
    expected = min(min(_brute_distance_to_polygon(lon, lat, b_vertices) for lon, lat in a_vertices),
                   min(_brute_distance_to_polygon(lon, lat, a_vertices) for lon, lat in b_vertices))
    assert a.distance_to(b).value.value == pytest.approx(expected, abs=1e-9)
    assert b.distance_to(a).value.value == pytest.approx(expected, abs=1e-9)
    crossing = Polygon([icrs(358, 4), icrs(12, 4), icrs(12, 6), icrs(358, 6)])  # solo i lati si incrociano
    nested = Polygon([icrs(4, 4), icrs(6, 4), icrs(6, 6)])
    assert a.distance_to(crossing).value.value == 0.0 and a.distance_to(nested).value.value == 0.0
    circle = Circle(icrs(40, 5), 2 * u.deg)
    to_center = _brute_distance_to_polygon(40, 5, b_vertices)
    assert circle.distance_to(b).value.value == pytest.approx(to_center - 2, abs=1e-9)
    assert b.distance_to(circle).value.value == pytest.approx(to_center - 2, abs=1e-9)
    assert Circle(icrs(5, 5), 1 * u.deg).distance_to(a).value.value == 0.0
    closed = Freehand([icrs(*v) for v in b_vertices], closed=True)
    assert closed.distance_to(a).value.value == pytest.approx(expected, abs=1e-9)


def test_t20_distance_other_frame_converted():
    gal = SkyCoord(10 * u.deg, 20 * u.deg).galactic
    circle_gal = Circle(SkyFrame(coord=gal), 1 * u.deg)
    polygon = Polygon([icrs(20, 18), icrs(25, 18), icrs(25, 24), icrs(20, 24)])
    in_icrs = Circle(icrs(10, 20), 1 * u.deg).distance_to(polygon).value.value
    result = circle_gal.distance_to(polygon)
    assert result.value.value == pytest.approx(in_icrs, abs=1e-9)
    assert result.report.frame == "galactic" and "convertito" in result.report.description


def test_t20_distance_unsupported_shapes_d17_9():
    circle = Circle(icrs(0, 0), 1 * u.deg)
    others = (Ellipse(icrs(5, 0), 2 * u.deg, 1 * u.deg, 0 * u.deg), Arrow(icrs(1, 1), icrs(2, 2)),
              Text(icrs(1, 1), "M1"), Freehand([icrs(5, 0), icrs(6, 1), icrs(7, 0)]))
    for shape in others:
        for call in (lambda s=shape: s.distance_to(circle), lambda s=shape: circle.distance_to(s)):
            with pytest.raises(MeasuresError) as exc:
                call()
            assert exc.value.code == "OPERATION_UNSUPPORTED" and "D17-9" in exc.value.message


# =============================================================================
# P4 — distanza automatica tra due sorgenti di catalogo (T10–T12)


def catalog(tmp_path, name, ra, dec, *, epoch=None, pm=None, plx=None):
    t = Table()
    t["RA"] = np.asarray(ra, dtype=np.float64) * u.deg
    t["DE"] = np.asarray(dec, dtype=np.float64) * u.deg
    t["RA"].meta["ucd"] = "pos.eq.ra;meta.main"
    t["DE"].meta["ucd"] = "pos.eq.dec;meta.main"
    if epoch is not None:
        t["ep"] = np.full(len(t), epoch) * u.yr
        t["ep"].meta["ucd"] = "meta.ref;time.epoch"
    if pm is not None:
        t["pmRA"] = np.asarray(pm[0], dtype=np.float64) * u.mas / u.yr
        t["pmDE"] = np.asarray(pm[1], dtype=np.float64) * u.mas / u.yr
    if plx is not None:
        t["plx"] = np.asarray(plx, dtype=np.float64) * u.mas
    path = tmp_path / f"{name}.csv"
    path.write_text("x,y\n1,2\n")
    return confirm_position_columns(dataclasses.replace(read_table(path), table=t), "RA", "DE", "icrs")


def test_t10_auto_distance(tmp_path):
    cat = catalog(tmp_path, "a", [10.0, 10.2, 11.0], [-5.0, -4.9, -5.5], epoch=2016.0)
    result = auto_distance([CatalogSource(cat, 0), CatalogSource(cat, 2)], "arcsec")
    expected = SkyCoord(10.0 * u.deg, -5.0 * u.deg).separation(SkyCoord(11.0 * u.deg, -5.5 * u.deg))
    assert abs((result.distance - expected).to_value(u.arcsec)) < 1e-9
    assert result.segment.start.lon.to_value(u.deg) == 10.0 and result.segment.end.lat.to_value(u.deg) == -5.5
    assert result.epoch.jyear == 2016.0 and "J2016.000" in result.report.description
    # Nessuna epoca richiesta: il report dice che è quella della prima sorgente.
    assert result.epoch_from_first_source
    assert "nessuna epoca richiesta" in result.report.description and "prima sorgente" in result.report.description
    requested = auto_distance([CatalogSource(cat, 0), CatalogSource(cat, 2)], "arcsec", epoch=2016.0)
    assert not requested.epoch_from_first_source and "epoca richiesta" in requested.report.description


def test_t11_selection_not_two(tmp_path):
    cat = catalog(tmp_path, "a", [10.0, 10.2, 11.0], [-5.0, -4.9, -5.5], epoch=2016.0)
    for selection in ([CatalogSource(cat, 0)], [CatalogSource(cat, i) for i in range(3)], []):
        with pytest.raises(MeasuresError) as exc:
            auto_distance(selection, "arcsec")
        assert exc.value.code == "SELECTION_NOT_TWO_SOURCES" and exc.value.details["selected"] == len(selection)


def test_t12_different_epochs_propagated(tmp_path):
    a = catalog(tmp_path, "a", [150.0], [2.0], epoch=2000.0, pm=([500.0], [-300.0]), plx=[20.0])
    b = catalog(tmp_path, "b", [150.01], [2.01], epoch=2016.0)
    result = auto_distance([CatalogSource(b, 0), CatalogSource(a, 0, pm_ra="pmRA", pm_dec="pmDE",
                                                                pm_ra_includes_cosdec=True, parallax="plx")], "arcsec")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        moved = SkyCoord(ra=150.0 * u.deg, dec=2.0 * u.deg, pm_ra_cosdec=500 * u.mas / u.yr, pm_dec=-300 * u.mas / u.yr,
                         distance=Distance(parallax=20 * u.mas), obstime=Time(2000.0, format="jyear", scale="tt"),
                         ).apply_space_motion(new_obstime=Time(2016.0, format="jyear", scale="tt"))
    expected = SkyCoord(150.01 * u.deg, 2.01 * u.deg).separation(SkyCoord(moved.ra, moved.dec))
    assert abs((result.distance - expected).to_value(u.arcsec)) < 1e-6
    assert result.epoch.jyear == 2016.0
    assert any("propagata" in n for n in result.report.notes)
    # Senza colonne del moto proprio: l'epoca non si assume.
    with pytest.raises(MeasuresError) as exc:
        auto_distance([CatalogSource(b, 0), CatalogSource(a, 0)], "arcsec")
    assert exc.value.code == "EPOCH_REQUIRED"
    # Epoca non nei metadati e non data.
    plain = catalog(tmp_path, "c", [150.0], [2.0])
    with pytest.raises(MeasuresError) as exc:
        auto_distance([CatalogSource(b, 0), CatalogSource(plain, 0)], "arcsec")
    assert exc.value.code == "EPOCH_REQUIRED"
    given = auto_distance([CatalogSource(b, 0), CatalogSource(plain, 0, source_epoch=2016.0)], "arcsec")
    assert given.epoch.jyear == 2016.0
    # Epoca richiesta esplicitamente: entrambe propagate se diverse.
    with pytest.raises(MeasuresError) as exc:
        auto_distance([CatalogSource(b, 0), CatalogSource(a, 0)], "arcsec", epoch=2000.0)
    assert exc.value.code == "EPOCH_REQUIRED"  # b non ha il moto proprio


def test_auto_distance_body(tmp_path):
    a = catalog(tmp_path, "a", [10.0], [0.0], epoch=2016.0)
    mars = dataclasses.replace(catalog(tmp_path, "m", [10.0], [0.0], epoch=2016.0), body="Mars")
    unknown = dataclasses.replace(a, body=None)
    with pytest.raises(MeasuresError) as exc:
        auto_distance([CatalogSource(a, 0), CatalogSource(mars, 0)], "deg")
    assert exc.value.code == "BODY_MISMATCH"
    with pytest.raises(MeasuresError) as exc:
        auto_distance([CatalogSource(a, 0), CatalogSource(unknown, 0)], "deg")
    assert exc.value.code == "BODY_UNKNOWN"
