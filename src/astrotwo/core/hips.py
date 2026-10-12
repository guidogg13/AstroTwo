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
    "DEFAULT_TILE_MEMORY_BYTES",
    "HIPS_STANDARD_VERSION",
    "MANDATORY_PROPERTIES",
    "HiPSError",
    "HiPSList",
    "HiPSService",
    "HiPSTile",
    "PixelValues",
    "TileMemory",
    "TileSelection",
    "add_hips",
    "fetch_tile",
    "order_for_resolution",
    "parse_properties",
    "pixel_values",
    "read_service",
    "service_coverage",
    "tile_path",
    "tile_pixel_values",
    "tiles_for_fov",
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


# --------------------------------------------------------------------------
# P2 — Tile: campo, scaricamento con cache e provenienza, copertura, valore del pixel (H27)
# --------------------------------------------------------------------------

#: Tile tenuti in memoria (A10 per gli HiPS, decisa il 2026-10-12): 512 MB = 512 × 10⁶ byte, configurabile.
DEFAULT_TILE_MEMORY_BYTES = 512_000_000
_EXTENSIONS = {"fits": "fits", "jpeg": "jpg", "png": "png", "tsv": "tsv"}


def _check_space_order(order: object, high: int = _SPACE_MAX_ORDER, what: str = "ordine HEALPix") -> int:
    if isinstance(order, bool) or not isinstance(order, int) or not 0 <= order <= high:
        raise HiPSError("HEALPIX_ORDER_INVALID", f"{what} {order!r}: serve un intero in [0, {high}]")
    return order


def _check_index(order: int, index: object) -> int:
    import numpy as np

    npix = 12 * 4 ** order
    if isinstance(index, bool) or not isinstance(index, (int, np.integer)) or not 0 <= int(index) < npix:
        raise HiPSError("HEALPIX_INDEX_INVALID", f"indice {index!r} all'ordine {order}: serve un intero in "
                        f"[0, {npix - 1}]")
    return int(index)


def tile_path(order: int, index: int, extension: str, *, plane: int | None = None) -> str:
    """Percorso di un tile secondo lo standard HiPS 1.0 §4.1: ``NorderK/DirD/NpixN.ext``, D = (N/10000)×10000;
    per i cubi il suffisso ``_n`` del piano (§4.2.3; il piano 0 è il tile senza suffisso)."""
    suffix = f"_{plane}" if plane else ""
    return f"Norder{order}/Dir{(index // 10000) * 10000}/Npix{index}{suffix}.{extension}"


def _astropy_frame(frame: str) -> str:
    """Frame di ``astropy`` di un ``hips_frame``; ``ecliptic`` (frame non precisato dallo standard, D12-7) e i frame
    planetari (modulo 19) → ``HIPS_FRAME_UNSUPPORTED``."""
    name = CELESTIAL_FRAMES.get(frame)
    if name is None:
        why = ("lo standard HiPS 1.0 non precisa quale eclittica (D12-7, da decidere)" if frame == "ecliptic"
               else "frame planetario: le posizioni planetarie arrivano con il modulo 19")
        raise HiPSError("HIPS_FRAME_UNSUPPORTED", f"hips_frame {frame!r}: {why}", frame=frame)
    return name


def _to_frame(coords, frame: str, what: str):
    """Coordinate (``SkyFrame``/``SkyCoord``) nel frame del HiPS con il modulo 10: (lon, lat) in gradi e nota."""
    import numpy as np
    from astropy.coordinates import SkyCoord

    from astrotwo.core.coordinates_wcs import CoordinatesWcsError, SkyFrame

    target = _astropy_frame(frame)
    if isinstance(coords, SkyCoord):
        coords = SkyFrame(coords)
    if not isinstance(coords, SkyFrame):
        raise TypeError(f"{what}: servono coordinate SkyFrame/SkyCoord con il sistema dichiarato (modulo 10)")
    try:
        converted = coords if coords.frame_name == target else coords.to(target)
    except CoordinatesWcsError as exc:
        raise HiPSError("REGION_INVALID", f"{what}: {exc.message}") from exc
    lon = np.atleast_1d(converted.lon.to_value(u.deg))
    lat = np.atleast_1d(converted.lat.to_value(u.deg))
    note = "" if coords.frame_name == target else f" (convertite da {coords.frame_name} in {target} con il modulo 10)"
    return lon, lat, note


