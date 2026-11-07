# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Profilo di un oggetto, motore (``mdfiles/25-analisi-profilo-oggetto.md`` §3.10, §12: T1–T6, T10, T12, T13).

Servizi simulati con le risposte vere registrate il 2026-11-07 (``tests/analysis/profile_fakes.py``). Gli attesi
vengono dalle risposte registrate lette con Astropy o dalla specifica (T1–T5, osservati quel giorno), mai calcolati
qui con un'altra formula: la distanza 1/ϖ si ricalcola con ``astropy.units.parallax`` come dice T3. I test con il
marcatore ``network`` interrogano i servizi veri (non eseguiti nel commit, ``--no-network``).
"""

from __future__ import annotations

import io

import astropy.units as u
import pytest
from astropy.coordinates import SkyCoord
from astropy.io.votable import parse_single_table
from astropy.time import Time

import astrotwo.analysis.object_profile as op
from astrotwo.analysis.object_profile import (
    DEFAULT_CROSSMATCH_RADIUS,
    ObjectProfileError,
    ProfileTarget,
    ProfileValue,
    Provenance,
    ResolvedTarget,
    TargetCandidates,
    build_profile,
    cross_identify,
    distance_from,
    resolve_target,
)
from astrotwo.core.coordinates_wcs import ResolvedName, SkyFrame
from astrotwo.core.vo_protocols import VoProtocolsError
from tests.analysis.profile_fakes import recorded, recorded_query, services, votable  # noqa: F401

J2000 = Time("J2000.0")
VEGA_J2000 = (279.234734787025, 38.783688956244)
PEG_J2000 = (344.36658535524, 20.768832511140005)
ETA_TAU_J2000 = (56.871152303749994, 24.105135651944444)
TRAPPIST_J2000 = (346.62236872857875, -5.041399250518334)


def at(ra: float, dec: float, epoch=J2000) -> SkyFrame:
    return SkyFrame.from_lonlat(ra * u.deg, dec * u.deg, "icrs", epoch=epoch)


def table_of(service: str, contains: str):
    return parse_single_table(io.BytesIO(recorded(service, recorded_query(service, contains)))).to_table()


def section(profile, name):
    return next(s for s in profile.sections if s.name == name)


def values(sec) -> dict:
    return {v.quantity: v for v in sec.values}


def codes(items) -> list[str]:
    return [w[0] for w in items]


def profile(name, cache, **kw):
    return build_profile(ProfileTarget(name=name), cache=cache, **kw)


# =============================================================================
# T1 — identità di 51 Peg


def test_t1_identity_of_51_peg(services, cache):
    resolved = resolve_target(ProfileTarget(name="51 Peg"), cache=cache)
    assert isinstance(resolved, ResolvedTarget) and resolved.method == "simbad_identifier"
    record = resolved.simbad
    assert " ".join(record.main_id.split()) == "* 51 Peg"  # SIMBAD scrive "*  51 Peg"
    assert record.basic["otype"] == "PM*" and record.basic["sp_type"] == "G2IV"
    assert record.basic["sp_bibcode"] == "1989ApJS...71..245K"
    for ident in ("Gaia DR3 2835207319109249920", "2MASS J22572795+2046077", "HIP 113357", "NAME Helvetios"):
        assert ident in record.identifiers
    idents = table_of("simbad", "SELECT id FROM ident WHERE oidref = 1472090")
    assert len(record.identifiers) == len({str(i).strip() for i in idents["id"]}) == 46
    prof = profile("51 Peg", cache, sections=("identity",))
    sec = section(prof, "identity")
    assert sec.status == "done"
    v = values(sec)
    assert v["sp_type"].reference == "1989ApJS...71..245K" and v["otype"].note == "High Proper Motion Star"
    assert v["ra"].value.unit == u.deg and v["ra"].provenance.table == "basic"
    assert v["ra"].provenance.server == services.url("simbad") + "/sync"
    assert "NAME" in sec.details["identifiers"] and "HIP" in sec.details["identifiers"]
    assert sec.details["simbad_url"].startswith(services.fake.url + "/simbad/sim-id?Ident=")


# =============================================================================
# T2 — catena degli identificativi di 51 Peg


def test_t2_identifier_chain_of_51_peg(services, cache):
    resolved = resolve_target(ProfileTarget(name="51 Peg"), cache=cache)
    gaia = cross_identify(resolved, "gaia_dr3", cache=cache)
    assert (gaia.identifier, gaia.method, gaia.source_id) == ("Gaia DR3 2835207319109249920", "simbad_identifier",
                                                              2835207319109249920)
    tmass = cross_identify(resolved, "2mass", gaia=gaia, cache=cache)
    assert (tmass.identifier, tmass.method) == ("2MASS J22572795+2046077", "simbad_identifier")
    assert tmass.official["designation"] == "22572795+2046077" and tmass.conflict is None
    allwise = cross_identify(resolved, "allwise", gaia=gaia, cache=cache)
    official = table_of("gaia", "allwise_best_neighbour WHERE source_id = 2835207319109249920")
    assert (allwise.identifier, allwise.method) == ("WISEA J225728.12+204608.6", "official_crossmatch")
    # 0,238″ letta dall'archivio (float a 32 bit riportato al decimale scritto dal servizio)
    assert allwise.separation == float(str(official["angular_distance"][0])) * u.arcsec
    assert round(allwise.separation.to_value(u.arcsec), 3) == 0.238
    exo = cross_identify(resolved, "exoplanet", gaia=gaia, cache=cache)
    assert (exo.identifier, exo.method) == ("51 Peg", "simbad_identifier")
    assert "gaia_dr3_id = 'Gaia DR3 2835207319109249920'" in exo.queries[0]


# =============================================================================
# T3 — Alcyone (eta Tau), soluzione Gaia a 2 parametri


def test_t3_alcyone_two_parameter_solution(services, cache):
    prof = profile("eta Tau", cache, sections=("astrometry",))
    sec = section(prof, "astrometry")
    v = values(sec)
    assert v["source_id"].value == 66714384142368256 and v["astrometric_params_solved"].value == 3
    assert "PROFILE_GAIA_TWO_PARAMETER" in codes(sec.warnings)
    assert v["ruwe"].value is None  # nullo per le soluzioni a 2 parametri
    assert v["parallax"].provenance.table == "basic" and v["parallax"].reference == "2007A&A...474..653V"
    assert v["parallax"].value == 8.09 * u.mas and v["parallax"].error == 0.42 * u.mas
    d = v["distance_parallax"]
    assert d.method == "computed" and d.value == (8.09 * u.mas).to(u.pc, u.parallax())
    assert d.interval == ((8.51 * u.mas).to(u.pc, u.parallax()), (7.67 * u.mas).to(u.pc, u.parallax()))
    assert "zero point" in d.note and d.reference == "2007A&A...474..653V"
    assert sec.status == "done"


# =============================================================================
# T4 — Vega senza Gaia DR3


def test_t4_vega_without_gaia(services, cache):
    prof = profile("Vega", cache)
    gaia = prof.cross_ids[0]
    assert gaia.identifier is None and gaia.method is None and not gaia.candidates
    assert not any(i.startswith("Gaia DR3") for i in prof.resolved.simbad.identifiers)
    sec = section(prof, "astrometry")
    assert "PROFILE_NO_GAIA" in codes(sec.warnings)
    no_gaia = next(w for w in sec.warnings if w[0] == "PROFILE_NO_GAIA")
    assert no_gaia.params == {"reason": "no_counterpart", "radius": {"value": 2.0, "unit": "arcsec"}}
    v = values(sec)
    assert v["parallax"].note == "SIMBAD" and v["parallax"].reference == "2007A&A...474..653V"
    assert v["distance_parallax"].value == v["parallax"].value.to(u.pc, u.parallax())
    # la posizione SIMBAD è portata a J2016.0 prima del cerchio di 2″ (il cerchio registrato non ha sorgenti)
    assert gaia.epochs == {"source": "J2000.000", "target": "J2016.000"}
    assert "CIRCLE('ICRS'" in gaia.queries[0]


def test_t4_larger_radius_is_declared_never_silent(services, cache):
    """Con 36″ l'archivio dà una stella di G = 17,3 a 24,7″: incrocio per posizione dichiarato, con la separazione."""
    prof = build_profile(ProfileTarget(name="Vega"), sections=("astrometry",), crossmatch_radius=36 * u.arcsec,
                         cache=cache)
    gaia = prof.cross_ids[0]
    assert gaia.method == "position" and gaia.identifier == "Gaia DR3 2097893856820155008"
    match = next(w for w in gaia.warnings if w[0] == "PROFILE_POSITIONAL_MATCH")
    assert match.params["reason"] == "catalog_match" and match.params["radius"] == {"value": 36.0, "unit": "arcsec"}
    assert 24.7 < match.params["separation"]["value"] < 24.8
    assert gaia.candidates[0]["phot_g_mean_mag"]["value"] > 17


