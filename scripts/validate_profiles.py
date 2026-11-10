# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Validation measurements of the object profile (docs/validation.md): network script, run by hand, never in the suite.

For each reference object it does two independent things:

1. **AstroTwo side**: runs the real ``object.profile`` command (the one the app records) with an empty cache, and
   writes the result JSON and the ECSV export.
2. **Reference side**: queries SIMBAD, the Gaia archive, VizieR and the NASA Exoplanet Archive **directly**, with
   plain HTTP (``urllib``) and Astropy's VOTable reader. No AstroTwo code is used on this side.

Then it compares each AstroTwo value with the reference value, with the tolerances written in docs/validation.md
§2.1 **before** the first measurement, and writes ``results.json`` and ``results.md`` (the rows of §5).

A service that does not answer gives rows ``not measured`` with the server, the time and the error: those rows
stay to be redone. Usage::

    uv run python scripts/validate_profiles.py [--out docs/validation-runs/<date>] [OBJECT ...]

**Empty text** (decision D25-24 of the project owner, 2026-11-10): an empty text returned by a source (``''`` or
only spaces) is a **value declared absent** by the source, never a value; on both sides it compares like a missing
value. ``--recompare DIR`` applies this rule, **without network**, to the rows of a run already saved in ``DIR``
(``results.json``) and writes ``results-recompared.json`` and ``.md`` next to it; the saved files stay unchanged.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import io
import json
import math
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

OBJECTS = ("51 Peg", "Vega", "eta Tau", "TRAPPIST-1", "Barnard's Star", "3C 273", "M 13")

#: Reference servers, in order: the first one that answers is used and written in the row.
SIMBAD = ("https://simbad.cds.unistra.fr/simbad/sim-tap/sync", "https://simbad.harvard.edu/simbad/sim-tap/sync")
GAIA = ("https://gea.esac.esa.int/tap-server/tap/sync",)
VIZIER = ("https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync",)
EXOPLANETS = ("https://exoplanetarchive.ipac.caltech.edu/TAP/sync",)
TIMEOUT = 60

#: Tolerances of docs/validation.md §2.1 (fixed on 2026-11-10, before the measurements)
TOL_DISTANCE_PARALLAX = 1e-12  # relative
TOL_SED_FLUX = 1e-10  # relative
TOL_SEPARATION_ARCSEC = 1e-6

#: SIMBAD ``basic`` column for each AstroTwo quantity read from SIMBAD (25 §3.4.1, §3.4.3)
SIMBAD_COLUMNS = {"main_id": "main_id", "otype": "otype", "sp_type": "sp_type", "nbref": "nbref", "ra": "ra",
                  "dec": "dec", "coo_err_maj": "coo_err_maj", "coo_err_min": "coo_err_min",
                  "coo_err_angle": "coo_err_angle", "coo_qual": "coo_qual", "parallax": "plx_value",
                  "pmra": "pmra", "pmdec": "pmdec", "pm_err_maj": "pm_err_maj", "pm_err_min": "pm_err_min",
                  "pm_err_angle": "pm_err_angle", "radial_velocity": "rvz_radvel"}
SIMBAD_ERRORS = {"parallax": "plx_err", "radial_velocity": "rvz_err"}
GAIA_SOURCE_COLUMNS = ("source_id", "ref_epoch", "ra", "ra_error", "dec", "dec_error", "parallax", "parallax_error",
                       "pmra", "pmra_error", "pmdec", "pmdec_error", "radial_velocity", "radial_velocity_error",
                       "ruwe", "astrometric_params_solved", "duplicated_source", "ipd_frac_multi_peak",
                       "phot_g_mean_mag", "phot_bp_mean_mag", "phot_rp_mean_mag", "phot_g_mean_flux",
                       "phot_g_mean_flux_error", "phot_bp_mean_flux", "phot_bp_mean_flux_error", "phot_rp_mean_flux",
                       "phot_rp_mean_flux_error")
