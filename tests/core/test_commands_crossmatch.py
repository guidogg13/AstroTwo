# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""``catalog.crossmatch`` del 05 (sprint B2, D15-10): T25 del ``05-comandi-sessione.md``.

Le coppie attese vengono dal modulo 15 chiamato direttamente sulle stesse tabelle (e quindi da astropy), mai scritte a
mano; le posizioni spostate sono costruite con ``SkyCoord.directional_offset_by``.
"""

from __future__ import annotations

import dataclasses
import socket

import astropy.units as u
import numpy as np
import pytest

import astrotwo.core.vo_protocols as vo
from astrotwo.core.catalogs import TableLimits
from astrotwo.core.commands import Command, RequestedBy, Session, default_registry
from astrotwo.core.crossmatch import crossmatch
from astrotwo.messages_catalog import message_text
from tests.core.test_crossmatch import make_table, offset, xmatch_route

RA = 56.75 + 0.01 * np.arange(8)
DEC = 24.1 + 0.0 * np.arange(8)


def run(session, name, requested_by=RequestedBy("menu"), /, **params):
    return session.run(Command(name, 1, params, requested_by))


@pytest.fixture
def session(cache):
    return Session(default_registry(cache=cache))


def two_catalogs(session, tmp_path, *, epoch_a=None, epoch_b=None, missing_a=False):
    """A: 8 stelle; B: copie spostate di 0,5″ delle stelle 0–5 (una riga in meno di A più una lontana) e una seconda
    copia a 1,5″ della stella 0 (per ``all``)."""
    lon_a = [float(x) for x in RA]
    lat_a = [float(x) for x in DEC]
    if missing_a:
        lon_a[7] = None
    make_table(tmp_path / "a.xml", lon_a, lat_a, epoch=epoch_a, ids=[f"a{k}" for k in range(8)],
               extra={"mag": ("mag", [10.0 + k for k in range(8)])})
    shifted = [offset(RA[k], DEC[k], 40.0, 0.5) for k in range(6)] + [offset(RA[0], DEC[0], 200.0, 1.5)]
    shifted.append((10.0, -30.0))  # nessuna stella di A vicina
    make_table(tmp_path / "b.xml", [p[0] for p in shifted], [p[1] for p in shifted], epoch=epoch_b,
               ids=[f"b{k}" for k in range(len(shifted))], extra={"mag": ("mag", [20.0] * len(shifted))})
    for name in ("a.xml", "b.xml"):
        assert run(session, "catalog.open_file", file={"path": str(tmp_path / name)}).status == "ok"
    return session.workspace.state.layer("L1").data, session.workspace.state.layer("L2").data


def joined_rows(session, layer_id):
    table = session.workspace.state.layer(layer_id).data.table
    return [tuple(row) for row in table.as_array().tolist()]


# =============================================================================
# best / all / none, default del raggio, unità, nuovo livello


@pytest.mark.parametrize("mode", ["best", "all", "none"])
def test_t25_modes_like_the_module(session, tmp_path, mode):
    a, b = two_catalogs(session, tmp_path)
    result = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", mode=mode)
    assert result.status == "ok", result.error
    entry = session.history.entries[-1]
    # default 2″ risolto alla registrazione (D15-10 (a)), metodo locale e ICRS di default
    assert entry.command.parameters["max_sep"] == {"value": 2.0, "unit": "arcsec"}
    assert (entry.command.parameters["method"], entry.command.parameters["frame"]) == ("local", "icrs")
    expected = crossmatch(a, b, mode, 2 * u.arcsec)
    layer = session.workspace.state.layer(result.layers_created[0])
    assert layer.kind == "catalog" and layer.source == "crossmatch" and result.layers_created == ("L3",)
    x = result.values["crossmatch"]
    joined = layer.data.table
    if mode == "none":
        assert list(joined["id"]) == [f"a{k}" for k in expected.unmatched] == ["a6", "a7"]
        assert x["unmatched"] == 2 and x["separation_column"] is None and "xmatch_sep" not in joined.colnames
    else:
        assert list(joined["id_tab1"]) == [f"a{k}" for k in expected.pairs["idx_a"]]
        assert list(joined["id_tab2"]) == [f"b{k}" for k in expected.pairs["idx_b"]]
        assert joined["xmatch_sep"].unit == u.arcsec and x["separation_column"] == "xmatch_sep"
        assert np.array_equal(np.asarray(joined["xmatch_sep"]), np.asarray(expected.pairs["sep"]))
        assert x["pairs"] == len(expected.pairs) == {"best": 6, "all": 7}[mode]
    # report salvato nel risultato (as_dict e describe del 15), posizioni della tabella A
    assert x["report"]["mode"] == mode and x["report"]["criterion"] == expected.report.criterion
    assert x["report_text"].startswith("Metodo: locale: astropy.coordinates.search_around_sky")
    assert layer.data.positions is not None and layer.data.body == "celestial"
    # tabelle d'ingresso invariate (D13-5)
    assert session.workspace.state.layer("L1").data is a and len(a.table) == 8


def test_t25_units_chosen_by_the_user(session, tmp_path):
    two_catalogs(session, tmp_path)
    by_arcsec = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", mode="all",
                    max_sep={"value": 1.0, "unit": "arcsec"})
    by_arcmin = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", mode="all",
                    max_sep={"value": 1.0 / 60.0, "unit": "arcmin"})
    by_mas = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", mode="all",
                 max_sep={"value": 100.0, "unit": "mas"})
    assert by_arcsec.values["crossmatch"]["pairs"] == by_arcmin.values["crossmatch"]["pairs"] == 6
    assert by_mas.values["crossmatch"]["pairs"] == 0 and "NO_MATCH" in [w.code for w in by_mas.warnings]
    assert session.history.entries[-1].command.parameters["max_sep"] == {"value": 100.0, "unit": "mas"}


# =============================================================================
# Regole del 15: epoche, coordinate mancanti, raggio, colonne, tetto, frame del servizio


def test_t25_epoch_differs_without_propagation(session, tmp_path):
    two_catalogs(session, tmp_path, epoch_a="J2016.0", epoch_b="J2000.0")
    result = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2")
    assert result.status == "ok"
    warning = next(w for w in result.warnings if w.code == "EPOCH_DIFFERS")
    assert warning.params == {"epoch_a": "J2016.0", "epoch_b": "J2000.0"}
    assert "J2016.0" in message_text(warning.code, warning.params, "en")
    assert result.values["crossmatch"]["report"]["epochs"] == ["J2016.0", "J2000.0"]
    assert result.values["crossmatch"]["pairs"] == 6  # stesse coppie: nessuna propagazione


def test_t25_missing_coordinates_and_no_position_columns(session, tmp_path):
    two_catalogs(session, tmp_path, missing_a=True)
    result = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", mode="none")
    assert result.status == "ok"
    warning = next(w for w in result.warnings if w.code == "COORD_MISSING")
    assert warning.params == {"excluded_a": 1, "excluded_b": 0}
    assert result.values["crossmatch"]["unmatched"] == 1  # a7 senza posizione non è tra i non appaiati
    plain = tmp_path / "plain.csv"
    plain.write_text("name,x,y\nq,1.0,2.0\n")
    assert run(session, "catalog.open_file", file={"path": str(plain)}).status == "ok"
    layers = len(session.workspace.state.layers)
    error = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L4").error
    assert error.code == "NO_COORD_COLUMNS" and error.params["which"] == "B"
    assert len(session.workspace.state.layers) == layers  # nessun livello nuovo


@pytest.mark.parametrize(("max_sep", "method", "reason"), [
    ({"value": 0.0, "unit": "arcsec"}, "local", "range_local"),
    ({"value": 200.0, "unit": "deg"}, "local", "range_local"),
    ({"value": 181.0, "unit": "arcsec"}, "cds", "range_cds"),
])
def test_t25_max_sep_invalid(session, tmp_path, max_sep, method, reason):
    two_catalogs(session, tmp_path)
    result = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", max_sep=max_sep, method=method)
    assert result.status == "error" and result.error.code == "MAX_SEP_INVALID"
    assert result.error.params["reason"] == reason
    assert "180" in message_text("MAX_SEP_INVALID", result.error.params, "it")
    assert [layer.id for layer in session.workspace.state.layers] == ["L1", "L2"]
    unit = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", max_sep={"value": 1.0, "unit": "m"})
    assert unit.error.code == "COMMAND_PARAMETER_INVALID"  # unità non angolare: validazione del 05


def test_t25_table_too_large(session, tmp_path):
    two_catalogs(session, tmp_path)
    state = session.workspace.state
    layer = state.layer("L2")
    small = dataclasses.replace(layer.data, limits=TableLimits(max_rows=3))  # tetto abbassato per la prova
    session.workspace._commit(state.replace_layer(dataclasses.replace(layer, data=small)))
    error = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2").error
    assert error.code == "TABLE_TOO_LARGE" and error.params == {"reason": "crossmatch_table", "which": "B",
                                                                  "rows": 8, "max_rows": 3}


def test_t25_cds_only_in_icrs(session, tmp_path):
    two_catalogs(session, tmp_path)
    error = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", method="cds", frame="galactic").error
    assert error.code == "COMMAND_PARAMETER_INVALID" and error.params["reason"] == "crossmatch_cds_frame"
    assert "ICRS" in message_text(error.code, error.params, "en")


def test_t25_galactic_comparison_frame(session, tmp_path):
    a, b = two_catalogs(session, tmp_path)
    result = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", mode="all", frame="galactic")
    expected = crossmatch(a, b, "all", 2 * u.arcsec, frame="galactic")
    assert result.values["crossmatch"]["report"]["frame"] == "galactic"
    assert result.values["crossmatch"]["pairs"] == len(expected.pairs)


# =============================================================================
# Riesecuzione identica (cronologia e sessione)


def test_t25_replay_identical(session, tmp_path, cache):
    two_catalogs(session, tmp_path, epoch_a="J2016.0", epoch_b="J2000.0")
    result = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", mode="all",
                 max_sep={"value": 1.8, "unit": "arcsec"})
    before = joined_rows(session, "L3")
    # Riesegui dalla cronologia: stesso comando registrato, nuovo livello con le stesse righe
    entry = session.history.entries[-1]
    again = session.run(Command(entry.command.name, entry.command.version, dict(entry.command.parameters),
                                RequestedBy("history")))
    assert again.status == "ok" and joined_rows(session, again.layers_created[0]) == before
    assert again.values["crossmatch"]["pairs"] == result.values["crossmatch"]["pairs"]
    # sessione salvata e riaperta: stesso stato, stesse righe
    path = tmp_path / "s.astrotwo.json"
    session.save(path, app_version="0.0.0")
    reopened = Session.load(path, default_registry(cache=cache))
    report = reopened.replay()
    assert report.stop is None, report.stop
    assert joined_rows(reopened, "L3") == before and joined_rows(reopened, "L4") == before


# =============================================================================
# CDS XMatch simulato: risposta, errore del servizio, servizio irraggiungibile (nessun ripiego)


def test_t25_cds_simulated(session, tmp_path, service, monkeypatch):
    a, b = two_catalogs(session, tmp_path)
    log = []
    service.routes["/xmatch"] = xmatch_route(log)
    monkeypatch.setattr(vo, "XMATCH_URL", service.url + "/xmatch")
    result = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", method="cds", mode="best")
    assert result.status == "ok", result.error
    assert log[-1][1]["selection"] == "all"  # D15-9
    local = crossmatch(a, b, "best", 2 * u.arcsec)
    joined = session.workspace.state.layer(result.layers_created[0]).data.table
    assert list(joined["id_tab2"]) == [f"b{k}" for k in local.pairs["idx_b"]]
    assert np.max(np.abs(np.asarray(joined["xmatch_sep"]) - np.asarray(local.pairs["sep"]))) <= 1e-3  # 1 mas
    assert result.values["crossmatch"]["report"]["service"] == service.url + "/xmatch"
    assert result.provenance[0]["origin"] == service.url + "/xmatch" and result.network_fingerprint
    # errore del servizio (eco delle posizioni sbagliata) → errore con la proposta del locale
    service.routes["/xmatch"] = xmatch_route(log, corrupt=True)
    error = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", method="cds", mode="all",
                max_sep={"value": 1.9, "unit": "arcsec"}).error
    assert error.code == "CROSSMATCH_SERVICE_FAILED" and error.params["reason"] == "service_error"
    assert error.params["cause"]["code"] == "SERVICE_ERROR"
    for lang, word in (("en", "local method"), ("it", "metodo locale")):
        assert word in message_text(error.code, error.params, lang)


def test_t25_cds_unreachable_no_fallback(session, tmp_path, monkeypatch):
    two_catalogs(session, tmp_path)
    with socket.socket() as s:  # porta libera, poi chiusa: connessione rifiutata subito
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    monkeypatch.setattr(vo, "XMATCH_URL", f"http://127.0.0.1:{port}/xmatch")
    result = run(session, "catalog.crossmatch", layer_a="L1", layer_b="L2", method="cds")
    assert result.status == "error" and result.error.code == "CROSSMATCH_SERVICE_FAILED"
    assert result.error.params["reason"] == "unreachable" and result.error.params["cause"]["code"] == "NET_TIMEOUT"
    text = message_text(result.error.code, result.error.params, "en")
    assert "cannot be reached" in text and "local method" in text and "no automatic fallback" in text
    assert [layer.id for layer in session.workspace.state.layers] == ["L1", "L2"]  # nessun ripiego automatico
    assert session.history.entries[-1].command.parameters["method"] == "cds"
