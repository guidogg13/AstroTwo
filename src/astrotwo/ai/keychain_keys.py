# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Chiavi API dei provider IA solo nel Portachiavi di macOS (livello 3).

Specifica: ``mdfiles/31-ia-chiavi-portachiavi.md`` (stato ``approvato``).

Regola d'oro n. 5: una chiave non finisce mai in un file, in un log, nella cronologia, nella sessione o nel
repository. Il modulo usa **solo** il backend macOS di ``keyring`` (``keyring.backends.macOS.Keyring``), creato
direttamente: la scelta automatica di ``keyring``, ``PYTHON_KEYRING_BACKEND``, ``keyringrc.cfg`` e i backend di
altri pacchetti (es. ``keyrings.alt``, in chiaro su file) non si usano mai, e non c'è alcun ripiego.
"""

from __future__ import annotations

import platform

__all__ = [
    "SERVICE_NAME",
    "MAX_KEY_LENGTH",
    "KeychainError",
    "SecretKey",
    "KeychainStore",
]

#: Nome del servizio degli elementi del Portachiavi (decisione del proprietario del 2026-10-16).
SERVICE_NAME = "dev.pages.astrotwo.ai"
#: Lunghezza massima di una chiave (§3.3).
MAX_KEY_LENGTH = 4096
_MASK = "••••"


class KeychainError(Exception):
    """Errore del modulo 31 con codice di §10 e testo **senza** la chiave."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


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
    if platform.system() != "Darwin":
        raise KeychainError("KEYCHAIN_UNAVAILABLE", f"sistema {platform.system()!r}: il Portachiavi di macOS non "
                            "c'è; l'assistente non è disponibile, il resto dell'app funziona")
    try:
        from keyring.backends import macOS
    except Exception as exc:  # noqa: BLE001 - libreria Security non caricabile
        raise KeychainError("KEYCHAIN_UNAVAILABLE", f"backend macOS di keyring non caricabile "
                            f"({type(exc).__name__})") from exc
    try:
        macOS.Keyring.priority  # noqa: B018 - solleva se l'API Security non è disponibile
    except Exception as exc:  # noqa: BLE001
        raise KeychainError("KEYCHAIN_UNAVAILABLE", f"Portachiavi di macOS non disponibile: {exc}") from exc
    backend = macOS.Keyring()
    backend.keychain = None  # KEYCHAIN_PATH dell'ambiente ignorato: solo il Portachiavi di login
    return backend


class KeychainStore:
    """Accesso al Portachiavi con il backend macOS forzato (§3.2); ``KEYCHAIN_UNAVAILABLE`` se non c'è."""

    def __init__(self, *, service: str = SERVICE_NAME) -> None:
        if not isinstance(service, str) or not service:
            raise ValueError("service: nome del servizio del Portachiavi")
        self.service = service
        self._backend = _macos_backend()

    def _failure(self, exc: BaseException, operation: str, secret: str | None = None) -> KeychainError:
        from keyring.errors import KeyringLocked, PasswordDeleteError, PasswordSetError

        text = _clean_text(str(exc), secret)
        if isinstance(exc, KeyringLocked):
            return KeychainError("KEYCHAIN_ACCESS_DENIED", f"{operation}: accesso al Portachiavi negato ({text})")
        if isinstance(exc, (PasswordSetError, PasswordDeleteError)):
            return KeychainError("KEYCHAIN_WRITE_FAILED", f"{operation}: {text}")
        return KeychainError("KEYCHAIN_UNAVAILABLE", f"{operation}: Portachiavi non raggiungibile ({text})")

    def _read(self, profile_id: str) -> str | None:
        from keyring.errors import KeyringError

        try:
            return self._backend.get_password(self.service, profile_id)
        except KeyringError as exc:
            raise self._failure(exc, f"lettura della chiave del profilo {profile_id!r}") from None

    def store_key(self, profile_id: str, key: str) -> None:
        """Salva (o sostituisce) la chiave del profilo; spazi e a capo ai bordi tolti (scelta minore 3)."""
        from keyring.errors import KeyringError

        profile_id = _profile(profile_id)
        if not isinstance(key, str):
            raise KeychainError("KEY_FORMAT_INVALID", "la chiave è un testo")
        cleaned = key.strip()
        if not cleaned:
            raise KeychainError("KEY_FORMAT_INVALID", "chiave vuota: nulla scritto")
        if len(cleaned) > MAX_KEY_LENGTH:
            raise KeychainError("KEY_FORMAT_INVALID", f"chiave di {len(cleaned)} caratteri, oltre {MAX_KEY_LENGTH}: "
                                "nulla scritto")
        if any(ord(c) < 32 or ord(c) == 127 for c in cleaned):
            raise KeychainError("KEY_FORMAT_INVALID", "la chiave contiene caratteri di controllo: nulla scritto")
        try:
            self._backend.set_password(self.service, profile_id, cleaned)
        except KeyringError as exc:
            raise self._failure(exc, f"scrittura della chiave del profilo {profile_id!r}", cleaned) from None

    def has_key(self, profile_id: str) -> bool:
        """Sì/no; il segreto letto si scarta subito (la libreria non offre una lettura dell'esistenza)."""
        return self._read(_profile(profile_id)) is not None

    def get_key(self, profile_id: str) -> SecretKey:
        """La chiave al momento della chiamata (nessuna copia tenuta dal modulo)."""
        profile_id = _profile(profile_id)
        value = self._read(profile_id)
        if value is None:
            raise KeychainError("KEY_NOT_FOUND", f"nessuna chiave nel Portachiavi per il profilo {profile_id!r}")
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
            raise self._failure(exc, f"cancellazione della chiave del profilo {profile_id!r}") from None
        return "deleted"
