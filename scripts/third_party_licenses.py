# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
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
    "pyside6-essentials": (
        "PySide6 (Qt for Python) e le librerie Qt incluse nella ruota: AstroTwo le usa con la LGPL-3.0 (licenza "
        "scelta tra LGPL-3.0-only, GPL-2.0-only e GPL-3.0-only; registrata il 2026-10-15 per A11 e per il modulo "
        "60). La ruota non contiene i testi: LGPL-3.0 e GPL-3.0 (a cui la LGPL rimanda) sono presi dal sorgente "
        "ufficiale, sotto. Obblighi LGPL nel .dmg (librerie sostituibili dall'utente, avvisi) e avvisi delle "
        "componenti di terze parti incluse nelle librerie Qt (elenco \"Licenses Used in Qt\" della "
        "documentazione di Qt): da completare con il modulo 60."),
    "shiboken6": "Generatore e runtime dei binding di PySide6: stessa licenza e stessi testi di pyside6-essentials.",
    "anthropic": "SDK ufficiale di Anthropic (modulo 30). Include httpx_aiohttp (licenza e avviso sotto).",
    "openai": "SDK ufficiale di OpenAI (modulo 30). Include httpx_aiohttp (licenza sotto).",
    "httpx2": "Trasporto HTTP degli SDK anthropic e openai (successore di httpx; il modulo 30 lo usa solo tramite gli SDK).",
    "keyring": "Accesso al Portachiavi di macOS (modulo 31), usato solo con il backend macOS.",
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


_PYSIDE_SOURCE = (
    "cartella LICENSES/ del sorgente ufficiale https://download.qt.io/official_releases/QtForPython/pyside6/"
    "PySide6-6.12.0-src/pyside-setup-everywhere-src-6.12.0.zip (SHA-256 "
    "15b25c9e06f3acb8930c318192f3c20aee162f4b8d01bf4b4c60193c924cd847), copiata in scripts/licenses/; letto il "
    "2026-10-16")
_LICENSES_DIR = Path(__file__).resolve().parent / "licenses"


def _pyside_texts() -> str:
    return "\n\n".join(
        f"--- {name} ---\n\n" + (_LICENSES_DIR / name).read_text(encoding="utf-8").rstrip()
        for name in ("LGPL-3.0-only.txt", "GPL-3.0-only.txt"))


#: Testi di licenza presi fuori dal pacchetto installato, quando la ruota non li contiene: nome del pacchetto →
#: (fonte, testo integrale).
EXTERNAL_LICENSE_TEXTS: dict[str, tuple[str, str]] = {
    "pyside6-essentials": (_PYSIDE_SOURCE, _pyside_texts()),
    "shiboken6": (_PYSIDE_SOURCE, _pyside_texts()),
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


def _texts(folder: Path, names: tuple[str, ...]) -> str:
    return "\n\n".join(f"--- {name} ---\n\n" + (folder / name).read_text(encoding="utf-8").rstrip() for name in names)


#: Testi del Python di AstroTwo.app (60 §3.7): CPython e librerie compilate in libpython da python-build-standalone.
_PYTHON_LICENSES = ("LICENSE.cpython.txt", "LICENSE.openssl-3.txt", "LICENSE.sqlite.txt", "LICENSE.libffi.txt",
                    "LICENSE.liblzma.txt", "LICENSE.bzip2.txt", "LICENSE.mpdecimal.txt", "LICENSE.expat.txt",
                    "LICENSE.libuuid.txt")


def _pyinstaller_texts() -> str:
    """Licenza del bootloader e degli hook di esecuzione inclusi nell'app, dai pacchetti installati (gruppo build)."""
    parts = []
    for name in ("pyinstaller", "pyinstaller-hooks-contrib"):
        distribution = md.distribution(name)
        parts += [f"--- {name} {distribution.version}: {filename} ---\n\n{text.rstrip()}"
                  for filename, text in _license_files(distribution)]
    return "\n\n".join(parts)


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
    Component(
        name="Lucide (icone SVG dell'interfaccia)",
        version="lucide-static 1.59.0",
        license="ISC; MIT (progetto Feather) per le icone derivate elencate nel testo",
        source=("pacchetto npm lucide-static 1.59.0 (https://registry.npmjs.org/lucide-static/-/"
                "lucide-static-1.59.0.tgz, SHA-1 3a4b633a0516bd1cf96524ef54f907cec0fd1007, verificata il 2026-10-17); "
                "icone copiate senza modifiche in src/astrotwo/ui/icons/ insieme al file LICENSE del pacchetto "
                "(40 §3.11)"),
        license_text=(ROOT / "src" / "astrotwo" / "ui" / "icons" / "LICENSE").read_text(encoding="utf-8"),
    ),
)


