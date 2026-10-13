"""Genera e controlla ``THIRD_PARTY_LICENSES`` (decisione del proprietario del 2026-10-13).

Uso: ``uv run python scripts/third_party_licenses.py`` riscrive il file nella radice del progetto;
con ``--check`` controlla soltanto che sia aggiornato (uscita 1 se non lo è; lo stesso controllo è
in ``tests/test_third_party_licenses.py``).

Contenuto: tutte le dipendenze di esecuzione di AstroTwo su macOS (chiusura delle ``dependencies``
di ``pyproject.toml`` con i marcatori valutati sulla piattaforma corrente), con nome, versione,
licenza dichiarata e il testo integrale dei file di licenza e degli avvisi distribuiti nel pacchetto
installato; più i componenti che non sono pacchetti Python (``EXTRA_COMPONENTS``) e le note scritte
a mano (``NOTES``). Ogni nuova dipendenza entra qui rigenerando il file.
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "THIRD_PARTY_LICENSES"

#: Note scritte a mano per pacchetto (avvisi da riportare, licenze particolari, testi mancanti).
NOTES: dict[str, str] = {
    "spherical-geometry": (
        "Include la libreria QD (Lawrence Berkeley National Laboratory, licenza BSD modificata, testo "
        "integrale sotto in QD_LIBRARY_LICENSE.rst): le distribuzioni binarie devono riportarne l'avviso "
        "di copyright, le condizioni e la clausola di esclusione di garanzia. Il testo invita a contattare "
        "il Technology Transfer Department di LBNL per usi commerciali (frase fuori dalle clausole "
        "numerate): da valutare con A11 (licenza di AstroTwo) e con il modulo 60."),
    "astropy": (
        "Include WCSLIB, licenza LGPL-3 (testo sotto in WCSLIB_LICENSE.rst): obblighi di distribuzione "
        "nel .dmg da rispettare nel modulo 60 (vincolo registrato il 2026-10-09); la LGPL-3 incorpora per "
        "riferimento la GPL-3, il cui testo va aggiunto nella distribuzione (modulo 60). Include anche ERFA, "
        "CFITSIO, expat e le altre componenti elencate nei file di licenza sotto."),
    "pims": (
        "Il pacchetto installato non contiene un file di licenza: licenza dichiarata nei metadati "
        "BSD-3-Clause; testo integrale da recuperare dal repository sorgente prima della distribuzione "
        "(da verificare, modulo 60)."),
    "matplotlib": "Licenza basata sulla PSF; il file sotto contiene anche le licenze delle componenti incluse.",
    "numpy": "Le librerie compilate incluse nella ruota (OpenBLAS e runtime GCC) sono descritte nel LICENSE.txt.",
    "scipy": "Le librerie compilate incluse nella ruota (OpenBLAS e runtime GCC) sono descritte nel LICENSE.txt.",
    "pillow": "Il file sotto contiene anche le licenze delle librerie di immagini incluse nella ruota.",
}


@dataclass(frozen=True)
class Component:
    """Componente che non è un pacchetto Python (dati o programmi inclusi nel progetto)."""

    name: str
    version: str
    license: str
    source: str
    license_text: str


#: Componenti non Python inclusi nel progetto (es. kernel della NAIF), con il testo dell'avviso.
EXTRA_COMPONENTS: tuple[Component, ...] = ()


def _roots() -> list[Requirement]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    return [Requirement(text) for text in project["dependencies"]]


def runtime_closure() -> list[md.Distribution]:
    """Pacchetti di esecuzione (marcatori valutati su questa piattaforma, nessun extra), in ordine di nome."""
    environment = default_environment()
    pending, seen = list(_roots()), {}
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        if name in seen:
            continue
        distribution = md.distribution(requirement.name)
        seen[name] = distribution
        for text in distribution.requires or []:
            child = Requirement(text)
            if child.marker is not None and not child.marker.evaluate({**environment, "extra": ""}):
                continue
            pending.append(child)
    return [seen[name] for name in sorted(seen)]


def _license(distribution: md.Distribution) -> str:
    metadata = distribution.metadata
    if metadata.get("License-Expression"):
        return metadata["License-Expression"]
    declared = (metadata.get("License") or "").strip()
    classifiers = [c.split(" :: ")[-1] for c in metadata.get_all("Classifier") or [] if c.startswith("License ::")]
    if declared and "\n" not in declared and len(declared) <= 60:
        return declared
    if classifiers:
        return ", ".join(dict.fromkeys(classifiers)) + " (classificatori)"
    return "non dichiarata nei metadati: vedi il testo sotto"


_LICENSE_FILE = re.compile(r"licen[cs]e|copying|notice|authors", re.IGNORECASE)


def _license_files(distribution: md.Distribution) -> list[tuple[str, str]]:
    files = []
    for path in distribution.files or []:
        text = str(path)
        if ".dist-info/" not in text or not _LICENSE_FILE.search(text.split(".dist-info/", 1)[1]):
            continue
        located = Path(distribution.locate_file(path))
        if located.is_file():
            files.append((text.split(".dist-info/", 1)[1], located.read_text(encoding="utf-8", errors="replace")))
    return sorted(files)


def render() -> str:
    distributions = runtime_closure()
    lines = [
        "THIRD_PARTY_LICENSES — componenti di terze parti di AstroTwo",
        "",
        "File generato da scripts/third_party_licenses.py (decisione del proprietario del 2026-10-13):",
        "non modificarlo a mano; per ogni nuova dipendenza si rigenera. Contiene tutte le dipendenze di",
        "esecuzione su macOS (chiusura delle dipendenze di pyproject.toml), con nome, versione, licenza",
        "dichiarata e il testo integrale dei file di licenza e degli avvisi distribuiti con ogni pacchetto,",
        "più i componenti non Python inclusi nel progetto. Licenza di AstroTwo: da decidere (A11).",
        "Pacchetti esclusi perché richiesti solo su Linux o Windows (marcatori di piattaforma): non",
        "elencati. Python stesso (PSF) e le librerie dell'interfaccia si aggiungeranno con il modulo 60.",
        "",
        "Riepilogo",
        "=========",
        "",
    ]
    width = max(len(d.metadata["Name"]) for d in distributions)
    for distribution in distributions:
        lines.append(f"{distribution.metadata['Name']:<{width}}  {distribution.version:<22}  {_license(distribution)}")
    for component in EXTRA_COMPONENTS:
        lines.append(f"{component.name:<{width}}  {component.version:<22}  {component.license}")
    lines.append("")
    for distribution in distributions:
        name = distribution.metadata["Name"]
        title = f"{name} {distribution.version}"
        lines += ["", "=" * 78, title, "=" * 78, f"Licenza: {_license(distribution)}"]
        home = distribution.metadata.get("Home-page") or next(
            (url.split(",", 1)[1].strip() for url in distribution.metadata.get_all("Project-URL") or []), None)
        if home:
            lines.append(f"Sito: {home}")
        note = NOTES.get(canonicalize_name(name))
        if note:
            lines.append(f"Nota: {note}")
        files = _license_files(distribution)
        if not files:
            lines.append("Testo di licenza: non incluso nel pacchetto installato (vedi la nota).")
        for filename, text in files:
            lines += ["", f"--- {filename} ---", "", text.rstrip()]
    for component in EXTRA_COMPONENTS:
        lines += ["", "=" * 78, f"{component.name} {component.version}", "=" * 78,
                  f"Licenza: {component.license}", f"Fonte: {component.source}", "", component.license_text.rstrip()]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="controlla che il file sia aggiornato, senza scriverlo")
    args = parser.parse_args()
    content = render()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print("THIRD_PARTY_LICENSES non aggiornato: rigenerarlo con scripts/third_party_licenses.py",
                  file=sys.stderr)
            return 1
        return 0
    OUTPUT.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
