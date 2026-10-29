# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Finestra Licenze e About ridotto (60 §3.9, T6–T8; 40 §3.3), piattaforma ``offscreen``."""

from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton

import astrotwo
from astrotwo.ui.export_view import DSS_TEXT, SIMBAD_TEXT
from astrotwo.ui.licenses_dialog import LicensesDialog
from astrotwo.ui.main_window import load_translations
from tests.ui.test_main_window import make_window, settings_path, trigger  # noqa: F401 - fixture

ROOT = Path(__file__).resolve().parents[2]


def test_t6_licenses_window_from_the_menu(qtbot, settings_path, cache):
    win = make_window(qtbot, settings_path, cache)
    help_menu = [a for a in win.menuBar().actions() if a.text() == "Help"][0].menu()
    names = [a.objectName() for a in help_menu.actions()]
    assert names[names.index("about") + 1] == "licenses"  # subito dopo About (§3.9)
    assert win.findChild(QAction, "licenses").menuRole() == QAction.MenuRole.ApplicationSpecificRole
    trigger(win, "licenses")
    dialog = win.findChild(LicensesDialog)
    assert dialog is not None and dialog.isVisible() and not dialog.isModal()
    assert [dialog.tabs.tabText(i) for i in range(4)] == ["AstroTwo", "Third-party", "Sources", "Data credits"]
    assert (ROOT / "LICENSE").read_text(encoding="utf-8") in dialog.tab_text("astrotwo")
    assert dialog.tab_text("third_party") == (ROOT / "THIRD_PARTY_LICENSES").read_text(encoding="utf-8")
    assert "pyside-setup-everywhere-src-6.12.0.zip" in dialog.tab_text("sources")
    credits = dialog.tab_text("data_credits")
    assert SIMBAD_TEXT in credits and DSS_TEXT in credits and "Acknowledgement text not yet verified." in credits
    trigger(win, "licenses")  # una sola finestra
    assert len(win.findChildren(LicensesDialog)) == 1
    win.close()


def test_t6_licenses_window_in_italian(qtbot):
    try:
        load_translations("it")
        dialog = LicensesDialog()
        qtbot.addWidget(dialog)
        assert dialog.windowTitle() == "Licenze"
        assert [dialog.tabs.tabText(i) for i in range(4)] == ["AstroTwo", "Terze parti", "Sorgenti",
                                                              "Crediti dei dati"]
        assert "Testo di riconoscimento non ancora verificato." in dialog.tab_text("data_credits")
        assert "GNU GENERAL PUBLIC LICENSE" in dialog.tab_text("astrotwo")  # i testi di licenza non si traducono
    finally:
        load_translations("en")


def test_t7_missing_file_shown_in_the_tab(qtbot, tmp_path):
    (tmp_path / "LICENSE").write_text("GPL\n", encoding="utf-8")
    dialog = LicensesDialog(folder=tmp_path)
    qtbot.addWidget(dialog)
    assert dialog.tab_text("sources") == f"The license file SOURCES.txt was not found in {tmp_path / 'SOURCES.txt'}."
    assert "GPL" in dialog.tab_text("astrotwo")


def test_search_finds_and_wraps(qtbot):
    dialog = LicensesDialog()
    qtbot.addWidget(dialog)
    tab = dialog.tabs.widget(0)
    tab.search.setText("GNU GENERAL PUBLIC LICENSE")
    assert tab.find_next()  # senza distinguere maiuscole e minuscole
    assert tab.text.textCursor().selectedText().upper() == "GNU GENERAL PUBLIC LICENSE"
    tab.search.setText("testo che non esiste in nessuna licenza")
    assert not tab.find_next()


def test_t8_about_is_short_with_licenses_button(qtbot, settings_path, cache):
    win = make_window(qtbot, settings_path, cache)
    dialog = win.about_dialog()
    labels = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "0.1.0-beta.2" in labels and astrotwo.__version__ in labels and "Guido Ratti" in labels
    assert "General Public License" in labels and not dialog.findChildren(QPlainTextEdit)
    dialog.findChild(QPushButton, "aboutLicenses").click()
    assert win.findChild(LicensesDialog).isVisible()
    dialog.close()
    win.close()
