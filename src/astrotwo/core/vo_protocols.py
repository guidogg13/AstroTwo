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
import time
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import astropy
import numpy as np
from astropy.io import ascii as astropy_ascii
from astropy.io import fits
import astropy.units as u
import pyvo
import requests
from defusedxml.ElementTree import fromstring as safe_fromstring
from astropy.coordinates import SkyCoord
from astropy.io.votable import parse as parse_votable
from astropy.table import Table

import astrotwo
from astrotwo.core.cache import NETWORK_TIMEOUTS, CacheError, NetworkTimeouts, SharedCache
from astrotwo.core.coordinates_wcs import SkyFrame
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
    "AdqlCheck",
    "BUILTIN_SERVERS",
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


def validate_adql(adql: str) -> AdqlCheck:
    """Controlli minimi: non vuota, inizia con SELECT, virgolette chiuse, parentesi bilanciate."""
    if not isinstance(adql, str) or not adql.strip():
        return AdqlCheck(False, "ADQL vuota", 0)
    start = len(adql) - len(adql.lstrip())
    if not re.match(r"select\b", adql[start:], re.IGNORECASE):
        return AdqlCheck(False, "l'ADQL deve iniziare con SELECT", start)
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
                return AdqlCheck(False, "parentesi chiusa senza apertura", k)
            opened.pop()
        k += 1
    if quote is not None:
        return AdqlCheck(False, f"virgoletta {quote} non chiusa", quote_at)
    if opened:
        return AdqlCheck(False, "parentesi aperta non chiusa", opened[-1])
    return AdqlCheck(True, "controlli minimi superati (la validazione vera è del servizio)")


def _check_max_rows(max_rows, limits: TableLimits | None) -> TableLimits:
    limits = TableLimits() if limits is None else limits
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or not 1 <= max_rows <= limits.max_rows:
        raise VoProtocolsError("MAX_ROWS_INVALID",
                               f"max_rows = {max_rows!r}: ammessi gli interi da 1 a {limits.max_rows} "
                               "(tetto di righe del modulo 13)")
    return limits


def _service_url(service: str, protocol: str, servers: ServerRegistry | None = None) -> str:
    """URL esplicito, oppure voce dell'elenco dei server con il protocollo richiesto (D14-9 punto 6)."""
    if isinstance(service, str) and service.startswith(("http://", "https://")):
        return service.rstrip("/") if protocol == "tap" else service
    entry = (ServerRegistry() if servers is None else servers).get(service)
    if entry.protocol != protocol:
        raise VoProtocolsError("SERVER_UNKNOWN", f"la voce {service!r} è un servizio {entry.protocol}, non "
                               f"{protocol}", server=service)
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
        if http_status is not None and http_status.startswith("5"):
            raise VoProtocolsError("SERVICE_ERROR", f"{response.url}: HTTP {http_status}: {message}{extra}",
                                   url=response.url) from exc
        raise VoProtocolsError("ADQL_INVALID" if results_class is pyvo.dal.TAPResults else "SERVICE_ERROR",
                               f"{response.url}: il servizio ha rifiutato la richiesta: {message}{extra}",
                               url=response.url, service_message=message) from exc
    except Exception as exc:
        if http_status is not None:
            raise VoProtocolsError("SERVICE_ERROR", f"{response.url}: risposta HTTP {http_status} senza VOTable",
                                   url=response.url) from exc
        raise VoProtocolsError("VOTABLE_INVALID", f"{response.url}: risposta non leggibile come VOTable ({exc})",
                               url=response.url) from exc


def _limited(result: CatalogTable, max_rows: int, service_overflow: bool) -> tuple[CatalogTable, tuple, bool]:
    """Dichiara sempre il superamento di ``max_rows`` (``ROW_LIMIT_EXCEEDED``), mai una riduzione silenziosa."""
    received = result.rows
    if received > max_rows:
        cut = dataclasses.replace(result, table=result.table[:max_rows],
                                  history=result.history + (f"prime {max_rows} righe di {received} ricevute",))
        return cut, (("ROW_LIMIT_EXCEEDED", f"ricevute {received} righe, restituite le prime {max_rows} "
                      f"(max_rows = {max_rows})"),), True
    if service_overflow:
        return result, (("ROW_LIMIT_EXCEEDED", f"il servizio ha troncato il risultato a {received} righe "
                         f"(max_rows = {max_rows}, stato OVERFLOW)"),), True
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
    url = _service_url(catalog, "scs", servers)
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
              timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> VoResult:
    """Esegue ADQL su un servizio TAP: sincrona di default, asincrona su richiesta (D14-9 punto 8)."""
    check = validate_adql(adql)
    if not check.valid:  # nessuna chiamata di rete inutile (T4)
        raise VoProtocolsError("ADQL_INVALID", f"{check.message} (carattere {check.position})",
                               position=check.position)
    limits = _check_max_rows(max_rows, limits)
    if mode not in ("sync", "async"):
        raise ValueError("mode deve essere 'sync' o 'async'")
    if not (isinstance(async_timeout, (int, float)) and async_timeout > 0):
        raise ValueError("async_timeout deve essere un numero di secondi positivo")
    base = _service_url(url, "tap", servers)
    arguments = {"url": url, "adql": adql, "max_rows": max_rows, "mode": mode}
    if mode == "sync":
        query = pyvo.dal.tap.TAPQuery(base, adql, mode="sync", maxrec=max_rows)
        response = _http("tap", query.queryurl, dict(query), method="POST", cache=cache, refresh=refresh,
                         timeouts=timeouts, accept_error_body=True, hint=_ASYNC_HINT)
    else:
        arguments["async_timeout"] = async_timeout
        response = _tap_async(base, adql, max_rows, async_timeout, cache=cache, refresh=refresh, timeouts=timeouts)
    results = _parse_results(response, pyvo.dal.TAPResults, hint=_ASYNC_HINT if mode == "sync" else "")
    return _finish("tap", "tap_query", arguments, response, results, max_rows=max_rows, limits=limits, cache=cache)


