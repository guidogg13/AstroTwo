# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
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
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

import astropy
import astropy.units as u
import numpy as np
from astropy.coordinates import search_around_sky
from astropy.table import Table, join

from astrotwo.core.catalogs import CatalogTable, PositionColumns
from astrotwo.core.cache import NETWORK_TIMEOUTS, NetworkTimeouts
from astrotwo.core.coordinates_wcs import CoordinatesWcsError, ModuleWarning, SkyFrame

__all__ = [
    "CROSSMATCH_MODES",
    "CrossMatchResult",
    "CrossmatchError",
    "ColumnSuggestions",
    "MatchReport",
    "FIELD_MODES",
    "crossmatch",
    "crossmatch_by_field",
    "crossmatch_cds",
    "crossmatch_ellipses",
    "suggest_columns",
]

#: Modalità dell'incrocio per posizione (§3); ``best`` è il default (D15-1).
CROSSMATCH_MODES: tuple[str, ...] = ("all", "best", "none")
_LOCAL_METHOD = f"locale: astropy.coordinates.search_around_sky (astropy {astropy.__version__})"


class CrossmatchError(Exception):
    """Errore del modulo 15 con identificatore della specifica (§10).

    ``params``: valori JSON del messaggio (D40-3); la traduzione è del catalogo del 40. ``relayed``: errore di un
    modulo sotto (10, 14) rilanciato con il suo codice, il suo testo e i suoi ``params``."""

    def __init__(self, code: str, message: str, *, params: Mapping[str, object] | None = None,
                 relayed: bool = False, **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.params = dict(params or {})
        self.relayed = relayed
        self.details = details


def _relay(exc, text: str) -> CrossmatchError:
    """Errore di un modulo sotto rilanciato: codice e ``params`` restano suoi, il testo del 15 ha il prefisso."""
    return CrossmatchError(exc.code, text, params=getattr(exc, "params", None), relayed=True,
                           **getattr(exc, "details", {}))


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
    warnings: tuple[ModuleWarning, ...]
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

    def joined(self, keep_columns=None, prefixes=("", ""), suffixes=("_tab1", "_tab2"), main: str = "a") -> CatalogTable:
        """Tabella unita (P2): colonne scelte delle due tabelle, rinomine dichiarate, separazione."""
        return _joined(self, keep_columns, prefixes, suffixes, main)


# --------------------------------------------------------------------------
# P1 — Incrocio locale, controlli d'ingresso, report
# --------------------------------------------------------------------------


def _check_table(table, which: str) -> CatalogTable:
    if not isinstance(table, CatalogTable):
        raise TypeError(f"tabella {which}: serve una CatalogTable del modulo 13 (posizioni, corpo, provenienza)")
    if table.rows > table.limits.max_rows:
        raise CrossmatchError("TABLE_TOO_LARGE", f"tabella {which}: {table.rows} righe, oltre il tetto di "
                              f"{table.limits.max_rows} (D15-3): usare il servizio CDS o l'elaborazione a blocchi",
                              rows=table.rows, max_rows=table.limits.max_rows,
                              params={"reason": "crossmatch_table", "which": which, "rows": table.rows,
                                      "max_rows": table.limits.max_rows})
    return table


def _check_bodies(a: CatalogTable, b: CatalogTable, force_body: bool,
                  unknown_allowed: bool = False) -> list[ModuleWarning]:
    if unknown_allowed and (a.body is None or b.body is None):  # D15-8: join senza posizioni
        unknown = " e ".join(w for w, t in (("A", a), ("B", b)) if t.body is None)
        return [ModuleWarning("BODY_NOT_CHECKED", f"corpo non ricavabile per la tabella {unknown}: nella "
                              "correlazione per campo il corpo si controlla solo se entrambe le tabelle ne hanno uno "
                              "(D15-8)", {"tables": [w for w, t in (("A", a), ("B", b)) if t.body is None]})]
    for which, t in (("A", a), ("B", b)):
        if t.body is None:
            raise CrossmatchError("BODY_UNKNOWN", f"tabella {which} ({t.origin}): corpo non ricavabile, nessun incrocio",
                                  params={"reason": "crossmatch_table", "which": which, "origin": t.origin})
    if a.body != b.body:
        if not force_body:
            raise CrossmatchError("BODY_MISMATCH", f"corpi diversi: A {a.body!r}, B {b.body!r}; forzabile solo con "
                                  "force_body=True (citato nel report)",
                                  params={"reason": "tables", "body_a": str(a.body), "body_b": str(b.body)})
        return [ModuleWarning("BODY_FORCED", f"incrocio tra corpi diversi forzato: A {a.body!r}, B {b.body!r}",
                              {"reason": "tables", "body_a": str(a.body), "body_b": str(b.body)})]
    return []


def _check_max_sep(max_sep, limit=180 * u.deg, what: str = "in locale") -> u.Quantity:
    if max_sep is None:
        raise CrossmatchError("MAX_SEP_INVALID", "max_sep obbligatorio, senza default (angolo con unità)",
                              params={"reason": "required"})
    if not isinstance(max_sep, u.Quantity) or not max_sep.unit.is_equivalent(u.deg) or not max_sep.isscalar:
        raise CrossmatchError("MAX_SEP_INVALID", f"max_sep {max_sep!r}: serve un solo angolo con unità",
                              params={"reason": "not_angle", "max_sep": repr(max_sep)})
    value = max_sep.to(u.deg)
    if not (np.isfinite(value.value) and value.value > 0 and value <= limit):
        raise CrossmatchError("MAX_SEP_INVALID", f"max_sep {max_sep}: ammesso in (0, {limit}] {what}",
                              params={"reason": "range_local" if what == "in locale" else "range_cds",
                                      "max_sep": {"value": float(max_sep.value), "unit": str(max_sep.unit)},
                                      "limit": {"value": float(limit.value), "unit": str(limit.unit)}})
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
                              "da UCD o confermata (modulo 13)",
                              params={"reason": "crossmatch_no_positions", "which": which, "origin": table.origin})
    if pos.frame is None:
        raise CrossmatchError("FRAME_UNKNOWN", f"tabella {which}: colonne {pos.lon}/{pos.lat} senza sistema "
                              "dichiarato; confermarlo con confirm_position_columns (modulo 13)",
                              params={"reason": "crossmatch_columns", "which": which, "lon": pos.lon, "lat": pos.lat})
    data = table.table
    lon, lat = data[pos.lon], data[pos.lat]
    if lon.unit is None or lat.unit is None or not (lon.unit.is_equivalent(u.deg) and lat.unit.is_equivalent(u.deg)):
        raise CrossmatchError("NO_COORD_COLUMNS", f"tabella {which}: colonne {pos.lon}/{pos.lat} senza unità angolare",
                              params={"reason": "crossmatch_no_angular_unit", "which": which, "lon": pos.lon,
                                      "lat": pos.lat})
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
        raise _relay(exc, f"tabella {which}: {exc.message}") from exc
    return index, coords, int(np.count_nonzero(~valid))


