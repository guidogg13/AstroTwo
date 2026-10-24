# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Visualizzatore del cielo (41), sprint 4a-4f: sfondo HiPS (a colori o FITS), zoom, spostamento, lettura sotto il
mouse, griglia delle coordinate, indicatore del nord e barra di scala, immagine FITS base, cataloghi e clic, MOC,
pannello dei livelli.

Nessun numero mostrato nasce qui: la geometria è la ``ViewGeometry`` del 10 (dai comandi di vista del 05), i tile
e il loro campionamento sulla finestra vengono dal 12 (``view_sampling``, ``fetch_tile``, ``fill_view``).
Traslazione e scala dello schermo durante un gesto sono solo disegno (41 §3.4); a fine gesto (300 ms fermo, 05
§3.3) si registrano ``view.set_zoom`` e/o ``view.set_center`` con lo stato finale.

Sfondo HiPS: un solo survey; i tile JPEG/PNG si disegnano com'è, i tile FITS sono portati a colori da
``set_display`` dell'11 con i limiti scelti da ``hips.set_survey`` (campo ``display`` del livello, 41 §3.7). Sotto il
mouse una lettura passiva ``cursor.read`` (05) nel gruppo di thread dei tile, al più una in corso (41 §3.11). Dallo
sprint 4f lo sfondo si campiona anche sulla geometria di un'immagine FITS base, e sfondo e immagine sono due texture
composte nell'ordine dei livelli con la loro opacità (41 §3.5, §3.7).

MOC (41 §3.9, sprint 4f): celle e perimetro da ``healpix_grid`` del 16 e pixel della base con ``sky_to_pixel`` del
10, nel gruppo di thread dei tile, una volta per base; qui solo ``base_to_window`` e il disegno. Pannello dei livelli
(``LayerPanel``, 41 §3.5): ogni azione è un comando del 05, l'elenco si ricostruisce dallo stato.

Cataloghi (41 §3.8, sprint 4e): posizioni dal 13 (``display_positions`` con le colonne di moto proprio scelte,
altrimenti le posizioni della tabella, ``catalog_positions`` del 05) e pixel della base con ``sky_to_pixel`` del 10,
nel gruppo di thread dei tile, una volta per base; qui solo ``base_to_window`` (fattore e spostamento della
``ViewGeometry``) e il disegno. Un clic sceglie il simbolo più vicino (``cKDTree`` sullo schermo) e registra
``catalog.select``; la scheda della sorgente mostra il risultato del comando.

Griglia, nord/est e barra di scala (41 §3.10, §3.18): tutti i numeri sono del 10 (``compute_grid_lines``,
``choose_grid_spacing``, ``compass_and_scale_bar``, ``format_coordinates``), calcolati dai comandi di vista del 05 e
letti dallo stato; qui si portano solo i punti nello spazio dei pixel della finestra disegnata (``Overlay``).
"""

from __future__ import annotations

import dataclasses
import html
import os
import sys
import threading
import time
from collections.abc import Callable, Mapping

import astropy.units as u
import numpy as np
from PySide6.QtCore import QEvent, QObject, QPointF, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QSlider, QToolButton, QVBoxLayout, QWidget)

from astrotwo.core.commands import ResultMessage, quantity_json, sky_json, time_text
from astrotwo.core.hips import DEFAULT_TILE_MEMORY_BYTES, HiPSError, TileMemory
from astrotwo.ui.message_view import shown_text
from astrotwo.ui.sky_tools import (
    DEFAULT_TOOL_TEXTS, DistanceOptionsBar, DistanceTool, MeasureOverlay, SimbadPointerTool)

#: Fine del gesto: puntatore fermo per 300 ms (05 §3.3).
GESTURE_IDLE_MS = 300
#: Fattore di zoom per scatto della rotella del mouse (120 unità di ``angleDelta``): 2^(1/4), 4 scatti = raddoppio
#: (41 §3.4, scelta del proprietario del 2026-10-17); sul trackpad lo zoom è il pizzico, due dita spostano.
ZOOM_STEP = 2.0 ** 0.25
#: Eventi di rotella che macOS manda per uno scatto fisico (misurati sul Mac del proprietario il 2026-10-17: 34
#: eventi per 6 scatti, da 4 a 7 per scatto, tutti con ``angleDelta`` = ±120); ogni evento vale 1/6 di scatto.
WHEEL_EVENTS_PER_NOTCH = 6
#: Fattore dei pulsanti e delle scorciatoie di zoom (41 §3.4, decisione del proprietario del 2026-10-17).
BUTTON_ZOOM = 2.0
#: Campo della vista a cui porta un "Vai a" riuscito se la vista era più larga (stessa decisione).
GO_TO_FIELD = 1.0 * u.deg
#: Oltre questo campo il "Vai a" zooma; il campo ottenuto è solo vicino a 1° (la proiezione può cambiare).
GO_TO_FIELD_MAX = 1.25 * u.deg
#: Scala minima della vista (angolo per pixel della finestra), scelta del proprietario del 2026-10-17.
MIN_SCALE = 0.01 * u.arcsec
#: Larghezza angolare massima della finestra: scala massima = 360° / larghezza in pixel fisici (stessa scelta).
MAX_WIDTH_ANGLE = 360.0 * u.deg
#: Vista iniziale (scelta del proprietario del 2026-10-17): cielo intero centrato su ICRS (0°, 0°).
START_CENTER = {"lon": {"value": 0.0, "unit": "deg"}, "lat": {"value": 0.0, "unit": "deg"}, "frame": "icrs",
                "equinox": None, "obstime": None, "epoch": None,
                "epoch_reason": "epoca delle posizioni non nota (non assunta)"}
#: Testi dell'indicatore e della barra di scala nella lingua dell'interfaccia (la finestra principale li traduce, 40).
DEFAULT_OVERLAY_TEXTS = {"pole": "pole in field", "at_center": "at the center"}
#: Testi della scheda della sorgente nella lingua dell'interfaccia (la finestra principale li traduce, 40).
DEFAULT_CARD_TEXTS = {
    "row": "row %1", "epoch": "catalog epoch %1", "epoch_unknown": "catalog epoch not declared",
    "no_position": "no position: %1", "not_propagated": "drawn at the table positions (not propagated)",
    "propagated": "drawn at epoch %1 (proper motion; %2)", "not_drawn": "not drawn in this view",
    "catalog": "catalog %1", "retrieved": "retrieved %1",
}
#: Testi del pannello dei livelli nella lingua dell'interfaccia (la finestra principale li traduce, 40).
DEFAULT_PANEL_TEXTS = {
    "image": "image", "hips": "HiPS", "catalog": "catalog", "moc": "MOC", "measure": "measure",
    "visible": "Visible", "opacity": "Opacity", "up": "Move up", "down": "Move down", "remove": "Remove layer",
    "body": "body %1", "body_unknown": "body unknown (%1)", "forced": "overlay forced (force_body)",
    "retrieved": "retrieved %1", "epoch": "epoch %1", "epoch_unknown": "epoch unknown",
    "drawn": "%1 of %2 rows drawn", "propagated": "drawn at epoch %1", "not_propagated": "table positions (not propagated)",
    "order": "drawn at order %1", "by_excess": "drawn at order %1, by excess (MOC order %2)", "cells": "%1 cells",
    "not_drawn": "not drawn: %1",
}
#: Tolleranza minima del clic su un simbolo, pixel logici (41 §3.8, scelta minore 5).
CLICK_TOLERANCE = 4.0
#: Movimento oltre il quale una pressione del mouse diventa trascinamento invece di clic (pixel logici).
CLICK_SLOP = 3.0
#: Variabile d'ambiente che accende il log diagnostico degli ingressi (rotella, zoom, gesto) sul terminale.
DEBUG_INPUT_ENV = "ASTROTWO_DEBUG_INPUT"


def debug_input_enabled() -> bool:
    return os.environ.get(DEBUG_INPUT_ENV) == "1"


def debug_input(text: str) -> None:
    """Riga di diagnostica su stderr (solo con ``ASTROTWO_DEBUG_INPUT=1``): valori di Qt e stato dello zoom, mai
    chiavi o dati personali."""
    if debug_input_enabled():
        print(f"[astrotwo-input] {text}", file=sys.stderr, flush=True)


class _WheelSpy(QObject):
    """Filtro di eventi dell'applicazione, solo per la diagnostica: dice quale widget riceve ogni rotella."""

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Wheel and debug_input_enabled():
            debug_input(f"wheel visto da {type(obj).__name__}({obj.objectName()!r}) "
                        f"accettato_prima={event.isAccepted()}")
        return False


#: Thread del gruppo dei tile (41 §3.13, scelta minore 8).
TILE_THREADS = 6
#: Taglio del bordo dell'``AIT`` (41 §3.9, scelta di disegno): una cella con un lato più lungo di questo multiplo della
#: mediana dei lati della griglia, in pixel della base, è attraversata dal bordo della proiezione e non si disegna.
MOC_CUT = 8.0


@dataclasses.dataclass(frozen=True)
class GridLabel:
    """Etichetta di una linea della griglia: punto nello spazio dei pixel della finestra disegnata (origine in alto a
    sinistra, pixel fisici); ``side`` dice dove sta il testo rispetto al punto (``top``: sotto, centrato; ``left``: a
    destra)."""

    x: float
    y: float
    text: str
    side: str


@dataclasses.dataclass(frozen=True)
class Overlay:
    """Ciò che sta sopra il cielo (41 §3.10, §3.18), già in pixel di disegno; nessun numero nasce qui.

    ``grid_lines``: linee spezzate ``(N, 2)`` ``float32`` (solo disegno, DC6) nello spazio dei pixel della finestra
    disegnata, che segue lo spostamento e lo zoom del gesto. Indicatore e barra stanno invece fissi nell'angolo:
    ``north``/``east`` sono i vettori unitari del 10 in pixel della finestra (y verso l'alto), ``bar_pixels`` la
    lunghezza della barra in pixel fisici. ``None`` = elemento spento.
    """

    grid_lines: tuple[np.ndarray, ...] = ()
    grid_labels: tuple[GridLabel, ...] = ()
    compass_shown: bool = False
    north: tuple[float, float] | None = None
    east: tuple[float, float] | None = None
    pole_text: str | None = None
    bar_pixels: float | None = None
    bar_text: str | None = None


def build_overlay(view, texts: Mapping[str, str] = DEFAULT_OVERLAY_TEXTS) -> Overlay | None:
    """Dati da disegnare dallo stato della vista: linee e passi della griglia (10), etichette con
    ``format_coordinates`` del 10 (precisione = passo), nord/est e barra di ``compass_and_scale_bar`` del 10."""
    from astrotwo.core.coordinates_wcs import format_coordinates

    g = view.geometry
    if g is None:
        return None
    rows, cols = g.shape
    lines: list[np.ndarray] = []
    labels: list[GridLabel] = []
    grid = view.grid
    for line in () if grid is None else grid.lines:
        points = []
        for xs, ys in line.segments:  # pixel (numpy) della regione visibile → base → finestra → spazio del disegno
            wx, wy = g.base_to_window(np.asarray(xs) + g.visible_origin[0], np.asarray(ys) + g.visible_origin[1])
            q = np.column_stack([wx + 0.5, rows - wy - 0.5])
            lines.append(q.astype(np.float32))
            points.append(q)
        if not points:
            continue
        q = np.concatenate(points)
        inside = q[(q[:, 0] >= 0) & (q[:, 0] <= cols) & (q[:, 1] >= 0) & (q[:, 1] <= rows)]
        if not len(inside):
            continue
        meridian = line.kind == "meridian"
        # meridiani: etichetta vicino al bordo alto; paralleli: vicino al bordo sinistro (l'angolo in basso è
        # dell'indicatore e della barra, quello in alto a destra dei pulsanti di zoom)
        x, y = inside[np.argmin(inside[:, 1] if meridian else inside[:, 0])]
        text = format_coordinates(values=line.value, frame=grid.frame_name, axis="lon" if meridian else "lat",
                                  style=view.coordinate_format,
                                  precision=grid.lon_spacing if meridian else grid.lat_spacing)
        labels.append(GridLabel(float(x), float(y), (text.lon if meridian else text.lat)[0], "top" if meridian else "left"))
    c = view.compass
    compass_shown = c is not None and view.compass_visible
    bar_shown = c is not None and view.scale_bar_visible
    return Overlay(
        grid_lines=tuple(lines), grid_labels=tuple(labels), compass_shown=compass_shown,
        north=c.north if compass_shown else None, east=c.east if compass_shown else None,
        pole_text=texts["pole"] if compass_shown and c.north is None else None,
        bar_pixels=c.bar_pixels if bar_shown else None,
        bar_text=(c.label + (" " + texts["at_center"] if c.local_only else "")) if bar_shown else None)


