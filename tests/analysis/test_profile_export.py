# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Esportazione del profilo (``mdfiles/25-analisi-profilo-oggetto.md`` §3.15, T15, T26, T27, T28; sprint C6).

Profili costruiti dal comando ``object.profile`` con le risposte vere registrate il 2026-11-07
(``tests/analysis/profile_fakes.py``: SIMBAD di Harvard, archivio Gaia ESA, IRSA, NASA Exoplanet Archive, ESASky; CDS
giù). Ogni file esportato si confronta con il risultato del comando: nessun valore ricalcolato. Nessuna rete.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re

import numpy as np
import pytest
from astropy.table import Table

from astrotwo.analysis.object_profile import command_specs
from astrotwo.analysis.profile_export import (
    ProfileExportError,
    export_profile,
    merge_profile_results,
    profile_values_table,
    sed_catalog_path,
    sed_catalog_table,
)
from astrotwo.core.commands import Command, RequestedBy, Session, default_registry
from astrotwo.ui.profiles import exec_object_export
from tests.analysis.profile_fakes import services  # noqa: F401


def session_with_export(cache) -> Session:
    registry = default_registry(cache=cache)
    for spec in command_specs():
        registry.register(spec)
    session = Session(registry)
    registry.bind("object.export", exec_object_export(lambda: session.history))
    return session


def profile(session: Session, params: dict):
    result = session.run(Command("object.profile", 1, params, RequestedBy("menu")))
    return session.history.entries[-1].number, result


def export(session: Session, commands, fmt, path, language="en"):
    return session.run(Command("object.export", 1, {"commands": list(commands), "format": fmt, "path": str(path),
                                                    "language": language}, RequestedBy("menu")))


def values_of(result) -> dict:
    return json.loads(json.dumps(result.values))


def text_of(value) -> str:
    number = value["value"] if isinstance(value, dict) and "value" in value else value
    if isinstance(number, bool):
        return "true" if number else "false"
    return repr(number) if isinstance(number, float) else str(number)


# =============================================================================
# T15 — ECSV dei valori con provenienza


def test_t15_ecsv_one_row_per_value_with_provenance(cache, services, tmp_path):  # noqa: F811
    session = session_with_export(cache)
    number, result = profile(session, {"name": "TRAPPIST-1"})
    data = merge_profile_results([(number, values_of(result))])
    path = tmp_path / "trappist.ecsv"
    written = export_profile(data, path, "ecsv")
    table = Table.read(path, format="ascii.ecsv")
    expected = [(s["name"], v) for s in result.values["sections"] for v in s["values"]]
    assert len(table) == len(expected) == written.rows
    assert table.colnames == ["section", "quantity", "value", "value_text", "unit", "error", "error_lower",
                              "error_upper", "interval_lower", "interval_upper", "interval_kind", "band", "system",
                              "upper_limit", "method", "formula", "service", "server", "table", "query", "identifier",
                              "match", "reference", "note", "retrieved_at", "from_cache", "command_id"]
    for row, (section, value) in zip(table, expected, strict=True):
        assert row["section"] == section and row["quantity"] == value["quantity"]
        assert row["value_text"] == text_of(value["value"])  # esattamente il valore del risultato
        prov = value["provenance"]
        assert row["server"] == prov["server"] and row["retrieved_at"] == prov["retrieved_at"]
        assert (row["query"] or None) == prov["query"] and (row["table"] or None) == prov["table"]
        assert row["command_id"] == number
        if isinstance(value["value"], dict) and isinstance(value["value"]["value"], float):
            unit = "" if np.ma.is_masked(row["unit"]) else row["unit"]  # stringa vuota → cella vuota nell'ECSV
            assert row["value"] == value["value"]["value"] and unit == value["value"]["unit"]
    source_id = table[table["quantity"] == "source_id"][0]
    assert source_id["value_text"] == "2635476908753563008" and np.ma.is_masked(source_id["value"])
    period = table[table["quantity"] == "TRAPPIST-1 b period"][0]
    assert (period["error_upper"], period["error_lower"]) == (6e-06, -6e-06) and period["unit"] == "d"
    assert period["reference"] == "2021PSJ.....2....1A"
    w4 = table[table["quantity"] == "AllWISE W4 flux_nu"][0]
    assert w4["upper_limit"] and w4["band"] == "W4" and w4["system"] == "Vega" and w4["method"] == "computed"
    assert not table[table["quantity"] == "AllWISE W1 flux_nu"][0]["upper_limit"]
    assert table.meta["A2KIND"] == "object_profile" and table.meta["commands"] == [number]
    assert table.meta["main_id"] == result.values["resolved"]["main_id"]
    # Bailer-Jones: intervallo 16°–84° percentile così come letto
    number2, peg = profile(session, {"name": "51 Peg", "sections": ["astrometry"]})
    rows = profile_values_table(merge_profile_results([(number2, values_of(peg))]))
    geo = rows[rows["quantity"] == "distance_geo"][0]
    assert (geo["value"], geo["interval_lower"], geo["interval_upper"]) == (15.514698, 15.494703, 15.533528)
    assert geo["interval_kind"] == "16th-84th percentile" and geo["reference"] == "2021AJ....161..147B"


