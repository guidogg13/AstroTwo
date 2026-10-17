"""Test della finestra principale (40 §12) con pytest-qt, piattaforma ``offscreen`` e servizi simulati."""

import json
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtCore import QElapsedTimer, QLocale, QSettings, Qt, QTimer
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from astrotwo.core import catalogs, hips
from astrotwo.core import coordinates_wcs as cw
from astrotwo.core.commands import Command, RequestedBy, default_registry
from astrotwo.ui import main_window as mw
from astrotwo.ui.main_window import MainWindow, ThreadCache, apply_appearance, load_translations
from tests.core.test_commands import files, sky  # noqa: F401 - fixture e aiuti del 05
from tests.core.test_coordinates_wcs import simbad_table

TS_FILE = Path(mw.__file__).parent / "i18n" / "astrotwo_it.ts"


@pytest.fixture
def settings_path(tmp_path):
    return str(tmp_path / "settings.ini")


def make_window(qtbot, settings_path, cache, **kw):
    settings = QSettings(settings_path, QSettings.Format.IniFormat)
    win = MainWindow(registry=default_registry(cache=ThreadCache(root=cache.root)), settings=settings,
                     startup_commands=False, **kw)
    win.confirm = lambda title, text: True
    win.modals = []
    win.show_modal = lambda title, text: win.modals.append((title, text))
    qtbot.addWidget(win)
    win.resize(1000, 700)
    win.show()
    return win


@pytest.fixture
def window(qtbot, settings_path, cache):
    win = make_window(qtbot, settings_path, cache)
    yield win
    win.confirm = lambda title, text: True  # alla fine si esce sempre: nessun thread lasciato acceso
    win.close()


def wait_idle(qtbot, win, timeout=15000):
    qtbot.waitUntil(lambda: not win.busy(), timeout=timeout)


def names(win):
    return [e.command.name for e in win.session.history]


@pytest.fixture
def offline(monkeypatch):
    """HiPS e cataloghi di rete simulati: rispondono subito con un errore del modulo (nessuna rete)."""
    def no_hips(*a, **k):
        raise hips.HiPSError("NET_TIMEOUT", "servizio HiPS simulato non raggiungibile")

    def no_catalog(*a, **k):
        raise catalogs.CatalogsError("NET_TIMEOUT", "servizio del catalogo simulato non raggiungibile")

    monkeypatch.setattr(hips, "set_survey", no_hips)
    monkeypatch.setattr(catalogs, "load_catalog", no_catalog)


@pytest.fixture
def fake_simbad(monkeypatch):
    monkeypatch.setattr(cw, "_query_simbad", lambda name, timeouts: (
        simbad_table(rows=1 if name == "M31" else 0), "https://simbad.cds.unistra.fr/simbad/sim-tap"))


def trigger(win, name):
    from PySide6.QtGui import QAction
    action = win.findChild(QAction, name)
    assert action is not None, name
    action.trigger()


# =============================================================================
# T1 — menu → comandi


