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

import gzip
import math
import os
import warnings
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import astropy
import astropy.units as u
import numpy as np
import scipy
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.wcs import WCS, FITSFixedWarning
from scipy import ndimage

from astrotwo.core.coordinates_wcs import CoordinatesWcsError, WcsSolution, pixel_to_sky, wcs_from_header

__all__ = [
    "SUPPORTED_FORMATS",
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
    provenance: str = field(default=_FITS_PROVENANCE)

    @property
    def shape(self) -> tuple[int, int]:
        return tuple(self.data.shape)  # type: ignore[return-value]

    @property
    def has_wcs(self) -> bool:
        return self.wcs is not None

    def header_value(self, key: str, default=None):
        """Valore di una parola chiave dell'intestazione originale."""
        return self.header.get(key, default)

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


def load_image(source, hdu=None) -> FitsImage:
    """Carica un'immagine e ne dichiara origine e data (P1: file FITS locali).

    Con più HDU immagine serve ``hdu`` (indice o nome), altrimenti
    ``HDU_CHOICE_REQUIRED`` (D11-4).
    """
    text = os.fspath(source) if not isinstance(source, str) else source
    if text.startswith(("http://", "https://")):
        raise NotImplementedError("lettura da URL: parte P3 del modulo 11, non ancora scritta")
    path = str(Path(text).expanduser().resolve())
    fmt = detect_format(path)
    if fmt in ("jpeg", "png", "gif"):
        raise NotImplementedError(f"formato {fmt}: parte P2 del modulo 11, non ancora scritta")
    retrieved_at = datetime.now(UTC)
    with _open_fits(path) as hdul:
        index = _select_hdu(hdul, hdu, path)
        chosen = hdul[index]
        header = chosen.header.copy()  # prima di leggere i dati: BZERO/BSCALE originali
        compression = _compression(chosen)
        try:
            data = np.array(chosen.data)
        except Exception as exc:
            if compression is not None:
                raise ImagesFitsError(
                    "COMPRESSION_UNSUPPORTED", f"{path}: compressione {compression} non leggibile ({exc})"
                ) from exc
            raise ImagesFitsError("FITS_UNREADABLE", f"{path}: dati non leggibili ({exc})", path=path) from exc
        name = chosen.name
    ndim = data.ndim
    dropped = tuple(ndim - k for k, n in enumerate(data.shape) if n == 1)
    kept = {ndim - k for k, n in enumerate(data.shape) if n > 1}
    data = data.reshape(tuple(n for n in data.shape if n > 1))
    if not data.dtype.isnative:
        # Stesso tipo e stessi valori, nell'ordine di byte della macchina
        # (FITS è big-endian): evita conversioni lente nelle librerie.
        data = data.astype(data.dtype.newbyteorder("="))
    notes: list[tuple[str, str]] = []
    if dropped:
        notes.append(("AXES_DROPPED", f"assi FITS di lunghezza 1 tolti: {sorted(dropped)}"))
    solution, wcs_notes = _image_wcs(header, kept)
    notes.extend(wcs_notes)
    if np.issubdtype(data.dtype, np.floating) and not np.all(np.isfinite(data)):
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
    )


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
