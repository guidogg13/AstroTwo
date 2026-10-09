"""Cache comune dei dati scaricati (A7).

Specifica: ``mdfiles/04-cache.md`` (stato ``approvato``).

- una sola cache per tutta l'app, in ``~/Library/Caches/AstroTwo/``;
- SQLite (``cache.sqlite``) per le righe dei moduli, file su disco
  (``files/<modulo>/``) per i dati in byte;
- ogni voce ha origine e data di scaricamento (UTC, ISO 8601) nel registro;
- un solo limite (5 × 10⁹ byte di default) sulla somma dei dati delle voci,
  con eliminazione LRU registrata nel log;
- nessuna richiesta di rete: i timeout comuni sono qui (``NETWORK_TIMEOUTS``)
  perché siano gli stessi per tutti i moduli.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import sqlite3
import tempfile
import warnings
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "DEFAULT_LIMIT_BYTES",
    "NETWORK_TIMEOUTS",
    "CacheError",
    "CacheWarning",
    "CachedValue",
    "CacheTable",
    "CacheUsage",
    "NetworkTimeouts",
    "SharedCache",
    "default_cache_root",
]

#: Limite unico di default: 5 GB = 5 × 10⁹ byte (CA2).
DEFAULT_LIMIT_BYTES = 5_000_000_000

_DB_NAME = "cache.sqlite"
_FILES_DIR = "files"
_TMP_PREFIX = ".tmp-"
_MODULE_RE = re.compile(r"^\d{2}$")
_IDENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_COLUMN_TYPES = frozenset({"TEXT", "REAL", "INTEGER", "BLOB"})

log = logging.getLogger("astrotwo.cache")


@dataclass(frozen=True)
class NetworkTimeouts:
    """Timeout di rete comuni ai moduli del livello 1 (CA1), in secondi."""

    connect: float = 10.0
    read: float = 60.0

    def __post_init__(self) -> None:
        if not (self.connect > 0 and self.read > 0):
            raise ValueError("i timeout devono essere positivi")

    def as_requests(self) -> tuple[float, float]:
        """Forma ``(connessione, lettura)`` accettata da ``requests``."""
        return (self.connect, self.read)


#: Timeout di default: 10 s per la connessione, 60 s per la lettura (CA1).
NETWORK_TIMEOUTS = NetworkTimeouts()


class CacheError(Exception):
    """Errore della cache con identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


