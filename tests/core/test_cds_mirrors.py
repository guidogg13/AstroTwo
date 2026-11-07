# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Ripiego sui mirror dei servizi del CDS (sprint B4): T27 del 14, T36 del 13, T27 del 05.

Servizi simulati con server HTTP locali (``FakeService`` di ``tests/conftest.py``): un "principale" e un "mirror";
nessuna rete. Gli attesi vengono dalla richiesta stessa (URL del server finto che ha risposto, centro convertito con
astropy), mai scritti a mano. I test con il marcatore ``network`` verificano gli URL veri dei mirror e degli archivi
originali (non eseguiti nel commit, ``--no-network``).
"""

from __future__ import annotations

import dataclasses

import astropy.units as u
import pytest
import pyvo
import requests
from astropy.coordinates import SkyCoord
from astropy.table import Table

import astrotwo.core.catalogs as cats
import astrotwo.core.vo_protocols as vo
from astrotwo.core.cache import NetworkTimeouts
from astrotwo.core.catalogs import CatalogsError, load_catalog
from astrotwo.core.vo_protocols import ServiceMirrors, VoProtocolsError, is_failover_error, tap_query
from tests.conftest import FakeService

FAST = NetworkTimeouts(connect=0.5, read=2.0)

VOTABLE = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>
<COOSYS ID="c" system="ICRS" epoch="J2000"/>
<TABLE><FIELD name="ra" datatype="double" unit="deg" ucd="pos.eq.ra;meta.main" ref="c"/>
<FIELD name="dec" datatype="double" unit="deg" ucd="pos.eq.dec;meta.main" ref="c"/>
<FIELD name="main_id" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>{rows}</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""
ERROR = """<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="ERROR">{text}</INFO></RESOURCE></VOTABLE>"""


def rows(n: int) -> str:
    return VOTABLE.format(rows="".join(f"<TR><TD>{10 + k}</TD><TD>{20 + k}</TD><TD>o{k}</TD></TR>"
                                       for k in range(n)))


def ok(n=2):
    return lambda request: (200, "application/x-votable+xml", rows(n))


def status(code, body="down", ctype="text/plain"):
    return lambda request: (code, ctype, body)


@pytest.fixture
def pair(monkeypatch):
    """Principale e mirror finti per la voce ``cds-simbad-tap`` (stato dei mirror azzerato da ``conftest``)."""
    primary, mirror = FakeService(), FakeService()
    entries = tuple(dataclasses.replace(e, url=primary.url + "/tap") if e.id == "cds-simbad-tap" else e
                    for e in vo.BUILTIN_SERVERS)
    monkeypatch.setattr(vo, "BUILTIN_SERVERS", entries)
    monkeypatch.setattr(vo, "SERVICE_MIRRORS", {"cds-simbad-tap": ServiceMirrors("simbad", "SIMBAD",
                                                                                  (mirror.url + "/tap",))})
    yield primary, mirror
    primary.close()
    mirror.close()


def query(adql="SELECT ra, dec, main_id FROM basic", **kw):
    return tap_query("cds-simbad-tap", adql, timeouts=FAST, **kw)


# =============================================================================
# T27 del 14 — cause del cambio, avviso, stato di sessione, cache, tutti giù
# =============================================================================


@pytest.mark.parametrize("primary_route, reason, code", [
    (status(503), "http_status", 503),
    (status(429), "http_status", 429),
    (status(503, ERROR.format(text="maintenance"), "application/x-votable+xml"), "http_status", 503),
    (lambda r: (200, "text/html", "<html><body>Service unavailable</body></html>"), "invalid_response", None),
])
def test_t27_primary_failure_switches_to_mirror(pair, cache, primary_route, reason, code):
    primary, mirror = pair
    primary.routes["/tap/sync"] = primary_route
    mirror.routes["/tap/sync"] = ok(3)
    result = query(cache=cache)
    assert result.table.rows == 3 and result.request.url == mirror.url + "/tap/sync"
    assert result.table.origin == mirror.url + "/tap/sync"  # provenienza = server che ha risposto
    assert result.request.arguments["url"] == "cds-simbad-tap"  # argomenti registrati invariati
    warning = next(w for w in result.warnings if w[0] == "SERVICE_MIRROR_FALLBACK")
    assert warning.params["reason"] == reason and warning.params.get("status") == code
    assert (warning.params["primary"], warning.params["mirror"]) == (primary.url + "/tap", mirror.url + "/tap")
    assert primary.hits("/tap/sync") == 1 and mirror.hits("/tap/sync") == 1


def test_t27_connection_refused_switches_once_and_stays(pair, cache):
    primary, mirror = pair
    primary.routes["/tap/sync"] = status(503)
    mirror.routes["/tap/sync"] = ok(2)
    first = query(cache=cache)
    assert "SERVICE_MIRROR_FALLBACK" in dict(first.warnings)
    # Richiesta diversa: subito al mirror (servizio in uso per la sessione), nessun nuovo avviso.
    second = query("SELECT ra, dec, main_id FROM basic WHERE ra > 0", cache=cache)
    assert "SERVICE_MIRROR_FALLBACK" not in dict(second.warnings) and primary.hits("/tap/sync") == 1
    assert vo.current_server("simbad") == 1
    # Principale di nuovo su: refresh=True riparte da lì e il servizio torna al principale.
    primary.routes["/tap/sync"] = ok(5)
    again = query("SELECT ra, dec, main_id FROM basic WHERE ra > 0", cache=cache, refresh=True)
    assert again.request.url == primary.url + "/tap/sync" and again.table.rows == 5
    assert vo.current_server("simbad") == 0


def test_t27_principal_closed_connection_error(pair, cache):
    primary, mirror = pair
    mirror.routes["/tap/sync"] = ok(1)
    primary.close()
    result = query(cache=cache)
    assert result.request.url.startswith(mirror.url)
    assert next(w for w in result.warnings if w[0] == "SERVICE_MIRROR_FALLBACK").params["reason"] == "network"


def test_t27_no_switch_for_404_adql_or_empty_result(pair, cache):
    primary, mirror = pair
    mirror.routes["/tap/sync"] = ok(2)
    # 404: il server è vivo (nessuna rotta: "not found").
    with pytest.raises(VoProtocolsError) as err:
        query(cache=cache)
    assert err.value.code == "SERVICE_ERROR" and err.value.params["status"] == 404
    # ADQL rifiutata dal servizio (HTTP 400 con VOTable d'errore).
    primary.routes["/tap/sync"] = status(400, ERROR.format(text="Unknown table basicx"), "application/x-votable+xml")
    with pytest.raises(VoProtocolsError) as err:
        query("SELECT * FROM basicx", cache=cache)
    assert err.value.code == "ADQL_INVALID"
    # Nessun risultato: è un risultato.
    primary.routes["/tap/sync"] = ok(0)
    empty = query("SELECT * FROM basic WHERE 1 = 0", cache=cache)
    assert empty.table.rows == 0 and empty.request.url.startswith(primary.url)
    assert mirror.hits("/tap/sync") == 0 and vo.current_server("simbad") == 0


def test_t27_all_down_counts_servers_and_stale_copy(pair, cache):
    primary, mirror = pair
    primary.routes["/tap/sync"] = ok(4)
    fresh = query(cache=cache)  # risposta del principale in cache
    primary.routes["/tap/sync"] = status(503)
    mirror.routes["/tap/sync"] = status(502)
    with pytest.raises(VoProtocolsError) as err:
        query("SELECT * FROM basic WHERE ra > 1", cache=cache)
    assert err.value.code == "NET_TIMEOUT" and err.value.params["reason"] == "service_servers"
    assert err.value.params["servers"] == 2 and err.value.params["tried"] == [primary.url + "/tap", mirror.url + "/tap"]
    assert err.value.params["last"]["code"] == "SERVICE_ERROR"
    # Copia vecchia in cache: con la rete giù (refresh=True) si usa, dichiarata; mai con use_stale_cache=False.
    primary.close()
    mirror.close()
    vo.reset_mirror_state()
    stale = query(cache=cache, refresh=True)
    assert stale.request.from_cache and stale.table.rows == fresh.table.rows
    assert dict(stale.warnings)["FROM_CACHE"] and stale.warnings[0].params["reason"] == "network_cached"
    with pytest.raises(VoProtocolsError) as err:
        query(cache=cache, refresh=True, use_stale_cache=False)
    assert err.value.params["reason"] == "service_servers"


def test_t27_mirror_cache_found_before_network(pair, cache):
    primary, mirror = pair
    primary.routes["/tap/sync"] = status(503)
    mirror.routes["/tap/sync"] = ok(2)
    query(cache=cache)
    vo.reset_mirror_state()  # nuova sessione: il servizio riparte dal principale
    hits = primary.hits("/tap/sync")
    again = query(cache=cache)
    assert again.request.from_cache and again.request.url.startswith(mirror.url)
    assert primary.hits("/tap/sync") == hits  # la copia del mirror in cache basta: nessuna richiesta


def test_t27_written_url_has_no_fallback(pair, cache):
    primary, mirror = pair
    primary.routes["/tap/sync"] = status(503)
    mirror.routes["/tap/sync"] = ok(2)
    with pytest.raises(VoProtocolsError) as err:
        tap_query(primary.url + "/tap", "SELECT * FROM basic", cache=cache, timeouts=FAST)
    assert err.value.code == "SERVICE_ERROR" and mirror.hits("/tap/sync") == 0


def test_t27_is_failover_error_rules():
    def err(code, **params):  # solo codice e params: la regola non guarda il testo (nessuna voce da controllare)
        exc = VoProtocolsError.__new__(VoProtocolsError)
        exc.code, exc.message, exc.params = code, "x", params
        return exc

    assert is_failover_error(err("NET_TIMEOUT", reason="url"))
    assert not is_failover_error(err("NET_TIMEOUT", reason="async_deadline"))
    assert is_failover_error(err("SERVICE_ERROR", reason="http_status", status=500))
    assert is_failover_error(err("SERVICE_ERROR", reason="http_status", status=429))
    assert not is_failover_error(err("SERVICE_ERROR", reason="http_status", status=404))
    assert not is_failover_error(err("SERVICE_ERROR", reason="service_rejected"))
    assert is_failover_error(err("VOTABLE_INVALID", reason="unreadable_response"))
    for code in ("ADQL_INVALID", "AUTH_REQUIRED", "QUERY_CANCELLED", "MAX_ROWS_INVALID"):
        assert not is_failover_error(err(code))
    assert is_failover_error(requests.exceptions.ConnectionError("refused"))
    assert is_failover_error(pyvo.dal.DALServiceError("down"))
    assert is_failover_error(pyvo.dal.DALServiceError("bad gateway", code=502))
    assert not is_failover_error(pyvo.dal.DALServiceError("not found", code=404))


# --- Puntatore SIMBAD: regione (astroquery) e magnitudini (TAP) dallo stesso servizio ---------------------------


FLUX = """<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/><TABLE>
<FIELD name="filter" datatype="char" arraysize="*"/><FIELD name="flux" datatype="float"/>
<FIELD name="flux_err" datatype="float"/><FIELD name="system" datatype="char" arraysize="1"/>
<FIELD name="qual" datatype="char" arraysize="1"/><FIELD name="bibcode" datatype="char" arraysize="19"/>
<FIELD name="description" datatype="char" arraysize="*"/><FIELD name="unit" datatype="char" arraysize="*"/>
<DATA><TABLEDATA><TR><TD>V</TD><TD>0.03</TD><TD></TD><TD>V</TD><TD>C</TD><TD></TD><TD>V</TD><TD>mag</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""


