# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""AstroTwo dentro l'app costruita: punto d'ingresso, file di licenza, sorgenti e autocontrollo.

Specifica: ``mdfiles/60-distribuzione-dmg.md`` (stato ``approvato``), §3.7, §3.9 e §7.

L'app si costruisce con ``scripts/build_app.py`` (PyInstaller, A2). Dentro l'app ``sys._MEIPASS`` è
``Contents/Frameworks``, dove PyInstaller rende raggiungibili anche i dati di ``Contents/Resources``; nello sviluppo
gli stessi file stanno nella radice del progetto. Questo modulo non calcola nulla di scientifico: l'autocontrollo
verifica che codice e dati ci siano e si carichino, non i loro valori (quelli li controllano i test dei moduli).
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import secrets
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import astrotwo
from astrotwo.core.commands import ResultMessage

#: Identificativo dell'app (01 §6) e servizio del Portachiavi riservato all'autocontrollo (60 §7): mai quello delle
#: chiavi vere (``dev.pages.astrotwo.ai``, 31 §3.1).
BUNDLE_ID = "dev.pages.astrotwo"
SELF_CHECK_SERVICE = "dev.pages.astrotwo.selfcheck"

#: Sorgente di AstroTwo (D60-1, decisa il 2026-10-25): repository con un tag per versione e archivio accanto al .dmg.
REPOSITORY = "https://github.com/guidogg13/AstroTwo"

#: Sorgenti esatti di PySide6/shiboken6 e Qt delle librerie incluse (01 §6.1 punto 3, 60 §3.7; SHA-256 verificate il
#: 2026-10-16 per PySide6 e il 2026-10-25 per Qt, V-b).
PYSIDE_VERSION = "6.12.0"
PYSIDE_SOURCE = ("https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/"
                 "pyside-setup-everywhere-src-6.12.0.zip",
                 "15b25c9e06f3acb8930c318192f3c20aee162f4b8d01bf4b4c60193c924cd847")
QT_VERSION = "6.12.0"
QT_SOURCES_URL = "https://download.qt.io/official_releases/qt/6.12/6.12.0/"
QT_SOURCES = (
    ("https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qtbase-everywhere-src-6.12.0.tar.xz",
     "a951bd163c7b80fc6b8c88d7668fb56abf91c152373e13c10666763238131307"),
    ("https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qtsvg-everywhere-src-6.12.0.tar.xz",
     "e4ab39534ec97987b1b9b60ef7f4d3253d5912a69f8c713a01753174a4029331"),
)

#: File di licenza dell'app, nell'ordine della finestra Licenze (§3.9).
LICENSE_NAMES = ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES", "SOURCES.txt")
BUILD_INFO_NAME = "BUILD_INFO.json"
#: Riga scritta alla prima vista con ``--quit-after-first-view`` (controllo V7 di §3.8).
FIRST_VIEW_LINE = "astrotwo: first_view"
PROJECT_ROOT = Path(astrotwo.__file__).resolve().parents[2]


def is_bundled() -> bool:
    """Vero dentro l'app costruita da PyInstaller."""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def bundle_contents() -> Path | None:
    """Cartella ``Contents`` dell'app, ``None`` nello sviluppo."""
    return Path(sys._MEIPASS).resolve().parent if is_bundled() else None


def licenses_dir() -> Path:
    """``Contents/Resources/licenses`` nell'app (tramite ``sys._MEIPASS``), la radice del progetto nello sviluppo."""
    return Path(sys._MEIPASS) / "licenses" if is_bundled() else PROJECT_ROOT


def license_files(folder: Path | None = None) -> dict[str, Path]:
    """Percorso di ogni file di :data:`LICENSE_NAMES` (anche se manca) e di ``BUILD_INFO.json`` nell'app."""
    folder = licenses_dir() if folder is None else Path(folder)
    files = {name: folder / name for name in LICENSE_NAMES}
    if is_bundled():
        files[BUILD_INFO_NAME] = Path(sys._MEIPASS) / BUILD_INFO_NAME
    return files


