# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Prestazioni del visualizzatore del cielo (41 §3.15, §12: TP1–TP7), sprint 4h. Esclusi dai test di default.

Si eseguono a mano sul Mac di riferimento, con lo schermo vero (OpenGL e rapporto dei pixel veri)::

    QT_QPA_PLATFORM=cocoa uv run pytest -m "perf or gl" tests/ui/test_perf.py -s

Con ``-m perf`` da solo girano solo le misure che non usano la GPU. Ogni misura scrive una riga sul terminale e in
``perf-report.json`` (cartella indicata da ``ASTROTWO_PERF_DIR``, altrimenti quella temporanea del test) con il Mac
(modello, processore, memoria, macOS), il valore, l'obiettivo e l'esito. Regola del proprietario (2026-10-15): un
obiettivo non raggiunto si misura e si riporta, mai abbassato; un test ``perf`` non blocca il commit (D41-4), un test
``gl`` che fallisce sì. Qui l'obiettivo è un ``assert`` per P1–P6; P7 è solo misurato.
"""

import json
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path

import astropy.units as u
import numpy as np
import pytest
from astropy.table import Table
from PySide6.QtCore import QElapsedTimer, QEvent, QPoint, QTimer

from astrotwo.core import coordinates_wcs as cw
from astrotwo.core import hips
from astrotwo.core.commands import quantity_json, sky_json
from astrotwo.ui import sky_viewer as sv
from tests.ui.test_catalog_sky import PLEIADES, open_file, wait_settled
from tests.ui.test_main_window import make_window, settings_path, wait_idle  # noqa: F401 - fixture
from tests.ui.test_sky_viewer import mouse, serve_png_survey

pytestmark = pytest.mark.perf


def need_gpu():
    """TP1 e TP2 usano OpenGL vero: saltati sulla piattaforma ``offscreen`` (un test ``perf`` non blocca mai)."""
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.platformName() == "offscreen":
        pytest.skip("serve la piattaforma cocoa: QT_QPA_PLATFORM=cocoa")

#: Obiettivi di 41 §3.15.
P1_MS, P2_BYTES, P3_MS, P4_MS, P5_S, P6_S = 16.7, 1 << 30, 100.0, 50.0, 3.0, 2.0
MILLION = 1_000_000


def _sysctl(name: str) -> str:
    try:
        return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "?"


def machine() -> dict:
    return {"model": _sysctl("hw.model"), "cpu": _sysctl("machdep.cpu.brand_string"),
            "memory_bytes": int(_sysctl("hw.memsize") or 0), "macos": platform.mac_ver()[0],
            "qt_platform": os.environ.get("QT_QPA_PLATFORM", ""), "python": platform.python_version()}


@pytest.fixture
def report(tmp_path):
    """Scrive la misura sul terminale e in ``perf-report.json``; restituisce l'esito rispetto all'obiettivo."""
    folder = Path(os.environ.get("ASTROTWO_PERF_DIR", tmp_path))
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "perf-report.json"

    def write(name: str, value: float, unit: str, target: float | None, **detail) -> bool:
        ok = None if target is None else value <= target
        entry = {"test": name, "value": round(value, 3), "unit": unit, "target": target, "ok": ok, **detail}
        rows = json.loads(path.read_text()) if path.exists() else {"machine": machine(), "results": []}
        rows["results"].append(entry)
        path.write_text(json.dumps(rows, indent=2))
        print(f"\nPERF {name}: {value:.2f} {unit} (obiettivo {target}) {'OK' if ok else 'NON RAGGIUNTO' if ok is False else ''}"
              f" {detail or ''}")
        return ok is not False

    return write


def rss_bytes() -> int:
    return int(subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())], capture_output=True, text=True).stdout) * 1024


def write_million(path: Path) -> str:
    """Catalogo sintetico di 1 milione di righe attorno alle Pleiadi (campo di 10°), con identificativo e due magnitudini."""
    rng = np.random.default_rng(20261024)
    n = MILLION
    table = Table({
        "Name": np.char.add("S", np.arange(n).astype("U7")),
        "RA_ICRS": PLEIADES[0] + rng.uniform(-5, 5, n) / np.cos(np.radians(PLEIADES[1])),
        "DE_ICRS": PLEIADES[1] + rng.uniform(-5, 5, n),
        "Gmag": rng.uniform(8, 20, n).astype(np.float32),
        "BPmag": rng.uniform(8, 21, n).astype(np.float32)})
    table["RA_ICRS"].unit = u.deg
    table["DE_ICRS"].unit = u.deg
    table["Name"].description = "identificativo"
    table["Name"].meta["ucd"] = "meta.id;meta.main"
    table["RA_ICRS"].meta["ucd"] = "pos.eq.ra;meta.main"
    table["DE_ICRS"].meta["ucd"] = "pos.eq.dec;meta.main"
    table.write(path, format="votable", tabledata_format="binary2", overwrite=True)
    return str(path)


# --- TP1, TP2 (GPU) ----------------------------------------------------------------------------------------


def test_tp1_frame_time_with_a_million_sources(qtbot, report):
    """P1: spostamento e zoom ≤ 16,7 ms per fotogramma al 95° percentile (immagine, sfondo, 1 milione di sorgenti)."""
    need_gpu()
    from astrotwo.ui.sky_renderer_gl import GlSkyRenderer

    renderer = GlSkyRenderer()
    qtbot.addWidget(renderer)
    renderer.resize(1600, 1000)
    renderer.show()
    qtbot.waitExposed(renderer)
    assert renderer.available
    ratio = renderer.devicePixelRatioF()
    w, h = round(1600 * ratio), round(1000 * ratio)
    rng = np.random.default_rng(1)
    for key, alpha in (("hips", 255), ("image", 200)):  # sfondo e immagine 4096 × 4096 già campionata sulla finestra
        plane = rng.integers(0, 255, (h, w, 4), dtype=np.uint8)
        plane[..., 3] = alpha
        renderer.upload_texture(plane, key)
    n = MILLION
    xy = np.column_stack([rng.uniform(0, w, n), rng.uniform(0, h, n)]).astype(np.float32)
    rgba = np.tile(np.array([[0.0, 0.62, 0.45, 1.0]], np.float32), (n, 1))
    renderer.upload_points((sv.PointSet("L3", np.arange(n), xy, rgba, np.full(n, 6.0, np.float32),
                                        np.zeros(n, np.float32), np.zeros(n, bool)),))
    renderer.set_layers((("texture", "hips", 1.0), ("texture", "image", 0.7), ("points", "L3", 1.0)))
    renderer.render_offscreen()  # primo disegno: caricamento sulla GPU, non si misura
    times = []
    for i in range(120):
        phase = i / 120 * 2 * np.pi
        k = 1.0 + 0.5 * np.sin(phase)  # zoom
        renderer.set_transform(k, 200.0 * np.cos(phase) * ratio, 120.0 * np.sin(phase) * ratio)  # spostamento
        start = time.perf_counter()
        renderer.render_offscreen()
        times.append((time.perf_counter() - start) * 1000)
    p95 = float(np.percentile(times, 95))
    # diagnosi (non obiettivo): solo il disegno con ``glFinish``, senza la lettura dei pixel, con e senza simboli
    drawn = {}
    renderer.makeCurrent()
    f = renderer.context().functions()
    for label, with_points in (("draw_p95_ms", True), ("draw_without_points_p95_ms", False)):
        if not with_points:
            renderer.set_layers((("texture", "hips", 1.0), ("texture", "image", 0.7)))
        samples = []
        for i in range(60):
            phase = i / 60 * 2 * np.pi
            renderer.set_transform(1.0 + 0.5 * np.sin(phase), 200.0 * np.cos(phase) * ratio, 120.0 * np.sin(phase) * ratio)
            start = time.perf_counter()
            renderer.paintGL()
            f.glFinish()
            samples.append((time.perf_counter() - start) * 1000)
        drawn[label] = round(float(np.percentile(samples, 95)), 2)
    renderer.doneCurrent()
    assert report("TP1 fotogramma (p95, con lettura dei pixel)", p95, "ms", P1_MS, median=round(float(np.median(times)), 2),
                  window=[w, h], points=n, **drawn)


@pytest.mark.timeout(900)
def test_tp2_memory_of_a_million_sources(qtbot, settings_path, cache, tmp_path, report):  # noqa: F811
    """P2: memoria aggiuntiva ≤ 1 GB per un catalogo di 1 milione di righe disegnato."""
    need_gpu()
    win = make_window(qtbot, settings_path, cache)
    win.sky.start_view()
    wait_idle(qtbot, win)
    window = win.view_window()
    win.submit("view.set_zoom", {"scale": quantity_json((20.0 * u.arcsec).to(u.deg)), "window": window})
    win.submit("view.set_center", {"position": sky_json(cw.SkyFrame.from_lonlat(*(PLEIADES * u.deg), "icrs")),
                                   "window": window})
    wait_settled(qtbot, win)
    path = write_million(tmp_path / "million.xml")
    before = rss_bytes()
    open_file(qtbot, win, "catalog.open_file", path)
    layer = win.session.workspace.state.of_kind("catalog")[0]
    # il file non dichiara il sistema (FRAME_UNKNOWN): si confermano le colonne come farebbe l'utente (42)
    win.submit("catalog.set_columns", {"layer": layer.id, "lon": "RA_ICRS", "lat": "DE_ICRS", "frame": "icrs"})
    wait_settled(qtbot, win)
    qtbot.waitUntil(lambda: sum(len(c.rows) for c in win.sky.catalog_cache.values()) == MILLION
                    and not win.sky._catalog_pending and win.sky._stage is None, timeout=300000)
    win.sky.renderer.render_offscreen()
    added = rss_bytes() - before
    drawn = sum(len(s.rows) for s in win.sky.point_sets)
    assert drawn == MILLION  # tutte le righe sono nei simboli caricati sulla GPU (anche fuori dalla finestra)
    win.close()
    assert report("TP2 memoria aggiuntiva", float(added), "byte", P2_BYTES, megabytes=round(added / 1e6), rows=MILLION,
                  drawn_in_window=drawn)


# --- TP3, TP4, TP6 (senza GPU) -----------------------------------------------------------------------------


@pytest.fixture
def win(qtbot, settings_path, cache, service, monkeypatch):  # noqa: F811
    monkeypatch.setattr(hips, "survey_coverage", lambda svc, **k: hips.service_coverage(svc, **k))
    win = make_window(qtbot, settings_path, cache)
    win.service = service
    win.survey_url = serve_png_survey(service)
    yield win
    win.close()


def test_tp3_main_thread_never_blocked(qtbot, win, tmp_path, monkeypatch, report):
    """P3: thread principale mai fermo più di 100 ms con tile lenti (2 s) e calcolo lento del catalogo."""
    from tests.core.test_commands_catalog_sky import write_catalog

    slow = threading.Event()
    original_fetch = hips.fetch_tile
    original_points = sv.catalog_points

    def slow_fetch(*args, **kwargs):
        if slow.is_set():
            time.sleep(2.0)
        return original_fetch(*args, **kwargs)

    def slow_points(*args, **kwargs):
        if slow.is_set():
            time.sleep(2.0)
        return original_points(*args, **kwargs)

    monkeypatch.setattr(hips, "fetch_tile", slow_fetch)
    monkeypatch.setattr(sv, "catalog_points", slow_points)
    win.submit("hips.set_survey", {"survey": win.survey_url})
    win.sky.start_view()
    wait_idle(qtbot, win)
    open_file(qtbot, win, "catalog.open_file", write_catalog(tmp_path / "c.xml"))
    wait_settled(qtbot, win)
    gaps = []
    clock = QElapsedTimer()
    probe = QTimer()
    probe.setInterval(10)
    probe.timeout.connect(lambda: gaps.append(clock.restart()))
    slow.set()
    clock.start()
    probe.start()
    window = win.view_window()
    center = sky_json(cw.SkyFrame.from_lonlat(*(PLEIADES * u.deg), "icrs"))
    win.submit("view.set_zoom", {"scale": quantity_json((60.0 * u.arcsec).to(u.deg)), "window": window})
    win.submit("view.set_center", {"position": center, "window": window})
    qtbot.wait(300)
    wait_idle(qtbot, win)
    qtbot.waitUntil(lambda: win.sky._in_flight == 0 and win.sky._stage is None, timeout=60000)
    probe.stop()
    slow.clear()
    assert len(gaps) > 50
    assert report("TP3 intervallo massimo della sonda", float(max(gaps[1:])), "ms", P3_MS, samples=len(gaps))


def test_tp4_cursor_readout(qtbot, win, report):
    """P4: coordinate sotto il mouse aggiornate entro 50 ms (sfondo HiPS; massimo su 50 movimenti)."""
    win.submit("hips.set_survey", {"survey": win.survey_url})
    win.sky.start_view()
    wait_idle(qtbot, win)
    qtbot.waitUntil(lambda: win.sky._in_flight == 0 and win.sky._stage is None, timeout=30000)
    sky = win.sky
    results = []
    sky.cursor_read.connect(results.append)
    times = []
    rng = np.random.default_rng(4)
    for _ in range(50):
        point = QPoint(int(rng.integers(20, sky.width() - 20)), int(rng.integers(20, sky.height() - 20)))
        count = len(results)
        start = time.perf_counter()
        mouse(sky, QEvent.Type.MouseMove, point)
        qtbot.waitUntil(lambda: len(results) > count, timeout=5000)
        times.append((time.perf_counter() - start) * 1000)
    assert report("TP4 coordinate sotto il mouse (massimo)", max(times), "ms", P4_MS, median=round(float(np.median(times)), 2))


def test_tp6_first_tiles_with_warm_cache(qtbot, settings_path, cache, service, monkeypatch, report):  # noqa: F811
    """P6: primi tile HiPS visibili in ≤ 2 s con la cache calda (il servizio non risponde più: solo la cache)."""
    monkeypatch.setattr(hips, "survey_coverage", lambda svc, **k: hips.service_coverage(svc, **k))
    url = serve_png_survey(service)
    first = make_window(qtbot, settings_path, cache)
    first.submit("hips.set_survey", {"survey": url})
    first.sky.start_view()
    wait_idle(qtbot, first)
    qtbot.waitUntil(lambda: first.sky._in_flight == 0 and first.sky._stage is None, timeout=30000)
    first.close()
    service.routes.clear()  # cache calda: nessun'altra richiesta di rete possibile
    win = make_window(qtbot, settings_path, cache)
    texture = []
    original = win.sky.renderer.upload_texture
    win.sky.renderer.upload_texture = lambda rgba, key="plane": (original(rgba, key), texture.append(
        (time.perf_counter(), bool(np.any(rgba[..., 3])))))
    start = time.perf_counter()
    win.submit("hips.set_survey", {"survey": url})
    win.sky.start_view()
    qtbot.waitUntil(lambda: any(seen for _, seen in texture), timeout=20000)
    seconds = next(t for t, seen in texture if seen) - start
    win.close()
    assert report("TP6 primi tile con cache calda", seconds, "s", P6_S)


# --- TP5, TP7 ----------------------------------------------------------------------------------------------

START_SCRIPT = """
import sys, time
t0 = time.perf_counter()
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from astrotwo.ui.main_window import MainWindow
t1 = time.perf_counter()
app = QApplication([])
window = MainWindow()
t2 = time.perf_counter()
window.sky.first_shown.connect(lambda: (print("READY %.3f %.3f %.3f" % (t1 - t0, t2 - t1, time.perf_counter() - t2),
                                            flush=True), app.quit()))
