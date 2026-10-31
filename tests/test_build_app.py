# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Strumento di costruzione dell'app (``scripts/build_app.py``, 60 §3.3–§3.8): T2, T3, T4, T18 e controlli V6.

Nessuna costruzione vera qui (quella è T12, eseguita a mano con lo script): si provano le parti pure su file
temporanei e su copie di librerie già installate.
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_app.py"
spec = importlib.util.spec_from_file_location("build_app", SCRIPT)
build_app = importlib.util.module_from_spec(spec)
sys.modules["build_app"] = build_app  # richiesto da dataclass
spec.loader.exec_module(build_app)

SITE = Path(next(p for p in sys.path if p.endswith("site-packages")))
QTCORE = SITE / "PySide6" / "Qt" / "lib" / "QtCore.framework" / "Versions" / "A" / "QtCore"
CSPICE = SITE / "spiceypy" / "utils" / "libcspice.dylib"


def test_t2_spec_contains_data_exclusions_and_plist(tmp_path):
    stage = tmp_path / "stage"
    text = build_app.spec_text(entry=tmp_path / "launch.py", stage=stage, icon=None, version="0.1.0-beta.3",
                               build=1, metadata=["astropy", "keyring"])
    compile(text, "AstroTwo.spec", "exec")  # Python valido
    for needle in ("astrotwo/ui/i18n", "astrotwo_it.qm", "pck00011.tpc", "astrotwo/core/data/naif",
                   str(stage / "licenses"), "BUILD_INFO.json", "keyring.backends.macOS", "'tkinter'",
                   "'PySide6.QtQml'", "build_app.keep_entry", "copy_metadata", "'dev.pages.astrotwo'",
                   "'CFBundleShortVersionString': '0.1.0'", "'CFBundleVersion': '1'", "target_arch=None",
                   "strip=False", "upx=False", "**/tests/**"):
        assert needle in text, needle
    assert "astrotwo_it.ts" not in text
    plist = build_app.info_plist("0.1.0-beta.3", 1, "14.4", True)
    assert plist["LSMinimumSystemVersion"] == "14.4" and plist["CFBundleIconFile"] == "AstroTwo.icns"
    assert str(ROOT) not in repr(plist)


def test_t2_qt_plugins_and_translations_filter():
    keep = build_app.keep_entry
    assert keep("PySide6/Qt/plugins/platforms/libqcocoa.dylib")
    assert not keep("PySide6/Qt/plugins/platforms/libqoffscreen.dylib")
    assert not keep("PySide6/Qt/plugins/imageformats/libqpdf.dylib")
    assert not keep("PySide6/Qt/plugins/sqldrivers/libqsqlite.dylib")
    assert keep("PySide6/Qt/translations/qtbase_it.qm")
    assert not keep("PySide6/Qt/translations/qtbase_de.qm")
    assert not keep("PySide6/Qt/qml/QtQuick/qmldir")
    assert keep("astropy/units/si.py") and keep("PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore")
    assert not keep("PySide6/Qt/lib/QtNetwork.framework/Versions/A/QtNetwork")
    assert keep("QtCore") and not keep("QtNetwork")  # collegamenti nella radice dell'app


def test_versions():
    assert build_app.short_version("0.1.0-beta.3") == "0.1.0"
    version, build = build_app.bundle_version()
    assert version == "0.1.0-beta.3" and build == 3


@pytest.mark.skipif(not (QTCORE.is_file() and CSPICE.is_file()), reason="librerie della ruota non installate")
def test_t3_minimum_macos_is_the_maximum(tmp_path):
    shutil.copy(CSPICE, tmp_path / "libcspice.dylib")
    assert build_app.minimum_macos(tmp_path) == "11.0"  # minos di libcspice nella ruota di spiceypy 8.3.0
    shutil.copy(QTCORE, tmp_path / "QtCore")
    assert build_app.minimum_macos(tmp_path) == "14.4"  # QtCore della ruota di PySide6 6.12.0, slice arm64
    (tmp_path / "notes.txt").write_text("non è un Mach-O")
    assert build_app.minimum_macos(tmp_path) == "14.4"


@pytest.mark.skipif(not CSPICE.is_file() or shutil.which("install_name_tool") is None,
                    reason="serve libcspice e install_name_tool")
