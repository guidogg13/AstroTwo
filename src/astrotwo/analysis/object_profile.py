# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Profilo di un oggetto (livello 2): bersaglio, identificativi, identità, astrometria, distanza; ``object.profile``.

Specifica: ``mdfiles/25-analisi-profilo-oggetto.md`` (stato ``approvato``), in particolare §3.10 (sprint C2).

Nessun numero nasce qui fuori da codice deterministico (regola d'oro n. 1): i valori sono **letti** dai servizi
(con unità, errore e riferimento) oppure **calcolati** da ``distance_from`` (distanza da parallasse con
``astropy.units.parallax``), con il metodo scritto nel valore. Ogni valore porta la sua provenienza (servizio, server
che ha risposto, tabella, interrogazione ADQL, identificativo usato, tipo di incrocio, data, cache).

Le sezioni sono indipendenti (regola c): l'errore di un servizio resta nella sua sezione. Sprint C4 (25 §3.12): le
sezioni partono insieme dopo la risoluzione del bersaglio, al più 4 richieste di rete contemporanee, tempo massimo per
servizio e per sezione, Annulla con le sezioni arrivate conservate. Sprint C3 (25 §3.11): sezione ``photometry`` con i punti e la SED del ``20``
(``astrotwo.analysis.photometry``), passo per posizione di 2MASS e AllWISE nella catena, pianeti esclusi dai
candidati da coordinate (D25-13 (8)). Il comando ``object.profile`` è definito qui (comando del livello 2,
05 §3.2): il 05 non importa questo modulo, lo riceve con ``register`` da chi costruisce il registro (``40``).
"""

from __future__ import annotations

import contextlib
import contextvars
import dataclasses
import queue
import re
import threading
import time
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.time import Time

from astrotwo.analysis.photometry import (
    VIZIER_SED_RADIUS,
    Sed,
    VizierSeries,
    build_sed,
    high_proper_motion,
    sed_png,
    sed_points_from,
)
from astrotwo.core.cache import NETWORK_TIMEOUTS, NetworkTimeouts, SharedCache
from astrotwo.core.coordinates_wcs import ModuleWarning, SkyFrame, propagate_position, resolve_name
from astrotwo.core.vo_protocols import (
    RequestRecord,
    SimbadRecord,
    VoProtocolsError,
    cone_search,
    cpu_turn,
    network_wait,
    refresh_once,
    is_failover_error,
    simbad_object,
    tap_query,
    tap_query_cached,
    vizier_photometry,
    vizier_photometry_cached,
)

__all__ = [
    "ALLWISE_EPOCH",
    "BAILER_JONES_REFERENCE",
    "CATALOGS",
    "DEFAULT_CROSSMATCH_RADIUS",
    "DEFAULT_MATCH_RADIUS",
    "DEFAULT_THUMBNAIL_FOV",
    "DEFAULT_THUMBNAIL_SIZE",
    "DESIGNATION_RADIUS",
    "IMAGE_SURVEYS",
    "PLANET_PARAMETERS",
    "GAIA_DR3_EPOCH",
    "MAX_CONCURRENT_REQUESTS",
    "PARALLAX_SNR_MIN",
    "PM_SEARCH_MAX",
    "PROFILE_TARGET_TIME",
    "SECTIONS",
    "SECTION_SERVICES",
    "SERVICE_TIME_LIMITS",
    "TMASS_OBSERVATIONS",
    "CrossIdentification",
    "ObjectProfile",
    "ObjectProfileError",
    "ProfileSection",
    "ProfileTarget",
    "ProfileValue",
    "Provenance",
    "ResolvedTarget",
    "TargetCandidates",
    "build_profile",
    "command_specs",
    "cross_identify",
    "model_view",
    "distance_from",
    "profile_astrometry",
    "profile_content",
    "parse_reflink",
    "profile_identity",
    "profile_images",
    "profile_photometry",
    "profile_planets",
    "resolve_target",
]

#: Sezioni del profilo nell'ordine di §3.4 (C2 identità e astrometria, C3 fotometria, C4 immagini e pianeti, §3.13).
SECTIONS: tuple[str, ...] = ("identity", "images", "astrometry", "photometry", "planets")
#: Survey delle miniature (D25-5): AllWISE colore perché il mirror ESASky è stato verificato il 2026-11-07 (§3.13).
IMAGE_SURVEYS: tuple[str, ...] = ("CDS/P/DSS2/color", "CDS/P/2MASS/color", "CDS/P/allWISE/color")
#: Campo e dimensione delle miniature (D25-5).
DEFAULT_THUMBNAIL_FOV = 5.0 * u.arcmin
DEFAULT_THUMBNAIL_SIZE = 256
#: Cataloghi della catena degli identificativi (25 §3.2).
CATALOGS: tuple[str, ...] = ("gaia_dr3", "2mass", "allwise", "exoplanet")
#: Raggio dei candidati SIMBAD da coordinate (D25-9).
DEFAULT_MATCH_RADIUS = 10.0 * u.arcsec
#: Raggio degli incroci per posizione dopo la propagazione (D25-9).
DEFAULT_CROSSMATCH_RADIUS = 2.0 * u.arcsec
#: Moto proprio massimo per allargare la ricerca dei candidati: sopra la stella di Barnard, 10,393″/anno da SIMBAD
#: (``pm_bibcode`` 2020yCat.1350....0G, letto il 2026-11-07; 25 §3.10).
PM_SEARCH_MAX = 10.5 * u.arcsec / u.yr
#: Rapporto minimo parallasse/errore per la distanza 1/ϖ (errore relativo ≤ 10 %, D25-2).
PARALLAX_SNR_MIN = 10.0
#: Epoca di riferimento di Gaia DR3 (``ref_epoch`` = 2016.0, anno giuliano in TCB, modello dei dati di Gaia DR3).
GAIA_DR3_EPOCH = Time(2016.0, format="jyear", scale="tcb")
#: Distanze di Bailer-Jones et al. (2021, AJ 161, 147) da Gaia EDR3 (D25-2).
BAILER_JONES_REFERENCE = "2021AJ....161..147B"
_SIMBAD_EPOCH = Time("J2000.0")
#: Epoca delle posizioni AllWISE: MJD 55400,0 UTC (2010,5589), AllWISE Explanatory Supplement §II.1 (25 §3.11).
ALLWISE_EPOCH = Time(55400.0, format="mjd", scale="utc")
#: Periodo delle osservazioni 2MASS (giugno 1997 – febbraio 2001, 2MASS Explanatory Supplement §I.1; 25 §3.11).
TMASS_OBSERVATIONS = (Time("1997-06-01", scale="utc"), Time("2001-03-01", scale="utc"))
#: Raggio attorno alla posizione scritta nella designazione 2MASS/AllWISE (posizione troncata; 25 §3.11).
DESIGNATION_RADIUS = 2.0 * u.arcsec

#: Al più 4 richieste di rete contemporanee in tutto il profilo (D25-8, 25 §3.12 regola 3).
MAX_CONCURRENT_REQUESTS = 4
#: Al più 2 richieste contemporanee per servizio, dentro le 4 (D25-21 (5), 25 §3.17 punto 5).
MAX_REQUESTS_PER_SERVICE = 2
#: Tempo massimo per servizio (D25-8, D25-15; 25 §3.12): per ogni richiesta e, attraverso ``SECTION_SERVICES``, per
#: ogni sezione. HiPS vale per la sezione Immagini, quando scritta.
SERVICE_TIME_LIMITS: Mapping[str, u.Quantity] = {
    "simbad": 15.0 * u.s, "gaia": 30.0 * u.s, "irsa": 60.0 * u.s, "exoplanet": 30.0 * u.s, "hips": 30.0 * u.s,
    "vizier_sed": 30.0 * u.s}
#: Tempo massimo di una sezione diverso dal più grande dei suoi servizi (D25-22 (12 b), 25 §3.17): Astrometria 35 s,
#: oltre i 30 s per richiesta di Gaia, perché l'errore di rete arrivi prima della scadenza.
SECTION_TIME_LIMITS: Mapping[str, u.Quantity] = {"astrometry": 35.0 * u.s}
#: Servizi le cui richieste non partono più dopo un guasto nello stesso profilo (D25-22 (12 a), 25 §3.17).
SKIP_AFTER_FAILURE: tuple[str, ...] = ("gaia",)
#: Servizi che ogni sezione può interrogare (25 §3.12 regola 5): il tempo massimo della sezione è il più grande.
SECTION_SERVICES: Mapping[str, tuple[str, ...]] = {
    "identity": ("simbad", "gaia", "irsa", "exoplanet"), "astrometry": ("gaia",),
    "photometry": ("gaia", "irsa", "vizier_sed"), "images": ("hips",), "planets": ("exoplanet",)}
#: Obiettivo complessivo (D25-8): misurato e scritto nel risultato (``elapsed``), non è un limite (25 §3.12).
PROFILE_TARGET_TIME = 60.0 * u.s

_SIMBAD_TAP = "cds-simbad-tap"
_GAIA_TAP = "esa-gaia-tap"
_EXOPLANET_TAP = "nasa-exoplanet-tap"
_GAIA_SOURCE = "gaiadr3.gaia_source"
_BJ_TABLE = "external.gaiaedr3_distance"
_IRSA_TAP = "nasa-irsa-tap"
_SERVICE_OF = {_SIMBAD_TAP: "simbad", _GAIA_TAP: "gaia", _IRSA_TAP: "irsa", _EXOPLANET_TAP: "exoplanet"}
_POLL = 0.05  # s: intervallo di controllo di Annulla e delle scadenze (25 §3.12 regola 7)
_WORKERS = 24  # thread del profilo: risoluzione, incroci, 5 sezioni, 4 richieste della fotometria, 3 miniature (fino
               # a 17 insieme, mai in attesa reciproca senza un thread libero; 25 §3.16 C7-g); le richieste
               # contemporanee le limita il semaforo
_IRSA_TABLE = {"2mass": "fp_psc", "allwise": "allwise_p3as_psd"}
#: Cone Search di IRSA per 2MASS e AllWISE (D25-21 (1), 25 §3.17 punto 1): ``?table=<tabella>``; stesse colonne,
#: unità e tipi del TAP verificati il 2026-11-09.
_IRSA_SCS = "https://irsa.ipac.caltech.edu/SCS"
_IRSA_COLUMNS = {
    "2mass": "designation, ra, dec, j_m, j_msigcom, h_m, h_msigcom, k_m, k_msigcom, ph_qual, rd_flg, cc_flg, jdate",
    "allwise": "designation, ra, dec, w1mpro, w1sigmpro, w2mpro, w2sigmpro, w3mpro, w3sigmpro, w4mpro, w4sigmpro, "
               "ph_qual, cc_flags, ext_flg"}
_GAIA_PHOT_COLUMNS = ("source_id", "phot_g_mean_mag", "phot_g_mean_flux", "phot_g_mean_flux_error", "phot_bp_mean_mag",
                      "phot_bp_mean_flux", "phot_bp_mean_flux_error", "phot_rp_mean_mag", "phot_rp_mean_flux",
                      "phot_rp_mean_flux_error", "phot_variable_flag", "phot_bp_rp_excess_factor")
_OFFICIAL = {"2mass": "gaiadr3.tmass_psc_xsc_best_neighbour", "allwise": "gaiadr3.allwise_best_neighbour"}
_SIMBAD_PREFIX = {"gaia_dr3": "Gaia DR3 ", "2mass": "2MASS J", "allwise": "WISEA "}
_NAME_PREFIXES = ("NAME ", "V* ", "** ", "* ")
_ZERO_POINT_NOTE = "no parallax zero-point correction (D25-10)"
_RUWE_NOTE = "RUWE without a threshold: no threshold from a verified official Gaia source (D25-11)"


class ObjectProfileError(Exception):
    """Errore del profilo con codice della specifica (25 §10) e ``params`` (D40-3)."""

    def __init__(self, code: str, message: str, *, params: Mapping[str, object] | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.params = dict(params or {})


def _qj(value: u.Quantity, unit: str | None = None) -> dict:
    """Valore con unità in forma JSON per i ``params``, mai arrotondato."""
    q = value.to(unit) if unit else value
    return {"value": float(q.value), "unit": q.unit.to_string()}


def _iso(moment: datetime | None) -> str | None:
    return None if moment is None else moment.isoformat()


def _message(exc: BaseException) -> dict:
    """Errore di un modulo come messaggio (codice, testo, ``params``), invariato."""
    return {"code": getattr(exc, "code", type(exc).__name__), "text": getattr(exc, "message", str(exc)),
            "params": dict(getattr(exc, "params", None) or {})}


def _warning_json(item) -> dict:
    return {"code": item[0], "text": item[1], "params": dict(getattr(item, "params", None) or {})}


# --------------------------------------------------------------------------
# Valori con provenienza (25 §7.1, §3.10)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Provenance:
    """Da dove viene un valore: servizio e server che ha risposto, tabella, ADQL, identificativo, incrocio, data."""

    service: str
    server: str
    table: str | None
    query: str | None
    identifier: str | None
    match: str | None  # simbad_identifier | official_crossmatch | position | None
    retrieved_at: datetime | None
    from_cache: bool | None

    def as_dict(self) -> dict:
        return {"service": self.service, "server": self.server, "table": self.table, "query": self.query,
                "identifier": self.identifier, "match": self.match, "retrieved_at": _iso(self.retrieved_at),
                "from_cache": self.from_cache}


@dataclass(frozen=True)
class ProfileValue:
    """Una grandezza del profilo: valore (``Quantity`` ``float64``, testo, intero o booleano), errori, metodo, fonte.

    ``interval``: limiti inferiore e superiore (``interval_kind`` dice quali: percentili 16°–84° di Bailer-Jones o
    1/(ϖ ± σ)). ``method``: ``read`` (letto dal servizio) o ``computed`` (``formula`` dice come)."""

    quantity: str
    value: object
    provenance: Provenance
    error: u.Quantity | None = None
    interval: tuple[u.Quantity, u.Quantity] | None = None
    interval_kind: str | None = None
    method: str = "read"
    formula: str | None = None
    reference: str | None = None
    note: str | None = None
    error_upper: u.Quantity | None = None  # errori asimmetrici così come dati dal servizio (pianeti, §3.13)
    error_lower: u.Quantity | None = None

    def as_dict(self) -> dict:
        from astrotwo.core.commands import quantity_json

        def plain(v):
            if isinstance(v, u.Quantity):
                return quantity_json(v)
            if isinstance(v, (np.bool_, bool)):
                return bool(v)
            if isinstance(v, (np.integer,)):
                return int(v)
            return v

        return {"quantity": self.quantity, "value": plain(self.value), "error": plain(self.error),
                "interval": None if self.interval is None else [plain(self.interval[0]), plain(self.interval[1])],
                "interval_kind": self.interval_kind, "method": self.method, "formula": self.formula,
                "reference": self.reference, "note": self.note, "provenance": self.provenance.as_dict(),
                **({"error_upper": plain(self.error_upper), "error_lower": plain(self.error_lower)}
                   if self.error_upper is not None or self.error_lower is not None else {})}


def _provenance(request: RequestRecord, service: str, table: str | None, query: str | None,
                identifier: str | None, match: str | None) -> Provenance:
    return Provenance(service=service, server=request.url, table=table, query=query, identifier=identifier,
                      match=match, retrieved_at=request.retrieved_at, from_cache=request.from_cache)


def _record_service(record) -> str:
    """Servizio di un oggetto SIMBAD del 14 con il nome inglese del profilo (DD-3 (a)): dal server che ha risposto,
    non dall'etichetta del modulo sotto."""
    return _service_name(record.requests[0].url) if record.requests else str(record.source)


def _resolver_label(resolved) -> str:
    """Nome del servizio che ha risolto il nome (etichetta inglese del 10, prima di «via astroquery» o
    «ObjectLookup»), senza la nota sul sistema scritta dal 10 in italiano (DD-3 (a))."""
    return re.split(r" via astroquery| ObjectLookup", str(resolved.source))[0].strip() or str(resolved.source)


def _resolver_source(resolved) -> str:
    """Fonte della posizione da un risolutore di nomi del 10, in inglese (DD-3 (a)): servizio, sistema ed epoca come
    li dichiara il 10 (SIMBAD: ICRS J2000; NED: FK5 J2000, epoca non dichiarata), server che ha risposto."""
    servers = re.findall(r"https?://[^\s)]+", str(resolved.origin))
    frame = resolved.coords.frame_name
    system = "ICRS J2000" if frame == "icrs" else f"{frame.upper()} J2000, epoch not declared"
    return f"{_resolver_label(resolved)}, name resolver, {system}" + (f" ({servers[-1]})" if servers else "")


def _english(note) -> str:
    """Testo inglese di un avviso (codice e ``params``) dal catalogo dei messaggi (DD-3 (a), D40-5)."""
    from astrotwo.messages_catalog import message_text

    return message_text(note[0], dict(getattr(note, "params", None) or {}), "en", text=note[1])


def _service_name(url: str) -> str:
    host = urllib.parse.urlparse(url).hostname or url
    if "simbad" in host:
        return "SIMBAD (Harvard mirror)" if "harvard" in host else "SIMBAD (CDS)"
    if "gea.esac.esa.int" in host:
        return "Gaia archive (ESA)"
    if "skies.esac.esa.int" in host:
        return "ESASky (ESA)"
    if "exoplanetarchive" in host:
        return "NASA Exoplanet Archive"
    if "irsa" in host:
        return "IRSA (NASA/IPAC)"
    if "vizier" in host:
        return "VizieR (CDS)"
    return host


# --------------------------------------------------------------------------
# Bersaglio (25 §3.2, §3.10)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ProfileTarget:
    """Il bersaglio come scritto: un nome, oppure una posizione con sistema ed epoca; ``simbad_id`` se già risolto."""

    name: str | None = None
    position: SkyFrame | None = None
    simbad_id: str | None = None
    origin: str | None = None  # es. "riga 3 del livello L2" (solo descrizione)

    def as_dict(self) -> dict:
        from astrotwo.core.commands import sky_json

        return {"name": self.name, "position": None if self.position is None else sky_json(self.position),
                "simbad_id": self.simbad_id, "origin": self.origin}


@dataclass(frozen=True)
class ResolvedTarget:
    """Bersaglio risolto: oggetto SIMBAD (con identificativi) oppure solo una posizione, con epoca e fonte."""

    target: ProfileTarget
    simbad: SimbadRecord | None
    position: SkyFrame
    position_source: str
    method: str  # simbad_identifier | simbad_candidate | name_resolver | position
    separation: u.Quantity | None = None
    simbad_error: dict | None = None
    warnings: tuple[ModuleWarning, ...] = ()
    requests: tuple[RequestRecord, ...] = ()

    def as_dict(self) -> dict:
        from astrotwo.core.commands import quantity_json, sky_json

        return {"method": self.method, "main_id": None if self.simbad is None else self.simbad.main_id,
                "position": sky_json(self.position), "position_source": self.position_source,
                "separation": None if self.separation is None else quantity_json(self.separation.to(u.arcsec)),
                "simbad_error": self.simbad_error}


@dataclass(frozen=True)
class TargetCandidates:
    """Più oggetti SIMBAD entro il raggio: l'utente sceglie (nessuna scelta silenziosa, regola a)."""

    target: ProfileTarget
    radius: u.Quantity
    candidates: tuple[dict, ...]  # main_id, otype, separation (arcsec, forma JSON), nbref, propagated
    requests: tuple[RequestRecord, ...] = ()
    warnings: tuple[ModuleWarning, ...] = ()  # es. PROFILE_PLANETS_EXCLUDED


def _column(table, name: str) -> str:
    """Nome effettivo di una colonna senza badare a maiuscole (l'archivio Gaia restituisce ``SOURCE_ID``)."""
    for col in table.colnames:
        if col.lower() == name.lower():
            return col
    raise KeyError(name)


def _value(row, name: str):
    """Cella: ``None`` se vuota; ``Quantity`` con l'unità dichiarata; float32 al decimale scritto dal servizio."""
    col = _column(row.table, name)
    value = row[col]
    if np.ma.is_masked(value):
        return None
    unit = row.table[col].unit
    if isinstance(value, (bytes, str, np.str_, np.bytes_)):
        text = value.decode() if isinstance(value, bytes) else str(value)
        return text.strip() or None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)) and unit is None:
        return int(value)
    number = float(str(value)) if isinstance(value, np.float32) else float(value)
    if not np.isfinite(number):
        return None
    return number * unit if unit is not None else number


