# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Implementazione OpenGL dell'interfaccia di disegno del 41 (``SkyRenderer``) su ``QOpenGLWidget``.

OpenGL 4.1 core profile (il massimo su macOS), solo con le funzioni incluse in PySide6 (41 §3.13). Sprint 4a: il
piano dello sfondo HiPS come una texture, traslazione e scala del gesto come uniformi del programma di disegno,
modalità notte rossa nel programma di disegno (luminosità in scala di rossi: trasformazione di disegno).
Sprint 4c: sopra il piano, griglia delle coordinate, indicatore del nord e barra di scala con ``QPainter`` sullo
stesso widget (nessun numero calcolato qui: punti e testi arrivano già pronti da ``Overlay``).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QOpenGLContext, QPainter, QPen, QPolygonF, QSurfaceFormat
from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram, QOpenGLTexture,
                              QOpenGLVertexArrayObject)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from astrotwo.ui.sky_viewer import Overlay, SkyRenderer

#: Versione minima di OpenGL (41 §3.13); sotto, ``GL_UNAVAILABLE`` (41 §10, nessun ripiego nella v1).
GL_VERSION = (4, 1)
# Costanti di OpenGL (specifica OpenGL 4.1): PySide6 non le esporta senza PyOpenGL.
_GL_FLOAT = 0x1406
_GL_TRIANGLE_STRIP = 0x0005
_GL_COLOR_BUFFER_BIT = 0x4000
_GL_BLEND = 0x0BE2
_GL_SRC_ALPHA = 0x0302
_GL_ONE_MINUS_SRC_ALPHA = 0x0303

_VERTEX = """#version 410 core
layout(location = 0) in vec2 corner;  // (0, 0) in alto a sinistra, (1, 1) in basso a destra
uniform vec2 image_size;              // pixel fisici dell'immagine
uniform vec3 transform;               // k, tx, ty: schermo = k * pixel + t (pixel fisici)
uniform vec2 viewport;                // pixel fisici del widget
out vec2 uv;
void main() {
    vec2 screen = transform.x * corner * image_size + transform.yz;
    vec2 ndc = screen / viewport * 2.0 - 1.0;
    gl_Position = vec4(ndc.x, -ndc.y, 0.0, 1.0);
    uv = corner;
}
"""

_FRAGMENT = """#version 410 core
in vec2 uv;
uniform sampler2D image;
uniform bool night;
out vec4 color;
void main() {
    vec4 c = texture(image, uv);
    if (night) {
        float lum = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));  // luminanza (Rec. 709) portata sul rosso
        c = vec4(lum, 0.0, 0.0, c.a);
    }
    color = c;
}
"""

#: Fondo del cielo dove non ci sono dati (stesso tono dell'area del cielo del 40 §3.11; nero in modalità notte).
_CLEAR = (0x05 / 255, 0x07 / 255, 0x0C / 255)


#: Colori di griglia, testi, indicatore e barra (RGBA): il cielo è scuro in ogni tema; in modalità notte rossa solo
#: rossi (41 §3.11). "stale" = durante un gesto (valori dell'ultimo comando di vista, 41 §3.18).
_PALETTE = {
    False: {"grid": QColor(150, 195, 255, 120), "text": QColor(215, 228, 255, 235), "mark": QColor(240, 244, 250, 240),
            "stale": QColor(150, 150, 150, 200)},
    # rossi puri (verde e blu a 0), come il piano del cielo in modalità notte (programma di disegno)
    True: {"grid": QColor(190, 0, 0, 150), "text": QColor(235, 0, 0, 240), "mark": QColor(235, 0, 0, 240),
           "stale": QColor(125, 0, 0, 220)},
}
_SHADOW = QColor(0, 0, 0, 170)
#: Dimensioni in pixel logici (disegno): margine dell'angolo, frecce di nord ed est (41 §3.18, scelte minori 10 e 11).
_MARGIN = 16
_ARROW = 40
_ARROW_HEAD = 6
#: Angolo in basso a sinistra occupato da indicatore e barra (pixel logici): le etichette della griglia non ci entrano.
_CORNER_WIDTH = 2 * _ARROW + 30
_CORNER_HEIGHT = 30 + 2 * _ARROW + 30


def surface_format() -> QSurfaceFormat:
    fmt = QSurfaceFormat()
    fmt.setVersion(*GL_VERSION)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    return fmt


