# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del modulo 13 (``mdfiles/13-core-cataloghi.md`` §12).

File di prova generati nel test; gli attesi sono ricalcolati con
``astropy.io.votable``, ``astropy.io.ascii``, ``astropy.io.fits`` e ``numpy``.
"""

from __future__ import annotations

import dataclasses as _dataclasses
import io

import astropy.units as u
import numpy as np
import pytest
from astropy.io import ascii as astropy_ascii
from astropy.io import fits
from astropy.io.votable import parse as parse_votable
from astropy.table import Table

import astrotwo.core.vo_protocols as vo
from astrotwo.core.catalogs import (
    FIXED_COLLECTIONS,
    CatalogsError,
    TableLimits,
    confirm_position_columns,
    datalink_column,
    detect_table_format,
    list_tables,
    load_catalog,
    load_table,
    read_table,
    suggest_position_columns,
)

# =============================================================================
# P1 — Lettura da file locale, formati, colonne di posizione, limiti
# (T1, T8–T11, T21, T22, T24, T27)
# =============================================================================

VOTABLE = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE>
<COOSYS ID="sys" system="{system}" {equinox} epoch="J2016.0"/>
<TABLE name="stelle">
<FIELD name="RA" ucd="pos.eq.ra;meta.main" ref="sys" datatype="double" unit="deg"/>
<FIELD name="DE" ucd="pos.eq.dec;meta.main" ref="sys" datatype="double" unit="deg"/>
<FIELD name="Vmag" ucd="phot.mag;em.opt.V" datatype="float" unit="mag"/>
<FIELD name="pmRA" ucd="pos.pm;pos.eq.ra" datatype="double" unit="mas/yr"/>
<FIELD name="Note" datatype="char" arraysize="*" unit="---"/>
<DATA><TABLEDATA>
<TR><TD>10.5</TD><TD>-3.25</TD><TD>11.2</TD><TD>3.5</TD><TD>a</TD></TR>
<TR><TD>11.5</TD><TD>-4.25</TD><TD></TD><TD>-1.0</TD><TD>bb</TD></TR>
<TR><TD>12.5</TD><TD>-5.25</TD><TD>9.8</TD><TD>0.25</TD><TD>ccc</TD></TR>
</TABLEDATA></DATA>
</TABLE>
{second}
</RESOURCE>
</VOTABLE>
"""
SECOND = """<TABLE name="altra"><FIELD name="x" datatype="int"/>
<DATA><TABLEDATA><TR><TD>1</TD></TR><TR><TD>2</TD></TR></TABLEDATA></DATA></TABLE>"""


def write_votable(path, system="ICRS", equinox="", second=""):
    path.write_text(VOTABLE.format(system=system, equinox=equinox, second=second), encoding="utf-8")
    return path


def test_t1_votable(tmp_path):
    path = write_votable(tmp_path / "cat.xml")
    cat = read_table(path)
    expected = parse_votable(str(path)).get_first_table().to_table(use_names_over_ids=True)
    assert cat.format == "votable" and cat.colnames == expected.colnames and cat.rows == len(expected) == 3
    assert cat.table["RA"].unit == u.deg and cat.table["pmRA"].unit == u.mas / u.yr
    assert cat.table["RA"].meta["ucd"] == "pos.eq.ra;meta.main"
    assert np.array_equal(cat.table["RA"], expected["RA"])
    assert bool(cat.table["Vmag"].mask[1])  # cella vuota: valore mancante, mai inventato
    assert cat.origin == str(path.resolve()) and cat.retrieved_at.tzinfo is not None and cat.file_modified


def test_t8_ipac(tmp_path):
    t = Table({"ra": [10.0, 11.0], "flux": [1.5, 2.5]})
    t["ra"].unit = u.deg
    t["flux"].unit = u.Jy
    path = tmp_path / "tab.tbl"
    t.write(path, format="ascii.ipac")
    cat = read_table(path)
    expected = astropy_ascii.read(path, format="ipac")
    assert cat.format == "ipac" and cat.colnames == expected.colnames
    assert cat.table["flux"].unit == u.Jy and np.array_equal(cat.table["flux"], expected["flux"])


SEXTRACTOR = """#   1 NUMBER                 Running object number
#   2 X_IMAGE                Object position along x                         [pixel]
#   3 MAG_AUTO               Kron-like elliptical aperture magnitude         [mag]
         1    100.523   18.2340
         2    200.100   19.1000
"""


def test_t9_sextractor(tmp_path):
    path = tmp_path / "cat.dat"
    path.write_text(SEXTRACTOR)
    cat = read_table(path)
    expected = astropy_ascii.read(path, format="sextractor")
    assert cat.format == "sextractor" and cat.colnames == ["NUMBER", "X_IMAGE", "MAG_AUTO"]
    assert np.array_equal(cat.table["MAG_AUTO"], expected["MAG_AUTO"]) and cat.table["X_IMAGE"].unit == u.pix


def test_t10_bsv(tmp_path):
    path = tmp_path / "spazi.txt"
    path.write_text("id  x   y\n1  1.5  2.5\n2  3.5  4.5\n")
    cat = read_table(path)
    expected = astropy_ascii.read(path, format="basic", delimiter=" ")
    assert cat.format == "bsv" and cat.colnames == ["id", "x", "y"]
    assert np.array_equal(cat.table["y"], expected["y"])


def test_t11_recognized_from_content(tmp_path):
    vot = write_votable(tmp_path / "in_realta_votable.csv")
    assert detect_table_format(vot) == "votable"
    fits_path = tmp_path / "tabella.txt"
    Table({"a": [1, 2]}).write(fits_path, format="fits")
    assert detect_table_format(fits_path) == "fits" and read_table(fits_path).rows == 2
    for name, content, fmt in [("c", "a,b\n1,2\n3,4\n", "csv"), ("t", "a\tb\n1\t2\n", "tsv"),
                               ("s", "a b\n1 2\n", "bsv")]:
        path = tmp_path / name
        path.write_text(content)
        assert detect_table_format(path) == fmt
        assert read_table(path).colnames == ["a", "b"]
    ambiguous = tmp_path / "amb"
    ambiguous.write_text("a,b\tc\n1,2\t3\n")  # virgole e tabulazioni insieme
    with pytest.raises(CatalogsError) as info:
        read_table(ambiguous)
    assert info.value.code == "FORMAT_AMBIGUOUS"
    uneven = tmp_path / "uneven"
    uneven.write_text("a,b\n1,2,3\n")  # numero di virgole diverso
    with pytest.raises(CatalogsError) as info:
        detect_table_format(uneven)
    assert info.value.code == "FORMAT_AMBIGUOUS"
    declared = read_table(ambiguous, format="tsv")
    assert declared.format == "tsv" and "FORMAT_DECLARED" in dict(declared.warnings)


def test_t11_unsupported_and_unreadable(tmp_path):
    xml = tmp_path / "x.xml"
    xml.write_text("<?xml version='1.0'?><html><body/></html>")
    missing = tmp_path / "manca.csv"
    for path, code in [(xml, "FORMAT_UNSUPPORTED"), (missing, "TABLE_UNREADABLE")]:
        with pytest.raises(CatalogsError) as info:
            read_table(path)
        assert info.value.code == code
    image = tmp_path / "img.fits"
    fits.PrimaryHDU(np.zeros((3, 3))).writeto(image)
    with pytest.raises(CatalogsError) as info:
        read_table(image)
    assert info.value.code == "FORMAT_UNSUPPORTED"


def test_t21_limits_before_loading(tmp_path):
    csv = tmp_path / "righe.csv"
    csv.write_text("a,b\n" + "".join(f"{k},{k * 2}\n" for k in range(50)))
    fits_path = tmp_path / "righe.fits"
    Table({"a": np.arange(50.0), "b": np.arange(50.0)}).write(fits_path, format="fits")
    vot = write_votable(tmp_path / "cat.xml")
    for path in (csv, fits_path, vot):
        with pytest.raises(CatalogsError) as info:
            read_table(path, limits=TableLimits(max_rows=2))
        assert info.value.code == "TABLE_TOO_LARGE" and info.value.details["max_rows"] == 2
        with pytest.raises(CatalogsError) as info:
            read_table(path, limits=TableLimits(operation_bytes=100))
        assert info.value.code == "MEMORY_LIMIT_EXCEEDED" and info.value.details["limit_bytes"] == 100
    # FITS: stima dall'intestazione, 50 righe × 16 byte per riga.
    with pytest.raises(CatalogsError) as info:
        read_table(fits_path, limits=TableLimits(operation_bytes=799))
    assert info.value.details["needed_bytes"] == 800
    assert read_table(fits_path, limits=TableLimits(max_rows=50, operation_bytes=800)).rows == 50
    with pytest.raises(ValueError):
        TableLimits(max_rows=0)
    assert TableLimits() == TableLimits(1_000_000, 4_000_000_000)


def test_t22_positions_from_ucd_and_coosys(tmp_path):
    icrs = read_table(write_votable(tmp_path / "icrs.xml"))
    assert (icrs.positions.lon, icrs.positions.lat, icrs.positions.frame) == ("RA", "DE", "icrs")
    assert icrs.positions.epoch == "J2016.0" and icrs.positions.source == "ucd" and icrs.body == "celestial"
    fk5 = read_table(write_votable(tmp_path / "fk5.xml", system="eq_FK5", equinox='equinox="J2000"'))
    assert fk5.positions.frame == "fk5" and fk5.positions.equinox == "J2000"
    # Sistema senza corrispondenza univoca: colonne note, sistema sconosciuto, mai assunto.
    ecl = read_table(write_votable(tmp_path / "ecl.xml", system="ecl_FK5"))
    assert ecl.positions.frame is None and "FRAME_UNKNOWN" in dict(ecl.warnings) and ecl.body == "celestial"


def test_t22_name_suggestions_need_confirmation(tmp_path):
    path = tmp_path / "cat.csv"
    path.write_text("RAJ2000,DEJ2000,GLON,GLAT,mag\n10.5,-3.2,100.1,20.2,11.0\n11.5,-4.2,101.1,21.2,12.0\n")
    cat = read_table(path)
    codes = dict(cat.warnings)
    assert cat.positions is None and cat.body is None and "NO_COORD_COLUMNS" in codes and "BODY_UNKNOWN" in codes
    suggestions = suggest_position_columns(cat)
    assert [(s.lon, s.lat, s.frame_hint, s.kind) for s in suggestions] == [
        ("RAJ2000", "DEJ2000", None, "suggestion"), ("GLON", "GLAT", "galactic", "suggestion")]
    with pytest.raises(CatalogsError) as info:
        confirm_position_columns(cat, "RAJ2000", "DEJ2000", "fk5")  # colonne senza unità: non si assume
    assert info.value.code == "COORD_UNIT_MISSING"
    confirmed = confirm_position_columns(cat, "RAJ2000", "DEJ2000", "fk5", equinox="J2000", unit="deg")
    assert confirmed.positions.source == "confirmed" and confirmed.positions.frame == "fk5"
    assert confirmed.body == "celestial" and "NO_COORD_COLUMNS" not in dict(confirmed.warnings)
    assert "confermate dall'utente" in confirmed.history[-1] and confirmed.table["RAJ2000"].unit == u.deg
    assert cat.positions is None and cat.table["RAJ2000"].unit is None  # originale invariata
    for args, code in [(("RAJ2000", "mag", "fk5"), "COORD_UNIT_MISSING"), (("RAJ2000", "XX", "icrs"), "NO_COORD_COLUMNS"),
                       (("RAJ2000", "DEJ2000", "nessuno"), "FRAME_UNKNOWN")]:
        with pytest.raises(CatalogsError) as info:
            confirm_position_columns(cat, *args, unit="mag" if args[1] == "mag" else "deg")
        assert info.value.code == code


