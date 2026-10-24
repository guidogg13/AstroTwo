# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Renderer in memoria per i test sulla piattaforma ``offscreen`` (senza GPU): registra ciò che il 41 disegna."""

from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from astrotwo.ui.sky_viewer import SkyRenderer


class MemoryRenderer(QWidget, SkyRenderer):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.texture: np.ndarray | None = None
        self.uploads = 0
        self.transform = (1.0, 0.0, 0.0)
        self.night = False
        self.overlay = None
        self.points: tuple = ()
        self.point_uploads = 0
        self.textures: dict = {}  # chiave (livello) → RGBA
        self.texture_uploads: dict = {}
        self.layers = None  # ordine di disegno (tipo, livello, opacità), dal basso
        self.polygons: tuple = ()
        self.polygon_uploads = 0

    def widget(self):
        return self

    def upload_texture(self, rgba, key="plane") -> None:
        self.texture = np.array(rgba, copy=True)  # l'ultimo piano caricato
        self.textures[key] = self.texture
        self.texture_uploads[key] = self.texture_uploads.get(key, 0) + 1
        self.uploads += 1

    def drop_texture(self, key) -> None:
        self.textures.pop(key, None)

    def set_layers(self, items) -> None:
        self.layers = tuple(items)

    def upload_polygons(self, sets) -> None:
        self.polygons = tuple(sets)
        self.polygon_uploads += 1

    def drawn_polygons(self):
        k, tx, ty = self.transform
        t = np.array([tx, ty])
        return [(s.layer, k * s.triangles.astype(np.float64) + t, k * s.lines.astype(np.float64) + t)
                for s in self.polygons]

    def set_transform(self, k, tx, ty) -> None:
        self.transform = (k, tx, ty)

    def set_night(self, night) -> None:
        self.night = night

    def set_overlay(self, overlay) -> None:
        self.overlay = overlay

    def upload_points(self, sets) -> None:
        self.points = tuple(sets)
        self.point_uploads += 1

    def drawn_positions(self):
        k, tx, ty = self.transform
        return [(s.layer, s.rows, k * s.xy.astype(np.float64) + np.array([tx, ty])) for s in self.points]

    def render_offscreen(self):
        """Piani composti nell'ordine dei livelli con la loro opacità, su fondo nero, grandi quanto la finestra."""
        ratio = self.devicePixelRatioF()
        w, h = max(1, round(self.width() * ratio)), max(1, round(self.height() * ratio))
        out = np.zeros((h, w, 3), dtype=np.float64)
        order = [key for kind, key, _ in (self.layers or ()) if kind == "texture"] or list(self.textures)
        opacity = {key: op for kind, key, op in (self.layers or ()) if kind == "texture"}
        for key in order:
            plane = self.textures.get(key)
            if plane is None:
                continue
            rows, cols = min(h, plane.shape[0]), min(w, plane.shape[1])
            alpha = plane[:rows, :cols, 3:4] / 255.0 * opacity.get(key, 1.0)
            out[:rows, :cols] = out[:rows, :cols] * (1 - alpha) + plane[:rows, :cols, :3] * alpha
        data = np.ascontiguousarray(out.round().astype(np.uint8))
        return QImage(data.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
