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
from astrotwo.core.coordinates_wcs import CoordinatesWcsError, SkyFrame, wcs_from_header
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
    "SampHub",
    "SampSelection",
    "SampSendResult",
    "SIMBAD_COORDINATES_NOTE",
    "SimbadObject",
    "SimbadMagnitude",
    "SIMBAD_FLUX_SYSTEMS",
    "SimbadPointer",
    "VIZIER_PHOTOMETRY_URL",
    "MOCSERVER_URL",
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
                               f"formato {format!r}: ammessi {', '.join(EXPORT_FORMATS)}")
    if not isinstance(table, CatalogTable):
        raise TypeError("export_table accetta una CatalogTable (nessun dato senza provenienza)")
    target = Path(os.fspath(path)).expanduser()
    if target.exists() and not overwrite:
        raise VoProtocolsError("FILE_EXISTS", f"{target}: esiste già; usare overwrite=True", path=str(target))
    if target.exists():
        target.unlink()
    info = _provenance(table, format)
    writers = {"votable": _write_votable_file, "fits": _write_fits_file, "csv": _write_csv_file,
               "ecsv": _write_ecsv_file}
    writers[format](table, target, info)
    notes = []
    if format == "csv" and _has_units(table):
        notes.append(("CSV_UNITS_NOT_SAVED", "il CSV semplice non salva le unità delle colonne: per conservarle "
                      "esportare in ecsv (D14-10)"))
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
                response = session.post(url, data=list(canonical))
            else:
                response = session.get(url, params=list(canonical))
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


def _link_fetcher(*, cache: SharedCache | None = None, refresh: bool = False,
                  timeouts: NetworkTimeouts = NETWORK_TIMEOUTS):
    """Funzione di rete per i dati in un ``LINK`` ASTRORES (D13-17): prima la cache, risposta registrata."""

    def fetch(url: str) -> tuple[bytes, tuple[str, str]]:
        response = _http("download", url, cache=cache, refresh=refresh, timeouts=timeouts)
        _store(response, "download", cache)
        state = "copia in cache" if response.from_cache else "scaricati"
        return response.payload, ("ASTRORES_LINK_SOURCE", f"dati collegati {url}: {state} il "
                                  f"{_iso(response.retrieved_at)}")

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


# --------------------------------------------------------------------------
# P5 — Immagini SIA/SIA2 (H23), IDHA, spettri SSA (E4)
# --------------------------------------------------------------------------


def _no_result(result: VoResult, code: str, what: str) -> VoResult:
    """Esito vuoto: avviso, non errore (§10)."""
    if result.table.rows:
        return result
    return dataclasses.replace(result, warnings=result.warnings + ((code, f"nessun{what} per i criteri dati"),))


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
    url = _service_url(service, protocol, servers)
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
            raise VoProtocolsError("SIA_INVALID", exc.message, url=url) from exc
        raise
    result = _finish(protocol, "sia_search", arguments, response, parsed, max_rows=max_rows, limits=limits,
                     cache=cache)
    return _no_result(result, "SIA_NO_RESULT", "a immagine")


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
                               "nessun dato caricato", path=text) from exc
    except (XmlParseError, OSError) as exc:
        raise VoProtocolsError("IDHA_UNREADABLE", f"{text}: file non leggibile come XML ({exc})", path=text) from exc
    raise VoProtocolsError("IDHA_UNREADABLE", f"{text}: formato IDHA non leggibile: nessuna documentazione pubblica "
                           "del formato (D14-9 punto 13); usare SIA o SIA2", path=text)


