# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Esportazione del profilo di un oggetto (livello 2, modulo 25 §3.15, sprint C6): ECSV, PDF, PNG della SED, VOTable.

Specifica: ``mdfiles/25-analisi-profilo-oggetto.md`` §3.15 (file a parte di ``object_profile.py`` per la lunghezza;
stesso modulo 25). Tutto si costruisce **dalla forma JSON del risultato** di comandi ``object.profile`` già eseguiti
(``merge_profile_results``): nessuna richiesta di rete, nessun valore ricalcolato (regola d'oro n. 1). I numeri sono
scritti con la rappresentazione più corta del ``float64`` del risultato (``repr``), le unità come nel risultato.

Il PDF si disegna con matplotlib (``backend_pdf.PdfPages``, senza pyplot; D25-20 (1)), il grafico della SED è quello
del 20 (``plot_sed_rows``, limiti superiori come frecce, D43-9). Nessuna data di esportazione nei file ECSV, PDF e PNG
(D25-20 (7)): Riesegui riscrive lo stesso file byte per byte.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import os
import re
import tempfile
import textwrap
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from astropy.table import MaskedColumn, Table

import astrotwo
from astrotwo.analysis.photometry import sed_rows_png
from astrotwo.messages_catalog import message_text

__all__ = [
    "EXPORT_EXTENSIONS",
    "EXPORT_FORMATS",
    "STSCI_DSS_TEXT",
    "STSCI_DSS_URL",
    "ProfileExport",
    "ProfileExportError",
    "check_export_path",
    "default_sed_folder",
    "export_profile",
    "merge_profile_results",
    "profile_values_table",
    "results_from_history",
    "sed_catalog_path",
    "sed_catalog_table",
]

EXPORT_FORMATS: tuple[str, ...] = ("ecsv", "pdf", "sed_png", "sed_votable")
EXPORT_EXTENSIONS: dict[str, tuple[str, ...]] = {"ecsv": (".ecsv",), "pdf": (".pdf",), "sed_png": (".png",),
                                                 "sed_votable": (".xml", ".vot")}
#: Testo di riconoscimento di STScI per i survey DSS (01 §6.1, primo paragrafo; D25-17 (3)).
STSCI_DSS_TEXT = ("The Digitized Sky Surveys were produced at the Space Telescope Science Institute under U.S. "
                  "Government grant NAG W-2166. The images of these surveys are based on photographic data obtained "
                  "using the Oschin Schmidt Telescope on Palomar Mountain and the UK Schmidt Telescope. The plates "
                  "were processed into the present compressed digital form with the permission of these "
                  "institutions.")
STSCI_DSS_URL = "https://archive.stsci.edu/dss/acknowledging.html"
_SECTION_ORDER = ("identity", "images", "astrometry", "photometry", "planets")
_EXACT_INT = 2 ** 53  # interi rappresentati esattamente da un float64
_PLANET_COLUMNS = ("period", "semi_major_axis", "eccentricity", "mass", "radius", "equilibrium_temperature")


class ProfileExportError(Exception):
    """Errore dell'esportazione con codice della specifica (25 §10) e ``params`` (D40-3)."""

    def __init__(self, code: str, message: str, *, params: Mapping[str, object] | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.params = dict(params or {})


def _invalid(reason: str, message: str, **params) -> ProfileExportError:
    return ProfileExportError("PROFILE_EXPORT_INVALID", message, params={"reason": reason, **params})


@dataclass(frozen=True)
class ProfileExport:
    """File scritto: percorso, formato, SHA-256, byte, righe (ECSV, VOTable) o pagine (PDF)."""

    path: Path
    format: str
    sha256: str
    size: int
    rows: int | None = None
    pages: int | None = None
    warnings: tuple = ()

    def as_dict(self) -> dict:
        return {"path": str(self.path), "format": self.format, "sha256": self.sha256,
                "size": {"value": self.size, "unit": "byte"}, "rows": self.rows, "pages": self.pages}


# --------------------------------------------------------------------------
# Risultati registrati → forma JSON della scheda (25 §3.15)
# --------------------------------------------------------------------------


def results_from_history(history, commands: Sequence[int]) -> list[tuple[int, dict]]:
    """``(numero, valori)`` dei comandi ``object.profile`` indicati, dalla cronologia del 05; controlli di §3.15."""
    entries = {e.number: e for e in history}
    out = []
    for number in commands:
        entry = entries.get(int(number))
        if entry is None:
            raise _invalid("command_missing", f"#{number}: nessun comando con questo numero in cronologia",
                           number=int(number))
        if entry.command.name != "object.profile":
            raise _invalid("not_profile", f"#{number} è {entry.command.name}, non object.profile", number=int(number),
                           command=entry.command.name)
        values = entry.result.values if isinstance(entry.result.values, Mapping) else {}
        if entry.result.status not in ("ok", "cancelled") or not values.get("sections"):
            raise _invalid("no_profile", f"#{number}: il risultato non contiene un profilo (esito "
                           f"{entry.result.status})", number=int(number))
        out.append((int(number), json.loads(json.dumps(values))))
    return out


def merge_profile_results(results: Sequence[tuple[int, Mapping]]) -> dict:
    """Forma JSON della scheda: il primo risultato è il profilo di base, ogni risultato successivo sostituisce le
    sezioni che contiene («Riprova questa sezione», 43 §3.6); ogni sezione porta ``command_id``."""
    if not results:
        raise _invalid("command_missing", "nessun comando indicato", number=0)
    first, values = results[0]
    data = copy.deepcopy(dict(values))
    sections = {s["name"]: {**s, "command_id": first} for s in data.get("sections") or []}
    for number, later in results[1:]:
        for section in later.get("sections") or []:
            sections[section["name"]] = {**copy.deepcopy(section), "command_id": number}
    data["sections"] = [sections[n] for n in _SECTION_ORDER if n in sections]
    data["commands"] = [n for n, _ in results]
    return data


def _section(data: Mapping, name: str) -> dict | None:
    for s in data.get("sections") or []:
        if s.get("name") == name:
            return s
    return None


def _sed(data: Mapping) -> tuple[list, dict | None]:
    photometry = _section(data, "photometry") or {}
    details = photometry.get("details") or {}
    return list(details.get("points") or []), details.get("vizier")


def _has_sed(data: Mapping) -> bool:
    points, vizier = _sed(data)
    return bool(points) or bool((vizier or {}).get("rows"))


def check_export_path(path: str, fmt: str) -> Path:
    """Percorso assoluto con l'estensione del formato in una cartella scrivibile (``PROFILE_EXPORT_INVALID``)."""
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"formato {fmt!r} non in {EXPORT_FORMATS}")
    target = Path(path)
    if not target.is_absolute():
        raise _invalid("not_absolute", f"{path!r}: serve un percorso assoluto", path=str(path))
    if target.suffix.lower() not in EXPORT_EXTENSIONS[fmt]:
        raise _invalid("extension", f"{path!r}: il formato {fmt} vuole l'estensione "
                       f"{' o '.join(EXPORT_EXTENSIONS[fmt])}", path=str(path), format=fmt,
                       extensions=list(EXPORT_EXTENSIONS[fmt]))
    if target.is_dir():
        raise _invalid("is_directory", f"{path!r} è una cartella", path=str(path))
    if not target.parent.is_dir() or not os.access(target.parent, os.W_OK):
        raise _invalid("folder_unwritable", f"{str(target.parent)!r}: cartella inesistente o non scrivibile",
                       folder=str(target.parent))
    return target


def default_sed_folder() -> Path:
    """Cartella dei VOTable dei punti SED caricati come catalogo (25 §3.15): mai cancellati, servono alle sessioni."""
    return Path.home() / "Library" / "Application Support" / "AstroTwo" / "Profiles"


def sed_catalog_path(main_id: str | None, number: int, folder: Path | None = None) -> Path:
    """File del VOTable dei punti SED nella cartella ``Profiles/`` (25 §3.15): ``<main_id ridotto>-sed-<n>.xml``."""
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", " ".join(str(main_id or "profile").split())).strip("_") or "profile"
    return (default_sed_folder() if folder is None else folder) / f"{stem}-sed-{int(number)}.xml"


# --------------------------------------------------------------------------
# Testi dei valori: nessun calcolo, solo scrittura (come la finestra, D43-7)
# --------------------------------------------------------------------------


def _plain(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _num(value) -> str:
    """Testo di un valore del risultato (numero con unità o testo) senza unità."""
    if isinstance(value, Mapping) and "value" in value:
        return _plain(value["value"])
    return _plain(value)


def _unit(value) -> str:
    return str(value.get("unit") or "") if isinstance(value, Mapping) else ""


def _with_unit(value) -> str:
    text, unit = _num(value), _unit(value)
    return f"{text} {unit}".strip() if text else ""


def _error(entry: Mapping) -> str:
    if entry.get("error_upper") is not None or entry.get("error_lower") is not None:
        return f"+{_num(entry.get('error_upper'))} / {_num(entry.get('error_lower'))}"
    if entry.get("error") is not None:
        return f"± {_num(entry['error'])}"
    if entry.get("interval"):
        low, high = entry["interval"]
        return f"[{_num(low)}, {_num(high)}]"
    return ""


def _float_cell(value) -> float | None:
    """Numero per una colonna ``float64``: solo se il valore del risultato lo è esattamente (mai testi né interi
    oltre 2^53, che restano in ``value_text``)."""
    number = value.get("value") if isinstance(value, Mapping) else value
    if isinstance(number, bool) or number is None:
        return None
    if isinstance(number, int):
        return float(number) if abs(number) <= _EXACT_INT else None
    if isinstance(number, float):
        return number
    return None


# --------------------------------------------------------------------------
# 1. ECSV dei valori con provenienza (25 §3.15 punto 1)
# --------------------------------------------------------------------------

_VALUE_COLUMNS = (("section", str), ("quantity", str), ("value", float), ("value_text", str), ("unit", str),
                  ("error", float), ("error_lower", float), ("error_upper", float), ("interval_lower", float),
                  ("interval_upper", float), ("interval_kind", str), ("band", str), ("system", str),
                  ("upper_limit", bool), ("method", str), ("formula", str), ("service", str), ("server", str),
                  ("table", str), ("query", str), ("identifier", str), ("match", str), ("reference", str),
                  ("note", str), ("retrieved_at", str), ("from_cache", str), ("command_id", int))
_DESCRIPTIONS = {
    "value": "numeric value as in the result (empty for texts, booleans and integers not exact in float64)",
    "value_text": "value exactly as in the result (shortest repr of the float64, integer digits, text)",
    "upper_limit": "SED point that is an upper limit: never a measurement",
    "server": "URL of the server that actually answered (also a mirror)",
    "command_id": "number of the object.profile command that produced the value",
}


def _value_row(section: str, entry: Mapping, command_id: int, band: tuple | None) -> dict:
    prov = entry.get("provenance") or {}
    interval = entry.get("interval") or [None, None]
    cache = prov.get("from_cache")
    return {"section": section, "quantity": str(entry.get("quantity") or ""), "value": _float_cell(entry.get("value")),
            "value_text": _num(entry.get("value")), "unit": _unit(entry.get("value")),
            "error": _float_cell(entry.get("error")), "error_lower": _float_cell(entry.get("error_lower")),
            "error_upper": _float_cell(entry.get("error_upper")), "interval_lower": _float_cell(interval[0]),
            "interval_upper": _float_cell(interval[1]), "interval_kind": entry.get("interval_kind") or "",
            "band": "" if band is None else band[0] or "", "system": "" if band is None else band[1] or "",
            "upper_limit": False if band is None else bool(band[2]), "method": entry.get("method") or "",
            "formula": entry.get("formula") or "", "service": prov.get("service") or "",
            "server": prov.get("server") or "", "table": prov.get("table") or "", "query": prov.get("query") or "",
            "identifier": prov.get("identifier") or "", "match": prov.get("match") or "",
            "reference": entry.get("reference") or "", "note": entry.get("note") or "",
            "retrieved_at": prov.get("retrieved_at") or "", "from_cache": "" if cache is None else _plain(bool(cache)),
            "command_id": int(command_id)}


def _vizier_rows(vizier: Mapping, command_id: int) -> list[dict]:
    prov = vizier.get("provenance") or {}
    out = []
    for row in vizier.get("rows") or []:
        flux, err = row.get("flux"), row.get("flux_error")
        freq = row.get("frequency")
        entry = {"quantity": f"VizieR SED {row.get('filter') or ''} flux_nu".replace("  ", " "), "value": flux,
                 "error": err, "method": "read",
                 "note": "as given by VizieR (D20-5)" + (f"; frequency {_with_unit(freq)}" if freq else ""),
                 "provenance": {**prov, "table": row.get("catalog") or prov.get("table")}}
        out.append(_value_row("photometry", entry, command_id, (row.get("filter"), None, False)))
    return out


def profile_values_table(data: Mapping) -> Table:
    """Una riga per valore con la provenienza (colonne di 25 §3.15 punto 1), più una per riga della serie VizieR."""
    rows: list[dict] = []
    for section in data.get("sections") or []:
        name, command_id = section.get("name"), section.get("command_id")
        bands = {}
        if name == "photometry":
            for p in (section.get("details") or {}).get("points") or []:
                bands[p.get("label") or f"{p.get('catalog')} {p.get('band')}"] = (p.get("band"), p.get("system"),
                                                                                   p.get("upper_limit"))
        for entry in section.get("values") or []:
            quantity = str(entry.get("quantity") or "")
            band = bands.get(quantity.rsplit(" ", 1)[0]) if name == "photometry" else None
            rows.append(_value_row(name, entry, command_id, band))
        vizier = (section.get("details") or {}).get("vizier") if name == "photometry" else None
        if vizier:
            rows.extend(_vizier_rows(vizier, command_id))
    columns = []
    for col, kind in _VALUE_COLUMNS:
        cells = [r[col] for r in rows]
        if kind is float:
            column = MaskedColumn([np.nan if c is None else c for c in cells], name=col, dtype=np.float64,
                                  mask=[c is None for c in cells])
        elif kind is bool:
            column = MaskedColumn(np.array(cells, dtype=bool), name=col)
        elif kind is int:
            column = MaskedColumn(np.array(cells, dtype=np.int64), name=col)
        else:
            column = MaskedColumn(np.array(cells, dtype=str) if cells else np.array([], dtype=str), name=col)
        if col in _DESCRIPTIONS:
            column.description = _DESCRIPTIONS[col]
        columns.append(column)
    table = Table(columns, masked=True)
    resolved = data.get("resolved") or {}
    table.meta.update({"A2VERS": f"AstroTwo {astrotwo.__version__}", "A2KIND": "object_profile",
                       "target": data.get("target"), "main_id": resolved.get("main_id"),
                       "position": resolved.get("position"), "position_source": resolved.get("position_source"),
                       "commands": list(data.get("commands") or [])})
    return table


# --------------------------------------------------------------------------
# 4. Tabella dei punti della SED (25 §3.15 punto 4)
# --------------------------------------------------------------------------

_SED_COLUMNS = (
    ("ra", float, "deg", "pos.eq.ra;meta.main", "position of the resolved target (same for every row)"),
    ("dec", float, "deg", "pos.eq.dec;meta.main", "position of the resolved target (same for every row)"),
    ("series", str, None, "meta.code", "astrotwo (our points) or vizier (as given by VizieR)"),
    ("catalog", str, None, "meta.id;meta.dataset", "source of the point (catalog or VizieR _tabname)"),
    ("band", str, None, "instr.bandpass", None), ("system", str, None, "meta.code", "photometric system"),
    ("wavelength", float, "um", "em.wl", "reference wavelength (20)"),
    ("flux_nu", float, "Jy", "phot.flux.density", "Fnu (conversion of the 20 or as given by VizieR)"),
    ("flux_nu_error", float, "Jy", "stat.error;phot.flux.density", None),
    ("magnitude", float, "mag", "phot.mag", "as given by the catalog"),
    ("magnitude_error", float, "mag", "stat.error;phot.mag", None),
    ("quality", str, None, "meta.code.qual", None),
    ("upper_limit", bool, None, "meta.code", "upper limit: never a measurement"),
    ("in_plot", bool, None, "meta.code", "point of the measured series of the plot"),
    ("reasons", str, None, "meta.note", "SED_* codes"), ("zero_point", str, None, "meta.ref", None),
    ("reference", str, None, "meta.bib.bibcode", None), ("identifier", str, None, "meta.id", None),
    ("match", str, None, "meta.code", None), ("server", str, None, "meta.ref.url", None),
    ("table", str, None, "meta.id", None), ("retrieved_at", str, None, "time.processing", None),
    ("from_cache", str, None, "meta.code", None), ("command_id", int, None, "meta.id", None),
)


def _quantity_in(value, unit: str) -> float | None:
    """Valore di una grandezza già nell'unità della colonna (il 20 scrive λ in µm, Fν in Jy, magnitudini in mag)."""
    if not isinstance(value, Mapping) or value.get("value") is None:
        return None
    given = str(value.get("unit") or "")
    if given.replace(" ", "") not in (unit, {"um": "micron", "Jy": "Jy", "mag": "mag"}[unit]):
        raise ValueError(f"unità {given!r} inattesa per una colonna in {unit}")
    return float(value["value"])


def sed_catalog_table(data: Mapping):
    """``CatalogTable`` del 13 con i punti della SED del profilo (25 §3.15 punto 4): una riga per punto (anche in
    magnitudini) e per riga della serie VizieR; posizione del bersaglio risolto in ogni riga (dichiarata)."""
    from astrotwo.core.catalogs import CatalogTable, PositionColumns, TableLimits

    points, vizier = _sed(data)
    if not points and not (vizier or {}).get("rows"):
        raise _invalid("no_sed", "la sezione Fotometria non ha punti della SED")
    photometry = _section(data, "photometry") or {}
    command_id = photometry.get("command_id")
    resolved = data.get("resolved") or {}
    position = resolved.get("position") or {}
    ra = _float_cell(position.get("lon")) if position else None
    dec = _float_cell(position.get("lat")) if position else None
    rows = []
    newest = None
    for p in points:
        prov = p.get("provenance") or {}
        newest = max(filter(None, (newest, prov.get("retrieved_at"))), default=None)
        cache = prov.get("from_cache")
        rows.append({"ra": ra, "dec": dec, "series": "astrotwo", "catalog": p.get("catalog") or "",
                     "band": p.get("band") or "", "system": p.get("system") or "",
                     "wavelength": _quantity_in(p.get("wavelength"), "um"), "flux_nu": _quantity_in(p.get("flux"), "Jy"),
                     "flux_nu_error": _quantity_in(p.get("flux_error"), "Jy"),
                     "magnitude": _quantity_in(p.get("magnitude"), "mag"),
                     "magnitude_error": _quantity_in(p.get("magnitude_error"), "mag"),
                     "quality": p.get("quality") or "", "upper_limit": bool(p.get("upper_limit")),
                     "in_plot": bool(p.get("in_plot")),
                     "reasons": " ".join(n.get("code", "") for n in p.get("notes") or []),
                     "zero_point": p.get("zero_point") or "", "reference": p.get("reference") or "",
                     "identifier": p.get("identifier") or "", "match": p.get("match") or "",
                     "server": prov.get("server") or "", "table": p.get("table") or prov.get("table") or "",
                     "retrieved_at": prov.get("retrieved_at") or "",
                     "from_cache": "" if cache is None else _plain(bool(cache)), "command_id": command_id})
    vprov = (vizier or {}).get("provenance") or {}
    for r in (vizier or {}).get("rows") or []:
        newest = max(filter(None, (newest, vprov.get("retrieved_at"))), default=None)
        cache = vprov.get("from_cache")
        rows.append({"ra": ra, "dec": dec, "series": "vizier", "catalog": r.get("catalog") or "",
                     "band": r.get("filter") or "", "system": "", "wavelength": _quantity_in(r.get("wavelength"), "um"),
                     "flux_nu": _quantity_in(r.get("flux"), "Jy"), "flux_nu_error": _quantity_in(r.get("flux_error"), "Jy"),
                     "magnitude": None, "magnitude_error": None, "quality": "", "upper_limit": False, "in_plot": False,
                     "reasons": "", "zero_point": "", "reference": "", "identifier": "", "match": "position",
                     "server": vprov.get("server") or "", "table": r.get("catalog") or "",
                     "retrieved_at": vprov.get("retrieved_at") or "",
                     "from_cache": "" if cache is None else _plain(bool(cache)), "command_id": command_id})
    columns = []
    for name, kind, unit, ucd, description in _SED_COLUMNS:
        cells = [r[name] for r in rows]
        if kind is float:
            column = MaskedColumn([np.nan if c is None else c for c in cells], name=name, dtype=np.float64,
                                  mask=[c is None for c in cells], unit=unit)
        elif kind is bool:
            column = MaskedColumn(np.array(cells, dtype=bool), name=name)
        elif kind is int:
            column = MaskedColumn(np.array([-1 if c is None else c for c in cells], dtype=np.int64), name=name)
        else:
            column = MaskedColumn(np.array(cells, dtype=str), name=name)
        column.meta["ucd"] = ucd
        if description:
            column.description = description
        columns.append(column)
    main_id = " ".join(str(resolved.get("main_id") or "").split()) or "profile"
    table = Table(columns, masked=True)
    table.meta["name"] = f"SED {main_id}"
    epoch = position.get("epoch") if position else None
    positions = None
    if ra is not None and dec is not None and position.get("frame") == "icrs":
        positions = PositionColumns(lon="ra", lat="dec", frame="icrs", epoch=epoch, source="ucd", system="ICRS")
    commands = ", ".join(f"#{n}" for n in data.get("commands") or [])
    services = sorted({(p.get("provenance") or {}).get("service") or "" for p in points} - {""}
                      | ({vprov.get("service")} if vprov.get("service") else set()))
    moment = datetime.fromisoformat(newest) if newest else datetime.fromtimestamp(0, tz=UTC)
    return CatalogTable(
        table=table, source="object.profile", origin=f"punti della SED del profilo di {main_id}, comandi {commands}",
        retrieved_at=moment, file_modified=None, format="object_profile_sed", table_index=0, table_name=f"SED {main_id}",
        positions=positions, body="celestial" if positions is not None else None, limits=TableLimits(),
        history=(f"punti della SED (20) dai risultati registrati dei comandi object.profile {commands}; servizi: "
                 f"{', '.join(services) or '—'}; posizione {resolved.get('position_source') or '—'} in ogni riga",))


# --------------------------------------------------------------------------
# 2. PDF della scheda (25 §3.15 punto 2)
# --------------------------------------------------------------------------

_W, _H = 8.27, 11.69  # A4 verticale, pollici
_LEFT, _RIGHT, _TOP, _FOOT = 0.6, 0.6, 0.6, 1.0
_LABELS = {
    "en": {"title": "Profile of {name}", "identity": "Identity", "images": "Images",
           "astrometry": "Astrometry and distance", "photometry": "Photometry", "planets": "Planets",
           "sources": "Sources and credits", "status": "Status", "quantity": "Quantity", "value": "Value",
           "error": "Error", "unit": "Unit", "notes": "Notes", "catalog": "Catalog", "identifier": "Identifier",
           "method": "Method", "separation": "Separation", "band": "Band", "system": "System",
           "quality": "Quality", "lambda": "λ", "fnu": "Fν", "plot": "In plot", "yes": "yes", "no": "no",
           "arrow": "arrow (upper limit)", "identifiers": "Identifiers ({count})", "chain": "Identifier chain",
           "more": "… {count} more rows: full table in the ECSV", "more_groups": "… {count} more: full list in the tab",
           "no_planets": "No planet in the archive", "planet": "Planet", "discovery": "Discovery",
           "period": "Period", "semi_major_axis": "Semi-major axis", "eccentricity": "Eccentricity", "mass": "Mass",
           "radius": "Radius", "equilibrium_temperature": "Eq. temperature", "fov": "field", "center": "center",
           "tiles": "tiles from", "credits": "Survey credits", "zero_points": "Zero points used",
           "queries": "Queries", "sources_line": "Sources", "cache": "cache", "not_requested": "Section not requested",
           "target": "Target as written", "position": "Position", "section_command": "command",
           "warnings": "Warnings", "lang": "en"},
    "it": {"title": "Profilo di {name}", "identity": "Identità", "images": "Immagini",
           "astrometry": "Astrometria e distanza", "photometry": "Fotometria", "planets": "Pianeti",
           "sources": "Fonti e crediti", "status": "Stato", "quantity": "Grandezza", "value": "Valore",
           "error": "Errore", "unit": "Unità", "notes": "Note", "catalog": "Catalogo", "identifier": "Identificativo",
           "method": "Metodo", "separation": "Separazione", "band": "Banda", "system": "Sistema",
           "quality": "Qualità", "lambda": "λ", "fnu": "Fν", "plot": "Nel grafico", "yes": "sì", "no": "no",
           "arrow": "freccia (limite superiore)", "identifiers": "Identificativi ({count})",
           "chain": "Catena degli identificativi", "more": "… {count} righe in più: tabella completa nell'ECSV",
           "more_groups": "… {count} in più: elenco completo nella scheda", "no_planets": "Nessun pianeta nell'archivio",
           "planet": "Pianeta", "discovery": "Scoperta", "period": "Periodo", "semi_major_axis": "Semiasse",
           "eccentricity": "Eccentricità", "mass": "Massa", "radius": "Raggio",
           "equilibrium_temperature": "Temp. di equilibrio", "fov": "campo", "center": "centro",
           "tiles": "tile da", "credits": "Crediti dei survey", "zero_points": "Punti zero usati",
           "queries": "Interrogazioni", "sources_line": "Fonti", "cache": "cache",
           "not_requested": "Sezione non richiesta", "target": "Bersaglio come scritto", "position": "Posizione",
           "section_command": "comando", "warnings": "Avvisi", "lang": "it"},
}


class _Page:
    """Una pagina A4 con un cursore verticale (pollici dal basso); testi e tabelle senza ricalcolare nulla."""

    def __init__(self, title: str, subtitle: str = "") -> None:
        from matplotlib.figure import Figure

        self.fig = Figure(figsize=(_W, _H), dpi=100)
        self.y = _H - _TOP
        self.text(title, size=14, bold=True)
        if subtitle:
            self.text(subtitle, size=8, color="0.35")
        self.y -= 0.05

    def room(self) -> float:
        return self.y - _FOOT

    def text(self, text: str, *, size: float = 8.0, bold: bool = False, x: float = _LEFT, width: float | None = None,
             color: str = "black", mono: bool = False) -> None:
        width = (_W - _RIGHT - x) if width is None else width
        chars = max(10, int(width / (size * 0.6 / 72)))
        for paragraph in str(text).split("\n"):
            for line in textwrap.wrap(paragraph, chars, break_long_words=True, break_on_hyphens=False) or [""]:
                if self.room() < size / 72:
                    return
                self.fig.text(x / _W, self.y / _H, line, fontsize=size, weight="bold" if bold else "normal",
                              color=color, va="top", ha="left", family="monospace" if mono else None)
                self.y -= size * 1.35 / 72

    def table(self, headers: Sequence[str], rows: Sequence[Sequence[str]], widths: Sequence[float], *,
              size: float = 6.5, more: str = "", x: float = _LEFT) -> int:
        """Tabella con le celle a capo (mai tagliate né arrotondate); oltre lo spazio della pagina, la riga ``more``
        con il numero delle righe non scritte. Restituisce le righe scritte."""
        line_h = size * 1.3 / 72

        def wrapped(cells):
            out = []
            for cell, w in zip(cells, widths, strict=True):
                chars = max(4, int(w / (size * 0.6 / 72)))
                lines = []
                for part in str(cell).split("\n"):
                    lines += textwrap.wrap(part, chars, break_long_words=True, break_on_hyphens=False) or [""]
                out.append(lines)
            return out

        def draw(cells, bold=False):
            lines = wrapped(cells)
            left = x
            for cell, w in zip(lines, widths, strict=True):
                for k, line in enumerate(cell):
                    self.fig.text(left / _W, (self.y - k * line_h) / _H, line, fontsize=size, va="top", ha="left",
                                  weight="bold" if bold else "normal")
                left += w
            self.y -= max(len(c) for c in lines) * line_h + 0.03

        draw(headers, bold=True)
        written = 0
        for k, row in enumerate(rows):
            need = max(len(c) for c in wrapped(row)) * line_h + 0.03
            if self.room() - need < (2 * line_h if k < len(rows) - 1 else 0):
                self.text(more.replace("{count}", str(len(rows) - k)), size=size, color="0.35", x=x)
                break
            draw(row)
            written += 1
        self.y -= 0.08
        return written

    def image(self, png: bytes, x: float, top: float, width: float) -> float:
        """Immagine PNG del risultato (nessun ridisegno) larga ``width`` pollici con l'angolo in alto a sinistra in
        ``(x, top)``; restituisce l'altezza usata."""
        import matplotlib.image as mpimg

        picture = mpimg.imread(io.BytesIO(png), format="png")
        height = width * picture.shape[0] / picture.shape[1]
        ax = self.fig.add_axes((x / _W, (top - height) / _H, width / _W, height / _H))
        ax.imshow(picture, interpolation="nearest")
        ax.set_axis_off()
        return height

    def footer(self, text: str) -> None:
        y = _FOOT - 0.15
        chars = int((_W - _LEFT - _RIGHT) / (5.5 * 0.6 / 72))
        for line in textwrap.wrap(text, chars, break_long_words=True)[:9]:
            self.fig.text(_LEFT / _W, y / _H, line, fontsize=5.5, color="0.35", va="top", ha="left")
            y -= 5.5 * 1.3 / 72


def _message_line(item: Mapping, label: dict) -> str:
    """Avviso o errore del risultato come ``codice: testo``, testo dal catalogo dei messaggi nella lingua del PDF
    (codice e ``params``, D40-3; DD-3 (a)); il testo originale del modulo solo come ripiego del catalogo."""
    code = str(item.get("code") or "")
    params = item.get("params") if isinstance(item.get("params"), Mapping) else {}
    return f"{code}: {message_text(code, params, label['lang'], text=item.get('text'))}"


def _messages(section: Mapping, label: dict) -> list[str]:
    return [_message_line(item, label) for item in list(section.get("errors") or []) +
            list(section.get("warnings") or [])]


def _sources(section: Mapping, label: dict) -> str:
    """Nota delle fonti della sezione: servizi, server, tabelle, date, cache e comando (25 §3.15 punto 2)."""
    seen = {}
    entries = list(section.get("values") or [])
    for p in (section.get("details") or {}).get("points") or []:
        entries.append({"provenance": p.get("provenance") or {}})
    for t in (section.get("details") or {}).get("thumbnails") or []:
        for tile in t.get("tiles") or []:
            entries.append({"provenance": {"service": t.get("hips_id"), "server": tile.get("server"),
                                           "retrieved_at": tile.get("retrieved_at"),
                                           "from_cache": tile.get("from_cache")}})
    for e in entries:
        prov = e.get("provenance") or {}
        key = (prov.get("service"), prov.get("server"), prov.get("table"))
        dates = seen.setdefault(key, set())
        if prov.get("retrieved_at"):
            dates.add((prov["retrieved_at"], prov.get("from_cache")))
    parts = []
    for (service, server, table), dates in seen.items():
        when = ", ".join(sorted(f"{d}{' (' + label['cache'] + ')' if c else ''}" for d, c in dates))
        parts.append(" · ".join(x for x in (service, server, table, when) if x))
    command = section.get("command_id")
    head = f"{label['sources_line']} (#{command})" if command is not None else label["sources_line"]
    return head + ": " + ("; ".join(parts) if parts else "—")


def _status_lines(page: _Page, section: Mapping | None, label: dict) -> None:
    if section is None:
        page.text(label["not_requested"], size=9, color="0.35")
        return
    page.text(f"{label['status']}: {section.get('status')}  ·  {label['section_command']} "
              f"#{section.get('command_id')}", size=8, color="0.35")
    for line in _messages(section, label):
        page.text("⚠ " + line, size=7)


def _value_rows(values: Sequence[Mapping]) -> list[list[str]]:
    rows = []
    for v in values:
        notes = [x for x in (v.get("note"), v.get("formula"), v.get("reference"), v.get("interval_kind")) if x]
        rows.append([str(v.get("quantity") or ""), _num(v.get("value")), _error(v), _unit(v.get("value")),
                     "; ".join(str(n) for n in notes)])
    return rows


def _identity_page(data: Mapping, label: dict, title: str) -> _Page:
    page = _Page(f"{label['identity']} · {label['images']}", title)
    section = _section(data, "identity")
    images = _section(data, "images")
    left_width = 4.5 if images else _W - _LEFT - _RIGHT
    top = page.y
    target = data.get("target") or {}
    resolved = data.get("resolved") or {}
    page.text(f"{label['target']}: {target.get('name') or target.get('position') or target.get('origin') or ''}",
              size=7, width=left_width)
    if resolved.get("position_source"):
        page.text(f"{label['position']}: {resolved['position_source']}", size=7, width=left_width)
    warnings = data.get("warnings") or []
    for w in warnings:
        page.text("⚠ " + _message_line(w, label), size=7, width=left_width)
    _status_lines(page, section, label)
    if section is not None:
        page.table([label["quantity"], label["value"], label["error"], label["unit"]],
                   [r[:4] for r in _value_rows(section.get("values") or [])], (1.1, 1.6, 0.8, 0.9 if images else 2.0),
                   more=label["more"])
        details = section.get("details") or {}
        groups = details.get("identifiers") or {}
        if groups:
            page.text(label["identifiers"].replace("{count}", str(details.get("identifier_count", ""))), size=8,
                      bold=True, width=left_width)
            items = list(groups.items())
            for group, names in items[:30]:
                more = len(names) - 8
                page.text(f"{group}: {', '.join(names[:8])}" + (f" (+{more})" if more > 0 else ""), size=6.5,
                          width=left_width)
            if len(items) > 30:
                page.text(label["more_groups"].replace("{count}", str(len(items) - 30)), size=6.5, color="0.35",
                          width=left_width)
        chain = details.get("cross_identifications") or []
        if chain:
            page.y -= 0.05
            page.text(label["chain"], size=8, bold=True, width=left_width)
            rows = []
            for c in chain:
                notes = [c.get("note") or ""]
                if c.get("conflict"):
                    notes.append(", ".join(f"{k}: {v}" for k, v in c["conflict"].items()))
                if c.get("error"):
                    notes.append(_message_line(c["error"], label))
                rows.append([str(c.get("catalog") or ""), str(c.get("identifier") or "—"), str(c.get("method") or "—"),
                             _with_unit(c.get("separation")), "; ".join(n for n in notes if n)])
            page.table([label["catalog"], label["identifier"], label["method"], label["separation"], label["notes"]],
                       rows, (0.6, 1.6, 0.9, 0.6, 0.8) if images else (0.9, 2.0, 1.2, 0.9, 2.07),
                       more=label["more"])
    if images is not None:
        x, y = _LEFT + left_width + 0.2, top
        width = _W - _RIGHT - x
        thumbs = (images.get("details") or {}).get("thumbnails") or []
        status = f"{label['images']}: {images.get('status')}  ·  #{images.get('command_id')}"
        page.fig.text(x / _W, y / _H, status, fontsize=7, color="0.35", va="top")
        y -= 0.2
        for line in _messages(images, label):
            for piece in textwrap.wrap(line, 52) or []:
                page.fig.text(x / _W, y / _H, piece, fontsize=5.5, va="top")
                y -= 5.5 * 1.3 / 72
        for t in thumbs:
            if t.get("png"):
                y -= page.image(base64.b64decode(t["png"]), x, y, min(width, 1.75)) + 0.05
            center = t.get("center") or {}
            servers = sorted({re.sub(r"^https?://([^/]+).*$", r"\1", s) for s in t.get("servers") or []})
            credits = t.get("credits") or {}
            lines = [str(t.get("title") or t.get("hips_id") or ""),
                     f"{_with_unit(t.get('fov'))} {label['fov']} · {t.get('size')} px · HEALPix {t.get('order')}",
                     f"{label['center']} {_num(center.get('ra'))}, {_num(center.get('dec'))} deg · "
                     f"{center.get('epoch') or '—'}",
                     f"{label['tiles']} {', '.join(servers)}" if servers else "",
                     str(credits.get("obs_copyright") or "")]
            if "DSS2" in str(t.get("hips_id") or ""):
                lines.append(STSCI_DSS_TEXT[:STSCI_DSS_TEXT.index("W-2166.") + 7] + " " + STSCI_DSS_URL)  # 1ª frase
            for line in lines:
                for piece in textwrap.wrap(line, 52) or []:
                    page.fig.text(x / _W, y / _H, piece, fontsize=5.5, va="top", ha="left")
                    y -= 5.5 * 1.3 / 72
            y -= 0.1
    page.footer(" · ".join(x for x in (_sources(section, label) if section else "",
                                       _sources(images, label) if images else "") if x))
    return page


def _astrometry_page(data: Mapping, label: dict, title: str) -> _Page:
    page = _Page(label["astrometry"], title)
    section = _section(data, "astrometry")
    _status_lines(page, section, label)
    if section is not None:
        page.table([label["quantity"], label["value"], label["error"], label["unit"], label["notes"]],
                   _value_rows(section.get("values") or []), (1.4, 1.5, 1.2, 0.7, 2.27), size=7, more=label["more"])
        page.footer(_sources(section, label))
    return page


def _photometry_page(data: Mapping, label: dict, title: str) -> _Page:
    page = _Page(label["photometry"], title)
    section = _section(data, "photometry")
    _status_lines(page, section, label)
    if section is not None:
        points, vizier = _sed(data)
        if points or (vizier or {}).get("rows"):
            png = sed_rows_png(points, vizier, title=" ".join(str((data.get("resolved") or {}).get("main_id")
                                                                  or "").split()) or None)
            page.y -= page.image(png, _LEFT + 0.6, page.y, 5.8) + 0.1
        rows = []
        for p in points:
            shown = p.get("magnitude") or p.get("count_rate")
            err = p.get("magnitude_error") if p.get("magnitude") else p.get("count_rate_error")  # errore del valore
            value = "" if not shown else _with_unit(shown) + (f" ± {_num(err)}" if err else "")
            flux = "" if not p.get("flux") else _with_unit(p["flux"]) + (
                f" ± {_num(p['flux_error'])}" if p.get("flux_error") else "")
            plot = label["yes"] if p.get("in_plot") else (label["arrow"] if p.get("upper_limit") and p.get("flux")
                                                          else label["no"])
            codes = " ".join(n.get("code", "") for n in p.get("notes") or [])
            rows.append([str(p.get("catalog") or ""), str(p.get("band") or ""), str(p.get("system") or "—"), value,
                         str(p.get("quality") or "—"), _with_unit(p.get("wavelength")), flux,
                         plot + (f" ({codes})" if codes else "")])
        if rows:
            page.table([label["catalog"], label["band"], label["system"], label["value"], label["quality"],
                        label["lambda"], label["fnu"], label["plot"]], rows, (0.65, 0.4, 0.45, 1.35, 0.45, 0.75, 1.5,
                                                                             1.52), size=6, more=label["more"])
        page.footer(_sources(section, label))
    return page


def _planets_page(data: Mapping, label: dict, title: str) -> _Page:
    page = _Page(label["planets"], title)
    section = _section(data, "planets")
    _status_lines(page, section, label)
    if section is not None:
        planets = (section.get("details") or {}).get("planets") or []
        if not planets and section.get("status") in ("done", "partial"):
            page.text(label["no_planets"], size=9)
        rows = []
        for planet in planets:
            cells = [str(planet.get("pl_name") or ""),
                     f"{planet.get('discoverymethod') or '—'} {planet.get('disc_year') or ''}".strip()]
            for key in _PLANET_COLUMNS:
                par = (planet.get("parameters") or {}).get(key) or {}
                if not par.get("value"):
                    cells.append("—")
                    continue
                mark = {"upper": "< ", "lower": "> "}.get(par.get("limit"), "")
                text = f"{mark}{_with_unit(par['value'])}"
                if par.get("error_upper") or par.get("error_lower"):
                    text += f"\n+{_num(par.get('error_upper'))} / {_num(par.get('error_lower'))}"
                if key == "mass" and planet.get("pl_bmassprov"):
                    text += f"\n({planet['pl_bmassprov']})"
                cells.append(text)
            rows.append(cells)
        if rows:
            page.table([label["planet"], label["discovery"], *[label[k] for k in _PLANET_COLUMNS]], rows,
                       (0.95, 0.9, 0.85, 0.85, 0.75, 1.0, 0.9, 0.87), size=6, more=label["more"])
        page.footer(_sources(section, label))
    return page


def _sources_page(data: Mapping, label: dict, title: str) -> _Page:
    page = _Page(label["sources"], title)
    images = _section(data, "images")
    thumbs = ((images or {}).get("details") or {}).get("thumbnails") or []
    if thumbs:
        page.text(label["credits"], size=9, bold=True)
        for t in thumbs:
            credits = t.get("credits") or {}
            page.text(str(t.get("title") or t.get("hips_id") or ""), size=7, bold=True)
            for key in ("obs_copyright", "obs_copyright_url", "obs_ack"):
                if credits.get(key):
                    page.text(str(credits[key]), size=6)
            if "DSS2" in str(t.get("hips_id") or ""):
                page.text(f"{STSCI_DSS_TEXT} {STSCI_DSS_URL}", size=6)
    photometry = _section(data, "photometry")
    zps = ((photometry or {}).get("details") or {}).get("zero_points") or []
    if zps:
        page.y -= 0.05
        page.text(label["zero_points"], size=9, bold=True)
        for z in zps:
            page.text(f"{z.get('key')}: {_with_unit(z.get('value'))} ± {_num(z.get('error'))}; "
                      f"λ {z.get('wavelength_kind')} {_with_unit(z.get('wavelength'))} — {z.get('source')} "
                      f"({z.get('reference')})", size=6)
    page.y -= 0.05
    page.text(label["queries"], size=9, bold=True)
    for section in data.get("sections") or []:
        queries = {}
        for v in section.get("values") or []:
            prov = v.get("provenance") or {}
            if prov.get("query"):
                queries[prov["query"]] = prov
        for query, prov in queries.items():
            cache = f" ({label['cache']})" if prov.get("from_cache") else ""
            page.text(f"#{section.get('command_id')} {section.get('name')} · {prov.get('service')} · "
                      f"{prov.get('server')} · {prov.get('retrieved_at')}{cache}", size=6, bold=True)
            page.text(query, size=5.5, mono=True)
    page.footer(f"AstroTwo {astrotwo.__version__} · {', '.join(f'#{n}' for n in data.get('commands') or [])}")
    return page


def _write_pdf(data: Mapping, target: Path, language: str) -> int:
    from matplotlib.backends.backend_pdf import PdfPages

    label = _LABELS.get(language, _LABELS["en"])
    name = " ".join(str((data.get("resolved") or {}).get("main_id") or "").split()) or "—"
    title = label["title"].replace("{name}", name)
    subtitle = f"{title} · {', '.join(f'#{n}' for n in data.get('commands') or [])}"
    pages = [_identity_page(data, label, subtitle), _astrometry_page(data, label, subtitle),
             _photometry_page(data, label, subtitle), _planets_page(data, label, subtitle),
             _sources_page(data, label, subtitle)]
    metadata = {"Title": title, "Creator": f"AstroTwo {astrotwo.__version__}", "Producer": None,
                "CreationDate": None}
    with PdfPages(str(target), metadata=metadata) as pdf:
        for page in pages:
            pdf.savefig(page.fig)
    return len(pages)


# --------------------------------------------------------------------------
# Scrittura (25 §3.15): file temporaneo e rinomina, mai un file a metà
# --------------------------------------------------------------------------


def export_profile(data: Mapping, path: str | os.PathLike, format: str, *, language: str = "en") -> ProfileExport:
    """Scrive l'esportazione ``format`` della forma JSON unita del profilo (``merge_profile_results``)."""
    target = check_export_path(str(path), format)
    if format in ("sed_png", "sed_votable") and not _has_sed(data):
        raise _invalid("no_sed", "la sezione Fotometria non ha punti della SED")
    handle, temporary = tempfile.mkstemp(prefix=".astrotwo-export-", suffix=target.suffix, dir=target.parent)
    os.close(handle)
    temp = Path(temporary)
    rows = pages = None
    warnings: tuple = ()
    try:
        if format == "ecsv":
            table = profile_values_table(data)
            table.write(str(temp), format="ascii.ecsv", overwrite=True)
            rows = len(table)
        elif format == "pdf":
            pages = _write_pdf(data, temp, language)
        elif format == "sed_png":
            points, vizier = _sed(data)
            name = " ".join(str((data.get("resolved") or {}).get("main_id") or "").split()) or None
            temp.write_bytes(sed_rows_png(points, vizier, title=name))
        else:
            from astrotwo.core.vo_protocols import export_table

            table = sed_catalog_table(data)
            temp.unlink()
            result = export_table(table, temp, "votable")
            warnings = tuple(result.warnings)
            rows = len(table.table)
        os.replace(temp, target)
    except ProfileExportError:
        temp.unlink(missing_ok=True)
        raise
    except Exception as exc:  # noqa: BLE001 - disco pieno, permessi: un errore con il motivo, mai un file a metà
        temp.unlink(missing_ok=True)
        raise ProfileExportError("PROFILE_EXPORT_FAILED", f"{target}: file non scritto: {exc}",
                                 params={"path": str(target), "detail": str(exc)}) from exc
    content = target.read_bytes()
    return ProfileExport(target, format, hashlib.sha256(content).hexdigest(), len(content), rows, pages, warnings)

