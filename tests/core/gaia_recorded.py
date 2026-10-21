# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Risposta registrata di TAP VizieR per Gaia DR3 attorno ad Alcyone (``data/gaia_dr3_alcyone``, README), servita dal
servizio HTTP simulato dei test: nessuna rete (D41-6, T35 del 13, T34 del 41)."""

import dataclasses
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord

import astrotwo.core.vo_protocols as vo

DATA = Path(__file__).parent / "data" / "gaia_dr3_alcyone"
CATALOG = "I/355/gaiadr3"
CENTER = (56.75, 24.1167)  # gradi ICRS, la regione registrata
RADIUS = 1 * u.arcmin
ROWS = 11


def center() -> SkyCoord:
    return SkyCoord(CENTER[0] * u.deg, CENTER[1] * u.deg)


def serve(service, monkeypatch) -> None:
    """Il TAP di VizieR punta al servizio simulato, che risponde con i tre file registrati secondo la query."""
    entries = tuple(dataclasses.replace(e, url=service.url + "/viz") if e.id == "cds-vizier-tap" else e
                    for e in vo.BUILTIN_SERVERS)
    monkeypatch.setattr(vo, "BUILTIN_SERVERS", entries)

    def tap(request):
        query = request["params"]["QUERY"]
        name = "tap_schema" if "TAP_SCHEMA.columns" in query else "top0" if "TOP 0" in query else "region"
        return 200, "application/x-votable+xml", (DATA / f"{name}.xml").read_bytes()

    service.routes["/viz/sync"] = tap
