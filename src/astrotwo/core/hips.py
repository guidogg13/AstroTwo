"""Servizi HiPS all-sky: metadati, tile, collezioni, cubi, cataloghi progressivi, generazione.

Specifica: ``mdfiles/12-core-hips.md`` (stato ``approvato``).

Il modulo si scrive in 5 parti (decisione del proprietario del 2026-10-12):
P1 metadati e ``add_hips`` (C3); P2 tile (``tiles_for_fov``, ``fetch_tile``, valore del pixel H27);
P3 elenco delle collezioni (``CollectionIndex``, ``HiPSList``, ``set_survey``, ``survey_coverage``);
P4 cubi (H24) e cataloghi progressivi (H12); P5 ``build_hips`` (H9).

Riferimento: standard IVOA HiPS 1.0 (REC 2017-05-19). Rete e cache: la rete del 14 e la cache comune
del 04; HEALPix con ``astropy-healpix`` (``healpy`` escluso); MOC con il 16.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

import astropy.units as u

__all__ = [
    "CELESTIAL_FRAMES",
    "HIPS_STANDARD_VERSION",
    "MANDATORY_PROPERTIES",
    "HiPSError",
    "HiPSList",
    "HiPSService",
    "add_hips",
    "parse_properties",
    "read_service",
]

#: Valore di ``hips_version`` dello standard HiPS 1.0 (§4.4.1: "1.4" corrisponde al documento).
HIPS_STANDARD_VERSION = "1.4"
#: Le 9 chiavi obbligatorie del file ``properties`` (standard HiPS 1.0 §4.4.1).
MANDATORY_PROPERTIES: tuple[str, ...] = (
    "creator_did", "obs_title", "dataproduct_type", "hips_version", "hips_release_date", "hips_status",
    "hips_tile_format", "hips_order", "hips_frame",
)
#: Valori di ``hips_frame`` celesti dello standard 1.0 → frame di ``astropy.coordinates`` (``ecliptic``: frame
#: non precisato dallo standard, nessuna conversione finché non è deciso, D12-7).
CELESTIAL_FRAMES: dict[str, str | None] = {"equatorial": "icrs", "galactic": "galactic", "ecliptic": None}
_PRODUCT_TYPES = ("image", "catalog", "cube")
_IMAGE_FORMATS = ("fits", "jpeg", "png")
_DEFAULT_TILE_WIDTH = 512  # standard HiPS 1.0, hips_tile_width: "Default : 512"
_SPACE_MAX_ORDER = 29
_KEY = re.compile(r"^[^\s=]+$")
_CACHE_MODULE = "12"


class HiPSError(Exception):
    """Errore del modulo 12 con identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


# --------------------------------------------------------------------------
# P1 — File properties (standard HiPS 1.0 §4.4.1) e metadati del servizio (C3)
# --------------------------------------------------------------------------

def parse_properties(text: str, *, source: str = "properties") -> dict[str, tuple[str, ...]]:
    """Legge un file ``properties``: una proprietà per riga ``chiave = valore``; righe vuote e commenti (``#``)
    ignorati; chiavi ripetibili (tutti i valori, nell'ordine). Una riga diversa → ``HIPS_NOT_A_SERVICE``."""
    values: dict[str, list[str]] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not _KEY.match(key):
            raise HiPSError("HIPS_NOT_A_SERVICE", f"{source}: riga {number} non è nella forma 'chiave = valore' "
                            f"dello standard HiPS 1.0: {raw[:120]!r}", line=number)
        values.setdefault(key, []).append(value.strip())
    if not values:
        raise HiPSError("HIPS_NOT_A_SERVICE", f"{source}: nessuna proprietà HiPS")
    return {key: tuple(v) for key, v in values.items()}


