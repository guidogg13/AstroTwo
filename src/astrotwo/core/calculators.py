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
import difflib
import math
import re
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime

import astropy
import astropy.units as u
import matplotlib
import numpy as np
from astropy.io import fits
from astropy.time import Time
from astropy.utils import iers

from astrotwo.core.catalogs import CONSTANTS, FUNCTIONS
from astrotwo.core.coordinates_wcs import (
    CoordinatesWcsError,
    SkyFrame,
    _to_epoch,
    convert_coordinates,
    parse_sexagesimal,
    propagate_position,
)
from astrotwo.core.images_fits import FitsImage, ImagesFitsError, _section_key, pixel_scaling, set_display
from astrotwo.core import measures
from astrotwo.core.measures import (
    UNDECLARED_UNIT,
    CatalogSource,
    MeasuresError,
    angular_distance,
    angular_offsets,
    apply_offsets,
    offset_position,
    read_pixel,
)

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
    "EQUIVALENCIES",
    "convert_units",
    "DisplaySettings",
    "PixelValues",
    "convert_pixel_value",
    "CoordinateInput",
    "CoordinateTarget",
    "ProperMotion",
    "CoordinateRepresentation",
    "CoordinatesOutput",
    "calculate_coordinates",
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


# --------------------------------------------------------------------------
# P3 — convertitore di unità (D18-2 formati FITS/VOUnit, D18-3 equivalenze, D18-4 magnitudini)
# --------------------------------------------------------------------------

#: Equivalenze offerte solo su richiesta esplicita (D18-3): nome → (funzione di astropy, parametro richiesto).
EQUIVALENCIES: dict[str, tuple[object, str | None]] = {
    "spectral": (u.spectral, None),
    "spectral_density": (u.spectral_density, "lunghezza d'onda o frequenza di riferimento"),
    "temperature": (u.temperature, None),
    "parallax": (u.parallax, None),
    "doppler_radio": (u.doppler_radio, "frequenza o lunghezza d'onda a riposo"),
    "doppler_optical": (u.doppler_optical, "frequenza o lunghezza d'onda a riposo"),
    "doppler_relativistic": (u.doppler_relativistic, "frequenza o lunghezza d'onda a riposo"),
}
_SEXAGESIMAL = re.compile(r"[+-]?\d+(?::\d+){1,2}(?:\.\d*)?")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d*)?)?)?")
_TIME_TARGETS = ("iso", "jd", "mjd", "jyear", "byear")


def _similar_units(text: str) -> list[str]:
    """Unità simili note ad ``astropy.units`` e valide in FITS o VOUnit (per il messaggio di ``UNIT_UNKNOWN``)."""
    found: list[str] = []
    try:
        found.append(u.Unit(text).to_string("fits"))  # nota al formato generico di astropy
    except (ValueError, TypeError):
        pass
    names = list(u.get_current_unit_registry().registry)
    lowered = {n.lower(): n for n in names}
    for match in difflib.get_close_matches(text.lower(), list(lowered), n=10, cutoff=0.6):
        name = lowered[match]
        for fmt in ("fits", "vounit"):
            try:
                u.Unit(name, format=fmt)
            except ValueError:
                continue
            found.append(name)
            break
    return list(dict.fromkeys(found))[:5]


def _standard_unit(text: object, what: str) -> tuple[u.UnitBase, str]:
    """Unità nel formato FITS o, se non lo è, VOUnit (D18-2): (unità, formato usato)."""
    if not isinstance(text, str) or not text.strip():
        raise CalculatorError("UNIT_UNKNOWN", f"{what} {text!r}: serve una stringa di unità FITS o VOUnit")
    errors = []
    for fmt in ("fits", "vounit"):
        try:
            return u.Unit(text.strip(), format=fmt), fmt.upper() if fmt == "fits" else "VOUnit"
        except ValueError as exc:
            errors.append(str(exc).split(".")[0])
    similar = _similar_units(text.strip())
    raise CalculatorError("UNIT_UNKNOWN", f"{what} {text!r} non valida nei formati FITS e VOUnit"
                          + (f"; unità simili note ad astropy.units: {', '.join(similar)}" if similar else ""),
                          similar=similar, errors=errors)


def _is_logarithmic(unit: u.UnitBase) -> bool:
    """Unità logaritmica (``mag``, ``dex``…): in ``astropy`` si decompone in ``dex``."""
    return any(base == u.dex for base in unit.decompose().bases)


