"""Finestra principale (interfaccia v1): menu, barra di stato, campo "Vai a", pannelli, preferenze.

Specifica: ``mdfiles/40-ui-finestra-principale.md`` (stato ``approvato``).

Ogni azione dell'utente diventa un comando del registro del 05 (regola d'oro n. 6) ed entra in **una coda**
eseguita da un thread di lavoro (``CommandRunner`` in un ``QThread``, §3.8): uno alla volta, nell'ordine di
arrivo; i risultati tornano al thread principale con i segnali di Qt. La finestra **non calcola nulla**:
mostra valori, codici e testi dei moduli invariati (§4, D40-1).

Il visualizzatore del cielo (41), la tabella (42) e il pannello dell'assistente (44) sono parti successive
della v1: qui la finestra riserva il loro spazio con uno stato vuoto che dice cosa arriverà.

Aspetto (§3.11, mockup in ``mdfiles/mockup/``): tavolozza e foglio di stile dai colori del tema, icone Lucide
(``ui/icons/``, licenza ISC in ``ui/icons/LICENSE``) disegnate con QtSvg nel colore del tema.
"""

from __future__ import annotations

import functools
import itertools
import json
import sys
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import (
    QByteArray,
    QCoreApplication,
    QEvent,
    QLibraryInfo,
    QLocale,
    QObject,
    QRunnable,
    QSettings,
    QSize,
    Qt,
    QThread,
    QThreadPool,
    QTimer,
    QTranslator,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QKeySequence,
    QPainter,
    QPalette,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import astrotwo
from astrotwo.core.cache import DEFAULT_LIMIT_BYTES, NETWORK_TIMEOUTS, SharedCache
from astrotwo.core.commands import (
    Command,
    CommandError,
    CommandRegistry,
    CommandResult,
    HistoryEntry,
    Outcome,
    ProgressReport,
    ReplayReport,
    RequestedBy,
    ResultMessage,
    Session,
    SESSION_EXTENSION,
    CancelToken,
    default_registry,
)

__all__ = [
    "MainWindow",
    "CommandRunner",
    "StatusBar",
    "HistoryPanel",
    "MessagesPanel",
    "GoToField",
    "PreferencesDialog",
    "EmptyState",
    "load_translations",
    "themed_icon",
    "apply_appearance",
    "PREFERENCES",
    "main",
]

# --------------------------------------------------------------------------
# Preferenze essenziali (§3.10), pannelli e strumenti
# --------------------------------------------------------------------------

#: Elenco chiuso delle coppie frame/formato del menu "Coordinates shown" (§3.3) e della preferenza (§3.10).
COORDINATE_DISPLAYS: dict[str, tuple[str, str]] = {
    "icrs_sexagesimal": ("icrs", "sexagesimal"),
    "icrs_decimal": ("icrs", "decimal"),
    "galactic": ("galactic", "decimal"),
}
LANGUAGES = ("system", "en", "it")
APPEARANCES = ("system", "dark", "light", "night")
PANELS = ("layers", "table", "commands", "messages", "assistant")
TOOLS = ("none", "distance", "simbad_pointer")
DEFAULT_SURVEY = "CDS/P/DSS2/color"  # D12-3 (default del 12, hips.DEFAULT_SURVEY)


def _choice(choices: tuple[str, ...]) -> Callable[[str], str]:
    def check(text: str) -> str:
        if text not in choices:
            raise ValueError(f"valore {text!r} non in {choices}")
        return text
    return check


def _positive_bytes(text: str) -> str:
    try:
        number = int(text)
    except ValueError:
        raise ValueError(f"{text!r} non è un numero intero di byte") from None
    if number <= 0:
        raise ValueError(f"limite della cache {number} byte: serve un intero positivo")
    return str(number)


def _survey(text: str) -> str:
    if not text.strip():
        raise ValueError("identificativo del survey vuoto")
    return text.strip()


@dataclass(frozen=True)
class Preference:
    key: str
    default: str
    check: Callable[[str], str]


#: Le cinque preferenze di §3.10: chiave in ``QSettings`` → default (forma testuale) e controllo.
PREFERENCES: dict[str, Preference] = {p.key: p for p in (
    Preference("language", "system", _choice(LANGUAGES)),
    Preference("cache/limit_bytes", str(DEFAULT_LIMIT_BYTES), _positive_bytes),
    Preference("view/coordinates", "icrs_sexagesimal", _choice(tuple(COORDINATE_DISPLAYS))),
    Preference("hips/default_survey", DEFAULT_SURVEY, _survey),
    Preference("appearance", "system", _choice(APPEARANCES)),
)}


def _check_preference(key: str, value: str) -> str:
    """Valore valido nella forma testuale, oppure ``PREFERENCE_INVALID`` (§10)."""
    pref = PREFERENCES.get(key)
    if pref is None:
        raise CommandError("PREFERENCE_INVALID", f"preferenza {key!r} sconosciuta ({', '.join(PREFERENCES)})")
    try:
        return pref.check(value)
    except ValueError as exc:
        raise CommandError("PREFERENCE_INVALID", f"{key}: {exc}; resta il valore precedente") from None


# --------------------------------------------------------------------------
# Esecuzione dei comandi dell'interfaccia (bound_by = "40")
# --------------------------------------------------------------------------
# Gli esecutori girano nel thread di lavoro: controllano i valori e li restituiscono; l'effetto (impostazioni,
# pannelli, aspetto) lo applica la finestra nel thread principale quando il comando è ``ok``.


def _exec_prefs_set(ctx, p: Mapping) -> Outcome:
    return Outcome(values={"key": p["key"], "value": _check_preference(p["key"], p["value"])})


def _closed(name: str, choices: tuple[str, ...]):
    def run(ctx, p: Mapping) -> Outcome:
        if p[name] not in choices:
            raise CommandError("COMMAND_PARAMETER_INVALID", f"{name}: {p[name]!r} non in {choices}")
        return Outcome(values=dict(p))
    return run


def _exec_plain(ctx, p: Mapping) -> Outcome:
    return Outcome(values=dict(p))


BOUND_EXECUTORS: dict[str, Callable] = {
    "prefs.set": _exec_prefs_set,
    "ui.set_tool": _closed("tool", TOOLS),
    "ui.set_panel": _closed("panel", PANELS),
    "ui.set_fullscreen": _exec_plain,
    "ui.set_appearance": _exec_plain,
}


# --------------------------------------------------------------------------
# Cache del 04 da più thread (una istanza per thread, D04) con il limite della preferenza
# --------------------------------------------------------------------------


class ThreadCache:
    """Accesso alla ``SharedCache`` del 04 con una istanza per thread (la connessione ``sqlite3`` è legata al
    thread che la crea) e il limite della preferenza (CA2); ogni attributo è quello della cache del thread."""

    def __init__(self, limit_bytes: int = DEFAULT_LIMIT_BYTES, root=None) -> None:
        self.limit_bytes = limit_bytes
        self._root = root
        self._local = threading.local()

    def _cache(self) -> SharedCache:
        cache = getattr(self._local, "cache", None)
        if cache is None:
            cache = self._local.cache = SharedCache(self._root, limit_bytes=self.limit_bytes)
        cache.limit_bytes = self.limit_bytes
        return cache

    def __getattr__(self, name: str):
        return getattr(self._cache(), name)


# --------------------------------------------------------------------------
# Coda dei comandi nel thread di lavoro (§3.8)
# --------------------------------------------------------------------------


@dataclass
class CommandJob:
    id: int
    command: Command
    cancel: CancelToken = field(default_factory=CancelToken)
    network: bool = False


@dataclass
class ReplayJob:
    id: int
    path: str
    cancel: CancelToken = field(default_factory=CancelToken)
    network: bool = False


@dataclass(frozen=True)
class CommandDone:
    """Ritorno di un comando: comando chiesto, comando registrato, risultato, voce della cronologia."""

    job_id: int
    command: Command
    registered: Command
    result: CommandResult
    entry: HistoryEntry | None


@dataclass(frozen=True)
class ReplayDone:
    """Ritorno della riapertura di una sessione: sessione nuova e rapporto del 05, oppure l'errore del 05."""

    job_id: int
    path: str
    session: Session | None
    report: ReplayReport | None
    error: ResultMessage | None = None


class CommandRunner(QObject):
    """Oggetto nel thread di lavoro: esegue i comandi in coda con il registro del 05, uno alla volta.

    Il thread principale non esegue mai un comando della coda (§3.8): manda i lavori con un segnale
    (connessione in coda) e riceve ``started``, ``progress``, ``finished`` e ``replayed``.
    """

    started = Signal(int, str)
    progress = Signal(int, object)  # ProgressReport
    finished = Signal(object)  # CommandDone
    replayed = Signal(object)  # ReplayDone

    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session  # usata e sostituita solo nel thread di lavoro dopo la creazione

    @Slot(object)
    def run_job(self, job) -> None:
        if isinstance(job, ReplayJob):
            self._replay(job)
        else:
            self._run(job)

    def _run(self, job: CommandJob) -> None:
        session = self.session
        self.started.emit(job.id, job.command.name)
        try:
            registered, result = session.registry.run(job.command, session.workspace, job.cancel,
                                                      lambda r: self.progress.emit(job.id, r))
        except Exception as exc:  # noqa: BLE001 - il thread di lavoro non si ferma mai (§10 del 40)
            registered = job.command
            result = CommandResult("error", error=ResultMessage("UI_COMMAND_FAILED", f"{type(exc).__name__}: {exc}"))
        try:
            spec = session.registry.spec(registered.name)
        except CommandError:
            entry = None
        else:
            entry = session.history.record(spec, registered, result)
        self.finished.emit(CommandDone(job.id, job.command, registered, result, entry))

    def _replay(self, job: ReplayJob) -> None:
        registry = self.session.registry
        self.started.emit(job.id, "session.open")
        try:
            loaded = Session.load(job.path, registry)
            report = loaded.replay(cancel=job.cancel, progress=lambda r: self.progress.emit(job.id, r))
        except CommandError as exc:
            self.replayed.emit(ReplayDone(job.id, job.path, None, None, ResultMessage(exc.code, exc.message)))
            return
        if report.status != "cancelled":  # annullata: si scarta, resta la sessione di prima (§3.8)
            self.session = loaded
        self.replayed.emit(ReplayDone(job.id, job.path, loaded if report.status != "cancelled" else None, report))


# --------------------------------------------------------------------------
# Aspetto (§3.11): sistema, scuro (di riferimento), chiaro, notte rossa
# --------------------------------------------------------------------------

# Ruoli della tavolozza di Qt e, per il foglio di stile, i colori dei mockup (``mdfiles/mockup/``): ``chrome``
# barre, ``panel`` pannelli, ``line_soft`` righe e intestazioni, ``accent_soft`` selezione ed elementi attivi,
# ``focus`` accento pieno (bordi, avanzamento, icone attive), ``sky_*`` fondo e testi dell'area del cielo.
_DARK = {"window": "#1c1d21", "base": "#18191c", "alternate": "#141518", "text": "#e6e6e8", "text2": "#a0a2a8",
         "text3": "#6c6f76", "button": "#232428", "line": "#2a2c31", "accent": "#0a84ff", "on_accent": "#ffffff",
         "error": "#ff453a", "shadow": "#000000",
         "chrome": "#1c1d21", "panel": "#18191c", "line_soft": "#232428", "accent_soft": "rgba(10, 132, 255, 46)",
         "focus": "#0a84ff", "sky_top": "#05070c", "sky_bottom": "#0a0d16", "sky_text": "#a0a2a8",
         "sky_text3": "#6c6f76"}
_LIGHT = {"window": "#ececec", "base": "#ffffff", "alternate": "#f5f5f7", "text": "#1d1d1f", "text2": "#515154",
          "text3": "#8e8e93", "button": "#f5f5f7", "line": "#d1d1d6", "accent": "#007aff", "on_accent": "#ffffff",
          "error": "#ff3b30", "shadow": "#8e8e93",
          "chrome": "#ececec", "panel": "#ffffff", "line_soft": "#e5e5ea", "accent_soft": "rgba(0, 122, 255, 36)",
          "focus": "#007aff", "sky_top": "#05070c", "sky_bottom": "#0a0d16", "sky_text": "#a0a2a8",
          "sky_text3": "#6c6f76"}  # il cielo resta scuro anche nel tema chiaro
#: Notte rossa: solo toni di rosso a bassa luminosità, nessun bianco né blu (dai mockup del 2026-10-15).
_NIGHT = {"window": "#0e0101", "base": "#0c0101", "alternate": "#0a0000", "text": "#d23a2a", "text2": "#9a2a1e",
          "text3": "#6a1d15", "button": "#1d0404", "line": "#2a0606", "accent": "#5a0f0a", "on_accent": "#ff3b2f",
          "error": "#ff3b2f", "shadow": "#000000",
          "chrome": "#0e0101", "panel": "#0c0101", "line_soft": "#1d0404", "accent_soft": "rgba(255, 59, 47, 41)",
          "focus": "#ff3b2f", "sky_top": "#000000", "sky_bottom": "#050000", "sky_text": "#9a2a1e",
          "sky_text3": "#6a1d15"}
_TOKENS = {"dark": _DARK, "light": _LIGHT, "night": _NIGHT}


def _palette(tokens: Mapping[str, str]) -> QPalette:
    """Tavolozza con **tutti** i ruoli in tutti i gruppi (nessun colore lasciato al default dello stile)."""
    c = {k: QColor(v) for k, v in tokens.items() if v.startswith("#")}
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: c["window"], QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["base"], QPalette.ColorRole.AlternateBase: c["alternate"],
        QPalette.ColorRole.ToolTipBase: c["window"], QPalette.ColorRole.ToolTipText: c["text"],
        QPalette.ColorRole.PlaceholderText: c["text3"], QPalette.ColorRole.Text: c["text"],
        QPalette.ColorRole.Button: c["button"], QPalette.ColorRole.ButtonText: c["text"],
        QPalette.ColorRole.BrightText: c["error"], QPalette.ColorRole.Light: c["line"],
        QPalette.ColorRole.Midlight: c["line"], QPalette.ColorRole.Mid: c["line"],
        QPalette.ColorRole.Dark: c["alternate"], QPalette.ColorRole.Shadow: c["shadow"],
        QPalette.ColorRole.Highlight: c["accent"], QPalette.ColorRole.HighlightedText: c["on_accent"],
        QPalette.ColorRole.Link: c["accent"] if tokens is not _NIGHT else c["on_accent"],
        QPalette.ColorRole.LinkVisited: c["text2"], QPalette.ColorRole.Accent: c["accent"],
    }
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled):
        for role, color in roles.items():
            pal.setColor(group, role, color)
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText,
                 QPalette.ColorRole.HighlightedText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, c["text3"])
    return pal


