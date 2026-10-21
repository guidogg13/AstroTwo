# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Pannello cataloghi e tabelle (42), sprint 5a: una scheda per livello di catalogo con la tabella in sola lettura,
ordinamento, selezione sincronizzata con il cielo e riquadro del record.

Nessun valore nasce qui: le celle sono i valori della tabella del 13 (colonne di posizione scritte da
``format_coordinates`` del 10, magnitudini a 3 decimali, le altre col formato dichiarato o la rappresentazione più
breve che si rilegge identica, 42 §3.2); l'ordine delle righe mostrate è ``shown_order`` del 05 (``numpy.argsort``
stabile, scelta minore 2); il record è ``record_view`` del 13 dal risultato di ``catalog.select``. Ogni azione è un
comando del 05 (``table.sort``, ``catalog.select``, ``requested_by`` = ``mouse`` o ``keyboard``); la tabella del 13
non cambia mai (D13-5). Il modello è virtuale (``QAbstractTableModel``): le righe si leggono solo quando sono
visibili, senza copie.

I dialoghi delle colonne di posizione e di moto proprio (42 §3.5) arrivano con lo sprint 5b.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import astropy.units as u
import numpy as np
from astropy.table.pprint import get_auto_format_func
from PySide6.QtCore import QAbstractTableModel, QItemSelection, QItemSelectionModel, QModelIndex, Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QKeySequence, QPalette
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QSplitter, QStackedWidget,
                               QTableView, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from astrotwo.core.commands import shown_order

#: Testi del pannello (inglese); la finestra principale passa quelli tradotti con ``tr()`` (40 §3.9).
DEFAULT_TEXTS = {
    "missing": "missing value", "not_drawn": "not drawn in this view", "row": "row %1",
    "rows": "%1 rows", "sorted": "sorted by %1 (%2)", "ascending": "ascending", "descending": "descending",
    "table_order": "table order", "retrieved": "retrieved %1", "ucd": "UCD: %1",
    "record_empty": "Select one row to see the full record.", "record_many": "%1 rows selected.",
    "field": "Field", "value": "Value", "unit": "Unit", "ucd_header": "UCD",
    "unit_unrecognized": "unit not recognised: %1",
}

#: Segno grafico delle celle senza valore (42 §3.2): la cella resta vuota di numeri.
MISSING_MARK = "–"
#: Segno della riga non disegnata nel 41 (moto proprio mancante o posizione non valida, 42 §3.3).
NOT_DRAWN_MARK = "◌"
#: Righe formattate insieme per le colonne di posizione (una chiamata vettoriale del 10 per blocco).
FORMAT_BLOCK = 128


def _t(text: str, *args: object) -> str:
    for i, a in enumerate(args, 1):
        text = text.replace(f"%{i}", str(a))
    return text


def _tabular(font: QFont) -> QFont:
    """Cifre a larghezza fissa (``tnum``) nelle colonne numeriche (40 §3.11)."""
    font = QFont(font)
    font.setFeature(QFont.Tag("tnum"), 1)
    return font


def _plain(value: object) -> str:
    """Valore com'è nella tabella: scalari di numpy con la rappresentazione più breve che si rilegge identica."""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _full(value: object) -> str:
    """Valore pieno (42 §3.2, 02 §6): ``float64`` della tabella con tutte le cifre che lo rileggono identico."""
    if isinstance(value, (np.floating, float)):
        return repr(float(value))
    return _plain(value)


