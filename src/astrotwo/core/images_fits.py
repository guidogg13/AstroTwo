"""Immagini FITS: lettura, gestione e visualizzazione.

Specifica: ``mdfiles/11-core-immagini-fits.md`` (stato ``approvato``).

Il modulo si scrive in 7 parti (decisione del proprietario del 2026-10-10):
P1 lettura FITS e HDU (questa), P2 JPEG/PNG/GIF e FITS RGB, P3 rete e cache,
P4 visualizzazione, P5 taglio/operazioni/contorni, P6 immagini grandi, P7
ricampionamento/RGB/mosaico. C'è già il centroide per la calibrazione
astrometrica (``star_centroid``, H6; D10-8 e D11-7).

Coordinate pixel in convenzione numpy (origine 0, ``array[y, x]``), come da
DC7 di ``02-convenzioni.md``; calcoli in ``float64`` (DC6).
"""

from __future__ import annotations

import dataclasses
import gzip
import math
import os
import re
import tempfile
import warnings
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import astropy
import astropy.units as u
import contourpy
import matplotlib
import numpy as np
import scipy
from astropy.convolution import Kernel2D
from astropy.convolution import convolve as astropy_convolve
from astropy.io import fits
from astropy.nddata import Cutout2D, NoOverlapError
from astropy.stats import sigma_clipped_stats
from astropy.visualization import (
    AsinhStretch,
    HistEqStretch,
    LinearStretch,
    LogStretch,
    ManualInterval,
    PowerStretch,
    SqrtStretch,
    SquaredStretch,
)
from astropy.wcs import WCS, FITSFixedWarning
from astropy.wcs.utils import proj_plane_pixel_scales
import PIL
import reproject as reproject_lib
import requests
from PIL import Image, UnidentifiedImageError
from reproject import reproject_exact, reproject_interp
from reproject.mosaicking import reproject_and_coadd
from scipy import ndimage

from astrotwo.core.cache import NETWORK_TIMEOUTS, CacheError, NetworkTimeouts, SharedCache
from astrotwo.core.coordinates_wcs import (
    CoordinatesWcsError,
    PixelPosition,
    SkyFrame,
    WcsSolution,
    convert_pixel_convention,
    pixel_to_sky,
    wcs_from_header,
)

__all__ = [
    "PALETTES",
    "STRETCHES",
    "SUPPORTED_FORMATS",
    "DisplayPlane",
    "OPERATIONS",
    "LargeImageLimits",
    "RESAMPLING_METHODS",
    "Resampled",
    "RgbComposite",
    "mosaic",
    "reproject",
    "resample_to_reference",
    "rgb_composite",
    "open_large_image",
    "Contours",
    "contours",
    "cutout",
    "image_operation",
    "save_fits",
    "blend",
    "set_display",
    "FitsImage",
    "HduInfo",
    "ImagesFitsError",
    "PixelScaling",
    "StarCentroid",
    "detect_format",
    "list_image_hdus",
    "load_image",
    "pixel_scaling",
    "star_centroid",
]

# Parametri di sigma_clipped_stats: i default della libreria (D11-7), resi
# espliciti perché siano scritti nel risultato.
_CLIP_SIGMA = 3.0
_CLIP_MAXITERS = 5

_PROVENANCE = (
    f"astropy {astropy.__version__} (sigma_clipped_stats), scipy {scipy.__version__} (ndimage.center_of_mass)"
)


class ImagesFitsError(Exception):
    """Errore del modulo 11 con identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


# --------------------------------------------------------------------------
# P1 — Lettura FITS e HDU
# --------------------------------------------------------------------------

#: Formati riconosciuti dal contenuto (H22).
SUPPORTED_FORMATS: tuple[str, ...] = ("fits", "fits-gzip", "fits-compressed", "jpeg", "png", "gif")

_FITS_SIGNATURE = b"SIMPLE  ="
_GZIP_SIGNATURE = b"\x1f\x8b"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_GIF_SIGNATURES = (b"GIF87a", b"GIF89a")
_FITS_PROVENANCE = f"astropy {astropy.__version__} (astropy.io.fits)"


@dataclass(frozen=True)
class HduInfo:
    """HDU immagine di un file FITS (per la scelta dell'utente, D11-4)."""

    index: int
    name: str
    shape: tuple[int, int]  # (righe, colonne) dopo aver tolto gli assi di lunghezza 1
    compression: str | None


@dataclass(frozen=True)
class PixelScaling:
    """Costanti dei pixel dell'intestazione originale (per il modulo 18)."""

    bzero: float | None
    bscale: float | None
    blank: int | None
    bunit: str | None


@dataclass(frozen=True)
class LargeImageLimits:
    """Soglie delle strategie per dimensione (A10 per le immagini, decisa il 2026-10-10).

    In byte (1 GB = 10⁹ byte) e in pixel; configurabili e scritte nel risultato.
    """

    memory_bytes: int = 1_000_000_000
    two_level_bytes: int = 4_000_000_000
    compressed_bytes: int = 1_000_000_000
    preview_max_side: int = 4096

    def __post_init__(self) -> None:
        if min(self.memory_bytes, self.two_level_bytes, self.compressed_bytes, self.preview_max_side) <= 0:
            raise ValueError("le soglie devono essere positive")
        if self.two_level_bytes < self.memory_bytes:
            raise ValueError("two_level_bytes non può essere minore di memory_bytes")


@dataclass(frozen=True, eq=False)
class FitsImage:
    """Immagine con dati, intestazione originale, WCS, unità e provenienza.

    ``data`` contiene i valori fisici nel tipo prodotto da ``astropy.io.fits``
    (tipo nativo del file, D11-1); ``header`` è l'intestazione originale,
    letta prima che la libreria applicasse ``BZERO``/``BSCALE``.
    """

    data: np.ndarray
    header: fits.Header
    wcs: WcsSolution | None
    bunit: str | None
    unit: u.UnitBase | None
    source: str
    origin: str
    retrieved_at: datetime
    file_modified: datetime | None
    format: str
    hdu_index: int
    hdu_name: str
    compression: str | None = None
    dropped_axes: tuple[int, ...] = ()  # assi FITS (da 1) di lunghezza 1 tolti
    warnings: tuple[tuple[str, str], ...] = ()
    color: bool = False  # True: data è 3 × righe × colonne (R, G, B), solo presentazione
    frames: int | None = None  # fotogrammi del file (GIF animate)
    calibration_source: str | None = None  # "comment" o "hhh" per JPEG/PNG
    from_cache: bool = False  # True: copia servita dalla cache comune (04), con origine e data del download
    history: tuple[str, ...] = ()  # operazioni applicate (taglio, H5), per la riproducibilità
    strategy: str = "memory"  # "memory", "memmap" o "two_level" (H27, A10)
    strategy_reason: str | None = None
    limits: LargeImageLimits | None = None
    preview_step: int | None = None  # due livelli: data è l'anteprima a questo passo
    full_shape: tuple[int, int] | None = None  # due livelli: (righe, colonne) dell'originale
    raw_ndim: int = 2  # numero di assi della HDU nel file (per la lettura per regione)
    provenance: str = field(default=_FITS_PROVENANCE)

    @property
    def shape(self) -> tuple[int, int]:
        """(righe, colonne) dell'immagine originale; per le immagini a colori, di un piano."""
        if self.full_shape is not None:
            return self.full_shape
        return tuple(self.data.shape[-2:])  # type: ignore[return-value]

    @property
    def is_preview(self) -> bool:
        """True se ``data`` è l'anteprima a bassa risoluzione (due livelli): mai per le misure."""
        return self.strategy == "two_level"

    @property
    def memory_bytes(self) -> int:
        """Byte dei dati tenuti in RAM (0 per il ``memmap``: letti dal disco su richiesta)."""
        return 0 if self.strategy == "memmap" else int(self.data.nbytes)

    def read_region(self, x0: int, x1: int, y0: int, y1: int) -> np.ndarray:
        """Pixel originali della regione ``[y0:y1, x0:x1]`` (convenzione numpy).

        Con i due livelli si leggono dal file con ``section`` di ``astropy.io.fits``.
        """
        if self.color:
            raise ImagesFitsError("OPERATION_UNSUPPORTED", "read_region: immagine a colori, solo presentazione")
        ny, nx = self.shape
        bounds = [int(v) for v in (x0, x1, y0, y1)]
        if not (0 <= bounds[0] < bounds[1] <= nx and 0 <= bounds[2] < bounds[3] <= ny):
            raise ImagesFitsError(
                "CUTOUT_OUT_OF_RANGE", f"regione x {x0}:{x1}, y {y0}:{y1} fuori dall'immagine {nx}×{ny}"
            )
        x0, x1, y0, y1 = bounds
        if not self.is_preview:
            return np.array(self.data[y0:y1, x0:x1])
        with fits.open(self.origin, memmap=False) as hdul:
            region = np.array(hdul[self.hdu_index].section[_section_key(self.raw_ndim, self.dropped_axes, slice(y0, y1), slice(x0, x1))])
        return region.astype(region.dtype.newbyteorder("=")) if not region.dtype.isnative else region

    @property
    def has_wcs(self) -> bool:
        return self.wcs is not None

    def header_value(self, key: str, default=None):
        """Valore di una parola chiave dell'intestazione originale."""
        return self.header.get(key, default)

    def cutout(self, center, size) -> FitsImage:
        """Taglio con WCS coerente (vedi :func:`cutout`)."""
        return cutout(self, center, size)

    def with_operation(self, op: str, operand=None) -> FitsImage:
        """Copia con un'operazione H5 (vedi :func:`image_operation`)."""
        return image_operation(self, operand, op)

    def field_of_view(self) -> tuple[u.Quantity, u.Quantity] | None:
        """Larghezza e altezza angolari tra i bordi opposti, ai punti medi (modulo 10).

        ``None`` se l'immagine non ha WCS: il campo non si indovina.
        """
        if self.wcs is None:
            return None
        ny, nx = self.shape
        cx, cy = (nx - 1) / 2.0, (ny - 1) / 2.0
        xs = np.array([-0.5, nx - 0.5, cx, cx])
        ys = np.array([cy, cy, -0.5, ny - 0.5])
        coords = pixel_to_sky(self.wcs, xs, ys, convention="numpy").coords.coord
        return coords[0].separation(coords[1]).to(u.deg), coords[2].separation(coords[3]).to(u.deg)


def _read_head(source) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source[:2880])
    try:
        with open(source, "rb") as handle:
            return handle.read(2880)
    except OSError as exc:
        raise ImagesFitsError("FITS_UNREADABLE", f"file non leggibile: {source} ({exc})", path=str(source)) from exc


