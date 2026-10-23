# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del visualizzatore del cielo (41 §12), sprint 4c: griglia delle coordinate (T3, T18), indicatore del nord e
barra di scala (T21), menu → comandi, modalità notte (T20, ``gl``).

Piattaforma ``offscreen`` con il renderer in memoria; il test ``gl`` usa la GPU. Valori attesi ricalcolati con il 10.
"""

import astropy.units as u
import numpy as np
import pytest

from astrotwo.core import coordinates_wcs as cw
from astrotwo.ui import sky_viewer as sv
from tests.core.test_commands import sky
from tests.ui.test_main_window import fake_simbad, make_window, names, settings_path, wait_idle  # noqa: F401 - fixture
from tests.ui.test_sky_viewer import start, viewer_window, wait_drawn  # noqa: F401 - fixture


def zoom_to(qtbot, win, arcsec=20.0, lon=56.75, lat=24.12):
    before = win.sky.sampling
    window = win.sky.window_size()
    win.submit("view.set_zoom", {"scale": {"value": arcsec, "unit": "arcsec"}, "window": window})
    win.submit("view.set_center", {"position": sky(lon, lat), "window": window})
    wait_drawn(qtbot, win, before)


def window_sky(win, q):
    """Punto del disegno (origine in alto, centri a +0.5) → cielo, con ``window_to_sky`` del 10."""
    rows = win.sky.geometry.shape[0]
    return win.sky.geometry.window_to_sky(q[:, 0] - 0.5, rows - q[:, 1] - 0.5)


@pytest.mark.parametrize("frame", ["icrs", "galactic"])
def test_t3_grid_points_are_on_the_lines_of_the_core(qtbot, viewer_window, frame):
    win = viewer_window
    start(qtbot, win)
    zoom_to(qtbot, win)
    win.submit("view.set_grid", {"visible": True, "frame": frame})
    wait_idle(qtbot, win)
    view = win.session.workspace.state.view
    overlay = win.sky.renderer.overlay
    assert win.sky.renderer.overlay is win.sky.overlay and view.grid.frame_name == frame
    assert len(view.grid.lines) >= 4
    # una polilinea per ogni tratto del 10, nello stesso ordine
    segments = [(line, seg) for line in view.grid.lines for seg in line.segments]
    assert len(overlay.grid_lines) == len(segments)
    for (line, _), points in zip(segments, overlay.grid_lines):
        coords = window_sky(win, points.astype(np.float64)).transform_to(frame)
        if line.kind == "meridian":
            diff = (coords.spherical.lon - line.value + 180 * u.deg) % (360 * u.deg) - 180 * u.deg
        else:
            diff = coords.spherical.lat - line.value
        assert np.max(np.abs(diff.to_value(u.deg))) < 1e-5  # ≪ 1 pixel (20″ = 0.0056°)


def test_t18_grid_labels_are_written_by_the_core_with_the_step_precision(qtbot, viewer_window):
    win = viewer_window
    start(qtbot, win)
    zoom_to(qtbot, win)
    win.submit("view.set_grid", {"visible": True, "frame": "icrs"})
    wait_idle(qtbot, win)
    grid = win.session.workspace.state.view.grid
    overlay = win.sky.renderer.overlay
    assert len(overlay.grid_labels) == len(grid.lines)
    cols, rows = win.sky.geometry.shape[1], win.sky.geometry.shape[0]
    for line, label in zip(grid.lines, overlay.grid_labels):
        meridian = line.kind == "meridian"
        text = cw.format_coordinates(values=line.value, frame="icrs", axis="lon" if meridian else "lat",
                                     precision=grid.lon_spacing if meridian else grid.lat_spacing)
        assert label.text == (text.lon if meridian else text.lat)[0]
        assert label.side == ("top" if meridian else "left")
        assert 0 <= label.x <= cols and 0 <= label.y <= rows
    # passo di circa 1′ o più: nessun secondo nelle etichette dei paralleli (precisione = passo)
    assert grid.lat_spacing >= 1 * u.arcmin
    assert all("″" not in label.text for label, line in zip(overlay.grid_labels, grid.lines) if line.kind == "parallel"
               and grid.lat_spacing >= 1 * u.arcmin)
    # grid spenta: nessuna linea
    win.submit("view.set_grid", {"visible": False, "frame": "icrs"})
    wait_idle(qtbot, win)
    assert win.sky.renderer.overlay.grid_lines == () and win.sky.renderer.overlay.grid_labels == ()


def test_grid_follows_zoom_and_pan(qtbot, viewer_window):
    win = viewer_window
    start(qtbot, win)
    zoom_to(qtbot, win)
    win.submit("view.set_grid", {"visible": True, "frame": "icrs"})
    wait_idle(qtbot, win)
    first = win.sky.renderer.overlay
    zoom_to(qtbot, win, arcsec=5.0, lon=57.0, lat=24.2)
    second = win.sky.renderer.overlay
    assert second is not first and second.grid_lines
    assert win.session.workspace.state.view.grid.lines
    assert [e.command.name for e in win.session.history.entries].count("view.set_grid") == 1  # nessun comando in più


def test_t21_compass_and_scale_bar_are_the_ones_of_the_core(qtbot, viewer_window):
    win = viewer_window
    start(qtbot, win)
    overlay = win.sky.renderer.overlay  # cielo intero: AIT, il polo può essere nel campo
    view = win.session.workspace.state.view
    expected = cw.compass_and_scale_bar(view.geometry, frame="icrs")
    assert overlay.bar_pixels == expected.bar_pixels
    assert overlay.bar_text == expected.label + " " + win.sky.overlay_texts["at_center"]  # AIT: vale al centro
    zoom_to(qtbot, win)
    overlay = win.sky.renderer.overlay
    view = win.session.workspace.state.view
    expected = cw.compass_and_scale_bar(view.geometry, frame="icrs")
    assert overlay.compass_shown and overlay.north == expected.north and overlay.east == expected.east
    assert overlay.bar_pixels == expected.bar_pixels and overlay.bar_text == expected.label  # TAN piccolo: locale
    assert overlay.pole_text is None
    # nord in alto e est a sinistra su una base creata (convenzione del 10)
    assert expected.north == pytest.approx((0.0, 1.0), abs=1e-3) and expected.east[0] < 0


def test_t21_pole_in_field_text(qtbot, viewer_window):
    win = viewer_window
    start(qtbot, win)
    zoom_to(qtbot, win, arcsec=5.0, lon=10.0, lat=90.0)
    overlay = win.sky.renderer.overlay
    assert overlay.north is None and overlay.east is None and overlay.pole_text == win.sky.overlay_texts["pole"]
    assert overlay.bar_pixels is not None


def test_menu_toggles_submit_set_overlays_and_stay_in_step(qtbot, viewer_window):
    win = viewer_window
    start(qtbot, win)
    zoom_to(qtbot, win)
    assert win.act_compass.isChecked() and win.act_scale_bar.isChecked()
    win.act_compass.trigger()
    wait_idle(qtbot, win)
    entry = win.session.history.entries[-1]
    assert entry.command.name == "view.set_overlays" and entry.command.parameters == {"compass": False, "scale_bar": True}
    overlay = win.sky.renderer.overlay
    assert not overlay.compass_shown and overlay.north is None and overlay.bar_pixels is not None
    win.act_scale_bar.trigger()
    wait_idle(qtbot, win)
    overlay = win.sky.renderer.overlay
    assert overlay.bar_pixels is None and overlay.bar_text is None and not overlay.compass_shown
    # un comando (per esempio dall'assistente o dalla riesecuzione) aggiorna le voci del menu
    win.submit("view.set_overlays", {"compass": True, "scale_bar": True})
    wait_idle(qtbot, win)
    assert win.act_compass.isChecked() and win.act_scale_bar.isChecked()
    assert win.sky.renderer.overlay.compass_shown and win.sky.renderer.overlay.bar_pixels is not None


@pytest.mark.gl
def test_t20_gl_overlay_drawn_and_red_only_at_night(qtbot):
    """Griglia, indicatore e barra sulla GPU: visibili, in grigio durante il gesto, solo rossi in modalità notte."""
    from astrotwo.ui.sky_renderer_gl import GlSkyRenderer

    renderer = GlSkyRenderer()
    qtbot.addWidget(renderer)
    renderer.resize(300, 200)
    renderer.show()
    qtbot.waitExposed(renderer)
    r = renderer.devicePixelRatioF()
    w, h = round(300 * r), round(200 * r)
    renderer.upload_texture(np.full((h, w, 4), (30, 90, 160, 255), dtype=np.uint8))
    line = np.array([[0.0, h / 2], [w, h / 2]], dtype=np.float32)
    overlay = sv.Overlay(grid_lines=(line,), grid_labels=(sv.GridLabel(w / 2, h / 4, "12h", "top"),),
                         compass_shown=True, north=(0.0, 1.0), east=(-1.0, 0.0), bar_pixels=80.0 * r, bar_text="10′")
    renderer.set_overlay(overlay)

    def bright(shot):
        return sum(1 for x in range(0, w, 2) for y in range(0, h, 2)
                   if (c := shot.pixelColor(x, y)).red() > 200 and c.green() > 200 and c.blue() > 200)

    assert bright(renderer.render_offscreen()) > 20  # indicatore e barra chiari sul cielo
    renderer.set_transform(1.0, 5.0, 0.0)  # gesto in corso: grigio, non più bianco
    assert bright(renderer.render_offscreen()) == 0
    renderer.set_transform(1.0, 0.0, 0.0)
    renderer.set_night(True)
    shot = renderer.render_offscreen()
    pixels = [shot.pixelColor(x, y) for x in range(0, w, 3) for y in range(0, h, 3)]
    assert all(c.green() <= 8 and c.blue() <= 8 for c in pixels)
    assert max(c.red() for c in pixels) > 150  # i tratti ci sono