def test_t24_units(tmp_path):
    cat = read_table(write_votable(tmp_path / "cat.xml"))
    assert cat.table["Note"].unit is None and cat.table["Note"].meta["unit_unrecognized"] == "---"
    assert "UNIT_UNRECOGNIZED" in dict(cat.warnings)
    assert cat.table["Vmag"].unit == u.Unit("mag", format="vounit")
    described = {d["name"]: d for d in cat.describe_columns()}
    assert described["Note"]["unit_unrecognized"] == "---" and described["RA"]["ucd"] == "pos.eq.ra;meta.main"


def test_t27_multiple_tables(tmp_path):
    vot = write_votable(tmp_path / "due.xml", second=SECOND)
    with pytest.raises(CatalogsError) as info:
        read_table(vot)
    assert info.value.code == "TABLE_CHOICE_REQUIRED" and len(info.value.details["tables"]) == 2
    assert [(t.index, t.name, t.rows) for t in list_tables(vot)] == [(0, "stelle", 3), (1, "altra", 2)]
    second = read_table(vot, table=1)
    assert second.colnames == ["x"] and list(second.table["x"]) == [1, 2] and second.table_name == "altra"
    fits_path = tmp_path / "due.fits"
    fits.HDUList([fits.PrimaryHDU(), fits.BinTableHDU(Table({"a": [1, 2]}), name="A"),
                  fits.BinTableHDU(Table({"b": [3.0]}), name="B")]).writeto(fits_path)
    with pytest.raises(CatalogsError) as info:
        read_table(fits_path)
    assert info.value.code == "TABLE_CHOICE_REQUIRED"
    assert read_table(fits_path, table=2).colnames == ["b"]
    with pytest.raises(CatalogsError) as info:
        read_table(fits_path, table=5)
    assert info.value.code == "TABLE_CHOICE_REQUIRED"


# =============================================================================
# P3 — search e regole di disegno (T2, T17–T20)
# =============================================================================

import dataclasses
import re

from astropy.table import MaskedColumn

from astrotwo.core.catalogs import PlotRule, SizeScale, search, set_plot_rules


def search_table(tmp_path):
    t = Table()
    t["name"] = ["M31", "m33", "NGC 224  ", "Vega", "M*1", "alpha Cen"]
    t["mag"] = MaskedColumn([3.4, 5.7, np.nan, 0.03, -1.5, 9.0], mask=[False, False, False, False, False, True])
    t["flag"] = [True, False, True, False, True, False]
    t["B V"] = [0.1, -0.2, 0.3, -0.4, 0.5, -0.6]
    t["note"] = MaskedColumn(["a", "b", "c", "d", "e", "f"], mask=[False, False, False, False, False, True])
    path = tmp_path / "s.csv"
    path.write_text("x,y\n1,2\n")
    # Tabella costruita in memoria: maschere dei testi esatte (il VOTable non le conserva per i testi vuoti).
    return dataclasses.replace(read_table(path), table=t)


def expected_text(values, mask, regex, flags=re.IGNORECASE):
    return np.array([(not m) and re.fullmatch(regex, str(v).rstrip(" "), flags) is not None
                     for v, m in zip(values, mask, strict=True)])


def test_t17_numeric_and_text_comparisons(tmp_path):
    cat = search_table(tmp_path)
    mag = np.asarray(cat.table["mag"].data, dtype=float)
    valid = ~np.asarray(cat.table["mag"].mask) & np.isfinite(mag)
    assert np.array_equal(search(cat, "mag < 4"), valid & (mag < 4))
    assert np.array_equal(search(cat, "mag>=0.03"), valid & (mag >= 0.03))
    assert np.array_equal(search(cat, "|mag| > 1"), valid & (np.abs(mag) > 1))
    assert np.array_equal(search(cat, "mag != 3.4"), valid & (mag != 3.4))  # mancanti e NaN mai selezionati
    assert np.array_equal(search(cat, "${B V} < 0"), np.asarray(cat.table["B V"]) < 0)
    assert np.array_equal(search(cat, "flag = 1"), np.asarray(cat.table["flag"]))
    names = list(cat.table["name"])
    nomask = [False] * len(names)
    assert np.array_equal(search(cat, "name = M3?"), expected_text(names, nomask, r"M3."))
    assert np.array_equal(search(cat, "name = 'ngc *'"), expected_text(names, nomask, r"ngc .*"))  # spazi finali ignorati
    assert np.array_equal(search(cat, r"name = M\*1"), expected_text(names, nomask, r"M\*1"))
    assert np.array_equal(search(cat, "name != m*"), ~expected_text(names, nomask, r"m.*"))


def test_t17_logic_precedence_and_free_text(tmp_path):
    cat = search_table(tmp_path)
    a, b, c = search(cat, "mag < 4"), search(cat, "flag = 1"), search(cat, "name = Vega")
    assert np.array_equal(search(cat, "mag < 4 || flag = 1 && name = Vega"), a | (b & c))  # && prima di ||
    assert np.array_equal(search(cat, "(mag < 4 || flag = 1) && name = Vega"), (a | b) & c)
    # Testo da solo: almeno una colonna di testo corrisponde; i mancanti mai.
    names, notes = list(cat.table["name"]), list(cat.table["note"])
    expected = expected_text(names, [False] * 6, r"m.*") | expected_text(notes, list(cat.table["note"].mask), r"m.*")
    assert np.array_equal(search(cat, "m*"), expected)
    assert np.array_equal(search(cat, '"alpha cen"'), expected_text(names, [False] * 6, r"alpha cen"))


@pytest.mark.parametrize("expression,position", [
    ("", 0), ("mag <", 5), ("nessuna < 3", 0), ("mag < abc", 6), ("name < M3", 5), ("|name| = 3", 1),
    ("(mag < 3", 8), ("mag < 3 &", 8), ("mag < 3 ! 2", 8), ("'aperta", 0), ("${mag < 3", 0), ("mag < 3)", 7),
])
def test_t17_invalid_expressions(tmp_path, expression, position):
    cat = search_table(tmp_path)
    with pytest.raises(CatalogsError) as info:
        search(cat, expression)
    assert info.value.code == "EXPRESSION_INVALID" and info.value.details["position"] == position


def test_t18_case_sensitivity(tmp_path):
    cat = search_table(tmp_path)
    names = list(cat.table["name"])
    assert np.array_equal(search(cat, "name = m3*"), expected_text(names, [False] * 6, r"m3.*"))
    assert np.array_equal(search(cat, "name = m3*", case_sensitive=True),
                          expected_text(names, [False] * 6, r"m3.*", flags=0))
    assert search(cat, "name = m3*").sum() == 2 and search(cat, "name = m3*", case_sensitive=True).sum() == 1


def test_t19_prefixes_and_missing_values(tmp_path):
    cat = search_table(tmp_path)
    current = np.array([True, False, False, False, False, True])
    found = search(cat, "flag = 1")
    assert np.array_equal(search(cat, "+flag = 1", selection=current), current | found)
    assert np.array_equal(search(cat, " - flag = 1", selection=current), current & ~found)
    for kwargs in (dict(), dict(selection=[True, False])):
        with pytest.raises(CatalogsError) as info:
            search(cat, "+flag = 1", **kwargs)
        assert info.value.code == "EXPRESSION_INVALID"
    assert not search(cat, "mag < 100")[[2, 5]].any()  # NaN e mascherato
    assert not search(cat, "note != zzz")[5]


def test_t2_rules_do_not_change_records_and_t20_rules(tmp_path):
    cat = search_table(tmp_path)
    before = cat.table.copy()
    rules = [
        PlotRule(shape="circle", color="#ff0000", size=SizeScale("mag", vmin=0.0, vmax=6.0, size_min=12.0, size_max=2.0),
                 selection="flag = 1"),
        PlotRule(shape="cross", color="#00FF00", size=4.0, selection="mag < 4"),
    ]
    style = set_plot_rules(cat, rules)
    assert before.as_array().tobytes() == cat.table.as_array().tobytes()  # tabella invariata
    flag = np.asarray(cat.table["flag"])
    rule1 = search(cat, "mag < 4") & ~flag
    assert np.array_equal(style.rule, np.where(flag, 0, np.where(rule1, 1, -1)))  # prima regola che seleziona
    mag = np.asarray(cat.table["mag"].data, dtype=float)
    ok0 = flag & np.isfinite(mag) & ~np.asarray(cat.table["mag"].mask)
    expected = 12.0 + (np.clip(mag[ok0], 0, 6) - 0) / 6 * (2.0 - 12.0)  # intervallo invertito, estremi
    assert np.allclose(style.size[ok0], expected, rtol=0, atol=1e-12)
    assert style.missing_size == (1, 0) and np.isnan(style.size[2]) and not style.drawn[2]  # NaN: non disegnato
    assert style.counts == (int(ok0.sum()), int(rule1.sum())) and style.not_selected == int((style.rule < 0).sum())
    assert set(style.shape[style.drawn]) <= {"circle", "cross"} and style.color[3] == "#00FF00"
    bad = [PlotRule(shape="star", color="#ff0000", size=3.0), PlotRule(shape="dot", color="red", size=3.0),
           PlotRule(shape="dot", color="#ff0000", size=-1.0),
           PlotRule(shape="dot", color="#ff0000", size=SizeScale("mag", 5.0, 1.0, 2.0, 4.0)),
           PlotRule(shape="dot", color="#ff0000", size=SizeScale("name", 0.0, 1.0, 2.0, 4.0)),
           PlotRule(shape="dot", color="#ff0000", size=3.0, selection="+mag < 3")]
    for rule in bad:
        with pytest.raises(CatalogsError) as info:
            set_plot_rules(cat, [rule])
        assert info.value.code == "PLOT_RULE_INVALID", rule
    with pytest.raises(CatalogsError) as info:
        set_plot_rules(cat, [PlotRule(shape="dot", color="#ff0000", size=3.0, selection="mag <")])
    assert info.value.code == "EXPRESSION_INVALID"