def app_components() -> tuple[Component, ...]:
    """Componenti che entrano solo in AstroTwo.app (60 §3.7): Python, avvisi di Qt, bootloader di PyInstaller."""
    return (
        Component(
            name="Python (CPython, python-build-standalone)",
            version="3.12.15+20261003",
            license="PSF-2.0; OpenSSL Apache-2.0; SQLite pubblico dominio; libffi, expat MIT; XZ 0BSD; bzip2; "
                    "mpdecimal BSD-2-Clause; libuuid BSD-3-Clause",
            source=("interprete di AstroTwo.app (60 §3.3): archivio cpython-3.12.15+20261003-aarch64-apple-darwin di "
                    "https://github.com/astral-sh/python-build-standalone/releases/tag/20261003; testi in "
                    "scripts/licenses/python/ (provenienza e SHA-256 nel README.md di quella cartella)"),
            license_text=_texts(_LICENSES_DIR / "python", _PYTHON_LICENSES),
        ),
        Component(
            name="Qt 6.12.0, componenti di terze parti (qtbase, qtsvg)",
            version="6.12.0",
            license="licenze delle singole componenti, elencate sotto (Licenses Used in Qt)",
            source=("qt_attribution.json e LICENSES/ dei sorgenti ufficiali qtbase e qtsvg 6.12.0 "
                    "(https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/); criterio e SHA-256 in "
                    "scripts/licenses/qt/README.md"),
            license_text=(_LICENSES_DIR / "qt" / "QT_THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8"),
        ),
        Component(
            name="Bootloader e hook di esecuzione di PyInstaller",
            version=f"pyinstaller {md.version('pyinstaller')}, hooks-contrib {md.version('pyinstaller-hooks-contrib')}",
            license="GPL-2.0-or-later con eccezione del bootloader; hook di esecuzione Apache-2.0",
            source=("eseguibile Contents/MacOS/AstroTwo e hook di esecuzione dell'app, dai pacchetti pyinstaller e "
                    "pyinstaller-hooks-contrib (gruppo build); lo strumento PyInstaller non si distribuisce"),
            license_text=_pyinstaller_texts(),
        ),
    )


#: Dati di terze parti inclusi solo per i test (tests/core/data/README.md), con le condizioni d'uso delle fonti.
TEST_DATA: tuple[tuple[str, str], ...] = ()  # dal 2026-10-22 nessuno: i dati di test sono sintetici


def _roots() -> list[Requirement]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    return [Requirement(text) for text in project["dependencies"]]


def _dev_roots() -> list[Requirement]:
    groups = tomllib.loads((ROOT / "pyproject.toml").read_text()).get("dependency-groups", {})
    return [Requirement(text) for group in ("dev", "build") for text in groups.get(group, [])]


def runtime_closure() -> list[md.Distribution]:
    """Pacchetti di esecuzione (marcatori valutati su questa piattaforma, nessun extra), in ordine di nome."""
    return _closure(_roots())


def dev_closure() -> list[md.Distribution]:
    """Strumenti di sviluppo (gruppi ``dev`` e ``build``) che non sono già dipendenze di esecuzione: non vanno nel .dmg."""
    runtime = {canonicalize_name(d.metadata["Name"]) for d in runtime_closure()}
    return [d for d in _closure(_dev_roots()) if canonicalize_name(d.metadata["Name"]) not in runtime]


def _closure(roots: list[Requirement]) -> list[md.Distribution]:
    environment = default_environment()
    pending, seen = list(roots), {}
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
        "più i componenti non Python inclusi nel progetto. Licenza di AstroTwo: GPL-3.0-or-later (A11 decisa il 2026-10-17).",
        "Pacchetti esclusi perché richiesti solo su Linux o Windows (marcatori di piattaforma): non",
        "elencati. Dal modulo 60 (2026-10-25) anche i componenti che entrano solo in AstroTwo.app: il",
        "Python dell'app (PSF e librerie incluse), gli avvisi delle componenti incluse nelle librerie Qt e",
        "il bootloader di PyInstaller. In fondo, a parte, gli strumenti di sviluppo (test e costruzione),",
        "che non si distribuiscono.",
        "",
        "Riepilogo",
        "=========",
        "",
    ]
    width = max(len(d.metadata["Name"]) for d in distributions)
    for distribution in distributions:
        lines.append(f"{distribution.metadata['Name']:<{width}}  {distribution.version:<22}  {_license(distribution)}")
    components = EXTRA_COMPONENTS + app_components()
    for component in components:
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
    for component in components:
        lines += ["", "=" * 78, f"{component.name} {component.version}", "=" * 78,
                  f"Licenza: {component.license}", f"Fonte: {component.source}", "", component.license_text.rstrip()]
    dev = dev_closure()
    lines += ["", "", "Strumenti di sviluppo (test e costruzione, non distribuiti nell'app né nel .dmg)",
              "================================================================================", ""]
    for distribution in dev:
        lines.append(f"{distribution.metadata['Name']:<{width}}  {distribution.version:<22}  {_license(distribution)}")
    for distribution in dev:
        lines += ["", "-" * 78, f"{distribution.metadata['Name']} {distribution.version}", "-" * 78,
                  f"Licenza: {_license(distribution)}"]
        for filename, text in _license_files(distribution):
            lines += ["", f"--- {filename} ---", "", text.rstrip()]
    lines += ["", "", "Dati di terze parti nei test (solo nel repository, non distribuiti nel .dmg)",
              "==========================================================================", ""]
    if not TEST_DATA:
        lines.append("Nessuno: i dati di test in tests/core/data/ sono sintetici (stelle inventate, generate da "
                     "scripts/make_synthetic_catalog.py) e coperti dalla GPL di AstroTwo; vedi tests/core/data/README.md.")
    else:
        lines += ["I file in tests/core/data/ elencati qui NON sono coperti dalla GPL di AstroTwo ma dalle condizioni",
                  "d'uso delle loro fonti; testo completo e link ufficiali in tests/core/data/README.md.", ""]
    for name, terms in TEST_DATA:
        lines.append(f"- {name}: {terms}")
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
