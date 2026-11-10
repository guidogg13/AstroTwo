# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Sezioni Immagini e Pianeti del profilo (``mdfiles/25-analisi-profilo-oggetto.md`` §3.13; §12: T8, T9, T16, T24, T25).

Risposte vere registrate il 2026-11-07 (``tests/analysis/profile_fakes.py``): ``pscomppars`` del NASA Exoplanet Archive
per 51 Peg e TRAPPIST-1; ``properties`` e tile di ESASky per DSS2, 2MASS e AllWISE colore (CDS giù quel giorno: il
MocServer non risponde e i survey si aprono dai mirror verificati del 12).
"""

from __future__ import annotations

import base64
import io
import time

import astropy.units as u
import pytest
from astropy.time import Time
from PIL import Image

import astrotwo.analysis.object_profile as op
from astrotwo.analysis.object_profile import ProfileTarget, build_profile, parse_reflink
from astrotwo.core.coordinates_wcs import propagate_position
from tests.analysis.profile_fakes import irsa_empty, services, votable  # noqa: F401

AGOL = "2021PSJ.....2....1A"


def section(prof, name):
    return next(s for s in prof.sections if s.name == name)


def values(sec) -> dict:
    return {v.quantity: v for v in sec.values}


# =============================================================================
# T8 — pianeti di TRAPPIST-1


def test_t8_trappist_1_seven_planets_with_errors_and_references(services, cache):
    prof = build_profile(ProfileTarget(name="TRAPPIST-1"), sections=("planets",), cache=cache)
    sec = section(prof, "planets")
    assert sec.status == "done"
    planets = sec.details["planets"]
    assert [p["pl_name"] for p in planets] == [f"TRAPPIST-1 {x}" for x in "bcdefgh"]
    assert sec.details["query_by"] == "gaia_dr3_id"  # l'ospite è stato trovato per gaia_dr3_id (catena, §3.10)
    vals = values(sec)
    b = vals["TRAPPIST-1 b period"]
    assert b.value == 1.510826 * u.d and b.error_upper == 6e-06 * u.d and b.error_lower == -6e-06 * u.d
    assert b.reference == AGOL and b.method == "read" and b.provenance.table == "pscomppars"
    mass = vals["TRAPPIST-1 h mass"]
    assert mass.value == 0.326 * u.M_earth and mass.error_upper == 0.02 * u.M_earth
    assert mass.error_lower == -0.02 * u.M_earth and mass.note == "pl_bmassprov = Mass"
    for planet in planets:
        for key in ("period", "semi_major_axis", "eccentricity", "mass", "radius", "equilibrium_temperature"):
            assert key in planet["parameters"]
        ref = planet["parameters"]["period"]["reference"]
        assert ref == {"text": "Agol et al. 2021", "url": f"https://ui.adsabs.harvard.edu/abs/{AGOL}/abstract",
                       "bibcode": AGOL}
        assert planet["discoverymethod"] == "Transit"
    assert planets[0]["parameters"]["semi_major_axis"]["value"]["unit"] == "AU"
    assert vals["TRAPPIST-1 b discoverymethod"].value == "Transit"
    composite = [w for w in sec.warnings if w[0] == "PROFILE_PLANETS_COMPOSITE"]
    assert composite and composite[0].params["count"] == 7 and composite[0].params["table"] == "pscomppars"


def test_t8_51_peg_b_reference_with_ampersand_in_the_bibcode(services, cache):
    prof = build_profile(ProfileTarget(name="51 Peg"), sections=("planets",), cache=cache)
    sec = section(prof, "planets")
    assert [p["pl_name"] for p in sec.details["planets"]] == ["51 Peg b"]
    assert values(sec)["51 Peg b mass"].reference == "2026A&A...710A.345C"  # «&» non è un'entità HTML


# =============================================================================
# T9 — nessun pianeta: sezione done, nessuna richiesta pscomppars


@pytest.mark.parametrize("name", ["Vega", "eta Tau"])
def test_t9_no_planet_is_not_an_error(services, cache, name):
    prof = build_profile(ProfileTarget(name=name), sections=("planets",), cache=cache)
    sec = section(prof, "planets")
    assert sec.status == "done" and not sec.errors and not sec.values
    assert sec.details["planets"] == [] and sec.details["note"].startswith("no planet in the archive")
    assert not any("ORDER BY pl_name" in q for s, q in services.queries if s == "exoplanet")


# =============================================================================
# T25 — Pianeti senza aspettare Gaia (D25-17 (10), 25 §3.14)

VEGA = (279.234734787025, 38.783688956244)
GAIA_CONE = [("source_id", "long", None), ("ra", "double", "deg"), ("dec", "double", "deg"),
             ("phot_g_mean_mag", "float", "mag")]
HOSTS = [("hostname", "char", None), ("gaia_dr3_id", "char", None)]


def test_t25_vega_planets_do_not_wait_for_a_slow_gaia_archive(services, cache):
    """Vega non ha Gaia DR3 in SIMBAD: con l'archivio Gaia fermo la sezione Pianeti arriva subito (ricerca per
    hostname), senza aspettare il passo per posizione di Gaia (prima: fino a 30 s e PROFILE_SECTION_TIMEOUT)."""
    def slow(query):
        time.sleep(3.0)
        return votable(GAIA_CONE, [])
    services.overrides[("gaia", "CONTAINS")] = slow
    seen = []
    started = time.monotonic()
    prof = build_profile(ProfileTarget(name="Vega"), sections=("planets",), cache=cache,
                         on_section=lambda s: seen.append((s.name, time.monotonic() - started)))
    assert seen[0][0] == "planets" and seen[0][1] < 2.0  # prima della risposta di Gaia (3 s)
    sec = section(prof, "planets")
    assert sec.status == "done" and sec.details["note"].startswith("no planet in the archive")
    assert not sec.errors
    asked = [q for s, q in services.queries if s == "exoplanet"]
    assert len(asked) == 1 and "WHERE hostname IN (" in asked[0]


def test_t25_host_found_only_by_the_later_gaia_dr3_id_is_declared(services, cache):
    """Gaia per posizione dà poi una sorgente il cui gaia_dr3_id ha un ospite: nessuna scelta, avviso dichiarato."""
    services.overrides[("gaia", "CONTAINS")] = lambda q: votable(GAIA_CONE, [[42, VEGA[0], VEGA[1], 17.0]])
    services.overrides[("gaia", "best_neighbour")] = lambda q: votable(
        [("source_id", "long", None), ("original_ext_source_id", "char", None),
         ("angular_distance", "double", "arcsec"), ("number_of_neighbours", "int", None), ("xm_flag", "short", None)],
        [])
    services.overrides[("irsa", "")] = lambda q: irsa_empty("allwise" if "allwise" in q else "2mass")
    services.overrides[("exoplanet", "gaia_dr3_id = 'Gaia DR3 42'")] = lambda q: votable(
        HOSTS, [["Altro ospite", "Gaia DR3 42"]])
    prof = build_profile(ProfileTarget(name="Vega"), sections=("identity", "planets"), cache=cache)
    assert section(prof, "planets").details["planets"] == []  # pianeti dell'esito per hostname (nessuno)
    notes = [w for w in section(prof, "identity").warnings if w[0] == "PROFILE_PLANET_HOST_MISMATCH"]
    assert len(notes) == 1 and notes[0].params == {"reason": "only_gaia", "gaia_dr3_id": "Gaia DR3 42",
                                                   "by_gaia": "Altro ospite"}
    assert any(w[0] == "PROFILE_PLANET_HOST_MISMATCH" for w in prof.warnings)
    host = next(c for c in prof.cross_ids if c.catalog == "exoplanet")
    assert host.identifier is None and host.conflict["by_gaia"] == "Altro ospite"


# =============================================================================
# T16 — reflink: solo testo, URL e bibcode di ADS


def test_t16_reflink_keeps_only_text_and_ads():
    html = ('<a refstr=AGOL_ET_AL__2021 href=https://ui.adsabs.harvard.edu/abs/2021PSJ.....2....1A/abstract '
            'target=ref>Agol et al. 2021</a>')
    assert parse_reflink(html) == {"text": "Agol et al. 2021", "url": "https://ui.adsabs.harvard.edu/abs/"
                                   "2021PSJ.....2....1A/abstract", "bibcode": AGOL}
    other = '<a href="https://example.org/x" onclick="alert(1)">Calculated &amp; <b>value</b></a><script>x</script>'
    assert parse_reflink(other) == {"text": "Calculated & value x", "url": None, "bibcode": None}
    assert parse_reflink(None) is None and parse_reflink("  ") is None


# =============================================================================
# T24 — miniature


def test_t24_thumbnails_of_51_peg(services, cache):
    prof = build_profile(ProfileTarget(name="51 Peg"), sections=("images",), cache=cache)
    sec = section(prof, "images")
    assert sec.status == "done" and not sec.errors
    thumbs = {t["hips_id"]: t for t in sec.details["thumbnails"]}
    assert list(thumbs) == ["CDS/P/DSS2/color", "CDS/P/2MASS/color", "CDS/P/allWISE/color"]
    for hips_id, t in thumbs.items():
        assert t["size"] == 256 and t["fov"] == {"value": 5.0, "unit": "arcmin"}
        assert t["pixels_with_data"] == 256 * 256
        assert len(t["servers"]) == 1 and "/hips/skies.esac.esa.int/" in t["servers"][0]  # server reale dei tile
        assert t["credits"]["obs_title"] and "obs_copyright" in t["credits"] or "obs_ack" in t["credits"]
        png = Image.open(io.BytesIO(base64.b64decode(t["png"])))
        assert png.size == (256, 256)
        assert "CTYPE1  = 'RA---TAN'" in t["wcs"]
    assert thumbs["CDS/P/DSS2/color"]["order"] == 9 and thumbs["CDS/P/allWISE/color"]["order"] == 8
    # DSS2 e 2MASS: epoca della survey non nota → posizione SIMBAD J2000, dichiarato
    simbad = prof.resolved.position.coord.icrs
    for hips_id in ("CDS/P/DSS2/color", "CDS/P/2MASS/color"):
        t = thumbs[hips_id]
        assert t["epoch"] is None and t["center_note"].startswith("survey epoch not known")
        assert t["center"]["ra"]["value"] == pytest.approx(simbad.ra.deg, abs=1e-12)
    # AllWISE: epoca 2010,545 (MJD 55396), centro portato all'epoca con il moto proprio SIMBAD
    allwise = thumbs["CDS/P/allWISE/color"]
    assert allwise["epoch"]["mjd"] == 55396.0 and allwise["center_note"].startswith("centre moved to the survey epoch")
    basic = prof.resolved.simbad.basic
    plx = basic["plx_value"]
    moved = propagate_position(prof.resolved.position, pm_ra_cosdec=basic["pmra"], pm_dec=basic["pmdec"],
                               parallax=plx, target_epoch=Time(55396.0, format="mjd", scale="utc"),
                               proper_motion_only=False).position.coord.icrs
    assert allwise["center"]["ra"]["value"] == pytest.approx(moved.ra.deg, abs=1e-12)
    assert allwise["center"]["dec"]["value"] == pytest.approx(moved.dec.deg, abs=1e-12)
    assert "HIPS_MIRROR_FALLBACK" in {w[0] for w in sec.warnings}  # MocServer giù: mirror dichiarato
    # i PNG non entrano nell'impronta di rete (come il grafico della SED)
    assert "png" not in str(op.profile_content(sec.as_dict()))


def test_t24_survey_down_on_all_servers_leaves_the_thumbnail_missing(services, cache, monkeypatch):
    from astrotwo.core import hips

    table = dict(hips.MIRROR_FALLBACKS)
    table["CDS/P/2MASS/color"] = (f"{services.fake.url}/hips/down-a/2MASSColor",
                                  f"{services.fake.url}/hips/down-b/2MASSColor")
    monkeypatch.setattr(hips, "MIRROR_FALLBACKS", table)
    services.overrides[("hips", "down-")] = lambda path: (503, "text/plain", "giù")
    prof = build_profile(ProfileTarget(name="51 Peg"), sections=("images",), cache=cache)
    sec = section(prof, "images")
    assert sec.status == "partial"
    assert [t["hips_id"] for t in sec.details["thumbnails"]] == ["CDS/P/DSS2/color", "CDS/P/allWISE/color"]
    error = sec.errors[0]
    assert error["code"] == "NET_TIMEOUT" and error["params"]["reason"] == "hips_servers"
    assert error["survey"] == "CDS/P/2MASS/color" and error["params"]["servers"] == 2



# =============================================================================
# Rete (marcati ``network``, non nel commit): miniature e pianeti veri, solo struttura e identificativi


@pytest.mark.network
@pytest.mark.parametrize("name, planets", [("TRAPPIST-1", 7), ("51 Peg", 1), ("Vega", 0)])
def test_network_images_and_planets(name, planets, cache):
    prof = build_profile(ProfileTarget(name=name), sections=("images", "planets"), cache=cache)
    images = section(prof, "images")
    assert images.status == "done", images.errors
    assert [t["hips_id"] for t in images.details["thumbnails"]] == list(op.IMAGE_SURVEYS)
    assert all(t["pixels_with_data"] > 0 and t["servers"] for t in images.details["thumbnails"])
    found = section(prof, "planets")
    assert found.status == "done" and len(found.details["planets"]) == planets
