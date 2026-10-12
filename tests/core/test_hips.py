"""Test del modulo 12 (``mdfiles/12-core-hips.md`` §12).

I file ``properties`` e i tile di prova si scrivono nel test secondo il testo dello standard IVOA HiPS 1.0, mai
copiati da altri programmi (regola d'oro n. 8); i valori attesi si ricalcolano con ``astropy-healpix``,
``astropy`` e ``numpy``.
"""

import json

import pytest

from astrotwo.core.hips import (
    HIPS_STANDARD_VERSION,
    HiPSError,
    HiPSList,
    add_hips,
    parse_properties,
    read_service,
)

# =============================================================================
# P1 — Metadati e add_hips (T7, T8)


def properties_text(**overrides) -> str:
    """File properties con le 9 chiavi obbligatorie dello standard HiPS 1.0 (§4.4.1); ``None`` toglie una chiave."""
    props = {
        "creator_did": "ivo://TEST/P/prova/r",
        "obs_title": "Survey di prova",
        "dataproduct_type": "image",
        "hips_version": HIPS_STANDARD_VERSION,
        "hips_release_date": "2026-10-01T12:00Z",
        "hips_status": "public master clonableOnce",
        "hips_tile_format": "fits png",
        "hips_order": "3",
        "hips_frame": "equatorial",
        "hips_tile_width": "64",
        "obs_regime": "Optical",
        "em_min": "6e-7",
        "em_max": "7e-7",
        "hips_pixel_scale": "0.0143",
        "obs_description": "Dati sintetici scritti nel test",
    }
    props.update(overrides)
    lines = ["# commento: ignorato", ""]
    lines += [f"{key:20} = {value}" for key, value in props.items() if value is not None]
    return "\n".join(lines) + "\n"


def serve_properties(service, path="/hips", text=None):
    body = properties_text() if text is None else text
    service.routes[path + "/properties"] = lambda request: (200, "text/plain", body)
    return service.url + path


def test_parse_properties():
    props = parse_properties("# c\n\nkey_a = 1\n  key_b=due parole  \nkey_a = 2\nvuota =\n")
    assert props == {"key_a": ("1", "2"), "key_b": ("due parole",), "vuota": ("",)}
    for bad in ("<html><body>pagina</body></html>", "chiave con spazi = 1", "", "# solo commento\n"):
        with pytest.raises(HiPSError) as err:
            parse_properties(bad)
        assert err.value.code == "HIPS_NOT_A_SERVICE"


def test_t7_add_hips_from_url(service, cache):
    url = serve_properties(service)
    hips = HiPSList()
    added = hips.add_hips(url + "/", cache=cache)
    assert added.hips_id == "TEST/P/prova/r" and added.base_url == url and "TEST/P/prova/r" in hips
    assert (added.title, added.dataproduct_type, added.order, added.tile_width) == ("Survey di prova", "image", 3, 64)
    assert added.tile_formats == ("fits", "png") and added.frame == "equatorial" and added.body == "celestial"
    assert added.version == "1.4" and added.release_date.isoformat() == "2026-10-01T12:00:00+00:00"
    assert added.em_range[0].value == pytest.approx(6e-7) and str(added.em_range.unit) == "m"
    assert added.pixel_scale.to_value("deg") == pytest.approx(0.0143)
    assert added.origin == url + "/properties" and added.request.url == url + "/properties"
    assert added.warnings == () and hips.get("TEST/P/prova/r") is added
    assert "Survey di prova" in added.describe() and "corpo celestial" in added.describe()
    # Seconda lettura dalla cache, con la provenienza.
    again = read_service(url, cache=cache)
    assert again.from_cache and "FROM_CACHE" in dict(again.warnings) and service.hits("/hips/properties") == 1
    listed = hips.add_hips(url, cache=cache)
    assert "HIPS_ALREADY_LISTED" in dict(listed.warnings) and len(hips) == 1


def test_t8_not_a_service(service, cache):
    hips = HiPSList()
    service.routes["/pagina/properties"] = lambda request: (200, "text/html", "<html><body>Benvenuti</body></html>")
    service.routes["/json/properties"] = lambda request: (200, "application/json", json.dumps({"a": 1}))
    service.routes["/altro/properties"] = lambda request: (200, "text/plain", "colore = rosso\n")
    for path in ("/pagina", "/json", "/altro", "/assente"):
        with pytest.raises(HiPSError) as err:
            hips.add_hips(service.url + path, cache=cache)
        assert err.value.code == "HIPS_NOT_A_SERVICE", path
    assert len(hips) == 0


@pytest.mark.parametrize(("change", "field"), [
    ({"obs_title": None}, "obs_title"),
    ({"hips_order": "tre"}, "hips_order"),
    ({"hips_order": "30"}, "hips_order"),
    ({"hips_tile_format": "gif"}, "hips_tile_format"),
    ({"hips_tile_format": "tsv"}, "hips_tile_format"),
    ({"dataproduct_type": "spectral-cube"}, "dataproduct_type"),
    ({"dataproduct_type": "cube"}, "hips_cube_depth"),
    ({"hips_release_date": "1 ottobre 2026"}, "hips_release_date"),
    ({"hips_tile_width": "100"}, "hips_tile_width"),
    ({"em_min": "rosso"}, "em_min"),
])
def test_metadata_invalid(service, cache, change, field):
    url = serve_properties(service, text=properties_text(**change))
    hips = HiPSList()
    with pytest.raises(HiPSError) as err:
        hips.add_hips(url, cache=cache)
    assert err.value.code == "HIPS_METADATA_INVALID" and err.value.details["field"] == field
    assert len(hips) == 0
    with pytest.raises(HiPSError):  # una risposta non valida non va in cache
        read_service(url, cache=cache)
    assert service.hits("/hips/properties") == 2


