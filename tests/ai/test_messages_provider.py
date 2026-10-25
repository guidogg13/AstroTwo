# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 30 con codice + ``params`` (D40-3; ``40`` §3.7.1, T18–T19; ``30`` §10.1).

Con i servizi simulati dei test del 30. Ogni errore e avviso è controllato contro il catalogo alla creazione
(``tests/conftest.py``); qui si verifica la copertura di tutte le coppie (codice, ragione), che i valori restino
quelli ricevuti e che nessun messaggio contenga la chiave.
"""

from __future__ import annotations

import socket
from types import SimpleNamespace

import pytest

from astrotwo import messages_catalog as mc
from astrotwo.ai import provider_adapter as pa
from astrotwo.ai.provider_adapter import (
    ProfileError,
    ProviderAdapterError,
    ProviderError,
    ProviderNotice,
    ProviderProfile,
    TurnOptions,
    make_adapter,
    profile_from_preset,
)
from tests.ai.fake_providers import FakeKeychain, Reply, UnavailableKeychain, provider_service  # noqa: F401
from tests.ai.test_provider_adapter import (
    CONVERSATION,
    FAKE_KEY,
    FAST,
    KINDS,
    TOOL,
    adapter,
    anthropic_text,
    error_reply,
    openai_text,
    text_reply,
)
from tests.message_helpers import catalog_combinations, check_error, check_message

OWN_CODES = ("AI_PROFILE_INVALID", "AI_AUTH", "AI_MODEL_NOT_FOUND", "AI_RATE_LIMIT", "AI_SERVICE",
             "AI_CONTEXT_TOO_LONG", "AI_NO_TOOLS", "AI_TIMEOUT", "AI_CONNECTION", "AI_BAD_RESPONSE",
             "AI_INSECURE_ENDPOINT", "AI_MODELS_UNAVAILABLE", "AI_RETRY")
#: Ragione di ``AI_BAD_RESPONSE`` che solo l'assistente del 35 produce (provata in ``test_messages_assistant.py``).
FROM_35 = {("AI_BAD_RESPONSE", "no_stop_reason")}


class Seen:
    def __init__(self) -> None:
        self.pairs: set[tuple[str, str | None]] = set()

    def event(self, event) -> object:
        """Errore o avviso del 30 controllato contro il catalogo; nessuna chiave nel testo, nei parametri o nel catalogo."""
        self.pairs.add(check_message(event.code, event.params, getattr(event, "message", None)
                                     or getattr(event, "text", None)))
        joined = " ".join([repr(event.params)] + [mc.message_text(event.code, event.params, lang)
                                                  for lang in ("en", "it")])
        assert FAKE_KEY not in joined
        return event

    def last(self, events) -> ProviderError:
        assert isinstance(events[-1], ProviderError), events
        return self.event(events[-1])


def stream_error(provider_service, kind, reply, **kw) -> ProviderError:
    provider_service.script = reply if isinstance(reply, list) else [reply]
    a, _, _ = adapter(kind, provider_service, **kw)
    return list(a.stream_turn(CONVERSATION, [TOOL], FAST))


@pytest.mark.parametrize("kind", KINDS)
def test_http_errors_carry_status_and_service_text(kind, provider_service):
    seen = Seen()
    cases = [(401, "invalid x-api-key", "AI_AUTH", None), (404, "model: test-model not found", "AI_MODEL_NOT_FOUND", None),
             (400, "prompt is too long: 300000 tokens > 200000 maximum", "AI_CONTEXT_TOO_LONG", None),
             (400, "registry.ollama.ai/library/m:latest does not support tools", "AI_NO_TOOLS", None),
             (400, "bad request", "AI_SERVICE", "rejected")]
    for status, text, code, reason in cases:
        error = seen.last(stream_error(provider_service, kind, error_reply(kind, status, text)))
        assert error.code == code and error.params["status"] == status and text in error.params["detail"]
        assert error.params.get("reason") == reason
    # troppe richieste e errore del servizio dopo le ripetizioni (avvisi di ripetizione compresi)
    events = stream_error(provider_service, kind, [error_reply(kind, 429, "slow", {"retry-after": "7"})] * 3)
    error = seen.last(events)
    assert error.code == "AI_RATE_LIMIT" and error.retry_after == 7.0 and error.params["status"] == 429
    notices = [seen.event(e) for e in events if isinstance(e, ProviderNotice)]
    assert notices[0].params == {"reason": "http_status", "status": 429, "error_code": "AI_RATE_LIMIT",
                                 "wait": {"value": 7.0, "unit": "s"}, "attempt": 2, "attempts": 3}
    assert notices[0].text.startswith("ripetuta dopo AI_RATE_LIMIT (troppe richieste (HTTP 429)), attesa 7 s")
    assert mc.message_text(notices[0].code, notices[0].params, "en") == (
        "Repeated after AI_RATE_LIMIT (HTTP 429), waiting 7.0 s (attempt 2 of 3).")
    error = seen.last(stream_error(provider_service, kind, [error_reply(kind, 500, "overloaded")] * 3))
    assert error.code == "AI_SERVICE" and error.params["reason"] == "http_error"
    assert seen.pairs >= {("AI_AUTH", None), ("AI_RATE_LIMIT", None), ("AI_RETRY", "http_status"),
                          ("AI_SERVICE", "http_error"), ("AI_SERVICE", "rejected")}


@pytest.mark.parametrize("kind", KINDS)
def test_timeouts_and_connection(kind, provider_service):
    seen = Seen()
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    profile = ProviderProfile(kind=kind, base_url=f"http://127.0.0.1:{port}", model="m")
    a = make_adapter(profile, FakeKeychain({profile.id: FAKE_KEY}), sleep=lambda w: None)
    events = list(a.stream_turn(CONVERSATION, [TOOL], FAST))
    error = seen.last(events)
    assert error.code in ("AI_CONNECTION", "AI_TIMEOUT")
    if error.code == "AI_CONNECTION":
        assert error.params["host"] == "127.0.0.1"
        assert seen.event([e for e in events if isinstance(e, ProviderNotice)][0]).params["reason"] == "connection"
    error = seen.last(stream_error(provider_service, kind, Reply(chunks=["x"], delay_first=1.6)))
    assert error.params == {"reason": "connect_read", "connect": {"value": 1.0, "unit": "s"},
                            "read": {"value": 1.0, "unit": "s"}}
    body = anthropic_text(["a", "b"]) if kind == "anthropic" else openai_text(["a", "b"])
    error = seen.last(stream_error(provider_service, kind, Reply(chunks=body[:3] + [(0.8, body[3])] + body[4:])))
    assert error.params == {"reason": "silence", "silence": {"value": 0.3, "unit": "s"}}
    assert seen.pairs >= {("AI_TIMEOUT", "connect_read"), ("AI_TIMEOUT", "silence")}


def translate(a, events, key="k"):
    """Errore del 30 per una sequenza di eventi dell'SDK che il traduttore non accetta."""
    watchdog = SimpleNamespace(tick=lambda: None, reason=None)
    with pytest.raises(Exception) as info:
        list(a._translate(iter(events), watchdog))
    return a._classify(info.value, key, TurnOptions())[0]


