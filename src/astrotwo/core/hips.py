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
    "ViewSampling",
    "ViewTile",
    "view_sampling",
    "fill_view",
    "ActiveSurvey",
    "BUILD_METHODS",
    "BuildResult",
    "CELESTIAL_FRAMES",
    "CatalogTiles",
    "CollectionIndex",
    "CubePlanes",
    "DEFAULT_SURVEY",
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
    "build_hips",
    "catalog_tiles",
    "cube_planes",
    "fetch_tile",
    "order_for_resolution",
    "parse_properties",
    "pixel_values",
    "read_service",
    "service_coverage",
    "set_survey",
    "survey_coverage",
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
#: non precisato dallo standard, nessuna conversione finché non è verificato su un HiPS reale, D12-7).
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
    """Corpo (D19-3) dal sistema dichiarato; per i HiPS planetari da ``hips_body`` (WD HiPS 2.0), normalizzato
    con la tabella dei nomi del 19 (D12-6)."""
    if frame in CELESTIAL_FRAMES:
        return "celestial", []
    body = _first(props, "hips_body")
    if body is None:
        return None, [("BODY_UNKNOWN", f"{source}: hips_frame {frame!r} non celeste e senza hips_body: corpo non "
                       "ricavabile, il dato si apre da solo")]
    if body != frame:
        return None, [("BODY_UNKNOWN", f"{source}: hips_frame {frame!r} e hips_body {body!r} diversi: corpo non "
                       "ricavabile, il dato si apre da solo")]
    from astrotwo.core.planetary_data import PlanetaryDataError, normalize_body_name

    draft = ("HIPS_BODY_DRAFT", f"{source}: corpo {body!r} da hips_body, definito nel Working Draft HiPS 2.0 "
             "(2026-05-01), versione non ancora raccomandazione IVOA")
    try:
        canonical = normalize_body_name(body)
    except PlanetaryDataError as exc:
        return None, [draft, ("BODY_UNSUPPORTED", f"{source}: {exc.message} (tabella dei nomi del 19, D12-6): il "
                              "dato si apre da solo")]
    return canonical, [draft, ("BODY_NORMALIZED", f"{source}: hips_body {body!r} → {canonical!r} (tabella dei nomi "
                               "del modulo 19, D12-6)")]


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
    from astrotwo.core import vo_protocols as vo

    params = {"ID": hips_id, "get": "record", "fmt": "json", "fields": "ID,hips_service_url,dataproduct_type"}
    try:
        response = vo._http("mocserver", vo.MOCSERVER_URL, params, cache=cache, refresh=refresh, timeouts=timeouts)
    except vo.VoProtocolsError as exc:
        if exc.code == "NET_TIMEOUT":
            raise HiPSError("MOCSERVER_UNAVAILABLE", f"MocServer non raggiungibile per risolvere {hips_id!r}: "
                            f"{exc.message}") from exc
        raise _net(exc) from exc
    records = _mocserver_records(response.payload, vo.MOCSERVER_URL)
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
        why = ("lo standard HiPS 1.0 non precisa quale eclittica (D12-7: non supportato finché non è verificato "
               "su un HiPS reale)" if frame == "ecliptic" else "frame planetario: le posizioni planetarie arrivano con il modulo 19")
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
    if native > order:
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
    """Piano di un cubo (H24): intero in [0, hips_cube_depth); senza piano, il piano 0 (il tile senza suffisso,
    standard §4.2.3). Per un HiPS non cubo solo ``None``/0."""
    if service.dataproduct_type != "cube":
        if plane not in (None, 0):
            raise HiPSError("HIPS_CUBE_PLANE_INVALID", f"{service.hips_id}: non è un cubo, nessun piano {plane!r}")
        return None
    if plane is None:
        return 0
    if isinstance(plane, bool) or not isinstance(plane, int) or not 0 <= plane < service.cube_depth:
        raise HiPSError("HIPS_CUBE_PLANE_INVALID", f"{service.hips_id}: piano {plane!r} inesistente; piani "
                        f"disponibili 0–{service.cube_depth - 1} ({service.cube_depth})", depth=service.cube_depth)
    return plane


def service_coverage(service: HiPSService, *, cache=None, refresh: bool = False, timeouts=None) -> tuple:
    """(MOC, avvisi): MOC del servizio (``Moc.fits`` nella radice, standard HiPS 1.0 §4.4.2) letto con il modulo 16 (cache in FITS
    IVOA). File assente → ``None`` con avviso ``HIPS_COVERAGE_UNKNOWN`` (il file è solo consigliato)."""
    from astrotwo.core.moc import MocError, read_moc

    if service.body != "celestial":
        raise HiPSError("HIPS_FRAME_UNSUPPORTED", f"{service.hips_id}: corpo {service.body!r}; il MOC IVOA è ICRS, "
                        "copertura dei HiPS planetari con il modulo 19")
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


def pixel_values(service: HiPSService, coords, *, order: int | None = None, plane: int | None = None, cache=None,
                 refresh: bool = False, timeouts=None, memory: TileMemory | None = None) -> PixelValues:
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
        tile = fetch_tile(service, order, int(index), format="fits", plane=plane, cache=cache, refresh=refresh,
                          timeouts=timeouts, memory=memory)
        data = tile.data if tile.data.ndim == 2 else tile.data[0]
        if values is None:
            values = np.empty(len(tiles), dtype=data.dtype)
        here = tiles == index
        values[here] = data[y[here], x[here]]
        sources.append(tile.provenance())
        notes += [n for n in tile.warnings if n[0] != "FROM_CACHE"]
        unit = tile.header.get("BUNIT") if tile.header is not None else None
    where = f", piano {tile.plane}" if tile.plane is not None else ""
    description = (f"{len(tiles)} valori di {service.hips_id} all'ordine {order}{where} dai tile FITS "
                   f"{', '.join(sources)}{note}")
    return PixelValues(values=values, tile_index=tiles, x=x, y=y, order=order, unit=unit, description=description,
                       warnings=tuple(notes))


# --------------------------------------------------------------------------
# P6 — Riproiezione dei tile sulla vista del modulo 41 (2026-10-15)
# --------------------------------------------------------------------------
# Verifica del 2026-10-16: le funzioni HiPS pubbliche di reproject 0.21 (hips_as_dask_array,
# reproject_from_hips) scaricano i tile da sé con astropy.utils.data.download_file, non con la rete del 14
# e la cache del 04: si usa il campionamento al più vicino sulla griglia HEALPix descritto nel 12 (P6).


