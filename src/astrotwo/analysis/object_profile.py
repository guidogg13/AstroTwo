# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Profilo di un oggetto (livello 2): bersaglio, identificativi, identità, astrometria, distanza; ``object.profile``.

Specifica: ``mdfiles/25-analisi-profilo-oggetto.md`` (stato ``approvato``), in particolare §3.10 (sprint C2).

Nessun numero nasce qui fuori da codice deterministico (regola d'oro n. 1): i valori sono **letti** dai servizi
(con unità, errore e riferimento) oppure **calcolati** da ``distance_from`` (distanza da parallasse con
``astropy.units.parallax``), con il metodo scritto nel valore. Ogni valore porta la sua provenienza (servizio, server
che ha risposto, tabella, interrogazione ADQL, identificativo usato, tipo di incrocio, data, cache).

Le sezioni sono indipendenti (regola c): l'errore di un servizio resta nella sua sezione. In C2 le sezioni girano una
dopo l'altra (parallelismo nello sprint C4). Il comando ``object.profile`` è definito qui (comando del livello 2,
05 §3.2): il 05 non importa questo modulo, lo riceve con ``register`` da chi costruisce il registro (``40``).
"""

from __future__ import annotations

import time
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.time import Time

from astrotwo.core.cache import NETWORK_TIMEOUTS, NetworkTimeouts, SharedCache
from astrotwo.core.coordinates_wcs import ModuleWarning, SkyFrame, propagate_position, resolve_name
from astrotwo.core.vo_protocols import RequestRecord, SimbadRecord, VoProtocolsError, simbad_object, tap_query

__all__ = [
    "BAILER_JONES_REFERENCE",
    "CATALOGS",
    "DEFAULT_CROSSMATCH_RADIUS",
    "DEFAULT_MATCH_RADIUS",
    "GAIA_DR3_EPOCH",
    "PARALLAX_SNR_MIN",
    "PM_SEARCH_MAX",
    "SECTIONS",
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
    "distance_from",
    "profile_astrometry",
    "profile_content",
    "profile_identity",
    "resolve_target",
]

#: Sezioni scritte nello sprint C2 (25 §3.10); immagini, fotometria e pianeti arrivano negli sprint C3–C4.
SECTIONS: tuple[str, ...] = ("identity", "astrometry")
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

_SIMBAD_TAP = "cds-simbad-tap"
_GAIA_TAP = "esa-gaia-tap"
_EXOPLANET_TAP = "nasa-exoplanet-tap"
_GAIA_SOURCE = "gaiadr3.gaia_source"
_BJ_TABLE = "external.gaiaedr3_distance"
_OFFICIAL = {"2mass": "gaiadr3.tmass_psc_xsc_best_neighbour", "allwise": "gaiadr3.allwise_best_neighbour"}
_SIMBAD_PREFIX = {"gaia_dr3": "Gaia DR3 ", "2mass": "2MASS J", "allwise": "WISEA "}
_NAME_PREFIXES = ("NAME ", "V* ", "** ", "* ")
_ZERO_POINT_NOTE = "nessuna correzione dello zero point di parallasse (D25-10)"
_RUWE_NOTE = "RUWE senza soglia: nessuna soglia da fonte ufficiale Gaia verificata (D25-11)"


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
                "reference": self.reference, "note": self.note, "provenance": self.provenance.as_dict()}


def _provenance(request: RequestRecord, service: str, table: str | None, query: str | None,
                identifier: str | None, match: str | None) -> Provenance:
    return Provenance(service=service, server=request.url, table=table, query=query, identifier=identifier,
                      match=match, retrieved_at=request.retrieved_at, from_cache=request.from_cache)


def _service_name(url: str) -> str:
    host = urllib.parse.urlparse(url).hostname or url
    if "simbad" in host:
        return "SIMBAD (mirror di Harvard)" if "harvard" in host else "SIMBAD (CDS)"
    if "gea.esac.esa.int" in host:
        return "Archivio Gaia (ESA)"
    if "exoplanetarchive" in host:
        return "NASA Exoplanet Archive"
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


def _simbad_candidates(position: SkyFrame, radius: u.Quantity, *, cache, refresh, timeouts):
    """Candidati SIMBAD per coordinate (25 §3.10): cerchio allargato da ``PM_SEARCH_MAX``, propagazione all'epoca."""
    icrs = position if position.frame_name == "icrs" else position.to("icrs")
    ra0, dec0 = float(icrs.lon.to_value(u.deg)), float(icrs.lat.to_value(u.deg))
    epoch = position.epoch
    dt = abs(_years_between(epoch, _SIMBAD_EPOCH)) if epoch is not None else 0.0
    search = (radius + (PM_SEARCH_MAX * dt * u.yr)).to(u.deg)
    adql = ("SELECT main_id, otype, ra, dec, pmra, pmdec, nbref FROM basic WHERE CONTAINS(POINT('ICRS', ra, dec), "
            f"CIRCLE('ICRS', {ra0!r}, {dec0!r}, {float(search.value)!r})) = 1")
    result = tap_query(_SIMBAD_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts)
    target = SkyCoord(ra0 * u.deg, dec0 * u.deg, frame="icrs")
    found = []
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
            found.append({"main_id": _value(row, "main_id"), "otype": _value(row, "otype"),
                          "separation": _qj(sep, "arcsec"), "nbref": _value(row, "nbref"),
                          "propagated": propagated})
    found.sort(key=lambda c: (c["separation"]["value"], c["main_id"] or ""))
    return tuple(found), result.request, tuple(result.warnings)


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
            record = simbad_object(identifier, cache=cache, refresh=refresh, timeouts=timeouts)
        except VoProtocolsError as exc:
            if exc.code in ("NAME_NOT_FOUND", "ADQL_INVALID"):
                raise
            resolved = resolve_name(identifier, cache=cache, refresh=refresh)
            note = ModuleWarning("PROFILE_NO_IDENTIFIERS", f"SIMBAD non raggiungibile ({exc.code}): '{identifier}' "
                                 f"risolto da {resolved.source}, profilo per posizione senza identificativi",
                                 {"reason": "simbad_unreachable", "name": identifier, "service": resolved.source,
                                  "cause": _message(exc)})
            return ResolvedTarget(target, None, resolved.coords, f"{resolved.source} ({resolved.origin})",
                                  "name_resolver", simbad_error=_message(exc),
                                  warnings=(note,) + tuple(resolved.warnings))
        notes = _network_notes(record.warnings)
        if target.name is not None and target.simbad_id is not None and record.main_id != target.simbad_id:
            notes += (ModuleWarning("PROFILE_TARGET_CHANGED", f"'{target.name}': SIMBAD indica oggi "
                                    f"{record.main_id}, il comando registrato {target.simbad_id}",
                                    {"name": target.name, "recorded": target.simbad_id, "found": record.main_id}),)
        return ResolvedTarget(target, record, record.coords, f"{record.source}, ICRS J2000 (coo_bibcode "
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
        return ResolvedTarget(target, None, position, "coordinate scritte", "position", simbad_error=_message(exc),
                              warnings=notes + (note,))
    if len(candidates) > 1:
        return TargetCandidates(target, match_radius, candidates, (request,))
    if not candidates:
        return ResolvedTarget(target, None, position, "coordinate scritte (nessun oggetto SIMBAD entro "
                              f"{float(match_radius.to_value(u.arcsec)):g} arcsec)", "position",
                              warnings=notes + _network_notes(cand_notes), requests=(request,))
    chosen = candidates[0]
    record = simbad_object(chosen["main_id"], cache=cache, refresh=refresh, timeouts=timeouts)
    sep = chosen["separation"]["value"] * u.arcsec
    note = ModuleWarning("PROFILE_POSITIONAL_MATCH", f"bersaglio per posizione: {record.main_id} a "
                         f"{float(sep.value)!r} arcsec (raggio {float(match_radius.to_value(u.arcsec))!r} arcsec)",
                         {"reason": "simbad_candidate", "main_id": record.main_id, "separation": _qj(sep),
                          "radius": _qj(match_radius, "arcsec"),
                          "epoch": "—" if position.epoch is None else str(position.epoch.jyear_str)})
    return ResolvedTarget(target, record, record.coords, f"{record.source}, ICRS J2000", "simbad_candidate",
                          separation=sep, warnings=notes + _network_notes(cand_notes) + (note,)
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
    result = tap_query(_GAIA_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts)
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
    result = tap_query(_GAIA_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts)
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
                                   note="confermato dall'incrocio ufficiale di Gaia", **common)
    if simbad is not None:
        return CrossIdentification(catalog, simbad, "simbad_identifier", warnings=notes, **common)
    if official is not None:
        prefix = "2MASS J" if catalog == "2mass" else "WISEA "
        return CrossIdentification(catalog, prefix + str(official["designation"]).strip(), "official_crossmatch",
                                   separation=official["angular_distance"], warnings=notes, **common)
    return CrossIdentification(catalog, None, None, warnings=notes,
                               note="nessun identificativo da SIMBAD né dall'incrocio ufficiale; il passo per "
                                    "posizione arriva con la fotometria (sprint C3)", **common)


def _exoplanet_host(resolved: ResolvedTarget, gaia: CrossIdentification, *, cache, refresh, timeouts):
    requests, queries, notes = [], [], []

    def ask(adql: str):
        result = tap_query(_EXOPLANET_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts)
        requests.append(result.request)
        queries.append(adql)
        notes.extend(w for w in result.warnings if w[0] == "FROM_CACHE")
        return result.table.table

    if gaia.source_id is not None:
        rows = ask("SELECT DISTINCT hostname, gaia_dr3_id FROM pscomppars WHERE gaia_dr3_id = "
                   f"{_adql_text(gaia.identifier)}")
        if len(rows):
            return CrossIdentification("exoplanet", _value(rows[0], "hostname"), "simbad_identifier",
                                       official={"gaia_dr3_id": gaia.identifier}, warnings=tuple(notes),
                                       requests=tuple(requests), queries=tuple(queries))
    names = _host_names(resolved)
    if names:
        rows = ask("SELECT DISTINCT hostname, gaia_dr3_id FROM pscomppars WHERE hostname IN ("
                   + ", ".join(_adql_text(n) for n in names) + ")")
        hosts = sorted({str(_value(r, "hostname")) for r in rows})
        if len(hosts) == 1:
            return CrossIdentification("exoplanet", hosts[0], "simbad_identifier",
                                       official={"hostname": hosts[0]}, warnings=tuple(notes),
                                       requests=tuple(requests), queries=tuple(queries))
        if len(hosts) > 1:
            return CrossIdentification("exoplanet", None, None, candidates=tuple({"hostname": h} for h in hosts),
                                       note="più ospiti dell'archivio corrispondono agli identificativi SIMBAD: "
                                            "nessuna scelta", warnings=tuple(notes), requests=tuple(requests),
                                       queries=tuple(queries))
    return CrossIdentification("exoplanet", None, None, note="nessun ospite nell'archivio", warnings=tuple(notes),
                               requests=tuple(requests), queries=tuple(queries))


# --------------------------------------------------------------------------
# Sezioni (25 §3.4, §3.10)
# --------------------------------------------------------------------------


@dataclass
class ProfileSection:
    """Una sezione: stato, valori, dettagli, avvisi, errori, server, tempo."""

    name: str
    status: str = "pending"  # pending, running, done, partial, error, not_applicable
    values: list[ProfileValue] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    requests: list[RequestRecord] = field(default_factory=list)
    elapsed: float | None = None

    def as_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "values": [v.as_dict() for v in self.values],
                "details": self.details, "warnings": [_warning_json(w) for w in self.warnings],
                "errors": list(self.errors), "servers": sorted({r.url for r in self.requests}),
                "elapsed": None if self.elapsed is None else {"value": self.elapsed, "unit": "s"}}


