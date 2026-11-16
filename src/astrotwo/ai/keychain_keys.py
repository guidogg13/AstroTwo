# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Chiavi API dei provider IA solo nell'archivio sicuro del sistema (livello 3).

Specifica: ``mdfiles/31-ia-chiavi-portachiavi.md`` (stato ``approvato``); Windows e Linux: ``65`` (D65-1, sprint W2).

Regola d'oro n. 5: una chiave non finisce mai in un file, in un log, nella cronologia, nella sessione o nel
repository. Il modulo usa **un solo backend di ``keyring`` per sistema**, creato direttamente: su macOS il Portachiavi
(``keyring.backends.macOS.Keyring``, invariato), su Windows la Gestione credenziali
(``keyring.backends.Windows.WinVaultKeyring``), su Linux il Secret Service (``keyring.backends.SecretService.Keyring``:
GNOME Keyring, KWallet, KeePassXC). La scelta automatica di ``keyring``, ``PYTHON_KEYRING_BACKEND``,
``keyringrc.cfg`` e i backend di altri pacchetti (es. ``keyrings.alt``, in chiaro su file) non si usano mai, e non
c'è alcun ripiego: senza l'archivio del sistema, ``KEYCHAIN_UNAVAILABLE``.
"""

from __future__ import annotations

import platform
from collections.abc import Mapping

__all__ = [
    "SERVICE_NAME",
    "MAX_KEY_LENGTH",
    "KeychainError",
    "SecretKey",
    "KeychainStore",
    "SYSTEM_STORES",
    "store_name",
]

#: Nome del servizio degli elementi del Portachiavi (decisione del proprietario del 2026-10-16).
SERVICE_NAME = "dev.pages.astrotwo.ai"
#: Lunghezza massima di una chiave (§3.3).
MAX_KEY_LENGTH = 4096
_MASK = "••••"


class KeychainError(Exception):
    """Errore del modulo 31 con codice di §10 e testo **senza** la chiave."""

    def __init__(self, code: str, message: str, *, params: Mapping[str, object] | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.params = dict(params or {})  # valori JSON del messaggio (D40-3); mai la chiave


def _operation(kind: str, profile_id: str) -> dict:
    """Messaggio annidato (D40-7) che dice quale operazione sul profilo è fallita: ``read``, ``write``, ``delete``."""
    text = {"read": "lettura", "write": "scrittura", "delete": "cancellazione"}[kind]
    return {"code": "KEYCHAIN_OPERATION", "params": {"reason": kind, "profile_id": profile_id},
            "text": f"{text} della chiave del profilo {profile_id!r}"}


class SecretKey:
    """Contenitore del segreto: ogni forma di testo è ``"••••"``; il valore solo con ``reveal()`` (§3.3)."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        object.__setattr__(self, "_value", value)

    def reveal(self) -> str:
        return self._value

    def __str__(self) -> str:
        return _MASK

    def __repr__(self) -> str:
        return f"SecretKey({_MASK})"

    def __format__(self, spec: str) -> str:
        return _MASK

    def __setattr__(self, name, value):
        raise AttributeError("SecretKey non si modifica")

    def __reduce__(self):
        raise TypeError("SecretKey non si serializza")

    def __getstate__(self):
        raise TypeError("SecretKey non si serializza")

    def __eq__(self, other):
        return NotImplemented

    __hash__ = None


def _clean_text(text: str, secret: str | None) -> str:
    """Testo d'errore del sistema senza il segreto (nemmeno in parte: ogni sottostringa di 4 o più caratteri)."""
    if not secret:
        return text
    for size in range(len(secret), 3, -1):
        for start in range(0, len(secret) - size + 1):
            piece = secret[start:start + size]
            if piece in text:
                text = text.replace(piece, _MASK)
    return text


def _profile(profile_id: object) -> str:
    if not isinstance(profile_id, str) or not profile_id or any(ord(c) < 32 or ord(c) == 127 for c in profile_id):
        raise ValueError("profile_id: identificativo del profilo del 30, testo senza caratteri di controllo")
    return profile_id


