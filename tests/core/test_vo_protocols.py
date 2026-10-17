# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del modulo 14 (``mdfiles/14-core-protocolli-vo.md`` §12).

File e servizi di prova generati nel test (servizi simulati con un server
HTTP locale); gli attesi sono ricalcolati con ``astropy`` e ``pyvo``, mai
scritti a mano. I test che usano la rete vera hanno il marcatore ``network``.
"""

from __future__ import annotations

import io
import time as _time
import urllib.parse

import astropy
import astropy.units as u
import numpy as np
import pytest
import pyvo
import pyvo.samp as pyvo_samp
from astropy.coordinates import SkyCoord
from astropy.io import ascii as astropy_ascii
from astropy.io import fits
from astropy.io.votable import parse as parse_votable
from astropy.table import Table
from astropy.time import Time

import astrotwo
import astrotwo.core.vo_protocols as vo
from astrotwo.core.coordinates_wcs import SkyFrame
from astrotwo.core.cache import NetworkTimeouts, SharedCache
from astrotwo.core.catalogs import CatalogsError, read_table
from astrotwo.core.vo_protocols import (
    DEFAULT_MAX_ROWS,
    VOTABLE_VERSION,
    BUILTIN_SERVERS,
    DataLinkClient,
    SampHub,
    SampSelection,
    ServerRegistry,
    VoProtocolsError,
    cone_search,
    download_table,
    read_idha,
    sia_search,
    simbad_pointer,
    vizier_photometry,
    ssa_load,
    ssa_search,
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
    out = write_votable(catalog, tmp_path / "out.xml").path
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
    out = write_votable(catalog, tmp_path / "out.xml").path
    vot = parse_votable(str(out))
    assert vot.version == VOTABLE_VERSION == "1.4"
    infos = {i.name: i.value for i in vot.resources[0].infos}
    assert infos["A2VERS"] == f"AstroTwo {astrotwo.__version__}"
    assert infos["A2FORMAT"] == "VOTable 1.4"
    assert infos["A2ORIGIN"] == catalog.origin and infos["A2DATE"].endswith("Z") and "A2EXPORT" in infos


def test_t5_export_all_formats(tmp_path, catalog):
    results = {fmt: export_table(catalog, tmp_path / f"t.{fmt}", fmt) for fmt in ("votable", "fits", "csv", "ecsv")}
    paths = {fmt: r.path for fmt, r in results.items()}
    expected = {
        "votable": parse_votable(str(paths["votable"])).get_first_table().to_table(use_names_over_ids=True),
        "fits": Table.read(paths["fits"], hdu=1),
        "csv": astropy_ascii.read(paths["csv"], format="csv", comment="#"),
        "ecsv": astropy_ascii.read(paths["ecsv"], format="ecsv"),
    }
    for fmt, path in paths.items():
        back = read_table(path)
        assert back.format == fmt
        for name in ("RA", "DE", "Vmag"):
            assert np.allclose(np.asarray(back.table[name], dtype=float), np.asarray(expected[fmt][name], dtype=float))
            assert np.allclose(np.asarray(back.table[name], dtype=float), np.asarray(catalog.table[name], dtype=float))
        assert [str(v) for v in back.table["Name"]] == [str(v) for v in catalog.table["Name"]]
        if fmt == "csv":  # CSV semplice: nessuna unità, con l'avviso (D14-10)
            assert all(back.table[name].unit is None for name in ("RA", "DE", "Vmag"))
            assert [c for c, _ in results[fmt].warnings] == ["CSV_UNITS_NOT_SAVED"]
        else:
            for name in ("RA", "DE", "Vmag"):
                assert back.table[name].unit == catalog.table[name].unit == expected[fmt][name].unit
            assert results[fmt].warnings == ()


def test_ecsv_round_trip_units_and_ucd(tmp_path, catalog):
    # Andata e ritorno ECSV (D14-10): unità (anche non riconosciute), UCD, valori mancanti, provenienza.
    data = catalog.table.copy()
    data["Vmag"] = np.ma.MaskedArray(data["Vmag"], mask=[False, True, False])
    data["Vmag"].unit = u.mag
    data["Vmag"].meta["ucd"] = "phot.mag;em.opt.V"
    data["flag"] = [1, 2, 3]
    data["flag"].meta["unit_unrecognized"] = "---"
    import dataclasses
    table = dataclasses.replace(catalog, table=data)
    out = export_table(table, tmp_path / "t.ecsv", "ecsv")
    back = read_table(out)
    assert back.format == "ecsv"
    for name in ("RA", "DE", "Vmag"):
        assert back.table[name].unit == data[name].unit
        assert back.table[name].meta["ucd"] == data[name].meta["ucd"]
    assert np.ma.getmaskarray(back.table["Vmag"]).tolist() == [False, True, False]
    assert back.table["flag"].unit is None and back.table["flag"].meta["unit_unrecognized"] == "---"
    assert ("UNIT_UNRECOGNIZED" in [c for c, _ in back.warnings])
    # Sistema, equinozio ed epoca delle posizioni nei metadati YAML: riletti, nessun FRAME_UNKNOWN.
    assert (back.positions.lon, back.positions.lat) == ("RA", "DE")
    assert (back.positions.frame, back.positions.epoch) == (catalog.positions.frame, catalog.positions.epoch) == (
        "icrs", "J2016.0")
    assert back.body == "celestial" and "FRAME_UNKNOWN" not in dict(back.warnings)
    assert "POSITIONS_FROM_ECSV" in dict(back.warnings)
    meta = back.table.meta
    assert meta["A2FORMAT"] == "ECSV 1.0" and meta["A2ORIGIN"] == catalog.origin
    assert meta["A2WRITER"] == f"astropy {astropy.__version__}"
    assert out.path.read_text(encoding="utf-8").startswith("# %ECSV")
    # Senza unità nella tabella il CSV non dà avvisi.
    plain = dataclasses.replace(catalog, table=Table({"a": [1, 2]}))
    assert export_table(plain, tmp_path / "p.csv", "csv").warnings == ()


def test_ecsv_positions_fk5_and_confirmed(tmp_path):
    # FK5 con equinozio, e colonne confermate dall'utente (senza UCD): andata e ritorno ECSV.
    import dataclasses
    from astrotwo.core.catalogs import confirm_position_columns

    path = tmp_path / "fk5.xml"
    path.write_text(VOTABLE.replace('<COOSYS ID="sys" system="ICRS" epoch="J2016.0"/>',
                                    '<COOSYS ID="sys" system="eq_FK5" equinox="J2000"/>')
                    .format(rows="<TR><TD>1</TD><TD>2</TD><TD>3</TD><TD>a</TD></TR>", status="OK"), encoding="utf-8")
    fk5 = read_table(path)
    back = read_table(export_table(fk5, tmp_path / "fk5.ecsv", "ecsv"))
    assert (back.positions.frame, back.positions.equinox) == ("fk5", "J2000")
    plain = dataclasses.replace(fk5, table=Table({"x": [1.0, 2.0], "y": [3.0, 4.0]}), positions=None, body=None)
    confirmed = confirm_position_columns(plain, "x", "y", "galactic", unit=u.deg)
    again = read_table(export_table(confirmed, tmp_path / "c.ecsv", "ecsv"))
    assert (again.positions.lon, again.positions.frame, again.positions.source) == ("x", "galactic", "confirmed")
    assert again.body == "celestial"


def test_fits_and_csv_provenance(tmp_path, catalog):
    fits_path = export_table(catalog, tmp_path / "t.fits", "fits")
    header = fits.getheader(fits_path, 1)
    assert header["A2VERS"] == f"AstroTwo {astrotwo.__version__}" and header["A2ORIGIN"] == catalog.origin
    assert header["A2FORMAT"] == "FITS Standard 4.0" and header["TUCD1"] == "pos.eq.ra;meta.main"
    assert header["A2WRITER"] == f"astropy {astropy.__version__}"
    csv_path = export_table(catalog, tmp_path / "t.csv", "csv").path
    head = csv_path.read_text(encoding="utf-8").splitlines()
    assert head[0] == f"# A2VERS = AstroTwo {astrotwo.__version__}"
    assert f"# A2ORIGIN = {catalog.origin}" in head and head[head.index("RA,DE,Vmag,Name") - 1].startswith("#")


def test_export_errors(tmp_path, catalog):
    with pytest.raises(VoProtocolsError) as err:
        export_table(catalog, tmp_path / "t.txt", "xlsx")
    assert err.value.code == "EXPORT_FORMAT_UNSUPPORTED" and "csv" in err.value.message
    path = export_table(catalog, tmp_path / "t.xml", "votable").path
    with pytest.raises(VoProtocolsError) as err:
        export_table(catalog, path, "votable")
    assert err.value.code == "FILE_EXISTS"
    assert export_table(catalog, path, "fits", overwrite=True).path == path
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
    # Servizio SCS pubblico (IRSA, AllWISE); atteso ricalcolato con pyvo contro lo stesso servizio.
    url = "https://irsa.ipac.caltech.edu/SCS?table=allwise_p3as_psd"  # pagina ufficiale IRSA (TAP.html)
    center = SkyCoord(210.80225 * u.deg, 54.34894 * u.deg, frame="icrs")
    result = cone_search(center, 10 * u.arcsec, url, cache=cache)
    expected = pyvo.dal.SCSService(url).search(center, 10 * u.arcsec)
    assert result.table.rows == len(expected) and result.request.rows == len(expected)


# =============================================================================
# P4 — Elenco dei server, registro VO, DataLink (T17, T18, T19)
# =============================================================================


def test_t17_server_registry(service, cache):
    registry = ServerRegistry()
    assert registry.builtin == BUILTIN_SERVERS and len(BUILTIN_SERVERS) >= 5
    for entry in BUILTIN_SERVERS:
        assert entry.provider and entry.protocol in ("scs", "tap", "sia", "sia2", "ssa")
        assert entry.url.startswith("https://") and entry.source.startswith("https://") and entry.verified
    assert len({e.id for e in BUILTIN_SERVERS}) == len(BUILTIN_SERVERS)
    assert {e.provider for e in BUILTIN_SERVERS} >= {"CDS", "ESA"}
    mine = registry.add_personal("mio-scs", "Il mio cone search", "scs", service.url + "/scs")
    assert mine.personal and registry.get("mio-scs") == mine and registry.personal_servers() == (mine,)
    assert mine in registry.find(protocol="scs")
    with pytest.raises(ValueError):
        registry.add_personal("mio-scs", "doppio", "scs", service.url + "/scs")
    with pytest.raises(ValueError):
        registry.add_personal("x", "x", "ftp", service.url)
    service.routes["/scs"] = votable_route(votable_text(2))
    result = cone_search(SkyCoord(10 * u.deg, -3 * u.deg), 5 * u.arcsec, "mio-scs", servers=registry, cache=cache)
    assert result.table.rows == 2 and result.request.arguments["catalog"] == "mio-scs"
    with pytest.raises(VoProtocolsError) as err:
        cone_search(SkyCoord(10 * u.deg, -3 * u.deg), 5 * u.arcsec, "cds-simbad-tap", cache=cache)
    assert err.value.code == "SERVER_UNKNOWN" and "tap" in err.value.message
    registry.remove_personal("mio-scs")
    with pytest.raises(VoProtocolsError) as err:
        registry.get("mio-scs")
    assert err.value.code == "SERVER_UNKNOWN"
    # una voce TAP dell'elenco come servizio di tap_query (URL della voce)
    service.routes["/tap/sync"] = tap_sync_route(3)
    registry.add_personal("mio-tap", "Il mio TAP", "tap", service.url + "/tap/")
    assert tap_query("mio-tap", "SELECT * FROM t", servers=registry, cache=cache).table.rows == 3


REGTAP = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>
<TABLE>
<FIELD name="ivoid" datatype="char" arraysize="*"/>
<FIELD name="res_title" datatype="char" arraysize="*"/>
<FIELD name="access_urls" datatype="char" arraysize="*"/>
<FIELD name="standard_ids" datatype="char" arraysize="*"/>
<FIELD name="intf_roles" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>
<TR><TD>ivo://esavo/gaia/tap</TD><TD>Gaia TAP</TD>
<TD>https://gea.esac.esa.int/tap-server/tap:::py VO sep:::https://gea.esac.esa.int/tap-server/tap/tables</TD>
<TD>ivo://ivoa.net/std/TAP:::py VO sep:::ivo://ivoa.net/std/VOSI#tables-1.1</TD>
<TD>std:::py VO sep:::std</TD></TR>
<TR><TD>ivo://example/aux</TD><TD>Ausiliario</TD><TD>https://example.org/tap</TD>
<TD>ivo://ivoa.net/std/TAP#aux</TD><TD></TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""


def test_t18_registry_search(service, cache):
    service.routes["/reg/sync"] = votable_route(REGTAP)
    assert vo.DEFAULT_REGISTRY_URL.startswith("https://")  # nessun default senza HTTPS
    found = ServerRegistry().search_registry(["gaia"], "tap", registry_url=service.url + "/reg", cache=cache)
    sent = service.requests[-1]["params"]["QUERY"]
    expected_adql = pyvo.registry.regtap.get_RegTAP_query(keywords=["gaia"], servicetype="tap")
    assert sent == expected_adql  # ADQL RegTAP costruito da pyvo
    assert [(s.url, s.protocol, s.source) for s in found.services] == [
        ("https://gea.esac.esa.int/tap-server/tap", "tap", "registro VO")]
    assert found.result.request.protocol == "tap" and found.result.table.rows == 2


DATALINK = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>
<TABLE>
<FIELD name="ID" datatype="char" arraysize="*" ucd="meta.id;meta.main"/>
<FIELD name="access_url" datatype="char" arraysize="*" ucd="meta.ref.url"/>
<FIELD name="service_def" datatype="char" arraysize="*" ucd="meta.ref"/>
<FIELD name="error_message" datatype="char" arraysize="*" ucd="meta.code.error"/>
<FIELD name="semantics" datatype="char" arraysize="*" ucd="meta.code"/>
<FIELD name="description" datatype="char" arraysize="*" ucd="meta.note"/>
<FIELD name="content_type" datatype="char" arraysize="*" ucd="meta.code.mime"/>
<FIELD name="content_length" datatype="long" unit="byte" ucd="phys.size;meta.file"/>
<DATA><TABLEDATA>
<TR><TD>ivo://x/obs?1</TD><TD>{url}/data/1.fits</TD><TD></TD><TD></TD><TD>#this</TD><TD>immagine</TD>
<TD>image/fits</TD><TD>2880</TD></TR>
<TR><TD>ivo://x/obs?1</TD><TD></TD><TD>soda</TD><TD></TD><TD>#cutout</TD><TD>ritaglio</TD>
<TD>image/fits</TD><TD></TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE>
<RESOURCE type="meta" utype="adhoc:service" ID="soda">
<PARAM name="standardID" datatype="char" arraysize="*" value="ivo://ivoa.net/std/SODA#sync-1"/>
<PARAM name="accessURL" datatype="char" arraysize="*" value="{url}/soda"/>
<GROUP name="inputParams">
<PARAM name="ID" datatype="char" arraysize="*" value="ivo://x/obs?1"/>
<PARAM name="CIRCLE" datatype="double" arraysize="3" unit="deg" ucd="obs.field" value="">
<VALUES><MIN value="0"/><MAX value="360"/></VALUES></PARAM>
<PARAM name="RESPONSEFORMAT" datatype="char" arraysize="*" value="">
<VALUES><OPTION value="image/fits"/><OPTION value="application/fits"/></VALUES></PARAM>
</GROUP>
</RESOURCE>
</VOTABLE>
"""