def _equivalency(name: object, reference: object) -> tuple[list, str]:
    if name not in EQUIVALENCIES:
        raise CalculatorError("UNIT_EQUIVALENCY_UNKNOWN", f"equivalenza {name!r} non offerta; equivalenze: "
                              f"{', '.join(EQUIVALENCIES)} (D18-3)")
    function, parameter = EQUIVALENCIES[name]
    if parameter is None:
        if reference is not None:
            raise ValueError(f"l'equivalenza {name!r} non usa reference")
        return function(), f"equivalenza {name} (astropy.units.{function.__name__}), richiesta esplicitamente"
    if not isinstance(reference, u.Quantity) or reference.size != 1:
        raise CalculatorError("UNIT_REFERENCE_REQUIRED", f"equivalenza {name!r}: serve reference, {parameter}, "
                              "con unità (obbligatoria, D18-3)")
    try:
        return function(reference), (f"equivalenza {name} (astropy.units.{function.__name__}) con riferimento "
                                     f"{reference}, richiesta esplicitamente")
    except (u.UnitsError, ValueError, TypeError) as exc:
        raise CalculatorError("UNIT_INCOMPATIBLE", f"reference {reference}: {exc}") from exc


def _units_command(**arguments) -> CalculatorCommand:
    return CalculatorCommand("convert_units", tuple(arguments.items()))


@_registered
def convert_units(value, from_unit, to_unit, equivalency=None, *, reference=None, sexagesimal=None, scale=None,
                  target_scale=None) -> CalculatorResult:
    """Converte un valore tra unità con ``astropy.units`` (formati FITS e VOUnit, D18-2).

    ``value``: numero, espressione della calcolatrice algebrica, angolo sessagesimale (``sexagesimal`` =
    ``"degrees"`` o ``"hours"``, ``from_unit=None``) o data ISO 8601 (``scale`` obbligatoria,
    ``from_unit=None``, ``to_unit`` = ``iso``/``jd``/``mjd``/``jyear``/``byear``, calcolo di ``convert_time``).
    Equivalenze solo se richieste (D18-3); magnitudini ↔ flussi rifiutate (D18-4).
    """
    command = _units_command(value=value, from_unit=from_unit, to_unit=to_unit, equivalency=equivalency,
                             reference=reference, sexagesimal=sexagesimal, scale=scale, target_scale=target_scale)
    text = value.strip() if isinstance(value, str) else None
    if text is not None and _ISO_DATE.fullmatch(text):
        if from_unit is not None or equivalency is not None or sexagesimal is not None:
            raise ValueError("una data si converte senza from_unit, equivalenza o sexagesimal")
        if to_unit not in _TIME_TARGETS:
            raise CalculatorError("TIME_INVALID", f"data {text!r}: to_unit {to_unit!r} non è una rappresentazione "
                                  f"del tempo ({', '.join(_TIME_TARGETS)})")
        timed = convert_time(text, "iso", scale, target_scale)
        return CalculatorResult(
            calculator="unità", input=f"{timed.input} → {to_unit}", value=getattr(timed.value, to_unit), unit=None,
            scale=timed.scale, library=timed.library, command=command,
            notes=("data convertita con la calcolatrice del tempo (convert_time)",) + timed.notes)
    if scale is not None or target_scale is not None:
        raise ValueError("scale e target_scale solo per le date")
    notes: list[str] = []
    library = f"astropy {astropy.__version__} (astropy.units)"
    if text is not None and _SEXAGESIMAL.fullmatch(text):
        if sexagesimal not in ("degrees", "hours"):
            raise CalculatorError("UNIT_SEXAGESIMAL_UNIT_REQUIRED", f"angolo sessagesimale {text!r}: dichiarare "
                                  "sexagesimal='degrees' (d:m:s) o 'hours' (h:m:s)")
        if from_unit is not None:
            raise ValueError("con un angolo sessagesimale from_unit non si passa: l'angolo è in gradi")
        try:
            number = np.float64(parse_sexagesimal(text, hours=sexagesimal == "hours")[0].to_value(u.deg))
        except CoordinatesWcsError as exc:
            raise _forwarded(exc, "angolo sessagesimale") from exc
        source, source_format = u.deg, "angolo sessagesimale"
        notes.append(f"{text} letto in {'ore' if sexagesimal == 'hours' else 'gradi'} con parse_sexagesimal "
                     f"del modulo 10 (astropy Angle): {number!r} deg")
    else:
        if sexagesimal is not None:
            raise ValueError("sexagesimal solo per un angolo sessagesimale scritto come d:m:s o h:m:s")
        source, source_format = _standard_unit(from_unit, "from_unit")
        if text is not None:
            expression = evaluate_expression(text)
            number = np.float64(expression.value)
            if expression.unit == u.deg and not source.is_equivalent(u.deg):
                raise CalculatorError("UNIT_INCOMPATIBLE", f"{text!r} dà gradi (skydist): from_unit {from_unit!r} "
                                      "non è un angolo")
            notes.append(f"valore dall'espressione {expression.input!r} = {number!r} (calcolatrice algebrica)")
            library += f", {expression.library}"
        elif isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
            raise TypeError("value: numero, espressione, angolo sessagesimale o data ISO 8601")
        else:
            number = np.float64(value)
        notes.append(f"from_unit {from_unit!r} letta nel formato {source_format}")
    if not np.isfinite(number):
        raise CalculatorError("CALC_DOMAIN_ERROR", f"valore {number!r} non finito")
    target, target_format = _standard_unit(to_unit, "to_unit")
    notes.append(f"to_unit {to_unit!r} letta nel formato {target_format}")
    if _is_logarithmic(source) != _is_logarithmic(target):
        raise CalculatorError("UNIT_ZERO_POINT_REQUIRED", f"{source} → {target}: magnitudine (unità logaritmica) ↔ "
                              "flusso richiede punto zero e sistema fotometrico: conversione del modulo 20 (D18-4)")
    equivalencies = []
    if equivalency is not None:
        equivalencies, note = _equivalency(equivalency, reference)
        notes.append(note)
    elif reference is not None:
        raise ValueError("reference solo con un'equivalenza")
    try:
        with np.errstate(all="ignore"):
            converted = (number * source).to(target, equivalencies=equivalencies)
    except u.UnitConversionError as exc:
        hint = "" if equivalency is not None else " (equivalenze solo su richiesta esplicita, D18-3)"
        raise CalculatorError("UNIT_INCOMPATIBLE", f"{source} ({source.physical_type}) e {target} "
                              f"({target.physical_type}) non convertibili{hint}",
                              physical_types=(str(source.physical_type), str(target.physical_type))) from exc
    result = np.float64(converted.value)
    if not np.isfinite(result):
        raise CalculatorError("CALC_DOMAIN_ERROR", f"{number!r} {source} → {target}: risultato non finito ({result!r})")
    written = text if text is not None else repr(number)
    given = f"sessagesimale in {sexagesimal}" if source_format == "angolo sessagesimale" else str(source)
    return CalculatorResult(calculator="unità", input=f"{written} [{given}] → {target}", value=result, unit=target,
                            scale=None, library=library, notes=tuple(notes), command=command)