@dataclass(frozen=True)
class HiPSService:
    """Metadati di un servizio HiPS letti dal suo file ``properties`` (§6), con provenienza."""

    hips_id: str  # creator_did senza "ivo://"
    base_url: str
    title: str
    dataproduct_type: str  # image, catalog, cube
    subtype: str | None  # color, live
    version: str
    release_date: datetime
    status: tuple[str, ...]
    tile_formats: tuple[str, ...]  # il primo è quello suggerito dal servizio
    order: int  # ordine più profondo
    frame: str  # hips_frame come scritto
    tile_width: int | None  # None per i cataloghi
    body: str | None  # D19-3: "celestial" dal sistema, corpo del servizio per i planetari, None se ignoto
    cube_depth: int | None
    regime: str | None
    em_range: u.Quantity | None  # (min, max) in metri
    pixel_scale: u.Quantity | None  # hips_pixel_scale in gradi
    description: str | None
    properties: dict[str, tuple[str, ...]]
    origin: str  # URL del file properties
    retrieved_at: datetime
    from_cache: bool = False
    request: object | None = None  # RequestRecord del 14
    warnings: tuple[tuple[str, str], ...] = field(default=())

    @property
    def properties_url(self) -> str:
        return self.base_url + "/properties"

    def describe(self) -> str:
        parts = [f"HiPS {self.hips_id} «{self.title}»", f"tipo {self.dataproduct_type}"
                 + (f"/{self.subtype}" if self.subtype else ""),
                 f"ordine massimo {self.order}", f"formati {' '.join(self.tile_formats)}",
                 f"frame {self.frame}", f"corpo {self.body if self.body is not None else 'non ricavabile'}"]
        if self.tile_width is not None:
            parts.append(f"tile da {self.tile_width} pixel")
        if self.cube_depth is not None:
            parts.append(f"cubo di {self.cube_depth} piani")
        if self.regime or self.em_range is not None:
            band = self.regime or ""
            if self.em_range is not None:
                band += f" {self.em_range[0].value:g}–{self.em_range[1].value:g} m"
            parts.append(f"banda {band.strip()}")
        parts.append(f"versione {self.version}, rilascio {self.release_date.strftime('%Y-%m-%dT%H:%MZ')}")
        state = "copia in cache" if self.from_cache else "letto"
        parts.append(f"{state} da {self.origin} il {self.retrieved_at.isoformat()}")
        return "; ".join(parts)


def _invalid(source: str, field_name: str, reason: str) -> HiPSError:
    return HiPSError("HIPS_METADATA_INVALID", f"{source}: {field_name} {reason}; nessuna voce aggiunta",
                     field=field_name)


def _first(props: dict[str, tuple[str, ...]], key: str) -> str | None:
    values = props.get(key)
    return values[0] if values and values[0] != "" else None


def _int(props, key: str, source: str, *, low: int = 0, high: int | None = None) -> int | None:
    text = _first(props, key)
    if text is None:
        return None
    try:
        value = int(text)
    except ValueError:
        raise _invalid(source, key, f"{text!r} non è un intero") from None
    if value < low or (high is not None and value > high):
        raise _invalid(source, key, f"{value} fuori da [{low}, {high if high is not None else '∞'}]")
    return value


def _float(props, key: str, source: str) -> float | None:
    text = _first(props, key)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        raise _invalid(source, key, f"{text!r} non è un numero") from None


def _release_date(text: str, source: str) -> datetime:
    """ISO 8601 ``YYYY-mm-ddTHH:MMZ`` (standard §4.4.1); ammessi anche i secondi."""
    for pattern in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise _invalid(source, "hips_release_date", f"{text!r} non è nella forma ISO 8601 YYYY-mm-ddTHH:MMZ")