def _tile_cells_at(moc, order: int):
    """Celle all'ordine ``order`` che toccano il MOC spaziale (``mocpy``), come insieme ordinato di indici."""
    import numpy as np

    native = int(moc.max_order)
    if native >= order:
        cells = np.asarray(moc.degrade_to_order(order).flatten(), dtype=np.int64)
    else:
        cells = np.asarray(moc.flatten(), dtype=np.int64)  # celle all'ordine del MOC
    return cells, native


def _in_coverage(coverage, order: int, indices):
    """Maschera dei tile (ordine, indici NESTED in ICRS) che toccano il MOC del servizio."""
    import numpy as np

    cells, native = _tile_cells_at(coverage.moc, order)
    indices = np.asarray(indices, dtype=np.int64)
    if native >= order:
        return np.isin(indices, cells)
    return np.isin(indices >> (2 * (order - native)), cells)


@dataclass(frozen=True)
class TileSelection:
    """Tile che servono per un campo circolare (decisione 4 del 2026-10-12), con la descrizione del calcolo."""

    order: int
    indices: tuple[int, ...]
    frame: str
    outside_coverage: int
    description: str
    warnings: tuple[tuple[str, str], ...] = ()


def tiles_for_fov(center, radius, order: int, *, frame: str = "equatorial", coverage=None) -> TileSelection:
    """Tile (NESTED, frame del HiPS) che toccano il cerchio di centro ``center`` e raggio ``radius``, all'ordine dato.

    Calcolo: ``astropy-healpix`` ``cone_search_lonlat`` (celle che toccano il cerchio, anche in parte); centro
    convertito nel frame del HiPS con il modulo 10. Con ``coverage`` (MOC spaziale del servizio, ICRS) restano solo
    i tile che lo toccano; nessuno → ``HIPS_OUT_OF_COVERAGE``. Il filtro di copertura vale solo per i HiPS
    equatoriali (il MOC è ICRS): per gli altri frame non si applica e si dichiara."""
    import numpy as np
    from astropy_healpix import HEALPix

    order = _check_space_order(order)
    if not isinstance(radius, u.Quantity) or not radius.isscalar or not radius.unit.is_equivalent(u.deg) \
            or not 0 < float(radius.to_value(u.deg)) <= 180:
        raise HiPSError("REGION_INVALID", f"raggio {radius!r}: serve un angolo con unità in (0°, 180°]")
    lon, lat, note = _to_frame(center, frame, "centro del campo")
    if lon.size != 1:
        raise HiPSError("REGION_INVALID", "il centro del campo è una sola posizione")
    hp = HEALPix(nside=2 ** order, order="nested")
    found = np.sort(np.asarray(hp.cone_search_lonlat(lon[0] * u.deg, lat[0] * u.deg, radius), dtype=np.int64))
    notes: list[tuple[str, str]] = []
    outside = 0
    if coverage is not None:
        if frame != "equatorial":
            notes.append(("HIPS_COVERAGE_NOT_CHECKED", f"hips_frame {frame!r}: il MOC del servizio è in ICRS, filtro "
                          "di copertura non applicato"))
        else:
            if getattr(coverage, "kind", None) != "space":
                raise TypeError("coverage: serve il MOC spaziale del servizio (modulo 16)")
            inside = _in_coverage(coverage, order, found)
            outside = int(np.count_nonzero(~inside))
            found = found[inside]
            if not found.size:
                raise HiPSError("HIPS_OUT_OF_COVERAGE", f"campo fuori dalla copertura del servizio ({outside} tile "
                                "fuori): nessun tile", outside=outside)
    description = (f"{found.size} tile all'ordine {order} per il cerchio ({lon[0]!r}°, {lat[0]!r}°) di raggio "
                   f"{float(radius.to_value(u.deg))!r}° nel frame {frame}{note} (calcolo: astropy-healpix "
                   "cone_search_lonlat, celle che toccano il cerchio)"
                   + (f"; {outside} tile fuori dalla copertura esclusi" if outside else ""))
    return TileSelection(order=order, indices=tuple(int(i) for i in found), frame=frame, outside_coverage=outside,
                         description=description, warnings=tuple(notes))