def _group(identifier: str) -> str:
    """Catalogo di un identificativo SIMBAD: prima parola; ``NAME`` = nomi propri; ``*``/``**``/``V*`` = stelle."""
    head = identifier.split()[0] if identifier.split() else identifier
    return {"*": "star", "**": "star", "V*": "star", "NAME": "NAME"}.get(head, head)


def _simbad_link(record: SimbadRecord) -> str:
    parsed = urllib.parse.urlparse(record.requests[0].url)
    return f"{parsed.scheme}://{parsed.netloc}/simbad/sim-id?Ident={urllib.parse.quote(record.main_id)}"


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
            section.details["note"] = "nessun oggetto SIMBAD per questa posizione"
        return section
    basic = record.basic
    req = record.requests[0]
    query = req.arguments.get("adql")

    def read(name: str, value, *, error=None, reference=None, note=None):
        section.values.append(ProfileValue(name, value, _provenance(req, record.source, "basic", query,
                                                                    record.identifier, "simbad_identifier"),
                                           error=error, reference=reference, note=note))

    read("main_id", record.main_id)
    read("otype", basic.get("otype"), note=record.otype_description)
    read("sp_type", basic.get("sp_type"), reference=basic.get("sp_bibcode"))
    read("nbref", basic.get("nbref"))
    read("ra", basic.get("ra"), reference=basic.get("coo_bibcode"), note="ICRS, epoca J2000")
    read("dec", basic.get("dec"), reference=basic.get("coo_bibcode"), note="ICRS, epoca J2000")
    for name in ("coo_err_maj", "coo_err_min", "coo_err_angle", "coo_qual"):
        read(name, basic.get(name), reference=basic.get("coo_bibcode"))
    groups: dict[str, list[str]] = {}
    for ident in record.identifiers:
        groups.setdefault(_group(ident), []).append(ident)
    ident_req = record.requests[1]
    section.details = {"identifiers": {k: groups[k] for k in sorted(groups)}, "identifier_count":
                       len(record.identifiers), "simbad_url": _simbad_link(record),
                       "identifiers_provenance": _provenance(ident_req, record.source, "ident",
                                                             ident_req.arguments.get("adql"), record.main_id,
                                                             "simbad_identifier").as_dict()}
    section.requests.extend(record.requests[:2])
    section.status = "done"
    return section


