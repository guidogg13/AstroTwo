"""Test del modulo 14 (``mdfiles/14-core-protocolli-vo.md`` §12).

File e servizi di prova generati nel test (servizi simulati con un server
HTTP locale); gli attesi sono ricalcolati con ``astropy`` e ``pyvo``, mai
scritti a mano. I test che usano la rete vera hanno il marcatore ``network``.
"""

from __future__ import annotations

import io
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import astropy.units as u
import numpy as np
import pytest
import pyvo
from astropy.coordinates import SkyCoord
from astropy.io import ascii as astropy_ascii
from astropy.io import fits
from astropy.io.votable import parse as parse_votable
from astropy.table import Table

import astrotwo
from astrotwo.core.coordinates_wcs import SkyFrame
from astrotwo.core.cache import NetworkTimeouts, SharedCache
from astrotwo.core.catalogs import CatalogsError, read_table
from astrotwo.core.vo_protocols import (
    DEFAULT_MAX_ROWS,
    VOTABLE_VERSION,
    VoProtocolsError,
    cone_search,
    download_table,
    export_table,
    read_votable,
    tap_query,
    validate_adql,
    write_votable,
)

# =============================================================================
# P1 — Lettura/scrittura VOTable ed esportazione (T1, T5)
# =============================================================================