def _network_notes(items) -> tuple:
    """Avvisi di rete del 14 (cache, mirror); quelli delle magnitudini SIMBAD sono della fotometria (sprint C3)."""
    return tuple(w for w in items if w[0] in ("FROM_CACHE", "SERVICE_MIRROR_FALLBACK"))


def _years_between(a: Time, b: Time) -> float:
    return float((a - b).to_value(u.yr))


def _cancelled(cancel: Callable[[], bool] | None) -> bool:
    return bool(cancel is not None and cancel())


class _Cancelled(Exception):
    pass


def _check(cancel) -> None:
    if _cancelled(cancel):
        raise _Cancelled()


# --------------------------------------------------------------------------
# Esecuzione parallela (25 §3.12): semaforo delle richieste, tempi per servizio, thread, cache per thread
# --------------------------------------------------------------------------


class _Run:
    """Un profilo in esecuzione: thread di lavoro, semaforo delle richieste di rete, segnale di arresto, turno della
    CPU (``cpu_turn`` del 14: un thread alla volta lavora, le attese di rete sono parallele; 25 §3.12 regola 10)."""

    def __init__(self) -> None:
        self.gate = threading.BoundedSemaphore(MAX_CONCURRENT_REQUESTS)
        self.service_gates = {s: threading.BoundedSemaphore(MAX_REQUESTS_PER_SERVICE) for s in SERVICE_TIME_LIMITS}
        self.down: dict[str, dict] = {}  # servizio → prova del guasto nel profilo (D25-22 (12 a))
        self.skipped: dict[str, int] = {}  # servizio → richieste non inviate
        self.stop = threading.Event()
        self.cpu = threading.Lock()
        self.cpu_free = threading.Lock()  # stato dei guasti (``down``, ``skipped``), senza il turno della CPU
        self.pool = ThreadPoolExecutor(max_workers=_WORKERS, thread_name_prefix="astrotwo-profile")

    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        """Lavoro in un thread del profilo, con il turno della CPU e questo profilo come contesto (``_RUN``)."""
        def task():
            with cpu_turn(self.cpu):
                return fn(*args, **kwargs)

        context = contextvars.copy_context()
        context.run(_RUN.set, self)
        return self.pool.submit(context.run, task)

    def wait(self, future: Future):
        """Risultato di un lavoro, senza il turno della CPU durante l'attesa; arrestato → ``_Cancelled``."""
        with network_wait():
            while True:
                try:
                    return future.result(timeout=_POLL)
                except TimeoutError:
                    if self.stop.is_set():
                        raise _Cancelled() from None


_RUN: contextvars.ContextVar[_Run | None] = contextvars.ContextVar("astrotwo_profile_run", default=None)


def _limited(timeouts: NetworkTimeouts, service: str) -> NetworkTimeouts:
    """Timeout di una richiesta: il minimo tra quello del chiamante e il tempo massimo del servizio (§3.12 regola 4)."""
    limit = float(SERVICE_TIME_LIMITS[service].to_value(u.s))
    return NetworkTimeouts(connect=min(timeouts.connect, limit), read=min(timeouts.read, limit))


def _acquire(run: _Run, gate: threading.BoundedSemaphore) -> None:
    with network_wait():  # posto del semaforo atteso senza il turno della CPU
        while not gate.acquire(timeout=_POLL):
            if run.stop.is_set():
                raise _Cancelled()


def _skipped(run: _Run, service: str, cached: Callable[[], object] | None, refresh: bool):
    """Richiesta non inviata perché il servizio è già fermo nel profilo: copia in cache (senza ``refresh``) oppure
    ``PROFILE_GAIA_SKIPPED`` come errore di rete del servizio (D25-22 (12 a), 25 §3.17)."""
    hit = cached() if cached is not None and not refresh else None
    if hit is not None:
        return hit
    with run.cpu_free:
        run.skipped[service] = run.skipped.get(service, 0) + 1
    evidence = str(run.down[service]["evidence"])
    note = ObjectProfileError("PROFILE_GAIA_SKIPPED", f"archivio Gaia: richiesta non inviata, l'archivio non ha "
                              f"risposto in questo profilo ({evidence})",
                              params={"reason": "gaia_down", "evidence": evidence})
    # Messaggio del 25 portato come errore di rete del 14: ogni sezione lo tratta come un errore di Gaia.
    raise VoProtocolsError(note.code, note.message, params=dict(note.params))


def _network(service: str | None, function: Callable, *args, cached: Callable[[], object] | None = None, **kwargs):
    """Chiamata a un servizio del livello 1 con il tempo massimo del servizio e, dentro ``build_profile``, con un posto
    del suo servizio (``MAX_REQUESTS_PER_SERVICE``) e poi uno dei ``MAX_CONCURRENT_REQUESTS`` posti comuni (25 §3.12
    regole 3–4, §3.17 punto 5); profilo arrestato → ``_Cancelled``. Per i servizi di ``SKIP_AFTER_FAILURE``, dopo un
    guasto nel profilo la richiesta non parte (``cached``: copia in cache, D25-22 (12 a))."""
    if service is not None and "timeouts" in kwargs:
        kwargs["timeouts"] = _limited(kwargs["timeouts"], service)
    run = _RUN.get()
    if run is None:
        return function(*args, **kwargs)
    watched = service in SKIP_AFTER_FAILURE
    refresh = bool(kwargs.get("refresh"))
    if watched and service in run.down:
        return _skipped(run, service, cached, refresh)
    own = run.service_gates.get(service) if service is not None else None
    if own is not None:  # prima il posto del servizio: chi lo aspetta non tiene un posto comune
        _acquire(run, own)
    try:
        _acquire(run, run.gate)
        try:
            if run.stop.is_set():
                raise _Cancelled()
            if watched and service in run.down:  # guasto arrivato durante l'attesa del posto
                return _skipped(run, service, cached, refresh)
            try:
                return function(*args, **kwargs)
            except VoProtocolsError as exc:
                if watched and is_failover_error(exc):  # registrato prima di lasciare il posto
                    with run.cpu_free:
                        run.down.setdefault(service, {"evidence": exc.code})
                raise
        finally:
            run.gate.release()
    finally:
        if own is not None:
            own.release()


def _tap(service: str, adql: str, **kwargs):
    return _network(_SERVICE_OF[service], tap_query, service, adql,
                    cached=lambda: tap_query_cached(service, adql, cache=kwargs.get("cache")), **kwargs)


def _gather(functions: Sequence[Callable[[], object]]) -> list:
    """Esegue funzioni indipendenti insieme dentro ``build_profile`` (in fila fuori); risultati nell'ordine dato."""
    run = _RUN.get()
    if run is None:
        return [f() for f in functions]
    futures = [run.submit(f) for f in functions]
    return [run.wait(f) for f in futures]


class _ThreadCaches:
    """La ``SharedCache`` del 04 con un'istanza per thread sulla stessa cartella (la connessione ``sqlite3`` è legata
    al thread che la apre; 25 §3.12 regola 9): il thread di chi chiama usa l'istanza ricevuta."""

    def __init__(self, cache: SharedCache) -> None:
        self._main = cache
        self._owner = threading.get_ident()
        self._local = threading.local()

    def _cache(self) -> SharedCache:
        if threading.get_ident() == self._owner:
            return self._main
        cache = getattr(self._local, "cache", None)
        if cache is None:
            cache = self._local.cache = SharedCache(self._main.root, limit_bytes=self._main.limit_bytes,
                                                    orphan_min_age=self._main.orphan_min_age)
        return cache

    def __getattr__(self, name: str):
        return getattr(self._cache(), name)


def _simbad_candidates(position: SkyFrame, radius: u.Quantity, *, cache, refresh, timeouts):
    """Candidati SIMBAD per coordinate (25 §3.10): cerchio allargato da ``PM_SEARCH_MAX``, propagazione all'epoca."""
    icrs = position if position.frame_name == "icrs" else position.to("icrs")
    ra0, dec0 = float(icrs.lon.to_value(u.deg)), float(icrs.lat.to_value(u.deg))
    epoch = position.epoch
    dt = abs(_years_between(epoch, _SIMBAD_EPOCH)) if epoch is not None else 0.0
    search = (radius + (PM_SEARCH_MAX * dt * u.yr)).to(u.deg)
    adql = ("SELECT b.main_id, b.otype, b.ra, b.dec, b.pmra, b.pmdec, b.nbref, d.path FROM basic AS b "
            "LEFT OUTER JOIN otypedef AS d ON d.otype = b.otype WHERE CONTAINS(POINT('ICRS', b.ra, b.dec), "
            f"CIRCLE('ICRS', {ra0!r}, {dec0!r}, {float(search.value)!r})) = 1")
    result = _tap(_SIMBAD_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts)
    target = SkyCoord(ra0 * u.deg, dec0 * u.deg, frame="icrs")
    found, planets = [], []
    for row in result.table.table:
        ra, dec = _value(row, "ra"), _value(row, "dec")
        if ra is None or dec is None:
            continue
        here = SkyFrame.from_lonlat(ra.to(u.deg), dec.to(u.deg), "icrs", epoch=_SIMBAD_EPOCH)
        pmra, pmdec = _value(row, "pmra"), _value(row, "pmdec")
        propagated = False
        if epoch is not None and pmra is not None and pmdec is not None:
            here = propagate_position(here, pm_ra_cosdec=pmra, pm_dec=pmdec, parallax=None, target_epoch=epoch,
                                      proper_motion_only=True).position
            propagated = True
        sep = here.coord.separation(target).to(u.arcsec)
        if sep <= radius:
            item = {"main_id": _value(row, "main_id"), "otype": _value(row, "otype"),
                    "separation": _qj(sep, "arcsec"), "nbref": _value(row, "nbref"), "propagated": propagated}
            (planets if is_planet_path(_value(row, "path")) else found).append(item)
    def order(c):
        return (c["separation"]["value"], c["main_id"] or "")

    found.sort(key=order)
    planets.sort(key=order)
    notes = tuple(result.warnings)
    if planets:
        names = [" ".join(str(c["main_id"]).split()) for c in planets]
        notes += (ModuleWarning("PROFILE_PLANETS_EXCLUDED", f"{len(planets)} oggetti SIMBAD della famiglia dei "
                                f"pianeti esclusi dai candidati: {', '.join(names)}",
                                {"count": len(planets), "names": names}),)
    return tuple(found), result.request, notes


def is_planet_path(path: str | None) -> bool:
    """Vero se il percorso della gerarchia dei tipi di SIMBAD (``otypedef.path``, es. ``* > Pl``) contiene il nodo
    ``Pl`` (famiglia «Planet»: ``Pl`` e ``Pl?``, verificati il 2026-11-07; D25-13 (8))."""
    return path is not None and "Pl" in [part.strip() for part in str(path).split(">")]