def test_t1_menu_items_produce_commands(qtbot, window, files, offline, tmp_path, monkeypatch):  # noqa: F811
    win = window
    paths = {"image.open": files["image"], "catalog.open_file": files["catalog"], "moc.open": files["moc"]}
    win.open_path = lambda name: paths.get(name)
    png = tmp_path / "view.png"
    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(png), "")))
    for name in ("openImage", "openCatalog", "openMoc", "grid", "gridGalactic", "coords_icrs_decimal",
                 "toolDistance", "panel_messages", "exportPng", "fullscreen", "night"):
        trigger(win, name)
    wait_idle(qtbot, win)
    # Data → HiPS survey… con la copia locale delle collezioni simulata
    index = hips.CollectionIndex()
    index.records = ({"ID": "CDS/P/DSS2/color", "obs_title": "DSS colored"},
                     {"ID": "CDS/P/2MASS/color", "obs_title": "2MASS colour"})
    index.origin, index.synced_at = "simulato", hips.datetime.now(hips.UTC)
    win.collection_index_loader = lambda: index
    dialog = win.hips_dialog()
    qtbot.waitUntil(lambda: dialog.results.count() == 2)
    dialog.search.setText("2mass")
    assert dialog.results.count() == 1
    dialog.results.setCurrentRow(0)
    assert dialog.survey.text() == "CDS/P/2MASS/color"
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
    # Data → Catalog in view… (centro e raggio della vista del 10; la scala la darà il 41)
    win.submit("view.set_zoom", {"scale": {"value": 1.0, "unit": "arcsec"}, "window": win.view_window()})
    win.go_to("56.75 24.12")
    wait_idle(qtbot, win)
    cat = win.catalog_dialog()
    assert cat is not None, [(e.command.name, e.result.status, e.result.error) for e in win.session.history][-4:]
    cat.catalog.setCurrentText("II/246/out")
    cat.accept()
    wait_idle(qtbot, win)
    got = names(win)
    assert got == ["image.open", "catalog.open_file", "moc.open", "view.set_grid", "view.set_grid",
                   "view.set_coordinate_display", "ui.set_tool", "ui.set_panel", "view.export_png",
                   "ui.set_fullscreen", "ui.set_appearance", "hips.set_survey", "view.set_zoom", "view.go_to",
                   "catalog.load_region"]
    by_name = {}
    for e in win.session.history:
        by_name.setdefault(e.command.name, []).append(e)
    assert by_name["image.open"][0].command.parameters["file"]["path"] == str(Path(files["image"]).resolve())
    assert by_name["image.open"][0].result.status == "ok"
    assert [e.command.parameters["frame"] for e in by_name["view.set_grid"]] == ["icrs", "galactic"]
    assert by_name["view.set_coordinate_display"][0].command.parameters == {"frame": "icrs", "format": "decimal"}
    assert by_name["ui.set_tool"][0].command.parameters == {"tool": "distance"} and win.active_tool == "distance"
    assert by_name["ui.set_panel"][0].command.parameters == {"panel": "messages", "visible": False}
    assert not win.docks["messages"].isVisible()
    # export_png: disegno del 41 non ancora collegato → COMMAND_UNKNOWN del 05
    assert by_name["view.export_png"][0].result.error.code == "COMMAND_UNKNOWN"
    assert by_name["ui.set_appearance"][0].command.parameters == {"mode": "night"} and win.appearance == "night"
    assert by_name["hips.set_survey"][0].command.parameters == {"survey": "CDS/P/2MASS/color"}
    assert by_name["hips.set_survey"][0].result.error.code == "NET_TIMEOUT"
    region = by_name["catalog.load_region"][0].command.parameters
    view = win.session.workspace.state.view
    assert region["catalog"] == "II/246/out" and region["max_rows"] == 100_000
    assert region["center"] == cw_sky_json(view.center)
    assert region["radius"]["value"] == pytest.approx(view.geometry.field_radius.to_value(region["radius"]["unit"]))
    for e in win.session.history:
        cls = win.registry.spec(e.command.name).command_class
        assert e.command_class == cls
        assert e.command.requested_by.source in ("menu", "keyboard")


def cw_sky_json(point):
    from astrotwo.core.commands import sky_json
    return sky_json(point)


def test_t1_session_and_settings_menus(qtbot, window, files, tmp_path):  # noqa: F811
    win = window
    win.submit("moc.open", {"file": {"path": files["moc"]}})
    wait_idle(qtbot, win)
    assert win.unsaved()
    target = tmp_path / "work"
    win.save_session(str(target))
    saved = Path(str(target) + ".astrotwo.json")
    assert saved.is_file() and not win.unsaved()
    data = json.loads(saved.read_text())
    assert [c["command"]["name"] for c in data["commands"]] == ["moc.open"] and "conversations" not in data
    win.open_path = lambda name: str(saved) if name == "session.open" else None
    trigger(win, "openSession")
    wait_idle(qtbot, win)
    assert [e.command.name for e in win.session.history] == ["moc.open"]
    assert win.session.history.entries[0].command.requested_by.source == "menu"  # conserva chi lo aveva chiesto
    assert win.session.workspace.state.layers[0].kind == "moc"


# =============================================================================
# T2 — Riesegui


