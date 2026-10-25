# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 04 con codice + ``params`` (D40-3; ``40`` §3.7.1, T18–T19; ``04`` §10.1).

Provoca ogni errore e avviso della cache; ogni istanza è controllata contro il catalogo alla creazione
(``tests/conftest.py``) e qui si verifica la copertura di tutte le coppie (codice, ragione) e il testo invariato.
"""

from __future__ import annotations

import os
import sqlite3
import stat
from datetime import UTC, datetime, timedelta

import pytest

from astrotwo import messages_catalog as mc
from astrotwo.core import cache as cache_module
from astrotwo.core.cache import CacheError, CacheWarning, SharedCache
from tests.message_helpers import catalog_combinations, check_error, check_message

WHEN = datetime(2026, 10, 9, 12, 30, 15, tzinfo=UTC)
ORIGIN = "https://example.org/servizio?id=1"
COLUMNS = {"main_id": "TEXT", "ra_deg": "REAL"}
OWN_CODES = ("CACHE_UNAVAILABLE", "CACHE_FULL", "CACHE_PROVENANCE_MISSING", "CACHE_FORBIDDEN")


def test_every_error_and_warning_has_code_params_and_catalog_entry(tmp_path, monkeypatch):
    seen: set[tuple[str, str | None]] = set()

    def error(func, *args, **kwargs) -> CacheError:
        with pytest.raises(CacheError) as info:
            func(*args, **kwargs)
        seen.add(check_error(info.value))
        return info.value

    def warning(record) -> CacheWarning:
        message = record[0].message
        assert isinstance(message, CacheWarning)
        seen.add(check_message(message.code, message.params, message.message))
        return message

    with SharedCache(tmp_path / "a", limit_bytes=1000) as cache:
        error(cache.put, "11", "k", b"x", "", WHEN)  # origin
        error(cache.put, "11", "k", b"x", ORIGIN, "ieri")  # retrieved_at
        error(cache.put, "11", "k", b"x", ORIGIN, datetime(2026, 1, 1))  # no_timezone
        big = error(cache.put, "11", "grande", bytes(1001), ORIGIN, WHEN)
        assert big.params == {"key": "grande", "size": 1001, "limit": 1000}
        assert mc.message_text(big.code, big.params, "it") == (
            "La voce grande (1001 byte) supera da sola il limite di 1000 byte.")
        cache.put("10", "chiave-del-10", b"x", ORIGIN, WHEN)
        other = error(cache.get, "13", "chiave-del-10")
        assert other.params == {"reason": "other_module", "key": "chiave-del-10", "owner": "10", "module": "13"}
        table = cache.table("10", "nomi", COLUMNS)
        table.put("riga", {"main_id": "M31", "ra_deg": 10.68}, ORIGIN, WHEN)
        assert error(cache.get, "10", "riga").params["reason"] == "file_is_row"
        cache.table("10", "altra", COLUMNS).put("altra-riga", {"main_id": "M32", "ra_deg": 10.67}, ORIGIN, WHEN)
        assert error(table.get, "altra-riga").params["reason"] == "wrong_table"
    # database corrotto: ricreato
    with SharedCache(tmp_path / "b") as cache:
        cache.put("11", "k", b"dato", ORIGIN, WHEN)
    (tmp_path / "b" / "cache.sqlite").write_bytes(os.urandom(8192))
    with pytest.warns(CacheWarning) as record:
        SharedCache(tmp_path / "b").close()
    assert warning(record).params["reason"] == "corrupt"
    # cartella non scrivibile, voce e riga non salvate con la cache spenta
    locked = tmp_path / "bloccata"
    locked.mkdir()
    locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.warns(CacheWarning) as record:
            off = SharedCache(locked / "AstroTwo")
        unwritable = warning(record)
        assert unwritable.params["reason"] == "folder_unwritable" and unwritable.params["folder"].endswith("AstroTwo")
        with pytest.warns(CacheWarning) as record:
            off.put("11", "k", b"dato", ORIGIN, WHEN)
        assert warning(record).params == {"reason": "entry_not_saved"}
        with pytest.warns(CacheWarning) as record:
            off.table("10", "t", COLUMNS).put("k", {"main_id": "x", "ra_deg": 1.0}, ORIGIN, WHEN)
        assert warning(record).params == {"reason": "row_not_saved"}
    finally:
        locked.chmod(stat.S_IRWXU)
    # database non utilizzabile (errore di SQLite che non è una corruzione) e ricreazione non riuscita
    def busy(self):
        raise sqlite3.DatabaseError("database is locked")

    with monkeypatch.context() as patch:
        patch.setattr(SharedCache, "_connect", busy)
        with pytest.warns(CacheWarning) as record:
            SharedCache(tmp_path / "c").close()
        assert warning(record).params == {"reason": "unusable", "detail": "database is locked"}

    def corrupt(self):
        raise sqlite3.DatabaseError("file is not a database")

    with monkeypatch.context() as patch:
        patch.setattr(SharedCache, "_connect", corrupt)
        patch.setattr(cache_module.shutil, "rmtree", lambda *a, **k: (_ for _ in ()).throw(OSError("disco pieno")))
        with pytest.warns(CacheWarning) as record:
            SharedCache(tmp_path / "d").close()
        assert [r.message.params["reason"] for r in record if isinstance(r.message, CacheWarning)] == [
            "corrupt", "recreate_failed"]
        seen.add(("CACHE_UNAVAILABLE", "recreate_failed"))
    required = {(c, r) for c, r in catalog_combinations(OWN_CODES) if r is not None or not mc.CATALOG[c].variants}
    assert required <= seen, sorted(required - seen, key=str)
    assert timedelta and WHEN