@pytest.mark.parametrize("name", ["51 Peg", "Vega", "eta Tau", "TRAPPIST-1"])
def test_t15_ecsv_row_by_row_for_the_four_objects(cache, services, tmp_path, name):  # noqa: F811
    session = session_with_export(cache)
    number, result = profile(session, {"name": name})
    assert export(session, [number], "ecsv", tmp_path / "p.ecsv").status == "ok"
    table = Table.read(tmp_path / "p.ecsv", format="ascii.ecsv")
    expected = [(s["name"], v) for s in result.values["sections"] for v in s["values"]]
    assert len(table) == len(expected)
    for row, (section, value) in zip(table, expected, strict=True):
        shown = "" if np.ma.is_masked(row["value_text"]) else row["value_text"]  # valore assente: cella vuota
        assert (row["section"], row["quantity"], shown) == (section, value["quantity"],
                                                            "" if value["value"] is None else text_of(value["value"]))
        for key in ("error", "error_upper", "error_lower"):
            given = value.get(key)
            cell = row[key]
            assert (np.ma.is_masked(cell) if given is None else cell == given["value"]), (name, value["quantity"], key)
        prov = value["provenance"]
        assert (row["service"], row["server"]) == (prov["service"], prov["server"])
        assert (row["retrieved_at"], row["command_id"]) == (prov["retrieved_at"], number)


def test_t15_vizier_series_rows_as_given(cache, services, tmp_path):  # noqa: F811
    session = session_with_export(cache)
    number, result = profile(session, {"name": "51 Peg", "sections": ["photometry"]})
    data = merge_profile_results([(number, values_of(result))])
    photometry = data["sections"][0]
    photometry["details"]["vizier"] = {  # serie sintetica (il CDS era giù il 2026-11-07): così come data
        "rows": [{"frequency": {"value": 241.0, "unit": "GHz"}, "flux": {"value": 0.0123, "unit": "Jy"},
                  "flux_error": {"value": 0.0004, "unit": "Jy"}, "filter": "WISE:W4", "catalog": "II/328/allwise",
                  "wavelength": {"value": 1243.9, "unit": "micron"}}],
        "provenance": {"service": "VizieR (CDS)", "server": "https://vizier.cds.unistra.fr/viz-bin/sed",
                       "table": "VizieR SED", "retrieved_at": "2026-11-08T10:00:00+00:00", "from_cache": False}}
    table = profile_values_table(data)
    row = table[table["quantity"] == "VizieR SED WISE:W4 flux_nu"][0]
    assert (row["value"], row["error"], row["unit"]) == (0.0123, 0.0004, "Jy")
    assert row["table"] == "II/328/allwise" and row["server"].startswith("https://vizier")
    assert "241.0 GHz" in row["note"] and row["method"] == "read"
    sed = sed_catalog_table(data)
    vizier = sed.table[sed.table["series"] == "vizier"][0]
    assert (vizier["flux_nu"], vizier["wavelength"], vizier["catalog"]) == (0.0123, 1243.9, "II/328/allwise")


