# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Cone search e query ADQL nell'interfaccia (sprint B3, decisioni del proprietario del 2026-11-06): T23 del ``40``,
T10 e T11 del ``42``.

Servizi SCS e TAP simulati (server HTTP locale) come voci dell'elenco del 14; i valori attesi (centro della vista in
ICRS, posizione della sorgente) vengono dal 10 e dal 05 chiamati direttamente, mai scritti a mano.
"""

from __future__ import annotations

import dataclasses
import json

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialogButtonBox

import astrotwo.core.vo_protocols as vo
from astrotwo.core.commands import catalog_positions, sky_json
from astrotwo.core.coordinates_wcs import SkyFrame
from astrotwo.ui.vo_query_dialogs import ADQL_EXAMPLES, VIEW_COMMENT_PREFIX, view_values
from tests.core.test_commands_vo_queries import NO_COOSYS
from tests.core.test_vo_protocols import tap_sync_route, uws_service, votable_route, votable_text
from tests.ui.test_main_window import make_window, settings_path, wait_idle  # noqa: F401 - fixture


@pytest.fixture
def listed(service, monkeypatch):
    urls = {"nasa-irsa-allwise-scs": service.url + "/scs?table=t", "esa-gaia-tap": service.url + "/tap"}
    entries = tuple(dataclasses.replace(e, url=urls.get(e.id, e.url)) for e in vo.BUILTIN_SERVERS)
    monkeypatch.setattr(vo, "BUILTIN_SERVERS", entries)
    service.routes["/scs"] = votable_route(votable_text(5))
    service.routes["/tap/sync"] = tap_sync_route(6)
    return service


@pytest.fixture
def window(qtbot, settings_path, cache, listed):  # noqa: F811 - fixture locale
    win = make_window(qtbot, settings_path, cache)
    win.submit("view.set_zoom", {"scale": {"value": 1.0, "unit": "arcsec"}, "window": win.view_window()})
    win.go_to("10.5 -3.2")
    wait_idle(qtbot, win)
    yield win
    win.confirm = lambda title, text: True
    win.close()


def last(win, name):
    return [e for e in win.session.history.entries if e.command.name == name][-1]


def accept(qtbot, win, dialog):
    dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    wait_idle(qtbot, win)


def cone(qtbot, win):
    dialog = win.cone_search_dialog()
    accept(qtbot, win, dialog)
    return last(win, "catalog.cone_search")


# =============================================================================
# Menu e cone search


def test_t23_menu_order(window):
    data = next(a.menu() for a in window.menuBar().actions() if a.text() == "Data")
    texts = [a.text() for a in data.actions()]
    assert texts == ["HiPS survey…", "Catalog in view…", "Cone search…", "ADQL query…", "", "Cross-match catalogs…"]


def test_t23_cone_search_view_centre(qtbot, window, listed):
    win = window
    dialog = win.cone_search_dialog()
    assert dialog.center_view.isChecked() and dialog.chooser.entry_id() == "nasa-irsa-allwise-scs"
    view = win.session.workspace.state.view
    assert dialog.unit.currentData() == "arcmin"
    assert dialog.radius.value() == pytest.approx(float(view.geometry.field_radius.to_value("arcmin")), abs=1e-4)
    accept(qtbot, win, dialog)
    entry = last(win, "catalog.cone_search")
    assert entry.result.status == "ok", entry.result.error
    assert entry.command.requested_by.source == "menu"
    assert entry.command.parameters["center"] == sky_json(view.center)  # centro della vista com'è nello stato
    assert entry.command.parameters["service"] == "nasa-irsa-allwise-scs"
    assert entry.command.parameters["url"] == listed.url + "/scs?table=t"
    new = entry.result.layers_created[0]
    assert new in win.catalog_panel.pages and win.session.workspace.state.layer(new).kind == "catalog"


def test_t23_cone_search_selected_source_typed_and_truncation(qtbot, window, listed):
    win = window
    first = cone(qtbot, win)
    layer_id = first.result.layers_created[0]
    win.submit("catalog.select", {"layer": layer_id, "rows": [2]})
    wait_idle(qtbot, win)
    dialog = win.cone_search_dialog()
    assert dialog.center_source.isEnabled()
    dialog.center_source.setChecked(True)
    accept(qtbot, win, dialog)
    entry = last(win, "catalog.cone_search")
    coords, _ = catalog_positions(win.session.workspace.state.layer(layer_id).data, [2])
    expected = sky_json(SkyFrame(coord=coords.coord[0], epoch=coords.epoch))
    assert entry.command.parameters["center"] == expected and expected["epoch"] == "J2016.000"  # epoca del 13
    # coordinate scritte (galattiche, J2000.0), righe massime sotto quelle del servizio
    listed.routes["/scs"] = votable_route(votable_text(8))
    dialog = win.cone_search_dialog()
    dialog.typed.setText("120 30")
    dialog.center_typed.setChecked(True)
    dialog.frame.setCurrentIndex(dialog.frame.findData("galactic"))
    dialog.epoch.setText("J2000.0")
    dialog.max_rows.setValue(3)
    accept(qtbot, win, dialog)
    entry = last(win, "catalog.cone_search")
    assert entry.result.status == "ok", entry.result.error
    center = entry.command.parameters["center"]
    assert (center["frame"], center["epoch"], center["lon"]["value"], center["lat"]["value"]) == (
        "galactic", "J2000.0", 120.0, 30.0)
    assert [m for m in win.messages.messages if m[1] == "ROW_LIMIT_EXCEEDED"]
    assert entry.result.values["query"]["truncated"] is True
    # coordinate non leggibili: il dialogo resta aperto, nessun comando
    count = len(win.session.history)
    dialog = win.cone_search_dialog()
    dialog.center_typed.setChecked(True)
    dialog.typed.setText("Pleiadi")
    dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    assert dialog.isVisible() and "not readable" in dialog.error.text()
    dialog.reject()
    assert len(win.session.history) == count


def test_t23_columns_dialog_without_coosys(qtbot, window, listed):
    win = window
    win.auto_column_dialogs = True
    listed.routes["/scs"] = votable_route(NO_COOSYS)
    entry = cone(qtbot, win)
    assert entry.result.status == "ok" and "POSITION_COLUMNS_REQUIRED" in [w.code for w in entry.result.warnings]
    assert win.column_dialog is not None and win.column_dialog.isVisible()
    win.column_dialog.reject()


# =============================================================================
# Query ADQL


def adql(win):
    dialog = win.adql_dialog()
    dialog.chooser.combo.setCurrentIndex(dialog.chooser.combo.findData("esa-gaia-tap"))
    return dialog


def test_t23_adql_invalid_blocked_with_position(qtbot, window, listed):
    win = window
    dialog = adql(win)
    assert dialog.editor.font().fixedPitch() or dialog.editor.font().styleHint() is not None
    dialog.editor.setPlainText("SELECT *\nFROM t WHERE a = 'x")
    dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    assert dialog.isVisible() and dialog.error_position == 26
    assert "ADQL_INVALID" in dialog.error.text() and "line 2, column 18" in dialog.error.text()
    marks = dialog.editor.extraSelections()
    assert len(marks) == 1 and marks[0].cursor.selectionStart() == 26 and marks[0].cursor.selectionEnd() == 27
    assert dialog.editor.textCursor().position() == 26
    dialog.reject()
    assert listed.requests == [] and not [e for e in win.session.history if e.command.name == "catalog.tap_query"]


def test_t23_adql_service_rejects_shows_its_text(qtbot, window, listed):
    win = window
    error = votable_text(0, status="ERROR").replace(
        '<INFO name="QUERY_STATUS" value="ERROR"/>',
        '<INFO name="QUERY_STATUS" value="ERROR">Table stelle_x does not exist &lt;here&gt;</INFO>')
    listed.routes["/tap/sync"] = lambda r: (400, "application/x-votable+xml", error)
    dialog = adql(win)
    dialog.editor.setPlainText("SELECT * FROM stelle_x")
    accept(qtbot, win, dialog)
    assert last(win, "catalog.tap_query").result.error.code == "ADQL_INVALID"
    title, text = win.modals[-1]
    assert title == "The query was not run"
    assert text.endswith("Message of the service (as received):\nTable stelle_x does not exist <here>")
    # la query si riapre con l'ultimo testo e servizio della sessione
    again = win.adql_dialog()
    assert again.editor.toPlainText() == "SELECT * FROM stelle_x" and again.chooser.entry_id() == "esa-gaia-tap"
    again.reject()


def test_t23_adql_insert_view_example_and_sync(qtbot, window, listed):
    win = window
    dialog = adql(win)
    dialog.choose_example(1)
    assert dialog.editor.toPlainText() == ADQL_EXAMPLES["esa-gaia-tap"][0][1]
    ra, dec, radius, epoch = view_values(win.session.workspace.state.view)  # conversione del 10
    dialog.insert_view_values()
    text = dialog.editor.toPlainText()
    assert f"CIRCLE('ICRS', {ra:.10g}, {dec:.10g}, {radius:.10g})" in text
    assert text.splitlines()[-1] == (f"{VIEW_COMMENT_PREFIX}, ICRS, degrees; epoch of the centre: "
                                     f"{epoch if epoch is not None else 'not known (not assumed)'}")
    dialog.insert_view_values()  # una seconda volta: stessa CIRCLE, un solo commento
    assert dialog.editor.toPlainText().count(VIEW_COMMENT_PREFIX) == 1
    dialog.editor.setPlainText("SELECT * FROM stelle\nWHERE 1 = CONTAINS(POINT('ICRS', ra, dec), "
                               "CIRCLE('ICRS', 1, 2, 3))")
    dialog.insert_view_values()
    dialog.max_rows.setValue(4)
    accept(qtbot, win, dialog)
    entry = last(win, "catalog.tap_query")
    assert entry.result.status == "ok", entry.result.error
    sent = listed.requests[-1]["params"]
    assert VIEW_COMMENT_PREFIX not in sent["QUERY"] and f"{ra:.10g}" in sent["QUERY"] and sent["MAXREC"] == "4"
    assert VIEW_COMMENT_PREFIX in entry.command.parameters["adql"]
    assert entry.command.parameters["mode"] == "sync"
    assert [m for m in win.messages.messages if m[1] == "ROW_LIMIT_EXCEEDED"]
    assert entry.result.layers_created[0] in win.catalog_panel.pages


def test_t23_adql_async_and_cancel(qtbot, window, listed):
    win = window
    uws_service(listed, ["EXECUTING", "COMPLETED"], total=4)
    dialog = adql(win)
    dialog.editor.setPlainText("SELECT * FROM stelle")
    dialog.asynchronous.setChecked(True)
    assert dialog.timeout.isEnabled() and dialog.timeout.value() == 600
    accept(qtbot, win, dialog)
    entry = last(win, "catalog.tap_query")
    assert entry.result.status == "ok" and entry.command.parameters["mode"] == "async"
    assert entry.command.parameters["async_timeout"] == {"value": 600.0, "unit": "s"}
    # lavoro che non finisce: annullato dalla barra di stato
    state = uws_service(listed, ["EXECUTING"])
    dialog = adql(win)
    dialog.editor.setPlainText("SELECT * FROM altre")
    dialog.asynchronous.setChecked(True)
    dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    qtbot.waitUntil(lambda: state["phase"] == "EXECUTING", timeout=10000)
    layers = len(win.session.workspace.state.layers)
    win.status.cancelRequested.emit()
    wait_idle(qtbot, win)
    entry = last(win, "catalog.tap_query")
    assert entry.result.status == "cancelled" and entry.result.error.code == "COMMAND_CANCELLED"
    assert state["posted"] == ["RUN", "ABORT"] and len(win.session.workspace.state.layers) == layers


# =============================================================================
# Miei server, Riesegui, incrocio del risultato


def test_t23_personal_server_saved_and_removed(qtbot, window, listed, settings_path):  # noqa: F811
    win = window
    listed.routes["/mine"] = votable_route(votable_text(3))
    dialog = win.cone_search_dialog()
    chooser = dialog.chooser
    chooser.combo.setCurrentIndex(chooser.combo.findData("__manual__"))
    assert not chooser.save_button.isEnabled()
    chooser.url.setText(listed.url + "/mine")
    assert chooser.save_button.isEnabled() and not chooser.remove_button.isEnabled()
    chooser.ask_save("Il mio SCS")
    wait_idle(qtbot, win)
    assert last(win, "vo.add_server").result.status == "ok"
    saved = json.loads(QSettings(settings_path, QSettings.Format.IniFormat).value("vo/personal_servers"))
    assert saved == [{"id": "my-scs-1", "name": "Il mio SCS", "protocol": "scs", "url": listed.url + "/mine"}]
    assert chooser.entry_id() == "my-scs-1" and chooser.combo.currentText() == "Il mio SCS (my server)"
    assert chooser.remove_button.isEnabled()
    accept(qtbot, win, dialog)
    assert last(win, "catalog.cone_search").result.values["query"]["service_name"] == "Il mio SCS"
    # una nuova finestra della stessa sessione rilegge le preferenze
    dialog = win.cone_search_dialog()
    dialog.chooser.combo.setCurrentIndex(dialog.chooser.combo.findData("my-scs-1"))
    dialog.chooser.remove_button.click()
    wait_idle(qtbot, win)
    assert last(win, "vo.remove_server").result.status == "ok"
    assert dialog.chooser.combo.findData("my-scs-1") < 0
    assert json.loads(QSettings(settings_path, QSettings.Format.IniFormat).value("vo/personal_servers")) == []
    dialog.reject()


def test_t23_personal_servers_loaded_at_startup(qtbot, settings_path, cache, listed):  # noqa: F811
    items = [{"id": "my-tap-1", "name": "Mio TAP", "protocol": "tap", "url": "https://example.org/tap"},
             {"id": "rotto", "protocol": "tap"}]
    QSettings(settings_path, QSettings.Format.IniFormat).setValue("vo/personal_servers", json.dumps(items))
    win = make_window(qtbot, settings_path, cache)
    try:
        assert [e.id for e in win.registry.servers.personal_servers()] == ["my-tap-1"]
        assert [m for m in win.messages.messages if m[1] == "PREFERENCE_VALUE_INVALID"]
        dialog = win.adql_dialog()
        assert dialog.chooser.combo.findData("my-tap-1") >= 0
        dialog.reject()
    finally:
        win.confirm = lambda title, text: True
        win.close()


def test_t23_rerun_identical_and_crossmatch(qtbot, window, listed):
    win = window
    entry = cone(qtbot, win)
    hits = listed.hits("/scs")
    win.rerun([entry])
    wait_idle(qtbot, win)
    again = last(win, "catalog.cone_search")
    assert again.command.requested_by.source == "history" and again.result.status == "ok"
    assert again.command.parameters == entry.command.parameters  # stesso URL e stessi parametri
    assert again.result.values["query"]["params"] == entry.result.values["query"]["params"]
    assert again.result.network_fingerprint[0]["sha256"] == entry.result.network_fingerprint[0]["sha256"]
    assert listed.hits("/scs") == hits  # prima la cache del 14 (D42-2 (6)), dichiarata
    assert "FROM_CACHE" in [w.code for w in again.result.warnings]
    a, b = entry.result.layers_created[0], again.result.layers_created[0]
    win.submit("catalog.crossmatch", {"layer_a": a, "layer_b": b})
    wait_idle(qtbot, win)
    xmatch = last(win, "catalog.crossmatch")
    assert xmatch.result.status == "ok" and xmatch.result.values["crossmatch"]["pairs"] == 5


def test_t23_italian_texts(qtbot, settings_path, cache, listed):  # noqa: F811
    QSettings(settings_path, QSettings.Format.IniFormat).setValue("language", "it")
    win = make_window(qtbot, settings_path, cache)
    try:
        assert win.act_cone_search.text() == "Cone search…" and win.act_adql.text() == "Query ADQL…"
        dialog = win.adql_dialog()
        assert dialog.windowTitle() == "Query ADQL"
        assert dialog.insert_view.text() == "Inserisci centro e raggio della vista"
        dialog.reject()
        cone_dialog = win.cone_search_dialog()
        assert cone_dialog.center_view.text() == "Centro della vista"
        cone_dialog.reject()
    finally:
        win.confirm = lambda title, text: True
        win.close()



# =============================================================================
# Riesegui con dati aggiornati (sprint B4, T24 del 40)


def select_rows(win, numbers):
    from PySide6.QtCore import QItemSelectionModel

    panel = win.history
    panel.table.clearSelection()
    model = panel.table.selectionModel()
    for row, entry in enumerate(panel.shown):
        if entry.number in numbers:
            model.select(panel.table.model().index(row, 0),
                         QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)


def test_t24_rerun_with_fresh_data(qtbot, window, listed):
    win = window
    panel = win.history
    assert not panel.rerun_fresh_button.isEnabled()  # nessuna selezione
    entry = cone(qtbot, win)
    zoom = last(win, "view.set_zoom")
    select_rows(win, {zoom.number})
    assert not panel.rerun_fresh_button.isEnabled()
    assert panel.rerun_fresh_button.toolTip() == "Only for commands that use the network"
    select_rows(win, {zoom.number, entry.number})  # selezione mista: spento
    assert not panel.rerun_fresh_button.isEnabled()
    select_rows(win, {entry.number})
    assert panel.rerun_fresh_button.isEnabled() and panel.rerun_fresh_button.toolTip() == ""
    # Riesegui: dalla cache; Riesegui con dati aggiornati: nuova richiesta al servizio, dichiarata.
    hits = listed.hits("/scs")
    panel.rerun_button.click()
    wait_idle(qtbot, win)
    assert listed.hits("/scs") == hits and "FROM_CACHE" in [w.code for w in last(win, "catalog.cone_search").result.warnings]
    select_rows(win, {entry.number})
    panel.rerun_fresh_button.click()
    wait_idle(qtbot, win)
    fresh = last(win, "catalog.cone_search")
    assert listed.hits("/scs") == hits + 1 and fresh.command.refresh
    assert fresh.command.requested_by.source == "history" and fresh.command.parameters == entry.command.parameters
    codes = {w.code: w for w in fresh.result.warnings}
    assert "FROM_CACHE" not in codes and codes["DATA_REFRESHED"].params == {"reason": "fresh"}
    select_rows(win, {fresh.number})
    assert json.loads(panel.detail.toPlainText())["command"]["refresh"] is True
    # Servizio spento: la copia in cache, dichiarata (cache_used).
    listed.close()
    panel.rerun_fresh_button.click()
    wait_idle(qtbot, win)
    down = last(win, "catalog.cone_search")
    assert next(w for w in down.result.warnings if w.code == "DATA_REFRESHED").params == {"reason": "cache_used"}


def test_t24_italian_fresh_button(qtbot, settings_path, cache, listed):  # noqa: F811
    QSettings(settings_path, QSettings.Format.IniFormat).setValue("language", "it")
    win = make_window(qtbot, settings_path, cache)
    try:
        assert win.history.rerun_fresh_button.text() == "Riesegui con dati aggiornati"
        assert win.history.tr("Only for commands that use the network") == "Solo per i comandi che usano la rete"
    finally:
        win.confirm = lambda title, text: True
        win.close()
