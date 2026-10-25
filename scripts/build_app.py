# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Costruzione di ``dist/AstroTwo.app`` per macOS su Apple Silicon (60-distribuzione-dmg.md, parte A, sprint 60a).

Uso: ``uv run python scripts/build_app.py`` (opzioni ``--allow-dirty``, ``--skip-tests``, ``--keep-build``,
``--check-only dist/AstroTwo.app``). Passi (§3.3): controlli iniziali, Python 3.12.15 di python-build-standalone
gestito da uv, ambiente ``build/env`` da ``uv.lock`` (``uv sync --frozen``), test di default e controllo di
``THIRD_PARTY_LICENSES`` in quell'ambiente, icona, PyInstaller (``onedir`` + ``BUNDLE``, specifica generata in
``build/AstroTwo.spec``), firma ad hoc (A6), controlli V1–V9 (§3.8), rapporto in ``dist/build-report.json``.

Lo script non legge né scrive il Portachiavi, ``QSettings`` o la cache (regola d'oro 5); cancella solo
``dist/AstroTwo.app``, ``dist/AstroTwo-FAILED.app`` e ``build/``, ignorati da git. I messaggi sono in italiano
sul terminale: è uno strumento di sviluppo, fuori dal catalogo dei messaggi dell'app.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from astrotwo.app_bundle import (  # noqa: E402 - il pacchetto si importa dal sorgente, non da un ambiente installato
    BUILD_INFO_NAME,
    BUNDLE_ID,
    FIRST_VIEW_LINE,
    LICENSE_NAMES,
    PYSIDE_VERSION,
    QT_VERSION,
    sources_text,
)

DIST = ROOT / "dist"
BUILD = ROOT / "build"
ENV = BUILD / "env"
APP_NAME = "AstroTwo"
APP = DIST / f"{APP_NAME}.app"
FAILED_APP = DIST / f"{APP_NAME}-FAILED.app"
REPORT = DIST / "build-report.json"
ICON_SVG = ROOT / "assets" / "icon" / "AstroNew.svg"

#: Python dell'app (decisione del proprietario del 2026-10-25, §3.3 punto 2): aggiornarlo solo su richiesta esplicita.
PYTHON_VERSION = "3.12.15"
PBS_RELEASE = "20261003"

#: Esclusioni (§3.5): modulo → motivo. Solo cose che il codice di AstroTwo non importa (V4 lo controlla).
EXCLUDES: dict[str, str] = {
    "tkinter": "nessuna interfaccia Tk",
    "_tkinter": "nessuna interfaccia Tk",
    "PySide6.QtQml": "nessun QML", "PySide6.QtQuick": "nessun QML", "PySide6.QtQuickWidgets": "nessun QML",
    "PySide6.QtDesigner": "nessun Designer", "PySide6.QtHelp": "nessun Qt Help", "PySide6.QtPdf": "nessun PDF",
    "PySide6.QtPdfWidgets": "nessun PDF", "PySide6.QtNetwork": "la rete passa da requests/httpx2",
    "PySide6.QtSql": "nessun database Qt", "PySide6.QtTest": "solo per i test", "PySide6.QtUiTools": "nessun .ui",
    "PySide6.QtXml": "nessun QtXml", "PySide6.QtConcurrent": "nessun QtConcurrent",
    "PySide6.QtPrintSupport": "nessuna stampa",
    "matplotlib.backends.backend_qtagg": "matplotlib solo per le palette (V-d)",
    "matplotlib.backends.backend_qt": "matplotlib solo per le palette (V-d)",
    "matplotlib.pyplot": "matplotlib solo per le palette (V-d)",
    "pytest": "solo per i test", "IPython": "non usato", "notebook": "non usato",
}

#: Plugin di Qt da tenere (§3.4): cartella → file. Tutti di qtbase o qtsvg (gli altri formati d'immagine vengono da
#: qtimageformats o QtPdf, con altre licenze, e AstroTwo non li usa).
QT_PLUGINS_KEEP: dict[str, frozenset[str]] = {
    "platforms": frozenset({"libqcocoa.dylib"}),
    "styles": frozenset({"libqmacstyle.dylib"}),
    "imageformats": frozenset({"libqsvg.dylib", "libqjpeg.dylib", "libqgif.dylib", "libqico.dylib"}),
    "iconengines": frozenset({"libqsvgicon.dylib"}),
}
QT_TRANSLATIONS_KEEP = frozenset({"qtbase_it.qm"})
#: Framework di Qt da tenere (§3.4): i moduli usati e le loro dipendenze (``QtDBus`` per ``QtGui``, V-d). Un altro
#: framework (es. ``QtNetwork``, dipendenza dei plugin ``tls`` esclusi) resterebbe senza utenti.
QT_FRAMEWORKS_KEEP = frozenset({"QtCore", "QtGui", "QtWidgets", "QtDBus", "QtOpenGL", "QtOpenGLWidgets", "QtSvg"})

#: Pacchetti di cui si raccolgono i dati letti a runtime (§3.4), senza le cartelle dei test.
DATA_PACKAGES = ("astropy", "astropy_iers_data", "astroquery", "pyvo", "certifi", "pds4_tools", "astropy_healpix",
                 "reproject", "mocpy", "spherical_geometry", "matplotlib", "anthropic", "openai")

