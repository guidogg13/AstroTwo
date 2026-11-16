# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Validazione dei VOTable scritti da AstroTwo rispetto allo schema (D62-8, decisione del proprietario del 2026-11-13).

Tre controlli, tutti senza rete:

1. **ID univoci nel documento** (letti dal file con un parser XML: il difetto del build 8, ``INFO ID="A2NOTE"``
   ripetuto, è proprio questo);
2. **Astropy con ``verify="exception"``**: nessun avviso del lettore di VOTable. L'unica eccezione ammessa è
   ``W50`` (unità non valida) sulle unità **della fonte** che il test dichiara: D05-7 le scrive così come sono, e
   l'esportazione le dichiara (``EXPORT_UNIT_NOT_STANDARD``); qualunque altro avviso fa fallire il controllo;
3. **``votlint`` di STILTS** (dentro ``topcat-full.jar`` o ``stilts.jar``), se Java e il file ``.jar`` ci sono:
   **zero righe ``ERROR``**; gli avvisi (es. ``Bad VOUnit`` su ``'electron'``, lo stesso dell'archivio Gaia)
   restano avvisi. Senza ``.jar`` il controllo si salta e lo dice (``votlint_available``).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import warnings
from collections import Counter
from pathlib import Path

from astropy.io.votable import parse
from astropy.io.votable.exceptions import VOWarning
from defusedxml.ElementTree import parse as safe_parse_xml

#: Dove cercare STILTS (``ASTROTWO_STILTS_JAR`` prima): ``votlint`` lavora senza rete (schema dentro il ``.jar``).
#: La cartella home è quella vera dell'utente (``pwd``): i test girano con una ``HOME`` temporanea (``conftest``).
def _real_home() -> Path:
    """Home vera dell'utente: ``pwd`` su macOS e Linux; su Windows (niente ``pwd``) ``USERPROFILE`` (65, sprint W1)."""
    try:
        import pwd
    except ImportError:
        return Path(os.environ.get("USERPROFILE") or Path.home())
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


_HOME = _real_home()
STILTS_JARS = (os.environ.get("ASTROTWO_STILTS_JAR", ""),
               str(_HOME / "Applications/topcat/topcat-full.jar"), str(_HOME / "Applications/topcat/stilts.jar"),
               "/Applications/TOPCAT.app/Contents/Resources/Java/topcat-full.jar")


def stilts_jar() -> Path | None:
    if shutil.which("java") is None:
        return None
    for candidate in STILTS_JARS:
        if candidate and Path(candidate).expanduser().is_file():
            return Path(candidate).expanduser()
    return None


def votlint_available() -> bool:
    return stilts_jar() is not None


def duplicate_ids(path: Path) -> list[str]:
    root = safe_parse_xml(str(path)).getroot()
    counts = Counter(el.get("ID") for el in root.iter() if el.get("ID") is not None)
    return sorted(k for k, n in counts.items() if n > 1)


def astropy_problems(path: Path, source_units: tuple[str, ...] = ()) -> list[str]:
    """Avvisi del lettore di Astropy non ammessi (vuoto = valido). Senza unità della fonte: ``verify="exception"``."""
    if not source_units:
        try:
            parse(str(path), verify="exception")
        except Exception as exc:  # noqa: BLE001 - qualunque avviso o errore è un problema
            return [f"{type(exc).__name__}: {exc}"]
        return []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        parse(str(path), verify="warn")
    problems = []
    for w in caught:
        if not issubclass(w.category, VOWarning):
            continue
        text = str(w.message)
        unit = re.search(r"W50: Invalid unit string '(.+)'", text)
        if unit and unit.group(1) in source_units:
            continue
        problems.append(text)
    return problems


def votlint_errors(path: Path) -> list[str] | None:
    """Righe ``ERROR`` di ``votlint`` (``None`` se STILTS non c'è)."""
    jar = stilts_jar()
    if jar is None:
        return None
    done = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", str(jar), "-stilts", "votlint",
                           "version=1.4", f"votable={path}"], capture_output=True, text=True, timeout=120)
    lines = (done.stdout + done.stderr).splitlines()
    return [line for line in lines if line.startswith("ERROR")]


def assert_valid_votable(path, source_units: tuple[str, ...] = ()) -> None:
    path = Path(path)
    assert duplicate_ids(path) == [], f"{path.name}: ID ripetuti"
    assert astropy_problems(path, source_units) == [], f"{path.name}: avvisi di Astropy"
    errors = votlint_errors(path)
    assert errors in (None, []), f"{path.name}: votlint {errors}"
