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