# --------------------------------------------------------------------------
# P4 — calcolatrice dei pixel (regola FITS, D18-6 valore grezzo dal file)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DisplaySettings:
    """Parametri di visualizzazione passati a ``set_display`` del modulo 11 per l'indice di colore."""

    vmin: float
    vmax: float
    gamma: float = 1.0
    stretch: str = "linear"
    palette: str = "gray"


@dataclass(frozen=True)
class PixelValues:
    """Valori di un pixel: grezzo, fisico (``BZERO + BSCALE × grezzo``), costanti e indice di colore."""

    raw: np.float64
    physical: np.float64
    bzero: np.float64
    bscale: np.float64
    blank: int | None
    color_index: int | None  # 0–255 nella palette; None senza parametri di visualizzazione o per un pixel non finito
    in_memory: np.float64 | None = None  # valore tenuto dal modulo 11 (clic), per il confronto
    x: int | None = None  # colonna, convenzione numpy (clic)
    y: int | None = None

    @property
    def fits_position(self) -> tuple[int, int] | None:
        """Posizione mostrata all'utente in convenzione FITS (indice da 1, DC7)."""
        return None if self.x is None else (self.x + 1, self.y + 1)


def _fits_number(value: object, what: str) -> np.float64:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)) \
            or not np.isfinite(value):
        raise ValueError(f"{what} {value!r}: serve un numero finito")
    return np.float64(value)