def test_t2_rerun(qtbot, window):
    win = window
    win.submit("view.set_coordinate_display", {"frame": "galactic", "format": "decimal"})
    win.go_to("56.75 24.12")
    win.submit("view.set_grid", {"visible": True, "frame": "icrs"})
    wait_idle(qtbot, win)
    before = win.session.workspace.state.state_json()
    win.history.table.selectAll()
    assert len(win.history.selected()) == 3
    win.history.rerun_button.click()
    wait_idle(qtbot, win)
    entries = win.session.history.entries
    assert [e.number for e in entries] == [1, 2, 3, 4, 5, 6]
    assert [e.command.name for e in entries[3:]] == [e.command.name for e in entries[:3]]
    assert all(e.command.requested_by.source == "history" and e.result.status == "ok" for e in entries[3:])
    assert win.session.workspace.state.state_json() == before
    win.history.table.selectRow(0)
    win.history.copy_button.click()
    assert json.loads(QApplication.clipboard().text()) == entries[0].command.to_json()


# =============================================================================
# T3, T4 — interfaccia reattiva e Annulla


def test_t3_t4_responsive_and_cancel(qtbot, window, monkeypatch):
    win = window
    slow_started = []

    def slow_catalog(*a, **k):
        slow_started.append(time.monotonic())
        time.sleep(5.0)  # servizio simulato che risponde dopo 5 s
        return object()  # risultato da scartare: il 05 vede l'annullamento al passo successivo

    monkeypatch.setattr(catalogs, "load_catalog", slow_catalog)
    win.submit("view.set_zoom", {"scale": {"value": 1.0, "unit": "arcsec"}, "window": win.view_window()})
    win.go_to("56.75 24.12")
    wait_idle(qtbot, win)
    before = win.session.workspace.state.state_json()
    gaps, clock = [], QElapsedTimer()
    clock.start()
    probe = QTimer()
    probe.setInterval(10)

    def tick():
        gaps.append(clock.restart())

    probe.timeout.connect(tick)
    probe.start()
    view = win.session.workspace.state.view
    win.submit("catalog.load_region", {"catalog": "II/246/out", "center": cw_sky_json(view.center),
                                       "radius": {"value": 0.1, "unit": "deg"}})
    qtbot.waitUntil(lambda: bool(slow_started), timeout=5000)
    qtbot.wait(1500)
    probe.stop()
    assert max(gaps[1:]) < 100, max(gaps)  # sonda di latenza del thread principale (§9)
    assert win.status.cancel_button.isVisible() and win.status.progress_bar.isVisible()
    assert "catalog.load_region" in win.status.command_label.text()
    assert win.status.network_label.text().startswith("Network: 1")
    win.status.cancel_button.click()
    wait_idle(qtbot, win, timeout=10000)
    last = win.session.history.entries[-1]
    assert last.command.name == "catalog.load_region" and last.result.status == "cancelled"
    assert last.result.error.code == "COMMAND_CANCELLED"
    assert win.session.workspace.state.state_json() == before
    assert not win.status.cancel_button.isVisible()
    assert win.history.table.item(win.history.table.rowCount() - 1, 5).text() == "cancelled"


# =============================================================================
# T5 — messaggi invariati, finestra modale solo per un file illeggibile


def test_t5_messages_unchanged(qtbot, window, files, tmp_path):  # noqa: F811
    win = window
    win.submit("view.set_center", {"position": sky(10.0, 95.0)})
    wait_idle(qtbot, win)
    with pytest.raises(cw.CoordinatesWcsError) as direct:
        cw.SkyFrame.from_lonlat(10.0 * cw.u.deg, 95.0 * cw.u.deg, "icrs")
    assert win.messages.messages[-1] == ("#1", direct.value.code, direct.value.message, True)
    assert win.modals == []
    plain = tmp_path / "plain.xml"
    shutil.copy(files["catalog"], plain)  # catalogo senza UCD: avvisi del 13/05
    text = plain.read_text().replace('ucd="pos.eq.ra;meta.main"', "").replace('ucd="pos.eq.dec;meta.main"', "")
    plain.write_text(text.replace('name="RA"', 'name="X1"').replace('name="DE"', 'name="X2"'))
    win.submit("catalog.open_file", {"file": {"path": str(plain)}})
    wait_idle(qtbot, win)
    result = win.session.history.entries[-1].result
    assert result.warnings
    shown = [(code, text) for ref, code, text, error in win.messages.messages if ref == "#2"]
    assert shown == [(w.code, w.text) for w in result.warnings]
    assert win.modals == []
    broken = tmp_path / "broken.fits"
    broken.write_bytes(b"not a fits file")
    win.submit("image.open", {"file": {"path": str(broken)}})
    wait_idle(qtbot, win)
    error = win.session.history.entries[-1].result.error
    assert win.messages.messages[-1] == ("#3", error.code, error.text, True)
    assert win.modals == [("The file cannot be opened", f"{error.code}: {error.text}")]


