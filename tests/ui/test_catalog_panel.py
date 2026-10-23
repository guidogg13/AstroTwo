# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del pannello cataloghi e tabelle (42 §12), sprint 5a: ordinamento (T1), selezione dalla tabella (T2) e dalla
vista (T3), record (T4), valori mostrati (T5), un milione di righe (T6, ``perf``). T7 (dialoghi delle colonne) arriva
con lo sprint 5b.

Piattaforma ``offscreen`` con il renderer in memoria; valori attesi ricalcolati nel test con ``numpy``, con il 10
(``format_coordinates``) e con il 13 (``record_view``).
"""

import dataclasses
import time
import tracemalloc

import astropy.units as u
import numpy as np
import pytest
from astropy.table import MaskedColumn, Table
from PySide6.QtCore import QEvent, QPoint, QSettings, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence
from PySide6.QtTest import QTest

from astrotwo.core import coordinates_wcs as cw
from astrotwo.core.catalogs import load_table, record_view
from astrotwo.core.commands import Layer, _jsonable
from astrotwo.ui.catalog_panel import MISSING_MARK, NOT_DRAWN_MARK, CatalogTableModel
from tests.ui.test_catalog_sky import PLEIADES, center_on, open_file, screen_point, wait_points, wait_settled
from tests.ui.test_main_window import make_window, settings_path, wait_idle  # noqa: F401 - fixture
from tests.ui.test_sky_viewer import mouse

#: Righe: nome, RA, Dec (deg, ICRS), Vmag (ripetute e una mancante), Plx (formato dichiarato 7.2f), Flux (nessun
#: formato), Flag (intero con un mancante), Vec (array per riga). La riga D non ha posizione: non disegnata.
ROWS = (
    ("A", "56.8711", "24.1051", "3.5", "7.123", "0.1", "1", "1 2"),
    ("B", "56.2190", "24.1133", "", "7.5", "1e-20", "", "3 4"),
    ("C", "57.2906", "24.0534", "2.25", "", "3.0", "1", "5 6"),
    ("D", "", "", "3.5", "8.0", "0.30000000000000004", "0", "7 8"),
    ("E", "56.5", "24.0", "2.25", "6.2", "2.5", "1", "9 10"),
)


def votable(rows=ROWS) -> str:
    data = "\n".join("<TR>" + "".join(f"<TD>{v}</TD>" for v in row) + "</TR>" for row in rows)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE>
<COOSYS ID="sys" system="ICRS" epoch="J2016.0"/>
<TABLE name="stars">
<FIELD name="Name" datatype="char" arraysize="*" ucd="meta.id;meta.main"/>
<FIELD name="RA_ICRS" datatype="double" unit="deg" ucd="pos.eq.ra;meta.main" ref="sys"/>
<FIELD name="DE_ICRS" datatype="double" unit="deg" ucd="pos.eq.dec;meta.main" ref="sys"/>
<FIELD name="Vmag" datatype="double" unit="mag" ucd="phot.mag;em.opt.V"><DESCRIPTION>V magnitude</DESCRIPTION></FIELD>
<FIELD name="Plx" datatype="double" unit="mas" ucd="pos.parallax" precision="2" width="7"/>
<FIELD name="Flux" datatype="double" unit="Jy"/>
<FIELD name="Flag" datatype="int"/>
<FIELD name="Vec" datatype="double" arraysize="2"/>
<DATA><TABLEDATA>
{data}
</TABLEDATA></DATA>
</TABLE>
</RESOURCE>
</VOTABLE>
"""


GALACTIC = """<?xml version="1.0" encoding="utf-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE>
<COOSYS ID="gal" system="galactic"/>
<TABLE name="gal">
<FIELD name="GLON" datatype="double" unit="deg" ucd="pos.galactic.lon" ref="gal"/>
<FIELD name="GLAT" datatype="double" unit="deg" ucd="pos.galactic.lat" ref="gal"/>
<DATA><TABLEDATA>
<TR><TD>166.6</TD><TD>-23.5</TD></TR>
<TR><TD>0.25</TD><TD>1.125</TD></TR>
</TABLEDATA></DATA>
</TABLE>
</RESOURCE>
</VOTABLE>
"""


@pytest.fixture
def win(qtbot, settings_path, cache):  # noqa: F811
    win = make_window(qtbot, settings_path, cache)
    win.sky.start_view()
    wait_settled(qtbot, win)  # anche il centramento che la vista invia da sola dopo la prima comparsa (300 ms)
    yield win
    win.close()


