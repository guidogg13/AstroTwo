# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi dell'interfaccia con codice + ``params`` (D40-3; ``40`` §3.7.1, T18–T19; ``40``, ``41``, ``44`` §10.1).

Provoca i messaggi scritti direttamente da finestra, visualizzatore e pannello dell'assistente che gli altri test
dell'interfaccia non toccano; ogni messaggio è controllato contro il catalogo (voce, ``reason``, nome e tipo dei
parametri) e reso nelle due lingue.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from astrotwo import messages_catalog as mc
from astrotwo.core.commands import CommandError, Session, WorkspaceState
from astrotwo.ui import export_view
from astrotwo.ui import main_window as mw
from astrotwo.ui.ai_panel import check_assistant_preference
from astrotwo.ui.message_view import ValueProblem, exception_message, shown_exception
from astrotwo.ui.sky_renderer_gl import GlSkyRenderer
from tests.message_helpers import check_error, check_message
from tests.ui.test_main_window import make_window, settings_path  # noqa: F401 - fixture

PREFERENCE_REASONS = {
    "choice", "cache_not_integer", "cache_not_positive", "survey_empty", "box_not_integer", "box_range",
    "profiles_json", "profiles_object", "profile_fields", "profile_invalid", "profile_other", "profile_id",
    "consents_json", "consents_shape", "true_false", "int_not_integer", "int_range"}


def test_preference_values_and_settings_are_messages():
    seen_values: set[str | None] = set()
    seen_codes: set[tuple[str, str | None]] = set()

    def value_problem(check, *args) -> ValueProblem:
        with pytest.raises(ValueProblem) as info:
            check(*args)
        seen_codes.add(check_error(info.value))
        if info.value.code == "PREFERENCE_VALUE_INVALID":
            seen_values.add(info.value.params["reason"])
        return info.value

    pref = mw.PREFERENCES
    value_problem(pref["language"].check, "xx")
    value_problem(pref["cache/limit_bytes"].check, "abc")
    value_problem(pref["cache/limit_bytes"].check, "-5")
    value_problem(pref["hips/default_survey"].check, "  ")
    value_problem(mw.TOOL_PREFERENCES["tools/distance_box_size"].check, "x")
    assert value_problem(mw.TOOL_PREFERENCES["tools/distance_box_size"].check, "4").params == {
        "reason": "box_range", "value": 4, "low": 3, "high": 201}
    good = {"kind": "openai_compatible", "base_url": "https://api.example.org/v1", "model": "m"}
    profile_id = "openai-compatible:api.example.org"
    for key, value in (
            ("assistant/profiles", "{non json"), ("assistant/profiles", "[]"),
            ("assistant/profiles", json.dumps({"x": {"bogus": 1}})),
            ("assistant/profiles", json.dumps({"x": {**good, "kind": "nope"}})),
            ("assistant/profiles", json.dumps({"x": {"kind": "anthropic"}})),
            ("assistant/profiles", json.dumps({"x": good})),
            ("assistant/consents", "{non json"), ("assistant/consents", '{"x": 1}'),
            ("assistant/strict", "forse"), ("assistant/max_calls", "tre"), ("assistant/max_calls", "500")):
        value_problem(check_assistant_preference, key, value)
    insecure = value_problem(check_assistant_preference, "assistant/profiles", json.dumps(
        {"openai-compatible:example.org": {**good, "base_url": "http://example.org/v1"}}))
    assert insecure.code == "AI_INSECURE_ENDPOINT" and insecure.params == {"base_url": "http://example.org/v1"}
    assert seen_values == PREFERENCE_REASONS, sorted(seen_values ^ PREFERENCE_REASONS)
    assert profile_id  # l'identificativo giusto di un profilo valido è quello dell'indirizzo
    # PREFERENCE_INVALID: chiave sconosciuta, valore non valido (messaggio annidato) e valore non valido di altro tipo
    reasons = set()
    for key, value in (("nope", "x"), ("assistant/nope", "x"), ("cache/limit_bytes", "-5")):
        with pytest.raises(CommandError) as info:
            mw._check_preference(key, value)
        reasons.add(check_error(info.value))
    nested = info.value
    assert nested.params["reason"] == "invalid_value" and nested.params["cause"]["code"] == "PREFERENCE_VALUE_INVALID"
    assert mc.message_text(nested.code, nested.params, "en") == (
        "cache/limit_bytes: Cache limit of -5 bytes: a positive integer is required.; the previous value is kept.")
    assert mc.message_text(nested.code, nested.params, "it").startswith("cache/limit_bytes: Limite della cache di -5")

    class Odd:
        key, default = "x", "1"

        @staticmethod
        def check(text):
            raise ValueError("strano")

    original = dict(mw.PREFERENCES)
    mw.PREFERENCES["odd"] = Odd
    try:
        with pytest.raises(CommandError) as info:
            mw._check_preference("odd", "1")
    finally:
        mw.PREFERENCES.clear()
        mw.PREFERENCES.update(original)
    assert info.value.params == {"reason": "invalid_value_other", "key": "odd", "detail": "strano"}
    reasons.add(check_error(info.value))
    assert {("PREFERENCE_INVALID", r) for r in ("unknown_key", "unknown_assistant_key", "invalid_value",
                                                "invalid_value_other")} <= reasons
    with pytest.raises(CommandError) as info:  # comando dell'interfaccia con un valore fuori dall'elenco
        mw._closed("mode", ("a", "b"))(None, {"mode": "c"})
    assert info.value.params == {"reason": "choice", "parameter": "mode", "given": '"c"', "allowed": ["a", "b"]}
    check_error(info.value)


