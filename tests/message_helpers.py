# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Controlli comuni sui messaggi dei moduli rispetto al catalogo (D40-3, ``40`` §3.7.1, T18–T19)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping

from astrotwo.messages_catalog import CATALOG, REASON, message_params, message_text, uses_catalog, validate_params

_LEFTOVER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


def check_message(code: str, params: Mapping[str, object] | None, text: str | None = None) -> tuple[str, str | None]:
    """Un messaggio dei moduli: voce nel catalogo, ``params`` conformi e JSON, testi senza segnaposto rimasti.

    Restituisce ``(codice, reason)`` per verificare la copertura delle sotto-voci.
    """
    assert code in CATALOG, f"{code}: nessuna voce nel catalogo"
    params = {} if params is None else params
    json.dumps(params)  # i parametri sono valori JSON
    assert validate_params(code, params) == [], (code, params)
    # Un messaggio annidato di un modulo non ancora convertito (D40-7) si mostra col testo originale e la nota.
    fallback = any(not uses_catalog(c, p) for c, p in _nested(code, params))
    for lang in ("en", "it"):
        rendered = message_text(code, params, lang, text=text)
        scrubbed = rendered
        for literal in ("${name}", "${nome}", "${...}"):  # graffe scritte nel testo (``{{``), non segnaposto
            scrubbed = scrubbed.replace(literal, "")
        for value in sorted(_strings(params), key=len, reverse=True):  # un valore può contenere graffe (${x})
            scrubbed = scrubbed.replace(value, "")
        assert not _LEFTOVER.search(scrubbed), (code, lang, rendered)
        if not fallback:
            assert "(no translation)" not in rendered and "(nessuna traduzione)" not in rendered, rendered
    return code, params.get(REASON)


def _strings(value: object):
    """Tutti i testi dei valori di ``params`` (anche annidati)."""
    if isinstance(value, str):
        if value:
            yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def _nested(code: str, params: Mapping[str, object] | None):
    """(codice, params) dei messaggi annidati (tipo ``message``, D40-7) di un messaggio, in modo ricorsivo."""
    for name in message_params(code, params):
        value = (params or {}).get(name)
        for item in (value if isinstance(value, (list, tuple)) else [value]):
            if isinstance(item, Mapping):
                inner = item.get("params") or {}
                yield item["code"], inner
                yield from _nested(item["code"], inner)


def nested_pairs(code: str, params: Mapping[str, object] | None) -> set[tuple[str, str | None]]:
    """Coppie (codice, reason) dei messaggi annidati con voce nel catalogo, controllate come ogni messaggio."""
    out = set()
    for inner_code, inner in _nested(code, params):
        if uses_catalog(inner_code, inner):
            out.add((inner_code, inner.get(REASON)))
    return out


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


#: Sotto-voci di codici condivisi che solo il modulo 14 solleva o restituisce (provate in ``test_messages_vo_protocols.py``).
MODULE_14_SUBVARIANTS = {
    ("NET_TIMEOUT", "url_sync_tap"), ("NET_TIMEOUT", "async_deadline"), ("BODY_UNKNOWN", "spectrum_without_candidate"),
    ("FORMAT_DECLARED", "recognized_differs"), ("TABLE_TOO_LARGE", "upload"),
    ("FROM_CACHE", "cached_origin"), ("FROM_CACHE", "network_cached"), ("FROM_CACHE", "cached_since"),
    ("FROM_CACHE", "network_unavailable"),
} | {("SERVICE_ERROR", r) for r in (
    "http_message", "http_message_async_hint", "http_no_votable", "service_rejected", "request_failed", "job_phase",
    "job_result_status", "descriptor_missing", "simbad_no_units")}

#: Sotto-voci di codici condivisi che solo il modulo 16 solleva o restituisce (provate in ``test_messages_moc.py``).
MODULE_16_SUBVARIANTS = {
    ("HEALPIX_ORDER_INVALID", "moc_order"), ("HEALPIX_ORDER_INVALID", "map_too_large"),
    ("BODY_UNKNOWN", "moc_without_body"), ("BODY_UNKNOWN", "no_moc"), ("BODY_UNKNOWN", "no_filter"),
    ("REGION_INVALID", "conversion"), ("REGION_INVALID", "not_finite"), ("REGION_INVALID", "polygon_vertices"),
    ("REGION_INVALID", "polygon_mocpy"), ("NO_COORD_COLUMNS", "no_positions"), ("NO_COORD_COLUMNS", "no_angular_unit"),
    ("FRAME_UNKNOWN", "columns_without_frame"), ("PREVIEW_NOT_MEASURABLE", "moc_from_image"),
    ("MOCSERVER_UNAVAILABLE", "filter"), ("SERVICE_ERROR", "mocserver_response"), ("FROM_CACHE", "cached_converted"),
}

#: Sotto-voci di codici condivisi che solo il modulo 19 solleva o restituisce (provate in ``test_messages_planetary.py``).
MODULE_19_SUBVARIANTS = (
    {("BODY_UNSUPPORTED", r) for r in ("no_name", "celestial", "no_naif", "not_in_table")}
    | {("BODY_UNKNOWN", r) for r in ("layer", "overlay_unknown", "layer_alone", "epntap_columns", "epntap_frames",
                                     "epntap_target", "pds_target", "pds_targets")}
    | {("BODY_MISMATCH", "multiple_in_layer"), ("BODY_MISMATCH", "overlay"), ("ADQL_INVALID", "epntap_core"),
       ("BODY_NORMALIZED", "pds_target"), ("BODY_NORMALIZED", "epntap_target")}
    | {("COORD_OUT_OF_RANGE", r) for r in ("planetary_not_finite", "planetary_latitude", "planetary_longitude")}
)

#: Sotto-voci di codici condivisi che solo il modulo 15 solleva o restituisce (provate in ``test_messages_crossmatch.py``).
MODULE_15_SUBVARIANTS = (
    {("TABLE_TOO_LARGE", "crossmatch_table"), ("TABLE_TOO_LARGE", "joined"), ("BODY_UNKNOWN", "crossmatch_table"),
     ("BODY_MISMATCH", "tables"), ("BODY_FORCED", "tables"), ("NO_COORD_COLUMNS", "crossmatch_no_positions"),
     ("NO_COORD_COLUMNS", "crossmatch_no_angular_unit"), ("NO_COORD_COLUMNS", "joined"),
     ("FRAME_UNKNOWN", "crossmatch_columns"), ("SERVICE_ERROR", "echo_mismatch")}
    | {("MAX_SEP_INVALID", r) for r in ("required", "not_angle", "range_local", "range_cds")}
)

#: Sotto-voci di codici condivisi che solo il modulo 17 solleva o restituisce (provate in ``test_messages_measures.py``).
MODULE_17_SUBVARIANTS = (
    {("FRAME_UNKNOWN", "measure_point"), ("FRAME_UNKNOWN", "measure_columns"), ("MEMORY_LIMIT_EXCEEDED", "profile"),
     ("NO_COORD_COLUMNS", "measure_no_positions"), ("NO_COORD_COLUMNS", "row_position_missing"),
     ("BODY_UNKNOWN", "measure_sources"), ("BODY_MISMATCH", "sources"), ("NONFINITE_PIXELS", "window"),
     ("NONFINITE_PIXELS", "samples")}
    | {("OPERATION_UNSUPPORTED", r) for r in ("shape_kind", "open_path", "text_distance")}
    | {("EPOCH_REQUIRED", r) for r in ("row_epoch", "pm_columns", "row_incomplete", "epoch_invalid")}
)
