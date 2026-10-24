# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Configurazione comune dei test.

Servizio HTTP simulato locale (``service``) e cache temporanea (``cache``) per i moduli di rete.

Ogni test gira con una cartella home temporanea: così nessun test può
scrivere nella vera cache ``~/Library/Caches/AstroTwo/`` (04-cache.md §12).
"""

import os
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from astrotwo.core.cache import SharedCache

# Test dell'interfaccia con pytest-qt sulla piattaforma Qt ``offscreen`` (senza schermo, 40 §12). Qui e non in
# ``tests/ui/conftest.py``: un secondo modulo ``conftest`` nasconderebbe questo a ``tests/test_network_retries.py``.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Limite per test di rete (secondi): comprende le ripetizioni (``_with_network_retries``); gli altri test hanno
#: ``timeout`` di ``pyproject.toml`` (pytest-timeout, metodo ``thread``).
NETWORK_TEST_TIMEOUT = 600

pytest_plugins = ["pytester"]  # per il test della regola di ripetizione dei test di rete


@pytest.fixture(autouse=True)
def _memory_sky_renderer(request, monkeypatch):
    """Sulla piattaforma ``offscreen`` non c'è GPU: il visualizzatore del 41 disegna in memoria (tranne ``gl``)."""
    import sys

    if "astrotwo.ui.sky_viewer" in sys.modules and request.node.get_closest_marker("gl") is None:
        from tests.ui.fake_renderer import MemoryRenderer

        monkeypatch.setattr(sys.modules["astrotwo.ui.sky_viewer"], "DEFAULT_RENDERER", MemoryRenderer)


@pytest.fixture(autouse=True)
def _no_real_keychain(monkeypatch):
    """La finestra del 40 non usa mai il Portachiavi vero nei test (44 §12: Portachiavi simulato del 31)."""
    import sys

    if "astrotwo.ui.main_window" in sys.modules:
        from tests.ai.fake_providers import FakeKeychain

        monkeypatch.setattr(sys.modules["astrotwo.ui.main_window"], "default_keychain", FakeKeychain)


#: Errori dei moduli già in codice + ``params`` (D40-3): ogni istanza creata in un test viene controllata contro il
#: catalogo dei messaggi (voce, ``reason``, nomi e tipi dei parametri, JSON, testi senza segnaposto rimasti).
CONVERTED_ERROR_CLASSES = (
    ("astrotwo.core.coordinates_wcs", "CoordinatesWcsError"),
    ("astrotwo.core.images_fits", "ImagesFitsError"),
    ("astrotwo.core.hips", "HiPSError"),
)


@pytest.fixture(autouse=True, scope="session")
def _module_messages_match_catalog():
    import importlib

    try:
        from tests.message_helpers import check_error, check_message
    except ImportError:  # copia di questo conftest in un progetto di prova (pytester): niente controllo
        yield
        return

    restore = []
    for module_name, class_name in CONVERTED_ERROR_CLASSES:
        cls = getattr(importlib.import_module(module_name), class_name)
        original = cls.__init__

        def checked(self, *args, __original=original, **kwargs):
            __original(self, *args, **kwargs)
            check_error(self)

        cls.__init__ = checked
        restore.append((cls, "__init__", original))
    warning_cls = importlib.import_module("astrotwo.core.coordinates_wcs").ModuleWarning
    original_new = warning_cls.__new__

    def checked_new(cls, code, text, params=None):
        self = original_new(cls, code, text, params)
        from astrotwo.messages_catalog import has_message

        if has_message(code):  # i codici di moduli non ancora convertiti (es. CACHE_FULL) non hanno voce
            check_message(code, self.params, text)
        return self

    warning_cls.__new__ = checked_new
    restore.append((warning_cls, "__new__", original_new))
    yield
    for cls, name, original in restore:
        setattr(cls, name, original)


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
# Dal 2026-10-16 (decisione del proprietario) contano come la connessione anche le risposte HTTP
# 429, 502, 503 e 504 dei servizi esterni (servizio temporaneamente non disponibile).

NETWORK_RETRIES = 2
# Testi fissi con cui pyvo segnala connessione fallita o timeout (DALServiceError senza causa concatenata).
_PYVO_NETWORK_TEXTS = ("Connection failed", "Request timed out")
# Decisione del proprietario del 2026-10-16: servizio esterno temporaneamente non disponibile, trattato
# come la connessione (stesse ripetizioni, commit dichiarato). Gli altri 4xx restano risultati sbagliati.
TRANSIENT_HTTP_STATUSES = (429, 502, 503, 504)
_TRANSIENT_HTTP_TEXT = re.compile(r"\bHTTP (429|502|503|504)\b|\b(429|502|503|504) (?:Client|Server) Error\b")


def _transient_http_status(exc: BaseException) -> int | None:
    """Stato HTTP 429/502/503/504 dichiarato dall'eccezione (attributi o testo fisso), altrimenti ``None``."""
    response = getattr(exc, "response", None)
    details = getattr(exc, "details", None)
    for status in (getattr(exc, "status", None), getattr(response, "status_code", None),
                   details.get("status") if isinstance(details, dict) else None):
        if isinstance(status, int) and status in TRANSIENT_HTTP_STATUSES:
            return status
    match = _TRANSIENT_HTTP_TEXT.search(str(exc))
    return int(match.group(1) or match.group(2)) if match else None


def network_reason(exc: BaseException) -> str | None:
    """Motivo "di rete" (connessione, timeout, HTTP 429/502/503/504) lungo la catena delle cause, altrimenti ``None``."""
    import socket

    import requests

    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, AssertionError):
            return None
        if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout, ConnectionError,
                            TimeoutError, socket.timeout)):
            return f"connessione: {type(exc).__name__}"
        if getattr(exc, "code", None) == "NET_TIMEOUT":  # errori dei moduli di AstroTwo per la rete
            return f"connessione: {type(exc).__name__}"
        if type(exc).__name__ == "DALServiceError" and any(t in str(exc) for t in _PYVO_NETWORK_TEXTS):
            return f"connessione: {type(exc).__name__}"
        status = _transient_http_status(exc)
        if status is not None:
            return f"servizio temporaneamente non disponibile: HTTP {status} ({type(exc).__name__})"
        exc = exc.__cause__ or exc.__context__
    return None


def network_failure(exc: BaseException) -> bool:
    """Vero solo per connessione, timeout o servizio temporaneamente non disponibile (02-convenzioni.md §8)."""
    return network_reason(exc) is not None


def _with_network_retries(item):
    original = item.runtest

    def runtest():
        for attempt in range(NETWORK_RETRIES + 1):
            try:
                return original()
            except BaseException as exc:
                reason = network_reason(exc)
                if attempt == NETWORK_RETRIES or reason is None:
                    if reason is not None:
                        # Fallito ancora per la rete dopo le ripetizioni (02-convenzioni.md §8, punto 8).
                        item.user_properties.append(("network_final", reason))
                    raise
                item.user_properties.append(
                    ("network_retry", f"tentativo {attempt + 1} fallito per la rete "
                                      f"({type(exc).__name__}: {str(exc)[:200]}); ripetuto"))
    return runtest


def pytest_collection_modifyitems(config, items):
    for item in items:
        if item.get_closest_marker("network") is not None:
            item.runtest = _with_network_retries(item)
            if item.get_closest_marker("timeout") is None:
                # limite più alto (3 tentativi con i timeout di rete del 04), 600 s invece dei 120 s di default
                item.add_marker(pytest.mark.timeout(NETWORK_TEST_TIMEOUT))


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
