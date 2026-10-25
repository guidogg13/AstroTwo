# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Esportazione della vista in PNG (41 §3.14, sprint 4h): testi dei metadati, crediti dei dati e scrittura del file.

Nessun numero nuovo: centro, scala, proiezione, base e finestra sono quelli dello stato dello spazio di lavoro
(``ViewState.state_json`` del 05), il campo di vista è ``2 × field_radius`` della ``ViewGeometry`` del 10 (come in
``view.*``), origine e data dei livelli sono quelle già registrate dai moduli 11, 12 e 13. I testi di riconoscimento
sono quelli di ``01`` §6.1 (letti il 2026-10-17); per un survey HiPS vale il testo dichiarato dal survey stesso
(``obs_ack``, ``obs_copyright``), mai un testo nostro.

``compose_metadata`` e ``credit_entries`` girano nel thread dei comandi (leggono solo lo stato immutabile);
``write_png`` gira nel thread principale (usa ``QImage`` e ``QPainter``).
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter

import astrotwo
from astrotwo.core.commands import CommandError, WorkspaceState, quantity_json

#: Frase del blocco ``Comment`` (41 §3.14): l'immagine è per l'occhio, non per le misure.
COMMENT = "Image for display only: pixel values are not scientific data. Exported by AstroTwo."

SIMBAD_TEXT = ("This research has made use of the SIMBAD database, CDS, Strasbourg Astronomical Observatory, France; "
               "2000, A&AS, 143, 9, \"The SIMBAD astronomical database\", Wenger et al.")
VIZIER_TEXT = ("This research has made use of the VizieR catalogue access tool, CDS, Strasbourg Astronomical "
               "Observatory, France (DOI : 10.26093/cds/vizier); 2000, A&AS, 143, 23, \"The VizieR database of "
               "astronomical catalogues\", Ochsenbein et al.")
DSS_TEXT = ("The Digitized Sky Surveys were produced at the Space Telescope Science Institute under U.S. Government "
            "grant NAG W-2166. The images of these surveys are based on photographic data obtained using the Oschin "
            "Schmidt Telescope on Palomar Mountain and the UK Schmidt Telescope. The plates were processed into the "
            "present compressed digital form with the permission of these institutions. "
            "Full text: https://archive.stsci.edu/dss/acknowledging.html")

#: Larghezza massima della riga dei crediti nell'immagine, come frazione della larghezza (41 §3.14).
CREDIT_WIDTH_FRACTION = 0.5


@dataclass(frozen=True)
class Credit:
    """Un credito: ``short`` per la riga nell'immagine, ``full`` per i metadati."""

    key: str
    short: str
    full: str


def _host(url: str | None) -> str:
    return (urlsplit(url or "").hostname or "").lower()


def _declared(properties: Mapping[str, tuple[str, ...]], *names: str) -> str:
    parts = []
    for name in names:
        parts.extend(v for v in properties.get(name, ()) if v)
    return " ".join(parts)


def credit_entries(state: WorkspaceState) -> tuple[Credit, ...]:
    """Crediti dei livelli visibili, senza ripetizioni, nell'ordine dei livelli (41 §3.14, scelta minore 3)."""
    found: dict[str, Credit] = {}
    for layer in state.layers:
        if not layer.visible:
            continue
        if layer.kind == "hips" and layer.data is not None:
            service = layer.data
            props = getattr(service, "properties", {}) or {}
            declared = _declared(props, "obs_ack", "obs_copyright")
            title = service.title or service.hips_id
            if "DSS" in service.hips_id.upper():
                found.setdefault("dss", Credit("dss", "DSS (STScI, Palomar, UKST)", DSS_TEXT))
            if declared or "dss" not in found:
                full = f"{title} ({service.hips_id})" + (f": {declared}" if declared else "")
                found.setdefault(f"hips:{service.hips_id}", Credit(f"hips:{service.hips_id}", title, full))
        elif layer.kind == "catalog" and layer.data is not None:
            host = _host(getattr(layer.data, "origin", ""))
            if "simbad" in host:
                found.setdefault("simbad", Credit("simbad", "SIMBAD, CDS", SIMBAD_TEXT))
            elif "vizier" in host:
                found.setdefault("vizier", Credit("vizier", "VizieR, CDS", VIZIER_TEXT))
                found.setdefault(f"table:{layer.id}", Credit(
                    f"table:{layer.id}", layer.name,
                    f"VizieR catalogue table {layer.name}: cite the authors and the publisher of the catalogue "
                    "(see its ReadMe)"))
    return tuple(found.values())


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _layer_entry(layer) -> dict:
    entry = {"id": layer.id, "kind": layer.kind, "name": layer.name, "source": layer.source}
    data = layer.data
    if layer.kind in ("image", "hips", "catalog") and data is not None:
        entry["origin"] = getattr(data, "origin", None)
        entry["retrieved_at"] = _iso(getattr(data, "retrieved_at", None))
    return entry


