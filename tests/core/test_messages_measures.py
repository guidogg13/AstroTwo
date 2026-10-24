# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 17 con codice + ``params`` (D40-3, D40-7; ``40`` §3.7.1, T18–T19; ``17`` §10).

Provoca ogni errore e ogni avviso del modulo; ogni istanza è controllata contro il catalogo alla creazione
(``tests/conftest.py``) e qui si verifica la copertura di tutte le coppie (codice, ragione) del modulo, gli errori
rilanciati e il testo italiano invariato.
"""

from __future__ import annotations

import dataclasses

import astropy.units as u
import numpy as np
import pytest

from astrotwo import messages_catalog as mc
from astrotwo.core import measures
from astrotwo.core.coordinates_wcs import ModuleWarning
from astrotwo.core.images_fits import LargeImageLimits
from astrotwo.core.measures import (
    Arrow,
    CatalogSource,
    Circle,
    Ellipse,
    Freehand,
    MeasuresError,
    Polygon,
    Text,
    angular_distance,
    apply_offsets,
    auto_distance,
    offset_position,
    position_angle,
    profile_along_line,
    read_pixel,
)
from tests.core.test_measures import catalog, icrs, numpy_px, write_image
from tests.message_helpers import (
    MODULE_14_SUBVARIANTS,
    MODULE_15_SUBVARIANTS,
    MODULE_16_SUBVARIANTS,
    MODULE_19_SUBVARIANTS,
    catalog_combinations,
    check_error,
    check_message,
)

OWN_CODES = (
    "PA_UNDEFINED", "OFFSET_INVALID", "POINT_OUT_OF_IMAGE", "NO_WCS", "PROFILE_STEP_INVALID", "SHAPE_INVALID",
    "DISTANCE_PRECISION_NOT_REACHED", "AREA_PRECISION_NOT_REACHED", "SELECTION_NOT_TWO_SOURCES",
)
SHARED = (
    {("FRAME_UNKNOWN", "measure_point"), ("FRAME_UNKNOWN", "measure_columns"),
     ("MEMORY_LIMIT_EXCEEDED", "profile"), ("NO_COORD_COLUMNS", "measure_no_positions"),
     ("NO_COORD_COLUMNS", "row_position_missing"), ("BODY_UNKNOWN", "measure_sources"),
     ("BODY_MISMATCH", "sources"), ("NONFINITE_PIXELS", "window"), ("NONFINITE_PIXELS", "samples")}
    | {("OPERATION_UNSUPPORTED", r) for r in ("shape_kind", "open_path", "text_distance")}
    | {("EPOCH_REQUIRED", r) for r in ("row_epoch", "pm_columns", "row_incomplete", "epoch_invalid")}
)


def required_combinations() -> set[tuple[str, str | None]]:
    out = {(c, r) for c, r in catalog_combinations(OWN_CODES) if r is not None or not mc.CATALOG[c].variants}
    return out | SHARED


class Seen:
    def __init__(self) -> None:
        self.pairs: set[tuple[str, str | None]] = set()

    def error(self, func, *args, **kwargs) -> MeasuresError:
        with pytest.raises(MeasuresError) as info:
            func(*args, **kwargs)
        self.pairs.add(check_error(info.value))
        return info.value

    def notes(self, items) -> None:
        for item in items:
            if isinstance(item, ModuleWarning):
                self.pairs.add(check_message(item[0], item.params, item[1]))


def test_every_error_and_warning_has_code_params_and_catalog_entry(tmp_path, monkeypatch):
    seen = Seen()
    p = icrs(10, 10)

    # --- punti, angoli, offset ----------------------------------------------------------------------------------------
    seen.error(position_angle, 5, p)  # measure_point
    seen.error(position_angle, p, icrs(10, 10))  # coincident
    seen.error(position_angle, icrs(0, 0), icrs(180, 0))  # antipodal
    seen.error(position_angle, icrs(0, 90), icrs(10, 10))  # pole
    seen.error(offset_position, p, 1.0, 0 * u.deg)  # not_angle
    seen.error(offset_position, p, np.nan * u.deg, 0 * u.deg)  # not_finite
    seen.error(offset_position, p, 181 * u.deg, 0 * u.deg)  # distance_range
    seen.error(apply_offsets, p, 1.0, 1 * u.deg)
    err = seen.error(auto_distance, [CatalogSource(catalog(tmp_path, "z", [1.0, 2.0], [1.0, 2.0], epoch=2016.0), 0),
                                     CatalogSource(catalog(tmp_path, "y", [1.0, 2.0], [1.0, 2.0], epoch=2016.0), 1)],
                     "arcsec", epoch="boh")  # errore del 10 rilanciato
    assert err.relayed and err.message.startswith("epoch:")
    assert angular_distance is not None

    # --- pixel e profili ----------------------------------------------------------------------------------------------
    data = np.arange(100, dtype=np.float64).reshape(10, 10)
    image = write_image(tmp_path, data)
    seen.error(read_pixel, image, numpy_px(np.nan, 1))  # not_finite
    seen.error(read_pixel, image, icrs(10, -60))  # outside_wcs / outside_pixels
    seen.error(read_pixel, image, numpy_px(100, 100))  # outside_pixels
    seen.error(read_pixel, image, numpy_px(1, 1), half_size=3)  # window
    seen.error(profile_along_line, image, numpy_px(1, 1), numpy_px(9.2, 5), 1)  # outside_centers
    for step in (1 * u.arcsec, "1", 0):
        seen.error(profile_along_line, image, numpy_px(1, 1), numpy_px(5, 5), step)  # not_pixels, not_number, not_positive
    plain = write_image(tmp_path, data, wcs=False, name="plain.fits")
    seen.error(read_pixel, plain, icrs(150, 2))  # NO_WCS
    with monkeypatch.context() as patch:
        patch.setattr(type(image), "limits", LargeImageLimits(operation_bytes=10), raising=False)
        object.__setattr__(image, "limits", LargeImageLimits(operation_bytes=10))
        seen.error(profile_along_line, image, numpy_px(0, 0), numpy_px(9, 9), 1)  # profile
    holes = data.copy()
    holes[3, 3] = np.nan
    holey = write_image(tmp_path, holes, name="holey.fits")
    seen.notes(read_pixel(holey, numpy_px(3, 3)).report.warnings)  # window
    seen.notes(profile_along_line(holey, numpy_px(0, 3), numpy_px(9, 3), 1).report.warnings)  # samples

    # --- forme --------------------------------------------------------------------------------------------------------
    centre = icrs(0, 0)
    seen.error(Circle, centre, 1.0)  # not_angle
    seen.error(Circle, centre, np.nan * u.deg)  # not_finite
    seen.error(Circle, centre, 200 * u.deg)  # radius_range
    seen.error(Ellipse, centre, 5 * u.deg, 8 * u.deg, 0 * u.deg)  # semiaxes
    seen.error(Polygon, [])  # no_points
    seen.error(Polygon, [icrs(0, 0), icrs(10, 0)])  # few_vertices
    seen.error(Polygon, [icrs(0, 0), icrs(10, 10), icrs(0, 10), icrs(10, 0)])  # self_intersects
    seen.error(Polygon, [icrs(0, 0), icrs(1, 0), icrs(2, 0)])  # degenerate
    with monkeypatch.context() as patch:  # due regioni di area uguale: caso esatto, qui simulato
        patch.setattr(measures.SphericalPolygon, "area", lambda self: 2 * np.pi)
        seen.error(Polygon, [icrs(0, 0), icrs(90, 0), icrs(0, 90)])  # equal_areas
    arrow, text, opened = Arrow(icrs(1, 1), icrs(2, 2)), Text(icrs(1, 1), "M1"), Freehand([icrs(0, 0), icrs(5, 0), icrs(6, 4)])
    seen.error(arrow.area)  # shape_kind
    seen.error(opened.area)  # open_path
    seen.error(text.distance_to, Circle(centre, 1 * u.deg))  # text_distance
    long_ellipse = Ellipse(icrs(0, 0), 60 * u.deg, 0.001 * u.deg, 0 * u.deg)
    with monkeypatch.context() as patch:
        patch.setattr(measures, "ELLIPSE_MAX_SAMPLES", 256)
        seen.error(long_ellipse.distance_to, icrs(0.3, 59.9), atol=1e-14 * u.deg)  # DISTANCE_PRECISION_NOT_REACHED
    seen.error(Ellipse(icrs(0, 0), 89 * u.deg, 0.01 * u.deg, 0 * u.deg).area)  # AREA_PRECISION_NOT_REACHED

    # --- distanza automatica ------------------------------------------------------------------------------------------
    cat = catalog(tmp_path, "a", [10.0, 10.2, 11.0], [-5.0, -4.9, -5.5], epoch=2016.0)
    seen.error(auto_distance, [CatalogSource(cat, 0)], "arcsec")  # SELECTION_NOT_TWO_SOURCES
    mars = dataclasses.replace(cat, body="Mars")
    seen.error(auto_distance, [CatalogSource(cat, 0), CatalogSource(mars, 0)], "deg")  # sources
    seen.error(auto_distance, [CatalogSource(cat, 0), CatalogSource(dataclasses.replace(cat, body=None), 0)], "deg")
    seen.error(auto_distance, [CatalogSource(dataclasses.replace(cat, positions=None), 0), CatalogSource(cat, 0)],
               "arcsec")  # measure_no_positions
    seen.error(auto_distance, [CatalogSource(dataclasses.replace(
        cat, positions=dataclasses.replace(cat.positions, frame=None)), 0), CatalogSource(cat, 0)], "arcsec")
    masked = catalog(tmp_path, "m", [150.0, 151.0], [2.0, 3.0], epoch=2016.0)
    masked.table["RA"] = np.ma.masked_array(masked.table["RA"], mask=[True, False])
    masked.table["RA"].unit = u.deg
    masked.table["RA"].meta["ucd"] = "pos.eq.ra;meta.main"
    seen.error(auto_distance, [CatalogSource(cat, 0), CatalogSource(masked, 0)], "arcsec")  # row_position_missing
    masked_epoch = catalog(tmp_path, "n", [150.0, 151.0], [2.0, 3.0], epoch=2016.0)
    masked_epoch.table["ep"] = np.ma.masked_array(masked_epoch.table["ep"], mask=[True, False])
    masked_epoch.table["ep"].unit = u.yr
    masked_epoch.table["ep"].meta["ucd"] = "meta.ref;time.epoch"
    seen.error(auto_distance, [CatalogSource(masked_epoch, 0), CatalogSource(cat, 0)], "arcsec")  # row_epoch
    no_epoch = catalog(tmp_path, "c", [150.0], [2.0])
    b = catalog(tmp_path, "b", [150.01], [2.01], epoch=2016.0)
    seen.error(auto_distance, [CatalogSource(b, 0), CatalogSource(no_epoch, 0)], "arcsec")  # row_epoch
    a_pm = catalog(tmp_path, "d", [150.0], [2.0], epoch=2000.0, pm=([500.0], [-300.0]), plx=[20.0])
    seen.error(auto_distance, [CatalogSource(b, 0), CatalogSource(a_pm, 0)], "arcsec")  # pm_columns
    seen.error(auto_distance, [CatalogSource(b, 0), CatalogSource(no_epoch, 0, source_epoch="boh")], "arcsec")
    broken = catalog(tmp_path, "e", [150.0], [2.0], epoch=2000.0, pm=([np.nan], [-300.0]), plx=[20.0])
    seen.error(auto_distance, [CatalogSource(b, 0), CatalogSource(
        broken, 0, pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True, parallax="plx")], "arcsec")  # row_incomplete

    missing = (required_combinations() - seen.pairs - MODULE_14_SUBVARIANTS - MODULE_15_SUBVARIANTS
               - MODULE_16_SUBVARIANTS - MODULE_19_SUBVARIANTS)
    assert not missing, f"errori e avvisi del 17 mai provocati nel test: {sorted(missing, key=str)}"


def test_italian_text_is_unchanged_and_catalog_renders_both_languages():
    with pytest.raises(MeasuresError) as info:
        position_angle(icrs(0, 0), icrs(180, 0))
    err = info.value
    assert err.message == "punti antipodali: ogni direzione porta al secondo punto"
    assert err.params == {"reason": "antipodal"}
    assert mc.message_text(err.code, err.params, "en") == "Antipodal points: every direction leads to the second point."
    assert mc.message_text(err.code, err.params, "it") == "Punti antipodali: ogni direzione porta al secondo punto."
    with pytest.raises(MeasuresError) as info:
        offset_position(icrs(10, 10), 181 * u.deg, 0 * u.deg)
    assert info.value.params == {"reason": "distance_range", "distance": {"value": 181.0, "unit": "deg"}}
