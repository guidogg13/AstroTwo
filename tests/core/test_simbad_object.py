# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""``simbad_object`` del 14 (T28, sprint C2): oggetto SIMBAD esatto per identificativo, con il ripiego sul mirror.

Servizio SIMBAD simulato con le risposte vere registrate il 2026-11-07 dal mirror di Harvard (CDS irraggiungibile
quel giorno; ``tests/analysis/profile_fakes.py``). Gli attesi vengono dalle risposte registrate lette con Astropy.
"""

from __future__ import annotations

import dataclasses
import io

import astropy.units as u
import pytest
from astropy.io.votable import parse_single_table

import astrotwo.core.vo_protocols as vo
from astrotwo.core.vo_protocols import ServiceMirrors, VoProtocolsError, simbad_object
from tests.analysis.profile_fakes import RecordedServices, recorded, recorded_query, services, votable  # noqa: F401


def recorded_table(contains: str):
    return parse_single_table(io.BytesIO(recorded("simbad", recorded_query("simbad", contains)))).to_table()


def test_t28_51_peg_from_the_recorded_answers(services, cache):
    record = simbad_object("51 Peg", cache=cache)
    basic = recorded_table("WHERE i.id = '51 Peg'")
    assert record.main_id == str(basic["main_id"][0]) and record.oid == int(basic["oid"][0]) == 1472090
    assert record.basic["plx_value"] == basic["plx_value"].quantity[0] and record.basic["plx_value"].unit == u.mas
    assert record.basic["pmra"].unit == u.mas / u.yr and record.basic["coo_bibcode"] == "2020yCat.1350....0G"
    assert record.basic["rvz_err"] == 0.0001 * u.km / u.s  # float a 32 bit al decimale scritto dal servizio
    assert record.otype_description == "High Proper Motion Star"
    assert record.coords.epoch.jyear == 2000.0 and record.coords.frame_name == "icrs"
    assert len(record.identifiers) == 46 and "NAME Helvetios" in record.identifiers
    flux = recorded_table("WHERE b.main_id = '*  51 Peg'")
    assert len(record.magnitudes) == len(flux) and {m.band for m in record.magnitudes} >= {"V", "G", "J"}
    assert [r.arguments["adql"].split()[0] for r in record.requests] == ["SELECT"] * 3
    assert all(r.url == services.url("simbad") + "/sync" for r in record.requests)


def test_t28_eta_tau_has_62_identifiers_and_no_spectral_reference(services, cache):
    record = simbad_object("eta Tau", cache=cache)
    assert len(record.identifiers) == 62 and record.basic["sp_bibcode"] is None
    assert record.basic["plx_value"] == 8.09 * u.mas


def test_t28_unknown_identifier_never_falls_back(services, cache):
    with pytest.raises(VoProtocolsError) as info:
        simbad_object("No Such Object 98765", cache=cache)
    assert info.value.code == "NAME_NOT_FOUND" and info.value.params["reason"] == "simbad_identifier"
    assert services.count("simbad") == 1  # nessuna altra richiesta, nessun oggetto vicino


def test_t28_an_identifier_of_several_objects_is_not_chosen(services, cache):
    services.overrides[("simbad", "WHERE i.id = 'doppio'")] = lambda q: votable(
        [(c, "long" if c in ("oid", "nbref") else "double" if c in ("ra", "dec") else "char", None)
         for c in vo.SIMBAD_BASIC_COLUMNS] + [("description", "char", None)],
        [[1 if c == "oid" else 0.0 if c in ("ra", "dec") else 0 if c == "nbref" else "x"
          for c in vo.SIMBAD_BASIC_COLUMNS] + ["d"],
         [2 if c == "oid" else 0.0 if c in ("ra", "dec") else 0 if c == "nbref" else "y"
          for c in vo.SIMBAD_BASIC_COLUMNS] + ["d"]])
    with pytest.raises(VoProtocolsError) as info:
        simbad_object("doppio", cache=cache)
    assert info.value.code == "NAME_NOT_FOUND" and info.value.params["reason"] == "several_objects"


def test_t28_primary_down_the_mirror_answers_and_is_the_provenance(services, cache, monkeypatch):
    mirror = RecordedServices()
    try:
        services.overrides[("simbad", "")] = lambda q: (503, "text/plain", "giù")
        monkeypatch.setattr(vo, "SERVICE_MIRRORS", {"cds-simbad-tap": ServiceMirrors(
            "simbad", "SIMBAD", (mirror.url("simbad"),))})
        record = simbad_object("51 Peg", cache=cache)
        assert all(r.url == mirror.url("simbad") + "/sync" for r in record.requests)
        assert [w[0] for w in record.warnings].count("SERVICE_MIRROR_FALLBACK") == 1
        assert mirror.count("simbad") == 3
    finally:
        mirror.close()
    assert not mirror.missing


def test_t28_empty_identifier_is_refused():
    with pytest.raises(ValueError):
        simbad_object("  ")
    assert dataclasses.is_dataclass(vo.SimbadRecord)