class CatalogTableModel(QAbstractTableModel):
    """Modello virtuale sulla tabella del 13 (42 §3.2) con l'ordine delle righe mostrate.

    ``layer``: livello di catalogo dello stato del 05 (tabella in ``data``, ordinamento in ``sort``);
    ``coordinate_format``: stile di "Coordinates shown" del 40 (``view.set_coordinate_display``)."""

    def __init__(self, layer, coordinate_format: str = "sexagesimal", texts: Mapping[str, str] = DEFAULT_TEXTS,
                 parent=None) -> None:
        super().__init__(parent)
        self.texts = texts
        self.drawn: np.ndarray | None = None  # righe disegnate nel 41 (None = non ancora note)
        self._layer = None
        self.set_layer(layer, coordinate_format)

    # --- stato -------------------------------------------------------------------------

    def set_layer(self, layer, coordinate_format: str = "sexagesimal") -> None:
        """Tabella, ordinamento e stile delle coordinate dal livello; il modello si ricostruisce solo se cambiano."""
        old = self._layer
        same_table = old is not None and old.data is layer.data
        if same_table and old.sort == layer.sort and coordinate_format == self.coordinate_format:
            self._layer = layer
            return
        self.beginResetModel()
        self._layer = layer
        self.coordinate_format = coordinate_format
        self.catalog = layer.data
        self.table = layer.data.table
        self.names = list(self.table.colnames)
        if not same_table or old.sort != layer.sort:
            self.order = shown_order(self.table, layer.sort)
            self._inverse = None
        self._kinds = [self._kind(name) for name in self.names]
        self._formatted: dict[tuple[int, int], tuple[str, ...]] = {}
        self.endResetModel()

    @property
    def layer(self):
        return self._layer

    def set_drawn(self, rows: np.ndarray | None) -> None:
        """Righe disegnate nel 41 sulla base corrente (``CatalogPoints.rows``), per il segno "non disegnata"."""
        if rows is None:
            drawn = None
        else:
            drawn = np.zeros(len(self.table), dtype=bool)
            drawn[np.asarray(rows, dtype=np.int64)] = True
        if (drawn is None) != (self.drawn is None) or (drawn is not None and not np.array_equal(drawn, self.drawn)):
            self.drawn = drawn
            if self.rowCount():
                self.headerDataChanged.emit(Qt.Orientation.Vertical, 0, self.rowCount() - 1)

    def _kind(self, name: str) -> tuple:
        """Come si scrive la colonna (42 §3.2): posizione (10), magnitudine (3 decimali), formato dichiarato o com'è."""
        column = self.table[name]
        pos = self.catalog.positions
        unit = column.unit
        if pos is not None and pos.frame is not None and name in (pos.lon, pos.lat) and unit is not None \
                and unit.is_equivalent(u.deg) and getattr(column, "ndim", 1) == 1:
            axis = "lon" if name == pos.lon else "lat"
            return ("position", axis, pos.frame)
        ucd = (column.meta.get("ucd") or "").strip().lower()
        if ucd.startswith("phot.mag") and column.dtype.kind in "iuf" and getattr(column, "ndim", 1) == 1:
            return ("mag",)
        fmt = column.info.format
        if fmt:
            return ("declared", get_auto_format_func(column), fmt)
        return ("plain",)

    def table_row(self, shown: int) -> int:
        return int(self.order[shown])

    def shown_row(self, row: int) -> int:
        """Posizione nella tabella mostrata della riga ``row`` della tabella del 13."""
        if self._inverse is None:
            self._inverse = np.empty(len(self.order), dtype=np.int64)
            self._inverse[self.order] = np.arange(len(self.order))
        return int(self._inverse[row])

    # --- valori ------------------------------------------------------------------------

    def _missing(self, column, row: int) -> bool:
        mask = getattr(column, "mask", None)
        return bool(np.all(mask[row])) if mask is not None and np.ndim(mask) else False  # array: tutto mancante

    def value(self, shown: int, col: int):
        """Valore della tabella (``None`` se mancante) alla riga mostrata ``shown``."""
        column = self.table[self.names[col]]
        row = self.table_row(shown)
        return None if self._missing(column, row) else column[row]

    def cell_text(self, shown: int, col: int) -> str:
        """Testo mostrato nella cella (42 §3.2); ``MISSING_MARK`` per i valori mancanti."""
        value = self.value(shown, col)
        if value is None:
            return MISSING_MARK
        kind = self._kinds[col]
        if kind[0] == "position":
            return self._position_text(shown, col, kind)
        if kind[0] == "mag":
            return f"{float(value):.3f}"
        if kind[0] == "declared":
            try:
                return kind[1](kind[2], value).strip()
            except (TypeError, ValueError):
                return _plain(value)
        return _plain(value)

    def _position_text(self, shown: int, col: int, kind: tuple) -> str:
        """Colonne di posizione con ``format_coordinates`` del 10 nel frame della colonna, a blocchi di righe."""
        from astrotwo.core.coordinates_wcs import format_coordinates

        block = shown // FORMAT_BLOCK
        texts = self._formatted.get((col, block))
        if texts is None:
            column = self.table[self.names[col]]
            first = block * FORMAT_BLOCK
            rows = self.order[first:first + FORMAT_BLOCK]
            data = np.asarray(getattr(column, "data", column), dtype=np.float64)[rows]
            mask = np.zeros(rows.size, dtype=bool)
            if getattr(column, "mask", None) is not None and np.ndim(column.mask):
                mask = np.asarray(column.mask, dtype=bool)[rows]
            ok = ~mask & np.isfinite(data)
            out = [MISSING_MARK] * rows.size
            if ok.any():
                try:
                    formatted = format_coordinates(values=data[ok] * column.unit, frame=kind[2], axis=kind[1],
                                                   style=self.coordinate_format)
                    for i, text in zip(np.flatnonzero(ok), getattr(formatted, kind[1]), strict=True):
                        out[i] = str(text)
                except Exception:  # noqa: BLE001 - frame o valori che il 10 rifiuta: valori come sono
                    for i in np.flatnonzero(ok):
                        out[i] = _plain(column[rows[i]])
            for i in np.flatnonzero(~ok):
                if not mask[i]:
                    out[i] = _plain(column[rows[i]])  # NaN o infinito: scritto com'è
            texts = tuple(out)
            self._formatted[(col, block)] = texts
        return texts[shown - block * FORMAT_BLOCK]

    def full_text(self, shown: int, col: int) -> str:
        """Valore pieno con l'unità (suggerimento e copia, 42 §3.2); stringa vuota se mancante."""
        value = self.value(shown, col)
        if value is None:
            return ""
        unit = self.table[self.names[col]].unit
        text = _full(value)
        return f"{text} {unit}" if unit is not None and str(unit) else text

    def header_unit(self, col: int) -> str:
        """Unità nell'intestazione: quella della colonna; per le posizioni quella del testo del 10."""
        kind = self._kinds[col]
        if kind[0] == "position":
            if self.coordinate_format == "decimal":
                return "deg"
            from astrotwo.core.coordinates_wcs import format_coordinates
            probe = format_coordinates(values=np.zeros(1) * u.deg, frame=kind[2], axis=kind[1])
            precision = probe.lon_precision if kind[1] == "lon" else probe.lat_precision
            return "h m s" if precision is not None and precision.unit.physical_type == "time" else "° ′ ″"
        unit = self.table[self.names[col]].unit
        return "" if unit is None else str(unit)

    # --- QAbstractTableModel --------------------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802 - nome di Qt
        return 0 if parent.isValid() else len(self.order)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802 - nome di Qt
        return 0 if parent.isValid() else len(self.names)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        shown, col = index.row(), index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return self.cell_text(shown, col)
        if role == Qt.ItemDataRole.ToolTipRole:
            full = self.full_text(shown, col)
            return full if full else self.texts["missing"]
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return self.full_text(shown, col) or self.texts["missing"]
        if role == Qt.ItemDataRole.ForegroundRole and self.value(shown, col) is None:
            return QGuiApplication.palette().color(QPalette.ColorRole.PlaceholderText)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            numeric = self.table[self.names[col]].dtype.kind in "iuf" or self._kinds[col][0] == "position"
            return int((Qt.AlignmentFlag.AlignRight if numeric else Qt.AlignmentFlag.AlignLeft)
                       | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Vertical:
            if section >= len(self.order):
                return None
            row = self.table_row(section)
            not_drawn = self.drawn is not None and not self.drawn[row]
            if role == Qt.ItemDataRole.DisplayRole:
                return f"{row} {NOT_DRAWN_MARK}" if not_drawn else str(row)  # riga della tabella del 13
            if role == Qt.ItemDataRole.ToolTipRole:
                return _t(self.texts["row"], row) + (f" · {self.texts['not_drawn']}" if not_drawn else "")
            return None
        if section >= len(self.names):
            return None
        name = self.names[section]
        if role == Qt.ItemDataRole.DisplayRole:
            unit = self.header_unit(section)
            return f"{name}\n{unit}" if unit else name
        if role == Qt.ItemDataRole.ToolTipRole:
            column = self.table[name]
            lines = [name]
            if column.unit is not None:
                lines[0] += f" [{column.unit}]"
            ucd = column.meta.get("ucd")
            if ucd:
                lines.append(_t(self.texts["ucd"], ucd))
            if column.description:
                lines.append(str(column.description))
            return "\n".join(lines)
        return None

    def flags(self, index: QModelIndex):
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable if index.isValid() else Qt.ItemFlag.NoItemFlags


class _TableView(QTableView):
    """Vista della tabella: ⌘C copia le righe selezionate con il valore pieno (42 §3.2)."""

    def keyPressEvent(self, event) -> None:  # noqa: N802 - nome di Qt
        if event.matches(QKeySequence.StandardKey.Copy):
            QGuiApplication.clipboard().setText(self.copy_text())
            return
        super().keyPressEvent(event)

    def copy_text(self) -> str:
        """Intestazione (nome e unità) e righe selezionate nell'ordine mostrato, valori pieni separati da tab."""
        model = self.model()
        shown = sorted({i.row() for i in self.selectionModel().selectedRows()})
        header = "\t".join(f"{n} [{model.table[n].unit}]" if model.table[n].unit is not None else n
                           for n in model.names)
        lines = [header]
        for r in shown:
            values = []
            for c in range(model.columnCount()):
                value = model.value(r, c)
                values.append("" if value is None else _full(value))
            lines.append("\t".join(values))
        return "\n".join(lines)


class CatalogTab(QWidget):
    """Una scheda: riga della sorgente, tabella e riquadro del record (42 §3.2–§3.4)."""

    def __init__(self, panel: CatalogPanel, layer, coordinate_format: str) -> None:
        super().__init__(panel)
        self.panel = panel
        self.layer_id = layer.id
        texts = panel.texts
        self.info = QLabel(self)
        self.info.setObjectName("catalogInfo")
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.model = CatalogTableModel(layer, coordinate_format, texts, self)
        self.view = _TableView(self)
        self.view.setObjectName("catalogTable")
        self.view.setModel(self.model)
        self.view.setFont(_tabular(self.view.font()))
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setShowGrid(False)
        self.view.setWordWrap(False)
        self.view.setCornerButtonEnabled(False)
        vertical = self.view.verticalHeader()
        vertical.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)  # nessuna misura riga per riga (1 milione)
        vertical.setDefaultSectionSize(24)
        vertical.setDefaultAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header = self.view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setHighlightSections(False)
        header.sectionClicked.connect(self._header_clicked)
        self.view.selectionModel().selectionChanged.connect(self._selection_changed)
        self.record_title = QLabel(self)
        self.record_title.setObjectName("recordTitle")
        self.record_title.setWordWrap(True)
        self.record = QTableWidget(0, 4, self)
        self.record.setObjectName("recordTable")
        self.record.setHorizontalHeaderLabels([texts["field"], texts["value"], texts["unit"], texts["ucd_header"]])
        self.record.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.record.verticalHeader().setVisible(False)
        self.record.verticalHeader().setDefaultSectionSize(22)
        self.record.setShowGrid(False)
        self.record.setFont(_tabular(self.record.font()))
        self.record.horizontalHeader().setStretchLastSection(True)
        record_box = QWidget(self)
        rb = QVBoxLayout(record_box)
        rb.setContentsMargins(8, 4, 0, 0)
        rb.setSpacing(4)
        rb.addWidget(self.record_title)
        rb.addWidget(self.record, 1)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.addWidget(self.view)
        self.splitter.addWidget(record_box)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        top = QHBoxLayout()
        top.setContentsMargins(8, 4, 8, 4)
        top.addWidget(self.info, 1)
        box.addLayout(top)
        box.addWidget(self.splitter, 1)
        self._syncing = False
        self._pending: tuple[int, ...] | None = None  # selezione chiesta con catalog.select, non ancora nello stato
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)  # una sola richiesta a fine gesto (clic, ⇧, ⌘, trascinamento)
        self._timer.timeout.connect(self._submit_selection)
        self.record_shown: tuple[int, list] | None = None
        self.show_record(None)
        self._fit_columns()
        self.update_layer(layer, coordinate_format)

    # --- stato -------------------------------------------------------------------------

    def update_layer(self, layer, coordinate_format: str) -> None:
        self._syncing = True
        try:
            self.model.set_layer(layer, coordinate_format)
        finally:
            self._syncing = False
        sort = layer.sort
        header = self.view.horizontalHeader()
        header.blockSignals(True)
        if sort is None:
            header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        else:
            header.setSortIndicator(self.model.names.index(sort["column"]), Qt.SortOrder.AscendingOrder
                                    if sort["direction"] == "ascending" else Qt.SortOrder.DescendingOrder)
        header.blockSignals(False)
        self._show_info(layer)
        if self._pending is not None:
            if tuple(layer.selection) == self._pending:
                self._pending = None
            else:
                return  # la selezione chiesta dall'utente arriva con il suo comando
        self.apply_selection(layer.selection)

    def _show_info(self, layer) -> None:
        t = self.panel.texts
        catalog = layer.data
        parts = [layer.name, catalog.source]
        if catalog.origin and catalog.origin != catalog.source:
            parts.append(catalog.origin)
        if catalog.retrieved_at is not None:
            parts.append(_t(t["retrieved"], catalog.retrieved_at.isoformat(timespec="seconds")))
        parts.append(_t(t["rows"], len(catalog.table)))
        sort = layer.sort
        parts.append(t["table_order"] if sort is None else _t(t["sorted"], sort["column"], t[sort["direction"]]))
        self.info.setText(" · ".join(str(p) for p in parts if p))

    def _fit_columns(self) -> None:
        """Larghezze iniziali da intestazione e prime righe (mai tutta la tabella)."""
        metrics = self.view.fontMetrics()
        sample = min(self.model.rowCount(), 50)
        for c in range(self.model.columnCount()):
            texts = str(self.model.headerData(c, Qt.Orientation.Horizontal)).split("\n")
            texts += [self.model.cell_text(r, c) for r in range(sample)]
            width = max(metrics.horizontalAdvance(s) for s in texts) + 28
            self.view.setColumnWidth(c, min(max(width, 56), 320))

    def apply_selection(self, rows) -> None:
        """Selezione della vista dallo stato (righe della tabella del 13), a intervalli contigui di righe mostrate."""
        selection = QItemSelection()
        shown = np.sort(np.fromiter((self.model.shown_row(r) for r in rows), dtype=np.int64, count=len(rows)))
        if shown.size:
            breaks = np.flatnonzero(np.diff(shown) != 1) + 1
            last = self.model.columnCount() - 1
            for run in np.split(shown, breaks):
                selection.select(self.model.index(int(run[0]), 0), self.model.index(int(run[-1]), last))
        self._syncing = True
        try:
            self.view.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        finally:
            self._syncing = False

    def selected_rows(self) -> list[int]:
        """Righe della tabella del 13 selezionate, nell'ordine mostrato."""
        shown = sorted({i.row() for i in self.view.selectionModel().selectedRows()})
        return [self.model.table_row(r) for r in shown]

    def scroll_to_row(self, row: int) -> None:
        self.view.scrollTo(self.model.index(self.model.shown_row(row), 0),
                           QAbstractItemView.ScrollHint.EnsureVisible)

    # --- azioni (comandi del 05) ---------------------------------------------------------

    def _header_clicked(self, section: int) -> None:
        """Clic sull'intestazione → ``table.sort``: salita, poi discesa sulla stessa colonna."""
        column = self.model.names[section]
        sort = self.model.layer.sort
        direction = "descending" if sort == {"column": column, "direction": "ascending"} else "ascending"
        self.panel.submit("table.sort", {"layer": self.layer_id, "column": column, "direction": direction},
                          source="mouse")

    def _selection_changed(self, *_) -> None:
        if not self._syncing:
            self._timer.start()

    def _submit_selection(self) -> None:
        rows = tuple(self.selected_rows())
        current = self.model.layer.selection
        if self._pending is None and set(rows) == set(current):
            return
        self._pending = rows
        self.panel.submit("catalog.select", {"layer": self.layer_id, "rows": list(rows)}, source="mouse")

    def selection_failed(self) -> None:
        self._pending = None
        self.apply_selection(self.model.layer.selection)

    # --- record (42 §3.4) ----------------------------------------------------------------

    def show_record(self, values: Mapping | None, selected: int = 0) -> None:
        """Riquadro del record dal risultato di ``catalog.select`` (``source.record`` = ``record_view`` del 13)."""
        t = self.panel.texts
        card = None if values is None else values.get("source")
        self.record.setRowCount(0)
        if card is None:
            self.record_shown = None
            self.record_title.setText(_t(t["record_many"], selected) if selected > 1 else t["record_empty"])
            return
        row = int(card["row"])
        name = card["name"]["value"] or _t(t["row"], row)
        title = name if card["name"]["value"] is None else f"{name} · {_t(t['row'], row)}"
        drawn = self.model.drawn
        if drawn is not None and not drawn[row]:
            title += f" · {NOT_DRAWN_MARK} {t['not_drawn']}"
        self.record_title.setText(title)
        record = list(card["record"])
        self.record_shown = (row, record)
        self.record.setRowCount(len(record))
        muted = QGuiApplication.palette().color(QPalette.ColorRole.PlaceholderText)
        for i, field in enumerate(record):
            value = field["value"]
            missing = field["missing"] or value is None
            text = MISSING_MARK if missing else _full(value)
            unit = field["unit"] or ""
            if field.get("unit_unrecognized"):
                unit = _t(t["unit_unrecognized"], field["unit_unrecognized"])
            cells = (field["name"], text, unit, field["ucd"] or "")
            for c, cell in enumerate(cells):
                item = QTableWidgetItem(str(cell))
                if c == 1 and missing:
                    item.setForeground(muted)
                    item.setToolTip(t["missing"])
                self.record.setItem(i, c, item)
        self.record.resizeColumnsToContents()