def _body(props, frame: str, source: str) -> tuple[str | None, list[tuple[str, str]]]:
    """Corpo (D19-3) dal sistema dichiarato; per i HiPS planetari da ``hips_body`` (WD HiPS 2.0)."""
    if frame in CELESTIAL_FRAMES:
        return "celestial", []
    body = _first(props, "hips_body")
    if body is None:
        return None, [("BODY_UNKNOWN", f"{source}: hips_frame {frame!r} non celeste e senza hips_body: corpo non "
                       "ricavabile, il dato si apre da solo")]
    if body != frame:
        return None, [("BODY_UNKNOWN", f"{source}: hips_frame {frame!r} e hips_body {body!r} diversi: corpo non "
                       "ricavabile, il dato si apre da solo")]
    return body, [("HIPS_BODY_DRAFT", f"{source}: corpo {body!r} da hips_body, definito nel Working Draft HiPS 2.0 "
                   "(2026-05-01), versione non ancora raccomandazione IVOA")]


def _service_from_properties(props: dict[str, tuple[str, ...]], base_url: str, origin: str, retrieved_at: datetime,
                             from_cache: bool) -> HiPSService:
    """Valida le proprietà secondo lo standard HiPS 1.0 e costruisce ``HiPSService``."""
    source = origin
    for key in MANDATORY_PROPERTIES:
        if _first(props, key) is None:
            raise _invalid(source, key, "mancante (chiave obbligatoria dello standard HiPS 1.0)")
    notes: list[tuple[str, str]] = []
    product = _first(props, "dataproduct_type")
    if product not in _PRODUCT_TYPES:
        raise _invalid(source, "dataproduct_type", f"{product!r} non previsto dallo standard HiPS 1.0 "
                       f"({', '.join(_PRODUCT_TYPES)})")
    formats = tuple(_first(props, "hips_tile_format").split())
    allowed = ("tsv",) if product == "catalog" else _IMAGE_FORMATS
    if not formats or any(f not in allowed for f in formats):
        raise _invalid(source, "hips_tile_format", f"{' '.join(formats)!r}: per {product} ammessi "
                       f"{', '.join(allowed)}")
    order = _int(props, "hips_order", source, high=_SPACE_MAX_ORDER)
    width = None
    if product != "catalog":
        width = _int(props, "hips_tile_width", source, low=1)
        if width is None:
            width = _DEFAULT_TILE_WIDTH
            notes.append(("HIPS_DEFAULT_TILE_WIDTH", f"{source}: hips_tile_width assente, {width} pixel (default "
                          "dello standard HiPS 1.0)"))
        if width & (width - 1):
            raise _invalid(source, "hips_tile_width", f"{width} non è una potenza di 2")
    depth = _int(props, "hips_cube_depth", source, low=1)
    if product == "cube" and depth is None:
        raise _invalid(source, "hips_cube_depth", "mancante (obbligatoria per i cubi, standard HiPS 1.0)")
    version = _first(props, "hips_version")
    if version != HIPS_STANDARD_VERSION:
        notes.append(("HIPS_VERSION_UNKNOWN", f"{source}: hips_version {version!r}; lo standard HiPS 1.0 scrive "
                      f"{HIPS_STANDARD_VERSION!r}: proprietà lette secondo HiPS 1.0"))
    frame = _first(props, "hips_frame")
    body, body_notes = _body(props, frame, source)
    notes += body_notes
    em_min, em_max = _float(props, "em_min", source), _float(props, "em_max", source)
    em_range = (u.Quantity([em_min, em_max], u.m) if em_min is not None and em_max is not None else None)
    scale = _float(props, "hips_pixel_scale", source)
    did = _first(props, "creator_did")
    hips_id = did[len("ivo://"):] if did.startswith("ivo://") else did
    return HiPSService(
        hips_id=hips_id, base_url=base_url, title=_first(props, "obs_title"), dataproduct_type=product,
        subtype=_first(props, "dataproduct_subtype"), version=version,
        release_date=_release_date(_first(props, "hips_release_date"), source),
        status=tuple(_first(props, "hips_status").split()), tile_formats=formats, order=order, frame=frame,
        tile_width=width, body=body, cube_depth=depth, regime=_first(props, "obs_regime"), em_range=em_range,
        pixel_scale=None if scale is None else scale * u.deg, description=_first(props, "obs_description"),
        properties=props, origin=origin, retrieved_at=retrieved_at, from_cache=from_cache,
        warnings=tuple(notes))


