# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Visualizzatore del cielo (41), sprint 4a-4b: sfondo HiPS (a colori o FITS), zoom, spostamento, lettura sotto il mouse.

Nessun numero mostrato nasce qui: la geometria è la ``ViewGeometry`` del 10 (dai comandi di vista del 05), i tile
e il loro campionamento sulla finestra vengono dal 12 (``view_sampling``, ``fetch_tile``, ``fill_view``).
Traslazione e scala dello schermo durante un gesto sono solo disegno (41 §3.4); a fine gesto (300 ms fermo, 05
§3.3) si registrano ``view.set_zoom`` e/o ``view.set_center`` con lo stato finale.

Sfondo HiPS: un solo survey; i tile JPEG/PNG si disegnano com'è, i tile FITS sono portati a colori da
``set_display`` dell'11 con i limiti scelti da ``hips.set_survey`` (campo ``display`` del livello, 41 §3.7). Sotto il
mouse una lettura passiva ``cursor.read`` (05) nel gruppo di thread dei tile, al più una in corso (41 §3.11). I
cataloghi, i livelli e gli strumenti arrivano negli sprint successivi.
"""

from __future__ import annotations

import dataclasses
import os
import sys
import threading
from collections.abc import Callable, Mapping

import astropy.units as u
import numpy as np
from PySide6.QtCore import QEvent, QObject, QPointF, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import QApplication, QToolButton, QVBoxLayout, QWidget

from astrotwo.core.commands import ResultMessage, quantity_json, sky_json
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
    cursor = Signal(object)  # CommandResult di una lettura sotto il mouse


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
        self._cursor_busy = False
        self._cursor_next: QPointF | None = None  # ultima posizione arrivata mentre una lettura era in corso
        self._cursor_inside = False
        self.geometry = None  # ViewGeometry del 10 disegnata (o in preparazione)
        self.view = None  # ViewState corrente
        self.service = None
        self.survey_layer: str | None = None
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
        self.display = layer.display if layer else None
        self.survey_layer = layer.id if layer else None
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
        self._upload()
        self.renderer.set_transform(self.k, self.tx, self.ty)
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
        self.renderer.set_night(night)

    # --- gesti (41 §3.4, 05 §3.3) --------------------------------------------------------

    def _gesture_step(self) -> None:
        self.renderer.set_transform(self.k, self.tx, self.ty)
        self.idle.start()

    def zoom_by(self, factor: float, at: QPointF) -> None:
        """Zoom di ``factor`` (dato in ingresso dal gesto) attorno al punto ``at`` (pixel logici), entro i limiti."""
        if self.view is None or self.view.scale is None:
            debug_input(f"zoom_by ignorato: vista non pronta (view={self.view is not None})")
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
        elif not pixels.isNull():  # trackpad a due dita (fasi Begin/Update/End/Momentum): spostamento (41 §3.16)
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
            self._drag = event.position()
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag is not None:
            pos = event.position()
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
        self._drag = None
        event.accept()

    def _gesture_end(self) -> None:
        """Fine del gesto: ``view.set_zoom`` poi ``view.set_center`` con lo stato finale (05 §3.3)."""
        geometry = self.geometry
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