def test_t19_datalink(service, cache):
    service.routes["/links"] = votable_route(DATALINK.format(url=service.url))
    service.routes["/soda"] = lambda r: (200, "image/fits", b"SIMPLE  =                    T")
    client = DataLinkClient(cache=cache)
    links = client.links(service.url + "/links")
    expected = pyvo.dal.adhoc.DatalinkResults(
        parse_votable(io.BytesIO(DATALINK.format(url=service.url).encode())))  # ricalcolo con pyvo
    assert links.table.rows == len(expected) == 2
    assert [str(v) for v in links.table.table["semantics"]] == [r.semantics for r in expected]
    assert str(links.table.table["access_url"][0]) == expected[0].access_url
    soda = links.descriptor("soda")
    assert soda.standard_id == "ivo://ivoa.net/std/SODA#sync-1" and soda.access_url == service.url + "/soda"
    assert [p.name for p in soda.params] == ["ID", "CIRCLE", "RESPONSEFORMAT"]
    circle = soda.params[1]
    assert circle.unit == "deg" and circle.value is None and (circle.minimum, circle.maximum) == ("0.0", "360.0")
    assert soda.params[2].options == ("image/fits", "application/fits") and not soda.is_datalink
    product = client.call_service(soda, CIRCLE="10.5 -3.2 0.01")
    params = service.requests[-1]["params"]
    assert params == {"ID": "ivo://x/obs?1", "CIRCLE": "10.5 -3.2 0.01"}  # vuoti non inviati
    assert product.payload.startswith(b"SIMPLE") and product.request.protocol == "datalink-service"
    with pytest.raises(ValueError):
        client.call_service(soda, BAND="1 2")
    service.routes["/bad"] = votable_route(votable_text(1))
    with pytest.raises(VoProtocolsError) as err:
        client.links(service.url + "/bad")
    assert err.value.code == "VOTABLE_INVALID"


