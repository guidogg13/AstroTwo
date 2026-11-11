# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test di ``scripts/validate_profiles.py`` senza rete: regola del testo vuoto (D25-24, decisa il 2026-11-10).

Un testo vuoto di una fonte è un valore assente dichiarato, mai un valore (``02`` §2): il confronto lo tratta come un
valore mancante su entrambi i lati; ``--recompare`` lo applica alle righe di una misura già salvata (la seconda misura
del 2026-11-10 in ``docs/validation-runs/2026-11-10-run2/``) e lascia invariati i file misurati."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import urllib.request
from pathlib import Path

import pytest
from astropy.table import Table

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "validate_profiles.py"
RUN2 = ROOT / "docs" / "validation-runs" / "2026-11-10-run2"
spec = importlib.util.spec_from_file_location("validate_profiles", SCRIPT)
vp = importlib.util.module_from_spec(spec)
sys.modules["validate_profiles"] = vp
spec.loader.exec_module(vp)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("richiesta di rete")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)


@pytest.mark.parametrize(("astro", "ref", "expected"), [
    (None, "", (True, "both empty")), (None, "   ", (True, "both empty")), ("", "", (True, "both empty")),
    (None, None, (True, "both empty")), (None, "G2IV", (False, "one is empty")), ("G2IV", "", (False, "one is empty")),
    ("G2IV", "G2IV", (True, "text")), ("G2IV", "G2V", (False, "text"))])
def test_empty_text_is_a_value_declared_absent(astro, ref, expected):
    assert vp.same_read(astro, ref, None) == expected


def test_absent_rows_from_the_profile_details():
    simbad = {"table": Table({"sp_type": [""]}), "server": "https://simbad.example/sync", "query": "q",
              "retrieved_at": "2026-11-10T20:04:00Z"}
    section = {"name": "identity", "values": [],
               "details": {"absent": [{"quantity": "sp_type", "note": "SIMBAD has no spectral type"}]}}
    (r,) = vp.absent_rows("M 13", section, {"simbad": simbad})
    assert r["outcome"] == "pass" and r["difference"] == "both empty" and r["quantity"] == "sp_type (SIMBAD)"
    assert "SIMBAD has no spectral type" in r["astrotwo"]
    simbad["table"] = Table({"sp_type": ["G2IV"]})
    (r,) = vp.absent_rows("51 Peg", section, {"simbad": simbad})
    assert r["outcome"] == "fail"  # AstroTwo non scrive un valore che la fonte ha
    (r,) = vp.absent_rows("M 13", section, {"simbad": {"table": None, "error": "down", "query": "q"}})
    assert r["outcome"] == "not measured"


def test_recompare_second_run_of_2026_11_10(tmp_path):
    """I 2 fail della seconda misura (3C 273 e M 13, tipo spettrale vuoto) diventano pass; nient'altro cambia."""
    run = tmp_path / "run2"
    run.mkdir()
    shutil.copy(RUN2 / "results.json", run / "results.json")
    saved = json.loads((run / "results.json").read_text())
    assert sum(r["outcome"] == "fail" for r in saved["rows"]) == 2
    assert vp.recompare_run(run) == 0
    again = json.loads((run / "results-recompared.json").read_text())
    rows = again["rows"]
    assert len(rows) == len(saved["rows"])
    assert {k: sum(r["outcome"] == k for r in rows) for k in ("pass", "fail", "not measured")} == \
        {"pass": 177, "fail": 0, "not measured": 85}
    changed = [(a["object"], a["quantity"]) for a, b in zip(saved["rows"], rows, strict=True) if a != b]
    assert changed == [("3C 273", "sp_type (SIMBAD)"), ("M 13", "sp_type (SIMBAD)")]
    assert all("D25-24" in b["note"] for a, b in zip(saved["rows"], rows, strict=True) if a != b)
    assert again["meta"]["recompared"]["changed"] == [["3C 273", "sp_type (SIMBAD)", "fail", "pass"],
                                                      ["M 13", "sp_type (SIMBAD)", "fail", "pass"]]
    # i file salvati nel repository coincidono con il ricalcolo (nessuna data a parte quella del ricalcolo)
    committed = json.loads((RUN2 / "results-recompared.json").read_text())
    assert committed["rows"] == rows
    assert (RUN2 / "results-recompared.md").read_text() == (run / "results-recompared.md").read_text()


@pytest.mark.parametrize(("astro", "ref", "same"), [
    ("d", "days", True), ("earthMass", "Earth Mass", True), ("earthRad", "Earth Radius", True),
    ("5.9721679e+24kg", "Earth Mass", False),  # fattore troncato: non è la massa terrestre (D05-6)
    ("mas yr-1", "mas / yr", True), ("K", "K", True), ("d", "Earth Mass", False), ("", "", True)])
def test_d05_6_units_compared_as_astropy_units(astro, ref, same):
    """D05-6 (decisione del proprietario del 2026-11-11): unità confrontate come unità di Astropy, non come testo;
    le parole del NASA Exoplanet Archive lette con la tabella dichiarata nello script; tolleranze invariate."""
    assert vp.same_unit(astro, ref) is same


def test_d05_6_planet_row_passes_only_with_the_same_unit():
    table = Table({"pl_bmasse": [193.87532827]})
    table["pl_bmasse"].unit = "Earth Mass"
    part = {"table": table, "server": "s", "query": "q", "retrieved_at": "t"}
    good = vp.read_row("51 Peg", "Planets", "51 Peg b mass", {"value": 193.87532827, "unit": "earthMass"}, part,
                       "pl_bmasse")
    bad = vp.read_row("51 Peg", "Planets", "51 Peg b mass", {"value": 193.87532827, "unit": "5.9721679e+24kg"},
                      part, "pl_bmasse")
    assert good["outcome"] == "pass" and bad["outcome"] == "fail" and "unit" in bad["note"]