@dataclasses.dataclass(frozen=True, eq=False)
class CatalogPoints:
    """Posizioni di un catalogo nei pixel della base (41 §3.8), calcolate nel gruppo di thread dei tile.

    ``rows``: righe della tabella disegnate; ``base_xy``: pixel della base (convenzione numpy, ``float64``) da
    ``sky_to_pixel`` del 10; ``rgba``/``size``/``shape``: stile per riga da ``set_plot_rules`` del 13 (colore in
    [0, 1], dimensione in pixel logici, indice nella lista delle forme del 13). ``epoch`` è l'epoca delle posizioni
    disegnate (13), ``propagated`` dice se viene da ``display_positions``; ``seconds`` il tempo del calcolo."""

    key: tuple
    layer: str
    rows: np.ndarray
    base_xy: np.ndarray
    rgba: np.ndarray
    size: np.ndarray
    shape: np.ndarray
    epoch: object = None
    propagated: bool = False
    epoch_source: str | None = None
    warnings: tuple[ResultMessage, ...] = ()
    seconds: float = 0.0


@dataclasses.dataclass(frozen=True, eq=False)
class PointSet:
    """Simboli di un catalogo pronti per il renderer: ``xy`` nello spazio dei pixel della finestra disegnata
    (origine in alto a sinistra, pixel fisici, ``float32`` solo per il disegno, DC6), come le linee della griglia."""

    layer: str
    rows: np.ndarray
    xy: np.ndarray
    rgba: np.ndarray
    size: np.ndarray
    shape: np.ndarray
    selected: np.ndarray


@dataclasses.dataclass(frozen=True, eq=False)
class MocShapes:
    """Celle e perimetro di un MOC nei pixel della base (41 §3.9), calcolati nel gruppo di thread dei tile.

    ``triangles``: vertici dei triangoli (ventaglio per cella) ``(3 × T, 2)``; ``lines``: estremi dei segmenti del
    perimetro ``(2 × L, 2)``; pixel della base (convenzione numpy, ``float64``) da ``sky_to_pixel`` del 10 sui punti di
    ``healpix_grid`` del 16. ``order`` è l'ordine disegnato, ``moc_order`` quello del MOC (per eccesso se minore)."""

    key: tuple
    layer: str
    order: int
    moc_order: int
    cells: int
    drawn_cells: int
    triangles: np.ndarray
    lines: np.ndarray
    description: str = ""
    seconds: float = 0.0


@dataclasses.dataclass(frozen=True, eq=False)
class PolygonSet:
    """MOC pronto per il renderer: ``triangles`` e ``lines`` nello spazio dei pixel della finestra disegnata (come i
    simboli, ``float32`` solo per il disegno); colori RGBA in [0, 1] con l'opacità del livello già applicata."""

    layer: str
    triangles: np.ndarray
    fill: tuple[float, float, float, float]
    lines: np.ndarray
    line: tuple[float, float, float, float]


def _hex_rgba(colors: np.ndarray) -> np.ndarray:
    """Colori ``#RRGGBB`` del 13 → RGBA in [0, 1] per il disegno."""
    out = np.ones((len(colors), 4), dtype=np.float32)
    for k, text in enumerate(colors):
        out[k, :3] = [int(text[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    return out


def base_key(geometry) -> tuple:
    """Identità della base (41 §3.2): l'immagine (WCS del file) o la base creata dal 10 (tipo, punto di tangenza,
    scala). Due geometrie con la stessa chiave hanno gli stessi pixel della base."""
    w = geometry.base
    if not geometry.base_created:
        return ("image", id(w))
    return ("created", tuple(w.wcs.ctype), tuple(float(v) for v in w.wcs.crval),
            tuple(float(v) for v in w.wcs.cdelt), tuple(float(v) for v in w.wcs.crpix))


def catalog_key(layer, image) -> tuple:
    """Ciò da cui dipendono le posizioni disegnate di un catalogo: tabella, stile del 13, colonne di moto proprio
    e immagine base (epoca di visualizzazione, D10-2)."""
    columns = tuple(sorted((layer.columns or {}).items()))
    return (layer.id, id(layer.data), id(layer.derived.get("plot_style")), columns,
            None if image is None else id(image.data))


def _epoch_warnings(table, image, layer_name: str) -> tuple[ResultMessage, ...]:
    """Avviso di epoche diverse (D10-2, 41 §3.8) quando le posizioni non sono propagate: epoca del catalogo e
    dell'immagine base entrambe dichiarate e diverse, o epoca del catalogo non dichiarata con un'immagine datata."""
    wcs = None if image is None else image.data.wcs
    image_epoch = None if wcs is None else wcs.image_epoch
    if image_epoch is None:
        return ()
    epoch = table.positions.epoch
    shown = time_text(image_epoch)
    if epoch is None:
        return (ResultMessage("CATALOG_EPOCH_UNKNOWN", f"{layer_name}: epoca del catalogo non dichiarata, immagine "
                              f"all'epoca {shown}; posizioni della tabella non propagate (moto proprio con "
                              "catalog.set_columns)"),)
    from astrotwo.core.coordinates_wcs import SkyFrame

    catalog_epoch = SkyFrame.from_lonlat(0 * u.deg, 0 * u.deg, "icrs", epoch=epoch).epoch  # lettura del 10
    if (catalog_epoch - image_epoch).to_value(u.s) == 0.0:
        return ()
    return (ResultMessage("CATALOG_EPOCH_DIFFERS", f"{layer_name}: catalogo all'epoca {time_text(catalog_epoch)}, "
                          f"immagine all'epoca {shown}; posizioni della tabella non propagate (moto proprio con "
                          "catalog.set_columns)"),)


def catalog_points(key: tuple, layer, geometry, image) -> CatalogPoints:
    """Posizioni di un catalogo nei pixel della base (41 §3.8): con le colonne di moto proprio scelte
    (``catalog.set_columns``) ``display_positions`` del 13 all'epoca di visualizzazione (D10-2), altrimenti le
    posizioni della tabella con l'epoca del catalogo (scelta minore 3); poi ``sky_to_pixel`` del 10 sulla base. Si
    disegnano le righe con posizione, stile del 13 e pixel finiti dentro la proiezione."""
    from astrotwo.core.catalogs import PLOT_SHAPES, display_positions
    from astrotwo.core.commands import catalog_positions
    from astrotwo.core.coordinates_wcs import sky_to_pixel

    start = time.perf_counter()
    table = layer.data
    style = layer.derived.get("plot_style")
    columns = layer.columns or {}
    empty = CatalogPoints(key, layer.id, np.zeros(0, dtype=np.int64), np.zeros((0, 2)), np.zeros((0, 4), np.float32),
                          np.zeros(0, np.float32), np.zeros(0, np.float32))
    if table.positions is None or style is None:
        return empty
    if columns.get("pm_ra") and columns.get("pm_dec"):
        shown = display_positions(table, None if image is None else image.data, pm_ra=columns["pm_ra"],
                                  pm_dec=columns["pm_dec"], pm_ra_includes_cosdec=columns.get("pm_ra_includes_cosdec"),
                                  parallax=columns.get("parallax"), radial_velocity=columns.get("radial_velocity"))
        coords, valid = shown.coords, shown.drawable
        epoch, propagated, source, warnings_ = shown.epoch, True, shown.epoch_source, ()
    else:
        coords, valid = catalog_positions(table)
        epoch, propagated, source = table.positions.epoch, False, None
        warnings_ = _epoch_warnings(table, image, layer.name)
    if coords is None:
        return dataclasses.replace(empty, epoch=epoch, propagated=propagated, epoch_source=source, warnings=warnings_)
    rows = np.flatnonzero(valid)
    pixels = sky_to_pixel(geometry.base, coords, convention="numpy")
    bx, by = np.asarray(pixels.pixels.x, dtype=np.float64), np.asarray(pixels.pixels.y, dtype=np.float64)
    # Fuori dalla proiezione = pixel non finito; fuori dal riquadro dell'immagine base si disegna (lo sfondo HiPS si
    # vede attorno all'immagine, sprint 4f), quindi ``out_of_field`` del 10 non basta da solo.
    keep = np.isfinite(bx) & np.isfinite(by) & np.asarray(style.drawn, dtype=bool)[rows]
    rows, bx, by = rows[keep], bx[keep], by[keep]
    shapes = {name: float(k) for k, name in enumerate(PLOT_SHAPES)}
    return CatalogPoints(
        key, layer.id, rows, np.column_stack([bx, by]), _hex_rgba(style.color[rows]),
        np.asarray(style.size[rows], dtype=np.float32), np.array([shapes[x] for x in style.shape[rows]], np.float32),
        epoch=epoch, propagated=propagated, epoch_source=source, warnings=warnings_,
        seconds=time.perf_counter() - start)


def moc_key(layer) -> tuple:
    """Ciò da cui dipende il disegno di un MOC: livello e oggetto del 16 (lo stile si applica dopo, nel disegno)."""
    return (layer.id, id(layer.data))


def moc_step(order: int) -> int:
    """Punti per lato del contorno (``step`` del 16, scelta di disegno, 41 §3.9): 2^(6 − k) sotto l'ordine 6."""
    return 2 ** (6 - order) if order < 6 else 1


def moc_shapes(key: tuple, layer, geometry) -> MocShapes:
    """Celle e perimetro di un MOC sulla base (41 §3.9): ``healpix_grid`` del 16 all'ordine del MOC o, se il 16
    risponde ``GRID_TOO_LARGE``, all'ordine sotto, finché passa (si parte dall'ordine che la frazione di cielo del 16
    rende possibile); poi ``sky_to_pixel`` del 10. Gli errori del 16 (MOC temporale, di un altro corpo) passano."""
    from astrotwo.core.coordinates_wcs import SkyFrame, sky_to_pixel
    from astrotwo.core.moc import GRID_MAX_CELLS, MocError, healpix_grid

    start = time.perf_counter()
    moc = layer.data
    top = moc.space_order
    if top is None:  # MOC solo temporale: il 16 lo dice (MOC_TYPE_MISMATCH)
        healpix_grid(0, within=moc)
    order = top
    fraction = moc.sky_fraction or 0.0
    while order > 0 and fraction * 12 * 4 ** order > GRID_MAX_CELLS:  # meno celle di così non ce ne sono
        order -= 1
    while True:
        try:
            grid = healpix_grid(order, within=moc, step=moc_step(order))
            break
        except MocError as exc:
            if exc.code != "GRID_TOO_LARGE" or order == 0:
                raise
            order -= 1
    cells, n = grid.lon.shape
    empty = np.zeros((0, 2))
    if not cells:
        return MocShapes(key, layer.id, order, top, 0, 0, empty, empty, grid.description)
    coords = SkyFrame.from_lonlat(grid.lon.ravel() * u.deg, grid.lat.ravel() * u.deg, grid.frame.lower())
    pixels = sky_to_pixel(geometry.base, coords, convention="numpy")
    xy = np.column_stack([np.asarray(pixels.pixels.x, dtype=np.float64),
                          np.asarray(pixels.pixels.y, dtype=np.float64)]).reshape(cells, n, 2)
    ok = np.all(np.isfinite(xy), axis=(1, 2))  # fuori dalla proiezione = non finito (anche oltre il riquadro
    # dell'immagine base la cella si disegna: lo sfondo si vede attorno, come per i cataloghi)
    side = np.hypot(*(np.roll(xy, -1, axis=1) - xy).transpose(2, 0, 1))  # (celle, n)
    if ok.any():
        ok &= side.max(axis=1) <= MOC_CUT * float(np.median(side[ok]))  # celle tagliate dal bordo dell'AIT
    fan = np.stack([np.zeros(n - 2, dtype=np.int64), np.arange(1, n - 1), np.arange(2, n)], axis=1).ravel()
    triangles = xy[ok][:, fan].reshape(-1, 2)
    step = n // 4
    a = (np.arange(4)[:, None] * step + np.arange(step)[None, :])  # (4 lati, step) primo punto di ogni segmento
    b = (a + 1) % n
    cell, j = np.nonzero(grid.boundary & ok[:, None])
    lines = np.stack([xy[cell[:, None], a[j]], xy[cell[:, None], b[j]]], axis=2).reshape(-1, 2)
    return MocShapes(key, layer.id, order, top, cells, int(ok.sum()), triangles, lines, grid.description,
                     time.perf_counter() - start)


class SkyRenderer:
    """Interfaccia di disegno (41 §3.13, §7): piani come texture, simboli, MOC, sovrapposizioni e trasformazione.

    ``upload_texture``: immagine RGBA a 8 bit della finestra, riga 0 = riga in alto sullo schermo, una per piano
    (``key`` = livello; sprint 4f). ``set_layers``: ordine di disegno dal basso, ``(tipo, livello, opacità)`` con tipo
    ``texture``, ``points`` o ``polygons``; senza elenco si disegnano piani e poi simboli.
    ``set_transform``: scala ``k`` e traslazione ``(tx, ty)`` in pixel fisici: il pixel ``q`` dell'immagine va
    sullo schermo in ``k * q + t`` (solo disegno, 41 §3.4). ``set_night``: modalità notte rossa (luminosità in
    scala di rossi, trasformazione di disegno).
    """

    def widget(self) -> QWidget:
        raise NotImplementedError

    def upload_texture(self, rgba: np.ndarray, key: str = "plane") -> None:
        raise NotImplementedError

    def drop_texture(self, key: str) -> None:
        """Toglie il piano ``key`` (livello rimosso o sostituito)."""
        raise NotImplementedError

    def set_layers(self, items: tuple[tuple[str, str, float], ...]) -> None:
        raise NotImplementedError

    def upload_polygons(self, sets: tuple[PolygonSet, ...]) -> None:
        """MOC (41 §3.9): triangoli del riempimento e segmenti del perimetro, uno per livello."""
        raise NotImplementedError

    def drawn_polygons(self) -> list[tuple[str, np.ndarray, np.ndarray]]:
        """Per i test (41 §7): ``(livello, vertici dei triangoli, estremi dei segmenti)`` sullo schermo in pixel
        fisici, con la trasformazione corrente."""
        raise NotImplementedError

    def set_transform(self, k: float, tx: float, ty: float) -> None:
        raise NotImplementedError

    def set_night(self, night: bool) -> None:
        raise NotImplementedError

    def set_overlay(self, overlay: Overlay | None) -> None:
        """Griglia, indicatore del nord e barra di scala (41 §3.10, §3.18). Durante un gesto (trasformazione diversa
        dall'identità) indicatore e barra sono in grigio: restano quelli dell'ultimo comando di vista."""
        raise NotImplementedError

    def upload_points(self, sets: tuple[PointSet, ...]) -> None:
        """Simboli dei cataloghi (41 §3.8), dal basso verso l'alto; le sorgenti selezionate hanno un anello."""
        raise NotImplementedError

    def drawn_positions(self) -> list[tuple[str, np.ndarray, np.ndarray]]:
        """Per i test (41 §7): ``(livello, righe, posizioni sullo schermo in pixel fisici)`` dei simboli disegnati,
        con la trasformazione corrente."""
        raise NotImplementedError

    def render_offscreen(self):
        """Il disegno corrente come ``QImage`` in pixel fisici, per il PNG (41 §3.14) e per i test (``gl``)."""
        raise NotImplementedError


def _default_renderer() -> SkyRenderer:
    from astrotwo.ui.sky_renderer_gl import GlSkyRenderer

    return GlSkyRenderer()


#: Costruttore del renderer (i test lo sostituiscono con uno in memoria: la piattaforma ``offscreen`` non ha GPU).
DEFAULT_RENDERER: Callable[[], SkyRenderer] = _default_renderer


class _LockedTileMemory(TileMemory):
    """``TileMemory`` del 12 condivisa dai thread dei tile: stesse regole, accesso sotto un lucchetto."""

    def __init__(self, limit_bytes: int = DEFAULT_TILE_MEMORY_BYTES) -> None:
        super().__init__(limit_bytes)
        self._lock = threading.Lock()

    def get(self, url: str):
        with self._lock:
            return super().get(url)

    def put(self, tile) -> None:
        with self._lock:
            super().put(tile)


class _Bridge(QObject):
    """Risultati dei thread dei tile verso il thread principale (segnali di Qt, connessione in coda)."""

    sampled = Signal(int, object)  # generazione, ViewSampling
    tile = Signal(int, object)  # generazione, ViewTile
    failed = Signal(int, str, str)  # generazione, codice, testo
    done = Signal(int)  # generazione (una richiesta di tile finita, riuscita o no)
    cursor = Signal(object)  # CommandResult di una lettura sotto il mouse
    simbad = Signal(object)  # CommandResult di simbad.pointer (puntatore Simbad, 41 §3.12)
    catalog = Signal(object, object)  # chiave, CatalogPoints o ResultMessage (errore del modulo)
    moc = Signal(object, object)  # chiave, MocShapes o ResultMessage (errore del modulo)


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], None]) -> None:
        super().__init__()
        self.fn = fn

    def run(self) -> None:
        self.fn()


