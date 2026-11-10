# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Finestra «Profili» (``mdfiles/43-ui-profili.md`` §12).

Servizi simulati con le risposte vere registrate il 2026-11-07 (``tests/analysis/profile_fakes.py``: SIMBAD di
Harvard, archivio Gaia ESA, IRSA, NASA Exoplanet Archive, ESASky; CDS giù quel giorno). Nessuna rete.
"""

from __future__ import annotations

import time

import astropy.units as u
import pytest
from PySide6.QtCore import QSettings

import astrotwo.analysis.object_profile as op
from astrotwo.core.commands import default_registry
from astrotwo.ui.main_window import MainWindow, ThreadCache, register_analysis_commands
from astrotwo.ui.profiles import ProfileTab, SectionView
from tests.analysis.profile_fakes import recorded, services  # noqa: F401
from tests.ui.test_main_window import settings_path, wait_idle  # noqa: F401 - fixture


@pytest.fixture(scope="module", autouse=True)
def warm_matplotlib():
    """Prima figura di matplotlib fuori dai tempi misurati (cache dei caratteri)."""
    import io

    from matplotlib.figure import Figure

    figure = Figure()
    figure.text(0.5, 0.5, "λ Fν µm")
    figure.savefig(io.BytesIO(), format="png")


@pytest.fixture
def win(qtbot, settings_path, cache, services):  # noqa: F811
    settings = QSettings(settings_path, QSettings.Format.IniFormat)
    registry = default_registry(cache=ThreadCache(root=cache.root))
    register_analysis_commands(registry)
    window = MainWindow(registry=registry, settings=settings, startup_commands=False)
    window.confirm = lambda title, text: True
    window.modals = []
    window.show_modal = lambda title, text: window.modals.append((title, text))
    window.auto_column_dialogs = False
    qtbot.addWidget(window)
    window.resize(1000, 700)
    window.show()
    yield window
    if window.profiles is not None:
        window.profiles.close()
    window.confirm = lambda title, text: True
    window.close()


def delayed(services, service: str, seconds: float, text: str = "") -> None:  # noqa: F811
    def make(query):
        time.sleep(seconds)
        return recorded(service, query)
    services.overrides[(service, text)] = make


def states(tab: ProfileTab) -> dict[str, str]:
    return {name: view.state for name, view in tab.views.items()}


def finished(win, tab: ProfileTab) -> bool:
    return not win.busy() and tab.state in ("done", "cancelled", "error")


# =============================================================================
# T1–T3 — scheletro subito, stati, arrivo progressivo, risultato definitivo


def test_t1_skeleton_at_once_then_sections_arrive(qtbot, win, services):  # noqa: F811
    delayed(services, "gaia", 5.0, "FROM gaiadr3.gaia_source WHERE source_id")  # astrometria e fotometria lente
    seen: list[tuple[str, dict]] = []
    tab = win.open_profile({"name": "51 Peg"})
    # scheletro subito, prima di ogni risposta: tutte le sezioni «In attesa», scheda nella finestra Profili
    assert win.profiles.isVisible() and win.profiles.tabs.currentWidget() is tab
    assert list(tab.views) == ["identity", "images", "astrometry", "photometry", "planets"]
    assert set(states(tab).values()) == {"waiting"}
    assert all("Waiting" in v.header.text() for v in tab.views.values())
    assert tab.status.text().startswith("Queued") or tab.status.text().startswith("Running")
    # in corso con i servizi della sezione e i secondi
    qtbot.waitUntil(lambda: tab.views["astrometry"].state == "running", timeout=10000)
    header = tab.views["astrometry"].header.text()
    assert "Running · Gaia archive (ESA) ·" in header and header.endswith(" s")
    assert "SIMBAD, Gaia archive (ESA), IRSA, NASA Exoplanet Archive" in tab.views["identity"].header.text()
    assert tab.title.text() == "*  51 Peg"  # bersaglio risolto (evento resolved)
    # arrivo progressivo: le Immagini e i Pianeti arrivano mentre l'astrometria aspetta l'archivio Gaia
    qtbot.waitUntil(lambda: tab.views["planets"].state == "done", timeout=20000)
    seen.append(("planets", states(tab)))
    assert seen[0][1]["astrometry"] == "running"
    assert tab.views["planets"].findChild(object, "planetsTable") is not None
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    assert tab.state == "done" and tab.status.text().startswith("Done in")
    assert states(tab) == {"identity": "done", "images": "done", "astrometry": "done", "photometry": "partial",
                           "planets": "done"}
    # risultato definitivo: numero del comando nella testata e in ogni sezione
    number = win.session.history.entries[-1].number
    assert tab.command_number == number and tab.command_button.text() == f"#{number}"
    assert all(v.command_number == number for v in tab.views.values())
    header = tab.views["astrometry"].header.text()
    assert "Arrived · 127.0.0.1 · " in header and f"#{number}" in header  # server che ha risposto (simulato)
    assert "in part" in tab.views["photometry"].header.text()  # serie VizieR in errore (CDS giù)
    # errore di rete di VizieR, oppure serie saltata se il MocServer simulato (connessione rifiutata all'istante) ha
    # già dato la prova del CDS giù quando VizieR parte (25 §3.17 punto 3)
    assert tab.views["photometry"].errors_label.isVisibleTo(tab) and \
        tab.views["photometry"].errors_label.text().startswith(("SERVICE_ERROR", "PROFILE_VIZIER_SKIPPED"))
    assert tab.fresh_button.isEnabled() and tab.sky_button.isEnabled()
    assert win.profiles.tabs.tabText(win.profiles.tabs.indexOf(tab)) == "*  51 Peg"


def test_t2_contents_of_the_sections(qtbot, win, services):  # noqa: F811
    tab = win.open_profile({"name": "51 Peg"})
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    identity = tab.views["identity"]
    assert "Gaia DR3 2835207319109249920" in identity.findChild(object, "identifiers").text()
    chain = identity.findChild(object, "crossIdentifications")
    assert chain.rowCount() == 4
    # collegamento solo verso i server SIMBAD ammessi (41 §3.19): il server simulato locale non lo è
    assert identity.findChild(object, "simbadLink") is None
    data = dict(identity.data)
    data["details"] = {**data["details"], "simbad_url": "https://simbad.harvard.edu/simbad/sim-id?Ident=%2A%2051%20Peg"}
    identity.show_section(data, tab.command_number)
    assert "https://simbad.harvard.edu/" in identity.findChild(object, "simbadLink").text()
    images = tab.views["images"]
    pictures = images.findChildren(object, "thumbnailPicture")
    assert len(pictures) == 3 and all(not p.pixmap().isNull() for p in pictures)
    assert pictures[0].pixmap().width() == 192
    photometry = tab.views["photometry"]
    table = photometry.findChild(object, "photometryPoints")
    assert table.rowCount() >= 10
    assert photometry.findChild(object, "sedPlot") is not None
    from astrotwo.ui.profiles import ValueTable

    astrometry = tab.views["astrometry"].body.findChild(ValueTable)
    rows = {astrometry.item(r, 0).text(): r for r in range(astrometry.rowCount())}
    assert "parallax" in rows and astrometry.item(rows["parallax"], 3).text() == "mas"
    planets = tab.views["planets"].findChild(object, "planetsTable")
    assert planets.rowCount() == 1 and planets.item(0, 0).text() == "51 Peg b"


# =============================================================================
# T4 — sezione in errore e «Riprova questa sezione»


def test_t4_error_and_retry_this_section(qtbot, win, services, monkeypatch):  # noqa: F811
    limit = op._section_limit
    monkeypatch.setattr(op, "_section_limit", lambda name: 0.3 * u.s if name == "planets" else limit(name))
    delayed(services, "exoplanet", 1.0, "ORDER BY pl_name")
    tab = win.open_profile({"name": "51 Peg", "sections": ["identity", "planets"]})
    qtbot.waitUntil(lambda: finished(win, tab), timeout=60000)
    planets = tab.views["planets"]
    assert planets.state == "error" and "Error" in planets.header.text()
    assert "PROFILE_SECTION_TIMEOUT" in planets.errors_label.text()
    assert planets.retry_button.isVisible()
    first = tab.command_number
    services.overrides.clear()
    monkeypatch.setattr(op, "_section_limit", limit)
    planets.retry_button.click()
    assert planets.state == "waiting"
    qtbot.waitUntil(lambda: not win.busy() and planets.state == "done", timeout=60000)
    entry = win.session.history.entries[-1]
    assert entry.command.name == "object.profile" and entry.command.parameters["sections"] == ["planets"]
    assert entry.command.parameters["simbad_id"] == "*  51 Peg" and entry.command.parameters["name"] == "51 Peg"
    assert planets.command_number == entry.number != first
    assert f"#{entry.number}" in planets.header.text()
    assert tab.views["identity"].command_number == first  # le altre sezioni restano quelle del primo comando
    assert not planets.retry_button.isVisible()


def test_planets_view_absence_only_after_a_request(qtbot):
    """D25-23: «No planet in the archive» solo dopo una richiesta vera e riuscita; senza richiesta «Not checked»
    (il motivo è nell'avviso); una sezione in errore non afferma niente."""
    from PySide6.QtWidgets import QLabel

    from astrotwo.ui.profiles import PlanetsView

    def shown(data):
        view = PlanetsView("planets", "Planets", ("exoplanet",))
        qtbot.addWidget(view)
        view.show_section({"name": "planets", "values": [], "servers": [], **data}, 1)
        return {w.objectName() for w in view.findChildren(QLabel)}

    checked = shown({"status": "done", "details": {"planets": [], "checked": True}})
    assert "noPlanets" in checked and "planetsNotChecked" not in checked
    unchecked = shown({"status": "not_applicable", "details": {"planets": [], "checked": False},
                       "warnings": [{"code": "PROFILE_PLANETS_NOT_CHECKED", "text": "x",
                                     "params": {"reason": "simbad_unavailable"}}]})
    assert "planetsNotChecked" in unchecked and "noPlanets" not in unchecked
    failed = shown({"status": "error", "details": {"planets": [], "checked": False},
                    "errors": [{"code": "SERVICE_ERROR", "text": "giù", "params": {}}]})
    assert "noPlanets" not in failed and "planetsNotChecked" not in failed
    old = shown({"status": "done", "details": {"planets": [], "note": "no planet in the archive"}})  # prima del 2026-11-10
    assert "noPlanets" not in old and "planetsNotChecked" in old


def test_section_view_states_text(qtbot):
    view = SectionView("astrometry", "Astrometry and distance", ("gaia",))
    qtbot.addWidget(view)
    assert view.header.text() == "Astrometry and distance · Waiting"
    view.set_running(time.monotonic() - 3.2)
    assert view.header.text() == "Astrometry and distance · Running · Gaia archive (ESA) · 3 s"
    view.set_cancelled()
    assert view.header.text() == "Astrometry and distance · Cancelled" and not view.retry_button.isHidden()
    view.show_section({"name": "astrometry", "status": "done", "values": [], "servers":
                       ["https://gea.esac.esa.int/tap-server/tap"], "elapsed": {"value": 1.25, "unit": "s"}}, 7)
    assert view.header.text() == "Astrometry and distance · Arrived · gea.esac.esa.int · 1.2 s  #7"
