# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
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
import re
import tempfile
import threading
import time
import warnings
from dataclasses import dataclass, field
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import astropy
import numpy as np
from astropy.io import ascii as astropy_ascii
from astropy.io import fits
import astropy.units as u
import pyvo
import requests
from astropy.time import Time
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError as XmlParseError
from defusedxml.ElementTree import fromstring as safe_fromstring
from defusedxml.ElementTree import parse as safe_parse
from astropy.coordinates import SkyCoord
from astropy.io.votable import parse as parse_votable
from astropy.table import Table

import astrotwo
from astrotwo.core.cache import NETWORK_TIMEOUTS, CacheError, NetworkTimeouts, SharedCache
from astrotwo.core.coordinates_wcs import CoordinatesWcsError, ModuleWarning, SkyFrame, wcs_from_header
from astrotwo.core.catalogs import (
    CatalogsError,
    CatalogTable,
    TableLimits,
    _catalog_votable,
    _read_table,
    detect_table_format,
    read_table,
)

__all__ = [
    "DEFAULT_MAX_ROWS",
    "EXPORT_FORMATS",
    "ExportResult",
    "AdqlCheck",
    "SAMP_MTYPES",
    "SampClient",
    "SampFailure",
    "SampHub",
    "SampSelection",
    "SampSendResult",
    "SampTableReference",
    "SAMP_HUB_EVENTS",
    "SIMBAD_COORDINATES_NOTE",
    "SimbadObject",
    "SimbadMagnitude",
    "SIMBAD_FLUX_SYSTEMS",
    "SimbadPointer",
    "SimbadRecord",
    "SIMBAD_BASIC_COLUMNS",
    "simbad_object",
    "VIZIER_PHOTOMETRY_URL",
    "MOCSERVER_CHARSET",
    "MOCSERVER_URL",
    "XMATCH_URL",
    "cds_xmatch",
    "MocServerRecords",
    "vizier_collections",
    "simbad_pointer",
    "vizier_photometry",
    "Spectrum",
    "SiaCalibration",
    "sia_calibration",
    "read_idha",
    "sia_search",
    "ssa_load",
    "ssa_search",
    "BUILTIN_SERVERS",
    "DEFAULT_REGISTRY_URL",
    "DataLinkClient",
    "DataLinks",
    "DataProduct",
    "PROTOCOLS",
    "RegistrySearch",
    "ServerEntry",
    "ServerRegistry",
    "ServiceDescriptor",
    "ServiceParam",
    "DEFAULT_ASYNC_TIMEOUT",
    "RequestRecord",
    "VoResult",
    "cone_search",
    "download_table",
    "tap_query",
    "validate_adql",
    "adql_to_send",
    "service_url",
    "SERVICE_MIRRORS",
    "ServiceMirrors",
    "SIMBAD_SERVERS",
    "current_server",
    "is_failover_error",
    "reset_mirror_state",
    "service_servers",
    "VOTABLE_VERSION",
    "VoProtocolsError",
    "export_table",
    "read_votable",
    "write_votable",
]


