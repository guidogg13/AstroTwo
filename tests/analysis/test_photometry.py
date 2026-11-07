# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Fotometria, parte SED (``mdfiles/20-analisi-fotometria.md`` §12: T1–T10).

Gli attesi si ricalcolano con Astropy (``u.Magnitude`` per 10^(−0,4 m), ``u.spectral``) a partire dai punti zero
scritti nella specifica (20 §3.2), mai con la formula del modulo. I valori di ingresso sono quelli osservati il
2026-11-07 (20 §12); i test con le risposte registrate dei servizi sono in ``test_object_profile_photometry.py``.
"""

from __future__ import annotations

import io

import astropy.units as u
import numpy as np
import pytest
from astropy.table import Table

from astrotwo.analysis.photometry import (
    AB_FLUX_ZERO,
    CATALOG_REFERENCES,
    ZERO_POINTS,
    Sed,
    VizierSeries,
    build_sed,
    high_proper_motion,
    mag_to_flux,
    sed_png,
    sed_points_from,
    sed_table,
)
from astrotwo.core.vo_protocols import SimbadMagnitude

PROV = {"service": "test", "server": "http://test", "retrieved_at": None}


def tmass_row(j, ej, h, eh, k, ek, ph_qual="AAA", rd="111", cc="000", jdate=2451500.5):
    table = Table({"designation": ["22572795+2046077"], "ra": [344.366], "dec": [20.768],
                   "j_m": [j], "j_msigcom": [ej], "h_m": [h], "h_msigcom": [eh], "k_m": [k], "k_msigcom": [ek],
                   "ph_qual": [ph_qual], "rd_flg": [rd], "cc_flg": [cc], "jdate": [jdate]})
    for name in ("j_m", "j_msigcom", "h_m", "h_msigcom", "k_m", "k_msigcom"):
        table[name].unit = u.mag
    table["jdate"].unit = u.d
    return table


def wise_row(mags, errs, ph_qual="AAAA"):
    table = Table({"designation": ["J225728.12+204608.6"], "ra": [344.367], "dec": [20.769]})
    for k in range(4):
        table[f"w{k + 1}mpro"] = np.ma.masked_invalid([np.nan if mags[k] is None else mags[k]])
        table[f"w{k + 1}sigmpro"] = np.ma.masked_invalid([np.nan if errs[k] is None else errs[k]])
        table[f"w{k + 1}mpro"].unit = table[f"w{k + 1}sigmpro"].unit = u.mag
    table["ph_qual"], table["cc_flags"], table["ext_flg"] = [ph_qual], ["0000"], [0]
    return table


def gaia_row(flux=(1.0e7, 5.0e6, 6.0e6), err=(1.0e3, 2.0e3, 3.0e3)):
    table = Table({"source_id": [2835207319109249920]})
    for k, band in enumerate(("g", "bp", "rp")):
        table[f"phot_{band}_mean_mag"] = [5.0 + k]
        table[f"phot_{band}_mean_mag"].unit = u.mag
        table[f"phot_{band}_mean_flux"] = [flux[k]]
        table[f"phot_{band}_mean_flux_error"] = [err[k]]
        table[f"phot_{band}_mean_flux"].unit = table[f"phot_{band}_mean_flux_error"].unit = u.electron / u.s
    table["phot_variable_flag"], table["phot_bp_rp_excess_factor"] = ["NOT_AVAILABLE"], [1.2]
    return table


def point(points, catalog, band):
    return next(p for p in points if p.catalog == catalog and p.band == band)


def vega_flux(f0_jy: float, mag: float) -> u.Quantity:
    return f0_jy * u.Jy * u.Magnitude(mag).physical  # 10^(−0,4 m) da Astropy


# =============================================================================
# T1 — 2MASS → flusso


def test_t1_2mass_flux_with_zero_point_error():
    j = point(sed_points_from(tmass_row(4.655, 0.296, 4.234, 0.268, 3.911, 0.021), "2mass", provenance=PROV),
              "2MASS", "J")
    out = mag_to_flux(j)
    expected = vega_flux(1594.0, 4.655)
    assert out.flux.unit == u.Jy and out.flux.value == pytest.approx(expected.value, rel=1e-12)
    rel = np.hypot(0.4 * np.log(10) * 0.296, 27.8 / 1594.0)
    assert out.flux_error.value == pytest.approx(expected.value * rel, rel=1e-12)
    assert out.wavelength == 1.235 * u.um
    assert out.conversion["zero_point"]["key"] == "2MASS J"
    assert out.flux.dtype == np.float64


# =============================================================================
# T2 — WISE → flusso


def test_t2_wise_flux():
    pts = sed_points_from(wise_row([4.0, 3.9, 3.929, 3.8], [0.1, 0.05, 0.016, 0.03]), "allwise", provenance=PROV)
    out = mag_to_flux(point(pts, "AllWISE", "W3"))
    expected = vega_flux(31.674, 3.929)
    assert out.flux.value == pytest.approx(expected.value, rel=1e-12)
    rel = np.hypot(0.4 * np.log(10) * 0.016, 0.450 / 31.674)
    assert out.flux_error.value == pytest.approx(expected.value * rel, rel=1e-12)
    assert out.wavelength == 11.5608 * u.um


# =============================================================================
# T3 — Gaia → flusso dal flusso in e⁻/s


def test_t3_gaia_flux_from_count_rate():
    out = mag_to_flux(point(sed_points_from(gaia_row(), "gaia_dr3", provenance=PROV), "Gaia DR3", "G"))
    m_ab = -2.5 * np.log10(1.0e7) + 25.8010446445
    # 3631 Jy come scritto nel 20 §3.2 (Astropy usa 10^(−0,4·48,60) cgs = 3630,78 Jy: differenza 6·10⁻⁵, D20-9 (5))
    expected = 3631.0 * u.Jy * u.Magnitude(m_ab).physical
    assert out.flux.value == pytest.approx(expected.value, rel=1e-9)
    sigma_m = 2.5 / np.log(10) * 1.0e3 / 1.0e7
    assert out.flux_error.value == pytest.approx(expected.value * 0.4 * np.log(10) * np.hypot(sigma_m, 0.0027590522),
                                                 rel=1e-9)
    assert out.conversion["m_ab"]["value"] == pytest.approx(m_ab, rel=1e-12)
    assert out.wavelength == (621.79 * u.nm).to(u.um)
    assert AB_FLUX_ZERO == 3631 * u.Jy


# =============================================================================
# T4 — banda senza punto zero (SIMBAD V) e sistema non dichiarato


def test_t4_band_without_zero_point_and_without_system():
    mags = (SimbadMagnitude("V", "Magnitude V", 5.46, 0.05, "mag", "Vega", "C", "2009ApJ...694.1085V"),
            SimbadMagnitude("J", "Magnitude J", 11.354, 0.022, "mag", None, "C", "2003yCat.2246....0C"))
    sed = build_sed(sed_points_from(mags, "simbad", provenance=PROV))
    v, j = point(sed.points, "SIMBAD", "V"), point(sed.points, "SIMBAD", "J")
    assert v.codes() == ["SED_NO_ZERO_POINT"] and v.flux is None and not v.in_plot
    assert v.magnitude == 5.46 * u.mag
    assert "SED_NO_SYSTEM" in j.codes() and j.flux is None


# =============================================================================
# T5 — qualità (2MASS D, AllWISE X) fuori dal grafico; T6 — limite superiore


def test_t5_low_quality_out_of_the_plot():
    sed = build_sed(sed_points_from(tmass_row(2.9, 0.3, 3.0, 0.2, 2.9, 0.3, ph_qual="DCD"), "2mass",
                                    provenance=PROV))
    j, h = point(sed.points, "2MASS", "J"), point(sed.points, "2MASS", "H")
    assert "SED_LOW_QUALITY" in j.codes() and not j.in_plot and j.flux is not None
    assert h.quality == "C" and h.in_plot


def test_t6_upper_limit():
    pts = sed_points_from(wise_row([10.068, 9.5, 9.0, 8.565], [0.023, 0.02, 0.03, None], ph_qual="AAAU"),
                          "allwise", provenance=PROV)
    sed = build_sed(pts)
    w4 = point(sed.points, "AllWISE", "W4")
    assert w4.upper_limit and "SED_UPPER_LIMIT" in w4.codes() and "SED_NO_ERROR" in w4.codes()
    assert not w4.in_plot and w4.flux.value == pytest.approx(vega_flux(8.363, 8.565).value, rel=1e-12)
    assert point(sed.points, "AllWISE", "W1").in_plot


# =============================================================================
# T7 — duplicati SIMBAD (51 Peg)


def test_t7_simbad_duplicates_of_catalog_points():
    simbad = (SimbadMagnitude("G", None, 5.283212, 0.002831, "mag", "Vega", "C", "2020yCat.1350....0G"),
              SimbadMagnitude("K", None, 3.911, 0.021, "mag", "Vega", "C", "2003yCat.2246....0C"),
              SimbadMagnitude("V", None, 5.46, 0.05, "mag", "Vega", "C", "2009ApJ...694.1085V"))
    pts = (sed_points_from(gaia_row(), "gaia_dr3", provenance=PROV)
           + sed_points_from(tmass_row(4.655, 0.296, 4.234, 0.268, 3.911, 0.021), "2mass", provenance=PROV)
           + sed_points_from(simbad, "simbad", provenance=PROV))
    sed = build_sed(pts)
    assert point(sed.points, "SIMBAD", "G").duplicate_of == "Gaia DR3 G"
    assert point(sed.points, "SIMBAD", "K").duplicate_of == "2MASS Ks"
    assert point(sed.points, "SIMBAD", "V").duplicate_of is None
    assert not any(p.in_plot for p in sed.points if p.catalog == "SIMBAD")
    assert len([p for p in sed.plotted if p.band in ("G", "Ks")]) == 2  # una volta sola
    # senza il punto del catalogo nella SED non è un duplicato
    alone = build_sed(sed_points_from(simbad, "simbad", provenance=PROV))
    assert point(alone.points, "SIMBAD", "G").duplicate_of is None
    assert set(CATALOG_REFERENCES) == {"2022yCat.1355....0G", "2020yCat.1350....0G", "2003yCat.2246....0C"}


# =============================================================================
# T8 — serie VizieR separata, non convertita


def test_t8_vizier_series_as_given():
    table = Table({"_sed_freq": [138.55, 241.96], "_sed_flux": [3.6, 2.1], "_sed_eflux": [0.1, np.nan],
                   "_sed_filter": ["2MASS:Ks", "2MASS:H"], "_tabname": ["II/246/out", "II/246/out"]})
    table["_sed_freq"].unit = u.GHz
    table["_sed_flux"].unit = table["_sed_eflux"].unit = u.Jy
    table["_sed_eflux"] = np.ma.masked_invalid(table["_sed_eflux"])
    sed = build_sed((), VizierSeries(table, PROV))
    rows = sed.vizier.rows()
    assert rows[0]["flux"] == {"value": 3.6, "unit": "Jy"} and rows[0]["catalog"] == "II/246/out"
    assert rows[0]["wavelength"]["value"] == pytest.approx((138.55 * u.GHz).to_value(u.um, u.spectral()))
    assert rows[1]["flux_error"] is None
    assert sed.points == ()


def test_high_proper_motion_threshold():
    assert high_proper_motion(100 * u.mas / u.yr, 0 * u.mas / u.yr) is None  # 1,6″ < 2″
    note = high_proper_motion(125 * u.mas / u.yr, 0 * u.mas / u.yr)  # 2,0″
    assert note[0] == "SED_HIGH_PROPER_MOTION" and note.params["shift"]["value"] == pytest.approx(2.0)
    assert high_proper_motion(None, None) is None


# =============================================================================
# T9 — tabella dei punti zero


def test_t9_zero_point_table():
    assert set(ZERO_POINTS) == {"Gaia DR3 G", "Gaia DR3 BP", "Gaia DR3 RP", "2MASS J", "2MASS H", "2MASS Ks",
                                "WISE W1", "WISE W2", "WISE W3", "WISE W4"}
    for zp in ZERO_POINTS.values():
        assert zp.source and zp.reference and zp.verified == "2026-11-07"
        assert zp.error.value > 0 and zp.wavelength.unit == u.um
    assert ZERO_POINTS["Gaia DR3 G"].value == 25.8010446445 * u.mag
    assert ZERO_POINTS["WISE W1"].error == 4.582 * u.Jy
    assert ZERO_POINTS["Gaia DR3 BP"].wavelength_kind == "pivot"


# =============================================================================
# T10 — grafico e tabella


def test_t10_plot_and_table():
    pts = (sed_points_from(gaia_row(), "gaia_dr3", provenance=PROV)
           + sed_points_from(tmass_row(4.655, 0.296, 4.234, 0.268, 3.911, 0.021, ph_qual="DDA"), "2mass",
                             provenance=PROV))
    sed = build_sed(pts)
    png = sed_png(sed, title="51 Peg")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    import matplotlib.image as mpimg

    assert mpimg.imread(io.BytesIO(png)).shape[2] in (3, 4)
    assert isinstance(sed_png(sed, quantity="lambda_flambda", encoded=True), str)
    with pytest.raises(ValueError):
        sed_png(sed, quantity="nulla")
    table = sed_table(sed)
    assert len(table) == 6 and table["flux"].unit == u.Jy
    assert list(table["in_plot"]) == [True, True, True, False, False, True]
    assert sed_table(Sed(())).colnames == table.colnames
