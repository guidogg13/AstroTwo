# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Profilo di un oggetto, sezione fotometria (``mdfiles/25-analisi-profilo-oggetto.md`` §3.11, §12: T7, T19, T20).

Servizi simulati con le risposte vere registrate il 2026-11-07 (archivio Gaia ESA, IRSA, SIMBAD di Harvard); la SED di
VizieR (CDS giù quel giorno) risponde HTTP 503. Gli attesi vengono dalle risposte registrate lette con Astropy e dai
punti zero scritti nel 20 §3.2; le separazioni si ricalcolano con ``SkyCoord.apply_space_motion`` di Astropy.
"""

from __future__ import annotations

import base64
import io
import json

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.io.votable import parse_single_table
from astropy.time import Time

import astrotwo.analysis.object_profile as op
from astrotwo.analysis.object_profile import ProfileTarget, build_profile, cross_identify, resolve_target
from tests.analysis.profile_fakes import recorded, recorded_query, services, votable  # noqa: F401


def table_of(service: str, contains: str):
    return parsed(service, recorded_query(service, contains))


def parsed(service: str, query: str):
    """Risposta registrata per l'interrogazione esatta, con i nomi delle colonne (IRSA dà anche gli ID ``col_N``)."""
    return parse_single_table(io.BytesIO(recorded(service, query))).to_table(use_names_over_ids=True)


def photometry(prof):
    return next(s for s in prof.sections if s.name == "photometry")


def points(sec) -> dict:
    return {f"{p['catalog']} {p['band']}": p for p in sec.details["points"]}


def codes(items) -> list[str]:
    return [w[0] for w in items]


def run(name, cache, **kw):
    return build_profile(ProfileTarget(name=name), sections=("identity", "photometry"), cache=cache, **kw)


# =============================================================================
# T19 — sezione fotometria sui quattro oggetti


