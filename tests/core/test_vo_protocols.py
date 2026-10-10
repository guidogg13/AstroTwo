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
from astropy.io import ascii as astropy_ascii
from astropy.io import fits
from astropy.io.votable import parse as parse_votable
from astropy.table import Table

import astrotwo
from astrotwo.core.cache import NetworkTimeouts, SharedCache
from astrotwo.core.catalogs import CatalogsError, read_table
from astrotwo.core.vo_protocols import (
    DEFAULT_MAX_ROWS,
    VOTABLE_VERSION,
    VoProtocolsError,
    download_table,
    export_table,
    read_votable,
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
                    status, ctype, payload = 404, "text/plain", b"not found"
                else:
                    status, ctype, payload = route(request)
                    payload = payload.encode() if isinstance(payload, str) else payload
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                self._serve("GET")

            def do_POST(self):
                self._serve("POST")

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
