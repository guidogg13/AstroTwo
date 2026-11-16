# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Script dei pacchetti di Windows e Linux (``scripts/build_windows_linux.py``, ``mdfiles/65-windows-linux.md`` §3.9).

I pacchetti si costruiscono solo sui runner del workflow manuale: qui si provano, senza PyInstaller, le parti che non
dipendono dal sistema (scelta dei plugin, nomi, zip e tar, AppDir, impronte, ambiente dei controlli, specifica).
"""

from __future__ import annotations

import importlib.util
import platform
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_windows_linux", ROOT / "scripts" / "build_windows_linux.py")
bwl = importlib.util.module_from_spec(_spec)
sys.modules["build_windows_linux"] = bwl
_spec.loader.exec_module(bwl)


def test_only_windows_and_linux_x86_64(monkeypatch):
    for system, machine in (("Darwin", "arm64"), ("Windows", "ARM64"), ("Linux", "aarch64"), ("FreeBSD", "amd64")):
        monkeypatch.setattr(platform, "system", lambda s=system: s)
        monkeypatch.setattr(platform, "machine", lambda m=machine: m)
        with pytest.raises(bwl.BuildError):
            bwl.current_system()
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(platform, "machine", lambda: "AMD64")
    assert bwl.current_system() == ("Windows", "windows")
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    assert bwl.current_system() == ("Linux", "linux")


def test_keep_entry_per_system():
    keep = bwl.keep_entry
    assert keep("PySide6/plugins/platforms/qwindows.dll", "Windows")
    assert keep("PySide6\\plugins\\platforms\\qoffscreen.dll", "Windows")
    assert not keep("PySide6/plugins/platforms/qminimal.dll", "Windows")
    assert not keep("PySide6/plugins/sqldrivers/qsqlite.dll", "Windows")
    assert keep("PySide6/Qt/plugins/platforms/libqxcb.so", "Linux")
    assert keep("PySide6/Qt/plugins/xcbglintegrations/libqxcb-glx-integration.so", "Linux")
    assert not keep("PySide6/Qt/plugins/platforms/libqvnc.so", "Linux")
    assert keep("PySide6/translations/qtbase_it.qm", "Windows") and not keep("PySide6/translations/qtbase_de.qm",
                                                                             "Windows")
    assert not keep("PySide6/Qt/qml/QtQuick/qmldir", "Linux")
    assert keep("astropy/units/core.py", "Linux") and keep("PySide6/opengl32sw.dll", "Windows")


def test_needed_plugins_are_kept():
    """Ogni plugin che l'autocontrollo vuole (P8) passa il filtro della costruzione."""
    from astrotwo.app_bundle import QT_PLUGINS_NEEDED

    for system, key, prefix in (("Windows", "win32", "PySide6/plugins/"), ("Linux", "linux", "PySide6/Qt/plugins/")):
        for name in QT_PLUGINS_NEEDED[key]:
            assert bwl.keep_entry(prefix + name, system), name


def test_package_names_and_sha256_file(tmp_path):
    assert bwl.package_name("1.1.0", "windows", ".zip") == "AstroTwo-1.1.0-windows-x86_64.zip"
    assert bwl.package_name("1.1.0", "linux", ".AppImage") == "AstroTwo-1.1.0-linux-x86_64.AppImage"
    package = tmp_path / "AstroTwo-1.1.0-linux-x86_64.tar.gz"
    package.write_bytes(b"abc")
    written = bwl.write_sha256(package)
    assert written.name == package.name + ".sha256"
    assert written.read_bytes() == (b"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad  "
                                    b"AstroTwo-1.1.0-linux-x86_64.tar.gz\n")


def _fake_onedir(tmp_path: Path) -> Path:
    folder = tmp_path / "AstroTwo"
    (folder / "_internal" / "licenses").mkdir(parents=True)
    executable = folder / "AstroTwo"
    executable.write_bytes(b"#!/bin/sh\n")
    executable.chmod(0o755)
    (folder / "_internal" / "licenses" / "LICENSE").write_bytes(b"GPL\n")
    return folder


def test_zip_and_tar_contain_the_folder(tmp_path):
    folder = _fake_onedir(tmp_path)
    archive = bwl.make_zip(folder, tmp_path / "p.zip")
    with zipfile.ZipFile(archive) as z:
        assert sorted(z.namelist()) == ["AstroTwo/AstroTwo", "AstroTwo/_internal/licenses/LICENSE"]
    tar = bwl.make_tar(folder, tmp_path / "p.tar.gz")
    out = tmp_path / "estratto"
    extracted = bwl.extract(tar, out)
    assert extracted == out / "AstroTwo" and (extracted / "_internal" / "licenses" / "LICENSE").read_bytes() == b"GPL\n"
    if sys.platform != "win32":
        assert (extracted / "AstroTwo").stat().st_mode & 0o111  # eseguibile anche dopo il tar
    with tarfile.open(tar) as t:
        assert all(name == "AstroTwo" or name.startswith("AstroTwo/") for name in t.getnames())


