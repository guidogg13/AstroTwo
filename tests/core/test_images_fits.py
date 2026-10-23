# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del modulo 11 (``mdfiles/11-core-immagini-fits.md`` §12, T1–T34).

Gli attesi sono ricalcolati nel test con le librerie di riferimento
(``astropy``, ``scipy``, ``reproject``, ``matplotlib``, ``Pillow``).
"""

from __future__ import annotations

import dataclasses

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


# =============================================================================
# P1 — Lettura FITS e HDU (T1, T8 parte FITS, T9, T15, T28, T29)
# File generati nei test con astropy.io.fits, mai file esterni.
# =============================================================================

import gzip as _gzip
import shutil as _shutil

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS

from astrotwo.core.images_fits import (
    detect_format,
    list_image_hdus,
    load_image,
    pixel_scaling,
    read_raw_pixel,
)


def wcs_header(nx=60, ny=40, crval=(150.0, 2.0), scale=1e-3):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = list(crval)
    w.wcs.crpix = [nx / 2 + 0.5, ny / 2 + 0.5]
    w.wcs.cdelt = [-scale, scale]
    w.wcs.radesys = "ICRS"
    header = w.to_header()
    header["BUNIT"] = "MJy/sr"
    return header


def write_fits(path, data, header=None):
    fits.PrimaryHDU(data=data, header=header).writeto(path)
    return path


def test_t1_open_fits_with_wcs(tmp_path):
    data = np.random.default_rng(1).normal(10, 1, (40, 60)).astype(np.float32)
    path = write_fits(tmp_path / "img.fits", data, wcs_header())
    image = load_image(path)
    with fits.open(path) as hdul:
        expected_data = hdul[0].data
        expected_header = hdul[0].header
        expected_wcs = WCS(expected_header)
    assert image.data.dtype == np.float32  # tipo nativo del file (D11-1)
    assert np.array_equal(image.data, expected_data)
    assert image.shape == (40, 60) and image.format == "fits" and image.hdu_index == 0
    assert image.header["CTYPE1"] == expected_header["CTYPE1"] and image.bunit == "MJy/sr"
    assert image.unit == u.MJy / u.sr
    assert image.origin == str(path.resolve()) and image.retrieved_at.tzinfo is not None
    assert image.file_modified is not None and image.warnings == ()
    xs, ys = np.array([0.0, 59.0, 30.5]), np.array([0.0, 39.0, 12.25])
    ours = image.wcs.wcs.pixel_to_world(xs, ys)
    ra, dec = expected_wcs.all_pix2world(xs, ys, 0)
    assert np.max(ours.separation(SkyCoord(ra, dec, unit="deg")).deg) < 1e-12
    # Campo di vista ricalcolato con astropy.wcs ai punti medi dei bordi.
    width, height = image.field_of_view()
    edges = expected_wcs.pixel_to_world([-0.5, 59.5, 29.5, 29.5], [19.5, 19.5, -0.5, 39.5])
    assert abs(width - edges[0].separation(edges[1])).to_value(u.deg) < 1e-12
    assert abs(height - edges[2].separation(edges[3])).to_value(u.deg) < 1e-12


def test_t1_header_without_wcs_opens_as_pixel_grid(tmp_path):
    path = write_fits(tmp_path / "nowcs.fits", np.ones((10, 12), dtype=np.int16))
    image = load_image(path)
    assert image.wcs is None and image.field_of_view() is None
    assert [code for code, _ in image.warnings] == ["WCS_MISSING"]


def test_t8_fits_recognized_from_content_not_extension(tmp_path):
    path = write_fits(tmp_path / "in_realta_fits.png", np.zeros((5, 5), dtype=np.float32))
    assert detect_format(path) == "fits"
    assert load_image(path).format == "fits"
    gz = tmp_path / "img.fits.gz"
    with open(path, "rb") as src, _gzip.open(gz, "wb") as dst:
        _shutil.copyfileobj(src, dst)
    assert detect_format(gz) == "fits-gzip"
    assert np.array_equal(load_image(gz).data, np.zeros((5, 5), dtype=np.float32))
    junk = tmp_path / "junk.fits"
    junk.write_bytes(b"questo non e un file astronomico" * 10)
    with pytest.raises(ImagesFitsError) as info:
        detect_format(junk)
    assert info.value.code == "FORMAT_UNSUPPORTED"


@pytest.mark.parametrize("compression", ["HCOMPRESS_1", "RICE_1", "GZIP_1", "GZIP_2"])
@pytest.mark.parametrize("dtype", [np.int16, np.float32])
def test_t9_compressed_fits(tmp_path, compression, dtype):
    rng = np.random.default_rng(9)
    data = (rng.integers(0, 1000, (64, 80)) if dtype is np.int16 else rng.normal(100, 5, (64, 80))).astype(dtype)
    path = tmp_path / f"{compression}.fits"
    kwargs = {"hcomp_scale": 0} if compression == "HCOMPRESS_1" else {}
    fits.HDUList([fits.PrimaryHDU(), fits.CompImageHDU(data, compression_type=compression, **kwargs)]).writeto(path)
    image = load_image(path)
    with fits.open(path) as hdul:
        expected = hdul[1].data  # valori restituiti da astropy.io.fits sulla stessa HDU
    assert np.array_equal(image.data, expected)
    assert detect_format(path) == "fits-compressed"
    assert image.compression == compression and image.hdu_index == 1


def test_t15_pixel_scaling_constants(tmp_path):
    data = np.array([[0, 1000], [40000, 65535]], dtype=np.uint16)
    header = fits.Header({"BUNIT": "ADU"})
    path = write_fits(tmp_path / "uint16.fits", data, header)
    with fits.open(path) as hdul:  # astropy scrive uint16 come int16 con BZERO = 32768
        raw_header = hdul[0].header.copy()
    image = load_image(path)
    scaling = pixel_scaling(image)
    assert raw_header["BZERO"] == 32768 and raw_header["BSCALE"] == 1
    assert scaling.bzero == raw_header["BZERO"] and scaling.bscale == raw_header["BSCALE"]
    assert scaling.blank is None and scaling.bunit == "ADU"
    assert np.array_equal(image.data, data)


def test_t36_read_raw_pixel(tmp_path):
    raw = np.array([[-32768, 0, 7], [100, -5, 3]], dtype=np.int16)
    header = fits.Header({"BZERO": 10.0, "BSCALE": 0.5, "BLANK": -5})
    path = tmp_path / "scaled.fits"
    fits.PrimaryHDU(raw, header=header).writeto(path)
    image = load_image(str(path))
    with fits.open(path, do_not_scale_image_data=True) as hdul:  # riferimento: astropy senza scala
        stored = np.array(hdul[0].data)
    assert stored.dtype.kind == "i"
    for y in range(2):
        for x in range(3):
            value = read_raw_pixel(image, x, y)
            assert isinstance(value, np.float64) and value == stored[y, x]
    assert read_raw_pixel(image, 1, 1) == -5  # uguale a BLANK: restituito com'è
    # Assi degeneri tolti (D11-4): stessa lettura sull'asse di lunghezza 1.
    cube_path = tmp_path / "degenerate.fits"
    fits.PrimaryHDU(raw[np.newaxis], header=header).writeto(cube_path)
    degenerate = load_image(str(cube_path))
    assert read_raw_pixel(degenerate, 2, 0) == stored[0, 2]
    # Fuori dall'immagine, indici non interi, immagine derivata o non FITS: errore.
    for x, y in ((3, 0), (0, 2), (-1, 0), (0.5, 0), (True, 0)):
        with pytest.raises(ImagesFitsError) as exc:
            read_raw_pixel(image, x, y)
        assert exc.value.code == "PIXEL_RAW_UNAVAILABLE"
    with pytest.raises(ImagesFitsError) as exc:
        read_raw_pixel(image.with_operation("add", 1.0), 0, 0)
    assert exc.value.code == "PIXEL_RAW_UNAVAILABLE"


def test_t28_multiple_image_hdus(tmp_path):
    first = np.full((10, 20), 1.0, dtype=np.float32)
    second = np.full((30, 15), 2.0, dtype=np.float64)
    table = fits.BinTableHDU.from_columns([fits.Column(name="a", format="E", array=np.arange(3))], name="TAB")
    path = tmp_path / "mef.fits"
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(first, name="SCI"), table, fits.ImageHDU(second, name="ERR")]).writeto(path)
    hdus = list_image_hdus(path)
    assert [(h.index, h.name, h.shape) for h in hdus] == [(1, "SCI", (10, 20)), (3, "ERR", (30, 15))]
    with pytest.raises(ImagesFitsError) as info:
        load_image(path)
    assert info.value.code == "HDU_CHOICE_REQUIRED"
    assert [entry[0] for entry in info.value.details["hdus"]] == [1, 3]
    with fits.open(path) as hdul:
        assert np.array_equal(load_image(path, hdu="ERR").data, hdul["ERR"].data)
        assert np.array_equal(load_image(path, hdu=1).data, hdul[1].data)
    for bad, code in [(2, "HDU_NOT_IMAGE"), ("NOPE", "HDU_NOT_IMAGE")]:
        with pytest.raises(ImagesFitsError) as info:
            load_image(path, hdu=bad)
        assert info.value.code == code


def test_t29_degenerate_axes_and_cubes(tmp_path):
    header = wcs_header(nx=12, ny=8)
    w4 = WCS(header).sub([1, 2, 0, 0])
    w4.wcs.ctype = ["RA---TAN", "DEC--TAN", "FREQ", "STOKES"]
    w4.wcs.crval = [150.0, 2.0, 1.4e9, 1.0]
    w4.wcs.cdelt = [-1e-3, 1e-3, 1e6, 1.0]
    w4.wcs.crpix = [6.5, 4.5, 1.0, 1.0]
    data4 = np.arange(8 * 12, dtype=np.float32).reshape(1, 1, 8, 12)
    path = write_fits(tmp_path / "radio.fits", data4, w4.to_header())
    image = load_image(path)
    assert image.shape == (8, 12)
    assert sorted(image.dropped_axes) == [3, 4]  # FREQ e STOKES, assi FITS 3 e 4
    assert np.array_equal(image.data, data4[0, 0])
    expected = WCS(fits.getheader(path)).celestial
    xs, ys = np.array([0.0, 11.0]), np.array([0.0, 7.0])
    sep = image.wcs.wcs.pixel_to_world(xs, ys).separation(expected.pixel_to_world(xs, ys)).deg
    assert np.max(sep) < 1e-12
    assert any(code == "AXES_DROPPED" for code, _ in image.warnings)
    cube = write_fits(tmp_path / "cube.fits", np.zeros((3, 8, 12), dtype=np.float32))
    with pytest.raises(ImagesFitsError) as info:
        load_image(cube)
    assert info.value.code == "CUBE_NOT_SUPPORTED"


def test_p1_unreadable_and_nonfinite(tmp_path):
    with pytest.raises(ImagesFitsError) as info:
        load_image(tmp_path / "manca.fits")
    assert info.value.code == "FITS_UNREADABLE"
    broken = tmp_path / "rotto.fits"
    broken.write_bytes(b"SIMPLE  =                    T" + b" " * 50)
    with pytest.raises(ImagesFitsError) as info, pytest.warns(Warning):  # avviso atteso di astropy
        load_image(broken)
    assert info.value.code == "FITS_UNREADABLE"
    data = np.ones((4, 4), dtype=np.float32)
    data[1, 2] = np.nan
    image = load_image(write_fits(tmp_path / "nan.fits", data))
    assert "NONFINITE_PIXELS" in [code for code, _ in image.warnings]
    assert np.isnan(image.data[1, 2])  # mai sostituito


# =============================================================================
# P2 — JPEG, PNG, GIF, calibrazione (commento / .hhh) e FITS RGB
# (T8 parte PNG, T10, T27, T30). File generati nei test con Pillow.
# =============================================================================

from PIL import Image as PilImage
from PIL.PngImagePlugin import PngInfo


def calibration_text(nx, ny, newline=False):
    header = wcs_header(nx=nx, ny=ny)
    header.insert(0, ("NAXIS2", ny))
    header.insert(0, ("NAXIS1", nx))
    header.insert(0, ("NAXIS", 2))
    if newline:
        return "\n".join(card.image.rstrip() for card in header.cards)
    return header.tostring()  # schede da 80 caratteri attaccate


def gradient_rgb(nx=40, ny=30):
    yy, xx = np.mgrid[:ny, :nx]
    return np.stack([xx * 6 % 256, yy * 8 % 256, (xx + yy) % 256], axis=-1).astype(np.uint8)


def test_t8_png_recognized_from_content(tmp_path):
    path = tmp_path / "in_realta_png.fits"
    PilImage.fromarray(gradient_rgb()).save(path, format="PNG")
    assert detect_format(path) == "png"
    image = load_image(path)
    assert image.format == "png" and image.color


def test_t10_gif(tmp_path):
    gray = (np.arange(30 * 40).reshape(30, 40) % 256).astype(np.uint8)
    path = tmp_path / "gray.gif"
    PilImage.fromarray(gray, mode="L").save(path)
    image = load_image(path)
    with PilImage.open(path) as pil:
        expected = np.array(pil.convert("L"))  # tavolozza grigia → grigi (conversione di Pillow)
    assert image.shape == expected.shape and not image.color
    assert np.array_equal(image.data, expected[::-1])  # righe dal basso, come un FITS
    color_path = tmp_path / "color.gif"
    frames = [PilImage.fromarray(gradient_rgb()), PilImage.fromarray(gradient_rgb()[::-1].copy())]
    frames[0].save(color_path, save_all=True, append_images=frames[1:])
    colored = load_image(color_path)
    with PilImage.open(color_path) as pil:
        expected_rgb = np.array(pil.convert("RGB"))
    assert colored.color and colored.frames == 2
    assert np.array_equal(colored.data, np.moveaxis(expected_rgb[::-1], -1, 0))
    assert "FRAMES" in [code for code, _ in colored.warnings]


@pytest.mark.parametrize("fmt,newline", [("PNG", False), ("PNG", True), ("JPEG", False), ("JPEG", True)])
def test_t27_calibration_in_comment(tmp_path, fmt, newline):
    nx, ny = 40, 30
    text = calibration_text(nx, ny, newline=newline)
    path = tmp_path / f"cal.{fmt.lower()}"
    pil = PilImage.fromarray(gradient_rgb(nx, ny))
    if fmt == "PNG":
        info = PngInfo()
        info.add_text("Comment", text)
        pil.save(path, pnginfo=info)
    else:
        pil.save(path, comment=text.encode("latin-1"), quality=95)
    image = load_image(path)
    assert image.calibration_source == "comment" and image.wcs is not None
    expected = WCS(fits.Header.fromstring(text, sep="\n" if newline else ""))
    xs, ys = np.array([0.0, 39.0, 17.5]), np.array([0.0, 29.0, 9.25])
    # Pixel numpy (x, y) = pixel FITS (x + 1, y + 1) grazie all'ordine delle righe dal basso.
    ra, dec = expected.all_pix2world(xs + 1, ys + 1, 1)
    sep = image.wcs.wcs.pixel_to_world(xs, ys).separation(SkyCoord(ra, dec, unit="deg")).deg
    assert np.max(sep) < 1e-12
    with PilImage.open(path) as reread:
        assert np.array_equal(image.data, np.moveaxis(np.array(reread.convert("RGB"))[::-1], -1, 0))


def test_t27_calibration_in_hhh_and_precedence(tmp_path):
    nx, ny = 40, 30
    png = tmp_path / "foto.png"
    PilImage.fromarray(gradient_rgb(nx, ny)).save(png)
    (tmp_path / "foto.hhh").write_text(calibration_text(nx, ny), encoding="latin-1")
    image = load_image(png)
    assert image.calibration_source == "hhh" and image.wcs is not None
    # Commento nel file e .hhh insieme: vale il commento, il .hhh è dichiarato ignorato.
    info = PngInfo()
    info.add_text("Comment", calibration_text(nx, ny, newline=True))
    PilImage.fromarray(gradient_rgb(nx, ny)).save(png, pnginfo=info)
    both = load_image(png)
    assert both.calibration_source == "comment"
    assert "HHH_IGNORED" in [code for code, _ in both.warnings]


def test_t27_invalid_or_mismatched_calibration(tmp_path):
    info = PngInfo()
    info.add_text("Comment", "questo non e un header FITS")
    bad = tmp_path / "bad.png"
    PilImage.fromarray(gradient_rgb()).save(bad, pnginfo=info)
    image = load_image(bad)
    assert image.wcs is None and image.calibration_source is None
    assert "WCS_MISSING" in [code for code, _ in image.warnings]
    other = PngInfo()
    other.add_text("Comment", calibration_text(99, 77))  # dimensioni di un'altra immagine
    wrong = tmp_path / "wrong.png"
    PilImage.fromarray(gradient_rgb(40, 30)).save(wrong, pnginfo=other)
    image = load_image(wrong)
    assert image.wcs is None and any("NAXIS1/NAXIS2" in msg for _, msg in image.warnings)
    plain = tmp_path / "plain.png"
    PilImage.fromarray(gradient_rgb()).save(plain)
    assert load_image(plain).wcs is None


def _source_image(mode):
    rgb = gradient_rgb()
    if mode == "I;16":
        return PilImage.fromarray((np.arange(30 * 40).reshape(30, 40) * 50).astype(np.uint16))
    if mode == "RGBA":
        return PilImage.fromarray(np.dstack([rgb, np.full(rgb.shape[:2], 128, np.uint8)]), mode="RGBA")
    return PilImage.fromarray(rgb).convert(mode)


@pytest.mark.parametrize("mode", ["L", "I;16", "1", "RGBA", "LA"])
def test_p2_color_modes(tmp_path, mode):
    path = tmp_path / "img.png"
    _source_image(mode).save(path)
    image = load_image(path)
    with PilImage.open(path) as pil:  # atteso: conversioni di Pillow descritte in §3
        if pil.mode == "RGBA":
            expected = np.moveaxis(np.array(pil.convert("RGB"))[::-1], -1, 0)
        elif pil.mode == "LA":
            expected = np.array(pil.convert("L"))[::-1]
        elif pil.mode == "1":
            expected = np.array(pil, dtype=np.uint8)[::-1]
        else:
            expected = np.array(pil)[::-1]
        alpha = pil.mode in ("RGBA", "LA")
    assert np.array_equal(image.data, expected)
    assert image.color == (mode == "RGBA")
    assert ("ALPHA_DROPPED" in [code for code, _ in image.warnings]) == alpha


def test_p2_unreadable_image(tmp_path):
    path = tmp_path / "rotta.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)
    with pytest.raises(ImagesFitsError) as info:
        load_image(path)
    assert info.value.code == "IMAGE_UNREADABLE"


def test_t30_fits_rgb(tmp_path):
    header = wcs_header(nx=12, ny=8)
    planes = np.stack([np.full((8, 12), v, dtype=np.int16) for v in (10, 20, 30)])
    path = write_fits(tmp_path / "rgb.fits", planes, header)
    with pytest.raises(ImagesFitsError) as info:
        load_image(path)
    assert info.value.code == "CUBE_NOT_SUPPORTED"
    image = load_image(path, rgb=True)
    with fits.open(path) as hdul:
        assert np.array_equal(image.data, hdul[0].data)
    assert image.color and image.shape == (8, 12) and image.wcs is not None
    expected = WCS(fits.getheader(path)).celestial
    sep = image.wcs.wcs.pixel_to_world([0, 11], [0, 7]).separation(expected.pixel_to_world([0, 11], [0, 7])).deg
    assert np.max(sep) < 1e-12
    for n in (2, 4):
        other = write_fits(tmp_path / f"p{n}.fits", np.zeros((n, 8, 12), dtype=np.int16), header)
        with pytest.raises(ImagesFitsError) as info:
            load_image(other, rgb=True)
        assert info.value.code == "RGB_INPUT_INVALID"
    with pytest.raises(ValueError):
        star_centroid(image, (5, 4), 3, 1, 2)  # le immagini a colori non si misurano


# =============================================================================
# P3 — Rete e cache (T6, T7). Server HTTP locale simulato, nessuna rete esterna.
# =============================================================================

import functools
import http.server
import socket
import threading
import time

from astrotwo.core.cache import NetworkTimeouts, SharedCache


class _CountingHandler(http.server.SimpleHTTPRequestHandler):
    requests_seen: list = []

    def do_GET(self):  # noqa: N802 (nome imposto da http.server)
        type(self).requests_seen.append(self.path)
        super().do_GET()

    def log_message(self, *args):
        pass


@pytest.fixture
def http_server(tmp_path):
    served = tmp_path / "www"
    served.mkdir()
    handler = functools.partial(type("H", (_CountingHandler,), {"requests_seen": []}), directory=str(served))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield served, base, handler.func, server
    server.shutdown()
    server.server_close()


def test_t6_url_served_from_cache_with_provenance(tmp_path, http_server):
    served, base, handler_cls, _ = http_server
    data = np.arange(12, dtype=np.float32).reshape(3, 4)
    write_fits(served / "img.fits", data, wcs_header(nx=4, ny=3))
    url = f"{base}/img.fits"
    with SharedCache(tmp_path / "cache") as cache:
        first = load_image(url, cache=cache)
        assert not first.from_cache and first.origin == url and np.array_equal(first.data, data)
        entry = cache.get("11", f"url:{url}")
        assert entry.origin == url and entry.retrieved_at == first.retrieved_at
        assert cache.usage().by_module["11"] == (served / "img.fits").stat().st_size
        second = load_image(url, cache=cache)  # dalla cache, senza rete
        assert second.from_cache and second.retrieved_at == first.retrieved_at
        assert np.array_equal(second.data, data) and len(handler_cls.requests_seen) == 1
        assert "FROM_CACHE" in [code for code, _ in second.warnings]
        third = load_image(url, cache=cache, refresh=True)
        assert not third.from_cache and len(handler_cls.requests_seen) == 2


def test_t6_cached_copy_used_when_network_is_down(tmp_path, http_server):
    served, base, _, server = http_server
    write_fits(served / "img.fits", np.ones((3, 4), dtype=np.int16))
    url = f"{base}/img.fits"
    with SharedCache(tmp_path / "cache") as cache:
        load_image(url, cache=cache)
        server.shutdown()
        server.server_close()
        stale = load_image(url, cache=cache, refresh=True, timeouts=NetworkTimeouts(connect=1.0, read=1.0))
        assert stale.from_cache
        assert any("rete non disponibile" in msg for code, msg in stale.warnings if code == "FROM_CACHE")


def test_t6_png_from_url_ignores_hhh(tmp_path, http_server):
    served, base, _, _ = http_server
    PilImage.fromarray(gradient_rgb()).save(served / "foto.png")
    (served / "foto.hhh").write_text(calibration_text(40, 30))
    with SharedCache(tmp_path / "cache") as cache:
        image = load_image(f"{base}/foto.png", cache=cache)
    assert image.format == "png" and image.wcs is None and image.calibration_source is None


def test_t7_timeout_on_unresponsive_server(tmp_path):
    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(1)  # accetta la connessione ma non risponde mai
    url = f"http://127.0.0.1:{silent.getsockname()[1]}/img.fits"
    timeouts = NetworkTimeouts(connect=1.0, read=0.5)
    try:
        with SharedCache(tmp_path / "cache") as cache:
            start = time.monotonic()
            with pytest.raises(ImagesFitsError) as info:
                load_image(url, cache=cache, timeouts=timeouts)
            elapsed = time.monotonic() - start
            assert info.value.code == "NET_TIMEOUT" and "0.5 s lettura" in info.value.message
            assert elapsed < timeouts.read + 2.0  # entro il timeout dichiarato (più margine)
            assert cache.usage().total_bytes == 0  # nessun dato fasullo in cache
    finally:
        silent.close()


def test_t7_unreachable_and_http_errors(tmp_path, http_server):
    _, base, _, _ = http_server
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()  # porta chiusa: connessione rifiutata
    with SharedCache(tmp_path / "cache") as cache:
        for url in (f"http://127.0.0.1:{port}/x.fits", f"{base}/non_esiste.fits"):
            with pytest.raises(ImagesFitsError) as info:
                load_image(url, cache=cache, timeouts=NetworkTimeouts(connect=1.0, read=1.0))
            assert info.value.code == "NET_TIMEOUT"
        assert cache.usage().total_bytes == 0


# =============================================================================
# P4 — Visualizzazione (T2, T24, T31)
# =============================================================================

import matplotlib
from astropy import visualization as viz

from astrotwo.core.images_fits import PALETTES, STRETCHES, blend, set_display


def display_test_image(tmp_path):
    data = np.random.default_rng(24).gamma(2.0, 50.0, (20, 30)).astype(np.float32)
    data[3, 4] = np.nan
    return load_image(write_fits(tmp_path / "disp.fits", data, wcs_header(nx=30, ny=20)))


def test_t2_display_does_not_alter_data(tmp_path):
    image = display_test_image(tmp_path)
    before = image.data.tobytes()
    for stretch in STRETCHES:
        set_display(image, vmin=10.0, vmax=300.0, gamma=0.7, palette="viridis_r", stretch=stretch)
    assert image.data.tobytes() == before and image.data.dtype == np.float32


def _expected_values(data, vmin, vmax, stretch, gamma):
    data = data.astype(np.float32)  # presentazione in float32 (DC6)
    finite = np.isfinite(data)
    norm = viz.ManualInterval(vmin, vmax)(data[finite], clip=True)
    classes = {"linear": viz.LinearStretch, "log": viz.LogStretch, "sqrt": viz.SqrtStretch,
               "squared": viz.SquaredStretch, "asinh": viz.AsinhStretch}
    st = viz.HistEqStretch(norm) if stretch == "histeq" else classes[stretch]()
    out = st(norm, clip=True)
    if gamma != 1.0:
        out = viz.PowerStretch(gamma)(out, clip=True)
    full = np.full(data.shape, np.nan, dtype=np.float32)
    full[finite] = out
    return full


@pytest.mark.parametrize("gamma", [1.0, 0.5])
@pytest.mark.parametrize("stretch", STRETCHES)
def test_t24_transfer_functions(tmp_path, stretch, gamma):
    image = display_test_image(tmp_path)
    plane = set_display(image, vmin=20.0, vmax=250.0, gamma=gamma, stretch=stretch)
    expected = _expected_values(image.data, 20.0, 250.0, stretch, gamma)
    assert plane.values.dtype == np.float32 and plane.stretch == stretch and plane.gamma == gamma
    assert np.allclose(plane.values, expected.astype(np.float32), equal_nan=True, atol=0, rtol=0)
    assert np.isnan(plane.values[3, 4]) and plane.rgba[3, 4, 3] == 0  # non finito: trasparente


@pytest.mark.parametrize("palette", PALETTES)
def test_t24_palettes(tmp_path, palette):
    image = display_test_image(tmp_path)
    plane = set_display(image, vmin=0.0, vmax=400.0, palette=palette)
    values = _expected_values(image.data, 0.0, 400.0, "linear", 1.0)
    expected = matplotlib.colormaps[palette](np.where(np.isfinite(values), values, 0.0), bytes=True)
    expected[~np.isfinite(values), 3] = 0
    assert plane.palette == palette and np.array_equal(plane.rgba, expected)


def test_t24_unknown_options_and_default_gray(tmp_path):
    image = display_test_image(tmp_path)
    assert set_display(image, 0, 1).palette == "gray"
    for kwargs in (dict(palette="Stern"), dict(palette="rainbow"), dict(stretch="zscale")):
        with pytest.raises(ImagesFitsError) as info:
            set_display(image, 0, 1, **kwargs)
        assert info.value.code == "DISPLAY_OPTION_UNKNOWN"
    with pytest.raises(ValueError):
        set_display(image, 5, 5)


def test_t24_color_image_display(tmp_path):
    path = tmp_path / "c.png"
    PilImage.fromarray(gradient_rgb()).save(path)
    image = load_image(path)
    plane = set_display(image, vmin=0, vmax=255, stretch="sqrt")
    expected = np.stack([_expected_values(p, 0, 255, "sqrt", 1.0) for p in image.data])
    assert plane.palette is None and plane.values.shape == (3, 30, 40)
    assert np.allclose(plane.values, expected.astype(np.float32), rtol=0, atol=0)
    assert np.array_equal(plane.rgba[..., 0], np.round(expected[0] * np.float32(255)).astype(np.uint8))
    assert np.all(plane.rgba[..., 3] == 255)


def test_t31_blend_over_operator():
    rng = np.random.default_rng(31)
    bottom = rng.integers(0, 256, (6, 7, 4), dtype=np.uint8)
    bottom[..., 3] = 255
    top = rng.integers(0, 256, (6, 7, 4), dtype=np.uint8)
    out = blend([bottom, top], [1.0, 0.4])
    # Porter e Duff, "over", con colore premoltiplicato, ricalcolato qui con numpy.
    a_top = 0.4 * top[..., 3] / 255.0
    color = a_top[..., None] * top[..., :3] / 255.0 + (1 - a_top[..., None]) * bottom[..., :3] / 255.0
    alpha = a_top + (1 - a_top) * 1.0
    expected_rgb = np.round(color / alpha[..., None] * 255.0).astype(np.uint8)
    assert np.array_equal(out[..., :3], expected_rgb)
    assert np.all(out[..., 3] == 255)
    assert np.array_equal(blend([bottom], [1.0]), bottom)  # un solo piano opaco: invariato
    with pytest.raises(ImagesFitsError) as info:
        blend([bottom, top[:5]], [1.0, 0.5])
    assert info.value.code == "IMAGE_SHAPE_MISMATCH"


# =============================================================================
# P5 — Taglio, operazioni H5, contorni, salvataggio (T3, T4, T5, T20, T26)
# =============================================================================

import contourpy
from astropy.convolution import Box2DKernel, Gaussian2DKernel
from astropy.convolution import convolve as astropy_convolve_ref
from astropy.utils.data import get_pkg_data_filename

from astrotwo.core.coordinates_wcs import SkyFrame, convert_pixel_convention
from astrotwo.core.images_fits import OPERATIONS, contours, cutout, image_operation, save_fits


def rotated_wcs_image(tmp_path, name="rot.fits", nx=60, ny=40, value=None):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [150.0, 2.0]
    w.wcs.crpix = [25.3, 17.8]
    w.wcs.cd = [[-9e-4, 3e-4], [2e-4, 1.1e-3]]
    w.wcs.radesys = "ICRS"
    data = (np.arange(nx * ny, dtype=np.float32).reshape(ny, nx) if value is None
            else np.full((ny, nx), value, dtype=np.float32))
    header = w.to_header()
    header["BUNIT"] = "ADU"
    return load_image(write_fits(tmp_path / name, data, header))


def test_t3_cutout_corners_keep_sky_coordinates(tmp_path):
    image = rotated_wcs_image(tmp_path)
    center = convert_pixel_convention(30.0, 20.0, "numpy", "numpy")
    cut = cutout(image, center, (11, 15))
    assert cut.shape == (11, 15) and cut.history and "cutout" in cut.history[-1]
    original = WCS(fits.getheader(tmp_path / "rot.fits"))
    x0, y0 = 30 - 7, 20 - 5  # origine del taglio nell'originale (pixel numpy)
    xs, ys = np.array([0.0, 14.0, 0.0, 14.0]), np.array([0.0, 0.0, 10.0, 10.0])
    ra, dec = original.all_pix2world(xs + x0, ys + y0, 0)
    back_x, back_y = cut.wcs.wcs.world_to_pixel(SkyCoord(ra, dec, unit="deg"))
    assert np.max(np.hypot(back_x - xs, back_y - ys)) < 1e-6
    assert np.array_equal(cut.data, image.data[y0:y0 + 11, x0:x0 + 15])
    # Centro celeste e lato angolare.
    sky_center = SkyFrame(coord=original.pixel_to_world(30.0, 20.0))
    sky_cut = cutout(image, sky_center, 0.01 * u.deg)
    assert sky_cut.shape[0] > 5 and sky_cut.wcs is not None


def test_t3_cutout_trimmed_and_outside(tmp_path):
    image = rotated_wcs_image(tmp_path)
    edge = cutout(image, convert_pixel_convention(2.0, 2.0, "numpy", "numpy"), (9, 9))
    assert edge.shape == (7, 7) and "CUTOUT_TRIMMED" in [c for c, _ in edge.warnings]
    with pytest.raises(ImagesFitsError) as info:
        cutout(image, convert_pixel_convention(500.0, 500.0, "numpy", "numpy"), (5, 5))
    assert info.value.code == "CUTOUT_OUT_OF_RANGE"
    nowcs = load_image(write_fits(tmp_path / "nw.fits", np.ones((10, 10), dtype=np.float32)))
    with pytest.raises(ImagesFitsError) as info:
        cutout(nowcs, convert_pixel_convention(5.0, 5.0, "numpy", "numpy"), 3 * u.arcsec)
    assert info.value.code == "WCS_MISSING"


def test_t4_arithmetic(tmp_path):
    ones = rotated_wcs_image(tmp_path, "a.fits", value=1.0)
    twos = rotated_wcs_image(tmp_path, "b.fits", value=2.0)
    before = (ones.data.copy(), twos.data.copy())
    total = image_operation(ones, twos, "add")
    assert np.array_equal(total.data, np.full(ones.data.shape, 3.0)) and total.data.dtype == np.float64
    assert np.array_equal(ones.data, before[0]) and np.array_equal(twos.data, before[1])  # input intatti
    assert np.array_equal(image_operation(twos, ones, "sub").data, np.ones(ones.data.shape))
    assert np.array_equal(image_operation(twos, 4, "mul").data, np.full(ones.data.shape, 8.0))
    # "ADU" non è un'unità FITS riconosciuta da astropy: unità del prodotto non determinabile, dichiarato.
    product = image_operation(twos, twos, "mul")
    assert product.bunit is None and "UNIT_UNKNOWN" in [c for c, _ in product.warnings]
    jy = load_image(write_fits(tmp_path / "jy.fits", twos.data, _header_with_unit(twos, "Jy")))
    expected_unit = (u.Unit("Jy", format="fits") ** 2).to_string("fits")
    assert image_operation(jy, jy, "mul").bunit == expected_unit
    divided = image_operation(ones, 0.0, "div")
    assert np.all(np.isinf(divided.data)) and "NONFINITE_PIXELS" in [c for c, _ in divided.warnings]


def test_t4_grid_unit_and_operation_errors(tmp_path):
    a = rotated_wcs_image(tmp_path, "a.fits")
    smaller = rotated_wcs_image(tmp_path, "s.fits", nx=30)
    for b, code in [(smaller, "IMAGE_SHAPE_MISMATCH")]:
        with pytest.raises(ImagesFitsError) as info:
            image_operation(a, b, "add")
        assert info.value.code == code
    other_unit = load_image(write_fits(tmp_path / "u.fits", a.data, _header_with_unit(a, "Jy")))
    with pytest.raises(ImagesFitsError) as info:
        image_operation(a, other_unit, "add")
    assert info.value.code == "UNIT_MISMATCH"
    for op, operand in [("rotate", None), ("convolve", 3), ("add", "x"), ("normalize", 2)]:
        with pytest.raises(ImagesFitsError) as info:
            image_operation(a, operand, op)
        assert info.value.code == "OPERATION_UNSUPPORTED"
    assert set(OPERATIONS) == {"add", "sub", "mul", "div", "convolve", "normalize", "flip_x", "flip_y"}


def _header_with_unit(image, unit):
    header = fits.Header(image.header)
    header["BUNIT"] = unit
    return header


def test_t5_convolution_matches_scipy(tmp_path):
    yy, xx = np.mgrid[:20, :30]
    gradient = (2.0 * xx + 3.0 * yy).astype(np.float64)
    image = load_image(write_fits(tmp_path / "g.fits", gradient))
    kernel = Box2DKernel(3)  # media 3×3, normalizzata
    result = image_operation(image, kernel, "convolve")
    # Bordo riempito con 0 (default di astropy) = mode "constant", cval 0 di SciPy.
    expected = ndimage.convolve(gradient, kernel.array, mode="constant", cval=0.0)
    assert np.allclose(result.data, expected, rtol=0, atol=1e-12)
    gauss = image_operation(image, Gaussian2DKernel(1.5), "convolve")
    assert np.allclose(gauss.data, astropy_convolve_ref(gradient, Gaussian2DKernel(1.5)), rtol=0, atol=0)


def test_h5_normalize_divides_by_mean(tmp_path):
    data = np.random.default_rng(5).normal(40, 3, (10, 12))
    data[2, 3] = np.nan
    image = load_image(write_fits(tmp_path / "n.fits", data))
    result = image_operation(image, None, "normalize")
    assert np.allclose(result.data, data / np.nanmean(data), equal_nan=True, rtol=0, atol=0)
    assert result.bunit is None and "media" in result.history[-1]
    zero = load_image(write_fits(tmp_path / "z.fits", np.array([[1.0, -1.0], [1.0, -1.0]])))
    with pytest.raises(ImagesFitsError) as info:
        image_operation(zero, None, "normalize")
    assert info.value.code == "OPERATION_UNSUPPORTED"


@pytest.mark.parametrize("op,axis", [("flip_x", 1), ("flip_y", 0)])
def test_t20_flips_update_wcs(tmp_path, op, axis):
    image = rotated_wcs_image(tmp_path)
    flipped = image_operation(image, None, op)
    assert np.array_equal(flipped.data, np.flip(image.data.astype(np.float64), axis=axis))
    ny, nx = image.shape
    xs, ys = np.meshgrid(np.arange(nx, dtype=float), np.arange(ny, dtype=float))
    xs, ys = xs.ravel(), ys.ravel()
    fx, fy = (nx - 1 - xs, ys) if op == "flip_x" else (xs, ny - 1 - ys)
    original = WCS(fits.getheader(tmp_path / "rot.fits"))
    sep = original.pixel_to_world(xs, ys).separation(flipped.wcs.wcs.pixel_to_world(fx, fy)).deg
    assert np.max(sep) < 1e-9  # stesso cielo per lo stesso pixel fisico
    twice = image_operation(flipped, None, op)
    assert np.array_equal(twice.data, image.data.astype(np.float64))


def test_t20_flip_rejected_with_distortion(tmp_path):
    path = get_pkg_data_filename("data/dss.14.29.56-62.41.05.fits.gz", package="astropy.wcs.tests")
    import warnings as _w
    with _w.catch_warnings():
        _w.simplefilter("ignore")
        image = load_image(path)
    assert image.wcs is not None
    with pytest.raises(ImagesFitsError) as info:
        image_operation(image, None, "flip_x")
    assert info.value.code == "OPERATION_UNSUPPORTED"


def test_h7_contours_match_contourpy(tmp_path):
    yy, xx = np.mgrid[:40, :50]
    data = np.exp(-((xx - 24.3) ** 2 + (yy - 19.7) ** 2) / 60.0) * 100.0
    image = rotated_wcs_image(tmp_path, nx=50, ny=40)
    image = load_image(write_fits(tmp_path / "c.fits", data, image.header))
    result = contours(image, [10.0, 50.0])
    generator = contourpy.contour_generator(z=data, line_type=contourpy.LineType.Separate)
    for level, curves in zip([10.0, 50.0], result.curves, strict=True):
        expected = generator.lines(level)
        assert len(curves) == len(expected)
        for got, exp in zip(curves, expected, strict=True):
            assert np.allclose(got, exp, rtol=0, atol=0)
    sky = result.to_sky(image)
    ra, dec = WCS(image.header).all_pix2world(result.curves[0][0][:, 0], result.curves[0][0][:, 1], 0)
    assert np.max(sky[0][0].coord.separation(SkyCoord(ra, dec, unit="deg")).deg) < 1e-12


def test_t26_save_fits_roundtrip(tmp_path):
    image = rotated_wcs_image(tmp_path)
    cut = cutout(image, convert_pixel_convention(30.0, 20.0, "numpy", "numpy"), (11, 15))
    target = save_fits(cut, tmp_path / "taglio.fits")
    with fits.open(target) as hdul:
        header, data = hdul[0].header, hdul[0].data
    assert np.array_equal(data, cut.data)
    assert header["A2ORIGIN"] == str(image.origin) and header["A2DATE"].endswith("Z")
    assert any("cutout" in str(h) for h in header["HISTORY"])
    reread = WCS(header)
    xs, ys = np.array([0.0, 14.0]), np.array([0.0, 10.0])
    assert np.max(reread.pixel_to_world(xs, ys).separation(cut.wcs.wcs.pixel_to_world(xs, ys)).deg) < 1e-12
    with pytest.raises(OSError):
        save_fits(cut, target)  # niente sovrascrittura implicita


# =============================================================================
# P6 — Immagini grandi (T11, T25). Soglie piccole configurate nel test.
# =============================================================================

from astrotwo.core.images_fits import LargeImageLimits, open_large_image

SMALL = LargeImageLimits(memory_bytes=10_000, two_level_bytes=50_000, compressed_bytes=10_000, preview_max_side=16)


def star_field(ny, nx, dtype=np.float32):
    yy, xx = np.mgrid[:ny, :nx]
    image = 100.0 + 5000.0 * np.exp(-((xx - nx * 0.43) ** 2 + (yy - ny * 0.57) ** 2) / (2 * 1.8**2))
    image = image + np.random.default_rng(11).normal(0, 2.0, image.shape)
    return image.astype(dtype)


def test_t25_strategy_rules(tmp_path):
    small = write_fits(tmp_path / "small.fits", np.zeros((40, 50), np.float32))  # 8000 byte
    mapped = write_fits(tmp_path / "mapped.fits", star_field(60, 100))  # 24000 byte, senza scala
    scaled = write_fits(tmp_path / "scaled.fits", np.ones((100, 150), np.uint16))  # 30000 byte, BZERO
    big = write_fits(tmp_path / "big.fits", star_field(100, 200))  # 80000 byte
    comp = tmp_path / "comp.fits"
    fits.HDUList([fits.PrimaryHDU(), fits.CompImageHDU(np.ones((60, 100), np.int16), compression_type="RICE_1")]).writeto(comp)
    expected = {small: "memory", mapped: "memmap", scaled: "two_level", big: "two_level", comp: "two_level"}
    for path, strategy in expected.items():
        image = open_large_image(path, limits=SMALL)
        assert image.strategy == strategy, (path.name, image.strategy)
        assert image.limits == SMALL
    assert "BZERO" in open_large_image(scaled, limits=SMALL).strategy_reason
    assert open_large_image(comp, limits=LargeImageLimits(compressed_bytes=20_000, memory_bytes=10_000,
                                                          two_level_bytes=50_000)).strategy == "memory"
    assert load_image(small).strategy == "memory"  # soglie di default: 1 GB


def test_t25_memmap_reads_from_disk(tmp_path):
    path = write_fits(tmp_path / "mapped.fits", star_field(60, 100))
    image = open_large_image(path, limits=SMALL)
    with fits.open(path, memmap=False) as hdul:
        expected = hdul[0].data
    assert image.memory_bytes == 0 and image.shape == (60, 100) and not image.is_preview
    assert np.array_equal(image.data, expected)
    assert np.array_equal(image.read_region(10, 20, 5, 9), expected[5:9, 10:20])


def test_t11_two_levels_preview_and_original_pixels(tmp_path):
    path = write_fits(tmp_path / "big.fits", star_field(100, 200))
    image = open_large_image(path, limits=SMALL)
    with fits.open(path, memmap=False) as hdul:
        full = hdul[0].data
    step = -(-200 // 16)  # passo intero più piccolo che rispetta 16 pixel sul lato lungo
    assert image.is_preview and image.preview_step == step and image.shape == (100, 200)
    assert max(image.data.shape) <= 16 and np.array_equal(image.data, full[::step, ::step])
    assert image.memory_bytes == image.data.nbytes
    # Misura su un pixel = valore del pixel originale (letto con section, non dall'anteprima).
    assert image.read_region(137, 138, 61, 62)[0, 0] == full[61, 137]
    assert np.array_equal(image.read_region(0, 200, 98, 100), full[98:100, :])
    # Il display usa l'anteprima.
    assert set_display(image, 0, 6000).values.shape == image.data.shape


def test_t11_measurements_never_use_the_preview(tmp_path):
    path = write_fits(tmp_path / "big.fits", star_field(100, 200), wcs_header(nx=200, ny=100))
    preview = open_large_image(path, limits=SMALL)
    full = load_image(path)  # soglie di default: tutto in memoria
    start = (86.0, 57.0)
    a = star_centroid(preview, start, 11, 8.0, 14.0)
    b = star_centroid(full, start, 11, 8.0, 14.0)
    assert (a.x, a.y, a.window, a.background) == (b.x, b.y, b.window, b.background)
    center = convert_pixel_convention(100.0, 50.0, "numpy", "numpy")
    cut_preview, cut_full = cutout(preview, center, (21, 31)), cutout(full, center, (21, 31))
    assert np.array_equal(cut_preview.data, cut_full.data) and cut_preview.strategy == "memory"
    xs, ys = np.array([0.0, 30.0]), np.array([0.0, 20.0])
    sep = cut_preview.wcs.wcs.pixel_to_world(xs, ys).separation(cut_full.wcs.wcs.pixel_to_world(xs, ys)).deg
    assert np.max(sep) == 0.0
    for call in (lambda: image_operation(preview, 2.0, "mul"), lambda: contours(preview, [500.0]),
                 lambda: save_fits(preview, tmp_path / "x.fits")):
        with pytest.raises(ImagesFitsError) as info:
            call()
        assert info.value.code == "PREVIEW_NOT_MEASURABLE"
    with pytest.raises(ImagesFitsError) as info:
        preview.read_region(190, 210, 0, 5)
    assert info.value.code == "CUTOUT_OUT_OF_RANGE"


def test_t25_limits_validation():
    with pytest.raises(ValueError):
        LargeImageLimits(memory_bytes=0)
    with pytest.raises(ValueError):
        LargeImageLimits(memory_bytes=10, two_level_bytes=5)
    assert LargeImageLimits() == LargeImageLimits(10**9, 4 * 10**9, 10**9, 4096)


# =============================================================================
# P7 — Ricampionamento, RGB, mosaico (T12, T13, T14, T21, T22, T23)
# =============================================================================

from reproject import reproject_exact as ref_exact
from reproject import reproject_interp as ref_interp
from reproject.mosaicking import reproject_and_coadd as ref_coadd

from astrotwo.core.images_fits import RESAMPLING_METHODS, mosaic, reproject, resample_to_reference, rgb_composite


def sky_image(tmp_path, name, crval=(150.0, 2.0), scale=1e-3, nx=40, ny=30, rot=0.0, seed=0, unit="Jy"):
    c, s = np.cos(np.radians(rot)), np.sin(np.radians(rot))
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = list(crval)
    w.wcs.crpix = [nx / 2 + 0.5, ny / 2 + 0.5]
    w.wcs.cd = [[-scale * c, scale * s], [scale * s, scale * c]]
    w.wcs.radesys = "ICRS"
    header = w.to_header()
    header["BUNIT"] = unit
    data = np.random.default_rng(seed).gamma(3.0, 20.0, (ny, nx)).astype(np.float32)
    return load_image(write_fits(tmp_path / name, data, header))


def expected_component(values, vmin, vmax, stretch):
    out = np.zeros(values.shape)
    finite = np.isfinite(values)
    norm = viz.ManualInterval(vmin, vmax)(values[finite], clip=True)
    st = {"linear": viz.LinearStretch, "sqrt": viz.SqrtStretch, "log": viz.LogStretch}[stretch]()
    out[finite] = np.round(st(norm, clip=True) * 255.0)
    return out.astype(np.uint8)


def test_t23_resample_quality(tmp_path):
    reference = sky_image(tmp_path, "ref.fits")
    # Immagine spostata di metà campo in RA: copre circa metà del riferimento.
    shifted = sky_image(tmp_path, "half.fits", crval=(150.0 - 20e-3 / np.cos(np.radians(2.0)), 2.0), seed=1)
    for method in RESAMPLING_METHODS:
        result = resample_to_reference(shifted, reference, method)
        function = {"nearest": lambda *a, **k: ref_interp(*a, order="nearest-neighbor", **k),
                    "bilinear": lambda *a, **k: ref_interp(*a, order="bilinear", **k),
                    "flux": ref_exact}[method]
        expected, footprint = function((shifted.data.astype(np.float64), shifted.wcs.wcs), reference.wcs.wcs,
                                       shape_out=reference.shape)
        assert np.array_equal(result.footprint, footprint)
        assert np.allclose(result.image.data, expected, equal_nan=True, rtol=0, atol=0)
        assert result.coverage_percent == pytest.approx(100.0 * np.count_nonzero(footprint > 0) / footprint.size)
        assert 30.0 < result.coverage_percent < 70.0 and result.method == method
        assert "ricampionamento" in result.image.history[-1]
    with pytest.raises(TypeError):
        resample_to_reference(shifted, reference)  # metodo obbligatorio, nessun default
    with pytest.raises(ImagesFitsError) as info:
        resample_to_reference(shifted, reference, "cubic")
    assert info.value.code == "OPERATION_UNSUPPORTED"
    assert len(reproject([shifted, reference], reference, "nearest")) == 2


def test_t12_rgb_three_images_on_smallest_pixel(tmp_path):
    images = [sky_image(tmp_path, f"b{i}.fits", scale=s, rot=r, seed=i)
              for i, (s, r) in enumerate([(1.2e-3, 10.0), (0.9e-3, -5.0), (1.5e-3, 0.0)])]
    display = [(0.0, 150.0, "linear"), (10.0, 200.0, "sqrt"), (0.0, 120.0, "log")]
    rgb = rgb_composite(images, mode="rgb", display=display)
    assert rgb.reference_origin == images[1].origin  # pixel angolare più piccolo
    reference = images[1]
    for k, (image, (vmin, vmax, stretch)) in enumerate(zip(images, display, strict=True)):
        values, footprint = ref_interp((image.data.astype(np.float64), image.wcs.wcs), reference.wcs.wcs,
                                       shape_out=reference.shape, order="nearest-neighbor")
        expected = expected_component(values, vmin, vmax, stretch)
        expected[~rgb.coverage] = 0
        assert np.array_equal(rgb.planes[k], expected), k
    assert rgb.planes.dtype == np.uint8 and rgb.components == tuple(im.origin for im in images)
    assert rgb.display == tuple(display) and rgb.method == "nearest"


def test_t13_rgb_two_images_third_is_mean(tmp_path):
    a = sky_image(tmp_path, "a.fits", seed=3)
    b = sky_image(tmp_path, "b.fits", seed=4, rot=3.0)
    rgb = rgb_composite([a, b], display=[(0, 150, "linear"), (0, 150, "linear")])
    expected_b = np.round((rgb.planes[0].astype(np.float64) + rgb.planes[1]) / 2.0).astype(np.uint8)
    assert np.array_equal(rgb.planes[2], expected_b) and rgb.components[2] is None


@pytest.mark.parametrize("swap", [False, True])
def test_t14_t22_rgb_diff_single_scale(tmp_path, swap):
    base = sky_image(tmp_path, "base.fits", seed=5)
    data = base.data.astype(np.float64).copy()
    data[:15] += 40.0   # differenze positive di ampiezza 40
    data[15:] -= 90.0   # differenze negative di ampiezza 90
    other = load_image(write_fits(tmp_path / "other.fits", data.astype(np.float32), base.header))
    first, second = (other, base) if not swap else (base, other)
    rgb = rgb_composite([first, second], reference=base, mode="rgb_diff")
    diff = first.data.astype(np.float64) - second.data.astype(np.float64)
    scale = 255.0 / np.max(np.abs(diff))
    assert rgb.scale == pytest.approx(scale, rel=1e-12)
    assert np.array_equal(rgb.planes[0], np.round(np.clip(diff, 0, None) * scale).astype(np.uint8))
    assert np.array_equal(rgb.planes[1], np.round(np.clip(-diff, 0, None) * scale).astype(np.uint8))
    assert not np.any(rgb.planes[2])  # B = 0
    assert rgb.planes.max() == 255  # un solo fattore: la differenza più grande arriva a 255


def test_rgb_wavelength_order_and_errors(tmp_path):
    a, b, c = (sky_image(tmp_path, f"w{i}.fits", seed=10 + i) for i in range(3))
    display = [(0, 100, "linear"), (0, 200, "linear"), (0, 300, "linear")]
    rgb = rgb_composite([a, b, c], reference=a, display=display, wavelengths=[500, 2200, 1250] * u.nm)
    assert rgb.components == (b.origin, c.origin, a.origin)  # la lunghezza d'onda più lunga in R
    assert rgb.display == ((0.0, 200.0, "linear"), (0.0, 300.0, "linear"), (0.0, 100.0, "linear"))
    nowcs = load_image(write_fits(tmp_path / "nw.fits", np.ones((30, 40), np.float32)))
    cases = [([a], dict(display=display[:1]), "RGB_INPUT_INVALID"),
             ([a, b, c, a], dict(display=display + display[:1]), "RGB_INPUT_INVALID"),
             ([a, b, c], dict(mode="rgb_diff"), "RGB_INPUT_INVALID"),
             ([a, b], dict(), "RGB_INPUT_INVALID"),  # parametri di display mancanti
             ([a, nowcs], dict(display=display[:2]), "WCS_MISSING")]
    for images, kwargs, code in cases:
        with pytest.raises(ImagesFitsError) as info:
            rgb_composite(images, **kwargs)
        assert info.value.code == code
    other_unit = sky_image(tmp_path, "u.fits", unit="MJy/sr")
    with pytest.raises(ImagesFitsError) as info:
        rgb_composite([a, other_unit], mode="rgb_diff")
    assert info.value.code == "UNIT_MISMATCH"


@pytest.mark.parametrize("method", RESAMPLING_METHODS)
def test_t21_mosaic_matches_reproject_and_coadd(tmp_path, method):
    left = sky_image(tmp_path, "l.fits", crval=(150.0 - 12e-3, 2.0), seed=20)
    right = sky_image(tmp_path, "r.fits", crval=(150.0 + 12e-3, 2.0), seed=21, rot=7.0)
    reference = sky_image(tmp_path, "grid.fits", nx=70, ny=40, scale=1e-3, seed=22)
    result = mosaic([left, right], reference, method)
    function = {"nearest": lambda *a, **k: ref_interp(*a, order="nearest-neighbor", **k),
                "bilinear": lambda *a, **k: ref_interp(*a, order="bilinear", **k),
                "flux": ref_exact}[method]
    expected, footprint = ref_coadd(
        [(im.data.astype(np.float64), im.wcs.wcs) for im in (left, right)], reference.wcs.wcs,
        shape_out=reference.shape, reproject_function=function, combine_function="mean", match_background=False,
    )
    assert np.allclose(result.image.data, expected, equal_nan=True, rtol=0, atol=0)
    assert np.array_equal(result.footprint, footprint) and result.method == method
    assert "nessuna correzione del fondo" in result.image.history[-1]


# =============================================================================
# Decisioni del proprietario del 2026-10-10: commento contro .hhh (T32) e
# tetto di memoria A10 per le operazioni sull'immagine intera (T33).
# =============================================================================


def calibration_text_at(nx, ny, crval):
    header = wcs_header(nx=nx, ny=ny, crval=crval)
    for card in (("NAXIS2", ny), ("NAXIS1", nx), ("NAXIS", 2)):
        header.insert(0, card)
    return header.tostring()


def png_with_comment(path, nx, ny, text):
    info = PngInfo()
    info.add_text("Comment", text)
    PilImage.fromarray(gradient_rgb(nx, ny)).save(path, pnginfo=info)
    return path


def test_t32_comment_wins_and_different_hhh_is_reported(tmp_path):
    nx, ny = 40, 30
    png = png_with_comment(tmp_path / "foto.png", nx, ny, calibration_text_at(nx, ny, (150.0, 2.0)))
    hhh = tmp_path / "foto.hhh"
    # Stesso WCS: il .hhh è ignorato, nessun avviso di differenza.
    hhh.write_text(calibration_text_at(nx, ny, (150.0, 2.0)), encoding="latin-1")
    same = load_image(png)
    codes = [code for code, _ in same.warnings]
    assert same.calibration_source == "comment" and "HHH_IGNORED" in codes and "HHH_WCS_DIFFERS" not in codes
    # WCS diverso: vale il commento, l'avviso cita le parole chiave diverse.
    hhh.write_text(calibration_text_at(nx, ny, (151.0, 2.0)), encoding="latin-1")
    different = load_image(png)
    messages = dict(different.warnings)
    assert different.calibration_source == "comment" and "HHH_WCS_DIFFERS" in messages
    assert "CRVAL1" in messages["HHH_WCS_DIFFERS"] and "CRVAL2" not in messages["HHH_WCS_DIFFERS"]
    expected = WCS(fits.Header.fromstring(calibration_text_at(nx, ny, (150.0, 2.0))))
    assert different.wcs.wcs.wcs.compare(expected.wcs, tolerance=1e-12)
    # .hhh non valido accanto a un commento valido: due calibrazioni diverse, avviso.
    hhh.write_text("non e un header FITS", encoding="latin-1")
    assert "HHH_WCS_DIFFERS" in dict(load_image(png).warnings)


TINY = LargeImageLimits(memory_bytes=2_000, two_level_bytes=50_000, compressed_bytes=2_000, preview_max_side=16,
                        operation_bytes=2_000)


def test_t33_memory_limit_before_whole_image_operations(tmp_path):
    header = wcs_header(nx=20, ny=10)
    a = open_large_image(write_fits(tmp_path / "a.fits", star_field(10, 20), header), limits=TINY)
    b = open_large_image(write_fits(tmp_path / "b.fits", star_field(10, 20), header), limits=TINY)
    assert a.strategy == "memory"  # 800 byte di dati: sotto la soglia di 2000 byte
    pixels = 200
    calls = {
        "operazione add": (lambda: image_operation(a, b, "add"), pixels * 24),
        "operazione mul": (lambda: image_operation(a, 2.0, "mul"), pixels * 16),
        "operazione convolve": (lambda: image_operation(a, Box2DKernel(3), "convolve"), pixels * 24),
        "operazione flip_x": (lambda: image_operation(a, None, "flip_x"), pixels * 16),
        "contorni": (lambda: contours(a, [500.0]), pixels * 16),
        # (4 + 4) × N di risultato + 16 × N di lavoro del blocco (un solo blocco)
        "visualizzazione": (lambda: set_display(a, 0, 6000), pixels * 8 + pixels * 16),
        "ricampionamento": (lambda: resample_to_reference(a, b, "nearest"), pixels * 8 + 2 * pixels * 8),
        "mosaico": (lambda: mosaic([a, b], b, "nearest"), 2 * pixels * 8 + 6 * pixels * 8),
        "RGB": (lambda: rgb_composite([a, b], display=[(0, 1, "linear")] * 2), 2 * pixels * 8 + 6 * pixels * 8),
    }
    for what, (call, needed) in calls.items():
        with pytest.raises(ImagesFitsError) as info:
            call()
        assert info.value.code == "MEMORY_LIMIT_EXCEEDED", what
        assert info.value.details == {"needed_bytes": needed, "limit_bytes": 2_000}, what
        assert info.value.message.startswith(what)
    # Salvataggio: dati più la copia big-endian (200 × 4 × 2 = 1600 byte) → sotto il tetto.
    assert save_fits(a, tmp_path / "ok.fits").exists()
    # Taglio: solo i pixel del taglio contano.
    center = convert_pixel_convention(10.0, 5.0, "numpy", "numpy")
    assert cutout(a, center, (5, 5)).data.shape == (5, 5)
    # Con il limite di default (4 GB) le stesse operazioni riescono.
    full = load_image(tmp_path / "a.fits")
    assert image_operation(full, load_image(tmp_path / "b.fits"), "add").data.shape == (10, 20)


def test_t33_memmap_image_refused_instead_of_loaded(tmp_path):
    # Immagine oltre il tetto in memoria, letta dal disco su richiesta: le operazioni
    # sull'immagine intera non la caricano, il taglio piccolo sì.
    path = write_fits(tmp_path / "mapped.fits", star_field(60, 100), wcs_header(nx=100, ny=60))
    image = open_large_image(path, limits=dataclasses.replace(SMALL, operation_bytes=10_000))
    assert image.strategy == "memmap"
    for call in (lambda: image_operation(image, 2.0, "mul"), lambda: save_fits(image, tmp_path / "x.fits"),
                 lambda: contours(image, [500.0]), lambda: set_display(image, 0, 6000)):
        with pytest.raises(ImagesFitsError) as info:
            call()
        assert info.value.code == "MEMORY_LIMIT_EXCEEDED"
    center = convert_pixel_convention(50.0, 30.0, "numpy", "numpy")
    with pytest.raises(ImagesFitsError) as info:
        cutout(image, center, (60, 100))  # 24000 byte, oltre 10000
    assert info.value.code == "MEMORY_LIMIT_EXCEEDED"
    # La strategia di caricamento (A10) e il limite delle operazioni sono separati:
    # con il limite di default la stessa immagine in memmap si visualizza.
    assert open_large_image(path, limits=SMALL).strategy == "memmap"
    assert set_display(open_large_image(path, limits=SMALL), 0, 6000).values.shape == (60, 100)
    with fits.open(path, memmap=False) as hdul:
        assert np.array_equal(cutout(image, center, (11, 21)).data, hdul[0].data[25:36, 40:61])


def test_t34_large_display_in_float32_blocks():
    # 6000 × 6000 si visualizza con il limite di default, a blocchi in float32,
    # senza copiare l'immagine intera in float64 (decisione del proprietario del 2026-10-10).
    import tracemalloc

    rng = np.random.default_rng(34)
    data = rng.gamma(2.0, 50.0, (6000, 6000)).astype(np.float32)
    data[17, 23] = np.nan
    tracemalloc.start()
    try:
        plane = set_display(data, vmin=0.0, vmax=400.0, gamma=0.8, palette="viridis", stretch="asinh")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    n = data.size
    assert plane.values.shape == data.shape and plane.values.dtype == np.float32
    # Risultato (4 + 4 byte per pixel) più un blocco: molto meno di una copia float64 (8 byte per pixel).
    assert peak < 8 * n + 64 * (1 << 20), peak
    rows = slice(2990, 3010)
    expected = _expected_values(data[rows], 0.0, 400.0, "asinh", 0.8)
    assert np.allclose(plane.values[rows], expected, equal_nan=True, rtol=0, atol=0)
    assert np.isnan(plane.values[17, 23]) and plane.rgba[17, 23, 3] == 0


def test_t34_histeq_uses_the_whole_plane_across_blocks(tmp_path, monkeypatch):
    # Con blocchi piccoli il risultato resta quello dell'equalizzazione su tutto il piano.
    import astrotwo.core.images_fits as module

    monkeypatch.setattr(module, "_DISPLAY_BLOCK_PIXELS", 64)
    image = display_test_image(tmp_path)
    plane = set_display(image, vmin=20.0, vmax=250.0, stretch="histeq")
    expected = _expected_values(image.data, 20.0, 250.0, "histeq", 1.0)
    assert np.allclose(plane.values, expected, equal_nan=True, rtol=0, atol=0)


def test_external_calibration_parameter(tmp_path):
    # D14-11: calibrazione esterna usata solo se l'immagine non ne ha una, sempre dichiarata.
    from types import SimpleNamespace
    from astropy.wcs import WCS

    header = fits.Header({"NAXIS": 2, "NAXIS1": 8, "NAXIS2": 6, "CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN",
                          "CRPIX1": 4.5, "CRPIX2": 3.5, "CRVAL1": 150.0, "CRVAL2": 2.0, "CDELT1": -0.01,
                          "CDELT2": 0.01, "RADESYS": "ICRS"})
    path = tmp_path / "nowcs.fits"
    fits.PrimaryHDU(np.ones((6, 8), dtype=np.float32)).writeto(path)
    external = SimpleNamespace(header=header, source="prova del test")
    image = load_image(path, calibration=external)
    assert image.calibration_source == "external" and ("EXTERNAL_CALIBRATION_USED", "calibrazione astrometrica esterna: prova del test") in image.warnings
    assert np.allclose(image.wcs.wcs.pixel_to_world_values(3.5, 2.5), WCS(header).pixel_to_world_values(3.5, 2.5))
    with pytest.raises(TypeError):
        load_image(path, calibration=SimpleNamespace(header=header))


# =============================================================================
# T37–T40: corona di default (D11-8) e limiti iniziali (D41-3), 2026-10-15/16
# =============================================================================

from astropy.visualization import ZScaleInterval  # noqa: E402

from astrotwo.core.images_fits import suggest_display_limits  # noqa: E402


def test_t37_default_annulus():
    image = synthetic_image()
    default = star_centroid(image, (46.8, 39.2), box_size=15)
    explicit = star_centroid(image, (46.8, 39.2), box_size=15, annulus_inner=15.0, annulus_outer=22.5)
    assert (default.x, default.y, default.background) == (explicit.x, explicit.y, explicit.background)
    assert (default.annulus_inner, default.annulus_outer) == (15.0, 22.5)


def test_t38_display_limits_zscale():
    image = synthetic_image(seed=38, extra_star=(20.0, 20.0)).astype(np.float64)
    image[5, 5] = np.nan
    before = image.copy()
    limits = suggest_display_limits(image)
    expected = ZScaleInterval().get_limits(image[np.isfinite(image)].astype(np.float64))
    assert (limits.vmin, limits.vmax) == tuple(float(v) for v in expected)
    assert limits.n_pixels == image.size - 1 and limits.parameters["n_samples"] == 1000
    assert "zscale" in limits.method and limits.unit == "non dichiarata"
    assert np.array_equal(image, before, equal_nan=True)


def test_t39_display_limits_repeatable_and_errors():
    image = synthetic_image()
    assert suggest_display_limits(image) == suggest_display_limits(image)
    expect_error("DISPLAY_LIMITS_UNDEFINED", suggest_display_limits, np.full((10, 10), 7.0))
    expect_error("DISPLAY_LIMITS_UNDEFINED", suggest_display_limits, np.full((10, 10), np.nan))
    expect_error("DISPLAY_METHOD_UNKNOWN", suggest_display_limits, image, method="minmax")


def test_t40_display_limits_color_and_two_level(tmp_path):
    planes = np.stack([synthetic_image(seed=s) for s in (1, 2, 3)]).astype(np.float64)

    class Color:
        data = planes
        color = True
        bunit = None

    limits = suggest_display_limits(Color())
    expected = ZScaleInterval().get_limits(planes.ravel())
    assert (limits.vmin, limits.vmax) == tuple(float(v) for v in expected) and "colori" in limits.notes[0]
    path = write_fits(tmp_path / "big.fits", star_field(100, 200))
    preview = open_large_image(path, limits=SMALL)
    assert preview.is_preview
    two = suggest_display_limits(preview)
    data = np.asarray(preview.data, dtype=np.float64)
    assert (two.vmin, two.vmax) == tuple(float(v) for v in ZScaleInterval().get_limits(data[np.isfinite(data)]))
    assert any("anteprima" in n for n in two.notes)