def _has_compressed_hdu(source) -> bool:
    with fits.open(source) as hdul:
        return any(isinstance(h, fits.CompImageHDU) for h in hdul)


def detect_format(source) -> str:
    """Riconosce il formato dal contenuto (firma del file), mai dall'estensione."""
    head = _read_head(source)
    if head.startswith(_GZIP_SIGNATURE):
        try:
            if isinstance(source, (bytes, bytearray)):
                inner = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(head)
            else:
                with gzip.open(source) as handle:
                    inner = handle.read(len(_FITS_SIGNATURE))
        except (OSError, EOFError, zlib.error) as exc:
            raise ImagesFitsError("FORMAT_UNSUPPORTED", f"file gzip non leggibile: {exc}") from exc
        if inner.startswith(_FITS_SIGNATURE):
            return "fits-gzip"
    elif head.startswith(_FITS_SIGNATURE):
        if not isinstance(source, (bytes, bytearray)):
            try:
                if _has_compressed_hdu(source):
                    return "fits-compressed"
            except Exception as exc:
                raise ImagesFitsError("FITS_UNREADABLE", f"FITS non leggibile: {source} ({exc})") from exc
        return "fits"
    elif head.startswith(_PNG_SIGNATURE):
        return "png"
    elif head.startswith(_JPEG_SIGNATURE):
        return "jpeg"
    elif head.startswith(_GIF_SIGNATURES):
        return "gif"
    raise ImagesFitsError(
        "FORMAT_UNSUPPORTED", f"formato non riconosciuto; formati supportati: {', '.join(SUPPORTED_FORMATS)}"
    )


def _useful_shape(hdu) -> tuple[int, ...]:
    shape = hdu.shape if hdu.header.get("NAXIS", 0) else ()
    return tuple(n for n in shape if n > 1)


def _is_image_hdu(hdu) -> bool:
    return isinstance(hdu, (fits.PrimaryHDU, fits.ImageHDU, fits.CompImageHDU)) and bool(hdu.header.get("NAXIS", 0))


def _compression(hdu) -> str | None:
    if isinstance(hdu, fits.CompImageHDU):
        return str(hdu.compression_type)
    return None


def _open_fits(path: str):
    try:
        return fits.open(path, memmap=False)
    except FileNotFoundError as exc:
        raise ImagesFitsError("FITS_UNREADABLE", f"file inesistente: {path}", path=path) from exc
    except Exception as exc:
        raise ImagesFitsError("FITS_UNREADABLE", f"FITS non leggibile: {path} ({exc})", path=path) from exc


def _image_hdus(hdul) -> tuple[list[HduInfo], list[int]]:
    images, cubes = [], []
    for index, hdu in enumerate(hdul):
        if not _is_image_hdu(hdu):
            continue
        useful = _useful_shape(hdu)
        if len(useful) == 2:
            images.append(HduInfo(index=index, name=hdu.name, shape=useful, compression=_compression(hdu)))
        elif len(useful) > 2:
            cubes.append(index)
    return images, cubes


def list_image_hdus(source) -> tuple[HduInfo, ...]:
    """Elenco delle HDU immagine (2 assi di lunghezza > 1) del file."""
    path = os.fspath(source)
    with _open_fits(path) as hdul:
        images, _ = _image_hdus(hdul)
    return tuple(images)


def _rgb_hdus(hdul) -> list[int]:
    out = []
    for index, h in enumerate(hdul):
        if _is_image_hdu(h):
            shape = tuple(n for n in h.shape if n > 1)
            if len(shape) == 3 and shape[0] == 3:
                out.append(index)
    return out


def _select_rgb_hdu(hdul, hdu, path: str) -> int:
    candidates = _rgb_hdus(hdul)
    if hdu is None:
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise ImagesFitsError("RGB_INPUT_INVALID", f"{path}: nessuna HDU con 3 piani per rgb=True")
        raise ImagesFitsError(
            "HDU_CHOICE_REQUIRED", f"{path}: {len(candidates)} HDU con 3 piani, indicare quale", hdus=candidates
        )
    try:
        index = hdul.index_of(hdu)
    except (KeyError, IndexError) as exc:
        raise ImagesFitsError("HDU_NOT_IMAGE", f"HDU {hdu!r} inesistente") from exc
    if index not in candidates:
        raise ImagesFitsError("RGB_INPUT_INVALID", f"HDU {hdu!r}: rgb=True richiede esattamente 3 piani")
    return index


def _select_hdu(hdul, hdu, path: str) -> int:
    images, cubes = _image_hdus(hdul)
    listing = [(h.index, h.name, h.shape) for h in images]
    if hdu is None:
        if len(images) == 1:
            return images[0].index
        if not images:
            if cubes:
                raise ImagesFitsError(
                    "CUBE_NOT_SUPPORTED", f"{path}: solo cubi (3 o più assi utili): vanno al modulo 23", hdus=cubes
                )
            raise ImagesFitsError("HDU_NOT_IMAGE", f"{path}: nessuna HDU immagine", hdus=listing)
        raise ImagesFitsError(
            "HDU_CHOICE_REQUIRED", f"{path}: {len(images)} HDU immagine, indicare quale aprire: {listing}", hdus=listing
        )
    try:
        index = hdul.index_of(hdu)
    except (KeyError, IndexError) as exc:
        raise ImagesFitsError("HDU_NOT_IMAGE", f"HDU {hdu!r} inesistente; HDU immagine: {listing}", hdus=listing) from exc
    if index in cubes:
        raise ImagesFitsError("CUBE_NOT_SUPPORTED", f"HDU {hdu!r}: cubo (3 o più assi utili), modulo 23")
    if index not in {h.index for h in images}:
        raise ImagesFitsError("HDU_NOT_IMAGE", f"HDU {hdu!r} non è un'immagine; HDU immagine: {listing}", hdus=listing)
    return index


