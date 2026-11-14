# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""D62-8 (decisione del proprietario del 2026-11-13): **con l'interfaccia in inglese nessun testo visibile e nessuna
stringa dei PDF contiene parole italiane**, e viceversa dove si può controllare. Il build 8 mostrava «Ollama (locale)»
nell'interfaccia inglese e «SIMBAD (mirror di Harvard)» in un messaggio inglese; il PDF italiano diceva «Immagini:
done». Nessuna rete.

Come si controlla: ogni testo si spezza in parole e si cerca in due elenchi chiusi, scritti qui:

- ``ITALIAN``: parole italiane che non sono anche inglesi né nomi di parametri (non c'è «data», che in italiano vuol
  dire «data del calendario», né «per», «non», «come»);
- ``ENGLISH``: parole inglesi che non sono anche italiane e non compaiono come nomi di parametri nei messaggi.

Dove si guarda: tutti i testi visibili della finestra principale e dei dialoghi che si aprono senza dati (impostazioni
dell'assistente con l'elenco dei provider, Licenze, Profili, ricerca a cono, ADQL), il file delle traduzioni (ogni
testo inglese e ogni traduzione italiana), il catalogo dei messaggi dei moduli, i nomi dei servizi, e tutte le
stringhe delle cinque pagine del PDF del profilo. «Viceversa» non vale per i nomi propri dei servizi, che sono in
inglese anche nell'interfaccia italiana (D62-6), né per le note del motore con valori dentro, che restano in
inglese nel PDF italiano (DD-3): sono elencati in ``ENGLISH_ALLOWED_IN_ITALIAN``.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtCore import QModelIndex, QSettings, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QTabWidget,
    QTextEdit,
    QWidget,
)

from astrotwo.messages_catalog import CATALOG
from astrotwo.ui import main_window as mw

ITALIAN = frozenset("""
di della delle dei degli del dal dalla dallo dai nella nelle nello nel nei sulla sulle sul sui alla alle allo agli
il gli che nessun nessuna nessuno sono questo questa questi queste quello quella colonna colonne catalogo cataloghi
immagine immagini errore errori stato locale sorgente sorgenti oggetto oggetti valore valori unità completata
annullata già perché più può è anche oppure quando senza tutti tutte dopo ancora mancante trovato trovata scritto
scritta apri salva annulla chiudi cielo stella stelle servizio servizi mappa scheda livello livelli chiave
impostazioni finestra vista aiuto riga righe tabella numero comando comandi parte grafico punti carica esporta
dati mirror_di posizione posizioni separazione identificativo bersaglio pianeta pianeti fotometria astrometria
""".split())
ENGLISH = frozenset("""
the and with without found done running cancel show hide open save close settings please cannot failed loaded
window help stars star columns rows images catalog catalogue points load export
""".split())
#: Nomi propri dei servizi e degli archivi, in inglese anche nell'interfaccia italiana (D62-6), e parole inglesi che
#: in un testo italiano sono nomi (di parametri, di formati, di survey): il controllo «viceversa» li ignora.
ENGLISH_ALLOWED_IN_ITALIAN = ("Gaia archive", "IRSA images (SIA 2)", "IRSA AllWISE (sources)", "All-Sky", "Sky",
                              "Harvard mirror", "help")


def words(text: str) -> set[str]:
    text = re.sub(r"<[^>]+>", " ", text or "")  # testo ricco di Qt
    text = re.sub(r"\{[^}]*\}|%\d|&(?=\w)", "", text)  # segnaposto e scorciatoie
    text = re.sub(r"[\w.]*[._][\w.]*\w", " ", text)  # nomi di codice (catalog.set_columns, max_rows): non parole
    return {w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9]*", text)}


def italian_in(text: str) -> set[str]:
    return words(text) & ITALIAN


def english_in(text: str) -> set[str]:
    for allowed in ENGLISH_ALLOWED_IN_ITALIAN:
        text = (text or "").replace(allowed, " ")
    return words(text) & ENGLISH


def widget_texts(widget: QWidget) -> list[str]:
    out = [widget.windowTitle(), widget.toolTip(), widget.statusTip()]
    if isinstance(widget, QLabel):
        out.append(widget.text())
    if isinstance(widget, QAbstractButton):
        out.append(widget.text())
    if isinstance(widget, QGroupBox):
        out.append(widget.title())
    if isinstance(widget, QLineEdit):
        out += [widget.text(), widget.placeholderText()]
    if isinstance(widget, (QPlainTextEdit, QTextEdit)):
        out.append(widget.placeholderText())
    if isinstance(widget, QComboBox):
        out += [widget.itemText(i) for i in range(widget.count())]
        out += [str(widget.itemData(i, Qt.ItemDataRole.ToolTipRole) or "") for i in range(widget.count())]
    if isinstance(widget, QTabWidget):
        out += [widget.tabText(i) for i in range(widget.count())] + [widget.tabToolTip(i) for i in
                                                                      range(widget.count())]
    if isinstance(widget, QMenu):
        out.append(widget.title())
    if isinstance(widget, QAbstractItemView) and widget.model() is not None:
        model = widget.model()
        try:
            count = model.columnCount(QModelIndex())
        except TypeError:  # modello a elenco: una colonna, intestazione non mostrata
            count = 0
        out += [str(model.headerData(i, Qt.Orientation.Horizontal) or "") for i in range(count)]
    for action in widget.actions():
        out += [action.text(), action.toolTip(), action.statusTip()]
    return [t for t in out if t]


