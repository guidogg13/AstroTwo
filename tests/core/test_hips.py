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