@dataclass(frozen=True, eq=False)
class ViewSampling:
    """Per ogni pixel della finestra (righe × colonne, centro, convenzione numpy): tile e pixel del tile.

    ``tile_of_pixel`` vale -1 per "nessun dato" (fuori dalla proiezione o fuori copertura); ``tile_x``,
    ``tile_y`` sono colonna e riga nel tile (indice da 0, orientamento FITS)."""

    hips_id: str
    order: int
    frame: str
    plane: int | None
    shape: tuple[int, int]
    tiles: tuple[int, ...]
    tile_of_pixel: object
    tile_x: object
    tile_y: object
    method: str
    description: str
    warnings: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, eq=False)
class ViewTile:
    """Valori di un tile per i pixel della finestra che vi cadono (riquadro ``[y0:y1, x0:x1]`` e maschera)."""

    index: int
    order: int
    box: tuple[int, int, int, int]  # y0, y1, x0, x1 (estremi superiori esclusi), pixel della finestra
    values: object  # FITS: tipo nativo (DC6); JPEG/PNG: uint8 (…, 3 o 4), orientamento già capovolto
    mask: object  # True dove il pixel della finestra prende il valore da questo tile
    format: str
    provenance: str
    from_cache: bool


def view_sampling(service: HiPSService, view, *, order: int | None = None, plane: int | None = None,
                  coverage=None) -> ViewSampling:
    """Tile necessari per la finestra della vista e, per ogni suo pixel, tile e pixel del tile (P6).

    Metodo ``nearest``: cielo del centro di ogni pixel con ``window_to_sky`` di ``ViewGeometry`` (10), frame del
    HiPS con il modulo 10, cella all'ordine K + S con ``astropy-healpix`` e disposizione dei pixel verificata
    (stessa regola di ``pixel_values``). Ordine di default: ``order_for_resolution`` alla scala della finestra."""
    import numpy as np

    from astrotwo.core.coordinates_wcs import SkyFrame, ViewGeometry

    if not isinstance(view, ViewGeometry):
        raise TypeError("view: serve la ViewGeometry di make_view_wcs (modulo 10)")
    if service.tile_width is None:
        raise HiPSError("HIPS_TYPE_MISMATCH", f"{service.hips_id}: i cataloghi non hanno pixel")
    target = _astropy_frame(service.frame)
    notes: list[tuple[str, str]] = []
    if order is None:
        order, more = order_for_resolution(service, view.scale)
        notes += list(more)
    _check_space_order(order, service.order, f"ordine (massimo del servizio {service.order})")
    plane = _check_plane(service, plane)
    rows, cols = view.shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    sky = view.window_to_sky(xx.ravel().astype(np.float64), yy.ravel().astype(np.float64))
    finite = np.isfinite(sky.spherical.lon.value) & np.isfinite(sky.spherical.lat.value)
    tile_of_pixel = np.full(rows * cols, -1, dtype=np.int64)
    tile_x = np.zeros(rows * cols, dtype=np.int32)
    tile_y = np.zeros(rows * cols, dtype=np.int32)
    note = ""
    if np.any(finite):
        lon, lat, note = _to_frame(SkyFrame(coord=sky[finite], frame_defaults_note="frame della base della vista"),
                                   service.frame, "pixel della finestra")
        tiles, x, y = _tile_pixels(lon, lat, order, service.tile_width)
        keep = np.ones(tiles.size, dtype=bool)
        if coverage is not None:
            if service.frame != "equatorial":
                notes.append(("HIPS_COVERAGE_NOT_CHECKED", f"hips_frame {service.frame!r}: il MOC del servizio è in "
                              "ICRS, filtro di copertura non applicato"))
            else:
                if getattr(coverage, "kind", None) != "space":
                    raise TypeError("coverage: serve il MOC spaziale del servizio (modulo 16)")
                keep = _in_coverage(coverage, order, tiles)
        where = np.flatnonzero(finite)[keep]
        tile_of_pixel[where] = tiles[keep]
        tile_x[where] = x[keep]
        tile_y[where] = y[keep]
    needed = tuple(int(i) for i in np.unique(tile_of_pixel[tile_of_pixel >= 0]))
    empty = int(np.count_nonzero(tile_of_pixel < 0))
    description = (f"{len(needed)} tile di {service.hips_id} all'ordine {order} per una finestra di {cols} × {rows} "
                   f"pixel; {empty} pixel senza dati (fuori dalla proiezione o dalla copertura); frame {target}{note}; "
                   "metodo nearest: pixel HiPS che contiene il centro di ogni pixel della finestra (astropy-healpix, "
                   "disposizione dei pixel verificata)")
    return ViewSampling(hips_id=service.hips_id, order=order, frame=service.frame, plane=plane, shape=(rows, cols),
                        tiles=needed, tile_of_pixel=tile_of_pixel.reshape(rows, cols),
                        tile_x=tile_x.reshape(rows, cols), tile_y=tile_y.reshape(rows, cols), method="nearest",
                        description=description, warnings=tuple(notes))


def fill_view(sampling: ViewSampling, tile: HiPSTile) -> ViewTile:
    """Valori del tile (``fetch_tile``) per i soli pixel della finestra che vi cadono (riempimento progressivo)."""
    import numpy as np

    if tile.order != sampling.order:
        raise HiPSError("HIPS_OUT_OF_TILE", f"tile all'ordine {tile.order}, campionamento all'ordine {sampling.order}")
    mask = sampling.tile_of_pixel == tile.index
    if not np.any(mask):
        raise HiPSError("HIPS_OUT_OF_TILE", f"il tile {tile.index} non contiene pixel della finestra")
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    y0, y1, x0, x1 = int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1
    box_mask = mask[y0:y1, x0:x1]
    tx = sampling.tile_x[y0:y1, x0:x1][box_mask]
    ty = sampling.tile_y[y0:y1, x0:x1][box_mask]
    data = tile.data
    if tile.format == "fits":
        plane_data = data if data.ndim == 2 else data[0]
        values = np.zeros(box_mask.shape, dtype=plane_data.dtype)
    else:
        plane_data = data
        values = np.zeros(box_mask.shape + data.shape[2:], dtype=data.dtype)
    values[box_mask] = plane_data[ty, tx]
    return ViewTile(index=tile.index, order=tile.order, box=(y0, y1, x0, x1), values=values, mask=box_mask,
                    format=tile.format, provenance=tile.provenance(), from_cache=tile.from_cache)


