# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Ogni file .py del progetto porta l'intestazione di licenza (A11, decisione del proprietario del 2026-10-17)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = ("# SPDX-License-Identifier: GPL-3.0-or-later", "# Copyright (C) 2026 Guido Ratti")


def _python_files(folder: str):
    return sorted(p for p in (ROOT / folder).rglob("*.py") if "__pycache__" not in p.parts)


def _has_header(path: Path) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].startswith("#!"):
        lines = lines[1:]
    return tuple(lines[:2]) == HEADER


def test_every_source_file_has_license_header():
    files = _python_files("src")
    assert files
    missing = [str(p.relative_to(ROOT)) for p in files if not _has_header(p)]
    assert not missing, f"intestazione di licenza mancante: {missing}"


def test_tests_scripts_examples_have_license_header():
    missing = [str(p.relative_to(ROOT)) for folder in ("tests", "scripts", "examples")
               for p in _python_files(folder) if not _has_header(p)]
    assert not missing, f"intestazione di licenza mancante: {missing}"


def test_license_files_present():
    assert "GNU GENERAL PUBLIC LICENSE" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Copyright (C) 2026 Guido Ratti" in (ROOT / "NOTICE").read_text(encoding="utf-8")
