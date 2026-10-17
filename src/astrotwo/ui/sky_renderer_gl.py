# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Implementazione OpenGL dell'interfaccia di disegno del 41 (``SkyRenderer``) su ``QOpenGLWidget``.

OpenGL 4.1 core profile (il massimo su macOS), solo con le funzioni incluse in PySide6 (41 §3.13). Sprint 4a: il
piano dello sfondo HiPS come una texture, traslazione e scala del gesto come uniformi del programma di disegno,
modalità notte rossa nel programma di disegno (luminosità in scala di rossi: trasformazione di disegno).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtGui import QImage, QOpenGLContext, QSurfaceFormat
from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram, QOpenGLTexture,
                              QOpenGLVertexArrayObject)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from astrotwo.ui.sky_viewer import SkyRenderer

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
        if self.program is None or self._image is None:
            return
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
