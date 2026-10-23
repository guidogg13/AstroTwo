# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Pannello dell'assistente IA (interfaccia v1, parte 7).

Specifica: ``mdfiles/44-ui-pannello-ia.md`` (stato ``approvato``).

Il pannello sta nell'area a destra della finestra (40 §3.2) e mostra ciò che fa l'assistente del 35: messaggi in
Markdown semplice (nessun HTML, nessuna immagine, collegamenti come testo visibile), una scheda per ogni comando
chiesto dall'IA, le schede di conferma con i tre pulsanti, il riepilogo della verifica del 34, i token, le note dei
limiti e "Cosa è stato inviato" (JSON esatto del ``RequestRecord`` del 30). Le impostazioni dell'assistente sono
comandi ``prefs.set`` (classe ``application``); la chiave va **solo** nel Portachiavi tramite il 31 e non è mai in
un comando, in ``QSettings`` o nei log.

Il pannello non parla con il provider e non esegue comandi (35, 32, coda del 40); non calcola nulla: testi e numeri
vengono dai moduli. Gli eventi del 35 arrivano dal thread dell'assistente e passano al thread principale con un
segnale di Qt (connessione in coda), così l'interfaccia non aspetta mai l'assistente.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QPointF, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFontDatabase,
    QGuiApplication,
    QKeyEvent,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTextBrowser,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from astrotwo.ai.chat_assistant import (
    CONSENT_TEXT_VERSION,
    AssistantError,
    AssistantErrorCode,
    AssistantLimits,
    ChatAssistant,
    ConfirmationRequested,
    ConsentRecord,
    Pricing,
    ProviderNoticeEvent,
    RegenerationStarted,
    RequestSent,
    ResponseFinished,
    ResponseStarted,
    TextChunk,
    TokenCount,
    ToolCallFinished,
    ToolCallStarted,
)
from astrotwo.ai.keychain_keys import KeychainError
from astrotwo.ai.provider_adapter import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    PROVIDER_PRESETS,
    ProviderAdapterError,
    ProviderProfile,
    make_adapter,
)
from astrotwo.ai.tool_registry import ToolRegistry

__all__ = [
    "AiPanel",
    "MessageView",
    "NumberMark",
    "CommandCard",
    "ConfirmationCard",
    "SentDataDialog",
    "AssistantSettingsDialog",
    "ConsentDialog",
    "AssistantSettings",
    "ASSISTANT_DEFAULTS",
    "check_assistant_preference",
    "set_safe_markdown",
    "PANEL_WIDTH",
]

#: Larghezza di default del pannello (scelta minore 1 del 44: 400 pt, intervallo 380–420).
PANEL_WIDTH = 400

# --------------------------------------------------------------------------
# Impostazioni dell'assistente (44 §3.6): chiavi di ``QSettings`` scritte con ``prefs.set``
# --------------------------------------------------------------------------

#: Default delle impostazioni (forma testuale, come le preferenze del 40). Profili e consensi sono JSON.
ASSISTANT_DEFAULTS: dict[str, str] = {
    "assistant/profiles": "{}",
    "assistant/active": "",
    "assistant/strict": "false",
    "assistant/max_calls": "10",
    "assistant/max_minutes": "5",
    "assistant/consents": "{}",
}

_PROFILE_FIELDS = ("preset", "kind", "base_url", "model", "max_output_tokens", "max_tokens_field",
                   "price_input", "price_output", "currency")


def _profile_from_json(data: Mapping) -> ProviderProfile:
    return ProviderProfile(kind=data["kind"], base_url=data["base_url"], model=data["model"],
                           max_output_tokens=data.get("max_output_tokens", DEFAULT_MAX_OUTPUT_TOKENS),
                           preset=data.get("preset", "custom"),
                           max_tokens_field=data.get("max_tokens_field", "max_tokens"))


def _pricing_from_json(data: Mapping) -> Pricing | None:
    if data.get("price_input") is None and data.get("price_output") is None:
        return None
    return Pricing(data.get("price_input") or 0.0, data.get("price_output") or 0.0, data.get("currency") or "")


def _check_profiles(text: str) -> str:
    """Profili: oggetto JSON ``{id: campi}``; ogni voce è un ``ProviderProfile`` valido del 30 con l'``id`` uguale
    alla chiave (un profilo per endpoint, scelta minore 4 del 30) e un prezzo facoltativo (35 §3.6)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"profili: JSON non valido ({exc})") from None
    if not isinstance(data, dict):
        raise ValueError("profili: serve un oggetto JSON {id: profilo}")
    out = {}
    for key, entry in data.items():
        if not isinstance(entry, dict) or set(entry) - set(_PROFILE_FIELDS):
            raise ValueError(f"profilo {key!r}: campi ammessi {', '.join(_PROFILE_FIELDS)}")
        try:
            profile = _profile_from_json(entry)
            _pricing_from_json(entry)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"profilo {key!r}: {exc}") from None
        if profile.id != key:
            raise ValueError(f"profilo {key!r}: l'indirizzo dà l'identificativo {profile.id!r}")
        if urllib.parse.urlsplit(profile.base_url).scheme != "https" and not profile.local:
            raise ValueError(f"AI_INSECURE_ENDPOINT: {profile.base_url}: un endpoint remoto deve essere https")
        out[key] = {f: entry[f] for f in _PROFILE_FIELDS if f in entry}
    return json.dumps(out, ensure_ascii=False, sort_keys=True)


def _check_consents(text: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"consensi: JSON non valido ({exc})") from None
    if not isinstance(data, dict) or not all(
            isinstance(v, dict) and isinstance(v.get("version"), int) and isinstance(v.get("given_at"), str)
            for v in data.values()):
        raise ValueError("consensi: {profilo: {version, given_at}}")
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _check_bool(text: str) -> str:
    if text not in ("true", "false"):
        raise ValueError(f"{text!r}: true o false")
    return text


def _check_int(low: int, high: int) -> Callable[[str], str]:
    def check(text: str) -> str:
        try:
            number = int(text)
        except ValueError:
            raise ValueError(f"{text!r} non è un intero") from None
        if not low <= number <= high:
            raise ValueError(f"{number}: serve un intero tra {low} e {high}")
        return str(number)
    return check


_CHECKS: dict[str, Callable[[str], str]] = {
    "assistant/profiles": _check_profiles,
    "assistant/active": lambda text: text,
    "assistant/strict": _check_bool,
    "assistant/max_calls": _check_int(1, 100),
    "assistant/max_minutes": _check_int(1, 60),
    "assistant/consents": _check_consents,
}


def check_assistant_preference(key: str, value: str) -> str:
    """Controllo delle impostazioni dell'assistente per ``prefs.set`` (40 §3.10); ``ValueError`` se non valida."""
    return _CHECKS[key](value)


@dataclass(frozen=True)
class AssistantSettings:
    """Impostazioni lette da ``QSettings`` (mai la chiave)."""

    profiles: dict[str, dict]
    active: str
    strict: bool
    max_calls: int
    max_minutes: int
    consents: dict[str, dict]

    @classmethod
    def read(cls, value: Callable[[str], str]) -> AssistantSettings:
        return cls(json.loads(value("assistant/profiles")), value("assistant/active"),
                   value("assistant/strict") == "true", int(value("assistant/max_calls")),
                   int(value("assistant/max_minutes")), json.loads(value("assistant/consents")))

    @property
    def active_entry(self) -> dict | None:
        return self.profiles.get(self.active)

    @property
    def limits(self) -> AssistantLimits:
        return AssistantLimits(self.max_calls, self.max_minutes * 60.0)


class SettingsConsentStore:
    """Consensi per il 35 letti dalle impostazioni dell'app (35 §3.8); si scrivono con ``prefs.set`` dal pannello."""

    def __init__(self, value: Callable[[str], str]) -> None:
        self._value = value

    def get(self, profile_id: str) -> ConsentRecord | None:
        record = json.loads(self._value("assistant/consents")).get(profile_id)
        return None if record is None else ConsentRecord(record["version"], record["given_at"])

    def set(self, profile_id: str, record: ConsentRecord) -> None:  # pragma: no cover - il pannello usa prefs.set
        raise RuntimeError("il consenso si salva con prefs.set dal pannello del 44")


# --------------------------------------------------------------------------
# Markdown semplice e sicuro (44 §3.2, T12)
# --------------------------------------------------------------------------

_F = QTextDocument.MarkdownFeature
#: Dialetto GitHub (tabelle, elenchi) senza HTML: con ``MarkdownNoHTML`` i tag restano testo (verificato il
#: 2026-10-22 con Qt 6.12, md4c).
MARKDOWN_FEATURES = _F(_F.MarkdownDialectGitHub.value | _F.MarkdownNoHTML.value)
_OPEN_SCHEMES = ("http", "https")


@dataclass(frozen=True)
class NumberMark:
    """Un numero della risposta da evidenziare (44 §3.4): posizione nel testo Markdown, stato del 34, suggerimento e
    valore pieno da copiare (solo per i numeri trovati nei comandi)."""

    start: int
    end: int
    state: str
    tooltip: str
    full_value: str | None = None


#: Stile di ogni stato del 34 (44 §3.4, §3.11 punto 3); ``excluded`` non ha stile.
MARK_STYLES = {"verified": "solid", "verified_other_command": "solid", "command_parameter": "dashed",
               "user_input": "dashed", "external_text": "dashed", "not_verified": "warn", "ambiguous": "warn"}
#: Proprietà del formato con lo stato (ispezione del documento, T5).
MARK_STATE_PROPERTY = QTextFormat.Property.UserProperty + 1
_DEFAULT_MARK_COLORS = {"accent": "#0a84ff", "secondary": "#a0a2a8", "warn": "#ff453a"}
# Segni invisibili dell'area privata di Unicode attorno a ogni numero prima della conversione (§3.11 punto 1).
_START, _SEP, _END, _DIGIT0 = "\ue000", "\ue001", "\ue002", 0xE010
_MARKED = re.compile("\ue000([\ue010-\ue019]+)\ue001([^\ue000-\ue019]*)\ue002")
_MARK_CHAR = re.compile("[\ue000-\ue019]")
# Indirizzi scritti senza parentesi: un segno dentro li spezzerebbe (md4c non li riconosce più come collegamenti), i
# loro numeri si ritrovano cercando l'indirizzo nel documento.
_URL = re.compile(r"(?:https?://|www\.)[^\s<>]*")
_URL_TRAILING = ".,:;!?*_~'\""