#: Dati di AstroTwo (sorgente relativo a ROOT → cartella nell'app), agli stessi percorsi del pacchetto (§3.4).
ASTROTWO_DATA = (
    ("src/astrotwo/ui/i18n/astrotwo_it.qm", "astrotwo/ui/i18n"),
    ("src/astrotwo/ui/icons/*.svg", "astrotwo/ui/icons"),
    ("src/astrotwo/ui/icons/LICENSE", "astrotwo/ui/icons"),
    ("src/astrotwo/core/data/naif/pck00011.tpc", "astrotwo/core/data/naif"),
    ("src/astrotwo/core/data/naif/README.md", "astrotwo/core/data/naif"),
)

#: Dimensioni dell'iconset richieste da ``iconutil`` (§3.6): nome → lato in pixel.
ICONSET_SIZES = {f"icon_{s}x{s}{suffix}.png": s * scale for s in (16, 32, 128, 256, 512)
                 for suffix, scale in (("", 1), ("@2x", 2))}

#: Sezioni attese in THIRD_PARTY_LICENSES dentro l'app (V8).
LICENSE_SECTIONS = ("\nPython (CPython, python-build-standalone)", "\nQt 6.12.0, componenti di terze parti",
                    "\nBootloader e hook di esecuzione di PyInstaller")

#: Percorsi permessi nei comandi di caricamento dei Mach-O (V2).
ALLOWED_PREFIXES = ("@rpath/", "@loader_path", "@executable_path", "/System/Library/", "/usr/lib/")


class BuildError(Exception):
    """Errore che ferma la costruzione: ``code`` (§10), messaggio, codice di uscita (1 controllo, 2 prerequisito)."""

    def __init__(self, code: str, message: str, exit_code: int = 1) -> None:
        super().__init__(f"{code}: {message}")
        self.code, self.exit_code = code, exit_code


@dataclass
class Check:
    name: str
    status: str  # ok | failed | not_run
    detail: object = None


@dataclass
class Report:
    steps: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    info: dict = field(default_factory=dict)
    size: dict = field(default_factory=dict)
    startup: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# Utilità
# --------------------------------------------------------------------------


def run(command: list[str], *, cwd: Path = ROOT, env: Mapping[str, str] | None = None, capture: bool = True,
        check: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run([str(c) for c in command], cwd=cwd, env=None if env is None else dict(env),
                            capture_output=capture, text=True, timeout=timeout)
    if check and result.returncode != 0:
        tail = ((result.stdout or "") + (result.stderr or ""))[-2000:] if capture else ""
        raise BuildError("BUILD_STEP_FAILED", f"{' '.join(map(str, command))} → uscita {result.returncode}\n{tail}")
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


_MACHO_MAGIC = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}


def is_macho(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    with path.open("rb") as handle:
        head = handle.read(8)
    if head[:4] == b"\xca\xfe\xba\xbe":  # stessa firma dei .class di Java: un Mach-O universale ha pochi archi
        return int.from_bytes(head[4:8], "big") < 20
    return head[:4] in _MACHO_MAGIC


def macho_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if is_macho(p))


def _load_commands(path: Path, arch: str | None = "arm64") -> str:
    command = ["otool", "-l", path] if arch is None else ["otool", "-arch", arch, "-l", path]
    result = run(command, check=False)
    if result.returncode != 0 and arch is not None:  # file non universale senza quella architettura
        result = run(["otool", "-l", path], check=False)
    return result.stdout


def macho_references(path: Path) -> list[str]:
    """Percorsi di ``LC_LOAD_DYLIB``, ``LC_LOAD_WEAK_DYLIB``, ``LC_REEXPORT_DYLIB`` e ``LC_RPATH`` (tutti gli archi)."""
    text = _load_commands(path, arch=None)
    found = re.findall(r"cmd LC_(?:LOAD_DYLIB|LOAD_WEAK_DYLIB|REEXPORT_DYLIB|LOAD_UPWARD_DYLIB)\n"
                       r"\s+cmdsize \d+\n\s+name (.+?) \(offset", text)
    found += re.findall(r"cmd LC_RPATH\n\s+cmdsize \d+\n\s+path (.+?) \(offset", text)
    return found


def minimum_macos(folder: Path) -> str:
    """Massimo dei ``minos`` (``LC_BUILD_VERSION``, ``LC_VERSION_MIN_MACOSX``) dei Mach-O arm64 di ``folder``."""
    best = (0,)
    for path in macho_files(folder):
        text = _load_commands(path)
        versions = re.findall(r"cmd LC_BUILD_VERSION\n(?:.*\n){2}\s+minos ([\d.]+)", text)
        versions += re.findall(r"cmd LC_VERSION_MIN_MACOSX\n\s+cmdsize \d+\n\s+version ([\d.]+)", text)
        for version in versions:
            best = max(best, tuple(int(x) for x in version.split(".")))
    if best == (0,):
        raise BuildError("BUILD_CHECK_FAILED", f"nessun Mach-O con la versione minima di macOS in {folder}")
    while len(best) > 2 and best[-1] == 0:
        best = best[:-1]
    return ".".join(map(str, best if len(best) > 1 else (*best, 0)))


def env_python() -> Path:
    return ENV / "bin" / "python"


def bundle_version() -> tuple[str, int]:
    """(versione SemVer di ``astrotwo.__version__``, numero di build di ``[tool.astrotwo.bundle]``)."""
    import astrotwo

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return astrotwo.__version__, int(project["tool"]["astrotwo"]["bundle"]["build"])


