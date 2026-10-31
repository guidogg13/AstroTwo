# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del ripiego sui mirror dei survey HiPS (``mdfiles/12-core-hips.md`` §3 "Ripiego sui mirror", T19, D12-9,
D12-10): server finti locali; un server "giù" è una porta chiusa (connessione rifiutata) o una risposta 5xx/429.
I test di rete in fondo verificano i mirror reali di ``MIRROR_FALLBACKS`` (non eseguiti nel commit)."""

import io
import json

import numpy as np
import pytest
from astropy.io import fits

from astrotwo.core import hips
from astrotwo.core.cache import NetworkTimeouts
from astrotwo.core.hips import (
    MIRROR_SWITCH_FAILURES,
    HiPSError,
    _server_order,
    add_hips,
    fetch_tile,
    tile_path,
)

HIPS_ID = "TEST/P/prova/r"
WIDTH = 64
DEAD = "http://127.0.0.1:9"  # porta chiusa: connessione rifiutata subito
FAST = NetworkTimeouts(connect=0.5, read=0.5)


def properties_text(**overrides) -> str:
    props = {"creator_did": f"ivo://{HIPS_ID}", "obs_title": "Survey di prova", "dataproduct_type": "image",
             "hips_version": "1.4", "hips_release_date": "2026-10-01T12:00Z", "hips_status": "public mirror",
             "hips_tile_format": "fits", "hips_order": "3", "hips_frame": "equatorial",
             "hips_tile_width": str(WIDTH)}
    props.update(overrides)
    return "\n".join(f"{k} = {v}" for k, v in props.items() if v is not None) + "\n"


def fits_tile(seed: int) -> bytes:
    buffer = io.BytesIO()
    fits.PrimaryHDU(np.random.default_rng(seed).normal(size=(WIDTH, WIDTH)).astype(np.float32)).writeto(buffer)
    return buffer.getvalue()


def serve(service, path, *, tiles=range(12), status=200, **props):
    """Server HiPS finto in ``path``: ``properties`` e i tile all'ordine 3 (``status`` diverso da 200 per i tile)."""
    text = properties_text(**props)
    service.routes[f"{path}/properties"] = lambda request: (200, "text/plain", text)
    for index in tiles:
        payload = fits_tile(index)
        service.routes[f"{path}/{tile_path(3, index, 'fits')}"] = (
            (lambda request, p=payload: (200, "application/fits", p)) if status == 200
            else (lambda request, s=status: (s, "text/plain", "guasto")))
    return service.url + path


def mocserver(service, monkeypatch, record):
    from astrotwo.core import vo_protocols as vo

    def route(request):
        found = [record] if request["params"].get("ID") == record["ID"] else []
        return 200, "application/json;charset=ISO-8859-1", json.dumps(found).encode("latin-1")

    service.routes["/MocServer/query"] = route
    monkeypatch.setattr(vo, "MOCSERVER_URL", service.url + "/MocServer/query")


def tile_hits(service, path):
    return sum(1 for r in service.requests if r["path"].startswith(path + "/Norder"))


def codes(notes):
    return [n[0] for n in notes]


def test_t19_server_order():
    order = _server_order("https://alasky.cds.unistra.fr/DSS/DSSColor/", [
        "https://alaskybis.cds.unistra.fr/DSS/DSSColor", "https://skies.esac.esa.int/DSSColor",
        "http://alaskybis.u-strasbg.fr/DSS/DSSColor", "https://skies.esac.esa.int/DSSColor/",
        "https://irsa.ipac.caltech.edu/data/hips/CDS/DSS2/color"])
    assert order == ("https://alasky.cds.unistra.fr/DSS/DSSColor", "https://skies.esac.esa.int/DSSColor",
                     "https://irsa.ipac.caltech.edu/data/hips/CDS/DSS2/color",
                     "https://alaskybis.cds.unistra.fr/DSS/DSSColor", "http://alaskybis.u-strasbg.fr/DSS/DSSColor")
    assert _server_order(None, ["https://alaskybis.unistra.fr/x", "https://example.org/x"]) == (
        "https://example.org/x", "https://alaskybis.unistra.fr/x")