@pytest.mark.network
def test_t18_registry_network(cache):
    # Registro di default: RegTAP del GAVO in HTTPS (il default di pyvo, http://reg.g-vo.org/tap, non ha HTTPS
    # valido ed è rifiutato da questa rete con "Request Denied": vedi il registro modifiche del 14).
    assert vo.DEFAULT_REGISTRY_URL == "https://dc.g-vo.org/tap"
    found = ServerRegistry().search_registry(["gaia"], "tap", max_rows=200, cache=cache)
    assert found.result.request.url.startswith("https://dc.g-vo.org/tap")
    assert found.services and all(s.protocol == "tap" and s.url.startswith("http") for s in found.services)


# =============================================================================
# P5 — SIA/SIA2, IDHA, SSA (T9–T12, T15, T16)
# =============================================================================

SIA1 = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>
<TABLE>
<FIELD name="title" datatype="char" arraysize="*" ucd="VOX:Image_Title"/>
<FIELD name="ra" datatype="double" unit="deg" ucd="POS_EQ_RA_MAIN"/>
<FIELD name="dec" datatype="double" unit="deg" ucd="POS_EQ_DEC_MAIN"/>
<FIELD name="format" datatype="char" arraysize="*" ucd="VOX:Image_Format"/>
<FIELD name="url" datatype="char" arraysize="*" ucd="VOX:Image_AccessReference"/>
<FIELD name="crpix" datatype="double" arraysize="2" ucd="VOX:WCS_CoordRefPixel"/>
<FIELD name="crval" datatype="double" arraysize="2" unit="deg" ucd="VOX:WCS_CoordRefValue"/>
<DATA><TABLEDATA>
{rows}
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""


def sia1_text(n):
    rows = "".join(f"<TR><TD>img{k}</TD><TD>{10 + k}</TD><TD>20</TD><TD>image/fits</TD>"
                   f"<TD>http://example.org/img{k}.fits</TD><TD>50 50</TD><TD>{10 + k} 20</TD></TR>" for k in range(n))
    return SIA1.format(rows=rows)