def test_t19_51_peg_points_quality_duplicates_and_vizier_error(services, cache):
    prof = run("51 Peg", cache)
    sec = photometry(prof)
    assert sec.status == "partial"  # SED di VizieR giù: errore della sola sezione
    assert [e["catalog"] for e in sec.errors] == ["vizier_sed"] and sec.errors[0]["code"] == "SERVICE_ERROR"
    pts = points(sec)
    assert {k for k in pts if not k.startswith("SIMBAD")} == {
        "Gaia DR3 G", "Gaia DR3 BP", "Gaia DR3 RP", "2MASS J", "2MASS H", "2MASS Ks",
        "AllWISE W1", "AllWISE W2", "AllWISE W3", "AllWISE W4"}
    # 2MASS: valori e qualità dalla risposta registrata (designazione dentro il cerchio della designazione)
    tm = table_of("irsa", "designation = '22572795+2046077'")
    assert str(tm["ph_qual"][0]) == "DDA"
    k_m = float(str(tm["k_m"][0]))
    assert pts["2MASS Ks"]["magnitude"]["value"] == k_m and pts["2MASS Ks"]["in_plot"]
    assert pts["2MASS Ks"]["flux"]["value"] == pytest.approx((666.7 * u.Jy * u.Magnitude(k_m).physical).value,
                                                              rel=1e-12)
    for band in ("J", "H"):
        assert not pts[f"2MASS {band}"]["in_plot"] and [n["code"] for n in pts[f"2MASS {band}"]["notes"]] == [
            "SED_LOW_QUALITY"]
    # AllWISE dall'incrocio ufficiale di Gaia, tutti A/B/C
    assert all(pts[f"AllWISE W{k}"]["in_plot"] for k in range(1, 5))
    assert pts["AllWISE W1"]["identifier"] == "WISEA J225728.12+204608.6"
    assert pts["AllWISE W1"]["match"] == "official_crossmatch"
    # Gaia: dal flusso in e⁻/s con ZP_AB; SIMBAD G (Gaia EDR3) duplicato del punto Gaia DR3
    gaia = table_of("gaia", "phot_bp_rp_excess_factor FROM gaiadr3.gaia_source WHERE source_id = 2835207319109249920")
    rate = float(gaia["phot_g_mean_flux"][0])
    m_ab = -2.5 * np.log10(rate) + 25.8010446445
    assert pts["Gaia DR3 G"]["flux"]["value"] == pytest.approx((3631 * u.Jy * u.Magnitude(m_ab).physical).value,
                                                                rel=1e-12)
    assert pts["SIMBAD G"]["duplicate_of"] == "Gaia DR3 G"
    assert {pts[f"SIMBAD {b}"]["duplicate_of"] for b in "JHK"} == {"2MASS J", "2MASS H", "2MASS Ks"}
    assert not any(p["in_plot"] for k, p in pts.items() if k.startswith("SIMBAD"))
    assert pts["SIMBAD B"]["magnitude"]["value"] == 6.16  # float32 di SIMBAD al decimale scritto
    assert "SED_HIGH_PROPER_MOTION" in codes(sec.warnings)  # 51 Peg: |μ| · 16 anni > 2″
    # grafico PNG nel risultato, zero point usati con fonte
    png = base64.b64decode(sec.details["plot_png"]["data"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert {z["key"] for z in sec.details["zero_points"]} == {
        "Gaia DR3 G", "Gaia DR3 BP", "Gaia DR3 RP", "2MASS J", "2MASS H", "2MASS Ks", "WISE W1", "WISE W2",
        "WISE W3", "WISE W4"}
    # valori della sezione: letti e calcolati, con provenienza
    computed = [v for v in sec.values if v.method == "computed"]
    assert len(computed) == 10 and all(v.formula and v.provenance.table for v in computed)
    json.dumps(prof.as_dict())


def test_t19_vega_saturated_2mass_and_allwise_upper_limits(services, cache):
    sec = photometry(run("Vega", cache))
    pts = points(sec)
    assert not any(k.startswith("Gaia") for k in pts)  # Vega non è in Gaia DR3
    tm = table_of("irsa", "designation = '18365633+3847012'")
    assert str(tm["ph_qual"][0]) == "CBC"  # saturata ma con qualità C/B/C: nel grafico per la regola D20-4
    assert all(pts[f"2MASS {b}"]["in_plot"] for b in ("J", "H", "Ks"))
    assert pts["2MASS J"]["magnitude"]["value"] == -0.177 and pts["2MASS J"]["flags"]["rd_flg"] == "3"
    for band in ("W1", "W2"):
        assert pts[f"AllWISE {band}"]["upper_limit"] and not pts[f"AllWISE {band}"]["in_plot"]
        assert "SED_UPPER_LIMIT" in [n["code"] for n in pts[f"AllWISE {band}"]["notes"]]
    assert pts["AllWISE W3"]["in_plot"] and pts["AllWISE W4"]["in_plot"]
    assert pts["AllWISE W1"]["match"] == "position"


def test_t19_eta_tau_saturated_2mass_and_gaia(services, cache):
    pts = points(photometry(run("eta Tau", cache)))
    assert pts["2MASS J"]["quality"] == "D" and pts["2MASS Ks"]["quality"] == "D"
    assert not pts["2MASS J"]["in_plot"] and not pts["2MASS Ks"]["in_plot"] and pts["2MASS H"]["in_plot"]
    assert pts["Gaia DR3 G"]["in_plot"]  # soluzione astrometrica a 2 parametri, fotometria presente
    assert pts["SIMBAD G"]["duplicate_of"] == "Gaia DR3 G"  # 2022yCat.1355 (Gaia DR3)
    assert not any(k.startswith("AllWISE") for k in pts)  # nessuna sorgente AllWISE entro 2″ (C1: entro 10,8″)


def test_t19_trappist_1_w4_upper_limit_and_undeclared_simbad_system(services, cache):
    pts = points(photometry(run("TRAPPIST-1", cache)))
    w4 = pts["AllWISE W4"]
    assert w4["upper_limit"] and w4["magnitude"]["value"] == 8.565 and w4["magnitude_error"] is None
    assert {n["code"] for n in w4["notes"]} == {"SED_UPPER_LIMIT", "SED_NO_ERROR"}
    assert "SED_NO_SYSTEM" in [n["code"] for n in pts["SIMBAD J"]["notes"]]  # SIMBAD non dichiara il sistema
    assert pts["SIMBAD J"]["duplicate_of"] == "2MASS J"


# =============================================================================
# T7 — AllWISE per posizione con propagazione (Vega)


def test_t7_allwise_by_position_only_after_propagation(services, cache):
    resolved = resolve_target(ProfileTarget(name="Vega"), cache=cache)
    found = cross_identify(resolved, "allwise", cache=cache)
    assert found.identifier == "WISEA J183656.51+384704.4" and found.method == "position"
    note = next(w for w in found.warnings if w[0] == "PROFILE_POSITIONAL_MATCH")
    assert note.params["target_epoch"].startswith("MJD 55400.0 UTC")
    # separazione ricalcolata con Astropy: posizione SIMBAD J2000 + moto proprio SIMBAD → MJD 55400,0
    basic = resolved.simbad.basic
    start = SkyCoord(basic["ra"], basic["dec"], pm_ra_cosdec=basic["pmra"], pm_dec=basic["pmdec"],
                     distance=basic["plx_value"].to(u.pc, u.parallax()), radial_velocity=0 * u.km / u.s,
                     obstime=Time("J2000.0"))
    moved = start.apply_space_motion(new_obstime=Time(55400.0, format="mjd", scale="utc"))
    row = parsed("irsa", found.queries[-1])
    row = row[[str(d) == "J183656.51+384704.4" for d in row["designation"]]]
    sep = SkyCoord(row["ra"][0], row["dec"][0], unit="deg").separation(
        SkyCoord(moved.ra, moved.dec)).to(u.arcsec)
    assert found.separation.to_value(u.arcsec) == pytest.approx(sep.value, abs=1e-6)
    # senza propagazione (posizione J2000 così com'è) la sorgente è fuori dai 2″: risposta vera vuota
    still = table_of("irsa", "allwise_p3as_psd WHERE CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', "
                             "279.234734787025, 38.783688956244,")
    assert len(still) == 0


# =============================================================================
# T20 — passo per posizione di 2MASS (jdate della riga)


def test_t20_2mass_by_position_at_the_jdate_of_the_row(services, cache):
    import dataclasses

    resolved = resolve_target(ProfileTarget(name="Vega"), cache=cache)
    record = dataclasses.replace(resolved.simbad, identifiers=tuple(
        i for i in resolved.simbad.identifiers if not i.startswith("2MASS")))
    resolved = dataclasses.replace(resolved, simbad=record)
    found = cross_identify(resolved, "2mass", cache=cache)
    assert found.identifier == "2MASS J18365633+3847012" and found.method == "position"
    query = found.queries[-1]
    assert "FROM fp_psc WHERE CONTAINS" in query
    row = parsed("irsa", query)
    row = row[[str(d) == "18365633+3847012" for d in row["designation"]]]
    basic = resolved.simbad.basic
    start = SkyCoord(basic["ra"], basic["dec"], pm_ra_cosdec=basic["pmra"], pm_dec=basic["pmdec"],
                     distance=basic["plx_value"].to(u.pc, u.parallax()), radial_velocity=0 * u.km / u.s,
                     obstime=Time("J2000.0"))
    moved = start.apply_space_motion(new_obstime=Time(float(row["jdate"][0]), format="jd", scale="utc"))
    sep = SkyCoord(row["ra"][0], row["dec"][0], unit="deg").separation(SkyCoord(moved.ra, moved.dec)).to(u.arcsec)
    assert found.separation.to_value(u.arcsec) == pytest.approx(sep.value, abs=1e-6)
    # cerchio di ricerca allargato dal moto proprio sul periodo delle osservazioni 2MASS (1997-06-01 – 2001-03-01)
    radius = float(query.split(",")[-1].split(")")[0]) * u.deg
    span = (Time("J2000.0") - Time("1997-06-01", scale="utc")).to(u.yr)
    pm = np.hypot(basic["pmra"], basic["pmdec"])
    assert radius.to_value(u.arcsec) == pytest.approx((2 * u.arcsec + pm * span).to_value(u.arcsec), rel=1e-9)


# =============================================================================
# Sezioni indipendenti con la fotometria (T10 del 25) e designazioni


def test_t10_gaia_down_keeps_2mass_and_allwise_photometry(services, cache):
    services.overrides[("gaia", "")] = lambda q: (503, "text/plain", "coda piena")
    sec = photometry(build_profile(ProfileTarget(name="51 Peg"), cache=cache))
    assert sec.status == "partial"
    assert {e["catalog"] for e in sec.errors} == {"Gaia DR3", "vizier_sed"}
    pts = points(sec)
    assert "2MASS Ks" in pts and "AllWISE W3" in pts  # AllWISE per posizione (incrocio ufficiale giù)
    assert pts["AllWISE W3"]["match"] == "position"


def test_no_row_for_a_known_identifier_is_declared(services, cache):
    services.overrides[("irsa", "designation = '22572795+2046077'")] = lambda q: votable(
        [("designation", "char", None)], [])
    sec = photometry(run("51 Peg", cache))
    note = next(w for w in sec.warnings if w[0] == "PROFILE_NO_PHOTOMETRY")
    assert note.params == {"reason": "not_in_catalog", "catalog": "2MASS", "identifier": "2MASS J22572795+2046077",
                           "table": "fp_psc"}
    assert not any(k.startswith("2MASS") for k in points(sec))


@pytest.mark.parametrize("catalog, designation, expected", [
    ("2mass", "22572795+2046077", (344.36645833333333, 20.768805555555556)),
    ("allwise", "J230630.02-050234.1", (346.62508333333335, -5.042805555555556)),
    ("2mass", "nonvalida", None)])
def test_designation_position(catalog, designation, expected):
    found = op.designation_position(catalog, designation)
    if expected is None:
        assert found is None
    else:
        assert found == pytest.approx(expected, abs=1e-12)


def test_plot_png_is_not_part_of_the_network_fingerprint(services, cache):
    data = run("51 Peg", cache).as_dict()
    content = op.profile_content(data)
    sec = next(s for s in content["sections"] if s["name"] == "photometry")
    assert "plot_png" not in sec["details"] and "points" in sec["details"]


# =============================================================================
# Rete (marcatore network, non eseguito nel commit)


@pytest.mark.network
@pytest.mark.parametrize("name", ["51 Peg", "Vega", "eta Tau", "TRAPPIST-1"])
def test_network_photometry_four_objects(name, cache):
    sec = photometry(build_profile(ProfileTarget(name=name), sections=("identity", "photometry"), cache=cache))
    pts = points(sec)
    assert any(k.startswith("2MASS") for k in pts)
    assert all(p["provenance"]["server"] for p in pts.values())
