# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Finestra «Profili» del profilo di un oggetto (``mdfiles/43-ui-profili.md``, sprint C5).

Una finestra non modale con una scheda per comando ``object.profile`` (25): scheletro delle sezioni subito, stato
nell'intestazione di ogni sezione, contenuto all'arrivo (eventi ``resolved`` e ``section`` dell'avanzamento, 43 §3.5),
risultato finale come fonte definitiva, «Riprova questa sezione», riquadro della provenienza di ogni numero.

Nessun numero è calcolato qui (regola d'oro n. 1): si scrive la rappresentazione dei valori del risultato. I testi dei
servizi sono dati (mai HTML): si mostrano come testo semplice; i collegamenti sono costruiti solo per ADS, le pagine
SIMBAD ammesse (41 §3.19), la pagina di STScI e gli URL di copyright dichiarati dai survey.
"""

from __future__ import annotations

import base64
import html
import time
import urllib.parse
from collections.abc import Mapping, Sequence

from PySide6.QtCore import QCoreApplication, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QFileDialog,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from astrotwo.analysis.profile_export import STSCI_DSS_TEXT, STSCI_DSS_URL  # testo di STScI (01 §6.1), anche nel PDF
from astrotwo.core.commands import CancelToken, Command, Outcome, RequestedBy, ResultMessage
from astrotwo.ui.message_view import shown_line, shown_text

__all__ = ["ProfilesWindow", "ProfileTab", "SectionView", "ProvenancePopup", "CandidatesDialog", "ObjectProfileDialog",
           "number_text", "row_identifier", "SECTION_ORDER", "STSCI_DSS_TEXT", "exec_object_export"]

#: Ordine fisso delle sezioni nella scheda (D43-2): le Immagini stanno a destra dell'Identità.
SECTION_ORDER = ("identity", "images", "astrometry", "photometry", "planets")
#: Servizi che ogni sezione può interrogare (copia dei nomi di ``SECTION_SERVICES`` del 25, per l'intestazione).
SERVICE_NAMES = {"simbad": "SIMBAD", "gaia": "Gaia archive (ESA)", "irsa": "IRSA", "exoplanet": "NASA Exoplanet Archive",
                 "hips": "HiPS", "vizier_sed": "VizieR SED"}
ADS_ABSTRACT = "https://ui.adsabs.harvard.edu/abs/"
SIMBAD_PREFIXES = ("https://simbad.cds.unistra.fr/", "https://simbad.harvard.edu/")
#: Misure (D43-6).
WINDOW_SIZE = (760, 900)
THUMBNAIL_SHOWN = 192
IDENTIFIERS_SHOWN = 8
#: Riconoscimento dell'identificativo di una riga (43 §3.2 punto 5, D43-3): origine del livello → colonne e prefisso.
ROW_IDENTIFIERS = (
    (("gaiadr3.gaia_source", "I/355/gaiadr3"), ("source_id", "Source"), "Gaia DR3 "),
    (("fp_psc", "II/246/out"), ("designation", "2MASS"), "2MASS J"),
    (("allwise_p3as_psd", "II/328/allwise"), ("designation", "AllWISE"), "WISEA "),
    (("basic", "simbad"), ("main_id",), ""),
)


# --------------------------------------------------------------------------
# Testi dei valori (43 §3.7, D43-7): nessun calcolo, solo scrittura
# --------------------------------------------------------------------------


def _plain(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)  # rappresentazione decimale più corta del float64 (quella scritta dal servizio)
    return str(value)


def number_text(value) -> str:
    """Valore del risultato come testo: numero con la sua rappresentazione più corta (senza unità), testo com'è."""
    if isinstance(value, Mapping) and "value" in value:
        return _plain(value["value"])
    return _plain(value)


def unit_text(value) -> str:
    if isinstance(value, Mapping) and value.get("unit"):
        return str(value["unit"])
    return ""


def error_text(entry: Mapping) -> str:
    """Errore così come dato: simmetrico ``± e``, oppure ``+a / −b`` (pianeti, 25 §3.13)."""
    if entry.get("error_upper") is not None or entry.get("error_lower") is not None:
        return f"+{number_text(entry.get('error_upper'))} / {number_text(entry.get('error_lower'))}"
    if entry.get("error") is not None:
        return f"± {number_text(entry['error'])}"
    return ""


def ads_url(bibcode: str) -> str:
    return f"{ADS_ABSTRACT}{urllib.parse.quote(bibcode, safe='.')}/abstract"


def message_of(item: Mapping) -> ResultMessage:
    return ResultMessage(item.get("code", ""), item.get("text", ""), dict(item.get("params") or {}))


def row_identifier(origin: Mapping | None, row: Mapping) -> str | None:
    """Identificativo di una riga di catalogo per ``object.profile`` (43 §3.2 punto 5): solo con un'**origine** del
    livello riconosciuta (``table`` o ``catalog`` dei metadati del 13) e la colonna con un valore; altrimenti
    ``None`` (profilo per posizione). Il nome della colonna da solo non basta."""
    if not origin:
        return None
    names = {str(origin.get(k) or "") for k in ("table", "catalog", "catalog_id")}
    for tables, columns, prefix in ROW_IDENTIFIERS:
        if not names & set(tables):
            continue
        for column in columns:
            value = row.get(column)
            if value is None or str(value).strip() in ("", "--"):
                continue
            text = str(value).strip()
            return text if not prefix or text.startswith(prefix) else prefix + text
    return None


def _label(text: str = "", *, name: str | None = None, wrap: bool = True, rich: bool = False) -> QLabel:
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
    label.setText(text)
    label.setWordWrap(wrap)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                  | (Qt.TextInteractionFlag.LinksAccessibleByMouse if rich
                                     else Qt.TextInteractionFlag.NoTextInteraction))
    if rich:
        label.setOpenExternalLinks(False)
        label.linkActivated.connect(open_allowed_link)
    if name:
        label.setObjectName(name)
    return label


#: URL di copyright dichiarati dai survey (``obs_copyright_url``) già mostrati come collegamento (43 §3.7).
_SURVEY_LINKS: set[str] = set()


def allowed_link(url: str) -> bool:
    """Indirizzi che la finestra apre (43 §9): ADS, pagina di STScI, pagine SIMBAD ammesse, URL di copyright
    dichiarati da un survey (il collegamento si costruisce solo da quel campo)."""
    return url.startswith((ADS_ABSTRACT, STSCI_DSS_URL, *SIMBAD_PREFIXES)) or url in _SURVEY_LINKS


def open_allowed_link(url: str) -> None:
    """Apre nel browser di sistema solo gli indirizzi ammessi."""
    if allowed_link(url):
        QDesktopServices.openUrl(QUrl(url))


def _link(url: str, text: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(text)}</a>'


# --------------------------------------------------------------------------
# Riquadro della provenienza (43 §3.8)
# --------------------------------------------------------------------------


class ProvenancePopup(QFrame):
    """Riquadro non modale con valore, errori, unità, metodo, servizio, server, tabella, ADQL, riferimento, data,
    cache e comando di una ``ProfileValue`` (forma JSON). Si chiude con Esc o con un clic fuori."""

    commandRequested = Signal(int)

    def __init__(self, entry: Mapping, command_number: int | None, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("provenancePopup")
        self.entry = dict(entry)
        self.command_number = command_number
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self.rows = self._rows()
        body = "<br>".join(f"<b>{html.escape(k)}</b>: {v}" for k, v in self.rows)
        self.text_label = _label(body, name="provenanceText", rich=True)
        self.text_label.linkActivated.disconnect()
        self.text_label.linkActivated.connect(self._link)
        self.text_label.setMinimumWidth(420)
        layout.addWidget(self.text_label)
        buttons = QHBoxLayout()
        self.copy_button = QPushButton(self.tr("Copy"))
        self.copy_button.clicked.connect(self.copy)
        buttons.addStretch(1)
        buttons.addWidget(self.copy_button)
        layout.addLayout(buttons)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)

    def _rows(self) -> list[tuple[str, str]]:
        e, prov = self.entry, dict(self.entry.get("provenance") or {})
        esc = html.escape
        rows = [(self.tr("Quantity"), esc(str(e.get("quantity", "")))),
                (self.tr("Value"), esc(number_text(e.get("value")))),
                (self.tr("Error"), esc(error_text(e) or "—")),
                (self.tr("Unit"), esc(unit_text(e.get("value")) or "—"))]
        if e.get("interval"):
            low, high = e["interval"]
            rows.append((self.tr("Interval"), esc(f"[{number_text(low)}, {number_text(high)}] {unit_text(low)} "
                                                  f"({e.get('interval_kind') or ''})")))
        for key, title in (("band", self.tr("Band")), ("system", self.tr("System"))):
            if e.get(key):
                rows.append((title, esc(str(e[key]))))
        method = self.tr("read from the service") if e.get("method") == "read" else self.tr("computed")
        rows.append((self.tr("Method"), esc(method + (f": {e['formula']}" if e.get("formula") else ""))))
        rows.append((self.tr("Service"), esc(str(prov.get("service") or "—"))))
        rows.append((self.tr("Server"), esc(str(prov.get("server") or "—"))))
        rows.append((self.tr("Table"), esc(str(prov.get("table") or "—"))))
        query = prov.get("query")
        rows.append((self.tr("Query"), f"<code>{esc(query)}</code>" if query else "—"))
        if prov.get("identifier"):
            rows.append((self.tr("Identifier"), esc(f"{prov['identifier']} ({prov.get('match') or '—'})")))
        reference = e.get("reference")
        if reference:
            text = str(reference)
            rows.append((self.tr("Reference"), _link(ads_url(text), text) if " " not in text else esc(text)))
        else:
            rows.append((self.tr("Reference"), "—"))
        rows.append((self.tr("Retrieved"), esc(str(prov.get("retrieved_at") or "—"))))
        cache = prov.get("from_cache")
        rows.append((self.tr("From cache"), esc("—" if cache is None else (self.tr("yes") if cache else self.tr("no")))))
        rows.append((self.tr("Command"), _link(f"command:{self.command_number}", f"#{self.command_number}")
                     if self.command_number is not None else "—"))
        if e.get("note"):
            rows.append((self.tr("Note"), esc(str(e["note"]))))
        return rows

    def plain_text(self) -> str:
        """Le stesse righe come testo semplice (nessun numero ricalcolato)."""
        return "\n".join(f"{key}: {html.unescape(_strip_tags(value))}" for key, value in self.rows)

    def copy(self) -> None:
        QGuiApplication.clipboard().setText(self.plain_text())

    def _link(self, url: str) -> None:
        if url.startswith("command:"):
            self.commandRequested.emit(int(url.split(":", 1)[1]))
            self.close()
        else:
            open_allowed_link(url)


def _strip_tags(text: str) -> str:
    out, inside = [], False
    for ch in text:
        if ch == "<":
            inside = True
        elif ch == ">":
            inside = False
        elif not inside:
            out.append(ch)
    return "".join(out)


# --------------------------------------------------------------------------
# Tabelle di valori cliccabili
# --------------------------------------------------------------------------


class ValueTable(QTableWidget):
    """Tabella di sola lettura: ogni cella cliccabile apre il riquadro della ``ProfileValue`` della sua riga/cella."""

    valueClicked = Signal(object)

    def __init__(self, headers: Sequence[str], parent=None) -> None:
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(list(headers))
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.entries: dict[tuple[int, int], Mapping] = {}
        self.cellClicked.connect(self._clicked)

    def add_row(self, cells: Sequence[str], entries: Mapping[int, Mapping] | None = None) -> None:
        row = self.rowCount()
        self.insertRow(row)
        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.setItem(row, col, item)
        for col, entry in (entries or {}).items():
            if entry is not None:
                self.entries[(row, col)] = entry
                self.item(row, col).setToolTip(self.tr("Click for the source of this value"))

    def fit(self) -> None:
        height = self.horizontalHeader().height() + 2 * self.frameWidth()
        height += sum(self.rowHeight(r) for r in range(self.rowCount()))
        self.setFixedHeight(height + 2)

    def _clicked(self, row: int, col: int) -> None:
        entry = self.entries.get((row, col))
        if entry is not None:
            self.valueClicked.emit(entry)


# --------------------------------------------------------------------------
# Sezione: intestazione con lo stato e corpo (43 §3.6, §3.7)
# --------------------------------------------------------------------------


class SectionView(QFrame):
    """Una sezione della scheda: intestazione con lo stato, errori, avvisi, corpo."""

    retryRequested = Signal(str)
    valueClicked = Signal(object, object)  # forma JSON della ProfileValue, numero del comando

    def __init__(self, name: str, title: str, services: Sequence[str], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName(f"section_{name}")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.name, self.title, self.services = name, title, tuple(services)
        self.state = "waiting"
        self.started: float | None = None
        self.data: dict | None = None
        self.command_number: int | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)
        top = QHBoxLayout()
        self.header = _label("", name="sectionHeader", wrap=True)
        font = self.header.font()
        font.setBold(True)
        self.header.setFont(font)
        top.addWidget(self.header, 1)
        self.retry_button = QPushButton(QCoreApplication.translate("SectionView", "Retry this section"))
        self.retry_button.setObjectName("retrySection")
        self.retry_button.clicked.connect(lambda: self.retryRequested.emit(self.name))
        self.retry_button.hide()
        top.addWidget(self.retry_button)
        layout.addLayout(top)
        self.errors_label = _label("", name="sectionErrors")
        self.errors_label.hide()
        layout.addWidget(self.errors_label)
        self.warnings_label = _label("", name="sectionWarnings")
        self.warnings_label.hide()
        layout.addWidget(self.warnings_label)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(8)
        layout.addWidget(self.body)
        self.set_waiting()

    # --- stati --------------------------------------------------------------------------------

    def status_text(self) -> str:
        if self.state == "waiting":
            return QCoreApplication.translate("SectionView", "Waiting")
        if self.state == "running":
            seconds = 0 if self.started is None else int(time.monotonic() - self.started)
            services = ", ".join(SERVICE_NAMES.get(s, s) for s in self.services)
            text = QCoreApplication.translate("SectionView", "Running · %1 · %2 s")
            return text.replace("%1", services).replace("%2", str(seconds))
        if self.state == "cancelled":
            return QCoreApplication.translate("SectionView", "Cancelled")
        if self.state == "error":
            return QCoreApplication.translate("SectionView", "Error")
        data = self.data or {}
        servers = sorted({urllib.parse.urlparse(s).hostname or s for s in data.get("servers") or []})
        source = ", ".join(servers) if servers else QCoreApplication.translate("SectionView", "no request")
        elapsed = data.get("elapsed")
        seconds = "—" if not elapsed else f"{float(elapsed['value']):.1f}"
        text = QCoreApplication.translate("SectionView", "Arrived · %1 · %2 s")
        text = text.replace("%1", source).replace("%2", seconds)
        if self.state == "partial":
            text += " · " + QCoreApplication.translate("SectionView", "in part")
        return text

    def refresh_header(self) -> None:
        number = f"  #{self.command_number}" if self.command_number is not None else ""
        self.header.setText(f"{self.title} · {self.status_text()}{number}")

    def set_waiting(self) -> None:
        self.state, self.started = "waiting", None
        self.retry_button.hide()
        self.refresh_header()

    def set_running(self, started: float) -> None:
        if self.state in ("waiting",):
            self.state, self.started = "running", started
            self.refresh_header()

    def tick(self) -> None:
        if self.state == "running":
            self.refresh_header()

    def set_cancelled(self) -> None:
        if self.state in ("waiting", "running"):
            self.state = "cancelled"
            self.retry_button.show()
            self.refresh_header()

    def show_section(self, data: Mapping, command_number: int | None) -> None:
        """Sezione arrivata (evento ``section`` o risultato finale): stato, errori, avvisi, corpo."""
        self.data = dict(data)
        self.command_number = command_number
        status = data.get("status", "done")
        self.state = {"done": "done", "not_applicable": "done", "partial": "partial", "error": "error",
                      "cancelled": "cancelled"}.get(status, "done")
        errors = [shown_line(message_of(e)) for e in data.get("errors") or []]
        self.errors_label.setText("\n".join(errors))
        self.errors_label.setVisible(bool(errors))
        warnings = [f"⚠ {shown_text(message_of(w))}" for w in data.get("warnings") or []
                    if w.get("code") not in ("FROM_CACHE",)]
        self.warnings_label.setText("\n".join(warnings))
        self.warnings_label.setVisible(bool(warnings))
        self.retry_button.setVisible(self.state in ("error", "cancelled"))
        self._clear_body()
        if self.state != "cancelled":
            self.fill_body(self.data)
        self.refresh_header()

    def _clear_body(self) -> None:
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:  # staccato subito: un ridisegno non lascia i vecchi widget tra i figli
                widget.setParent(None)
                widget.deleteLater()

    def add(self, widget: QWidget) -> QWidget:
        self.body_layout.addWidget(widget)
        if isinstance(widget, ValueTable):
            widget.valueClicked.connect(lambda entry: self.valueClicked.emit(entry, self.command_number))
        return widget

    def values(self) -> dict[str, Mapping]:
        return {v["quantity"]: v for v in (self.data or {}).get("values") or []}

    def fill_body(self, data: Mapping) -> None:
        if data.get("values"):
            self.add(self.values_table(data["values"]))

    def values_table(self, values: Sequence[Mapping]) -> ValueTable:
        table = ValueTable([QCoreApplication.translate("SectionView", "Quantity"),
                            QCoreApplication.translate("SectionView", "Value"),
                            QCoreApplication.translate("SectionView", "Error"),
                            QCoreApplication.translate("SectionView", "Unit"),
                            QCoreApplication.translate("SectionView", "Reference"),
                            QCoreApplication.translate("SectionView", "Note")])
        for v in values:
            table.add_row([str(v.get("quantity", "")), number_text(v.get("value")), error_text(v),
                           unit_text(v.get("value")), str(v.get("reference") or ""), str(v.get("note") or "")],
                          {1: v, 2: v})
        table.fit()
        return table


class IdentityView(SectionView):
    def fill_body(self, data: Mapping) -> None:
        details = data.get("details") or {}
        if details.get("note"):
            self.add(_label(str(details["note"])))
        super().fill_body(data)
        groups = details.get("identifiers") or {}
        if groups:
            lines = []
            for group, names in groups.items():
                shown = ", ".join(names[:IDENTIFIERS_SHOWN])
                more = len(names) - IDENTIFIERS_SHOWN
                lines.append(f"{group}: {shown}" + (f" (+{more})" if more > 0 else ""))
            self.add(_label(self.tr("Identifiers (%1)").replace("%1", str(details.get("identifier_count", "")))
                            + "\n" + "\n".join(lines), name="identifiers"))
        chain = details.get("cross_identifications") or []
        if chain:
            table = ValueTable([self.tr("Catalog"), self.tr("Identifier"), self.tr("Method"), self.tr("Separation"),
                                self.tr("Notes")])
            for c in chain:
                notes = [c.get("note") or ""]
                if c.get("conflict"):
                    notes.append(", ".join(f"{k}: {v}" for k, v in c["conflict"].items()))
                if c.get("error"):
                    notes.append(shown_line(message_of(c["error"])))
                if c.get("candidates") and not c.get("identifier"):
                    notes.append(self.tr("%1 candidates, no choice").replace("%1", str(len(c["candidates"]))))
                sep = c.get("separation")
                table.add_row([str(c.get("catalog", "")), str(c.get("identifier") or "—"), str(c.get("method") or "—"),
                               "" if not sep else f"{number_text(sep)} {unit_text(sep)}",
                               "; ".join(n for n in notes if n)])
            table.fit()
            table.setObjectName("crossIdentifications")
            self.add(table)
        url = details.get("simbad_url")
        if url and str(url).startswith(SIMBAD_PREFIXES):
            self.add(_label(_link(str(url), self.tr("SIMBAD page")), name="simbadLink", rich=True))


class ImagesView(SectionView):
    def fill_body(self, data: Mapping) -> None:
        for thumb in (data.get("details") or {}).get("thumbnails") or []:
            box = QWidget()
            box.setObjectName("thumbnail")
            col = QVBoxLayout(box)
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(4)
            picture = QLabel()
            picture.setObjectName("thumbnailPicture")
            if thumb.get("png"):
                pixmap = QPixmap()
                pixmap.loadFromData(base64.b64decode(thumb["png"]), "PNG")
                picture.setPixmap(pixmap.scaled(THUMBNAIL_SHOWN, THUMBNAIL_SHOWN, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation))
            col.addWidget(picture)
            center = thumb.get("center") or {}
            lines = [str(thumb.get("title") or thumb.get("hips_id") or ""),
                     f"{number_text(thumb.get('fov'))} {unit_text(thumb.get('fov'))} · {thumb.get('size')} px · "
                     f"HEALPix {thumb.get('order')}",
                     self.tr("Center epoch: %1").replace("%1", str(center.get("epoch") or "—"))]
            if thumb.get("center_note"):
                lines.append(str(thumb["center_note"]))
            servers = sorted({urllib.parse.urlparse(s).hostname or s for s in thumb.get("servers") or []})
            if servers:
                lines.append(self.tr("Tiles from %1").replace("%1", ", ".join(servers)))
            col.addWidget(_label("\n".join(lines), name="thumbnailCaption"))
            col.addWidget(_label(self._credits(thumb), name="thumbnailCredits", rich=True))
            self.add(box)

    def _credits(self, thumb: Mapping) -> str:
        credits = dict(thumb.get("credits") or {})
        parts = []
        if credits.get("obs_copyright"):
            text = str(credits["obs_copyright"])
            url = str(credits.get("obs_copyright_url") or "")
            if url.startswith(("https://", "http://")):
                _SURVEY_LINKS.add(url)
                parts.append(_link(url, text))
            else:
                parts.append(html.escape(text))
        if credits.get("obs_ack"):
            parts.append(html.escape(str(credits["obs_ack"])))
        if "DSS2" in str(thumb.get("hips_id") or ""):
            parts.append(html.escape(STSCI_DSS_TEXT) + " " + _link(STSCI_DSS_URL, self.tr("Full text")))
        return "<br>".join(parts)


class PhotometryView(SectionView):
    def fill_body(self, data: Mapping) -> None:
        details = data.get("details") or {}
        points = details.get("points") or []
        values = self.values()
        if points:
            table = ValueTable([self.tr("Catalog"), self.tr("Band"), self.tr("System"), self.tr("Value"),
                                self.tr("Quality"), self.tr("λ"), self.tr("Fν"), self.tr("In plot")])
            table.setObjectName("photometryPoints")
            for p in points:
                label = p.get("label") or f"{p.get('catalog')} {p.get('band')}"
                read = values.get(f"{label} magnitude") or values.get(f"{label} count_rate")
                flux = values.get(f"{label} flux_nu")
                shown = p.get("magnitude") or p.get("count_rate")
                # l'errore del valore mostrato: mai quello del flusso in e⁻/s accanto a una magnitudine Gaia (C6)
                err = p.get("magnitude_error") if p.get("magnitude") else p.get("count_rate_error")
                value = "" if not shown else (f"{number_text(shown)} {unit_text(shown)}"
                                              + (f" ± {number_text(err)}" if err else ""))
                fnu = "" if not p.get("flux") else (f"{number_text(p['flux'])} {unit_text(p['flux'])}"
                                                    + (f" ± {number_text(p['flux_error'])}" if p.get("flux_error")
                                                       else ""))
                lam = "" if not p.get("wavelength") else f"{number_text(p['wavelength'])} {unit_text(p['wavelength'])}"
                why = "; ".join(shown_text(message_of(n)) for n in p.get("notes") or [])
                plot = self.tr("yes") if p.get("in_plot") else self.tr("no")
                if p.get("upper_limit"):
                    plot += " · " + self.tr("upper limit")
                table.add_row([str(p.get("catalog", "")), str(p.get("band", "")), str(p.get("system") or "—"), value,
                               str(p.get("quality") or "—"), lam, fnu, plot + (f" ({why})" if why else "")],
                              {3: read, 6: flux})
            table.fit()
            self.add(table)
        elif data.get("values"):
            super().fill_body(data)
        if points or (details.get("vizier") or {}).get("rows"):
            self.add(self._plot(points, details.get("vizier")))

    def _plot(self, points, vizier) -> QWidget:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        from astrotwo.analysis.photometry import plot_sed_rows

        figure = Figure(figsize=(6.4, 4.0), dpi=100)
        plot_sed_rows(points, vizier, figure=figure)  # D43-9: limiti superiori come frecce, ovunque
        canvas = FigureCanvasQTAgg(figure)
        canvas.setObjectName("sedPlot")
        canvas.setFixedHeight(340)
        self.figure = figure
        return canvas


class PlanetsView(SectionView):
    COLUMNS = ("period", "semi_major_axis", "eccentricity", "mass", "radius", "equilibrium_temperature")

    def fill_body(self, data: Mapping) -> None:
        details = data.get("details") or {}
        planets = details.get("planets") or []
        if not planets:
            self.add(_label(self.tr("No planet in the archive"), name="noPlanets"))
            return
        values = self.values()
        titles = {"period": self.tr("Period"), "semi_major_axis": self.tr("Semi-major axis"),
                  "eccentricity": self.tr("Eccentricity"), "mass": self.tr("Mass"), "radius": self.tr("Radius"),
                  "equilibrium_temperature": self.tr("Equilibrium temperature")}
        table = ValueTable([self.tr("Planet"), self.tr("Discovery"), *[titles[c] for c in self.COLUMNS]])
        table.setObjectName("planetsTable")
        for planet in planets:
            name = str(planet.get("pl_name", ""))
            cells, entries = [name, f"{planet.get('discoverymethod') or '—'} {planet.get('disc_year') or ''}".strip()],\
                {}
            for k, key in enumerate(self.COLUMNS, start=2):
                par = (planet.get("parameters") or {}).get(key) or {}
                if not par.get("value"):
                    cells.append("—")
                    continue
                mark = {"upper": "< ", "lower": "> "}.get(par.get("limit"), "")
                text = f"{mark}{number_text(par['value'])}"
                if par.get("error_upper") or par.get("error_lower"):
                    text += f" +{number_text(par.get('error_upper'))} / {number_text(par.get('error_lower'))}"
                unit = unit_text(par["value"])
                cells.append(text + (f" {unit}" if unit else ""))
                entries[k] = values.get(f"{name} {key}")
            table.add_row(cells, entries)
        table.fit()
        self.add(table)


VIEWS = {"identity": IdentityView, "images": ImagesView, "astrometry": SectionView, "photometry": PhotometryView,
         "planets": PlanetsView}


# --------------------------------------------------------------------------
# Scheda di un profilo (43 §3.4)
# --------------------------------------------------------------------------


class ProfileTab(QWidget):
    """Una scheda: testata, avvisi del profilo, sezioni in ordine fisso con le Immagini a destra dell'Identità."""

    def __init__(self, owner: ProfilesWindow, job_id: int, params: Mapping, label: str) -> None:
        super().__init__()
        self.owner = owner
        self.job_id = job_id
        self.params = dict(params)
        self.registered: dict | None = None  # parametri del comando registrato (con simbad_id), alla fine
        self.label = label
        self.command_number: int | None = None
        self.resolved: dict | None = None
        self.result_values: dict | None = None
        self.state = "queued"
        self.started: float | None = None
        self.retries: dict[int, str] = {}  # lavoro → sezione riprovata
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)
        head = QHBoxLayout()
        self.title = _label(label, name="profileTitle")
        font = self.title.font()
        font.setPointSizeF(font.pointSizeF() * 1.3)
        font.setBold(True)
        self.title.setFont(font)
        head.addWidget(self.title, 1)
        self.command_button = QPushButton("")
        self.command_button.setObjectName("profileCommand")
        self.command_button.setFlat(True)
        self.command_button.hide()
        self.command_button.clicked.connect(lambda: self.command_number is not None
                                            and owner.show_command(self.command_number))
        head.addWidget(self.command_button)
        self.fresh_button = QPushButton(self.tr("Rerun with fresh data"))
        self.fresh_button.setObjectName("rerunFresh")
        self.fresh_button.setEnabled(False)
        self.fresh_button.clicked.connect(self.rerun_fresh)
        head.addWidget(self.fresh_button)
        self.sky_button = QPushButton(self.tr("Show in sky"))
        self.sky_button.setObjectName("showInSky")
        self.sky_button.setEnabled(False)
        self.sky_button.clicked.connect(self.show_in_sky)
        head.addWidget(self.sky_button)
        outer.addLayout(head)
        # Sprint C6 (43 §3.10): esportazione, punti SED come catalogo, SAMP; tutti comandi registrati
        actions = QHBoxLayout()
        self.export_button = QPushButton(self.tr("Export…"))
        self.export_button.setObjectName("exportProfile")
        menu = QMenu(self.export_button)
        self.act_export_ecsv = menu.addAction(self.tr("Values with provenance (ECSV)…"),
                                              lambda: self.export_dialog("ecsv"))
        self.act_export_pdf = menu.addAction(self.tr("Profile sheet (PDF)…"), lambda: self.export_dialog("pdf"))
        self.act_export_png = menu.addAction(self.tr("SED plot (PNG)…"), lambda: self.export_dialog("sed_png"))
        self.export_button.setMenu(menu)
        actions.addWidget(self.export_button)
        self.catalog_button = QPushButton(self.tr("Load SED points as catalog"))
        self.catalog_button.setObjectName("loadSedCatalog")
        self.catalog_button.clicked.connect(self.load_sed_catalog)
        actions.addWidget(self.catalog_button)
        self.samp_button = QPushButton(self.tr("Send via SAMP"))
        self.samp_button.setObjectName("sendSedSamp")
        self.samp_menu = QMenu(self.samp_button)
        self.samp_menu.aboutToShow.connect(self._fill_samp_menu)
        self.samp_button.setMenu(self.samp_menu)
        actions.addWidget(self.samp_button)
        actions.addStretch(1)
        outer.addLayout(actions)
        self.retry_numbers: dict[str, int] = {}  # sezione → ultimo «Riprova» riuscito, nell'ordine di fine
        samp = getattr(owner.main, "samp", None)
        if samp is not None:
            samp.status_changed.connect(self._samp_changed)  # metodo legato: scollegato con la scheda
        self.status = _label("", name="profileStatus")
        outer.addWidget(self.status)
        self.warnings = _label("", name="profileWarnings")
        self.warnings.hide()
        outer.addWidget(self.warnings)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        page = QWidget()
        self.page_layout = QVBoxLayout(page)
        self.page_layout.setContentsMargins(0, 0, 0, 0)
        self.page_layout.setSpacing(12)
        scroll.setWidget(page)
        outer.addWidget(scroll, 1)
        titles = {"identity": self.tr("Identity"), "images": self.tr("Images"),
                  "astrometry": self.tr("Astrometry and distance"), "photometry": self.tr("Photometry"),
                  "planets": self.tr("Planets")}
        from astrotwo.analysis.object_profile import SECTION_SERVICES, SECTIONS

        wanted = [s for s in SECTION_ORDER if s in (self.params.get("sections") or SECTIONS)]
        self.views: dict[str, SectionView] = {}
        for name in wanted:
            view = VIEWS[name](name, titles[name], SECTION_SERVICES[name])
            view.retryRequested.connect(self.retry)
            view.valueClicked.connect(self.show_provenance)
            self.views[name] = view
        if "identity" in self.views or "images" in self.views:
            row = QHBoxLayout()
            row.setSpacing(12)
            if "identity" in self.views:
                row.addWidget(self.views["identity"], 1)
            if "images" in self.views:
                self.views["images"].setFixedWidth(THUMBNAIL_SHOWN + 48)
                row.addWidget(self.views["images"], 0, Qt.AlignmentFlag.AlignTop)
            self.page_layout.addLayout(row)
        for name in ("astrometry", "photometry", "planets"):
            if name in self.views:
                self.page_layout.addWidget(self.views[name])
        self.page_layout.addStretch(1)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.popup: ProvenancePopup | None = None
        self.refresh_status()
        self.refresh_actions()

    # --- stato complessivo ----------------------------------------------------------------------

    def refresh_status(self, extra: str = "") -> None:
        texts = {"queued": self.tr("Queued"), "running": self.tr("Running"), "cancelled": self.tr("Cancelled"),
                 "error": self.tr("Error")}
        if self.state == "done":
            elapsed = (self.result_values or {}).get("elapsed")
            text = self.tr("Done in %1 s").replace("%1", "—" if not elapsed else f"{float(elapsed['value']):.1f}")
        else:
            text = texts.get(self.state, self.state)
        self.status.setText(text + (f" · {extra}" if extra else ""))
        if self.command_number is not None:
            self.command_button.setText(f"#{self.command_number}")
            self.command_button.show()
        self.owner.tab_changed(self)

    def active_jobs(self) -> list[int]:
        return [j for j in [self.job_id, *self.retries] if j in self.owner.jobs]

    # --- eventi del comando (43 §3.5) -----------------------------------------------------------

    def job_started(self, job_id: int) -> None:
        if job_id == self.job_id:
            self.state = "running"
            self.refresh_status()

    def job_progress(self, job_id: int, report) -> None:
        detail = getattr(report, "detail", None)
        if not isinstance(detail, Mapping):
            return
        retry = self.retries.get(job_id)
        if detail.get("event") == "resolved":
            now = time.monotonic()
            if retry is None:
                self.resolved = dict(detail.get("resolved") or {})
                main_id = self.resolved.get("main_id")
                if main_id:
                    self.title.setText(str(main_id))
                self.sky_button.setEnabled(bool(self.resolved.get("position")))
                self._show_warnings(detail.get("warnings") or [])
                for name in detail.get("sections") or []:
                    if name in self.views:
                        self.views[name].set_running(now)
            elif retry in self.views:
                self.views[retry].set_running(now)
            self.timer.start()
        elif detail.get("event") == "section":
            section = detail.get("section") or {}
            name = section.get("name")
            if name in self.views and (retry is None or retry == name):
                self.views[name].show_section(section, None)

    def job_finished(self, done) -> None:
        retry = self.retries.pop(done.job_id, None)
        result = done.result
        number = None if done.entry is None else done.entry.number
        values = result.values if isinstance(result.values, Mapping) else {}
        sections = {s["name"]: s for s in values.get("sections") or []}
        if retry is not None:  # Riprova questa sezione: si sostituisce solo quella sezione (43 §3.6)
            view = self.views.get(retry)
            if retry in sections and number is not None:  # entra nell'esportazione (43 §3.10)
                self.retry_numbers.pop(retry, None)
                self.retry_numbers[retry] = number
            if view is not None:
                if retry in sections:
                    view.show_section(sections[retry], number)
                elif result.error is not None:
                    view.show_section({"name": retry, "status": "error",
                                       "errors": [{"code": result.error.code, "text": result.error.text,
                                                   "params": dict(result.error.params)}]}, number)
            self._stop_timer()
            self.refresh_actions()
            return
        self.command_number = number
        self.registered = dict(done.registered.parameters)
        self.fresh_button.setEnabled(True)
        if sections:  # risultato finale: fonte definitiva (anche annullato con sezioni arrivate)
            self.result_values = dict(values)
            self.resolved = dict(values.get("resolved") or self.resolved or {})
            if self.resolved.get("main_id"):
                self.title.setText(str(self.resolved["main_id"]))
            self.sky_button.setEnabled(bool(self.resolved.get("position")))
            self._show_warnings(list(values.get("warnings") or []) + [
                {"code": w.code, "text": w.text, "params": dict(w.params)} for w in result.warnings
                if w.code in ("PROFILE_PLANET_HOST_MISMATCH", "DATA_REFRESHED")])
            for name, view in self.views.items():
                if name in sections:
                    view.show_section(sections[name], number)
        if result.status == "cancelled":
            self.state = "cancelled"
            for view in self.views.values():
                view.set_cancelled()
        elif result.status == "error":
            self.state = "error"
            for view in self.views.values():
                view.set_cancelled()
            self.status.setText("")
            if result.error is not None and result.error.code == "PROFILE_AMBIGUOUS_TARGET":
                self.owner.ambiguous(self, result.error)
        else:
            self.state = "done"
        extra = "" if result.error is None else shown_line(result.error)
        self.refresh_status(extra)
        self._stop_timer()
        self.refresh_actions()

    def _stop_timer(self) -> None:
        if not self.active_jobs():
            self.timer.stop()

    def _tick(self) -> None:
        for view in self.views.values():
            view.tick()

    def _show_warnings(self, items: Sequence[Mapping]) -> None:
        seen, lines = set(), []
        for w in items:
            if w.get("code") in ("FROM_CACHE",):
                continue
            line = f"⚠ {shown_text(message_of(w))}"
            if line not in seen:
                seen.add(line)
                lines.append(line)
        self.warnings.setText("\n".join(lines))
        self.warnings.setVisible(bool(lines))

    # --- azioni (ogni azione è un comando registrato, 43 §9) ------------------------------------

    def base_params(self) -> dict:
        params = dict(self.registered or self.params)
        if not params.get("simbad_id") and (self.resolved or {}).get("main_id"):
            params["simbad_id"] = self.resolved["main_id"]
        params.pop("refresh", None)
        return params

    def retry(self, name: str) -> None:
        params = self.base_params()
        params["sections"] = [name]
        job = self.owner.submit(params, tab=self, retry=name)
        self.retries[job] = name
        self.views[name].set_waiting()

    def rerun_fresh(self) -> None:
        self.owner.rerun_fresh(self)

    def show_in_sky(self) -> None:
        position = (self.resolved or {}).get("position")
        if position:
            self.owner.main.submit("view.set_center", {"position": position}, source="menu")

    # --- esportazione, catalogo, SAMP (43 §3.10, sprint C6) ----------------------------------------

    def has_profile(self) -> bool:
        return self.command_number is not None and self.result_values is not None

    def has_sed(self) -> bool:
        view = self.views.get("photometry")
        details = ((view.data if view is not None else None) or {}).get("details") or {}
        return bool(details.get("points")) or bool((details.get("vizier") or {}).get("rows"))

    def export_commands(self) -> list[int]:
        """``commands`` di 43 §3.10: il comando di base, poi l'ultimo «Riprova» riuscito di ogni sezione."""
        out = [self.command_number] if self.command_number is not None else []
        for number in self.retry_numbers.values():
            if number not in out:
                out.append(number)
        return out

    def refresh_actions(self) -> None:
        profile, sed = self.has_profile(), self.has_profile() and self.has_sed()
        self.export_button.setEnabled(profile)
        self.act_export_png.setEnabled(sed)
        self.catalog_button.setEnabled(sed)
        samp = getattr(self.owner.main, "samp", None)
        connected = samp is not None and samp.status.connected
        self.samp_button.setEnabled(sed and connected)
        no_sed = self.tr("No SED points") if profile and not sed else ""
        self.catalog_button.setToolTip(no_sed)
        self.samp_button.setToolTip(no_sed or ("" if connected else self.tr("SAMP not connected")))

    def _samp_changed(self, status=None) -> None:
        self.refresh_actions()

    def main_id(self) -> str:
        return " ".join(str((self.resolved or {}).get("main_id") or self.title.text() or "profile").split())

    def export_dialog(self, fmt: str) -> None:
        from astrotwo.analysis.profile_export import sed_catalog_path

        suffix = {"ecsv": ("-profile.ecsv", "ECSV (*.ecsv)"), "pdf": ("-profile.pdf", "PDF (*.pdf)"),
                  "sed_png": ("-sed.png", "PNG (*.png)")}[fmt]
        proposed = sed_catalog_path(self.main_id(), 0).name.replace("-sed-0.xml", suffix[0])
        titles = {"ecsv": self.tr("Export values with provenance"), "pdf": self.tr("Export profile sheet"),
                  "sed_png": self.tr("Export SED plot")}
        path, _ = QFileDialog.getSaveFileName(self, titles[fmt], proposed, suffix[1])
        if path:
            self.export(fmt, path)

    def export(self, fmt: str, path: str, *, then: str | None = None) -> int:
        """Mette in coda ``object.export`` (25 §3.15) con i comandi della scheda e la lingua dell'app."""
        from pathlib import Path

        language = getattr(self.owner.main, "language", "en")
        params = {"commands": self.export_commands(), "format": fmt, "path": str(Path(path).resolve()),
                  "language": language if language in ("en", "it") else "en"}
        job = self.owner.main.submit("object.export", params, source="menu")
        self.owner.exports[job] = (self, then)
        return job

    def load_sed_catalog(self) -> int:
        """«Carica i punti SED come catalogo»: ``object.export`` ``sed_votable`` nella cartella ``Profiles/``, poi
        ``catalog.open_file`` sullo stesso file (43 §3.10, 25 §3.15)."""
        from astrotwo.analysis.profile_export import sed_catalog_path

        folder = self.owner.sed_folder
        folder.mkdir(parents=True, exist_ok=True)
        commands = self.export_commands()
        return self.export("sed_votable", str(sed_catalog_path(self.main_id(), commands[-1], folder)),
                           then="catalog")

    def send_sed(self, recipient: str | None) -> int:
        return self.owner.main.submit("object.send_sed", {"commands": self.export_commands(), "recipient": recipient},
                                      source="menu")

    def _fill_samp_menu(self) -> None:
        self.samp_menu.clear()
        every = self.samp_menu.addAction(self.tr("All applications"))
        every.triggered.connect(lambda checked=False: self.send_sed(None))
        samp = getattr(self.owner.main, "samp", None)
        clients = samp.status.clients if samp is not None else ()
        if clients:
            self.samp_menu.addSeparator()
        for client in clients:
            act = self.samp_menu.addAction(client.name or client.id)  # nome dichiarato: testo semplice
            act.setToolTip(client.id)
            act.triggered.connect(lambda checked=False, cid=client.id: self.send_sed(cid))

    def show_provenance(self, entry: Mapping, command_number: int | None) -> ProvenancePopup:
        self.popup = ProvenancePopup(entry, command_number if command_number is not None else self.command_number,
                                     self)
        self.popup.commandRequested.connect(self.owner.show_command)
        self.popup.adjustSize()
        cursor = self.mapToGlobal(self.rect().center())
        self.popup.move(cursor.x() - self.popup.width() // 2, cursor.y() - self.popup.height() // 2)
        self.popup.show()
        return self.popup


# --------------------------------------------------------------------------
# Finestra (43 §3.3)
# --------------------------------------------------------------------------


class ProfilesWindow(QWidget):
    """Finestra non modale «Profili»: una scheda per comando ``object.profile``; i comandi vanno nella coda del 40."""

    def __init__(self, main, settings: QSettings | None = None) -> None:
        super().__init__(None, Qt.WindowType.Window)
        self.main = main
        self.settings = settings
        self.setObjectName("profilesWindow")
        self.setWindowTitle(self.tr("Profiles"))
        self.resize(*WINDOW_SIZE)
        if settings is not None:
            geometry = settings.value("profiles/geometry")
            if geometry is not None:
                self.restoreGeometry(geometry)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        layout.addWidget(self.tabs)
        self.jobs: dict[int, ProfileTab] = {}
        self.exports: dict[int, tuple[ProfileTab, str | None]] = {}  # lavoro object.export → scheda, poi (43 §3.10)
        from astrotwo.analysis.profile_export import default_sed_folder

        self.sed_folder = default_sed_folder()  # cartella dei punti SED caricati come catalogo (25 §3.15)
        self.last_dialog: QDialog | None = None

    # --- comandi -----------------------------------------------------------------------------------

    def submit(self, params: Mapping, *, source: str = "menu", tab: ProfileTab | None = None,
               retry: str | None = None) -> int:
        version = self.main.registry.spec("object.profile").version
        command = Command("object.profile", version, dict(params), RequestedBy(source))
        token = CancelToken()
        job = self.main.submit_command(command, token)
        self.tokens = getattr(self, "tokens", {})
        self.tokens[job] = token
        if tab is not None:
            self.jobs[job] = tab
        return job

    def open_profile(self, params: Mapping, *, source: str = "menu", label: str | None = None) -> ProfileTab:
        """Mette in coda ``object.profile`` e apre subito la sua scheda con lo scheletro (43 §3.5)."""
        params = dict(params)
        job = self.submit(params, source=source)
        tab = ProfileTab(self, job, params, label or describe_target(params))
        self.jobs[job] = tab
        self.tabs.addTab(tab, tab.label)
        self.tabs.setCurrentWidget(tab)
        self.show()
        self.raise_()
        return tab

    def rerun_fresh(self, tab: ProfileTab) -> ProfileTab:
        """«Riesegui con dati aggiornati»: lo stesso comando registrato con ``refresh`` in una scheda nuova (D43-1)."""
        params = tab.base_params()
        params["sections"] = list(tab.params.get("sections") or params.get("sections") or SECTION_ORDER)
        version = self.main.registry.spec("object.profile").version
        command = Command("object.profile", version, params, RequestedBy("menu"), refresh=True)
        token = CancelToken()
        job = self.main.submit_command(command, token)
        self.tokens = getattr(self, "tokens", {})
        self.tokens[job] = token
        new = ProfileTab(self, job, params, tab.title.text())
        self.jobs[job] = new
        self.tabs.addTab(new, new.label)
        self.tabs.setCurrentWidget(new)
        return new

    def show_command(self, number: int) -> None:
        self.main.show_command(number)

    # --- eventi dalla finestra principale ------------------------------------------------------

    def handles(self, job_id: int) -> bool:
        return job_id in self.jobs or job_id in self.exports

    def job_started(self, job_id: int) -> None:
        tab = self.jobs.get(job_id)
        if tab is not None:
            tab.job_started(job_id)

    def job_progress(self, job_id: int, report) -> None:
        tab = self.jobs.get(job_id)
        if tab is not None:
            tab.job_progress(job_id, report)

    def job_finished(self, done) -> None:
        if done.job_id in self.exports:
            self.export_finished(done)
            return
        tab = self.jobs.pop(done.job_id, None)
        getattr(self, "tokens", {}).pop(done.job_id, None)
        if tab is not None and self.tabs.indexOf(tab) >= 0:
            tab.job_finished(done)

    def export_finished(self, done) -> None:
        """Esito di ``object.export``: errore in una finestra; per «Carica i punti SED come catalogo» il
        ``catalog.open_file`` sul file scritto (43 §3.10)."""
        _tab, then = self.exports.pop(done.job_id)
        result = done.result
        if result.status != "ok":
            if result.error is not None:
                self.main.show_modal(self.tr("The export was not written"), shown_line(result.error))
            return
        if then == "catalog":
            self.main.submit("catalog.open_file", {"file": {"path": result.values["path"]}}, source="menu")

    def tab_changed(self, tab: ProfileTab) -> None:
        index = self.tabs.indexOf(tab)
        if index >= 0:
            self.tabs.setTabText(index, tab.title.text())
            self.tabs.setTabToolTip(index, f"#{tab.command_number}  {tab.status.text()}"
                                    if tab.command_number is not None else tab.status.text())

    def close_tab(self, index: int) -> bool:
        """Chiude una scheda; con un suo comando in coda o in corso chiede conferma e lo annulla (43 §3.3)."""
        tab = self.tabs.widget(index)
        if not isinstance(tab, ProfileTab):
            return False
        active = tab.active_jobs()
        if active:
            if not self.main.confirm(self.tr("Close profile"),
                                     self.tr("The profile is still running: cancel it and close the tab?")):
                return False
            for job in active:
                token = getattr(self, "tokens", {}).get(job)
                if token is not None:
                    token.cancel()
                self.jobs.pop(job, None)
        self.tabs.removeTab(index)
        tab.timer.stop()
        tab.deleteLater()
        return True

    def ambiguous(self, tab: ProfileTab, error: ResultMessage) -> CandidatesDialog:
        """Bersaglio ambiguo: dialogo con l'elenco, nessuna scelta automatica (43 §3.4)."""
        dialog = CandidatesDialog(list(error.params.get("candidates") or []), self)
        self.last_dialog = dialog

        def chosen() -> None:
            if dialog.choice is not None:
                params = tab.base_params()
                params["simbad_id"] = dialog.choice
                params["sections"] = list(tab.params.get("sections") or SECTION_ORDER)
                self.open_profile(params, label=dialog.choice)

        dialog.accepted.connect(chosen)
        dialog.open()
        return dialog

    def hideEvent(self, event) -> None:  # noqa: N802 - nome di Qt
        if self.settings is not None:
            self.settings.setValue("profiles/geometry", self.saveGeometry())
        super().hideEvent(event)


def exec_object_export(history):
    """Esecutore di ``object.export`` (``bound_by = 43``, 25 §3.15): ``history()`` dà la cronologia della sessione
    della finestra principale; i file si scrivono dai risultati registrati, nel thread dei comandi."""
    from astrotwo.analysis.profile_export import export_profile, merge_profile_results, results_from_history

    def run(ctx, p: Mapping) -> Outcome:
        data = merge_profile_results(results_from_history(history(), p["commands"]))
        written = export_profile(data, p["path"], p["format"], language=p["language"])
        warnings = [ResultMessage(w[0], w[1], dict(getattr(w, "params", None) or {})) for w in written.warnings]
        return Outcome(values={**written.as_dict(), "commands": list(p["commands"]),
                               "main_id": (data.get("resolved") or {}).get("main_id")}, warnings=warnings)

    return run


def describe_target(params: Mapping) -> str:
    """Bersaglio come scritto, per il titolo della scheda prima della risoluzione."""
    if params.get("name"):
        return str(params["name"])
    position = params.get("position")
    if position:
        from astropy import units as u

        from astrotwo.core.coordinates_wcs import format_coordinates

        lon = format_coordinates(values=position["lon"]["value"] * u.Unit(position["lon"]["unit"]),
                                 frame=position["frame"], axis="lon").lon[0]
        lat = format_coordinates(values=position["lat"]["value"] * u.Unit(position["lat"]["unit"]),
                                 frame=position["frame"], axis="lat").lat[0]
        return f"{lon} {lat}"
    if params.get("layer") is not None:
        return f"{params['layer']} · {params.get('row')}"
    return str(params.get("simbad_id") or "?")


# --------------------------------------------------------------------------
# Dialoghi
# --------------------------------------------------------------------------


class CandidatesDialog(QDialog):
    """Più candidati SIMBAD (``PROFILE_AMBIGUOUS_TARGET``): elenco con nome, tipo, separazione e citazioni; l'utente
    sceglie; nessuna voce scelta in partenza (25 regola a)."""

    def __init__(self, candidates: Sequence[Mapping], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Choose the object"))
        self.choice: str | None = None
        layout = QVBoxLayout(self)
        layout.addWidget(_label(self.tr("Several SIMBAD objects match: choose one. No object is chosen "
                                        "automatically.")))
        self.table = QTableWidget(0, 4)
        self.table.setObjectName("candidates")
        self.table.setHorizontalHeaderLabels([self.tr("Name"), self.tr("Type"), self.tr("Separation"),
                                              self.tr("Citations")])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.candidates = [dict(c) for c in candidates]
        for c in self.candidates:
            row = self.table.rowCount()
            self.table.insertRow(row)
            sep = c.get("separation")
            for col, text in enumerate([str(c.get("main_id", "")), str(c.get("otype") or "—"),
                                        "" if not sep else f"{number_text(sep)} {unit_text(sep)}",
                                        _plain(c.get("nbref"))]):
                self.table.setItem(row, col, QTableWidgetItem(text))
        self.table.clearSelection()
        layout.addWidget(self.table)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Profile of this object"))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        self.table.itemSelectionChanged.connect(
            lambda: self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
                bool(self.table.selectionModel().selectedRows())))
        layout.addWidget(self.buttons)

    def choose(self, row: int) -> None:
        self.table.selectRow(row)
        self._accept()

    def _accept(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        self.choice = self.candidates[rows[0].row()]["main_id"]
        self.accept()


class ObjectProfileDialog(QDialog):
    """Data → Object profile…: nome o coordinate (nel frame delle coordinate mostrate) con l'epoca dichiarata."""

    def __init__(self, frame: str, text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Object profile"))
        self.frame = frame
        form = QFormLayout(self)
        self.text = QLineEdit(text)
        self.text.setObjectName("profileTarget")
        self.text.setPlaceholderText(self.tr("Name or coordinates (%1)").replace("%1", frame.upper()))
        form.addRow(self.tr("Name or coordinates"), self.text)
        self.epoch = QLineEdit("J2000.0")
        self.epoch.setObjectName("profileEpoch")
        self.epoch.setToolTip(self.tr("Epoch of typed coordinates (never assumed): written in the command"))
        form.addRow(self.tr("Epoch"), self.epoch)
        self.error = _label("", name="profileDialogError")
        self.error.hide()
        form.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Profile"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.params: dict | None = None

    def build(self) -> dict:
        """Parametri di ``object.profile``: ``position`` con sistema ed epoca per una coppia di coordinate, ``name``
        altrimenti. Errori del 10 o dell'epoca come eccezioni dei moduli."""
        from astropy.time import Time

        from astrotwo.core.commands import parse_typed_position, sky_json
        from astrotwo.core.coordinates_wcs import SkyFrame

        text = self.text.text().strip()
        if not text:
            raise ValueError(self.tr("Write a name or a coordinate pair"))
        point = parse_typed_position(text, self.frame)
        if point is None:
            return {"name": text}
        try:
            epoch = Time(self.epoch.text().strip())
        except ValueError as exc:
            raise ValueError(self.tr("Epoch not readable: %1 (for example J2000.0 or 2016.0)")
                             .replace("%1", self.epoch.text())) from exc
        return {"position": sky_json(SkyFrame(coord=point.coord, epoch=epoch))}

    def _accept(self) -> None:
        from astrotwo.ui.message_view import shown_exception

        try:
            self.params = self.build()
        except Exception as exc:  # noqa: BLE001 - errore mostrato nel dialogo, con il codice del modulo
            self.error.setText(shown_exception(exc) if getattr(exc, "code", None) else str(exc))
            self.error.show()
            return
        self.accept()