def resolve_target(target: ProfileTarget, *, match_radius: u.Quantity = DEFAULT_MATCH_RADIUS,
                   cache: SharedCache | None = None, refresh: bool = False,
                   timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> ResolvedTarget | TargetCandidates:
    """Dal nome, dall'identificativo SIMBAD o dalle coordinate all'oggetto (25 §3.2, §3.10).

    ``NAME_NOT_FOUND`` sale invariato; SIMBAD giù su tutti i server → ``resolve_name`` del 10 e profilo per posizione
    con ``PROFILE_NO_IDENTIFIERS``. Più candidati da coordinate → ``TargetCandidates`` (nessuna scelta)."""
    given = [x for x in (target.simbad_id or target.name, target.position) if x is not None]
    if not given:
        raise ObjectProfileError("PROFILE_TARGET_INVALID", "nessun bersaglio: serve un nome o una posizione",
                                 params={"reason": "none"})
    if target.name is not None and target.position is not None:
        raise ObjectProfileError("PROFILE_TARGET_INVALID", "un solo bersaglio: un nome oppure una posizione",
                                 params={"reason": "several"})
    identifier = target.name or target.simbad_id  # con un nome: stessa richiesta del comando registrato (A7)
    if identifier is not None:
        try:
            record = _network("simbad", simbad_object, identifier, cache=cache, refresh=refresh, timeouts=timeouts)
        except VoProtocolsError as exc:
            if exc.code in ("NAME_NOT_FOUND", "ADQL_INVALID"):
                raise
            resolved = _network(None, resolve_name, identifier, cache=cache, refresh=refresh)
            note = ModuleWarning("PROFILE_NO_IDENTIFIERS", f"SIMBAD non raggiungibile ({exc.code}): '{identifier}' "
                                 f"risolto da {resolved.source}, profilo per posizione senza identificativi",
                                 {"reason": "simbad_unreachable", "name": identifier, "service": _resolver_label(resolved),
                                  "cause": _message(exc)})
            return ResolvedTarget(target, None, resolved.coords, _resolver_source(resolved),
                                  "name_resolver", simbad_error=_message(exc),
                                  warnings=(note,) + tuple(resolved.warnings))
        notes = _network_notes(record.warnings)
        if target.name is not None and target.simbad_id is not None and record.main_id != target.simbad_id:
            notes += (ModuleWarning("PROFILE_TARGET_CHANGED", f"'{target.name}': SIMBAD indica oggi "
                                    f"{record.main_id}, il comando registrato {target.simbad_id}",
                                    {"name": target.name, "recorded": target.simbad_id, "found": record.main_id}),)
        return ResolvedTarget(target, record, record.coords, f"{_record_service(record)}, ICRS J2000 (coo_bibcode "
                              f"{record.basic.get('coo_bibcode')})", "simbad_identifier", warnings=notes,
                              requests=record.requests)
    position = target.position
    notes: tuple = ()
    if position.epoch is None:
        notes += (ModuleWarning("PROFILE_NO_PROPER_MOTION", "epoca del bersaglio non nota: candidati SIMBAD senza "
                                "propagazione, alla loro epoca J2000", {"reason": "target_epoch_unknown"}),)
    try:
        candidates, request, cand_notes = _simbad_candidates(position, match_radius, cache=cache, refresh=refresh,
                                                             timeouts=timeouts)
    except VoProtocolsError as exc:
        if exc.code == "ADQL_INVALID":
            raise
        note = ModuleWarning("PROFILE_NO_IDENTIFIERS", f"SIMBAD non raggiungibile ({exc.code}): profilo per "
                             "posizione senza identificativi",
                             {"reason": "simbad_unreachable_position", "cause": _message(exc)})
        return ResolvedTarget(target, None, position, "coordinates as written", "position", simbad_error=_message(exc),
                              warnings=notes + (note,))
    excluded = tuple(w for w in cand_notes if w[0] == "PROFILE_PLANETS_EXCLUDED")
    if len(candidates) > 1:
        return TargetCandidates(target, match_radius, candidates, (request,), excluded)
    if not candidates:
        return ResolvedTarget(target, None, position, "coordinates as written (no SIMBAD object within "
                              f"{float(match_radius.to_value(u.arcsec)):g} arcsec)", "position",
                              warnings=notes + _network_notes(cand_notes) + excluded, requests=(request,))
    chosen = candidates[0]
    record = _network("simbad", simbad_object, chosen["main_id"], cache=cache, refresh=refresh,
                      timeouts=timeouts)
    sep = chosen["separation"]["value"] * u.arcsec
    note = ModuleWarning("PROFILE_POSITIONAL_MATCH", f"bersaglio per posizione: {record.main_id} a "
                         f"{float(sep.value)!r} arcsec (raggio {float(match_radius.to_value(u.arcsec))!r} arcsec)",
                         {"reason": "simbad_candidate", "main_id": record.main_id, "separation": _qj(sep),
                          "radius": _qj(match_radius, "arcsec"),
                          "epoch": "—" if position.epoch is None else str(position.epoch.jyear_str)})
    return ResolvedTarget(target, record, record.coords, f"{_record_service(record)}, ICRS J2000", "simbad_candidate",
                          separation=sep, warnings=notes + _network_notes(cand_notes) + excluded + (note,)
                          + _network_notes(record.warnings),
                          requests=(request,) + record.requests)


# --------------------------------------------------------------------------
# Catena degli identificativi (25 §3.2, §3.3, §3.10)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CrossIdentification:
    """Esito della catena per un catalogo: identificativo (o nessuno), metodo, separazione, candidati, conflitto."""

    catalog: str
    identifier: str | None
    method: str | None  # simbad_identifier | official_crossmatch | position | None
    separation: u.Quantity | None = None
    epochs: Mapping[str, str] | None = None
    candidates: tuple[dict, ...] = ()
    conflict: Mapping[str, str] | None = None
    official: Mapping[str, object] | None = None  # riga dell'incrocio ufficiale (designazione, distanza, vicini)
    note: str | None = None
    warnings: tuple[ModuleWarning, ...] = ()
    requests: tuple[RequestRecord, ...] = ()
    queries: tuple[str, ...] = ()
    error: Mapping[str, object] | None = None  # errore del servizio dell'incrocio (messaggio invariato)
    #: Passo per posizione di 2MASS/AllWISE: la riga scelta (tabella di una riga, stesse colonne della fotometria),
    #: usata dalla fotometria senza una seconda richiesta (25 §3.16 C7-a); non fa parte del risultato (``as_dict``).
    row: object = field(default=None, repr=False, compare=False)

    @property
    def source_id(self) -> int | None:
        if self.catalog != "gaia_dr3" or self.identifier is None:
            return None
        return int(self.identifier.removeprefix("Gaia DR3 "))

    def as_dict(self) -> dict:
        from astrotwo.core.commands import quantity_json

        return {"catalog": self.catalog, "identifier": self.identifier, "method": self.method,
                "separation": None if self.separation is None else quantity_json(self.separation.to(u.arcsec)),
                "epochs": None if self.epochs is None else dict(self.epochs), "candidates": list(self.candidates),
                "conflict": None if self.conflict is None else dict(self.conflict),
                "official": None if self.official is None else {
                    k: (quantity_json(v) if isinstance(v, u.Quantity) else v) for k, v in self.official.items()},
                "note": self.note, "warnings": [_warning_json(w) for w in self.warnings],
                "servers": [r.url for r in self.requests], "queries": list(self.queries),
                "error": None if self.error is None else dict(self.error)}


def _simbad_identifier(resolved: ResolvedTarget, catalog: str) -> str | None:
    if resolved.simbad is None:
        return None
    prefix = _SIMBAD_PREFIX[catalog]
    for ident in resolved.simbad.identifiers:
        if ident.startswith(prefix):
            return ident
    return None


def _designation(catalog: str, text: str) -> str:
    """Designazione senza prefisso SIMBAD (``2MASS J…`` → ``…``; ``WISEA J…`` → ``J…``), formati del 2026-11-07."""
    if catalog == "2mass":
        return text.removeprefix("2MASS J").removeprefix("J").strip()
    return text.removeprefix("WISEA ").strip()


def _simbad_motion(resolved: ResolvedTarget):
    basic = resolved.simbad.basic if resolved.simbad is not None else {}
    return basic.get("pmra"), basic.get("pmdec"), basic.get("plx_value")


def _gaia_by_position(resolved: ResolvedTarget, radius: u.Quantity, *, cache, refresh, timeouts) -> CrossIdentification:
    """Passo per posizione su Gaia DR3 (25 §3.10): posizione portata a J2016.0, cerchio di ``radius``."""
    position = resolved.position
    notes: list = []
    pmra, pmdec, plx = _simbad_motion(resolved)
    source_epoch = position.epoch
    if source_epoch is not None and pmra is not None and pmdec is not None:
        full = isinstance(plx, u.Quantity) and plx.value > 0
        moved = propagate_position(position, pm_ra_cosdec=pmra, pm_dec=pmdec, parallax=plx if full else None,
                                   target_epoch=GAIA_DR3_EPOCH, proper_motion_only=not full)
        position = moved.position
    else:
        notes.append(ModuleWarning("PROFILE_NO_PROPER_MOTION", "moto proprio del bersaglio non noto: posizione "
                                   "confrontata con Gaia DR3 senza propagazione", {"reason": "target_pm_unknown",
                                                                                    "catalog": "Gaia DR3"}))
    icrs = position if position.frame_name == "icrs" else position.to("icrs")
    ra0, dec0 = float(icrs.lon.to_value(u.deg)), float(icrs.lat.to_value(u.deg))
    adql = (f"SELECT source_id, ra, dec, phot_g_mean_mag FROM {_GAIA_SOURCE} WHERE 1 = CONTAINS(POINT('ICRS', ra, "
            f"dec), CIRCLE('ICRS', {ra0!r}, {dec0!r}, {float(radius.to_value(u.deg))!r}))")
    result = _tap(_GAIA_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts)
    target = SkyCoord(ra0 * u.deg, dec0 * u.deg, frame="icrs")
    found = []
    for row in result.table.table:
        ra, dec = _value(row, "ra"), _value(row, "dec")
        sep = SkyCoord(ra, dec, frame="icrs").separation(target).to(u.arcsec)
        found.append({"identifier": f"Gaia DR3 {_value(row, 'source_id')}", "separation": _qj(sep, "arcsec"),
                      "phot_g_mean_mag": None if _value(row, "phot_g_mean_mag") is None
                      else _qj(_value(row, "phot_g_mean_mag"))})
    found.sort(key=lambda c: (c["separation"]["value"], c["identifier"]))
    epochs = {"source": None if source_epoch is None else source_epoch.jyear_str,
              "target": GAIA_DR3_EPOCH.jyear_str}
    common = dict(epochs=epochs, requests=(result.request,), queries=(adql,))
    warnings = tuple(notes) + tuple(w for w in result.warnings if w[0] in ("FROM_CACHE", "SERVICE_MIRROR_FALLBACK"))
    if not found:
        note = ModuleWarning("PROFILE_NO_GAIA", f"nessuna sorgente Gaia DR3 entro {float(radius.to_value(u.arcsec))!r} "
                             "arcsec dalla posizione propagata", {"reason": "no_counterpart",
                                                                 "radius": _qj(radius, "arcsec")})
        return CrossIdentification("gaia_dr3", None, None, warnings=warnings + (note,), **common)
    if len(found) > 1:
        note = ModuleWarning("PROFILE_POSITIONAL_MATCH", f"{len(found)} sorgenti Gaia DR3 entro "
                             f"{float(radius.to_value(u.arcsec))!r} arcsec: nessuna scelta",
                             {"reason": "several_candidates", "catalog": "Gaia DR3", "count": len(found),
                              "radius": _qj(radius, "arcsec")})
        return CrossIdentification("gaia_dr3", None, None, candidates=tuple(found), warnings=warnings + (note,),
                                   **common)
    best = found[0]
    sep = best["separation"]["value"] * u.arcsec
    note = ModuleWarning("PROFILE_POSITIONAL_MATCH", f"Gaia DR3 per posizione: {best['identifier']} a {float(sep.value)!r} "
                         f"arcsec (raggio {float(radius.to_value(u.arcsec))!r} arcsec, epoche {epochs['source']} → "
                         f"{epochs['target']})",
                         {"reason": "catalog_match", "catalog": "Gaia DR3", "identifier": best["identifier"],
                          "separation": _qj(sep), "radius": _qj(radius, "arcsec"),
                          "source_epoch": epochs["source"] or "", "target_epoch": epochs["target"]})
    return CrossIdentification("gaia_dr3", best["identifier"], "position", separation=sep, candidates=tuple(found),
                               warnings=warnings + (note,), **common)


def _official_crossmatch(catalog: str, source_id: int, *, cache, refresh, timeouts):
    table = _OFFICIAL[catalog]
    adql = (f"SELECT source_id, original_ext_source_id, angular_distance, number_of_neighbours, xm_flag FROM {table} "
            f"WHERE source_id = {int(source_id)}")
    result = _tap(_GAIA_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts)
    rows = result.table.table
    if len(rows) == 0:
        return None, result, adql
    row = rows[0]
    return ({"table": table, "designation": _value(row, "original_ext_source_id"),
             "angular_distance": _value(row, "angular_distance"),
             "number_of_neighbours": _value(row, "number_of_neighbours"), "xm_flag": _value(row, "xm_flag")},
            result, adql)


def _host_names(resolved: ResolvedTarget) -> list[str]:
    """Identificativi SIMBAD senza i prefissi ``*``, ``**``, ``V*``, ``NAME`` e con gli spazi ridotti (25 §3.10)."""
    if resolved.simbad is None:
        return []
    out = []
    for ident in resolved.simbad.identifiers:
        text = " ".join(ident.split())
        for prefix in _NAME_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):]
                break
        if text and text not in out:
            out.append(text)
    return out


def _typed_names(resolved: ResolvedTarget) -> list[str]:
    """Nome scritto dall'utente (o ``simbad_id`` già noto), ridotto come gli identificativi SIMBAD (25 §3.10), per
    la ricerca dell'ospite dei pianeti quando SIMBAD non ha risposto (D25-23, decisione del 2026-11-10)."""
    out = []
    for written in (resolved.target.simbad_id, resolved.target.name):
        text = " ".join(str(written or "").split())
        for prefix in _NAME_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):]
                break
        if text and text not in out:
            out.append(text)
    return out