GAIA_BANDS = {"G": "g", "BP": "bp", "RP": "rp"}
BJ_COLUMNS = {"distance_geo": ("r_med_geo", "r_lo_geo", "r_hi_geo"),
              "distance_photogeo": ("r_med_photogeo", "r_lo_photogeo", "r_hi_photogeo")}
#: VizieR tables of 2MASS and AllWISE: (table, designation column, {band: (magnitude, error)})
VIZIER_TABLES = {"2MASS": ("II/246/out", "2MASS", {"J": ("Jmag", "e_Jmag"), "H": ("Hmag", "e_Hmag"),
                                                    "Ks": ("Kmag", "e_Kmag")}),
                 "AllWISE": ("II/328/allwise", "AllWISE", {"W1": ("W1mag", "e_W1mag"), "W2": ("W2mag", "e_W2mag"),
                                                           "W3": ("W3mag", "e_W3mag"), "W4": ("W4mag", "e_W4mag")})}
AREAS = {"identity": "Identity", "astrometry": "Astrometry", "photometry": "Photometry", "planets": "Planets",
         "images": "Images"}
PLANET_COLUMNS = {"period": "pl_orbper", "semi_major_axis": "pl_orbsmax", "eccentricity": "pl_orbeccen",
                  "radius": "pl_rade", "mass": "pl_bmasse", "equilibrium_temperature": "pl_eqt"}


# =============================================================================
# Reference side: direct TAP queries (no AstroTwo code)


class ServiceDown(Exception):
    def __init__(self, servers, detail):
        super().__init__(detail)
        self.servers, self.detail = servers, detail


def now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def tap(servers: tuple[str, ...], adql: str):
    """First server that answers: (astropy Table with native column types, server URL, UTC time)."""
    from astropy.io.votable import parse_single_table

    errors = []
    for url in servers:
        data = urllib.parse.urlencode({"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable",
                                       "QUERY": adql}).encode()
        when = now()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=TIMEOUT) as response:
                body = response.read()
            return parse_single_table(io.BytesIO(body)).to_table(use_names_over_ids=True), url, when
        except Exception as exc:  # noqa: BLE001 - every failure is written in the row, never hidden
            errors.append(f"{url} at {when}: {type(exc).__name__}: {exc}")
    raise ServiceDown(servers, "; ".join(errors))


def cell(table, column):
    """Value of the first row with its native type; ``None`` when masked or absent."""
    if table is None or len(table) == 0 or column not in table.colnames:
        return None
    value = table[column][0]
    if np.ma.is_masked(value):
        return None
    if isinstance(value, bytes):
        value = value.decode()
    return value.item() if isinstance(value, np.generic) and not isinstance(value, np.floating) else value