# =============================================================================
# P4 — sottoinsiemi, salvataggio, statistiche, istogramma, x-y, vista a record,
# tabella delle funzioni (T5, T6, T25, T26, T29 per skydist)
# =============================================================================

from astropy.coordinates import angular_separation

from astrotwo.core.catalogs import (
    CONSTANTS,
    FUNCTIONS,
    column_statistics,
    histogram,
    record_view,
    save_subset,
    skydist,
    subset,
    xy_plot,
)


def test_t5_histogram(tmp_path):
    cat = search_table(tmp_path)
    mag = np.asarray(cat.table["mag"].data, dtype=float)
    valid = ~np.asarray(cat.table["mag"].mask) & np.isfinite(mag)
    h = histogram(cat, "mag", bins=[-2.0, 0.0, 2.0, 6.0])
    expected, edges = np.histogram(mag[valid], bins=[-2.0, 0.0, 2.0, 6.0])
    assert np.array_equal(h.counts, expected) and np.array_equal(h.edges, edges) and h.excluded == 2
    assert np.array_equal(histogram(cat, "mag", bins=3).counts, np.histogram(mag[valid], bins=3)[0])
    for bins in (None, 0, -2, [1.0], [2.0, 1.0], 2.5, True):
        with pytest.raises(CatalogsError) as info:
            histogram(cat, "mag", bins=bins)
        assert info.value.code == "COLUMN_TYPE_UNSUPPORTED", bins


def test_t26_column_statistics(tmp_path):
    cat = search_table(tmp_path)
    mag = np.asarray(cat.table["mag"].data, dtype=float)
    good = mag[~np.asarray(cat.table["mag"].mask) & np.isfinite(mag)]
    stats = column_statistics(cat, "mag")
    assert (stats.minimum, stats.maximum) == (good.min(), good.max())
    assert stats.mean == good.mean() and stats.std == good.std() and stats.ddof == 0
    assert (stats.valid, stats.missing) == (4, 2)
    with pytest.raises(CatalogsError) as info:
        column_statistics(cat, "name")
    assert info.value.code == "COLUMN_TYPE_UNSUPPORTED"


def test_t25_subset_new_or_inplace(tmp_path):
    cat = search_table(tmp_path)
    mask = search(cat, "flag = 1")
    new = subset(cat, mask)
    assert len(new.table) == mask.sum() and len(cat.table) == 6  # originale invariata
    assert "sottoinsieme: 3 record su 6" in new.history[-1] and "INPLACE" not in dict(new.warnings)
    same = subset(cat, mask, inplace=True)
    assert same is cat and len(cat.table) == 3
    assert "inplace=True" in cat.history[-1] and "INPLACE" in dict(cat.warnings)
    with pytest.raises(CatalogsError):
        subset(cat, [True])


def test_t6_saved_subset_roundtrip(tmp_path):
    cat = read_table(write_votable(tmp_path / "cat.xml", system="eq_FK5", equinox='equinox="J2000"'))
    mask = np.array([True, False, True])
    path = save_subset(cat, mask, tmp_path / "scelta.xml")
    back = read_table(path)
    assert back.rows == 2 and np.array_equal(back.table["RA"], cat.table["RA"][mask])
    assert bool(back.table["Vmag"].mask[0]) is False and back.table["RA"].unit == u.deg
    assert (back.positions.lon, back.positions.lat, back.positions.frame, back.positions.equinox) == (
        "RA", "DE", "fk5", "J2000")
    infos = {i.name: i.value for i in parse_votable(str(path)).iter_info()}
    assert infos["A2ORIGIN"] == cat.origin and infos["A2SELECTED"] == "2 record su 3" and "A2SAVED" in infos
    with pytest.raises(CatalogsError) as info:
        save_subset(cat, mask, path)  # mai sovrascritto senza richiesta
    assert info.value.code == "FILE_EXISTS"
    assert save_subset(cat, mask, path, overwrite=True) == path


def test_xy_plot_and_record_view(tmp_path):
    cat = search_table(tmp_path)
    xy = xy_plot(cat, "mag", "B V")
    mag = np.asarray(cat.table["mag"].data, dtype=float)
    assert np.array_equal(xy.valid, ~np.asarray(cat.table["mag"].mask) & np.isfinite(mag))
    record = {r["name"]: r for r in record_view(cat, 5)}
    assert record["mag"]["missing"] and record["mag"]["value"] is None and record["name"]["value"] == "alpha Cen"
    with pytest.raises(CatalogsError):
        record_view(cat, 6)


def test_t29_skydist_and_function_table():
    ra1, dec1 = np.array([10.0, 200.0, 0.0]), np.array([20.0, -30.0, 89.9])
    expected = angular_separation(ra1 * u.deg, dec1 * u.deg, 10.0 * u.deg, 20.0 * u.deg).to_value(u.deg)
    assert np.array_equal(skydist(ra1, dec1, 10.0, 20.0), expected)
    assert FUNCTIONS["skydist"] == (4, skydist)
    x = np.array([0.25, 0.5])
    assert np.array_equal(FUNCTIONS["sind"][1](x * 360), np.sin(np.deg2rad(x * 360)))
    assert np.array_equal(FUNCTIONS["atan2d"][1](1.0, -1.0), np.rad2deg(np.arctan2(1.0, -1.0)))
    assert np.array_equal(FUNCTIONS["max"][1](x, 0.3, x[::-1]), np.maximum(np.maximum(x, 0.3), x[::-1]))
    assert FUNCTIONS["log"][1](100.0) == 2.0 and FUNCTIONS["dist"][1](0, 0, 3, 4) == 5.0
    assert CONSTANTS == {"pi": np.pi, "e": np.e}


# =============================================================================
# P5 — propagazione e frecce del moto proprio (T3, T7, T23)
# =============================================================================

import warnings

from astropy.coordinates import Distance, SkyCoord
from astropy.time import Time

from astrotwo.core.catalogs import propagate, proper_motion_arrows


def motion_table(tmp_path, n=100, seed=3, with_epoch_column=False):
    rng = np.random.default_rng(seed)
    t = Table()
    t["RA"] = rng.uniform(0, 359, n) * u.deg
    t["DE"] = rng.uniform(-80, 80, n) * u.deg
    t["pmRA"] = rng.normal(0, 200, n) * u.mas / u.yr  # include cos δ
    t["pmDE"] = rng.normal(0, 200, n) * u.mas / u.yr
    t["plx"] = rng.uniform(1, 50, n) * u.mas
    t["RA"].meta["ucd"] = "pos.eq.ra;meta.main"
    t["DE"].meta["ucd"] = "pos.eq.dec;meta.main"
    if with_epoch_column:
        t["ep"] = np.full(n, 2016.0) * u.yr
        t["ep"].meta["ucd"] = "meta.ref;time.epoch"
    path = tmp_path / "cat.csv"
    path.write_text("x,y\n1,2\n")
    cat = dataclasses.replace(read_table(path), table=t)
    return confirm_position_columns(cat, "RA", "DE", "icrs")


def expected_positions(t, rows, target, epoch, with_parallax=True):
    kwargs = dict(ra=t["RA"][rows], dec=t["DE"][rows], pm_ra_cosdec=t["pmRA"][rows], pm_dec=t["pmDE"][rows],
                  obstime=epoch, frame="icrs")
    if with_parallax:
        kwargs["distance"] = Distance(parallax=t["plx"][rows])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return SkyCoord(**kwargs).apply_space_motion(new_obstime=target)


def test_t3_propagation_matches_astropy(tmp_path):
    cat = motion_table(tmp_path)
    target = Time(2026.0, format="jyear", scale="tt")
    result = propagate(cat, target, pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True, parallax="plx",
                       source_epoch=2016.0)
    t = cat.table
    expected = expected_positions(t, slice(None), target, Time(2016.0, format="jyear", scale="tt"))
    got = SkyCoord(result.table.table["RA_prop"], result.table.table["DE_prop"], frame="icrs")
    assert np.max(got.separation(expected).deg) < 1e-9
    assert result.counts == {"full": 100, "pm_only": 0, "missing": 0}
    assert set(result.table.table["RA_prop_mode"]) == {"full"} and "parametro source_epoch" in result.source_epoch
    assert np.array_equal(result.table.table["RA"], t["RA"]) and "RA_prop" not in t.colnames  # originali intatte
    with pytest.raises(CatalogsError) as info:
        propagate(result.table, target, pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True, source_epoch=2016.0)
    assert info.value.code == "COLUMN_NAME_EXISTS"


def test_t3_epoch_from_metadata_and_cosdec(tmp_path):
    cat = motion_table(tmp_path, n=5, with_epoch_column=True)
    target = Time(2030.0, format="jyear", scale="tt")
    result = propagate(cat, target, pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True, parallax="plx")
    assert "time.epoch" in result.source_epoch
    with pytest.raises(CatalogsError) as info:  # epoca nei metadati e parametro: nessuna scelta silenziosa
        propagate(cat, target, pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True, source_epoch=2000.0)
    assert info.value.code == "EPOCH_INVALID"
    plain = motion_table(tmp_path, n=5)
    for kwargs in (dict(pm_ra_includes_cosdec=True), dict(pm_ra_includes_cosdec=None, source_epoch=2016.0)):
        with pytest.raises(CatalogsError) as info:
            propagate(plain, target, pm_ra="pmRA", pm_dec="pmDE", **kwargs)
        assert info.value.code in ("EPOCH_INVALID", "PROPER_MOTION_MISSING")
    # Moto proprio in RA senza cos δ: moltiplicato per cos δ, dichiarato.
    t = plain.table.copy()
    t["pmRA"] = t["pmRA"] / np.cos(np.deg2rad(np.asarray(t["DE"])))
    no_cos = dataclasses.replace(plain, table=t)
    a = propagate(no_cos, target, pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=False, source_epoch=2016.0)
    b = propagate(plain, target, pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True, source_epoch=2016.0)
    assert np.allclose(a.table.table["RA_prop"], b.table.table["RA_prop"], rtol=0, atol=1e-12)
    assert any("cos δ" in n for n in a.notes)


def test_t7_proper_motion_columns_missing(tmp_path):
    cat = motion_table(tmp_path, n=3)
    with pytest.raises(CatalogsError) as info:
        propagate(cat, 2030.0, pm_ra="nessuna", pm_dec="pmDE", pm_ra_includes_cosdec=True, source_epoch=2016.0)
    assert info.value.code == "PROPER_MOTION_MISSING"


