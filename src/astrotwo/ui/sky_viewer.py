"""Visualizzatore del cielo (41), sprint 4a: sfondo HiPS di un survey, zoom e spostamento.

Nessun numero mostrato nasce qui: la geometria è la ``ViewGeometry`` del 10 (dai comandi di vista del 05), i tile
e il loro campionamento sulla finestra vengono dal 12 (``view_sampling``, ``fetch_tile``, ``fill_view``).
Traslazione e scala dello schermo durante un gesto sono solo disegno (41 §3.4); a fine gesto (300 ms fermo, 05
§3.3) si registrano ``view.set_zoom`` e/o ``view.set_center`` con lo stato finale.

In questo sprint: un solo sfondo HiPS a colori (JPEG/PNG); i tile FITS (colori con ``set_display`` dell'11), i
cataloghi, i livelli e gli strumenti arrivano negli sprint successivi.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping

import astropy.units as u
import numpy as np
from PySide6.QtCore import QEvent, QObject, QPointF, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from astrotwo.core.commands import ResultMessage, quantity_json, sky_json
from astrotwo.core.hips import DEFAULT_TILE_MEMORY_BYTES, HiPSError, TileMemory

#: Fine del gesto: puntatore fermo per 300 ms (05 §3.3).
GESTURE_IDLE_MS = 300
#: Fattore di zoom per scatto della rotella del mouse (120 unità di ``angleDelta``): 2^(1/4), 4 scatti = raddoppio
#: (41 §3.4, scelta del proprietario del 2026-10-17); sul trackpad lo zoom è il pizzico, due dita spostano.
ZOOM_STEP = 2.0 ** 0.25
#: Scala minima della vista (angolo per pixel della finestra), scelta del proprietario del 2026-10-17.
MIN_SCALE = 0.01 * u.arcsec
#: Larghezza angolare massima della finestra: scala massima = 360° / larghezza in pixel fisici (stessa scelta).
MAX_WIDTH_ANGLE = 360.0 * u.deg
#: Vista iniziale (scelta del proprietario del 2026-10-17): cielo intero centrato su ICRS (0°, 0°).
START_CENTER = {"lon": {"value": 0.0, "unit": "deg"}, "lat": {"value": 0.0, "unit": "deg"}, "frame": "icrs",
                "equinox": None, "obstime": None, "epoch": None,
                "epoch_reason": "epoca delle posizioni non nota (non assunta)"}
#: Thread del gruppo dei tile (41 §3.13, scelta minore 8).
TILE_THREADS = 6


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

    def fetch(self, generation: int, service, sampling, index: int) -> None:
        from astrotwo.core.hips import fetch_tile, fill_view

        def run() -> None:
            try:
                if not self.current(generation):
                    return  # richiesta superata: annullata prima della rete
                try:
                    tile = fetch_tile(service, sampling.order, index, plane=sampling.plane, cache=self.cache,
                                      memory=self.memory)
                    if self.current(generation):
                        self.bridge.tile.emit(generation, fill_view(sampling, tile))
                except Exception as exc:  # noqa: BLE001 - errori del 12/04: zona vuota e un messaggio
                    code = getattr(exc, "code", type(exc).__name__)
                    self.bridge.failed.emit(generation, str(code), str(exc))
            finally:
                self.bridge.done.emit(generation)

        self.pool.start(_Task(run))

    def wait(self, msecs: int = 30000) -> bool:
        return self.pool.waitForDone(msecs)


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


class SkyViewer(QWidget):
    """Widget del cielo (41 §7): tiene la ``ViewGeometry`` corrente, traduce i gesti in comandi, disegna i tile.

    ``submit(name, params, source)`` mette in coda un comando del 05 (la coda del 40).
    """

    message = Signal(object)  # ResultMessage per il pannello Messaggi (un solo messaggio per survey e codice)
    tiles_changed = Signal(int)  # richieste di tile in corso, per la barra di stato
    view_changed = Signal()  # nuova geometria o nuovo survey disegnati (scritta della barra)
    first_shown = Signal()  # la finestra ha la sua dimensione vera: si può chiedere la vista iniziale

    def __init__(self, submit: Callable[..., int], cache=None, renderer: SkyRenderer | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("skyArea")
        self.setMinimumSize(320, 240)
        self.setMouseTracking(False)
        self.submit = submit
        self.renderer = renderer if renderer is not None else DEFAULT_RENDERER()
        child = self.renderer.widget()
        child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(child)
        self.tiles = TilePool(cache)
        self.tiles.bridge.sampled.connect(self._sampled)
        self.tiles.bridge.tile.connect(self._tile)
        self.tiles.bridge.failed.connect(self._failed)
        self.tiles.bridge.done.connect(self._tile_done)
        self.geometry = None  # ViewGeometry del 10 disegnata (o in preparazione)
        self.view = None  # ViewState corrente
        self.service = None
        self.survey_layer: str | None = None
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
        """Dopo ogni comando (riuscito o no): disegna la nuova geometria e il survey attivo, se sono cambiati."""
        if name in ("view.set_center", "view.set_zoom") and self._awaiting:
            self._awaiting -= 1
        if status == "ok" and "field_of_view" in values:
            self.field = values["field_of_view"]  # campo della geometria disegnata, dal 05 con il 10
        if self._awaiting:
            return  # il gesto ha ancora un comando in coda: si disegna lo stato finale
        # ``state`` può essere già più avanti di questo risultato (il thread dei comandi continua): si disegna
        # sempre lo stato più recente e la scritta si aggiorna dopo ogni comando.
        self.show_state(state)
        self.view_changed.emit()

    def show_state(self, state) -> None:
        view = state.view
        layers = state.of_kind("hips")
        layer = layers[-1] if layers else None
        self.view = view
        changed_geometry = view.geometry is not self.geometry
        changed_survey = (layer.id if layer else None) != self.survey_layer
        if not (changed_geometry or changed_survey):
            return
        self.geometry = view.geometry
        self.service = layer.data if layer else None
        self.survey_layer = layer.id if layer else None
        sent = self._submitted if changed_geometry else (1.0, 0.0, 0.0)
        self._submitted = None
        self.tiles.generation += 1
        gen = self.tiles.generation
        self._pending = {gen: sent}
        self.view_changed.emit()
        if self.geometry is None or self.service is None:
            return
        if self.service.tile_width is None:
            return  # HiPS catalogo: niente pixel da disegnare
        self.tiles.sample(gen, self.service, self.geometry, layer.derived.get("coverage"))

    def _sampled(self, gen: int, sampling) -> None:
        if not self.tiles.current(gen):
            return
        rows, cols = sampling.shape
        self.sampling = sampling
        self.canvas = np.zeros((rows, cols, 4), dtype=np.uint8)
        sent = self._pending.pop(gen, None)
        if sent is None:
            self.k, self.tx, self.ty = 1.0, 0.0, 0.0
        else:  # trasformazione residua del gesto continuato dopo l'invio dei comandi (solo disegno)
            ks, txs, tys = sent
            kr = self.k / ks
            self.k, self.tx, self.ty = kr, self.tx - kr * txs, self.ty - kr * tys
        self._upload()
        self.renderer.set_transform(self.k, self.tx, self.ty)
        if "fits" in self.service.tile_formats[:1]:
            self._report("HIPS_FITS_NOT_YET", f"{self.service.hips_id}: i tile FITS si disegnano con set_display "
                         "dell'11 nello sprint successivo del 41; scegliere un survey a colori (JPEG o PNG)")
            return
        for index in sampling.tiles:
            self._in_flight += 1
            self.tiles.fetch(gen, self.service, sampling, index)
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
        self.renderer.set_night(night)

    # --- gesti (41 §3.4, 05 §3.3) --------------------------------------------------------

    def _gesture_step(self) -> None:
        self.renderer.set_transform(self.k, self.tx, self.ty)
        self.idle.start()

    def zoom_by(self, factor: float, at: QPointF) -> None:
        """Zoom di ``factor`` (dato in ingresso dal gesto) attorno al punto ``at`` (pixel logici), entro i limiti."""
        if self.view is None or self.view.scale is None:
            return
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

    def pan_by(self, dx: float, dy: float) -> None:
        """Spostamento di ``(dx, dy)`` pixel logici."""
        r = self.ratio()
        self.tx += dx * r
        self.ty += dy * r
        self._moved = True
        self._gesture_step()

    def wheelEvent(self, event) -> None:  # noqa: N802 - nome di Qt
        pixels = event.pixelDelta()
        if not pixels.isNull():  # trackpad a due dita: spostamento (41 §3.16); lo zoom è il pizzico
            self.pan_by(pixels.x(), pixels.y())
        else:
            steps = event.angleDelta().y() / 120.0
            if steps:
                self.zoom_by(ZOOM_STEP ** steps, event.position())
        event.accept()

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.NativeGesture and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
            self.zoom_by(1.0 + event.value(), event.position())  # pizzico sul trackpad
            return True
        return super().event(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = event.position()
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag is not None:
            pos = event.position()
            self.pan_by(pos.x() - self._drag.x(), pos.y() - self._drag.y())
            self._drag = pos
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag = None
        event.accept()

    def _gesture_end(self) -> None:
        """Fine del gesto: ``view.set_zoom`` poi ``view.set_center`` con lo stato finale (05 §3.3)."""
        geometry = self.geometry
        if geometry is None or self.view is None or self.view.scale is None:
            self._zoomed = self._moved = False
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
        if sent:
            self._awaiting += sent
            self._submitted = (self.k, self.tx, self.ty)

    # --- dimensioni ----------------------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._shown:
            self._shown = True
            QTimer.singleShot(0, self.first_shown.emit)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        old, new = event.oldSize(), event.size()
        if not old.isValid() or self.view is None or self.view.window is None:
            return
        # Stesso centro; a fine gesto (300 ms) view.set_center con la nuova finestra (05 §3.2, parametro window).
        self.pan_by((new.width() - old.width()) / 2, (new.height() - old.height()) / 2)