class GlSkyRenderer(QOpenGLWidget, SkyRenderer):
    """``SkyRenderer`` su ``QOpenGLWidget``: una texture per il piano dello sfondo, trasformazione sulla GPU."""

    failed = Signal(str, str)  # codice, testo (GL_UNAVAILABLE)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFormat(surface_format())
        self._image: QImage | None = None
        self._dirty = False
        self._texture: QOpenGLTexture | None = None
        self._transform = (1.0, 0.0, 0.0)
        self._night = False
        self._overlay: Overlay | None = None
        self.available = True
        self.program: QOpenGLShaderProgram | None = None

    # --- interfaccia SkyRenderer ---------------------------------------------------------

    def widget(self):
        return self

    def upload_texture(self, rgba: np.ndarray) -> None:
        rows, cols = rgba.shape[:2]
        data = np.ascontiguousarray(rgba, dtype=np.uint8)
        self._image = QImage(data.data, cols, rows, 4 * cols, QImage.Format.Format_RGBA8888).copy()
        self._dirty = True
        self.update()

    def set_transform(self, k: float, tx: float, ty: float) -> None:
        self._transform = (float(k), float(tx), float(ty))
        self.update()

    def set_night(self, night: bool) -> None:
        self._night = bool(night)
        self.update()

    def set_overlay(self, overlay: Overlay | None) -> None:
        self._overlay = overlay
        self.update()

    def render_offscreen(self) -> QImage:
        """Immagine del disegno (pixel fisici), per i test ``gl`` e per il PNG (sprint successivo)."""
        return self.grabFramebuffer()

    # --- QOpenGLWidget -------------------------------------------------------------------

    def initializeGL(self) -> None:  # noqa: N802 - nome di Qt
        fmt = self.context().format() if self.context() is not None else None
        version = (fmt.majorVersion(), fmt.minorVersion()) if fmt is not None else (0, 0)
        if version < GL_VERSION or not QOpenGLContext.currentContext():
            self._unavailable(f"OpenGL {version[0]}.{version[1]}: serve OpenGL {GL_VERSION[0]}.{GL_VERSION[1]} "
                              "core profile; visualizzatore non disponibile")
            return
        program = QOpenGLShaderProgram(self)
        ok = (program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, _VERTEX)
              and program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, _FRAGMENT)
              and program.link())
        if not ok:
            self._unavailable(f"programma di disegno non compilato: {program.log()}")
            return
        self.program = program
        self.context().aboutToBeDestroyed.connect(self._cleanup)
        self.vao = QOpenGLVertexArrayObject(self)
        self.vao.create()
        self.vao.bind()
        corners = np.array([0, 0, 1, 0, 0, 1, 1, 1], dtype=np.float32)
        self.vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self.vbo.create()
        self.vbo.bind()
        self.vbo.allocate(corners.tobytes(), corners.nbytes)
        program.bind()
        program.enableAttributeArray(0)
        program.setAttributeBuffer(0, _GL_FLOAT, 0, 2)
        program.release()
        self.vao.release()
        self.vbo.release()

    def _cleanup(self) -> None:
        """Texture distrutta con il suo contesto attivo (chiusura della finestra)."""
        if self._texture is not None:
            self.makeCurrent()
            self._texture.destroy()
            self._texture = None
            self.doneCurrent()

    def _unavailable(self, text: str) -> None:
        self.available = False
        self.failed.emit("GL_UNAVAILABLE", text)

    def paintGL(self) -> None:  # noqa: N802
        f = self.context().functions()
        clear = (0.0, 0.0, 0.0) if self._night else _CLEAR
        f.glClearColor(*clear, 1.0)
        f.glClear(_GL_COLOR_BUFFER_BIT)
        if self.program is not None and self._image is not None:
            self._paint_plane(f)
        if self._overlay is not None:
            self._paint_overlay(self._overlay)

    def _paint_plane(self, f) -> None:
        if self._dirty:
            if self._texture is not None:
                self._texture.destroy()
            self._texture = QOpenGLTexture(self._image, QOpenGLTexture.MipMapGeneration.DontGenerateMipMaps)
            self._texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            self._texture.setMagnificationFilter(QOpenGLTexture.Filter.Nearest)
            self._texture.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
            self._dirty = False
        ratio = self.devicePixelRatioF()
        f.glEnable(_GL_BLEND)
        f.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
        self.program.bind()
        self.program.setUniformValue("image_size", float(self._image.width()), float(self._image.height()))
        self.program.setUniformValue("transform", *self._transform)
        self.program.setUniformValue("viewport", float(self.width() * ratio), float(self.height() * ratio))
        self.program.setUniformValue("night", self._night)
        self.program.setUniformValue("image", 0)
        self._texture.bind(0)
        self.vao.bind()
        f.glDrawArrays(_GL_TRIANGLE_STRIP, 0, 4)
        self.vao.release()
        self._texture.release()
        self.program.release()

    # --- griglia, indicatore, barra ------------------------------------------------------

    def _paint_overlay(self, overlay: Overlay) -> None:
        ratio = self.devicePixelRatioF()
        k, tx, ty = self._transform
        colors = _PALETTE[self._night]
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            font = painter.font()
            font.setPointSizeF(max(8.0, font.pointSizeF() * 0.95))
            painter.setFont(font)
            metrics = QFontMetricsF(font)

            def to_screen(x: float, y: float) -> QPointF:  # spazio del disegno → pixel logici (solo disegno, 41 §3.4)
                return QPointF((k * x + tx) / ratio, (k * y + ty) / ratio)

            pen = QPen(colors["grid"], 1.0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for line in overlay.grid_lines:
                painter.drawPolyline(QPolygonF([to_screen(float(x), float(y)) for x, y in line]))
            # etichette: si scartano quelle che si sovrappongono a una già scritta o all'angolo di indicatore e barra
            taken = [QRectF(0, self.height() - (_CORNER_HEIGHT + _MARGIN), _CORNER_WIDTH + _MARGIN,
                            _CORNER_HEIGHT + _MARGIN)]
            for label in overlay.grid_labels:
                at = to_screen(label.x, label.y)
                width = metrics.horizontalAdvance(label.text)
                x = at.x() - width / 2 if label.side == "top" else at.x() + 5
                y = at.y() + metrics.ascent() + 3 if label.side == "top" else at.y() - 3
                x = min(max(x, 3.0), max(3.0, self.width() - width - 3.0))  # il testo resta dentro la vista
                box = QRectF(x - 2, y - metrics.ascent() - 1, width + 4, metrics.height() + 2)
                if any(box.intersects(other) for other in taken):
                    continue
                taken.append(box)
                self._text(painter, x, y, label.text, colors["text"])
            # indicatore e barra: fissi nell'angolo, in grigio mentre il gesto è in corso
            moving = self._transform != (1.0, 0.0, 0.0)
            mark = colors["stale"] if moving else colors["mark"]
            h = self.height()
            origin_x, bottom = float(_MARGIN), h - float(_MARGIN)
            if overlay.bar_pixels is not None:
                length = overlay.bar_pixels / ratio
                self._line(painter, mark, origin_x, bottom, origin_x + length, bottom)
                self._line(painter, mark, origin_x, bottom - 4, origin_x, bottom + 4)
                self._line(painter, mark, origin_x + length, bottom - 4, origin_x + length, bottom + 4)
                self._text(painter, origin_x, bottom - 8, overlay.bar_text or "", mark)
            if overlay.compass_shown:
                cx, cy = origin_x + _ARROW + 14, bottom - 30 - _ARROW - 14
                if overlay.north is None or overlay.east is None:
                    self._text(painter, origin_x, cy, overlay.pole_text or "", mark)
                else:
                    for name, (vx, vy) in (("N", overlay.north), ("E", overlay.east)):
                        ex, ey = cx + _ARROW * vx, cy - _ARROW * vy  # y della finestra verso il nord = in su
                        self._line(painter, mark, cx, cy, ex, ey)
                        # punta: due tratti a ±150° rispetto alla direzione della freccia
                        for sign in (1.0, -1.0):
                            hx = -vx * 0.866 + sign * vy * 0.5
                            hy = -vy * 0.866 - sign * vx * 0.5
                            self._line(painter, mark, ex, ey, ex + _ARROW_HEAD * hx, ey - _ARROW_HEAD * hy)
                        tx_, ty_ = ex + 10 * vx, ey - 10 * vy
                        self._text(painter, tx_ - metrics.horizontalAdvance(name) / 2,
                                   ty_ + metrics.ascent() / 2 - 1, name, mark)
        finally:
            painter.end()

    @staticmethod
    def _line(painter: QPainter, color: QColor, x0: float, y0: float, x1: float, y1: float) -> None:
        for dx, color_ in ((1.0, _SHADOW), (0.0, color)):
            pen = QPen(color_, 1.6)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawLine(QPointF(x0 + dx, y0 + dx), QPointF(x1 + dx, y1 + dx))

    @staticmethod
    def _text(painter: QPainter, x: float, y: float, text: str, color: QColor) -> None:
        painter.setPen(_SHADOW)
        painter.drawText(QPointF(x + 1, y + 1), text)
        painter.setPen(color)
        painter.drawText(QPointF(x, y), text)