def build_info() -> dict | None:
    """Contenuto di ``BUILD_INFO.json`` dell'app (versione, build, commit, …); ``None`` nello sviluppo o se manca."""
    path = license_files().get(BUILD_INFO_NAME)
    if path is None or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_license(name: str, folder: Path | None = None) -> tuple[str | None, ResultMessage | None]:
    """Testo del file ``name`` oppure ``LICENSE_FILE_MISSING`` (§3.9: la scheda mostra il messaggio, nessun blocco).

    Nello sviluppo ``SOURCES.txt`` non esiste come file: si genera con :func:`sources_text` (stessa forma dell'app).
    """
    path = license_files(folder)[name]
    if not path.is_file() and name == "SOURCES.txt" and folder is None and not is_bundled():
        return sources_text(None), None
    try:
        return path.read_text(encoding="utf-8"), None
    except OSError:
        return None, ResultMessage("LICENSE_FILE_MISSING", f"file di licenza {name} non trovato in {path}",
                                   {"file": name, "path": str(path)})


def sources_text(info: Mapping | None) -> str:
    """Testo di ``SOURCES.txt`` (inglese, come i testi di licenza; 60 §3.7 punto 3).

    ``info``: ``BUILD_INFO.json`` della costruzione; ``None`` nello sviluppo (nessun commit dichiarato).
    """
    version = (info or {}).get("version", astrotwo.__version__)
    if info:
        build = f"build {info.get('build')}, commit {info.get('commit')}" + (
            " (built from a tree with uncommitted changes)" if info.get("dirty") else "")
    else:
        build = "development tree, not a built application"
    qt_lines = "\n".join(f"  {url}\n    SHA-256 {digest}" for url, digest in QT_SOURCES)
    return f"""AstroTwo {version} ({build})
Copyright (C) 2026 Guido Ratti. AstroTwo is free software under the GNU General Public License,
version 3 or (at your option) any later version (GPL-3.0-or-later): see LICENSE.

Source code of AstroTwo (GPL-3.0, section 6)
--------------------------------------------
Repository: {REPOSITORY}
Tag of this version: v{version}
A source archive of this exact commit is published next to the disk image (.dmg) of this version.

Qt for Python (PySide6 and shiboken6 {PYSIDE_VERSION}, LGPL-3.0-only)
-------------------------------------------------------------
Exact source of the PySide6 and shiboken6 libraries included in this application:
  {PYSIDE_SOURCE[0]}
    SHA-256 {PYSIDE_SOURCE[1]}

Qt {QT_VERSION} (LGPL-3.0-only)
------------------------
Exact source of the Qt libraries included in this application (modules qtbase and qtsvg):
{qt_lines}
Complete Qt {QT_VERSION} sources: {QT_SOURCES_URL}

The Qt libraries are included unmodified, as separate frameworks and plug-ins of the PySide6 {PYSIDE_VERSION}
wheel. Only their code signature is replaced by the ad-hoc signature of the application.

How to replace the Qt libraries (LGPL-3.0, section 4)
-----------------------------------------------------
The Qt libraries are the files in AstroTwo.app/Contents/Frameworks/PySide6/Qt/lib/*.framework and the plug-ins
in AstroTwo.app/Contents/Frameworks/PySide6/Qt/plugins/. Replace them with a compatible build (same Qt minor
version, binary compatible with PySide6 {PYSIDE_VERSION}), then sign the application again:
  codesign --force --deep --sign - AstroTwo.app

Terms of use
------------
AstroTwo has no terms of use other than the GPL-3.0. Nothing restricts analysing, reverse engineering,
debugging or modifying AstroTwo or the libraries it contains.
"""


# --------------------------------------------------------------------------
# Autocontrollo (§7, controllo V4 di §3.8)
# --------------------------------------------------------------------------


def _inside(path: object, root: Path | None) -> bool:
    return root is not None and Path(str(path)).resolve().is_relative_to(root)


def _item(name: str, ok: bool | None, detail: object) -> dict:
    return {"name": name, "status": "not_bundled" if ok is None else ("ok" if ok else "failed"), "detail": detail}


def _guarded(name: str, function) -> dict:
    try:
        return function()
    except Exception as exc:  # una voce che solleva è un fallimento con il motivo, mai un blocco del rapporto
        return _item(name, False, f"{type(exc).__name__}: {exc}")


def _check_python(root: Path | None) -> list[dict]:
    items = [_item("python", sys.version_info[:2] == (3, 12), {"version": sys.version.split()[0],
                                                                "executable": sys.executable})]
    if root is None:
        items.append(_item("python_inside_app", None, "development environment"))
        items.append(_item("sys_path_inside_app", None, "development environment"))
    else:
        items.append(_item("python_inside_app", _inside(sys.prefix, root) and _inside(sys.executable, root),
                           {"prefix": sys.prefix}))
        outside = [p for p in sys.path if p and not _inside(p, root)]
        items.append(_item("sys_path_inside_app", not outside, {"outside": outside}))
    return items


