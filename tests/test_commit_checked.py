"""Regola dei commit (02-convenzioni.md §8, punto 9): lettura dei test di rete falliti."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "commit_checked.py"
spec = importlib.util.spec_from_file_location("commit_checked", SCRIPT)
commit_checked = importlib.util.module_from_spec(spec)
spec.loader.exec_module(commit_checked)


def test_network_failures_split_connection_from_other(tmp_path):
    junit = tmp_path / "network.xml"
    junit.write_text(
        '<testsuites><testsuite>'
        '<testcase classname="t" name="ok"/>'
        '<testcase classname="t" name="conn"><properties>'
        '<property name="network_retry" value="tentativo 1"/>'
        '<property name="network_final" value="connessione: ConnectionError"/>'
        '</properties><failure message="x"/></testcase>'
        '<testcase classname="t" name="busy"><properties>'
        '<property name="network_final" value="servizio temporaneamente non disponibile: HTTP 503 (VoProtocolsError)"/>'
        '</properties><failure message="x"/></testcase>'
        '<testcase classname="t" name="wrong"><failure message="assert"/></testcase>'
        '<testcase classname="t" name="notfound"><failure message="SERVICE_ERROR: risposta HTTP 404"/></testcase>'
        '</testsuite></testsuites>')
    by_connection, other = commit_checked.network_failures(junit)
    assert by_connection == ["t::conn (connessione: ConnectionError)",
                             "t::busy (servizio temporaneamente non disponibile: HTTP 503 (VoProtocolsError))"]
    assert other == ["t::wrong", "t::notfound"]  # un 404 resta un risultato sbagliato: nessun commit


def test_commit_message_declares_unavailable_services(tmp_path, monkeypatch):
    """Solo test falliti per la rete (compreso un HTTP 503) → commit con la dichiarazione nel messaggio."""
    calls = []

    def fake_pytest(*args, junit=None):
        if junit is not None:
            junit.write_text(
                '<testsuites><testsuite><testcase classname="t" name="busy"><properties>'
                '<property name="network_final" value="servizio temporaneamente non disponibile: HTTP 503 (X)"/>'
                '</properties><failure message="x"/></testcase></testsuite></testsuites>')
            return 1
        return 0

    monkeypatch.setattr(commit_checked, "run_pytest", fake_pytest)
    monkeypatch.setattr(commit_checked.subprocess, "run",
                        lambda command, cwd: calls.append(command) or type("R", (), {"returncode": 0})())
    monkeypatch.setattr("sys.argv", ["commit_checked.py", "-m", "Titolo\n\nCo-Authored-By: X <x@example.org>"])
    assert commit_checked.main() == 0
    message = calls[-1][-1]
    assert "servizio temporaneamente non disponibile (HTTP 429, 502, 503, 504)" in message
    assert "- t::busy (servizio temporaneamente non disponibile: HTTP 503 (X))" in message
    assert message.endswith("Co-Authored-By: X <x@example.org>")


def test_no_commit_for_other_http_errors(monkeypatch):
    calls = []

    def fake_pytest(*args, junit=None):
        if junit is not None:
            junit.write_text('<testsuites><testsuite><testcase classname="t" name="notfound">'
                             '<failure message="HTTP 404"/></testcase></testsuite></testsuites>')
            return 1
        return 0

    monkeypatch.setattr(commit_checked, "run_pytest", fake_pytest)
    monkeypatch.setattr(commit_checked.subprocess, "run", lambda command, cwd: calls.append(command))
    monkeypatch.setattr("sys.argv", ["commit_checked.py", "-m", "Titolo"])
    assert commit_checked.main() == 1
    assert calls == []


def test_note_goes_before_attribution():
    message = "Titolo\n\nCorpo\n\nCo-Authored-By: X <x@example.org>"
    assert commit_checked.with_note(message, "Nota") == "Titolo\n\nCorpo\n\nNota\n\nCo-Authored-By: X <x@example.org>"
    assert commit_checked.with_note("Titolo", "Nota") == "Titolo\n\nNota"
