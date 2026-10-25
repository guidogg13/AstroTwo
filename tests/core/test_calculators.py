# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del modulo 18 (``mdfiles/18-core-calcolatrici.md`` §12).

I valori attesi si ricalcolano nel test con la libreria indicata (``numpy``, ``astropy``), mai copiati da
altri programmi (regola d'oro n. 8).
"""

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import Angle, SkyCoord
import matplotlib
from astropy.io import fits
from astropy.time import Time

from astrotwo.core.calculators import (
    CalculatorError,
    CoordinatesOutput,
    CalculatorResult,
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
import dataclasses
import warnings
from pathlib import Path

from astropy.coordinates import Distance
from astropy.table import Table

from astrotwo.core.catalogs import confirm_position_columns, read_table
from astrotwo.core.coordinates_wcs import PixelPosition, SkyFrame, convert_coordinates
from astrotwo.core.images_fits import cutout, load_image, set_display
from astrotwo.core.measures import CatalogSource, angular_distance, offset_position


def same_result(a: CalculatorResult, b: CalculatorResult) -> bool:
    """Stesso input interpretato, valore, unità e scala (l'istante della richiesta cambia)."""
    return (a.input, a.unit, a.scale, a.calculator) == (b.input, b.unit, b.scale, b.calculator) \
        and np.array_equal(np.asarray(a.value), np.asarray(b.value))


# =============================================================================
# P1 — calcolatrice algebrica (T1–T5, D18-5)


def test_t1_simple_expression():
    result = evaluate_expression("3*8")
    assert result.value == 24.0 and result.value.dtype == np.float64
    assert result.unit == u.dimensionless_unscaled and result.input == "3*8"
    assert "numpy" in result.library and result.requested_at.tzinfo is not None
    # '=' prima o dopo l'espressione.
    assert evaluate_expression("= 3*8").value == 24.0 and evaluate_expression("3*8 =").value == 24.0
    # Operatori, precedenza, potenza con '^', costanti e notazione esponenziale.
    assert evaluate_expression("2^10").value == 1024.0
    assert evaluate_expression("-2^2").value == -4.0  # come in matematica: −(2²)
    assert evaluate_expression("7 % 3 + (1 + 2) * 4 / 8").value == 1.0 + 12.0 / 8.0
    assert evaluate_expression("1.5e3 + .5").value == 1500.5
    assert evaluate_expression("pi").value == np.pi and evaluate_expression("e").value == np.e
    assert evaluate_expression("min(3, 1, 2) + max(4, 5)").value == 6.0
    assert evaluate_expression("dist(0, 0, 3, 4)").value == 5.0


def test_t2_degrees_and_radians():
    a, b = evaluate_expression("sind(30)"), evaluate_expression("sin(pi/6)")
    assert abs(a.value - 0.5) < 1e-15 and abs(b.value - 0.5) < 1e-15
    assert a.value == np.sin(np.deg2rad(30.0)) and b.value == np.sin(np.pi / 6)
    assert evaluate_expression("atan2d(1, 1)").value == np.rad2deg(np.arctan2(1.0, 1.0))
    assert evaluate_expression("cosd(60)").value == np.cos(np.deg2rad(60.0))
    note = evaluate_expression("asind(0.5)").notes
    assert any("numeri puri" in n for n in note)


def test_t3_no_code_execution(tmp_path):
    marker = tmp_path / "eseguito"
    attempts = (f"__import__('os').system('touch {marker}')", f"open('{marker}', 'w')", "exec('1')",
                "print(1)", "x + 1", "(1).real", "True + 1")
    for text in attempts:
        with pytest.raises(CalculatorError) as exc:
            evaluate_expression(text)
        assert exc.value.code == "CALC_UNKNOWN_FUNCTION", text
    assert not marker.exists()
    for text in ("1 +", "2 ** 3", "0x10", "1_000", "'a'", "1 < 2", "lambda: 1", "[1]", "1j", "sin(x=1)", "sin(1, 2)",
                 ""):
        with pytest.raises(CalculatorError) as exc:
            evaluate_expression(text)
        assert exc.value.code == "CALC_SYNTAX_ERROR", text
    with pytest.raises(CalculatorError) as exc:
        evaluate_expression("1 + * 2")
    assert exc.value.details["position"] == 4


def test_t4_invalid_domain():
    for text, code in (("sqrt(-1)", "CALC_DOMAIN_ERROR"), ("ln(0)", "CALC_DOMAIN_ERROR"), ("1/0", "CALC_DIVISION_BY_ZERO"),
                       ("asin(2)", "CALC_DOMAIN_ERROR"), ("5 % 0", "CALC_DIVISION_BY_ZERO"),
                       ("0^-1", "CALC_DIVISION_BY_ZERO"), ("(-8)^(1/3)", "CALC_DOMAIN_ERROR"),
                       ("exp(1000)", "CALC_OVERFLOW"), ("10^400", "CALC_OVERFLOW"), ("1e400", "CALC_OVERFLOW"),
                       ("1e308 * 10", "CALC_OVERFLOW")):
        with pytest.raises(CalculatorError) as exc:
            evaluate_expression(text)
        assert exc.value.code == code, text
    assert evaluate_expression("1e-320 * 1e-10").value == 0.0  # underflow verso zero: valore finito


def test_t5_skydist():
    pairs = ((10.0, 20.0, 10.5, 20.5), (0.0, -89.0, 180.0, -89.0), (359.0, 0.0, 1.0, 0.0))
    for ra1, dec1, ra2, dec2 in pairs:
        result = evaluate_expression(f"skydist({ra1}, {dec1}, {ra2}, {dec2})")
        expected = SkyCoord(ra1 * u.deg, dec1 * u.deg).separation(SkyCoord(ra2 * u.deg, dec2 * u.deg)).deg
        via_17 = angular_distance(SkyFrame.from_lonlat(ra1 * u.deg, dec1 * u.deg, "icrs"),
                                  SkyFrame.from_lonlat(ra2 * u.deg, dec2 * u.deg, "icrs"), "deg").value.value
        assert result.value == via_17 and abs(result.value - expected) < 1e-12
        assert result.unit == u.deg and "modulo 17" in result.library
    # Dentro un'espressione: numero puro, dichiarato.
    combined = evaluate_expression("skydist(10, 20, 10.5, 20.5) * 60")
    assert combined.unit == u.dimensionless_unscaled and any("numeri puri" in n for n in combined.notes)
    # Coordinate fuori intervallo: errore del modulo 10 inoltrato.
    with pytest.raises(CalculatorError) as exc:
        evaluate_expression("skydist(10, 95, 10, 20)")
    assert exc.value.code == "COORD_OUT_OF_RANGE"
    # Due punti senza unità dichiarata: ambiguo (D18-7).
    with pytest.raises(CalculatorError) as exc:
        evaluate_expression("skydist(10:20:30, 20, 10, 20)")
    assert exc.value.code == "UNIT_SEXAGESIMAL_UNIT_REQUIRED" and "D18-7" in exc.value.message


def test_t5_skydist_sexagesimal_d18_7():
    a = SkyCoord("10h30m00s", "-20d15m30s")
    b = SkyCoord("10h31m12.5s", "-20d05m00s")
    expected = a.separation(b).deg
    written = ("skydist(10h30m00s, -20d15m30s, 10h31m12.5s, -20d05m00s)",
               "skydist(10h30m00s, -20°15′30″, 10h31m12.5s, -20°05′00″)",
               "skydist(10h30m00s, -20°15'30\", 10h31m12.5s, -20°05'00\")")
    for text in written:
        result = evaluate_expression(text)
        assert abs(result.value - expected) < 1e-12 and result.unit == u.deg
        assert any("unità scritta nel testo" in n and "parse_sexagesimal" in n for n in result.notes)
        assert run_command(result.command).value == result.value
    # Gradi per tutte e quattro: l'unità nel testo decide, non la posizione dell'argomento.
    in_degrees = evaluate_expression("skydist(157d30m, -20d15m30s, 157d48m07.5s, -20d05m)")
    assert abs(in_degrees.value - expected) < 1e-12
    # Due punti: solo con l'unità dichiarata nel parametro (tutti uguali o uno per valore, in ordine).
    colon = "skydist(10:30:00, -20:15:30, 10:31:12.5, -20:05:00)"
    for units in (None, "hours", ("hours", "degrees"), ("hours", "degrees", "hours", "minutes")):
        with pytest.raises(CalculatorError) as exc:
            evaluate_expression(colon, colon_units=units)
        if units is None or units == "hours":
            assert exc.value.code in ("UNIT_SEXAGESIMAL_UNIT_REQUIRED", "COORD_OUT_OF_RANGE")
        else:
            assert exc.value.code == "UNIT_SEXAGESIMAL_UNIT_REQUIRED"
    declared = evaluate_expression(colon, colon_units=("hours", "degrees", "hours", "degrees"))
    assert abs(declared.value - expected) < 1e-12
    assert any("unità dichiarata in colon_units" in n for n in declared.notes)
    assert run_command(declared.command).value == declared.value
    all_degrees = evaluate_expression("skydist(157:30:00, 10, 157:48:07.5, 10)", colon_units="degrees")
    assert abs(all_degrees.value - SkyCoord(157.5, 10, unit="deg").separation(SkyCoord(157.8020833333333, 10,
                                                                                         unit="deg")).deg) < 1e-12
    # Sessagesimali fuori da skydist o due punti isolati: errore di sintassi; testo illeggibile: errore del 10.
    for text in ("10h30m + 1", "1:2 * 3", "skydist(1, 2, 3, 4) + 2d"):
        with pytest.raises(CalculatorError) as exc:
            evaluate_expression(text, colon_units="degrees")
        assert exc.value.code == "CALC_SYNTAX_ERROR"
    with pytest.raises(CalculatorError) as exc:
        evaluate_expression("skydist(10h75m, 0, 0, 0)")
    assert exc.value.code in ("COORD_FORMAT_INVALID", "COORD_OUT_OF_RANGE")


def test_d18_5_limits():
    with pytest.raises(CalculatorError) as exc:
        evaluate_expression("1+" * 500 + "1")  # 1001 caratteri
    assert exc.value.code == "CALC_TOO_COMPLEX" and exc.value.details["limit"] == 1000
    assert evaluate_expression("1+" * 499 + "1").value == 500.0  # 999 caratteri: catena lunga ma non annidata
    nested = "(" * 51 + "1" + ")" * 51
    with pytest.raises(CalculatorError) as exc:
        evaluate_expression(nested)
    assert exc.value.code == "CALC_TOO_COMPLEX" and exc.value.details["depth"] == 51
    assert evaluate_expression("(" * 50 + "1" + ")" * 50).value == 1.0
    # Limiti configurabili.
    assert evaluate_expression(nested, max_depth=60).value == 1.0
    with pytest.raises(CalculatorError) as exc:
        evaluate_expression("1+1", max_length=2)
    assert exc.value.code == "CALC_TOO_COMPLEX"
    with pytest.raises(CalculatorError) as exc:
        evaluate_expression("-" * 990 + "1")  # catena unaria troppo profonda per l'analizzatore
    assert exc.value.code == "CALC_TOO_COMPLEX"


def test_result_requires_unit_or_scale_and_rerun():
    result = evaluate_expression("= sqrt(2) ^ 2")
    assert same_result(run_command(result.command), result)
    assert "evaluate_expression(expression='sqrt(2) ^ 2'" in result.command.text
    with pytest.raises(TypeError):
        CalculatorResult(calculator="x", input="1", value=1.0, unit=None, scale=None, library="numpy",
                         command=result.command)


# =============================================================================
# P2 — calcolatrice del tempo (T15–T17)


def test_t15_j2000():
    result = convert_time("2000-01-01T12:00:00", "iso", "TT")
    expected = Time("2000-01-01T12:00:00", format="isot", scale="tt")
    values = result.value
    assert values.jd == 2451545.0 and values.jyear == 2000.0  # definizione di J2000.0
    assert values.byear == np.float64(expected.byear) and values.mjd == np.float64(expected.mjd)
    assert values.iso == "2000-01-01T12:00:00.000000000" and result.scale == "tt" and values.scale == "tt"
    assert values.text.count("(TT)") == 5  # la scala in ogni rappresentazione
    # Da JD, anno giuliano e besseliano: stessa data.
    assert convert_time(2451545.0, "jd", "tt").value.iso == values.iso
    assert convert_time(2000.0, "jyear", "tt").value.jd == 2451545.0
    assert convert_time(float(expected.byear), "byear", "tt").value.byear == np.float64(expected.byear)


def test_t16_mjd_leap_day():
    result = convert_time("2024-02-29T18:00:00", "iso", "utc")
    assert result.value.mjd == np.float64(Time("2024-02-29T18:00:00", format="isot", scale="utc").mjd)
    assert result.value.mjd == 60369.75
    # ISO con spazio o solo data; cambio di scala con astropy.time.
    assert convert_time("2024-02-29 18:00:00", "iso", "utc").value.mjd == 60369.75
    assert convert_time("2024-02-29", "iso", "utc").value.mjd == 60369.0
    tt = convert_time("2024-02-29T18:00:00", "iso", "utc", target_scale="TT")
    assert tt.scale == "tt" and tt.value.jd == np.float64(Time("2024-02-29T18:00:00", scale="utc").tt.jd)
    assert any("UTC → TT" in n for n in tt.notes)
    # Secondo intercalare, data inesistente, formato errato.
    assert convert_time("2016-12-31T23:59:60", "iso", "utc").value.iso == "2016-12-31T23:59:60.000000000"
    for value, fmt in (("2024-02-30T00:00:00", "iso"), ("ieri", "iso"), ("2451545", "jd"), (np.nan, "mjd"),
                       (True, "jd"), (2451545.0, "unix")):
        with pytest.raises(CalculatorError) as exc:
            convert_time(value, fmt, "utc")
        assert exc.value.code == "TIME_INVALID", (value, fmt)


def test_t17_scale_required():
    for scale in (None, "", "local", "GPS"):
        with pytest.raises(CalculatorError) as exc:
            convert_time("2000-01-01T12:00:00", "iso", scale)
        assert exc.value.code == "TIME_SCALE_REQUIRED"
    with pytest.raises(CalculatorError) as exc:
        convert_time("2000-01-01T12:00:00", "iso", "tt", target_scale="local")
    assert exc.value.code == "TIME_SCALE_REQUIRED"
    future = convert_time("2100-01-01T00:00:00", "iso", "utc", target_scale="tt")
    assert any("dubious year" in n for n in future.notes)  # UTC oltre la tabella dei secondi intercalari
    result = convert_time("2024-02-29T18:00:00", "iso", "utc", "tdb")
    again = run_command(result.command)
    assert again.value == result.value and again.scale == result.scale == "tdb"


def test_t17_ut1_bundled_iers_tables(monkeypatch):
    from astropy.utils import iers

    # Nessuna rete: ogni tentativo di aprire una connessione fa fallire il test.
    import socket

    def no_network(*args, **kwargs):
        raise AssertionError("accesso alla rete durante la conversione UT1")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    table_a = iers.IERS_A.open(iers.IERS_A_FILE)
    table_b = iers.IERS_B.open(iers.IERS_B_FILE)
    # Data coperta dall'IERS-A incluso: UT1 ricalcolato con delta_ut1_utc della stessa tabella.
    result = convert_time("2020-01-01T00:00:00", "iso", "utc", "ut1")
    reference = Time("2020-01-01T00:00:00", scale="utc")
    reference.delta_ut1_utc = table_a.ut1_utc(reference)
    assert result.value.jd1 + result.value.jd2 == pytest.approx(reference.ut1.jd1 + reference.ut1.jd2, abs=1e-12)
    assert result.iers.name == "finals2000A.all" and "astropy-iers-data" in result.iers.source
    assert any("finals2000A.all" in n and "Bulletin B" in n and "rete" in n for n in result.notes)
    assert run_command(result.command).value == result.value
    # Prima dell'IERS-A: IERS-B incluso (eopc04).
    old = convert_time("1965-06-01T00:00:00", "iso", "utc", "ut1")
    reference = Time("1965-06-01T00:00:00", scale="utc")
    reference.delta_ut1_utc = table_b.ut1_utc(reference)
    assert old.value.jd1 + old.value.jd2 == pytest.approx(reference.ut1.jd1 + reference.ut1.jd2, abs=1e-12)
    assert old.iers.name == Path(iers.IERS_B_FILE).name
    # Predizione dell'IERS dichiarata come tale; UT1 → UTC.
    end = float(table_a["MJD"][-1].to_value(u.d))
    predicted = convert_time(end - 30, "mjd", "ut1", "utc")
    assert any("predizione" in n for n in predicted.notes)
    # Fuori dalla copertura: errore esplicito, mai estrapolazione.
    for value in (end + 400, 30000.0):
        for scales in (("utc", "ut1"), ("ut1", "tt")):
            with pytest.raises(CalculatorError) as exc:
                convert_time(value, "mjd", *scales)
            assert exc.value.code == "IERS_RANGE" and "finals2000A.all" in exc.value.message
    # Senza UT1 nessuna tabella IERS.
    assert convert_time("2020-01-01T00:00:00", "iso", "utc", "tt").iers is None


def test_t17_ut1_updated_table_on_request(service, cache):
    from astropy.utils import iers

    payload = Path(iers.IERS_A_FILE).read_bytes()
    service.routes["/finals2000A.all"] = lambda request: (200, "text/plain", payload)
    with pytest.raises(CalculatorError) as exc:  # nessun aggiornamento chiesto: nessuna tabella aggiornata
        convert_time("2020-01-01T00:00:00", "iso", "utc", "ut1", iers_table="updated", cache=cache)
    assert exc.value.code == "IERS_TABLE_MISSING"
    info = update_iers_table(cache=cache, url=f"{service.url}/finals2000A.all")
    assert service.hits("/finals2000A.all") == 1 and "scaricato da" in info.source
    updated = convert_time("2020-01-01T00:00:00", "iso", "utc", "ut1", iers_table="updated", cache=cache)
    bundled = convert_time("2020-01-01T00:00:00", "iso", "utc", "ut1")
    assert updated.value == bundled.value and "scaricato da" in updated.iers.source
    assert ("iers_table", "updated") in updated.command.arguments
    assert service.hits("/finals2000A.all") == 1  # la conversione non usa la rete
    service.routes["/bad"] = lambda request: (200, "text/plain", b"non una tabella")
    with pytest.raises(CalculatorError) as exc:
        update_iers_table(cache=cache, url=f"{service.url}/bad")
    assert exc.value.code == "IERS_TABLE_INVALID"
    with pytest.raises(CalculatorError) as exc:
        update_iers_table(cache=cache, url="http://127.0.0.1:9/finals2000A.all")
    assert exc.value.code == "NET_TIMEOUT"


def test_t17_ut1_update_falls_back_to_the_mirror(service, cache, monkeypatch):
    """Decisione del 2026-10-25: indirizzo ufficiale muto → mirror dichiarato nella fonte; esplicito → nessun ripiego."""
    from astropy.utils import iers

    payload = Path(iers.IERS_A_FILE).read_bytes()
    service.routes["/official"] = lambda request: (400, "text/html", b"Request Rejected")
    service.routes["/mirror"] = lambda request: (200, "text/plain", payload)
    monkeypatch.setattr(iers, "IERS_A_URL", f"{service.url}/official")
    monkeypatch.setattr(iers, "IERS_A_URL_MIRROR", f"{service.url}/mirror")
    info = update_iers_table(cache=cache)
    assert f"scaricato da {service.url}/mirror" in info.source and "indirizzo ufficiale non ha risposto" in info.source
    assert service.hits("/official") >= 1 and service.hits("/mirror") == 1
    with pytest.raises(CalculatorError):  # url esplicito: nessun ripiego sul mirror
        update_iers_table(cache=cache, url=f"{service.url}/official")
    assert service.hits("/mirror") == 1
    service.routes["/mirror"] = lambda request: (503, "text/plain", b"")  # entrambi muti: errore del mirror
    with pytest.raises(CalculatorError) as exc:
        update_iers_table(cache=cache)
    assert f"{service.url}/mirror" in str(exc.value.params)


@pytest.mark.network
def test_t17_ut1_update_from_iers_network(cache):
    info = update_iers_table(cache=cache)
    assert info.name == "finals2000A.all" and info.mjd_end > 61000
    result = convert_time("2020-01-01T00:00:00", "iso", "utc", "ut1", iers_table="updated", cache=cache)
    assert result.iers == info or "scaricato da" in result.iers.source


# =============================================================================
# P3 — convertitore di unità (T6–T9)


def test_t6_length():
    result = convert_units(0.1, "m", "nm")
    assert result.value == (0.1 * u.m).to_value(u.nm) and abs(result.value - 1e8) < 1e-6
    assert result.unit == u.nm and any("FITS" in n for n in result.notes)
    # Composte, prefissi, espressioni e formato VOUnit dichiarato.
    assert convert_units(1, "km/s", "m/s").value == 1000.0
    assert convert_units(2, "mHz", "Hz").value == (2 * u.mHz).to_value(u.Hz)
    assert convert_units("3*8", "km", "m").value == 24000.0
    vo = convert_units(1, "au", "km")
    assert vo.value == (1 * u.AU).to_value(u.km) and any("VOUnit" in n for n in vo.notes)


def test_t7_julian_years():
    result = convert_units(2, "a", "d")
    assert result.value == 730.5 and result.value == (2 * u.yr).to_value(u.d)
    assert convert_units(2, "yr", "d").value == 730.5


def test_t8_sexagesimal_angle():
    result = convert_units("10:10:08", None, "deg", sexagesimal="degrees")
    expected = Angle("10:10:08", unit=u.deg).deg
    assert result.value == expected and abs(result.value - (10 + 10 / 60 + 8 / 3600)) < 1e-13
    hours = convert_units("12:30:15.5", None, "deg", sexagesimal="hours")
    assert hours.value == Angle("12:30:15.5", unit=u.hourangle).deg
    assert convert_units("-05:06:07", None, "arcsec", sexagesimal="degrees").value \
        == Angle("-05:06:07", unit=u.deg).to_value(u.arcsec)
    with pytest.raises(CalculatorError) as exc:
        convert_units("10:10:08", None, "deg")
    assert exc.value.code == "UNIT_SEXAGESIMAL_UNIT_REQUIRED"
    # Date con la calcolatrice del tempo (P2).
    date = convert_units("2024-02-29T18:00:00", None, "mjd", scale="utc")
    assert date.value == 60369.75 and date.scale == "utc" and date.unit is None
    with pytest.raises(CalculatorError) as exc:
        convert_units("2024-02-29T18:00:00", None, "mjd")
    assert exc.value.code == "TIME_SCALE_REQUIRED"


def test_t9_incompatible_and_equivalencies():
    with pytest.raises(CalculatorError) as exc:
        convert_units(1, "m", "s")
    assert exc.value.code == "UNIT_INCOMPATIBLE" and exc.value.details["physical_types"] == ("length", "time")
    # Equivalenze solo su richiesta esplicita (D18-3).
    with pytest.raises(CalculatorError) as exc:
        convert_units(500, "nm", "Hz")
    assert exc.value.code == "UNIT_INCOMPATIBLE"
    spectral = convert_units(500, "nm", "Hz", "spectral")
    assert spectral.value == (500 * u.nm).to_value(u.Hz, equivalencies=u.spectral())
    assert any("spectral" in n for n in spectral.notes)
    assert convert_units(0, "Celsius", "K", "temperature").value == 273.15
    assert convert_units(10, "mas", "pc", "parallax").value == (10 * u.mas).to_value(u.pc, equivalencies=u.parallax())
    rest = 115.27 * u.GHz
    assert convert_units(1, "km/s", "GHz", "doppler_radio", reference=rest).value \
        == (1 * u.km / u.s).to_value(u.GHz, equivalencies=u.doppler_radio(rest))
    with pytest.raises(CalculatorError) as exc:
        convert_units(1, "km/s", "GHz", "doppler_optical")
    assert exc.value.code == "UNIT_REFERENCE_REQUIRED"
    with pytest.raises(CalculatorError) as exc:
        convert_units(1, "m", "nm", "magic")
    assert exc.value.code == "UNIT_EQUIVALENCY_UNKNOWN"
    # Unità fuori dai formati standard, con le unità simili.
    with pytest.raises(CalculatorError) as exc:
        convert_units(1, "arcsecs", "deg")
    assert exc.value.code == "UNIT_UNKNOWN" and "arcsec" in exc.value.details["similar"]
    # Magnitudini ↔ flussi: solo nel modulo 20 (D18-4); mag ↔ mmag ammessa.
    with pytest.raises(CalculatorError) as exc:
        convert_units(10, "mag", "Jy")
    assert exc.value.code == "UNIT_ZERO_POINT_REQUIRED"
    assert convert_units(1, "mag", "mmag").value == 1000.0
    # Nessun valore non finito.
    with pytest.raises(CalculatorError) as exc:
        convert_units(0, "Hz", "m", "spectral")
    assert exc.value.code == "CALC_DOMAIN_ERROR"
    result = convert_units(500, "nm", "Hz", "spectral")
    assert same_result(run_command(result.command), result)


# =============================================================================
# P4 — calcolatrice dei pixel (T10–T12, D18-6)


def scaled_fits(tmp_path, raw, **keys):
    """File con i valori grezzi dati e BZERO/BSCALE/BLANK aggiunti all'intestazione dopo la scrittura."""
    path = tmp_path / "scaled.fits"
    fits.PrimaryHDU(raw).writeto(path)
    for key, value in keys.items():
        fits.setval(path, key, value=value)
    return path


def test_t10_raw_to_physical():
    result = convert_pixel_value(raw=-32768, bzero=32768, bscale=1)
    assert result.value.physical == 0.0 and result.value.raw == -32768.0
    assert result.unit == "non dichiarata"
    back = convert_pixel_value(physical=0.0, bzero=32768, bscale=1, bunit="adu")
    assert back.value.raw == -32768.0 and back.unit == "adu"
    general = convert_pixel_value(raw=100, bzero=10.0, bscale=0.5)
    assert general.value.physical == 10.0 + 0.5 * 100
    assert any("non intero" in n for n in convert_pixel_value(physical=10.25, bzero=10.0, bscale=0.5).notes)
    with pytest.raises(CalculatorError) as exc:
        convert_pixel_value(physical=5.0, bzero=1.0, bscale=0)
    assert exc.value.code == "PIXEL_BSCALE_ZERO"
    with pytest.raises(TypeError):
        convert_pixel_value(raw=1)  # bzero e bscale non si assumono a mano
    with pytest.raises(TypeError):
        convert_pixel_value(raw=1, physical=2, bzero=0, bscale=1)
    assert same_result(run_command(general.command), general)


def test_t11_blank(tmp_path):
    with pytest.raises(CalculatorError) as exc:
        convert_pixel_value(raw=-5, bzero=10.0, bscale=0.5, blank=-5)
    assert exc.value.code == "PIXEL_BLANK"
    raw = np.array([[-32768, 0, 7], [100, -5, 3]], dtype=np.int16)
    image = load_image(str(scaled_fits(tmp_path, raw, BZERO=10.0, BSCALE=0.5, BLANK=-5)))
    with pytest.raises(CalculatorError) as exc:
        convert_pixel_value(image=image, position=PixelPosition(x=np.float64(1), y=np.float64(1), convention="numpy"))
    assert exc.value.code == "PIXEL_BLANK"


def test_d18_6_raw_from_file(tmp_path):
    raw = np.array([[-32768, 0, 7], [100, -5, 3]], dtype=np.int16)
    image = load_image(str(scaled_fits(tmp_path, raw, BZERO=10.0, BSCALE=0.5, BLANK=-5)))
    with fits.open(image.origin, do_not_scale_image_data=True) as hdul:
        stored = hdul[0].data
        assert stored.dtype.kind == "i"
    for x, y in ((0, 0), (2, 0), (0, 1)):
        result = convert_pixel_value(image=image, position=PixelPosition(x=np.float64(x + 1), y=np.float64(y + 1),
                                                                         convention="fits"))
        assert result.value.raw == stored[y, x] and result.value.physical == 10.0 + 0.5 * float(stored[y, x])
        assert result.value.fits_position == (x + 1, y + 1)
    # Immagine derivata: i pixel non sono più quelli del file.
    small = cutout(image, PixelPosition(x=np.float64(1), y=np.float64(0.5), convention="numpy"), (2, 2))
    with pytest.raises(CalculatorError) as exc:
        convert_pixel_value(image=small, position=PixelPosition(x=np.float64(0), y=np.float64(0), convention="numpy"))
    assert exc.value.code == "PIXEL_RAW_UNAVAILABLE"


def test_t12_color_index(tmp_path):
    yy, xx = np.mgrid[0:20, 0:30]
    data = (xx * 7.0 + yy * 3.0).astype(np.float32)
    path = tmp_path / "img.fits"
    fits.PrimaryHDU(data).writeto(path)
    image = load_image(str(path))
    for stretch, palette in (("linear", "gray"), ("sqrt", "viridis"), ("histeq", "gray"), ("log", "inferno")):
        settings = DisplaySettings(vmin=10.0, vmax=180.0, gamma=1.3, stretch=stretch, palette=palette)
        plane = set_display(image, settings.vmin, settings.vmax, settings.gamma, settings.palette, settings.stretch)
        colormap = matplotlib.colormaps[palette]
        for x, y in ((0, 0), (5, 7), (17, 12), (29, 19)):
            result = convert_pixel_value(image=image, display=settings,
                                         position=PixelPosition(x=np.float64(x), y=np.float64(y), convention="numpy"))
            index = result.value.color_index
            assert 0 <= index <= 255
            # Stesso colore che set_display del modulo 11 ha dato al pixel.
            assert np.array_equal(colormap(index, bytes=True), plane.rgba[y, x]), (stretch, x, y)
    with pytest.raises(CalculatorError) as exc:
        convert_pixel_value(raw=1, bzero=0, bscale=1, display=DisplaySettings(0.0, 1.0, stretch="histeq"))
    assert exc.value.code == "OPERATION_UNSUPPORTED"
    manual = convert_pixel_value(raw=50, bzero=0, bscale=1, display=DisplaySettings(0.0, 100.0))
    assert manual.value.color_index == 128  # 0,5 · 256 nella palette


# =============================================================================
# P5 — calcolatrice delle coordinate (T13, T14, T18)


def test_t13_icrs_to_galactic():
    start = SkyFrame.from_lonlat(83.6331 * u.deg, 22.0145 * u.deg, "icrs", epoch=Time(2000.0, format="jyear",
                                                                                       scale="tt"))
    result = calculate_coordinates(start, [CoordinateTarget("galactic"), CoordinateTarget("fk5", equinox="J2000"),
                                           CoordinateTarget("icrs")])
    galactic, fk5, icrs = result.value.representations
    expected = convert_coordinates(start, "galactic")
    assert galactic.lon_deg == np.float64(expected.lon.to_value(u.deg))
    assert galactic.lat_deg == np.float64(expected.lat.to_value(u.deg))
    fk5_expected = convert_coordinates(start, "fk5", equinox="J2000")
    assert (fk5.lon_deg, fk5.lat_deg) == (fk5_expected.lon.to_value(u.deg), fk5_expected.lat.to_value(u.deg))
    assert icrs.lon_in_hours and not galactic.lon_in_hours
    assert icrs.lon_sexagesimal == Angle(83.6331 * u.deg).to_string(unit=u.hourangle, sep=":", precision=5, pad=True)
    assert icrs.lat_sexagesimal.startswith("+22:00:52")
    assert result.unit == u.deg and "J2000.000" in icrs.text
    # Coordinate scritte in sessagesimale, ore dichiarate; equinozio storico.
    written = CoordinateInput("05:34:31.94", "+22:00:52.2", "icrs", lon_sexagesimal="hours")
    from_text = calculate_coordinates(written, [CoordinateTarget("fk4", equinox="B1875", obstime="B1875")])
    direct = convert_coordinates(SkyFrame.from_lonlat(Angle("05:34:31.94", unit=u.hourangle), Angle("+22:00:52.2",
                                                      unit=u.deg), "icrs"), "fk4", equinox="B1875", obstime="B1875")
    first = from_text.value.representations[0]
    assert (first.lon_deg, first.lat_deg) == (direct.lon.to_value(u.deg), direct.lat.to_value(u.deg))
    with pytest.raises(CalculatorError) as exc:
        calculate_coordinates(CoordinateInput("05:34:31.94", 22.0, "icrs"), [CoordinateTarget("icrs")])
    assert exc.value.code == "UNIT_SEXAGESIMAL_UNIT_REQUIRED"
    with pytest.raises(CalculatorError) as exc:
        calculate_coordinates(start, [CoordinateTarget("fk5")])  # equinozio non assunto
    assert exc.value.code == "EPOCH_REQUIRED"
    with pytest.raises(CalculatorError) as exc:
        calculate_coordinates(CoordinateInput(10.0, 95.0, "icrs"), [CoordinateTarget("icrs")])
    assert exc.value.code == "COORD_OUT_OF_RANGE"


def test_t13_offsets_and_inverse():
    start = SkyFrame.from_lonlat(150.0 * u.deg, 2.2 * u.deg, "icrs")
    inverse = calculate_coordinates(start, [CoordinateTarget("icrs")], direction=(30 * u.arcmin, 135 * u.deg))
    expected = offset_position(start, 30 * u.arcmin, 135 * u.deg).position
    assert inverse.value.base.coord.separation(expected.coord).deg == 0.0
    moved = calculate_coordinates(start, [CoordinateTarget("icrs")], offsets=(1 * u.arcmin, -2 * u.arcmin),
                                  to_point=start)
    back = moved.value.offsets_to
    d_lon, d_lat = moved.value.base.coord.spherical_offsets_to(start.coord)
    assert back.d_lon == d_lon and back.d_lat == d_lat
    assert moved.value.base.coord.separation(start.coord.spherical_offsets_by(1 * u.arcmin, -2 * u.arcmin)).deg < 1e-12


def test_t14_missing_epoch():
    motion = ProperMotion(pm_ra_cosdec=500 * u.mas / u.yr, pm_dec=-300 * u.mas / u.yr, parallax=20 * u.mas)
    no_epoch = SkyFrame.from_lonlat(150.0 * u.deg, 2.0 * u.deg, "icrs")
    with pytest.raises(CalculatorError) as exc:
        calculate_coordinates(no_epoch, [CoordinateTarget("icrs")], epoch=2016.0, motion=motion)
    assert exc.value.code == "EPOCH_REQUIRED"
    with pytest.raises(CalculatorError) as exc:  # senza moto proprio: nessun moto nullo assunto
        calculate_coordinates(dataclasses.replace(no_epoch, epoch=Time(2000.0, format="jyear", scale="tt")),
                              [CoordinateTarget("icrs")], epoch=2016.0)
    assert exc.value.code == "EPOCH_REQUIRED"
    start = dataclasses.replace(no_epoch, epoch=Time(2000.0, format="jyear", scale="tt"))
    result = calculate_coordinates(start, [CoordinateTarget("icrs")], epoch=2016.0, motion=motion)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        expected = SkyCoord(ra=150.0 * u.deg, dec=2.0 * u.deg, pm_ra_cosdec=500 * u.mas / u.yr,
                            pm_dec=-300 * u.mas / u.yr, distance=Distance(parallax=20 * u.mas),
                            obstime=Time(2000.0, format="jyear", scale="tt"),
                            ).apply_space_motion(new_obstime=Time(2016.0, format="jyear", scale="tt"))
    assert result.value.base.coord.separation(SkyCoord(expected.ra, expected.dec)).to_value(u.mas) < 1e-6
    assert result.value.base.epoch.jyear == 2016.0


def catalog_row(tmp_path):
    t = Table()
    t["RA"] = np.array([150.0]) * u.deg
    t["DE"] = np.array([2.0]) * u.deg
    t["RA"].meta["ucd"] = "pos.eq.ra;meta.main"
    t["DE"].meta["ucd"] = "pos.eq.dec;meta.main"
    t["ep"] = np.array([2000.0]) * u.yr
    t["ep"].meta["ucd"] = "meta.ref;time.epoch"
    t["pmRA"] = np.array([500.0]) * u.mas / u.yr
    t["pmDE"] = np.array([-300.0]) * u.mas / u.yr
    t["plx"] = np.array([20.0]) * u.mas
    path = tmp_path / "cat.csv"
    path.write_text("x,y\n1,2\n")
    return confirm_position_columns(dataclasses.replace(read_table(path), table=t), "RA", "DE", "icrs")


def test_t14_catalog_row(tmp_path):
    table = catalog_row(tmp_path)
    source = CatalogSource(table, 0, pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True, parallax="plx")
    result = calculate_coordinates(source, [CoordinateTarget("icrs")], epoch=2016.0)
    assert result.value.base.epoch.jyear == 2016.0 and any("propagata" in n for n in result.notes)
    with pytest.raises(CalculatorError) as exc:
        calculate_coordinates(CatalogSource(table, 0), [CoordinateTarget("icrs")], epoch=2016.0)
    assert exc.value.code == "EPOCH_REQUIRED"


def test_t18_rerun_registered_commands(tmp_path):
    """T18: finché il 24 non esiste, si riesegue il comando registrato nel CalculatorResult (T1–T16)."""
    raw = np.array([[-32768, 0, 7], [100, -5, 3]], dtype=np.int16)
    image = load_image(str(scaled_fits(tmp_path, raw, BZERO=10.0, BSCALE=0.5, BLANK=-5)))
    start = SkyFrame.from_lonlat(83.6331 * u.deg, 22.0145 * u.deg, "icrs")
    results = [
        evaluate_expression("3*8"), evaluate_expression("sind(30)"), evaluate_expression("skydist(10, 20, 10.5, 20.5)"),
        convert_units(0.1, "m", "nm"), convert_units(2, "a", "d"),
        convert_units("10:10:08", None, "deg", sexagesimal="degrees"),
        convert_pixel_value(raw=-32768, bzero=32768, bscale=1),
        convert_pixel_value(image=image, position=PixelPosition(x=np.float64(1), y=np.float64(1), convention="fits"),
                            display=DisplaySettings(0.0, 100.0)),
        calculate_coordinates(start, [CoordinateTarget("galactic")]),
        convert_time("2000-01-01T12:00:00", "iso", "TT"), convert_time("2024-02-29T18:00:00", "iso", "utc"),
    ]
    for result in results:
        again = run_command(result.command)
        assert (again.input, again.unit, again.scale, again.calculator) == \
            (result.input, result.unit, result.scale, result.calculator), result.command.text
        assert again.value == result.value or np.array_equal(again.value, result.value), result.command.text


# =============================================================================
# Adattatore del formato del 05 (D05-4, decisa il 2026-10-17; T18 nel formato del 05, T9 del 05)

import json  # noqa: E402


def through_05(result: CalculatorResult, layers=None) -> CalculatorResult:
    """Comando del risultato nel formato del 05, passato per il testo JSON e rieseguito con l'adattatore."""
    command = json.loads(json.dumps(result.command_05(layers)))
    assert command["name"].startswith("calc.") and command["version"] == 1
    return run_command(command, layers)


def assert_same(again: CalculatorResult, result: CalculatorResult) -> None:
    assert (again.input, again.unit, again.scale, again.calculator) == \
        (result.input, result.unit, result.scale, result.calculator), result.command.text
    if isinstance(result.value, CoordinatesOutput):  # i rapporti del 17 hanno l'istante della misura
        a, b = again.value, result.value
        assert a.base == b.base and a.representations == b.representations, result.command.text
        assert (a.offsets_to is None) == (b.offsets_to is None)
        if a.offsets_to is not None:
            assert (a.offsets_to.d_lon, a.offsets_to.d_lat) == (b.offsets_to.d_lon, b.offsets_to.d_lat)
        return
    assert again.value == result.value or np.array_equal(again.value, result.value), result.command.text


def test_t18_rerun_in_05_format(tmp_path):
    raw = np.array([[-32768, 0, 7], [100, -5, 3]], dtype=np.int16)
    image = load_image(str(scaled_fits(tmp_path, raw, BZERO=10.0, BSCALE=0.5, BLANK=-5)))
    start = SkyFrame.from_lonlat(83.6331 * u.deg, 22.0145 * u.deg, "icrs")
    dated = SkyFrame.from_lonlat(150.0 * u.deg, 2.0 * u.deg, "icrs", epoch=Time(2000.0, format="jyear", scale="tt"))
    motion = ProperMotion(pm_ra_cosdec=500 * u.mas / u.yr, pm_dec=-300 * u.mas / u.yr, parallax=20 * u.mas)
    table = catalog_row(tmp_path)
    layers = {"L1": image, "L2": table}
    results = [
        evaluate_expression("3*8"), evaluate_expression("sind(30)"), evaluate_expression("skydist(10, 20, 10.5, 20.5)"),
        evaluate_expression("skydist(10:00:00, 20, 10:30:00, 20.5)", colon_units=["hours", "hours"]),
        convert_units(0.1, "m", "nm"), convert_units(2, "a", "d"),
        convert_units("10:10:08", None, "deg", sexagesimal="degrees"),
        convert_units(500, "nm", "Hz", "spectral"),
        convert_units(1.0, "km/s", "MHz", "doppler_radio", reference=1420.405751768 * u.MHz),
        convert_units("2024-02-29T18:00:00", None, "mjd", scale="utc"),
        convert_pixel_value(raw=-32768, bzero=32768, bscale=1),
        convert_pixel_value(physical=12.5, bzero=10.0, bscale=0.5, blank=-5, bunit="adu"),
        convert_pixel_value(image=image, position=PixelPosition(x=np.float64(1), y=np.float64(1), convention="fits"),
                            display=DisplaySettings(0.0, 100.0)),
        calculate_coordinates(start, [CoordinateTarget("galactic")]),
        calculate_coordinates(start, [CoordinateTarget("fk5", equinox="J2000"),
                                      CoordinateTarget("fk4", equinox="B1875", obstime="B1875")]),
        calculate_coordinates(CoordinateInput("05:34:31.94", "+22:00:52.2", "icrs", lon_sexagesimal="hours"),
                              [CoordinateTarget("icrs")]),
        calculate_coordinates(dated, [CoordinateTarget("icrs")], epoch=2016.0, motion=motion),
        calculate_coordinates(start, [CoordinateTarget("icrs")], direction=(30 * u.arcmin, 135 * u.deg)),
        calculate_coordinates(start, [CoordinateTarget("icrs")], offsets=(1 * u.arcmin, -2 * u.arcmin), to_point=start),
        calculate_coordinates(CatalogSource(table, 0, pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True,
                                            parallax="plx"), [CoordinateTarget("icrs")], epoch=2016.0),
        convert_time("2000-01-01T12:00:00", "iso", "TT"), convert_time("2024-02-29T18:00:00", "iso", "utc"),
        convert_time(2451545.0, "jd", "tt", "tdb"),
    ]
    for result in results:
        assert_same(through_05(result, layers), result)
    # Il formato del 05 della posizione in pixel è sempre numpy (DC7).
    click = results[12].command_05(layers)["parameters"]
    assert click["position"] == {"x": 0.0, "y": 0.0, "convention": "numpy"} and click["image"] == "L1"
    assert results[0].command_05()["parameters"] == {"expression": "3*8", "max_length": 1000, "max_depth": 50,
                                                     "colon_units": None, "colon_units_each": None}


def test_adapter_rejects_malformed_05_commands():
    good = evaluate_expression("1+1").command_05()
    for broken in (
        {**good, "name": "calc.unknown"},
        {**good, "version": 2},
        {**good, "parameters": {**good["parameters"], "extra": 1}},
        {**good, "parameters": {**good["parameters"], "max_length": "1000"}},
        {"name": "calc.convert_units", "version": 1, "parameters": {"value": 1.0, "value_text": "2", "from_unit": "m",
                                                                     "to_unit": "km"}},
        {"name": "calc.convert_units", "version": 1, "parameters": {"value": 1.0, "from_unit": "m", "to_unit": "nm",
                                                                     "reference": {"value": 1.0}}},
        {"name": "calc.convert_pixel_value", "version": 1, "parameters": {"image": "L9", "position": {
            "x": 0.0, "y": 0.0, "convention": "numpy"}}},
        {"name": "calc.calculate_coordinates", "version": 1, "parameters": {
            "position": {"lon": {"value": 1.0, "unit": "deg"}, "lat": {"value": 1.0, "unit": "deg"}, "frame": "icrs"},
            "targets": "icrs"}},
    ):
        with pytest.raises(CalculatorError) as exc:
            run_command(broken, {})
        assert exc.value.code == "CALC_COMMAND_INVALID", broken
    # Gli errori delle calcolatrici passano invariati anche dall'adattatore.
    with pytest.raises(CalculatorError) as exc:
        run_command({"name": "calc.convert_units", "version": 1,
                     "parameters": {"value": 1.0, "from_unit": "m", "to_unit": "s"}})
    assert exc.value.code == "UNIT_INCOMPATIBLE"