# =============================================================================
# T6, T7 — traduzioni e punto decimale


def test_t6_translations_complete(qapp, tmp_path):
    copy = tmp_path / "check_it.ts"
    shutil.copy(TS_FILE, copy)
    lupdate = Path(sys.executable).parent / "pyside6-lupdate"
    subprocess.run([str(lupdate), mw.__file__, "-ts", str(copy), "-no-obsolete", "-locations", "none"],
                   check=True, capture_output=True)
    messages = list(ET.parse(copy).getroot().iter("message"))
    assert len(messages) > 100
    missing = [m.find("source").text for m in messages
               if m.find("translation").get("type") == "unfinished" or not (m.find("translation").text or "")]
    assert missing == []
    assert (TS_FILE.parent / "astrotwo_it.qm").is_file()
    language, warnings = load_translations("it")
    assert language == "it" and warnings == []
    assert QApplication.translate("QPlatformTheme", "Cancel") == "Annulla"  # traduzione di Qt (qtbase_it)
    assert load_translations("en") == ("en", [])


def test_translation_missing_warning(qtbot, settings_path, cache, monkeypatch, tmp_path):
    monkeypatch.setattr(mw, "I18N_DIR", tmp_path)
    QSettings(settings_path, QSettings.Format.IniFormat).setValue("language", "it")
    win = make_window(qtbot, settings_path, cache)
    assert win.language == "en"
    assert win.messages.messages[0][1] == "UI_TRANSLATION_MISSING"
    assert win.menuBar().actions()[0].text() == "File" and win.menuBar().actions()[1].text() == "View"
    win.close()


def test_t7_decimal_point_in_italian(qtbot, settings_path, cache):
    QLocale.setDefault(QLocale("it_IT"))
    QSettings(settings_path, QSettings.Format.IniFormat).setValue("language", "it")
    win = make_window(qtbot, settings_path, cache)
    try:
        assert win.language == "it"
        assert [a.text() for a in win.menuBar().actions()][:3] == ["File", "Vista", "Dati"]
        assert QLocale().decimalPoint() == "."
        win.submit("view.set_zoom", {"scale": {"value": 1.5, "unit": "arcsec"}, "window": win.view_window()})
        win.go_to("56.75 24.125")
        wait_idle(qtbot, win)
        params = win.history.table.item(0, 4).text()
        assert "1.5" in params and "1,5" not in params
        win.history.table.selectRow(1)
        detail = win.history.detail.toPlainText()
        assert "56.75" in detail and "24.125" in detail and "56,75" not in detail and "24,125" not in detail
        assert json.loads(detail)["result"]["values"] == win.session.history.entries[1].result.values
        win.status.show_cursor(win.session.history.entries[1].result.__class__(
            "ok", values={"sky": sky(56.75, 24.125), "pixel": {"value": 0.25, "unit": "Jy"}}))
        assert "56.75" in win.status.cursor_label.text() and "0.25 Jy" in win.status.cursor_label.text()
        cat = win.catalog_dialog()
        assert cat.max_rows.text() == "100000"  # nessun separatore delle migliaia che sembri un decimale
        cat.reject()
        assert win.history.table.item(0, 2).text() == "Utente"
    finally:
        load_translations("en")
        win.close()


# =============================================================================
# T8 — preferenze ritrovate dopo il riavvio


