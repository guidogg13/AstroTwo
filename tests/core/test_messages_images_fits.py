# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 11 con codice + ``params`` (D40-3; ``40`` §3.7.1, T18–T19).

Provoca gli errori e gli avvisi che i test del modulo non raggiungono già; ogni istanza è controllata contro il
catalogo alla creazione (``tests/conftest.py``) e qui si verifica di nuovo la coppia (codice, ragione) attesa.
"""

from __future__ import annotations

import astropy.units as u
import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from astrotwo.core import images_fits as im
from astrotwo.core.coordinates_wcs import SkyFrame
from astrotwo.core.images_fits import ImagesFitsError, load_image
from tests.core.test_images_fits import wcs_header, write_fits
from tests.message_helpers import check_error


def raised(func, *args, **kwargs):
    with pytest.raises(ImagesFitsError) as info:
        func(*args, **kwargs)
    return check_error(info.value)


@pytest.fixture
def images(tmp_path):
    data = np.random.default_rng(2).normal(10, 1, (40, 60)).astype(np.float32)
    with_wcs = load_image(write_fits(tmp_path / "a.fits", data, wcs_header()))
    no_wcs = load_image(write_fits(tmp_path / "b.fits", data))
    return with_wcs, no_wcs, tmp_path


def test_load_errors(tmp_path):
    assert raised(load_image, tmp_path / "missing.fits") == ("FITS_UNREADABLE", "file_unreadable")
    gz = tmp_path / "bad.gz"
    gz.write_bytes(b"\x1f\x8b\x08\x00broken")
    assert raised(im.detect_format, str(gz))[0] == "FORMAT_UNSUPPORTED"
    two = tmp_path / "two.fits"
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(np.zeros((5, 5)), name="A"), fits.ImageHDU(np.zeros((5, 5)))]
                 ).writeto(two)
    assert raised(load_image, two)[1] == "images"
    assert raised(load_image, two, hdu="NOPE") == ("HDU_NOT_IMAGE", "no_such_hdu_listed")
    assert raised(load_image, two, hdu=0)[1] == "not_an_image"
    assert raised(load_image, two, rgb=True) == ("RGB_INPUT_INVALID", "no_rgb_hdu")
    cube = tmp_path / "cube.fits"
    write_fits(cube, np.zeros((3, 4, 5)))
    assert raised(load_image, cube)[0] in ("CUBE_NOT_SUPPORTED", "HDU_NOT_IMAGE")
    rgb2 = tmp_path / "rgb2.fits"
    fits.HDUList([fits.PrimaryHDU(np.zeros((3, 4, 5))), fits.ImageHDU(np.zeros((3, 4, 5)))]).writeto(rgb2)
    assert raised(load_image, rgb2, rgb=True) == ("HDU_CHOICE_REQUIRED", "rgb")
    assert raised(load_image, rgb2, hdu="NOPE", rgb=True) == ("HDU_NOT_IMAGE", "no_such_hdu")
    plain = tmp_path / "plain.fits"
    write_fits(plain, np.zeros((4, 5)))
    assert raised(load_image, plain, rgb=True)[0] == "RGB_INPUT_INVALID"
    empty = tmp_path / "empty.fits"
    fits.HDUList([fits.PrimaryHDU()]).writeto(empty)
    assert raised(load_image, empty) == ("HDU_NOT_IMAGE", "no_image_hdu")
    with pytest.raises(ImagesFitsError) as info:
        load_image(two, hdu=1, rgb=True)
    check_error(info.value)


def test_image_errors(images, monkeypatch):
    with_wcs, no_wcs, tmp_path = images
    assert raised(with_wcs.read_region, 0, 1000, 0, 5) == ("CUTOUT_OUT_OF_RANGE", "region")
    assert raised(im.cutout, no_wcs, SkyFrame.from_lonlat(150 * u.deg, 2 * u.deg, "icrs"), 5) == ("WCS_MISSING", "cutout_center")
    assert raised(im.cutout, no_wcs, im.PixelPosition(5.0, 5.0, "numpy"), 1 * u.arcsec) == ("WCS_MISSING", "cutout_size")
    assert raised(im.cutout, with_wcs, im.PixelPosition(5000.0, 5000.0, "numpy"), 3) == ("CUTOUT_OUT_OF_RANGE", "outside")
    other = load_image(write_fits(tmp_path / "c.fits", np.zeros((10, 10), dtype=np.float32)))
    assert raised(im.image_operation, with_wcs, other, "add") == ("IMAGE_SHAPE_MISMATCH", "sizes")
    shifted = load_image(write_fits(tmp_path / "d.fits", np.zeros((40, 60), dtype=np.float32), wcs_header(crval=(10.0, 5.0))))
    assert raised(im.image_operation, with_wcs, shifted, "add") == ("IMAGE_SHAPE_MISMATCH", "grids")
    assert raised(im.image_operation, with_wcs, 2.0, "nope")[1] == "operation_unknown"
    assert raised(im.image_operation, with_wcs, "x", "add") == ("OPERATION_UNSUPPORTED", "operand_required")
    assert raised(im.image_operation, with_wcs, 2.0, "convolve") == ("OPERATION_UNSUPPORTED", "kernel_required")
    assert raised(im.image_operation, with_wcs, 2.0, "normalize") == ("OPERATION_UNSUPPORTED", "no_operands")
    assert raised(im.image_operation, with_wcs, 2.0, "flip_x") == ("OPERATION_UNSUPPORTED", "no_operands")
    zero = load_image(write_fits(tmp_path / "z.fits", np.zeros((4, 4), dtype=np.float32)))
    assert raised(im.image_operation, zero, None, "normalize")[1] == "normalization_undefined"
    assert raised(im.Contours(levels=(1.0,), bunit=None, curves=((),)).to_sky, no_wcs) == ("WCS_MISSING", "contours_sky")
    assert raised(im.read_raw_pixel, with_wcs, 10000, 10000) == ("PIXEL_RAW_UNAVAILABLE", "position")
    assert raised(im.read_raw_pixel, im.cutout(with_wcs, im.PixelPosition(20.0, 20.0, "numpy"), 5), 1, 1) == (
        "PIXEL_RAW_UNAVAILABLE", "derived")
    assert raised(im.suggest_display_limits, np.full((5, 5), np.nan)) == ("DISPLAY_LIMITS_UNDEFINED", "no_finite_pixels")
    assert raised(im.suggest_display_limits, np.ones((5, 5)))[1] == "constant"
    assert raised(im.suggest_display_limits, np.ones((5, 5)), method="zzz")[0] == "DISPLAY_METHOD_UNKNOWN"
    assert raised(im.set_display, with_wcs, 0.0, 1.0, 1.0, "gray", "zzz")[0] == "DISPLAY_OPTION_UNKNOWN"
    assert raised(im.star_centroid, np.zeros((30, 30)), (15, 15), 5, 3.0, 4.0)[0] == "CENTROID_UNDEFINED"


def test_resampling_and_rgb_errors(images):
    with_wcs, no_wcs, _ = images
    assert raised(im.resample_to_reference, no_wcs, with_wcs, "nearest") == ("WCS_MISSING", "resampling")
    assert raised(im.resample_to_reference, with_wcs, no_wcs, "nearest") == ("WCS_MISSING", "reference")
    assert raised(im.resample_to_reference, with_wcs, with_wcs, "zzz") == ("OPERATION_UNSUPPORTED", "resampling_method_unknown")
    assert raised(im.rgb_composite, [with_wcs, with_wcs], mode="zzz") == ("RGB_INPUT_INVALID", "mode_unknown")
    assert raised(im.rgb_composite, [with_wcs])[1] == "image_count"
    assert raised(im.rgb_composite, [with_wcs, no_wcs]) == ("WCS_MISSING", "rgb")
    assert raised(im.rgb_composite, ["x", with_wcs]) == ("RGB_INPUT_INVALID", "monochrome_images_required")
    assert raised(im.rgb_composite, [with_wcs, with_wcs], wavelengths=[1, 2]) == ("RGB_INPUT_INVALID", "wavelengths")
    assert raised(im.rgb_composite, [with_wcs, with_wcs]) == ("RGB_INPUT_INVALID", "display_required")
    units = im.dataclasses.replace(with_wcs, bunit="Jy")
    assert raised(im.mosaic, [with_wcs, units], with_wcs, "nearest") == ("UNIT_MISMATCH", "mosaic")
    assert raised(im.rgb_composite, [with_wcs, units], mode="rgb_diff") == ("UNIT_MISMATCH", "rgb_diff")


def test_notes_with_params(images, monkeypatch):
    with_wcs, no_wcs, tmp_path = images

    class Calibration:
        header = None
        source = "survey"
        reason = "service said no"

    out = im._apply_external_calibration(no_wcs, Calibration())
    assert out.warnings[-1][0] == "WCS_MISSING" and out.warnings[-1].params["reason"] == "external_unavailable"
    Calibration.reason = None
    out = im._apply_external_calibration(no_wcs, Calibration())
    assert out.warnings[-1].params["reason"] == "external_no_header"
    Calibration.header = wcs_header()
    ignored = im._apply_external_calibration(with_wcs, Calibration())
    assert ignored.warnings[-1][0] == "EXTERNAL_CALIBRATION_IGNORED"
    bad = im._raster_calibration(fits.Header(), "hhh", 5, 5)[1][0]
    assert bad.params["reason"] == "calibration_invalid_header"
    w = WCS(naxis=3)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN", "FREQ"]
    assert im._image_wcs(w.to_header(), {1, 3})[1][0].params["reason"] == "celestial_axes"