def test_catalog_and_defaults(service, cache):
    url = serve_properties(service, text=properties_text(dataproduct_type="catalog", hips_tile_format="tsv",
                                                         hips_tile_width=None, hips_version="1.5"))
    cat = read_service(url, cache=cache)
    assert cat.tile_width is None and cat.tile_formats == ("tsv",) and "HIPS_VERSION_UNKNOWN" in dict(cat.warnings)
    url2 = serve_properties(service, "/img", properties_text(hips_tile_width=None))
    img = read_service(url2, cache=cache)
    assert img.tile_width == 512 and "HIPS_DEFAULT_TILE_WIDTH" in dict(img.warnings)


@pytest.mark.parametrize(("frame", "body", "expected", "code"), [
    ("galactic", None, "celestial", None),
    ("ecliptic", None, "celestial", None),
    ("mars", "mars", "mars", "HIPS_BODY_DRAFT"),
    ("mars", None, None, "BODY_UNKNOWN"),
    ("mars", "moon", None, "BODY_UNKNOWN"),
])
def test_body_from_frame(service, cache, frame, body, expected, code):
    url = serve_properties(service, text=properties_text(hips_frame=frame, hips_body=body))
    hips = HiPSList()
    found = hips.add_hips(url, cache=cache)
    assert found.body == expected and found.hips_id in hips  # anche con corpo ignoto il dato si apre (da solo)
    assert (code in dict(found.warnings)) if code else found.warnings == ()


def test_add_hips_by_id(service, cache, monkeypatch):
    from astrotwo.core import vo_protocols as vo

    url = serve_properties(service)
    records = {"TEST/P/prova/r": {"ID": "TEST/P/prova/r", "hips_service_url": url, "dataproduct_type": "image"},
               "TEST/C/solo-catalogo": {"ID": "TEST/C/solo-catalogo", "dataproduct_type": "catalog"},
               "TEST/P/altro": {"ID": "TEST/P/altro", "hips_service_url": url}}

    def mocserver(request):
        found = [records[request["params"]["ID"]]] if request["params"]["ID"] in records else []
        return 200, "application/json", json.dumps(found)

    service.routes["/MocServer/query"] = mocserver
    monkeypatch.setattr(vo, "MOCSERVER_URL", service.url + "/MocServer/query")
    got = add_hips("ivo://TEST/P/prova/r", cache=cache)
    assert got.hips_id == "TEST/P/prova/r" and got.base_url == url
    sent = [r for r in service.requests if r["path"] == "/MocServer/query"][0]["params"]
    assert sent["ID"] == "TEST/P/prova/r" and sent["get"] == "record" and sent["fmt"] == "json"
    for hips_id, code in (("TEST/P/sconosciuto", "HIPS_UNKNOWN"), ("TEST/C/solo-catalogo", "HIPS_NOT_A_SERVICE")):
        with pytest.raises(HiPSError) as err:
            add_hips(hips_id, cache=cache)
        assert err.value.code == code
    other = add_hips("TEST/P/altro", cache=cache)
    assert "HIPS_ID_MISMATCH" in dict(other.warnings) and other.hips_id == "TEST/P/prova/r"
    with pytest.raises(HiPSError) as err:
        HiPSList().get("TEST/P/nessuno")
    assert err.value.code == "HIPS_UNKNOWN"


def test_network_errors(cache, monkeypatch):
    from astrotwo.core import vo_protocols as vo
    from astrotwo.core.cache import NetworkTimeouts

    fast = NetworkTimeouts(connect=0.5, read=0.5)
    with pytest.raises(HiPSError) as err:
        add_hips("http://127.0.0.1:9/hips", cache=cache, timeouts=fast)
    assert err.value.code == "NET_TIMEOUT"
    monkeypatch.setattr(vo, "MOCSERVER_URL", "http://127.0.0.1:9/MocServer/query")
    with pytest.raises(HiPSError) as err:
        add_hips("TEST/P/prova/r", cache=cache, timeouts=fast)
    assert err.value.code == "MOCSERVER_UNAVAILABLE"


# =============================================================================
# P2 — Tile (T2–T6, T12)

import io  # noqa: E402

import astropy.units as u  # noqa: E402
import numpy as np  # noqa: E402
from astropy.coordinates import SkyCoord  # noqa: E402
from astropy.io import fits  # noqa: E402
from astropy_healpix import HEALPix  # noqa: E402
from PIL import Image  # noqa: E402

