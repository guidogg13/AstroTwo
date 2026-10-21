# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Visualizzatore del cielo (41), sprint 4a-4e: sfondo HiPS (a colori o FITS), zoom, spostamento, lettura sotto il
mouse, griglia delle coordinate, indicatore del nord e barra di scala, immagine FITS base, cataloghi e clic.

Nessun numero mostrato nasce qui: la geometria è la ``ViewGeometry`` del 10 (dai comandi di vista del 05), i tile
e il loro campionamento sulla finestra vengono dal 12 (``view_sampling``, ``fetch_tile``, ``fill_view``).
Traslazione e scala dello schermo durante un gesto sono solo disegno (41 §3.4); a fine gesto (300 ms fermo, 05
§3.3) si registrano ``view.set_zoom`` e/o ``view.set_center`` con lo stato finale.

Sfondo HiPS: un solo survey; i tile JPEG/PNG si disegnano com'è, i tile FITS sono portati a colori da
``set_display`` dell'11 con i limiti scelti da ``hips.set_survey`` (campo ``display`` del livello, 41 §3.7). Sotto il
mouse una lettura passiva ``cursor.read`` (05) nel gruppo di thread dei tile, al più una in corso (41 §3.11). Il
pannello dei livelli e gli strumenti arrivano negli sprint successivi.

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
from PySide6.QtWidgets import QApplication, QLabel, QToolButton, QVBoxLayout, QWidget

from astrotwo.core.commands import ResultMessage, quantity_json, sky_json, time_text
from astrotwo.core.hips import DEFAULT_TILE_MEMORY_BYTES, HiPSError, TileMemory

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
    keep = ~np.asarray(pixels.out_of_field, dtype=bool) & np.asarray(style.drawn, dtype=bool)[rows]
    rows, bx, by = rows[keep], bx[keep], by[keep]
    shapes = {name: float(k) for k, name in enumerate(PLOT_SHAPES)}
    return CatalogPoints(
        key, layer.id, rows, np.column_stack([bx, by]), _hex_rgba(style.color[rows]),
        np.asarray(style.size[rows], dtype=np.float32), np.array([shapes[x] for x in style.shape[rows]], np.float32),
        epoch=epoch, propagated=propagated, epoch_source=source, warnings=warnings_,
        seconds=time.perf_counter() - start)


class SkyRenderer:
    """Interfaccia di disegno (41 §3.13, §7); in questo sprint solo il piano dello sfondo e la trasformazione.

    ``upload_texture``: immagine RGBA a 8 bit della finestra, riga 0 = riga in alto sullo schermo.
    ``set_transform``: scala ``k`` e traslazione ``(tx, ty)`` in pixel fisici: il pixel ``q`` dell'immagine va
    sullo schermo in ``k * q + t`` (solo disegno, 41 §3.4). ``set_night``: modalità notte rossa (luminosità in
    scala di rossi, trasformazione di disegno).
    """

    def widget(self) -> QWidget:
        raise NotImplementedError

    def upload_texture(self, rgba: np.ndarray) -> None:
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
    catalog = Signal(object, object)  # chiave, CatalogPoints o ResultMessage (errore del modulo)


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
            except HiPSError as exc:
                self.bridge.failed.emit(generation, exc.code, str(exc))
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

    def read(self, passive: Callable[..., object], name: str, params: Mapping) -> None:
        """Lettura passiva (``cursor.read``, 41 §3.11) nel gruppo di thread dei tile; il risultato torna al thread
        principale con ``bridge.cursor`` (un errore imprevisto diventa un risultato in errore, mai un'eccezione)."""
        from astrotwo.core.commands import CommandResult

        def run() -> None:
            try:
                result = passive(name, params, "mouse")
            except Exception as exc:  # noqa: BLE001 - il gruppo di thread non si ferma mai
                result = CommandResult("error", error=ResultMessage("UI_COMMAND_FAILED", f"{type(exc).__name__}: {exc}"))
            self.bridge.cursor.emit(result)

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

    def wait(self, msecs: int = 30000) -> bool:
        return self.pool.waitForDone(msecs)


