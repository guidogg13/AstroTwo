"""Test del modulo 18 (``mdfiles/18-core-calcolatrici.md`` §12).

I valori attesi si ricalcolano nel test con la libreria indicata (``numpy``, ``astropy``), mai copiati da
altri programmi (regola d'oro n. 8).
"""

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord

from astrotwo.core.calculators import (
    CalculatorError,
    CalculatorResult,
    evaluate_expression,
    run_command,
)
from astrotwo.core.coordinates_wcs import SkyFrame
from astrotwo.core.measures import angular_distance


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
    # Sessagesimali: fermi su D18-7.
    with pytest.raises(CalculatorError) as exc:
        evaluate_expression("skydist(10:20:30, 20, 10, 20)")
    assert exc.value.code == "CALC_SYNTAX_ERROR" and "D18-7" in exc.value.message


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