def _adql_text(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def cross_identify(resolved: ResolvedTarget, catalog: str, *, gaia: CrossIdentification | None = None,
                   crossmatch_radius: u.Quantity = DEFAULT_CROSSMATCH_RADIUS, cache: SharedCache | None = None,
                   refresh: bool = False, timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> CrossIdentification:
    """Catena degli identificativi di un catalogo (25 §3.2, §3.10): SIMBAD, poi incrocio ufficiale, poi posizione.

    ``gaia``: esito già noto per Gaia DR3 (serve a 2MASS, AllWISE ed Exoplanet Archive); senza, si calcola."""
    if catalog not in CATALOGS:
        raise ValueError(f"catalogo {catalog!r} non in {CATALOGS}")
    if catalog == "gaia_dr3":
        ident = _simbad_identifier(resolved, "gaia_dr3")
        if ident is not None:
            return CrossIdentification("gaia_dr3", ident, "simbad_identifier")
        return _gaia_by_position(resolved, crossmatch_radius, cache=cache, refresh=refresh, timeouts=timeouts)
    if gaia is None:
        gaia = cross_identify(resolved, "gaia_dr3", crossmatch_radius=crossmatch_radius, cache=cache,
                              refresh=refresh, timeouts=timeouts)
    if catalog == "exoplanet":
        return _exoplanet_host(resolved, gaia, cache=cache, refresh=refresh, timeouts=timeouts)
    label = {"2mass": "2MASS", "allwise": "AllWISE"}[catalog]
    simbad = _simbad_identifier(resolved, catalog)
    official, requests, queries, notes, error = None, (), (), (), None
    if gaia.source_id is not None:
        try:
            official, result, adql = _official_crossmatch(catalog, gaia.source_id, cache=cache, refresh=refresh,
                                                          timeouts=timeouts)
        except VoProtocolsError as exc:  # incrocio ufficiale non disponibile: resta l'identificativo di SIMBAD
            error = _message(exc)
        else:
            requests, queries = (result.request,), (adql,)
            notes = _network_notes(result.warnings)
    common = dict(official=official, requests=requests, queries=queries, error=error)
    if simbad is not None and official is not None:
        if _designation(catalog, simbad) != str(official["designation"]).strip():
            conflict = {"simbad": simbad, "official": str(official["designation"]), "table": official["table"]}
            note = ModuleWarning("PROFILE_IDENTIFIER_CONFLICT", f"{label}: SIMBAD indica {simbad}, l'incrocio "
                                 f"ufficiale di Gaia {official['designation']}: nessuna scelta",
                                 {"catalog": label, "simbad": simbad, "official": str(official["designation"])})
            return CrossIdentification(catalog, None, None, conflict=conflict, warnings=notes + (note,), **common)
        return CrossIdentification(catalog, simbad, "simbad_identifier", warnings=notes,
                                   note="confirmed by the official Gaia cross-match", **common)
    if simbad is not None:
        return CrossIdentification(catalog, simbad, "simbad_identifier", warnings=notes, **common)
    if official is not None:
        prefix = "2MASS J" if catalog == "2mass" else "WISEA "
        return CrossIdentification(catalog, prefix + str(official["designation"]).strip(), "official_crossmatch",
                                   separation=official["angular_distance"], warnings=notes, **common)
    found = _catalog_by_position(resolved, catalog, crossmatch_radius, cache=cache, refresh=refresh,
                                 timeouts=timeouts)
    return dataclasses.replace(found, official=official, error=error, warnings=notes + found.warnings,
                               requests=requests + found.requests, queries=queries + found.queries)


def _propagated(resolved: ResolvedTarget, epoch: Time, catalog: str) -> tuple[SkyFrame, tuple]:
    """Posizione del bersaglio portata a ``epoch`` con il moto proprio (e la parallasse) di SIMBAD, come per Gaia
    (25 §3.10); senza moto proprio o senza epoca: nessuna propagazione e ``PROFILE_NO_PROPER_MOTION``."""
    position = resolved.position
    pmra, pmdec, plx = _simbad_motion(resolved)
    if position.epoch is None or pmra is None or pmdec is None:
        return position, (ModuleWarning("PROFILE_NO_PROPER_MOTION", "moto proprio del bersaglio non noto: posizione "
                                        f"confrontata con {catalog} senza propagazione",
                                        {"reason": "target_pm_unknown", "catalog": catalog}),)
    full = isinstance(plx, u.Quantity) and plx.value > 0
    moved = propagate_position(position, pm_ra_cosdec=pmra, pm_dec=pmdec, parallax=plx if full else None,
                               target_epoch=epoch, proper_motion_only=not full)
    return moved.position, ()


def _icrs_deg(position: SkyFrame) -> tuple[float, float]:
    icrs = position if position.frame_name == "icrs" else position.to("icrs")
    return float(icrs.lon.to_value(u.deg)), float(icrs.lat.to_value(u.deg))


def _circle(ra: float, dec: float, radius: u.Quantity) -> str:
    return (f"CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra!r}, {dec!r}, "
            f"{float(radius.to_value(u.deg))!r})) = 1")


def _request_text(request: RequestRecord) -> str:
    """URL completo di una richiesta GET (Cone Search di IRSA): la ``query`` della provenienza (25 §3.17 punto 1)."""
    import requests

    return requests.Request("GET", request.url, params=list(request.params)).prepare().url


def _irsa_cone(catalog: str, center, radius: u.Quantity, *, cache, refresh, timeouts):
    """Cono del Cone Search di IRSA su ``fp_psc`` o ``allwise_p3as_psd`` (D25-21 (1)): righe con le sole colonne di
    ``_IRSA_COLUMNS`` (stesse unità e tipi del TAP, verificati il 2026-11-09), richiesta e URL completo."""
    url = f"{_IRSA_SCS}?table={_IRSA_TABLE[catalog]}"
    result = _network("irsa", cone_search, center, radius, url, cache=cache, refresh=refresh, timeouts=timeouts)
    columns = [c.strip() for c in _IRSA_COLUMNS[catalog].split(",")]
    table = result.table.table
    missing = [c for c in columns if c not in table.colnames]
    if missing:  # mai una colonna mancante in silenzio: la condizione di D25-21 (1) non vale più
        raise VoProtocolsError("VOTABLE_INVALID", f"{result.request.url}: risposta senza le colonne {missing}",
                               params={"reason": "photometry_columns", "url": result.request.url, "missing": missing})
    return table[columns], result.request, _request_text(result.request), tuple(result.warnings)


def _catalog_by_position(resolved: ResolvedTarget, catalog: str, radius: u.Quantity, *, cache, refresh,
                         timeouts) -> CrossIdentification:
    """Passo per posizione di 2MASS o AllWISE (25 §3.11): AllWISE all'epoca MJD 55400,0; 2MASS al ``jdate`` di ogni
    riga, con il cerchio di ricerca allargato dal moto proprio sul periodo delle osservazioni."""
    label = {"2mass": "2MASS", "allwise": "AllWISE"}[catalog]
    notes: tuple = ()
    pmra, pmdec, _ = _simbad_motion(resolved)
    source_epoch = resolved.position.epoch
    if catalog == "allwise":
        center, notes = _propagated(resolved, ALLWISE_EPOCH, label)
        search = radius
        target_epoch = f"MJD 55400.0 UTC ({ALLWISE_EPOCH.utc.jyear_str})"
    else:
        center = resolved.position
        search = radius
        if source_epoch is not None and pmra is not None and pmdec is not None:
            span = max(abs(_years_between(t, source_epoch)) for t in TMASS_OBSERVATIONS) * u.yr
            search = (radius + (np.hypot(pmra.to(u.mas / u.yr), pmdec.to(u.mas / u.yr)) * span)).to(u.arcsec)
        else:
            notes = _propagated(resolved, TMASS_OBSERVATIONS[0], label)[1]
        target_epoch = "jdate della riga (UTC)"
    rows, request, query, net_notes = _irsa_cone(catalog, center, search, cache=cache, refresh=refresh,
                                                 timeouts=timeouts)
    found = []
    for index, row in enumerate(rows):
        ra, dec = _value(row, "ra"), _value(row, "dec")
        if ra is None or dec is None:
            continue
        here = center
        if catalog == "2mass" and not notes:
            jd = _value(row, "jdate")
            if jd is not None:
                jd_value = float(jd.to_value(u.d)) if isinstance(jd, u.Quantity) else float(jd)
                here, _ = _propagated(resolved, Time(jd_value, format="jd", scale="utc"), label)
        hx, hy = _icrs_deg(here)
        sep = SkyCoord(ra, dec, frame="icrs").separation(SkyCoord(hx * u.deg, hy * u.deg, frame="icrs")).to(u.arcsec)
        if sep <= radius:
            prefix = "2MASS J" if catalog == "2mass" else "WISEA "
            found.append({"identifier": prefix + str(_value(row, "designation")).strip(),
                          "separation": _qj(sep, "arcsec"), "_index": index})
    found.sort(key=lambda c: (c["separation"]["value"], c["identifier"]))
    indices = [c.pop("_index") for c in found]
    epochs = {"source": None if source_epoch is None else source_epoch.jyear_str, "target": target_epoch}
    common = dict(epochs=epochs, requests=(request,), queries=(query,))
    warnings = notes + _network_notes(net_notes)
    r_arcsec = float(radius.to_value(u.arcsec))
    if not found:
        return CrossIdentification(catalog, None, None, warnings=warnings,
                                   note=f"no {label} source within {r_arcsec!r} arcsec of the propagated position",
                                   **common)
    if len(found) > 1:
        note = ModuleWarning("PROFILE_POSITIONAL_MATCH", f"{len(found)} sorgenti {label} entro {r_arcsec!r} arcsec: "
                             "nessuna scelta", {"reason": "several_candidates", "catalog": label,
                                                 "count": len(found), "radius": _qj(radius, "arcsec")})
        return CrossIdentification(catalog, None, None, candidates=tuple(found), warnings=warnings + (note,),
                                   **common)
    best = found[0]
    sep = best["separation"]["value"] * u.arcsec
    note = ModuleWarning("PROFILE_POSITIONAL_MATCH", f"{label} per posizione: {best['identifier']} a "
                         f"{float(sep.value)!r} arcsec (raggio {r_arcsec!r} arcsec, epoche {epochs['source']} → "
                         f"{target_epoch})",
                         {"reason": "catalog_match", "catalog": label, "identifier": best["identifier"],
                          "separation": _qj(sep), "radius": _qj(radius, "arcsec"),
                          "source_epoch": epochs["source"] or "", "target_epoch": target_epoch})
    return CrossIdentification(catalog, best["identifier"], "position", separation=sep, candidates=tuple(found),
                               warnings=warnings + (note,), row=rows[indices[0]:indices[0] + 1], **common)


class _ExoplanetAsk:
    """Richieste all'Exoplanet Archive di un passo della catena, con richieste, interrogazioni e avvisi raccolti."""

    def __init__(self, *, cache, refresh, timeouts) -> None:
        self.net = dict(cache=cache, refresh=refresh, timeouts=timeouts)
        self.requests: list = []
        self.queries: list = []
        self.notes: list = []

    def __call__(self, adql: str):
        result = _tap(_EXOPLANET_TAP, adql, **self.net)
        self.requests.append(result.request)
        self.queries.append(adql)
        self.notes.extend(w for w in result.warnings if w[0] == "FROM_CACHE")
        return result.table.table

    def found(self, identifier: str | None, official=None, method: str = "simbad_identifier",
              **kw) -> CrossIdentification:
        return CrossIdentification("exoplanet", identifier, None if identifier is None else method,
                                   official=official, warnings=tuple(self.notes) + tuple(kw.pop("extra", ())),
                                   requests=tuple(self.requests), queries=tuple(self.queries), **kw)


def _exoplanet_by_gaia(gaia: CrossIdentification, ask: _ExoplanetAsk) -> CrossIdentification | None:
    """Ospite per ``gaia_dr3_id`` (25 §3.10); ``None`` senza righe."""
    rows = ask("SELECT DISTINCT hostname, gaia_dr3_id FROM pscomppars WHERE gaia_dr3_id = "
               f"{_adql_text(gaia.identifier)}")
    if not len(rows):
        return None
    return ask.found(_value(rows[0], "hostname"), official={"gaia_dr3_id": gaia.identifier})


#: Nota dell'ospite non cercato (D25-23): nessuna richiesta all'archivio, quindi nessuna assenza affermata.
PLANETS_NOT_CHECKED_NOTE = "not checked: no SIMBAD identifier, no written name and no Gaia DR3 source_id"


def _planets_not_checked(resolved: ResolvedTarget) -> ModuleWarning:
    reason = "simbad_unavailable" if resolved.simbad_error is not None else "no_identifiers"
    return ModuleWarning("PROFILE_PLANETS_NOT_CHECKED", "pianeti non controllati: nessun identificativo SIMBAD, "
                         "nessun nome scritto e nessun source_id di Gaia DR3 da chiedere all'archivio",
                         {"reason": reason})


def _exoplanet_by_hostname(resolved: ResolvedTarget, ask: _ExoplanetAsk) -> CrossIdentification:
    """Ospite per ``hostname`` uguale a un identificativo SIMBAD (25 §3.10); senza SIMBAD, uguale al nome scritto
    dall'utente (D25-23). Nessun ospite dopo la richiesta → «nessun ospite»; nessun nome da chiedere e nessuna
    richiesta fatta → «non controllato» con ``PROFILE_PLANETS_NOT_CHECKED``, mai un'assenza (D25-23)."""
    names, method = _host_names(resolved), "simbad_identifier"
    if not names and resolved.simbad is None:
        names, method = _typed_names(resolved), "written_name"
    if names:
        rows = ask("SELECT DISTINCT hostname, gaia_dr3_id FROM pscomppars WHERE hostname IN ("
                   + ", ".join(_adql_text(n) for n in names) + ")")
        hosts = sorted({str(_value(r, "hostname")) for r in rows})
        source = "the SIMBAD identifiers" if method == "simbad_identifier" else "the written name"
        if len(hosts) == 1:
            return ask.found(hosts[0], official={"hostname": hosts[0]}, method=method,
                             note=None if method == "simbad_identifier" else
                             "host found by the written name (SIMBAD unavailable): identity not verified")
        if len(hosts) > 1:
            return ask.found(None, candidates=tuple({"hostname": h} for h in hosts),
                             note=f"several archive hosts match {source}: none chosen")
        return ask.found(None, note="no host in the archive" + ("" if method == "simbad_identifier" else
                                                                 " (searched by the written name)"))
    if ask.requests:  # già chiesto per gaia_dr3_id, nessuna riga: l'assenza viene da una richiesta vera
        return ask.found(None, note="no host in the archive")
    return ask.found(None, note=PLANETS_NOT_CHECKED_NOTE, extra=(_planets_not_checked(resolved),))


def _exoplanet_host(resolved: ResolvedTarget, gaia: CrossIdentification, *, cache, refresh, timeouts):
    ask = _ExoplanetAsk(cache=cache, refresh=refresh, timeouts=timeouts)
    if gaia.source_id is not None:
        found = _exoplanet_by_gaia(gaia, ask)
        if found is not None:
            return found
    return _exoplanet_by_hostname(resolved, ask)


def exoplanet_host_early(resolved: ResolvedTarget) -> bool:
    """Vero se l'ospite dei pianeti si cerca subito per ``hostname``, senza aspettare l'esito di Gaia della catena
    (D25-17 (10), 25 §3.14): SIMBAD ha risposto e i suoi identificativi non contengono ``Gaia DR3``."""
    return resolved.simbad is not None and _simbad_identifier(resolved, "gaia_dr3") is None and bool(
        _host_names(resolved))


def check_exoplanet_host(early: CrossIdentification, gaia: CrossIdentification, *, cache: SharedCache | None = None,
                         refresh: bool = False, timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> CrossIdentification:
    """Verifica dell'ospite trovato subito per ``hostname`` con il ``gaia_dr3_id`` arrivato dopo (D25-17 (10)).

    Stesso ospite, o nessuna riga per ``gaia_dr3_id``: l'esito per ``hostname`` resta (come nella catena normale, dove
    ``hostname`` è il secondo passo). Ospite diverso, o trovato solo per ``gaia_dr3_id``: l'esito per ``hostname``
    resta (è quello usato dalla sezione Pianeti) con l'altro in ``conflict`` e l'avviso
    ``PROFILE_PLANET_HOST_MISMATCH``: nessuna scelta silenziosa."""
    if gaia.source_id is None or early.error is not None:
        return early
    ask = _ExoplanetAsk(cache=cache, refresh=refresh, timeouts=timeouts)
    by_gaia = _exoplanet_by_gaia(gaia, ask)
    merged = dict(requests=early.requests + tuple(ask.requests), queries=early.queries + tuple(ask.queries),
                  warnings=early.warnings + tuple(ask.notes))
    if by_gaia is None or by_gaia.identifier == early.identifier:
        note = early.note if by_gaia is None else "confirmed by gaia_dr3_id"
        return dataclasses.replace(early, note=note, **merged)
    params = {"gaia_dr3_id": gaia.identifier, "by_gaia": by_gaia.identifier}
    if early.identifier is None:
        warning = ModuleWarning("PROFILE_PLANET_HOST_MISMATCH", f"ospite dei pianeti: nessuno per hostname, "
                                f"{by_gaia.identifier} per {gaia.identifier}: pianeti mostrati per hostname",
                                {"reason": "only_gaia", **params})
    else:
        warning = ModuleWarning("PROFILE_PLANET_HOST_MISMATCH", f"ospite dei pianeti: {early.identifier} per "
                                f"hostname, {by_gaia.identifier} per {gaia.identifier}: pianeti mostrati per hostname",
                                {"reason": "different", "by_name": early.identifier, **params})
    conflict = {"hostname": early.identifier or "", "gaia_dr3_id": gaia.identifier, "by_gaia": by_gaia.identifier}
    return dataclasses.replace(early, conflict=conflict, **{**merged, "warnings": merged["warnings"] + (warning,)})


# --------------------------------------------------------------------------
# Sezioni (25 §3.4, §3.10)
# --------------------------------------------------------------------------


@dataclass
class ProfileSection:
    """Una sezione: stato, valori, dettagli, avvisi, errori, server, tempo."""

    name: str
    status: str = "pending"  # pending, running, done, partial, error, not_applicable, cancelled (25 §3.12)
    values: list[ProfileValue] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    requests: list[RequestRecord] = field(default_factory=list)
    elapsed: float | None = None  # s dopo sections_started, all'arrivo (25 §3.12)
    started: float | None = None  # s dopo sections_started, partenza della sezione (25 §3.17 punto 4)

    def as_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "values": [v.as_dict() for v in self.values],
                "details": self.details, "warnings": [_warning_json(w) for w in self.warnings],
                "errors": list(self.errors), "servers": sorted({r.url for r in self.requests}),
                "elapsed": None if self.elapsed is None else {"value": self.elapsed, "unit": "s"},
                "started": None if self.started is None else {"value": self.started, "unit": "s"}}


def _group(identifier: str) -> str:
    """Catalogo di un identificativo SIMBAD: prima parola; ``NAME`` = nomi propri; ``*``/``**``/``V*`` = stelle."""
    head = identifier.split()[0] if identifier.split() else identifier
    return {"*": "star", "**": "star", "V*": "star", "NAME": "NAME"}.get(head, head)


def _simbad_link(record: SimbadRecord) -> str:
    parsed = urllib.parse.urlparse(record.requests[0].url)
    return f"{parsed.scheme}://{parsed.netloc}/simbad/sim-id?Ident={urllib.parse.quote(record.main_id)}"


#: Nota dell'Identità quando SIMBAD non ha un tipo spettrale (D25-24, decisa il 2026-11-10; inglese alla fonte, DD-3)
SP_TYPE_ABSENT_NOTE = "SIMBAD has no spectral type"


def profile_identity(resolved: ResolvedTarget) -> ProfileSection:
    """Sezione Identità dai dati SIMBAD già letti da ``simbad_object`` (25 §3.10): nessuna nuova richiesta."""
    section = ProfileSection("identity")
    record = resolved.simbad
    if record is None:
        section.status = "error"
        if resolved.simbad_error is not None:
            section.errors.append(resolved.simbad_error)
        else:
            section.status = "not_applicable"
            section.details["note"] = "no SIMBAD object for this position"
        return section
    basic = record.basic
    req = record.requests[0]
    query = req.arguments.get("adql")

    def read(name: str, value, *, error=None, reference=None, note=None):
        section.values.append(ProfileValue(name, value, _provenance(req, _record_service(record), "basic", query,
                                                                    record.identifier, "simbad_identifier"),
                                           error=error, reference=reference, note=note))

    read("main_id", record.main_id)
    read("otype", basic.get("otype"), note=record.otype_description)
    absent = []
    sp_type = basic.get("sp_type")
    if isinstance(sp_type, str) and sp_type.strip():
        read("sp_type", sp_type, reference=basic.get("sp_bibcode"))
    else:  # D25-24: testo vuoto o nullo = valore assente dichiarato da SIMBAD, mai un valore (02 §2)
        absent.append({"quantity": "sp_type", "note": SP_TYPE_ABSENT_NOTE})
    read("nbref", basic.get("nbref"))
    read("ra", basic.get("ra"), reference=basic.get("coo_bibcode"), note="ICRS, epoch J2000")
    read("dec", basic.get("dec"), reference=basic.get("coo_bibcode"), note="ICRS, epoch J2000")
    for name in ("coo_err_maj", "coo_err_min", "coo_err_angle", "coo_qual"):
        read(name, basic.get(name), reference=basic.get("coo_bibcode"))
    groups: dict[str, list[str]] = {}
    for ident in record.identifiers:
        groups.setdefault(_group(ident), []).append(ident)
    ident_req = record.requests[1]
    section.details = {"identifiers": {k: groups[k] for k in sorted(groups)}, "identifier_count":
                       len(record.identifiers), "simbad_url": _simbad_link(record),
                       "identifiers_provenance": _provenance(ident_req, _record_service(record), "ident",
                                                             ident_req.arguments.get("adql"), record.main_id,
                                                             "simbad_identifier").as_dict()}
    if absent:
        section.details["absent"] = absent
    section.requests.extend(record.requests[:2])
    section.status = "done"
    return section


def _simbad_astrometry(section: ProfileSection, record: SimbadRecord) -> ProfileValue | None:
    """Parallasse, moto proprio e velocità radiale di SIMBAD con i loro bibcode; restituisce la parallasse."""
    basic = record.basic
    req = record.requests[0]
    prov = _provenance(req, _record_service(record), "basic", req.arguments.get("adql"), record.main_id,
                       "simbad_identifier")
    parallax = None
    if basic.get("plx_value") is not None:
        parallax = ProfileValue("parallax", basic["plx_value"], prov, error=basic.get("plx_err"),
                                reference=basic.get("plx_bibcode"), note="SIMBAD")
        section.values.append(parallax)
    for name in ("pmra", "pmdec"):
        if basic.get(name) is not None:
            section.values.append(ProfileValue(name, basic[name], prov, reference=basic.get("pm_bibcode"),
                                               note="SIMBAD; error as an ellipse (pm_err_maj, pm_err_min, "
                                                    "pm_err_angle)"))
    for name in ("pm_err_maj", "pm_err_min", "pm_err_angle"):
        if basic.get(name) is not None:
            section.values.append(ProfileValue(name, basic[name], prov, reference=basic.get("pm_bibcode"),
                                               note="SIMBAD"))
    if basic.get("rvz_radvel") is not None:
        section.values.append(ProfileValue("radial_velocity", basic["rvz_radvel"], prov, error=basic.get("rvz_err"),
                                           reference=basic.get("rvz_bibcode"), note="SIMBAD"))
    return parallax


_GAIA_COLUMNS = ("source_id", "ref_epoch", "ra", "ra_error", "dec", "dec_error", "parallax", "parallax_error", "pmra",
                 "pmra_error", "pmdec", "pmdec_error", "radial_velocity", "radial_velocity_error", "ruwe",
                 "astrometric_params_solved", "duplicated_source", "ipd_frac_multi_peak")


def _bits(value: int) -> int:
    """Numero di parametri astrometrici = bit a 1 di ``astrometric_params_solved`` (modello dei dati Gaia DR3)."""
    return bin(int(value)).count("1")


def profile_astrometry(resolved: ResolvedTarget, gaia: CrossIdentification, *, cache: SharedCache | None = None,
                       refresh: bool = False, timeouts: NetworkTimeouts = NETWORK_TIMEOUTS,
                       cancel: Callable[[], bool] | None = None) -> ProfileSection:
    """Sezione Astrometria con la distanza (25 §3.4.3–§3.4.4, §3.10)."""
    section = ProfileSection("astrometry")
    section.details["gaia"] = gaia.as_dict()
    section.warnings.extend(gaia.warnings)
    section.requests.extend(gaia.requests)
    parallax = None
    gaia_row = None
    bj = None
    gaia_failed = False
    if gaia.source_id is not None:
        adql = f"SELECT {', '.join(_GAIA_COLUMNS)} FROM {_GAIA_SOURCE} WHERE source_id = {gaia.source_id}"
        bj_adql = ("SELECT source_id, r_med_geo, r_lo_geo, r_hi_geo, r_med_photogeo, r_lo_photogeo, r_hi_photogeo, "
                   f"flag FROM {_BJ_TABLE} WHERE source_id = {gaia.source_id}")

        def ask(text: str):
            def run():
                _check(cancel)
                try:
                    return _tap(_GAIA_TAP, text, cache=cache, refresh=refresh, timeouts=timeouts), None
                except VoProtocolsError as exc:
                    return None, exc
            return run

        # gaia_source e Bailer-Jones insieme (stesso source_id, §3.17 punto 5); Bailer-Jones si usa solo con la riga
        (result, exc), (bj_result, bj_exc) = _gather([ask(adql), ask(bj_adql)])
        if exc is not None:
            section.errors.append(_message(exc))
            gaia_failed = True
        else:
            section.requests.append(result.request)
            section.warnings.extend(w for w in result.warnings if w[0] in ("FROM_CACHE",))
            if len(result.table.table) == 0:
                section.warnings.append(ModuleWarning(
                    "PROFILE_NO_GAIA", f"{gaia.identifier} indicato da SIMBAD ma assente da {_GAIA_SOURCE}",
                    {"reason": "not_in_archive", "identifier": gaia.identifier}))
            else:
                gaia_row = result.table.table[0]
                parallax = _gaia_values(section, gaia_row, result.request, adql, gaia)
        _check(cancel)
        if gaia_row is not None:  # senza la riga di gaia_source la risposta di Bailer-Jones si scarta (D25-22 (6))
            if bj_exc is not None:
                section.errors.append(_message(bj_exc))
            else:
                section.requests.append(bj_result.request)
                if len(bj_result.table.table):
                    bj = (bj_result.table.table[0], _provenance(bj_result.request, _service_name(
                        bj_result.request.url), _BJ_TABLE, bj_adql, gaia.identifier, gaia.method))
    elif gaia.method is None and not gaia.candidates and not any(w[0] == "PROFILE_NO_GAIA" for w in gaia.warnings):
        section.warnings.append(ModuleWarning("PROFILE_NO_GAIA", "nessuna sorgente Gaia DR3 associata",
                                              {"reason": "no_counterpart",
                                               "radius": _qj(DEFAULT_CROSSMATCH_RADIUS, "arcsec")}))
    use_simbad = resolved.simbad is not None and (gaia_row is None or parallax is None)
    if use_simbad:
        simbad_plx = _simbad_astrometry(section, resolved.simbad)
        section.requests.append(resolved.simbad.requests[0])
        if parallax is None and gaia_row is None:
            parallax = simbad_plx
        elif parallax is None:  # soluzione a 2 parametri: la parallasse di SIMBAD (Gaia non la dà)
            parallax = simbad_plx
    values, notes = distance_from(bj, parallax)
    section.values.extend(values)
    section.warnings.extend(notes)
    if gaia_failed:
        section.status = "partial" if section.values else "error"
    elif not section.values:
        section.status = "error" if section.errors else "not_applicable"
    else:
        section.status = "partial" if section.errors else "done"
    return section


def _gaia_values(section: ProfileSection, row, request: RequestRecord, adql: str,
                 gaia: CrossIdentification) -> ProfileValue | None:
    """Valori di ``gaiadr3.gaia_source`` con errori e indicatori; restituisce la parallasse (``None`` a 2 parametri)."""
    prov = _provenance(request, _service_name(request.url), _GAIA_SOURCE, adql, gaia.identifier, gaia.method)
    epoch = _value(row, "ref_epoch")
    epoch_note = None if epoch is None else f"reference epoch {_plain_number(epoch)} (ref_epoch, TCB)"
    add = section.values.append
    add(ProfileValue("source_id", _value(row, "source_id"), prov))
    add(ProfileValue("ref_epoch", epoch, prov))
    add(ProfileValue("ra", _value(row, "ra"), prov, error=_value(row, "ra_error"), note=epoch_note))
    add(ProfileValue("dec", _value(row, "dec"), prov, error=_value(row, "dec_error"), note=epoch_note))
    solved = _value(row, "astrometric_params_solved")
    n_params = None if solved is None else _bits(solved)
    add(ProfileValue("astrometric_params_solved", solved, prov,
                     note=None if n_params is None else f"{n_params} parameters"))
    parallax = None
    if n_params == 2:
        section.warnings.append(ModuleWarning(
            "PROFILE_GAIA_TWO_PARAMETER", f"{gaia.identifier}: soluzione Gaia DR3 a 2 parametri, senza parallasse "
            "né moto proprio", {"identifier": gaia.identifier}))
    else:
        for name in ("parallax", "pmra", "pmdec"):
            value = ProfileValue(name, _value(row, name), prov, error=_value(row, f"{name}_error"))
            if value.value is not None:
                add(value)
                if name == "parallax":
                    parallax = value
    rv = _value(row, "radial_velocity")
    if rv is not None:
        add(ProfileValue("radial_velocity", rv, prov, error=_value(row, "radial_velocity_error")))
    ruwe = _value(row, "ruwe")
    add(ProfileValue("ruwe", ruwe, prov, note=_RUWE_NOTE if ruwe is not None else
                     "null for 2-parameter solutions (Gaia DR3 data model)"))
    add(ProfileValue("duplicated_source", _value(row, "duplicated_source"), prov))
    add(ProfileValue("ipd_frac_multi_peak", _value(row, "ipd_frac_multi_peak"), prov))
    return parallax


def _plain_number(value) -> str:
    v = value.value if isinstance(value, u.Quantity) else value
    return repr(float(v))


def distance_from(bailer_jones, parallax: ProfileValue | None) -> tuple[tuple[ProfileValue, ...], tuple]:
    """Distanza solo con metodo dichiarato (25 §3.4.4, D25-2): Bailer-Jones → 1/ϖ con ϖ/σ ≥ 10 → nessuna.

    ``bailer_jones``: ``(riga di external.gaiaedr3_distance, Provenance)`` o ``None``; ``parallax``: il valore di
    Gaia DR3 o, se Gaia non lo dà, di SIMBAD. Restituisce ``(valori, avvisi)``."""
    if bailer_jones is not None:
        row, prov = bailer_jones
        out = []
        flag = _value(row, "flag")
        for kind in ("geo", "photogeo"):
            med = _value(row, f"r_med_{kind}")
            if med is None:
                continue
            lo, hi = _value(row, f"r_lo_{kind}"), _value(row, f"r_hi_{kind}")
            out.append(ProfileValue(f"distance_{kind}", med, prov,
                                    interval=None if lo is None or hi is None else (lo, hi),
                                    interval_kind="16th-84th percentile", reference=BAILER_JONES_REFERENCE,
                                    note=f"Bailer-Jones et al. (2021), {'geometric' if kind == 'geo' else 'photogeometric'} median"
                                         + (f"; flag {flag}" if flag is not None else "")))
        if out:
            return tuple(out), ()
    if parallax is None or parallax.value is None:
        return (), (ModuleWarning("PROFILE_NO_DISTANCE", "nessuna distanza: parallasse non disponibile",
                                  {"reason": "no_parallax"}),)
    plx = u.Quantity(parallax.value, dtype=np.float64)
    source = parallax.note or parallax.provenance.service
    if plx.value <= 0:
        return (), (ModuleWarning("PROFILE_NO_DISTANCE", f"nessuna distanza: parallasse non positiva "
                                  f"({float(plx.value)!r} {plx.unit})", {"reason": "negative_parallax",
                                                                  "parallax": _qj(plx), "source": source}),)
    err = parallax.error
    if err is None or err.value <= 0:
        return (), (ModuleWarning("PROFILE_NO_DISTANCE", "nessuna distanza: errore della parallasse non disponibile",
                                  {"reason": "no_parallax_error", "source": source}),)
    ratio = float((plx / err).decompose().value)
    if ratio < PARALLAX_SNR_MIN:
        return (), (ModuleWarning("PROFILE_NO_DISTANCE", f"nessuna distanza: parallasse/errore = {ratio!r} < "
                                  f"{PARALLAX_SNR_MIN!r}", {"reason": "low_snr", "ratio": ratio,
                                                           "minimum": PARALLAX_SNR_MIN, "source": source}),)
    distance = plx.to(u.pc, u.parallax())
    near, far = (plx + err).to(u.pc, u.parallax()), (plx - err).to(u.pc, u.parallax())
    value = ProfileValue("distance_parallax", distance, parallax.provenance, interval=(near, far),
                         interval_kind="1/(parallax +/- error)", method="computed",
                         formula="parallax.to(u.pc, u.parallax()) (astropy.units)", reference=parallax.reference,
                         note=f"1/parallax from {source}; parallax/error = {ratio!r} >= {PARALLAX_SNR_MIN!r}; "
                              f"{_ZERO_POINT_NOTE}")
    return (value,), ()


# --------------------------------------------------------------------------
# Fotometria e SED (25 §3.4.5, §3.11; punti e conversioni del 20)
# --------------------------------------------------------------------------

_DESIGNATION = {
    "2mass": re.compile(r"^(\d{2})(\d{2})(\d{2})(\d{2})([+-])(\d{2})(\d{2})(\d{2})(\d)$"),
    "allwise": re.compile(r"^J(\d{2})(\d{2})(\d{2}\.\d{2})([+-])(\d{2})(\d{2})(\d{2}\.\d)$"),
}


def designation_position(catalog: str, designation: str) -> tuple[float, float] | None:
    """Posizione (gradi ICRS) scritta in una designazione 2MASS (``hhmmssss±ddmmsss``) o AllWISE
    (``Jhhmmss.ss±ddmmss.s``): posizione del catalogo troncata (formati verificati il 2026-11-07, 25 §3.11)."""
    match = _DESIGNATION[catalog].match(designation.strip())
    if match is None:
        return None
    g = match.groups()
    if catalog == "2mass":
        hours = int(g[0]) + int(g[1]) / 60 + (int(g[2]) + int(g[3]) / 100) / 3600
        sign, dd, dm, ds = g[4], int(g[5]), int(g[6]), int(g[7]) + int(g[8]) / 10
    else:
        hours = int(g[0]) + int(g[1]) / 60 + float(g[2]) / 3600
        sign, dd, dm, ds = g[3], int(g[4]), int(g[5]), float(g[6])
    dec = dd + dm / 60 + ds / 3600
    return hours * 15.0, -dec if sign == "-" else dec


def _irsa_by_designation(catalog: str, identifier: str, *, cache, refresh, timeouts):
    """Righe di 2MASS o AllWISE con la designazione data: cono del Cone Search di IRSA di ``DESIGNATION_RADIUS``
    attorno alla posizione scritta nella designazione, riga scelta per designazione (25 §3.17 punto 1); senza
    posizione leggibile, interrogazione TAP per designazione come prima. → (richiesta, interrogazione, righe, avvisi)"""
    designation = _designation(catalog, identifier) if catalog == "2mass" else identifier.removeprefix("WISEA ").strip()
    position = designation_position(catalog, designation)
    if position is not None:
        center = SkyCoord(position[0] * u.deg, position[1] * u.deg, frame="icrs")
        rows, request, query, notes = _irsa_cone(catalog, center, DESIGNATION_RADIUS, cache=cache, refresh=refresh,
                                                 timeouts=timeouts)
        same = np.array([str(d).strip() == designation for d in rows["designation"]], dtype=bool) if len(rows) \
            else np.zeros(0, dtype=bool)
        return request, query, rows[same], notes
    adql = (f"SELECT {_IRSA_COLUMNS[catalog]} FROM {_IRSA_TABLE[catalog]} WHERE "
            f"designation = {_adql_text(designation)}")
    result = _tap(_IRSA_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts)
    return result.request, adql, result.table.table, result.warnings


def _vizier_center(resolved: ResolvedTarget) -> tuple[SkyFrame, tuple]:
    """Centro della serie VizieR: posizione del bersaglio a J2000 (25 §3.11)."""
    position = resolved.position
    if position.epoch is not None and abs(_years_between(position.epoch, _SIMBAD_EPOCH)) < 1e-9:
        return position, ()
    return _propagated(resolved, _SIMBAD_EPOCH, "VizieR")


def _point_values(point, prov: Provenance) -> list[ProfileValue]:
    """Valori della sezione per un punto: letto (magnitudine, flusso in e⁻/s) e calcolato (Fν), con provenienza."""
    out = []
    note = "; ".join(_english(n) for n in point.notes) or None
    if point.magnitude is not None:
        out.append(ProfileValue(f"{point.label} magnitude", point.magnitude, prov, error=point.magnitude_error,
                                reference=point.reference,
                                note=f"system {point.system or 'not declared'}; quality {point.quality or '—'}"))
    if point.count_rate is not None:
        out.append(ProfileValue(f"{point.label} count_rate", point.count_rate, prov, error=point.count_rate_error,
                                reference=point.reference))
    if point.flux is not None:
        zp = point.conversion["zero_point"]
        out.append(ProfileValue(f"{point.label} flux_nu", point.flux, prov, error=point.flux_error, method="computed",
                                formula=point.conversion["formula"], reference=zp["reference"],
                                note=f"zero point {zp['key']} ({zp['source']}); λ {zp['wavelength_kind']} "
                                     f"{zp['wavelength']['value']!r} {zp['wavelength']['unit']}"
                                     + (f"; {note}" if note else "")))
    return out


def profile_photometry(resolved: ResolvedTarget,
                       cross_ids: Mapping[str, CrossIdentification | Callable[[], CrossIdentification]], *,
                       cache: SharedCache | None = None, refresh: bool = False,
                       timeouts: NetworkTimeouts = NETWORK_TIMEOUTS,
                       cancel: Callable[[], bool] | None = None) -> tuple[ProfileSection, Sed]:
    """Sezione Fotometria e SED (25 §3.11): punti Gaia DR3, 2MASS, AllWISE, SIMBAD per gli identificativi della
    catena, serie VizieR separata; conversioni, qualità, duplicati e grafico dal ``20``.

    Un valore di ``cross_ids`` può essere una funzione senza argomenti che attende l'esito della catena: dentro
    ``build_profile`` la serie VizieR (altro servizio) parte subito (25 §3.16 C7-b), la richiesta Gaia appena è noto
    Gaia, 2MASS e AllWISE appena è noto il loro esito (§3.17 punto 5: al più 2 richieste per servizio). Con il CDS
    già giù la serie VizieR non si chiede (§3.17 punto 3): copia in cache se c'è, altrimenti
    ``PROFILE_VIZIER_SKIPPED`` dichiarato."""
    section = ProfileSection("photometry")
    pending = dict(cross_ids)

    def crossid(catalog: str) -> CrossIdentification | None:
        value = pending.get(catalog)
        return value() if callable(value) else value

    points, provs = [], []

    def add(new_points, prov: Provenance) -> None:
        points.extend(new_points)
        provs.extend([prov] * len(new_points))

    def attempt(function):
        """Una richiesta della sezione: ``(risultato, None)`` oppure ``(None, errore del 14)``."""
        def run():
            _check(cancel)
            try:
                return function(), None
            except VoProtocolsError as exc:
                return None, exc
        return run

    # Le quattro richieste (Gaia, 2MASS, AllWISE, VizieR) partono insieme dentro build_profile (25 §3.12 regola 2):
    # VizieR subito, ognuna delle altre appena è noto il suo identificativo (§3.16 C7-b, §3.17 punto 5); i risultati
    # si applicano sempre nello stesso ordine. Una richiesta senza identificativo restituisce ``None``.
    def gaia_job():
        gaia = crossid("gaia_dr3")
        if gaia is None or gaia.source_id is None:
            return None
        adql = f"SELECT {', '.join(_GAIA_PHOT_COLUMNS)} FROM {_GAIA_SOURCE} WHERE source_id = {gaia.source_id}"
        return _tap(_GAIA_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts), adql

    def irsa_job(catalog: str):
        def job():
            found = crossid(catalog)
            if found is None or found.identifier is None:
                return None
            if found.method == "position" and found.row is not None:  # riga già letta nella catena (C7-a)
                return found.requests[0], found.queries[0], found.row, ()
            return _irsa_by_designation(catalog, found.identifier, cache=cache, refresh=refresh, timeouts=timeouts)
        return job

    center, center_notes = _vizier_center(resolved)

    def vizier_job():
        from astrotwo.core.hips import cds_down_evidence

        down = cds_down_evidence(refresh=refresh)  # letta alla partenza della richiesta (§3.17 punto 3)
        if down is not None:
            hit = None if refresh else vizier_photometry_cached(center, VIZIER_SED_RADIUS, cache=cache)
            return hit if hit is not None else {"skipped": down}
        return _network("vizier_sed", vizier_photometry, center, VIZIER_SED_RADIUS, cache=cache, refresh=refresh,
                        timeouts=timeouts)

    jobs: list[tuple[str, Callable]] = [
        ("gaia_dr3", attempt(gaia_job)), ("2mass", attempt(irsa_job("2mass"))),
        ("allwise", attempt(irsa_job("allwise"))), ("vizier_sed", attempt(vizier_job))]
    answers = dict(zip([name for name, _ in jobs], _gather([job for _, job in jobs]), strict=True))
    answers = {k: v for k, v in answers.items() if v[0] is not None or v[1] is not None}
    _check(cancel)
    gaia = crossid("gaia_dr3")
    if "gaia_dr3" in answers:
        answer, exc = answers["gaia_dr3"]
        if exc is not None:
            section.errors.append({**_message(exc), "catalog": "Gaia DR3"})
        else:
            result, gaia_adql = answer
            section.requests.append(result.request)
            section.warnings.extend(_network_notes(result.warnings))
            prov = _provenance(result.request, _service_name(result.request.url), _GAIA_SOURCE, gaia_adql,
                               gaia.identifier, gaia.method)
            add(sed_points_from(result.table.table, "gaia_dr3", identifier=gaia.identifier, match=gaia.method,
                                provenance=prov.as_dict(), epoch="J2016.0 (ref_epoch)"), prov)
    for catalog in ("2mass", "allwise"):
        if catalog not in answers:
            continue
        found = crossid(catalog)
        answer, exc = answers[catalog]
        if exc is not None:
            section.errors.append({**_message(exc), "catalog": catalog})
            continue
        request, adql, rows, notes = answer
        section.requests.append(request)
        section.warnings.extend(_network_notes(notes))
        if len(rows) == 0:
            section.warnings.append(ModuleWarning(
                "PROFILE_NO_PHOTOMETRY", f"{found.identifier} non ha righe in {_IRSA_TABLE[catalog]}",
                {"reason": "not_in_catalog", "catalog": {"2mass": "2MASS", "allwise": "AllWISE"}[catalog],
                 "identifier": found.identifier, "table": _IRSA_TABLE[catalog]}))
            continue
        prov = _provenance(request, _service_name(request.url), _IRSA_TABLE[catalog], adql,
                           found.identifier, found.method)
        epoch = "MJD 55400.0 UTC (AllWISE Explanatory Supplement §II.1)" if catalog == "allwise" else None
        add(sed_points_from(rows[:1], catalog, identifier=found.identifier, match=found.method,
                            provenance=prov.as_dict(), epoch=epoch), prov)
    record = resolved.simbad
    if record is not None and len(record.requests) > 2:
        req = record.requests[2]
        prov = _provenance(req, _record_service(record), "flux", req.arguments.get("adql"), record.main_id,
                           "simbad_identifier")
        add(sed_points_from(record.magnitudes, "simbad", identifier=record.main_id, match="simbad_identifier",
                            provenance=prov.as_dict()), prov)
        section.requests.append(req)
    vizier = None
    section.warnings.extend(center_notes)
    result, exc = answers["vizier_sed"]
    if exc is not None:
        section.errors.append({**_message(exc), "catalog": "vizier_sed"})
    elif isinstance(result, dict):  # CDS già giù, nessuna copia: serie non chiesta, dichiarata (§3.17 punto 3)
        evidence = str(result["skipped"].get("evidence"))
        skipped = ObjectProfileError(
            "PROFILE_VIZIER_SKIPPED", f"serie SED di VizieR non chiesta: il CDS risulta già non raggiungibile "
            f"({evidence}); nessuna copia in cache",
            params={"reason": "cds_down", "evidence": evidence})
        section.errors.append({**_message(skipped), "catalog": "vizier_sed"})
    else:
        section.requests.append(result.request)
        section.warnings.extend(_network_notes(result.warnings))
        prov = _provenance(result.request, _service_name(result.request.url), "VizieR SED", None, None, "position")
        vizier = VizierSeries(result.table.table, prov.as_dict())
    pmra, pmdec, _ = _simbad_motion(resolved)
    fast = high_proper_motion(pmra, pmdec)
    if fast is not None:
        section.warnings.append(fast)
    sed = build_sed(points, vizier)
    for point, prov in zip(sed.points, provs, strict=True):
        section.values.extend(_point_values(point, prov))
    name = resolved.simbad.main_id if resolved.simbad is not None else None
    title = None if name is None else " ".join(name.split())
    cra, cdec = _icrs_deg(center)
    skip = answers["vizier_sed"][0]["skipped"] if isinstance(answers["vizier_sed"][0], dict) else None
    section.details = {**sed.as_dict(), **({"vizier_sed": {"skipped": True, "reason": "cds_down",
                                                            "evidence": skip.get("evidence")}} if skip else {}),
                       "vizier_center": {"ra": {"value": cra, "unit": "deg"},
                                                          "dec": {"value": cdec, "unit": "deg"},
                                                          "epoch": None if center.epoch is None else
                                                          center.epoch.jyear_str,
                                                          "radius": _qj(VIZIER_SED_RADIUS, "arcsec")},
                       "plot_png": {"format": "image/png", "encoding": "base64", "quantity": "fnu",
                                    "data": sed_png(sed, title=title, encoded=True)} if sed.plotted or vizier
                       else None}
    if not points and not (vizier and len(vizier.table)):
        section.status = "error" if section.errors else "not_applicable"
    else:
        section.status = "partial" if section.errors else "done"
    return section, sed


# --------------------------------------------------------------------------
# Immagini (25 §3.13, D25-5): miniature HiPS del 12
# --------------------------------------------------------------------------


def _thumbnail_center(resolved: ResolvedTarget, epoch: dict | None) -> tuple[SkyFrame, str, tuple]:
    """Centro della miniatura: all'epoca della survey se nota (con il moto proprio SIMBAD), altrimenti la posizione
    del bersaglio così com'è (SIMBAD J2000 o coordinate scritte), dichiarato."""
    position = resolved.position
    where = "SIMBAD position (ICRS J2000)" if resolved.simbad is not None else resolved.position_source
    if epoch is None:
        return position, (f"survey epoch not known (observations longer than one year, or t_min/t_max missing): "
                          f"centre = {where}"), ()
    target = Time(epoch["mjd"], format="mjd", scale="utc")
    moved, notes = _propagated(resolved, target, "la miniatura")
    if notes:
        return position, f"survey epoch {epoch['jyear']!r} without a known proper motion: centre = {where}", notes
    return moved, (f"centre moved to the survey epoch (MJD {epoch['mjd']!r} UTC, {epoch['jyear']!r}) with the SIMBAD "
                   f"proper motion from {where} (propagate_position of module 10)"), ()


def profile_images(resolved: ResolvedTarget, *, surveys: Sequence[str] = IMAGE_SURVEYS,
                   fov: u.Quantity = DEFAULT_THUMBNAIL_FOV, size: int = DEFAULT_THUMBNAIL_SIZE,
                   cache: SharedCache | None = None, refresh: bool = False,
                   timeouts: NetworkTimeouts = NETWORK_TIMEOUTS,
                   cancel: Callable[[], bool] | None = None) -> ProfileSection:
    """Sezione Immagini (25 §3.13): una miniatura TAN per survey con ``hips_thumbnail`` del 12 (mirror compresi);
    un survey giù resta un errore della sola miniatura."""
    import base64

    from astrotwo.core.hips import HiPSError, add_hips, cds_down_evidence, hips_thumbnail, survey_epoch

    section = ProfileSection("images")

    def one(hips_id: str):
        def run():
            _check(cancel)
            try:
                service = _network("hips", add_hips, hips_id, cache=cache, refresh=refresh, timeouts=timeouts,
                                   cds_down_shortcut=True)  # D25-18: CDS già giù → subito i mirror verificati
                _check(cancel)
                center, note, notes = _thumbnail_center(resolved, survey_epoch(service))
                thumb = _network("hips", hips_thumbnail, service, center, fov=fov, size=size, cache=cache,
                                 refresh=refresh, timeouts=timeouts)
            except (HiPSError, VoProtocolsError) as exc:
                return hips_id, None, exc
            return hips_id, (service, thumb, note, notes), None
        return run

    # Stato del CDS non noto (nella sessione; con refresh, nel profilo: §3.17 punto 2): prima un survey, poi gli altri
    # insieme; se il MocServer non ha risposto gli altri prendono subito la scorciatoia di D25-18 (25 §3.16 C7-d).
    first: list = []
    if surveys and cds_down_evidence(refresh=refresh) is None:
        first = _gather([one(surveys[0])])
    thumbnails = []
    for hips_id, found, exc in first + _gather([one(h) for h in surveys[len(first):]]):
        if exc is not None:
            section.errors.append({**_message(exc), "survey": hips_id})
            continue
        service, thumb, note, notes = found
        section.warnings.extend(notes)
        section.warnings.extend(w for w in tuple(service.warnings) + tuple(thumb.warnings)
                                if w[0] in ("HIPS_MIRROR_FALLBACK", "HIPS_MIRROR_REJECTED", "FROM_CACHE"))
        if service.request is not None:
            section.requests.append(service.request)
        thumbnails.append({**thumb.as_dict(), "center_note": note,
                           "png": base64.b64encode(thumb.png()).decode("ascii") if thumb.format != "fits" else None})
    section.details = {"thumbnails": thumbnails, "surveys": list(surveys), "fov": _qj(fov, "arcmin"), "size": size}
    if not thumbnails:
        section.status = "error" if section.errors else "not_applicable"
    else:
        section.status = "partial" if section.errors else "done"
    return section


# --------------------------------------------------------------------------
# Pianeti (25 §3.13, D25-3): NASA Exoplanet Archive, pscomppars
# --------------------------------------------------------------------------

#: Parametri dei pianeti (colonna di ``pscomppars`` → unità). Unità dichiarate dall'archivio nel ``TAP_SCHEMA.columns``
#: (letto il 2026-11-07); dove una colonna non la dichiara (``pl_orbsmax``, errori di ``pl_bmasse``) vale quella della
#: stessa grandezza nelle altre colonne (``pl_orbsmaxerr1`` au, ``pl_bmasse`` masse terrestri), 25 §3.13.
PLANET_PARAMETERS: Mapping[str, tuple[str, u.UnitBase]] = {
    "period": ("pl_orbper", u.d), "semi_major_axis": ("pl_orbsmax", u.AU),
    "eccentricity": ("pl_orbeccen", u.dimensionless_unscaled), "mass": ("pl_bmasse", u.M_earth),
    "radius": ("pl_rade", u.R_earth), "equilibrium_temperature": ("pl_eqt", u.K)}
_PLANET_TEXT = ("pl_name", "pl_letter", "hostname", "gaia_dr3_id", "discoverymethod", "disc_year", "pl_bmassprov")
_HREF = re.compile(r"""href\s*=\s*["']?([^"'\s>]+)""", re.IGNORECASE)
_ADS_BIBCODE = re.compile(r"/abs/([^/?#]+)")
_TAG = re.compile(r"<[^>]*>")


def parse_reflink(text: str | None) -> dict | None:
    """Riferimento da un ``*_reflink`` dell'Exoplanet Archive (frammento HTML, testo esterno): solo il testo visibile
    e, se il collegamento è di ADS, URL e bibcode (25 §3.13, T16). Nulla viene eseguito."""
    import html

    if text is None or not str(text).strip():
        return None
    raw = str(text)
    label = " ".join(html.unescape(_TAG.sub(" ", raw)).split()) or None
    out = {"text": label, "url": None, "bibcode": None}
    match = _HREF.search(raw)
    if match is not None:
        url = html.unescape(match.group(1))
        host = urllib.parse.urlparse(url).hostname or ""
        if host.endswith("adsabs.harvard.edu"):
            out["url"] = url
            bib = _ADS_BIBCODE.search(urllib.parse.urlparse(url).path)
            if bib is not None:
                out["bibcode"] = urllib.parse.unquote(bib.group(1))
    return out


def _planet_columns() -> str:
    cols = list(_PLANET_TEXT)
    for column, _unit in PLANET_PARAMETERS.values():
        cols += [column, f"{column}err1", f"{column}err2", f"{column}lim", f"{column}_reflink"]
    return ", ".join(cols)


def _as_unit(value, unit) -> u.Quantity | None:
    if value is None:
        return None
    number = float(value.value) if isinstance(value, u.Quantity) else float(value)
    return u.Quantity(number, unit, dtype=np.float64)


def profile_planets(resolved: ResolvedTarget, host: CrossIdentification | None, *, cache: SharedCache | None = None,
                    refresh: bool = False, timeouts: NetworkTimeouts = NETWORK_TIMEOUTS,
                    cancel: Callable[[], bool] | None = None) -> ProfileSection:
    """Sezione Pianeti (25 §3.13): ``pscomppars`` per ``gaia_dr3_id`` o ``hostname`` (come l'ospite è stato trovato);
    parametri letti con errori, limite e riferimento. «Nessun pianeta nell'archivio» solo dopo una richiesta vera e
    riuscita all'archivio (``details["checked"]``, D25-23); senza richiesta → ``not_applicable`` «non controllato»
    con ``PROFILE_PLANETS_NOT_CHECKED``; richiesta fallita → ``error``."""
    section = ProfileSection("planets")
    if host is None or host.identifier is None:
        if host is not None and host.error is not None:
            section.errors.append({**host.error, "catalog": "exoplanet"})
            section.details = {"planets": [], "checked": False}
            section.status = "error"
            return section
        if host is None or not host.requests:
            warning = next((w for w in (host.warnings if host is not None else ()) if
                            w[0] == "PROFILE_PLANETS_NOT_CHECKED"), None) or _planets_not_checked(resolved)
            section.warnings.append(warning)
            section.details = {"planets": [], "checked": False, "note": PLANETS_NOT_CHECKED_NOTE}
            section.status = "not_applicable"
            return section
        section.requests.extend(host.requests)  # le richieste che danno l'assenza (D25-23)
        section.warnings.extend(_network_notes(host.warnings))
        section.details = {"planets": [], "checked": True, "note": "no planet in the archive"
                           + (f" ({host.note})" if host.note else "")}
        section.status = "done"
        return section
    official = dict(host.official or {})
    if official.get("gaia_dr3_id"):
        where = f"gaia_dr3_id = {_adql_text(str(official['gaia_dr3_id']))}"
    else:
        where = f"hostname = {_adql_text(host.identifier)}"
    adql = f"SELECT {_planet_columns()} FROM pscomppars WHERE {where} ORDER BY pl_name"
    _check(cancel)
    try:
        result = _tap(_EXOPLANET_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts)
    except VoProtocolsError as exc:
        section.errors.append({**_message(exc), "catalog": "exoplanet"})
        section.status = "error"
        return section
    section.requests.append(result.request)
    section.warnings.extend(_network_notes(result.warnings))
    prov = _provenance(result.request, _service_name(result.request.url), "pscomppars", adql, host.identifier,
                       host.method)
    planets, references = [], set()
    for row in result.table.table:
        name = _value(row, "pl_name")
        planet = {k: _value(row, k) for k in _PLANET_TEXT}
        planet["parameters"] = {}
        for key in ("discoverymethod", "disc_year"):
            if planet[key] is not None:
                section.values.append(ProfileValue(f"{name} {key}", planet[key], prov))
        for key, (column, unit) in PLANET_PARAMETERS.items():
            value = _as_unit(_value(row, column), unit)
            ref = parse_reflink(_value(row, f"{column}_reflink"))
            limit = _value(row, f"{column}lim")
            upper, lower = _as_unit(_value(row, f"{column}err1"), unit), _as_unit(_value(row, f"{column}err2"), unit)
            entry = {"column": column, "value": None if value is None else _qj(value),
                     "error_upper": None if upper is None else _qj(upper),
                     "error_lower": None if lower is None else _qj(lower),
                     "limit": {1: "upper", -1: "lower", 0: None}.get(limit, limit), "reference": ref}
            if key == "mass":
                entry["mass_provenance"] = planet["pl_bmassprov"]
            planet["parameters"][key] = entry
            if value is None:
                continue
            if ref is not None:
                references.add(ref.get("bibcode") or ref.get("text"))
            note = None
            if key == "mass" and planet["pl_bmassprov"]:
                note = f"pl_bmassprov = {planet['pl_bmassprov']}"
            if entry["limit"] in ("upper", "lower"):
                note = "; ".join(x for x in (note, f"{'upper' if entry['limit'] == 'upper' else 'lower'} limit"
                                             f" ({column}lim = {limit})") if x)
            section.values.append(ProfileValue(f"{name} {key}", value, prov, error_upper=upper, error_lower=lower,
                                               reference=None if ref is None else (ref["bibcode"] or ref["text"]),
                                               note=note))
        planets.append(planet)
    section.details = {"planets": planets, "host": host.identifier, "query_by": where.split(" =")[0],
                       "checked": True, "note": None if planets else "no planet in the archive"}
    if host.method == "written_name":
        section.warnings.append(ModuleWarning(
            "PROFILE_PLANETS_BY_WRITTEN_NAME", f"ospite {host.identifier} trovato per il nome scritto (SIMBAD non "
            "disponibile): identità non verificata", {"host": host.identifier}))
    if planets:
        section.warnings.append(ModuleWarning(
            "PROFILE_PLANETS_COMPOSITE", f"{len(planets)} pianeti da pscomppars: i parametri possono venire da lavori "
            f"diversi ({len(references)} riferimenti distinti)",
            {"count": len(planets), "references": len(references), "table": "pscomppars"}))
    section.status = "done"
    return section


def planets_absence_shown(section: Mapping | None, chain: Sequence[Mapping] = ()) -> bool:
    """Vero se la sezione Pianeti (forma JSON) può dire «nessun pianeta nell'archivio» (D25-23): sezione ``done`` o
    ``partial``, nessun pianeta, e una richiesta vera e riuscita all'archivio. Risultati registrati prima del
    2026-11-10 (senza ``checked``): la richiesta si riconosce da ``query_by`` o dalle interrogazioni del passo
    ``exoplanet`` della catena (``chain``); altrimenti «non controllato»."""
    if not section or section.get("status") not in ("done", "partial"):
        return False
    details = section.get("details") or {}
    if details.get("planets"):
        return False
    if "checked" in details:
        return bool(details["checked"])
    if details.get("query_by"):
        return True
    return any(c.get("catalog") == "exoplanet" and c.get("queries") and not c.get("error") for c in chain)


def section_not_checked(section: Mapping | None, chain: Sequence[Mapping] = ()) -> bool:
    """Vero se la sezione (forma JSON) non è stata controllata: ``details["checked"]`` falso e nessun errore né
    annullamento (decisione del proprietario del 2026-11-10: intestazione «Not checked» / «Non controllata», per
    ogni sezione con ``checked`` falso). Sezione Pianeti registrata prima del 2026-11-10 (senza ``checked``) e
    senza prova della richiesta: non controllata (D25-23, ``planets_absence_shown``)."""
    if not section or section.get("status") in ("error", "cancelled"):
        return False
    details = section.get("details") or {}
    if "checked" in details:
        return details["checked"] is False
    if section.get("name") == "planets" and not details.get("planets"):
        return not planets_absence_shown(section, chain)
    return False


# --------------------------------------------------------------------------
# Profilo completo (25 §7.1)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ObjectProfile:
    """Profilo: bersaglio risolto, identificativi, sezioni, avvisi, richieste di rete."""

    target: ProfileTarget
    resolved: ResolvedTarget
    cross_ids: tuple[CrossIdentification, ...]
    sections: tuple[ProfileSection, ...]
    warnings: tuple = ()
    options: Mapping[str, object] = field(default_factory=dict)
    cancelled: bool = False  # annullato: sezioni arrivate conservate, le altre ``cancelled`` (25 §3.12)
    elapsed: float | None = None  # s, dalla chiamata (obiettivo PROFILE_TARGET_TIME, misurato, non un limite)
    skipped_services: Mapping[str, Mapping] = field(default_factory=dict)  # D25-22 (12 a): servizio → prova, n

    @property
    def requests(self) -> tuple[RequestRecord, ...]:
        seen, out = set(), []
        for req in (list(self.resolved.requests) + [r for c in self.cross_ids for r in c.requests]
                    + [r for s in self.sections for r in s.requests]):
            key = (req.url, req.params)
            if key not in seen:
                seen.add(key)
                out.append(req)
        return tuple(out)

    def as_dict(self) -> dict:
        return {"target": self.target.as_dict(), "resolved": self.resolved.as_dict(), "options": dict(self.options),
                "cross_identifications": [c.as_dict() for c in self.cross_ids],
                "sections": [s.as_dict() for s in self.sections],
                "warnings": [_warning_json(w) for w in self.warnings], "cancelled": self.cancelled,
                "elapsed": None if self.elapsed is None else {"value": self.elapsed, "unit": "s"},
                "skipped_services": {k: dict(v) for k, v in self.skipped_services.items()}}


#: avvisi della catena che l'Identità mostra (nessuna scelta tra due esiti, 25 §3.10 e §3.14)
_CHAIN_CONFLICTS = ("PROFILE_IDENTIFIER_CONFLICT", "PROFILE_PLANET_HOST_MISMATCH")


def _section_limit(name: str) -> u.Quantity:
    """Tempo massimo di una sezione: ``SECTION_TIME_LIMITS`` (Astrometria 35 s, D25-22) o il più grande tra quelli
    dei suoi servizi (25 §3.12 regola 5)."""
    if name in SECTION_TIME_LIMITS:
        return SECTION_TIME_LIMITS[name]
    return max((SERVICE_TIME_LIMITS[s] for s in SECTION_SERVICES[name]), key=lambda q: float(q.to_value(u.s)))


def _cross_failed(catalog: str, exc: VoProtocolsError) -> CrossIdentification:
    return CrossIdentification(catalog, None, None, note="cross-match failed", error=_message(exc))


def build_profile(target: ProfileTarget, *, sections: Sequence[str] = SECTIONS,
                  match_radius: u.Quantity = DEFAULT_MATCH_RADIUS,
                  crossmatch_radius: u.Quantity = DEFAULT_CROSSMATCH_RADIUS,
                  on_section: Callable[[ProfileSection], None] | None = None,
                  on_resolved: Callable[[ResolvedTarget], None] | None = None,
                  cancel: Callable[[], bool] | None = None, cache: SharedCache | None = None,
                  refresh: bool = False, timeouts: NetworkTimeouts = NETWORK_TIMEOUTS,
                  surveys: Sequence[str] = IMAGE_SURVEYS, thumbnail_fov: u.Quantity = DEFAULT_THUMBNAIL_FOV,
                  thumbnail_size: int = DEFAULT_THUMBNAIL_SIZE) -> ObjectProfile | None:
    """Profilo (25 §3.12, §3.13): bersaglio, poi tutte le sezioni insieme con al più ``MAX_CONCURRENT_REQUESTS`` richieste
    contemporanee e il tempo massimo di ogni sezione; ``on_section`` nel thread di chi chiama, una volta per sezione,
    nell'ordine di arrivo.

    Più candidati → ``PROFILE_AMBIGUOUS_TARGET`` con l'elenco (nessuna scelta). Annullato prima che il bersaglio sia
    risolto → ``None``; dopo → ``ObjectProfile`` con ``cancelled = True``, sezioni arrivate conservate e le altre nello
    stato ``cancelled``."""
    unknown = [s for s in sections if s not in SECTIONS]
    if unknown or not sections:
        raise ValueError(f"sezioni {unknown or list(sections)} non in {SECTIONS}")
    for name, value in (("match_radius", match_radius), ("crossmatch_radius", crossmatch_radius)):
        if not isinstance(value, u.Quantity) or not value.unit.is_equivalent(u.deg) or not value.value > 0:
            raise ValueError(f"{name}: angolo positivo con unità")
    started = time.monotonic()
    if _cancelled(cancel):
        return None
    if isinstance(cache, SharedCache):
        cache = _ThreadCaches(cache)
    run = _Run()
    net = dict(cache=cache, refresh=refresh, timeouts=timeouts)
    scope = contextlib.ExitStack()
    if refresh:  # giro con dati aggiornati: dal principale una volta per profilo (§3.17 punto 2)
        scope.enter_context(refresh_once())
    try:
        # 1. Bersaglio (regola 1): annullabile, nessun limite complessivo (ripiego su NED, §3.10).
        future = run.submit(resolve_target, target, match_radius=match_radius, **net)
        while not future.done():
            if _cancelled(cancel):
                return None
            time.sleep(_POLL / 5)
        resolved = future.result()
        if isinstance(resolved, TargetCandidates):
            raise ObjectProfileError(
                "PROFILE_AMBIGUOUS_TARGET", f"{len(resolved.candidates)} oggetti SIMBAD entro "
                f"{float(match_radius.to_value(u.arcsec))!r} arcsec: scegliere l'oggetto ("
                + ", ".join(str(c["main_id"]) for c in resolved.candidates) + ")",
                params={"count": len(resolved.candidates), "radius": _qj(match_radius, "arcsec"),
                        "candidates": [dict(c) for c in resolved.candidates]})
        if _cancelled(cancel):
            return None
        if on_resolved is not None:  # bersaglio risolto, prima delle sezioni, nel thread di chi chiama (43 §3.5)
            on_resolved(resolved)
        names = [name for name in SECTIONS if name in sections]
        flags = {name: threading.Event() for name in names}

        def stopper(name: str) -> Callable[[], bool]:
            return lambda: run.stop.is_set() or flags[name].is_set() or _cancelled(cancel)

        # 2. Catena degli identificativi condivisa (regola 2): Gaia una volta, gli altri appena Gaia è noto.
        needed: set[str] = set()
        if "identity" in names and resolved.simbad is not None:
            needed.update(CATALOGS)
        if "astrometry" in names:
            needed.add("gaia_dr3")
        if "photometry" in names:
            needed.update(("gaia_dr3", "2mass", "allwise"))
        if "planets" in names:
            needed.update(("gaia_dr3", "exoplanet"))

        def identify_gaia() -> CrossIdentification:
            try:
                return cross_identify(resolved, "gaia_dr3", crossmatch_radius=crossmatch_radius, **net)
            except VoProtocolsError as exc:
                return _cross_failed("gaia_dr3", exc)

        ids: dict[str, Future] = {}
        finished: dict[str, float] = {}  # istante in cui finisce ogni passo della catena (§3.17 punto 4)

        def submit_step(key: str, fn: Callable[[], CrossIdentification]) -> None:
            def step():
                try:
                    return fn()
                finally:
                    finished[key] = time.monotonic()
            ids[key] = run.submit(step)

        sections_started = time.monotonic()
        if needed:
            submit_step("gaia_dr3", identify_gaia)
        early_host = "exoplanet" in needed and exoplanet_host_early(resolved)
        if early_host:  # D25-17 (10): ospite subito per hostname, poi verifica con gaia_dr3_id quando Gaia arriva
            def host_by_name() -> CrossIdentification:
                try:
                    return _exoplanet_by_hostname(resolved, _ExoplanetAsk(**net))
                except VoProtocolsError as exc:
                    return _cross_failed("exoplanet", exc)

            def host_checked() -> CrossIdentification:
                early = run.wait(ids["exoplanet_hostname"])
                gaia = run.wait(ids["gaia_dr3"])
                try:
                    return check_exoplanet_host(early, gaia, **net)
                except VoProtocolsError as exc:  # verifica non riuscita: resta l'esito per hostname, con l'errore
                    return dataclasses.replace(early, error=_message(exc), note="check with gaia_dr3_id failed")
            submit_step("exoplanet_hostname", host_by_name)
        for catalog in CATALOGS[1:]:
            if catalog == "exoplanet" and early_host:
                submit_step(catalog, host_checked)
            elif catalog in needed:
                def identify(catalog: str = catalog) -> CrossIdentification:
                    gaia = run.wait(ids["gaia_dr3"])
                    try:
                        return cross_identify(resolved, catalog, gaia=gaia, crossmatch_radius=crossmatch_radius,
                                              **net)
                    except VoProtocolsError as exc:
                        return _cross_failed(catalog, exc)
                submit_step(catalog, identify)

        def known(catalogs) -> list[CrossIdentification]:
            return [run.wait(ids[c]) for c in CATALOGS if c in catalogs and c in ids]

        # 3. Sezioni (regole 2, 5, 6).
        def identity_section() -> ProfileSection:
            section = profile_identity(resolved)
            if section.status != "done":
                return section
            found = known(CATALOGS)
            for c in found:
                if c.error is not None:
                    section.errors.append({**c.error, "catalog": c.catalog})
            section.details["cross_identifications"] = [c.as_dict() for c in found]
            for c in found:
                section.warnings.extend(w for w in c.warnings if w[0] in _CHAIN_CONFLICTS)
                section.requests.extend(c.requests)
            if section.errors:
                section.status = "partial"
            return section

        def astrometry_section() -> ProfileSection:
            gaia = run.wait(ids["gaia_dr3"])

            def without_gaia(error: dict) -> ProfileSection:  # servizio Gaia non riuscito: SIMBAD con la fonte
                section = ProfileSection("astrometry", errors=[error])
                if resolved.simbad is not None:
                    _simbad_astrometry(section, resolved.simbad)
                    section.requests.append(resolved.simbad.requests[0])
                    values, notes = distance_from(None, next((v for v in section.values if v.quantity == "parallax"),
                                                             None))
                    section.values.extend(values)
                    section.warnings.extend(notes)
                section.status = "partial" if section.values else "error"
                return section

            if gaia.error is not None:  # incrocio per posizione con Gaia non riuscito
                return without_gaia(dict(gaia.error))
            try:
                return profile_astrometry(resolved, gaia, cancel=stopper("astrometry"), **net)
            except VoProtocolsError as exc:
                return without_gaia(_message(exc))

        def photometry_section() -> ProfileSection:
            waits = {c: (lambda c=c: run.wait(ids[c])) for c in ("gaia_dr3", "2mass", "allwise") if c in ids}
            section, _sed = profile_photometry(resolved, waits, cancel=stopper("photometry"), **net)  # C7-b
            if "identity" not in names:
                found = known(("gaia_dr3", "2mass", "allwise"))
                section.details["cross_identifications"] = [c.as_dict() for c in found]
                for c in found:
                    section.warnings.extend(w for w in c.warnings if w[0] in ("PROFILE_POSITIONAL_MATCH",
                                                                              "PROFILE_IDENTIFIER_CONFLICT"))
                    section.requests.extend(r for r in c.requests if r not in section.requests)  # C7-a: una volta
            return section

        def images_section() -> ProfileSection:
            return profile_images(resolved, surveys=surveys, fov=thumbnail_fov, size=thumbnail_size,
                                  cancel=stopper("images"), **net)

        def planets_section() -> ProfileSection:
            host = run.wait(ids["exoplanet_hostname" if early_host else "exoplanet"])
            return profile_planets(resolved, host, cancel=stopper("planets"), **net)

        builders = {"identity": identity_section, "astrometry": astrometry_section,
                    "photometry": photometry_section, "images": images_section, "planets": planets_section}
        arrivals: queue.Queue = queue.Queue()

        def run_section(name: str) -> None:
            try:
                section = builders[name]()
            except _Cancelled:
                return
            except BaseException as exc:  # noqa: BLE001 - errore di programmazione: risale nel thread di chi chiama
                arrivals.put((name, None, exc))
                return
            arrivals.put((name, section, None))

        # Partenza di ogni sezione (§3.17 punto 4): fine dell'ultimo passo della catena che aspetta; nessuno → subito.
        waits_for = {"identity": list(CATALOGS) if resolved.simbad is not None else [], "images": [],
                     "astrometry": ["gaia_dr3"], "photometry": ["gaia_dr3", "2mass", "allwise"],
                     "planets": ["exoplanet_hostname" if early_host else "exoplanet"]}
        waits_for = {name: [k for k in waits_for[name] if k in ids] for name in names}

        def started_at(name: str) -> float | None:
            keys = waits_for[name]
            if any(k not in finished for k in keys):
                return None
            return max((finished[k] for k in keys), default=sections_started)

        for name in names:
            run.submit(run_section, name)
        done: dict[str, ProfileSection] = {}
        cancelled = False

        def announce(section: ProfileSection) -> None:
            start = started_at(section.name)
            section.started = None if start is None else start - sections_started
            done[section.name] = section
            if on_section is not None:
                on_section(section)

        while len(done) < len(names):
            try:
                arrival = arrivals.get(timeout=_POLL)  # attesa senza il turno della CPU
            except queue.Empty:
                arrival = None
            with cpu_turn(run.cpu):  # come i thread di lavoro: unità di Astropy e on_section un thread alla volta
                if _cancelled(cancel):  # regola 7: arrivate conservate, le altre annullate
                    run.stop.set()
                    cancelled = True
                    for name in names:
                        if name not in done:
                            announce(ProfileSection(name, status="cancelled",
                                                    elapsed=time.monotonic() - sections_started))
                    break
                if arrival is not None and arrival[0] not in done:
                    name, section, exc = arrival
                    if exc is not None:
                        raise exc
                    section.elapsed = time.monotonic() - sections_started
                    announce(section)
                now = time.monotonic()
                for name in names:
                    start = None if name in done else started_at(name)
                    if start is not None and now >= start + float(_section_limit(name).to_value(u.s)):
                        # regola 5 contata dalla partenza (§3.17 punto 4): scaduta, le altre continuano
                        flags[name].set()
                        limit = _section_limit(name)
                        services = list(SECTION_SERVICES[name])
                        timeout = ObjectProfileError(
                            "PROFILE_SECTION_TIMEOUT", f"sezione {name}: nessuna risposta entro "
                            f"{float(limit.to_value(u.s))!r} s ({', '.join(services)})",
                            params={"section": name, "limit": _qj(limit, "s"), "services": services})
                        announce(ProfileSection(name, status="error", elapsed=now - sections_started,
                                                errors=[_message(timeout)]))
        # Un solo esito per l'Exoplanet Archive: la verifica con gaia_dr3_id se è finita (l'Identità la aspetta
        # sempre), altrimenti la ricerca per hostname usata dai Pianeti (D25-17 (10), 25 §3.14).
        if early_host and not ids["exoplanet"].done():
            ids["exoplanet"] = ids["exoplanet_hostname"]
        ids.pop("exoplanet_hostname", None)
        cross_ids = [f.result() for c, f in ids.items() if f.done() and not f.cancelled() and f.exception() is None]
        order = {c: k for k, c in enumerate(CATALOGS)}
        cross_ids.sort(key=lambda c: order[c.catalog])
        chain_notes = tuple(w for c in cross_ids for w in c.warnings if w[0] == "PROFILE_PLANET_HOST_MISMATCH")
    except _Cancelled:
        return None
    finally:
        run.stop.set()  # le richieste ancora in corso (sezioni scadute o annullate) si scartano quando finiscono
        run.pool.shutdown(wait=False, cancel_futures=True)
        scope.close()
    options = {"sections": list(sections), "match_radius": _qj(match_radius, "arcsec"),
               "crossmatch_radius": _qj(crossmatch_radius, "arcsec"), "surveys": list(surveys),
               "thumbnail_fov": _qj(thumbnail_fov, "arcmin"), "thumbnail_size": int(thumbnail_size)}
    skipped = {s: {"evidence": run.down[s]["evidence"], "requests": n} for s, n in run.skipped.items()}
    return ObjectProfile(target, resolved, tuple(cross_ids), tuple(done[name] for name in names),
                         tuple(resolved.warnings) + chain_notes, options, cancelled=cancelled,
                         elapsed=time.monotonic() - started, skipped_services=skipped)


# --------------------------------------------------------------------------
# Comando object.profile (05 §7, comando del livello 2; 25 §3.10)
# --------------------------------------------------------------------------


#: plot_png: disegnato dai valori (25 §3.11); png: miniature disegnate dai tile, la cui provenienza resta (§3.13)
_RUN_KEYS = ("retrieved_at", "from_cache", "elapsed", "started", "plot_png", "png")
_RUN_CODES = ("FROM_CACHE", "SERVICE_MIRROR_FALLBACK", "DATA_REFRESHED", "HIPS_MIRROR_FALLBACK")  # D25-18


def profile_content(data):
    """Forma JSON del profilo senza ciò che cambia a ogni esecuzione (data, cache, tempi, avvisi di rete): il
    contenuto scientifico, per l'impronta di rete (D05-2) e per confrontare due esecuzioni."""
    if isinstance(data, Mapping):
        return {k: profile_content(v) for k, v in data.items() if k not in _RUN_KEYS}
    if isinstance(data, list):
        return [profile_content(v) for v in data
                if not (isinstance(v, Mapping) and v.get("code") in _RUN_CODES and "text" in v)]
    return data


#: Chiavi tolte nel riassunto per il modello (32 §3.7bis): immagini, ADQL, duplicati dei valori; nessun numero nuovo
_MODEL_DROP_DETAILS = {"photometry": ("zero_points", "plot_png"), "identity": ("identifiers",)}
_MODEL_THUMB = ("hips_id", "title", "fov", "size", "order", "center", "pixels_with_data", "epoch")
#: campi di un punto della SED nel riassunto (la tabella dei punti al posto dei valori duplicati, 25 §11)
_MODEL_POINT = ("catalog", "band", "system", "magnitude", "magnitude_error", "count_rate", "count_rate_error",
                "quality", "wavelength", "flux", "flux_error", "in_plot", "duplicate_of", "reference", "zero_point")
_MODEL_PLANET_TEXT = ("discoverymethod", "disc_year")
#: byte del riassunto (JSON) oltre i quali si tolgono pianeti interi dalla coda, dichiarato (32 §3.7bis): il resto
#: del limite di 20 kB del 32 serve ai testi esterni marcati e all'intestazione del risultato
MODEL_BUDGET = 13_000


def _without(value, keys=("query", "queries")):
    """Senza ADQL, chiavi nulle ed elenchi vuoti (nessuna informazione persa)."""
    if isinstance(value, Mapping):
        out = {k: _without(v, keys) for k, v in value.items() if k not in keys and v is not None}
        return {k: v for k, v in out.items() if not (isinstance(v, (list, dict)) and not v)}
    if isinstance(value, list):
        return [_without(v, keys) for v in value]
    return value


def _trim(values: dict) -> None:
    """Oltre ``MODEL_BUDGET``: prima le magnitudini di SIMBAD (fuori dal grafico, in magnitudini), poi le descrizioni
    delle miniature, poi i pianeti dalla coda; ogni taglio dichiarato in ``truncated`` della sezione con il totale (32 §3.7bis)."""
    sections = {s.get("name"): s for s in values.get("sections") or []}
    photometry = sections.get("photometry")
    if photometry is not None and _json_size(values) > MODEL_BUDGET:
        points = photometry.get("details", {}).get("points") or []
        kept = [p for p in points if p.get("catalog") != "SIMBAD"]
        removed = "SIMBAD magnitudes (not in the plot)"
        if len(kept) < len(points):
            photometry["details"]["points"] = kept
        if _json_size(values) > MODEL_BUDGET:  # poi i punti fuori dal grafico che non sono limiti superiori
            kept = [p for p in kept if p.get("in_plot") or p.get("upper_limit")]
            photometry["details"]["points"] = kept
            removed = "SIMBAD magnitudes and points out of the plot that are not upper limits"
        if len(kept) < len(points):
            photometry["truncated"] = {"points_total": len(points), "points_kept": len(kept), "removed": removed}
    images = sections.get("images")
    if images is not None and _json_size(values) > MODEL_BUDGET:
        thumbs = images.get("details", {}).get("thumbnails") or []
        if thumbs:
            images["details"]["thumbnails"] = [{"hips_id": t.get("hips_id")} for t in thumbs]
            images["truncated"] = {"removed": "thumbnail descriptions (the images are shown in the Profiles window)"}
    planets = sections.get("planets")
    if planets is not None and _json_size(values) > MODEL_BUDGET:
        rows = planets.get("details", {}).get("planets") or []
        total = len(rows)
        while len(rows) > 1 and _json_size(values) > MODEL_BUDGET:
            gone = rows.pop()
            prefix = f"{gone.get('pl_name')} "
            planets["values"] = [v for v in planets["values"] if not str(v.get("quantity", "")).startswith(prefix)]
        if len(rows) < total:
            planets["truncated"] = {"planets_total": total, "planets_kept": len(rows),
                                    "removed": "planets from the end; ask sections = [planets] for all of them"}


def _json_size(value) -> int:
    import json

    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def model_view(full: Mapping) -> dict:
    """Riassunto per il modello del risultato di ``object.profile`` (25 §11, 32 §3.7bis): ``full`` = ``{"values",
    "provenance"}`` del risultato completo. Stessa struttura del risultato, senza PNG, ADQL, chiavi nulle e duplicati
    dei valori; la provenienza di ogni valore è nell'elenco ``sources`` della sua sezione (``source`` = indice) e le
    formule in ``formulas`` (``formula`` = indice). Ogni numero restante è quello del risultato, mai cambiato. Oltre
    ``MODEL_BUDGET`` si tolgono pianeti interi dalla coda, dichiarati in ``truncated`` della sezione."""
    import copy

    values = copy.deepcopy(dict(full.get("values") or {}))
    for key in ("cross_identifications", "options"):
        values.pop(key, None)
    for section in values.get("sections") or []:
        details = section.get("details") or {}
        name = section.get("name")
        # gli avvisi delle sezioni sono già tra gli avvisi del risultato (resi in inglese dal 32); i server sono nelle
        # fonti dei valori
        section.pop("warnings", None)
        section.pop("servers", None)
        section.pop("elapsed", None)
        details.pop("identifiers_provenance", None)  # stessa fonte dei valori dell'Identità
        details.pop("simbad_url", None)
        if name == "photometry":
            # la tabella dei punti (stessi numeri dei valori della sezione) al posto dei valori: fonte e formula per
            # indice, motivi come codici; i limiti superiori hanno upper_limit vero (mai una misura, D43-9)
            points, sources, formulas = [], [], []
            for p in details.get("points") or []:
                item = {k: p.get(k) for k in _MODEL_POINT}
                prov = _without(p.get("provenance") or {})
                if prov not in sources:
                    sources.append(prov)
                item["source"] = sources.index(prov)
                formula = (p.get("conversion") or {}).get("formula")
                if formula:
                    if formula not in formulas:
                        formulas.append(formula)
                    item["formula"] = formulas.index(formula)
                reasons = [n.get("code") for n in p.get("notes") or []]
                if reasons:
                    item["reasons"] = reasons
                if p.get("upper_limit"):
                    item["upper_limit"] = True  # limite superiore: mai una misura (D43-9)
                points.append(item)
            details["points"] = points
            section["values"] = []
            section["point_sources"], section["point_formulas"] = sources, formulas
        if name == "planets":
            planets = details.get("planets") or []
            names = {str(pl.get("pl_name")) for pl in planets}
            section["values"] = [v for v in section.get("values") or []
                                 if not any(v.get("quantity") == f"{n} {k}" for n in names for k in _MODEL_PLANET_TEXT)]
            details["planets"] = [{k: pl.get(k) for k in ("pl_name", "discoverymethod", "disc_year", "pl_bmassprov")}
                                  for pl in planets]
        if name == "images":
            details["thumbnails"] = [{**{k: t.get(k) for k in _MODEL_THUMB},
                                      "credits": {"obs_copyright": (t.get("credits") or {}).get("obs_copyright")}}
                                     for t in details.get("thumbnails") or []]
        for key in _MODEL_DROP_DETAILS.get(name, ()):
            details.pop(key, None)
        sources: list[dict] = []
        formulas: list[str] = []
        references: list[str] = []
        for v in section.get("values") or []:
            prov = _without(v.pop("provenance", None) or {})
            if prov not in sources:
                sources.append(prov)
            v["source"] = sources.index(prov)
            if v.get("method") == "read":  # metodo di default della sezione, scritto una volta (method_default)
                del v["method"]
            unit = v["value"].get("unit") if isinstance(v.get("value"), Mapping) else None
            for key in ("error", "error_upper", "error_lower"):  # errori nell'unità del valore: solo il numero
                if isinstance(v.get(key), Mapping) and v[key].get("unit") == unit:
                    v[key] = v[key].get("value")
            if isinstance(v.get("interval"), list) and all(isinstance(x, Mapping) and x.get("unit") == unit
                                                           for x in v["interval"]):
                v["interval"] = [x.get("value") for x in v["interval"]]
            if v.get("reference"):  # riferimenti scritti una volta per sezione (references), come le fonti
                if v["reference"] not in references:
                    references.append(v["reference"])
                v["reference"] = references.index(v["reference"])
            if v.get("formula"):
                if v["formula"] not in formulas:
                    formulas.append(v["formula"])
                v["formula"] = formulas.index(v["formula"])
        if sources:
            section["sources"] = sources
            section["method_default"] = "read"
            section["errors_unit"] = "errors and intervals without a unit are in the unit of their value"
        if formulas:
            section["formulas"] = formulas
        if references:
            section["references"] = references
    values = _without(values)
    _trim(values)
    return {"values": values, "provenance": []}


def _exec_object_profile(ctx, p: Mapping):
    from astrotwo.core.commands import (
        Outcome,
        ProgressReport,
        ResultMessage,
        catalog_positions,
        quantity_json,
        sky_from_json,
    )

    def q(value: Mapping) -> u.Quantity:
        return float(value["value"]) * u.Unit(value["unit"])

    targets = [k for k in ("name", "position", "layer") if p.get(k) is not None]
    if p.get("row") is not None and p.get("layer") is None:
        raise ObjectProfileError("PROFILE_TARGET_INVALID", "row senza layer: serve la riga di un livello catalogo",
                                 params={"reason": "row_without_layer"})
    if len(targets) > 1:
        raise ObjectProfileError("PROFILE_TARGET_INVALID", "un solo bersaglio: un nome, una posizione o una riga",
                                 params={"reason": "several"})
    if not targets and p.get("simbad_id") is None:
        raise ObjectProfileError("PROFILE_TARGET_INVALID", "nessun bersaglio: serve un nome o una posizione",
                                 params={"reason": "none"})
    position, origin = None, None
    if p.get("position") is not None:
        position = sky_from_json(p["position"])
    elif p.get("layer") is not None:
        layer = ctx.state.layer(p["layer"])
        row = p.get("row")
        if row is None or not 0 <= int(row) < len(layer.data.table):
            raise ObjectProfileError("PROFILE_TARGET_INVALID", f"riga {row!r} fuori dal livello {layer.id}",
                                     params={"reason": "row_out_of_range", "layer": layer.id,
                                             "row": -1 if row is None else int(row)})
        coords, valid = catalog_positions(layer.data, rows=[int(row)])
        if coords is None or not valid.any():
            raise ObjectProfileError("PROFILE_TARGET_INVALID", f"riga {row} del livello {layer.id} senza posizione "
                                     "leggibile", params={"reason": "row_without_position", "layer": layer.id,
                                                          "row": int(row)})
        position = SkyFrame(coords.coord[0], epoch=coords.epoch)
        origin = f"riga {int(row)} del livello {layer.id}"
    target = ProfileTarget(name=p.get("name"), position=position, simbad_id=p.get("simbad_id"), origin=origin)
    total = len(p["sections"])
    arrived: list[str] = []

    def on_section(section: ProfileSection) -> None:  # avanzamento «passo k di n», una sezione per passo (§3.12)
        arrived.append(section.name)
        if ctx.progress is not None:  # con la sezione arrivata per la finestra Profili (43 §3.5)
            ctx.progress(ProgressReport(len(arrived), total, f"object_profile/{section.name}",
                                        detail={"event": "section", "section": section.as_dict()}))

    def on_resolved(resolved: ResolvedTarget) -> None:
        if ctx.progress is not None:
            ctx.progress(ProgressReport(0, total, "object_profile/resolved", detail={
                "event": "resolved", "resolved": resolved.as_dict(),
                "warnings": [_warning_json(w) for w in resolved.warnings], "sections": list(p["sections"])}))

    profile = build_profile(target, sections=tuple(p["sections"]), match_radius=q(p["match_radius"]),
                            crossmatch_radius=q(p["crossmatch_radius"]), on_section=on_section,
                            on_resolved=on_resolved,
                            cancel=lambda: ctx.cancel.cancelled, cache=ctx.cache, refresh=ctx.refresh,
                            surveys=tuple(p["surveys"]), thumbnail_fov=q(p["thumbnail_fov"]),
                            thumbnail_size=int(p["thumbnail_size"]))
    if profile is None:  # annullato prima della risoluzione del bersaglio: niente da conservare (discarded)
        return None
    values = profile.as_dict()
    warnings = [ResultMessage(w[0], w[1], dict(getattr(w, "params", None) or {})) for w in profile.warnings]
    for section in profile.sections:
        warnings.extend(ResultMessage(w[0], w[1], dict(getattr(w, "params", None) or {})) for w in section.warnings)
    seen, unique = set(), []
    for w in warnings:
        key = (w.code, w.text)
        if key not in seen:
            seen.add(key)
            unique.append(w)
    provenance = [{"origin": r.url, "retrieved_at": _iso(r.retrieved_at), "from_cache": r.from_cache,
                   "query": r.arguments.get("adql")} for r in profile.requests]
    fingerprint = []
    import hashlib
    import json

    for section in profile.sections:
        data = profile_content(section.as_dict())
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
        reqs = section.requests
        fingerprint.append({"sha256": digest, "origin": f"object.profile/{section.name}",
                            "retrieved_at": _iso(max((r.retrieved_at for r in reqs), default=None)),
                            "from_cache": all(r.from_cache for r in reqs) if reqs else None,
                            "rows": len(section.values)})
    resolved = {}
    if profile.resolved.simbad is not None:
        resolved["simbad_id"] = profile.resolved.simbad.main_id
    values["match_radius"] = quantity_json(q(p["match_radius"]))
    # Annullato dopo la risoluzione: le sezioni arrivate restano nel risultato (COMMAND_CANCELLED partial, 05 §3.2)
    return Outcome(values=values, warnings=unique, provenance=provenance, network_fingerprint=fingerprint,
                   resolved=resolved, cancelled=profile.cancelled or ctx.cancel.cancelled)


def command_specs() -> list:
    """Definizioni dei comandi del 25 da aggiungere al registro con ``register`` (05 §3.2, comandi dei livelli 2–4)."""
    from astrotwo.core.commands import P, CommandSpec

    from astrotwo.analysis.profile_export import EXPORT_FORMATS

    angle = {"physical_type": "angle"}
    commands = P("commands", "list", "Numbers (#n) of the object.profile commands of the profile: the first is the base, "
                 "the next ones replace the sections they contain.",
                 "Numeri (#n) dei comandi object.profile del profilo: il primo è la base, i successivi sostituiscono "
                 "le sezioni che contengono.", item=P("command", "integer", "Command number.", "Numero del comando.",
                                                      minimum=1))
    return [
        CommandSpec(
            "object.profile", 1, "Build the profile of an object: identity (SIMBAD), HiPS thumbnails, Gaia DR3 "
            "astrometry and distance with a declared method, photometry and SED with official zero points, known "
            "planets (NASA Exoplanet Archive); every value with its source.",
            "Costruisce il profilo di un oggetto: identità (SIMBAD), miniature HiPS, astrometria Gaia DR3 e distanza "
            "con metodo dichiarato, fotometria e SED con punti zero ufficiali, pianeti noti (NASA Exoplanet "
            "Archive); ogni valore con la sua fonte.",
            ("25 resolve_target", "25 build_profile", "14 simbad_object", "14 tap_query", "14 vizier_photometry",
             "20 build_sed", "10 resolve_name", "10 propagate_position", "12 add_hips", "12 hips_thumbnail"), (
                P("name", "string", "Object name or identifier (one target only).",
                  "Nome o identificativo dell'oggetto (un solo bersaglio).", default=None),
                P("position", "sky_position", "Sky position with frame and epoch (one target only).",
                  "Posizione con sistema ed epoca (un solo bersaglio).", default=None),
                P("layer", "layer_ref", "Catalog layer of the row (with row).", "Livello catalogo della riga (con row).",
                  default=None, layer_kinds=("catalog",)),
                P("row", "integer", "Row of the catalog layer (index from 0).",
                  "Riga del livello catalogo (indice da 0).", default=None, minimum=0),
                P("simbad_id", "string", "SIMBAD identifier to start from (written after the resolution).",
                  "Identificativo SIMBAD da cui partire (scritto dopo la risoluzione).", default=None),
                P("sections", "list", "Sections of the profile.", "Sezioni del profilo.", default=list(SECTIONS),
                  item=P("section", "enum", "Section.", "Sezione.", choices=SECTIONS)),
                P("match_radius", "quantity", "Radius for SIMBAD candidates from coordinates.",
                  "Raggio dei candidati SIMBAD da coordinate.",
                  default={"value": float(DEFAULT_MATCH_RADIUS.value), "unit": "arcsec"}, minimum=0.0,
                  exclusive_minimum=True, maximum=3600.0, range_unit="arcsec", **angle),
                P("crossmatch_radius", "quantity", "Radius of the positional cross-matches after propagation.",
                  "Raggio degli incroci per posizione dopo la propagazione.",
                  default={"value": float(DEFAULT_CROSSMATCH_RADIUS.value), "unit": "arcsec"}, minimum=0.0,
                  exclusive_minimum=True, maximum=60.0, range_unit="arcsec", **angle),
                P("surveys", "list", "HiPS surveys of the thumbnails (identifiers).",
                  "Survey HiPS delle miniature (identificativi).", default=list(IMAGE_SURVEYS),
                  item=P("survey", "string", "HiPS identifier.", "Identificativo HiPS.")),
                P("thumbnail_fov", "quantity", "Field of view of the thumbnails (side).",
                  "Campo delle miniature (lato).",
                  default={"value": float(DEFAULT_THUMBNAIL_FOV.value), "unit": "arcmin"}, minimum=0.0,
                  exclusive_minimum=True, maximum=600.0, range_unit="arcmin", **angle),
                P("thumbnail_size", "integer", "Side of the thumbnails in pixels.", "Lato delle miniature in pixel.",
                  default=DEFAULT_THUMBNAIL_SIZE, minimum=16, maximum=2048)),
            "session", _exec_object_profile, network=True, long=True, read_only=True, confirm=True),
        # Sprint C6 (25 §3.15): file e SAMP dai risultati registrati; eseguiti dall'interfaccia, che ha la cronologia
        CommandSpec(
            "object.export", 1, "Write the profile of an object to a file (ECSV of the values with provenance, PDF "
            "sheet, PNG of the SED, VOTable of the SED points) from the recorded results of object.profile commands.",
            "Scrive il profilo di un oggetto in un file (ECSV dei valori con provenienza, scheda PDF, PNG della SED, "
            "VOTable dei punti SED) dai risultati registrati dei comandi object.profile.",
            ("25 merge_profile_results", "25 export_profile", "14 export_table", "20 sed_rows_png"), (
                commands,
                P("format", "enum", "File format.", "Formato del file.", choices=EXPORT_FORMATS),
                P("path", "string", "Absolute path of the file to write.", "Percorso assoluto del file da scrivere."),
                P("language", "enum", "Language of the PDF headings.", "Lingua delle intestazioni del PDF.",
                  default="en", choices=("en", "it"))),
            "application", bound_by="43"),
        CommandSpec(
            "object.send_sed", 1, "Send the SED points of a profile to SAMP applications (table.load.votable).",
            "Manda i punti della SED di un profilo ai programmi SAMP (table.load.votable).",
            ("25 merge_profile_results", "25 sed_catalog_table", "14 SampHub.send_table"), (
                commands,
                P("recipient", "string", "Public id of one SAMP client (null: all subscribed clients).",
                  "Identificativo pubblico di un client SAMP (null: tutti i client iscritti).", default=None)),
            "application", bound_by="40"),
    ]
