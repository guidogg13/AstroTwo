# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del 05 per lo sprint 4f del 41: stile iniziale dei MOC in ``moc.open`` (rieseguito uguale), corpi diversi
con ``BODY_MISMATCH`` e forzatura, comandi dei livelli. Senza Qt e senza rete."""

import astropy.units as u
import pytest
from astropy.coordinates import SkyCoord
from mocpy import MOC

from astrotwo.core import planetary_data as pd
from astrotwo.core.commands import (
    CATALOG_COLORS,
    MOC_COLORS,
    MOC_FILL,
    Command,
    RequestedBy,
    Session,
    default_registry,
)
from astrotwo.core.moc import CircleRegion, Moc, moc_from_region, write_moc


def run(session, name, /, **params):
    return session.run(Command(name, 1, params, RequestedBy("menu")))


@pytest.fixture
def session(cache):
    return Session(default_registry(cache=cache))


def sky_moc(tmp_path, name="m.fits", radius=1.0):
    path = tmp_path / name
    write_moc(moc_from_region(CircleRegion(SkyCoord(10 * u.deg, 20 * u.deg), radius * u.deg), 8), path)
    return str(path)


def mars_moc(tmp_path):
    path = tmp_path / "mars.fits"
    write_moc(Moc(moc=MOC.from_string("3/1-5"), kind="space", body="Mars", origin="test"), path, overwrite=True)
    return str(path)


def test_moc_initial_style_in_opening_order_and_replayed(session, tmp_path):
    styles = [run(session, "moc.open", file={"path": sky_moc(tmp_path, f"m{k}.fits")}).values["style"]
              for k in range(3)]
    assert MOC_COLORS == CATALOG_COLORS[::-1] and MOC_FILL == 0.25
    assert styles == [{"color": MOC_COLORS[k], "fill": 0.25} for k in range(3)]
    assert MOC_COLORS[0] != CATALOG_COLORS[0]  # primo MOC e primo catalogo con colori diversi
    for layer, style in zip(session.workspace.state.of_kind("moc"), styles, strict=True):
        assert layer.style == style and layer.state_json()["style"] == style
    path = tmp_path / "s.astrotwo"
    session.save(path, app_version="0.1.0")
    loaded = Session.load(path, default_registry(cache=session.registry.cache))
    assert loaded.replay().status == "ok"
    assert [x.style for x in loaded.workspace.state.of_kind("moc")] == styles


def test_body_mismatch_then_forced(session, tmp_path):
    assert run(session, "moc.open", file={"path": sky_moc(tmp_path)}).status == "ok"
    result = run(session, "moc.open", file={"path": mars_moc(tmp_path)})
    assert result.status == "error" and result.error.code == "BODY_MISMATCH" and "Mars" in result.error.text
    # forzata con i dati planetari spenti (default): il 19 lo dice
    forced = run(session, "moc.open", file={"path": mars_moc(tmp_path)}, force_body=True)
    assert forced.error.code == "PLANETARY_DATA_DISABLED"
    pd.set_planetary_data_enabled(True)
    try:
        forced = run(session, "moc.open", file={"path": mars_moc(tmp_path)}, force_body=True)
    finally:
        pd.set_planetary_data_enabled(False)
    assert forced.status == "ok" and "BODY_MISMATCH_FORCED" in [w.code for w in forced.warnings]
    layer = session.workspace.state.layer(forced.values["layer"])
    assert layer.force_body and layer.state_json()["force_body"] is True


def test_layer_commands_order_opacity_visibility(session, tmp_path):
    ids = [run(session, "moc.open", file={"path": sky_moc(tmp_path, f"m{k}.fits")}).values["layer"] for k in range(3)]
    assert run(session, "layer.move", layer=ids[0], position=2).values["order"] == [ids[1], ids[2], ids[0]]
    assert run(session, "layer.set_opacity", layer=ids[1], opacity=0.4).status == "ok"
    assert run(session, "layer.set_visible", layer=ids[2], visible=False).status == "ok"
    state = session.workspace.state
    assert [x.id for x in state.layers] == [ids[1], ids[2], ids[0]]
    assert state.layer(ids[1]).opacity == 0.4 and not state.layer(ids[2]).visible
    assert run(session, "layer.remove", layer=ids[2]).values["order"] == [ids[1], ids[0]]