def reference(name: str, astro: dict) -> dict:
    """All reference answers for one object; each part records server, time and query, or why it is missing."""
    ref: dict = {}
    esc = name.replace("'", "''")
    simbad_q = ("SELECT b.main_id, b.otype, b.sp_type, b.nbref, b.ra, b.dec, b.coo_err_maj, b.coo_err_min, "
                "b.coo_err_angle, b.coo_qual, b.plx_value, b.plx_err, b.pmra, b.pmdec, b.pm_err_maj, b.pm_err_min, "
                "b.pm_err_angle, b.rvz_radvel, b.rvz_err FROM basic AS b JOIN ident AS i ON i.oidref = b.oid "
                f"WHERE i.id = '{esc}'")
    ref["simbad"] = run(SIMBAD, simbad_q)
    ids_q = ("SELECT i2.id FROM ident AS i1 JOIN ident AS i2 ON i2.oidref = i1.oidref "
             f"WHERE i1.id = '{esc}'")
    ref["simbad_ids"] = run(SIMBAD, ids_q)
    ids = [] if ref["simbad_ids"]["table"] is None else [str(v) for v in ref["simbad_ids"]["table"]["id"]]
    gaia_id = next((i.split()[-1] for i in ids if i.startswith("Gaia DR3 ")), None)
    ref["gaia_dr3_from_simbad"] = gaia_id
    if gaia_id is not None:
        ref["gaia"] = run(GAIA, f"SELECT {', '.join(GAIA_SOURCE_COLUMNS)} FROM gaiadr3.gaia_source "
                                f"WHERE source_id = {gaia_id}")
        ref["bailer_jones"] = run(GAIA, "SELECT source_id, r_med_geo, r_lo_geo, r_hi_geo, r_med_photogeo, "
                                        "r_lo_photogeo, r_hi_photogeo, flag FROM external.gaiaedr3_distance "
                                        f"WHERE source_id = {gaia_id}")
    # SIMBAD writes «2MASS J23021732+2058352» (VizieR II/246: «23021732+2058352») and, for AllWISE,
    # «WISEA J230217.30+205835.0» (VizieR II/328: «J230217.30+205835.0»).
    for catalog, (table, column, _bands) in VIZIER_TABLES.items():
        prefix = "2MASS J" if catalog == "2MASS" else "WISEA J"
        found = next((i for i in ids if i.startswith(prefix)), None)
        if found is None:
            continue
        designation = found[len(prefix):] if catalog == "2MASS" else found[len(prefix) - 1:]
        ref[catalog] = run(VIZIER, f'SELECT * FROM "{table}" WHERE "{column}" = \'{designation}\'')
        ref[catalog]["simbad_identifier"] = found
    host = None
    for section in astro.get("sections") or []:
        if section.get("name") == "planets":
            host = (section.get("details") or {}).get("host")  # testo: l'ospite trovato (25 §3.13)
            host = host.get("identifier") if isinstance(host, dict) else host
    planets = [v for s in astro.get("sections") or [] if s.get("name") == "planets" for v in s.get("values") or []]
    if planets or host:
        hostname = host or name
        ref["planets"] = run(EXOPLANETS, "SELECT pl_name, hostname, " + ", ".join(
            f"{c}, {c}err1, {c}err2" for c in PLANET_COLUMNS.values()) +
            f" FROM pscomppars WHERE hostname = '{hostname.replace(chr(39), chr(39) * 2)}'")
    return ref


def run(servers, adql) -> dict:
    try:
        table, server, when = tap(servers, adql)
        return {"table": table, "server": server, "retrieved_at": when, "query": adql, "error": None}
    except ServiceDown as exc:
        return {"table": None, "server": None, "retrieved_at": now(), "query": adql, "error": exc.detail}


# =============================================================================
# AstroTwo side: the recorded command object.profile, then the ECSV export


def without_images(data):
    """The result without the PNG images (thumbnails, SED plot), written as ``"<png omitted>"``: values,
    provenance, warnings and errors stay as they are."""
    if isinstance(data, dict):
        return {k: ("<png omitted>" if k in ("png", "plot_png") and isinstance(v, str) else without_images(v))
                for k, v in data.items()}
    if isinstance(data, list):
        return [without_images(v) for v in data]
    return data


def astrotwo_profile(name: str, out: Path) -> dict:
    from astrotwo.analysis.object_profile import command_specs
    from astrotwo.analysis.profile_export import export_profile, merge_profile_results
    from astrotwo.core.cache import SharedCache
    from astrotwo.core.commands import Command, RequestedBy, Session, default_registry

    stem = "".join(c if c.isalnum() else "_" for c in name).strip("_")
    with tempfile.TemporaryDirectory() as tmp, SharedCache(Path(tmp) / "cache") as cache:
        registry = default_registry(cache=cache)
        for spec in command_specs():
            registry.register(spec)
        session = Session(registry)
        result = session.run(Command("object.profile", 1, {"name": name}, RequestedBy("menu")))
        number = session.history.entries[-1].number
        values = json.loads(json.dumps(result.values))
        record = {"status": result.status, "error": None if result.error is None else str(result.error),
                  "values": without_images(values)}
        (out / f"{stem}-result.json").write_text(json.dumps(record, indent=1, ensure_ascii=False))
        if values.get("sections"):
            export_profile(merge_profile_results([(number, values)]), out / f"{stem}-profile.ecsv", "ecsv")
        return values


