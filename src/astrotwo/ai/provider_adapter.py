# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Adattatore dei provider IA: un solo contratto "a capacità" (chiamata di strumenti e streaming) (livello 3).

Specifica: ``mdfiles/30-ia-adattatore-provider.md`` (stato ``approvato``).

Due implementazioni con gli SDK ufficiali: ``AnthropicAdapter`` (API Messages, SDK ``anthropic``) e
``OpenAICompatibleAdapter`` (Chat Completions, SDK ``openai`` con l'indirizzo del profilo). L'adattatore non
calcola e non interpreta: traduce formati e trasporta testo ed eventi. Nessun identificativo di modello nel
codice; la chiave si legge dal 31 a ogni turno e non va mai in log né nel ``RequestRecord``.
"""

from __future__ import annotations

import copy
import json
import logging
import re
import threading
import time
import urllib.parse
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from astrotwo.ai.keychain_keys import KeychainError, _clean_text

__all__ = [
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "CONNECT_TIMEOUT",
    "READ_TIMEOUT",
    "SILENCE_TIMEOUT",
    "ProviderErrorCode",
    "ProviderAdapterError",
    "ProviderPreset",
    "PROVIDER_PRESETS",
    "ProviderProfile",
    "profile_from_preset",
    "SystemMessage",
    "UserMessage",
    "ToolCall",
    "AssistantMessage",
    "ToolResultMessage",
    "ToolDefinition",
    "TOOL_CHOICES",
    "TurnOptions",
    "TextDelta",
    "ToolCallRequest",
    "Usage",
    "ProviderNotice",
    "TurnEnd",
    "ProviderError",
    "RequestRecord",
    "ProviderCapabilities",
    "ModelInfo",
    "ModelList",
    "ProbeResult",
    "ProviderAdapter",
    "AnthropicAdapter",
    "OpenAICompatibleAdapter",
    "make_adapter",
]

#: Scelta minore 1 (confermata il 2026-10-16).
DEFAULT_MAX_OUTPUT_TOKENS = 4096
#: Tempi massimi (decisi il 2026-10-16, configurabili): connessione, lettura, silenzio nello streaming (s).
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 60.0
SILENCE_TIMEOUT = 30.0
#: Ripetizioni (scelta minore 3): al più 2, solo prima del primo evento.
MAX_RETRIES = 2
RETRY_STATUSES = (429, 500, 502, 503, 504, 529)
RETRY_WAITS = (1.0, 4.0)
MAX_RETRY_AFTER = 30.0
#: Segnaposto fisso non segreto per i server locali senza chiave (l'SDK openai ne richiede una, §3.6).
LOCAL_PLACEHOLDER_KEY = "astrotwo-local-no-key"
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")

#: Intestazioni ammesse nelle richieste (§3.6): le altre (anche da variabili d'ambiente lette dagli SDK) si tolgono.
_ALLOWED_HEADERS = ("authorization", "x-api-key", "anthropic-version", "anthropic-beta", "content-type",
                    "content-length", "accept", "accept-encoding", "user-agent", "host", "connection")
_ALLOWED_PREFIXES = ("x-stainless-",)


class ProviderErrorCode:
    """Codici di §10."""

    AUTH = "AI_AUTH"
    RATE_LIMIT = "AI_RATE_LIMIT"
    CONNECTION = "AI_CONNECTION"
    TIMEOUT = "AI_TIMEOUT"
    SERVICE = "AI_SERVICE"
    MODEL_NOT_FOUND = "AI_MODEL_NOT_FOUND"
    CONTEXT_TOO_LONG = "AI_CONTEXT_TOO_LONG"
    NO_TOOLS = "AI_NO_TOOLS"
    BAD_RESPONSE = "AI_BAD_RESPONSE"
    INSECURE_ENDPOINT = "AI_INSECURE_ENDPOINT"
    MODELS_UNAVAILABLE = "AI_MODELS_UNAVAILABLE"
    CANCELLED = "AI_CANCELLED"


class ProviderAdapterError(Exception):
    """Errore fuori dallo streaming (profilo, indirizzo, chiave) con codice di §10."""

    def __init__(self, code: str, message: str, *, params: Mapping[str, object] | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.params = dict(params or {})  # valori JSON del messaggio (D40-3); mai la chiave


class ProfileError(ValueError):
    """Profilo del provider non valido (``AI_PROFILE_INVALID``, 30 §10.1): sottoclasse di ``ValueError``."""

    def __init__(self, message: str, *, params: Mapping[str, object]) -> None:
        super().__init__(message)
        self.code = "AI_PROFILE_INVALID"
        self.message = message
        self.params = dict(params)


class _StreamProblem(RuntimeError):
    """Evento dello streaming non conforme; ``reason`` e ``fields`` diventano i ``params`` di ``AI_BAD_RESPONSE``."""

    def __init__(self, reason: str, message: str, **fields: object) -> None:
        super().__init__(message)
        self.params = {"reason": reason, **fields}


# --------------------------------------------------------------------------
# Log degli SDK e del trasporto (§3.6): al più WARNING e senza intestazioni né corpi
# --------------------------------------------------------------------------

_LIBRARY_LOGGERS = ("anthropic", "openai", "httpx", "httpx2", "httpcore", "httpcore2")


def _is_library(name: str) -> bool:
    return any(name == lib or name.startswith(lib + ".") for lib in _LIBRARY_LOGGERS)


def _quiet_library_logs() -> None:
    """Livello WARNING per le librerie e, alla creazione di ogni loro messaggio (anche dei moduli figli e qualunque
    gestore lo riceva), testo sostituito: intestazioni, corpi e chiavi non entrano mai in un log (§3.6)."""
    for name in _LIBRARY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    previous = logging.getLogRecordFactory()
    if getattr(previous, "_astrotwo_clean", False):
        return

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        if _is_library(record.name):
            record.msg = (f"messaggio della libreria {record.name} (testo omesso: intestazioni e corpi non si "
                          "registrano)")
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        return record

    factory._astrotwo_clean = True
    logging.setLogRecordFactory(factory)


_quiet_library_logs()


# --------------------------------------------------------------------------
# Profili e profili predefiniti (§3.1, §3.1.1)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderPreset:
    """Profilo predefinito (§3.1.1): indirizzo e note dalla documentazione ufficiale, con la fonte."""

    preset: str
    provider: str
    kind: str
    base_url: str
    tool_calling: str  # verified, documented, unverified
    sources: tuple[str, ...]
    notes: str
    max_tokens_field: str = "max_tokens"


#: Elenco chiuso dei profili predefiniti (decisione del proprietario del 2026-10-17; fonti consultate il 2026-10-17).
PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset("anthropic", "Anthropic", "anthropic", "https://api.anthropic.com", "documented",
                   ("https://platform.claude.com/docs/en/api/overview",),
                   "API Messages con tool_use; da provare con le chiavi dell'utente"),
    ProviderPreset("openai", "OpenAI", "openai_compatible", "https://api.openai.com/v1", "documented",
                   ("https://developers.openai.com/api/reference/overview",
                    "https://developers.openai.com/api/docs/guides/function-calling",
                    "https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/"
                    "methods/create"),
                   "alcuni modelli chiamano strumenti solo con la Responses API (AI_NO_TOOLS); max_tokens deprecato "
                   "a favore di max_completion_tokens", max_tokens_field="max_completion_tokens"),
    ProviderPreset("gemini", "Google Gemini", "openai_compatible",
                   "https://generativelanguage.googleapis.com/v1beta/openai/", "documented",
                   ("https://ai.google.dev/gemini-api/docs/openai",),
                   "compatibilità con le librerie OpenAI dichiarata in beta"),
    ProviderPreset("mistral", "Mistral AI", "openai_compatible", "https://api.mistral.ai/v1", "documented",
                   ("https://docs.mistral.ai/api/", "https://docs.mistral.ai/api/endpoint/models",
                    "https://docs.mistral.ai/capabilities/function_calling/"),
                   "chiamata di funzioni solo per alcuni modelli (elenco non esaustivo)"),
    ProviderPreset("deepseek", "DeepSeek", "openai_compatible", "https://api.deepseek.com", "documented",
                   ("https://api-docs.deepseek.com/", "https://api-docs.deepseek.com/guides/tool_calls"),
                   "Chat Completions non accetta chiamate di strumenti inserite a metà conversazione"),
    ProviderPreset("xai", "xAI", "openai_compatible", "https://api.x.ai/v1", "unverified",
                   ("https://docs.x.ai/docs/api-reference",
                    "https://docs.x.ai/developers/model-capabilities/legacy/chat-completions"),
                   "Chat Completions è un endpoint legacy; la chiamata di strumenti non è dichiarata su questo endpoint"),
    ProviderPreset("groq", "Groq", "openai_compatible", "https://api.groq.com/openai/v1", "documented",
                   ("https://console.groq.com/docs/openai", "https://console.groq.com/docs/tool-use"),
                   "campi non supportati: logprobs, logit_bias, top_logprobs, messages[].name (non inviati)"),
    ProviderPreset("openrouter", "OpenRouter", "openai_compatible", "https://openrouter.ai/api/v1", "documented",
                   ("https://openrouter.ai/docs/quickstart",
                    "https://openrouter.ai/docs/guides/features/tool-calling"),
                   "solo i modelli con il parametro tools; intestazioni facoltative delle classifiche non inviate"),
    ProviderPreset("ollama", "Ollama (locale)", "openai_compatible", "http://localhost:11434/v1", "verified",
                   ("https://docs.ollama.com/api/openai-compatibility",),
                   "verificato il 2026-10-16 (modello nel 30 §13); la chiave è richiesta dal client ma ignorata"),
    ProviderPreset("lmstudio", "LM Studio (locale)", "openai_compatible", "http://localhost:1234/v1", "documented",
                   ("https://lmstudio.ai/docs/app/api/endpoints/openai",
                    "https://lmstudio.ai/docs/developer/openai-compat/tools"),
                   "prova nostra rimandata (LM Studio non installato)"),
)
_PRESETS = {p.preset: p for p in PROVIDER_PRESETS}


@dataclass(frozen=True)
class ProviderProfile:
    """Profilo (§3.1): mai la chiave. ``id`` e ``local`` sono ricavati da ``base_url``."""

    kind: str
    base_url: str
    model: str
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    preset: str = "custom"
    max_tokens_field: str = "max_tokens"

    def __post_init__(self) -> None:
        if self.kind not in ("anthropic", "openai_compatible"):
            raise ProfileError(f"kind {self.kind!r}: anthropic oppure openai_compatible",
                               params={"reason": "kind", "kind": str(self.kind)})
        parsed = urllib.parse.urlsplit(self.base_url or "")
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ProfileError(f"base_url {self.base_url!r}: indirizzo http(s) obbligatorio",
                               params={"reason": "base_url", "base_url": str(self.base_url)})
        if not isinstance(self.model, str) or not self.model.strip():
            raise ProfileError("model: scelto dall'utente (nessun modello predefinito nel codice)",
                               params={"reason": "model_required"})
        if isinstance(self.max_output_tokens, bool) or not isinstance(self.max_output_tokens, int) \
                or self.max_output_tokens <= 0:
            raise ProfileError("max_output_tokens: intero > 0", params={"reason": "max_output_tokens"})
        if self.preset != "custom" and self.preset not in _PRESETS:
            raise ProfileError(f"preset {self.preset!r} non nell'elenco",
                               params={"reason": "preset_unknown", "preset": str(self.preset)})
        if self.max_tokens_field not in ("max_tokens", "max_completion_tokens"):
            raise ProfileError("max_tokens_field: max_tokens o max_completion_tokens",
                               params={"reason": "max_tokens_field"})

    @property
    def host(self) -> str:
        return urllib.parse.urlsplit(self.base_url).hostname

    @property
    def local(self) -> bool:
        return self.host in _LOCAL_HOSTS

    @property
    def id(self) -> str:
        """``anthropic`` oppure ``openai-compatible:<host>[:<porta>]`` (scelta minore 4); account del 31."""
        if self.kind == "anthropic":
            return "anthropic"
        port = urllib.parse.urlsplit(self.base_url).port
        return f"openai-compatible:{self.host}" + (f":{port}" if port is not None else "")

    @property
    def tool_calling_status(self) -> str:
        return _PRESETS[self.preset].tool_calling if self.preset in _PRESETS else "unverified"


def profile_from_preset(preset: str, model: str, *, max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
                        base_url: str | None = None) -> ProviderProfile:
    """Profilo da un profilo predefinito; il modello lo sceglie l'utente; indirizzo modificabile."""
    if preset not in _PRESETS:
        raise ProfileError(f"preset {preset!r} non nell'elenco ({', '.join(_PRESETS)})",
                           params={"reason": "preset_not_in_list", "preset": preset, "presets": list(_PRESETS)})
    p = _PRESETS[preset]
    return ProviderProfile(kind=p.kind, base_url=base_url or p.base_url, model=model,
                           max_output_tokens=max_output_tokens, preset=preset, max_tokens_field=p.max_tokens_field)


# --------------------------------------------------------------------------
# Messaggi, strumenti, eventi (§3.5)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SystemMessage:
    text: str


@dataclass(frozen=True)
class UserMessage:
    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # testo JSON completo, come ricevuto


@dataclass(frozen=True)
class AssistantMessage:
    text: str | None
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class ToolResultMessage:
    call_id: str
    content: str  # JSON del 32
    is_error: bool = False


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict


#: Valori di ``TurnOptions.tool_choice`` (§3.5, decisione del proprietario del 2026-10-22).
TOOL_CHOICES = ("auto", "none")


@dataclass(frozen=True)
class TurnOptions:
    max_output_tokens: int | None = None  # None: quello del profilo
    connect_timeout: float = CONNECT_TIMEOUT
    read_timeout: float = READ_TIMEOUT
    silence_timeout: float = SILENCE_TIMEOUT
    tool_choice: str = "auto"  # auto: nessun campo inviato; none: il modello non chiama strumenti (con strumenti)

    def __post_init__(self) -> None:
        if self.tool_choice not in TOOL_CHOICES:
            raise ValueError(f"tool_choice {self.tool_choice!r}: {' o '.join(TOOL_CHOICES)}")


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCallRequest:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None


@dataclass(frozen=True)
class ProviderNotice:
    """Avviso di una ripetizione (``AI_RETRY``): ``text`` è il testo italiano, ``params`` i valori del messaggio."""

    code: str
    text: str
    params: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TurnEnd:
    reason: str  # end, tool_use, max_tokens, refusal, cancelled


@dataclass(frozen=True)
class ProviderError:
    code: str
    message: str
    retry_after: float | None = None
    params: Mapping[str, object] = field(default_factory=dict)  # D40-3: valori JSON del messaggio


@dataclass(frozen=True)
class RequestRecord:
    """Corpo JSON esatto inviato, senza intestazioni né chiave, con indirizzo e ora UTC (§3.6)."""

    url: str
    sent_at: str
    body: dict


@dataclass(frozen=True)
class ProviderCapabilities:
    tool_calling: bool | None  # None: non ancora noto (openai_compatible prima della prova)
    streaming: bool
    parallel_tool_calls: bool | None
    max_context_tokens: int | None  # None: non dichiarato
    local: bool


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str | None = None
    max_context_tokens: int | None = None


@dataclass(frozen=True)
class ModelList:
    models: tuple[ModelInfo, ...]
    notice: ProviderError | None = None  # AI_MODELS_UNAVAILABLE: identificativo da scrivere a mano


@dataclass(frozen=True)
class ProbeResult:
    """Esito di "Prova il modello": chiamata di strumenti sì/no, token, errore."""

    tool_calling: bool
    usage: Usage | None
    error: ProviderError | None = None


# --------------------------------------------------------------------------
# Trasporto ed errori
# --------------------------------------------------------------------------


def _strip_headers(request) -> None:
    """Solo le intestazioni dell'elenco chiuso (§3.6): via quelle aggiunte da variabili d'ambiente."""
    for name in list(request.headers.keys()):
        low = name.lower()
        if low not in _ALLOWED_HEADERS and not low.startswith(_ALLOWED_PREFIXES):
            del request.headers[name]


def _http_client(options: TurnOptions):
    import httpx2

    timeout = httpx2.Timeout(options.read_timeout, connect=options.connect_timeout)
    # trust_env=False: niente .netrc né variabili d'ambiente del trasporto.
    return httpx2.Client(timeout=timeout, trust_env=False, event_hooks={"request": [_strip_headers]})


_CONTEXT_HINT = re.compile(r"prompt is too long|context[ _-]?length|context window|maximum context|too many tokens|"
                           r"context_length_exceeded", re.I)
_TOOLS_HINT = re.compile(r"(does not support|not support(ed)?|unsupported)\W+(\w+\W+){0,4}(tools?|function)|"
                         r"(tools?|function calling)\W+(\w+\W+){0,4}(not supported|unsupported)", re.I)


def _retry_after(response) -> float | None:
    if response is None:
        return None
    headers = response.headers
    for name, scale in (("retry-after-ms", 1e-3), ("retry-after", 1.0)):
        value = headers.get(name)
        if value is None:
            continue
        try:
            return float(value) * scale
        except ValueError:
            continue
    return None


def _status_error(status: int, text: str, retry_after: float | None) -> tuple[ProviderError, bool]:
    """(errore di §10, ripetibile)."""
    if status in (401, 403):
        return ProviderError(ProviderErrorCode.AUTH, f"chiave non valida o senza permessi (HTTP {status}): {text}",
                             params={"status": status, "detail": text}), False
    if status == 404:
        return ProviderError(ProviderErrorCode.MODEL_NOT_FOUND, f"modello o endpoint inesistente (HTTP 404): {text}",
                             params={"status": status, "detail": text}), False
    if status == 429:
        return ProviderError(ProviderErrorCode.RATE_LIMIT, f"troppe richieste (HTTP 429): {text}", retry_after,
                             params={"status": status, "detail": text}), True
    if status in RETRY_STATUSES:
        return ProviderError(ProviderErrorCode.SERVICE, f"errore del servizio (HTTP {status}): {text}",
                             retry_after, params={"reason": "http_error", "status": status, "detail": text}), True
    if _CONTEXT_HINT.search(text):
        return ProviderError(ProviderErrorCode.CONTEXT_TOO_LONG, f"conversazione oltre il contesto del modello "
                             f"(HTTP {status}): {text}", params={"status": status, "detail": text}), False
    if _TOOLS_HINT.search(text):
        return ProviderError(ProviderErrorCode.NO_TOOLS, f"il modello non chiama strumenti (HTTP {status}): {text}",
                             params={"status": status, "detail": text}), False
    return ProviderError(ProviderErrorCode.SERVICE, f"richiesta rifiutata dal servizio (HTTP {status}): {text}",
                         params={"reason": "rejected", "status": status, "detail": text}), False


def _response_text(exc) -> str:
    response = getattr(exc, "response", None)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        return json.dumps(body)[:500]
    if response is not None:
        try:
            return response.text[:500]
        except Exception:  # noqa: BLE001 - corpo dello streaming non letto
            pass
    return str(getattr(exc, "message", exc))[:500]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class _Watchdog:
    """Chiude lo streaming dopo ``silence`` secondi senza eventi o all'annullamento (§3.7)."""

    def __init__(self, stream, silence: float, cancel) -> None:
        self.stream, self.silence, self.cancel = stream, silence, cancel
        self.last = time.monotonic()
        self.reason: str | None = None
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    _GRACE = 0.2  # con eventi in arrivo lo Stop lo applica il thread che legge, senza chiudere da qui

    def _run(self) -> None:
        while not self._done.wait(0.02):
            idle = time.monotonic() - self.last
            if self.cancel is not None and self.cancel.cancelled:
                self.reason = "cancelled"
                if idle < self._GRACE:
                    continue
            elif idle > self.silence:
                self.reason = "silence"
            else:
                continue
            if not self._done.is_set():
                try:
                    self.stream.close()  # il thread che legge è fermo sulla rete: lo sblocca
                except Exception:  # noqa: BLE001
                    pass
            return

    def tick(self) -> None:
        self.last = time.monotonic()
        if self.cancel is not None and self.cancel.cancelled:
            self.reason = "cancelled"

    def stop(self) -> None:
        self._done.set()
        self._thread.join(timeout=5.0)


# --------------------------------------------------------------------------
# Contratto comune (§3.3–§3.7)
# --------------------------------------------------------------------------


class ProviderAdapter:
    """Contratto: ``capabilities``, ``list_models``, ``stream_turn``, ``probe_tools``, ``last_request``."""

    kind = ""

    def __init__(self, profile: ProviderProfile, keychain, *, sleep: Callable[[float], None] = time.sleep) -> None:
        _check_transport(profile)
        if profile.kind != self.kind:
            raise ValueError(f"profilo {profile.kind}: serve {self.kind}")
        self.profile = profile
        self.keychain = keychain
        self._sleep = sleep
        self._last: RequestRecord | None = None
        self._tool_calling: bool | None = self._declared_tool_calling()
        self._context: int | None = None

    # --- da specializzare ---------------------------------------------------------------
    def _declared_tool_calling(self) -> bool | None:
        return None

    def _client(self, key: str, options: TurnOptions):
        raise NotImplementedError

    def _url(self) -> str:
        raise NotImplementedError

    def _body(self, messages, tools, options: TurnOptions) -> dict:
        raise NotImplementedError

    def _open(self, client, body: dict):
        raise NotImplementedError

    def _translate(self, stream, watchdog: _Watchdog) -> Iterator[object]:
        raise NotImplementedError

    def _models(self, client) -> list[ModelInfo]:
        raise NotImplementedError

    # --- comuni -----------------------------------------------------------------------------
    def _key(self) -> str:
        """Chiave dal 31 all'inizio del turno; segnaposto fisso per un profilo locale senza chiave (§3.6)."""
        try:
            return self.keychain.get_key(self.profile.id).reveal()
        except KeychainError as exc:
            if exc.code == "KEY_NOT_FOUND" and self.profile.local:
                return LOCAL_PLACEHOLDER_KEY
            raise

    def last_request(self) -> RequestRecord | None:
        return self._last

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(tool_calling=self._tool_calling, streaming=True,
                                    parallel_tool_calls=True if self.kind == "anthropic" else None,
                                    max_context_tokens=self._context, local=self.profile.local)

    def _clean(self, text: str, key: str) -> str:
        return _clean_text(text, key if key != LOCAL_PLACEHOLDER_KEY else None)

    def _classify(self, exc: BaseException, key: str, options: TurnOptions) -> tuple[ProviderError, bool]:
        import anthropic
        import openai

        timeout_types = (anthropic.APITimeoutError, openai.APITimeoutError)
        connection_types = (anthropic.APIConnectionError, openai.APIConnectionError)
        status_types = (anthropic.APIStatusError, openai.APIStatusError)
        if isinstance(exc, timeout_types):
            return ProviderError(ProviderErrorCode.TIMEOUT, f"tempo massimo superato (connessione "
                                 f"{options.connect_timeout:g} s, lettura {options.read_timeout:g} s)",
                                 params={"reason": "connect_read",
                                         "connect": {"value": options.connect_timeout, "unit": "s"},
                                         "read": {"value": options.read_timeout, "unit": "s"}}), False
        if isinstance(exc, connection_types):
            detail = self._clean(str(exc), key)
            return ProviderError(ProviderErrorCode.CONNECTION, f"connessione impossibile con "
                                 f"{self.profile.host}: {detail}",
                                 params={"host": self.profile.host, "detail": detail}), True
        if isinstance(exc, status_types):
            return _status_error(exc.status_code, self._clean(_response_text(exc), key),
                                 _retry_after(getattr(exc, "response", None)))
        detail = self._clean(str(exc), key)
        if isinstance(exc, _StreamProblem):  # evento dello streaming non conforme: motivo e valori strutturati
            return ProviderError(ProviderErrorCode.BAD_RESPONSE, f"risposta non conforme: RuntimeError: {detail}",
                                 params=dict(exc.params)), False
        return ProviderError(ProviderErrorCode.BAD_RESPONSE, f"risposta non conforme: {type(exc).__name__}: "
                             f"{detail}", params={"reason": "other", "error_type": type(exc).__name__,
                                                  "detail": detail}), False

    def stream_turn(self, messages: Sequence[object], tools: Sequence[ToolDefinition] = (),
                    options: TurnOptions | None = None, cancel=None) -> Iterator[object]:
        """Una richiesta; eventi normalizzati man mano che arrivano (§3.5)."""
        options = TurnOptions() if options is None else options
        try:
            key = self._key()
        except KeychainError as exc:
            yield ProviderError(exc.code, exc.message, params=exc.params)
            return
        body = self._body(list(messages), list(tools), options)
        self._last = RequestRecord(url=self._url(), sent_at=_now(), body=copy.deepcopy(body))
        client = self._client(key, options)
        try:
            yield from self._run(client, body, key, options, cancel)
        finally:
            client.close()

    def _run(self, client, body, key, options, cancel) -> Iterator[object]:
        attempt = 0
        while True:
            if cancel is not None and cancel.cancelled:
                yield TurnEnd("cancelled")
                return
            try:
                stream = self._open(client, body)
                break
            except Exception as exc:  # noqa: BLE001 - errori del servizio prima del primo evento
                error, retryable = self._classify(exc, key, options)
                if error.code == ProviderErrorCode.NO_TOOLS:
                    self._tool_calling = False
                if not retryable or attempt >= MAX_RETRIES:
                    yield error
                    return
                wait = error.retry_after if error.retry_after is not None else RETRY_WAITS[attempt]
                wait = min(wait, MAX_RETRY_AFTER)
                attempt += 1
                yield self._retry_notice(error, wait, attempt)
                self._sleep(wait)
        watchdog = _Watchdog(stream, options.silence_timeout, cancel)
        try:
            for event in self._translate(stream, watchdog):
                if watchdog.reason:
                    break
                if isinstance(event, ToolCallRequest):
                    self._tool_calling = True
                yield event
        except Exception as exc:  # noqa: BLE001 - dopo il primo evento non si ripete mai (§3.7)
            if not watchdog.reason:
                error, _ = self._classify(exc, key, options)
                yield error
                return
        finally:
            watchdog.stop()
            try:
                stream.close()
            except Exception:  # noqa: BLE001
                pass
        if watchdog.reason == "cancelled":
            yield TurnEnd("cancelled")
        elif watchdog.reason == "silence":
            yield ProviderError(ProviderErrorCode.TIMEOUT, f"tempo massimo superato: {options.silence_timeout:g} s "
                                "di silenzio nello streaming",
                                params={"reason": "silence", "silence": {"value": options.silence_timeout,
                                                                           "unit": "s"}})

    def _retry_notice(self, error: ProviderError, wait: float, attempt: int) -> ProviderNotice:
        """Avviso della ripetizione ``attempt`` (già incrementato) dopo ``error``."""
        text = (f"ripetuta dopo {error.code} ({error.message.split(':')[0]}), attesa {wait:g} s (tentativo "
                f"{attempt + 1} di {MAX_RETRIES + 1})")
        common = {"error_code": error.code, "wait": {"value": wait, "unit": "s"}, "attempt": attempt + 1,
                  "attempts": MAX_RETRIES + 1}
        if error.code == ProviderErrorCode.CONNECTION:
            return ProviderNotice("AI_RETRY", text, {"reason": "connection", "host": error.params["host"], **common})
        return ProviderNotice("AI_RETRY", text, {"reason": "http_status", "status": error.params["status"], **common})

    def list_models(self) -> ModelList:
        """Elenco dei modelli dell'endpoint (§3.4); nessun elenco nel codice."""
        try:
            key = self._key()
        except KeychainError as exc:
            raise ProviderAdapterError(exc.code, exc.message, params=exc.params) from None
        client = self._client(key, TurnOptions())
        try:
            models = tuple(self._models(client))
        except Exception as exc:  # noqa: BLE001
            error, _ = self._classify(exc, key, TurnOptions())
            if error.code in (ProviderErrorCode.MODEL_NOT_FOUND, ProviderErrorCode.SERVICE,
                              ProviderErrorCode.BAD_RESPONSE):
                return ModelList((), ProviderError(
                    ProviderErrorCode.MODELS_UNAVAILABLE, "elenco dei modelli non "
                    f"disponibile ({error.message}): scrivere l'identificativo a mano",
                    params={"cause": {"code": error.code, "params": dict(error.params), "text": error.message}}))
            raise ProviderAdapterError(error.code, error.message, params=error.params) from None
        finally:
            client.close()
        for m in models:
            if m.id == self.profile.model:
                self._context = m.max_context_tokens
        return ModelList(models)

    def probe_tools(self, options: TurnOptions | None = None, cancel=None) -> ProbeResult:
        """"Prova il modello": richiesta minima con uno strumento di prova, avviata dall'utente (§3.3)."""
        tool = ToolDefinition("astrotwo_probe", "Probe tool of AstroTwo: call it with no arguments.",
                              {"type": "object", "properties": {}, "additionalProperties": False})
        messages = [UserMessage("Call the tool astrotwo_probe now, with no arguments.")]
        called, usage, error = False, None, None
        for event in self.stream_turn(messages, [tool], options, cancel):
            if isinstance(event, ToolCallRequest) and event.name == tool.name:
                called = True
            elif isinstance(event, Usage):
                usage = event
            elif isinstance(event, ProviderError):
                error = event
        if error is None:
            self._tool_calling = called
        return ProbeResult(called, usage, error)


def _check_transport(profile: ProviderProfile) -> None:
    """``https`` per gli endpoint remoti; ``http`` solo per gli host locali (§3.1)."""
    scheme = urllib.parse.urlsplit(profile.base_url).scheme
    if scheme != "https" and not profile.local:
        raise ProviderAdapterError(ProviderErrorCode.INSECURE_ENDPOINT, f"{profile.base_url}: un endpoint remoto "
                                   "deve essere https; nessuna richiesta inviata",
                                   params={"base_url": profile.base_url})


# --------------------------------------------------------------------------
# Anthropic (API Messages)
# --------------------------------------------------------------------------

_ANTHROPIC_STOP = {"end_turn": "end", "stop_sequence": "end", "tool_use": "tool_use", "max_tokens": "max_tokens",
                   "refusal": "refusal", "pause_turn": "end"}


class AnthropicAdapter(ProviderAdapter):
    kind = "anthropic"

    def _declared_tool_calling(self) -> bool | None:
        return True  # l'API Messages la offre (da verificare per ogni modello, §3.3)

    def _client(self, key: str, options: TurnOptions):
        import anthropic

        return anthropic.Anthropic(api_key=key, base_url=self.profile.base_url, max_retries=0,
                                   http_client=_http_client(options))

    def _url(self) -> str:
        return self.profile.base_url.rstrip("/") + "/v1/messages"

    def _body(self, messages, tools, options) -> dict:
        system = "\n\n".join(m.text for m in messages if isinstance(m, SystemMessage))
        out: list[dict] = []
        for m in messages:
            if isinstance(m, SystemMessage):
                continue
            if isinstance(m, UserMessage):
                block = {"type": "text", "text": m.text}
                if out and out[-1]["role"] == "user":
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
            elif isinstance(m, AssistantMessage):
                content = [{"type": "text", "text": m.text}] if m.text else []
                for call in m.tool_calls:
                    try:
                        arguments = json.loads(call.arguments) if call.arguments else {}
                    except json.JSONDecodeError:
                        arguments = {}
                    content.append({"type": "tool_use", "id": call.id, "name": call.name, "input": arguments})
                out.append({"role": "assistant", "content": content})
            elif isinstance(m, ToolResultMessage):
                block = {"type": "tool_result", "tool_use_id": m.call_id, "content": m.content,
                         "is_error": m.is_error}
                if out and out[-1]["role"] == "user" and all(b["type"] == "tool_result" for b in out[-1]["content"]):
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
            else:
                raise TypeError(f"messaggio {type(m).__name__} non previsto")
        body = {"model": self.profile.model,
                "max_tokens": options.max_output_tokens or self.profile.max_output_tokens,
                "messages": out, "stream": True}
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.input_schema}
                             for t in tools]
            if options.tool_choice == "none":
                body["tool_choice"] = {"type": "none"}
        return body

    def _open(self, client, body):
        return client.messages.create(**body)

    def _translate(self, stream, watchdog) -> Iterator[object]:
        tools: dict[int, dict] = {}
        usage = {"input": None, "output": None, "cache_read": None, "cache_creation": None}
        reason = None
        for event in stream:
            watchdog.tick()
            kind = getattr(event, "type", None)
            if kind == "message_start":
                u = event.message.usage
                usage.update(input=u.input_tokens, output=u.output_tokens,
                             cache_read=getattr(u, "cache_read_input_tokens", None),
                             cache_creation=getattr(u, "cache_creation_input_tokens", None))
            elif kind == "content_block_start":
                block = event.content_block
                if block.type == "tool_use":
                    tools[event.index] = {"id": block.id, "name": block.name, "json": ""}
            elif kind == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    yield TextDelta(delta.text)
                elif delta.type == "input_json_delta":
                    tools[event.index]["json"] += delta.partial_json
            elif kind == "content_block_stop":
                if event.index in tools:
                    t = tools.pop(event.index)
                    yield ToolCallRequest(t["id"], t["name"], t["json"] or "{}")
            elif kind == "message_delta":
                reason = event.delta.stop_reason
                if event.usage is not None and event.usage.output_tokens is not None:
                    usage["output"] = event.usage.output_tokens
            elif kind == "message_stop":
                break
            elif kind == "error":
                detail = str(getattr(event, "error", event))
                raise _StreamProblem("stream_error", f"errore nello streaming: {detail}", detail=detail)
            elif kind != "ping":
                raise _StreamProblem("unknown_event", f"evento sconosciuto {kind!r}", event=str(kind))
        else:
            if not watchdog.reason:
                raise _StreamProblem("stream_cut", "streaming interrotto prima di message_stop")
            return
        yield Usage(usage["input"], usage["output"], usage["cache_read"], usage["cache_creation"])
        if reason not in _ANTHROPIC_STOP:
            raise _StreamProblem("unknown_stop_reason", f"motivo di fine {reason!r} non previsto", stop_reason=str(reason))
        yield TurnEnd(_ANTHROPIC_STOP[reason])

    def _models(self, client) -> list[ModelInfo]:
        return [ModelInfo(m.id, getattr(m, "display_name", None), getattr(m, "max_input_tokens", None))
                for m in client.models.list()]


