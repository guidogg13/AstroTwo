# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 05 con codice + ``params`` (D40-3; ``40`` §3.7.1, T18–T19; ``05`` §10.1).

Provoca ogni errore e avviso del registro e della sessione; ogni messaggio è controllato contro il catalogo
(voce, ``reason``, nome e tipo dei parametri, testi senza segnaposto rimasti) e si verifica la copertura di tutte le
coppie (codice, ragione) del modulo, il testo italiano invariato e i messaggi annidati.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.table import Table

from astrotwo import messages_catalog as mc
from astrotwo.core import commands, hips
from astrotwo.core.coordinates_wcs import CoordinatesWcsError
from astrotwo.core.commands import (
    CancelToken,
    Command,
    CommandError,
    CommandRegistry,
    CommandSpec,
    Outcome,
    P,
    ResultMessage,
    Session,
    Workspace,
    default_registry,
    shown_order,
)
from tests.core.test_commands import WINDOW, build_session, files, pix, registry, run, sky  # noqa: F401
from astrotwo.core.moc import CircleRegion, moc_from_region
from tests.core.test_commands_hips_display import ORDER, origin_tile, serve_fits_survey
from tests.core.test_commands_image_base import header, write
from tests.message_helpers import catalog_combinations, check_error, check_message

OWN_CODES = (
    "COMMAND_PARAMETER_INVALID", "LAYER_UNKNOWN", "COMMAND_UNKNOWN", "COMMAND_VERSION_UNSUPPORTED",
    "COMMAND_CANCELLED", "SESSION_INVALID", "SESSION_SCHEMA_UNSUPPORTED", "SESSION_FILE_MISSING",
    "SESSION_FILE_CHANGED", "SESSION_REPLAY_FAILED", "SESSION_NETWORK_DATA_DIFFERS", "SESSION_FINGERPRINT_CHANGE",
    "SESSION_STATE_DIFFERS", "SESSION_STATE_DIFFERENCE", "HIPS_DISPLAY_FALLBACK", "HIPS_DISPLAY_LIMITS_UNDEFINED",
    "TABLE_SORT_UNSUPPORTED", "POSITION_COLUMNS_REQUIRED", "VIEW_UNDEFINED", "OUT_OF_SKY", "MODULE_NOTE",
)
#: Sotto-voci di codici condivisi che solo il 05 solleva o restituisce.
SHARED = {("WCS_INVALID", "no_celestial_coordinates"), ("WCS_INVALID", "absent"),
          ("WCS_INVALID", "absent_with_reasons"), ("WCS_MISSING", "pixel_grid_overlay"), ("NO_WCS", "distance")}


class Seen:
    """Coppie (codice, reason) incontrate, ognuna controllata contro il catalogo."""

    def __init__(self) -> None:
        self.pairs: set[tuple[str, str | None]] = set()

    def message(self, message: ResultMessage | None) -> ResultMessage:
        assert message is not None
        self.pairs.add(check_message(message.code, message.params, message.text))
        return message

    def error(self, session: Session, name: str, parameters: dict, version: int = 1) -> ResultMessage:
        result = session.run(Command(name, version, parameters))
        assert result.status == "error", (name, parameters, result)
        return self.message(result.error)

    def raised(self, func, *args, **kwargs) -> CommandError:
        with pytest.raises(CommandError) as info:
            func(*args, **kwargs)
        self.pairs.add(check_error(info.value))
        return info.value


def custom_registry() -> CommandRegistry:
    """Registro con comandi di prova per i casi che il registro vero non raggiunge."""
    custom = CommandRegistry()

    def spec(name, parameters=(), executor=None):
        return CommandSpec(name, 1, "test", "prova", (), tuple(parameters), "session", executor=executor)

    def boom(ctx, p):
        raise ValueError("rifiutato dal modulo")

    custom.register(spec("test.quantity", [P("angle", "quantity", "a", "a", physical_type="angle", minimum=1.0,
                                             range_unit="deg")]))
    custom.register(spec("test.list", [P("items", "list", "a", "a", item=P("x", "integer", "x", "x"), max_items=2)]))
    custom.register(spec("test.url", [P("url", "url", "a", "a")]))
    custom.register(spec("test.boom", executor=boom))
    return custom


