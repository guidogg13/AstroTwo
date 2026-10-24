# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 14 con codice + ``params`` (D40-3, D40-7; ``40`` §3.7.1, T18–T19; ``14`` §10).

Provoca ogni errore e ogni avviso del modulo; ogni istanza è controllata contro il catalogo alla creazione
(``tests/conftest.py``) e qui si verifica la copertura di tutte le coppie (codice, ragione) del modulo, i messaggi
annidati e il testo italiano invariato.
"""

from __future__ import annotations

import types

import astropy.units as u
import numpy as np
import pytest
import pyvo
import pyvo.samp as pyvo_samp
import requests
from astropy.coordinates import SkyCoord
from astropy.table import MaskedColumn, Table

from astrotwo import messages_catalog as mc
from astrotwo.core import vo_protocols as vo
from astrotwo.core.cache import NetworkTimeouts
from astrotwo.core.catalogs import read_table
from astrotwo.core.coordinates_wcs import ModuleWarning
from astrotwo.core.vo_protocols import (
    DataLinkClient,
    SampHub,
    ServerRegistry,
    VoProtocolsError,
    cds_xmatch,
    cone_search,
    download_table,
    export_table,
    read_idha,
    read_votable,
    sia_search,
    simbad_pointer,
    ssa_load,
    ssa_search,
    tap_query,
    validate_adql,
    vizier_collections,
    vizier_photometry,
)
from tests.core.test_vo_protocols import (  # noqa: F401  (fixture e servizi simulati del 14)
    DATALINK,
    FLUX,
    SED,
    SPECTRUM,
    SSA_RESULTS,
    catalog,
    fits_spectrum,
    local_hub,
    samp_home,
    simbad_table,
    simbad_tap,
    sia1_text,
    ssa_service,
    tap_sync_route,
    uws_service,
    votable_route,
    votable_text,
)
from tests.message_helpers import catalog_combinations, check_error, check_message, nested_pairs

#: Codici che solo il modulo 14 solleva o restituisce (le sotto-voci aggiunte a voci condivise sono in ``SHARED``).
OWN_CODES = (
    "VOTABLE_INVALID", "EXPORT_FORMAT_UNSUPPORTED", "AUTH_REQUIRED", "ADQL_INVALID", "MAX_ROWS_INVALID",
    "MAX_SEP_INVALID", "SERVER_UNKNOWN", "SIA_INVALID", "SSA_INVALID", "IDHA_UNREADABLE", "SAMP_UNAVAILABLE",
    "SAMP_UNSUPPORTED_TYPE", "SAMP_NO_PEER", "ROW_LIMIT_EXCEEDED", "CSV_UNITS_NOT_SAVED", "SIA_NO_RESULT",
    "SSA_NO_RESULT", "ASTRORES_LINK_SOURCE", "SIMBAD_NO_OBJECT", "SIMBAD_SYSTEM_UNKNOWN", "SIMBAD_SYSTEM_UNDECLARED",
    "SIMBAD_NBREF_MISSING", "SIMBAD_TIE", "SIMBAD_NO_MAGNITUDE",
)
SHARED = {
    ("FILE_EXISTS", None), ("XML_UNSAFE", None), ("TABLE_TOO_LARGE", "upload"),
    ("NET_TIMEOUT", "url"), ("NET_TIMEOUT", "url_sync_tap"), ("NET_TIMEOUT", "async_deadline"),
    ("BODY_UNKNOWN", "spectrum_without_candidate"), ("FORMAT_DECLARED", "recognized_differs"),
} | {("SERVICE_ERROR", r) for r in (
    "http_status", "unreadable_response", "http_message", "http_message_async_hint", "http_no_votable",
    "service_rejected", "request_failed", "job_phase", "job_result_status", "descriptor_missing",
    "simbad_no_units")} | {("FROM_CACHE", r) for r in (
        "cached_origin", "network_cached", "cached_since", "network_unavailable")}


def required_combinations() -> set[tuple[str, str | None]]:
    """Coppie (codice, ragione) del 14: ogni sotto-voce; la voce generale solo dove non ha sotto-voci o è usata."""
    out = {(c, r) for c, r in catalog_combinations(OWN_CODES) if r is not None or not mc.CATALOG[c].variants}
    return out | {("SIMBAD_TIE", None)} | SHARED


class Seen:
    def __init__(self) -> None:
        self.pairs: set[tuple[str, str | None]] = set()

    def error(self, func, *args, **kwargs) -> VoProtocolsError:
        with pytest.raises(VoProtocolsError) as info:
            func(*args, **kwargs)
        self.pairs.add(check_error(info.value))
        self.pairs |= nested_pairs(info.value.code, info.value.params)
        return info.value

    def notes(self, items) -> None:
        for item in items:
            if isinstance(item, ModuleWarning):
                self.pairs.add(check_message(item[0], item.params, item[1]))
                self.pairs |= nested_pairs(item[0], item.params)


SEEN = Seen()  # coppie provocate dai due test che seguono; la copertura è verificata dal terzo
FAST = NetworkTimeouts(connect=0.5, read=0.5)
CENTER = SkyCoord(10 * u.deg, -3 * u.deg, frame="icrs")
ERROR_BODY = votable_text(0, status="ERROR").replace(
    '<INFO name="QUERY_STATUS" value="ERROR"/>', '<INFO name="QUERY_STATUS" value="ERROR">{message}</INFO>')


def test_every_error_and_warning_has_code_params_and_catalog_entry(service, cache, catalog, tmp_path, monkeypatch,  # noqa: F811
                                                                    simbad_tap, samp_home):
    seen = SEEN

    # --- P1: VOTable ed esportazione ----------------------------------------------------------------------------
    bad = tmp_path / "bad.xml"
    bad.write_text(votable_text().replace("</TABLE>", ""), encoding="utf-8")
    seen.error(read_votable, bad)  # malformed
    csv = tmp_path / "t.csv"
    csv.write_text("a,b\n1,2\n", encoding="utf-8")
    seen.error(read_votable, csv)  # other_format
    other = tmp_path / "altro.xml"  # not_votable: XML con un'altra radice, che il 13 non riconosce
    other.write_text('<?xml version="1.0"?><ALTRO/>', encoding="utf-8")
    err = seen.error(read_votable, other)
    assert err.params["reason"] == "not_votable" and err.params["cause"]["code"] == "FORMAT_UNSUPPORTED"
    err = seen.error(export_table, catalog, tmp_path / "t.txt", "xlsx")
    assert err.params == {"format": "xlsx", "allowed": list(vo.EXPORT_FORMATS)}
    path = export_table(catalog, tmp_path / "t.xml", "votable").path
    seen.error(export_table, catalog, path, "votable")  # FILE_EXISTS
    seen.notes(export_table(catalog, tmp_path / "out.csv", "csv").warnings)  # CSV_UNITS_NOT_SAVED

    # --- P2: rete di base, cache --------------------------------------------------------------------------------
    service.routes["/private"] = lambda r: (401, "text/plain", "auth")
    err = seen.error(download_table, service.url + "/private", cache=cache)
    assert err.params == {"url": service.url + "/private", "status": 401}
    err = seen.error(download_table, service.url + "/missing", cache=cache)  # http_status
    assert err.params["status"] == 404 and "404" in err.message
    service.routes["/t.xml"] = votable_route(votable_text(3))
    first = download_table(service.url + "/t.xml", cache=cache)
    seen.notes(first.warnings)
    seen.notes(download_table(service.url + "/t.xml", cache=cache).warnings)  # cached_origin
    service.routes["/garbage"] = lambda r: (200, "text/plain", "non è un VOTable")
    seen.error(cone_search, CENTER, 1 * u.arcmin, service.url + "/garbage", cache=cache)  # unreadable_response
    seen.error(sia_search, CENTER, 0.1 * u.deg, version=1, service=service.url + "/garbage", cache=cache)  # SIA_INVALID

    # --- P3: cone search e TAP ----------------------------------------------------------------------------------
    service.routes["/scs"] = votable_route(votable_text(8))
    cut = cone_search(CENTER, 1 * u.arcmin, service.url + "/scs", max_rows=3, cache=cache)
    seen.notes(cut.warnings)
    err = seen.error(cone_search, CENTER, 1 * u.arcmin, service.url + "/scs", max_rows=0, cache=cache)
    assert err.params == {"value": "0", "maximum": 1_000_000}
    seen.error(cone_search, CENTER, 1 * u.arcmin, "esa-gaia-tap", cache=cache)  # wrong_protocol
    seen.error(cone_search, CENTER, 1 * u.arcmin, "I/239/hip_main", cache=cache)  # not_listed
    service.routes["/scs"] = votable_route(votable_text(1).replace(
        '<INFO name="QUERY_STATUS" value="OK"/>', '<INFO name="Error" value="RA fuori intervallo"/>'))
    seen.error(cone_search, CENTER, 1 * u.arcmin, service.url + "/scs", cache=cache, refresh=True)  # service_rejected

    service.routes["/tap/sync"] = tap_sync_route(50)
    seen.notes(tap_query(service.url + "/tap", "SELECT * FROM stelle", max_rows=7, cache=cache).warnings)  # cut
    for adql in ("", "DELETE FROM t", "SELECT * FROM t WHERE a = 'x", "SELECT COUNT(* FROM t", "SELECT a) FROM t"):
        seen.error(tap_query, service.url + "/tap", adql, cache=cache)
    assert {p[1] for p in seen.pairs if p[0] == "ADQL_INVALID"} == {
        "empty", "not_select", "unclosed_quote", "unclosed_paren", "unmatched_close"}
    service.routes["/tap/sync"] = lambda r: (400, "application/x-votable+xml",
                                             ERROR_BODY.format(message="Table stelle_x does not exist"))
    err = seen.error(tap_query, service.url + "/tap", "SELECT * FROM stelle_x", cache=cache)
    assert err.params["reason"] == "service_rejected" and "does not exist" in err.params["detail"]
    service.routes["/tap/sync"] = lambda r: (200, "application/x-votable+xml", ERROR_BODY.format(
        message="Query execution time limit exceeded"))
    err = seen.error(tap_query, service.url + "/tap", "SELECT * FROM stelle", cache=cache)
    assert err.params["reason"] == "service_rejected_async_hint" and "mode='async'" in err.message
    service.routes["/tap/sync"] = lambda r: (503, "application/x-votable+xml", ERROR_BODY.format(message="maintenance"))
    err = seen.error(tap_query, service.url + "/tap", "SELECT * FROM stelle", cache=cache)
    assert err.params["reason"] == "http_message" and err.params["status"] == 503
    service.routes["/tap/sync"] = lambda r: (500, "application/x-votable+xml", ERROR_BODY.format(
        message="Query timed out"))
    err = seen.error(tap_query, service.url + "/tap", "SELECT * FROM stelle", cache=cache)
    assert err.params["reason"] == "http_message_async_hint"
    service.routes["/tap/sync"] = lambda r: (500, "text/plain", "boom")
    err = seen.error(tap_query, service.url + "/tap", "SELECT * FROM stelle", cache=cache)
    assert err.params["reason"] == "http_no_votable"

    def slow(request):
        import time

        time.sleep(1.0)
        return 200, "application/x-votable+xml", votable_text(1)

    service.routes["/tap/sync"] = slow
    err = seen.error(tap_query, service.url + "/tap", "SELECT * FROM stelle", cache=cache,
                     timeouts=NetworkTimeouts(connect=1.0, read=0.2))
    assert err.params["reason"] == "url_sync_tap" and err.params["read"] == {"value": 0.2, "unit": "s"}

    # TAP asincrona: attesa massima, errore del lavoro, fase diversa da COMPLETED, risultato non raggiungibile.
    uws_service(service, ["EXECUTING"])
    err = seen.error(tap_query, service.url + "/tap", "SELECT * FROM stelle", mode="async", async_timeout=0.5,
                     cache=cache)
    assert err.params["reason"] == "async_deadline" and err.params["timeout"] == {"value": 0.5, "unit": "s"}
    uws_service(service, ["ERROR"])
    seen.error(tap_query, service.url + "/tap", "SELECT * FROM stelle", mode="async", cache=cache, refresh=True)
    uws_service(service, ["ABORTED"])
    with monkeypatch.context() as patch:  # pyvo segnala già l'errore per ERROR e ABORTED: il ramo è di difesa
        patch.setattr(pyvo.dal.AsyncTAPJob, "raise_if_error", lambda self: None)
        err = seen.error(tap_query, service.url + "/tap", "SELECT * FROM stelle", mode="async", cache=cache,
                         refresh=True)
    assert err.params["reason"] == "job_phase" and err.params["phase"] == "ABORTED"
    uws_service(service, ["COMPLETED"])
    service.routes["/tap/async/1/results/result"] = lambda r: (500, "text/plain", "boom")
    err = seen.error(tap_query, service.url + "/tap", "SELECT * FROM stelle", mode="async", cache=cache, refresh=True)
    assert err.params["reason"] == "job_result_status" and err.params["status"] == 500
    uws_service(service, ["COMPLETED"])
    tap_query(service.url + "/tap", "SELECT * FROM stelle", mode="async", cache=cache, refresh=True)
    service.close()
    seen.notes(tap_query(service.url + "/tap", "SELECT * FROM stelle", mode="async", cache=cache,
                         refresh=True, timeouts=FAST).warnings)  # network_cached (cache dell'asincrona)
    seen.error(download_table, service.url + "/assente.xml", cache=cache, timeouts=FAST)  # url

    # --- P4: elenco dei server e DataLink -----------------------------------------------------------------------
    seen.error(ServerRegistry().remove_personal, "mio")  # not_personal
    seen.error(ServerRegistry().get, "nessuno")  # not_listed (anche l'elenco dei server)


def test_services_p4_to_p6(service, cache, catalog, tmp_path, monkeypatch, simbad_tap):  # noqa: F811
    seen = SEEN
    # DataLink
    service.routes["/links"] = votable_route(DATALINK.format(url=service.url))
    client = DataLinkClient(cache=cache)
    links = client.links(service.url + "/links")
    seen.error(links.descriptor, "nessuno")  # descriptor_missing
    service.routes["/bad"] = votable_route(votable_text(1))
    seen.error(client.links, service.url + "/bad")  # datalink_columns

    # SIA / SSA / IDHA
    service.routes["/sia"] = votable_route(sia1_text(0))
    seen.notes(sia_search(CENTER, 0.1 * u.deg, version=1, service=service.url + "/sia", cache=cache).warnings)
    ssa_service(service)
    found = ssa_search(SkyCoord(10 * u.deg, 20 * u.deg), 5 * u.arcsec, service=service.url + "/ssa", cache=cache)
    seen.error(ssa_load, found, 2, cache=cache)  # no_unit (la terza riga è lo spettro senza unità)
    service.routes["/plain.xml"] = votable_route(votable_text(3))
    err = seen.error(ssa_load, service.url + "/plain.xml", cache=cache)
    assert err.params["reason"] == "axes_dm" and "RA" in err.params["columns"]
    service.routes["/nolinks.fits"] = lambda r: (200, "application/fits", _fits_without_ucd())
    err = seen.error(ssa_load, service.url + "/nolinks.fits", cache=cache)
    assert err.params["reason"] == "axes_dm_ucd"
    service.routes["/spec.csv"] = lambda r: (200, "text/csv", "a,b\n1,2\n")
    err = seen.error(ssa_load, service.url + "/spec.csv", cache=cache)
    assert err.params["reason"] in ("format", "unreadable")
    service.routes["/spec.html"] = lambda r: (200, "text/html", "<html><body>errore</body></html>")
    err = seen.error(ssa_load, service.url + "/spec.html", cache=cache)
    assert err.params["reason"] == "unreadable" and err.params["cause"]["code"]
    service.routes["/scs-plain"] = votable_route(votable_text(2))
    plain = cone_search(CENTER, 1 * u.arcmin, service.url + "/scs-plain", cache=cache)
    err = seen.error(ssa_load, plain, 0, cache=cache)
    assert err.params["reason"] == "no_access_column"
    direct = ssa_load(service.url + "/spec.xml", format="image/fits", cache=cache)
    seen.notes(direct.warnings)  # spectrum_without_candidate, recognized_differs
    service.routes["/ssa-empty"] = votable_route(SSA_RESULTS.format(url=service.url).replace(
        SSA_RESULTS.format(url=service.url)[SSA_RESULTS.format(url=service.url).index("<TR>"):
                                            SSA_RESULTS.format(url=service.url).index("</TABLEDATA>")], ""))
    seen.notes(ssa_search(SkyCoord(10 * u.deg, 20 * u.deg), 5 * u.arcsec, service=service.url + "/ssa-empty",
                          cache=cache).warnings)
    xml = tmp_path / "lista.xml"
    xml.write_text('<?xml version="1.0"?><IDHA><Image name="x"/></IDHA>', encoding="utf-8")
    seen.error(read_idha, xml)  # format_unknown
    broken = tmp_path / "rotto.xml"
    broken.write_text("<IDHA><Image>", encoding="utf-8")
    seen.error(read_idha, broken)  # xml_error
    bomb = tmp_path / "bomba.xml"
    bomb.write_text('<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><IDHA>&b;</IDHA>',
                    encoding="utf-8")
    seen.error(read_idha, bomb)  # XML_UNSAFE

    # SIMBAD e fotometria VizieR
    monkeypatch.setattr(vo, "_query_simbad_region", lambda ra, dec, r, t: (simbad_table([]), "https://simbad/tap"))
    center = SkyCoord(10 * u.deg, 20 * u.deg)
    seen.notes(simbad_pointer(center, 30 * u.arcsec, cache=cache).warnings)  # SIMBAD_NO_OBJECT
    tied = simbad_table([("A", 10.002, 20.0, "Star", 50), ("B", 10.0005, 20.0, "Star", 50)])
    monkeypatch.setattr(vo, "_query_simbad_region", lambda ra, dec, r, t: (tied, "https://simbad/tap"))
    first = simbad_pointer(center, 31 * u.arcsec, cache=cache)
    seen.notes(first.warnings)  # SIMBAD_TIE, SIMBAD_SYSTEM_UNDECLARED
    seen.notes(simbad_pointer(center, 31 * u.arcsec, cache=cache).warnings)  # cached_since
    untyped = simbad_table([("A", 10.002, 20.0, "Star", 1), ("B", 10.0005, 20.0, "Star", 1)])
    untyped["nbref"] = MaskedColumn([1, 2], mask=[True, True])
    monkeypatch.setattr(vo, "_query_simbad_region", lambda ra, dec, r, t: (untyped, "https://simbad/tap2"))
    seen.notes(simbad_pointer(center, 32 * u.arcsec, cache=cache).warnings)  # SIMBAD_NBREF_MISSING, TIE nbref_missing
    service.routes["/simbad/sync"] = lambda r: (200, "application/x-votable+xml", FLUX.replace(
        "<TD>V</TD><TD>C</TD>", "<TD>Z</TD><TD>C</TD>", 1))
    other = simbad_table([("C", 11.0, 21.0, "Star", 4)])
    monkeypatch.setattr(vo, "_query_simbad_region", lambda ra, dec, r, t: (other, "https://simbad/tap3"))
    seen.notes(simbad_pointer(SkyCoord(11 * u.deg, 21 * u.deg), 30 * u.arcsec, cache=cache).warnings)  # UNKNOWN
    service.routes["/simbad/sync"] = lambda r: (200, "application/x-votable+xml", FLUX.split("<DATA>")[0]
                                                 + "<DATA><TABLEDATA></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>")
    monkeypatch.setattr(vo, "_query_simbad_region", lambda ra, dec, r, t: (
        simbad_table([("E", 11.0, 21.0, "Star", 4)]), "https://simbad/tap3"))  # altro oggetto: nessuna cache
    seen.notes(simbad_pointer(SkyCoord(11 * u.deg, 21 * u.deg), 31 * u.arcsec, cache=cache).warnings)  # NO_MAGNITUDE
    unitless = simbad_table([("D", 12.0, 22.0, "Star", 4)])
    unitless["ra"].unit = None
    monkeypatch.setattr(vo, "_query_simbad_region", lambda ra, dec, r, t: (unitless, "https://simbad/tap4"))
    seen.error(simbad_pointer, SkyCoord(12 * u.deg, 22 * u.deg), 30 * u.arcsec, cache=cache)  # simbad_no_units
    service.routes["/sed"] = votable_route(votable_text(2))
    monkeypatch.setattr(vo, "VIZIER_PHOTOMETRY_URL", service.url + "/sed")
    seen.error(vizier_photometry, CENTER, 2 * u.arcsec, cache=cache)  # photometry_columns
    service.routes["/moc"] = lambda r: (200, "application/json", "non è JSON")
    monkeypatch.setattr(vo, "MOCSERVER_URL", service.url + "/moc")
    seen.error(vizier_collections, cache=cache)  # unreadable_response del MocServer

    # CDS XMatch
    cat = Table({"idx": [1, 2], "ra": [10.0, 11.0], "dec": [20.0, 21.0]})
    seen.error(cds_xmatch, cat, cat, 200 * u.arcsec, "best", cache=cache)  # MAX_SEP_INVALID
    with monkeypatch.context() as patch:
        patch.setattr(vo, "XMATCH_MAX_UPLOAD_BYTES", 10)
        seen.error(cds_xmatch, cat, cat, 5 * u.arcsec, "best", cache=cache)  # TABLE_TOO_LARGE upload
    from astroquery.exceptions import InvalidQueryError
    from astroquery.xmatch import XMatchClass

    def answer(self, *args, **kwargs):
        return types.SimpleNamespace(content=votable_text(2).encode())

    with monkeypatch.context() as patch:
        patch.setattr(vo, "XMATCH_URL", service.url + "/xmatch")
        patch.setattr(XMatchClass, "query_async", lambda self, *a, **k: (_ for _ in ()).throw(InvalidQueryError("no")))
        seen.error(cds_xmatch, cat, cat, 5 * u.arcsec, "best", cache=cache)  # service_rejected
        patch.setattr(XMatchClass, "query_async",
                      lambda self, *a, **k: (_ for _ in ()).throw(requests.exceptions.HTTPError("HTTP 500")))
        seen.error(cds_xmatch, cat, cat, 5 * u.arcsec, "best", cache=cache)  # request_failed
        patch.setattr(XMatchClass, "query_async", answer)
        seen.notes(cds_xmatch(cat, cat, 5 * u.arcsec, "best", cache=cache).warnings)
        seen.notes(cds_xmatch(cat, cat, 5 * u.arcsec, "best", cache=cache).warnings)  # cached_since
        patch.setattr(XMatchClass, "query_async",
                      lambda self, *a, **k: (_ for _ in ()).throw(requests.exceptions.ConnectionError("giù")))
        seen.notes(cds_xmatch(cat, cat, 5 * u.arcsec, "best", cache=cache, refresh=True).warnings)  # network_unavailable

    # Dati collegati di un ASTRORES
    service.routes["/linked.xml"] = votable_route(votable_text(1))
    fetch = vo._link_fetcher(cache=cache)
    for _ in range(2):  # downloaded, poi cached
        payload, note = fetch(service.url + "/linked.xml")
        seen.notes([note])

    # SAMP
    with SampHub() as samp:
        seen.error(samp.send_table, catalog, table_id="t1")  # none
        seen.error(samp.send_message, "image.load.fits", {"url": "file:///x.fits"})  # type
        seen.error(samp.send_message, "coord.pointAt.sky", {"ra": "1", "dec": "2"}, recipient="x")  # recipient
        replies = []
        monkeypatch.setattr(samp, "_reply", lambda msg_id, error: replies.append(error))
        samp._dispatch("nessun.tipo", "id", lambda: ())
        assert isinstance(replies[0], VoProtocolsError) and replies[0].params["reason"] == "no_handler"
        seen.pairs.add(check_error(replies[0]))
    seen.error(samp.send_point, SkyCoord(1 * u.deg, 2 * u.deg))  # not_connected

    def fail(self, wait=False):
        raise OSError("porta non disponibile")

    monkeypatch.setattr(pyvo_samp.SAMPHubServer, "start", fail)
    seen.error(SampHub().connect)  # no_hub



def test_every_code_and_reason_of_the_module_is_provoked():
    """Tutte le coppie (codice, ragione) del modulo (14 §10) sono state provocate dai due test precedenti."""
    if not SEEN.pairs:
        pytest.skip("si esegue dopo i due test che provocano i messaggi")
    missing = required_combinations() - SEEN.pairs
    assert not missing, f"coppie (codice, ragione) non provocate: {sorted(missing, key=str)}"


def _fits_without_ucd() -> bytes:
    import io

    from astropy.io import fits

    t = Table({"lambda": np.array([[5000.0, 5001.0]]), "f": np.array([[1.0, 2.0]])})
    t["lambda"].unit, t["f"].unit = u.AA, u.Jy
    buffer = io.BytesIO()
    fits.HDUList([fits.PrimaryHDU(), fits.table_to_hdu(t)]).writeto(buffer)
    return buffer.getvalue()


def test_italian_text_is_unchanged_and_catalog_renders_both_languages(service, cache, tmp_path):
    err = pytest.raises(VoProtocolsError, tap_query, service.url + "/tap", "SELECT a) FROM t").value
    assert err.message == "parentesi chiusa senza apertura (carattere 8)"
    assert mc.message_text(err.code, err.params, "en") == "Closing parenthesis without an opening one (character 8)"
    assert mc.message_text(err.code, err.params, "it") == "Parentesi chiusa senza apertura (carattere 8)"
    check = validate_adql("SELECT a) FROM t")
    assert (check.valid, check.reason, check.position) == (False, "unmatched_close", 8)
    assert validate_adql("SELECT a FROM t").reason is None
    csv = tmp_path / "t.csv"
    csv.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(VoProtocolsError) as info:
        read_votable(csv)
    assert mc.message_text(info.value.code, info.value.params, "en") == (
        f"{csv}: not a VOTable (recognised content: csv)")
    assert info.value.message == f"{csv}: non è un VOTable (contenuto riconosciuto: csv)"
    # La causa annidata di SIA_INVALID è un messaggio del 14 reso in modo ricorsivo (D40-7).
    service.routes["/garbage"] = lambda r: (200, "text/plain", "non è un VOTable")
    with pytest.raises(VoProtocolsError) as info:
        sia_search(CENTER, 0.1 * u.deg, version=1, service=service.url + "/garbage", cache=cache)
    assert info.value.params["cause"]["code"] == "VOTABLE_INVALID"
    text = mc.message_text(info.value.code, info.value.params, "en")
    assert text.startswith("Invalid SIA response: " + service.url + "/garbage: the response cannot be read as a VOTable")
    assert read_table is not None
