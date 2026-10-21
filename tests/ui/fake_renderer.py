# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Renderer in memoria per i test sulla piattaforma ``offscreen`` (senza GPU): registra ciò che il 41 disegna."""

from __future__ import annotations

import numpy as np
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

    def widget(self):
        return self

    def upload_texture(self, rgba) -> None:
        self.texture = np.array(rgba, copy=True)
        self.uploads += 1

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
