# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Fotometria, parte SED (livello 2): punti da cataloghi, conversione magnitudine → flusso, grafico.

Specifica: ``mdfiles/20-analisi-fotometria.md`` (stato ``approvato`` per la sola parte SED), §3 e §7.

Una magnitudine diventa flusso **solo** con un punto zero di ``ZERO_POINTS`` (fonti ufficiali verificate il
2026-11-07, §3.2); tutto il resto resta in magnitudini, nella tabella e fuori dal grafico. I punti della SED di VizieR
sono mostrati così come li dà VizieR, in una serie separata (D20-5). Nessun numero nasce fuori da queste formule
(regola d'oro n. 1); calcoli in ``float64`` con ``astropy.units`` (DC6).

Il modulo non dipende dal ``25``: riceve le tabelle già scelte e la provenienza come mappa JSON del chiamante.
"""

from __future__ import annotations

import base64
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

import astropy.units as u
import numpy as np
from astropy.table import Table

from astrotwo.core.coordinates_wcs import ModuleWarning

__all__ = [
    "AB_FLUX_ZERO",
    "CATALOG_REFERENCES",
    "CATALOG_SOURCES",
    "VIZIER_SED_RADIUS",
    "ZERO_POINTS",
    "Sed",
    "SedPoint",
    "VizierSeries",
    "ZeroPoint",
    "build_sed",
    "high_proper_motion",
    "mag_to_flux",
    "plot_sed",
    "sed_png",
    "sed_points_from",
    "sed_table",
]

#: Data della verifica delle costanti sulle fonti ufficiali (20 §3.2).
VERIFIED_ON = "2026-11-07"

#: Densità di flusso a m_AB = 0: 3631 Jy (definizione del sistema AB, Oke & Gunn 1983, ApJ 266, 713).
AB_FLUX_ZERO = 3631.0 * u.Jy
AB_REFERENCE = "1983ApJ...266..713O"

#: Raggio della serie VizieR attorno alla posizione J2000 del bersaglio (D20-5).
VIZIER_SED_RADIUS = 2.0 * u.arcsec
#: Intervallo per l'avviso di moto proprio elevato della serie VizieR: J2000 → J2016 (20 §3.5, D25-14 (5)).
_HIGH_PM_SPAN = 16.0 * u.yr

_GAIA_SOURCE = ("«Gaia (E)DR3 passbands and zero points», file zeropt.dat versione 2 (ESA, "
                "cosmos.esa.int/web/gaia/edr3-passbands; Riello et al. 2021, A&A 649, A3); λ_p: documentazione di "
                "Gaia DR3 §5.4.1, Tabella 5.4")
_TMASS_SOURCE = ("2MASS All-Sky Explanatory Supplement §VI.4a, Tabella 1 (Cohen, Wheaton & Megeath 2003, AJ 126, "
                 "1090)")
_WISE_SOURCE = ("WISE All-Sky Explanatory Supplement §IV.4.h, Tabelle 1 e 9 (Wright et al. 2010; Jarrett et al. "
                "2011, ApJ 735, 112); valida per AllWISE (AllWISE Explanatory Supplement §V.3.e)")


@dataclass(frozen=True)
class ZeroPoint:
    """Punto zero di una banda (20 §3.2): unica fonte delle conversioni.

    ``kind``: ``ab_count_rate`` (Gaia: m_AB = −2,5 log₁₀ F_e + ZP_AB, F_e in e⁻/s) oppure ``vega_flux`` (2MASS, WISE:
    Fν = Fν(0) · 10^(−0,4 m)). ``value``/``error``: ZP_AB in mag oppure Fν(0) in Jy."""

    key: str
    catalog: str
    band: str
    system: str
    kind: str
    value: u.Quantity
    error: u.Quantity
    wavelength: u.Quantity
    wavelength_error: u.Quantity | None
    wavelength_kind: str  # pivot | isophotal
    source: str
    reference: str
    verified: str = VERIFIED_ON

    def as_dict(self) -> dict:
        def qj(q):
            return None if q is None else {"value": float(q.value), "unit": q.unit.to_string()}

        return {"key": self.key, "catalog": self.catalog, "band": self.band, "system": self.system,
                "kind": self.kind, "value": qj(self.value), "error": qj(self.error),
                "wavelength": qj(self.wavelength), "wavelength_error": qj(self.wavelength_error),
                "wavelength_kind": self.wavelength_kind, "source": self.source, "reference": self.reference,
                "verified": self.verified}


def _gaia(band: str, zp: float, err: float, lam_nm: float) -> ZeroPoint:
    return ZeroPoint(f"Gaia DR3 {band}", "Gaia DR3", band, "AB", "ab_count_rate", zp * u.mag, err * u.mag,
                     (lam_nm * u.nm).to(u.um), None, "pivot", _GAIA_SOURCE, "2021A&A...649A...3R")


def _vega(catalog: str, band: str, f0: float, f0_err: float, lam: float, lam_err: float, source: str,
          reference: str) -> ZeroPoint:
    return ZeroPoint(f"{catalog} {band}", catalog, band, "Vega", "vega_flux", f0 * u.Jy, f0_err * u.Jy, lam * u.um,
                     lam_err * u.um, "isophotal", source, reference)


#: Tabella dei punti zero (20 §3.2), verificata il 2026-11-07 sulle fonti ufficiali; si cambia solo aggiornando
#: prima la specifica (20 §9).
ZERO_POINTS: dict[str, ZeroPoint] = {zp.key: zp for zp in (
    _gaia("G", 25.8010446445, 0.0027590522, 621.79),
    _gaia("BP", 25.3539555559, 0.0023065687, 510.97),
    _gaia("RP", 25.1039837393, 0.0015800349, 776.91),
    _vega("2MASS", "J", 1594.0, 27.8, 1.235, 0.006, _TMASS_SOURCE, "2003AJ....126.1090C"),
    _vega("2MASS", "H", 1024.0, 20.0, 1.662, 0.009, _TMASS_SOURCE, "2003AJ....126.1090C"),
    _vega("2MASS", "Ks", 666.7, 12.6, 2.159, 0.011, _TMASS_SOURCE, "2003AJ....126.1090C"),
    _vega("WISE", "W1", 309.540, 4.582, 3.3526, 0.0132, _WISE_SOURCE, "2011ApJ...735..112J"),
    _vega("WISE", "W2", 171.787, 2.516, 4.6028, 0.0168, _WISE_SOURCE, "2011ApJ...735..112J"),
    _vega("WISE", "W3", 31.674, 0.450, 11.5608, 0.0446, _WISE_SOURCE, "2011ApJ...735..112J"),
    _vega("WISE", "W4", 8.363, 0.124, 22.0883, 0.1184, _WISE_SOURCE, "2011ApJ...735..112J"),
)}

#: Cataloghi interrogati direttamente: nome, tabella, riferimento bibliografico del catalogo.
CATALOG_SOURCES: dict[str, dict] = {
    "gaia_dr3": {"catalog": "Gaia DR3", "table": "gaiadr3.gaia_source", "reference": "2023A&A...674A...1G"},
    "2mass": {"catalog": "2MASS", "table": "fp_psc", "reference": "2006AJ....131.1163S"},
    "allwise": {"catalog": "AllWISE", "table": "allwise_p3as_psd", "reference": "2014yCat.2328....0C"},
    "simbad": {"catalog": "SIMBAD", "table": "flux", "reference": None},
}

#: Riferimenti SIMBAD che sono lo stesso dato di un catalogo interrogato direttamente (20 §3.3, D20-6, D20-9 (2)):
#: bibcode → (catalogo, {banda SIMBAD → banda del catalogo}). Visti nelle risposte SIMBAD del 2026-11-07.
CATALOG_REFERENCES: dict[str, tuple[str, dict[str, str]]] = {
    "2022yCat.1355....0G": ("Gaia DR3", {"G": "G"}),  # VizieR I/355 (Gaia DR3)
    "2020yCat.1350....0G": ("Gaia DR3", {"G": "G"}),  # VizieR I/350 (Gaia EDR3, stessa fotometria di DR3)
    "2003yCat.2246....0C": ("2MASS", {"J": "J", "H": "H", "K": "Ks"}),  # VizieR II/246
}

_GAIA_BANDS = ("G", "BP", "RP")
_TMASS_BANDS = (("J", "j_m", "j_msigcom"), ("H", "h_m", "h_msigcom"), ("Ks", "k_m", "k_msigcom"))
_WISE_BANDS = tuple((f"W{k}", f"w{k}mpro", f"w{k}sigmpro") for k in range(1, 5))
_GOOD_QUALITY = ("A", "B", "C")
_LN10 = float(np.log(10.0))


# --------------------------------------------------------------------------
# Punti (20 §3.1)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SedPoint:
    """Una misura di una banda per un oggetto (20 §3.1), con la sua provenienza e, se convertita, Fν in Jy.

    ``magnitude``: come data dal catalogo (Gaia: ``phot_*_mean_mag`` in VEGAMAG; 2MASS, AllWISE, SIMBAD). Gaia ha
    anche ``count_rate`` (``phot_*_mean_flux`` in e⁻/s), da cui si converte (D20-1). ``notes``: motivi (codici del
    20 §10) che spiegano perché il punto non è convertito o non entra nel grafico."""

    catalog: str
    table: str | None
    band: str
    zero_point_key: str | None
    system: str | None
    magnitude: u.Quantity | None
    magnitude_error: u.Quantity | None
    provenance: Mapping[str, object]
    identifier: str | None = None
    match: str | None = None
    count_rate: u.Quantity | None = None
    count_rate_error: u.Quantity | None = None
    quality: str | None = None
    flags: Mapping[str, object] = field(default_factory=dict)
    epoch: str | None = None
    reference: str | None = None
    upper_limit: bool = False
    flux: u.Quantity | None = None
    flux_error: u.Quantity | None = None
    wavelength: u.Quantity | None = None
    conversion: Mapping[str, object] | None = None
    notes: tuple[ModuleWarning, ...] = ()
    in_plot: bool = False
    duplicate_of: str | None = None

    @property
    def label(self) -> str:
        return f"{self.catalog} {self.band}"

    def codes(self) -> list[str]:
        return [n[0] for n in self.notes]

    def as_dict(self) -> dict:
        def qj(q):
            return None if q is None else {"value": float(q.value), "unit": q.unit.to_string()}

        return {"catalog": self.catalog, "table": self.table, "band": self.band, "label": self.label,
                "zero_point": self.zero_point_key, "system": self.system, "magnitude": qj(self.magnitude),
                "magnitude_error": qj(self.magnitude_error), "count_rate": qj(self.count_rate),
                "count_rate_error": qj(self.count_rate_error), "quality": self.quality,
                "flags": {k: _plain(v) for k, v in self.flags.items()}, "epoch": self.epoch,
                "reference": self.reference, "upper_limit": self.upper_limit, "identifier": self.identifier,
                "match": self.match, "flux": qj(self.flux), "flux_error": qj(self.flux_error),
                "wavelength": qj(self.wavelength), "conversion": None if self.conversion is None
                else dict(self.conversion), "in_plot": self.in_plot, "duplicate_of": self.duplicate_of,
                "notes": [{"code": n[0], "text": n[1], "params": dict(n.params)} for n in self.notes],
                "provenance": dict(self.provenance)}


def _plain(value):
    if isinstance(value, u.Quantity):
        return {"value": float(value.value), "unit": value.unit.to_string()}
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def _cell(row, name: str):
    """Cella senza badare a maiuscole: ``None`` se vuota; ``Quantity`` con l'unità dichiarata; float32 al decimale
    scritto dal servizio (come il 14), poi ``float64``."""
    col = next((c for c in row.colnames if c.lower() == name.lower()), None)
    if col is None:
        return None
    value = row[col]
    if np.ma.is_masked(value):
        return None
    unit = row.table[col].unit if hasattr(row, "table") else None
    if isinstance(value, (bytes, str, np.str_, np.bytes_)):
        text = value.decode() if isinstance(value, bytes) else str(value)
        return text.strip() or None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)) and unit is None:
        return int(value)
    number = float(str(value)) if isinstance(value, np.float32) else float(value)
    if not np.isfinite(number):
        return None
    return number * unit if unit is not None else number


def _as(value, unit) -> u.Quantity | None:
    """Valore in ``unit``: una ``Quantity`` si converte; un numero senza unità prende quella del catalogo (le colonne
    lette con unità dichiarata arrivano già come ``Quantity``)."""
    if value is None:
        return None
    if isinstance(value, u.Quantity):
        return u.Quantity(value, unit, dtype=np.float64)
    return u.Quantity(float(value), unit, dtype=np.float64)


def _mag(value) -> u.Quantity | None:
    """Magnitudine come ``Quantity`` in ``u.mag`` (l'unità ``mag`` dei VOTable è adimensionale per Astropy)."""
    if value is None:
        return None
    number = float(value.value) if isinstance(value, u.Quantity) else float(value)
    return u.Quantity(number, u.mag, dtype=np.float64)


def _flag_char(text: str | None, index: int) -> str | None:
    if text is None or index >= len(text):
        return None
    return text[index]


def _jdate_text(jdate) -> str | None:
    """Epoca di una misura 2MASS (``jdate``, giorno giuliano ±30 s; scala non dichiarata dal servizio: UTC, 25 §3.11)."""
    if jdate is None:
        return None
    value = float(jdate.to_value(u.d)) if isinstance(jdate, u.Quantity) else float(jdate)
    return f"JD {value!r} (jdate; scala non dichiarata dal servizio, trattata come UTC)"


def sed_points_from(table, catalog: str, *, identifier: str | None = None, match: str | None = None,
                    provenance: Mapping[str, object] | None = None, epoch: str | None = None) -> tuple[SedPoint, ...]:
    """Punti di una tabella nota (20 §3.1): ``gaia_dr3``, ``2mass``, ``allwise`` (tabelle Astropy, una riga per
    sorgente già identificata) o ``simbad`` (sequenza di ``SimbadMagnitude`` del 14). Nessuna conversione qui."""
    if catalog not in CATALOG_SOURCES:
        raise ValueError(f"catalogo {catalog!r} non in {tuple(CATALOG_SOURCES)}")
    meta = CATALOG_SOURCES[catalog]
    prov = dict(provenance or {})
    out: list[SedPoint] = []
    if catalog == "simbad":
        for m in table:
            out.append(SedPoint("SIMBAD", "flux", m.band, None, m.system,
                                _mag(m.value), _mag(m.error), prov, identifier=identifier, match=match,
                                quality=m.quality, reference=m.bibcode,
                                flags={"description": m.description} if m.description else {}))
        return tuple(out)
    for row in table:
        if catalog == "gaia_dr3":
            flags = {k: _cell(row, k) for k in ("phot_variable_flag", "phot_bp_rp_excess_factor")}
            for band in _GAIA_BANDS:
                b = band.lower()
                mag, rate = _cell(row, f"phot_{b}_mean_mag"), _cell(row, f"phot_{b}_mean_flux")
                if mag is None and rate is None:
                    continue
                out.append(SedPoint("Gaia DR3", meta["table"], band, f"Gaia DR3 {band}", "Vega", _mag(mag), None,
                                    prov, identifier=identifier, match=match,
                                    count_rate=_as(rate, u.electron / u.s),
                                    count_rate_error=_as(_cell(row, f"phot_{b}_mean_flux_error"), u.electron / u.s),
                                    flags=flags, epoch=epoch, reference=meta["reference"]))
            continue
        bands = _TMASS_BANDS if catalog == "2mass" else _WISE_BANDS
        key_catalog = "2MASS" if catalog == "2mass" else "WISE"
        ph_qual = _cell(row, "ph_qual")
        if catalog == "2mass":
            rd, cc = _cell(row, "rd_flg"), _cell(row, "cc_flg")
            jdate = _cell(row, "jdate")
        else:
            rd, cc = None, _cell(row, "cc_flags")
            ext = _cell(row, "ext_flg")
        for k, (band, mag_col, err_col) in enumerate(bands):
            mag = _cell(row, mag_col)
            if mag is None:
                continue
            quality = _flag_char(ph_qual, k)
            if catalog == "2mass":
                flags = {"ph_qual": ph_qual, "rd_flg": _flag_char(rd, k), "cc_flg": _flag_char(cc, k)}
                point_epoch = epoch if epoch is not None else _jdate_text(jdate)
            else:
                flags = {"ph_qual": ph_qual, "cc_flags": _flag_char(cc, k), "ext_flg": ext}
                point_epoch = epoch
            out.append(SedPoint(meta["catalog"], meta["table"], band, f"{key_catalog} {band}", "Vega", _mag(mag),
                                _mag(_cell(row, err_col)), prov, identifier=identifier, match=match,
                                quality=quality, flags=flags, epoch=point_epoch, reference=meta["reference"],
                                upper_limit=quality == "U"))
    return tuple(out)


# --------------------------------------------------------------------------
# Conversione (20 §3.2)
# --------------------------------------------------------------------------


def _note(code: str, text: str, **params) -> ModuleWarning:
    return ModuleWarning(code, text, params)


def mag_to_flux(point: SedPoint) -> SedPoint:
    """Fν ed errore con il punto zero e la formula di 20 §3.2, oppure il punto con il motivo per cui non si
    converte (``SED_NO_ZERO_POINT``, ``SED_NO_SYSTEM``). Calcoli in ``float64`` con Astropy (DC6)."""
    zp = ZERO_POINTS.get(point.zero_point_key) if point.zero_point_key else None
    if zp is None:
        if point.system is None:
            note = _note("SED_NO_SYSTEM", f"{point.label}: sistema non dichiarato, resta in magnitudini",
                         catalog=point.catalog, band=point.band)
        else:
            note = _note("SED_NO_ZERO_POINT", f"{point.label}: nessun punto zero ufficiale in tabella, resta in "
                         "magnitudini", catalog=point.catalog, band=point.band)
        return replace(point, notes=point.notes + (note,))
    if zp.kind == "ab_count_rate":
        if point.count_rate is None or point.count_rate.value <= 0:
            note = _note("SED_NO_ZERO_POINT", f"{point.label}: flusso in e⁻/s assente, resta in magnitudini",
                         catalog=point.catalog, band=point.band)
            return replace(point, notes=point.notes + (note,))
        rate = float(point.count_rate.to_value(u.electron / u.s))
        m_ab = -2.5 * np.log10(rate) + float(zp.value.to_value(u.mag))
        flux = (AB_FLUX_ZERO * 10.0 ** (-0.4 * m_ab)).to(u.Jy)
        sigma_zp = float(zp.error.to_value(u.mag))
        if point.count_rate_error is not None:
            sigma_m = 2.5 / _LN10 * float(point.count_rate_error.to_value(u.electron / u.s)) / rate
            error = flux * 0.4 * _LN10 * np.sqrt(sigma_m ** 2 + sigma_zp ** 2)
        else:
            sigma_m, error = None, None
        conversion = {"formula": "m_AB = -2.5 log10(F_e) + ZP_AB; F_nu = 3631 Jy * 10**(-0.4 m_AB); "
                                 "sigma_F = F_nu * 0.4 ln(10) * sqrt(sigma_m**2 + sigma_ZP**2), "
                                 "sigma_m = 2.5/ln(10) * sigma_Fe/F_e",
                      "zero_point": zp.as_dict(), "m_ab": {"value": float(m_ab), "unit": "mag"},
                      "m_ab_error": None if sigma_m is None else {"value": float(sigma_m), "unit": "mag"},
                      "ab_flux_zero": {"value": float(AB_FLUX_ZERO.value), "unit": "Jy",
                                       "reference": AB_REFERENCE}}
    else:
        if point.magnitude is None:
            return replace(point, notes=point.notes + (_note("SED_NO_ZERO_POINT", f"{point.label}: magnitudine "
                                                             "assente", catalog=point.catalog, band=point.band),))
        m = float(point.magnitude.to_value(u.mag))
        f0 = zp.value.to(u.Jy)
        flux = (f0 * 10.0 ** (-0.4 * m)).to(u.Jy)
        if point.magnitude_error is not None:
            sigma_m = float(point.magnitude_error.to_value(u.mag))
            rel_f0 = float((zp.error / zp.value).decompose().value)
            error = flux * np.sqrt((0.4 * _LN10 * sigma_m) ** 2 + rel_f0 ** 2)
        else:
            error = None
        conversion = {"formula": "F_nu = F_nu(0) * 10**(-0.4 m); sigma_F = F_nu * sqrt((0.4 ln(10) sigma_m)**2 + "
                                 "(sigma_F0/F0)**2)", "zero_point": zp.as_dict()}
    notes = point.notes
    if error is None:
        notes += (_note("SED_NO_ERROR", f"{point.label}: senza errore, punto senza barra",
                        catalog=point.catalog, band=point.band),)
    return replace(point, flux=flux, flux_error=None if error is None else error.to(u.Jy),
                   wavelength=zp.wavelength, conversion=conversion, notes=notes)


# --------------------------------------------------------------------------
# SED (20 §3.3, §3.5)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class VizierSeries:
    """Serie della SED di VizieR così come data dal servizio (D20-5): nessuna conversione né fusione."""

    table: Table
    provenance: Mapping[str, object]

    def rows(self) -> list[dict]:
        out = []
        for row in self.table:
            freq, flux, err = _cell(row, "_sed_freq"), _cell(row, "_sed_flux"), _cell(row, "_sed_eflux")
            item = {"frequency": _plain(_as(freq, u.GHz)), "flux": _plain(_as(flux, u.Jy)),
                    "flux_error": _plain(_as(err, u.Jy)), "filter": _cell(row, "_sed_filter"),
                    "catalog": _cell(row, "_tabname")}
            item["wavelength"] = (None if freq is None else
                                  _plain(_as(freq, u.GHz).to(u.um, equivalencies=u.spectral())))
            out.append(item)
        return out


@dataclass(frozen=True)
class Sed:
    """SED: punti con conversioni, qualità e duplicati marcati, più la serie VizieR separata (o ``None``)."""

    points: tuple[SedPoint, ...]
    vizier: VizierSeries | None = None

    @property
    def plotted(self) -> tuple[SedPoint, ...]:
        return tuple(p for p in self.points if p.in_plot)

    def zero_points(self) -> list[dict]:
        keys = sorted({p.zero_point_key for p in self.points if p.conversion is not None})
        return [ZERO_POINTS[k].as_dict() for k in keys]

    def as_dict(self) -> dict:
        return {"points": [p.as_dict() for p in self.points],
                "vizier": None if self.vizier is None else {"rows": self.vizier.rows(),
                                                            "provenance": dict(self.vizier.provenance)},
                "zero_points": self.zero_points()}


def _quality_notes(point: SedPoint) -> tuple[ModuleWarning, ...]:
    if point.catalog not in ("2MASS", "AllWISE") or point.quality in _GOOD_QUALITY:
        return ()
    if point.quality == "U":
        return (_note("SED_UPPER_LIMIT", f"{point.label}: limite superiore (ph_qual U), fuori dal grafico",
                      catalog=point.catalog, band=point.band),)
    return (_note("SED_LOW_QUALITY", f"{point.label}: qualità {point.quality} (ph_qual), fuori dal grafico",
                  catalog=point.catalog, band=point.band, quality=point.quality or ""),)


def build_sed(points: Sequence[SedPoint], vizier: VizierSeries | None = None) -> Sed:
    """Converte i punti con un punto zero, marca qualità e duplicati, decide chi entra nel grafico (20 §3.3).

    Nel grafico: punti convertiti dei cataloghi interrogati direttamente con qualità A/B/C (Gaia: sempre). SIMBAD
    resta in tabella (D20-6); un suo valore con lo stesso riferimento di un punto del catalogo presente è marcato
    ``SED_DUPLICATE``."""
    converted = []
    for point in points:
        point = replace(point, notes=point.notes + _quality_notes(point))
        point = mag_to_flux(point)
        converted.append(point)
    present = {(p.catalog, p.band) for p in converted if p.catalog != "SIMBAD"}
    out = []
    for point in converted:
        if point.catalog == "SIMBAD":
            ref = CATALOG_REFERENCES.get(point.reference or "")
            target = None if ref is None else (ref[0], ref[1].get(point.band))
            if target is not None and target[1] is not None and target in present:
                label = f"{target[0]} {target[1]}"
                point = replace(point, duplicate_of=label, notes=point.notes + (_note(
                    "SED_DUPLICATE", f"SIMBAD {point.band} ({point.reference}): stesso dato di {label}, una sola "
                    "volta nel grafico", band=point.band, reference=point.reference or "", duplicate_of=label),))
            out.append(replace(point, in_plot=False))
            continue
        excluded = any(c in ("SED_UPPER_LIMIT", "SED_LOW_QUALITY") for c in point.codes())
        out.append(replace(point, in_plot=point.flux is not None and not excluded))
    return Sed(tuple(out), vizier)


def high_proper_motion(pm_ra_cosdec: u.Quantity | None, pm_dec: u.Quantity | None,
                       radius: u.Quantity = VIZIER_SED_RADIUS) -> ModuleWarning | None:
    """``SED_HIGH_PROPER_MOTION`` se |μ| · 16 anni (J2000 → J2016) ≥ raggio della serie VizieR (20 §3.5)."""
    if pm_ra_cosdec is None or pm_dec is None:
        return None
    total = np.hypot(pm_ra_cosdec.to(u.mas / u.yr), pm_dec.to(u.mas / u.yr))
    shift = (total * _HIGH_PM_SPAN).to(u.arcsec)
    if shift < radius:
        return None
    return ModuleWarning("SED_HIGH_PROPER_MOTION", f"moto proprio {float(total.value)!r} mas/yr: in 16 anni la "
                         f"posizione si sposta di {float(shift.value)!r} arcsec, oltre il raggio della serie VizieR",
                         {"proper_motion": {"value": float(total.value), "unit": "mas / yr"},
                          "shift": {"value": float(shift.value), "unit": "arcsec"},
                          "radius": {"value": float(radius.to_value(u.arcsec)), "unit": "arcsec"}})


# --------------------------------------------------------------------------
# Tabella e grafico (20 §3.4, §6)
# --------------------------------------------------------------------------


def sed_table(sed: Sed) -> Table:
    """Una riga per punto con provenienza (20 §6): magnitudine, Fν, λ, qualità, motivi, fonte."""
    names = ("catalog", "band", "system", "magnitude", "magnitude_error", "flux", "flux_error", "wavelength",
             "quality", "in_plot", "duplicate_of", "reasons", "zero_point", "reference", "identifier", "match",
             "server", "retrieved_at")
    rows = []
    for p in sed.points:
        rows.append((p.catalog, p.band, p.system or "",
                     np.nan if p.magnitude is None else float(p.magnitude.to_value(u.mag)),
                     np.nan if p.magnitude_error is None else float(p.magnitude_error.to_value(u.mag)),
                     np.nan if p.flux is None else float(p.flux.to_value(u.Jy)),
                     np.nan if p.flux_error is None else float(p.flux_error.to_value(u.Jy)),
                     np.nan if p.wavelength is None else float(p.wavelength.to_value(u.um)),
                     p.quality or "", p.in_plot, p.duplicate_of or "", " ".join(p.codes()),
                     p.zero_point_key or "", p.reference or "", p.identifier or "", p.match or "",
                     str(p.provenance.get("server") or ""), str(p.provenance.get("retrieved_at") or "")))
    table = Table(rows=rows or None, names=names, dtype=(str, str, str, float, float, float, float, float, str, bool,
                                                         str, str, str, str, str, str, str, str))
    for name, unit in (("magnitude", u.mag), ("magnitude_error", u.mag), ("flux", u.Jy), ("flux_error", u.Jy),
                       ("wavelength", u.um)):
        table[name].unit = unit
    return table


_COLORS = {"Gaia DR3": "#1f77b4", "2MASS": "#d62728", "AllWISE": "#2ca02c"}  # colori per catalogo (D20-7)


def plot_sed(sed: Sed, *, quantity: str = "fnu", title: str | None = None):
    """Grafico della SED (20 §3.4, D20-7): Fν (Jy) contro λ (µm), scale logaritmiche, barre d'errore, colori per
    catalogo, serie VizieR distinta; ``quantity="lambda_flambda"`` per λFλ (W/m²). Solo i punti ``in_plot``.
    Figura matplotlib senza pyplot (incorporabile in Qt dal 43)."""
    from matplotlib.figure import Figure

    if quantity not in ("fnu", "lambda_flambda"):
        raise ValueError("quantity deve essere 'fnu' o 'lambda_flambda'")

    def y(flux: u.Quantity, lam: u.Quantity) -> float:
        if quantity == "fnu":
            return float(flux.to_value(u.Jy))
        return float((flux * lam.to(u.Hz, equivalencies=u.spectral())).to_value(u.W / u.m ** 2))

    fig = Figure(figsize=(6.4, 4.4), dpi=100)
    ax = fig.add_subplot(1, 1, 1)
    for catalog in ("Gaia DR3", "2MASS", "AllWISE"):
        pts = [p for p in sed.plotted if p.catalog == catalog]
        if not pts:
            continue
        xs = [float(p.wavelength.to_value(u.um)) for p in pts]
        ys = [y(p.flux, p.wavelength) for p in pts]
        errs = [0.0 if p.flux_error is None else y(p.flux_error, p.wavelength) for p in pts]
        ax.errorbar(xs, ys, yerr=errs, fmt="o", color=_COLORS[catalog], label=catalog, capsize=2, ms=5)
    if sed.vizier is not None:
        rows = [r for r in sed.vizier.rows() if r["wavelength"] and r["flux"] and r["flux"]["value"] > 0]
        if rows:
            xs = [r["wavelength"]["value"] for r in rows]
            ys = [y(r["flux"]["value"] * u.Jy, r["wavelength"]["value"] * u.um) for r in rows]
            ax.plot(xs, ys, "x", color="0.45", ms=5, label="VizieR SED (as given by VizieR)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("λ (µm)")
    ax.set_ylabel("Fν (Jy)" if quantity == "fnu" else "λFλ (W m⁻²)")
    if title:
        ax.set_title(title)
    if ax.has_data():
        ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.25)
    fig.text(0.01, 0.01, "Zero points: Gaia (E)DR3 ESA/DPAC, 2MASS Cohen+2003, WISE Jarrett+2011. "
             "Data: ESA Gaia, IPAC/IRSA, CDS.", fontsize=6, color="0.35")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return fig


def sed_png(sed: Sed, *, quantity: str = "fnu", title: str | None = None, encoded: bool = False) -> bytes | str:
    """PNG del grafico (metadati del programma tolti); ``encoded=True`` → testo base64 per il risultato JSON."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = plot_sed(sed, quantity=quantity, title=title)
    FigureCanvasAgg(fig)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", metadata={"Software": None})
    data = buffer.getvalue()
    return base64.b64encode(data).decode("ascii") if encoded else data
