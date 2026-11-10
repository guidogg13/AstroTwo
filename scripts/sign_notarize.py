# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Firma Developer ID e notarizzazione di AstroTwo (60-distribuzione-dmg.md §3.12, A6-b): preparati, non eseguiti.

Decisione del proprietario del 2026-11-10: specifica e script si preparano oggi, ma **non si eseguono** finché
l'account Apple Developer non è pronto. Per questo lo script, **senza ``--execute``, non esegue niente**: stampa i
comandi che eseguirebbe (prova a secco). Passi, uno per sottocomando:

1. ``app`` — firma ``dist/AstroTwo.app`` (costruita da ``scripts/build_app.py``, firmata ad hoc) con il certificato
   «Developer ID Application», runtime rinforzato (``--options runtime``), marca temporale di Apple
   (``--timestamp``) e i diritti di ``ENTITLEMENTS``; ogni codice annidato prima del contenitore (mai ``--deep`` per
   firmare); poi ``codesign --verify --deep --strict``.
2. ``dmg DMG`` — firma il ``.dmg`` (creato a mano dal proprietario, come oggi) con lo stesso certificato.
3. ``notarize DMG`` — invio al servizio di notarizzazione di Apple con ``xcrun notarytool submit --keychain-profile
   PROFILO --wait``, poi ``xcrun stapler staple`` e i controlli (``stapler validate``, ``spctl``). Esito rifiutato:
   il registro di Apple (``notarytool log``) in ``dist/notary-log.json``.