class TilePool:
    """Gruppo di thread dei tile (41 §3.13): campionamento della vista e richieste dei tile, con annullamento
    cooperativo: ogni lavoro porta la sua generazione e, se nel frattempo la finestra è cambiata, si scarta."""

    def __init__(self, cache=None) -> None:
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(TILE_THREADS)
        self.cache = cache
        self.memory = _LockedTileMemory()
        self.bridge = _Bridge()
        self.generation = 0

    def current(self, generation: int) -> bool:
        return generation == self.generation

    def sample(self, generation: int, service, geometry, coverage) -> None:
        from astrotwo.core.hips import view_sampling

        def run() -> None:
            if not self.current(generation):
                return
            try:
                sampling = view_sampling(service, geometry, coverage=coverage)
            except Exception as exc:  # noqa: BLE001 - errori del 12/10 (es. frame dell'immagine base): un messaggio
                self.bridge.failed.emit(generation, str(getattr(exc, "code", type(exc).__name__)), str(exc))
                return
            self.bridge.sampled.emit(generation, sampling)

        self.pool.start(_Task(run))

    def fetch(self, generation: int, service, sampling, index: int, display: Mapping | None = None) -> None:
        from astrotwo.core.hips import fetch_tile, fill_view

        def run() -> None:
            try:
                if not self.current(generation):
                    return  # richiesta superata: annullata prima della rete
                try:
                    tile = fetch_tile(service, sampling.order, index, plane=sampling.plane, cache=self.cache,
                                      memory=self.memory)
                    if self.current(generation):
                        self.bridge.tile.emit(generation, colorize(fill_view(sampling, tile), display))
                except Exception as exc:  # noqa: BLE001 - errori del 12/04: zona vuota e un messaggio
                    code = getattr(exc, "code", type(exc).__name__)
                    self.bridge.failed.emit(generation, str(code), str(exc))
            finally:
                self.bridge.done.emit(generation)

        self.pool.start(_Task(run))

    def read(self, passive: Callable[..., object], name: str, params: Mapping, signal: str = "cursor") -> None:
        """Lettura passiva (``cursor.read``, 41 §3.11) nel gruppo di thread dei tile; il risultato torna al thread
        principale con ``bridge.cursor`` (un errore imprevisto diventa un risultato in errore, mai un'eccezione)."""
        from astrotwo.core.commands import CommandResult

        def run() -> None:
            try:
                result = passive(name, params, "mouse")
            except Exception as exc:  # noqa: BLE001 - il gruppo di thread non si ferma mai
                result = CommandResult("error", error=ResultMessage("UI_COMMAND_FAILED", f"{type(exc).__name__}: {exc}"))
            getattr(self.bridge, signal).emit(result)

        self.pool.start(_Task(run))

    def catalog(self, key: tuple, layer, geometry, image) -> None:
        """Posizioni di un catalogo sulla base (41 §3.8) nel gruppo di thread dei tile; l'errore di un modulo diventa
        un messaggio."""

        def run() -> None:
            try:
                result = catalog_points(key, layer, geometry, image)
            except Exception as exc:  # noqa: BLE001 - errori del 10/13: catalogo non disegnato e un messaggio
                code = getattr(exc, "code", type(exc).__name__)
                result = ResultMessage(str(code), f"{layer.name}: {getattr(exc, 'message', None) or exc}")
            self.bridge.catalog.emit(key, result)

        self.pool.start(_Task(run))

    def moc(self, key: tuple, layer, geometry) -> None:
        """Celle e perimetro di un MOC sulla base (41 §3.9) nel gruppo di thread dei tile; l'errore di un modulo
        diventa un messaggio."""

        def run() -> None:
            try:
                result = moc_shapes(key, layer, geometry)
            except Exception as exc:  # noqa: BLE001 - errori del 10/16: MOC non disegnato e un messaggio
                code = getattr(exc, "code", type(exc).__name__)
                result = ResultMessage(str(code), f"{layer.name}: {getattr(exc, 'message', None) or exc}")
            self.bridge.moc.emit(key, result)

        self.pool.start(_Task(run))

    def wait(self, msecs: int = 30000) -> bool:
        return self.pool.waitForDone(msecs)


def colorize(view_tile, display: Mapping | None):
    """Tile FITS → colori RGBA con ``set_display`` dell'11 (41 §3.7): nessun calcolo qui, solo la chiamata al modulo.
    I tile JPEG/PNG hanno già i colori. Pixel non finiti = trasparenti (``set_display``)."""
    if view_tile.format != "fits":
        return view_tile
    from astrotwo.core.images_fits import set_display

    if display is None or display.get("vmin") is None or display.get("vmax") is None:
        raise HiPSError("HIPS_DISPLAY_UNKNOWN", "limiti di colore del survey non noti: i tile FITS non si disegnano",
                        params={"reason": "no_limits"})
    plane = set_display(view_tile.values, display["vmin"], display["vmax"], display.get("gamma", 1.0),
                        display.get("palette", "gray"), display.get("stretch", "linear"))
    return dataclasses.replace(view_tile, values=plane.rgba, format="rgba")