def _common_notes(a: CatalogTable, b: CatalogTable, excluded: tuple[int, int]) -> list[ModuleWarning]:
    notes = []
    ea = a.positions.epoch if a.positions else None
    eb = b.positions.epoch if b.positions else None
    if ea and eb and ea != eb:
        notes.append(ModuleWarning("EPOCH_DIFFERS", f"epoche delle posizioni diverse: A {ea}, B {eb}; nessuna "
                                   "propagazione automatica (usare propagate del modulo 13)",
                                   {"epoch_a": str(ea), "epoch_b": str(eb)}))
    if any(excluded):
        notes.append(ModuleWarning("COORD_MISSING", f"righe con valori mancanti escluse: A {excluded[0]}, "
                                   f"B {excluded[1]}", {"excluded_a": excluded[0], "excluded_b": excluded[1]}))
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
        notes.append(ModuleWarning("NO_MATCH", f"nessuna coppia entro il criterio ({report.criterion})",
                                   {"criterion": report.criterion}))
    if report.best_ties:
        notes.append(ModuleWarning("BEST_TIE", f"{report.best_ties} righe di A con più righe di B alla stessa "
                                   "distanza: scelto l'indice più basso in B", {"count": int(report.best_ties)}))
    if report.b_reused:
        notes.append(ModuleWarning("B_REUSED", f"{report.b_reused} righe di B scelte come migliori da più righe di A "
                                   "(incrocio non simmetrico)", {"count": int(report.b_reused)}))
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


# --------------------------------------------------------------------------
# P2 — Tabella unita, colonne proposte dagli UCD
# --------------------------------------------------------------------------

_EXTRA_COLUMNS = ("sep", "mahalanobis")


def _ucd_words(ucd) -> list[str]:
    return [w.strip().lower() for w in str(ucd or "").split(";") if w.strip()]


def _kept(table: CatalogTable, chosen, which: str) -> list[str]:
    if chosen is None:
        return list(table.colnames)
    missing = [c for c in chosen if c not in table.colnames]
    if missing:
        raise CrossmatchError("KEY_COLUMN_INVALID", f"tabella {which}: colonne inesistenti {missing}",
                              params={"reason": "missing_columns", "which": which, "missing": list(missing)})
    return list(chosen)


