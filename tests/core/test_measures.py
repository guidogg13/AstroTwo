"""Test del modulo 17 (``mdfiles/17-core-misure.md`` §12).

I valori attesi si ricalcolano nel test con ``astropy`` (e ``numpy``/``scipy`` per i pixel), mai copiati
da altri programmi (regola d'oro n. 8).
"""

import dataclasses
import warnings

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import Distance, SkyCoord, angular_separation
from astropy.io import fits
from astropy.table import Table
from astropy.time import Time
from scipy.ndimage import map_coordinates

from astrotwo.core.catalogs import confirm_position_columns, read_table
from astrotwo.core.coordinates_wcs import PixelPosition, SkyFrame, pixel_to_sky
from astrotwo.core.images_fits import load_image
from astrotwo.core.measures import (
    CatalogSource,
    MeasuresError,
    Segment,
    angular_distance,
    angular_offsets,
    apply_offsets,
    auto_distance,
    distance_with_profile,
    offset_position,
    position_angle,
    profile_along_line,
    read_pixel,
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


def test_t3_unitless_and_nonfinite(tmp_path):
    data = np.ones((5, 5))
    data[2, 2] = np.nan
    image = write_image(tmp_path, data, bunit=None)
    reading = read_pixel(image, numpy_px(2, 2))
    assert np.isnan(reading.value) and reading.unit_label == "unitless"
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