# --------------------------------------------------------------------------
# P3 — Elenco delle collezioni (H26), survey attivo (C1, C2), impronta (C4)
# --------------------------------------------------------------------------

#: Survey attivo di default (D12-3): DSS2 a colori, identificativo verificato nel MocServer il 2026-10-12.
DEFAULT_SURVEY = "CDS/P/DSS2/color"
#: Proprietà copiate nell'indice locale delle collezioni HiPS (scelta minore, confermata il 2026-10-12).
INDEX_FIELDS: tuple[str, ...] = (
    "ID", "obs_title", "obs_regime", "dataproduct_type", "dataproduct_subtype", "hips_service_url", "hips_order",
    "hips_frame", "hips_body", "hips_tile_format", "em_min", "em_max", "moc_sky_fraction", "client_category",
)
_INDEX_TEXT_FIELDS = ("ID", "obs_title", "client_category")


def _mocserver_records(payload: bytes, url: str) -> list[dict]:
    """Record del MocServer, letti con la codifica dichiarata dal servizio (``MOCSERVER_CHARSET`` del 14)."""
    import json

    from astrotwo.core.vo_protocols import MOCSERVER_CHARSET

    try:
        records = json.loads(payload.decode(MOCSERVER_CHARSET))
        if not isinstance(records, list) or not all(isinstance(r, dict) and isinstance(r.get("ID"), str)
                                                    for r in records):
            raise ValueError("attesa una lista di record con ID")
    except ValueError as exc:
        raise HiPSError("SERVICE_ERROR", f"{url}: risposta non leggibile ({exc})", url=url) from exc
    return records


class CollectionIndex:
    """Copia locale delle proprietà delle collezioni HiPS del MocServer (H26), con origine e data della
    sincronizzazione. ``sync()`` legge il MocServer (rete e cache del 14); senza rete usa la copia in cache con
    la sua data (avviso ``MOCSERVER_UNAVAILABLE``). ``filter`` lavora solo sulla copia locale."""

    def __init__(self, *, cache=None, timeouts=None) -> None:
        self._cache = cache
        self._timeouts = timeouts
        self.records: tuple[dict, ...] = ()
        self.origin: str | None = None
        self.synced_at: datetime | None = None
        self.from_cache = False
        self.request = None
        self.warnings: tuple[tuple[str, str], ...] = ()

    def sync(self) -> CollectionIndex:
        from astrotwo.core import vo_protocols as vo
        from astrotwo.core.cache import NETWORK_TIMEOUTS

        timeouts = NETWORK_TIMEOUTS if self._timeouts is None else self._timeouts
        params = {"expr": "hips_service_url=*", "get": "record", "fmt": "json", "fields": ",".join(INDEX_FIELDS)}
        try:
            response = vo._http("mocserver", vo.MOCSERVER_URL, params, cache=self._cache, refresh=True,
                                timeouts=timeouts)
        except vo.VoProtocolsError as exc:
            if exc.code == "NET_TIMEOUT":
                raise HiPSError("MOCSERVER_UNAVAILABLE", f"MocServer non raggiungibile e nessuna copia locale delle "
                                f"collezioni: {exc.message}") from exc
            raise _net(exc) from exc
        records = _mocserver_records(response.payload, vo.MOCSERVER_URL)
        notes = []
        if response.from_cache:  # rete assente: copia locale con la sua data
            notes.append(("MOCSERVER_UNAVAILABLE", f"MocServer non raggiungibile: copia locale delle collezioni del "
                          f"{response.retrieved_at.isoformat()}"))
        else:
            notes += list(vo._store(response, "mocserver", self._cache))
        self.records = tuple(sorted(records, key=lambda r: r["ID"]))
        self.origin = vo.MOCSERVER_URL
        self.synced_at = response.retrieved_at
        self.from_cache = response.from_cache
        self.request = vo._record("mocserver", "CollectionIndex.sync", {"fields": list(INDEX_FIELDS)}, response,
                                  len(records))
        self.warnings = tuple(notes)
        return self

    def filter(self, text: str | None = None, **rules: str) -> tuple[dict, ...]:
        """Collezioni della copia locale: ``text`` = parole cercate (senza maiuscole) in identificativo, titolo e
        categoria, tutte presenti; ``rules`` = proprietà → modello con i jolly ``*`` e ``?`` (senza maiuscole),
        tutte vere. Nessuna rete."""
        import fnmatch

        words = text.lower().split() if text else []
        found = []
        for record in self.records:
            haystack = " ".join(str(record.get(f, "")) for f in _INDEX_TEXT_FIELDS).lower()
            if any(word not in haystack for word in words):
                continue
            ok = True
            for name, pattern in rules.items():
                value = record.get(name)
                values = value if isinstance(value, list) else [value]
                if not any(v is not None and fnmatch.fnmatchcase(str(v).lower(), str(pattern).lower())
                           for v in values):
                    ok = False
                    break
            if ok:
                found.append(record)
        return tuple(found)

    def describe(self) -> str:
        if self.synced_at is None:
            return "indice delle collezioni non sincronizzato"
        state = "copia locale" if self.from_cache else "sincronizzato"
        return f"{len(self.records)} collezioni HiPS da {self.origin} ({state} del {self.synced_at.isoformat()})"


@dataclass(frozen=True)
class ActiveSurvey:
    """Survey attivato (C1): metadati del servizio e copertura (C4), con gli avvisi."""

    service: HiPSService
    coverage: object | None  # Moc spaziale del 16, None se non nota
    warnings: tuple[tuple[str, str], ...] = ()