# --------------------------------------------------------------------------
# Compatibile OpenAI (Chat Completions)
# --------------------------------------------------------------------------

_OPENAI_STOP = {"stop": "end", "tool_calls": "tool_use", "function_call": "tool_use", "length": "max_tokens",
                "content_filter": "refusal"}


class OpenAICompatibleAdapter(ProviderAdapter):
    kind = "openai_compatible"

    def _client(self, key: str, options: TurnOptions):
        import openai

        return openai.OpenAI(api_key=key, base_url=self.profile.base_url, max_retries=0,
                             http_client=_http_client(options))

    def _url(self) -> str:
        return self.profile.base_url.rstrip("/") + "/chat/completions"

    def _body(self, messages, tools, options) -> dict:
        out: list[dict] = []
        for m in messages:
            if isinstance(m, SystemMessage):
                out.append({"role": "system", "content": m.text})
            elif isinstance(m, UserMessage):
                out.append({"role": "user", "content": m.text})
            elif isinstance(m, AssistantMessage):
                item: dict = {"role": "assistant", "content": m.text}
                if m.tool_calls:
                    item["tool_calls"] = [{"id": c.id, "type": "function",
                                           "function": {"name": c.name, "arguments": c.arguments}}
                                          for c in m.tool_calls]
                out.append(item)
            elif isinstance(m, ToolResultMessage):
                # Chat Completions non ha un campo d'errore: l'esito è nel contenuto JSON del 32.
                out.append({"role": "tool", "tool_call_id": m.call_id, "content": m.content})
            else:
                raise TypeError(f"messaggio {type(m).__name__} non previsto")
        body = {"model": self.profile.model, "messages": out, "stream": True,
                "stream_options": {"include_usage": True},
                self.profile.max_tokens_field: options.max_output_tokens or self.profile.max_output_tokens}
        if tools:
            body["tools"] = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                               "parameters": t.input_schema}} for t in tools]
            if options.tool_choice == "none":
                body["tool_choice"] = "none"
        return body

    def _open(self, client, body):
        return client.chat.completions.create(**body)

    def _translate(self, stream, watchdog) -> Iterator[object]:
        calls: dict[int, dict] = {}
        reason = None
        usage = None
        refused = False
        for chunk in stream:
            watchdog.tick()
            if getattr(chunk, "usage", None) is not None:
                u = chunk.usage
                details = getattr(u, "prompt_tokens_details", None)
                usage = Usage(u.prompt_tokens, u.completion_tokens, getattr(details, "cached_tokens", None))
            for choice in chunk.choices or ():
                delta = choice.delta
                if delta is not None:
                    if getattr(delta, "refusal", None):
                        refused = True
                        yield TextDelta(delta.refusal)
                    if delta.content:
                        yield TextDelta(delta.content)
                    for tc in delta.tool_calls or ():
                        slot = calls.setdefault(tc.index, {"id": None, "name": "", "args": ""})
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function is not None:
                            if tc.function.name:
                                slot["name"] += tc.function.name
                            if tc.function.arguments:
                                slot["args"] += tc.function.arguments
                if choice.finish_reason:
                    reason = choice.finish_reason
        if watchdog.reason:
            return
        if reason is None:
            raise _StreamProblem("no_finish_reason", "streaming finito senza finish_reason")
        for index in sorted(calls):
            c = calls[index]
            yield ToolCallRequest(c["id"] or f"call_{index}", c["name"], c["args"] or "{}")
        if usage is not None:
            yield Usage(usage.input_tokens, usage.output_tokens, usage.cache_read_tokens)
        if refused:
            yield TurnEnd("refusal")
            return
        if reason not in _OPENAI_STOP:
            raise _StreamProblem("unknown_finish_reason", f"finish_reason {reason!r} non previsto",
                                 finish_reason=str(reason))
        yield TurnEnd(_OPENAI_STOP[reason])

    def _models(self, client) -> list[ModelInfo]:
        out = []
        for m in client.models.list():
            extra = getattr(m, "model_extra", None) or {}
            context = extra.get("context_length") or extra.get("context_window")
            out.append(ModelInfo(m.id, extra.get("name"), int(context) if isinstance(context, (int, float)) else None))
        return out


def make_adapter(profile: ProviderProfile, keychain, **kwargs) -> ProviderAdapter:
    """Adattatore del profilo; controlla ``https`` (§3.1)."""
    _check_transport(profile)
    cls = AnthropicAdapter if profile.kind == "anthropic" else OpenAICompatibleAdapter
    return cls(profile, keychain, **kwargs)
