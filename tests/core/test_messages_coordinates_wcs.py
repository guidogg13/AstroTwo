# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 10 con codice + ``params`` e voci del catalogo (D40-3; ``40`` §3.7.1, T18–T19).

Ogni errore e ogni avviso del modulo viene provocato; i ``params`` devono essere conformi alla voce del catalogo
(nomi, tipi, JSON) e i testi inglese e italiano non lasciano segnaposto. Tutte le coppie (codice, ragione) del
catalogo per il modulo 10 devono essere raggiunte.
"""

from __future__ import annotations

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.time import Time
from astropy.wcs import WCS

from astrotwo.core import coordinates_wcs as cw
from astrotwo.core.coordinates_wcs import CoordinatesWcsError, SkyFrame
from astrotwo.messages_catalog import message_text
from tests.core.test_coordinates_wcs import SHAPE, make_header
from tests.message_helpers import (
    MODULE_14_SUBVARIANTS,
    MODULE_16_SUBVARIANTS,
    MODULE_17_SUBVARIANTS,
    MODULE_18_SUBVARIANTS,
    MODULE_15_SUBVARIANTS,
    MODULE_19_SUBVARIANTS,
    catalog_combinations,
    check_error,
    check_message,
    collect_errors,
)

MODULE_CODES = (
    "PIXEL_CONVENTION_UNKNOWN", "FRAME_UNSUPPORTED", "EPOCH_REQUIRED", "COORD_UNIT_MISSING", "COORD_OUT_OF_RANGE",
    "NAME_NOT_FOUND", "NET_TIMEOUT", "COORD_FORMAT_INVALID", "PROPAGATION_MODE_CONFLICT", "WCS_INVALID", "WCS_MISSING",
    "WCS_LEGACY_UNSUPPORTED", "PROJECTION_UNSUPPORTED", "PROJECTION_PARAMETERS_MISSING", "CALIB_INCONSISTENT",
    "CALIB_TOO_FEW_STARS", "CALIB_FIT_FAILED", "CALIB_RESIDUALS_TOO_LARGE", "GRID_SPACING_INVALID",
    "VIEW_PARAMETERS_INVALID", "FORMAT_PRECISION_INVALID", "NORTH_UNDEFINED", "SCALE_BAR_TOO_LONG", "OUT_OF_FIELD",
)

#: Voci generali che i moduli non sollevano mai da sole (ogni punto di sollevamento ha una ragione).
GENERAL_IS_FALLBACK = {
    "EPOCH_REQUIRED", "COORD_UNIT_MISSING", "COORD_OUT_OF_RANGE", "WCS_INVALID", "WCS_MISSING", "GRID_SPACING_INVALID",
    "VIEW_PARAMETERS_INVALID", "FORMAT_PRECISION_INVALID", "NORTH_UNDEFINED",
}

DEG = u.deg


def header_with(**changes):
    header = make_header("TAN")
    for key, value in changes.items():
        header[key] = value
    return header


def sky(lon=10.0, lat=20.0, frame="icrs", **kwargs):
    return SkyFrame.from_lonlat(lon * DEG, lat * DEG, frame, **kwargs)


def icrs_epoch_sky():
    return sky(epoch=Time("J2016.0"))


def view(**kwargs):
    base = {"center": sky(), "scale": 1 * u.arcsec, "shape": (100, 100), "projection": "TAN"}
    base.update(kwargs)
    return cw.make_view_wcs(**base)


def geometry():
    return view()


def calibrate_stars(**kwargs):
    base = dict(pixel_x=[10, 20, 30, 40], pixel_y=[10, 25, 12, 40], convention="numpy", sky=sky_list(4),
                projection="TAN", pixel_shape=(100, 100), projection_parameters=None,
                thresholds=cw.CalibrationThresholds())
    base.update(kwargs)
    return cw.astrometric_calibration("stars", **{k: v for k, v in base.items() if k != "projection_parameters"})


def sky_list(n):
    rng = np.random.default_rng(1)
    return SkyFrame.from_lonlat((10 + rng.uniform(0, 0.01, n)) * DEG, (20 + rng.uniform(0, 0.01, n)) * DEG, "icrs")


def calibrate_parameters(**kwargs):
    base = dict(reference=sky(), reference_pixel=(50, 50), convention="numpy", scale=1 * u.arcsec, rotation=0 * DEG,
                projection="TAN", east_left=True, pixel_shape=(100, 100))
    base.update(kwargs)
    return cw.astrometric_calibration("parameters", **base)


def trigger_conversion_failed():
    class Boom(SkyCoord):
        def transform_to(self, *args, **kwargs):
            raise ValueError("boom")

    coords = SkyFrame(coord=Boom(10 * DEG, 20 * DEG, frame="icrs"))
    return cw.convert_coordinates(coords, "galactic")


def trigger_library_failed(monkeypatch):
    header = make_header("TAN")
    header["AMDX1"] = 1.0  # soluzione storica DSS
    monkeypatch.setattr(cw, "_build_wcs", lambda h: (_ for _ in ()).throw(ValueError("libreria")))
    return cw.wcs_from_header(header)


def trigger_not_constructible(monkeypatch):
    monkeypatch.setattr(cw, "_build_wcs", lambda h: (_ for _ in ()).throw(ValueError("libreria")))
    return cw.wcs_from_header(make_header("TAN"))


def trigger_legacy_not_translated(monkeypatch):
    header = make_header("TAN")
    header["AMDX1"] = 1.0
    monkeypatch.setattr(cw, "_build_wcs", lambda h: (WCS(naxis=2), ()))
    return cw.wcs_from_header(header)


def trigger_no_celestial():
    header = make_header("TAN")
    header["CTYPE1"], header["CTYPE2"] = "LINEAR", "LINEAR"
    return cw.wcs_from_header(header)


def good_stars(projection="TAN", n=12, **kwargs):
    """Stelle da una WCS vera: posizioni pixel e celesti coerenti."""
    rng = np.random.default_rng(7)
    x, y = rng.uniform(5, 195, n), rng.uniform(5, 195, n)
    positions = cw.pixel_to_sky(cw.wcs_from_header(make_header(projection)), x, y, convention="numpy").coords
    base = dict(pixel_x=x, pixel_y=y, convention="numpy", sky=positions, projection=projection,
                pixel_shape=SHAPE)
    base.update(kwargs)
    return cw.astrometric_calibration("stars", **base)


def trigger_fit_failed(monkeypatch):
    monkeypatch.setattr(cw, "fit_wcs_from_points", lambda *a, **k: (_ for _ in ()).throw(ValueError("non converge")))
    return good_stars()


class _FakeWcs:
    """WCS finta: l'andata e ritorno al centro non torna (``not_coherent``)."""

    pixel_scale_matrix = np.eye(2)
    pixel_shape = (10, 10)

    def pixel_to_world(self, x, y):
        return (x, y)

    def world_to_pixel(self, world):
        return (world[0] + 1.0, world[1])