def test_t23_missing_parallax_and_proper_motion(tmp_path):
    cat = motion_table(tmp_path, n=6)
    t = cat.table
    t["plx"] = MaskedColumn(t["plx"].value, mask=[False, True, False, False, False, False], unit=u.mas)
    t["plx"][2] = -1.5  # parallasse negativa
    t["pmDE"] = MaskedColumn(t["pmDE"].value, mask=[False, False, False, True, False, False], unit=u.mas / u.yr)
    t["pmRA"][4] = np.nan  # moto proprio non finito
    target = Time(2026.0, format="jyear", scale="tt")
    epoch = Time(2016.0, format="jyear", scale="tt")
    result = propagate(cat, target, pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True, parallax="plx",
                       source_epoch=2016.0)
    out = result.table.table
    assert list(out["RA_prop_mode"]) == ["full", "pm_only", "pm_only", "missing", "missing", "full"]
    assert result.counts == {"full": 2, "pm_only": 2, "missing": 2} and len(out) == 6  # nessuna riga esclusa
    assert list(out["RA_prop"].mask) == [False, False, False, True, True, False]
    pm_only = expected_positions(t, [1, 2], target, epoch, with_parallax=False)
    got = SkyCoord(out["RA_prop"][[1, 2]], out["DE_prop"][[1, 2]], frame="icrs")
    assert np.max(got.separation(pm_only).deg) < 1e-12
    assert "PROPER_MOTION_ROW_MISSING" in dict(result.table.warnings)
    assert any("solo moto proprio" in n for n in result.notes)
    assert bool(t["pmDE"].mask[3]) and np.isnan(t["pmRA"][4])  # colonne originali intatte


def test_t34_display_positions(tmp_path):
    """D10-2 in un passo: epoca dell'immagine se nota, altrimenti J2000; spostamento ricalcolato con astropy."""
    from types import SimpleNamespace

    from astropy.coordinates import angular_separation

    from astrotwo.core.catalogs import display_positions
    from astrotwo.core.coordinates_wcs import wcs_from_header

    cat = motion_table(tmp_path, n=6)
    t = cat.table
    t["plx"] = MaskedColumn(t["plx"].value, mask=[False, True, False, False, False, False], unit=u.mas)
    t["pmDE"] = MaskedColumn(t["pmDE"].value, mask=[False, False, False, True, False, False], unit=u.mas / u.yr)
    kwargs = dict(pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True, parallax="plx", source_epoch=2016.0)
    header = fits.Header({"CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN", "CRVAL1": 10.0, "CRVAL2": 20.0, "CRPIX1": 5.0,
                          "CRPIX2": 5.0, "CDELT1": -0.01, "CDELT2": 0.01, "RADESYS": "ICRS", "MJD-OBS": 47877.5})
    solution = wcs_from_header(header)
    image = SimpleNamespace(wcs=solution)  # un'immagine si riconosce dal suo attributo wcs (nessuna dipendenza dall'11)
    shown = display_positions(cat, image, **kwargs)
    assert shown.epoch.mjd == pytest.approx(47877.5) and shown.epoch.scale == "utc"
    assert "epoca dell'immagine" in shown.epoch_source
    reference = propagate(cat, Time(47877.5, format="mjd", scale="utc"), **kwargs).table.table
    drawable = np.array([True, True, True, False, True, True])
    assert np.array_equal(shown.drawable, drawable) and list(shown.mode) == list(reference["RA_prop_mode"])
    assert shown.counts == {"full": 4, "pm_only": 1, "missing": 1}
    assert np.array_equal(shown.lon[drawable], np.asarray(reference["RA_prop"])[drawable])
    assert np.isnan(shown.lon[3]) and np.isnan(shown.shift[3].value)
    expected = angular_separation(t["RA"].quantity[drawable], t["DE"].quantity[drawable],
                                  np.asarray(reference["RA_prop"])[drawable] * u.deg,
                                  np.asarray(reference["DE_prop"])[drawable] * u.deg).to(u.arcsec)
    assert np.allclose(shown.shift[drawable].value, expected.value, rtol=0, atol=1e-9)
    assert shown.shift_mean.value == pytest.approx(np.mean(expected.value), rel=1e-12)
    assert shown.shift_max.value == pytest.approx(np.max(expected.value), rel=1e-12)
    assert np.allclose(shown.coords.lon.to_value(u.deg), shown.lon[drawable], rtol=0, atol=1e-12)
    assert shown.coords.epoch == shown.epoch and "RA_prop" in shown.table.table.colnames
    assert display_positions(cat, solution, **kwargs).epoch == shown.epoch  # anche il WCS del 10 da solo
    # Senza epoca dell'immagine, senza WCS o senza immagine: J2000 (TT), fonte dichiarata.
    no_epoch = wcs_from_header(fits.Header({k: v for k, v in header.items() if k != "MJD-OBS"}))
    for given, words in ((no_epoch, "non dichiarata"), (SimpleNamespace(wcs=None), "senza WCS"),
                         (None, "nessuna immagine")):
        out = display_positions(cat, given, **kwargs)
        assert out.epoch == Time("J2000.0", scale="tt") and out.epoch.scale == "tt"
        assert "J2000" in out.epoch_source and words in out.epoch_source
    user = display_positions(cat, Time(2030.0, format="jyear", scale="tt"), **kwargs)
    assert user.epoch_source == "indicata dall'utente" and user.epoch.jyear == pytest.approx(2030.0)
    for bad in (True, [2030.0], object()):
        with pytest.raises(CatalogsError) as info:
            display_positions(cat, bad, **kwargs)
        assert info.value.code == "EPOCH_INVALID"


def test_proper_motion_arrows(tmp_path):
    cat = motion_table(tmp_path, n=4)
    arrows = proper_motion_arrows(cat, 1000 * u.yr, pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True,
                                  source_epoch=2016.0)
    epoch = Time(2016.0, format="jyear", scale="tt")
    expected = expected_positions(cat.table, slice(None), epoch + 1000 * u.yr, epoch, with_parallax=False)
    got = SkyCoord(arrows.lon_end * u.deg, arrows.lat_end * u.deg, frame="icrs")
    assert np.max(got.separation(expected).deg) < 1e-12 and set(arrows.mode) == {"pm_only"}
    assert np.array_equal(arrows.lon_start, np.asarray(cat.table["RA"]))
    for scale in (None, 1000, 0 * u.yr, 3 * u.m):
        with pytest.raises(CatalogsError) as info:
            proper_motion_arrows(cat, scale, pm_ra="pmRA", pm_dec="pmDE", pm_ra_includes_cosdec=True,
                                 source_epoch=2016.0)
        assert info.value.code == "EPOCH_INVALID"


# =============================================================================
# P2 — ASTRORES: file nostri scritti dalla DTD pubblica del CDS (T15, T16, T28);
# l'esempio pubblico del CDS si legge solo in un test di rete, senza copiarlo.
# =============================================================================

ASTRORES = """<?xml version="1.0"?>
<!DOCTYPE ASTRO SYSTEM "astrores.dtd">
<ASTRO ID="prova">
 <DEFINITIONS>
  <COOSYS ID="eq" system="eq_FK5" equinox="2000." epoch="2000."/>
 </DEFINITIONS>
 <RESOURCE ID="r1">
  <TABLE ID="t1">
   <NAME>stelle</NAME>
   <FIELD ID="ra" ref="{ref}" ucd="pos.eq.ra;meta.main" unit="deg" datatype="F" width="11">
     <NAME>RA</NAME><DESCRIPTION>Ascensione retta</DESCRIPTION></FIELD>
   <FIELD ID="de" ref="{ref}" ucd="pos.eq.dec;meta.main" unit="deg" datatype="F"><NAME>DE</NAME></FIELD>
   <FIELD ID="mag" unit="mag" datatype="F"><NAME>Vmag</NAME></FIELD>
   <FIELD ID="n" datatype="I"><NAME>N</NAME></FIELD>
   <FIELD ID="ok" datatype="L"><NAME>OK</NAME></FIELD>
   <FIELD ID="id" datatype="A"><NAME>Id</NAME></FIELD>
   <DATA><CSV colsep="|" headlines="2"><![CDATA[
RA|DE|Vmag|N|OK|Id
deg|deg|mag|-|-|-
{row1}
{row2}
]]></CSV></DATA>
  </TABLE>
  <TABLE ID="t2">
   <FIELD name="x" datatype="D"/><FIELD name="y" datatype="A"/>
   <DATA><TABLEDATA headlines="1"><ROW><CELL>x</CELL><CELL>y</CELL></ROW>
   <ROW><CELL>1.5</CELL><CELL>uno</CELL></ROW><ROW><CELL></CELL><CELL>due</CELL></ROW></TABLEDATA></DATA>
  </TABLE>
 </RESOURCE>
</ASTRO>
"""
ROW_DECIMAL = ("10.5|-3.25|11.2|7|T|a", "11.5|-4.25||8|F|bb")
ROW_SEXAGESIMAL = ("00 13 00.93|+72 31 19.9|11.2|7|T|a", "12:30:15.5|-05:06:07||8|false|bb")


def write_astrores(path, rows=ROW_DECIMAL, ref="eq"):
    path.write_text(ASTRORES.format(row1=rows[0], row2=rows[1], ref=ref), encoding="utf-8")
    return path


def test_t15_astrores_from_dtd(tmp_path):
    path = write_astrores(tmp_path / "in_realta_astrores.txt")
    assert detect_table_format(path) == "astrores"
    assert [(t.index, t.name, t.rows, t.columns) for t in list_tables(path)] == [(0, "stelle", 2, 6), (1, "t2", 2, 2)]
    with pytest.raises(CatalogsError) as info:
        read_table(path)
    assert info.value.code == "TABLE_CHOICE_REQUIRED"
    cat = read_table(path, table=0)
    t = cat.table
    assert cat.format == "astrores" and t.colnames == ["RA", "DE", "Vmag", "N", "OK", "Id"]
    assert np.array_equal(t["RA"], [10.5, 11.5]) and t["RA"].unit == u.deg and t["RA"].dtype == np.float64
    assert list(t["Vmag"].mask) == [False, True] and t["Vmag"][0] == 11.2
    assert list(t["N"]) == [7, 8] and t["N"].dtype == np.int64 and list(t["OK"]) == [True, False]
    assert list(t["Id"]) == ["a", "bb"] and t["RA"].description == "Ascensione retta"
    # Equinozio ed epoca scritti come numeri: giuliani per FK5 (dichiarato nel lettore).
    assert (cat.positions.lon, cat.positions.frame, cat.positions.equinox, cat.positions.epoch) == (
        "RA", "fk5", "J2000", "J2000") and cat.body == "celestial"
    second = read_table(path, table=1)
    assert list(second.table["y"]) == ["uno", "due"] and list(second.table["x"].mask) == [False, True]