def simbad_region_table():
    t = Table(rows=[("* alf Lyr", 279.2347, 38.7837, "dS*", 2500)], names=("main_id", "ra", "dec", "otype", "nbref"),
              dtype=(str, float, float, str, int))
    t["ra"].unit = t["dec"].unit = u.deg
    return t


def test_t27_simbad_pointer_falls_back_with_one_warning(pair, cache, monkeypatch):
    primary, mirror = pair
    primary.routes["/tap/sync"] = status(503)
    mirror.routes["/tap/sync"] = lambda r: (200, "application/x-votable+xml", FLUX)
    asked = []

    def region(ra, dec, radius_deg, timeouts, server=None):
        asked.append(server)
        if server == primary.url.split("//")[1]:
            raise requests.exceptions.ConnectionError("CDS down")
        return simbad_region_table(), mirror.url + "/tap"

    monkeypatch.setattr(vo, "_query_simbad_region", region)
    found = vo.simbad_pointer(SkyCoord(279.2347 * u.deg, 38.7837 * u.deg), 10 * u.arcsec, cache=cache, timeouts=FAST)
    assert asked == [primary.url.split("//")[1], mirror.url.split("//")[1]]
    assert found.object.main_id == "* alf Lyr" and "mirror di Harvard" not in found.source  # URL finto, non Harvard
    assert found.request.url == mirror.url + "/tap"
    assert found.magnitudes_request.url == mirror.url + "/tap/sync" and primary.hits("/tap/sync") == 0
    assert [w[0] for w in found.warnings].count("SERVICE_MIRROR_FALLBACK") == 1
    assert found.object.magnitudes[0].system == "Vega"
    # Un 4xx della regione non fa cambiare server.
    vo.reset_mirror_state()

    def bad(ra, dec, radius_deg, timeouts, server=None):
        raise pyvo.dal.DALServiceError("bad request", code=400)

    monkeypatch.setattr(vo, "_query_simbad_region", bad)
    with pytest.raises(VoProtocolsError) as err:
        vo.simbad_pointer(SkyCoord(1 * u.deg, 2 * u.deg), 10 * u.arcsec, cache=cache, timeouts=FAST)
    assert err.value.code == "SERVICE_ERROR" and err.value.params["status"] == 400