**Credenziali (regola d'oro 5, decisione del proprietario del 2026-11-10):** solo nel Portachiavi. Il proprietario
salva una volta, a mano, il profilo di ``notarytool`` (``xcrun notarytool store-credentials astrotwo-notary``: chiede
Apple ID, Team ID e password specifica per l'app e li mette nel Portachiavi); lo script conosce **solo il nome del
profilo**. Non accetta né legge Apple ID, password, chiavi API o Team ID da opzioni, variabili d'ambiente o file, e
non li scrive in log o rapporti. Il certificato sta nel Portachiavi di login; lo script ne usa il nome.

Rapporto in ``dist/sign-report.json`` (comandi ed esiti, nessuna credenziale). Messaggi in italiano sul terminale:
strumento di sviluppo, fuori dal catalogo dei messaggi dell'app.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import plistlib
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP = DIST / "AstroTwo.app"
REPORT = DIST / "sign-report.json"
NOTARY_LOG = DIST / "notary-log.json"

#: Nome del profilo di ``notarytool`` nel Portachiavi (60 §3.12): solo il nome, mai le credenziali.
KEYCHAIN_PROFILE = "astrotwo-notary"
#: Prefisso del certificato per le app distribuite fuori dal Mac App Store.
IDENTITY_PREFIX = "Developer ID Application: "
#: Diritti del runtime rinforzato (60 §3.12, D60-6 (2)): il minimo **da verificare** alla prima firma vera (prova
#: T19 del 60). ``allow-unsigned-executable-memory``: ctypes e cffi (usati da librerie incluse) scrivono codice in
#: memoria per le funzioni di richiamo. Nessun ``disable-library-validation``: tutte le librerie sono firmate con lo
#: stesso certificato. Si aggiunge un diritto solo se la prova lo dimostra necessario, scritto nel 60.
ENTITLEMENTS: dict[str, bool] = {"com.apple.security.cs.allow-unsigned-executable-memory": True}
#: Numeri magici dei file Mach-O (32/64 bit, entrambi gli ordini dei byte, file «fat»).
MACHO_MAGIC = {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
               b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}
#: Opzioni che lo script rifiuta sempre: le credenziali non passano mai da qui (regola d'oro 5).
FORBIDDEN_OPTIONS = ("--password", "--apple-id", "--team-id", "--key", "--key-id", "--issuer")


class SignError(Exception):
    """Errore dello script con un codice e il testo per il terminale."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


@dataclass
class Step:
    """Un comando del piano, con l'esito quando è eseguito."""

    command: list[str]
    purpose: str
    outcome: str = "not_run"  # not_run (prova a secco), ok, failed
    detail: str = ""


@dataclass
class Plan:
    action: str
    steps: list[Step] = field(default_factory=list)

    def add(self, command: Sequence[object], purpose: str) -> None:
        self.steps.append(Step([str(c) for c in command], purpose))


# =============================================================================
# Parti pure (provate nei test senza eseguire niente)


def developer_identities(find_identity_output: str) -> list[str]:
    """Nomi dei certificati «Developer ID Application» validi dall'uscita di ``security find-identity -v -p
    codesigning`` (righe ``  1) <SHA-1> "<nome>"``)."""
    names = re.findall(r'^\s*\d+\)\s+[0-9A-F]{40}\s+"([^"]+)"', find_identity_output, flags=re.MULTILINE)
    return sorted({n for n in names if n.startswith(IDENTITY_PREFIX)})


def choose_identity(identities: Sequence[str], wanted: str | None) -> str:
    """Il certificato da usare: quello indicato (deve esserci) o l'unico presente; mai una scelta silenziosa."""
    if wanted is not None:
        if not wanted.startswith(IDENTITY_PREFIX):
            raise SignError("SIGN_IDENTITY_INVALID", f"il certificato deve essere «{IDENTITY_PREFIX}…», non {wanted!r}")
        if wanted not in identities:
            raise SignError("SIGN_IDENTITY_MISSING", f"{wanted!r} non è nel Portachiavi")
        return wanted
    if len(identities) == 1:
        return identities[0]
    if not identities:
        raise SignError("SIGN_IDENTITY_MISSING", "nessun certificato «Developer ID Application» nel Portachiavi")
    raise SignError("SIGN_IDENTITY_AMBIGUOUS", f"{len(identities)} certificati «Developer ID Application»: "
                    "indicarne uno con --identity")


def is_macho(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) in MACHO_MAGIC
    except OSError:
        return False


def signing_order(app: Path) -> list[Path]:
    """Codice da firmare dall'interno verso l'esterno (60 §3.12): ogni file Mach-O fuori dai ``.framework``, poi i
    ``.framework`` (che firmano i loro binari), dal più profondo; l'eseguibile principale per ultimo, poi l'app."""
    contents = app / "Contents"
    main = contents / "MacOS" / app.stem
    frameworks = sorted((p for p in contents.rglob("*.framework") if p.is_dir() and not p.is_symlink()),
                        key=lambda p: (-len(p.parts), str(p)))
    inside_framework = tuple(frameworks)
    files = [p for p in contents.rglob("*") if p.is_file() and not p.is_symlink() and p != main and is_macho(p)
             and not any(f in p.parents for f in inside_framework)]
    files.sort(key=lambda p: (-len(p.parts), str(p)))
    return files + frameworks + ([main] if main.exists() else []) + [app]


def sign_command(target: Path, identity: str, entitlements: Path | None) -> list[str]:
    """``codesign`` di un elemento: runtime rinforzato, marca temporale di Apple, mai ``--deep``."""
    command = ["codesign", "--force", "--options", "runtime", "--timestamp", "--sign", identity]
    if entitlements is not None:
        command += ["--entitlements", str(entitlements)]
    return command + [str(target)]


def entitlements_bytes() -> bytes:
    return plistlib.dumps(ENTITLEMENTS, fmt=plistlib.FMT_XML, sort_keys=True)


def app_plan(app: Path, identity: str, entitlements: Path) -> Plan:
    plan = Plan("app")
    for target in signing_order(app):
        # i diritti valgono per gli eseguibili (principale e app); le librerie si firmano senza
        is_executable = target == app or target.parent.name == "MacOS"
        plan.add(sign_command(target, identity, entitlements if is_executable else None), f"firma {target.name}")
    plan.add(["codesign", "--verify", "--deep", "--strict", "--verbose=2", app], "verifica della firma")
    plan.add(["codesign", "-dv", "--verbose=4", app], "dettagli: Authority, TeamIdentifier, Runtime, Timestamp")
    return plan


def dmg_plan(dmg: Path, identity: str) -> Plan:
    plan = Plan("dmg")
    plan.add(["codesign", "--force", "--timestamp", "--sign", identity, dmg], "firma del .dmg")
    plan.add(["codesign", "--verify", "--strict", "--verbose=2", dmg], "verifica della firma del .dmg")
    return plan


def notarize_plan(dmg: Path, profile: str) -> Plan:
    """Invio, attesa, ticket e controlli; le credenziali sono nel profilo del Portachiavi (solo il nome qui)."""
    plan = Plan("notarize")
    plan.add(["xcrun", "notarytool", "submit", dmg, "--keychain-profile", profile, "--wait",
              "--output-format", "json"], "notarizzazione (attesa dell'esito di Apple)")
    plan.add(["xcrun", "stapler", "staple", dmg], "ticket di notarizzazione nel .dmg")
    plan.add(["xcrun", "stapler", "validate", dmg], "controllo del ticket")
    plan.add(["spctl", "--assess", "--type", "open", "--context", "context:primary-signature", "--verbose=2", dmg],
             "Gatekeeper sul .dmg")
    return plan


def check_no_credentials(argv: Sequence[str]) -> None:
    """Rifiuta ogni opzione di credenziali (regola d'oro 5): anche se scritte a mano non arrivano mai a un comando."""
    for arg in argv:
        if any(arg == f or arg.startswith(f + "=") for f in FORBIDDEN_OPTIONS):
            raise SignError("SIGN_CREDENTIALS_REFUSED", f"{arg.split('=')[0]}: le credenziali stanno solo nel "
                            f"Portachiavi (profilo di notarytool «{KEYCHAIN_PROFILE}»), mai nelle opzioni")


# =============================================================================
# Esecuzione (solo con --execute)


def run_plan(plan: Plan, *, execute: bool) -> int:
    for step in plan.steps:
        print(("$ " if execute else "[prova a secco] ") + " ".join(step.command))
        if not execute:
            continue
        result = subprocess.run(step.command, capture_output=True, text=True, check=False)
        step.detail = (result.stdout + result.stderr).strip()[-4000:]
        step.outcome = "ok" if result.returncode == 0 else "failed"
        if result.returncode != 0:
            print(f"  fallito ({step.purpose}): {step.detail}", file=sys.stderr)
            if step.command[:3] == ["xcrun", "notarytool", "submit"]:
                save_notary_log(step.detail, plan)
            return 1
    return 0


def save_notary_log(submit_output: str, plan: Plan) -> None:
    """Registro di Apple di un invio rifiutato in ``dist/notary-log.json`` (nessuna credenziale: solo l'esito)."""
    match = re.search(r'"id"\s*:\s*"([0-9a-f-]{36})"', submit_output)
    if match is None:
        return
    profile = plan.steps[0].command[plan.steps[0].command.index("--keychain-profile") + 1]
    result = subprocess.run(["xcrun", "notarytool", "log", match.group(1), "--keychain-profile", profile,
                             str(NOTARY_LOG)], capture_output=True, text=True, check=False)
    print(f"  registro di Apple: {NOTARY_LOG}" if result.returncode == 0 else
          f"  registro di Apple non scaricato: {result.stderr.strip()}", file=sys.stderr)


def write_report(plan: Plan, execute: bool) -> None:
    report = {"action": plan.action, "executed": execute,
              "date": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "steps": [{"command": s.command, "purpose": s.purpose, "outcome": s.outcome, "detail": s.detail}
                        for s in plan.steps]}
    DIST.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, ensure_ascii=False))


