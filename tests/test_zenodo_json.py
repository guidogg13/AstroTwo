# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
""".zenodo.json coerente con CITATION.cff (Fase D, sprint D4c): controlli senza rete.

Zenodo, all'archivio di un rilascio GitHub, legge ``.zenodo.json`` al posto di ``CITATION.cff``: i due file devono
dire la stessa cosa. Titolo, autore, licenza, parole chiave, descrizione in inglese e repository devono coincidere;
la versione non sta in ``.zenodo.json`` (Zenodo la prende dal tag del rilascio, che è la stessa di ``CITATION.cff``,
controllata da ``test_citation_cff.py``), così non c'è un secondo numero da tenere allineato. Il DOI non c'è ancora
(arriva con il primo archivio su Zenodo) e non sta in nessuno dei due file finché non esiste.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CFF = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
ZENODO = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))

#: Chiavi usate (sottoinsieme dei metadati di deposito di Zenodo); nessun'altra, così niente resta non controllato.
KEYS = {"title", "description", "upload_type", "creators", "license", "keywords", "related_identifiers"}


def test_only_known_keys_and_software():
    assert set(ZENODO) == KEYS
    assert ZENODO["upload_type"] == "software" and CFF["type"] == "software"
    assert "version" not in ZENODO and "doi" not in ZENODO and "doi" not in CFF


def test_title_license_keywords_match():
    assert ZENODO["title"] == CFF["title"]
    assert ZENODO["license"].lower() == CFF["license"].lower() == "gpl-3.0-or-later"
    assert ZENODO["keywords"] == CFF["keywords"]


def test_creators_match_authors():
    expected = [f"{a['family-names']}, {a['given-names']}" for a in CFF["authors"]]
    assert [c["name"] for c in ZENODO["creators"]] == expected
    for creator, author in zip(ZENODO["creators"], CFF["authors"], strict=True):
        orcid = author.get("orcid")  # nel CFF è un URL, in Zenodo solo il numero; oggi assente in entrambi
        assert creator.get("orcid") == (orcid.removeprefix("https://orcid.org/") if orcid else None)


def test_description_is_the_english_abstract():
    assert ZENODO["description"] == " ".join(CFF["abstract"].split())
    text = ZENODO["description"]
    assert text.isascii() and "AstroTwo" in text
    # posizionamento della Fase D: complementare ad Aladin, TOPCAT e DS9, mai sostituto; l'IA non inventa numeri
    assert "alongside Aladin, TOPCAT and DS9" in text and "never produces numbers" in text
    assert not any(word in text.lower() for word in ("replace", "successor", "instead of"))


def test_repository_matches():
    urls = [r["identifier"] for r in ZENODO["related_identifiers"]]
    assert urls == [CFF["repository-code"]]
    assert ZENODO["related_identifiers"][0]["scheme"] == "url"