def test_t15_astrores_link_and_errors(tmp_path):
    linked = tmp_path / "link.xml"
    linked.write_text('<?xml version="1.0"?><ASTRO><RESOURCE><TABLE><FIELD name="a" datatype="F"/>'
                      '<DATA><LINK href="http://esempio.invalid/dati.csv"/></DATA></TABLE></RESOURCE></ASTRO>')
    wrong = tmp_path / "righe.xml"
    wrong.write_text('<?xml version="1.0"?><ASTRO><RESOURCE><TABLE><FIELD name="a"/><FIELD name="b"/>'
                     '<DATA><CSV>1\t2\n3</CSV></DATA></TABLE></RESOURCE></ASTRO>')
    for path in (linked, wrong):
        with pytest.raises(CatalogsError) as info:
            read_table(path)
        assert info.value.code == "ASTRORES_UNREADABLE"
    tabs = tmp_path / "tab.xml"  # colsep di default: tabulazione
    tabs.write_text('<?xml version="1.0"?><ASTRO><RESOURCE><TABLE><FIELD name="a" datatype="I"/><FIELD name="b"/>'
                    '<DATA><CSV>1\tuno\n2\tdue</CSV></DATA></TABLE></RESOURCE></ASTRO>')
    assert list(read_table(tabs).table["b"]) == ["uno", "due"]


def test_t16_astrores_entity_expansion(tmp_path):
    path = tmp_path / "bomba.xml"
    path.write_text('<?xml version="1.0"?><!DOCTYPE ASTRO [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
                    '<ASTRO><RESOURCE><TABLE><FIELD name="x"/><DATA><CSV>&b;</CSV></DATA></TABLE></RESOURCE></ASTRO>')
    with pytest.raises(CatalogsError) as info:
        read_table(path)
    assert info.value.code == "XML_UNSAFE"


def test_t28_astrores_sexagesimal_and_nonconforming_ref(tmp_path):
    from astropy.coordinates import Angle

    cat = read_table(write_astrores(tmp_path / "sex.xml", rows=ROW_SEXAGESIMAL, ref="#id(eq)"), table=0)
    t = cat.table
    assert np.array_equal(t["RA"], Angle(["00 13 00.93", "12:30:15.5"], unit=u.hourangle).deg)
    assert np.array_equal(t["DE"], Angle(["+72 31 19.9", "-05:06:07"], unit=u.deg).deg)
    assert list(t["RA_text"]) == ["00 13 00.93", "12:30:15.5"] and t["RA"].unit == u.deg
    codes = [code for code, _ in cat.warnings]
    assert codes.count("ASTRORES_TYPE_MISMATCH") == 2 and "ASTRORES_NONCONFORMING_REF" in codes
    assert cat.positions.frame == "fk5"  # il riferimento #id(eq) è stato accettato
    assert list(t["OK"]) == [True, False]


@pytest.mark.network
def test_t15_public_astrores_example(tmp_path):
    # Esempio pubblico del CDS, scaricato nel test e mai copiato nel repository (D13-14 e).
    import requests

    response = requests.get("https://vizier.cds.unistra.fr/catstd/astrores.xml", timeout=(10, 60))
    response.raise_for_status()
    path = tmp_path / "astrores.xml"
    path.write_bytes(response.content)
    cat = read_table(path)
    codes = [code for code, _ in cat.warnings]
    assert cat.rows == 10 and "GSC-Id" in cat.colnames and "ASTRORES_NONCONFORMING_REF" in codes
    # D13-14b: POS_EQ_RA tradotto (raccomandazione IVOA); POS_EQ_DE non c'è nella raccomandazione → non tradotto.
    assert "UCD1_TRANSLATED" in codes and "UCD1_NOT_TRANSLATED" in codes and cat.positions is None
    assert cat.table["RA(J2000)"].meta["ucd"] == "pos.eq.ra" and cat.table["RA(J2000)"].unit == u.deg
    assert "ASTRORES_TYPE_MISMATCH" in codes  # RA/Dec sessagesimali in campi F


# =============================================================================
# D13-14b, D13-15, D13-16: UCD1, colonne calcolate (T4, T12–T14, T29), filtro
# temporale (T30)
# =============================================================================

from astropy.coordinates import Angle as _Angle

from astrotwo.core.catalogs import UCD1_TRANSLATIONS, calculated_column, time_filter


def test_t28_ucd1_translated_only_from_the_ivoa_recommendation(tmp_path):
    rows = ("00 13 00.93|+72 31 19.9|11.2|7|T|a", "12:30:15.5|-05:06:07||8|false|bb")
    text = ASTRORES.format(row1=rows[0], row2=rows[1], ref="eq")
    text = text.replace('ucd="pos.eq.ra;meta.main"', 'ucd="POS_EQ_RA_MAIN"').replace(
        'ucd="pos.eq.dec;meta.main"', 'ucd="POS_EQ_DEC_MAIN"').replace('<FIELD ID="mag" unit="mag"',
                                                                       '<FIELD ID="mag" ucd="PHOT_JHN_V" unit="mag"')
    path = tmp_path / "ucd1.xml"
    path.write_text(text)
    cat = read_table(path, table=0)
    codes = [c for c, _ in cat.warnings]
    assert cat.table["RA"].meta["ucd"] == "pos.eq.ra;meta.main" and cat.table["RA"].meta["ucd_original"] == "POS_EQ_RA_MAIN"
    assert cat.positions.lon == "RA" and cat.positions.lat == "DE" and cat.body == "celestial"
    assert np.array_equal(cat.table["RA"], _Angle(["00 13 00.93", "12:30:15.5"], unit=u.hourangle).deg)
    assert codes.count("UCD1_TRANSLATED") == 2 and "UCD1_NOT_TRANSLATED" in codes  # PHOT_JHN_V non tradotto
    assert cat.table["Vmag"].meta["ucd"] == "PHOT_JHN_V"
    assert set(UCD1_TRANSLATIONS) == {"POS_EQ_RA_MAIN", "POS_EQ_RA", "POS_EQ_DEC_MAIN", "POS_EQ_DEC"}


def calc_table(tmp_path):
    t = Table()
    t["mag"] = MaskedColumn([10.0, 11.0, 12.5], mask=[False, False, True], unit=u.mag)
    t["B"] = [1.20, 0.80, 1.50] * u.mag
    t["V"] = [0.70, 0.60, 1.10] * u.mag
    t["ra"] = [10.0, 200.0, 359.0] * u.deg
    t["dec"] = [20.0, -30.0, 5.0] * u.deg
    t["x"] = [2.0, 4.0, 8.0]
    t["note"] = ["a", "b", "c"]
    path = tmp_path / "c.csv"
    path.write_text("x,y\n1,2\n")
    return dataclasses.replace(read_table(path), table=t)


def test_t4_t12_calculated_columns(tmp_path):
    cat = calc_table(tmp_path)
    r = calculated_column(cat, "mag_corr", "${mag} - 0.12")
    col = r.table["mag_corr"]
    assert col.unit == u.mag and list(col.mask) == [False, False, True]  # mancante in ingresso → mancante
    assert np.array_equal(col.data[:2], np.asarray(cat.table["mag"].data[:2]) - 0.12)
    assert "mag_corr" not in cat.table.colnames  # originale invariata
    bv = calculated_column(cat, "B-V", "${B} - ${V}", ucd="phot.color;em.opt.B;em.opt.V", decimals=3)
    c = bv.table["B-V"]
    assert np.array_equal(c.data, np.asarray(cat.table["B"]) - np.asarray(cat.table["V"]))
    assert c.unit == u.mag and c.meta["ucd"] == "phot.color;em.opt.B;em.opt.V" and c.format == ".3f"
    assert c.meta["calculated"] and c.meta["expression"] == "${B} - ${V}" and "B-V" in bv.history[-1]


def test_d13_15_literals_units_and_functions(tmp_path):
    cat = calc_table(tmp_path)
    ra = np.asarray(cat.table["ra"])
    cases = {
        "${ra} % 15": (np.mod(ra, 15.0), u.deg),  # il numero prende l'unità della colonna
        "max(${ra}, 100)": (np.maximum(ra, 100.0), u.deg),
        "${ra} * 2": (ra * 2.0, u.deg),  # in * resta adimensionale
        "${ra} / 2 + 1": (ra / 2.0 + 1.0, u.deg),
        "${x} ^ 2 + pi": (np.asarray(cat.table["x"]) ** 2 + np.pi, None),
        "sin(${ra})": (np.sin(np.deg2rad(ra)), u.dimensionless_unscaled),
        "sind(${ra})": (np.sin(np.deg2rad(ra)), u.dimensionless_unscaled),  # su colonne angolari stesso risultato
        "sin(${x})": (np.sin(np.asarray(cat.table["x"])), None),  # numeri: sin in radianti
        "sind(${x})": (np.sin(np.deg2rad(np.asarray(cat.table["x"]))), None),  # sind in gradi
        "round(${x} / 4)": (np.round(np.asarray(cat.table["x"]) / 4), None),  # metà al pari (numpy)
    }
    for expression, (expected, unit) in cases.items():
        col = calculated_column(cat, "z", expression).table["z"]
        assert np.allclose(col.data, expected, rtol=0, atol=1e-12), expression
        assert (col.unit or None) == (unit if unit is not u.dimensionless_unscaled else col.unit), expression
    assert calculated_column(cat, "z", "round(${x} / 4)").table["z"][0] == 0.0  # 0.5 → 0
    assert calculated_column(cat, "z", "${ra}", unit="rad").table["z"].unit == u.rad


def test_t13_t14_invalid_expressions(tmp_path):
    cat = calc_table(tmp_path)
    for expression, position in [("${nessuna} + 1", 0), ("${mag} +", 8), ("__import__('os')", 0), ("${x} ** 2", 5),
                                 ("${x} < 2", 0), ("pippo(${x})", 0), ("dist(1, 2)", 0), ("${x} if 1 else 2", 0)]:
        with pytest.raises(CatalogsError) as info:
            calculated_column(cat, "z", expression)
        assert info.value.code == "COLUMN_EXPRESSION_INVALID", expression
        assert info.value.details["position"] == position, expression
    for expression in ("${ra} + ${mag}", "exp(${ra})", "${ra} + ${x}"):
        with pytest.raises(CatalogsError) as info:
            calculated_column(cat, "z", expression)
        assert info.value.code == "UNIT_INCOMPATIBLE", expression
    with pytest.raises(CatalogsError) as info:
        calculated_column(cat, "mag", "${x}")
    assert info.value.code == "COLUMN_NAME_EXISTS"
    with pytest.raises(CatalogsError) as info:
        calculated_column(cat, "z", "${note} + 1")
    assert info.value.code == "COLUMN_TYPE_UNSUPPORTED"