def ssa_search(center, radius, *, service: str, max_rows: int = DEFAULT_MAX_ROWS,
               servers: ServerRegistry | None = None, limits: TableLimits | None = None,
               cache: SharedCache | None = None, refresh: bool = False,
               timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> VoResult:
    """Ricerca di spettri SSA 1.1 con ``pyvo`` (``SIZE`` = diametro = 2 × raggio); vuota → ``SSA_NO_RESULT``."""
    limits = _check_max_rows(max_rows, limits)
    url = _service_url(service, "ssa", servers)
    ra, dec = _icrs_degrees(center)
    r = _radius_degrees(radius)
    query = pyvo.dal.ssa.SSAQuery(url, (ra, dec), diameter=2 * r * u.deg)
    query["MAXREC"] = max_rows
    response = _http("ssa", url, dict(query), cache=cache, refresh=refresh, timeouts=timeouts, accept_error_body=True)
    parsed = _parse_results(response, pyvo.dal.SSAResults)
    arguments = {"center": {"ra_deg": ra, "dec_deg": dec, "frame": "icrs"}, "radius": {"value": r, "unit": "deg"},
                 "service": service, "max_rows": max_rows}
    result = _finish("ssa", "ssa_search", arguments, response, parsed, max_rows=max_rows, limits=limits, cache=cache)
    return _no_result(result, "SSA_NO_RESULT", "o spettro")


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
                               f"colonna per asse); colonne: {', '.join(table.colnames)}", url=origin)
    for name in (spectral, flux):
        if table[name].unit is None:
            raise VoProtocolsError("SSA_INVALID", f"{origin}: colonna {name!r} senza unità valida", url=origin)
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
                                   "(utype ssa:Access.Reference o UCD meta.ref.url)")
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
        raise VoProtocolsError("SSA_INVALID", f"{url}: spettro non leggibile ({exc.message})", url=url) from exc
    if table.format not in ("votable", "fits"):
        raise VoProtocolsError("SSA_INVALID", f"{url}: formato {table.format} (ammessi VOTable Spectrum DM e FITS)",
                               url=url)
    data = _flatten_single_row(table.table)
    spectral, flux, error = _spectrum_columns(data, table.format, url)
    out = Table()
    out["spectral"] = data[spectral]
    out["flux"] = data[flux]
    if error is not None:
        out["flux_error"] = data[error]
    notes = response.notes + _store(response, "ssa-spectrum", cache)
    if body is None:
        notes += (("BODY_UNKNOWN", "corpo non ricavabile: spettro caricato da URL senza il candidato di ssa_search"),)
    if declared and table.format not in declared.lower() and not (table.format == "votable" and "xml" in declared):
        notes += (("FORMAT_DECLARED", f"formato dichiarato {declared!r}, riconosciuto dal contenuto: {table.format}"),)
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
        value = row[name]
        return None if np.ma.is_masked(value) or not np.isfinite(float(value)) else float(value)

    magnitudes, notes = [], []
    for row in data:
        value = number(row, "flux")
        if value is None:
            continue
        code = text(row, "system")
        system = SIMBAD_FLUX_SYSTEMS.get(code) if code else None
        if code and system is None:
            notes.append(("SIMBAD_SYSTEM_UNKNOWN", f"banda {text(row, 'filter')}: codice di sistema {code!r} "
                          "non documentato da SIMBAD, sistema non dichiarato"))
        magnitudes.append(SimbadMagnitude(band=text(row, "filter") or "", description=text(row, "description"),
                                          value=value, error=number(row, "flux_err"), unit=text(row, "unit"),
                                          system=system, quality=text(row, "qual"), bibcode=text(row, "bibcode")))
    magnitudes.sort(key=lambda m: (m.band, m.bibcode or ""))  # ordine stabile, indipendente dal servizio
    undeclared = [m.band for m in magnitudes if m.system is None]
    if undeclared:
        notes.append(("SIMBAD_SYSTEM_UNDECLARED", f"bande senza sistema dichiarato da SIMBAD: {', '.join(undeclared)}"))
    return tuple(magnitudes), result, tuple(notes)