def identity_for(args, execute: bool) -> str:
    if not execute:  # prova a secco: il Portachiavi non si legge
        return args.identity or IDENTITY_PREFIX + "<nome> (<TEAMID>)"
    output = subprocess.run(["security", "find-identity", "-v", "-p", "codesigning"], capture_output=True,
                            text=True, check=False).stdout
    return choose_identity(developer_identities(output), args.identity)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--execute", action="store_true",
                        help="esegue davvero i comandi (senza: prova a secco, nessun comando eseguito)")
    parser.add_argument("--identity", help=f"nome del certificato «{IDENTITY_PREFIX}…» (se ce n'è più di uno)")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("app", help="firma dist/AstroTwo.app").add_argument("--app", type=Path, default=APP)
    sub.add_parser("dmg", help="firma un .dmg").add_argument("dmg", type=Path)
    notarize = sub.add_parser("notarize", help="notarizza un .dmg firmato e vi aggiunge il ticket")
    notarize.add_argument("dmg", type=Path)
    notarize.add_argument("--profile", default=KEYCHAIN_PROFILE, help="nome del profilo di notarytool nel Portachiavi")
    try:
        check_no_credentials(argv)
        args = parser.parse_args(argv)
        execute = bool(args.execute)
        if args.action == "app":
            if not (args.app / "Contents" / "MacOS").is_dir():
                raise SignError("SIGN_APP_MISSING", f"{args.app}: non è un'app costruita (scripts/build_app.py)")
            entitlements = BUILD / "entitlements.plist"
            if execute:
                BUILD.mkdir(exist_ok=True)
                entitlements.write_bytes(entitlements_bytes())
            plan = app_plan(args.app, identity_for(args, execute), entitlements)
        elif args.action == "dmg":
            if not args.dmg.is_file():
                raise SignError("SIGN_DMG_MISSING", f"{args.dmg}: file .dmg non trovato")
            plan = dmg_plan(args.dmg, identity_for(args, execute))
        else:
            if not args.dmg.is_file():
                raise SignError("SIGN_DMG_MISSING", f"{args.dmg}: file .dmg non trovato")
            plan = notarize_plan(args.dmg, args.profile)
    except SignError as exc:
        print(exc, file=sys.stderr)
        return 2
    if not execute:
        print("Prova a secco: nessun comando eseguito (decisione del proprietario del 2026-11-10; --execute quando "
              "l'account Apple Developer è pronto).")
    code = run_plan(plan, execute=execute)
    if execute:
        write_report(plan, execute)
    return code


if __name__ == "__main__":
    sys.exit(main())
