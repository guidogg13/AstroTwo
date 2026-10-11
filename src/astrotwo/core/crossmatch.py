"""Incrocio tra cataloghi: locale, per campo, con ellissi d'errore e con il servizio CDS XMatch.

Specifica: ``mdfiles/15-core-crossmatch.md`` (stato ``approvato``).

Il modulo si scrive in 5 parti (decisione del proprietario del 2026-10-11):
P1 incrocio locale ``all``/``best``/``none`` e report; P2 tabella unita;
P3 ``crossmatch_by_field``; P4 ``crossmatch_ellipses``; P5 ``crossmatch_cds``.

Le posizioni vengono dalle colonne di posizione della ``CatalogTable`` del
modulo 13; le conversioni di sistema sono del modulo 10; le separazioni di
``astropy.coordinates``. Nessuna propagazione automatica delle epoche.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

import astropy
import astropy.units as u
import numpy as np
from astropy.coordinates import search_around_sky
from astropy.table import Table

from astrotwo.core.catalogs import CatalogTable
from astrotwo.core.coordinates_wcs import CoordinatesWcsError, SkyFrame

__all__ = [
    "CROSSMATCH_MODES",
    "CrossMatchResult",
    "CrossmatchError",
    "MatchReport",
    "crossmatch",
]

#: Modalità dell'incrocio per posizione (§3); ``best`` è il default (D15-1).
CROSSMATCH_MODES: tuple[str, ...] = ("all", "best", "none")
_LOCAL_METHOD = f"locale: astropy.coordinates.search_around_sky (astropy {astropy.__version__})"


class CrossmatchError(Exception):
    """Errore del modulo 15 con identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class MatchReport:
    """Criteri e conteggi di un incrocio (§3): accompagna sempre il risultato."""

    method: str
    mode: str
    criterion: str  # es. "max_sep = 2 arcsec"
    frame: str | None
    systems: tuple[str, str]  # sistema (con equinozio) di A e di B
    epochs: tuple[str | None, str | None]
    bodies: tuple[str | None, str | None]
    forced_body: bool
    origins: tuple[str, str]
    rows: tuple[int, int]  # righe delle due tabelle
    excluded: tuple[int, int]  # righe escluse per valori mancanti
    pairs: int
    unmatched: int | None
    best_ties: int = 0
    b_reused: int = 0
    renames: tuple[tuple[str, str], ...] = ()
    service: str | None = None
    request: object | None = None  # RequestRecord del 14 per il servizio CDS
    notes: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict:
        out = dataclasses.asdict(self)
        out["created_at"] = _iso(self.created_at)
        if self.request is not None and hasattr(self.request, "as_dict"):
            out["request"] = self.request.as_dict()
        return out

    def describe(self) -> str:
        """Testo dei criteri per l'utente (base di ``describe_match_report``)."""
        epochs = [e or "non dichiarata" for e in self.epochs]
        lines = [
            f"Metodo: {self.method}" + (f" ({self.service})" if self.service else ""),
            f"Modalità: {self.mode}; criterio: {self.criterion}",
            f"Sistema di confronto: {self.frame or '—'}; tabella A {self.systems[0]}, tabella B {self.systems[1]}",
            f"Epoche delle posizioni: A {epochs[0]}, B {epochs[1]} (nessuna propagazione automatica)",
            f"Corpo: A {self.bodies[0]}, B {self.bodies[1]}" + (" — FORZATO (force_body=True)" if self.forced_body
                                                                else ""),
            f"Righe: A {self.rows[0]} (escluse {self.excluded[0]}), B {self.rows[1]} (escluse {self.excluded[1]})",
            f"Coppie: {self.pairs}" + (f"; non appaiati: {self.unmatched}" if self.unmatched is not None else ""),
        ]
        if self.best_ties or self.b_reused:
            lines.append(f"best: {self.best_ties} righe di A con pari merito (vince l'indice più basso in B); "
                         f"{self.b_reused} righe di B scelte da più righe di A")
        if self.renames:
            lines.append("Rinomine: " + ", ".join(f"{a} → {b}" for a, b in self.renames))
        lines.extend(self.notes)
        lines.append(f"Eseguito il {_iso(self.created_at)}")
        return "\n".join(lines)


@dataclass(frozen=True, eq=False)
class CrossMatchResult:
    """Coppie (``idx_a``, ``idx_b``, ``sep``), non appaiati, report e avvisi; tiene le tabelle per ``rematch``."""

    pairs: Table
    unmatched: np.ndarray | None
    report: MatchReport
    warnings: tuple[tuple[str, str], ...]
    table_a: CatalogTable
    table_b: CatalogTable
    params: dict

    @property
    def mode(self) -> str:
        return self.report.mode

    def rematch(self, max_sep=None, threshold=None) -> CrossMatchResult:
        """Riesegue il calcolo con una soglia diversa sulle stesse tabelle (senza ricaricare i dati)."""
        runner = self.params["runner"]
        kwargs = {k: v for k, v in self.params.items() if k != "runner"}
        if max_sep is not None:
            kwargs["max_sep"] = max_sep
        if threshold is not None:
            kwargs["threshold"] = threshold
        return runner(self.table_a, self.table_b, **kwargs)


