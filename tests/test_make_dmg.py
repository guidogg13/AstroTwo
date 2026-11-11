# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test di ``scripts/make_dmg.py`` (60-distribuzione-dmg.md §3.10, sprint 60b): prova a secco e parti pure.

Nessun ``hdiutil``, ``ditto``, ``codesign`` o ``xcrun`` parte mai: ``subprocess.run`` è sostituito da una funzione
che fa fallire il test, oppure (per il percorso con ``--execute``) da una finta che registra i comandi. Nessuna app
costruita serve: si usa un'app finta in una cartella temporanea."""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "make_dmg.py"
spec = importlib.util.spec_from_file_location("make_dmg", SCRIPT)
md = importlib.util.module_from_spec(spec)
sys.modules["make_dmg"] = md
spec.loader.exec_module(md)


@pytest.fixture(autouse=True)
def no_commands(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError(f"comando eseguito: {args[0] if args else kwargs}")
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Cartelle ``dist/`` e ``build/`` finte e un'app finta (nessuna costruzione)."""
    dist, build = tmp_path / "dist", tmp_path / "build"
    app = dist / "AstroTwo.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "MacOS" / "AstroTwo").write_bytes(b"\xcf\xfa\xed\xfe" + b"\0" * 28)
    build.mkdir()
    monkeypatch.setattr(md, "DIST", dist)
    monkeypatch.setattr(md, "BUILD", build)
    monkeypatch.setattr(md, "APP", app)
    monkeypatch.setattr(md, "STAGING", build / "dmg-root")
    return dist, build, app


def commands(plan) -> list[list[str]]:
    return [s.command for s in plan.steps]


def test_version_and_names():
    import astrotwo

    assert md.version() == astrotwo.__version__
    assert md.dmg_path("1.0.0", Path("/d")) == Path("/d/AstroTwo-1.0.0.dmg")
    assert md.volume_name("1.0.0") == "AstroTwo 1.0.0"


def test_unsigned_plan_order(project):
    dist, build, app = project
    dmg = md.dmg_path("1.0.0", dist)
    plan = md.build_plan(app, dmg, "1.0.0", signed=False, staging=build / "dmg-root")
    cmds = commands(plan)
    assert [c[0] for c in cmds] == ["rm", "mkdir", "ditto", "ln", "hdiutil", "hdiutil", "shasum"]
    assert cmds[2] == ["ditto", str(app), str(build / "dmg-root" / "AstroTwo.app")]
    assert cmds[3] == ["ln", "-s", "/Applications", str(build / "dmg-root" / "Applications")]
    assert cmds[4] == ["hdiutil", "create", "-volname", "AstroTwo 1.0.0", "-srcfolder", str(build / "dmg-root"),
                       "-fs", "HFS+", "-format", "UDZO", str(dmg)]
    assert cmds[5] == ["hdiutil", "verify", str(dmg)]
    assert not any(c[0] in ("codesign", "xcrun", "spctl") for c in cmds)


def test_signed_plan_uses_sign_notarize_in_the_right_order(project):
    dist, build, app = project
    dmg = md.dmg_path("1.0.0", dist)
    plan = md.build_plan(app, dmg, "1.0.0", signed=True, identity="Developer ID Application: Test (ABCDE12345)",
                         staging=build / "dmg-root")
    cmds = commands(plan)
    first = [c[0] for c in cmds]
    ditto, create = first.index("ditto"), cmds.index(next(c for c in cmds if c[:2] == ["hdiutil", "create"]))
    app_signs = [i for i, c in enumerate(cmds) if c[0] == "codesign" and str(app) in c[-1]]
    assert app_signs and max(app_signs) < ditto  # l'app si firma prima di copiarla nel .dmg
    dmg_sign = next(i for i, c in enumerate(cmds) if c[0] == "codesign" and c[-1] == str(dmg) and "--sign" in c)
    submit = next(i for i, c in enumerate(cmds) if c[:3] == ["xcrun", "notarytool", "submit"])
    staple = next(i for i, c in enumerate(cmds) if c[:3] == ["xcrun", "stapler", "staple"])
    assert create < dmg_sign < submit < staple < len(cmds) - 1 and cmds[-1][0] == "shasum"
    assert "--keychain-profile" in cmds[submit] and "astrotwo-notary" in cmds[submit]


def test_dry_run_prints_and_runs_nothing(project, capsys):
    assert md.main([]) == 0
    out = capsys.readouterr().out
    assert "Prova a secco" in out and "[prova a secco] hdiutil create" in out
    assert not (project[0] / f"AstroTwo-{md.version()}.dmg").exists()
    assert md.main(["--signed"]) == 0  # anche con la firma: nessun Portachiavi letto, nessun comando
    assert "notarytool submit" in capsys.readouterr().out


def test_dry_run_without_a_built_app(project, capsys):
    import shutil

    shutil.rmtree(project[2])
    assert md.main([]) == 0
    assert "non c'è ancora" in capsys.readouterr().out
    assert md.main(["--execute"]) == 2
    assert "DMG_APP_MISSING" in capsys.readouterr().err


def test_existing_dmg_is_never_overwritten(project, capsys):
    dmg = md.dmg_path(md.version(), project[0])
    dmg.write_bytes(b"old")
    assert md.main(["--execute"]) == 2
    assert "DMG_EXISTS" in capsys.readouterr().err and dmg.read_bytes() == b"old"


@pytest.mark.parametrize("option", ["--password=x", "--apple-id", "--team-id=ABC", "--key"])
def test_credentials_are_refused(project, capsys, option):
    assert md.main(["--signed", option]) == 2
    assert "SIGN_CREDENTIALS_REFUSED" in capsys.readouterr().err


def test_execute_with_fake_tools_writes_the_checksum(project, monkeypatch, capsys):
    """Percorso ``--execute`` con strumenti finti: i comandi nell'ordine, cartella di lavoro in ``build/``,
    impronta SHA-256 scritta dallo script (non da ``shasum``)."""
    dist, build, app = project
    dmg = md.dmg_path(md.version(), dist)
    seen = []
    (build / "dmg-root").mkdir()
    (build / "dmg-root" / "old").write_text("x")

    def fake_run(command, **kwargs):
        seen.append(command)
        if command[0] == "mkdir":
            Path(command[-1]).mkdir(parents=True, exist_ok=True)
        if command[:2] == ["hdiutil", "create"]:
            Path(command[-1]).write_bytes(b"fake dmg")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert md.main(["--execute"]) == 0
    assert not (build / "dmg-root" / "old").exists()  # cartella di lavoro nuova
    assert [c[0] for c in seen] == ["mkdir", "ditto", "hdiutil", "hdiutil"]  # il collegamento lo crea lo script
    checksum = Path(f"{dmg}.sha256").read_text()
    assert checksum == f"{hashlib.sha256(b'fake dmg').hexdigest()}  {dmg.name}\n"


def test_staging_outside_build_is_refused(project, tmp_path):
    plan = md.Plan()
    plan.add(["rm", "-rf", tmp_path / "elsewhere"], "x", action="clean_staging")
    with pytest.raises(md.DmgError) as err:
        md.run_plan(plan, execute=True, staging=tmp_path / "elsewhere")
    assert err.value.code == "DMG_STAGING_UNSAFE"


def test_staged_folder_holds_only_the_app_and_the_applications_link(project, monkeypatch):
    """D60-7 (2026-11-11): la cartella data a ``hdiutil create -srcfolder`` contiene **solo** ``AstroTwo.app`` e il
    collegamento simbolico ``Applications`` → ``/Applications`` (l'utente trascina l'app lì); nessun file di aspetto
    della finestra (``.background``, ``.DS_Store``). ``mkdir`` e ``ditto`` sono finti ma fanno davvero il loro lavoro
    nella cartella temporanea; il collegamento lo crea lo script."""
    import shutil

    dist, build, app = project
    staged = {}

    def fake_run(command, **kwargs):
        if command[0] == "mkdir":
            Path(command[-1]).mkdir(parents=True, exist_ok=True)
        elif command[0] == "ditto":
            shutil.copytree(command[1], command[2], symlinks=True)
        elif command[:2] == ["hdiutil", "create"]:
            src = Path(command[command.index("-srcfolder") + 1])
            staged.update({p.name: p for p in src.iterdir()})
            staged["_links"] = {p.name: str(p.readlink()) for p in src.iterdir() if p.is_symlink()}
            Path(command[-1]).write_bytes(b"fake dmg")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert md.main(["--execute"]) == 0
    links = staged.pop("_links")
    assert sorted(staged) == ["Applications", "AstroTwo.app"]
    assert links == {"Applications": "/Applications"}  # destinazione assoluta, non relativa
    assert (staged["AstroTwo.app"] / "Contents" / "MacOS" / "AstroTwo").is_file()
    assert not staged["AstroTwo.app"].is_symlink()  # l'app è copiata, non collegata