def format_field(field: Mapping | None) -> str:
    """Campo della vista (``field_of_view`` dei comandi di vista del 05, dal 10) con cifre fisse (scelta del
    proprietario del 2026-10-17): in gradi con 2 decimali da 1° in su, in primi sotto 1°, in secondi sotto 1′."""
    if field is None:
        return ""
    q = field["value"] * u.Unit(field["unit"], format="fits")
    for unit, symbol in ((u.deg, "°"), (u.arcmin, "′")):
        if q.to_value(unit) >= 1.0:
            return f"{q.to_value(unit):.2f}{symbol}"
    return f"{q.to_value(u.arcsec):.2f}″"


def sample_image(geometry, image) -> np.ndarray:
    """Colori (RGBA, righe nell'ordine della finestra: riga 0 = sud) dell'immagine FITS base per ogni pixel della
    finestra: pixel più vicino della base (le posizioni vengono da ``window_to_base`` del 10). Disegno: nessun numero
    mostrato nasce da qui (41 §3.4). Con le immagini a due livelli (11) il piano è l'anteprima e l'indice si divide per
    il passo; fuori dall'immagine, trasparente. Visibilità e opacità del livello le applica il renderer (sprint 4f)."""
    rows, cols = geometry.shape
    canvas = np.zeros((rows, cols, 4), dtype=np.uint8)
    plane = image.derived.get("plane")
    if plane is None:
        return canvas
    rgba = plane.rgba
    step = image.data.preview_step or 1
    bx, by = geometry.window_to_base(np.arange(cols), np.arange(rows))
    ix = np.floor((bx + 0.5) / step).astype(np.int64)
    iy = np.floor((by + 0.5) / step).astype(np.int64)
    ok_x = (ix >= 0) & (ix < rgba.shape[1])
    ok_y = (iy >= 0) & (iy < rgba.shape[0])
    if ok_x.any() and ok_y.any():
        canvas[np.ix_(ok_y, ok_x)] = rgba[np.ix_(iy[ok_y], ix[ok_x])]
    return canvas


