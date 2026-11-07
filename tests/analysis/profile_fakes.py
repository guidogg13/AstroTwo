# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Servizi simulati del profilo (sprint C2–C3) con le **risposte vere registrate il 2026-11-07**.

Le risposte sono in ``tests/analysis/data/profile/`` (``index.json``: servizio e interrogazione ADQL inviata → file,
server che ha risposto, data). Le hanno date il mirror SIMBAD di Harvard (CDS irraggiungibile quel giorno), l'archivio
Gaia dell'ESA, il NASA Exoplanet Archive e (sprint C3) l'IRSA a richieste fatte dal codice del 25 stesso, per 51 Peg,
Vega, eta Tau (Alcyone) e TRAPPIST-1, più bersagli per coordinate e un nome sconosciuto. Il servizio SED di VizieR
(CDS) era giù quel giorno: senza una risposta in ``overrides`` risponde HTTP 503 (CDS giù, come il 2026-11-07).

Un server HTTP locale (``FakeService``) risponde a ``/simbad/sync``, ``/gaia/sync``, ``/exoplanet/sync``, ``/irsa/sync``
e ``/vizier/sed`` cercando
la ``QUERY`` nell'indice; ``overrides`` sostituisce una risposta (servizio giù, risposta sintetica per un caso che i
dati veri non hanno). Una interrogazione non registrata fa fallire il test con il testo della query.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

import astrotwo.core.vo_protocols as vo
from tests.conftest import FakeService

DATA = Path(__file__).resolve().parent / "data" / "profile"
INDEX = json.loads((DATA / "index.json").read_text(encoding="utf-8"))
SERVICES = {"cds-simbad-tap": "simbad", "esa-gaia-tap": "gaia", "nasa-exoplanet-tap": "exoplanet",
            "nasa-irsa-tap": "irsa"}

EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>
<TABLE>{fields}<DATA><TABLEDATA>{rows}</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""


def votable(fields: list[tuple[str, str, str | None]], rows: list[list[object]]) -> str:
    """VOTable sintetico: ``fields`` = (nome, tipo VOTable, unità)."""
    head = "".join(
        f'<FIELD name="{n}" datatype="{t}"' + (' arraysize="*"' if t == "char" else "")
        + (f' unit="{unit}"' if unit else "") + "/>" for n, t, unit in fields)
    body = "".join("<TR>" + "".join(f"<TD>{'' if v is None else v}</TD>" for v in row) + "</TR>" for row in rows)
    return EMPTY.format(fields=head, rows=body)


def recorded(service: str, query: str) -> bytes:
    return (DATA / INDEX[f"{service}|{query}"]["file"]).read_bytes()


def recorded_query(service: str, contains: str) -> str:
    """L'unica interrogazione registrata del servizio che contiene il testo dato."""
    found = [k.split("|", 1)[1] for k in INDEX if k.startswith(service + "|") and contains in k]
    assert len(found) == 1, (service, contains, found)
    return found[0]


class RecordedServices:
    """Server locale con le risposte registrate; ``overrides[(servizio, testo)] = funzione(query) -> risposta``."""

    def __init__(self) -> None:
        self.fake = FakeService()
        self.overrides: dict[tuple[str, str], object] = {}
        self.queries: list[tuple[str, str]] = []
        self.missing: list[tuple[str, str]] = []
        for service in SERVICES.values():
            self.fake.routes[f"/{service}/sync"] = self._route(service)
        self.fake.routes["/vizier/sed"] = self._route("vizier")

    def _route(self, service: str):
        def answer(request):
            params = request["params"]
            query = (params.get("QUERY", "") if service != "vizier"
                     else "&".join(f"{k}={v}" for k, v in sorted(params.items())))
            self.queries.append((service, query))
            for (name, text), make in self.overrides.items():
                if name == service and text in query:
                    out = make(query)
                    return out if isinstance(out, tuple) else (200, "application/x-votable+xml", out)
            key = f"{service}|{query}"
            if service == "vizier" and key not in INDEX:
                return 503, "text/plain", "CDS non raggiungibile (come il 2026-11-07)"
            if key not in INDEX:
                self.missing.append((service, query))
                return 400, "text/plain", f"query non registrata: {query}"
            return 200, "application/x-votable+xml", recorded(service, query)
        return answer

    def url(self, service: str) -> str:
        return f"{self.fake.url}/{service}"

    def count(self, service: str | None = None) -> int:
        return sum(1 for s, _ in self.queries if service is None or s == service)

    def close(self) -> None:
        self.fake.close()


@pytest.fixture
def services(monkeypatch):
    """Voci ``cds-simbad-tap``, ``esa-gaia-tap``, ``nasa-exoplanet-tap``, ``nasa-irsa-tap`` e servizio SED di VizieR
    diretti al server locale (nessun mirror)."""
    fake = RecordedServices()
    entries = tuple(dataclasses.replace(e, url=fake.url(SERVICES[e.id])) if e.id in SERVICES else e
                    for e in vo.BUILTIN_SERVERS)
    monkeypatch.setattr(vo, "BUILTIN_SERVERS", entries)
    monkeypatch.setattr(vo, "VIZIER_PHOTOMETRY_URL", f"{fake.url('vizier')}/sed")
    yield fake
    fake.close()
    assert not fake.missing, f"interrogazioni non registrate: {fake.missing}"