def _joined(result: CrossMatchResult, keep_columns, prefixes, suffixes, main: str) -> CatalogTable:
    if main not in ("a", "b"):
        raise ValueError("main deve essere 'a' o 'b'")
    a, b = result.table_a, result.table_b
    cols_a, cols_b = (None, None) if keep_columns is None else keep_columns
    keep_a, keep_b = _kept(a, cols_a, "A"), _kept(b, cols_b, "B")
    none_mode = result.mode == "none"
    if none_mode:
        keep_b = []
        rows_a = np.asarray(result.unmatched, dtype=np.int64)
        rows_b = np.zeros(0, dtype=np.int64)
    else:
        rows_a = np.asarray(result.pairs["idx_a"], dtype=np.int64)
        rows_b = np.asarray(result.pairs["idx_b"], dtype=np.int64)
    if len(rows_a) > a.limits.max_rows:
        raise CrossmatchError("TABLE_TOO_LARGE", f"tabella unita di {len(rows_a)} righe, oltre il tetto di "
                              f"{a.limits.max_rows}",
                              params={"reason": "joined", "rows": int(len(rows_a)), "max_rows": a.limits.max_rows})
    extras = [f"xmatch_{n}" for n in _EXTRA_COLUMNS if n in result.pairs.colnames and not none_mode]
    conflicts = (set(keep_a) & set(keep_b)) | ((set(keep_a) | set(keep_b)) & set(extras))
    renames: list[tuple[str, str]] = []

    def name_for(col: str, k: int) -> str:
        if col not in conflicts:
            return col
        new = f"{prefixes[k]}{col}{suffixes[k]}"
        renames.append((f"{'AB'[k]}.{col}", new))
        return new

    out = Table()
    sources = []
    for k, (table, keep, rows) in enumerate(((a, keep_a, rows_a), (b, keep_b, rows_b))):
        for col in keep:
            new = name_for(col, k)
            if new in out.colnames or new in extras:
                raise CrossmatchError("KEY_COLUMN_INVALID", f"nome {new!r} ripetuto anche dopo prefissi e suffissi",
                                      params={"reason": "name_repeated", "name": new})
            out[new] = table.table[col][rows]
            out[new].meta = dict(table.table[col].meta)  # copia: la tabella d'ingresso non cambia mai
            sources.append((k, col, new))
    for name in extras:
        out[name] = result.pairs[name.removeprefix("xmatch_")]
    notes: list[ModuleWarning] = []
    if renames:
        notes.append(ModuleWarning("COLUMNS_RENAMED", "rinomine: " + ", ".join(f"{old} → {new}" for old, new in renames),
                                   {"renames": [f"{old} → {new}" for old, new in renames]}))
    # Conflitti di UCD principali: prevale la tabella principale; l'altra perde meta.main.
    main_k = 0 if main == "a" else 1
    main_ucds = {tuple(_ucd_words((a, b)[main_k].table[col].meta.get("ucd")))
                 for k, col, _ in sources if k == main_k and "meta.main" in _ucd_words((a, b)[k].table[col].meta.get("ucd"))}
    stripped = []
    for k, col, new in sources:
        words = _ucd_words(out[new].meta.get("ucd"))
        if k != main_k and "meta.main" in words:
            if tuple(words) in main_ucds:
                notes.append(ModuleWarning("UCD_CONFLICT", f"UCD principale {out[new].meta['ucd']!r} in entrambe le "
                                           f"tabelle: prevale la tabella {'AB'[main_k]}",
                                           {"ucd": str(out[new].meta["ucd"]), "table": "AB"[main_k]}))
            out[new].meta["ucd"] = ";".join(w for w in str(out[new].meta["ucd"]).split(";")
                                            if w.strip().lower() != "meta.main")
            stripped.append(new)
    if stripped:
        notes.append(ModuleWarning("MAIN_UCD_REMOVED", f"meta.main tolto dall'UCD delle colonne {stripped} "
                                   "(tabella non principale)", {"columns": list(stripped)}))
    owner = (a, b)[main_k]
    positions = None
    pos = owner.positions
    if pos is not None:
        names = {col: new for k, col, new in sources if k == main_k}
        if pos.lon in names and pos.lat in names:
            positions = dataclasses.replace(pos, lon=names[pos.lon], lat=names[pos.lat])
    if positions is None:
        notes.append(ModuleWarning("NO_COORD_COLUMNS", "la tabella unita non ha le colonne di posizione della "
                                   "tabella principale", {"reason": "joined"}))
    report = result.report
    history = (f"incrocio {report.mode} di {a.origin} (A) e {b.origin} (B): {report.criterion}; {report.method}",)
    history += tuple(f"rinomina {old} → {new}" for old, new in renames)
    return CatalogTable(
        table=out, source="crossmatch", origin=f"incrocio di {a.origin} e {b.origin}", retrieved_at=datetime.now(UTC),
        file_modified=None, format="crossmatch", table_index=0, table_name="", positions=positions, body=owner.body,
        limits=a.limits, warnings=tuple(notes) + result.warnings, history=history,
    )


