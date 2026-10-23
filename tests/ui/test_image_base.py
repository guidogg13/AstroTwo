# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del visualizzatore del cielo (41 §12), sprint 4d: immagine FITS locale come base della vista (File → Apri),
colori di ``set_display`` dell'11, coordinate e valore originale sotto il mouse con unità e pixel (x, y), immagine
senza WCS valido come griglia di pixel (``WCS_INVALID``).

Piattaforma ``offscreen`` con il renderer in memoria. Valori attesi ricalcolati con i moduli 10, 11 e 17.
"""

import numpy as np
import pytest
from astropy.time import Time
from PySide6.QtCore import QEvent, QPoint

from astrotwo.core import coordinates_wcs as cw
from astrotwo.core.images_fits import load_image, set_display
from tests.core.test_commands_image_base import NX, NY, header, write
from tests.ui.test_main_window import fake_simbad, make_window, names, settings_path, wait_idle  # noqa: F401 - fixture
from tests.ui.test_sky_viewer import hover, mouse, shown_text, wheel


@pytest.fixture
def win(qtbot, settings_path, cache):
    win = make_window(qtbot, settings_path, cache)
    win.sky.start_view()
    wait_idle(qtbot, win)
    yield win
    win.close()


def open_through_menu(qtbot, win, path):
    win.open_path = lambda name: path
    win.act_open_image.trigger()
    wait_idle(qtbot, win)
    qtbot.waitUntil(lambda: win.sky.image_key is not None or bool(win.modals), timeout=10000)


def window_pixel(win, x, y):
    """Pixel logici dello schermo che cadono sul pixel ``(x, y)`` (numpy) della base."""
    g = win.sky.geometry
    wx, wy = g.base_to_window(x, y)
    r = win.sky.ratio()
    return QPoint(round((float(wx) + 0.5) / r), round((g.shape[0] - float(wy) - 0.5) / r))


def test_t22_open_fits_becomes_base_with_set_display_colors(qtbot, win, tmp_path):
    data = np.random.default_rng(3).normal(100, 5, (NY, NX)).astype(np.float32)
    path = write(tmp_path / "img.fits", header(), data)
    open_through_menu(qtbot, win, path)
    assert "image.open" in names(win)
    state = win.session.workspace.state
    layer = state.of_kind("image")[0]
    assert state.view.base_layer == layer.id and win.sky.geometry is state.view.geometry
    # i colori sono quelli di set_display dell'11 con i limiti registrati nel comando (D41-3)
    params = win.session.history.entries[-1].command.parameters
    plane = set_display(load_image(path), params["vmin"], params["vmax"], 1.0, "gray", "linear")
    texture = win.sky.renderer.texture[::-1]  # riga 0 = sud
    g = win.sky.geometry
    assert texture.shape[:2] == g.shape
    for bx, by in ((0, 0), (30, 20), (59, 39), (10, 35)):
        wx, wy = (int(round(float(v))) for v in g.base_to_window(bx, by))
        assert np.array_equal(texture[wy, wx], plane.rgba[by, bx])
    # tutta l'immagine nella finestra: i bordi del disegno sono quelli dell'immagine
    assert texture[g.shape[0] // 2, 0, 3] == 255 and texture[g.shape[0] // 2, g.shape[1] - 1, 3] == 255
    # cambio di visualizzazione: stessi dati, altri colori
    win.submit("image.set_display", {"layer": layer.id, "vmin": float(params["vmin"]) - 5, "vmax": float(params["vmax"]),
                                     "stretch": "sqrt", "palette": "viridis", "gamma": 1.0})
    wait_idle(qtbot, win)
    changed = win.sky.renderer.texture[::-1]
    assert not np.array_equal(changed, texture)


def test_t23_cursor_value_unit_pixel_and_header_frame(qtbot, win, tmp_path):
    data = np.arange(NX * NY, dtype=np.float32).reshape(NY, NX) * 2.5
    path = write(tmp_path / "img.fits", header(**{"RADESYS": "ICRS", "MJD-OBS": 55000.0}), data)
    open_through_menu(qtbot, win, path)
    wcs = win.session.workspace.state.of_kind("image")[0].data.wcs
    history = len(win.session.history)
    for bx, by in ((12, 7), (50, 30)):
        at = window_pixel(win, bx, by)
        result = hover(qtbot, win, at.x(), at.y())
        pixel = result.values["pixel"]
        assert pixel["value"] == float(data[by, bx]) and pixel["fits"] == {"x": bx + 1, "y": by + 1}
        base = result.values["base_pixel"]  # posizione esatta del mouse nella base: cielo ricalcolato con il 10
        assert round(base["x"]) == bx and round(base["y"]) == by
        sky = cw.pixel_to_sky(wcs, base["x"], base["y"], convention="numpy").coords
        text = shown_text(win.status)
        frame = cw.SkyFrame(coord=sky.coord)
        lon, lat = (cw.format_coordinates(frame, style="sexagesimal").lon[0],
                    cw.format_coordinates(frame, style="sexagesimal").lat[0])
        # epoca dall'intestazione (MJD-OBS) in ISO 8601 con la scala, mai il JD (T29, DC1); attesa ricalcolata con astropy
        iso = Time(55000.0, format="mjd", scale="utc").isot.removesuffix(".000")
        assert iso == "2009-06-18T00:00:00"
        assert text.startswith(f"ICRS {lon} {lat} (epoch {iso} UTC)") and "JD" not in text
        assert f"{float(data[by, bx]):.6g} MJy / sr" in text and f"FITS ({bx + 1}, {by + 1})" in text
    assert len(win.session.history) == history  # lettura passiva: mai in cronologia


def test_t23_epoch_never_assumed_when_header_has_none(qtbot, win, tmp_path):
    path = write(tmp_path / "img.fits", header(bunit=None))
    open_through_menu(qtbot, win, path)
    p = window_pixel(win, 30, 20)
    hover(qtbot, win, p.x(), p.y())
    text = shown_text(win.status)
    assert "(epoch unknown)" in text and "(unit not declared)" in text


def test_t24_no_wcs_pixel_grid_wcs_invalid_and_no_gestures(qtbot, win, tmp_path):
    data = np.arange(NX * NY, dtype=np.float32).reshape(NY, NX)
    path = write(tmp_path / "plain.fits", None, data)
    open_through_menu(qtbot, win, path)
    assert win.sky.pixel_grid and win.sky.image_key is not None
    p = window_pixel(win, 20, 10)
    result = hover(qtbot, win, p.x(), p.y())
    assert result.values["sky"] is None and result.values["wcs_problem"]["code"] == "WCS_INVALID"
    text = shown_text(win.status)
    assert text.startswith("WCS_INVALID") and f"{float(data[10, 20]):.6g}" in text and "FITS (21, 11)" in text
    assert "ICRS" not in text  # nessuna coordinata inventata
    history = len(win.session.history)
    wheel(win.sky, 4, QPoint(win.sky.width() // 2, win.sky.height() // 2))
    mouse(win.sky, QEvent.Type.MouseButtonPress, QPoint(100, 100))
    qtbot.wait(50)
    mouse(win.sky, QEvent.Type.MouseButtonRelease, QPoint(160, 140))
    qtbot.wait(600)
    assert len(win.session.history) == history and win.sky.renderer.transform == (1.0, 0.0, 0.0)


def test_t25_zoom_on_the_image_keeps_it_drawn(qtbot, win, tmp_path):
    path = write(tmp_path / "img.fits", header(), np.random.default_rng(5).normal(10, 1, (NY, NX)).astype(np.float32))
    open_through_menu(qtbot, win, path)
    before = len(win.session.history)
    factor = win.sky.geometry.factor
    for _ in range(4 * 6):
        wheel(win.sky, 1, QPoint(win.sky.width() // 2, win.sky.height() // 2))
    qtbot.waitUntil(lambda: len(win.session.history) == before + 2, timeout=5000)
    wait_idle(qtbot, win)
    assert win.sky.geometry.factor == pytest.approx(2 * factor, rel=1e-6)  # 4 scatti = ×2
    texture = win.sky.renderer.texture
    assert texture[texture.shape[0] // 2, texture.shape[1] // 2, 3] == 255
    # il valore sotto il mouse è sempre quello del pixel disegnato
    p = window_pixel(win, 30, 20)
    result = hover(qtbot, win, p.x(), p.y())
    assert result.values["pixel"]["fits"] in ({"x": 31, "y": 21}, {"x": 30, "y": 21}, {"x": 31, "y": 20}, {"x": 30, "y": 20})


def test_bad_file_is_a_modal_error_and_view_unchanged(qtbot, win, tmp_path):
    broken = tmp_path / "broken.fits"
    broken.write_bytes(b"not a fits file")
    win.open_path = lambda name: str(broken)
    win.act_open_image.trigger()
    wait_idle(qtbot, win)
    qtbot.waitUntil(lambda: bool(win.modals), timeout=5000)
    assert win.session.workspace.state.view.base_layer is None and win.sky.image_key is None