def _system_color_scheme() -> Qt.ColorScheme:
    """Modalità chiaro/scuro dichiarata dal sistema (``QStyleHints.colorScheme``, Qt ≥ 6.5)."""
    return QApplication.styleHints().colorScheme()


def _stylesheet(t: Mapping[str, str], *, native_toolbar: bool) -> str:
    """Foglio di stile dei pannelli, delle barre e degli stati vuoti dai colori del tema (mockup, §3.11).

    Margini e distanze sulla griglia di 4 punti; i controlli (pulsanti, menu a tendina, caselle) restano quelli
    dello stile. Con lo stile nativo di macOS la barra degli strumenti non ha fondo proprio: resta unita alla
    barra del titolo (§3.11). Nessuna dimensione del carattere qui: la danno i font di sistema (accessibilità).
    """
    toolbar = "" if native_toolbar else f"""
QToolBar#mainToolbar {{ background: {t['chrome']}; border: none; border-bottom: 1px solid {t['line']}; }}"""
    return f"""{toolbar}
QToolBar#mainToolbar {{ padding: 4px 8px; spacing: 4px; }}
QToolBar#mainToolbar::separator {{ background: {t['line']}; width: 1px; margin: 4px 4px; }}
QToolBar#mainToolbar QToolButton {{ border: none; border-radius: 6px; padding: 4px 6px; }}
QToolBar#mainToolbar QToolButton:hover {{ background: {t['line_soft']}; }}
QToolBar#mainToolbar QToolButton:checked {{ background: {t['accent_soft']}; }}
QLineEdit#goToField {{ background: {t['alternate']}; color: {t['text']}; border: 1px solid {t['line']};
    border-radius: 6px; padding: 2px 8px; selection-background-color: {t['accent_soft']};
    selection-color: {t['text']}; }}
QLineEdit#goToField:focus {{ border: 1px solid {t['focus']}; }}
QMainWindow::separator {{ background: {t['line']}; width: 1px; height: 1px; }}
QMainWindow > QTabBar {{ background: {t['panel']}; }}
QMainWindow > QTabBar::tab {{ background: transparent; color: {t['text3']}; border: none; border-radius: 6px;
    padding: 4px 12px; margin: 4px 2px; }}
QMainWindow > QTabBar::tab:selected {{ background: {t['line_soft']}; color: {t['text']}; }}
QMainWindow > QTabBar::tab:hover:!selected {{ color: {t['text2']}; }}
QWidget#dockHeader {{ background: {t['panel']}; border-bottom: 1px solid {t['line_soft']}; }}
QLabel#dockTitle {{ color: {t['text3']}; }}
QWidget#dockHeader QToolButton {{ border: none; border-radius: 4px; padding: 2px; }}
QWidget#dockHeader QToolButton:hover {{ background: {t['line_soft']}; }}
QWidget[panel="true"] {{ background: {t['panel']}; }}
QTableView {{ background: {t['panel']}; color: {t['text']}; border: none; gridline-color: {t['line_soft']};
    selection-background-color: {t['accent_soft']}; selection-color: {t['text']}; }}
QTableView::item {{ padding: 0px 8px; border-bottom: 1px solid {t['line_soft']}; }}
QHeaderView::section {{ background: {t['panel']}; color: {t['text2']}; border: none;
    border-bottom: 1px solid {t['line_soft']}; padding: 4px 8px; }}
QTableCornerButton::section {{ background: {t['panel']}; border: none; }}
QSplitter::handle {{ background: {t['line_soft']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QPlainTextEdit#historyDetail {{ background: {t['alternate']}; color: {t['text2']}; border: none;
    border-left: 1px solid {t['line_soft']}; padding: 8px; }}
#skyArea {{ background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {t['sky_top']},
    stop: 1 {t['sky_bottom']}); }}
QWidget#emptyState {{ background: {t['panel']}; }}
QLabel#emptyTitle {{ color: {t['text2']}; }}
QLabel#emptyText {{ color: {t['text3']}; }}
QLabel#surveyLabel {{ color: {t['text2']}; }}
QStatusBar {{ background: {t['chrome']}; border-top: 1px solid {t['line']}; color: {t['text2']}; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {t['text2']}; padding: 0px 4px; }}
QPushButton#cancelCommand {{ background: transparent; color: {t['text']}; border: 1px solid {t['line']};
    border-radius: 5px; padding: 1px 8px; }}
QPushButton#cancelCommand:hover {{ background: {t['line_soft']}; }}
QStatusBar QProgressBar {{ background: {t['line']}; border: none; border-radius: 2px; }}
QStatusBar QProgressBar::chunk {{ background: {t['focus']}; border-radius: 2px; }}
"""


# --------------------------------------------------------------------------
# Icone (§3.11): raccolta Lucide (ISC, ``ui/icons/LICENSE``), disegnate con QtSvg nel colore del tema
# --------------------------------------------------------------------------

ICONS_DIR = Path(__file__).resolve().parent / "icons"
ICON_SIZE = 16  # punti; le immagini si disegnano anche al doppio per gli schermi Retina


@functools.lru_cache(maxsize=None)
def _icon_svg(name: str) -> str:
    return (ICONS_DIR / f"{name}.svg").read_text(encoding="utf-8")