from astrotwo.core.cache import NetworkTimeouts, SharedCache  # noqa: E402
from astrotwo.core.hips import (  # noqa: E402
    TileMemory,
    fetch_tile,
    order_for_resolution,
    pixel_values,
    service_coverage,
    tile_path,
    tile_pixel_values,
    tiles_for_fov,
)
from astrotwo.core.moc import CircleRegion, moc_from_region, write_moc  # noqa: E402

WIDTH = 64


def fits_tile(seed: int, width: int = WIDTH) -> bytes:
    data = np.random.default_rng(seed).normal(size=(width, width)).astype(np.float32)
    buffer = io.BytesIO()
    fits.PrimaryHDU(data, header=fits.Header({"BUNIT": "mJy"})).writeto(buffer)
    return buffer.getvalue()


def image_tile(fmt: str, width: int = WIDTH) -> tuple[bytes, np.ndarray]:
    rows = np.arange(width, dtype=np.uint8)[:, None] * np.ones((1, width), dtype=np.uint8)
    array = np.stack([rows, rows, rows], axis=-1)  # riga 0 del file = alto del tile (standard §4.2.1.3)
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG" if fmt == "png" else "JPEG", quality=100)
    return buffer.getvalue(), array


def tile_service(service, cache, *, formats="fits png jpeg", order=3, frame="equatorial", path="/hips"):
    url = serve_properties(service, path, properties_text(hips_tile_format=formats, hips_order=str(order),
                                                          hips_frame=frame, hips_tile_width=str(WIDTH)))
    return read_service(url, cache=cache)


def route_tile(service, path, order, index, payload, ext="fits", ctype="application/fits"):
    service.routes[f"{path}/{tile_path(order, index, ext)}"] = lambda request: (200, ctype, payload)


def boundary_cells(order, lon, lat, radius):
    """Celle toccate dal cerchio ricalcolate nel test: centro o contorno campionato (astropy-healpix) entro il
    raggio, più la cella del centro."""
    hp = HEALPix(nside=2 ** order, order="nested")
    cells = np.arange(hp.npix)
    blon, blat = hp.boundaries_lonlat(cells, step=50)
    center = SkyCoord(lon, lat)
    near = SkyCoord(blon, blat).separation(center).min(axis=1) <= radius
    clon, clat = hp.healpix_to_lonlat(cells)
    near |= SkyCoord(clon, clat).separation(center) <= radius
    return set(cells[near]) | {int(hp.lonlat_to_healpix(lon, lat))}


def test_tile_path():
    assert tile_path(6, 10302, "fits") == "Norder6/Dir10000/Npix10302.fits"  # esempio dello standard §4.1
    assert tile_path(3, 5, "jpg") == "Norder3/Dir0/Npix5.jpg" and tile_path(3, 5, "png", plane=2) == \
        "Norder3/Dir0/Npix5_2.png"


@pytest.mark.parametrize("order", [3, 6])
def test_t2_tiles_for_fov(order):
    center = SkyCoord(0 * u.deg, 0 * u.deg, frame="icrs")
    sel = tiles_for_fov(center, 1 * u.deg, order)
    assert set(sel.indices) == boundary_cells(order, 0 * u.deg, 0 * u.deg, 1 * u.deg)
    assert sel.order == order and "cone_search_lonlat" in sel.description
    # Centro galattico: convertito nel frame del HiPS con il modulo 10; in un HiPS galattico è il punto (0°, 0°).
    gal = SkyCoord(0 * u.deg, 0 * u.deg, frame="galactic")
    in_gal = tiles_for_fov(gal, 1 * u.deg, order, frame="galactic")
    assert set(in_gal.indices) == set(sel.indices)
    icrs = gal.icrs
    assert set(tiles_for_fov(gal, 1 * u.deg, order).indices) == boundary_cells(order, icrs.ra, icrs.dec, 1 * u.deg)
    for bad in (0 * u.deg, 181 * u.deg, 1.0):
        with pytest.raises(HiPSError) as err:
            tiles_for_fov(center, bad, order)
        assert err.value.code == "REGION_INVALID"
    with pytest.raises(HiPSError) as err:
        tiles_for_fov(center, 1 * u.deg, 30)
    assert err.value.code == "HEALPIX_ORDER_INVALID"
    for frame in ("ecliptic", "mars"):
        with pytest.raises(HiPSError) as err:
            tiles_for_fov(center, 1 * u.deg, order, frame=frame)
        assert err.value.code == "HIPS_FRAME_UNSUPPORTED"


def test_t3_cache_and_provenance(service, cache):
    hips = tile_service(service, cache)
    payload = fits_tile(1)
    route_tile(service, "/hips", 3, 100, payload)
    first = fetch_tile(hips, 3, 100, cache=cache)
    second = fetch_tile(hips, 3, 100, cache=cache)
    assert not first.from_cache and second.from_cache and "FROM_CACHE" in dict(second.warnings)
    assert first.url == second.url == service.url + "/hips/Norder3/Dir0/Npix100.fits"
    assert first.retrieved_at == second.retrieved_at and service.hits("/hips/Norder3/Dir0/Npix100.fits") == 1
    assert np.array_equal(second.data, fits.getdata(io.BytesIO(payload))) and second.data.dtype == np.dtype(">f4")  # tipo nativo del FITS (DC6)
    assert first.body == "celestial" and first.url in first.provenance()
    memory = TileMemory()
    held = fetch_tile(hips, 3, 100, cache=cache, memory=memory)
    assert fetch_tile(hips, 3, 100, cache=cache, memory=memory) is held and len(memory) == 1
    fresh = fetch_tile(hips, 3, 100, cache=cache, refresh=True)
    assert not fresh.from_cache and service.hits("/hips/Norder3/Dir0/Npix100.fits") == 2


