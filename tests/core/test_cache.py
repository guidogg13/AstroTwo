"""Test di accettazione della cache comune (``mdfiles/04-cache.md`` §12).

Tutti i test usano una cartella temporanea (``tmp_path``) o, per T8, una
cartella home simulata: mai la vera ``~/Library/Caches/AstroTwo/``.
"""

from __future__ import annotations

import logging
import os
import stat
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from astrotwo.core import cache as cache_module
from astrotwo.core.cache import (
    DEFAULT_LIMIT_BYTES,
    NETWORK_TIMEOUTS,
    CacheError,
    CacheWarning,
    SharedCache,
    default_cache_root,
)

WHEN = datetime(2026, 10, 9, 12, 30, 15, 123456, tzinfo=UTC)
ORIGIN = "https://example.org/servizio?id=1"
COLUMNS = {"main_id": "TEXT", "ra_deg": "REAL", "dec_deg": "REAL"}


def expect_error(code, func, *args, **kwargs):
    with pytest.raises(CacheError) as info:
        func(*args, **kwargs)
    assert info.value.code == code, info.value
    return info.value


def data_bytes_on_disk(root: Path) -> int:
    return sum(p.stat().st_size for p in (root / "files").rglob("*") if p.is_file())


def test_constants_from_decisions():
    assert DEFAULT_LIMIT_BYTES == 5 * 10**9  # CA2: 5 GB decimali
    assert (NETWORK_TIMEOUTS.connect, NETWORK_TIMEOUTS.read) == (10.0, 60.0)  # CA1
    assert NETWORK_TIMEOUTS.as_requests() == (10.0, 60.0)


# --- T1 ---------------------------------------------------------------------


def test_t1_provenance_roundtrip_file_and_row(tmp_path):
    with SharedCache(tmp_path) as cache:
        payload = bytes(range(256)) * 10
        cache.put("11", "img:1", payload, ORIGIN, WHEN)
        value = cache.get("11", "img:1")
        assert value.data == payload and value.origin == ORIGIN
        assert value.retrieved_at == WHEN and value.from_cache is True
        table = cache.table("10", "name_resolution", COLUMNS)
        row = {"main_id": "M  31", "ra_deg": 10.684708333333333, "dec_deg": 41.268750000000004}
        other_tz = WHEN.astimezone(timezone(timedelta(hours=2)))  # stesso istante, altro fuso
        table.put("simbad:M31", row, ORIGIN, other_tz)
        got = table.get("simbad:M31")
        assert got.data == row and got.origin == ORIGIN and got.retrieved_at == WHEN
    # Persistenza: riaprendo, stessi dati e stessa provenienza.
    with SharedCache(tmp_path) as cache:
        assert cache.get("11", "img:1").data == payload
        assert cache.table("10", "name_resolution", COLUMNS).get("simbad:M31").data == row
        assert cache.get("11", "assente") is None


# --- T2 ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "origin,when",
    [(None, WHEN), ("", WHEN), ("   ", WHEN), (ORIGIN, None), (ORIGIN, datetime(2026, 10, 9, 12, 0)), (ORIGIN, "2026-10-09")],
)
def test_t2_provenance_mandatory(tmp_path, origin, when):
    with SharedCache(tmp_path) as cache:
        expect_error("CACHE_PROVENANCE_MISSING", cache.put, "11", "k", b"x", origin, when)
        expect_error(
            "CACHE_PROVENANCE_MISSING", cache.table("10", "t", COLUMNS).put, "k2",
            {"main_id": "a", "ra_deg": 1.0, "dec_deg": 2.0}, origin, when,
        )
        assert cache.usage().total_bytes == 0 and cache.get("11", "k") is None


# --- T3 ---------------------------------------------------------------------