def _icon_pixmap(name: str, color: str, size: int) -> QPixmap:
    """L'icona ``name`` di Lucide a ``size`` pixel, con i tratti (``currentColor``) nel colore dato."""
    renderer = QSvgRenderer(QByteArray(_icon_svg(name).replace("currentColor", color).encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def themed_icon(name: str, tokens: Mapping[str, str], size: int = ICON_SIZE) -> QIcon:
    """Icona nel colore del tema: normale ``text2``, attiva (spuntata) ``focus``, disattivata ``text3``.

    In modalità notte i tre colori sono toni di rosso (§3.11).
    """
    icon = QIcon()
    for scale in (1, 2):
        px = size * scale
        icon.addPixmap(_icon_pixmap(name, tokens["text2"], px), QIcon.Mode.Normal, QIcon.State.Off)
        icon.addPixmap(_icon_pixmap(name, tokens["focus"], px), QIcon.Mode.Normal, QIcon.State.On)
        icon.addPixmap(_icon_pixmap(name, tokens["text3"], px), QIcon.Mode.Disabled, QIcon.State.Off)
        icon.addPixmap(_icon_pixmap(name, tokens["text3"], px), QIcon.Mode.Disabled, QIcon.State.On)
    return icon


_BASE_STYLE: list[str] = []  # stile nativo dell'app all'avvio ("macOS" sul Mac)


def apply_appearance(mode: str, app: QApplication | None = None) -> str:
    """Applica l'aspetto (§3.11) e restituisce quello effettivo: ``dark``, ``light`` o ``night``.

    Con lo stile nativo di macOS il chiaro/scuro passa da ``QStyleHints.setColorScheme`` (controlli nativi);
    con gli altri stili (es. piattaforma ``offscreen`` dei test) si usa la tavolozza del tema. La notte rossa usa
    lo stile Fusion con la tavolozza rossa (lo stile nativo non accetta colori propri). Senza una preferenza del
    sistema vale il tema scuro, quello di riferimento.
    """
    if mode not in APPEARANCES:
        raise ValueError(f"aspetto {mode!r} non in {APPEARANCES}")
    app = QApplication.instance() if app is None else app
    hints = app.styleHints()
    if not _BASE_STYLE:
        _BASE_STYLE.append(app.style().name())
    base = _BASE_STYLE[0]
    if mode == "night":
        effective = "night"
        hints.setColorScheme(Qt.ColorScheme.Dark)
        if app.style().name().lower() != "fusion":
            app.setStyle("Fusion")
        app.setPalette(_palette(_NIGHT))
        app.setStyleSheet(_stylesheet(_NIGHT, native_toolbar=False))
        return effective
    if app.style().name() != base:
        app.setStyle(base)
    if mode == "system":
        hints.unsetColorScheme()
        scheme = _system_color_scheme()
        effective = "light" if scheme == Qt.ColorScheme.Light else "dark"
        if scheme == Qt.ColorScheme.Unknown:
            hints.setColorScheme(Qt.ColorScheme.Dark)
    else:
        effective = mode
        hints.setColorScheme(Qt.ColorScheme.Dark if mode == "dark" else Qt.ColorScheme.Light)
    native = base.lower() == "macos"
    if native:
        app.setPalette(app.style().standardPalette())
    else:
        app.setPalette(_palette(_TOKENS[effective]))
    app.setStyleSheet(_stylesheet(_TOKENS[effective], native_toolbar=native))
    return effective


def _tabular(font: QFont) -> QFont:
    """Cifre a larghezza fissa (funzione OpenType ``tnum``) per coordinate e valori (§3.11)."""
    font = QFont(font)
    font.setFeature(QFont.Tag("tnum"), 1)
    return font


def _scaled(font: QFont, factor: float) -> QFont:
    """Carattere in proporzione a quello di sistema (segue le impostazioni di accessibilità, §3.11)."""
    font = QFont(font)
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() * factor)
    return font


def _header_font(font: QFont) -> QFont:
    """Intestazione dei pannelli del mockup: piccola, semigrassetto, maiuscole spaziate."""
    font = _scaled(font, 0.85)
    font.setWeight(QFont.Weight.DemiBold)
    font.setCapitalization(QFont.Capitalization.AllUppercase)
    font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 104)
    return font


# --------------------------------------------------------------------------
# Lingua (A9, §3.9)
# --------------------------------------------------------------------------

I18N_DIR = Path(__file__).resolve().parent / "i18n"
_TRANSLATORS: list[QTranslator] = []


def load_translations(language: str, app: QCoreApplication | None = None) -> tuple[str, list[ResultMessage]]:
    """Carica la traduzione nostra (``i18n/astrotwo_it.qm``) e quella di Qt (``qtbase_it``) per i dialoghi.

    ``language``: ``system`` (dalla ``QLocale`` del sistema), ``en`` o ``it``. Restituisce la lingua usata e gli
    avvisi: senza file di traduzione resta l'inglese con ``UI_TRANSLATION_MISSING`` (§10).
    """
    if language not in LANGUAGES:
        raise ValueError(f"lingua {language!r} non in {LANGUAGES}")
    app = QCoreApplication.instance() if app is None else app
    for old in _TRANSLATORS:
        app.removeTranslator(old)
    _TRANSLATORS.clear()
    if language == "system":
        language = "it" if QLocale.system().language() == QLocale.Language.Italian else "en"
    if language == "en":
        return "en", []
    warnings = []
    ours = QTranslator()
    path = I18N_DIR / "astrotwo_it.qm"
    if path.is_file() and ours.load(str(path)):
        app.installTranslator(ours)
        _TRANSLATORS.append(ours)
    else:
        warnings.append(ResultMessage("UI_TRANSLATION_MISSING", f"traduzione italiana {path} mancante o "
                                      "illeggibile: interfaccia in inglese"))
        language = "en"
    qt = QTranslator()
    qt_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt.load("qtbase_it", qt_dir):
        app.installTranslator(qt)
        _TRANSLATORS.append(qt)
    else:
        warnings.append(ResultMessage("UI_TRANSLATION_MISSING", f"traduzione di Qt qtbase_it non trovata in "
                                      f"{qt_dir}: dialoghi standard in inglese"))
    return language, warnings


def _json_text(value: object) -> str:
    """Valori dei moduli come testo JSON: punto decimale in ogni lingua (§3.9), numeri invariati."""
    return json.dumps(value, ensure_ascii=False, allow_nan=True)


def _who(requested_by: RequestedBy) -> str:
    if requested_by.source == "ai":
        return QCoreApplication.translate("HistoryPanel", "AI")
    if requested_by.source == "session":
        return QCoreApplication.translate("HistoryPanel", "Session")
    return QCoreApplication.translate("HistoryPanel", "User")


# --------------------------------------------------------------------------
# Pannelli e barra di stato
# --------------------------------------------------------------------------