@dataclass(frozen=True)
class ColumnSuggestions:
    """Colonne proposte dagli UCD (E3): posizione ed ellisse d'errore per tabella, conflitti ``meta.main``."""

    positions: tuple[PositionColumns | None, ...]
    errors: tuple[dict[str, list[str]], ...]  # ruolo ("major", "minor", "angle", "error") → colonne
    conflicts: tuple[str, ...]
    kind: str = "suggestion"


_ERROR_ROLES = (("major", "phys.size.smajaxis"), ("minor", "phys.size.sminaxis"), ("angle", "pos.posang"))


def _error_columns(table: CatalogTable) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for col in table.colnames:
        words = _ucd_words(table.table[col].meta.get("ucd"))
        erroneous = "stat.error" in words or "pos.errorellipse" in words
        if not erroneous:
            continue
        role = next((r for r, w in _ERROR_ROLES if w in words), None)
        if role is None and any(w.startswith("pos.eq") for w in words):
            role = "error"
        if role is not None:
            out.setdefault(role, []).append(col)
    return out


def suggest_columns(table_a: CatalogTable, table_b: CatalogTable | None = None) -> ColumnSuggestions:
    """Colonne di posizione (dagli UCD, modulo 13) ed errore proposte, con i conflitti di UCD ``meta.main``."""
    tables = (table_a,) if table_b is None else (table_a, table_b)
    conflicts: tuple[str, ...] = ()
    if table_b is not None:
        def mains(t):
            return {";".join(_ucd_words(t.table[c].meta.get("ucd"))) for c in t.colnames
                    if "meta.main" in _ucd_words(t.table[c].meta.get("ucd"))}
        conflicts = tuple(sorted(mains(table_a) & mains(table_b)))
    return ColumnSuggestions(positions=tuple(t.positions for t in tables),
                             errors=tuple(_error_columns(t) for t in tables), conflicts=conflicts)


# --------------------------------------------------------------------------
# P3 — Correlazione per campo (join su valori identici)
# --------------------------------------------------------------------------

#: Modalità della correlazione per campo (§3).
FIELD_MODES: tuple[str, ...] = ("pairs", "none")


def _key_kind(column) -> str | None:
    kind = column.dtype.kind
    if kind == "b":
        return "bool"
    if kind in "iuf":
        return "number"
    if kind in "US":
        return "text"
    if kind == "O" and all(isinstance(v, str) for v in np.ma.compressed(column)):
        return "text"
    return None


def _key_values(column, kind: str):
    """(valori normalizzati, maschera dei validi): testo senza spazi finali, numeri finiti, nessun mancante."""
    mask = np.ma.getmaskarray(column)
    if kind == "text":
        values = np.array([str(v).rstrip() for v in np.ma.filled(column.astype(object), "")], dtype=str)
        return values, ~mask
    if kind == "bool":
        return np.ma.filled(column, False).astype(bool), ~mask
    raw = np.ma.filled(np.ma.asarray(column), 0)
    if raw.dtype.kind == "f":
        return raw.astype(np.float64), ~mask & np.isfinite(raw)
    return raw, ~mask


