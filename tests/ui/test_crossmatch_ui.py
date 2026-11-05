# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Incrocio per posizione nell'interfaccia (sprint B2, D15-10): T22 del ``40`` e T9 del ``42``.

Dialogo "Cross-match catalogs…" (Data e menu contestuale della tabella), comando ``catalog.crossmatch`` in
cronologia, nuovo catalogo nel cielo e nel pannello Tabella, report, errori in finestra, Riesegui identico.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialogButtonBox

from tests.core.test_commands_crossmatch import RA, DEC  # noqa: F401 - stesse stelle dei test del 05
from tests.core.test_crossmatch import make_table, offset
from tests.ui.test_main_window import make_window, settings_path, wait_idle  # noqa: F401 - fixture


@pytest.fixture
def window(qtbot, settings_path, cache):  # noqa: F811 - fixture locale
    win = make_window(qtbot, settings_path, cache)
    yield win
    win.confirm = lambda title, text: True
    win.close()


def last(win, name):
    return [e for e in win.session.history.entries if e.command.name == name][-1]


def open_two(qtbot, win, tmp_path, *, epoch_a="J2016.0", epoch_b="J2016.0"):
    make_table(tmp_path / "a.xml", list(RA), list(DEC), epoch=epoch_a, ids=[f"a{k}" for k in range(len(RA))])
    shifted = [offset(RA[k], DEC[k], 40.0, 0.5) for k in range(6)]
    make_table(tmp_path / "b.xml", [p[0] for p in shifted], [p[1] for p in shifted], epoch=epoch_b,
               ids=[f"b{k}" for k in range(6)])
    for name in ("a.xml", "b.xml"):
        win.submit("catalog.open_file", {"file": {"path": str(tmp_path / name)}})
    wait_idle(qtbot, win)
    return "L1", "L2"


def accept(qtbot, win, dialog):
    dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    wait_idle(qtbot, win)


def test_t22_menu_needs_two_catalogs(qtbot, window):
    win = window
    data = next(a.menu() for a in win.menuBar().actions() if a.text() == "Data")
    assert "Cross-match catalogs…" in [a.text() for a in data.actions()]
    win.act_crossmatch.trigger()
    assert win.modals and win.modals[-1][0] == "Cross-match catalogs"
    assert "at least two catalogs" in win.modals[-1][1]


def test_t22_dialog_best_new_catalog_report_and_rerun(qtbot, window, tmp_path):
    win = window
    open_two(qtbot, win, tmp_path)
    win.act_crossmatch.trigger()
    dialog = win.last_crossmatch_dialog
    assert (dialog.layer_a.currentData(), dialog.layer_b.currentData()) == ("L1", "L2")
    assert dialog.mode.currentData() == "best" and "nearest row of B" in dialog.mode_help.text()
    assert (dialog.max_sep.value(), dialog.unit.currentData()) == (2.0, "arcsec")  # default (D15-10 (a))
    assert (dialog.method.currentData(), dialog.frame.currentData()) == ("local", "icrs")
    assert "J2016.0" in dialog.epochs.text() and "differ" not in dialog.epochs.text()
    accept(qtbot, win, dialog)
    entry = last(win, "catalog.crossmatch")
    assert entry.result.status == "ok", entry.result.error
    assert entry.command.requested_by.source == "menu"
    assert entry.command.parameters == {"layer_a": "L1", "layer_b": "L2", "mode": "best",
                                        "max_sep": {"value": 2.0, "unit": "arcsec"}, "method": "local",
                                        "frame": "icrs", "force_body": False}
    new = entry.result.layers_created[0]
    # nuovo catalogo nel cielo (livello disegnato dal 41) e nel pannello Tabella (scheda del 42)
    assert new in win.catalog_panel.pages
    assert win.session.workspace.state.layer(new).kind == "catalog"
    assert "xmatch_sep" in win.session.workspace.state.layer(new).data.table.colnames
    # report visibile subito, salvato nel risultato
    report = win.last_crossmatch_report
    text = report.text.toPlainText()
    assert "Pairs: 6" in text and "Separation column: xmatch_sep (arcsec)" in text
    assert entry.result.values["crossmatch"]["report_text"] in text
    # riaperto dal menu contestuale della scheda del nuovo catalogo
    menu = win._table_context_menu(new, None)
    show = next(a for a in menu.actions() if a.text() == "Show cross-match report")
    show.trigger()
    assert win.last_crossmatch_report is not report
    # Riesegui dalla cronologia: stesso comando, stesse righe
    rows = [tuple(r) for r in win.session.workspace.state.layer(new).data.table.as_array().tolist()]
    win.history.table.selectRow(entry.number - 1)
    win.history.rerun_button.click()
    wait_idle(qtbot, win)
    again = last(win, "catalog.crossmatch")
    assert again.command.requested_by.source == "history" and again.command.parameters == entry.command.parameters
    copy = win.session.workspace.state.layer(again.result.layers_created[0]).data.table
    assert [tuple(r) for r in copy.as_array().tolist()] == rows