def _macos_backend():
    """Il solo backend macOS di ``keyring``, creato direttamente (nessuna scelta automatica, nessun ripiego)."""
    try:
        from keyring.backends import macOS
    except Exception as exc:  # noqa: BLE001 - libreria Security non caricabile
        raise KeychainError("KEYCHAIN_UNAVAILABLE", f"backend macOS di keyring non caricabile "
                            f"({type(exc).__name__})",
                            params={"reason": "backend_not_loadable", "error_type": type(exc).__name__}) from exc
    try:
        macOS.Keyring.priority  # noqa: B018 - solleva se l'API Security non è disponibile
    except Exception as exc:  # noqa: BLE001
        raise KeychainError("KEYCHAIN_UNAVAILABLE", f"Portachiavi di macOS non disponibile: {exc}",
                            params={"reason": "api_unavailable", "detail": str(exc)}) from exc
    backend = macOS.Keyring()
    backend.keychain = None  # KEYCHAIN_PATH dell'ambiente ignorato: solo il Portachiavi di login
    return backend


#: Archivio sicuro di ogni sistema (D65-1): sistema di ``platform.system()`` → (modulo di ``keyring.backends``,
#: classe, nome mostrato). Nessun altro backend, mai.
SYSTEM_STORES = {
    "Windows": ("Windows", "WinVaultKeyring", "Windows Credential Manager"),
    "Linux": ("SecretService", "Keyring", "Secret Service"),
}


def store_name(system: str | None = None) -> str:
    """Nome dell'archivio delle chiavi del sistema, per i testi (``macOS Keychain`` su macOS)."""
    system = platform.system() if system is None else system
    return "macOS Keychain" if system == "Darwin" else SYSTEM_STORES.get(system, (None, None, "—"))[2]


def _other_backend(system: str):
    """Backend forzato di Windows o Linux (D65-1), creato direttamente; ``KEYCHAIN_UNAVAILABLE`` se non c'è."""
    if system not in SYSTEM_STORES:
        raise KeychainError("KEYCHAIN_UNAVAILABLE", f"sistema {system!r}: nessun archivio sicuro delle chiavi "
                            "previsto; l'assistente non è disponibile, il resto dell'app funziona",
                            params={"reason": "unsupported_system", "system": system})
    module_name, class_name, name = SYSTEM_STORES[system]
    try:
        import importlib

        backend_class = getattr(importlib.import_module(f"keyring.backends.{module_name}"), class_name)
    except Exception as exc:  # noqa: BLE001 - backend non caricabile
        raise KeychainError("KEYCHAIN_UNAVAILABLE", f"backend {name} di keyring non caricabile "
                            f"({type(exc).__name__})",
                            params={"reason": "store_not_loadable", "store": name,
                                    "error_type": type(exc).__name__}) from exc
    try:
        backend_class.priority  # noqa: B018 - solleva se l'archivio non c'è (pywin32-ctypes, D-Bus, servizio)
    except Exception as exc:  # noqa: BLE001
        raise KeychainError("KEYCHAIN_UNAVAILABLE", f"{name} non disponibile: {exc}",
                            params={"reason": "store_unavailable", "store": name, "detail": str(exc)}) from exc
    return backend_class()


def _system_backend():
    """Il backend dell'archivio del sistema: macOS invariato, Windows e Linux con D65-1."""
    system = platform.system()
    return _macos_backend() if system == "Darwin" else _other_backend(system)