class CacheWarning(UserWarning):
    """Avviso della cache (es. ``CACHE_UNAVAILABLE``): il programma continua."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class CachedValue:
    """Dato servito dalla cache con la sua provenienza (mai senza)."""

    module: str
    key: str
    data: object  # byte per i file, dizionario per le righe
    origin: str
    retrieved_at: datetime
    from_cache: bool = True


@dataclass(frozen=True)
class CacheUsage:
    """Spazio usato (somma dei dati delle voci) e limite, in byte."""

    total_bytes: int
    limit_bytes: int
    by_module: dict[str, int] = field(default_factory=dict)


def default_cache_root() -> Path:
    """Cartella standard delle cache di macOS: ``~/Library/Caches/AstroTwo/``."""
    return Path.home() / "Library" / "Caches" / "AstroTwo"


def _check_module(module: object) -> str:
    if not isinstance(module, str) or not _MODULE_RE.match(module):
        raise ValueError(f"identificativo di modulo non valido: {module!r} (es. '10')")
    return module


def _check_key(key: object) -> str:
    if not isinstance(key, str) or not key:
        raise ValueError("la chiave deve essere una stringa non vuota")
    return key


def _check_provenance(origin: object, retrieved_at: object) -> str:
    if not isinstance(origin, str) or not origin.strip():
        raise CacheError("CACHE_PROVENANCE_MISSING", "origine mancante: nessun dato senza provenienza")
    if not isinstance(retrieved_at, datetime):
        raise CacheError("CACHE_PROVENANCE_MISSING", "data di scaricamento mancante")
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise CacheError("CACHE_PROVENANCE_MISSING", "data di scaricamento senza fuso orario: serve UTC")
    return retrieved_at.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _value_size(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, (bytes, bytearray, memoryview)):
        return len(value)
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, (bool, int, float)):
        return 8
    raise TypeError(f"valore non ammesso in una riga di cache: {type(value).__name__}")


class SharedCache:
    """Cache comune A7 (``04-cache.md`` §7).

    ``root`` si indica solo nei test (cartella temporanea) o per
    un'impostazione esplicita dell'utente; altrimenti è
    ``~/Library/Caches/AstroTwo/``.
    """

    def __init__(self, root: str | os.PathLike | None = None, limit_bytes: int = DEFAULT_LIMIT_BYTES) -> None:
        if isinstance(limit_bytes, bool) or not isinstance(limit_bytes, int) or limit_bytes <= 0:
            raise ValueError("limit_bytes deve essere un intero positivo")
        self.root = Path(root) if root is not None else default_cache_root()
        self.limit_bytes = limit_bytes
        self.available = False
        self._db: sqlite3.Connection | None = None
        self._open()

    # -- apertura, ricreazione, chiusura ----------------------------------

    def _open(self) -> None:
        try:
            (self.root / _FILES_DIR).mkdir(parents=True, exist_ok=True)
            self._db = self._connect()
        except sqlite3.DatabaseError as exc:
            if self._is_corruption(exc):
                self._recreate(f"database corrotto ({exc}): cache ricreata vuota")
            else:
                self._disable(f"database non utilizzabile ({exc}): cache ignorata")
            return
        except OSError as exc:
            self._disable(f"cartella {self.root} non scrivibile ({exc}): cache ignorata")
            return
        self.available = True
        self._remove_orphans()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.root / _DB_NAME, isolation_level=None)
        try:
            db.execute("PRAGMA journal_mode=DELETE")
            row = db.execute("PRAGMA quick_check").fetchone()
            if row is None or row[0] != "ok":
                raise sqlite3.DatabaseError(f"quick_check: {row}")
            db.execute(
                "CREATE TABLE IF NOT EXISTS registry ("
                " key TEXT PRIMARY KEY, module TEXT NOT NULL, kind TEXT NOT NULL,"
                " location TEXT NOT NULL, origin TEXT NOT NULL, retrieved_at TEXT NOT NULL,"
                " size INTEGER NOT NULL, last_use INTEGER NOT NULL, last_used_at TEXT NOT NULL)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO meta VALUES ('use_counter', 0)")
        except Exception:
            db.close()
            raise
        return db

    @staticmethod
    def _is_corruption(exc: sqlite3.DatabaseError) -> bool:
        text = str(exc).lower()
        return "not a database" in text or "malformed" in text or "quick_check" in text or "corrupt" in text

    def _recreate(self, reason: str) -> None:
        warnings.warn(CacheWarning("CACHE_UNAVAILABLE", reason), stacklevel=3)
        log.warning("CACHE_UNAVAILABLE: %s", reason)
        try:
            for suffix in ("", "-journal", "-wal", "-shm"):
                (self.root / f"{_DB_NAME}{suffix}").unlink(missing_ok=True)
            shutil.rmtree(self.root / _FILES_DIR, ignore_errors=True)
            (self.root / _FILES_DIR).mkdir(parents=True, exist_ok=True)
            self._db = self._connect()
        except (OSError, sqlite3.DatabaseError) as exc:
            self._disable(f"ricreazione non riuscita ({exc}): cache ignorata")
            return
        self.available = True

    def _disable(self, reason: str) -> None:
        warnings.warn(CacheWarning("CACHE_UNAVAILABLE", reason), stacklevel=3)
        log.warning("CACHE_UNAVAILABLE: %s", reason)
        self.available = False
        self._db = None

    def _remove_orphans(self) -> None:
        """File temporanei o senza registro: non hanno provenienza, si eliminano."""
        known = {row[0] for row in self._db.execute("SELECT location FROM registry WHERE kind = 'file'")}
        files_dir = self.root / _FILES_DIR
        for path in files_dir.rglob("*"):
            if path.is_file() and path.relative_to(files_dir).as_posix() not in known:
                path.unlink(missing_ok=True)

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None
        self.available = False

    def __enter__(self) -> SharedCache:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- registro ----------------------------------------------------------

    def _next_use(self) -> int:
        self._db.execute("UPDATE meta SET value = value + 1 WHERE name = 'use_counter'")
        return self._db.execute("SELECT value FROM meta WHERE name = 'use_counter'").fetchone()[0]

    def _owner_check(self, module: str, key: str):
        row = self._db.execute(
            "SELECT module, kind, location, origin, retrieved_at, size FROM registry WHERE key = ?", (key,)
        ).fetchone()
        if row is not None and row[0] != module:
            raise CacheError(
                "CACHE_FORBIDDEN", f"la voce {key!r} appartiene al modulo {row[0]}, non al {module}"
            )
        return row

    def _make_room(self, needed: int, replacing_key: str) -> None:
        """Elimina le voci usate meno di recente finché ``needed`` byte entrano."""
        total = self._db.execute("SELECT COALESCE(SUM(size), 0) FROM registry WHERE key != ?", (replacing_key,)).fetchone()[0]
        if total + needed <= self.limit_bytes:
            return
        victims = self._db.execute(
            "SELECT key, module, kind, location, size FROM registry WHERE key != ? ORDER BY last_use ASC",
            (replacing_key,),
        ).fetchall()
        for key, module, kind, location, size in victims:
            self._delete_entry(key, kind, location)
            log.info("eliminazione LRU: modulo %s, voce %r, %d byte (limite %d byte)", module, key, size, self.limit_bytes)
            total -= size
            if total + needed <= self.limit_bytes:
                return

    def _delete_entry(self, key: str, kind: str, location: str) -> None:
        self._db.execute("DELETE FROM registry WHERE key = ?", (key,))
        if kind == "file":
            (self.root / _FILES_DIR / location).unlink(missing_ok=True)
        else:
            self._db.execute(f'DELETE FROM "{location}" WHERE key = ?', (key,))

    def _check_fits(self, size: int, key: str) -> None:
        if size > self.limit_bytes:
            raise CacheError(
                "CACHE_FULL", f"la voce {key!r} ({size} byte) supera da sola il limite di {self.limit_bytes} byte"
            )

    # -- dati in byte (file) ----------------------------------------------

    def put(self, module: str, key: str, data: bytes, origin: str, retrieved_at: datetime) -> None:
        """Salva ``data`` come file con la sua provenienza; applica il limite (LRU)."""
        module, key = _check_module(module), _check_key(key)
        stamp = _check_provenance(origin, retrieved_at)
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("put accetta solo byte; per le righe usare table()")
        data = bytes(data)
        if not self.available:
            warnings.warn(CacheWarning("CACHE_UNAVAILABLE", "cache disattivata: voce non salvata"), stacklevel=2)
            return
        self._check_fits(len(data), key)
        self._owner_check(module, key)
        location = f"{module}/{hashlib.sha256(key.encode('utf-8')).hexdigest()}.bin"
        final = self.root / _FILES_DIR / location
        final.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=_TMP_PREFIX, dir=final.parent)
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._make_room(len(data), key)
                now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
                self._db.execute(
                    "INSERT OR REPLACE INTO registry VALUES (?, ?, 'file', ?, ?, ?, ?, ?, ?)",
                    (key, module, location, origin, stamp, len(data), self._next_use(), now),
                )
                os.replace(tmp, final)  # la voce diventa leggibile solo qui
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
        finally:
            tmp.unlink(missing_ok=True)

    def get(self, module: str, key: str) -> CachedValue | None:
        """Dato + provenienza, o ``None`` se assente; aggiorna l'ultimo uso."""
        module, key = _check_module(module), _check_key(key)
        if not self.available:
            return None
        row = self._owner_check(module, key)
        if row is None:
            return None
        _, kind, location, origin, stamp, _ = row
        if kind != "file":
            raise CacheError("CACHE_FORBIDDEN", f"la voce {key!r} è una riga della tabella {location}: usare table()")
        try:
            data = (self.root / _FILES_DIR / location).read_bytes()
        except OSError:
            # File sparito (es. pulizia del sistema): la voce non è più servibile.
            self._db.execute("DELETE FROM registry WHERE key = ?", (key,))
            return None
        self._touch(key)
        return CachedValue(module=module, key=key, data=data, origin=origin, retrieved_at=_parse_time(stamp))

    def _touch(self, key: str) -> None:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        self._db.execute("BEGIN IMMEDIATE")
        self._db.execute("UPDATE registry SET last_use = ?, last_used_at = ? WHERE key = ?", (self._next_use(), now, key))
        self._db.execute("COMMIT")

    # -- righe (tabelle SQLite dei moduli) --------------------------------

    def table(self, module: str, name: str, columns: Mapping[str, str]) -> CacheTable:
        """Tabella SQLite propria del modulo, con colonne dichiarate dal modulo."""
        module = _check_module(module)
        if not isinstance(name, str) or not _IDENT_RE.match(name):
            raise ValueError(f"nome di tabella non valido: {name!r}")
        cols = dict(columns)
        if not cols:
            raise ValueError("servono le colonne della tabella")
        for col, sqltype in cols.items():
            if not _IDENT_RE.match(col) or col == "key":
                raise ValueError(f"nome di colonna non valido: {col!r}")
            if sqltype not in _COLUMN_TYPES:
                raise ValueError(f"tipo di colonna non ammesso: {sqltype!r} ({', '.join(sorted(_COLUMN_TYPES))})")
        return CacheTable(self, module, f"m{module}_{name}", cols)

    # -- stato e pulizia ----------------------------------------------------

    def usage(self) -> CacheUsage:
        if not self.available:
            return CacheUsage(total_bytes=0, limit_bytes=self.limit_bytes)
        rows = self._db.execute("SELECT module, SUM(size) FROM registry GROUP BY module").fetchall()
        by_module = {module: int(size) for module, size in rows}
        return CacheUsage(total_bytes=sum(by_module.values()), limit_bytes=self.limit_bytes, by_module=by_module)

    def clear(self, module: str | None = None) -> None:
        """Svuota tutta la cache o la parte di un modulo."""
        if module is not None:
            module = _check_module(module)
        if not self.available:
            return
        query = "SELECT key, kind, location FROM registry" + (" WHERE module = ?" if module else "")
        entries = self._db.execute(query, (module,) if module else ()).fetchall()
        self._db.execute("BEGIN IMMEDIATE")
        try:
            for key, kind, location in entries:
                self._delete_entry(key, kind, location)
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        log.info("cache svuotata: %s (%d voci)", f"modulo {module}" if module else "tutti i moduli", len(entries))