def _url_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    for m in _URL.finditer(text):
        end = m.end()
        while end > m.start() and (text[end - 1] in _URL_TRAILING or (
                text[end - 1] == ")" and text.count("(", m.start(), end) < text.count(")", m.start(), end))):
            end -= 1
        spans.append((m.start(), end))
    return spans


def _ident(k: int) -> str:
    return "".join(chr(_DIGIT0 + int(d)) for d in str(k))


def set_safe_markdown(document: QTextDocument, text: str, image_text: str = "image not shown: %1",
                      marks: Sequence[NumberMark] = (), colors: Mapping[str, str] | None = None
                      ) -> list[tuple[int, int, NumberMark]]:
    """Markdown semplice: HTML mostrato come testo; immagini sostituite dal loro indirizzo come testo (nessun
    caricamento); collegamenti con l'indirizzo **scritto per intero** accanto al testo (nessun indirizzo nascosto).
    Nulla si apre da solo: l'apertura è un clic dell'utente (``MessageView``).

    ``marks``: numeri da evidenziare (posizioni in ``text``); restituisce le loro posizioni nel documento."""
    spans = _url_spans(text)
    pieces, last, tagged, in_urls = [], 0, [], []
    for mark in sorted(marks, key=lambda m: m.start):
        if not 0 <= last <= mark.start < mark.end <= len(text):
            continue
        span = next((k for k, (a, b) in enumerate(spans) if a <= mark.start and mark.end <= b), None)
        if span is not None:
            in_urls.append((span, mark))
            continue
        pieces += [text[last:mark.start], _START + _ident(len(tagged)) + _SEP + text[mark.start:mark.end] + _END]
        tagged.append(mark)
        last = mark.end
    pieces.append(text[last:])
    document.setMarkdown("".join(pieces), MARKDOWN_FEATURES)
    edits = []
    block = document.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            fmt = fragment.charFormat()
            if fmt.isImageFormat():
                edits.append((fragment.position(), fragment.length(), "image", fmt.toImageFormat().name()))
            elif fmt.isAnchor() and fmt.anchorHref() and fmt.anchorHref() != fragment.text():
                edits.append((fragment.position(), fragment.length(), "link", fmt.anchorHref()))
            it += 1
        block = block.next()
    cursor = QTextCursor(document)
    for position, length, kind, target in reversed(edits):
        if kind == "image":
            cursor.setPosition(position)
            cursor.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(f"[{image_text.replace('%1', target)}]", QTextCharFormat())
        else:
            cursor.setPosition(position + length)
            cursor.insertText(f" <{target}>", QTextCharFormat())
    ranges = _place_marks(document, tagged)
    ranges += _find_in_urls(document, text, spans, in_urls)
    _format_marks(document, ranges, colors or _DEFAULT_MARK_COLORS)
    return sorted(ranges, key=lambda r: r[0])


def _place_marks(document: QTextDocument, tagged: Sequence[NumberMark]) -> list[tuple[int, int, NumberMark]]:
    """Trova i segni nel documento convertito, li toglie (anche quelli rimasti soli) e dà le posizioni dei numeri."""
    deletions: list[tuple[int, int]] = []
    found: list[tuple[int, int, NumberMark]] = []
    block = document.begin()
    while block.isValid():
        text, base = block.text(), block.position()
        covered = set()
        for m in _MARKED.finditer(text):
            k = int("".join(str(ord(c) - _DIGIT0) for c in m.group(1)))
            deletions += [(base + m.start(), m.start(2) - m.start()), (base + m.end(2), 1)]
            if k < len(tagged) and m.group(2):
                found.append((base + m.start(2), len(m.group(2)), tagged[k]))
            covered.update(range(m.start(), m.end()))
        deletions += [(base + m.start(), 1) for m in _MARK_CHAR.finditer(text) if m.start() not in covered]
        block = block.next()
    cursor = QTextCursor(document)
    for position, length in sorted(deletions, reverse=True):
        cursor.setPosition(position)
        cursor.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
    out = []
    for position, length, mark in found:
        shift = sum(n for p, n in deletions if p < position)
        out.append((position - shift, position - shift + length, mark))
    return out


def _find_in_urls(document: QTextDocument, text: str, spans: Sequence[tuple[int, int]],
                  in_urls: Sequence[tuple[int, NumberMark]]) -> list[tuple[int, int, NumberMark]]:
    """Numeri dentro un indirizzo: l'indirizzo si cerca nel documento (k-esima occorrenza per il k-esimo indirizzo
    uguale del testo), il numero sta alla stessa distanza dall'inizio."""
    out = []
    flags = QTextDocument.FindFlag.FindCaseSensitively
    for span, mark in in_urls:
        a, b = spans[span]
        url = text[a:b]
        k = sum(1 for j in range(span) if text[spans[j][0]:spans[j][1]] == url)
        cursor = QTextCursor(document)
        for _ in range(k + 1):
            cursor = document.find(url, cursor, flags)
            if cursor.isNull():
                break
        if not cursor.isNull():
            start = cursor.selectionStart() + mark.start - a
            out.append((start, start + mark.end - mark.start, mark))
    return out


def _format_marks(document: QTextDocument, ranges, colors: Mapping[str, str]) -> None:
    """Stili di §3.11 punto 3: continua nell'accento, tratteggiata nel testo secondario, sfondo d'avviso."""
    cursor = QTextCursor(document)
    for start, end, mark in ranges:
        style = MARK_STYLES.get(mark.state)
        if style is None:
            continue
        fmt = QTextCharFormat()
        if style == "solid":
            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
            fmt.setUnderlineColor(QColor(colors["accent"]))
        elif style == "dashed":
            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DashUnderline)
            fmt.setUnderlineColor(QColor(colors["secondary"]))
        else:
            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
            fmt.setUnderlineColor(QColor(colors["warn"]))
            background = QColor(colors["warn"])
            background.setAlpha(77)  # 30 %
            fmt.setBackground(background)
        fmt.setToolTip(mark.tooltip)
        fmt.setProperty(MARK_STATE_PROPERTY, mark.state)
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.mergeCharFormat(fmt)


# --------------------------------------------------------------------------
# Testi dei valori (nessun calcolo: valori dei moduli scritti per intero)
# --------------------------------------------------------------------------


def _value_text(value: object) -> str:
    """Un valore di un comando come testo: quantità ``{value, unit}`` con l'unità, il resto come JSON compatto."""
    if isinstance(value, Mapping) and "value" in value and "unit" in value and len(value) <= 3:
        return f"{_value_text(value['value'])} {value['unit']}".rstrip()
    if isinstance(value, float):
        return repr(value) if math.isfinite(value) else str(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, allow_nan=True)


def _params_text(params: Mapping) -> str:
    return " · ".join(f"{k} = {_value_text(v)}" for k, v in params.items())


def _elide(text: str, limit: int = 160) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _fill(template: str, *values: str) -> str:
    """``%1``, ``%2``… sostituiti in un solo passaggio (un valore che contiene ``%2`` resta com'è)."""
    return re.sub(r"%(\d)", lambda m: values[int(m.group(1)) - 1] if 0 < int(m.group(1)) <= len(values)
                  else m.group(0), template)


# --------------------------------------------------------------------------
# Widget dei messaggi e delle schede
# --------------------------------------------------------------------------


class MessageView(QTextBrowser):
    """Testo di un messaggio (44 §3.2): altezza pari al contenuto, sola lettura, nessun collegamento aperto da solo.

    ``markdown``: Markdown semplice e sicuro (risposte); altrimenti testo semplice (messaggi dell'utente). Un clic
    su un collegamento ``http(s)`` lo apre con ``opener`` (default il browser del sistema); gli altri schemi no.
    """

    def __init__(self, text: str = "", *, markdown: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.markdown = markdown
        self.opener: Callable[[QUrl], object] = QDesktopServices.openUrl
        self.image_text = "image not shown: %1"
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.viewport().setAutoFillBackground(False)
        self.setStyleSheet("QTextBrowser { background: transparent; }")
        self.document().setDocumentMargin(0)
        self.anchorClicked.connect(self._clicked)
        self.document().documentLayout().documentSizeChanged.connect(lambda _s: self._fit())
        self.source_text = ""
        self.marks: tuple[NumberMark, ...] = ()
        self.mark_ranges: list[tuple[int, int, NumberMark]] = []
        self.mark_colors: Mapping[str, str] = _DEFAULT_MARK_COLORS
        self.copy_texts = {"value": "Copy full value", "note": "Copy note"}
        self.set_text(text)

    def set_text(self, text: str, marks: Sequence[NumberMark] | None = None) -> None:
        """Testo del messaggio; ``marks`` (posizioni in ``text``) evidenzia i numeri, ``None`` tiene quelli di prima
        (cambio di tema)."""
        self.source_text = text
        if marks is not None:
            self.marks = tuple(marks)
        if self.markdown:
            self.mark_ranges = set_safe_markdown(self.document(), text, self.image_text, self.marks,
                                                 self.mark_colors)
        else:
            self.document().setPlainText(text)
        self._fit()

    def mark_at(self, pos) -> NumberMark | None:
        """Numero evidenziato sotto il punto ``pos`` (coordinate della vista), se c'è."""
        layout = self.document().documentLayout()
        p = layout.hitTest(QPointF(pos), Qt.HitTestAccuracy.ExactHit)
        if p < 0:
            return None
        cursor = QTextCursor(self.document())
        cursor.setPosition(p)
        if pos.x() < self.cursorRect(cursor).x():
            p -= 1  # il punto è sul carattere prima della posizione del cursore
        return next((m for start, end, m in self.mark_ranges if start <= p < end), None)

    def viewportEvent(self, event) -> bool:  # noqa: N802 - nome di Qt
        if event.type() == QEvent.Type.ToolTip:
            mark = self.mark_at(event.pos())
            if mark is not None:
                QToolTip.showText(event.globalPos(), mark.tooltip, self.viewport())
            else:
                QToolTip.hideText()
            return True
        return super().viewportEvent(event)

    def mark_menu(self, pos) -> QMenu:
        """Menu del clic destro: quello del testo in sola lettura, più la copia del valore pieno e della nota del
        numero sotto il mouse (02 §6)."""
        menu = self.createStandardContextMenu(pos)
        mark = self.mark_at(pos)
        if mark is not None:
            first = menu.actions()[0] if menu.actions() else None
            if mark.full_value is not None:
                action = menu.addAction(self.copy_texts["value"])
                action.setObjectName("copyFullValue")
                action.triggered.connect(lambda: QGuiApplication.clipboard().setText(mark.full_value))
                menu.insertAction(first, action)
            note = menu.addAction(self.copy_texts["note"])
            note.setObjectName("copyNote")
            note.triggered.connect(lambda: QGuiApplication.clipboard().setText(mark.tooltip))
            menu.insertAction(first, note)
            if first is not None:
                menu.insertSeparator(first)
        return menu

    def contextMenuEvent(self, event) -> None:  # noqa: N802 - nome di Qt
        menu = self.mark_menu(event.pos())
        menu.exec(event.globalPos())
        menu.deleteLater()

    def set_dimmed(self, dimmed: bool, color: str) -> None:
        """Testo "in verifica" durante lo streaming (44 §3.4): grigio chiaro."""
        self.setStyleSheet("QTextBrowser { background: transparent; %s }" % (f"color: {color};" if dimmed else ""))

    def _clicked(self, url: QUrl) -> None:
        if url.scheme() in _OPEN_SCHEMES:
            self.opener(url)

    def _fit(self) -> None:
        width = self.viewport().width()
        if width > 0:
            self.document().setTextWidth(width)
        self.setFixedHeight(max(1, math.ceil(self.document().size().height())) + 2)

    def resizeEvent(self, event) -> None:  # noqa: N802 - nome di Qt
        super().resizeEvent(event)
        self._fit()


def _mono_font():
    from astrotwo.ui.main_window import _scaled, _tabular

    return _tabular(_scaled(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont), 0.92))


