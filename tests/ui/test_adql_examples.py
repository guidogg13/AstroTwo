# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Esempi ADQL dei dialoghi (sprint B3, D42-2 (7)): T11 del ``42``.

Offline: ogni esempio supera ``validate_adql`` del 14, cita solo servizi TAP dell'elenco e non ha ``TOP``. Di rete
(marcatore ``network``, non eseguiti nel commit): ogni esempio eseguito sul servizio vero con ``tap_query`` del 14,
anche con la riga di commento di "Inserisci centro e raggio della vista" (tolta prima dell'invio).
"""

from __future__ import annotations

import pytest

import astrotwo.core.vo_protocols as vo
from astrotwo.ui.vo_query_dialogs import ADQL_EXAMPLES, VIEW_COMMENT_PREFIX

CASES = [(service, key, text) for service, items in ADQL_EXAMPLES.items() for key, text in items]


def test_examples_valid_offline():
    tap_ids = {e.id for e in vo.BUILTIN_SERVERS if e.protocol == "tap"}
    assert set(ADQL_EXAMPLES) <= tap_ids and len(CASES) == 6
    for _service, _key, text in CASES:
        assert vo.validate_adql(text).valid, text
        assert "TOP " not in text.upper()  # decide max_rows (MAXREC), troncamento dichiarato
        assert vo.adql_to_send(text) == text  # nessun commento negli esempi


@pytest.mark.network
@pytest.mark.parametrize(("service", "key", "text"), CASES, ids=[c[1] for c in CASES])
def test_examples_on_the_real_services(service, key, text, cache):
    comment = f"\n{VIEW_COMMENT_PREFIX}, ICRS, degrees; epoch of the centre: not known (not assumed)"
    mode = "async" if service == "esa-gaia-tap" else "sync"  # Gaia: la sincrona può superare i 60 s di lettura
    result = vo.tap_query(service, text + comment, max_rows=50, mode=mode, cache=cache, refresh=True)
    assert result.table.rows > 0, key
    assert result.table.positions is not None, key  # colonne di posizione riconosciute dagli UCD
    assert VIEW_COMMENT_PREFIX not in dict(result.request.params)["QUERY"]
