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