def test_t3_lru_limit(tmp_path, caplog):
    limit = 10_000
    with SharedCache(tmp_path, limit_bytes=limit) as cache:
        for name in "abc":
            cache.put("12", name, bytes(3000), ORIGIN, WHEN)
        assert cache.get("12", "a") is not None  # "a" diventa la più usata di recente
        with caplog.at_level(logging.INFO, logger="astrotwo.cache"):
            cache.put("12", "d", bytes(3000), ORIGIN, WHEN)
        # Eliminata la meno usata di recente ("b"), non "a".
        assert cache.get("12", "b") is None
        assert all(cache.get("12", k) is not None for k in "acd")
        assert any("eliminazione LRU" in r.message and "'b'" in r.message for r in caplog.records)
        usage = cache.usage()
        assert usage.total_bytes == 9000 <= limit and usage.by_module == {"12": 9000}
        assert data_bytes_on_disk(tmp_path) == 9000
        # Anche le righe contano nel totale e possono far uscire i file.
        table = cache.table("13", "query", {"payload": "TEXT"})
        table.put("q1", {"payload": "x" * 2500}, ORIGIN, WHEN)
        usage = cache.usage()
        assert usage.total_bytes <= limit and usage.by_module["13"] == 2500
        assert cache.get("12", "a") is None  # ora la meno usata era "a"
        assert data_bytes_on_disk(tmp_path) + 2500 == usage.total_bytes


# --- T4 ---------------------------------------------------------------------


def test_t4_entry_larger_than_limit(tmp_path):
    with SharedCache(tmp_path, limit_bytes=1000) as cache:
        cache.put("11", "small", bytes(500), ORIGIN, WHEN)
        expect_error("CACHE_FULL", cache.put, "11", "big", bytes(1001), ORIGIN, WHEN)
        expect_error("CACHE_FULL", cache.table("13", "t", {"v": "BLOB"}).put, "row", {"v": bytes(1001)}, ORIGIN, WHEN)
        assert cache.get("11", "big") is None
        assert cache.get("11", "small") is not None  # nessuna eliminazione inutile
        assert data_bytes_on_disk(tmp_path) == 500


# --- T5 ---------------------------------------------------------------------


def test_t5_module_separation(tmp_path):
    with SharedCache(tmp_path) as cache:
        cache.put("10", "chiave-del-10", b"dato", ORIGIN, WHEN)
        expect_error("CACHE_FORBIDDEN", cache.get, "13", "chiave-del-10")
        expect_error("CACHE_FORBIDDEN", cache.put, "13", "chiave-del-10", b"altro", ORIGIN, WHEN)
        rows = cache.table("10", "nomi", COLUMNS)
        rows.put("riga-del-10", {"main_id": "a", "ra_deg": 1.0, "dec_deg": 2.0}, ORIGIN, WHEN)
        expect_error("CACHE_FORBIDDEN", cache.table("13", "nomi", COLUMNS).get, "riga-del-10")
        assert cache.get("10", "chiave-del-10").data == b"dato"


# --- T6 ---------------------------------------------------------------------


def test_t6_corrupted_database_is_recreated(tmp_path):
    with SharedCache(tmp_path) as cache:
        cache.put("11", "k", b"dato", ORIGIN, WHEN)
    (tmp_path / "cache.sqlite").write_bytes(os.urandom(8192))
    with pytest.warns(CacheWarning) as record:
        cache = SharedCache(tmp_path)
    assert record[0].message.code == "CACHE_UNAVAILABLE"
    with cache:
        assert cache.available
        assert cache.get("11", "k") is None  # dato senza registro: non servibile
        assert data_bytes_on_disk(tmp_path) == 0
        cache.put("11", "k", b"nuovo", ORIGIN, WHEN)
        assert cache.get("11", "k").data == b"nuovo"


def test_t6_unwritable_folder_is_ignored_with_warning(tmp_path):
    locked = tmp_path / "bloccata"
    locked.mkdir()
    locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.warns(CacheWarning) as record:
            cache = SharedCache(locked / "AstroTwo")
        assert record[0].message.code == "CACHE_UNAVAILABLE" and not cache.available
        with pytest.warns(CacheWarning):
            cache.put("11", "k", b"dato", ORIGIN, WHEN)  # ignorata, con avviso
        assert cache.get("11", "k") is None
    finally:
        locked.chmod(stat.S_IRWXU)


# --- T7 ---------------------------------------------------------------------