def _query_simbad_region(ra: float, dec: float, radius_deg: float, timeouts: NetworkTimeouts) -> tuple[Table, str]:
    """Interroga SIMBAD con ``astroquery`` (sessione con i timeout comuni del modulo 10); (tabella, URL TAP)."""
    from astrotwo.core.coordinates_wcs import _simbad_with_timeouts  # unico punto con il campo interno di astroquery

    simbad = _simbad_with_timeouts(timeouts)
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
                             cached.retrieved_at, True, (("FROM_CACHE", f"copia in cache del {_iso(cached.retrieved_at)}"),))
    else:
        try:
            table, url = _query_simbad_region(ra, dec, r, timeouts)
        except (requests.exceptions.RequestException, pyvo.dal.DALServiceError, OSError) as exc:
            if cached is None:
                raise _net_error("SIMBAD", exc, timeouts) from exc
            response = _Response(cached.data["payload"], cached.data["url"], "astroquery", canonical,
                                 cached.retrieved_at, True,
                                 (("FROM_CACHE", f"rete non disponibile ({type(exc).__name__}): copia in cache"),))
        else:
            response = _Response(_table_bytes(table), url, "astroquery", canonical, datetime.now(UTC), False)
            try:
                rows.put(key, {"protocol": "simbad", "url": url, "params": json.dumps(canonical),
                               "payload": response.payload}, origin=url, retrieved_at=response.retrieved_at)
            except CacheError as exc:
                notes += ((exc.code, exc.message),)
    found = _read_payload(response).table
    notes = response.notes + notes
    arguments = {"center": {"ra_deg": ra, "dec_deg": dec, "frame": "icrs"}, "radius": {"value": r, "unit": "deg"}}
    record = _record("simbad", "simbad_pointer", arguments, response, len(found))
    source = f"SIMBAD (CDS) via astroquery; {SIMBAD_COORDINATES_NOTE}"
    if len(found) == 0:
        return SimbadPointer(None, 0, source, record,
                             notes + (("SIMBAD_NO_OBJECT", f"nessun oggetto SIMBAD entro {r * 3600:g} arcsec"),))
    ra_col = (found["ra"].quantity if found["ra"].unit is not None else None)
    if ra_col is None or found["dec"].unit is None:
        raise VoProtocolsError("SERVICE_ERROR", "SIMBAD: coordinate senza unità nella risposta")
    from astropy.coordinates import angular_separation

    sep = angular_separation(ra * u.deg, dec * u.deg, ra_col, found["dec"].quantity).to(u.arcsec)
    nbref = np.ma.masked_invalid(np.ma.asarray(found["nbref"], dtype=float))
    valid = ~np.ma.getmaskarray(nbref)
    if valid.any():
        best = nbref[valid].max()
        tied = np.flatnonzero(valid & (np.ma.filled(nbref, -1) == best))
    else:
        tied = np.arange(len(found))
        notes += (("SIMBAD_NBREF_MISSING", "numero di citazioni assente per tutti gli oggetti: scelto il più vicino"),)
    order = sorted(tied, key=lambda k: (float(sep[k].value), str(found["main_id"][k])))
    choice = order[0]
    if len(tied) > 1:
        notes += (("SIMBAD_TIE", f"{len(tied)} oggetti con lo stesso numero di citazioni "
                   f"({'—' if not valid.any() else int(best)}): scelto il più vicino al centro, "
                   f"{found['main_id'][choice]} a {sep[choice].value:.3f} arcsec"),)
    row = found[choice]
    coords = SkyFrame.from_lonlat(float(ra_col[choice].to_value(u.deg)) * u.deg,
                                  float(found["dec"].quantity[choice].to_value(u.deg)) * u.deg, "icrs",
                                  epoch=Time("J2000.0"))
    otype = None if np.ma.is_masked(row["otype"]) else str(row["otype"])
    magnitudes, mag_result, mag_notes = _simbad_magnitudes(str(row["main_id"]), cache=cache, refresh=refresh,
                                                           timeouts=timeouts)
    notes += tuple(w for w in mag_result.warnings if w[0] == "FROM_CACHE") + mag_notes
    if not magnitudes:
        notes += (("SIMBAD_NO_MAGNITUDE", f"nessuna magnitudine in SIMBAD per {row['main_id']}"),)
    obj = SimbadObject(main_id=str(row["main_id"]), otype=otype, coords=coords,
                       nbref=None if not valid[choice] else int(nbref[choice]), separation=sep[choice],
                       magnitudes=magnitudes)
    return SimbadPointer(obj, len(found), source, record, notes, magnitudes_request=mag_result.request)


#: MocServer del CDS (D13-18): elenco delle collezioni VizieR con le loro proprietà (verificato il 2026-10-11).
MOCSERVER_URL = "https://alasky.cds.unistra.fr/MocServer/query"
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
    response = _http("mocserver", MOCSERVER_URL, params, cache=cache, refresh=refresh, timeouts=timeouts)
    try:
        records = json.loads(response.payload.decode("utf-8"))
        if not isinstance(records, list) or not all(isinstance(r, dict) and isinstance(r.get("ID"), str)
                                                    for r in records):
            raise ValueError("attesa una lista di record con ID")
    except (UnicodeDecodeError, ValueError) as exc:
        raise VoProtocolsError("SERVICE_ERROR", f"{MOCSERVER_URL}: risposta non leggibile ({exc})",
                               url=MOCSERVER_URL) from exc
    notes = response.notes + _store(response, "mocserver", cache)
    record = _record("mocserver", "vizier_collections", {}, response, len(records))
    return MocServerRecords(records=tuple(records), request=record, warnings=notes)


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
        raise VoProtocolsError("VOTABLE_INVALID", f"{VIZIER_PHOTOMETRY_URL}: risposta senza le colonne {missing}")
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


@dataclass(frozen=True)
class SampSendResult:
    """Esito di un invio: tipo di messaggio e destinatari raggiunti."""

    mtype: str
    recipients: tuple[str, ...]