def crossmatch_by_field(table_a: CatalogTable, table_b: CatalogTable, key_a: str, key_b: str, mode: str = "pairs",
                        *, force_body: bool = False) -> CrossMatchResult:
    """Correlazione per valori identici (P3, E3) con ``astropy.table.join``: ``pairs`` (join interno) o ``none``.

    Chiavi compatibili: numeri con numeri, testo con testo (senza spazi finali), booleani con booleani; le
    chiavi mancanti non coincidono mai. Chiavi ripetute: tutte le combinazioni, numero dichiarato."""
    if mode not in FIELD_MODES:
        raise ValueError(f"mode {mode!r}: ammesse {', '.join(FIELD_MODES)}")
    a, b = _check_table(table_a, "A"), _check_table(table_b, "B")
    notes = _check_bodies(a, b, force_body, unknown_allowed=True)
    for which, t, key in (("A", a, key_a), ("B", b, key_b)):
        if key not in t.colnames:
            raise CrossmatchError("KEY_COLUMN_INVALID", f"tabella {which}: colonna chiave {key!r} inesistente",
                                  params={"reason": "key_missing", "which": which, "key": str(key)})
    kind_a, kind_b = _key_kind(a.table[key_a]), _key_kind(b.table[key_b])
    if kind_a is None or kind_a != kind_b:
        raise CrossmatchError("KEY_COLUMN_INVALID", f"chiavi di tipo incompatibile: A {key_a!r} "
                              f"({a.table[key_a].dtype}), B {key_b!r} ({b.table[key_b].dtype}); ammessi numeri con "
                              "numeri, testo con testo, booleani con booleani",
                              params={"reason": "key_types", "key_a": str(key_a), "dtype_a": str(a.table[key_a].dtype),
                                      "key_b": str(key_b), "dtype_b": str(b.table[key_b].dtype)})
    values_a, valid_a = _key_values(a.table[key_a], kind_a)
    values_b, valid_b = _key_values(b.table[key_b], kind_b)
    if kind_a == "number" and (values_a.dtype.kind == "f" or values_b.dtype.kind == "f"):
        values_a, values_b = values_a.astype(np.float64), values_b.astype(np.float64)
    left = Table({"key": values_a[valid_a], "idx_a": np.flatnonzero(valid_a)})
    right = Table({"key": values_b[valid_b], "idx_b": np.flatnonzero(valid_b)})
    if len(left) and len(right):
        joined = join(left, right, keys="key", join_type="inner")
        order = np.lexsort((joined["idx_b"], joined["idx_a"]))
        ia, ib, keys = (np.asarray(joined["idx_a"])[order], np.asarray(joined["idx_b"])[order],
                        np.asarray(joined["key"])[order])
    else:
        ia = ib = np.zeros(0, dtype=np.int64)
        keys = np.zeros(0, dtype=object)
    missing = (int(np.count_nonzero(~valid_a)), int(np.count_nonzero(~valid_b)))
    if any(missing):
        notes.append(ModuleWarning("KEY_MISSING", f"chiavi mancanti (mai coincidenti): A {missing[0]}, B "
                                   f"{missing[1]}", {"missing_a": missing[0], "missing_b": missing[1]}))
    _, inverse, counts = np.unique(keys.astype(str), return_inverse=True, return_counts=True) if len(keys) \
        else (None, np.zeros(0, dtype=int), np.zeros(0, dtype=int))
    repeated = int(np.count_nonzero(counts[inverse] > 1)) if len(keys) else 0
    if repeated:
        notes.append(ModuleWarning("KEY_REPEATED", f"{repeated} coppie da chiavi ripetute (tutte le combinazioni)",
                                   {"count": repeated}))
    unmatched = np.setdiff1d(np.flatnonzero(valid_a), ia) if mode == "none" else None
    if mode == "none":
        ia, ib = ia[:0], ib[:0]
    report = MatchReport(
        method=f"per campo: astropy.table.join (astropy {astropy.__version__})", mode=mode,
        criterion=f"A.{key_a} = B.{key_b} ({kind_a}" + (", testo senza spazi finali" if kind_a == "text" else "") + ")",
        frame=None, systems=(_system_text(a), _system_text(b)),
        epochs=(a.positions.epoch if a.positions else None, b.positions.epoch if b.positions else None),
        bodies=(a.body, b.body), forced_body=None not in (a.body, b.body) and a.body != b.body,
        origins=(a.origin, b.origin), rows=(a.rows, b.rows), excluded=missing, pairs=len(ia), unmatched=None if unmatched is None else len(unmatched),
        notes=(f"combinazioni da chiavi ripetute: {repeated}",),
    )
    params = {"runner": crossmatch_by_field, "key_a": key_a, "key_b": key_b, "mode": mode, "force_body": force_body}
    return _result(ia, ib, {}, unmatched, report, notes, a, b, params)


# --------------------------------------------------------------------------
# P4 — Correlazione con ellissi d'errore (distanza di Mahalanobis, D15-5)
# --------------------------------------------------------------------------

_AXES = {"semi": "semiassi a 1σ", "full": "assi interi (2 × semiasse a 1σ)"}


def _check_threshold(threshold) -> float:
    if isinstance(threshold, u.Quantity):
        if threshold.unit != u.dimensionless_unscaled:
            raise CrossmatchError("ERROR_ELLIPSE_INVALID", f"threshold {threshold!r}: è in sigma, senza unità",
                                  params={"reason": "threshold_unit", "threshold": repr(threshold)})
        threshold = threshold.value
    if threshold is None or isinstance(threshold, bool) or not isinstance(threshold, (int, float, np.floating)):
        raise CrossmatchError("ERROR_ELLIPSE_INVALID", "threshold obbligatoria, senza default (D15-6): numero di "
                              "sigma > 0", params={"reason": "threshold_required"})
    if not (math.isfinite(float(threshold)) and float(threshold) > 0):
        raise CrossmatchError("ERROR_ELLIPSE_INVALID", f"threshold {threshold!r}: serve un numero di sigma > 0",
                              params={"reason": "threshold_value", "threshold": repr(threshold)})
    return float(threshold)