def survey_coverage(service: HiPSService, *, cache=None, refresh: bool = False, timeouts=None) -> tuple:
    """(MOC, avvisi): copertura del survey come MOC (C4), calcolata dal 16. Prima il ``Moc.fits`` del servizio
    (standard HiPS 1.0 §4.4.2); se manca, il MOC della collezione dal MocServer (``get=moc``), dichiarato. Solo
    per i survey celesti: il MOC IVOA è ICRS (planetari → ``HIPS_FRAME_UNSUPPORTED`` fino al 19)."""
    from astrotwo.core import vo_protocols as vo
    from astrotwo.core.moc import MocError, read_moc

    if service.body != "celestial":
        raise HiPSError("HIPS_FRAME_UNSUPPORTED", f"{service.hips_id}: corpo {service.body!r}; copertura dei HiPS "
                        "planetari con il modulo 19")
    moc, notes = service_coverage(service, cache=cache, refresh=refresh, timeouts=timeouts)
    if moc is not None:
        return moc, notes
    import urllib.parse

    url = vo.MOCSERVER_URL + "?" + urllib.parse.urlencode({"ID": service.hips_id, "get": "moc", "fmt": "fits"})
    try:
        moc = read_moc(url, format="fits", kind="space", cache=cache, refresh=refresh, timeouts=timeouts)
    except MocError as exc:
        if exc.code == "NET_TIMEOUT":
            raise HiPSError("MOCSERVER_UNAVAILABLE", f"copertura di {service.hips_id}: {exc.message}") from exc
        raise HiPSError(exc.code, exc.message) from exc
    return moc, tuple(notes) + (("HIPS_COVERAGE_FROM_MOCSERVER", f"{service.hips_id}: copertura dal MocServer "
                                 f"({url}), il servizio non fornisce Moc.fits"),)


def set_survey(hips_id: str | None = None, *, hips_list: HiPSList | None = None, cache=None, refresh: bool = False,
               timeouts=None) -> ActiveSurvey:
    """Attiva un survey (C1) e ne restituisce metadati e copertura; senza identificativo il default DSS2 a colori
    (D12-3). Un survey non in ``hips_list`` si legge con ``add_hips`` (e si aggiunge all'elenco). La copertura
    mancante non impedisce l'attivazione (avviso); un survey planetario si attiva senza copertura (19)."""
    target = DEFAULT_SURVEY if hips_id is None else hips_id
    notes: list[tuple[str, str]] = []
    if hips_id is None:
        notes.append(("HIPS_DEFAULT_SURVEY", f"survey di default {DEFAULT_SURVEY} (D12-3)"))
    if hips_list is not None and target in hips_list and not refresh:
        service = hips_list.get(target)
    elif hips_list is not None:
        service = hips_list.add_hips(target, cache=cache, refresh=refresh, timeouts=timeouts)
    else:
        service = add_hips(target, cache=cache, refresh=refresh, timeouts=timeouts)
    coverage = None
    try:
        coverage, cov_notes = survey_coverage(service, cache=cache, refresh=refresh, timeouts=timeouts)
        notes += cov_notes
    except HiPSError as exc:
        notes.append(("HIPS_COVERAGE_UNKNOWN", f"{service.hips_id}: copertura non disponibile ({exc.code}: "
                      f"{exc.message})"))
    return ActiveSurvey(service=service, coverage=coverage, warnings=service.warnings + tuple(notes))


# --------------------------------------------------------------------------
# P4 — Cubi HiPS (H24) e cataloghi HiPS progressivi (H12)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class CubePlanes:
    """Piani di un cubo HiPS (standard HiPS 1.0 §4.2.3, ``hips_cube_depth``) e asse fisico se dichiarato."""

    depth: int
    first_frame: int  # hips_cube_firstframe (piano da mostrare all'inizio; default 0)
    axis: u.Quantity | None  # valore fisico di ogni piano dalle chiavi data_cube_*, se presenti
    description: str
    warnings: tuple[tuple[str, str], ...] = ()


def cube_planes(service: HiPSService) -> CubePlanes:
    """Numero e descrizione dei piani di un cubo HiPS (H24). Asse fisico dalle chiavi facoltative
    ``data_cube_crpix3``, ``data_cube_crval3``, ``data_cube_cdelt3``, ``data_cube_bunit3`` secondo la regola FITS
    lineare ``valore = CRVAL3 + (p − CRPIX3) × CDELT3`` con p = indice FITS del piano (da 1, conversione del 10)."""
    import numpy as np

    from astrotwo.core.coordinates_wcs import convert_pixel_convention

    if service.dataproduct_type != "cube":
        raise HiPSError("HIPS_TYPE_MISMATCH", f"{service.hips_id}: non è un cubo HiPS ({service.dataproduct_type})")
    props, source = service.properties, service.origin
    first = _int(props, "hips_cube_firstframe", source) or 0
    notes: list[tuple[str, str]] = []
    if first >= service.cube_depth:
        raise _invalid(source, "hips_cube_firstframe", f"{first} oltre la profondità {service.cube_depth}")
    keys = ("data_cube_crpix3", "data_cube_crval3", "data_cube_cdelt3")
    found = {k: _float(props, k, source) for k in keys}
    axis = None
    if all(v is not None for v in found.values()):
        planes = np.arange(service.cube_depth, dtype=np.float64)
        fits_index = convert_pixel_convention(planes, np.zeros_like(planes), "numpy", "fits").x
        values = found["data_cube_crval3"] + (fits_index - found["data_cube_crpix3"]) * found["data_cube_cdelt3"]
        unit_text = _first(props, "data_cube_bunit3")
        unit = u.dimensionless_unscaled
        if unit_text is not None:
            try:
                unit = u.Unit(unit_text, format="fits")
            except ValueError:
                notes.append(("HIPS_CUBE_UNIT_UNKNOWN", f"{source}: data_cube_bunit3 {unit_text!r} non è un'unità FITS: "
                              "asse senza unità"))
        else:
            notes.append(("HIPS_CUBE_UNIT_UNKNOWN", f"{source}: data_cube_bunit3 assente: asse senza unità"))
        axis = values * unit
    elif any(v is not None for v in found.values()):
        notes.append(("HIPS_CUBE_AXIS_INCOMPLETE", f"{source}: chiavi data_cube_* incomplete, asse fisico non "
                      "calcolato"))
    description = (f"cubo {service.hips_id}: {service.cube_depth} piani (0–{service.cube_depth - 1}), piano iniziale "
                   f"{first}" + (f", asse da {axis[0]} a {axis[-1]}" if axis is not None else ", asse fisico non "
                                 "dichiarato"))
    return CubePlanes(depth=service.cube_depth, first_frame=first, axis=axis, description=description,
                      warnings=tuple(notes))


