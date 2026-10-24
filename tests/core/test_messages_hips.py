# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 12 con codice + ``params`` (D40-3; ``40`` §3.7.1, T18–T19; ``12`` §10).

Provoca ogni errore e ogni avviso del modulo; ogni istanza è controllata contro il catalogo alla creazione
(``tests/conftest.py``) e qui si verifica la copertura di tutte le coppie (codice, ragione) del modulo, la regola degli
errori rilanciati dal 14 e dal 16 e il testo italiano invariato.
"""

from __future__ import annotations

import dataclasses
import json

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy_healpix import HEALPix

from astrotwo import messages_catalog as mc
from astrotwo.core import coordinates_wcs as cw
from astrotwo.core import hips as hips_module
from astrotwo.core import vo_protocols as vo
from astrotwo.core.cache import NetworkTimeouts, SharedCache
from astrotwo.core.coordinates_wcs import ModuleWarning, SkyFrame, make_view_wcs
from astrotwo.core.hips import (
    CollectionIndex,
    HiPSError,
    HiPSList,
    add_hips,
    build_hips,
    catalog_tiles,
    cube_planes,
    fetch_tile,
    fill_view,
    order_for_resolution,
    parse_properties,
    pixel_values,
    read_service,
    service_coverage,
    set_survey,
    survey_coverage,
    tile_path,
    tile_pixel_values,
    tiles_for_fov,
    view_sampling,
)
from astrotwo.core.images_fits import LargeImageLimits
from astrotwo.core.moc import CircleRegion, MocError, moc_from_region, write_moc
from tests.core.test_hips import (
    METADATA_XML,
    fits_tile,
    image_tile,
    mocserver,  # noqa: F401  (fixture)
    mocserver_records,
    properties_text,
    route_all_tiles,
    route_tile,
    serve_properties,
    tan_image,
    tile_service,
    tsv,
)
from tests.message_helpers import MODULE_14_SUBVARIANTS, catalog_combinations, check_error, check_message, nested_pairs

#: Codici che solo il modulo 12 solleva o restituisce (le sotto-voci aggiunte a voci condivise sono in ``SHARED``).
OWN_CODES = (
    "HIPS_NOT_A_SERVICE", "HIPS_METADATA_INVALID", "HIPS_UNKNOWN", "HEALPIX_ORDER_INVALID", "HEALPIX_INDEX_INVALID",
    "HIPS_FRAME_UNSUPPORTED", "REGION_INVALID", "HIPS_OUT_OF_COVERAGE", "HIPS_TYPE_MISMATCH", "SERVICE_ERROR",
    "HIPS_FORMAT_UNAVAILABLE", "HIPS_TILE_MISSING", "HIPS_BAD_TILE", "HIPS_CUBE_PLANE_INVALID",
    "HIPS_PIXEL_UNAVAILABLE", "HIPS_OUT_OF_TILE", "MOCSERVER_UNAVAILABLE", "HIPS_DISPLAY_REQUIRED",
    "HIPS_DISPLAY_INVALID", "HIPS_EMPTY", "BODY_UNKNOWN", "HIPS_BODY_DRAFT", "BODY_UNSUPPORTED", "BODY_NORMALIZED",
    "HIPS_DEFAULT_TILE_WIDTH", "HIPS_VERSION_UNKNOWN", "HIPS_ID_MISMATCH", "HIPS_ALREADY_LISTED",
    "HIPS_COVERAGE_NOT_CHECKED", "HIPS_RESOLUTION_LIMIT", "HIPS_TILE_DISCARDED", "HIPS_COVERAGE_UNKNOWN",
    "HIPS_COVERAGE_FROM_MOCSERVER", "HIPS_DEFAULT_SURVEY", "HIPS_CUBE_UNIT_UNKNOWN", "HIPS_CUBE_AXIS_INCOMPLETE",
    "HIPS_UNIT_MIXED", "HIPS_ALLSKY_NOT_WRITTEN", "HIPS_TILE_PROBLEM",
)
SHARED = {("NET_TIMEOUT", "url"), ("WCS_MISSING", "image_without_wcs"), ("OPERATION_UNSUPPORTED", "build_method"),
          ("OPERATION_UNSUPPORTED", "build_color_image"), ("PREVIEW_NOT_MEASURABLE", "build_hips"),
          ("MEMORY_LIMIT_EXCEEDED", "build_hips"), ("FROM_CACHE", "cached_tile")}


def required_combinations() -> set[tuple[str, str | None]]:
    """Coppie (codice, ragione) del 12: ogni sotto-voce; la voce generale solo dove non ha sotto-voci o è usata."""
    module_13 = {("BODY_UNKNOWN", "table_body"), ("REGION_INVALID", "radius_not_angle"),
                 ("REGION_INVALID", "radius_range")}  # sotto-voci del 13 nelle voci condivise
    out = {(c, r) for c, r in catalog_combinations(OWN_CODES)
           if r is not None or not mc.CATALOG[c].variants} - module_13 - MODULE_14_SUBVARIANTS
    return out | {("HEALPIX_ORDER_INVALID", None)} | SHARED


class Seen:
    def __init__(self) -> None:
        self.pairs: set[tuple[str, str | None]] = set()

    def error(self, func, *args, **kwargs) -> HiPSError:
        with pytest.raises(HiPSError) as info:
            func(*args, **kwargs)
        self.pairs.add(check_error(info.value))
        self.pairs |= nested_pairs(info.value.code, info.value.params)
        return info.value

    def notes(self, items) -> None:
        for item in items:
            if isinstance(item, ModuleWarning):
                self.pairs.add(check_message(item[0], item.params, item[1]))
                self.pairs |= nested_pairs(item[0], item.params)


def test_every_error_and_warning_has_code_params_and_catalog_entry(service, cache, mocserver, tmp_path, monkeypatch):  # noqa: F811
    seen = Seen()
    fast = NetworkTimeouts(connect=0.5, read=0.5)

    # --- P1: file properties e metadati -------------------------------------------------------------------------
    seen.error(parse_properties, "senza uguale")
    seen.error(parse_properties, "# solo un commento\n")
    seen.error(read_service, service.url + "/assente", cache=cache)  # 404 → service_error
    service.routes["/bin/properties"] = lambda request: (200, "application/octet-stream", b"\xff\xfe\x00")
    seen.error(read_service, service.url + "/bin", cache=cache)
    service.routes["/altro/properties"] = lambda request: (200, "text/plain", "colore = rosso\n")
    seen.error(read_service, service.url + "/altro", cache=cache)
    for i, change in enumerate([
        {"obs_title": None}, {"hips_order": "tre"}, {"hips_order": "30"}, {"hips_tile_width": "0"},
        {"em_min": "rosso"}, {"hips_release_date": "1 ottobre 2026"}, {"dataproduct_type": "spectral-cube"},
        {"hips_tile_format": "gif"}, {"hips_tile_width": "100"}, {"dataproduct_type": "cube"},
    ]):
        url = serve_properties(service, f"/m{i}", properties_text(**change))
        err = seen.error(read_service, url, cache=cache)
        assert err.code == "HIPS_METADATA_INVALID" and err.params["reason"] and "nessuna voce aggiunta" in err.message
    cube_first = read_service(serve_properties(service, "/cf", properties_text(
        dataproduct_type="cube", hips_cube_depth="3", hips_cube_firstframe="7")), cache=cache)
    seen.error(cube_planes, cube_first)

    # Avvisi di lettura: larghezza di default, versione, corpo (tutti i casi del 12 §3).
    versions = read_service(serve_properties(service, "/v", properties_text(hips_tile_width=None, hips_version="1.5")),
                            cache=cache)
    seen.notes(versions.warnings)
    for name, frame, body in (("a", "mars", "mars"), ("b", "moon", "moon"), ("c", "mars-stimson", "mars-stimson"),
                              ("d", "mars", None), ("e", "mars", "moon")):
        seen.notes(read_service(serve_properties(service, f"/b{name}", properties_text(
            hips_frame=frame, hips_body=body)), cache=cache).warnings)

    # --- MocServer e identificativi -------------------------------------------------------------------------------
    serve_properties(service, "/hips")
    listed = HiPSList()
    first = listed.add_hips("TEST/P/IR/K", cache=cache)
    seen.notes(first.warnings)  # HIPS_ID_MISMATCH: il creator_did del servizio è un altro
    seen.notes(listed.add_hips(service.url + "/hips", cache=cache).warnings)  # HIPS_ALREADY_LISTED
    seen.error(add_hips, "TEST/P/nessuno", cache=cache)  # mocserver
    seen.error(listed.get, "TEST/P/nessuno")  # not_listed
    seen.error(HiPSList().get, "TEST/P/nessuno")  # not_listed_empty
    service.routes["/MocServer/query"] = lambda request: (
        200, "application/json", json.dumps([{"ID": "X/P/nourl", "obs_title": "t"}]))
    seen.error(add_hips, "X/P/nourl", cache=cache)
    service.routes["/MocServer/query"] = lambda request: (200, "application/json", "non è json")
    seen.error(add_hips, "X/P/illeggibile", cache=cache)

    # --- P2: tile ---------------------------------------------------------------------------------------------------
    hips = tile_service(service, cache, order=3)
    center = SkyCoord(45 * u.deg, 20 * u.deg)
    seen.error(tiles_for_fov, center, 1 * u.deg, 30)  # ordine HEALPix generale
    seen.error(fetch_tile, hips, 4, 0, cache=cache)  # service_maximum
    seen.error(hips_module._tile_pixels, np.array([0.0]), np.array([0.0]), 28, 64)  # plus_tile_bits
    seen.error(fetch_tile, hips, 3, 768, cache=cache)
    seen.error(tiles_for_fov, center, 1 * u.deg, 3, frame="ecliptic")
    seen.error(tiles_for_fov, center, 1 * u.deg, 3, frame="mars")
    seen.error(tiles_for_fov, center, 5, 3)  # raggio senza unità
    seen.error(tiles_for_fov, SkyCoord([1, 2] * u.deg, [1, 2] * u.deg), 1 * u.deg, 3)
    # Conversione di frame non riuscita (il 10 solleva): REGION_INVALID con il suo messaggio come testo esterno.
    galactic_service = tile_service(service, cache, order=3, frame="galactic", path="/gal")
    view = make_view_wcs(SkyFrame.from_lonlat(45 * u.deg, 20 * u.deg, "icrs"), 20 * u.arcsec, (40, 80),
                         projection="TAN")
    route_tile(service, "/hips", 3, 5, fits_tile(1))
    some_tile = fetch_tile(hips, 3, 5, cache=cache)

    def failing_conversion(self, *args, **kwargs):
        raise cw.CoordinatesWcsError("FRAME_UNSUPPORTED", "conversione di prova", params={"reason": "frame_required"})

    galactic_coords = SkyCoord(10 * u.deg, 20 * u.deg, frame="galactic")
    with monkeypatch.context() as patch:
        patch.setattr(cw.SkyFrame, "to", failing_conversion)
        conv = seen.error(tiles_for_fov, galactic_coords, 1 * u.deg, 3)
        assert conv.params == {"reason": "conversion_center", "detail": {
            "code": "FRAME_UNSUPPORTED", "params": {"reason": "frame_required"}, "text": "conversione di prova"}}
        seen.error(tile_pixel_values, some_tile, galactic_coords)
        seen.error(view_sampling, galactic_service, view)

    # Copertura (MOC del servizio).
    moc = moc_from_region(CircleRegion(SkyCoord(10 * u.deg, 0 * u.deg), 5 * u.deg), 6)
    moc_bytes = write_moc(moc, cache.root.parent / "moc.fits").path.read_bytes()
    service.routes["/hips/Moc.fits"] = lambda request: (200, "application/fits", moc_bytes)
    coverage, _ = service_coverage(hips, cache=cache)
    pole = SkyCoord(0 * u.deg, 89.5 * u.deg)
    seen.error(tiles_for_fov, pole, 1 * u.deg, 3, coverage=coverage)  # field
    polar = int(HEALPix(nside=8, order="nested").lonlat_to_healpix(0 * u.deg, 89.5 * u.deg))
    seen.error(fetch_tile, hips, 3, polar, coverage=coverage, cache=cache)  # tile
    seen.notes(tiles_for_fov(pole, 1 * u.deg, 3, frame="galactic", coverage=coverage).warnings)
    seen.notes(view_sampling(galactic_service, view, coverage=coverage).warnings)
    seen.notes(service_coverage(tile_service(service, cache, path="/senzamoc"), cache=cache)[1])  # moc_missing
    seen.notes(order_for_resolution(hips, 1e-6 * u.arcsec)[1])

    # Tipi di HiPS.
    catalog = read_service(serve_properties(service, "/cat", properties_text(
        dataproduct_type="catalog", hips_tile_format="tsv", hips_tile_width=None)), cache=cache)
    seen.error(order_for_resolution, catalog, 1 * u.arcsec)
    seen.error(fetch_tile, catalog, 0, 0, cache=cache)
    seen.error(cube_planes, hips)
    seen.error(catalog_tiles, hips, center, 1 * u.deg, 1, cache=cache)

    # Errori dei tile, avvisi dei tile, rete.
    service.routes["/hips/" + tile_path(3, 20, "fits")] = lambda request: (500, "text/plain", "guasto")
    http = seen.error(fetch_tile, hips, 3, 20, cache=cache)
    assert http.params["status"] == 500 and http.params["url"].endswith("Npix20.fits")
    jpeg_only = tile_service(service, cache, formats="jpeg", path="/jpg")
    seen.error(fetch_tile, jpeg_only, 3, 0, format="fits", cache=cache)
    seen.error(fetch_tile, hips, 3, 12, cache=cache)  # 404
    route_tile(service, "/hips", 3, 10, b"non un FITS")
    seen.error(fetch_tile, hips, 3, 10, cache=cache)
    calls = {"n": 0}

    def flaky(request):
        calls["n"] += 1
        return 200, "application/fits", b"SIMPLE  = rovinato" if calls["n"] == 1 else fits_tile(2)

    service.routes["/hips/" + tile_path(3, 9, "fits")] = flaky
    seen.notes(fetch_tile(hips, 3, 9, cache=cache).warnings)  # tile_corrupt (avviso)
    from datetime import UTC, datetime

    cache.put("12", f"tile:{hips.base_url}/{tile_path(3, 13, 'fits')}", b"rovinato", origin="prova",
              retrieved_at=datetime.now(UTC))
    route_tile(service, "/hips", 3, 13, fits_tile(4))
    seen.notes(fetch_tile(hips, 3, 13, cache=cache).warnings)  # cache_corrupt
    cached = fetch_tile(hips, 3, 13, cache=cache)
    assert cached.from_cache
    seen.notes(cached.warnings)  # FROM_CACHE cached_tile
    dead = dataclasses.replace(hips, base_url="http://127.0.0.1:9/morto")
    timeout = seen.error(fetch_tile, dead, 3, 7, cache=cache, timeouts=fast)
    assert timeout.params["connect"] == {"value": 0.5, "unit": "s"} and timeout.params["read"]["unit"] == "s"
    assert timeout.message.startswith("http://127.0.0.1:9/morto/") and "0.5 s connessione" in timeout.message

    # Cubi.
    cube = read_service(serve_properties(service, "/cubo", properties_text(
        dataproduct_type="cube", hips_cube_depth="3", data_cube_crpix3="1", data_cube_crval3="1.4e9",
        data_cube_cdelt3="-1e5", data_cube_bunit3="Hz")), cache=cache)
    seen.error(fetch_tile, cube, 3, 50, plane=5, cache=cache)
    seen.error(fetch_tile, hips, 3, 50, plane=1, cache=cache)
    for name, extra in (("u1", {"data_cube_bunit3": None}), ("u2", {"data_cube_bunit3": "frobnicate"}),
                        ("u3", {"data_cube_cdelt3": None})):
        base = {"dataproduct_type": "cube", "hips_cube_depth": "3", "data_cube_crpix3": "1",
                "data_cube_crval3": "1.4e9", "data_cube_cdelt3": "-1e5", "data_cube_bunit3": "Hz"}
        seen.notes(cube_planes(read_service(serve_properties(service, f"/{name}", properties_text(**(base | extra))),
                                            cache=cache)).warnings)

    # Valore del pixel e finestra.
    png_service = tile_service(service, cache, formats="png", path="/png")
    payload, _ = image_tile("png")
    route_tile(service, "/png", 3, 5, payload, ext="png", ctype="image/png")
    png_tile = fetch_tile(png_service, 3, 5, format="png", cache=cache)
    seen.error(tile_pixel_values, png_tile, center)
    seen.error(pixel_values, jpeg_only, center, cache=cache)
    seen.error(tile_pixel_values, some_tile, SkyCoord(200 * u.deg, -50 * u.deg))
    route_all_tiles(service, "/hips", 3, fits_tile)
    sampling = view_sampling(hips, view)
    low = fetch_tile(hips, 3, sampling.tiles[0], cache=cache)
    seen.error(fill_view, dataclasses.replace(sampling, order=2), low)
    spare = next(i for i in range(768) if i not in sampling.tiles)
    seen.error(fill_view, sampling, fetch_tile(hips, 3, spare, cache=cache))

    # --- P3: coperture, survey, MocServer non raggiungibile ---------------------------------------------------------
    mars = read_service(serve_properties(service, "/marte", properties_text(hips_frame="mars", hips_body="mars")),
                        cache=cache)
    seen.error(service_coverage, mars, cache=cache)
    seen.error(survey_coverage, mars, cache=cache)
    seen.notes(set_survey(mars.base_url, cache=cache).warnings)  # copertura non disponibile (annidato)
    monkeypatch.setattr(hips_module, "DEFAULT_SURVEY", "TEST/P/IR/K")

    def records_route(request):
        wanted = request["params"].get("ID")
        records = [r for r in mocserver_records(service.url + "/hips") if wanted is None or r["ID"] == wanted]
        return 200, "application/json;charset=ISO-8859-1", json.dumps(records, ensure_ascii=False).encode("latin-1")

    service.routes["/MocServer/query"] = records_route
    seen.notes(set_survey(hips_list=HiPSList(), cache=cache).warnings)  # HIPS_DEFAULT_SURVEY
    senza = tile_service(service, cache, path="/fallback")
    whole = moc_from_region(CircleRegion(SkyCoord(0 * u.deg, 0 * u.deg), 180 * u.deg), 3)
    whole_bytes = write_moc(whole, cache.root.parent / "w.fits").path.read_bytes()

    def moc_route(request):
        if request["params"].get("get") == "moc":
            return 200, "application/fits", whole_bytes
        return 404, "text/plain", "x"

    service.routes["/MocServer/query"] = moc_route
    seen.notes(survey_coverage(senza, cache=cache)[1])  # HIPS_COVERAGE_FROM_MOCSERVER
    monkeypatch.setattr(vo, "MOCSERVER_URL", "http://127.0.0.1:9/MocServer/query")
    seen.error(add_hips, "TEST/P/prova/r", cache=cache, timeouts=fast)  # resolve
    with SharedCache(tmp_path / "vuota") as empty:
        seen.error(CollectionIndex(cache=empty, timeouts=fast).sync)  # index
    seen.error(survey_coverage, tile_service(service, cache, path="/senzamoc2"), cache=cache, timeouts=fast)

    # --- P4: catalogo progressivo --------------------------------------------------------------------------------------
    cat = read_service(serve_properties(service, "/cat2", properties_text(
        dataproduct_type="catalog", hips_tile_format="tsv", hips_tile_width=None)), cache=cache)
    seen.error(catalog_tiles, cat, center, 1 * u.deg, 0, cache=cache)  # metadata_xml_unavailable
    service.routes["/cat2/metadata.xml"] = lambda request: (200, "text/xml", "<non xml")
    seen.error(catalog_tiles, cat, center, 1 * u.deg, 0, cache=cache)  # metadata_xml_unreadable
    service.routes["/cat2/metadata.xml"] = lambda request: (200, "text/xml", METADATA_XML)
    index = int(tiles_for_fov(center, 1 * u.deg, 0).indices[0])
    path = f"/cat2/{tile_path(0, index, 'tsv')}"
    service.routes[path] = lambda request: (200, "text/plain", tsv([["x", "1", "2", "3"]], header="a\tb\tc\td"))
    seen.error(catalog_tiles, cat, center, 1 * u.deg, 0, cache=cache)  # file_corrupt
    ints = read_service(serve_properties(service, "/cat3", properties_text(
        dataproduct_type="catalog", hips_tile_format="tsv", hips_tile_width=None)), cache=cache)
    service.routes["/cat3/metadata.xml"] = lambda request: (200, "text/xml", METADATA_XML.replace(
        '<FIELD name="mag" datatype="float"', '<FIELD name="mag" datatype="int"'))
    service.routes[f"/cat3/{tile_path(0, index, 'tsv')}"] = lambda request: (
        200, "text/plain", tsv([["x", "1", "2", "abc"]]))
    seen.error(catalog_tiles, ints, center, 1 * u.deg, 0, cache=cache)  # value_not_conformant
    good = tsv([["x", "45.0", "20.0", "12.5"]])
    cache.put("12", f"tile:{cat.base_url}/{tile_path(0, index, 'tsv')}", b"rovinato", origin="prova",
              retrieved_at=datetime.now(UTC))
    service.routes[path] = lambda request: (200, "text/plain", good)
    seen.notes(catalog_tiles(cat, center, 1 * u.deg, 0, cache=cache).warnings)  # cache_invalid
    state = {"n": 0}

    def bad_then_good(request):
        state["n"] += 1
        return 200, "text/plain", "rovinato" if state["n"] == 1 else good

    service.routes[path] = bad_then_good
    seen.notes(catalog_tiles(cat, center, 1 * u.deg, 0, cache=cache, refresh=True).warnings)  # file_invalid

    # --- P5: build_hips ------------------------------------------------------------------------------------------------
    image, _, _ = tan_image(tmp_path, "a.fits")
    other, _, _ = tan_image(tmp_path, "b.fits", bunit="Jy")
    args = dict(order=3, hips_id="TEST/P/x", title="x", method="bilinear", tile_width=64)
    out = tmp_path / "out"
    seen.error(build_hips, [image], out, **(args | {"method": "flux"}))
    seen.error(build_hips, [image], out, **(args | {"formats": ("png",)}))
    seen.error(build_hips, [image], out, **(args | {"formats": ("png",), "display": (0.0, 1.0, "histeq")}))
    seen.error(build_hips, [image], out, **(args | {"formats": ("png",), "display": (1.0, 0.0, "linear")}))
    seen.error(build_hips, [image], out, **(args | {"order": 24}))
    seen.error(build_hips, [dataclasses.replace(image, limits=LargeImageLimits(operation_bytes=10_000))], out, **args)
    seen.error(build_hips, [dataclasses.replace(image, wcs=None)], out, **args)
    seen.error(build_hips, [dataclasses.replace(image, color=True)], out, **args)
    with monkeypatch.context() as patch:
        patch.setattr(type(image), "is_preview", property(lambda self: True))
        seen.error(build_hips, [image], out, **args)
    empty_image = dataclasses.replace(image, data=np.full(image.data.shape, np.nan, dtype=np.float32))
    seen.error(build_hips, [empty_image], tmp_path / "vuoto", **args)
    built = build_hips([image, other], tmp_path / "ok", **(args | {"order": 1}))
    seen.notes(built.warnings)  # HIPS_UNIT_MIXED e HIPS_ALLSKY_NOT_WRITTEN

    # --- MocServer non raggiungibile con copia locale (per ultimo: chiude il servizio) -------------------------------------
    monkeypatch.setattr(vo, "MOCSERVER_URL", service.url + "/MocServer/index")
    service.routes["/MocServer/index"] = lambda request: (
        200, "application/json", json.dumps([{"ID": "TEST/P/x", "obs_title": "t"}]))
    CollectionIndex(cache=cache).sync()
    service.close()
    seen.notes(CollectionIndex(cache=cache, timeouts=fast).sync().warnings)  # local_copy

    # --- Diagnosi dei tile (messaggi annidati, D40-7): ogni motivo, con il testo italiano invariato ----------------------
    import io

    from astropy.io import fits
    from PIL import Image

    png = io.BytesIO()
    Image.new("RGB", (4, 4)).save(png, format="PNG")
    empty_fits = io.BytesIO()
    fits.HDUList([fits.PrimaryHDU()]).writeto(empty_fits)
    diagnoses = [
        (hips_module._decode_tile(empty_fits.getvalue(), "fits", 4, "u"), "nessun dato nel FITS"),
        (hips_module._decode_tile(fits_tile(1), "fits", 7, "u"), "dimensione "),
        (hips_module._decode_tile(png.getvalue(), "jpeg", 4, "u"), "formato PNG invece di JPEG"),
        (hips_module._decode_tile(b"x", "png", 4, "u"), "immagine non leggibile ("),
        (hips_module._decode_tile(png.getvalue(), "png", 8, "u"), "dimensione "),
        (hips_module._tsv_rows(b"\xff\xfe", ["a"]), "non UTF-8 ("),
        (hips_module._tsv_rows(b"# solo un commento\n", ["a"]), "nessuna riga di intestazione"),
        (hips_module._tsv_rows(b"a\tb\n1\n", ["a", "b"]), "riga 2: 1 campi invece di 2"),
    ]
    for (rows, problem), expected in diagnoses:
        assert rows is None and problem["code"] == "HIPS_TILE_PROBLEM" and problem["text"].startswith(expected)
        seen.pairs.add(check_message(problem["code"], problem["params"], problem["text"]))
    assert mc.message_text("HIPS_TILE_PROBLEM", diagnoses[7][0][1]["params"], "en") == "row 2: 1 fields instead of 2"

    missing = required_combinations() - seen.pairs
    assert not missing, f"errori e avvisi del 12 mai provocati nel test: {sorted(missing, key=str)}"


def test_italian_text_is_unchanged_and_params_are_json():
    """Il testo italiano resta quello del modulo (campo ``message``) e ``params`` sono valori JSON."""
    with pytest.raises(HiPSError) as info:
        parse_properties("senza uguale", source="prova")
    err = info.value
    assert err.message == "prova: riga 1 non è nella forma 'chiave = valore' dello standard HiPS 1.0: 'senza uguale'"
    assert err.params == {"reason": "bad_line", "source": "prova", "line": 1, "content": "senza uguale"}
    json.dumps(err.params)
    assert mc.message_text(err.code, err.params, "en", text=err.message).startswith(
        "prova: line 1 is not in the form 'key = value'")
    assert mc.message_text(err.code, err.params, "it", text=err.message) == err.message.replace("'senza uguale'",
                                                                                              "senza uguale")


def test_relayed_errors_keep_the_code_and_params_of_the_lower_module(cache):
    """``_net`` e il rilancio degli errori del 16 non riscrivono codice, testo e ``params`` (12 §10)."""
    lower = vo.VoProtocolsError("NET_TIMEOUT", "testo del 14", url="http://x",
                                params={"reason": "url", "url": "http://x", "connect": {"value": 1.0, "unit": "s"},
                                        "read": {"value": 2.0, "unit": "s"}, "detail": "boom"})
    relayed = hips_module._net(lower)
    assert (relayed.code, relayed.message, relayed.params, relayed.relayed) == ("NET_TIMEOUT", "testo del 14",
                                                                                 lower.params, True)
    assert check_error(relayed) == ("NET_TIMEOUT", "url")  # con i params del 14 si controlla come ogni errore
    unconverted = MocError("SERVICE_ERROR", "testo del 16", url="http://x")  # il 16 si converte nello sprint 8d
    plain = hips_module._relay(unconverted)
    assert plain.params == {} and plain.relayed and check_error(plain) == ("SERVICE_ERROR", None)
    assert mc.message_text("NET_TIMEOUT", {}, "en", text="testo del 14") == "testo del 14 (no translation)"


def test_every_entry_renders_with_declared_parameters():
    """Voci generali e sotto-voci dei codici del 12: si riempiono con valori di prova senza segnaposto rimasti."""
    samples = {"string": "valore", "number": 1.5, "integer": 3, "boolean": True,
               "quantity": {"value": 2.5, "unit": "s"}, "list": ["a", "b"], "object": {"k": 1},
               "message": {"code": "HIPS_TILE_PROBLEM", "params": {"reason": "no_data"}, "text": "nessun dato"}}
    for code in OWN_CODES:
        entry = mc.CATALOG[code]
        for reason, params in [(None, entry.params)] + [(r, v.params) for r, v in entry.variants.items()]:
            values = {p.name: samples[p.type] for p in params}
            if reason:
                values["reason"] = reason
            for lang in ("en", "it"):
                assert "{" not in mc.message_text(code, values, lang), (code, reason, lang)


def test_nested_messages_are_rendered_in_the_language_and_the_external_text_is_kept():
    """Messaggi annidati (D40-7): ricorsivi nella lingua, testo di terzi tale e quale, ripiego e profondità."""
    inner = {"code": "HIPS_TILE_PROBLEM", "params": {"reason": "fits_unreadable", "detail": "boom of astropy"},
             "text": "FITS non leggibile (boom of astropy)"}
    params = {"reason": "tile_corrupt", "url": "http://x/Npix1.fits", "problem": inner}
    assert mc.message_text("HIPS_BAD_TILE", params, "en") == (
        "http://x/Npix1.fits: tile corrupt even after a new request (FITS not readable (boom of astropy)).")
    assert mc.message_text("HIPS_BAD_TILE", params, "it") == (
        "http://x/Npix1.fits: tile corrotto anche dopo una nuova richiesta (FITS non leggibile (boom of astropy)).")
    # Verso l'IA: il testo di terzi non entra nel testo, resta nei parametri.
    masked = mc.message_text("HIPS_BAD_TILE", params, "en", mask_external=True)
    assert "boom" not in masked and "FITS not readable (<detail>)" in masked
    assert mc.message_params("HIPS_BAD_TILE", params) == {"problem"}
    # Messaggio di un modulo non convertito (senza voce utile): testo originale con la nota; mascherato: <nome>.
    unconverted = {"code": "SERVICE_ERROR", "params": {}, "text": "testo del 14"}
    cov = {"reason": "unavailable", "hips_id": "A/B", "cause_code": "SERVICE_ERROR", "cause": unconverted}
    assert mc.message_text("HIPS_COVERAGE_UNKNOWN", cov, "en") == (
        "A/B: coverage not available (SERVICE_ERROR: testo del 14 (no translation)).")
    assert "<cause>" in mc.message_text("HIPS_COVERAGE_UNKNOWN", cov, "en", mask_external=True)
    assert mc.validate_params("HIPS_COVERAGE_UNKNOWN", cov) == []
    assert mc.validate_params("HIPS_COVERAGE_UNKNOWN", cov | {"cause": {"code": "SERVICE_ERROR"}})  # né testo né voce
    assert mc.validate_params("HIPS_COVERAGE_UNKNOWN", cov | {"cause": "testo"})  # non è un messaggio
    # Profondità: oltre il limite il solo codice.
    deep = {"code": "HIPS_TILE_PROBLEM", "params": {"reason": "no_data"}, "text": "x"}
    for _ in range(mc.MAX_MESSAGE_DEPTH + 1):
        deep = {"code": "HIPS_COVERAGE_UNKNOWN", "params": {"reason": "unavailable", "hips_id": "h",
                                                             "cause_code": "C", "cause": deep}, "text": "x"}
    rendered = mc.message_text("HIPS_COVERAGE_UNKNOWN", deep["params"], "en")
    assert rendered.count("coverage not available") == 1 + mc.MAX_MESSAGE_DEPTH  # primo livello + annidati
    assert mc.validate_params("HIPS_COVERAGE_UNKNOWN", deep["params"])  # troppo profondo
