# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del visualizzatore del cielo (41 §12), sprint 4h: cambio di base in un passo (T17, 41 §3.2).

Il calcolo delle posizioni del catalogo e delle celle del MOC sulla base nuova è trattenuto da un cancello; il
renderer in memoria registra ogni chiamata con il «turno» del ciclo degli eventi (un timer a 0 ms): un fotogramma
non può cadere nel mezzo di una chiamata sincrona, quindi chiamate dello stesso turno sono nello stesso fotogramma.
"""

import threading

import astropy.units as u
import pytest
from PySide6.QtCore import QTimer

from astrotwo.core import hips
from astrotwo.core.catalogs import load_table
from astrotwo.core.commands import catalog_positions, quantity_json, sky_json
from astrotwo.core import coordinates_wcs as cw
from astrotwo.ui import sky_viewer as sv
from tests.core.test_commands_catalog_sky import ROWS, write_catalog
from tests.ui.test_catalog_sky import PLEIADES, check_within_one_pixel, open_file, wait_points, wait_settled
from tests.ui.test_layers_moc import sky_moc_file
from tests.ui.test_main_window import make_window, settings_path, wait_idle  # noqa: F401 - fixture
from tests.ui.test_sky_viewer import serve_png_survey

DRAWN = ("upload_texture", "upload_points", "upload_polygons", "set_overlay")


class Gate:
    """Trattiene, finché è chiuso, il calcolo dei simboli o dei MOC (thread dei tile)."""

    def __init__(self):
        self.closed = False
        self.event = threading.Event()
        self.entered = threading.Event()

    def wrap(self, original):
        def run(*args, **kwargs):
            if self.closed:
                self.entered.set()
                self.event.wait(30)
            return original(*args, **kwargs)
        return run

    def close(self):
        self.closed = True
        self.event.clear()
        self.entered.clear()

    def open(self):
        self.closed = False
        self.event.set()


@pytest.fixture
def scene(qtbot, settings_path, cache, service, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(hips, "survey_coverage", lambda svc, **k: hips.service_coverage(svc, **k))
    catalog_gate, moc_gate = Gate(), Gate()
    monkeypatch.setattr(sv, "catalog_points", catalog_gate.wrap(sv.catalog_points))
    monkeypatch.setattr(sv, "moc_shapes", moc_gate.wrap(sv.moc_shapes))
    win = make_window(qtbot, settings_path, cache)
    win.seen = []
    win.sky.message.connect(win.seen.append)
    url = serve_png_survey(service)
    win.submit("hips.set_survey", {"survey": url})
    win.sky.start_view()
    wait_idle(qtbot, win)
    window = win.view_window()
    win.submit("view.set_zoom", {"scale": quantity_json((30.0 * u.arcsec).to(u.deg)), "window": window})
    win.submit("view.set_center", {"position": sky_json(cw.SkyFrame.from_lonlat(*(PLEIADES * u.deg), "icrs")),
                                   "window": window})
    wait_settled(qtbot, win)
    path = write_catalog(tmp_path / "c.xml")
    open_file(qtbot, win, "catalog.open_file", path)
    wait_points(qtbot, win, len(ROWS))
    moc_path, _ = sky_moc_file(tmp_path, center=PLEIADES, radius=2.0, order=7)
    win.open_path = lambda _name: moc_path
    win.act_open_moc.trigger()
    wait_settled(qtbot, win)
    qtbot.waitUntil(lambda: win.sky._in_flight == 0 and bool(win.sky.polygon_sets), timeout=20000)
    win.catalog_path = path
    win.gates = (catalog_gate, moc_gate)
    yield win
    catalog_gate.open()
    moc_gate.open()
    win.close()


def record_calls(win):
    """Registro ``(chiamata, turno)`` delle chiamate al renderer che disegnano la base (turno = ciclo degli eventi)."""
    turn = [0]
    timer = QTimer(win)
    timer.setInterval(0)
    timer.timeout.connect(lambda: turn.__setitem__(0, turn[0] + 1))
    timer.start()
    log = []
    renderer = win.sky.renderer
    for name in DRAWN:
        original = getattr(renderer, name)

        def wrapped(*args, _original=original, _name=name, **kwargs):
            log.append((_name, turn[0], win.sky.screen_geometry))
            return _original(*args, **kwargs)

        setattr(renderer, name, wrapped)
    return log, timer


def held(log, old):
    """Finché la base nuova non è pronta: nessun piano e nessuna griglia, e i simboli (se ricaricati) sono quelli
    della base vecchia (``refresh_points`` ricarica gli stessi dati)."""
    return all(g is old and name in ("upload_points", "upload_polygons") for name, _, g in log)


def move_far(win):
    window = win.view_window()
    old = win.session.workspace.state.view.geometry
    # 8° a est: con 30″ per pixel la finestra è larga meno di 8°, il punto di tangenza esce dalla finestra
    center = cw.SkyFrame.from_lonlat((PLEIADES[0] + 8.0) * u.deg, PLEIADES[1] * u.deg, "icrs")
    win.submit("view.set_center", {"position": sky_json(center), "window": window})
    return old


def test_t17_one_step_base_change(qtbot, scene):
    win = scene
    sky = win.sky
    catalog_gate, moc_gate = win.gates
    old = sky.screen_geometry
    before = {"points": [(n, xy.copy()) for n, _, xy in sky.renderer.drawn_positions()],
              "overlay": sky.renderer.overlay, "texture": sky.renderer.textures.copy()}
    log, timer = record_calls(win)
    catalog_gate.close()
    moc_gate.close()
    move_far(win)
    wait_idle(qtbot, win)
    new = win.session.workspace.state.view.geometry
    assert sv.base_key(new) != sv.base_key(old)  # la base è cambiata
    assert catalog_gate.entered.wait(20)
    qtbot.waitUntil(lambda: sky._stage_sampled and sky._in_flight == 0, timeout=20000)  # tile della base nuova arrivati
    # base nuova pronta per sfondo e tile, ma non per i simboli: nulla del disegno è cambiato
    assert sky.geometry is new and sky.screen_geometry is old and sky._stage is not None
    assert held(log, old)
    assert sky.renderer.overlay is before["overlay"]
    assert all(sky.renderer.textures[k] is v for k, v in before["texture"].items())
    assert all((xy == b).all() for (_, _, xy), (_, b) in zip(sky.renderer.drawn_positions(), before["points"],
                                                             strict=True))
    # i simboli sono pronti, il MOC no: ancora nulla
    catalog_gate.open()
    qtbot.waitUntil(lambda: not sky._catalog_pending, timeout=20000)
    assert moc_gate.entered.wait(20)
    assert sky.screen_geometry is old and held(log, old)
    moc_gate.open()
    qtbot.waitUntil(lambda: sky.screen_geometry is new, timeout=20000)
    # tutto insieme: sfondo, simboli, poligoni, griglia/indicatori nello stesso turno e sulla base nuova
    kinds = {name for name, _, _ in log}
    assert {"upload_texture", "upload_points", "upload_polygons", "set_overlay"} <= kinds
    commit_turn = [t for n, t, g in log if g is new and n == "upload_texture"][0]
    commit = [(n, t, g) for n, t, g in log if t == commit_turn]
    # a fine turno (= fotogramma) l'ultima chiamata di ogni genere è sulla base nuova; prima possono esserci solo
    # i ricaricamenti dei dati vecchi (``refresh_points`` sulla base vecchia), mai il contrario
    for kind in DRAWN:
        calls = [g for n, _, g in commit if n == kind]
        assert calls and calls[-1] is new, kind
        assert calls == [old] * calls.count(old) + [new] * calls.count(new), kind
    assert not [1 for n, t, g in log if g is old and t > commit_turn]  # dopo il passaggio la vecchia base non c'è più
    wait_points(qtbot, win, len(ROWS))
    coords, valid = catalog_positions(load_table(win.catalog_path))
    check_within_one_pixel(win, coords, layer=win.session.workspace.state.of_kind("catalog")[0].id)
    timer.stop()


def test_t17_failed_catalog_does_not_block_the_change(qtbot, scene, monkeypatch):
    win = scene
    sky = win.sky
    old = sky.screen_geometry

    def broken(key, layer, geometry, image):
        raise RuntimeError("calcolo di prova fallito")

    monkeypatch.setattr(sv, "catalog_points", broken)
    move_far(win)
    wait_idle(qtbot, win)
    new = win.session.workspace.state.view.geometry
    qtbot.waitUntil(lambda: sky.screen_geometry is new, timeout=20000)
    assert new is not old and sky._stage is None
    assert any("calcolo di prova fallito" in m.text for m in win.seen)
    assert sky.point_sets == ()  # il livello non si disegna, la vista è passata lo stesso


def test_t17_latest_base_wins(qtbot, scene):
    win = scene
    sky = win.sky
    catalog_gate, _ = win.gates
    catalog_gate.close()
    move_far(win)
    wait_idle(qtbot, win)
    assert catalog_gate.entered.wait(20)
    window = win.view_window()
    center = cw.SkyFrame.from_lonlat((PLEIADES[0] - 8.0) * u.deg, PLEIADES[1] * u.deg, "icrs")
    win.submit("view.set_center", {"position": sky_json(center), "window": window})
    wait_idle(qtbot, win)
    catalog_gate.open()
    final = win.session.workspace.state.view.geometry
    qtbot.waitUntil(lambda: sky.screen_geometry is final, timeout=30000)
    assert sky._stage is None