def open_catalog(qtbot, win, tmp_path, text=None, name="c.xml"):
    path = tmp_path / name
    path.write_text(votable() if text is None else text)
    open_file(qtbot, win, "catalog.open_file", str(path))
    wait_settled(qtbot, win)  # simboli calcolati sulla base finale prima di leggere o cliccare
    return str(path)


def page(win, layer="L1"):
    return win.catalog_panel.tab(layer)


def history(win):
    return win.session.history.entries


def wait_command(qtbot, win, name, since, where=lambda entry: True):
    """Il comando ``name`` registrato dopo le prime ``since`` voci, cercato per nome: dopo un cambio di layout la vista
    manda da sola un ``view.set_center`` 300 ms più tardi (41), quindi l'ultima voce dipende dalla velocità del Mac."""
    found = []

    def registered():
        found[:] = [e for e in history(win)[since:] if e.command.name == name and where(e)]
        return bool(found)

    qtbot.waitUntil(registered, timeout=30000)
    wait_settled(qtbot, win)
    return found[0]


def click_header(qtbot, win, tab, column):
    header = tab.view.horizontalHeader()
    x = header.sectionViewportPosition(tab.model.names.index(column)) + 5
    since = len(history(win))
    QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(x, 5))
    return wait_command(qtbot, win, "table.sort", since)


def click_row(tab, shown, modifier=Qt.KeyboardModifier.NoModifier):
    rect = tab.view.visualRect(tab.model.index(shown, 0))
    QTest.mouseClick(tab.view.viewport(), Qt.MouseButton.LeftButton, modifier, rect.center())


def expected_order(values, mask, direction):
    """Ordine atteso ricalcolato nel test: presenti con ``numpy.argsort`` stabile (in discesa a pari valore resta
    l'ordine originale), mancanti in fondo nell'ordine della tabella."""
    present = np.flatnonzero(~mask)
    if direction == "ascending":
        order = present[np.argsort(values[present], kind="stable")]
    else:
        order = np.array(sorted(present, key=lambda i: (-values[i], i)), dtype=np.int64)
    return np.concatenate([order, np.flatnonzero(mask)]).tolist()


# =============================================================================
# T1 — ordinamento


def test_t1_sort_from_header(qtbot, win, tmp_path):
    open_catalog(qtbot, win, tmp_path)
    tab = page(win)
    assert win.docks["table"].widget() is win.catalog_panel and win.catalog_panel.tabs.count() == 1
    layer = win.session.workspace.state.layer("L1")
    table = layer.data.table
    assert tab.model.table is table  # nessuna copia della tabella del 13
    before = {n: np.array(table[n]).copy() for n in table.colnames}
    masks = {n: np.array(getattr(table[n], "mask", False)).copy() for n in table.colnames}
    shown = [tab.model.table_row(r) for r in range(tab.model.rowCount())]
    assert shown == [0, 1, 2, 3, 4]  # ordine della tabella
    values, mask = np.asarray(table["Vmag"].data, dtype=float), np.asarray(table["Vmag"].mask, dtype=bool)
    for direction in ("ascending", "descending"):
        entry = click_header(qtbot, win, tab, "Vmag")
        assert entry.result.status == "ok"
        assert entry.command.parameters == {"layer": "L1", "column": "Vmag", "direction": direction}
        assert entry.command.requested_by.source == "mouse"
        shown = [tab.model.table_row(r) for r in range(tab.model.rowCount())]
        assert shown == expected_order(values, mask, direction)
        assert shown[-1] == 1  # il mancante in fondo in entrambi i versi
        indicator = tab.view.horizontalHeader()
        assert indicator.sortIndicatorSection() == tab.model.names.index("Vmag")
        assert direction in tab.info.text()
    assert expected_order(values, mask, "ascending") == [2, 4, 0, 3, 1]  # a pari valore l'ordine originale
    assert expected_order(values, mask, "descending") == [0, 3, 2, 4, 1]
    # la tabella del 13 non cambia (D13-5)
    after = win.session.workspace.state.layer("L1").data.table
    assert after is table
    for n in table.colnames:
        np.testing.assert_array_equal(np.array(after[n]), before[n])  # NaN uguale a NaN
        np.testing.assert_array_equal(np.array(getattr(after[n], "mask", False)), masks[n])
    # colonna non ordinabile (array per riga): rifiuto con messaggio, ordine invariato
    shown_before = [tab.model.table_row(r) for r in range(tab.model.rowCount())]
    entry = click_header(qtbot, win, tab, "Vec")
    assert entry.result.error.code == "TABLE_SORT_UNSUPPORTED"
    assert [m for m in win.messages.messages if m[1] == "TABLE_SORT_UNSUPPORTED"]
    assert [tab.model.table_row(r) for r in range(tab.model.rowCount())] == shown_before