def test_t19_primary_down_mocserver_mirror(service, cache, monkeypatch):
    mirror = serve(service, "/mirror")
    mocserver(service, monkeypatch, {"ID": HIPS_ID, "hips_service_url": DEAD + "/hips",
                                     "hips_service_url_1": [mirror], "dataproduct_type": "image"})
    got = add_hips(HIPS_ID, cache=cache, timeouts=FAST)
    assert got.base_url == DEAD + "/hips" and got.server == mirror
    assert got.servers.servers == (DEAD + "/hips", mirror)
    note = [w for w in got.warnings if w[0] == "HIPS_MIRROR_FALLBACK"]
    assert len(note) == 1 and note[0].params == {"reason": "network", "hips_id": HIPS_ID, "primary": DEAD + "/hips",
                                                 "mirror": mirror}
    sent = [r for r in service.requests if r["path"] == "/MocServer/query"][0]["params"]["fields"].split(",")
    assert "hips_service_url" in sent and "hips_service_url_1" in sent and "hips_service_url_9" in sent
    tile = fetch_tile(got, 3, 5, cache=cache, timeouts=FAST)
    assert tile.url.startswith(mirror) and tile.server == mirror
    assert got.servers.take_notes() == ()  # avviso già consegnato nel risultato: una volta sola


def test_t19_mocserver_down_cached_record_without_mirrors(service, cache, monkeypatch):
    """Record del MocServer in cache scritto prima dello sprint 10b (senza i campi dei mirror), MocServer giù:
    il principale dal record, i mirror dalla tabella interna."""
    from astrotwo.core import vo_protocols as vo

    table = serve(service, "/tabella")
    monkeypatch.setattr(hips, "MIRROR_FALLBACKS", {HIPS_ID: (table,)})
    monkeypatch.setattr(vo, "MOCSERVER_URL", DEAD + "/MocServer/query")
    params = vo._canonical({"ID": HIPS_ID, "get": "record", "fmt": "json", "fields": hips._LEGACY_RESOLVE_FIELDS})
    rows = cache.table(vo._CACHE_MODULE, vo._QUERY_TABLE, vo._QUERY_COLUMNS)
    record = json.dumps([{"ID": HIPS_ID, "hips_service_url": DEAD + "/hips"}]).encode("latin-1")
    rows.put(vo._cache_key("mocserver", "GET", vo.MOCSERVER_URL, params),
             {"protocol": "mocserver", "url": vo.MOCSERVER_URL, "params": "[]", "payload": record},
             origin=vo.MOCSERVER_URL, retrieved_at=hips.datetime(2026, 10, 20, tzinfo=hips.UTC))
    got = add_hips(HIPS_ID, cache=cache, timeouts=FAST)
    assert got.server == table and got.base_url == DEAD + "/hips"
    assert "FROM_CACHE" in codes(got.warnings) and "HIPS_MIRROR_FALLBACK" in codes(got.warnings)


def test_t19_mocserver_down_without_cache(service, cache, monkeypatch):
    from astrotwo.core import vo_protocols as vo

    table = serve(service, "/tabella")
    monkeypatch.setattr(vo, "MOCSERVER_URL", DEAD + "/MocServer/query")
    with pytest.raises(HiPSError) as err:  # fuori dalla tabella: come prima
        add_hips(HIPS_ID, cache=cache, timeouts=FAST)
    assert err.value.code == "MOCSERVER_UNAVAILABLE"
    monkeypatch.setattr(hips, "MIRROR_FALLBACKS", {HIPS_ID: (table,)})
    got = add_hips(HIPS_ID, cache=cache, timeouts=FAST)
    assert got.server == table and got.servers is None  # un solo server noto
    note = [w for w in got.warnings if w[0] == "HIPS_MIRROR_FALLBACK"][0]
    assert note.params == {"reason": "mocserver", "hips_id": HIPS_ID, "mirror": table}


@pytest.mark.parametrize(("status", "reason"), [(503, {"reason": "http_status", "status": 503}),
                                                (429, {"reason": "http_status", "status": 429})])
