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

import io
import os
import warnings
from datetime import UTC, datetime
from pathlib import Path

import astropy
import numpy as np
from astropy.io import ascii as astropy_ascii
from astropy.io import fits
from astropy.table import Table

import astrotwo
from astrotwo.core.catalogs import (
    CatalogsError,
    CatalogTable,
    TableLimits,
    _catalog_votable,
    detect_table_format,
    read_table,
)

__all__ = [
    "EXPORT_FORMATS",
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

#: Formati di esportazione (D13).
EXPORT_FORMATS: tuple[str, ...] = ("csv", "votable", "fits")
#: Versione dei VOTable scritti (D14-9 punto 9).
VOTABLE_VERSION = "1.4"
_FORMAT_VERSIONS = {
    "votable": f"VOTable {VOTABLE_VERSION}",
    "fits": f"FITS (scritto con astropy.io.fits {astropy.__version__})",
    "csv": "CSV (RFC 4180)",
}


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


def write_votable(table: CatalogTable, path, overwrite: bool = False) -> Path:
    """Scrive un VOTable 1.4 con provenienza: ``export_table(table, path, "votable")``."""
    return export_table(table, path, "votable", overwrite=overwrite)


def _provenance(table: CatalogTable, fmt: str) -> dict[str, str]:
    """Provenienza comune ai tre formati (stesse chiavi, D14-9 punto 9)."""
    info = {
        "A2VERS": f"AstroTwo {astrotwo.__version__}",
        "A2FORMAT": _FORMAT_VERSIONS[fmt],
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
    # D14-10 (da decidere): nessuna unità nel CSV, solo provenienza e valori.
    lines = [f"# {name} = {value}" for name, value in info.items()]
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.write(buffer.getvalue())


def export_table(table: CatalogTable, path, format: str, overwrite: bool = False) -> Path:
    """Salva una tabella in CSV, VOTable o FITS con origine, data, versione di AstroTwo e del formato."""
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
    {"votable": _write_votable_file, "fits": _write_fits_file, "csv": _write_csv_file}[format](table, target, info)
    return target