def table_with(**columns):
    from astropy.table import Table

    return Table(columns)


def trigger_net_timeout(monkeypatch, cache):
    def fail(name, timeouts):
        raise ConnectionError("rete assente")

    monkeypatch.setattr(cw, "_query_simbad", fail)
    return cw.resolve_name("M31", cache=cache)


def trigger_name(monkeypatch, cache, table):
    monkeypatch.setattr(cw, "_query_simbad", lambda name, timeouts: (table, "https://simbad.example/tap"))
    return cw.resolve_name("M31", cache=cache)


def test_every_module_10_error_matches_the_catalog(monkeypatch, cache):
    pm = dict(pm_ra_cosdec=1 * u.mas / u.yr, pm_dec=1 * u.mas / u.yr, parallax=1 * u.mas)
    position = icrs_epoch_sky()
    good_header = make_header("TAN")

    def propagate(**kw):
        args = dict(position=position, target_epoch=Time("J2020.0"), radial_velocity=None, **pm)
        args.update(kw)
        return cw.propagate_position(**args)

    triggers = [
        lambda: cw.convert_pixel_convention(1, 1, "xx", "fits"),
        lambda: sky(frame="nonexistent"),
        lambda: sky(frame="galactic", equinox=Time("J2000")),
        trigger_conversion_failed,
        lambda: propagate(position=SkyFrame(coord=SkyCoord(10 * DEG, 20 * DEG, frame="galactic"), epoch=Time("J2016"))),
        lambda: view(projection="TAN", frame="fk5"),
        lambda: cw.format_coordinates(sky(), frame="galactic"),
        lambda: cw.format_coordinates(values=[1] * DEG, axis="lon"),
        # EPOCH_REQUIRED
        lambda: cw._to_epoch("xx", "equinox"),
        lambda: sky(frame="fk5"),
        lambda: cw._check_epochs_explicit(SkyCoord(1 * DEG, 2 * DEG, frame="fk5").frame),
        lambda: SkyFrame(coord=SkyCoord(1 * DEG, 2 * DEG, frame="icrs"), epoch="J2000"),
        lambda: propagate(position=sky()),
        lambda: propagate(pm_ra_cosdec=None),
        lambda: propagate(target_epoch=None),
        # COORD_UNIT_MISSING
        lambda: SkyFrame.from_lonlat(10, 20, "icrs"),
        lambda: SkyFrame.from_lonlat(10 * u.m, 20 * DEG, "icrs"),
        lambda: SkyFrame(coord="x"),
        lambda: cw.convert_coordinates("x", "galactic"),
        lambda: cw.astrometric_calibration("parameters", reference="x", pixel_shape=(10, 10), reference_pixel=(1, 1),
                                           convention="numpy", scale=1 * u.arcsec, rotation=0 * DEG,
                                           projection="TAN", east_left=True),
        lambda: propagate(pm_ra_cosdec=1.0),
        lambda: propagate(radial_velocity=1.0, parallax=1 * u.mas),
        lambda: geometry().sky_to_window("x"),
        lambda: cw.format_coordinates(),
        lambda: cw.format_coordinates(values=[1] * DEG, frame="icrs", axis="x"),
        # COORD_OUT_OF_RANGE
        lambda: SkyFrame.from_lonlat(np.nan * DEG, 0 * DEG, "icrs"),
        lambda: SkyFrame.from_lonlat(10 * DEG, 95 * DEG, "icrs"),
        lambda: SkyFrame.from_lonlat(400 * DEG, 20 * DEG, "icrs"),
        lambda: propagate(parallax=-1 * u.mas),
        lambda: cw.choose_projection(-1 * DEG),
        # NAME_NOT_FOUND
        lambda: cw.resolve_name("", cache=cache),
        lambda: cw.resolve_name("M31", source="x", cache=cache),
        lambda: trigger_net_timeout(monkeypatch, cache),
        lambda: cw.parse_sexagesimal(["xx yy"], hours=True),
        lambda: propagate(proper_motion_only=True),
        # WCS
        lambda: cw.pixel_to_sky(cw.wcs_from_header(good_header), [0], [0], convention="x"),
        lambda: cw._as_wcs("x"),
        lambda: cw.wcs_from_header("x"),
        lambda: cw._as_wcs(WCS(naxis=2)),
        trigger_no_celestial,
        lambda: cw._check_internal_consistency(_FakeWcs()),
        lambda: cw.wcs_from_header(header_with(CD1_1=0.0, CD1_2=0.0, CD2_1=0.0, CD2_2=0.0)),
        lambda: cw.wcs_from_header(header_with(CD1_1=0.01, CD1_2=0.01, CD2_1=0.01, CD2_2=0.01)),
        lambda: cw.choose_grid_spacing(WCS(header_with(CTYPE1="RA---AIT", CTYPE2="DEC--AIT", CRPIX1=1e7)),
                                       frame="icrs", pixel_shape=(10, 10)),
        lambda: cw._column_value(table_with(ra=[1.0]), "ra", u.deg),
        lambda: cw.make_view_wcs(sky(180.0, 0.0), 1 * u.arcsec, (100, 100),
                                 base=view(projection="SIN", center=sky(0.0, 0.0)).base),
        # calibrazioni con dati veri
        lambda: good_stars(thresholds=cw.CalibrationThresholds(max_rms_px=1e-15, max_residual_px=1e-15)),
        lambda: good_stars("STG", thresholds=cw.CalibrationThresholds(coherence_factor=1e-9, max_rms_px=100,
                                                                    max_residual_px=100)),
        lambda: cw.astrometric_calibration("x", pixel_shape=(10, 10)),
        lambda: calibrate_parameters(pixel_shape=None),
        lambda: calibrate_parameters(east_left=None),
        lambda: calibrate_parameters(scale=-1 * u.arcsec),
        # proiezioni
        lambda: view(projection="XYZ"),
        lambda: calibrate_parameters(projection="XYZ"),
        lambda: calibrate_parameters(projection="ZPN"),
        # calibrazioni
        lambda: calibrate_stars(pixel_x=[1, 2, 3]),
        lambda: calibrate_stars(),
        lambda: calibrate_stars(pixel_x=[1, 2], pixel_y=[1, 2], sky=sky_list(2)),
        # griglia
        lambda: cw.compute_grid_lines(cw.wcs_from_header(good_header), frame="icrs", lon_spacing=1, lat_spacing=1 * DEG,
                                      pixel_shape=SHAPE),
        lambda: cw.compute_grid_lines(cw.wcs_from_header(good_header), frame="icrs", lon_spacing=500 * DEG,
                                      lat_spacing=1 * DEG, pixel_shape=SHAPE),
        lambda: cw.choose_grid_spacing(cw.wcs_from_header(good_header), frame="icrs", pixel_shape=SHAPE, target_lines=0),
        lambda: cw.compute_grid_lines(cw.wcs_from_header(good_header), frame="icrs", lon_spacing=1 * DEG,
                                      pixel_shape=SHAPE),
        lambda: cw.compute_grid_lines(cw.wcs_from_header(good_header), frame="icrs", lon_spacing=1 * DEG,
                                      lat_spacing=1 * DEG, pixel_shape=SHAPE, samples_per_line=1),
        # vista
        lambda: view(shape=(0, 5)),
        lambda: view(scale=1.0),
        lambda: view(scale=-1 * u.arcsec),
        lambda: view(center="x"),
        lambda: view(base=geometry().base, projection="TAN"),
        lambda: view(projection=None),
        lambda: view(tangent_point="x"),
        lambda: cw.compass_and_scale_bar("x"),
        lambda: cw.compass_and_scale_bar(geometry(), max_bar_pixels=0),
        lambda: view(projection="NCP"),
        lambda: view(projection="ZPN"),
        # formato
        lambda: cw.format_coordinates(sky(), style="decimal", precision=1 * u.s),
        lambda: cw.format_coordinates(sky(), precision=1 * u.m),
        lambda: cw.format_coordinates(sky(), precision=-1 * u.arcsec),
        lambda: cw.format_coordinates(sky(), precision=1.0),
        lambda: cw.format_coordinates(sky(), style="x"),
        lambda: cw.format_coordinates(sky(), separators="x"),
        lambda: cw.format_coordinates(values=[1] * DEG, frame="galactic", axis="lat", precision=1 * u.s),
    ]
    seen = collect_errors(triggers, CoordinatesWcsError)
    seen |= collect_errors([lambda: trigger_library_failed(monkeypatch)], CoordinatesWcsError)
    monkeypatch.undo()
    seen |= collect_errors([lambda: trigger_not_constructible(monkeypatch)], CoordinatesWcsError)
    monkeypatch.undo()
    seen |= collect_errors([lambda: trigger_legacy_not_translated(monkeypatch)], CoordinatesWcsError)
    monkeypatch.undo()
    seen |= collect_errors([lambda: trigger_fit_failed(monkeypatch)], CoordinatesWcsError)
    monkeypatch.undo()
    for table in (table_with(main_id=["a", "b"], ra=[1.0, 2.0], dec=[1.0, 2.0]),
                  table_with(main_id=["a"], ra=[np.nan], dec=[np.nan]),
                  table_with(main_id=[], ra=[], dec=[])):
        seen |= collect_errors([lambda: trigger_name(monkeypatch, cache, table)], CoordinatesWcsError)
        monkeypatch.undo()
    from astrotwo.messages_catalog import CATALOG

    # ragioni di WCS_MISSING e NET_TIMEOUT sollevate dal modulo 11 (provate in test_messages_images_fits.py)
    module_13 = {("COORD_UNIT_MISSING", "column_unit_required"), ("COORD_UNIT_MISSING", "column_not_angular")}
    module_11 = module_13 | MODULE_14_SUBVARIANTS | MODULE_15_SUBVARIANTS | MODULE_16_SUBVARIANTS | MODULE_17_SUBVARIANTS | MODULE_18_SUBVARIANTS | MODULE_19_SUBVARIANTS | {("NET_TIMEOUT", "url")} | {("WCS_MISSING", r) for r in CATALOG["WCS_MISSING"].variants
                                             if r not in ("header_required", "no_celestial_wcs", "not_celestial",
                                                           "wcs_required")}
    required = {c for c in catalog_combinations(MODULE_CODES)
                if not (c[1] is None and c[0] in GENERAL_IS_FALLBACK)} - module_11
    # avvisi e verifiche che non sono eccezioni (provate sotto) e voci che richiedono dati di rete simulati
    non_exceptions = {("NORTH_UNDEFINED", r) for r in ("center_outside", "pole_near", "direction_outside")}
    non_exceptions |= {("SCALE_BAR_TOO_LONG", None), ("OUT_OF_FIELD", None)}
    missing = required - seen - non_exceptions
    assert not missing, "\n" + "\n".join(map(str, sorted(missing, key=str)))


