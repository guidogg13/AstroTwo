# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""D62-8 (decisione del proprietario del 2026-11-13): **ogni tipo di VOTable che AstroTwo scrive** è valido rispetto
allo schema VOTable: cataloghi esportati, sottoinsiemi salvati, tabelle mandate via SAMP, punti della SED, risultati
di un incrocio e di una query ADQL. Controlli in ``tests/votable_check.py`` (ID univoci, Astropy
``verify="exception"`` con le sole unità della fonte ammesse, ``votlint`` di STILTS se c'è). Nessuna rete."""

from __future__ import annotations

import urllib.parse

import astropy.units as u
import numpy as np
import pytest
from astropy.io.votable import parse as parse_votable

from astrotwo.core.catalogs import read_table, save_subset
from astrotwo.core.crossmatch import crossmatch
from astrotwo.core.vo_protocols import SampHub, export_table, tap_query
from tests.analysis.profile_fakes import services  # noqa: F401
from tests.analysis.test_profile_export import export, profile, session_with_export
from tests.core.test_vo_protocols import local_hub, peer, samp_home, wait_for  # noqa: F401
from tests.votable_check import assert_valid_votable, duplicate_ids, votlint_available, votlint_errors

#: Come il catalogo Gaia DR3 di C1 (megatest): **due** colonne con un'unità fuori da VOUnit (``log(cm.s**-2)``, testo
#: della fonte) e un flusso con l'unità VOUnit tra apici.
GAIA_LIKE = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/><COOSYS ID="s" system="ICRS" epoch="J2016.0"/>
<TABLE name="gaia">
<FIELD name="ra" datatype="double" unit="deg" ucd="pos.eq.ra;meta.main" ref="s"/>
<FIELD name="dec" datatype="double" unit="deg" ucd="pos.eq.dec;meta.main" ref="s"/>
<FIELD name="logg_gspphot" datatype="float" unit="log(cm.s**-2)"/>
<FIELD name="logg_gspspec" datatype="float" unit="log(cm.s**-2)"/>
<FIELD name="phot_g_mean_flux" datatype="double" unit="'electron'.s**-1" ucd="phot.flux;em.opt"/>
<DATA><TABLEDATA>
{rows}
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""
SOURCE_UNITS = ("log(cm.s**-2)",)


def gaia_text(n: int = 3, start: float = 56.75) -> str:
    rows = "\n".join(f"<TR><TD>{start + 0.01 * k}</TD><TD>{24.1 + 0.01 * k}</TD><TD>4.4</TD><TD>4.3</TD>"
                     f"<TD>{1000.5 + k}</TD></TR>" for k in range(n))
    return GAIA_LIKE.format(rows=rows)


@pytest.fixture
def gaia(tmp_path):
    path = tmp_path / "gaia.xml"
    path.write_text(gaia_text(), encoding="utf-8")
    return read_table(path)


def same_values(path, table) -> None:
    """Valori e unità invariati (D62-8): stessa tabella, stessa unità per ogni colonna."""
    got = parse_votable(str(path)).get_first_table().to_table(use_names_over_ids=True)
    for name in ("ra", "dec", "phot_g_mean_flux", "logg_gspphot"):
        assert np.array_equal(np.asarray(got[name]), np.asarray(table.table[name]))
    assert got["ra"].unit == u.deg


def test_build8_defect_is_caught(tmp_path):
    """Il controllo vede il difetto del build 8: due ``INFO`` con lo stesso ID."""
    bad = tmp_path / "bad.xml"
    bad.write_text(gaia_text().replace('<INFO name="QUERY_STATUS" value="OK"/>',
                                       '<INFO ID="A2NOTE" name="A2NOTE" value="x"/>'
                                       '<INFO ID="A2NOTE" name="A2NOTE" value="y"/>'), encoding="utf-8")
    assert duplicate_ids(bad) == ["A2NOTE"]
    if votlint_available():
        assert any("A2NOTE" in line for line in votlint_errors(bad))


def test_catalog_export_valid_with_two_nonstandard_units(gaia, tmp_path):
    result = export_table(gaia, tmp_path / "out.xml", "votable")
    text = (tmp_path / "out.xml").read_text(encoding="utf-8")
    assert text.count('name="A2NOTE"') == 2 and 'ID="A2NOTE"' in text and 'ID="A2NOTE_2"' in text
    assert "logg_gspphot (log(cm.s**-2))" in dict(result.warnings)["EXPORT_UNIT_NOT_STANDARD"]
    assert 'unit="log(cm.s**-2)"' in text and "unit=\"&apos;electron&apos;.s**-1\"" in text  # unità invariate
    assert_valid_votable(tmp_path / "out.xml", SOURCE_UNITS)
    same_values(tmp_path / "out.xml", gaia)


def test_field_ids_unique_for_similar_column_names(tmp_path):
    """Due nomi di colonna diversi che danno lo stesso ID in Astropy («a b» e «a_b» → ``a_b``): il secondo FIELD
    prende ``a_b_2``, i nomi non cambiano. (Qui Astropy, rileggendo, rinomina per conto suo la colonna nella tabella
    in memoria, avviso ``W33``: non riguarda lo schema, quindi si controllano ID e ``votlint``.)"""
    from astropy.table import Table

    from astrotwo.core.catalogs import CatalogTable

    path = tmp_path / "names.xml"
    path.write_text(gaia_text(), encoding="utf-8")
    table = read_table(path)
    extra = Table(table.table, copy=True)
    extra["a b"], extra["a_b"] = [1.0, 2.0, 3.0], [4.0, 5.0, 6.0]
    import dataclasses

    export_table(dataclasses.replace(table, table=extra), tmp_path / "out.xml", "votable")
    text = (tmp_path / "out.xml").read_text(encoding="utf-8")
    assert 'ID="a_b" ' in text and 'ID="a_b_2" ' in text and 'name="a b"' in text and 'name="a_b"' in text
    assert duplicate_ids(tmp_path / "out.xml") == []
    assert votlint_errors(tmp_path / "out.xml") in (None, [])
    assert CatalogTable  # tipo della tabella esportata


def test_saved_subset_valid_keeps_every_note(gaia, tmp_path):
    path = save_subset(gaia, np.ones(len(gaia.table), bool), tmp_path / "subset.xml")
    text = path.read_text(encoding="utf-8")
    assert text.count('name="A2NOTE"') == 2  # prima: solo la prima nota (setdefault)
    assert_valid_votable(path, SOURCE_UNITS)
    same_values(path, gaia)


def test_samp_table_valid(peer, gaia):  # noqa: F811
    with SampHub() as samp:
        samp.send_table(gaia, table_id="gaia", name="Gaia DR3")
        assert wait_for(lambda: peer.received)
        url = peer.received[0][4]["url"]
        path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)  # file temporaneo: si legge prima di chiudere
        assert_valid_votable(path, SOURCE_UNITS)
        same_values(path, gaia)