class EmptyState(QWidget):
    """Stato vuoto di un pannello o di uno spazio riservato: icona, titolo e un testo che dice cosa arriverà."""

    def __init__(self, icon: str, title: str, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.icon_name = icon
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("emptyTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont(self.title_label.font())
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title_label.setFont(title_font)
        self.text_label = QLabel(text)
        self.text_label.setObjectName("emptyText")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setWordWrap(True)
        self.text_label.setFont(_scaled(self.text_label.font(), 0.92))
        body = QWidget()
        body.setMaximumWidth(420)
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        for w in (self.icon_label, self.title_label, self.text_label):
            column.addWidget(w)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(body, 100)
        row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(2)

    def text(self) -> str:
        return f"{self.title_label.text()}\n{self.text_label.text()}"

    def cover(self, host: QWidget) -> None:
        """Sovrapposto a ``host`` (una tabella vuota) con la sua stessa forma, fuori dalla disposizione: mostrarlo o
        nasconderlo non cambia le misure dei pannelli né della vista."""
        self.setParent(host)
        host.installEventFilter(self)
        self.setGeometry(host.rect())
        self.raise_()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - nome di Qt
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return False

    def set_theme(self, tokens: Mapping[str, str], *, on_sky: bool = False) -> None:
        color = tokens["sky_text3"] if on_sky else tokens["text3"]
        self.icon_label.setPixmap(themed_icon(self.icon_name, {**tokens, "text2": color}, 32).pixmap(32, 32))


def _as_panel(widget: QWidget) -> QWidget:
    """Fondo dei pannelli dal foglio di stile (le sottoclassi di ``QWidget`` lo disegnano solo con questo
    attributo)."""
    widget.setProperty("panel", True)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return widget


ROW_HEIGHT = 24  # stessa altezza di riga in tutti i pannelli (§3.11, griglia di 4 punti)


def _style_table(table: QTableWidget) -> None:
    """Tabelle dei pannelli come nel mockup: righe di 24 punti, nessuna griglia, cifre tabulari."""
    table.setFont(_tabular(_scaled(table.font(), 0.92)))
    table.setShowGrid(False)
    table.setFrameShape(QFrame.Shape.NoFrame)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


class GoToField(QLineEdit):
    """Campo "Vai a" (§3.4): un nome di oggetto o una coppia di coordinate; Invio → ``view.go_to``."""

    goTo = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("goToField")
        self.setPlaceholderText(self.tr("Go to: object name or coordinates"))
        self.setClearButtonEnabled(True)
        self.setMinimumWidth(280)
        self.setMaximumWidth(420)
        self.setFont(_tabular(self.font()))
        self.search_icon = self.addAction(QIcon(), QLineEdit.ActionPosition.LeadingPosition)
        self.returnPressed.connect(self._go)

    def _go(self) -> None:
        text = self.text().strip()
        if text:
            self.goTo.emit(text)


class StatusBar(QStatusBar):
    """Barra di stato di una riga (§3.5): sotto il mouse, attività di rete, comando in corso con Annulla."""

    cancelRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.setContentsMargins(8, 0, 8, 0)
        font = _tabular(_scaled(self.font(), 0.92))
        self.cursor_label = QLabel(self.tr("No data"))
        self.network_label = QLabel()
        self.command_label = QLabel()
        for label in (self.cursor_label, self.network_label, self.command_label):
            label.setFont(font)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedSize(90, 4)
        self.progress_bar.setTextVisible(False)
        self.cancel_button = QPushButton(self.tr("Cancel"))
        self.cancel_button.setObjectName("cancelCommand")
        self.cancel_button.setFont(font)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self.cancelRequested)
        self.addWidget(self.cursor_label, 1)
        for w in (self.network_label, self.command_label, self.progress_bar, self.cancel_button):
            self.addPermanentWidget(w)
        # Altezza fissa del mockup (26 px): mostrare Annulla e l'avanzamento non ridimensiona il cielo (41), che
        # a ogni nuova dimensione registra la nuova finestra.
        self.setFixedHeight(26)
        self.show_network(0, 0)
        self.show_idle()

    def show_cursor(self, result: CommandResult | None) -> None:
        """Valori di ``cursor.read`` (41) come li dà il modulo; "fuori dal cielo"/"nessun dato" senza valore."""
        if result is None or result.status != "ok":
            self.cursor_label.setText(self.tr("No data"))
            return
        values = result.values
        if values.get("sky") is None:
            self.cursor_label.setText(self.tr("Outside the sky"))
            return
        sky = values["sky"]
        parts = [f"{sky['frame']} {_json_text(sky['lon'])} {_json_text(sky['lat'])}"]
        pixel = values.get("pixel")
        if pixel is None:
            parts.append(self.tr("no data"))
        else:
            unit = pixel.get("unit") or pixel.get("unit_label") or ""
            parts.append(f"{_json_text(pixel['value'])} {unit}".strip())
            if pixel.get("fits") is not None:
                parts.append(f"FITS ({pixel['fits']['x']}, {pixel['fits']['y']})")
        self.cursor_label.setText("  ·  ".join(parts))

    def show_network(self, commands: int, tiles: int) -> None:
        self.network_label.setText(self.tr("Network: %1 commands, %2 tiles").replace("%1", str(commands))
                                   .replace("%2", str(tiles)))

    def show_running(self, name: str, report: ProgressReport | None = None) -> None:
        if report is not None and report.total:
            self.progress_bar.setRange(0, report.total)
            self.progress_bar.setValue(report.step)
            step = self.tr("step %1 of %2").replace("%1", str(report.step)).replace("%2", str(report.total))
            self.command_label.setText(f"{name} · {step}")
        else:
            self.progress_bar.setRange(0, 0)  # indeterminato
            self.command_label.setText(name)
        for w in (self.command_label, self.progress_bar, self.cancel_button):
            w.setVisible(True)

    def show_idle(self) -> None:
        self.command_label.clear()
        for w in (self.command_label, self.progress_bar, self.cancel_button):
            w.setVisible(False)


class HistoryPanel(QWidget):
    """Pannello Comandi (§3.6): cronologia con chi, esito, dettagli, Riesegui e Copia come JSON."""

    rerunRequested = Signal(list)  # list[HistoryEntry]

    COLUMNS = ("#", "Time (UTC)", "Who", "Command", "Parameters", "Result", "Warnings")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.entries: list[HistoryEntry] = []
        self.shown: list[HistoryEntry] = []
        self.class_filter = QComboBox()
        self.class_filter.setObjectName("classFilter")
        for key, text in (("session", self.tr("Session commands")), ("application", self.tr("Application commands")),
                          ("all", self.tr("All classes"))):
            self.class_filter.addItem(text, key)
        self.who_filter = QComboBox()
        self.who_filter.setObjectName("whoFilter")
        for key, text in (("all", self.tr("Everyone")), ("user", self.tr("User")), ("ai", self.tr("AI")),
                          ("session", self.tr("Session"))):
            self.who_filter.addItem(text, key)
        self.rerun_button = QPushButton(self.tr("Rerun"))
        self.copy_button = QPushButton(self.tr("Copy as JSON"))
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setObjectName("historyTable")
        self.table.setHorizontalHeaderLabels([
            self.tr("#"), self.tr("Time (UTC)"), self.tr("Who"), self.tr("Command"), self.tr("Parameters"),
            self.tr("Result"), self.tr("Warnings")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        _style_table(self.table)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.mono = _tabular(_scaled(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont), 0.92))
        self.detail = QPlainTextEdit()
        self.detail.setObjectName("historyDetail")
        self.detail.setReadOnly(True)
        self.detail.setFont(self.mono)
        self.empty = EmptyState("history", self.tr("No commands yet"), self.tr(
            "Every action from the menus, the keyboard or the mouse appears here with its number: select it to "
            "see parameters, result and provenance, rerun it or copy it as JSON."))
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 8, 8, 0)
        bar.setSpacing(8)
        for w in (self.class_filter, self.who_filter):
            bar.addWidget(w)
        bar.addStretch(1)
        bar.addWidget(self.rerun_button)
        bar.addWidget(self.copy_button)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self.table)
        split.addWidget(self.detail)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(split)
        self.empty.cover(body)  # non il QSplitter: lo prenderebbe come terza colonna
        _as_panel(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(bar)
        layout.addWidget(body)
        self.class_filter.currentIndexChanged.connect(self.refresh)
        self.who_filter.currentIndexChanged.connect(self.refresh)
        self.table.itemSelectionChanged.connect(self._show_detail)
        self.rerun_button.clicked.connect(lambda: self.rerunRequested.emit(self.selected()))
        self.copy_button.clicked.connect(self.copy_json)

    def set_entries(self, entries) -> None:
        self.entries = list(entries)
        self.refresh()

    def add(self, entry: HistoryEntry) -> None:
        self.entries.append(entry)
        if self._passes(entry):
            self.shown.append(entry)
            self._add_row(entry)
        self._show_empty()

    def _show_empty(self) -> None:
        self.empty.setVisible(not self.shown)

    def _passes(self, entry: HistoryEntry) -> bool:
        cls, who = self.class_filter.currentData(), self.who_filter.currentData()
        if cls != "all" and entry.command_class != cls:
            return False
        source = entry.command.requested_by.source
        group = "ai" if source == "ai" else "session" if source == "session" else "user"
        return who == "all" or who == group

    def refresh(self) -> None:
        self.table.setRowCount(0)
        self.shown = [e for e in self.entries if self._passes(e)]
        for entry in self.shown:
            self._add_row(entry)
        self._show_empty()

    def _add_row(self, entry: HistoryEntry) -> None:
        r = entry.result
        status = {"ok": self.tr("ok"), "error": self.tr("error"), "cancelled": self.tr("cancelled")}[r.status]
        cells = [str(entry.number), r.started_at[11:19], _who(entry.command.requested_by), entry.command.name,
                 _json_text(dict(entry.command.parameters))[:160], status, str(len(r.warnings))]
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            if col == 3:
                item.setFont(self.mono)  # nome del comando a larghezza fissa (mockup)
            if r.status == "error":
                item.setForeground(QColor(_TOKENS[_current_tokens()]["error"]))
            self.table.setItem(row, col, item)

    def selected(self) -> list[HistoryEntry]:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.shown[r] for r in rows]

    def _show_detail(self) -> None:
        chosen = self.selected()
        if not chosen:
            self.detail.clear()
            return
        entry = chosen[-1]
        self.detail.setPlainText(json.dumps(entry.to_json(), ensure_ascii=False, indent=2))

    def copy_json(self) -> None:
        chosen = self.selected()
        if not chosen:
            return
        data = [e.command.to_json() for e in chosen]
        QApplication.clipboard().setText(json.dumps(data[0] if len(data) == 1 else data, ensure_ascii=False,
                                                    indent=2))


