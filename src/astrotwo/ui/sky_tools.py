# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Strumenti del cielo del 41 (§3.12, §3.19, sprint 4g): misura della distanza e puntatore Simbad.

Il calcolo non è qui: la distanza la fa ``measure.distance`` del 05 (``angular_distance`` del 17) e l'oggetto Simbad
``simbad.pointer`` (``simbad_pointer`` del 14); qui si traducono i gesti in comandi e si disegna quello che i
comandi restituiscono. I punti dello schermo diventano pixel della finestra disegnata con la stessa trasformazione
del disegno (``SkyViewer.window_position``), quindi anche durante un gesto.
"""

from __future__ import annotations

import html
import urllib.parse
from collections.abc import Mapping

import astropy.units as u
import numpy as np
from PySide6.QtCore import QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QSpinBox, QWidget

from astrotwo.core.commands import ResultMessage, quantity_json, sky_json

__all__ = [
    "DEFAULT_TOOL_TEXTS",
    "DISTANCE_DEFAULTS",
    "DISTANCE_UNITS",
    "SIMBAD_LINK_PREFIX",
    "SIMBAD_RADIUS_PIXELS",
    "SIMBAD_STOP_MS",
    "DistanceOptionsBar",
    "DistanceTool",
    "MeasureOverlay",
    "SimbadPointerTool",
    "distance_text",
    "simbad_url",
]

#: Mouse fermo per tanto tempo prima di interrogare Simbad (41 §3.12).
SIMBAD_STOP_MS = 500
#: Raggio del puntatore Simbad in pixel logici, convertito in angolo (41 §3.12).
SIMBAD_RADIUS_PIXELS = 12.0
#: Si apre solo una pagina di Simbad (41 §3.19).
SIMBAD_LINK_PREFIX = "https://simbad.cds.unistra.fr/"
#: Magnitudini scritte nel riquadro (le altre restano nel risultato del comando, 41 §3.19).
SIMBAD_MAX_MAGNITUDES = 8
#: Cifre significative dell'etichetta di una misura (41 §3.19, scelta minore).
LABEL_SIGNIFICANT_DIGITS = 4
#: Unità offerte dallo strumento: nome di astropy → simbolo mostrato.
DISTANCE_UNITS = {"arcsec": "″", "arcmin": "′", "deg": "°"}
#: Opzioni iniziali della distanza (41 §3.12): unità ′, nessun aggancio, finestra del centroide 15 pixel.
DISTANCE_DEFAULTS = {"unit": "arcmin", "snap": False, "box_size": 15}

DEFAULT_TOOL_TEXTS = {
    "unit": "Unit", "snap": "Snap to centroid", "snap_needs_image": "Needs an image as the base of the view",
    "box": "Box (px)", "box_tip": "Centroid box size in pixels (odd, 3 or more)",
    "simbad_none": "No SIMBAD object within %1", "simbad_citations": "%1 citations",
    "simbad_separation": "%1 from the pointer", "simbad_system_unknown": "system not declared",
    "simbad_more": "+%1 more magnitudes (in the command result)", "simbad_link": "SIMBAD page",
    "simbad_retrieved": "retrieved %1", "simbad_from": "source %1", "simbad_error": "SIMBAD: %1",
}

_MEASURE_INK = "#f0e442"  # giallo di Okabe e Ito: leggibile su cielo scuro e chiaro
_NIGHT_INK = "#ff2020"


def distance_text(value: u.Quantity) -> str:
    """Etichetta di una misura: ``LABEL_SIGNIFICANT_DIGITS`` cifre significative e il simbolo dell'unità (41 §3.19).

    È solo scrittura del valore del 17: il valore pieno e l'unità restano nel livello e nel risultato."""
    number = np.format_float_positional(float(value.value), precision=LABEL_SIGNIFICANT_DIGITS, unique=False,
                                        fractional=False, trim="-")
    name = value.unit.to_string()
    return f"{number}{DISTANCE_UNITS.get(name, ' ' + name)}"


def simbad_url(main_id: str) -> str:
    """Pagina di Simbad dell'oggetto (solo l'indirizzo, nessun dato)."""
    return f"{SIMBAD_LINK_PREFIX}simbad/sim-id?Ident={urllib.parse.quote(main_id)}"