# =============================================================================
# Comparison (docs/validation.md §2.1)


def number(value):
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def unit_of(value):
    return value.get("unit") if isinstance(value, dict) else None


def declared_absent(value) -> bool:
    """D25-24: no value, or an empty text (``''`` or only spaces), is a value declared absent by the source."""
    return value is None or (isinstance(value, str) and not value.strip())


def same_read(astro_value, ref_value, ref_dtype) -> tuple[bool, str]:
    """Read value: identical; ``float32`` columns compared after rounding both values to ``float32``; an empty text
    on either side is a value declared absent (D25-24), never a value."""
    a = number(astro_value)
    if declared_absent(ref_value) or declared_absent(a):
        both = declared_absent(a) and declared_absent(ref_value)
        return both, "both empty" if both else "one is empty"
    if isinstance(ref_value, str) or isinstance(a, str):
        return str(a).strip() == str(ref_value).strip(), "text"
    if ref_dtype is not None and np.dtype(ref_dtype) == np.float32:
        return bool(np.float32(a) == np.float32(ref_value)), f"float32: Δ = {float(a) - float(ref_value)!r}"
    diff = float(a) - float(ref_value)
    return diff == 0 or (a == ref_value), f"Δ = {diff!r}"


def english(message: dict) -> str:
    """AstroTwo error as ``code: text``, text in English from the message catalog (code and ``params``)."""
    from astrotwo.messages_catalog import message_text

    code = str(message.get("code") or "")
    return f"{code}: {message_text(code, message.get('params') or {}, 'en', text=message.get('text'))}"


#: Rule of the owner (2026-11-10): while the CDS is down, SIMBAD is compared with the Harvard mirror and every such
#: row says so; these rows are repeated against the CDS when it answers again.
HARVARD_NOTE = "reference: Harvard mirror, to be repeated against CDS"


def row(obj, area, quantity, astro, ref, server, query, when, diff, outcome, note=""):
    if server and "harvard" in server and HARVARD_NOTE not in note:
        note = f"{note}; {HARVARD_NOTE}" if note else HARVARD_NOTE
    return {"object": obj, "area": area, "quantity": quantity, "astrotwo": astro, "reference": ref, "server": server,
            "query": query, "retrieved_at": when, "difference": diff, "outcome": outcome, "note": note}


def not_measured(obj, area, quantity, astro, part, why=None):
    return row(obj, area, quantity, astro, None, None, part.get("query") if part else None,
               part.get("retrieved_at") if part else now(), None, "not measured",
               why or (part or {}).get("error") or "no reference answer")


def show(value):
    v = number(value)
    unit = unit_of(value)
    if isinstance(v, float):
        v = repr(v)
    return f"{v} {unit}".strip() if unit else ("" if v is None else str(v))


def compare(name: str, astro: dict, ref: dict) -> list[dict]:
    out = []
    resolved = astro.get("resolved") or {}
    simbad = ref.get("simbad") or {}
    # Identity: SIMBAD main identifier
    if resolved.get("main_id") is None and resolved.get("simbad_error"):
        err = resolved["simbad_error"]
        out.append(row(name, "Identity", "main_id", None, None, None, None, now(), None, "not measured",
                       f"AstroTwo side: SIMBAD did not answer ({english(err)})"))
    elif simbad.get("table") is not None and len(simbad["table"]):
        ok, how = same_read(resolved.get("main_id"), cell(simbad["table"], "main_id"), None)
        out.append(row(name, "Identity", "main_id", resolved.get("main_id"), cell(simbad["table"], "main_id"),
                       simbad["server"], simbad["query"], simbad["retrieved_at"], how, "pass" if ok else "fail"))
    elif simbad.get("error"):
        out.append(not_measured(name, "Identity", "main_id", resolved.get("main_id"), simbad))
    for section in astro.get("sections") or []:
        for v in section.get("values") or []:
            out.extend(compare_value(name, section, v, astro, ref))
        out.extend(absent_rows(name, section, ref))
        for err in section.get("errors") or []:  # values AstroTwo could not read: the rows stay to be redone
            server = (err.get("params") or {}).get("url") or ""
            out.append(row(name, AREAS.get(section.get("name"), section.get("name")),
                           f"section {section.get('name')} ({err.get('catalog') or 'all values'})", None, None,
                           None, None, now(), None, "not measured",
                           f"AstroTwo side: {english(err)}" + (f" [{server}]" if server and server not in
                                                               english(err) else "")))
    return out


