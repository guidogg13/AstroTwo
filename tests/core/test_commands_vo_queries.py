# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""``catalog.cone_search``, ``catalog.tap_query``, ``vo.add_server``, ``vo.remove_server`` del 05 (sprint B3,
decisioni del proprietario del 2026-11-06): T26 del ``05-comandi-sessione.md``.

Servizi SCS e TAP simulati con il server HTTP locale dei test del 14 (nessuna rete); i parametri attesi della cone
search sono ricalcolati con astropy, le righe attese lette dallo stesso VOTable con astropy, mai scritte a mano.
"""

from __future__ import annotations

import dataclasses
import io
import threading
import time

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.io.votable import parse as parse_votable

import astrotwo.core.vo_protocols as vo
from astrotwo.core.commands import CancelToken, Command, RequestedBy, Session, default_registry
from tests.core.test_vo_protocols import tap_sync_route, uws_service, votable_route, votable_text


def run(session, name, requested_by=RequestedBy("menu"), /, cancel=None, **params):
    return session.run(Command(name, 1, params, requested_by), cancel)


@pytest.fixture
def session(cache):
    return Session(default_registry(cache=cache))


@pytest.fixture
def listed(service, monkeypatch):
    """Voci SCS e TAP dell'elenco del 14 dirottate sul servizio simulato (stessi identificativi e nomi)."""
    urls = {"nasa-irsa-allwise-scs": service.url + "/scs?table=t", "esa-gaia-tap": service.url + "/tap"}
    entries = tuple(dataclasses.replace(e, url=urls.get(e.id, e.url)) for e in vo.BUILTIN_SERVERS)
    monkeypatch.setattr(vo, "BUILTIN_SERVERS", entries)
    return service


def sky(lon, lat, frame="icrs", epoch=None):
    return {"lon": {"value": lon, "unit": "deg"}, "lat": {"value": lat, "unit": "deg"}, "frame": frame,
            "epoch": epoch, "epoch_reason": None if epoch else "epoca non dichiarata (test)"}


def rows(session, layer_id):
    return [tuple(r) for r in session.workspace.state.layer(layer_id).data.table.as_array().tolist()]


def expected_rows(text):
    table = parse_votable(io.BytesIO(text.encode())).get_first_table().to_table()
    return [tuple(r) for r in table.as_array().tolist()]


NO_COOSYS = votable_text(5).replace('<COOSYS ID="sys" system="ICRS" epoch="J2016.0"/>', "").replace(
    ' ref="sys"', "")


# =============================================================================
# Cone search: voce dell'elenco e URL, centro con frame ed epoca, troncamento


def test_t26_cone_search_listed_entry(session, listed):
    listed.routes["/scs"] = votable_route(votable_text(5))
    result = run(session, "catalog.cone_search", service="nasa-irsa-allwise-scs",
                 center=sky(120.0, 30.0, "galactic", "J2000.0"), radius={"value": 10.0, "unit": "arcsec"})
    assert result.status == "ok", result.error
    params = listed.requests[-1]["params"]
    icrs = SkyCoord(120.0 * u.deg, 30.0 * u.deg, frame="galactic").icrs  # conversione ricalcolata con astropy
    assert np.isclose(float(params["RA"]), icrs.ra.deg, rtol=0, atol=1e-9)
    assert np.isclose(float(params["DEC"]), icrs.dec.deg, rtol=0, atol=1e-9)
    assert np.isclose(float(params["SR"]), (10 * u.arcsec).to_value(u.deg), rtol=1e-12)
    entry = session.history.entries[-1]
    # URL risolto dall'elenco e scritto nel comando registrato; epoca del centro conservata
    assert entry.command.parameters["url"] == listed.url + "/scs?table=t"
    assert entry.command.parameters["center"]["epoch"] == "J2000.0"
    assert entry.command.parameters["max_rows"] == 100_000  # D14-5
    layer = session.workspace.state.layer(result.layers_created[0])
    assert layer.kind == "catalog" and layer.name == "IRSA AllWISE (sorgenti) · cone search"
    assert layer.source == listed.url + "/scs?table=t"
    assert rows(session, layer.id) == expected_rows(votable_text(5))
    query = result.values["query"]
    assert query["protocol"] == "scs" and query["service"] == "nasa-irsa-allwise-scs"
    assert query["service_name"] == "IRSA AllWISE (sorgenti)" and query["url"] == listed.url + "/scs?table=t"
    assert query["params"]["RA"] == params["RA"] and query["rows"] == 5 and query["truncated"] is False
    assert query["from_cache"] is False and query["retrieved_at"].endswith("+00:00")
    assert result.values["positions"]["frame"] == "icrs" and result.values["positions"]["epoch"] == "J2016.0"
    assert result.provenance[0]["origin"] == listed.url + "/scs?table=t"
    assert result.network_fingerprint and result.network_fingerprint[0]["rows"] == 5
    assert not [w for w in result.warnings if w.code == "POSITION_COLUMNS_REQUIRED"]


