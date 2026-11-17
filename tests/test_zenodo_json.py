# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
""".zenodo.json coerente con CITATION.cff (Fase D, sprint D4c): controlli senza rete.

Zenodo, all'archivio di un rilascio GitHub, legge ``.zenodo.json`` al posto di ``CITATION.cff``: i due file devono
dire la stessa cosa. Titolo, autore, licenza, parole chiave, descrizione in inglese e repository devono coincidere;
la versione non sta in ``.zenodo.json`` (Zenodo la prende dal tag del rilascio, che è la stessa di ``CITATION.cff``,
controllata da ``test_citation_cff.py``), così non c'è un secondo numero da tenere allineato. Dalla 1.0.0 (archiviata
su Zenodo il 2026-11-17, passo 14 della ``63``) ``CITATION.cff`` ha il DOI della versione e ``.zenodo.json`` il DOI
«concept».

**D63-2 (decisione del proprietario del 2026-11-11):** ``.zenodo.json`` non ha **mai** la chiave ``doi`` (Zenodo
userebbe quel DOI per il prossimo archivio). Il DOI «concept» di tutte le versioni, quando esiste, sta in
``related_identifiers`` con ``relation`` = ``isVersionOf`` e ``scheme`` = ``doi``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CFF = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
ZENODO = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))

#: Chiavi usate (sottoinsieme dei metadati di deposito di Zenodo); nessun'altra, così niente resta non controllato.
KEYS = {"title", "description", "upload_type", "creators", "license", "keywords", "related_identifiers"}


def doi_problems(data: dict) -> list[str]:
    """Violazioni di D63-2 in un contenuto di ``.zenodo.json`` (lista vuota = conforme)."""
    problems = []
    if "doi" in data:
        problems.append("chiave 'doi' presente: il DOI «concept» va in related_identifiers (isVersionOf)")
    for item in data.get("related_identifiers", []):
        is_doi = item.get("scheme") == "doi" or str(item.get("identifier", "")).lower().startswith(
            ("10.", "doi:", "https://doi.org/"))
        if is_doi and item.get("relation") != "isVersionOf":
            problems.append(f"DOI {item.get('identifier')} con relazione {item.get('relation')!r}, non 'isVersionOf'")
        if is_doi and item.get("scheme") != "doi":
            problems.append(f"DOI {item.get('identifier')} senza scheme 'doi'")
    return problems


def test_only_known_keys_and_software():
    assert set(ZENODO) == KEYS
    assert ZENODO["upload_type"] == "software" and CFF["type"] == "software"
    assert "version" not in ZENODO


def test_doi_rule_d63_2():
    assert doi_problems(ZENODO) == []
    dois = [r for r in ZENODO["related_identifiers"] if r.get("scheme") == "doi"]
    assert len(dois) <= 1  # al più il DOI «concept» di tutte le versioni


@pytest.mark.parametrize(("extra", "ok"), [
    ({"doi": "10.5281/zenodo.1"}, False),
    ({"related_identifiers": [{"identifier": "10.5281/zenodo.1", "relation": "isVersionOf", "scheme": "doi"}]},
     True),
    ({"related_identifiers": [{"identifier": "10.5281/zenodo.1", "relation": "isSupplementTo", "scheme": "doi"}]},
     False),
    ({"related_identifiers": [{"identifier": "https://doi.org/10.5281/zenodo.1", "relation": "isVersionOf",
                               "scheme": "url"}]}, False),
])
def test_doi_rule_rejects_wrong_forms(extra, ok):
    assert (doi_problems({**ZENODO, **extra}) == []) is ok


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
    urls = [r for r in ZENODO["related_identifiers"] if r.get("scheme") != "doi"]
    assert [r["identifier"] for r in urls] == [CFF["repository-code"]]
    assert urls[0]["scheme"] == "url"
