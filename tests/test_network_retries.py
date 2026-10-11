"""Test della regola di ripetizione dei test di rete (decisione del proprietario del 2026-10-11)."""

import pytest
import requests

from conftest import network_failure


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
calls = {"n": 0, "a": 0}

@pytest.mark.network
def test_conn():
    calls["n"] += 1
    raise requests.exceptions.ConnectionError("sempre")

@pytest.mark.network
def test_wrong():
    calls["a"] += 1
    assert calls["a"] > 5, "risultato sbagliato"

def test_count():
    assert calls == {"n": 3, "a": 1}
''')
    pytester.makeini("[pytest]\nmarkers =\n    network: rete\n")
    result = pytester.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(failed=2, passed=1)
    result.stdout.fnmatch_lines(["*test di rete ripetuti*", "*test_conn*dopo 2 ripetizioni*"])
    reports = {r.nodeid.split("::")[-1]: r for r in result.reprec.getreports("pytest_runtest_logreport")
               if r.when == "call"}
    assert ("network_final", "connessione: ConnectionError") in reports["test_conn"].user_properties
    assert not any(name == "network_final" for name, _ in reports["test_wrong"].user_properties)