def test_t11_sia(service, cache):
    service.routes["/sia"] = votable_route(sia1_text(2))
    center = SkyCoord(10 * u.deg, 20 * u.deg)
    result = sia_search(center, 0.1 * u.deg, version=1, service=service.url + "/sia", cache=cache)
    params = service.requests[-1]["params"]
    assert params["POS"] == "10.0,20.0" and float(params["SIZE"]) == pytest.approx(0.2)  # lato = 2 × raggio
    expected = pyvo.dal.SIAResults(parse_votable(io.BytesIO(sia1_text(2).encode())))  # ricalcolo con pyvo
    assert result.table.rows == len(expected) == 2
    assert [str(v) for v in result.table.table["url"]] == [r.acref for r in expected]
    assert [str(v) for v in result.table.table["format"]] == [r.format for r in expected]
    assert list(result.table.table["crval"][1]) == [11.0, 20.0]  # calibrazione della lista conservata
    assert result.request.protocol == "sia" and result.table.origin == service.url + "/sia"
    service.routes["/sia"] = votable_route(sia1_text(0))
    empty = sia_search(center, 0.1 * u.deg, version=1, service=service.url + "/sia", cache=cache, refresh=True)
    assert empty.table.rows == 0 and "SIA_NO_RESULT" in dict(empty.warnings)
    service.routes["/sia"] = lambda r: (200, "text/xml", "<VOTABLE><RESOURCE>")
    with pytest.raises(VoProtocolsError) as err:
        sia_search(center, 0.1 * u.deg, version=1, service=service.url + "/sia", cache=cache, refresh=True)
    assert err.value.code == "SIA_INVALID"
    with pytest.raises(ValueError):
        sia_search(center, 0.1 * u.deg, version=1, service=service.url + "/sia", band=[1, 2] * u.m)


SIA1_WCS = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>
<TABLE>
<FIELD name="title" datatype="char" arraysize="*" ucd="VOX:Image_Title"/>
<FIELD name="url" datatype="char" arraysize="*" ucd="VOX:Image_AccessReference"/>
<FIELD name="format" datatype="char" arraysize="*" ucd="VOX:Image_Format"/>
<FIELD name="naxis" datatype="int" arraysize="*" ucd="VOX:Image_Naxis"/>
<FIELD name="frame" datatype="char" arraysize="*" ucd="VOX:STC_CoordRefFrame"/>
<FIELD name="equinox" datatype="double" ucd="VOX:STC_CoordEquinox"/>
<FIELD name="proj" datatype="char" arraysize="3" ucd="VOX:WCS_CoordProjection"/>
<FIELD name="crpix" datatype="double" arraysize="2" ucd="VOX:WCS_CoordRefPixel"/>
<FIELD name="crval" datatype="double" arraysize="2" unit="deg" ucd="VOX:WCS_CoordRefValue"/>
<FIELD name="cd" datatype="double" arraysize="4" ucd="VOX:WCS_CDMatrix"/>
<DATA><TABLEDATA>
{rows}
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""
SIA1_WCS_ROWS = (
    # (url, naxis, frame, equinox, proiezione)
    ("/img.fits", "40 30", "ICRS", "", "TAN"),
    ("/img.fits", "40 30", "FK5", "", "TAN"),  # FK5 senza equinozio: mai assunto
    ("/img.fits", "40 30", "ECL", "", "TAN"),  # sistema non tradotto
    ("/img.fits", "41 30", "FK5", "2000", "SIN"),  # dimensioni diverse dall'immagine
)


def sia1_wcs_text(base):
    rows = "".join(f"<TR><TD>i{k}</TD><TD>{base}{url}</TD><TD>image/fits</TD><TD>{naxis}</TD><TD>{frame}</TD>"
                   f"<TD>{equinox}</TD><TD>{proj}</TD><TD>20.5 15.5</TD><TD>10 20</TD>"
                   f"<TD>-0.001 0.0002 0.0003 0.001</TD></TR>"
                   for k, (url, naxis, frame, equinox, proj) in enumerate(SIA1_WCS_ROWS))
    return SIA1_WCS.format(rows=rows)


def test_t11_sia_calibration_used_by_11(service, cache):
    from astropy.wcs import WCS
    from astrotwo.core.images_fits import load_image

    service.routes["/sia"] = votable_route(sia1_wcs_text(service.url))
    buffer = io.BytesIO()
    fits.PrimaryHDU(np.arange(30 * 40, dtype=np.float32).reshape(30, 40)).writeto(buffer)  # senza WCS
    service.routes["/img.fits"] = lambda r: (200, "application/fits", buffer.getvalue())
    result = sia_search(SkyCoord(10 * u.deg, 20 * u.deg), 0.1 * u.deg, version=1, service=service.url + "/sia",
                        cache=cache)
    calibration = vo.sia_calibration(result, 0)
    assert calibration.reason is None and "riga 0" in calibration.source
    h = calibration.header
    assert (h["CTYPE1"], h["CTYPE2"], h["RADESYS"]) == ("RA---TAN", "DEC--TAN", "ICRS")
    assert (h["CRPIX1"], h["CRPIX2"], h["CRVAL1"], h["CRVAL2"]) == (20.5, 15.5, 10.0, 20.0)
    assert [h[k] for k in ("CD1_1", "CD1_2", "CD2_1", "CD2_2")] == [-0.001, 0.0002, 0.0003, 0.001]
    url = str(result.table.table["url"][0])
    image = load_image(url, cache=cache, calibration=calibration)
    codes = [c for c, _ in image.warnings]
    assert "EXTERNAL_CALIBRATION_USED" in codes and image.calibration_source == "external"
    # Ricalcolo con astropy dall'intestazione scritta nel test (CRPIX in convenzione FITS: pixel 1 = indice 0).
    expected = WCS(fits.Header({"CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN", "CRPIX1": 20.5, "CRPIX2": 15.5,
                                "CRVAL1": 10.0, "CRVAL2": 20.0, "CD1_1": -0.001, "CD1_2": 0.0002,
                                "CD2_1": 0.0003, "CD2_2": 0.001, "RADESYS": "ICRS"}))
    x, y = np.array([0.0, 19.5, 39.0]), np.array([0.0, 14.5, 29.0])
    assert np.allclose(image.wcs.wcs.pixel_to_world_values(x, y), expected.pixel_to_world_values(x, y), atol=1e-12)
    # Righe senza i dati necessari: nessuna calibrazione, con il motivo; l'11 lo dichiara.
    assert "equinozio" in vo.sia_calibration(result, 1).reason and vo.sia_calibration(result, 1).header is None
    assert "ECL" in vo.sia_calibration(result, 2).reason
    plain = load_image(url, cache=cache, calibration=vo.sia_calibration(result, 1))
    assert plain.wcs is None and any("non disponibile" in m for c, m in plain.warnings if c == "WCS_MISSING")
    wrong_size = load_image(url, cache=cache, calibration=vo.sia_calibration(result, 3))
    assert wrong_size.wcs is None and any("NAXIS1/NAXIS2 = 41/30" in m for c, m in wrong_size.warnings)
    # Immagine con calibrazione propria: la esterna si ignora, dichiarato.
    own = io.BytesIO()
    fits.PrimaryHDU(np.zeros((30, 40), dtype=np.float32), header=expected.to_header()).writeto(own)
    service.routes["/own.fits"] = lambda r: (200, "application/fits", own.getvalue())
    kept = load_image(service.url + "/own.fits", cache=cache, calibration=calibration)
    assert "EXTERNAL_CALIBRATION_IGNORED" in [c for c, _ in kept.warnings] and kept.calibration_source is None
    with pytest.raises(IndexError):
        vo.sia_calibration(result, 9)