def _check_modules() -> dict:
    failed = {}
    names = ["astrotwo"] + [m.name for m in pkgutil.walk_packages(astrotwo.__path__, "astrotwo.")]
    for name in names:
        try:
            importlib.import_module(name)
        except Exception as exc:
            failed[name] = f"{type(exc).__name__}: {exc}"
    return _item("astrotwo_modules", not failed, {"imported": len(names) - len(failed), "failed": failed})


def _check_data(root: Path | None) -> list[dict]:
    from astrotwo.core.planetary_data import KERNEL_PATH
    from astrotwo.ui.main_window import I18N_DIR, ICONS_DIR

    package = Path(astrotwo.__file__).resolve().parent
    required = [I18N_DIR / "astrotwo_it.qm", ICONS_DIR / "LICENSE", KERNEL_PATH, KERNEL_PATH.with_name("README.md")]
    missing = [str(p) for p in required if not p.is_file()]
    icons = len(list(ICONS_DIR.glob("*.svg")))
    items = [_item("astrotwo_data", not missing and icons > 0, {"missing": missing, "icons": icons,
                                                                 "package": str(package)})]
    licenses = license_files()
    absent = [name for name, path in licenses.items() if not path.is_file()]
    if root is None:
        absent = [name for name in absent if name != "SOURCES.txt"]  # generato al volo nello sviluppo (§3.9)
    items.append(_item("license_files", not absent, {"folder": str(licenses_dir()), "missing": absent}))
    return items


def _check_qt(root: Path | None) -> list[dict]:
    from PySide6.QtCore import QCoreApplication, QLibraryInfo, QTranslator
    from PySide6.QtGui import QImageReader

    from astrotwo.ui.main_window import I18N_DIR

    app = QCoreApplication.instance() or QCoreApplication([sys.argv[0] if sys.argv else "astrotwo"])
    plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
    translations = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    version = QLibraryInfo.version().toString()
    items = [_item("qt_version", version == QT_VERSION, {"qt": version, "expected": QT_VERSION})]
    if root is None:
        items.append(_item("qt_paths_inside_app", None, "development environment"))
    else:
        items.append(_item("qt_paths_inside_app", _inside(plugins, root) and _inside(translations, root),
                           {"plugins": str(plugins), "translations": str(translations)}))
    needed = ["platforms/libqcocoa.dylib", "styles/libqmacstyle.dylib", "imageformats/libqsvg.dylib",
              "imageformats/libqjpeg.dylib", "iconengines/libqsvgicon.dylib"]
    missing = [name for name in needed if not (plugins / name).is_file()]
    formats = sorted(bytes(f).decode() for f in QImageReader.supportedImageFormats())
    lacking = [f for f in ("jpeg", "png", "svg") if f not in formats]
    items.append(_item("qt_plugins", not missing and not lacking, {"missing": missing, "formats": formats}))
    ours, theirs = QTranslator(app), QTranslator(app)
    loaded = {"astrotwo_it": ours.load(str(I18N_DIR / "astrotwo_it.qm")),
              "qtbase_it": theirs.load("qtbase_it", str(translations))}
    items.append(_item("translations", all(loaded.values()), loaded))
    return items


def _check_certificates(root: Path | None) -> dict:
    import ssl

    import certifi

    where = Path(certifi.where())
    context = ssl.create_default_context(cafile=str(where))
    ok = where.is_file() and context.cert_store_stats()["x509_ca"] > 0 and (root is None or _inside(where, root))
    return _item("certificates", ok, {"certifi": str(where), "openssl": ssl.OPENSSL_VERSION})


def _check_astropy_data(root: Path | None) -> dict:
    import astropy_iers_data
    from astropy.utils import iers

    table = iers.IERS_B.open(astropy_iers_data.IERS_B_FILE)
    files = [astropy_iers_data.IERS_A_FILE, astropy_iers_data.IERS_B_FILE, astropy_iers_data.IERS_LEAP_SECOND_FILE]
    ok = all(Path(f).is_file() for f in files) and len(table) > 0
    ok = ok and (root is None or all(_inside(f, root) for f in files))
    return _item("astropy_iers_data", ok, {"files": files, "iers_b_rows": len(table)})