def _color_index(value: np.float64, display: DisplaySettings, image: FitsImage | None, xy) -> tuple[int | None, str]:
    """Indice nella palette (0–255) dal valore normalizzato di ``set_display`` del modulo 11."""
    if not isinstance(display, DisplaySettings):
        raise TypeError("display: serve un DisplaySettings")
    try:
        if display.stretch == "histeq":
            # L'equalizzazione dipende da tutta l'immagine: si calcola sull'immagine intera.
            if image is None or image.is_preview:
                raise CalculatorError("OPERATION_UNSUPPORTED", "stretch histeq: l'indice dipende da tutta l'immagine; "
                                      "serve il clic su un'immagine intera in memoria")
            plane = set_display(image, display.vmin, display.vmax, display.gamma, display.palette, display.stretch)
            normalized = plane.values[xy[1], xy[0]]
            how = "set_display del modulo 11 sull'immagine intera (histeq)"
        else:
            plane = set_display(np.array([[value]]), display.vmin, display.vmax, display.gamma, display.palette,
                                display.stretch)
            normalized = plane.values[0, 0]
            how = "set_display del modulo 11 sul valore (funzione di trasferimento punto per punto)"
    except ImagesFitsError as exc:
        raise CalculatorError(exc.code, f"indice di colore: {exc.message}") from exc
    if not np.isfinite(normalized):
        return None, f"{how}: pixel non finito, trasparente (alfa 0), nessun indice"
    size = matplotlib.colormaps[display.palette].N
    # Regola delle palette di matplotlib per un valore in [0, 1]: indice floor(v·N), 1 → N − 1.
    index = int(min(np.floor(np.float64(normalized) * size), size - 1))
    return index, f"{how}; valore normalizzato {float(normalized)!r} → indice floor(v·{size}) della palette " \
                  f"{display.palette!r} (0–{size - 1}; lo 0 non è riservato: la trasparenza è nell'alfa)"


def _raw_from_file(image: FitsImage, x: int, y: int) -> np.float64:
    """Valore grezzo scritto nel file (D18-6): ``astropy.io.fits`` con ``do_not_scale_image_data=True``."""
    if not image.format.startswith("fits"):
        raise CalculatorError("PIXEL_RAW_UNAVAILABLE", f"immagine {image.format}: nessun valore grezzo FITS")
    if image.history:
        raise CalculatorError("PIXEL_RAW_UNAVAILABLE", "immagine derivata (" + "; ".join(image.history)
                              + "): i pixel non sono più quelli del file")
    try:
        with fits.open(image.origin, do_not_scale_image_data=True, memmap=False) as hdul:
            section = hdul[image.hdu_index].section
            value = np.asarray(section[_section_key(image.raw_ndim, image.dropped_axes, slice(y, y + 1),
                                                    slice(x, x + 1))]).ravel()[0]
    except (OSError, IndexError, ValueError, TypeError) as exc:
        raise CalculatorError("PIXEL_RAW_UNAVAILABLE", f"{image.origin}: valore grezzo non leggibile ({exc})") from exc
    return np.float64(value)


