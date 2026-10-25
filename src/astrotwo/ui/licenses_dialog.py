# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Finestra "Licenses" / "Licenze" (requisito 1 di ``01`` §6.1).

Specifica: ``mdfiles/60-distribuzione-dmg.md`` §3.9 (stato ``approvato``) e ``40`` §3.3. Quattro schede di sola
lettura con un campo di ricerca: AstroTwo (``NOTICE`` e ``LICENSE``), terze parti (``THIRD_PARTY_LICENSES``),
sorgenti (``SOURCES.txt``) e crediti dei dati (testi di ``01`` §6.1). I testi di licenza non si traducono; un file
mancante mostra ``LICENSE_FILE_MISSING`` senza bloccare. Aprire la finestra non è un comando del 05 (lettura).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import astrotwo
from astrotwo.app_bundle import build_info, read_license
from astrotwo.ui.export_view import DSS_TEXT, SIMBAD_TEXT, VIZIER_TEXT
from astrotwo.ui.message_view import shown_text

# Crediti dei dati e dei servizi (01 §6.1, testi letti il 2026-10-17): (servizio, testo o ``None`` se il testo
# ufficiale non è ancora verificato, fonte). Testi nella lingua originale (inglese).
DATA_CREDITS: tuple[tuple[str, str | None, str], ...] = (
    ("Simbad (CDS)", SIMBAD_TEXT, "https://cds.unistra.fr/help/acknowledgement/"),
    ("VizieR (CDS), service", VIZIER_TEXT,
     "https://cds.unistra.fr/help/acknowledgement/, https://cds.unistra.fr/vizier-org/licences_vizier.html"),
    ("VizieR, data of each catalogue",
     "Cite the authors, producer and publisher of each catalogue (ReadMe file of the catalogue); some catalogues "
     "have an \"Acknowledging\" section. Commercial use of the data depends on the origin of each catalogue.",
     "https://cds.unistra.fr/vizier-org/licences_vizier.html"),
    ("Sesame name resolver (CDS)", None, "https://cds.unistra.fr/help/acknowledgement/"),
    ("HiPS (CDS)", None, "—"),
    ("MocServer (CDS)", None, "—"),
    ("CDS X-Match service",
     "This research has made use of the CDS cross-match service, Strasbourg Astronomical Observatory, France; "
     "2012, ASPC, 461, 291 (Boch et al.) and 2020, ASPC, 522, 125 (Pineau et al.).",
     "https://cds.unistra.fr/help/acknowledgement/"),
    ("Digitized Sky Survey DSS2 (STScI/MAST)", DSS_TEXT, "https://archive.stsci.edu/dss/acknowledging.html"),
    ("DSS images: copyright",
     "The images are copyrighted (Caltech 1993-1995 for the northern part, AAO Board 1993-5, UK SERC/PPARC and AAT "
     "Board 1992-5, AURA 1995 for the rest) and distributed by agreement.",
     "https://archive.stsci.edu/dss/copyright.html"),
    ("NAIF / SPICE (kernel and toolkit)", None, "https://naif.jpl.nasa.gov/naif/rules.html"),
)


def data_credits_text(not_verified: str) -> str:
    """Testo della scheda dei crediti; ``not_verified``: frase (tradotta) per i testi ancora da verificare."""
    blocks = []
    for service, text, source in DATA_CREDITS:
        blocks.append(f"{service}\n{text if text is not None else not_verified}\nSource: {source}")
    return "\n\n".join(blocks) + "\n"


class _TextTab(QWidget):
    """Una scheda: campo di ricerca (Invio = occorrenza successiva, dall'inizio quando finisce) e testo."""

    def __init__(self, text: str, name: str, parent=None) -> None:
        super().__init__(parent)
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.tr("Search"))
        self.search.setClearButtonEnabled(True)
        self.search.setObjectName(f"licensesSearch_{name}")
        self.text = QPlainTextEdit(text)
        self.text.setReadOnly(True)
        self.text.setObjectName(f"licensesText_{name}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(self.search)
        layout.addWidget(self.text)
        self.search.returnPressed.connect(self.find_next)

    def find_next(self) -> bool:
        needle = self.search.text()
        if not needle:
            return False
        if self.text.find(needle):
            return True
        cursor = self.text.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self.text.setTextCursor(cursor)
        return self.text.find(needle, QTextDocument.FindFlag(0))


class LicensesDialog(QDialog):
    """Finestra Licenze (60 §3.9). ``folder``: cartella dei file (per i test); di default quella dell'app."""

    TABS = ("astrotwo", "third_party", "sources", "data_credits")

    def __init__(self, parent=None, *, folder: Path | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("licensesDialog")
        self.setWindowTitle(self.tr("Licenses"))
        self.setModal(False)
        self.folder = folder
        self.tabs = QTabWidget()
        self.tabs.addTab(_TextTab(self._astrotwo_text(), "astrotwo"), "AstroTwo")
        self.tabs.addTab(_TextTab(self._file_text("THIRD_PARTY_LICENSES"), "third_party"), self.tr("Third-party"))
        self.tabs.addTab(_TextTab(self._file_text("SOURCES.txt"), "sources"), self.tr("Sources"))
        not_verified = self.tr("Acknowledgement text not yet verified.")
        self.tabs.addTab(_TextTab(data_credits_text(not_verified), "data_credits"), self.tr("Data credits"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)
        self.resize(760, 560)

    def tab_text(self, key: str) -> str:
        return self.tabs.widget(self.TABS.index(key)).text.toPlainText()

    def _file_text(self, name: str) -> str:
        text, problem = read_license(name, self.folder)
        return text if problem is None else shown_text(problem)

    def _astrotwo_text(self) -> str:
        info = build_info()
        lines = [f"AstroTwo {astrotwo.__version__}"]
        if info:
            lines.append(self.tr("Build {build}, commit {commit}").format(build=info.get("build"),
                                                                       commit=info.get("commit")))
        lines += ["Copyright (C) 2026 Guido Ratti", "License: GPL-3.0-or-later", "",
                  self._file_text("NOTICE").rstrip(), "", self._file_text("LICENSE")]
        return "\n".join(lines)