# =============================================================================
# T5 — distanza di Bailer-Jones


def test_t5_bailer_jones_distance(services, cache):
    sec = section(profile("51 Peg", cache, sections=("astrometry",)), "astrometry")
    v = values(sec)
    d = v["distance_geo"]
    assert d.method == "read" and d.reference == "2021AJ....161..147B"
    assert d.value == 15.514698 * u.pc and d.interval == (15.494703 * u.pc, 15.533528 * u.pc)
    assert d.provenance.table == "external.gaiaedr3_distance" and d.interval_kind == "16th-84th percentile"
    assert "distance_parallax" not in v  # con Bailer-Jones nessun 1/ϖ
    assert v["ruwe"].value == pytest.approx(1.0572765, abs=0) and "senza soglia" in v["ruwe"].note
    assert v["parallax"].provenance.table == "gaiadr3.gaia_source"


# =============================================================================
# T6 — soglia di 1/ϖ


PROV = Provenance("test", "http://test", "t", None, None, None, None, None)


def plx(value, error):
    return ProfileValue("parallax", value * u.mas, PROV, error=None if error is None else error * u.mas)


@pytest.mark.parametrize("value, error, reason", [
    (9.9, 1.0, "low_snr"), (-1.0, 0.1, "negative_parallax"), (5.0, None, "no_parallax_error")])
