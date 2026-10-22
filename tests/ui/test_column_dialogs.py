# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test dei dialoghi delle colonne del pannello cataloghi (42 §3.5, §12 T7), sprint 5b.

Piattaforma ``offscreen``. I dialoghi scelgono solo nomi, sistema e unità dichiarati; la conferma è ``catalog.set_columns``
del 05 e ``confirm_position_columns`` del 13 (spiato nel test). Nulla è assunto: senza scelta esplicita il pulsante
resta spento.
"""

import pytest
from PySide6.QtWidgets import QDialogButtonBox

from astrotwo.core import catalogs
from astrotwo.ui.catalog_panel import PositionColumnsDialog, ProperMotionColumnsDialog
from tests.ui.test_catalog_panel import open_catalog, votable  # noqa: F401 - votable() per i dati con UCD
from tests.ui.test_catalog_sky import open_file
from tests.ui.test_main_window import make_window, settings_path, wait_idle  # noqa: F401 - fixture

#: CSV senza UCD né unità: nessuna colonna è riconosciuta (mai dai nomi), le colonne vanno dichiarate dall'utente.
CSV = "id,x,y,mu_a,mu_d,mag\nA,56.87,24.10,10.5,-3.25,5.5\nB,56.22,24.11,-2.0,4.5,6.0\nC,57.29,24.05,0.5,0.25,7.5\n"
#: Con nomi riconoscibili solo come ipotesi (``suggest_position_columns``).
CSV_NAMES = "id,ra,dec,mag\nA,56.87,24.10,5.5\nB,56.22,24.11,6.0\n"


@pytest.fixture
def win(qtbot, settings_path, cache):  # noqa: F811
    win = make_window(qtbot, settings_path, cache)
    win.auto_column_dialogs = True
    win.sky.start_view()
    wait_idle(qtbot, win)
    yield win
    win.close()


def ok_button(dialog):
    return dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)


def spy_confirm(monkeypatch):
    calls = []
    real = catalogs.confirm_position_columns

    def spy(table, lon, lat, frame, equinox=None, unit=None):
        calls.append({"lon": lon, "lat": lat, "frame": frame, "equinox": equinox, "unit": unit})
        return real(table, lon, lat, frame, equinox=equinox, unit=unit)

    monkeypatch.setattr(catalogs, "confirm_position_columns", spy)
    return calls


def given(entry) -> dict:
    """Parametri scritti nel comando, senza i valori predefiniti ``None``."""
    return {k: v for k, v in entry.command.parameters.items() if v is not None}


def set_columns_entries(win):
    return [e for e in win.session.history.entries if e.command.name == "catalog.set_columns"]


def test_t7_position_and_proper_motion_choice(qtbot, win, tmp_path, monkeypatch):
    calls = spy_confirm(monkeypatch)
    open_catalog(qtbot, win, tmp_path, CSV, "c.csv")
    layer = win.session.workspace.state.layer("L1")
    assert layer.data.positions is None  # nessuna colonna riconosciuta: i dialoghi sono necessari
    dialog = win.column_dialog
    assert isinstance(dialog, PositionColumnsDialog) and dialog.isVisible()
    assert not ok_button(dialog).isEnabled()  # nulla preselezionato: serve una scelta esplicita
    assert dialog.frame.currentData() is None and dialog.lon.currentData() is None
    # solo colonne numeriche: l'identificativo "id" e il nome non sono offerti come posizione
    offered = [dialog.lon.itemData(i) for i in range(dialog.lon.count())]
    assert offered == [None, "x", "y", "mu_a", "mu_d", "mag"]
    dialog.lon.setCurrentIndex(dialog.lon.findData("x"))
    dialog.lat.setCurrentIndex(dialog.lat.findData("y"))
    dialog.frame.setCurrentIndex(dialog.frame.findData("icrs"))
    assert dialog.unit.isVisible()
    assert not ok_button(dialog).isEnabled()  # le colonne non hanno unità: va dichiarata, mai assunta
    dialog.unit.setCurrentIndex(dialog.unit.findData("deg"))
    assert ok_button(dialog).isEnabled()
    ok_button(dialog).click()
    wait_idle(qtbot, win)
    entries = set_columns_entries(win)
    assert len(entries) == 1 and entries[0].result.status == "ok"
    assert given(entries[0]) == {"layer": "L1", "lon": "x", "lat": "y", "frame": "icrs", "unit": "deg"}
    assert calls == [{"lon": "x", "lat": "y", "frame": "icrs", "equinox": None, "unit": catalogs.u.Unit("deg")}]
    layer = win.session.workspace.state.layer("L1")
    assert layer.data.positions.source == "confirmed" and layer.data.body == "celestial"
    # moto proprio dal pulsante "Colonne…" della scheda (nessun UCD: non si apre da solo)
    assert win.column_dialog is dialog
    win.catalog_panel.tab("L1").columns_button.click()
    position = win.column_dialog
    assert isinstance(position, PositionColumnsDialog) and position is not dialog
    assert position.lon.currentData() == "x" and position.frame.currentData() == "icrs"  # prefissato dallo stato
    ok_button(position).click()
    motion = win.column_dialog
    assert isinstance(motion, ProperMotionColumnsDialog) and motion is not position
    assert "x / y, icrs" in motion.findChild(type(motion.cos_label), "motionPosition").text()
    assert all(motion.combos[k].currentData() is None for k in motion.combos)  # nessun UCD: nessuna ipotesi
    assert ok_button(motion).isEnabled()  # scegliere nulla è lecito
    motion.combos["pm_ra"].setCurrentIndex(motion.combos["pm_ra"].findData("mu_a"))
    assert not ok_button(motion).isEnabled()  # serve anche la declinazione
    motion.combos["pm_dec"].setCurrentIndex(motion.combos["pm_dec"].findData("mu_d"))
    assert not ok_button(motion).isEnabled()  # e dire se mu_a include cos δ: mai assunto
    motion.cos_no.setChecked(True)
    assert ok_button(motion).isEnabled()
    ok_button(motion).click()
    wait_idle(qtbot, win)
    entries = set_columns_entries(win)
    assert len(entries) == 2 and entries[1].result.status == "ok"
    assert given(entries[1]) == {
        "layer": "L1", "lon": "x", "lat": "y", "frame": "icrs", "pm_ra": "mu_a", "pm_dec": "mu_d",
        "pm_ra_includes_cosdec": False}
    assert calls[-1] == {"lon": "x", "lat": "y", "frame": "icrs", "equinox": None, "unit": None}
    assert win.session.workspace.state.layer("L1").columns["pm_ra"] == "mu_a"


def test_name_hint_is_only_a_hypothesis(qtbot, win, tmp_path):
    open_catalog(qtbot, win, tmp_path, CSV_NAMES, "n.csv")
    dialog = win.column_dialog
    assert isinstance(dialog, PositionColumnsDialog)
    assert (dialog.lon.currentData(), dialog.lat.currentData()) == ("ra", "dec")
    assert "to be confirmed" in dialog.note.text()
    assert not ok_button(dialog).isEnabled()  # il sistema e l'unità restano da dichiarare
    dialog.reject()
    wait_idle(qtbot, win)
    assert set_columns_entries(win) == []  # annullare non registra nulla; il catalogo resta non disegnato
    assert win.session.workspace.state.layer("L1").data.positions is None


def test_equinox_is_required_for_fk5(qtbot, win, tmp_path):
    open_catalog(qtbot, win, tmp_path, CSV, "c.csv")
    dialog = win.column_dialog
    dialog.lon.setCurrentIndex(dialog.lon.findData("x"))
    dialog.lat.setCurrentIndex(dialog.lat.findData("y"))
    dialog.unit.setCurrentIndex(dialog.unit.findData("deg"))
    dialog.frame.setCurrentIndex(dialog.frame.findData("icrs"))
    assert not dialog.equinox.isVisible() and ok_button(dialog).isEnabled()
    dialog.frame.setCurrentIndex(dialog.frame.findData("fk5"))
    assert dialog.equinox.isVisible() and not ok_button(dialog).isEnabled()
    dialog.equinox.setText("J2000")
    assert ok_button(dialog).isEnabled()
    assert dialog.choice() == {"lon": "x", "lat": "y", "frame": "fk5", "equinox": "J2000", "unit": "deg"}


def test_proper_motion_dialog_preselects_from_ucd_only(qtbot, win, tmp_path):
    rows = tuple(("%s" % n, ra, dec, "3.5", "7.1", "0.1", "1", "0.5", "0.1", "0.25", "1 2")
                 for n, ra, dec in (("A", "56.8", "24.1"), ("B", "56.2", "24.2")))
    open_catalog(qtbot, win, tmp_path, votable(rows).replace(
        '<FIELD name="Vec"', '<FIELD name="pmRA" datatype="double" unit="mas/yr" ucd="pos.pm;pos.eq.ra"/>'
        '<FIELD name="e_pmRA" datatype="double" unit="mas/yr" ucd="stat.error;pos.pm;pos.eq.ra"/>'
        '<FIELD name="pmDE" datatype="double" unit="mas/yr" ucd="pos.pm;pos.eq.dec"/><FIELD name="Vec"'), "p.xml")
    motion = win.column_dialog
    assert isinstance(motion, ProperMotionColumnsDialog)  # posizione dagli UCD: solo il moto da scegliere
    assert "RA_ICRS / DE_ICRS, icrs" in motion.findChild(type(motion.cos_label), "motionPosition").text()
    assert "epoch J2016" in motion.findChild(type(motion.cos_label), "motionPosition").text()
    assert motion.combos["pm_ra"].currentData() == "pmRA"  # le colonne di errore non sono candidate
    assert motion.combos["pm_dec"].currentData() == "pmDE"
    assert motion.combos["parallax"].currentData() == "Plx" and motion.combos["radial_velocity"].currentData() is None
    assert not ok_button(motion).isEnabled()  # cos δ mai preselezionato
    motion.reject()  # "Salta": posizioni della tabella, non propagate; nessun comando
    wait_idle(qtbot, win)
    assert set_columns_entries(win) == []
    motion.cos_yes.setChecked(True)
    assert motion.choice() == {"pm_ra": "pmRA", "pm_dec": "pmDE", "pm_ra_includes_cosdec": True, "parallax": "Plx",
                               "radial_velocity": None}