class MessagesPanel(QWidget):
    """Pannello Messaggi (§3.7): errori e avvisi con codice e testo dei moduli invariati e numero del comando."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("messagesTable")
        self.table.setHorizontalHeaderLabels([self.tr("Command"), self.tr("Code"), self.tr("Message")])
        _style_table(self.table)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(True)
        self.empty = EmptyState("message-square-warning", self.tr("No messages"), self.tr(
            "Errors and warnings of the modules appear here with their code, their unchanged text and the "
            "number of the command that produced them; errors in red."))
        self.empty.cover(self.table)
        _as_panel(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        self.messages: list[tuple[str, str, str, bool]] = []  # (comando, codice, testo, errore)

    def add(self, number: int | None, message: ResultMessage, *, error: bool) -> None:
        ref = "—" if number is None else f"#{number}"
        self.messages.append((ref, message.code, message.text, error))
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, text in enumerate((ref, message.code, message.text)):
            item = QTableWidgetItem(text)
            if error:
                item.setForeground(QColor(_TOKENS[_current_tokens()]["error"]))
            self.table.setItem(row, col, item)
        self.empty.hide()
        self.table.scrollToBottom()


_CURRENT_APPEARANCE = ["dark"]


def _current_tokens() -> str:
    return _CURRENT_APPEARANCE[0]


# --------------------------------------------------------------------------
# Finestre di dialogo: HiPS, catalogo nel campo, salva sessione, preferenze, informazioni
# --------------------------------------------------------------------------


class _IndexTask(QRunnable):
    """Sincronizzazione della copia locale delle collezioni HiPS (12) fuori dal thread principale."""

    class _Signals(QObject):
        done = Signal(object, object)  # indice, errore (ResultMessage)

    def __init__(self, loader: Callable) -> None:
        super().__init__()
        self.loader = loader
        self.signals = self._Signals()

    def run(self) -> None:
        try:
            index = self.loader()
        except Exception as exc:  # noqa: BLE001 - codice e testo del modulo invariati
            code, message = getattr(exc, "code", type(exc).__name__), getattr(exc, "message", str(exc))
            self.signals.done.emit(None, ResultMessage(str(code), str(message)))
            return
        self.signals.done.emit(index, None)


class HipsSurveyDialog(QDialog):
    """Data → HiPS survey… (§3.3): ricerca nella copia locale delle collezioni (``CollectionIndex.filter``)
    e campo per identificativo o URL; OK → ``hips.set_survey``."""

    def __init__(self, loader: Callable, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("HiPS survey"))
        self.index = None
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.tr("Search the local copy of the HiPS collections"))
        self.results = QListWidget()
        self.status = QLabel(self.tr("Reading the list of HiPS collections…"))
        self.status.setWordWrap(True)
        self.survey = QLineEdit()
        self.survey.setObjectName("surveyField")
        self.survey.setPlaceholderText(self.tr("Identifier or URL, e.g. CDS/P/DSS2/color"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form = QVBoxLayout(self)
        form.setSpacing(8)
        for w in (self.search, self.results, self.status, QLabel(self.tr("Survey")), self.survey, buttons):
            form.addWidget(w)
        self.search.textChanged.connect(self._filter)
        self.results.currentTextChanged.connect(lambda t: self.survey.setText(t.split("  ")[0]) if t else None)
        task = _IndexTask(loader)
        task.signals.done.connect(self._loaded)
        self._task = task
        QThreadPool.globalInstance().start(task)

    def _loaded(self, index, error) -> None:
        if error is not None:
            self.status.setText(f"{error.code}: {error.text}")
            return
        self.index = index
        self.status.setText(index.describe())
        self._filter(self.search.text())

    def _filter(self, text: str) -> None:
        if self.index is None:
            return
        self.results.clear()
        for record in self.index.filter(text or None)[:500]:
            self.results.addItem(f"{record.get('ID')}  {record.get('obs_title', '')}")

    def _accept(self) -> None:
        if self.survey.text().strip():
            self.accept()


class CatalogInViewDialog(QDialog):
    """Data → Catalog in view… (§3.3): identificativo per ``load_catalog`` del 13 e ``max_rows`` (D14-5)."""

    def __init__(self, collections, default_max_rows: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Catalog in view"))
        self.catalog = QComboBox()
        self.catalog.setObjectName("catalogField")
        self.catalog.setEditable(True)
        for c in collections:
            self.catalog.addItem(f"{c.id}", c.id)
            self.catalog.setItemData(self.catalog.count() - 1, c.title, Qt.ItemDataRole.ToolTipRole)
        self.max_rows = QSpinBox()
        self.max_rows.setObjectName("maxRows")
        self.max_rows.setLocale(QLocale.c())
        self.max_rows.setGroupSeparatorShown(False)
        self.max_rows.setRange(1, 2_000_000_000)
        self.max_rows.setValue(default_max_rows)
        note = QLabel(self.tr("Centre and radius are those of the current view."))
        note.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout(self)
        form.addRow(self.tr("Catalog"), self.catalog)
        form.addRow(self.tr("Maximum rows"), self.max_rows)
        form.addRow(note)
        form.addRow(buttons)


class SaveSessionDialog(QDialog):
    """File → Save session… con la casella "Includi il testo delle conversazioni" (spenta, 35 §3.9)."""

    def __init__(self, start: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Save session"))
        self.path = QLineEdit(start)
        self.path.setObjectName("sessionPath")
        browse = QPushButton(self.tr("Choose…"))
        browse.clicked.connect(self._browse)
        self.conversations = QCheckBox(self.tr("Include the text of the conversations"))
        self.conversations.setObjectName("includeConversations")
        self.conversations.setChecked(False)
        row = QHBoxLayout()
        row.addWidget(self.path, 1)
        row.addWidget(browse)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addLayout(row)
        layout.addWidget(self.conversations)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Save session"), self.path.text(),
                                              self.tr("AstroTwo session (*%1)").replace("%1", SESSION_EXTENSION))
        if path:
            if not path.endswith(SESSION_EXTENSION):
                path += SESSION_EXTENSION
            self.path.setText(path)


class PreferencesDialog(QDialog):
    """Le cinque preferenze di §3.10; OK → un ``prefs.set`` per ogni valore cambiato (classe ``application``)."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window_ = window
        self.setWindowTitle(self.tr("Settings"))
        self.language = QComboBox()
        self.language.setObjectName("prefLanguage")
        for key, text in (("system", self.tr("System")), ("en", "English"), ("it", "Italiano")):
            self.language.addItem(text, key)
        self.cache_limit = QLineEdit()
        self.cache_limit.setObjectName("prefCacheLimit")
        self.cache_usage = QLabel()
        self.cache_usage.setObjectName("cacheUsage")
        self.cache_usage.setWordWrap(True)
        self.cache_usage.setFont(_tabular(self.cache_usage.font()))
        clear = QPushButton(self.tr("Clear cache"))
        clear.setObjectName("clearCache")
        clear.clicked.connect(lambda: window.submit("cache.clear", {"module": None}))
        self.coordinates = QComboBox()
        self.coordinates.setObjectName("prefCoordinates")
        for key, text in (("icrs_sexagesimal", self.tr("ICRS sexagesimal")), ("icrs_decimal", self.tr("ICRS decimal")),
                          ("galactic", self.tr("Galactic"))):
            self.coordinates.addItem(text, key)
        self.survey = QLineEdit()
        self.survey.setObjectName("prefSurvey")
        self.appearance = QComboBox()
        self.appearance.setObjectName("prefAppearance")
        for key, text in (("system", self.tr("System")), ("dark", self.tr("Dark")), ("light", self.tr("Light")),
                          ("night", self.tr("Red night mode"))):
            self.appearance.addItem(text, key)
        assistant = QLabel(self.tr("The assistant settings arrive with the assistant panel (module 44). "
                                   "API keys are kept only in the macOS Keychain."))
        assistant.setWordWrap(True)
        restart = QLabel(self.tr("A new language applies when AstroTwo restarts."))
        restart.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        form = QFormLayout(self)
        form.setSpacing(8)
        form.addRow(self.tr("Language"), self.language)
        form.addRow("", restart)
        cache_row = QHBoxLayout()
        cache_row.addWidget(self.cache_limit, 1)
        cache_row.addWidget(clear)
        form.addRow(self.tr("Cache limit (bytes)"), cache_row)
        form.addRow("", self.cache_usage)
        form.addRow(self.tr("Coordinates shown"), self.coordinates)
        form.addRow(self.tr("Default HiPS survey"), self.survey)
        form.addRow(self.tr("Appearance"), self.appearance)
        form.addRow(self.tr("Assistant"), assistant)
        form.addRow(buttons)
        self._load()

    def _load(self) -> None:
        w = self.window_
        self.language.setCurrentIndex(self.language.findData(w.preference("language")))
        self.cache_limit.setText(w.preference("cache/limit_bytes"))
        self.coordinates.setCurrentIndex(self.coordinates.findData(w.preference("view/coordinates")))
        self.survey.setText(w.preference("hips/default_survey"))
        self.appearance.setCurrentIndex(self.appearance.findData(w.preference("appearance")))
        self.show_usage()

    def show_usage(self) -> None:
        """Spazio usato per modulo e totale (``usage`` del 04), in byte."""
        try:
            usage = self.window_.cache.usage()
        except Exception as exc:  # noqa: BLE001
            self.cache_usage.setText(f"{getattr(exc, 'code', type(exc).__name__)}: {exc}")
            return
        modules = ", ".join(f"{m}: {b}" for m, b in sorted(usage.by_module.items())) or self.tr("empty")
        self.cache_usage.setText(self.tr("Used: %1 bytes of %2 (%3)").replace("%1", str(usage.total_bytes))
                                 .replace("%2", str(usage.limit_bytes)).replace("%3", modules))

    def values(self) -> dict[str, str]:
        return {"language": self.language.currentData(), "cache/limit_bytes": self.cache_limit.text().strip(),
                "view/coordinates": self.coordinates.currentData(), "hips/default_survey": self.survey.text(),
                "appearance": self.appearance.currentData()}

    def _apply(self) -> None:
        for key, value in self.values().items():
            if value != self.window_.preference(key):
                self.window_.submit("prefs.set", {"key": key, "value": value})
        self.accept()


def _licenses_text() -> str:
    for candidate in (Path(astrotwo.__file__).resolve().parents[2] / "THIRD_PARTY_LICENSES",
                      Path(sys.prefix) / "THIRD_PARTY_LICENSES"):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return QCoreApplication.translate("MainWindow", "THIRD_PARTY_LICENSES not found.")


# --------------------------------------------------------------------------
# Finestra principale
# --------------------------------------------------------------------------