@dataclass(frozen=True)
class SampSelection:
    """Selezione ricevuta o da inviare: tabella (identificativo e URL) e righe (indici da 0)."""

    table_id: str
    url: str
    rows: tuple[int, ...]


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

    # -- collegamento ---------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    def connect(self) -> SampHub:
        """Si collega all'hub attivo; se non c'è ne avvia uno proprio; altrimenti ``SAMP_UNAVAILABLE``."""
        from pyvo.samp import SAMPHubError, SAMPHubServer, SAMPIntegratedClient

        if self.connected:
            return self
        client = SAMPIntegratedClient(name=self.name, description=f"AstroTwo {astrotwo.__version__}",
                                      metadata={"samp.name": self.name})
        try:
            client.connect()
        except (SAMPHubError, OSError):
            try:
                hub = SAMPHubServer(web_profile=self.web_profile, label=self.name)
                hub.start(wait=False)
                client.connect()
            except Exception as exc:
                raise VoProtocolsError("SAMP_UNAVAILABLE", f"nessun hub SAMP attivo e avvio del proprio non riuscito "
                                       f"({exc}); le altre funzioni VO restano disponibili") from exc
            self._hub, self.own_hub = hub, True
        self._client = client
        for mtype, function in (("table.load.votable", self._receive_table),
                                ("table.select.rowList", self._receive_selection),
                                ("coord.pointAt.sky", self._receive_point)):
            client.bind_receive_notification(mtype, function)
            client.bind_receive_call(mtype, function)
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
            raise VoProtocolsError("SAMP_UNAVAILABLE", "non collegato a un hub SAMP: chiamare connect()")
        return self._client

    def clients(self) -> tuple[SampClient, ...]:
        """Programmi collegati (escluso AstroTwo e l'hub)."""
        client = self._require()
        out = []
        for cid in client.get_registered_clients():
            if cid == "cli#hub":
                continue
            name = client.get_metadata(cid).get("samp.name")
            out.append(SampClient(id=cid, name=None if name is None else str(name)))
        return tuple(out)

    # -- invio ----------------------------------------------------------------

    def send_message(self, mtype: str, params: dict, recipient: str | None = None) -> SampSendResult:
        """Invia uno dei tipi supportati; altri tipi → ``SAMP_UNSUPPORTED_TYPE``; nessun destinatario → ``SAMP_NO_PEER``."""
        if mtype not in SAMP_MTYPES:
            raise VoProtocolsError("SAMP_UNSUPPORTED_TYPE",
                                   f"tipo {mtype!r} non supportato; supportati: {', '.join(SAMP_MTYPES)}")
        client = self._require()
        subscribed = set(client.get_subscribed_clients(mtype)) - {client.get_public_id()}
        if recipient is not None:
            if recipient not in subscribed:
                raise VoProtocolsError("SAMP_NO_PEER", f"{recipient!r} non è collegato o non accetta {mtype}")
            targets = [recipient]
        else:
            targets = sorted(subscribed)
        if not targets:
            raise VoProtocolsError("SAMP_NO_PEER", f"nessun programma collegato accetta {mtype}")
        message = {"samp.mtype": mtype, "samp.params": {k: v for k, v in params.items()}}
        for target in targets:
            client.notify(target, message)
        return SampSendResult(mtype=mtype, recipients=tuple(targets))

    def send_table(self, table: CatalogTable, *, table_id: str, name: str | None = None,
                   recipient: str | None = None) -> SampSendResult:
        """``table.load.votable``: la tabella si scrive in un VOTable temporaneo con provenienza (P1)."""
        self._require()
        if self._tmpdir is None:
            self._tmpdir = tempfile.TemporaryDirectory(prefix="astrotwo-samp-")
        path = export_table(table, Path(self._tmpdir.name) / f"{len(os.listdir(self._tmpdir.name))}.xml",
                            "votable").path
        params = {"url": path.resolve().as_uri(), "table-id": table_id, "name": name or table_id}
        return self.send_message("table.load.votable", params, recipient)

    def send_selection(self, selection: SampSelection, recipient: str | None = None) -> SampSendResult:
        """``table.select.rowList``: righe con indice da 0, come chiede il messaggio SAMP."""
        rows = [str(int(k)) for k in selection.rows]
        params = {"table-id": selection.table_id, "url": selection.url, "row-list": rows}
        return self.send_message("table.select.rowList", params, recipient)

    def send_point(self, center, recipient: str | None = None) -> SampSendResult:
        """``coord.pointAt.sky``: posizione in gradi ICRS (conversione del modulo 10)."""
        ra, dec = _icrs_degrees(center)
        return self.send_message("coord.pointAt.sky", {"ra": repr(ra), "dec": repr(dec)}, recipient)

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
                raise VoProtocolsError("SAMP_UNSUPPORTED_TYPE", f"nessuna funzione registrata per {mtype}")
            handler(*build())
        except Exception as exc:  # l'errore torna al mittente, il collegamento resta attivo
            self._reply(msg_id, exc)
            return
        self._reply(msg_id, None)

    def _receive_table(self, private_key, sender_id, msg_id, mtype, params, extra) -> None:
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
