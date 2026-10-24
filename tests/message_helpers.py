# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Controlli comuni sui messaggi dei moduli rispetto al catalogo (D40-3, ``40`` §3.7.1, T18–T19)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping

from astrotwo.messages_catalog import CATALOG, REASON, message_text, validate_params

_LEFTOVER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


def check_message(code: str, params: Mapping[str, object] | None, text: str | None = None) -> tuple[str, str | None]:
    """Un messaggio dei moduli: voce nel catalogo, ``params`` conformi e JSON, testi senza segnaposto rimasti.

    Restituisce ``(codice, reason)`` per verificare la copertura delle sotto-voci.
    """
    assert code in CATALOG, f"{code}: nessuna voce nel catalogo"
    params = {} if params is None else params
    json.dumps(params)  # i parametri sono valori JSON
    assert validate_params(code, params) == [], (code, params)
    for lang in ("en", "it"):
        rendered = message_text(code, params, lang, text=text)
        assert not _LEFTOVER.search(rendered), (code, lang, rendered)
        assert "(no translation)" not in rendered and "(nessuna traduzione)" not in rendered, rendered
    return code, params.get(REASON)


def check_error(exc: BaseException) -> tuple[str, str | None]:
    """Eccezione di un modulo con ``code``, ``message`` e ``params``.

    Un errore rilanciato da un modulo sotto non ancora convertito (``relayed`` e senza ``params``, es. il 14 prima
    dello sprint 8d) non ha una voce da controllare: codice, testo e ``params`` restano dell'altro modulo."""
    if getattr(exc, "relayed", False) and not exc.params:
        return exc.code, None
    return check_message(exc.code, exc.params, exc.message)


def collect_errors(triggers: Iterable[Callable[[], object]], error_type: type[BaseException]) -> set[tuple[str, str | None]]:
    """Esegue le funzioni (ognuna deve sollevare ``error_type``) e controlla ogni errore; insieme di (codice, reason)."""
    seen = set()
    for trigger in triggers:
        try:
            trigger()
        except error_type as exc:
            seen.add(check_error(exc))
        else:
            raise AssertionError(f"{getattr(trigger, '__name__', trigger)} non ha sollevato {error_type.__name__}")
    return seen


def catalog_combinations(codes: Iterable[str]) -> set[tuple[str, str | None]]:
    """Tutte le coppie (codice, reason) del catalogo per i codici dati (più la voce generale)."""
    out: set[tuple[str, str | None]] = set()
    for code in codes:
        entry = CATALOG[code]
        out.add((code, None))
        out.update((code, reason) for reason in entry.variants)
    return out
