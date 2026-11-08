# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Miniatura HiPS fuori dalla vista (``mdfiles/12-core-hips.md`` §7, T20) e scorciatoia «CDS già giù» (D25-18).

Risposte vere di ESASky registrate il 2026-11-07 attorno a 51 Peg (``tests/analysis/data/profile/``, servite dal server
locale di ``tests/analysis/profile_fakes.py``; MocServer non raggiungibile come quel giorno).
"""

from __future__ import annotations

import io

import astropy.units as u
import numpy as np
import pytest
from astropy.time import Time
from PIL import Image

import astrotwo.core.vo_protocols as vo
from astrotwo.core import hips
from astrotwo.core.coordinates_wcs import SkyFrame, make_view_wcs
from tests.analysis.profile_fakes import services  # noqa: F401
from tests.message_helpers import check_message

PEG = SkyFrame.from_lonlat(344.36658535524 * u.deg, 20.768832511140005 * u.deg, "icrs", epoch=Time("J2000.0"))


def open_survey(hips_id, cache, **kw):
    return hips.add_hips(hips_id, cache=cache, **kw)


def mocserver_calls(monkeypatch) -> list:
    calls = []
    original = vo._http

    def counted(protocol, url, *args, **kw):
        if url == vo.MOCSERVER_URL:
            calls.append(url)
        return original(protocol, url, *args, **kw)

    monkeypatch.setattr(vo, "_http", counted)
    return calls


# =============================================================================
# T20 — miniatura


@pytest.mark.parametrize("hips_id, order, epoch", [("CDS/P/DSS2/color", 9, None), ("CDS/P/2MASS/color", 9, None),
                                                    ("CDS/P/allWISE/color", 8, 55396.0)])
def test_t20_thumbnail_from_the_recorded_tiles(services, cache, hips_id, order, epoch):
    service = open_survey(hips_id, cache)
    thumb = hips.hips_thumbnail(service, PEG, cache=cache)
    assert thumb.image.shape == (256, 256, 3) and thumb.image.dtype == np.uint8
    assert thumb.mask.all() and thumb.order == order and thumb.fov == 5 * u.arcmin
    assert thumb.servers == (service.server,) and "/hips/skies.esac.esa.int/" in thumb.servers[0]
    assert thumb.credits["obs_title"] == service.properties["obs_title"][0]
    assert (thumb.epoch is None) if epoch is None else thumb.epoch["mjd"] == epoch
    # WCS della griglia = geometria della vista del 10
    view = make_view_wcs(PEG, (5 * u.arcmin) / 256, (256, 256), projection="TAN", frame="icrs")
    x, y = np.array([0.0, 255.0, 127.5, 31.0]), np.array([0.0, 255.0, 127.5, 200.0])
    expected = view.window_to_sky(x, y)
    got = thumb.wcs.pixel_to_world(x, y)
    assert np.allclose(got.separation(expected).to_value(u.arcsec), 0.0, atol=1e-9)
    # ogni pixel composto da fill_view: uguale al pixel del tile scelto da view_sampling
    sampling = hips.view_sampling(service, view)
    tile = hips.fetch_tile(service, sampling.order, sampling.tiles[0], cache=cache)
    part = hips.fill_view(sampling, tile)
    y0, y1, x0, x1 = part.box
    assert np.array_equal(thumb.image[y0:y1, x0:x1][part.mask], part.values[part.mask])
    # orientamento: riga 0 = sud (FITS); PNG con il nord in alto
    assert thumb.wcs.pixel_to_world(127.5, 255.0).dec > thumb.wcs.pixel_to_world(127.5, 0.0).dec
    png = np.asarray(Image.open(io.BytesIO(thumb.png())).convert("RGB"))
    assert np.array_equal(png, thumb.image[::-1])
    data = thumb.as_dict()
    assert data["pixels_with_data"] == 256 * 256 and data["servers"] == list(thumb.servers)


def test_t20_missing_tile_and_all_servers_down(services, cache, monkeypatch):
    service = open_survey("CDS/P/DSS2/color", cache)
    view = make_view_wcs(PEG, (5 * u.arcmin) / 256, (256, 256), projection="TAN", frame="icrs")
    first = hips.view_sampling(service, view).tiles[0]
    services.overrides[("hips", f"Npix{first}.jpg")] = lambda path: (404, "text/plain", "assente")
    thumb = hips.hips_thumbnail(service, PEG, cache=cache, refresh=True)
    assert [m["index"] for m in thumb.missing] == [first] and not thumb.mask.all() and thumb.mask.any()
    services.overrides.clear()
    table = {"CDS/P/2MASS/color": (f"{services.fake.url}/hips/down-a/2MASSColor",
                                   f"{services.fake.url}/hips/down-b/2MASSColor")}
    monkeypatch.setattr(hips, "MIRROR_FALLBACKS", table)
    services.overrides[("hips", "down-")] = lambda path: (503, "text/plain", "giù")
    with pytest.raises(hips.HiPSError) as info:
        open_survey("CDS/P/2MASS/color", cache)
    assert info.value.code == "NET_TIMEOUT" and info.value.params["reason"] == "hips_servers"
    for bad in ({"fov": 0 * u.arcmin}, {"fov": 5.0}, {"size": 8}, {"size": True}):
        with pytest.raises(ValueError):
            hips.hips_thumbnail(service, PEG, cache=cache, **bad)


# =============================================================================
# D25-18 — CDS già giù nella sessione: subito i mirror verificati, avviso dichiarato


def test_d25_18_mocserver_down_once_then_straight_to_the_mirrors(services, cache, monkeypatch):
    calls = mocserver_calls(monkeypatch)
    assert hips.cds_down_in_session() is None
    first = open_survey("CDS/P/DSS2/color", cache, cds_down_shortcut=True)
    assert len(calls) == 1  # prima volta: il MocServer si prova (e non risponde)
    assert hips.cds_down_in_session()["evidence"] == "mocserver"
    assert {w.params["reason"] for w in first.warnings if w[0] == "HIPS_MIRROR_FALLBACK"} == {"mocserver"}
    second = open_survey("CDS/P/2MASS/color", cache, cds_down_shortcut=True)
    assert len(calls) == 1  # seconda volta: nessuna attesa del MocServer
    note = next(w for w in second.warnings if w[0] == "HIPS_MIRROR_FALLBACK")
    assert note.params == {"reason": "cds_down", "hips_id": "CDS/P/2MASS/color", "mirror": second.server,
                           "evidence": "mocserver"}
    check_message(note[0], note.params, note[1])
    open_survey("CDS/P/allWISE/color", cache, cds_down_shortcut=True, refresh=True)  # refresh: si riprova
    open_survey("CDS/P/allWISE/color", cache)  # senza l'opzione (es. il cielo del 41): comportamento di prima
    assert len(calls) == 3


_SIMBAD_MIRRORS = vo.SERVICE_MIRRORS["cds-simbad-tap"]  # letta all'import, prima che il fixture svuoti l'elenco


def test_d25_18_simbad_on_its_mirror_is_also_evidence(services, cache, monkeypatch):
    calls = mocserver_calls(monkeypatch)
    # SIMBAD passato davvero a Harvard con il ripiego del 14 (sprint C7: prima il test impostava a mano la chiave
    # sbagliata ``cds-simbad-tap`` e nascondeva il difetto di ``cds_down_in_session``, 25 §3.16 C7-e).
    import requests

    monkeypatch.setattr(vo, "_MIRROR_IN_USE", {})
    monkeypatch.setattr(vo, "_MIRROR_ANNOUNCED", set())
    monkeypatch.setitem(vo.SERVICE_MIRRORS, "cds-simbad-tap", _SIMBAD_MIRRORS)  # voce vera (il fixture la toglie)
    entry = _SIMBAD_MIRRORS
    servers = ("https://simbad.cds.unistra.fr/simbad/sim-tap",) + tuple(entry.mirrors)
    assert hips.cds_down_in_session() is None

    def attempt(server, refresh, stale):
        if server == servers[0]:
            raise requests.exceptions.ConnectTimeout("CDS giù")
        return "risposta"

    assert vo._with_mirrors(entry, servers, attempt, None, refresh=False)[0] == "risposta"
    assert hips.cds_down_in_session() == {"evidence": "simbad_failover"}
    service = open_survey("CDS/P/DSS2/color", cache, cds_down_shortcut=True)
    assert calls == [] and next(w for w in service.warnings if w[0] == "HIPS_MIRROR_FALLBACK").params["evidence"] \
        == "simbad_failover"


def test_d25_18_profile_thumbnails_skip_the_mocserver_after_the_first_profile(services, cache, monkeypatch):
    from astrotwo.analysis.object_profile import ProfileTarget, build_profile

    calls = mocserver_calls(monkeypatch)
    build_profile(ProfileTarget(name="51 Peg"), sections=("images",), cache=cache)
    seen = len(calls)
    assert seen >= 1
    prof = build_profile(ProfileTarget(name="51 Peg"), sections=("images",), cache=cache)
    assert len(calls) == seen
    images = prof.sections[0]
    assert images.status == "done"
    assert {w.params["reason"] for w in images.warnings if w[0] == "HIPS_MIRROR_FALLBACK"} == {"cds_down"}
