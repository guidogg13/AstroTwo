"""Test del visualizzatore del cielo (41 §12), sprint 4a: sfondo HiPS, gesti → comandi, vista iniziale.

Piattaforma ``offscreen`` con il renderer in memoria (``tests/ui/fake_renderer.py``); il test ``gl`` usa la GPU.
"""

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QNativeGestureEvent, QPointingDevice, QWheelEvent
from PySide6.QtWidgets import QApplication

from astrotwo.core import hips
from astrotwo.core.commands import ResultMessage
from astrotwo.ui import sky_viewer as sv
from tests.core.test_hips import WIDTH, image_tile, properties_text, serve_properties
from tests.ui.test_main_window import fake_simbad, make_window, names, settings_path, wait_idle  # noqa: F401 - fixture


def serve_png_survey(service, *, order=3):
    """Survey PNG simulato con tutti i tile fino a ``order`` (tile di prova del 12: righe a sfumatura)."""
    url = serve_properties(service, "/png", properties_text(hips_tile_format="png", hips_order=str(order),
                                                            hips_tile_width=str(WIDTH)))
    payload, _ = image_tile("png")
    for k in range(order + 1):
        for index in range(12 * 4 ** k):
            service.routes[f"/png/{hips.tile_path(k, index, 'png')}"] = lambda request: (200, "image/png", payload)
    return url


@pytest.fixture
def viewer_window(qtbot, settings_path, cache, service, monkeypatch):  # noqa: F811
    # copertura dal solo servizio simulato (Moc.fits assente → copertura non nota), mai dal MocServer reale
    monkeypatch.setattr(hips, "survey_coverage", lambda svc, **k: hips.service_coverage(svc, **k))
    win = make_window(qtbot, settings_path, cache)
    win.survey_url = serve_png_survey(service)
    yield win
    win.close()


def wait_drawn(qtbot, win, before=None, timeout=20000):
    """Comandi finiti, campionamento della geometria corrente pronto (diverso da ``before``) e tile arrivati."""
    wait_idle(qtbot, win, timeout)
    qtbot.waitUntil(lambda: win.sky.sampling is not None and win.sky.sampling is not before
                    and win.sky._in_flight == 0, timeout=timeout)
    wait_idle(qtbot, win, timeout)


def start(qtbot, win):
    win.submit("hips.set_survey", {"survey": win.survey_url})
    win.sky.start_view()
    wait_drawn(qtbot, win)


def test_start_view_and_background(qtbot, viewer_window):
    """Vista iniziale (cielo intero) e T4: ogni pixel della finestra = pixel del tile che contiene il suo centro."""
    win = viewer_window
    start(qtbot, win)
    entries = win.session.history.entries
    assert names(win) == ["hips.set_survey", "view.set_zoom", "view.set_center"]
    window = win.sky.window_size()
    zoom, center = entries[1].command.parameters, entries[2].command.parameters
    assert zoom["window"] == window and center["window"] == window
    assert zoom["scale"]["value"] == pytest.approx(360.0 / window["width"]) and zoom["scale"]["unit"] == "deg"
    assert center["position"]["lon"]["value"] == 0.0 and center["position"]["frame"] == "icrs"
    view = win.session.workspace.state.view
    assert view.projection == "AIT" and win.sky.geometry is view.geometry
    sampling = win.sky.sampling
    assert sampling.shape == (window["height"], window["width"])
    # ricalcolo nel test con il 12: valore del pixel del tile per ogni pixel della finestra con dati
    service = win.sky.service
    expected = np.zeros(sampling.shape + (4,), dtype=np.uint8)
    for index in sampling.tiles:
        tile = hips.fetch_tile(service, sampling.order, index, cache=win.cache)
        mask = sampling.tile_of_pixel == index
        expected[mask, :3] = tile.data[sampling.tile_y[mask], sampling.tile_x[mask]][:, :3]
        expected[mask, 3] = 255
    assert np.array_equal(win.sky.canvas, expected)
    assert np.count_nonzero(sampling.tile_of_pixel >= 0) > 0.25 * sampling.tile_of_pixel.size  # ellisse AIT
    drawn = win.sky.renderer.texture
    assert np.array_equal(drawn, expected[::-1])  # riga 0 della finestra (sud) in basso sullo schermo
    assert win.sky.renderer.transform == (1.0, 0.0, 0.0)
    assert win.survey_label.text() == "Survey di prova · AIT · field 360.00°"