@_registered
def convert_pixel_value(*, raw=None, physical=None, bzero=None, bscale=None, blank=None, display=None, bunit=None,
                        image=None, position=None) -> CalculatorResult:
    """Valore grezzo ↔ fisico con la regola FITS ``fisico = BZERO + BSCALE × grezzo`` e indice di colore.

    A mano: ``raw`` o ``physical`` e ``bzero``, ``bscale`` (obbligatori), ``blank`` facoltativo. Con un clic:
    ``image`` e ``position`` (``read_pixel`` del 17, costanti dall'intestazione con ``pixel_scaling`` dell'11,
    grezzo dal file con ``do_not_scale_image_data=True``, D18-6).
    """
    notes: list[str] = []
    in_memory = x = y = None
    if image is not None or position is not None:
        if image is None or position is None:
            raise TypeError("clic: servono image e position")
        if any(v is not None for v in (raw, physical, bzero, bscale, blank, bunit)):
            raise TypeError("clic: raw, physical, bzero, bscale, blank e bunit vengono dall'immagine")
        try:
            reading = read_pixel(image, position)
        except MeasuresError as exc:
            raise _forwarded(exc, "clic sull'immagine") from exc
        x, y, in_memory = reading.x, reading.y, reading.value
        scaling = pixel_scaling(image)
        zero = np.float64(0.0 if scaling.bzero is None else scaling.bzero)
        scale = np.float64(1.0 if scaling.bscale is None else scaling.bscale)
        blank = scaling.blank
        unit = reading.unit if reading.unit is not None else reading.unit_label
        notes.append(f"pixel ({x + 1}, {y + 1}) in convenzione FITS (numpy ({x}, {y})), letto con read_pixel del "
                     "modulo 17; BZERO, BSCALE e BLANK dall'intestazione (pixel_scaling del modulo 11)"
                     + ("; BZERO assente: 0 per lo standard FITS" if scaling.bzero is None else "")
                     + ("; BSCALE assente: 1 per lo standard FITS" if scaling.bscale is None else ""))
        raw_value = _raw_from_file(image, x, y)
        notes.append("valore grezzo letto dal file con astropy.io.fits, do_not_scale_image_data=True (D18-6)")
        given = "raw"
    else:
        if (raw is None) == (physical is None):
            raise TypeError("a mano: serve raw oppure physical (uno solo)")
        if bzero is None or bscale is None:
            raise TypeError("a mano: bzero e bscale obbligatori (nessun valore assunto)")
        zero, scale = _fits_number(bzero, "bzero"), _fits_number(bscale, "bscale")
        if blank is not None and (isinstance(blank, bool) or not isinstance(blank, (int, np.integer))):
            raise ValueError(f"blank {blank!r}: serve un intero (BLANK vale per i dati interi)")
        unit = bunit if bunit is not None else UNDECLARED_UNIT
        given = "raw" if raw is not None else "physical"
        raw_value = _fits_number(raw, "raw") if raw is not None else None
    if given == "raw":
        if blank is not None and raw_value == blank:
            raise CalculatorError("PIXEL_BLANK", f"valore grezzo {raw_value!r} uguale a BLANK: pixel senza valore, "
                                  "nessun valore fisico", raw=raw_value, blank=int(blank))
        physical_value = np.float64(zero + scale * raw_value)
    else:
        physical_value = _fits_number(physical, "physical")
        if scale == 0.0:
            raise CalculatorError("PIXEL_BSCALE_ZERO", "BSCALE = 0: il valore grezzo non si ricava dal fisico")
        raw_value = np.float64((physical_value - zero) / scale)
        if raw_value != np.floor(raw_value):
            notes.append(f"valore grezzo {raw_value!r} non intero: non rappresentabile esattamente in un file con "
                         "BITPIX intero (nessun arrotondamento)")
        if blank is not None and raw_value == blank:
            notes.append("il valore grezzo coincide con BLANK: nel file indicherebbe un pixel senza valore")
    if not (np.isfinite(physical_value) and np.isfinite(raw_value)):
        raise CalculatorError("CALC_OVERFLOW", "valore oltre i limiti di float64")
    if in_memory is not None and in_memory != physical_value:
        notes.append(f"valore tenuto dal modulo 11: {in_memory!r} (tipo prodotto da astropy.io.fits); "
                     f"regola FITS in float64: {physical_value!r}")
    index = None
    if display is not None:
        shown = in_memory if in_memory is not None else physical_value
        index, how = _color_index(shown, display, image, (x, y))
        notes.append(how)
    notes.append("regola FITS: fisico = BZERO + BSCALE × grezzo, in float64")
    values = PixelValues(raw=raw_value, physical=physical_value, bzero=zero, bscale=scale,
                         blank=None if blank is None else int(blank), color_index=index, in_memory=in_memory, x=x, y=y)
    arguments = (("image", image), ("position", position)) if image is not None else (
        ("raw", raw), ("physical", physical), ("bzero", bzero), ("bscale", bscale), ("blank", blank), ("bunit", bunit))
    return CalculatorResult(
        calculator="pixel", input=f"{given} = {raw_value if given == 'raw' else physical_value!r}, BZERO = {zero!r}, "
        f"BSCALE = {scale!r}, BLANK = {blank!r}", value=values, unit=unit, scale=None,
        library=f"numpy {np.__version__}; astropy {astropy.__version__} (astropy.io.fits, modulo 11)",
        notes=tuple(notes), command=CalculatorCommand("convert_pixel_value", arguments + (("display", display),)))


# --------------------------------------------------------------------------
# P5 — calcolatrice delle coordinate (moduli 10 e 17, D10-8: nessun calcolo riscritto qui)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CoordinateInput:
    """Coordinate scritte: numeri in gradi o testo sessagesimale; per il testo della longitudine si dichiara
    ``lon_sexagesimal`` (``"hours"`` per h:m:s, ``"degrees"`` per d:m:s); la latitudine sessagesimale è in gradi."""

    lon: object
    lat: object
    frame: str
    lon_sexagesimal: str | None = None
    equinox: object = None
    obstime: object = None
    epoch: object = None  # epoca delle posizioni, se nota (mai assunta)