def test_t4_cache_limit(service, tmp_path):
    size = len(fits_tile(0))
    small = SharedCache(tmp_path / "piccola", limit_bytes=3 * size)
    hips = tile_service(service, small)
    for index in range(6):
        route_tile(service, "/hips", 3, index, fits_tile(index))
        fetch_tile(hips, 3, index, cache=small)
        assert small.usage().total_bytes <= 3 * size
    kept = [i for i in range(6) if small.get("12", f"tile:{hips.base_url}/{tile_path(3, i, 'fits')}") is not None]
    assert kept == [3, 4, 5]  # tolti i tile usati meno di recente
    small.close()


def test_tile_memory_limit():
    def tile(i):
        from datetime import UTC, datetime

        from astrotwo.core.hips import HiPSTile

        return HiPSTile("x", 3, i, "fits", np.zeros((WIDTH, WIDTH)), None, f"u{i}", datetime.now(UTC), False,
                        "celestial")

    nbytes = WIDTH * WIDTH * 8
    memory = TileMemory(limit_bytes=2 * nbytes)
    for i in range(4):
        memory.put(tile(i))
    assert len(memory) == 2 and memory.total_bytes <= 2 * nbytes and memory.evicted == 2
    assert memory.get("u0") is None and memory.get("u3") is not None
    from astrotwo.core.hips import DEFAULT_TILE_MEMORY_BYTES

    assert TileMemory().limit_bytes == DEFAULT_TILE_MEMORY_BYTES == 512_000_000


def test_t5_out_of_coverage(service, cache):
    hips = tile_service(service, cache, order=3)
    coverage_moc = moc_from_region(CircleRegion(SkyCoord(10 * u.deg, 0 * u.deg), 5 * u.deg), 6)
    path = write_moc(coverage_moc, cache.root.parent / "moc.fits").path
    service.routes["/hips/Moc.fits"] = lambda request: (200, "application/fits", path.read_bytes())
    coverage, notes = service_coverage(hips, cache=cache)
    assert coverage == coverage_moc and notes == ()
    pole = SkyCoord(0 * u.deg, 89.5 * u.deg)
    with pytest.raises(HiPSError) as err:
        tiles_for_fov(pole, 1 * u.deg, 3, coverage=coverage)
    assert err.value.code == "HIPS_OUT_OF_COVERAGE"
    hp = HEALPix(nside=2 ** 3, order="nested")
    polar_tile = int(hp.lonlat_to_healpix(0 * u.deg, 89.5 * u.deg))
    with pytest.raises(HiPSError) as err:
        fetch_tile(hips, 3, polar_tile, coverage=coverage, cache=cache)
    assert err.value.code == "HIPS_OUT_OF_COVERAGE"
    assert not any("Npix" in r["path"] for r in service.requests)  # nessuna richiesta di tile
    # Campo a cavallo del bordo: restano solo i tile che toccano il MOC (ricalcolo con mocpy nel test).
    edge = tiles_for_fov(SkyCoord(16 * u.deg, 0 * u.deg), 3 * u.deg, 3, coverage=coverage)
    full = tiles_for_fov(SkyCoord(16 * u.deg, 0 * u.deg), 3 * u.deg, 3)
    from mocpy import MOC

    expected = [i for i in full.indices if not MOC.from_healpix_cells(np.array([i]), np.array([3]), 3)
                .intersection(coverage.moc).empty()]
    assert list(edge.indices) == expected and edge.outside_coverage == len(full.indices) - len(expected)
    other = tile_service(service, cache, path="/vuoto")
    none, notes = service_coverage(other, cache=cache)
    assert none is None and "HIPS_COVERAGE_UNKNOWN" in dict(notes)
    gal = tiles_for_fov(pole, 1 * u.deg, 3, frame="galactic", coverage=coverage)
    assert "HIPS_COVERAGE_NOT_CHECKED" in dict(gal.warnings)


def test_t6_network_error(service, tmp_path):
    cache = SharedCache(tmp_path / "c")
    hips = tile_service(service, cache)
    service.close()
    fast = NetworkTimeouts(connect=0.5, read=0.5)
    with pytest.raises(HiPSError) as err:
        fetch_tile(hips, 3, 7, cache=cache, timeouts=fast)
    assert err.value.code == "NET_TIMEOUT" and cache.get("12", f"tile:{hips.base_url}/{tile_path(3, 7, 'fits')}") is None
    cache.close()


