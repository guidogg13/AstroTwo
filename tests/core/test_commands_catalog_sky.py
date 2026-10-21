# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del 05 per lo sprint 4e del 41: stile iniziale dei cataloghi nel comando di caricamento, scheda della
sorgente di ``catalog.select``, tempi scritti in ISO 8601 con la scala (``time_text``, DC1). Senza Qt e senza rete.

Valori attesi ricalcolati nel test con ``astropy`` e con le funzioni del 13.
"""

import astropy.units as u
import numpy as np
import pytest
from astropy.time import Time

from astrotwo.core.catalogs import PlotRule, load_table, record_view, set_plot_rules
from astrotwo.core.commands import (
    CATALOG_COLORS,
    CATALOG_SHAPES,
    CATALOG_SIZE,
    Command,
    RequestedBy,
    Session,
    catalog_positions,
    default_registry,
    time_json,
    time_text,
)

ROWS = (("HD 23630", 56.8711, 24.1051, 19.3, -43.7), ("HD 23302", 56.2190, 24.1133, 20.9, -45.0),
        ("HD 23850", 57.2906, 24.0534, 17.7, -44.2))


def votable_text(rows=ROWS, *, epoch='epoch="J2016.0"', name_ucd="meta.id;meta.main"):
    """VOTable con COOSYS ICRS (epoca facoltativa), un identificativo con UCD e moto proprio in mas/yr."""
    data = "\n".join(f"<TR><TD>{n}</TD><TD>{ra!r}</TD><TD>{de!r}</TD><TD>{pa!r}</TD><TD>{pd!r}</TD></TR>"
                     for n, ra, de, pa, pd in rows)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE>
<COOSYS ID="sys" system="ICRS" {epoch}/>
<TABLE name="stars">
<FIELD name="Name" datatype="char" arraysize="*" ucd="{name_ucd}"/>
<FIELD name="RA_ICRS" datatype="double" unit="deg" ucd="pos.eq.ra;meta.main" ref="sys"/>
<FIELD name="DE_ICRS" datatype="double" unit="deg" ucd="pos.eq.dec;meta.main" ref="sys"/>
<FIELD name="pmRA" datatype="double" unit="mas/yr" ucd="pos.pm;pos.eq.ra"/>
<FIELD name="pmDE" datatype="double" unit="mas/yr" ucd="pos.pm;pos.eq.dec"/>
<DATA><TABLEDATA>
{data}
</TABLEDATA></DATA>
</TABLE>
</RESOURCE>
</VOTABLE>
"""


def write_catalog(path, rows=ROWS, **kw):
    path.write_text(votable_text(rows, **kw))
    return str(path)


def run(session, name, requested_by=RequestedBy("menu"), /, **params):
    return session.run(Command(name, 1, params, requested_by))


@pytest.fixture
def session(cache):
    return Session(default_registry(cache=cache))


def test_initial_style_in_opening_order_and_replayed(session, tmp_path):
    path = write_catalog(tmp_path / "c.xml")
    styles = []
    for _ in range(3):
        result = run(session, "catalog.open_file", file={"path": path})
        assert result.status == "ok"
        styles.append(result.values["style"])
    assert styles == [{"shape": CATALOG_SHAPES[k], "color": CATALOG_COLORS[k], "size": CATALOG_SIZE} for k in range(3)]
    assert CATALOG_COLORS == ("#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7")
    assert CATALOG_SHAPES == ("circle", "square", "diamond", "triangle", "cross", "plus") and CATALOG_SIZE == 8.0
    state = session.workspace.state
    for layer, style in zip(state.of_kind("catalog"), styles, strict=True):
        assert layer.style == style and layer.state_json()["style"] == style
        expected = set_plot_rules(layer.data, [PlotRule(**style)])  # stile per riga dal 13
        plot = layer.derived["plot_style"]
        assert list(plot.color) == list(expected.color) and list(plot.shape) == list(expected.shape)
        assert np.array_equal(plot.size, expected.size)
    # un livello tolto non libera il suo stile: il contatore va avanti come gli identificativi
    assert run(session, "layer.remove", layer="L2").status == "ok"
    assert run(session, "catalog.open_file", file={"path": path}).values["style"]["color"] == CATALOG_COLORS[3]
    # riesecuzione: stessi stili
    saved = tmp_path / "s.astrotwo.json"
    session.save(saved, app_version="0.1.0")
    reopened = Session.load(saved, default_registry(cache=session.registry.cache))
    assert reopened.replay().status == "ok"
    assert [x.style for x in reopened.workspace.state.of_kind("catalog")] == \
        [x.style for x in session.workspace.state.of_kind("catalog")]