def _small(label: QLabel, factor: float = 0.88) -> QLabel:
    from astrotwo.ui.main_window import _scaled

    label.setFont(_scaled(label.font(), factor))
    return label


class CommandCard(QFrame):
    """Scheda di un comando chiesto dall'IA (44 §3.2): ``#n``, nome, parametri con unità, esito, risultato in breve,
    fonte (funzioni dei moduli; origine e data se dalla rete o dalla cache). Un clic apre la riga del pannello
    Comandi (``open_command``)."""

    open_command = Signal(int)

    def __init__(self, call_id: str, tool: str, texts: Mapping[str, str], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("commandCard")
        self.call_id, self.tool, self.texts = call_id, tool, texts
        self.number: int | None = None
        self.status = "running"
        self.head = QLabel()
        self.head.setObjectName("cardHead")
        self.head.setTextFormat(Qt.TextFormat.PlainText)
        self.head.setFont(_mono_font())
        self.params = _small(QLabel())
        self.params.setObjectName("cardParams")
        self.result = QLabel()
        self.result.setObjectName("cardResult")
        self.source = _small(QLabel(), 0.82)
        self.source.setObjectName("cardSource")
        for label in (self.head, self.params, self.result, self.source):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 0, 4)
        layout.setSpacing(2)
        for label in (self.head, self.params, self.result, self.source):
            layout.addWidget(label)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def show_started(self, command, functions: tuple[str, ...]) -> None:
        self.command_name = command.name
        self.head.setText(f"{command.name}")
        self.params.setText(_elide(_params_text(command.parameters), 240))
        self.params.setToolTip(_params_text(command.parameters))
        self.result.setText(self.texts["running"])
        self.source.setText(" · ".join(functions))

    def show_finished(self, call, functions: tuple[str, ...]) -> None:
        """Esito dal ``CallLogEntry`` del 35 (risultato completo del 05 se eseguito, errore del 32 altrimenti)."""
        self.number = call.number
        name = call.command.name if call.command is not None else call.tool
        number = f"#{call.number}  " if call.number is not None else ""
        confirmed = {"yes": self.texts["confirmed"], "conversation": self.texts["confirmed_conversation"],
                     "no": self.texts["not_confirmed"]}.get(call.confirmed or "", "")
        self.head.setText(f"{number}{name}" + (f"  · {confirmed}" if confirmed else ""))
        if call.command is not None:
            self.params.setText(_elide(_params_text(call.command.parameters), 240))
            self.params.setToolTip(_params_text(call.command.parameters))
        full = call.outcome.full_result
        if full is not None:
            self.status = full.status
            if full.status == "ok":
                values = full.values or {}
                brief = " · ".join(f"{k} = {_value_text(v)}" for k, v in list(values.items())[:4]) or "ok"
                self.result.setText("→ " + _elide(brief, 240))
                self.result.setToolTip(json.dumps(values, ensure_ascii=False, indent=1, allow_nan=True))
            elif full.error is not None:
                self.result.setText(f"{full.error.code}: {full.error.text}")
            else:
                self.result.setText(full.status)
            origins = []
            for p in full.provenance:
                parts = [str(p[k]) for k in ("origin", "retrieved_at") if p.get(k)]
                if p.get("from_cache"):
                    parts.append(self.texts["from_cache"])
                if parts:
                    origins.append(" ".join(parts))
            self.source.setText(" · ".join([*functions, *origins]))
        else:
            self.status = "not_executed"
            error = call.model_result.get("error") or {}
            self.result.setText(f"{error.get('code', call.error_code)}: {error.get('text') or error.get('message', '')}"
                                .rstrip(": "))
            self.source.setText(self.texts["not_executed"])
        self.setProperty("status", self.status)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - nome di Qt
        if self.number is not None and event.button() == Qt.MouseButton.LeftButton:
            self.open_command.emit(self.number)
        super().mousePressEvent(event)


class ConfirmationCard(QFrame):
    """Scheda di conferma (44 §3.3): comando, parametri con unità, righe massime, motivo; Conferma (predefinito),
    Annulla e "Conferma per questa conversazione" (assente dopo un testo esterno, 32 §3.6)."""

    chosen = Signal(str, str)  # call_id, scelta: yes, no, conversation

    def __init__(self, call_id: str, request: Mapping, texts: Mapping[str, str], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("confirmationCard")
        self.call_id, self.request, self.texts = call_id, dict(request), texts
        self.choice: str | None = None
        title = QLabel(texts["confirm_title"])
        title.setObjectName("confirmTitle")
        name = QLabel(request["command"])
        name.setFont(_mono_font())
        params = {k: v for k, v in request.get("parameters", {}).items() if k != "max_rows"}
        self.params = QLabel(_params_text(params))
        self.params.setObjectName("confirmParams")
        self.max_rows = QLabel(texts["max_rows"].replace("%1", _value_text(request["max_rows"]))
                               if request.get("max_rows") is not None else "")
        self.max_rows.setObjectName("confirmMaxRows")
        self.max_rows.setVisible(request.get("max_rows") is not None)
        self.reason = QLabel(self.reasons_text())
        self.reason.setObjectName("confirmReason")
        for label in (title, name, self.params, self.max_rows, self.reason):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
        self.confirm_button = QPushButton(texts["confirm"])
        self.confirm_button.setObjectName("confirmYes")
        self.confirm_button.setDefault(True)
        self.cancel_button = QPushButton(texts["cancel"])
        self.cancel_button.setObjectName("confirmNo")
        self.conversation_button: QPushButton | None = None
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.confirm_button)
        buttons.addWidget(self.cancel_button)
        self.confirm_button.clicked.connect(lambda: self._choose("yes"))
        self.cancel_button.clicked.connect(lambda: self._choose("no"))
        if request.get("conversation_allowed", True):
            self.conversation_button = QPushButton(texts["confirm_conversation"])
            self.conversation_button.setObjectName("confirmConversation")
            self.conversation_button.clicked.connect(lambda: self._choose("conversation"))
            buttons.addWidget(self.conversation_button)
        buttons.addStretch(1)
        self.state = _small(QLabel())
        self.state.setObjectName("confirmState")
        self.state.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        for w in (title, name, self.params, self.max_rows, self.reason):
            layout.addWidget(w)
        layout.addLayout(buttons)
        layout.addWidget(self.state)

    def reasons_text(self) -> str:
        names = {"network": self.texts["reason_network"], "long": self.texts["reason_long"],
                 "modifies_layer": self.texts["reason_layer"],
                 "after_external_text": self.texts["reason_external"].replace(
                     "%1", self.request.get("external_source") or "?")}
        reasons = [names.get(r, r) for r in self.request.get("reasons", ())]
        return self.texts["reason"].replace("%1", "; ".join(reasons))

    def _choose(self, choice: str) -> None:
        if self.choice is None:
            self.chosen.emit(self.call_id, choice)
            self.close_with(choice)

    def close_with(self, choice: str) -> None:
        """Scheda chiusa (scelta dell'utente, oppure Stop o fine della risposta: "non confermato")."""
        self.choice = choice
        for button in (self.confirm_button, self.cancel_button, self.conversation_button):
            if button is not None:
                button.setEnabled(False)
        self.state.setText({"yes": self.texts["confirmed"], "conversation": self.texts["confirmed_conversation"]}
                           .get(choice, self.texts["not_confirmed"]))
        self.state.show()