# =============================================================================
# T2, T3 — selezione sincronizzata


def test_t2_select_rows_from_table(qtbot, win, tmp_path):
    center_on(qtbot, win, *PLEIADES, 10.0)
    open_catalog(qtbot, win, tmp_path)
    wait_points(qtbot, win, 4)  # la riga D non ha posizione
    tab = page(win)
    since = len(history(win))
    click_row(tab, 0)
    click_row(tab, 2, Qt.KeyboardModifier.ControlModifier)
    click_row(tab, 4, Qt.KeyboardModifier.ControlModifier)
    wait_command(qtbot, win, "catalog.select", since, lambda e: len(e.command.parameters["rows"]) == 3)
    selects = [e for e in history(win) if e.command.name == "catalog.select"]
    assert len(selects) == 1  # una sola richiesta a fine gesto
    entry = selects[0]
    assert entry.command.parameters == {"layer": "L1", "rows": [0, 2, 4]}
    assert entry.command.requested_by.source == "mouse" and entry.result.values["source"] is None
    assert win.session.workspace.state.layer("L1").selection == (0, 2, 4)
    points = win.sky.renderer.points[0]
    assert points.rows.tolist() == [0, 1, 2, 4]
    assert points.selected.tolist() == [True, False, True, True]  # evidenziate nel 41
    assert "3" in tab.record_title.text() and tab.record.rowCount() == 0  # più righe: nessun record
    # riga non disegnabile: selezionabile qui, marcata "non disegnata"
    assert tab.model.headerData(3, Qt.Orientation.Vertical) == f"3 {NOT_DRAWN_MARK}"
    assert tab.model.headerData(0, Qt.Orientation.Vertical) == "0"
    since = len(history(win))
    click_row(tab, 3)
    wait_command(qtbot, win, "catalog.select", since, lambda e: e.command.parameters["rows"] == [3])
    assert "not drawn" in tab.record_title.text() and tab.record_shown[0] == 3
    assert not win.sky.card.isVisible() or "no position" in win.sky.card.text()


def test_t3_select_from_sky(qtbot, win, tmp_path):
    center_on(qtbot, win, *PLEIADES, 10.0)
    open_catalog(qtbot, win, tmp_path)
    wait_points(qtbot, win, 4)
    tab = page(win)
    click_header(qtbot, win, tab, "Vmag")  # ordinata: la riga 2 della tabella è la prima mostrata
    tab.view.verticalScrollBar().setValue(tab.view.verticalScrollBar().maximum())
    at = screen_point(win, index=2)
    since = len(history(win))
    mouse(win.sky, QEvent.Type.MouseButtonPress, at)
    mouse(win.sky, QEvent.Type.MouseButtonRelease, at)
    entry = wait_command(qtbot, win, "catalog.select", since)
    assert entry.command.parameters["rows"] == [2]
    assert tab.selected_rows() == [2]
    shown = tab.model.shown_row(2)
    assert shown == 0
    rect = tab.view.visualRect(tab.model.index(shown, 0))
    assert tab.view.viewport().rect().contains(rect.center())  # riga visibile
    assert tab.record_shown[0] == 2 and tab.record.rowCount() == len(tab.model.names)
    assert win.sky.card.isVisible()  # il riquadro sul cielo resta
    # clic nel vuoto: selezione tolta anche nella tabella
    corner = QPoint(30, 30)
    mouse(win.sky, QEvent.Type.MouseButtonPress, corner)
    mouse(win.sky, QEvent.Type.MouseButtonRelease, corner)
    wait_settled(qtbot, win)
    assert tab.selected_rows() == [] and tab.record_shown is None


# =============================================================================
# T4 — record


def test_t4_record_equals_record_view(qtbot, win, tmp_path):
    path = open_catalog(qtbot, win, tmp_path)
    tab = page(win)
    click_row(tab, 1)  # riga B: Vmag e Flag mancanti
    qtbot.waitUntil(lambda: tab.record_shown is not None, timeout=30000)
    expected = _jsonable(record_view(load_table(path), 1))
    row, record = tab.record_shown
    assert row == 1 and record == expected
    assert [tab.record.item(i, 0).text() for i in range(tab.record.rowCount())] == [f["name"] for f in expected]
    for i, field in enumerate(expected):
        value = tab.record.item(i, 1).text()
        if field["missing"]:
            assert value == MISSING_MARK
        elif isinstance(field["value"], float):
            assert float(value) == field["value"]  # valore pieno, si rilegge identico
        elif isinstance(field["value"], (str, int)):
            assert value == str(field["value"])
        assert tab.record.item(i, 2).text() == (field["unit"] or "")
        assert tab.record.item(i, 3).text() == (field["ucd"] or "")
    assert [f["name"] for f in expected if f["missing"]] == ["Vmag", "Flag"]
    assert "B" in tab.record_title.text() and "row 1" in tab.record_title.text()