def short_version(version: str) -> str:
    """``CFBundleShortVersionString``: la parte ``MAJOR.MINOR.PATCH`` (§3.2)."""
    return re.match(r"\d+\.\d+\.\d+", version).group(0)


def info_plist(version: str, build: int, minimum: str | None, icon: bool) -> dict:
    """Chiavi di §3.2; ``minimum``: ``LSMinimumSystemVersion`` letto dai binari dopo PyInstaller."""
    keys = {
        "CFBundleName": APP_NAME, "CFBundleDisplayName": APP_NAME, "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleShortVersionString": short_version(version), "CFBundleVersion": str(build),
        "CFBundleExecutable": APP_NAME, "CFBundlePackageType": "APPL", "LSArchitecturePriority": ["arm64"],
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Copyright © 2026 Guido Ratti. GPL-3.0-or-later.",
    }
    if minimum is not None:
        keys["LSMinimumSystemVersion"] = minimum
    if icon:
        keys["CFBundleIconFile"] = f"{APP_NAME}.icns"
    return keys


# --------------------------------------------------------------------------
# Specifica di PyInstaller (§3.4, §3.5)
# --------------------------------------------------------------------------


def astrotwo_datas(root: Path = ROOT) -> list[tuple[str, str]]:
    datas = []
    for pattern, target in ASTROTWO_DATA:
        matches = sorted(root.glob(pattern))
        if not matches:
            raise BuildError("BUILD_STEP_FAILED", f"dato di AstroTwo mancante: {pattern}")
        datas += [(str(p), target) for p in matches]
    return datas


def keep_entry(dest: str) -> bool:
    """Falso per plugin, traduzioni e QML di Qt non usati (§3.4, §3.5); ``dest``: percorso nell'app."""
    dest = dest.replace("\\", "/")
    if re.fullmatch(r"Qt[A-Za-z0-9]+", dest):  # collegamenti di PyInstaller nella radice (es. QtNetwork)
        return dest in QT_FRAMEWORKS_KEEP
    if dest.startswith("PySide6/Qt/qml") or "/Qt/qml/" in dest:
        return False
    if dest.startswith("PySide6/Qt/translations/"):
        return dest.rsplit("/", 1)[1] in QT_TRANSLATIONS_KEEP
    if dest.startswith("PySide6/Qt/lib/"):
        framework = dest.removeprefix("PySide6/Qt/lib/").split("/", 1)[0]
        return not framework.endswith(".framework") or framework.removesuffix(".framework") in QT_FRAMEWORKS_KEEP
    if dest.startswith("PySide6/Qt/plugins/"):
        folder, _, name = dest.removeprefix("PySide6/Qt/plugins/").partition("/")
        return folder in QT_PLUGINS_KEEP and name.split("/")[0] in QT_PLUGINS_KEEP[folder]
    return True


def spec_text(*, entry: Path, stage: Path, icon: Path | None, version: str, build: int,
              metadata: Iterable[str], root: Path = ROOT) -> str:
    """Testo della specifica di PyInstaller: ``stage`` contiene ``licenses/`` e ``BUILD_INFO.json`` da includere."""
    datas = astrotwo_datas(root) + [(str(stage / "licenses"), "licenses"), (str(stage / BUILD_INFO_NAME), ".")]
    plist = info_plist(version, build, None, icon is not None)
    return f'''# Generato da scripts/build_app.py (60-distribuzione-dmg.md §3.3): non modificarlo a mano.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

datas = {datas!r}
for package in {list(DATA_PACKAGES)!r}:
    datas += collect_data_files(package, excludes=["**/tests/**", "**/tests", "**/*.pyx", "**/*.c", "**/*.h"])
for name in {sorted(metadata)!r}:
    datas += copy_metadata(name)

import importlib.util, sys
_spec = importlib.util.spec_from_file_location("build_app", {str(Path(__file__).resolve())!r})
build_app = importlib.util.module_from_spec(_spec)
sys.modules["build_app"] = build_app
_spec.loader.exec_module(build_app)


a = Analysis(
    [{str(entry)!r}],
    pathex=[{str(root / "src")!r}],
    datas=datas,
    hiddenimports=collect_submodules("astrotwo") + ["keyring.backends.macOS"],
    excludes={sorted(EXCLUDES)!r},
    noarchive=False,
)
a.binaries = [e for e in a.binaries if build_app.keep_entry(e[0])]
a.datas = [e for e in a.datas if build_app.keep_entry(e[0])]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name={APP_NAME!r}, console=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name={APP_NAME!r})
app = BUNDLE(coll, name={APP_NAME + ".app"!r}, icon={None if icon is None else str(icon)!r},
             bundle_identifier={BUNDLE_ID!r}, version={short_version(version)!r}, info_plist={plist!r})
'''


# --------------------------------------------------------------------------
# Icona (§3.6)
# --------------------------------------------------------------------------


