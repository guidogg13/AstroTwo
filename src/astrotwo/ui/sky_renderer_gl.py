# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Implementazione OpenGL dell'interfaccia di disegno del 41 (``SkyRenderer``) su ``QOpenGLWidget``.

OpenGL 4.1 core profile (il massimo su macOS), solo con le funzioni incluse in PySide6 (41 §3.13). Sprint 4a: il
piano dello sfondo HiPS come una texture, traslazione e scala del gesto come uniformi del programma di disegno,
modalità notte rossa nel programma di disegno (luminosità in scala di rossi: trasformazione di disegno).
Sprint 4c: sopra il piano, griglia delle coordinate, indicatore del nord e barra di scala con ``QPainter`` sullo
stesso widget (nessun numero calcolato qui: punti e testi arrivano già pronti da ``Overlay``).
Sprint 4e: i cataloghi come punti in un buffer della GPU (un vertice per sorgente: posizione, colore, dimensione,
forma), con ``gl_PointSize`` e la forma disegnata nel programma di disegno da ``gl_PointCoord``; anelli della
selezione con ``QPainter``.
Sprint 4f: una texture per piano (sfondo HiPS, immagine) con l'opacità del livello; i MOC come triangoli (riempimento)
e linee (perimetro) in un buffer della GPU con colore per vertice; tutto nell'ordine dei livelli (``set_layers``).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QOpenGLContext, QPainter, QPen, QPolygonF, QSurfaceFormat
from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram, QOpenGLTexture,
                              QOpenGLVertexArrayObject)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from astrotwo.ui.sky_viewer import Overlay, PointSet, PolygonSet, SkyRenderer