def test_t27_simbad_source_names_the_harvard_mirror():
    assert vo._simbad_label("https://simbad.harvard.edu/simbad/sim-tap") == "SIMBAD (mirror di Harvard)"
    assert vo._simbad_label("https://simbad.cds.unistra.fr/simbad/sim-tap") == "SIMBAD (CDS)"


def test_t27_real_table_of_mirrors_is_verified_and_ordered(monkeypatch):
    """La voce vera di SIMBAD (la tabella è svuotata da ``conftest`` nei test senza rete): solo il mirror verificato."""
    real = vo._SIMBAD_STATE
    assert (real.service, real.label, real.mirrors) == ("simbad", "SIMBAD",
                                                         ("https://simbad.harvard.edu/simbad/sim-tap",))
    monkeypatch.setattr(vo, "SERVICE_MIRRORS", {"cds-simbad-tap": real})
    assert vo.service_servers("cds-simbad-tap") == ("https://simbad.cds.unistra.fr/simbad/sim-tap",
                                                    "https://simbad.harvard.edu/simbad/sim-tap")
    assert vo.service_servers("cds-vizier-tap") == ("https://tapvizier.cds.unistra.fr/TAPVizieR/tap",)
    assert vo.SIMBAD_SERVERS == ("simbad.cds.unistra.fr", "simbad.harvard.edu")
    # Prima i mirror fuori da Strasburgo (D14-14 c), il principale sempre primo.
    monkeypatch.setattr(vo, "SERVICE_MIRRORS", {"cds-simbad-tap": ServiceMirrors(
        "simbad", "SIMBAD", ("https://alaskybis.cds.unistra.fr/x", "https://simbad.harvard.edu/simbad/sim-tap"))})
    assert vo.service_servers("cds-simbad-tap")[1:] == ("https://simbad.harvard.edu/simbad/sim-tap",
                                                        "https://alaskybis.cds.unistra.fr/x")
    assert {k: (a.server, a.table) for k, a in cats.ORIGINAL_ARCHIVES.items()} == {
        "I/355/gaiadr3": ("esa-gaia-tap", "gaiadr3.gaia_source"), "II/246/out": ("nasa-irsa-tap", "fp_psc")}