def absent_rows(name, section, ref) -> list[dict]:
    """Values the profile does not write because the source declares them absent (``details["absent"]``, D25-24):
    pass when the reference is empty or missing too, fail when the reference has a value."""
    rows = []
    area = AREAS.get(section.get("name"), section.get("name"))
    for item in (section.get("details") or {}).get("absent") or []:
        quantity = item.get("quantity")
        if section.get("name") != "identity" or quantity not in SIMBAD_COLUMNS:
            continue
        part = ref.get("simbad") or {}
        shown = f"(not written: {item.get('note')})"
        if part.get("table") is None or not len(part["table"]):
            rows.append(not_measured(name, area, f"{quantity} (SIMBAD)", shown, part))
            continue
        ref_value = cell(part["table"], SIMBAD_COLUMNS[quantity])
        ok = declared_absent(ref_value)
        rows.append(row(name, area, f"{quantity} (SIMBAD)", shown, repr(ref_value), part["server"], part["query"],
                        part["retrieved_at"], "both empty" if ok else "one is empty", "pass" if ok else "fail",
                        "declared absent (D25-24)"))
    return rows


def recompare(rows: list[dict]) -> list[dict]:
    """Offline recomparison of saved rows with the empty-text rule (D25-24): only the rows that failed because one
    side was empty change; every other row stays as measured. The reference is read back from its saved ``repr``."""
    out = []
    for r in rows:
        if r.get("outcome") != "fail" or r.get("difference") != "one is empty":
            out.append(r)
            continue
        text = str(r.get("reference") or "")
        try:
            ref_value = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            out.append(r)
            continue
        astro = r.get("astrotwo")
        ok, how = same_read(None if declared_absent(astro) else astro, ref_value, None)
        note = "; ".join(x for x in (r.get("note"), "recomputed offline with the empty-text rule (D25-24)") if x)
        out.append({**r, "difference": how, "outcome": "pass" if ok else "fail", "note": note})
    return out