def _simbad_astrometry(section: ProfileSection, record: SimbadRecord) -> ProfileValue | None:
    """Parallasse, moto proprio e velocità radiale di SIMBAD con i loro bibcode; restituisce la parallasse."""
    basic = record.basic
    req = record.requests[0]
    prov = _provenance(req, record.source, "basic", req.arguments.get("adql"), record.main_id, "simbad_identifier")
    parallax = None
    if basic.get("plx_value") is not None:
        parallax = ProfileValue("parallax", basic["plx_value"], prov, error=basic.get("plx_err"),
                                reference=basic.get("plx_bibcode"), note="SIMBAD")
        section.values.append(parallax)
    for name in ("pmra", "pmdec"):
        if basic.get(name) is not None:
            section.values.append(ProfileValue(name, basic[name], prov, reference=basic.get("pm_bibcode"),
                                               note="SIMBAD; errore come ellisse (pm_err_maj, pm_err_min, "
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
        try:
            result = tap_query(_GAIA_TAP, adql, cache=cache, refresh=refresh, timeouts=timeouts)
        except VoProtocolsError as exc:
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
        if gaia_row is not None:
            bj_adql = ("SELECT source_id, r_med_geo, r_lo_geo, r_hi_geo, r_med_photogeo, r_lo_photogeo, r_hi_photogeo, "
                       f"flag FROM {_BJ_TABLE} WHERE source_id = {gaia.source_id}")
            try:
                bj_result = tap_query(_GAIA_TAP, bj_adql, cache=cache, refresh=refresh, timeouts=timeouts)
            except VoProtocolsError as exc:
                section.errors.append(_message(exc))
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
    epoch_note = None if epoch is None else f"epoca di riferimento {_plain_number(epoch)} (ref_epoch, TCB)"
    add = section.values.append
    add(ProfileValue("source_id", _value(row, "source_id"), prov))
    add(ProfileValue("ref_epoch", epoch, prov))
    add(ProfileValue("ra", _value(row, "ra"), prov, error=_value(row, "ra_error"), note=epoch_note))
    add(ProfileValue("dec", _value(row, "dec"), prov, error=_value(row, "dec_error"), note=epoch_note))
    solved = _value(row, "astrometric_params_solved")
    n_params = None if solved is None else _bits(solved)
    add(ProfileValue("astrometric_params_solved", solved, prov,
                     note=None if n_params is None else f"{n_params} parametri"))
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
                     "nullo per le soluzioni a 2 parametri (modello dei dati Gaia DR3)"))
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
                                    note=f"Bailer-Jones et al. (2021), mediana {'geometrica' if kind == 'geo' else 'fotogeometrica'}"
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
                         note=f"1/parallasse da {source}; parallasse/errore = {ratio!r} >= {PARALLAX_SNR_MIN!r}; "
                              f"{_ZERO_POINT_NOTE}")
    return (value,), ()


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
                "warnings": [_warning_json(w) for w in self.warnings]}