# --- MocServer: nessuna copia fuori da Strasburgo ---------------------------------------------------------------


def test_t27_mocserver_down_uses_cache_or_clear_message(service, cache, monkeypatch):
    monkeypatch.setattr(vo, "MOCSERVER_URL", service.url + "/MocServer/query")
    service.routes["/MocServer/query"] = lambda r: (200, "application/json", '[{"ID": "CDS/I/355/gaiadr3"}]')
    first = vo.vizier_collections(cache=cache)
    service.routes["/MocServer/query"] = status(503)
    with pytest.raises(VoProtocolsError) as err:
        vo.vizier_collections(cache=cache, refresh=True)  # 503: nessuna copia usata per un 5xx (regola del 14)
    assert err.value.code == "NET_TIMEOUT" and err.value.params["reason"] == "mocserver_no_mirror"
    assert err.value.params["cause"]["code"] == "SERVICE_ERROR"
    service.close()
    cached = vo.vizier_collections(cache=cache, refresh=True, timeouts=FAST)
    assert cached.request.from_cache and cached.records == first.records
    assert cached.warnings[0].params["reason"] == "network_cached"


def test_t27_mocserver_down_without_cache(cache, monkeypatch):
    dead = FakeService()
    url = dead.url
    dead.close()
    monkeypatch.setattr(vo, "MOCSERVER_URL", url + "/MocServer/query")
    with pytest.raises(VoProtocolsError) as err:
        vo.vizier_collections(cache=cache, timeouts=FAST)
    assert err.value.params["reason"] == "mocserver_no_mirror" and err.value.params["cause"]["code"] == "NET_TIMEOUT"


