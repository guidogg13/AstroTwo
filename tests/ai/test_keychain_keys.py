"""Test del modulo 31 (``mdfiles/31-ia-chiavi-portachiavi.md`` §12).

Di default con un'**API Security simulata in memoria** al posto delle funzioni che il backend macOS di
``keyring`` chiama: mai il Portachiavi reale, mai una chiave reale. Il Portachiavi reale solo con il
marcatore ``keychain`` (escluso di default, eseguito a mano).
"""

import json
import logging
import subprocess

import pytest
from keyring.backend import KeyringBackend
from keyring.backends.macOS import api

from astrotwo.ai import keychain_keys as kk
from astrotwo.ai.keychain_keys import SERVICE_NAME, KeychainError, KeychainStore, SecretKey

FAKE_KEY = "sk-finta-123-ABCDEFGHIJKLMNOP"


@pytest.fixture
def security(monkeypatch):
    """Elementi del Portachiavi simulati: (servizio, account) → segreto."""
    items: dict[tuple[str, str], str] = {}
    state = {"deny": False, "fail_write": False}

    def find(kc, service, username, not_found_ok=False):
        if state["deny"]:
            raise api.KeychainDenied(-128, "Keychain Access Denied")
        if (service, username) not in items:
            raise api.NotFound(-25300, "Item not found")
        return items[(service, username)]

    def set_password(name, service, username, password):
        if state["deny"]:
            raise api.KeychainDenied(-128, "Keychain Access Denied")
        if state["fail_write"]:
            raise api.Error(-61, "Unknown Error")
        items[(service, username)] = password

    def delete(name, service, username):
        if state["fail_write"]:
            raise api.Error(-61, "Unknown Error")
        if (service, username) not in items:
            raise api.NotFound(-25300, "Item not found")
        del items[(service, username)]

    monkeypatch.setattr(api, "find_generic_password", find)
    monkeypatch.setattr(api, "set_generic_password", set_password)
    monkeypatch.setattr(api, "delete_generic_password", delete)
    return items, state


def test_t1_store_read_delete(security):
    items, _ = security
    store = KeychainStore()
    store.store_key("test-profile", "sk-finta-123")
    assert items == {(SERVICE_NAME, "test-profile"): "sk-finta-123"} and store.has_key("test-profile")
    assert store.get_key("test-profile").reveal() == "sk-finta-123"
    store.store_key("test-profile", "sk-finta-456")  # una chiave per profilo: sostituita
    assert store.get_key("test-profile").reveal() == "sk-finta-456" and len(items) == 1
    assert store.delete_key("test-profile") == "deleted" and not store.has_key("test-profile")
    assert store.delete_key("test-profile") == "nothing_to_delete"
    with pytest.raises(KeychainError) as err:
        store.get_key("test-profile")
    assert err.value.code == "KEY_NOT_FOUND"


def test_t2_trim_and_formats(security):
    items, _ = security
    store = KeychainStore()
    store.store_key("p", "  \n sk-finta-123 \t\n")
    assert items[(SERVICE_NAME, "p")] == "sk-finta-123"
    for bad in ("", "   \n", "sk-\x00finta", "x" * 4097):
        with pytest.raises(KeychainError) as err:
            store.store_key("q", bad)
        assert err.value.code == "KEY_FORMAT_INVALID"
    assert (SERVICE_NAME, "q") not in items
    store.store_key("q", "x" * 4096)  # al limite: ammessa


class PlainFileBackend(KeyringBackend):
    """Backend di prova che salverebbe in chiaro su file: non deve mai essere usato."""

    priority = 100

    def set_password(self, service, username, password):
        raise AssertionError("backend su file usato")

    def get_password(self, service, username):
        raise AssertionError("backend su file usato")

    def delete_password(self, service, username):
        raise AssertionError("backend su file usato")


def test_t3_backend_forced(security, monkeypatch, _temporary_home):
    import keyring

    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", f"{__name__}.PlainFileBackend")
    keyring.set_keyring(PlainFileBackend())  # anche un backend registrato come scelta di keyring è ignorato
    try:
        store = KeychainStore()
        store.store_key("p", FAKE_KEY)
        assert store.get_key("p").reveal() == FAKE_KEY
    finally:
        keyring.core._keyring_backend = None
    assert security[0] == {(SERVICE_NAME, "p"): FAKE_KEY}
    assert list(_temporary_home.rglob("*")) == []  # nessun file creato nella cartella home


