# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Comandi dell'assistente (35) nella coda della finestra (40 §3.8, 32 §3.5, 35 §3.2).

Provider simulato a copione, nessuna rete e nessuna chiave: i comandi chiesti dal "modello" entrano nella stessa coda
di quelli dell'utente, uno alla volta, con ``requested_by = ai``; il thread principale non aspetta mai l'assistente.
"""

import threading

import pytest

from astrotwo.ai.chat_assistant import ChatAssistant
from astrotwo.ai.tool_registry import ToolRegistry
from astrotwo.core.commands import CancelToken, Command
from tests.ai.fake_providers import ScriptedAdapter, calls_turn, text_turn, tool_call
from tests.ui.test_main_window import settings_path, wait_idle, window  # noqa: F401 - fixture


def assistant_for(win, script):
    adapter = ScriptedAdapter(script)
    assistant = ChatAssistant(ToolRegistry(win.registry), win.assistant_executor(), adapter, language="Italian")
    assistant.record_consent()
    return assistant, adapter


def test_commands_go_through_window_queue(qtbot, window):  # noqa: F811 - fixture
    script = [calls_turn(tool_call("a", "view__set_grid", visible=True),
                         tool_call("b", "view__set_overlays", compass=True, scale_bar=False),
                         tool_call("c", "layer__list")),
              text_turn("Fatto.")]
    assistant, adapter = assistant_for(window, script)
    before = len(window.session.history)
    window.submit("view.set_grid", {"visible": False})  # comando dell'utente già in coda
    response = assistant.send("Griglia, bussola, livelli")
    qtbot.waitUntil(lambda: response.done, timeout=15000)  # il thread principale continua a girare
    answer = response.answer
    assert answer.error is None and answer.text == "Fatto."
    entries = window.session.history.entries[before:]
    assert [(e.command.name, e.command.requested_by.source) for e in entries] == [
        ("view.set_grid", "menu"), ("view.set_grid", "ai"), ("view.set_overlays", "ai"), ("layer.list", "ai")]
    assert [e.command.requested_by.call for e in entries[1:]] == ["a", "b", "c"]
    assert [c.number for c in answer.calls] == [e.number for e in entries[1:]]
    assert window.session.workspace.state.view.grid_visible  # effetto mostrato dalla finestra
    assert not window._assistant_waiters
    wait_idle(qtbot, window)


def test_stop_cancels_queued_command(qtbot, window):  # noqa: F811 - fixture
    gate, entered = threading.Event(), threading.Event()
    original = window.registry.run

    def slow_run(command, *args, **kwargs):  # nel thread di lavoro del 40
        if command.name == "layer.list":
            entered.set()
            gate.wait(10)
        return original(command, *args, **kwargs)

    window.registry.run = slow_run
    script = [calls_turn(tool_call("a", "layer__list"), tool_call("b", "view__set_grid", visible=True)),
              text_turn("mai")]
    assistant, adapter = assistant_for(window, script)
    response = assistant.send("Livelli")
    qtbot.waitUntil(entered.is_set, timeout=5000)
    assistant.stop()  # il CancelToken della risposta è quello del lavoro in coda
    gate.set()
    qtbot.waitUntil(lambda: response.done, timeout=15000)
    entry = window.session.history.entries[-1]
    assert entry.command.name == "layer.list" and entry.result.status == "cancelled"
    assert response.answer.interrupted and [c.error_code for c in response.answer.calls] == [
        "COMMAND_CANCELLED", "AI_CANCELLED"]
    wait_idle(qtbot, window)


def test_main_thread_never_waits(window):  # noqa: F811 - fixture
    with pytest.raises(RuntimeError):
        window.assistant_executor().execute(Command("layer.list", 1, {}), CancelToken())