window.show()
QTimer.singleShot(30000, app.quit)
app.exec()
"""


def test_tp5_cold_start_without_network(tmp_path, report):
    """P5: finestra pronta (mostrata, vista dimensionata) in ≤ 3 s senza rete, in un processo nuovo e con home vuota.
    Il tempo è quello dalla partenza del processo alla riga ``READY`` (non conta la chiusura del processo)."""
    env = {**os.environ, "HOME": str(tmp_path), "ALL_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9",
           "HTTP_PROXY": "http://127.0.0.1:9", "NO_PROXY": ""}
    start = time.perf_counter()
    process = subprocess.Popen([sys.executable, "-c", START_SCRIPT], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, env=env)
    try:
        line = ""
        while not line.startswith("READY"):
            line = process.stdout.readline()
            assert line, process.stderr.read()[-2000:]
        seconds = time.perf_counter() - start
    finally:
        process.kill()
        process.wait(timeout=60)
    imports, window, shown = (float(x) for x in line.split()[1:])
    assert report("TP5 avvio a freddo (processo → finestra pronta)", seconds, "s", P5_S, imports=imports,
                  window_created=window, first_shown=shown)


def test_tp7_sky_to_pixel_million(report):
    """P7: tempo di ``sky_to_pixel`` del 10 su 1 milione di posizioni (solo misurato, nessun obiettivo)."""
    from astropy.coordinates import SkyCoord

    rng = np.random.default_rng(7)
    coords = cw.SkyFrame(SkyCoord(PLEIADES[0] * u.deg + rng.uniform(-5, 5, MILLION) * u.deg,
                                  PLEIADES[1] * u.deg + rng.uniform(-5, 5, MILLION) * u.deg, frame="icrs"))
    geometry = cw.make_view_wcs(cw.SkyFrame.from_lonlat(*(PLEIADES * u.deg), "icrs"), 20 * u.arcsec, (1000, 1600),
                                projection="TAN")
    start = time.perf_counter()
    cw.sky_to_pixel(geometry.base, coords, convention="numpy")
    seconds = time.perf_counter() - start
    report("TP7 sky_to_pixel su 1 milione di posizioni", seconds, "s", None, positions=MILLION)
