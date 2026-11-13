# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Prova di fumo della finestra Profili (V10, D62-2) e esclusioni di ``scripts/build_app.py``
(``mdfiles/60-distribuzione-dmg.md`` §3.5, §3.8; decisione del proprietario del 2026-11-13).

La prova gira in un processo a parte, come nell'app costruita: piattaforma Qt ``offscreen``, un proxy verso una porta
chiusa (nessuna rete, solo 127.0.0.1) e le risposte vere registrate di ``tests/analysis/data/profile``.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_app  # noqa: E402

#: Esclusioni che servono solo ai test o a nient'altro: il processo dei test le carica (pytest, QtTest di pytest-qt).
_TEST_ONLY = {"pytest", "PySide6.QtTest"}

_SCRIPT = """
import json, sys
from pathlib import Path
{sabotage}
from astrotwo.smoke_profile import run
report = run(Path(sys.argv[1]), timeout=float(sys.argv[2]))
excluded = json.loads(sys.argv[3])
report["excluded_loaded"] = sorted(m for m in sys.modules if any(m == e or m.startswith(e + ".") for e in excluded))
print("SMOKE=" + json.dumps(report, default=str))
"""


def smoke(tmp_path, *, sabotage: str = "", timeout: float = 120.0) -> dict:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "HOME": str(tmp_path),
           "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9",
           "http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9",
           "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}
    script = _SCRIPT.format(sabotage=sabotage)
    result = subprocess.run([sys.executable, "-c", script, str(build_app.SMOKE_DATA), str(timeout),
                             json.dumps(sorted(build_app.EXCLUDES))], cwd=tmp_path, env=env, capture_output=True,
                            text=True, timeout=600)
    line = next((x for x in result.stdout.splitlines() if x.startswith("SMOKE=")), None)
    assert line is not None, result.stderr[-3000:]
    return json.loads(line.removeprefix("SMOKE="))


def test_v10_smoke_profile_passes_and_loads_no_excluded_module(tmp_path):
    report = smoke(tmp_path)
    failed = [c for c in report["checks"] if not c["ok"]]
    assert report["ok"] and not failed, failed
    names = {c["name"] for c in report["checks"]}
    assert {"all_sections_done", "export_enabled", "load_sed_enabled", "export_pdf", "load_sed_catalog"} <= names
    sections = next(c for c in report["checks"] if c["name"] == "all_sections_done")["detail"]
    assert sections == dict.fromkeys(("identity", "images", "astrometry", "photometry", "planets"), "done")
    # nessun modulo escluso dall'app viene caricato da un profilo completo con le esportazioni (import nelle funzioni)
    assert report["excluded_loaded"] == []


def test_v10_smoke_profile_fails_without_backend_qtagg(tmp_path):
    """Il difetto del build 7 (D62-2): senza ``backend_qtagg`` la prova fallisce, con l'errore di ``_plot``."""
    report = smoke(tmp_path, sabotage="sys.modules['matplotlib.backends.backend_qtagg'] = None", timeout=60.0)
    failed = {c["name"] for c in report["checks"] if not c["ok"]}
    assert not report["ok"] and {"profile_finished", "export_enabled", "load_sed_enabled"} <= failed
    assert any("backend_qtagg" in e for e in report["errors"])


def _imports(path: Path) -> list[tuple[str, int]]:
    """Ogni modulo importato dal file, **anche dentro le funzioni** (``import a.b``, ``from a.b import c``, ``from
    . import x`` risolto), con la riga."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    package = ".".join(path.relative_to(ROOT / "src").with_suffix("").parts[:-1])
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(alias.name, node.lineno) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = importlib.util.resolve_name("." * node.level + (node.module or ""), package) if node.level \
                else node.module or ""
            out.append((base, node.lineno))
            out += [(f"{base}.{alias.name}", node.lineno) for alias in node.names]
    return out


def test_excluded_modules_are_never_imported_by_astrotwo():
    """D62-2: ogni esclusione di ``build_app.EXCLUDES`` non serve a nessun import di AstroTwo, neanche dentro una
    funzione (l'autocontrollo V4 importa solo i moduli, non esegue le funzioni)."""
    found = []
    for path in sorted((ROOT / "src" / "astrotwo").rglob("*.py")):
        for name, line in _imports(path):
            for excluded in build_app.EXCLUDES:
                if name == excluded or name.startswith(excluded + "."):
                    found.append(f"{path.relative_to(ROOT)}:{line} {name}")
    assert found == []


@pytest.mark.parametrize("module", ["matplotlib.backends.backend_qtagg", "matplotlib.backends.backend_qt"])
def test_qt_backends_of_matplotlib_are_in_the_app(module):
    assert module not in build_app.EXCLUDES
    assert importlib.util.find_spec(module) is not None


def test_excluded_modules_are_not_loaded_by_the_app_modules():
    """Importare tutti i moduli di AstroTwo (come V4) non carica nessun modulo escluso, salvo quelli dei test."""
    code = ("import importlib, pkgutil, sys, json, astrotwo\n"
            "for m in pkgutil.walk_packages(astrotwo.__path__, 'astrotwo.'):\n"
            "    importlib.import_module(m.name)\n"
            "print(json.dumps(sorted(sys.modules)))")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    loaded = json.loads(result.stdout.splitlines()[-1])
    bad = [m for m in loaded for e in set(build_app.EXCLUDES) - _TEST_ONLY if m == e or m.startswith(e + ".")]
    assert bad == []