def build_profile(target: ProfileTarget, *, sections: Sequence[str] = SECTIONS,
                  match_radius: u.Quantity = DEFAULT_MATCH_RADIUS,
                  crossmatch_radius: u.Quantity = DEFAULT_CROSSMATCH_RADIUS,
                  on_section: Callable[[ProfileSection], None] | None = None,
                  cancel: Callable[[], bool] | None = None, cache: SharedCache | None = None,
                  refresh: bool = False, timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> ObjectProfile | None:
    """Esegue le sezioni richieste (in C2 una dopo l'altra); ``on_section`` a ogni sezione terminata.

    Più candidati → ``PROFILE_AMBIGUOUS_TARGET`` con l'elenco (nessuna scelta); annullato → ``None``."""
    unknown = [s for s in sections if s not in SECTIONS]
    if unknown or not sections:
        raise ValueError(f"sezioni {unknown or list(sections)} non in {SECTIONS}")
    for name, value in (("match_radius", match_radius), ("crossmatch_radius", crossmatch_radius)):
        if not isinstance(value, u.Quantity) or not value.unit.is_equivalent(u.deg) or not value.value > 0:
            raise ValueError(f"{name}: angolo positivo con unità")
    try:
        resolved = resolve_target(target, match_radius=match_radius, cache=cache, refresh=refresh, timeouts=timeouts)
        if isinstance(resolved, TargetCandidates):
            raise ObjectProfileError(
                "PROFILE_AMBIGUOUS_TARGET", f"{len(resolved.candidates)} oggetti SIMBAD entro "
                f"{float(match_radius.to_value(u.arcsec))!r} arcsec: scegliere l'oggetto ("
                + ", ".join(str(c["main_id"]) for c in resolved.candidates) + ")",
                params={"count": len(resolved.candidates), "radius": _qj(match_radius, "arcsec"),
                        "candidates": [dict(c) for c in resolved.candidates]})
        _check(cancel)
        done: list[ProfileSection] = []
        cross_ids: list[CrossIdentification] = []

        def finish(section: ProfileSection, started: float) -> None:
            section.elapsed = time.monotonic() - started
            done.append(section)
            if on_section is not None:
                on_section(section)

        if "identity" in sections:
            started = time.monotonic()
            section = profile_identity(resolved)
            if section.status == "done":
                for catalog in CATALOGS:
                    _check(cancel)
                    gaia = cross_ids[0] if cross_ids else None
                    try:
                        found = cross_identify(resolved, catalog, gaia=gaia, crossmatch_radius=crossmatch_radius,
                                               cache=cache, refresh=refresh, timeouts=timeouts)
                    except VoProtocolsError as exc:
                        found = CrossIdentification(catalog, None, None, note="incrocio non riuscito",
                                                    error=_message(exc))
                    cross_ids.append(found)
                    if found.error is not None:
                        section.errors.append({**found.error, "catalog": catalog})
                section.details["cross_identifications"] = [c.as_dict() for c in cross_ids]
                for c in cross_ids:
                    section.warnings.extend(w for w in c.warnings if w[0] == "PROFILE_IDENTIFIER_CONFLICT")
                    section.requests.extend(c.requests)
                if section.errors:
                    section.status = "partial"
            finish(section, started)
        if "astrometry" in sections:
            _check(cancel)
            started = time.monotonic()
            gaia = cross_ids[0] if cross_ids else None
            section = ProfileSection("astrometry")
            try:
                if gaia is None:
                    gaia = cross_identify(resolved, "gaia_dr3", crossmatch_radius=crossmatch_radius, cache=cache,
                                          refresh=refresh, timeouts=timeouts)
                    cross_ids.insert(0, gaia)
                section = profile_astrometry(resolved, gaia, cache=cache, refresh=refresh, timeouts=timeouts,
                                             cancel=cancel)
            except VoProtocolsError as exc:
                section.errors.append(_message(exc))
                if resolved.simbad is not None:
                    _simbad_astrometry(section, resolved.simbad)
                    section.requests.append(resolved.simbad.requests[0])
                    values, notes = distance_from(None, next((v for v in section.values if v.quantity == "parallax"),
                                                             None))
                    section.values.extend(values)
                    section.warnings.extend(notes)
                section.status = "partial" if section.values else "error"
            finish(section, started)
    except _Cancelled:
        return None
    options = {"sections": list(sections), "match_radius": _qj(match_radius, "arcsec"),
               "crossmatch_radius": _qj(crossmatch_radius, "arcsec")}
    order = {name: k for k, name in enumerate(SECTIONS)}
    return ObjectProfile(target, resolved, tuple(cross_ids), tuple(sorted(done, key=lambda s: order[s.name])),
                         tuple(resolved.warnings), options)


# --------------------------------------------------------------------------
# Comando object.profile (05 §7, comando del livello 2; 25 §3.10)
# --------------------------------------------------------------------------


_RUN_KEYS = ("retrieved_at", "from_cache", "elapsed")
_RUN_CODES = ("FROM_CACHE", "SERVICE_MIRROR_FALLBACK", "DATA_REFRESHED")


def profile_content(data):
    """Forma JSON del profilo senza ciò che cambia a ogni esecuzione (data, cache, tempi, avvisi di rete): il
    contenuto scientifico, per l'impronta di rete (D05-2) e per confrontare due esecuzioni."""
    if isinstance(data, Mapping):
        return {k: profile_content(v) for k, v in data.items() if k not in _RUN_KEYS}
    if isinstance(data, list):
        return [profile_content(v) for v in data
                if not (isinstance(v, Mapping) and v.get("code") in _RUN_CODES and "text" in v)]
    return data


def _exec_object_profile(ctx, p: Mapping):
    from astrotwo.core.commands import (
        Outcome,
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
    ctx.step("object_profile")
    profile = build_profile(target, sections=tuple(p["sections"]), match_radius=q(p["match_radius"]),
                            crossmatch_radius=q(p["crossmatch_radius"]), cancel=lambda: ctx.cancel.cancelled,
                            cache=ctx.cache, refresh=ctx.refresh)
    if profile is None:
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
    return Outcome(values=values, warnings=unique, provenance=provenance, network_fingerprint=fingerprint,
                   resolved=resolved)


def command_specs() -> list:
    """Definizioni dei comandi del 25 da aggiungere al registro con ``register`` (05 §3.2, comandi dei livelli 2–4)."""
    from astrotwo.core.commands import P, CommandSpec

    angle = {"physical_type": "angle"}
    return [
        CommandSpec(
            "object.profile", 1, "Build the profile of an object: identity (SIMBAD), Gaia DR3 astrometry and "
            "distance with a declared method; every value with its source.",
            "Costruisce il profilo di un oggetto: identità (SIMBAD), astrometria Gaia DR3 e distanza con metodo "
            "dichiarato; ogni valore con la sua fonte.",
            ("25 resolve_target", "25 build_profile", "14 simbad_object", "14 tap_query", "10 resolve_name",
             "10 propagate_position"), (
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
                  exclusive_minimum=True, maximum=60.0, range_unit="arcsec", **angle)),
            "session", _exec_object_profile, network=True, long=True, read_only=True, confirm=True, steps=1),
    ]