def test_italian_text_is_unchanged_and_catalog_renders_both_languages(registry):
    error = Seen().raised(registry.validate, Command("catalog.load_region", 1, {
        "catalog": "II/246/out", "center": sky(10.0, 41.0), "radius": {"value": 5.0, "unit": "m"}}))
    assert error.message == "radius: unità 'm' (length) non convertibile in angle"
    assert error.params == {"reason": "unit_not_convertible", "parameter": "radius", "unit": "m",
                            "physical_type": "length", "expected": ["angle"]}
    assert mc.message_text(error.code, error.params, "en") == (
        "radius: the unit m (length) is not convertible into angle.")
    assert mc.message_text(error.code, error.params, "it") == (
        "radius: l'unità m (length) non è convertibile in angle.")
    quantity = Seen().raised(custom_registry().validate, Command("test.quantity", 1, {"angle": {"value": 0.5,
                                                                                               "unit": "deg"}}))
    assert quantity.params["value"] == {"value": 0.5, "unit": "deg"} and quantity.params["limit"] == {
        "value": 1.0, "unit": "deg"}
    assert mc.message_text(quantity.code, quantity.params, "en") == "angle: 0.5 deg is out of range: must be ≥ 1.0 deg."


def test_validation_errors_cover_every_reason(registry, files):
    seen = Seen()
    custom = custom_registry()
    s = build_session(registry, files)
    base = {"catalog": "II/246/out", "center": sky(10.0, 41.0), "radius": {"value": 5.0, "unit": "arcmin"}}

    def bad(name, **parameters):
        seen.error(s, name, parameters)

    center = base["center"]
    for name, parameters in [
        ("image.open", {}),  # required
        ("view.set_zoom", {"scale": {"value": 1.0, "unit": ""}}),  # unit_missing
        ("view.set_zoom", {"scale": {"value": 1.0, "unit": "zzz"}}),  # unit_invalid
        ("view.set_zoom", {"scale": {"value": 1.0, "unit": "m"}}),  # unit_not_convertible
        ("view.set_zoom", {"scale": 1.0}),  # quantity_form
        ("layer.set_opacity", {"layer": "L1", "opacity": "x"}),  # not_finite
        ("layer.set_opacity", {"layer": "L1", "opacity": 2.0}),  # above_maximum
        ("image.open", {"file": {"path": "/x"}, "gamma": 0.0}),  # file_unreadable (first)
        ("catalog.load_region", {**base, "max_rows": 0}),  # below_minimum
        ("view.set_zoom", {"scale": {"value": 0.0, "unit": "deg"}}),  # not_above_minimum_quantity
        ("view.set_zoom", {"scale": {"value": 200.0, "unit": "deg"}}),  # above_maximum_quantity
        ("catalog.load_region", {**base, "center": {**center, "epoch": "X"}}),  # epoch_form
        ("catalog.load_region", {**base, "center": {**center, "epoch": "Jabc"}}),  # epoch_unreadable
        ("catalog.load_region", {**base, "center": {**center, "epoch": 5}}),  # time_form
        ("catalog.load_region", {**base, "center": {**center, "epoch": {"value": 1, "format": "x", "scale": "utc"}}}),
        ("catalog.load_region", {**base, "center": {**center, "epoch": {"value": 1, "format": "jd", "scale": "x"}}}),
        ("catalog.load_region", {**base, "center": {**center, "epoch": {"value": 5, "format": "isot",
                                                                         "scale": "utc"}}}),  # time_isot_text
        ("catalog.load_region", {**base, "center": 5}),  # position_form
        ("catalog.load_region", {**base, "center": {**center, "frame": ""}}),  # frame_name
        ("catalog.load_region", {**base, "center": sky(10.0, 41.0, reason="  ")}),  # epoch_reason_missing
        ("cursor.read", {"position": 5}),  # pixel_form
        ("cursor.read", {"position": {"x": 1.0, "y": 1.0, "convention": "fits"}}),  # pixel_convention
        ("image.open", {"file": 5}),  # file_form
        ("image.open", {"file": {"path": "rel.fits"}}),  # path_not_absolute
        ("layer.remove", {"layer": "x"}),  # layer_form
        ("layer.remove", {"layer": "L9"}),  # LAYER_UNKNOWN in_parameter
        ("image.set_display", {"layer": "L2", "vmin": 0.0, "vmax": 1.0}),  # layer_kind
        ("image.open", {"file": {"path": files["image"]}, "stretch": "x"}),  # choice
        ("image.open", {"file": {"path": files["image"]}, "hdu": "a"}),  # integer_required
        ("layer.set_visible", {"layer": "L1", "visible": 5}),  # boolean_required
        ("image.open", {"file": {"path": files["image"]}, "palette": 5}),  # string_required
        ("catalog.select", {"layer": "L2", "rows": 5}),  # list_required
        ("view.set_center", {"position": sky(1.0, 1.0), "window": 5}),  # record_required
        ("view.set_center", {"position": sky(1.0, 1.0), "window": {"bogus": 1}}),  # field_unknown
        ("layer.list", {"bogus": 1}),  # parameter_unexpected
        ("catalog.select", {"layer": "L2", "rows": [99]}),  # rows_out_of_range
        ("table.sort", {"layer": "L2", "column": "nope"}),  # column_unknown
        ("catalog.rows", {"layer": "L2", "columns": ["nope"]}),  # columns_unknown
        ("layer.move", {"layer": "L1", "position": 99}),  # position_beyond
        ("measure.distance", {}),  # distance_form
        ("measure.distance", {"sky1": sky(1.0, 1.0)}),  # sky_form_incomplete
        ("measure.distance", {"sky1": sky(1.0, 1.0), "sky2": sky(2.0, 2.0), "snap": True}),  # snap_needs_pixels
        ("measure.distance", {"layer": "L1", "p1": pix(1, 1)}),  # pixel_form_incomplete
        ("measure.distance", {"layer": "L1", "p1": pix(1, 1), "p2": pix(2, 2), "snap": True}),  # box_size_required
    ]:
        bad(name, **parameters)
    # parametri che non sono un oggetto, grandezza sotto il minimo, lista troppo lunga, indirizzo non http(s)
    seen.raised(registry.validate, Command("layer.list", 1, 5))  # parameters_form
    seen.raised(custom.validate, Command("test.quantity", 1, {"angle": {"value": 0.5, "unit": "deg"}}))
    seen.raised(custom.validate, Command("test.list", 1, {"items": [1, 2, 3]}))  # list_too_long
    seen.raised(custom.validate, Command("test.url", 1, {"url": "ftp://x"}))  # url_form
    seen.raised(registry.validate, Command("image.open", 1, {"file": {"path": files["image"]}, "gamma": 0.0}))
    # numero sotto il minimo (esclusivo)
    # un TypeError/ValueError di un modulo senza codice
    boom = Session(custom).run(Command("test.boom", 1, {}))
    assert boom.error.params == {"reason": "module_rejected", "error_type": "ValueError",
                                 "detail": "rifiutato dal modulo"}
    seen.message(boom.error)
    needed = {(c, r) for c, r in catalog_combinations(["COMMAND_PARAMETER_INVALID"]) if r is not None}
    assert needed <= seen.pairs, sorted(needed - seen.pairs)
    assert ("COMMAND_PARAMETER_INVALID", "not_above_minimum") in seen.pairs