def _base_url(url: str) -> str:
    base = url.strip().rstrip("/")
    if base.endswith("/properties"):
        base = base[: -len("/properties")]
    if not base.startswith(("http://", "https://")):
        raise ValueError(f"URL non valido: {url!r} (serve http:// o https://)")
    return base


def _net(exc) -> HiPSError:
    return HiPSError(exc.code, exc.message, **exc.details)


def read_service(url: str, *, cache=None, refresh: bool = False, timeouts=None) -> HiPSService:
    """Legge e valida il file ``properties`` di un servizio HiPS dato l'URL di base (rete e cache del 14).

    Un URL che non risponde con un file ``properties`` → ``HIPS_NOT_A_SERVICE``; chiavi obbligatorie mancanti o
    valori non validi → ``HIPS_METADATA_INVALID``; rete assente senza copia in cache → ``NET_TIMEOUT``. Solo un
    servizio valido va in cache."""
    from astrotwo.core import vo_protocols as vo
    from astrotwo.core.cache import NETWORK_TIMEOUTS

    timeouts = NETWORK_TIMEOUTS if timeouts is None else timeouts
    base = _base_url(url)
    target = base + "/properties"
    try:
        response = vo._http("hips", target, cache=cache, refresh=refresh, timeouts=timeouts)
    except vo.VoProtocolsError as exc:
        if exc.code == "SERVICE_ERROR":
            raise HiPSError("HIPS_NOT_A_SERVICE", f"{target}: {exc.message}; non è un servizio HiPS",
                            url=target) from exc
        raise _net(exc) from exc
    try:
        text = response.payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HiPSError("HIPS_NOT_A_SERVICE", f"{target}: risposta non UTF-8, non è un file properties HiPS "
                        f"({exc})", url=target) from exc
    props = parse_properties(text, source=target)
    if not any(key in props for key in MANDATORY_PROPERTIES):
        raise HiPSError("HIPS_NOT_A_SERVICE", f"{target}: nessuna delle chiavi obbligatorie dello standard HiPS 1.0; "
                        "non è un servizio HiPS", url=target)
    service = _service_from_properties(props, base, target, response.retrieved_at, response.from_cache)
    notes = response.notes + vo._store(response, "hips", cache)
    record = vo._record("hips", "read_service", {"url": url}, response, None)
    return _replace(service, request=record, warnings=tuple(notes) + service.warnings)


def _replace(service: HiPSService, **changes) -> HiPSService:
    from dataclasses import replace

    return replace(service, **changes)


def _resolve_id(hips_id: str, *, cache, refresh: bool, timeouts) -> tuple[str, tuple]:
    """URL del servizio di un identificativo HiPS dal MocServer (rete del 14)."""
    import json

    from astrotwo.core import vo_protocols as vo

    params = {"ID": hips_id, "get": "record", "fmt": "json", "fields": "ID,hips_service_url,dataproduct_type"}
    try:
        response = vo._http("mocserver", vo.MOCSERVER_URL, params, cache=cache, refresh=refresh, timeouts=timeouts)
    except vo.VoProtocolsError as exc:
        if exc.code == "NET_TIMEOUT":
            raise HiPSError("MOCSERVER_UNAVAILABLE", f"MocServer non raggiungibile per risolvere {hips_id!r}: "
                            f"{exc.message}") from exc
        raise _net(exc) from exc
    try:
        records = json.loads(response.payload.decode("utf-8"))
        if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
            raise ValueError("attesa una lista di record")
    except (UnicodeDecodeError, ValueError) as exc:
        raise HiPSError("SERVICE_ERROR", f"{vo.MOCSERVER_URL}: risposta non leggibile ({exc})") from exc
    match = [r for r in records if r.get("ID") == hips_id]
    if not match:
        raise HiPSError("HIPS_UNKNOWN", f"identificativo {hips_id!r} sconosciuto al MocServer", hips_id=hips_id)
    url = match[0].get("hips_service_url")
    if isinstance(url, list):  # il MocServer può dare più valori
        url = url[0] if url else None
    if not isinstance(url, str) or not url:
        raise HiPSError("HIPS_NOT_A_SERVICE", f"{hips_id!r}: la collezione non ha un servizio HiPS "
                        "(hips_service_url assente nel MocServer)", hips_id=hips_id)
    notes = response.notes + vo._store(response, "mocserver", cache)
    return url, notes


