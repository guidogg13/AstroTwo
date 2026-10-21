# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del visualizzatore del cielo (41 §12), sprint 4f: MOC disegnati (T31, T3 per i MOC), sfondo sotto l'immagine
(T32), pannello dei livelli (T33, T15), corpi diversi con la forzatura (T13), Gaia DR3 propagato con la risposta
registrata (T34), MOC e notte sulla GPU (T35, ``gl``).

Piattaforma ``offscreen`` con il renderer in memoria; valori attesi ricalcolati con il 10 (``sky_to_window``) e il 16
(``healpix_grid``).
"""

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from mocpy import MOC
from scipy.spatial import cKDTree

from astrotwo.core import coordinates_wcs as cw
from astrotwo.core import planetary_data as pd
from astrotwo.core.catalogs import display_positions
from astrotwo.core.commands import MOC_COLORS, quantity_json, sky_json
from astrotwo.core.images_fits import load_image
from astrotwo.core.moc import CircleRegion, Moc, healpix_grid, moc_from_region, write_moc
from astrotwo.ui.sky_viewer import moc_step
from tests.core import gaia_recorded as gaia
from tests.core.test_commands_image_base import header, write
from tests.ui.test_catalog_sky import check_within_one_pixel, wait_points
from tests.ui.test_main_window import make_window, names, settings_path, wait_idle  # noqa: F401 - fixture
from tests.ui.test_sky_viewer import serve_png_survey, wait_drawn

CENTER = (10.0, 20.0)


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
    win.submit("view.set_center", {"position": sky_json(cw.SkyFrame.from_lonlat(lon * u.deg, lat * u.deg, "icrs")),
                                   "window": window})
    wait_idle(qtbot, win)


def sky_moc_file(tmp_path, name="m.fits", center=CENTER, radius=1.0, order=8):
    moc = moc_from_region(CircleRegion(SkyCoord(center[0] * u.deg, center[1] * u.deg), radius * u.deg), order)
    path = tmp_path / name
    write_moc(moc, path)
    return str(path), moc


def mars_moc_file(tmp_path):
    path = tmp_path / "mars.fits"
    write_moc(Moc(moc=MOC.from_string("3/1-5"), kind="space", body="Mars", origin="test"), path, overwrite=True)
    return str(path)


def open_moc(qtbot, win, path):
    win.open_path = lambda _name: path
    win.act_open_moc.trigger()
    wait_idle(qtbot, win)


def wait_mocs(qtbot, win, timeout=30000):
    """Comandi finiti e celle dei MOC visibili calcolate sulla base dello schermo, che è quella dello stato."""
    def ready():
        sky = win.sky
        state = win.session.workspace.state
        return (not win.busy() and not sky._moc_pending and sky.screen_geometry is state.view.geometry
                and all(sky.shapes_for(x) is not None or x.id in sky.moc_errors
                        for x in state.of_kind("moc") if x.visible))
    qtbot.waitUntil(ready, timeout=timeout)


def to_screen(win, lon_deg, lat_deg):
    """Punti dei contorni del 16 sullo schermo (pixel fisici): ``sky_to_window`` del 10 e trasformazione del disegno."""
    g = win.sky.screen_geometry
    wx, wy = g.sky_to_window(cw.SkyFrame.from_lonlat(np.ravel(lon_deg) * u.deg, np.ravel(lat_deg) * u.deg, "icrs"))
    k, tx, ty = win.sky.renderer.transform
    return np.column_stack([k * (np.asarray(wx) + 0.5) + tx, k * (g.shape[0] - np.asarray(wy) - 0.5) + ty])


def check_moc_within_one_pixel(win, layer_id, moc, order):
    """Ogni vertice disegnato (triangoli e perimetro) entro 1 pixel da un punto dei contorni di ``healpix_grid``; i
    segmenti del perimetro sono tutti e soli i lati di ``boundary`` delle celle disegnate."""
    grid = healpix_grid(order, within=moc, step=moc_step(order))
    expected = to_screen(win, grid.lon, grid.lat)
    _, triangles, lines = next(x for x in win.sky.renderer.drawn_polygons() if x[0] == layer_id)
    tree = cKDTree(expected)
    for points in (triangles, lines):
        assert len(points) and np.max(tree.query(points)[0]) <= 1.0
    shapes = win.sky.shapes_for(win.session.workspace.state.layer(layer_id))
    assert shapes.drawn_cells == grid.cells.size  # nessuna cella fuori proiezione in questi test
    assert len(lines) == 2 * moc_step(order) * int(grid.boundary.sum())
    assert len(triangles) == 3 * (4 * moc_step(order) - 2) * grid.cells.size


def test_t31_moc_drawn_within_one_pixel_with_style(qtbot, win, tmp_path):
    center_on(qtbot, win, *CENTER, 10.0)
    path, moc = sky_moc_file(tmp_path)
    open_moc(qtbot, win, path)
    wait_mocs(qtbot, win)
    layer = win.session.workspace.state.of_kind("moc")[0]
    assert layer.style == {"color": MOC_COLORS[0], "fill": 0.25}
    check_moc_within_one_pixel(win, layer.id, moc, 8)
    s = win.sky.renderer.polygons[0]
    rgb = tuple(int(MOC_COLORS[0][i:i + 2], 16) / 255 for i in (1, 3, 5))
    assert s.fill == pytest.approx(rgb + (0.25,)) and s.line == pytest.approx(rgb + (1.0,))
    assert win.sky.renderer.layers == (("polygons", layer.id, 1.0),)
    # opacità: riempimento 0,25 × opacità, perimetro = opacità
    win.submit("layer.set_opacity", {"layer": layer.id, "opacity": 0.5})
    wait_mocs(qtbot, win)
    s = win.sky.renderer.polygons[0]
    assert s.fill[3] == pytest.approx(0.125) and s.line[3] == pytest.approx(0.5)
    # zoom: nuova geometria, stesse celle entro 1 pixel
    center_on(qtbot, win, CENTER[0] + 0.3, CENTER[1], 4.0)
    wait_mocs(qtbot, win)
    check_moc_within_one_pixel(win, layer.id, moc, 8)
    assert "drawn at order 8" in win.layer_panel.rows[layer.id].details.text()


def test_t31_moc_on_image_base(qtbot, win, tmp_path):
    image = write(tmp_path / "img.fits", header(crval=CENTER, scale=2e-2))
    win.open_path = lambda _name: image
    win.act_open_image.trigger()
    wait_idle(qtbot, win)
    path, moc = sky_moc_file(tmp_path, radius=0.2)
    open_moc(qtbot, win, path)
    wait_mocs(qtbot, win)
    check_moc_within_one_pixel(win, "L2", moc, 8)


def test_t31_large_moc_drawn_by_excess(qtbot, win, tmp_path):
    path, moc = sky_moc_file(tmp_path, radius=30.0, order=12)
    open_moc(qtbot, win, path)
    wait_mocs(qtbot, win, timeout=60000)
    layer = win.session.workspace.state.of_kind("moc")[0]
    shapes = win.sky.shapes_for(layer)
    assert shapes.moc_order == 12 and shapes.order < 12
    # l'ordine disegnato è il più alto che il 16 accetta: quello sopra dà GRID_TOO_LARGE
    from astrotwo.core.moc import MocError
    healpix_grid(shapes.order, within=moc)
    with pytest.raises(MocError) as err:
        healpix_grid(shapes.order + 1, within=moc)
    assert err.value.code == "GRID_TOO_LARGE"
    text = win.layer_panel.rows[layer.id].details.text()
    assert f"drawn at order {shapes.order}, by excess (MOC order 12)" in text


def test_t32_hips_under_image_with_opacity_and_order(qtbot, settings_path, cache, service, monkeypatch, tmp_path):  # noqa: F811
    from astrotwo.core import hips

    monkeypatch.setattr(hips, "survey_coverage", lambda svc, **k: hips.service_coverage(svc, **k))
    win = make_window(qtbot, settings_path, cache)
    try:
        win.submit("hips.set_survey", {"survey": serve_png_survey(service)})
        win.sky.start_view()
        wait_drawn(qtbot, win)
        image = write(tmp_path / "img.fits", header(crval=CENTER, scale=2e-2))
        before = win.sky.sampling
        win.open_path = lambda _name: image
        win.act_open_image.trigger()
        wait_drawn(qtbot, win, before)
        state = win.session.workspace.state
        survey, img = state.of_kind("hips")[0].id, state.of_kind("image")[0].id
        r = win.sky.renderer
        assert state.view.base_layer == img and survey in r.textures and img in r.textures
        assert r.layers == (("texture", survey, 1.0), ("texture", img, 1.0))
        # fuori dall'immagine si vede lo sfondo: pixel trasparenti nel piano dell'immagine, dati nello sfondo
        assert (r.textures[img][..., 3] == 0).any() and (r.textures[survey][..., 3] == 255).any()
        tiles = len(service.requests)
        win.layer_panel.set_opacity(img, 50)
        wait_idle(qtbot, win)
        assert r.layers == (("texture", survey, 1.0), ("texture", img, 0.5))
        win.layer_panel.step(survey, -1)  # sfondo sopra l'immagine
        wait_idle(qtbot, win)
        assert r.layers == (("texture", img, 0.5), ("texture", survey, 1.0))
        win.layer_panel.set_visible(survey, False)
        wait_idle(qtbot, win)
        assert r.layers == (("texture", img, 0.5),)
        assert len(service.requests) == tiles  # opacità, ordine e visibilità: nessun nuovo tile
        assert names(win)[-3:] == ["layer.set_opacity", "layer.move", "layer.set_visible"]
    finally:
        win.close()


def test_t33_layer_panel_commands(qtbot, win, tmp_path):
    center_on(qtbot, win, *CENTER, 10.0)
    ids = []
    for k in range(3):
        open_moc(qtbot, win, sky_moc_file(tmp_path, f"m{k}.fits", radius=0.2 + 0.1 * k)[0])
        ids.append(win.session.workspace.state.of_kind("moc")[-1].id)
    wait_mocs(qtbot, win)
    panel = win.layer_panel
    assert win.layer_stack.currentIndex() == 1
    assert panel.panel_order() == tuple(reversed(ids))  # in alto il livello disegnato sopra
    row = panel.rows[ids[0]]
    assert "body celestial" in row.details.text() and "m0.fits" in row.details.text()
    assert not panel.rows[ids[2]].up.isEnabled() and not row.down.isEnabled()
    entries = len(win.session.history)
    row.visible.click()  # casella → layer.set_visible
    wait_idle(qtbot, win)
    # cursore: un solo comando al rilascio
    slider = panel.rows[ids[1]].opacity
    slider.setSliderDown(True)
    for value in (90, 70, 40):
        slider.setValue(value)
    slider.setSliderDown(False)
    wait_idle(qtbot, win)
    panel.rows[ids[2]].down.click()  # su/giù → layer.move
    wait_idle(qtbot, win)
    panel.move_row(0, 2)  # trascinamento dalla cima al fondo
    wait_idle(qtbot, win)
    panel.rows[ids[1]].remove.click()
    wait_idle(qtbot, win)
    new = win.session.history.entries[entries:]
    assert [e.command.name for e in new] == ["layer.set_visible", "layer.set_opacity", "layer.move", "layer.move",
                                            "layer.remove"]
    assert all(e.command.requested_by.source == "mouse" for e in new)
    assert new[0].command.parameters == {"layer": ids[0], "visible": False, "force_body": False}
    assert new[1].command.parameters["opacity"] == pytest.approx(0.4)
    state = win.session.workspace.state
    # [L1, L2, L3] → giù di L3 → [L1, L3, L2] → L2 dalla cima al fondo → [L2, L1, L3] → via L2 → [L1, L3]
    assert [x.id for x in state.layers] == [ids[0], ids[2]] and panel.panel_order() == (ids[2], ids[0])
    assert win.sky.renderer.layers == (("polygons", ids[2], 1.0),)  # ids[0] nascosto
    win.submit("layer.remove", {"layer": ids[0]})
    win.submit("layer.remove", {"layer": ids[2]})
    wait_idle(qtbot, win)
    assert win.layer_stack.currentIndex() == 0  # stato vuoto del 40


def test_t13_different_bodies_force_dialog(qtbot, win, tmp_path):
    asked = []
    answers = [False, True, True]
    win.ask_force_body = lambda text: (asked.append(text), answers.pop(0))[1]
    open_moc(qtbot, win, sky_moc_file(tmp_path)[0])
    open_moc(qtbot, win, mars_moc_file(tmp_path))
    assert asked and asked[0].startswith("BODY_MISMATCH") and "Mars" in asked[0]
    assert names(win)[-1] == "moc.open" and len(win.session.workspace.state.of_kind("moc")) == 1  # annullata
    # forzata con i dati planetari spenti: il 19 risponde PLANETARY_DATA_DISABLED
    open_moc(qtbot, win, mars_moc_file(tmp_path))
    wait_idle(qtbot, win)
    last = win.session.history.entries[-1]
    assert last.command.parameters["force_body"] is True and last.result.error.code == "PLANETARY_DATA_DISABLED"
    pd.set_planetary_data_enabled(True)
    try:
        open_moc(qtbot, win, mars_moc_file(tmp_path))
        wait_idle(qtbot, win)
        wait_mocs(qtbot, win)
    finally:
        pd.set_planetary_data_enabled(False)
    layer = win.session.workspace.state.of_kind("moc")[-1]
    assert layer.force_body and win.session.history.entries[-1].command.parameters["force_body"] is True
    assert win.sky.moc_errors[layer.id].code == "MOC_BODY_UNSUPPORTED"  # nessun disegno di un MOC di Marte sul cielo
    text = win.layer_panel.rows[layer.id].details.text()
    assert "overlay forced (force_body)" in text and "not drawn: MOC_BODY_UNSUPPORTED" in text
    assert len(win.sky.polygon_sets) == 1


def test_t34_gaia_dr3_propagated_from_coosys_epoch(qtbot, win, tmp_path, service, monkeypatch):
    gaia.serve(service, monkeypatch)
    image = write(tmp_path / "img.fits", header(crval=gaia.CENTER, scale=1e-3, **{"RADESYS": "ICRS",
                                                                                 "MJD-OBS": 55000.0}))
    win.open_path = lambda _name: image
    win.act_open_image.trigger()
    wait_idle(qtbot, win)
    center = sky_json(cw.SkyFrame.from_lonlat(gaia.CENTER[0] * u.deg, gaia.CENTER[1] * u.deg, "icrs"))
    win.submit("catalog.load_region", {"catalog": gaia.CATALOG, "center": center,
                                       "radius": quantity_json(gaia.RADIUS), "max_rows": 100})
    wait_idle(qtbot, win)
    assert win.session.history.entries[-1].result.status == "ok"
    layer = win.session.workspace.state.of_kind("catalog")[0]
    assert layer.data.positions.epoch == "J2016"
    win.submit("catalog.set_columns", {"layer": layer.id, "lon": "RA_ICRS", "lat": "DE_ICRS", "frame": "icrs",
                                       "pm_ra": "pmRA", "pm_dec": "pmDE", "pm_ra_includes_cosdec": True})
    wait_idle(qtbot, win)
    layer = win.session.workspace.state.of_kind("catalog")[0]
    shown = display_positions(layer.data, load_image(image), pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True)
    wait_points(qtbot, win, int(shown.drawable.sum()))
    assert not any(m.code == "EPOCH_INVALID" for m in win.seen)
    ok = shown.drawable  # le righe non disegnabili (NaN) non si controllano: non sono tra quelle disegnate
    coords = cw.SkyFrame.from_lonlat(np.where(ok, shown.lon, 0.0) * u.deg, np.where(ok, shown.lat, 0.0) * u.deg, "icrs")
    check_within_one_pixel(win, coords, layer.id)
    points = win.sky.points_for(layer)
    assert points.propagated and "J2016" in shown.source_epoch
    assert "drawn at epoch" in win.layer_panel.rows[layer.id].details.text()


@pytest.mark.gl
def test_t35_gl_moc_fill_perimeter_and_night(qtbot):
    """MOC sulla GPU: riempimento trasparente e perimetro nel colore dello stile, sopra un piano; in notte solo rossi."""
    from astrotwo.ui.sky_renderer_gl import GlSkyRenderer
    from astrotwo.ui.sky_viewer import PolygonSet

    renderer = GlSkyRenderer()
    qtbot.addWidget(renderer)
    renderer.resize(300, 200)
    renderer.show()
    qtbot.waitExposed(renderer)
    assert renderer.available
    r = renderer.devicePixelRatioF()
    w, h = int(300 * r), int(200 * r)
    plane = np.zeros((h, w, 4), np.uint8)
    plane[..., 2], plane[..., 3] = 200, 255  # piano blu
    renderer.upload_texture(plane, "L1")
    x0, y0, x1, y1 = 60 * r, 40 * r, 240 * r, 160 * r
    tri = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y0], [x1, y1], [x0, y1]], np.float32)
    lines = np.array([[x0, y0], [x1, y0], [x1, y0], [x1, y1], [x1, y1], [x0, y1], [x0, y1], [x0, y0]], np.float32)
    orange = (0.9, 0.62, 0.0)
    renderer.upload_polygons((PolygonSet("L2", tri, orange + (0.25,), lines, orange + (1.0,)),))
    renderer.set_layers((("texture", "L1", 1.0), ("polygons", "L2", 1.0)))
    shot = renderer.render_offscreen()
    inside = shot.pixelColor(int(150 * r), int(100 * r))
    outside = shot.pixelColor(int(20 * r), int(20 * r))
    edge = shot.pixelColor(int(150 * r), int(y0))
    assert inside.red() > 150 * 0.2 and inside.blue() < 200 and outside.red() < 10 and outside.blue() > 180
    assert edge.red() > 200 and edge.blue() < 30  # perimetro pieno sopra il piano
    renderer.set_layers((("polygons", "L2", 1.0), ("texture", "L1", 0.5)))  # piano sopra, semitrasparente
    shot = renderer.render_offscreen()
    assert shot.pixelColor(int(150 * r), int(y0)).blue() > 60
    renderer.set_night(True)
    renderer.set_layers((("texture", "L1", 1.0), ("polygons", "L2", 1.0)))
    shot = renderer.render_offscreen()
    pixels = [shot.pixelColor(x, y) for x in range(0, shot.width(), 3) for y in range(0, shot.height(), 3)]
    assert all(c.green() <= 8 and c.blue() <= 8 for c in pixels)
    assert shot.pixelColor(int(150 * r), int(y0)).red() > 120  # perimetro rosso, ben visibile