def _ellipse(table: CatalogTable, columns, which: str, rows: np.ndarray, axes: str):
    """(semiasse maggiore, minore in arcsec, angolo in radianti, righe valide) per le righe ``rows``."""
    if not isinstance(columns, (tuple, list)) or len(columns) != 3:
        raise CrossmatchError("ERROR_ELLIPSE_INVALID", f"tabella {which}: servono 3 colonne (asse maggiore, asse "
                              "minore, orientamento)", params={"reason": "three_columns", "which": which})
    out, valid = [], np.ones(len(rows), dtype=bool)
    for name in columns:
        if name not in table.colnames:
            raise CrossmatchError("ERROR_ELLIPSE_INVALID", f"tabella {which}: colonna {name!r} inesistente",
                                  params={"reason": "column_missing", "which": which, "column": str(name)})
        col = table.table[name]
        if col.unit is None or not col.unit.is_equivalent(u.deg):
            raise CrossmatchError("ERROR_ELLIPSE_INVALID", f"tabella {which}: colonna {name!r} senza unità angolare",
                                  params={"reason": "column_unit", "which": which, "column": str(name)})
        values = np.ma.filled(np.ma.asarray(col, dtype=float), np.nan)[rows]
        valid &= np.isfinite(values)
        out.append((values * col.unit).to_value(u.arcsec if len(out) < 2 else u.rad))
    major, minor, angle = out
    for k in np.flatnonzero(valid):
        problem = reason = None
        if major[k] <= 0 or minor[k] <= 0:
            reason = "axes_not_positive"
            problem = "assi negativi o nulli"
        elif minor[k] > major[k]:
            reason = "minor_larger"
            problem = "asse minore maggiore dell'asse maggiore"
        if problem:
            raise CrossmatchError("ERROR_ELLIPSE_INVALID", f"tabella {which}, riga {int(rows[k])}, colonne "
                                  f"{columns[0]}/{columns[1]}: {problem}", row=int(rows[k]),
                                  params={"reason": reason, "which": which, "row": int(rows[k]),
                                          "major": str(columns[0]), "minor": str(columns[1])})
    if axes == "full":
        major, minor = major / 2, minor / 2
    return major, minor, angle, valid


def _covariance(a, b, theta):
    """Componenti (xx, yy, xy) di Σ = a²·u·uᵀ + b²·v·vᵀ, u = (sin θ, cos θ), x verso est e y verso nord."""
    s, c = np.sin(theta), np.cos(theta)
    return a ** 2 * s ** 2 + b ** 2 * c ** 2, a ** 2 * c ** 2 + b ** 2 * s ** 2, (a ** 2 - b ** 2) * s * c