# --------------------------------------------------------------------------
# P1 — Incrocio locale, controlli d'ingresso, report
# --------------------------------------------------------------------------


def _check_table(table, which: str) -> CatalogTable:
    if not isinstance(table, CatalogTable):
        raise TypeError(f"tabella {which}: serve una CatalogTable del modulo 13 (posizioni, corpo, provenienza)")
    if table.rows > table.limits.max_rows:
        raise CrossmatchError("TABLE_TOO_LARGE", f"tabella {which}: {table.rows} righe, oltre il tetto di "
                              f"{table.limits.max_rows} (D15-3): usare il servizio CDS o l'elaborazione a blocchi",
                              rows=table.rows, max_rows=table.limits.max_rows)
    return table


def _check_bodies(a: CatalogTable, b: CatalogTable, force_body: bool) -> list[tuple[str, str]]:
    for which, t in (("A", a), ("B", b)):
        if t.body is None:
            raise CrossmatchError("BODY_UNKNOWN", f"tabella {which} ({t.origin}): corpo non ricavabile, nessun incrocio")
    if a.body != b.body:
        if not force_body:
            raise CrossmatchError("BODY_MISMATCH", f"corpi diversi: A {a.body!r}, B {b.body!r}; forzabile solo con "
                                  "force_body=True (citato nel report)")
        return [("BODY_FORCED", f"incrocio tra corpi diversi forzato: A {a.body!r}, B {b.body!r}")]
    return []


def _check_max_sep(max_sep, limit=180 * u.deg, what: str = "in locale") -> u.Quantity:
    if max_sep is None:
        raise CrossmatchError("MAX_SEP_INVALID", "max_sep obbligatorio, senza default (angolo con unità)")
    if not isinstance(max_sep, u.Quantity) or not max_sep.unit.is_equivalent(u.deg) or not max_sep.isscalar:
        raise CrossmatchError("MAX_SEP_INVALID", f"max_sep {max_sep!r}: serve un solo angolo con unità")
    value = max_sep.to(u.deg)
    if not (np.isfinite(value.value) and value.value > 0 and value <= limit):
        raise CrossmatchError("MAX_SEP_INVALID", f"max_sep {max_sep}: ammesso in (0, {limit}] {what}")
    return max_sep


def _system_text(table: CatalogTable) -> str:
    pos = table.positions
    if pos is None:
        return "—"
    return (pos.frame or "sconosciuto") + (f" equinozio {pos.equinox}" if pos.equinox else "")


def _coordinates(table: CatalogTable, which: str, frame: str):
    """(indici validi, SkyFrame nel sistema di confronto, righe escluse): conversione con il modulo 10."""
    pos = table.positions
    if pos is None:
        raise CrossmatchError("NO_COORD_COLUMNS", f"tabella {which} ({table.origin}): nessuna colonna di posizione "
                              "da UCD o confermata (modulo 13)")
    if pos.frame is None:
        raise CrossmatchError("FRAME_UNKNOWN", f"tabella {which}: colonne {pos.lon}/{pos.lat} senza sistema "
                              "dichiarato; confermarlo con confirm_position_columns (modulo 13)")
    data = table.table
    lon, lat = data[pos.lon], data[pos.lat]
    if lon.unit is None or lat.unit is None or not (lon.unit.is_equivalent(u.deg) and lat.unit.is_equivalent(u.deg)):
        raise CrossmatchError("NO_COORD_COLUMNS", f"tabella {which}: colonne {pos.lon}/{pos.lat} senza unità angolare")
    lon_v = np.ma.filled(np.ma.asarray(lon, dtype=float), np.nan)
    lat_v = np.ma.filled(np.ma.asarray(lat, dtype=float), np.nan)
    valid = np.isfinite(lon_v) & np.isfinite(lat_v)
    index = np.flatnonzero(valid)
    lon_q = (lon_v[valid] * lon.unit).to(u.deg) % (360 * u.deg)
    lat_q = (lat_v[valid] * lat.unit).to(u.deg)
    obstime = pos.epoch if pos.frame == "fk4" else None
    try:
        coords = SkyFrame.from_lonlat(lon_q, lat_q, pos.frame, equinox=pos.equinox, obstime=obstime)
        if coords.frame_name != frame:
            coords = coords.to(frame)
    except CoordinatesWcsError as exc:
        raise CrossmatchError(exc.code, f"tabella {which}: {exc.message}") from exc
    return index, coords, int(np.count_nonzero(~valid))


