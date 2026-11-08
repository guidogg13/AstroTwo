# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Finestra «Profili», seconda parte (``mdfiles/43-ui-profili.md`` §12, sprint C5b): aperture dai quattro punti,
dialogo dei candidati, Annulla con le sezioni conservate, riquadro della provenienza, grafico SED con i limiti
superiori, chiusura di una scheda in corso, traduzioni.

Risposte vere registrate il 2026-11-07 (``tests/analysis/profile_fakes.py``). Nessuna rete.
"""

from __future__ import annotations

import time

import astropy.units as u
from astropy.io.votable import from_table
from astropy.io.votable.tree import CooSys
from astropy.table import Table
from PySide6.QtWidgets import QApplication

from astrotwo.analysis.photometry import plot_sed_rows
from astrotwo.core.commands import Command, CommandResult
from astrotwo.ui.main_window import load_translations
from astrotwo.ui.profiles import (
    STSCI_DSS_TEXT,
    CandidatesDialog,
    ObjectProfileDialog,
    ValueTable,
    number_text,
    row_identifier,
)
from astrotwo.ui.sky_tools import PROFILE_LINK
from tests.analysis.profile_fakes import recorded, services  # noqa: F401
from tests.ui.test_main_window import settings_path, wait_idle  # noqa: F401 - fixture
from tests.ui.test_profiles import finished, win, warm_matplotlib  # noqa: F401 - fixture

AGOL = "2021PSJ.....2....1A"
ETA_TAU = (56.871152303749994, 24.105135651944444)


def delayed(services, service: str, seconds: float, text: str = "") -> None:  # noqa: F811
    def make(query):
        time.sleep(seconds)
        return recorded(service, query)
    services.overrides[(service, text)] = make


def last_profile(win) -> Command:
    return next(e.command for e in reversed(win.session.history.entries) if e.command.name == "object.profile")


def cell(table: ValueTable, first_column: str, column: int) -> tuple[int, int]:
    row = next(r for r in range(table.rowCount()) if table.item(r, 0).text() == first_column)
    return row, column


# =============================================================================
# T13 e aperture — menu Data, «Vai a», cielo, puntatore SIMBAD, tabella


def test_open_from_the_data_menu_with_name_and_coordinates(qtbot, win):
    action = win.findChild(object, "objectProfile")
    assert action.text() == "Object profile…"
    dialog = win.object_profile_dialog()
    dialog.text.setText("51 Peg")
    dialog._accept()
    tab = win.profiles.tabs.currentWidget()
    assert tab.params == {"name": "51 Peg"} and tab.title.text() == "51 Peg"
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    assert last_profile(win).requested_by.source == "menu"
    # coppia di coordinate: posizione con sistema ed epoca scritte nel comando (DC2)
    dialog = win.object_profile_dialog()
    dialog.text.setText("344.36658535524 20.768832511140005")
    dialog.epoch.setText("J2000.0")
    params = dialog.build()
    assert params["position"]["frame"] == "icrs" and params["position"]["epoch"] is not None
    assert params["position"]["lon"]["value"] == 344.36658535524
    # epoca non leggibile: messaggio nel dialogo, nessun comando
    dialog.epoch.setText("ieri")
    dialog._accept()
    assert dialog.params is None and "Epoch not readable: ieri" in dialog.error.text()
    dialog.text.setText("")
    dialog._accept()
    assert "Write a name or a coordinate pair" in dialog.error.text()


def test_open_from_the_go_to_field(qtbot, win):
    named = CommandResult("ok", values={"resolved": {"name": "51 Peg"}})
    win._offer_go_to_profile(Command("view.go_to", 1, {"text": "51 Peg"}), named)
    assert win.go_to_profile_action.isVisible() and win.go_to_profile.text() == "Profile"
    assert win._go_to_profile_timer.interval() == 30000
    win.go_to_profile.click()
    assert not win.go_to_profile_action.isVisible()
    tab = win.profiles.tabs.currentWidget()
    assert tab.params == {"name": "51 Peg"}
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    # coordinate scritte: nessun pulsante (l'epoca si dichiara dal menu)
    win._offer_go_to_profile(Command("view.go_to", 1, {"text": "10 20"}), CommandResult("ok", values={}))
    assert not win.go_to_profile_action.isVisible()


def test_open_from_the_sky_context_menu(qtbot, win, monkeypatch):
    monkeypatch.setattr(win.sky, "context_sky_text", lambda: None)
    menu = win._sky_context_menu(None)
    entry = next(a for a in menu.actions() if a.text() == "Profile at this position…")
    assert not entry.isEnabled()  # fuori dal cielo o senza WCS
    monkeypatch.setattr(win.sky, "context_sky_text", lambda: "344.36658535524 20.768832511140005")
    menu = win._sky_context_menu(None)
    entry = next(a for a in menu.actions() if a.text() == "Profile at this position…")
    assert entry.isEnabled()
    entry.trigger()
    dialog = win.last_profile_dialog
    assert isinstance(dialog, ObjectProfileDialog)
    assert dialog.text.text() == "344.36658535524 20.768832511140005" and dialog.epoch.text() == "J2000.0"
    dialog._accept()
    tab = win.profiles.tabs.currentWidget()
    assert "position" in tab.params
    qtbot.waitUntil(lambda: not win.busy(), timeout=60000)
    assert last_profile(win).requested_by.source == "mouse"


def test_open_from_the_simbad_pointer_card(qtbot, win):
    tool = win.sky.simbad_tool
    tool.last_request = {"radius": {"value": 10.0, "unit": "arcsec"}}
    result = CommandResult("ok", values={"object": {
        "main_id": "*  51 Peg", "otype": "PM*", "nbref": 1, "separation": {"value": 1.0, "unit": "arcsec"},
        "position": {"lon": {"value": 344.36, "unit": "deg"}, "lat": {"value": 20.76, "unit": "deg"},
                     "frame": "icrs"}, "magnitudes": []}})
    html = tool.card_html(result)
    assert "Profile of *  51 Peg" in html and PROFILE_LINK in html
    tool.open_link(PROFILE_LINK + "%2A%20%2051%20Peg")
    tab = win.profiles.tabs.currentWidget()
    assert tab.params == {"name": "*  51 Peg", "simbad_id": "*  51 Peg"}  # per identificativo (43 §3.2 punto 4)
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    assert tab.state == "done" and last_profile(win).requested_by.source == "mouse"


def test_open_from_a_table_row(qtbot, win, tmp_path):
    table = Table({"source_id": [123, 456], "ra": [344.36658535524, 10.0], "dec": [20.768832511140005, 10.0]})
    table["ra"].unit = table["dec"].unit = u.deg
    vot = from_table(table)
    fields = vot.get_first_table().fields
    fields[1].ucd, fields[2].ucd = "pos.eq.ra;meta.main", "pos.eq.dec;meta.main"
    vot.resources[0].coordinate_systems.append(CooSys(ID="sys", system="ICRS", epoch="J2000"))
    fields[1].ref = fields[2].ref = "sys"
    path = tmp_path / "rows.vot"
    vot.to_xml(str(path))
    win.submit("catalog.open_file", {"file": {"path": str(path)}})
    wait_idle(qtbot, win)
    layer = win.session.workspace.state.of_kind("catalog")[0]
    menu = win._table_context_menu(layer.id, None)
    entry = next(a for a in menu.actions() if a.text() == "Profile of this source")
    assert not entry.isEnabled()  # nessuna riga selezionata
    # una colonna source_id di un catalogo d'origine sconosciuta non è Gaia DR3: profilo per posizione
    tab = win.profile_of_row(layer.id, 0)
    assert tab.params == {"layer": layer.id, "row": 0}
    qtbot.waitUntil(lambda: not win.busy(), timeout=60000)
    # riconoscimento dall'origine del livello (D43-3)
    assert row_identifier({"catalog": "I/355/gaiadr3"}, {"Source": 2835207319109249920}) == \
        "Gaia DR3 2835207319109249920"
    assert row_identifier({"table": "gaiadr3.gaia_source"}, {"source_id": 66714384142368256}) == \
        "Gaia DR3 66714384142368256"
    assert row_identifier({"catalog": "II/246/out"}, {"2MASS": "22572795+2046077"}) == "2MASS J22572795+2046077"
    assert row_identifier({"table": "allwise_p3as_psd"}, {"designation": "J225728.12+204608.6"}) == \
        "WISEA J225728.12+204608.6"
    assert row_identifier({"catalog": "simbad"}, {"main_id": "*  51 Peg"}) == "*  51 Peg"
    assert row_identifier({"catalog": "my_file.vot"}, {"source_id": 123}) is None
    assert row_identifier({"catalog": "I/355/gaiadr3"}, {"Source": None}) is None


# =============================================================================
# T8 — bersaglio ambiguo: dialogo, nessuna scelta automatica


def test_t8_ambiguous_target_dialog(qtbot, win, services):  # noqa: F811
    from astrotwo.core.commands import sky_json
    from astrotwo.core.coordinates_wcs import SkyFrame
    from astropy.time import Time

    position = sky_json(SkyFrame.from_lonlat(ETA_TAU[0] * u.deg, ETA_TAU[1] * u.deg, "icrs",
                                             epoch=Time("J2000.0")))
    tab = win.open_profile({"position": position})
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    assert tab.state == "error" and "PROFILE_AMBIGUOUS_TARGET" in tab.status.text()
    dialog = win.profiles.last_dialog
    assert isinstance(dialog, CandidatesDialog)
    names = [dialog.table.item(r, 0).text() for r in range(dialog.table.rowCount())]
    assert len(names) == 2 and "GN 03.44.2" in names
    ok = dialog.buttons.buttons()[0]
    assert not dialog.table.selectionModel().selectedRows()  # nessuna voce scelta in partenza
    assert not any(b.isEnabled() for b in dialog.buttons.buttons() if b.text() == "Profile of this object")
    before = win.profiles.tabs.count()
    star = next(r for r, n in enumerate(names) if n != "GN 03.44.2")
    # il profilo scelto cerca l'oggetto per il suo main_id: stessa risposta registrata del nome «eta Tau»
    by_name = next(k.split("|", 1)[1] for k in __import__("tests.analysis.profile_fakes", fromlist=["INDEX"]).INDEX
                   if k.startswith("simbad|") and "WHERE i.id = 'eta Tau'" in k)
    services.overrides[("simbad", f"WHERE i.id = '{names[star]}'")] = lambda q: recorded("simbad", by_name)
    dialog.choose(star)
    assert ok is not None and win.profiles.tabs.count() == before + 1
    chosen = win.profiles.tabs.currentWidget()
    assert chosen.params["simbad_id"] == names[star] and chosen.params["position"] == position
    qtbot.waitUntil(lambda: finished(win, chosen), timeout=60000)
    assert chosen.state == "done" and last_profile(win).parameters["simbad_id"] == names[star]


# =============================================================================
# T5 — Annulla: arrivate conservate, le altre annullate


def test_t5_cancel_keeps_the_arrived_sections(qtbot, win, services):  # noqa: F811
    for service in ("exoplanet", "irsa"):
        delayed(services, service, 4.0)
    tab = win.open_profile({"name": "TRAPPIST-1", "sections": ["identity", "astrometry", "photometry"]})
    qtbot.waitUntil(lambda: tab.views["astrometry"].state == "done", timeout=30000)
    win.cancel_running()  # Annulla della barra di stato
    qtbot.waitUntil(lambda: finished(win, tab), timeout=30000)
    assert tab.state == "cancelled" and tab.status.text().startswith("Cancelled")
    assert tab.views["astrometry"].state == "done"
    for name in ("identity", "photometry"):
        assert tab.views[name].state == "cancelled" and tab.views[name].retry_button.isVisibleTo(tab)
        assert "Cancelled" in tab.views[name].header.text()


def test_closing_a_running_tab_cancels_its_command(qtbot, win, services):  # noqa: F811
    delayed(services, "exoplanet", 4.0)
    asked = []
    win.confirm = lambda title, text: asked.append((title, text)) or True
    tab = win.open_profile({"name": "TRAPPIST-1", "sections": ["planets"]})
    qtbot.waitUntil(lambda: tab.state == "running", timeout=10000)
    count = win.profiles.tabs.count()
    assert win.profiles.close_tab(win.profiles.tabs.indexOf(tab))
    assert asked and asked[0][0] == "Close profile"
    qtbot.waitUntil(lambda: not win.busy(), timeout=30000)
    assert win.session.history.entries[-1].result.status == "cancelled"
    assert win.profiles.tabs.count() == count - 1 and not win.profiles.jobs


# =============================================================================
# T6 — riquadro della provenienza


def test_t6_provenance_popup(qtbot, win):
    tab = win.open_profile({"name": "51 Peg", "sections": ["astrometry"]})
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    table = tab.views["astrometry"].body.findChild(ValueTable)
    table.cellClicked.emit(*cell(table, "parallax", 1))
    popup = tab.popup
    assert popup is not None and popup.isVisible()
    value = tab.views["astrometry"].values()["parallax"]
    rows = dict(popup.rows)
    assert rows["Value"] == number_text(value["value"]) and rows["Unit"] == "mas"
    assert rows["Error"] == f"± {number_text(value['error'])}"
    assert rows["Method"] == "read from the service"
    assert rows["Table"] == "gaiadr3.gaia_source"
    assert "source_id = 2835207319109249920" in rows["Query"]
    assert rows["Server"] == value["provenance"]["server"] and rows["Retrieved"] == value["provenance"]["retrieved_at"]
    assert rows["From cache"] in ("yes", "no")
    assert f"#{tab.command_number}" in rows["Command"]
    text = popup.plain_text()
    assert "Table: gaiadr3.gaia_source" in text and "<" not in text.split("Query: ")[0]
    popup.copy()
    assert QApplication.clipboard().text() == text
    shown = []
    win.show_command = lambda number: shown.append(number)
    popup.text_label.linkActivated.emit(f"command:{tab.command_number}")
    assert shown == [tab.command_number]


def test_t6_planet_reference_is_an_ads_link(qtbot, win):
    tab = win.open_profile({"name": "TRAPPIST-1", "sections": ["planets"]})
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    table = tab.views["planets"].findChild(object, "planetsTable")
    assert table.rowCount() == 7
    row, _ = cell(table, "TRAPPIST-1 b", 0)
    assert table.item(row, 2).text().startswith("1.510826 +6e-06 / -6e-06 d")
    table.cellClicked.emit(row, 2)
    rows = dict(tab.popup.rows)
    assert f"https://ui.adsabs.harvard.edu/abs/{AGOL}/abstract" in rows["Reference"]
    assert rows["Error"] == "+6e-06 / -6e-06" and rows["Table"] == "pscomppars"
    assert "PROFILE_PLANETS_COMPOSITE" not in tab.views["planets"].warnings_label.text()
    assert "pscomppars" in tab.views["planets"].warnings_label.text()  # avviso nella lingua dell'interfaccia


# =============================================================================
# T11 — grafico SED con i limiti superiori; T9 — crediti delle miniature


def test_t11_sed_plot_with_upper_limits(qtbot, win):
    tab = win.open_profile({"name": "TRAPPIST-1", "sections": ["photometry"]})
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    view = tab.views["photometry"]
    assert view.findChild(object, "sedPlot") is not None
    ax = view.figure.axes[0]
    assert ax.get_xscale() == "log" and ax.get_yscale() == "log"
    assert ax.get_xlabel() == "λ (µm)" and ax.get_ylabel() == "Fν (Jy)"
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert "AllWISE upper limit" in labels and "Gaia DR3" in labels  # W4 di TRAPPIST-1 (ph_qual U) come freccia
    points = view.data["details"]["points"]
    upper = [p for p in points if p["upper_limit"]]
    assert upper and all(not p["in_plot"] for p in upper)  # fuori dalla serie dei punti misurati (D43-9)
    table = view.findChild(object, "photometryPoints")
    assert any("upper limit" in table.item(r, 7).text() for r in range(table.rowCount()))
    # stesse frecce fuori dalla finestra (PNG del risultato ed esportazione): D43-9, ovunque
    again = plot_sed_rows(points, None)
    assert "AllWISE upper limit" in [t.get_text() for t in again.axes[0].get_legend().get_texts()]


def test_t9_thumbnail_credits_with_the_stsci_text(qtbot, win):
    tab = win.open_profile({"name": "51 Peg", "sections": ["images"]})
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    credits = [c.text() for c in tab.views["images"].findChildren(object, "thumbnailCredits")]
    captions = [c.text() for c in tab.views["images"].findChildren(object, "thumbnailCaption")]
    assert len(credits) == 3
    assert "NAG W-2166" in credits[0] and "https://archive.stsci.edu/dss/acknowledging.html" in credits[0]
    assert STSCI_DSS_TEXT.split(".")[0] in credits[0]
    assert all("NAG W-2166" not in c for c in credits[1:])
    assert "Center epoch: 2010.545" in captions[2] or "Center epoch: J2010.5" in captions[2]


# =============================================================================
# T16 — traduzioni


def test_t16_italian_texts(qtbot, win):
    try:
        load_translations("it")
        tab = win.open_profile({"name": "51 Peg", "sections": ["identity", "astrometry"]})
        assert tab.fresh_button.text() == "Riesegui con dati aggiornati" and tab.sky_button.text() == "Mostra nel cielo"
        assert tab.views["identity"].header.text() == "Identità · In attesa"  # contesto di SectionView
        assert tab.views["astrometry"].retry_button.text() == "Riprova questa sezione"
        assert win.profiles.windowTitle() == "Profili"
        qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
        assert tab.status.text().startswith("Finito in")
        assert tab.views["astrometry"].header.text().startswith("Astrometria e distanza · Arrivata · ")
        dialog = CandidatesDialog([{"main_id": "a", "otype": "*", "separation": {"value": 1.0, "unit": "arcsec"},
                                    "nbref": 3}])
        assert dialog.windowTitle() == "Scegli l'oggetto"
    finally:
        load_translations("en")


# =============================================================================
# Pulsanti della scheda in C5 (43 §3.4; brief punto f)


def test_tab_buttons_rerun_fresh_and_show_in_sky(qtbot, win):
    tab = win.open_profile({"name": "51 Peg", "sections": ["identity"]})
    assert not tab.fresh_button.isEnabled() and not tab.sky_button.isEnabled()
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    names = {b.objectName() for b in tab.findChildren(type(tab.fresh_button)) if b.isVisibleTo(tab)}
    assert {"rerunFresh", "showInSky"} <= names
    assert {"exportProfile", "loadSedCatalog", "sendSedSamp"} <= names  # pulsanti dello sprint C6 (43 §3.10)
    tab.sky_button.click()
    qtbot.waitUntil(lambda: not win.busy(), timeout=30000)
    entry = win.session.history.entries[-1]
    assert entry.command.name == "view.set_center"
    assert entry.command.parameters["position"]["lon"] == tab.resolved["position"]["lon"]
    count = win.profiles.tabs.count()
    tab.fresh_button.click()
    fresh = win.profiles.tabs.currentWidget()
    assert win.profiles.tabs.count() == count + 1 and fresh is not tab  # scheda nuova (D43-1)
    qtbot.waitUntil(lambda: finished(win, fresh), timeout=60000)
    command = last_profile(win)
    assert command.refresh is True and command.parameters["simbad_id"] == "*  51 Peg"
    assert command.parameters["sections"] == ["identity"]
