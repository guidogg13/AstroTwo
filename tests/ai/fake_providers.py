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
