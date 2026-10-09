"""Immagini FITS: lettura, gestione e visualizzazione.

Specifica: ``mdfiles/11-core-immagini-fits.md`` (stato ``approvato``).

Per ora contiene solo il centroide per la calibrazione astrometrica
(``star_centroid``, H6; D10-8 e D11-7). Il resto del modulo non è ancora
scritto.

Coordinate pixel in convenzione numpy (origine 0, ``array[y, x]``), come da
DC7 di ``02-convenzioni.md``; calcoli in ``float64`` (DC6).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import astropy
import numpy as np
import scipy
from astropy.stats import sigma_clipped_stats
from scipy import ndimage

__all__ = ["ImagesFitsError", "StarCentroid", "star_centroid"]

# Parametri di sigma_clipped_stats: i default della libreria (D11-7), resi
# espliciti perché siano scritti nel risultato.
_CLIP_SIGMA = 3.0
_CLIP_MAXITERS = 5

_PROVENANCE = (
    f"astropy {astropy.__version__} (sigma_clipped_stats), scipy {scipy.__version__} (ndimage.center_of_mass)"
)


class ImagesFitsError(Exception):
    """Errore del modulo 11 con identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


@dataclass(frozen=True)
class StarCentroid:
    """Centroide di una stella, pronto per ``astrometric_calibration`` (modulo 10)."""

    x: float
    y: float
    convention: str  # sempre "numpy"
    window: tuple[int, int, int, int]  # x_min, x_max, y_min, y_max inclusi
    background: float
    background_std: float
    n_background_pixels: int
    annulus_inner: float
    annulus_outer: float
    clip_sigma: float
    clip_maxiters: int
    provenance: str = _PROVENANCE


def _image_array(image) -> np.ndarray:
    data = getattr(image, "data", image)
    array = np.asarray(data)
    if array.ndim != 2:
        raise ValueError("serve un'immagine 2-D (array o oggetto con attributo data)")
    return array


def star_centroid(image, position, box_size: int, annulus_inner: float, annulus_outer: float) -> StarCentroid:
    """Baricentro pesato sull'intensità dopo la sottrazione del fondo (D11-7).

    - finestra quadrata di lato ``box_size`` (intero dispari ≥ 3) centrata sul
      pixel più vicino a ``position`` = (x, y) in convenzione numpy;
    - fondo = mediana con sigma clipping (``astropy.stats.sigma_clipped_stats``)
      dei pixel a distanza da ``position`` in [``annulus_inner``,
      ``annulus_outer``) pixel;
    - baricentro con ``scipy.ndimage.center_of_mass`` su finestra − fondo,
      in ``float64``.
    """
    data = _image_array(image)
    if isinstance(box_size, bool) or not isinstance(box_size, int) or box_size < 3 or box_size % 2 == 0:
        raise ValueError("box_size deve essere un intero dispari ≥ 3")
    r_in, r_out = float(annulus_inner), float(annulus_outer)
    if not (math.isfinite(r_in) and math.isfinite(r_out) and 0.0 <= r_in < r_out):
        raise ValueError("raggi della corona non validi: serve 0 ≤ annulus_inner < annulus_outer")
    px, py = (float(v) for v in position)
    if not (math.isfinite(px) and math.isfinite(py)):
        raise ValueError("posizione non finita")

    ny, nx = data.shape
    half = box_size // 2
    cx, cy = int(round(px)), int(round(py))
    x0, x1, y0, y1 = cx - half, cx + half, cy - half, cy + half
    # La corona deve stare tutta nell'immagine, come la finestra.
    ax0, ax1 = math.floor(px - r_out), math.ceil(px + r_out)
    ay0, ay1 = math.floor(py - r_out), math.ceil(py + r_out)
    if min(x0, y0, ax0, ay0) < 0 or x1 > nx - 1 or ax1 > nx - 1 or y1 > ny - 1 or ay1 > ny - 1:
        raise ImagesFitsError(
            "CENTROID_OUT_OF_IMAGE",
            f"finestra x {x0}..{x1}, y {y0}..{y1} o corona di raggio {r_out} fuori dall'immagine {nx}×{ny}",
            window=(x0, x1, y0, y1),
            shape=(nx, ny),
        )

    window = data[y0 : y1 + 1, x0 : x1 + 1].astype(np.float64)
    if not np.all(np.isfinite(window)):
        raise ImagesFitsError("CENTROID_UNDEFINED", "pixel non finiti nella finestra del centroide")

    sub = data[ay0 : ay1 + 1, ax0 : ax1 + 1].astype(np.float64)
    yy, xx = np.mgrid[ay0 : ay1 + 1, ax0 : ax1 + 1]
    r = np.hypot(xx - px, yy - py)
    ring = sub[(r >= r_in) & (r < r_out) & np.isfinite(sub)]
    if ring.size == 0:
        raise ImagesFitsError("CENTROID_UNDEFINED", "nessun pixel finito nella corona del fondo")
    _, median, std = sigma_clipped_stats(ring, sigma=_CLIP_SIGMA, maxiters=_CLIP_MAXITERS)

    weights = window - median
    if not np.sum(weights) > 0.0:
        raise ImagesFitsError(
            "CENTROID_UNDEFINED", "somma dei pesi ≤ 0 dopo la sottrazione del fondo: nessuna stella nella finestra"
        )
    row, col = ndimage.center_of_mass(weights)
    return StarCentroid(
        x=float(x0 + col),
        y=float(y0 + row),
        convention="numpy",
        window=(x0, x1, y0, y1),
        background=float(median),
        background_std=float(std),
        n_background_pixels=int(ring.size),
        annulus_inner=r_in,
        annulus_outer=r_out,
        clip_sigma=_CLIP_SIGMA,
        clip_maxiters=_CLIP_MAXITERS,
    )
