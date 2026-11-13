# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""D62-6 (decisione del proprietario del 2026-11-13): difetti di lingua e di aspetto trovati dalle prove automatiche
del megatest (sprint D12, ``docs/megatest-runs/1.0.0.md``). Il dialogo delle colonne è in ``test_column_dialogs.py``,
il corpo «celestial» dei livelli in ``test_layers_moc.py``, la nota assente del PDF in ``test_object_profile.py``."""

from __future__ import annotations

from astrotwo.analysis import profile_export as pe
from astrotwo.core.vo_protocols import BUILTIN_SERVERS
from astrotwo.messages_catalog import message_text
from astrotwo.ui.main_window import ElidedLabel


def test_status_title_whole_or_elided_never_cut(qtbot):
    """U1: alla larghezza preferita il titolo è intero; più stretto finisce con «…», mai tagliato senza."""
    label = ElidedLabel()
    qtbot.addWidget(label)
    label.show()
    label.set_full_text("Loading catalog… · step 1 of 2")
    label.resize(label.sizeHint())
    assert label.text() == label.full_text
    label.resize(70, label.height())
    assert label.text().endswith("…") and label.text() != label.full_text


def test_server_names_in_english():
    names = {e.id: e.name for e in BUILTIN_SERVERS}
    assert names["esa-gaia-tap"] == "Gaia archive" and names["nasa-irsa-allwise-scs"] == "IRSA AllWISE (sources)"
    assert names["nasa-irsa-sia2"] == "IRSA images (SIA 2)"


def test_moc_type_message_without_parameter_syntax():
    for reason in ("json", "ascii"):
        params = {"reason": reason, "path": "/tmp/x.json"}
        for lang in ("en", "it"):
            text = message_text("MOC_TYPE_REQUIRED", params, lang)
            assert "kind=" not in text and "/tmp/x.json" in text


def _section(status: str) -> dict:
    return {"name": "identity", "status": status, "command_id": 1, "values": [], "details": {
        "cross_identifications": [{"catalog": "2MASS", "identifier": "J1", "method": "simbad_identifier",
                                   "note": "confirmed by the official Gaia cross-match"}]}}


def test_italian_pdf_status_and_fixed_notes():
    for status, italian in (("done", "completata"), ("partial", "in parte"), ("error", "errore"),
                            ("cancelled", "annullata")):
        data = {"target": {"name": "x"}, "sections": [_section(status)]}
        it = [t.get_text() for t in pe._identity_page(data, pe._LABELS["it"], "x").fig.texts]
        en = [t.get_text() for t in pe._identity_page(data, pe._LABELS["en"], "x").fig.texts]
        assert f"Stato: {italian}  ·  comando #1" in it
        assert f"Status: {status}  ·  command #1" in en  # il PDF inglese non cambia
    it_text, en_text = " ".join(it), " ".join(en)  # la cella va a capo: si confrontano le parole
    assert "confermato" in it_text and "confirmed" not in it_text
    assert "confirmed" in en_text and "confermato" not in en_text


def test_separation_and_notes_headers_do_not_touch():
    """«Separazione» e «Note» nella tabella della catena: colonna larga abbastanza per l'intestazione in grassetto."""
    images = {"name": "images", "status": "done", "command_id": 1, "values": [], "details": {"thumbnails": []}}
    data = {"target": {"name": "x"}, "sections": [_section("done"), images]}  # con le Immagini: colonne strette
    page = pe._identity_page(data, pe._LABELS["it"], "x")
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    canvas = FigureCanvasAgg(page.fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    boxes = {t.get_text(): t.get_window_extent(renderer) for t in page.fig.texts}
    assert boxes["Note"].x0 - boxes["Separazione"].x1 >= 5  # prima: 0 px (si toccavano)