def test_t12_sia2_band_time(service, cache):
    service.routes["/sia2"] = votable_route(sia1_text(1))
    start, end = Time("2020-01-01T00:00:00", scale="tt"), Time("2020-02-01T00:00:00", scale="tt")
    sia_search(SkyCoord(10 * u.deg, 20 * u.deg), 6 * u.arcmin, version=2, service=service.url + "/sia2",
               band=[700, 400] * u.nm, time=(start, end), max_rows=9, cache=cache)
    params = service.requests[-1]["params"]
    ra, dec, r = (float(v) for v in params["POS"].split()[1:])
    assert params["POS"].startswith("CIRCLE") and (ra, dec) == (10.0, 20.0) and r == pytest.approx(0.1)
    band = [float(v) for v in params["BAND"].split()]
    assert band == pytest.approx([(400 * u.nm).to_value(u.m), (700 * u.nm).to_value(u.m)])  # metri (SIA 2.0)
    t0, t1 = (float(v) for v in params["TIME"].split())
    assert t0 == pytest.approx(start.utc.mjd, abs=1e-9) and t1 == pytest.approx(end.utc.mjd, abs=1e-9)  # UTC
    assert t0 != pytest.approx(start.mjd, abs=1e-6)  # la scala TT è stata convertita, non ignorata
    assert params["MAXREC"] == "9"
    with pytest.raises(TypeError):
        sia_search(SkyCoord(10 * u.deg, 20 * u.deg), 6 * u.arcmin, version=2, service=service.url + "/sia2",
                   time=(58000, 58001))
    with pytest.raises(TypeError):
        sia_search(SkyCoord(10 * u.deg, 20 * u.deg), 6 * u.arcmin, version=2, service=service.url + "/sia2",
                   band=[1, 2] * u.s)


SSA_RESULTS = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>
<COOSYS ID="sys" system="ICRS"/>
<TABLE>
<FIELD name="title" datatype="char" arraysize="*" utype="ssa:DataID.Title"/>
<FIELD name="ra" datatype="double" unit="deg" ucd="pos.eq.ra;meta.main" ref="sys"/>
<FIELD name="dec" datatype="double" unit="deg" ucd="pos.eq.dec;meta.main" ref="sys"/>
<FIELD name="acref" datatype="char" arraysize="*" ucd="meta.ref.url" utype="ssa:Access.Reference"/>
<FIELD name="fmt" datatype="char" arraysize="*" utype="ssa:Access.Format"/>
<DATA><TABLEDATA>
<TR><TD>spettro VOTable</TD><TD>10</TD><TD>20</TD><TD>{url}/spec.xml</TD><TD>application/x-votable+xml</TD></TR>
<TR><TD>spettro FITS</TD><TD>10</TD><TD>20</TD><TD>{url}/spec.fits</TD><TD>application/fits</TD></TR>
<TR><TD>senza unità</TD><TD>10</TD><TD>20</TD><TD>{url}/bad.xml</TD><TD>application/x-votable+xml</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""

SPECTRUM = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE utype="spec:Spectrum"><TABLE utype="spec:Spectrum">
<FIELD name="WAVE" datatype="double" {unit} ucd="em.wl" utype="spec:Spectrum.Data.SpectralAxis.Value"/>
<FIELD name="FLUX" datatype="double" unit="erg/(s.cm**2.Angstrom)" ucd="phot.flux.density;em.wl"
 utype="spec:Spectrum.Data.FluxAxis.Value"/>
<FIELD name="ERR" datatype="double" unit="erg/(s.cm**2.Angstrom)"
 utype="spec:Spectrum.Data.FluxAxis.Accuracy.StatError"/>
<DATA><TABLEDATA>
<TR><TD>4000.5</TD><TD>1.5e-15</TD><TD>1e-17</TD></TR>
<TR><TD>4001.5</TD><TD>1.7e-15</TD><TD>2e-17</TD></TR>
<TR><TD>4002.5</TD><TD>1.6e-15</TD><TD>1e-17</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""


def fits_spectrum():
    t = Table({"lambda": np.array([[5000.0, 5001.0, 5002.0, 5003.0]]),
               "f": np.array([[1.0, 2.0, 3.0, 4.0]])})  # una riga di colonne vettoriali
    t["lambda"].unit, t["f"].unit = u.AA, u.Jy
    hdu = fits.table_to_hdu(t)
    hdu.header["TUCD1"], hdu.header["TUCD2"] = "em.wl", "phot.flux.density;em.wl"
    buffer = io.BytesIO()
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(buffer)
    return buffer.getvalue()


def ssa_service(service):
    service.routes["/ssa"] = votable_route(SSA_RESULTS.format(url=service.url))
    service.routes["/spec.xml"] = votable_route(SPECTRUM.format(unit='unit="Angstrom"'))
    service.routes["/bad.xml"] = votable_route(SPECTRUM.format(unit=""))
    service.routes["/spec.fits"] = lambda r: (200, "application/fits", fits_spectrum())


