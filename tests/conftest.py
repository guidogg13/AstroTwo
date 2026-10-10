"""Configurazione comune dei test.

Servizio HTTP simulato locale (``service``) e cache temporanea (``cache``) per i moduli di rete.

Ogni test gira con una cartella home temporanea: così nessun test può
scrivere nella vera cache ``~/Library/Caches/AstroTwo/`` (04-cache.md §12).
"""

import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from astrotwo.core.cache import SharedCache


@pytest.fixture(autouse=True)
def _temporary_home(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    return home


class FakeService:
    """Server HTTP locale: ``routes[path] = funzione(richiesta) -> (stato, content-type, corpo)``."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        service = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _serve(self, method):
                parsed = urllib.parse.urlsplit(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                params = dict(urllib.parse.parse_qsl(parsed.query))
                if method == "POST" and self.headers.get("Content-Type", "").startswith("application/x-www-form"):
                    params.update(urllib.parse.parse_qsl(body.decode()))
                request = {"method": method, "path": parsed.path, "params": params, "body": body,
                           "headers": dict(self.headers)}
                service.requests.append(request)
                route = service.routes.get(parsed.path)
                if route is None:
                    status, ctype, payload, extra = 404, "text/plain", b"not found", []
                else:
                    status, ctype, payload, *extra = route(request)
                    payload = payload.encode() if isinstance(payload, str) else payload
                self.send_response(status)
                for name, value in (extra[0] if extra else {}).items():
                    self.send_header(name, value)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                self._serve("GET")

            def do_POST(self):
                self._serve("POST")

            def do_DELETE(self):
                self._serve("DELETE")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def hits(self, path):
        return sum(1 for r in self.requests if r["path"] == path)


@pytest.fixture
def service():
    fake = FakeService()
    yield fake
    fake.close()


@pytest.fixture
def cache(tmp_path):
    """Cache comune in una cartella temporanea (04-cache.md)."""
    with SharedCache(tmp_path / "cache") as shared:
        yield shared
