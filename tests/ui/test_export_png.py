# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del visualizzatore del cielo (41 §12), sprint 4h: esportazione della vista in PNG (T14, 41 §3.14).

Piattaforma ``offscreen`` con il renderer in memoria (che compone i piani come ``render_offscreen``); il PNG si rilegge
con Pillow e i blocchi ``tEXt`` si confrontano con il risultato del comando e con lo stato dello spazio di lavoro.
"""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import astropy.units as u
import numpy as np
import pytest
from PIL import Image

import astrotwo
from astrotwo.core import coordinates_wcs as cw
from astrotwo.core import hips
from astrotwo.core.commands import Layer, ViewState, WorkspaceState, quantity_json, sky_json
from astrotwo.ui import export_view as ev
from tests.core.test_commands_catalog_sky import write_catalog
from tests.ui.test_catalog_sky import PLEIADES, open_file, wait_points, wait_settled
from tests.ui.test_main_window import make_window, settings_path, wait_idle  # noqa: F401 - fixture
from tests.ui.test_sky_viewer import serve_png_survey


def hips_layer(hips_id, title, **properties):
    service = SimpleNamespace(hips_id=hips_id, title=title, properties={k: (v,) for k, v in properties.items()},
                              origin="https://example.invalid/properties",
                              retrieved_at=datetime(2026, 10, 1, 12, tzinfo=UTC))
    return Layer("L1", "hips", title, service, source="https://example.invalid")


def catalog_layer(layer_id, name, origin, visible=True):
    table = SimpleNamespace(origin=origin, retrieved_at=datetime(2026, 10, 2, 8, 30, tzinfo=UTC))
    return Layer(layer_id, "catalog", name, table, visible=visible, source=origin)


def test_credits_follow_the_visible_layers():
    state = WorkspaceState(layers=(
        hips_layer("CDS/P/DSS2/color", "DSS colored"),
        hips_layer("TEST/P/other", "Other survey", obs_ack="Thanks to the test team", obs_copyright="(c) test"),
        catalog_layer("L3", "basic", "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"),
        catalog_layer("L4", "I/355/gaiadr3", "https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync"),
        catalog_layer("L5", "hidden", "https://tapvizier.cds.unistra.fr/x", visible=False),
        catalog_layer("L6", "local", "/Users/me/catalog.xml")))
    entries = {c.key: c for c in ev.credit_entries(state)}
    assert set(entries) == {"dss", "hips:TEST/P/other", "simbad", "vizier", "table:L4"}
    assert entries["dss"].full == ev.DSS_TEXT and entries["dss"].full.startswith("The Digitized Sky Surveys")
    assert entries["hips:TEST/P/other"].full == (
        "Other survey (TEST/P/other): Thanks to the test team (c) test")  # il testo del survey, non un testo nostro
    assert entries["simbad"].full == ev.SIMBAD_TEXT and "Wenger et al." in ev.SIMBAD_TEXT
    assert "10.26093/cds/vizier" in entries["vizier"].full
    assert "I/355/gaiadr3" in entries["table:L4"].full
    assert ev.credit_line(ev.credit_entries(state)).startswith("Credits: DSS (STScI, Palomar, UKST) · Other survey")
    # nessun credito senza servizi (immagini e cataloghi da file) e nessuna riga
    assert ev.credit_entries(WorkspaceState(layers=(catalog_layer("L1", "local", "/tmp/c.xml"),))) == ()
    assert ev.credit_line(()) == ""
    # un survey senza testo dichiarato: solo titolo e identificativo
    plain = ev.credit_entries(WorkspaceState(layers=(hips_layer("TEST/P/plain", "Plain"),)))
    assert [c.full for c in plain] == ["Plain (TEST/P/plain)"]


def test_path_validation(tmp_path):
    assert ev.validate_path(str(tmp_path / "a.png")) == tmp_path / "a.png"
    assert ev.validate_path(str(tmp_path / "A.PNG")) == tmp_path / "A.PNG"
    for bad in ("relative.png", str(tmp_path / "a.jpg"), str(tmp_path / "missing" / "a.png"), str(tmp_path / "a")):
        with pytest.raises(Exception) as caught:
            ev.validate_path(bad)
        assert caught.value.code == "EXPORT_PATH_INVALID"
    (tmp_path / "dir.png").mkdir()
    with pytest.raises(Exception) as caught:
        ev.validate_path(str(tmp_path / "dir.png"))
    assert caught.value.code == "EXPORT_PATH_INVALID"


def test_metadata_is_latin1_and_needs_a_view():
    with pytest.raises(Exception) as caught:
        ev.compose_metadata(WorkspaceState(), night=False)
    assert caught.value.code == "VIEW_UNDEFINED"
    assert ev._latin1("Åα→") == "Å??"
    state = WorkspaceState(view=ViewState())
    with pytest.raises(Exception) as caught:
        ev.compose_metadata(state, night=False)
    assert caught.value.code == "VIEW_UNDEFINED"


@pytest.fixture
def win(qtbot, settings_path, cache, service, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(hips, "survey_coverage", lambda svc, **k: hips.service_coverage(svc, **k))
    win = make_window(qtbot, settings_path, cache)
    win.survey_url = serve_png_survey(service)
    yield win
    win.close()


def start(qtbot, win):
    win.submit("hips.set_survey", {"survey": win.survey_url})
    win.sky.start_view()
    wait_idle(qtbot, win)
    window = win.view_window()
    win.submit("view.set_zoom", {"scale": quantity_json((30.0 * u.arcsec).to(u.deg)), "window": window})
    win.submit("view.set_center", {"position": sky_json(cw.SkyFrame.from_lonlat(*(PLEIADES * u.deg), "icrs")),
                                   "window": window})
    wait_settled(qtbot, win)
    qtbot.waitUntil(lambda: win.sky._in_flight == 0 and win.sky._stage is None, timeout=20000)


def export(qtbot, win, path):
    win.submit("view.export_png", {"path": str(path)})
    wait_idle(qtbot, win)
    return win.session.history.entries[-1]


def test_t14_png_with_metadata_and_credits(qtbot, win, tmp_path):
    start(qtbot, win)
    catalog = write_catalog(tmp_path / "c.xml")
    open_file(qtbot, win, "catalog.open_file", catalog)
    wait_points(qtbot, win, 3)
    # l'apertura del catalogo può ridimensionare la vista: si aspettano i tile della finestra nuova
    qtbot.waitUntil(lambda: win.sky._in_flight == 0 and win.sky._stage is None, timeout=20000)
    wait_settled(qtbot, win)
    qtbot.waitUntil(lambda: win.sky._in_flight == 0, timeout=20000)
    out = tmp_path / "view.png"
    shots = []
    original = win.sky.renderer.render_offscreen
    win.sky.renderer.render_offscreen = lambda: shots.append(original()) or shots[-1]  # il disegno scritto nel file
    entry = export(qtbot, win, out)
    assert entry.command.name == "view.export_png" and entry.result.status == "ok"
    values = entry.result.values
    assert values["path"] == str(out)
    state = win.session.workspace.state
    window = win.view_window()
    assert (values["width"], values["height"]) == ({"value": float(window["width"]), "unit": "pixel"},
                                                   {"value": float(window["height"]), "unit": "pixel"})
    with Image.open(out) as picture:
        assert picture.format == "PNG" and picture.size == (window["width"], window["height"])  # pixel fisici
        text = dict(picture.text)
        pixels = np.asarray(picture.convert("RGB"))
    assert text == values["metadata"]  # i blocchi tEXt sono quelli scritti nel risultato del comando
    assert text["Software"] == f"AstroTwo {astrotwo.__version__}"
    assert datetime.fromisoformat(text["Creation Time"].replace("Z", "+00:00")).tzinfo is not None
    view = json.loads(text["AstroTwo:View"])
    expected = state.view.state_json()
    for key in ("center", "scale", "projection", "frame", "window", "base_layer"):
        assert view[key] == expected[key]
    assert view["field_of_view"]["unit"] == "deg" and view["night_mode"] is False
    layers = json.loads(text["AstroTwo:Layers"])
    assert [(x["id"], x["kind"], x["name"]) for x in layers] == [(x.id, x.kind, x.name) for x in state.layers]
    survey = layers[0]
    assert survey["origin"].endswith("/png/properties") and survey["retrieved_at"].endswith("Z")
    assert layers[1]["origin"] == catalog and layers[1]["retrieved_at"].endswith("Z")
    # crediti: il survey di prova non dichiara testi, il catalogo è un file: nessun servizio con testo proprio
    assert values["credits"] == [f"Survey di prova ({win.sky.service.hips_id})"]
    assert text["AstroTwo:Credits"] == values["credits"][0]
    assert values["credit_line"] == "Credits: Survey di prova"
    # la riga dei crediti è disegnata in basso a destra (fondo scuro) e non nel resto dell'immagine
    plain = shots[-1]
    ptr = np.frombuffer(plain.constBits(), np.uint8).reshape(plain.height(), plain.bytesPerLine())[:, : 3 * plain.width()]
    plain_pixels = ptr.reshape(plain.height(), plain.width(), 3)
    changed = np.any(pixels != plain_pixels, axis=2)
    ys, xs = np.nonzero(changed)
    assert len(ys) and ys.min() > 0.9 * window["height"] and xs.min() > 0.4 * window["width"]
    assert not changed[: int(0.9 * window["height"])].any()
    r = win.sky.renderer
    assert plain_pixels.any(), (r.layers, {k: (v.shape, int(v[..., :3].max()), int(v[..., 3].max())) for k, v in r.textures.items()}, win.sky._stage, r.size())  # il disegno non è vuoto
    # nessun file temporaneo rimasto, comando registrato e senza effetto sullo stato
    assert [p.name for p in tmp_path.iterdir() if p.suffix == ".part" or p.name.endswith(".part")] == []
    assert win.session.workspace.state.layers == state.layers


def test_t14_errors_and_no_partial_file(qtbot, win, tmp_path, monkeypatch):
    # vista senza geometria
    entry = export(qtbot, win, tmp_path / "none.png")
    assert entry.result.status == "error" and entry.result.error.code == "VIEW_UNDEFINED"
    assert not (tmp_path / "none.png").exists()
    start(qtbot, win)
    for bad in ("relative.png", str(tmp_path / "x.jpg"), str(tmp_path / "missing" / "x.png")):
        entry = export(qtbot, win, bad)
        assert entry.result.status == "error" and entry.result.error.code == "EXPORT_PATH_INVALID"
    assert list(tmp_path.glob("*.png")) == []
    # scrittura che fallisce: comando ok, messaggio EXPORT_FAILED, nessun file né file a metà
    def broken(self, *args, **kwargs):
        raise OSError("disco pieno di prova")

    monkeypatch.setattr(Image.Image, "save", broken)
    target = tmp_path / "fail.png"
    entry = export(qtbot, win, target)
    assert entry.result.status == "ok"
    qtbot.waitUntil(lambda: any(m[1] == "EXPORT_FAILED" for m in win.messages.messages), timeout=5000)
    message = [m for m in win.messages.messages if m[1] == "EXPORT_FAILED"][-1]
    assert "disco pieno di prova" in message[2] and message[3] is True
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith((".png", ".part"))] == []
    assert not target.exists()


def test_t14_night_mode(qtbot, win, tmp_path):
    start(qtbot, win)
    win.submit("ui.set_appearance", {"mode": "night"})
    wait_idle(qtbot, win)
    out = tmp_path / "night.png"
    entry = export(qtbot, win, out)
    assert entry.result.status == "ok"
    with Image.open(out) as picture:
        assert json.loads(picture.text["AstroTwo:View"])["night_mode"] is True


@pytest.mark.gl
def test_gl_png_has_physical_pixels(qtbot, tmp_path):
    """T14 sulla GPU: il PNG scritto dal disegno vero ha le dimensioni in pixel fisici (rapporto dei pixel dello
    schermo) e il colore dei pixel disegnati."""
    from astrotwo.ui.sky_renderer_gl import GlSkyRenderer

    renderer = GlSkyRenderer()
    qtbot.addWidget(renderer)
    renderer.resize(200, 100)
    renderer.show()
    qtbot.waitExposed(renderer)
    assert renderer.available
    ratio = renderer.devicePixelRatioF()
    w, h = round(200 * ratio), round(100 * ratio)
    plane = np.zeros((h, w, 4), dtype=np.uint8)
    plane[...] = (255, 0, 0, 255)
    renderer.upload_texture(plane)
    out = tmp_path / "gl.png"
    ev.write_png(renderer.render_offscreen(), out, {"Software": "test"}, "Credits: test")
    with Image.open(out) as picture:
        assert picture.size == (w, h) and picture.text["Software"] == "test"
        pixels = np.asarray(picture.convert("RGB"))
    assert tuple(pixels[h // 4, w // 4]) == (255, 0, 0)  # lontano dalla riga dei crediti