def _latin1(text: str) -> str:
    """Il blocco ``tEXt`` è Latin-1 (ISO/IEC 15948): i caratteri fuori Latin-1 diventano ``?``."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def compose_metadata(state: WorkspaceState, *, night: bool, now: datetime | None = None) -> dict[str, str]:
    """Blocchi ``tEXt`` del PNG dallo stato (41 §3.14): parole chiave e valori testuali."""
    view = state.view
    if view.geometry is None or view.window is None:
        raise CommandError("VIEW_UNDEFINED", "vista non definita: centro, scala o finestra mancanti",
                           params={"reason": "export"})
    info = view.state_json()
    info["field_of_view"] = quantity_json(2 * view.geometry.field_radius) if hasattr(
        view.geometry, "field_radius") else None
    info["night_mode"] = bool(night)
    layers = [_layer_entry(layer) for layer in state.layers if layer.visible]
    credits_ = credit_entries(state)
    now = now if now is not None else datetime.now(UTC)
    texts = {
        "Software": f"AstroTwo {astrotwo.__version__}",
        "Creation Time": _iso(now),
        "AstroTwo:View": json.dumps(info, ensure_ascii=True, sort_keys=True),
        "AstroTwo:Layers": json.dumps(layers, ensure_ascii=True, sort_keys=True),
        "AstroTwo:Credits": "\n".join(c.full for c in credits_),
        "Comment": COMMENT,
    }
    return {key: _latin1(value) for key, value in texts.items()}


def validate_path(path: str) -> Path:
    """Percorso assoluto con estensione ``.png`` in una cartella scrivibile (``EXPORT_PATH_INVALID``)."""
    target = Path(path)
    if not target.is_absolute() or target.suffix.lower() != ".png":
        raise CommandError("EXPORT_PATH_INVALID", f"{path!r}: serve un percorso assoluto con estensione .png",
                           params={"reason": "not_png", "path": path})
    if not target.parent.is_dir() or not os.access(target.parent, os.W_OK):
        raise CommandError("EXPORT_PATH_INVALID", f"{str(target.parent)!r}: cartella inesistente o non scrivibile",
                           params={"reason": "folder_unwritable", "folder": str(target.parent)})
    if target.is_dir():
        raise CommandError("EXPORT_PATH_INVALID", f"{path!r} è una cartella",
                           params={"reason": "is_directory", "path": path})
    return target


def draw_credits(image: QImage, line: str) -> QImage:
    """Riga dei crediti in basso a destra, su fondo scuro semitrasparente, tagliata a metà larghezza (§3.14)."""
    if not line:
        return image
    out = image.convertToFormat(QImage.Format.Format_RGB888)
    painter = QPainter(out)
    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        font = QFont()
        font.setPixelSize(max(10, round(out.height() / 70)))
        painter.setFont(font)
        metrics = QFontMetricsF(font)
        room = out.width() * CREDIT_WIDTH_FRACTION
        text = metrics.elidedText(line, Qt.TextElideMode.ElideRight, room)
        pad = metrics.height() / 3
        width = metrics.horizontalAdvance(text) + 2 * pad
        box = QRectF(out.width() - width, out.height() - metrics.height() - 2 * pad, width, metrics.height() + 2 * pad)
        painter.fillRect(box, QColor(0, 0, 0, 160))
        painter.setPen(QColor(235, 235, 235))
        painter.drawText(box.adjusted(pad, pad, -pad, -pad), Qt.AlignmentFlag.AlignVCenter, text)
    finally:
        painter.end()
    return out


def credit_line(credits_: tuple[Credit, ...]) -> str:
    return "Credits: " + " · ".join(c.short for c in credits_) if credits_ else ""


def write_png(image: QImage, path: Path, metadata: Mapping[str, str], line: str) -> tuple[int, int]:
    """Scrive il PNG con i blocchi ``tEXt`` in un file temporaneo e lo rinomina (mai un file a metà). Restituisce
    ``(larghezza, altezza)`` in pixel fisici del file scritto."""
    shot = draw_credits(image, line).convertToFormat(QImage.Format.Format_RGB888)
    rows, cols = shot.height(), shot.width()
    buffer = np.frombuffer(shot.constBits(), dtype=np.uint8).reshape(rows, shot.bytesPerLine())[:, : 3 * cols]
    picture = Image.fromarray(np.ascontiguousarray(buffer.reshape(rows, cols, 3)), "RGB")
    info = PngInfo()
    for key, value in metadata.items():
        info.add_text(key, value)
    handle, temporary = tempfile.mkstemp(suffix=".png.part", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            picture.save(stream, format="PNG", pnginfo=info)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return cols, rows