def test_unknown_and_unbound_commands_and_versions(registry):
    seen = Seen()
    assert seen.raised(registry.spec, "nope.x").params == {"command": "nope.x"}
    unbound = Session(registry).run(Command("ui.set_tool", 1, {"tool": "pan"}))
    assert unbound.error.params == {"reason": "not_bound", "command": "ui.set_tool", "module": "40"}
    seen.message(unbound.error)
    seen.raised(registry.validate, Command("layer.list", 2, {}))
    seen.raised(Workspace().state.layer, "L1")
    token = CancelToken()
    token.cancel()
    before = registry.run(Command("layer.list", 1, {}), Workspace(), token)[1]
    assert before.status == "cancelled" and before.error.params == {"reason": "before_start"}
    seen.message(before.error)
    assert ("COMMAND_UNKNOWN", None) in seen.pairs and ("COMMAND_VERSION_UNSUPPORTED", None) in seen.pairs
    assert ("LAYER_UNKNOWN", None) in seen.pairs


def test_discarded_and_replay_cancellation(registry, files, tmp_path):
    seen = Seen()
    s = Session(registry)
    run(s, "catalog.open_file", file={"path": files["catalog"]})
    token = CancelToken()
    result = s.run(Command("image.open", 1, {"file": {"path": files["image"]}}), cancel=token,
                   progress=lambda report: token.cancel() if report.step == 2 else None)
    assert result.status == "cancelled" and result.error.params == {"reason": "discarded"}
    seen.message(result.error)
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    cancelled = CancelToken()
    cancelled.cancel()
    report = Session.load(path, registry).replay(cancel=cancelled)
    assert report.status == "cancelled" and report.stop.params == {"reason": "replay"}
    seen.message(report.stop)


