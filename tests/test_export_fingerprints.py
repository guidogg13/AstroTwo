# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Identità dei byte dei file di dati esportati su macOS, Windows e Linux (``mdfiles/65-windows-linux.md`` T9, D65-10).

Il caso fisso di ``scripts/export_fingerprints.py`` (nessuna rete, data fissa) deve dare le impronte SHA-256 di
``tests/data/export_fingerprints.json`` su **ogni** sistema: lo stesso test gira sui tre runner del workflow ``tests``,
che in più confronta tra loro le impronte dei tre sistemi (job ``fingerprints``).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "tests" / "data" / "export_fingerprints.json"


def _script():
    spec = importlib.util.spec_from_file_location("export_fingerprints", ROOT / "scripts" / "export_fingerprints.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_t9_fingerprints_equal_reference():
    """Stessi byte del riferimento (calcolato su macOS): CSV, ECSV, VOTable, sottoinsieme, MOC, SED, sessione."""
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    found = _script().fingerprints()
    assert sorted(found["files"]) == sorted(reference["files"])
    different = {name: (found["sizes"][name], reference["sizes"][name]) for name in reference["files"]
                 if found["files"][name] != reference["files"][name]}
    assert different == {}, f"file con byte diversi dal riferimento (dimensione trovata, attesa): {different}"


def test_fingerprint_case_without_cr_and_absolute_paths(tmp_path):
    """Nessun ``\\r`` e nessun percorso della cartella di lavoro nei file del caso fisso (dati portabili)."""
    files = _script().write_case(tmp_path)
    for name, path in files.items():
        data = path.read_bytes()
        assert b"\r" not in data, name
        assert str(tmp_path).encode("utf-8") not in data, name


def test_fingerprint_script_output(tmp_path):
    """Lo script scrive il JSON delle impronte con ``--output`` (usato dal workflow)."""
    out = tmp_path / "impronte.json"
    assert _script().main(["--output", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data) == {"files", "sizes", "system"} and len(data["files"]) == 10


def test_compare_fails_when_one_system_differs(tmp_path, capsys):
    """Il confronto del workflow: uscita 0 con impronte uguali, 1 con un file diverso o mancante."""
    module = _script()
    files = {"catalog.csv": "a" * 64, "moc.json": "b" * 64}
    paths = []
    for system, changed in (("Darwin", {}), ("Windows", {}), ("Linux", {})):
        path = tmp_path / f"{system}.json"
        path.write_text(json.dumps({"system": system, "files": {**files, **changed}, "sizes": {}}), encoding="utf-8")
        paths.append(str(path))
    assert module.main(["--compare", *paths]) == 0
    (tmp_path / "Windows.json").write_text(json.dumps({"system": "Windows", "files": {"catalog.csv": "c" * 64},
                                                       "sizes": {}}), encoding="utf-8")
    assert module.main(["--compare", *paths]) == 1
    out = capsys.readouterr().out
    assert "DIVERSO catalog.csv" in out and "DIVERSO moc.json" in out and "mancante" in out