def crossmatch_ellipses(table_a: CatalogTable, table_b: CatalogTable, ellipse_a, ellipse_b, threshold=None, *,
                        axes: str | None = None, mode: str = "best", frame: str = "icrs",
                        force_body: bool = False) -> CrossMatchResult:
    """Correlazione con ellissi d'errore (P4, E3): distanza di Mahalanobis con covarianza combinata ≤ ``threshold``.

    ``threshold`` (sigma) e ``axes`` (``"semi"`` o ``"full"``) sono obbligatori, senza default (D15-6)."""
    if mode not in CROSSMATCH_MODES:
        raise ValueError(f"mode {mode!r}: ammesse {', '.join(CROSSMATCH_MODES)}")
    k = _check_threshold(threshold)
    if axes not in _AXES:
        raise CrossmatchError("ERROR_ELLIPSE_INVALID", f"axes {axes!r}: obbligatorio, 'semi' (semiassi a 1σ) o "
                              "'full' (assi interi)", params={"reason": "axes", "axes": repr(axes)})
    a, b = _check_table(table_a, "A"), _check_table(table_b, "B")
    notes = _check_bodies(a, b, force_body)
    rows_a, coords_a, excl_a = _coordinates(a, "A", frame)
    rows_b, coords_b, excl_b = _coordinates(b, "B", frame)
    ma, na, ta, ok_a = _ellipse(a, ellipse_a, "A", rows_a, axes)
    mb, nb, tb, ok_b = _ellipse(b, ellipse_b, "B", rows_b, axes)
    excl_a += int(np.count_nonzero(~ok_a))
    excl_b += int(np.count_nonzero(~ok_b))
    ca, cb = coords_a.coord[ok_a], coords_b.coord[ok_b]
    rows_a, rows_b = rows_a[ok_a], rows_b[ok_b]
    ma, na, ta, mb, nb, tb = ma[ok_a], na[ok_a], ta[ok_a], mb[ok_b], nb[ok_b], tb[ok_b]
    empty = np.zeros(0, dtype=np.int64)
    i1 = i2 = empty
    sep = np.zeros(0)
    if len(ca) and len(cb):
        # Raggio rigoroso dei candidati: d ≤ k implica |Δ| ≤ k·√(a_A,max² + a_B,max²).
        radius = min(k * math.hypot(ma.max(), mb.max()) * u.arcsec, 180 * u.deg)
        i1, i2, sep2d, _ = search_around_sky(ca, cb, radius)
        sep = sep2d.to_value(u.arcsec)
    dist = np.zeros(len(i1))
    singular = 0
    if len(i1):
        dx, dy = ca[i1].spherical_offsets_to(cb[i2])  # piano tangente in A: verso est e verso nord
        dx, dy = dx.to_value(u.arcsec), dy.to_value(u.arcsec)
        axx, ayy, axy = _covariance(ma[i1], na[i1], ta[i1])
        bxx, byy, bxy = _covariance(mb[i2], nb[i2], tb[i2])
        sxx, syy, sxy = axx + bxx, ayy + byy, axy + bxy
        det = sxx * syy - sxy ** 2
        good = np.isfinite(det) & (det > 0)
        singular = int(np.count_nonzero(~good))
        with np.errstate(divide="ignore", invalid="ignore"):
            dist = np.sqrt((syy * dx ** 2 - 2 * sxy * dx * dy + sxx * dy ** 2) / det)
        keep = good & (dist <= k)
        i1, i2, sep, dist = i1[keep], i2[keep], sep[keep], dist[keep]
    if singular:
        notes.append(ModuleWarning("ERROR_ELLIPSE_INVALID", f"{singular} coppie candidate con covarianza combinata "
                                   "singolare: escluse", {"reason": "singular", "count": singular}))
    order_sep = dict(zip(zip(rows_a[i1], rows_b[i2]), sep))
    ia, ib, d, unmatched, ties, reused = _select(rows_a[i1], rows_b[i2], dist, mode, rows_a)
    fraction = 1 - math.exp(-k * k / 2)
    notes += _common_notes(a, b, (excl_a, excl_b))
    report = MatchReport(
        method=f"ellissi d'errore: distanza di Mahalanobis con covarianza combinata (astropy {astropy.__version__}, "
               "numpy)",
        mode=mode, criterion=f"d ≤ {k:g} sigma; assi: {_AXES[axes]}", frame=frame,
        systems=(_system_text(a), _system_text(b)), epochs=(a.positions.epoch, b.positions.epoch),
        bodies=(a.body, b.body), forced_body=a.body != b.body, origins=(a.origin, b.origin), rows=(a.rows, b.rows),
        excluded=(excl_a, excl_b), pairs=len(ia), unmatched=None if unmatched is None else len(unmatched),
        best_ties=ties, b_reused=reused,
        notes=(
            f"Ellissi: A {tuple(ellipse_a)}, B {tuple(ellipse_b)}; orientamento da nord verso est.",
            "Formula: d = √(Δᵀ Σ⁻¹ Δ), Σ = Σ_A + Σ_B, Σ = a²·u·uᵀ + b²·v·vᵀ con u = (sin θ, cos θ), "
            "v = (cos θ, −sin θ), a e b semiassi a 1σ; Δ = spostamento di B rispetto ad A nel piano tangente in A "
            "(SkyCoord.spherical_offsets_to), usato per entrambe le ellissi.",
            f"In 2D la soglia di {k:g} sigma di Mahalanobis non corrisponde alla percentuale 1D: per errori "
            f"gaussiani la frazione attesa entro la soglia è 1 − exp(−k²/2) = {100 * fraction:.2f} %"
            + (" (non 99,73 %)." if k == 3 else "."),
        ),
    )
    params = {"runner": crossmatch_ellipses, "ellipse_a": ellipse_a, "ellipse_b": ellipse_b, "threshold": k,
              "axes": axes, "mode": mode, "frame": frame, "force_body": force_body}
    seps = np.array([order_sep[(x, y)] for x, y in zip(ia, ib)]) if len(ia) else np.zeros(0)
    return _result(ia, ib, {"sep": seps * u.arcsec, "mahalanobis": d}, unmatched, report, notes, a, b, params)


# --------------------------------------------------------------------------
# P5 — Incrocio con il servizio CDS XMatch (tramite il modulo 14)
# --------------------------------------------------------------------------

_ECHO_TOLERANCE_DEG = 1e-4  # il servizio restituisce RA e Dec in float32: controllo che l'indice sia quello giusto


def _upload(index: np.ndarray, coords: SkyFrame) -> Table:
    return Table({"idx": np.asarray(index, dtype=np.int64), "ra": coords.lon.to_value(u.deg).astype(np.float64),
                  "dec": coords.lat.to_value(u.deg).astype(np.float64)})


def _check_echo(answer: Table, up_a: Table, up_b: Table, url: str) -> None:
    """Ogni coppia restituita deve riportare RA e Dec caricate per quell'indice (nessun indice frainteso)."""
    for cols, upload in ((("idx", "ra", "dec"), up_a), (("idx2", "ra2", "dec2"), up_b)):
        rows = {int(i): k for k, i in enumerate(upload["idx"])}
        for k, i in enumerate(np.asarray(answer[cols[0]], dtype=np.int64)):
            pos = rows.get(int(i))
            if pos is None or abs(float(answer[cols[1]][k]) - upload["ra"][pos]) > _ECHO_TOLERANCE_DEG \
                    or abs(float(answer[cols[2]][k]) - upload["dec"][pos]) > _ECHO_TOLERANCE_DEG:
                raise CrossmatchError("SERVICE_ERROR", f"{url}: la riga {k} della risposta non corrisponde alle "
                                      f"posizioni caricate per l'indice {int(i)}",
                                      params={"reason": "echo_mismatch", "url": url, "row": k, "index": int(i)})