# =============================================================================
# T5 — valori mostrati


def cell(tab, shown, column, role=Qt.ItemDataRole.DisplayRole):
    return tab.model.data(tab.model.index(shown, tab.model.names.index(column)), role)


def test_t5_values_shown(qtbot, win, tmp_path):
    path = open_catalog(qtbot, win, tmp_path)
    tab = page(win)
    t = load_table(path).table
    # colonne di posizione ICRS: testi di format_coordinates del 10 (sessagesimale, cifre di DC3)
    for r in (0, 1, 2, 4):
        lon = cw.format_coordinates(values=t["RA_ICRS"][r] * u.deg, frame="icrs", axis="lon").lon[0]
        lat = cw.format_coordinates(values=t["DE_ICRS"][r] * u.deg, frame="icrs", axis="lat").lat[0]
        assert cell(tab, r, "RA_ICRS") == lon and cell(tab, r, "DE_ICRS") == lat
    assert cell(tab, 0, "RA_ICRS") == "03h47m29.06s"
    model = tab.model
    assert model.headerData(1, Qt.Orientation.Horizontal) == "RA_ICRS\nh m s"
    assert model.headerData(2, Qt.Orientation.Horizontal) == "DE_ICRS\n° ′ ″"
    # magnitudini a 3 decimali; formato dichiarato; più breve che si rilegge; mancanti
    assert [cell(tab, r, "Vmag") for r in range(5)] == ["3.500", MISSING_MARK, "2.250", "3.500", "2.250"]
    assert [cell(tab, r, "Plx") for r in range(5)] == ["7.12", "7.50", MISSING_MARK, "8.00", "6.20"]
    assert [cell(tab, r, "Flux") for r in range(5)] == ["0.1", "1e-20", "3.0", "0.30000000000000004", "2.5"]
    assert [cell(tab, r, "Flag") for r in range(5)] == ["1", MISSING_MARK, "1", "0", "1"]
    assert cell(tab, 3, "RA_ICRS") == MISSING_MARK
    assert cell(tab, 1, "Vmag", Qt.ItemDataRole.ToolTipRole) == "missing value"
    # suggerimento e copia: valore pieno, identico al float64 della tabella, con l'unità
    for r, column in ((0, "Plx"), (0, "RA_ICRS"), (4, "Vmag"), (1, "Flux")):
        tip = cell(tab, r, column, Qt.ItemDataRole.ToolTipRole)
        text, unit = tip.rsplit(" ", 1)
        assert float(text) == float(t[column][r]) and unit == str(t[column].unit)
    assert cell(tab, 0, "Plx", Qt.ItemDataRole.ToolTipRole) == "7.123 mas"
    header_tip = model.headerData(model.names.index("Vmag"), Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)
    assert "UCD: phot.mag;em.opt.V" in header_tip and "V magnitude" in header_tip and "[mag]" in header_tip
    click_row(tab, 0)
    qtbot.waitUntil(lambda: tab.selected_rows() == [0], timeout=30000)
    QTest.keySequence(tab.view, QKeySequence.StandardKey.Copy)
    lines = QGuiApplication.clipboard().text().split("\n")
    assert lines[0].split("\t")[:4] == ["Name", "RA_ICRS [deg]", "DE_ICRS [deg]", "Vmag [mag]"]
    copied = lines[1].split("\t")
    assert copied[:6] == ["A", "56.8711", "24.1051", "3.5", "7.123", "0.1"]
    # stile decimale di "Coordinates shown" (view.set_coordinate_display)
    win.submit("view.set_coordinate_display", {"frame": "icrs", "format": "decimal"})
    wait_settled(qtbot, win)
    assert cell(tab, 0, "RA_ICRS") == cw.format_coordinates(
        values=t["RA_ICRS"][0] * u.deg, frame="icrs", axis="lon", style="decimal").lon[0] == "56.871100"
    assert model.headerData(1, Qt.Orientation.Horizontal) == "RA_ICRS\ndeg"
    # colonne di posizione galattiche: nel frame della colonna, nessuna conversione
    open_catalog(qtbot, win, tmp_path, GALACTIC, "g.xml")
    gal = page(win, "L2")
    assert win.catalog_panel.tabs.currentWidget() is gal
    for r, (lon, lat) in enumerate(((166.6, -23.5), (0.25, 1.125))):
        assert cell(gal, r, "GLON") == cw.format_coordinates(values=lon * u.deg, frame="galactic", axis="lon",
                                                             style="decimal").lon[0]
        assert cell(gal, r, "GLAT") == cw.format_coordinates(values=lat * u.deg, frame="galactic", axis="lat",
                                                             style="decimal").lat[0]
    win.submit("view.set_coordinate_display", {"frame": "icrs", "format": "sexagesimal"})
    wait_settled(qtbot, win)
    assert cell(gal, 1, "GLON") == cw.format_coordinates(values=0.25 * u.deg, frame="galactic", axis="lon").lon[0]
    assert model.headerData(model.names.index("Vmag"), Qt.Orientation.Horizontal) == "Vmag\nmag"
    # livello rimosso: scheda chiusa
    win.submit("layer.remove", {"layer": "L2"})
    wait_settled(qtbot, win)
    assert page(win, "L2") is None and win.catalog_panel.tabs.count() == 1


