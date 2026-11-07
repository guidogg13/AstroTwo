# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del profilo (25 §10), della SED (20 §10) e di ``simbad_object`` del 14 con codice + ``params`` (D40-3).

Provoca ogni errore e ogni avviso del 25 (più le due sotto-voci di ``NAME_NOT_FOUND`` del 14); ogni istanza è
controllata contro il catalogo alla creazione (``tests/conftest.py``) e qui si verifica la copertura di tutte le coppie
(codice, ragione) e il testo nelle due lingue.
"""

from __future__ import annotations

import astropy.units as u
import pytest
from astropy.io.votable import from_table
from astropy.io.votable.tree import CooSys
from astropy.table import Table
from astropy.time import Time

import astrotwo.analysis.object_profile as op
from astrotwo import messages_catalog as mc
from astrotwo.analysis.object_profile import ObjectProfileError, ProfileTarget, ProfileValue, Provenance
from astrotwo.core.commands import Command, RequestedBy, Workspace, default_registry, sky_json
from astrotwo.core.coordinates_wcs import ResolvedName, SkyFrame
from astrotwo.core.vo_protocols import VoProtocolsError, simbad_object
from tests.analysis.profile_fakes import services, votable  # noqa: F401
from tests.message_helpers import catalog_combinations, check_error, check_message

OWN_CODES = ("PROFILE_TARGET_INVALID", "PROFILE_AMBIGUOUS_TARGET", "PROFILE_NO_IDENTIFIERS", "PROFILE_POSITIONAL_MATCH",
             "PROFILE_NO_PROPER_MOTION", "PROFILE_NO_GAIA", "PROFILE_GAIA_TWO_PARAMETER", "PROFILE_IDENTIFIER_CONFLICT",
             "PROFILE_NO_DISTANCE", "PROFILE_TARGET_CHANGED", "PROFILE_PLANETS_EXCLUDED", "PROFILE_NO_PHOTOMETRY",
             "SED_NO_ZERO_POINT", "SED_NO_SYSTEM", "SED_NO_ERROR", "SED_LOW_QUALITY", "SED_UPPER_LIMIT", "SED_DUPLICATE",
             "SED_HIGH_PROPER_MOTION")
FROM_14 = {("NAME_NOT_FOUND", "simbad_identifier"), ("NAME_NOT_FOUND", "several_objects")}
VEGA = (279.234734787025, 38.783688956244)
PEG = (344.36658535524, 20.768832511140005)
ETA_TAU = (56.871152303749994, 24.105135651944444)
GAIA_CONE = [("source_id", "long", None), ("ra", "double", "deg"), ("dec", "double", "deg"),
             ("phot_g_mean_mag", "float", "mag")]


def required() -> set[tuple[str, str | None]]:
    return {(c, r) for c, r in catalog_combinations(OWN_CODES) if r is not None or not mc.CATALOG[c].variants} | FROM_14


class Seen:
    def __init__(self) -> None:
        self.pairs: set[tuple[str, str | None]] = set()

    def notes(self, items) -> None:
        for item in items:
            if item[0] in OWN_CODES:
                self.pairs.add(check_message(item[0], item.params, item[1]))

    def profile(self, prof) -> None:
        self.notes(prof.warnings)
        for c in prof.cross_ids:
            self.notes(c.warnings)
        for s in prof.sections:
            self.notes(s.warnings)

    def sed(self, sed) -> None:
        for point in sed.points:
            self.notes(point.notes)

    def points(self, prof) -> None:
        """Motivi dei punti nella forma JSON del risultato (``details["points"]`` della sezione fotometria)."""
        section = next(s for s in prof.sections if s.name == "photometry")
        for point in section.details["points"]:
            for n in point["notes"]:
                self.pairs.add(check_message(n["code"], n["params"], n["text"]))

    def error(self, exc) -> None:
        self.pairs.add(check_error(exc))

    def result(self, result) -> None:
        assert result.status == "error", result
        self.pairs.add(check_message(result.error.code, result.error.params, result.error.text))


def at(ra, dec, epoch=Time("J2000.0")):
    return SkyFrame.from_lonlat(ra * u.deg, dec * u.deg, "icrs", epoch=epoch)


def stub_resolver(monkeypatch):
    monkeypatch.setattr(op, "resolve_name", lambda name, **kw: ResolvedName(
        name, "VEGA", at(*VEGA), "NED (test)", "ned://test", Time.now().datetime, False, None, None, None, None,
        service="ned"))


def test_every_code_and_reason_of_the_profile(services, cache, monkeypatch, tmp_path):
    seen = Seen()
    build = op.build_profile
    # PROFILE_TARGET_INVALID dal motore e dal comando
    for target in (ProfileTarget(), ProfileTarget(name="Vega", position=at(*VEGA))):
        with pytest.raises(ObjectProfileError) as info:
            op.resolve_target(target)
        seen.error(info.value)
    registry = default_registry(cache=cache)
    for spec in op.command_specs():
        registry.register(spec)
    workspace = Workspace()
    table = Table({"ra": [VEGA[0], 400.0], "dec": [VEGA[1], 10.0]})
    table["ra"].unit = table["dec"].unit = u.deg
    vot = from_table(table)
    ra_f, dec_f = vot.get_first_table().fields
    ra_f.ucd, dec_f.ucd = "pos.eq.ra;meta.main", "pos.eq.dec;meta.main"
    vot.resources[0].coordinate_systems.append(CooSys(ID="sys", system="ICRS", epoch="J2000"))
    ra_f.ref = dec_f.ref = "sys"
    path = tmp_path / "t.vot"
    vot.to_xml(str(path))
    _, opened = registry.run(Command("catalog.open_file", 1, {"file": {"path": str(path)}}, RequestedBy("menu")),
                             workspace)
    layer = opened.layers_created[0]
    for params in ({"row": 1}, {"layer": layer, "row": 5}, {"layer": layer, "row": 1}):
        seen.result(registry.run(Command("object.profile", 1, params, RequestedBy("menu")), workspace)[1])
    # PROFILE_AMBIGUOUS_TARGET (eta Tau e la nebulosa GN 03.44.2, risposta vera)
    with pytest.raises(ObjectProfileError) as info:
        build(ProfileTarget(position=at(*ETA_TAU)), cache=cache)
    seen.error(info.value)
    # PROFILE_PLANETS_EXCLUDED (51 Peg b alla posizione di 51 Peg, risposta vera)
    seen.profile(build(ProfileTarget(position=at(*PEG)), sections=("identity",), cache=cache))
    # SED: tutti i motivi dei punti e SED_HIGH_PROPER_MOTION (51 Peg, Vega, TRAPPIST-1: risposte vere)
    for name in ("51 Peg", "Vega", "TRAPPIST-1"):
        prof = build(ProfileTarget(name=name), sections=("photometry",), cache=cache)
        seen.profile(prof)
        seen.sed(op.build_sed(op.sed_points_from(prof.resolved.simbad.magnitudes, "simbad", provenance={})))
        seen.points(prof)
    # PROFILE_NO_PHOTOMETRY: identificativo 2MASS senza righe nel catalogo (risposta sintetica vuota)
    services.overrides[("irsa", "designation = '22572795+2046077'")] = lambda q: votable(
        [("designation", "char", None)], [])
    seen.profile(build(ProfileTarget(name="51 Peg"), sections=("photometry",), cache=cache, refresh=True))
    services.overrides.clear()
    # PROFILE_POSITIONAL_MATCH simbad_candidate; PROFILE_NO_GAIA no_counterpart (Vega)
    seen.profile(build(ProfileTarget(position=at(*VEGA)), cache=cache))
    # catalog_match (Vega con 36″) e several_candidates (risposta sintetica con due sorgenti)
    seen.profile(build(ProfileTarget(name="Vega"), sections=("astrometry",), crossmatch_radius=36 * u.arcsec,
                       cache=cache))
    services.overrides[("gaia", "CIRCLE('ICRS', 279.2")] = lambda q: votable(
        GAIA_CONE, [[1, VEGA[0], VEGA[1], 17.0], [2, VEGA[0], VEGA[1], 18.0]])
    seen.profile(build(ProfileTarget(name="Vega"), sections=("astrometry",), crossmatch_radius=3 * u.arcsec,
                       cache=cache, refresh=True))
    services.overrides.clear()
    # PROFILE_GAIA_TWO_PARAMETER (eta Tau); PROFILE_TARGET_CHANGED (nome con un simbad_id diverso)
    seen.profile(build(ProfileTarget(name="eta Tau", simbad_id="* altro"), sections=("astrometry",), cache=cache))
    # PROFILE_NO_GAIA not_in_archive (l'archivio non ha il source_id indicato da SIMBAD, risposta sintetica)
    services.overrides[("gaia", "WHERE source_id = 2835207319109249920")] = lambda q: votable(
        [("source_id", "long", None)], [])
    seen.profile(build(ProfileTarget(name="51 Peg"), sections=("astrometry",), cache=cache, refresh=True))
    services.overrides.clear()
    # PROFILE_IDENTIFIER_CONFLICT (incrocio ufficiale sintetico diverso da SIMBAD)
    services.overrides[("gaia", "tmass_psc_xsc_best_neighbour")] = lambda q: votable(
        [("source_id", "long", None), ("original_ext_source_id", "char", None),
         ("angular_distance", "double", "arcsec"), ("number_of_neighbours", "int", None), ("xm_flag", "short", None)],
        [[2835207319109249920, "00000000+0000000", 0.1, 1, 8]])
    seen.profile(build(ProfileTarget(name="51 Peg"), sections=("identity",), cache=cache, refresh=True))
    services.overrides.clear()
    # SIMBAD giù: PROFILE_NO_IDENTIFIERS (nome e posizione), PROFILE_NO_PROPER_MOTION (moto proprio, epoca)
    services.overrides[("simbad", "")] = lambda q: (503, "text/plain", "giù")
    services.overrides[("gaia", "CONTAINS")] = lambda q: votable(GAIA_CONE, [])
    stub_resolver(monkeypatch)
    seen.profile(build(ProfileTarget(name="Vega"), cache=cache, refresh=True))
    seen.profile(build(ProfileTarget(position=at(*VEGA, epoch=None)), sections=("identity",), cache=cache,
                       refresh=True))
    services.overrides.clear()
    # PROFILE_NO_DISTANCE: tutte le ragioni
    prov = Provenance("t", "http://t", "t", None, None, None, None, None)
    for value, error in ((None, None), (-1.0, 0.1), (5.0, None), (1.0, 1.0)):
        plx = None if value is None else ProfileValue("parallax", value * u.mas, prov,
                                                      error=None if error is None else error * u.mas)
        seen.notes(op.distance_from(None, plx)[1])
    # NAME_NOT_FOUND del 14: identificativo sconosciuto, identificativo di più oggetti
    for name in ("No Such Object 98765",):
        with pytest.raises(VoProtocolsError) as info:
            simbad_object(name, cache=cache)
        seen.error(info.value)
    services.overrides[("simbad", "WHERE i.id = 'doppio'")] = lambda q: votable(
        [("oid", "long", None), ("main_id", "char", None), ("ra", "double", "deg"), ("dec", "double", "deg")],
        [[1, "a", 0.0, 0.0], [2, "b", 0.0, 0.0]])
    with pytest.raises(VoProtocolsError) as info:
        simbad_object("doppio", cache=cache)
    seen.error(info.value)
    missing = required() - seen.pairs
    assert not missing, f"coppie (codice, ragione) non provocate: {sorted(missing, key=str)}"


def test_profile_messages_render_in_both_languages():
    out, notes = op.distance_from(None, ProfileValue("parallax", 1.0 * u.mas, Provenance(
        "t", "http://t", "t", None, None, None, None, None), error=1.0 * u.mas, note="SIMBAD"))
    params = notes[0].params
    assert mc.message_text("PROFILE_NO_DISTANCE", params, "en") == (
        "No distance: parallax/error = 1.0 from SIMBAD, below 10.0.")
    assert mc.message_text("PROFILE_NO_DISTANCE", params, "it") == (
        "Nessuna distanza: parallasse/errore = 1.0 da SIMBAD, sotto 10.0.")
    assert notes[0][1] == "nessuna distanza: parallasse/errore = 1.0 < 10.0"
    assert sky_json is not None