def test_appdir_layout(tmp_path, monkeypatch):
    monkeypatch.setattr(bwl, "BUILD", tmp_path / "build")
    folder = _fake_onedir(tmp_path)
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"\x89PNG")
    appdir = bwl.make_appdir(folder, icon)
    assert (appdir / "usr" / "lib" / "astrotwo" / "AstroTwo").is_file()
    assert (appdir / "AppRun").read_bytes().startswith(b"#!/bin/sh\n")
    desktop = (appdir / "astrotwo.desktop").read_text(encoding="utf-8")
    assert "Exec=AstroTwo" in desktop and "Icon=astrotwo" in desktop and "Categories=Science;Astronomy;" in desktop
    assert (appdir / "astrotwo.png").is_file() and (appdir / ".DirIcon").is_file()
    if sys.platform != "win32":
        assert (appdir / "AppRun").stat().st_mode & 0o111


def test_clean_environment_has_no_uv_and_a_fake_home(tmp_path):
    env = bwl.clean_environment(tmp_path)
    assert ".venv" not in env["PATH"] and "uv" not in env["PATH"].lower().split("/")
    assert env.get("HOME") == str(tmp_path)


def test_spec_text_per_system(tmp_path):
    stage = tmp_path / "stage"
    text = bwl.spec_text(entry=tmp_path / "launch.py", stage=stage, icon=None, system="Linux")
    compile(text, "spec", "exec")
    assert "keyring.backends.SecretService" in text and "keyring.backends.macOS" not in text
    assert "BUNDLE(" not in text and "COLLECT(" in text and "'tkinter'" in text
    text = bwl.spec_text(entry=tmp_path / "launch.py", stage=stage, icon=tmp_path / "a.ico", system="Windows")
    assert "keyring.backends.Windows" in text and "a.ico" in text


def test_report_file_option(qapp, tmp_path, monkeypatch, capsys):
    """``--report-file`` dell'avvio dell'app: il rapporto va nel file (l'eseguibile di Windows senza console)."""
    from astrotwo import app_bundle

    monkeypatch.setattr(app_bundle, "self_check", lambda keychain=False: {"ok": True, "checks": []})
    target = tmp_path / "r.json"
    assert app_bundle.main(["--self-check", "--report-file", str(target)]) == 0
    assert target.read_text(encoding="utf-8").startswith("{") and capsys.readouterr().out == ""
    assert app_bundle.main(["--self-check", "--report-file"]) == 2


def _workflow(name: str) -> dict:
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    data["on"] = data.pop(True, data.get("on"))  # YAML 1.1 legge «on» come vero
    return data


def test_build_workflow_manual_only_without_release():
    """Workflow dei pacchetti: solo a mano, sola lettura, x86_64 su windows-latest e ubuntu-22.04, strumenti
    dell'AppImage fissati per impronta, nessuna release, tag o push (65 §3.9)."""
    data = _workflow("build-windows-linux.yml")
    assert list(data["on"]) == ["workflow_dispatch"] and data["permissions"] == {"contents": "read"}
    assert data["jobs"]["windows"]["runs-on"] == "windows-latest"
    assert data["jobs"]["linux"]["runs-on"] == "ubuntu-22.04"
    env = data["jobs"]["linux"]["env"]
    for key in ("APPIMAGETOOL_SHA256", "APPIMAGE_RUNTIME_SHA256"):
        assert len(env[key]) == 64 and int(env[key], 16) >= 0
    text = (ROOT / ".github" / "workflows" / "build-windows-linux.yml").read_text(encoding="utf-8")
    for forbidden in ("gh release", "action-gh-release", "git tag", "git push", "secrets."):
        assert forbidden not in text
    steps = [s for job in data["jobs"].values() for s in job["steps"]]
    assert any("scripts/build_windows_linux.py" in s.get("run", "") for s in steps)
    assert sum(s.get("uses", "").startswith("actions/upload-artifact") for s in steps) == 2


def test_tests_workflow_compares_fingerprints():
    """Workflow dei test: impronte di ogni sistema come artefatto e job che le confronta (D65-10)."""
    data = _workflow("tests.yml")
    job = data["jobs"]["fingerprints"]
    assert job["needs"] == "tests" and job["if"] == "always()"
    assert any("--compare" in s.get("run", "") for s in job["steps"])
    steps = data["jobs"]["tests"]["steps"]
    assert any("export_fingerprints.py --output" in s.get("run", "") for s in steps)
