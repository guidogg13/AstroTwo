# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Cone search e query ADQL nell'interfaccia (sprint B3, decisioni del proprietario del 2026-11-06).

Specifica: ``mdfiles/42-ui-pannello-cataloghi.md`` §3.8 e ``mdfiles/40-ui-finestra-principale.md`` §3.3.

- ``ConeSearchDialog``: Data → Cone search…; servizio SCS dall'elenco del 14 o URL scritto, centro (vista, sorgente
  selezionata, coordinate scritte con sistema ed epoca), raggio con unità, righe massime. OK →
  ``catalog.cone_search`` del 05.
- ``AdqlQueryDialog``: Data → ADQL query…; servizio TAP dall'elenco o URL, editor a larghezza fissa, esempi,
  "Inserisci centro e raggio della vista", ``validate_adql`` del 14 con la posizione evidenziata, sincrona o
  asincrona, righe massime (``MAXREC``). OK → ``catalog.tap_query`` del 05.

Nessun calcolo qui: i campi diventano i parametri dei comandi; la conversione del centro della vista in ICRS è del 10
(``SkyFrame.to``), i controlli dei valori sono del 05 e del 14 e arrivano come messaggi.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import urlparse

import astropy.units as u
from PySide6.QtCore import QLocale, Signal
from PySide6.QtGui import QColor, QFontDatabase, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from astrotwo.core.commands import ResultMessage, TAP_DEFAULT_ASYNC_TIMEOUT, parse_typed_position, time_text
from astrotwo.core.vo_protocols import DEFAULT_MAX_ROWS, validate_adql
from astrotwo.ui.message_view import shown_line

__all__ = ["ADQL_EXAMPLES", "AdqlQueryDialog", "ConeSearchDialog", "RADIUS_UNITS", "TYPED_FRAMES",
           "VIEW_COMMENT_PREFIX", "insert_view_circle"]

# Unità del raggio della cone search (scelta dell'utente); il valore passa al 05 così com'è.
RADIUS_UNITS = ("arcsec", "arcmin", "deg")
# Sistemi delle coordinate scritte (D42-2 (9)): frame di astropy ed equinozio dichiarato (FK5 sempre J2000.0).
TYPED_FRAMES = (("icrs", None), ("fk5", "J2000.0"), ("galactic", None))
_EPOCH = re.compile(r"[JB]\d+(\.\d+)?")
# Inizio della riga di commento scritta da "Inserisci centro e raggio della vista" (in inglese: lingua della query).
VIEW_COMMENT_PREFIX = "-- CIRCLE: view centre and radius"
_CIRCLE = re.compile(r"CIRCLE\s*\(\s*'ICRS'\s*,\s*([^,()]+?)\s*,\s*([^,()]+?)\s*,\s*([^,()]+?)\s*\)", re.IGNORECASE)
_MANUAL = "__manual__"

# Esempi ADQL per i servizi TAP dell'elenco del 14 (D42-2 (7)): scritti da Claude Code il 2026-11-06, centrati sulle
# Pleiadi (M45), senza TOP (decide ``max_rows``, troncamento dichiarato). Provati sui servizi veri il 2026-11-06:
# Gaia ESA, IRSA, HEASARC, MAST; SIMBAD e VizieR (CDS) non raggiungibili quel giorno (solo validati offline).
ADQL_EXAMPLES: dict[str, tuple[tuple[str, str], ...]] = {
    "esa-gaia-tap": (
        ("gaia_circle", "SELECT source_id, ra, dec, parallax, pmra, pmdec, phot_g_mean_mag, bp_rp\n"
                        "FROM gaiadr3.gaia_source\n"
                        "WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', 56.75, 24.1167, 0.5))\n"
                        "  AND phot_g_mean_mag < 15\n"
                        "ORDER BY phot_g_mean_mag"),
    ),
    "cds-simbad-tap": (
        ("simbad_type", "SELECT main_id, ra, dec, otype, sp_type\n"
                        "FROM basic\n"
                        "WHERE otype = 'Star..'\n"
                        "  AND 1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', 56.75, 24.1167, 1.0))"),
    ),
    "cds-vizier-tap": (
        ("vizier_2mass", "SELECT \"2MASS\", RAJ2000, DEJ2000, Jmag, Hmag, Kmag\n"
                         "FROM \"II/246/out\"\n"
                         "WHERE 1 = CONTAINS(POINT('ICRS', RAJ2000, DEJ2000), CIRCLE('ICRS', 56.75, 24.1167, 0.1))"),
    ),
    "nasa-irsa-tap": (
        ("irsa_allwise", "SELECT designation, ra, dec, w1mpro, w2mpro, w3mpro, w4mpro\n"
                         "FROM allwise_p3as_psd\n"
                         "WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', 56.75, 24.1167, 0.1))"),
    ),
    "nasa-heasarc-tap": (
        ("heasarc_rass", "SELECT name, ra, dec, count_rate, exposure\n"
                         "FROM rassbsc\n"
                         "WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', 56.75, 24.1167, 2.0))"),
    ),
    "nasa-mast-caom-tap": (
        ("mast_obscore", "SELECT obs_collection, instrument_name, obs_id, target_name, s_ra, s_dec, t_exptime\n"
                         "FROM ivoa.obscore\n"
                         "WHERE 1 = CONTAINS(POINT('ICRS', s_ra, s_dec), CIRCLE('ICRS', 56.75, 24.1167, 0.5))"),
    ),
}


