# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test di ``scripts/sign_notarize.py`` (60-distribuzione-dmg.md §3.12, T19): solo le parti pure e la prova a secco.

Nessun comando viene eseguito: ``codesign``, ``security``, ``xcrun`` e ``spctl`` non partono mai (decisione del
proprietario del 2026-11-10: script preparato, non eseguito finché l'account Apple Developer non è pronto)."""

from __future__ import annotations

import importlib.util
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sign_notarize.py"
spec = importlib.util.spec_from_file_location("sign_notarize", SCRIPT)
sn = importlib.util.module_from_spec(spec)
sys.modules["sign_notarize"] = sn
spec.loader.exec_module(sn)

MACHO = b"\xcf\xfa\xed\xfe" + b"\0" * 28
IDENTITY = "Developer ID Application: Test Person (ABCDE12345)"


@pytest.fixture(autouse=True)
def no_commands(monkeypatch):
    """Ogni tentativo di eseguire un comando fa fallire il test."""
    def refuse(*args, **kwargs):
        raise AssertionError(f"comando eseguito: {args[0] if args else kwargs}")
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def fake_app(tmp_path: Path) -> Path:
    app = tmp_path / "AstroTwo.app"
    files = {"Contents/MacOS/AstroTwo": MACHO,
             "Contents/Frameworks/libpython3.12.dylib": MACHO,
             "Contents/Frameworks/numpy/_core/_multiarray_umath.cpython-312-darwin.so": MACHO,
             "Contents/Frameworks/PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore": MACHO,
             "Contents/Frameworks/PySide6/Qt/lib/QtCore.framework/Versions/A/Resources/Info.plist": b"<plist/>",
             "Contents/Resources/astrotwo/data/readme.txt": b"testo",
             "Contents/Info.plist": b"<plist/>"}
    for name, data in files.items():
        path = app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (app / "Contents/Resources/libpython3.12.dylib").symlink_to(app / "Contents/Frameworks/libpython3.12.dylib")
    return app


def test_identities_from_security_output():
    output = ('  1) 0123456789ABCDEF0123456789ABCDEF01234567 "Apple Development: Test Person (XYZ)"\n'
              f'  2) 89ABCDEF0123456789ABCDEF0123456789ABCDEF "{IDENTITY}"\n'
              "     2 valid identities found\n")
    assert sn.developer_identities(output) == [IDENTITY]
    assert sn.choose_identity([IDENTITY], None) == IDENTITY
    for identities, wanted, code in (([], None, "SIGN_IDENTITY_MISSING"),
                                     ([IDENTITY, IDENTITY + "x"], None, "SIGN_IDENTITY_AMBIGUOUS"),
                                     ([IDENTITY], "Apple Development: X", "SIGN_IDENTITY_INVALID"),
                                     ([IDENTITY], IDENTITY + "x", "SIGN_IDENTITY_MISSING")):
        with pytest.raises(sn.SignError) as err:
            sn.choose_identity(identities, wanted)
        assert err.value.code == code


def test_signing_order_inside_out(tmp_path):
    app = fake_app(tmp_path)
    order = [p.relative_to(app).as_posix() for p in sn.signing_order(app)]
    assert order == ["Contents/Frameworks/numpy/_core/_multiarray_umath.cpython-312-darwin.so",
                     "Contents/Frameworks/libpython3.12.dylib",
                     "Contents/Frameworks/PySide6/Qt/lib/QtCore.framework",
                     "Contents/MacOS/AstroTwo", "."]
    # nessun file di dati, nessun collegamento simbolico, nessun binario dentro un .framework firmato a parte


def test_app_plan_hardened_runtime_timestamp_no_deep(tmp_path):
    app = fake_app(tmp_path)
    plan = sn.app_plan(app, IDENTITY, tmp_path / "e.plist")
    signs = [s.command for s in plan.steps if s.command[:2] == ["codesign", "--force"]]
    assert len(signs) == 5
    for command in signs:
        assert command[2:7] == ["--options", "runtime", "--timestamp", "--sign", IDENTITY]
        assert "--deep" not in command
    with_entitlements = [c[-1] for c in signs if "--entitlements" in c]
    assert with_entitlements == [str(app / "Contents/MacOS/AstroTwo"), str(app)]
    assert plan.steps[-2].command[:5] == ["codesign", "--verify", "--deep", "--strict", "--verbose=2"]


def test_entitlements_are_minimal():
    data = plistlib.loads(sn.entitlements_bytes())
    assert data == {"com.apple.security.cs.allow-unsigned-executable-memory": True}
    assert not any("disable-library-validation" in k or "get-task-allow" in k for k in data)


def test_notarize_plan_uses_only_the_keychain_profile(tmp_path):
    dmg = tmp_path / "AstroTwo.dmg"
    plan = sn.notarize_plan(dmg, sn.KEYCHAIN_PROFILE)
    submit = plan.steps[0].command
    assert submit[:4] == ["xcrun", "notarytool", "submit", str(dmg)]
    assert submit[submit.index("--keychain-profile") + 1] == "astrotwo-notary" and "--wait" in submit
    arguments = {a for s in plan.steps for a in s.command}
    assert not arguments & set(sn.FORBIDDEN_OPTIONS)
    assert [s.command[:3] for s in plan.steps[1:3]] == [["xcrun", "stapler", "staple"],
                                                         ["xcrun", "stapler", "validate"]]
    assert plan.steps[3].command[0] == "spctl"


@pytest.mark.parametrize("option", ["--password", "--apple-id=a@b.c", "--team-id", "--key", "--issuer"])
def test_credentials_are_refused(option, capsys):
    assert sn.main(["notarize", "x.dmg", option, "segreto"] if "=" not in option else ["notarize", "x.dmg", option]) == 2
    assert "SIGN_CREDENTIALS_REFUSED" in capsys.readouterr().err


def test_dry_run_executes_nothing_and_writes_nothing(tmp_path, monkeypatch, capsys):
    app = fake_app(tmp_path)
    monkeypatch.setattr(sn, "DIST", tmp_path / "dist")
    monkeypatch.setattr(sn, "BUILD", tmp_path / "build")
    monkeypatch.setattr(sn, "REPORT", tmp_path / "dist" / "sign-report.json")
    assert sn.main(["app", "--app", str(app)]) == 0
    out = capsys.readouterr().out
    assert "Prova a secco" in out and out.count("[prova a secco] codesign --force") == 5
    assert not (tmp_path / "dist").exists() and not (tmp_path / "build").exists()
    dmg = tmp_path / "AstroTwo.dmg"
    dmg.write_bytes(b"dmg")
    assert sn.main(["dmg", str(dmg)]) == 0 and sn.main(["notarize", str(dmg)]) == 0
    assert "notarytool submit" in capsys.readouterr().out
    assert sn.main(["notarize", str(tmp_path / "manca.dmg")]) == 2