def test_exception_messages():
    plain = exception_message(RuntimeError("guasto"))
    assert (plain.code, plain.params) == ("UI_COMMAND_FAILED", {"error_type": "RuntimeError", "detail": "guasto"})
    check_message(plain.code, plain.params, plain.text)
    assert shown_exception(RuntimeError("guasto")).startswith("UI_COMMAND_FAILED: ")
    coded = CommandError("LAYER_UNKNOWN", "livello L9 inesistente", params={"layer": "L9"})
    relayed = exception_message(coded)
    assert (relayed.code, relayed.text, dict(relayed.params)) == ("LAYER_UNKNOWN", "livello L9 inesistente",
                                                                  {"layer": "L9"})


def test_export_messages(tmp_path):
    reasons = set()
    for path, reason in (("relative.png", "not_png"), (str(tmp_path / "a.jpg"), "not_png"),
                         (str(tmp_path / "missing" / "a.png"), "folder_unwritable")):
        with pytest.raises(CommandError) as info:
            export_view.validate_path(path)
        reasons.add(check_error(info.value))
        assert info.value.params["reason"] == reason
    folder = tmp_path / "cartella.png"
    folder.mkdir()
    with pytest.raises(CommandError) as info:
        export_view.validate_path(str(folder))
    reasons.add(check_error(info.value))
    assert info.value.params == {"reason": "is_directory", "path": str(folder)}
    assert mc.message_text(info.value.code, info.value.params, "en") == f"{folder} is a folder."
    with pytest.raises(CommandError) as info:
        export_view.compose_metadata(WorkspaceState(), night=False)
    reasons.add(check_error(info.value))
    assert reasons == {("EXPORT_PATH_INVALID", "not_png"), ("EXPORT_PATH_INVALID", "folder_unwritable"),
                       ("EXPORT_PATH_INVALID", "is_directory"), ("VIEW_UNDEFINED", "export")}


def test_gl_unavailable_reasons():
    emitted = []
    renderer = SimpleNamespace(available=True, failed=SimpleNamespace(emit=lambda *args: emitted.append(args)))
    GlSkyRenderer._unavailable(renderer, "version", "OpenGL 2.1: serve OpenGL 3.3 core profile; visualizzatore non "
                               "disponibile", {"found": "2.1", "required": "3.3"})
    for reason in ("program", "points_program", "moc_program"):
        GlSkyRenderer._unavailable(renderer, reason, "programma non compilato: errore", {"log": "errore"})
    assert not renderer.available and [e[2]["reason"] for e in emitted] == [
        "version", "program", "points_program", "moc_program"]
    for code, text, params in emitted:
        assert code == "GL_UNAVAILABLE"
        check_message(code, params, text)
    assert mc.message_text("GL_UNAVAILABLE", emitted[0][2], "it") == (
        "OpenGL 2.1: serve OpenGL 3.3 core profile; visualizzatore non disponibile.")


def test_session_save_failure_is_a_message(qtbot, settings_path, cache, monkeypatch):
    win = make_window(qtbot, settings_path, cache)
    try:
        def broken(self, path, **kwargs):
            raise OSError("disco pieno")

        monkeypatch.setattr(Session, "save", broken)
        assert win.save_session(str(cache.root / "s")) is False
        title, text = win.modals[-1]
        assert title == "The session cannot be saved"
        assert text == "SESSION_SAVE_FAILED: The session cannot be saved: OSError: disco pieno"
    finally:
        win.confirm = lambda title, text: True
        win.close()


def test_module_errors_while_drawing_name_the_layer():
    """Errore di un modulo mentre si disegna un catalogo o un MOC (sprint 8f): ``layer_context`` nei ``params``."""
    from astrotwo.core.commands import ResultMessage
    from astrotwo.ui.sky_viewer import with_layer

    error = ValueError("corpo ignoto")  # → UI_COMMAND_FAILED con tipo e testo dell'eccezione
    for kind, label in (("catalog", "Catalog layer"), ("moc", "MOC layer")):
        layer = SimpleNamespace(id="L2", name="Gaia DR3", kind=kind)
        message = with_layer(exception_message(error), layer)
        assert isinstance(message, ResultMessage) and message.text == "Gaia DR3: ValueError: corpo ignoto"
        assert message.params["layer_context"] == {"id": "L2", "name": "Gaia DR3", "kind": kind}
        assert mc.validate_params(message.code, message.params) == []
        assert mc.message_text(message.code, message.params, "en").startswith(f"{label} L2 «Gaia DR3»: ")
