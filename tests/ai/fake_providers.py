# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Servizi simulati locali dei provider IA (30 §12): nessuna rete, nessuna chiave reale.

``StreamingService`` risponde a ogni richiesta con il prossimo elemento di ``script`` (o di ``routes[path]``):
uno stato HTTP, intestazioni e una lista di pezzi di corpo, ciascuno con un'attesa facoltativa prima
dell'invio; così si simulano lo streaming a frammenti, il silenzio a metà e la chiusura dal client.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class Reply:
    def __init__(self, status=200, chunks=(), headers=None, ctype="text/event-stream", delay_first=0.0):
        self.status, self.chunks, self.headers, self.ctype = status, list(chunks), headers or {}, ctype
        self.delay_first = delay_first


def sse(events):
    """Eventi dell'API Messages di Anthropic come pezzi SSE."""
    return [f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events]


def sse_openai(chunks):
    return [f"data: {json.dumps(c)}\n\n" for c in chunks] + ["data: [DONE]\n\n"]


class StreamingService:
    def __init__(self):
        self.requests = []
        self.script: list[Reply] = []
        self.routes: dict[str, list[Reply]] = {}
        self.closed_early = threading.Event()
        service = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *args):
                pass

            def _serve(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                service.requests.append({"method": self.command, "path": self.path, "headers": dict(self.headers),
                                         "body": json.loads(body) if body else None})
                queue = service.routes.get(self.path.split("?")[0]) or service.script
                reply = queue.pop(0) if len(queue) > 1 else queue[0]
                if reply.delay_first:
                    time.sleep(reply.delay_first)
                self.send_response(reply.status)
                self.send_header("Content-Type", reply.ctype)
                for k, v in reply.headers.items():
                    self.send_header(k, v)
                self.end_headers()
                try:
                    for chunk in reply.chunks:
                        if isinstance(chunk, tuple):
                            wait, chunk = chunk
                            time.sleep(wait)
                        self.wfile.write(chunk.encode() if isinstance(chunk, str) else chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    service.closed_early.set()

            def do_GET(self):
                self._serve()

            def do_POST(self):
                self._serve()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def provider_service():
    fake = StreamingService()
    yield fake
    fake.close()


class FakeKeychain:
    """31 simulato: chiavi finte per identificativo del profilo."""

    def __init__(self, keys=None):
        self.keys = dict(keys or {})
        self.reads = []

    def get_key(self, profile_id):
        from astrotwo.ai.keychain_keys import KeychainError, SecretKey

        self.reads.append(profile_id)
        if profile_id not in self.keys:
            raise KeychainError("KEY_NOT_FOUND", f"nessuna chiave per {profile_id!r}")
        return SecretKey(self.keys[profile_id])

    def has_key(self, profile_id):
        return profile_id in self.keys

    def store_key(self, profile_id, key):
        self.keys[profile_id] = key.strip()

    def delete_key(self, profile_id):
        return "deleted" if self.keys.pop(profile_id, None) is not None else "nothing_to_delete"


class UnavailableKeychain:
    """Portachiavi che non risponde (KEYCHAIN_UNAVAILABLE)."""

    def has_key(self, profile_id):
        from astrotwo.ai.keychain_keys import KeychainError

        raise KeychainError("KEYCHAIN_UNAVAILABLE", "Portachiavi non disponibile (simulato)")

    get_key = has_key


# --------------------------------------------------------------------------
# Provider simulato a copione per il 35 (35 §12): sequenze di eventi del 30 scritte nei test
# --------------------------------------------------------------------------


def tool_call(call_id, tool, **arguments):
    from astrotwo.ai.provider_adapter import ToolCallRequest

    return ToolCallRequest(call_id, tool, json.dumps(arguments))


def calls_turn(*requests, usage=(100, 10)):
    from astrotwo.ai.provider_adapter import TurnEnd, Usage

    return [*requests, Usage(*usage), TurnEnd("tool_use")]


def text_turn(text, usage=(200, 30)):
    from astrotwo.ai.provider_adapter import TextDelta, TurnEnd, Usage

    return [TextDelta(text), *([Usage(*usage)] if usage else []), TurnEnd("end")]


def numbers_sent(messages):
    """Numeri ``#n`` dei risultati degli strumenti già mandati al modello, in ordine."""
    from astrotwo.ai.provider_adapter import ToolResultMessage

    return [json.loads(m.content)["command"]["number"] for m in messages if isinstance(m, ToolResultMessage)]


class ScriptedAdapter:
    """``ProviderAdapter`` finto (35 §12): ogni richiesta consuma un passo di ``script`` (lista di eventi, oppure
    funzione ``(messaggi, strumenti, cancel)`` che li genera). Il corpo JSON registrato è quello vero del 30
    (``_body`` dell'adattatore del tipo del profilo), così i test controllano ciò che uscirebbe dal Mac."""

    def __init__(self, script, *, kind="openai_compatible", base_url="https://api.example.invalid/v1",
                 model="modello-finto", keychain=None, tool_calling=True):
        from astrotwo.ai.provider_adapter import ProviderProfile, make_adapter

        self.profile = ProviderProfile(kind=kind, base_url=base_url, model=model)
        self.keychain = keychain if keychain is not None else FakeKeychain({self.profile.id: "sk-finta-0123456789"})
        self._real = make_adapter(self.profile, self.keychain)
        self.script = list(script)
        self.requests = []  # (messaggi, strumenti) di ogni richiesta
        self.options = []  # TurnOptions di ogni richiesta
        self.records = []
        self.tool_calling = tool_calling

    def capabilities(self):
        from astrotwo.ai.provider_adapter import ProviderCapabilities

        return ProviderCapabilities(self.tool_calling, True, None, None, self.profile.local)

    def last_request(self):
        return self.records[-1] if self.records else None

    def stream_turn(self, messages, tools=(), options=None, cancel=None):
        from astrotwo.ai.provider_adapter import RequestRecord, TurnEnd, TurnOptions

        messages, tools = list(messages), list(tools)
        options = options or TurnOptions()
        self.options.append(options)
        body = self._real._body(messages, tools, options)
        self.records.append(RequestRecord(self._real._url(), "2026-10-22T12:00:00+00:00", body))
        self.requests.append((messages, tools))
        step = self.script.pop(0) if self.script else text_turn("")
        events = step(messages, tools, cancel) if callable(step) else step
        for event in events:
            if cancel is not None and cancel.cancelled:
                yield TurnEnd("cancelled")
                return
            yield event
