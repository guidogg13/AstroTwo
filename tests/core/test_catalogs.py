"""Test del modulo 13 (``mdfiles/13-core-cataloghi.md`` §12).

File di prova generati nel test; gli attesi sono ricalcolati con
``astropy.io.votable``, ``astropy.io.ascii``, ``astropy.io.fits`` e ``numpy``.
"""

from __future__ import annotations

import astropy.units as u
import numpy as np
import pytest
from astropy.io import ascii as astropy_ascii
from astropy.io import fits
from astropy.io.votable import parse as parse_votable
from astropy.table import Table

from astrotwo.core.catalogs import (
    CatalogsError,
    TableLimits,
    confirm_position_columns,
    detect_table_format,
    list_tables,
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