@dataclass(frozen=True)
class CoordinateTarget:
    """Sistema richiesto in uscita, con equinozio e ``obstime`` se il sistema li prevede (modulo 10)."""

    frame: str
    equinox: object = None
    obstime: object = None


@dataclass(frozen=True)
class ProperMotion:
    """Moto proprio per ``propagate_position`` del modulo 10 (coordinate scritte)."""

    pm_ra_cosdec: u.Quantity
    pm_dec: u.Quantity
    parallax: u.Quantity | None = None
    radial_velocity: u.Quantity | None = None
    proper_motion_only: bool = False


@dataclass(frozen=True)
class CoordinateRepresentation:
    """Una posizione in un sistema: decimale e sessagesimale, con frame ed epoca dichiarati."""

    position: SkyFrame
    lon_deg: np.float64
    lat_deg: np.float64
    lon_sexagesimal: str
    lat_sexagesimal: str
    lon_in_hours: bool

    @property
    def text(self) -> str:
        epoch = "non nota" if self.position.epoch is None else self.position.epoch.jyear_str
        unit = "h:m:s" if self.lon_in_hours else "d:m:s"
        return (f"{self.position.frame_name}: {self.lon_deg!r}° {self.lat_deg!r}° = {self.lon_sexagesimal} ({unit}) "
                f"{self.lat_sexagesimal} (d:m:s); epoca delle posizioni {epoch}")


@dataclass(frozen=True)
class CoordinatesOutput:
    """Risultato della calcolatrice delle coordinate."""

    base: SkyFrame  # posizione dopo propagazione e offset, nel suo frame
    representations: tuple[CoordinateRepresentation, ...]
    offsets_to: measures.AngularOffsets | None = None


def _point_from_input(value: CoordinateInput) -> tuple[SkyFrame, str]:
    def angle(component, what: str, hours: bool) -> u.Quantity:
        if isinstance(component, str):
            return parse_sexagesimal(component, hours=hours)[0]
        if isinstance(component, u.Quantity):
            return component
        if isinstance(component, bool) or not isinstance(component, (int, float, np.integer, np.floating)):
            raise TypeError(f"{what}: numero in gradi, Quantity angolare o testo sessagesimale")
        return np.float64(component) * u.deg

    if isinstance(value.lon, str) and value.lon_sexagesimal not in ("hours", "degrees"):
        raise CalculatorError("UNIT_SEXAGESIMAL_UNIT_REQUIRED", f"longitudine {value.lon!r}: dichiarare "
                              "lon_sexagesimal='hours' (h:m:s) o 'degrees' (d:m:s)")
    lon = angle(value.lon, "lon", value.lon_sexagesimal == "hours")
    lat = angle(value.lat, "lat", False)
    point = SkyFrame.from_lonlat(lon, lat, value.frame, equinox=value.equinox, obstime=value.obstime,
                                 epoch=value.epoch)
    return point, f"coordinate scritte {value.lon!r}, {value.lat!r} in {value.frame}"


def _representation(point: SkyFrame) -> CoordinateRepresentation:
    in_hours = "ra" in point.coord.frame.representation_component_names
    lon, lat = point.coord.spherical.lon, point.coord.spherical.lat
    lon_text = lon.to_string(unit=u.hourangle, sep=":", precision=5, pad=True) if in_hours \
        else lon.to_string(unit=u.deg, sep=":", precision=4, pad=True)
    lat_text = lat.to_string(unit=u.deg, sep=":", precision=4, pad=True, alwayssign=True)
    return CoordinateRepresentation(position=point, lon_deg=np.float64(lon.deg), lat_deg=np.float64(lat.deg),
                                    lon_sexagesimal=lon_text, lat_sexagesimal=lat_text, lon_in_hours=in_hours)