# =============================================================================
# T36 del 13 — Gaia DR3 e 2MASS dagli archivi originali
# =============================================================================

SCHEMA = """<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/><TABLE>
<FIELD name="column_name" datatype="char" arraysize="*"/><FIELD name="ucd" datatype="char" arraysize="*"/>
<DATA><TABLEDATA><TR><TD>ra</TD><TD>pos.eq.ra;meta.main</TD></TR><TR><TD>dec</TD><TD>pos.eq.dec;meta.main</TD></TR>
<TR><TD>phot_g_mean_mag</TD><TD>phot.mag;em.opt</TD></TR></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""
ARCHIVE = """<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>{coosys}<TABLE>
<FIELD name="ra" datatype="double" unit="deg" ucd="pos.eq.ra;meta.main"{ref}/>
<FIELD name="dec" datatype="double" unit="deg" ucd="pos.eq.dec;meta.main"{ref}/>
<FIELD name="phot_g_mean_mag" datatype="float" unit="mag" ucd="phot.mag;em.opt"/>
<DATA><TABLEDATA>{rows}</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""
GAIA_COOSYS = '<COOSYS ID="g" system="ICRS" epoch="J2016.0"/>'


def archive_tap(coosys: str, n: int = 3):
    def tap(request):
        q = request["params"]["QUERY"]
        if "TAP_SCHEMA.columns" in q:
            return 200, "application/x-votable+xml", SCHEMA
        count = 0 if "TOP 0" in q else n
        body = "".join(f"<TR><TD>{56.75 + 0.001 * k}</TD><TD>{24.11 + 0.001 * k}</TD><TD>{9 + k}</TD></TR>"
                       for k in range(count))
        return 200, "application/x-votable+xml", ARCHIVE.format(coosys=coosys, ref=' ref="g"' if coosys else "",
                                                               rows=body)
    return tap


@pytest.fixture
def archives(monkeypatch):
    """TAPVizieR, archivio Gaia e IRSA finti; gruppo fisso con gli archivi originali."""
    vizier, gaia, irsa = FakeService(), FakeService(), FakeService()
    urls = {"cds-vizier-tap": vizier.url + "/viz", "esa-gaia-tap": gaia.url + "/tap", "nasa-irsa-tap": irsa.url + "/TAP"}
    monkeypatch.setattr(vo, "BUILTIN_SERVERS", tuple(dataclasses.replace(e, url=urls[e.id]) if e.id in urls else e
                                                     for e in vo.BUILTIN_SERVERS))
    monkeypatch.setattr(cats, "FIXED_COLLECTIONS", tuple(  # gruppo fisso con gli archivi veri (tolti da conftest)
        dataclasses.replace(c, archive=cats.ORIGINAL_ARCHIVES.get(c.id)) for c in cats.FIXED_COLLECTIONS))
    gaia.routes["/tap/sync"] = archive_tap(GAIA_COOSYS)
    irsa.routes["/TAP/sync"] = archive_tap("")
    yield vizier, gaia, irsa
    for s in (vizier, gaia, irsa):
        s.close()


CENTER = SkyCoord(56.75 * u.deg, 24.1167 * u.deg)