def test_t8_preferences(qtbot, settings_path, cache):
    win = make_window(qtbot, settings_path, cache)
    dialog = win.preferences_dialog()
    dialog.language.setCurrentIndex(dialog.language.findData("en"))
    dialog.cache_limit.setText("123456789")
    dialog.coordinates.setCurrentIndex(dialog.coordinates.findData("galactic"))
    dialog.survey.setText("CDS/P/2MASS/color")
    dialog.appearance.setCurrentIndex(dialog.appearance.findData("light"))
    assert "byte" in dialog.cache_usage.text().lower() or "Used" in dialog.cache_usage.text()
    dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
    wait_idle(qtbot, win)
    prefs = [e for e in win.session.history if e.command.name == "prefs.set"]
    assert {e.command.parameters["key"] for e in prefs} == set(mw.PREFERENCES)
    assert all(e.command_class == "application" and e.result.status == "ok" for e in prefs)
    assert win.appearance == "light" and win.cache.limit_bytes == 123456789
    win.submit("prefs.set", {"key": "cache/limit_bytes", "value": "-1"})
    wait_idle(qtbot, win)
    assert win.session.history.entries[-1].result.error.code == "PREFERENCE_INVALID"
    win.close()
    again = make_window(qtbot, settings_path, cache)
    assert {k: again.preference(k) for k in mw.PREFERENCES} == {
        "language": "en", "cache/limit_bytes": "123456789", "view/coordinates": "galactic",
        "hips/default_survey": "CDS/P/2MASS/color", "appearance": "light"}
    assert again.coordinate_actions["galactic"].isChecked()
    again.close()


def test_startup_commands_from_preferences(qtbot, settings_path, cache, offline):
    QSettings(settings_path, QSettings.Format.IniFormat).setValue("view/coordinates", "icrs_decimal")
    settings = QSettings(settings_path, QSettings.Format.IniFormat)
    win = MainWindow(registry=default_registry(cache=ThreadCache(root=cache.root)), settings=settings)
    win.confirm = lambda *a: True
    win.show_modal = lambda *a: None
    qtbot.addWidget(win)
    wait_idle(qtbot, win)
    entries = win.session.history.entries
    assert [e.command.name for e in entries] == ["view.set_coordinate_display", "hips.set_survey"]
    assert entries[0].command.parameters == {"frame": "icrs", "format": "decimal"}
    assert entries[1].command.parameters == {"survey": "CDS/P/DSS2/color"}
    win.close()


# =============================================================================
# T9 — sessione fermata


def test_t9_session_stopped(qtbot, window, files):  # noqa: F811
    win = window
    win.submit("image.open", {"file": {"path": files["image"]}})
    wait_idle(qtbot, win)
    saved = win.saved_path or str(Path(files["image"]).parent / "s.astrotwo.json")
    assert win.save_session(saved)
    data = bytearray(Path(files["image"]).read_bytes())
    data[-1] ^= 0xFF
    Path(files["image"]).write_bytes(bytes(data))
    win.open_session(saved)
    wait_idle(qtbot, win)
    assert win.modals and win.modals[-1][0] == "The session was stopped"
    assert win.modals[-1][1].startswith("SESSION_FILE_CHANGED")
    assert win.messages.messages[-1][1] == "SESSION_FILE_CHANGED"


def test_open_session_asks_confirmation(qtbot, window, files, tmp_path):  # noqa: F811
    win = window
    win.submit("moc.open", {"file": {"path": files["moc"]}})
    wait_idle(qtbot, win)
    asked = []
    win.confirm = lambda title, text: asked.append(title) or False
    assert win.open_session(str(tmp_path / "x.astrotwo.json")) is None
    assert asked == ["Open session"]


# =============================================================================
# T10 — spazio del pannello IA


def test_t10_assistant_area(qtbot, window):
    win = window
    dock = win.docks["assistant"]
    assert win.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea
    assert dock.minimumWidth() == 380 and dock.maximumWidth() == 420
    assert "not available" in dock.widget().text()
    action = win.panel_actions["assistant"]
    assert action.shortcut().toString() == "Meta+Ctrl+A" and action.isEnabled()
    assert action in win.toolbar.actions()
    action.trigger()
    wait_idle(qtbot, win)
    assert not dock.isVisible()
    action.trigger()
    wait_idle(qtbot, win)
    assert dock.isVisible()
    assert [e.command.parameters for e in win.session.history] == [
        {"panel": "assistant", "visible": False}, {"panel": "assistant", "visible": True}]


# =============================================================================
# T11 — Vai a


