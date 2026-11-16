# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Pacchetti di AstroTwo per Windows e Linux x86_64 (``mdfiles/65-windows-linux.md`` §3.9, sprint W2).

Gira **solo sui runner** del workflow manuale ``.github/workflows/build-windows-linux.yml`` (Windows x86_64 e Linux
x86_64 con glibc 2.35 di ``ubuntu-22.04``): niente pacchetti dal Mac, niente firma, niente release. Uso, dall'ambiente
di ``uv sync --locked`` (gruppo ``build`` compreso)::

    uv run --frozen python scripts/build_windows_linux.py [--skip-tests] [--appimagetool PERCORSO]

Passi: controlli (sistema, versione e build di ``pyproject.toml``, commit), test di default (se non ``--skip-tests``),
``THIRD_PARTY_LICENSES`` del pacchetto generato qui (D65-7), icona (``.ico`` su Windows, PNG su Linux) dall'SVG,
PyInstaller ``onedir`` (A2; stessa scelta dei moduli e delle esclusioni del ``.app``, plugin di Qt per sistema), poi
i pacchetti: Windows ``AstroTwo-<versione>-windows-x86_64.zip`` (D65-3); Linux ``…-linux-x86_64.tar.gz`` e
``…-linux-x86_64.AppImage`` (D65-4, runtime statico di ``appimagetool``), ognuno con il suo ``.sha256``. Controlli
**sui pacchetti** (estratti in una cartella nuova, come li riceve l'utente): W1 contenuto e licenze, W2
``opengl32sw.dll`` su Windows (D65-8), W3 autocontrollo ``--self-check``, W4 prova di fumo ``--smoke-profile`` con le
risposte registrate (come V10 del ``.dmg``: Qt ``offscreen``, senza rete). Rapporto in
``dist/build-report-<sistema>.json``. I messaggi sono in italiano: strumento di sviluppo, fuori dal catalogo.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import build_app  # noqa: E402 - stesse scelte di moduli, dati ed esclusioni del .app (60 §3.4, §3.5)

from astrotwo.app_bundle import BUILD_INFO_NAME, LICENSE_NAMES, QT_PLUGINS_NEEDED, sources_text  # noqa: E402

DIST = ROOT / "dist"
BUILD = ROOT / "build" / "windows-linux"
APP_NAME = "AstroTwo"
ICON_SVG = ROOT / "assets" / "icon" / "AstroNew.svg"
SMOKE_DATA = ROOT / "tests" / "analysis" / "data" / "profile"
#: Sistemi ammessi: ``platform.system()`` → (nome nei file, macchina attesa). Solo x86_64 (D65-5).
SYSTEMS = {"Windows": ("windows", ("AMD64", "x86_64")), "Linux": ("linux", ("x86_64",))}

#: Plugin di Qt da tenere per sistema (P8 della 65): stesse famiglie del .app (qtbase e qtsvg), più i plugin della
#: piattaforma. ``offscreen`` serve alla prova di fumo W4 (come V10). Gli stili di Windows e Linux non servono:
#: senza plugin Qt usa Fusion o lo stile incluso in QtWidgets.
QT_PLUGINS_KEEP: dict[str, dict[str, frozenset[str]]] = {
    "Windows": {
        "platforms": frozenset({"qwindows.dll", "qoffscreen.dll"}),
        "styles": frozenset({"qmodernwindowsstyle.dll"}),
        "imageformats": frozenset({"qsvg.dll", "qjpeg.dll", "qgif.dll", "qico.dll"}),
        "iconengines": frozenset({"qsvgicon.dll"}),
    },
    "Linux": {
        "platforms": frozenset({"libqxcb.so", "libqoffscreen.so", "libqwayland.so", "libqwayland-egl.so",
                                "libqwayland-generic.so"}),
        "platformthemes": frozenset({"libqxdgdesktopportal.so", "libqgtk3.so"}),
        "xcbglintegrations": frozenset({"libqxcb-glx-integration.so", "libqxcb-egl-integration.so"}),
        "wayland-graphics-integration-client": frozenset({"libqt-plugin-wayland-egl.so"}),
        "wayland-shell-integration": frozenset({"libxdg-shell.so"}),
        "wayland-decoration-client": frozenset({"libbradient.so"}),
        "imageformats": frozenset({"libqsvg.so", "libqjpeg.so", "libqgif.so", "libqico.so"}),
        "iconengines": frozenset({"libqsvgicon.so"}),
    },
}

#: Moduli di ``keyring`` e delle loro librerie da includere per sistema (31, D65-1): PyInstaller non li vede, perché
#: il 31 li importa per nome.
HIDDEN_IMPORTS = {
    "Windows": ["keyring.backends.Windows", "win32ctypes.pywin32.win32cred", "win32ctypes.pywin32.pywintypes"],
    "Linux": ["keyring.backends.SecretService", "secretstorage", "jeepney", "jeepney.io.blocking"],
}

#: Contenuto del file ``.desktop`` dell'AppImage (Freedesktop Desktop Entry 1.5).
DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Name=AstroTwo
Comment=Sky atlas and analysis for astrophysicists
Exec=AstroTwo %F
Icon=astrotwo
Categories=Science;Astronomy;Education;
Terminal=false
"""

#: Script ``AppRun`` dell'AppImage: avvia l'eseguibile della cartella onedir con gli argomenti dati.
APP_RUN = """#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/astrotwo/AstroTwo" "$@"
"""


class BuildError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass
class Check:
    name: str
    status: str  # ok, failed
    detail: object = None


@dataclass
class Report:
    status: str = "running"
    info: dict = field(default_factory=dict)
    steps: list[dict] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    packages: list[dict] = field(default_factory=list)


def run(command: list, *, cwd: Path = ROOT, env: Mapping[str, str] | None = None, timeout: float | None = None,
        check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run([str(c) for c in command], cwd=cwd, env=None if env is None else dict(env),
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                            stdin=subprocess.DEVNULL)
    if check and result.returncode != 0:
        raise BuildError(f"comando fallito ({result.returncode}): {' '.join(map(str, command))}\n"
                         f"{result.stdout[-3000:]}\n{result.stderr[-3000:]}")
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_sha256(path: Path) -> Path:
    """File ``<pacchetto>.sha256`` nel formato di ``sha256sum`` (impronta, due spazi, nome), con ``\\n``."""
    target = path.with_name(path.name + ".sha256")
    target.write_bytes(f"{sha256(path)}  {path.name}\n".encode("ascii"))
    return target


def current_system() -> tuple[str, str]:
    """(``Windows`` o ``Linux``, nome nei file); ``BuildError`` su ogni altro sistema o architettura (D65-5)."""
    system, machine = platform.system(), platform.machine()
    if system not in SYSTEMS or machine not in SYSTEMS[system][1]:
        raise BuildError(f"sistema {system} {machine}: i pacchetti si costruiscono solo su Windows o Linux x86_64 "
                         "(runner del workflow build-windows-linux.yml); per macOS c'è scripts/build_app.py")
    return system, SYSTEMS[system][0]


def keep_entry(dest: str, system: str) -> bool:
    """Come ``build_app.keep_entry`` ma con i plugin di Qt del sistema; traduzioni e QML come nel .app."""
    dest = dest.replace("\\", "/")
    if dest.startswith("PySide6/Qt/qml") or "/qml/" in dest:
        return False
    for prefix in ("PySide6/Qt/translations/", "PySide6/translations/"):
        if dest.startswith(prefix):
            return dest.rsplit("/", 1)[1] in build_app.QT_TRANSLATIONS_KEEP
    for prefix in ("PySide6/Qt/plugins/", "PySide6/plugins/"):
        if dest.startswith(prefix):
            folder, _, name = dest.removeprefix(prefix).partition("/")
            keep = QT_PLUGINS_KEEP[system]
            return folder in keep and name.split("/")[0] in keep[folder]
    return True


def package_name(version: str, tag: str, suffix: str) -> str:
    return f"{APP_NAME}-{version}-{tag}-x86_64{suffix}"


def build_info(system: str, skip_tests: bool) -> dict:
    import astrotwo

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    dirty = bool(run(["git", "status", "--porcelain", "--untracked-files=no"]).stdout.strip())
    import PyInstaller
    import PySide6

    return {"version": astrotwo.__version__, "build": int(project["tool"]["astrotwo"]["bundle"]["build"]),
            "commit": commit, "dirty": dirty, "system": system, "machine": platform.machine(),
            "python": f"CPython {platform.python_version()} ({sys.executable})", "pyside6": PySide6.__version__,
            "pyinstaller": PyInstaller.__version__, "uv_lock_sha256": sha256(ROOT / "uv.lock"),
            "tests_run": not skip_tests,
            "built_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")}


def stage_files(info: dict, system: str) -> Path:
    """``licenses/`` (LICENSE, NOTICE, THIRD_PARTY_LICENSES del pacchetto, SOURCES.txt) e ``BUILD_INFO.json``."""
    stage = BUILD / "stage"
    shutil.rmtree(stage, ignore_errors=True)
    (stage / "licenses").mkdir(parents=True)
    for name in LICENSE_NAMES[:2]:
        shutil.copy2(ROOT / name, stage / "licenses" / name)
    run([sys.executable, ROOT / "scripts" / "third_party_licenses.py", "--package",
         stage / "licenses" / "THIRD_PARTY_LICENSES"])
    (stage / "licenses" / "SOURCES.txt").write_bytes(sources_text(info).encode("utf-8"))
    (stage / BUILD_INFO_NAME).write_bytes((json.dumps(info, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return stage


def make_icon(system: str) -> Path | None:
    """``.ico`` (Windows: 16–256 pixel) o PNG 256 (Linux) disegnati dall'SVG con ``QSvgRenderer``."""
    if not ICON_SVG.is_file():
        return None
    folder = BUILD / "icon"
    shutil.rmtree(folder, ignore_errors=True)
    build_app.make_iconset(ICON_SVG, folder)
    big = folder / "icon_256x256.png"
    if system == "Linux":
        return big
    from PIL import Image

    target = folder / "AstroTwo.ico"
    Image.open(big).save(target, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    return target


def opengl32sw_binaries(system: str) -> list[tuple[str, str]]:
    """Su Windows ``opengl32sw.dll`` della ruota di PySide6 (Mesa llvmpipe, D65-8) accanto alle DLL di Qt."""
    if system != "Windows":
        return []
    import PySide6

    path = Path(PySide6.__file__).resolve().parent / "opengl32sw.dll"
    return [(str(path), "PySide6")] if path.is_file() else []


def spec_text(*, entry: Path, stage: Path, icon: Path | None, system: str) -> str:
    """Specifica di PyInstaller ``onedir`` (A2), con i dati e le esclusioni del .app (60 §3.4, §3.5)."""
    datas = build_app.astrotwo_datas(ROOT) + [(str(stage / "licenses"), "licenses"),
                                              (str(stage / BUILD_INFO_NAME), ".")]
    metadata = sorted(build_app_distributions())
    return f'''# Generato da scripts/build_windows_linux.py (65 §3.9): non modificarlo a mano.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

datas = {datas!r}
for package in {list(build_app.DATA_PACKAGES)!r}:
    datas += collect_data_files(package, excludes=["**/tests/**", "**/tests", "**/*.pyx", "**/*.c", "**/*.h"])
for name in {metadata!r}:
    datas += copy_metadata(name)

import importlib.util, sys
_spec = importlib.util.spec_from_file_location("build_windows_linux", {str(Path(__file__).resolve())!r})
bwl = importlib.util.module_from_spec(_spec)
sys.modules["build_windows_linux"] = bwl
_spec.loader.exec_module(bwl)

a = Analysis(
    [{str(entry)!r}],
    pathex=[{str(ROOT / "src")!r}],
    binaries={opengl32sw_binaries(system)!r},
    datas=datas,
    hiddenimports=collect_submodules("astrotwo") + {HIDDEN_IMPORTS[system]!r},
    excludes={sorted(build_app.EXCLUDES)!r},
    noarchive=False,
)
a.binaries = [e for e in a.binaries if bwl.keep_entry(e[0], {system!r})]
a.datas = [e for e in a.datas if bwl.keep_entry(e[0], {system!r})]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name={APP_NAME!r}, console=False,
          icon={None if icon is None or system != "Windows" else str(icon)!r}, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name={APP_NAME!r})
'''


def build_app_distributions() -> list[str]:
    """Pacchetti di esecuzione di questo sistema (stessa chiusura del file delle licenze)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("third_party_licenses", ROOT / "scripts" / "third_party_licenses.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["third_party_licenses"] = module
    spec.loader.exec_module(module)
    return [d.metadata["Name"] for d in module.runtime_closure()]


def run_pyinstaller(spec: Path) -> Path:
    folder = DIST / APP_NAME
    shutil.rmtree(folder, ignore_errors=True)
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
         "--distpath", DIST, "--workpath", BUILD / "pyinstaller", spec], timeout=3600)
    executable = folder / (f"{APP_NAME}.exe" if os.name == "nt" else APP_NAME)
    if not executable.is_file():
        raise BuildError(f"PyInstaller non ha prodotto {executable}")
    return folder


# --------------------------------------------------------------------------
# Pacchetti
# --------------------------------------------------------------------------


def make_zip(folder: Path, target: Path) -> Path:
    """Zip della cartella ``AstroTwo/`` (D65-3): si scompatta e si avvia ``AstroTwo\\AstroTwo.exe``."""
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(path, Path(APP_NAME) / path.relative_to(folder))
    return target


def make_tar(folder: Path, target: Path) -> Path:
    """``.tar.gz`` della cartella ``AstroTwo/`` (D65-4 (b)), permessi di esecuzione conservati."""
    target.unlink(missing_ok=True)
    with tarfile.open(target, "w:gz", compresslevel=9) as archive:
        archive.add(folder, arcname=APP_NAME)
    return target


def make_appdir(folder: Path, icon: Path | None) -> Path:
    """AppDir dell'AppImage: ``AppRun``, ``astrotwo.desktop``, icona e la cartella onedir in ``usr/lib/astrotwo``."""
    appdir = BUILD / "AstroTwo.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    shutil.copytree(folder, appdir / "usr" / "lib" / "astrotwo", symlinks=True)
    (appdir / "AppRun").write_bytes(APP_RUN.encode("ascii"))
    (appdir / "AppRun").chmod(0o755)
    (appdir / "astrotwo.desktop").write_bytes(DESKTOP_ENTRY.encode("utf-8"))
    if icon is not None:
        shutil.copy2(icon, appdir / "astrotwo.png")
        shutil.copy2(icon, appdir / ".DirIcon")
    return appdir


def make_appimage(appdir: Path, target: Path, appimagetool: Path, runtime: Path | None = None) -> Path:
    """AppImage con il runtime statico (type2-runtime: non serve ``libfuse2``, D65-4); ``runtime`` = file del runtime
    fissato dal workflow (altrimenti ``appimagetool`` lo scaricherebbe da solo, versione non fissata)."""
    target.unlink(missing_ok=True)
    env = {**os.environ, "ARCH": "x86_64", "APPIMAGE_EXTRACT_AND_RUN": "1"}
    options = ["--no-appstream"] + ([] if runtime is None else ["--runtime-file", runtime])
    run([appimagetool, *options, appdir, target], env=env, timeout=1800)
    target.chmod(0o755)
    return target


# --------------------------------------------------------------------------
# Controlli sui pacchetti (W1–W4)
# --------------------------------------------------------------------------


def clean_environment(home: Path) -> dict:
    """Ambiente minimo per l'app: home temporanea (nessuna impostazione, cache o chiave dell'utente), ``PATH`` del
    sistema senza uv né ``.venv``; su Windows le variabili che Windows richiede e le cartelle sotto la home finta."""
    if os.name == "nt":
        system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
        return {"SYSTEMROOT": system_root, "WINDIR": system_root, "PATH": rf"{system_root}\System32;{system_root}",
                "USERPROFILE": str(home), "HOME": str(home), "LOCALAPPDATA": str(home / "AppData" / "Local"),
                "APPDATA": str(home / "AppData" / "Roaming"), "TEMP": str(home), "TMP": str(home)}
    return {"HOME": str(home), "PATH": "/usr/bin:/bin", "TMPDIR": os.environ.get("TMPDIR", "/tmp")}


def _json_payload(result: subprocess.CompletedProcess, report_file: Path) -> dict | None:
    """Rapporto JSON dal file di ``--report-file`` (sempre scritto, anche senza console) o dallo standard output."""
    text = report_file.read_text(encoding="utf-8") if report_file.is_file() else result.stdout
    try:
        return json.loads(text[text.index("{"):])
    except ValueError:
        return None


def check_contents(folder: Path, system: str) -> Check:
    """W1 — eseguibile, ``BUILD_INFO.json``, licenze (con il file delle licenze del sistema), plugin di Qt."""
    internal = folder / "_internal"
    executable = folder / (f"{APP_NAME}.exe" if system == "Windows" else APP_NAME)
    missing = [str(p.relative_to(folder)) for p in [executable, internal / BUILD_INFO_NAME]
               + [internal / "licenses" / n for n in LICENSE_NAMES] if not p.is_file()]
    plugins = internal / "PySide6" / ("plugins" if system == "Windows" else "Qt/plugins")
    key = "win32" if system == "Windows" else "linux"
    missing += [f"plugin {name}" for name in QT_PLUGINS_NEEDED[key] if not (plugins / name).is_file()]
    licenses = (internal / "licenses" / "THIRD_PARTY_LICENSES").read_text(encoding="utf-8") \
        if (internal / "licenses" / "THIRD_PARTY_LICENSES").is_file() else ""
    expected = "pywin32-ctypes" if system == "Windows" else "SecretStorage"
    if expected not in licenses or "Contents/MacOS" in licenses.split("Strumenti di sviluppo", 1)[0]:
        missing.append(f"THIRD_PARTY_LICENSES del pacchetto ({expected})")
    return Check("W1_contents", "failed" if missing else "ok", missing or "contenuto e licenze presenti")


def check_opengl32sw(folder: Path, system: str) -> Check:
    """W2 — su Windows ``opengl32sw.dll`` accanto alle DLL di Qt (ripiego software di D65-8)."""
    if system != "Windows":
        return Check("W2_opengl32sw", "ok", "non applicabile: su Linux Mesa llvmpipe del sistema")
    found = sorted(str(p.relative_to(folder)) for p in folder.rglob("opengl32sw.dll"))
    return Check("W2_opengl32sw", "ok" if found else "failed",
                 found or "opengl32sw.dll assente: D65-8 su Windows non funziona (includere Mesa per Windows)")


def check_self(executable: Path, extra_env: Mapping[str, str] | None = None) -> Check:
    """W3 — ``--self-check`` (60 §7) con la home finta: moduli, dati, Qt, certificati, IERS, NAIF, keyring."""
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as out:
        report_file = Path(out) / "self-check.json"
        env = {**clean_environment(Path(home)), "QT_QPA_PLATFORM": "offscreen", **(extra_env or {})}
        result = run([executable, "--self-check", "--report-file", report_file], cwd=executable.parent, env=env,
                     timeout=600, check=False)
        payload = _json_payload(result, report_file)
    if payload is None:
        return Check("W3_self_check", "failed", {"exit": result.returncode, "stdout": result.stdout[-2000:],
                                                 "stderr": result.stderr[-2000:]})
    bad = [c for c in payload["checks"] if c["status"] != "ok"]
    ok = result.returncode == 0 and payload.get("bundled") and not bad
    return Check("W3_self_check", "ok" if ok else "failed", bad or f"{len(payload['checks'])} voci ok")


def check_smoke_profile(executable: Path, extra_env: Mapping[str, str] | None = None) -> Check:
    """W4 — prova di fumo della finestra Profili dentro il pacchetto (come V10 del .dmg, D62-2): profilo di 51 Peg
    con le risposte registrate, Qt ``offscreen``, senza rete (proxy verso una porta chiusa)."""
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as out:
        report_file = Path(out) / "smoke.json"
        closed = "http://127.0.0.1:9"
        env = {**clean_environment(Path(home)), "QT_QPA_PLATFORM": "offscreen", "HTTP_PROXY": closed,
               "HTTPS_PROXY": closed, "http_proxy": closed, "https_proxy": closed,
               "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost", **(extra_env or {})}
        result = run([executable, "--smoke-profile", SMOKE_DATA, "--report-file", report_file],
                     cwd=executable.parent, env=env, timeout=900, check=False)
        payload = _json_payload(result, report_file)
    if payload is None:
        return Check("W4_smoke_profile", "failed", {"exit": result.returncode, "stdout": result.stdout[-2000:],
                                                    "stderr": result.stderr[-3000:]})
    failed = [c for c in payload.get("checks", []) if not c.get("ok")]
    ok = result.returncode == 0 and payload.get("ok") and not failed
    return Check("W4_smoke_profile", "ok" if ok else "failed",
                 f"{len(payload['checks'])} voci ok" if ok else {"failed": failed, "errors": payload.get("errors")})


def extract(package: Path, into: Path) -> Path:
    """Scompatta ``.zip`` o ``.tar.gz`` come farebbe l'utente; restituisce la cartella ``AstroTwo``."""
    if package.suffix == ".zip":
        with zipfile.ZipFile(package) as archive:
            archive.extractall(into)
    else:
        with tarfile.open(package) as archive:
            archive.extractall(into, filter="tar")
    return into / APP_NAME


def check_package(package: Path, system: str) -> list[Check]:
    """W1–W4 sul pacchetto scompattato in una cartella nuova (non sulla cartella di PyInstaller)."""
    with tempfile.TemporaryDirectory(prefix="astrotwo-package-") as tmp:
        folder = extract(package, Path(tmp))
        executable = folder / (f"{APP_NAME}.exe" if system == "Windows" else APP_NAME)
        checks = [check_contents(folder, system), check_opengl32sw(folder, system), check_self(executable),
                  check_smoke_profile(executable)]
    for check in checks:
        check.name = f"{check.name} ({package.name})"
    return checks


def check_appimage(appimage: Path) -> list[Check]:
    """W3 e W4 lanciando l'AppImage stessa (``APPIMAGE_EXTRACT_AND_RUN``: niente FUSE sul runner)."""
    checks = []
    for function in (check_self, check_smoke_profile):
        check = function(appimage, {"APPIMAGE_EXTRACT_AND_RUN": "1"})
        check.name = f"{check.name} ({appimage.name})"
        checks.append(check)
    return checks


# --------------------------------------------------------------------------
# Costruzione
# --------------------------------------------------------------------------


def write_report(report: Report, tag: str) -> Path:
    path = DIST / f"build-report-{tag}.json"
    data = asdict(report)
    path.write_bytes((json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n").encode("utf-8"))
    return path


def build(args: argparse.Namespace) -> int:
    system, tag = current_system()
    report = Report()
    DIST.mkdir(exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    if not args.skip_tests:
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=ROOT,
                                stdin=subprocess.DEVNULL)
        if result.returncode != 0:
            raise BuildError("test di default falliti: nessun pacchetto")
    info = build_info(system, args.skip_tests)
    report.info = info
    stage = stage_files(info, system)
    icon = make_icon(system)
    entry = BUILD / "launch.py"
    entry.write_bytes(b"import sys\n\nfrom astrotwo.app_bundle import main\n\nsys.exit(main())\n")
    spec = BUILD / f"{APP_NAME}-{tag}.spec"
    spec.write_bytes(spec_text(entry=entry, stage=stage, icon=icon, system=system).encode("utf-8"))
    folder = run_pyinstaller(spec)
    report.steps.append({"pyinstaller": str(folder.relative_to(ROOT))})
    packages = []
    if system == "Windows":
        packages.append(make_zip(folder, DIST / package_name(info["version"], tag, ".zip")))
    else:
        packages.append(make_tar(folder, DIST / package_name(info["version"], tag, ".tar.gz")))
        if args.appimagetool is not None:
            appdir = make_appdir(folder, icon)
            packages.append(make_appimage(appdir, DIST / package_name(info["version"], tag, ".AppImage"),
                                          args.appimagetool, args.appimage_runtime))
    for package in packages:
        if package.suffix == ".AppImage":
            report.checks += check_appimage(package)
        else:
            report.checks += check_package(package, system)
        report.packages.append({"file": package.name, "bytes": package.stat().st_size, "sha256": sha256(package),
                                "sha256_file": write_sha256(package).name})
    failed = [c for c in report.checks if c.status != "ok"]
    report.status = "ok" if not failed else "failed: " + ", ".join(c.name for c in failed)
    write_report(report, tag)
    for check in report.checks:
        print(f"{check.status.upper():6} {check.name}: {json.dumps(check.detail, ensure_ascii=False, default=str)[:3000]}")
    for package in report.packages:
        print(f"PACCHETTO {package['file']} {package['bytes']} byte SHA-256 {package['sha256']}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-tests", action="store_true", help="salta i test (già eseguiti dal workflow)")
    parser.add_argument("--appimagetool", type=Path, metavar="PERCORSO",
                        help="appimagetool per l'AppImage (solo Linux; senza, solo il .tar.gz)")
    parser.add_argument("--appimage-runtime", type=Path, metavar="PERCORSO",
                        help="runtime statico dell'AppImage (type2-runtime) fissato dal workflow")
    args = parser.parse_args(argv)
    try:
        return build(args)
    except BuildError as exc:
        print(f"BUILD_FAILED {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