def test_session_file_errors(registry, files, tmp_path):
    seen = Seen()
    s = build_session(registry, files)
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    original = json.loads(path.read_text())
    # file di sessione: illeggibile, struttura, comando non valido, schema più recente
    path.write_text("{non json")
    assert seen.raised(Session.load, path, registry).params["reason"] == "unreadable"
    path.write_text(json.dumps({"format": "other"}))
    assert seen.raised(Session.load, path, registry).params == {"reason": "structure"}
    path.write_text(json.dumps({**original, "commands": [{}]}))
    assert seen.raised(Session.load, path, registry).params["reason"] == "command"
    path.write_text(json.dumps({**original, "schema_version": 99}))
    assert seen.raised(Session.load, path, registry).params == {"schema_version": 99, "app_version": 1}
    # comando non registrato e versione non supportata alla riesecuzione
    data = json.loads(json.dumps(original))
    data["commands"][0]["command"]["name"] = "nope.x"
    path.write_text(json.dumps(data))
    stop = Session.load(path, registry).replay().stop
    assert stop.params == {"reason": "in_session", "number": 1, "command": "nope.x"}
    seen.message(stop)
    data = json.loads(json.dumps(original))
    data["commands"][0]["command"]["version"] = 2
    path.write_text(json.dumps(data))
    stop = Session.load(path, registry).replay().stop
    assert stop.params == {"reason": "in_session", "number": 1, "command": "image.open", "version": "2",
                           "registered": 1}
    seen.message(stop)
    # stato finale diverso (messaggi annidati)
    data = json.loads(json.dumps(original))
    data["final_state"]["layers"][1]["opacity"] = 0.25
    path.write_text(json.dumps(data))
    warning = Session.load(path, registry).replay().warnings[0]
    assert warning.code == "SESSION_STATE_DIFFERS"
    assert warning.params["differences"][0]["params"] == {"path": "layers[1].opacity", "recorded": "0.25",
                                                          "found": "0.5"}
    seen.message(warning)
    seen.pairs.add(check_message("SESSION_STATE_DIFFERENCE", warning.params["differences"][0]["params"]))
    assert mc.message_text(warning.code, warning.params, "en").endswith("layers[1].opacity: 0.25 → 0.5")
    # file cambiato e file mancante
    path.write_text(json.dumps(original))
    raw = bytearray(open(files["image"], "rb").read())
    raw[-1] ^= 0xFF
    open(files["image"], "wb").write(bytes(raw))
    stop = Session.load(path, registry).replay().stop
    assert stop.code == "SESSION_FILE_CHANGED" and stop.params["command"] == "image.open"
    seen.message(stop)
    (tmp_path / "img.fits").rename(tmp_path / "gone.fits")
    stop = Session.load(path, registry).replay().stop
    assert stop.code == "SESSION_FILE_MISSING" and stop.params["path"] == files["image"]
    seen.message(stop)
    assert mc.message_text(stop.code, stop.params, "it") == f"#1 image.open: il file {files['image']} manca."


def flaky_registry(state: dict) -> CommandRegistry:
    """Comando che cambia esito e impronta di rete tra la prima esecuzione e la riesecuzione."""
    custom = CommandRegistry()

    def run_it(ctx, p):
        if state["fail"]:
            raise ValueError("ora fallisce")
        return Outcome(network_fingerprint=[dict(f) for f in state["fingerprints"]])

    custom.register(CommandSpec("test.flaky", 1, "test", "prova", (), (), "session", executor=run_it, network=True))
    return custom


