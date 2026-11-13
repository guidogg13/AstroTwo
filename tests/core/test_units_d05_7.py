# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""D05-7 (decisione del proprietario del 2026-11-13): unità delle colonne nei VOTable dei cataloghi (anche via SAMP) e
nei FITS di tabella, e unità VOUnit di Gaia con un nome tra apici in ingresso (``mdfiles/05-comandi-sessione.md`` §13).

Regola: nel file il testo standard del formato **esatto** (mai un fattore troncato: D05-6); se il formato non scrive
l'unità esattamente, un testo esatto non standard dichiarato (``EXPORT_UNIT_NOT_STANDARD``), mai un'unità omessa.
"""

from __future__ import annotations

import dataclasses
import re
import warnings

import astropy.units as u
import numpy as np
import pytest
from astropy.io import fits

from astrotwo.core.catalogs import _standard_unit, column_unit_text, read_table
from astrotwo.core.vo_protocols import export_table

#: VOTable come quelli dell'archivio Gaia DR3: unità VOUnit con un nome tra apici (flussi in elettroni al secondo).
GAIA_LIKE = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><COOSYS ID="s" system="ICRS" epoch="J2016.0"/>
<TABLE>
<FIELD name="ra" datatype="double" unit="deg" ucd="pos.eq.ra;meta.main" ref="s"/>
<FIELD name="dec" datatype="double" unit="deg" ucd="pos.eq.dec;meta.main" ref="s"/>
<FIELD name="phot_g_mean_flux" datatype="double" unit="'electron'.s**-1" ucd="phot.flux;em.opt"/>
<DATA><TABLEDATA>
<TR><TD>56.75</TD><TD>24.1167</TD><TD>123456.789</TD></TR>
<TR><TD>56.80</TD><TD>24.1200</TD><TD>2345.5</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""


@pytest.fixture
def gaia(tmp_path):
    path = tmp_path / "gaia.xml"
    path.write_text(GAIA_LIKE, encoding="utf-8")
    return read_table(path)


def written_units(path) -> dict[str, str]:
    """Attributi ``unit`` dei FIELD così come sono scritti nel file (testo grezzo, non riletto)."""
    import html

    text = path.read_text(encoding="utf-8")
    return {k: html.unescape(v) for k, v in re.findall(r'<FIELD[^>]*?name="([^"]+)"[^>]*?unit="([^"]*)"', text)}


def test_gaia_quoted_vounit_kept_on_input(gaia):
    column = gaia.table["phot_g_mean_flux"]
    assert column.unit is not None and "unit_unrecognized" not in column.meta
    assert "UNIT_UNRECOGNIZED" not in [w[0] for w in gaia.warnings]
    assert column_unit_text(column, "vounit") == ("'electron'.s**-1", True)


def test_votable_units_exact_never_truncated_never_dropped(gaia, tmp_path):
    data = gaia.table.copy()
    data["ha"] = [1.0, 2.0] * u.hourangle
    data["turns"] = [0.5, 1.5] * u.cycle
    data["metal"] = [0.1, -0.2] * u.dex
    data["mass"] = [1.0, 2.0] * u.earthMass
    data["days"] = [3.0, 4.0]
    data["days"].meta["unit_unrecognized"] = "days"  # unità della fonte non letta: resta il testo della fonte
    table = dataclasses.replace(gaia, table=data)
    result = export_table(table, tmp_path / "t.xml", "votable")
    units = written_units(result.path)
    assert units["phot_g_mean_flux"] == "'electron'.s**-1"  # prima: unità assente (D11)
    assert units["ha"] == "15deg"  # esatto, accettato dal proprietario il 2026-11-13
    assert units["turns"] == "6.283185307179586rad"  # prima: 6.2831853rad (fattore troncato)
    assert units["mass"] == f"{u.earthMass.decompose().scale!r}kg"
    assert units["metal"] == "'dex'"  # unità che VOUnit non conosce: tra apici, come fa l'archivio Gaia
    assert units["days"] == "days"  # testo della fonte non letto: invariato, dichiarato
    for name in ("ha", "turns", "mass", "phot_g_mean_flux", "metal"):  # ogni testo si rilegge nella stessa unità
        assert _standard_unit(units[name]) == data[name].unit
    codes = [w[0] for w in result.warnings]
    assert codes == ["EXPORT_UNIT_NOT_STANDARD"]
    assert result.warnings[0].params["columns"] == ["days (days)"]
    back = read_table(result.path)  # rilettura: valori identici
    assert np.array_equal(np.asarray(back.table["turns"]), np.asarray(data["turns"]))


def test_fits_table_units_never_fail_never_dropped(gaia, tmp_path):
    data = gaia.table.copy()
    data["ha"] = [1.0, 2.0] * u.hourangle
    data["turns"] = [0.5, 1.5] * u.cycle
    data["metal"] = [0.1, -0.2] * u.dex
    table = dataclasses.replace(gaia, table=data)
    result = export_table(table, tmp_path / "t.fits", "fits")  # prima: UnitScaleError di Astropy
    with fits.open(result.path) as hdus:
        header = hdus[1].header
        tunit = {header[f"TTYPE{k}"]: header.get(f"TUNIT{k}") for k in range(1, header["TFIELDS"] + 1)}
    assert tunit["ra"] == "deg" and tunit["dec"] == "deg"  # standard FITS
    assert tunit["phot_g_mean_flux"] == "'electron'.s**-1"  # prima: TUNIT omesso in silenzio
    assert tunit["ha"] == "15deg" and tunit["turns"] == "6.283185307179586rad" and tunit["metal"] == "'dex'"
    assert [w[0] for w in result.warnings] == ["EXPORT_UNIT_NOT_STANDARD"]
    assert set(result.warnings[0].params["columns"]) == {"phot_g_mean_flux ('electron'.s**-1)", "ha (15deg)",
                                                     "turns (6.283185307179586rad)", "metal ('dex')"}


def test_standard_units_unchanged(gaia, tmp_path):
    """Le unità già standard non cambiano testo e non danno avvisi."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        data = gaia.table.copy()
        data["pm"] = [1.0, 2.0] * u.mas / u.yr
        data["flux"] = [1.0, 2.0] * u.Jy
        table = dataclasses.replace(gaia, table=data)
        result = export_table(table, tmp_path / "s.fits", "fits")
    with fits.open(result.path) as hdus:
        header = hdus[1].header
        tunit = {header[f"TTYPE{k}"]: header.get(f"TUNIT{k}") for k in range(1, header["TFIELDS"] + 1)}
    assert tunit["pm"] == "mas yr-1" and tunit["flux"] == "Jy"
    assert "pm" in written_units(export_table(table, tmp_path / "s.xml", "votable").path)
