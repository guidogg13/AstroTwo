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

    def widget(self):
        return self

    def upload_texture(self, rgba) -> None:
        self.texture = np.array(rgba, copy=True)
        self.uploads += 1

    def set_transform(self, k, tx, ty) -> None:
        self.transform = (k, tx, ty)

    def set_night(self, night) -> None:
        self.night = night
