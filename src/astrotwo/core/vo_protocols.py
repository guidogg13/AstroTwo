"""Protocolli Virtual Observatory: VOTable, esportazione, rete, servizi VO, SAMP.

Specifica: ``mdfiles/14-core-protocolli-vo.md`` (stato ``approvato``).

Il modulo si scrive in 7 parti (decisione del proprietario del 2026-10-10):
P1 lettura/scrittura VOTable ed esportazione; P2 base di rete (timeout,
registro delle richieste, cache, ``download_table``); P3 cone search e TAP;
P4 elenco dei server, registro VO, DataLink; P5 SIA/SIA2, IDHA, SSA;
P6 puntatore Simbad e fotometria VizieR; P7 SAMP.

Un solo lettore di tabelle (D14-9 punto 5): ogni tabella, anche ricevuta
dalla rete, si legge con ``read_table`` del modulo 13; qui vivono solo la
rete, i protocolli e la scrittura.
"""

from __future__ import annotations

import dataclasses
import io
import json
import os
import tempfile
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import astropy
import numpy as np
from astropy.io import ascii as astropy_ascii
from astropy.io import fits
import requests
from astropy.table import Table

import astrotwo
from astrotwo.core.cache import NETWORK_TIMEOUTS, CacheError, NetworkTimeouts, SharedCache
from astrotwo.core.catalogs import (
    CatalogsError,
    CatalogTable,
    TableLimits,
    _catalog_votable,
    detect_table_format,
    read_table,
)

__all__ = [
    "DEFAULT_MAX_ROWS",
    "EXPORT_FORMATS",
    "RequestRecord",
    "VoResult",
    "download_table",
    "VOTABLE_VERSION",
    "VoProtocolsError",
    "export_table",
    "read_votable",
    "write_votable",
]


