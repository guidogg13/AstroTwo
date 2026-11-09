# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Profilo completo vero dei quattro oggetti di prova con i tempi (``mdfiles/25-analisi-profilo-oggetto.md`` §12 T17,
sprint C6). Marcato ``network``: **non** si esegue nel commit (``--no-network``), solo a parte. L'esito dei servizi
(Gaia, CDS giù o su) si registra, non fa fallire il test: il profilo deve arrivare comunque, sezione per sezione.

Con ``ASTROTWO_PROFILE_TIMES=<file>`` scrive il riepilogo JSON (tempi e stati) nel file indicato.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from astrotwo.analysis.object_profile import SECTIONS, ProfileTarget, build_profile

OBJECTS = ("51 Peg", "Vega", "eta Tau", "TRAPPIST-1")


@pytest.mark.network
def test_network_full_profile_of_four_objects_with_times(cache):
    summary = []
    for name in OBJECTS:
        start = time.monotonic()
        # Cache del test nuova e vuota: dati scaricati comunque. Niente refresh=True, che riparte dal server
        # principale a ogni richiesta e misurerebbe anche i timeout del CDS giù (25 §3.16 C7-f, sprint C7).
        prof = build_profile(ProfileTarget(name=name), cache=cache)
        total = time.monotonic() - start
        assert prof is not None and not prof.cancelled
        assert [s.name for s in prof.sections] == list(SECTIONS)
        sections = {s.name: {"status": s.status, "elapsed": s.elapsed, "started": s.started,
                             "errors": [e.get("code") for e in s.errors],
                             "servers": sorted({r.url for r in s.requests})} for s in prof.sections}
        summary.append({"name": name, "main_id": None if prof.resolved.simbad is None else prof.resolved.simbad.main_id, "total_s": total, "sections": sections,
                        "warnings": [w[0] for w in prof.warnings]})
        out = os.environ.get("ASTROTWO_PROFILE_TIMES")
        if out:  # scritto a ogni oggetto: l'esito resta anche se un controllo fallisce
            with open(out, "w", encoding="utf-8") as handle:
                json.dump(summary, handle, indent=1, default=str)
    for item in summary:
        assert item["sections"]["identity"]["status"] in ("done", "partial"), item  # SIMBAD (CDS o Harvard)
        assert all(s["status"] != "pending" for s in item["sections"].values()), item