def test_format_field():
    assert sv.format_field({"value": 1.8234, "unit": "deg"}) == "1.82°"
    assert sv.format_field({"value": 0.5, "unit": "deg"}) == "30.00′"
    assert sv.format_field({"value": 12.0, "unit": "arcsec"}) == "12.00″"
    assert sv.format_field(None) == ""


def wheel(widget, steps, pos, pixel=0):
    event = QWheelEvent(QPointF(pos), QPointF(widget.mapToGlobal(pos)), QPoint(0, pixel), QPoint(0, int(120 * steps)),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)


def mouse(widget, kind, pos, button=Qt.MouseButton.LeftButton):
    buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
    event = QMouseEvent(kind, QPointF(pos), QPointF(widget.mapToGlobal(pos)), button, buttons,
                        Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, event)


def test_t5_wheel_zoom_to_commands(qtbot, viewer_window):
    """T5: nessun comando durante il gesto; a fine gesto ``view.set_zoom`` poi ``view.set_center``."""
    win = viewer_window
    start(qtbot, win)
    sky = win.sky
    before = win.session.workspace.state.view
    geometry = before.geometry
    drawn = sky.sampling
    center = QPoint(sky.width() // 2, sky.height() // 2)
    for _ in range(4 * sv.WHEEL_EVENTS_PER_NOTCH):
        wheel(sky, 1, center)  # 4 scatti (6 eventi ciascuno) = raddoppio (2^(1/4) per scatto)
    assert len(win.session.history) == 3 and not win.busy()  # gesto in corso: solo disegno
    assert sky.renderer.transform[0] == pytest.approx(2.0)
    qtbot.waitUntil(lambda: len(win.session.history) == 5, timeout=5000)
    wait_drawn(qtbot, win, drawn)
    zoom, moved = win.session.history.entries[3:]
    assert [zoom.command.name, moved.command.name] == ["view.set_zoom", "view.set_center"]
    assert zoom.command.requested_by.source == "mouse"
    assert zoom.command.parameters["scale"]["value"] == pytest.approx(before.scale.to_value("deg") / 2.0, rel=1e-12)
    # centro: il punto dello schermo al centro, riportato in pixel della finestra, dato da window_to_sky del 10
    r = sky.ratio()
    w, h = sky.window_size()["width"], sky.window_size()["height"]
    cx, cy = center.x() * r, center.y() * r
    k, tx, ty = 2.0, cx - 2.0 * cx, cy - 2.0 * cy  # zoom ×2 attorno al punto della rotella (solo disegno)
    qx, qy = (w / 2 - tx) / k, (h / 2 - ty) / k
    sky_center = geometry.window_to_sky(qx - 0.5, geometry.shape[0] - qy - 0.5)
    position = moved.command.parameters["position"]
    assert position["lon"]["value"] == pytest.approx(sky_center.spherical.lon.deg, abs=1e-9)
    assert position["lat"]["value"] == pytest.approx(sky_center.spherical.lat.deg, abs=1e-9)
    assert sky.renderer.transform == pytest.approx((1.0, 0.0, 0.0))  # nuova geometria: nessuna trasformazione


def test_t5_drag_to_center_and_limits(qtbot, viewer_window):
    win = viewer_window
    start(qtbot, win)
    sky = win.sky
    geometry = win.session.workspace.state.view.geometry
    drawn = sky.sampling
    a, b = QPoint(100, 150), QPoint(200, 150)
    mouse(sky, QEvent.Type.MouseButtonPress, a)
    mouse(sky, QEvent.Type.MouseMove, QPoint(150, 150))
    mouse(sky, QEvent.Type.MouseMove, b)
    mouse(sky, QEvent.Type.MouseButtonRelease, b)
    assert len(win.session.history) == 3
    qtbot.waitUntil(lambda: len(win.session.history) == 4, timeout=5000)
    wait_drawn(qtbot, win, drawn)
    entry = win.session.history.entries[3]
    assert entry.command.name == "view.set_center"  # solo spostamento: nessun view.set_zoom
    w, h = sky.window_size()["width"], sky.window_size()["height"]
    expected = geometry.window_to_sky(w / 2 - 100 * sky.ratio() - 0.5, geometry.shape[0] - h / 2 - 0.5)
    assert entry.command.parameters["position"]["lon"]["value"] == pytest.approx(expected.spherical.lon.deg,
                                                                                abs=1e-9)
    # limite della scala: dal cielo intero non si va oltre 360° sulla larghezza
    for _ in range(3 * sv.WHEEL_EVENTS_PER_NOTCH):
        wheel(sky, -1, QPoint(100, 150))
    assert sky.renderer.transform[0] == pytest.approx(1.0)


def test_trackpad_two_fingers_pan(qtbot, viewer_window):
    win = viewer_window
    start(qtbot, win)
    sky = win.sky
    event = QWheelEvent(QPointF(100, 100), QPointF(sky.mapToGlobal(QPoint(100, 100))), QPoint(30, -10),
                        QPoint(30, -10), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.ScrollUpdate, False)
    QApplication.sendEvent(sky, event)
    r = sky.ratio()
    assert sky.renderer.transform == pytest.approx((1.0, 30 * r, -10 * r))
    qtbot.waitUntil(lambda: len(win.session.history) == 4, timeout=5000)
    assert win.session.history.entries[3].command.name == "view.set_center"


def test_t12_stale_tiles_discarded(qtbot, viewer_window):
    """T12: un tile di una finestra superata non si disegna sulla nuova."""
    win = viewer_window
    start(qtbot, win)
    sky = win.sky
    canvas = sky.canvas.copy()
    old = sky.tiles.generation
    sky.tiles.generation += 1
    fake = hips.ViewTile(index=0, order=0, box=(0, 2, 0, 2), values=np.full((2, 2, 3), 7, dtype=np.uint8),
                         mask=np.ones((2, 2), dtype=bool), format="png", provenance="test", from_cache=True)
    sky._tile(old, fake)
    assert np.array_equal(sky.canvas, canvas)
    assert sky.tiles.current(old + 1) and not sky.tiles.current(old)


def test_tile_errors_one_message_per_survey(qtbot, viewer_window, service):
    win = viewer_window
    for path in [p for p in service.routes if p.startswith("/png/Norder")]:
        del service.routes[path]  # tutti i tile mancanti (HTTP 404)
    start(qtbot, win)
    codes = [code for _, code, _, _ in win.messages.messages]
    assert sum("HIPS_TILE_MISSING" in c for c in codes) == 1, codes
    assert not np.any(win.sky.canvas[..., 3])  # zone vuote


def test_night_mode_reaches_renderer(qtbot, viewer_window):
    win = viewer_window
    win.act_night.trigger()
    wait_idle(qtbot, win)
    assert win.sky.renderer.night is True
    win.act_night.trigger()
    wait_idle(qtbot, win)
    assert win.sky.renderer.night is False


def test_message_once():
    seen = []
    viewer = sv.SkyViewer.__new__(sv.SkyViewer)  # solo la regola del messaggio unico, senza widget
    viewer._reported, viewer.survey_layer = set(), "L1"
    viewer.message = type("S", (), {"emit": staticmethod(seen.append)})()
    for _ in range(3):
        sv.SkyViewer._report(viewer, "HIPS_BAD_TILE", "tile corrotto")
    assert seen == [ResultMessage("HIPS_BAD_TILE", "tile corrotto")]


@pytest.mark.gl
def test_gl_texture_orientation_transform_and_night(qtbot):
    """Disegno sulla GPU: riga 0 dell'immagine in alto, trasformazione del gesto, modalità notte senza verde/blu."""
    from astrotwo.ui.sky_renderer_gl import GlSkyRenderer

    renderer = GlSkyRenderer()
    qtbot.addWidget(renderer)
    renderer.resize(200, 100)
    renderer.show()
    qtbot.waitExposed(renderer)
    assert renderer.available
    r = renderer.devicePixelRatioF()
    w, h = round(200 * r), round(100 * r)
    image = np.zeros((h, w, 4), dtype=np.uint8)
    image[: h // 2] = (255, 0, 0, 255)  # metà alta rossa
    image[h // 2:] = (0, 0, 255, 255)  # metà bassa blu
    renderer.upload_texture(image)
    shot = renderer.render_offscreen()
    top, bottom = shot.pixelColor(w // 2, h // 4), shot.pixelColor(w // 2, 3 * h // 4)
    assert (top.red(), top.blue()) == (255, 0) and (bottom.red(), bottom.blue()) == (0, 255)
    renderer.set_transform(1.0, w / 2, 0.0)  # metà destra: immagine spostata di mezza larghezza
    shot = renderer.render_offscreen()
    assert shot.pixelColor(w // 4, h // 4).red() < 20 and shot.pixelColor(3 * w // 4, h // 4).red() == 255
    renderer.set_transform(1.0, 0.0, 0.0)
    renderer.set_night(True)
    shot = renderer.render_offscreen()
    pixels = [shot.pixelColor(x, y) for x in range(0, w, 7) for y in range(0, h, 7)]
    assert all(c.green() <= 8 and c.blue() <= 8 for c in pixels)
    assert shot.pixelColor(w // 2, 3 * h // 4).red() > 0  # il blu diventa rosso scuro (luminanza)


# --- 4a-fix: eventi arrivati come dal sistema (finestra → widget sotto il cursore), non dati al widget ----------


def via_window(win, kind, local, **kw):
    """Invia l'evento alla finestra (come fa macOS): Qt lo recapita al widget sotto il cursore."""
    sky = win.sky
    p = sky.mapTo(win, local)
    g = QPointF(win.mapToGlobal(p))
    if kind == "wheel":
        event = QWheelEvent(QPointF(p), g, kw.get("pixel", QPoint(0, 0)), QPoint(0, kw["angle"]),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase,
                            False)
    elif kind == "pinch":
        event = QNativeGestureEvent(Qt.NativeGestureType.ZoomNativeGesture, QPointingDevice.primaryPointingDevice(),
                                    2, QPointF(p), QPointF(p), g, kw["value"], QPointF())
    else:
        buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        event = QMouseEvent(kind, QPointF(p), g, Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier)
    assert win.childAt(p) is sky  # il cielo riceve l'evento: nessun widget sopra
    QApplication.sendEvent(win.windowHandle(), event)
    return event


def test_real_events_reach_sky(qtbot, viewer_window):
    """Rotella, pizzico e trascinamento arrivano al cielo passando dalla finestra; il pizzico è accettato."""
    win = viewer_window
    start(qtbot, win)
    sky = win.sky
    here = QPoint(sky.width() // 2, sky.height() // 2)
    per_event = sv.ZOOM_STEP ** (1 / sv.WHEEL_EVENTS_PER_NOTCH)
    via_window(win, "wheel", here, angle=120)
    assert sky.renderer.transform[0] == pytest.approx(per_event)
    via_window(win, "wheel", here, angle=120)
    via_window(win, "wheel", here, angle=-120)
    assert sky.renderer.transform[0] == pytest.approx(per_event)
    for _ in range(sv.WHEEL_EVENTS_PER_NOTCH - 1):
        via_window(win, "wheel", here, angle=120)
    assert sky.renderer.transform[0] == pytest.approx(sv.ZOOM_STEP)  # uno scatto fisico
    k = sky.k
    pinch = via_window(win, "pinch", here, value=0.25)
    assert pinch.isAccepted() and sky.k == pytest.approx(k * 1.25)
    tx = sky.tx
    for kind, offset in ((QEvent.Type.MouseButtonPress, 0), (QEvent.Type.MouseMove, 30),
                         (QEvent.Type.MouseButtonRelease, 30)):
        via_window(win, kind, here + QPoint(offset, 0))
    assert sky.tx == pytest.approx(tx + 30 * sky.ratio())
    assert sky.renderer.transform[1] == pytest.approx(sky.tx)
    qtbot.waitUntil(lambda: len(win.session.history) >= 5 and not win.busy(), timeout=8000)
    assert [e.command.name for e in win.session.history.entries[3:5]] == ["view.set_zoom", "view.set_center"]


def test_go_to_moves_view_and_survives_stale_gesture(qtbot, viewer_window, fake_simbad):  # noqa: F811
    """"Vai a" sposta il cielo; un gesto o un ridimensionamento ancora da registrare non lo sposta altrove."""
    win = viewer_window
    start(qtbot, win)
    sky = win.sky
    sky.pan_by(40, 25)  # spostamento in sospeso (come un ridimensionamento dei pannelli) prima di "Vai a"
    win.go_to_field.setText("M31")
    qtbot.keyClick(win.go_to_field, Qt.Key.Key_Return)
    wait_idle(qtbot, win)
    qtbot.wait(sv.GESTURE_IDLE_MS + 600)
    wait_idle(qtbot, win)
    assert "view.set_center" not in names(win)[4:]  # nessun comando del gesto scartato dopo il go_to
    center = win.session.workspace.state.view.center.coord
    assert center.ra.deg == pytest.approx(10.6847, abs=1e-3) and center.dec.deg == pytest.approx(41.2688, abs=1e-3)
    assert sky.renderer.transform == pytest.approx((1.0, 0.0, 0.0))


def test_go_to_error_is_visible(qtbot, viewer_window, fake_simbad):  # noqa: F811
    win = viewer_window
    start(qtbot, win)
    win.go_to("oggetto-che-non-esiste")
    wait_idle(qtbot, win)
    assert win.session.history.entries[-1].result.status == "error"
    assert win.status.currentMessage().startswith(win.session.history.entries[-1].result.error.code)


def test_zoom_buttons_and_shortcuts(qtbot, viewer_window):
    """Pulsanti + e − e voci ⌘+ / ⌘−: zoom ×2 e ÷2 come un gesto, poi i comandi registrati."""
    win = viewer_window
    start(qtbot, win)
    sky = win.sky
    assert sky.zoom_in_button.isVisible() and sky.zoom_out_button.isVisible()
    assert sky.zoom_in_button.geometry().right() < sky.width() and sky.zoom_in_button.y() >= 0
    assert win.childAt(sky.mapTo(win, sky.zoom_in_button.geometry().center())) is sky.zoom_in_button
    scale = win.session.workspace.state.view.scale
    qtbot.mouseClick(sky.zoom_in_button, Qt.MouseButton.LeftButton)
    assert sky.renderer.transform[0] == pytest.approx(2.0)
    qtbot.mouseClick(sky.zoom_out_button, Qt.MouseButton.LeftButton)
    assert sky.renderer.transform[0] == pytest.approx(1.0)
    win.act_zoom_in.trigger()
    win.act_zoom_in.trigger()
    assert sky.renderer.transform[0] == pytest.approx(4.0)
    assert win.act_zoom_in.shortcut().toString() and win.act_zoom_out.shortcut().toString()
    qtbot.waitUntil(lambda: len(win.session.history) == 5, timeout=8000)
    zoom = win.session.history.entries[3]
    assert zoom.command.name == "view.set_zoom"
    assert zoom.command.parameters["scale"]["value"] == pytest.approx(scale.to_value("deg") / 4.0, rel=1e-12)


def test_go_to_zooms_to_about_one_degree(qtbot, viewer_window, fake_simbad):  # noqa: F811
    win = viewer_window
    start(qtbot, win)
    win.go_to("M31")
    wait_idle(qtbot, win)
    qtbot.waitUntil(lambda: names(win)[-1] == "view.set_zoom", timeout=8000)
    wait_idle(qtbot, win)
    last = win.session.history.entries[-1]
    assert last.command.requested_by.source == "keyboard"
    field = last.result.values["field_of_view"]
    assert field["unit"] == "deg" and 0.5 < field["value"] < 2.0
    center = win.session.workspace.state.view.center.coord
    assert center.ra.deg == pytest.approx(10.6847, abs=1e-3)
    before = len(win.session.history)
    win.go_to("10.68 41.27")  # già a circa 1°: resta com'è
    wait_idle(qtbot, win)
    qtbot.wait(300)
    assert names(win)[before:] == ["view.go_to"], names(win)


def test_debug_input_log_off_by_default(qtbot, viewer_window, capfd, monkeypatch):
    """Il log diagnostico degli ingressi (ASTROTWO_DEBUG_INPUT) è spento di default e acceso con "1"."""
    win = viewer_window
    start(qtbot, win)
    sky = win.sky
    center = QPoint(sky.width() // 2, sky.height() // 2)
    monkeypatch.delenv("ASTROTWO_DEBUG_INPUT", raising=False)
    wheel(sky, 1, center)
    assert "astrotwo-input" not in capfd.readouterr().err
    monkeypatch.setenv("ASTROTWO_DEBUG_INPUT", "1")
    wheel(sky, 1, center)
    err = capfd.readouterr().err
    assert "wheelEvent angleDelta=(0,120)" in err and "zoom_by" in err and "accettato=True" in err


# Valori reali del Mac del proprietario (~/rotella.log del 2026-10-17): mouse a rotellina, NoScrollPhase,
# angleDelta = ±120 e pixelDelta non nullo e irregolare (accelerazione di macOS), 34 eventi per 6 scatti.
REAL_PIXEL_DELTAS = [2, 245, 287, 680, 385, 403, 425, 2, 248, 612, 739, 2, 41, 210, 288, 325, 1147, 424]  # 3 scatti


def test_real_mouse_wheel_values_zoom_not_pan(qtbot, viewer_window):
    """Con pixelDelta non nullo e NoScrollPhase è rotella di mouse: zoom, mai spostamento; 18 eventi = 3 scatti."""
    win = viewer_window
    start(qtbot, win)
    sky = win.sky
    here = QPoint(sky.width() // 2, sky.height() // 2)
    for pixel in REAL_PIXEL_DELTAS:
        via_window(win, "wheel", here, angle=120, pixel=QPoint(0, pixel))
    assert sky.renderer.transform[0] == pytest.approx(sv.ZOOM_STEP ** 3, rel=1e-9)
    assert sky._moved is False
    for pixel in REAL_PIXEL_DELTAS:  # e indietro con gli stessi valori di segno opposto
        via_window(win, "wheel", here, angle=-120, pixel=QPoint(0, -pixel))
    assert sky.renderer.transform[0] == pytest.approx(1.0, rel=1e-9)
    assert sky._moved is False


def phased_wheel(win, here, phase, pixel):
    sky = win.sky
    p = sky.mapTo(win, here)
    event = QWheelEvent(QPointF(p), QPointF(win.mapToGlobal(p)), QPoint(0, pixel), QPoint(0, pixel * 3 // 2),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, phase, False)
    QApplication.sendEvent(win.windowHandle(), event)


def test_trackpad_phased_scroll_pans_without_zoom(qtbot, viewer_window):
    """Sequenza di trackpad (Begin, Update, End, Momentum) con pixelDelta: solo spostamento, nessuno zoom."""
    win = viewer_window
    start(qtbot, win)
    sky = win.sky
    here = QPoint(sky.width() // 2, sky.height() // 2)
    ty = sky.ty
    for phase, pixel in ((Qt.ScrollPhase.ScrollBegin, 4), (Qt.ScrollPhase.ScrollUpdate, 10),
                         (Qt.ScrollPhase.ScrollUpdate, 6), (Qt.ScrollPhase.ScrollEnd, 0),
                         (Qt.ScrollPhase.ScrollMomentum, 2)):
        phased_wheel(win, here, phase, pixel)
    assert sky.ty == pytest.approx(ty + 22 * sky.ratio())
    assert sky.k == pytest.approx(1.0) and sky._zoomed is False