def _number(value: float) -> str:
    """Numero scritto nella query: 10 cifre significative (D42-2 (8))."""
    return format(float(value), ".10g")


def insert_view_circle(text: str, cursor: int, ra_deg: float, dec_deg: float, radius_deg: float,
                       epoch: str | None) -> tuple[str, int]:
    """Testo con centro e raggio della vista nella prima ``CIRCLE('ICRS', …)`` (o una ``CIRCLE`` nuova al cursore) e
    la riga di commento in fondo (sostituita se c'è). Restituisce (testo, posizione del cursore)."""
    numbers = f"{_number(ra_deg)}, {_number(dec_deg)}, {_number(radius_deg)}"
    match = _CIRCLE.search(text)
    if match is not None:
        new = f"CIRCLE('ICRS', {numbers})"
        text = text[:match.start()] + new + text[match.end():]
        cursor = match.start() + len(new)
    else:
        new = f"CIRCLE('ICRS', {numbers})"
        text = text[:cursor] + new + text[cursor:]
        cursor += len(new)
    lines = [line for line in text.split("\n") if not line.strip().startswith(VIEW_COMMENT_PREFIX)]
    while lines and not lines[-1].strip():
        lines.pop()
    when = epoch if epoch is not None else "not known (not assumed)"
    lines.append(f"{VIEW_COMMENT_PREFIX}, ICRS, degrees; epoch of the centre: {when}")
    text = "\n".join(lines)
    return text, min(cursor, len(text))


