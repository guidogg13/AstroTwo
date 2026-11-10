# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Immagine disco ``.dmg`` di AstroTwo con ``hdiutil`` (60-distribuzione-dmg.md §3.10, sprint 60b).

Decisione del proprietario del 2026-11-10: lo strumento è **``hdiutil``** (già in macOS, nessuna dipendenza nuova),
con uno script come quello della firma: **senza ``--execute`` non esegue niente** e stampa i comandi (prova a secco).
Passi:

1. cartella di lavoro ``build/dmg-root/`` nuova: copia di ``dist/AstroTwo.app`` con ``ditto`` (conserva firme,
   attributi estesi e collegamenti) e collegamento simbolico ``Applications`` → ``/Applications`` (si trascina l'app
   sul collegamento per installarla);
2. ``hdiutil create`` con volume «AstroTwo <versione>», file system HFS+, formato compresso UDZO, in
   ``dist/AstroTwo-<versione>.dmg`` (versione SemVer di ``astrotwo.__version__``, DC4);
3. ``hdiutil verify`` dell'immagine;
4. impronta SHA-256 in ``dist/AstroTwo-<versione>.dmg.sha256`` (da pubblicare con il rilascio).

Con ``--signed`` (firma Developer ID, A6-b, ``60`` §3.12) lo script aggiunge i passi di ``scripts/sign_notarize.py``
nell'ordine giusto: firma dell'app **prima** della copia, poi firma e notarizzazione del ``.dmg`` **dopo** la
creazione e prima dell'impronta. Senza ``--signed`` l'app resta com'è (firma ad hoc di ``build_app.py``, A6).

Un ``.dmg`` già presente con lo stesso nome non si sovrascrive mai (``DMG_EXISTS``): si cancella a mano o si
aumenta la versione. Messaggi in italiano sul terminale: strumento di sviluppo, fuori dal catalogo dei messaggi.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP = DIST / "AstroTwo.app"
STAGING = BUILD / "dmg-root"
APP_NAME = "AstroTwo"
#: File system e formato dell'immagine (60 §3.10, D60-7 da confermare): HFS+ e UDZO (zlib), leggibili da ogni
#: macOS supportato; nessuna opzione di aspetto (sfondo, posizioni delle icone): Finder mostra app e collegamento.
FILESYSTEM = "HFS+"
FORMAT = "UDZO"


class DmgError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


@dataclass
class Step:
    """Un passo: ``command`` (programma esterno) oppure ``action`` (operazione in Python, descritta in ``command``)."""

    command: list[str]
    purpose: str
    action: str | None = None  # "clean_staging", "sha256": eseguite da questo script, non da una shell


@dataclass
class Plan:
    steps: list[Step] = field(default_factory=list)

    def add(self, command, purpose: str, action: str | None = None) -> None:
        self.steps.append(Step([str(c) for c in command], purpose, action))

    def extend(self, other_steps, prefix: str) -> None:
        for s in other_steps:
            self.steps.append(Step(list(s.command), f"{prefix}: {s.purpose}"))


def version() -> str:
    """Versione SemVer mostrata dall'app (``astrotwo.__version__``, letta dal sorgente senza importare il pacchetto)."""
    text = (ROOT / "src" / "astrotwo" / "__init__.py").read_text()
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if match is None:
        raise DmgError("DMG_VERSION_MISSING", "__version__ non trovato in src/astrotwo/__init__.py")
    return match.group(1)


def dmg_path(ver: str, dist: Path | None = None) -> Path:
    return (DIST if dist is None else dist) / f"{APP_NAME}-{ver}.dmg"


def volume_name(ver: str) -> str:
    return f"{APP_NAME} {ver}"


def create_steps(app: Path, dmg: Path, ver: str, staging: Path | None = None) -> list[Step]:
    """Cartella di lavoro, ``hdiutil create`` e ``hdiutil verify`` (nessun passo eseguito qui)."""
    staging = STAGING if staging is None else staging
    plan = Plan()
    plan.add(["rm", "-rf", staging], "cartella di lavoro nuova (solo build/dmg-root)", action="clean_staging")
    plan.add(["mkdir", "-p", staging], "cartella di lavoro")
    plan.add(["ditto", app, staging / app.name], "copia dell'app con firme e attributi")
    plan.add(["ln", "-s", "/Applications", staging / "Applications"], "collegamento ad Applicazioni")
    plan.add(["hdiutil", "create", "-volname", volume_name(ver), "-srcfolder", staging, "-fs", FILESYSTEM,
              "-format", FORMAT, dmg], "creazione del .dmg")
    plan.add(["hdiutil", "verify", dmg], "verifica dell'immagine")
    return plan.steps


