"""Test del centroide del modulo 11 (``mdfiles/11-core-immagini-fits.md`` §12, T16–T19).

Solo ``star_centroid``: il resto del modulo 11 non è ancora scritto. Gli
attesi sono ricalcolati nel test con ``astropy.stats`` e ``scipy.ndimage``.
"""

from __future__ import annotations

import numpy as np
import pytest
from astropy.modeling.models import Gaussian2D
from astropy.stats import sigma_clipped_stats
from scipy import ndimage

from astrotwo.core.images_fits import ImagesFitsError, star_centroid

SHAPE_YX = (80, 100)
TRUE_X, TRUE_Y = 47.3, 38.6
BACKGROUND = 100.0
NOISE = 2.0


def synthetic_image(seed=16, extra_star=None):
    yy, xx = np.mgrid[: SHAPE_YX[0], : SHAPE_YX[1]]
    star = Gaussian2D(amplitude=5000.0, x_mean=TRUE_X, y_mean=TRUE_Y, x_stddev=1.8, y_stddev=1.8)
    image = BACKGROUND + star(xx, yy)
    if extra_star is not None:
        image = image + Gaussian2D(amplitude=3000.0, x_mean=extra_star[0], y_mean=extra_star[1],
                                   x_stddev=1.2, y_stddev=1.2)(xx, yy)
    rng = np.random.default_rng(seed)
    return (image + rng.normal(0.0, NOISE, image.shape)).astype(np.float32)


def expect_error(code, func, *args, **kwargs):
    with pytest.raises(ImagesFitsError) as info:
        func(*args, **kwargs)
    assert info.value.code == code, info.value
    return info.value


def test_t16_centroid_matches_scipy_and_astropy():
    image = synthetic_image()
    start = (46.8, 39.2)  # punto indicato dall'utente, vicino alla stella
    result = star_centroid(image, start, box_size=11, annulus_inner=8.0, annulus_outer=14.0)

    # Ricalcolo indipendente nel test.
    yy, xx = np.mgrid[: SHAPE_YX[0], : SHAPE_YX[1]]
    r = np.hypot(xx - start[0], yy - start[1])
    ring = image.astype(np.float64)[(r >= 8.0) & (r < 14.0)]
    _, median, std = sigma_clipped_stats(ring, sigma=3.0, maxiters=5)
    cx, cy = round(start[0]), round(start[1])
    window = image.astype(np.float64)[cy - 5 : cy + 6, cx - 5 : cx + 6] - median
    row, col = ndimage.center_of_mass(window)

    assert result.convention == "numpy"
    assert result.x == pytest.approx(cx - 5 + col, abs=1e-12)
    assert result.y == pytest.approx(cy - 5 + row, abs=1e-12)
    assert result.background == pytest.approx(median, abs=1e-12)
    assert result.background_std == pytest.approx(std, abs=1e-12)
    assert result.n_background_pixels == ring.size
    assert result.window == (cx - 5, cx + 5, cy - 5, cy + 5)
    assert (result.clip_sigma, result.clip_maxiters) == (3.0, 5)
    # Vicino al centro vero (la finestra di 11 pixel tronca appena le ali).
    assert np.hypot(result.x - TRUE_X, result.y - TRUE_Y) < 0.05


def test_t16_accepts_object_with_data():
    class FakeImage:
        data = synthetic_image()

    a = star_centroid(FakeImage(), (47, 39), 11, 8, 14)
    b = star_centroid(FakeImage.data, (47, 39), 11, 8, 14)
    assert (a.x, a.y) == (b.x, b.y)


@pytest.mark.parametrize("position", [(3.0, 40.0), (97.0, 40.0), (50.0, 2.0), (50.0, 78.0), (12.0, 40.0)])
def test_t17_window_or_annulus_out_of_image(position):
    expect_error("CENTROID_OUT_OF_IMAGE", star_centroid, synthetic_image(), position, 11, 8.0, 14.0)


def test_t18_undefined_centroid():
    image = synthetic_image()
    with_nan = image.copy()
    with_nan[39, 47] = np.nan
    expect_error("CENTROID_UNDEFINED", star_centroid, with_nan, (47, 39), 11, 8.0, 14.0)
    flat = np.full(SHAPE_YX, BACKGROUND)  # nessuna stella: pesi tutti zero
    expect_error("CENTROID_UNDEFINED", star_centroid, flat, (50, 40), 11, 8.0, 14.0)
    ring_nan = image.copy().astype(np.float64)
    yy, xx = np.mgrid[: SHAPE_YX[0], : SHAPE_YX[1]]
    ring_nan[np.hypot(xx - 47, yy - 39) >= 8.0] = np.nan
    expect_error("CENTROID_UNDEFINED", star_centroid, ring_nan, (47, 39), 11, 8.0, 14.0)


def test_t19_background_robust_to_star_in_annulus():
    image = synthetic_image(extra_star=(TRUE_X + 10.0, TRUE_Y))  # stella dentro la corona
    result = star_centroid(image, (47, 39), 11, 8.0, 14.0)
    assert abs(result.background - BACKGROUND) < 3 * NOISE


@pytest.mark.parametrize(
    "kwargs",
    [dict(box_size=10), dict(box_size=1), dict(annulus_inner=14.0, annulus_outer=8.0), dict(annulus_inner=-1.0)],
)
def test_invalid_parameters(kwargs):
    params = dict(box_size=11, annulus_inner=8.0, annulus_outer=14.0) | kwargs
    with pytest.raises(ValueError):
        star_centroid(synthetic_image(), (47, 39), **params)