# =============================================================================
# T26 — PDF e PNG


def pdf_pages(content: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b(?!s)", content))


def test_t26_pdf_and_png(cache, services, tmp_path):  # noqa: F811
    from astrotwo.analysis import profile_export as pe

    session = session_with_export(cache)
    number, result = profile(session, {"name": "TRAPPIST-1"})
    data = merge_profile_results([(number, values_of(result))])
    pdf = export_profile(data, tmp_path / "t.pdf", "pdf", language="it")
    content = (tmp_path / "t.pdf").read_bytes()
    assert content.startswith(b"%PDF") and pdf.pages == 5 and pdf_pages(content) == 5
    assert b"/Title (Profilo di TRAPPIST-1)" in content and b"/CreationDate" not in content
    assert b"AstroTwo" in content
    again = export_profile(data, tmp_path / "t.pdf", "pdf", language="it")
    assert again.sha256 == pdf.sha256 == hashlib.sha256(content).hexdigest()  # Riesegui: stesso file (D25-20 (7))
    png = export_profile(data, tmp_path / "sed.png", "sed_png")
    import matplotlib.image as mpimg

    assert mpimg.imread(io.BytesIO((tmp_path / "sed.png").read_bytes()), format="png").shape[2] in (3, 4)
    assert export_profile(data, tmp_path / "sed.png", "sed_png").sha256 == png.sha256
    # il PNG esportato è il grafico del 20 dai punti del risultato, con la freccia del limite superiore (D43-9)
    from astrotwo.analysis.photometry import plot_sed_rows, sed_rows_png

    photometry = next(s for s in data["sections"] if s["name"] == "photometry")["details"]
    assert (tmp_path / "sed.png").read_bytes() == sed_rows_png(photometry["points"], photometry["vizier"],
                                                               title="TRAPPIST-1")
    figure = plot_sed_rows(photometry["points"], photometry["vizier"])
    arrow = [c for c in figure.axes[0].containers if c.get_label() == "AllWISE upper limit"]
    assert arrow and len(arrow[0].lines[1]) == 1  # una freccia (uplims) per W4
    # pagina della Fotometria: grafico con il limite superiore come freccia, numeri del risultato tali e quali
    page = pe._photometry_page(data, pe._LABELS["en"], "x")
    texts = [t.get_text() for t in page.fig.texts]
    w4 = next(p for p in data["sections"][3]["details"]["points"] if p["label"] == "AllWISE W4")
    assert repr(w4["flux"]["value"]) + " Jy" in texts and "arrow (upper limit)" in " ".join(texts)
    # sezione in errore: la sua pagina dice lo stato e il messaggio
    broken = json.loads(json.dumps(data))
    astrometry = next(s for s in broken["sections"] if s["name"] == "astrometry")
    astrometry.update(status="error", values=[], errors=[{"code": "PROFILE_SECTION_TIMEOUT", "text": "nessuna "
                                                          "risposta entro 30 s", "params": {}}])
    page = pe._astrometry_page(broken, pe._LABELS["en"], "x")
    texts = " ".join(t.get_text() for t in page.fig.texts)
    assert "Status: error" in texts and "PROFILE_SECTION_TIMEOUT" in texts
    assert export_profile(broken, tmp_path / "broken.pdf", "pdf").pages == 5
    # miniature disegnate dal PNG del risultato, crediti del survey e testo di STScI per DSS
    page = pe._identity_page(data, pe._LABELS["en"], "x")
    texts = " ".join(t.get_text() for t in page.fig.texts)
    assert len(page.fig.axes) == 3 and "Digitized Sky Survey - STScI/NASA" in texts and "NAG W-2166" in texts
    thumb = next(s for s in data["sections"] if s["name"] == "images")["details"]["thumbnails"][0]
    shown = page.fig.axes[0].images[0].get_array()
    assert shown.shape[:2] == mpimg.imread(io.BytesIO(base64.b64decode(thumb["png"])), format="png").shape[:2]


def test_pdf_planets_not_checked_and_old_profiles(cache, services, tmp_path):  # noqa: F811
    """D25-23 e decisioni del 2026-11-10: nel PDF una sezione con ``checked`` falso dice «Status: not checked» e
    «Not checked»; un profilo registrato prima (senza ``checked``) cambia solo nella riga dei Pianeti."""
    from astrotwo.analysis import profile_export as pe

    session = session_with_export(cache)
    number, result = profile(session, {"name": "Vega"})
    data = merge_profile_results([(number, values_of(result))])
    planets = next(s for s in data["sections"] if s["name"] == "planets")
    assert planets["details"]["checked"] is True

    def texts(d, lang="en"):
        return [t.get_text() for t in pe._planets_page(d, pe._LABELS[lang], "x").fig.texts]

    assert "No planet in the archive" in texts(data) and not any("not checked" in t for t in texts(data))
    unchecked = json.loads(json.dumps(data))
    sec = next(s for s in unchecked["sections"] if s["name"] == "planets")
    sec.update(status="not_applicable", servers=[])
    sec["details"] = {"planets": [], "checked": False, "note": "not checked"}
    shown = texts(unchecked)
    assert "Not checked" in shown and any(t.startswith("Status: not checked") for t in shown)
    assert any(t.startswith("Stato: non controllata") for t in texts(unchecked, "it"))
    # profilo registrato prima del 2026-11-10 senza prova della richiesta: solo la riga dei Pianeti cambia
    old = json.loads(json.dumps(data))
    sec = next(s for s in old["sections"] if s["name"] == "planets")
    sec["details"] = {"planets": [], "note": "no planet in the archive (no host in the archive)"}
    for c in old.get("cross_identifications") or []:
        if c.get("catalog") == "exoplanet":
            c["queries"] = []
    for s in old["sections"]:
        for c in (s.get("details") or {}).get("cross_identifications") or []:
            if c.get("catalog") == "exoplanet":
                c["queries"] = []
    shown = texts(old)
    assert "Not checked" in shown and "No planet in the archive" not in shown
    assert any(t.startswith("Status: done") for t in shown)  # intestazione invariata per i profili vecchi


@pytest.mark.parametrize("umask", [0o022, 0o077])
def test_exported_files_follow_the_umask(cache, services, tmp_path, umask):  # noqa: F811
    """Decisione del proprietario del 2026-11-10: i file esportati hanno i permessi normali (0666 meno l'umask, di
    solito 0644), non 0600; nessun file temporaneo rimasto."""
    import os
    import stat

    session = session_with_export(cache)
    number, result = profile(session, {"name": "TRAPPIST-1"})
    data = merge_profile_results([(number, values_of(result))])
    out = tmp_path / "out"
    out.mkdir()
    previous = os.umask(umask)
    try:
        for name, fmt in (("p.ecsv", "ecsv"), ("p.pdf", "pdf"), ("s.png", "sed_png"), ("s.xml", "sed_votable")):
            export_profile(data, out / name, fmt)
            assert stat.S_IMODE((out / name).stat().st_mode) == 0o666 & ~umask, name
    finally:
        os.umask(previous)
    assert sorted(p.name for p in out.iterdir()) == ["p.ecsv", "p.pdf", "s.png", "s.xml"]


# =============================================================================
# T27 — comando object.export


def test_t27_export_command_merges_retried_sections_and_reruns_identically(cache, services, tmp_path):  # noqa: F811
    session = session_with_export(cache)
    base, _ = profile(session, {"name": "51 Peg"})
    retry, _ = profile(session, {"name": "51 Peg", "sections": ["astrometry"]})  # «Riprova questa sezione»
    path = tmp_path / "peg.ecsv"
    result = export(session, [base, retry], "ecsv", path)
    assert result.status == "ok", result.error
    entry = session.history.entries[-1]
    assert entry.command.name == "object.export" and entry.command_class == "application"
    assert result.values["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result.values["commands"] == [base, retry] and result.values["format"] == "ecsv"
    table = Table.read(path, format="ascii.ecsv")
    assert set(table[table["section"] == "astrometry"]["command_id"]) == {retry}
    assert set(table[table["section"] == "identity"]["command_id"]) == {base}
    # Riesegui (stesso comando registrato): stesso file, byte per byte
    first = path.read_bytes()
    again = session.run(entry.command)
    assert again.status == "ok" and path.read_bytes() == first
    # il comando application non si riesegue alla riapertura della sessione
    saved = tmp_path / "s.astrotwo.json"
    saved.write_text(json.dumps(session.to_json(app_version="0.0.0")), encoding="utf-8")
    reopened = Session.load(saved, session.registry)
    report = reopened.replay()
    assert any(name == "object.export" and why == "application" for _, name, why in report.not_replayed)


@pytest.mark.parametrize("case", ["missing", "not_profile", "no_profile", "relative", "extension", "folder",
                                  "directory", "no_sed"])
def test_t27_export_checks_write_nothing(cache, services, tmp_path, case):  # noqa: F811
    session = session_with_export(cache)
    number, _ = profile(session, {"name": "51 Peg", "sections": ["identity"]})
    path, fmt, commands, reason = tmp_path / "out.ecsv", "ecsv", [number], case
    if case == "missing":
        commands, reason = [number + 40], "command_missing"
    elif case == "not_profile":
        session.run(Command("layer.list", 1, {}, RequestedBy("menu")))
        commands = [session.history.entries[-1].number]
    elif case == "no_profile":
        profile(session, {"name": "No Such Object 98765"})  # NAME_NOT_FOUND registrato
        commands = [session.history.entries[-1].number]
    elif case == "relative":
        path, reason = "out.ecsv", "not_absolute"
    elif case == "extension":
        path = tmp_path / "out.csv"
    elif case == "folder":
        path, reason = tmp_path / "manca" / "out.ecsv", "folder_unwritable"
    elif case == "directory":
        path, reason = tmp_path / "cartella.ecsv", "is_directory"
        path.mkdir()
    else:
        path, fmt = tmp_path / "out.png", "sed_png"
    before = sorted(p.name for p in tmp_path.iterdir() if p.name != "cache")
    result = export(session, commands, fmt, path)
    assert result.status == "error" and result.error.code == "PROFILE_EXPORT_INVALID"
    assert result.error.params["reason"] == reason
    assert sorted(p.name for p in tmp_path.iterdir() if p.name != "cache") == before  # nessun file scritto, nessun temporaneo


def test_t27_write_error_leaves_no_partial_file(cache, services, tmp_path, monkeypatch):  # noqa: F811
    from astrotwo.analysis import profile_export as pe

    session = session_with_export(cache)
    number, result = profile(session, {"name": "51 Peg", "sections": ["identity"]})

    def broken(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(pe.Table, "write", broken)
    with pytest.raises(ProfileExportError) as info:
        export_profile(merge_profile_results([(number, values_of(result))]), tmp_path / "x.ecsv", "ecsv")
    assert info.value.code == "PROFILE_EXPORT_FAILED" and "No space left" in info.value.params["detail"]
    assert [p.name for p in tmp_path.iterdir() if p.name != "cache"] == []


# =============================================================================
# T28 — tabella dei punti della SED e livello catalogo


def test_t28_sed_points_table_and_catalog_layer(cache, services, tmp_path):  # noqa: F811
    session = session_with_export(cache)
    number, result = profile(session, {"name": "TRAPPIST-1", "sections": ["identity", "photometry"]})
    data = merge_profile_results([(number, values_of(result))])
    points = next(s for s in result.values["sections"] if s["name"] == "photometry")["details"]["points"]
    sed = sed_catalog_table(data)
    assert len(sed.table) == len(points) and sed.table_name == "SED TRAPPIST-1"
    assert sed.positions.frame == "icrs" and sed.positions.epoch == result.values["resolved"]["position"]["epoch"]
    assert str(sed.table["flux_nu"].unit) == "Jy" and str(sed.table["wavelength"].unit) == "um"
    assert sed.table["ra"].meta["ucd"] == "pos.eq.ra;meta.main" and sed.table["flux_nu"].meta["ucd"] == \
        "phot.flux.density"
    for row, point in zip(sed.table, points, strict=True):  # nessun valore ricalcolato
        assert (row["catalog"], row["band"]) == (point["catalog"], point["band"])
        if point["flux"]:
            assert row["flux_nu"] == point["flux"]["value"] and row["wavelength"] == point["wavelength"]["value"]
        else:
            assert np.ma.is_masked(row["flux_nu"])
        assert bool(row["upper_limit"]) == point["upper_limit"] and row["command_id"] == number
        assert row["ra"] == result.values["resolved"]["position"]["lon"]["value"]
    # «Carica i punti SED come catalogo»: object.export sed_votable, poi catalog.open_file (25 §3.15)
    path = sed_catalog_path(result.values["resolved"]["main_id"], number, tmp_path)
    assert path.name == f"TRAPPIST-1-sed-{number}.xml"
    written = export(session, [number], "sed_votable", path)
    assert written.status == "ok" and written.values["rows"] == len(points)
    opened = session.run(Command("catalog.open_file", 1, {"file": {"path": str(path)}}, RequestedBy("menu")))
    assert opened.status == "ok", opened.error
    layer = session.workspace.state.layer(opened.values["layer"])
    assert layer.kind == "catalog" and len(layer.data.table) == len(points)
    assert layer.data.positions.frame == "icrs" and layer.data.positions.lon == "ra"
    assert layer.data.body == "celestial"
    assert list(layer.data.table["flux_nu"].filled(np.nan)) == pytest.approx(
        list(sed.table["flux_nu"].filled(np.nan)), nan_ok=True, rel=0, abs=0)


#: Unità di testo del NASA Exoplanet Archive (attributo ``unit`` dei FIELD nella risposta registrata) → unità di
#: ``astropy.units``; dichiarate qui a mano, indipendenti dal codice del 25 (D05-6).
_ARCHIVE_UNITS = {"days": "d", "Earth Mass": "earthMass", "Earth Radius": "earthRad"}


def test_d05_6_planet_units_read_back_from_json_and_ecsv(cache, services, tmp_path):  # noqa: F811
    """D05-6 (decisione del proprietario del 2026-11-11): periodo, massa e raggio dei pianeti scritti col nome di
    astropy.units (``d``, ``earthMass``, ``earthRad``), mai in kg o m con un fattore; l'unità riletta dal JSON del
    risultato e dall'ECSV esportato, convertita nell'unità dell'archivio, dà esattamente il valore della fonte."""
    import astropy.units as u
    from astropy.io.votable import parse_single_table

    from astrotwo.core.commands import unit_from_json
    from tests.analysis.profile_fakes import DATA

    source = parse_single_table(DATA / "exoplanet-88bd9d6a3469.xml").to_table()  # risposta registrata di TRAPPIST-1
    session = session_with_export(cache)
    number, result = profile(session, {"name": "TRAPPIST-1"})
    data = merge_profile_results([(number, values_of(result))])
    path = tmp_path / "trappist.ecsv"
    export_profile(data, path, "ecsv")
    table = Table.read(path, format="ascii.ecsv")
    assert "sections" in result.values, result.error
    planets = next(s for s in json.loads(json.dumps(result.values))["sections"] if s["name"] == "planets")
    checked = 0
    for key, column, name in (("period", "pl_orbper", "d"), ("mass", "pl_bmasse", "earthMass"),
                              ("radius", "pl_rade", "earthRad")):
        archive_unit = u.Unit(_ARCHIVE_UNITS[str(source[column].unit)])
        for i, planet in enumerate(source["pl_name"]):
            if np.ma.is_masked(source[column][i]):
                continue
            quantity = f"{planet} {key}"
            value = next(v for v in planets["values"] if v["quantity"] == quantity)["value"]
            row = table[table["quantity"] == quantity][0]
            assert value["unit"] == row["unit"] == name  # mai «5.9721679e+24kg» o «6378100m»
            for number_, text in ((value["value"], value["unit"]), (row["value"], row["unit"])):
                back = number_ * unit_from_json(text)
                assert back.to_value(archive_unit) == float(source[column][i])
            checked += 1
    assert checked == 21  # 7 pianeti × periodo, massa e raggio