def test_t11_go_to(qtbot, window, fake_simbad):
    win = window
    win.go_to_field.setText("M31")
    qtbot.keyClick(win.go_to_field, Qt.Key.Key_Return)
    wait_idle(qtbot, win)
    first = win.session.history.entries[0]
    assert first.command.name == "view.go_to" and first.command.requested_by.source == "keyboard"
    assert first.result.values["resolved"]["source"]
    assert first.result.provenance[0]["origin"] == "https://simbad.cds.unistra.fr/simbad/sim-tap"
    assert first.command.parameters["window"] == win.view_window()
    win.go_to("03:47:00 +24:07:00")
    wait_idle(qtbot, win)
    second = win.session.history.entries[1]
    assert second.result.status == "ok" and "sessagesimale" in second.result.values["interpreted_as"]
    win.go_to("%%%")
    wait_idle(qtbot, win)
    bad = win.session.history.entries[2]
    assert bad.result.status == "error"
    with pytest.raises(cw.CoordinatesWcsError) as direct:
        cw.resolve_name("%%%", cache=win.cache._cache())
    assert (bad.result.error.code, bad.result.error.text) == (direct.value.code, direct.value.message)


# =============================================================================
# T13 — aspetto


NIGHT_THRESHOLD = 64  # componente verde o blu massima ammessa in modalità notte (0–255)


def palette_colors(palette):
    roles = [r for r in QPalette.ColorRole if r not in (QPalette.ColorRole.NoRole, QPalette.ColorRole.NColorRoles)]
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled):
        for role in roles:
            yield group, role, palette.color(group, role)


def test_t13_appearance(qtbot, window, monkeypatch):
    win = window
    app = QApplication.instance()
    monkeypatch.setattr(mw, "_system_color_scheme", lambda: Qt.ColorScheme.Light)
    assert apply_appearance("system") == "light"
    assert app.palette().color(QPalette.ColorRole.Window).lightness() > 128
    monkeypatch.setattr(mw, "_system_color_scheme", lambda: Qt.ColorScheme.Dark)
    assert apply_appearance("system") == "dark"
    assert app.palette().color(QPalette.ColorRole.Window).lightness() < 64
    monkeypatch.setattr(mw, "_system_color_scheme", lambda: Qt.ColorScheme.Unknown)
    assert apply_appearance("system") == "dark"  # tema di riferimento
    win.act_night.trigger()
    wait_idle(qtbot, win)
    assert win.appearance == "night"
    entry = win.session.history.entries[-1]
    assert entry.command.name == "ui.set_appearance" and entry.command_class == "application"
    for widget in [win, win.history.table, win.messages.table, win.go_to_field, win.status]:
        for group, role, color in palette_colors(widget.palette()):
            assert color.green() <= NIGHT_THRESHOLD and color.blue() <= NIGHT_THRESHOLD, (widget, group, role,
                                                                                           color.name())
    win.act_night.trigger()
    wait_idle(qtbot, win)
    assert win.appearance == "dark" and win.session.history.entries[-1].command.parameters == {"mode": "system"}


def stylesheet_colors(text):
    """Colori scritti nel foglio di stile: ``#rrggbb`` e ``rgba(r, g, b, a)``, come (rosso, verde, blu)."""
    for hexa in re.findall(r"#([0-9a-fA-F]{6})\b", text):
        yield tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))
    for r, g, b in re.findall(r"rgba\((\d+),\s*(\d+),\s*(\d+)", text):
        yield int(r), int(g), int(b)


def test_t13_night_stylesheet_and_icons(qtbot, window):
    """Modalità notte (§3.11): anche foglio di stile, icone e stati vuoti solo in toni di rosso; ⌃⌘N (D40-4)."""
    win = window
    assert win.act_night.shortcut().toString() == "Meta+Ctrl+N"
    win.act_night.trigger()
    wait_idle(qtbot, win)
    colors = list(stylesheet_colors(QApplication.instance().styleSheet()))
    assert len(colors) > 10
    assert all(g <= NIGHT_THRESHOLD and b <= NIGHT_THRESHOLD for _, g, b in colors), colors
    for act in win.toolbar_icons:
        image = act.icon().pixmap(32, 32).toImage()
        drawn = [image.pixelColor(x, y) for x in range(32) for y in range(32) if image.pixelColor(x, y).alpha()]
        assert drawn and all(c.green() <= NIGHT_THRESHOLD and c.blue() <= NIGHT_THRESHOLD for c in drawn), act
    win.act_night.trigger()
    wait_idle(qtbot, win)
    assert any(b > 200 for _, _, b in stylesheet_colors(QApplication.instance().styleSheet()))  # accento blu


