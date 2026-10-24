# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 13 con codice + ``params`` (D40-3, D40-7; ``40`` §3.7.1, T18–T19; ``13`` §10).

Provoca ogni errore e ogni avviso del modulo; ogni istanza è controllata contro il catalogo alla creazione
(``tests/conftest.py``) e qui si verifica la copertura di tutte le coppie (codice, ragione) del modulo, i messaggi
annidati, gli errori del 10 rilanciati e il testo italiano invariato.
"""

from __future__ import annotations

import dataclasses
import io
import json
from types import SimpleNamespace

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.io import ascii as astropy_ascii
from astropy.table import MaskedColumn, Table
from astropy.time import Time

from astrotwo import messages_catalog as mc
from astrotwo.core import catalogs as cats
from astrotwo.core import vo_protocols as vo
from astrotwo.core.catalogs import (
    CatalogRegion,
    CatalogsError,
    PlotRule,
    PositionColumns,
    SizeScale,
    TableLimits,
    calculated_column,
    collection_tree,
    column_statistics,
    histogram,
    record_view,
    confirm_position_columns,
    detect_table_format,
    display_positions,
    load_catalog,
    load_table,
    propagate,
    proper_motion_arrows,
    read_table,
    save_subset,
    search,
    set_plot_rules,
    subset,
    time_filter,
)
from astrotwo.core.coordinates_wcs import ModuleWarning, SkyFrame
from tests.core.test_catalogs import LINKED, LINKED_ROWS, linked_payloads, mocserver_route, write_astrores  # noqa: F401
from tests.message_helpers import MODULE_15_SUBVARIANTS, MODULE_16_SUBVARIANTS, MODULE_17_SUBVARIANTS, catalog_combinations, check_error, check_message, nested_pairs

#: Codici del 13 (le sotto-voci aggiunte a voci condivise con altri moduli sono in ``SHARED``).
OWN_CODES = (
    "TABLE_UNREADABLE", "FORMAT_AMBIGUOUS", "FORMAT_DECLARED", "UNIT_UNRECOGNIZED", "UNIT_DECLARED",
    "NO_COORD_COLUMNS", "POSITIONS_FROM_MANGO", "FRAME_UNKNOWN", "ECSV_POSITIONS_INVALID", "POSITIONS_FROM_ECSV",
    "EPOCH_FROM_METADATA", "TABLE_TOO_LARGE", "TABLE_CHOICE_REQUIRED", "COLUMN_TYPE_UNSUPPORTED",
    "PROPER_MOTION_MISSING", "UNIT_INCOMPATIBLE", "COLUMN_NAME_EXISTS", "EPOCH_INVALID", "EXPRESSION_INVALID",
    "COLUMN_EXPRESSION_INVALID", "PLOT_RULE_INVALID", "FILE_EXISTS", "INPLACE", "PROPER_MOTION_ROW_MISSING",
    "XML_UNSAFE", "ASTRORES_UNREADABLE", "ASTRORES_LINK_PROBLEM", "ASTRORES_LINK", "ASTRORES_TYPE_MISMATCH",
    "UCD1_TRANSLATED", "ASTRORES_NONCONFORMING_REF", "UCD1_NOT_TRANSLATED", "CATALOG_UNKNOWN", "REGION_REQUIRED",
    "REGION_TOO_LARGE", "REGION", "PARTIAL_CATALOG", "COLLECTION_SKIPPED", "POPULARITY_INVALID",
    "POPULARITY_MISSING",
)
SHARED = {("FORMAT_UNSUPPORTED", r) for r in ("url_via_vo", "format_not_text", "xml_root", "binary", "no_table")} | {
    ("MEMORY_LIMIT_EXCEEDED", r) for r in ("read_file", "loaded_table", "linked_data", "subset", "calculated_column")
} | {("REGION_INVALID", "radius_not_angle"), ("REGION_INVALID", "radius_range"), ("BODY_UNKNOWN", "table_body"),
     ("COORD_UNIT_MISSING", "column_unit_required"), ("COORD_UNIT_MISSING", "column_not_angular")}


def required_combinations() -> set[tuple[str, str | None]]:
    """Coppie (codice, ragione) del 13: ogni sotto-voce; la voce generale solo dove non ha sotto-voci."""
    out = {(c, r) for c, r in catalog_combinations(OWN_CODES) if r is not None or not mc.CATALOG[c].variants}
    module_14 = {("FORMAT_DECLARED", "recognized_differs"), ("TABLE_TOO_LARGE", "upload")}  # sotto-voci del 14
    return (out - module_14 - MODULE_15_SUBVARIANTS - MODULE_16_SUBVARIANTS
            - MODULE_17_SUBVARIANTS) | {("FORMAT_DECLARED", None), ("TABLE_TOO_LARGE", None)} | SHARED


class Seen:
    def __init__(self) -> None:
        self.pairs: set[tuple[str, str | None]] = set()

    def error(self, func, *args, **kwargs) -> CatalogsError:
        with pytest.raises(CatalogsError) as info:
            func(*args, **kwargs)
        self.pairs.add(check_error(info.value))
        self.pairs |= nested_pairs(info.value.code, info.value.params)
        return info.value

    def notes(self, items) -> None:
        for item in items:
            if isinstance(item, ModuleWarning):
                self.pairs.add(check_message(item[0], item.params, item[1]))
                self.pairs |= nested_pairs(item[0], item.params)


CSV = ("ra,dec,pmra,pmde,plx,name,flag,t\n"
       "10.0,20.0,5.0,-3.0,2.0,a,1,2000.0\n"
       "11.0,21.0,1.0,2.0,4.0,b,0,2001.0\n")


def base_table(tmp_path, *, units=True):
    """Tabella con posizioni confermate (ICRS), moti propri, parallasse e una colonna di testo."""
    path = tmp_path / "t.csv"
    path.write_text(CSV)
    cat = read_table(path)
    cat = confirm_position_columns(cat, "ra", "dec", "icrs", unit="deg")
    if units:
        cat.table["pmra"].unit = u.mas / u.yr
        cat.table["pmde"].unit = u.mas / u.yr
        cat.table["plx"].unit = u.mas
    return cat


def pm(**kwargs):
    return {"pm_ra": "pmra", "pm_dec": "pmde", "pm_ra_includes_cosdec": True, "source_epoch": 2000.0} | kwargs


def test_every_error_and_warning_has_code_params_and_catalog_entry(tmp_path, service, cache, monkeypatch):  # noqa: F811
    seen = Seen()
    cat = base_table(tmp_path)
    csv = tmp_path / "t.csv"

    # --- formati e lettura -------------------------------------------------------------------------------------------
    binary = tmp_path / "bin.dat"
    binary.write_bytes(b"\x00\x01\x02 abc")
    seen.error(detect_table_format, binary)
    seen.error(read_table, "http://esempio.invalid/t.csv")
    seen.error(read_table, csv, format="votable")
    other = tmp_path / "other.xml"
    other.write_text("<?xml version='1.0'?><ALTRO><x/></ALTRO>")
    seen.error(read_table, other)
    ambiguous = tmp_path / "amb.txt"
    ambiguous.write_text("a,b\nc d\n")
    seen.error(read_table, ambiguous)
    seen.error(read_table, tmp_path / "manca.csv")
    with monkeypatch.context() as patch:
        patch.setattr(cats.astropy_ascii, "read", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
        seen.error(read_table, csv)
    seen.error(read_table, csv, limits=TableLimits(max_rows=1))
    seen.error(read_table, csv, limits=TableLimits(operation_bytes=10))  # read_file
    with monkeypatch.context() as patch:
        patch.setattr(cats, "_table_bytes", lambda table: 10**12)
        seen.error(read_table, csv)  # loaded_table
    seen.notes(read_table(csv, format="csv").warnings)  # FORMAT_DECLARED, NO_COORD_COLUMNS not_found, BODY_UNKNOWN
    seen.notes(_unrecognized())
    two_tables = tmp_path / "due.xml"
    two_tables.write_text(
        '<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3"><RESOURCE>'
        '<TABLE name="a"><FIELD name="x" datatype="int"/><DATA><TABLEDATA><TR><TD>1</TD></TR></TABLEDATA></DATA></TABLE>'
        '<TABLE name="b"><FIELD name="y" datatype="int"/><DATA><TABLEDATA><TR><TD>2</TD></TR></TABLEDATA></DATA></TABLE>'
        "</RESOURCE></VOTABLE>")
    seen.error(read_table, two_tables)
    seen.error(read_table, two_tables, table=7)
    broken = tmp_path / "rotto.xml"
    broken.write_text('<VOTABLE version="1.4"><RESOURCE><TABLE><FIELD name="x" datatype="int"/>')
    seen.error(read_table, broken)
    empty_votable = tmp_path / "vuoto.xml"
    empty_votable.write_text('<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3"><RESOURCE/></VOTABLE>')
    seen.error(read_table, empty_votable)

    # --- colonne di posizione ---------------------------------------------------------------------------------------------
    seen.error(confirm_position_columns, cat, "nope", "dec", "icrs")
    seen.error(confirm_position_columns, cat, "name", "dec", "icrs", unit="deg")
    raw = read_table(csv)
    seen.error(confirm_position_columns, raw, "ra", "dec", "icrs")  # senza unità
    seen.error(confirm_position_columns, raw, "ra", "dec", "icrs", unit="m")
    seen.error(confirm_position_columns, raw, "ra", "dec", "boh", unit="deg")
    seen.notes(confirm_position_columns(read_table(csv), "ra", "dec", "icrs", unit="deg").warnings)  # UNIT_DECLARED
    pairs = Table({"a": [1.0], "b": [2.0], "c": [3.0], "d": [4.0]})
    for name, ucd in zip("abcd", ("pos.eq.ra", "pos.eq.dec", "pos.eq.ra", "pos.eq.dec")):
        pairs[name].meta["ucd"] = ucd
    seen.notes(cats._positions_from_ucd(pairs, {})[1])  # multiple_pairs
    undeclared = Table({"a": [1.0], "b": [2.0]})
    undeclared["a"].meta["ucd"] = "pos.eq.ra;meta.main"
    undeclared["b"].meta["ucd"] = "pos.eq.dec;meta.main"
    seen.notes(cats._positions_from_ucd(undeclared, {})[1])  # FRAME_UNKNOWN undeclared
    undeclared["a"].meta["ref"] = "sys"
    system = SimpleNamespace(system="boh", equinox=None, epoch=None)
    seen.notes(cats._positions_from_ucd(undeclared, {"sys": system})[1])  # ambiguous
    for column, utype in (("a", "mango:EpochPosition.longitude[CS.spaceSys=ICRS CT.epoch=J2016.0]"),
                          ("b", "mango:EpochPosition.latitude[CS.spaceSys=ICRS CT.epoch=J2016.0]")):
        undeclared[column].meta["utype"] = utype
        undeclared[column].meta.pop("ref", None)
    seen.notes(cats._positions_from_ucd(undeclared, {})[1])  # POSITIONS_FROM_MANGO con epoca
    for column, utype in (("a", "mango:EpochPosition.longitude[CS.spaceSys=ICRS]"),
                          ("b", "mango:EpochPosition.latitude[CS.spaceSys=ICRS]")):
        undeclared[column].meta["utype"] = utype
    seen.notes(cats._positions_from_ucd(undeclared, {})[1])  # senza epoca
    ecsv = Table({"lon": [1.0], "lat": [2.0]})
    ecsv.meta["A2POSITIONS"] = {"lon": "nope", "lat": "lat", "frame": "icrs"}
    seen.notes(cats._ecsv_positions(ecsv, None, [])[1])  # unusable
    ecsv.meta["A2POSITIONS"] = {"lon": "lon", "lat": "lat", "frame": "icrs"}
    seen.notes(cats._ecsv_positions(ecsv, PositionColumns("a", "b", "icrs"), [])[1])  # differs
    for meta in ({}, {"equinox": "J2000"}, {"epoch": "J2016.0"}, {"equinox": "J2000", "epoch": "J2016.0"}):
        ecsv.meta["A2POSITIONS"] = {"lon": "lon", "lat": "lat", "frame": "fk5", **meta}
        seen.notes(cats._ecsv_positions(ecsv, None, [])[1])
    epoch_kept = dataclasses.replace(cat, positions=PositionColumns("ra", "dec", "icrs", epoch="J2016.0", system="ICRS"))
    seen.notes(confirm_position_columns(epoch_kept, "ra", "dec", "icrs").warnings)  # EPOCH_FROM_METADATA
    # sistema non dichiarato / senza posizioni
    no_frame = dataclasses.replace(cat, positions=PositionColumns("ra", "dec", None))
    seen.error(propagate, no_frame, 2020.0, **pm())
    seen.error(propagate, dataclasses.replace(cat, positions=None), 2020.0, **pm())

    # --- epoca, moto proprio, grandezze con unità ------------------------------------------------------------------------
    seen.error(propagate, cat, 2020.0, **pm(pm_ra_includes_cosdec=None))
    seen.error(propagate, cat, 2020.0, **pm(pm_ra="nope"))
    seen.error(propagate, cat, 2020.0, **pm(parallax="nope"))
    seen.error(propagate, cat, 2020.0, **pm(parallax="name"))
    seen.error(propagate, cat, 2020.0, **pm(parallax="pmra"))  # unità
    seen.error(propagate, cat, None, **pm())  # target_required
    seen.error(propagate, cat, 2020.0, **pm(source_epoch=None))  # source_missing
    seen.error(propagate, dataclasses.replace(cat, positions=dataclasses.replace(cat.positions, epoch="J2016.0")),
               2020.0, **pm())  # source_in_metadata
    two = cat.table.copy()
    two["t"].meta["ucd"] = "time.epoch"
    two["t"].unit = u.yr
    two["t2"] = two["t"]
    two["t2"].meta["ucd"] = "time.epoch"
    seen.error(propagate, dataclasses.replace(cat, table=two), 2020.0, **pm(source_epoch=None))
    one = cat.table.copy()
    one["t"].meta["ucd"] = "time.epoch"
    seen.error(propagate, dataclasses.replace(cat, table=one), 2020.0, **pm(source_epoch=None))  # epoch_column_unit
    seen.error(propagate, cat, 2020.0, **pm(parallax="plx", source_epoch="boh"))  # relayed: errore del 10
    moved = propagate(cat, 2020.0, **pm())
    seen.error(propagate, moved.table, 2020.0, **pm())  # COLUMN_NAME_EXISTS propagation_columns
    seen.error(proper_motion_arrows, cat, 5, **pm())
    seen.error(display_positions, cat, object(), **pm())
    missing_pm = cat.table.copy()
    missing_pm["pmra"] = MaskedColumn([5.0, 1.0], mask=[True, False], unit=u.mas / u.yr)
    seen.notes(propagate(dataclasses.replace(cat, table=missing_pm), 2020.0, **pm()).table.warnings)

    # --- search -------------------------------------------------------------------------------------------------------------
    for expression in ("|=1", "(ra=1 x", "ra>", "=1", "(", "flag=1", "name>1", "|name|=1", "ra=a", "nope=1", "",
                       "ra=1 ^", "${ra", "'abc", "ra ! 1", "(ra=1"):
        try:
            search(cat, expression)
        except CatalogsError as exc:
            seen.pairs.add(check_error(exc))
    numeric_only = dataclasses.replace(cat, table=cat.table[["ra", "dec"]])
    seen.error(search, numeric_only, "abc")  # no_text_columns
    seen.error(search, cat, 5)
    seen.error(search, cat, "+ra=1")
    seen.error(search, cat, "+ra=1", selection=np.ones(5, dtype=bool))
    flag_bool = cat.table.copy()
    flag_bool["flag"] = np.array([1j, 2j])
    seen.error(search, dataclasses.replace(cat, table=flag_bool), "flag=1")  # not_comparable
    seen.error(set_plot_rules, cat, ["x"])
    seen.error(set_plot_rules, cat, [PlotRule(shape="boh", color="#000000", size=3)])
    seen.error(set_plot_rules, cat, [PlotRule(shape="circle", color="rosso", size=3)])
    seen.error(set_plot_rules, cat, [PlotRule(shape="circle", color="#000000", size=SizeScale("nope", 0, 1, 1, 2))])
    seen.error(set_plot_rules, cat, [PlotRule(shape="circle", color="#000000", size=SizeScale("ra", 1, 0, 1, 2))])
    seen.error(set_plot_rules, cat, [PlotRule(shape="circle", color="#000000", size=SizeScale("ra", 0, 1, -1, 2))])
    seen.error(set_plot_rules, cat, [PlotRule(shape="circle", color="#000000", size=-1)])
    seen.error(set_plot_rules, cat, [PlotRule(shape="circle", color="#000000", size=3, selection="+ra=1")])

    # --- sottoinsiemi, statistiche, colonne calcolate ----------------------------------------------------------------------
    seen.error(histogram, cat, "ra", None)
    seen.error(histogram, cat, "ra", 0)
    seen.error(histogram, cat, "ra", [1.0])
    seen.error(record_view, cat, 9)
    seen.error(column_statistics, cat, "nope")
    seen.error(column_statistics, cat, "name")
    seen.error(subset, cat, np.ones(5, dtype=bool))
    small = dataclasses.replace(cat, limits=TableLimits(operation_bytes=1))
    seen.error(subset, small, np.ones(2, dtype=bool))
    seen.error(calculated_column, small, "z", "${ra}*2")
    target = tmp_path / "out.xml"
    target.write_text("x")
    seen.error(save_subset, cat, np.ones(2, dtype=bool), target)
    seen.notes(subset(dataclasses.replace(cat, table=cat.table.copy()), np.ones(2, dtype=bool), inplace=True).warnings)
    seen.notes(calculated_column(dataclasses.replace(cat, table=cat.table.copy()), "z", "${flag}*2", inplace=True).warnings)
    seen.notes(calculated_column(dataclasses.replace(cat, table=cat.table.copy()), "z", "${pmra}*2", inplace=True).warnings)
    seen.error(calculated_column, cat, "", "${ra}")
    seen.error(calculated_column, cat, "ra", "${dec}")
    seen.error(calculated_column, cat, "z", "${ra}", decimals=-1)
    seen.error(calculated_column, cat, "z", "  ")
    for expression in ("${ra} ** 2", "${ra", "${nope}", "foo+1", "boh(${ra})", "sind(${ra}, ${dec})", "sind(*${ra})",
                       "${ra} <", "[1]", "lambda: 1"):
        try:
            calculated_column(cat, "z", expression)
        except CatalogsError as exc:
            seen.pairs.add(check_error(exc))
    seen.error(calculated_column, cat, "z", "${name}")
    seen.error(calculated_column, cat, "z", "${pmra}", unit="m")
    unknown_unit = cat.table.copy()
    unknown_unit["plx"].meta["unit_unrecognized"] = "banana"
    seen.error(calculated_column, dataclasses.replace(cat, table=unknown_unit), "z", "${plx}")

    # --- filtro temporale -------------------------------------------------------------------------------------------------------
    start, end = Time("2000-01-01"), Time("2001-01-01")
    seen.error(time_filter, cat, start, end, column="nope")
    seen.error(time_filter, cat, "x", end, column="t")
    seen.error(time_filter, cat, end, start, column="t")
    seen.error(time_filter, cat, start, end, column="t")  # format_scale_required
    seen.error(time_filter, cat, start, end, column="t", time_format="iso", scale="utc")  # values_unreadable
    for timesys, kwargs in (({"timescale": "TT", "timeorigin": None}, {"time_format": "jd"}),
                            ({"timescale": "XYZ"}, {}),
                            ({"timescale": "TT", "timeorigin": "abc"}, {}),
                            ({"timescale": "TT", "timeorigin": "MJD-origin"}, {}),
                            ({"timescale": "TT"}, {})):
        t2 = cat.table.copy()
        t2["t"].meta["timesys"] = timesys
        seen.error(time_filter, dataclasses.replace(cat, table=t2), start, end, column="t", **kwargs)

    # --- ASTRORES ----------------------------------------------------------------------------------------------------------------
    def astro(body: str):
        path = tmp_path / "a.xml"
        path.write_text(f'<?xml version="1.0"?><ASTRO><RESOURCE><TABLE>{body}</TABLE></RESOURCE></ASTRO>')
        return path

    seen.error(read_table, astro('<FIELD name="a"/><DATA/>'.replace("<DATA/>", "<DATA></DATA>")))  # no_data
    seen.error(read_table, astro("<DATA><CSV>1</CSV></DATA>"))  # no_fields
    seen.error(read_table, astro('<FIELD name="a"/><FIELD name="a"/><DATA><CSV>1\t2</CSV></DATA>'))
    seen.error(read_table, astro('<FIELD name="a"/><DATA><LINK content-type="text/csv"/></DATA>'))  # link_no_address
    seen.error(cats._parse_astrores, _write(tmp_path / "r.xml", "<ALTRO/>"))
    seen.error(cats._parse_astrores, _write(tmp_path / "m.xml", "<ASTRO><x></ASTRO>"))
    seen.notes(read_table(astro('<FIELD name="a" datatype="F"/><FIELD name="b" datatype="L"/>'
                                '<DATA><CSV>abc\tx</CSV></DATA>')).warnings)
    seen.notes(read_table(write_astrores(tmp_path / "w.xml", ), table=0).warnings)
    seen.notes(read_table(write_astrores(tmp_path / "s.xml", rows=("00 13 00.93|+72 31 19.9|11.2|7|T|a",
                                                                   "12:30:15.5|-05:06:07||8|false|bb"), ref="#id(eq)"),
                          table=0).warnings)
    seen.notes(read_table(astro('<FIELD name="a" ucd="POS_EQ_RA"/><FIELD name="b" ucd="POS_EQ_DE"/>'
                                '<DATA><CSV>1\t2</CSV></DATA>')).warnings)
    seen.error(read_table, astro('<FIELD name="a"/><FIELD name="b"/><DATA><CSV>1\t2\n3</CSV></DATA>'))
    bomb = tmp_path / "bomba.xml"
    bomb.write_text('<?xml version="1.0"?><!DOCTYPE ASTRO [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
                    '<ASTRO><RESOURCE><TABLE><FIELD name="x"/><DATA><CSV>&b;</CSV></DATA></TABLE></RESOURCE></ASTRO>')
    seen.error(read_table, bomb)
    # LINK: rifiuti e lettura riuscita
    payloads = linked_payloads()
    service.routes["/dati.csv"] = lambda r: (200, "text/csv", payloads["csv"])
    url = service.url + "/dati.csv"
    for link_text in ('href="%s"' % url, 'href="%s" content-type="text/plain"' % url,
                      'href="%s" content-type="text/csv; header=absent"' % url,
                      'gref="VizieR" content-type="text/csv"', 'action="http://esempio.invalid/q" content-type="text/csv"',
                      'href="dati.csv" content-type="text/csv"'):
        path = tmp_path / "rifiuto.xml"
        path.write_text(LINKED.format(link=link_text))
        seen.error(load_table, path, cache=cache)
    path.write_text(LINKED.format(link=f'href="{url}" content-type="text/csv"'))
    seen.error(read_table, path)  # link_needs_network
    seen.notes(load_table(path, cache=cache).warnings)  # ASTRORES_LINK
    # LINK: dati non leggibili, differenze tra FIELD e dati collegati, memoria
    garbage = b"questo non e un votable"
    service.routes["/g.xml"] = lambda r: (200, "text/xml", garbage)
    link = tmp_path / "g.xml"
    link.write_text(LINKED.format(link=f'href="{service.url}/g.xml" content-type="application/x-votable+xml"'))
    seen.error(load_table, link, cache=cache)
    big = b"a" * 20000
    service.routes["/big.csv"] = lambda r: (200, "text/csv", big)
    link.write_text(LINKED.format(link=f'href="{service.url}/big.csv" content-type="text/csv"'))
    seen.error(load_table, link, cache=cache, limits=TableLimits(operation_bytes=5000))
    service.routes["/bad.fits"] = lambda r: (200, "application/fits", b"XX")
    link.write_text(LINKED.format(link=f'href="{service.url}/bad.fits" content-type="application/fits"'))
    seen.error(load_table, link, cache=cache)
    conflict = tmp_path / "conf.xml"
    conflict.write_text(
        '<?xml version="1.0"?><ASTRO><RESOURCE><TABLE>'
        '<FIELD datatype="F" unit="mag" ucd="phot.mag"><NAME>A</NAME></FIELD>'
        '<FIELD datatype="F"><NAME>B</NAME></FIELD><FIELD datatype="L"><NAME>C</NAME></FIELD>'
        f'<DATA><LINK href="{service.url}/c.xml" content-type="application/x-votable+xml"/></DATA>'
        "</TABLE></RESOURCE></ASTRO>")
    linked = Table({"A": [1.0], "B": ["x"], "C": [2.0]})
    linked["A"].unit = u.Jy
    linked["A"].meta["ucd"] = "phot.flux"
    buffer = io.BytesIO()
    linked.write(buffer, format="votable")
    service.routes["/c.xml"] = lambda r: (200, "text/xml", buffer.getvalue())
    seen.error(load_table, conflict, cache=cache)
    names = io.StringIO()
    astropy_ascii.write(Table({"Z": [1.0]}), names, format="csv")
    service.routes["/z.csv"] = lambda r: (200, "text/csv", names.getvalue())
    conflict.write_text(conflict.read_text().replace("/c.xml", "/z.csv").replace("application/x-votable+xml", "text/csv"))
    seen.error(load_table, conflict, cache=cache)

    # --- servizio: regioni e cataloghi --------------------------------------------------------------------------------------------
    from astropy.coordinates import SkyCoord as Sky

    center = SkyFrame(Sky(10 * u.deg, 20 * u.deg))
    seen.error(load_catalog, "I/355/gaiadr3", region=(center, 5))
    seen.error(load_catalog, "I/355/gaiadr3", region=(center, 500 * u.deg))
    seen.error(load_catalog, "no valido!")
    monkeypatch.setattr(cats, "_schema_columns", lambda *a, **k: ("RA", "DE"))

    def tap_with(positions):
        return lambda *a, **k: SimpleNamespace(table=SimpleNamespace(positions=positions))

    with monkeypatch.context() as patch:
        patch.setattr(vo, "tap_query", tap_with(None))
        seen.error(load_catalog, "I/355/gaiadr3", region=(center, 1 * u.deg))  # service_no_coosys
        patch.setattr(vo, "tap_query", tap_with(PositionColumns("RA", "DE", "fk5", system="eq_FK5")))
        seen.error(load_catalog, "I/355/gaiadr3", region=(center, 1 * u.deg))  # no_equinox
        patch.setattr(vo, "tap_query", tap_with(PositionColumns("RA", "DE", None, system="boh")))
        seen.error(load_catalog, "I/355/gaiadr3", region=(center, 1 * u.deg))  # service_undeclared
    monkeypatch.undo()
    schema = Table({"column_name": ["a b", "dec"], "ucd": ["pos.eq.ra;meta.main", "pos.eq.dec;meta.main"]})
    two_ra = Table({"column_name": ["ra1", "ra2", "dec"], "ucd": ["pos.eq.ra", "pos.eq.ra", "pos.eq.dec"]})
    with monkeypatch.context() as patch:
        patch.setattr(vo, "tap_query", lambda *a, **k: SimpleNamespace(table=SimpleNamespace(table=schema)))
        seen.error(cats._schema_columns, vo, "cds-vizier-tap", "X", {})  # column_name_invalid
        patch.setattr(vo, "tap_query", lambda *a, **k: SimpleNamespace(table=SimpleNamespace(table=two_ra)))
        seen.error(cats._schema_columns, vo, "cds-vizier-tap", "X", {})  # schema_ambiguous
        patch.setattr(vo, "tap_query", lambda *a, **k: SimpleNamespace(table=SimpleNamespace(table=schema[:0])))
        monkeypatch.setattr(cats, "_table_candidates", lambda *a, **k: ((), False))
        seen.error(cats._schema_columns, vo, "cds-vizier-tap", "X", {})
        monkeypatch.setattr(cats, "_table_candidates", lambda *a, **k: (("X/a", "X/b"), False))
        seen.error(cats._schema_columns, vo, "cds-vizier-tap", "X", {})
        monkeypatch.setattr(cats, "_table_candidates", lambda *a, **k: (("X/a", "X/b"), True))
        seen.error(cats._schema_columns, vo, "cds-vizier-tap", "X", {})

        def refused(*args, **kwargs):
            raise vo.VoProtocolsError("ADQL_INVALID", "rifiutato", service_message="table not found",
                                         params={"reason": "service_rejected", "url": "https://tap.example/tap",
                                                 "detail": "table not found"})

        patch.setattr(vo, "tap_query", refused)
        for candidates in (((), False), (("X/a",), False), (("X/a",), True)):
            monkeypatch.setattr(cats, "_table_candidates", lambda *a, __c=candidates, **k: __c)
            seen.error(load_catalog, "X")
    # troncamento
    truncated = SimpleNamespace(truncated=True, max_rows=10, warnings=(ModuleWarning("ROW_LIMIT_EXCEEDED", "tagliato", {"reason": "service_overflow", "received": 10,
                                                                                    "max_rows": 10}),),
                                table=read_table(csv), request=None, descriptors=())
    with monkeypatch.context() as patch:
        patch.setattr(vo, "tap_query", lambda *a, **k: truncated)
        seen.error(load_catalog, "X")
        patch.setattr(cats, "_catalog_region", lambda *a, **k: CatalogRegion(
            "RA", "DE", "fk5", "J2000", "J2016.0", 10.0, 20.0, 1.0, "SELECT 1"))
        seen.error(load_catalog, "X", region=(center, 1 * u.deg))
        patch.setattr(cats, "_from_vo_result", lambda result: result.table)
        partial = load_catalog("X", region=(center, 1 * u.deg), allow_partial=True)
        seen.notes(partial.warnings)  # REGION equinox_epoch, PARTIAL_CATALOG in_region
        partial = load_catalog("X", allow_partial=True)
        seen.notes(partial.warnings)
    for equinox, epoch in ((None, None), ("J2000", None), (None, "J2016.0")):
        region = CatalogRegion("RA", "DE", "fk5", equinox, epoch, 10.0, 20.0, 1.0, "SELECT 1")
        seen.notes([ModuleWarning("REGION", region.describe(), region.describe_params())])

    # --- albero delle collezioni ---------------------------------------------------------------------------------------------
    records = [{"ID": f"CDS/Altro{k}", "obs_title": "x"} for k in range(12)] + [
        {"ID": "CDS/I/1/a", "vizier_popularity": "abc"}, {"ID": "CDS/I/2/b", "vizier_popularity": "5"},
        {"ID": "CDS/I/3/c"}]
    fetched = SimpleNamespace(records=records, warnings=(), request=SimpleNamespace(retrieved_at=None))
    with monkeypatch.context() as patch:
        patch.setattr(vo, "vizier_collections", lambda **k: fetched)
        seen.notes(collection_tree().warnings)

    # --- verifiche finali -------------------------------------------------------------------------------------------------------------
    missing = required_combinations() - seen.pairs
    assert not missing, f"errori e avvisi del 13 mai provocati nel test: {sorted(missing, key=str)}"


def _write(path, text):
    path.write_text(text)
    return str(path)


def _unrecognized():
    table = Table({"x": [1.0]})
    table["x"].unit = u.UnrecognizedUnit("banana")
    return cats._normalize_units(table)


def test_italian_text_is_unchanged_and_params_are_json(tmp_path):
    cat = base_table(tmp_path)
    with pytest.raises(CatalogsError) as info:
        confirm_position_columns(cat, "nope", "dec", "icrs")
    err = info.value
    assert err.message == "colonna 'nope' inesistente" and err.params == {"reason": "column_missing", "column": "nope"}
    json.dumps(err.params)
    assert mc.message_text(err.code, err.params, "en", text=err.message) == "Column 'nope' does not exist."
    assert mc.message_text(err.code, err.params, "it", text=err.message) == "La colonna 'nope' non esiste."


def test_propagation_relays_the_error_of_module_10(tmp_path):
    cat = base_table(tmp_path)
    with pytest.raises(CatalogsError) as info:
        propagate(cat, 2020.0, **pm(parallax="plx", source_epoch="boh"))
    err = info.value
    assert err.relayed and err.message.startswith("propagazione: ") and err.params
    assert check_error(err)[0] == err.code


def test_nested_message_of_a_linked_data_error(tmp_path, service, cache):  # noqa: F811
    """``cause`` e ``problems`` sono messaggi annidati (D40-7): resi nella lingua, testo di terzi esterno."""
    service.routes["/g.xml"] = lambda r: (200, "text/xml", b"non e un votable")
    link = tmp_path / "g.xml"
    link.write_text(LINKED.format(link=f'href="{service.url}/g.xml" content-type="application/x-votable+xml"'))
    with pytest.raises(CatalogsError) as info:
        load_table(link, cache=cache)
    err = info.value
    assert err.params["reason"] == "link_unreadable" and err.params["cause"]["code"] == "TABLE_UNREADABLE"
    assert mc.message_params(err.code, err.params) == {"cause"}
    text_en = mc.message_text(err.code, err.params, "en", text=err.message)
    assert "VOTable not readable" in text_en and "non leggibili" not in text_en
    masked = mc.message_text(err.code, err.params, "en", text=err.message, mask_external=True)
    assert "<detail>" in masked