def _common_notes(a: CatalogTable, b: CatalogTable, excluded: tuple[int, int]) -> list[tuple[str, str]]:
    notes = []
    ea = a.positions.epoch if a.positions else None
    eb = b.positions.epoch if b.positions else None
    if ea and eb and ea != eb:
        notes.append(("EPOCH_DIFFERS", f"epoche delle posizioni diverse: A {ea}, B {eb}; nessuna propagazione "
                      "automatica (usare propagate del modulo 13)"))
    if any(excluded):
        notes.append(("COORD_MISSING", f"righe con valori mancanti escluse: A {excluded[0]}, B {excluded[1]}"))
    return notes


def _select(idx_a: np.ndarray, idx_b: np.ndarray, dist: np.ndarray, mode: str, valid_a: np.ndarray):
    """Coppie secondo la modalità sulla distanza ``dist`` (ordine stabile); (ia, ib, d, non appaiati, pari, riusati)."""
    order = np.lexsort((idx_b, dist, idx_a))
    ia, ib, d = idx_a[order], idx_b[order], dist[order]
    unmatched = None
    ties = reused = 0
    if mode == "best":
        first = np.ones(len(ia), dtype=bool)
        first[1:] = ia[1:] != ia[:-1]
        # Pari merito: la seconda candidata di A ha la stessa distanza della prima.
        second = np.zeros(len(ia), dtype=bool)
        second[1:] = (~first[1:]) & first[:-1]
        ties = int(np.count_nonzero(second & np.r_[False, d[1:] == d[:-1]]))
        ia, ib, d = ia[first], ib[first], d[first]
        counts = np.bincount(ib) if len(ib) else np.array([], dtype=int)
        reused = int(np.count_nonzero(counts > 1))
    elif mode == "none":
        unmatched = np.setdiff1d(valid_a, ia)
        ia, ib, d = ia[:0], ib[:0], d[:0]
    return ia, ib, d, unmatched, ties, reused


def _result(ia, ib, columns: dict, unmatched, report: MatchReport, notes, a, b, params) -> CrossMatchResult:
    pairs = Table({"idx_a": np.asarray(ia, dtype=np.int64), "idx_b": np.asarray(ib, dtype=np.int64), **columns})
    notes = list(notes)
    count = len(pairs) if report.mode != "none" else len(unmatched)
    if report.mode != "none" and count == 0:
        notes.append(("NO_MATCH", f"nessuna coppia entro il criterio ({report.criterion})"))
    if report.best_ties:
        notes.append(("BEST_TIE", f"{report.best_ties} righe di A con più righe di B alla stessa distanza: scelto "
                      "l'indice più basso in B"))
    if report.b_reused:
        notes.append(("B_REUSED", f"{report.b_reused} righe di B scelte come migliori da più righe di A "
                      "(incrocio non simmetrico)"))
    return CrossMatchResult(pairs=pairs, unmatched=unmatched, report=report, warnings=tuple(notes), table_a=a,
                            table_b=b, params=params)


def crossmatch(table_a: CatalogTable, table_b: CatalogTable, mode: str = "best", max_sep=None, *,
               frame: str = "icrs", force_body: bool = False) -> CrossMatchResult:
    """Incrocio locale per posizione (P1): ``all``, ``best`` (default, D15-1) o ``none``; ``max_sep`` obbligatorio.

    Calcolo: ``astropy.coordinates.search_around_sky`` sulle coordinate convertite dal modulo 10."""
    if mode not in CROSSMATCH_MODES:
        raise ValueError(f"mode {mode!r}: ammesse {', '.join(CROSSMATCH_MODES)}")
    max_sep = _check_max_sep(max_sep)
    a, b = _check_table(table_a, "A"), _check_table(table_b, "B")
    notes = _check_bodies(a, b, force_body)
    valid_a, coords_a, excl_a = _coordinates(a, "A", frame)
    valid_b, coords_b, excl_b = _coordinates(b, "B", frame)
    i1, i2, sep, _ = search_around_sky(coords_a.coord, coords_b.coord, max_sep)
    sep_arcsec = sep.to_value(u.arcsec)
    ia, ib, d, unmatched, ties, reused = _select(valid_a[i1], valid_b[i2], sep_arcsec, mode, valid_a)
    notes += _common_notes(a, b, (excl_a, excl_b))
    report = MatchReport(
        method=_LOCAL_METHOD, mode=mode, criterion=f"max_sep = {max_sep}", frame=frame,
        systems=(_system_text(a), _system_text(b)), epochs=(a.positions.epoch, b.positions.epoch),
        bodies=(a.body, b.body), forced_body=a.body != b.body, origins=(a.origin, b.origin), rows=(a.rows, b.rows),
        excluded=(excl_a, excl_b), pairs=len(ia), unmatched=None if unmatched is None else len(unmatched),
        best_ties=ties, b_reused=reused,
    )
    params = {"runner": crossmatch, "mode": mode, "max_sep": max_sep, "frame": frame, "force_body": force_body}
    return _result(ia, ib, {"sep": d * u.arcsec}, unmatched, report, notes, a, b, params)