def test_warnings_of_module_10_match_the_catalog():
    seen = set()
    near_pole = cw.make_view_wcs(sky(0.0, 90.0), 1 * u.arcsec, (100, 100), projection="TAN")
    result = cw.compass_and_scale_bar(near_pole, frame="icrs")
    for warning in result.warnings:
        seen.add(check_message(warning[0], warning.params, warning[1]))
    tiny = cw.make_view_wcs(sky(), 0.001 * u.arcsec, (100, 100), projection="TAN")
    result = cw.compass_and_scale_bar(tiny, max_bar_pixels=5)
    for warning in result.warnings:
        seen.add(check_message(warning[0], warning.params, warning[1]))
    solution = cw.wcs_from_header(make_header("TAN"))
    outside = cw.pixel_to_sky(solution, [10000], [10000], convention="numpy")
    for code in outside.warnings:
        seen.add(check_message(code, {}))
    assert ("NORTH_UNDEFINED", "pole_near") in seen
    assert ("SCALE_BAR_TOO_LONG", None) in seen
    assert ("OUT_OF_FIELD", None) in seen


def test_numbers_of_module_10_errors_keep_their_full_value():
    with pytest.raises(CoordinatesWcsError) as info:
        SkyFrame.from_lonlat(10 * DEG, 95.12345678901235 * DEG, "icrs")
    assert info.value.params["values"] == {"value": [95.12345678901235], "unit": "deg"}
    assert "95.12345678901235 deg" in message_text(info.value.code, info.value.params, "en")
    assert "95.12345678901235 deg" in message_text(info.value.code, info.value.params, "it")
    check_error(info.value)