def test_t9_ssa_search_and_load(service, cache):
    ssa_service(service)
    found = ssa_search(SkyCoord(10 * u.deg, 20 * u.deg), 5 * u.arcsec, service=service.url + "/ssa", cache=cache)
    params = service.requests[-1]["params"]
    assert params["POS"] == "10.0,20.0" and float(params["SIZE"]) == pytest.approx((10 * u.arcsec).to_value(u.deg))
    assert params["REQUEST"] == "queryData" and found.table.rows == 3 and found.table.body == "celestial"
    spec = ssa_load(found, 0, cache=cache)
    expected = parse_votable(io.BytesIO(SPECTRUM.format(unit='unit="Angstrom"').encode())).get_first_table().to_table()
    assert spec.format == "votable" and spec.spectral_kind == "wavelength" and spec.body == "celestial"
    assert np.array_equal(spec.table["spectral"], expected["WAVE"]) and spec.table["spectral"].unit == u.AA
    assert np.array_equal(spec.table["flux"], expected["FLUX"]) and spec.table["flux"].unit == expected["FLUX"].unit
    assert np.array_equal(spec.table["flux_error"], expected["ERR"])
    assert spec.origin == service.url + "/spec.xml" and spec.request.protocol == "ssa-spectrum"
    fits_spec = ssa_load(found, 1, cache=cache)
    expected_fits = Table.read(io.BytesIO(fits_spectrum()), hdu=1)
    assert fits_spec.format == "fits" and fits_spec.columns == {"spectral": "lambda", "flux": "f", "flux_error": None}
    assert np.array_equal(fits_spec.table["spectral"], expected_fits["lambda"][0])
    assert fits_spec.table["flux"].unit == u.Jy and len(fits_spec.table) == 4
    direct = ssa_load(service.url + "/spec.xml", cache=cache)
    assert direct.body is None and "BODY_UNKNOWN" in dict(direct.warnings) and direct.from_cache


def test_t10_ssa_invalid(service, cache):
    ssa_service(service)
    found = ssa_search(SkyCoord(10 * u.deg, 20 * u.deg), 5 * u.arcsec, service=service.url + "/ssa", cache=cache)
    with pytest.raises(VoProtocolsError) as err:
        ssa_load(found, 2, cache=cache)
    assert err.value.code == "SSA_INVALID" and "WAVE" in err.value.message
    service.routes["/plain.xml"] = votable_route(votable_text(3))  # tabella senza Spectrum DM
    with pytest.raises(VoProtocolsError) as err:
        ssa_load(service.url + "/plain.xml", cache=cache)
    assert err.value.code == "SSA_INVALID"
    service.routes["/spec.csv"] = lambda r: (200, "text/csv", "a,b\n1,2\n")
    with pytest.raises(VoProtocolsError) as err:
        ssa_load(service.url + "/spec.csv", cache=cache)
    assert err.value.code == "SSA_INVALID"
    service.routes["/ssa"] = votable_route(SSA_RESULTS.format(url=service.url).replace(
        SSA_RESULTS.format(url=service.url)[SSA_RESULTS.format(url=service.url).index("<TR>"):
                                            SSA_RESULTS.format(url=service.url).index("</TABLEDATA>")], ""))
    empty = ssa_search(SkyCoord(10 * u.deg, 20 * u.deg), 5 * u.arcsec, service=service.url + "/ssa", cache=cache,
                       refresh=True)
    assert empty.table.rows == 0 and "SSA_NO_RESULT" in dict(empty.warnings)


def test_t15_idha_unreadable(tmp_path):
    path = tmp_path / "lista.xml"
    path.write_text('<?xml version="1.0"?><IDHA><Image name="x"/></IDHA>', encoding="utf-8")
    with pytest.raises(VoProtocolsError) as err:
        read_idha(path)
    assert err.value.code == "IDHA_UNREADABLE" and "documentazione" in err.value.message
    broken = tmp_path / "rotto.xml"
    broken.write_text("<IDHA><Image>", encoding="utf-8")
    with pytest.raises(VoProtocolsError) as err:
        read_idha(broken)
    assert err.value.code == "IDHA_UNREADABLE"


def test_t16_idha_unsafe_xml(tmp_path):
    path = tmp_path / "bomba.xml"
    path.write_text('<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
                    "<IDHA>&b;</IDHA>", encoding="utf-8")
    with pytest.raises(VoProtocolsError) as err:
        read_idha(path)
    assert err.value.code == "XML_UNSAFE"


# =============================================================================
# P6 — Puntatore Simbad e fotometria VizieR (T13, T14)
# =============================================================================


def simbad_table(rows):
    t = Table(rows=rows, names=("main_id", "ra", "dec", "otype", "nbref"), dtype=(str, float, float, str, int))
    t["ra"].unit = t["dec"].unit = u.deg
    return t


FLUX = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>
<TABLE>
<FIELD name="filter" datatype="char" arraysize="*"/>
<FIELD name="flux" datatype="float"/>
<FIELD name="flux_err" datatype="float"/>
<FIELD name="system" datatype="char" arraysize="1"/>
<FIELD name="qual" datatype="char" arraysize="1"/>
<FIELD name="bibcode" datatype="char" arraysize="19"/>
<FIELD name="description" datatype="unicodeChar" arraysize="*"/>
<FIELD name="unit" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>
<TR><TD>G</TD><TD>17.5</TD><TD>0.003</TD><TD>V</TD><TD>C</TD><TD>2020yCat.1350....0G</TD><TD>Magnitude Gaia G</TD><TD>mag</TD></TR>
<TR><TD>g</TD><TD>18.1</TD><TD></TD><TD>A</TD><TD>D</TD><TD>2017yCat.2349....0C</TD><TD>Magnitude SDSS g</TD><TD>mag</TD></TR>
<TR><TD>V</TD><TD>17.9</TD><TD></TD><TD></TD><TD>E</TD><TD></TD><TD>Magnitude V</TD><TD>mag</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""


@pytest.fixture
def simbad_tap(service, monkeypatch):
    """TAP di SIMBAD simulato per le magnitudini (D14-12)."""
    service.routes["/simbad/sync"] = lambda r: (200, "application/x-votable+xml", FLUX)
    monkeypatch.setattr(vo, "_SIMBAD_TAP", service.url + "/simbad")
    return service


