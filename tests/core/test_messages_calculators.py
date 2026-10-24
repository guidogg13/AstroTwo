# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 18 con codice + ``params`` (D40-3; ``40`` §3.7.1, T18–T19; ``18`` §10).

Provoca ogni errore del modulo; ogni istanza è controllata contro il catalogo alla creazione
(``tests/conftest.py``) e qui si verifica la copertura di tutte le coppie (codice, ragione) del modulo, gli errori
rilanciati e il testo italiano invariato.
"""

from __future__ import annotations

import dataclasses

import astropy.units as u
import numpy as np
import pytest
from astropy.time import Time
from astropy.utils import iers

from astrotwo import messages_catalog as mc
from astrotwo.core import calculators
from astrotwo.core.calculators import (
    CalculatorError,
    CoordinateInput,
    CoordinateTarget,
    DisplaySettings,
    ProperMotion,
    calculate_coordinates,
    convert_pixel_value,
    convert_time,
    convert_units,
    evaluate_expression,
    run_command,
    update_iers_table,
)
from astrotwo.core.coordinates_wcs import SkyFrame
from tests.core.test_calculators import scaled_fits
from tests.message_helpers import (
    MODULE_14_SUBVARIANTS,
    MODULE_15_SUBVARIANTS,
    MODULE_16_SUBVARIANTS,
    MODULE_17_SUBVARIANTS,
    MODULE_19_SUBVARIANTS,
    catalog_combinations,
    check_error,
)

OWN_CODES = (
    "CALC_SYNTAX_ERROR", "CALC_UNKNOWN_FUNCTION", "CALC_OVERFLOW", "CALC_DIVISION_BY_ZERO", "CALC_DOMAIN_ERROR",
    "CALC_TOO_COMPLEX", "UNIT_SEXAGESIMAL_UNIT_REQUIRED", "TIME_SCALE_REQUIRED", "TIME_INVALID",
    "IERS_TABLE_MISSING", "IERS_TABLE_INVALID", "IERS_RANGE", "UNIT_EQUIVALENCY_UNKNOWN", "UNIT_REFERENCE_REQUIRED",
    "UNIT_ZERO_POINT_REQUIRED", "PIXEL_BLANK", "PIXEL_BSCALE_ZERO", "CALC_COMMAND_INVALID",
)
SHARED = (
    {("NET_TIMEOUT", "iers_no_new"), ("OPERATION_UNSUPPORTED", "histeq"), ("EPOCH_REQUIRED", "propagation_motion")}
    | {("UNIT_UNKNOWN", r) for r in ("not_text", "unknown", "unknown_similar")}
    | {("UNIT_INCOMPATIBLE", r) for r in ("reference", "skydist", "types", "types_hint")}
)


def required_combinations() -> set[tuple[str, str | None]]:
    out = {(c, r) for c, r in catalog_combinations(OWN_CODES) if r is not None or not mc.CATALOG[c].variants}
    return out | {("CALC_OVERFLOW", None), ("CALC_DIVISION_BY_ZERO", None), ("CALC_DOMAIN_ERROR", None)} | SHARED


class Seen:
    def __init__(self) -> None:
        self.pairs: set[tuple[str, str | None]] = set()

    def error(self, func, *args, **kwargs) -> CalculatorError:
        with pytest.raises(CalculatorError) as info:
            func(*args, **kwargs)
        self.pairs.add(check_error(info.value))
        return info.value

    def expression(self, text: str, **kwargs) -> CalculatorError:
        return self.error(evaluate_expression, text, **kwargs)


def command(name: str, parameters, version: int = 1) -> dict:
    return {"name": f"calc.{name}", "version": version, "parameters": parameters}


def test_every_error_has_code_params_and_catalog_entry(tmp_path, monkeypatch, service, cache):
    seen = Seen()
    prefix = calculators._SEXAGESIMAL_PREFIX

    # --- calcolatrice algebrica ---------------------------------------------------------------------------------------
    for text in ("", "1+", "2**3", "a:b", "0x10", "1d2m3s + 1", "sin(x=1)", "sin(1, 2)", "max(1)", "[1]"):
        seen.expression(text)
    seen.expression("a.b")  # construct (CALC_UNKNOWN_FUNCTION)
    seen.expression(f"1 + {prefix}0")  # sexagesimal_prefix
    for text in ("foo", "foo(1)", "None"):
        seen.expression(text)
    seen.expression("1/0")
    seen.expression("sqrt(-1)")
    seen.expression("1e308 * 10")
    seen.expression("1+1+1", max_length=3)  # length
    seen.expression("((1))", max_depth=1)  # depth
    seen.expression("1" + "+1" * 3000, max_length=10**7, max_depth=10**6)  # chain
    seen.expression("1" + "+1" * 100000, max_length=10**7, max_depth=10**6)  # parser
    seen.expression("skydist(1:2:3, 0, 0, 0)")  # colon_ambiguous
    seen.expression("skydist(1:2:3, 0, 0, 0)", colon_units=5)  # colon_units_value
    seen.expression("skydist(1:2:3, 0, 0, 0)", colon_units=["hours", "degrees"])  # colon_units_count

    # --- unità -------------------------------------------------------------------------------------------------------
    seen.error(convert_units, 1, None, "m")  # not_text
    seen.error(convert_units, 1, "zzzzzz", "m")  # unknown
    seen.error(convert_units, 1, "arcsecs", "deg")  # unknown_similar
    seen.error(convert_units, 1, "m", "s")  # types_hint
    seen.error(convert_units, 500, "nm", "Hz", "boh")  # UNIT_EQUIVALENCY_UNKNOWN
    seen.error(convert_units, 1, "km/s", "GHz", "doppler_optical")  # UNIT_REFERENCE_REQUIRED
    seen.error(convert_units, 1, "km/s", "GHz", "doppler_radio", reference=1 * u.kg)  # reference
    seen.error(convert_units, 10, "mag", "Jy")  # UNIT_ZERO_POINT_REQUIRED
    seen.error(convert_units, "skydist(0, 0, 1, 0)", "m", "rad")  # skydist
    with monkeypatch.context() as patch:  # types (con un'equivalenza richiesta): conversione che l'equivalenza non copre
        seen.error(convert_units, 1, "m", "s", "spectral")
        assert patch is not None
    seen.error(convert_units, float("nan"), "m", "km")  # not_finite
    seen.error(convert_units, 1e308, "km", "m")  # result_not_finite
    seen.error(convert_units, "10:30:00", "deg", "rad")  # angle_text
    seen.error(convert_units, "2020-01-01T00:00:00", None, "kg", scale="utc")  # to_unit (CALC: data)

    # --- tempo --------------------------------------------------------------------------------------------------------
    seen.error(convert_time, "2020-01-01T00:00:00", "iso", None)  # missing
    seen.error(convert_time, "2020-01-01T00:00:00", "iso", "xx")  # unknown
    seen.error(convert_time, 5, "iso", "utc")  # iso_type
    seen.error(convert_time, "2020-13-45T00:00:00", "iso", "utc")  # iso_invalid
    seen.error(convert_time, float("nan"), "jd", "utc")  # number
    with monkeypatch.context() as patch:  # astropy accetta ogni numero finito: ramo di difesa, qui simulato
        patch.setattr(calculators, "Time", lambda *a, **k: (_ for _ in ()).throw(ValueError("fuori limite")))
        seen.error(convert_time, 1.0, "jd", "utc")  # format_value
    seen.error(convert_time, "2020-01-01", "boh", "utc")  # format
    seen.error(convert_time, "2300-01-01T00:00:00", "iso", "utc", "ut1")  # IERS_RANGE date
    with monkeypatch.context() as patch:  # data al bordo della tabella (UT1 → UTC itera sulla data): simulato
        patch.setattr(Time, "ut1", property(lambda self: (_ for _ in ()).throw(iers.IERSRangeError("bordo"))),
                     raising=False)
        seen.error(convert_time, "2020-01-01T00:00:00", "iso", "utc", "ut1")  # limit
    with monkeypatch.context() as patch:
        patch.setattr(Time, "tai", property(lambda self: (_ for _ in ()).throw(ValueError("non definita"))),
                     raising=False)
        seen.error(convert_time, "2020-01-01T00:00:00", "iso", "utc", "tai")  # conversion
    seen.error(convert_time, "2020-01-01T00:00:00", "iso", "utc", "ut1", iers_table="updated", cache=cache)
    payload = open(iers.IERS_A_FILE, "rb").read()
    service.routes["/finals2000A.all"] = lambda request: (200, "text/plain", payload)
    service.routes["/bad"] = lambda request: (200, "text/plain", b"non una tabella")
    seen.error(update_iers_table, cache=cache, url=f"{service.url}/bad")  # IERS_TABLE_INVALID
    update_iers_table(cache=cache, url=f"{service.url}/finals2000A.all")
    service.close()
    with monkeypatch.context() as patch:  # rete assente con la risposta già nella cache del 14: nessuna tabella nuova
        cached = type("Cached", (), {"from_cache": True, "payload": b"", "notes": ()})()
        patch.setattr(calculators.vo_protocols, "_http", lambda *a, **k: cached)
        seen.error(update_iers_table, cache=cache, url=f"{service.url}/finals2000A.all")  # iers_no_new
    err = seen.error(update_iers_table, cache=None, url="http://127.0.0.1:9/finals2000A.all")
    assert err.relayed and err.code == "NET_TIMEOUT"

    # --- pixel -------------------------------------------------------------------------------------------------------
    seen.error(convert_pixel_value, raw=-5, bzero=10.0, bscale=0.5, blank=-5)  # PIXEL_BLANK
    seen.error(convert_pixel_value, physical=1.0, bzero=0.0, bscale=0.0)  # PIXEL_BSCALE_ZERO
    seen.error(convert_pixel_value, raw=1, bzero=0, bscale=1, display=DisplaySettings(0.0, 1.0, stretch="histeq"))
    seen.error(convert_pixel_value, raw=1e308, bzero=0, bscale=1e308)  # CALC_OVERFLOW value

    # --- coordinate ---------------------------------------------------------------------------------------------------
    motion = ProperMotion(pm_ra_cosdec=500 * u.mas / u.yr, pm_dec=-300 * u.mas / u.yr, parallax=20 * u.mas)
    start = SkyFrame.from_lonlat(150.0 * u.deg, 2.0 * u.deg, "icrs", epoch=Time(2000.0, format="jyear", scale="tt"))
    seen.error(calculate_coordinates, start, [CoordinateTarget("icrs")], epoch=2016.0)  # propagation_motion
    seen.error(calculate_coordinates, CoordinateInput(lon="10:30:00", lat=5.0, frame="icrs"),
               [CoordinateTarget("icrs")])  # longitude
    assert motion is not None

    # --- comandi nel formato del 05 -----------------------------------------------------------------------------------
    good = evaluate_expression("1+1").command_05()
    position = {"lon": {"value": 1.0, "unit": "deg"}, "lat": {"value": 1.0, "unit": "deg"}, "frame": "icrs"}
    broken = [
        command("evaluate_expression", 5),  # params_not_object
        command("evaluate_expression", {"expression": "1", "bogus": 1}),  # unknown_params
        command("convert_units", {"value": "x", "from_unit": "m", "to_unit": "km"}),  # expect_number
        {**good, "parameters": {**good["parameters"], "max_length": "1000"}},  # expect_integer
        command("evaluate_expression", {"expression": 5}),  # expect_text
        command("calculate_coordinates", {"position": position, "targets": [], "motion": {"proper_motion_only": "x"}}),
        command("convert_pixel_value", {"raw": 1.0, "bzero": 0.0, "bscale": 1.0, "display": 5}),  # expect_record
        command("convert_units", {"value": 1.0, "from_unit": "m", "to_unit": "nm", "reference": {"value": 1.0}}),
        command("convert_units", {"value": 1.0, "from_unit": "m", "to_unit": "nm",
                                  "reference": {"value": 1.0, "unit": "zzz"}}),  # expect_unit
        command("calculate_coordinates", {"position": position, "targets": [], "epoch": 5}),  # expect_time
        command("calculate_coordinates", {"position": position, "targets": [],
                                          "epoch": {"value": "x", "format": "jd", "scale": "tt"}}),  # unreadable
        command("convert_pixel_value", {"image": "L9", "position": {"x": 0.0, "y": 0.0, "convention": "numpy"}}),
        command("convert_pixel_value", {"image": "L9", "position_sky": {"lon": {"value": 1.0, "unit": "deg"}}}),
        command("convert_pixel_value", {"image": "L9", "position_sky": {**position, "epoch": None}}),  # epoch_reason
        {"name": "calc.convert_units", "bogus": 1},  # command_shape
        {"name": "calc.unknown", "version": 1, "parameters": {}},  # not_calculator
        {**good, "version": 2},  # version
        command("evaluate_expression", {"expression": "1", "colon_units_each": [1]}),  # colon_units_each
        command("evaluate_expression", {"expression": "1", "colon_units": "hours", "colon_units_each": ["hours"]}),
        command("convert_units", {"value": 1.0, "value_text": "2", "from_unit": "m", "to_unit": "km"}),  # value_both
        command("convert_pixel_value", {"image": "L9"}),  # image_position
        command("convert_pixel_value", {"image": "L9", "position": {"x": 0.0, "y": 0.0, "convention": "fits"}}),
        command("calculate_coordinates", {"position": position, "catalog_row": {}, "targets": []}),  # position_both
        command("calculate_coordinates", {"position": {"lon": {"value": 1.0, "unit": "deg"}}, "targets": []}),
        command("calculate_coordinates", {"position": position, "targets": "icrs"}),  # targets_list
        command("calculate_coordinates", {"position": position, "targets": [{"equinox": None}]}),  # target_frame
        command("convert_time", {"time_value": 1.0, "time_text": "x", "time_format": "jd", "scale": "utc"}),
    ]
    for item in broken:
        err = seen.error(run_command, item, {})
        assert err.code == "CALC_COMMAND_INVALID"

    missing = (required_combinations() - seen.pairs - MODULE_14_SUBVARIANTS - MODULE_15_SUBVARIANTS
               - MODULE_16_SUBVARIANTS - MODULE_17_SUBVARIANTS - MODULE_19_SUBVARIANTS)
    assert not missing, f"errori del 18 mai provocati nel test: {sorted(missing, key=str)}"
    assert scaled_fits is not None and dataclasses is not None and np is not None


def test_italian_text_is_unchanged_and_catalog_renders_both_languages():
    with pytest.raises(CalculatorError) as info:
        evaluate_expression("2**3")
    err = info.value
    assert err.message == "'**' non previsto: la potenza si scrive '^' (carattere 1): '2**3'"
    assert err.params == {"reason": "power", "position": 1, "expression": "2**3"}
    assert mc.message_text(err.code, err.params, "en") == (
        "'**' is not provided: the power is written '^' (character 1): '2**3'.")
    assert mc.message_text(err.code, err.params, "it") == (
        "'**' non previsto: la potenza si scrive '^' (carattere 1): '2**3'.")