class VoProtocolsError(Exception):
    """Errore del modulo 14 con identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------------
# P1 — Lettura/scrittura VOTable ed esportazione con provenienza
# --------------------------------------------------------------------------

#: Formati di esportazione (D13).
EXPORT_FORMATS: tuple[str, ...] = ("csv", "votable", "fits")
#: Versione dei VOTable scritti (D14-9 punto 9).
VOTABLE_VERSION = "1.4"
_FORMAT_VERSIONS = {
    "votable": f"VOTable {VOTABLE_VERSION}",
    "fits": f"FITS (scritto con astropy.io.fits {astropy.__version__})",
    "csv": "CSV (RFC 4180)",
}


def read_votable(path, *, table: int | None = None, limits: TableLimits | None = None) -> CatalogTable:
    """Legge un VOTable con ``read_table`` del 13; file malformato o non VOTable → ``VOTABLE_INVALID``."""
    text = os.fspath(path)
    try:
        fmt = detect_table_format(text)
    except CatalogsError as exc:
        if exc.code == "TABLE_UNREADABLE":
            raise
        raise VoProtocolsError("VOTABLE_INVALID", f"{text}: non è un VOTable ({exc.message})", path=text) from exc
    if fmt != "votable":
        raise VoProtocolsError("VOTABLE_INVALID", f"{text}: non è un VOTable (contenuto riconosciuto: {fmt})",
                               path=text)
    try:
        return read_table(text, table=table, limits=limits)
    except CatalogsError as exc:
        if exc.code != "TABLE_UNREADABLE":
            raise
        # Il messaggio di astropy indica riga e colonna del problema (es. "12:3: ...").
        raise VoProtocolsError("VOTABLE_INVALID", f"{text}: VOTable malformato ({exc.message})", path=text) from exc


def write_votable(table: CatalogTable, path, overwrite: bool = False) -> Path:
    """Scrive un VOTable 1.4 con provenienza: ``export_table(table, path, "votable")``."""
    return export_table(table, path, "votable", overwrite=overwrite)


def _provenance(table: CatalogTable, fmt: str) -> dict[str, str]:
    """Provenienza comune ai tre formati (stesse chiavi, D14-9 punto 9)."""
    info = {
        "A2VERS": f"AstroTwo {astrotwo.__version__}",
        "A2FORMAT": _FORMAT_VERSIONS[fmt],
        "A2ORIGIN": table.origin,
        "A2DATE": _iso(table.retrieved_at),
        "A2EXPORT": _iso(datetime.now(UTC)),
        "A2HIST": " | ".join(table.history) or "nessuna operazione",
    }
    if table.body is not None:
        info["A2BODY"] = table.body
    pos = table.positions
    if pos is not None:
        info["A2POS"] = f"{pos.lon}/{pos.lat}, frame {pos.frame}, fonte {pos.source}"
    return info


def _write_votable_file(table: CatalogTable, target: Path, info: dict[str, str]) -> None:
    from astropy.io.votable.tree import Info

    vot, notes = _catalog_votable(table, table.table)
    vot.version = VOTABLE_VERSION
    resource = vot.resources[0]
    for name, value in info.items():
        resource.infos.append(Info(name=name, value=value))
    for note in notes:
        resource.infos.append(Info(name="A2NOTE", value=note))
    vot.to_xml(str(target))


def _write_fits_file(table: CatalogTable, target: Path, info: dict[str, str]) -> None:
    data = table.table.copy(copy_data=False)
    data.meta = {}
    for name in data.colnames:
        col = data[name]
        if col.dtype == object and all(isinstance(v, str) for v in np.ma.compressed(col)):
            # Testi a lunghezza variabile (es. VOTable arraysize="*"): FITS vuole una larghezza fissa.
            data[name] = col.astype(str)
            data[name].meta, data[name].unit, data[name].description = col.meta, col.unit, col.description
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hdu = fits.table_to_hdu(data)
    header = hdu.header
    for name, value in info.items():
        if name == "A2HIST":
            for step in table.history:
                header.add_history(step)
            continue
        header[name] = value  # chiavi di 8 caratteri al massimo; testi lunghi con CONTINUE
    for k, name in enumerate(data.colnames, start=1):
        ucd = data[name].meta.get("ucd")
        if ucd:
            header[f"TUCD{k}"] = ucd  # convenzione diffusa per gli UCD nelle tabelle FITS
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(target)


def _write_csv_file(table: CatalogTable, target: Path, info: dict[str, str]) -> None:
    buffer = io.StringIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        astropy_ascii.write(table.table, buffer, format="csv", fast_writer=False)
    # D14-10 (da decidere): nessuna unità nel CSV, solo provenienza e valori.
    lines = [f"# {name} = {value}" for name, value in info.items()]
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.write(buffer.getvalue())


def export_table(table: CatalogTable, path, format: str, overwrite: bool = False) -> Path:
    """Salva una tabella in CSV, VOTable o FITS con origine, data, versione di AstroTwo e del formato."""
    if format not in EXPORT_FORMATS:
        raise VoProtocolsError("EXPORT_FORMAT_UNSUPPORTED",
                               f"formato {format!r}: ammessi {', '.join(EXPORT_FORMATS)}")
    if not isinstance(table, CatalogTable):
        raise TypeError("export_table accetta una CatalogTable (nessun dato senza provenienza)")
    target = Path(os.fspath(path)).expanduser()
    if target.exists() and not overwrite:
        raise VoProtocolsError("FILE_EXISTS", f"{target}: esiste già; usare overwrite=True", path=str(target))
    if target.exists():
        target.unlink()
    info = _provenance(table, format)
    {"votable": _write_votable_file, "fits": _write_fits_file, "csv": _write_csv_file}[format](table, target, info)
    return target


# --------------------------------------------------------------------------
# P2 — Base di rete: timeout comuni, registro delle richieste, cache
# --------------------------------------------------------------------------

_CACHE_MODULE = "14"
_QUERY_TABLE = "query_results"
_QUERY_COLUMNS = {"protocol": "TEXT", "url": "TEXT", "params": "TEXT", "payload": "BLOB"}
#: Righe massime di default delle interrogazioni (D14-5).
DEFAULT_MAX_ROWS = 100_000


@dataclass(frozen=True)
class RequestRecord:
    """Richiesta di rete registrata: basta per rieseguirla (regola d'oro n. 6)."""

    protocol: str
    command: str
    arguments: dict
    url: str
    method: str
    params: tuple[tuple[str, str], ...]
    retrieved_at: datetime
    rows: int | None
    from_cache: bool

    def as_dict(self) -> dict:
        return {
            "protocol": self.protocol,
            "command": self.command,
            "arguments": dict(self.arguments),
            "url": self.url,
            "method": self.method,
            "params": [list(p) for p in self.params],
            "retrieved_at": _iso(self.retrieved_at),
            "rows": self.rows,
            "from_cache": self.from_cache,
        }


@dataclass(frozen=True)
class VoResult:
    """Tabella ricevuta (``CatalogTable`` del 13) con la richiesta registrata e gli avvisi."""

    table: CatalogTable
    request: RequestRecord
    warnings: tuple[tuple[str, str], ...] = ()
    truncated: bool = False
    max_rows: int | None = None


@dataclass(frozen=True)
class _Response:
    payload: bytes
    url: str
    method: str
    params: tuple[tuple[str, str], ...]
    retrieved_at: datetime
    from_cache: bool
    notes: tuple[tuple[str, str], ...] = field(default=())


class _Session(requests.Session):
    """Sessione HTTP con i timeout comuni di ``04-cache.md`` (CA1) su ogni richiesta."""

    def __init__(self, timeouts: NetworkTimeouts) -> None:
        super().__init__()
        self.timeouts = timeouts.as_requests()
        self.headers["User-Agent"] = f"AstroTwo/{astrotwo.__version__} {self.headers.get('User-Agent', '')}".strip()

    def request(self, method, url, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self.timeouts
        return super().request(method, url, **kwargs)


def _canonical(params) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(k), str(v)) for k, v in dict(params or {}).items()))