def test_t13_simbad_pointer(monkeypatch, cache, simbad_tap):
    calls = []

    def fake(ra, dec, radius_deg, timeouts):
        calls.append((ra, dec, radius_deg))
        return simbad_table([("A", 10.0, 20.0, "Star", 12), ("B", 10.001, 20.0, "QSO", 340)]), "https://simbad/tap"

    monkeypatch.setattr(vo, "_query_simbad_region", fake)
    center = SkyCoord(10 * u.deg, 20 * u.deg)
    result = simbad_pointer(center, 30 * u.arcsec, cache=cache)
    obj = result.object
    assert obj.main_id == "B" and obj.nbref == 340 and obj.otype == "QSO" and result.candidates == 2
    expected = SkyCoord(10 * u.deg, 20 * u.deg).separation(SkyCoord(10.001 * u.deg, 20 * u.deg))  # astropy
    assert obj.separation.to_value(u.arcsec) == pytest.approx(expected.arcsec, rel=1e-12)
    assert obj.coords.frame_name == "icrs" and obj.coords.epoch == Time("J2000.0")
    assert "SIMBAD" in result.source and result.request.url == "https://simbad/tap" and not result.request.from_cache
    assert calls[0][2] == pytest.approx((30 * u.arcsec).to_value(u.deg))
    # Tutte le magnitudini, con banda e sistema come dichiarati da SIMBAD (D14-12).
    query = simbad_tap.requests[-1]["params"]["QUERY"]
    assert "b.main_id = 'B'" in query and "JOIN filter" in query
    mags = {m.band: m for m in obj.magnitudes}
    assert set(mags) == {"G", "g", "V"}
    assert (mags["G"].value, mags["G"].error, mags["G"].system, mags["G"].unit) == (pytest.approx(17.5),
                                                                                    pytest.approx(0.003), "Vega", "mag")
    assert mags["G"].description == "Magnitude Gaia G" and mags["G"].bibcode == "2020yCat.1350....0G"
    assert mags["g"].system == "AB" and mags["g"].error is None
    assert mags["V"].system is None and "V" in dict(result.warnings)["SIMBAD_SYSTEM_UNDECLARED"]
    assert result.magnitudes_request.protocol == "tap" and result.magnitudes_request.rows == 3
    again = simbad_pointer(center, 30 * u.arcsec, cache=cache)
    assert again.request.from_cache and again.object.main_id == "B" and len(calls) == 1
    assert again.magnitudes_request.from_cache and len(again.object.magnitudes) == 3


def test_simbad_pointer_tie_and_empty(monkeypatch, cache, simbad_tap):
    monkeypatch.setattr(vo, "_query_simbad_region", lambda ra, dec, r, t: (simbad_table(
        [("lontano", 10.002, 20.0, "Star", 50), ("vicino", 10.0005, 20.0, "Star", 50), ("poco", 10.0, 20.0, "G", 3)]),
        "https://simbad/tap"))
    result = simbad_pointer(SkyCoord(10 * u.deg, 20 * u.deg), 30 * u.arcsec, cache=cache)
    assert result.object.main_id == "vicino" and "SIMBAD_TIE" in dict(result.warnings)
    monkeypatch.setattr(vo, "_query_simbad_region", lambda ra, dec, r, t: (simbad_table([]), "https://simbad/tap"))
    empty = simbad_pointer(SkyCoord(11 * u.deg, 20 * u.deg), 30 * u.arcsec, cache=cache)
    assert empty.object is None and "SIMBAD_NO_OBJECT" in dict(empty.warnings)
    with pytest.raises(TypeError):
        simbad_pointer(SkyCoord(11 * u.deg, 20 * u.deg), 30, cache=cache)  # raggio sempre esplicito, con unità


SED = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE>
<COOSYS ID="J2000" system="eq_FK5" equinox="J2000"/>
<TIMESYS ID="time_1" refposition="BARYCENTER" timeorigin="0.000000" timescale="TCB"/>
<TABLE name="allVizieR">
<FIELD name="_RAJ2000" ucd="pos.eq.ra" ref="J2000" datatype="double" unit="deg"/>
<FIELD name="_DEJ2000" ucd="pos.eq.dec" ref="J2000" datatype="double" unit="deg"/>
<FIELD name="_tabname" ucd="meta.table" datatype="char" arraysize="32*"/>
<FIELD name="_ID" ucd="meta.id" datatype="char" arraysize="128*"/>
<FIELD name="_time" ucd="time.epoch" ref="time_1" datatype="double" unit="d"/>
<FIELD ID="sed_freq" name="_sed_freq" ucd="em.freq" unit="GHz" datatype="double"/>
<FIELD ID="sed_flux" name="_sed_flux" ucd="phot.flux.density" unit="Jy" datatype="float"/>
<FIELD ID="sed_eflux" name="_sed_eflux" ucd="stat.error;phot.flux.density" unit="Jy" datatype="float"/>
<FIELD ID="sed_filter" name="_sed_filter" ucd="meta.id;instr.filter" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>
<TR><TD>10.0</TD><TD>+20.0</TD><TD>II/246/out</TD><TD>2MASS=1</TD><TD></TD><TD>136.89e+3</TD><TD>1.5</TD><TD>0.03</TD><TD>2MASS:Ks</TD></TR>
<TR><TD>10.0</TD><TD>+20.0</TD><TD>I/355/gaiadr3</TD><TD>Source=2</TD><TD>2457389.0</TD><TD>445.46e+3</TD><TD>2.5</TD><TD></TD><TD>GAIA/GAIA3:G</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""


def test_t14_vizier_photometry(service, cache, monkeypatch):
    service.routes["/sed"] = votable_route(SED)
    monkeypatch.setattr(vo, "VIZIER_PHOTOMETRY_URL", service.url + "/sed")
    result = vizier_photometry(SkyCoord(10 * u.deg, 20 * u.deg), 2 * u.arcsec, cache=cache)
    params = service.requests[-1]["params"]
    assert params == {"-c": "10.00000000 +20.00000000", "-c.rs": "2"}
    expected = parse_votable(io.BytesIO(SED.encode())).get_first_table().to_table(use_names_over_ids=True)
    table = result.table.table
    assert np.array_equal(table["_sed_freq"], expected["_sed_freq"]) and table["_sed_freq"].unit == u.GHz
    assert np.array_equal(table["_sed_flux"], expected["_sed_flux"]) and table["_sed_flux"].unit == u.Jy
    assert [str(v) for v in table["_tabname"]] == ["II/246/out", "I/355/gaiadr3"]  # catalogo d'origine
    assert bool(table["_time"].mask[0]) and table["_time"][1] == 2457389.0  # data solo quando presente
    assert table["_time"].meta["timesys"]["timescale"] == "TCB"
    assert result.request.protocol == "vizier-photometry" and result.table.body == "celestial"
    with pytest.raises(ValueError):
        vizier_photometry(SkyCoord(10 * u.deg, 20 * u.deg), 31 * u.arcsec, cache=cache)
    service.close()
    with pytest.raises(VoProtocolsError) as err:
        vizier_photometry(SkyCoord(11 * u.deg, 20 * u.deg), 2 * u.arcsec, cache=cache,
                          timeouts=NetworkTimeouts(connect=0.5, read=0.5))
    assert err.value.code == "NET_TIMEOUT"