class KeychainStore:
    """Accesso all'archivio del sistema con il backend forzato (§3.2, D65-1); ``KEYCHAIN_UNAVAILABLE`` se non c'è."""

    def __init__(self, *, service: str = SERVICE_NAME) -> None:
        if not isinstance(service, str) or not service:
            raise ValueError("service: nome del servizio del Portachiavi")
        self.service = service
        self._backend = _system_backend()

    def _failure(self, exc: BaseException, operation: str, profile_id: str, secret: str | None = None) -> KeychainError:
        """Errore del Portachiavi per l'operazione ``operation`` (``read``, ``write``, ``delete``) sul profilo."""
        from keyring.errors import KeyringLocked, PasswordDeleteError, PasswordSetError

        text = _clean_text(str(exc), secret)
        what = {"read": f"lettura della chiave del profilo {profile_id!r}",
                "write": f"scrittura della chiave del profilo {profile_id!r}",
                "delete": f"cancellazione della chiave del profilo {profile_id!r}"}[operation]
        nested = {"read": _operation("read", profile_id), "write": _operation("write", profile_id),
                  "delete": _operation("delete", profile_id)}[operation]
        params = {"operation": nested, "detail": text}
        if isinstance(exc, KeyringLocked):
            return KeychainError("KEYCHAIN_ACCESS_DENIED", f"{what}: accesso al Portachiavi negato ({text})",
                                 params=params)
        if isinstance(exc, (PasswordSetError, PasswordDeleteError)):
            return KeychainError("KEYCHAIN_WRITE_FAILED", f"{what}: {text}", params=params)
        return KeychainError("KEYCHAIN_UNAVAILABLE", f"{what}: Portachiavi non raggiungibile ({text})",
                             params={"reason": "unreachable", **params})

    def _read(self, profile_id: str) -> str | None:
        from keyring.errors import KeyringError

        try:
            return self._backend.get_password(self.service, profile_id)
        except KeyringError as exc:
            raise self._failure(exc, "read", profile_id) from None

    def store_key(self, profile_id: str, key: str) -> None:
        """Salva (o sostituisce) la chiave del profilo; spazi e a capo ai bordi tolti (scelta minore 3)."""
        from keyring.errors import KeyringError

        profile_id = _profile(profile_id)
        if not isinstance(key, str):
            raise KeychainError("KEY_FORMAT_INVALID", "la chiave è un testo", params={"reason": "not_text"})
        cleaned = key.strip()
        if not cleaned:
            raise KeychainError("KEY_FORMAT_INVALID", "chiave vuota: nulla scritto", params={"reason": "empty"})
        if len(cleaned) > MAX_KEY_LENGTH:
            raise KeychainError("KEY_FORMAT_INVALID", f"chiave di {len(cleaned)} caratteri, oltre {MAX_KEY_LENGTH}: "
                                "nulla scritto",
                                params={"reason": "too_long", "length": len(cleaned), "maximum": MAX_KEY_LENGTH})
        if any(ord(c) < 32 or ord(c) == 127 for c in cleaned):
            raise KeychainError("KEY_FORMAT_INVALID", "la chiave contiene caratteri di controllo: nulla scritto",
                                params={"reason": "control_characters"})
        try:
            self._backend.set_password(self.service, profile_id, cleaned)
        except KeyringError as exc:
            raise self._failure(exc, "write", profile_id, cleaned) from None

    def has_key(self, profile_id: str) -> bool:
        """Sì/no; il segreto letto si scarta subito (la libreria non offre una lettura dell'esistenza)."""
        return self._read(_profile(profile_id)) is not None

    def get_key(self, profile_id: str) -> SecretKey:
        """La chiave al momento della chiamata (nessuna copia tenuta dal modulo)."""
        profile_id = _profile(profile_id)
        value = self._read(profile_id)
        if value is None:
            raise KeychainError("KEY_NOT_FOUND", f"nessuna chiave nel Portachiavi per il profilo {profile_id!r}",
                                params={"profile_id": profile_id})
        return SecretKey(value)

    def delete_key(self, profile_id: str) -> str:
        """Toglie l'elemento: ``"deleted"``, oppure ``"nothing_to_delete"`` se non c'era (nessun errore)."""
        from keyring.errors import KeyringError

        profile_id = _profile(profile_id)
        if self._read(profile_id) is None:
            return "nothing_to_delete"
        try:
            self._backend.delete_password(self.service, profile_id)
        except KeyringError as exc:
            raise self._failure(exc, "delete", profile_id) from None
        return "deleted"