class MainWindow(QMainWindow):
    """Finestra, menu, pannelli agganciabili, area riservata al pannello IA; registro e sessione del 05.

    ``registry``/``settings``: per i test (registro con servizi simulati, impostazioni in una cartella
    temporanea). ``startup_commands``: all'avvio i comandi delle preferenze (coordinate mostrate, survey HiPS).
    """

    _submit_job = Signal(object)

    def __init__(self, registry: CommandRegistry | None = None, settings: QSettings | None = None, *,
                 startup_commands: bool = True) -> None:
        super().__init__()
        self.settings = settings if settings is not None else QSettings()
        QLocale.setDefault(QLocale.c())  # punto decimale per tutti i numeri in ogni lingua (§3.9)
        self.language, translation_warnings = load_translations(self.preference("language"))
        if registry is None:
            self.cache = ThreadCache(int(self.preference("cache/limit_bytes")))
            registry = default_registry(cache=self.cache)
        else:
            self.cache = registry.cache if registry.cache is not None else ThreadCache()
        for name, executor in BOUND_EXECUTORS.items():
            if name in {s.name for s in registry.specs()}:
                registry.bind(name, executor)
        self.registry = registry
        self.session = Session(registry)
        self.saved_count = 0
        self.saved_path: str | None = None
        self.active_tool = "none"
        self.appearance = "dark"
        self._ids = itertools.count(1)
        self._jobs: dict[int, CommandJob | ReplayJob] = {}
        self._running: int | None = None
        self.collection_index_loader: Callable = self._load_collection_index
        self.confirm: Callable[[str, str], bool] = self._ask_confirmation
        self.show_modal: Callable[[str, str], None] = self._modal
        self.open_path: Callable[[str], str | None] = self._ask_open_path
        self.last_modal: tuple[str, str] | None = None
        self.setWindowTitle("AstroTwo")
        self.setUnifiedTitleAndToolBarOnMac(True)
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks | QMainWindow.DockOption.AllowTabbedDocks)
        self.resize(1280, 800)
        self._build_central()
        self._build_docks()
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self.status = StatusBar(self)
        self.status.cancelRequested.connect(self.cancel_running)
        self.setStatusBar(self.status)
        self._start_runner()
        self.apply_appearance(self.preference("appearance"))
        QApplication.styleHints().colorSchemeChanged.connect(self._system_scheme_changed)
        geometry = self.settings.value("window/geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        state = self.settings.value("window/state")
        if isinstance(state, QByteArray):
            self.restoreState(state)
        for message in translation_warnings:
            self.messages.add(None, message, error=False)
        self._startup_view = startup_commands
        if startup_commands:
            frame, fmt = COORDINATE_DISPLAYS[self.preference("view/coordinates")]
            self.submit("view.set_coordinate_display", {"frame": frame, "format": fmt})
            self.submit("hips.set_survey", {"survey": self.preference("hips/default_survey")})

    # --- costruzione -------------------------------------------------------------------

    def _build_central(self) -> None:
        """Visualizzatore del cielo del 41 al centro (sprint 4a: sfondo HiPS, zoom e spostamento)."""
        from astrotwo.ui.sky_viewer import SkyViewer

        self.sky = SkyViewer(self.submit, cache=self.cache)
        self.sky.message.connect(lambda m: self.messages.add(None, m, error=m.code == "GL_UNAVAILABLE"))
        if hasattr(self.sky.renderer, "failed"):
            self.sky.renderer.failed.connect(
                lambda code, text: self.messages.add(None, ResultMessage(code, text), error=True))
        self.sky.tiles_changed.connect(lambda _n: self._update_network())
        self.sky.view_changed.connect(self._show_survey)
        self.sky.first_shown.connect(self._first_view)
        self.sky_area = self.sky
        self.setCentralWidget(self.sky)

    def _panel(self, widget: QWidget) -> QWidget:
        return _as_panel(widget)

    def _build_docks(self) -> None:
        self.history = HistoryPanel()
        self.history.rerunRequested.connect(self.rerun)
        self.messages = MessagesPanel()
        self.empty_states = {
            "layers": EmptyState("layers", self.tr("No layers yet"), self.tr(
                "Arrive with the sky viewer (module 41): one row for each HiPS survey, image, catalog, MOC and "
                "measurement, with order, visibility and opacity.")),
            "assistant": EmptyState("sparkles", self.tr("Assistant"), self.tr(
                "The assistant is not available: its panel (module 44) is not written yet. "
                "The rest of AstroTwo works normally.")),
            "table": EmptyState("table-2", self.tr("No catalog yet"), self.tr(
                "Arrives with module 42: one tab for each catalog layer, column headers with units, sorting, "
                "and selection synchronised with the sky.")),
        }
        specs = (
            ("layers", self.tr("Layers"), self._panel(self.empty_states["layers"]),
             Qt.DockWidgetArea.LeftDockWidgetArea),
            ("assistant", self.tr("Assistant"), self._panel(self.empty_states["assistant"]),
             Qt.DockWidgetArea.RightDockWidgetArea),
            ("table", self.tr("Table"), self._panel(self.empty_states["table"]), Qt.DockWidgetArea.BottomDockWidgetArea),
            ("commands", self.tr("Commands"), self.history, Qt.DockWidgetArea.BottomDockWidgetArea),
            ("messages", self.tr("Messages"), self.messages, Qt.DockWidgetArea.BottomDockWidgetArea),
        )
        self.setTabPosition(Qt.DockWidgetArea.BottomDockWidgetArea, QTabWidget.TabPosition.North)
        self.docks: dict[str, _Dock] = {}
        for key, title, widget, area in specs:
            dock = _Dock(key, title, self)
            dock.setWidget(widget)
            dock.closeRequested.connect(lambda k: self.submit("ui.set_panel", {"panel": k, "visible": False},
                                                              source="mouse"))
            for signal in (dock.visibilityChanged, dock.topLevelChanged, dock.dockLocationChanged):
                signal.connect(self._schedule_headers)
            self.addDockWidget(area, dock)
            self.docks[key] = dock
        self.docks["layers"].setMinimumWidth(232)
        self.docks["assistant"].setMinimumWidth(380)
        self.docks["assistant"].setMaximumWidth(420)
        self.tabifyDockWidget(self.docks["table"], self.docks["commands"])
        self.tabifyDockWidget(self.docks["commands"], self.docks["messages"])
        self.docks["commands"].raise_()
        self._refresh_headers()

    def _schedule_headers(self, *_) -> None:
        QTimer.singleShot(0, self._refresh_headers)

    def _refresh_headers(self) -> None:
        """Intestazione propria per i pannelli soli; per i pannelli a schede fanno da intestazione le schede."""
        for dock in self.docks.values():
            tabbed = not dock.isFloating() and any(not d.isHidden() for d in self.tabifiedDockWidgets(dock))
            dock.show_header(not tabbed)

    def _action(self, text: str, slot: Callable | None = None, *, shortcut=None, checkable=False,
                name: str | None = None) -> QAction:
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        action.setCheckable(checkable)
        if name:
            action.setObjectName(name)
        if slot is not None:
            action.triggered.connect(slot)
        return action

    def _build_actions(self) -> None:
        a = self._action
        self.act_open_image = a(self.tr("Open image…"), lambda: self._open_file("image.open"),
                                shortcut=QKeySequence.StandardKey.Open, name="openImage")
        self.act_open_catalog = a(self.tr("Open catalog…"), lambda: self._open_file("catalog.open_file"),
                                  name="openCatalog")
        self.act_open_moc = a(self.tr("Open MOC…"), lambda: self._open_file("moc.open"), name="openMoc")
        self.act_open_session = a(self.tr("Open session…"), self.open_session_dialog, name="openSession")
        self.act_save_session = a(self.tr("Save session…"), self.save_session_dialog,
                                  shortcut=QKeySequence.StandardKey.Save, name="saveSession")
        self.act_export_png = a(self.tr("Export view as PNG…"), self._export_png, name="exportPng")
        self.act_settings = a(self.tr("Settings…"), self.preferences_dialog,
                              shortcut=QKeySequence.StandardKey.Preferences, name="settings")
        self.act_settings.setMenuRole(QAction.MenuRole.PreferencesRole)
        self.act_quit = a(self.tr("Quit"), self.close, shortcut=QKeySequence.StandardKey.Quit, name="quit")
        self.act_quit.setMenuRole(QAction.MenuRole.QuitRole)
        self.act_go_to = a(self.tr("Go to…"), lambda: self.go_to_field.setFocus(), shortcut="Ctrl+L", name="goTo")
        self.act_grid = a(self.tr("Show coordinate grid"), self._grid_toggled, checkable=True, name="grid")
        self.grid_frames = QActionGroup(self)
        self.act_grid_icrs = a(self.tr("Grid in ICRS"), lambda: self._grid_frame("icrs"), checkable=True,
                               name="gridIcrs")
        self.act_grid_gal = a(self.tr("Grid in galactic"), lambda: self._grid_frame("galactic"), checkable=True,
                              name="gridGalactic")
        for act in (self.act_grid_icrs, self.act_grid_gal):
            self.grid_frames.addAction(act)
        self.act_grid_icrs.setChecked(True)
        self.coordinate_actions: dict[str, QAction] = {}
        self.coordinate_group = QActionGroup(self)
        for key, text in (("icrs_sexagesimal", self.tr("ICRS sexagesimal")), ("icrs_decimal", self.tr("ICRS decimal")),
                          ("galactic", self.tr("Galactic"))):
            act = a(text, lambda checked=False, k=key: self._coordinates_shown(k), checkable=True,
                    name=f"coords_{key}")
            self.coordinate_group.addAction(act)
            self.coordinate_actions[key] = act
        self.coordinate_actions[self.preference("view/coordinates")].setChecked(True)
        self.act_fullscreen = a(self.tr("Full screen"), lambda c: self.submit("ui.set_fullscreen", {"enabled": c}),
                                shortcut="Meta+Ctrl+F", checkable=True, name="fullscreen")
        self.act_night = a(self.tr("Night mode"), self._night_toggled, shortcut="Meta+Ctrl+N", checkable=True,
                           name="night")  # ⌃⌘N (D40-4)
        self.act_hips = a(self.tr("HiPS survey…"), self.hips_dialog, name="hipsSurvey")
        self.act_catalog_view = a(self.tr("Catalog in view…"), self.catalog_dialog, name="catalogInView")
        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        self.act_distance = a(self.tr("Distance"), lambda c: self._tool("distance", c), checkable=True,
                              name="toolDistance")
        self.act_simbad = a(self.tr("Simbad pointer"), lambda c: self._tool("simbad_pointer", c), checkable=True,
                            name="toolSimbad")
        for act in (self.act_distance, self.act_simbad):
            self.tool_group.addAction(act)
        self.panel_actions: dict[str, QAction] = {}
        for key, dock in self.docks.items():
            act = a(dock.windowTitle(), lambda c, k=key: self.submit("ui.set_panel", {"panel": k, "visible": c}),
                    checkable=True, name=f"panel_{key}")
            act.setChecked(True)
            self.panel_actions[key] = act
        self.panel_actions["assistant"].setShortcut(QKeySequence("Meta+Ctrl+A"))
        self.act_about = a(self.tr("About AstroTwo"), self.about_dialog, name="about")
        self.act_about.setMenuRole(QAction.MenuRole.AboutRole)

    def _build_menus(self) -> None:
        bar = self.menuBar()
        m = bar.addMenu(self.tr("File"))
        for act in (self.act_open_image, self.act_open_catalog, self.act_open_moc):
            m.addAction(act)
        m.addSeparator()
        m.addAction(self.act_open_session)
        m.addAction(self.act_save_session)
        m.addSeparator()
        m.addAction(self.act_export_png)
        m.addSeparator()
        m.addAction(self.act_settings)
        m.addAction(self.act_quit)
        m = bar.addMenu(self.tr("View"))
        m.addAction(self.act_go_to)
        grid = m.addMenu(self.tr("Coordinate grid"))
        grid.addAction(self.act_grid)
        grid.addSeparator()
        grid.addAction(self.act_grid_icrs)
        grid.addAction(self.act_grid_gal)
        shown = m.addMenu(self.tr("Coordinates shown"))
        for act in self.coordinate_actions.values():
            shown.addAction(act)
        m.addSeparator()
        m.addAction(self.act_fullscreen)
        m.addAction(self.act_night)
        m = bar.addMenu(self.tr("Data"))
        m.addAction(self.act_hips)
        m.addAction(self.act_catalog_view)
        m = bar.addMenu(self.tr("Tools"))
        m.addAction(self.act_distance)
        m.addAction(self.act_simbad)
        m = bar.addMenu(self.tr("Window"))
        for act in self.panel_actions.values():
            m.addAction(act)
        m = bar.addMenu(self.tr("Help"))
        m.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        tb = QToolBar(self.tr("Toolbar"))
        tb.setObjectName("mainToolbar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        def spacer() -> QWidget:
            w = QWidget()
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            return w

        # Pulsanti del mockup: ognuno è un'azione dei menu di §3.3 (stesso comando del 05), nessuna funzione nuova.
        for act in (self.act_open_image, self.panel_actions["layers"], self.act_grid):
            tb.addAction(act)
        tb.addSeparator()
        for act in (self.act_distance, self.act_simbad):
            tb.addAction(act)
        tb.addWidget(spacer())
        self.go_to_field = GoToField()
        self.go_to_field.goTo.connect(self.go_to)
        tb.addWidget(self.go_to_field)
        tb.addWidget(spacer())
        self.survey_label = QLabel()
        self.survey_label.setObjectName("surveyLabel")
        self.survey_label.setFont(_tabular(_scaled(self.survey_label.font(), 0.92)))
        self.survey_label.setMinimumHeight(self.survey_label.fontMetrics().height())  # barra di altezza fissa
        tb.addWidget(self.survey_label)
        tb.addAction(self.act_night)
        tb.addAction(self.panel_actions["assistant"])
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        self.toolbar = tb
        self.toolbar_icons = {
            self.act_open_image: "folder-open", self.panel_actions["layers"]: "layers", self.act_grid: "grid-3x3",
            self.act_distance: "ruler", self.act_simbad: "crosshair", self.act_night: "moon",
            self.panel_actions["assistant"]: "sparkles"}
        for act in self.toolbar_icons:
            act.setIconVisibleInMenu(False)  # menu di macOS senza icone
            shortcut = act.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
            act.setToolTip(f"{act.text()} ({shortcut})" if shortcut else act.text())

    def _start_runner(self) -> None:
        self._thread = QThread(self)
        self._thread.setObjectName("astrotwo-commands")
        self.runner = CommandRunner(self.session)
        self.runner.moveToThread(self._thread)
        self._submit_job.connect(self.runner.run_job, Qt.ConnectionType.QueuedConnection)
        self.runner.started.connect(self._job_started)
        self.runner.progress.connect(self._job_progress)
        self.runner.finished.connect(self._job_finished)
        self.runner.replayed.connect(self._replay_finished)
        self._thread.start()

    # --- preferenze ---------------------------------------------------------------------

    def preference(self, key: str) -> str:
        pref = PREFERENCES[key]
        value = self.settings.value(key, pref.default)
        try:
            return pref.check(str(value))
        except ValueError:
            return pref.default

    # --- coda dei comandi ----------------------------------------------------------------

    def submit(self, name: str, params: Mapping[str, object], *, source: str = "menu") -> int:
        """Mette in coda il comando ``name`` (versione registrata) chiesto da ``source`` (05 ``requested_by``)."""
        try:
            version = self.registry.spec(name).version
        except CommandError:
            version = 1  # nome sconosciuto: il 05 risponde COMMAND_UNKNOWN
        return self.submit_command(Command(name, version, dict(params), RequestedBy(source)))

    def submit_command(self, command: Command) -> int:
        """Mette in coda un comando già formato (Riesegui, assistente con ``requested_by = ai``)."""
        try:
            network = self.registry.spec(command.name).network
        except CommandError:
            network = False
        job = CommandJob(next(self._ids), command, network=network)
        self._jobs[job.id] = job
        self._update_network()
        self._submit_job.emit(job)
        return job.id

    def busy(self) -> bool:
        return bool(self._jobs)

    def cancel_running(self) -> None:
        if self._running is not None and self._running in self._jobs:
            self._jobs[self._running].cancel.cancel()

    def _update_network(self) -> None:
        """Comandi di rete in coda o in corso; i tile HiPS in arrivo li conta il 41."""
        self.status.show_network(sum(1 for j in self._jobs.values() if j.network), self.sky._in_flight)

    @Slot(int, str)
    def _job_started(self, job_id: int, name: str) -> None:
        self._running = job_id
        self.status.show_running(name)

    @Slot(int, object)
    def _job_progress(self, job_id: int, report: ProgressReport) -> None:
        job = self._jobs.get(job_id)
        if job is not None:
            self.status.show_running(job.command.name if isinstance(job, CommandJob) else "session.open", report)

    def _job_done(self, job_id: int) -> None:
        self._jobs.pop(job_id, None)
        if self._running == job_id:
            self._running = None
            self.status.show_idle()
        self._update_network()

    @Slot(object)
    def _job_finished(self, done: CommandDone) -> None:
        self._job_done(done.job_id)
        result = done.result
        number = None if done.entry is None else done.entry.number
        if done.entry is not None:
            self.history.add(done.entry)
        for w in result.warnings:
            self.messages.add(number, w, error=False)
        if result.error is not None and result.status == "error":
            self.messages.add(number, result.error, error=True)
            if done.registered.name == "view.go_to":  # il pannello Messaggi è in una scheda: errore anche qui
                self.status.showMessage(f"{result.error.code}: {result.error.text}", 10000)
            if done.registered.name in ("image.open", "catalog.open_file", "moc.open"):
                self.show_modal(self.tr("The file cannot be opened"), f"{result.error.code}: {result.error.text}")
        elif result.status == "ok":
            self._apply_effect(done.registered, result)
        self.sky.command_finished(done.registered.name, result.status, result.values,
                                  self.session.workspace.state)

    def _apply_effect(self, command: Command, result: CommandResult) -> None:
        """Effetto dei comandi dell'interfaccia (classe ``application``) e stato dei menu, nel thread principale."""
        p = result.values
        name = command.name
        if name == "prefs.set":
            self.settings.setValue(p["key"], p["value"])
            self.settings.sync()
            if p["key"] == "appearance":
                self.apply_appearance(p["value"])
            elif p["key"] == "cache/limit_bytes" and isinstance(self.cache, ThreadCache):
                self.cache.limit_bytes = int(p["value"])
        elif name == "ui.set_appearance":
            self.apply_appearance(p["mode"])
        elif name == "ui.set_fullscreen":
            self.showFullScreen() if p["enabled"] else self.showNormal()
            self.act_fullscreen.setChecked(p["enabled"])
        elif name == "ui.set_panel":
            self.docks[p["panel"]].setVisible(p["visible"])
            self.panel_actions[p["panel"]].setChecked(p["visible"])
        elif name == "ui.set_tool":
            self.active_tool = p["tool"]
            self.act_distance.setChecked(p["tool"] == "distance")
            self.act_simbad.setChecked(p["tool"] == "simbad_pointer")
        elif name == "view.set_grid":
            self.act_grid.setChecked(command.parameters["visible"])
            (self.act_grid_icrs if command.parameters["frame"] == "icrs" else self.act_grid_gal).setChecked(True)
        elif name == "view.set_coordinate_display":
            for key, (frame, fmt) in COORDINATE_DISPLAYS.items():
                if (frame, fmt) == (p["frame"], p["format"]):
                    self.coordinate_actions[key].setChecked(True)

    # --- azioni dei menu ----------------------------------------------------------------

    def view_window(self) -> dict[str, int]:
        """Dimensioni della vista in pixel fisici (pixel logici × rapporto dei pixel dello schermo)."""
        return self.sky.window_size()

    def _first_view(self) -> None:
        """Vista iniziale (cielo intero) quando il cielo ha la sua dimensione vera, dopo il survey dell'avvio."""
        if self._startup_view:
            self.sky.start_view()

    def _show_survey(self) -> None:
        """Scritta del survey nella barra (40 §3.11): titolo · proiezione · campo, valori dati da 12 e 10."""
        from astrotwo.ui.sky_viewer import format_field

        sky = self.sky
        if sky.service is None:
            self.survey_label.setText("")
            return
        parts = [sky.service.title or sky.service.hips_id]
        if sky.view is not None and sky.view.projection:
            parts.append(sky.view.projection)
        if sky.field is not None:
            parts.append(self.tr("field %1").replace("%1", format_field(sky.field)))
        self.survey_label.setText(" · ".join(parts))

    def go_to(self, text: str) -> int:
        return self.submit("view.go_to", {"text": text, "window": self.view_window()}, source="keyboard")

    def _open_file(self, name: str) -> None:
        path = self.open_path(name)
        if path:
            self.submit(name, {"file": {"path": str(Path(path).resolve())}})

    def _ask_open_path(self, name: str) -> str | None:
        titles = {"image.open": (self.tr("Open image"), self.tr("FITS images (*.fits *.fit *.fts *.fits.gz)")),
                  "catalog.open_file": (self.tr("Open catalog"),
                                        self.tr("Catalogs (*.xml *.vot *.fits *.csv *.tsv *.ecsv *.txt)")),
                  "moc.open": (self.tr("Open MOC"), self.tr("MOC (*.fits *.json *.txt)")),
                  "session.open": (self.tr("Open session"),
                                   self.tr("AstroTwo session (*%1)").replace("%1", SESSION_EXTENSION))}
        title, filters = titles[name]
        everything = self.tr("All files (*)")
        path, _ = QFileDialog.getOpenFileName(self, title, "", f"{filters};;{everything}")
        return path or None

    def _export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Export view as PNG"), "", "PNG (*.png)")
        if path:
            self.submit("view.export_png", {"path": str(Path(path).resolve())})

    def _grid_toggled(self, checked: bool) -> None:
        self.submit("view.set_grid", {"visible": checked,
                                      "frame": "icrs" if self.act_grid_icrs.isChecked() else "galactic"})

    def _grid_frame(self, frame: str) -> None:
        self.submit("view.set_grid", {"visible": self.act_grid.isChecked(), "frame": frame})

    def _coordinates_shown(self, key: str) -> None:
        frame, fmt = COORDINATE_DISPLAYS[key]
        self.submit("view.set_coordinate_display", {"frame": frame, "format": fmt})

    def _night_toggled(self, checked: bool) -> None:
        """Notte rossa sì/no; spenta torna all'aspetto della preferenza (sistema se la preferenza è la notte)."""
        back = self.preference("appearance")
        self.submit("ui.set_appearance", {"mode": "night" if checked else ("system" if back == "night" else back)})

    def _tool(self, tool: str, checked: bool) -> None:
        self.submit("ui.set_tool", {"tool": tool if checked else "none"})

    def _load_collection_index(self):
        from astrotwo.core.hips import CollectionIndex

        return CollectionIndex(cache=self.cache).sync()

    def hips_dialog(self) -> HipsSurveyDialog:
        dialog = HipsSurveyDialog(self.collection_index_loader, self)
        dialog.accepted.connect(lambda: self.submit("hips.set_survey", {"survey": dialog.survey.text().strip()}))
        dialog.open()
        return dialog

    def catalog_dialog(self) -> CatalogInViewDialog | None:
        """Catalogo nel campo: centro e raggio della vista dalla ``ViewGeometry`` del 10 (scelta minore 5)."""
        from astrotwo.core.catalogs import FIXED_COLLECTIONS
        from astrotwo.core.commands import quantity_json, sky_json
        from astrotwo.core.vo_protocols import DEFAULT_MAX_ROWS

        view = self.session.workspace.state.view
        if view.geometry is None or view.center is None:
            self.show_modal(self.tr("Catalog in view"), self.tr(
                "The view has no centre, scale or size yet: centre it first (Go to…)."))
            return None
        dialog = CatalogInViewDialog(FIXED_COLLECTIONS, DEFAULT_MAX_ROWS, self)

        def accepted() -> None:
            state = self.session.workspace.state.view
            catalog = dialog.catalog.currentText().strip()
            if catalog and state.geometry is not None:
                self.submit("catalog.load_region", {
                    "catalog": catalog, "center": sky_json(state.center),
                    "radius": quantity_json(state.geometry.field_radius), "max_rows": dialog.max_rows.value()})

        dialog.accepted.connect(accepted)
        dialog.open()
        return dialog

    def preferences_dialog(self) -> PreferencesDialog:
        dialog = PreferencesDialog(self)
        dialog.open()
        return dialog

    def about_dialog(self) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("About AstroTwo"))
        text = QPlainTextEdit(_licenses_text())
        text.setReadOnly(True)
        layout = QVBoxLayout(dialog)
        title = QLabel(f"<b>AstroTwo</b> {astrotwo.__version__}")
        layout.addWidget(title)
        layout.addWidget(QLabel(self.tr("Third-party licenses")))
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(640, 480)
        dialog.open()
        return dialog

    # --- cronologia ---------------------------------------------------------------------

    def rerun(self, entries: list[HistoryEntry]) -> list[int]:
        """Riesegui (§3.6): nuovi comandi in coda, con nuovi numeri, chiesti da ``history``."""
        return [self.submit_command(Command(e.command.name, e.command.version, dict(e.command.parameters),
                                            RequestedBy("history"))) for e in entries]

    def unsaved(self) -> bool:
        return len(self.session.history) > self.saved_count

    # --- sessione -----------------------------------------------------------------------

    def save_session_dialog(self) -> None:
        start = self.saved_path or str(Path.home() / f"session{SESSION_EXTENSION}")
        dialog = SaveSessionDialog(start, self)
        dialog.accepted.connect(lambda: self.save_session(dialog.path.text(), dialog.conversations.isChecked()))
        dialog.open()

    def save_session(self, path: str, include_conversations: bool = False) -> bool:
        """Salva la sessione del 05 (non è un comando della sessione stessa, 05 §3.4)."""
        if not path.endswith(SESSION_EXTENSION):
            path += SESSION_EXTENSION
        conversations = [] if include_conversations else None  # testi del 35: con il pannello 44
        try:
            self.session.save(path, app_version=astrotwo.__version__, conversations=conversations)
        except (OSError, ValueError) as exc:
            self.show_modal(self.tr("The session cannot be saved"), f"{type(exc).__name__}: {exc}")
            return False
        self.saved_count = len(self.session.history)
        self.saved_path = path
        return True

    def open_session_dialog(self) -> None:
        path = self.open_path("session.open")
        if path:
            self.open_session(path)

    def open_session(self, path: str) -> int | None:
        """Riapre una sessione rieseguendo i comandi (05 §3.4), con conferma se il lavoro non è salvato."""
        if (self.unsaved() or self.busy()) and not self.confirm(
                self.tr("Open session"),
                self.tr("The current work has commands that are not saved or still running. "
                        "Opening a session replaces it. Continue?")):
            return None
        job = ReplayJob(next(self._ids), str(path))
        self._jobs[job.id] = job
        self._submit_job.emit(job)
        return job.id

    @Slot(object)
    def _replay_finished(self, done: ReplayDone) -> None:
        self._job_done(done.job_id)
        if done.error is not None:
            self.messages.add(None, done.error, error=True)
            self.show_modal(self.tr("The session cannot be opened"), f"{done.error.code}: {done.error.text}")
            return
        report = done.report
        if done.session is not None:
            self.session = done.session
            self.saved_count = len(self.session.history)
            self.saved_path = done.path
            self.history.set_entries(self.session.history.entries)
            self.sky.show_state(self.session.workspace.state)
        for w in report.warnings:
            self.messages.add(None, w, error=False)
        if report.status == "stopped" and report.stop is not None:
            self.messages.add(report.stop_details.get("number"), report.stop, error=True)
            self.show_modal(self.tr("The session was stopped"), f"{report.stop.code}: {report.stop.text}")
        elif report.status == "cancelled":
            self.messages.add(None, report.stop or ResultMessage("COMMAND_CANCELLED", "riapertura annullata"),
                              error=False)

    # --- aspetto ------------------------------------------------------------------------

    def apply_appearance(self, mode: str) -> None:
        self.appearance_mode = mode
        self.appearance = apply_appearance(mode)
        _CURRENT_APPEARANCE[0] = self.appearance
        self.act_night.setChecked(self.appearance == "night")
        self._apply_theme_details(_TOKENS[self.appearance])
        self.sky.set_night(self.appearance == "night")

    def _apply_theme_details(self, tokens: Mapping[str, str]) -> None:
        """Icone e stati vuoti nei colori del tema (in modalità notte solo toni di rosso, §3.11)."""
        for act, name in self.toolbar_icons.items():
            act.setIcon(themed_icon(name, tokens))
        self.go_to_field.search_icon.setIcon(themed_icon("search", {**tokens, "text2": tokens["text3"]}))
        for dock in self.docks.values():
            dock.header.set_theme(tokens)
        for empty in (*self.empty_states.values(), self.history.empty, self.messages.empty):
            empty.set_theme(tokens)

    def _system_scheme_changed(self, scheme) -> None:
        if getattr(self, "appearance_mode", None) == "system" and not getattr(self, "_reapplying", False):
            self._reapplying = True
            try:
                self.apply_appearance("system")
            finally:
                self._reapplying = False

    # --- conferme e finestre modali --------------------------------------------------------

    def _ask_confirmation(self, title: str, text: str) -> bool:
        answer = QMessageBox.question(self, title, text,
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def _modal(self, title: str, text: str) -> None:
        """Finestra modale solo quando l'azione non può proseguire (§3.7), come foglio della finestra."""
        self.last_modal = (title, text)
        box = QMessageBox(QMessageBox.Icon.Warning, title, text, QMessageBox.StandardButton.Ok, self)
        box.setWindowModality(Qt.WindowModality.WindowModal)
        box.open()

    # --- uscita -------------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 - nome di Qt
        if self.busy() or self.unsaved():
            parts = []
            if self.busy():
                parts.append(self.tr("Some commands are still running: they will be cancelled."))
            if self.unsaved():
                parts.append(self.tr("Some commands are not saved in a session."))
            if not self.confirm(self.tr("Quit AstroTwo"), " ".join(parts) + " " + self.tr("Quit anyway?")):
                event.ignore()
                return
        for job in self._jobs.values():
            job.cancel.cancel()
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/state", self.saveState())
        self.settings.sync()
        self.sky.tiles.generation += 1  # richieste di tile superate: si scartano
        if hasattr(self.sky.renderer, "_cleanup"):
            self.sky.renderer._cleanup()  # texture della GPU liberate con il contesto ancora attivo
        self.sky.tiles.wait(int((NETWORK_TIMEOUTS.connect + NETWORK_TIMEOUTS.read) * 1000))
        self._thread.quit()
        # attesa del ritorno della funzione in corso entro i timeout di rete del 04 (§3.8)
        self._thread.wait(int((NETWORK_TIMEOUTS.connect + NETWORK_TIMEOUTS.read) * 1000))
        event.accept()


class _Dock(QDockWidget):
    """Pannello agganciabile: la chiusura con il pulsante del pannello diventa un comando ``ui.set_panel``."""

    closeRequested = Signal(str)

    def __init__(self, key: str, title: str, parent=None) -> None:
        super().__init__(title, parent)
        self.key = key
        self.setObjectName(f"dock_{key}")
        self.header = _DockHeader(self)
        self.no_header = QWidget()  # pannello a schede: niente intestazione, la fanno le schede
        self.setTitleBarWidget(self.header)

    def show_header(self, visible: bool) -> None:
        wanted = self.header if visible else self.no_header
        if self.titleBarWidget() is not wanted:
            self.setTitleBarWidget(wanted)

    def closeEvent(self, event) -> None:  # noqa: N802 - nome di Qt
        event.ignore()  # lo nasconde l'effetto del comando (MainWindow._apply_effect)
        self.closeRequested.emit(self.key)


class _DockHeader(QWidget):
    """Intestazione dei pannelli del mockup: titolo piccolo in maiuscolo, pulsanti per staccare e chiudere.

    Trascinare l'intestazione sposta il pannello e il doppio clic lo stacca, come la barra standard di Qt (i clic
    non usati dalla barra passano al ``QDockWidget``). Chiudere passa da ``_Dock.closeEvent`` (comando
    ``ui.set_panel``).
    """

    def __init__(self, dock: _Dock) -> None:
        super().__init__(dock)
        self.setObjectName("dockHeader")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(30)
        self.title = QLabel(dock.windowTitle())
        self.title.setObjectName("dockTitle")
        self.title.setFont(_header_font(self.title.font()))
        dock.windowTitleChanged.connect(self.title.setText)
        self.float_button = QToolButton()
        self.float_button.setObjectName("dockFloat")
        self.float_button.setToolTip(QCoreApplication.translate("MainWindow", "Detach panel"))
        self.float_button.clicked.connect(lambda: dock.setFloating(not dock.isFloating()))
        self.close_button = QToolButton()
        self.close_button.setObjectName("dockClose")
        self.close_button.setToolTip(QCoreApplication.translate("MainWindow", "Close panel"))
        self.close_button.clicked.connect(dock.close)
        for button in (self.float_button, self.close_button):
            button.setIconSize(QSize(14, 14))
            button.setAutoRaise(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(4)
        layout.addWidget(self.title, 1)
        layout.addWidget(self.float_button)
        layout.addWidget(self.close_button)

    def set_theme(self, tokens: Mapping[str, str]) -> None:
        quiet = {**tokens, "text2": tokens["text3"]}
        self.float_button.setIcon(themed_icon("picture-in-picture-2", quiet, 14))
        self.close_button.setIcon(themed_icon("x", quiet, 14))


def main(argv: list[str] | None = None) -> int:
    """Avvio con ``uv run astrotwo``."""
    from PySide6.QtGui import QSurfaceFormat

    from astrotwo.ui.sky_renderer_gl import surface_format

    QSurfaceFormat.setDefaultFormat(surface_format())  # OpenGL 4.1 core profile prima della QApplication (41)
    app = QApplication(sys.argv if argv is None else argv)
    app.setOrganizationDomain("pages.dev")  # impostazioni in dev.pages.astrotwo (01 §6)
    app.setApplicationName("astrotwo")
    app.setApplicationDisplayName("AstroTwo")
    app.setApplicationVersion(astrotwo.__version__)
    window = MainWindow()
    window.show()
    QTimer.singleShot(0, window.raise_)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
