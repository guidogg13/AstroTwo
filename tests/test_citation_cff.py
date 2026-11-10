# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""CITATION.cff: controlli senza rete (Fase D, sprint D1b).

La validazione completa sullo schema ufficiale 1.2.0 si fa a mano con ``cffconvert --validate`` (richiede di
scaricare lo strumento); qui si controllano, senza rete, le regole dello schema che il file usa e la coerenza
con il progetto: chiavi ammesse, campi obbligatori, formati di data, URL, licenza SPDX, ORCID e DOI se presenti,
versione uguale a ``astrotwo.__version__``.
"""

from __future__ import annotations

import datetime as dt
import re
import tomllib
from pathlib import Path

import yaml

import astrotwo

ROOT = Path(__file__).resolve().parents[1]
CFF = ROOT / "CITATION.cff"

# Chiavi di primo livello ammesse dallo schema CFF 1.2.0 (``additionalProperties: false``).
ALLOWED_KEYS = {
    "abstract", "authors", "cff-version", "commit", "contact", "date-released", "doi", "identifiers", "keywords",
    "license", "license-url", "message", "preferred-citation", "references", "repository", "repository-artifact",
    "repository-code", "title", "type", "url", "version",
}
REQUIRED_KEYS = {"authors", "cff-version", "message", "title"}
PERSON_KEYS = {
    "address", "affiliation", "alias", "city", "country", "email", "family-names", "fax", "given-names",
    "name-particle", "name-suffix", "orcid", "post-code", "region", "tel", "website",
}
ORCID = re.compile(r"^https://orcid\.org/[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]{1}$")
DOI = re.compile(r"^10\.\d{4,9}(\.\d+)?/[A-Za-z0-9:/_;\-\.\(\)\[\]\\]+$")
URL = re.compile(r"^(https|http|ftp|sftp)://.+")


def _cff() -> dict:
    # BaseLoader: tutti i valori come stringhe, come li legge lo schema (date e versioni non convertite).
    return yaml.load(CFF.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_keys_and_required_fields() -> None:
    data = _cff()
    assert set(data) <= ALLOWED_KEYS, set(data) - ALLOWED_KEYS
    assert REQUIRED_KEYS <= set(data)
    assert data["cff-version"] == "1.2.0"
    assert data["type"] == "software"
    assert data["title"] == "AstroTwo"
    assert data["message"].strip()


def test_authors_from_project_without_invented_orcid() -> None:
    data = _cff()
    authors = data["authors"]
    assert isinstance(authors, list) and authors
    for person in authors:
        assert set(person) <= PERSON_KEYS
        if "orcid" in person:  # solo un ORCID vero e ben formato; oggi nessuno (commento nel file)
            assert ORCID.match(person["orcid"])
    # Nome già presente nel progetto (NOTICE, copyright)
    names = [f"{p['given-names']} {p['family-names']}" for p in authors]
    assert names == ["Guido Ratti"]
    assert "Copyright (C) 2026 Guido Ratti" in (ROOT / "NOTICE").read_text(encoding="utf-8")


def test_version_license_repository_and_date() -> None:
    data = _cff()
    assert data["version"] == astrotwo.__version__
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert data["license"] == project["license"] == "GPL-3.0-or-later"
    assert data["repository-code"] == "https://github.com/guidogg13/AstroTwo"
    assert URL.match(data["repository-code"])
    dt.date.fromisoformat(data["date-released"])  # formato YYYY-MM-DD dello schema
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["date-released"])
    if "doi" in data:  # da aggiungere dopo Zenodo
        assert DOI.match(data["doi"])
    assert all(isinstance(k, str) and k for k in data.get("keywords", []))