def test_t6_parallax_threshold_refusals(value, error, reason):
    out, notes = distance_from(None, plx(value, error))
    assert out == () and notes[0][0] == "PROFILE_NO_DISTANCE" and notes[0].params["reason"] == reason
    if reason == "low_snr":
        assert notes[0].params["ratio"] == 9.9 and notes[0].params["minimum"] == 10.0


def test_t6_parallax_threshold_accepts_ten_and_reports_missing():
    out, notes = distance_from(None, plx(10.0, 1.0))
    assert notes == () and out[0].value == (10.0 * u.mas).to(u.pc, u.parallax())
    assert out[0].interval == ((11.0 * u.mas).to(u.pc, u.parallax()), (9.0 * u.mas).to(u.pc, u.parallax()))
    assert distance_from(None, None)[1][0].params == {"reason": "no_parallax"}


# =============================================================================
# T10 — sezioni indipendenti (archivio Gaia giù)


def test_t10_gaia_down_keeps_the_other_sections(services, cache):
    services.overrides[("gaia", "")] = lambda q: (503, "text/plain", "coda piena")
    prof = profile("51 Peg", cache)
    identity, astrometry = section(prof, "identity"), section(prof, "astrometry")
    assert identity.status == "partial" and values(identity)["main_id"].value == prof.resolved.simbad.main_id
    assert {e["catalog"] for e in identity.errors} == {"2mass", "allwise"}
    assert astrometry.status == "partial" and astrometry.errors[0]["code"] == "SERVICE_ERROR"
    v = values(astrometry)
    assert v["parallax"].note == "SIMBAD" and v["distance_parallax"].method == "computed"
    exo = prof.cross_ids[3]
    assert exo.identifier == "51 Peg"  # l'Exoplanet Archive risponde anche con Gaia giù


# =============================================================================
# T12 — più candidati per coordinate; un solo candidato


def test_t12_several_candidates_are_never_chosen(services, cache):
    """eta Tau: la stella e la nebulosa GN 03.44.2 (nessuna dei due è un pianeta, D25-13 (8)): nessuna scelta."""
    target = ProfileTarget(position=at(*ETA_TAU_J2000))
    found = resolve_target(target, cache=cache)
    assert isinstance(found, TargetCandidates) and found.warnings == ()
    assert [" ".join(c["main_id"].split()) for c in found.candidates] == ["* eta Tau", "GN 03.44.2"]
    with pytest.raises(ObjectProfileError) as info:
        build_profile(target, cache=cache)
    assert info.value.code == "PROFILE_AMBIGUOUS_TARGET" and info.value.params["count"] == 2
    assert info.value.params["radius"] == {"value": 10.0, "unit": "arcsec"}


# =============================================================================
# T18 — pianeti esclusi dai candidati da coordinate (D25-13 (8))


@pytest.mark.parametrize("coords, star, planets", [
    (PEG_J2000, "* 51 Peg", ["* 51 Peg b"]),
    (TRAPPIST_J2000, "TRAPPIST-1", [f"TRAPPIST-1{x}" for x in "bcdefghi"])])
