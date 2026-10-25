# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Modulo 60 nel pacchetto (``src/astrotwo/app_bundle.py``): versione, file di licenza, sorgenti, autocontrollo.

Specifica: ``mdfiles/60-distribuzione-dmg.md`` §3.2, §3.7, §7 e §12 (T1, T5, T7, T9, T10). Nessun accesso al
Portachiavi (T10 lo controlla).
"""

import re
import tomllib
from pathlib import Path

from packaging.version import Version

import astrotwo
from astrotwo import app_bundle
from astrotwo.messages_catalog import message_text

ROOT = Path(__file__).resolve().parent.parent

# SemVer 2.0.0 (https://semver.org), espressione regolare ufficiale.
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
                    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")


def test_t1_version_semver_and_pep440_are_the_same():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == "0.1.0b1"
    assert astrotwo.__version__ == "0.1.0-beta.1" and SEMVER.match(astrotwo.__version__)
    assert Version(project["project"]["version"]) == Version(astrotwo.__version__)
    assert isinstance(project["tool"]["astrotwo"]["bundle"]["build"], int)


def test_t5_license_files_in_the_project():
    assert not app_bundle.is_bundled() and app_bundle.build_info() is None
    files = app_bundle.license_files()
    assert set(files) == set(app_bundle.LICENSE_NAMES)
    for name in ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES"):
        text, problem = app_bundle.read_license(name)
        assert problem is None and text == (ROOT / name).read_text(encoding="utf-8")
    sources, problem = app_bundle.read_license("SOURCES.txt")  # generato al volo nello sviluppo (§3.9)
    assert problem is None and sources == app_bundle.sources_text(None)


def test_t5_sources_text_cites_exact_sources():
    info = {"version": "0.1.0-beta.1", "build": 1, "commit": "abc123", "dirty": False}
    text = app_bundle.sources_text(info)
    assert "AstroTwo 0.1.0-beta.1 (build 1, commit abc123)" in text
    assert "https://github.com/guidogg13/AstroTwo" in text and "Tag of this version: v0.1.0-beta.1" in text
    assert "pyside-setup-everywhere-src-6.12.0.zip" in text and app_bundle.PYSIDE_SOURCE[1] in text
    for url, digest in app_bundle.QT_SOURCES:
        assert url in text and digest in text
    assert "codesign --force --deep --sign - AstroTwo.app" in text
    assert "Nothing restricts analysing, reverse engineering" in text
    assert "uncommitted changes" in app_bundle.sources_text({**info, "dirty": True})


def test_t7_missing_license_file(tmp_path):
    text, problem = app_bundle.read_license("SOURCES.txt", tmp_path)
    assert text is None and problem.code == "LICENSE_FILE_MISSING"
    assert problem.params == {"file": "SOURCES.txt", "path": str(tmp_path / "SOURCES.txt")}
    assert message_text(problem.code, problem.params, "it") == (
        f"File di licenza SOURCES.txt non trovato in {tmp_path / 'SOURCES.txt'}.")


def test_t9_self_check_in_development(qapp):
    report = app_bundle.self_check()
    statuses = {c["name"]: c["status"] for c in report["checks"]}
    assert report["bundled"] is False and report["ok"], [c for c in report["checks"] if c["status"] == "failed"]
    for name in ("python_inside_app", "sys_path_inside_app", "qt_paths_inside_app"):
        assert statuses[name] == "not_bundled"
    for name in ("python", "astrotwo_modules", "astrotwo_data", "license_files", "qt_version", "qt_plugins",
                 "translations", "certificates", "astropy_iers_data", "naif_kernel", "keyring_backend",
                 "cache_outside_app"):
        assert statuses[name] == "ok", name
    assert "keychain_roundtrip" not in statuses


def test_t10_self_check_never_touches_the_keychain(qapp, monkeypatch):
    from keyring.backends import macOS

    used = []

    def forbidden(*args, **kwargs):
        used.append(args)
        raise AssertionError("Portachiavi usato dall'autocontrollo")

    for method in ("get_password", "set_password", "delete_password", "get_credential"):
        monkeypatch.setattr(macOS.Keyring, method, forbidden)
    report = app_bundle.self_check()
    assert used == [] and any(c["name"] == "keyring_backend" and c["status"] == "ok" for c in report["checks"])


def test_self_check_entry_point_prints_json(qapp, capsys, monkeypatch):
    monkeypatch.setattr(app_bundle, "self_check", lambda keychain=False: {"ok": True, "keychain": keychain,
                                                                           "checks": []})
    assert app_bundle.main(["--self-check"]) == 0
    assert '"keychain": false' in capsys.readouterr().out
