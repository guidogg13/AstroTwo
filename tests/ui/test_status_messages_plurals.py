# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Problemi della prova a mano del proprietario del 2026-11-10 (sprint D5b, ``40`` §3.5, §3.7, §3.9; T25, T26).

1. Barra di stato: il comando in corso si mostra con un titolo leggibile e tradotto, mai con il nome interno, e la sua
   etichetta non copre mai la barra di avanzamento né «Annulla», a nessuna larghezza della finestra.
2. Plurali giusti in inglese e in italiano (interfaccia e catalogo dei messaggi).
3. Pannello Messaggi: un messaggio lungo si legge tutto (suggerimento, Dettagli…, doppio clic, Copia).
4. Nome «AstroTwo» nella barra dei menu anche avviando dal codice.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication

from astrotwo.core.commands import ResultMessage, default_registry
from astrotwo.messages_catalog import CATALOG, message_text, placeholders
from astrotwo.ui import main_window as mw
from astrotwo.ui.message_view import counted
from tests.ui.test_main_window import make_window, settings_path  # noqa: F401 - fixture


# =============================================================================
# T25 — barra di stato


def all_command_names() -> list[str]:
    registry = default_registry()
    mw.register_analysis_commands(registry)
    return sorted(s.name for s in registry.specs()) + ["session.open"]


def test_t25_every_command_has_a_readable_title(qtbot, settings_path, cache):  # noqa: F811
    win = make_window(qtbot, settings_path, cache)
    names = all_command_names()
    titles = {name: win.status.command_title(name) for name in names}
    fallback = win.status.command_title("no.such_command")
    for name, title in titles.items():
        assert title != fallback, f"{name}: senza titolo"
        assert name not in title and "." not in title.rstrip("…"), f"{name}: titolo con il nome interno"
        assert title.endswith("…")
    assert len(set(titles.values())) == len(titles)  # un titolo diverso per ogni comando
    win.close()


@pytest.mark.parametrize("width", [1400, 900, 0])  # 0 = la finestra più stretta possibile
def test_t25_running_command_never_covers_cancel(qtbot, settings_path, cache, width):  # noqa: F811
    win = make_window(qtbot, settings_path, cache)
    win.status.show_network(1, 12)
    win.status.show_running("catalog.load_region")
    win.resize(max(width, win.minimumSizeHint().width()), 700)
    qtbot.wait(50)
    bar = win.status
    label, progress, cancel = bar.command_label, bar.progress_bar, bar.cancel_button
    assert label.isVisible() and progress.isVisible() and cancel.isVisible()
    assert label.full_text == "Loading catalog…" and "catalog.load_region" in label.toolTip()
    assert label.geometry().right() < progress.geometry().left() < cancel.geometry().left()
    assert progress.geometry().right() < cancel.geometry().left()
    assert cancel.geometry().right() <= bar.width()
    assert label.width() >= label.minimumSizeHint().width() > 0  # l'inizio del titolo resta visibile
    assert QFontMetrics(label.font()).horizontalAdvance(label.text()) <= label.width()  # il testo entra
    assert label.text() == label.full_text or label.text().endswith("…")
    # passo n di m: stesso titolo con il passo, mai il nome interno
    from astrotwo.core.commands import ProgressReport

    bar.show_running("object.profile", ProgressReport(2, 5, ""))
    assert label.full_text == "Building the object profile… · step 2 of 5"
    bar.show_idle()
    assert not label.isVisible() and label.full_text == ""
    win.close()


# =============================================================================
# T26 — plurali


def test_t26_counted_and_status_bar_plurals(qtbot, settings_path, cache):  # noqa: F811
    assert [counted(n, "%1 row", "%1 rows") for n in (0, 1, 2)] == ["0 rows", "1 row", "2 rows"]
    win = make_window(qtbot, settings_path, cache)
    bar = win.status
    for (commands, tiles), text in {(1, 0): "Network: 1 command, 0 tiles", (0, 1): "Network: 0 commands, 1 tile",
                                    (2, 3): "Network: 2 commands, 3 tiles"}.items():
        bar.show_network(commands, tiles)
        assert bar.network_label.text() == text
    win.close()


def test_t26_italian_plurals_in_the_interface(qtbot, settings_path, cache):  # noqa: F811
    QSettings(settings_path, QSettings.Format.IniFormat).setValue("language", "it")
    try:
        win = make_window(qtbot, settings_path, cache)
        assert win.language == "it"
        bar = win.status
        bar.show_network(1, 1)
        assert bar.network_label.text() == "Rete: 1 comando, 1 tile"
        bar.show_network(2, 0)
        assert bar.network_label.text() == "Rete: 2 comandi, 0 tile"
        assert bar.command_title("catalog.load_region") == "Caricamento catalogo…"
        win.close()
    finally:
        mw.load_translations("en")


@pytest.mark.parametrize(("code", "params", "en", "it"), [
    ("ROWS_EXCLUDED", {"count": 1}, "1 row without a position excluded.", "1 riga senza posizione esclusa."),
    ("ROWS_EXCLUDED", {"count": 0}, "0 rows without a position excluded.", "0 righe senza posizione escluse."),
    ("ROWS_EXCLUDED", {"count": 3}, "3 rows without a position excluded.", "3 righe senza posizione escluse."),
    ("SELECTION_NOT_TWO_SOURCES", {"count": 1}, "1 source selected: 2 are required.",
     "Selezionata 1 sorgente: ne servono 2."),
    ("SELECTION_NOT_TWO_SOURCES", {"count": 3}, "3 sources selected: 2 are required.",
     "Selezionate 3 sorgenti: ne servono 2."),
    ("PROFILE_PLANETS_COMPOSITE", {"count": 1, "table": "pscomppars", "references": 2},
     "1 planet from pscomppars: the parameters may come from different works (2 distinct references).",
     "1 pianeta da pscomppars: i parametri possono venire da lavori diversi (2 riferimenti distinti)."),
])
def test_t26_catalog_plural_forms(code, params, en, it):
    assert message_text(code, params, "en") == en
    assert message_text(code, params, "it") == it