def test_t26_cone_search_url_truncation_and_columns(session, service):
    service.routes["/scs"] = votable_route(votable_text(8))
    url = service.url + "/scs"
    result = run(session, "catalog.cone_search", service=url, center=sky(10.0, -3.0),
                 radius={"value": 1.0, "unit": "arcmin"}, max_rows=3)
    assert result.status == "ok", result.error
    assert session.history.entries[-1].command.parameters["url"] == url
    assert result.values["query"]["truncated"] is True and result.values["query"]["rows"] == 3
    assert result.values["query"]["service_name"] is None
    assert session.workspace.state.layer(result.layers_created[0]).name == "127.0.0.1:" + url.split(":")[2].split(
        "/")[0] + " · cone search"
    limit = [w for w in result.warnings if w.code == "ROW_LIMIT_EXCEEDED"]
    assert limit and limit[0].params == {"reason": "cut", "received": 8, "max_rows": 3}
    # VOTable senza COOSYS: colonne da UCD ma sistema non dichiarato → da confermare, mai assunto
    service.routes["/scs"] = votable_route(NO_COOSYS)
    result = run(session, "catalog.cone_search", service=url, center=sky(10.0, -2.0),
                 radius={"value": 1.0, "unit": "arcmin"})
    assert result.status == "ok", result.error
    assert result.values["positions"]["frame"] is None
    assert [w for w in result.warnings if w.code == "POSITION_COLUMNS_REQUIRED"]


def test_t26_cone_search_errors(session, listed):
    before = len(session.workspace.state.layers)
    wrong = run(session, "catalog.cone_search", service="esa-gaia-tap", center=sky(10.0, -3.0),
                radius={"value": 1.0, "unit": "arcmin"})
    assert wrong.status == "error" and wrong.error.code == "SERVER_UNKNOWN"
    assert wrong.error.params["reason"] == "wrong_protocol"
    unknown = run(session, "catalog.cone_search", service="I/239/hip_main", center=sky(10.0, -3.0),
                  radius={"value": 1.0, "unit": "arcmin"})
    assert unknown.error.code == "SERVER_UNKNOWN" and unknown.error.params["reason"] == "not_listed"
    rows_bad = run(session, "catalog.cone_search", service="nasa-irsa-allwise-scs", center=sky(10.0, -3.0),
                   radius={"value": 1.0, "unit": "arcmin"}, max_rows=2_000_000)
    assert rows_bad.error.code == "MAX_ROWS_INVALID"
    assert len(session.workspace.state.layers) == before and listed.requests == []


# =============================================================================
# Query ADQL: validazione prima della rete, servizio che rifiuta, commenti, sincrona e asincrona


def test_t26_tap_invalid_adql_blocked_before_network(session, listed):
    listed.routes["/tap/sync"] = tap_sync_route(5)
    for adql, reason, position in (("", "empty", 0), ("DELETE FROM t", "not_select", 0),
                                   ("SELECT * FROM t WHERE a = 'x", "unclosed_quote", 26)):
        result = run(session, "catalog.tap_query", service="esa-gaia-tap", adql=adql)
        assert result.status == "error" and result.error.code == "ADQL_INVALID", adql
        assert result.error.params["reason"] == reason and result.error.params["position"] == position
    assert listed.requests == []  # nessuna richiesta al servizio