def test_bad_and_missing_tiles(service, cache):
    hips = tile_service(service, cache)
    calls = {"n": 0}

    def flaky(request):
        calls["n"] += 1
        return 200, "application/fits", b"SIMPLE  = rovinato" if calls["n"] == 1 else fits_tile(2)

    service.routes["/hips/" + tile_path(3, 9, "fits")] = flaky
    tile = fetch_tile(hips, 3, 9, cache=cache)
    assert calls["n"] == 2 and "HIPS_TILE_DISCARDED" in dict(tile.warnings)
    route_tile(service, "/hips", 3, 10, b"non un FITS")
    with pytest.raises(HiPSError) as err:
        fetch_tile(hips, 3, 10, cache=cache)
    assert err.value.code == "HIPS_BAD_TILE" and service.hits("/hips/" + tile_path(3, 10, "fits")) == 2
    route_tile(service, "/hips", 3, 11, fits_tile(3, width=32))  # dimensione inattesa
    with pytest.raises(HiPSError) as err:
        fetch_tile(hips, 3, 11, cache=cache)
    assert err.value.code == "HIPS_BAD_TILE"
    with pytest.raises(HiPSError) as err:
        fetch_tile(hips, 3, 12, cache=cache)
    assert err.value.code == "HIPS_TILE_MISSING"
    # Copia in cache corrotta: scartata, una nuova richiesta.
    key = f"tile:{hips.base_url}/{tile_path(3, 13, 'fits')}"
    from datetime import UTC, datetime

    cache.put("12", key, b"rovinato", origin="prova", retrieved_at=datetime.now(UTC))
    route_tile(service, "/hips", 3, 13, fits_tile(4))
    healed = fetch_tile(hips, 3, 13, cache=cache)
    assert not healed.from_cache and "HIPS_TILE_DISCARDED" in dict(healed.warnings)
    for args, code in (((4, 0), "HEALPIX_ORDER_INVALID"), ((3, 768), "HEALPIX_INDEX_INVALID")):
        with pytest.raises(HiPSError) as err:
            fetch_tile(hips, *args, cache=cache)
        assert err.value.code == code
    jpeg_only = tile_service(service, cache, formats="jpeg", path="/jpg")
    with pytest.raises(HiPSError) as err:
        fetch_tile(jpeg_only, 3, 0, format="fits", cache=cache)
    assert err.value.code == "HIPS_FORMAT_UNAVAILABLE"


@pytest.mark.parametrize("fmt", ["png", "jpeg"])
def test_image_tiles(service, cache, fmt):
    hips = tile_service(service, cache)
    payload, array = image_tile(fmt)
    ext = "png" if fmt == "png" else "jpg"
    route_tile(service, "/hips", 3, 20, payload, ext=ext, ctype=f"image/{fmt}")
    tile = fetch_tile(hips, 3, 20, format=fmt, cache=cache)
    assert tile.data.shape == (WIDTH, WIDTH, 3) and tile.header is None
    # Riga 0 nell'orientamento FITS = ultima riga del file (standard §4.2.1.3).
    assert np.array_equal(tile.data[:, :, 0], array[::-1, :, 0]) if fmt == "png" else \
        np.abs(tile.data[:, :, 0].astype(int) - array[::-1, :, 0]).max() <= 2
    with pytest.raises(HiPSError) as err:
        tile_pixel_values(tile, SkyCoord(0 * u.deg, 0 * u.deg))
    assert err.value.code == "HIPS_PIXEL_UNAVAILABLE"
    route_tile(service, "/hips", 3, 21, fits_tile(5), ext=ext, ctype=f"image/{fmt}")  # FITS al posto di un'immagine
    with pytest.raises(HiPSError) as err:
        fetch_tile(hips, 3, 21, format=fmt, cache=cache)
    assert err.value.code == "HIPS_BAD_TILE"


def test_t12_pixel_value(service, cache):
    """Valore sotto il cursore uguale a quello del tile FITS letto con astropy.io.fits; pixel atteso dal WCS HPX
    del tile calcolato da reproject (verifica indipendente della disposizione dei pixel)."""
    import warnings

    from astropy.coordinates import ICRS
    from astropy.wcs import WCS

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from reproject.hips._utils import tile_header

    order, shift = 3, 6
    hips = tile_service(service, cache, order=order)
    rng = np.random.default_rng(7)
    hp = HEALPix(nside=2 ** (order + shift), order="nested")
    for index in (100, 333):
        payload = fits_tile(index)
        route_tile(service, "/hips", order, index, payload)
        cells = (index << (2 * shift)) + rng.integers(0, 4 ** shift, 25)
        lon, lat = hp.healpix_to_lonlat(cells)
        coords = SkyCoord(lon, lat, frame="icrs")
        got = pixel_values(hips, coords, cache=cache)
        px, py = WCS(tile_header(level=order, index=index, frame=ICRS(), tile_dims=WIDTH)).world_to_pixel(coords)
        data = fits.getdata(io.BytesIO(payload))
        assert np.array_equal(got.x, np.round(px).astype(int)) and np.array_equal(got.y, np.round(py).astype(int))
        assert np.array_equal(got.values, data[np.round(py).astype(int), np.round(px).astype(int)])
        assert got.unit == "mJy" and got.order == order and set(got.tile_index) == {index}
        tile = fetch_tile(hips, order, index, cache=cache)
        assert np.array_equal(tile_pixel_values(tile, coords).values, got.values)
    with pytest.raises(HiPSError) as err:
        tile_pixel_values(tile, SkyCoord(180 * u.deg, -60 * u.deg))
    assert err.value.code == "HIPS_OUT_OF_TILE"
    jpeg_only = tile_service(service, cache, formats="jpeg", path="/jpg")
    with pytest.raises(HiPSError) as err:
        pixel_values(jpeg_only, coords, cache=cache)
    assert err.value.code == "HIPS_PIXEL_UNAVAILABLE"