def test_t36_gaia_from_the_esa_archive(archives, cache):
    vizier, gaia, irsa = archives
    vizier.routes["/viz/sync"] = status(503)
    table = load_catalog("I/355/gaiadr3", region=(CENTER, 1 * u.arcmin), max_rows=500, cache=cache, timeouts=FAST)
    queries = [r["params"]["QUERY"] for r in gaia.requests]
    assert "TAP_SCHEMA.columns" in queries[0] and "gaiadr3.gaia_source" in queries[0]
    assert queries[1] == "SELECT TOP 0 ra, dec FROM gaiadr3.gaia_source"
    expected = (f"SELECT * FROM gaiadr3.gaia_source WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), "
                f"CIRCLE('ICRS', {float(CENTER.ra.deg)!r}, {float(CENTER.dec.deg)!r}, "
                f"{float((1 * u.arcmin).to_value(u.deg))!r}))")
    assert queries[2] == expected and gaia.requests[2]["params"]["MAXREC"] == "500"  # stessa regione e max_rows
    assert (table.positions.lon, table.positions.lat, table.positions.frame, table.positions.epoch) == (
        "ra", "dec", "icrs", "J2016.0")
    assert table.table.colnames == ["ra", "dec", "phot_g_mean_mag"]  # nomi dell'archivio, non rinominati
    assert table.origin == gaia.url + "/tap/sync"
    note = next(w for w in table.warnings if w[0] == "CATALOG_ORIGINAL_ARCHIVE")
    assert note.params["table"] == "gaiadr3.gaia_source" and note.params["cause"]["code"] == "SERVICE_ERROR"
    assert "nomi delle colonne dell'archivio" in table.history[0]


def test_t36_2mass_from_irsa_without_coosys(archives, cache):
    vizier, gaia, irsa = archives
    vizier.close()  # connessione rifiutata
    table = load_catalog("II/246/out", region=(CENTER, 2 * u.arcmin), cache=cache, timeouts=FAST)
    last = irsa.requests[-1]["params"]["QUERY"]
    assert last.startswith("SELECT * FROM fp_psc WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', ")
    assert table.positions is None or table.positions.frame is None  # sistema non dichiarato: mai assunto
    region = next(w for w in table.warnings if w[0] == "REGION")
    assert region.params["reason"] == "archive_icrs_circle" and region.params["archive"] == "IRSA (NASA/IPAC)"
    assert "CATALOG_ORIGINAL_ARCHIVE" in dict(table.warnings) and table.origin.startswith(irsa.url)


def test_t36_no_archive_for_404_or_adql(archives, cache):
    vizier, gaia, irsa = archives
    vizier.routes["/viz/sync"] = status(404)
    with pytest.raises(VoProtocolsError) as err:
        load_catalog("I/355/gaiadr3", region=(CENTER, 1 * u.arcmin), cache=cache, timeouts=FAST)
    assert err.value.code == "SERVICE_ERROR"
    vizier.routes["/viz/sync"] = status(400, ERROR.format(text="no such table"), "application/x-votable+xml")
    with pytest.raises(CatalogsError) as err:
        load_catalog("I/355/gaiadr3", cache=cache, timeouts=FAST)
    assert err.value.code == "CATALOG_UNKNOWN"
    assert gaia.requests == [] and irsa.requests == []


def test_t36_everything_down_and_other_identifiers(archives, cache):
    vizier, gaia, irsa = archives
    vizier.routes["/viz/sync"] = status(503)
    gaia.routes["/tap/sync"] = status(502)
    with pytest.raises(CatalogsError) as err:
        load_catalog("I/355/gaiadr3", region=(CENTER, 1 * u.arcmin), cache=cache, timeouts=FAST)
    assert err.value.code == "NET_TIMEOUT" and err.value.params["reason"] == "catalog_servers"
    assert err.value.params["servers"] == 2 and err.value.params["tried"] == [vizier.url + "/viz", gaia.url + "/tap"]
    with pytest.raises(CatalogsError) as err:
        load_catalog("I/239/hip_main", region=(CENTER, 1 * u.arcmin), cache=cache, timeouts=FAST)
    assert err.value.params["reason"] == "vizier_no_mirror" and err.value.params["url"] == vizier.url + "/viz"
    assert "Query ADQL" in err.value.message


# =============================================================================
# T27 del 05 — refresh del comando e catalog.load_region con l'archivio senza sistema
# =============================================================================