class CatalogPanel(QWidget):
    """Pannello in basso (42): una scheda per livello di catalogo del 41; senza cataloghi lo stato vuoto del 40."""

    def __init__(self, submit: Callable[..., int], viewer=None, empty: QWidget | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("catalogPanel")
        self.submit = submit
        self.viewer = viewer
        self.texts: Mapping[str, str] = DEFAULT_TEXTS  # tradotti dalla finestra principale (40)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("catalogTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        self.stack = QStackedWidget(self)
        self.stack.addWidget(empty if empty is not None else QWidget(self))
        self.stack.addWidget(self.tabs)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.stack)
        self.pages: dict[str, CatalogTab] = {}
        self.state = None
        if viewer is not None:
            viewer.layers_drawn.connect(self.refresh_drawn)

    def tab(self, layer_id: str) -> CatalogTab | None:
        return self.pages.get(layer_id)

    def show_state(self, state) -> None:
        """Schede dallo stato: una per livello di catalogo, chiuse quando il livello è rimosso (42 §10)."""
        self.state = state
        layers = state.of_kind("catalog")
        fmt = state.view.coordinate_format
        ids = [layer.id for layer in layers]
        for layer_id in [i for i in self.pages if i not in ids]:
            page = self.pages.pop(layer_id)
            self.tabs.removeTab(self.tabs.indexOf(page))
            page.deleteLater()
        for layer in layers:
            page = self.pages.get(layer.id)
            if page is None:
                page = CatalogTab(self, layer, fmt)
                self.pages[layer.id] = page
                self.tabs.addTab(page, layer.name)
                self.tabs.setCurrentWidget(page)  # il catalogo appena aperto in primo piano
            else:
                page.update_layer(layer, fmt)
            index = self.tabs.indexOf(page)
            self.tabs.setTabText(index, layer.name)
            self.tabs.setTabToolTip(index, f"{layer.id} · {layer.data.source}")
        self.stack.setCurrentIndex(1 if layers else 0)
        self.refresh_drawn()

    def refresh_drawn(self) -> None:
        """Segno "non disegnata" dalle posizioni che il 41 ha disegnato sulla base corrente."""
        if self.viewer is None or self.state is None:
            return
        for layer in self.state.of_kind("catalog"):
            page = self.pages.get(layer.id)
            if page is None:
                continue
            points = self.viewer.points_for(layer) if layer.visible else None
            page.model.set_drawn(None if points is None else points.rows)

    def command_finished(self, name: str, status: str, values: Mapping, state) -> None:
        """Dopo ogni comando: schede dallo stato; dopo ``catalog.select`` scheda in primo piano, prima riga
        selezionata visibile e record (42 §3.3, §3.4)."""
        if name == "catalog.select" and status != "ok":
            for page in self.pages.values():
                if page._pending is not None:
                    page.selection_failed()
        self.show_state(state)
        if name != "catalog.select" or status != "ok":
            return
        page = self.pages.get(values["layer"])
        if page is None:
            return
        selected = values["selected"]
        page._pending = None
        page.apply_selection(selected)
        page.show_record(values, len(selected))
        if selected:
            self.tabs.setCurrentWidget(page)
            page.scroll_to_row(int(selected[0]))
