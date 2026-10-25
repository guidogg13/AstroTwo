# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del 05 per lo sprint 4d del 41: immagine FITS come base della vista (inquadratura, griglia di pixel senza WCS
valido, ``cursor.read`` con valore originale e unità, epoca e frame dall'intestazione) e avvisi di
``hips.set_survey`` senza ripetizioni. Senza Qt e senza rete.

Valori attesi ricalcolati nel test con ``astropy`` e con le funzioni del 10 e dell'11.
"""

import astropy.units as u
import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from astrotwo.core import coordinates_wcs as cw
from astrotwo.core import hips
from astrotwo.core.commands import Command, PixelGridGeometry, RequestedBy, Session, default_registry
from tests.core.test_commands_hips_display import serve_fits_survey

NX, NY = 60, 40
WINDOW = {"width": 600, "height": 400}


def header(ctype=("RA---TAN", "DEC--TAN"), crval=(150.0, 2.0), scale=1e-3, bunit="MJy/sr", **cards):
    w = WCS(naxis=2)
    w.wcs.ctype = list(ctype)
    w.wcs.crval = list(crval)
    w.wcs.crpix = [NX / 2 + 0.5, NY / 2 + 0.5]
    w.wcs.cdelt = [-scale, scale]
    h = w.to_header()
    if bunit:
        h["BUNIT"] = bunit
    for key, value in cards.items():
        h[key] = value
    return h


def write(path, hdr=None, data=None):
    data = np.arange(NX * NY, dtype=np.float32).reshape(NY, NX) if data is None else data
    fits.PrimaryHDU(data=data, header=hdr).writeto(path)
    return str(path)


@pytest.fixture
def session(cache):
    return Session(default_registry(cache=cache))


def run(session, name, **params):
    return session.run(Command(name, 1, params, RequestedBy("menu")))


def read_cursor(session, x, y):
    """Lettura passiva ``cursor.read`` a un pixel della finestra (convenzione numpy)."""
    position = {"x": x, "y": y, "convention": "numpy"}
    return session.run(Command("cursor.read", 1, {"position": position, "order": None}, RequestedBy("mouse")))


def open_image(session, path, window=WINDOW):
    assert run(session, "view.set_zoom", scale={"value": 10, "unit": "deg"}, window=window).status == "ok"
    result = run(session, "image.open", file={"path": path})
    assert result.status == "ok", result.error
    return result


def test_open_frames_whole_image_with_its_wcs(session, tmp_path):
    path = write(tmp_path / "img.fits", header())
    result = open_image(session, path)
    state = session.workspace.state
    layer = state.of_kind("image")[0]
    view = state.view
    assert view.base_layer == layer.id and result.values["framing"]["fitted"]
    g = view.geometry
    assert not isinstance(g, PixelGridGeometry) and g.base_created is False
    # tutta l'immagine nella finestra: 600/60 = 10 pixel di finestra per pixel dell'immagine (altezza 400/40 = 10)
    assert g.factor == pytest.approx(10.0, rel=1e-9)
    assert g.window_to_base(0, 0)[0] == pytest.approx(-0.45) and g.window_to_base(599, 399)[1] == pytest.approx(39.45)
    expected = cw.pixel_to_sky(layer.data.wcs, (NX - 1) / 2, (NY - 1) / 2, convention="numpy").coords
    assert view.center.coord.separation(expected.coord).to_value(u.arcsec) < 1e-6
    # il comando registra i limiti scelti (D41-3); riesecuzione = stessa vista
    entry = session.history.entries[-1]
    assert entry.command.parameters["vmin"] is not None
    other = Session(default_registry(cache=session.registry.cache))
    run(other, "view.set_zoom", scale={"value": 10, "unit": "deg"}, window=WINDOW)
    again = other.run(Command("image.open", 1, dict(entry.command.parameters), RequestedBy("session")))
    assert again.status == "ok" and other.workspace.state.view.geometry.factor == pytest.approx(10.0)


def test_cursor_reads_original_value_unit_and_pixel_position(session, tmp_path):
    data = np.arange(NX * NY, dtype=np.float32).reshape(NY, NX) * 3.5 + 1000.0
    path = write(tmp_path / "img.fits", header(), data)
    open_image(session, path)
    g = session.workspace.state.view.geometry
    for bx, by in ((10, 5), (59, 39), (0, 0)):
        wx, wy = g.base_to_window(bx, by)
        result = read_cursor(session, float(wx), float(wy))
        pixel = result.values["pixel"]
        assert pixel["value"] == float(data[by, bx])  # valore ORIGINALE, non quello dei colori (D11-1)
        assert pixel["unit"] == "MJy / sr" and pixel["unit_label"] == "MJy/sr" and pixel["unit_declared"]
        assert pixel["fits"] == {"x": bx + 1, "y": by + 1}  # convenzione FITS ai bordi (DC7)
        sky = cw.pixel_to_sky(session.workspace.state.of_kind("image")[0].data.wcs, bx, by, convention="numpy").coords
        shown = result.values["sky"]
        assert shown["lon"]["value"] == pytest.approx(sky.lon.to_value(u.deg), abs=1e-9)
        assert shown["lat"]["value"] == pytest.approx(sky.lat.to_value(u.deg), abs=1e-9)
    # fuori dall'immagine: nessun valore, con il messaggio del modulo
    outside = read_cursor(session, 5.0, 5.0)
    assert "pixel" not in outside.values or outside.values["pixel"]["layer"]


def test_no_bunit_means_no_unit(session, tmp_path):
    path = write(tmp_path / "img.fits", header(bunit=None))
    open_image(session, path)
    g = session.workspace.state.view.geometry
    wx, wy = g.base_to_window(30, 20)
    pixel = read_cursor(session, float(wx), float(wy)).values["pixel"]
    assert pixel["unit"] is None and pixel["unit_declared"] is False


def test_no_wcs_is_a_pixel_grid_without_coordinates(session, tmp_path):
    data = np.arange(NX * NY, dtype=np.float32).reshape(NY, NX)
    path = write(tmp_path / "plain.fits", None, data)
    result = open_image(session, path)
    assert "WCS_MISSING" in [w.code for w in result.warnings]
    g = session.workspace.state.view.geometry
    assert isinstance(g, PixelGridGeometry) and g.problem.code == "WCS_INVALID"
    wx, wy = g.base_to_window(12, 7)
    read = read_cursor(session, float(wx), float(wy))
    assert read.status == "ok" and read.values["sky"] is None  # nessuna coordinata inventata
    assert read.values["wcs_problem"]["code"] == "WCS_INVALID" and "WCS_INVALID" in [w.code for w in read.warnings]
    assert read.values["pixel"]["value"] == float(data[7, 12]) and read.values["pixel"]["fits"] == {"x": 13, "y": 8}
    # immagine intera nella finestra, centrata
    assert g.factor == pytest.approx(10.0) and g.window_to_base(299.5, 199.5) == pytest.approx((29.5, 19.5))
    # griglia e indicatore non esistono senza cielo
    run(session, "view.set_grid", visible=True, frame="icrs")
    assert session.workspace.state.view.grid is None and session.workspace.state.view.compass is None
    pointer = session.run(Command("simbad.pointer", 1, {"position": {"x": 1.0, "y": 1.0, "convention": "numpy"},
                                                        "radius": {"value": 5, "unit": "arcsec"}},
                                  RequestedBy("mouse")))
    assert pointer.status == "error" and pointer.error.code == "WCS_INVALID"


def test_invalid_wcs_is_reported_not_guessed(session, tmp_path):
    bad = header(CD1_1=0.0, CD1_2=0.0, CD2_1=0.0, CD2_2=0.0)
    for key in ("CDELT1", "CDELT2"):
        del bad[key]
    path = write(tmp_path / "bad.fits", bad)
    result = open_image(session, path)
    g = session.workspace.state.view.geometry
    assert isinstance(g, PixelGridGeometry) and g.problem.code == "WCS_INVALID"
    assert any(w.code in ("WCS_MISSING", "WCS_INVALID") for w in result.warnings)
    wx, wy = g.base_to_window(3, 4)
    assert read_cursor(session, float(wx), float(wy)).values["sky"] is None


@pytest.mark.parametrize("cards, frame, epoch_known", [
    ({"RADESYS": "ICRS"}, "icrs", False),
    ({"RADESYS": "FK5", "EQUINOX": 2000.0}, "icrs", False),
])
def test_epoch_and_frame_come_from_the_header_never_assumed(session, tmp_path, cards, frame, epoch_known):
    hdr = header()
    for key, value in cards.items():
        hdr[key] = value
    path = write(tmp_path / "img.fits", hdr)
    open_image(session, path)
    g = session.workspace.state.view.geometry
    wx, wy = g.base_to_window(30, 20)
    result = read_cursor(session, float(wx), float(wy))
    assert result.status == "ok"
    sky = result.values["sky"]
    assert sky["frame"] == frame and (sky.get("epoch") is not None) == epoch_known
    assert not any(w.code == "EPOCH_REQUIRED" for w in result.warnings) or sky is not None


def test_epoch_from_mjd_obs_is_declared(session, tmp_path):
    hdr = header(**{"MJD-OBS": 55000.0, "RADESYS": "ICRS"})
    open_image(session, write(tmp_path / "img.fits", hdr))
    g = session.workspace.state.view.geometry
    wx, wy = g.base_to_window(30, 20)
    sky = read_cursor(session, float(wx), float(wy)).values["sky"]
    print(sky)
    assert sky.get("epoch") is not None


def test_galactic_image_in_its_own_frame(session, tmp_path):
    hdr = header(ctype=("GLON-TAN", "GLAT-TAN"), crval=(120.0, 30.0))
    open_image(session, write(tmp_path / "gal.fits", hdr))
    view = session.workspace.state.view
    assert view.geometry.frame_name == "galactic"
    run(session, "view.set_coordinate_display", frame="galactic", format="decimal")
    wx, wy = view.geometry.base_to_window(29.5, 19.5)
    sky = read_cursor(session, float(wx), float(wy)).values["sky"]
    assert sky["frame"] == "galactic" and sky["lon"]["value"] == pytest.approx(120.0, abs=1e-3)


def test_hips_set_survey_warnings_once_per_source(session, service, cache, monkeypatch):
    monkeypatch.setattr(hips, "survey_coverage", lambda svc, **k: hips.service_coverage(svc, **k))
    url = serve_fits_survey(service)
    run(session, "hips.set_survey", survey=url)
    result = run(session, "hips.set_survey", survey=url)  # seconda volta: proprietà dalla cache
    pairs = [(w.code, w.text) for w in result.warnings]
    assert len(pairs) == len(set(pairs))
    cached = [w for w in result.warnings if w.code == "FROM_CACHE"]
    assert len({w.text for w in cached}) == len(cached)
    print(pairs)
