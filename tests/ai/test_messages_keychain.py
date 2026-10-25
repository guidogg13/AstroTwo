# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 31 con codice + ``params`` (D40-3; ``40`` §3.7.1, T18–T19; ``31`` §10.1).

Con il Portachiavi simulato dei test del 31. Ogni errore è controllato contro il catalogo alla creazione
(``tests/conftest.py``); qui si verifica la copertura di tutte le coppie (codice, ragione) e che nessun parametro,
né testo, contenga la chiave.
"""

from __future__ import annotations

import sys

import pytest
from keyring.errors import KeyringError

from astrotwo import messages_catalog as mc
from astrotwo.ai import keychain_keys as kk
from astrotwo.ai.keychain_keys import KeychainError, KeychainStore
from tests.ai.test_keychain_keys import FAKE_KEY, security  # noqa: F401
from tests.message_helpers import catalog_combinations, check_error, nested_pairs

OWN_CODES = ("KEYCHAIN_UNAVAILABLE", "KEYCHAIN_ACCESS_DENIED", "KEYCHAIN_WRITE_FAILED", "KEY_NOT_FOUND",
             "KEY_FORMAT_INVALID", "KEYCHAIN_OPERATION")


def test_every_error_has_code_params_and_catalog_entry(security, monkeypatch):  # noqa: F811
    items, state = security
    seen: set[tuple[str, str | None]] = set()

    def raised(call) -> KeychainError:
        with pytest.raises(KeychainError) as info:
            call()
        exc = info.value
        seen.add(check_error(exc))
        seen.update(nested_pairs(exc.code, exc.params))
        joined = " ".join([exc.message, repr(exc.params)] + [mc.message_text(exc.code, exc.params, lang)
                                                              for lang in ("en", "it")])
        assert FAKE_KEY not in joined and "sk-finta" not in joined  # la chiave non è mai in un messaggio
        return exc

    store = KeychainStore()
    # formato della chiave
    for bad, reason in ((5, "not_text"), ("  ", "empty"), ("x" * 4097, "too_long"), ("sk-\x00finta", "control_characters")):
        assert raised(lambda bad=bad: store.store_key("p", bad)).params["reason"] == reason
    assert raised(lambda: store.store_key("p", "x" * 4097)).params == {"reason": "too_long", "length": 4097,
                                                                        "maximum": 4096}
    # chiave assente
    missing = raised(lambda: store.get_key("p"))
    assert missing.params == {"profile_id": "p"}
    assert mc.message_text(missing.code, missing.params, "it") == "Nessuna chiave nel Portachiavi per il profilo p."
    # accesso negato e scrittura fallita, con l'operazione annidata
    state["deny"] = True
    assert raised(lambda: store.store_key("p", FAKE_KEY)).params["operation"]["params"]["reason"] == "write"
    assert raised(lambda: store.get_key("p")).params["operation"]["params"]["reason"] == "read"
    state["deny"] = False
    store.store_key("p", FAKE_KEY)
    state["fail_write"] = True
    assert raised(lambda: store.store_key("p", FAKE_KEY)).code == "KEYCHAIN_WRITE_FAILED"
    delete_failed = raised(lambda: store.delete_key("p"))
    assert delete_failed.code == "KEYCHAIN_WRITE_FAILED" and delete_failed.params["operation"]["params"] == {
        "reason": "delete", "profile_id": "p"}
    state["fail_write"] = False
    # Portachiavi non raggiungibile (errore generico della libreria) in lettura, scrittura e cancellazione
    store.store_key("p", FAKE_KEY)

    def broken(*args, **kwargs):
        raise KeyringError("non raggiungibile")

    for method, call in (("get_password", lambda: store.get_key("p")),
                         ("set_password", lambda: store.store_key("p", FAKE_KEY)),
                         ("delete_password", lambda: store.delete_key("p"))):
        with monkeypatch.context() as patch:
            patch.setattr(store._backend, method, broken)
            unreachable = raised(call)
            assert unreachable.params["reason"] == "unreachable"
    assert mc.message_text("KEYCHAIN_UNAVAILABLE", unreachable.params, "en").startswith(
        "deleting the key of profile p: the Keychain cannot be reached (")
    # sistema non macOS, backend non caricabile, API non disponibile
    with monkeypatch.context() as patch:
        patch.setattr(kk.platform, "system", lambda: "Linux")
        assert raised(KeychainStore).params == {"reason": "not_macos", "system": "Linux"}
    import keyring.backends as backends
    from keyring.backends import macOS

    with monkeypatch.context() as patch:
        patch.delattr(backends, "macOS")
        patch.setitem(sys.modules, "keyring.backends.macOS", None)
        assert raised(KeychainStore).params["reason"] == "backend_not_loadable"
    with monkeypatch.context() as patch:
        patch.delitem(macOS.__dict__, "api")
        assert raised(KeychainStore).params["reason"] == "api_unavailable"
    assert items

    required = {(c, r) for c, r in catalog_combinations(OWN_CODES) if r is not None or not mc.CATALOG[c].variants}
    assert required <= seen, f"errori del 31 mai provocati nel test: {sorted(required - seen, key=str)}"