def colorize(view_tile, display: Mapping | None):
    """Tile FITS → colori RGBA con ``set_display`` dell'11 (41 §3.7): nessun calcolo qui, solo la chiamata al modulo.
    I tile JPEG/PNG hanno già i colori. Pixel non finiti = trasparenti (``set_display``)."""
    if view_tile.format != "fits":
        return view_tile
    from astrotwo.core.images_fits import set_display

    if display is None or display.get("vmin") is None or display.get("vmax") is None:
        raise HiPSError("HIPS_DISPLAY_UNKNOWN", "limiti di colore del survey non noti: i tile FITS non si disegnano")
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
    il passo; fuori dall'immagine, trasparente; ``visible`` e ``opacity`` del livello valgono qui."""
    rows, cols = geometry.shape
    canvas = np.zeros((rows, cols, 4), dtype=np.uint8)
    plane = image.derived.get("plane")
    if plane is None or not image.visible:
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
        if image.opacity < 1.0:
            canvas[..., 3] = (canvas[..., 3] * image.opacity).astype(np.uint8)
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
        self.zoom_in_button = self._zoom_button("zoomIn", +1)
        self.zoom_out_button = self._zoom_button("zoomOut", -1)
        self.tiles = TilePool(cache)
        self.tiles.bridge.sampled.connect(self._sampled)
        self.tiles.bridge.tile.connect(self._tile)
        self.tiles.bridge.failed.connect(self._failed)
        self.tiles.bridge.done.connect(self._tile_done)
        self.tiles.bridge.cursor.connect(self._cursor_done)
        self.tiles.bridge.catalog.connect(self._catalog_done)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)  # Esc chiude la scheda della sorgente
        self.card_texts: Mapping[str, str] = DEFAULT_CARD_TEXTS  # tradotti dalla finestra principale (40)
        self.card = QLabel(self)
        self.card.setObjectName("sourceCard")
        self.card.setTextFormat(Qt.TextFormat.RichText)
        self.card.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.card.hide()
        self._card: tuple[str, int, Mapping] | None = None  # livello, riga, scheda di catalog.select (05)
        self._night = False
        self.screen_geometry = None  # geometria del disegno sullo schermo (la sua finestra è lo spazio dei punti)
        self.catalog_layers: tuple = ()
        self.base_image = None  # livello dell'immagine base (epoca di visualizzazione, D10-2)
        self.catalog_cache: dict[tuple, CatalogPoints] = {}
        self._catalog_pending: set[tuple] = set()
        self.point_sets: tuple[PointSet, ...] = ()
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
        self.image_key: tuple | None = None  # (livello, piano di colori, visibilità, opacità) dell'immagine disegnata
        self.overlay_texts: Mapping[str, str] = DEFAULT_OVERLAY_TEXTS  # tradotti dalla finestra principale (40)
        self.overlay: Overlay | None = None
        self.display: Mapping | None = None  # limiti, palette e funzione di trasferimento del survey FITS (livello)
        self.field: Mapping | None = None  # field_of_view dell'ultimo comando di vista
        self.sampling = None
        self.canvas: np.ndarray | None = None  # RGBA, righe nell'ordine della finestra (riga 0 = sud, y del 10)
        self.k, self.tx, self.ty = 1.0, 0.0, 0.0
        self._pending: dict[int, tuple[float, float, float] | None] = {}  # generazione → trasformazione inviata
        self._in_flight = 0
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
        layers = [] if image is not None else state.of_kind("hips")  # con un'immagine aperta lo sfondo non si disegna
        layer = layers[-1] if layers else None
        self.view = view
        self.catalog_layers = state.of_kind("catalog")
        self.base_image = image
        changed_geometry = view.geometry is not self.geometry
        changed_survey = (layer.id if layer else None) != self.survey_layer
        image_key = None if image is None else (image.id, id(image.derived.get("plane")), image.visible, image.opacity)
        changed_image = image_key != self.image_key
        if not changed_geometry:
            self.show_overlay()  # griglia, indicatore o barra cambiati sulla stessa geometria (view.set_grid, ...)
        if not (changed_geometry or changed_survey or changed_image):
            self.update_catalogs()
            return
        self.geometry = view.geometry
        self.update_catalogs()
        self.service = layer.data if layer else None
        self.display = layer.display if layer else None
        self.survey_layer = layer.id if layer else None
        previous_image, self.image_key = self.image_key, image_key
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
        if self.geometry is None or self.service is None or self.service.tile_width is None:
            # nessun pixel da disegnare (nessun survey o HiPS catalogo) o immagine FITS come base: niente
            # campionamento dei tile, la trasformazione residua del gesto si chiude subito e griglia e indicatore
            # seguono la nuova geometria
            self.sampling = None
            if changed_geometry and self.geometry is not None:
                self._settle_transform(gen, *self.geometry.shape)
                self.renderer.set_transform(self.k, self.tx, self.ty)
            if not changed_geometry:
                self._pending.pop(gen, None)
            self.screen_geometry = self.geometry
            self.refresh_points()
            if self.geometry is not None and image is not None:
                self.canvas = sample_image(self.geometry, image)
                self._upload()
            elif previous_image is not None and self.geometry is not None:
                self.canvas = np.zeros((*self.geometry.shape, 4), dtype=np.uint8)  # immagine tolta: vista vuota
                self._upload()
            self.show_overlay()
            return
        self.tiles.sample(gen, self.service, self.geometry, layer.derived.get("coverage"))

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
        self.overlay = None if self.view is None else build_overlay(self.view, self.overlay_texts)
        self.renderer.set_overlay(self.overlay)

    def _sampled(self, gen: int, sampling) -> None:
        if not self.tiles.current(gen):
            return
        rows, cols = sampling.shape
        self.sampling = sampling
        self.canvas = np.zeros((rows, cols, 4), dtype=np.uint8)
        self._settle_transform(gen, rows, cols)
        self._upload()
        self.renderer.set_transform(self.k, self.tx, self.ty)
        self.screen_geometry = self.geometry  # tile e simboli passano alla nuova finestra insieme
        self.refresh_points()
        self.show_overlay()
        if "fits" in self.service.tile_formats[:1] and (self.display is None or self.display.get("vmin") is None):
            self._report("HIPS_DISPLAY_UNKNOWN", f"{self.service.hips_id}: limiti di colore del survey non noti, "
                         "i tile FITS non si disegnano; riaprire il survey indicando vmin e vmax")
            return
        for index in sampling.tiles:
            self._in_flight += 1
            self.tiles.fetch(gen, self.service, sampling, index, self.display)
        self.tiles_changed.emit(self._in_flight)

    def _tile(self, gen: int, view_tile) -> None:
        if not self.tiles.current(gen) or self.canvas is None:
            return  # tile di una finestra superata: scartato
        y0, y1, x0, x1 = view_tile.box
        box = self.canvas[y0:y1, x0:x1]
        values = view_tile.values
        box[view_tile.mask, :3] = values[view_tile.mask][:, :3]
        box[view_tile.mask, 3] = values[view_tile.mask][:, 3] if values.shape[-1] == 4 else 255
        self._upload()

    def _failed(self, gen: int, code: str, text: str) -> None:
        if self.tiles.current(gen):
            self._report(code, text)

    def _tile_done(self, gen: int) -> None:
        self._in_flight = max(0, self._in_flight - 1)
        self.tiles_changed.emit(self._in_flight)

    def _report(self, code: str, text: str) -> None:
        key = (self.survey_layer or "", code)
        if key not in self._reported:  # un solo messaggio per survey e codice, non uno per tile (41 §3.7)
            self._reported.add(key)
            self.message.emit(ResultMessage(code, text))

    def _upload(self) -> None:
        # Riga 0 della finestra = sud (asse y del WCS verso nord): sullo schermo va in basso.
        self.renderer.upload_texture(np.ascontiguousarray(self.canvas[::-1]))

    def set_night(self, night: bool) -> None:
        self._night = bool(night)
        self.renderer.set_night(night)
        self._style_card()

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
            return
        self.catalog_cache[key] = result
        for message in result.warnings:  # epoche diverse: una volta per livello e immagine (41 §3.8)
            self._report_once((key[0][0], message.code, key[0][4]), message)
        self.refresh_points()

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
                lines.append(f"⚠ {html.escape(message.text)}")
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
        if event.key() == Qt.Key.Key_Escape and self._card is not None:
            self.hide_card()
            event.accept()
            return
        super().keyPressEvent(event)

    # --- gesti (41 §3.4, 05 §3.3) --------------------------------------------------------

    def _gesture_step(self) -> None:
        self.renderer.set_transform(self.k, self.tx, self.ty)
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
            self._drag = self._press = event.position()
            self._dragging = False
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
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
