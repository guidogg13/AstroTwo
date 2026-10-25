# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Verifica dei numeri nelle risposte dell'IA (livello 3).

Specifica: ``mdfiles/34-ia-verifica-risultati.md`` (stato ``approvato``).

Codice deterministico: ogni numero scritto dall'assistente si cerca nei risultati completi dei comandi della
conversazione (05), nei loro parametri e nei messaggi dell'utente, alla precisione scritta e con l'unità scritta
(conversioni con ``astropy.units`` solo per confrontare). Solo le eccezioni dell'elenco chiuso ``EXCEPTIONS`` non si
verificano; un numero trovato solo in un testo esterno (32 §3.6) è ``external_text``, mai ``verified``. Il modulo
non chiama l'IA, non interpreta mai i testi come istruzioni, non riscrive la risposta e non usa Qt.
"""

from __future__ import annotations

import functools
import math
import re
import unicodedata
import warnings
from bisect import bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import astropy.units as u
import numpy as np

from astrotwo.ai.tool_registry import ASTROTWO_MESSAGE_CODES, ToolRegistry, external_source
from astrotwo.core.commands import WorkspaceState, time_text
from astrotwo.core.coordinates_wcs import CoordinatesWcsError, parse_sexagesimal

__all__ = [
    "EXCEPTIONS",
    "STATES",
    "CheckedNumber",
    "NumberException",
    "VerificationIssue",
    "VerificationReport",
    "WrittenNumber",
    "extract_numbers",
    "needs_regeneration",
    "regeneration_request",
    "verify_answer",
]

#: Stati di §3.5, nell'ordine di ricerca dopo le eccezioni.
STATES = ("verified", "verified_other_command", "command_parameter", "user_input", "external_text", "excluded",
          "not_verified", "ambiguous")

# --------------------------------------------------------------------------
# Eccezioni (§3.3, elenco chiuso): si cambia solo modificando la specifica
# --------------------------------------------------------------------------

_X4_NAMES = ("Gaia DR1", "Gaia DR2", "Gaia EDR3", "Gaia DR3", "2MASS", "2MASX", "AllWISE", "DSS1", "DSS2", "PS1",
             "Pan-STARRS1", "Tycho-2", "UCAC4", "URAT1", "GALEX GR6", "GALEX GR7", "APASS DR9")
_X5_PREFIXES = ("M", "NGC", "IC", "HD", "HIP", "HR", "TYC", "UGC", "PGC", "Mrk", "Arp", "Abell", "Cr", "Mel", "Tr")
_X7_NAMES = ("ISO 8601", "UTF-8", "SHA-256", "JSON Schema 2020-12", "VOTable 1.4", "ADQL 2.0")


def _alternatives(names: Sequence[str]) -> str:
    return "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))


@dataclass(frozen=True)
class NumberException:
    """Una riga di §3.3: identificativo, nome e riconoscimento."""

    id: str
    name: str
    pattern: re.Pattern


_PATH_PART = r"[\w.+-]+"
#: L'elenco chiuso di §3.3 come dati. Ordine di applicazione: nomi lunghi prima (X7, X4), poi gli altri.
EXCEPTIONS: tuple[NumberException, ...] = (
    NumberException("X7", "nome di uno standard", re.compile(rf"(?<![\w-])(?:{_alternatives(_X7_NAMES)})(?![\w-])")),
    NumberException("X4", "nome di catalogo o di survey", re.compile(
        rf"(?<![\w-])(?:{_alternatives(_X4_NAMES)}|SDSS DR\d+)(?![\w-])"
        # identificativi VizieR: I/ … IX/, B/, J/
        rf"|(?<![\w/])(?:IX|VIII|VII|VI|IV|V|III|II|I|B|J)/{_PATH_PART}(?:/{_PATH_PART})*"
        # identificativi HiPS: sequenze con /P/
        rf"|(?<![\w/])[\w.-]+/P/{_PATH_PART}(?:/{_PATH_PART})*")),
    NumberException("X1", "numero di comando", re.compile(r"(?<![\w#&])#\d+\b")),
    NumberException("X2", "identificativo di livello", re.compile(r"\bL\d+\b")),
    NumberException("X3", "epoca o equinozio", re.compile(r"\b[JB]\d{4}(?:\.\d+)?\b")),
    NumberException("X5", "designazione di un oggetto", re.compile(
        rf"(?<![\w-])(?:(?:{_alternatives(_X5_PREFIXES)}) ?\d+(?:-\d+)*|Sh2-\d+)(?!\.\d|\d)")),
    NumberException("X6", "numerazione Markdown", re.compile(
        r"(?m)^[ \t]*(?:[-*+][ \t]+)?\d+[.)](?=[ \t])|^#{1,6}[ \t]+\d+(?:\.\d+)*\.?(?=[ \t]|$)")),
)

# --------------------------------------------------------------------------
# Estrazione (§3.2)
# --------------------------------------------------------------------------

_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_SPACES = "   "  # spazio non separabile, stretto non separabile, sottile

#: Sequenze numeriche, nell'ordine in cui si provano nella stessa posizione. Il segno vale solo all'inizio di una
#: parola ("3-5" sono due numeri, 3 e 5); le cifre dopo una lettera sono parte di un identificativo (``ident``).
_NUMBER = re.compile(rf"""
 (?P<datetime>(?<![\w.:+-])\d{{4}}-\d{{2}}-\d{{2}}(?:T\d{{2}}:\d{{2}}(?::\d{{2}}(?:\.\d+)?)?(?:Z|[+-]\d{{2}}:?\d{{2}})?)?(?![\w-]))
