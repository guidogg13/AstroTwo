# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del 05 per lo sprint 4c del 41: ``view.set_overlays`` (indicatore del nord e barra di scala, §3.18) e la
griglia nel frame scelto. Senza Qt e senza rete. Valori attesi ricalcolati chiamando direttamente il 10."""

import pytest

from astrotwo.core import coordinates_wcs as cw
from astrotwo.core.commands import Command, RequestedBy, Session, default_registry
from tests.core.test_commands import WINDOW, run, sky


@pytest.fixture
def session(cache):
    return Session(default_registry(cache=cache))


def zoomed(session, lon=56.75, lat=24.12, arcsec=20.0):
    assert run(session, "view.set_zoom", scale={"value": arcsec, "unit": "arcsec"}, window=WINDOW).status == "ok"
    assert run(session, "view.set_center", position=sky(lon, lat), window=WINDOW).status == "ok"
    return session.workspace.state.view


def test_overlays_on_by_default_and_equal_to_the_core(session):
    view = zoomed(session)
    assert view.compass_visible and view.scale_bar_visible
    expected = cw.compass_and_scale_bar(view.geometry, frame="icrs")
    assert view.compass == expected
    result = run(session, "view.set_center", position=sky(56.75, 24.12), window=WINDOW)
    shown = result.values["compass"]
    assert shown["north"] == list(expected.north) and shown["east"] == list(expected.east)
    assert shown["bar_pixels"] == expected.bar_pixels and shown["bar_label"] == expected.label


def test_set_overlays_toggles_and_is_recorded(session):
    zoomed(session)
    result = run(session, "view.set_overlays", compass=False, scale_bar=True)
    assert result.status == "ok" and result.values["compass_visible"] is False
    view = session.workspace.state.view
    assert (view.compass_visible, view.scale_bar_visible) == (False, True) and view.compass is not None
    run(session, "view.set_overlays", compass=False, scale_bar=False)
    assert session.workspace.state.view.compass is None  # niente da calcolare
    assert session.workspace.state.state_json()["view"]["overlays"] == {"compass": False, "scale_bar": False}
    entry = session.history.entries[-1].command
    assert entry.name == "view.set_overlays" and entry.parameters == {"compass": False, "scale_bar": False}
    run(session, "view.set_overlays")  # valori di default registrati: entrambi accesi
    assert session.history.entries[-1].command.parameters == {"compass": True, "scale_bar": True}
    assert session.workspace.state.view.compass is not None


def test_compass_follows_the_grid_frame(session):
    view = zoomed(session)
    run(session, "view.set_grid", visible=True, frame="galactic")
    view = session.workspace.state.view
    assert view.compass.frame_name == "galactic"
    assert view.compass == cw.compass_and_scale_bar(view.geometry, frame="galactic")
    run(session, "view.set_grid", visible=False, frame="galactic")  # griglia spenta: ICRS
    assert session.workspace.state.view.compass.frame_name == "icrs"


def test_overlays_without_view_and_replay(session, cache):
    assert run(session, "view.set_overlays", compass=False, scale_bar=True).status == "ok"  # nessuna vista ancora
    assert session.workspace.state.view.compass is None
    zoomed(session)
    run(session, "view.set_grid", visible=True)
    other = Session(default_registry(cache=cache))
    for entry in session.history.entries:
        assert other.run(Command(entry.command.name, 1, dict(entry.command.parameters), RequestedBy("session"))
                         ).status == "ok"
    assert other.workspace.state.state_json() == session.workspace.state.state_json()
    assert other.workspace.state.view.compass == session.workspace.state.view.compass