def _image_wcs(header: fits.Header, kept_fits_axes: set[int]) -> tuple[WcsSolution | None, list[tuple[str, str]]]:
    try:
        solution = wcs_from_header(header)
    except CoordinatesWcsError as exc:
        return None, [(exc.code, exc.message)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        full = WCS(header)
    celestial_axes = {full.wcs.lng + 1, full.wcs.lat + 1}
    if celestial_axes != kept_fits_axes:
        return None, [("WCS_MISSING", f"gli assi celesti {sorted(celestial_axes)} non sono i due assi utili {sorted(kept_fits_axes)}")]
    return solution, []


def _parse_unit(bunit: str | None) -> u.UnitBase | None:
    if not bunit:
        return None
    unit = u.Unit(bunit, format="fits", parse_strict="silent")
    return None if isinstance(unit, u.UnrecognizedUnit) else unit


def load_image(
    source,
    hdu=None,
    rgb: bool = False,
    *,
    cache: SharedCache | None = None,
    refresh: bool = False,
    timeouts: NetworkTimeouts = NETWORK_TIMEOUTS,
) -> FitsImage:
    """Carica un'immagine e ne dichiara origine e data.

    Con più HDU immagine serve ``hdu`` (indice o nome), altrimenti
    ``HDU_CHOICE_REQUIRED`` (D11-4); ``rgb=True`` legge una HDU di 3 piani come
    FITS RGB; JPEG/PNG/GIF si leggono con ``Pillow`` (P2). Gli URL seguono la
    politica "prima la cache" con la cache comune di ``04-cache.md`` (P3).
    """
    text = os.fspath(source) if not isinstance(source, str) else source
    if text.startswith(("http://", "https://")):
        return _load_url(text, hdu, rgb, cache, refresh, timeouts)
    path = str(Path(text).expanduser().resolve())
    return _load_path(text, path, hdu, rgb, allow_hhh=True)


def _section_key(raw_ndim: int, dropped: tuple[int, ...], rows, cols) -> tuple:
    """Chiave per ``section``: 0 sugli assi FITS di lunghezza 1, ``rows``/``cols`` sugli altri."""
    key, spatial = [], [rows, cols]
    for k in range(raw_ndim):
        key.append(0 if (raw_ndim - k) in dropped else spatial.pop(0))
    return tuple(key)


def _choose_strategy(header: fits.Header, raw_shape: tuple[int, ...], compressed: bool, limits: LargeImageLimits):
    """Strategia per dimensione (§3): (strategia, motivo, byte dei dati decompressi)."""
    nbytes = int(np.prod(raw_shape, dtype=np.int64)) * abs(int(header.get("BITPIX", 8))) // 8
    if compressed:
        if nbytes <= limits.compressed_bytes:
            return "memory", None, nbytes
        return "two_level", f"file compresso di {nbytes} byte decompressi, oltre {limits.compressed_bytes}", nbytes
    if nbytes <= limits.memory_bytes:
        return "memory", None, nbytes
    if nbytes <= limits.two_level_bytes:
        scaled = [k for k in ("BZERO", "BSCALE", "BLANK") if k in header]
        if scaled:
            return "two_level", f"{nbytes} byte: memmap impossibile con {', '.join(scaled)} (astropy.io.fits)", nbytes
        return "memmap", f"{nbytes} byte, oltre {limits.memory_bytes}: letti dal disco su richiesta", nbytes
    return "two_level", f"{nbytes} byte, oltre {limits.two_level_bytes}", nbytes


def _load_path(text: str, path: str, hdu, rgb: bool, allow_hhh: bool, limits: LargeImageLimits | None = None) -> FitsImage:
    fmt = detect_format(path)
    if fmt in ("jpeg", "png", "gif"):
        return _load_raster(text, path, fmt, allow_hhh=allow_hhh)
    limits = LargeImageLimits() if limits is None else limits
    retrieved_at = datetime.now(UTC)
    preview_step = None
    with _open_fits(path) as hdul:
        index = _select_rgb_hdu(hdul, hdu, path) if rgb else _select_hdu(hdul, hdu, path)
        chosen = hdul[index]
        header = chosen.header.copy()  # prima di leggere i dati: BZERO/BSCALE originali
        compression = _compression(chosen)
        raw_shape = tuple(chosen.shape)
        name = chosen.name
        if rgb:
            strategy, reason = "memory", None
        else:
            strategy, reason, _ = _choose_strategy(header, raw_shape, compression is not None or fmt == "fits-gzip", limits)
        dropped = tuple(len(raw_shape) - k for k, n in enumerate(raw_shape) if n == 1)
        useful = tuple(n for n in raw_shape if n > 1)
        try:
            if strategy == "memory":
                data = np.array(chosen.data)
            elif strategy == "two_level":
                preview_step = max(1, math.ceil(max(useful) / limits.preview_max_side))
                step = slice(None, None, preview_step)
                data = np.array(chosen.section[_section_key(len(raw_shape), dropped, step, step)])
        except Exception as exc:
            if compression is not None:
                raise ImagesFitsError(
                    "COMPRESSION_UNSUPPORTED", f"{path}: compressione {compression} non leggibile ({exc})"
                ) from exc
            raise ImagesFitsError("FITS_UNREADABLE", f"{path}: dati non leggibili ({exc})", path=path) from exc
    if strategy == "memmap":
        with fits.open(path, memmap=True) as mapped:
            data = mapped[index].data  # resta mappata dopo la chiusura del file
    kept = {len(raw_shape) - k for k, n in enumerate(raw_shape) if n > 1}
    if strategy != "two_level":
        data = data.reshape(useful)
    if not data.dtype.isnative and strategy != "memmap":
        # Stesso tipo e stessi valori, nell'ordine di byte della macchina
        # (FITS è big-endian): evita conversioni lente nelle librerie. Il
        # memmap resta nell'ordine del file per non copiare i dati.
        data = data.astype(data.dtype.newbyteorder("="))
    notes: list[tuple[str, str]] = []
    if strategy != "memory":
        notes.append(("STRATEGY", f"{strategy}: {reason}"))
    if dropped:
        notes.append(("AXES_DROPPED", f"assi FITS di lunghezza 1 tolti: {sorted(dropped)}"))
    if rgb:
        kept = {1, 2}  # i due assi spaziali; il terzo sono i piani R, G, B
    solution, wcs_notes = _image_wcs(header, kept)
    notes.extend(wcs_notes)
    if strategy != "memmap" and np.issubdtype(data.dtype, np.floating) and not np.all(np.isfinite(data)):
        notes.append(("NONFINITE_PIXELS", "pixel non finiti (NaN/inf): esclusi da display e misure, mai sostituiti"))
    bunit = header.get("BUNIT")
    modified = datetime.fromtimestamp(os.path.getmtime(path), tz=UTC)
    return FitsImage(
        data=data,
        header=header,
        wcs=solution,
        bunit=bunit,
        unit=_parse_unit(bunit),
        source=text,
        origin=path,
        retrieved_at=retrieved_at,
        file_modified=modified,
        format=fmt,
        hdu_index=index,
        hdu_name=name,
        compression=compression,
        dropped_axes=dropped,
        warnings=tuple(notes),
        color=rgb,
        strategy=strategy,
        strategy_reason=reason,
        limits=limits,
        preview_step=preview_step,
        full_shape=useful if strategy == "two_level" else None,
        raw_ndim=len(raw_shape),
    )


def open_large_image(source, hdu=None, limits: LargeImageLimits | None = None) -> FitsImage:
    """Apre un'immagine FITS locale con la strategia per dimensione (H27, A10)."""
    text = os.fspath(source) if not isinstance(source, str) else source
    if text.startswith(("http://", "https://")):
        raise ValueError("open_large_image lavora sui file locali; per gli URL usare load_image")
    path = str(Path(text).expanduser().resolve())
    if detect_format(path) in ("jpeg", "png", "gif"):
        return _load_raster(text, path, detect_format(path))
    return _load_path(text, path, hdu, False, True, LargeImageLimits() if limits is None else limits)


# --------------------------------------------------------------------------
# P2 — JPEG, PNG, GIF e calibrazione nel commento o nel file .hhh
# --------------------------------------------------------------------------


def _header_from_text(text: str) -> fits.Header | None:
    """Intestazione FITS scritta come testo: schede da 80 caratteri attaccate o
    separate da a capo (standard FITS 4.0, ``Header.fromstring``)."""
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text.strip():
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if "\n" in text:
                return fits.Header.fromstring(text, sep="\n")
            return fits.Header.fromstring(text)
    except Exception:
        return None


def _comment_text(image, fmt: str) -> str | None:
    if fmt == "jpeg":
        value = image.info.get("comment")  # segmento COM
    elif fmt == "png":
        value = image.info.get("Comment")  # blocco di testo con la parola chiave "Comment"
    else:
        return None
    if value is None:
        return None
    return value.decode("latin-1") if isinstance(value, bytes) else str(value)


def _raster_array(image) -> tuple[np.ndarray, bool, list[tuple[str, str]]]:
    """Array dal file (righe dall'alto) secondo i modi di colore di §3."""
    notes: list[tuple[str, str]] = []
    mode = image.mode
    if mode in ("RGBA", "LA", "PA") or (mode == "P" and "transparency" in image.info):
        notes.append(("ALPHA_DROPPED", f"canale alfa del modo {mode} scartato"))
    if mode == "1":
        return np.array(image, dtype=np.uint8), False, notes
    if mode in ("L", "I", "F") or mode.startswith("I;16"):
        return np.array(image), False, notes
    if mode == "LA":
        return np.array(image.convert("L")), False, notes
    rgb = np.array(image.convert("RGB"))
    if mode in ("P", "PA") and np.array_equal(rgb[..., 0], rgb[..., 1]) and np.array_equal(rgb[..., 1], rgb[..., 2]):
        return np.array(image.convert("L")), False, notes
    return rgb, True, notes


def _raster_calibration(header: fits.Header, source_kind: str, nx: int, ny: int) -> tuple[WcsSolution | None, list[tuple[str, str]]]:
    """WCS dal testo del commento o del ``.hhh``, o ``None`` con il motivo dello scarto."""
    if not header:
        return None, [("WCS_MISSING", f"calibrazione ({source_kind}) scartata: non è un'intestazione FITS valida")]
    if (header.get("NAXIS1"), header.get("NAXIS2")) != (nx, ny):
        return None, [(
            "WCS_MISSING",
            f"calibrazione ({source_kind}) scartata: NAXIS1/NAXIS2 = {header.get('NAXIS1')}/{header.get('NAXIS2')}, "
            f"immagine {nx}×{ny}",
        )]
    solution, wcs_notes = _image_wcs(header, {1, 2})
    if solution is None:
        return None, [(code, f"calibrazione ({source_kind}) scartata: {msg}") for code, msg in wcs_notes]
    return solution, []


def _wcs_keywords(solution: WcsSolution | None) -> dict[str, object]:
    if solution is None:
        return {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        header = solution.wcs.to_header(relax=True)
    return {key: header[key] for key in header if key not in ("COMMENT", "HISTORY", "")}


def _wcs_differences(a: WcsSolution | None, b: WcsSolution | None) -> str:
    """Differenze tra due WCS (parole chiave normalizzate da ``WCS.to_header``); stringa vuota se uguali."""
    if (a is None) != (b is None):
        return "uno solo dei due è una calibrazione valida"
    ka, kb = _wcs_keywords(a), _wcs_keywords(b)
    keys = sorted(k for k in set(ka) | set(kb) if ka.get(k) != kb.get(k))
    return ", ".join(keys)


def _load_raster(text: str, path: str, fmt: str, allow_hhh: bool = True) -> FitsImage:
    retrieved_at = datetime.now(UTC)
    try:
        with Image.open(path) as image:
            frames = getattr(image, "n_frames", 1)
            image.seek(0)
            image.load()
            raw, color, notes = _raster_array(image)
            comment = _comment_text(image, fmt)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImagesFitsError("IMAGE_UNREADABLE", f"{path}: immagine non decodificabile ({exc})", path=path) from exc
    # Righe dal basso verso l'alto, come un FITS (convenzione dei pixel, §3).
    data = raw[::-1].copy()
    if color:
        data = np.moveaxis(data, -1, 0).copy()
    ny, nx = data.shape[-2:]
    if frames > 1:
        notes.append(("FRAMES", f"{frames} fotogrammi: letto il primo"))

    header, source_kind = fits.Header(), None
    hhh = Path(path).with_suffix(".hhh")
    hhh_text = None
    if fmt in ("jpeg", "png") and allow_hhh and hhh.exists():
        try:
            hhh_text = hhh.read_text("latin-1")
        except OSError as exc:
            notes.append(("WCS_MISSING", f"{hhh.name} non leggibile: {exc}"))
    if fmt in ("jpeg", "png"):
        if comment is not None:
            header, source_kind = (_header_from_text(comment) or fits.Header()), "comment"
            if hhh_text is not None:
                notes.append(("HHH_IGNORED", f"{hhh.name} ignorato: vale la calibrazione nel commento del file"))
        elif hhh_text is not None:
            header, source_kind = (_header_from_text(hhh_text) or fits.Header()), "hhh"

    solution = None
    if source_kind is not None:
        solution, calibration_notes = _raster_calibration(header, source_kind, nx, ny)
        notes.extend(calibration_notes)
        if solution is None:
            source_kind = None
    else:
        notes.append(("WCS_MISSING", "nessuna calibrazione astrometrica: immagine come griglia di pixel"))
    if comment is not None and hhh_text is not None:
        # Vale il commento; se il .hhh ignorato descrive un WCS diverso, lo si dice (decisione del 2026-10-10).
        other, _ = _raster_calibration(_header_from_text(hhh_text) or fits.Header(), "hhh", nx, ny)
        differing = _wcs_differences(solution, other)
        if differing:
            notes.append(("HHH_WCS_DIFFERS", f"{hhh.name} descrive un WCS diverso da quello del commento (usato): {differing}"))

    return FitsImage(
        data=data,
        header=header if source_kind else fits.Header(),
        wcs=solution,
        bunit=None,
        unit=None,
        source=text,
        origin=path,
        retrieved_at=retrieved_at,
        file_modified=datetime.fromtimestamp(os.path.getmtime(path), tz=UTC),
        format=fmt,
        hdu_index=0,
        hdu_name="",
        warnings=tuple(notes),
        color=color,
        frames=frames,
        calibration_source=source_kind,
        provenance=f"Pillow {PIL.__version__}; {_FITS_PROVENANCE}",
    )


# --------------------------------------------------------------------------
# P3 — Rete e cache (prima la cache, timeout comuni di 04-cache.md)
# --------------------------------------------------------------------------

_CACHE_MODULE = "11"


def _download(url: str, timeouts: NetworkTimeouts) -> bytes:
    """Scarica tutto il contenuto o niente (nessun dato parziale)."""
    with requests.get(url, timeout=timeouts.as_requests(), stream=True) as response:
        response.raise_for_status()
        return b"".join(response.iter_content(chunk_size=1 << 16))


def _load_url(url: str, hdu, rgb: bool, cache: SharedCache | None, refresh: bool, timeouts: NetworkTimeouts) -> FitsImage:
    cache = SharedCache() if cache is None else cache
    key = f"url:{url}"
    cached = cache.get(_CACHE_MODULE, key)
    notes: list[tuple[str, str]] = []
    if cached is not None and not refresh:
        payload, retrieved_at, from_cache = cached.data, cached.retrieved_at, True
    else:
        try:
            payload = _download(url, timeouts)
        except requests.exceptions.RequestException as exc:
            if cached is None:
                raise ImagesFitsError(
                    "NET_TIMEOUT",
                    f"{url} non raggiungibile (timeout {timeouts.connect:g} s connessione, "
                    f"{timeouts.read:g} s lettura): {exc}",
                    url=url,
                ) from exc
            payload, retrieved_at, from_cache = cached.data, cached.retrieved_at, True
            notes.append(("FROM_CACHE", f"rete non disponibile ({type(exc).__name__}): copia in cache"))
        else:
            retrieved_at, from_cache = datetime.now(UTC), False
            try:
                cache.put(_CACHE_MODULE, key, payload, origin=url, retrieved_at=retrieved_at)
            except CacheError as exc:  # es. CACHE_FULL: l'immagine si apre comunque
                notes.append((exc.code, exc.message))
    if from_cache and not notes:
        notes.append(("FROM_CACHE", f"copia in cache dell'URL, scaricata il {retrieved_at.isoformat()}"))
    fd, tmp = tempfile.mkstemp(prefix="astrotwo-url-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        image = _load_path(url, tmp, hdu, rgb, allow_hhh=False)
    finally:
        os.unlink(tmp)
    return dataclasses.replace(
        image,
        origin=url,
        retrieved_at=retrieved_at,
        file_modified=None,
        from_cache=from_cache,
        warnings=tuple(notes) + image.warnings,
    )


# --------------------------------------------------------------------------
# P4 — Visualizzazione (solo presentazione: i dati non cambiano mai)
# --------------------------------------------------------------------------

_BASE_PALETTES = ("gray", "viridis", "plasma", "inferno", "magma", "cividis", "cubehelix", "afmhot", "coolwarm")
#: Palette ammesse (D11-5 corretta): tabelle di ``matplotlib``, anche invertite.
PALETTES: tuple[str, ...] = _BASE_PALETTES + tuple(f"{name}_r" for name in _BASE_PALETTES)
#: Funzioni di trasferimento ammesse (``astropy.visualization``).
STRETCHES: tuple[str, ...] = ("linear", "log", "sqrt", "squared", "asinh", "histeq")
_STRETCH_CLASSES = {
    "linear": LinearStretch,
    "log": LogStretch,
    "sqrt": SqrtStretch,
    "squared": SquaredStretch,
    "asinh": AsinhStretch,
}


@dataclass(frozen=True, eq=False)
class DisplayPlane:
    """Piano di presentazione: valori in [0, 1] (``float32``) e colori RGBA a 8 bit.

    ``values`` ha la forma dei dati (``3 × righe × colonne`` per le immagini a
    colori); ``rgba`` è ``righe × colonne × 4``; righe nello stesso ordine dei
    dati (dal basso). I pixel non finiti hanno valore NaN e alfa 0.
    """

    values: np.ndarray
    rgba: np.ndarray
    vmin: float
    vmax: float
    gamma: float
    stretch: str
    palette: str | None
    provenance: str = field(
        default=f"astropy {astropy.__version__} (astropy.visualization), matplotlib {matplotlib.__version__} (palette)"
    )


def _check_display_option(value: str, allowed: tuple[str, ...], what: str) -> str:
    if value not in allowed:
        raise ImagesFitsError("DISPLAY_OPTION_UNKNOWN", f"{what} {value!r} non ammessa; ammesse: {', '.join(allowed)}")
    return value


def _apply_stretch(normalized: np.ndarray, name: str, gamma: float) -> np.ndarray:
    finite = np.isfinite(normalized)
    if name == "histeq":
        stretch = HistEqStretch(normalized[finite])
    else:
        stretch = _STRETCH_CLASSES[name]()
    out = np.full(normalized.shape, np.nan)
    out[finite] = stretch(normalized[finite], clip=True)
    if gamma != 1.0:
        out[finite] = PowerStretch(gamma)(out[finite], clip=True)
    return out


def set_display(image, vmin: float, vmax: float, gamma: float = 1.0, palette: str = "gray", stretch: str = "linear") -> DisplayPlane:
    """Piano di presentazione con intervallo, funzione di trasferimento, gamma e palette.

    Non modifica mai ``image.data``: lavora su una copia in ``float64`` e
    restituisce valori ``float32`` e colori (D11-1, §9 separazione display/dati).
    """
    _check_display_option(stretch, STRETCHES, "funzione di trasferimento")
    color = bool(getattr(image, "color", False))
    if not color:
        _check_display_option(palette, PALETTES, "palette")
    vmin, vmax, gamma = float(vmin), float(vmax), float(gamma)
    if not (math.isfinite(vmin) and math.isfinite(vmax) and vmin < vmax):
        raise ValueError("serve vmin < vmax, entrambi finiti")
    if not (math.isfinite(gamma) and gamma > 0):
        raise ValueError("gamma deve essere positivo")
    source = getattr(image, "data", image)
    _check_memory("visualizzazione", int(np.size(source)) * _MEMORY_BYTES_PER_PIXEL["set_display"], image)
    data = np.array(source, dtype=np.float64)  # copia: l'originale non si tocca
    normalized = np.full(data.shape, np.nan)
    finite = np.isfinite(data)
    normalized[finite] = ManualInterval(vmin, vmax)(data[finite], clip=True)
    if color:
        values = np.stack([_apply_stretch(plane, stretch, gamma) for plane in normalized])
        planes = np.where(np.isfinite(values), np.round(values * 255.0), 0.0).astype(np.uint8)
        alpha = np.where(np.all(np.isfinite(values), axis=0), 255, 0).astype(np.uint8)
        rgba = np.dstack([planes[0], planes[1], planes[2], alpha])
        used_palette = None
    else:
        values = _apply_stretch(normalized, stretch, gamma)
        rgba = matplotlib.colormaps[palette](np.where(np.isfinite(values), values, 0.0), bytes=True)
        rgba[~np.isfinite(values), 3] = 0  # non finiti trasparenti, mai un valore inventato
        used_palette = palette
    return DisplayPlane(
        values=values.astype(np.float32),
        rgba=rgba,
        vmin=vmin,
        vmax=vmax,
        gamma=gamma,
        stretch=stretch,
        palette=used_palette,
    )


def blend(planes, opacities) -> np.ndarray:
    """Compone piani RGBA della stessa griglia dal basso verso l'alto (operatore "over").

    ``planes``: array ``righe × colonne × 4`` (``uint8``) o ``DisplayPlane``;
    ``opacities``: opacità di ciascun piano in [0, 1]. Restituisce RGBA ``uint8``.
    """
    arrays = [np.asarray(getattr(plane, "rgba", plane)) for plane in planes]
    opacities = [float(a) for a in opacities]
    if not arrays or len(arrays) != len(opacities):
        raise ValueError("serve un'opacità per ciascun piano")
    if any(not (0.0 <= a <= 1.0) for a in opacities):
        raise ValueError("le opacità devono stare in [0, 1]")
    shape = arrays[0].shape
    if any(a.shape != shape or a.ndim != 3 or a.shape[2] != 4 for a in arrays):
        raise ImagesFitsError(
            "IMAGE_SHAPE_MISMATCH", f"piani di griglie diverse: {[a.shape for a in arrays]}; ricampionare prima (P7)"
        )
    color = np.zeros(shape[:2] + (3,))  # colore premoltiplicato per l'alfa
    alpha = np.zeros(shape[:2])
    for array, opacity in zip(arrays, opacities, strict=True):
        a = opacity * array[..., 3].astype(np.float64) / 255.0
        color = a[..., None] * (array[..., :3].astype(np.float64) / 255.0) + (1.0 - a[..., None]) * color
        alpha = a + (1.0 - a) * alpha
    rgb = np.divide(color, alpha[..., None], out=np.zeros_like(color), where=alpha[..., None] > 0)
    return np.dstack([np.round(rgb * 255.0), np.round(alpha * 255.0)]).astype(np.uint8)


# --------------------------------------------------------------------------
# P5 — Taglio, operazioni H5, contorni, salvataggio FITS
# --------------------------------------------------------------------------

#: Elenco chiuso delle operazioni H5 (§3).
OPERATIONS: tuple[str, ...] = ("add", "sub", "mul", "div", "convolve", "normalize", "flip_x", "flip_y")
_ARITHMETIC = {"add": np.add, "sub": np.subtract, "mul": np.multiply, "div": np.divide}
_WCS_KEY = re.compile(
    r"^(WCSAXES|CTYPE\d|CRPIX\d|CRVAL\d|CDELT\d|CUNIT\d|CROTA\d|CD\d_\d|PC\d_\d|PV\d_\d+|PS\d_\d+"
    r"|LONPOLE|LATPOLE|RADESYS|RADECSYS|EQUINOX|[AB]P?_\d+_\d+|[AB]P?_ORDER)$"
)


def _header_with_wcs(header: fits.Header, wcs: WCS | None, shape: tuple[int, ...]) -> fits.Header:
    """Intestazione con le parole chiave WCS sostituite e le dimensioni aggiornate."""
    out = fits.Header([card for card in header.cards if not _WCS_KEY.match(card.keyword)])
    for key in ("BZERO", "BSCALE", "BLANK"):
        out.remove(key, ignore_missing=True, remove_all=True)  # i dati sono già valori fisici
    out["NAXIS"] = len(shape)
    for k, n in enumerate(reversed(shape), start=1):
        out[f"NAXIS{k}"] = n
    if wcs is not None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            out.update(wcs.to_header(relax=True))
    return out


def _derived(image: FitsImage, data: np.ndarray, wcs: WCS | None, step: str, notes=(), bunit=...) -> FitsImage:
    solution = None
    if wcs is not None and image.wcs is not None:
        solution = dataclasses.replace(image.wcs, wcs=wcs, pixel_shape=(data.shape[-1], data.shape[-2]))
    new_bunit = image.bunit if bunit is ... else bunit
    header = _header_with_wcs(image.header, wcs, data.shape)
    if new_bunit:
        header["BUNIT"] = new_bunit
    else:
        header.remove("BUNIT", ignore_missing=True)
    return dataclasses.replace(
        image,
        data=data,
        header=header,
        wcs=solution,
        bunit=new_bunit,
        unit=_parse_unit(new_bunit),
        compression=None,
        warnings=image.warnings + tuple(notes),
        history=image.history + (step,),
        strategy="memory",
        strategy_reason=None,
        preview_step=None,
        full_shape=None,
        raw_ndim=data.ndim,
        dropped_axes=(),
    )


def _refuse_preview(image: FitsImage, what: str) -> None:
    if getattr(image, "is_preview", False):
        raise ImagesFitsError(
            "PREVIEW_NOT_MEASURABLE",
            f"{what}: l'immagine è aperta a due livelli e i dati in memoria sono solo l'anteprima "
            f"(passo {image.preview_step}); usare read_region o un taglio sui pixel originali",
        )


#: Byte per pixel stimati per le operazioni sull'immagine intera (§3): array
#: ``float64`` presenti insieme (operandi, risultato, copie di lavoro) × 8 byte.
_FLOAT64 = 8
_MEMORY_BYTES_PER_PIXEL = {
    "image_operation_image": 3 * _FLOAT64,  # a, b, risultato
    "image_operation": 2 * _FLOAT64,  # a, risultato (costante, normalizzazione, specchiature)
    "convolve": 3 * _FLOAT64,  # a, risultato, copia di lavoro di astropy.convolution
    "contours": 2 * _FLOAT64,  # copia float64 con maschera, strutture di contourpy
    "set_display": 4 * _FLOAT64,  # per piano: copia, intervallo, funzione di trasferimento, valori e colori
}


def _pixels(shape) -> int:
    return int(np.prod(shape, dtype=np.int64))


def _check_memory(what: str, needed: int, *images) -> None:
    """Rifiuta l'operazione se la memoria stimata supera il tetto A10 (``memory_bytes``).

    Il tetto è il più piccolo tra quelli delle immagini coinvolte (default se assente).
    """
    caps = [im.limits.memory_bytes for im in images if getattr(im, "limits", None) is not None]
    cap = min(caps) if caps else LargeImageLimits().memory_bytes
    if needed > cap:
        raise ImagesFitsError(
            "MEMORY_LIMIT_EXCEEDED",
            f"{what}: servono circa {needed} byte, oltre il tetto di {cap} byte (A10); "
            "usare un taglio, una regione o soglie più alte",
            needed_bytes=needed,
            limit_bytes=cap,
        )


def cutout(image: FitsImage, center, size) -> FitsImage:
    """Taglio con WCS coerente (B8) con ``astropy.nddata.Cutout2D``.

    ``center``: ``SkyFrame`` (serve il WCS) o ``PixelPosition`` (convenzione
    dichiarata); ``size``: angolo (serve il WCS), pixel interi o ``(alto, largo)``.
    """
    w = image.wcs.wcs if image.wcs is not None else None
    if isinstance(center, SkyFrame):
        if w is None:
            raise ImagesFitsError("WCS_MISSING", "taglio con centro in coordinate celesti: l'immagine non ha WCS")
        position = center.coord if center.coord.isscalar else center.coord[0]
        described = f"centro {position.to_string('decimal', precision=8)} ({center.frame_name})"
    elif isinstance(center, PixelPosition):
        px = convert_pixel_convention(center.x, center.y, center.convention, "numpy")
        position = (float(px.x), float(px.y))
        described = f"centro pixel numpy ({position[0]:g}, {position[1]:g})"
    else:
        raise TypeError("center deve essere uno SkyFrame o una PixelPosition (convenzione dichiarata)")
    if isinstance(size, u.Quantity) and size.unit.is_equivalent(u.deg) and w is None:
        raise ImagesFitsError("WCS_MISSING", "lato in unità angolari: l'immagine non ha WCS")
    if image.is_preview:
        # Geometria su un array virtuale delle dimensioni dell'originale (nessuna memoria),
        # dati letti dal file per la sola regione del taglio.
        plane = np.broadcast_to(np.zeros((), dtype=image.data.dtype), image.shape)
    else:
        plane = image.data[0] if image.color else image.data
    try:
        cut = Cutout2D(plane, position, size, wcs=w, mode="trim", copy=False)  # copia dopo il controllo della memoria
    except NoOverlapError as exc:
        raise ImagesFitsError("CUTOUT_OUT_OF_RANGE", f"taglio del tutto fuori dall'immagine ({described})") from exc
    except ValueError as exc:
        raise ImagesFitsError("CUTOUT_OUT_OF_RANGE", f"taglio non valido ({described}): {exc}") from exc
    planes = 3 if image.color else 1
    _check_memory("taglio", _pixels(cut.shape) * planes * image.data.dtype.itemsize, image)
    if image.is_preview:
        rows, cols = cut.slices_original
        data = image.read_region(cols.start, cols.stop, rows.start, rows.stop)
    elif image.color:
        data = np.stack([p[cut.slices_original].copy() for p in image.data])
    else:
        data = np.array(cut.data)
    notes = []
    if tuple(cut.shape) != tuple(cut.shape_input):
        notes.append(("CUTOUT_TRIMMED", f"taglio ridotto all'intersezione con l'immagine: {cut.shape} invece di {cut.shape_input}"))
    x0, y0 = cut.origin_original
    return _derived(image, data, cut.wcs, f"cutout: {described}, origine pixel numpy ({x0}, {y0}), forma {cut.shape}", notes)


def _same_grid(a: FitsImage, b: FitsImage) -> None:
    if a.data.shape != b.data.shape:
        raise ImagesFitsError("IMAGE_SHAPE_MISMATCH", f"dimensioni diverse {a.data.shape} e {b.data.shape}: ricampionare prima (P7)")
    if (a.wcs is None) != (b.wcs is None) or (a.wcs is not None and not a.wcs.wcs.wcs.compare(b.wcs.wcs.wcs, tolerance=1e-12)):
        raise ImagesFitsError("IMAGE_SHAPE_MISMATCH", "griglie (WCS) diverse: ricampionare prima (P7)")


def _flip_wcs(w: WCS, axis_fits: int, n: int) -> WCS:
    """WCS dopo la specchiatura dell'asse FITS ``axis_fits`` (1 o 2) lungo ``n`` pixel.

    Parte lineare secondo FITS WCS (Paper I): CRPIX → n + 1 − CRPIX e segno
    cambiato della colonna della matrice CD (o PC). Con distorsioni: rifiuto.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        keys = list(w.to_header(relax=True).keys())
    wcslib_distortion = any(k.startswith(("DP", "DQ", "CPDIS", "CQDIS")) for k in keys)
    if w.has_distortion or w.sip is not None or wcslib_distortion:
        raise ImagesFitsError("OPERATION_UNSUPPORTED", "specchiatura di un WCS con distorsioni (SIP, TPD, tabelle) non supportata")
    flipped = w.deepcopy()
    k = axis_fits - 1
    crpix = flipped.wcs.crpix.copy()
    crpix[k] = n + 1 - crpix[k]
    flipped.wcs.crpix = crpix
    if flipped.wcs.has_cd():
        cd = flipped.wcs.cd.copy()
        cd[:, k] *= -1
        flipped.wcs.cd = cd
    else:
        pc = flipped.wcs.get_pc().copy()
        pc[:, k] *= -1
        flipped.wcs.pc = pc
    flipped.wcs.set()
    return flipped


def image_operation(a: FitsImage, b, op: str) -> FitsImage:
    """Operazione H5 dall'elenco chiuso; restituisce sempre una nuova immagine (``float64``)."""
    if op not in OPERATIONS:
        raise ImagesFitsError("OPERATION_UNSUPPORTED", f"operazione {op!r} non prevista; elenco: {', '.join(OPERATIONS)}")
    if a.color:
        raise ImagesFitsError("OPERATION_UNSUPPORTED", "le immagini a colori sono solo di presentazione")
    _refuse_preview(a, f"operazione {op}")
    if isinstance(b, FitsImage):
        _refuse_preview(b, f"operazione {op}")
    if op == "convolve":
        per_pixel = _MEMORY_BYTES_PER_PIXEL["convolve"]
    elif op in _ARITHMETIC and isinstance(b, FitsImage):
        per_pixel = _MEMORY_BYTES_PER_PIXEL["image_operation_image"]
    else:
        per_pixel = _MEMORY_BYTES_PER_PIXEL["image_operation"]
    _check_memory(f"operazione {op}", _pixels(a.data.shape) * per_pixel, a, *([b] if isinstance(b, FitsImage) else []))
    data = np.asarray(a.data, dtype=np.float64)
    w = a.wcs.wcs if a.wcs is not None else None
    notes: list[tuple[str, str]] = []
    bunit = ...
    if op in _ARITHMETIC:
        if isinstance(b, FitsImage):
            if b.color:
                raise ImagesFitsError("OPERATION_UNSUPPORTED", "le immagini a colori sono solo di presentazione")
            _same_grid(a, b)
            if op in ("add", "sub") and (a.bunit or None) != (b.bunit or None):
                raise ImagesFitsError("UNIT_MISMATCH", f"unità diverse: {a.bunit!r} e {b.bunit!r}")
            if op in ("mul", "div"):
                if a.unit is not None and b.unit is not None:
                    bunit = (a.unit * b.unit if op == "mul" else a.unit / b.unit).to_string("fits") or None
                else:
                    bunit = None
                    if a.bunit or b.bunit:
                        notes.append(("UNIT_UNKNOWN", f"unità del risultato non determinabile da {a.bunit!r} e {b.bunit!r}"))
            other = np.asarray(b.data, dtype=np.float64)
            step = f"{op} con l'immagine {b.origin} (HDU {b.hdu_index})"
        elif isinstance(b, (int, float, np.integer, np.floating)) and not isinstance(b, bool):
            other = float(b)
            step = f"{op} con la costante {other!r}"
        else:
            raise ImagesFitsError("OPERATION_UNSUPPORTED", f"{op}: serve un'immagine o una costante")
        with np.errstate(divide="ignore", invalid="ignore"):
            result = _ARITHMETIC[op](data, other)
    elif op == "convolve":
        if not isinstance(b, Kernel2D):
            raise ImagesFitsError("OPERATION_UNSUPPORTED", "convolve: serve un kernel di astropy.convolution (Kernel2D)")
        result = astropy_convolve(data, b)
        step = f"convolve con {type(b).__name__} {b.array.shape} (astropy, default: bordo 0, NaN interpolati, kernel normalizzato)"
    elif op == "normalize":
        if b is not None:
            raise ImagesFitsError("OPERATION_UNSUPPORTED", "normalize non ha operandi")
        mean = float(np.nanmean(data)) if np.any(np.isfinite(data)) else float("nan")
        if not math.isfinite(mean) or mean == 0.0:
            raise ImagesFitsError("OPERATION_UNSUPPORTED", f"normalizzazione non definita: media dei pixel finiti = {mean!r}")
        result = data / mean
        step = f"normalize: divisione per la media dei pixel finiti {mean!r}"
        bunit = None
    else:  # specchiature
        if b is not None:
            raise ImagesFitsError("OPERATION_UNSUPPORTED", f"{op} non ha operandi")
        axis = 1 if op == "flip_x" else 0
        result = np.flip(data, axis=axis).copy()
        if w is not None:
            w = _flip_wcs(w, axis_fits=1 if op == "flip_x" else 2, n=data.shape[axis])
        step = f"{op}: specchiatura {'orizzontale' if op == 'flip_x' else 'verticale'}, WCS aggiornato"
    if not np.all(np.isfinite(result)) and np.all(np.isfinite(data)):
        notes.append(("NONFINITE_PIXELS", f"{op}: il risultato ha pixel non finiti (es. divisione per zero)"))
    return _derived(a, result, w, step, notes, bunit=bunit)


@dataclass(frozen=True)
class Contours:
    """Isofote (H7): per ogni livello, le curve in pixel (convenzione numpy)."""

    levels: tuple[float, ...]
    bunit: str | None
    curves: tuple[tuple[np.ndarray, ...], ...]  # curves[i][j]: array (N, 2) di (x, y)
    convention: str = "numpy"
    provenance: str = field(default=f"contourpy {contourpy.__version__}")

    def to_sky(self, image: FitsImage) -> tuple[tuple[SkyFrame, ...], ...]:
        """Le stesse curve in coordinate celesti, con il WCS dell'immagine (modulo 10)."""
        if image.wcs is None:
            raise ImagesFitsError("WCS_MISSING", "contorni in coordinate celesti: l'immagine non ha WCS")
        return tuple(
            tuple(pixel_to_sky(image.wcs, c[:, 0], c[:, 1], convention="numpy").coords for c in level)
            for level in self.curves
        )


def contours(image: FitsImage, levels) -> Contours:
    """Isofote (H7) con ``contourpy``; ``levels`` nelle unità dell'immagine."""
    if image.color:
        raise ImagesFitsError("OPERATION_UNSUPPORTED", "contorni su un'immagine a colori: serve un'immagine monocroma")
    _refuse_preview(image, "contorni")
    _check_memory("contorni", _pixels(image.data.shape) * _MEMORY_BYTES_PER_PIXEL["contours"], image)
    values = tuple(float(v) for v in np.atleast_1d(levels))
    z = np.ma.masked_invalid(np.asarray(image.data, dtype=np.float64))
    generator = contourpy.contour_generator(z=z, line_type=contourpy.LineType.Separate)
    curves = tuple(tuple(np.asarray(c, dtype=np.float64) for c in generator.lines(v)) for v in values)
    return Contours(levels=values, bunit=image.bunit, curves=curves)


def save_fits(image: FitsImage, path, overwrite: bool = False) -> Path:
    """Salva l'immagine come FITS con WCS e provenienza (A2ORIGIN, A2DATE, HISTORY)."""
    _refuse_preview(image, "salvataggio FITS")
    # Dati in RAM più la copia nell'ordine di byte del FITS (big-endian) scritta da astropy.
    _check_memory("salvataggio FITS", _pixels(image.data.shape) * image.data.dtype.itemsize * 2, image)
    w = image.wcs.wcs if image.wcs is not None else None
    header = _header_with_wcs(image.header, w, image.data.shape)
    header["A2ORIGIN"] = (str(image.origin), "origine")  # valori lunghi: convenzione CONTINUE (FITS 4.0)
    header["A2DATE"] = (image.retrieved_at.astimezone(UTC).isoformat().replace("+00:00", "Z"), "data UTC")
    header.add_history(f"AstroTwo: origine {image.origin}")
    for step in image.history:
        header.add_history(f"AstroTwo: {step}")
    target = Path(path)
    fits.PrimaryHDU(data=image.data, header=header).writeto(target, overwrite=overwrite)
    return target


# --------------------------------------------------------------------------
# P7 — Ricampionamento, RGB e mosaico (reproject, D11-2)
# --------------------------------------------------------------------------

#: Metodi di ricampionamento (obbligatori, senza default).
RESAMPLING_METHODS: tuple[str, ...] = ("nearest", "bilinear", "flux")
_REPROJECT_PROVENANCE = f"reproject {reproject_lib.__version__}"


def _reproject_function(method: str):
    """(funzione di reproject, argomenti) per il metodo richiesto."""
    if method == "nearest":
        return reproject_interp, {"order": "nearest-neighbor"}
    if method == "bilinear":
        return reproject_interp, {"order": "bilinear"}
    if method == "flux":
        return reproject_exact, {}
    raise ImagesFitsError(
        "OPERATION_UNSUPPORTED", f"metodo di ricampionamento {method!r} non previsto; metodi: {', '.join(RESAMPLING_METHODS)}"
    )


def _check_resampling_input(image: FitsImage, what: str) -> None:
    if not isinstance(image, FitsImage):
        raise TypeError(f"{what}: serve un FitsImage")
    if image.color:
        raise ImagesFitsError("RGB_INPUT_INVALID", f"{what}: serve un'immagine monocroma")
    if image.wcs is None:
        raise ImagesFitsError("WCS_MISSING", f"{what}: il ricampionamento richiede la calibrazione ({image.origin})")
    _refuse_preview(image, what)


def _resampling_input(image: FitsImage) -> tuple[np.ndarray, WCS]:
    return np.asarray(image.data, dtype=np.float64), image.wcs.wcs


def _resampling_memory(images, reference: FitsImage, what: str, extra_reference_arrays: int = 0) -> None:
    """Copie float64 degli ingressi, più risultato e copertura di ciascuno sulla griglia di riferimento."""
    reference_pixels = _pixels(_reference_grid(reference)[1])
    needed = sum(_pixels(im.data.shape) for im in images) * _FLOAT64
    needed += (2 * len(images) + extra_reference_arrays) * reference_pixels * _FLOAT64
    _check_memory(what, needed, *images, reference)


def _reference_grid(reference: FitsImage) -> tuple[WcsSolution, tuple[int, int]]:
    if not isinstance(reference, FitsImage) or reference.wcs is None:
        raise ImagesFitsError("WCS_MISSING", "il riferimento deve essere un'immagine con WCS")
    return reference.wcs, reference.shape


@dataclass(frozen=True, eq=False)
class Resampled:
    """Immagine ricampionata e qualità: mappa di copertura e percentuale di pixel coperti."""

    image: FitsImage
    footprint: np.ndarray
    coverage_percent: float
    method: str
    provenance: str = field(default=_REPROJECT_PROVENANCE)


def _on_reference(image: FitsImage, data: np.ndarray, reference: FitsImage, step: str, notes=()) -> FitsImage:
    ref_wcs, shape = _reference_grid(reference)
    header = _header_with_wcs(image.header, ref_wcs.wcs, data.shape)
    if image.bunit:
        header["BUNIT"] = image.bunit
    return dataclasses.replace(
        image,
        data=data,
        header=header,
        wcs=dataclasses.replace(ref_wcs, pixel_shape=(shape[1], shape[0])),
        compression=None,
        warnings=image.warnings + tuple(notes),
        history=image.history + (step,),
        strategy="memory",
        strategy_reason=None,
        preview_step=None,
        full_shape=None,
        raw_ndim=2,
        dropped_axes=(),
    )


def resample_to_reference(image: FitsImage, reference: FitsImage, method: str) -> Resampled:
    """Ricampiona sulla griglia del riferimento (B7) con ``reproject``; metodo obbligatorio."""
    function, kwargs = _reproject_function(method)
    _check_resampling_input(image, "ricampionamento")
    _resampling_memory([image], reference, "ricampionamento")
    data, wcs = _resampling_input(image)
    ref_wcs, shape = _reference_grid(reference)
    out, footprint = function((data, wcs), ref_wcs.wcs, shape_out=shape, **kwargs)
    coverage = 100.0 * float(np.count_nonzero(footprint > 0)) / footprint.size
    step = f"ricampionamento ({method}, reproject) sulla griglia di {reference.origin}: copertura {coverage:.3f} %"
    return Resampled(
        image=_on_reference(image, out, reference, step),
        footprint=footprint,
        coverage_percent=coverage,
        method=method,
    )


def reproject(images, reference: FitsImage, method: str) -> list[Resampled]:
    """Ricampiona più immagini sulla stessa griglia di riferimento."""
    return [resample_to_reference(image, reference, method) for image in images]


@dataclass(frozen=True, eq=False)
class RgbComposite:
    """Immagine a colori di sola presentazione (B11): piani R, G, B a 8 bit sul riferimento."""

    planes: np.ndarray  # 3 × righe × colonne, uint8
    wcs: WcsSolution
    mode: str
    components: tuple[str | None, str | None, str | None]  # origine dell'immagine in R, G, B
    display: tuple[tuple[float, float, str], ...] | None
    scale: float | None  # rgb_diff: fattore unico 255 / max|differenza|
    coverage: np.ndarray  # True dove tutte le componenti coprono il pixel
    reference_origin: str
    method: str = "nearest"
    provenance: str = field(default=f"{_REPROJECT_PROVENANCE}; astropy {astropy.__version__} (astropy.visualization)")


def _smallest_pixel(images) -> FitsImage:
    scales = [float(np.mean(proj_plane_pixel_scales(im.wcs.wcs))) for im in images]
    return images[int(np.argmin(scales))]


def rgb_composite(images, reference: FitsImage | None = None, mode: str = "rgb", display=None, wavelengths=None) -> RgbComposite:
    """Immagine a colori da 2 o 3 immagini monocrome (``rgb``) o differenza (``rgb_diff``)."""
    images = list(images)
    if mode not in ("rgb", "rgb_diff"):
        raise ImagesFitsError("RGB_INPUT_INVALID", f"modalità {mode!r}: ammesse 'rgb' e 'rgb_diff'")
    if not 2 <= len(images) <= 3 or (mode == "rgb_diff" and len(images) != 2):
        raise ImagesFitsError("RGB_INPUT_INVALID", f"{len(images)} immagini per {mode}: servono 2 o 3 (2 per rgb_diff)")
    for im in images:
        if not isinstance(im, FitsImage) or im.color:
            raise ImagesFitsError("RGB_INPUT_INVALID", "servono immagini monocrome (FitsImage)")
        if im.wcs is None:
            raise ImagesFitsError("WCS_MISSING", f"RGB: {im.origin} non ha WCS, il ricampionamento richiede la calibrazione")
    order = list(range(len(images)))
    if wavelengths is not None:
        if not isinstance(wavelengths, u.Quantity) or len(wavelengths) != len(images):
            raise ImagesFitsError("RGB_INPUT_INVALID", "wavelengths: una lunghezza d'onda (Quantity) per immagine")
        order = list(np.argsort(-wavelengths.to_value(u.m, equivalencies=u.spectral())))
        images = [images[i] for i in order]
    reference = _smallest_pixel(images) if reference is None else reference
    for im in images:
        _check_resampling_input(im, "RGB")
    # Più i piani di presentazione: intervallo e funzione di trasferimento per componente.
    _resampling_memory(images, reference, "RGB", extra_reference_arrays=2)
    resampled = reproject(images, reference, "nearest")
    covered = np.all([r.footprint > 0 for r in resampled], axis=0)
    shape = resampled[0].image.data.shape
    planes = np.zeros((3,) + shape, dtype=np.uint8)
    scale = None
    used_display = None
    if mode == "rgb":
        if display is None or len(display) != len(images):
            raise ImagesFitsError("RGB_INPUT_INVALID", "rgb: servono (vmin, vmax, funzione di trasferimento) per ogni componente")
        if wavelengths is not None:
            display = [display[i] for i in order]
        used_display = []
        for k, (r, params) in enumerate(zip(resampled, display, strict=True)):
            vmin, vmax, stretch = float(params[0]), float(params[1]), _check_display_option(params[2], STRETCHES, "funzione di trasferimento")
            if not (math.isfinite(vmin) and math.isfinite(vmax) and vmin < vmax):
                raise ValueError("serve vmin < vmax, entrambi finiti")
            values = r.image.data
            normalized = np.full(values.shape, np.nan)
            finite = np.isfinite(values)
            normalized[finite] = ManualInterval(vmin, vmax)(values[finite], clip=True)
            stretched = _apply_stretch(normalized, stretch, 1.0)
            planes[k] = np.where(np.isfinite(stretched), np.round(stretched * 255.0), 0.0).astype(np.uint8)
            used_display.append((vmin, vmax, stretch))
        if len(images) == 2:
            planes[2] = np.round((planes[0].astype(np.float64) + planes[1]) / 2.0).astype(np.uint8)
        used_display = tuple(used_display)
    else:
        a, b = resampled[0].image, resampled[1].image
        if (images[0].bunit or None) != (images[1].bunit or None):
            raise ImagesFitsError("UNIT_MISMATCH", f"rgb_diff: unità diverse {images[0].bunit!r} e {images[1].bunit!r}")
        diff = a.data - b.data
        finite = np.isfinite(diff)
        peak = float(np.max(np.abs(diff[finite]))) if np.any(finite) else 0.0
        if peak > 0.0:
            scale = 255.0 / peak
            planes[0] = np.where(finite, np.round(np.clip(diff, 0.0, None) * scale), 0.0).astype(np.uint8)
            planes[1] = np.where(finite, np.round(np.clip(-diff, 0.0, None) * scale), 0.0).astype(np.uint8)
    planes[:, ~covered] = 0
    origins = [im.origin for im in images] + [None] * (3 - len(images))
    return RgbComposite(
        planes=planes,
        wcs=resampled[0].image.wcs,
        mode=mode,
        components=tuple(origins),  # type: ignore[arg-type]
        display=used_display,
        scale=scale,
        coverage=covered,
        reference_origin=reference.origin,
    )


def mosaic(images, reference: FitsImage, method: str) -> Resampled:
    """Mosaico nella griglia del riferimento: media nelle sovrapposizioni, nessuna correzione del fondo."""
    function, kwargs = _reproject_function(method)
    images = list(images)
    if not images:
        raise ValueError("servono immagini per il mosaico")
    units = {im.bunit or None for im in images}
    if len(units) > 1:
        raise ImagesFitsError("UNIT_MISMATCH", f"mosaico: unità diverse {sorted(map(str, units))}")
    for im in images:
        _check_resampling_input(im, "mosaico")
    # Per ogni ingresso: risultato e copertura; in più somma e conteggio della media.
    _resampling_memory(images, reference, "mosaico", extra_reference_arrays=2)
    inputs = [_resampling_input(im) for im in images]
    ref_wcs, shape = _reference_grid(reference)
    out, footprint = reproject_and_coadd(
        inputs, ref_wcs.wcs, shape_out=shape, reproject_function=function, combine_function="mean",
        match_background=False, **kwargs,
    )
    coverage = 100.0 * float(np.count_nonzero(footprint > 0)) / footprint.size
    step = (
        f"mosaico di {len(images)} immagini ({method}, reproject_and_coadd, media, nessuna correzione del fondo) "
        f"sulla griglia di {reference.origin}"
    )
    return Resampled(image=_on_reference(images[0], out, reference, step), footprint=footprint,
                     coverage_percent=coverage, method=method)


def pixel_scaling(image: FitsImage) -> PixelScaling:
    """``BZERO``, ``BSCALE``, ``BLANK`` e ``BUNIT`` dell'intestazione originale."""
    header = image.header

    def number(key, kind):
        value = header.get(key)
        return None if value is None else kind(value)

    return PixelScaling(
        bzero=number("BZERO", float),
        bscale=number("BSCALE", float),
        blank=number("BLANK", int),
        bunit=header.get("BUNIT"),
    )


@dataclass(frozen=True)
class StarCentroid:
    """Centroide di una stella, pronto per ``astrometric_calibration`` (modulo 10)."""

    x: float
    y: float
    convention: str  # sempre "numpy"
    window: tuple[int, int, int, int]  # x_min, x_max, y_min, y_max inclusi
    background: float
    background_std: float
    n_background_pixels: int
    annulus_inner: float
    annulus_outer: float
    clip_sigma: float
    clip_maxiters: int
    provenance: str = _PROVENANCE


def _image_array(image) -> np.ndarray:
    data = getattr(image, "data", image)
    array = np.asarray(data)
    if array.ndim != 2:
        raise ValueError("serve un'immagine 2-D (array o oggetto con attributo data)")
    return array


def _star_centroid_by_region(image: FitsImage, position, box_size, annulus_inner, annulus_outer) -> StarCentroid:
    """Centroide di un'immagine a due livelli: pixel originali della sola regione che serve."""
    px, py = (float(v) for v in position)
    r_out = float(annulus_outer)
    half = int(box_size) // 2 if isinstance(box_size, int) and not isinstance(box_size, bool) else 0
    cx, cy = int(round(px)), int(round(py))
    bx0 = min(cx - half, math.floor(px - r_out))
    bx1 = max(cx + half, math.ceil(px + r_out))
    by0 = min(cy - half, math.floor(py - r_out))
    by1 = max(cy + half, math.ceil(py + r_out))
    ny, nx = image.shape
    if bx0 < 0 or by0 < 0 or bx1 > nx - 1 or by1 > ny - 1:
        raise ImagesFitsError(
            "CENTROID_OUT_OF_IMAGE", f"finestra o corona fuori dall'immagine {nx}×{ny}", window=(bx0, bx1, by0, by1), shape=(nx, ny)
        )
    region = image.read_region(bx0, bx1 + 1, by0, by1 + 1)
    local = star_centroid(region, (px - bx0, py - by0), box_size, annulus_inner, annulus_outer)
    x0, x1, y0, y1 = local.window
    return dataclasses.replace(local, x=local.x + bx0, y=local.y + by0, window=(x0 + bx0, x1 + bx0, y0 + by0, y1 + by0))


def star_centroid(image, position, box_size: int, annulus_inner: float, annulus_outer: float) -> StarCentroid:
    """Baricentro pesato sull'intensità dopo la sottrazione del fondo (D11-7).

    - finestra quadrata di lato ``box_size`` (intero dispari ≥ 3) centrata sul
      pixel più vicino a ``position`` = (x, y) in convenzione numpy;
    - fondo = mediana con sigma clipping (``astropy.stats.sigma_clipped_stats``)
      dei pixel a distanza da ``position`` in [``annulus_inner``,
      ``annulus_outer``) pixel;
    - baricentro con ``scipy.ndimage.center_of_mass`` su finestra − fondo,
      in ``float64``.
    """
    if getattr(image, "is_preview", False):
        return _star_centroid_by_region(image, position, box_size, annulus_inner, annulus_outer)
    data = _image_array(image)
    if isinstance(box_size, bool) or not isinstance(box_size, int) or box_size < 3 or box_size % 2 == 0:
        raise ValueError("box_size deve essere un intero dispari ≥ 3")
    r_in, r_out = float(annulus_inner), float(annulus_outer)
    if not (math.isfinite(r_in) and math.isfinite(r_out) and 0.0 <= r_in < r_out):
        raise ValueError("raggi della corona non validi: serve 0 ≤ annulus_inner < annulus_outer")
    px, py = (float(v) for v in position)
    if not (math.isfinite(px) and math.isfinite(py)):
        raise ValueError("posizione non finita")

    ny, nx = data.shape
    half = box_size // 2
    cx, cy = int(round(px)), int(round(py))
    x0, x1, y0, y1 = cx - half, cx + half, cy - half, cy + half
    # La corona deve stare tutta nell'immagine, come la finestra.
    ax0, ax1 = math.floor(px - r_out), math.ceil(px + r_out)
    ay0, ay1 = math.floor(py - r_out), math.ceil(py + r_out)
    if min(x0, y0, ax0, ay0) < 0 or x1 > nx - 1 or ax1 > nx - 1 or y1 > ny - 1 or ay1 > ny - 1:
        raise ImagesFitsError(
            "CENTROID_OUT_OF_IMAGE",
            f"finestra x {x0}..{x1}, y {y0}..{y1} o corona di raggio {r_out} fuori dall'immagine {nx}×{ny}",
            window=(x0, x1, y0, y1),
            shape=(nx, ny),
        )

    window = data[y0 : y1 + 1, x0 : x1 + 1].astype(np.float64)
    if not np.all(np.isfinite(window)):
        raise ImagesFitsError("CENTROID_UNDEFINED", "pixel non finiti nella finestra del centroide")

    sub = data[ay0 : ay1 + 1, ax0 : ax1 + 1].astype(np.float64)
    yy, xx = np.mgrid[ay0 : ay1 + 1, ax0 : ax1 + 1]
    r = np.hypot(xx - px, yy - py)
    ring = sub[(r >= r_in) & (r < r_out) & np.isfinite(sub)]
    if ring.size == 0:
        raise ImagesFitsError("CENTROID_UNDEFINED", "nessun pixel finito nella corona del fondo")
    _, median, std = sigma_clipped_stats(ring, sigma=_CLIP_SIGMA, maxiters=_CLIP_MAXITERS)

    weights = window - median
    if not np.sum(weights) > 0.0:
        raise ImagesFitsError(
            "CENTROID_UNDEFINED", "somma dei pesi ≤ 0 dopo la sottrazione del fondo: nessuna stella nella finestra"
        )
    row, col = ndimage.center_of_mass(weights)
    return StarCentroid(
        x=float(x0 + col),
        y=float(y0 + row),
        convention="numpy",
        window=(x0, x1, y0, y1),
        background=float(median),
        background_std=float(std),
        n_background_pixels=int(ring.size),
        annulus_inner=r_in,
        annulus_outer=r_out,
        clip_sigma=_CLIP_SIGMA,
        clip_maxiters=_CLIP_MAXITERS,
    )
