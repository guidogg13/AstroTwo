# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Strumento ``object__profile`` (``mdfiles/32-ia-registro-strumenti.md`` §3.2, §3.7bis, T15; ``34`` T15; ``25``
§11; sprint C6b).

Risposte vere registrate il 2026-11-07 (``tests/analysis/profile_fakes.py``: SIMBAD di Harvard, archivio Gaia ESA,
IRSA, NASA Exoplanet Archive, ESASky; CDS giù). Nessuna rete, nessun provider: le chiamate sono scritte nel test.
"""

from __future__ import annotations

import json

from astrotwo.ai.result_verification import verify_answer
from astrotwo.ai.tool_registry import MAX_RESULT_BYTES, ToolRegistry, string_paths
from astrotwo.analysis.object_profile import command_specs
from astrotwo.core.commands import Session, default_registry
from tests.ai.ai_workspace import ai
from tests.analysis.profile_fakes import services  # noqa: F401


def profile_registry(cache):
    registry = default_registry(cache=cache)
    for spec in command_specs():
        registry.register(spec)
    return registry


def ask(tools, session, args):
    command = tools.command_for("object__profile", json.dumps(args), ai(), session.workspace.state)
    result = session.run(command)
    entry = session.history.entries[-1]
    return entry, result, tools.reduce_result(result, command=entry.command, number=entry.number,
                                              state=session.workspace.state)


def numbers(value, path=""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from numbers(v, f"{path}.{k}")
    elif isinstance(value, list):
        for v in value:
            yield from numbers(v, f"{path}[]")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield path, value


def test_t15_tool_exposed_only_with_level_2(cache):
    tools = ToolRegistry(profile_registry(cache))
    names = [t["name"] for t in tools.tools()]
    assert len(names) == 25 and "object__profile" in names
    tool = next(t for t in tools.tools() if t["name"] == "object__profile")
    assert "Requires user confirmation." in tool["description"] and "Uses the network." in tool["description"]
    assert {"name", "position", "sections", "simbad_id"} <= set(tool["input_schema"]["properties"])
    alone = ToolRegistry(default_registry(cache=cache))  # solo il livello 1: nessuno strumento, nessun errore
    assert len(alone.tools()) == 24 and "object__profile" not in alone.valid_tools()


def test_t15_confirmation_classification_and_reduced_result(cache, services):  # noqa: F811
    registry = profile_registry(cache)
    tools = ToolRegistry(registry)
    session = Session(registry)
    command = tools.command_for("object__profile", json.dumps({"name": "TRAPPIST-1"}), ai(),
                                session.workspace.state)
    confirmation = tools.needs_confirmation(command)
    assert confirmation.required and confirmation.reasons == ("network", "long")
    entry, result, reduced = ask(tools, session, {"name": "TRAPPIST-1"})
    assert result.status == "ok", result.error
    assert entry.command.requested_by.source == "ai" and entry.command.parameters["simbad_id"] == "TRAPPIST-1"
    assert tools.unclassified("object.profile", result) == []  # ogni stringa classificata (T12 del 32)
    text = json.dumps(reduced)
    assert len(text.encode()) <= MAX_RESULT_BYTES and "over_limit" not in reduced
    assert "truncated" not in reduced  # nessun taglio generico del 32: le sezioni ci sono tutte
    assert [s["name"] for s in reduced["values"]["sections"]] == ["identity", "images", "astrometry", "photometry",
                                                                  "planets"]
    assert "SELECT" not in text and "iVBOR" not in text and "png" not in text  # niente ADQL né immagini
    assert reduced["contains_external_text"]
    assert reduced["values"]["resolved"]["main_id"]["external_text"] == "TRAPPIST-1"
    # ogni numero del riassunto è uno dei numeri del risultato completo, mai cambiato
    full = set(v for _, v in numbers(result.values))
    own = (".source", ".formula", ".reference", ".truncated.")  # indici delle fonti e formule e conteggi dei tagli dichiarati
    assert {v for p, v in numbers(reduced["values"]) if not any(k in p + "." for k in own)} <= full
    sections = {s["name"]: s for s in reduced["values"]["sections"]}
    full_sections = {s["name"]: s for s in result.values["sections"]}
    assert [v["quantity"] for v in sections["astrometry"]["values"]] == \
        [v["quantity"] for v in full_sections["astrometry"]["values"]]
    parallax = next(v for v in sections["astrometry"]["values"] if v["quantity"] == "parallax")
    original = next(v for v in full_sections["astrometry"]["values"] if v["quantity"] == "parallax")
    assert parallax["value"] == original["value"] and parallax["error"] == original["error"]["value"]
    assert original["error"]["unit"] == original["value"]["unit"]  # errore nell'unità del valore (32 §3.7bis)
    source = sections["astrometry"]["sources"][parallax["source"]]
    assert source["table"] == "gaiadr3.gaia_source" and "query" not in source
    # Fotometria: la tabella dei punti (25 §11) con gli stessi numeri; W4 di TRAPPIST-1 è un limite superiore
    points = {(p["catalog"], p["band"]): p for p in sections["photometry"]["details"]["points"]}
    full_points = {(p["catalog"], p["band"]): p for p in full_sections["photometry"]["details"]["points"]}
    for key, point in points.items():
        assert point["flux"] == full_points[key]["flux"] and point.get("wavelength") == full_points[key]["wavelength"]
    assert points[("AllWISE", "W4")]["upper_limit"] is True and "upper_limit" not in points[("AllWISE", "W1")]
    assert sections["photometry"]["truncated"]["points_total"] == len(full_points)
    planets = sections["planets"]
    period = next(v for v in planets["values"] if v["quantity"] == "TRAPPIST-1 b period")
    assert period["value"] == {"value": 1.510826, "unit": "d"}
    assert planets["references"][period["reference"]]["external_text"] == "2021PSJ.....2....1A"
    assert planets["details"]["planets"][0]["disc_year"] == 2016
    kept = planets.get("truncated", {}).get("planets_kept", 7)  # pianeti tolti dalla coda solo se servono, dichiarati
    assert len(planets["details"]["planets"]) == kept and planets.get("truncated", {}).get("planets_total", 7) == 7
    # il profilo dei soli pianeti li porta tutti e 7 entro i 20 kB
    _, _, only = ask(tools, session, {"name": "TRAPPIST-1", "sections": ["planets"]})
    assert len(json.dumps(only).encode()) <= MAX_RESULT_BYTES and "truncated" not in only
    assert len(only["values"]["sections"][0]["details"]["planets"]) == 7
    assert not any(p.endswith(".png") for p, _ in string_paths(reduced))
    # 51 Peg: stesso limite di 20 kB
    _, _, peg = ask(tools, session, {"name": "51 Peg"})
    assert len(json.dumps(peg).encode()) <= MAX_RESULT_BYTES and "over_limit" not in peg


def test_t15_34_verifies_profile_numbers_on_the_full_result(cache, services):  # noqa: F811
    registry = profile_registry(cache)
    tools = ToolRegistry(registry)
    session = Session(registry)
    entry, result, _ = ask(tools, session, {"name": "TRAPPIST-1"})
    astrometry = next(s for s in result.values["sections"] if s["name"] == "astrometry")
    parallax = next(v for v in astrometry["values"] if v["quantity"] == "parallax")["value"]["value"]
    distance = next(v for v in astrometry["values"] if v["quantity"] == "distance_geo")["value"]["value"]
    n = entry.number
    answer = (f"From #{n}: the Gaia DR3 parallax of TRAPPIST-1 is {parallax!r} mas, the Bailer-Jones distance "
              f"{distance!r} pc and the period of planet b 1.510826 d. A wrong parallax would be 81.5 mas.")
    report = verify_answer(answer, ["Profile of TRAPPIST-1?"], [entry], tools=tools,
                           state=session.workspace.state)
    states = {c.number.text: c.state for c in report.numbers}
    assert states[repr(parallax)] == "verified" and states[repr(distance)] == "verified"
    assert states["1.510826"] == "verified" and states["81.5"] == "not_verified"
    assert report.has_unverified


def test_t22_profile_asked_by_the_assistant_opens_its_tab(qtbot, cache, services, tmp_path):  # noqa: F811
    from PySide6.QtCore import QSettings

    from astrotwo.core.commands import CancelToken, Command, RequestedBy
    from astrotwo.ui.main_window import MainWindow, ThreadCache, register_analysis_commands
    from tests.ui.test_profiles import finished

    registry = default_registry(cache=ThreadCache(root=cache.root))
    register_analysis_commands(registry)
    window = MainWindow(registry=registry, settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat),
                        startup_commands=False)
    window.confirm = lambda title, text: True
    qtbot.addWidget(window)
    try:
        from astrotwo.ui.main_window import _AssistantTicket

        ticket = _AssistantTicket()
        command = Command("object.profile", 1, {"name": "TRAPPIST-1", "sections": ["identity", "planets"]},
                          RequestedBy("ai", conversation="c1", turn=1, call="t1", profile="p", model="m"))
        window._assistant_enqueue(command, CancelToken(), ticket)
        tab = window.profiles.tabs.currentWidget()
        assert tab is not None and tab.origin_label.text() in ("Asked by the assistant", "Chiesto dall'assistente")
        qtbot.waitUntil(lambda: ticket.event.is_set() and finished(window, tab), timeout=60000)
        profiles = [e for e in window.session.history.entries if e.command.name == "object.profile"]
        assert len(profiles) == 1 and profiles[0].command.requested_by.source == "ai"  # nessun secondo comando
        assert ticket.done.result.status == "ok" and tab.command_number == profiles[0].number
        assert tab.views["planets"].state == "done"
    finally:
        window.close()
        if window.profiles is not None:
            window.profiles.close()