class SkyViewer(QWidget):
    """Widget del cielo (41 §7): tiene la ``ViewGeometry`` corrente, traduce i gesti in comandi, disegna i tile.

    ``submit(name, params, source)`` mette in coda un comando del 05 (la coda del 40); ``passive(name, params,
    source)`` esegue subito un comando passivo (D05-1) e ne restituisce il risultato (chiamata da un thread dei tile).
    """

    message = Signal(object)  # ResultMessage per il pannello Messaggi (un solo messaggio per survey e codice)
    tiles_changed = Signal(int)  # richieste di tile in corso, per la barra di stato
    view_changed = Signal()  # nuova geometria o nuovo survey disegnati (scritta della barra)
    first_shown = Signal()  # la finestra ha la sua dimensione vera: si può chiedere la vista iniziale
    cursor_read = Signal(object)  # CommandResult di cursor.read, o None se il mouse esce dal cielo
    layers_drawn = Signal()  # posizioni di un catalogo o celle di un MOC pronte (dettagli del pannello dei livelli)

    def __init__(self, submit: Callable[..., int], cache=None, renderer: SkyRenderer | None = None,
                 parent=None, passive: Callable[..., object] | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("skyArea")
        self.setMinimumSize(320, 240)
        self.setMouseTracking(True)  # coordinate sotto il mouse anche senza premere (41 §3.11)
        self.submit = submit
        self.passive = passive
        self.renderer = renderer if renderer is not None else DEFAULT_RENDERER()
        child = self.renderer.widget()
        child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(child)
        self.tool = "none"  # strumento attivo (ui.set_tool del 05): none, distance, simbad_pointer
        self.tool_texts: Mapping[str, str] = DEFAULT_TOOL_TEXTS  # tradotti dalla finestra principale (40)
        self._loading_options = False
        self.measure_overlay = MeasureOverlay(self)  # misure disegnate sopra il cielo (41 §3.19)
        self.zoom_in_button = self._zoom_button("zoomIn", +1)
        self.zoom_out_button = self._zoom_button("zoomOut", -1)
        self.tiles = TilePool(cache)
        self.tiles.bridge.sampled.connect(self._sampled)
        self.tiles.bridge.tile.connect(self._tile)
        self.tiles.bridge.failed.connect(self._failed)
        self.tiles.bridge.done.connect(self._tile_done)
        self.tiles.bridge.cursor.connect(self._cursor_done)
        self.tiles.bridge.simbad.connect(lambda result: self.simbad_tool.done(result))
        self.tiles.bridge.catalog.connect(self._catalog_done)
        self.tiles.bridge.moc.connect(self._moc_done)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)  # Esc chiude la scheda della sorgente
        self.card_texts: Mapping[str, str] = DEFAULT_CARD_TEXTS  # tradotti dalla finestra principale (40)
        self.card = QLabel(self)
        self.card.setObjectName("sourceCard")
        self.card.setTextFormat(Qt.TextFormat.RichText)
        self.card.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.card.hide()
        self.distance_tool = DistanceTool(self)
        self.simbad_tool = SimbadPointerTool(self)
        self.options_bar = DistanceOptionsBar(self)
        self.options_bar.show_options(self.distance_tool.options, False)
        self._card: tuple[str, int, Mapping] | None = None  # livello, riga, scheda di catalog.select (05)
        self._night = False
        self.screen_geometry = None  # geometria del disegno sullo schermo (la sua finestra è lo spazio dei punti)
        self.catalog_layers: tuple = ()
        self.base_image = None  # livello dell'immagine base (epoca di visualizzazione, D10-2)
        self.catalog_cache: dict[tuple, CatalogPoints] = {}
        self._catalog_pending: set[tuple] = set()
        self.point_sets: tuple[PointSet, ...] = ()
        self.layers: tuple = ()  # livelli dello stato, nell'ordine di disegno (il primo in basso)
        self.moc_layers: tuple = ()
        self.moc_cache: dict[tuple, MocShapes] = {}
        self._moc_pending: set[tuple] = set()
        self.moc_errors: dict[str, ResultMessage] = {}  # livello → perché il MOC non si disegna
        self.polygon_sets: tuple[PolygonSet, ...] = ()
        self.image_layer: str | None = None  # livello dell'immagine il cui piano è nel renderer
        self.image_canvas: np.ndarray | None = None
        self._image_next: np.ndarray | None = None  # piano dell'immagine per la geometria in arrivo (con lo sfondo)
        self._trees: dict[int, object] = {}
        self._press: QPointF | None = None
        self._dragging = False
        self._cursor_busy = False
        self._cursor_next: QPointF | None = None  # ultima posizione arrivata mentre una lettura era in corso
        self._cursor_inside = False
        self.geometry = None  # ViewGeometry del 10 disegnata (o in preparazione)
        self.view = None  # ViewState corrente
        self.service = None
        self.survey_layer: str | None = None
        self.image_key: tuple | None = None  # (livello, piano di colori) dell'immagine disegnata
        self.overlay_texts: Mapping[str, str] = DEFAULT_OVERLAY_TEXTS  # tradotti dalla finestra principale (40)
        self.overlay: Overlay | None = None
        self.display: Mapping | None = None  # limiti, palette e funzione di trasferimento del survey FITS (livello)
        self.field: Mapping | None = None  # field_of_view dell'ultimo comando di vista
        self.sampling = None
        self.canvas: np.ndarray | None = None  # RGBA, righe nell'ordine della finestra (riga 0 = sud, y del 10)
        self.k, self.tx, self.ty = 1.0, 0.0, 0.0
        self._pending: dict[int, tuple[float, float, float] | None] = {}  # generazione → trasformazione inviata
        self._in_flight = 0
        self._stage: int | None = None  # generazione della base in attesa del passaggio (41 §3.2, T17)
        self._stage_sampling = False  # la base in attesa ha un campionamento dei tile da aspettare
        self._stage_sampled = False
        self._stage_geometry_changed = False
        self._reported: set[tuple[str, str]] = set()
        self._awaiting = 0  # comandi di vista del gesto ancora in coda
        self._submitted: tuple[float, float, float] | None = None
        self._zoomed = self._moved = False
        self._drag: QPointF | None = None
        self._shown = False
        self._size = None
        self.idle = QTimer(self)
        self.idle.setSingleShot(True)
        self.idle.setInterval(GESTURE_IDLE_MS)
        self.idle.timeout.connect(self._gesture_end)
        if debug_input_enabled():
            self._spy = _WheelSpy(self)
            QApplication.instance().installEventFilter(self._spy)

    def _zoom_button(self, name: str, direction: int) -> QToolButton:
        """Pulsante + o − in sovrimpressione (icona, nome e testo li dà la finestra principale, 40)."""
        button = QToolButton(self)
        button.setObjectName(name)
        button.setAutoRaise(True)
        button.setFixedSize(32, 32)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(lambda: self.zoom_step(direction))
        return button

    def _place_buttons(self) -> None:
        self.measure_overlay.setGeometry(self.rect())
        self.options_bar.move(12, 12)
        self.options_bar.raise_()
        x = self.width() - self.zoom_in_button.width() - 12
        self.zoom_in_button.move(x, 12)
        self.zoom_out_button.move(x, 12 + self.zoom_in_button.height() + 4)
        self.zoom_in_button.raise_()
        self.zoom_out_button.raise_()

    def zoom_step(self, direction: int) -> None:
        """Zoom ×2 (``direction`` = +1) o ÷2 (−1) attorno al centro della finestra, come un gesto (41 §3.4)."""
        self.zoom_by(BUTTON_ZOOM ** direction, QPointF(self.width() / 2, self.height() / 2))

    def go_to_zoom(self) -> bool:
        """Dopo un "Vai a" riuscito: se il campo è maggiore di 1°, ``view.set_zoom`` per portarlo a circa 1° (41
        §3.4). Il campo è quello del risultato del comando (10)."""
        if self.view is None or self.view.scale is None or self.field is None:
            return False
        field = self.field["value"] * u.Unit(self.field["unit"], format="fits")
        if field <= GO_TO_FIELD_MAX:
            return False
        # Parametro scelto da noi (non un risultato): a campi piccoli il campo è la diagonale della finestra per la
        # scala, quindi scala = 1° / diagonale in pixel; il campo vero lo darà il 10 nel risultato.
        window = self.window_size()
        scale = max((GO_TO_FIELD / float(np.hypot(window["width"], window["height"]))).to(u.deg), MIN_SCALE)
        self.submit("view.set_zoom", {"scale": quantity_json(scale), "window": window}, source="keyboard")
        return True

    # --- stato dai comandi --------------------------------------------------------------

    def ratio(self) -> float:
        return float(self.devicePixelRatioF())

    def window_size(self) -> dict:
        """Dimensioni della vista in pixel fisici (pixel logici × rapporto dei pixel dello schermo)."""
        r = self.ratio()
        return {"width": max(1, round(self.width() * r)), "height": max(1, round(self.height() * r))}

    def max_scale(self) -> u.Quantity:
        return MAX_WIDTH_ANGLE / self.window_size()["width"]

    def start_view(self) -> None:
        """Vista iniziale: cielo intero (scala = 360° / larghezza), centro ICRS (0°, 0°); prima lo zoom."""
        window = self.window_size()
        self.submit("view.set_zoom", {"scale": quantity_json(self.max_scale().to(u.deg)), "window": window})
        self.submit("view.set_center", {"position": START_CENTER, "window": window})

    def command_finished(self, name: str, status: str, values: Mapping, state) -> None:
        """Dopo ogni comando (riuscito o no): disegna la nuova geometria e il survey attivo, se sono cambiati; dopo
        ``catalog.select`` mostra o chiude la scheda della sorgente."""
        if name in ("view.set_center", "view.set_zoom") and self._awaiting:
            self._awaiting -= 1
        if name == "catalog.select" and status == "ok":
            self.catalog_layers = state.of_kind("catalog")  # la scheda legge la selezione nuova
            self.show_card(values)
        elif name == "layer.remove" and self._card is not None and state.find(self._card[0]) is None:
            self.hide_card()
        if status == "ok" and "field_of_view" in values:
            self.field = values["field_of_view"]  # campo della geometria disegnata, dal 05 con il 10
        if self._awaiting:
            return  # il gesto ha ancora un comando in coda: si disegna lo stato finale
        # ``state`` può essere già più avanti di questo risultato (il thread dei comandi continua): si disegna
        # sempre lo stato più recente e la scritta si aggiorna dopo ogni comando.
        self.show_state(state)
        self.view_changed.emit()

    @property
    def pixel_grid(self) -> bool:
        """True se la base è la griglia di pixel di un'immagine senza WCS valido (41 §3.5): niente cielo, zoom e
        spostamento col mouse non ci sono (decisione D41-5)."""
        return self.geometry is not None and not hasattr(self.geometry, "window_to_sky")

    def show_state(self, state) -> None:
        view = state.view
        base = state.find(view.base_layer) if view.base_layer else None
        image = base if base is not None and base.kind == "image" else None
        # Lo sfondo si disegna anche sotto un'immagine base (sprint 4f), non sulla griglia di pixel (niente cielo).
        layers = state.of_kind("hips") if view.geometry is None or self._has_sky(view.geometry) else ()
        layer = layers[-1] if layers else None
        if view.geometry is not None and not self._has_sky(view.geometry) and state.of_kind("hips"):
            self._report_once(("", "VIEW_NO_WCS", "hips"), ResultMessage(
                "VIEW_NO_WCS", "immagine senza WCS valido: lo sfondo HiPS non si disegna sotto la griglia di pixel"))
        self.view = view
        self.layers = state.layers
        self.catalog_layers = state.of_kind("catalog")
        self.moc_layers = state.of_kind("moc")
        self.base_image = image
        self._refresh_options_bar()
        self.measure_overlay.update()
        changed_geometry = view.geometry is not self.geometry
        changed_survey = (layer.id if layer else None) != self.survey_layer
        image_key = None if image is None else (image.id, id(image.derived.get("plane")))
        changed_image = image_key != self.image_key
        if not changed_geometry:
            self.show_overlay()  # griglia, indicatore o barra cambiati sulla stessa geometria (view.set_grid, ...)
        if not (changed_geometry or changed_survey):
            if changed_image:  # nuovi colori (image.set_display) sulla stessa geometria
                self.image_key = image_key
                self._image_next = None if image is None or self.geometry is None else sample_image(self.geometry, image)
                if self._stage is None:  # con una base in attesa il piano passa con le altre cose (§3.2)
                    self._show_image(image.id if image is not None else None)
            self.update_catalogs()
            self.update_mocs()
            self.refresh_layers()
            return
        self.geometry = view.geometry
        self.update_catalogs()
        self.update_mocs()
        if changed_survey and self.survey_layer is not None:
            self.renderer.drop_texture(self.survey_layer)
            self.canvas = None
        self.service = layer.data if layer else None
        self.display = layer.display if layer else None
        self.survey_layer = layer.id if layer else None
        self.image_key = image_key
        self._image_next = None if image is None or self.geometry is None else sample_image(self.geometry, image)
        self.refresh_layers()
        if changed_geometry and self._submitted is None:
            # Vista cambiata da altro che dal gesto in corso (Vai a, comando dell'assistente, cronologia): lo
            # spostamento o lo zoom ancora da registrare erano relativi alla geometria vecchia e non valgono più
            # per la nuova; se restassero, a fine gesto sposterebbero il centro appena scelto.
            debug_input(f"gesto AZZERATO da show_state (geometria cambiata da altro): k {self.k:.4f}->1 "
                        f"zoomed={self._zoomed} moved={self._moved}")
            self.idle.stop()
            self._zoomed = self._moved = False
            self.k, self.tx, self.ty = 1.0, 0.0, 0.0
            self.renderer.set_transform(1.0, 0.0, 0.0)
        sent = self._submitted if changed_geometry else (1.0, 0.0, 0.0)
        self._submitted = None
        self.tiles.generation += 1
        gen = self.tiles.generation
        self._pending = {gen: sent}
        self.view_changed.emit()
        # Cambio di base in un passo (41 §3.2, T17): la base vecchia resta disegnata finché per la nuova non sono
        # pronti campionamento dei tile, simboli e MOC; poi tutto passa insieme in ``_try_commit``.
        self._stage, self._stage_geometry_changed = gen, changed_geometry
        self._stage_sampled = False
        self._stage_sampling = not (self.geometry is None or self.service is None or self.service.tile_width is None)
        if self._stage_sampling:
            self.tiles.sample(gen, self.service, self.geometry, layer.derived.get("coverage"))
        else:
            self.sampling = None  # nessun pixel da disegnare (nessun survey o HiPS catalogo) o immagine FITS base
            self._try_commit(gen)

    def _base_ready(self) -> bool:
        """Posizioni dei cataloghi e celle dei MOC visibili calcolate (o fallite) per la base in attesa."""
        g = self.geometry
        if not self._has_sky(g):
            return True
        for layer in self.catalog_layers:
            if layer.visible and (catalog_key(layer, self.base_image), base_key(g)) in self._catalog_pending:
                return False
        return not any(layer.visible and (moc_key(layer), base_key(g)) in self._moc_pending
                       for layer in self.moc_layers)

    def _try_commit(self, gen: int | None = None) -> None:
        """Passa alla base in attesa se tutto è pronto (41 §3.2): un solo blocco di chiamate al renderer, quindi nessun
        fotogramma con livelli su basi diverse."""
        if self._stage is None or (gen is not None and gen != self._stage):
            return
        if self._stage_sampling and not self._stage_sampled:
            return
        if not self._base_ready():
            return
        gen, self._stage = self._stage, None
        image = self.base_image
        if self.sampling is not None:
            rows, cols = self.sampling.shape
            self._settle_transform(gen, rows, cols)
            self.screen_geometry = self.geometry  # tile, immagine, MOC e simboli passano alla nuova finestra insieme
            self._upload()
            self.renderer.set_transform(self.k, self.tx, self.ty)
        else:
            if self._stage_sampling and self.survey_layer is not None:
                self.renderer.drop_texture(self.survey_layer)  # campionamento fallito: nessun sfondo sulla base nuova
            if self._stage_geometry_changed and self.geometry is not None:
                self._settle_transform(gen, *self.geometry.shape)
                self.renderer.set_transform(self.k, self.tx, self.ty)
            if not self._stage_geometry_changed:
                self._pending.pop(gen, None)
            self.screen_geometry = self.geometry
        self._show_image(image.id if image is not None else None)
        self.refresh_points()
        self.refresh_polygons()
        self.show_overlay()

    def _show_image(self, layer_id: str | None) -> None:
        """Piano dell'immagine base per la geometria dello schermo (texture con chiave = livello); immagine tolta o
        cambiata → il piano vecchio si toglie."""
        if self.image_layer is not None and self.image_layer != layer_id:
            self.renderer.drop_texture(self.image_layer)
        self.image_layer, self.image_canvas = layer_id, self._image_next
        if layer_id is not None and self.image_canvas is not None:
            self.renderer.upload_texture(np.ascontiguousarray(self.image_canvas[::-1]), layer_id)
        self.refresh_layers()

    def refresh_layers(self) -> None:
        """Ordine di disegno dal basso, come nello stato, con l'opacità dei piani (41 §3.5, sprint 4f): sfondo e
        immagine come texture, MOC come poligoni, cataloghi come simboli; i livelli nascosti non si disegnano."""
        items = []
        for layer in self.layers:
            if not layer.visible:
                continue
            if layer.kind == "hips" and layer.id == self.survey_layer:
                items.append(("texture", layer.id, float(layer.opacity)))
            elif layer.kind == "image" and layer.id == self.image_layer:
                items.append(("texture", layer.id, float(layer.opacity)))
            elif layer.kind == "moc":
                items.append(("polygons", layer.id, 1.0))
            elif layer.kind == "catalog":
                items.append(("points", layer.id, 1.0))
        self.renderer.set_layers(tuple(items))

    def _settle_transform(self, gen: int, rows: int, cols: int) -> None:
        """La geometria della generazione ``gen`` (finestra ``rows`` × ``cols``) è pronta: si chiude la
        trasformazione del gesto che l'ha chiesta e si tiene quella residua, solo disegno (41 §3.4)."""
        sent = self._pending.pop(gen, None)
        if sent is None:
            self.k, self.tx, self.ty = 1.0, 0.0, 0.0
            # La geometria è stata chiesta con una finestra che può non essere più quella di adesso (pannelli
            # ridimensionati nel frattempo): stesso centro, immagine ricentrata e, a fine gesto, nuova finestra.
            dx, dy = (self.window_size()["width"] - cols) / 2, (self.window_size()["height"] - rows) / 2
            if dx or dy:
                self.tx, self.ty, self._moved = dx, dy, True
                self.idle.start()
        else:  # trasformazione residua del gesto continuato dopo l'invio dei comandi (solo disegno)
            ks, txs, tys = sent
            debug_input(f"geometria ridisegnata: gesto RIPRISTINATO come residuo, k inviato={ks:.4f} k attuale={self.k:.4f}")
            kr = self.k / ks
            self.k, self.tx, self.ty = kr, self.tx - kr * txs, self.ty - kr * tys

    def show_overlay(self) -> None:
        """Griglia, indicatore e barra dallo stato corrente (dati del 10) al renderer."""
        if self._stage is not None:
            return  # griglia, indicatore e barra della base in attesa passano con essa (§3.2)
        self.overlay = None if self.view is None else build_overlay(self.view, self.overlay_texts)
        self.renderer.set_overlay(self.overlay)

    def _sampled(self, gen: int, sampling) -> None:
        if not self.tiles.current(gen):
            return
        rows, cols = sampling.shape
        self.sampling = sampling
        self.canvas = np.zeros((rows, cols, 4), dtype=np.uint8)  # si carica sulla GPU al passaggio (§3.2)
        self._stage_sampled = True
        if "fits" in self.service.tile_formats[:1] and (self.display is None or self.display.get("vmin") is None):
            self._report("HIPS_DISPLAY_UNKNOWN", f"{self.service.hips_id}: limiti di colore del survey non noti, "
                         "i tile FITS non si disegnano; riaprire il survey indicando vmin e vmax",
                         {"reason": "reopen", "hips_id": self.service.hips_id})
        else:
            for index in sampling.tiles:
                self._in_flight += 1
                self.tiles.fetch(gen, self.service, sampling, index, self.display)
            self.tiles_changed.emit(self._in_flight)
        self._try_commit(gen)

    def _tile(self, gen: int, view_tile) -> None:
        if not self.tiles.current(gen) or self.canvas is None:
            return  # tile di una finestra superata: scartato
        y0, y1, x0, x1 = view_tile.box
        box = self.canvas[y0:y1, x0:x1]
        values = view_tile.values
        box[view_tile.mask, :3] = values[view_tile.mask][:, :3]
        box[view_tile.mask, 3] = values[view_tile.mask][:, 3] if values.shape[-1] == 4 else 255
        if self._stage is None:  # con una base in attesa i tile si caricano al passaggio
            self._upload()

    def _failed(self, gen: int, code: str, text: str) -> None:
        if self.tiles.current(gen):
            self._report(code, text)
            if gen == self._stage and self._stage_sampling and not self._stage_sampled:
                # campionamento fallito: la base nuova passa senza lo sfondo (zona vuota e un messaggio)
                self._stage_sampled = True
                self.sampling = self.canvas = None
                self._try_commit(gen)

    def _tile_done(self, gen: int) -> None:
        self._in_flight = max(0, self._in_flight - 1)
        self.tiles_changed.emit(self._in_flight)

    def _report(self, code: str, text: str, params: dict | None = None) -> None:
        key = (self.survey_layer or "", code)
        if key not in self._reported:  # un solo messaggio per survey e codice, non uno per tile (41 §3.7)
            self._reported.add(key)
            self.message.emit(ResultMessage(code, text, params or {}))

    def _upload(self) -> None:
        # Riga 0 della finestra = sud (asse y del WCS verso nord): sullo schermo va in basso.
        self.renderer.upload_texture(np.ascontiguousarray(self.canvas[::-1]), self.survey_layer or "plane")

    def set_night(self, night: bool) -> None:
        self._night = bool(night)
        self.renderer.set_night(night)
        self._style_card()
        self.simbad_tool.style()
        self.measure_overlay.update()

    # --- cataloghi (41 §3.8) ---------------------------------------------------------------

    def update_catalogs(self) -> None:
        """Chiede le posizioni mancanti dei cataloghi visibili sulla base corrente e aggiorna il disegno."""
        g = self.geometry
        if g is not None and self.pixel_grid:
            if self.catalog_layers:
                self._report_once(("", "VIEW_NO_WCS"), ResultMessage(
                    "VIEW_NO_WCS", "immagine senza WCS valido: i cataloghi non si sovrappongono alla griglia di pixel"))
        elif g is not None:
            keep = {base_key(g)} | ({base_key(self.screen_geometry)} if self._has_sky(self.screen_geometry) else set())
            self.catalog_cache = {k: v for k, v in self.catalog_cache.items() if k[1] in keep}
            for layer in self.catalog_layers:
                key = (catalog_key(layer, self.base_image), base_key(g))
                if layer.visible and key not in self.catalog_cache and key not in self._catalog_pending:
                    self._catalog_pending.add(key)
                    self.tiles.catalog(key, layer, g, self.base_image)
        self.refresh_points()

    @staticmethod
    def _has_sky(geometry) -> bool:
        return geometry is not None and hasattr(geometry, "window_to_sky")

    def _catalog_done(self, key: tuple, result) -> None:
        self._catalog_pending.discard(key)
        if isinstance(result, ResultMessage):
            self._report_once((key[0][0], result.code), result)
            self._try_commit()
            return
        self.catalog_cache[key] = result
        for message in result.warnings:  # epoche diverse: una volta per livello e immagine (41 §3.8)
            self._report_once((key[0][0], message.code, key[0][4]), message)
        self.refresh_points()
        self._try_commit()
        self.layers_drawn.emit()

    def _report_once(self, key: tuple, message: ResultMessage) -> None:
        if key not in self._reported:
            self._reported.add(key)
            self.message.emit(message)

    def points_for(self, layer) -> CatalogPoints | None:
        """Posizioni disegnate del livello sulla base dello schermo, se già calcolate."""
        g = self.screen_geometry
        if not self._has_sky(g):
            return None
        return self.catalog_cache.get((catalog_key(layer, self.base_image), base_key(g)))

    def refresh_points(self) -> None:
        """Simboli nello spazio della finestra disegnata: solo ``base_to_window`` della ``ViewGeometry`` (fattore e
        spostamento, 41 §3.4), opacità del livello e selezione; nessun numero mostrato nasce qui."""
        sets: list[PointSet] = []
        g = self.screen_geometry
        for layer in self.catalog_layers if self._has_sky(g) else ():
            points = self.points_for(layer)
            if not layer.visible or points is None or not len(points.rows):
                continue
            wx, wy = g.base_to_window(points.base_xy[:, 0], points.base_xy[:, 1])
            xy = np.column_stack([wx + 0.5, g.shape[0] - wy - 0.5]).astype(np.float32)
            rgba = points.rgba.copy()
            rgba[:, 3] *= np.float32(layer.opacity)
            sets.append(PointSet(layer.id, points.rows, xy, rgba, points.size, points.shape,
                                 np.isin(points.rows, np.asarray(layer.selection, dtype=np.int64))))
        self.point_sets = tuple(sets)
        self._trees = {}
        self.renderer.upload_points(self.point_sets)
        self._place_card()
        self.measure_overlay.update()

    # --- MOC (41 §3.9, sprint 4f) ---------------------------------------------------------

    def update_mocs(self) -> None:
        """Chiede le celle mancanti dei MOC visibili sulla base corrente e aggiorna il disegno."""
        g = self.geometry
        if g is not None and self.pixel_grid:
            if self.moc_layers:
                self._report_once(("", "VIEW_NO_WCS", "moc"), ResultMessage(
                    "VIEW_NO_WCS", "immagine senza WCS valido: i MOC non si sovrappongono alla griglia di pixel"))
        elif g is not None:
            keep = {base_key(g)} | ({base_key(self.screen_geometry)} if self._has_sky(self.screen_geometry) else set())
            self.moc_cache = {k: v for k, v in self.moc_cache.items() if k[1] in keep}
            for layer in self.moc_layers:
                key = (moc_key(layer), base_key(g))
                if layer.visible and key not in self.moc_cache and key not in self._moc_pending:
                    self._moc_pending.add(key)
                    self.tiles.moc(key, layer, g)
        self.refresh_polygons()

    def _moc_done(self, key: tuple, result) -> None:
        self._moc_pending.discard(key)
        if isinstance(result, ResultMessage):
            self.moc_errors[key[0][0]] = result
            self._report_once((key[0][0], result.code), result)
        else:
            self.moc_cache[key] = result
            self.refresh_polygons()
        self._try_commit()
        self.layers_drawn.emit()

    def shapes_for(self, layer) -> MocShapes | None:
        """Celle disegnate del MOC sulla base dello schermo, se già calcolate."""
        g = self.screen_geometry
        if not self._has_sky(g):
            return None
        return self.moc_cache.get((moc_key(layer), base_key(g)))

    def refresh_polygons(self) -> None:
        """MOC nello spazio della finestra disegnata: solo ``base_to_window`` (41 §3.4); colori dallo stile del livello
        (05) con ``fill`` × opacità per il riempimento e l'opacità per il perimetro."""
        sets: list[PolygonSet] = []
        g = self.screen_geometry
        for layer in self.moc_layers if self._has_sky(g) else ():
            shapes = self.shapes_for(layer)
            if not layer.visible or shapes is None or not (len(shapes.triangles) or len(shapes.lines)):
                continue

            def window(xy: np.ndarray) -> np.ndarray:
                wx, wy = g.base_to_window(xy[:, 0], xy[:, 1])
                return np.column_stack([wx + 0.5, g.shape[0] - wy - 0.5]).astype(np.float32)

            style = layer.style or {}
            r, gg, b, _ = _hex_rgba(np.array([style.get("color", "#CC79A7")]))[0]
            opacity = float(layer.opacity)
            fill = float(style.get("fill", 0.25)) * opacity
            sets.append(PolygonSet(layer.id, window(shapes.triangles), (float(r), float(gg), float(b), fill),
                                   window(shapes.lines), (float(r), float(gg), float(b), opacity)))
        self.polygon_sets = tuple(sets)
        self.renderer.upload_polygons(self.polygon_sets)

    def source_at(self, at: QPointF) -> tuple[str, int] | None:
        """Simbolo disegnato più vicino al punto ``at`` (pixel logici) entro metà della sua dimensione o, se più
        grande, entro ``CLICK_TOLERANCE`` (41 §3.8, scelta minore 5); a pari distanza il livello più in alto. È una
        scelta sullo schermo (``cKDTree`` di scipy), non un numero mostrato."""
        from scipy.spatial import cKDTree

        r = self.ratio()
        q = np.array([(at.x() * r - self.tx) / self.k, (at.y() * r - self.ty) / self.k])
        best: tuple[float, str, int] | None = None
        for i, points in enumerate(self.point_sets):
            tolerance = np.maximum(points.size / 2.0, CLICK_TOLERANCE)  # pixel logici
            tree = self._trees.get(i)
            if tree is None:
                tree = self._trees[i] = cKDTree(points.xy.astype(np.float64))
            near = tree.query_ball_point(q, float(tolerance.max()) * r / self.k)
            for j in near:
                d = float(np.hypot(*(points.xy[j] - q))) * self.k / r
                if d <= tolerance[j] and (best is None or d <= best[0]):
                    best = (d, points.layer, int(points.rows[j]))
        return None if best is None else (best[1], best[2])

    def click_at(self, at: QPointF) -> None:
        """Clic sul cielo: ``catalog.select`` della sorgente scelta; nel vuoto chiude la scheda e toglie le
        selezioni attive con ``catalog.select`` a righe vuote (41 §3.8)."""
        hit = self.source_at(at)
        if hit is not None:
            self.submit("catalog.select", {"layer": hit[0], "rows": [hit[1]]}, source="mouse")
            return
        self.hide_card()
        for layer in self.catalog_layers:
            if layer.selection:
                self.submit("catalog.select", {"layer": layer.id, "rows": []}, source="mouse")

    # --- scheda della sorgente (41 §3.8, decisione del proprietario del 2026-10-21) --------------

    def show_card(self, values: Mapping) -> None:
        card = values.get("source")
        if card is None:
            self.hide_card()
            return
        self._card = (values["layer"], int(card["row"]), card)
        self.card.setText(self.card_html())
        self.card.adjustSize()
        self._style_card()
        self.card.show()
        self.card.raise_()
        self._place_card()

    def hide_card(self) -> None:
        self._card = None
        self.card.hide()

    def card_html(self) -> str:
        """Testo della scheda: tutto dal risultato di ``catalog.select`` (05) e dalle posizioni disegnate (13), le
        coordinate scritte da ``format_coordinates`` del 10 nello stile scelto, le epoche con ``time_text`` (DC1)."""
        from astrotwo.core.coordinates_wcs import format_coordinates

        layer_id, row, card = self._card
        t = self.card_texts
        name = card["name"]["value"] or t["row"].replace("%1", str(row))
        lines = [f"<b>{html.escape(name)}</b>"]
        position = card.get("position")
        style = self.view.coordinate_format if self.view is not None else "sexagesimal"
        if position is None:
            lines.append(html.escape(t["no_position"].replace("%1", card.get("position_reason") or "")))
        else:
            frame = position["frame"]
            q = {axis: position[axis]["value"] * u.Unit(position[axis]["unit"]) for axis in ("lon", "lat")}
            lon = format_coordinates(values=q["lon"], frame=frame, axis="lon", style=style).lon[0]
            lat = format_coordinates(values=q["lat"], frame=frame, axis="lat", style=style).lat[0]
            label = frame.upper() if frame in ("icrs", "fk5", "fk4") else frame.capitalize()
            lines.append(html.escape(f"{label} {lon} {lat}"))
            epoch = time_text(position.get("epoch"))
            lines.append(html.escape(t["epoch"].replace("%1", epoch) if epoch else t["epoch_unknown"]))
        layer = next((x for x in self.catalog_layers if x.id == layer_id), None)
        points = None if layer is None else self.points_for(layer)
        if points is not None:
            if points.propagated:
                lines.append(html.escape(t["propagated"].replace("%1", time_text(points.epoch) or "")
                                         .replace("%2", points.epoch_source or "")))
            else:
                lines.append(html.escape(t["not_propagated"]))
            for message in points.warnings:
                lines.append(f"⚠ {html.escape(shown_text(message))}")
            if row not in set(points.rows.tolist()):
                lines.append(html.escape(t["not_drawn"]))
        catalog = card["catalog"]
        lines.append(html.escape(t["catalog"].replace("%1", f"{catalog['name']} · {catalog['origin']}")))
        if catalog.get("retrieved_at"):
            lines.append(html.escape(t["retrieved"].replace("%1", catalog["retrieved_at"])))
        return "<br>".join(lines)

    def _style_card(self) -> None:
        ink, edge = ("#ff2020", "#7a0000") if self._night else ("#e8eefc", "#3a4660")
        self.card.setStyleSheet(f"QLabel#sourceCard {{ background: rgba(8, 10, 16, 225); color: {ink}; "
                                f"border: 1px solid {edge}; border-radius: 6px; padding: 8px; }}")

    def _place_card(self) -> None:
        """La scheda sta vicino al simbolo e lo segue durante il gesto (stessa traslazione e scala, solo disegno)."""
        if self._card is None:
            return
        layer_id, row, _ = self._card
        x, y = 12.0, 12.0
        r = self.ratio()
        for points in self.point_sets:
            if points.layer == layer_id:
                hit = np.flatnonzero(points.rows == row)
                if hit.size:
                    qx, qy = points.xy[hit[0]]
                    x, y = (self.k * qx + self.tx) / r + 12, (self.k * qy + self.ty) / r + 12
                break
        w, h = self.card.width(), self.card.height()
        x = min(max(x, 4.0), max(4.0, self.width() - w - 4.0))
        y = min(max(y, 4.0), max(4.0, self.height() - h - 4.0))
        self.card.move(int(x), int(y))

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            if self.tool == "distance" and self.distance_tool.cancel():
                event.accept()
                return
            if self.tool == "simbad_pointer" and self.simbad_tool.card.isVisible():
                self.simbad_tool.hide()
                event.accept()
                return
        if event.key() == Qt.Key.Key_Escape and self._card is not None:
            self.hide_card()
            event.accept()
            return
        super().keyPressEvent(event)

    # --- strumenti (41 §3.12, §3.19) ---------------------------------------------------------

    def set_tool(self, tool: str) -> None:
        """Strumento attivo dopo ``ui.set_tool``: cursore a croce, barra delle opzioni della distanza."""
        if tool != self.tool:
            self.distance_tool.reset()
            self.simbad_tool.reset()
        self.tool = tool
        self.setCursor(Qt.CursorShape.CrossCursor if tool != "none" else Qt.CursorShape.ArrowCursor)
        self._refresh_options_bar()

    def set_tool_option(self, key: str, value: str) -> None:
        """Opzione dello strumento di distanza dalla preferenza ``tools/…`` (`prefs.set`, 40)."""
        options = self.distance_tool.options
        if key == "tools/distance_unit":
            options["unit"] = value
        elif key == "tools/distance_snap":
            options["snap"] = value == "true"
        elif key == "tools/distance_box_size":
            options["box_size"] = int(value)
        self._refresh_options_bar()

    def image_is_base(self) -> bool:
        """Base della vista = immagine con WCS: solo allora la distanza usa i pixel e si può agganciare."""
        return self.base_image is not None and getattr(self.base_image.data, "wcs", None) is not None

    def _refresh_options_bar(self) -> None:
        self.options_bar.setVisible(self.tool == "distance")
        self.options_bar.show_options(self.distance_tool.options, self.image_is_base())
        self.options_bar.raise_()
        self.options_bar.setStyleSheet(
            "QFrame#distanceOptions { background: rgba(8, 10, 16, 225); border-radius: 6px; } "
            + "QFrame#distanceOptions QLabel, QFrame#distanceOptions QCheckBox { color: "
            + ("#ff2020" if self._night else "#e8eefc") + "; }")

    # --- gesti (41 §3.4, 05 §3.3) --------------------------------------------------------

    def _gesture_step(self) -> None:
        self.renderer.set_transform(self.k, self.tx, self.ty)
        self.measure_overlay.update()
        self._place_card()
        self.idle.start()

    def zoom_by(self, factor: float, at: QPointF) -> None:
        """Zoom di ``factor`` (dato in ingresso dal gesto) attorno al punto ``at`` (pixel logici), entro i limiti."""
        if self.view is None or self.view.scale is None or self.pixel_grid:
            debug_input(f"zoom_by ignorato: vista non pronta o griglia di pixel (view={self.view is not None})")
            return
        k_before, requested = self.k, factor
        scale = (self.view.scale / (self.k * factor)).to(u.deg)
        if scale < MIN_SCALE:
            factor = float((self.view.scale / MIN_SCALE).decompose()) / self.k
        elif scale > self.max_scale():
            factor = float((self.view.scale / self.max_scale()).decompose()) / self.k
        r = self.ratio()
        cx, cy = at.x() * r, at.y() * r
        self.k *= factor
        self.tx = cx - factor * (cx - self.tx)
        self.ty = cy - factor * (cy - self.ty)
        self._zoomed = True
        self._gesture_step()
        debug_input(f"zoom_by fattore_chiesto={requested:.4f} fattore_usato={factor:.4f} k {k_before:.4f}->{self.k:.4f} "
                    f"scala_vista={self.view.scale.to_value(u.arcsec):.6g}arcsec; debounce {GESTURE_IDLE_MS} ms riavviato")

    def pan_by(self, dx: float, dy: float) -> None:
        """Spostamento di ``(dx, dy)`` pixel logici."""
        debug_input(f"pan_by dx={dx} dy={dy}")
        r = self.ratio()
        self.tx += dx * r
        self.ty += dy * r
        self._moved = True
        self._gesture_step()

    def wheelEvent(self, event) -> None:  # noqa: N802 - nome di Qt
        pixels = event.pixelDelta()
        debug_input(f"wheelEvent angleDelta=({event.angleDelta().x()},{event.angleDelta().y()}) "
                    f"pixelDelta=({pixels.x()},{pixels.y()}) phase={event.phase().name} inverted={event.inverted()} "
                    f"modifiers={event.modifiers()} source={event.source().name}")
        if event.phase() == Qt.ScrollPhase.NoScrollPhase:
            # Rotella di un mouse: su macOS ogni scatto arriva spezzato in più eventi (tutti con angleDelta = ±120) e
            # con un pixelDelta non nullo (accelerazione del sistema), da ignorare. Ogni evento vale 1/6 di scatto.
            delta = event.angleDelta().y()
            if delta:
                steps = delta / 120.0 / WHEEL_EVENTS_PER_NOTCH
                self.zoom_by(ZOOM_STEP ** steps, event.position())
            else:
                debug_input("wheelEvent: angleDelta.y = 0, nessuna azione")
        elif not pixels.isNull() and not self.pixel_grid:  # trackpad a due dita (fasi Begin/Update/End/Momentum): spostamento (41 §3.16)
            self.pan_by(pixels.x(), pixels.y())  # lo zoom del trackpad è il pizzico
        event.accept()
        debug_input(f"wheelEvent accettato={event.isAccepted()}")

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.NativeGesture and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
            self.zoom_by(1.0 + event.value(), event.position())  # pizzico sul trackpad
            event.accept()
            return True
        return super().event(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self.tool == "distance":  # il trascinamento misura, non sposta la vista (41 §3.19)
                self.distance_tool.press(event.position())
                event.accept()
                return
            if self.tool == "simbad_pointer":
                self.simbad_tool.hide()
                self._press = event.position()
                event.accept()
                return
            self._drag = self._press = event.position()
            self._dragging = False
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self.tool == "distance":
            self.distance_tool.move(event.position())
        elif self.tool == "simbad_pointer":
            self.simbad_tool.move(event.position())
        if self._drag is not None and not self.pixel_grid:
            pos = event.position()
            # sotto CLICK_SLOP la pressione può ancora essere un clic: nessuno spostamento
            if self._dragging or np.hypot(pos.x() - self._press.x(), pos.y() - self._press.y()) >= CLICK_SLOP:
                self._dragging = True
                self.pan_by(pos.x() - self._drag.x(), pos.y() - self._drag.y())
                self._drag = pos
        self._cursor_inside = True
        self.read_cursor(event.position())
        event.accept()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._cursor_inside = False
        self._cursor_next = None
        self.cursor_read.emit(None)
        self.simbad_tool.leave()
        super().leaveEvent(event)

    # --- coordinate e valore sotto il mouse (41 §3.11) -----------------------------------

    def window_position(self, at: QPointF) -> dict:
        """Punto dello schermo (pixel logici) → pixel della finestra disegnata (convenzione numpy, riga 0 = sud):
        stessa traslazione e scala del disegno (§3.4), anche durante un gesto. È geometria di disegno: le coordinate
        celesti le dà ``cursor.read`` con il 10."""
        r = self.ratio()
        qx, qy = (at.x() * r - self.tx) / self.k, (at.y() * r - self.ty) / self.k
        rows = self.geometry.shape[0]
        return {"x": qx - 0.5, "y": rows - qy - 0.5, "convention": "numpy"}

    def read_cursor(self, at: QPointF) -> None:
        """Lettura passiva ``cursor.read`` alla posizione ``at``: al più una in corso, vale l'ultima posizione."""
        if self.passive is None or self.geometry is None or self.view is None:
            return
        if self._cursor_busy:
            self._cursor_next = at
            return
        self._cursor_busy = True
        order = None
        if self.service is not None and self.sampling is not None and "fits" in self.service.tile_formats:
            order = int(self.sampling.order)  # il valore è quello del pixel disegnato (decisione del 2026-10-18)
        self.tiles.read(self.passive, "cursor.read", {"position": self.window_position(at), "order": order})

    def _cursor_done(self, result) -> None:
        self._cursor_busy = False
        if self._cursor_inside:
            self.cursor_read.emit(result)
        pending, self._cursor_next = self._cursor_next, None
        if pending is not None and self._cursor_inside:
            self.read_cursor(pending)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.tool != "none":
            self._press = None
            if self.tool == "distance":
                self.distance_tool.release(event.position())
            else:
                self.simbad_tool.click(event.position())
            event.accept()
            return
        clicked = event.button() == Qt.MouseButton.LeftButton and self._press is not None and not self._dragging
        self._drag = self._press = None
        self._dragging = False
        if clicked and self._has_sky(self.screen_geometry):
            self.click_at(event.position())
        event.accept()

    def _gesture_end(self) -> None:
        """Fine del gesto: ``view.set_zoom`` poi ``view.set_center`` con lo stato finale (05 §3.3)."""
        geometry = self.geometry
        if self.pixel_grid:  # nessun comando di vista da registrare: resta solo il centramento dopo un ridimensionamento
            self._zoomed = self._moved = False
            return
        debug_input(f"debounce scaduto: zoomed={self._zoomed} moved={self._moved} k={self.k:.4f} "
                    f"tx={self.tx:.1f} ty={self.ty:.1f}")
        if geometry is None or self.view is None or self.view.scale is None:
            self._zoomed = self._moved = False
            debug_input("gesto AZZERATO: geometria o vista non pronta")
            return
        window = self.window_size()
        w, h = window["width"], window["height"]
        # Punto dello schermo al centro della finestra → pixel della finestra disegnata (stessa traslazione e
        # scala, convenzione numpy con riga 0 in basso) → cielo con window_to_sky del 10.
        qx, qy = (w / 2 - self.tx) / self.k, (h / 2 - self.ty) / self.k
        rows = geometry.shape[0]
        center = geometry.window_to_sky(qx - 0.5, rows - qy - 0.5)
        sent = 0
        if self._zoomed:
            scale = (self.view.scale / self.k).to(u.deg)
            self.submit("view.set_zoom", {"scale": quantity_json(scale), "window": window}, source="mouse")
            sent += 1
        if np.isfinite(center.spherical.lon.deg) and np.isfinite(center.spherical.lat.deg):
            self.submit("view.set_center", {"position": sky_json(center), "window": window}, source="mouse")
            sent += 1
        self._zoomed = self._moved = False
        debug_input(f"gesto inviato: {sent} comandi (view.set_zoom/view.set_center)")
        if sent:
            self._awaiting += sent
            self._submitted = (self.k, self.tx, self.ty)

    # --- dimensioni ----------------------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._place_buttons()
        if not self._shown:
            self._shown = True
            QTimer.singleShot(0, self.first_shown.emit)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_buttons()
        old, new = event.oldSize(), event.size()
        if not old.isValid() or self.view is None or self.view.window is None:
            return
        # Stesso centro; a fine gesto (300 ms) view.set_center con la nuova finestra (05 §3.2, parametro window).
        self.pan_by((new.width() - old.width()) / 2, (new.height() - old.height()) / 2)


# --- pannello dei livelli (41 §3.5, A11 minimo; sprint 4f) ----------------------------------


class _LayerList(QListWidget):
    """Elenco con il trascinamento: il rilascio non sposta la riga, chiede ``layer.move`` (``dropped``); l'elenco si
    ricostruisce dallo stato dopo il comando."""

    dropped = Signal(int, int)  # riga trascinata, riga di arrivo (righe del pannello, 0 = in alto)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    def dropEvent(self, event) -> None:  # noqa: N802 - nome di Qt
        source = self.currentRow()
        item = self.itemAt(event.position().toPoint())
        indicator = self.dropIndicatorPosition()
        if item is None or indicator == QAbstractItemView.DropIndicatorPosition.OnViewport:
            index = self.count()
        else:
            index = self.row(item) + (1 if indicator == QAbstractItemView.DropIndicatorPosition.BelowItem else 0)
        if index > source:
            index -= 1  # posizione nell'elenco senza la riga trascinata
        event.ignore()
        if source >= 0 and index != source:
            self.dropped.emit(source, index)


class _LayerRow(QWidget):
    """Una riga del pannello: visibilità, nome e tipo, dettagli, opacità, su/giù, rimozione."""

    def __init__(self, layer_id: str, texts: Mapping[str, str], parent=None) -> None:
        super().__init__(parent)
        self.layer_id = layer_id
        self.setObjectName("layerRow")
        self.visible = QCheckBox(self)
        self.visible.setObjectName("layerVisible")
        self.visible.setToolTip(texts["visible"])
        self.name = QLabel(self)
        self.name.setObjectName("layerName")
        self.name.setTextFormat(Qt.TextFormat.RichText)
        self.details = QLabel(self)
        self.details.setObjectName("layerDetails")
        self.details.setWordWrap(True)
        self.opacity = QSlider(Qt.Orientation.Horizontal, self)
        self.opacity.setObjectName("layerOpacity")
        self.opacity.setRange(0, 100)
        self.opacity.setToolTip(texts["opacity"])
        self.percent = QLabel(self)
        self.percent.setObjectName("layerPercent")
        self.percent.setMinimumWidth(36)
        self.up, self.down, self.remove = (self._button(name, text, tip) for name, text, tip in (
            ("layerUp", "▲", texts["up"]), ("layerDown", "▼", texts["down"]), ("layerRemove", "✕", texts["remove"])))
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self.visible)
        top.addWidget(self.name, 1)
        for button in (self.up, self.down, self.remove):
            top.addWidget(button)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(22, 0, 0, 0)
        bottom.addWidget(self.opacity, 1)
        bottom.addWidget(self.percent)
        box = QVBoxLayout(self)
        box.setContentsMargins(6, 4, 6, 4)
        box.setSpacing(2)
        box.addLayout(top)
        details = QHBoxLayout()
        details.setContentsMargins(22, 0, 0, 0)
        details.addWidget(self.details)
        box.addLayout(details)
        box.addLayout(bottom)
        self.opacity.valueChanged.connect(lambda v: self.percent.setText(f"{v} %"))

    def _button(self, name: str, text: str, tip: str) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(name)
        button.setText(text)
        button.setToolTip(tip)
        button.setAccessibleName(tip)
        button.setAutoRaise(True)
        return button