def compare_value(name, section, v, astro, ref) -> list[dict]:
    prov = v.get("provenance") or {}
    table, quantity = prov.get("table"), v.get("quantity")
    area = AREAS.get(section.get("name"), section.get("name"))
    rows = []
    if table == "basic" and quantity in SIMBAD_COLUMNS:
        part = ref.get("simbad") or {}
        if part.get("table") is None or not len(part["table"]):
            return [not_measured(name, area, f"{quantity} (SIMBAD)", show(v["value"]), part)]
        rows.append(read_row(name, area, f"{quantity} (SIMBAD)", v["value"], part, SIMBAD_COLUMNS[quantity]))
        if quantity in SIMBAD_ERRORS and v.get("error") is not None:
            rows.append(read_row(name, area, f"{quantity} error (SIMBAD)", v["error"], part, SIMBAD_ERRORS[quantity]))
    elif table == "gaiadr3.gaia_source":
        part = ref.get("gaia") or {}
        column, error_column = gaia_column(quantity)
        if column is None:
            return []
        if part.get("table") is None or not len(part["table"]):
            return [not_measured(name, area, f"{quantity} (Gaia DR3)", show(v["value"]), part,
                                 None if ref.get("gaia_dr3_from_simbad") else "no Gaia DR3 identifier in SIMBAD")]
        if v.get("method") == "computed":
            rows.append(flux_row(name, area, quantity, v, astro, part))
        else:
            rows.append(read_row(name, area, f"{quantity} (Gaia DR3)", v["value"], part, column))
            if error_column and v.get("error") is not None:
                rows.append(read_row(name, area, f"{quantity} error (Gaia DR3)", v["error"], part, error_column))
    elif table == "external.gaiaedr3_distance" and quantity in BJ_COLUMNS:
        part = ref.get("bailer_jones") or {}
        med, lo, hi = BJ_COLUMNS[quantity]
        if part.get("table") is None or not len(part["table"]):
            return [not_measured(name, area, quantity, show(v["value"]), part)]
        rows.append(read_row(name, "Distance", f"{quantity} (Bailer-Jones)", v["value"], part, med))
        if v.get("interval"):
            rows.append(read_row(name, "Distance", f"{quantity} 16th pct", v["interval"][0], part, lo))
            rows.append(read_row(name, "Distance", f"{quantity} 84th pct", v["interval"][1], part, hi))
    elif quantity == "distance_parallax":
        rows.append(distance_row(name, v, ref))
    elif table in ("fp_psc", "allwise_p3as_psd"):
        catalog = "2MASS" if table == "fp_psc" else "AllWISE"
        part = ref.get(catalog)
        band = quantity.split()[1] if len(quantity.split()) > 1 else None
        if v.get("method") == "computed":
            rows.append(flux_row(name, area, quantity, v, astro, None))
        elif quantity.endswith(" magnitude"):
            if part is None or part.get("table") is None or not len(part["table"]):
                rows.append(not_measured(name, area, f"{quantity} (VizieR {VIZIER_TABLES[catalog][0]})",
                                         show(v["value"]), part, None if part else
                                         f"no {catalog} designation in SIMBAD"))
            else:
                mag, err = VIZIER_TABLES[catalog][2][band]
                rows.append(read_row(name, area, f"{quantity} (VizieR)", v["value"], part, mag))
                if v.get("error") is not None:
                    rows.append(read_row(name, area, f"{quantity} error (VizieR)", v["error"], part, err))
    elif table == "pscomppars":
        rows.extend(planet_rows(name, v, ref))
    return rows


def gaia_column(quantity):
    if quantity in GAIA_SOURCE_COLUMNS:
        error = f"{quantity}_error" if f"{quantity}_error" in GAIA_SOURCE_COLUMNS else None
        return quantity, error
    parts = quantity.split()
    if len(parts) == 4 and parts[:2] == ["Gaia", "DR3"] and parts[2] in GAIA_BANDS:
        band = GAIA_BANDS[parts[2]]
        return {"magnitude": (f"phot_{band}_mean_mag", None),
                "count_rate": (f"phot_{band}_mean_flux", f"phot_{band}_mean_flux_error"),
                "flux_nu": (f"phot_{band}_mean_flux", None)}.get(parts[3], (None, None))
    return None, None


def read_row(name, area, quantity, astro_value, part, column):
    table = part["table"]
    ref_value = cell(table, column)
    dtype = table[column].dtype if column in table.colnames else None
    ok, how = same_read(astro_value, ref_value, dtype)
    ref_unit = str(table[column].unit) if column in table.colnames and table[column].unit is not None else ""
    unit_ok = True
    if unit_of(astro_value) and ref_unit:
        from astropy import units as u
        unit_ok = u.Unit(unit_of(astro_value)) == u.Unit(ref_unit, parse_strict="silent")
    shown_ref = ref_value.item() if isinstance(ref_value, np.generic) else ref_value
    return row(name, area, quantity, show(astro_value), f"{shown_ref!r} {ref_unit}".strip(), part["server"],
               part["query"], part["retrieved_at"], how, "pass" if ok and unit_ok else "fail",
               "" if unit_ok else f"unit {unit_of(astro_value)} vs {ref_unit}")