def _tap_async(base: str, adql: str, max_rows: int, async_timeout: float, *, cache, refresh,
               timeouts: NetworkTimeouts) -> _Response:
    """Lavoro UWS con ``pyvo``: attesa massima complessiva ``async_timeout`` s, poi interruzione."""
    params = dict(pyvo.dal.tap.TAPQuery(base, adql, mode="async", maxrec=max_rows))
    url = f"{base}/async"
    canonical = _canonical(params)
    cache = SharedCache() if cache is None else cache
    rows = cache.table(_CACHE_MODULE, _QUERY_TABLE, _QUERY_COLUMNS)
    cached = rows.get(_cache_key("tap", "POST", url, canonical))
    if cached is not None and not refresh:
        return _Response(cached.data["payload"], url, "POST", canonical, cached.retrieved_at, True,
                         (("FROM_CACHE", f"copia in cache di {cached.origin}, scaricata il "
                           f"{_iso(cached.retrieved_at)}"),))
    deadline = time.monotonic() + async_timeout
    session = _Session(timeouts)
    try:
        job = pyvo.dal.AsyncTAPJob.create(base, adql, maxrec=max_rows, session=session)
        try:
            job.run()
            interval = 0.2
            while (phase := job.phase) not in ("COMPLETED", "ERROR", "ABORTED"):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    job.abort()
                    raise VoProtocolsError("NET_TIMEOUT", f"{url}: attesa massima di {async_timeout:g} s superata "
                                           f"(fase {phase}); lavoro interrotto", url=url)
                time.sleep(min(interval, remaining))
                interval = min(interval * 1.5, 10.0)
            if phase != "COMPLETED":
                try:
                    job.raise_if_error()
                except pyvo.dal.DALQueryError as exc:
                    raise VoProtocolsError("ADQL_INVALID", f"{url}: il servizio ha rifiutato la richiesta: {exc}",
                                           url=url, service_message=str(exc)) from exc
                raise VoProtocolsError("SERVICE_ERROR", f"{url}: lavoro terminato in fase {phase}", url=url)
            response = session.get(job.result_uri)
            _check_http(response, url)
            if not response.ok:
                raise VoProtocolsError("SERVICE_ERROR", f"{job.result_uri}: risposta HTTP {response.status_code}",
                                       url=url)
            payload = response.content
        finally:
            try:
                job.delete()
            except (pyvo.dal.DALServiceError, requests.exceptions.RequestException):
                pass  # il servizio elimina comunque i lavori scaduti
    except (requests.exceptions.RequestException, pyvo.dal.DALServiceError) as exc:
        if cached is not None:
            return _Response(cached.data["payload"], url, "POST", canonical, cached.retrieved_at, True,
                             (("FROM_CACHE", f"rete non disponibile ({type(exc).__name__}): copia in cache del "
                               f"{_iso(cached.retrieved_at)}"),))
        raise _net_error(url, exc, timeouts) from exc
    finally:
        session.close()
    return _Response(payload, url, "POST", canonical, datetime.now(UTC), False)


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
)


@dataclass(frozen=True)
class RegistrySearch:
    """Esito di una ricerca nel registro VO: tabella RegTAP registrata e servizi trovati."""

    result: VoResult
    services: tuple[ServerEntry, ...]


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
                               server=server_id)

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
            raise VoProtocolsError("SERVER_UNKNOWN", f"{server_id!r} non è un server personale", server=server_id)
        del self._personal[server_id]

    def search_registry(self, keywords, servicetype: str, *, max_rows: int = DEFAULT_MAX_ROWS,
                        registry_url: str = pyvo.registry.regtap.REGISTRY_BASEURL,
                        cache: SharedCache | None = None, refresh: bool = False,
                        timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> RegistrySearch:
        """Ricerca nel registro VO (RegTAP): ADQL costruito da ``pyvo``, eseguito con ``tap_query``."""
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
        raise VoProtocolsError("SERVICE_ERROR", f"descrittore {service_def!r} assente dal documento DataLink")


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
                                   url=url)
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