def test_t26_tap_service_rejects_query(session, listed):
    error = votable_text(0, status="ERROR").replace(
        '<INFO name="QUERY_STATUS" value="ERROR"/>',
        '<INFO name="QUERY_STATUS" value="ERROR">Table stelle_x does not exist</INFO>')
    listed.routes["/tap/sync"] = lambda r: (400, "application/x-votable+xml", error)
    result = run(session, "catalog.tap_query", service="esa-gaia-tap", adql="SELECT * FROM stelle_x")
    assert result.status == "error" and result.error.code == "ADQL_INVALID"
    assert result.error.params["reason"] == "service_rejected"
    assert result.error.params["detail"] == "Table stelle_x does not exist"  # testo del servizio tale e quale
    assert len(session.workspace.state.layers) == 0


def test_t26_tap_sync_comments_and_registration(session, listed):
    listed.routes["/tap/sync"] = tap_sync_route(6)
    adql = "SELECT * FROM stelle\n-- CIRCLE: view centre and radius, ICRS, degrees; epoch: not known (it's ok)"
    result = run(session, "catalog.tap_query", service="esa-gaia-tap", adql=adql, max_rows=4)
    assert result.status == "ok", result.error
    sent = listed.requests[-1]["params"]
    assert sent["QUERY"] == "SELECT * FROM stelle" and sent["MAXREC"] == "4"  # commento non inviato
    entry = session.history.entries[-1]
    assert entry.command.parameters["adql"] == adql  # testo scritto registrato
    assert entry.command.parameters["async_timeout"] == {"value": 600.0, "unit": "s"}  # default risolto
    assert entry.command.parameters["mode"] == "sync" and entry.command.parameters["url"] == listed.url + "/tap"
    query = result.values["query"]
    assert query["adql"] == adql and query["params"]["QUERY"] == "SELECT * FROM stelle" and query["mode"] == "sync"
    assert query["truncated"] is True and query["max_rows"] == 4
    assert [w for w in result.warnings if w.code == "ROW_LIMIT_EXCEEDED" and w.params["reason"] == "service_overflow"]
    assert session.workspace.state.layer(result.layers_created[0]).name == "Archivio Gaia · ADQL"


def test_t26_tap_async_ok_and_deadline(session, listed):
    uws_service(listed, ["EXECUTING", "COMPLETED"], total=4)
    result = run(session, "catalog.tap_query", service="esa-gaia-tap", adql="SELECT * FROM stelle", mode="async")
    assert result.status == "ok", result.error
    assert rows(session, result.layers_created[0]) == expected_rows(votable_text(4))
    assert result.values["query"]["mode"] == "async"
    state = uws_service(listed, ["EXECUTING"])
    late = run(session, "catalog.tap_query", service="esa-gaia-tap", adql="SELECT * FROM altre", mode="async",
               async_timeout={"value": 0.5, "unit": "s"})
    assert late.status == "error" and late.error.code == "NET_TIMEOUT"
    assert late.error.params["reason"] == "async_deadline" and state["posted"] == ["RUN", "ABORT"]


def test_t26_tap_async_cancelled(session, listed):
    state = uws_service(listed, ["EXECUTING"])
    cancel = CancelToken()
    threading.Timer(0.4, cancel.cancel).start()
    started = time.monotonic()
    result = run(session, "catalog.tap_query", service="esa-gaia-tap", adql="SELECT * FROM stelle", mode="async",
                 cancel=cancel)
    assert time.monotonic() - started < 2.0
    assert result.status == "cancelled" and result.error.code == "COMMAND_CANCELLED"
    assert result.error.params == {"reason": "discarded"}
    assert state["posted"] == ["RUN", "ABORT"]  # lavoro interrotto
    assert any(r["method"] == "DELETE" for r in listed.requests)  # ed eliminato
    assert len(session.workspace.state.layers) == 0


# =============================================================================
# Riesecuzione: stesso URL, stessi parametri, righe identiche (Riesegui e sessione riaperta)