class CacheTable:
    """Tabella SQLite di un modulo dentro la cache comune (``SharedCache.table``)."""

    def __init__(self, cache: SharedCache, module: str, sql_name: str, columns: dict[str, str]) -> None:
        self._cache = cache
        self.module = module
        self.sql_name = sql_name
        self.columns = columns
        if cache.available:
            cols = ", ".join(f'"{c}" {t}' for c, t in columns.items())
            cache._db.execute(f'CREATE TABLE IF NOT EXISTS "{sql_name}" (key TEXT PRIMARY KEY, {cols})')

    def put(self, key: str, row: Mapping[str, object], origin: str, retrieved_at: datetime) -> None:
        """Salva una riga con la sua provenienza; applica il limite (LRU)."""
        cache = self._cache
        key = _check_key(key)
        stamp = _check_provenance(origin, retrieved_at)
        if set(row) != set(self.columns):
            raise ValueError(f"colonne attese {sorted(self.columns)}, ricevute {sorted(row)}")
        size = sum(_value_size(row[c]) for c in self.columns)
        if not cache.available:
            warnings.warn(CacheWarning("CACHE_UNAVAILABLE", "cache disattivata: riga non salvata"), stacklevel=2)
            return
        cache._check_fits(size, key)
        cache._owner_check(self.module, key)
        names = ", ".join(f'"{c}"' for c in self.columns)
        marks = ", ".join("?" for _ in self.columns)
        cache._db.execute("BEGIN IMMEDIATE")
        try:
            cache._make_room(size, key)
            cache._db.execute(
                f'INSERT OR REPLACE INTO "{self.sql_name}" (key, {names}) VALUES (?, {marks})',
                (key, *(row[c] for c in self.columns)),
            )
            now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            cache._db.execute(
                "INSERT OR REPLACE INTO registry VALUES (?, ?, 'row', ?, ?, ?, ?, ?, ?)",
                (key, self.module, self.sql_name, origin, stamp, size, cache._next_use(), now),
            )
            cache._db.execute("COMMIT")
        except BaseException:
            cache._db.execute("ROLLBACK")
            raise

    def get(self, key: str) -> CachedValue | None:
        """Riga (dizionario) + provenienza, o ``None`` se assente."""
        cache = self._cache
        key = _check_key(key)
        if not cache.available:
            return None
        entry = cache._owner_check(self.module, key)
        if entry is None:
            return None
        _, kind, location, origin, stamp, _ = entry
        if kind != "row" or location != self.sql_name:
            raise CacheError("CACHE_FORBIDDEN", f"la voce {key!r} non appartiene alla tabella {self.sql_name}")
        names = ", ".join(f'"{c}"' for c in self.columns)
        values = cache._db.execute(f'SELECT {names} FROM "{self.sql_name}" WHERE key = ?', (key,)).fetchone()
        if values is None:
            return None
        cache._touch(key)
        return CachedValue(
            module=self.module,
            key=key,
            data=dict(zip(self.columns, values, strict=True)),
            origin=origin,
            retrieved_at=_parse_time(stamp),
        )