def test_order_for_resolution(service, cache):
    from astropy_healpix import nside_to_pixel_resolution

    hips = tile_service(service, cache, order=8)
    order, notes = order_for_resolution(hips, 1 * u.arcmin)
    assert nside_to_pixel_resolution(2 ** (order + 6)) <= 1 * u.arcmin < nside_to_pixel_resolution(2 ** (order + 5))
    deepest, notes = order_for_resolution(hips, 0.001 * u.arcsec)
    assert deepest == 8 and "HIPS_RESOLUTION_LIMIT" in dict(notes)


# =============================================================================
# P3 — Collezioni, survey attivo, copertura (T1, T10, T11)

from astrotwo.core.hips import (  # noqa: E402
    DEFAULT_SURVEY,
    INDEX_FIELDS,
    CollectionIndex,
    set_survey,
    survey_coverage,
)


def mocserver_records(url):
    return [
        {"ID": "CDS/P/DSS2/color", "obs_title": "DSS colored", "dataproduct_type": "image",
         "dataproduct_subtype": "color", "hips_service_url": url, "hips_frame": "equatorial", "hips_order": "9",
         "hips_tile_format": "jpeg", "obs_regime": "Optical", "client_category": "Image/Optical/DSS"},
        {"ID": "TEST/P/IR/K", "obs_title": "Survey K (2.2 µm)", "dataproduct_type": "image", "hips_service_url": url,
         "hips_frame": "galactic", "obs_regime": "Infrared", "client_category": "Image/Infrared"},
        {"ID": "TEST/P/Mars/carta", "obs_title": "Carta di Marte", "dataproduct_type": "image",
         "hips_service_url": url, "hips_frame": "mars", "hips_body": "mars", "client_category": "Solar system/Mars"},
    ]


@pytest.fixture
def mocserver(service, monkeypatch):
    from astrotwo.core import vo_protocols as vo

    state = {"up": True}

    def route(request):
        params = request["params"]
        records = mocserver_records(service.url + "/hips")
        if "ID" in params:
            records = [r for r in records if r["ID"] == params["ID"]]
        # Il MocServer risponde in ISO-8859-1 (verificato il 2026-10-12).
        return 200, "application/json;charset=ISO-8859-1", json.dumps(records, ensure_ascii=False).encode("latin-1")

    service.routes["/MocServer/query"] = lambda request: route(request) if state["up"] else (500, "text/plain", "x")
    monkeypatch.setattr(vo, "MOCSERVER_URL", service.url + "/MocServer/query")
    return state


def test_t10_collection_index(service, cache, mocserver):
    index = CollectionIndex(cache=cache).sync()
    assert len(index.records) == 3 and index.origin.endswith("/MocServer/query") and not index.from_cache
    assert index.synced_at is not None and index.request.rows == 3 and "3 collezioni HiPS" in index.describe()
    sent = [r for r in service.requests if r["path"] == "/MocServer/query"][0]["params"]
    assert sent["expr"] == "hips_service_url=*" and sent["fields"] == ",".join(INDEX_FIELDS)
    assert [r["ID"] for r in index.filter("µm")] == ["TEST/P/IR/K"]  # testo ISO-8859-1 letto correttamente
    assert [r["ID"] for r in index.filter("dss colored")] == ["CDS/P/DSS2/color"]
    assert [r["ID"] for r in index.filter(hips_frame="mars")] == ["TEST/P/Mars/carta"]
    assert [r["ID"] for r in index.filter(client_category="image/*")] == ["CDS/P/DSS2/color", "TEST/P/IR/K"]
    assert index.filter("carta", obs_regime="*") == ()  # tutte le regole: obs_regime assente
    assert len(index.filter()) == 3


def test_t11_mocserver_unavailable(service, cache, mocserver, tmp_path):
    from astrotwo.core import vo_protocols as vo
    from astrotwo.core.hips import HiPSError

    first = CollectionIndex(cache=cache).sync()
    service.close()  # rete assente: copia locale con la sua data
    fast = NetworkTimeouts(connect=0.5, read=0.5)
    local = CollectionIndex(cache=cache, timeouts=fast).sync()
    assert local.from_cache and local.records == first.records and local.synced_at == first.synced_at
    note = dict(local.warnings)["MOCSERVER_UNAVAILABLE"]
    assert first.synced_at.isoformat() in note
    empty = SharedCache(tmp_path / "vuota")
    with pytest.raises(HiPSError) as err:
        CollectionIndex(cache=empty, timeouts=fast).sync()
    assert err.value.code == "MOCSERVER_UNAVAILABLE"
    empty.close()
    assert vo.MOCSERVER_URL.endswith("/MocServer/query")