def distance_row(name, v, ref):
    """1/parallax: AstroTwo value against 1000/parallax[mas] pc from the reference parallax (§2.1)."""
    source = (v.get("provenance") or {}).get("table")
    part = ref.get("gaia") if source == "gaiadr3.gaia_source" else ref.get("simbad")
    column = "parallax" if source == "gaiadr3.gaia_source" else "plx_value"
    if not part or part.get("table") is None or not len(part["table"]):
        return not_measured(name, "Distance", "distance_parallax", show(v["value"]), part)
    plx = float(cell(part["table"], column))
    expected = 1000.0 / plx
    got = float(number(v["value"]))
    rel = abs(got - expected) / abs(expected)
    ok = rel <= TOL_DISTANCE_PARALLAX and unit_of(v["value"]) == "pc"
    return row(name, "Distance", "distance_parallax (1/parallax)", show(v["value"]), f"{expected!r} pc",
               part["server"], part["query"], part["retrieved_at"], f"relative {rel:.3g}", "pass" if ok else "fail")


def zero_point(astro, key):
    for section in astro.get("sections") or []:
        for zp in (section.get("details") or {}).get("zero_points") or []:
            if zp.get("key") == key:
                return zp
    return None


def flux_row(name, area, quantity, v, astro, gaia_part):
    """Fν from a magnitude or a count rate, recomputed independently with the zero point AstroTwo declares."""
    label = quantity[: -len(" flux_nu")]
    point = next((p for s in astro.get("sections") or [] for p in (s.get("details") or {}).get("points") or []
                  if f"{p.get('catalog')} {p.get('band')}" == label or p.get("label") == label), None)
    zp_key = ((point or {}).get("zero_point") or {}).get("key") if isinstance((point or {}).get("zero_point"), dict) \
        else (point or {}).get("zero_point")
    zp = zero_point(astro, zp_key) if zp_key else None
    got = float(number(v["value"]))
    if zp is None:
        return row(name, area, f"{quantity} (recomputed)", show(v["value"]), None, None, None, now(), None,
                   "not measured", f"zero point of {label} not found in the result")
    zp_value = float(number(zp["value"]))
    if label.startswith("Gaia DR3"):
        band = GAIA_BANDS[label.split()[2]]
        if gaia_part is None or gaia_part.get("table") is None:
            return not_measured(name, area, f"{quantity} (recomputed)", show(v["value"]), gaia_part)
        rate = float(cell(gaia_part["table"], f"phot_{band}_mean_flux"))
        m_ab = -2.5 * math.log10(rate) + zp_value
        expected = 1e23 * 10.0 ** (-0.4 * 48.60) * 10.0 ** (-0.4 * m_ab)  # Jy, AB definition
        source = f"Gaia count rate (archive) and ZP_AB {zp_value!r} mag declared by AstroTwo"
        server, query, when = gaia_part["server"], gaia_part["query"], gaia_part["retrieved_at"]
    else:
        magnitude = number(point.get("magnitude")) if point else None
        if magnitude is None:
            return row(name, area, f"{quantity} (recomputed)", show(v["value"]), None, None, None, now(), None,
                       "not measured", "magnitude not in the result")
        expected = zp_value * 10.0 ** (-0.4 * float(magnitude))
        source = f"magnitude read by AstroTwo and F0 {zp_value!r} Jy declared by AstroTwo (conversion only)"
        server, query, when = None, None, now()
    rel = abs(got - expected) / abs(expected)
    return row(name, area, f"{quantity} (recomputed)", show(v["value"]), f"{expected!r} Jy", server, query, when,
               f"relative {rel:.3g}", "pass" if rel <= TOL_SED_FLUX and unit_of(v["value"]) == "Jy" else "fail",
               source)