def order_for_resolution(service: HiPSService, resolution) -> tuple[int, tuple[tuple[str, str], ...]]:
    """Ordine più basso il cui pixel di tile non supera ``resolution`` (angolo); oltre l'ordine massimo del servizio
    si resta all'ordine massimo, dichiarato (``HIPS_RESOLUTION_LIMIT``). Calcolo: ``astropy-healpix``."""
    from astropy_healpix import nside_to_pixel_resolution

    if service.tile_width is None:
        raise HiPSError("HIPS_TYPE_MISMATCH", f"{service.hips_id}: i cataloghi non hanno pixel")
    if not isinstance(resolution, u.Quantity) or not resolution.unit.is_equivalent(u.deg) or resolution.value <= 0:
        raise ValueError("resolution: angolo positivo con unità")
    shift = service.tile_width.bit_length() - 1
    for order in range(service.order + 1):
        if nside_to_pixel_resolution(2 ** (order + shift)) <= resolution:
            return order, ()
    return service.order, (("HIPS_RESOLUTION_LIMIT", f"{service.hips_id}: risoluzione richiesta {resolution} "
                            f"oltre quella del servizio; ordine massimo {service.order}"),)


@dataclass(frozen=True, eq=False)
class HiPSTile:
    """Tile di un servizio HiPS con provenienza (A7). ``data`` è nell'orientamento FITS (riga 0 = prima riga del
    FITS); i tile JPEG/PNG, scritti dall'alto in basso (standard §4.2.1.3), sono capovolti per allinearli."""

    hips_id: str
    order: int
    index: int
    format: str
    data: object  # numpy.ndarray: tipo nativo del FITS (DC6); uint8 (…, 3 o 4 canali) per JPEG/PNG
    header: object | None  # astropy.io.fits.Header per i tile FITS
    url: str
    retrieved_at: datetime
    from_cache: bool
    body: str | None
    plane: int | None = None
    warnings: tuple[tuple[str, str], ...] = ()

    @property
    def nbytes(self) -> int:
        return int(self.data.nbytes)

    def provenance(self) -> str:
        state = "copia in cache" if self.from_cache else "scaricato"
        return f"{self.url} ({state} il {self.retrieved_at.isoformat()})"


class TileMemory:
    """Tile in memoria entro un limite (A10 per gli HiPS: 512 × 10⁶ byte di default, configurabile); oltre, si
    tolgono i tile usati meno di recente. Non è una cache su disco (quella è la cache comune del 04, CA4)."""

    def __init__(self, limit_bytes: int = DEFAULT_TILE_MEMORY_BYTES) -> None:
        from collections import OrderedDict

        if isinstance(limit_bytes, bool) or not isinstance(limit_bytes, int) or limit_bytes <= 0:
            raise ValueError("limit_bytes: intero positivo")
        self.limit_bytes = limit_bytes
        self._tiles: OrderedDict[str, HiPSTile] = OrderedDict()
        self.total_bytes = 0
        self.evicted = 0

    def __len__(self) -> int:
        return len(self._tiles)

    def get(self, url: str) -> HiPSTile | None:
        tile = self._tiles.get(url)
        if tile is not None:
            self._tiles.move_to_end(url)
        return tile

    def put(self, tile: HiPSTile) -> None:
        if tile.nbytes > self.limit_bytes:
            return  # più grande del limite da solo: non si tiene in memoria
        old = self._tiles.pop(tile.url, None)
        if old is not None:
            self.total_bytes -= old.nbytes
        self._tiles[tile.url] = tile
        self.total_bytes += tile.nbytes
        while self.total_bytes > self.limit_bytes:
            _, dropped = self._tiles.popitem(last=False)
            self.total_bytes -= dropped.nbytes
            self.evicted += 1