def test_t1_list_and_default_survey(service, cache, mocserver):
    """Elenco con il survey predefinito (DSS2 a colori) e metadati completi; set_survey di default."""
    index = CollectionIndex(cache=cache).sync()
    dss = [r for r in index.records if r["ID"] == DEFAULT_SURVEY]
    assert dss and all(dss[0].get(k) for k in ("obs_title", "dataproduct_type", "hips_service_url", "hips_frame"))
    serve_properties(service, "/hips", properties_text(creator_did="ivo://CDS/P/DSS2/color", hips_tile_format="jpeg",
                                                       dataproduct_subtype="color"))
    coverage_moc = moc_from_region(CircleRegion(SkyCoord(10 * u.deg, 0 * u.deg), 5 * u.deg), 5)
    payload = write_moc(coverage_moc, cache.root.parent / "c.fits").path.read_bytes()
    service.routes["/hips/Moc.fits"] = lambda request: (200, "application/fits", payload)
    hips = HiPSList()
    active = set_survey(hips_list=hips, cache=cache)
    assert active.service.hips_id == DEFAULT_SURVEY and DEFAULT_SURVEY in hips
    assert active.coverage == coverage_moc and "HIPS_DEFAULT_SURVEY" in dict(active.warnings)
    again = set_survey(DEFAULT_SURVEY, hips_list=hips, cache=cache)
    assert again.service is active.service


def test_survey_coverage_fallback(service, cache, mocserver):
    from astrotwo.core import vo_protocols as vo
    from astrotwo.core.hips import HiPSError

    hips = tile_service(service, cache, path="/senza-moc")
    whole = moc_from_region(CircleRegion(SkyCoord(0 * u.deg, 0 * u.deg), 180 * u.deg), 3)
    payload = write_moc(whole, cache.root.parent / "w.fits").path.read_bytes()

    def route(request):
        if request["params"].get("get") == "moc":
            assert request["params"] == {"ID": hips.hips_id, "get": "moc", "fmt": "fits"}
            return 200, "application/fits", payload
        return 404, "text/plain", "x"

    service.routes["/MocServer/query"] = route
    moc, notes = survey_coverage(hips, cache=cache)
    assert moc == whole and "HIPS_COVERAGE_FROM_MOCSERVER" in dict(notes) and "HIPS_COVERAGE_UNKNOWN" in dict(notes)
    mars = read_service(serve_properties(service, "/marte", properties_text(hips_frame="mars", hips_body="mars")),
                        cache=cache)
    with pytest.raises(HiPSError) as err:
        survey_coverage(mars, cache=cache)
    assert err.value.code == "HIPS_FRAME_UNSUPPORTED"
    active = set_survey(mars.base_url, cache=cache)
    assert active.coverage is None and "HIPS_COVERAGE_UNKNOWN" in dict(active.warnings)
    assert vo.MOCSERVER_URL.startswith(service.url)


# =============================================================================
# P4 — Cubi (T9) e cataloghi progressivi (test nuovo)

from astrotwo.core.hips import catalog_tiles, cube_planes  # noqa: E402


def test_t9_cube(service, cache):
    text = properties_text(dataproduct_type="cube", hips_cube_depth="3", hips_cube_firstframe="1",
                           data_cube_crpix3="1", data_cube_crval3="1.4204e9", data_cube_cdelt3="-1e5",
                           data_cube_bunit3="Hz")
    cube = read_service(serve_properties(service, "/cubo", text), cache=cache)
    planes = cube_planes(cube)
    # Asse ricalcolato nel test con astropy.wcs (WCS lineare a 1 asse, pixel da 0).
    from astropy.wcs import WCS

    w = WCS(naxis=1)
    w.wcs.crpix, w.wcs.crval, w.wcs.cdelt, w.wcs.cunit, w.wcs.ctype = [1], [1.4204e9], [-1e5], ["Hz"], ["FREQ"]
    expected = w.pixel_to_world_values(np.arange(3))
    assert planes.depth == 3 and planes.first_frame == 1 and planes.axis.unit == u.Hz
    assert np.allclose(planes.axis.value, expected, rtol=0, atol=1e-3)
    for plane in (0, 2):
        route = "/cubo/" + tile_path(3, 50, "fits", plane=plane)
        service.routes[route] = lambda request, p=plane: (200, "application/fits", fits_tile(100 + p))
    tile = fetch_tile(cube, 3, 50, plane=2, cache=cache)
    assert tile.plane == 2 and tile.url.endswith("Npix50_2.fits")
    assert np.array_equal(tile.data, fits.getdata(io.BytesIO(fits_tile(102))))
    assert fetch_tile(cube, 3, 50, cache=cache).url.endswith("Npix50.fits")  # piano 0 = senza suffisso
    for plane in (5, -1, 3):
        with pytest.raises(HiPSError) as err:
            fetch_tile(cube, 3, 50, plane=plane, cache=cache)
        assert err.value.code == "HIPS_CUBE_PLANE_INVALID" and err.value.details["depth"] == 3
    hp = HEALPix(nside=2 ** (3 + 6), order="nested")
    lon, lat = hp.healpix_to_lonlat([(50 << 12) + 7])
    got = pixel_values(cube, SkyCoord(lon, lat), plane=2, cache=cache)
    assert "piano 2" in got.description
    image = read_service(serve_properties(service), cache=cache)
    with pytest.raises(HiPSError) as err:
        fetch_tile(image, 3, 50, plane=1, cache=cache)
    assert err.value.code == "HIPS_CUBE_PLANE_INVALID"
    with pytest.raises(HiPSError) as err:
        cube_planes(image)
    assert err.value.code == "HIPS_TYPE_MISMATCH"
    bare = read_service(serve_properties(service, "/cubo2", properties_text(dataproduct_type="cube",
                                                                            hips_cube_depth="4")), cache=cache)
    plain = cube_planes(bare)
    assert plain.axis is None and plain.first_frame == 0 and plain.warnings == ()