def test_t27_command_refresh_field_and_declaration(pair, cache):
    from astrotwo.core.commands import Command, RequestedBy, Workspace, default_registry

    primary, mirror = pair
    primary.routes["/tap/sync"] = ok(2)
    registry = default_registry(cache=cache)
    ws = Workspace()
    params = {"service": primary.url + "/tap", "url": None, "adql": "SELECT ra, dec, main_id FROM basic"}
    _, first = registry.run(Command("catalog.tap_query", 1, params), ws)
    assert first.status == "ok"
    cmd = Command("catalog.tap_query", 1, params, RequestedBy("history"), refresh=True)
    registered, fresh = registry.run(cmd, ws)
    assert fresh.status == "ok" and registered.refresh and registered.to_json()["refresh"] is True
    assert not any(w.code == "FROM_CACHE" for w in fresh.warnings) and primary.hits("/tap/sync") == 2
    assert next(w for w in fresh.warnings if w.code == "DATA_REFRESHED").params == {"reason": "fresh"}
    assert "refresh" not in Command("catalog.tap_query", 1, params).to_json()
    assert Command.from_json(registered.to_json()).refresh is True
    primary.close()
    _, stale = registry.run(cmd, ws)
    assert next(w for w in stale.warnings if w.code == "DATA_REFRESHED").params == {"reason": "cache_used"}
    _, wrong = registry.run(Command("view.set_center", 1, {}, refresh=True), ws)
    assert wrong.error.code == "COMMAND_PARAMETER_INVALID"
    assert wrong.error.params["reason"] == "refresh_not_network" and wrong.error.params["parameter"] == "refresh"


def test_t27_load_region_from_irsa_asks_for_columns(archives, cache):
    from astrotwo.core.commands import Command, Workspace, default_registry, sky_json
    from astrotwo.core.coordinates_wcs import SkyFrame

    vizier, gaia, irsa = archives
    vizier.routes["/viz/sync"] = status(503)
    registry = default_registry(cache=cache)
    center = sky_json(SkyFrame(CENTER))
    center["epoch_reason"] = center.get("epoch_reason") or "posizione del test senza epoca"
    _, result = registry.run(Command("catalog.load_region", 1, {
        "catalog": "II/246/out", "center": center, "radius": {"value": 1.0, "unit": "arcmin"}}), Workspace())
    assert result.status == "ok", result.error
    codes = [w.code for w in result.warnings]
    assert "CATALOG_ORIGINAL_ARCHIVE" in codes and "POSITION_COLUMNS_REQUIRED" in codes
    assert result.provenance[0]["origin"].startswith(irsa.url)
    assert result.network_fingerprint[0]["origin"].startswith(irsa.url)


# =============================================================================
# Test di rete (marcatore ``network``, non nel commit): URL veri del 2026-11-07
# =============================================================================


@pytest.mark.network
def test_network_simbad_harvard_mirror(cache):
    url = "https://simbad.harvard.edu/simbad/sim-tap"
    header = tap_query(url, "SELECT TOP 0 ra, dec FROM basic", cache=cache, refresh=True)
    assert header.table.positions.frame == "icrs" and header.table.positions.epoch == "J2000"
    m31 = tap_query(url, "SELECT main_id, ra, dec FROM basic WHERE main_id = 'M  31'", cache=cache, refresh=True)
    row = m31.table.table[0]
    assert row["ra"] == pytest.approx(10.684708333, abs=1e-6) and row["dec"] == pytest.approx(41.26875, abs=1e-6)


@pytest.mark.network
def test_network_original_archives_declare_positions(cache):
    gaia = tap_query("esa-gaia-tap", "SELECT TOP 0 ra, dec FROM gaiadr3.gaia_source", cache=cache, refresh=True)
    assert (gaia.table.positions.frame, gaia.table.positions.epoch) == ("icrs", "J2016.0")
    irsa = tap_query("nasa-irsa-tap", "SELECT TOP 0 ra, dec FROM fp_psc", cache=cache, refresh=True)
    assert irsa.table.positions is None or irsa.table.positions.frame is None  # l'IRSA non dichiara il sistema
    alcyone = tap_query("nasa-irsa-tap", "SELECT designation FROM fp_psc WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), "
                        "CIRCLE('ICRS', 56.871152, 24.105136, 0.0003))", cache=cache, refresh=True)
    assert "03472908+2406184" in [str(d) for d in alcyone.table.table["designation"]]


@pytest.mark.network
def test_network_vizier_mirrors_have_no_tap():
    """I mirror ufficiali di VizieR non offrono TAPVizieR (verifica del 2026-11-07): se uno lo offrisse, il 14 va
    aggiornato con una nuova verifica (D14-14 b)."""
    for host in ("vizier.cfa.harvard.edu", "vizier.idia.ac.za"):
        response = requests.get(f"https://{host}/TAPVizieR/tap/capabilities", timeout=(10, 30))
        assert response.status_code == 404