def test_t26_rerun_same_request(session, listed, tmp_path, cache):
    listed.routes["/scs"] = votable_route(votable_text(5))
    listed.routes["/tap/sync"] = tap_sync_route(6)
    first = run(session, "catalog.cone_search", service="nasa-irsa-allwise-scs", center=sky(10.0, -3.0),
                radius={"value": 2.0, "unit": "arcmin"})
    tap = run(session, "catalog.tap_query", service="esa-gaia-tap", adql="SELECT * FROM stelle")
    assert first.status == tap.status == "ok"
    for k, entry in enumerate(list(session.history.entries)):
        again = session.run(Command(entry.command.name, entry.command.version, dict(entry.command.parameters),
                                    RequestedBy("history")))
        assert again.status == "ok", again.error
        assert again.values["query"]["url"] == entry.result.values["query"]["url"]
        assert again.values["query"]["params"] == entry.result.values["query"]["params"]
        assert rows(session, again.layers_created[0]) == rows(session, entry.result.layers_created[0])
        assert again.network_fingerprint[0]["sha256"] == entry.result.network_fingerprint[0]["sha256"]
    # il servizio nell'elenco cambia URL: il comando registrato ha l'URL e rifà la stessa richiesta
    path = tmp_path / "s.astrotwo.json"
    session.save(path, app_version="0.0.0")
    entries = tuple(dataclasses.replace(e, url="https://altrove.invalid/scs") if e.id == "nasa-irsa-allwise-scs"
                    else e for e in vo.BUILTIN_SERVERS)
    vo.BUILTIN_SERVERS = entries  # ripristinato da monkeypatch alla fine del test
    reopened = Session.load(path, default_registry(cache=cache))
    report = reopened.replay()
    assert report.stop is None, report.stop
    assert rows(reopened, "L1") == rows(session, "L1") and rows(reopened, "L2") == rows(session, "L2")
    assert reopened.workspace.state.layer("L1").source == listed.url + "/scs?table=t"


# =============================================================================
# Server personali


def test_t26_personal_servers(session, service):
    service.routes["/mine"] = votable_route(votable_text(3))
    url = service.url + "/mine"
    added = run(session, "vo.add_server", name="Il mio SCS", protocol="scs", url=url)
    assert added.status == "ok", added.error
    assert added.values["server"] == "my-scs-1"
    assert added.values["personal_servers"] == [{"id": "my-scs-1", "name": "Il mio SCS", "protocol": "scs",
                                                 "url": url}]
    again = run(session, "vo.add_server", name="Doppio", protocol="scs", url=url)
    assert again.error.code == "COMMAND_PARAMETER_INVALID"
    assert again.error.params == {"reason": "server_already_listed", "parameter": "url", "server": "my-scs-1",
                                  "url": url}
    other = run(session, "vo.add_server", name="Stesso URL, altro protocollo", protocol="tap", url=url)
    assert other.status == "ok" and other.values["server"] == "my-tap-1"
    empty = run(session, "vo.add_server", name="  ", protocol="tap", url=url + "2")
    assert empty.error.code == "COMMAND_PARAMETER_INVALID" and empty.error.params["parameter"] == "name"
    # cone search sul mio server, poi il server si toglie: il comando registrato ha l'URL e si riesegue
    cone = run(session, "catalog.cone_search", service="my-scs-1", center=sky(10.0, -3.0),
               radius={"value": 1.0, "unit": "arcmin"})
    assert cone.status == "ok" and cone.values["query"]["service_name"] == "Il mio SCS"
    removed = run(session, "vo.remove_server", server="my-scs-1")
    assert removed.status == "ok" and [e["id"] for e in removed.values["personal_servers"]] == ["my-tap-1"]
    builtin = run(session, "vo.remove_server", server="esa-gaia-tap")
    assert builtin.error.code == "SERVER_UNKNOWN" and builtin.error.params["reason"] == "not_personal"
    entry = [e for e in session.history.entries if e.command.name == "catalog.cone_search"][-1]
    rerun = session.run(Command(entry.command.name, 1, dict(entry.command.parameters), RequestedBy("history")))
    assert rerun.status == "ok" and rerun.values["query"]["url"] == url
    # classe application: in cronologia, mai rieseguiti alla riapertura
    assert session.registry.spec("vo.add_server").command_class == "application"