def test_select_one_row_gives_source_card(session, tmp_path):
    path = write_catalog(tmp_path / "c.xml")
    run(session, "catalog.open_file", file={"path": path})
    result = run(session, "catalog.select", RequestedBy("mouse"), layer="L1", rows=[1])
    assert result.status == "ok"
    card = result.values["source"]
    assert card["row"] == 1 and card["name"] == {"column": "Name", "value": "HD 23302"}
    # posizione della tabella nel suo frame, con l'epoca del catalogo (COOSYS) come la dichiara il 13
    position = card["position"]
    assert position["frame"] == "icrs"
    assert position["lon"] == {"value": pytest.approx(ROWS[1][1], abs=1e-12), "unit": "deg"}
    assert position["lat"] == {"value": pytest.approx(ROWS[1][2], abs=1e-12), "unit": "deg"}
    assert time_text(position["epoch"]) == time_text(time_json(Time("J2016.0")))
    table = load_table(path)
    assert card["catalog"]["layer"] == "L1" and card["catalog"]["origin"] == table.origin
    assert [f["name"] for f in card["record"]] == [f["name"] for f in record_view(table, 1)]
    assert card["record"][0]["value"] == "HD 23302"
    # più righe: nessuna scheda; righe vuote: selezione tolta
    assert run(session, "catalog.select", layer="L1", rows=[0, 2]).values["source"] is None
    cleared = run(session, "catalog.select", layer="L1", rows=[])
    assert cleared.status == "ok" and cleared.values["selected"] == []
    assert session.workspace.state.layer("L1").selection == ()


def test_select_name_fallback_and_epoch_not_declared(session, tmp_path):
    path = write_catalog(tmp_path / "c.xml", epoch="", name_ucd="meta.id")
    run(session, "catalog.open_file", file={"path": path})
    card = run(session, "catalog.select", layer="L1", rows=[0]).values["source"]
    assert card["name"] == {"column": "Name", "value": "HD 23630"}  # prima colonna con meta.id
    assert card["position"]["epoch"] is None  # epoca non dichiarata: mai assunta
    path = write_catalog(tmp_path / "d.xml", name_ucd="meta.note")
    run(session, "catalog.open_file", file={"path": path})
    assert run(session, "catalog.select", layer="L2", rows=[0]).values["source"]["name"] == \
        {"column": None, "value": None}  # l'interfaccia scrive "riga N"


def test_catalog_positions_valid_rows(tmp_path):
    rows = ROWS + (("bad", 400.0, 24.0, 1.0, 1.0),)
    table = load_table(write_catalog(tmp_path / "c.xml", rows))
    coords, valid = catalog_positions(table)
    assert valid.tolist() == [True, True, True, False]  # longitudine fuori da [0°, 360°): non disegnata
    assert np.allclose(coords.lon.to_value(u.deg), [r[1] for r in ROWS], atol=1e-12)
    assert coords.epoch == Time("J2016.0") and coords.frame_name == "icrs"


def test_time_text_iso_with_scale_never_jd():
    t = Time(2448248.07569, format="jd", scale="utc")
    assert time_text(time_json(t)) == t.isot + " UTC"  # millesimi non nulli: restano
    assert time_text(time_json(Time("1990-12-22T13:49:00", scale="utc"))) == "1990-12-22T13:49:00 UTC"
    assert time_text(Time(55000.0, format="mjd", scale="tdb")) == "2009-06-18T00:00:00 TDB"
    assert time_text("J2000.0") == "J2000.0" and time_text(None) is None
    assert "JD" not in time_text(time_json(t))
