# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test della regola di ripetizione dei test di rete (decisione del proprietario del 2026-10-11)."""

import pytest
import requests

from conftest import cds_down_reason, cds_not_found_host, network_failure, network_reason


class _Coded(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def test_network_failure_classification():
    assert network_failure(requests.exceptions.ConnectionError("x"))
    assert network_failure(requests.exceptions.ReadTimeout("x"))
    assert network_failure(TimeoutError())
    assert network_failure(_Coded("NET_TIMEOUT"))
    wrapped = _Coded("SERVICE_ERROR")
    wrapped.__cause__ = requests.exceptions.ConnectionError("y")
    assert network_failure(wrapped)  # causa concatenata
    assert not network_failure(AssertionError("risultato sbagliato"))
    assert not network_failure(_Coded("ADQL_INVALID"))
    assert not network_failure(ValueError("x"))


class _ModuleError(Exception):
    """Come gli errori dei moduli di AstroTwo: ``code``, testo e dettagli (es. ``status``)."""

    def __init__(self, code, message, **details):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.details = details


def _http_error(status):
    response = requests.models.Response()
    response.status_code = status
    return requests.exceptions.HTTPError(f"{status} Server Error: x for url: https://example.org", response=response)


def test_transient_http_statuses_count_as_network():
    # Decisione del proprietario del 2026-10-16: 429, 502, 503, 504 = servizio temporaneamente non disponibile.
    for status in (429, 502, 503, 504):
        assert network_reason(_ModuleError("SERVICE_ERROR", "risposta HTTP", status=status)) == (
            f"servizio temporaneamente non disponibile: HTTP {status} (_ModuleError)")
        assert network_failure(_http_error(status))
        assert network_failure(_ModuleError("SERVICE_ERROR", f"https://x/tap/sync: risposta HTTP {status} senza VOTable"))
    wrapped = _ModuleError("SERVICE_ERROR", "errore del servizio")
    wrapped.__cause__ = _http_error(503)
    assert network_failure(wrapped)  # causa concatenata
    assert network_reason(requests.exceptions.ConnectionError("x")) == "connessione: ConnectionError"


def test_other_http_errors_stay_wrong_results():
    for status in (400, 401, 403, 404, 410, 422, 500, 501):
        assert not network_failure(_ModuleError("SERVICE_ERROR", f"risposta HTTP {status}", status=status))
        assert not network_failure(_http_error(status))
    assert not network_failure(_ModuleError("SERVICE_ERROR", "risposta HTTP 4290"))  # nessun falso riconoscimento
    assert not network_failure(AssertionError("atteso HTTP 503"))  # un risultato sbagliato non si ripete mai


_calls = {"conn": 0, "wrong": 0}


@pytest.mark.network
def test_retry_only_on_connection_error():
    _calls["conn"] += 1
    if _calls["conn"] <= 2:
        raise requests.exceptions.ConnectionError("simulato")
    assert _calls["conn"] == 3  # due ripetizioni, poi riuscito


def test_retry_counts_and_assertion_not_retried(pytester):
    pytester.makeconftest(open(__import__("conftest").__file__, encoding="utf-8").read())
    pytester.makepyfile(test_x='''
import pytest, requests
calls = {"n": 0, "a": 0, "u": 0, "f": 0}

@pytest.mark.network
def test_conn():
    calls["n"] += 1
    raise requests.exceptions.ConnectionError("sempre")

@pytest.mark.network
def test_wrong():
    calls["a"] += 1
    assert calls["a"] > 5, "risultato sbagliato"

class Unavailable(Exception):
    def __init__(self, status):
        super().__init__(f"SERVICE_ERROR: risposta HTTP {status}")
        self.details = {"status": status}

@pytest.mark.network
def test_unavailable():
    calls["u"] += 1
    raise Unavailable(503)

@pytest.mark.network
def test_not_found():
    calls["f"] += 1
    raise Unavailable(404)

def test_count():
    assert calls == {"n": 3, "a": 1, "u": 3, "f": 1}
''')
    pytester.makeini("[pytest]\nmarkers =\n    network: rete\n")
    result = pytester.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(failed=4, passed=1)
    result.stdout.fnmatch_lines(["*test di rete ripetuti*", "*test_conn*dopo 2 ripetizioni*"])
    reports = {r.nodeid.split("::")[-1]: r for r in result.reprec.getreports("pytest_runtest_logreport")
               if r.when == "call"}
    assert ("network_final", "connessione: ConnectionError") in reports["test_conn"].user_properties
    assert not any(name == "network_final" for name, _ in reports["test_wrong"].user_properties)
    assert ("network_final", "servizio temporaneamente non disponibile: HTTP 503 (Unavailable)") in (
        reports["test_unavailable"].user_properties)
    assert not any(name == "network_final" for name, _ in reports["test_not_found"].user_properties)


def _not_found(url):
    response = requests.models.Response()
    response.status_code, response.url = 404, url
    return requests.exceptions.HTTPError(f"404 Client Error: Not Found for url: {url}", response=response)


def test_gaia_overloaded_text_counts_as_unavailable():
    # Testo dell'archivio Gaia osservato il 2026-11-11 (sprint D8), senza stato nell'eccezione
    exc = requests.exceptions.HTTPError("Error 503: Server overloaded: synchronous job rejected")
    assert network_reason(exc) == "servizio temporaneamente non disponibile: HTTP 503 (HTTPError)"
    assert not network_failure(requests.exceptions.HTTPError("Error 404: not found"))


def test_cds_404_host_is_found_along_the_chain():
    # Decisione del proprietario del 2026-11-11: il 404 del CDS è un servizio giù (come D14-16)
    assert cds_not_found_host(_not_found("https://vizier.cds.unistra.fr/catstd/astrores.xml")) == (
        "vizier.cds.unistra.fr")
    assert cds_not_found_host(_ModuleError(
        "SERVICE_ERROR", "https://vizier.cds.unistra.fr/viz-bin/sed: risposta HTTP 404 senza VOTable",
        status=404)) == "vizier.cds.unistra.fr"
    pyvo_like = RuntimeError("Unable to access the capabilities endpoint at: - "
                             "https://simbad.cds.unistra.fr/simbad/sim-tap/capabilities: 404 Not Found")
    wrapped = _ModuleError("CATALOG_UNAVAILABLE", "SIMBAD")
    wrapped.__cause__ = pyvo_like
    assert cds_not_found_host(wrapped) == "simbad.cds.unistra.fr"
    assert cds_not_found_host(_not_found("https://irsa.ipac.caltech.edu/x")) is None  # non è il CDS
    assert cds_not_found_host(_ModuleError("SERVICE_ERROR", "https://simbad.cds.unistra.fr: HTTP 400",
                                           status=400)) is None  # solo il 404
    assert cds_not_found_host(AssertionError("https://simbad.cds.unistra.fr HTTP 404")) is None  # risultato


def test_cds_404_is_skipped_only_when_the_probe_fails():
    exc = _not_found("https://simbad.cds.unistra.fr/simbad/sim-tap/sync")
    down = cds_down_reason(exc, probe=lambda host: "sonda x: HTTP 404")
    assert down == "servizio giù: HTTP 404 (simbad.cds.unistra.fr); sonda x: HTTP 404"
    # la sonda risponde: il 404 viene da un indirizzo sbagliato nostro e resta un errore vero
    assert cds_down_reason(exc, probe=lambda host: None) is None
    assert cds_down_reason(_not_found("https://example.org/x"), probe=lambda host: "giù") is None


def test_cds_404_skip_in_a_run(pytester):
    pytester.makeconftest(open(__import__("conftest").__file__, encoding="utf-8").read()
                          + "\nprobe_service = lambda host: 'sonda finta: HTTP 404' if host.startswith('simbad') "
                            "else None\n")
    pytester.makepyfile(test_y='''
import pytest, requests

def _nf(url):
    r = requests.models.Response(); r.status_code, r.url = 404, url
    return requests.exceptions.HTTPError(f"404 Client Error: Not Found for url: {url}", response=r)

@pytest.mark.network
def test_cds_down():
    raise _nf("https://simbad.cds.unistra.fr/simbad/sim-tap/sync")

@pytest.mark.network
def test_our_wrong_url():
    raise _nf("https://vizier.cds.unistra.fr/sbagliato.xml")
''')
    pytester.makeini("[pytest]\nmarkers =\n    network: rete\n")
    result = pytester.runpytest("-p", "no:cacheprovider", "-rs")
    result.assert_outcomes(skipped=1, failed=1)
    result.stdout.fnmatch_lines(["*servizio giù: HTTP 404 (simbad.cds.unistra.fr); sonda finta: HTTP 404*"])