def planet_rows(name, v, ref):
    part = ref.get("planets") or {}
    quantity = v.get("quantity") or ""
    planet, _, key = quantity.rpartition(" ")
    if key not in PLANET_COLUMNS:
        return []
    if part.get("table") is None:
        return [not_measured(name, "Planets", quantity, show(v["value"]), part)]
    table = part["table"]
    match = [i for i in range(len(table)) if str(table["pl_name"][i]) == planet]
    if not match:
        return [row(name, "Planets", quantity, show(v["value"]), None, part["server"], part["query"],
                    part["retrieved_at"], None, "fail", "planet not in the reference answer")]
    sub = table[match[0]:match[0] + 1]
    return [read_row(name, "Planets", quantity, v["value"], {**part, "table": sub}, PLANET_COLUMNS[key])]


# =============================================================================


def markdown(rows: list[dict]) -> str:
    lines = ["| Object | Area | Value | AstroTwo | Reference | Server and date | Difference | Outcome |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        server = f"{urllib.parse.urlparse(r['server']).hostname} · {r['retrieved_at']}" if r["server"] else \
            f"— · {r['retrieved_at']}"
        shown_note = r["note"] and (r["outcome"] != "pass" or HARVARD_NOTE in r["note"])
        outcome = r["outcome"] + (f" ({r['note']})" if shown_note else "")
        lines.append("| " + " | ".join(str(x).replace("|", "\\|") for x in (
            r["object"], r["area"], r["quantity"], r["astrotwo"], r["reference"] or "—", server,
            r["difference"] or "—", outcome)) + " |")
    return "\n".join(lines) + "\n"


def recompare_run(run: Path) -> int:
    """``--recompare``: reads ``run/results.json``, writes ``results-recompared.json`` and ``.md``; no network."""
    saved = json.loads((run / "results.json").read_text())
    rows = recompare(saved["rows"])
    changed = [(a["object"], a["quantity"], a["outcome"], b["outcome"]) for a, b in zip(saved["rows"], rows,
                                                                                       strict=True) if a != b]
    meta = {**saved["meta"], "recompared": {"date": now(), "rule": "D25-24: empty text = value declared absent",
                                            "changed": [list(c) for c in changed]}}
    (run / "results-recompared.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=1,
                                                            ensure_ascii=False, default=str))
    (run / "results-recompared.md").write_text(markdown(rows))
    for c in changed:
        print(f"{c[0]} · {c[1]}: {c[2]} → {c[3]}", file=sys.stderr)
    total = {k: sum(r["outcome"] == k for r in rows) for k in ("pass", "fail", "not measured")}
    print(f"total: {total}; written {run / 'results-recompared.json'}", file=sys.stderr)
    return 0


def main() -> int:
    import astrotwo

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("objects", nargs="*", default=list(OBJECTS))
    parser.add_argument("--out", type=Path, default=Path("docs/validation-runs") / dt.date.today().isoformat())
    parser.add_argument("--recompare", type=Path, metavar="DIR",
                        help="recompare the saved rows of DIR/results.json with the empty-text rule (no network)")
    args = parser.parse_args()
    if args.recompare is not None:
        return recompare_run(args.recompare)
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for name in args.objects:
        print(f"{name}: AstroTwo profile…", file=sys.stderr)
        astro = astrotwo_profile(name, args.out)
        print(f"{name}: reference queries…", file=sys.stderr)
        ref = reference(name, astro)
        found = compare(name, astro, ref)
        rows.extend(found)
        counts = {k: sum(r["outcome"] == k for r in found) for k in ("pass", "fail", "not measured")}
        print(f"{name}: {counts}", file=sys.stderr)
    meta = {"astrotwo_version": astrotwo.__version__, "date": now(), "objects": args.objects,
            "tolerances": {"distance_parallax_relative": TOL_DISTANCE_PARALLAX, "sed_flux_relative": TOL_SED_FLUX,
                           "separation_arcsec": TOL_SEPARATION_ARCSEC}}
    (args.out / "results.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=1, ensure_ascii=False,
                                                      default=str))
    (args.out / "results.md").write_text(markdown(rows))
    total = {k: sum(r["outcome"] == k for r in rows) for k in ("pass", "fail", "not measured")}
    print(f"total: {total}; written {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