|(?P<hms>(?<![\w.:])\d{{1,2}}[ ]?h[ ]?\d{{1,2}}[ ]?m(?:[ ]?\d{{1,2}}(?:\.\d+)?[ ]?s)?(?![^\W\d_]))
|(?P<dms>(?<![\w.:])[+-]?\d{{1,3}}[ ]?(?:°[ ]?\d{{1,2}}[ ]?[′'](?:[ ]?\d{{1,2}}(?:\.\d+)?[ ]?[″"])?
                                       |d[ ]?\d{{1,2}}[ ]?m(?:[ ]?\d{{1,2}}(?:\.\d+)?[ ]?s)?(?![^\W\d_])))
|(?P<colon>(?<![\w.:])[+-]?\d{{1,3}}:\d{{2}}(?::\d{{2}}(?:\.\d+)?)?(?![\d:]))
|(?P<sci>(?<![\w.])[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+|[ ]?[×x·][ ]?10(?:\^[+-]?\d+|[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+))(?!\d))
|(?P<ambiguous>(?<![\w.,])[+-]?(?:\d+(?:,\d+)+|\d{{1,3}}(?:[ {_SPACES}]\d{{3}})+)(?!\d|[.,]\d))
|(?P<decimal>(?<![\w.])[+-]?(?:\d+(?:\.\d+)*|\.\d+))
|(?P<ident>(?<=[^\W\d])\d+(?:\.\d+)*)
""", re.VERBOSE)

_DATETIME_FULL = re.compile(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?")

#: Simboli di unità subito dopo il numero (``%`` anche dopo uno spazio).
_UNIT_SYMBOLS = {"″": "arcsec", '"': "arcsec", "′": "arcmin", "'": "arcmin", "°": "deg", "%": "%"}
_UNIT_WORD = re.compile(r"[A-Za-zµμÅ][A-Za-z0-9µμÅ/^*.+\-]*")
_UNIT_POWER = re.compile(r" [A-Za-zµμÅ]+\^?[+-]?\d+(?![\w])")  # "km s-1": le cifre dell'esponente sono dell'unità
#: Parole della prosa che ``astropy.units`` leggerebbe come unità (annum, deca-annum, attosecondo): dopo uno spazio
#: non sono unità. Gli anni nei risultati sono scritti ``yr``.
_PROSE_WORDS = frozenset({"a", "da", "as"})
_WORD_STRIP = ".,;:!?()[]{}*_`|\"'“”‘’«»<>"
_BIGINT_DIGITS = 16  # oltre 15 cifre un float64 non distingue interi vicini: solo uguaglianza esatta


@dataclass(frozen=True)
class WrittenNumber:
    """Una sequenza numerica della risposta (§3.2) con posizione nel testo normalizzato (NFC).

    ``kind``: ``decimal``, ``scientific``, ``sexagesimal``, ``datetime``, ``ambiguous``, ``identifier`` (cifre dopo
    una lettera o con più punti: solo uguaglianza di testo), ``exception`` (§3.3, con ``exception``).
    ``tolerance``: mezza unità dell'ultima cifra scritta (più 1e-12 relativo), nell'unità scritta; per i
    sessagesimali ``angles`` dà le letture possibili (gradi, tolleranza in gradi).
    """

    text: str
    start: int
    end: int
    kind: str
    word: str = ""
    value: float | None = None
    tolerance: float | None = None
    unit: str | None = None
    unit_unrecognized: bool = False
    angles: tuple[tuple[float, float], ...] = ()
    exact_integer: bool = False
    cited: tuple[int, ...] = ()
    exception: str | None = None


def _normalized(text: str) -> tuple[str, str]:
    """(testo NFC, copia di lavoro con i segni meno ``−`` e ``‐`` davanti a una cifra resi ``-``): stessa lunghezza."""
    nfc = unicodedata.normalize("NFC", text)
    work = re.sub(r"[−‐](?=\d)", "-", nfc)
    return nfc, work


@functools.cache
def _parse_unit(text: str) -> u.UnitBase | None:
    """Unità di ``astropy.units`` (formato generico, poi VOUnit e FITS) o ``None`` se non riconosciuta."""
    if text == "%":
        return u.percent
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for fmt in ("generic", "vounit", "fits"):
            try:
                return u.Unit(text, format=fmt)
            except (ValueError, TypeError, u.UnitsError):
                continue
    return None


@functools.cache
def _factor(source: u.UnitBase, target: u.UnitBase) -> float | None:
    """Fattore da ``source`` a ``target`` (nessuna equivalenza), ``None`` se le grandezze sono diverse."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            f = float(source.to(target))
    except (u.UnitsError, TypeError, ValueError):
        return None
    return f if math.isfinite(f) and f != 0 else None


def _unit_after(work: str, end: int) -> tuple[str | None, int, bool]:
    """(unità scritta, fine dell'unità, non riconosciuta) dopo un numero che finisce in ``end``."""
    c = work[end:end + 1]
    if c in _UNIT_SYMBOLS:
        return _UNIT_SYMBOLS[c], end + 1, False
    if c == " " and work[end + 1:end + 2] == "%":
        return "%", end + 2, False
    adjacent = c != " "
    m = _UNIT_WORD.match(work, end if adjacent else end + 1)
    if not m:
        return None, end, False
    token_end = m.end()
    while token_end > m.start() and work[token_end - 1] in ".-+*/^":
        token_end -= 1
    token = work[m.start():token_end]
    if not token or work[token_end:token_end + 1] in ("'", "’"):  # elisione ("3 l'oggetto")
        return None, end, False
    if not adjacent and token in _PROSE_WORDS:
        return None, end, False
    full, full_end = token, token_end
    while (p := _UNIT_POWER.match(work, full_end)) and _parse_unit(full + p.group()) is not None:
        full, full_end = full + p.group(), p.end()
    if _parse_unit(full) is not None:
        return full, full_end, False
    if adjacent:  # "3x": unità non riconosciuta, il numero si confronta senza unità (§10)
        return None, token_end, True
    return None, end, False


def _word(nfc: str, start: int, end: int) -> str:
    """La parola che contiene il numero (spazi esclusi), senza la punteggiatura ai bordi."""
    a, b = start, end
    while a > 0 and not nfc[a - 1].isspace():
        a -= 1
    while b < len(nfc) and not nfc[b].isspace():
        b += 1
    return nfc[a:b].strip(_WORD_STRIP)


def _decimals(digits: str) -> int:
    return len(digits.split(".", 1)[1]) if "." in digits else 0


def _tolerance(value: float, step: float) -> float:
    """Mezza unità dell'ultima cifra scritta più 1e-12 relativo (rappresentazione binaria), R2."""
    return 0.5 * step + 1e-12 * abs(value)


def _sexagesimal(kind: str, text: str) -> tuple[tuple[float, float], ...]:
    """Letture possibili (gradi, tolleranza in gradi) con ``parse_sexagesimal`` del 10."""
    clean = text.replace(" ", "").replace("'", "′").replace('"', "″")
    fields = re.findall(r"\d+(?:\.\d+)?", clean)
    if kind == "hms":
        readings = (True,)
    elif kind == "colon":  # ore o gradi: un segno vuol dire gradi
        readings = (False,) if clean[0] in "+-" else (True, False)
    else:
        readings = (False,)
    out = []
    for hours in readings:
        try:
            value = float(parse_sexagesimal(clean, hours=hours).to_value(u.deg)[0])
        except CoordinatesWcsError:
            continue
        field_unit = (15.0, 0.25, 15.0 / 3600.0) if hours else (1.0, 1.0 / 60.0, 1.0 / 3600.0)
        step = field_unit[len(fields) - 1] * 10.0 ** -_decimals(fields[-1])
        out.append((value, _tolerance(value, step)))
    return tuple(out)


def _scientific(text: str) -> tuple[float, float]:
    clean = text.replace(" ", "").translate(_SUPERSCRIPTS)
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)(?:[eE]([+-]?\d+)|[×x·]10\^?([+-]?\d+))", clean)
    mantissa, exponent = m.group(1), int(m.group(2) or m.group(3))
    value = float(f"{mantissa}e{exponent}")
    return value, _tolerance(value, 10.0 ** (exponent - _decimals(mantissa)))


def _unit_digits(work: str, kind: str, start: int, word: str) -> bool:
    """Cifre dell'esponente di un'unità (``deg2``, ``s-1``): attaccate a una lettera o dopo ``-``/``^`` attaccato a
    una lettera, in una parola che ``astropy.units`` legge come unità."""
    exponent = kind in ("ident", "identifier") or (kind == "decimal" and start >= 2 and work[start - 1] in "-+^"
                                        and work[start - 2].isalpha())
    return exponent and any(c.isalpha() for c in word) and _parse_unit(word) is not None


def _sentences(work: str) -> list[int]:
    """Inizi delle frasi: dopo un a capo o dopo ``. ! ? ;`` seguiti da uno spazio."""
    return [0] + [m.end() for m in re.finditer(r"\n|[.!?;](?=\s)", work)]


def extract_numbers(text: str) -> list[WrittenNumber]:
    """Sequenze numeriche di §3.2 con posizione, valore, precisione scritta, unità e ``#n`` citati; eccezioni di
    §3.3 marcate (``kind == "exception"``). Posizioni nel testo normalizzato NFC."""
    nfc, work = _normalized(text)
    found: list[WrittenNumber] = []
    masked = list(work)
    for exc in EXCEPTIONS:
        for m in exc.pattern.finditer("".join(masked)):
            start, end = m.span()
            if exc.id == "X4":
                while end > start and work[end - 1] in ".-+":  # punto finale della frase
                    end -= 1
            found.append(WrittenNumber(nfc[start:end], start, end, "exception", exception=exc.id))
            masked[start:end] = "\0" * (end - start)
    work_masked = "".join(masked)
    commands = [(n.start, int(n.text[1:])) for n in found if n.exception == "X1"]
    starts = _sentences(work)
    consumed = 0
    for m in _NUMBER.finditer(work_masked):
        start, end = m.span()
        if start < consumed:
            continue
        kind, raw = m.lastgroup, m.group()
        word = _word(nfc, start, end)
        fields: dict = {}
        unit, unit_end, unrecognized = None, end, False
        if kind == "decimal" and raw.count(".") > 1:
            kind = "identifier"  # "1.2.3": versione o identificativo con punti
        if _unit_digits(work_masked, kind, start, word):
            continue  # "deg2", "km s-1" scritti senza numero: le cifre sono dell'unità (§3.2)
        if kind in ("decimal", "sci"):
            unit, unit_end, unrecognized = _unit_after(work_masked, end)
        if kind == "decimal":
            value = float(raw)
            digits = raw.lstrip("+-").replace(".", "").lstrip("0")
            exact = "." not in raw and len(digits) >= _BIGINT_DIGITS
            fields = dict(value=value, tolerance=_tolerance(value, 10.0 ** -_decimals(raw)), exact_integer=exact)
        elif kind == "sci":
            kind = "scientific"
            value, tolerance = _scientific(raw)
            fields = dict(value=value, tolerance=tolerance)
        elif kind in ("hms", "dms", "colon"):
            angles = _sexagesimal(kind, raw)
            kind = "sexagesimal"
            fields = dict(angles=angles, unit="deg", value=angles[0][0] if angles else None)
        elif kind == "ident":
            kind = "identifier"
        if unit is not None:
            fields["unit"] = unit
        consumed = unit_end
        sentence = bisect_right(starts, start) - 1
        lo = starts[sentence]
        hi = starts[sentence + 1] if sentence + 1 < len(starts) else len(work)
        cited = sorted((abs(pos - start), n) for pos, n in commands if lo <= pos < hi)
        found.append(WrittenNumber(nfc[start:end], start, end, kind, word=word, unit_unrecognized=unrecognized,
                                   cited=tuple(dict.fromkeys(n for _, n in cited)), **fields))
    return sorted(found, key=lambda n: n.start)


# --------------------------------------------------------------------------
# Indici dei valori (§3.4): uno per categoria (valori di AstroTwo, parametri, testi esterni, dati dell'utente), con
# il numero del comando su ogni voce, così ogni numero scritto si cerca una volta sola per categoria
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Hit:
    value: object
    unit: str | None
    path: str


@functools.lru_cache(maxsize=8192)
def _numbers_in(text: str) -> tuple[WrittenNumber, ...]:
    return tuple(extract_numbers(text))


class _Index:
    """Numeri con unità (R2, R3), testi (R1) e date ISO; gruppi per unità con valori ordinati. ``owner``: numero
    del comando (``None`` per i messaggi dell'utente)."""

    def __init__(self) -> None:
        self._groups: dict[object, list[tuple[float, object, str | None, str, int | None]]] = {}
        self.texts: dict[str, dict[int | None, str]] = {}
        self.datetimes: list[tuple[str, str, int | None]] = []
        self._arrays: list[tuple[object, np.ndarray, list]] | None = None

    def _text(self, text: str, path: str, owner: int | None) -> None:
        self.texts.setdefault(text, {}).setdefault(owner, path)

    def add_number(self, value: object, unit: str | None, path: str, owner: int | None) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return
        if isinstance(value, int) and abs(value) >= 2 ** 53:
            self._text(str(value), path, owner)  # interi lunghi: solo uguaglianza esatta
        key: object = None if unit is None else (_parse_unit(unit) or unit)
        self._groups.setdefault(key, []).append((float(value), value, unit, path, owner))
        self._arrays = None

    def add_datetime(self, text: str, path: str, owner: int | None) -> None:
        self.datetimes.append((text, path, owner))

    def add_text(self, text: str, path: str, owner: int | None, *, numbers: bool) -> None:
        """Una stringa: uguaglianza di testo (R1), date ISO; con ``numbers`` anche i numeri e le parole al suo
        interno (testi esterni, parametri, messaggi dell'utente)."""
        text = unicodedata.normalize("NFC", text).strip()
        if not text:
            return
        self._text(text, path, owner)
        head = text.split(" ", 1)[0]
        if _DATETIME_FULL.fullmatch(head):
            self.add_datetime(head, path, owner)
        if numbers and any(c.isdigit() for c in text):
            for word in text.split():
                self._text(word.strip(_WORD_STRIP), path, owner)
            for n in _numbers_in(text):
                self._text(n.text, path, owner)
                if n.kind == "datetime":
                    self.add_datetime(n.text, path, owner)
                elif n.kind == "sexagesimal":
                    for value, _ in n.angles:
                        self.add_number(value, "deg", path, owner)
                elif n.kind in ("decimal", "scientific") and n.value is not None:
                    self.add_number(n.value, n.unit, path, owner)

    def _frozen(self) -> list[tuple[object, np.ndarray, list]]:
        if self._arrays is None:
            self._arrays = []
            for key, items in self._groups.items():
                items = sorted(items, key=lambda t: t[0])
                self._arrays.append((key, np.array([t[0] for t in items]), items))
        return self._arrays

    def _range(self, x: float, tol: float, unit: object, hits: dict, angle: bool = False) -> None:
        """Per ogni comando il valore più vicino con ``|v′ − x| ≤ tol`` (``v′`` nell'unità scritta), tra i gruppi
        di unità confrontabili (R3)."""
        best: dict[int | None, tuple[float, tuple]] = {}
        for key, values, items in self._frozen():
            if angle:
                f = _factor(key, u.deg) if isinstance(key, u.UnitBase) else None
            elif unit is None:
                f = 1.0  # numero scritto senza unità: confronto nell'unità del valore
            elif isinstance(key, u.UnitBase) and isinstance(unit, u.UnitBase):
                f = _factor(key, unit)
            else:  # unità non riconosciute: solo se scritte uguali
                f = 1.0 if key is not None and str(key) == str(unit) else None
            if f is None:
                continue
            for target in ((x, x - 360.0, x + 360.0) if angle else (x,)):
                lo, hi = sorted(((target - tol) / f, (target + tol) / f))
                i, j = values.searchsorted(lo, "left"), values.searchsorted(hi, "right")
                for k in range(i, j):
                    d, item = abs(values[k] * f - target), items[k]
                    if item[4] not in best or d < best[item[4]][0]:
                        best[item[4]] = (d, item)
        for owner, (_, (_, raw, written_unit, path, _)) in best.items():
            hits.setdefault(owner, _Hit(raw, written_unit, path))

    def find(self, n: WrittenNumber) -> dict[int | None, _Hit]:
        """Corrispondenze per comando: prima l'uguaglianza di testo (R1), poi quella numerica (R2, R3)."""
        hits: dict[int | None, _Hit] = {}
        for text in (n.word, n.text):
            for owner, path in self.texts.get(text, {}).items():
                hits.setdefault(owner, _Hit(text, None, path))
        if n.kind in ("ambiguous", "identifier") or n.exact_integer:
            return hits
        if n.kind == "datetime":
            for text, path, owner in self.datetimes:
                if text == n.text or (text.startswith(n.text) and text[len(n.text)] in "T:.Z+- "):
                    hits.setdefault(owner, _Hit(text, None, path))
        elif n.kind == "sexagesimal":
            for value, tol in n.angles:
                self._range(value, tol, None, hits, angle=True)
        else:
            unit = None if n.unit is None else (_parse_unit(n.unit) or n.unit)
            self._range(n.value, n.tolerance, unit, hits)
        return hits


@dataclass
class _Indexes:
    own: _Index = field(default_factory=_Index)  # valori e testi di AstroTwo (verified)
    parameters: _Index = field(default_factory=_Index)  # parametri registrati (R4)
    user: _Index = field(default_factory=_Index)  # messaggi dell'utente (R5)
    external: _Index = field(default_factory=_Index)  # testi esterni (external_text)
    sources: dict[int, str] = field(default_factory=dict)


@functools.lru_cache(maxsize=4096)
def _classify(tools: ToolRegistry, command: str, path: str) -> str:
    """Classificazione del 32 (i percorsi delle righe si ripetono: una volta per percorso)."""
    return tools.classify(command, path)


class _Sink:
    """Dove va ciò che ``_walk`` trova: nei valori di un risultato le stringhe esterne (32 §3.6, nel dubbio esterne)
    vanno in ``external`` con i numeri al loro interno; le altre stringhe valgono solo per intero (R1). Nei parametri
    anche i numeri dentro i testi ("G < 10" in un'espressione è un parametro scritto)."""

    def __init__(self, indexes: _Indexes, owner: int, command: str, tools: ToolRegistry | None) -> None:
        self.indexes, self.owner, self.command, self.tools = indexes, owner, command, tools

    def _index(self) -> _Index:
        return self.indexes.own if self.tools is not None else self.indexes.parameters

    def number(self, value: object, unit: str | None, path: str) -> None:
        self._index().add_number(value, unit, path, self.owner)

    def datetime(self, text: str, path: str) -> None:
        self._index().add_datetime(text, path, self.owner)

    def text(self, text: str, path: str) -> None:
        if self.tools is None:
            self.indexes.parameters.add_text(text, path, self.owner, numbers=True)
        elif _classify(self.tools, self.command, path) != "astrotwo":
            self.indexes.external.add_text(text, path, self.owner, numbers=True)
        else:
            self.indexes.own.add_text(text, path, self.owner, numbers=False)


def _walk(sink: _Sink, value: object, path: str, unit: str | None = None) -> None:
    """Numeri e stringhe di un JSON del 05: un oggetto con ``value`` e ``unit`` dà l'unità ai suoi valori; un tempo
    del 05 (JD in due parti con la scala) dà anche il suo testo ISO 8601 (``time_text``)."""
    if isinstance(value, Mapping):
        if value.get("format") == "jd" and "scale" in value and isinstance(value.get("value"), list):
            try:
                sink.datetime(str(time_text(value)).split(" ", 1)[0], path)
            except (TypeError, ValueError, KeyError):
                pass
        own_unit = None
        if "value" in value and "unit" in value:
            own_unit = value["unit"] if isinstance(value["unit"], str) else value.get("unit_label")
        for key, item in value.items():
            if key == "sha256":
                continue
            _walk(sink, item, f"{path}.{key}", own_unit if key == "value" else None)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _walk(sink, item, f"{path}[]", unit)
    elif isinstance(value, str):
        sink.text(value, path)
    elif isinstance(value, (int, float)):
        sink.number(value, unit, path)


def _index_command(indexes: _Indexes, entry, tools: ToolRegistry, state: WorkspaceState | None) -> None:
    """Valori, provenienza, messaggi e parametri di un comando della conversazione (risultato completo del 05)."""
    result, n = entry.result, entry.number
    sink = _Sink(indexes, n, entry.command.name, tools)
    _walk(sink, result.values, "values")
    _walk(sink, result.provenance, "provenance")
    for i, message in enumerate([*result.warnings, *([result.error] if result.error else [])]):
        if message.code in ASTROTWO_MESSAGE_CODES:
            indexes.own.add_text(message.text, f"messages[{i}].text", n, numbers=False)
        else:
            indexes.external.add_text(message.text, f"messages[{i}].text", n, numbers=True)
    _walk(_Sink(indexes, n, entry.command.name, None), entry.command.parameters, "parameters")
    indexes.sources[n] = external_source(entry.command, {"provenance": result.provenance}, state)


# --------------------------------------------------------------------------
# Rapporto (§3.5)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckedNumber:
    """Un numero con il suo stato; per i numeri trovati: comando ``#n``, valore e unità corrispondenti, percorso
    nel risultato; per ``external_text`` la fonte."""

    number: WrittenNumber
    state: str
    command: int | None = None
    matched_value: object = None
    matched_unit: str | None = None
    matched_path: str | None = None
    source: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerificationIssue:
    """``VERIFY_COMMAND_UNKNOWN``, ``VERIFY_LAYER_UNKNOWN`` o ``ACTION_WITHOUT_CONFIRMATION`` (§10)."""

    code: str
    text: str
    start: int | None = None
    end: int | None = None
    command: int | None = None
    params: Mapping[str, object] = field(default_factory=dict)  # D40-3: valori JSON del messaggio


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


@dataclass(frozen=True)
class VerificationReport:
    """Esito della verifica di una risposta (§3.5): numeri con stato e posizione, problemi, riepilogo."""

    text: str  # testo normalizzato (NFC) a cui si riferiscono le posizioni
    numbers: tuple[CheckedNumber, ...]
    issues: tuple[VerificationIssue, ...] = ()
    interrupted: bool = False
    strict_retry: bool = False

    def count(self, *states: str) -> int:
        return sum(1 for n in self.numbers if n.state in states)

    @property
    def checked(self) -> int:
        """Numeri contati nel riepilogo: verificati, non verificati e ambigui."""
        return self.count("verified", "verified_other_command", "not_verified", "ambiguous")

    @property
    def unverified(self) -> tuple[CheckedNumber, ...]:
        return tuple(n for n in self.numbers if n.state in ("not_verified", "ambiguous"))

    @property
    def has_unverified(self) -> bool:
        return bool(self.unverified)

    @property
    def action_issues(self) -> tuple[VerificationIssue, ...]:
        return tuple(i for i in self.issues if i.code == "ACTION_WITHOUT_CONFIRMATION")

    @property
    def summary(self) -> str:
        """Riepilogo sotto la risposta (§3.5); gli esclusi non si contano, gli altri stati a parte."""
        m, bad = self.checked, len(self.unverified)
        if m == 0:
            text = "nessun numero da verificare"
        elif bad:
            text = f"⚠ {_plural(bad, 'numero', 'numeri')} su {m} non {'viene' if bad == 1 else 'vengono'} da un comando"
        else:
            text = f"✓ {_plural(m, 'numero', 'numeri')} su {m} {'verificato' if m == 1 else 'verificati'}"
        extra = [(self.count("user_input"), "dato in ingresso", "dati in ingresso"),
                 (self.count("command_parameter"), "parametro di un comando", "parametri di comandi"),
                 (self.count("external_text"), "da testo esterno", "da testi esterni")]
        text += "".join(f" + {_plural(n, one, many)}" for n, one, many in extra if n)
        if self.strict_retry and bad:
            text += " (modalità rigorosa: ancora non verificati)"
        if self.interrupted:
            text += " (risposta interrotta)"
        if self.action_issues:
            text += f" ⛔ {_plural(len(self.action_issues), 'comando', 'comandi')} senza la conferma dovuta"
        return text


def _layer_ids(state: WorkspaceState | None, results: Sequence) -> set[str]:
    ids = {layer.id for layer in state.layers} if state is not None else set()
    for entry in results:
        ids.update(entry.result.layers_created)
    return ids


def _action_issues(call_log: Sequence, tools: ToolRegistry) -> list[VerificationIssue]:
    """§3.7: dopo un risultato con testo esterno, ogni comando eseguito che non è di sola lettura senza rete deve
    avere la conferma dell'utente data per quel comando ("per questa conversazione" non vale)."""
    issues, after = [], False
    for outcome in call_log:
        command = getattr(outcome, "command", None)
        if command is not None and getattr(outcome, "number", None) is not None:
            spec = tools.registry.spec(command.name)
            if after and not (spec.read_only and not spec.network) and outcome.confirmed != "yes":
                issues.append(VerificationIssue(
                    "ACTION_WITHOUT_CONFIRMATION", f"#{outcome.number} {command.name}: chiesto dopo un testo esterno "
                    "senza la conferma dell'utente (errore di programmazione)", command=outcome.number,
                    params={"number": outcome.number, "command": command.name}))
        model_result = getattr(outcome, "model_result", None) or {}
        if getattr(outcome, "external_text", False) or model_result.get("contains_external_text"):
            after = True
    return issues


def verify_answer(text: str, user_messages: Sequence[str], results: Sequence, call_log: Sequence = (), *,
                  tools: ToolRegistry, state: WorkspaceState | None = None, interrupted: bool = False,
                  strict_retry: bool = False) -> VerificationReport:
    """Verifica ogni numero di ``text`` (§3.4, §3.5) e le conferme dei comandi della risposta (§3.7).

    ``results``: comandi della conversazione con ``number``, ``command`` e ``result`` completo (``HistoryEntry`` del
    05); ``call_log``: chiamate della risposta in ordine (``ToolCallOutcome`` del 32); ``state``: spazio di lavoro per
    i livelli ``L<n>`` e la fonte dei testi esterni. Le risposte precedenti dell'assistente e le regole di sistema
    non si passano: i loro numeri non contano.
    """
    numbers = extract_numbers(text)
    nfc, _ = _normalized(text)
    indexes = _Indexes()
    for entry in results:
        _index_command(indexes, entry, tools, state)
    for i, message in enumerate(user_messages):
        indexes.user.add_text(message, f"user[{i}]", None, numbers=True)
    known = set(indexes.sources)
    recent = sorted(known, reverse=True)
    layers = _layer_ids(state, results)
    checked: list[CheckedNumber] = []
    issues: list[VerificationIssue] = []
    for n in numbers:
        if n.kind == "exception":
            checked.append(CheckedNumber(n, "excluded"))
            if n.exception == "X1" and int(n.text[1:]) not in known:
                issues.append(VerificationIssue("VERIFY_COMMAND_UNKNOWN", f"comando inesistente: {n.text}", n.start,
                                                n.end, int(n.text[1:]), params={"reference": n.text}))
            elif n.exception == "X2" and n.text not in layers:
                issues.append(VerificationIssue("VERIFY_LAYER_UNKNOWN", f"livello inesistente: {n.text}", n.start,
                                                n.end, params={"layer": n.text}))
            continue
        checked.append(_check(n, indexes, recent))
    issues += _action_issues(call_log, tools)
    return VerificationReport(nfc, tuple(checked), tuple(issues), interrupted, strict_retry)


def _check(n: WrittenNumber, indexes: _Indexes, recent: Sequence[int]) -> CheckedNumber:
    """Ricerca nell'ordine di §3.4: comando citato, altri comandi (dal più recente), parametri, dati dell'utente,
    testi esterni; nessuna corrispondenza → ``not_verified`` (``ambiguous`` per le forme ambigue)."""
    notes = []
    if n.unit_unrecognized:
        notes.append("unità non riconosciuta")
    cited = [c for c in n.cited if c in indexes.sources]
    notes += [f"comando inesistente: #{c}" for c in n.cited if c not in indexes.sources]
    order = cited + [c for c in recent if c not in cited]

    def first(hits: Mapping) -> int | None:
        return next((c for c in order if c in hits), None)

    def found(state: str, number: int | None, hit: _Hit, *extra: str, source: str | None = None) -> CheckedNumber:
        return CheckedNumber(n, state, number, hit.value, hit.unit, hit.path, source, tuple(notes) + extra)

    hits = indexes.own.find(n)
    if (c := first(hits)) is not None:
        if c in cited:
            return found("verified", c, hits[c])
        return found("verified_other_command", c, hits[c], f"da #{c}")
    hits = indexes.parameters.find(n)
    if (c := first(hits)) is not None:
        return found("command_parameter", c, hits[c], f"parametro di #{c}")
    hits = indexes.user.find(n)
    if None in hits:
        return found("user_input", None, hits[None], "dato in ingresso")
    hits = indexes.external.find(n)
    if (c := first(hits)) is not None:
        return found("external_text", c, hits[c], "da testo esterno (non calcolato)", source=indexes.sources[c])
    if n.kind == "ambiguous":
        return CheckedNumber(n, "ambiguous", notes=tuple(notes) + ("formato ambiguo",))
    return CheckedNumber(n, "not_verified", notes=tuple(notes) + ("non viene da un comando",))


# --------------------------------------------------------------------------
# Modalità rigorosa (§3.6): il 35 chiede al più una rigenerazione
# --------------------------------------------------------------------------


def needs_regeneration(report: VerificationReport, *, strict: bool, regenerated: bool) -> bool:
    """Vero solo in modalità rigorosa, per la prima risposta, se ha numeri non verificati o ambigui: **mai** una
    seconda rigenerazione."""
    return strict and not regenerated and report.has_unverified


def regeneration_request(report: VerificationReport) -> str:
    """Messaggio di sistema per la rigenerazione: elenca i numeri non verificati e chiede di ottenerli con i comandi
    o di toglierli (testo per il modello, in inglese come le altre regole di sistema del 35)."""
    items = "; ".join(f"{n.number.text!r} at characters {n.number.start}-{n.number.end}" for n in report.unverified)
    return ("Strict verification: these numbers in your previous answer do not come from any command result: "
            f"{items}. Rewrite the answer: obtain each of these numbers with the commands (and cite #n), or remove "
            "it. Never compute numbers yourself.")