def make_iconset(svg: Path, folder: Path) -> list[Path]:
    """PNG dell'iconset di ``iconutil`` disegnati da ``svg`` con ``QSvgRenderer`` (il file SVG non cambia)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    _app = QGuiApplication.instance() or QGuiApplication(["build_app", "-platform", "offscreen"])
    renderer = QSvgRenderer(str(svg))
    if not renderer.isValid():
        raise BuildError("BUILD_STEP_FAILED", f"icona {svg}: SVG non leggibile da Qt")
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for name, side in ICONSET_SIZES.items():
        image = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()
        path = folder / name
        if not image.save(str(path), "PNG"):
            raise BuildError("BUILD_STEP_FAILED", f"icona: {path} non scritto")
        written.append(path)
    return written


# --------------------------------------------------------------------------
# Passi della costruzione (§3.3)
# --------------------------------------------------------------------------


def preliminary_checks(allow_dirty: bool, report: Report) -> dict:
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise BuildError("BUILD_UNSUPPORTED_PLATFORM", f"serve macOS su arm64, qui {sys.platform} "
                         f"{platform.machine()}", 2)
    for tool in ("uv", "codesign", "iconutil", "otool", "ditto", "git"):
        if shutil.which(tool) is None:
            hint = "Xcode Command Line Tools (xcode-select --install)" if tool != "uv" else "https://docs.astral.sh/uv/"
            raise BuildError("BUILD_TOOL_MISSING", f"{tool} non trovato: installarlo ({hint})", 2)
    status = run(["git", "status", "--porcelain"]).stdout.strip()
    if status and not allow_dirty:
        raise BuildError("BUILD_DIRTY_TREE", "modifiche non salvate in git (salvarle o usare --allow-dirty):\n"
                         + status, 2)
    commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    version, build = bundle_version()
    if not run(["git", "tag", "-l", f"v{version}"]).stdout.strip():
        report.warnings.append(f"BUILD_SOURCE_NOT_PUBLIC: il tag v{version} non esiste ancora; prima della "
                               "distribuzione (60b) servono il tag e il repository pubblico (D60-1)")
    else:
        report.warnings.append("BUILD_SOURCE_NOT_PUBLIC: la visibilità pubblica del repository non si controlla da "
                               "qui; va verificata prima della distribuzione (60b, D60-1)")
    return {"version": version, "build": build, "commit": commit, "dirty": bool(status)}


def install_python() -> Path:
    try:
        run(["uv", "python", "install", PYTHON_VERSION])
        found = run(["uv", "python", "find", "--managed-python", PYTHON_VERSION]).stdout.strip()
    except BuildError as exc:
        raise BuildError("BUILD_PYTHON_UNAVAILABLE", str(exc), 2) from exc
    python = Path(found)
    marker = python.resolve().parent.parent / "BUILD"
    release = marker.read_text().strip() if marker.is_file() else "?"
    if release != PBS_RELEASE:
        raise BuildError("BUILD_PYTHON_UNAVAILABLE", f"{python}: rilascio python-build-standalone {release}, atteso "
                         f"{PBS_RELEASE}", 2)
    return python


def create_env(python: Path, keep_build: bool, report: Report) -> None:
    marker = BUILD / "env.json"
    wanted = {"uv_lock": sha256(ROOT / "uv.lock"), "python": str(python)}
    if keep_build and ENV.exists() and marker.is_file() and json.loads(marker.read_text()) == wanted:
        report.warnings.append("--keep-build: ambiente build/env riusato (stesso uv.lock e stesso Python)")
    else:
        shutil.rmtree(ENV, ignore_errors=True)
    env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(ENV)}
    env.pop("VIRTUAL_ENV", None)
    result = run(["uv", "sync", "--frozen", "--python", python, "--group", "dev", "--group", "build"], env=env,
                 check=False)
    if result.returncode != 0:
        raise BuildError("BUILD_LOCK_MISMATCH", f"uv sync --frozen non riuscito:\n{result.stderr[-2000:]}")
    marker.write_text(json.dumps(wanted))


def run_tests() -> None:
    result = run([env_python(), "-m", "pytest", "-q", "-p", "no:cacheprovider"], capture=False, check=False)
    if result.returncode != 0:
        raise BuildError("BUILD_TESTS_FAILED", "test di default falliti in build/env (Python dell'app)")


def check_licenses_file() -> None:
    result = run([env_python(), ROOT / "scripts" / "third_party_licenses.py", "--check"], check=False)
    if result.returncode != 0:
        raise BuildError("BUILD_LICENSES_OUTDATED", "THIRD_PARTY_LICENSES non corrisponde a build/env: rigenerarlo")


def qt_versions() -> dict:
    code = "import PySide6; from PySide6.QtCore import QLibraryInfo; print(PySide6.__version__, " \
           "QLibraryInfo.version().toString())"
    pyside, qt = run([env_python(), "-c", code]).stdout.split()
    if pyside != PYSIDE_VERSION or qt != QT_VERSION:
        raise BuildError("BUILD_QT_VERSION_MISMATCH", f"PySide6 {pyside} / Qt {qt} in build/env, ma SOURCES.txt "
                         f"cita PySide6 {PYSIDE_VERSION} / Qt {QT_VERSION}")
    return {"pyside6": pyside, "qt": qt}


def build_icon(report: Report) -> Path | None:
    if not ICON_SVG.is_file():
        report.warnings.append(f"BUILD_ICON_MISSING: {ICON_SVG.relative_to(ROOT)} non c'è, app senza icona")
        return None
    iconset = BUILD / f"{APP_NAME}.iconset"
    shutil.rmtree(iconset, ignore_errors=True)
    run([env_python(), Path(__file__), "--make-iconset", ICON_SVG, iconset])
    icns = BUILD / f"{APP_NAME}.icns"
    run(["iconutil", "-c", "icns", iconset, "-o", icns])
    return icns


def runtime_distributions() -> list[str]:
    """Nomi dei pacchetti di esecuzione (stessa chiusura di THIRD_PARTY_LICENSES), letti in build/env."""
    code = ("import importlib.util, sys; s = importlib.util.spec_from_file_location('t', sys.argv[1]); "
            "m = importlib.util.module_from_spec(s); sys.modules['t'] = m; s.loader.exec_module(m); "
            "print('\\n'.join(d.metadata['Name'] for d in m.runtime_closure()))")
    return run([env_python(), "-c", code, ROOT / "scripts" / "third_party_licenses.py"]).stdout.split()


def stage_files(info: dict) -> Path:
    stage = BUILD / "stage"
    shutil.rmtree(stage, ignore_errors=True)
    (stage / "licenses").mkdir(parents=True)
    for name in LICENSE_NAMES[:3]:
        shutil.copy2(ROOT / name, stage / "licenses" / name)
    (stage / "licenses" / "SOURCES.txt").write_text(sources_text(info), encoding="utf-8")
    (stage / BUILD_INFO_NAME).write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return stage


def run_pyinstaller(spec: Path) -> None:
    shutil.rmtree(APP, ignore_errors=True)
    shutil.rmtree(DIST / APP_NAME, ignore_errors=True)
    run([env_python(), "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
         "--distpath", DIST, "--workpath", BUILD / "pyinstaller", spec], capture=False)
    shutil.rmtree(DIST / APP_NAME, ignore_errors=True)  # la cartella onedir: resta solo il pacchetto .app
    if not APP.is_dir():
        raise BuildError("BUILD_STEP_FAILED", f"PyInstaller non ha prodotto {APP}")


def wheel_site_packages() -> Path | None:
    return next((ENV / "lib").glob("python3.*/site-packages"), None)


def restore_qt_from_wheel(app: Path, site_packages: Path) -> int:
    """D60-3 (b): ogni binario di Qt dell'app torna la copia esatta della ruota (PyInstaller toglie la parte
    ``x86_64`` e riscrive ``LC_ID_DYLIB``/``LC_RPATH``, §3.7 punto 4). Restituisce quanti file ha sostituito."""
    bundled_qt = app / "Contents" / "Frameworks" / "PySide6" / "Qt"
    replaced = 0
    for path in macho_files(bundled_qt):
        wheel = site_packages / "PySide6" / "Qt" / path.relative_to(bundled_qt)
        if not wheel.is_file():
            raise BuildError("BUILD_CHECK_FAILED", f"{path.relative_to(app)}: nessun file corrispondente nella ruota")
        shutil.copy2(wheel, path)
        replaced += 1
    if replaced == 0:
        raise BuildError("BUILD_CHECK_FAILED", "nessun binario di Qt trovato nell'app")
    return replaced


def finish_bundle(info: dict, icon: bool) -> None:
    """Qt dalla ruota (D60-3), ``LSMinimumSystemVersion`` e ``BUILD_INFO.json`` definitivi, firma ad hoc (§3.1, A6)."""
    contents = APP / "Contents"
    info["qt_binaries_from_wheel"] = restore_qt_from_wheel(APP, wheel_site_packages())
    info["macos_minimum"] = minimum_macos(contents)
    plist_path = contents / "Info.plist"
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    plist.update(info_plist(info["version"], info["build"], info["macos_minimum"], icon))
    with plist_path.open("wb") as handle:
        plistlib.dump(plist, handle)
    (contents / "Resources" / BUILD_INFO_NAME).write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n",
                                                           encoding="utf-8")
    run(["codesign", "--force", "--deep", "--sign", "-", APP])


# --------------------------------------------------------------------------
# Controlli V1–V9 (§3.8)
# --------------------------------------------------------------------------


def check_signature(app: Path) -> Check:
    verify = run(["codesign", "--verify", "--deep", "--strict", app], check=False)
    details = run(["codesign", "-dv", app], check=False).stderr
    ok = verify.returncode == 0 and "Signature=adhoc" in details
    return Check("V1_signature", "ok" if ok else "failed", (verify.stderr or "").strip() or "adhoc")


def check_references(app: Path, forbidden: Iterable[str] = ()) -> Check:
    forbidden = tuple(forbidden) or (str(ROOT), "/opt/homebrew", "/usr/local", ".venv", "build/env")
    bad = {}
    for path in macho_files(app):
        wrong = [r for r in macho_references(path)
                 if not r.startswith(ALLOWED_PREFIXES) or any(f in r for f in forbidden)]
        if wrong:
            bad[str(path.relative_to(app))] = wrong
    return Check("V2_references", "ok" if not bad else "failed", bad or "solo @rpath, @loader_path, /System, /usr/lib")


def check_layout(app: Path, info: Mapping, icon: bool) -> Check:
    contents = app / "Contents"
    required = [contents / "Info.plist", contents / "MacOS" / APP_NAME, contents / "Resources" / BUILD_INFO_NAME,
                *(contents / "Resources" / "licenses" / n for n in LICENSE_NAMES)]
    if icon:
        required.append(contents / "Resources" / f"{APP_NAME}.icns")
    missing = [str(p.relative_to(app)) for p in required if not p.exists()]
    qt_core = list(contents.glob("Frameworks/PySide6/Qt/lib/QtCore.framework"))
    if not qt_core:
        missing.append("Contents/Frameworks/PySide6/Qt/lib/QtCore.framework")
    with (contents / "Info.plist").open("rb") as handle:
        plist = plistlib.load(handle)
    expected = info_plist(info["version"], info["build"], minimum_macos(contents), icon)
    wrong = {k: plist.get(k) for k, v in expected.items() if plist.get(k) != v}
    via_frameworks = (contents / "Frameworks" / "licenses" / "LICENSE").is_file()  # V-e: dati raggiungibili da _MEIPASS
    ok = not missing and not wrong and via_frameworks
    return Check("V3_layout", "ok" if ok else "failed",
                 {"missing": missing, "plist_wrong": wrong, "licenses_via_frameworks": via_frameworks,
                  "macos_minimum": expected["LSMinimumSystemVersion"]})


def clean_environment(home: Path) -> dict:
    """Ambiente vuoto per V4 e V7: niente uv né .venv nel ``PATH`` e una HOME temporanea, così l'app non trova il
    Portachiavi di login (nessun accesso alle chiavi vere, nessuna richiesta di macOS) né impostazioni e cache
    dell'utente: si avvia come per un utente nuovo."""
    return {"HOME": str(home), "PATH": "/usr/bin:/bin", "TMPDIR": os.environ.get("TMPDIR", "/tmp")}


