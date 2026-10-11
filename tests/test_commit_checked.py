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
        '<testcase classname="t" name="wrong"><failure message="assert"/></testcase>'
        '</testsuite></testsuites>')
    by_connection, other = commit_checked.network_failures(junit)
    assert by_connection == ["t::conn (connessione: ConnectionError)"]
    assert other == ["t::wrong"]