def test_t29_skydist_in_calculated_column_and_inplace(tmp_path):
    cat = calc_table(tmp_path)
    r = calculated_column(cat, "d", "skydist(${ra}, ${dec}, 10, 20)")
    expected = angular_separation(cat.table["ra"].quantity, cat.table["dec"].quantity, 10 * u.deg, 20 * u.deg)
    assert np.array_equal(r.table["d"].data, expected.to_value(u.deg)) and r.table["d"].unit == u.deg
    same = calculated_column(cat, "d", "${x} * 2", inplace=True)
    assert same is cat and "d" in cat.table.colnames and "inplace=True" in cat.history[-1]


TIMESYS_VOT = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3"><RESOURCE>
<TIMESYS ID="t" timeorigin="MJD-origin" timescale="TDB" refposition="BARYCENTER"/>
<TABLE><FIELD name="obs" ref="t" datatype="double" unit="d"/><FIELD name="iso" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>
<TR><TD>58000.0</TD><TD>2017-09-04T00:00:00</TD></TR>
<TR><TD>58010.0</TD><TD>2017-09-14T00:00:00</TD></TR>
<TR><TD></TD><TD>2017-09-24T00:00:00</TD></TR>
<TR><TD>58020.0</TD><TD>2017-09-24T00:00:00</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""


def test_t30_time_filter(tmp_path):
    path = tmp_path / "t.xml"
    path.write_text(TIMESYS_VOT)
    cat = read_table(path)
    start, end = Time(58000.0, format="mjd", scale="tdb"), Time(58010.0, format="mjd", scale="tdb")
    sel = time_filter(cat, start, end, column="obs")
    assert list(sel.mask) == [True, True, False, False]  # intervallo chiuso; mancante mai selezionato
    assert sel.source == "TIMESYS" and sel.scale == "tdb" and sel.excluded_missing == 1
    with pytest.raises(CatalogsError) as info:
        time_filter(cat, start, end, column="obs", scale="utc")  # già nel TIMESYS
    assert info.value.code == "EPOCH_INVALID"
    with pytest.raises(CatalogsError) as info:
        time_filter(cat, start, end, column="iso")  # nessun TIMESYS: formato e scala obbligatori
    assert info.value.code == "EPOCH_INVALID"
    iso = time_filter(cat, Time("2017-09-14T00:00:00", scale="utc"), Time("2017-09-24T00:00:00", scale="utc"),
                      column="iso", time_format="isot", scale="utc")
    assert list(iso.mask) == [False, True, True, True] and iso.source == "parametri"
    with pytest.raises(CatalogsError) as info:
        time_filter(cat, end, start, column="obs")
    assert info.value.code == "EPOCH_INVALID"


def test_votable_binary_without_nrows(tmp_path):
    # Senza l'attributo facoltativo nrows, con dati BINARY, astropy dà nrows = None: le righe si contano dai dati letti
    # (correzione del 2026-10-10, trovata con le risposte TAP del registro VO).
    text_path = write_votable(tmp_path / "cat.xml")
    vot = parse_votable(str(text_path))
    path = tmp_path / "binary.xml"
    vot.to_xml(str(path), tabledata_format="binary")
    text = path.read_text(encoding="utf-8")
    assert 'nrows="3"' in text
    path.write_text(text.replace(' nrows="3"', ""), encoding="utf-8")  # nrows è facoltativo nello standard
    expected = parse_votable(str(path)).get_first_table()
    assert expected.nrows is None
    cat = read_table(path, limits=TableLimits(max_rows=3))
    assert cat.rows == len(expected.array) == 3
    with pytest.raises(CatalogsError) as err:
        read_table(path, limits=TableLimits(max_rows=2))
    assert err.value.code == "TABLE_TOO_LARGE"


# =============================================================================
# P6 — Cataloghi da servizio e da URL, colonna DataLink (tramite il modulo 14)
# =============================================================================


def votable_route(text, status=200):
    return lambda request: (status, "application/x-votable+xml", text)


def test_load_table_from_url(service, cache, tmp_path):
    text = VOTABLE.format(system="ICRS", equinox="", second="")
    service.routes["/cat.xml"] = votable_route(text)
    cat = load_table(service.url + "/cat.xml", cache=cache)
    expected = parse_votable(io.BytesIO(text.encode())).get_first_table().to_table(use_names_over_ids=True)
    assert cat.colnames == expected.colnames and cat.rows == len(expected)
    assert cat.origin == service.url + "/cat.xml" and cat.request.protocol == "download" and not cat.request.from_cache
    assert cat.positions is not None and cat.body == "celestial"
    again = load_table(service.url + "/cat.xml", cache=cache)
    assert again.request.from_cache and any(code == "FROM_CACHE" for code, _ in again.warnings)
    local = load_table(write_votable(tmp_path / "loc.xml"))  # file locale: come read_table
    assert local.request is None and local.rows == 3


LINKED = """<?xml version="1.0"?>
<ASTRO>
 <DEFINITIONS><COOSYS ID="eq" system="ICRS"/></DEFINITIONS>
 <RESOURCE><TABLE>
  <FIELD ref="eq" ucd="pos.eq.ra;meta.main" unit="deg" datatype="F"><NAME>RA</NAME><DESCRIPTION>Ascensione retta</DESCRIPTION></FIELD>
  <FIELD ref="eq" ucd="pos.eq.dec;meta.main" unit="deg" datatype="F"><NAME>DE</NAME></FIELD>
  <FIELD unit="mag" datatype="F"><NAME>Vmag</NAME></FIELD>
  <FIELD datatype="A"><NAME>Id</NAME></FIELD>
  <DATA><LINK {link}/></DATA>
 </TABLE></RESOURCE>
</ASTRO>
"""
LINKED_ROWS = {"RA": [10.5, 11.5], "DE": [-3.25, -4.25], "Vmag": [11.2, 12.4], "Id": ["a", "bb"]}


def linked_payloads():
    """Gli stessi dati nei quattro formati ammessi per un LINK (D13-17), scritti con astropy nel test."""
    t = Table(LINKED_ROWS)
    out = {}
    for fmt, kw in (("csv", dict(format="csv")), ("tsv", dict(format="tab"))):
        buffer = io.StringIO()
        astropy_ascii.write(t, buffer, **kw)
        out[fmt] = buffer.getvalue().encode()
    buffer = io.BytesIO()
    t.write(buffer, format="votable")
    out["votable"] = buffer.getvalue()
    buffer = io.BytesIO()
    fits.HDUList([fits.PrimaryHDU(), fits.table_to_hdu(t)]).writeto(buffer)
    out["fits"] = buffer.getvalue()
    return out


def test_t15_astrores_link(service, cache, tmp_path):
    payloads = linked_payloads()
    types = {"csv": "text/csv", "tsv": "text/tab-separated-values", "votable": "application/x-votable+xml",
             "fits": "application/fits"}
    for fmt, ctype in types.items():
        service.routes[f"/dati.{fmt}"] = (lambda body: lambda r: (200, "application/octet-stream", body))(payloads[fmt])
        path = tmp_path / f"link_{fmt}.xml"
        path.write_text(LINKED.format(link=f'href="{service.url}/dati.{fmt}" content-type="{ctype}; charset=utf-8"'),
                        encoding="utf-8")
        with pytest.raises(CatalogsError) as info:  # read_table non usa la rete
            read_table(path)
        assert info.value.code == "ASTRORES_UNREADABLE" and "load_table" in info.value.message
        cat = load_table(path, cache=cache)
        t = cat.table
        assert t.colnames == list(LINKED_ROWS) and cat.format == "astrores"
        for name in ("RA", "DE", "Vmag"):
            assert np.allclose(np.asarray(t[name], dtype=float), LINKED_ROWS[name])
        assert [str(v) for v in t["Id"]] == LINKED_ROWS["Id"]
        assert t["RA"].unit == u.deg and t["Vmag"].unit == u.mag and t["RA"].description == "Ascensione retta"
        assert (cat.positions.lon, cat.positions.lat, cat.positions.frame) == ("RA", "DE", "icrs")
        assert cat.body == "celestial"
        codes = dict(cat.warnings)
        assert fmt in codes["ASTRORES_LINK"] and "dati collegati" in codes["ASTRORES_LINK_SOURCE"]
    # Documento scaricato da URL: href relativo risolto sull'URL del documento.
    service.routes["/doc.xml"] = lambda r: (200, "text/xml", LINKED.format(
        link='href="dati.csv" content-type="text/csv"'))
    remote = load_table(service.url + "/doc.xml", cache=cache)
    assert remote.rows == 2 and "dati.csv" in dict(remote.warnings)["ASTRORES_LINK"]


def test_t15_astrores_link_refused(service, cache, tmp_path):
    payloads = linked_payloads()
    service.routes["/dati.csv"] = lambda r: (200, "text/csv", payloads["csv"])
    service.routes["/dati.vot"] = lambda r: (200, "text/xml", payloads["votable"])
    url = service.url + "/dati.csv"
    cases = {
        "senza content-type": f'href="{url}"',
        "content-type sconosciuto": f'href="{url}" content-type="text/plain"',
        "xml generico": f'href="{service.url}/dati.vot" content-type="text/xml"',
        "csv senza intestazione": f'href="{url}" content-type="text/csv; header=absent"',
        "gref": 'gref="VizieR ${-source}" content-type="text/csv"',
        "action": 'action="http://esempio.invalid/q" content-type="text/csv"',
        "href relativo in un file locale": 'href="dati.csv" content-type="text/csv"',
        "formato dichiarato diverso": f'href="{url}" content-type="application/fits"',
    }
    for label, link in cases.items():
        path = tmp_path / "rifiuto.xml"
        path.write_text(LINKED.format(link=link), encoding="utf-8")
        with pytest.raises(CatalogsError) as info:
            load_table(path, cache=cache)
        assert info.value.code == "ASTRORES_UNREADABLE", label
    # FIELD e dati collegati diversi: nessuna scelta tra i due.
    other = Table({"RA": [1.0], "DE": [2.0], "Vmag": [3.0], "Nome": ["x"]})
    buffer = io.StringIO()
    astropy_ascii.write(other, buffer, format="csv")
    service.routes["/nomi.csv"] = lambda r: (200, "text/csv", buffer.getvalue())
    vot = io.BytesIO()
    units = Table(LINKED_ROWS)
    units["Vmag"].unit = u.Jy
    units.write(vot, format="votable")
    service.routes["/unita.xml"] = lambda r: (200, "text/xml", vot.getvalue())
    for href, ctype, word in ((service.url + "/nomi.csv", "text/csv", "colonne"),
                              (service.url + "/unita.xml", "application/x-votable+xml", "unità")):
        path = tmp_path / "diversi.xml"
        path.write_text(LINKED.format(link=f'href="{href}" content-type="{ctype}"'), encoding="utf-8")
        with pytest.raises(CatalogsError) as info:
            load_table(path, cache=cache)
        assert info.value.code == "ASTRORES_UNREADABLE" and word in info.value.message


