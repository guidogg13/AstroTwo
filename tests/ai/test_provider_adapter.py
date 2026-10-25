# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del modulo 30 (``mdfiles/30-ia-adattatore-provider.md`` §12).

Senza rete e senza chiavi reali: due servizi simulati locali (API Messages di Anthropic e Chat Completions)
con risposte scritte a mano nei test. I profili puntano a ``http://127.0.0.1``, cioè a un host locale
(``http`` ammesso solo lì, §3.1). Tempi massimi ridotti nelle opzioni del turno al posto dell'orologio.
"""

import json
import logging
import re
from dataclasses import replace
from pathlib import Path

import pytest

from astrotwo.ai import provider_adapter as pa
from astrotwo.ai.provider_adapter import (
    PROVIDER_PRESETS,
    AssistantMessage,
    ProviderAdapterError,
    ProviderError,
    ProviderNotice,
    ProviderProfile,
    SystemMessage,
    TextDelta,
    ToolCall,
    ToolCallRequest,
    ToolDefinition,
    ToolResultMessage,
    TurnEnd,
    TurnOptions,
    Usage,
    UserMessage,
    make_adapter,
    profile_from_preset,
)
from tests.ai.fake_providers import FakeKeychain, Reply, provider_service, sse, sse_openai  # noqa: F401

FAKE_KEY = "sk-QzX9w7Lr4Tb2Np8Vk6Hm3Jd5Wc1Yf0"
FAST = TurnOptions(connect_timeout=1.0, read_timeout=1.0, silence_timeout=0.3)
TOOL = ToolDefinition("layer__list", "List the layers.", {"type": "object", "properties": {},
                                                         "additionalProperties": False})


class Token:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


def adapter(kind, service, **kw):
    profile = ProviderProfile(kind=kind, base_url=service.url + ("" if kind == "anthropic" else "/v1"),
                              model="test-model", **kw)
    keychain = FakeKeychain({profile.id: FAKE_KEY})
    waits = []
    a = make_adapter(profile, keychain, sleep=waits.append)
    return a, keychain, waits


# --- risposte simulate ----------------------------------------------------------------------


def anthropic_text(parts, stop="end_turn"):
    events = [{"type": "message_start", "message": {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "test-model", "content": [],
        "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 11, "output_tokens": 1}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}]
    events += [{"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": p}} for p in parts]
    events += [{"type": "content_block_stop", "index": 0},
               {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                "usage": {"output_tokens": 22}},
               {"type": "message_stop"}]
    return sse(events)


def anthropic_tools(calls):
    events = [{"type": "message_start", "message": {
        "id": "msg_2", "type": "message", "role": "assistant", "model": "test-model", "content": [],
        "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 5, "output_tokens": 1}}}]
    for i, (cid, name, pieces) in enumerate(calls):
        events.append({"type": "content_block_start", "index": i, "content_block": {
            "type": "tool_use", "id": cid, "name": name, "input": {}}})
        events += [{"type": "content_block_delta", "index": i,
                    "delta": {"type": "input_json_delta", "partial_json": p}} for p in pieces]
        events.append({"type": "content_block_stop", "index": i})
    events += [{"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None},
                "usage": {"output_tokens": 9}}, {"type": "message_stop"}]
    return sse(events)


def chunk(delta, finish=None):
    return {"id": "c1", "object": "chat.completion.chunk", "created": 1, "model": "test-model",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}


USAGE_CHUNK = {"id": "c1", "object": "chat.completion.chunk", "created": 1, "model": "test-model", "choices": [],
               "usage": {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33}}


def openai_text(parts, finish="stop"):
    return sse_openai([chunk({"role": "assistant", "content": p}) for p in parts]
                      + [chunk({}, finish), USAGE_CHUNK])


def openai_tools(calls):
    chunks = []
    for i, (cid, name, pieces) in enumerate(calls):
        chunks.append(chunk({"tool_calls": [{"index": i, "id": cid, "type": "function",
                                             "function": {"name": name, "arguments": ""}}]}))
        chunks += [chunk({"tool_calls": [{"index": i, "function": {"arguments": p}}]}) for p in pieces]
    return sse_openai(chunks + [chunk({}, "tool_calls"), USAGE_CHUNK])


def text_reply(kind, parts):
    return Reply(chunks=anthropic_text(parts) if kind == "anthropic" else openai_text(parts))


def tools_reply(kind, calls):
    return Reply(chunks=anthropic_tools(calls) if kind == "anthropic" else openai_tools(calls))


def error_reply(kind, status, message, headers=None):
    body = ({"type": "error", "error": {"type": "api_error", "message": message}} if kind == "anthropic"
            else {"error": {"message": message, "type": "invalid_request_error"}})
    return Reply(status=status, chunks=[json.dumps(body)], ctype="application/json", headers=headers)


KINDS = ["anthropic", "openai_compatible"]
CONVERSATION = [SystemMessage("You are AstroTwo's assistant."), UserMessage("List the layers.")]


# =============================================================================


@pytest.mark.parametrize("kind", KINDS)
def test_t1_text_streaming(kind, provider_service):
    parts = [f"pezzo{k} " for k in range(20)]
    provider_service.script = [text_reply(kind, parts)]
    a, _, _ = adapter(kind, provider_service)
    events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    deltas = [e for e in events if isinstance(e, TextDelta)]
    assert [d.text for d in deltas] == parts and "".join(d.text for d in deltas) == "".join(parts)
    assert events[-2:] == [Usage(11, 22, None, None), TurnEnd("end")]


@pytest.mark.parametrize("kind", KINDS)
def test_t2_tool_calls(kind, provider_service):
    arguments = '{"layer": "L1", "first": 0, "count": 5, "order": "table"}'
    pieces = [arguments[i:i + 8] for i in range(0, len(arguments), 8)][:6]
    pieces.append(arguments[len("".join(pieces)):])
    assert len(pieces) == 7 and "".join(pieces) == arguments
    provider_service.script = [tools_reply(kind, [("call_a", "catalog__rows", pieces),
                                                  ("call_b", "layer__list", ["{}"])])]
    a, _, _ = adapter(kind, provider_service)
    events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    calls = [e for e in events if isinstance(e, ToolCallRequest)]
    assert calls == [ToolCallRequest("call_a", "catalog__rows", arguments), ToolCallRequest("call_b", "layer__list",
                                                                                          "{}")]
    assert events[-1] == TurnEnd("tool_use") and a.capabilities().tool_calling is True


@pytest.mark.parametrize("kind", KINDS)
def test_t3_tool_results_sent(kind, provider_service):
    provider_service.script = [text_reply(kind, ["ok"])]
    a, _, _ = adapter(kind, provider_service)
    ok_json = '{"status": "ok", "values": {"layers": []}}'
    err_json = '{"status": "error", "error": {"code": "LAYER_UNKNOWN", "text": "livello L9"}}'
    messages = CONVERSATION + [
        AssistantMessage("Ecco.", (ToolCall("call_a", "layer__list", "{}"), ToolCall("call_b", "catalog__rows",
                                                                                    '{"layer": "L9"}'))),
        ToolResultMessage("call_a", ok_json), ToolResultMessage("call_b", err_json, is_error=True)]
    list(a.stream_turn(messages, [TOOL], FAST))
    body = provider_service.requests[-1]["body"]
    if kind == "anthropic":
        assert body["system"] == "You are AstroTwo's assistant."
        assert body["messages"][1]["content"][1] == {"type": "tool_use", "id": "call_a", "name": "layer__list",
                                                     "input": {}}
        assert body["messages"][2] == {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call_a", "content": ok_json, "is_error": False},
            {"type": "tool_result", "tool_use_id": "call_b", "content": err_json, "is_error": True}]}
        assert body["tools"] == [{"name": TOOL.name, "description": TOOL.description,
                                  "input_schema": TOOL.input_schema}]
    else:
        assert body["messages"][0] == {"role": "system", "content": "You are AstroTwo's assistant."}
        assert body["messages"][2]["tool_calls"][1] == {"id": "call_b", "type": "function", "function": {
            "name": "catalog__rows", "arguments": '{"layer": "L9"}'}}
        assert body["messages"][3:] == [{"role": "tool", "tool_call_id": "call_a", "content": ok_json},
                                        {"role": "tool", "tool_call_id": "call_b", "content": err_json}]
        assert body["tools"][0]["function"]["parameters"] == TOOL.input_schema
    assert "temperature" not in body and "top_p" not in body  # nessun parametro di campionamento


@pytest.mark.parametrize("kind", KINDS)
def test_t16_tool_choice(kind, provider_service):
    """§3.5 (decisione del proprietario del 2026-10-22): ``none`` con gli strumenti presenti; ``auto`` non si manda."""
    provider_service.script = [text_reply(kind, ["ok"])]
    a, _, _ = adapter(kind, provider_service)
    list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    assert "tool_choice" not in provider_service.requests[-1]["body"]
    list(a.stream_turn(CONVERSATION, [TOOL], replace(FAST, tool_choice="none")))
    body = provider_service.requests[-1]["body"]
    assert body["tool_choice"] == ({"type": "none"} if kind == "anthropic" else "none")
    assert len(body["tools"]) == 1 and a.last_request().body == body
    list(a.stream_turn(CONVERSATION, [], replace(FAST, tool_choice="none")))  # senza strumenti: nessun campo
    assert "tool_choice" not in provider_service.requests[-1]["body"]
    with pytest.raises(ValueError):
        TurnOptions(tool_choice="required")


@pytest.mark.parametrize("kind", KINDS)
def test_t4_errors_and_retries(kind, provider_service):
    cases = [
        ([error_reply(kind, 401, "invalid x-api-key")], "AI_AUTH", 1),
        ([error_reply(kind, 403, "forbidden")], "AI_AUTH", 1),
        ([error_reply(kind, 404, "model: test-model not found")], "AI_MODEL_NOT_FOUND", 1),
        ([error_reply(kind, 400, "prompt is too long: 300000 tokens > 200000 maximum")], "AI_CONTEXT_TOO_LONG", 1),
        ([Reply(status=200, chunks=["event: strano\ndata: {\"type\": \"strano\"}\n\n"])], "AI_BAD_RESPONSE", 1),
    ]
    for replies, code, requests in cases:
        provider_service.requests.clear()
        provider_service.script = replies
        a, _, waits = adapter(kind, provider_service)
        events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
        assert isinstance(events[-1], ProviderError) and events[-1].code == code, (code, events)
        assert len(provider_service.requests) == requests and waits == []
    # 429 con retry-after: ripetuta al più 2 volte, attese dichiarate.
    provider_service.requests.clear()
    provider_service.script = [error_reply(kind, 429, "slow down", {"retry-after": "7"})] * 3
    a, _, waits = adapter(kind, provider_service)
    events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    assert len(provider_service.requests) == 3 and waits == [7.0, 7.0]
    notices = [e for e in events if isinstance(e, ProviderNotice)]
    assert len(notices) == 2 and "attesa 7 s" in notices[0].text
    assert events[-1].code == "AI_RATE_LIMIT" and events[-1].retry_after == 7.0
    # retry-after oltre 30 s: attesa limitata a 30 s.
    provider_service.requests.clear()
    provider_service.script = [error_reply(kind, 429, "slow", {"retry-after": "120"})] * 3
    a, _, waits = adapter(kind, provider_service)
    list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    assert waits == [30.0, 30.0]
    # 500 e 529 senza retry-after: attese 1 s e 4 s; 503 poi successo.
    for status in (500, 529):
        provider_service.requests.clear()
        provider_service.script = [error_reply(kind, status, "overloaded")] * 3
        a, _, waits = adapter(kind, provider_service)
        events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
        assert waits == [1.0, 4.0] and events[-1].code == "AI_SERVICE" and len(provider_service.requests) == 3
    provider_service.requests.clear()
    provider_service.script = [error_reply(kind, 503, "busy"), text_reply(kind, ["ciao"])]
    a, _, waits = adapter(kind, provider_service)
    events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    assert waits == [1.0] and events[-1] == TurnEnd("end") and len(provider_service.requests) == 2


@pytest.mark.parametrize("kind", KINDS)
def test_t5_no_retry_after_first_event(kind, provider_service):
    body = anthropic_text(["a", "b", "c", "d"]) if kind == "anthropic" else openai_text(["a", "b", "c", "d"])
    cut = 5 if kind == "anthropic" else 3  # tre frammenti di testo, poi lo streaming si interrompe
    error = (sse([{"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}])
             if kind == "anthropic" else ["data: {non json\n\n"])
    provider_service.script = [Reply(chunks=body[:cut] + error)]
    a, _, waits = adapter(kind, provider_service)
    events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["a", "b", "c"]
    assert isinstance(events[-1], ProviderError) and events[-1].code in ("AI_BAD_RESPONSE", "AI_SERVICE")
    assert len(provider_service.requests) == 1 and waits == []


@pytest.mark.parametrize("kind", KINDS)
def test_t6_timeouts(kind, provider_service):
    # Connessione rifiutata: porta chiusa.
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    profile = ProviderProfile(kind=kind, base_url=f"http://127.0.0.1:{port}", model="m")
    a = make_adapter(profile, FakeKeychain({profile.id: FAKE_KEY}), sleep=lambda w: None)
    events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    assert events[-1].code in ("AI_CONNECTION", "AI_TIMEOUT")
    # Nessuna risposta oltre il tempo di lettura.
    provider_service.script = [Reply(chunks=["x"], delay_first=1.6)]
    a, _, _ = adapter(kind, provider_service)
    events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    assert events[-1].code == "AI_TIMEOUT" and "lettura 1 s" in events[-1].message
    # Silenzio a metà streaming oltre la soglia.
    body = anthropic_text(["a", "b"]) if kind == "anthropic" else openai_text(["a", "b"])
    provider_service.script = [Reply(chunks=body[:3] + [(0.8, body[3])] + body[4:])]
    a, _, _ = adapter(kind, provider_service)
    events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    assert events[-1].code == "AI_TIMEOUT" and "0.3 s di silenzio" in events[-1].message


@pytest.mark.parametrize("kind", KINDS)
def test_t7_cancellation(kind, provider_service):
    parts = [f"p{k}" for k in range(20)]
    body = anthropic_text(parts) if kind == "anthropic" else openai_text(parts)
    provider_service.script = [Reply(chunks=[(0.05, c) for c in body])]
    a, _, _ = adapter(kind, provider_service)
    token = Token()
    events = []
    for event in a.stream_turn(CONVERSATION, [TOOL], TurnOptions(silence_timeout=5.0), token):
        events.append(event)
        if sum(isinstance(e, TextDelta) for e in events) == 5:
            token.cancel()
    assert events[-1] == TurnEnd("cancelled")
    assert sum(isinstance(e, TextDelta) for e in events) == 5  # nessun evento dopo lo Stop
    assert provider_service.closed_early.wait(3.0)  # connessione chiusa


MODEL_IDS = ["claude-opus", "claude-sonnet", "claude-haiku", "claude-3", "gpt-4o", "gpt-4.1", "gpt-5", "o3-mini",
             "o4-mini", "llama3", "llama-3", "gemini-1.5", "gemini-2", "mistral-large", "mistral-small",
             "deepseek-chat", "deepseek-reasoner", "grok-", "qwen2", "phi-3"]


def test_t8_no_model_in_code():
    root = Path(pa.__file__).parent
    for path in root.rglob("*.py"):
        text = path.read_text().lower()
        for model in MODEL_IDS:
            assert model not in text, (path.name, model)


@pytest.mark.parametrize("kind", KINDS)
def test_t9_environment_ignored(kind, provider_service, monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.setenv(name, "env-key-da-non-usare")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", "X-Env-Header: da-togliere")
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "X-Env-Header: da-togliere")
    monkeypatch.setenv("OPENAI_ORG_ID", "org-env")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "proj-env")
    provider_service.script = [text_reply(kind, ["ciao"])]
    a, keychain, _ = adapter(kind, provider_service)
    events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    assert events[-1] == TurnEnd("end")  # l'indirizzo del profilo, non quello delle variabili
    headers = {k.lower(): v for k, v in provider_service.requests[-1]["headers"].items()}
    sent = headers.get("x-api-key") or headers.get("authorization", "").removeprefix("Bearer ")
    assert sent == FAKE_KEY and keychain.reads == [a.profile.id]
    assert "env-key-da-non-usare" not in json.dumps(headers)
    for name in ("x-env-header", "openai-organization", "openai-project"):
        assert name not in headers


@pytest.mark.parametrize("kind", KINDS)
def test_t10_no_key_in_logs_and_record(kind, provider_service, caplog):
    caplog.set_level(logging.DEBUG)
    for name in ("anthropic", "openai", "httpx2", "httpcore2"):
        logging.getLogger(name).setLevel(logging.DEBUG)  # anche se qualcuno alza il livello: il filtro resta
    provider_service.script = [error_reply(kind, 401, f"Incorrect API key provided: {FAKE_KEY[:12]}…{FAKE_KEY[-6:]}"),
                               tools_reply(kind, [("call_a", "layer__list", ["{}"])])]
    a, _, _ = adapter(kind, provider_service)
    first = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    second = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    record = a.last_request()
    assert record.body == provider_service.requests[-1]["body"]  # identico al corpo ricevuto
    assert record.url == a._url() and record.sent_at.endswith("+00:00")
    texts = [r.getMessage() for r in caplog.records] + [repr(e) for e in first + second] + [json.dumps(record.body)]
    joined = "\n".join(texts)
    for size in range(6, len(FAKE_KEY) + 1):
        for start in range(len(FAKE_KEY) - size + 1):
            assert FAKE_KEY[start:start + size] not in joined
    assert first[-1].code == "AI_AUTH"


def test_t11_https_required():
    with pytest.raises(ProviderAdapterError) as err:
        make_adapter(ProviderProfile("openai_compatible", "http://example.org/v1", "m"), FakeKeychain())
    assert err.value.code == "AI_INSECURE_ENDPOINT"
    local = ProviderProfile("openai_compatible", "http://127.0.0.1:11434", "m")
    assert local.local and local.id == "openai-compatible:127.0.0.1:11434"
    assert make_adapter(local, FakeKeychain()).capabilities().local
    remote = ProviderProfile("openai_compatible", "https://api.example.org/v1", "m")
    assert not remote.local and remote.id == "openai-compatible:api.example.org"
    assert ProviderProfile("anthropic", "https://api.anthropic.com", "m").id == "anthropic"


@pytest.mark.parametrize("kind", KINDS)
def test_t12_list_models(kind, provider_service):
    models_path = "/v1/models"
    listing = ({"data": [{"type": "model", "id": "test-model", "display_name": "Test", "created_at":
                          "2026-01-01T00:00:00Z", "max_input_tokens": 1000}],
                "has_more": False, "first_id": "test-model", "last_id": "test-model"} if kind == "anthropic"
               else {"object": "list", "data": [{"id": "test-model", "object": "model", "created": 1,
                                                  "owned_by": "x", "context_length": 8192}]})
    provider_service.routes[models_path] = [Reply(chunks=[json.dumps(listing)], ctype="application/json")]
    a, _, _ = adapter(kind, provider_service)
    result = a.list_models()
    assert [m.id for m in result.models] == ["test-model"] and result.notice is None
    assert a.capabilities().max_context_tokens == (1000 if kind == "anthropic" else 8192)
    provider_service.routes[models_path] = [error_reply(kind, 404, "not found")]
    result = a.list_models()
    assert result.models == () and result.notice.code == "AI_MODELS_UNAVAILABLE"


def test_t13_model_without_tools(provider_service):
    # Risposta registrata come la dà un server compatibile quando il modello non chiama strumenti (es. Ollama).
    provider_service.script = [error_reply("openai_compatible", 400,
                                           "registry.ollama.ai/library/test-model:latest does not support tools")]
    a, _, _ = adapter("openai_compatible", provider_service)
    events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    assert events[-1].code == "AI_NO_TOOLS" and a.capabilities().tool_calling is False
    provider_service.script = [text_reply("openai_compatible", ["non chiamo strumenti"])]
    probe = a.probe_tools(FAST)
    assert probe.tool_calling is False and probe.usage == Usage(11, 22, None)
    provider_service.script = [tools_reply("openai_compatible", [("c1", "astrotwo_probe", ["{}"])])]
    assert a.probe_tools(FAST).tool_calling is True and a.capabilities().tool_calling is True


def test_t14_same_contract(provider_service):
    sequences = []
    for kind in KINDS:
        provider_service.script = [text_reply(kind, ["Ci sono ", "due livelli."])]
        a, _, _ = adapter(kind, provider_service)
        sequences.append([e for e in a.stream_turn(CONVERSATION, [TOOL], FAST) if not isinstance(e, Usage)])
        provider_service.script = [tools_reply(kind, [("call_1", "layer__list", ['{"a"', ': 1}'])])]
        sequences.append([e for e in a.stream_turn(CONVERSATION, [TOOL], FAST) if not isinstance(e, Usage)])
    assert sequences[0] == sequences[2] and sequences[1] == sequences[3]


def test_t15_presets(provider_service):
    assert [p.preset for p in PROVIDER_PRESETS] == ["anthropic", "openai", "gemini", "mistral", "deepseek", "xai",
                                                    "groq", "openrouter", "ollama", "lmstudio"]
    ids = set()
    for p in PROVIDER_PRESETS:
        assert p.tool_calling in ("verified", "documented", "unverified") and p.sources
        assert all(s.startswith("https://") for s in p.sources)
        profile = profile_from_preset(p.preset, "modello-scelto-dall-utente")
        assert profile.local == (p.preset in ("ollama", "lmstudio"))
        assert profile.base_url.startswith("http://localhost") if profile.local else profile.base_url.startswith(
            "https://")
        assert profile.tool_calling_status == p.tool_calling
        ids.add(profile.id)
        if p.kind == "openai_compatible":
            assert re.fullmatch(r"openai-compatible:[a-z0-9.\-]+(:\d+)?", profile.id)
        make_adapter(profile, FakeKeychain())
    assert len(ids) == len(PROVIDER_PRESETS)
    assert profile_from_preset("openai", "m").max_tokens_field == "max_completion_tokens"
    assert {p.preset: p.tool_calling for p in PROVIDER_PRESETS}["ollama"] == "verified"
    # Un turno con il servizio simulato al posto dell'indirizzo di ogni profilo compatibile.
    for p in PROVIDER_PRESETS:
        if p.kind != "openai_compatible":
            continue
        provider_service.requests.clear()
        provider_service.script = [text_reply("openai_compatible", ["ok"])]
        profile = profile_from_preset(p.preset, "m", base_url=provider_service.url + "/v1")
        a = make_adapter(profile, FakeKeychain({profile.id: FAKE_KEY}))
        assert list(a.stream_turn(CONVERSATION, [TOOL], FAST))[-1] == TurnEnd("end")
        request = provider_service.requests[-1]
        assert p.max_tokens_field in request["body"] and request["body"][p.max_tokens_field] == 4096
        headers = {k.lower() for k in request["headers"]}
        assert not {"http-referer", "x-openrouter-title", "x-title"} & headers


def test_local_profile_without_key(provider_service):
    provider_service.script = [text_reply("openai_compatible", ["ciao"])]
    profile = ProviderProfile("openai_compatible", provider_service.url + "/v1", "m")
    a = make_adapter(profile, FakeKeychain())
    assert list(a.stream_turn(CONVERSATION, [TOOL], FAST))[-1] == TurnEnd("end")
    headers = {k.lower(): v for k, v in provider_service.requests[-1]["headers"].items()}
    assert headers["authorization"] == f"Bearer {pa.LOCAL_PLACEHOLDER_KEY}"
    remote = ProviderProfile("openai_compatible", "https://api.example.org/v1", "m")
    events = list(make_adapter(remote, FakeKeychain()).stream_turn(CONVERSATION, [TOOL], FAST))
    assert events == [ProviderError("KEY_NOT_FOUND", "nessuna chiave per 'openai-compatible:api.example.org'",
                                    params={"profile_id": "openai-compatible:api.example.org"})]
