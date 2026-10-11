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
from astropy.table import Table, join

from astrotwo.core.catalogs import CatalogTable, PositionColumns
from astrotwo.core.coordinates_wcs import CoordinatesWcsError, SkyFrame

__all__ = [
    "CROSSMATCH_MODES",
    "CrossMatchResult",
    "CrossmatchError",
    "ColumnSuggestions",
    "MatchReport",
    "FIELD_MODES",
    "crossmatch",
    "crossmatch_by_field",
    "suggest_columns",
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
        raise CrossmatchError("KEY_COLUMN_INVALID", f"tabella {which}: colonne inesistenti {missing}")
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
                              f"{a.limits.max_rows}")
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
                raise CrossmatchError("KEY_COLUMN_INVALID", f"nome {new!r} ripetuto anche dopo prefissi e suffissi")
            out[new] = table.table[col][rows]
            out[new].meta = dict(table.table[col].meta)  # copia: la tabella d'ingresso non cambia mai
            sources.append((k, col, new))
    for name in extras:
        out[name] = result.pairs[name.removeprefix("xmatch_")]
    notes: list[tuple[str, str]] = []
    if renames:
        notes.append(("COLUMNS_RENAMED", "rinomine: " + ", ".join(f"{old} → {new}" for old, new in renames)))
    # Conflitti di UCD principali: prevale la tabella principale; l'altra perde meta.main.
    main_k = 0 if main == "a" else 1
    main_ucds = {tuple(_ucd_words((a, b)[main_k].table[col].meta.get("ucd")))
                 for k, col, _ in sources if k == main_k and "meta.main" in _ucd_words((a, b)[k].table[col].meta.get("ucd"))}
    stripped = []
    for k, col, new in sources:
        words = _ucd_words(out[new].meta.get("ucd"))
        if k != main_k and "meta.main" in words:
            if tuple(words) in main_ucds:
                notes.append(("UCD_CONFLICT", f"UCD principale {out[new].meta['ucd']!r} in entrambe le tabelle: "
                              f"prevale la tabella {'AB'[main_k]}"))
            out[new].meta["ucd"] = ";".join(w for w in str(out[new].meta["ucd"]).split(";")
                                            if w.strip().lower() != "meta.main")
            stripped.append(new)
    if stripped:
        notes.append(("MAIN_UCD_REMOVED", f"meta.main tolto dall'UCD delle colonne {stripped} (tabella non principale)"))
    owner = (a, b)[main_k]
    positions = None
    pos = owner.positions
    if pos is not None:
        names = {col: new for k, col, new in sources if k == main_k}
        if pos.lon in names and pos.lat in names:
            positions = dataclasses.replace(pos, lon=names[pos.lon], lat=names[pos.lat])
    if positions is None:
        notes.append(("NO_COORD_COLUMNS", "la tabella unita non ha le colonne di posizione della tabella principale"))
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
    notes = _check_bodies(a, b, force_body)
    for which, t, key in (("A", a, key_a), ("B", b, key_b)):
        if key not in t.colnames:
            raise CrossmatchError("KEY_COLUMN_INVALID", f"tabella {which}: colonna chiave {key!r} inesistente")
    kind_a, kind_b = _key_kind(a.table[key_a]), _key_kind(b.table[key_b])
    if kind_a is None or kind_a != kind_b:
        raise CrossmatchError("KEY_COLUMN_INVALID", f"chiavi di tipo incompatibile: A {key_a!r} "
                              f"({a.table[key_a].dtype}), B {key_b!r} ({b.table[key_b].dtype}); ammessi numeri con "
                              "numeri, testo con testo, booleani con booleani")
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
        notes.append(("KEY_MISSING", f"chiavi mancanti (mai coincidenti): A {missing[0]}, B {missing[1]}"))
    _, inverse, counts = np.unique(keys.astype(str), return_inverse=True, return_counts=True) if len(keys) \
        else (None, np.zeros(0, dtype=int), np.zeros(0, dtype=int))
    repeated = int(np.count_nonzero(counts[inverse] > 1)) if len(keys) else 0
    if repeated:
        notes.append(("KEY_REPEATED", f"{repeated} coppie da chiavi ripetute (tutte le combinazioni)"))
    unmatched = np.setdiff1d(np.flatnonzero(valid_a), ia) if mode == "none" else None
    if mode == "none":
        ia, ib = ia[:0], ib[:0]
    report = MatchReport(
        method=f"per campo: astropy.table.join (astropy {astropy.__version__})", mode=mode,
        criterion=f"A.{key_a} = B.{key_b} ({kind_a}" + (", testo senza spazi finali" if kind_a == "text" else "") + ")",
        frame=None, systems=(_system_text(a), _system_text(b)),
        epochs=(a.positions.epoch if a.positions else None, b.positions.epoch if b.positions else None),
        bodies=(a.body, b.body), forced_body=a.body != b.body, origins=(a.origin, b.origin), rows=(a.rows, b.rows),
        excluded=missing, pairs=len(ia), unmatched=None if unmatched is None else len(unmatched),
        notes=(f"combinazioni da chiavi ripetute: {repeated}",),
    )
    params = {"runner": crossmatch_by_field, "key_a": key_a, "key_b": key_b, "mode": mode, "force_body": force_body}
    return _result(ia, ib, {}, unmatched, report, notes, a, b, params)