def test_t7_interrupted_file_write(tmp_path, monkeypatch):
    with SharedCache(tmp_path) as cache:
        cache.put("11", "k", b"versione 1", ORIGIN, WHEN)

        def broken_replace(src, dst):
            raise OSError("disco pieno simulato a metà scrittura")

        monkeypatch.setattr(cache_module.os, "replace", broken_replace)
        with pytest.raises(OSError):
            cache.put("11", "k", b"versione 2 mai completata", ORIGIN, WHEN)
        with pytest.raises(OSError):
            cache.put("11", "nuova", b"mai completata", ORIGIN, WHEN)
        monkeypatch.undo()
        assert cache.get("11", "k").data == b"versione 1"  # la voce precedente resta intera
        assert cache.get("11", "nuova") is None
        assert not [p for p in (tmp_path / "files").rglob(".tmp-*")]
        assert cache.usage().total_bytes == len(b"versione 1")


def test_t7_interrupted_row_write(tmp_path, monkeypatch):
    with SharedCache(tmp_path) as cache:
        table = cache.table("13", "query", {"payload": "TEXT"})

        def broken_counter():
            raise RuntimeError("arresto simulato dentro la transazione")

        monkeypatch.setattr(cache, "_next_use", broken_counter)
        with pytest.raises(RuntimeError):
            table.put("q", {"payload": "riga"}, ORIGIN, WHEN)
        monkeypatch.undo()
        assert table.get("q") is None
        rows = cache._db.execute('SELECT COUNT(*) FROM "m13_query"').fetchone()[0]
        assert rows == 0


# --- T8 ---------------------------------------------------------------------


def test_t8_default_location(_temporary_home):
    expected = Path(_temporary_home) / "Library" / "Caches" / "AstroTwo"
    assert default_cache_root() == expected
    with SharedCache() as cache:
        assert cache.root == expected and (expected / "cache.sqlite").exists()
    assert str(expected).startswith(str(_temporary_home))  # mai la home vera


# --- Altri comportamenti di §7 ----------------------------------------------


def test_usage_and_clear(tmp_path):
    with SharedCache(tmp_path) as cache:
        cache.put("11", "a", bytes(100), ORIGIN, WHEN)
        cache.put("12", "b", bytes(200), ORIGIN, WHEN)
        cache.table("10", "nomi", {"v": "TEXT"}).put("c", {"v": "abc"}, ORIGIN, WHEN)
        assert cache.usage().by_module == {"10": 3, "11": 100, "12": 200}
        cache.clear("12")
        assert cache.get("12", "b") is None and cache.get("11", "a") is not None
        assert cache.usage().by_module == {"10": 3, "11": 100}
        cache.clear()
        assert cache.usage().total_bytes == 0 and data_bytes_on_disk(tmp_path) == 0


def test_invalid_arguments(tmp_path):
    with SharedCache(tmp_path) as cache:
        with pytest.raises(ValueError):
            cache.put("modulo", "k", b"x", ORIGIN, WHEN)
        with pytest.raises(TypeError):
            cache.put("11", "k", "testo non byte", ORIGIN, WHEN)
        with pytest.raises(ValueError):
            cache.table("10", "nomi", {"v": "VARCHAR"})
        with pytest.raises(ValueError):
            cache.table("10", "nomi; DROP", {"v": "TEXT"})
    with pytest.raises(ValueError):
        SharedCache(tmp_path, limit_bytes=0)


# --- D04 (decisione del proprietario del 2026-10-16): più thread, più processi, orfani -------------

import subprocess  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402

LOAD_LIMIT = 2_000_000