#: Versione minima di OpenGL (41 §3.13); sotto, ``GL_UNAVAILABLE`` (41 §10, nessun ripiego nella v1).
GL_VERSION = (4, 1)
# Costanti di OpenGL (specifica OpenGL 4.1): PySide6 non le esporta senza PyOpenGL.
_GL_FLOAT = 0x1406
_GL_TRIANGLE_STRIP = 0x0005
_GL_COLOR_BUFFER_BIT = 0x4000
_GL_BLEND = 0x0BE2
_GL_SRC_ALPHA = 0x0302
_GL_ONE_MINUS_SRC_ALPHA = 0x0303
_GL_POINTS = 0x0000
_GL_PROGRAM_POINT_SIZE = 0x8642
_GL_TRIANGLES = 0x0004
_GL_LINES = 0x0001

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
uniform float opacity;                // opacità del livello (41 §3.5)
out vec4 color;
void main() {
    vec4 c = texture(image, uv);
    if (night) {
        float lum = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));  // luminanza (Rec. 709) portata sul rosso
        c = vec4(lum, 0.0, 0.0, c.a);
    }
    color = vec4(c.rgb, c.a * opacity);
}
"""

#: Simboli dei cataloghi (41 §3.8): un vertice per sorgente = x, y (spazio della finestra disegnata, pixel fisici),
#: r, g, b, a, dimensione (pixel logici), forma (indice in PLOT_SHAPES del 13). Lato del punto = dimensione × rapporto
#: dei pixel + margine per lo spessore del tratto.
_POINT_FLOATS = 8
_POINT_VERTEX = """#version 410 core
layout(location = 0) in vec2 pos;
layout(location = 1) in vec4 rgba;
layout(location = 2) in float size;
layout(location = 3) in float shape;
uniform vec3 transform;   // k, tx, ty: schermo = k * pixel + t (pixel fisici)
uniform vec2 viewport;
uniform float ratio;      // pixel fisici per pixel logico
out vec4 v_color;
out float v_shape;
out float v_side;
void main() {
    vec2 screen = transform.x * pos + transform.yz;
    vec2 ndc = screen / viewport * 2.0 - 1.0;
    gl_Position = vec4(ndc.x, -ndc.y, 0.0, 1.0);
    v_side = size * ratio + 3.0 * ratio;
    gl_PointSize = v_side;
    v_color = rgba;
    v_shape = shape;
}
"""
_POINT_FRAGMENT = """#version 410 core
in vec4 v_color;
in float v_shape;
in float v_side;
uniform bool night;
uniform float ratio;
out vec4 color;
// forme del 13: 0 circle, 1 square, 2 diamond, 3 triangle, 4 cross, 5 plus, 6 dot (contorni, tranne dot)
void main() {
    vec2 p = gl_PointCoord * 2.0 - 1.0;
    p.y = -p.y;                                  // y verso l'alto
    float px = 2.0 / v_side;                     // un pixel fisico in unità del punto
    float r = 1.0 - 1.5 * ratio * px;            // raggio del simbolo dentro il margine
    float half_width = 0.75 * ratio * px;        // metà dello spessore del tratto (1.5 pixel logici)
    float d;
    int s = int(v_shape + 0.5);
    if (s == 0) d = abs(length(p) - r);
    else if (s == 1) d = abs(max(abs(p.x), abs(p.y)) - r * 0.85);
    else if (s == 2) d = abs(abs(p.x) + abs(p.y) - r) * 0.7071;
    else if (s == 3) {
        float e = max(-p.y, max(dot(p, vec2(0.866, 0.5)), dot(p, vec2(-0.866, 0.5))));
        d = abs(e - 0.5 * r);
    } else if (s == 4) d = max(min(abs(p.x - p.y), abs(p.x + p.y)) * 0.7071, max(abs(p.x), abs(p.y)) - r * 0.8);
    else if (s == 5) d = max(min(abs(p.x), abs(p.y)), max(abs(p.x), abs(p.y)) - r);
    else d = max(length(p) - 0.45 * r, 0.0);
    float a = 1.0 - smoothstep(half_width, half_width + px, d);
    if (a <= 0.0) discard;
    vec4 c = v_color;
    if (night) {
        // modalità notte rossa: luminanza (Rec. 709) portata sul rosso, mai sotto metà intensità perché il simbolo
        // si veda sul nero; i cataloghi si distinguono per forma (41 §3.13). Trasformazione di disegno.
        float lum = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
        c = vec4(0.5 + 0.5 * lum, 0.0, 0.0, c.a);
    }
    color = vec4(c.rgb, c.a * a);
}
"""

#: MOC (41 §3.9): un vertice = x, y (spazio della finestra disegnata, pixel fisici), r, g, b, a (opacità già applicata).
_POLY_FLOATS = 6
_POLY_VERTEX = """#version 410 core
layout(location = 0) in vec2 pos;
layout(location = 1) in vec4 rgba;
uniform vec3 transform;   // k, tx, ty: schermo = k * pixel + t (pixel fisici)
uniform vec2 viewport;
out vec4 v_color;
void main() {
    vec2 screen = transform.x * pos + transform.yz;
    vec2 ndc = screen / viewport * 2.0 - 1.0;
    gl_Position = vec4(ndc.x, -ndc.y, 0.0, 1.0);
    v_color = rgba;
}
"""
_POLY_FRAGMENT = """#version 410 core
in vec4 v_color;
uniform bool night;
out vec4 color;
void main() {
    vec4 c = v_color;
    if (night) {
        // come i simboli: luminanza sul rosso, mai sotto metà intensità (trasformazione di disegno)
        float lum = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
        c = vec4(0.5 + 0.5 * lum, 0.0, 0.0, c.a);
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
            "stale": QColor(150, 150, 150, 200), "accent": QColor(10, 132, 255, 255)},
    # rossi puri (verde e blu a 0), come il piano del cielo in modalità notte (programma di disegno)
    True: {"grid": QColor(190, 0, 0, 150), "text": QColor(235, 0, 0, 240), "mark": QColor(235, 0, 0, 240),
           "stale": QColor(125, 0, 0, 220), "accent": QColor(255, 0, 0, 255)},
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

    failed = Signal(str, str, object)  # codice, testo, params (GL_UNAVAILABLE)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFormat(surface_format())
        self._planes: dict[str, list] = {}  # chiave → [QImage, QOpenGLTexture | None, da ricaricare]
        self._dead: list[QOpenGLTexture] = []  # texture da distruggere con il contesto attivo
        self._layers: tuple[tuple[str, str, float], ...] | None = None
        self._polygons: tuple[PolygonSet, ...] = ()
        self._polygons_dirty = False
        self._poly_ranges: dict[str, tuple[int, int, int, int]] = {}
        self._point_ranges: dict[str, tuple[int, int]] = {}
        self._transform = (1.0, 0.0, 0.0)
        self._night = False
        self._overlay: Overlay | None = None
        self._points: tuple[PointSet, ...] = ()
        self._points_dirty = False
        self._point_count = 0
        self.available = True
        self.program: QOpenGLShaderProgram | None = None
        self.point_program: QOpenGLShaderProgram | None = None
        self.poly_program: QOpenGLShaderProgram | None = None

    # --- interfaccia SkyRenderer ---------------------------------------------------------

    def widget(self):
        return self

    def upload_texture(self, rgba: np.ndarray, key: str = "plane") -> None:
        rows, cols = rgba.shape[:2]
        data = np.ascontiguousarray(rgba, dtype=np.uint8)
        image = QImage(data.data, cols, rows, 4 * cols, QImage.Format.Format_RGBA8888).copy()
        old = self._planes.get(key)
        self._planes[key] = [image, None if old is None else old[1], True]
        self.update()

    def drop_texture(self, key: str) -> None:
        old = self._planes.pop(key, None)
        if old is not None and old[1] is not None:
            self._dead.append(old[1])
        self.update()

    def set_layers(self, items) -> None:
        self._layers = tuple(items)
        self.update()

    def upload_polygons(self, sets) -> None:
        self._polygons = tuple(sets)
        self._polygons_dirty = True
        self.update()

    def drawn_polygons(self) -> list[tuple[str, np.ndarray, np.ndarray]]:
        k, tx, ty = self._transform
        t = np.array([tx, ty])
        return [(s.layer, k * s.triangles.astype(np.float64) + t, k * s.lines.astype(np.float64) + t)
                for s in self._polygons]

    def set_transform(self, k: float, tx: float, ty: float) -> None:
        self._transform = (float(k), float(tx), float(ty))
        self.update()

    def set_night(self, night: bool) -> None:
        self._night = bool(night)
        self.update()

    def set_overlay(self, overlay: Overlay | None) -> None:
        self._overlay = overlay
        self.update()

    def upload_points(self, sets: tuple[PointSet, ...]) -> None:
        self._points = tuple(sets)
        self._points_dirty = True
        self.update()

    def drawn_positions(self) -> list[tuple[str, np.ndarray, np.ndarray]]:
        k, tx, ty = self._transform
        return [(s.layer, s.rows, k * s.xy.astype(np.float64) + np.array([tx, ty])) for s in self._points]

    def render_offscreen(self) -> QImage:
        """Immagine del disegno (pixel fisici), per i test ``gl`` e per il PNG (sprint successivo)."""
        return self.grabFramebuffer()

    # --- QOpenGLWidget -------------------------------------------------------------------

    def initializeGL(self) -> None:  # noqa: N802 - nome di Qt
        fmt = self.context().format() if self.context() is not None else None
        version = (fmt.majorVersion(), fmt.minorVersion()) if fmt is not None else (0, 0)
        if version < GL_VERSION or not QOpenGLContext.currentContext():
            self._unavailable("version", f"OpenGL {version[0]}.{version[1]}: serve OpenGL {GL_VERSION[0]}."
                              f"{GL_VERSION[1]} core profile; visualizzatore non disponibile",
                              {"found": f"{version[0]}.{version[1]}", "required": f"{GL_VERSION[0]}.{GL_VERSION[1]}"})
            return
        program = QOpenGLShaderProgram(self)
        ok = (program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, _VERTEX)
              and program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, _FRAGMENT)
              and program.link())
        if not ok:
            self._unavailable("program", f"programma di disegno non compilato: {program.log()}",
                              {"log": program.log()})
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
        points = QOpenGLShaderProgram(self)
        ok = (points.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, _POINT_VERTEX)
              and points.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, _POINT_FRAGMENT)
              and points.link())
        if not ok:
            self._unavailable("points_program", f"programma dei simboli non compilato: {points.log()}",
                              {"log": points.log()})
            return
        self.point_program = points
        self.point_vao = QOpenGLVertexArrayObject(self)
        self.point_vao.create()
        self.point_vao.bind()
        self.point_vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self.point_vbo.setUsagePattern(QOpenGLBuffer.UsagePattern.DynamicDraw)
        self.point_vbo.create()
        self.point_vbo.bind()
        self.point_vbo.allocate(_POINT_FLOATS * 4)
        points.bind()
        stride = _POINT_FLOATS * 4
        for location, offset, size in ((0, 0, 2), (1, 2, 4), (2, 6, 1), (3, 7, 1)):
            points.enableAttributeArray(location)
            points.setAttributeBuffer(location, _GL_FLOAT, offset * 4, size, stride)
        points.release()
        self.point_vao.release()
        self.point_vbo.release()
        self._points_dirty = True
        poly = QOpenGLShaderProgram(self)
        ok = (poly.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, _POLY_VERTEX)
              and poly.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, _POLY_FRAGMENT)
              and poly.link())
        if not ok:
            self._unavailable("moc_program", f"programma dei MOC non compilato: {poly.log()}",
                              {"log": poly.log()})
            return
        self.poly_program = poly
        self.poly_vao = QOpenGLVertexArrayObject(self)
        self.poly_vao.create()
        self.poly_vao.bind()
        self.poly_vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self.poly_vbo.setUsagePattern(QOpenGLBuffer.UsagePattern.DynamicDraw)
        self.poly_vbo.create()
        self.poly_vbo.bind()
        self.poly_vbo.allocate(_POLY_FLOATS * 4)
        poly.bind()
        stride = _POLY_FLOATS * 4
        for location, offset, size in ((0, 0, 2), (1, 2, 4)):
            poly.enableAttributeArray(location)
            poly.setAttributeBuffer(location, _GL_FLOAT, offset * 4, size, stride)
        poly.release()
        self.poly_vao.release()
        self.poly_vbo.release()
        self._polygons_dirty = True

    def _cleanup(self) -> None:
        """Texture distrutte con il loro contesto attivo (chiusura della finestra)."""
        textures = [p[1] for p in self._planes.values() if p[1] is not None] + self._dead
        if textures:
            self.makeCurrent()
            for texture in textures:
                texture.destroy()
            for plane in self._planes.values():
                plane[1], plane[2] = None, True
            self._dead = []
            self.doneCurrent()

    def _unavailable(self, reason: str, text: str, params: dict) -> None:
        """Visualizzatore non disponibile (``GL_UNAVAILABLE``, 41 §10.1): ``reason`` sceglie la voce del catalogo."""
        self.available = False
        self.failed.emit("GL_UNAVAILABLE", text, {"reason": reason, **params})

    def paintGL(self) -> None:  # noqa: N802
        f = self.context().functions()
        clear = (0.0, 0.0, 0.0) if self._night else _CLEAR
        f.glClearColor(*clear, 1.0)
        f.glClear(_GL_COLOR_BUFFER_BIT)
        for texture in self._dead:
            texture.destroy()
        self._dead = []
        items = self._layers
        if items is None:  # nessun ordine dato: piani, poi MOC, poi simboli
            items = (tuple(("texture", k, 1.0) for k in self._planes) + tuple(("polygons", s.layer, 1.0)
                     for s in self._polygons) + tuple(("points", s.layer, 1.0) for s in self._points))
        if self.point_program is not None:
            self._upload_points()
        if self.poly_program is not None:
            self._upload_polygons()
        for kind, key, opacity in items:
            if kind == "texture" and self.program is not None and key in self._planes:
                self._paint_plane(f, key, opacity)
            elif kind == "points" and self.point_program is not None and key in self._point_ranges:
                self._paint_points(f, key)
            elif kind == "polygons" and self.poly_program is not None and key in self._poly_ranges:
                self._paint_polygons(f, key)
        if self._overlay is not None or any(s.selected.any() for s in self._points):
            self._paint_overlay(self._overlay)

    def _upload_points(self) -> None:
        """Simboli di tutti i cataloghi in un solo buffer, con l'intervallo di ogni livello."""
        if not self._points_dirty:
            return
        data = np.concatenate([np.column_stack([s.xy, s.rgba, s.size, s.shape]).astype(np.float32)
                               for s in self._points]) if self._points else np.zeros((0, _POINT_FLOATS), np.float32)
        data = np.ascontiguousarray(data)
        self._point_count = len(data)
        self._point_ranges, first = {}, 0
        for s in self._points:
            self._point_ranges[s.layer] = (first, len(s.xy))
            first += len(s.xy)
        self.point_vbo.bind()
        self.point_vbo.allocate(data.tobytes(), max(data.nbytes, _POINT_FLOATS * 4))
        self.point_vbo.release()
        self._points_dirty = False

    def _upload_polygons(self) -> None:
        """MOC di tutti i livelli in un solo buffer: per livello prima i triangoli, poi i segmenti del perimetro."""
        if not self._polygons_dirty:
            return
        chunks, self._poly_ranges, first = [], {}, 0
        for s in self._polygons:
            tri = np.column_stack([s.triangles, np.tile(np.asarray(s.fill, np.float32), (len(s.triangles), 1))])
            lines = np.column_stack([s.lines, np.tile(np.asarray(s.line, np.float32), (len(s.lines), 1))])
            chunks += [tri, lines]
            self._poly_ranges[s.layer] = (first, len(tri), first + len(tri), len(lines))
            first += len(tri) + len(lines)
        data = np.ascontiguousarray(np.concatenate(chunks).astype(np.float32) if chunks
                                    else np.zeros((0, _POLY_FLOATS), np.float32))
        self.poly_vbo.bind()
        self.poly_vbo.allocate(data.tobytes(), max(data.nbytes, _POLY_FLOATS * 4))
        self.poly_vbo.release()
        self._polygons_dirty = False

    def _paint_polygons(self, f, layer: str) -> None:
        """Riempimento (``GL_TRIANGLES``) e perimetro (``GL_LINES``) di un MOC, trasformazione come uniforme."""
        tri_first, tri_n, line_first, line_n = self._poly_ranges[layer]
        ratio = self.devicePixelRatioF()
        f.glEnable(_GL_BLEND)
        f.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
        program = self.poly_program
        program.bind()
        program.setUniformValue("transform", *self._transform)
        program.setUniformValue("viewport", float(self.width() * ratio), float(self.height() * ratio))
        program.setUniformValue("night", self._night)
        self.poly_vao.bind()
        if tri_n:
            f.glDrawArrays(_GL_TRIANGLES, tri_first, tri_n)
        if line_n:
            f.glDrawArrays(_GL_LINES, line_first, line_n)
        self.poly_vao.release()
        program.release()

    def _paint_points(self, f, layer: str) -> None:
        """Simboli di un catalogo: ``glDrawArrays(GL_POINTS)`` sul suo intervallo, trasformazione come uniforme."""
        first, count = self._point_ranges[layer]
        if not count:
            return
        ratio = self.devicePixelRatioF()
        f.glEnable(_GL_BLEND)
        f.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
        f.glEnable(_GL_PROGRAM_POINT_SIZE)
        program = self.point_program
        program.bind()
        program.setUniformValue("transform", *self._transform)
        program.setUniformValue("viewport", float(self.width() * ratio), float(self.height() * ratio))
        program.setUniformValue1f("ratio", float(ratio))  # 1f: con il rapporto 1.0 non diventa un int
        program.setUniformValue("night", self._night)
        self.point_vao.bind()
        f.glDrawArrays(_GL_POINTS, first, count)
        self.point_vao.release()
        program.release()

    def _paint_plane(self, f, key: str, opacity: float) -> None:
        plane = self._planes[key]
        image = plane[0]
        if plane[2]:
            if plane[1] is not None:
                plane[1].destroy()
            texture = QOpenGLTexture(image, QOpenGLTexture.MipMapGeneration.DontGenerateMipMaps)
            texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            texture.setMagnificationFilter(QOpenGLTexture.Filter.Nearest)
            texture.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
            plane[1], plane[2] = texture, False
        texture = plane[1]
        ratio = self.devicePixelRatioF()
        f.glEnable(_GL_BLEND)
        f.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
        self.program.bind()
        self.program.setUniformValue("image_size", float(image.width()), float(image.height()))
        self.program.setUniformValue("transform", *self._transform)
        self.program.setUniformValue("viewport", float(self.width() * ratio), float(self.height() * ratio))
        self.program.setUniformValue("night", self._night)
        self.program.setUniformValue1f("opacity", float(opacity))  # 1f: un float intero non diventa un int
        self.program.setUniformValue("image", 0)
        texture.bind(0)
        self.vao.bind()
        f.glDrawArrays(_GL_TRIANGLE_STRIP, 0, 4)
        self.vao.release()
        texture.release()
        self.program.release()

    # --- griglia, indicatore, barra ------------------------------------------------------

    def _paint_overlay(self, overlay: Overlay | None) -> None:
        ratio = self.devicePixelRatioF()
        k, tx, ty = self._transform
        colors = _PALETTE[self._night]
        painter = QPainter(self)
        try:
            # anello d'accento attorno alle sorgenti selezionate (41 §3.8)
            for s in self._points:
                for j in np.flatnonzero(s.selected):
                    x, y = (k * float(s.xy[j, 0]) + tx) / ratio, (k * float(s.xy[j, 1]) + ty) / ratio
                    radius = float(s.size[j]) / 2 + 4
                    for width, color in ((3.4, _SHADOW), (1.8, colors["accent"])):
                        pen = QPen(color, width)
                        pen.setCosmetic(True)
                        painter.setPen(pen)
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                        painter.drawEllipse(QPointF(x, y), radius, radius)
            if overlay is None:
                return
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