def _check_naif() -> dict:
    import spiceypy

    from astrotwo.core import planetary_data

    planetary_data._load_kernel()  # carica il PCK del 19 dopo il controllo della sua impronta SHA-256
    loaded = spiceypy.ktotal("ALL")
    return _item("naif_kernel", loaded >= 1, {"kernel": str(planetary_data.KERNEL_PATH), "kernels": loaded})


def _check_keyring() -> dict:
    from astrotwo.ai.keychain_keys import KeychainStore

    store = KeychainStore(service=SELF_CHECK_SERVICE)  # crea solo il backend macOS: nessun accesso alle voci
    return _item("keyring_backend", type(store._backend).__module__ == "keyring.backends.macOS",
                 {"backend": f"{type(store._backend).__module__}.{type(store._backend).__name__}"})


def _check_keychain_roundtrip() -> dict:
    from astrotwo.ai.keychain_keys import KeychainStore

    store = KeychainStore(service=SELF_CHECK_SERVICE)
    profile, token = "self-check", "selfcheck-" + secrets.token_hex(8)
    store.store_key(profile, token)
    try:
        read = store.get_key(profile).reveal() == token
    finally:
        store.delete_key(profile)
    return _item("keychain_roundtrip", read and not store.has_key(profile), {"service": SELF_CHECK_SERVICE})


def _check_cache(root: Path | None) -> dict:
    from astrotwo.core.cache import default_cache_root

    folder = default_cache_root()
    return _item("cache_outside_app", not _inside(folder, root), {"cache": str(folder)})


def self_check(keychain: bool = False) -> dict:
    """Rapporto dell'autocontrollo: ``{"ok", "bundled", "version", "checks": [{"name", "status", "detail"}]}``.

    ``status``: ``ok``, ``failed`` o ``not_bundled`` (voce che ha senso solo dentro l'app). Il Portachiavi si usa
    solo con ``keychain=True`` (a mano, servizio :data:`SELF_CHECK_SERVICE`); altrimenti si crea solo il backend.
    """
    root = bundle_contents()
    checks = _check_python(root)
    checks.append(_guarded("astrotwo_modules", _check_modules))
    for name, function in (("astrotwo_data", lambda: _check_data(root)), ("qt", lambda: _check_qt(root))):
        result = _guarded(name, function)
        checks += result if isinstance(result, list) else [result]
    for name, function in (("certificates", lambda: _check_certificates(root)),
                           ("astropy_iers_data", lambda: _check_astropy_data(root)),
                           ("naif_kernel", _check_naif), ("keyring_backend", _check_keyring),
                           ("cache_outside_app", lambda: _check_cache(root))):
        checks.append(_guarded(name, function))
    if keychain:
        checks.append(_guarded("keychain_roundtrip", _check_keychain_roundtrip))
    return {"ok": all(c["status"] != "failed" for c in checks), "bundled": root is not None,
            "version": astrotwo.__version__, "checks": checks}


# --------------------------------------------------------------------------
# Punto d'ingresso dell'app
# --------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """``--self-check`` / ``--self-check-keychain``: rapporto JSON ed uscita (0 se tutto ``ok``), nessuna finestra;
    ``--quit-after-first-view``: l'app esce dopo la prima vista del cielo (controllo V7); altrimenti l'app normale."""
    args = list(sys.argv[1:] if argv is None else argv)
    if is_bundled():
        sys.dont_write_bytecode = True  # nessun .pyc scritto (V6)
    if "--self-check" in args or "--self-check-keychain" in args:
        report = self_check(keychain="--self-check-keychain" in args)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["ok"] else 1
    from astrotwo.ui.main_window import main as window_main

    rest = [a for a in args if a != "--quit-after-first-view"]
    hook = _quit_after_first_view if "--quit-after-first-view" in args else None
    return window_main([sys.argv[0] if sys.argv else "AstroTwo", *rest], on_first_view=hook)


def _quit_after_first_view(app, window) -> None:
    """Scrive ``first_view`` (letto dalla misura di V7) e chiude la finestra senza la domanda di conferma.

    I comandi delle preferenze eseguiti all'avvio rendono la sessione "non salvata": la chiusura normale chiederebbe
    conferma (40 §3.8); qui si risponde sì, così la chiusura fa le stesse pulizie di sempre (thread, tile).
    """
    from PySide6.QtCore import QTimer

    print(FIRST_VIEW_LINE, flush=True)
    window.confirm = lambda title, text: True

    def close() -> None:
        window.close()
        app.quit()

    QTimer.singleShot(0, close)


if __name__ == "__main__":
    sys.exit(main())
