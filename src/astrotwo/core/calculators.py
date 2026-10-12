"""Calcolatrici: algebrica, unità, pixel, coordinate e tempo.

Specifica: ``mdfiles/18-core-calcolatrici.md`` (stato ``approvato``).

Il modulo si scrive in 5 parti (decisione del proprietario del 2026-10-12):
P1 ``CalculatorResult`` ed ``evaluate_expression``, P2 ``convert_time``,
P3 ``convert_units``, P4 ``convert_pixel_value``, P5 ``calculate_coordinates``.

Regole applicate in tutto il modulo:

- ogni numero viene da una libreria dichiarata nel risultato (``numpy`` con la
  tabella delle funzioni del 13, ``astropy``) o dalle funzioni dei moduli 10,
  11, 13 e 17, mai riscritte qui; l'IA non calcola mai (regola d'oro n. 1);
- le espressioni si analizzano con ``ast`` a elenco chiuso e non si eseguono
  mai come codice (D18-1);
- ogni risultato ha unità o scala e il comando con cui si riesegue (regola
  d'oro n. 6); nessun valore non finito restituito in silenzio.
"""

from __future__ import annotations

import ast
import math
import re
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime

import astropy
import astropy.units as u
import numpy as np
from astropy.time import Time
from astropy.utils import iers

from astrotwo.core.catalogs import CONSTANTS, FUNCTIONS
from astrotwo.core.coordinates_wcs import CoordinatesWcsError, SkyFrame
from astrotwo.core.measures import MeasuresError, angular_distance

__all__ = [
    "MAX_EXPRESSION_LENGTH",
    "MAX_NESTING_DEPTH",
    "CalculatorError",
    "CalculatorCommand",
    "CalculatorResult",
    "run_command",
    "evaluate_expression",
    "TIME_FORMATS",
    "TIME_SCALES",
    "TimeRepresentations",
    "convert_time",
]

#: Limiti delle espressioni (D18-5, decisa il 2026-10-12), configurabili per chiamata.
MAX_EXPRESSION_LENGTH = 1000
MAX_NESTING_DEPTH = 50


# --------------------------------------------------------------------------
# Errori, comandi e risultati
# --------------------------------------------------------------------------