def test_replay_failed_and_network_data_differs(tmp_path):
    seen = Seen()
    state = {"fail": False, "fingerprints": [{"sha256": "aa", "origin": "https://x", "retrieved_at": "2026-10-25",
                                              "from_cache": False, "rows": 3}]}
    custom = flaky_registry(state)
    s = Session(custom)
    assert s.run(Command("test.flaky", 1, {})).status == "ok"
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    state["fingerprints"] = [{"sha256": "bb", "origin": "https://y", "retrieved_at": "2026-10-26", "from_cache": False,
                              "rows": None}]
    warning = Session.load(path, custom).replay().warnings[0]
    assert warning.code == "SESSION_NETWORK_DATA_DIFFERS"
    change = warning.params["changes"][0]
    assert change["code"] == "SESSION_FINGERPRINT_CHANGE"
    assert change["params"]["rows_before"] == "3" and change["params"]["rows_after"] == "null"
    seen.message(warning)
    seen.pairs.add(check_message(change["code"], change["params"], change["text"]))
    assert "impronta aa → bb, origine https://x del 2026-10-25 → https://y del 2026-10-26, righe 3 → None" in warning.text
    assert "fingerprint aa → bb" in mc.message_text(warning.code, warning.params, "en")
    state["fingerprints"] = []  # numero di risposte diverso
    warning = Session.load(path, custom).replay().warnings[0]
    assert warning.params == {"reason": "count_differs", "number": 1, "command": "test.flaky"}
    seen.message(warning)
    state["fingerprints"] = [{"sha256": "aa", "origin": "https://x", "retrieved_at": "2026-10-25", "from_cache": False,
                              "rows": 3}]
    state["fail"] = True  # comando prima ok, ora in errore
    stop = Session.load(path, custom).replay().stop
    assert stop.code == "SESSION_REPLAY_FAILED" and stop.params["error"]["code"] == "COMMAND_PARAMETER_INVALID"
    seen.message(stop)
    assert "era ok e ora fallisce" in mc.message_text(stop.code, stop.params, "it")
    assert {("SESSION_NETWORK_DATA_DIFFERS", None), ("SESSION_NETWORK_DATA_DIFFERS", "count_differs"),
            ("SESSION_REPLAY_FAILED", None)} <= seen.pairs


def test_image_without_coordinates(registry, tmp_path, monkeypatch):
    seen = Seen()
    s = Session(registry)
    assert run(s, "view.set_zoom", scale={"value": 10, "unit": "deg"}, window=WINDOW).status == "ok"
    plain = write(tmp_path / "plain.fits", None)
    opened = run(s, "image.open", file={"path": plain})
    warnings = {w.code: w for w in opened.warnings}
    assert warnings["WCS_MISSING"].params["reason"] == "pixel_grid_overlay"
    seen.message(warnings["WCS_MISSING"])
    problem = s.workspace.state.view.geometry.problem
    assert problem.code == "WCS_INVALID" and problem.params["reason"] == "absent_with_reasons"
    assert problem.params["reasons"][0]["code"] == "WCS_MISSING"
    seen.message(problem)
    assert mc.message_text(problem.code, problem.params, "en").startswith(
        "The WCS is missing or not valid: no celestial coordinates (")
    read = s.run(Command("cursor.read", 1, {"position": pix(5, 5), "order": None}))
    assert read.values["wcs_problem"] == problem.to_json() and read.warnings[0] == problem
    pointer = s.run(Command("simbad.pointer", 1, {"position": pix(5, 5), "radius": {"value": 5, "unit": "arcsec"}}))
    assert pointer.error.code == "WCS_INVALID" and pointer.error.params == dict(problem.params)
    # senza avvisi del modulo 11 il motivo è la sola assenza
    layer = SimpleNamespace(data=SimpleNamespace(wcs=None, warnings=()), derived={})
    seen.message(commands._wcs_problem(layer))
    # WCS presente ma non utilizzabile per la vista: la causa è un messaggio annidato
    def refuse(*args, **kwargs):
        raise CoordinatesWcsError("WCS_INVALID", "matrice singolare", params={"reason": "singular_matrix"})

    other = Session(registry)
    run(other, "view.set_zoom", scale={"value": 10, "unit": "deg"}, window=WINDOW)
    monkeypatch.setattr(commands, "make_view_wcs", refuse, raising=False)
    monkeypatch.setattr("astrotwo.core.coordinates_wcs.make_view_wcs", refuse)
    opened = run(other, "image.open", file={"path": write(tmp_path / "ok.fits", header())})
    invalid = next(w for w in opened.warnings if w.params.get("reason") == "no_celestial_coordinates")
    assert invalid.params["cause"]["code"] == invalid.params["cause_code"] == "WCS_INVALID"
    seen.message(invalid)
    assert invalid.text.startswith("WCS non valido (")
    assert mc.message_text(invalid.code, invalid.params, "en") == (
        "The WCS is not valid (WCS_INVALID: The pixel scale matrix is singular or not finite.): no celestial "
        "coordinates.")
    # misura di distanza su un'immagine senza WCS
    result = s.run(Command("measure.distance", 1, {"layer": "L1", "p1": pix(1, 1), "p2": pix(5, 5)}))
    assert result.error.code == "NO_WCS" and result.error.params == {"reason": "distance", "layer": "L1"}
    seen.message(result.error)
    assert SHARED <= seen.pairs, sorted(SHARED - seen.pairs)


