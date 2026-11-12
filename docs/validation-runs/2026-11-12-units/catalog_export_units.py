"""Percorsi veri di AstroTwo: lettura del catalogo → export_table (VOTable 1.4, FITS, ECSV). Senza rete."""

import sys
import re
import warnings
from pathlib import Path
import astropy.units as u
from astropy.table import Table
from astropy.io import fits
from astrotwo.core.catalogs import read_table, confirm_position_columns
from astrotwo.core.vo_protocols import export_table

out = Path(sys.argv[1])
csv = out / "hours.csv"
csv.write_text("ra,dec,mag\n1.5,10.0,12.1\n13.2,-5.0,9.8\n")
cases = {}
for unit in ("hourangle", "deg", "cycle"):
    t = read_table(str(csv))
    cases[f"csv_{unit}"] = confirm_position_columns(t, "ra", "dec", "icrs", unit=u.Unit(unit))
D = Path("tests/analysis/data/profile")
cases["gaia"] = read_table(str(D / "gaia-14433d97cf8b.xml"))
cases["nasa"] = read_table(str(D / "exoplanet-88bd9d6a3469.xml"))
for name, cat in cases.items():
    src = {
        c: (
            str(cat.table[c].unit)
            if cat.table[c].unit is not None
            else f"None[{cat.table[c].meta.get('unit_unrecognized')}]"
        )
        for c in cat.table.colnames
        if cat.table[c].unit is not None or cat.table[c].meta.get("unit_unrecognized")
    }
    print(f"== {name}: unità in memoria {src}")
    for fmt, ext in (("votable", "xml"), ("fits", "fits"), ("ecsv", "ecsv")):
        p = out / f"{name}.{ext}"
        p.unlink(missing_ok=True)
        try:
            export_table(cat, p, fmt)
        except Exception as e:
            print(f"   {fmt}: ERRORE {type(e).__name__}: {str(e)[:150]}")
            continue
        if fmt == "votable":
            txt = dict(re.findall(r'<FIELD[^>]*?name="([^"]+)"[^>]*?unit="([^"]*)"', p.read_text()))
        elif fmt == "fits":
            h = fits.getheader(p, 1)
            txt = {h[f"TTYPE{i}"]: h.get(f"TUNIT{i}") for i in range(1, h["TFIELDS"] + 1) if h.get(f"TUNIT{i}")}
        else:
            txt = dict(re.findall(r"name: (\S+), unit: ([^,}]+)", p.read_text()))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Table.read(p, format={"votable": "votable", "fits": "fits", "ecsv": "ascii.ecsv"}[fmt])
        ws = sorted({f"{x.category.__name__}: {str(x.message)[:90]}" for x in w})
        print(f"   {fmt}: unità scritte {txt}; avvisi astropy in lettura: {ws or 'nessuno'}")