def mocserver_route(records):
    """Come il MocServer reale: JSON in ISO-8859-1 dichiarato nel Content-Type (verificato il 2026-10-12)."""
    import json
    payload = json.dumps(records, ensure_ascii=False).encode("latin-1")
    return lambda request: (200, "application/json;charset=ISO-8859-1", payload)


def test_collection_tree_popularity(service, cache, monkeypatch):
    from astrotwo.core.catalogs import ALPHABETICAL_NOTE, POPULARITY_NOTE, collection_tree

    records = [
        {"ID": "CDS/II/246/out", "obs_title": "2MASS", "vizier_popularity": "320"},
        {"ID": "CDS/I/355/gaiadr3", "obs_title": "Gaia DR3", "vizier_popularity": "1000"},
        {"ID": "CDS/I/355/paramp", "obs_title": "Gaia DR3 paramp", "vizier_popularity": "1000"},
        {"ID": "CDS/I/239/hip_main", "obs_title": "Hipparcos", "vizier_popularity": "50"},
        {"ID": "CDS/I/10/x", "obs_title": "pari 50, numero più grande", "vizier_popularity": "50"},
        {"ID": "CDS/I/9/y", "obs_title": "pari 50, numero più piccolo", "vizier_popularity": "50"},
        {"ID": "CDS/I/100/a", "obs_title": "senza popolarità"},
        {"ID": "CDS/I/101/b", "obs_title": "anche lui"},
        {"ID": "CDS/Simbad", "obs_title": "SIMBAD"},
    ]
    service.routes["/moc"] = mocserver_route(records)
    monkeypatch.setattr(vo, "MOCSERVER_URL", service.url + "/moc")
    tree = collection_tree(cache=cache)
    params = service.requests[-1]["params"]
    assert params["fmt"] == "json" and "vizier_popularity" in params["fields"]
    assert tree.ordering == POPULARITY_NOTE and "non documentata" in tree.ordering
    assert [r.id for r in tree.roots] == ["I", "II"]  # 1000 prima di 320
    i = tree.find("I")
    assert i.popularity == 1000 and not i.table
    # Decrescente per popolarità, poi le collezioni senza la proprietà in ordine alfabetico.
    # A pari popolarità ordine naturale (I/9 prima di I/10 e di I/239).
    assert [c.id for c in i.children] == ["I/355", "I/9", "I/10", "I/239", "I/100", "I/101"]
    assert [c.id for c in tree.find("I/355").children] == ["I/355/gaiadr3", "I/355/paramp"]  # pari: alfabetico
    leaf = tree.find("II/246/out")
    assert leaf.table and leaf.title == "2MASS" and leaf.popularity == 320
    assert tree.find("I/10/x").title == "pari 50, numero più grande"  # testo ISO-8859-1 letto correttamente
    codes = dict(tree.warnings)
    assert "CDS/Simbad" in codes["COLLECTION_SKIPPED"] and "2 collezioni" in codes["POPULARITY_MISSING"]
    assert tree.request.protocol == "mocserver" and tree.find("Simbad") is None
    assert collection_tree(cache=cache).request.from_cache
    # Proprietà assente ovunque: ordine alfabetico dichiarato.
    service.routes["/moc"] = mocserver_route([{"ID": r["ID"], "obs_title": r["obs_title"]} for r in records])
    plain = collection_tree(cache=cache, refresh=True)
    assert plain.ordering == ALPHABETICAL_NOTE and [c.id for c in plain.find("I").children] == [
        "I/9", "I/10", "I/100", "I/101", "I/239", "I/355"]
    service.routes["/moc"] = lambda r: (200, "application/json", "non è json")
    with pytest.raises(vo.VoProtocolsError) as err:
        collection_tree(cache=cache, refresh=True)
    assert err.value.code == "SERVICE_ERROR"


@pytest.mark.network
def test_collection_tree_network(cache):
    from astrotwo.core.catalogs import POPULARITY_NOTE, collection_tree

    tree = collection_tree(cache=cache)
    assert tree.ordering == POPULARITY_NOTE
    assert tree.find("I/355/gaiadr3").table and tree.find("II/246/out").table
    pops = [r.popularity for r in tree.roots]
    assert pops == sorted(pops, reverse=True)


def test_load_catalog_vizier_tap(service, cache, monkeypatch):
    def tap(request):
        query = request["params"]["QUERY"]
        if '"II/246/out"' in query:
            maxrec = int(request["params"]["MAXREC"])
            text = VOTABLE.format(system="ICRS", equinox="", second="")
            if maxrec < 3:  # il servizio tronca e lo dichiara
                rows = text.split("<TR>")
                text = "<TR>".join(rows[:maxrec + 1]) + "</TABLEDATA></DATA>\n</TABLE>\n</RESOURCE>\n</VOTABLE>\n"
                text = text.replace("<RESOURCE>", '<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OVERFLOW"/>', 1)
            return 200, "application/x-votable+xml", text
        error = ('<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">'
                 '<RESOURCE type="results"><INFO name="QUERY_STATUS" value="ERROR">Unknown table</INFO>'
                 '</RESOURCE></VOTABLE>')
        return 400, "application/x-votable+xml", error

    service.routes["/viz/sync"] = tap
    entries = tuple(_dataclasses.replace(e, url=service.url + "/viz") if e.id == "cds-vizier-tap" else e
                    for e in vo.BUILTIN_SERVERS)
    monkeypatch.setattr(vo, "BUILTIN_SERVERS", entries)
    cat = load_catalog("II/246/out", cache=cache)
    assert service.requests[-1]["params"]["QUERY"] == 'SELECT * FROM "II/246/out"' and cat.rows == 3
    assert cat.request.protocol == "tap" and cat.history == ("catalogo II/246/out da cds-vizier-tap",)
    # Catalogo oltre max_rows senza regione: errore, oppure allow_partial=True dichiarato.
    with pytest.raises(CatalogsError) as err:
        load_catalog("II/246/out", max_rows=2, cache=cache)
    assert err.value.code == "REGION_REQUIRED" and "allow_partial" in err.value.message
    cut = load_catalog("II/246/out", max_rows=2, allow_partial=True, cache=cache)
    assert cut.rows == 2 and "ROW_LIMIT_EXCEEDED" in dict(cut.warnings) and "PARTIAL_CATALOG" in dict(cut.warnings)
    assert "allow_partial=True: prime 2 righe" in cut.history
    exact = load_catalog("II/246/out", max_rows=3, cache=cache)  # entro max_rows: nessun avviso
    assert exact.rows == 3 and "PARTIAL_CATALOG" not in dict(exact.warnings)
    with pytest.raises(CatalogsError) as err:
        load_catalog("XX/999/none", cache=cache)
    assert err.value.code == "CATALOG_UNKNOWN" and "Unknown table" in err.value.message
    with pytest.raises(CatalogsError) as err:
        load_catalog('I/239" OR 1=1', cache=cache)
    assert err.value.code == "CATALOG_UNKNOWN"
    assert [c.id for c in FIXED_COLLECTIONS] == ["simbad", "I/355/gaiadr3", "II/246/out"]


REGION_SCHEMA = """<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/><TABLE>
<FIELD name="column_name" datatype="char" arraysize="*"/><FIELD name="ucd" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>{rows}</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""
REGION_DATA = """<?xml version="1.0"?><VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="{status}"/>{coosys}<TABLE>
<FIELD name="RAJ2000" datatype="double" unit="deg" ucd="pos.eq.ra;meta.main" ref="c"/>
<FIELD name="DEJ2000" datatype="double" unit="deg" ucd="pos.eq.dec;meta.main" ref="c"/>
<DATA><TABLEDATA>{rows}</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""
FK5_COOSYS = '<COOSYS ID="c" system="FK5" equinox="2000.0"/>'


def region_tap(coosys=FK5_COOSYS, schema=('"RAJ2000"', "pos.eq.ra;meta.main", '"DEJ2000"', "pos.eq.dec;meta.main"),
               rows=3):
    def tap(request):
        query = request["params"]["QUERY"]
        if "TAP_SCHEMA.columns" in query:
            cells = "".join(f"<TR><TD>{schema[k]}</TD><TD>{schema[k + 1]}</TD></TR>" for k in range(0, len(schema), 2))
            return 200, "application/x-votable+xml", REGION_SCHEMA.format(rows=cells)
        maxrec = int(request["params"].get("MAXREC", 10 ** 6))
        n = 0 if "TOP 0" in query else rows
        body = "".join(f"<TR><TD>{10 + 0.001 * k}</TD><TD>{41 + 0.001 * k}</TD></TR>" for k in range(min(n, maxrec)))
        return 200, "application/x-votable+xml", REGION_DATA.format(
            coosys=coosys, rows=body, status="OVERFLOW" if n > maxrec else "OK")
    return tap


def test_t33_load_catalog_region(service, cache, monkeypatch):
    from astropy.coordinates import FK5, SkyCoord

    entries = tuple(_dataclasses.replace(e, url=service.url + "/viz") if e.id == "cds-vizier-tap" else e
                    for e in vo.BUILTIN_SERVERS)
    monkeypatch.setattr(vo, "BUILTIN_SERVERS", entries)
    service.routes["/viz/sync"] = region_tap()
    center = SkyCoord(10.0 * u.deg, 41.0 * u.deg)  # ICRS
    cat = load_catalog("II/246/out", region=(center, 30 * u.arcsec), cache=cache)
    queries = [r["params"]["QUERY"] for r in service.requests]
    assert "TAP_SCHEMA.columns" in queries[0] and "\"II/246/out\"" in queries[0]
    assert queries[1] == 'SELECT TOP 0 "RAJ2000", "DEJ2000" FROM "II/246/out"'
    # Centro convertito nel sistema delle colonne (FK5 J2000), ricalcolato nel test con astropy.
    fk5 = center.transform_to(FK5(equinox="J2000"))
    expected = (f"SELECT * FROM \"II/246/out\" WHERE 1 = CONTAINS(POINT('FK5', \"RAJ2000\", \"DEJ2000\"), "
                f"CIRCLE('FK5', {float(fk5.ra.deg)!r}, {float(fk5.dec.deg)!r}, {float((30 * u.arcsec).to_value(u.deg))!r}))")
    assert queries[2] == expected and cat.rows == 3
    assert (cat.positions.frame, cat.positions.equinox) == ("fk5", "J2000")  # equinozio "2000.0" letto giuliano
    region = dict(cat.warnings)["REGION"]
    assert "FK5 equinozio J2000" in region and "RAJ2000/DEJ2000" in region and region in cat.history
    # Oltre max_rows nella regione: errore, o allow_partial dichiarato.
    with pytest.raises(CatalogsError) as err:
        load_catalog("II/246/out", region=(center, 30 * u.arcsec), max_rows=2, cache=cache)
    assert err.value.code == "REGION_TOO_LARGE"
    part = load_catalog("II/246/out", region=(center, 30 * u.arcsec), max_rows=2, allow_partial=True, cache=cache)
    assert part.rows == 2 and "PARTIAL_CATALOG" in dict(part.warnings)
    # Senza regione e oltre max_rows: l'errore indica il parametro region.
    with pytest.raises(CatalogsError) as err:
        load_catalog("II/246/out", max_rows=2, cache=cache)
    assert err.value.code == "REGION_REQUIRED" and "region=(centro, raggio)" in err.value.message
    for bad in ((center, 30), (center, -1 * u.arcsec), (center, 181 * u.deg), (center, 1 * u.m)):
        with pytest.raises(CatalogsError) as err:
            load_catalog("II/246/out", region=bad, cache=cache)
        assert err.value.code == "REGION_INVALID"
    with pytest.raises(TypeError):
        load_catalog("II/246/out", region=(10.0, 30 * u.arcsec), cache=cache)