@dataclass(frozen=True)
class CatalogTiles:
    """Sorgenti di un catalogo HiPS progressivo (H12) nei tile che toccano il campo, ordine per ordine."""

    table: object  # CatalogTable del 13
    order: int  # ordine più profondo letto
    tiles: tuple[tuple[int, int, str, int, bool], ...]  # (ordine, indice, URL, righe, da cache)
    complete: bool  # True se nessun tile letto ha figli possibili (ordine massimo del servizio raggiunto)
    description: str
    warnings: tuple[tuple[str, str], ...] = ()


def _cached_bytes(url: str, cache, refresh: bool, timeouts, check):
    """(byte, data, da cache, avvisi) di un file del servizio: cache comune (modulo 12) o rete; ``check`` dice se
    i byte sono validi (un file non valido: una nuova richiesta, poi ``HIPS_BAD_TILE``); 404 → ``None``."""
    import requests

    from astrotwo.core.cache import CacheError

    key = f"tile:{url}"
    notes: list[tuple[str, str]] = []
    cached = None if refresh else cache.get(_CACHE_MODULE, key)
    attempts = 1
    if cached is not None:
        problem = check(cached.data)
        if problem is None:
            return cached.data, cached.retrieved_at, True, ()
        notes.append(("HIPS_TILE_DISCARDED", f"copia in cache di {url} non valida ({problem}): nuova richiesta"))
        attempts = 0
    for _ in range(attempts + 1):
        try:
            payload = _download_tile(url, timeouts)
        except requests.exceptions.RequestException as exc:
            raise HiPSError("NET_TIMEOUT", f"{url} non raggiungibile (timeout {timeouts.connect:g} s connessione, "
                            f"{timeouts.read:g} s lettura): {exc}", url=url) from exc
        if payload is None:
            return None, None, False, tuple(notes)
        problem = check(payload)
        if problem is None:
            break
        notes.append(("HIPS_TILE_DISCARDED", f"{url}: file non valido ({problem}), scartato"))
    else:
        raise HiPSError("HIPS_BAD_TILE", f"{url}: file non valido anche dopo una nuova richiesta ({problem})", url=url)
    retrieved_at = datetime.now(UTC)
    try:
        cache.put(_CACHE_MODULE, key, payload, origin=url, retrieved_at=retrieved_at)
    except CacheError as exc:
        notes.append((exc.code, exc.message))
    return payload, retrieved_at, False, tuple(notes)


def _tsv_rows(payload: bytes, names: list[str]):
    """Righe di un tile TSV (standard §4.2.2.1): UTF-8, ``#`` = commento, prima riga = nomi delle colonne (uguali a
    quelli di ``metadata.xml``), campi separati da TAB, campo vuoto = nullo. Errore → (None, motivo)."""
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, f"non UTF-8 ({exc})"
    lines = [line.rstrip("\r") for line in text.split("\n")]
    lines = [line for line in lines if line and not line.startswith("#")]
    if not lines:
        return None, "nessuna riga di intestazione"
    header = lines[0].split("\t")
    if header != names:
        return None, f"colonne {header} diverse da metadata.xml {names}"
    rows = [line.split("\t") for line in lines[1:]]
    bad = [i for i, row in enumerate(rows) if len(row) != len(names)]
    if bad:
        return None, f"riga {bad[0] + 2}: {len(rows[bad[0]])} campi invece di {len(names)}"
    return rows, None


def catalog_tiles(service: HiPSService, center, radius, order: int, *, cache=None, refresh: bool = False,
                  timeouts=None):
    """Catalogo HiPS progressivo (H12): sorgenti dei tile che toccano il cerchio, dall'ordine più basso fino a
    ``order`` (ogni ordine aggiunge sorgenti diverse, standard §4.2.2). Si usano i tile regolari, mai ``Allsky``
    (che li duplica). Si parte da ``hips_order_min`` (gli ordini sotto sono omessi dal servizio e non si chiedono);
    un tile assente (HTTP 404) chiude il suo ramo (nessun figlio richiesto). Colonne, unità, UCD e sistema delle posizioni
    da ``metadata.xml`` (VOTable obbligatorio per i cataloghi); la tabella si legge con il lettore del 13. Le righe
    non sono ritagliate sul cerchio (tutto il contenuto dei tile)."""
    import dataclasses
    import io
    import os
    import tempfile

    from astropy.io import votable

    from astrotwo.core import vo_protocols as vo
    from astrotwo.core.cache import NETWORK_TIMEOUTS, SharedCache
    from astrotwo.core.catalogs import read_table

    if service.dataproduct_type != "catalog":
        raise HiPSError("HIPS_TYPE_MISMATCH", f"{service.hips_id}: non è un catalogo HiPS ({service.dataproduct_type})")
    timeouts = NETWORK_TIMEOUTS if timeouts is None else timeouts
    cache = SharedCache() if cache is None else cache
    order = _check_space_order(order, service.order, f"ordine (massimo del servizio {service.order})")
    order_min = _int(service.properties, "hips_order_min", service.origin) or 0
    meta_url = service.base_url + "/metadata.xml"
    try:
        response = vo._http("hips", meta_url, cache=cache, refresh=refresh, timeouts=timeouts)
    except vo.VoProtocolsError as exc:
        if exc.code == "SERVICE_ERROR":
            raise HiPSError("HIPS_METADATA_INVALID", f"{meta_url}: {exc.message}; metadata.xml è richiesto per i "
                            "cataloghi HiPS (standard §4.4.3)", field="metadata.xml") from exc
        raise _net(exc) from exc
    try:
        template = votable.parse(io.BytesIO(response.payload), verify="warn")
        vtable = template.get_first_table()
    except Exception as exc:  # astropy.io.votable: errori di XML o di VOTable
        raise HiPSError("HIPS_METADATA_INVALID", f"{meta_url}: VOTable non leggibile ({exc})",
                        field="metadata.xml") from exc
    notes = list(response.notes) + list(vo._store(response, "hips", cache))
    names = [f.name for f in vtable.fields]
    selection = None
    rows: list[list[str]] = []
    read: list[tuple[int, int, str, int, bool]] = []
    present: set[int] | None = None
    latest = response.retrieved_at
    for level in range(min(order_min, order), order + 1):  # gli ordini sotto hips_order_min sono omessi
        selection = tiles_for_fov(center, radius, level, frame=service.frame)
        indices = selection.indices
        if present is not None:
            indices = tuple(i for i in indices if (i >> 2) in present)
        found: set[int] = set()
        for index in indices:
            url = f"{service.base_url}/{tile_path(level, index, 'tsv')}"
            payload, when, from_cache, tile_notes = _cached_bytes(url, cache, refresh, timeouts,
                                                               lambda b: _tsv_rows(b, names)[1])
            notes += tile_notes
            if payload is None:
                continue
            tile_rows, _ = _tsv_rows(payload, names)
            rows += tile_rows
            latest = when if latest is None else max(latest, when)
            found.add(index)
            read.append((level, index, url, len(tile_rows), from_cache))
        present = found
        if not found:
            break
    vtable.create_arrays(nrows=len(rows))
    for j, field in enumerate(vtable.fields):
        column = vtable.array[field.name]
        for i, row in enumerate(rows):
            text = row[j]
            if text == "":
                column.mask[i] = True
                continue
            try:
                value, mask = field.converter.parse(text, config={"version": template.version})
            except Exception as exc:  # valore non conforme al tipo dichiarato
                raise HiPSError("HIPS_BAD_TILE", f"{service.hips_id}: valore {text!r} della colonna {field.name} non "
                                f"conforme al tipo {field.datatype} ({exc})") from exc
            column[i] = value
            column.mask[i] = mask
    fd, tmp = tempfile.mkstemp(prefix="astrotwo-hipscat-", suffix=".xml")
    os.close(fd)
    try:
        template.to_xml(tmp)
        table = read_table(tmp)  # formato riconosciuto dal 13 (VOTable)
    finally:
        os.unlink(tmp)
    table = dataclasses.replace(table, source=service.base_url, origin=service.base_url, retrieved_at=latest,
                                file_modified=None)
    deepest = max((t[0] for t in read), default=0)
    complete = not read or deepest >= service.order or (present is not None and not present)
    description = (f"{len(rows)} sorgenti di {service.hips_id} da {len(read)} tile TSV (ordini 0–{order}, minimo del "
                   f"servizio {order_min}) per {selection.description if selection else 'il campo'}; righe dei tile "
                   "non ritagliate sul cerchio" + ("" if complete else "; altre sorgenti agli ordini più profondi"))
    return CatalogTiles(table=table, order=order, tiles=tuple(read), complete=bool(complete), description=description,
                        warnings=tuple(notes) + table.warnings)


