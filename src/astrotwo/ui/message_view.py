# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Testo dei messaggi dei moduli nella lingua dell'interfaccia (D40-3; ``40`` §3.7.1 e §3.7.2).

Il testo viene dal catalogo (``astrotwo.messages_catalog``) con i ``params`` del messaggio; il **codice** si mostra
sempre, invariato. Un codice senza voce, o un messaggio senza ``params`` per una voce che li richiede (sessione
scritta prima di D40-3), mostra il testo originale del modulo con la nota "(nessuna traduzione)".
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from astrotwo.core.commands import ResultMessage
from astrotwo.messages_catalog import LANGUAGES, message_text

__all__ = ["set_language", "language", "shown_text", "shown_line", "message_details", "ValueProblem",
           "exception_message", "shown_exception"]

_language = "en"


def set_language(lang: str) -> None:
    """Lingua dell'interfaccia (``en`` o ``it``), fissata all'avvio (cambia al riavvio, 40 §3.9)."""
    global _language
    _language = lang if lang in LANGUAGES else "en"


def language() -> str:
    return _language


def shown_text(message: ResultMessage) -> str:
    """Testo del messaggio nella lingua dell'interfaccia."""
    return message_text(message.code, message.params, _language, text=message.text)


def shown_line(message: ResultMessage) -> str:
    """``CODICE: testo`` come compare nelle righe di stato, nelle finestre e nei pannelli."""
    return f"{message.code}: {shown_text(message)}"


def message_details(message: ResultMessage) -> str:
    """Dettagli di una voce: testo originale del modulo e parametri, per il suggerimento e "Copia come JSON"."""
    lines = [message.text]
    if message.params:
        lines.append(json.dumps(dict(message.params), ensure_ascii=False, allow_nan=True))
    return "\n".join(lines)


class ValueProblem(ValueError):
    """Valore di un'impostazione non valido (``PREFERENCE_VALUE_INVALID``, 40 §10.1): sottoclasse di ``ValueError``
    con ``code``, ``message`` (italiano, invariato) e ``params`` per il catalogo. ``code`` è un altro solo per un
    errore già codificato di un modulo (es. ``AI_INSECURE_ENDPOINT`` di un profilo)."""

    def __init__(self, message: str, *, params: Mapping[str, object], code: str = "PREFERENCE_VALUE_INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.params = dict(params)


def exception_message(exc: BaseException) -> ResultMessage:
    """Messaggio di un'eccezione: se ha ``code`` e ``message`` (errori dei moduli) restano quelli con i loro ``params``;
    altrimenti ``UI_COMMAND_FAILED`` con il tipo e il testo dell'eccezione (testo di terzi, esterno)."""
    code, message = getattr(exc, "code", None), getattr(exc, "message", None)
    if isinstance(code, str) and isinstance(message, str):
        return ResultMessage(code, message, dict(getattr(exc, "params", None) or {}))
    return ResultMessage("UI_COMMAND_FAILED", f"{type(exc).__name__}: {exc}",
                         {"error_type": type(exc).__name__, "detail": str(exc)})


def shown_exception(exc: BaseException) -> str:
    """``CODICE: testo`` di un'eccezione nella lingua dell'interfaccia."""
    return shown_line(exception_message(exc))