def test_t26_catalog_plural_forms_are_well_formed():
    """Ogni forma ``{n|uno|molti}`` usa un parametro numerico dichiarato; con n = 1 e n = 2 nessuna forma resta nel
    testo e le due lingue hanno gli stessi segnaposto."""
    import re

    form = re.compile(r"\{([A-Za-z_]\w*)\|([^|{}]*)\|([^|{}]*)\}")
    found = 0
    for code, entry in CATALOG.items():
        texts = [(entry.en, entry.it, entry.params)] + [(v.en, v.it, v.params) for v in entry.variants.values()]
        for en, it, params in texts:
            declared = {p.name: p.type for p in params}
            for text in (en, it):
                for name, one, many in form.findall(text):
                    found += 1
                    assert declared.get(name) in ("integer", "number"), f"{code}: {name} non è un numero"
                    assert one and many and one != many, f"{code}: forme {one!r} {many!r}"
            assert placeholders(en) == placeholders(it), code
    assert found >= 60


def test_t26_ai_panel_counts():
    from astrotwo.ai.chat_assistant import TokenCount
    from astrotwo.ui.ai_panel import token_counts

    assert token_counts(TokenCount(1, 1)) == "1 input token, 1 output token"
    assert token_counts(TokenCount(0, 2)) == "0 input tokens, 2 output tokens"


# =============================================================================
# T26 — messaggi lunghi


def test_t26_long_message_can_be_read_whole(qtbot, settings_path, cache):  # noqa: F811
    win = make_window(qtbot, settings_path, cache)
    panel = win.messages
    long_url = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync?" + "x" * 400
    message = ResultMessage("SERVICE_ERROR", f"{long_url}: risposta HTTP 404 senza VOTable",
                            {"url": long_url, "status": 404, "reason": "http_no_votable"})
    panel.add(7, message, error=True)
    row = panel.table.rowCount() - 1
    shown = panel.messages[-1][2]
    assert long_url in shown
    for col in range(3):  # suggerimento su ogni cella con il testo completo e i dettagli
        tip = panel.table.item(row, col).toolTip()
        assert tip.startswith(f"#7 SERVICE_ERROR: {shown}") and message.text in tip
    assert not panel.details_button.isEnabled() and not panel.copy_button.isEnabled()
    panel.table.selectRow(row)
    assert panel.details_button.isEnabled() and panel.copy_button.isEnabled()
    QApplication.clipboard().clear()
    panel.copy_button.click()
    assert QApplication.clipboard().text() == panel.full_texts[row]
    assert long_url in QApplication.clipboard().text() and "404" in QApplication.clipboard().text()
    # doppio clic = Dettagli…: finestra con il testo completo, selezionabile, e Copia
    panel.table.itemDoubleClicked.emit(panel.table.item(row, 2))  # il pannello può essere chiuso nella finestra
    dialog = panel.last_dialog
    assert dialog is not None and dialog.isVisible()
    from PySide6.QtWidgets import QPlainTextEdit

    text = dialog.findChild(QPlainTextEdit)
    assert text.toPlainText() == panel.full_texts[row] and text.isReadOnly()
    dialog.close()
    panel.details_button.click()
    assert panel.last_dialog is not dialog and panel.last_dialog.isVisible()
    panel.last_dialog.close()
    win.close()


# =============================================================================
# Nome dell'app nella barra dei menu


@pytest.mark.skipif(sys.platform != "darwin", reason="solo macOS")
def test_app_name_in_the_menu_bar_when_started_from_the_code():
    """In un processo nuovo (come ``uv run astrotwo``): ``CFBundleName`` del bundle principale diventa «AstroTwo»
    prima della ``QApplication``; nessun file scritto."""
    code = ("import ctypes, ctypes.util\n"
            "from astrotwo.ui.main_window import set_macos_app_name\n"
            "assert set_macos_app_name('AstroTwo') is True\n"
            "from PySide6.QtWidgets import QApplication\n"
            "app = QApplication(['x', '-platform', 'offscreen'])\n"
            "assert set_macos_app_name('AstroTwo') is True\n"
            "print('ok')\n")
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0 and done.stdout.strip() == "ok", done.stderr


def test_app_name_outside_macos_does_nothing(monkeypatch):
    monkeypatch.setattr(mw.sys, "platform", "linux")
    assert mw.set_macos_app_name() is False


def test_app_name_in_the_built_app():
    """Nell'app costruita il nome viene dall'Info.plist (60 §3.2): verificato sul generatore, senza costruire."""
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "build_app.py"
    spec = importlib.util.spec_from_file_location("build_app_names", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_app_names"] = module
    spec.loader.exec_module(module)
    keys = module.info_plist("0.1.0-beta.5", 5, None, False)
    assert keys["CFBundleName"] == keys["CFBundleDisplayName"] == keys["CFBundleExecutable"] == "AstroTwo"


def test_translate_context_exists():
    assert QCoreApplication.translate("TokenCounts", "%1 input token") == "%1 input token"
