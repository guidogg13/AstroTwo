"""Sprint D11 (b): ECSV e VOTable del profilo di TRAPPIST-1 dalle risposte registrate dei test, senza rete."""

import json
import os
import warnings
from pathlib import Path
import astropy.units as u
import numpy as np
from astropy.table import Table
from astropy.io.votable import parse
from tests.analysis.profile_fakes import services  # noqa: F401
from tests.analysis.test_profile_export import session_with_export, profile, values_of, export
from astrotwo.core.commands import unit_from_json

OUT = Path(os.environ["D11_OUT"])


def test_trappist_files(cache, services):  # noqa: F811
    session = session_with_export(cache)
    number, result = profile(session, {"name": "TRAPPIST-1"})
    assert result.status == "ok", result.error
    (OUT / "TRAPPIST_1-result.json").write_text(json.dumps(values_of(result), indent=1, ensure_ascii=False))
    for fmt, name in (("ecsv", "TRAPPIST_1-profile.ecsv"), ("sed_votable", "TRAPPIST_1-sed.xml")):
        p = OUT / name
        p.unlink(missing_ok=True)
        w = export(session, [number], fmt, p)
        assert w.status == "ok", w.error
    report = {}
    # ECSV: lettura con ogni avviso trasformato in errore (UnitsWarning compresi)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ecsv = Table.read(OUT / "TRAPPIST_1-profile.ecsv", format="ascii.ecsv")
    sections = values_of(result)["sections"]
    expected = [v for s in sections for v in s["values"]]
    units_ok, units = 0, {}
    for row, v in zip(ecsv, expected, strict=True):
        val = v["value"]
        if isinstance(val, dict) and "unit" in val:
            text = "" if np.ma.is_masked(row["unit"]) else str(row["unit"])
            assert text == (val["unit"] or "")
            if text:
                with warnings.catch_warnings():
                    warnings.simplefilter("error")
                    a = unit_from_json(text)
                    b = u.Unit(text)  # lettore generico di astropy, senza il codice di AstroTwo
                assert a == b
                units[text] = units.get(text, 0) + 1
                units_ok += 1
    report["ecsv_rows"] = len(ecsv)
    report["ecsv_rows_with_unit"] = units_ok
    report["ecsv_units"] = units
    report["ecsv_column_units"] = {c: str(ecsv[c].unit) for c in ecsv.colnames if ecsv[c].unit is not None}
    # VOTable della SED: parse con verify="exception" (ogni avviso VOTable è un errore) e avvisi come errori
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        vot = parse(str(OUT / "TRAPPIST_1-sed.xml"), verify="exception")
        sed = vot.get_first_table().to_table()
    want = {
        "ra": u.deg,
        "dec": u.deg,
        "wavelength": u.um,
        "flux_nu": u.Jy,
        "flux_nu_error": u.Jy,
        "magnitude": u.mag,
        "magnitude_error": u.mag,
    }
    for c, unit in want.items():
        assert sed[c].unit == unit, (c, sed[c].unit)
    assert [c for c in sed.colnames if sed[c].unit is not None] == list(want)
    report["votable_version"] = vot.version
    report["votable_rows"] = len(sed)
    report["votable_units"] = {
        f.name: f.unit.to_string("vounit") for f in vot.get_first_table().fields if f.unit is not None
    }
    (OUT / "check.json").write_text(json.dumps(report, indent=1))