def check_self(app: Path) -> Check:
    executable = app / "Contents" / "MacOS" / APP_NAME
    with tempfile.TemporaryDirectory() as home:
        result = run([executable, "--self-check"], cwd=Path("/"), env=clean_environment(Path(home)), check=False,
                     timeout=300)
    try:
        payload = json.loads(result.stdout[result.stdout.index("{"):])
    except ValueError:
        return Check("V4_self_check", "failed", {"exit": result.returncode, "stdout": result.stdout[-2000:],
                                                 "stderr": result.stderr[-2000:]})
    bad = [c for c in payload["checks"] if c["status"] != "ok"]
    ok = result.returncode == 0 and payload.get("bundled") and not bad
    return Check("V4_self_check", "ok" if ok else "failed", bad or f"{len(payload['checks'])} voci ok")


_LC_SEGMENT_64 = 0x19
_MH_MAGIC_64 = 0xFEEDFACF


def _clear_linkedit_vmsize(data: bytearray) -> None:
    """Azzera ``vmsize`` di ``__LINKEDIT`` in ogni parte (arm64, x86_64) di un Mach-O a 64 bit, in posto.

    Dopo ``codesign --remove-signature`` è l'unico campo che la firma lascia cambiato: la firma ad hoc dell'app
    (obbligatoria) è più grande di quella del linker della ruota e ingrandisce ``__LINKEDIT`` (V5, §3.7 punto 4).
    """
    if data[:4] == b"\xca\xfe\xba\xbe":
        count = int.from_bytes(data[4:8], "big")
        offsets = [int.from_bytes(data[8 + 20 * i + 8:8 + 20 * i + 12], "big") for i in range(count)]
    else:
        offsets = [0]
    for base in offsets:
        if int.from_bytes(data[base:base + 4], "little") != _MH_MAGIC_64:
            raise BuildError("BUILD_CHECK_FAILED", "Mach-O non a 64 bit: V5 non sa confrontarlo")
        ncmds = int.from_bytes(data[base + 16:base + 20], "little")
        position = base + 32
        for _ in range(ncmds):
            cmd = int.from_bytes(data[position:position + 4], "little")
            size = int.from_bytes(data[position + 4:position + 8], "little")
            if cmd == _LC_SEGMENT_64 and data[position + 8:position + 24].rstrip(b"\0") == b"__LINKEDIT":
                data[position + 32:position + 40] = bytes(8)
            position += size