def test_t4_reference_outside_the_app(tmp_path):
    app = tmp_path / "AstroTwo.app"
    (app / "Contents" / "Frameworks").mkdir(parents=True)
    library = app / "Contents" / "Frameworks" / "libcspice.dylib"
    shutil.copy(CSPICE, library)
    assert build_app.check_references(app).status == "ok"
    subprocess.run(["install_name_tool", "-add_rpath", "/opt/homebrew/lib", str(library)], check=True,
                   capture_output=True)
    check = build_app.check_references(app)
    assert check.status == "failed"
    assert check.detail == {"Contents/Frameworks/libcspice.dylib": ["/opt/homebrew/lib"]}


def test_v6_snapshot_detects_writes(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    before = build_app.snapshot(tmp_path)
    assert build_app.check_no_writes(before, build_app.snapshot(tmp_path)).status == "ok"
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"x")
    check = build_app.check_no_writes(before, build_app.snapshot(tmp_path))
    assert check.status == "failed" and check.detail["added"] == ["__pycache__/x.pyc"]


@pytest.mark.skipif(shutil.which("iconutil") is None, reason="iconutil non disponibile")
def test_t18_iconset_from_the_owner_svg(qapp, tmp_path):
    written = build_app.make_iconset(build_app.ICON_SVG, tmp_path / "AstroTwo.iconset")
    assert sorted(p.name for p in written) == sorted(build_app.ICONSET_SIZES)
    from PySide6.QtGui import QImage
    for path in written:
        image = QImage(str(path))
        side = build_app.ICONSET_SIZES[path.name]
        assert (image.width(), image.height()) == (side, side) and not image.isNull()
        assert any(image.pixelColor(x, side // 2).alpha() > 0 for x in range(side))  # non vuota
    subprocess.run(["iconutil", "-c", "icns", str(tmp_path / "AstroTwo.iconset"), "-o", str(tmp_path / "A.icns")],
                   check=True, capture_output=True)
    assert (tmp_path / "A.icns").stat().st_size > 0


@pytest.mark.skipif(not CSPICE.is_file(), reason="serve una libreria Mach-O della ruota")
def test_d60_3_qt_binaries_restored_from_the_wheel(tmp_path):
    wheel = tmp_path / "site-packages"
    (wheel / "PySide6" / "Qt" / "plugins" / "styles").mkdir(parents=True)
    original = wheel / "PySide6" / "Qt" / "plugins" / "styles" / "libqmacstyle.dylib"
    shutil.copy(CSPICE, original)
    app = tmp_path / "AstroTwo.app"
    bundled = app / "Contents" / "Frameworks" / "PySide6" / "Qt" / "plugins" / "styles" / "libqmacstyle.dylib"
    bundled.parent.mkdir(parents=True)
    data = bytearray(CSPICE.read_bytes())
    data[-1] ^= 0xFF  # copia "modificata" da PyInstaller
    bundled.write_bytes(bytes(data))
    assert build_app.restore_qt_from_wheel(app, wheel) == 1
    assert bundled.read_bytes() == original.read_bytes()
    assert build_app.check_qt_unmodified(app, wheel).status == "ok"


@pytest.mark.skipif(not QTCORE.is_file(), reason="serve QtCore della ruota")
def test_v5_resigned_qt_equals_the_wheel_except_the_signature(tmp_path):
    """La firma ad hoc dell'app cambia solo la firma e ``vmsize`` di ``__LINKEDIT``: V5 li ignora, niente altro."""
    resigned = tmp_path / "QtCore"
    shutil.copy(QTCORE, resigned)
    subprocess.run(["codesign", "--force", "--sign", "-", "--identifier", "org.qt-project.QtCore", str(resigned)],
                   check=True, capture_output=True)
    assert resigned.read_bytes() != QTCORE.read_bytes()
    assert build_app._unsigned_digest(resigned, tmp_path) == build_app._unsigned_digest(QTCORE, tmp_path)
    data = bytearray(resigned.read_bytes())
    data[len(data) // 4] ^= 0xFF  # un byte del codice (a metà della parte x86_64), fuori da intestazione e firma
    resigned.write_bytes(bytes(data))
    subprocess.run(["codesign", "--force", "--sign", "-", str(resigned)], check=True, capture_output=True)
    assert build_app._unsigned_digest(resigned, tmp_path) != build_app._unsigned_digest(QTCORE, tmp_path)
