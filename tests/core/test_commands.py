# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del modulo 05 (``mdfiles/05-comandi-sessione.md`` §12).

Senza Qt e senza rete: servizi simulati (SIMBAD, TAP VizieR) come nei test dei moduli 10 e 13. I valori attesi
si ricalcolano chiamando nel test le stesse funzioni dei moduli (regola d'oro n. 8).
"""

import dataclasses
import json
import threading
import time

import astropy.units as u
import numpy as np
import pytest
from astropy.io import fits
from astropy.table import Table
from astropy.wcs import WCS
from mocpy import MOC

from astrotwo.core import coordinates_wcs as cw
from astrotwo.core import vo_protocols as vo
from astrotwo.core.cache import SharedCache
from astrotwo.core.commands import (
    CancelToken,
    Command,
    CommandError,
    CommandRegistry,
    CommandSpec,
    Outcome,
    RequestedBy,
    Session,
    Workspace,
    default_registry,
)
from tests.core.test_catalogs import region_tap
from tests.core.test_coordinates_wcs import simbad_table

WINDOW = {"width": 800, "height": 600}
PIXEL_MARK = 12345.678  # valore riconoscibile di un pixel: non deve finire nel file di sessione


def sky(lon, lat, frame="icrs", epoch=None, reason="posizione scritta nel test, senza epoca"):
    return {"lon": {"value": lon, "unit": "deg"}, "lat": {"value": lat, "unit": "deg"}, "frame": frame,
            "equinox": None, "obstime": None, "epoch": epoch, "epoch_reason": None if epoch else reason}


def pix(x, y):
    return {"x": float(x), "y": float(y), "convention": "numpy"}


@pytest.fixture
def files(tmp_path):
    """Immagine FITS sintetica con WCS, catalogo VOTable con UCD, MOC."""
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [56.75, 24.12]
    w.wcs.crpix = [50.5, 50.5]
    w.wcs.cdelt = [-0.001, 0.001]
    data = np.random.default_rng(1).normal(100, 5, (100, 100)).astype(np.float64)
    data[10, 10] = PIXEL_MARK
    image = tmp_path / "img.fits"
    fits.PrimaryHDU(data, header=w.to_header()).writeto(image)
    t = Table({"RA": [56.75, 56.76, 56.77], "DE": [24.12, 24.13, 24.11], "V": [5.0, 7.0, 6.0]})
    t["RA"].unit = t["DE"].unit = "deg"
    t["RA"].meta["ucd"], t["DE"].meta["ucd"] = "pos.eq.ra;meta.main", "pos.eq.dec;meta.main"
    catalog = tmp_path / "cat.xml"
    t.write(catalog, format="votable")
    moc = tmp_path / "m.fits"
    MOC.from_string("5/100 101").save(str(moc), format="fits")
    return {"image": str(image), "catalog": str(catalog), "moc": str(moc)}


@pytest.fixture
def registry(cache):
    return default_registry(cache=cache)


def run(session, command_name, requested_by=RequestedBy("menu"), /, **params):
    return session.run(Command(command_name, 1, params, requested_by))


def build_session(registry, files):
    s = Session(registry)
    assert run(s, "image.open", file={"path": files["image"]}).status == "ok"
    assert run(s, "catalog.open_file", file={"path": files["catalog"]}).status == "ok"
    assert run(s, "moc.open", file={"path": files["moc"]}).status == "ok"
    assert run(s, "view.set_zoom", scale={"value": 0.5, "unit": "arcsec"}, window=WINDOW).status == "ok"
    assert run(s, "view.set_center", position=sky(56.75, 24.12), window=WINDOW).status == "ok"
    assert run(s, "view.set_grid", visible=True).status == "ok"
    assert run(s, "layer.set_opacity", layer="L2", opacity=0.5).status == "ok"
    assert run(s, "image.set_display", layer="L1", vmin=90.0, vmax=110.0, stretch="sqrt").status == "ok"
    assert run(s, "catalog.select", layer="L2", rows=[0, 2]).status == "ok"
    return s


# =============================================================================
# T1, T2, T22 — tipi, unità, default, record


def test_t1_types_and_units(registry):
    base = {"catalog": "II/246/out", "center": sky(10.0, 41.0)}
    for unit in ("arcmin", "deg"):
        cmd = registry.validate(Command("catalog.load_region", 1, {**base, "radius": {"value": 5.0, "unit": unit}}))
        assert cmd.parameters["radius"] == {"value": 5.0, "unit": unit}  # unità conservata
    bad = [
        ("radius", {**base, "radius": {"value": 5.0}}),  # senza unità
        ("radius", {**base, "radius": {"value": 5.0, "unit": "m"}}),  # non un angolo
        ("radius", {**base, "radius": 5.0}),  # numero puro per un angolo
        ("center.epoch", {**base, "radius": {"value": 5.0, "unit": "arcmin"},
                          "center": {**sky(10.0, 41.0), "epoch_reason": None}}),  # senza epoca e senza motivo
        ("radius", {**base, "radius": {"value": 200.0, "unit": "deg"}}),  # fuori intervallo
    ]
    for parameter, params in bad:
        with pytest.raises(CommandError) as err:
            registry.validate(Command("catalog.load_region", 1, params))
        assert err.value.code == "COMMAND_PARAMETER_INVALID" and err.value.details["parameter"] == parameter
    with pytest.raises(CommandError) as err:
        registry.validate(Command("catalog.nothing", 1, {}))
    assert err.value.code == "COMMAND_UNKNOWN"
    with pytest.raises(CommandError) as err:
        registry.validate(Command("layer.set_opacity", 1, {"layer": "L1", "opacity": 0.5}), Workspace())
    assert err.value.code == "LAYER_UNKNOWN"


def test_t2_defaults_resolved(registry):
    cmd = registry.validate(Command("catalog.load_region", 1, {
        "catalog": "II/246/out", "center": sky(10.0, 41.0), "radius": {"value": 5.0, "unit": "arcmin"}}))
    assert cmd.parameters["max_rows"] == vo.DEFAULT_MAX_ROWS and cmd.parameters["force_body"] is False
    rows = registry.validate(Command("catalog.rows", 1, {"layer": "L1"}))
    assert rows.parameters == {"layer": "L1", "first": 0, "count": 10, "columns": None, "order": "table"}


def test_t22_record_and_json_forms(registry, files):
    spec = registry.spec("calc.convert_pixel_value")
    display = {"vmin": 0.0, "vmax": 100.0}
    cmd = registry.validate(Command(spec.name, 1, {"raw": 1.0, "bzero": 0.0, "bscale": 1.0, "display": display}))
    assert cmd.parameters["display"] == {"vmin": 0.0, "vmax": 100.0, "gamma": 1.0, "stretch": "linear",
                                         "palette": "gray"}
    cases = [({**display, "extra": 1}, "display.extra"), ({"vmax": 100.0}, "display.vmin")]
    for value, parameter in cases:
        with pytest.raises(CommandError) as err:
            registry.validate(Command(spec.name, 1, {"raw": 1.0, "bzero": 0.0, "bscale": 1.0, "display": value}))
        assert err.value.code == "COMMAND_PARAMETER_INVALID" and err.value.details["parameter"] == parameter
    motion = {"pm_ra_cosdec": {"value": 1.0, "unit": "m"}, "pm_dec": {"value": 1.0, "unit": "mas/yr"}}
    with pytest.raises(CommandError) as err:
        registry.validate(Command("calc.calculate_coordinates", 1, {
            "position": {"lon": {"value": 1.0, "unit": "deg"}, "lat": {"value": 1.0, "unit": "deg"},
                         "frame": "icrs"}, "targets": [{"frame": "icrs"}], "motion": motion}))
    assert err.value.details["parameter"] == "motion.pm_ra_cosdec"
    # Forme JSON di ogni tipo: scritte e rilette identiche.
    forms = Command("calc.convert_pixel_value", 1, {
        "image": "L1", "position": pix(1.5, 2.0), "position_sky": None, "display": None,
    }).to_json()
    assert Command.from_json(json.loads(json.dumps(forms))).to_json() == forms
    time_forms = ["J2016.0", {"value": [2451545.0, 0.25], "format": "jd", "scale": "tdb"},
                  {"value": "2024-02-29T18:00:00", "format": "isot", "scale": "utc"}]
    for t in time_forms:
        cmd = registry.validate(Command("calc.calculate_coordinates", 1, {
            "position": {"lon": {"value": 1.0, "unit": "deg"}, "lat": {"value": 1.0, "unit": "deg"},
                         "frame": "icrs", "epoch": t}, "targets": [{"frame": "icrs"}]}))
        assert json.loads(json.dumps(cmd.parameters["position"]["epoch"])) == t
    with pytest.raises(CommandError):
        registry.validate(Command("calc.convert_time", 1, {"time_text": "2000-01-01", "time_format": "iso",
                                                           "scale": "local"}))
    schema = registry.export_schema(["calc.convert_pixel_value"])["commands"][0]["parameters"]["properties"]
    record = schema["display"]["anyOf"][0]
    assert record["type"] == "object" and record["additionalProperties"] is False
    assert record["required"] == ["vmin", "vmax"] and set(record["properties"]) == set(display) | {
        "gamma", "stretch", "palette"}


# =============================================================================
# T3, T20 — schema JSON per il 32


def test_t3_schema(registry):
    schema = registry.export_schema()
    text = json.dumps(schema)  # JSON valido
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema" and json.loads(text) == schema
    names = [c["name"] for c in schema["commands"]]
    assert len(names) == len(set(names)) == len(registry.specs())
    for c in schema["commands"]:
        assert c["version"] == 1 and c["description"] and c["result"]["properties"]["status"]
        params = c["parameters"]
        assert params["type"] == "object" and params["additionalProperties"] is False
        for name, p in params["properties"].items():
            assert "description" in p, (c["name"], name)
    radius = next(c for c in schema["commands"] if c["name"] == "catalog.load_region")["parameters"]["properties"][
        "radius"]
    assert radius["x-physical-type"] == ["angle"] and radius["x-maximum"] == 180.0 and radius["x-range-unit"] == "deg"
    opacity = next(c for c in schema["commands"] if c["name"] == "layer.set_opacity")["parameters"]["properties"][
        "opacity"]
    assert (opacity["minimum"], opacity["maximum"]) == (0.0, 1.0)


CONFIRM = {"image.open", "catalog.open_file", "catalog.load_region", "hips.set_survey", "view.go_to",
           "image.set_display", "catalog.set_columns", "catalog.set_style", "layer.set_visible", "layer.set_opacity",
           "layer.move", "layer.remove"}
READ_ONLY_NEW = {"coords.resolve_name", "catalog.search", "catalog.describe", "catalog.rows", "layer.list"}


def test_t20_confirm_flag(registry):
    flags = {c["name"]: c["flags"] for c in registry.export_schema()["commands"]}
    assert {name for name, f in flags.items() if f["confirm"]} == CONFIRM
    for name in READ_ONLY_NEW:
        assert flags[name]["read_only"] and flags[name]["class"] == "session" and not flags[name]["confirm"]
    assert flags["coords.resolve_name"]["network"]


# =============================================================================
# T4–T6, T10, T14 — sessione


def test_t4_save_and_reopen(registry, files, tmp_path):
    s = build_session(registry, files)
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["schema_version"] == 1 and data["app_version"] == "0.1.0"
    assert {f["path"] for f in data["files"]} == set(files.values())
    assert all(len(f["sha256"]) == 64 and f["size"] > 0 for f in data["files"])
    assert repr(PIXEL_MARK) not in text and "12345" not in text  # nessun pixel nel file
    reopened = Session.load(path, registry)
    report = reopened.replay()
    assert report.status == "ok" and report.stop is None and report.warnings == ()
    assert reopened.workspace.state.state_json() == s.workspace.state.state_json()
    state = reopened.workspace.state
    assert [layer.id for layer in state.layers] == ["L1", "L2", "L3"]
    assert state.layer("L1").display["stretch"] == "sqrt" and state.layer("L2").opacity == 0.5
    assert state.layer("L2").selection == (0, 2) and state.view.grid_visible and state.view.grid is not None
    # I limiti scelti da zscale sono registrati nel comando (D41-3) e riusati alla riapertura.
    opened = s.history.entries[0].command.parameters
    assert opened["vmin"] is not None and opened["vmax"] is not None


def test_t5_file_changed(registry, files, tmp_path):
    s = build_session(registry, files)
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    raw = bytearray(open(files["image"], "rb").read())
    raw[-1] ^= 0xFF
    open(files["image"], "wb").write(bytes(raw))
    report = Session.load(path, registry).replay()
    assert report.status == "stopped" and report.stop.code == "SESSION_FILE_CHANGED"
    assert report.stop_details["expected"] != report.stop_details["found"] and report.replayed == ()


def test_t6_file_missing(registry, files, tmp_path):
    s = build_session(registry, files)
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    (tmp_path / "cat.xml").rename(tmp_path / "other.xml")
    reopened = Session.load(path, registry)
    report = reopened.replay()
    assert report.stop.code == "SESSION_FILE_MISSING" and report.replayed == (1,)
    assert [layer.id for layer in reopened.workspace.state.layers] == ["L1"]  # stato fino al comando precedente


def test_t10_layer_identifiers(registry, files, tmp_path):
    s = Session(registry)
    for _ in range(3):
        run(s, "catalog.open_file", file={"path": files["catalog"]})
    run(s, "layer.remove", layer="L2")
    assert run(s, "catalog.open_file", file={"path": files["catalog"]}).layers_created == ("L4",)
    assert [layer.id for layer in s.workspace.state.layers] == ["L1", "L3", "L4"]
    assert run(s, "layer.set_opacity", layer="L2", opacity=0.1).error.code == "LAYER_UNKNOWN"
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    reopened = Session.load(path, registry)
    assert reopened.replay().status == "ok"
    assert [layer.id for layer in reopened.workspace.state.layers] == ["L1", "L3", "L4"]


def test_t14_state_differs(registry, files, tmp_path):
    s = build_session(registry, files)
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    data = json.loads(path.read_text())
    data["final_state"]["layers"][1]["opacity"] = 0.25
    path.write_text(json.dumps(data))
    report = Session.load(path, registry).replay()
    assert report.status == "ok" and [w.code for w in report.warnings] == ["SESSION_STATE_DIFFERS"]
    assert report.warning_details[0]["state_differences"] == [
        {"path": "layers[1].opacity", "recorded": 0.25, "found": 0.5}]


def test_t12_versions(registry, files, tmp_path):
    s = Session(registry)
    run(s, "catalog.open_file", file={"path": files["catalog"]})
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    data = json.loads(path.read_text())
    data["commands"][0]["command"]["version"] = 2
    path.write_text(json.dumps(data))
    assert Session.load(path, registry).replay().stop.code == "COMMAND_VERSION_UNSUPPORTED"
    data["schema_version"] = 99
    path.write_text(json.dumps(data))
    with pytest.raises(CommandError) as err:
        Session.load(path, registry)
    assert err.value.code == "SESSION_SCHEMA_UNSUPPORTED"
    path.write_text("{non json")
    with pytest.raises(CommandError) as err:
        Session.load(path, registry)
    assert err.value.code == "SESSION_INVALID"
    assert run(Session(registry), "layer.list", **{}).status == "ok"
    assert registry.execute(Command("layer.list", 2, {}), Workspace()).error.code == "COMMAND_VERSION_UNSUPPORTED"


# =============================================================================
# T7, T8 — letture passive, annullamento


def test_t7_passive_reads(registry, files):
    s = Session(registry)
    run(s, "image.open", file={"path": files["image"]})
    run(s, "view.set_zoom", scale={"value": 1.0, "unit": "arcsec"}, window=WINDOW)
    before = len(s.history)
    for k in range(100):
        result = run(s, "cursor.read", RequestedBy("mouse"), position=pix(300 + k, 200))
        assert result.status == "error" and result.error.code == "VIEW_UNDEFINED"  # vista senza centro
    run(s, "view.set_center", position=sky(56.75, 24.12), window=WINDOW)
    read = run(s, "cursor.read", RequestedBy("mouse"), position=pix(400, 300))
    assert read.status == "ok" and read.values["pixel"]["layer"] == "L1"
    assert [e.command.name for e in s.history.entries[before:]] == ["view.set_center"]
    # Il valore è quello del 17 (read_pixel) nel punto della base dato dal 10.
    from astrotwo.core.coordinates_wcs import PixelPosition
    from astrotwo.core.measures import read_pixel
    g = s.workspace.state.view.geometry
    bx, by = g.window_to_base(400.0, 300.0)
    expected = read_pixel(s.workspace.state.layer("L1").data, PixelPosition(x=np.float64(bx), y=np.float64(by),
                                                                             convention="numpy"))
    assert read.values["pixel"]["value"] == float(expected.value)


def test_t8_cancellation(registry, files, tmp_path):
    s = Session(registry)
    run(s, "catalog.open_file", file={"path": files["catalog"]})
    before = s.workspace.state
    token = CancelToken()

    def progress(report):
        if report.step == 2:
            token.cancel()

    result = s.run(Command("image.open", 1, {"file": {"path": files["image"]}}), cancel=token, progress=progress)
    assert result.status == "cancelled" and result.error.code == "COMMAND_CANCELLED"
    assert s.workspace.state is before and s.history.entries[-1].result.status == "cancelled"
    # Comando a più passi simulato: annullato tra due passi, risultato scartato.
    custom = CommandRegistry()
    calls = []

    def slow(ctx, p):
        for k in range(5):
            ctx.step(f"passo {k}")
            calls.append(k)
        return Outcome(values={"n": {"value": 5.0, "unit": ""}}, state=dataclasses.replace(ctx.state, next_layer=99))

    custom.register(CommandSpec("test.slow", 1, "Slow.", "Lento.", (), (), "session", slow, long=True, steps=5))
    ws = Workspace()
    stop = CancelToken()
    res = custom.execute(Command("test.slow", 1, {}), ws, stop, lambda r: stop.cancel() if r.step == 3 else None)
    assert res.status == "cancelled" and calls == [0, 1, 2] and ws.state.next_layer == 1  # il passo 3 già avviato finisce
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    report = Session.load(path, registry).replay()
    assert report.replayed == (1,) and (2, "image.open", "cancelled") in report.not_replayed


# =============================================================================
# T9 — adattatore del 18


def test_t9_calculator_adapter(registry, files):
    from astrotwo.core import calculators as calc
    from astrotwo.core.commands import _calculator_value
    from astrotwo.core.coordinates_wcs import PixelPosition, SkyFrame

    s = Session(registry)
    run(s, "image.open", file={"path": files["image"]})
    run(s, "catalog.open_file", file={"path": files["catalog"]})
    image, table = (s.workspace.state.layer(i).data for i in ("L1", "L2"))
    start = SkyFrame.from_lonlat(83.6331 * u.deg, 22.0145 * u.deg, "icrs")
    results = [
        calc.evaluate_expression("3*8"), calc.evaluate_expression("sind(30)"),
        calc.evaluate_expression("skydist(10, 20, 10.5, 20.5)"),
        calc.convert_units(0.1, "m", "nm"), calc.convert_units(2, "a", "d"),
        calc.convert_units("10:10:08", None, "deg", sexagesimal="degrees"),
        calc.convert_units("2024-02-29T18:00:00", None, "mjd", scale="utc"),
        calc.convert_pixel_value(raw=-32768, bzero=32768, bscale=1),
        calc.convert_pixel_value(image=image, position=PixelPosition(x=np.float64(10), y=np.float64(10),
                                                                     convention="numpy"),
                                 display=calc.DisplaySettings(0.0, 100.0)),
        calc.calculate_coordinates(start, [calc.CoordinateTarget("galactic"),
                                           calc.CoordinateTarget("fk5", equinox="J2000")]),
        calc.calculate_coordinates(calc.CoordinateInput("05:34:31.94", "+22:00:52.2", "icrs",
                                                        lon_sexagesimal="hours"), [calc.CoordinateTarget("icrs")]),
        calc.convert_time("2000-01-01T12:00:00", "iso", "TT"), calc.convert_time(2451545.0, "jd", "tt", "tdb"),
    ]
    for result in results:
        command = result.command_05({"L1": image, "L2": table})
        out = s.run(Command(command["name"], command["version"], command["parameters"]))
        assert out.status == "ok", (command, out.error)
        again = calc.run_command(result.command)
        assert out.values["input"] == again.input and out.values["scale"] == again.scale
        expected = _calculator_value(again)
        if isinstance(again.value, calc.CoordinatesOutput):
            assert out.values["value"]["representations"] == expected["representations"]
        else:
            assert out.values["value"] == expected, command["name"]
    assert s.history.entries[-1].command.name == "calc.convert_time"  # classe session: in cronologia
    bad = run(s, "calc.convert_units", value=1.0, from_unit="m", to_unit="s")
    assert bad.error.code == "UNIT_INCOMPATIBLE"


# =============================================================================
# T11 — numeri esatti


def test_t11_exact_numbers(registry, tmp_path):
    values = np.random.default_rng(20261017).standard_normal(10_000) * 10.0 ** np.random.default_rng(1).integers(
        -300, 300, 10_000)
    text = json.dumps([float(v) for v in values], allow_nan=False)
    back = np.array(json.loads(text), dtype=np.float64)
    assert np.array_equal(back.view(np.uint64), values.view(np.uint64))
    # Lo stesso percorso nella sessione: scale casuali scritte e rilette identiche.
    s = Session(registry)
    scales = np.random.default_rng(3).uniform(1e-6, 1.0, 50)
    for scale in scales:
        run(s, "view.set_zoom", scale={"value": float(scale), "unit": "deg"})
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    loaded = Session.load(path, registry).loaded["entries"]
    read = np.array([e.command.parameters["scale"]["value"] for e in loaded])
    assert np.array_equal(read.view(np.uint64), scales.view(np.uint64))


# =============================================================================
# T13 — errori dei moduli invariati


def test_t13_module_errors_unchanged(registry):
    result = registry.execute(Command("view.set_center", 1, {"position": sky(10.0, 95.0)}), Workspace())
    with pytest.raises(cw.CoordinatesWcsError) as direct:
        cw.SkyFrame.from_lonlat(10.0 * u.deg, 95.0 * u.deg, "icrs")
    assert result.status == "error"
    assert (result.error.code, result.error.text) == (direct.value.code, direct.value.message) == (
        "COORD_OUT_OF_RANGE", direct.value.message)


# =============================================================================
# T15, T19 — servizi simulati (D05-2, comandi di sola lettura)


@pytest.fixture
def fake_simbad(monkeypatch):
    calls = []

    def query(name, timeouts):
        calls.append(name)
        return simbad_table(), "https://simbad.cds.unistra.fr/simbad/sim-tap"

    monkeypatch.setattr(cw, "_query_simbad", query)
    return calls


@pytest.fixture
def fake_tap(service, monkeypatch):
    state = {"rows": 3}

    def tap(request):
        return region_tap(rows=state["rows"])(request)

    entries = tuple(dataclasses.replace(e, url=service.url + "/viz") if e.id == "cds-vizier-tap" else e
                    for e in vo.BUILTIN_SERVERS)
    monkeypatch.setattr(vo, "BUILTIN_SERVERS", entries)
    service.routes["/viz/sync"] = tap
    return state


def region_command():
    return {"catalog": "II/246/out", "center": sky(10.0, 41.0), "radius": {"value": 30.0, "unit": "arcsec"}}


def test_t15_network_data_differs(fake_tap, tmp_path):
    with SharedCache(tmp_path / "c1") as first_cache:
        s = Session(default_registry(cache=first_cache))
        result = run(s, "catalog.load_region", **region_command())
        assert result.status == "ok" and result.network_fingerprint[0]["rows"] == 3
        path = tmp_path / "s.astrotwo.json"
        s.save(path, app_version="0.1.0")
    fake_tap["rows"] = 4  # alla riapertura il servizio risponde con una riga in più
    with SharedCache(tmp_path / "c2") as second_cache:
        reopened = Session.load(path, default_registry(cache=second_cache))
        report = reopened.replay()
        assert report.status == "ok" and report.replayed == (1,)
        codes = [w.code for w in report.warnings]
        assert codes[0] == "SESSION_NETWORK_DATA_DIFFERS" and "#1 catalog.load_region" in report.warnings[0].text
        info = report.warning_details[0]
        assert (info["number"], info["name"]) == (1, "catalog.load_region")
        assert (info["before"][0]["rows"], info["after"][0]["rows"]) == (3, 4)
        assert info["before"][0]["sha256"] != info["after"][0]["sha256"]
        assert info["after"][0]["origin"] and info["after"][0]["retrieved_at"]
    fake_tap["rows"] = 3  # cache svuotata e stessa risposta: nessun avviso sui dati di rete
    with SharedCache(tmp_path / "c3") as third_cache:
        third_cache.clear()
        report = Session.load(path, default_registry(cache=third_cache)).replay()
        assert "SESSION_NETWORK_DATA_DIFFERS" not in [w.code for w in report.warnings]


def test_t19_read_only_commands(registry, files, fake_simbad, cache):
    from astrotwo.core.catalogs import CatalogsError, record_view, search

    s = Session(registry)
    run(s, "catalog.open_file", file={"path": files["catalog"]})
    run(s, "catalog.select", layer="L1", rows=[1])
    before = s.workspace.state.state_json()
    resolved = run(s, "coords.resolve_name", name="M31")
    direct = cw.resolve_name("M31", cache=cache)
    assert resolved.status == "ok" and resolved.values["main_id"] == direct.main_id
    assert resolved.values["position"]["lon"] == {"value": float(direct.coords.coord.ra.deg), "unit": "deg"}
    found = run(s, "catalog.search", layer="L1", expression="V > 5.5")
    mask = search(s.workspace.state.layer("L1").data, "V > 5.5")
    assert found.values["matching_rows"] == int(np.count_nonzero(mask)) == 2
    assert found.values["first_rows"] == [int(i) for i in np.flatnonzero(mask)]
    wrong = run(s, "catalog.search", layer="L1", expression="V >> 5")
    with pytest.raises(CatalogsError) as err:
        search(s.workspace.state.layer("L1").data, "V >> 5")
    assert wrong.error.code == err.value.code == "EXPRESSION_INVALID"
    described = run(s, "catalog.describe", layer="L1")
    assert [c["name"] for c in described.values["columns"]] == ["RA", "DE", "V"]
    assert described.values["columns"][0]["ucd"] == "pos.eq.ra;meta.main" and described.values["rows"] == 3
    too_many = run(s, "catalog.rows", layer="L1", count=60)
    assert too_many.error.code == "COMMAND_PARAMETER_INVALID"
    rows = run(s, "catalog.rows", layer="L1", first=1, count=2, columns=["V"])
    assert [r["row"] for r in rows.values["rows"]] == [1, 2]
    table = s.workspace.state.layer("L1").data
    assert rows.values["rows"][0]["values"][0]["value"] == record_view(table, 1)[2]["value"]
    listed = run(s, "layer.list")
    assert listed.values["layers"][0]["id"] == "L1" and listed.values["layers"][0]["rows"] == 3
    assert s.workspace.state.state_json() == before  # selezione e spazio di lavoro invariati
    run(s, "table.sort", layer="L1", column="V", direction="descending")
    shown = run(s, "catalog.rows", layer="L1", order="shown")
    assert [r["row"] for r in shown.values["rows"]] == [1, 2, 0]


# =============================================================================
# T16, T18, T21 — segreti, requested_by, conversazioni


def test_t16_no_secrets(registry, files, tmp_path, monkeypatch):
    fake_key = "sk-finta-chiave-0123456789"
    monkeypatch.setenv("ANTHROPIC_API_KEY", fake_key)
    monkeypatch.setenv("OPENAI_API_KEY", fake_key)
    s = build_session(registry, files)
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    text = path.read_text()
    assert fake_key not in text and "dev.pages.astrotwo.ai" not in text and "keychain" not in text.lower()
    assert str(registry.cache.root) not in text and "cache.sqlite" not in text


def test_t18_requested_by(registry, files, tmp_path):
    origins = [RequestedBy("menu"), RequestedBy("mouse"), RequestedBy("history"),
               RequestedBy("ai", conversation="c1", turn=3, call="call-7", profile="anthropic", model="model-x")]
    s = Session(registry)
    run(s, "catalog.open_file", file={"path": files["catalog"]})
    results = [run(s, "catalog.search", o, layer="L1", expression="V > 5.5") for o in origins]
    assert len({json.dumps(r.values, sort_keys=True) for r in results}) == 1  # stessi risultati
    path = tmp_path / "s.astrotwo.json"
    s.save(path, app_version="0.1.0")
    saved = [c["command"]["requested_by"] for c in json.loads(path.read_text())["commands"][1:]]
    assert saved[3] == {"source": "ai", "conversation": "c1", "turn": 3, "call": "call-7", "profile": "anthropic",
                        "model": "model-x"} and saved[1] == {"source": "mouse"}
    reopened = Session.load(path, registry)
    assert reopened.replay().status == "ok"
    assert [e.command.requested_by for e in reopened.history.entries[1:]] == origins
    with pytest.raises(ValueError):
        RequestedBy("ai", conversation="c1")
    with pytest.raises(ValueError):
        RequestedBy("menu", model="x")


def test_t21_conversations_block(registry, files, tmp_path):
    class FailingProvider:
        def __getattr__(self, name):
            raise AssertionError("il 05 non chiama mai l'IA")

    provider = FailingProvider()
    s = build_session(registry, files)
    plain, with_block = tmp_path / "a.astrotwo.json", tmp_path / "b.astrotwo.json"
    s.save(plain, app_version="0.1.0")
    block = [{"conversation": "c1", "messages": [{"role": "user", "text": "apri cat.xml"}]}]
    s.save(with_block, app_version="0.1.0", conversations=block)
    assert "conversations" not in json.loads(plain.read_text())
    assert json.loads(with_block.read_text())["conversations"] == block
    with pytest.raises(ValueError):
        s.save(tmp_path / "c.astrotwo.json", app_version="0.1.0",
               conversations=[{"messages": [{"text": f"apri {files['catalog']}"}]}])
    states = []
    for path in (plain, with_block):
        reopened = Session.load(path, registry)
        assert reopened.replay().status == "ok"
        states.append(reopened.workspace.state.state_json())
    assert states[0] == states[1] and provider is not None


# =============================================================================
# T17 — cache del 04 da più thread durante i comandi (verifica di §3.2; carico completo nel T9 del 04)


def test_t17_cache_from_threads(fake_tap, fake_simbad, tmp_path):
    root = tmp_path / "shared-cache"
    errors = []

    def worker():
        with SharedCache(root) as cache:
            s = Session(default_registry(cache=cache))
            for _ in range(5):
                result = run(s, "catalog.load_region", **region_command())
                if result.status != "ok":
                    errors.append(result.error)

    def passive():
        with SharedCache(root) as cache:
            reg = default_registry(cache=cache)
            for _ in range(20):
                result = reg.execute(Command("coords.resolve_name", 1, {"name": "M31"}), Workspace())
                if result.status != "ok":
                    errors.append(result.error)

    threads = [threading.Thread(target=worker)] + [threading.Thread(target=passive) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    with SharedCache(root) as cache:
        assert cache.usage().total_bytes <= cache.limit_bytes


# =============================================================================
# Vista, misure, interfaccia collegata, prestazioni


def test_view_projection_and_go_to(registry, fake_simbad):
    s = Session(registry)
    run(s, "view.set_zoom", scale={"value": 1.0, "unit": "arcsec"}, window=WINDOW)
    small = run(s, "view.set_center", position=sky(10.0, 41.0), window=WINDOW)
    assert small.values["projection"] == "TAN" and small.values["base"].startswith("base creata")
    wide = run(s, "view.set_zoom", scale={"value": 0.1, "unit": "deg"}, window=WINDOW)  # campo ≈ 100°
    assert wide.values["projection"] == "AIT"
    assert wide.values["projection_choice"]["threshold"] == {"value": 33.0, "unit": "deg"}
    back = run(s, "view.set_zoom", scale={"value": 0.04, "unit": "deg"}, window=WINDOW)  # campo ≈ 40°: resta AIT
    assert back.values["projection"] == "AIT" and back.values["projection_choice"]["threshold"]["value"] == 27.0
    # campo della geometria disegnata (dal 10), anche dopo la ricreazione della base
    whole = run(s, "view.set_zoom", scale={"value": 360.0 / WINDOW["width"], "unit": "deg"}, window=WINDOW)
    radius = s.workspace.state.view.geometry.field_radius
    assert whole.values["field_of_view"] == {"value": float(2 * radius.to_value(u.deg)), "unit": "deg"}
    assert whole.values["field_of_view_method"].startswith("2 × field_radius")
    by_name = run(s, "view.go_to", text="M31", window=WINDOW)
    assert by_name.status == "ok" and by_name.values["resolved"]["main_id"] == "M  31" and fake_simbad == ["M31"]
    typed = run(s, "view.go_to", text="00:42:44.3 +41:16:09", window=WINDOW)
    expected = cw.parse_sexagesimal("00:42:44.3", hours=True)[0]
    assert typed.values["center"]["lon"]["value"] == float(expected.to_value(u.deg))
    decimal = run(s, "view.go_to", text="10.5 41.25", window=WINDOW)
    assert decimal.values["center"]["lat"] == {"value": 41.25, "unit": "deg"}


def test_measure_distance(registry, files):
    from astrotwo.core.measures import angular_distance

    s = Session(registry)
    run(s, "image.open", file={"path": files["image"]})
    result = run(s, "measure.distance", layer="L1", p1=pix(10, 10), p2=pix(20, 30))
    image = s.workspace.state.layer("L1").data
    a = cw.pixel_to_sky(image.wcs, 10.0, 10.0, convention="numpy").coords
    b = cw.pixel_to_sky(image.wcs, 20.0, 30.0, convention="numpy").coords
    assert result.values["distance"] == {"value": float(angular_distance(a, b, "arcsec").value.value),
                                         "unit": "arcsec"}
    assert result.layers_created == ("L2",) and s.workspace.state.layer("L2").kind == "measure"
    assert run(s, "measure.distance", layer="L1", p1=pix(10, 10), p2=pix(20, 30), snap=True).error.code == \
        "COMMAND_PARAMETER_INVALID"


def test_interface_commands_bound(registry, tmp_path):
    s = Session(registry)
    unbound = run(s, "prefs.set", key="appearance", value="night")
    assert unbound.status == "error" and unbound.error.code == "COMMAND_UNKNOWN"
    seen = []
    registry.bind("prefs.set", lambda ctx, p: seen.append(dict(p)) or Outcome(values={"key": p["key"]}))
    assert run(s, "prefs.set", key="appearance", value="night").status == "ok"
    assert seen == [{"key": "appearance", "value": "night"}]
    assert [e.command_class for e in s.history.entries] == ["application", "application"]
    with pytest.raises(ValueError):
        registry.bind("view.set_center", lambda ctx, p: None)
    cleared = run(s, "cache.clear", module=None)
    assert cleared.status == "ok" and cleared.values["total_bytes"] == {"value": 0.0, "unit": "byte"}


def test_registry_overhead(registry, files):
    """§9: costo del registro per comando (validazione e registrazione, esclusa la funzione del modulo)."""
    ws = Workspace()
    command = Command("calc.calculate_coordinates", 1, {
        "position": {"lon": {"value": 1.0, "unit": "deg"}, "lat": {"value": 1.0, "unit": "deg"}, "frame": "icrs"},
        "targets": [{"frame": "galactic"}]})
    start = time.perf_counter()
    for _ in range(200):
        registry.validate(command, ws)
    per_command = (time.perf_counter() - start) / 200
    assert per_command < 0.005, f"validazione: {per_command * 1e3:.3f} ms per comando"


def test_go_to_center_outside_current_projection_recreates_base(registry, monkeypatch):
    """Regressione del 2026-10-19: da una vista ``TAN`` centrata su Sirius, "Vai a" M31 (a circa 100°) dava
    ``VIEW_PARAMETERS_INVALID``. Risposte di SIMBAD registrate dal servizio reale il 2026-10-19."""
    recorded = {"Sirius": ("* alf CMa", 101.28715533333335, -16.71611586111111),
                "M31": ("M  31", 10.684708333333333, 41.268750000000004)}
    monkeypatch.setattr(cw, "_query_simbad", lambda name, timeouts: (
        simbad_table(*recorded[name]), "https://simbad.cds.unistra.fr/simbad/sim-tap"))
    s = Session(registry)
    assert run(s, "view.set_zoom", scale={"value": 7.5, "unit": "arcsec"}, window=WINDOW).status == "ok"
    for name in ("Sirius", "M31", "Sirius", "M31"):
        result = run(s, "view.go_to", text=name, window=WINDOW)
        assert result.status == "ok", result.error
        view = s.workspace.state.view
        assert view.projection == "TAN" and "ricreata" in result.values["base"]
        _, ra, dec = recorded[name]
        assert view.center.lon.to_value(u.deg) == pytest.approx(ra, abs=1e-9)
        assert view.center.lat.to_value(u.deg) == pytest.approx(dec, abs=1e-9)
        # il centro del cielo disegnato è quello chiesto (10, window_to_sky)
        mid = view.geometry.window_to_sky((WINDOW["width"] - 1) / 2, (WINDOW["height"] - 1) / 2)
        assert mid.spherical.lon.deg == pytest.approx(ra, abs=1e-6)
