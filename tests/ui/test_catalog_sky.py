# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del visualizzatore del cielo (41 §12), sprint 4e: cataloghi disegnati (T26), clic e scheda della sorgente
(T27), epoche diverse (T28), epoca nella barra in ISO 8601 (T29, in ``test_image_base.py``), qualche migliaio di
sorgenti (T30), griglia di pixel senza cataloghi, simboli sulla GPU (``gl``).

Piattaforma ``offscreen`` con il renderer in memoria; valori attesi ricalcolati con il 10 (``sky_to_window`` della
``ViewGeometry``, ``format_coordinates``) e con il 13 (``display_positions``).
"""

import time

import astropy.units as u
import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtTest import QTest

from astrotwo.core import coordinates_wcs as cw
from astrotwo.core.catalogs import display_positions, load_table
from astrotwo.core.commands import CATALOG_COLORS, catalog_positions, quantity_json, sky_json, time_text
from astrotwo.core.images_fits import load_image
from tests.core.test_commands_catalog_sky import ROWS, write_catalog
from tests.core.test_commands_image_base import header, write
from tests.ui.test_main_window import make_window, settings_path, wait_idle  # noqa: F401 - fixture
from tests.ui.test_sky_viewer import mouse

PLEIADES = (56.75, 24.12)


@pytest.fixture
def win(qtbot, settings_path, cache):  # noqa: F811
    win = make_window(qtbot, settings_path, cache)
    win.seen = []
    win.sky.message.connect(win.seen.append)
    win.sky.start_view()
    wait_idle(qtbot, win)
    yield win
    win.close()


def center_on(qtbot, win, lon, lat, scale_arcsec):
    window = win.view_window()
    win.submit("view.set_zoom", {"scale": quantity_json((scale_arcsec * u.arcsec).to(u.deg)), "window": window})
    position = sky_json(cw.SkyFrame.from_lonlat(lon * u.deg, lat * u.deg, "icrs"))
    win.submit("view.set_center", {"position": position, "window": window})
    wait_idle(qtbot, win)


def open_file(qtbot, win, name, path):
    win.open_path = lambda _name: path
    {"image.open": win.act_open_image, "catalog.open_file": win.act_open_catalog}[name].trigger()
    wait_idle(qtbot, win)


def wait_points(qtbot, win, n, timeout=15000):
    """Comandi finiti e simboli calcolati sulla base dello schermo, che è quella dello stato."""
    def ready():
        sky = win.sky
        return (not win.busy() and not sky._catalog_pending
                and sky.screen_geometry is win.session.workspace.state.view.geometry
                and sum(len(s.rows) for s in sky.point_sets) == n)
    qtbot.waitUntil(ready, timeout=timeout)


def expected_screen(win, coords):
    """Posizioni attese sullo schermo (pixel fisici): ``sky_to_window`` del 10 poi la trasformazione del disegno."""
    g = win.sky.screen_geometry
    wx, wy = g.sky_to_window(coords)
    k, tx, ty = win.sky.renderer.transform
    return np.column_stack([k * (np.asarray(wx) + 0.5) + tx, k * (g.shape[0] - np.asarray(wy) - 0.5) + ty])


def drawn(win, layer="L1"):
    return next((rows, xy) for name, rows, xy in win.sky.renderer.drawn_positions() if name == layer)


def check_within_one_pixel(win, coords, layer="L1"):
    """``coords`` = posizioni di tutte le righe, nell'ordine della tabella (tutte disegnate in questi test)."""
    rows, xy = drawn(win, layer)
    expected = expected_screen(win, coords)[rows]
    assert np.max(np.hypot(*(xy - expected).T)) <= 1.0


