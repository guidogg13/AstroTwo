# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del 05 per lo sprint 4b del 41: limiti di colore dei survey FITS in ``hips.set_survey`` (T19) e
``cursor.read`` con sistema scelto e ordine (T8). Senza Qt e senza rete: survey simulato con tile FITS sintetici.

Valori attesi ricalcolati nel test con ``astropy`` (ZScale, HEALPix) e con le funzioni dei moduli 10 e 12.
"""

import io

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.visualization import ZScaleInterval
from astropy_healpix import HEALPix, nside_to_pixel_resolution

from astrotwo.core import coordinates_wcs as cw
from astrotwo.core import hips
from astrotwo.core.commands import Command, RequestedBy, Session, default_registry
from astrotwo.core.moc import CircleRegion, moc_from_region
from tests.core.test_hips import WIDTH, properties_text, serve_properties

ORDER = 3


def tile_data(index: int) -> np.ndarray:
    """Tile sintetico: rumore gaussiano attorno a un livello che dipende poco dal tile (riconoscibile, ma tutti i
    tile restano dentro l'intervallo ZScale)."""
    return np.random.default_rng(index).normal(loc=100.0 + index % 5, scale=5.0, size=(WIDTH, WIDTH)).astype(np.float32)


def tile_bytes(index: int) -> bytes:
    buffer = io.BytesIO()
    fits.PrimaryHDU(tile_data(index), header=fits.Header({"BUNIT": "mJy"})).writeto(buffer)
    return buffer.getvalue()


def serve_fits_survey(service, *, path="/fits", missing=(), **props):
    url = serve_properties(service, path, properties_text(hips_tile_format="fits", hips_order=str(ORDER),
                                                          hips_tile_width=str(WIDTH), **props))
    for order in range(ORDER + 1):
        for index in range(12 * 4 ** order):
            if (order, index) in missing:
                continue
            service.routes[f"{path}/{hips.tile_path(order, index, 'fits')}"] = (
                lambda request, i=index: (200, "application/fits", tile_bytes(i)))
    return url


def origin_tile(order=ORDER) -> int:
    """Tile che contiene ICRS (0°, 0°) all'ordine dato (HEALPix nested, ricalcolo con astropy-healpix)."""
    return int(HEALPix(nside=2 ** order, order="nested").lonlat_to_healpix(0 * u.deg, 0 * u.deg))


@pytest.fixture
def session(cache, monkeypatch):
    # copertura dal solo servizio simulato (Moc.fits assente → copertura non nota), mai dal MocServer reale
    monkeypatch.setattr(hips, "survey_coverage", lambda svc, **k: hips.service_coverage(svc, **k))
    return Session(default_registry(cache=cache))


def run(session, name, **params):
    return session.run(Command(name, 1, params, RequestedBy("menu")))


def tile_requests(service):
    return [r for r in service.requests if "Npix" in r["path"]]


def test_t19_zscale_on_origin_tile_registered_in_command(session, service):
    url = serve_fits_survey(service)
    result = run(session, "hips.set_survey", survey=url)
    assert result.status == "ok", result.error
    expected = ZScaleInterval().get_limits(tile_data(origin_tile()).astype(np.float64).ravel())
    entry = session.history.entries[0]
    assert entry.command.parameters["vmin"] == pytest.approx(expected[0]) and \
        entry.command.parameters["vmax"] == pytest.approx(expected[1])  # registrati nel comando (D41-3)
    display = result.values["display"]
    assert (display["vmin"], display["vmax"]) == (entry.command.parameters["vmin"], entry.command.parameters["vmax"])
    assert display["palette"] == "gray" and display["stretch"] == "linear" and display["gamma"] == 1.0
    assert f"tile {origin_tile()}" in display["limits_source"] and "zscale" in display["limits_source"]
    layer = session.workspace.state.of_kind("hips")[0]
    assert layer.display["vmin"] == display["vmin"]
    # riesecuzione dal comando registrato: stessi limiti, nessun tile richiesto
    service.requests.clear()
    other = Session(default_registry(cache=session.registry.cache))
    again = other.run(Command("hips.set_survey", 1, dict(entry.command.parameters), RequestedBy("session")))
    assert again.status == "ok" and again.values["display"]["vmin"] == display["vmin"]
    assert tile_requests(service) == []


def test_hips_pixel_cut_and_explicit_limits(session, service):
    url = serve_fits_survey(service, hips_pixel_cut="10 200")
    result = run(session, "hips.set_survey", survey=url)
    assert (result.values["display"]["vmin"], result.values["display"]["vmax"]) == (10.0, 200.0)
    assert "hips_pixel_cut" in result.values["display"]["limits_source"] and tile_requests(service) == []
    assert session.history.entries[0].command.parameters["vmin"] == 10.0
    result = run(session, "hips.set_survey", survey=url, vmin=1.5, vmax=2.5)  # dati dall'utente: si usano
    assert (result.values["display"]["vmin"], result.values["display"]["vmax"]) == (1.5, 2.5)
    assert "parametri" in result.values["display"]["limits_source"]


def test_color_survey_has_no_limits(session, service):
    url = serve_properties(service, "/png", properties_text(hips_tile_format="png", hips_order="3",
                                                            hips_tile_width=str(WIDTH)))
    result = run(session, "hips.set_survey", survey=url)
    assert result.status == "ok" and result.values["display"] is None
    assert session.history.entries[0].command.parameters["vmin"] is None
    assert session.workspace.state.of_kind("hips")[0].display is None


def test_fallback_first_covered_tile_and_undefined(session, service, monkeypatch):
    missing = {(ORDER, origin_tile())}
    url = serve_fits_survey(service, missing=missing)
    result = run(session, "hips.set_survey", survey=url)  # tile mancante e copertura non nota
    assert result.status == "error" and result.error.code == "HIPS_DISPLAY_LIMITS_UNDEFINED"
    coverage = moc_from_region(CircleRegion(SkyCoord(40 * u.deg, 30 * u.deg), 8 * u.deg), 6)
    monkeypatch.setattr(hips, "survey_coverage", lambda svc, **k: (coverage, ()))
    result = run(session, "hips.set_survey", survey=url)
    assert result.status == "ok", result.error
    cells = np.asarray(coverage.moc.degrade_to_order(ORDER).flatten(), dtype=np.int64)
    first = int(cells.min())
    expected = ZScaleInterval().get_limits(tile_data(first).astype(np.float64).ravel())
    assert result.values["display"]["vmin"] == pytest.approx(expected[0])
    assert "primo tile coperto" in result.values["display"]["limits_source"]
    assert any(w.code == "HIPS_DISPLAY_FALLBACK" for w in result.warnings)


def test_t8_cursor_read_frame_and_order(session, service):
    url = serve_fits_survey(service)
    assert run(session, "hips.set_survey", survey=url).status == "ok"
    window = {"width": 800, "height": 400}
    assert run(session, "view.set_zoom", scale={"value": 360.0 / 800, "unit": "deg"}, window=window).status == "ok"
    center = {"lon": {"value": 56.75, "unit": "deg"}, "lat": {"value": 24.12, "unit": "deg"}, "frame": "icrs",
              "equinox": None, "obstime": None, "epoch": None, "epoch_reason": "prova senza epoca"}
    assert run(session, "view.set_center", position=center, window=window).status == "ok"
    position = {"x": 400.0, "y": 200.0, "convention": "numpy"}
    history = len(session.history)
    base = session.workspace.state.view.geometry
    bx, by = (float(v) for v in base.window_to_base(position["x"], position["y"]))
    sky = cw.pixel_to_sky(base.base, bx, by, convention="numpy").coords
    service_obj = session.workspace.state.of_kind("hips")[0].data
    for order in (2, None):
        result = run(session, "cursor.read", position=position, order=order)
        assert result.status == "ok", result.error
        used = ORDER if order is None else order
        expected = hips.pixel_values(service_obj, sky, order=used, cache=session.registry.cache)
        assert result.values["pixel"]["value"] == float(expected.values[0])
        assert result.values["pixel"]["order"] == used and result.values["pixel"]["unit"] == "mJy"
        # risoluzione del pixel letto (ordine + log2(64) = 6 livelli sotto il tile), ricalcolo con astropy-healpix
        res = nside_to_pixel_resolution(2 ** (used + 6)).to_value(u.arcsec)
        assert result.values["pixel"]["resolution"] == {"value": pytest.approx(res), "unit": "arcsec"}
        assert result.values["pixel"]["survey_order"] == ORDER
    assert len(session.history) == history  # lettura passiva: mai in cronologia (D05-1)
    # cielo nel frame di base (ICRS, epoca non nota dichiarata)
    shown = result.values["sky"]
    assert shown["frame"] == "icrs" and shown["epoch"] is None and shown["epoch_reason"]
    assert shown["lon"]["value"] == pytest.approx(sky.lon.to_value(u.deg)) and \
        shown["lat"]["value"] == pytest.approx(sky.lat.to_value(u.deg))
    # sistema scelto per le coordinate mostrate: galattico
    assert run(session, "view.set_coordinate_display", frame="galactic", format="decimal").status == "ok"
    galactic = run(session, "cursor.read", position=position, order=2)
    converted = sky.coord.transform_to("galactic")
    assert galactic.values["sky"]["frame"] == "galactic"
    assert galactic.values["sky"]["lon"]["value"] == pytest.approx(converted.l.deg)
    assert galactic.values["sky"]["lat"]["value"] == pytest.approx(converted.b.deg)
    at2 = hips.pixel_values(service_obj, sky, order=2, cache=session.registry.cache)
    assert galactic.values["pixel"]["value"] == float(at2.values[0])  # il valore non dipende dal sistema
    assert len(session.history) == history + 1  # solo il comando di visualizzazione