def test_stream_problems_have_reasons(provider_service):
    seen = Seen()
    anthropic, _, _ = adapter("anthropic", provider_service)
    stop = SimpleNamespace(type="message_stop")
    start = SimpleNamespace(type="message_start", message=SimpleNamespace(usage=SimpleNamespace(
        input_tokens=1, output_tokens=1, cache_read_input_tokens=None, cache_creation_input_tokens=None)))
    delta = lambda reason: SimpleNamespace(type="message_delta", delta=SimpleNamespace(stop_reason=reason),  # noqa: E731
                                           usage=SimpleNamespace(output_tokens=1))
    cases = [(anthropic, [SimpleNamespace(type="error", error="boom")], "stream_error", {"detail": "boom"}),
             (anthropic, [SimpleNamespace(type="weird")], "unknown_event", {"event": "weird"}),
             (anthropic, [start], "stream_cut", {}),
             (anthropic, [start, delta("odd"), stop], "unknown_stop_reason", {"stop_reason": "odd"})]
    openai_adapter, _, _ = adapter("openai_compatible", provider_service)
    chunk = lambda reason: SimpleNamespace(usage=None, choices=[SimpleNamespace(  # noqa: E731
        delta=SimpleNamespace(refusal=None, content="x", tool_calls=None), finish_reason=reason)])
    cases += [(openai_adapter, [chunk(None)], "no_finish_reason", {}),
              (openai_adapter, [chunk("odd")], "unknown_finish_reason", {"finish_reason": "odd"})]
    for a, events, reason, fields in cases:
        error = seen.event(translate(a, events))
        assert error.code == "AI_BAD_RESPONSE" and error.params == {"reason": reason, **fields}, error
        assert error.message.startswith("risposta non conforme: RuntimeError: ")
    other = seen.event(anthropic._classify(ValueError("inatteso"), FAKE_KEY, TurnOptions())[0])
    assert other.params == {"reason": "other", "error_type": "ValueError", "detail": "inatteso"}
    assert {("AI_BAD_RESPONSE", r) for r in ("stream_error", "unknown_event", "stream_cut", "unknown_stop_reason",
                                             "no_finish_reason", "unknown_finish_reason", "other")} <= seen.pairs