def _cache_key(protocol: str, method: str, url: str, params: tuple[tuple[str, str], ...]) -> str:
    return f"{protocol}:{method}:{url}?" + json.dumps(params, ensure_ascii=False, separators=(",", ":"))


def _net_error(url: str, exc: Exception, timeouts: NetworkTimeouts, hint: str = "") -> VoProtocolsError:
    return VoProtocolsError(
        "NET_TIMEOUT",
        f"{url} non raggiungibile (timeout {timeouts.connect:g} s connessione, {timeouts.read:g} s lettura): "
        f"{exc}{hint}",
        url=url,
    )


def _check_http(response: requests.Response, url: str) -> None:
    if response.status_code in (401, 403):
        raise VoProtocolsError(
            "AUTH_REQUIRED",
            f"{url}: il servizio chiede autenticazione (HTTP {response.status_code}); nel livello 1 solo servizi "
            "pubblici",
            url=url,
        )


def _http(protocol: str, url: str, params=None, *, method: str = "GET", cache: SharedCache | None,
          refresh: bool, timeouts: NetworkTimeouts, accept_error_body: bool = False,
          hint: str = "") -> _Response:
    """Richiesta con prima la cache (``refresh=True`` la rifà); salva in cache solo le risposte riuscite.

    ``accept_error_body``: una risposta HTTP di errore con un corpo (es. VOTable con ``QUERY_STATUS``
    ``ERROR``) si restituisce al chiamante, che ne legge il messaggio; non va mai in cache.
    """
    canonical = _canonical(params)
    cache = SharedCache() if cache is None else cache
    rows = cache.table(_CACHE_MODULE, _QUERY_TABLE, _QUERY_COLUMNS)
    key = _cache_key(protocol, method, url, canonical)
    cached = rows.get(key)
    if cached is not None and not refresh:
        return _Response(cached.data["payload"], url, method, canonical, cached.retrieved_at, True,
                         (("FROM_CACHE", f"copia in cache di {cached.origin}, scaricata il "
                           f"{_iso(cached.retrieved_at)}"),))
    try:
        with _Session(timeouts) as session:
            if method == "POST":
                response = session.post(url, data=dict(canonical))
            else:
                response = session.get(url, params=dict(canonical))
            payload = response.content
    except requests.exceptions.RequestException as exc:
        if cached is not None:
            return _Response(cached.data["payload"], url, method, canonical, cached.retrieved_at, True,
                             (("FROM_CACHE", f"rete non disponibile ({type(exc).__name__}): copia in cache del "
                               f"{_iso(cached.retrieved_at)}"),))
        raise _net_error(url, exc, timeouts, hint) from exc
    _check_http(response, url)
    retrieved_at = datetime.now(UTC)
    if not response.ok:
        if accept_error_body and payload:
            return _Response(payload, url, method, canonical, retrieved_at, False, (("HTTP_STATUS", str(response.status_code)),))
        raise VoProtocolsError("SERVICE_ERROR", f"{url}: risposta HTTP {response.status_code} {response.reason}",
                               url=url, status=response.status_code)
    return _Response(payload, url, method, canonical, retrieved_at, False)