def test_t18_planets_are_excluded_from_the_candidates(services, cache, coords, star, planets):
    prof = build_profile(ProfileTarget(position=at(*coords)), sections=("identity",), cache=cache)
    assert prof.resolved.method == "simbad_candidate" and " ".join(prof.resolved.simbad.main_id.split()) == star
    note = next(w for w in prof.warnings if w[0] == "PROFILE_PLANETS_EXCLUDED")
    assert note.params["count"] == len(planets) and sorted(note.params["names"]) == sorted(planets)
    # il tipo viene dalla gerarchia di SIMBAD letta nella stessa risposta (otypedef.path), mai da un elenco
    query = recorded_query("simbad", f"CIRCLE('ICRS', {coords[0]!r}")
    table = table_of("simbad", f"CIRCLE('ICRS', {coords[0]!r}")
    assert "LEFT OUTER JOIN otypedef" in query
    assert {str(r["path"]) for r in table if str(r["main_id"]).replace(" ", "") in
            {p.replace(" ", "") for p in planets}} == {"* > Pl"}


def test_planet_family_comes_from_the_otype_path():
    assert op.is_planet_path("* > Pl") and not op.is_planet_path("* > Ev* > PN")
    assert not op.is_planet_path(None) and not op.is_planet_path("ISM > Cld > GNe > RNe")


def test_single_candidate_is_used_with_its_separation(services, cache):
    prof = build_profile(ProfileTarget(position=at(*VEGA_J2000)), sections=("identity",), cache=cache)
    assert prof.resolved.method == "simbad_candidate" and prof.resolved.simbad.main_id == "* alf Lyr"
    match = next(w for w in prof.warnings if w[0] == "PROFILE_POSITIONAL_MATCH")
    assert match.params["reason"] == "simbad_candidate" and match.params["epoch"] == "J2000.000"
    expected = SkyCoord(*VEGA_J2000, unit="deg").separation(prof.resolved.simbad.coords.coord).to(u.arcsec)
    assert prof.resolved.separation.to_value(u.arcsec) == pytest.approx(expected.value, abs=1e-9)


def test_candidates_are_propagated_to_the_epoch_of_the_target(services, cache):
    """Bersaglio a J2016.0: la ricerca si allarga di 10,5″/anno × 16 anni e i candidati si portano a J2016."""
    services.overrides[("simbad", "ON d.otype = b.otype WHERE CONTAINS")] = lambda q: votable(
        [("main_id", "char", None), ("otype", "char", None), ("ra", "double", "deg"), ("dec", "double", "deg"),
         ("pmra", "double", "mas/yr"), ("pmdec", "double", "mas/yr"), ("nbref", "int", None), ("path", "char", None)],
        [["fast", "PM*", 10.0, 0.0, 0.0, 1000.0, 3, "* > PM*"], ["slow", "*", 10.0, 0.0, None, None, 5, "*"]])
    target = at(10.0, 16.0 / 3600.0, Time(2016.0, format="jyear", scale="tt"))
    found, _, _ = op._simbad_candidates(target, 10 * u.arcsec, cache=cache, refresh=False,
                                        timeouts=op.NETWORK_TIMEOUTS)
    query = next(q for s, q in services.queries if s == "simbad")
    radius = float(query.split(",")[-1].split(")")[0])
    dt = float((target.epoch - J2000).to_value(u.yr))
    assert radius == pytest.approx(((10 + 10.5 * dt) * u.arcsec).to_value(u.deg), rel=1e-12)
    # "fast" (1″/anno verso nord) arriva sul bersaglio; "slow" (senza moto proprio) resta a 16″, fuori dai 10″
    assert [c["main_id"] for c in found] == ["fast"] and found[0]["propagated"] is True
    assert found[0]["separation"]["value"] < 0.01


# =============================================================================
# T13 — conflitto di identificativi


def test_t13_identifier_conflict_is_shown_without_choice(services, cache):
    real = table_of("gaia", "tmass_psc_xsc_best_neighbour WHERE source_id = 2835207319109249920")
    services.overrides[("gaia", "tmass_psc_xsc_best_neighbour")] = lambda q: votable(
        [("source_id", "long", None), ("original_ext_source_id", "char", None), ("angular_distance", "double", "arcsec"),
         ("number_of_neighbours", "int", None), ("xm_flag", "short", None)],
        [[2835207319109249920, "22572795+2046099", float(real["angular_distance"][0]), 1, 8]])
    resolved = resolve_target(ProfileTarget(name="51 Peg"), cache=cache)
    tmass = cross_identify(resolved, "2mass", cache=cache)
    assert tmass.identifier is None and tmass.method is None
    assert tmass.conflict == {"simbad": "2MASS J22572795+2046077", "official": "22572795+2046099",
                              "table": "gaiadr3.tmass_psc_xsc_best_neighbour"}
    assert codes(tmass.warnings) == ["PROFILE_IDENTIFIER_CONFLICT"]


