# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Finestra «Profili», sprint C6 (``mdfiles/43-ui-profili.md`` §3.10, §12 T17–T21): «Esporta…», «Carica i punti SED
come catalogo», «Invia con SAMP».

Risposte vere registrate il 2026-11-07 (``tests/analysis/profile_fakes.py``), hub e client SAMP simulati di
``pyvo.samp`` nella cartella home temporanea dei test. Nessuna rete.
"""

from __future__ import annotations

import time
import urllib.parse

import pyvo.samp as pyvo_samp
import pytest
from astropy.io.votable import parse as parse_votable
from astropy.table import Table

import astrotwo.ui.profiles as profiles_module
from tests.analysis.profile_fakes import recorded, services  # noqa: F401
from tests.core.samp_fakes import bind_recorder
from tests.ui.test_main_window import settings_path, wait_idle  # noqa: F401 - fixture
from tests.ui.test_profiles import finished, win, warm_matplotlib  # noqa: F401 - fixture


def entries(win, name):
    return [e for e in win.session.history.entries if e.command.name == name]


def save_as(monkeypatch, path) -> list:
    asked = []

    def dialog(parent, title, proposed, filters):
        asked.append((title, proposed, filters))
        return str(path), ""

    monkeypatch.setattr(profiles_module.QFileDialog, "getSaveFileName", staticmethod(dialog))
    return asked


def save_pdf_as(monkeypatch, path, language=None) -> list:
    """Dialogo del PDF (DD-1): registra titolo, nome proposto e lingua proposta; ``language`` = scelta dell'utente
    (``None``: lascia quella proposta)."""
    asked = []

    def run(dialog):
        asked.append((dialog.windowTitle(), dialog.selectedFiles(), dialog.language()))
        if language is not None:
            dialog.language_box.setCurrentIndex(dialog.language_box.findData(language))
        dialog.selectFile(str(path))
        return 1

    monkeypatch.setattr(profiles_module.PdfExportDialog, "exec", run)
    return asked


# =============================================================================
# T21 — pulsanti attivi solo con un profilo


def test_t21_buttons_enabled_only_with_a_profile(qtbot, win, services):  # noqa: F811
    def slow(query):
        time.sleep(1.5)
        return recorded("simbad", query)

    services.overrides[("simbad", "WHERE i.id = '51 Peg'")] = slow
    tab = win.open_profile({"name": "51 Peg"})
    assert not tab.export_button.isEnabled() and not tab.catalog_button.isEnabled()
    assert not tab.samp_button.isEnabled()
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    assert tab.export_button.isEnabled() and tab.act_export_png.isEnabled() and tab.catalog_button.isEnabled()
    assert not tab.samp_button.isEnabled() and tab.samp_button.toolTip() == "SAMP not connected"
    assert tab.export_commands() == [tab.command_number]
    only_identity = win.open_profile({"name": "51 Peg", "sections": ["identity"]})
    qtbot.waitUntil(lambda: finished(win, only_identity), timeout=60000)
    assert only_identity.export_button.isEnabled() and not only_identity.act_export_png.isEnabled()
    assert not only_identity.catalog_button.isEnabled() and only_identity.catalog_button.toolTip() == "No SED points"


# =============================================================================
# T17 — Esporta… (ECSV, PDF, PNG) come comandi registrati


def test_t17_export_menu_queues_registered_commands(qtbot, win, services, tmp_path, monkeypatch):  # noqa: F811
    tab = win.open_profile({"name": "TRAPPIST-1"})
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    number = tab.command_number
    win.language = "it"  # app in italiano: la lingua proposta per il PDF resta l'inglese (DD-1)
    for fmt, action, name in (("ecsv", tab.act_export_ecsv, "t.ecsv"), ("pdf", tab.act_export_pdf, "t.pdf"),
                              ("sed_png", tab.act_export_png, "t.png")):
        asked = save_pdf_as(monkeypatch, tmp_path / name) if fmt == "pdf" else save_as(monkeypatch, tmp_path / name)
        action.trigger()
        wait_idle(qtbot, win, 60000)
        proposed = asked[0][1][0].rsplit("/", 1)[-1] if fmt == "pdf" else asked[0][1]
        assert proposed == {"ecsv": "TRAPPIST-1-profile.ecsv", "pdf": "TRAPPIST-1-profile.pdf",
                            "sed_png": "TRAPPIST-1-sed.png"}[fmt]
        if fmt == "pdf":
            assert asked[0][2] == "en"
        entry = entries(win, "object.export")[-1]
        assert entry.command.parameters == {"commands": [number], "format": fmt, "path": str(tmp_path / name),
                                            "language": "en"}
        assert entry.result.status == "ok", entry.result.error
        assert entry.command.requested_by.source == "menu" and (tmp_path / name).stat().st_size > 0
    assert len(Table.read(tmp_path / "t.ecsv", format="ascii.ecsv")) > 50
    # PDF di nuovo in inglese (lingua proposta), poi in italiano scelto nel dialogo (DD-1, 43 §3.10)
    save_pdf_as(monkeypatch, tmp_path / "t2.pdf")
    tab.act_export_pdf.trigger()
    wait_idle(qtbot, win, 60000)
    assert (tmp_path / "t2.pdf").read_bytes() == (tmp_path / "t.pdf").read_bytes()  # stesso file, byte per byte
    asked = save_pdf_as(monkeypatch, tmp_path / "t-it.pdf", language="it")
    tab.act_export_pdf.trigger()
    wait_idle(qtbot, win, 60000)
    italian = entries(win, "object.export")[-1]
    assert asked[0][2] == "en" and italian.command.parameters["language"] == "it"
    first = (tmp_path / "t-it.pdf").read_bytes()
    assert first != (tmp_path / "t.pdf").read_bytes()
    # Riesegui dalla cronologia: stesso comando, stessa lingua, stesso file
    win.rerun([italian])
    wait_idle(qtbot, win, 60000)
    assert entries(win, "object.export")[-1].command.parameters["language"] == "it"
    assert (tmp_path / "t-it.pdf").read_bytes() == first
    # esportazione non valida: finestra con il messaggio, nessun file
    win.modals.clear()
    tab.export("ecsv", str(tmp_path / "manca" / "x.ecsv"))
    wait_idle(qtbot, win)
    assert win.modals and win.modals[-1][0] == "The export was not written"
    assert "folder does not exist" in win.modals[-1][1]


# =============================================================================
# T18 — esportazione dopo «Riprova questa sezione»


def test_t18_export_after_retry_uses_both_commands(qtbot, win, services, tmp_path):  # noqa: F811
    services.overrides[("gaia", "FROM gaiadr3.gaia_source WHERE source_id")] = \
        lambda query: (503, "text/plain", "coda piena")
    tab = win.open_profile({"name": "51 Peg", "sections": ["identity", "astrometry"]})
    qtbot.waitUntil(lambda: finished(win, tab), timeout=90000)
    assert tab.views["astrometry"].state in ("error", "partial")  # Gaia giù: solo SIMBAD
    services.overrides.clear()
    tab.retry("astrometry")
    # La sezione arriva prima con l'avanzamento (numero ancora None), il numero del comando alla fine del comando:
    # si aspettano entrambi (corsa vista con la suite completa, sprint C7).
    qtbot.waitUntil(lambda: tab.views["astrometry"].state == "done"
                    and tab.views["astrometry"].command_number is not None, timeout=60000)
    retry = tab.views["astrometry"].command_number
    assert tab.export_commands() == [tab.command_number, retry]
    tab.export("ecsv", str(tmp_path / "p.ecsv"))
    wait_idle(qtbot, win)
    table = Table.read(tmp_path / "p.ecsv", format="ascii.ecsv")
    assert set(table[table["section"] == "astrometry"]["command_id"]) == {retry}
    assert set(table[table["section"] == "identity"]["command_id"]) == {tab.command_number}


# =============================================================================
# T19 — Carica i punti SED come catalogo


def test_t19_load_sed_points_as_catalog(qtbot, win, services, tmp_path):  # noqa: F811
    tab = win.open_profile({"name": "51 Peg", "sections": ["identity", "photometry"]})
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    win.profiles.sed_folder = tmp_path / "Profiles"
    tab.catalog_button.click()
    qtbot.waitUntil(lambda: bool(entries(win, "catalog.open_file")), timeout=30000)
    wait_idle(qtbot, win)
    export = entries(win, "object.export")[-1]
    path = tmp_path / "Profiles" / f"51_Peg-sed-{tab.command_number}.xml"
    assert export.command.parameters["format"] == "sed_votable" and export.command.parameters["path"] == str(path)
    opened = entries(win, "catalog.open_file")[-1]
    assert opened.result.status == "ok", opened.result.error
    assert opened.command.parameters["file"]["path"] == str(path) and opened.command.parameters["file"]["sha256"]
    layer = win.session.workspace.state.layer(opened.result.values["layer"])
    points = tab.views["photometry"].data["details"]["points"]
    assert layer.kind == "catalog" and len(layer.data.table) == len(points)
    assert layer.name == "SED * 51 Peg" and layer.data.positions.frame == "icrs"


# =============================================================================
# T20 — Invia con SAMP


@pytest.fixture
def hub():
    server = pyvo_samp.SAMPHubServer(web_profile=False)
    server.start(wait=False)
    yield server
    if server.is_running:
        server.stop()


@pytest.fixture
def peer(hub):
    client = pyvo_samp.SAMPIntegratedClient(name="TOPCAT simulato")
    client.connect()
    received: list = []
    bind_recorder(client, received)
    client.received = received
    yield client
    if client.is_connected:
        client.disconnect()


def test_t20_send_sed_via_samp(qtbot, win, services, peer, monkeypatch):  # noqa: F811
    from astrotwo.core.vo_protocols import SampHub

    tab = win.open_profile({"name": "TRAPPIST-1", "sections": ["identity", "photometry"]})
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    assert not tab.samp_button.isEnabled()  # senza collegamento: spento con il suggerimento
    win.act_samp_connect.trigger()
    wait_idle(qtbot, win)
    qtbot.waitUntil(lambda: tab.samp_button.isEnabled(), timeout=10000)
    seen = []
    original = SampHub.send_message

    def spy(self, mtype, params, recipient=None, *, among=None, timeout=10.0):
        seen.append((mtype, timeout))
        return original(self, mtype, params, recipient, among=among, timeout=timeout)

    monkeypatch.setattr(SampHub, "send_message", spy)
    tab._fill_samp_menu()
    actions = {a.text(): a for a in tab.samp_menu.actions() if a.text()}
    assert "All applications" in actions and "TOPCAT simulato" in actions
    actions["TOPCAT simulato"].trigger()
    wait_idle(qtbot, win, 70000)
    entry = entries(win, "object.send_sed")[-1]
    assert entry.result.status == "ok", entry.result.error
    assert entry.command.parameters == {"commands": [tab.command_number], "recipient": peer.get_public_id()}
    assert seen == [("table.load.votable", 60.0)]  # chiamata sincrona con il tempo delle tabelle (14, D40-9 (7))
    assert entry.result.values["recipients"] == [peer.get_public_id()]
    qtbot.waitUntil(lambda: bool(peer.received), timeout=10000)
    mtype, params = peer.received[-1][3], peer.received[-1][4]
    assert mtype == "table.load.votable" and params["name"] == "SED TRAPPIST-1"
    assert params["table-id"].startswith(f"astrotwo-{win.samp.launch}-sed{tab.command_number}-")
    table = parse_votable(urllib.parse.urlparse(params["url"]).path).get_first_table().to_table()
    points = tab.views["photometry"].data["details"]["points"]
    assert len(table) == len(points) and {"wavelength", "flux_nu", "band", "catalog"} <= set(table.colnames)