class LayerPanel(QWidget):
    """Pannello dei livelli (41 §3.5): in alto il livello disegnato sopra. Ogni azione è un comando del 05
    (``requested_by`` = ``mouse``): ``layer.set_visible``, ``layer.set_opacity`` (al rilascio del cursore),
    ``layer.move`` (su/giù e trascinamento), ``layer.remove``. I dettagli vengono dai moduli (corpo dal 19, epoche con
    ``time_text``) e dal disegno del visualizzatore (righe disegnate, ordine del MOC)."""

    def __init__(self, submit: Callable[..., int], viewer: SkyViewer | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("layerPanel")
        self.submit = submit
        self.viewer = viewer
        self.texts: Mapping[str, str] = DEFAULT_PANEL_TEXTS  # tradotti dalla finestra principale (40)
        self.list = _LayerList(self)
        self.list.setObjectName("layerList")
        self.list.dropped.connect(self.move_row)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.list)
        self.state = None
        self.rows: dict[str, _LayerRow] = {}
        self._order: tuple[str, ...] = ()
        if viewer is not None:
            viewer.layers_drawn.connect(self.refresh)

    # --- stato -------------------------------------------------------------------------

    def panel_order(self) -> tuple[str, ...]:
        """Identificativi dall'alto (livello disegnato sopra) in basso."""
        return tuple(layer.id for layer in reversed(self.state.layers)) if self.state is not None else ()

    def show_state(self, state) -> None:
        """Elenco dallo stato: si ricostruisce se cambiano livelli o ordine, altrimenti si aggiornano le righe."""
        self.state = state
        order = self.panel_order()
        if order != self._order:
            self._order = order
            self.list.clear()
            self.rows = {}
            for layer_id in order:
                row = _LayerRow(layer_id, self.texts)
                row.visible.toggled.connect(lambda on, i=layer_id: self.set_visible(i, on))
                row.opacity.sliderReleased.connect(lambda i=layer_id, r=row: self.set_opacity(i, r.opacity.value()))
                row.opacity.valueChanged.connect(
                    lambda v, i=layer_id, r=row: None if r.opacity.isSliderDown() or r.opacity.signalsBlocked()
                    else self.set_opacity(i, v))
                row.up.clicked.connect(lambda _=False, i=layer_id: self.step(i, -1))
                row.down.clicked.connect(lambda _=False, i=layer_id: self.step(i, +1))
                row.remove.clicked.connect(lambda _=False, i=layer_id: self.remove(i))
                item = QListWidgetItem(self.list)
                self.list.setItemWidget(item, row)
                self.rows[layer_id] = row
        self.refresh()

    def refresh(self) -> None:
        """Righe aggiornate dallo stato e dal disegno, senza nuovi comandi."""
        if self.state is None:
            return
        last = len(self._order) - 1
        for index, layer_id in enumerate(self._order):
            layer = self.state.find(layer_id)
            row = self.rows.get(layer_id)
            if layer is None or row is None:
                continue
            row.visible.blockSignals(True)
            row.visible.setChecked(layer.visible)
            row.visible.blockSignals(False)
            if not row.opacity.isSliderDown():
                row.opacity.blockSignals(True)
                row.opacity.setValue(round(layer.opacity * 100))
                row.opacity.blockSignals(False)
                row.percent.setText(f"{row.opacity.value()} %")
            row.up.setEnabled(index > 0)
            row.down.setEnabled(index < last)
            kind = self.texts.get(layer.kind, layer.kind)
            row.name.setText(f"<b>{html.escape(layer.name)}</b> · {html.escape(kind)}")
            row.details.setText(self.details(layer))
            item = self.list.item(index)
            if item is not None:
                item.setSizeHint(row.sizeHint())

    def details(self, layer) -> str:
        """Riga dei dettagli (41 §3.5): sorgente, corpo, epoca usata per il disegno, conteggi, forzatura."""
        from astrotwo.core.planetary_data import body_of

        t = self.texts
        data = layer.data
        parts: list[str] = []
        if layer.kind == "hips":
            parts.append(getattr(data, "title", None) or getattr(data, "hips_id", "") or layer.source)
        elif layer.source:
            parts.append(os.path.basename(layer.source) or layer.source)
        retrieved = getattr(data, "retrieved_at", None) if layer.kind == "catalog" else None
        if retrieved is not None:
            parts.append(t["retrieved"].replace("%1", retrieved.strftime("%Y-%m-%dT%H:%M:%SZ")))
        if layer.kind != "measure" and data is not None:
            try:
                parts.append(t["body"].replace("%1", body_of(data)))
            except Exception as exc:  # noqa: BLE001 - corpo non ricavabile: il codice del 19
                parts.append(t["body_unknown"].replace("%1", str(getattr(exc, "code", type(exc).__name__))))
        if layer.kind == "measure" and hasattr(data, "value"):  # valore pieno e unità del 17 (41 §3.19)
            parts.append(f"{float(data.value.value)!r} {data.value.unit}")
        if layer.kind == "image":
            epoch = None if data is None or data.wcs is None else data.wcs.image_epoch
            parts.append(t["epoch"].replace("%1", time_text(epoch)) if epoch is not None else t["epoch_unknown"])
        viewer = self.viewer
        if layer.kind == "catalog" and viewer is not None:
            points = viewer.points_for(layer)
            if points is not None:
                parts.append(t["drawn"].replace("%1", str(len(points.rows))).replace("%2", str(len(data.table))))
                parts.append(t["propagated"].replace("%1", time_text(points.epoch) or "") if points.propagated
                             else t["not_propagated"])
        if layer.kind == "moc" and viewer is not None:
            shapes = viewer.shapes_for(layer)
            error = viewer.moc_errors.get(layer.id)
            if shapes is not None:
                key = "order" if shapes.order >= shapes.moc_order else "by_excess"
                parts.append(t[key].replace("%1", str(shapes.order)).replace("%2", str(shapes.moc_order)))
                parts.append(t["cells"].replace("%1", str(shapes.cells)))
            elif error is not None:
                parts.append(t["not_drawn"].replace("%1", error.code))
        if layer.force_body:
            parts.append(t["forced"])
        return html.escape(" · ".join(p for p in parts if p))

    # --- azioni (comandi del 05) ---------------------------------------------------------

    def set_visible(self, layer_id: str, visible: bool) -> int:
        return self.submit("layer.set_visible", {"layer": layer_id, "visible": bool(visible)}, source="mouse")

    def set_opacity(self, layer_id: str, percent: int) -> int | None:
        layer = self.state.find(layer_id) if self.state is not None else None
        value = percent / 100.0
        if layer is not None and round(layer.opacity * 100) == percent:
            return None  # stessa opacità: nessun comando
        return self.submit("layer.set_opacity", {"layer": layer_id, "opacity": value}, source="mouse")

    def step(self, layer_id: str, direction: int) -> int | None:
        """Su (−1) o giù (+1) di una riga del pannello."""
        row = self._order.index(layer_id)
        return self.move_row(row, row + direction)

    def move_row(self, source: int, target: int) -> int | None:
        """Riga ``source`` del pannello alla riga ``target`` → ``layer.move`` (posizione nello stato: 0 = in basso)."""
        n = len(self._order)
        if not (0 <= source < n and 0 <= target < n) or source == target:
            return None
        return self.submit("layer.move", {"layer": self._order[source], "position": n - 1 - target}, source="mouse")

    def remove(self, layer_id: str) -> int:
        return self.submit("layer.remove", {"layer": layer_id}, source="mouse")