def add_hips(hips_id_or_url: str, *, cache=None, refresh: bool = False, timeouts=None) -> HiPSService:
    """Legge e valida un servizio HiPS da identificativo (es. ``CDS/P/DSS2/color``, risolto con il MocServer) o da
    URL di base (C3). In caso di errore non restituisce nulla (codici del §10). Per registrarlo in un elenco:
    ``HiPSList.add_hips``."""
    from astrotwo.core.cache import NETWORK_TIMEOUTS

    timeouts = NETWORK_TIMEOUTS if timeouts is None else timeouts
    if not isinstance(hips_id_or_url, str) or not hips_id_or_url.strip():
        raise ValueError("serve un identificativo HiPS o un URL di base")
    text = hips_id_or_url.strip()
    if text.lower().startswith(("http://", "https://")):
        return read_service(text, cache=cache, refresh=refresh, timeouts=timeouts)
    hips_id = text[len("ivo://"):] if text.startswith("ivo://") else text
    url, notes = _resolve_id(hips_id, cache=cache, refresh=refresh, timeouts=timeouts)
    service = read_service(url, cache=cache, refresh=refresh, timeouts=timeouts)
    extra = list(notes)
    if service.hips_id != hips_id:
        extra.append(("HIPS_ID_MISMATCH", f"identificativo richiesto {hips_id!r}, creator_did del servizio "
                      f"{service.hips_id!r}: vale quello del servizio"))
    return _replace(service, warnings=service.warnings + tuple(extra))


class HiPSList:
    """Elenco dei survey HiPS attivabili, con provenienza di ogni voce (C1, C3)."""

    def __init__(self, services=()) -> None:
        self._services: dict[str, HiPSService] = {}
        for service in services:
            self._services[service.hips_id] = service

    @property
    def services(self) -> tuple[HiPSService, ...]:
        return tuple(self._services.values())

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self._services)

    def __len__(self) -> int:
        return len(self._services)

    def __contains__(self, hips_id: object) -> bool:
        return hips_id in self._services

    def get(self, hips_id: str) -> HiPSService:
        if hips_id not in self._services:
            known = ", ".join(sorted(self._services)) or "nessuno"
            raise HiPSError("HIPS_UNKNOWN", f"survey {hips_id!r} non in elenco; noti: {known}", hips_id=hips_id)
        return self._services[hips_id]

    def add_hips(self, hips_id_or_url: str, *, cache=None, refresh: bool = False, timeouts=None) -> HiPSService:
        """Aggiunge un servizio HiPS (C3) solo se i metadati sono validi; in caso di errore l'elenco non cambia.
        Una voce già presente si sostituisce solo con ``refresh=True``."""
        service = add_hips(hips_id_or_url, cache=cache, refresh=refresh, timeouts=timeouts)
        if service.hips_id in self._services and not refresh:
            existing = self._services[service.hips_id]
            return _replace(existing, warnings=existing.warnings + (
                ("HIPS_ALREADY_LISTED", f"{service.hips_id} già in elenco (letto da {existing.origin} il "
                 f"{existing.retrieved_at.isoformat()}); refresh=True per rileggerlo"),))
        self._services[service.hips_id] = service
        return service
