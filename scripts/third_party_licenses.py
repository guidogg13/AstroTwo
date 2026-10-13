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
        "La ruota installata non contiene un file di licenza: testo integrale (BSD-3-Clause) preso dal "
        "license.txt del sorgente ufficiale pims-0.7.tar.gz su PyPI, identico a quello del repository "
        "(verificato il 2026-10-13, sotto). Il testo lascia non compilato il segnaposto <COPYRIGHT HOLDER> "
        "della clausola di esclusione di garanzia: da valutare con A11 e con il modulo 60."),
    "matplotlib": "Licenza basata sulla PSF; il file sotto contiene anche le licenze delle componenti incluse.",
    "numpy": "Le librerie compilate incluse nella ruota (OpenBLAS e runtime GCC) sono descritte nel LICENSE.txt.",
    "scipy": "Le librerie compilate incluse nella ruota (OpenBLAS e runtime GCC) sono descritte nel LICENSE.txt.",
    "pillow": "Il file sotto contiene anche le licenze delle librerie di immagini incluse nella ruota.",
    "spiceypy": (
        "La ruota include il toolkit CSPICE (N0067) della NAIF (Caltech/JPL per la NASA), soggetto alle regole "
        "d'uso della NAIF riportate sotto nella voce del kernel pck00011.tpc (uso anche commerciale ammesso senza "
        "licenze né costi; inclusione dei moduli del toolkit in un programma che li usa ammessa; clausola di "
        "esclusione di garanzia da riportare)."),
    "pds4-tools": "Small Bodies Node della NASA PDS (University of Maryland).",
}

#: Regole d'uso della NAIF (https://naif.jpl.nasa.gov/naif/rules.html, lette il 2026-10-13): estratti pertinenti.
NAIF_RULES = """Rules Regarding Use of SPICE (NAIF, https://naif.jpl.nasa.gov/naif/rules.html), estratti letti il
2026-10-13:

Toolkit Redistribution
Redistribution of the unmodified SPICE Toolkit, such as from a mirror site, is prohibited without prior,
written clearance from the NAIF manager. However, including the SPICE Toolkit modules (source and object
code), documentation, and relevant SPICE Toolkit programs and allied User Guides as part of a package
supporting a customer-built SPICE-based tool is entirely appropriate. This includes providing a new 3rd party
interface to the SPICE Toolkit, subject to the relevant rules listed elsewhere on this webpage.

Kernels Distribution
SPICE kernels placed on the NAIF server may be downloaded and used by anyone, consistent with the other rules
found on this web page.

Kernels Redistribution
Redistribution of SPICE kernels distributed by NAIF is permitted as long as they have not been modified. If a
kernel distributed by NAIF has been modified in any way, any embedded or otherwise allied attribution of the
original kernel producer must be replaced with the name and institution of whomever has made the last
modification. Redistribution of kernels distributed by any other entity is subject to the rules on and of
that entity.

Commercial Use of SPICE
Use of SPICE components in commercial products is allowed, subject to the substantial restrictions on user
support noted under "Getting Help from NAIF" above. No fees or licensing are required. Acknowledgement of the
use of NASA's SPICE system is encouraged.

Disclaimer applicable to all NAIF-provided software
THIS SOFTWARE AND ANY RELATED MATERIALS WERE CREATED BY THE CALIFORNIA INSTITUTE OF TECHNOLOGY (CALTECH) UNDER
A U.S. GOVERNMENT CONTRACT WITH THE NATIONAL AERONAUTICS AND SPACE ADMINISTRATION (NASA). THE SOFTWARE IS
TECHNOLOGY AND SOFTWARE PUBLICLY AVAILABLE UNDER U.S. EXPORT LAWS AND IS PROVIDED "AS-IS" TO THE RECIPIENT
WITHOUT WARRANTY OF ANY KIND, INCLUDING ANY WARRANTIES OF PERFORMANCE OR MERCHANTABILITY OR FITNESS FOR A
PARTICULAR USE OR PURPOSE (AS SET FORTH IN UNITED STATES UCC§2312-§2313) OR FOR ANY PURPOSE WHATSOEVER, FOR THE
SOFTWARE AND RELATED MATERIALS, HOWEVER USED. IN NO EVENT SHALL CALTECH, ITS JET PROPULSION LABORATORY, OR NASA
BE LIABLE FOR ANY DAMAGES AND/OR COSTS, INCLUDING, BUT NOT LIMITED TO, INCIDENTAL OR CONSEQUENTIAL DAMAGES OF
ANY KIND, INCLUDING ECONOMIC DAMAGE OR INJURY TO PROPERTY AND LOST PROFITS, REGARDLESS OF WHETHER CALTECH, JPL,
OR NASA BE ADVISED, HAVE REASON TO KNOW, OR, IN FACT, SHALL KNOW OF THE POSSIBILITY. RECIPIENT BEARS ALL RISK
RELATING TO QUALITY AND PERFORMANCE OF THE SOFTWARE AND ANY RELATED MATERIALS, AND AGREES TO INDEMNIFY CALTECH
AND NASA FOR ALL THIRD-PARTY CLAIMS RESULTING FROM THE ACTIONS OF RECIPIENT IN THE USE OF THE SOFTWARE.

Acknowledgement: AstroTwo uses NASA's SPICE system (NAIF, JPL) for planetary body names and constants.
"""


#: Testi di licenza presi fuori dal pacchetto installato, quando la ruota non li contiene: nome del pacchetto →
#: (fonte, testo integrale).
EXTERNAL_LICENSE_TEXTS: dict[str, tuple[str, str]] = {
    "pims": (
        "license.txt del sorgente ufficiale https://files.pythonhosted.org/packages/b8/02/"
        "5bf3639f5b77e9b183011c08541c5039ba3d04f5316c70312b48a8e003a9/pims-0.7.tar.gz (SHA-256 "
        "55907a4c301256086d2aa4e34a5361b9109f24e375c2071e1117b9491e82946b, uguale a quello pubblicato da PyPI), "
        "identico a https://github.com/soft-matter/pims/blob/main/license.txt; letto il 2026-10-13",
        """Copyright Notice and Statement for the PIMS Project
===================================================

   Copyright (c) 2013-2014 PIMS contributors
   https://github.com/soft-matter/pims
   All rights reserved

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of the soft-matter organization nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.""",
    ),
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
EXTRA_COMPONENTS: tuple[Component, ...] = (
    Component(
        name="pck00011.tpc (kernel PCK generico della NAIF)",
        version="2022-12-27",
        license="regole d'uso della NAIF (ridistribuzione ammessa solo senza modifiche)",
        source=("https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc, incluso senza modifiche in "
                "src/astrotwo/core/data/naif/ (SHA-256 "
                "3dff7b1dbeceaa01f25467767d3fa25816051c85d162d1edf04acb310ee28bb1); dati del rapporto IAU WGCCRE "
                "2015 (Archinal et al. 2018)"),
        license_text=NAIF_RULES,
    ),
)


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
        external = EXTERNAL_LICENSE_TEXTS.get(canonicalize_name(name))
        if not files and external:
            lines += ["", f"--- testo di licenza (fonte: {external[0]}) ---", "", external[1].rstrip()]
        elif not files:
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