class _Bubble(QFrame):
    """Un messaggio: dell'utente (a destra, sfondo d'accento leggero) o dell'assistente (testo, schede, piede)."""

    def __init__(self, role: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("userBubble" if role == "user" else "assistantBubble")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(10, 8, 10, 8)
        self.layout_.setSpacing(4)


class _ComposeField(QPlainTextEdit):
    """Campo del messaggio: Invio invia, ⇧Invio va a capo (scelta minore 3 del 44)."""

    submitted = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - nome di Qt
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class _Bridge(QObject):
    """Eventi del 35 dal thread dell'assistente al thread principale (connessione in coda)."""

    event = Signal(object)


# --------------------------------------------------------------------------
# Finestre: "Cosa è stato inviato", consenso
# --------------------------------------------------------------------------


class SentDataDialog(QDialog):
    """"Cosa è stato inviato" (44 §3.5): per ogni richiesta della risposta il JSON esatto (``RequestRecord`` del
    30: corpo senza intestazioni né chiave), indirizzo e ora UTC; Copia; sola lettura."""

    def __init__(self, records, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("What was sent"))
        self.records = list(records)
        intro = QLabel(self.tr("Exact JSON of every request of this answer, without headers or key."))
        intro.setWordWrap(True)
        self.text = QPlainTextEdit()
        self.text.setObjectName("sentJson")
        self.text.setReadOnly(True)
        self.text.setFont(_mono_font())
        parts = []
        for i, record in enumerate(self.records, 1):
            parts.append(self.tr("Request %1 of %2 · %3 · %4 UTC").replace("%1", str(i))
                         .replace("%2", str(len(self.records))).replace("%3", record.url)
                         .replace("%4", record.sent_at))
            parts.append(json.dumps(record.body, ensure_ascii=False, indent=2))
        self.text.setPlainText("\n\n".join(parts))
        copy = QPushButton(self.tr("Copy"))
        copy.setObjectName("copySent")
        copy.clicked.connect(self.copy)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.addButton(copy, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.text, 1)
        layout.addWidget(buttons)
        self.resize(720, 560)

    def json_text(self) -> str:
        """Le richieste come JSON: indirizzo, ora UTC e corpo esatto."""
        return json.dumps([{"url": r.url, "sent_at": r.sent_at, "body": r.body} for r in self.records],
                          ensure_ascii=False, indent=2)

    def copy(self) -> None:
        QGuiApplication.clipboard().setText(self.json_text())


class ConsentDialog(QDialog):
    """Consenso al primo uso di un profilo (44 §3.7, 35 §3.8): cosa esce e cosa no, indirizzo del provider;
    Accetto / Non ora. Versione del testo: ``CONSENT_TEXT_VERSION`` del 35."""

    def __init__(self, profile: ProviderProfile, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Send data to the AI provider?"))
        self.setModal(True)
        sent = [self.tr("the text of the conversation"), self.tr("AstroTwo's system rules"),
                self.tr("names, descriptions and schemas of the commands the assistant can use"),
                self.tr("parameters and results of the commands asked by the model, reduced "
                        "(at most 50 rows and 20 kB)")]
        never = [self.tr("files, pixels and the content of the cache"), self.tr("API keys"),
                 self.tr("full paths (file names are sent without folders)"),
                 self.tr("the state of the workspace not asked by the model with a command")]
        text = "<p>" + self.tr("The assistant sends to <b>%1</b> (%2):").replace("%1", _html(profile.host)) \
            .replace("%2", _html(profile.base_url)) + "</p><ul>" + "".join(f"<li>{_html(s)}</li>" for s in sent) \
            + "</ul><p>" + self.tr("Never sent:") + "</p><ul>" + "".join(f"<li>{_html(s)}</li>" for s in never) \
            + "</ul><p>" + self.tr("You can see the exact JSON of every request with “What was sent”.") + "</p>"
        if profile.local:
            text += "<p>" + self.tr("This endpoint is local: nothing leaves the Mac.") + "</p>"
        self.label = QLabel(text)
        self.label.setObjectName("consentText")
        self.label.setTextFormat(Qt.TextFormat.RichText)  # testo nostro, nessun testo esterno (host escapato)
        self.label.setWordWrap(True)
        buttons = QDialogButtonBox()
        self.accept_button = buttons.addButton(self.tr("Accept"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.accept_button.setObjectName("consentAccept")
        self.later_button = buttons.addButton(self.tr("Not now"), QDialogButtonBox.ButtonRole.RejectRole)
        self.later_button.setObjectName("consentLater")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(buttons)


def _html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------
# Impostazioni dell'assistente (44 §3.6)
# --------------------------------------------------------------------------


class _TaskBridge(QObject):
    """Esiti dei lavori di rete verso il thread principale (connessione in coda). È figlio della finestra delle
    impostazioni: vive quanto lei (un oggetto dei segnali per ogni lavoro poteva essere già distrutto all'arrivo
    dell'esito, e l'esito si perdeva)."""

    done = Signal(object, object, object)  # funzione da chiamare, risultato, errore


class _Task(QRunnable):
    """Lavoro di rete delle impostazioni (elenco dei modelli, "Prova il modello") fuori dal thread principale."""

    def __init__(self, work: Callable[[], object], bridge: _TaskBridge, done: Callable[[object, object], None]) -> None:
        super().__init__()
        self.work, self.bridge, self.done = work, bridge, done

    def run(self) -> None:
        try:
            result, error = self.work(), None
        except Exception as exc:  # noqa: BLE001 - mostrato nella finestra
            result, error = None, exc
        try:
            self.bridge.done.emit(self.done, result, error)
        except RuntimeError:  # finestra già chiusa: l'esito non serve più
            pass


CUSTOM = "custom"


class AssistantSettingsDialog(QDialog):
    """Impostazioni dell'assistente (44 §3.6). Profili (campi del 30 §3.1), provider dai profili predefiniti del 30
    §3.1.1 più "Altro endpoint compatibile OpenAI…", modello da ``list_models`` o scritto, chiave mascherata nel
    Portachiavi (31; nessun comando), "Prova il modello", token in uscita, modalità rigorosa, limiti, prezzo. OK →
    un ``prefs.set`` per ogni impostazione cambiata (classe ``application``)."""

    def __init__(self, panel: AiPanel) -> None:
        super().__init__(panel.window())
        self.panel = panel
        self.setWindowTitle(self.tr("Assistant settings"))
        settings = panel.settings()
        self.profiles: dict[str, dict] = {k: dict(v) for k, v in settings.profiles.items()}
        self.order: list[str] = list(self.profiles)
        self.current: str | None = None
        self.tasks: list[_Task] = []
        self.task_bridge = _TaskBridge(self)
        self.task_bridge.done.connect(lambda done, result, error: done(result, error),
                                      Qt.ConnectionType.QueuedConnection)
        self.status_texts = {
            "documented": self.tr("tool calling declared by the provider, not tested by AstroTwo"),
            "unverified": self.tr("tool calling not declared: it may not work")}

        self.list = QListWidget()
        self.list.setObjectName("profileList")
        add = QPushButton(self.tr("Add"))
        add.setObjectName("addProfile")
        add.clicked.connect(self.add_profile)
        remove = QPushButton(self.tr("Remove"))
        remove.setObjectName("removeProfile")
        remove.clicked.connect(self.remove_profile)
        list_buttons = QHBoxLayout()
        list_buttons.addWidget(add)
        list_buttons.addWidget(remove)
        list_buttons.addStretch(1)

        self.provider = QComboBox()
        self.provider.setObjectName("provider")
        for preset in PROVIDER_PRESETS:
            self.provider.addItem(preset.provider, preset.preset)
            if preset.tool_calling != "verified":
                index = self.provider.count() - 1
                self.provider.setItemData(index, f"{self.status_texts[preset.tool_calling]} · "
                                          + " ".join(preset.sources), Qt.ItemDataRole.ToolTipRole)
        self.provider.addItem(self.tr("Other OpenAI-compatible endpoint…"), CUSTOM)
        self.badge = _small(QLabel())
        self.badge.setObjectName("providerBadge")
        self.badge.setWordWrap(True)
        self.base_url = QLineEdit()
        self.base_url.setObjectName("baseUrl")
        self.model = QComboBox()
        self.model.setObjectName("model")
        self.model.setEditable(True)
        self.model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.model.lineEdit().setPlaceholderText(self.tr("choose from the list or write the identifier"))
        refresh = QPushButton(self.tr("Refresh"))
        refresh.setObjectName("refreshModels")
        refresh.clicked.connect(self.refresh_models)
        self.models_note = _small(QLabel())
        self.models_note.setObjectName("modelsNote")
        self.models_note.setWordWrap(True)
        self.key = QLineEdit()
        self.key.setObjectName("apiKey")
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.key.setPlaceholderText(self.tr("API key (kept only in the macOS Keychain)"))
        save_key = QPushButton(self.tr("Save"))
        save_key.setObjectName("saveKey")
        save_key.clicked.connect(self.save_key)
        delete_key = QPushButton(self.tr("Delete"))
        delete_key.setObjectName("deleteKey")
        delete_key.clicked.connect(self.delete_key)
        self.key_state = _small(QLabel())
        self.key_state.setObjectName("keyState")
        self.key_state.setWordWrap(True)
        probe = QPushButton(self.tr("Test the model"))
        probe.setObjectName("probeModel")
        probe.clicked.connect(self.probe)
        self.probe_state = _small(QLabel())
        self.probe_state.setObjectName("probeState")
        self.probe_state.setWordWrap(True)
        self.max_tokens = QSpinBox()
        self.max_tokens.setObjectName("maxOutputTokens")
        self.max_tokens.setRange(1, 1_000_000)
        self.price_in = QLineEdit()
        self.price_in.setObjectName("priceInput")
        self.price_out = QLineEdit()
        self.price_out.setObjectName("priceOutput")
        self.currency = QLineEdit()
        self.currency.setObjectName("currency")
        for w, text in ((self.price_in, self.tr("input")), (self.price_out, self.tr("output")),
                        (self.currency, self.tr("currency"))):
            w.setPlaceholderText(text)
        price_note = _small(QLabel(self.tr("Optional. AstroTwo does not know the prices: the cost shown is an "
                                           "estimate with the price you enter.")))
        price_note.setWordWrap(True)

        self.strict = QCheckBox(self.tr("Strict mode (one regeneration if numbers are not verified)"))
        self.strict.setObjectName("strictMode")
        self.strict.setChecked(settings.strict)
        self.max_calls = QSpinBox()
        self.max_calls.setObjectName("maxCalls")
        self.max_calls.setRange(1, 100)
        self.max_calls.setValue(settings.max_calls)
        self.max_minutes = QSpinBox()
        self.max_minutes.setObjectName("maxMinutes")
        self.max_minutes.setRange(1, 60)
        self.max_minutes.setValue(settings.max_minutes)
        self.error = QLabel()
        self.error.setObjectName("settingsError")
        self.error.setWordWrap(True)
        self.error.setTextFormat(Qt.TextFormat.PlainText)

        form = QFormLayout()
        form.setSpacing(8)
        form.addRow(self.tr("Provider"), self.provider)
        form.addRow("", self.badge)
        form.addRow(self.tr("Endpoint address"), self.base_url)
        model_row = QHBoxLayout()
        model_row.addWidget(self.model, 1)
        model_row.addWidget(refresh)
        form.addRow(self.tr("Model"), model_row)
        form.addRow("", self.models_note)
        key_row = QHBoxLayout()
        key_row.addWidget(self.key, 1)
        key_row.addWidget(save_key)
        key_row.addWidget(delete_key)
        form.addRow(self.tr("API key"), key_row)
        form.addRow("", self.key_state)
        probe_row = QHBoxLayout()
        probe_row.addWidget(probe)
        probe_row.addWidget(self.probe_state, 1)
        form.addRow("", probe_row)
        form.addRow(self.tr("Maximum output tokens"), self.max_tokens)
        price_row = QHBoxLayout()
        for w in (self.price_in, self.price_out, self.currency):
            price_row.addWidget(w)
        form.addRow(self.tr("Price per million tokens"), price_row)
        form.addRow("", price_note)
        self.form_box = QWidget()
        self.form_box.setLayout(form)

        general = QFormLayout()
        general.setSpacing(8)
        general.addRow("", self.strict)
        general.addRow(self.tr("Commands per answer"), self.max_calls)
        general.addRow(self.tr("Minutes per answer"), self.max_minutes)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.apply)
        buttons.rejected.connect(self.reject)
        left = QVBoxLayout()
        left.addWidget(QLabel(self.tr("Profiles")))
        left.addWidget(self.list, 1)
        left.addLayout(list_buttons)
        top = QHBoxLayout()
        top.setSpacing(16)
        top.addLayout(left, 1)
        top.addWidget(self.form_box, 3)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addLayout(top)
        layout.addLayout(general)
        layout.addWidget(self.error)
        layout.addWidget(buttons)

        self.provider.currentIndexChanged.connect(self._preset_chosen)
        self.list.currentRowChanged.connect(self._select)
        self.base_url.editingFinished.connect(self._update_key_state)
        for key in self.order:
            self.list.addItem(self._title(self.profiles[key]))
        start = self.order.index(settings.active) if settings.active in self.order else (0 if self.order else -1)
        self.form_box.setEnabled(bool(self.order))
        if start >= 0:
            self.list.setCurrentRow(start)
        self.resize(820, 560)

    # --- profili ------------------------------------------------------------------------

    @staticmethod
    def _title(entry: Mapping) -> str:
        preset = next((p.provider for p in PROVIDER_PRESETS if p.preset == entry.get("preset")), None)
        host = urllib.parse.urlsplit(entry.get("base_url", "")).netloc
        return f"{preset or host} · {entry.get('model') or '—'}"

    def add_profile(self) -> None:
        self._store()
        preset = PROVIDER_PRESETS[0]
        key = f"new-{len(self.order) + 1}"
        self.profiles[key] = {"preset": preset.preset, "kind": preset.kind, "base_url": preset.base_url,
                              "model": "", "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
                              "max_tokens_field": preset.max_tokens_field}
        self.order.append(key)
        self.list.addItem(self._title(self.profiles[key]))
        self.form_box.setEnabled(True)
        self.current = None
        self.list.setCurrentRow(len(self.order) - 1)

    def remove_profile(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        key = self.order.pop(row)
        self.profiles.pop(key, None)
        self.current = None
        self.list.takeItem(row)
        self.form_box.setEnabled(bool(self.order))

    def _select(self, row: int) -> None:
        self._store()
        if row < 0 or row >= len(self.order):
            self.current = None
            return
        self.current = self.order[row]
        entry = self.profiles[self.current]
        self.provider.blockSignals(True)
        self.provider.setCurrentIndex(max(0, self.provider.findData(entry.get("preset", CUSTOM))))
        self.provider.blockSignals(False)
        self.base_url.setText(entry.get("base_url", ""))
        self.model.clear()
        self.model.setEditText(entry.get("model", ""))
        self.max_tokens.setValue(int(entry.get("max_output_tokens", DEFAULT_MAX_OUTPUT_TOKENS)))
        self.price_in.setText("" if entry.get("price_input") is None else repr(entry["price_input"]))
        self.price_out.setText("" if entry.get("price_output") is None else repr(entry["price_output"]))
        self.currency.setText(entry.get("currency") or "")
        self.models_note.clear()
        self.probe_state.clear()
        self._show_badge()
        self._update_key_state()

    def _preset_chosen(self, _index: int) -> None:
        """Provider scelto: indirizzo riempito come nel 30 §3.1.1 (modificabile); nessun modello preselezionato."""
        preset = self.provider.currentData()
        p = next((p for p in PROVIDER_PRESETS if p.preset == preset), None)
        self.base_url.setText(p.base_url if p is not None else "")
        self.model.clear()
        self.model.setEditText("")
        self._show_badge()
        self._update_key_state()

    def _show_badge(self) -> None:
        preset = self.provider.currentData()
        p = next((p for p in PROVIDER_PRESETS if p.preset == preset), None)
        status = p.tool_calling if p is not None else "unverified"
        self.badge.setText("" if status == "verified" else self.status_texts[status])
        self.badge.setToolTip("" if p is None else " ".join(p.sources))
        self.badge.setVisible(status != "verified")

    def _form_entry(self) -> dict:
        preset = self.provider.currentData()
        p = next((p for p in PROVIDER_PRESETS if p.preset == preset), None)
        entry = {"preset": preset if p is not None else CUSTOM,
                 "kind": p.kind if p is not None else "openai_compatible",
                 "base_url": self.base_url.text().strip(), "model": self.model.currentText().strip(),
                 "max_output_tokens": self.max_tokens.value(),
                 "max_tokens_field": p.max_tokens_field if p is not None else "max_tokens"}
        for name, field_ in (("price_input", self.price_in), ("price_output", self.price_out)):
            text = field_.text().strip()
            if text:
                try:
                    entry[name] = float(text)
                except ValueError:
                    entry[name] = text  # rifiutato da ``_collect`` con il messaggio
        if self.currency.text().strip():
            entry["currency"] = self.currency.text().strip()
        return entry

    def _store(self) -> None:
        if self.current is None or self.current not in self.profiles:
            return
        self.profiles[self.current] = self._form_entry()
        row = self.order.index(self.current)
        self.list.item(row).setText(self._title(self.profiles[self.current]))

    def _form_profile(self, *, need_model: bool) -> ProviderProfile:
        entry = self._form_entry()
        if not need_model and not entry["model"]:
            entry["model"] = "-"  # solo per elenco dei modelli e chiave: nessun modello nella richiesta
        return _profile_from_json(entry)

    # --- chiave (31) -------------------------------------------------------------------

    def _update_key_state(self) -> None:
        try:
            profile = self._form_profile(need_model=False)
        except ValueError as exc:
            self.key_state.setText(str(exc))
            return
        try:
            present = self.panel.keychain.has_key(profile.id)
        except KeychainError as exc:
            self.key_state.setText(f"{exc.code}: {exc.message}")
            return
        if present:
            self.key_state.setText(self.tr("A key for %1 is in the Keychain.").replace("%1", profile.id))
        elif profile.local:
            self.key_state.setText(self.tr("No key for %1: not needed by most local servers.").replace(
                "%1", profile.id))
        else:
            self.key_state.setText(self.tr("No key for %1 in the Keychain.").replace("%1", profile.id))

    def save_key(self) -> None:
        """Chiave nel Portachiavi con il 31; il campo si svuota (anche la cronologia delle modifiche); nessun
        comando registrato."""
        text = self.key.text()
        self.key.setText("")  # setText svuota anche annulla/ripeti del campo
        if not text.strip():
            return
        try:
            profile = self._form_profile(need_model=False)
            self.panel.keychain.store_key(profile.id, text)
        except ValueError as exc:
            self.key_state.setText(str(exc))
        except KeychainError as exc:
            self.key_state.setText(f"{exc.code}: {exc.message}")
        else:
            self._update_key_state()
        finally:
            del text
        self.panel.refresh()

    def delete_key(self) -> None:
        try:
            profile = self._form_profile(need_model=False)
            self.panel.keychain.delete_key(profile.id)
        except ValueError as exc:
            self.key_state.setText(str(exc))
        except KeychainError as exc:
            self.key_state.setText(f"{exc.code}: {exc.message}")
        else:
            self._update_key_state()
        self.panel.refresh()

    # --- modelli e prova (30 §3.3, §3.4), in un thread ---------------------------------

    def _run(self, work: Callable[[], object], done: Callable[[object, object], None]) -> None:
        task = _Task(work, self.task_bridge, done)
        task.setAutoDelete(False)
        self.tasks.append(task)
        QThreadPool.globalInstance().start(task)

    def refresh_models(self) -> None:
        try:
            adapter = self.panel.adapter_factory(self._form_profile(need_model=False), self.panel.keychain)
        except (ValueError, ProviderAdapterError) as exc:
            self.models_note.setText(str(exc))
            return
        self.models_note.setText(self.tr("Asking the provider for its models…"))
        self._run(adapter.list_models, self._models_listed)

    def _models_listed(self, result, error) -> None:
        if error is not None:
            self.models_note.setText(f"{getattr(error, 'code', type(error).__name__)}: "
                                     f"{getattr(error, 'message', error)}")
            return
        typed = self.model.currentText()
        self.model.clear()
        for info in result.models:
            self.model.addItem(info.id if not info.name else f"{info.id}", info.id)
            if info.name:
                self.model.setItemData(self.model.count() - 1, info.name, Qt.ItemDataRole.ToolTipRole)
        self.model.setEditText(typed)  # nessun modello preselezionato
        if result.notice is not None:
            self.models_note.setText(f"{result.notice.code}: {result.notice.message}")
        else:
            self.models_note.setText(self.tr("%1 models from the provider.").replace("%1", str(len(result.models))))

    def probe(self) -> None:
        try:
            adapter = self.panel.adapter_factory(self._form_profile(need_model=True), self.panel.keychain)
        except (ValueError, ProviderAdapterError) as exc:
            self.probe_state.setText(str(exc))
            return
        self.probe_state.setText(self.tr("Testing…"))
        self._run(adapter.probe_tools, self._probed)

    def _probed(self, result, error) -> None:
        if error is not None:
            self.probe_state.setText(f"{getattr(error, 'code', type(error).__name__)}: "
                                     f"{getattr(error, 'message', error)}")
            return
        tokens = TokenCount.of(result.usage)
        tokens_text = (self.tr("%1 input tokens, %2 output tokens").replace("%1", str(tokens.input_tokens))
                       .replace("%2", str(tokens.output_tokens)) if tokens.declared
                       else self.tr("tokens not declared by the provider"))
        if result.error is not None:
            self.probe_state.setText(f"{result.error.code}: {result.error.message}")
        elif result.tool_calling:
            self.probe_state.setText(self.tr("The model called the test tool.") + " " + tokens_text)
        else:
            self.probe_state.setText(self.tr("AI_NO_TOOLS: the model did not call the test tool.") + " "
                                     + tokens_text)

    # --- OK -------------------------------------------------------------------------------

    def _collect(self) -> tuple[dict[str, str], str]:
        """Impostazioni da salvare; ``ValueError`` con il motivo (indirizzo ``http`` remoto, modello mancante…)."""
        self._store()
        profiles: dict[str, dict] = {}
        active = ""
        for key in self.order:
            entry = self.profiles[key]
            if not entry.get("model"):
                raise ValueError(self.tr("Profile %1: choose a model.").replace("%1", self._title(entry)))
            for name in ("price_input", "price_output"):
                if name in entry and not isinstance(entry[name], float):
                    raise ValueError(self.tr("Price %1: write a number with a decimal point.").replace(
                        "%1", str(entry[name])))
            profile = _profile_from_json(entry)
            if profile.id in profiles:
                raise ValueError(self.tr("Two profiles have the same endpoint %1: one profile per endpoint.")
                                 .replace("%1", profile.id))
            profiles[profile.id] = entry
            if key == self.current:
                active = profile.id
        if not active and profiles:
            active = next(iter(profiles))
        values = {"assistant/profiles": json.dumps(profiles, ensure_ascii=False, sort_keys=True),
                  "assistant/active": active, "assistant/strict": "true" if self.strict.isChecked() else "false",
                  "assistant/max_calls": str(self.max_calls.value()),
                  "assistant/max_minutes": str(self.max_minutes.value())}
        for key, value in values.items():
            values[key] = check_assistant_preference(key, value)
        return values, active

    def apply(self) -> None:
        try:
            values, _ = self._collect()
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        for key, value in values.items():
            if value != self.panel.value(key):
                self.panel.submit("prefs.set", {"key": key, "value": value})
        self.accept()


# --------------------------------------------------------------------------
# Il pannello (44 §3.1–§3.8)
# --------------------------------------------------------------------------


class AiPanel(QWidget):
    """Pannello dell'assistente nell'area a destra (44 §3.1–§3.2).

    ``window``: la finestra del 40 (impostazioni, coda dei comandi con ``assistant_executor``, pannello Comandi).
    ``keychain``: il 31 (simulato nei test). ``adapter_factory``: ``make_adapter`` del 30 (sostituibile nei test
    con un provider simulato).
    """

    open_command = Signal(int)

    def __init__(self, window, keychain, *, adapter_factory: Callable = make_adapter) -> None:
        super().__init__()
        self.window_ = window
        self.keychain = keychain
        self.adapter_factory = adapter_factory
        self.tokens: Mapping[str, str] = {}
        self.texts = self._texts()
        self.bridge = _Bridge()
        self.bridge.event.connect(self._on_event, Qt.ConnectionType.QueuedConnection)
        self.assistant = ChatAssistant(ToolRegistry(window.registry), window.assistant_executor(), None,
                                       consents=SettingsConsentStore(self.value),
                                       language="Italian" if window.language == "it" else "English",
                                       listener=self.bridge.event.emit)
        self.adapter_error: ProviderAdapterError | None = None
        self.pending_message: str | None = None
        self.consent_dialog: ConsentDialog | None = None
        self.settings_dialog: AssistantSettingsDialog | None = None
        self.sent_dialog: SentDataDialog | None = None
        self.answers: list = []
        self._bubble: _Bubble | None = None
        self._segment: MessageView | None = None
        self._segments: list[MessageView] = []
        self._replaced_upto = 0  # blocchi della prima risposta sostituita dalla rigenerazione
        self._cards: dict[str, CommandCard] = {}
        self._confirmations: dict[str, ConfirmationCard] = {}
        self._render = QTimer(self)
        self._render.setSingleShot(True)
        self._render.setInterval(50)
        self._render.timeout.connect(self._render_segment)
        self._build()
        self.refresh()

    # --- testi tradotti ----------------------------------------------------------------

    def _texts(self) -> dict[str, str]:
        return {
            "running": self.tr("running…"), "confirmed": self.tr("confirmed by the user"),
            "confirmed_conversation": self.tr("confirmed for this conversation"),
            "not_confirmed": self.tr("not confirmed"), "not_executed": self.tr("not executed"),
            "from_cache": self.tr("from the cache"), "confirm_title": self.tr("The assistant asks to run:"),
            "max_rows": self.tr("at most %1 rows"), "reason": self.tr("Confirmation needed: %1"),
            "reason_network": self.tr("uses the network"), "reason_long": self.tr("long command"),
            "reason_layer": self.tr("changes a layer"),
            "reason_external": self.tr("asked after reading external text (%1)"),
            "confirm": self.tr("Confirm"), "cancel": self.tr("Cancel"),
            "confirm_conversation": self.tr("Confirm for this conversation")}

    # --- costruzione ---------------------------------------------------------------------

    def _build(self) -> None:
        self.setObjectName("aiPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # fondo del tema dal foglio di stile
        self.profile_label = QLabel()
        self.profile_label.setObjectName("aiProfile")
        self.profile_label.setTextFormat(Qt.TextFormat.PlainText)
        self.lock = QLabel()
        self.lock.setObjectName("aiLock")
        self.local_badge = _small(QLabel(self.tr("local · nothing leaves the Mac")))
        self.local_badge.setObjectName("aiLocal")
        self.new_button = QToolButton()
        self.new_button.setObjectName("aiNew")
        self.new_button.setToolTip(self.tr("New conversation"))
        self.new_button.clicked.connect(self.new_conversation)
        self.settings_button = QToolButton()
        self.settings_button.setObjectName("aiSettings")
        self.settings_button.setToolTip(self.tr("Assistant settings"))
        self.settings_button.clicked.connect(self.open_settings)
        header = QHBoxLayout()
        header.setContentsMargins(12, 8, 8, 4)
        header.setSpacing(4)
        header.addWidget(self.profile_label, 1)
        header.addWidget(self.lock)
        header.addWidget(self.new_button)
        header.addWidget(self.settings_button)
        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(12, 0, 12, 0)
        badge_row.setSpacing(4)
        self.local_icon = QLabel()
        badge_row.addWidget(self.local_icon)
        badge_row.addWidget(self.local_badge)
        badge_row.addStretch(1)

        self.privacy = _small(QLabel(self.tr(
            "The provider receives the text and the results of the commands; never files, pixels, keys or "
            "folders.")), 0.85)
        self.privacy.setObjectName("aiPrivacy")
        self.privacy.setWordWrap(True)
        self.privacy_detail = QToolButton()
        self.privacy_detail.setObjectName("aiPrivacyDetail")
        self.privacy_detail.setText(self.tr("Details"))
        self.privacy_detail.setAutoRaise(True)
        self.privacy_detail.clicked.connect(self.show_privacy)
        privacy_row = QHBoxLayout()
        privacy_row.setContentsMargins(12, 4, 12, 8)
        privacy_row.setSpacing(4)
        self.privacy_icon = QLabel()
        privacy_row.addWidget(self.privacy_icon, 0, Qt.AlignmentFlag.AlignTop)
        privacy_row.addWidget(self.privacy, 1)
        privacy_row.addWidget(self.privacy_detail, 0, Qt.AlignmentFlag.AlignTop)
        line = QFrame()
        line.setObjectName("aiLine")
        line.setFrameShape(QFrame.Shape.HLine)

        self.messages = QWidget()
        self.messages.setObjectName("aiMessages")
        self.messages_layout = QVBoxLayout(self.messages)
        self.messages_layout.setContentsMargins(12, 8, 12, 8)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch(1)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("aiScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.messages)
        self.scroll.verticalScrollBar().rangeChanged.connect(
            lambda _lo, hi: self.scroll.verticalScrollBar().setValue(hi))

        self.input = _ComposeField()
        self.input.setObjectName("aiInput")
        self.input.setPlaceholderText(self.tr("Ask the assistant…"))
        self.input.setFixedHeight(64)
        self.input.submitted.connect(self.send_or_stop)
        self.send_button = QPushButton(self.tr("Send"))
        self.send_button.setObjectName("aiSend")
        self.send_button.setDefault(True)
        self.send_button.clicked.connect(self.send_or_stop)
        compose = QWidget()
        compose_layout = QHBoxLayout(compose)
        compose_layout.setContentsMargins(12, 8, 12, 12)
        compose_layout.setSpacing(8)
        compose_layout.addWidget(self.input, 1)
        compose_layout.addWidget(self.send_button, 0, Qt.AlignmentFlag.AlignBottom)

        self.unavailable = QLabel()
        self.unavailable.setObjectName("aiUnavailable")
        self.unavailable.setWordWrap(True)
        self.unavailable.setTextFormat(Qt.TextFormat.PlainText)
        self.fix_button = QPushButton()
        self.fix_button.setObjectName("aiFix")
        self.fix_button.clicked.connect(self._fix)
        blocked = QWidget()
        blocked_layout = QVBoxLayout(blocked)
        blocked_layout.setContentsMargins(12, 8, 12, 12)
        blocked_layout.setSpacing(8)
        blocked_layout.addWidget(self.unavailable)
        blocked_layout.addWidget(self.fix_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.bottom = QStackedWidget()
        self.bottom.addWidget(compose)
        self.bottom.addWidget(blocked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addLayout(badge_row)
        layout.addLayout(privacy_row)
        layout.addWidget(line)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.bottom)

    # --- impostazioni -------------------------------------------------------------------

    def value(self, key: str) -> str:
        """Impostazione dell'assistente da ``QSettings`` (default se assente o non valida)."""
        raw = self.window_.settings.value(key, ASSISTANT_DEFAULTS[key])
        try:
            return check_assistant_preference(key, str(raw))
        except ValueError:
            return ASSISTANT_DEFAULTS[key]

    def settings(self) -> AssistantSettings:
        return AssistantSettings.read(self.value)

    def submit(self, name: str, params: Mapping) -> int:
        return self.window_.submit(name, params, source="mouse")

    def refresh(self) -> None:
        """Profilo, limiti, modalità rigorosa e prezzo dalle impostazioni; intestazione e disponibilità."""
        settings = self.settings()
        entry = settings.active_entry
        assistant = self.assistant
        if not assistant.busy:
            self.adapter_error = None
            adapter = None
            if entry is not None:
                try:
                    adapter = self.adapter_factory(_profile_from_json(entry), self.keychain)
                except ProviderAdapterError as exc:
                    self.adapter_error = exc
                except ValueError as exc:
                    self.adapter_error = ProviderAdapterError("AI_NO_PROFILE", str(exc))
            current = assistant.adapter
            if adapter is None or current is None or adapter.profile != current.profile:
                assistant.set_adapter(adapter)
            assistant.limits = settings.limits
            assistant.strict = settings.strict
            assistant.pricing = _pricing_from_json(entry) if entry is not None else None
        self._show_header(entry)
        self._show_availability()

    def settings_changed(self, key: str) -> None:
        """Un ``prefs.set`` dell'assistente applicato dalla finestra (thread principale)."""
        self.refresh()
        if key == "assistant/consents" and self.pending_message is not None and self.available().available:
            message, self.pending_message = self.pending_message, None
            self._start(message)

    def _show_header(self, entry: Mapping | None) -> None:
        profile = self.assistant.adapter.profile if self.assistant.adapter is not None else None
        if profile is None:
            self.profile_label.setText(self.tr("No profile"))
            self.lock.setToolTip("")
            self.local_badge.hide()
            self.local_icon.hide()
            self.lock.hide()
            return
        provider = next((p.provider for p in PROVIDER_PRESETS if p.preset == profile.preset), profile.host)
        self.profile_label.setText(f"{provider} · {profile.model}")
        self.profile_label.setToolTip(f"{profile.id} · {profile.base_url}")
        self.local_badge.setVisible(profile.local)
        self.local_icon.setVisible(profile.local)
        try:
            present = self.keychain.has_key(profile.id)
        except KeychainError:
            present = None
        self.key_present = present
        self.lock.show()
        self.lock.setToolTip(self.tr("key in the Keychain") if present else self.tr("no key in the Keychain"))
        self._lock_icon()

    def _lock_icon(self) -> None:
        if not self.tokens or not self.lock.isVisible():
            return
        from astrotwo.ui.main_window import themed_icon

        name = "lock" if getattr(self, "key_present", False) else "lock-open"
        self.lock.setPixmap(themed_icon(name, self.tokens).pixmap(16, 16))

    # --- disponibilità (44 §3.8, 35 §3.7) ---------------------------------------------

    def available(self):
        from astrotwo.ai.chat_assistant import Availability

        if self.adapter_error is not None:
            return Availability(False, self.adapter_error.code, self.adapter_error.message)
        return self.assistant.availability()

    def _reason_text(self, availability) -> str:
        profile = self.assistant.adapter.profile if self.assistant.adapter is not None else None
        code = availability.code
        if code == AssistantErrorCode.NO_PROFILE:
            reason = self.tr("no profile configured")
        elif code == "KEY_NOT_FOUND":
            reason = self.tr("no key in the Keychain for %1").replace("%1", profile.id if profile else "?")
        elif code in ("KEYCHAIN_UNAVAILABLE", "KEYCHAIN_ACCESS_DENIED"):
            reason = self.tr("Keychain not available (%1)").replace("%1", code)
        elif code == "AI_NO_TOOLS":
            reason = self.tr("the model %1 does not call tools").replace("%1", profile.model if profile else "?")
        elif code == AssistantErrorCode.CONSENT_REQUIRED:
            reason = self.tr("consent to send data to %1 not given").replace("%1", profile.host if profile else "?")
        else:
            reason = f"{code}: {availability.reason}"
        return self.tr("The assistant is not available: %1. The rest of AstroTwo works normally.").replace(
            "%1", reason)

    def _show_availability(self, *, consent_refused: bool = False) -> None:
        availability = self.available()
        # Senza consenso il campo resta: il primo messaggio apre la finestra del consenso (44 §3.7).
        consent_only = availability.code == AssistantErrorCode.CONSENT_REQUIRED and not consent_refused
        if availability.available or consent_only:
            self.bottom.setCurrentIndex(0)
            return
        self.blocked_code = availability.code
        self.unavailable.setText(self._reason_text(availability))
        self.fix_button.setText(self.tr("Give consent…") if availability.code == AssistantErrorCode.CONSENT_REQUIRED
                                else self.tr("Open assistant settings…"))
        self.bottom.setCurrentIndex(1)

    def _fix(self) -> None:
        if getattr(self, "blocked_code", None) == AssistantErrorCode.CONSENT_REQUIRED:
            self.ask_consent()
        else:
            self.open_settings()

    # --- finestre -------------------------------------------------------------------------

    def open_settings(self) -> AssistantSettingsDialog:
        dialog = AssistantSettingsDialog(self)
        dialog.finished.connect(lambda _r: self.refresh())
        self.settings_dialog = dialog
        dialog.open()
        return dialog

    def show_privacy(self) -> None:
        if self.assistant.adapter is not None:
            dialog = ConsentDialog(self.assistant.adapter.profile, self)
            dialog.accept_button.hide()
            dialog.later_button.setText(self.tr("Close"))
            dialog.open()

    def ask_consent(self) -> ConsentDialog | None:
        """Finestra modale del consenso (44 §3.7); Accetto → ``prefs.set`` dei consensi con versione e data."""
        if self.assistant.adapter is None:
            return None
        profile = self.assistant.adapter.profile
        dialog = ConsentDialog(profile, self)
        dialog.accepted.connect(lambda: self._consent_given(profile.id))
        dialog.rejected.connect(self._consent_refused)
        self.consent_dialog = dialog
        dialog.open()
        return dialog

    def _consent_given(self, profile_id: str) -> None:
        from datetime import UTC, datetime

        consents = json.loads(self.value("assistant/consents"))
        consents[profile_id] = {"version": CONSENT_TEXT_VERSION, "given_at": datetime.now(UTC).isoformat()}
        self.submit("prefs.set", {"key": "assistant/consents",
                                  "value": json.dumps(consents, ensure_ascii=False, sort_keys=True)})

    def _consent_refused(self) -> None:
        self.pending_message = None
        self._show_availability(consent_refused=True)

    def show_sent(self, answer) -> SentDataDialog:
        dialog = SentDataDialog(answer.requests, self)
        self.sent_dialog = dialog
        dialog.open()
        return dialog

    # --- invio, Stop, nuova conversazione ------------------------------------------------

    @property
    def busy(self) -> bool:
        return self.assistant.busy

    def send_or_stop(self) -> None:
        if self.assistant.busy:
            self.stop()
        else:
            self.send(self.input.toPlainText())

    def send(self, text: str) -> bool:
        """Invia il messaggio; senza consenso prima la finestra del consenso (nulla esce prima di Accetto)."""
        if not text.strip() or self.assistant.busy:
            return False
        self.refresh()
        availability = self.available()
        if availability.code == AssistantErrorCode.CONSENT_REQUIRED:
            self.pending_message = text
            self.input.clear()
            self._user_bubble(text)
            self.ask_consent()
            return False
        if not availability.available:
            self._show_availability()
            return False
        self.input.clear()
        self._user_bubble(text)
        return self._start(text)

    def _start(self, text: str) -> bool:
        try:
            self.assistant.send(text)
        except AssistantError as exc:
            self._error_line(f"{exc.code}: {exc.message}")
            self._show_availability()
            return False
        self._set_busy(True)
        return True

    def stop(self) -> None:
        self.assistant.stop()

    def new_conversation(self) -> None:
        if self.assistant.busy:
            return
        self.assistant.new_conversation()
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.answers.clear()

    def _set_busy(self, busy: bool) -> None:
        self.send_button.setText(self.tr("Stop") if busy else self.tr("Send"))
        self.send_button.setObjectName("aiStop" if busy else "aiSend")
        self.new_button.setEnabled(not busy)
        self._icons()

    # --- messaggi ----------------------------------------------------------------------

    def _add(self, widget: QWidget, *, right: bool = False) -> None:
        row = QHBoxLayout()
        if right:
            row.addStretch(1)
        row.addWidget(widget, 6 if right else 1)
        holder = QWidget()
        holder.setLayout(row)
        row.setContentsMargins(0, 0, 0, 0)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, holder)

    def _user_bubble(self, text: str) -> None:
        bubble = _Bubble("user")
        view = MessageView(text, markdown=False)
        view.setObjectName("userText")
        bubble.layout_.addWidget(view)
        self._add(bubble, right=True)

    def _error_line(self, text: str) -> QLabel:
        label = _small(QLabel(text))
        label.setObjectName("aiError")
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        if self._bubble is not None and self.assistant.busy:
            self._bubble.layout_.addWidget(label)
        else:
            self._add(label)
        return label

    def _new_segment(self) -> MessageView:
        view = MessageView("")
        view.setObjectName("assistantText")
        view.image_text = self.tr("image not shown: %1")
        view.mark_colors = self._mark_colors()
        view.copy_texts = {"value": self.tr("Copy full value"), "note": self.tr("Copy note")}
        view.set_dimmed(True, self.tokens.get("text3", "#808080"))
        self._bubble.layout_.addWidget(view)
        self._segments.append(view)
        self._segment = view
        return view

    def _render_segment(self) -> None:
        if self._segment is not None:
            self._segment.set_text(self._segment.pending)

    # --- eventi del 35 (thread principale) ---------------------------------------------

    def _on_event(self, event: object) -> None:
        if isinstance(event, ResponseStarted):
            self._bubble = _Bubble("assistant")
            self._segment = None
            self._segments = []
            self._replaced_upto = 0
            self._add(self._bubble)
        elif self._bubble is None:
            return
        elif isinstance(event, TextChunk):
            if self._segment is None:
                self._new_segment().pending = ""
            self._segment.pending += event.text
            if not self._render.isActive():
                self._render.start()
        elif isinstance(event, ToolCallStarted):
            card = self._card(event.call_id, event.tool)
            card.show_started(event.command, self._functions(event.command.name))
        elif isinstance(event, ConfirmationRequested):
            self._flush()
            card = ConfirmationCard(event.call_id, event.request, self.texts)
            card.chosen.connect(self.assistant.confirm)
            self._confirmations[event.call_id] = card
            self._bubble.layout_.addWidget(card)
        elif isinstance(event, ToolCallFinished):
            call = event.call
            card = self._card(call.call_id, call.tool)
            name = call.command.name if call.command is not None else None
            card.show_finished(call, self._functions(name) if name else ())
        elif isinstance(event, ProviderNoticeEvent):
            self._note(event.text)
        elif isinstance(event, RegenerationStarted):
            self._flush()
            self._replaced_upto = len(self._segments)
            for view in self._segments:
                view.set_dimmed(True, self.tokens.get("text3", "#808080"))
            self._note(self.tr("Strict mode: some numbers are not verified, the answer is being regenerated "
                               "once. The text above is replaced by the one below."))
        elif isinstance(event, RequestSent):
            pass  # le richieste sono nell'``AnswerRecord`` di fine risposta ("Cosa è stato inviato")
        elif isinstance(event, ResponseFinished):
            self._finish(event.answer)

    def _flush(self) -> None:
        """Il testo arrivato finora si disegna; il testo successivo va in un nuovo blocco sotto la scheda."""
        self._render.stop()
        self._render_segment()
        self._segment = None

    def _card(self, call_id: str, tool: str) -> CommandCard:
        card = self._cards.get(call_id)
        if card is None:
            self._flush()
            card = CommandCard(call_id, tool, self.texts)
            card.open_command.connect(self.open_command)
            self._cards[call_id] = card
            self._bubble.layout_.addWidget(card)
        return card

    def _functions(self, name: str) -> tuple[str, ...]:
        try:
            module = self.tr("module %1")
            return tuple(module.replace("%1", f) for f in self.window_.registry.spec(name).functions)
        except Exception:  # noqa: BLE001 - nome sconosciuto
            return ()

    def _note(self, text: str) -> QLabel:
        label = _small(QLabel(text))
        label.setObjectName("aiNote")
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        self._bubble.layout_.addWidget(label)
        return label

    def _finish(self, answer) -> None:
        self._flush()
        for card in self._confirmations.values():
            if card.choice is None:
                card.close_with("no")
        self._confirmations.clear()
        for view in self._segments:
            view.set_dimmed(False, "")
        if answer.regenerated:
            for view in self._segments[:self._replaced_upto]:
                view.set_dimmed(True, self.tokens.get("text3", "#808080"))
            self._show_marks(self._segments[:self._replaced_upto], answer.replaced[0][1])
        if answer.report is not None:
            self._show_marks(self._segments[self._replaced_upto:], answer.report)
        self.answers.append(answer)
        footer = QWidget()
        footer.setObjectName("answerFooter")
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)
        if answer.error is not None:
            error = _small(QLabel(f"{answer.error.code}: {answer.error.message}"))
            error.setObjectName("aiError")
            error.setWordWrap(True)
            layout.addWidget(error)
            if answer.error.code == "AI_CONTEXT_TOO_LONG":
                again = QPushButton(self.tr("New conversation"))
                again.clicked.connect(self.new_conversation)
                layout.addWidget(again, 0, Qt.AlignmentFlag.AlignLeft)
        if answer.report is not None:
            summary = _small(QLabel(self.summary_text(answer.report)))
            summary.setObjectName("verifySummary")
            summary.setWordWrap(True)
            summary.setProperty("warn", answer.report.has_unverified or bool(answer.report.action_issues))
            layout.addWidget(summary)
            for issue in answer.report.action_issues:
                line = _small(QLabel(f"{issue.code}: {issue.text}"))
                line.setObjectName("aiError")
                line.setWordWrap(True)
                layout.addWidget(line)
        for note in answer.notes:
            label = _small(QLabel(self.note_text(note)))
            label.setObjectName("aiLimitNote")
            label.setWordWrap(True)
            layout.addWidget(label)
        tokens = _small(QLabel(self.tokens_text(answer)), 0.82)
        tokens.setObjectName("aiTokens")
        tokens.setWordWrap(True)
        layout.addWidget(tokens)
        sent = QToolButton()
        sent.setObjectName("aiWhatSent")
        sent.setText(self.tr("What was sent"))
        sent.setAutoRaise(True)
        sent.setEnabled(bool(answer.requests))
        sent.clicked.connect(lambda: self.show_sent(answer))
        layout.addWidget(sent, 0, Qt.AlignmentFlag.AlignLeft)
        self._bubble.layout_.addWidget(footer)
        self._bubble = None
        self._segment = None
        self._cards = {}
        self._set_busy(False)
        self._show_availability()

    # --- numeri evidenziati (44 §3.4, §3.11) ---------------------------------------------

    def _show_marks(self, views: Sequence[MessageView], report) -> None:
        """Ogni numero del rapporto del 34 nel suo blocco di testo, con lo stile e il suggerimento del suo stato.

        Il testo verificato è l'unione dei blocchi; se non coincide (normalizzazione NFC al confine di due blocchi) si
        mostra intero nel primo, così nessun numero resta senza stile (§3.11 punto 2)."""
        if not views:
            return
        texts = [unicodedata.normalize("NFC", v.source_text) for v in views]
        if "".join(texts) != report.text:
            texts = [report.text] + [""] * (len(views) - 1)
        offset = 0
        for view, text in zip(views, texts, strict=True):
            marks = []
            for n in report.numbers:
                start, end = max(n.number.start, offset), min(n.number.end, offset + len(text))
                if n.state in MARK_STYLES and start < end:
                    tooltip, full = self.number_tooltip(n)
                    marks.append(NumberMark(start - offset, end - offset, n.state, tooltip, full))
            view.set_text(text, marks)
            offset += len(text)

    def number_tooltip(self, n) -> tuple[str, str | None]:
        """Suggerimento di un numero (§3.11 punto 4) e valore pieno con unità da copiare (numeri dei comandi)."""
        full = None
        if n.state in ("verified", "verified_other_command", "command_parameter") and n.matched_value is not None:
            value = n.matched_value.item() if hasattr(n.matched_value, "item") else n.matched_value
            full = _value_text(value) + (f" {n.matched_unit}" if n.matched_unit else "")
        functions = " · ".join(self._functions_of(n.command)) if n.command is not None else ""
        number = str(n.command) if n.command is not None else "?"
        if n.state == "verified":
            text = _fill(self.tr("Verified: %1 · command #%2"), full or "", number)
        elif n.state == "verified_other_command":
            text = _fill(self.tr("Verified with another command: %1 · command #%2"), full or "", number)
        elif n.state == "command_parameter":
            text = _fill(self.tr("Parameter of command #%1: %2"), number, full or "")
        elif n.state == "user_input":
            text = self.tr("From your message")
        elif n.state == "external_text":
            text = _fill(self.tr("From external text, not computed (%1)"), n.source or "?")
        elif n.state == "ambiguous":
            text = self.tr("Ambiguous format")
        else:
            text = self.tr("Does not come from a command")
        if functions and n.state in ("verified", "verified_other_command"):  # solo i valori calcolati dal modulo
            text += " · " + functions
        if n.number.unit_unrecognized:
            text += " · " + self.tr("unit not recognized")
        for note in n.notes:
            missing = re.fullmatch(r"comando inesistente: #(\d+)", note)  # nota del 34
            if missing:
                text += " · " + _fill(self.tr("command does not exist: #%1"), missing.group(1))
        return text, full

    def _functions_of(self, number: int) -> tuple[str, ...]:
        entries = self.window_.session.history.entries
        return self._functions(entries[number - 1].command.name) if 0 < number <= len(entries) else ()

    def _mark_colors(self) -> dict[str, str]:
        t = self.tokens
        if not t:
            return dict(_DEFAULT_MARK_COLORS)
        return {"accent": t["focus"], "secondary": t["text2"], "warn": t["error"]}

    # --- testi sotto la risposta (traduzione del 44 dei testi del 34 e del 35) -----------

    def summary_text(self, report) -> str:
        """Riepilogo della verifica del 34 (§3.5 del 34) nella lingua dell'interfaccia."""
        m, bad = report.checked, len(report.unverified)
        if m == 0:
            text = self.tr("no number to verify")
        elif bad:
            text = "⚠ " + self.tr("%1 of %2 numbers do not come from a command").replace("%1", str(bad)) \
                .replace("%2", str(m))
        else:
            text = "✓ " + self.tr("%1 of %2 numbers verified").replace("%1", str(m)).replace("%2", str(m))
        for state, label in (("user_input", self.tr("from your message")),
                             ("command_parameter", self.tr("command parameters")),
                             ("external_text", self.tr("from external text"))):
            n = report.count(state)
            if n:
                text += f" + {n} {label}"
        if report.strict_retry and bad:
            text += " " + self.tr("(strict mode: still not verified)")
        if report.interrupted:
            text += " " + self.tr("(answer interrupted)")
        if report.action_issues:
            text += " ⛔ " + self.tr("%1 commands without the required confirmation").replace(
                "%1", str(len(report.action_issues)))
        return text

    def note_text(self, note) -> str:
        limits = self.assistant.limits
        if note.code == AssistantErrorCode.TOOL_LIMIT:
            return self.tr("limit of %1 commands reached").replace("%1", str(limits.max_calls))
        if note.code == AssistantErrorCode.TIME_LIMIT:
            return self.tr("limit of %1 minutes reached").replace("%1", f"{limits.max_seconds / 60:g}")
        if note.code == AssistantErrorCode.CANCELLED:
            return self.tr("answer interrupted")
        return f"{note.code}: {note.text}"

    def tokens_text(self, answer) -> str:
        def count(tokens: TokenCount) -> str:
            if not tokens.declared:
                return self.tr("tokens not declared by the provider")
            return self.tr("%1 input tokens, %2 output tokens").replace("%1", str(tokens.input_tokens)) \
                .replace("%2", str(tokens.output_tokens))

        text = self.tr("This answer: %1").replace("%1", count(answer.tokens))
        if answer.cost is not None:
            text += " · " + self.tr("%1 %2, estimate with the price you entered").replace(
                "%1", repr(answer.cost.value)).replace("%2", answer.cost.currency)
        conversation = next((c for c in self.assistant.conversations if c.id == answer.conversation), None)
        if conversation is not None:
            text += " · " + self.tr("conversation: %1").replace("%1", count(conversation.tokens))
        return text

    # --- aspetto (40 §3.11) ---------------------------------------------------------------

    def set_theme(self, tokens: Mapping[str, str]) -> None:
        """Colori del tema: messaggi distinti per allineamento e sfondo leggero; in modalità notte solo rossi."""
        self.tokens = tokens
        t = tokens
        self.setStyleSheet(f"""
            #aiPanel {{ background: {t['panel']}; }}
            #aiMessages {{ background: {t['panel']}; }}
            #aiPrivacy, #aiLocal, #aiTokens, #cardSource, #aiNote {{ color: {t['text3']}; }}
            #aiLine {{ color: {t['line_soft']}; }}
            #userBubble {{ background: {t['accent_soft']}; border: 1px solid {t['focus']}; border-radius: 10px; }}
            #assistantBubble {{ background: {t['chrome']}; border: 1px solid {t['line']}; border-radius: 10px; }}
            #commandCard {{ border: none; border-left: 2px solid {t['line']}; }}
            #commandCard[status="error"], #commandCard[status="not_executed"] {{ border-left: 2px solid {t['error']}; }}
            #cardParams {{ color: {t['text3']}; }}
            #confirmationCard {{ border: 1px solid {t['focus']}; border-radius: 8px; }}
            #aiError {{ color: {t['error']}; }}
            #verifySummary[warn="true"] {{ color: {t['error']}; }}
            #aiLimitNote {{ color: {t['text2']}; }}
        """)
        self._icons()
        self._lock_icon()
        # Qt scrive il colore dei collegamenti nel documento quando converte il Markdown: si riconverte con la
        # tavolozza nuova (in modalità notte solo rossi).
        colors = self._mark_colors()
        for view in self.messages.findChildren(MessageView):
            view.mark_colors = colors
            if view.markdown:
                view.set_text(view.source_text)

    def _icons(self) -> None:
        if not self.tokens:
            return
        from astrotwo.ui.main_window import themed_icon

        self.new_button.setIcon(themed_icon("message-square-plus", self.tokens))
        self.settings_button.setIcon(themed_icon("settings", self.tokens))
        self.privacy_icon.setPixmap(themed_icon("shield", self.tokens).pixmap(14, 14))
        self.local_icon.setPixmap(themed_icon("laptop", self.tokens).pixmap(14, 14))
        self.send_button.setIcon(themed_icon("square" if self.assistant.busy else "send", self.tokens))