def _decode_tile(payload: bytes, fmt: str, width: int, url: str):
    """Dati e intestazione di un tile; ``None`` se il tile è corrotto o di dimensione inattesa."""
    import io

    import numpy as np

    if fmt == "fits":
        from astropy.io import fits

        try:
            with fits.open(io.BytesIO(payload), memmap=False) as hdul:
                hdu = next((h for h in hdul if h.data is not None), None)
                if hdu is None:
                    return None, "nessun dato nel FITS"
                data, header = np.array(hdu.data), hdu.header.copy()
        except Exception as exc:  # astropy: OSError/ValueError/TypeError per un FITS rovinato
            return None, f"FITS non leggibile ({exc})"
        if data.shape[-2:] != (width, width):
            return None, f"dimensione {data.shape} invece di {width}×{width}"
        return (data, header), None
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
            expected = "JPEG" if fmt == "jpeg" else "PNG"
            if image.format != expected:
                return None, f"formato {image.format} invece di {expected}"
            array = np.array(image)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        return None, f"immagine non leggibile ({exc})"
    if array.shape[:2] != (width, width):
        return None, f"dimensione {array.shape[:2]} invece di {width}×{width}"
    return (np.ascontiguousarray(array[::-1]), None), None


def _download_tile(url: str, timeouts):
    """Scarica tutto o niente; 404 → ``None`` (tile non fornito)."""
    import requests

    with requests.get(url, timeout=timeouts.as_requests(), stream=True) as response:
        if response.status_code == 404:
            return None
        if not response.ok:
            raise HiPSError("SERVICE_ERROR", f"{url}: risposta HTTP {response.status_code} {response.reason}",
                            url=url, status=response.status_code)
        return b"".join(response.iter_content(chunk_size=1 << 16))


def fetch_tile(service: HiPSService, order: int, index: int, *, format: str | None = None, plane: int | None = None,
               coverage=None, cache=None, refresh: bool = False, timeouts=None,
               memory: TileMemory | None = None) -> HiPSTile:
    """Tile ``index`` all'ordine ``order`` (immagini e cubi): prima la memoria, poi la cache comune (file del
    modulo 12, con origine e data), poi la rete. Mai un tile finto: rete assente senza copia → ``NET_TIMEOUT``;
    tile corrotto o di dimensione inattesa → una sola nuova richiesta, poi ``HIPS_BAD_TILE`` (decisione 5);
    tile non fornito dal servizio (HTTP 404) → ``HIPS_TILE_MISSING``; fuori dal MOC ``coverage`` del servizio →
    ``HIPS_OUT_OF_COVERAGE`` senza richiesta."""
    import requests

    from astrotwo.core.cache import NETWORK_TIMEOUTS, CacheError, SharedCache

    if not isinstance(service, HiPSService):
        raise TypeError("fetch_tile: serve un HiPSService")
    if service.dataproduct_type == "catalog":
        raise HiPSError("HIPS_TYPE_MISMATCH", f"{service.hips_id}: HiPS catalogo, i tile si leggono come tabelle")
    timeouts = NETWORK_TIMEOUTS if timeouts is None else timeouts
    order = _check_space_order(order, service.order, f"ordine (massimo del servizio {service.order})")
    index = _check_index(order, index)
    fmt = service.tile_formats[0] if format is None else format
    if fmt not in service.tile_formats:
        raise HiPSError("HIPS_FORMAT_UNAVAILABLE", f"{service.hips_id}: formato {fmt!r} non offerto; formati "
                        f"{', '.join(service.tile_formats)}", format=fmt)
    plane = _check_plane(service, plane)
    if coverage is not None and service.frame == "equatorial" and not _in_coverage(coverage, order, [index])[0]:
        raise HiPSError("HIPS_OUT_OF_COVERAGE", f"{service.hips_id}: tile {index} all'ordine {order} fuori dalla "
                        "copertura del servizio; nessun tile", order=order, index=index)
    url = f"{service.base_url}/{tile_path(order, index, _EXTENSIONS[fmt], plane=plane)}"
    if memory is not None and not refresh:
        held = memory.get(url)
        if held is not None:
            return held
    cache = SharedCache() if cache is None else cache
    key = f"tile:{url}"
    notes: list[tuple[str, str]] = []
    cached = None if refresh else cache.get(_CACHE_MODULE, key)
    attempts = 1  # richieste ammesse dopo un tile corrotto (decisione 5)
    if cached is not None:
        decoded, problem = _decode_tile(cached.data, fmt, service.tile_width, url)
        if decoded is not None:
            tile = HiPSTile(service.hips_id, order, index, fmt, decoded[0], decoded[1], url, cached.retrieved_at,
                            True, service.body, plane, (("FROM_CACHE", f"copia in cache di {url}, scaricata il "
                                                         f"{cached.retrieved_at.isoformat()}"),))
            if memory is not None:
                memory.put(tile)
            return tile
        notes.append(("HIPS_TILE_DISCARDED", f"copia in cache di {url} corrotta ({problem}): scartata, nuova "
                      "richiesta"))
        attempts = 0
    problem = None
    for _ in range(attempts + 1):
        try:
            payload = _download_tile(url, timeouts)
        except requests.exceptions.RequestException as exc:
            raise HiPSError("NET_TIMEOUT", f"{url} non raggiungibile (timeout {timeouts.connect:g} s connessione, "
                            f"{timeouts.read:g} s lettura): {exc}", url=url) from exc
        if payload is None:
            raise HiPSError("HIPS_TILE_MISSING", f"{url}: tile non fornito dal servizio (HTTP 404; lo standard ammette "
                            "alberi parziali e ordini bassi omessi)", url=url)
        decoded, problem = _decode_tile(payload, fmt, service.tile_width, url)
        if decoded is not None:
            break
        notes.append(("HIPS_TILE_DISCARDED", f"{url}: tile corrotto ({problem}), scartato"))
    else:
        raise HiPSError("HIPS_BAD_TILE", f"{url}: tile corrotto anche dopo una nuova richiesta ({problem})", url=url)
    retrieved_at = datetime.now(UTC)
    try:
        cache.put(_CACHE_MODULE, key, payload, origin=url, retrieved_at=retrieved_at)
    except CacheError as exc:  # es. CACHE_FULL: il tile si usa comunque
        notes.append((exc.code, exc.message))
    tile = HiPSTile(service.hips_id, order, index, fmt, decoded[0], decoded[1], url, retrieved_at, False,
                    service.body, plane, tuple(notes))
    if memory is not None:
        memory.put(tile)
    return tile