def test_crossmatch_result_valid(gaia, tmp_path):
    other = tmp_path / "other.xml"
    other.write_text(gaia_text(start=56.75 + 0.1 / 3600), encoding="utf-8")
    joined = crossmatch(gaia, read_table(other), max_sep=1 * u.arcsec).joined()
    assert len(joined.table) == 3
    export_table(joined, tmp_path / "joined.xml", "votable")
    assert_valid_votable(tmp_path / "joined.xml", SOURCE_UNITS)


def test_adql_result_valid(service, cache, tmp_path):
    service.routes["/tap/sync"] = lambda request: (200, "application/x-votable+xml", gaia_text(4))
    result = tap_query(service.url + "/tap", "SELECT * FROM gaia", cache=cache)
    export_table(result.table, tmp_path / "adql.xml", "votable")
    assert_valid_votable(tmp_path / "adql.xml", SOURCE_UNITS)


def test_sed_points_valid(cache, services, tmp_path):  # noqa: F811
    session = session_with_export(cache)
    number, _ = profile(session, {"name": "TRAPPIST-1", "sections": ["identity", "photometry"]})
    written = export(session, [number], "sed_votable", tmp_path / "sed.xml")
    assert written.status == "ok" and written.values["rows"] > 0
    assert_valid_votable(tmp_path / "sed.xml")  # unità della SED tutte standard: nessun avviso ammesso


def test_votlint_present_on_the_development_mac():
    """Sul Mac di sviluppo STILTS c'è (TOPCAT in ``~/Applications/topcat``): senza, i controlli sopra fanno solo le
    prove di Astropy e degli ID. Saltato, con il motivo, dove STILTS non c'è."""
    if not votlint_available():
        pytest.skip("STILTS (topcat-full.jar o stilts.jar) o Java non trovati: votlint non eseguito")