# =============================================================================
# Bersaglio: errori, SIMBAD giù, annullamento, arrivo delle sezioni


def test_unknown_name_stops_the_profile(services, cache):
    with pytest.raises(VoProtocolsError) as info:
        build_profile(ProfileTarget(name="No Such Object 98765"), cache=cache)
    assert info.value.code == "NAME_NOT_FOUND" and info.value.params["reason"] == "simbad_identifier"


@pytest.mark.parametrize("target, reason", [
    (ProfileTarget(), "none"), (ProfileTarget(name="Vega", position=at(*VEGA_J2000)), "several")])
def test_invalid_targets(target, reason):
    with pytest.raises(ObjectProfileError) as info:
        resolve_target(target)
    assert info.value.code == "PROFILE_TARGET_INVALID" and info.value.params["reason"] == reason


def test_simbad_down_falls_back_to_the_name_resolver_by_position(services, cache, monkeypatch):
    services.overrides[("simbad", "")] = lambda q: (503, "text/plain", "giù")
    services.overrides[("gaia", "CONTAINS")] = lambda q: votable(
        [("source_id", "long", None), ("ra", "double", "deg"), ("dec", "double", "deg"),
         ("phot_g_mean_mag", "float", "mag")], [])
    coords = at(*VEGA_J2000)
    monkeypatch.setattr(op, "resolve_name", lambda name, **kw: ResolvedName(
        name, "VEGA", coords, "NED (test)", "ned://test", Time.now().datetime, False, None, None, None, None,
        service="ned"))
    prof = profile("Vega", cache)
    assert prof.resolved.method == "name_resolver" and prof.resolved.simbad is None
    assert codes(prof.warnings)[0] == "PROFILE_NO_IDENTIFIERS"
    assert prof.warnings[0].params["cause"]["code"] == "SERVICE_ERROR"
    identity = section(prof, "identity")
    assert identity.status == "error" and identity.errors[0]["code"] == "SERVICE_ERROR"
    astrometry = section(prof, "astrometry")
    assert "PROFILE_NO_PROPER_MOTION" in codes(astrometry.warnings)  # nessun moto proprio senza SIMBAD


def test_sections_arrive_once_in_order_and_cancel_returns_none(services, cache):
    seen = []
    prof = profile("TRAPPIST-1", cache, on_section=lambda s: seen.append((s.name, s.status)))
    assert seen == [("identity", "done"), ("astrometry", "done"), ("photometry", "partial")]  # VizieR (CDS) giù
    assert [c.identifier for c in prof.cross_ids] == ["Gaia DR3 2635476908753563008", "2MASS J23062928-0502285",
                                                       "WISEA J230630.02-050234.1", "TRAPPIST-1"]
    assert values(section(prof, "astrometry"))["distance_geo"].value == 12.454126 * u.pc
    assert profile("TRAPPIST-1", cache, cancel=lambda: True) is None


def test_every_value_has_provenance_and_json(services, cache):
    import json

    prof = profile("eta Tau", cache)
    data = prof.as_dict()
    json.dumps(data)
    for sec in data["sections"]:
        for value in sec["values"]:
            p = value["provenance"]
            assert p["server"].startswith(services.fake.url) and p["table"] and p["query"]
            assert value["method"] in ("read", "computed")
    assert data["options"]["crossmatch_radius"] == {"value": DEFAULT_CROSSMATCH_RADIUS.value, "unit": "arcsec"}


# =============================================================================
# Rete (marcatore network, non eseguiti nel commit)


@pytest.mark.network
@pytest.mark.parametrize("name, gaia", [("51 Peg", "Gaia DR3 2835207319109249920"), ("Vega", None),
                                        ("eta Tau", "Gaia DR3 66714384142368256")])
def test_network_three_objects(name, gaia, cache):
    prof = build_profile(ProfileTarget(name=name), cache=cache)
    assert prof.cross_ids[0].identifier == gaia
    astrometry = section(prof, "astrometry")
    assert astrometry.status in ("done", "partial")
    assert any(v.quantity.startswith("distance") for v in astrometry.values)
