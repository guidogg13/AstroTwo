# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del visualizzatore del cielo (41 §12), sprint 4g: misura della distanza (T36) e puntatore Simbad (T37).

Piattaforma ``offscreen`` con il renderer in memoria; valori attesi ricalcolati nel test con i moduli 10, 11 e 17;
Simbad è un servizio simulato (nessuna rete).
"""

import threading
from types import SimpleNamespace

import astropy.units as u
import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from astrotwo.core import coordinates_wcs as cw
from astrotwo.core import vo_protocols as vo
from astrotwo.core.images_fits import load_image, star_centroid
from astrotwo.core.measures import angular_distance
from astrotwo.ui import sky_tools
from astrotwo.ui.sky_tools import distance_text, simbad_url
from tests.core.test_commands_image_base import header, write
from tests.ui.test_catalog_sky import wait_settled
from tests.ui.test_main_window import make_window, settings_path, wait_idle  # noqa: F401 - fixture


@pytest.fixture
def win(qtbot, settings_path, cache):
    win = make_window(qtbot, settings_path, cache)
    win.seen = []
    win.sky.message.connect(win.seen.append)
    win.sky.start_view()
    wait_settled(qtbot, win)
    yield win
    win.close()


def send(win, kind, at, buttons=Qt.MouseButton.LeftButton):
    pos = QPointF(at)
    button = Qt.MouseButton.LeftButton if kind != QEvent.Type.MouseMove else Qt.MouseButton.NoButton
    held = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else buttons
    event = QMouseEvent(kind, pos, QPointF(win.sky.mapToGlobal(at)), button, held, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(win.sky, event)


def drag(win, a, b):
    send(win, QEvent.Type.MouseButtonPress, a)
    for step in range(1, 6):
        send(win, QEvent.Type.MouseMove, a + (b - a) * step / 5)
    send(win, QEvent.Type.MouseButtonRelease, b)


def click(win, at):
    send(win, QEvent.Type.MouseButtonPress, at)
    send(win, QEvent.Type.MouseButtonRelease, at)


def history(win):
    return win.session.history.entries


def command(qtbot, win, name, since):
    """Il comando ``name`` registrato dopo le prime ``since`` voci, cercato per nome (la vista manda da sola un
    ``view.set_center`` dopo un cambio di layout)."""
    found = []
    qtbot.waitUntil(lambda: found.__setitem__(slice(None), [e for e in history(win)[since:]
                                                            if e.command.name == name]) or bool(found), timeout=30000)
    wait_settled(qtbot, win)
    return found[0]


def set_tool(qtbot, win, tool):
    win.submit("ui.set_tool", {"tool": tool})
    wait_settled(qtbot, win)
    assert win.sky.tool == tool


def window_pixel(win, x, y):
    """Pixel logici dello schermo che cadono sul pixel ``(x, y)`` (numpy) della base."""
    g = win.sky.geometry
    wx, wy = g.base_to_window(x, y)
    r = win.sky.ratio()
    return QPoint(round((float(wx) + 0.5) / r), round((g.shape[0] - float(wy) - 0.5) / r))


def open_image(qtbot, win, tmp_path, data=None, hdr=None):
    path = write(tmp_path / "img.fits", header() if hdr is None else hdr, data)
    win.open_path = lambda name: path
    win.act_open_image.trigger()
    wait_idle(qtbot, win)
    qtbot.waitUntil(lambda: win.sky.image_key is not None, timeout=10000)
    wait_settled(qtbot, win)
    return path


def sky_of(position):
    return cw.SkyFrame.from_lonlat(position["lon"]["value"] * u.Unit(position["lon"]["unit"]),
                                   position["lat"]["value"] * u.Unit(position["lat"]["unit"]), position["frame"])


# =============================================================================
# T36 — distanza


def test_t36_distance_on_image_base(qtbot, win, tmp_path):
    path = open_image(qtbot, win, tmp_path)
    image = load_image(path)
    set_tool(qtbot, win, "distance")
    assert win.sky.options_bar.isVisible() and win.sky.options_bar.snap.isEnabled()
    before = win.session.workspace.state.view
    since = len(history(win))
    a, b = window_pixel(win, 10, 10), window_pixel(win, 50, 30)
    drag(win, a, b)
    entry = command(qtbot, win, "measure.distance", since)
    params = entry.command.parameters
    assert entry.result.status == "ok" and entry.command.requested_by.source == "mouse"
    assert params["layer"] == "L1" and params["unit"] == "arcmin" and params["snap"] is False
    assert abs(params["p1"]["x"] - 10) < 1.5 and abs(params["p2"]["y"] - 30) < 1.5  # pixel della base = immagine
    # distanza ricalcolata con il 10 e il 17 sugli stessi pixel
    p1 = cw.pixel_to_sky(image.wcs, params["p1"]["x"], params["p1"]["y"], convention="numpy").coords
    p2 = cw.pixel_to_sky(image.wcs, params["p2"]["x"], params["p2"]["y"], convention="numpy").coords
    expected = angular_distance(p1, p2, "arcmin").value
    assert entry.result.values["distance"] == {"value": float(expected.value), "unit": "arcmin"}
    # il trascinamento ha misurato, non spostato la vista
    assert not [e for e in history(win)[since:] if e.command.name == "view.set_center"
                and e.command.requested_by.source == "mouse" and e.command.parameters["position"] != before.center]
    assert win.session.workspace.state.view.center == before.center
    # segmento ed etichetta: valore con 4 cifre significative e simbolo dell'unità, dal livello
    layer = win.session.workspace.state.layer(entry.result.layers_created[0])
    assert layer.kind == "measure"
    segments = win.sky.measure_overlay.segments()
    assert len(segments) == 1 and segments[0][2] == distance_text(expected)
    assert segments[0][2].endswith("′") and len(segments[0][2].rstrip("′").replace(".", "")) <= 4 + 1
    # due clic invece del trascinamento; l'unità dalle opzioni (prefs.set registrato)
    win.sky.options_bar.unit.setCurrentIndex(win.sky.options_bar.unit.findData("arcsec"))
    wait_settled(qtbot, win)
    assert history(win)[-1].command.name == "prefs.set"
    assert history(win)[-1].command.parameters == {"key": "tools/distance_unit", "value": "arcsec"}
    since = len(history(win))
    click(win, window_pixel(win, 5, 5))
    assert win.sky.distance_tool.first is not None and win.sky.measure_overlay.preview is not None
    click(win, window_pixel(win, 20, 5))
    second = command(qtbot, win, "measure.distance", since)
    assert second.command.parameters["unit"] == "arcsec" and second.result.values["distance"]["unit"] == "arcsec"
    assert win.sky.distance_tool.first is None
    # Esc toglie il primo punto
    click(win, window_pixel(win, 5, 5))
    win.sky.keyPressEvent(SimpleNamespace(key=lambda: Qt.Key.Key_Escape, accept=lambda: None))
    assert win.sky.distance_tool.first is None and win.sky.measure_overlay.preview is None


STARS_NX, STARS_NY = 200, 160
STARS = ((70.3, 60.6), (130.7, 90.2))


def stars_image():
    """Due stelle gaussiane sintetiche su fondo piatto, centri noti; abbastanza grande per la corona di 22,5 pixel."""
    yy, xx = np.mgrid[0:STARS_NY, 0:STARS_NX]
    data = np.full((STARS_NY, STARS_NX), 100.0, dtype=np.float32)
    for cx, cy in STARS:
        data += (1000.0 * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * 1.5 ** 2))).astype(np.float32)
    return data


def stars_header():
    from astropy.wcs import WCS

    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [150.0, 2.0]
    w.wcs.crpix = [STARS_NX / 2 + 0.5, STARS_NY / 2 + 0.5]
    w.wcs.cdelt = [-1e-3, 1e-3]
    return w.to_header()


def test_t36_distance_snaps_to_centroid(qtbot, win, tmp_path):
    path = open_image(qtbot, win, tmp_path, stars_image(), stars_header())
    image = load_image(path)
    set_tool(qtbot, win, "distance")
    win.sky.options_bar.snap.setChecked(True)
    wait_settled(qtbot, win)
    assert [(e.command.parameters["key"], e.command.parameters["value"]) for e in history(win)
            if e.command.name == "prefs.set"][-1] == ("tools/distance_snap", "true")
    since = len(history(win))
    drag(win, window_pixel(win, 71, 61), window_pixel(win, 130, 91))
    entry = command(qtbot, win, "measure.distance", since)
    params = entry.command.parameters
    assert params["snap"] is True and params["box_size"] == 15
    assert entry.result.status == "ok", entry.result.error
    centroids = entry.result.values["centroids"]
    for name, c in zip(("p1", "p2"), centroids, strict=True):
        expected = star_centroid(image, (params[name]["x"], params[name]["y"]), 15)
        assert (c["x"], c["y"]) == (float(expected.x), float(expected.y))
        assert c["annulus_inner"] == 15.0 and c["annulus_outer"] == 22.5  # corona di default dell'11, dichiarata
    assert abs(centroids[0]["x"] - STARS[0][0]) < 0.5 and abs(centroids[1]["y"] - STARS[1][1]) < 0.5


def test_t36_distance_on_hips_only_uses_sky_form(qtbot, win):
    assert win.sky.base_image is None
    set_tool(qtbot, win, "distance")
    assert not win.sky.options_bar.snap.isEnabled() and not win.sky.options_bar.snap.isChecked()
    w, h = win.sky.width(), win.sky.height()
    a, b = QPoint(w // 3, h // 2), QPoint(w // 2, h // 2)
    since = len(history(win))
    drag(win, a, b)
    entry = command(qtbot, win, "measure.distance", since)
    params = entry.command.parameters
    assert entry.result.status == "ok" and "layer" not in {k for k, v in params.items() if v is not None}
    g = win.session.workspace.state.view.geometry
    ra = win.sky.window_position(QPointF(a))
    expected_a = g.window_to_sky(ra["x"], ra["y"])
    assert params["sky1"]["lon"]["value"] == pytest.approx(float(expected_a.spherical.lon.deg), abs=1e-9)
    expected = angular_distance(sky_of(params["sky1"]), sky_of(params["sky2"]), "arcmin").value
    assert entry.result.values["distance"] == {"value": float(expected.value), "unit": "arcmin"}
    assert len(win.sky.measure_overlay.segments()) == 1


def test_t36_distance_outside_the_sky_sends_nothing(qtbot, win):
    set_tool(qtbot, win, "distance")
    since = len(history(win))
    drag(win, QPoint(5, 5), QPoint(30, 30))  # angolo fuori dall'ellisse dell'AIT
    wait_settled(qtbot, win)
    assert [e for e in history(win)[since:] if e.command.name == "measure.distance"] == []
    assert [m.code for m in win.seen] == ["OUT_OF_SKY"]


def test_t36_options_bar_and_night(qtbot, win, tmp_path):
    set_tool(qtbot, win, "none")
    assert not win.sky.options_bar.isVisible()
    set_tool(qtbot, win, "distance")
    assert win.sky.options_bar.isVisible()
    w, h = win.sky.width(), win.sky.height()
    since = len(history(win))
    drag(win, QPoint(w // 3, h // 2), QPoint(w // 2, h // 2))
    command(qtbot, win, "measure.distance", since)
    shot = win.sky.measure_overlay.grab().toImage()
    pixels = [shot.pixelColor(x, y) for x in range(0, shot.width(), 2) for y in range(0, shot.height(), 2)]
    drawn = [c for c in pixels if c.alpha() > 0]
    assert any(c.red() > 200 and c.green() > 200 and c.blue() < 120 for c in drawn)  # giallo di giorno
    win.act_night.trigger()
    wait_settled(qtbot, win)
    shot = win.sky.measure_overlay.grab().toImage()
    drawn = [c for c in (shot.pixelColor(x, y) for x in range(0, shot.width(), 2) for y in range(0, shot.height(), 2))
             if c.alpha() > 0]
    assert drawn and all(c.green() <= 40 and c.blue() <= 40 for c in drawn)  # di notte solo rossi
    assert any(c.red() > 120 for c in drawn)
    # tolto lo strumento, la vista si sposta di nuovo col trascinamento
    set_tool(qtbot, win, "none")
    assert not win.sky.options_bar.isVisible()


def test_t36_distance_available_to_the_assistant(win):
    from astrotwo.ai.tool_registry import EXPOSED_COMMANDS

    exposed = {command for command, _tool in EXPOSED_COMMANDS}
    assert "measure.distance" in exposed and "simbad.pointer" not in exposed  # 32 §3.2: le letture passive no


# =============================================================================
# T37 — puntatore Simbad


def fake_object(main_id="* alf Tau", nbref=1500):
    magnitudes = tuple(vo.SimbadMagnitude(band, None, value, 0.01, "mag", "Vega", None, None)
                       for band, value in (("B", 2.25), ("V", 0.86)))
    coords = cw.SkyFrame.from_lonlat(68.98 * u.deg, 16.51 * u.deg, "icrs")
    return vo.SimbadObject(main_id, "LP*", coords, nbref, 3.2 * u.arcsec, magnitudes)


@pytest.fixture
def simbad(monkeypatch):
    """Servizio Simbad simulato: registra le chiamate; ``gate`` ferma la risposta finché il test non la libera."""
    state = SimpleNamespace(calls=[], result=lambda: fake_object(), gate=threading.Event(), block=False, error=None)
    state.gate.set()

    def pointer(center, radius, *, cache=None, refresh=False, timeouts=None):
        state.calls.append((center, radius))
        if state.block:
            assert state.gate.wait(30)
        if state.error is not None:
            raise state.error
        found = state.result()
        request = SimpleNamespace(url="https://simbad.cds.unistra.fr/simbad/sim-tap", retrieved_at=None, from_cache=False)
        return vo.SimbadPointer(found, 0 if found is None else 1, "SIMBAD", request)

    monkeypatch.setattr(vo, "simbad_pointer", pointer)
    return state


def expected_radius(win, at):
    """12 pixel logici in angolo, ricalcolati nel test con il 10 e il 17."""
    sky = win.sky
    p = sky.window_position(QPointF(at))
    step = 12.0 * sky.ratio() / sky.k
    c = sky.geometry.window_to_sky([p["x"], p["x"] + step], [p["y"], p["y"]])
    return angular_distance(cw.SkyFrame(coord=c[0]), cw.SkyFrame(coord=c[1]), "arcsec").value


def test_t37_simbad_pointer_after_stop(qtbot, win, simbad):
    set_tool(qtbot, win, "simbad_pointer")
    at = QPoint(win.sky.width() // 2, win.sky.height() // 2)
    send(win, QEvent.Type.MouseMove, at)
    assert win.sky.simbad_tool.timer.isActive() and win.sky.simbad_tool.timer.interval() == 500
    assert simbad.calls == []  # non prima dell'arresto
    qtbot.waitUntil(lambda: win.sky.simbad_tool.card.isVisible(), timeout=10000)
    assert len(simbad.calls) == 1
    center, radius = simbad.calls[0]
    expected = expected_radius(win, at)
    assert radius.to_value(u.arcsec) == pytest.approx(float(expected.value), rel=1e-9)
    # il riquadro porta i campi del 14, la fonte e il collegamento
    text = win.sky.simbad_tool.card.text()
    assert "* alf Tau" in text and "LP*" in text and "1500 citations" in text
    assert "B 2.250 ± 0.010 (Vega)" in text and "V 0.860 ± 0.010 (Vega)" in text
    assert simbad_url("* alf Tau") in text.replace("&amp;", "&") or "sim-id?Ident=" in text
    assert "ICRS" in text and "source" in text.lower()
    # un movimento oltre la tolleranza chiude il riquadro
    send(win, QEvent.Type.MouseMove, at + QPoint(40, 0))
    assert not win.sky.simbad_tool.card.isVisible()


def test_t37_click_asks_at_once_and_opens_only_simbad_links(qtbot, win, simbad, monkeypatch):
    set_tool(qtbot, win, "simbad_pointer")
    at = QPoint(win.sky.width() // 3, win.sky.height() // 2)
    click(win, at)
    assert not win.sky.simbad_tool.timer.isActive()  # il clic non aspetta i 500 ms
    qtbot.waitUntil(lambda: win.sky.simbad_tool.card.isVisible(), timeout=10000)
    opened = []
    monkeypatch.setattr(sky_tools.QDesktopServices, "openUrl", lambda url: opened.append(bytes(url.toEncoded()).decode()))
    win.sky.simbad_tool.card.linkActivated.emit(simbad_url("* alf Tau"))
    win.sky.simbad_tool.card.linkActivated.emit("https://example.org/")
    win.sky.simbad_tool.card.linkActivated.emit("file:///etc/passwd")
    assert opened == [simbad_url("* alf Tau")]
    # Esc chiude il riquadro
    win.sky.keyPressEvent(SimpleNamespace(key=lambda: Qt.Key.Key_Escape, accept=lambda: None))
    assert not win.sky.simbad_tool.card.isVisible()
    # strumento spento: nessun riquadro
    click(win, at)
    qtbot.waitUntil(lambda: win.sky.simbad_tool.card.isVisible(), timeout=10000)
    set_tool(qtbot, win, "none")
    assert not win.sky.simbad_tool.card.isVisible()


def test_t37_one_request_at_a_time_last_stop_wins(qtbot, win, simbad):
    set_tool(qtbot, win, "simbad_pointer")
    simbad.block, simbad.gate = True, threading.Event()
    w, h = win.sky.width(), win.sky.height()
    a, b, c = QPoint(w // 4, h // 2), QPoint(w // 2, h // 2), QPoint(3 * w // 4, h // 2)
    click(win, a)
    qtbot.waitUntil(lambda: len(simbad.calls) == 1, timeout=10000)
    click(win, b)
    click(win, c)  # arrivano durante la richiesta: vale solo l'ultimo
    assert len(simbad.calls) == 1 and win.sky.simbad_tool.waiting == QPointF(c)
    simbad.block = False
    simbad.gate.set()
    qtbot.waitUntil(lambda: len(simbad.calls) == 2 and win.sky.simbad_tool.card.isVisible(), timeout=10000)
    assert len(simbad.calls) == 2  # mai B
    assert simbad.calls[1][1].to_value(u.arcsec) == pytest.approx(float(expected_radius(win, c).value), rel=1e-9)
    assert win.sky.simbad_tool.last_request["position"] == win.sky.window_position(QPointF(c))


def test_t37_no_object_and_errors(qtbot, win, simbad):
    set_tool(qtbot, win, "simbad_pointer")
    at = QPoint(win.sky.width() // 2, win.sky.height() // 2)
    simbad.result = lambda: None
    click(win, at)
    qtbot.waitUntil(lambda: win.sky.simbad_tool.card.isVisible(), timeout=10000)
    assert "No SIMBAD object within" in win.sky.simbad_tool.card.text()
    win.sky.simbad_tool.hide()
    simbad.error = vo.VoProtocolsError(
        "NET_TIMEOUT", "SIMBAD non raggiungibile",
        params={"reason": "url", "url": "SIMBAD", "connect": {"value": 10.0, "unit": "s"},
                "read": {"value": 60.0, "unit": "s"}, "detail": "giù"})
    click(win, at)
    qtbot.waitUntil(lambda: win.sky.simbad_tool.card.isVisible(), timeout=10000)
    assert "⚠" in win.sky.simbad_tool.card.text() and "NET_TIMEOUT" in win.sky.simbad_tool.card.text()
    # fuori dal cielo: nessuna richiesta, messaggio
    win.sky.simbad_tool.hide()
    calls = len(simbad.calls)
    click(win, QPoint(5, 5))
    assert len(simbad.calls) == calls and win.seen[-1].code == "OUT_OF_SKY"


def test_t37_card_in_night_mode(qtbot, win, simbad):
    set_tool(qtbot, win, "simbad_pointer")
    win.act_night.trigger()
    wait_settled(qtbot, win)
    click(win, QPoint(win.sky.width() // 2, win.sky.height() // 2))
    qtbot.waitUntil(lambda: win.sky.simbad_tool.card.isVisible(), timeout=10000)
    assert "#ff2020" in win.sky.simbad_tool.card.styleSheet()