def test_t19_tile_switch_after_three_and_equivalence(service, cache, monkeypatch, status, reason):
    """Principale vivo con i tile in errore: 2 tile falliti non cambiano server, il terzo sì; il primo mirror ha un
    ordine diverso ed è scartato; i tile falliti prima del cambio restano in errore (li richiede il 41); refresh
    riparte dal principale; il tile già in cache dal principale resta valido (chiave indipendente dall'host)."""
    primary = serve(service, "/hips", tiles=range(5), status=status)
    serve(service, "/hips", tiles=[7])  # un tile buono sul principale
    different = serve(service, "/diverso", hips_order="4")
    good = serve(service, "/buono")
    monkeypatch.setattr(hips, "MIRROR_FALLBACKS", {HIPS_ID: (different, good)})
    got = add_hips(primary, cache=cache, timeouts=FAST)  # aggiunto da URL: mirror dalla tabella
    assert got.server == primary and got.servers.servers == (primary, different, good)
    cached_before = fetch_tile(got, 3, 7, cache=cache, timeouts=FAST)
    assert cached_before.url.startswith(primary)
    for index in range(MIRROR_SWITCH_FAILURES - 1):
        with pytest.raises(HiPSError) as err:
            fetch_tile(got, 3, index, cache=cache, timeouts=FAST)
        assert err.value.code == "SERVICE_ERROR" and got.server == primary
    third = fetch_tile(got, 3, 2, cache=cache, timeouts=FAST)
    assert third.url.startswith(good) and got.server == good and got.servers.switches == 1
    notes = got.servers.take_notes()
    assert codes(notes) == ["HIPS_MIRROR_REJECTED", "HIPS_MIRROR_FALLBACK"]
    assert notes[0].params == {"reason": "different", "hips_id": HIPS_ID, "mirror": different, "field": "hips_order",
                               "expected": "3", "found": "4"}
    assert notes[1].params == {"hips_id": HIPS_ID, "primary": primary, "mirror": good, **reason}
    assert got.servers.take_notes() == ()
    assert tile_hits(service, "/diverso") == 0  # scartato prima di chiedergli un tile
    again = fetch_tile(got, 3, 7, cache=cache, timeouts=FAST)  # dalla cache, anche dopo il cambio
    assert again.from_cache and again.url == cached_before.url and tile_hits(service, "/buono") == 1
    assert fetch_tile(got, 3, 0, cache=cache, timeouts=FAST).url.startswith(good)  # ora dal mirror
    fresh = add_hips(primary, cache=cache, refresh=True, timeouts=FAST)
    assert fresh.server == primary and fresh.servers.switches == 0


def test_t19_404_does_not_switch(service, cache, monkeypatch):
    primary = serve(service, "/hips", tiles=[])
    good = serve(service, "/buono")
    monkeypatch.setattr(hips, "MIRROR_FALLBACKS", {HIPS_ID: (good,)})
    got = add_hips(primary, cache=cache, timeouts=FAST)
    for index in range(MIRROR_SWITCH_FAILURES + 2):
        with pytest.raises(HiPSError) as err:
            fetch_tile(got, 3, index, cache=cache, timeouts=FAST)
        assert err.value.code == "HIPS_TILE_MISSING"
    assert got.server == primary and got.servers.failures == 0 and tile_hits(service, "/buono") == 0


def test_t19_success_resets_count(service, cache, monkeypatch):
    primary = serve(service, "/hips", tiles=range(4), status=503)
    serve(service, "/hips", tiles=[9])
    good = serve(service, "/buono")
    monkeypatch.setattr(hips, "MIRROR_FALLBACKS", {HIPS_ID: (good,)})
    got = add_hips(primary, cache=cache, timeouts=FAST)
    for index in (0, 1):
        with pytest.raises(HiPSError):
            fetch_tile(got, 3, index, cache=cache, timeouts=FAST)
    fetch_tile(got, 3, 9, cache=cache, timeouts=FAST)  # un tile riuscito azzera il conteggio
    for index in (2, 3):
        with pytest.raises(HiPSError):
            fetch_tile(got, 3, index, cache=cache, timeouts=FAST)
    assert got.server == primary and got.servers.failures == 2