class MeasureOverlay(QWidget):
    """Widget trasparente sopra il cielo: segmenti ed etichette dei livelli ``measure`` e anteprima del gesto.

    Disegna con ``QPainter`` (41 §3.13); legge dal visualizzatore stato, geometria e trasformazione del gesto, così
    segue spostamento e zoom. Non riceve il mouse."""

    def __init__(self, viewer) -> None:
        super().__init__(viewer)
        self.viewer = viewer
        self.setObjectName("measureOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.preview: tuple[QPointF, QPointF] | None = None  # punti dello schermo (pixel logici) del gesto in corso

    def segments(self) -> list[tuple[QPointF, QPointF, str, float]]:
        """Segmenti dei livelli visibili in pixel logici dello schermo, con l'etichetta e l'opacità del livello."""
        viewer = self.viewer
        geometry = viewer.screen_geometry
        out = []
        if geometry is None or not viewer._has_sky(geometry):
            return out
        r = viewer.ratio()
        rows = geometry.shape[0]
        for layer in viewer.layers:
            data = layer.data
            if layer.kind != "measure" or not layer.visible or not hasattr(data, "p1"):
                continue
            ends = [geometry.sky_to_window(point) for point in (data.p1, data.p2)]
            wx, wy = np.array([e[0] for e in ends], dtype=float), np.array([e[1] for e in ends], dtype=float)
            if not np.all(np.isfinite(wx)) or not np.all(np.isfinite(wy)):
                continue
            sx = (viewer.k * (np.asarray(wx) + 0.5) + viewer.tx) / r
            sy = (viewer.k * (rows - np.asarray(wy) - 0.5) + viewer.ty) / r
            out.append((QPointF(sx[0], sy[0]), QPointF(sx[1], sy[1]), distance_text(data.value),
                        float(layer.opacity)))
        return out

    def paintEvent(self, event) -> None:  # noqa: N802
        night = self.viewer._night
        color = QColor(_NIGHT_INK if night else _MEASURE_INK)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(self.font())
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetricsF(font)
        for a, b, text, opacity in self.segments():
            color.setAlphaF(max(0.0, min(1.0, opacity)))
            self._segment(painter, metrics, color, a, b, text)
        if self.preview is not None:
            color.setAlphaF(0.7)
            pen = QPen(color, 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(*self._xy(self.preview))
        painter.end()

    @staticmethod
    def _xy(points: tuple[QPointF, QPointF]) -> tuple[float, float, float, float]:
        return points[0].x(), points[0].y(), points[1].x(), points[1].y()

    @staticmethod
    def _segment(painter: QPainter, metrics: QFontMetricsF, color: QColor, a: QPointF, b: QPointF, text: str) -> None:
        painter.setPen(QPen(color, 2.0))
        painter.drawLine(a, b)
        for end in (a, b):  # estremi: due piccole croci
            painter.drawLine(QPointF(end.x() - 4, end.y()), QPointF(end.x() + 4, end.y()))
            painter.drawLine(QPointF(end.x(), end.y() - 4), QPointF(end.x(), end.y() + 4))
        middle = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
        box = metrics.boundingRect(text).adjusted(-4, -2, 4, 2)
        box.moveCenter(QPointF(middle.x(), middle.y() - box.height()))
        shade = QColor(8, 10, 16, 200)
        painter.fillRect(box, shade)
        painter.drawText(box, int(Qt.AlignmentFlag.AlignCenter), text)


class DistanceOptionsBar(QFrame):
    """Barra delle opzioni della distanza (41 §3.19): unità, aggancio al centroide, finestra del centroide."""

    def __init__(self, viewer) -> None:
        super().__init__(viewer)
        self.viewer = viewer
        self.setObjectName("distanceOptions")
        t = viewer.tool_texts
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self.unit_label = QLabel(t["unit"], self)
        self.unit = QComboBox(self)
        self.unit.setObjectName("distanceUnit")
        for name, symbol in DISTANCE_UNITS.items():
            self.unit.addItem(symbol, name)
        self.snap = QCheckBox(t["snap"], self)
        self.snap.setObjectName("distanceSnap")
        self.box_label = QLabel(t["box"], self)
        self.box = QSpinBox(self)
        self.box.setObjectName("distanceBox")
        self.box.setRange(3, 201)
        self.box.setSingleStep(2)
        self.box.setToolTip(t["box_tip"])
        for widget in (self.unit_label, self.unit, self.snap, self.box_label, self.box):
            layout.addWidget(widget)
            widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.unit.currentIndexChanged.connect(lambda _i: self._changed("tools/distance_unit", self.unit.currentData()))
        self.snap.toggled.connect(lambda on: self._changed("tools/distance_snap", "true" if on else "false"))
        self.box.valueChanged.connect(self._box_changed)
        self.hide()

    def _changed(self, key: str, value: str) -> None:
        if not self.viewer._loading_options:
            self.viewer.submit("prefs.set", {"key": key, "value": value}, source="mouse")

    def _box_changed(self, value: int) -> None:
        if value % 2 == 0:  # la finestra del centroide è dispari (11): si porta al dispari successivo
            self.box.setValue(value + 1)
            return
        self._changed("tools/distance_box_size", str(value))

    def show_options(self, options: Mapping, image_base: bool) -> None:
        """Valori correnti; l'aggancio c'è solo con un'immagine come base (altrimenti spento e disattivato)."""
        viewer = self.viewer
        viewer._loading_options = True
        try:
            self.unit.setCurrentIndex(self.unit.findData(options["unit"]))
            self.box.setValue(int(options["box_size"]))
            self.snap.setChecked(bool(options["snap"]) and image_base)
        finally:
            viewer._loading_options = False
        self.snap.setEnabled(image_base)
        self.snap.setToolTip("" if image_base else viewer.tool_texts["snap_needs_image"])
        self.box.setEnabled(image_base)
        self.adjustSize()


class DistanceTool:
    """Misura della distanza (41 §3.12, §3.19): trascinamento da p1 a p2 o due clic → ``measure.distance``."""

    def __init__(self, viewer) -> None:
        self.viewer = viewer
        self.options = dict(DISTANCE_DEFAULTS)
        self.pressed: QPointF | None = None
        self.first: QPointF | None = None  # primo punto di una misura a due clic

    def reset(self) -> None:
        self.pressed = self.first = None
        self.viewer.measure_overlay.preview = None
        self.viewer.measure_overlay.update()

    def press(self, at: QPointF) -> None:
        self.pressed = at

    def move(self, at: QPointF) -> None:
        start = self.pressed or self.first
        if start is not None:
            self.viewer.measure_overlay.preview = (start, at)
            self.viewer.measure_overlay.update()

    def release(self, at: QPointF) -> None:
        from astrotwo.ui.sky_viewer import CLICK_SLOP

        pressed, self.pressed = self.pressed, None
        if pressed is None:
            return
        if np.hypot(at.x() - pressed.x(), at.y() - pressed.y()) >= CLICK_SLOP:
            self.first = None
            self.finish(pressed, at)
        elif self.first is None:
            self.first = pressed
            self.move(at)
        else:
            first, self.first = self.first, None
            self.finish(first, at)

    def cancel(self) -> bool:
        """Esc: toglie il primo punto. ``True`` se c'era qualcosa da annullare."""
        had = self.first is not None or self.pressed is not None
        self.reset()
        return had

    def finish(self, a: QPointF, b: QPointF) -> None:
        """Comando ``measure.distance`` per i due punti (pixel logici dello schermo)."""
        viewer = self.viewer
        self.reset()
        geometry = viewer.geometry
        if geometry is None or not viewer._has_sky(geometry):
            viewer.message.emit(ResultMessage("VIEW_NO_WCS", "immagine senza WCS valido: la distanza angolare "
                                              "non è misurabile sulla griglia di pixel"))
            return
        pa, pb = viewer.window_position(a), viewer.window_position(b)
        skies = geometry.window_to_sky([pa["x"], pb["x"]], [pa["y"], pb["y"]])
        if not np.all(np.isfinite(skies.spherical.lon.deg)) or not np.all(np.isfinite(skies.spherical.lat.deg)):
            viewer.message.emit(ResultMessage("OUT_OF_SKY", "fuori dal cielo: un punto non ha coordinate "
                                              "nella proiezione"))
            return
        unit = self.options["unit"]
        image = viewer.base_image
        if image is not None and getattr(image.data, "wcs", None) is not None:
            bx, by = geometry.window_to_base([pa["x"], pb["x"]], [pa["y"], pb["y"]])
            params = {"layer": image.id, "p1": {"x": float(bx[0]), "y": float(by[0]), "convention": "numpy"},
                      "p2": {"x": float(bx[1]), "y": float(by[1]), "convention": "numpy"}, "unit": unit,
                      "snap": bool(self.options["snap"]),
                      "box_size": int(self.options["box_size"]) if self.options["snap"] else None}
        else:  # sfondo HiPS senza immagine: forma cielo del 05 (nessun aggancio)
            params = {"sky1": sky_json(skies[0]), "sky2": sky_json(skies[1]), "unit": unit, "snap": False}
        viewer.submit("measure.distance", params, source="mouse")


class SimbadPointerTool:
    """Puntatore Simbad (41 §3.12, §3.19): mouse fermo 500 ms o clic → ``simbad.pointer`` (passivo, nel gruppo di
    thread dei tile, una richiesta alla volta) e riquadro vicino al cursore."""

    def __init__(self, viewer) -> None:
        self.viewer = viewer
        self.timer = QTimer(viewer)
        self.timer.setSingleShot(True)
        self.timer.setInterval(SIMBAD_STOP_MS)
        self.timer.timeout.connect(self._stopped)
        self.at: QPointF | None = None  # ultima posizione del mouse
        self.asked: QPointF | None = None  # posizione della richiesta in corso o del riquadro mostrato
        self.busy = False
        self.waiting: QPointF | None = None  # ultimo arresto arrivato mentre una richiesta era in corso
        self.card = QLabel(viewer)
        self.card.setObjectName("simbadCard")
        self.card.setTextFormat(Qt.TextFormat.RichText)
        self.card.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.card.setOpenExternalLinks(False)
        self.card.linkActivated.connect(self.open_link)
        self.card.hide()
        self.last_request: dict | None = None  # parametri dell'ultima richiesta, per i test e il riquadro

    # --- gesti ---------------------------------------------------------------------------------

    def move(self, at: QPointF) -> None:
        from astrotwo.ui.sky_viewer import CLICK_SLOP

        self.at = at
        if self.card.isVisible() and self.asked is not None and \
                np.hypot(at.x() - self.asked.x(), at.y() - self.asked.y()) > CLICK_SLOP:
            self.hide()
        self.timer.start()

    def click(self, at: QPointF) -> None:
        """Il clic è un arresto sicuro: la richiesta parte subito."""
        self.at = at
        self.timer.stop()
        self.request(at)

    def leave(self) -> None:
        self.timer.stop()
        self.waiting = None
        self.hide()

    def reset(self) -> None:
        self.leave()

    def _stopped(self) -> None:
        if self.at is not None:
            self.request(self.at)

    def hide(self) -> None:
        self.card.hide()
        self.asked = None

    # --- richiesta -----------------------------------------------------------------------------

    def radius(self, at: QPointF) -> dict | None:
        """12 pixel logici → angolo: centro e un punto a 12 pixel logici portati in cielo con il 10, distanza con
        ``angular_distance`` del 17. ``None`` fuori dal cielo."""
        from astrotwo.core.coordinates_wcs import SkyFrame
        from astrotwo.core.measures import angular_distance

        viewer = self.viewer
        geometry = viewer.geometry
        centre = viewer.window_position(at)
        step = SIMBAD_RADIUS_PIXELS * viewer.ratio() / viewer.k  # pixel logici → pixel della finestra disegnata
        sky = geometry.window_to_sky([centre["x"], centre["x"] + step], [centre["y"], centre["y"]])
        if not np.all(np.isfinite(sky.spherical.lon.deg)) or not np.all(np.isfinite(sky.spherical.lat.deg)):
            return None
        return quantity_json(angular_distance(SkyFrame(coord=sky[0]), SkyFrame(coord=sky[1]), "arcsec").value)

    def request(self, at: QPointF) -> None:
        viewer = self.viewer
        if viewer.passive is None or viewer.geometry is None or viewer.view is None:
            return
        if self.busy:  # una sola richiesta alla volta: vale l'ultimo arresto
            self.waiting = at
            return
        if not viewer._has_sky(viewer.geometry):
            viewer.message.emit(ResultMessage("WCS_INVALID", "WCS assente o non valido: nessuna coordinata celeste"))
            return
        radius = self.radius(at)
        if radius is None:
            viewer.message.emit(ResultMessage("OUT_OF_SKY", "fuori dal cielo: il punto non ha coordinate "
                                              "nella proiezione"))
            return
        self.busy = True
        self.asked = at
        self.last_request = {"position": viewer.window_position(at), "radius": radius}
        viewer.tiles.read(viewer.passive, "simbad.pointer", self.last_request, signal="simbad")

    def done(self, result) -> None:
        """Risultato nel thread principale: riquadro, a meno che sia arrivato un arresto più recente."""
        self.busy = False
        waiting, self.waiting = self.waiting, None
        if waiting is not None:
            self.asked = None
            self.request(waiting)
            return
        if self.viewer.tool != "simbad_pointer" or self.asked is None:
            return
        self.card.setText(self.card_html(result))
        self.card.adjustSize()
        self.style()
        self.card.show()
        self.card.raise_()
        self.place()

    def place(self) -> None:
        viewer = self.viewer
        at = self.asked or QPointF(12, 12)
        x = min(max(at.x() + 16, 4.0), max(4.0, viewer.width() - self.card.width() - 4.0))
        y = min(max(at.y() + 16, 4.0), max(4.0, viewer.height() - self.card.height() - 4.0))
        self.card.move(int(x), int(y))

    def style(self) -> None:
        ink, edge = ("#ff2020", "#7a0000") if self.viewer._night else ("#e8eefc", "#3a4660")
        self.card.setStyleSheet(f"QLabel#simbadCard {{ background: rgba(8, 10, 16, 225); color: {ink}; "
                                f"border: 1px solid {edge}; border-radius: 6px; padding: 8px; }}"
                                f"QLabel#simbadCard a {{ color: {ink}; }}")

    @staticmethod
    def open_link(url: str) -> None:
        """Solo pagine di Simbad (41 §3.19)."""
        if url.startswith(SIMBAD_LINK_PREFIX):
            QDesktopServices.openUrl(QUrl(url))

    def card_html(self, result) -> str:
        """Testo del riquadro: tutto dal risultato di ``simbad.pointer`` (05, 14); le coordinate le scrive
        ``format_coordinates`` del 10 nello stile scelto; nessun valore calcolato qui."""
        from astrotwo.core.coordinates_wcs import format_coordinates

        t = self.viewer.tool_texts
        esc = html.escape
        if result.status == "error" or result.error is not None:
            error = result.error
            return esc("⚠ " + t["simbad_error"].replace("%1", "" if error is None else f"{error.code}: {error.text}"))
        values = result.values
        obj = values.get("object")
        lines: list[str] = []
        if obj is None:
            radius = self.last_request["radius"]
            lines.append(esc(t["simbad_none"].replace("%1", f"{radius['value']:.3g} {radius['unit']}")))
        else:
            head = f"<b>{esc(obj['main_id'])}</b>" + (f" · {esc(obj['otype'])}" if obj.get("otype") else "")
            lines.append(head)
            position = obj["position"]
            style = self.viewer.view.coordinate_format if self.viewer.view is not None else "sexagesimal"
            q = {axis: position[axis]["value"] * u.Unit(position[axis]["unit"]) for axis in ("lon", "lat")}
            lon = format_coordinates(values=q["lon"], frame=position["frame"], axis="lon", style=style).lon[0]
            lat = format_coordinates(values=q["lat"], frame=position["frame"], axis="lat", style=style).lat[0]
            lines.append(esc(f"{position['frame'].upper()} {lon} {lat}"))
            if obj.get("nbref") is not None:
                lines.append(esc(t["simbad_citations"].replace("%1", str(obj["nbref"]))))
            separation = obj["separation"]
            lines.append(esc(t["simbad_separation"].replace("%1", f"{separation['value']:.3g} {separation['unit']}")))
            shown = obj.get("magnitudes", [])[:SIMBAD_MAX_MAGNITUDES]
            for mag in shown:
                text = f"{mag['band']} {mag['value']:.3f}"
                if mag.get("error") is not None:
                    text += f" ± {mag['error']:.3f}"
                text += f" ({mag['system'] or t['simbad_system_unknown']})"
                lines.append(esc(text))
            hidden = len(obj.get("magnitudes", [])) - len(shown)
            if hidden > 0:
                lines.append(esc(t["simbad_more"].replace("%1", str(hidden))))
            url = simbad_url(obj["main_id"])
            lines.append(f'<a href="{esc(url, quote=True)}">{esc(t["simbad_link"])}</a>')
        for message in result.warnings:
            lines.append(f"⚠ {esc(message.text)}")
        for source in result.provenance:
            if source.get("origin"):
                lines.append(esc(t["simbad_from"].replace("%1", str(source["origin"]))))
            if source.get("retrieved_at"):
                lines.append(esc(t["simbad_retrieved"].replace("%1", str(source["retrieved_at"]))))
        return "<br>".join(lines)