def test_t5_decimal_point_in_italian(qtbot, settings_path, cache, tmp_path):  # noqa: F811
    QSettings(settings_path, QSettings.Format.IniFormat).setValue("language", "it")
    win = make_window(qtbot, settings_path, cache)
    try:
        assert win.language == "it"
        path = open_catalog(qtbot, win, tmp_path)
        tab = page(win)
        assert [cell(tab, r, "Vmag") for r in (0, 2)] == ["3.500", "2.250"]
        assert cell(tab, 0, "Plx") == "7.12" and cell(tab, 0, "DE_ICRS").endswith("18.4″")
        assert tab.model.texts["missing"] == "valore mancante"
        assert load_table(path).table["Plx"][0] == 7.123
    finally:
        win.close()


def test_night_mode_table(qtbot, win, tmp_path):
    open_catalog(qtbot, win, tmp_path)
    win.submit("ui.set_appearance", {"mode": "night"})
    wait_settled(qtbot, win)
    from PySide6.QtGui import QPalette
    for role in (QPalette.ColorRole.Base, QPalette.ColorRole.Text, QPalette.ColorRole.PlaceholderText):
        color = page(win).view.palette().color(role)
        assert color.red() >= color.green() and color.red() >= color.blue()  # solo toni di rosso
    missing = cell(page(win), 1, "Vmag", Qt.ItemDataRole.ForegroundRole)
    assert missing.red() > missing.green() and missing.red() > missing.blue()


# =============================================================================
# T6 — un milione di righe (perf)


@pytest.mark.perf
def test_t6_one_million_rows(qtbot, tmp_path):
    n = 1_000_000
    rng = np.random.default_rng(3)
    (tmp_path / "s.xml").write_text(votable())
    small = load_table(str(tmp_path / "s.xml"))
    mag = MaskedColumn(rng.uniform(5, 20, n), name="Vmag", unit=u.mag, mask=rng.uniform(size=n) < 0.01)
    mag.meta["ucd"] = "phot.mag;em.opt.V"
    big = Table([MaskedColumn(rng.uniform(0, 360, n), name="RA_ICRS", unit=u.deg),
                 MaskedColumn(rng.uniform(-90, 90, n), name="DE_ICRS", unit=u.deg), mag])
    layer = Layer("L1", "catalog", "big", dataclasses.replace(small, table=big))
    tracemalloc.start()
    start = time.perf_counter()
    model = CatalogTableModel(layer)
    opened = time.perf_counter() - start
    texts = [model.cell_text(r, c) for r in range(40) for c in range(3)]
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert model.table is big and model.rowCount() == n and len(texts) == 120
    data_bytes = sum(big[c].data.nbytes for c in big.colnames)
    start = time.perf_counter()
    sorted_layer = dataclasses.replace(layer, sort={"column": "Vmag", "direction": "ascending"})
    model.set_layer(sorted_layer)
    sort_seconds = time.perf_counter() - start
    values, mask = np.asarray(big["Vmag"].data), np.asarray(big["Vmag"].mask)
    assert model.order.tolist() == expected_order(values, mask, "ascending")
    print(f"\nT6: {n} righe, apertura del modello in {opened * 1000:.1f} ms, memoria aggiuntiva "
          f"{peak / 2**20:.1f} MiB (dati della tabella {data_bytes / 2**20:.1f} MiB, non copiati), "
          f"ordinamento in {sort_seconds * 1000:.0f} ms")
    assert peak < data_bytes  # nessuna copia dei dati: solo l'ordine mostrato (8 byte per riga)