@pytest.mark.network
def test_t13_t14_network(cache):
    vega = SkyCoord(279.2347 * u.deg, 38.7837 * u.deg)
    pointer = simbad_pointer(vega, 30 * u.arcsec, cache=cache)
    assert pointer.object is not None and pointer.object.nbref is not None and pointer.candidates >= 1
    bands = {m.band: m for m in pointer.object.magnitudes}
    assert "V" in bands and bands["V"].system in ("Vega", "AB", None) and bands["V"].unit == "mag"
    photometry = vizier_photometry(vega, 1.5 * u.arcsec, cache=cache)
    assert photometry.table.rows > 0 and photometry.table.table["_sed_flux"].unit == u.Jy


# =============================================================================
# P7 — SAMP con un hub locale nei test (T7, T8)
# =============================================================================


def wait_for(condition, timeout=10.0):
    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        if condition():
            return True
        _time.sleep(0.05)
    return False


@pytest.fixture
def samp_home(monkeypatch):
    # Cartella home temporanea (conftest): il file di blocco dell'hub (~/.samp) non tocca quello vero.
    monkeypatch.delenv("SAMP_HUB", raising=False)


@pytest.fixture
def local_hub(samp_home):
    hub = pyvo_samp.SAMPHubServer(web_profile=False)
    hub.start(wait=False)
    yield hub
    hub.stop()


@pytest.fixture
def peer(local_hub):
    """Client simulato (al posto di TOPCAT, DS9…): registra i messaggi ricevuti."""
    client = pyvo_samp.SAMPIntegratedClient(name="Simulato")
    client.connect()
    received = []
    for mtype in ("table.load.votable", "table.select.rowList", "coord.pointAt.sky"):
        client.bind_receive_notification(mtype, lambda *args: received.append(args))
    client.received = received
    yield client
    client.disconnect()


def test_t7_samp_send_table(peer, catalog):
    with SampHub() as samp:
        assert samp.connected and not samp.own_hub  # hub già attivo: nessun hub proprio
        names = {c.name for c in samp.clients()}
        assert names == {"Simulato"}
        sent = samp.send_table(catalog, table_id="t1", name="stelle")
        assert sent.recipients == (peer.get_public_id(),)
        assert wait_for(lambda: peer.received)
        params = peer.received[0][4]
        assert peer.received[0][3] == "table.load.votable" and params["table-id"] == "t1"
        path = urllib.parse.unquote(urllib.parse.urlsplit(params["url"]).path)
        got = parse_votable(path).get_first_table().to_table(use_names_over_ids=True)  # come lo legge il client
        for name in ("RA", "DE", "Vmag"):
            assert np.array_equal(np.asarray(got[name]), np.asarray(catalog.table[name])) and got[name].unit == catalog.table[name].unit


def test_t8_samp_selection_and_point(peer, catalog, tmp_path):
    with SampHub() as samp:
        tables, selections, points = [], [], []
        samp.on_table(lambda table, table_id, sender: tables.append((table, table_id, sender)))
        samp.on_selection(lambda sel, sender: selections.append(sel))
        samp.on_point(lambda pos, sender: points.append(pos))
        selection = SampSelection("t1", "file:///tmp/t.xml", (0, 2))
        samp.send_selection(selection)
        center = SkyCoord(120 * u.deg, 30 * u.deg, frame="galactic")
        samp.send_point(center)
        assert wait_for(lambda: len(peer.received) == 2)
        by_type = {m[3]: m[4] for m in peer.received}
        assert by_type["table.select.rowList"] == {"table-id": "t1", "url": "file:///tmp/t.xml", "row-list": ["0", "2"]}
        icrs = center.icrs  # ricalcolo con astropy
        assert float(by_type["coord.pointAt.sky"]["ra"]) == pytest.approx(icrs.ra.deg, abs=1e-9)
        assert float(by_type["coord.pointAt.sky"]["dec"]) == pytest.approx(icrs.dec.deg, abs=1e-9)
        # ricezione: il client simulato invia gli stessi tre tipi ad AstroTwo
        me = [c for c in peer.get_registered_clients() if c not in ("cli#hub", peer.get_public_id())][0]
        peer.notify(me, {"samp.mtype": "table.select.rowList",
                         "samp.params": {"table-id": "t1", "url": "file:///tmp/t.xml", "row-list": ["0", "2"]}})
        peer.notify(me, {"samp.mtype": "coord.pointAt.sky", "samp.params": {"ra": "10.5", "dec": "-3.25"}})
        path = tmp_path / "dal_client.xml"
        path.write_text(votable_text(2), encoding="utf-8")
        peer.notify(me, {"samp.mtype": "table.load.votable",
                         "samp.params": {"url": path.as_uri(), "table-id": "x9", "name": "dal client"}})
        assert wait_for(lambda: selections and points and tables)
        assert selections[0] == selection
        assert (points[0].lon.to_value(u.deg)[()], points[0].lat.to_value(u.deg)[()]) == (10.5, -3.25)
        assert points[0].frame_name == "icrs"
        table, table_id, _ = tables[0]
        expected = parse_votable(str(path)).get_first_table().to_table(use_names_over_ids=True)
        assert table_id == "x9" and np.array_equal(table.table["RA"], expected["RA"]) and table.positions is not None


def test_samp_own_hub_and_errors(samp_home, catalog, monkeypatch):
    with SampHub() as samp:
        assert samp.own_hub and samp._hub._web_profile is False  # hub proprio, profilo web disattivato
        assert samp.clients() == ()
        with pytest.raises(VoProtocolsError) as err:
            samp.send_table(catalog, table_id="t1")
        assert err.value.code == "SAMP_NO_PEER"
        with pytest.raises(VoProtocolsError) as err:
            samp.send_message("image.load.fits", {"url": "file:///x.fits"})
        assert err.value.code == "SAMP_UNSUPPORTED_TYPE" and "coord.pointAt.sky" in err.value.message
    assert not samp.connected
    with pytest.raises(VoProtocolsError) as err:
        samp.send_point(SkyCoord(1 * u.deg, 2 * u.deg))
    assert err.value.code == "SAMP_UNAVAILABLE"

    def fail(self, wait=False):
        raise OSError("porta non disponibile")

    monkeypatch.setattr(pyvo_samp.SAMPHubServer, "start", fail)
    with pytest.raises(VoProtocolsError) as err:
        SampHub().connect()
    assert err.value.code == "SAMP_UNAVAILABLE"