def _check_plane(service: HiPSService, plane) -> int | None:
    if service.dataproduct_type != "cube":
        if plane not in (None, 0):
            raise HiPSError("HIPS_CUBE_PLANE_INVALID", f"{service.hips_id}: non è un cubo, nessun piano {plane!r}")
        return None
    return 0 if plane is None else plane  # controllo completo dei piani in P4


def service_coverage(service: HiPSService, *, cache=None, refresh: bool = False, timeouts=None) -> tuple:
    """(MOC, avvisi): MOC del servizio (``Moc.fits`` nella radice, standard HiPS 1.0 §4.4.2) letto con il modulo 16 (cache in FITS
    IVOA). File assente → ``None`` con avviso ``HIPS_COVERAGE_UNKNOWN`` (il file è solo consigliato)."""
    from astrotwo.core.moc import MocError, read_moc

    url = service.base_url + "/Moc.fits"
    try:
        return read_moc(url, format="fits", kind="space", cache=cache, refresh=refresh, timeouts=timeouts), ()
    except MocError as exc:
        response = getattr(exc.__cause__, "response", None)
        if exc.code == "NET_TIMEOUT" and getattr(response, "status_code", None) == 404:
            return None, (("HIPS_COVERAGE_UNKNOWN", f"{url}: MOC del servizio assente (facoltativo per lo standard); "
                           "copertura non nota"),)
        raise HiPSError(exc.code, exc.message) from exc


@dataclass(frozen=True)
class PixelValues:
    """Valori dei pixel di HiPS (H27) letti dai tile FITS, mai da una copia ridotta per la visualizzazione."""

    values: object  # numpy.ndarray, tipo dei dati del tile (DC6)
    tile_index: object  # numpy.ndarray di indici dei tile
    x: object  # colonna nel tile (indice da 0, orientamento FITS)
    y: object  # riga nel tile (indice da 0)
    order: int
    unit: str | None
    description: str
    warnings: tuple[tuple[str, str], ...] = ()