def _unsigned_digest(path: Path, scratch: Path) -> str:
    """SHA-256 del file tolta la firma (``codesign --remove-signature``) e con ``vmsize`` di ``__LINKEDIT`` azzerato."""
    copy = scratch / hashlib.sha1(str(path).encode()).hexdigest()
    shutil.copyfile(path, copy)
    result = run(["codesign", "--remove-signature", copy], check=False)
    if result.returncode != 0 and "not signed" not in (result.stderr or ""):
        raise BuildError("BUILD_CHECK_FAILED", f"codesign --remove-signature {path}: {result.stderr.strip()}")
    data = bytearray(copy.read_bytes())
    copy.unlink()
    _clear_linkedit_vmsize(data)
    return hashlib.sha256(data).hexdigest()


def check_qt_unmodified(app: Path, site_packages: Path | None = None) -> Check:
    """V5: ogni binario di Qt dell'app uguale a quello della ruota, tolta la firma da entrambe le copie."""
    site_packages = site_packages or wheel_site_packages()
    if site_packages is None or not (site_packages / "PySide6" / "Qt").is_dir():
        return Check("V5_qt_unmodified", "not_run", "build/env assente: nessuna ruota con cui confrontare")
    bundled_qt = app / "Contents" / "Frameworks" / "PySide6" / "Qt"
    different, missing, compared = [], [], 0
    with tempfile.TemporaryDirectory() as scratch:
        for path in macho_files(bundled_qt):
            relative = path.relative_to(bundled_qt)
            wheel = site_packages / "PySide6" / "Qt" / relative
            if not wheel.is_file():
                missing.append(str(relative))
                continue
            compared += 1
            if _unsigned_digest(path, Path(scratch)) != _unsigned_digest(wheel, Path(scratch)):
                different.append(str(relative))
    ok = compared > 0 and not different and not missing
    return Check("V5_qt_unmodified", "ok" if ok else "failed",
                 {"compared": compared, "different": different, "missing_in_wheel": missing})


