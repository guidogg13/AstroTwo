# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Incrocio per posizione nell'interfaccia (sprint B2, decisioni del proprietario del 2026-11-05, D15-10).

Specifica: ``mdfiles/42-ui-pannello-cataloghi.md`` §3.7 e ``mdfiles/40-ui-finestra-principale.md`` §3.3.

- ``CrossmatchDialog``: Data → Cross-match catalogs… e menu contestuale della tabella. Sceglie A e B tra i cataloghi
  caricati, modalità (con la spiegazione), separazione massima con unità, metodo e sistema di confronto, e mostra le
  epoche dichiarate dal 13 (mai assunte). OK → ``catalog.crossmatch`` del 05: nessun calcolo qui, i controlli
  (``MAX_SEP_INVALID``, ``NO_COORD_COLUMNS``, ``BODY_MISMATCH``, …) sono del 15 e arrivano come messaggi.
- ``CrossmatchReportDialog``: report dell'incrocio (riepilogo con le etichette nella lingua dell'interfaccia e i
  valori del 15 così come sono, avvisi dal catalogo dei messaggi, testo di ``MatchReport.describe()``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from astrotwo.core.commands import CROSSMATCH_DEFAULT_MAX_SEP, ResultMessage, time_text
from astrotwo.ui.message_view import shown_line

__all__ = ["CrossmatchDialog", "CrossmatchReportDialog", "MAX_SEP_UNITS", "epoch_of"]

# Unità proposte per la separazione massima (scelta dell'utente, D15-10 (a)); il valore passa al 05 così com'è.
MAX_SEP_UNITS = ("mas", "arcsec", "arcmin", "deg")


def epoch_of(layer) -> tuple[bool, str | None]:
    """(colonne di posizione note, epoca dichiarata dal 13 come testo o ``None``): solo lettura dei metadati."""
    positions = getattr(layer.data, "positions", None)
    if positions is None:
        return False, None
    return True, time_text(positions.epoch)


class CrossmatchDialog(QDialog):
    """Finestra "Cross-match catalogs…" (42 §3.7): parametri di ``catalog.crossmatch``."""

    def __init__(self, catalogs: Sequence, preset_a: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Cross-match catalogs"))
        self.setObjectName("crossmatchDialog")
        self.catalogs = {layer.id: layer for layer in catalogs}
        self.layer_a = QComboBox()
        self.layer_a.setObjectName("xmatchA")
        self.layer_b = QComboBox()
        self.layer_b.setObjectName("xmatchB")
        for combo in (self.layer_a, self.layer_b):
            for layer in catalogs:
                combo.addItem(f"{layer.id} · {layer.name}", layer.id)
        ids = list(self.catalogs)
        if preset_a in self.catalogs:
            self.layer_a.setCurrentIndex(ids.index(preset_a))
        others = [i for i in ids if i != self.layer_a.currentData()]
        if others:
            self.layer_b.setCurrentIndex(ids.index(others[0]))
        self.mode = QComboBox()
        self.mode.setObjectName("xmatchMode")
        self.mode.addItem(self.tr("Best match (nearest)"), "best")
        self.mode.addItem(self.tr("All pairs"), "all")
        self.mode.addItem(self.tr("Rows of A without a match"), "none")
        self.mode_help = QLabel()
        self.mode_help.setObjectName("xmatchModeHelp")
        self.mode_help.setWordWrap(True)
        self.max_sep = QDoubleSpinBox()
        self.max_sep.setObjectName("xmatchMaxSep")
        self.max_sep.setLocale(QLocale.c())  # punto decimale sempre (T7 del 40)
        self.max_sep.setDecimals(6)
        self.max_sep.setRange(0.0, 1.0e9)  # i limiti veri sono del 15 (MAX_SEP_INVALID), mai tagliati qui
        self.max_sep.setValue(float(CROSSMATCH_DEFAULT_MAX_SEP["value"]))
        self.unit = QComboBox()
        self.unit.setObjectName("xmatchUnit")
        for unit in MAX_SEP_UNITS:
            self.unit.addItem(unit, unit)
        self.unit.setCurrentIndex(MAX_SEP_UNITS.index(CROSSMATCH_DEFAULT_MAX_SEP["unit"]))
        self.method = QComboBox()
        self.method.setObjectName("xmatchMethod")
        self.method.addItem(self.tr("Local (astropy, on this computer)"), "local")
        self.method.addItem(self.tr("CDS XMatch service (network, at most 180 arcsec)"), "cds")
        self.frame = QComboBox()
        self.frame.setObjectName("xmatchFrame")
        self.frame.addItem("ICRS", "icrs")
        self.frame.addItem(self.tr("Galactic"), "galactic")
        self.epochs = QLabel()
        self.epochs.setObjectName("xmatchEpochs")
        self.epochs.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Cross-match"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        sep_row = QHBoxLayout()
        sep_row.addWidget(self.max_sep, 1)
        sep_row.addWidget(self.unit)
        form = QFormLayout()
        form.addRow(self.tr("Catalog A"), self.layer_a)
        form.addRow(self.tr("Catalog B"), self.layer_b)
        form.addRow(self.tr("Mode"), self.mode)
        form.addRow("", self.mode_help)
        form.addRow(self.tr("Maximum separation"), sep_row)
        form.addRow(self.tr("Method"), self.method)
        form.addRow(self.tr("Comparison frame"), self.frame)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.epochs)
        layout.addWidget(self.buttons)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.method.currentIndexChanged.connect(self._method_changed)
        self.layer_a.currentIndexChanged.connect(self._tables_changed)
        self.layer_b.currentIndexChanged.connect(self._tables_changed)
        self._mode_changed()
        self._method_changed()
        self._tables_changed()

    def _mode_changed(self, *_) -> None:
        texts = {
            "best": self.tr("For each row of A, the nearest row of B within the maximum separation. A row of B can "
                            "serve several rows of A; ties go to the lowest row of B."),
            "all": self.tr("Every pair within the maximum separation: a row of A or B can appear more than once."),
            "none": self.tr("Only the rows of A with no row of B within the maximum separation (rows without a "
                            "position are left out and counted)."),
        }
        self.mode_help.setText(texts[self.mode.currentData()])

    def _method_changed(self, *_) -> None:
        cds = self.method.currentData() == "cds"
        if cds:
            self.frame.setCurrentIndex(0)  # il servizio confronta posizioni ICRS
        self.frame.setEnabled(not cds)

    def _tables_changed(self, *_) -> None:
        """Epoche e colonne di posizione dichiarate dal 13: nessuna propagazione, l'avviso del 15 lo ripeterà."""
        lines = []
        known = {}
        for label, combo in (("A", self.layer_a), ("B", self.layer_b)):
            layer = self.catalogs.get(combo.currentData())
            if layer is None:
                continue
            has_positions, epoch = epoch_of(layer)
            if not has_positions:
                lines.append(self.tr("Catalog %1 has no confirmed position columns: confirm them with Columns… in "
                                     "the Table panel first.").replace("%1", label))
                continue
            known[label] = epoch
            lines.append(self.tr("Epoch of the positions of %1: %2").replace("%1", label)
                         .replace("%2", epoch if epoch is not None else self.tr("not declared")))
        if known.get("A") and known.get("B") and known["A"] != known["B"]:
            lines.append(self.tr("The epochs differ: positions are compared as they are, without propagation "
                                 "(the result will carry EPOCH_DIFFERS)."))
        self.epochs.setText("\n".join(lines))

    def params(self) -> dict:
        """Parametri di ``catalog.crossmatch`` (forma JSON del 05): valori scritti dall'utente, senza conversioni."""
        return {"layer_a": self.layer_a.currentData(), "layer_b": self.layer_b.currentData(),
                "mode": self.mode.currentData(),
                "max_sep": {"value": float(self.max_sep.value()), "unit": self.unit.currentData()},
                "method": self.method.currentData(), "frame": self.frame.currentData()}