class VoProtocolsError(Exception):
    """Errore del modulo 14 con identificatore della specifica (§10).

    ``params``: valori JSON del messaggio (D40-3); la traduzione è del catalogo del 40 (§10, "Parametri dei messaggi")."""

    def __init__(self, code: str, message: str, *, params: Mapping[str, object] | None = None,
                 **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.params = dict(params or {})
        self.details = details


def _q(value, unit: str) -> dict:
    """Valore con unità in forma JSON (``params``), mai arrotondato."""
    return {"value": float(value), "unit": unit}


def _message_of(exc) -> dict:
    """Messaggio annidato (tipo ``message``, D40-7) di un errore di AstroTwo: codice, ``params`` e testo suoi."""
    return {"code": exc.code, "params": dict(getattr(exc, "params", None) or {}), "text": exc.message}


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------------
# P1 — Lettura/scrittura VOTable ed esportazione con provenienza
# --------------------------------------------------------------------------

#: Formati di esportazione (D13; ``ecsv`` con D14-10).
EXPORT_FORMATS: tuple[str, ...] = ("csv", "ecsv", "votable", "fits")
#: Versione dei VOTable scritti (D14-9 punto 9).
VOTABLE_VERSION = "1.4"
_FORMAT_VERSIONS = {
    "votable": f"VOTable {VOTABLE_VERSION}",
    "fits": "FITS Standard 4.0",
    "csv": "CSV (RFC 4180)",
    "ecsv": "ECSV 1.0",
}
#: Libreria che scrive i file (A2WRITER, accanto alla versione del formato).
_WRITER = f"astropy {astropy.__version__}"


@dataclass(frozen=True)
class ExportResult:
    """File esportato con il formato e gli avvisi (es. ``CSV_UNITS_NOT_SAVED``); vale come percorso."""

    path: Path
    format: str
    warnings: tuple[tuple[str, str], ...] = ()

    def __fspath__(self) -> str:
        return os.fspath(self.path)


def read_votable(path, *, table: int | None = None, limits: TableLimits | None = None) -> CatalogTable:
    """Legge un VOTable con ``read_table`` del 13; file malformato o non VOTable → ``VOTABLE_INVALID``."""
    text = os.fspath(path)
    try:
        fmt = detect_table_format(text)
    except CatalogsError as exc:
        if exc.code == "TABLE_UNREADABLE":
            raise
        raise VoProtocolsError("VOTABLE_INVALID", f"{text}: non è un VOTable ({exc.message})", path=text,
                               params={"reason": "not_votable", "path": text, "cause": _message_of(exc)}) from exc
    if fmt != "votable":
        raise VoProtocolsError("VOTABLE_INVALID", f"{text}: non è un VOTable (contenuto riconosciuto: {fmt})",
                               path=text, params={"reason": "other_format", "path": text, "format": fmt})
    try:
        return read_table(text, table=table, limits=limits)
    except CatalogsError as exc:
        if exc.code != "TABLE_UNREADABLE":
            raise
        # Il messaggio di astropy indica riga e colonna del problema (es. "12:3: ...").
        raise VoProtocolsError("VOTABLE_INVALID", f"{text}: VOTable malformato ({exc.message})", path=text,
                               params={"reason": "malformed", "path": text, "cause": _message_of(exc)}) from exc


def write_votable(table: CatalogTable, path, overwrite: bool = False) -> ExportResult:
    """Scrive un VOTable 1.4 con provenienza: ``export_table(table, path, "votable")``."""
    return export_table(table, path, "votable", overwrite=overwrite)


def _provenance(table: CatalogTable, fmt: str) -> dict[str, str]:
    """Provenienza comune ai tre formati (stesse chiavi, D14-9 punto 9)."""
    info = {
        "A2VERS": f"AstroTwo {astrotwo.__version__}",
        "A2FORMAT": _FORMAT_VERSIONS[fmt],
        "A2WRITER": _WRITER,
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
    # CSV semplice (D14-10): provenienza e valori, nessuna unità (avviso CSV_UNITS_NOT_SAVED).
    lines = [f"# {name} = {value}" for name, value in info.items()]
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.write(buffer.getvalue())


def _write_ecsv_file(table: CatalogTable, target: Path, info: dict[str, str]) -> None:
    """ECSV di astropy (D14-10): unità, UCD e descrizioni nell'intestazione, provenienza nei metadati."""
    data = table.table.copy(copy_data=False)
    data.meta = dict(info)
    pos = table.positions
    if pos is not None and pos.frame is not None:
        # Sistema delle posizioni nei metadati YAML (l'ECSV non ha un COOSYS): il 13 lo rilegge.
        data.meta["A2POSITIONS"] = {"lon": pos.lon, "lat": pos.lat, "frame": pos.frame, "system": pos.system,
                                    "equinox": pos.equinox, "epoch": pos.epoch, "source": pos.source}
    for name in data.colnames:
        col = data[name]
        meta = {k: v for k, v in col.meta.items() if k != "ref"}  # il COOSYS citato non esiste nell'ECSV
        unrecognized = meta.pop("unit_unrecognized", None)
        if col.dtype == object and all(isinstance(v, str) for v in np.ma.compressed(col)):
            data[name] = col.astype(str)
            data[name].description = col.description
        data[name].meta = meta
        data[name].unit = col.unit if unrecognized is None else u.Unit(unrecognized, parse_strict="silent")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        astropy_ascii.write(data, str(target), format="ecsv", delimiter=",")


def _has_units(table: CatalogTable) -> bool:
    return any(table.table[n].unit is not None or table.table[n].meta.get("unit_unrecognized")
               for n in table.table.colnames)


def export_table(table: CatalogTable, path, format: str, overwrite: bool = False) -> ExportResult:
    """Salva una tabella in CSV, ECSV, VOTable o FITS con origine, data, versione di AstroTwo e del formato.

    Il CSV semplice non salva le unità: con colonne che ne hanno, avviso ``CSV_UNITS_NOT_SAVED``
    (per conservarle: ``ecsv``, D14-10)."""
    if format not in EXPORT_FORMATS:
        raise VoProtocolsError("EXPORT_FORMAT_UNSUPPORTED",
                               f"formato {format!r}: ammessi {', '.join(EXPORT_FORMATS)}",
                               params={"format": str(format), "allowed": list(EXPORT_FORMATS)})
    if not isinstance(table, CatalogTable):
        raise TypeError("export_table accetta una CatalogTable (nessun dato senza provenienza)")
    target = Path(os.fspath(path)).expanduser()
    if target.exists() and not overwrite:
        raise VoProtocolsError("FILE_EXISTS", f"{target}: esiste già; usare overwrite=True", path=str(target),
                               params={"path": str(target)})
    if target.exists():
        target.unlink()
    info = _provenance(table, format)
    writers = {"votable": _write_votable_file, "fits": _write_fits_file, "csv": _write_csv_file,
               "ecsv": _write_ecsv_file}
    writers[format](table, target, info)
    notes = []
    if format == "csv" and _has_units(table):
        notes.append(ModuleWarning("CSV_UNITS_NOT_SAVED", "il CSV semplice non salva le unità delle colonne: per "
                                   "conservarle esportare in ecsv (D14-10)"))
    return ExportResult(path=target, format=format, warnings=tuple(notes))


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
    descriptors: tuple[ServiceDescriptor, ...] = ()  # descrittori di servizio del VOTable (DataLink, SODA…)


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
    """Parametri ordinati; un valore lista (es. ``POS`` ripetuto in SIA2) dà una coppia per elemento."""
    pairs = []
    for key, value in dict(params or {}).items():
        for item in (value if isinstance(value, (list, tuple)) else [value]):
            pairs.append((str(key), str(item)))
    return tuple(sorted(pairs))


def _cache_key(protocol: str, method: str, url: str, params: tuple[tuple[str, str], ...]) -> str:
    return f"{protocol}:{method}:{url}?" + json.dumps(params, ensure_ascii=False, separators=(",", ":"))


def _net_error(url: str, exc: Exception, timeouts: NetworkTimeouts, hint: str = "") -> VoProtocolsError:
    return VoProtocolsError(
        "NET_TIMEOUT",
        f"{url} non raggiungibile (timeout {timeouts.connect:g} s connessione, {timeouts.read:g} s lettura): "
        f"{exc}{hint}",
        url=url,
        params={"reason": "url_sync_tap" if hint else "url", "url": url, "connect": _q(timeouts.connect, "s"),
                "read": _q(timeouts.read, "s"), "detail": str(exc)},
    )


def _network_cached(exc: Exception, cached) -> ModuleWarning:
    """``FROM_CACHE`` per rete non disponibile: copia in cache con la sua data."""
    return ModuleWarning("FROM_CACHE", f"rete non disponibile ({type(exc).__name__}): copia in cache del "
                         f"{_iso(cached.retrieved_at)}", {"reason": "network_cached", "error": type(exc).__name__,
                                                          "retrieved_at": _iso(cached.retrieved_at)})


def _cached_since(cached) -> ModuleWarning:
    """``FROM_CACHE`` per una risposta già in cache (SIMBAD, XMatch)."""
    return ModuleWarning("FROM_CACHE", f"copia in cache del {_iso(cached.retrieved_at)}",
                         {"reason": "cached_since", "retrieved_at": _iso(cached.retrieved_at)})


def _network_unavailable(exc: Exception) -> ModuleWarning:
    """``FROM_CACHE`` per rete non disponibile, copia in cache senza data nel testo (SIMBAD, XMatch)."""
    return ModuleWarning("FROM_CACHE", f"rete non disponibile ({type(exc).__name__}): copia in cache",
                         {"reason": "network_unavailable", "error": type(exc).__name__})


def _check_http(response: requests.Response, url: str) -> None:
    if response.status_code in (401, 403):
        raise VoProtocolsError(
            "AUTH_REQUIRED",
            f"{url}: il servizio chiede autenticazione (HTTP {response.status_code}); nel livello 1 solo servizi "
            "pubblici",
            url=url,
            params={"url": url, "status": response.status_code},
        )


def _http(protocol: str, url: str, params=None, *, method: str = "GET", cache: SharedCache | None,
          refresh: bool, timeouts: NetworkTimeouts, accept_error_body: bool = False,
          hint: str = "", use_stale: bool = True) -> _Response:
    """Richiesta con prima la cache (``refresh=True`` la rifà); salva in cache solo le risposte riuscite.

    ``accept_error_body``: una risposta HTTP di errore con un corpo (es. VOTable con ``QUERY_STATUS``
    ``ERROR``) si restituisce al chiamante, che ne legge il messaggio; non va mai in cache.
    ``use_stale=False``: con la rete giù la copia in cache non si restituisce (ripiego sui mirror, sprint B4).
    """
    canonical = _canonical(params)
    cache = SharedCache() if cache is None else cache
    rows = cache.table(_CACHE_MODULE, _QUERY_TABLE, _QUERY_COLUMNS)
    key = _cache_key(protocol, method, url, canonical)
    cached = rows.get(key)
    if cached is not None and not refresh:
        return _Response(cached.data["payload"], url, method, canonical, cached.retrieved_at, True,
                         (ModuleWarning("FROM_CACHE", f"copia in cache di {cached.origin}, scaricata il "
                                        f"{_iso(cached.retrieved_at)}",
                                        {"reason": "cached_origin", "origin": cached.origin,
                                         "retrieved_at": _iso(cached.retrieved_at)}),))
    try:
        with _Session(timeouts) as session:
            if method == "POST":
                response = session.post(url, data=list(canonical))
            else:
                response = session.get(url, params=list(canonical))
            payload = response.content
    except requests.exceptions.RequestException as exc:
        if cached is not None and use_stale:
            return _Response(cached.data["payload"], url, method, canonical, cached.retrieved_at, True,
                             (_network_cached(exc, cached),))
        raise _net_error(url, exc, timeouts, hint) from exc
    _check_http(response, url)
    retrieved_at = datetime.now(UTC)
    if not response.ok:
        if accept_error_body and payload:
            return _Response(payload, url, method, canonical, retrieved_at, False, (("HTTP_STATUS", str(response.status_code)),))
        raise VoProtocolsError("SERVICE_ERROR", f"{url}: risposta HTTP {response.status_code} {response.reason}",
                               url=url, status=response.status_code,
                               params={"reason": "http_status", "url": url, "status": response.status_code,
                                       "status_text": str(response.reason)})
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
        return (ModuleWarning(exc.code, exc.message, getattr(exc, "params", None)),)
    return ()


def _link_fetcher(*, cache: SharedCache | None = None, refresh: bool = False,
                  timeouts: NetworkTimeouts = NETWORK_TIMEOUTS):
    """Funzione di rete per i dati in un ``LINK`` ASTRORES (D13-17): prima la cache, risposta registrata."""

    def fetch(url: str) -> tuple[bytes, tuple[str, str]]:
        response = _http("download", url, cache=cache, refresh=refresh, timeouts=timeouts)
        _store(response, "download", cache)
        state = "copia in cache" if response.from_cache else "scaricati"
        return response.payload, ModuleWarning(
            "ASTRORES_LINK_SOURCE", f"dati collegati {url}: {state} il {_iso(response.retrieved_at)}",
            {"reason": "cached" if response.from_cache else "downloaded", "url": url,
             "retrieved_at": _iso(response.retrieved_at)})

    return fetch


def _read_payload(response: _Response, *, table=None, format=None, limits: TableLimits | None = None,
                  origin: str | None = None, fetch_link=None) -> CatalogTable:
    """Legge i byte ricevuti con ``read_table`` del 13 (un solo lettore) e mette la provenienza di rete."""
    fd, tmp = tempfile.mkstemp(prefix="astrotwo-vo-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(response.payload)
        result = _read_table(tmp, table=table, format=format, limits=limits, fetch_link=fetch_link,
                             base=response.url)
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
    result = _read_payload(response, table=table, format=format, limits=limits,
                           fetch_link=_link_fetcher(cache=cache, refresh=refresh, timeouts=timeouts))
    notes = response.notes + _store(response, "download", cache)
    arguments = {"url": url, "table": table, "format": format}
    descriptors = ()
    if result.format == "votable":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            descriptors = _descriptors(parse_votable(io.BytesIO(response.payload), verify="ignore"), response.payload)
    return VoResult(table=result, request=_record("download", "download_table", arguments, response, result.rows),
                    warnings=notes, descriptors=descriptors)


# --------------------------------------------------------------------------
# P3 — Cone search, TAP/ADQL, validate_adql
# --------------------------------------------------------------------------

#: Attesa massima complessiva delle interrogazioni TAP asincrone, in secondi (D14-9 punto 8).
DEFAULT_ASYNC_TIMEOUT = 600.0
_ASYNC_HINT = " — per le interrogazioni lunghe usare tap_query(..., mode='async')"
_DURATION_WORDS = re.compile(r"time ?out|timed out|time limit|execution ?duration|too long|exceed", re.IGNORECASE)


@dataclass(frozen=True)
class AdqlCheck:
    """Esito dei controlli minimi lato client (D14-9 punto 4); l'esito del servizio prevale."""

    valid: bool
    message: str
    position: int | None = None
    reason: str | None = None  # identificatore della sotto-voce di ``ADQL_INVALID`` (D40-6); ``None`` se valida
    quote: str | None = None  # la virgoletta non chiusa (``reason == "unclosed_quote"``)


def _adql_comments(adql: str) -> list[tuple[int, int]]:
    """Intervalli ``[inizio, fine)`` dei commenti ``--`` fuori dalle virgolette, fino a fine riga esclusa (ADQL 2.1).

    Le virgolette dentro un commento non contano; ``--`` dentro una stringa o un identificatore tra virgolette non è
    un commento (sprint B3, 14 §3)."""
    spans, quote, k = [], None, 0
    while k < len(adql):
        ch = adql[k]
        if quote is not None:
            if ch == quote:
                if adql[k + 1:k + 2] == quote:  # virgoletta raddoppiata dentro il testo
                    k += 2
                    continue
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif adql.startswith("--", k):
            end = adql.find("\n", k)
            end = len(adql) if end < 0 else end
            spans.append((k, end))
            k = end
            continue
        k += 1
    return spans


def adql_to_send(adql: str) -> str:
    """Testo ADQL senza i commenti ``--`` (fuori dalle virgolette) e senza le righe rimaste vuote (14 §3, sprint B3).

    Provato il 2026-11-06: Gaia (ESA), IRSA e HEASARC rifiutano una query con una riga di commento, MAST la
    accetta. Senza commenti il testo torna invariato; il resto del testo non cambia mai."""
    spans = _adql_comments(adql)
    if not spans:
        return adql
    text = adql
    for start, end in reversed(spans):
        line_start = text.rfind("\n", 0, start) + 1
        before = text[line_start:start]
        if before.strip():  # codice prima del commento: si toglie il commento con gli spazi che lo precedono
            text = text[:line_start] + before.rstrip() + text[end:]
        elif end < len(text):  # riga di solo commento: si toglie con il suo a capo
            text = text[:line_start] + text[end + 1:]
        else:  # ultima riga di solo commento: si toglie con l'a capo che la precede
            text = text[:max(line_start - 1, 0)]
    return text


def validate_adql(adql: str) -> AdqlCheck:
    """Controlli minimi: non vuota, inizia con SELECT, virgolette chiuse, parentesi bilanciate.

    I commenti ``--`` (fuori dalle virgolette) contano come spazio, anche prima di ``SELECT``; le posizioni sono
    quelle del testo scritto (sprint B3)."""
    if not isinstance(adql, str):
        return AdqlCheck(False, "ADQL vuota", 0, "empty")
    for start, end in _adql_comments(adql):
        adql = adql[:start] + " " * (end - start) + adql[end:]
    if not adql.strip():
        return AdqlCheck(False, "ADQL vuota", 0, "empty")
    start = len(adql) - len(adql.lstrip())
    if not re.match(r"select\b", adql[start:], re.IGNORECASE):
        return AdqlCheck(False, "l'ADQL deve iniziare con SELECT", start, "not_select")
    quote, quote_at, opened = None, None, []
    k = start
    while k < len(adql):
        ch = adql[k]
        if quote is not None:
            if ch == quote:
                if adql[k + 1:k + 2] == quote:  # virgoletta raddoppiata dentro il testo
                    k += 2
                    continue
                quote = None
        elif ch in ("'", '"'):
            quote, quote_at = ch, k
        elif ch == "(":
            opened.append(k)
        elif ch == ")":
            if not opened:
                return AdqlCheck(False, "parentesi chiusa senza apertura", k, "unmatched_close")
            opened.pop()
        k += 1
    if quote is not None:
        return AdqlCheck(False, f"virgoletta {quote} non chiusa", quote_at, "unclosed_quote", quote)
    if opened:
        return AdqlCheck(False, "parentesi aperta non chiusa", opened[-1], "unclosed_paren")
    return AdqlCheck(True, "controlli minimi superati (la validazione vera è del servizio)")


def _adql_params(check: AdqlCheck) -> dict:
    """``params`` di ``ADQL_INVALID`` per un controllo lato client non superato (sotto-voce = ``check.reason``)."""
    params = {"reason": check.reason, "position": check.position}
    if check.quote is not None:
        params["quote"] = check.quote
    return params


def _check_max_rows(max_rows, limits: TableLimits | None) -> TableLimits:
    limits = TableLimits() if limits is None else limits
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or not 1 <= max_rows <= limits.max_rows:
        raise VoProtocolsError("MAX_ROWS_INVALID",
                               f"max_rows = {max_rows!r}: ammessi gli interi da 1 a {limits.max_rows} "
                               "(tetto di righe del modulo 13)",
                               params={"value": repr(max_rows), "maximum": limits.max_rows})
    return limits


def service_url(service: str, protocol: str, servers: ServerRegistry | None = None) -> str:
    """URL esplicito, oppure voce dell'elenco dei server con il protocollo richiesto (D14-9 punto 6)."""
    if isinstance(service, str) and service.startswith(("http://", "https://")):
        return service.rstrip("/") if protocol == "tap" else service
    entry = (ServerRegistry() if servers is None else servers).get(service)
    if entry.protocol != protocol:
        raise VoProtocolsError("SERVER_UNKNOWN", f"la voce {service!r} è un servizio {entry.protocol}, non "
                               f"{protocol}", server=service,
                               params={"reason": "wrong_protocol", "service": service, "found": entry.protocol,
                                       "wanted": protocol})
    return entry.url.rstrip("/") if protocol == "tap" else entry.url


def _icrs_degrees(center) -> tuple[float, float]:
    """Centro in gradi ICRS: la conversione è del modulo 10 (``SkyFrame.to``)."""
    if isinstance(center, SkyCoord):
        center = SkyFrame(center)
    if not isinstance(center, SkyFrame):
        raise TypeError("center deve essere uno SkyFrame del modulo 10 o un SkyCoord (frame e unità dichiarati)")
    icrs = center if center.frame_name == "icrs" else center.to("icrs")
    lon, lat = np.atleast_1d(icrs.lon.to_value(u.deg)), np.atleast_1d(icrs.lat.to_value(u.deg))
    if lon.size != 1:
        raise ValueError("center deve essere una sola posizione")
    return float(lon[0]), float(lat[0])


def _radius_degrees(radius) -> float:
    if not isinstance(radius, u.Quantity) or radius.unit.physical_type != "angle":
        raise TypeError("radius deve essere un angolo con unità (es. 10 * u.arcsec)")
    value = float(radius.to_value(u.deg))
    if not (np.isfinite(value) and value > 0):
        raise ValueError("radius deve essere positivo e finito")
    return value


def _parse_results(response: _Response, results_class, *, hint: str = ""):
    """Interpreta lo stato della risposta con ``pyvo`` (``QUERY_STATUS``); errore del servizio riportato."""
    http_status = dict(response.notes).get("HTTP_STATUS")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            votable = parse_votable(io.BytesIO(response.payload), verify="ignore")
            return results_class(votable, url=response.url), votable
    except pyvo.dal.DALQueryError as exc:
        message = str(exc)
        extra = hint if hint and _DURATION_WORDS.search(message) else ""
        if http_status is not None and (http_status.startswith("5") or http_status == "429"):
            raise VoProtocolsError("SERVICE_ERROR", f"{response.url}: HTTP {http_status}: {message}{extra}",
                                   url=response.url,
                                   params={"reason": "http_message_async_hint" if extra else "http_message",
                                           "url": response.url, "status": int(http_status),
                                           "message": message}) from exc
        text = f"{response.url}: il servizio ha rifiutato la richiesta: {message}{extra}"
        if results_class is pyvo.dal.TAPResults:
            raise VoProtocolsError("ADQL_INVALID", text, url=response.url, service_message=message,
                                   params={"reason": "service_rejected_async_hint" if extra else "service_rejected",
                                           "url": response.url, "detail": message}) from exc
        raise VoProtocolsError("SERVICE_ERROR", text, url=response.url, service_message=message,
                               params={"reason": "service_rejected", "url": response.url,
                                       "detail": message}) from exc
    except Exception as exc:
        if http_status is not None:
            raise VoProtocolsError("SERVICE_ERROR", f"{response.url}: risposta HTTP {http_status} senza VOTable",
                                   url=response.url,
                                   params={"reason": "http_no_votable", "url": response.url,
                                           "status": int(http_status)}) from exc
        raise VoProtocolsError("VOTABLE_INVALID", f"{response.url}: risposta non leggibile come VOTable ({exc})",
                               url=response.url,
                               params={"reason": "unreadable_response", "url": response.url,
                                       "detail": str(exc)}) from exc


def _limited(result: CatalogTable, max_rows: int, service_overflow: bool) -> tuple[CatalogTable, tuple, bool]:
    """Dichiara sempre il superamento di ``max_rows`` (``ROW_LIMIT_EXCEEDED``), mai una riduzione silenziosa."""
    received = result.rows
    if received > max_rows:
        cut = dataclasses.replace(result, table=result.table[:max_rows],
                                  history=result.history + (f"prime {max_rows} righe di {received} ricevute",))
        return cut, (ModuleWarning("ROW_LIMIT_EXCEEDED", f"ricevute {received} righe, restituite le prime "
                                   f"{max_rows} (max_rows = {max_rows})",
                                   {"reason": "cut", "received": received, "max_rows": max_rows}),), True
    if service_overflow:
        return result, (ModuleWarning("ROW_LIMIT_EXCEEDED", f"il servizio ha troncato il risultato a {received} "
                                      f"righe (max_rows = {max_rows}, stato OVERFLOW)",
                                      {"reason": "service_overflow", "received": received, "max_rows": max_rows}),), True
    return result, (), False


def _finish(protocol: str, command: str, arguments: dict, response: _Response, parsed, *, max_rows: int,
            limits: TableLimits, cache: SharedCache | None) -> VoResult:
    results, votable = parsed
    result = _read_payload(response, limits=limits)
    overflow = getattr(results, "query_status", None) == "OVERFLOW"
    result, row_notes, truncated = _limited(result, max_rows, overflow)
    notes = response.notes + row_notes + _store(response, protocol, cache)
    notes = tuple(n for n in notes if n[0] != "HTTP_STATUS")
    return VoResult(table=result, request=_record(protocol, command, arguments, response, result.rows),
                    warnings=notes, truncated=truncated, max_rows=max_rows, descriptors=_descriptors(votable, response.payload))


def cone_search(center, radius, catalog: str, *, max_rows: int = DEFAULT_MAX_ROWS,
                servers: ServerRegistry | None = None, limits: TableLimits | None = None, cache: SharedCache | None = None, refresh: bool = False,
                timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> VoResult:
    """Cone search (SCS): ``catalog`` è una voce dell'elenco dei server o un URL SCS (D14-9 punto 6)."""
    limits = _check_max_rows(max_rows, limits)
    url = service_url(catalog, "scs", servers)
    ra, dec = _icrs_degrees(center)
    sr = _radius_degrees(radius)
    query = pyvo.dal.scs.SCSQuery(url, (ra, dec), sr)
    response = _http("scs", url, dict(query), cache=cache, refresh=refresh, timeouts=timeouts,
                     accept_error_body=True)
    results = _parse_results(response, pyvo.dal.SCSResults)
    arguments = {"center": {"ra_deg": ra, "dec_deg": dec, "frame": "icrs"}, "radius": {"value": sr, "unit": "deg"},
                 "catalog": catalog, "max_rows": max_rows}
    return _finish("scs", "cone_search", arguments, response, results, max_rows=max_rows, limits=limits, cache=cache)


def tap_query(url: str, adql: str, *, max_rows: int = DEFAULT_MAX_ROWS, mode: str = "sync",
              async_timeout: float = DEFAULT_ASYNC_TIMEOUT, servers: ServerRegistry | None = None,
              limits: TableLimits | None = None,
              cache: SharedCache | None = None, refresh: bool = False,
              timeouts: NetworkTimeouts = NETWORK_TIMEOUTS, cancel=None, use_stale_cache: bool = True) -> VoResult:
    """Esegue ADQL su un servizio TAP: sincrona di default, asincrona su richiesta (D14-9 punto 8).

    I commenti ``--`` si tolgono prima dell'invio (``adql_to_send``): ``adql`` scritto negli argomenti registrati,
    testo inviato nella ``QUERY``. ``cancel`` (funzione senza argomenti, vera se chi chiama ha annullato) vale solo
    in asincrona: lavoro interrotto ed eliminato, ``QUERY_CANCELLED`` (sprint B3).

    Una voce dell'elenco con mirror verificati (``SERVICE_MIRRORS``) passa al mirror per le cause di
    ``is_failover_error`` (14 §3, sprint B4); ``RequestRecord.url`` è il server che ha risposto. Con
    ``use_stale_cache=False`` un servizio giù non restituisce la sua copia vecchia in cache."""
    check = validate_adql(adql)
    if not check.valid:  # nessuna chiamata di rete inutile (T4)
        raise VoProtocolsError("ADQL_INVALID", f"{check.message} (carattere {check.position})",
                               position=check.position, params=_adql_params(check))
    limits = _check_max_rows(max_rows, limits)
    if mode not in ("sync", "async"):
        raise ValueError("mode deve essere 'sync' o 'async'")
    if not (isinstance(async_timeout, (int, float)) and async_timeout > 0):
        raise ValueError("async_timeout deve essere un numero di secondi positivo")
    bases = service_servers(url, servers)
    arguments = {"url": url, "adql": adql, "max_rows": max_rows, "mode": mode}
    if mode == "async":
        arguments["async_timeout"] = async_timeout
    sent = adql_to_send(adql)
    hint = _ASYNC_HINT if mode == "sync" else ""

    def request_key(base: str) -> tuple[str, dict]:
        query = pyvo.dal.tap.TAPQuery(base, sent, mode=mode, maxrec=max_rows)
        return (query.queryurl if mode == "sync" else f"{base}/async"), dict(query)

    def attempt(base: str, fresh: bool, stale: bool):
        if mode == "sync":
            target, params = request_key(base)
            response = _http("tap", target, params, method="POST", cache=cache, refresh=fresh,
                             timeouts=timeouts, accept_error_body=True, hint=_ASYNC_HINT, use_stale=stale)
        else:
            response = _tap_async(base, sent, max_rows, async_timeout, cache=cache, refresh=fresh,
                                  timeouts=timeouts, cancel=cancel, use_stale=stale)
        return response, _parse_results(response, pyvo.dal.TAPResults, hint=hint)

    mirrors = SERVICE_MIRRORS.get(url) if not _is_url(url) else None
    if mirrors is None or len(bases) == 1:
        response, parsed = attempt(bases[0], refresh, use_stale_cache)
        notes: tuple = ()
    else:
        def cached(base: str, exc=None):
            target, params = request_key(base)
            response = _cached_response("tap", "POST", target, params, cache, exc)
            return None if response is None else (response, _parse_results(response, pyvo.dal.TAPResults))

        (response, parsed), notes = _with_mirrors(mirrors, bases, attempt, cached, refresh=refresh,
                                                  use_stale_cache=use_stale_cache)
    result = _finish("tap", "tap_query", arguments, response, parsed, max_rows=max_rows, limits=limits, cache=cache)
    return dataclasses.replace(result, warnings=tuple(notes) + result.warnings) if notes else result


#: Intervallo massimo tra due controlli dell'annullamento durante l'attesa di un lavoro asincrono (s, sprint B3).
_CANCEL_POLL = 0.25


def _cancelled_job(job, url: str, phase) -> VoProtocolsError:
    """Lavoro annullato da chi chiama: ``ABORT`` (l'eliminazione è nel ``finally`` di ``_tap_async``)."""
    try:
        job.abort()
    except (pyvo.dal.DALServiceError, requests.exceptions.RequestException):
        pass  # l'eliminazione che segue basta: il servizio non deve tenere il lavoro
    return VoProtocolsError("QUERY_CANCELLED", f"{url}: lavoro annullato (fase {phase}); interrotto ed eliminato",
                            url=url, params={"reason": "async_aborted", "url": url, "phase": str(phase)})


def _tap_async(base: str, adql: str, max_rows: int, async_timeout: float, *, cache, refresh,
               timeouts: NetworkTimeouts, cancel=None, use_stale: bool = True) -> _Response:
    """Lavoro UWS con ``pyvo``: attesa massima complessiva ``async_timeout`` s, poi interruzione; ``cancel``
    controllato almeno ogni ``_CANCEL_POLL`` s (sprint B3)."""
    stopped = (lambda: False) if cancel is None else cancel
    params = dict(pyvo.dal.tap.TAPQuery(base, adql, mode="async", maxrec=max_rows))
    url = f"{base}/async"
    canonical = _canonical(params)
    cache = SharedCache() if cache is None else cache
    rows = cache.table(_CACHE_MODULE, _QUERY_TABLE, _QUERY_COLUMNS)
    cached = rows.get(_cache_key("tap", "POST", url, canonical))
    if cached is not None and not refresh:
        return _Response(cached.data["payload"], url, "POST", canonical, cached.retrieved_at, True,
                         (ModuleWarning("FROM_CACHE", f"copia in cache di {cached.origin}, scaricata il "
                                        f"{_iso(cached.retrieved_at)}",
                                        {"reason": "cached_origin", "origin": cached.origin,
                                         "retrieved_at": _iso(cached.retrieved_at)}),))
    deadline = time.monotonic() + async_timeout
    session = _Session(timeouts)
    try:
        job = pyvo.dal.AsyncTAPJob.create(base, adql, maxrec=max_rows, session=session)
        try:
            if stopped():
                raise _cancelled_job(job, url, job.phase)
            job.run()
            interval = 0.2
            while (phase := job.phase) not in ("COMPLETED", "ERROR", "ABORTED"):
                if stopped():
                    raise _cancelled_job(job, url, phase)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    job.abort()
                    raise VoProtocolsError("NET_TIMEOUT", f"{url}: attesa massima di {async_timeout:g} s superata "
                                           f"(fase {phase}); lavoro interrotto", url=url,
                                           params={"reason": "async_deadline", "url": url,
                                                   "timeout": _q(async_timeout, "s"), "phase": str(phase)})
                wake = time.monotonic() + min(interval, remaining)
                while (left := wake - time.monotonic()) > 0 and not stopped():
                    time.sleep(min(left, _CANCEL_POLL))
                interval = min(interval * 1.5, 10.0)
            if phase != "COMPLETED":
                try:
                    job.raise_if_error()
                except pyvo.dal.DALQueryError as exc:
                    raise VoProtocolsError("ADQL_INVALID", f"{url}: il servizio ha rifiutato la richiesta: {exc}",
                                           url=url, service_message=str(exc),
                                           params={"reason": "service_rejected", "url": url,
                                                   "detail": str(exc)}) from exc
                raise VoProtocolsError("SERVICE_ERROR", f"{url}: lavoro terminato in fase {phase}", url=url,
                                       params={"reason": "job_phase", "url": url, "phase": str(phase)})
            response = session.get(job.result_uri)
            _check_http(response, url)
            if not response.ok:
                raise VoProtocolsError("SERVICE_ERROR", f"{job.result_uri}: risposta HTTP {response.status_code}",
                                       url=url, params={"reason": "job_result_status", "uri": str(job.result_uri),
                                                        "status": response.status_code})
            payload = response.content
        finally:
            try:
                job.delete()
            except (pyvo.dal.DALServiceError, requests.exceptions.RequestException):
                pass  # il servizio elimina comunque i lavori scaduti
    except (requests.exceptions.RequestException, pyvo.dal.DALServiceError) as exc:
        if cached is not None and use_stale:
            return _Response(cached.data["payload"], url, "POST", canonical, cached.retrieved_at, True,
                             (_network_cached(exc, cached),))
        raise _net_error(url, exc, timeouts) from exc
    finally:
        session.close()
    return _Response(payload, url, "POST", canonical, datetime.now(UTC), False)


# --------------------------------------------------------------------------
# Ripiego sui mirror dei servizi del CDS (sprint B4, 14 §3, D14-14, D14-15)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceMirrors:
    """Mirror verificati di un servizio del CDS: chiave dello stato, nome mostrato, URL dei mirror in ordine."""

    service: str  # chiave dello stato di sessione (stessa per le funzioni che usano lo stesso servizio)
    label: str
    mirrors: tuple[str, ...]


#: Mirror verificati con richieste reali il 2026-11-07 (14 §3, tabella dei mirror). TAPVizieR, fotometria di
#: VizieR, MocServer e XMatch non hanno copie verificate: non sono qui.
SERVICE_MIRRORS: dict[str, ServiceMirrors] = {
    "cds-simbad-tap": ServiceMirrors("simbad", "SIMBAD", ("https://simbad.harvard.edu/simbad/sim-tap",)),
}
#: Server di ``astroquery.simbad`` per la regione del puntatore, nello stesso ordine della voce ``cds-simbad-tap``.
SIMBAD_SERVERS: tuple[str, ...] = ("simbad.cds.unistra.fr", "simbad.harvard.edu")
_SIMBAD_STATE = SERVICE_MIRRORS["cds-simbad-tap"]

_MIRROR_LOCK = threading.Lock()
_MIRROR_IN_USE: dict[str, int] = {}  # servizio → indice del server in uso (sessione dell'app)
_MIRROR_ANNOUNCED: set[str] = set()  # servizi per cui SERVICE_MIRROR_FALLBACK è già stato emesso


def _is_url(service: object) -> bool:
    return isinstance(service, str) and service.startswith(("http://", "https://"))


def _in_strasbourg(url: str) -> bool:
    host = requests.utils.urlparse(url).hostname or ""
    return host.endswith(("unistra.fr", "u-strasbg.fr"))


def service_servers(service: str, servers: ServerRegistry | None = None) -> tuple[str, ...]:
    """Server TAP di una voce in ordine: il principale, poi i mirror verificati (prima quelli fuori da Strasburgo,
    D14-14 c). Un URL o una voce senza mirror: solo quello."""
    principal = service_url(service, "tap", servers)
    entry = None if _is_url(service) else SERVICE_MIRRORS.get(service)
    if entry is None:
        return (principal,)
    ordered = sorted(entry.mirrors, key=_in_strasbourg)  # stabile: fuori da Strasburgo prima
    out = [principal]
    for url in ordered:
        if url.rstrip("/") not in {u.rstrip("/") for u in out}:
            out.append(url.rstrip("/"))
    return tuple(out)


def current_server(service: str) -> int:
    """Indice del server in uso del servizio (chiave di ``ServiceMirrors.service``) nella sessione: 0 = principale."""
    with _MIRROR_LOCK:
        return _MIRROR_IN_USE.get(service, 0)


def reset_mirror_state() -> None:
    """Riporta tutti i servizi sul principale e riemette l'avviso al prossimo cambio (test, nuova sessione)."""
    with _MIRROR_LOCK:
        _MIRROR_IN_USE.clear()
        _MIRROR_ANNOUNCED.clear()


def _http_status_of(exc) -> int | None:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def is_failover_error(exc: BaseException) -> bool:
    """Vero per le cause del cambio di server (D14-14 a): timeout o connessione, HTTP 5xx o 429, risposta non
    valida. Mai per 404 o altri 4xx, ADQL rifiutata, nessun risultato o errori di chi chiama."""
    if isinstance(exc, VoProtocolsError):
        params = exc.params or {}
        reason, status = params.get("reason"), params.get("status")
        if exc.code == "NET_TIMEOUT":
            return reason != "async_deadline"
        if exc.code == "SERVICE_ERROR":
            return isinstance(status, int) and (status >= 500 or status == 429)
        if exc.code == "VOTABLE_INVALID":
            return reason == "unreadable_response"
        return False
    if isinstance(exc, requests.exceptions.HTTPError):
        status = _http_status_of(exc)
        return status is None or status >= 500 or status == 429
    if isinstance(exc, pyvo.dal.DALServiceError):
        status = getattr(exc, "code", None)
        return not isinstance(status, int) or status >= 500 or status == 429
    return isinstance(exc, (requests.exceptions.RequestException, OSError))


def _fallback_reason(exc) -> dict:
    """Sotto-voce di ``SERVICE_MIRROR_FALLBACK`` dalla causa del guasto del principale."""
    status = (exc.params or {}).get("status") if isinstance(exc, VoProtocolsError) else _http_status_of(exc)
    if isinstance(exc, pyvo.dal.DALServiceError) and isinstance(getattr(exc, "code", None), int):
        status = exc.code
    if isinstance(status, int):
        return {"reason": "http_status", "status": status}
    if isinstance(exc, VoProtocolsError) and exc.code == "VOTABLE_INVALID":
        return {"reason": "invalid_response"}
    return {"reason": "network"}


def _fallback_warning(entry: ServiceMirrors, primary: str, mirror: str, cause) -> ModuleWarning:
    params = {"service": entry.label, "primary": primary, "mirror": mirror, **_fallback_reason(cause)}
    why = {"network": "non raggiungibile", "invalid_response": "risposta non valida"}.get(
        params["reason"], f"HTTP {params.get('status')}")
    return ModuleWarning("SERVICE_MIRROR_FALLBACK", f"{entry.label}: server {primary} {why}; risponde il mirror "
                         f"{mirror} (per il resto della sessione)", params)


def _all_servers_down(entry: ServiceMirrors, tried: Sequence[str], last: VoProtocolsError) -> VoProtocolsError:
    """``NET_TIMEOUT`` (``service_servers``) con il numero dei server provati e l'ultimo errore (D14-14 e)."""
    return VoProtocolsError("NET_TIMEOUT", f"{entry.label}: nessun server risponde (provati {len(tried)}: "
                            f"{', '.join(tried)}); ultimo errore {last.code}: {last.message}",
                            params={"reason": "service_servers", "service": entry.label, "servers": len(tried),
                                    "tried": list(tried), "last": _message_of(last)})


def _with_mirrors(entry: ServiceMirrors, servers: Sequence[str], attempt, cached, *, refresh: bool,
                  use_stale_cache: bool = True, as_error=None):
    """Prova i server di un servizio con le regole del 14 §3: prima la cache di tutti (senza ``refresh``), poi la
    rete dal server in uso (dal principale con ``refresh``) senza copie vecchie, poi la prima copia in cache.

    ``attempt(server, refresh, stale)`` → risultato o eccezione; ``cached(server, exc)`` → risultato dalla cache o
    ``None``; ``as_error(server, exc)`` → ``VoProtocolsError`` per gli errori che non lo sono già.
    Restituisce ``(risultato, avvisi)``; gli errori che non sono cause di cambio salgono subito."""
    if not refresh and cached is not None:
        for server in servers:
            hit = cached(server, None)
            if hit is not None:
                return hit, ()
    start = 0 if refresh else current_server(entry.service)
    failures: list[tuple[str, BaseException]] = []
    for index in range(start, len(servers)):
        try:
            result = attempt(servers[index], refresh, False)
        except Exception as exc:  # noqa: BLE001 - solo le cause di cambio passano oltre
            if not is_failover_error(exc):
                raise
            failures.append((servers[index], exc))
            continue
        notes: tuple = ()
        with _MIRROR_LOCK:
            _MIRROR_IN_USE[entry.service] = index
            announce = index > 0 and entry.service not in _MIRROR_ANNOUNCED
            if announce:
                _MIRROR_ANNOUNCED.add(entry.service)
        if announce:
            cause = failures[0][1] if failures else None
            notes = (_fallback_warning(entry, servers[0], servers[index], cause),)
        return result, notes
    last = failures[-1][1]
    if use_stale_cache and cached is not None:
        for server in servers:
            hit = cached(server, last)
            if hit is not None:
                return hit, ()
    if not isinstance(last, VoProtocolsError):
        last = as_error(failures[-1][0], last) if as_error is not None else _net_error(
            failures[-1][0], last, NETWORK_TIMEOUTS)
    tried = [server for server, _ in failures]
    if start > 0:  # server saltati perché già caduti in questa sessione: contano tra i provati
        tried = list(servers[:start]) + tried
    raise _all_servers_down(entry, tried, last) from failures[-1][1]


def _cached_response(protocol: str, method: str, url: str, params, cache: SharedCache | None,
                     exc: BaseException | None = None) -> _Response | None:
    """Risposta in cache di una richiesta (senza rete), con ``FROM_CACHE`` (``network_cached`` se ``exc``)."""
    canonical = _canonical(params)
    cache = SharedCache() if cache is None else cache
    rows = cache.table(_CACHE_MODULE, _QUERY_TABLE, _QUERY_COLUMNS)
    cached = rows.get(_cache_key(protocol, method, url, canonical))
    if cached is None:
        return None
    note = _network_cached(exc, cached) if exc is not None else ModuleWarning(
        "FROM_CACHE", f"copia in cache di {cached.origin}, scaricata il {_iso(cached.retrieved_at)}",
        {"reason": "cached_origin", "origin": cached.origin, "retrieved_at": _iso(cached.retrieved_at)})
    return _Response(cached.data["payload"], url, method, canonical, cached.retrieved_at, True, (note,))


# --------------------------------------------------------------------------
# P4 — Elenco dei server (D14-4), registro VO, DataLink (D14-3)
# --------------------------------------------------------------------------

#: Protocolli delle voci dell'elenco dei server.
PROTOCOLS: tuple[str, ...] = ("scs", "tap", "sia", "sia2", "ssa")
_STANDARD_IDS = {
    "scs": ("ivo://ivoa.net/std/conesearch",),
    "tap": ("ivo://ivoa.net/std/tap",),
    "sia": ("ivo://ivoa.net/std/sia",),
    "sia2": ("ivo://ivoa.net/std/sia#query-2.",),
    "ssa": ("ivo://ivoa.net/std/ssa",),
}
_VERIFIED = "2026-10-10"


@dataclass(frozen=True)
class ServerEntry:
    """Voce dell'elenco dei server: protocollo, URL ed ente dichiarati, con la fonte dell'URL."""

    id: str
    name: str
    provider: str
    protocol: str
    url: str
    source: str  # pagina ufficiale dell'ente che riporta l'URL, o "personale"/"registro VO"
    verified: str | None = None  # data della verifica sulla pagina ufficiale e del servizio in linea
    personal: bool = False


#: Elenco nostro (D14-4): ogni URL letto sulla pagina ufficiale dell'ente e provato in linea il 2026-10-10.
BUILTIN_SERVERS: tuple[ServerEntry, ...] = (
    ServerEntry("cds-simbad-tap", "SIMBAD", "CDS", "tap", "https://simbad.cds.unistra.fr/simbad/sim-tap",
                "https://cds.unistra.fr/help/documentation/simbad-more/adql-simbad/", _VERIFIED),
    ServerEntry("cds-vizier-tap", "VizieR (TAPVizieR)", "CDS", "tap", "https://tapvizier.cds.unistra.fr/TAPVizieR/tap",
                "https://cds.unistra.fr/news/2013/01/15-tapvizier-is-available", _VERIFIED),
    ServerEntry("esa-gaia-tap", "Archivio Gaia", "ESA", "tap", "https://gea.esac.esa.int/tap-server/tap",
                "https://www.cosmos.esa.int/web/gaia-users/archive/programmatic-access", _VERIFIED),
    ServerEntry("nasa-irsa-tap", "IRSA", "NASA/IPAC", "tap", "https://irsa.ipac.caltech.edu/TAP",
                "https://irsa.ipac.caltech.edu/docs/program_interface/TAP.html", _VERIFIED),
    ServerEntry("nasa-irsa-allwise-scs", "IRSA AllWISE (sorgenti)", "NASA/IPAC", "scs",
                "https://irsa.ipac.caltech.edu/SCS?table=allwise_p3as_psd",
                "https://irsa.ipac.caltech.edu/docs/program_interface/TAP.html", _VERIFIED),
    ServerEntry("nasa-irsa-sia2", "IRSA immagini (SIA 2)", "NASA/IPAC", "sia2", "https://irsa.ipac.caltech.edu/SIA",
                "https://irsa.ipac.caltech.edu/ibe/sia.html", _VERIFIED),
    ServerEntry("nasa-heasarc-tap", "HEASARC", "NASA/GSFC", "tap", "https://heasarc.gsfc.nasa.gov/xamin/vo/tap",
                "https://heasarc.gsfc.nasa.gov/docs/archive/vo/", _VERIFIED),
    ServerEntry("nasa-mast-caom-tap", "MAST CAOM", "NASA/STScI", "tap", "https://mast.stsci.edu/vo-tap/api/v0.1/caom",
                "https://mast.stsci.edu/vo-tap/", _VERIFIED),
    # Sprint C2 (D25-12 del 25): URL base letto sulla pagina ufficiale e servizio provato in linea il 2026-11-07.
    ServerEntry("nasa-exoplanet-tap", "NASA Exoplanet Archive", "NASA/IPAC (NExScI)", "tap",
                "https://exoplanetarchive.ipac.caltech.edu/TAP",
                "https://exoplanetarchive.ipac.caltech.edu/docs/TAP/usingTAP.html", "2026-11-07"),
)


@dataclass(frozen=True)
class RegistrySearch:
    """Esito di una ricerca nel registro VO: tabella RegTAP registrata e servizi trovati."""

    result: VoResult
    services: tuple[ServerEntry, ...]


#: Registro VO di default (RegTAP del GAVO in HTTPS, verificato il 2026-10-11, configurabile con
#: ``registry_url``): il default di ``pyvo`` (http://reg.g-vo.org/tap) non ha HTTPS valido.
DEFAULT_REGISTRY_URL = "https://dc.g-vo.org/tap"


class ServerRegistry:
    """Schede server (H10): elenco nostro più i server personali; ricerca nel registro VO."""

    def __init__(self, personal=()) -> None:
        self._personal: dict[str, ServerEntry] = {}
        for entry in personal:
            self.add_personal(entry.id, entry.name, entry.protocol, entry.url, provider=entry.provider)

    @property
    def builtin(self) -> tuple[ServerEntry, ...]:
        return BUILTIN_SERVERS

    def entries(self) -> tuple[ServerEntry, ...]:
        return BUILTIN_SERVERS + tuple(self._personal.values())

    def personal_servers(self) -> tuple[ServerEntry, ...]:
        """Server personali, da salvare nelle preferenze (``40``)."""
        return tuple(self._personal.values())

    def get(self, server_id: str) -> ServerEntry:
        for entry in self.entries():
            if entry.id == server_id:
                return entry
        known = ", ".join(e.id for e in self.entries())
        raise VoProtocolsError("SERVER_UNKNOWN", f"server {server_id!r} non in elenco (voci: {known})",
                               server=server_id,
                               params={"reason": "not_listed", "server": server_id,
                                       "known": [e.id for e in self.entries()]})

    def find(self, protocol: str | None = None, provider: str | None = None) -> tuple[ServerEntry, ...]:
        return tuple(e for e in self.entries()
                     if (protocol is None or e.protocol == protocol) and (provider is None or e.provider == provider))

    def add_personal(self, server_id: str, name: str, protocol: str, url: str, *,
                     provider: str = "personale") -> ServerEntry:
        if protocol not in PROTOCOLS:
            raise ValueError(f"protocollo {protocol!r}: ammessi {', '.join(PROTOCOLS)}")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ValueError(f"URL non valido: {url!r}")
        if not isinstance(server_id, str) or not server_id.strip():
            raise ValueError("serve un identificativo")
        if any(e.id == server_id for e in self.entries()):
            raise ValueError(f"identificativo {server_id!r} già in elenco")
        entry = ServerEntry(server_id, name, provider, protocol, url, "personale", None, personal=True)
        self._personal[server_id] = entry
        return entry

    def remove_personal(self, server_id: str) -> None:
        if server_id not in self._personal:
            raise VoProtocolsError("SERVER_UNKNOWN", f"{server_id!r} non è un server personale", server=server_id,
                                   params={"reason": "not_personal", "server": server_id})
        del self._personal[server_id]

    def search_registry(self, keywords, servicetype: str, *, max_rows: int = DEFAULT_MAX_ROWS,
                        registry_url: str | None = None,
                        cache: SharedCache | None = None, refresh: bool = False,
                        timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> RegistrySearch:
        """Ricerca nel registro VO (RegTAP): ADQL costruito da ``pyvo``, eseguito con ``tap_query``.

        ``registry_url`` di default ``DEFAULT_REGISTRY_URL`` (HTTPS)."""
        registry_url = DEFAULT_REGISTRY_URL if registry_url is None else registry_url
        if servicetype not in PROTOCOLS:
            raise ValueError(f"servicetype {servicetype!r}: ammessi {', '.join(PROTOCOLS)}")
        words = [keywords] if isinstance(keywords, str) else list(keywords)
        adql = pyvo.registry.regtap.get_RegTAP_query(keywords=words, servicetype=servicetype)
        result = tap_query(registry_url, adql, max_rows=max_rows, cache=cache, refresh=refresh, timeouts=timeouts)
        return RegistrySearch(result=result, services=_registry_services(result.table.table, servicetype))


_REGTAP_SEP = ":::py VO sep:::"


def _registry_services(table: Table, protocol: str) -> tuple[ServerEntry, ...]:
    """Interfacce standard del protocollo richiesto nelle righe RegTAP (liste aggregate da ``pyvo``)."""
    prefixes = _STANDARD_IDS[protocol]
    services = []
    for row in table:
        urls = str(row["access_urls"]).split(_REGTAP_SEP)
        stds = str(row["standard_ids"]).split(_REGTAP_SEP)
        roles = str(row["intf_roles"]).split(_REGTAP_SEP)
        for k, (url, std, role) in enumerate(zip(urls, stds, roles)):
            std_l = std.lower()
            if role != "std" or not url or not any(std_l.startswith(p) for p in prefixes):
                continue
            if protocol == "sia" and "#query-2." in std_l:
                continue
            services.append(ServerEntry(f"{row['ivoid']}#{k}", str(row["res_title"]), str(row["ivoid"]),
                                        protocol, url, "registro VO", None))
    return tuple(services)


@dataclass(frozen=True)
class ServiceParam:
    """Parametro d'ingresso di un descrittore di servizio (gruppo ``inputParams``)."""

    name: str
    ref: str | None  # ID del FIELD da cui prendere il valore, se riferito a una colonna
    ref_column: str | None  # nome della colonna con quell'ID
    value: str | None
    unit: str | None
    ucd: str | None
    datatype: str | None
    minimum: str | None = None
    maximum: str | None = None
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ServiceDescriptor:
    """Descrittore di servizio di un VOTable (``RESOURCE type="meta" utype="adhoc:service"``)."""

    id: str | None
    standard_id: str | None
    access_url: str
    params: tuple[ServiceParam, ...]

    @property
    def is_datalink(self) -> bool:
        return (self.standard_id or "").lower().startswith(pyvo.dal.adhoc.DATALINK_IVOID)


def _param_text(value) -> str | None:
    """Valore di un PARAM come testo; vuoto o mascherato (es. ``value=""`` per un array) → ``None``."""
    if value is None or np.ma.is_masked(value) or (isinstance(value, str) and not value):
        return None
    if isinstance(value, np.ndarray):
        return " ".join(str(v) for v in np.ravel(value))
    return str(value)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _raw_input_values(payload: bytes) -> dict[tuple[str | None, str], str]:
    """Testo originale dell'attributo ``value`` dei parametri d'ingresso dei descrittori.

    ``astropy`` converte ``value=""`` di un array numerico in zeri: il testo originale (letto con
    ``defusedxml``) dice se il valore è davvero vuoto.
    """
    raw: dict[tuple[str | None, str], str] = {}
    try:
        root = safe_fromstring(payload)
    except Exception:
        return raw
    for resource in root.iter():
        if _local(resource.tag) != "RESOURCE" or resource.get("utype") != "adhoc:service":
            continue
        for group in resource:
            if _local(group.tag) == "GROUP" and group.get("name") == "inputParams":
                for param in group:
                    if _local(param.tag) == "PARAM" and param.get("name") is not None:
                        raw[(resource.get("ID"), param.get("name"))] = param.get("value", "")
    return raw


def _descriptors(votable, payload: bytes = b"") -> tuple[ServiceDescriptor, ...]:
    """Descrittori di servizio del VOTable, letti con ``astropy`` (gruppi aggiunti da ``pyvo``)."""
    raw = _raw_input_values(payload) if payload else {}
    fields = {f.ID: f.name for t in votable.iter_tables() for f in t.fields if f.ID}
    out = []
    for resource in votable.iter_resources() if hasattr(votable, "iter_resources") else votable.resources:
        if resource.type != "meta" or resource.utype != "adhoc:service":
            continue
        top = {p.name: p for p in resource.params}
        if "accessURL" not in top:
            continue
        params = []
        for group in getattr(resource, "groups", []):
            if group.name != "inputParams":
                continue
            for entry in group.entries:
                if not hasattr(entry, "datatype"):
                    continue
                values = getattr(entry, "values", None)
                options = tuple(str(o[1]) for o in getattr(values, "options", []) or [])
                text = raw.get((resource.ID, entry.name))
                value = (text or None) if text is not None else _param_text(entry.value)
                params.append(ServiceParam(
                    name=entry.name, ref=entry.ref or None, ref_column=fields.get(entry.ref) if entry.ref else None,
                    value=value, unit=str(entry.unit) if entry.unit is not None else None, ucd=entry.ucd,
                    datatype=entry.datatype,
                    minimum=None if values is None or values.min is None else str(values.min),
                    maximum=None if values is None or values.max is None else str(values.max),
                    options=options))
        std = top.get("standardID")
        out.append(ServiceDescriptor(id=resource.ID, standard_id=None if std is None else str(std.value),
                                     access_url=str(top["accessURL"].value), params=tuple(params)))
    return tuple(out)


@dataclass(frozen=True)
class DataLinks:
    """Documento DataLink: tabella dei link (``CatalogTable``) e descrittori di servizio."""

    result: VoResult

    @property
    def table(self) -> CatalogTable:
        return self.result.table

    @property
    def descriptors(self) -> tuple[ServiceDescriptor, ...]:
        return self.result.descriptors

    def descriptor(self, service_def: str) -> ServiceDescriptor:
        """Descrittore citato dalla colonna ``service_def`` di un link."""
        for desc in self.descriptors:
            if desc.id == service_def:
                return desc
        raise VoProtocolsError("SERVICE_ERROR", f"descrittore {service_def!r} assente dal documento DataLink",
                               params={"reason": "descriptor_missing", "service_def": str(service_def)})


@dataclass(frozen=True)
class DataProduct:
    """Risposta di un servizio chiamato da un descrittore: byte, tipo dichiarato e richiesta registrata."""

    payload: bytes
    request: RequestRecord
    warnings: tuple[tuple[str, str], ...] = ()


_DATALINK_COLUMNS = ("ID", "access_url", "service_def", "error_message", "semantics", "description",
                     "content_type", "content_length")


class DataLinkClient:
    """Lettura e risoluzione dei link DataLink (H8, D14-3), con i descrittori di servizio, via ``pyvo``."""

    def __init__(self, *, cache: SharedCache | None = None, refresh: bool = False,
                 timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> None:
        self.cache, self.refresh, self.timeouts = cache, refresh, timeouts

    def links(self, url: str, *, max_rows: int = DEFAULT_MAX_ROWS) -> DataLinks:
        """Documento DataLink dall'URL (della colonna DataLink o di un descrittore): link e descrittori."""
        limits = _check_max_rows(max_rows, None)
        response = _http("datalink", url, cache=self.cache, refresh=self.refresh, timeouts=self.timeouts,
                         accept_error_body=True)
        parsed = _parse_results(response, pyvo.dal.adhoc.DatalinkResults)
        missing = [c for c in _DATALINK_COLUMNS if c not in [f.name for f in parsed[1].get_first_table().fields]]
        if missing:
            raise VoProtocolsError("VOTABLE_INVALID", f"{url}: documento DataLink senza le colonne {missing}",
                                   url=url, params={"reason": "datalink_columns", "url": url, "missing": missing})
        return DataLinks(_finish("datalink", "DataLinkClient.links", {"url": url, "max_rows": max_rows}, response,
                                 parsed, max_rows=max_rows, limits=limits, cache=self.cache))

    @staticmethod
    def service_descriptors(result: VoResult) -> tuple[ServiceDescriptor, ...]:
        return result.descriptors

    def call_service(self, descriptor: ServiceDescriptor, values: dict | None = None, **params) -> DataProduct:
        """Chiama il servizio descritto: parametri riferiti a colonne da ``values`` (nome colonna o ID),
        poi quelli dati dall'utente, poi i valori fissi del descrittore; parametri senza valore non si inviano."""
        values = values or {}
        query: dict[str, str] = {}
        names = {p.name for p in descriptor.params}
        unknown = sorted(set(params) - names)
        if unknown:
            raise ValueError(f"parametri non previsti dal descrittore: {unknown} (previsti: {sorted(names)})")
        for param in descriptor.params:
            if param.ref is not None:
                key = param.ref_column if param.ref_column in values else param.ref
                if key not in values:
                    raise ValueError(f"manca il valore della colonna {param.ref_column or param.ref!r} "
                                     f"per il parametro {param.name}")
                query[param.name] = str(values[key])
            elif param.name in params:
                query[param.name] = str(params[param.name])
            elif param.value is not None:
                query[param.name] = param.value
        response = _http("datalink-service", descriptor.access_url, query, cache=self.cache, refresh=self.refresh,
                         timeouts=self.timeouts)
        notes = response.notes + _store(response, "datalink-service", self.cache)
        arguments = {"descriptor": descriptor.id, "standard_id": descriptor.standard_id, "values": dict(values),
                     **params}
        return DataProduct(payload=response.payload,
                           request=_record("datalink-service", "DataLinkClient.call_service", arguments, response,
                                           None),
                           warnings=notes)


# --------------------------------------------------------------------------
# P5 — Immagini SIA/SIA2 (H23), IDHA, spettri SSA (E4)
# --------------------------------------------------------------------------


def _no_result(result: VoResult, note: ModuleWarning) -> VoResult:
    """Esito vuoto: avviso, non errore (§10)."""
    if result.table.rows:
        return result
    return dataclasses.replace(result, warnings=result.warnings + (note,))


def _time_interval(time) -> tuple[Time, Time]:
    if not (isinstance(time, (tuple, list)) and len(time) == 2 and all(isinstance(t, Time) for t in time)):
        raise TypeError("time deve essere una coppia (inizio, fine) di astropy.time.Time con scala dichiarata")
    start, end = time
    if start > end:
        raise ValueError("time: inizio dopo la fine")
    # SIA 2.0 (DALI): MJD in giorni sulla scala UTC; la conversione di scala è di astropy.time.
    return start.utc, end.utc


def _band_interval(band) -> u.Quantity:
    if not (isinstance(band, u.Quantity) and band.shape == (2,)):
        raise TypeError("band deve essere una Quantity di due valori (es. [400, 700] * u.nm)")
    try:
        meters = band.to(u.m, equivalencies=u.spectral())  # SIA 2.0: lunghezza d'onda osservata in metri
    except u.UnitConversionError as exc:
        raise TypeError(f"band: unità non spettrale ({band.unit})") from exc
    return np.sort(meters)


def sia_search(center, radius, *, version: int, service: str, band=None, time=None,
               max_rows: int = DEFAULT_MAX_ROWS, servers: ServerRegistry | None = None,
               limits: TableLimits | None = None, cache: SharedCache | None = None, refresh: bool = False,
               timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> VoResult:
    """Lista di immagini SIA (``version=1``) o SIA2 (``version=2``) con ``pyvo``; vuota → ``SIA_NO_RESULT``."""
    if version not in (1, 2):
        raise ValueError("version deve essere 1 (SIA) o 2 (SIA2)")
    if version == 1 and (band is not None or time is not None):
        raise ValueError("band e time sono parametri di SIA2 (version=2)")
    limits = _check_max_rows(max_rows, limits)
    protocol = "sia" if version == 1 else "sia2"
    url = service_url(service, protocol, servers)
    ra, dec = _icrs_degrees(center)
    r = _radius_degrees(radius)
    arguments = {"center": {"ra_deg": ra, "dec_deg": dec, "frame": "icrs"}, "radius": {"value": r, "unit": "deg"},
                 "version": version, "service": service, "max_rows": max_rows}
    if version == 1:
        # SIA 1: regione quadrata di lato SIZE; il lato 2 × raggio contiene tutto il cerchio richiesto.
        query = pyvo.dal.sia.SIAQuery(url, (ra, dec), 2 * r * u.deg)
        query["MAXREC"] = max_rows
        results_class = pyvo.dal.SIAResults
    else:
        kwargs = {}
        if band is not None:
            kwargs["band"] = tuple(_band_interval(band))
            arguments["band"] = {"min_m": float(kwargs["band"][0].value), "max_m": float(kwargs["band"][1].value)}
        if time is not None:
            start, end = _time_interval(time)
            kwargs["time"] = (start, end)
            arguments["time"] = {"start_mjd_utc": float(start.mjd), "end_mjd_utc": float(end.mjd)}
        query = pyvo.dal.sia2.SIA2Query(url, pos=(ra * u.deg, dec * u.deg, r * u.deg), maxrec=max_rows, **kwargs)
        results_class = pyvo.dal.SIA2Results
    response = _http(protocol, url, dict(query), cache=cache, refresh=refresh, timeouts=timeouts,
                     accept_error_body=True)
    try:
        parsed = _parse_results(response, results_class)
    except VoProtocolsError as exc:
        if exc.code == "VOTABLE_INVALID":
            raise VoProtocolsError("SIA_INVALID", exc.message, url=url,
                                   params={"cause": _message_of(exc)}) from exc
        raise
    result = _finish(protocol, "sia_search", arguments, response, parsed, max_rows=max_rows, limits=limits,
                     cache=cache)
    return _no_result(result, ModuleWarning("SIA_NO_RESULT", "nessuna immagine per i criteri dati"))


#: Sistemi di SIA 1.0 (VOX:STC_CoordRefFrame) tradotti in FITS WCS: assi e RADESYS; ECL e SGAL non tradotti
#: (lo standard non dice quale eclittica né il suo equinozio; il supergalattico non serve all'11).
_SIA_FRAMES = {"ICRS": ("RA", "DEC", "ICRS"), "FK5": ("RA", "DEC", "FK5"), "FK4": ("RA", "DEC", "FK4"),
               "GAL": ("GLON", "GLAT", None)}
_SIA_WCS_UCDS = {"projection": "vox:wcs_coordprojection", "crpix": "vox:wcs_coordrefpixel",
                 "crval": "vox:wcs_coordrefvalue", "cd": "vox:wcs_cdmatrix", "frame": "vox:stc_coordrefframe",
                 "equinox": "vox:stc_coordequinox", "naxis": "vox:image_naxis"}


@dataclass(frozen=True)
class SiaCalibration:
    """Calibrazione astrometrica di una riga della lista SIA 1 (D14-11), da dare a ``load_image`` dell'11.

    ``header`` è ``None`` se la riga non basta a costruirla, con il motivo in ``reason``."""

    header: fits.Header | None
    source: str
    columns: dict[str, str]
    reason: str | None = None


def _sia_cell(table: Table, index: int, name: str):
    value = table[name][index]
    if np.ma.is_masked(value):
        return None
    return value


def sia_calibration(result: VoResult, index: int) -> SiaCalibration:
    """Intestazione WCS dalle colonne ``VOX:WCS_*`` della riga ``index`` di una lista SIA 1 (D14-11).

    Colonne riconosciute dagli UCD di SIA 1.0 (§4.2 della raccomandazione IVOA): proiezione (3 caratteri),
    pixel di riferimento (= CRPIX, convenzione FITS), valori di riferimento (= CRVAL, gradi), matrice CD
    (ordine [1,1], [1,2], [2,1], [2,2]), sistema (ICRS, FK5, FK4, GAL), equinozio (FK5, FK4) e dimensioni.
    Ogni dato mancante → nessuna calibrazione, con il motivo; nulla è assunto. La validità è controllata
    con ``wcs_from_header`` del modulo 10."""
    table = result.table.table
    if result.request is None or result.request.protocol != "sia":
        raise ValueError("sia_calibration vale per le liste SIA 1 (version=1): SIA 2 non ha colonne WCS")
    if not 0 <= index < len(table):
        raise IndexError(f"riga {index} inesistente: la lista ha {len(table)} righe")
    source = f"lista SIA {result.request.url}, riga {index}"
    columns: dict[str, str] = {}
    for key, ucd in _SIA_WCS_UCDS.items():
        found = [n for n in table.colnames if (table[n].meta.get("ucd") or "").strip().lower() == ucd]
        if len(found) == 1:
            columns[key] = found[0]

    def unavailable(reason: str) -> SiaCalibration:
        return SiaCalibration(None, source, columns, reason)

    missing = [k for k in ("projection", "crpix", "crval", "cd", "frame", "naxis") if k not in columns]
    if missing:
        return unavailable(f"colonne VOX mancanti (o non univoche): {', '.join(_SIA_WCS_UCDS[k] for k in missing)}")
    values = {k: _sia_cell(table, index, n) for k, n in columns.items()}
    absent = [k for k in ("projection", "crpix", "crval", "cd", "frame", "naxis") if values[k] is None]
    if absent:
        return unavailable(f"valori mancanti nella riga: {', '.join(absent)}")
    projection = str(values["projection"]).strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", projection):
        return unavailable(f"proiezione {projection!r}: attesi tre caratteri come in FITS WCS")
    frame = str(values["frame"]).strip().upper()
    if frame not in _SIA_FRAMES:
        return unavailable(f"sistema {frame!r} non tradotto (tradotti: {', '.join(_SIA_FRAMES)})")
    try:
        crpix = np.asarray(values["crpix"], dtype=float).ravel()
        crval_col = table[columns["crval"]]
        crval = np.asarray(values["crval"], dtype=float).ravel()
        if crval_col.unit is not None:
            crval = (crval * crval_col.unit).to_value(u.deg)
        cd = np.asarray(values["cd"], dtype=float).ravel()
        naxis = np.asarray(values["naxis"], dtype=float).ravel()
    except (TypeError, ValueError, u.UnitsError) as exc:
        return unavailable(f"valori non numerici o unità non angolari: {exc}")
    if crpix.size != 2 or crval.size != 2 or cd.size != 4 or naxis.size < 2:
        return unavailable(f"dimensioni attese 2, 2, 4 e ≥ 2: trovate {crpix.size}, {crval.size}, {cd.size}, "
                           f"{naxis.size}")
    if naxis.size > 2 and np.any(naxis[2:] != 1):
        return unavailable(f"immagine con più di due assi utili ({naxis.astype(int).tolist()})")
    lon, lat, radesys = _SIA_FRAMES[frame]
    header = fits.Header()
    header["NAXIS"] = 2
    header["NAXIS1"], header["NAXIS2"] = int(naxis[0]), int(naxis[1])
    header["CTYPE1"] = f"{lon}{'-' * (5 - len(lon))}{projection}"
    header["CTYPE2"] = f"{lat}{'-' * (5 - len(lat))}{projection}"
    header["CRPIX1"], header["CRPIX2"] = float(crpix[0]), float(crpix[1])
    header["CRVAL1"], header["CRVAL2"] = float(crval[0]), float(crval[1])
    header["CUNIT1"] = header["CUNIT2"] = "deg"
    header["CD1_1"], header["CD1_2"], header["CD2_1"], header["CD2_2"] = (float(v) for v in cd)
    if radesys is not None:
        header["RADESYS"] = radesys
    if frame in ("FK5", "FK4"):
        equinox = values.get("equinox")
        if equinox is None:
            return unavailable(f"sistema {frame} senza equinozio (VOX:STC_CoordEquinox): mai assunto")
        try:
            header["EQUINOX"] = float(equinox)
        except (TypeError, ValueError):
            return unavailable(f"equinozio {equinox!r} non numerico")
    try:
        wcs_from_header(header)  # validazione con il modulo 10
    except CoordinatesWcsError as exc:
        return unavailable(f"calibrazione non valida ({exc.code}: {exc.message})")
    return SiaCalibration(header, source, columns)


def read_idha(path) -> None:
    """IDHA: nessuna documentazione pubblica (D14-9 punto 13); il file si apre in modo sicuro e si rifiuta."""
    text = os.fspath(path)
    try:
        safe_parse(text)
    except DefusedXmlException as exc:
        raise VoProtocolsError("XML_UNSAFE", f"{text}: costrutto XML pericoloso ({type(exc).__name__}); "
                               "nessun dato caricato", path=text,
                               params={"path": text, "construct": type(exc).__name__}) from exc
    except (XmlParseError, OSError) as exc:
        raise VoProtocolsError("IDHA_UNREADABLE", f"{text}: file non leggibile come XML ({exc})", path=text,
                               params={"reason": "xml_error", "path": text, "detail": str(exc)}) from exc
    raise VoProtocolsError("IDHA_UNREADABLE", f"{text}: formato IDHA non leggibile: nessuna documentazione pubblica "
                           "del formato (D14-9 punto 13); usare SIA o SIA2", path=text,
                           params={"reason": "format_unknown", "path": text})


def ssa_search(center, radius, *, service: str, max_rows: int = DEFAULT_MAX_ROWS,
               servers: ServerRegistry | None = None, limits: TableLimits | None = None,
               cache: SharedCache | None = None, refresh: bool = False,
               timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> VoResult:
    """Ricerca di spettri SSA 1.1 con ``pyvo`` (``SIZE`` = diametro = 2 × raggio); vuota → ``SSA_NO_RESULT``."""
    limits = _check_max_rows(max_rows, limits)
    url = service_url(service, "ssa", servers)
    ra, dec = _icrs_degrees(center)
    r = _radius_degrees(radius)
    query = pyvo.dal.ssa.SSAQuery(url, (ra, dec), diameter=2 * r * u.deg)
    query["MAXREC"] = max_rows
    response = _http("ssa", url, dict(query), cache=cache, refresh=refresh, timeouts=timeouts, accept_error_body=True)
    parsed = _parse_results(response, pyvo.dal.SSAResults)
    arguments = {"center": {"ra_deg": ra, "dec_deg": dec, "frame": "icrs"}, "radius": {"value": r, "unit": "deg"},
                 "service": service, "max_rows": max_rows}
    result = _finish("ssa", "ssa_search", arguments, response, parsed, max_rows=max_rows, limits=limits, cache=cache)
    return _no_result(result, ModuleWarning("SSA_NO_RESULT", "nessuno spettro per i criteri dati"))


@dataclass(frozen=True)
class Spectrum:
    """Spettro caricato (E4): asse spettrale e flusso con unità, metadati e provenienza; analisi nel 21."""

    table: Table  # colonne "spectral", "flux" ed eventualmente "flux_error"
    spectral_kind: str  # "wavelength", "frequency", "energy" o "wavenumber"
    columns: dict  # colonne d'origine usate per ogni asse
    format: str  # "votable" (Spectrum DM) o "fits"
    origin: str
    retrieved_at: datetime
    from_cache: bool
    body: str | None
    request: RequestRecord
    warnings: tuple[tuple[str, str], ...] = ()


_SPECTRAL_UCDS = {"em.wl": "wavelength", "em.freq": "frequency", "em.energy": "energy", "em.wavenumber": "wavenumber"}
_UTYPE_SPECTRAL = "data.spectralaxis.value"
_UTYPE_FLUX = "data.fluxaxis.value"
_UTYPE_ERROR = "data.fluxaxis.accuracy.staterror"


def _first_word(ucd: str | None) -> str:
    return (ucd or "").split(";")[0].strip().lower()


def _by_utype(table: Table, suffix: str) -> str | None:
    found = [n for n in table.colnames if str(table[n].meta.get("utype", "")).lower().endswith(suffix)]
    return found[0] if len(found) == 1 else None


def _by_ucd(table: Table, accept) -> list[str]:
    return [n for n in table.colnames if accept(_first_word(table[n].meta.get("ucd")))]


def _spectral_kind(table: Table, name: str) -> str:
    word = _first_word(table[name].meta.get("ucd"))
    if word in _SPECTRAL_UCDS:
        return _SPECTRAL_UCDS[word]
    unit = table[name].unit
    for kind, target in (("wavelength", u.m), ("frequency", u.Hz), ("energy", u.J), ("wavenumber", 1 / u.m)):
        if unit is not None and unit.is_equivalent(target):
            return kind
    return "unknown"


def _flatten_single_row(table: Table) -> Table:
    """FITS con una riga di colonne vettoriali (serializzazione diffusa degli spettri): una riga per campione."""
    if len(table) != 1 or not any(table[n].ndim > 1 for n in table.colnames):
        return table
    out = Table()
    for name in table.colnames:
        col = table[name]
        if col.ndim > 1:
            out[name] = np.asarray(col[0])
            out[name].unit, out[name].meta = col.unit, dict(col.meta)
    return out


def _spectrum_columns(table: Table, fmt: str, origin: str) -> tuple[str, str, str | None]:
    """Asse spettrale, flusso ed errore: utype dello Spectrum DM, poi (FITS) UCD; altrimenti ``SSA_INVALID``."""
    spectral, flux, error = _by_utype(table, _UTYPE_SPECTRAL), _by_utype(table, _UTYPE_FLUX), _by_utype(table, _UTYPE_ERROR)
    if fmt == "fits":
        if spectral is None:
            found = _by_ucd(table, lambda w: w in _SPECTRAL_UCDS)
            spectral = found[0] if len(found) == 1 else None
        if flux is None:
            found = _by_ucd(table, lambda w: w.startswith("phot.flux"))
            flux = found[0] if len(found) == 1 else None
        if error is None:
            found = [n for n in table.colnames if _first_word(table[n].meta.get("ucd")) == "stat.error"
                     and "phot.flux" in str(table[n].meta.get("ucd", "")).lower()]
            error = found[0] if len(found) == 1 else None
    if spectral is None or flux is None:
        how = "utype dello Spectrum DM" + (" o UCD (em.*, phot.flux*)" if fmt == "fits" else "")
        raise VoProtocolsError("SSA_INVALID", f"{origin}: asse spettrale o flusso non riconoscibili ({how}, una sola "
                               f"colonna per asse); colonne: {', '.join(table.colnames)}", url=origin,
                               params={"reason": "axes_dm_ucd" if fmt == "fits" else "axes_dm", "origin": origin,
                                       "columns": list(table.colnames)})
    for name in (spectral, flux):
        if table[name].unit is None:
            raise VoProtocolsError("SSA_INVALID", f"{origin}: colonna {name!r} senza unità valida", url=origin,
                                   params={"reason": "no_unit", "origin": origin, "column": name})
    return spectral, flux, error


def ssa_load(candidate, index: int | None = None, *, format: str | None = None, cache: SharedCache | None = None,
             refresh: bool = False, timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> Spectrum:
    """Carica lo spettro di un candidato di ``ssa_search`` (``candidate`` = risultato, ``index`` = riga)
    oppure da un URL di accesso; VOTable (Spectrum DM) o FITS tabellare, altrimenti ``SSA_INVALID``."""
    body = None
    if isinstance(candidate, VoResult):
        if index is None:
            raise ValueError("con un risultato di ssa_search serve index (la riga del candidato)")
        rows = candidate.table.table
        acref = _by_utype(rows, "access.reference") or next(iter(_by_ucd(rows, lambda w: w == "meta.ref.url")), None)
        if acref is None:
            raise VoProtocolsError("SSA_INVALID", "il risultato di ssa_search non ha la colonna di accesso "
                                   "(utype ssa:Access.Reference o UCD meta.ref.url)",
                                   params={"reason": "no_access_column"})
        url = str(rows[acref][index])
        fmt_col = _by_utype(rows, "access.format")
        declared = str(rows[fmt_col][index]) if fmt_col is not None else None
        body = candidate.table.body
    else:
        url, declared = candidate, format
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError(f"URL di accesso non valido: {url!r}")
    response = _http("ssa-spectrum", url, cache=cache, refresh=refresh, timeouts=timeouts)
    try:
        table = _read_payload(response)
    except CatalogsError as exc:
        raise VoProtocolsError("SSA_INVALID", f"{url}: spettro non leggibile ({exc.message})", url=url,
                               params={"reason": "unreadable", "url": url, "cause": _message_of(exc)}) from exc
    if table.format not in ("votable", "fits"):
        raise VoProtocolsError("SSA_INVALID", f"{url}: formato {table.format} (ammessi VOTable Spectrum DM e FITS)",
                               url=url, params={"reason": "format", "url": url, "format": table.format})
    data = _flatten_single_row(table.table)
    spectral, flux, error = _spectrum_columns(data, table.format, url)
    out = Table()
    out["spectral"] = data[spectral]
    out["flux"] = data[flux]
    if error is not None:
        out["flux_error"] = data[error]
    notes = response.notes + _store(response, "ssa-spectrum", cache)
    if body is None:
        notes += (ModuleWarning("BODY_UNKNOWN", "corpo non ricavabile: spettro caricato da URL senza il candidato "
                                "di ssa_search", {"reason": "spectrum_without_candidate"}),)
    if declared and table.format not in declared.lower() and not (table.format == "votable" and "xml" in declared):
        notes += (ModuleWarning("FORMAT_DECLARED", f"formato dichiarato {declared!r}, riconosciuto dal contenuto: "
                                f"{table.format}", {"reason": "recognized_differs", "declared": declared,
                                                    "recognized": table.format}),)
    arguments = {"url": url, "format": declared}
    return Spectrum(table=out, spectral_kind=_spectral_kind(data, spectral),
                    columns={"spectral": spectral, "flux": flux, "flux_error": error}, format=table.format,
                    origin=url, retrieved_at=response.retrieved_at, from_cache=response.from_cache, body=body,
                    request=_record("ssa-spectrum", "ssa_load", arguments, response, len(out)), warnings=notes)


# --------------------------------------------------------------------------
# P6 — Puntatore Simbad e fotometria VizieR (H17)
# --------------------------------------------------------------------------

#: Coordinate di SIMBAD: ICRS all'epoca J2000 (documentazione di SIMBAD, come nel modulo 10).
SIMBAD_COORDINATES_NOTE = "coordinate SIMBAD: ICRS all'epoca J2000 (documentazione di SIMBAD)"
#: Servizio fotometrico di VizieR (verificato il 2026-10-10 sulla documentazione del CDS e in linea).
VIZIER_PHOTOMETRY_URL = "https://vizier.cds.unistra.fr/viz-bin/sed"
_VIZIER_MAX_RADIUS = 30 * u.arcsec  # limite dichiarato dalla documentazione del servizio
_SIMBAD_FIELDS = ("otype", "nbref")  # nbref = "number of references" (colonne della tabella basic di SIMBAD)
#: Servizio TAP di SIMBAD per le magnitudini (voce dell'elenco dei server).
_SIMBAD_TAP = "cds-simbad-tap"
#: Colonna ``system`` della tabella ``flux`` di SIMBAD (TAP_SCHEMA, verificato il 2026-10-11: "A=AB V=Vega").
SIMBAD_FLUX_SYSTEMS = {"A": "AB", "V": "Vega"}


@dataclass(frozen=True)
class SimbadMagnitude:
    """Una magnitudine SIMBAD (D14-12): banda e sistema come dichiarati da SIMBAD, mai assunti."""

    band: str  # nome del filtro in SIMBAD (es. "V", "G")
    description: str | None  # descrizione del filtro (tabella filter, es. "Magnitude Gaia G")
    value: float
    error: float | None
    unit: str | None  # unità dichiarata dalla tabella filter (es. "mag")
    system: str | None  # "AB", "Vega" o None se SIMBAD non lo dichiara
    quality: str | None
    bibcode: str | None


@dataclass(frozen=True)
class SimbadObject:
    """Oggetto SIMBAD scelto dal puntatore, con tutte le magnitudini disponibili (D14-12)."""

    main_id: str
    otype: str | None
    coords: SkyFrame
    nbref: int | None
    separation: u.Quantity
    magnitudes: tuple[SimbadMagnitude, ...] = ()


@dataclass(frozen=True)
class SimbadPointer:
    """Esito del puntatore: oggetto più citato nel raggio (o nessuno), con fonte, data e avvisi."""

    object: SimbadObject | None
    candidates: int
    source: str
    request: RequestRecord
    warnings: tuple[tuple[str, str], ...] = ()
    magnitudes_request: RequestRecord | None = None  # interrogazione TAP delle magnitudini (D14-12)


def _adql_string(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _simbad_magnitudes(main_id: str, *, cache, refresh: bool, timeouts: NetworkTimeouts):
    """Tutte le magnitudini SIMBAD dell'oggetto (tabelle flux e filter), con banda e sistema dichiarati."""
    adql = ("SELECT f.filter, f.flux, f.flux_err, f.system, f.qual, f.bibcode, fl.description, fl.unit "
            "FROM flux AS f JOIN basic AS b ON f.oidref = b.oid "
            "LEFT OUTER JOIN filter AS fl ON f.filter = fl.filtername "
            f"WHERE b.main_id = {_adql_string(main_id)}")
    result = tap_query(_SIMBAD_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts)
    data = result.table.table

    def text(row, name):
        value = row[name]
        return None if np.ma.is_masked(value) or not str(value).strip() else str(value).strip()

    def number(row, name):
        """``float32`` del VOTable (colonne ``flux``, ``flux_err``) al decimale scritto da SIMBAD, come ``_cell``."""
        value = row[name]
        if np.ma.is_masked(value) or not np.isfinite(float(value)):
            return None
        return float(str(value)) if isinstance(value, np.float32) else float(value)

    magnitudes, notes = [], []
    for row in data:
        value = number(row, "flux")
        if value is None:
            continue
        code = text(row, "system")
        system = SIMBAD_FLUX_SYSTEMS.get(code) if code else None
        if code and system is None:
            notes.append(ModuleWarning(
                "SIMBAD_SYSTEM_UNKNOWN", f"banda {text(row, 'filter')}: codice di sistema {code!r} non documentato "
                "da SIMBAD, sistema non dichiarato", {"band": text(row, "filter") or "", "code": code}))
        magnitudes.append(SimbadMagnitude(band=text(row, "filter") or "", description=text(row, "description"),
                                          value=value, error=number(row, "flux_err"), unit=text(row, "unit"),
                                          system=system, quality=text(row, "qual"), bibcode=text(row, "bibcode")))
    magnitudes.sort(key=lambda m: (m.band, m.bibcode or ""))  # ordine stabile, indipendente dal servizio
    undeclared = [m.band for m in magnitudes if m.system is None]
    if undeclared:
        notes.append(ModuleWarning("SIMBAD_SYSTEM_UNDECLARED", "bande senza sistema dichiarato da SIMBAD: "
                                   f"{', '.join(undeclared)}", {"bands": undeclared}))
    return tuple(magnitudes), result, tuple(notes)


def _query_simbad_region(ra: float, dec: float, radius_deg: float, timeouts: NetworkTimeouts,
                         server: str = SIMBAD_SERVERS[0]) -> tuple[Table, str]:
    """Interroga SIMBAD con ``astroquery`` (sessione con i timeout comuni del modulo 10) sul server indicato
    (nome di ``astroquery.simbad``, sprint B4); (tabella, URL TAP)."""
    from astrotwo.core.coordinates_wcs import _simbad_with_timeouts  # unico punto con il campo interno di astroquery

    simbad = _simbad_with_timeouts(timeouts)
    simbad.server = server
    simbad.add_votable_fields(*_SIMBAD_FIELDS)
    center = SkyCoord(ra * u.deg, dec * u.deg, frame="icrs")
    return simbad.query_region(center, radius=radius_deg * u.deg), simbad.tap.baseurl


def _table_bytes(table: Table) -> bytes:
    from astropy.io.votable import from_table

    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from_table(table).to_xml(buffer)
    return buffer.getvalue()


def _simbad_label(url: str) -> str:
    """Nome del server SIMBAD che ha risposto (provenienza, sprint B4)."""
    return "SIMBAD (mirror di Harvard)" if "harvard" in (url or "") else "SIMBAD (CDS)"


def _simbad_region_error(url: str, exc: BaseException, timeouts: NetworkTimeouts) -> VoProtocolsError:
    """Errore di ``astroquery`` della regione del puntatore come ``VoProtocolsError`` (rete o stato HTTP)."""
    status = _http_status_of(exc)
    if isinstance(exc, pyvo.dal.DALServiceError) and isinstance(getattr(exc, "code", None), int):
        status = exc.code
    if isinstance(status, int):
        return VoProtocolsError("SERVICE_ERROR", f"{url}: risposta HTTP {status}", url=url, status=status,
                                params={"reason": "http_status", "url": url, "status": status,
                                        "status_text": " ".join(str(exc).split())[:200]})
    return _net_error(url, exc, timeouts)


def simbad_pointer(center, radius, *, cache: SharedCache | None = None, refresh: bool = False,
                   timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> SimbadPointer:
    """Oggetto SIMBAD più citato nel raggio; a pari citazioni il più vicino, dichiarato (D14-9 punto 15).

    Con l'oggetto, tutte le magnitudini disponibili in SIMBAD, ognuna con banda e sistema dichiarati
    (D14-12), da una seconda interrogazione TAP registrata in ``magnitudes_request``.

    ``radius`` è sempre esplicito: lo passa l'interfaccia (41), che ne decide il default (D14-9 punto 2).
    """
    ra, dec = _icrs_degrees(center)
    r = _radius_degrees(radius)
    params = {"ra_deg": f"{ra!r}", "dec_deg": f"{dec!r}", "radius_deg": f"{r!r}", "fields": ",".join(_SIMBAD_FIELDS)}
    canonical = _canonical(params)
    cache_obj = SharedCache() if cache is None else cache
    rows = cache_obj.table(_CACHE_MODULE, _QUERY_TABLE, _QUERY_COLUMNS)
    key = _cache_key("simbad", "astroquery", "simbad:query_region", canonical)
    cached = rows.get(key)
    notes: tuple = ()
    if cached is not None and not refresh:
        response = _Response(cached.data["payload"], cached.data["url"], "astroquery", canonical,
                             cached.retrieved_at, True, (_cached_since(cached),))
    else:
        servers = service_servers(_SIMBAD_TAP)  # principale e mirror verificati (14 §3, sprint B4)

        def attempt(url: str, fresh: bool, stale: bool):
            host = requests.utils.urlparse(url).netloc  # nome del server per astroquery (porta solo nei test)
            try:
                return _query_simbad_region(ra, dec, r, timeouts, host)
            except (requests.exceptions.RequestException, pyvo.dal.DALServiceError, OSError) as exc:
                raise _simbad_region_error(url, exc, timeouts) from exc

        try:
            (table, url), mirror_notes = _with_mirrors(_SIMBAD_STATE, servers, attempt, None, refresh=refresh,
                                                       use_stale_cache=False)
        except VoProtocolsError as exc:
            if cached is None or not is_failover_error(exc):
                raise
            response = _Response(cached.data["payload"], cached.data["url"], "astroquery", canonical,
                                 cached.retrieved_at, True,
                                 (_network_unavailable(exc),))
        else:
            notes += tuple(mirror_notes)
            response = _Response(_table_bytes(table), url, "astroquery", canonical, datetime.now(UTC), False)
            try:
                rows.put(key, {"protocol": "simbad", "url": url, "params": json.dumps(canonical),
                               "payload": response.payload}, origin=url, retrieved_at=response.retrieved_at)
            except CacheError as exc:
                notes += (ModuleWarning(exc.code, exc.message, getattr(exc, "params", None)),)
    found = _read_payload(response).table
    notes = response.notes + notes
    arguments = {"center": {"ra_deg": ra, "dec_deg": dec, "frame": "icrs"}, "radius": {"value": r, "unit": "deg"}}
    record = _record("simbad", "simbad_pointer", arguments, response, len(found))
    source = f"{_simbad_label(response.url)} via astroquery; {SIMBAD_COORDINATES_NOTE}"
    if len(found) == 0:
        return SimbadPointer(None, 0, source, record,
                             notes + (ModuleWarning("SIMBAD_NO_OBJECT", f"nessun oggetto SIMBAD entro {r * 3600:g} arcsec",
                                                    {"radius": _q(r, "deg")}),))
    ra_col = (found["ra"].quantity if found["ra"].unit is not None else None)
    if ra_col is None or found["dec"].unit is None:
        raise VoProtocolsError("SERVICE_ERROR", "SIMBAD: coordinate senza unità nella risposta",
                               params={"reason": "simbad_no_units"})
    from astropy.coordinates import angular_separation

    sep = angular_separation(ra * u.deg, dec * u.deg, ra_col, found["dec"].quantity).to(u.arcsec)
    nbref = np.ma.masked_invalid(np.ma.asarray(found["nbref"], dtype=float))
    valid = ~np.ma.getmaskarray(nbref)
    if valid.any():
        best = nbref[valid].max()
        tied = np.flatnonzero(valid & (np.ma.filled(nbref, -1) == best))
    else:
        tied = np.arange(len(found))
        notes += (ModuleWarning("SIMBAD_NBREF_MISSING", "numero di citazioni assente per tutti gli oggetti: scelto "
                                "il più vicino"),)
    order = sorted(tied, key=lambda k: (float(sep[k].value), str(found["main_id"][k])))
    choice = order[0]
    if len(tied) > 1:
        tie = {"count": len(tied), "main_id": str(found["main_id"][choice]),
               "separation": _q(sep[choice].value, "arcsec")}
        notes += (ModuleWarning("SIMBAD_TIE", f"{len(tied)} oggetti con lo stesso numero di citazioni "
                                f"({'—' if not valid.any() else int(best)}): scelto il più vicino al centro, "
                                f"{found['main_id'][choice]} a {sep[choice].value:.3f} arcsec",
                                {"reason": "nbref_missing", **tie} if not valid.any()
                                else {"nbref": int(best), **tie}),)
    row = found[choice]
    coords = SkyFrame.from_lonlat(float(ra_col[choice].to_value(u.deg)) * u.deg,
                                  float(found["dec"].quantity[choice].to_value(u.deg)) * u.deg, "icrs",
                                  epoch=Time("J2000.0"))
    otype = None if np.ma.is_masked(row["otype"]) else str(row["otype"])
    magnitudes, mag_result, mag_notes = _simbad_magnitudes(str(row["main_id"]), cache=cache, refresh=refresh,
                                                           timeouts=timeouts)
    notes += tuple(w for w in mag_result.warnings if w[0] in ("FROM_CACHE", "SERVICE_MIRROR_FALLBACK")) + mag_notes
    if not magnitudes:
        notes += (ModuleWarning("SIMBAD_NO_MAGNITUDE", f"nessuna magnitudine in SIMBAD per {row['main_id']}",
                                {"main_id": str(row["main_id"])}),)
    obj = SimbadObject(main_id=str(row["main_id"]), otype=otype, coords=coords,
                       nbref=None if not valid[choice] else int(nbref[choice]), separation=sep[choice],
                       magnitudes=magnitudes)
    return SimbadPointer(obj, len(found), source, record, notes, magnitudes_request=mag_result.request)


#: Colonne della tabella ``basic`` di SIMBAD lette da ``simbad_object`` (nomi e unità verificati il 2026-11-07 sul
#: mirror di Harvard); ``description`` viene da ``otypedef``.
SIMBAD_BASIC_COLUMNS: tuple[str, ...] = (
    "oid", "main_id", "otype", "sp_type", "sp_bibcode", "nbref", "ra", "dec", "coo_err_maj", "coo_err_min",
    "coo_err_angle", "coo_qual", "coo_bibcode", "plx_value", "plx_err", "plx_bibcode", "pmra", "pmdec", "pm_err_maj",
    "pm_err_min", "pm_err_angle", "pm_bibcode", "rvz_radvel", "rvz_err", "rvz_bibcode")


@dataclass(frozen=True)
class SimbadRecord:
    """Oggetto SIMBAD esatto di un identificativo (sprint C2, 14 §7): ``basic``, identificativi, magnitudini.

    ``basic``: nome di colonna → valore (``Quantity`` con l'unità dichiarata dal servizio, testo, intero o ``None``
    se vuoto); ``coords``: ICRS all'epoca J2000 (``SIMBAD_COORDINATES_NOTE``)."""

    identifier: str  # come scritto da chi chiama
    main_id: str
    oid: int
    basic: Mapping[str, object]
    otype_description: str | None
    coords: SkyFrame
    identifiers: tuple[str, ...]
    magnitudes: tuple[SimbadMagnitude, ...]
    source: str  # servizio che ha risposto (es. "SIMBAD (mirror di Harvard)")
    requests: tuple[RequestRecord, ...]  # basic, ident, flux
    warnings: tuple[tuple[str, str], ...] = ()


def _cell(row, name: str):
    """Valore di una cella: ``None`` se vuoto; ``Quantity`` se la colonna ha un'unità; tipo nativo altrimenti.

    Un ``float`` a 32 bit del VOTable torna al decimale scritto dal servizio (rappresentazione più corta del valore
    a 32 bit, es. ``1.0E-4`` e non ``9.99999975e-05``), poi in ``float64`` (DC6)."""
    value = row[name]
    if np.ma.is_masked(value):
        return None
    unit = row.columns[name].unit
    if isinstance(value, (bytes, str, np.str_, np.bytes_)):
        text = value.decode() if isinstance(value, bytes) else str(value)
        return text.strip() or None
    if isinstance(value, (np.integer, int)) and unit is None:
        return int(value)
    number = float(str(value)) if isinstance(value, np.float32) else float(value)  # float32: decimale scritto
    if not np.isfinite(number):
        return None
    return number * unit if unit is not None else number


def simbad_object(identifier: str, *, cache: SharedCache | None = None, refresh: bool = False,
                  timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> SimbadRecord:
    """L'oggetto SIMBAD esatto di un identificativo (mai il più citato), con il ripiego sul mirror (D14-14).

    SIMBAD confronta ``ident.id`` normalizzando maiuscole e spazi (verificato il 2026-11-07): l'identificativo si
    passa come scritto. Nessuna riga → ``NAME_NOT_FOUND`` (``simbad_identifier``), mai un ripiego; più oggetti →
    ``NAME_NOT_FOUND`` (``several_objects``), nessuna scelta."""
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("identifier deve essere un testo non vuoto")
    columns = ", ".join(f"b.{c}" for c in SIMBAD_BASIC_COLUMNS)
    adql = (f"SELECT {columns}, d.description FROM basic AS b JOIN ident AS i ON i.oidref = b.oid "
            "LEFT OUTER JOIN otypedef AS d ON d.otype = b.otype "
            f"WHERE i.id = {_adql_string(identifier.strip())}")
    basic = tap_query(_SIMBAD_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts)
    data = basic.table.table
    label = _simbad_label(basic.request.url)
    if len(data) == 0:
        raise VoProtocolsError("NAME_NOT_FOUND", f"'{identifier}' non trovato in {label}",
                               params={"reason": "simbad_identifier", "name": identifier, "service": label})
    if len({int(v) for v in data["oid"]}) > 1:
        raise VoProtocolsError("NAME_NOT_FOUND", f"'{identifier}' è ambiguo in {label}: indica più oggetti",
                               params={"reason": "several_objects", "name": identifier, "service": label})
    row = data[0]
    fields = {name: _cell(row, name) for name in SIMBAD_BASIC_COLUMNS}
    ra, dec = fields["ra"], fields["dec"]
    if not isinstance(ra, u.Quantity) or not isinstance(dec, u.Quantity):
        raise VoProtocolsError("SERVICE_ERROR", "SIMBAD: coordinate senza unità nella risposta",
                               params={"reason": "simbad_no_units"})
    coords = SkyFrame.from_lonlat(ra.to(u.deg), dec.to(u.deg), "icrs", epoch=Time("J2000.0"))
    oid = int(fields["oid"])
    idents = tap_query(_SIMBAD_TAP, f"SELECT id FROM ident WHERE oidref = {oid}", cache=cache, refresh=refresh,
                       timeouts=timeouts)
    names = sorted({str(v).strip() for v in idents.table.table["id"] if str(v).strip()})
    main_id = str(fields["main_id"])
    magnitudes, mag_result, mag_notes = _simbad_magnitudes(main_id, cache=cache, refresh=refresh, timeouts=timeouts)
    notes = tuple(basic.warnings) + tuple(
        w for result in (idents, mag_result) for w in result.warnings
        if w[0] in ("FROM_CACHE", "SERVICE_MIRROR_FALLBACK")) + tuple(mag_notes)
    return SimbadRecord(identifier=identifier, main_id=main_id, oid=oid, basic=fields,
                        otype_description=_cell(row, "description"), coords=coords, identifiers=tuple(names),
                        magnitudes=magnitudes, source=label,
                        requests=(basic.request, idents.request, mag_result.request), warnings=notes)


#: MocServer del CDS (D13-18): elenco delle collezioni VizieR con le loro proprietà (verificato il 2026-10-11).
MOCSERVER_URL = "https://alasky.cds.unistra.fr/MocServer/query"
#: Il MocServer dichiara le risposte JSON in ISO-8859-1 (``Content-Type: application/json;charset=ISO-8859-1``,
#: verificato il 2026-10-12: alcuni titoli contengono ad esempio "µm" in un byte, non UTF-8).
MOCSERVER_CHARSET = "iso-8859-1"
_MOCSERVER_FIELDS = "ID,obs_title,vizier_popularity"


@dataclass(frozen=True)
class MocServerRecords:
    """Record del MocServer (proprietà come stringhe, così come il servizio le dà) con la richiesta registrata."""

    records: tuple[dict, ...]
    request: RequestRecord
    warnings: tuple[tuple[str, str], ...] = ()


def vizier_collections(*, cache: SharedCache | None = None, refresh: bool = False,
                       timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> MocServerRecords:
    """Collezioni di cataloghi del CDS dal MocServer (ID, titolo, ``vizier_popularity``), per l'albero del 13."""
    params = {"expr": "ID=CDS/* && dataproduct_type=catalog", "get": "record", "fmt": "json",
              "fields": _MOCSERVER_FIELDS}
    try:
        response = _http("mocserver", MOCSERVER_URL, params, cache=cache, refresh=refresh, timeouts=timeouts)
    except VoProtocolsError as exc:
        if not is_failover_error(exc):
            raise
        # Nessuna copia del MocServer fuori da Strasburgo (14 §3, sprint B4): messaggio chiaro, nessun mirror.
        raise VoProtocolsError("NET_TIMEOUT", f"MocServer del CDS ({MOCSERVER_URL}) non raggiungibile e nessuna "
                               "copia locale dell'elenco delle collezioni; il MocServer non ha copie fuori da "
                               "Strasburgo. Gli identificativi scritti restano utilizzabili (Gaia DR3 e 2MASS "
                               f"con il ripiego sugli archivi originali): {exc.message}", url=MOCSERVER_URL,
                               params={"reason": "mocserver_no_mirror", "url": MOCSERVER_URL,
                                       "cause": _message_of(exc)}) from exc
    try:
        records = json.loads(response.payload.decode(MOCSERVER_CHARSET))
        if not isinstance(records, list) or not all(isinstance(r, dict) and isinstance(r.get("ID"), str)
                                                    for r in records):
            raise ValueError("attesa una lista di record con ID")
    except (UnicodeDecodeError, ValueError) as exc:
        raise VoProtocolsError("SERVICE_ERROR", f"{MOCSERVER_URL}: risposta non leggibile ({exc})",
                               url=MOCSERVER_URL,
                               params={"reason": "unreadable_response", "url": MOCSERVER_URL,
                                       "detail": str(exc)}) from exc
    notes = response.notes + _store(response, "mocserver", cache)
    record = _record("mocserver", "vizier_collections", {}, response, len(records))
    return MocServerRecords(records=tuple(records), request=record, warnings=notes)


#: Servizio CDS XMatch (modulo 15, D15-7): URL HTTPS (il default di astroquery è http://), verificato il 2026-10-11.
XMATCH_URL = "https://cdsxmatch.cds.unistra.fr/xmatch/api/v1/sync"
#: Limiti dichiarati dalla documentazione delle chiamate API del servizio (verificati il 2026-10-11).
XMATCH_MAX_DISTANCE = 180 * u.arcsec
XMATCH_MAX_UPLOAD_BYTES = 100 * 1000 * 1000  # "Total size of uploaded tables can not be larger than 100 MB"


def _upload_csv(table: Table) -> bytes:
    buffer = io.StringIO()
    table.write(buffer, format="ascii.csv")  # stessa scrittura di astroquery.xmatch per le tabelle caricate
    return buffer.getvalue().encode("utf-8")


def cds_xmatch(cat1: Table, cat2: Table, max_distance, selection: str, *, cache: SharedCache | None = None,
               refresh: bool = False, timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> VoResult:
    """Incrocio con il servizio CDS XMatch tramite ``astroquery.xmatch`` (per il modulo 15).

    ``cat1``/``cat2``: tabelle con colonne ``idx``, ``ra``, ``dec`` (gradi ICRS, preparate dal 15). URL HTTPS,
    timeout comuni di ``04``, cache di astroquery disattivata; risposta nella cache del 14 (chiave con l'impronta
    SHA-256 delle tabelle caricate) e letta con ``read_table`` del 13."""
    import hashlib

    from astroquery.exceptions import InvalidQueryError
    from astroquery.xmatch import XMatchClass

    if selection not in ("best", "all"):
        raise ValueError("selection: 'best' o 'all' (parametri del servizio)")
    distance = max_distance.to(u.arcsec)
    if not (0 < distance.value <= XMATCH_MAX_DISTANCE.value):
        raise VoProtocolsError("MAX_SEP_INVALID", f"max_distance {distance}: il servizio XMatch ammette (0, "
                               f"{XMATCH_MAX_DISTANCE}]",
                               params={"distance": _q(distance.value, "arcsec"),
                                       "maximum": _q(XMATCH_MAX_DISTANCE.value, "arcsec")})
    uploads = [_upload_csv(t) for t in (cat1, cat2)]
    if sum(len(b) for b in uploads) > XMATCH_MAX_UPLOAD_BYTES:
        raise VoProtocolsError("TABLE_TOO_LARGE", f"tabelle caricate di {sum(len(b) for b in uploads)} byte, oltre "
                               f"il limite di {XMATCH_MAX_UPLOAD_BYTES} byte del servizio XMatch",
                               params={"reason": "upload", "total": _q(sum(len(b) for b in uploads), "byte"),
                                       "limit": _q(XMATCH_MAX_UPLOAD_BYTES, "byte")})
    params = {"request": "xmatch", "distMaxArcsec": repr(float(distance.value)), "selection": selection,
              "RESPONSEFORMAT": "votable", "colRA1": "ra", "colDec1": "dec", "colRA2": "ra", "colDec2": "dec",
              "cat1_sha256": hashlib.sha256(uploads[0]).hexdigest(),
              "cat2_sha256": hashlib.sha256(uploads[1]).hexdigest()}
    canonical = _canonical(params)
    cache_obj = SharedCache() if cache is None else cache
    rows = cache_obj.table(_CACHE_MODULE, _QUERY_TABLE, _QUERY_COLUMNS)
    key = _cache_key("xmatch", "POST", XMATCH_URL, canonical)
    cached = rows.get(key)
    if cached is not None and not refresh:
        response = _Response(cached.data["payload"], XMATCH_URL, "POST", canonical, cached.retrieved_at, True,
                             (_cached_since(cached),))
    else:
        client = XMatchClass()
        client.URL = XMATCH_URL
        client.TIMEOUT = timeouts.as_requests()
        try:
            answer = client.query_async(cat1, cat2, distance, colRA1="ra", colDec1="dec", colRA2="ra",
                                        colDec2="dec", cache=False, selection=selection)
        except InvalidQueryError as exc:
            raise VoProtocolsError("SERVICE_ERROR", f"{XMATCH_URL}: il servizio ha rifiutato la richiesta: {exc}",
                                   url=XMATCH_URL, params={"reason": "service_rejected", "url": XMATCH_URL,
                                                           "detail": str(exc)}) from exc
        except requests.exceptions.HTTPError as exc:
            raise VoProtocolsError("SERVICE_ERROR", f"{XMATCH_URL}: {exc}", url=XMATCH_URL,
                                   params={"reason": "request_failed", "url": XMATCH_URL,
                                           "detail": str(exc)}) from exc
        except requests.exceptions.RequestException as exc:
            if cached is None:
                raise _net_error(XMATCH_URL, exc, timeouts) from exc
            response = _Response(cached.data["payload"], XMATCH_URL, "POST", canonical, cached.retrieved_at, True,
                                 (_network_unavailable(exc),))
        else:
            response = _Response(answer.content, XMATCH_URL, "POST", canonical, datetime.now(UTC), False)
    result = _read_payload(response)
    notes = response.notes + _store(response, "xmatch", cache)
    arguments = {"max_distance_arcsec": float(distance.value), "selection": selection,
                 "cat1_rows": len(cat1), "cat2_rows": len(cat2)}
    return VoResult(table=result, request=_record("xmatch", "cds_xmatch", arguments, response, result.rows),
                    warnings=notes)


def vizier_photometry(center, radius, *, max_rows: int = DEFAULT_MAX_ROWS, limits: TableLimits | None = None,
                      cache: SharedCache | None = None, refresh: bool = False,
                      timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> VoResult:
    """Misure di flusso del servizio fotometrico di VizieR attorno a una posizione (H17); SED nel 20.

    Parametri del servizio: ``-c`` (posizione in gradi) e ``-c.rs`` (raggio in arcsec, al massimo 30″).
    Ogni punto ha frequenza (``_sed_freq``), flusso ed errore (``_sed_flux``, ``_sed_eflux``), filtro,
    catalogo d'origine (``_tabname``) e, se presente, data (``_time``, con il ``TIMESYS`` del servizio).
    """
    limits = _check_max_rows(max_rows, limits)
    ra, dec = _icrs_degrees(center)
    r = _radius_degrees(radius)
    if r * u.deg > _VIZIER_MAX_RADIUS:
        raise ValueError(f"radius: il servizio fotometrico di VizieR accetta al massimo {_VIZIER_MAX_RADIUS} "
                         "(nessuna riduzione silenziosa)")
    params = {"-c": f"{ra:.8f} {dec:+.8f}", "-c.rs": f"{(r * u.deg).to_value(u.arcsec):.6g}"}
    response = _http("vizier-photometry", VIZIER_PHOTOMETRY_URL, params, cache=cache, refresh=refresh,
                     timeouts=timeouts, accept_error_body=True)
    parsed = _parse_results(response, pyvo.dal.DALResults)
    arguments = {"center": {"ra_deg": ra, "dec_deg": dec, "frame": "icrs"}, "radius": {"value": r, "unit": "deg"},
                 "max_rows": max_rows}
    result = _finish("vizier-photometry", "vizier_photometry", arguments, response, parsed, max_rows=max_rows,
                     limits=limits, cache=cache)
    missing = [c for c in ("_sed_freq", "_sed_flux", "_tabname") if c not in result.table.colnames]
    if missing:
        raise VoProtocolsError("VOTABLE_INVALID", f"{VIZIER_PHOTOMETRY_URL}: risposta senza le colonne {missing}",
                               params={"reason": "photometry_columns", "url": VIZIER_PHOTOMETRY_URL,
                                       "missing": missing})
    return result


# --------------------------------------------------------------------------
# P7 — SAMP con pyvo.samp (H14, G3; D14-2, D14-9 punti 1 e 10)
# --------------------------------------------------------------------------

#: Messaggi SAMP supportati (D14-9 punto 10): tabelle, selezioni e puntamenti.
SAMP_MTYPES: tuple[str, ...] = ("table.load.votable", "table.select.rowList", "coord.pointAt.sky")


@dataclass(frozen=True)
class SampClient:
    """Programma collegato all'hub (identificativo pubblico e nome dichiarato)."""

    id: str
    name: str | None


#: Avvisi amministrativi dell'hub (sprint B1): solo per l'elenco dei client e lo stato, non portano dati.
SAMP_HUB_EVENTS: tuple[str, ...] = ("samp.hub.event.register", "samp.hub.event.unregister",
                                    "samp.hub.event.metadata", "samp.hub.event.shutdown")


@dataclass(frozen=True)
class SampFailure:
    """Destinatario che non ha accettato un messaggio (sprint B1b): ``rejected`` (risposta ``samp.error`` o errore
    dell'hub) o ``no_reply`` (nessuna risposta entro il tempo massimo); ``detail`` è testo esterno."""

    id: str
    reason: str
    detail: str


@dataclass(frozen=True)
class SampSendResult:
    """Esito di un invio: tipo di messaggio, destinatari che hanno accettato, parametri inviati, destinatari falliti."""

    mtype: str
    recipients: tuple[str, ...]
    params: Mapping[str, object] = field(default_factory=dict)
    failures: tuple[SampFailure, ...] = ()


#: Tempo massimo di risposta di ogni destinatario (s), lo stesso del ``40`` (D40-9 (2)).
SAMP_REPLY_TIMEOUT = 10.0
#: Tempo di risposta per ``table.load.votable`` (D40-9 (7), decisa dal proprietario il 2026-11-05): TOPCAT risponde a
#: caricamento finito, con tabelle grandi oltre i 10 s degli altri tipi.
SAMP_TABLE_REPLY_TIMEOUT = 60.0


@dataclass(frozen=True)
class SampTableReference:
    """Tabella annunciata da ``table.load.votable`` senza leggerla (sprint B1): URL, identificativo e nome."""

    url: str
    table_id: str
    name: str | None


@dataclass(frozen=True)
class SampSelection:
    """Selezione ricevuta o da inviare: tabella (identificativo e URL) e righe (indici da 0)."""

    table_id: str
    url: str
    rows: tuple[int, ...]


def _restricted_client_class():
    """Client SAMP di ``pyvo`` che **non** si iscrive a ``client.env.get`` (sprint B1, 2026-11-05).

    ``pyvo.samp.SAMPClient`` risponde di default a ``client.env.get`` (variabili d'ambiente del processo a chi le
    chiede): AstroTwo riceve solo i tre tipi di ``SAMP_MTYPES`` (D14-9 punto 10) più ``samp.app.ping`` (risposta
    vuota, nessun dato). Il collegamento è quello di ``SAMPIntegratedClient.connect`` con una sola differenza: la voce si
    toglie (``unbind_receive_call`` pubblica, senza dichiarazione) **prima** della registrazione all'hub, così non c'è
    mai un istante in cui AstroTwo è iscritto.

    Sprint B1b: anche i gestori di ``bindings`` (``(mtype, funzione, chiamata sì/no)``) si legano **prima** della
    registrazione, senza dichiarazione: ``register()`` dichiara iscrizioni e metadati una volta sola (prima ogni legame
    ridichiarava l'elenco: 12 avvisi ``samp.hub.event.subscriptions`` a tutti i client a ogni collegamento)."""
    from pyvo.samp import SAMPIntegratedClient
    from pyvo.samp.client import SAMPClient

    class RestrictedSampClient(SAMPIntegratedClient):
        def connect(self, hub=None, hub_params=None, pool_size=20, bindings=()):
            self.hub.connect(hub, hub_params, pool_size)
            self.client = SAMPClient(self.hub, **self.client_arguments)
            self.client.unbind_receive_call("client.env.get", declare=False)
            for mtype, function, call in bindings:
                if call:
                    self.client.bind_receive_call(mtype, function, declare=False)
                else:
                    self.client.bind_receive_notification(mtype, function, declare=False)
            self.client.start()
            self.client.register()

        @property
        def hub_id(self) -> str | None:
            """Identificativo che l'hub dà a sé stesso alla registrazione (``samp.hub-id``): ``cli#hub`` per l'hub di
            ``pyvo``, ``hub`` per quello di TOPCAT (JSAMP). ``pyvo`` lo conserva senza un metodo pubblico."""
            client = getattr(self, "client", None)
            hub_id = getattr(client, "_hub_id", None)
            return None if hub_id is None else str(hub_id)

    return RestrictedSampClient


class SampHub:
    """Collegamento SAMP: hub già attivo se presente, altrimenti hub proprio (profilo web disattivato).

    Riceve i tre tipi di ``SAMP_MTYPES`` con le funzioni registrate da ``on_table``, ``on_selection``
    e ``on_point``; l'interfaccia (es. "invia la selezione") è di ``42-ui-pannello-cataloghi.md``.
    """

    def __init__(self, *, name: str = "AstroTwo", web_profile: bool = False) -> None:
        self.name = name
        self.web_profile = web_profile
        self.own_hub = False
        self._hub = None
        self._client = None
        self._tmpdir: tempfile.TemporaryDirectory | None = None
        self._handlers: dict[str, object] = {}
        self._table_reference = None
        self._hub_event = None

    # -- collegamento ---------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    def connect(self) -> SampHub:
        """Si collega all'hub attivo; se non c'è ne avvia uno proprio; altrimenti ``SAMP_UNAVAILABLE``."""
        from pyvo.samp import SAMPHubError, SAMPHubServer

        if self.connected:
            return self
        client = _restricted_client_class()(name=self.name, description=f"AstroTwo {astrotwo.__version__}",
                                            metadata={"samp.name": self.name})
        bindings = []  # legati prima della registrazione: una sola dichiarazione delle iscrizioni (sprint B1b)
        for mtype, function in (("table.load.votable", self._receive_table),
                                ("table.select.rowList", self._receive_selection),
                                ("coord.pointAt.sky", self._receive_point)):
            bindings += [(mtype, function, False), (mtype, function, True)]
        for mtype in SAMP_HUB_EVENTS:  # solo elenco dei client e stato del collegamento (sprint B1)
            bindings.append((mtype, self._receive_hub_event, False))
        try:
            client.connect(bindings=bindings)
        except (SAMPHubError, OSError):
            try:
                hub = SAMPHubServer(web_profile=self.web_profile, label=self.name)
                hub.start(wait=False)
                client.connect(bindings=bindings)
            except Exception as exc:
                raise VoProtocolsError("SAMP_UNAVAILABLE", f"nessun hub SAMP attivo e avvio del proprio non riuscito "
                                       f"({exc}); le altre funzioni VO restano disponibili",
                                       params={"reason": "no_hub", "detail": str(exc)}) from exc
            self._hub, self.own_hub = hub, True
        self._client = client
        return self

    def disconnect(self) -> None:
        if self._client is not None and self._client.is_connected:
            self._client.disconnect()
        self._client = None
        if self._hub is not None:
            self._hub.stop()
        self._hub, self.own_hub = None, False
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None

    def __enter__(self) -> SampHub:
        return self.connect()

    def __exit__(self, *exc) -> None:
        self.disconnect()

    def _require(self):
        if not self.connected:
            raise VoProtocolsError("SAMP_UNAVAILABLE", "non collegato a un hub SAMP: chiamare connect()",
                                   params={"reason": "not_connected"})
        return self._client

    @property
    def hub_id(self) -> str | None:
        """Identificativo dell'hub (``samp.hub-id`` della registrazione), ``None`` se non collegato."""
        return None if self._client is None else self._client.hub_id

    def clients(self) -> tuple[SampClient, ...]:
        """Programmi collegati, esclusi AstroTwo e l'hub (riconosciuto da ``samp.hub-id``, sprint B1b: l'hub di TOPCAT
        si chiama ``hub``, quello di ``pyvo`` ``cli#hub``)."""
        client = self._require()
        hub_id = client.hub_id
        out = []
        for cid in client.get_registered_clients():
            if cid == hub_id:
                continue
            name = client.get_metadata(cid).get("samp.name")
            out.append(SampClient(id=cid, name=None if name is None else str(name)))
        return tuple(out)

    # -- invio ----------------------------------------------------------------

    def send_message(self, mtype: str, params: dict, recipient: str | None = None, *,
                     among: Iterable[str] | None = None, timeout: float = SAMP_REPLY_TIMEOUT) -> SampSendResult:
        """Invia uno dei tipi supportati con **chiamata sincrona** a ogni destinatario, in parallelo (sprint B1b).

        Destinatari: ``recipient``, oppure tutti gli iscritti al tipo (escluso AstroTwo), ristretti ad ``among`` se dato.
        Ogni destinatario ha ``timeout`` secondi per rispondere; ``samp.ok`` (o ``samp.warning``) → accettato,
        ``samp.error`` o errore dell'hub → ``SampFailure`` ``rejected``, nessuna risposta → ``no_reply``. Nessun
        accettato → ``SAMP_NO_PEER`` (``rejected``/``no_reply`` del primo fallito). Altri tipi →
        ``SAMP_UNSUPPORTED_TYPE``; nessun destinatario → ``SAMP_NO_PEER`` (``recipient``/``none``)."""
        if mtype not in SAMP_MTYPES:
            raise VoProtocolsError("SAMP_UNSUPPORTED_TYPE",
                                   f"tipo {mtype!r} non supportato; supportati: {', '.join(SAMP_MTYPES)}",
                                   params={"reason": "type", "mtype": str(mtype), "supported": list(SAMP_MTYPES)})
        client = self._require()
        subscribed = set(client.get_subscribed_clients(mtype)) - {client.get_public_id(), client.hub_id}
        if recipient is not None:
            if recipient not in subscribed:
                raise VoProtocolsError("SAMP_NO_PEER", f"{recipient!r} non è collegato o non accetta {mtype}",
                                       params={"reason": "recipient", "recipient": recipient, "mtype": mtype})
            targets = [recipient]
        else:
            targets = sorted(subscribed if among is None else subscribed & set(among))
        if not targets:
            raise VoProtocolsError("SAMP_NO_PEER", f"nessun programma collegato accetta {mtype}",
                                   params={"reason": "none", "mtype": mtype})
        sent = {k: v for k, v in params.items()}
        outcomes = self._call_all(client, targets, {"samp.mtype": mtype, "samp.params": dict(sent)}, timeout)
        accepted = tuple(t for t in targets if outcomes[t] is None)
        failures = tuple(outcomes[t] for t in targets if outcomes[t] is not None)
        if not accepted:
            first = failures[0]
            name = self._name_or_id(first.id)
            if first.reason == "no_reply" and mtype == "table.load.votable":  # D40-9 (7): può arrivare comunque
                raise VoProtocolsError("SAMP_NO_PEER", f"{name} non ha risposto a {mtype} entro {timeout:g} s: la "
                                       "tabella potrebbe arrivare comunque",
                                       params={"reason": "no_reply_table", "recipient": name, "mtype": mtype,
                                               "seconds": float(timeout)})
            if first.reason == "no_reply":
                raise VoProtocolsError("SAMP_NO_PEER", f"{name} non ha risposto a {mtype} entro {timeout:g} s",
                                       params={"reason": "no_reply", "recipient": name, "mtype": mtype,
                                               "seconds": float(timeout)})
            raise VoProtocolsError("SAMP_NO_PEER", f"{name} non ha accettato {mtype}: {first.detail}",
                                   params={"reason": "rejected", "recipient": name, "mtype": mtype,
                                           "detail": first.detail})
        return SampSendResult(mtype=mtype, recipients=accepted, params=sent, failures=failures)

    def _name_or_id(self, client_id: str) -> str:
        try:
            return self.client_name(client_id) or client_id
        except Exception:  # noqa: BLE001 - client già uscito: resta l'identificativo
            return client_id

    @staticmethod
    def _call_all(client, targets: list[str], message: dict, timeout: float) -> dict[str, SampFailure | None]:
        """``callAndWait`` verso ogni destinatario in un thread proprio; oltre ``timeout`` (+1 s di margine per gli hub
        che non rispettano il proprio) → ``no_reply``. ``None`` = accettato."""
        import math
        from concurrent.futures import ThreadPoolExecutor, wait

        seconds = str(max(1, math.ceil(timeout)))

        def one(target: str) -> SampFailure | None:
            start = time.monotonic()
            try:
                response = client.call_and_wait(target, message, seconds)
            except Exception as exc:  # noqa: BLE001 - errore dell'hub (client morto, tempo scaduto): esito del singolo
                if time.monotonic() - start >= timeout:
                    return SampFailure(target, "no_reply", str(exc))
                return SampFailure(target, "rejected", str(exc))
            status = str((response or {}).get("samp.status", ""))
            if status in ("samp.ok", "samp.warning"):
                return None
            error = (response or {}).get("samp.error") or {}
            detail = error.get("samp.errortxt") if isinstance(error, Mapping) else None
            return SampFailure(target, "rejected", str(detail or status or "risposta vuota"))

        pool = ThreadPoolExecutor(max_workers=len(targets), thread_name_prefix="astrotwo-samp-call")
        try:
            futures = {target: pool.submit(one, target) for target in targets}
            wait(futures.values(), timeout=timeout + 1.0)
            return {target: (future.result() if future.done() else
                             SampFailure(target, "no_reply", f"nessuna risposta entro {timeout:g} s"))
                    for target, future in futures.items()}
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def client_name(self, client_id: str) -> str | None:
        """Nome dichiarato (``samp.name``) di un client, ``None`` se non lo dichiara."""
        name = self._require().get_metadata(client_id).get("samp.name")
        return None if name is None else str(name)

    def send_table(self, table: CatalogTable, *, table_id: str, name: str | None = None,
                   recipient: str | None = None, timeout: float = SAMP_TABLE_REPLY_TIMEOUT) -> SampSendResult:
        """``table.load.votable``: la tabella si scrive in un VOTable temporaneo con provenienza (P1)."""
        self._require()
        if self._tmpdir is None:
            self._tmpdir = tempfile.TemporaryDirectory(prefix="astrotwo-samp-")
        path = export_table(table, Path(self._tmpdir.name) / f"{len(os.listdir(self._tmpdir.name))}.xml",
                            "votable").path
        params = {"url": path.resolve().as_uri(), "table-id": table_id, "name": name or table_id}
        return self.send_message("table.load.votable", params, recipient, timeout=timeout)

    def send_selection(self, selection: SampSelection, recipient: str | None = None, *,
                       among: Iterable[str] | None = None, timeout: float = SAMP_REPLY_TIMEOUT) -> SampSendResult:
        """``table.select.rowList``: righe con indice da 0, come chiede il messaggio SAMP."""
        rows = [str(int(k)) for k in selection.rows]
        params = {"table-id": selection.table_id, "url": selection.url, "row-list": rows}
        return self.send_message("table.select.rowList", params, recipient, among=among, timeout=timeout)

    def send_point(self, center, recipient: str | None = None, *,
                   timeout: float = SAMP_REPLY_TIMEOUT) -> SampSendResult:
        """``coord.pointAt.sky``: posizione in gradi ICRS (conversione del modulo 10)."""
        ra, dec = _icrs_degrees(center)
        return self.send_message("coord.pointAt.sky", {"ra": repr(ra), "dec": repr(dec)}, recipient, timeout=timeout)

    # -- ricezione ------------------------------------------------------------

    def on_table(self, function) -> None:
        """``function(table: CatalogTable, table_id, sender)`` per ogni tabella ricevuta."""
        self._handlers["table.load.votable"] = function

    def on_selection(self, function) -> None:
        """``function(selection: SampSelection, sender)`` per ogni selezione ricevuta."""
        self._handlers["table.select.rowList"] = function

    def on_point(self, function) -> None:
        """``function(position: SkyFrame, sender)`` per ogni puntamento ricevuto (ICRS, epoca non dichiarata)."""
        self._handlers["coord.pointAt.sky"] = function

    def on_table_reference(self, function) -> None:
        """``function(reference: SampTableReference, sender)``: tabella ricevuta **senza leggerla** (sprint B1).

        Se registrata sostituisce ``on_table``; chi la riceve ne fa una copia con ``save_votable``."""
        self._table_reference = function

    def on_hub_event(self, function) -> None:
        """``function(mtype, params)`` per gli avvisi dell'hub di ``SAMP_HUB_EVENTS`` (elenco dei client, stato)."""
        self._hub_event = function

    @staticmethod
    def save_votable(url: str, path, *, timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> Path:
        """Copia il VOTable annunciato da un client: ``file:`` copiato, ``http(s):`` scaricato con i timeout del 04.

        Nessuna lettura e nessuna cache (dati di un altro programma); altri schemi o file assente →
        ``SAMP_TABLE_FETCH_FAILED``; errori di rete come per le altre richieste (``NET_TIMEOUT``, ``SERVICE_ERROR``)."""
        import shutil
        from urllib.parse import unquote, urlsplit

        target = Path(os.fspath(path))
        parts = urlsplit(str(url))
        if parts.scheme == "file":
            source = Path(unquote(parts.path))
            try:
                shutil.copyfile(source, target)
            except OSError as exc:
                raise VoProtocolsError("SAMP_TABLE_FETCH_FAILED", f"{url}: copia non riuscita ({exc})",
                                       params={"reason": "file", "url": str(url), "detail": str(exc)}) from exc
            return target
        if parts.scheme not in ("http", "https"):
            raise VoProtocolsError("SAMP_TABLE_FETCH_FAILED", f"{url}: schema non ammesso (file, http, https)",
                                   params={"reason": "scheme", "url": str(url)})
        try:
            with _Session(timeouts) as session:
                response = session.get(str(url))
                payload = response.content
        except requests.exceptions.RequestException as exc:
            raise _net_error(str(url), exc, timeouts) from exc
        _check_http(response, str(url))
        if not response.ok:
            raise VoProtocolsError("SERVICE_ERROR", f"{url}: risposta HTTP {response.status_code} {response.reason}",
                                   url=str(url), status=response.status_code,
                                   params={"reason": "http_status", "url": str(url), "status": response.status_code,
                                           "status_text": str(response.reason)})
        target.write_bytes(payload)
        return target

    def _receive_hub_event(self, private_key, sender_id, msg_id, mtype, params, extra) -> None:
        if self._hub_event is not None:
            try:
                self._hub_event(str(mtype), dict(params or {}))
            except Exception:  # noqa: BLE001 - un avviso dell'hub non deve mai fermare il collegamento
                pass

    def _reply(self, msg_id, error: Exception | None) -> None:
        if msg_id is None or self._client is None:
            return
        from pyvo.samp import SAMP_STATUS_ERROR, SAMP_STATUS_OK

        if error is None:
            self._client.reply(msg_id, {"samp.status": SAMP_STATUS_OK, "samp.result": {}})
        else:
            self._client.reply(msg_id, {"samp.status": SAMP_STATUS_ERROR,
                                        "samp.error": {"samp.errortxt": str(error)}})

    def _dispatch(self, mtype: str, msg_id, build) -> None:
        handler = self._handlers.get(mtype)
        try:
            if handler is None:
                raise VoProtocolsError("SAMP_UNSUPPORTED_TYPE", f"nessuna funzione registrata per {mtype}",
                                       params={"reason": "no_handler", "mtype": mtype})
            handler(*build())
        except Exception as exc:  # l'errore torna al mittente, il collegamento resta attivo
            self._reply(msg_id, exc)
            return
        self._reply(msg_id, None)

    def _receive_table(self, private_key, sender_id, msg_id, mtype, params, extra) -> None:
        if self._table_reference is not None:
            def run(function=self._table_reference):
                name = params.get("name")
                function(SampTableReference(str(params["url"]), str(params.get("table-id", "")),
                                            None if name is None else str(name)), sender_id)
            try:
                run()
            except Exception as exc:  # l'errore torna al mittente
                self._reply(msg_id, exc)
                return
            self._reply(msg_id, None)
            return

        def build():
            url = str(params["url"])
            if url.startswith("file:"):
                from urllib.parse import unquote, urlsplit
                table = read_votable(unquote(urlsplit(url).path))
            else:
                table = download_table(url).table
            return table, str(params.get("table-id", "")), sender_id
        self._dispatch(mtype, msg_id, build)

    def _receive_selection(self, private_key, sender_id, msg_id, mtype, params, extra) -> None:
        def build():
            rows = tuple(int(k) for k in params["row-list"])
            return SampSelection(str(params["table-id"]), str(params["url"]), rows), sender_id
        self._dispatch(mtype, msg_id, build)

    def _receive_point(self, private_key, sender_id, msg_id, mtype, params, extra) -> None:
        def build():
            position = SkyFrame.from_lonlat(float(params["ra"]) * u.deg, float(params["dec"]) * u.deg, "icrs")
            return position, sender_id
        self._dispatch(mtype, msg_id, build)