def snapshot(app: Path) -> dict[str, tuple]:
    state = {}
    for path in sorted(app.rglob("*")):
        relative = str(path.relative_to(app))
        if path.is_symlink():
            state[relative] = ("link", os.readlink(path))
        elif path.is_file():
            stat = path.stat()
            state[relative] = (stat.st_size, stat.st_mtime_ns, sha256(path))
    return state


def check_no_writes(before: Mapping, after: Mapping) -> Check:
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    ok = not (added or removed or changed)
    return Check("V6_no_writes", "ok" if ok else "failed", {"added": added[:50], "removed": removed[:50],
                                                           "changed": changed[:50]})


def gui_session() -> bool:
    result = run(["launchctl", "managername"], check=False)
    return result.stdout.strip() == "Aqua"


def launch_once(app: Path, timeout: float = 180.0) -> tuple[float | None, int | None]:
    """(secondi dal lancio dell'eseguibile alla riga ``first_view``, codice di uscita); ``None`` se non arrivano."""
    with tempfile.TemporaryDirectory() as home:
        process = subprocess.Popen([str(app / "Contents" / "MacOS" / APP_NAME), "--quit-after-first-view"],
                                   cwd="/", env=clean_environment(Path(home)), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        start, first = time.monotonic(), None
        for line in process.stdout:
            if FIRST_VIEW_LINE in line:
                first = time.monotonic() - start
                break
            if time.monotonic() - start > timeout:
                break
        try:
            code = process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            code = None
    return first, code


def launch_with_open(app: Path, timeout: float = 180.0) -> bool:
    """Avvio come dal Finder (``open``, Launch Services): vero se la prima vista c'è e l'app esce da sola."""
    with tempfile.TemporaryDirectory() as scratch:
        out = Path(scratch) / "stdout.txt"
        home = Path(scratch) / "home"
        home.mkdir()
        try:
            result = subprocess.run(["open", "-n", "-W", "--env", f"HOME={home}", "--stdout", str(out), "--stderr",
                                     str(out), str(app), "--args", "--quit-after-first-view"], timeout=timeout)
        except subprocess.TimeoutExpired:
            return False
        return result.returncode == 0 and out.is_file() and FIRST_VIEW_LINE in out.read_text(errors="replace")


def check_launch(app: Path, report: Report) -> Check:
    if not gui_session():
        return Check("V7_launch", "not_run", "nessuna sessione grafica (launchctl managername ≠ Aqua)")
    cold, cold_exit = launch_once(app)
    warm, warm_exit = launch_once(app)
    finder = launch_with_open(app)
    report.startup = {"cold_s": None if cold is None else round(cold, 2),
                      "warm_s": None if warm is None else round(warm, 2),
                      "measure": "dall'avvio dell'eseguibile alla prima vista del cielo (first_shown del 41), "
                                 "ambiente vuoto con HOME temporanea (cache vuota, nessun Portachiavi)",
                      "objective_P5_s": 3.0, "exit_codes": [cold_exit, warm_exit], "open_launch_ok": finder}
    ok = cold is not None and warm is not None and cold_exit == 0 and warm_exit == 0 and finder
    return Check("V7_launch", "ok" if ok else "failed", report.startup)


def check_license_copies(app: Path, info: Mapping) -> Check:
    folder = app / "Contents" / "Resources" / "licenses"
    different = [n for n in LICENSE_NAMES[:3]
                 if not (folder / n).is_file() or (folder / n).read_bytes() != (ROOT / n).read_bytes()]
    sources = folder / "SOURCES.txt"
    if not sources.is_file() or sources.read_text(encoding="utf-8") != sources_text(info):
        different.append("SOURCES.txt")
    text = (folder / "THIRD_PARTY_LICENSES").read_text(encoding="utf-8") if (folder / "THIRD_PARTY_LICENSES").is_file() else ""
    sections = [s.strip() for s in LICENSE_SECTIONS if s not in text]
    ok = not different and not sections
    return Check("V8_licenses", "ok" if ok else "failed", {"different": different, "missing_sections": sections})


def measure_size(app: Path, report: Report) -> Check:
    total_kb = int(run(["du", "-sk", app]).stdout.split()[0])
    parts = {}
    for folder in [p for p in (app / "Contents" / "Frameworks").iterdir() if p.is_dir() and not p.is_symlink()]:
        parts[folder.name] = int(run(["du", "-sk", folder]).stdout.split()[0])
    qt_lib = app / "Contents" / "Frameworks" / "PySide6" / "Qt"
    if qt_lib.is_dir():
        parts["PySide6/Qt"] = int(run(["du", "-sk", qt_lib]).stdout.split()[0])
    largest = dict(sorted(parts.items(), key=lambda kv: -kv[1])[:10])
    report.size = {"bytes": total_kb * 1024, "MB": round(total_kb / 1024, 1),
                   "largest_MB": {k: round(v / 1024, 1) for k, v in largest.items()}}
    return Check("V9_size", "ok", report.size)


def check_bundle(app: Path, info: Mapping, icon: bool, report: Report) -> list[Check]:
    checks = [check_signature(app), check_references(app), check_layout(app, info, icon)]
    before = snapshot(app)
    checks.append(check_self(app))
    checks.append(check_qt_unmodified(app))
    launch = check_launch(app, report)
    checks.append(check_no_writes(before, snapshot(app)))
    checks += [launch, check_license_copies(app, info), measure_size(app, report)]
    return checks


# --------------------------------------------------------------------------
# Rapporto e avvio
# --------------------------------------------------------------------------


def write_report(report: Report, outcome: str) -> None:
    DIST.mkdir(exist_ok=True)
    payload = {"outcome": outcome, **{k: v for k, v in asdict(report).items()}}
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print("\n=== Rapporto della costruzione ===")
    for warning in report.warnings:
        print(f"AVVISO {warning}")
    for check in report.checks:
        print(f"{check.name:22} {check.status}")
    if report.size:
        print(f"Dimensione dell'app: {report.size['MB']} MB ({report.size['bytes']} byte)")
    if report.startup:
        print(f"Avvio fino alla prima vista: a freddo {report.startup['cold_s']} s, a caldo {report.startup['warm_s']} s")
    for step, seconds in report.steps.items():
        print(f"  {step:20} {seconds:8.1f} s")
    print(f"Esito: {outcome}; rapporto in {REPORT.relative_to(ROOT)}")


def _step(report: Report, name: str, function, *args):
    print(f"--- {name}", flush=True)
    start = time.monotonic()
    result = function(*args)
    report.steps[name] = round(time.monotonic() - start, 1)
    return result


def build(args: argparse.Namespace) -> int:
    report = Report()
    info = _step(report, "controlli", preliminary_checks, args.allow_dirty, report)
    python = _step(report, "python", install_python)
    _step(report, "ambiente", create_env, python, args.keep_build, report)
    if args.skip_tests:
        report.warnings.insert(0, "--skip-tests: TEST NON ESEGUITI in build/env")
    else:
        _step(report, "test", run_tests)
    _step(report, "licenze", check_licenses_file)
    info.update(_step(report, "qt", qt_versions))
    icon = _step(report, "icona", build_icon, report)
    pyinstaller = run([env_python(), "-c", "import PyInstaller; print(PyInstaller.__version__)"]).stdout.strip()
    info.update({
        "python": f"CPython {PYTHON_VERSION} (python-build-standalone {PBS_RELEASE})", "pyinstaller": pyinstaller,
        "uv_lock_sha256": sha256(ROOT / "uv.lock"), "tests_run": not args.skip_tests,
        "options": [o for o, on in (("--allow-dirty", args.allow_dirty), ("--skip-tests", args.skip_tests),
                                    ("--keep-build", args.keep_build)) if on],
        "built_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    })
    stage = stage_files(info)
    entry = BUILD / "launch.py"
    entry.write_text("import sys\n\nfrom astrotwo.app_bundle import main\n\nsys.exit(main())\n", encoding="utf-8")
    spec = BUILD / f"{APP_NAME}.spec"
    spec.write_text(spec_text(entry=entry, stage=stage, icon=icon, version=info["version"], build=info["build"],
                              metadata=runtime_distributions()), encoding="utf-8")
    shutil.rmtree(FAILED_APP, ignore_errors=True)
    _step(report, "pyinstaller", run_pyinstaller, spec)
    _step(report, "firma", finish_bundle, info, icon is not None)
    report.info = info
    report.checks = _step(report, "controlli V1-V9", check_bundle, APP, info, icon is not None, report)
    blocking = [c for c in report.checks if c.status == "failed" and not c.name.startswith(("V7", "V9"))]
    if blocking:
        APP.rename(FAILED_APP)
        write_report(report, "failed: " + ", ".join(c.name for c in blocking) + f" (app in {FAILED_APP.name})")
        for check in blocking:
            print(f"BUILD_CHECK_FAILED {check.name}: {json.dumps(check.detail, ensure_ascii=False, default=str)[:3000]}")
        return 1
    write_report(report, "ok")
    return 0


def check_only(app: Path) -> int:
    report = Report()
    info = json.loads((app / "Contents" / "Resources" / BUILD_INFO_NAME).read_text(encoding="utf-8"))
    icon = (app / "Contents" / "Resources" / f"{APP_NAME}.icns").is_file()
    report.info = info
    report.checks = check_bundle(app, info, icon, report)
    failed = [c for c in report.checks if c.status == "failed" and not c.name.startswith(("V7", "V9"))]
    write_report(report, "ok" if not failed else "failed: " + ", ".join(c.name for c in failed))
    for check in failed:
        print(f"BUILD_CHECK_FAILED {check.name}: {json.dumps(check.detail, ensure_ascii=False, default=str)[:3000]}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--allow-dirty", action="store_true", help="costruisce anche con modifiche non salvate")
    parser.add_argument("--skip-tests", action="store_true", help="salta i test (solo prove dello script)")
    parser.add_argument("--keep-build", action="store_true", help="riusa build/env se uv.lock e Python sono gli stessi")
    parser.add_argument("--check-only", type=Path, metavar="APP", help="solo i controlli V1–V9 su un'app")
    parser.add_argument("--make-iconset", nargs=2, type=Path, metavar=("SVG", "CARTELLA"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.make_iconset:
            make_iconset(*args.make_iconset)
            return 0
        if args.check_only:
            return check_only(args.check_only)
        return build(args)
    except BuildError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