class CalculatorError(Exception):
    """Errore del modulo 18 con identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


def _forwarded(exc: CoordinatesWcsError | MeasuresError, what: str) -> CalculatorError:
    """Errore dei moduli 10/13/17 inoltrato con lo stesso identificatore (§10)."""
    return CalculatorError(exc.code, f"{what}: {exc.message}")


@dataclass(frozen=True)
class CalculatorCommand:
    """Comando registrato e rieseguibile (regola d'oro n. 6): funzione e argomenti come interpretati.

    Il formato del registro è del modulo 24; finché non esiste, ``run_command`` riesegue il comando.
    """

    function: str
    arguments: tuple[tuple[str, object], ...]

    @property
    def text(self) -> str:
        return f"{self.function}({', '.join(f'{name}={value!r}' for name, value in self.arguments)})"


@dataclass(frozen=True, eq=False)
class CalculatorResult:
    """Risultato di una calcolatrice: mai senza unità o scala (§7)."""

    calculator: str
    input: str  # input ripetuto così come è stato interpretato
    value: object
    unit: u.UnitBase | str | None  # unità di astropy, o "non dichiarata" quando la fonte non la dichiara
    scale: str | None  # scala di tempo (calcolatrice del tempo)
    library: str  # libreria e versione che hanno eseguito il calcolo
    command: CalculatorCommand
    notes: tuple[str, ...] = ()
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.unit is None and self.scale is None:
            raise TypeError("CalculatorResult senza unità né scala: errore di programmazione (§9)")


_COMMANDS: dict[str, object] = {}


def run_command(command: CalculatorCommand) -> CalculatorResult:
    """Riesegue un comando registrato (T18): solo le funzioni delle calcolatrici, nessun altro codice."""
    if not isinstance(command, CalculatorCommand) or command.function not in _COMMANDS:
        raise ValueError(f"comando non riconosciuto: {command!r}")
    return _COMMANDS[command.function](**dict(command.arguments))


def _registered(function):
    _COMMANDS[function.__name__] = function
    return function


# --------------------------------------------------------------------------
# P1 — calcolatrice algebrica (D18-1, D18-5)
# --------------------------------------------------------------------------

_BINARY = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Mod: "%", ast.Pow: "^"}
_NUMBER = re.compile(r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_FP_ERRORS = {"divide": "divide", "overflow": "overflow", "invalid": "invalid"}
#: Funzioni che restituiscono angoli: nel risultato restano numeri puri (§3, scelta minore 4 di P1).
_ANGLE_FUNCTIONS = ("asin", "acos", "atan", "atan2", "asind", "acosd", "atand", "atan2d", "rad2deg", "deg2rad",
                    "skydist")


def _syntax(message: str, position: int, expression: str) -> CalculatorError:
    return CalculatorError("CALC_SYNTAX_ERROR", f"{message} (carattere {position}): {expression!r}",
                           position=position)


def _prepare(expression: str) -> tuple[str, str, list[int]]:
    """Toglie un ``=`` iniziale o finale e traduce ``^`` in ``**``, con la mappa delle posizioni."""
    start = len(expression) - len(expression.lstrip())
    text = expression.strip()
    if text.startswith("="):
        text, start = text[1:], start + 1
    elif text.endswith("="):
        text = text[:-1]
    lead = len(text) - len(text.lstrip())
    text, start = text.strip(), start + lead
    out, origin = [], []
    for i, char in enumerate(text):
        position = start + i
        if text.startswith("**", i):
            raise _syntax("'**' non previsto: la potenza si scrive '^'", position, expression)
        if char == ":":
            raise _syntax("angoli sessagesimali nelle espressioni non ancora previsti (D18-7, da decidere): "
                          "usare gradi decimali", position, expression)
        if char == "^":
            out.append("**")
            origin.extend([position, position])
        else:
            out.append(char)
            origin.append(position)
    return text, "".join(out), origin


def _nesting_depth(text: str) -> int:
    depth = deepest = 0
    for char in text:
        if char == "(":
            depth += 1
            deepest = max(deepest, depth)
        elif char == ")":
            depth -= 1
    return deepest


class _Evaluator:
    """Validazione completa dell'albero (elenco chiuso) e valutazione in ``float64``."""

    def __init__(self, expression: str, text: str, origin: list[int]) -> None:
        self.expression, self.text, self.origin = expression, text, origin
        self.used: set[str] = set()

    def position(self, node) -> int:
        offset = getattr(node, "col_offset", 0)
        return self.origin[offset] if offset < len(self.origin) else len(self.expression)

    def unknown(self, message: str, node) -> CalculatorError:
        return CalculatorError("CALC_UNKNOWN_FUNCTION", f"{message} (carattere {self.position(node)}): "
                               f"{self.expression!r}; nulla è stato eseguito", position=self.position(node))

    def check(self, node) -> None:
        if isinstance(node, ast.Expression):
            return self.check(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            self.check(node.left)
            return self.check(node.right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return self.check(node.operand)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            segment = ast.get_source_segment(self.text, node) or ""
            if not _NUMBER.fullmatch(segment):
                raise _syntax(f"numero {segment!r} non previsto: solo notazione decimale o esponenziale",
                              self.position(node), self.expression)
            return None
        if isinstance(node, ast.Constant) and (node.value is None or isinstance(node.value, bool)):
            raise self.unknown(f"nome {node.value!r} non previsto (costanti: {', '.join(CONSTANTS)})", node)
        if isinstance(node, ast.Name):
            if node.id in CONSTANTS:
                return None
            raise self.unknown(f"nome {node.id!r} non previsto (costanti: {', '.join(CONSTANTS)})", node)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
                name = node.func.id if isinstance(node.func, ast.Name) else ast.get_source_segment(self.text, node.func)
                raise self.unknown(f"funzione {name!r} non prevista dalla grammatica", node)
            if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
                raise _syntax(f"{node.func.id}: solo argomenti posizionali", self.position(node), self.expression)
            arity = FUNCTIONS[node.func.id][0]
            if (arity is None and len(node.args) < 2) or (arity is not None and len(node.args) != arity):
                expected = "almeno 2" if arity is None else str(arity)
                raise _syntax(f"{node.func.id}: servono {expected} argomenti, non {len(node.args)}",
                              self.position(node), self.expression)
            for arg in node.args:
                self.check(arg)
            return None
        if isinstance(node, (ast.Attribute, ast.Subscript)):
            raise self.unknown(f"costrutto {type(node).__name__} non previsto", node)
        raise _syntax(f"costrutto {type(node).__name__} non previsto", self.position(node), self.expression)

    def fail_fp(self, kind: str, what: str, node, *, operator: bool) -> CalculatorError:
        position = self.position(node)
        if kind == "overflow":
            return CalculatorError("CALC_OVERFLOW", f"{what}: risultato oltre i limiti di float64 (carattere "
                                   f"{position})", position=position)
        if kind == "divide" and operator:
            return CalculatorError("CALC_DIVISION_BY_ZERO", f"{what}: divisione per zero (carattere {position})",
                                   position=position)
        return CalculatorError("CALC_DOMAIN_ERROR", f"{what}: argomento fuori dominio (carattere {position}); "
                               "nessun NaN restituito", position=position)

    def apply(self, function, args, what: str, node, *, operator: bool) -> np.float64:
        try:
            with np.errstate(divide="raise", over="raise", invalid="raise", under="ignore"):
                result = np.float64(function(*args))
        except FloatingPointError as exc:
            kind = next((k for k in _FP_ERRORS if k in str(exc)), "invalid")
            raise self.fail_fp(kind, what, node, operator=operator) from exc
        if not np.isfinite(result):
            raise self.fail_fp("overflow" if np.isinf(result) else "invalid", what, node, operator=operator)
        return result

    def evaluate(self, node) -> np.float64:
        if isinstance(node, ast.Expression):
            return self.evaluate(node.body)
        if isinstance(node, ast.Constant):
            try:
                value = np.float64(float(node.value))
            except OverflowError as exc:
                raise self.fail_fp("overflow", "numero scritto", node, operator=False) from exc
            if not np.isfinite(value):
                raise self.fail_fp("overflow", "numero scritto", node, operator=False)
            return value
        if isinstance(node, ast.Name):
            return np.float64(CONSTANTS[node.id])
        if isinstance(node, ast.UnaryOp):
            value = self.evaluate(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            op = _BINARY[type(node.op)]
            left, right = self.evaluate(node.left), self.evaluate(node.right)
            if op in ("/", "%") and right == 0.0:
                raise self.fail_fp("divide", f"operatore {op!r}", node, operator=True)
            function = {"+": np.add, "-": np.subtract, "*": np.multiply, "/": np.divide, "%": np.mod,
                        "^": np.power}[op]
            return self.apply(function, (left, right), f"operatore {op!r}", node, operator=True)
        if isinstance(node, ast.Call):
            name = node.func.id
            args = [self.evaluate(a) for a in node.args]
            self.used.add(name)
            if name == "skydist":
                return self.skydist(args, node)
            return self.apply(FUNCTIONS[name][1], args, f"{name}()", node, operator=False)
        raise AssertionError(type(node).__name__)

    def skydist(self, args, node) -> np.float64:
        """``skydist`` con ``angular_distance`` del 17 (che usa ``skydist`` del 13, D13-10)."""
        try:
            p1 = SkyFrame.from_lonlat(args[0] * u.deg, args[1] * u.deg, "icrs")
            p2 = SkyFrame.from_lonlat(args[2] * u.deg, args[3] * u.deg, "icrs")
            return np.float64(angular_distance(p1, p2, "deg").value.to_value(u.deg))
        except (CoordinatesWcsError, MeasuresError) as exc:
            raise _forwarded(exc, f"skydist (carattere {self.position(node)})") from exc


def _limit(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value <= 0:
        raise ValueError(f"{what} {value!r}: serve un intero positivo")
    return int(value)


@_registered
def evaluate_expression(expression: str, *, max_length: int = MAX_EXPRESSION_LENGTH,
                        max_depth: int = MAX_NESTING_DEPTH) -> CalculatorResult:
    """Valuta un'espressione della calcolatrice algebrica (grammatica chiusa, nessun ``eval``).

    Risultato adimensionale, o in gradi se l'espressione è una sola chiamata di ``skydist``.
    """
    max_length, max_depth = _limit(max_length, "max_length"), _limit(max_depth, "max_depth")
    if not isinstance(expression, str):
        raise TypeError("expression: serve una stringa")
    if len(expression) > max_length:
        raise CalculatorError("CALC_TOO_COMPLEX", f"espressione di {len(expression)} caratteri, oltre il limite "
                              f"di {max_length} (D18-5)", length=len(expression), limit=max_length)
    text, translated, origin = _prepare(expression)
    if not text:
        raise _syntax("espressione vuota", 0, expression)
    depth = _nesting_depth(text)
    if depth > max_depth:
        raise CalculatorError("CALC_TOO_COMPLEX", f"annidamento di {depth} parentesi, oltre il limite di "
                              f"{max_depth} (D18-5)", depth=depth, limit=max_depth)
    try:
        tree = ast.parse(translated, mode="eval")
    except SyntaxError as exc:
        offset = (exc.offset or 0) - 1
        position = origin[offset] if exc.offset and 0 <= offset < len(origin) else len(expression)
        raise _syntax("sintassi non valida", position, expression) from exc
    except (RecursionError, MemoryError) as exc:
        raise CalculatorError("CALC_TOO_COMPLEX", "espressione troppo complessa per l'analizzatore") from exc
    evaluator = _Evaluator(expression, translated, origin)
    try:
        evaluator.check(tree)
        value = evaluator.evaluate(tree)
    except RecursionError as exc:
        raise CalculatorError("CALC_TOO_COMPLEX", "espressione troppo complessa (catena di operazioni troppo "
                              "lunga)") from exc
    single_skydist = isinstance(tree.body, ast.Call) and tree.body.func.id == "skydist"
    library = f"numpy {np.__version__} (tabella FUNCTIONS del modulo 13)"
    notes = ["analizzatore ast a elenco chiuso (D18-1), '^' = potenza; funzioni senza 'd' in radianti, con 'd' "
             "in gradi"]
    if "skydist" in evaluator.used:
        library += f", astropy {astropy.__version__} (angular_distance del modulo 17)"
        notes.append("skydist: distanza sferica con angular_distance del modulo 17, coordinate in gradi; le due "
                     "coppie si intendono nello stesso sistema (la distanza non dipende da quale)")
    if "round" in evaluator.used:
        notes.append("round: numpy.round, metà al pari (D13-15)")
    angles = sorted(evaluator.used.intersection(_ANGLE_FUNCTIONS))
    if angles and not single_skydist:
        notes.append(f"valori angolari di {', '.join(angles)} usati come numeri puri: risultato adimensionale")
    return CalculatorResult(
        calculator="algebrica", input=text, value=value, unit=u.deg if single_skydist else u.dimensionless_unscaled,
        scale=None, library=library, notes=tuple(notes),
        command=CalculatorCommand("evaluate_expression", (("expression", text), ("max_length", max_length),
                                                          ("max_depth", max_depth))))


# --------------------------------------------------------------------------
# P2 — calcolatrice del tempo (DC1: scala sempre dichiarata)
# --------------------------------------------------------------------------

#: Formati di ingresso: ISO 8601 (con ``T``, con spazio o solo data), JD, MJD, anno giuliano e besseliano.
TIME_FORMATS = ("iso", "jd", "mjd", "jyear", "byear")
#: Scale di tempo di ``astropy.time`` ammesse (``local`` non è una scala astronomica).
TIME_SCALES = ("utc", "tai", "tt", "tdb", "tcb", "tcg", "ut1")


@dataclass(frozen=True)
class TimeRepresentations:
    """La stessa data in tutte le rappresentazioni, tutte nella scala ``scale``."""

    scale: str
    iso: str  # ISO 8601 al nanosecondo
    jd: np.float64
    mjd: np.float64
    jyear: np.float64
    byear: np.float64
    jd1: np.float64  # JD in due parti (jd1 + jd2) per la precisione piena di astropy.time
    jd2: np.float64

    @property
    def text(self) -> str:
        scale = self.scale.upper()
        return (f"ISO 8601 {self.iso} ({scale}); JD {self.jd!r} ({scale}); MJD {self.mjd!r} ({scale}); "
                f"anno giuliano J{self.jyear!r} ({scale}); anno besseliano B{self.byear!r} ({scale})")


def _time_scale(scale: object, what: str) -> str:
    if scale is None:
        raise CalculatorError("TIME_SCALE_REQUIRED", f"{what} mancante: la scala di tempo non si assume mai (DC1); "
                              f"scale ammesse: {', '.join(s.upper() for s in TIME_SCALES)}")
    name = scale.lower() if isinstance(scale, str) else None
    if name not in TIME_SCALES:
        raise CalculatorError("TIME_SCALE_REQUIRED", f"{what} {scale!r} non riconosciuta; scale ammesse: "
                              f"{', '.join(s.upper() for s in TIME_SCALES)}")
    return name


def _parse_time(time_value: object, time_format: str, scale: str) -> Time:
    if time_format == "iso":
        if not isinstance(time_value, str) or not time_value.strip():
            raise CalculatorError("TIME_INVALID", f"data {time_value!r}: serve un testo ISO 8601 "
                                  "(AAAA-MM-GGThh:mm:ss[.s], anche con spazio o solo data)")
        errors = []
        for fmt in ("isot", "iso"):
            try:
                return Time(time_value.strip(), format=fmt, scale=scale)
            except ValueError as exc:
                errors.append(str(exc).splitlines()[-1])
        raise CalculatorError("TIME_INVALID", f"data {time_value!r} non valida in ISO 8601 "
                              f"(AAAA-MM-GGThh:mm:ss[.s]): {errors[-1]}")
    if isinstance(time_value, bool) or not isinstance(time_value, (int, float, np.integer, np.floating)) \
            or not math.isfinite(float(time_value)):
        raise CalculatorError("TIME_INVALID", f"valore {time_value!r}: per il formato {time_format} serve un numero "
                              "finito")
    try:
        return Time(float(time_value), format=time_format, scale=scale)
    except ValueError as exc:
        raise CalculatorError("TIME_INVALID", f"valore {time_value!r} non valido per {time_format}: {exc}") from exc


@_registered
def convert_time(time_value, time_format: str, scale: str | None, target_scale: str | None = None) -> CalculatorResult:
    """Converte una data tra ISO 8601, JD, MJD, anno giuliano e besseliano con ``astropy.time``.

    ``scale`` è obbligatoria (DC1); ``target_scale`` facoltativa (cambio di scala con ``astropy.time``).
    """
    if time_format not in TIME_FORMATS:
        raise CalculatorError("TIME_INVALID", f"formato {time_format!r} non previsto; formati: {', '.join(TIME_FORMATS)}")
    source_scale = _time_scale(scale, "scale")
    target = source_scale if target_scale is None else _time_scale(target_scale, "target_scale")
    notes = []
    with warnings.catch_warnings(record=True) as caught, iers.conf.set_temp("auto_download", False):
        warnings.simplefilter("always")
        when = _parse_time(time_value, time_format, source_scale)
        try:
            converted = getattr(when, target)
        except Exception as exc:  # dati IERS mancanti per UT1, o conversione non definita
            raise CalculatorError("TIME_INVALID", f"conversione {source_scale.upper()} → {target.upper()} non "
                                  f"eseguibile: {exc}") from exc
        converted.precision = 9
        values = TimeRepresentations(
            scale=target, iso=converted.isot, jd=np.float64(converted.jd), mjd=np.float64(converted.mjd),
            jyear=np.float64(converted.jyear), byear=np.float64(converted.byear),
            jd1=np.float64(converted.jd1), jd2=np.float64(converted.jd2))
    notes.extend(dict.fromkeys(f"avviso di astropy/ERFA: {w.message}" for w in caught))
    if target != source_scale:
        notes.append(f"cambio di scala {source_scale.upper()} → {target.upper()} con astropy.time")
    if "ut1" in (source_scale, target):
        notes.append("UT1 con le tabelle IERS già disponibili ad astropy (nessuno scaricamento automatico)")
    notes.append("JD, MJD e anni in float64 (risoluzione del JD ≈ 40 µs); jd1 + jd2 a precisione piena")
    return CalculatorResult(
        calculator="tempo", input=f"{time_value!r} ({time_format}, scala {source_scale.upper()})", value=values,
        unit=None, scale=target, library=f"astropy {astropy.__version__} (astropy.time)", notes=tuple(notes),
        command=CalculatorCommand("convert_time", (("time_value", time_value), ("time_format", time_format),
                                                   ("scale", scale), ("target_scale", target_scale))))
