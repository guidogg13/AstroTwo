# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test di rete della demo delle Pleiadi (``examples/demo_pleiadi.py``): figura e report creati.

La demo usa solo funzioni pubbliche di AstroTwo; qui si controlla che arrivi in fondo con i servizi reali e che il
report contenga i numeri di ogni passo con la loro provenienza. Gira nella cartella home temporanea dei test (cache
comune vuota: tutto si scarica).
"""

import importlib.util
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parent.parent / "examples" / "demo_pleiadi.py"


def _load_demo():
    spec = importlib.util.spec_from_file_location("demo_pleiadi", DEMO)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.network
def test_demo_pleiadi_creates_figure_and_report(tmp_path):
    demo = _load_demo()
    figure, report = demo.run(tmp_path, show=False)
    assert figure == tmp_path / "demo_pleiadi.png" and report == tmp_path / "demo_pleiadi.txt"
    assert figure.stat().st_size > 100_000 and figure.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    text = report.read_text(encoding="utf-8")
    for expected in ("resolve_name (modulo 10)", "sia_search (modulo 14)", "DSS2-red", "epoca J2016.0",
                     "display_positions (modulo 13, D10-2)", "column_statistics del 13", "max_sep = 2.0 arcsec",
                     "calcolatrice algebrica del 18", "distanza Alcyone–Atlas:", "angolo di posizione di Atlas",
                     "stelle Gaia dentro il MOC:", "— tutte dentro", "set_display dell'11",
                     "epoca di visualizzazione 1989-12-17T00:00:00.000 (utc), fonte: epoca dell'immagine",
                     "spostamento epoca della tabella → epoca di visualizzazione: media",
                     "frecce del moto proprio: dalla posizione all'epoca di visualizzazione",
                     "stelle Gaia e frecce all'epoca di visualizzazione", "SIMBAD (J2000"):
        assert expected in text, expected
