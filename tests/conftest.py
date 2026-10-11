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

pytest_plugins = ["pytester"]  # per il test della regola di ripetizione dei test di rete


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


# --- Test di rete: ripetizione solo per errori di connessione o timeout -----------------------
# Decisione del proprietario del 2026-10-11: al massimo 2 ripetizioni, solo per i test con il
# marcatore ``network`` e solo se l'errore è di connessione o di timeout, mai per un risultato
# sbagliato (un AssertionError non si ripete); ogni ripetizione è scritta nel risultato del test.

NETWORK_RETRIES = 2
# Testi fissi con cui pyvo segnala connessione fallita o timeout (DALServiceError senza causa concatenata).
_PYVO_NETWORK_TEXTS = ("Connection failed", "Request timed out")


def network_failure(exc: BaseException) -> bool:
    """Vero solo per un errore di connessione o di timeout, cercato lungo la catena delle cause."""
    import socket

    import requests

    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, AssertionError):
            return False
        if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout, ConnectionError,
                            TimeoutError, socket.timeout)):
            return True
        if getattr(exc, "code", None) == "NET_TIMEOUT":  # errori dei moduli di AstroTwo per la rete
            return True
        if type(exc).__name__ == "DALServiceError" and any(t in str(exc) for t in _PYVO_NETWORK_TEXTS):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def _with_network_retries(item):
    original = item.runtest

    def runtest():
        for attempt in range(NETWORK_RETRIES + 1):
            try:
                return original()
            except BaseException as exc:
                if attempt == NETWORK_RETRIES or not network_failure(exc):
                    raise
                item.user_properties.append(
                    ("network_retry", f"tentativo {attempt + 1} fallito per la rete "
                                      f"({type(exc).__name__}: {str(exc)[:200]}); ripetuto"))
    return runtest


def pytest_collection_modifyitems(config, items):
    for item in items:
        if item.get_closest_marker("network") is not None:
            item.runtest = _with_network_retries(item)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    retries = [text for name, text in item.user_properties if name == "network_retry"]
    if report.when == "call" and retries:
        report.sections.append(("ripetizioni di rete", "\n".join(retries)))


def pytest_terminal_summary(terminalreporter):
    lines = []
    for reports in terminalreporter.stats.values():
        for report in reports:
            if getattr(report, "when", None) != "call":
                continue
            retries = [text for name, text in getattr(report, "user_properties", []) if name == "network_retry"]
            if retries:
                lines.append(f"{report.nodeid} [{report.outcome}] dopo {len(retries)} ripetizioni: "
                             + " | ".join(retries))
    if lines:
        terminalreporter.write_sep("-", "test di rete ripetuti per errori di connessione o timeout")
        for line in lines:
            terminalreporter.write_line(line)