class _ServiceChooser(QWidget):
    """Servizio dall'elenco del 14 (voci nostre, poi i miei server) o URL scritto; salva/togli tra i miei server."""

    changed = Signal()
    saveRequested = Signal(str, str, str)  # nome, protocollo, URL → vo.add_server
    removeRequested = Signal(str)  # identificativo → vo.remove_server

    def __init__(self, protocol: str, servers, prefix: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.protocol = protocol
        self.servers = servers
        self.combo = QComboBox()
        self.combo.setObjectName(f"{prefix}Service")
        self.url = QLineEdit()
        self.url.setObjectName(f"{prefix}Url")
        self.url.setPlaceholderText("https://…")
        self.save_button = QPushButton(self.tr("Save to my servers…"))
        self.save_button.setObjectName(f"{prefix}SaveServer")
        self.remove_button = QPushButton(self.tr("Remove from my servers"))
        self.remove_button.setObjectName(f"{prefix}RemoveServer")
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(self.combo, 0, 0, 1, 2)
        grid.addWidget(self.url, 1, 0, 1, 2)
        grid.addWidget(self.save_button, 2, 0)
        grid.addWidget(self.remove_button, 2, 1)
        self.combo.currentIndexChanged.connect(self._update)
        self.url.textChanged.connect(self._update)
        self.save_button.clicked.connect(lambda: self.ask_save())
        self.remove_button.clicked.connect(self._remove)
        self.refresh()

    def refresh(self, select: str | None = None) -> None:
        """Ricarica le voci (dopo ``vo.add_server``/``vo.remove_server``), scegliendo ``select`` se c'è."""
        current = select if select is not None else self.combo.currentData()
        self.combo.blockSignals(True)
        self.combo.clear()
        entries = self.servers.find(self.protocol)
        for entry in (e for e in entries if not e.personal):
            self.combo.addItem(f"{entry.name} ({entry.provider})", entry.id)
        for entry in (e for e in entries if e.personal):
            self.combo.addItem(self.tr("%1 (my server)").replace("%1", entry.name), entry.id)
        self.combo.addItem(self.tr("URL written by hand…"), _MANUAL)
        index = self.combo.findData(current) if current is not None else -1
        self.combo.setCurrentIndex(max(index, 0))
        self.combo.blockSignals(False)
        self._update()

    def entry_id(self) -> str | None:
        data = self.combo.currentData()
        return None if data == _MANUAL else data

    def personal(self) -> bool:
        data = self.entry_id()
        return data is not None and any(e.id == data and e.personal for e in self.servers.entries())

    def service(self) -> str | None:
        """Parametro ``service``: identificativo della voce o l'URL scritto (``None`` se l'URL non è http(s))."""
        if self.entry_id() is not None:
            return self.entry_id()
        text = self.url.text().strip()
        return text if text.startswith(("http://", "https://")) else None

    def _update(self, *_) -> None:
        manual = self.entry_id() is None
        self.url.setEnabled(manual)
        self.save_button.setEnabled(manual and self.service() is not None)
        self.remove_button.setEnabled(self.personal())
        self.changed.emit()

    def ask_save(self, name: str | None = None) -> None:
        """Salva l'URL scritto tra i miei server; ``name`` già dato (test) o chiesto con una finestra (host)."""
        url = self.service()
        if url is None or self.entry_id() is not None:
            return
        if name is None:
            name, ok = QInputDialog.getText(self, self.tr("Save to my servers"), self.tr("Name of the server:"),
                                            text=urlparse(url).netloc)
            if not ok:
                return
        self.saveRequested.emit(name, self.protocol, url)

    def _remove(self) -> None:
        if self.personal():
            self.removeRequested.emit(self.entry_id())


def _form_spin(maximum: int, value: int, name: str) -> QSpinBox:
    spin = QSpinBox()
    spin.setObjectName(name)
    spin.setLocale(QLocale.c())
    spin.setRange(1, maximum)
    spin.setValue(value)
    return spin


class ConeSearchDialog(QDialog):
    """Finestra "Cone search…" (42 §3.8): parametri di ``catalog.cone_search``."""

    def __init__(self, servers, view_center: Mapping | None, view_radius: u.Quantity | None,
                 selected: tuple[str, Mapping] | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Cone search"))
        self.setObjectName("coneSearchDialog")
        self.view_center = view_center
        self.selected = selected
        self.chooser = _ServiceChooser("scs", servers, "cone", self)
        self.center_view = QRadioButton(self.tr("Centre of the view"))
        self.center_view.setObjectName("coneCenterView")
        self.center_source = QRadioButton(self.tr("Selected source"))
        self.center_source.setObjectName("coneCenterSource")
        self.center_typed = QRadioButton(self.tr("Coordinates written here"))
        self.center_typed.setObjectName("coneCenterTyped")
        self.centers = QButtonGroup(self)
        for k, button in enumerate((self.center_view, self.center_source, self.center_typed)):
            self.centers.addButton(button, k)
        self.center_view.setEnabled(view_center is not None)
        self.center_source.setEnabled(selected is not None)
        if selected is not None:
            self.center_source.setText(self.tr("Selected source: %1").replace("%1", selected[0]))
        self.typed = QLineEdit()
        self.typed.setObjectName("coneTyped")
        self.typed.setPlaceholderText(self.tr("e.g. 56.75 24.1167 or 03:47:00 +24:07:00"))
        self.frame = QComboBox()
        self.frame.setObjectName("coneFrame")
        for (frame, equinox), text in zip(TYPED_FRAMES, ("ICRS", "FK5 J2000.0", self.tr("Galactic")), strict=True):
            self.frame.addItem(text, frame)
        self.epoch = QLineEdit()
        self.epoch.setObjectName("coneEpoch")
        self.epoch.setPlaceholderText(self.tr("epoch, e.g. J2000.0 (empty: not declared)"))
        self.radius = QDoubleSpinBox()
        self.radius.setObjectName("coneRadius")
        self.radius.setLocale(QLocale.c())  # punto decimale sempre (T7 del 40)
        self.radius.setDecimals(4)
        self.radius.setRange(0.0, 1.0e9)  # i limiti veri sono del 05 (COMMAND_PARAMETER_INVALID), mai tagliati qui
        self.unit = QComboBox()
        self.unit.setObjectName("coneUnit")
        for unit in RADIUS_UNITS:
            self.unit.addItem(unit, unit)
        self.unit.setCurrentIndex(RADIUS_UNITS.index("arcmin"))
        self.radius.setValue(float(view_radius.to_value(u.arcmin)) if view_radius is not None else 1.0)
        self.max_rows = _form_spin(1_000_000_000, DEFAULT_MAX_ROWS, "coneMaxRows")
        self.error = QLabel()
        self.error.setObjectName("coneError")
        self.error.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Search"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        typed_row = QHBoxLayout()
        typed_row.addWidget(self.typed, 2)
        typed_row.addWidget(self.frame)
        typed_row.addWidget(self.epoch, 1)
        radius_row = QHBoxLayout()
        radius_row.addWidget(self.radius, 1)
        radius_row.addWidget(self.unit)
        form = QFormLayout()
        form.addRow(self.tr("Service"), self.chooser)
        form.addRow(self.tr("Centre"), self.center_view)
        form.addRow("", self.center_source)
        form.addRow("", self.center_typed)
        form.addRow("", typed_row)
        form.addRow(self.tr("Radius"), radius_row)
        form.addRow(self.tr("Maximum rows"), self.max_rows)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addWidget(self.buttons)
        (self.center_view if view_center is not None else self.center_typed).setChecked(True)
        self.centers.idToggled.connect(self._center_changed)
        self.typed.textEdited.connect(lambda: self.center_typed.setChecked(True))
        self._center_changed()

    def _center_changed(self, *_) -> None:
        typed = self.center_typed.isChecked()
        for widget in (self.frame, self.epoch):
            widget.setEnabled(typed)

    def center(self) -> Mapping | None:
        """Centro nella forma ``sky_position`` del 05, o ``None`` con il motivo in ``self.error``."""
        if self.center_view.isChecked():
            return self.view_center
        if self.center_source.isChecked():
            return None if self.selected is None else self.selected[1]
        frame = self.frame.currentData()
        equinox = dict(TYPED_FRAMES)[frame]
        epoch = self.epoch.text().strip() or None
        if epoch is not None and not _EPOCH.fullmatch(epoch):
            self.error.setText(self.tr("Epoch: write J… or B… (for example J2000.0), or leave it empty."))
            return None
        try:
            point = parse_typed_position(self.typed.text(), "galactic" if frame == "galactic" else "icrs")
        except Exception as exc:  # noqa: BLE001 - errori del 10 con codice: mostrati come messaggio
            code, message = getattr(exc, "code", None), getattr(exc, "message", None)
            self.error.setText(shown_line(ResultMessage(code, message, dict(getattr(exc, "params", {}) or {})))
                               if isinstance(code, str) and isinstance(message, str) else str(exc))
            return None
        if point is None:
            self.error.setText(self.tr("Coordinates not readable: write a decimal pair in degrees or a sexagesimal "
                                       "pair (right ascension in hours)."))
            return None
        sph = point.coord.spherical
        return {"lon": {"value": float(sph.lon.to_value(u.deg)), "unit": "deg"},
                "lat": {"value": float(sph.lat.to_value(u.deg)), "unit": "deg"},
                "frame": frame, "equinox": equinox, "obstime": None, "epoch": epoch,
                "epoch_reason": None if epoch is not None else "epoch not given by the user (not assumed)"}

    def params(self) -> dict | None:
        """Parametri di ``catalog.cone_search`` (forma JSON del 05) o ``None`` con il motivo nel dialogo."""
        self.error.clear()
        service = self.chooser.service()
        if service is None:
            self.error.setText(self.tr("Write an http:// or https:// address of the service."))
            return None
        center = self.center()
        if center is None:
            if not self.error.text():
                self.error.setText(self.tr("Choose a centre."))
            return None
        return {"service": service, "center": dict(center),
                "radius": {"value": float(self.radius.value()), "unit": self.unit.currentData()},
                "max_rows": int(self.max_rows.value())}

    def accept(self) -> None:
        if self.params() is not None:
            super().accept()


class AdqlQueryDialog(QDialog):
    """Finestra "ADQL query…" (42 §3.8): parametri di ``catalog.tap_query``; ``validate_adql`` prima dell'invio."""

    def __init__(self, servers, view: tuple[float, float, float, str | None] | None,
                 last: Mapping | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("ADQL query"))
        self.setObjectName("adqlQueryDialog")
        self.view = view  # (ra ICRS in gradi, dec, raggio in gradi, epoca del centro o None) dal 10
        self.error_position: int | None = None  # posizione dell'ultimo errore di validate_adql
        self.chooser = _ServiceChooser("tap", servers, "adql", self)
        self.examples = QComboBox()
        self.examples.setObjectName("adqlExamples")
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("adqlEditor")
        self.editor.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.setMinimumSize(560, 220)
        self.insert_view = QPushButton(self.tr("Insert view centre and radius"))
        self.insert_view.setObjectName("adqlInsertView")
        self.insert_view.setEnabled(view is not None)
        self.sync = QRadioButton(self.tr("Synchronous"))
        self.sync.setObjectName("adqlSync")
        self.asynchronous = QRadioButton(self.tr("Asynchronous"))
        self.asynchronous.setObjectName("adqlAsync")
        self.sync.setChecked(True)
        self.timeout = _form_spin(86_400, int(TAP_DEFAULT_ASYNC_TIMEOUT["value"]), "adqlTimeout")
        self.timeout.setSuffix(" s")
        self.max_rows = _form_spin(1_000_000_000, DEFAULT_MAX_ROWS, "adqlMaxRows")
        self.error = QLabel()
        self.error.setObjectName("adqlError")
        self.error.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Run"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.check_button = self.buttons.addButton(self.tr("Check"), QDialogButtonBox.ButtonRole.ActionRole)
        self.check_button.setObjectName("adqlCheck")
        self.check_button.clicked.connect(self.check)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.sync)
        mode_row.addWidget(self.asynchronous)
        mode_row.addWidget(QLabel(self.tr("maximum wait")))
        mode_row.addWidget(self.timeout)
        mode_row.addStretch(1)
        tools_row = QHBoxLayout()
        tools_row.addWidget(self.examples, 1)
        tools_row.addWidget(self.insert_view)
        form = QFormLayout()
        form.addRow(self.tr("Service"), self.chooser)
        form.addRow(self.tr("Mode"), mode_row)
        form.addRow(self.tr("Maximum rows (MAXREC)"), self.max_rows)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(tools_row)
        layout.addWidget(self.editor, 1)
        layout.addWidget(self.error)
        layout.addWidget(self.buttons)
        self.chooser.changed.connect(self._fill_examples)
        self.examples.activated.connect(self._example_chosen)
        self.insert_view.clicked.connect(self.insert_view_values)
        self.asynchronous.toggled.connect(self.timeout.setEnabled)
        self.editor.textChanged.connect(self._clear_mark)
        self.timeout.setEnabled(False)
        if last:
            if last.get("service") is not None:
                index = self.chooser.combo.findData(last["service"])
                if index >= 0:
                    self.chooser.combo.setCurrentIndex(index)
                elif str(last["service"]).startswith(("http://", "https://")):
                    self.chooser.combo.setCurrentIndex(self.chooser.combo.findData(_MANUAL))
                    self.chooser.url.setText(last["service"])
            self.editor.setPlainText(last.get("adql", ""))
            self.asynchronous.setChecked(last.get("mode") == "async")
        self._fill_examples()

    def _example_titles(self) -> dict[str, str]:
        return {
            "gaia_circle": self.tr("Gaia DR3: stars brighter than G = 15 in a circle (if the synchronous query "
                                   "times out, use asynchronous)"),
            "simbad_type": self.tr("SIMBAD: objects of type star (and subtypes) in a circle"),
            "vizier_2mass": self.tr("VizieR: 2MASS point sources (II/246/out) in a circle"),
            "irsa_allwise": self.tr("IRSA: AllWISE sources in a circle"),
            "heasarc_rass": self.tr("HEASARC: ROSAT All-Sky Survey bright sources in a circle"),
            "mast_obscore": self.tr("MAST: observations (ObsCore) in a circle"),
        }

    def _fill_examples(self) -> None:
        titles = self._example_titles()
        self.examples.clear()
        items = ADQL_EXAMPLES.get(self.chooser.entry_id() or "", ())
        self.examples.addItem(self.tr("Examples…") if items else self.tr("No examples for this service"), None)
        for key, adql in items:
            self.examples.addItem(titles[key], adql)
        self.examples.setEnabled(bool(items))

    def _replace_text(self, text: str, cursor_at: int | None = None) -> None:
        """Sostituisce il testo con un'operazione annullabile (⌘Z)."""
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(text)
        cursor.endEditBlock()
        if cursor_at is not None:
            cursor.setPosition(cursor_at)
        self.editor.setTextCursor(cursor)

    def choose_example(self, index: int) -> None:
        self.examples.setCurrentIndex(index)
        self._example_chosen(index)

    def _example_chosen(self, index: int) -> None:
        adql = self.examples.itemData(index)
        if adql:
            self._replace_text(adql)
        self.examples.setCurrentIndex(0)

    def insert_view_values(self) -> None:
        """Centro (ICRS, gradi) e raggio della vista nella ``CIRCLE`` e commento con l'epoca in fondo (42 §3.8)."""
        if self.view is None:
            return
        ra, dec, radius, epoch = self.view
        text, at = insert_view_circle(self.editor.toPlainText(), self.editor.textCursor().position(), ra, dec,
                                      radius, epoch)
        self._replace_text(text, at)

    def _clear_mark(self) -> None:
        self.editor.setExtraSelections([])

    def check(self) -> bool:
        """``validate_adql`` del 14: con un errore evidenzia il carattere, sposta il cursore e mostra il messaggio."""
        text = self.editor.toPlainText()
        result = validate_adql(text)
        if result.valid:
            self.error.setText(self.tr("Minimal checks passed (the service validates the query)."))
            return True
        params = {"reason": result.reason, "position": result.position}
        if result.quote is not None:
            params["quote"] = result.quote
        position = int(result.position or 0)
        line = text.count("\n", 0, position) + 1
        column = position - (text.rfind("\n", 0, position) + 1) + 1
        self.error.setText(shown_line(ResultMessage("ADQL_INVALID", result.message, params)) + " — "
                           + self.tr("line %1, column %2").replace("%1", str(line)).replace("%2", str(column)))
        mark = QTextEdit.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#D55E00"))
        fmt.setForeground(QColor("#FFFFFF"))
        mark.format = fmt
        cursor = self.editor.textCursor()
        cursor.setPosition(min(position, len(text)))
        cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
        mark.cursor = cursor
        self.editor.blockSignals(True)
        self.editor.setExtraSelections([mark])
        self.editor.blockSignals(False)
        place = self.editor.textCursor()
        place.setPosition(min(position, len(text)))
        self.editor.setTextCursor(place)
        self.editor.setFocus()
        self.error_position = position
        return False

    def params(self) -> dict | None:
        """Parametri di ``catalog.tap_query`` (forma JSON del 05) o ``None`` con il motivo nel dialogo."""
        service = self.chooser.service()
        if service is None:
            self.error.setText(self.tr("Write an http:// or https:// address of the service."))
            return None
        if not self.check():
            return None
        return {"service": service, "adql": self.editor.toPlainText(), "max_rows": int(self.max_rows.value()),
                "mode": "async" if self.asynchronous.isChecked() else "sync",
                "async_timeout": {"value": float(self.timeout.value()), "unit": "s"}}

    def accept(self) -> None:
        if self.params() is not None:
            super().accept()


def view_values(view) -> tuple[float, float, float, str | None] | None:
    """(ra, dec ICRS in gradi, raggio del campo in gradi, epoca del centro) della vista; conversione del 10."""
    if view is None or view.center is None or view.geometry is None:
        return None
    center = view.center if view.center.frame_name == "icrs" else view.center.to("icrs")
    sph = center.coord.spherical
    radius = view.geometry.field_radius
    return (float(sph.lon.to_value(u.deg)), float(sph.lat.to_value(u.deg)), float(radius.to_value(u.deg)),
            time_text(center.epoch))