# --------------------------------------------------------------------------
# P5 — Generazione di HiPS (H9) secondo lo standard HiPS 1.0, ricampionamento con reproject
# --------------------------------------------------------------------------

#: Metodi di ricampionamento di ``build_hips`` (``reproject_interp``); "flux" (``reproject_exact``) richiede i
#: contorni dei pixel di uscita, non definiti per la griglia HEALPix dei tile: non disponibile.
BUILD_METHODS: tuple[str, ...] = ("nearest", "bilinear")
_FLOAT64 = 8


def _subindex(a, b, shift: int):
    """Inverso del de-interlacciamento: sotto-indice NESTED da a (bit pari) e b (bit dispari)."""
    import numpy as np

    sub = np.zeros_like(a)
    for bit in range(shift):
        sub |= ((a >> bit) & 1) << (2 * bit)
        sub |= ((b >> bit) & 1) << (2 * bit + 1)
    return sub


def _tile_wcs(order: int, index: int, width: int, frame: str):
    """WCS APE 14 di un tile HiPS: ogni pixel (x, y) è il centro della sua cella HEALPix all'ordine K+S
    (``astropy-healpix``), con la disposizione verificata (§3); posizioni fuori dal tile → NaN. Così il
    ricampionamento resta a ``reproject`` (API pubblica) senza una proiezione HPX scritta da noi."""
    import numpy as np
    from astropy.coordinates import SkyCoord, frame_transform_graph
    from astropy.wcs.wcsapi import BaseLowLevelWCS, HighLevelWCSWrapper
    from astropy_healpix import HEALPix

    shift = width.bit_length() - 1
    hp = HEALPix(nside=2 ** (order + shift), order="nested")
    sky_frame = frame_transform_graph.lookup_name(_astropy_frame(frame))()
    types = ["pos.eq.ra", "pos.eq.dec"] if frame == "equatorial" else ["pos.galactic.lon", "pos.galactic.lat"]

    class TileWCS(BaseLowLevelWCS):
        pixel_n_dim = 2
        world_n_dim = 2
        world_axis_physical_types = types
        world_axis_units = ["deg", "deg"]
        world_axis_object_components = [("celestial", 0, "spherical.lon.degree"),
                                        ("celestial", 1, "spherical.lat.degree")]
        world_axis_object_classes = {"celestial": (SkyCoord, (), {"frame": sky_frame, "unit": u.deg})}
        pixel_shape = (width, width)
        array_shape = (width, width)

        def pixel_to_world_values(self, x, y):
            x = np.rint(np.asarray(x, dtype=np.float64)).astype(np.int64)
            y = np.rint(np.asarray(y, dtype=np.float64)).astype(np.int64)
            ok = (x >= 0) & (x < width) & (y >= 0) & (y < width)
            b = np.where(ok, x, 0)
            a = np.where(ok, width - 1 - y, 0)
            lon, lat = hp.healpix_to_lonlat((index << (2 * shift)) + _subindex(a, b, shift))
            return (np.where(ok, lon.to_value(u.deg), np.nan), np.where(ok, lat.to_value(u.deg), np.nan))

        def world_to_pixel_values(self, lon, lat):
            lon = np.asarray(lon, dtype=np.float64)
            lat = np.asarray(lat, dtype=np.float64)
            good = np.isfinite(lon) & np.isfinite(lat)
            tiles, x, y = _tile_pixels(np.where(good, lon, 0.0), np.where(good, lat, 0.0), order, width)
            inside = good & (tiles == index)
            return (np.where(inside, x, np.nan).astype(np.float64), np.where(inside, y, np.nan).astype(np.float64))

    return HighLevelWCSWrapper(TileWCS())