def test_profile_endpoint_models_and_relayed_errors(provider_service):
    seen = Seen()
    errors: list[ProfileError] = []
    for call in (lambda: ProviderProfile("x", "https://a.org", "m"), lambda: ProviderProfile("anthropic", "ftp://a", "m"),
                 lambda: ProviderProfile("anthropic", "https://a.org", " "),
                 lambda: ProviderProfile("anthropic", "https://a.org", "m", max_output_tokens=0),
                 lambda: ProviderProfile("anthropic", "https://a.org", "m", preset="nope"),
                 lambda: ProviderProfile("anthropic", "https://a.org", "m", max_tokens_field="x"),
                 lambda: profile_from_preset("nope", "m")):
        with pytest.raises(ProfileError) as info:
            call()
        assert isinstance(info.value, ValueError)  # chi intercetta ValueError continua a funzionare
        seen.pairs.add(check_error(info.value))
        errors.append(info.value)
    assert errors[1].message == "base_url 'ftp://a': indirizzo http(s) obbligatorio"
    assert errors[1].params == {"reason": "base_url", "base_url": "ftp://a"}
    assert mc.message_text(errors[1].code, errors[1].params, "en") == "base_url ftp://a: an http(s) address is required."
    with pytest.raises(ProviderAdapterError) as info:
        make_adapter(ProviderProfile("openai_compatible", "http://example.org/v1", "m"), FakeKeychain())
    seen.pairs.add(check_error(info.value))
    assert info.value.params == {"base_url": "http://example.org/v1"}
    # elenco dei modelli non disponibile: la causa è un messaggio annidato
    provider_service.routes["/v1/models"] = [error_reply("anthropic", 404, "not found")]
    a, _, _ = adapter("anthropic", provider_service)
    notice = seen.event(a.list_models().notice)
    assert notice.params["cause"]["code"] == "AI_MODEL_NOT_FOUND" and notice.params["cause"]["params"]["status"] == 404
    assert "Elenco dei modelli non disponibile (Modello o endpoint inesistente (HTTP 404)" in mc.message_text(
        notice.code, notice.params, "it")
    # errori del 31 rilanciati con i loro params
    remote = ProviderProfile("openai_compatible", "https://api.example.org/v1", "m")
    relayed = list(make_adapter(remote, FakeKeychain()).stream_turn(CONVERSATION, [TOOL], FAST))[-1]
    assert relayed.code == "KEY_NOT_FOUND" and relayed.params == {"profile_id": remote.id}
    with pytest.raises(ProviderAdapterError) as info:
        make_adapter(remote, UnavailableKeychain()).list_models()
    assert info.value.code == "KEYCHAIN_UNAVAILABLE" and info.value.params["reason"] == "api_unavailable"
    required = {(c, r) for c, r in catalog_combinations(OWN_CODES) if r is not None or not mc.CATALOG[c].variants}
    missing = {p for p in required if p[0] in ("AI_PROFILE_INVALID", "AI_INSECURE_ENDPOINT", "AI_MODELS_UNAVAILABLE")}
    assert missing <= seen.pairs, sorted(missing - seen.pairs, key=str)
    assert pa and text_reply and FROM_35