def test_load_catalog_region_metadata_missing(service, cache, monkeypatch):
    from astropy.coordinates import SkyCoord

    entries = tuple(_dataclasses.replace(e, url=service.url + "/viz") if e.id == "cds-vizier-tap" else e
                    for e in vo.BUILTIN_SERVERS)
    monkeypatch.setattr(vo, "BUILTIN_SERVERS", entries)
    center = SkyCoord(10.0 * u.deg, 41.0 * u.deg)
    service.routes["/viz/sync"] = region_tap(coosys="")  # nessun COOSYS: sistema mai assunto
    with pytest.raises(CatalogsError) as err:
        load_catalog("II/246/out", region=(center, 1 * u.arcmin), cache=cache, refresh=True)
    assert err.value.code == "FRAME_UNKNOWN"
    service.routes["/viz/sync"] = region_tap(schema=('"RA1"', "pos.eq.ra", '"RA2"', "pos.eq.ra",
                                                     '"DE"', "pos.eq.dec;meta.main"))
    with pytest.raises(CatalogsError) as err:  # due RA senza meta.main: nessuna scelta
        load_catalog("II/246/out", region=(center, 1 * u.arcmin), cache=cache, refresh=True)
    assert err.value.code == "NO_COORD_COLUMNS"


SIMBAD_DATA = """<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/><TABLE>
<FIELD name="ra" datatype="double" unit="deg" ucd="pos.eq.ra;meta.main" utype="mango:EpochPosition.longitude[{lon}]"/>
<FIELD name="dec" datatype="double" unit="deg" ucd="pos.eq.dec;meta.main" utype="mango:EpochPosition.latitude[{lat}]"/>
<DATA><TABLEDATA>{rows}</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""


def simbad_tap(lon="CS.spaceSys=ICRS CT.epoch=J2000", lat="CS.spaceSys=ICRS CT.epoch=J2000"):
    def tap(request):
        query = request["params"]["QUERY"]
        if "TAP_SCHEMA.columns" in query:
            cells = "<TR><TD>ra</TD><TD>pos.eq.ra;meta.main</TD></TR><TR><TD>dec</TD><TD>pos.eq.dec;meta.main</TD></TR>"
            return 200, "application/x-votable+xml", REGION_SCHEMA.format(rows=cells)
        rows = "" if "TOP 0" in query else "<TR><TD>10.0</TD><TD>41.0</TD></TR>"
        return 200, "application/x-votable+xml", SIMBAD_DATA.format(lon=lon, lat=lat, rows=rows)
    return tap


def test_load_catalog_region_simbad_mango(service, cache, monkeypatch):
    """D13-20: SIMBAD senza COOSYS, sistema ICRS J2000 dall'utype MANGO, dichiarato."""
    from astropy.coordinates import FK5, SkyCoord

    entries = tuple(_dataclasses.replace(e, url=service.url + "/simbad") if e.id == "cds-simbad-tap" else e
                    for e in vo.BUILTIN_SERVERS)
    monkeypatch.setattr(vo, "BUILTIN_SERVERS", entries)
    service.routes["/simbad/sync"] = simbad_tap()
    center = SkyCoord(150.0 * u.deg, 2.0 * u.deg, frame=FK5(equinox="J2000"))  # convertito in ICRS
    cat = load_catalog("simbad", region=(center, 1 * u.arcmin), cache=cache)
    icrs = center.icrs
    expected = (f"SELECT * FROM basic WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), "
                f"CIRCLE('ICRS', {float(icrs.ra.deg)!r}, {float(icrs.dec.deg)!r}, {float((1 * u.arcmin).to_value(u.deg))!r}))")
    assert service.requests[-1]["params"]["QUERY"] == expected
    assert (cat.positions.frame, cat.positions.epoch, cat.positions.system) == ("icrs", "J2000", "MANGO CS.spaceSys=ICRS")
    notes = dict(cat.warnings)
    assert "MANGO" in notes["POSITIONS_FROM_MANGO"] and "FRAME_UNKNOWN" not in notes
    assert "ICRS, epoca delle posizioni J2000" in notes["REGION"]
    # utype diversi sulle due colonne o sistema che richiede l'equinozio: nessuna scelta, FRAME_UNKNOWN.
    for lon, lat in (("CS.spaceSys=ICRS CT.epoch=J2000", "CS.spaceSys=GALACTIC CT.epoch=J2000"),
                     ("CS.spaceSys=FK5 CT.epoch=J2000", "CS.spaceSys=FK5 CT.epoch=J2000")):
        service.routes["/simbad/sync"] = simbad_tap(lon, lat)
        with pytest.raises(CatalogsError) as err:
            load_catalog("simbad", region=(center, 1 * u.arcmin), cache=cache, refresh=True)
        assert err.value.code == "FRAME_UNKNOWN"


@pytest.mark.network
def test_t33_load_catalog_region_network(cache):
    from astropy.coordinates import FK5, SkyCoord

    m31 = SkyCoord(10.6847 * u.deg, 41.2690 * u.deg)
    cat = load_catalog("II/246/out", region=(m31, 30 * u.arcsec), cache=cache)
    assert cat.rows > 0 and cat.positions.frame == "fk5" and cat.positions.equinox == "J2000"
    rows = SkyCoord(cat.table["RAJ2000"].quantity, cat.table["DEJ2000"].quantity, frame=FK5(equinox="J2000"))
    sep = rows.separation(m31.transform_to(FK5(equinox="J2000")))
    assert sep.max() <= 30 * u.arcsec + 1e-6 * u.arcsec  # tutte le righe nel cerchio (ricalcolo con astropy)
    # SIMBAD: sistema ICRS J2000 dall'utype MANGO (D13-20); righe nel cerchio, separazione ricalcolata.
    simbad = load_catalog("simbad", region=(m31, 30 * u.arcsec), cache=cache)
    assert simbad.rows > 0 and (simbad.positions.frame, simbad.positions.epoch) == ("icrs", "J2000")
    assert "POSITIONS_FROM_MANGO" in dict(simbad.warnings)
    sep = SkyCoord(simbad.table["ra"].quantity, simbad.table["dec"].quantity).separation(m31)
    assert sep.max() <= 30 * u.arcsec + 1e-6 * u.arcsec


DATALINK_RESULT = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results">
<TABLE>
<FIELD name="obs_publisher_did" ID="pubdid" datatype="char" arraysize="*" ucd="meta.ref.ivoid"/>
<FIELD name="access_url" datatype="char" arraysize="*" ucd="meta.ref.url"/>
<FIELD name="access_format" datatype="char" arraysize="*" ucd="meta.code.mime"/>
<DATA><TABLEDATA>
<TR><TD>ivo://x?1</TD><TD>http://x/dl?ID=1</TD><TD>application/x-votable+xml;content=datalink</TD></TR>
<TR><TD>ivo://x?2</TD><TD>http://x/2.fits</TD><TD>image/fits</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE>
{descriptor}
</VOTABLE>
"""
DESCRIPTOR = """<RESOURCE type="meta" utype="adhoc:service" ID="dl">
<PARAM name="standardID" datatype="char" arraysize="*" value="ivo://ivoa.net/std/DataLink#links-1.1"/>
<PARAM name="accessURL" datatype="char" arraysize="*" value="http://x/dl"/>
<GROUP name="inputParams"><PARAM name="ID" datatype="char" arraysize="*" value="" ref="pubdid"/></GROUP>
</RESOURCE>"""


def test_datalink_column(tmp_path):
    with_descriptor = tmp_path / "d.xml"
    with_descriptor.write_text(DATALINK_RESULT.format(descriptor=DESCRIPTOR), encoding="utf-8")
    found = datalink_column(load_table(with_descriptor))
    assert found.column == "obs_publisher_did" and found.source == "descriptor"
    assert found.descriptor.access_url == "http://x/dl"
    by_type = tmp_path / "t.xml"
    by_type.write_text(DATALINK_RESULT.format(descriptor=""), encoding="utf-8")
    found = datalink_column(load_table(by_type))
    assert found.column == "access_url" and found.source == "content_type" and found.format_column == "access_format"
    assert list(found.rows) == [True, False]
    assert datalink_column(read_table(write_votable(tmp_path / "plain.xml"))) is None


@pytest.mark.network
def test_load_catalog_network(cache):
    with pytest.raises(CatalogsError) as err:  # 2MASS ha molte più di 5 righe: il servizio lo dichiara
        load_catalog("II/246/out", max_rows=5, cache=cache)
    assert err.value.code == "REGION_REQUIRED"
    cat = load_catalog("II/246/out", max_rows=5, allow_partial=True, cache=cache)
    assert cat.rows == 5 and "PARTIAL_CATALOG" in dict(cat.warnings) and cat.request.from_cache is True


def test_coosys_refframe_terms(tmp_path):
    # Termini del vocabolario IVOA refframe nel COOSYS; equinozio numerico giuliano (FK5) o besseliano (FK4).
    for system, equinox, frame, expected in (("FK5", "2000.0", "fk5", "J2000"), ("FK4", "1950.0", "fk4", "B1950"),
                                              ("eq_FK5", "J2000", "fk5", "J2000"), ("ICRS", "", "icrs", None)):
        path = tmp_path / f"{system}.xml"
        attr = f' equinox="{equinox}"' if equinox else ""
        path.write_text(REGION_DATA.format(coosys=f'<COOSYS ID="c" system="{system}"{attr}/>', status="OK",
                                           rows="<TR><TD>1</TD><TD>2</TD></TR>"), encoding="utf-8")
        pos = read_table(path).positions
        assert (pos.frame, pos.equinox, pos.system) == (frame, expected, system)
    path = tmp_path / "gal.xml"
    path.write_text(REGION_DATA.format(coosys='<COOSYS ID="c" system="GALACTIC"/>', status="OK", rows="")
                    .replace("pos.eq.ra", "pos.galactic.lon").replace("pos.eq.dec", "pos.galactic.lat"), encoding="utf-8")
    assert read_table(path).positions.frame == "galactic"