def test_view_and_table_messages(registry, tmp_path):
    seen = Seen()
    s = Session(registry)
    seen.message(s.run(Command("cursor.read", 1, {"position": pix(5, 5), "order": None})).error)  # VIEW_UNDEFINED
    assert run(s, "view.set_center", position=sky(0.0, 0.0), window={"width": 800, "height": 400}).status == "ok"
    assert run(s, "view.set_zoom", scale={"value": 360.0 / 800, "unit": "deg"},
               window={"width": 800, "height": 400}).status == "ok"
    outside = s.run(Command("cursor.read", 1, {"position": pix(1, 1), "order": None}))
    seen.message(outside.warnings[0])  # OUT_OF_SKY
    assert outside.warnings[0].code == "OUT_OF_SKY"
    # catalogo senza colonne di posizione note: da confermare
    table = Table({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    path = tmp_path / "plain.xml"
    table.write(path, format="votable")
    opened = run(s, "catalog.open_file", file={"path": str(path)})
    seen.message(next(w for w in opened.warnings if w.code == "POSITION_COLUMNS_REQUIRED"))
    # colonne non ordinabili
    multi = Table({"v": np.zeros((3, 2))})
    error = seen.raised(shown_order, multi, {"column": "v", "direction": "ascending"})
    assert error.params == {"reason": "array_column", "column": "v"}
    mixed = Table({"m": np.array([1, "a", 2.0], dtype=object)})
    error = seen.raised(shown_order, mixed, {"column": "m", "direction": "ascending"})
    assert error.params["reason"] == "not_sortable" and error.params["detail"] == str(error.__cause__)
    # avviso di un modulo senza codice strutturato
    note = commands._module_warnings(["testo semplice"])[0]
    assert note.params == {"note": "testo semplice"}
    seen.message(note)
    required = {(c, r) for c, r in catalog_combinations(OWN_CODES) if r is not None or not mc.CATALOG[c].variants}
    required -= {("VIEW_UNDEFINED", "export"), ("OUT_OF_SKY", "distance_point")}  # sotto-voce del 41 (provata in tests/ui/test_messages_ui.py)
    missing = {p for p in required if p[0] in {"VIEW_UNDEFINED", "OUT_OF_SKY", "POSITION_COLUMNS_REQUIRED",
                                                "TABLE_SORT_UNSUPPORTED", "MODULE_NOTE"}} - seen.pairs
    assert not missing, sorted(missing, key=str)


def test_hips_display_messages(cache, service, monkeypatch):
    seen = Seen()
    monkeypatch.setattr(hips, "survey_coverage", lambda svc, **k: hips.service_coverage(svc, **k))
    s = Session(default_registry(cache=cache))
    url = serve_fits_survey(service, missing={(ORDER, origin_tile())})
    unknown = run(s, "hips.set_survey", survey=url)  # tile mancante e copertura non nota
    assert unknown.error.params["reason"] == "coverage_unknown"
    seen.message(unknown.error)
    empty = SimpleNamespace(moc=moc_from_region(CircleRegion(SkyCoord(40 * u.deg, 30 * u.deg), 8 * u.deg), 6).moc
                            .intersection(moc_from_region(CircleRegion(SkyCoord(220 * u.deg, -30 * u.deg),
                                                                       8 * u.deg), 6).moc))
    monkeypatch.setattr(hips, "survey_coverage", lambda svc, **k: (empty, ()))
    none = run(s, "hips.set_survey", survey=url)
    assert none.error.params["reason"] == "coverage_empty"
    seen.message(none.error)
    coverage = moc_from_region(CircleRegion(SkyCoord(40 * u.deg, 30 * u.deg), 8 * u.deg), 6)
    monkeypatch.setattr(hips, "survey_coverage", lambda svc, **k: (coverage, ()))
    fallback = next(w for w in run(s, "hips.set_survey", survey=url).warnings if w.code == "HIPS_DISPLAY_FALLBACK")
    assert fallback.params["order"] == ORDER
    seen.message(fallback)
    assert mc.message_text(fallback.code, fallback.params, "it").startswith(f"{fallback.params['hips_id']}: il tile di ICRS")
    required = catalog_combinations(["HIPS_DISPLAY_FALLBACK", "HIPS_DISPLAY_LIMITS_UNDEFINED"])
    assert {p for p in required if p[1] is not None or not mc.CATALOG[p[0]].variants} <= seen.pairs