def all_visible_texts(*roots: QWidget) -> list[str]:
    """Testi della finestra e dei dialoghi aperti (con tutti i loro figli): non i widget di altre prove."""
    texts, seen = [], set()
    for root in roots:
        for widget in [root, *root.findChildren(QWidget)]:
            if id(widget) not in seen:
                seen.add(id(widget))
                texts += widget_texts(widget)
    return texts


def open_everything(win) -> list:
    """Apre, senza dati, i dialoghi e le finestre che non chiedono un catalogo caricato."""
    from astrotwo.ui.licenses_dialog import LicensesDialog

    opened = [win.ai_panel.open_settings(), LicensesDialog(), win.profiles_window(), win.cone_search_dialog(),
              win.adql_dialog()]
    for widget in opened:
        widget.show()
    return opened


@pytest.fixture
def make(qtbot, tmp_path, cache):
    from tests.ui.test_main_window import make_window

    made = []

    def build(language: str):
        path = str(tmp_path / f"settings-{language}.ini")
        QSettings(path, QSettings.Format.IniFormat).setValue("language", language)
        win = make_window(qtbot, path, cache)
        assert win.language == language
        made.append(win)
        return win

    yield build
    for win in made:
        win.confirm = lambda title, text: True
        win.close()
    mw.load_translations("en")


def test_english_interface_has_no_italian_words(make):
    win = make("en")
    opened = open_everything(win)
    texts = all_visible_texts(win, *opened)
    assert len(texts) > 300
    assert "Ollama (local)" in texts and "LM Studio (local)" in texts  # elenco dei provider (D62-8)
    found = {t: sorted(italian_in(t)) for t in texts if italian_in(t)}
    assert found == {}
    for widget in opened:
        widget.close()


def test_italian_interface_has_no_english_words(make):
    win = make("it")
    opened = open_everything(win)
    texts = all_visible_texts(win, *opened)
    assert "Ollama (locale)" in texts and "LM Studio (locale)" in texts
    found = {t: sorted(english_in(t)) for t in texts if english_in(t)}
    assert found == {}
    for widget in opened:
        widget.close()


def test_translation_file_sources_english_translations_italian():
    root = ET.parse(Path(mw.__file__).parent / "i18n" / "astrotwo_it.ts").getroot()
    messages = list(root.iter("message"))
    assert len(messages) > 600
    sources = {m.find("source").text: sorted(italian_in(m.find("source").text)) for m in messages
               if italian_in(m.find("source").text)}
    translations = {m.find("translation").text: sorted(english_in(m.find("translation").text)) for m in messages
                    if english_in(m.find("translation").text)}
    assert sources == {} and translations == {}


def test_message_catalog_languages():
    """Testi del catalogo dei messaggi (D40-3): l'inglese senza parole italiane, l'italiano senza parole inglesi."""
    pairs = []
    for entry in CATALOG.values():
        pairs.append((entry.en, entry.it))
        pairs += [(v.en, v.it) for v in (getattr(entry, "variants", None) or {}).values()]
    assert len(pairs) > 500
    assert {en: sorted(italian_in(en)) for en, _ in pairs if italian_in(en)} == {}
    assert {it: sorted(english_in(it)) for _, it in pairs if english_in(it)} == {}


def test_service_labels_in_english():
    from astrotwo.core import vo_protocols as vo

    for entry in vo.BUILTIN_SERVERS:
        assert italian_in(f"{entry.name} {entry.provider}") == set(), entry.id
    assert vo._simbad_label("https://simbad.harvard.edu/simbad/sim-tap") == "SIMBAD (Harvard mirror)"
    assert vo._simbad_label("https://simbad.cds.unistra.fr/simbad/sim-tap") == "SIMBAD (CDS)"


def pdf_texts(data, language: str) -> list[str]:
    from astrotwo.analysis import profile_export as pe

    label = pe._LABELS[language]
    pages = [pe._identity_page(data, label, "x"), pe._astrometry_page(data, label, "x"),
             pe._photometry_page(data, label, "x"), pe._planets_page(data, label, "x"),
             pe._sources_page(data, label, "x")]
    texts = []
    for page in pages:
        texts += [t.get_text() for t in page.fig.texts]
        for ax in page.fig.axes:
            texts += [t.get_text() for t in ax.texts] + [ax.get_xlabel(), ax.get_ylabel(), ax.get_title()]
            legend = ax.get_legend()
            if legend is not None:
                texts += [t.get_text() for t in legend.get_texts()]
    return [t for t in texts if t]


@pytest.mark.parametrize("name", ["TRAPPIST-1", "51 Peg", "Vega"])
def test_pdf_strings_in_the_chosen_language(cache, services, name):  # noqa: F811
    import json

    from astrotwo.analysis.profile_export import merge_profile_results
    from tests.analysis.test_profile_export import profile, session_with_export

    session = session_with_export(cache)
    number, result = profile(session, {"name": name})
    data = merge_profile_results([(number, json.loads(json.dumps(result.values)))])
    english = pdf_texts(data, "en")
    assert len(english) > 50
    assert {t: sorted(italian_in(t)) for t in english if italian_in(t)} == {}
    italian = pdf_texts(data, "it")
    assert any(t.startswith("Immagini: completata") for t in italian)  # D62-8: prima «Immagini: done»
    # viceversa: i testi fissi del PDF italiano (etichette e stati), non i dati delle fonti (DD-3)
    from astrotwo.analysis import profile_export as pe

    labels = [v for k, v in pe._LABELS["it"].items() if k != "lang"]
    assert {t: sorted(english_in(t)) for t in labels if english_in(t)} == {}
    assert {t: sorted(english_in(t)) for t in pe._STATUS_TEXT["it"].values() if english_in(t)} == {}


from tests.analysis.profile_fakes import services  # noqa: E402, F401