def test_visual_guidelines(qtbot, window):
    """Linee guida visive (§3.11) e mockup: icone Lucide con licenza, barra, intestazioni, righe, stati vuoti."""
    win = window
    names_used = set(win.toolbar_icons.values()) | {"search", "x", "picture-in-picture-2", "telescope", "table-2",
                                                    "history", "message-square-warning", "sparkles", "layers"}
    for name in names_used:
        assert (mw.ICONS_DIR / f"{name}.svg").is_file(), name
    assert {p.stem for p in mw.ICONS_DIR.glob("*.svg")} == names_used  # nessuna icona inutilizzata
    licenses = (Path(mw.__file__).resolve().parents[3] / "THIRD_PARTY_LICENSES").read_text(encoding="utf-8")
    assert (mw.ICONS_DIR / "LICENSE").read_text(encoding="utf-8").strip() in licenses
    # ogni pulsante della barra è un'azione dei menu (nessuna funzione nuova), con icona e nome nel suggerimento
    menu_actions = {a for m in win.menuBar().actions() for a in m.menu().actions()}
    menu_actions |= {a for m in win.menuBar().actions() for s in m.menu().actions() if s.menu()
                     for a in s.menu().actions()}
    for act in win.toolbar_icons:
        assert act in win.toolbar.actions() and act in menu_actions
        assert not act.icon().isNull() and act.text() in act.toolTip()
    assert win.act_night in win.toolbar.actions()
    # intestazioni: pannelli soli con l'intestazione propria; quelli a schede usano le schede
    assert win.docks["layers"].titleBarWidget() is win.docks["layers"].header
    assert win.docks["commands"].titleBarWidget() is win.docks["commands"].no_header
    assert win.docks["layers"].header.title.font().capitalization() == QFont.Capitalization.AllUppercase
    assert win.history.table.verticalHeader().defaultSectionSize() == mw.ROW_HEIGHT
    assert win.messages.table.verticalHeader().defaultSectionSize() == mw.ROW_HEIGHT
    assert "42" in win.docks["table"].widget().text()
    # stati vuoti: spariscono alla prima riga senza cambiare le misure della vista
    size = win.view_window()
    assert win.history.empty.isVisibleTo(win.history) and win.messages.empty.isVisibleTo(win.messages)
    win.go_to("%%%")
    wait_idle(qtbot, win)
    assert not win.history.empty.isVisibleTo(win.history) and not win.messages.empty.isVisibleTo(win.messages)
    qtbot.wait(50)
    assert win.view_window() == size


def test_tabular_digits(window):
    assert window.status.cursor_label.font().featureValue(QFont.Tag("tnum")) == 1
    assert window.history.table.font().featureValue(QFont.Tag("tnum")) == 1


# =============================================================================
# T14 — colonna "chi"


def test_t14_who_column(qtbot, window):
    win = window
    win.submit("view.set_coordinate_display", {"frame": "icrs", "format": "decimal"})  # menu
    win.docks["table"].close()  # pulsante del pannello: mouse
    ai = RequestedBy("ai", conversation="c1", turn=2, call="call-7", profile="ollama", model="modello-simulato")
    win.submit_command(Command("layer.list", 1, {}, ai))
    wait_idle(qtbot, win)
    win.history.class_filter.setCurrentIndex(win.history.class_filter.findData("all"))
    win.history.table.selectRow(0)
    win.history.rerun_button.click()
    wait_idle(qtbot, win)
    who = [win.history.table.item(r, 2).text() for r in range(win.history.table.rowCount())]
    assert who == ["User", "User", "AI", "User"]
    assert [e.command.requested_by.source for e in win.session.history] == ["menu", "mouse", "ai", "history"]
    win.history.who_filter.setCurrentIndex(win.history.who_filter.findData("ai"))
    assert win.history.table.rowCount() == 1
    win.history.table.selectRow(0)
    detail = json.loads(win.history.detail.toPlainText())
    assert detail["command"]["requested_by"] == {"source": "ai", "conversation": "c1", "turn": 2, "call": "call-7",
                                                 "profile": "ollama", "model": "modello-simulato"}


