# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Comando ``object.profile`` (05 §7 e T28; 25 §3.10 e T14): registro, comando registrato, riesecuzione, sessione.

Servizi simulati con le risposte vere registrate il 2026-11-07 (``tests/analysis/profile_fakes.py``). Il comando è
del livello 2: ``default_registry`` (05) non lo contiene; lo aggiunge ``command_specs()`` del 25, come fa il 40.
"""

from __future__ import annotations

import json

import astropy.units as u
import pytest
from astropy.table import Table
from astropy.time import Time

from astrotwo.analysis.object_profile import ProfileTarget, build_profile, command_specs, profile_content
from astrotwo.core.commands import Command, RequestedBy, Session, Workspace, default_registry, sky_json
from astrotwo.core.coordinates_wcs import SkyFrame
from tests.analysis.profile_fakes import recorded, recorded_query, services  # noqa: F401


def registry_with_profile(cache):
    registry = default_registry(cache=cache)
    for spec in command_specs():
        registry.register(spec)
    return registry


def content(values: dict) -> dict:
    """Valori del profilo senza ciò che cambia a ogni esecuzione (tempi, data, cache, avvisi di rete, ``simbad_id``
    scritto nel bersaglio dopo la prima esecuzione)."""
    data = profile_content(json.loads(json.dumps(values)))
    data["target"].pop("simbad_id", None)
    return data


def run(registry, workspace, params, refresh=False):
    return registry.run(Command("object.profile", 1, params, RequestedBy("menu"), refresh), workspace)


def test_t28_default_registry_does_not_contain_the_level_2_command(cache):
    assert "object.profile" not in {s.name for s in default_registry(cache=cache).specs()}
    registry = registry_with_profile(cache)
    spec = registry.spec("object.profile")
    assert spec.network and spec.long and spec.read_only and spec.confirm and spec.command_class == "session"
    schema = registry.export_schema(["object.profile"])["commands"][0]
    json.dumps(schema)
    assert set(schema["parameters"]["properties"]) == {"name", "position", "layer", "row", "simbad_id", "sections",
                                                       "match_radius", "crossmatch_radius"}


def test_t28_the_interface_registers_the_analysis_commands(cache):
    from astrotwo.ui.main_window import register_analysis_commands

    registry = default_registry(cache=cache)
    register_analysis_commands(registry)
    register_analysis_commands(registry)  # una seconda volta non ripete la registrazione
    assert [s.name for s in registry.specs()].count("object.profile") == 1


def test_t28_t14_name_profile_registered_replayed_and_refreshed(services, cache):
    registry = registry_with_profile(cache)
    workspace = Workspace()
    before = workspace.state
    registered, result = run(registry, workspace, {"name": "51 Peg"})
    assert result.status == "ok", result.error
    assert registered.parameters["simbad_id"] == "*  51 Peg"  # scritto nel comando registrato
    assert registered.parameters["match_radius"] == {"value": 10.0, "unit": "arcsec"}
    assert registered.parameters["crossmatch_radius"] == {"value": 2.0, "unit": "arcsec"}
    assert registered.parameters["sections"] == ["identity", "astrometry", "photometry"]
    assert workspace.state is before and result.layers_created == ()  # sola lettura
    direct = build_profile(ProfileTarget(name="51 Peg"), cache=cache)
    assert content(result.values)["sections"] == content(direct.as_dict())["sections"]
    assert {p["origin"].rsplit("/", 2)[-2] for p in result.provenance} == {"simbad", "gaia", "exoplanet", "irsa"}
    assert len(result.network_fingerprint) == 3
    # riesecuzione: stesse richieste dalla cache, nessuna nuova richiesta ai servizi, stessi valori; solo la SED di
    # VizieR (CDS giù, nessuna risposta in cache) si chiede di nuovo e resta un errore della sezione
    asked = services.count() - services.count("vizier")
    _, again = registry.run(registered, workspace)
    assert again.status == "ok" and services.count() - services.count("vizier") == asked
    assert content(again.values) == content(result.values)
    assert [f["sha256"] for f in again.network_fingerprint] == [f["sha256"] for f in result.network_fingerprint]
    assert all(p["from_cache"] for p in again.provenance)
    # con refresh: di nuovo dalla rete, DATA_REFRESHED fresh
    refreshed = Command(registered.name, 1, registered.parameters, RequestedBy("history"), True)
    _, fresh = registry.run(refreshed, workspace)
    assert fresh.status == "ok" and services.count() - services.count("vizier") > asked
    assert fresh.warnings[-1].code == "DATA_REFRESHED" and fresh.warnings[-1].params == {"reason": "fresh"}
    assert content(fresh.values) == content(result.values)


def test_t28_session_saved_and_replayed(services, cache, tmp_path):
    session = Session(registry_with_profile(cache))
    first = session.run(Command("object.profile", 1, {"name": "eta Tau"}, RequestedBy("menu")))
    assert first.status == "ok"
    path = tmp_path / "p.astrotwo.json"
    session.save(path, app_version="0.0.0")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert '"simbad_id": "* eta Tau"' in json.dumps(saved, ensure_ascii=False)
    reopened = Session.load(path, registry_with_profile(cache))
    report = reopened.replay()
    assert report.stop is None and report.replayed == (1,)
    replayed = reopened.history.entries[-1].result
    assert content(replayed.values) == content(first.values)


def test_t28_position_target_and_catalog_row(services, cache, tmp_path):
    registry = registry_with_profile(cache)
    workspace = Workspace()
    vega = SkyFrame.from_lonlat(279.234734787025 * u.deg, 38.783688956244 * u.deg, "icrs", epoch=Time("J2000.0"))
    registered, result = run(registry, workspace, {"position": sky_json(vega), "sections": ["identity"]})
    assert result.status == "ok", result.error
    assert registered.parameters["simbad_id"] == "* alf Lyr"
    assert result.values["resolved"]["method"] == "simbad_candidate"
    assert any(w.code == "PROFILE_POSITIONAL_MATCH" for w in result.warnings)
    # una riga di catalogo vale per posizione (25 §3.10): stessa stella da un VOTable con COOSYS ICRS J2000
    table = Table({"ra": [279.234734787025], "dec": [38.783688956244]})
    table["ra"].unit = table["dec"].unit = u.deg
    path = tmp_path / "vega.vot"
    from astropy.io.votable import from_table

    votable = from_table(table)
    field_ra, field_dec = votable.get_first_table().fields
    field_ra.ucd, field_dec.ucd = "pos.eq.ra;meta.main", "pos.eq.dec;meta.main"
    from astropy.io.votable.tree import CooSys

    coosys = CooSys(ID="sys", system="ICRS", epoch="J2000")
    votable.resources[0].coordinate_systems.append(coosys)
    field_ra.ref = field_dec.ref = "sys"
    votable.to_xml(str(path))
    _, opened = registry.run(Command("catalog.open_file", 1, {"file": {"path": str(path)}},
                                         RequestedBy("menu")), workspace)
    assert opened.status == "ok", opened.error
    layer = opened.layers_created[0]
    _, by_row = run(registry, workspace, {"layer": layer, "row": 0, "sections": ["identity"]})
    assert by_row.status == "ok", by_row.error
    assert by_row.values["target"]["origin"] == f"riga 0 del livello {layer}"
    assert by_row.values["resolved"]["main_id"] == "* alf Lyr"


@pytest.mark.parametrize("params, reason", [
    ({}, "none"), ({"name": "Vega", "simbad_id": None, "layer": None, "row": 3}, "row_without_layer"),
    ({"name": "Vega", "position": {"lon": {"value": 1.0, "unit": "deg"}, "lat": {"value": 2.0, "unit": "deg"},
                                   "frame": "icrs", "epoch": "J2000.0"}}, "several")])
def test_t28_invalid_targets_are_errors(cache, params, reason):
    registry = registry_with_profile(cache)
    _, result = run(registry, Workspace(), params)
    assert result.status == "error" and result.error.code == "PROFILE_TARGET_INVALID"
    assert result.error.params["reason"] == reason


def test_t28_ambiguous_target_is_an_error_with_the_list(services, cache):
    registry = registry_with_profile(cache)
    eta = SkyFrame.from_lonlat(56.871152303749994 * u.deg, 24.105135651944444 * u.deg, "icrs", epoch=Time("J2000.0"))
    _, result = run(registry, Workspace(), {"position": sky_json(eta)})
    assert result.status == "error" and result.error.code == "PROFILE_AMBIGUOUS_TARGET"
    assert [" ".join(c["main_id"].split()) for c in result.error.params["candidates"]] == ["* eta Tau", "GN 03.44.2"]
    # l'utente sceglie: lo stesso comando con simbad_id parte da quell'oggetto (risposta registrata per il nome)
    services.overrides[("simbad", "WHERE i.id = '* eta Tau'")] = lambda q: recorded(
        "simbad", recorded_query("simbad", "WHERE i.id = 'eta Tau'"))
    _, chosen = run(registry, Workspace(), {"position": sky_json(eta), "simbad_id": "* eta Tau",
                                            "sections": ["identity"]})
    assert chosen.status == "ok", chosen.error
    assert chosen.values["resolved"]["main_id"] == "* eta Tau"