def test_t26_catalog_drawn_within_one_pixel_with_layer_style(qtbot, win, tmp_path):
    center_on(qtbot, win, *PLEIADES, 10.0)
    path = write_catalog(tmp_path / "c.xml")
    open_file(qtbot, win, "catalog.open_file", path)
    wait_points(qtbot, win, len(ROWS))
    coords, valid = catalog_positions(load_table(path))
    assert valid.all()
    check_within_one_pixel(win, coords)
    s = win.sky.renderer.points[0]
    assert s.rows.tolist() == [0, 1, 2]
    rgb = [int(CATALOG_COLORS[0][i:i + 2], 16) / 255 for i in (1, 3, 5)]
    assert np.allclose(s.rgba[:, :3], rgb) and np.all(s.size == 8.0) and np.all(s.shape == 0.0)  # circle
    # zoom con la rotella: durante il gesto i simboli seguono la trasformazione, poi la nuova base
    uploads = win.sky.renderer.point_uploads
    here = QPoint(win.sky.width() // 2, win.sky.height() // 2)
    from tests.ui.test_sky_viewer import wheel
    for _ in range(12):
        wheel(win.sky, 1, here)
    assert win.sky.renderer.point_uploads == uploads  # solo la trasformazione cambia
    check_within_one_pixel(win, coords)
    qtbot.waitUntil(lambda: "view.set_zoom" in [e.command.name for e in win.session.history.entries[-2:]],
                    timeout=5000)
    wait_points(qtbot, win, len(ROWS))
    check_within_one_pixel(win, coords)
    # spostamento: i simboli seguono il gesto, poi la nuova finestra
    mouse(win.sky, QEvent.Type.MouseButtonPress, here)
    mouse(win.sky, QEvent.Type.MouseMove, here + QPoint(40, 25))
    mouse(win.sky, QEvent.Type.MouseButtonRelease, here + QPoint(40, 25))
    check_within_one_pixel(win, coords)
    qtbot.waitUntil(lambda: win.session.history.entries[-1].command.name == "view.set_center", timeout=5000)
    wait_points(qtbot, win, len(ROWS))
    check_within_one_pixel(win, coords)


def test_t26_catalog_on_image_base_and_propagation(qtbot, win, tmp_path):
    image = write(tmp_path / "img.fits", header(**{"RADESYS": "ICRS", "MJD-OBS": 55000.0}))
    open_file(qtbot, win, "image.open", image)
    rows = (("A", 150.01, 2.005, 300.0, -200.0), ("B", 149.99, 1.995, -150.0, 80.0))
    path = write_catalog(tmp_path / "c.xml", rows)
    open_file(qtbot, win, "catalog.open_file", path)
    wait_points(qtbot, win, 2)
    coords, _ = catalog_positions(load_table(path))
    check_within_one_pixel(win, coords, "L2")
    # moto proprio scelto con catalog.set_columns: posizioni di display_positions del 13 all'epoca dell'immagine;
    # l'epoca J2016.0 del COOSYS resta dopo la conferma delle colonne (D41-6, decisa il 2026-10-21).
    win.submit("catalog.set_columns", {"layer": "L2", "lon": "RA_ICRS", "lat": "DE_ICRS", "frame": "icrs",
                                       "pm_ra": "pmRA", "pm_dec": "pmDE", "pm_ra_includes_cosdec": True})
    wait_points(qtbot, win, 2)
    assert not any(m.code == "EPOCH_INVALID" for m in win.seen)
    layer = win.session.workspace.state.layer("L2")
    assert layer.data.positions.epoch == "J2016.0"
    shown = display_positions(layer.data, load_image(image), pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True)
    check_within_one_pixel(win, shown.coords, "L2")
    assert win.sky.points_for(layer).propagated


def test_propagated_positions_with_epoch_column(qtbot, win, tmp_path):
    image = write(tmp_path / "img.fits", header(**{"RADESYS": "ICRS", "MJD-OBS": 55000.0}))
    open_file(qtbot, win, "image.open", image)
    text = (write_catalog(tmp_path / "x.xml", (("A", 150.01, 2.005, 3000.0, -2000.0),)) and
            (tmp_path / "x.xml").read_text())
    text = text.replace('<FIELD name="pmRA"', '<FIELD name="Ep" datatype="double" unit="yr" ucd="time.epoch"/>\n'
                        '<FIELD name="pmRA"').replace("<TD>3000.0</TD>", "<TD>2016.0</TD><TD>3000.0</TD>")
    path = tmp_path / "e.xml"
    path.write_text(text)
    open_file(qtbot, win, "catalog.open_file", str(path))
    wait_points(qtbot, win, 1)
    win.submit("catalog.set_columns", {"layer": "L2", "lon": "RA_ICRS", "lat": "DE_ICRS", "frame": "icrs",
                                       "pm_ra": "pmRA", "pm_dec": "pmDE", "pm_ra_includes_cosdec": True})
    wait_points(qtbot, win, 1)
    layer = win.session.workspace.state.layer("L2")
    shown = display_positions(layer.data, load_image(image), pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True)
    check_within_one_pixel(win, shown.coords, "L2")
    points = win.sky.points_for(layer)
    assert points.propagated and time_text(points.epoch) == time_text(shown.epoch)
    assert points.warnings == ()  # propagata: nessun avviso di epoche diverse


def screen_point(win, layer="L1", index=0, dx=0.0):
    _, xy = drawn(win, layer)
    r = win.sky.ratio()
    return QPoint(round(xy[index, 0] / r + dx), round(xy[index, 1] / r))


def test_t27_click_selects_and_shows_card(qtbot, win, tmp_path):
    center_on(qtbot, win, *PLEIADES, 10.0)
    path = write_catalog(tmp_path / "c.xml")
    open_file(qtbot, win, "catalog.open_file", path)
    wait_points(qtbot, win, len(ROWS))
    at = screen_point(win, index=1, dx=2.0)  # 2 pixel logici dalla sorgente
    mouse(win.sky, QEvent.Type.MouseButtonPress, at)
    mouse(win.sky, QEvent.Type.MouseButtonRelease, at)
    wait_idle(qtbot, win)
    entry = win.session.history.entries[-1]
    assert entry.command.name == "catalog.select" and entry.command.parameters["rows"] == [1]
    assert entry.command.requested_by.source == "mouse"
    assert win.sky.card.isVisible()
    text = win.sky.card.text()
    lon = cw.format_coordinates(values=ROWS[1][1] * u.deg, frame="icrs", axis="lon").lon[0]
    lat = cw.format_coordinates(values=ROWS[1][2] * u.deg, frame="icrs", axis="lat").lat[0]
    assert "HD 23302" in text and f"ICRS {lon} {lat}" in text
    assert "J2016" in text and "not propagated" in text and "JD" not in text
    assert win.sky.renderer.points[0].selected.tolist() == [False, True, False]
    QTest.keyClick(win.sky, Qt.Key.Key_Escape)
    assert not win.sky.card.isVisible()
    # clic nel vuoto con una selezione attiva: selezione tolta con un comando
    corner = QPoint(30, 30)
    assert win.sky.source_at(corner) is None
    mouse(win.sky, QEvent.Type.MouseButtonPress, corner)
    mouse(win.sky, QEvent.Type.MouseButtonRelease, corner)
    wait_idle(qtbot, win)
    entry = win.session.history.entries[-1]
    assert entry.command.name == "catalog.select" and entry.command.parameters["rows"] == []
    count = len(win.session.history)
    mouse(win.sky, QEvent.Type.MouseButtonPress, corner)  # nessuna selezione: nessun comando
    mouse(win.sky, QEvent.Type.MouseButtonRelease, corner)
    wait_idle(qtbot, win)
    assert len(win.session.history) == count


def test_t27_far_click_selects_nothing_and_name_fallback(qtbot, win, tmp_path):
    center_on(qtbot, win, *PLEIADES, 10.0)
    open_file(qtbot, win, "catalog.open_file", write_catalog(tmp_path / "c.xml", name_ucd="meta.note"))
    wait_points(qtbot, win, len(ROWS))
    assert win.sky.source_at(screen_point(win, index=0, dx=6.0)) is None  # oltre 4 pixel logici
    at = screen_point(win, index=0)
    mouse(win.sky, QEvent.Type.MouseButtonPress, at)
    mouse(win.sky, QEvent.Type.MouseButtonRelease, at)
    wait_idle(qtbot, win)
    assert "row 0" in win.sky.card.text()


def test_t28_epoch_warnings(qtbot, win, tmp_path):
    center_on(qtbot, win, *PLEIADES, 10.0)
    open_file(qtbot, win, "catalog.open_file", write_catalog(tmp_path / "c.xml"))
    wait_points(qtbot, win, len(ROWS))
    assert not any(m.code.startswith("CATALOG_EPOCH") for m in win.seen)  # senza immagine datata: nessun avviso
    win.submit("layer.remove", {"layer": "L1"})
    image = write(tmp_path / "img.fits", header(**{"RADESYS": "ICRS", "MJD-OBS": 55000.0}))
    open_file(qtbot, win, "image.open", image)
    rows = (("A", 150.01, 2.005, 1.0, 1.0),)
    open_file(qtbot, win, "catalog.open_file", write_catalog(tmp_path / "d.xml", rows))
    open_file(qtbot, win, "catalog.open_file", write_catalog(tmp_path / "e.xml", rows, epoch=""))
    wait_points(qtbot, win, 2)
    codes = {m.code: m.text for m in win.seen}
    assert "J2016" in codes["CATALOG_EPOCH_DIFFERS"] and "2009-06-18T00:00:00 UTC" in codes["CATALOG_EPOCH_DIFFERS"]
    assert "CATALOG_EPOCH_UNKNOWN" in codes


def test_pixel_grid_draws_no_catalog(qtbot, win, tmp_path):
    # un catalogo e un'immagine senza WCS non stanno insieme: il 19 rifiuta l'uno sull'altro (BODY_UNKNOWN, anche con
    # force_body). La protezione del 41 (VIEW_NO_WCS) si prova sul visualizzatore con un livello di catalogo dato.
    from astrotwo.core.commands import Layer

    open_file(qtbot, win, "image.open", write(tmp_path / "plain.fits", None))
    assert win.sky.pixel_grid
    path = write_catalog(tmp_path / "c.xml")
    win.sky.catalog_layers = (Layer("L9", "catalog", "c", load_table(path)),)
    win.sky.update_catalogs()
    assert [m.code for m in win.seen] == ["VIEW_NO_WCS"] and not win.sky._catalog_pending
    assert not win.sky.point_sets


def test_t30_thousands_of_sources(qtbot, win, tmp_path):
    rng = np.random.default_rng(7)
    n = 5000
    ra, de = PLEIADES[0] + rng.uniform(-0.8, 0.8, n), PLEIADES[1] + rng.uniform(-0.6, 0.6, n)
    rows = tuple((f"S{k}", float(a), float(d), 0.0, 0.0) for k, (a, d) in enumerate(zip(ra, de, strict=True)))
    center_on(qtbot, win, *PLEIADES, 10.0)
    start = time.perf_counter()
    open_file(qtbot, win, "catalog.open_file", write_catalog(tmp_path / "c.xml", rows))
    drawn_rows = int(np.count_nonzero(np.isfinite(win.sky.geometry.sky_to_window(
        catalog_positions(load_table(str(tmp_path / "c.xml")))[0])[0])))
    qtbot.waitUntil(lambda: bool(win.sky.point_sets) and not win.sky._catalog_pending, timeout=20000)
    total = time.perf_counter() - start
    points = win.sky.points_for(win.session.workspace.state.layer("L1"))
    assert len(points.rows) == drawn_rows == n
    print(f"\nT30: {n} sorgenti, posizioni sulla base in {points.seconds * 1000:.1f} ms (gruppo di thread), "
          f"apertura e disegno in {total * 1000:.0f} ms")
    uploads = win.sky.renderer.point_uploads
    here = QPoint(win.sky.width() // 2, win.sky.height() // 2)
    mouse(win.sky, QEvent.Type.MouseButtonPress, here)
    for step in range(1, 20):
        mouse(win.sky, QEvent.Type.MouseMove, here + QPoint(3 * step, step))
    assert win.sky.renderer.point_uploads == uploads  # durante il gesto solo la trasformazione
    mouse(win.sky, QEvent.Type.MouseButtonRelease, here + QPoint(57, 19))
    wait_idle(qtbot, win)


def test_night_mode_card(qtbot, win, tmp_path):
    center_on(qtbot, win, *PLEIADES, 10.0)
    open_file(qtbot, win, "catalog.open_file", write_catalog(tmp_path / "c.xml"))
    wait_points(qtbot, win, len(ROWS))
    win.submit("catalog.select", {"layer": "L1", "rows": [0]})
    wait_idle(qtbot, win)
    win.act_night.trigger()
    wait_idle(qtbot, win)
    assert win.sky.renderer.night is True and "#ff2020" in win.sky.card.styleSheet()


@pytest.mark.gl
def test_gl_symbols_drawn_at_positions_and_red_at_night(qtbot):
    """Simboli sulla GPU: una macchia di colore attorno a ogni posizione, nulla lontano, solo rossi in notte."""
    from astrotwo.ui.sky_renderer_gl import GlSkyRenderer
    from astrotwo.ui.sky_viewer import PointSet

    renderer = GlSkyRenderer()
    qtbot.addWidget(renderer)
    renderer.resize(300, 200)
    renderer.show()
    qtbot.waitExposed(renderer)
    assert renderer.available
    r = renderer.devicePixelRatioF()
    positions = np.array([[50, 50], [150, 50], [250, 50], [50, 150], [150, 150], [250, 150], [100, 100]],
                         dtype=np.float32) * r
    n = len(positions)
    rgba = np.tile(np.array([[0.0, 0.62, 0.45, 1.0]], np.float32), (n, 1))  # verde-blu di Okabe e Ito
    sets = (PointSet("L1", np.arange(n), positions, rgba, np.full(n, 16.0, np.float32),
                     np.arange(n, dtype=np.float32), np.zeros(n, bool)),)
    renderer.upload_points(sets)
    shot = renderer.render_offscreen()
    for (x, y), shape in zip(positions, range(n), strict=True):
        found = [shot.pixelColor(int(x) + dx, int(y) + dy) for dx in range(-int(9 * r), int(9 * r) + 1)
                 for dy in range(-int(9 * r), int(9 * r) + 1)]
        assert any(c.green() > 80 for c in found), f"forma {shape} non disegnata"
    far = shot.pixelColor(int(100 * r), int(30 * r))
    assert far.green() < 20
    renderer.set_night(True)
    shot = renderer.render_offscreen()
    pixels = [shot.pixelColor(x, y) for x in range(0, shot.width(), 3) for y in range(0, shot.height(), 3)]
    assert all(c.green() <= 8 and c.blue() <= 8 for c in pixels)
    assert max(c.red() for c in pixels) > 120