class CrossmatchReportDialog(QDialog):
    """Report di un incrocio (42 §3.7): finestra non modale, testo selezionabile e copiabile."""

    def __init__(self, number: int | None, values: Mapping, warnings: Sequence[ResultMessage],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("crossmatchReport")
        title = self.tr("Cross-match report")
        self.setWindowTitle(title if number is None else f"{title} — #{number}")
        self.text = QPlainTextEdit()
        self.text.setObjectName("xmatchReportText")
        self.text.setReadOnly(True)
        self.text.setPlainText(self.compose(values, warnings))
        self.text.setMinimumSize(560, 360)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout = QVBoxLayout(self)
        layout.addWidget(self.text)
        layout.addWidget(buttons)

    def compose(self, values: Mapping, warnings: Sequence[ResultMessage]) -> str:
        """Riepilogo con etichette tradotte e valori del 15 così come sono (numeri mai riscritti)."""
        x = values["crossmatch"]
        report = x["report"]
        q = x["max_sep"]
        not_declared = self.tr("not declared")
        epochs = [e if e is not None else not_declared for e in report["epochs"]]
        lines = [
            self.tr("New catalog: %1 (%2 rows)").replace("%1", str(values["layer"])).replace("%2", str(x["rows"])),
            self.tr("A: %1 · %2").replace("%1", x["layer_a"]).replace("%2", x["name_a"]),
            self.tr("B: %1 · %2").replace("%1", x["layer_b"]).replace("%2", x["name_b"]),
            self.tr("Method: %1").replace("%1", report["method"] + (f" ({report['service']})"
                                                                   if report.get("service") else "")),
            self.tr("Mode: %1; maximum separation: %2 %3").replace("%1", x["mode"]).replace("%2", repr(q["value"]))
            .replace("%3", q["unit"]),
            self.tr("Comparison frame: %1; A in %2, B in %3").replace("%1", str(report["frame"]))
            .replace("%2", report["systems"][0]).replace("%3", report["systems"][1]),
            self.tr("Epochs of the positions: A %1, B %2 (no automatic propagation)").replace("%1", epochs[0])
            .replace("%2", epochs[1]),
            self.tr("Rows: A %1 (%2 without position), B %3 (%4 without position)")
            .replace("%1", str(report["rows"][0])).replace("%2", str(report["excluded"][0]))
            .replace("%3", str(report["rows"][1])).replace("%4", str(report["excluded"][1])),
        ]
        if x["mode"] == "none":
            lines.append(self.tr("Rows of A without a match: %1").replace("%1", str(x["unmatched"])))
        else:
            lines.append(self.tr("Pairs: %1").replace("%1", str(x["pairs"])))
            lines.append(self.tr("Separation column: %1 (%2)").replace("%1", str(x["separation_column"]))
                         .replace("%2", str(x["separation_unit"])))
        if report.get("forced_body"):
            lines.append(self.tr("Bodies: A %1, B %2 — overlay FORCED").replace("%1", str(report["bodies"][0]))
                         .replace("%2", str(report["bodies"][1])))
        if warnings:
            lines.append("")
            lines.append(self.tr("Warnings:"))
            lines.extend(f"• {shown_line(w)}" for w in warnings)
        lines.append("")
        lines.append(self.tr("Report of the cross-match module (text of the module):"))
        lines.append(x["report_text"])
        return "\n".join(lines)
