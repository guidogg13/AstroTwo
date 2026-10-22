# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test di accettazione del modulo 10 (``mdfiles/10-core-coordinate-wcs.md`` §12).

I valori attesi sono sempre ricalcolati nel test con Astropy (o con
l'aritmetica esatta della regola DC7); nessun numero atteso è scritto a
memoria. Fa eccezione T12, che per specifica si confronta con il riferimento
contenuto nel file di prova (posizione dell'oggetto scritta da STScI).
"""

from __future__ import annotations

import warnings

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import Distance, SkyCoord
from astropy.io import fits
from astropy.time import Time
from astropy.utils.data import get_pkg_data_filename
from astropy.wcs import WCS, FITSFixedWarning

from astrotwo.core import coordinates_wcs as cw
from astrotwo.core.coordinates_wcs import (
    SUPPORTED_PROJECTIONS,
    CalibrationThresholds,
    CoordinatesWcsError,
    SkyFrame,
    astrometric_calibration,
    choose_grid_spacing,
    choose_projection,
    compute_grid_lines,
    convert_coordinates,
    convert_pixel_convention,
    pixel_to_sky,
    propagate_position,
    sky_to_pixel,
    wcs_from_header,
)

SHAPE = (200, 200)
ZPN_PARAMS = {1: 1.0, 3: 0.2}


def make_header(projection, crval=(10.0, 41.0), rotation_deg=0.0, scale=0.01, shape=SHAPE, pv=None):
    """Header di prova con matrice CD (scala in gradi per pixel)."""
    if projection == "NCP" and crval == (10.0, 41.0):
        crval = (10.0, 60.0)
    if projection == "ZPN" and pv is None:
        pv = ZPN_PARAMS
    c, s = np.cos(np.radians(rotation_deg)), np.sin(np.radians(rotation_deg))
    h = fits.Header()
    h["NAXIS"] = 2
    h["NAXIS1"], h["NAXIS2"] = shape
    h["CTYPE1"], h["CTYPE2"] = f"RA---{projection}", f"DEC--{projection}"
    h["RADESYS"] = "ICRS"
    h["CUNIT1"] = h["CUNIT2"] = "deg"
    h["CRPIX1"], h["CRPIX2"] = shape[0] / 2 + 0.5, shape[1] / 2 + 0.5
    h["CRVAL1"], h["CRVAL2"] = crval
    h["CD1_1"], h["CD1_2"] = -scale * c, scale * s
    h["CD2_1"], h["CD2_2"] = scale * s, scale * c
    for m, value in (pv or {}).items():
        h[f"PV2_{m}"] = value
    return h


def astropy_wcs(header):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        return WCS(header)


def expect_error(code, func, *args, **kwargs):
    with pytest.raises(CoordinatesWcsError) as info:
        func(*args, **kwargs)
    assert info.value.code == code, info.value
    return info.value


# --- T1 ---------------------------------------------------------------------


def test_t1_roundtrip_icrs_galactic_icrs():
    rng = np.random.default_rng(12345)
    ra = rng.uniform(0.0, 360.0, 1000) * u.deg
    dec = np.degrees(np.arcsin(rng.uniform(-1.0, 1.0, 1000))) * u.deg
    start = SkyFrame.from_lonlat(ra, dec, "icrs")
    gal = convert_coordinates(start, "galactic")
    back = convert_coordinates(gal, "icrs")
    # Intermedio ricalcolato con Astropy.
    expected_gal = SkyCoord(ra, dec, frame="icrs").galactic
    assert gal.frame_name == "galactic"
    assert np.max(gal.coord.separation(expected_gal).deg) < 1e-9
    assert np.max(back.coord.separation(start.coord).deg) < 1e-9


# --- T2 ---------------------------------------------------------------------

# Posizione ICRS di M31 su SIMBAD (fonte scelta dal tester): solo dato
# d'ingresso; la seconda lettura da SIMBAD è il test di rete qui sotto.
M31_RA, M31_DEC = "00h42m44.330s", "+41d16m07.50s"


def test_t2_known_conversion_icrs_to_galactic():
    ref = SkyCoord(M31_RA, M31_DEC, frame="icrs")
    pos = SkyFrame.from_lonlat(ref.ra, ref.dec, "icrs")
    out = convert_coordinates(pos, "galactic")
    expected = ref.galactic
    assert abs(out.lon - expected.l).to_value(u.deg) < 1e-9
    assert abs(out.lat - expected.b).to_value(u.deg) < 1e-9


@pytest.mark.network
def test_t2_network_simbad_second_reading():
    from astroquery.simbad import Simbad

    table = Simbad.query_object("M31")
    live = SkyCoord(table["ra"][0], table["dec"][0], unit="deg", frame="icrs")
    assert live.separation(SkyCoord(M31_RA, M31_DEC, frame="icrs")).arcsec < 0.01


# --- T3 ---------------------------------------------------------------------


def test_t3_roundtrip_pixel_sky():
    solution = wcs_from_header(make_header("TAN", rotation_deg=17.0))
    rng = np.random.default_rng(3)
    x, y = rng.uniform(0, 199, 500), rng.uniform(0, 199, 500)
    sky = pixel_to_sky(solution, x, y, convention="numpy")
    back = sky_to_pixel(solution, sky.coords, convention="numpy")
    assert back.pixels.convention == "numpy"
    assert np.max(np.hypot(back.pixels.x - x, back.pixels.y - y)) < 1e-6
    # Ricalcolo con astropy.wcs.
    ra, dec = astropy_wcs(make_header("TAN", rotation_deg=17.0)).all_pix2world(x, y, 0)
    assert np.max(sky.coords.coord.separation(SkyCoord(ra, dec, unit="deg")).deg) < 1e-12


# --- T4 ---------------------------------------------------------------------

# Stella di Barnard: fonte dei sei valori qui sotto (posizione, moto proprio, parallasse, velocità radiale) è il
# catalogo Gaia DR3 (ESA/Gaia/DPAC; Gaia Collaboration, Vallenari et al. 2023, A&A 674, A1), source_id
# 4472832130942575872, epoca J2016.0 (restano nel test per decisione del proprietario del 2026-10-22).
# TCB: dati d'ingresso scelti dal tester; l'atteso è ricalcolato con Astropy.
# La corrispondenza con l'archivio Gaia si controlla nel test di rete.
BARNARD = dict(
    ra=269.44850252543836 * u.deg,
    dec=4.739420051112412 * u.deg,
    pm_ra_cosdec=-801.551 * u.mas / u.yr,
    pm_dec=10362.394 * u.mas / u.yr,
    parallax=546.9759 * u.mas,
    radial_velocity=-110.11 * u.km / u.s,
)
GAIA_EPOCH = Time(2016.0, format="jyear", scale="tcb")


@pytest.mark.parametrize("with_rv", [False, True])
def test_t4_propagation_matches_apply_space_motion(with_rv):
    pos = SkyFrame.from_lonlat(BARNARD["ra"], BARNARD["dec"], "icrs", epoch=GAIA_EPOCH)
    target = Time(2026.0, format="jyear", scale="tcb")
    rv = BARNARD["radial_velocity"] if with_rv else None
    out = propagate_position(
        pos,
        pm_ra_cosdec=BARNARD["pm_ra_cosdec"],
        pm_dec=BARNARD["pm_dec"],
        parallax=BARNARD["parallax"],
        target_epoch=target,
        radial_velocity=rv,
    )
    kwargs = dict(
        ra=BARNARD["ra"], dec=BARNARD["dec"], pm_ra_cosdec=BARNARD["pm_ra_cosdec"], pm_dec=BARNARD["pm_dec"],
        distance=Distance(parallax=BARNARD["parallax"]), obstime=GAIA_EPOCH, frame="icrs",
    )
    if with_rv:
        kwargs["radial_velocity"] = rv
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        expected = SkyCoord(**kwargs).apply_space_motion(new_obstime=target)
    assert out.position.coord.separation(expected).deg < 1e-9
    assert out.target_epoch == target and out.position.epoch == target
    assert out.source_epoch == GAIA_EPOCH
    if not with_rv:
        assert any("velocità radiale non fornita" in n for n in out.notes)
    # Spostamento reale: ~10 anni × ~10.4″/anno.
    assert out.position.coord.separation(pos.coord).arcsec > 90


def test_t4_epoch_and_motion_never_assumed():
    no_epoch = SkyFrame.from_lonlat(BARNARD["ra"], BARNARD["dec"], "icrs")
    common = dict(pm_ra_cosdec=BARNARD["pm_ra_cosdec"], pm_dec=BARNARD["pm_dec"], parallax=BARNARD["parallax"])
    expect_error("EPOCH_REQUIRED", propagate_position, no_epoch, target_epoch=2026.0, **common)
    with_epoch = SkyFrame.from_lonlat(BARNARD["ra"], BARNARD["dec"], "icrs", epoch=GAIA_EPOCH)
    expect_error(
        "EPOCH_REQUIRED", propagate_position, with_epoch, pm_ra_cosdec=None, pm_dec=BARNARD["pm_dec"],
        parallax=BARNARD["parallax"], target_epoch=2026.0,
    )
    expect_error("EPOCH_REQUIRED", propagate_position, with_epoch, target_epoch=None, **common)


@pytest.mark.network
def test_t4_network_gaia_values():
    from astroquery.gaia import Gaia

    job = Gaia.launch_job(
        "SELECT ra, dec, pmra, pmdec, parallax, radial_velocity FROM gaiadr3.gaia_source "
        "WHERE source_id = 4472832130942575872"
    )
    row = job.get_results()[0]
    assert abs(row["ra"] - BARNARD["ra"].value) < 1e-9
    assert abs(row["dec"] - BARNARD["dec"].value) < 1e-9
    assert abs(row["pmra"] - BARNARD["pm_ra_cosdec"].value) < 1e-2
    assert abs(row["pmdec"] - BARNARD["pm_dec"].value) < 1e-2
    assert abs(row["parallax"] - BARNARD["parallax"].value) < 1e-3


# --- T5 ---------------------------------------------------------------------


def simbad_table(main_id="M  31", ra=10.684708333333333, dec=41.268750000000004, rows=1):
    """Tabella con il formato di SimbadClass.query_object (astroquery 0.4.11)."""
    from astropy.table import MaskedColumn, Table

    return Table(
        {
            "main_id": [main_id] * rows if isinstance(main_id, str) else main_id,
            "ra": [ra] * rows,
            "dec": [dec] * rows,
            "coo_err_maj": MaskedColumn([0.0] * rows, mask=[True] * rows),
            "coo_err_min": MaskedColumn([0.0] * rows, mask=[True] * rows),
            "coo_err_angle": MaskedColumn([0.0] * rows, mask=[True] * rows),
            "coo_wavelength": ["I"] * rows,
            "coo_bibcode": ["2006AJ....131.1163S"] * rows,
            "matched_id": [main_id] * rows if isinstance(main_id, str) else main_id,
        },
        units={"ra": u.deg, "dec": u.deg, "coo_err_maj": u.mas, "coo_err_min": u.mas, "coo_err_angle": u.deg},
    )


SIMBAD_TAP = "https://simbad.cds.unistra.fr/simbad/sim-tap"


@pytest.fixture
def fake_simbad(monkeypatch):
    """Risposte simulate di SIMBAD: nessuna rete nei test di default."""
    calls = []
    state = {"response": simbad_table()}

    def query(name, timeouts):
        calls.append((name, timeouts))
        response = state["response"]
        if isinstance(response, Exception):
            raise response
        return response, SIMBAD_TAP

    monkeypatch.setattr(cw, "_query_simbad", query)
    return calls, state


def test_t5_resolve_name_cache_first(fake_simbad, tmp_path):
    from astrotwo.core.cache import NETWORK_TIMEOUTS, SharedCache

    calls, _ = fake_simbad
    with SharedCache(tmp_path) as cache:
        first = cw.resolve_name("  M31 ", cache=cache)
        assert not first.from_cache and len(calls) == 1
        assert calls[0] == ("M31", NETWORK_TIMEOUTS)
        expected = SkyCoord(10.684708333333333, 41.268750000000004, unit="deg", frame="icrs")
        assert first.coords.coord.separation(expected).deg < 1e-12
        assert first.coords.frame_name == "icrs" and first.coords.epoch == Time("J2000.0")
        assert first.main_id == "M  31" and first.origin == SIMBAD_TAP
        assert first.coo_err_maj is None and first.coo_bibcode == "2006AJ....131.1163S"
        assert first.retrieved_at.tzinfo is not None
        second = cw.resolve_name("M31", cache=cache)  # dalla cache, senza rete
        assert second.from_cache and len(calls) == 1
        assert second.coords.coord.separation(first.coords.coord).deg == 0.0
        assert second.retrieved_at == first.retrieved_at and second.origin == SIMBAD_TAP
        third = cw.resolve_name("M31", cache=cache, refresh=True)
        assert not third.from_cache and len(calls) == 2


def test_t5_name_not_found_and_ambiguous(fake_simbad, tmp_path):
    from astrotwo.core.cache import SharedCache

    _, state = fake_simbad
    with SharedCache(tmp_path) as cache:
        state["response"] = simbad_table(rows=0)
        expect_error("NAME_NOT_FOUND", cw.resolve_name, "NonEsiste", cache=cache)
        state["response"] = simbad_table(main_id=["A", "B"], rows=2)
        expect_error("NAME_NOT_FOUND", cw.resolve_name, "Ambiguo", cache=cache)
        state["response"] = simbad_table(ra=np.nan, dec=np.nan)
        expect_error("NAME_NOT_FOUND", cw.resolve_name, "SenzaCoordinate", cache=cache)
        assert cache.usage().total_bytes == 0  # nulla in cache
    expect_error("NAME_NOT_FOUND", cw.resolve_name, "M31", source="ned", cache=SharedCache(tmp_path / "c2"))


def test_t5_network_down(fake_simbad, tmp_path):
    import requests

    from astrotwo.core.cache import SharedCache

    _, state = fake_simbad
    with SharedCache(tmp_path) as cache:
        state["response"] = requests.exceptions.ConnectTimeout("rete assente")
        err = expect_error("NET_TIMEOUT", cw.resolve_name, "M31", cache=cache)
        assert "10 s" in err.message and "60 s" in err.message
        state["response"] = simbad_table()
        cw.resolve_name("M31", cache=cache)
        state["response"] = requests.exceptions.ConnectionError("rete assente")
        stale = cw.resolve_name("M31", cache=cache, refresh=True)
        assert stale.from_cache and any("copia in cache" in note for note in stale.notes)


def test_t5_timeouts_reach_the_http_session(monkeypatch, tmp_path):
    """Percorso reale di astroquery/pyvo, con la richiesta HTTP simulata."""
    import requests

    from astrotwo.core.cache import NetworkTimeouts, SharedCache

    seen = []

    def fake_request(self, method, url, **kwargs):
        seen.append(kwargs.get("timeout"))
        raise requests.exceptions.ConnectTimeout("rete simulata assente")

    monkeypatch.setattr(requests.Session, "request", fake_request)
    custom = NetworkTimeouts(connect=3.0, read=7.0)
    with SharedCache(tmp_path) as cache:
        expect_error("NET_TIMEOUT", cw.resolve_name, "M31", cache=cache, timeouts=custom)
    assert seen and all(t == (3.0, 7.0) for t in seen)


def test_t5_column_without_unit_is_rejected(fake_simbad, tmp_path):
    from astrotwo.core.cache import SharedCache

    _, state = fake_simbad
    table = simbad_table()
    table["ra"].unit = None
    state["response"] = table
    with SharedCache(tmp_path) as cache:
        expect_error("COORD_UNIT_MISSING", cw.resolve_name, "M31", cache=cache)


@pytest.mark.network
def test_t5_network_resolve_m31(tmp_path):
    from astroquery.simbad import SimbadClass

    from astrotwo.core.cache import SharedCache

    with SharedCache(tmp_path) as cache:
        resolved = cw.resolve_name("M31", cache=cache)
        again = cw.resolve_name("M31", cache=cache)
    reference = SimbadClass().query_object("M31")
    expected = SkyCoord(reference["ra"][0], reference["dec"][0], unit="deg", frame="icrs")
    # SIMBAD per M31 non dichiara un'ellisse d'errore: confronto al limite numerico.
    tolerance_deg = 1e-9 if resolved.coo_err_maj is None else resolved.coo_err_maj.to_value(u.deg)
    assert resolved.coords.coord.separation(expected).deg <= tolerance_deg
    assert not resolved.from_cache and again.from_cache
    assert resolved.main_id == str(reference["main_id"][0])


# --- T6 ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "lon,lat", [(10.0, 95.0), (10.0, -90.5), (360.0, 0.0), (-1.0, 0.0), (np.nan, 0.0)]
)
def test_t6_input_out_of_range(lon, lat):
    expect_error("COORD_OUT_OF_RANGE", SkyFrame.from_lonlat, lon * u.deg, lat * u.deg, "icrs")


# --- T7 ---------------------------------------------------------------------


@pytest.mark.parametrize("projection", SUPPORTED_PROJECTIONS)
def test_t7_one_test_per_projection(projection):
    header = make_header(projection, rotation_deg=12.0)
    solution = wcs_from_header(header)
    assert solution.projection == projection
    rng = np.random.default_rng(7)
    x, y = rng.uniform(0, 199, 500), rng.uniform(0, 199, 500)
    sky = pixel_to_sky(solution, x, y, convention="numpy")
    back = sky_to_pixel(solution, sky.coords, convention="numpy")
    assert np.max(np.hypot(back.pixels.x - x, back.pixels.y - y)) < 1e-6
    ra, dec = astropy_wcs(header).all_pix2world(x, y, 0)
    assert np.max(sky.coords.coord.separation(SkyCoord(ra, dec, unit="deg")).deg) < 1e-12
    if projection == "NCP":
        assert any("SIN" in fix or "celfix" in fix for fix in solution.fixes)


# --- T8-T11: convenzione dei pixel (DC7) -----------------------------------


def test_t8_pixel_convention_values():
    a = convert_pixel_convention(1, 1, "fits", "numpy")
    b = convert_pixel_convention(-0.5, -0.5, "numpy", "fits")
    assert (float(a.x), float(a.y), a.convention) == (0.0, 0.0, "numpy")
    assert (float(b.x), float(b.y), b.convention) == (0.5, 0.5, "fits")


def test_t9_pixel_convention_roundtrip():
    rng = np.random.default_rng(9)
    # Valori non interi rappresentabili esattamente (multipli di 2**-10).
    x = rng.integers(0, 2**21, 1000) / 1024.0 + 1 / 1024.0
    y = rng.integers(0, 2**21, 1000) / 1024.0 + 3 / 1024.0
    fits_pos = convert_pixel_convention(x, y, "numpy", "fits")
    back = convert_pixel_convention(fits_pos.x, fits_pos.y, "fits", "numpy")
    assert np.array_equal(back.x, x) and np.array_equal(back.y, y)


def test_t10_coherence_with_astropy_origin_1():
    header = make_header("TAN", rotation_deg=5.0)
    solution = wcs_from_header(header)
    rng = np.random.default_rng(10)
    x, y = rng.uniform(0, 199, 200), rng.uniform(0, 199, 200)
    ours = pixel_to_sky(solution, x, y, convention="numpy").coords.coord
    fits_pos = convert_pixel_convention(x, y, "numpy", "fits")
    ra, dec = astropy_wcs(header).wcs_pix2world(fits_pos.x, fits_pos.y, 1)
    assert np.max(ours.separation(SkyCoord(ra, dec, unit="deg")).deg) < 1e-12


@pytest.mark.parametrize("bad", ["idl", None, "", "FITS"])
def test_t11_invalid_convention(bad):
    expect_error("PIXEL_CONVENTION_UNKNOWN", convert_pixel_convention, 1, 1, bad, "numpy")
    expect_error("PIXEL_CONVENTION_UNKNOWN", convert_pixel_convention, 1, 1, "numpy", bad)


def test_t11_convention_mandatory_in_transforms():
    solution = wcs_from_header(make_header("TAN"))
    with pytest.raises(TypeError):
        pixel_to_sky(solution, 1, 1)  # convenzione mancante
    expect_error("PIXEL_CONVENTION_UNKNOWN", pixel_to_sky, solution, 1, 1, convention=None)


# --- T12 --------------------------------------------------------------------


def test_t12_dss1_legacy_solution():
    path = get_pkg_data_filename("data/dss.14.29.56-62.41.05.fits.gz", package="astropy.wcs.tests")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        header = fits.getheader(path)
    solution = wcs_from_header(header)
    assert solution.legacy == "DSS"
    # Convenzione DSS di WCSLIB: x_lastra = CNPIX1 + p - 0.5 (p pixel FITS).
    p_x = header["OBJCTX"] - header["CNPIX1"] + 0.5
    p_y = header["OBJCTY"] - header["CNPIX2"] + 0.5
    px = convert_pixel_convention(p_x, p_y, "fits", "numpy")
    sky = pixel_to_sky(solution, px.x, px.y, convention="numpy")
    ref = SkyCoord(header["OBJCTRA"], header["OBJCTDEC"], unit=(u.hourangle, u.deg), frame="fk5", equinox="J2000")
    # Tolleranza: arrotondamenti del riferimento (0.001 s, 0.01″, 0.01 pixel).
    assert sky.coords.coord.separation(ref).arcsec < 0.02
    assert sky.warnings == ()


def test_t12_legacy_unsupported_is_reported():
    header = fits.Header({"NAXIS": 2, "NAXIS1": 10, "NAXIS2": 10, "PLTRAH": 1, "AMDX1": 1.0})
    expect_error("WCS_LEGACY_UNSUPPORTED", wcs_from_header, header)


# --- T13-T18: calibrazione astrometrica (D10-1, D10-7, D10-8) ---------------


def stars_from_truth(projection, n, seed, noise=0.0):
    truth = astropy_wcs(make_header(projection, rotation_deg=17.0))
    rng = np.random.default_rng(seed)
    x, y = rng.uniform(5, 195, n), rng.uniform(5, 195, n)
    sky = truth.pixel_to_world(x, y)
    xm, ym = x + rng.normal(0, noise, n), y + rng.normal(0, noise, n)
    return truth, xm, ym, SkyFrame(coord=sky)


def calibrate_stars(projection, x, y, sky, **extra):
    params = ZPN_PARAMS if projection == "ZPN" else None
    return astrometric_calibration(
        "stars", pixel_x=x, pixel_y=y, convention="numpy", sky=sky, projection=projection,
        pixel_shape=SHAPE, projection_parameters=params, **extra,
    )


# Criterio sull'errore vero (rispetto alla WCS nota) su 300 punti del campo:
# senza rumore entro 0.01 pixel; con rumore gaussiano σ = 0.2 pixel per asse,
# RMS < σ e massimo < 2σ (atteso statistico per 6 parametri da 30 stelle:
# RMS ≈ σ·√2·√(6/30) ≈ 0.13 pixel, più alto agli angoli del campo).
@pytest.mark.parametrize("noise,max_true_rms_px,max_true_error_px", [(0.0, 0.01, 0.01), (0.2, 0.2, 0.4)])
@pytest.mark.parametrize("projection", SUPPORTED_PROJECTIONS)
def test_t13_star_calibration_every_projection(projection, noise, max_true_rms_px, max_true_error_px):
    truth, x, y, sky = stars_from_truth(projection, 30, seed=13, noise=noise)
    [solution] = calibrate_stars(projection, x, y, sky)
    assert solution.method == "stars" and solution.projection == projection
    assert solution.thresholds == CalibrationThresholds()
    assert solution.rms_px <= 1.0 and solution.max_residual_px <= 3.0
    assert solution.center_deviation_px <= 5.0 * solution.tan_rms_px
    # Scarto dalla WCS vera su tutto il campo (ricalcolo con astropy.wcs).
    rng = np.random.default_rng(130)
    gx, gy = rng.uniform(0, 199, 300), rng.uniform(0, 199, 300)
    scale_deg = 0.01
    err_px = truth.pixel_to_world(gx, gy).separation(solution.wcs.pixel_to_world(gx, gy)).deg / scale_deg
    assert np.sqrt(np.mean(err_px**2)) < max_true_rms_px
    assert np.max(err_px) < max_true_error_px


def test_t14_six_stars_on_sin_is_an_error():
    _, x, y, sky = stars_from_truth("SIN", 6, seed=2)
    err = expect_error("CALIB_TOO_FEW_STARS", calibrate_stars, "SIN", x, y, sky)
    assert err.details == {"n_stars": 6, "minimum": 10}


def test_t14_lowered_minimum_never_silently_wrong():
    """Con il minimo abbassato a 6: o errore CALIB_*, o soluzione davvero buona."""
    lowered = CalibrationThresholds(min_stars_other=6)
    for seed in range(40):
        truth, x, y, sky = stars_from_truth("SIN", 6, seed=seed)
        try:
            [solution] = calibrate_stars("SIN", x, y, sky, thresholds=lowered)
        except CoordinatesWcsError as exc:
            assert exc.code.startswith("CALIB_")
            continue
        cx, cy = (SHAPE[0] - 1) / 2, (SHAPE[1] - 1) / 2
        err_px = truth.pixel_to_world(cx, cy).separation(solution.wcs.pixel_to_world(cx, cy)).deg / 0.01
        assert err_px < 3.0, (seed, err_px)


def test_t15_residuals_above_threshold_list_worst_stars():
    _, x, y, sky = stars_from_truth("TAN", 30, seed=15)
    order = np.arange(30)
    order[[3, 7]] = [7, 3]  # coppia sbagliata: cielo delle stelle 3 e 7 scambiato
    sky_bad = SkyFrame(coord=sky.coord[order])
    err = expect_error("CALIB_RESIDUALS_TOO_LARGE", calibrate_stars, "TAN", x, y, sky_bad)
    worst_indices = [i for i, _ in err.details["worst_stars"]]
    assert {3, 7} & set(worst_indices[:2])


def test_t16_coherence_check():
    tan = astropy_wcs(make_header("TAN"))
    same = cw._check_coherence(tan, tan, SHAPE, tan_rms_px=0.1, factor=5.0)
    assert same == pytest.approx(0.0, abs=1e-9)
    shifted = astropy_wcs(make_header("TAN"))
    shifted.wcs.crpix = shifted.wcs.crpix + np.array([2.0, 0.0])  # 2 pixel > 5 × 0.1
    err = expect_error("CALIB_INCONSISTENT", cw._check_coherence, tan, shifted, SHAPE, 0.1, 5.0)
    assert err.details["center_deviation_px"] == pytest.approx(2.0, rel=1e-6)


def test_t17_parameters_and_header_methods():
    ref = SkyFrame.from_lonlat(150.0 * u.deg, 2.0 * u.deg, "icrs")
    [solution] = astrometric_calibration(
        "parameters", reference=ref, reference_pixel=(99.5, 99.5), convention="numpy",
        scale=1.0 * u.arcsec, rotation=30.0 * u.deg, projection="TAN", east_left=True, pixel_shape=SHAPE,
    )
    h = fits.Header({
        "NAXIS": 2, "NAXIS1": 200, "NAXIS2": 200, "CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN",
        "RADESYS": "ICRS", "CRVAL1": 150.0, "CRVAL2": 2.0, "CRPIX1": 100.5, "CRPIX2": 100.5,
        "CDELT1": -1 / 3600, "CDELT2": 1 / 3600, "CROTA2": 30.0,
    })
    expected = astropy_wcs(h)
    rng = np.random.default_rng(17)
    x, y = rng.uniform(0, 199, 100), rng.uniform(0, 199, 100)
    assert np.max(solution.wcs.pixel_to_world(x, y).separation(expected.pixel_to_world(x, y)).deg) < 1e-9
    [from_header] = astrometric_calibration("header", header=h)
    assert from_header.method == "header"
    assert np.max(from_header.wcs.pixel_to_world(x, y).separation(expected.pixel_to_world(x, y)).deg) < 1e-9


def test_t18_solutions_returned_as_list():
    header = make_header("TAN")
    first = astrometric_calibration("header", header=header)
    _, x, y, sky = stars_from_truth("TAN", 30, seed=18)
    second = calibrate_stars("TAN", x, y, sky, previous_solutions=first)
    assert len(first) == 1 and len(second) == 2
    assert second[0] is first[0] and second[1].method == "stars"


def test_calibration_projection_errors():
    _, x, y, sky = stars_from_truth("TAN", 30, seed=1)
    expect_error(
        "PROJECTION_PARAMETERS_MISSING", astrometric_calibration, "stars", pixel_x=x, pixel_y=y,
        convention="numpy", sky=sky, projection="ZPN", pixel_shape=SHAPE,
    )
    expect_error(
        "PROJECTION_UNSUPPORTED", astrometric_calibration, "stars", pixel_x=x, pixel_y=y,
        convention="numpy", sky=sky, projection="MOL", pixel_shape=SHAPE,
    )


# --- T19: griglia -----------------------------------------------------------


def _check_grid(grid, header, frame, equinox=None):
    w = astropy_wcs(header)
    assert grid.lines
    for line in grid.lines:
        for xs, ys in line.segments:
            assert np.all((xs >= -0.5) & (xs <= SHAPE[0] - 0.5) & (ys >= -0.5) & (ys <= SHAPE[1] - 0.5))
            target = SkyCoord(0, 0, unit="deg", frame=frame, equinox=equinox) if equinox else frame
            sky = w.pixel_to_world(xs, ys).transform_to(target)
            if line.kind == "meridian":
                # Al polo la longitudine non è definita: il punto sta su ogni meridiano.
                keep = np.abs(sky.spherical.lat.deg) < 90.0 - 1e-7
                diff = (sky.spherical.lon.deg[keep] - line.value.to_value(u.deg) + 180.0) % 360.0 - 180.0
            else:
                diff = sky.spherical.lat.deg - line.value.to_value(u.deg)
            assert np.max(np.abs(diff)) < 1e-9


def test_t19_grid_lines_icrs_and_galactic():
    header = make_header("TAN", rotation_deg=17.0)
    for frame in ("icrs", "galactic"):
        grid = compute_grid_lines(
            wcs_from_header(header), frame=frame, lon_spacing=0.5 * u.deg, lat_spacing=0.5 * u.deg
        )
        assert grid.frame_name == frame
        _check_grid(grid, header, frame)
    # Completezza in ICRS: ogni multiplo di 0.5° dentro l'intervallo di RA e Dec
    # dei pixel (ricalcolato con astropy.wcs) ha la sua linea.
    w = astropy_wcs(header)
    gx, gy = np.meshgrid(np.linspace(0, 199, 50), np.linspace(0, 199, 50))
    sky = w.pixel_to_world(gx.ravel(), gy.ravel())
    grid = compute_grid_lines(w, frame="icrs", lon_spacing=0.5 * u.deg, lat_spacing=0.5 * u.deg)
    meridians = {round(line.value.to_value(u.deg), 9) for line in grid.lines if line.kind == "meridian"}
    parallels = {round(line.value.to_value(u.deg), 9) for line in grid.lines if line.kind == "parallel"}
    for v in np.arange(np.ceil(sky.ra.deg.min() / 0.5) * 0.5, sky.ra.deg.max(), 0.5):
        assert round(v, 9) in meridians
    for v in np.arange(np.ceil(sky.dec.deg.min() / 0.5) * 0.5, sky.dec.deg.max(), 0.5):
        assert round(v, 9) in parallels


def test_t19_grid_with_pole_in_field():
    header = make_header("SIN", crval=(0.0, 89.5), scale=0.02)
    grid = compute_grid_lines(wcs_from_header(header), frame="icrs", lon_spacing=30 * u.deg, lat_spacing=1 * u.deg)
    meridians = {round(line.value.to_value(u.deg), 6) for line in grid.lines if line.kind == "meridian"}
    assert meridians == {float(v) for v in range(0, 360, 30)}
    _check_grid(grid, header, "icrs")


def test_t19_grid_errors():
    solution = wcs_from_header(make_header("TAN"))
    expect_error("GRID_SPACING_INVALID", compute_grid_lines, solution, frame="icrs", lon_spacing=0.5, lat_spacing=1 * u.deg)
    expect_error("GRID_SPACING_INVALID", compute_grid_lines, solution, frame="icrs", lon_spacing=0 * u.deg, lat_spacing=1 * u.deg)
    expect_error("EPOCH_REQUIRED", compute_grid_lines, solution, frame="fk5", lon_spacing=1 * u.deg, lat_spacing=1 * u.deg)


# --- T23: passo automatico della griglia -----------------------------------

# Elenchi di §9 del 10, riscritti qui dalla specifica (non importati dal modulo).
ARC_STEPS = (
    [v * u.arcsec for v in (0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30)]
    + [v * u.arcmin for v in (1, 2, 5, 10, 15, 30)]
    + [v * u.deg for v in (1, 2, 5, 10, 15, 30, 45, 90)]
)
TIME_STEPS = (
    [v * 15 * u.arcsec for v in (0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30)]
    + [v * 15 * u.arcmin for v in (1, 2, 5, 10, 15, 30)]
    + [v * 15 * u.deg for v in (1, 2, 3, 4, 6)]
)


def expected_step(extent_deg, steps, lines=5):
    for step in steps:
        if step.to_value(u.deg) >= extent_deg / lines:
            return step.to_value(u.deg)
    return steps[-1].to_value(u.deg)


def field_extent_astropy(header, frame):
    """Estensione del campo ricalcolata con astropy.wcs su 301×301 punti."""
    w = astropy_wcs(header)
    nx, ny = header["NAXIS1"], header["NAXIS2"]
    gx, gy = np.meshgrid(np.linspace(-0.5, nx - 0.5, 301), np.linspace(-0.5, ny - 0.5, 301))
    sky = w.pixel_to_world(gx.ravel(), gy.ravel()).transform_to(frame)
    lon, lat = sky.spherical.lon.deg, sky.spherical.lat.deg
    px, py = w.world_to_pixel(SkyCoord([0, 0], [90, -90], unit="deg", frame=frame))
    inside = np.isfinite(px) & (px >= -0.5) & (px <= nx - 0.5) & (py >= -0.5) & (py <= ny - 0.5)
    if inside.any():
        lon_ext = 360.0
    else:
        center = w.pixel_to_world((nx - 1) / 2, (ny - 1) / 2).transform_to(frame).spherical.lon.deg
        rel = (lon - center + 180.0) % 360.0 - 180.0
        lon_ext = rel.max() - rel.min()
    lat_hi = 90.0 if inside[0] else lat.max()
    lat_lo = -90.0 if inside[1] else lat.min()
    return lon_ext, lat_hi - lat_lo


@pytest.mark.parametrize(
    "header_kwargs,frame,lon_steps",
    [
        (dict(projection="TAN"), "icrs", TIME_STEPS),
        (dict(projection="TAN", rotation_deg=17.0), "galactic", ARC_STEPS),
        (dict(projection="TAN", scale=1e-4), "icrs", TIME_STEPS),
        (dict(projection="SIN", crval=(0.0, 89.5), scale=0.02), "icrs", TIME_STEPS),
    ],
)
def test_t23_choose_grid_spacing(header_kwargs, frame, lon_steps):
    header = make_header(**header_kwargs)
    spacing = choose_grid_spacing(wcs_from_header(header), frame=frame)
    lon_ext, lat_ext = field_extent_astropy(header, frame)
    assert spacing.lon_extent.to_value(u.deg) == pytest.approx(lon_ext, rel=1e-3)
    assert spacing.lat_extent.to_value(u.deg) == pytest.approx(lat_ext, rel=1e-3)
    assert spacing.lon_spacing.to_value(u.deg) == pytest.approx(expected_step(lon_ext, lon_steps), rel=1e-12)
    assert spacing.lat_spacing.to_value(u.deg) == pytest.approx(expected_step(lat_ext, ARC_STEPS), rel=1e-12)
    assert spacing.lon_steps == ("time" if lon_steps is TIME_STEPS else "arc")


def test_t23_smaller_field_never_larger_step():
    big = choose_grid_spacing(wcs_from_header(make_header("TAN", scale=0.01)), frame="icrs")
    small = choose_grid_spacing(wcs_from_header(make_header("TAN", scale=1e-4)), frame="icrs")
    assert small.lon_spacing <= big.lon_spacing and small.lat_spacing <= big.lat_spacing


def test_t23_grid_lines_use_automatic_spacing():
    solution = wcs_from_header(make_header("TAN", rotation_deg=17.0))
    spacing = choose_grid_spacing(solution, frame="icrs")
    auto = compute_grid_lines(solution, frame="icrs")
    explicit = compute_grid_lines(
        solution, frame="icrs", lon_spacing=spacing.lon_spacing, lat_spacing=spacing.lat_spacing
    )
    assert auto.lon_spacing == explicit.lon_spacing and auto.lat_spacing == explicit.lat_spacing
    assert [(line.kind, line.value) for line in auto.lines] == [(line.kind, line.value) for line in explicit.lines]
    for kind in ("meridian", "parallel"):
        assert 1 <= sum(line.kind == kind for line in auto.lines) <= 2 * spacing.target_lines + 2
    _check_grid(auto, make_header("TAN", rotation_deg=17.0), "icrs")


def test_t23_errors():
    solution = wcs_from_header(make_header("TAN"))
    expect_error("GRID_SPACING_INVALID", choose_grid_spacing, solution, frame="icrs", target_lines=0)
    expect_error("GRID_SPACING_INVALID", compute_grid_lines, solution, frame="icrs", lon_spacing=1 * u.deg)
    expect_error("EPOCH_REQUIRED", choose_grid_spacing, solution, frame="fk5")


# --- T20 --------------------------------------------------------------------


def test_t20_choose_projection():
    threshold = 30 * u.deg
    assert choose_projection(1 * u.deg, threshold=threshold).projection == "TAN"
    assert choose_projection(180 * u.deg, threshold=threshold).projection == "AIT"
    assert choose_projection(threshold, threshold=threshold).projection == "AIT"
    expect_error("COORD_UNIT_MISSING", choose_projection, 1.0, threshold=threshold)


# --- T21 --------------------------------------------------------------------


def test_t21_units_and_epochs_mandatory():
    expect_error("COORD_UNIT_MISSING", SkyFrame.from_lonlat, 10.0, 20.0, "icrs")
    expect_error("COORD_UNIT_MISSING", SkyFrame.from_lonlat, 10.0 * u.m, 20.0 * u.deg, "icrs")
    expect_error("EPOCH_REQUIRED", SkyFrame.from_lonlat, 10 * u.deg, 20 * u.deg, "fk5")
    expect_error("EPOCH_REQUIRED", SkyFrame, SkyCoord(10, 20, unit="deg", frame="fk5"))
    expect_error("EPOCH_REQUIRED", SkyFrame.from_lonlat, 10 * u.deg, 20 * u.deg, "fk5", equinox="2000-01-01")
    expect_error("FRAME_UNSUPPORTED", SkyFrame.from_lonlat, 10 * u.deg, 20 * u.deg, "ecliptic")
    pos = SkyFrame.from_lonlat(10 * u.deg, 20 * u.deg, "icrs")
    expect_error("EPOCH_REQUIRED", convert_coordinates, pos, "fk5")
    fk5 = convert_coordinates(pos, "fk5", equinox="J2000")
    expected = SkyCoord(10, 20, unit="deg", frame="icrs").transform_to("fk5")
    assert fk5.coord.separation(expected).deg < 1e-12 and fk5.equinox == Time("J2000")
    fk4 = convert_coordinates(pos, "fk4", equinox="B1950", obstime="B1950")
    expected = SkyCoord(10, 20, unit="deg").transform_to(SkyCoord(0, 0, unit="deg", frame="fk4", equinox="B1950", obstime="B1950").frame)
    assert fk4.coord.separation(expected).deg < 1e-12


# --- T22 --------------------------------------------------------------------


def test_t22_out_of_field_warning():
    solution = wcs_from_header(make_header("TAN"))
    res = pixel_to_sky(solution, [-5.0, 100.0, 250.0], [10.0, 100.0, 10.0], convention="numpy")
    assert res.warnings == ("OUT_OF_FIELD",)
    assert res.out_of_field.tolist() == [True, False, True]
    assert np.all(np.isfinite(res.coords.lon.value))  # il valore è comunque restituito
    inside = pixel_to_sky(solution, [0.0], [0.0], convention="numpy")
    assert inside.warnings == ()
    assert inside.display_epoch == Time("J2000.0")  # header senza DATE-OBS (D10-2)


# --- Altri casi limite di §10 -------------------------------------------------


def test_wcs_errors():
    expect_error("WCS_MISSING", wcs_from_header, fits.Header({"NAXIS": 2, "NAXIS1": 10, "NAXIS2": 10}))
    zero = make_header("TAN")
    zero["CD1_1"] = zero["CD1_2"] = zero["CD2_1"] = zero["CD2_2"] = 0.0  # WCSLIB la renderebbe identità
    expect_error("WCS_INVALID", wcs_from_header, zero)
    rank_one = make_header("TAN")
    rank_one["CD1_1"] = rank_one["CD1_2"] = rank_one["CD2_1"] = rank_one["CD2_2"] = 0.01
    expect_error("WCS_INVALID", wcs_from_header, rank_one)


def test_header_defaults_are_declared():
    header = make_header("TAN")
    del header["RADESYS"]
    solution = wcs_from_header(header)
    assert any("RADESYS assente" in fix for fix in solution.fixes)


def test_t24_proper_motion_only_propagation():
    # Opzione esplicita "solo moto proprio" (D13-12 del 13): astropy senza distanza,
    # nessun effetto prospettico, risultato marcato.
    pos = SkyFrame.from_lonlat(BARNARD["ra"], BARNARD["dec"], "icrs", epoch=GAIA_EPOCH)
    target = Time(2026.0, format="jyear", scale="tcb")
    out = propagate_position(pos, pm_ra_cosdec=BARNARD["pm_ra_cosdec"], pm_dec=BARNARD["pm_dec"],
                             parallax=None, target_epoch=target, proper_motion_only=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        expected = SkyCoord(ra=BARNARD["ra"], dec=BARNARD["dec"], pm_ra_cosdec=BARNARD["pm_ra_cosdec"],
                            pm_dec=BARNARD["pm_dec"], obstime=GAIA_EPOCH, frame="icrs").apply_space_motion(
                                new_obstime=target)
    assert out.position.coord.separation(expected).deg < 1e-12
    assert out.proper_motion_only and any("solo moto proprio" in n for n in out.notes)
    full = propagate_position(pos, pm_ra_cosdec=BARNARD["pm_ra_cosdec"], pm_dec=BARNARD["pm_dec"],
                              parallax=BARNARD["parallax"], target_epoch=target)
    assert not full.proper_motion_only
    for kwargs in (dict(parallax=BARNARD["parallax"]), dict(parallax=None, radial_velocity=BARNARD["radial_velocity"])):
        with pytest.raises(CoordinatesWcsError) as info:
            propagate_position(pos, pm_ra_cosdec=BARNARD["pm_ra_cosdec"], pm_dec=BARNARD["pm_dec"],
                               target_epoch=target, proper_motion_only=True, **kwargs)
        assert info.value.code == "PROPAGATION_MODE_CONFLICT"
    with pytest.raises(CoordinatesWcsError) as info:  # senza l'opzione la parallasse resta obbligatoria
        propagate_position(pos, pm_ra_cosdec=BARNARD["pm_ra_cosdec"], pm_dec=BARNARD["pm_dec"],
                           parallax=None, target_epoch=target)
    assert info.value.code == "EPOCH_REQUIRED"


def test_t25_parse_sexagesimal():
    from astropy.coordinates import Angle

    from astrotwo.core.coordinates_wcs import parse_sexagesimal

    ra = parse_sexagesimal(["00 13 00.93", "12:30:15.5"], hours=True)
    dec = parse_sexagesimal(["+72 31 19.9", "-05:06:07"], hours=False)
    assert type(ra) is u.Quantity and ra.unit == u.deg
    assert np.array_equal(ra.value, Angle(["00 13 00.93", "12:30:15.5"], unit=u.hourangle).deg)
    assert np.array_equal(dec.value, Angle(["+72 31 19.9", "-05:06:07"], unit=u.deg).deg)
    with pytest.raises(CoordinatesWcsError) as info:
        parse_sexagesimal(["non è un angolo"], hours=False)
    assert info.value.code == "COORD_FORMAT_INVALID"


# --- T26-T36: vista, scrittura delle coordinate, nord e barra di scala (2026-10-15/16) ---------------

from astropy.coordinates import Angle  # noqa: E402

from astrotwo.core.coordinates_wcs import (  # noqa: E402
    GRID_STEPS_ARC,
    ViewGeometry,
    compass_and_scale_bar,
    format_coordinates,
    make_view_wcs,
)


def icrs(ra, dec, epoch=None):
    return SkyFrame.from_lonlat(ra * u.deg, dec * u.deg, "icrs", epoch=epoch)


def test_t29_default_threshold():
    assert choose_projection(29.999 * u.deg).projection == "TAN"
    choice = choose_projection(30 * u.deg)
    assert choice.projection == "AIT" and choice.threshold == 30 * u.deg and "default" in choice.threshold_source
    explicit = choose_projection(31 * u.deg, threshold=33 * u.deg)
    assert explicit.projection == "TAN" and explicit.threshold == 33 * u.deg


@pytest.mark.parametrize("projection", ["TAN", "SIN", "AIT", "ZEA", "STG", "CAR"])
@pytest.mark.parametrize("frame", ["icrs", "galactic"])
def test_t26_view_without_base(projection, frame):
    center = icrs(56.75, 24.12) if frame == "icrs" else SkyFrame.from_lonlat(166.57 * u.deg, -23.52 * u.deg, "galactic")
    g = make_view_wcs(center, 2 * u.arcsec, (300, 400), projection=projection, frame=frame)
    lon_p, lat_p = ("RA---", "DEC--") if frame == "icrs" else ("GLON-", "GLAT-")
    ref = WCS(naxis=2)
    ref.wcs.ctype = [lon_p + projection, lat_p + projection]
    ref.wcs.crval = [center.lon.value, center.lat.value]
    ref.wcs.cdelt = [-2 / 3600, 2 / 3600]
    ref.wcs.crpix = [1, 1]
    ref.wcs.cunit = ["deg", "deg"]
    if frame == "icrs":
        ref.wcs.radesys = "ICRS"
    ref.wcs.set()
    xs, ys = np.meshgrid(np.linspace(-50, 50, 7), np.linspace(-40, 40, 7))
    a = g.base.pixel_to_world(xs.ravel(), ys.ravel())
    b = ref.pixel_to_world(xs.ravel(), ys.ravel())
    assert np.max(a.separation(b).deg) < 1e-9
    c = g.window_to_sky(399 / 2, 299 / 2)
    assert c.separation(center.coord).deg < 1e-9
    wx, wy = np.array([0.0, 123.4, 399.0]), np.array([0.0, 77.7, 299.0])
    bx, by = g.sky_to_window(g.window_to_sky(wx, wy))
    assert np.max(np.abs(bx - wx)) < 1e-6 and np.max(np.abs(by - wy)) < 1e-6
    assert g.factor == pytest.approx(1.0) and g.base_created


def sip_wcs():
    header = fits.Header()
    header.update({"NAXIS": 2, "NAXIS1": 1000, "NAXIS2": 800, "CTYPE1": "RA---TAN-SIP", "CTYPE2": "DEC--TAN-SIP",
                   "CRVAL1": 56.75, "CRVAL2": 24.12, "CRPIX1": 500.5, "CRPIX2": 400.5,
                   "CD1_1": -2.4e-4, "CD1_2": 1.4e-4, "CD2_1": 1.4e-4, "CD2_2": 2.4e-4,
                   "A_ORDER": 2, "B_ORDER": 2, "A_2_0": 2e-6, "A_1_1": -1e-6, "B_0_2": 3e-6, "B_1_1": 1e-6})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        return WCS(header)


def dss_solution():
    path = get_pkg_data_filename("data/dss.14.29.56-62.41.05.fits.gz", package="astropy.wcs.tests")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return wcs_from_header(fits.getheader(path))


@pytest.mark.parametrize("which", ["sip", "dss"])
def test_t27_view_on_distorted_image(which):
    base = sip_wcs() if which == "sip" else dss_solution()
    w = base if which == "sip" else base.wcs
    c = w.pixel_to_world(300.0, 200.0)
    center = SkyFrame(coord=SkyCoord(c.ra, c.dec, frame="icrs")) if which == "sip" else SkyFrame(coord=c)
    for scale in (0.5 * u.arcsec, 3 * u.arcsec, 20 * u.arcsec):
        g = make_view_wcs(center, scale, (240, 320), base=base)
        assert not g.base_created
        x, y = np.array([0.0, 17.3, 319.0]), np.array([0.0, 101.9, 239.0])
        direct = w.pixel_to_world(g.origin[0] + x / g.factor, g.origin[1] + y / g.factor)
        assert np.max(g.window_to_sky(x, y).separation(direct).arcsec) < 1e-12 * 3600
        bx, by = g.window_to_base(x, y)
        vis = g.visible_wcs.pixel_to_world(bx - g.visible_origin[0], by - g.visible_origin[1])
        assert np.max(vis.separation(direct).deg) < 1e-9


def test_t28_field_radius():
    center = icrs(10.0, 20.0)
    g = make_view_wcs(center, 6 * u.arcsec, (200, 300), projection="TAN")
    xs = np.linspace(-0.5, 299.5, 64)
    ys = np.linspace(-0.5, 199.5, 64)
    bx = np.concatenate([xs, xs, np.full(64, -0.5), np.full(64, 299.5)])
    by = np.concatenate([np.full(64, -0.5), np.full(64, 199.5), ys, ys])
    expected = np.max(center.coord.separation(g.window_to_sky(bx, by)).deg)
    assert g.field_radius.to_value(u.deg) == pytest.approx(expected, abs=1e-12)
    allsky = make_view_wcs(icrs(0.0, 0.0), 1.5 * u.deg, (200, 400), projection="AIT")
    assert allsky.field_radius == 180 * u.deg and "fuori dalla proiezione" in allsky.field_radius_method


def test_t30_view_errors():
    c = icrs(10.0, 20.0)
    expect_error("VIEW_PARAMETERS_INVALID", make_view_wcs, c, 0 * u.arcsec, (10, 10), projection="TAN")
    expect_error("VIEW_PARAMETERS_INVALID", make_view_wcs, c, 1.0, (10, 10), projection="TAN")
    expect_error("VIEW_PARAMETERS_INVALID", make_view_wcs, c, 1 * u.arcsec, (0, 10), projection="TAN")
    expect_error("VIEW_PARAMETERS_INVALID", make_view_wcs, c, 1 * u.arcsec, (10, 10), projection="TAN", base=sip_wcs())
    expect_error("VIEW_PARAMETERS_INVALID", make_view_wcs, c, 1 * u.arcsec, (10, 10))
    expect_error("PROJECTION_UNSUPPORTED", make_view_wcs, c, 1 * u.arcsec, (10, 10), projection="NCP")
    expect_error("PROJECTION_UNSUPPORTED", make_view_wcs, c, 1 * u.arcsec, (10, 10), projection="ZPN")


def test_t31_dc3_digits():
    rng = np.random.default_rng(31)
    ra, dec = rng.uniform(0, 360, 1000), rng.uniform(-90, 90, 1000)
    out = format_coordinates(SkyFrame.from_lonlat(ra * u.deg, dec * u.deg, "icrs", epoch="J2016.0"))
    exp_ra = [Angle(v * u.deg).to_string(unit=u.hourangle, sep=("h", "m", "s"), precision=2, pad=True) for v in ra]
    exp_dec = [Angle(v * u.deg).to_string(unit=u.deg, sep=("°", "′", "″"), precision=1, pad=True, alwayssign=True)
               for v in dec]
    exp_ra = ["00h00m00.00s" if t.startswith("24") else t for t in exp_ra]
    assert list(out.lon) == exp_ra and list(out.lat) == exp_dec
    assert out.frame_name == "icrs" and out.epoch == Time("J2016.0") and "," not in "".join(out.lon + out.lat)
    gal = format_coordinates(SkyFrame.from_lonlat(ra * u.deg, dec * u.deg, "galactic"))
    assert list(gal.lon)[:5] == [Angle(v * u.deg).to_string(unit=u.deg, sep=("°", "′", "″"), precision=1) for v in ra[:5]]
    assert gal.epoch is None and "non assunta" in gal.epoch_note


def test_t32_carry_wrap_sign():
    ra = Angle(["23h59m59.996s", "10h59m59.996s"]).deg
    out = format_coordinates(SkyFrame.from_lonlat(ra * u.deg, [-0.04 / 3600, 89 + 59 / 60 + 59.96 / 3600] * u.deg, "icrs"))
    assert out.lon == ("00h00m00.00s", "11h00m00.00s")
    assert out.lat == ("-00°00′00.0″", "+90°00′00.0″")
    gal = format_coordinates(SkyFrame.from_lonlat([359.99999999] * u.deg, [0.0] * u.deg, "galactic"))
    assert gal.lon == ("0°00′00.0″",)


def test_t33_precision_and_styles():
    lab = format_coordinates(values=[10.5, 11.0] * u.deg, frame="galactic", axis="lat", precision=10 * u.arcmin)
    assert lab.lat == ("+10°30′", "+11°00′")
    ra = format_coordinates(values=[150.0] * u.deg, frame="icrs", axis="lon", precision=1 * u.s)
    assert ra.lon == ("10h00m00s",)
    ra2 = format_coordinates(values=[150.0] * u.deg, frame="icrs", axis="lon", precision=0.01 * u.s)
    assert ra2.lon == ("10h00m00.00s",)
    dec = format_coordinates(icrs(150.123456789, -5.5), style="decimal")
    assert dec.lon == ("150.123457",) and dec.lat == ("-5.500000",)
    col = format_coordinates(icrs(187.5, 12.25), separators="colons")
    assert col.lon == ("12:30:00.00",) and col.lat == ("+12:15:00.0",)
    expect_error("FORMAT_PRECISION_INVALID", format_coordinates, icrs(1, 1), precision=0 * u.arcsec)
    expect_error("FORMAT_PRECISION_INVALID", format_coordinates, icrs(1, 1), precision=1.0)
    expect_error("FORMAT_PRECISION_INVALID", format_coordinates, values=[1] * u.deg, frame="icrs", axis="lat",
                 precision=1 * u.s)
    expect_error("FRAME_UNSUPPORTED", format_coordinates, values=[1] * u.deg, axis="lat")
    expect_error("COORD_UNIT_MISSING", format_coordinates, values=[1] * u.deg, frame="icrs")


def expected_vectors(g: ViewGeometry, frame):
    rows, cols = g.shape
    xc, yc = (cols - 1) / 2, (rows - 1) / 2
    c = g.window_to_sky(xc, yc).transform_to(frame)
    delta = 10 * g.scale
    out = []
    for pa in (0, 90):
        x, y = g.sky_to_window(c.directional_offset_by(pa * u.deg, delta))
        v = np.array([float(x) - xc, float(y) - yc])
        out.append(v / np.hypot(*v))
    return out


def test_t34_north_and_east():
    cases = [
        (make_view_wcs(icrs(56.75, 24.12), 2 * u.arcsec, (300, 400), projection="TAN"), "icrs", True),
        (make_view_wcs(icrs(56.75, 24.12), 2 * u.arcsec, (300, 400), projection="TAN", frame="galactic"), "galactic", True),
        (make_view_wcs(icrs(56.75, 24.12), 2 * u.arcsec, (300, 400), base=sip_wcs()), "icrs", True),
    ]
    flipped = WCS(naxis=2)
    flipped.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    flipped.wcs.crval = [56.75, 24.12]
    flipped.wcs.cdelt = [2 / 3600, 2 / 3600]
    flipped.wcs.crpix = [1, 1]
    flipped.wcs.set()
    cases.append((make_view_wcs(icrs(56.75, 24.12), 2 * u.arcsec, (300, 400), base=flipped), "icrs", False))
    for g, frame, east_left in cases:
        result = compass_and_scale_bar(g, frame=frame)
        n, e = expected_vectors(g, frame)
        assert np.max(np.abs(np.array(result.north) - n)) < 1e-9 and np.max(np.abs(np.array(result.east) - e)) < 1e-9
        assert result.east_left is east_left and result.warnings == ()


@pytest.mark.parametrize("scale", [0.2 * u.arcsec, 2 * u.arcsec, 30 * u.arcsec, 5 * u.arcmin])
def test_t35_scale_bar(scale):
    g = make_view_wcs(icrs(56.75, 24.12), scale, (300, 600), projection="TAN")
    bar = compass_and_scale_bar(g, max_bar_pixels=120)
    xc, yc = 599 / 2, 299 / 2
    ends = g.window_to_sky([xc - bar.bar_pixels / 2, xc + bar.bar_pixels / 2], [yc, yc])
    assert abs(ends[0].separation(ends[1]).deg - bar.bar_angle.to_value(u.deg)) < 1e-9
    assert bar.bar_pixels <= 120
    steps = [float(s.to_value(u.deg)) for s in GRID_STEPS_ARC]
    i = steps.index(pytest.approx(bar.bar_angle.to_value(u.deg)))
    if i + 1 < len(steps):
        far = g.window_to_sky([xc - 60, xc + 60], [yc, yc])
        assert far[0].separation(far[1]).deg < steps[i + 1]  # il valore tondo successivo non ci sta
    assert bar.label[-1] in "″′°" and "," not in bar.label
    assert bar.local_only is bool(g.field_radius > 15 * u.deg)


def test_t36_pole_aitoff_limits():
    pole = compass_and_scale_bar(make_view_wcs(icrs(10.0, 90.0), 2 * u.arcsec, (100, 100), projection="TAN"))
    assert pole.north is None and pole.warnings[0][0] == "NORTH_UNDEFINED"
    allsky = compass_and_scale_bar(make_view_wcs(icrs(0.0, 0.0), 1.5 * u.deg, (200, 400), projection="AIT"))
    assert allsky.local_only
    tiny = compass_and_scale_bar(make_view_wcs(icrs(1.0, 1.0), 0.001 * u.arcsec, (100, 100), projection="TAN"),
                                 max_bar_pixels=5)
    assert ("SCALE_BAR_TOO_LONG" in [w[0] for w in tiny.warnings]) and tiny.label == "0.01″"
    g = make_view_wcs(icrs(1.0, 1.0), 1 * u.arcsec, (100, 100), projection="TAN")
    expect_error("VIEW_PARAMETERS_INVALID", compass_and_scale_bar, g, max_bar_pixels=0)
    expect_error("FRAME_UNSUPPORTED", compass_and_scale_bar, g, frame="nonexistent")