def test_t4_no_fallback(security, monkeypatch):
    monkeypatch.setattr(kk.platform, "system", lambda: "Linux")
    with pytest.raises(KeychainError) as err:
        KeychainStore()
    assert err.value.code == "KEYCHAIN_UNAVAILABLE" and "Linux" in err.value.message
    monkeypatch.undo()
    from keyring.backends import macOS

    monkeypatch.delitem(macOS.__dict__, "api")  # API Security non caricabile
    with pytest.raises(KeychainError) as err:
        KeychainStore()
    assert err.value.code == "KEYCHAIN_UNAVAILABLE"


def test_t5_access_denied_and_write_failed(security):
    _, state = security
    store = KeychainStore()
    state["deny"] = True
    for call in (lambda: store.get_key("p"), lambda: store.store_key("p", FAKE_KEY), lambda: store.has_key("p")):
        with pytest.raises(KeychainError) as err:
            call()
        assert err.value.code == "KEYCHAIN_ACCESS_DENIED"
    state["deny"], state["fail_write"] = False, True
    with pytest.raises(KeychainError) as err:
        store.store_key("p", FAKE_KEY)
    assert err.value.code == "KEYCHAIN_WRITE_FAILED"


def test_t6_no_trace(security, caplog, monkeypatch):
    _, state = security
    caplog.set_level(logging.DEBUG)
    store = KeychainStore()
    store.store_key("p", FAKE_KEY)
    secret = store.get_key("p")
    texts = [str(secret), repr(secret), f"{secret}", f"{secret!r}", "%s" % secret, format(secret, ">40")]
    with pytest.raises(TypeError):
        json.dumps({"key": secret})
    import pickle
    with pytest.raises(TypeError):
        pickle.dumps(secret)
    for flag in ("deny", "fail_write"):
        state[flag] = True
        for call in (lambda: store.store_key("p", FAKE_KEY), lambda: store.get_key("p"),
                     lambda: store.delete_key("p")):
            try:
                call()
            except KeychainError as exc:
                texts += [str(exc), exc.message, repr(exc)]
        state[flag] = False
    # Un errore di sistema che riportasse la chiave nel testo: la chiave è tolta dal messaggio.
    def leaking(name, service, username, password):
        raise api.Error(-61, f"errore con {password}")
    monkeypatch.setattr(api, "set_generic_password", leaking)
    with pytest.raises(KeychainError) as err:
        store.store_key("p", FAKE_KEY)
    texts.append(str(err.value))
    texts += [r.getMessage() for r in caplog.records]
    joined = "\n".join(texts)
    for size in range(4, len(FAKE_KEY) + 1):
        for start in range(len(FAKE_KEY) - size + 1):
            assert FAKE_KEY[start:start + size] not in joined, FAKE_KEY[start:start + size]


def test_t7_environment_ignored(security, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    with pytest.raises(KeychainError) as err:
        KeychainStore().get_key("anthropic")
    assert err.value.code == "KEY_NOT_FOUND"


def test_secret_key_is_opaque():
    secret = SecretKey(FAKE_KEY)
    assert secret.reveal() == FAKE_KEY and str(secret) == "••••"
    with pytest.raises(AttributeError):
        secret._value = "altro"
    with pytest.raises(TypeError):
        hash(secret)


@pytest.mark.keychain
def test_t8_real_keychain():
    """Portachiavi reale (a mano): servizio di test, chiave finta, elemento rimosso alla fine."""
    service = SERVICE_NAME + ".test"
    store = KeychainStore(service=service)
    try:
        store.store_key("astrotwo-test-profile", "sk-finta-portachiavi-reale")
        assert store.has_key("astrotwo-test-profile")
        assert store.get_key("astrotwo-test-profile").reveal() == "sk-finta-portachiavi-reale"
        found = subprocess.run(["security", "find-generic-password", "-s", service, "-a", "astrotwo-test-profile"],
                               capture_output=True, text=True)
        assert found.returncode == 0 and "login.keychain" in found.stdout  # Portachiavi di login, non iCloud
    finally:
        store.delete_key("astrotwo-test-profile")
    assert not store.has_key("astrotwo-test-profile")