def _load(root, per_instance: bool, seed: int, operations: int, errors: list) -> int:
    """Letture e scritture concorrenti di file e righe; restituisce le operazioni fatte."""
    shared = None if per_instance else SharedCache(root, LOAD_LIMIT)
    done = 0
    for i in range(operations):
        try:
            c = SharedCache(root, LOAD_LIMIT) if per_instance else shared
            key = f"k{(seed * 7 + i) % 40}"
            if i % 3:
                c.put("12", key, bytes([seed % 256]) * (10_000 + 97 * i), origin=ORIGIN, retrieved_at=WHEN)
            value = c.get("12", key)
            if value is not None and len(set(value.data)) != 1:
                raise AssertionError(f"voce parziale o mista: {key}")
            rows = c.table("13", "rows", {"v": "TEXT"})
            if i % 2:
                rows.put(f"r{key}", {"v": str(seed) * 500}, origin=ORIGIN, retrieved_at=WHEN)
            row = rows.get(f"r{key}")
            if row is not None and len(set(row.data["v"])) != 1:
                raise AssertionError(f"riga parziale o mista: r{key}")
            if c.usage().total_bytes > LOAD_LIMIT:
                raise AssertionError("limite superato")
            if per_instance:
                c.close()
            done += 1
        except Exception as exc:  # raccolti: il test vuole 0 errori
            errors.append(f"{type(exc).__name__}: {exc}")
    if shared is not None:
        shared.close()
    return done


def _check_consistent(root):
    with SharedCache(root, LOAD_LIMIT) as c:
        rows = c._db.execute("SELECT kind, location FROM registry").fetchall()
        missing = [loc for kind, loc in rows if kind == "file" and not (root / "files" / loc).exists()]
        assert missing == []
        assert c.usage().total_bytes <= LOAD_LIMIT


@pytest.mark.parametrize("per_instance", [False, True], ids=["istanza_per_thread", "istanza_per_operazione"])
def test_t9_many_threads(tmp_path, per_instance):
    """T9 del 04 = T17 del 05: 8 thread, ≥ 1200 operazioni, 0 errori, nessuna voce parziale, limite."""
    root = tmp_path / "cache"
    errors, counts = [], []
    threads = [threading.Thread(target=lambda n=n: counts.append(_load(root, per_instance, n, 150, errors)))
               for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert sum(counts) >= 1200
    _check_consistent(root)


_PROCESS_LOAD = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[3])
import test_cache as t
errors = []
done = t._load(Path(sys.argv[1]), True, int(sys.argv[2]), 400, errors)
print(done, len(errors))
for e in errors[:5]:
    print(e)
"""


def test_t10_two_processes(tmp_path):
    root = tmp_path / "cache"
    SharedCache(root, LOAD_LIMIT).close()
    here = str(Path(__file__).resolve().parent)
    procs = [subprocess.Popen([sys.executable, "-c", _PROCESS_LOAD, str(root), str(seed), here],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for seed in (1, 2)]
    outputs = [p.communicate(timeout=300) for p in procs]
    for proc, (out, err) in zip(procs, outputs):
        assert proc.returncode == 0, err
        done, failed = map(int, out.split("\n")[0].split())
        assert (done, failed) == (400, 0), out
    _check_consistent(root)


def _orphans(root, age_seconds):
    folder = root / "files" / "12"
    folder.mkdir(parents=True, exist_ok=True)
    made = []
    for name in (f".tmp-{age_seconds}", f"{age_seconds:064d}.bin"):
        path = folder / name
        path.write_bytes(b"x")
        old = datetime.now().timestamp() - age_seconds
        os.utime(path, (old, old))
        made.append(path)
    return made


def test_t11_orphan_age_threshold_and_once_per_process(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(cache_module, "_CLEANED_ROOTS", set())
    root = tmp_path / "cache"
    old, young = _orphans(root, 601), _orphans(root, 30)
    with caplog.at_level(logging.INFO, logger="astrotwo.cache"):
        SharedCache(root).close()
    assert not any(p.exists() for p in old)
    assert all(p.exists() for p in young)
    assert "600" in caplog.text  # soglia dichiarata nel log
    later = _orphans(root, 3600)
    SharedCache(root).close()  # seconda apertura nello stesso processo: nessuna pulizia
    assert all(p.exists() for p in later)


def test_t11_orphan_threshold_configurable(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_module, "_CLEANED_ROOTS", set())
    root = tmp_path / "cache"
    old = _orphans(root, 120)
    SharedCache(root, orphan_min_age=60).close()
    assert not any(p.exists() for p in old)
    with pytest.raises(ValueError):
        SharedCache(tmp_path / "other", orphan_min_age=0)
