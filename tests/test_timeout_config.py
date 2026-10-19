# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Un test fermo diventa un fallimento con il suo nome (pytest-timeout, ``pyproject.toml``)."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_timeout_configured_for_every_test():
    ini = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]
    assert ini["timeout"] == 120 and ini["timeout_method"] == "thread"
    dev = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["dependency-groups"]["dev"]
    assert any(d.startswith("pytest-timeout") for d in dev)


def test_hanging_test_fails_with_its_name(pytester):
    """Metodo ``signal`` nel test interno (``thread`` terminerebbe anche questo processo)."""
    pytester.makepyfile(test_hang="""
        import time

        def test_stuck():
            time.sleep(10)
    """)
    result = pytester.runpytest_subprocess("-p", "no:cacheprovider", "-o", "timeout=1", "-o", "timeout_method=signal")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*test_stuck*", "*Timeout*1.0s*"])


def test_network_tests_get_a_longer_limit(pytester):
    pytester.makeconftest(open(ROOT / "tests" / "conftest.py", encoding="utf-8").read())
    pytester.makeini("[pytest]\nmarkers =\n    network: x\n")
    pytester.makepyfile(test_net="""
        import pytest

        @pytest.mark.network
        def test_net(request):
            assert request.node.get_closest_marker("timeout").args == (600,)

        def test_plain(request):
            assert request.node.get_closest_marker("timeout") is None
    """)
    result = pytester.runpytest_subprocess("-p", "no:cacheprovider", "-o", "addopts=")
    result.assert_outcomes(passed=2)