@_registered
def calculate_coordinates(position, targets, *, epoch=None, motion=None, offsets=None, direction=None,
                          to_point=None) -> CalculatorResult:
    """Raccoglie gli input e chiama i moduli 10 e 17; restituisce le rappresentazioni richieste.

    ``position``: ``SkyFrame``/``SkyCoord``, ``CoordinateInput`` o ``CatalogSource`` (riga di catalogo, epoca e
    moto proprio dai metadati del 13). ``targets``: sequenza di ``CoordinateTarget``. Ordine: propagazione
    all'``epoch`` (10), offset (``offsets`` = Δα·cos δ, Δδ) o calcolo inverso (``direction`` = distanza, angolo
    di posizione) del 17, conversione in ogni sistema richiesto (10); ``to_point``: offset verso quel punto (17).
    """
    notes: list[str] = []
    try:
        if isinstance(position, CatalogSource):
            single, base, epoch_source = measures._source_point(position, "riga di catalogo")
            notes.append(f"riga {int(position.row)} di {single.source}, epoca da {epoch_source}")
            if epoch is not None:
                target_epoch = _to_epoch(epoch, "epoch")
                if not measures._same_epoch(base.epoch, target_epoch):
                    base, note = measures._propagated(position, single, target_epoch, "riga di catalogo")
                    notes.append(note + " (propagate del 13 → propagate_position del 10)")
            if motion is not None:
                raise TypeError("con una riga di catalogo il moto proprio viene dai suoi metadati: motion non si passa")
        else:
            if isinstance(position, CoordinateInput):
                base, note = _point_from_input(position)
                notes.append(note)
            else:
                base = measures._as_point(position, "position")
            if epoch is not None:
                if not isinstance(motion, ProperMotion):
                    raise CalculatorError("EPOCH_REQUIRED", "propagazione: serve il moto proprio (ProperMotion); "
                                          "nessun moto proprio nullo assunto")
                moved = propagate_position(base, pm_ra_cosdec=motion.pm_ra_cosdec, pm_dec=motion.pm_dec,
                                           parallax=motion.parallax, target_epoch=epoch,
                                           radial_velocity=motion.radial_velocity,
                                           proper_motion_only=motion.proper_motion_only)
                base = moved.position
                notes.append(f"propagata da {moved.source_epoch.jyear_str} a {moved.target_epoch.jyear_str} con "
                             "propagate_position del modulo 10" + "".join(f"; {n}" for n in moved.notes))
            elif motion is not None:
                raise TypeError("motion senza epoch: nessuna propagazione richiesta")
        if offsets is not None and direction is not None:
            raise TypeError("offsets oppure direction, non entrambi")
        if offsets is not None:
            moved = apply_offsets(base, *offsets)
            base = moved.position
            notes.append("offset applicati con apply_offsets del modulo 17: " + "; ".join(moved.report.notes))
        if direction is not None:
            moved = offset_position(base, *direction)
            base = moved.position
            notes.append("calcolo inverso con offset_position del modulo 17: " + "; ".join(moved.report.notes))
        targets = tuple(targets)
        if not targets or not all(isinstance(t, CoordinateTarget) for t in targets):
            raise TypeError("targets: almeno un CoordinateTarget")
        representations = []
        for target in targets:
            converted = convert_coordinates(base, target.frame, equinox=target.equinox, obstime=target.obstime)
            representations.append(_representation(converted))
        offsets_to = angular_offsets(base, to_point) if to_point is not None else None
    except CoordinatesWcsError as exc:
        raise _forwarded(exc, "calcolatrice delle coordinate") from exc
    except MeasuresError as exc:
        raise _forwarded(exc, "calcolatrice delle coordinate") from exc
    notes.append("conversioni con convert_coordinates del modulo 10; sessagesimale: longitudine in h:m:s nei "
                 "sistemi equatoriali (0,00001 s), altrimenti d:m:s (0,0001″); latitudine d:m:s (0,0001″)")
    if offsets_to is not None:
        notes.append(f"offset verso to_point con angular_offsets del modulo 17: Δα·cos δ = {offsets_to.d_lon}, "
                     f"Δδ = {offsets_to.d_lat}")
    output = CoordinatesOutput(base=base, representations=tuple(representations), offsets_to=offsets_to)
    return CalculatorResult(
        calculator="coordinate", input=measures._describe(base), value=output, unit=u.deg, scale=None,
        library=f"astropy {astropy.__version__} (astropy.coordinates, moduli 10 e 17)", notes=tuple(notes),
        command=CalculatorCommand("calculate_coordinates", (
            ("position", position), ("targets", targets), ("epoch", epoch), ("motion", motion),
            ("offsets", offsets), ("direction", direction), ("to_point", to_point))))