def _store(response: _Response, protocol: str, cache: SharedCache | None) -> tuple[tuple[str, str], ...]:
    """Salva in cache una risposta riuscita appena scaricata; restituisce gli avvisi (es. ``CACHE_FULL``)."""
    if response.from_cache:
        return ()
    cache = SharedCache() if cache is None else cache
    rows = cache.table(_CACHE_MODULE, _QUERY_TABLE, _QUERY_COLUMNS)
    key = _cache_key(protocol, response.method, response.url, response.params)
    row = {"protocol": protocol, "url": response.url, "params": json.dumps(response.params, ensure_ascii=False),
           "payload": response.payload}
    origin = response.url + ("?" + "&".join(f"{k}={v}" for k, v in response.params) if response.params else "")
    try:
        rows.put(key, row, origin=origin, retrieved_at=response.retrieved_at)
    except CacheError as exc:  # es. CACHE_FULL: il dato si usa comunque
        return ((exc.code, exc.message),)
    return ()


def _read_payload(response: _Response, *, table=None, format=None, limits: TableLimits | None = None,
                  origin: str | None = None) -> CatalogTable:
    """Legge i byte ricevuti con ``read_table`` del 13 (un solo lettore) e mette la provenienza di rete."""
    fd, tmp = tempfile.mkstemp(prefix="astrotwo-vo-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(response.payload)
        result = read_table(tmp, table=table, format=format, limits=limits)
    finally:
        os.unlink(tmp)
    where = origin or response.url
    return dataclasses.replace(result, source=where, origin=where, retrieved_at=response.retrieved_at,
                               file_modified=None)


def _record(protocol: str, command: str, arguments: dict, response: _Response, rows: int | None) -> RequestRecord:
    return RequestRecord(protocol=protocol, command=command, arguments=arguments, url=response.url,
                         method=response.method, params=response.params, retrieved_at=response.retrieved_at,
                         rows=rows, from_cache=response.from_cache)


def download_table(url: str, *, table: int | None = None, format: str | None = None,
                   limits: TableLimits | None = None, cache: SharedCache | None = None, refresh: bool = False,
                   timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> VoResult:
    """Scarica una tabella da URL (D3) e la legge con ``read_table`` del 13; prima la cache."""
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError(f"URL non valido: {url!r} (serve http:// o https://)")
    response = _http("download", url, cache=cache, refresh=refresh, timeouts=timeouts)
    result = _read_payload(response, table=table, format=format, limits=limits)
    notes = response.notes + _store(response, "download", cache)
    arguments = {"url": url, "table": table, "format": format}
    return VoResult(table=result, request=_record("download", "download_table", arguments, response, result.rows),
                    warnings=notes)
