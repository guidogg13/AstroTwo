# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Genera i dati di test SINTETICI ``tests/core/data/synthetic_vizier/``: tre risposte TAP in VOTable (schema delle
colonne, ``SELECT TOP 0``, regione) con stelle INVENTATE, stessa struttura di un catalogo astrometrico con ``COOSYS``
ICRS ``epoch="2016.0"``. Nessun dato di terze parti: i numeri vengono da un generatore casuale con seme fisso.

Uso: ``uv run python scripts/make_synthetic_catalog.py`` (riscrive i tre file in modo identico a ogni esecuzione).
"""

from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "tests" / "core" / "data" / "synthetic_vizier"
CATALOG = "I/355/gaiadr3"  # solo il nome usato dai test per l'elenco dei cataloghi; i dati NON sono quelli reali
CENTER = (56.75, 24.1167)  # gradi ICRS
RADIUS_DEG = 1 / 60
ROWS = 11
SEED = 20261022
EPOCH = "2016.0"

# (nome, tipo, unità, UCD, ref al COOSYS, descrizione)
COLUMNS = (
    ("DR3Name", "char", None, "meta.id", False, "Synthetic source designation"),
    ("RA_ICRS", "double", "deg", "pos.eq.ra;meta.main", True, "Right ascension (ICRS) at Ep=2016.0"),
    ("DE_ICRS", "double", "deg", "pos.eq.dec;meta.main", True, "Declination (ICRS) at Ep=2016.0"),
    ("Source", "long", None, "meta.id;meta.main", False, "Synthetic source number"),
    ("e_RA_ICRS", "float", "mas", "stat.error;pos.eq.ra", False, "Standard error of right ascension"),
    ("e_DE_ICRS", "float", "mas", "stat.error;pos.eq.dec", False, "Standard error of declination"),
    ("Plx", "double", "mas", "pos.parallax.trig", False, "? Parallax"),
    ("e_Plx", "float", "mas", "stat.error;pos.parallax.trig", False, "? Standard error of parallax"),
    ("pmRA", "double", "mas/yr", "pos.pm;pos.eq.ra", True, "? Proper motion in right ascension, pmRA*cosDE"),
    ("e_pmRA", "float", "mas/yr", "stat.error;pos.pm;pos.eq.ra", False, "? Standard error of pmRA"),
    ("pmDE", "double", "mas/yr", "pos.pm;pos.eq.dec", True, "? Proper motion in declination"),
    ("e_pmDE", "double", "mas/yr", "stat.error;pos.pm;pos.eq.dec", False, "? Standard error of pmDE"),
    ("Gmag", "double", "mag", "phot.mag;em.opt", False, "? Synthetic G magnitude"),
    ("BPmag", "double", "mag", "phot.mag;em.opt.B", False, "? Synthetic BP magnitude"),
    ("RPmag", "double", "mag", "phot.mag;em.opt.R", False, "? Synthetic RP magnitude"),
)

HEAD = ('<?xml version="1.0" encoding="utf-8"?>\n'
        '<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">\n'
        '<RESOURCE type="results">\n'
        '<INFO name="QUERY_STATUS" value="OK"/>\n'
        '<INFO name="PROVIDER" value="AstroTwo tests">SYNTHETIC DATA: invented stars, not a real catalogue</INFO>\n')
TAIL = '</TABLEDATA>\n</DATA>\n</TABLE>\n</RESOURCE>\n</VOTABLE>\n'


def field(name, datatype, unit, ucd, ref, description) -> str:
    size = ' arraysize="*"' if datatype == "char" else ""
    unit_attr = f' unit="{unit}"' if unit else ""
    ref_attr = ' ref="coosys_synthetic"' if ref else ""
    return (f'<FIELD{size} datatype="{datatype}" name="{name}"{ref_attr} ucd="{ucd}"{unit_attr}>\n'
            f'<DESCRIPTION>{escape(description)}</DESCRIPTION>\n</FIELD>\n')


def table(name, columns, rows) -> str:
    body = "".join("  <TR>\n" + "".join(f"    <TD>{escape(str(v))}</TD>\n" for v in row) + "  </TR>\n" for row in rows)
    return (f'<TABLE name="{name}">\n' + "".join(columns) + f"<DATA>\n<TABLEDATA>\n{body}" + TAIL)


def stars() -> list[list]:
    rng = np.random.default_rng(SEED)
    rows = []
    for i in range(ROWS):
        r = RADIUS_DEG * 0.95 * np.sqrt(rng.uniform())
        a = rng.uniform(0, 2 * np.pi)
        dec = CENTER[1] + r * np.sin(a)
        ra = CENTER[0] + r * np.cos(a) / np.cos(np.radians(dec))
        g = rng.uniform(9.0, 20.0)
        has_motion = i % 4 != 3  # alcune righe senza moto proprio né parallasse (non disegnabili, D13-12)
        plx = rng.uniform(0.3, 6.0)
        pm_ra, pm_de = rng.normal(20.0, 8.0), rng.normal(-45.0, 8.0)
        errs = rng.uniform(0.01, 0.4, 3)
        rows.append([f"Synthetic star {i + 1:02d}", f"{ra:.11f}", f"{dec:.11f}", 9000000000 + i,
                     f"{errs[0]:.4f}", f"{errs[1]:.4f}",
                     f"{plx:.4f}" if has_motion else "", f"{errs[2]:.4f}" if has_motion else "",
                     f"{pm_ra:.3f}" if has_motion else "", f"{errs[0] * 1.1:.3f}" if has_motion else "",
                     f"{pm_de:.3f}" if has_motion else "", f"{errs[1] * 1.1:.3f}" if has_motion else "",
                     f"{g:.4f}", f"{g + rng.uniform(0.2, 1.2):.4f}", f"{g - rng.uniform(0.2, 0.9):.4f}"])
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    coosys = f'<COOSYS ID="coosys_synthetic" system="ICRS" epoch="{EPOCH}" />\n'
    fields = [field(*c) for c in COLUMNS]
    schema_cols = [field("column_name", "char", None, "Metadata", False, "the column name"),
                   field("ucd", "char", None, "Metadata", False, "the UCD")]
    schema = [(f'"{c[0]}"', c[3]) for c in COLUMNS]
    (OUT / "tap_schema.xml").write_text(HEAD + table("schema", schema_cols, schema), encoding="utf-8")
    (OUT / "top0.xml").write_text(HEAD + coosys + table("top0", fields[1:3], []), encoding="utf-8")
    (OUT / "region.xml").write_text(HEAD + coosys + table("region", fields, stars()), encoding="utf-8")


if __name__ == "__main__":
    main()