def crossmatch_cds(table_a: CatalogTable, table_b: CatalogTable, mode: str = "best", max_sep=None, *,
                   frame: str = "icrs", force_body: bool = False, cache=None, refresh: bool = False,
                   timeouts: NetworkTimeouts = NETWORK_TIMEOUTS) -> CrossMatchResult:
    """Incrocio con il servizio CDS XMatch (P5): si caricano solo indice, RA e Dec in ICRS (modulo 10);
    il servizio dà sempre tutte le coppie (``selection=all``, D15-9): ``best`` (a pari separazione l'indice più
    basso in B) e ``none`` si ricavano in locale con le regole dell'incrocio locale; ``max_sep`` ≤ 180″."""
    from astrotwo.core import vo_protocols as vo

    if mode not in CROSSMATCH_MODES:
        raise ValueError(f"mode {mode!r}: ammesse {', '.join(CROSSMATCH_MODES)}")
    if frame != "icrs":
        raise ValueError("il servizio CDS confronta le posizioni caricate: si caricano in ICRS (frame='icrs')")
    max_sep = _check_max_sep(max_sep, vo.XMATCH_MAX_DISTANCE, "per il servizio CDS XMatch")
    a, b = _check_table(table_a, "A"), _check_table(table_b, "B")
    notes = _check_bodies(a, b, force_body)
    valid_a, coords_a, excl_a = _coordinates(a, "A", "icrs")
    valid_b, coords_b, excl_b = _coordinates(b, "B", "icrs")
    up_a, up_b = _upload(valid_a, coords_a), _upload(valid_b, coords_b)
    selection = "all"  # D15-9: la modalità best si applica in locale con la nostra regola
    if len(up_a) and len(up_b):
        try:
            answer = vo.cds_xmatch(up_a, up_b, max_sep, selection, cache=cache, refresh=refresh, timeouts=timeouts)
        except vo.VoProtocolsError as exc:
            raise _relay(exc, exc.message) from exc
        data = answer.table.table
        _check_echo(data, up_a, up_b, vo.XMATCH_URL)
        ia = np.asarray(data["idx"], dtype=np.int64)
        ib = np.asarray(data["idx2"], dtype=np.int64)
        d = np.asarray(data["angDist"].quantity.to_value(u.arcsec) if data["angDist"].unit is not None
                       else data["angDist"], dtype=np.float64)
        request, service_notes = answer.request, list(answer.warnings)
    else:
        ia = ib = np.zeros(0, dtype=np.int64)
        d = np.zeros(0)
        request, service_notes = None, [ModuleWarning("NO_REQUEST", "una tabella non ha righe con posizione: "
                                                      "nessuna richiesta")]
    ia, ib, d, unmatched, ties, reused = _select(ia, ib, d, mode, valid_a)
    notes += service_notes + _common_notes(a, b, (excl_a, excl_b))
    extra = ()
    if mode == "best":
        extra = ("best ricavato in locale dalle coppie 'all' del servizio: per ogni riga di A la separazione minima "
                 "(angDist del servizio, 6 decimali in arcsec), a pari separazione l'indice più basso in B (D15-9).",)
    if mode == "none":
        extra = ("none ricavato dalle coppie 'all' del servizio.",)
    import astroquery

    report = MatchReport(
        method=f"servizio CDS XMatch via astroquery.xmatch (astroquery {astroquery.__version__}), selection="
               f"{selection}",
        mode=mode, criterion=f"max_sep = {max_sep}", frame="icrs", systems=(_system_text(a), _system_text(b)),
        epochs=(a.positions.epoch, b.positions.epoch), bodies=(a.body, b.body), forced_body=a.body != b.body,
        origins=(a.origin, b.origin), rows=(a.rows, b.rows), excluded=(excl_a, excl_b), pairs=len(ia),
        unmatched=None if unmatched is None else len(unmatched), best_ties=ties, b_reused=reused,
        service=vo.XMATCH_URL, request=request,
        notes=("Caricati solo indice di riga, RA e Dec in ICRS (gradi, convertiti con il modulo 10).",) + extra,
    )
    params = {"runner": crossmatch_cds, "mode": mode, "max_sep": max_sep, "frame": frame, "force_body": force_body,
              "cache": cache, "refresh": refresh, "timeouts": timeouts}
    return _result(ia, ib, {"sep": d * u.arcsec}, unmatched, report, notes, a, b, params)