@dataclass(frozen=True)
class BuildResult:
    """HiPS generato (H9): cartella, ordini, tile per ordine, formati, MOC, proprietà scritte e avvisi."""

    path: object  # pathlib.Path della radice del HiPS
    order: int
    tile_width: int
    tiles_per_order: dict[int, int]
    formats: tuple[str, ...]
    coverage: object  # Moc del 16 scritto in Moc.fits
    properties: dict[str, str]
    description: str
    warnings: tuple[tuple[str, str], ...] = ()


def _write_fits_tile(path, data, bunit: str | None) -> None:
    from astropy.io import fits

    header = fits.Header()
    if bunit:
        header["BUNIT"] = bunit
    path.parent.mkdir(parents=True, exist_ok=True)
    fits.PrimaryHDU(data, header=header).writeto(path)


def _quadrant(q: int, half: int) -> tuple[slice, slice]:
    """(righe, colonne) del figlio q (0–3) nel tile padre: bit alto di b = q >> 1 (colonne a destra), bit alto di
    a = q & 1 (righe in basso, perché y = larghezza − 1 − a) — dalla disposizione verificata (§3)."""
    rows = slice(0, half) if q & 1 else slice(half, 2 * half)
    cols = slice(half, 2 * half) if q >> 1 else slice(0, half)
    return rows, cols