def test_history_class_filter(qtbot, window):
    win = window
    win.submit("view.set_coordinate_display", {"frame": "icrs", "format": "decimal"})
    win.submit("ui.set_tool", {"tool": "distance"})
    wait_idle(qtbot, win)
    assert win.history.table.rowCount() == 1  # solo la classe session di default
    win.history.class_filter.setCurrentIndex(win.history.class_filter.findData("application"))
    assert win.history.table.rowCount() == 1
    assert win.history.table.item(0, 3).text() == "ui.set_tool"


# =============================================================================
# Coda, uscita, cache da più thread


def test_queue_order_and_main_thread_never_runs(qtbot, window, monkeypatch):
    import threading
    win = window
    threads = []
    original = win.registry.run

    def spy(*a, **k):
        threads.append(threading.current_thread() is threading.main_thread())
        return original(*a, **k)

    monkeypatch.setattr(win.registry, "run", spy)
    for k in range(5):
        win.submit("view.set_coordinate_display", {"frame": "icrs" if k % 2 else "galactic", "format": "decimal"})
    wait_idle(qtbot, win)
    assert threads == [False] * 5
    assert [e.command.parameters["frame"] for e in win.session.history] == ["galactic", "icrs", "galactic", "icrs",
                                                                            "galactic"]


def test_quit_with_running_command(qtbot, settings_path, cache, monkeypatch):
    win = make_window(qtbot, settings_path, cache)
    started = []

    def slow(*a, **k):
        started.append(1)
        time.sleep(1.0)
        return object()

    monkeypatch.setattr(catalogs, "load_catalog", slow)
    win.submit("catalog.load_region", {"catalog": "II/246/out", "center": sky(10.0, 41.0),
                                       "radius": {"value": 0.1, "unit": "deg"}})
    qtbot.waitUntil(lambda: bool(started))
    asked = []
    win.confirm = lambda title, text: asked.append(text) or False
    win.close()
    assert win.isVisible() and "still running" in asked[0]  # uscita rifiutata
    win.confirm = lambda title, text: True
    t0 = time.monotonic()
    win.close()
    assert not win.isVisible() and not win._thread.isRunning() and time.monotonic() - t0 < 5
    assert QSettings(settings_path, QSettings.Format.IniFormat).value("window/geometry") is not None


def test_thread_cache_one_instance_per_thread(cache):
    import threading
    proxy = ThreadCache(1000, root=cache.root)
    seen = {}

    def use(name):
        seen[name] = proxy._cache()
        proxy.usage()

    t = threading.Thread(target=use, args=("other",))
    t.start()
    t.join()
    use("main")
    assert seen["main"] is not seen["other"]
    proxy.limit_bytes = 2000
    assert proxy._cache().limit_bytes == 2000 and proxy.usage().limit_bytes == 2000


def test_status_bar_cursor_values(window):
    from astrotwo.core.commands import CommandResult
    bar = window.status
    bar.show_cursor(None)
    assert bar.cursor_label.text() == "No data"
    bar.show_cursor(CommandResult("ok", values={"sky": None}))
    assert bar.cursor_label.text() == "Outside the sky"
    bar.show_cursor(CommandResult("ok", values={"sky": sky(56.75, 24.12), "pixel": {
        "value": 105.5, "unit": "adu", "fits": {"x": 11, "y": 11}}}))
    text = bar.cursor_label.text()
    assert "56.75" in text and "105.5 adu" in text and "FITS (11, 11)" in text


def test_main_entry_point():
    import tomllib
    data = tomllib.loads((Path(__file__).resolve().parents[2] / "pyproject.toml").read_text())
    assert data["project"]["scripts"]["astrotwo"] == "astrotwo.ui.main_window:main"
    assert callable(mw.main)


@pytest.mark.perf
def test_t12_startup_time(qtbot, settings_path, cache):
    t0 = time.monotonic()
    win = make_window(qtbot, settings_path, cache)
    QApplication.processEvents()
    elapsed = time.monotonic() - t0
    win.close()
    assert elapsed <= 3.0