METADATA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
  <RESOURCE>
    <COOSYS ID="sys" system="ICRS" epoch="J2000"/>
    <TABLE name="prova">
      <FIELD name="ident" datatype="char" arraysize="*" ucd="meta.id;meta.main"/>
      <FIELD name="RA" datatype="double" unit="deg" ucd="pos.eq.ra;meta.main" ref="sys"/>
      <FIELD name="DE" datatype="double" unit="deg" ucd="pos.eq.dec;meta.main" ref="sys"/>
      <FIELD name="mag" datatype="float" unit="mag" ucd="phot.mag;em.opt.V"/>
    </TABLE>
  </RESOURCE>
</VOTABLE>
"""


def tsv(rows, header="ident\tRA\tDE\tmag"):
    return "# Completezza: commento ignorato\n" + header + "\n" + "".join("\t".join(r) + "\n" for r in rows)


def test_progressive_catalog(service, cache):
    text = properties_text(dataproduct_type="catalog", hips_tile_format="tsv", hips_order="3", hips_tile_width=None)
    cat = read_service(serve_properties(service, "/cat", text), cache=cache)
    service.routes["/cat/metadata.xml"] = lambda request: (200, "text/xml", METADATA_XML)
    center = SkyCoord(45 * u.deg, 20 * u.deg)
    radius = 2 * u.deg
    # Albero sintetico: a ogni ordine una sorgente per tile che tocca il campo, fino all'ordine 1 (ordine 2 assente).
    expected = []
    for level in (0, 1):
        for index in HEALPix(nside=2 ** level, order="nested").cone_search_lonlat(45 * u.deg, 20 * u.deg, radius):
            lon, lat = HEALPix(nside=2 ** level, order="nested").healpix_to_lonlat([index])
            row = [f"S{level}_{index}", f"{lon[0].deg:.6f}", f"{lat[0].deg:.6f}", "" if level else "12.5"]
            expected.append(row[0])
            service.routes[f"/cat/{tile_path(level, int(index), 'tsv')}"] = \
                lambda request, r=row: (200, "text/tab-separated-values", tsv([r]))
    result = catalog_tiles(cat, center, radius, 3, cache=cache)
    table = result.table
    assert sorted(table.table["ident"]) == sorted(expected) and len(result.tiles) == len(expected)
    assert table.positions.lon == "RA" and table.positions.frame == "icrs" and table.body == "celestial"
    assert str(table.table["mag"].unit) == "mag" and table.table["mag"].mask.sum() == len(expected) - 1
    assert [t[0] for t in result.tiles] == sorted(t[0] for t in result.tiles)  # dall'ordine più basso
    # Ordine 2: richiesti solo i figli dei tile presenti all'ordine 1; nessuno presente → ordine 3 non richiesto.
    hp1 = set(HEALPix(nside=2, order="nested").cone_search_lonlat(45 * u.deg, 20 * u.deg, radius))
    asked2 = {int(r["path"].split("Npix")[1].split(".")[0]) for r in service.requests
              if r["path"].startswith("/cat/Norder2/")}
    assert asked2 and all((i >> 2) in hp1 for i in asked2)
    assert not any(r["path"].startswith("/cat/Norder3/") for r in service.requests)
    assert result.complete and "non ritagliate" in result.description
    again = catalog_tiles(cat, center, radius, 1, cache=cache)
    assert all(t[4] for t in again.tiles) and len(again.table.table) == len(expected)
    # Tile con colonne diverse da metadata.xml: una nuova richiesta, poi HIPS_BAD_TILE.
    bad_index = int(HEALPix(nside=1, order="nested").lonlat_to_healpix(45 * u.deg, 20 * u.deg))
    path = f"/cat/{tile_path(0, bad_index, 'tsv')}"
    service.routes[path] = lambda request: (200, "text/plain", tsv([["x", "1", "2", "3"]], header="a\tb\tc\td"))
    before = service.hits(path)
    with pytest.raises(HiPSError) as err:
        catalog_tiles(cat, center, radius, 1, cache=cache, refresh=True)
    assert err.value.code == "HIPS_BAD_TILE" and service.hits(path) - before == 2
    image = read_service(serve_properties(service), cache=cache)
    with pytest.raises(HiPSError) as err:
        catalog_tiles(image, center, radius, 1, cache=cache)
    assert err.value.code == "HIPS_TYPE_MISMATCH"
    nometa = read_service(serve_properties(service, "/cat2", text), cache=cache)
    with pytest.raises(HiPSError) as err:
        catalog_tiles(nometa, center, radius, 1, cache=cache)
    assert err.value.code == "HIPS_METADATA_INVALID"