def build_hips(images, output, *, order: int, hips_id: str, title: str, method: str, tile_width: int = 512,
               formats: tuple[str, ...] = (), display=None, status: str = "public master clonableOnce"
               ) -> BuildResult:
    """Genera un HiPS immagine (H9) secondo lo standard HiPS 1.0 da una o più immagini dell'11 con WCS.

    - ``order`` (ordine più profondo) **obbligatorio**; ``tile_width`` 512 di default (potenza di 2), dichiarata.
    - Tile **FITS sempre** (``float64``: valori ricampionati, DC6); ``formats`` facoltativi ``png``/``jpeg``
      solo con ``display = (vmin, vmax, funzione di trasferimento)`` espliciti (come per l'RGB dell'11), palette
      grigia; ``histeq`` non ammessa (dipende dal tile).
    - Ricampionamento: ``reproject_interp`` (``method`` ``nearest`` o ``bilinear``, obbligatorio) sulla griglia
      HEALPix del tile; più immagini: media pesata con la copertura (``hips_overlay = mean``).
    - Un tile alla volta (A10); stima della memoria con il limite delle operazioni (D11-11, 4 GB).
    - Ordini inferiori: ogni pixel è la media (``nanmean``) dei 4 pixel dell'ordine sotto (``hips_hierarchy =
      mean``); ``Moc.fits`` con il 16 (unione dei MOC delle immagini all'ordine ``order``); ``properties``
      scritto per ultimo. Solo frame ``equatorial``. ``Allsky`` non prodotto (facoltativo; D12-8).
    - ``output`` deve essere una cartella nuova o vuota: nulla si sovrascrive."""
    import warnings
    from pathlib import Path

    import numpy as np
    from astropy.io import fits
    from astropy.nddata import block_reduce
    from PIL import Image
    from reproject import reproject_interp

    import astrotwo
    from astrotwo.core.images_fits import STRETCHES, FitsImage, LargeImageLimits, set_display
    from astrotwo.core.moc import moc_from_image, write_moc

    images = list(images)
    if not images or not all(isinstance(im, FitsImage) for im in images):
        raise TypeError("build_hips: servono una o più immagini FitsImage (modulo 11)")
    if isinstance(tile_width, bool) or not isinstance(tile_width, int) or tile_width < 2 or tile_width & (tile_width - 1):
        raise ValueError(f"tile_width {tile_width!r}: potenza di 2 (default 512)")
    shift = tile_width.bit_length() - 1
    order = _check_space_order(order, _SPACE_MAX_ORDER - shift, f"ordine (con tile da {tile_width} pixel)")
    if method not in BUILD_METHODS:
        raise HiPSError("OPERATION_UNSUPPORTED", f"metodo {method!r}: ammessi {', '.join(BUILD_METHODS)} (flux non "
                        "disponibile sulla griglia HEALPix dei tile)")
    if not isinstance(hips_id, str) or not re.match(r"^[A-Za-z0-9._~-]+(/[A-Za-z0-9._~+-]+)+$", hips_id):
        raise ValueError(f"hips_id {hips_id!r}: identificativo nella forma AUTORITÀ/P/nome (senza ivo://)")
    if not isinstance(title, str) or not title.strip() or "\n" in title:
        raise ValueError("title: testo di una riga, obbligatorio (obs_title)")
    formats = tuple(formats)
    if any(f not in ("png", "jpeg") for f in formats) or len(set(formats)) != len(formats):
        raise ValueError("formats: facoltativi 'png' e/o 'jpeg' (i tile FITS si scrivono sempre)")
    if formats:
        if display is None or len(display) != 3:
            raise HiPSError("HIPS_DISPLAY_REQUIRED", "tile PNG/JPEG: servono (vmin, vmax, funzione di trasferimento) "
                            "espliciti")
        vmin, vmax, stretch = float(display[0]), float(display[1]), display[2]
        if stretch not in STRETCHES or stretch == "histeq":
            raise HiPSError("HIPS_DISPLAY_INVALID", f"funzione di trasferimento {stretch!r}: ammesse "
                            f"{', '.join(s for s in STRETCHES if s != 'histeq')} (histeq dipende dal tile)")
        if not (np.isfinite(vmin) and np.isfinite(vmax) and vmin < vmax):
            raise HiPSError("HIPS_DISPLAY_INVALID", "serve vmin < vmax, entrambi finiti")
    for im in images:
        if im.color:
            raise HiPSError("OPERATION_UNSUPPORTED", f"{im.origin}: immagine a colori, solo presentazione")
        if im.is_preview:
            raise HiPSError("PREVIEW_NOT_MEASURABLE", f"{im.origin}: aperta a due livelli, in memoria c'è solo "
                            "l'anteprima")
        if im.wcs is None:
            raise HiPSError("WCS_MISSING", f"{im.origin}: nessun WCS, nessuna posizione sul cielo")
    # Memoria (A10, D11-11): copie float64 degli ingressi + lavoro di un tile (risultato e copertura per immagine,
    # somme, tile ridotto e immagine di presentazione).
    caps = [im.limits.operation_bytes for im in images if im.limits is not None]
    cap = min(caps) if caps else LargeImageLimits().operation_bytes
    tile_pixels = tile_width * tile_width
    needed = sum(int(np.prod(im.data.shape)) for im in images) * _FLOAT64 + (2 * len(images) + 6) * tile_pixels * \
        _FLOAT64
    if needed > cap:
        raise HiPSError("MEMORY_LIMIT_EXCEEDED", f"build_hips: servono circa {needed} byte, oltre il limite delle "
                        f"operazioni di {cap} byte (D11-11)", needed_bytes=needed, limit_bytes=cap)
    root = Path(output)
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise FileExistsError(f"{root}: la cartella del HiPS deve essere nuova o vuota (nulla si sovrascrive)")
    notes: list[tuple[str, str]] = []
    # Copertura e tile dell'ordine più profondo: unione dei MOC delle immagini (16, pixel validi con il WCS).
    coverage = None
    for im in images:
        moc = moc_from_image(im, order)
        notes += [n for n in moc.warnings if n[0] != "MOC_EMPTY"]
        coverage = moc if coverage is None else coverage.union(moc)
    candidates, _ = _tile_cells_at(coverage.moc, order)
    inputs = [(np.asarray(im.data, dtype=np.float64), im.wcs.wcs) for im in images]
    kwargs = {"order": "nearest-neighbor" if method == "nearest" else "bilinear"}
    bunits = {im.bunit for im in images}
    bunit = next(iter(bunits)) if len(bunits) == 1 else None
    if len(bunits) > 1:
        notes.append(("HIPS_UNIT_MIXED", f"unità diverse tra le immagini ({sorted(map(str, bunits))}): BUNIT non "
                      "scritto"))
    root.mkdir(parents=True, exist_ok=True)
    written: dict[int, list[int]] = {order: []}
    for index in candidates:
        wcs_out = _tile_wcs(order, int(index), tile_width, "equatorial")
        total = np.zeros((tile_width, tile_width))
        weight = np.zeros((tile_width, tile_width))
        for data, wcs_in in inputs:
            array, footprint = reproject_interp((data, wcs_in), wcs_out, shape_out=(tile_width, tile_width), **kwargs)
            valid = np.isfinite(array) & (footprint > 0)
            total[valid] += array[valid] * footprint[valid]
            weight[valid] += footprint[valid]
        if not np.any(weight > 0):
            continue
        with np.errstate(invalid="ignore", divide="ignore"):
            tile = np.where(weight > 0, total / weight, np.nan)
        _write_fits_tile(root / tile_path(order, int(index), "fits"), tile, bunit)
        written[order].append(int(index))
    if not written[order]:
        raise HiPSError("HIPS_EMPTY", "nessun pixel valido ricampionato: nessun tile scritto")
    half = tile_width // 2
    for level in range(order - 1, -1, -1):
        parents = sorted({i >> 2 for i in written[level + 1]})
        written[level] = []
        for parent in parents:
            tile = np.full((tile_width, tile_width), np.nan)
            for q in range(4):
                child = root / tile_path(level + 1, 4 * parent + q, "fits")
                if child.exists():
                    data = fits.getdata(child)
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)  # blocchi tutti NaN: restano NaN
                        tile[_quadrant(q, half)] = block_reduce(data, 2, func=np.nanmean)
            _write_fits_tile(root / tile_path(level, parent, "fits"), tile, bunit)
            written[level].append(parent)
    if formats:
        for level, indices in written.items():
            for index in indices:
                data = fits.getdata(root / tile_path(level, index, "fits"))
                rgba = set_display(data, vmin, vmax, stretch=stretch).rgba[::-1]  # righe dall'alto (§4.2.1.3)
                for fmt in formats:
                    image = Image.fromarray(rgba, "RGBA") if fmt == "png" else \
                        Image.fromarray(np.ascontiguousarray(rgba[:, :, :3]), "RGB")
                    image.save(root / tile_path(level, index, _EXTENSIONS[fmt]),
                               format="PNG" if fmt == "png" else "JPEG")
    write_moc(coverage, root / "Moc.fits")
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")
    tile_formats = ("fits",) + formats
    props = {
        "creator_did": f"ivo://{hips_id}", "obs_title": title.strip(), "dataproduct_type": "image",
        "hips_version": HIPS_STANDARD_VERSION, "hips_release_date": now, "hips_creation_date": now,
        "hips_status": status, "hips_tile_format": " ".join(tile_formats), "hips_order": str(order),
        "hips_frame": "equatorial", "hips_tile_width": str(tile_width), "hips_pixel_bitpix": "-64",
        "hips_builder": f"AstroTwo {astrotwo.__version__}", "hips_sampling": method, "hips_overlay": "mean",
        "hips_hierarchy": "mean", "moc_sky_fraction": repr(float(coverage.sky_fraction)),
        "hips_order_min": "0",
    }
    if formats:
        props["hips_pixel_cut"] = f"{vmin!r} {vmax!r}"
    lines = [f"# HiPS generato da AstroTwo {astrotwo.__version__} secondo lo standard IVOA HiPS 1.0",
             f"# sorgenti: {', '.join(im.origin for im in images)}"]
    lines += [f"{key:20} = {value}" for key, value in props.items()]
    (root / "properties").write_text("\n".join(lines) + "\n", encoding="utf-8")
    counts = {level: len(indices) for level, indices in sorted(written.items())}
    notes.append(("HIPS_ALLSKY_NOT_WRITTEN", "file Allsky non scritto (facoltativo nello standard; D12-8)"))
    description = (f"HiPS {hips_id} in {root}: {len(images)} immagini, ordine 0–{order}, tile {tile_width}×"
                   f"{tile_width} ({sum(counts.values())} tile FITS float64" + (f" + {', '.join(formats)}" if formats
                                                                               else "") +
                   f"), ricampionamento reproject_interp {method}, media pesata con la copertura, ordini inferiori per "
                   f"media di 4 pixel, Moc.fits all'ordine {order} (frazione di cielo {props['moc_sky_fraction']})")
    return BuildResult(path=root, order=order, tile_width=tile_width, tiles_per_order=counts, formats=tile_formats,
                       coverage=coverage, properties=props, description=description, warnings=tuple(notes))