def _tile_pixels(lon, lat, order: int, width: int):
    """Tile e pixel (x, y) di ogni posizione: cella all'ordine K+S (``astropy-healpix``), tile = cella >> 2S,
    sotto-indice de-interlacciato (a = bit pari, b = bit dispari); x = b, y = larghezza − 1 − a (disposizione
    verificata il 2026-10-12, §3)."""
    import numpy as np
    from astropy_healpix import HEALPix

    shift = width.bit_length() - 1
    if order + shift > _SPACE_MAX_ORDER:
        raise HiPSError("HEALPIX_ORDER_INVALID", f"ordine {order} + log2({width}) oltre {_SPACE_MAX_ORDER}")
    cells = np.asarray(HEALPix(nside=2 ** (order + shift), order="nested").lonlat_to_healpix(lon * u.deg, lat * u.deg),
                       dtype=np.int64)
    tiles = cells >> (2 * shift)
    sub = cells & ((1 << (2 * shift)) - 1)
    a = np.zeros_like(sub)
    b = np.zeros_like(sub)
    for bit in range(shift):
        a |= ((sub >> (2 * bit)) & 1) << bit
        b |= ((sub >> (2 * bit + 1)) & 1) << bit
    return tiles, b, width - 1 - a


def tile_pixel_values(tile: HiPSTile, coords, *, frame: str = "equatorial") -> PixelValues:
    """Valori del tile FITS alle posizioni date (H27); posizioni fuori dal tile → ``HIPS_OUT_OF_TILE``."""
    import numpy as np

    if tile.format != "fits":
        raise HiPSError("HIPS_PIXEL_UNAVAILABLE", f"{tile.url}: il valore del pixel si legge solo dai tile FITS, non da "
                        f"un tile {tile.format} (copia per la visualizzazione)")
    lon, lat, note = _to_frame(coords, frame, "posizioni")
    width = tile.data.shape[-1]
    tiles, x, y = _tile_pixels(lon, lat, tile.order, width)
    if np.any(tiles != tile.index):
        raise HiPSError("HIPS_OUT_OF_TILE", f"{int(np.count_nonzero(tiles != tile.index))} posizioni fuori dal tile "
                        f"{tile.index} (ordine {tile.order})")
    data = tile.data if tile.data.ndim == 2 else tile.data[0]
    values = data[y, x]
    unit = tile.header.get("BUNIT") if tile.header is not None else None
    description = (f"{len(values)} valori dal tile FITS {tile.provenance()}{note}; pixel (x, y) da 0 in "
                   "orientamento FITS (calcolo: astropy-healpix, disposizione dei pixel verificata)")
    return PixelValues(values=values, tile_index=tiles, x=x, y=y, order=tile.order, unit=unit, description=description)


def pixel_values(service: HiPSService, coords, *, order: int | None = None, cache=None, refresh: bool = False,
                 timeouts=None, memory: TileMemory | None = None) -> PixelValues:
    """Valore del pixel sotto le posizioni (H27): dai tile FITS del servizio all'ordine dato (default: il più
    profondo), scaricati o letti dalla cache; mai da tile JPEG/PNG."""
    import numpy as np

    if "fits" not in service.tile_formats:
        raise HiPSError("HIPS_PIXEL_UNAVAILABLE", f"{service.hips_id}: nessun tile FITS (formati "
                        f"{', '.join(service.tile_formats)}); il valore del pixel non è disponibile")
    order = service.order if order is None else order
    _check_space_order(order, service.order, f"ordine (massimo del servizio {service.order})")
    lon, lat, note = _to_frame(coords, service.frame, "posizioni")
    tiles, x, y = _tile_pixels(lon, lat, order, service.tile_width)
    values = None
    sources = []
    notes: list[tuple[str, str]] = []
    for index in np.unique(tiles):
        tile = fetch_tile(service, order, int(index), format="fits", cache=cache, refresh=refresh, timeouts=timeouts,
                          memory=memory)
        data = tile.data if tile.data.ndim == 2 else tile.data[0]
        if values is None:
            values = np.empty(len(tiles), dtype=data.dtype)
        here = tiles == index
        values[here] = data[y[here], x[here]]
        sources.append(tile.provenance())
        notes += [n for n in tile.warnings if n[0] != "FROM_CACHE"]
        unit = tile.header.get("BUNIT") if tile.header is not None else None
    description = (f"{len(tiles)} valori di {service.hips_id} all'ordine {order} dai tile FITS {', '.join(sources)}"
                   f"{note}")
    return PixelValues(values=values, tile_index=tiles, x=x, y=y, order=order, unit=unit, description=description,
                       warnings=tuple(notes))