VOTABLE = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results">
<INFO name="QUERY_STATUS" value="{status}"/>
<COOSYS ID="sys" system="ICRS" epoch="J2016.0"/>
<TABLE name="stelle">
<FIELD name="RA" ucd="pos.eq.ra;meta.main" ref="sys" datatype="double" unit="deg"/>
<FIELD name="DE" ucd="pos.eq.dec;meta.main" ref="sys" datatype="double" unit="deg"/>
<FIELD name="Vmag" ucd="phot.mag;em.opt.V" datatype="float" unit="mag"/>
<FIELD name="Name" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>
{rows}
</TABLEDATA></DATA>
</TABLE>
</RESOURCE>
</VOTABLE>
"""


def votable_text(n=3, status="OK", start=0):
    rows = "\n".join(
        f"<TR><TD>{10 + 0.5 * k}</TD><TD>{-3 - 0.25 * k}</TD><TD>{9 + 0.1 * k:.1f}</TD><TD>s{k}</TD></TR>"
        for k in range(start, start + n)
    )
    return VOTABLE.format(rows=rows, status=status)


@pytest.fixture
def catalog(tmp_path):
    path = tmp_path / "cat.xml"
    path.write_text(votable_text(), encoding="utf-8")
    return read_table(path)


def test_t1_votable_round_trip(tmp_path, catalog):
    out = write_votable(catalog, tmp_path / "out.xml")
    again = read_votable(out)
    expected = parse_votable(str(out)).get_first_table().to_table(use_names_over_ids=True)
    assert again.colnames == expected.colnames == catalog.colnames
    for name in catalog.colnames:
        assert again.table[name].unit == catalog.table[name].unit == expected[name].unit
        assert np.array_equal(np.asarray(again.table[name]), np.asarray(catalog.table[name]))
    # UCD e COOSYS conservati: le colonne di posizione si ritrovano.
    assert again.positions is not None and (again.positions.lon, again.positions.lat) == ("RA", "DE")
    assert again.positions.frame == "icrs" and again.body == "celestial"


def test_votable_provenance_and_version(tmp_path, catalog):
    out = write_votable(catalog, tmp_path / "out.xml")
    vot = parse_votable(str(out))
    assert vot.version == VOTABLE_VERSION == "1.4"
    infos = {i.name: i.value for i in vot.resources[0].infos}
    assert infos["A2VERS"] == f"AstroTwo {astrotwo.__version__}"
    assert infos["A2FORMAT"] == "VOTable 1.4"
    assert infos["A2ORIGIN"] == catalog.origin and infos["A2DATE"].endswith("Z") and "A2EXPORT" in infos


def test_t5_export_three_formats(tmp_path, catalog):
    paths = {fmt: export_table(catalog, tmp_path / f"t.{fmt}", fmt) for fmt in ("votable", "fits", "csv")}
    expected = {
        "votable": parse_votable(str(paths["votable"])).get_first_table().to_table(use_names_over_ids=True),
        "fits": Table.read(paths["fits"], hdu=1),
        "csv": astropy_ascii.read(paths["csv"], format="csv", comment="#"),
    }
    for fmt, path in paths.items():
        back = read_table(path)
        assert back.format == ("votable" if fmt == "votable" else fmt)
        for name in ("RA", "DE", "Vmag"):
            assert np.allclose(np.asarray(back.table[name], dtype=float), np.asarray(expected[fmt][name], dtype=float))
            assert np.allclose(np.asarray(back.table[name], dtype=float), np.asarray(catalog.table[name], dtype=float))
        assert [str(v) for v in back.table["Name"]] == [str(v) for v in catalog.table["Name"]]
        if fmt != "csv":  # unità nel CSV: D14-10 da decidere
            for name in ("RA", "DE", "Vmag"):
                assert back.table[name].unit == catalog.table[name].unit == expected[fmt][name].unit


def test_fits_and_csv_provenance(tmp_path, catalog):
    fits_path = export_table(catalog, tmp_path / "t.fits", "fits")
    header = fits.getheader(fits_path, 1)
    assert header["A2VERS"] == f"AstroTwo {astrotwo.__version__}" and header["A2ORIGIN"] == catalog.origin
    assert header["A2FORMAT"].startswith("FITS") and header["TUCD1"] == "pos.eq.ra;meta.main"
    csv_path = export_table(catalog, tmp_path / "t.csv", "csv")
    head = csv_path.read_text(encoding="utf-8").splitlines()
    assert head[0] == f"# A2VERS = AstroTwo {astrotwo.__version__}"
    assert f"# A2ORIGIN = {catalog.origin}" in head and head[head.index("RA,DE,Vmag,Name") - 1].startswith("#")


def test_export_errors(tmp_path, catalog):
    with pytest.raises(VoProtocolsError) as err:
        export_table(catalog, tmp_path / "t.txt", "xlsx")
    assert err.value.code == "EXPORT_FORMAT_UNSUPPORTED" and "csv" in err.value.message
    path = export_table(catalog, tmp_path / "t.xml", "votable")
    with pytest.raises(VoProtocolsError) as err:
        export_table(catalog, path, "votable")
    assert err.value.code == "FILE_EXISTS"
    assert export_table(catalog, path, "fits", overwrite=True) == path
    with pytest.raises(TypeError):
        export_table(Table({"a": [1]}), tmp_path / "x.xml", "votable")


def test_votable_invalid(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text(votable_text().replace("</TABLE>", ""), encoding="utf-8")
    with pytest.raises(VoProtocolsError) as err:
        read_votable(bad)
    assert err.value.code == "VOTABLE_INVALID" and ":" in err.value.message
    csv = tmp_path / "t.csv"
    csv.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(VoProtocolsError) as err:
        read_votable(csv)
    assert err.value.code == "VOTABLE_INVALID" and "csv" in err.value.message
    with pytest.raises(CatalogsError) as err:
        read_votable(tmp_path / "assente.xml")
    assert err.value.code == "TABLE_UNREADABLE"


# =============================================================================
# Servizi simulati: server HTTP locale (nessuna rete)
# =============================================================================


class FakeService:
    """Server HTTP locale: ``routes[path] = funzione(richiesta) -> (stato, content-type, corpo)``."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        service = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _serve(self, method):
                parsed = urllib.parse.urlsplit(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                params = dict(urllib.parse.parse_qsl(parsed.query))
                if method == "POST" and self.headers.get("Content-Type", "").startswith("application/x-www-form"):
                    params.update(urllib.parse.parse_qsl(body.decode()))
                request = {"method": method, "path": parsed.path, "params": params, "body": body,
                           "headers": dict(self.headers)}
                service.requests.append(request)
                route = service.routes.get(parsed.path)
                if route is None:
                    status, ctype, payload, extra = 404, "text/plain", b"not found", []
                else:
                    status, ctype, payload, *extra = route(request)
                    payload = payload.encode() if isinstance(payload, str) else payload
                self.send_response(status)
                for name, value in (extra[0] if extra else {}).items():
                    self.send_header(name, value)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                self._serve("GET")

            def do_POST(self):
                self._serve("POST")

            def do_DELETE(self):
                self._serve("DELETE")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def hits(self, path):
        return sum(1 for r in self.requests if r["path"] == path)


@pytest.fixture
def service():
    fake = FakeService()
    yield fake
    fake.close()


@pytest.fixture
def cache(tmp_path):
    with SharedCache(tmp_path / "cache") as shared:
        yield shared


def votable_route(text, status=200):
    return lambda request: (status, "application/x-votable+xml", text)


# =============================================================================
# P2 — Base di rete: registro, cache, download_table (T6, T21)
# =============================================================================


def test_download_table_provenance(service, cache):
    service.routes["/t.xml"] = votable_route(votable_text(4))
    result = download_table(service.url + "/t.xml", cache=cache)
    expected = parse_votable(io.BytesIO(votable_text(4).encode())).get_first_table().to_table()
    assert result.table.rows == len(expected) == 4 and result.table.colnames == expected.colnames
    assert result.table.origin == service.url + "/t.xml" and result.table.file_modified is None
    assert result.table.positions is not None and result.table.body == "celestial"
    record = result.request
    assert record.protocol == "download" and record.command == "download_table" and record.rows == 4
    assert record.url == service.url + "/t.xml" and record.method == "GET" and not record.from_cache
    assert record.as_dict()["retrieved_at"].endswith("Z")
    assert "AstroTwo/" in service.requests[0]["headers"]["User-Agent"]


def test_t6_reproducibility(service, cache):
    service.routes["/t.xml"] = votable_route(votable_text(3))
    first = download_table(service.url + "/t.xml", cache=cache)
    saved = first.request.as_dict()
    # Riesecuzione dai soli dati registrati (funzione + argomenti), richiesta forzata al servizio.
    command = {"download_table": download_table}[saved["command"]]
    second = command(**saved["arguments"], cache=cache, refresh=True)
    assert second.request.url == first.request.url and second.request.params == first.request.params
    assert second.table.colnames == first.table.colnames and not second.request.from_cache
    assert [str(c.dtype) for c in second.table.table.itercols()] == [str(c.dtype) for c in first.table.table.itercols()]
    assert service.hits("/t.xml") == 2


def test_t21_cache_first_refresh_offline(service, cache):
    service.routes["/t.xml"] = votable_route(votable_text(3))
    url = service.url + "/t.xml"
    first = download_table(url, cache=cache)
    second = download_table(url, cache=cache)
    assert second.request.from_cache and second.request.retrieved_at == first.request.retrieved_at
    assert any(code == "FROM_CACHE" for code, _ in second.warnings) and service.hits("/t.xml") == 1
    third = download_table(url, cache=cache, refresh=True)
    assert not third.request.from_cache and service.hits("/t.xml") == 2
    service.close()
    fourth = download_table(url, cache=cache, refresh=True, timeouts=NetworkTimeouts(connect=0.5, read=0.5))
    assert fourth.request.from_cache and "rete non disponibile" in dict(fourth.warnings)["FROM_CACHE"]
    assert np.array_equal(fourth.table.table["RA"], first.table.table["RA"])


def test_network_errors(service, cache):
    service.routes["/private"] = lambda r: (401, "text/plain", "auth")
    with pytest.raises(VoProtocolsError) as err:
        download_table(service.url + "/private", cache=cache)
    assert err.value.code == "AUTH_REQUIRED"
    with pytest.raises(VoProtocolsError) as err:
        download_table(service.url + "/missing", cache=cache)
    assert err.value.code == "SERVICE_ERROR" and "404" in err.value.message
    url = service.url + "/t.xml"
    service.close()
    with pytest.raises(VoProtocolsError) as err:
        download_table(url, cache=cache, timeouts=NetworkTimeouts(connect=0.5, read=0.5))
    assert err.value.code == "NET_TIMEOUT" and "0.5 s" in err.value.message


def test_failed_reading_is_not_cached(service, cache):
    service.routes["/t.xml"] = lambda r: (200, "text/html", "<html><body>errore</body></html>")
    with pytest.raises(CatalogsError):
        download_table(service.url + "/t.xml", cache=cache)
    service.routes["/t.xml"] = votable_route(votable_text(2))
    assert download_table(service.url + "/t.xml", cache=cache).table.rows == 2


def test_default_max_rows():
    assert DEFAULT_MAX_ROWS == 100_000


# =============================================================================
# P3 — Cone search, TAP/ADQL, validate_adql (T2, T3, T4, T20)
# =============================================================================


def test_cone_search_simulated(service, cache):
    service.routes["/scs"] = votable_route(votable_text(5))
    center = SkyFrame.from_lonlat(120.0 * u.deg, 30.0 * u.deg, "galactic")
    result = cone_search(center, 10 * u.arcsec, service.url + "/scs", cache=cache)
    params = service.requests[-1]["params"]
    expected = SkyCoord(120.0 * u.deg, 30.0 * u.deg, frame="galactic").icrs  # ricalcolo con astropy
    assert np.isclose(float(params["RA"]), expected.ra.deg, rtol=0, atol=1e-9)
    assert np.isclose(float(params["DEC"]), expected.dec.deg, rtol=0, atol=1e-9)
    assert np.isclose(float(params["SR"]), (10 * u.arcsec).to_value(u.deg), rtol=1e-12)
    assert result.table.rows == 5 and not result.truncated and result.request.protocol == "scs"
    assert result.request.arguments["center"]["frame"] == "icrs" and result.request.rows == 5


def test_cone_search_truncation_and_errors(service, cache):
    service.routes["/scs"] = votable_route(votable_text(8))
    center = SkyCoord(10 * u.deg, -3 * u.deg, frame="icrs")
    result = cone_search(center, 1 * u.arcmin, service.url + "/scs", max_rows=3, cache=cache)
    assert result.truncated and result.table.rows == 3 and result.request.rows == 3
    assert "ricevute 8 righe" in dict(result.warnings)["ROW_LIMIT_EXCEEDED"]
    for bad in (0, 1_000_001, 2.5, True):
        with pytest.raises(VoProtocolsError) as err:
            cone_search(center, 1 * u.arcmin, service.url + "/scs", max_rows=bad, cache=cache)
        assert err.value.code == "MAX_ROWS_INVALID"
    with pytest.raises(TypeError):
        cone_search(center, 0.01, service.url + "/scs", cache=cache)  # raggio senza unità
    with pytest.raises(VoProtocolsError) as err:
        cone_search(center, 1 * u.arcmin, "I/239/hip_main", cache=cache)
    assert err.value.code == "SERVER_UNKNOWN"
    # SCS 1.03: l'errore è un INFO di nome "Error".
    service.routes["/scs"] = votable_route(votable_text(1).replace(
        '<INFO name="QUERY_STATUS" value="OK"/>', '<INFO name="Error" value="RA fuori intervallo"/>'))
    with pytest.raises(VoProtocolsError) as err:
        cone_search(center, 1 * u.arcmin, service.url + "/scs", cache=cache, refresh=True)
    assert err.value.code == "SERVICE_ERROR"


def tap_sync_route(total):
    def route(request):
        maxrec = int(request["params"].get("MAXREC", total))
        status = "OVERFLOW" if total > maxrec else "OK"
        return 200, "application/x-votable+xml", votable_text(min(total, maxrec), status=status)
    return route


def test_t3_tap_truncation(service, cache):
    service.routes["/tap/sync"] = tap_sync_route(50)
    result = tap_query(service.url + "/tap", "SELECT * FROM stelle", max_rows=7, cache=cache)
    params = service.requests[-1]["params"]
    assert params["MAXREC"] == "7" and params["QUERY"] == "SELECT * FROM stelle" and params["LANG"] == "ADQL"
    assert params["REQUEST"] == "doQuery" and service.requests[-1]["method"] == "POST"
    assert result.truncated and result.table.rows == 7 == result.max_rows
    assert "OVERFLOW" in dict(result.warnings)["ROW_LIMIT_EXCEEDED"]
    full = tap_query(service.url + "/tap", "SELECT * FROM stelle", cache=cache)
    assert not full.truncated and full.table.rows == 50 and "ROW_LIMIT_EXCEEDED" not in dict(full.warnings)


def test_t4_invalid_adql_no_network(service, cache):
    service.routes["/tap/sync"] = tap_sync_route(5)
    for adql in ("", "DELETE FROM t", "SELECT * FROM t WHERE a = 'x", "SELECT COUNT(* FROM t"):
        with pytest.raises(VoProtocolsError) as err:
            tap_query(service.url + "/tap", adql, cache=cache)
        assert err.value.code == "ADQL_INVALID"
    assert service.requests == []  # nessuna chiamata di rete inutile


def test_tap_service_error_reported(service, cache):
    error = votable_text(0, status="ERROR").replace(
        '<INFO name="QUERY_STATUS" value="ERROR"/>',
        '<INFO name="QUERY_STATUS" value="ERROR">Table stelle_x does not exist</INFO>')
    service.routes["/tap/sync"] = lambda r: (400, "application/x-votable+xml", error)
    with pytest.raises(VoProtocolsError) as err:
        tap_query(service.url + "/tap", "SELECT * FROM stelle_x", cache=cache)
    assert err.value.code == "ADQL_INVALID" and "does not exist" in err.value.message
    timeout = error.replace("Table stelle_x does not exist", "Query execution time limit exceeded")
    service.routes["/tap/sync"] = lambda r: (200, "application/x-votable+xml", timeout)
    with pytest.raises(VoProtocolsError) as err:
        tap_query(service.url + "/tap", "SELECT * FROM stelle", cache=cache)
    assert "mode='async'" in err.value.message
    service.routes["/tap/sync"] = lambda r: (500, "text/plain", "boom")
    with pytest.raises(VoProtocolsError) as err:
        tap_query(service.url + "/tap", "SELECT * FROM stelle", cache=cache)
    assert err.value.code == "SERVICE_ERROR"


def test_tap_sync_timeout_suggests_async(service, cache):
    def slow(request):
        import time
        time.sleep(1.0)
        return 200, "application/x-votable+xml", votable_text(1)
    service.routes["/tap/sync"] = slow
    with pytest.raises(VoProtocolsError) as err:
        tap_query(service.url + "/tap", "SELECT * FROM stelle", cache=cache,
                  timeouts=NetworkTimeouts(connect=1.0, read=0.2))
    assert err.value.code == "NET_TIMEOUT" and "mode='async'" in err.value.message


UWS_JOB = """<?xml version="1.0" encoding="UTF-8"?>
<uws:job xmlns:uws="http://www.ivoa.net/xml/UWS/v1.0" xmlns:xlink="http://www.w3.org/1999/xlink"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.1">
<uws:jobId>1</uws:jobId>
<uws:runId xsi:nil="true"/><uws:ownerId xsi:nil="true"/>
<uws:phase>{phase}</uws:phase>
<uws:quote xsi:nil="true"/><uws:startTime xsi:nil="true"/><uws:endTime xsi:nil="true"/>
<uws:executionDuration>0</uws:executionDuration>
<uws:destruction xsi:nil="true"/>
<uws:parameters/>
<uws:results>{results}</uws:results>
{error}
</uws:job>
"""


def uws_service(service, phases, total=4):
    """Lavoro UWS simulato: ``phases`` = fasi restituite dopo RUN (l'ultima si ripete)."""
    state = {"phase": "PENDING", "after_run": list(phases)}

    def job(request):
        if request["method"] == "DELETE":
            return 200, "text/plain", ""
        if state["phase"] != "PENDING" and len(state["after_run"]) > 1:
            state["phase"] = state["after_run"].pop(0)
        elif state["phase"] != "PENDING":
            state["phase"] = state["after_run"][0]
        results = (f'<uws:result id="result" xlink:href="{service.url}/tap/async/1/results/result"/>'
                   if state["phase"] == "COMPLETED" else "")
        error = ('<uws:errorSummary type="fatal"><uws:message>syntax error at FROMM</uws:message>'
                 '</uws:errorSummary>' if state["phase"] == "ERROR" else "")
        return 200, "text/xml", UWS_JOB.format(phase=state["phase"], results=results, error=error)

    def phase(request):
        state["phase"] = "QUEUED" if request["params"].get("PHASE") == "RUN" else "ABORTED"
        state.setdefault("posted", []).append(request["params"].get("PHASE"))
        return 303, "text/plain", "", {"Location": f"{service.url}/tap/async/1"}

    service.routes["/tap/async"] = lambda r: (303, "text/plain", "", {"Location": f"{service.url}/tap/async/1"})
    service.routes["/tap/async/1"] = job
    service.routes["/tap/async/1/phase"] = phase
    service.routes["/tap/async/1/results/result"] = votable_route(votable_text(total))
    return state


def test_tap_async(service, cache):
    state = uws_service(service, ["EXECUTING", "COMPLETED"])
    result = tap_query(service.url + "/tap", "SELECT * FROM stelle", mode="async", max_rows=10, cache=cache)
    expected = parse_votable(io.BytesIO(votable_text(4).encode())).get_first_table().to_table()
    assert result.table.rows == len(expected) and state["posted"] == ["RUN"]
    created = [r for r in service.requests if r["path"] == "/tap/async" and r["method"] == "POST"][0]
    assert created["params"]["MAXREC"] == "10" and created["params"]["QUERY"] == "SELECT * FROM stelle"
    assert any(r["method"] == "DELETE" for r in service.requests)  # lavoro eliminato
    assert result.request.arguments["mode"] == "async" and result.request.url == service.url + "/tap/async"
    again = tap_query(service.url + "/tap", "SELECT * FROM stelle", mode="async", max_rows=10, cache=cache)
    assert again.request.from_cache


def test_tap_async_timeout_and_error(service, cache):
    state = uws_service(service, ["EXECUTING"])
    with pytest.raises(VoProtocolsError) as err:
        tap_query(service.url + "/tap", "SELECT * FROM stelle", mode="async", async_timeout=0.5, cache=cache)
    assert err.value.code == "NET_TIMEOUT" and "0.5 s" in err.value.message and state["posted"] == ["RUN", "ABORT"]
    uws_service(service, ["ERROR"])
    with pytest.raises(VoProtocolsError) as err:
        tap_query(service.url + "/tap", "SELECT * FROM stelle", mode="async", cache=cache, refresh=True)
    assert err.value.code == "ADQL_INVALID" and "FROMM" in err.value.message


def test_t20_validate_adql():
    cases = {
        "": (False, 0),
        "   ": (False, 0),
        "  UPDATE t SET a=1": (False, 2),
        "select a from t": (True, None),
        "SELECT a FROM t WHERE b = 'it''s'": (True, None),
        'SELECT "my col" FROM t': (True, None),
        "SELECT a FROM t WHERE b = 'x": (False, 26),
        'SELECT "a FROM t': (False, 7),
        "SELECT COUNT(*) FROM t WHERE (a > 1": (False, 29),
        "SELECT a) FROM t": (False, 8),
        "SELECT a FROM t WHERE b = '(' ": (True, None),
        "SELECTED FROM t": (False, 0),
    }
    for adql, (valid, position) in cases.items():
        check = validate_adql(adql)
        assert (check.valid, check.position) == (valid, position), adql


@pytest.mark.network
def test_t2_cone_search_network(cache):
    # Servizio SCS pubblico (Simbad, CDS); atteso ricalcolato con pyvo contro lo stesso servizio.
    url = "https://simbad.cds.unistra.fr/cone/"
    center = SkyCoord(83.8221 * u.deg, -5.3911 * u.deg, frame="icrs")
    result = cone_search(center, 10 * u.arcsec, url, cache=cache)
    expected = pyvo.dal.SCSService(url).search(center, 10 * u.arcsec)
    assert result.table.rows == len(expected) and result.request.rows == len(expected)
