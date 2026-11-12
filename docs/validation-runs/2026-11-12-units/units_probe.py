"""Sonda delle unità (sprint D11): testo scritto per ogni formato e validità. Senza rete."""

import io
import json
import sys
import warnings
from pathlib import Path
import astropy.units as u
from astropy.table import Table
from astropy.io import fits
from astropy.io.votable import from_table, parse_single_table
from astrotwo.core.commands import unit_json, unit_text
from astrotwo.core.catalogs import _standard_unit

out = Path(sys.argv[1])
CANDIDATES = [
    # unità dei risultati misurati (validation-runs 2026-11-11)
    "AU",
    "Jy",
    "K",
    "arcmin",
    "arcsec",
    "d",
    "deg",
    "earthMass",
    "earthRad",
    "electron/s",
    "km/s",
    "mag",
    "mas",
    "mas/yr",
    "pc",
    "s",
    "um",
    "yr",
    # citate dal proprietario e negli effetti di D05-6
    "hourangle",
    "cycle",
    "%",
    "AB",
    "GsolMass",
    "Gcount",
    "jupiterMass",
    "jupiterRad",
    # altre delle colonne dei VOTable registrati nei test, e comuni nei cataloghi
    "count",
    "pix",
    "solMass",
    "solRad",
    "solLum",
    "mJy",
    "GHz",
    "nm",
    "Angstrom",
    "dex",
    "erg/(s cm2)",
    "W/(m2 Hz)",
    "rad",
    "h",
    "min",
    "ct/s",
    "mag/arcsec2",
]


def strict(text, fmt):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            v = u.Unit(text, format=fmt)
        return not isinstance(v, u.UnrecognizedUnit), v
    except Exception as e:
        return False, type(e).__name__


rows = []
for name in CANDIDATES:
    unit = u.Unit(name)
    r = {"unit": name, "repr": repr(unit)}
    r["unit_json"] = unit_json(unit)
    r["unit_text"] = unit_text(unit)
    for k in ("unit_json", "unit_text"):
        for fmt in ("vounit", "fits"):
            ok, v = strict(r[k], fmt)
            r[f"{k}_astropy_{fmt}"] = ok and v == unit and v.to_string("generic") == unit.to_string("generic")
    r["catalog_ingest"] = _standard_unit(unit.to_string()) is not None  # 11 _normalize_units: entra come unità?
    t = Table({"x": [1.0]})
    t["x"].unit = unit
    # VOTable 1.4 come _write_votable_file (votable_from_table + version 1.4)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        vot = from_table(t)
        vot.version = "1.4"
        b = io.BytesIO()
        vot.to_xml(b)
    xml = b.getvalue().decode()
    import re

    m = re.search(r'<FIELD[^>]*unit="([^"]*)"', xml)
    r["votable_text"] = m.group(1) if m else None
    r["votable_write_warn"] = [str(x.message)[:100] for x in w]
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        back = parse_single_table(io.BytesIO(b.getvalue())).to_table()
    r["votable_read_warn"] = [f"{x.category.__name__}: {str(x.message)[:100]}" for x in w]
    r["votable_roundtrip"] = back["x"].unit == unit if back["x"].unit is not None else False
    p = out / f"vot_{len(rows)}.xml"
    p.write_bytes(b.getvalue())
    # FITS come _write_fits_file (warning silenziati nel codice: qui li registriamo)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            hdu = fits.table_to_hdu(t)
            err = None
        except Exception as e:
            hdu = None
            err = f"{type(e).__name__}"
    r["fits_error"] = err
    r["fits_text"] = hdu.header.get("TUNIT1") if hdu else None
    r["fits_write_warn"] = [str(x.message)[:160] for x in w]
    r["fits_read_warn"] = []
    r["fits_roundtrip"] = False
    if hdu is not None:
        pf = out / f"fits_{len(rows)}.fits"
        fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(pf, overwrite=True)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            fb = Table.read(pf)
        r["fits_read_warn"] = [f"{x.category.__name__}: {str(x.message)[:100]}" for x in w]
        r["fits_roundtrip"] = fb["x"].unit == unit if fb["x"].unit is not None else False
    # ECSV
    pe = out / f"ecsv_{len(rows)}.ecsv"
    t.write(pe, format="ascii.ecsv", overwrite=True)
    r["ecsv_text"] = [line for line in pe.read_text().splitlines() if "unit:" in line][0].split("unit:")[1].strip()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        eb = Table.read(pe, format="ascii.ecsv")
    r["ecsv_read_warn"] = [f"{x.category.__name__}: {str(x.message)[:100]}" for x in w]
    r["ecsv_roundtrip"] = eb["x"].unit == unit
    rows.append(r)
json.dump(rows, open(out / "probe.json", "w"), indent=1)
for r in rows:
    print(
        f"{r['unit']:12} json={r['unit_json']!s:14} text={r['unit_text']!s:14} JvoU={int(r['unit_json_astropy_vounit'])} Jfits={int(r['unit_json_astropy_fits'])} "
        f"VOT={r['votable_text']!s:14} rt={int(r['votable_roundtrip'])} rw={len(r['votable_read_warn'])} FITS={(r['fits_text'] or r['fits_error'])!s:14} ww={len(r['fits_write_warn'])} rt={int(r['fits_roundtrip'])} ECSV={r['ecsv_text']:14} rt={int(r['ecsv_roundtrip'])} ingest={int(r['catalog_ingest'])}"
    )
