# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""SAMP nell'interfaccia (40 §3.12 T21, 41 §3.20 T38, 42 §3.6 T8; sprint B1).

Hub e client simulati di ``pyvo.samp`` nella cartella home temporanea dei test (``tests/conftest.py``): porta casuale,
file di blocco in ``$HOME/.samp`` temporaneo, mai quello vero (controllato da ``real_samp_untouched``).
"""

from __future__ import annotations

import os
import pwd
import socket
import threading
import time
import urllib.parse
from pathlib import Path

import astropy.units as u
import numpy as np
import pytest
import pyvo.samp as pyvo_samp
from astropy.coordinates import SkyCoord
from astropy.io.votable import parse as parse_votable
from PySide6.QtCore import QElapsedTimer, QSettings, QTimer

from astrotwo.core.commands import RequestedBy
from astrotwo.core.vo_protocols import SAMP_HUB_EVENTS, SAMP_MTYPES
from astrotwo.ui.samp_link import SampLink
from tests.core.test_commands_catalog_sky import ROWS, write_catalog
from tests.core.samp_fakes import JsampLikeHub, TopcatLike, bind_recorder, dead_client
from tests.ui.test_main_window import make_window, wait_idle

PEER = "TOPCAT simulato"


@pytest.fixture(autouse=True)
def real_samp_untouched(monkeypatch):
    """Il file di blocco SAMP vero (~/.samp dell'utente) non cambia mai durante questi test."""
    monkeypatch.delenv("SAMP_HUB", raising=False)
    real = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".samp"
    assert Path.home() != real.parent  # cartella home temporanea del conftest
    before = real.stat().st_mtime_ns if real.exists() else None
    yield
    assert (real.stat().st_mtime_ns if real.exists() else None) == before


@pytest.fixture
def settings_path(tmp_path):
    return str(tmp_path / "settings.ini")


@pytest.fixture
def hub():
    """Hub "di un altro programma" (come quello di TOPCAT): già attivo prima di AstroTwo."""
    server = pyvo_samp.SAMPHubServer(web_profile=False)
    server.start(wait=False)
    yield server
    if server.is_running:
        server.stop()


def make_peer(name=PEER):
    client = pyvo_samp.SAMPIntegratedClient(name=name)
    client.connect()
    received = []
    bind_recorder(client, received)  # risponde alle chiamate come un programma vero (sprint B1b)
    client.received = received
    return client


@pytest.fixture
def peer(hub):
    client = make_peer()
    yield client
    if client.is_connected:
        client.disconnect()


def samp_window(qtbot, settings_path, cache, tmp_path, timeout=5.0):
    link = SampLink(tmp_path / "received", timeout=timeout)
    return make_window(qtbot, settings_path, cache, samp_link=link)


@pytest.fixture
def window(qtbot, settings_path, cache, tmp_path):
    win = samp_window(qtbot, settings_path, cache, tmp_path)
    yield win
    win.confirm = lambda title, text: True
    win.close()


def last(win, name):
    return [e for e in win.session.history.entries if e.command.name == name][-1]


def submenu(menu, title):
    for action in menu.actions():
        if action.menu() is not None and action.text() == title:
            return action.menu()
    raise AssertionError(f"{title!r} non in {[a.text() for a in menu.actions()]}")


def recipient(menu, text):
    for action in menu.actions():
        if action.text() == text:
            return action
    raise AssertionError(f"{text!r} non in {[a.text() for a in menu.actions()]}")


def send(qtbot, win, title, who="All applications"):
    win._fill_samp_menu()
    recipient(submenu(win.samp_menu, title), who).trigger()
    wait_idle(qtbot, win)


def connect(qtbot, win):
    win.act_samp_connect.trigger()
    wait_idle(qtbot, win)
    entry = last(win, "samp.connect")
    assert entry.result.status == "ok", entry.result.error
    return entry.result.values


def me_for(peer):
    return [c for c in peer.get_registered_clients() if c not in ("cli#hub", peer.get_public_id())][0]


def open_catalog(qtbot, win, tmp_path, name="c.xml"):
    win.submit("catalog.open_file", {"file": {"path": write_catalog(tmp_path / name)}})
    wait_idle(qtbot, win)
    return last(win, "catalog.open_file").result.values["layer"]


def by_type(peer, mtype):
    return [m[4] for m in peer.received if m[3] == mtype]


# =============================================================================
# T21 — hub già attivo: collegamento, invio, ricezione, elenco, scollegamento


def test_t21_external_hub_send_and_receive(qtbot, window, peer, tmp_path):
    win = window
    assert win.status.samp_label.text() == "SAMP: off" and not win.act_samp_disconnect.isEnabled()
    values = connect(qtbot, win)
    assert values == {"hub": "external", "web_profile": False,
                      "clients": [{"id": peer.get_public_id(), "name": PEER}]}  # nessun hub proprio
    assert win.status.samp_label.text() == "SAMP: 1 apps" and PEER in win.status.samp_label.toolTip()
    win._fill_samp_menu()
    apps = submenu(win.samp_menu, "Connected applications")
    assert [a.text() for a in apps.actions()] == [PEER]
    layer = open_catalog(qtbot, win, tmp_path)
    data = win.session.workspace.state.layer(layer).data

    # righe selezionate di una tabella mai mandata: prima la tabella, poi la selezione (D40-9)
    win.submit("catalog.select", {"layer": layer, "rows": [0, 2]})
    wait_idle(qtbot, win)
    send(qtbot, win, "Send only the selected rows (2)", PEER)
    entry = last(win, "samp.send_selection")
    assert entry.result.status == "ok" and entry.result.values["table_sent"] is True
    assert entry.result.values["recipients"] == [peer.get_public_id()]
    qtbot.waitUntil(lambda: bool(by_type(peer, "table.select.rowList")), timeout=5000)
    loaded = by_type(peer, "table.load.votable")[0]
    selection = by_type(peer, "table.select.rowList")[0]
    assert selection == {"table-id": loaded["table-id"], "url": loaded["url"], "row-list": ["0", "2"]}

    # catalogo: colonne, unità, UCD ed epoca del COOSYS come nella tabella del 13
    send(qtbot, win, "Send whole table")
    assert last(win, "samp.send_table").result.status == "ok"
    qtbot.waitUntil(lambda: len(by_type(peer, "table.load.votable")) == 2, timeout=5000)
    params = by_type(peer, "table.load.votable")[1]
    assert params["table-id"] != loaded["table-id"] and params["table-id"].startswith(f"astrotwo-{win.samp.launch}-{layer}-")
    votable = parse_votable(urllib.parse.unquote(urllib.parse.urlsplit(params["url"]).path))
    got = votable.get_first_table()
    for name in data.table.colnames:
        field = got.get_field_by_id_or_name(name)
        column = data.table[name]
        assert field.unit == column.unit and field.ucd == column.meta.get("ucd")
        if column.dtype.kind == "f":
            assert np.array_equal(np.asarray(got.array[name]), np.asarray(column))
    assert [str(c.epoch) for c in votable.resources[0].coordinate_systems] == ["J2016.0"]

    # centro della vista e sorgente selezionata, in gradi ICRS (conversione ricalcolata con astropy)
    center = {"lon": {"value": 120.0, "unit": "deg"}, "lat": {"value": 30.0, "unit": "deg"}, "frame": "galactic",
              "equinox": None, "obstime": None, "epoch": None, "epoch_reason": "test"}
    win.submit("view.set_center", {"position": center, "window": win.view_window()})
    wait_idle(qtbot, win)
    send(qtbot, win, "Point at view center")
    qtbot.waitUntil(lambda: bool(by_type(peer, "coord.pointAt.sky")), timeout=5000)
    icrs = SkyCoord(120 * u.deg, 30 * u.deg, frame="galactic").icrs
    point = by_type(peer, "coord.pointAt.sky")[0]
    assert float(point["ra"]) == pytest.approx(icrs.ra.deg, abs=1e-9)
    assert float(point["dec"]) == pytest.approx(icrs.dec.deg, abs=1e-9)
    assert last(win, "samp.point_at").result.values["ra"] == {"value": float(point["ra"]), "unit": "deg"}
    win.submit("catalog.select", {"layer": layer, "rows": [1]})
    wait_idle(qtbot, win)
    send(qtbot, win, "Point at selected source")
    qtbot.waitUntil(lambda: len(by_type(peer, "coord.pointAt.sky")) == 2, timeout=5000)
    point = by_type(peer, "coord.pointAt.sky")[1]
    assert (float(point["ra"]), float(point["dec"])) == pytest.approx((ROWS[1][1], ROWS[1][2]), abs=1e-9)
    position = last(win, "samp.point_at").result.values["position"]
    assert position["epoch"] is not None and position["frame"] == "icrs"  # epoca del catalogo, mai assunta

    # ricezione: selezione per la tabella mandata, puntamento, nuova tabella e selezione su quella
    me = me_for(peer)
    peer.notify(me, {"samp.mtype": "table.select.rowList",
                     "samp.params": {"table-id": loaded["table-id"], "url": loaded["url"], "row-list": ["2"]}})
    qtbot.waitUntil(lambda: win.session.workspace.state.layer(layer).selection == (2,), timeout=5000)
    entry = last(win, "catalog.select")
    origin = RequestedBy("samp", client=PEER, client_id=peer.get_public_id())
    assert entry.command.requested_by == origin and entry.result.status == "ok"
    assert win.catalog_panel.tab(layer).selected_rows() == [2]
    peer.notify(me, {"samp.mtype": "coord.pointAt.sky", "samp.params": {"ra": "56.75", "dec": "24.125"}})
    qtbot.waitUntil(lambda: last(win, "view.set_center").command.requested_by == origin, timeout=5000)
    wait_idle(qtbot, win)
    view = win.session.workspace.state.view
    assert view.center.frame_name == "icrs" and view.center.epoch is None
    assert (view.center.lon.to_value(u.deg)[()], view.center.lat.to_value(u.deg)[()]) == (56.75, 24.125)
    source = tmp_path / "da_topcat.xml"
    write_catalog(source)
    peer.notify(me, {"samp.mtype": "table.load.votable",
                     "samp.params": {"url": source.as_uri(), "table-id": "topcat-7", "name": "stelle"}})
    qtbot.waitUntil(lambda: last(win, "catalog.open_file").command.requested_by == origin, timeout=5000)
    wait_idle(qtbot, win)
    opened = last(win, "catalog.open_file")
    assert opened.result.status == "ok"
    copy = Path(opened.command.parameters["file"]["path"])
    assert copy.parent == tmp_path / "received" and copy.read_bytes() == source.read_bytes()
    received_layer = opened.result.values["layer"]
    assert win.session.workspace.state.layer(received_layer).data.positions.epoch is not None  # epoca dal COOSYS
    peer.notify(me, {"samp.mtype": "table.select.rowList",
                     "samp.params": {"table-id": "topcat-7", "url": source.as_uri(), "row-list": ["0", "1"]}})
    qtbot.waitUntil(lambda: win.session.workspace.state.layer(received_layer).selection == (0, 1), timeout=5000)
    # nel pannello Comandi: chi = SAMP e il nome del programma; filtro SAMP
    win.history.who_filter.setCurrentIndex(win.history.who_filter.findData("samp"))
    win.history.class_filter.setCurrentIndex(win.history.class_filter.findData("all"))
    who = {win.history.table.item(r, 2).text() for r in range(win.history.table.rowCount())}
    assert who == {f"SAMP · {PEER}"}

    # selezione per una tabella sconosciuta: nessun comando, messaggio e risposta d'errore
    count = len(win.session.history.entries)
    peer.notify(me, {"samp.mtype": "table.select.rowList",
                     "samp.params": {"table-id": "ignota", "url": "file:///ignota.xml", "row-list": ["0"]}})
    qtbot.waitUntil(lambda: bool(any(m[1] == "SAMP_TABLE_UNKNOWN" for m in win.messages.messages)), timeout=5000)
    assert len(win.session.history.entries) == count

    # tipo non supportato: AstroTwo non vi è iscritto, l'hub lo rifiuta e nulla accade
    subscribed = set(peer.get_subscriptions(me))
    assert subscribed == set(SAMP_MTYPES) | set(SAMP_HUB_EVENTS) | {"samp.app.ping"}  # mai client.env.get
    with pytest.raises(Exception):
        peer.notify(me, {"samp.mtype": "image.load.fits", "samp.params": {"url": source.as_uri()}})
    qtbot.wait(200)
    assert len(win.session.history.entries) == count

    # il programma esce: elenco e stato aggiornati dagli eventi dell'hub
    peer.disconnect()
    qtbot.waitUntil(lambda: bool(win.status.samp_label.text() == "SAMP: 0 apps"), timeout=5000)
    win.act_samp_disconnect.trigger()
    wait_idle(qtbot, win)
    assert last(win, "samp.disconnect").result.values == {"was_connected": True, "own_hub_stopped": False}
    assert win.status.samp_label.text() == "SAMP: off"
    assert (Path.home() / ".samp").exists()  # l'hub dell'altro programma resta acceso


# =============================================================================
# T21 — nessun hub: hub proprio con profilo web spento, spento pulito alla chiusura


def test_t21_own_hub_and_clean_close(qtbot, settings_path, cache, tmp_path):
    win = samp_window(qtbot, settings_path, cache, tmp_path)
    lockfile = Path.home() / ".samp"
    assert not lockfile.exists()
    values = connect(qtbot, win)
    assert values == {"hub": "own", "web_profile": False, "clients": []}
    assert win.samp._hub._hub._web_profile is False
    assert lockfile.exists() and win.status.samp_label.text() == "SAMP: 0 apps (own hub)"
    client = make_peer()  # un programma che arriva dopo usa l'hub di AstroTwo
    try:
        qtbot.waitUntil(lambda: bool(win.status.samp_label.text() == "SAMP: 1 apps (own hub)"), timeout=5000)
        assert win.status.samp_label.toolTip().startswith("Hub started by AstroTwo.")
        layer = open_catalog(qtbot, win, tmp_path)
        win.submit("samp.send_table", {"layer": layer, "recipient": client.get_public_id()})
        wait_idle(qtbot, win)
        qtbot.waitUntil(lambda: bool(client.received), timeout=5000)
        win.confirm = lambda title, text: True
        win.close()
        assert not lockfile.exists()  # hub proprio spento in modo pulito
        assert not win.samp.connected
    finally:
        if client.is_connected:
            try:
                client.disconnect()
            except Exception:  # noqa: BLE001 - l'hub non c'è più
                pass


# =============================================================================
# T21 — l'hub di un altro programma si spegne


def test_t21_external_hub_shutdown(qtbot, window, hub):
    connect(qtbot, window)
    hub.stop()
    qtbot.waitUntil(lambda: window.status.samp_label.text() == "SAMP: off", timeout=5000)
    assert any(m[1] == "SAMP_UNAVAILABLE" and m[3] is False for m in window.messages.messages)
    assert window.act_samp_connect.isEnabled()


# =============================================================================
# T21 — hub che non risponde: SAMP_UNAVAILABLE (timeout), thread principale sempre libero


def test_t21_mute_hub_never_blocks(qtbot, settings_path, cache, tmp_path):
    mute = socket.socket()
    mute.bind(("127.0.0.1", 0))
    mute.listen(16)  # accetta la connessione ma non risponde mai
    port = mute.getsockname()[1]
    (Path.home() / ".samp").write_text(f"samp.secret=muto\nsamp.hub.xmlrpc.url=http://127.0.0.1:{port}/xmlrpc\n"
                                       "samp.profile.version=1.3\n", encoding="utf-8")
    win = samp_window(qtbot, settings_path, cache, tmp_path, timeout=1.0)
    try:
        gaps, clock = [], QElapsedTimer()
        clock.start()
        probe = QTimer()
        probe.setInterval(10)
        probe.timeout.connect(lambda: gaps.append(clock.restart()))
        probe.start()
        started = time.monotonic()
        win.act_samp_connect.trigger()
        wait_idle(qtbot, win, timeout=10000)
        probe.stop()
        entry = last(win, "samp.connect")
        assert entry.result.status == "error"
        assert (entry.result.error.code, entry.result.error.params["reason"]) == ("SAMP_UNAVAILABLE", "timeout")
        assert entry.result.error.params["operation"] == "connect" and entry.result.error.params["seconds"] == 1.0
        assert 0.9 < time.monotonic() - started < 5.0
        assert max(gaps[1:]) < 100, max(gaps)  # sonda di latenza (40 §9)
        assert win.status.samp_label.text() == "SAMP: off"
        assert any(m[1] == "SAMP_UNAVAILABLE" for m in win.messages.messages)
    finally:
        mute.close()  # la chiamata abbandonata finisce; si aspetta il suo thread prima di lasciare la home temporanea
        qtbot.waitUntil(lambda: not any(t.name == "astrotwo-samp-connect" and t.is_alive()
                                        for t in threading.enumerate()), timeout=30000)
        win.confirm = lambda title, text: True
        win.close()


# =============================================================================
# T38 del 41 e T8 del 42 — menu contestuali; indici nell'ordine della tabella


def test_context_menus(qtbot, window, peer, tmp_path):
    win = window
    menu = win._sky_context_menu(None)
    assert menu.actions()[0].text() == "Connect to SAMP hub"
    assert not submenu(menu, "Point SAMP applications at view center").isEnabled()
    layer = open_catalog(qtbot, win, tmp_path)
    menu = win._table_context_menu(layer, None)
    assert not submenu(menu, "Send whole table via SAMP").isEnabled()
    menu.actions()[0].trigger()  # Connect to SAMP hub
    wait_idle(qtbot, win)
    assert win.samp.connected and last(win, "samp.connect").command.requested_by.source == "mouse"
    win.submit("view.set_center", {"position": {"lon": {"value": 56.8, "unit": "deg"},
                                                "lat": {"value": 24.1, "unit": "deg"}, "frame": "icrs",
                                                "equinox": None, "obstime": None, "epoch": None,
                                                "epoch_reason": "test"}, "window": win.view_window()})
    wait_idle(qtbot, win)
    menu = win._sky_context_menu(None)
    assert menu.actions()[0].text() != "Connect to SAMP hub"
    assert not submenu(menu, "Point SAMP applications at selected source").isEnabled()  # nessuna sorgente
    recipient(submenu(menu, "Point SAMP applications at view center"), PEER).trigger()
    wait_idle(qtbot, win)
    assert last(win, "samp.point_at").result.values["recipients"] == [peer.get_public_id()]
    qtbot.waitUntil(lambda: bool(by_type(peer, "coord.pointAt.sky")), timeout=5000)
    assert float(by_type(peer, "coord.pointAt.sky")[0]["ra"]) == pytest.approx(56.8, abs=1e-9)
    # tabella ordinata al contrario: gli indici mandati restano quelli della tabella, non quelli mostrati
    win.submit("table.sort", {"layer": layer, "column": "RA_ICRS", "direction": "descending"})
    wait_idle(qtbot, win)
    win.submit("catalog.select", {"layer": layer, "rows": [0, 2]})
    wait_idle(qtbot, win)
    menu = win._table_context_menu(layer, None)
    assert not submenu(menu, "Point SAMP applications at this source").isEnabled()  # due righe
    recipient(submenu(menu, "Send only the selected rows (2) via SAMP"), "All applications").trigger()
    wait_idle(qtbot, win)
    qtbot.waitUntil(lambda: bool(by_type(peer, "table.select.rowList")), timeout=5000)
    assert by_type(peer, "table.select.rowList")[0]["row-list"] == ["0", "2"]
    win.submit("catalog.select", {"layer": layer, "rows": [1]})
    wait_idle(qtbot, win)
    menu = win._table_context_menu(layer, None)
    recipient(submenu(menu, "Point SAMP applications at this source"), "All applications").trigger()
    wait_idle(qtbot, win)
    qtbot.waitUntil(lambda: len(by_type(peer, "coord.pointAt.sky")) == 2, timeout=5000)
    point = by_type(peer, "coord.pointAt.sky")[1]
    assert (float(point["ra"]), float(point["dec"])) == pytest.approx((ROWS[1][1], ROWS[1][2]), abs=1e-9)


# =============================================================================
# Preferenza "Connetti SAMP all'avvio" (40 §3.10): spenta di default


def test_connect_at_startup_preference(qtbot, settings_path, cache, tmp_path, hub, monkeypatch):
    from astrotwo.core import catalogs, hips

    monkeypatch.setattr(hips, "set_survey", lambda *a, **k: (_ for _ in ()).throw(
        hips.HiPSError("NET_TIMEOUT", "simulato", params={"reason": "url", "url": "http://x.invalid/",
                                                          "detail": "simulato", "connect": {"value": 5.0, "unit": "s"},
                                                          "read": {"value": 5.0, "unit": "s"}})))
    monkeypatch.setattr(catalogs, "load_catalog", lambda *a, **k: None)
    win = samp_window(qtbot, settings_path, cache, tmp_path)
    dialog = win.preferences_dialog()
    assert not dialog.samp_startup.isChecked() and win.preference("samp/connect_at_startup") == "false"
    dialog.samp_startup.setChecked(True)
    dialog._apply()
    wait_idle(qtbot, win)
    assert last(win, "prefs.set").command.parameters == {"key": "samp/connect_at_startup", "value": "true"}
    win.confirm = lambda title, text: True
    win.close()
    settings = QSettings(settings_path, QSettings.Format.IniFormat)
    again = mw_window(settings, cache, tmp_path)
    qtbot.addWidget(again)
    try:
        wait_idle(qtbot, again)
        assert last(again, "samp.connect").result.status == "ok" and again.samp.connected
    finally:
        again.confirm = lambda title, text: True
        again.close()


def mw_window(settings, cache, tmp_path):
    from astrotwo.core.commands import default_registry
    from astrotwo.ui.main_window import MainWindow, ThreadCache

    win = MainWindow(registry=default_registry(cache=ThreadCache(root=cache.root)), settings=settings,
                     startup_commands=True, samp_link=SampLink(tmp_path / "received2", timeout=5.0))
    win.auto_column_dialogs = False
    return win


# =============================================================================
# T21b — un destinatario come TOPCAT 4.10-8 (sprint B1b, 2026-11-05; tests/core/samp_fakes.py)


@pytest.fixture
def jsamp_hub():
    """Hub "di TOPCAT": identificativo ``hub`` come JSAMP (l'hub di pyvo si chiama ``cli#hub``)."""
    server = JsampLikeHub(web_profile=False)
    server.start(wait=False)
    yield server
    if server.is_running:
        server.stop()


@pytest.fixture
def topcat(jsamp_hub):
    peer = TopcatLike()
    yield peer
    peer.disconnect()


def click_rows(qtbot, win, layer, rows):
    """Righe selezionate con il mouse nella vista tabella (42): ``catalog.select`` dopo la pausa di fine gesto."""
    from PySide6.QtCore import QItemSelectionModel

    page = win.catalog_panel.pages[layer]
    model = page.view.selectionModel()
    model.clearSelection()
    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    for row in rows:
        model.select(page.model.index(page.model.shown_row(row), 0), flags)
    qtbot.waitUntil(lambda: set(win.session.workspace.state.layer(layer).selection) == set(rows), timeout=5000)
    wait_idle(qtbot, win)


def test_t21b_hub_is_not_counted(qtbot, window, topcat):
    """Problema A: con l'hub di TOPCAT la barra diceva «SAMP: 2 apps» con il solo TOPCAT collegato."""
    win = window
    values = connect(qtbot, win)
    assert values["clients"] == [{"id": topcat.id, "name": "topcat"}]
    assert win.status.samp_label.text() == "SAMP: 1 apps"
    tip = win.status.samp_label.toolTip()
    assert "Hub of another application." in tip and "Hub: PyVO SAMP Hub." in tip and "Connected: topcat" in tip
    win._fill_samp_menu()
    assert [a.text() for a in submenu(win.samp_menu, "Connected applications").actions()] == ["topcat"]
    who = [a.text() for a in submenu(win.samp_menu, "Send whole table").actions() if a.text()]
    assert who == ["All applications", "topcat"]  # l'hub non è un destinatario


def test_t21b_selection_after_catalog_two_launches(qtbot, settings_path, cache, tmp_path, topcat):
    """Problemi B e C: dopo "Send catalog" le righe selezionate non rimandano la tabella e arrivano sulla tabella giusta
    con le righe giuste, anche al secondo avvio di AstroTwo (prima: stesso ``table-id``, tabella scartata da TOPCAT
    in silenzio e selezione sulla tabella del lancio precedente)."""
    ids = []
    for launch, rows in enumerate(([0, 2], [1])):
        win = samp_window(qtbot, settings_path, cache, tmp_path / f"avvio{launch}")
        try:
            connect(qtbot, win)
            layer = open_catalog(qtbot, win, tmp_path, name=f"c{launch}.xml")
            send(qtbot, win, "Send whole table", "topcat")
            entry = last(win, "samp.send_table")
            assert entry.result.status == "ok" and entry.result.values.get("rejected", []) == []
            ids.append(entry.result.values["table_id"])
            qtbot.waitUntil(lambda n=launch + 1: len(topcat.tables) == n, timeout=3000)  # caricata in TOPCAT
            win.submit("table.sort", {"layer": layer, "column": "RA_ICRS", "direction": "descending"})
            wait_idle(qtbot, win)
            assert last(win, "table.sort").result.status == "ok"  # righe mostrate in un altro ordine
            click_rows(qtbot, win, layer, rows)
            recipient(submenu(win._table_context_menu(layer, None),
                                    f"Send only the selected rows ({len(rows)}) via SAMP"),
                      "All applications").trigger()
            wait_idle(qtbot, win)
            entry = last(win, "samp.send_selection")
            assert entry.result.status == "ok", entry.result.error
            assert entry.result.values["table_sent"] is False and entry.result.values["table_id"] == ids[-1]
            assert entry.result.values["rows"] == sorted(rows)  # ordine della tabella, non quello mostrato
            assert entry.result.values["recipients"] == [topcat.id]
            assert len(topcat.tables) == launch + 1  # una sola tabella per avvio
            assert topcat.tables[launch]["table_id"] == ids[-1]
            assert topcat.tables[launch]["subsets"] == {"AstroTwo": sorted(rows)}
        finally:
            win.confirm = lambda title, text: True
            win.close()
    assert ids[0] != ids[1] and topcat.errors == []
    assert topcat.tables[0]["subsets"] == {"AstroTwo": [0, 2]}  # la tabella del primo avvio non è toccata


def test_t21b_selection_of_a_table_never_sent(qtbot, window, topcat, tmp_path):
    """D40-9 (4): tabella mandata nello stesso comando; la selezione parte dopo la risposta di caricamento (prima:
    arrivava a TOPCAT prima della tabella ed era scartata in silenzio)."""
    win = window
    connect(qtbot, win)
    layer = open_catalog(qtbot, win, tmp_path)
    click_rows(qtbot, win, layer, [1, 2])
    send(qtbot, win, "Send only the selected rows (2)")
    entry = last(win, "samp.send_selection")
    assert entry.result.status == "ok" and entry.result.values["table_sent"] is True
    assert entry.result.values["recipients"] == [topcat.id] and entry.result.values.get("rejected", []) == []
    assert len(topcat.tables) == 1 and topcat.tables[0]["subsets"] == {"AstroTwo": [1, 2]}
    assert topcat.errors == []
    send(qtbot, win, "Send only the selected rows (2)")  # già passata da SAMP: mai rimandata
    assert last(win, "samp.send_selection").result.values["table_sent"] is False and len(topcat.tables) == 1


def test_t21b_rejections_are_reported(qtbot, window, topcat, tmp_path):
    """Chi rifiuta o non risponde va in ``rejected`` e nel pannello Messaggi; gli altri sono raggiunti."""
    win = window
    win.samp.timeout = win.samp.table_timeout = 1.0
    dead = dead_client()
    try:
        connect(qtbot, win)
        layer = open_catalog(qtbot, win, tmp_path)
        send(qtbot, win, "Send whole table")
        entry = last(win, "samp.send_table")
        assert entry.result.status == "ok" and entry.result.values["recipients"] == [topcat.id]
        assert [r["id"] for r in entry.result.values["rejected"]] == [dead.get_public_id()]
        assert [w.code for w in entry.result.warnings] == ["SAMP_NO_PEER"]
        assert entry.result.warnings[0].params["recipient"] == "morto"
        assert entry.result.warnings[0].params["reason"] in ("rejected", "no_reply_table")  # tabella: può arrivare
        assert any(m[1] == "SAMP_NO_PEER" for m in win.messages.messages)
        assert len(topcat.tables) == 1
        # selezione di una tabella che TOPCAT non ha più (TOPCAT riavviato): errore con il testo di TOPCAT
        topcat.tables.clear()
        topcat.by_id.clear()
        click_rows(qtbot, win, layer, [0])
        send(qtbot, win, "Send only the selected rows (1)", "topcat")
        entry = last(win, "samp.send_selection")
        assert entry.result.status == "error" and entry.result.error.code == "SAMP_NO_PEER"
        assert entry.result.error.params["reason"] == "rejected" and "No table with" in entry.result.error.params["detail"]
    finally:
        dead.client.hub.disconnect()


# =============================================================================
# Sprint B2 — rifiniture SAMP (D40-9 (7)) e catalogo incrociato mandato via SAMP


def test_b2_reply_timeout_by_type_and_no_reply_text(qtbot, window):
    """60 s per ``table.load.votable``, 10 s per gli altri tipi; per le tabelle l'avviso dice che può arrivare."""
    from astrotwo.messages_catalog import message_text
    from astrotwo.ui.samp_link import DEFAULT_TABLE_TIMEOUT, DEFAULT_TIMEOUT

    link = SampLink(Path("unused"))
    assert (DEFAULT_TIMEOUT, DEFAULT_TABLE_TIMEOUT) == (10.0, 60.0)
    assert link.reply_timeout("table.load.votable") == 60.0
    assert link.reply_timeout("table.select.rowList") == link.reply_timeout("coord.pointAt.sky") == 10.0
    win = window
    warnings = win._samp_rejected({"rejected": [
        {"id": "c1", "name": "topcat", "reason": "no_reply", "detail": "", "mtype": "table.load.votable"},
        {"id": "c1", "name": "topcat", "reason": "no_reply", "detail": "", "mtype": "table.select.rowList"}]})
    assert [(w.params["reason"], w.params["seconds"]) for w in warnings] == [("no_reply_table", 60.0),
                                                                             ("no_reply", 5.0)]
    assert "may still arrive" in message_text("SAMP_NO_PEER", warnings[0].params, "en")
    assert "potrebbe arrivare comunque" in message_text("SAMP_NO_PEER", warnings[0].params, "it")
    assert "arrive" not in message_text("SAMP_NO_PEER", warnings[1].params, "en")


def test_b2_send_table_waits_for_the_table_timeout(qtbot, window, peer, tmp_path, monkeypatch):
    """L'invio della tabella passa al 14 il tempo delle tabelle; selezione e puntamento quello degli altri tipi."""
    from astrotwo.core.vo_protocols import SampHub

    win = window
    connect(qtbot, win)
    seen = []
    original = SampHub.send_message

    def spy(self, mtype, params, recipient=None, *, among=None, timeout=10.0):
        seen.append((mtype, timeout))
        return original(self, mtype, params, recipient, among=among, timeout=timeout)

    monkeypatch.setattr(SampHub, "send_message", spy)
    layer = open_catalog(qtbot, win, tmp_path)
    click_rows(qtbot, win, layer, [0])
    send(qtbot, win, "Send only the selected rows (1)")  # tabella mai mandata: prima la tabella
    assert seen == [("table.load.votable", 60.0), ("table.select.rowList", 5.0)]


def test_b2_menu_texts_with_selected_rows(qtbot, window, peer, tmp_path):
    win = window
    connect(qtbot, win)
    layer = open_catalog(qtbot, win, tmp_path)
    win._fill_samp_menu()
    titles = [a.text() for a in win.samp_menu.actions()]
    assert "Send whole table" in titles and "Send only the selected rows (0)" in titles
    assert not submenu(win.samp_menu, "Send only the selected rows (0)").isEnabled()  # nessuna riga: spenta
    assert submenu(win.samp_menu, "Send whole table").isEnabled()
    menu = win._table_context_menu(layer, None)
    assert not submenu(menu, "Send only the selected rows (0) via SAMP").isEnabled()
    click_rows(qtbot, win, layer, [0, 1, 2])
    win._fill_samp_menu()
    assert submenu(win.samp_menu, "Send only the selected rows (3)").isEnabled()
    assert submenu(win._table_context_menu(layer, None), "Send only the selected rows (3) via SAMP").isEnabled()


def test_b2_crossmatch_catalog_via_samp(qtbot, window, peer, tmp_path):
    """Il catalogo nato da ``catalog.crossmatch`` si manda come gli altri, con la colonna della separazione."""
    win = window
    connect(qtbot, win)
    open_catalog(qtbot, win, tmp_path, name="a.xml")
    open_catalog(qtbot, win, tmp_path, name="b.xml")
    win.submit("catalog.crossmatch", {"layer_a": "L1", "layer_b": "L2", "mode": "best",
                                      "max_sep": {"value": 1.0, "unit": "arcsec"}})
    wait_idle(qtbot, win)
    entry = last(win, "catalog.crossmatch")
    assert entry.result.status == "ok", entry.result.error
    new = entry.result.layers_created[0]
    win.catalog_panel.tabs.setCurrentIndex(win.catalog_panel.tabs.indexOf(win.catalog_panel.pages[new]))
    send(qtbot, win, "Send whole table")
    sent = last(win, "samp.send_table")
    assert sent.result.status == "ok" and sent.result.values["layer"] == new
    qtbot.waitUntil(lambda: bool(by_type(peer, "table.load.votable")), timeout=5000)
    params = by_type(peer, "table.load.votable")[-1]
    votable = parse_votable(urllib.parse.unquote(urllib.parse.urlsplit(params["url"]).path))
    got = votable.get_first_table()
    assert "xmatch_sep" in [f.name for f in got.fields]
    assert next(f for f in got.fields if f.name == "xmatch_sep").unit == u.arcsec
    assert len(got.array) == len(win.session.workspace.state.layer(new).data.table) == len(ROWS)
