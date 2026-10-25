# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""THIRD_PARTY_LICENSES aggiornato con tutte le dipendenze (decisione del proprietario del 2026-10-13)."""

import importlib.util
import sys
from pathlib import Path

from packaging.utils import canonicalize_name

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "third_party_licenses.py"
spec = importlib.util.spec_from_file_location("third_party_licenses", SCRIPT)
third_party_licenses = importlib.util.module_from_spec(spec)
sys.modules["third_party_licenses"] = third_party_licenses  # richiesto da dataclass
spec.loader.exec_module(third_party_licenses)


def test_file_is_current():
    expected = third_party_licenses.render()
    current = third_party_licenses.OUTPUT.read_text(encoding="utf-8")
    assert current == expected, "rigenerare THIRD_PARTY_LICENSES con scripts/third_party_licenses.py"


def test_every_runtime_dependency_listed_with_version_and_license():
    text = third_party_licenses.OUTPUT.read_text(encoding="utf-8")
    summary = text.split("Riepilogo\n=========\n", 1)[1].split("\n\n=", 1)[0]
    for distribution in third_party_licenses.runtime_closure():
        name = distribution.metadata["Name"]
        assert any(line.split()[:2] == [name, distribution.version] for line in summary.splitlines()), name
    # Avviso della libreria QD (LBNL) inclusa in spherical-geometry.
    assert "Lawrence Berkeley National Laboratory" in text and "QD_LIBRARY_LICENSE" in text


def test_interface_and_ai_licenses_present():
    """Verifica prima del codice della v1 (2026-10-16): licenze di SDK, keyring, PySide6 e pytest-qt."""
    text = third_party_licenses.OUTPUT.read_text(encoding="utf-8")
    for name in ("anthropic", "openai", "httpx2", "keyring", "pyside6-essentials", "shiboken6"):
        assert any(canonicalize_name(d.metadata["Name"]) == name for d in third_party_licenses.runtime_closure()), name
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in text and "GNU GENERAL PUBLIC LICENSE" in text
    dev = text.split("Strumenti di sviluppo (test e costruzione, non distribuiti nell'app né nel .dmg)", 1)[1]
    assert "pytest-qt" in dev and "MIT" in dev and "pyinstaller" in dev


def test_t11_app_components_present():
    """60 §3.7 punto 2 (T11): Python dell'app, avvisi di Qt e bootloader di PyInstaller nella parte distribuita."""
    text = third_party_licenses.OUTPUT.read_text(encoding="utf-8")
    distributed = text.split("Strumenti di sviluppo (test e costruzione", 1)[0]
    for title in ("Python (CPython, python-build-standalone) 3.12.15+20261003",
                  "Qt 6.12.0, componenti di terze parti (qtbase, qtsvg) 6.12.0",
                  "Bootloader e hook di esecuzione di PyInstaller"):
        assert f"\n{title}" in distributed, title
    # PSF, OpenSSL, avvisi di Qt (PCRE2, FreeType) ed eccezione del bootloader.
    for needle in ("PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2", "Apache License", "PCRE2", "FreeType",
                   "Bootloader Exception"):
        assert needle in distributed, needle