def test_t19_all_servers_down(service, cache, monkeypatch):
    primary = serve(service, "/hips", status=503)
    monkeypatch.setattr(hips, "MIRROR_FALLBACKS", {HIPS_ID: (DEAD + "/mirror",)})
    got = add_hips(primary, cache=cache, timeouts=FAST)
    for index in range(MIRROR_SWITCH_FAILURES - 1):
        with pytest.raises(HiPSError):
            fetch_tile(got, 3, index, cache=cache, timeouts=FAST)
    for index in (2, 3):  # esaurito: ogni tile in errore dice quanti server sono stati provati
        with pytest.raises(HiPSError) as err:
            fetch_tile(got, 3, index, cache=cache, timeouts=FAST)
        assert err.value.code == "NET_TIMEOUT" and err.value.params["reason"] == "hips_servers"
        assert err.value.params["servers"] == 2 and err.value.params["tried"] == [primary, DEAD + "/mirror"]
        assert err.value.params["last"]["code"] == "SERVICE_ERROR"
    notes = got.servers.take_notes()
    assert codes(notes) == ["HIPS_MIRROR_REJECTED"] and notes[0].params["reason"] == "unreadable"


def test_t19_all_down_at_open(service, cache, monkeypatch):
    mocserver(service, monkeypatch, {"ID": HIPS_ID, "hips_service_url": DEAD + "/hips",
                                     "hips_service_url_1": DEAD + "/m1", "hips_service_url_2": DEAD + "/m2"})
    with pytest.raises(HiPSError) as err:
        add_hips(HIPS_ID, cache=cache, timeouts=FAST)
    assert err.value.code == "NET_TIMEOUT" and err.value.params["servers"] == 3


def test_t19_in_flight_failure_retried_on_new_server(service, cache, monkeypatch):
    """Un tile partito verso il server di prima e fallito dopo il cambio si riprova subito sul server in uso."""
    primary = serve(service, "/hips", status=503)
    good = serve(service, "/buono")
    monkeypatch.setattr(hips, "MIRROR_FALLBACKS", {HIPS_ID: (good,)})
    got = add_hips(primary, cache=cache, timeouts=FAST)
    state = got.servers
    assert state.failed(primary, {"reason": "network"}, cache=cache, timeouts=FAST) is None
    assert state.failed(primary, {"reason": "network"}, cache=cache, timeouts=FAST) is None
    assert state.failed(primary, {"reason": "network"}, cache=cache, timeouts=FAST) == good
    assert state.failed(primary, {"reason": "network"}, cache=cache, timeouts=FAST) == good  # in volo: riprova
    assert state.failures == 0 and state.switches == 1


def test_t19_legacy_tile_key_still_read(service, cache):
    """Tile salvato prima dello sprint 10b con la chiave dell'URL: si rilegge (D12-10)."""
    primary = serve(service, "/hips", tiles=[])
    got = add_hips(primary, cache=cache, timeouts=FAST)
    url = f"{primary}/{tile_path(3, 4, 'fits')}"
    cache.put("12", f"tile:{url}", fits_tile(4), origin=url, retrieved_at=hips.datetime(2026, 10, 18, tzinfo=hips.UTC))
    tile = fetch_tile(got, 3, 4, cache=cache, timeouts=FAST)
    assert tile.from_cache and tile.url == url


# =============================================================================
# Test di rete (non eseguiti nel commit, 02-convenzioni §8 punto 9): i mirror reali di MIRROR_FALLBACKS


@pytest.mark.network
@pytest.mark.parametrize(("hips_id", "mirror"), [(h, m) for h, ms in hips.MIRROR_FALLBACKS.items() for m in ms])
def test_network_mirror_fallbacks(cache, hips_id, mirror):
    """Ogni mirror della tabella: ``properties`` valido con il ``creator_did`` atteso e un tile scaricabile."""
    service = hips.read_service(mirror, cache=cache)
    assert service.hips_id == hips_id and service.frame == "equatorial" and service.tile_width == 512
    tile = fetch_tile(service, 3, 257, cache=cache)
    assert tile.url.startswith(mirror) and tile.data.shape[:2] == (512, 512)


@pytest.mark.network
def test_network_mirrors_equivalent():
    """I mirror di uno stesso survey servono lo stesso tile (verifica del 2026-10-31: SHA-256 uguali)."""
    import hashlib

    import requests

    for hips_id, mirrors in hips.MIRROR_FALLBACKS.items():
        digests = set()
        for mirror in mirrors:
            response = requests.get(f"{mirror}/{tile_path(3, 257, 'jpg')}", timeout=(10, 60))
            response.raise_for_status()
            digests.add(hashlib.sha256(response.content).hexdigest())
        assert len(digests) == 1, hips_id