def load_sign_notarize():
    """``scripts/sign_notarize.py`` come modulo (stessa cartella), per i suoi piani di firma e notarizzazione."""
    path = Path(__file__).resolve().parent / "sign_notarize.py"
    spec = importlib.util.spec_from_file_location("sign_notarize", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("sign_notarize", module)
    spec.loader.exec_module(module)
    return module


def build_plan(app: Path, dmg: Path, ver: str, *, signed: bool, identity: str | None = None,
               profile: str | None = None, staging: Path | None = None) -> Plan:
    plan = Plan()
    sn = load_sign_notarize() if signed else None
    if sn is not None:
        identity = identity or sn.IDENTITY_PREFIX + "<nome> (<TEAMID>)"
        plan.extend(sn.app_plan(app, identity, BUILD / "entitlements.plist").steps, "firma dell'app")
    plan.steps.extend(create_steps(app, dmg, ver, staging))
    if sn is not None:
        plan.extend(sn.dmg_plan(dmg, identity).steps, "firma del .dmg")
        plan.extend(sn.notarize_plan(dmg, profile or sn.KEYCHAIN_PROFILE).steps, "notarizzazione")
    plan.add(["shasum", "-a", "256", dmg], f"impronta in {dmg.name}.sha256", action="sha256")
    return plan


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run_plan(plan: Plan, *, execute: bool, staging: Path | None = None) -> int:
    staging = STAGING if staging is None else staging
    for step in plan.steps:
        print(("$ " if execute else "[prova a secco] ") + shlex.join(step.command))
        if not execute:
            continue
        if step.action == "clean_staging":
            if BUILD.resolve() not in staging.resolve().parents:
                raise DmgError("DMG_STAGING_UNSAFE", f"{staging}: la cartella di lavoro deve stare in build/")
            if staging.exists():
                shutil.rmtree(staging)
            continue
        if step.action == "sha256":
            dmg = Path(step.command[-1])
            Path(f"{dmg}.sha256").write_text(f"{sha256_file(dmg)}  {dmg.name}\n")
            continue
        result = subprocess.run(step.command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"  fallito ({step.purpose}): {(result.stdout + result.stderr).strip()[-4000:]}", file=sys.stderr)
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--execute", action="store_true",
                        help="esegue davvero i comandi (senza: prova a secco, nessun comando eseguito)")
    parser.add_argument("--app", type=Path, default=APP, help="app costruita da scripts/build_app.py")
    parser.add_argument("--signed", action="store_true",
                        help="con la firma Developer ID e la notarizzazione di scripts/sign_notarize.py (A6-b)")
    parser.add_argument("--identity", help="certificato «Developer ID Application: …» (solo con --signed)")
    parser.add_argument("--profile", help="profilo di notarytool nel Portachiavi (solo con --signed)")
    try:
        load_sign_notarize().check_no_credentials(argv)  # credenziali solo nel Portachiavi (regola d'oro 5)
        args = parser.parse_args(argv)
        execute = bool(args.execute)
        ver = version()
        dmg = dmg_path(ver)
        if not (args.app / "Contents" / "MacOS").is_dir():
            if execute:
                raise DmgError("DMG_APP_MISSING", f"{args.app}: non è un'app costruita (scripts/build_app.py)")
            print(f"Nota: {args.app} non c'è ancora (prova a secco: i comandi si stampano lo stesso).")
        if execute and dmg.exists():
            raise DmgError("DMG_EXISTS", f"{dmg}: esiste già; non si sovrascrive (cancellarlo a mano o cambiare "
                           "versione)")
        identity = None
        if args.signed and execute:
            sn = load_sign_notarize()
            identity = sn.identity_for(args, execute)
        plan = build_plan(args.app, dmg, ver, signed=args.signed, identity=identity or args.identity,
                          profile=args.profile)
    except DmgError as exc:
        print(exc, file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - SignError di sign_notarize (credenziali, certificato)
        if type(exc).__name__ == "SignError":
            print(exc, file=sys.stderr)
            return 2
        raise
    if not execute:
        print("Prova a secco: nessun comando eseguito (--execute per creare il .dmg).")
    if execute:
        DIST.mkdir(exist_ok=True)
        BUILD.mkdir(exist_ok=True)
    try:
        return run_plan(plan, execute=execute)
    except DmgError as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