def test_t22_context_menu_presets_a_and_modes(qtbot, window, tmp_path):
    win = window
    open_two(qtbot, win, tmp_path, epoch_b="J2000.0")
    menu = win._table_context_menu("L2", None)
    item = next(a for a in menu.actions() if a.text() == "Cross-match with another catalog…")
    assert item.isEnabled()
    item.trigger()
    dialog = win.last_crossmatch_dialog
    assert (dialog.layer_a.currentData(), dialog.layer_b.currentData()) == ("L2", "L1")
    assert "differ" in dialog.epochs.text() and "EPOCH_DIFFERS" in dialog.epochs.text()
    dialog.mode.setCurrentIndex(dialog.mode.findData("none"))
    dialog.unit.setCurrentIndex(dialog.unit.findData("arcmin"))
    dialog.max_sep.setValue(0.05)
    dialog.method.setCurrentIndex(dialog.method.findData("cds"))
    assert not dialog.frame.isEnabled() and dialog.frame.currentData() == "icrs"  # CDS: solo ICRS
    dialog.method.setCurrentIndex(dialog.method.findData("local"))
    accept(qtbot, win, dialog)
    entry = last(win, "catalog.crossmatch")
    assert entry.command.requested_by.source == "mouse"
    assert entry.command.parameters["max_sep"] == {"value": 0.05, "unit": "arcmin"}
    assert entry.result.values["crossmatch"]["unmatched"] == 0
    assert "EPOCH_DIFFERS" in [w.code for w in entry.result.warnings]
    assert any(m[1] == "EPOCH_DIFFERS" for m in win.messages.messages)
    assert "EPOCH_DIFFERS" in win.last_crossmatch_report.text.toPlainText()


def test_t22_errors_are_shown_and_nothing_is_created(qtbot, window, tmp_path):
    win = window
    open_two(qtbot, win, tmp_path)
    win.act_crossmatch.trigger()
    dialog = win.last_crossmatch_dialog
    dialog.max_sep.setValue(0.0)
    accept(qtbot, win, dialog)
    entry = last(win, "catalog.crossmatch")
    assert entry.result.error.code == "MAX_SEP_INVALID"
    assert win.modals[-1][0] == "The cross-match was not run" and win.modals[-1][1].startswith("MAX_SEP_INVALID")
    assert [layer.id for layer in win.session.workspace.state.layers] == ["L1", "L2"]
    # CDS oltre 180″
    win.act_crossmatch.trigger()
    dialog = win.last_crossmatch_dialog
    dialog.method.setCurrentIndex(dialog.method.findData("cds"))
    dialog.unit.setCurrentIndex(dialog.unit.findData("arcmin"))
    dialog.max_sep.setValue(4.0)
    accept(qtbot, win, dialog)
    error = last(win, "catalog.crossmatch").result.error
    assert (error.code, error.params["reason"]) == ("MAX_SEP_INVALID", "range_cds")


def test_t22_italian_dialog_texts(qtbot, settings_path, cache, tmp_path):  # noqa: F811
    from PySide6.QtCore import QSettings

    QSettings(settings_path, QSettings.Format.IniFormat).setValue("language", "it")
    win = make_window(qtbot, settings_path, cache)
    try:
        assert win.act_crossmatch.text() == "Incrocia cataloghi…"
        open_two(qtbot, win, tmp_path)
        win.act_crossmatch.trigger()
        dialog = win.last_crossmatch_dialog
        assert dialog.windowTitle() == "Incrocia cataloghi"
        assert dialog.mode.itemText(0) == "Migliore (la più vicina)"
    finally:
        win.confirm = lambda title, text: True
        win.close()


def test_t22_no_pair_gives_an_empty_catalog(qtbot, window, tmp_path):
    """D42-1 (7): un incrocio senza coppie crea comunque il livello (vuoto) con NO_MATCH; cielo e tabella reggono."""
    win = window
    open_two(qtbot, win, tmp_path)
    win.submit("catalog.crossmatch", {"layer_a": "L1", "layer_b": "L2", "max_sep": {"value": 1.0, "unit": "mas"}})
    wait_idle(qtbot, win)
    entry = last(win, "catalog.crossmatch")
    assert entry.result.status == "ok" and "NO_MATCH" in [w.code for w in entry.result.warnings]
    new = entry.result.layers_created[0]
    assert len(win.session.workspace.state.layer(new).data.table) == 0 and new in win.catalog_panel.pages
    assert win.catalog_panel.pages[new].model.rowCount() == 0
    win.sky.update()
    qtbot.wait(50)
