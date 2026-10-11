"""Test del modulo 15 (``mdfiles/15-core-crossmatch.md`` §12).

Tabelle di prova scritte nel test come VOTable e lette con il modulo 13; gli
attesi sono ricalcolati con ``astropy`` e ``numpy``, mai scritti a mano.
"""

from __future__ import annotations

import dataclasses

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import Galactic, SkyCoord, angular_separation

from astrotwo.core.catalogs import read_table
from astrotwo.core.crossmatch import (
    CrossmatchError,
    crossmatch,
    crossmatch_by_field,
    crossmatch_cds,
    crossmatch_ellipses,
    suggest_columns,
)

VOTABLE = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE><COOSYS ID="sys" system="{system}"{epoch}/>
<TABLE>
<FIELD name="{lon}" ucd="{lon_ucd};meta.main" ref="sys" datatype="double" unit="deg"/>
<FIELD name="{lat}" ucd="{lat_ucd};meta.main" ref="sys" datatype="double" unit="deg"/>
<FIELD name="id" datatype="char" arraysize="*"/>
{extra_fields}
<DATA><TABLEDATA>
{rows}
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""


def make_table(path, lon, lat, *, system="ICRS", epoch=None, galactic=False, ids=None, extra=None):
    """Tabella di prova: posizioni (``None`` = valore mancante) e colonne in più ``extra = {nome: (unità, valori)}``."""
    extra = extra or {}
    names = ("GLON", "GLAT") if galactic else ("RA", "DE")
    ucds = ("pos.galactic.lon", "pos.galactic.lat") if galactic else ("pos.eq.ra", "pos.eq.dec")
    ids = ids or [f"s{k}" for k in range(len(lon))]
    fields = "\n".join(f'<FIELD name="{n}" datatype="double"{f" unit={chr(34)}{unit}{chr(34)}" if unit else ""}/>'
                       for n, (unit, _) in extra.items())

    def cell(v):
        return "" if v is None or (isinstance(v, float) and np.isnan(v)) else repr(float(v))

    rows = "\n".join("<TR>" + "".join(f"<TD>{cell(v)}</TD>" for v in (lon[k], lat[k])) + f"<TD>{ids[k]}</TD>"
                     + "".join(f"<TD>{cell(vals[k])}</TD>" for _, vals in extra.values()) + "</TR>"
                     for k in range(len(lon)))
    path.write_text(VOTABLE.format(system=system, epoch=f' epoch="{epoch}"' if epoch else "", lon=names[0],
                                   lat=names[1], lon_ucd=ucds[0], lat_ucd=ucds[1], extra_fields=fields, rows=rows),
                    encoding="utf-8")
    return read_table(path)


def offset(ra, dec, pa_deg, sep_arcsec):
    """Punto a distanza e angolo di posizione dati (astropy), per costruire coppie note."""
    p = SkyCoord(ra * u.deg, dec * u.deg).directional_offset_by(pa_deg * u.deg, sep_arcsec * u.arcsec)
    return float(p.ra.deg), float(p.dec.deg)


# =============================================================================
# P1 — Incrocio locale (T1–T3, T5–T8, T14–T17, T19)
# =============================================================================


def test_t1_t2_known_pair_and_threshold(tmp_path):
    rb, db = offset(150.0, 2.0, 30.0, 5.0)
    a = make_table(tmp_path / "a.xml", [150.0], [2.0])
    b = make_table(tmp_path / "b.xml", [rb], [db])
    result = crossmatch(a, b, "best", 10 * u.arcsec)
    expected = angular_separation(150.0 * u.deg, 2.0 * u.deg, rb * u.deg, db * u.deg).to_value(u.arcsec)
    assert len(result.pairs) == 1 and list(result.pairs["idx_a"]) == [0] and list(result.pairs["idx_b"]) == [0]
    assert result.pairs["sep"].unit == u.arcsec
    assert result.pairs["sep"][0] == pytest.approx(expected, abs=1e-9) and expected == pytest.approx(5.0, abs=1e-6)
    none = crossmatch(a, b, "best", 1 * u.arcsec)
    assert len(none.pairs) == 0 and "NO_MATCH" in dict(none.warnings)


def test_t3_mode_none(tmp_path):
    ra = 10.0 + 0.01 * np.arange(10)
    a = make_table(tmp_path / "a.xml", ra, np.zeros(10))
    b = make_table(tmp_path / "b.xml", ra[[1, 4, 7]], np.zeros(3))
    result = crossmatch(a, b, "none", 1 * u.arcsec)
    expected = np.setdiff1d(np.arange(10), [1, 4, 7])  # ricalcolo con numpy
    assert np.array_equal(result.unmatched, expected) and len(result.pairs) == 0
    assert result.report.unmatched == 7


def test_mode_all_order(tmp_path):
    rb1, db1 = offset(20.0, 5.0, 0.0, 3.0)
    rb2, db2 = offset(20.0, 5.0, 90.0, 1.0)
    a = make_table(tmp_path / "a.xml", [20.0], [5.0])
    b = make_table(tmp_path / "b.xml", [rb1, rb2], [db1, db2])
    result = crossmatch(a, b, "all", 5 * u.arcsec)
    assert list(result.pairs["idx_b"]) == [1, 0]  # ordine per separazione
    seps = [angular_separation(20 * u.deg, 5 * u.deg, r * u.deg, d * u.deg).to_value(u.arcsec)
            for r, d in ((rb2, db2), (rb1, db1))]
    assert np.allclose(result.pairs["sep"], seps, atol=1e-9)


def test_t5_different_frames(tmp_path):
    rng = np.random.default_rng(1)
    ra, dec = 30 + rng.random(20), -10 + rng.random(20)
    shifted = [offset(r, d, 45.0, 0.5) for r, d in zip(ra, dec)]
    a = make_table(tmp_path / "a.xml", ra, dec)
    gal = SkyCoord([s[0] for s in shifted] * u.deg, [s[1] for s in shifted] * u.deg).transform_to(Galactic())
    b = make_table(tmp_path / "b.xml", gal.l.deg, gal.b.deg, system="galactic", galactic=True)
    result = crossmatch(a, b, "best", 2 * u.arcsec)
    # Ricalcolo: entrambe in ICRS convertite nel test con astropy.
    manual = SkyCoord(ra * u.deg, dec * u.deg).separation(gal.transform_to("icrs")).to_value(u.arcsec)
    assert list(result.pairs["idx_a"]) == list(range(20)) and list(result.pairs["idx_b"]) == list(range(20))
    assert np.allclose(result.pairs["sep"], manual, atol=1e-6)
    assert result.report.systems == ("icrs", "galactic")


def test_t6_report(tmp_path):
    a = make_table(tmp_path / "a.xml", [1.0], [1.0], epoch="J2000")
    b = make_table(tmp_path / "b.xml", [1.0], [1.0], epoch="J2000")
    report = crossmatch(a, b, "best", 2 * u.arcsec).report
    assert report.mode == "best" and "2.0 arcsec" in report.criterion and report.frame == "icrs"
    assert "search_around_sky" in report.method and report.epochs == ("J2000", "J2000")
    assert report.as_dict()["created_at"].endswith("Z") and report.origins == (a.origin, b.origin)
    text = report.describe()
    assert "Modalità: best" in text and "nessuna propagazione automatica" in text


def test_t7_t8_body(tmp_path):
    a = make_table(tmp_path / "a.xml", [1.0], [1.0])
    mars = dataclasses.replace(make_table(tmp_path / "m.xml", [1.0], [1.0]), body="Mars")  # dati di prova
    with pytest.raises(CrossmatchError) as err:
        crossmatch(a, mars, "best", 2 * u.arcsec)
    assert err.value.code == "BODY_MISMATCH"
    forced = crossmatch(a, mars, "best", 2 * u.arcsec, force_body=True)
    assert len(forced.pairs) == 1 and forced.report.forced_body and "BODY_FORCED" in dict(forced.warnings)
    assert "FORZATO" in forced.report.describe() and "Mars" in forced.report.describe()
    with pytest.raises(CrossmatchError) as err:
        crossmatch(a, dataclasses.replace(a, body=None), "best", 2 * u.arcsec)
    assert err.value.code == "BODY_UNKNOWN"


def test_t14_max_sep_required(tmp_path):
    a = make_table(tmp_path / "a.xml", [1.0], [1.0])
    for bad in (None, 2, 2 * u.m, 0 * u.arcsec, -1 * u.arcsec, 181 * u.deg, [1, 2] * u.arcsec):
        with pytest.raises(CrossmatchError) as err:
            crossmatch(a, a, "best", bad)
        assert err.value.code == "MAX_SEP_INVALID"
    assert len(crossmatch(a, a, "all", 180 * u.deg).pairs) == 1  # 180° ammesso


def test_t15_epochs_differ(tmp_path):
    a = make_table(tmp_path / "a.xml", [1.0], [1.0], epoch="J2016")
    b = make_table(tmp_path / "b.xml", [1.0], [1.0], epoch="J2000")
    result = crossmatch(a, b, "best", 1 * u.arcsec)
    assert "EPOCH_DIFFERS" in dict(result.warnings) and result.report.epochs == ("J2016", "J2000")
    assert result.pairs["sep"][0] == 0.0  # posizioni non propagate


def test_t16_best_ties_and_reuse(tmp_path):
    left, right = offset(40.0, 0.0, 270.0, 2.0), offset(40.0, 0.0, 90.0, 2.0)
    a = make_table(tmp_path / "a.xml", [40.0], [0.0])
    b = make_table(tmp_path / "b.xml", [right[0], left[0]], [right[1], left[1]])
    seps = angular_separation(40 * u.deg, 0 * u.deg, [right[0], left[0]] * u.deg, [right[1], left[1]] * u.deg)
    if seps[0] != seps[1]:  # pari merito esatto in float64: rendo le due righe identiche per costruzione
        b = make_table(tmp_path / "b.xml", [right[0], right[0]], [right[1], right[1]])
    result = crossmatch(a, b, "best", 5 * u.arcsec)
    assert list(result.pairs["idx_b"]) == [0] and "BEST_TIE" in dict(result.warnings)
    # Una riga di B più vicina a due righe di A: la stessa riga di B per entrambe.
    two = make_table(tmp_path / "a2.xml", [40.0, offset(40.0, 0.0, 0.0, 1.0)[0]], [0.0, offset(40.0, 0.0, 0.0, 1.0)[1]])
    single = make_table(tmp_path / "b2.xml", [40.0], [0.0])
    reused = crossmatch(two, single, "best", 5 * u.arcsec)
    assert list(reused.pairs["idx_b"]) == [0, 0] and reused.report.b_reused == 1 and "B_REUSED" in dict(reused.warnings)


def test_t17_missing_coordinates(tmp_path):
    a = make_table(tmp_path / "a.xml", [1.0, None, 3.0, float("nan")], [1.0, 2.0, None, 4.0])
    b = make_table(tmp_path / "b.xml", [1.0, None], [1.0, 5.0])
    result = crossmatch(a, b, "none", 1 * u.arcsec)
    assert result.report.excluded == (3, 1) and "COORD_MISSING" in dict(result.warnings)
    assert list(result.unmatched) == []  # le righe senza posizione non sono "non appaiate"
    best = crossmatch(a, b, "best", 1 * u.arcsec)
    assert list(best.pairs["idx_a"]) == [0] and list(best.pairs["idx_b"]) == [0]


def test_t19_rematch(tmp_path):
    rng = np.random.default_rng(3)
    ra, dec = 100 + 0.01 * rng.random(50), 0.01 * rng.random(50)
    a = make_table(tmp_path / "a.xml", ra, dec)
    b = make_table(tmp_path / "b.xml", ra + 1e-4 * rng.standard_normal(50), dec)
    first = crossmatch(a, b, "all", 20 * u.arcsec)
    again = first.rematch(max_sep=0.2 * u.arcsec)
    fresh = crossmatch(a, b, "all", 0.2 * u.arcsec)
    assert again.report.criterion == fresh.report.criterion
    for name in ("idx_a", "idx_b", "sep"):
        assert np.array_equal(again.pairs[name], fresh.pairs[name])


def test_errors_positions(tmp_path):
    from astrotwo.core.catalogs import TableLimits

    a = make_table(tmp_path / "a.xml", [1.0], [1.0])
    with pytest.raises(CrossmatchError) as err:
        crossmatch(a, dataclasses.replace(a, positions=None), "best", 1 * u.arcsec)
    assert err.value.code == "NO_COORD_COLUMNS"
    unknown = dataclasses.replace(a, positions=dataclasses.replace(a.positions, frame=None))
    with pytest.raises(CrossmatchError) as err:
        crossmatch(a, unknown, "best", 1 * u.arcsec)
    assert err.value.code == "FRAME_UNKNOWN"
    big = dataclasses.replace(make_table(tmp_path / "c.xml", [1.0, 2.0], [1.0, 2.0]), limits=TableLimits(max_rows=1))
    with pytest.raises(CrossmatchError) as err:
        crossmatch(big, a, "best", 1 * u.arcsec)
    assert err.value.code == "TABLE_TOO_LARGE"
    with pytest.raises(ValueError):
        crossmatch(a, a, "migliore", 1 * u.arcsec)
    assert a.table["RA"][0] == 1.0  # tabelle invariate


# =============================================================================
# P2 — Tabella unita e colonne proposte dagli UCD (T13, T18)
# =============================================================================


def test_t13_suffixes_and_ucd(tmp_path):
    a = make_table(tmp_path / "a.xml", [10.0, 11.0], [0.0, 0.0], extra={"mag": ("mag", [1.0, 2.0])})
    b = make_table(tmp_path / "b.xml", [10.0, 12.0], [0.0, 0.0], extra={"mag": ("mag", [5.0, 6.0])})
    result = crossmatch(a, b, "best", 1 * u.arcsec)
    t = result.joined()
    assert t.colnames == ["RA_tab1", "DE_tab1", "id_tab1", "mag_tab1", "RA_tab2", "DE_tab2", "id_tab2", "mag_tab2",
                          "xmatch_sep"]
    assert "COLUMNS_RENAMED" in dict(t.warnings) and "A.mag → mag_tab1" in dict(t.warnings)["COLUMNS_RENAMED"]
    assert list(t.table["mag_tab2"]) == [5.0] and t.table["mag_tab2"].unit == u.mag
    assert t.table["xmatch_sep"].unit == u.arcsec and any("rinomina A.RA → RA_tab1" in h for h in t.history)
    # Posizioni proposte dagli UCD e conflitto meta.main.
    sug = suggest_columns(a, b)
    assert (sug.positions[0].lon, sug.positions[1].lat) == ("RA", "DE") and sug.kind == "suggestion"
    assert sug.conflicts == ("pos.eq.dec;meta.main", "pos.eq.ra;meta.main")
    assert "UCD_CONFLICT" in dict(t.warnings) and "MAIN_UCD_REMOVED" in dict(t.warnings)
    assert "meta.main" not in t.table["RA_tab2"].meta["ucd"] and "meta.main" in t.table["RA_tab1"].meta["ucd"]
    assert (t.positions.lon, t.positions.lat, t.positions.frame) == ("RA_tab1", "DE_tab1", "icrs")
    assert "meta.main" in b.table["RA"].meta["ucd"]  # tabella d'ingresso invariata


def test_t18_joined_options(tmp_path):
    a = make_table(tmp_path / "a.xml", [10.0, 11.0], [0.0, 0.0])
    b = make_table(tmp_path / "b.xml", [10.0], [0.0], extra={"flux": ("Jy", [3.0])})
    result = crossmatch(a, b, "best", 1 * u.arcsec)
    t = result.joined(keep_columns=(["id"], ["RA", "DE", "flux", "id"]), prefixes=("A_", "B_"), suffixes=("", ""),
                      main="b")
    assert t.colnames == ["A_id", "RA", "DE", "flux", "B_id", "xmatch_sep"]
    assert (t.positions.lon, t.positions.lat) == ("RA", "DE") and t.body == "celestial"
    unmatched = crossmatch(a, b, "none", 1 * u.arcsec).joined()
    assert unmatched.colnames == ["RA", "DE", "id"] and list(unmatched.table["id"]) == ["s1"]
    with pytest.raises(CrossmatchError):
        result.joined(keep_columns=(["nessuna"], None))
    with pytest.raises(CrossmatchError):  # stesso nome anche dopo prefissi e suffissi vuoti
        result.joined(prefixes=("", ""), suffixes=("", ""))
    errors = make_table(tmp_path / "e.xml", [1.0], [1.0], extra={"emaj": ("arcsec", [0.1]), "emin": ("arcsec", [0.05]),
                                                                 "epa": ("deg", [10.0])})
    for col, ucd in (("emaj", "stat.error;phys.size.smajAxis"), ("emin", "stat.error;phys.size.sminAxis"),
                     ("epa", "stat.error;pos.posAng")):
        errors.table[col].meta["ucd"] = ucd
    assert suggest_columns(errors).errors[0] == {"major": ["emaj"], "minor": ["emin"], "angle": ["epa"]}


# =============================================================================
# P3 — Correlazione per campo (T9, T10)
# =============================================================================


def test_t9_by_field(tmp_path):
    from astropy.table import Table, join

    a = make_table(tmp_path / "a.xml", [1.0] * 5, [1.0] * 5, ids=["x1", "x2", "x3", "x4", "x5"])
    b = make_table(tmp_path / "b.xml", [2.0] * 4, [2.0] * 4, ids=["x4", "y1", "x2  ", "x5"])  # spazi finali
    result = crossmatch_by_field(a, b, "id", "id")
    # Ricalcolo con astropy.table.join nel test (testo senza spazi finali).
    left = Table({"k": ["x1", "x2", "x3", "x4", "x5"], "ia": range(5)})
    right = Table({"k": [v.rstrip() for v in ["x4", "y1", "x2  ", "x5"]], "ib": range(4)})
    expected = join(left, right, keys="k")
    expected.sort(["ia", "ib"])
    assert list(result.pairs["idx_a"]) == list(expected["ia"]) and list(result.pairs["idx_b"]) == list(expected["ib"])
    assert len(result.pairs) == 3 and "sep" not in result.pairs.colnames
    none = crossmatch_by_field(a, b, "id", "id", mode="none")
    assert list(none.unmatched) == [0, 2]
    joined = result.joined()
    assert list(joined.table["id_tab1"]) == ["x2", "x4", "x5"] and "xmatch_sep" not in joined.colnames


def test_t10_repeated_and_invalid_keys(tmp_path):
    a = make_table(tmp_path / "a.xml", [1.0] * 3, [1.0] * 3, extra={"n": (None, [7.0, 7.0, None])})
    b = make_table(tmp_path / "b.xml", [1.0] * 3, [1.0] * 3, extra={"n": (None, [7.0, 7.0, 8.0])})
    result = crossmatch_by_field(a, b, "n", "n")
    assert len(result.pairs) == 4 and "4 coppie" in dict(result.warnings)["KEY_REPEATED"]
    assert "KEY_MISSING" in dict(result.warnings) and result.report.excluded == (1, 0)
    with pytest.raises(CrossmatchError) as err:
        crossmatch_by_field(a, b, "id", "n")  # testo contro numero
    assert err.value.code == "KEY_COLUMN_INVALID"
    with pytest.raises(CrossmatchError) as err:
        crossmatch_by_field(a, b, "manca", "n")
    assert err.value.code == "KEY_COLUMN_INVALID"
    with pytest.raises(CrossmatchError) as err:  # corpo: stessa regola di ogni incrocio (§9)
        crossmatch_by_field(a, dataclasses.replace(b, body=None), "n", "n")
    assert err.value.code == "BODY_UNKNOWN"


# =============================================================================
# P4 — Correlazione con ellissi d'errore (T11, T12, T20)
# =============================================================================

ELL = ("emaj", "emin", "epa")


def ellipse_tables(tmp_path, a_rows, b_rows, scale=1.0):
    """Tabelle con posizione ed ellisse: righe (ra, dec, maggiore", minore", PA°); ``scale`` moltiplica gli assi."""
    def build(name, rows):
        return make_table(tmp_path / name, [r[0] for r in rows], [r[1] for r in rows],
                          extra={"emaj": ("arcsec", [scale * r[2] for r in rows]),
                                 "emin": ("arcsec", [scale * r[3] for r in rows]), "epa": ("deg", [r[4] for r in rows])})
    return build("ea.xml", a_rows), build("eb.xml", b_rows)


def mahalanobis(a_row, b_row):
    """Ricalcolo nel test con numpy: Σ = R·diag(a², b²)·Rᵀ per ogni ellisse, Δ dagli offset di astropy."""
    pa, pb = SkyCoord(a_row[0] * u.deg, a_row[1] * u.deg), SkyCoord(b_row[0] * u.deg, b_row[1] * u.deg)
    dx, dy = (x.to_value(u.arcsec) for x in pa.spherical_offsets_to(pb))

    def cov(major, minor, pa_deg):
        t = np.radians(pa_deg)
        rot = np.array([[np.sin(t), np.cos(t)], [np.cos(t), -np.sin(t)]])  # colonne: asse maggiore, asse minore
        return rot @ np.diag([major ** 2, minor ** 2]) @ rot.T

    total = cov(*a_row[2:]) + cov(*b_row[2:])
    delta = np.array([dx, dy])
    return float(np.sqrt(delta @ np.linalg.solve(total, delta)))


def test_t12_ellipses(tmp_path):
    a_rows = [(50.0, 10.0, 1.0, 0.5, 30.0), (50.01, 10.0, 0.3, 0.3, 0.0)]
    b0 = offset(50.0, 10.0, 30.0, 1.5) + (0.4, 0.2, 100.0)  # lungo l'asse maggiore di A
    b1 = offset(50.0, 10.0, 120.0, 1.5) + (0.4, 0.2, 100.0)  # lungo l'asse minore di A
    b2 = offset(50.01, 10.0, 200.0, 2.0) + (0.2, 0.1, 0.0)
    b_rows = [b0, b1, b2]
    a, b = ellipse_tables(tmp_path, a_rows, b_rows)
    result = crossmatch_ellipses(a, b, ELL, ELL, 3.0, axes="semi", mode="all")
    expected = {(i, j): mahalanobis(a_rows[i], b_rows[j]) for i in range(2) for j in range(3)}
    associated = sorted(pair for pair, d in expected.items() if d <= 3.0)
    got = sorted(zip(result.pairs["idx_a"].tolist(), result.pairs["idx_b"].tolist()))
    assert got == associated and len(got) >= 1
    for row in result.pairs:
        assert row["mahalanobis"] == pytest.approx(expected[(row["idx_a"], row["idx_b"])], rel=1e-9)
    report = result.report.describe()
    assert "1 − exp(−k²/2)" in report and f"{100 * (1 - np.exp(-4.5)):.2f} %" in report and "non 99,73 %" in report


def test_t20_axes_and_threshold(tmp_path):
    a_rows = [(50.0, 10.0, 1.0, 0.5, 30.0)]
    b_rows = [offset(50.0, 10.0, 60.0, 1.2) + (0.4, 0.2, 100.0)]
    semi = crossmatch_ellipses(*ellipse_tables(tmp_path, a_rows, b_rows), ELL, ELL, 5.0, axes="semi", mode="all")
    full = crossmatch_ellipses(*ellipse_tables(tmp_path, a_rows, b_rows, scale=2.0), ELL, ELL, 5.0, axes="full",
                               mode="all")
    assert list(semi.pairs["mahalanobis"]) == pytest.approx(list(full.pairs["mahalanobis"]), rel=1e-12)
    assert "assi interi" in full.report.criterion and "semiassi a 1σ" in semi.report.criterion
    a, b = ellipse_tables(tmp_path, a_rows, b_rows)
    for kwargs in ({"axes": "semi"}, {"threshold": 3.0}, {"threshold": 3.0, "axes": "sigma"},
                   {"threshold": -1.0, "axes": "semi"}, {"threshold": 3 * u.arcsec, "axes": "semi"}):
        with pytest.raises(CrossmatchError) as err:
            crossmatch_ellipses(a, b, ELL, ELL, **kwargs)
        assert err.value.code == "ERROR_ELLIPSE_INVALID"
    tighter = semi.rematch(threshold=0.5)
    assert tighter.report.criterion.startswith("d ≤ 0.5") and len(tighter.pairs) <= len(semi.pairs)


def test_t11_invalid_ellipse(tmp_path):
    a, b = ellipse_tables(tmp_path, [(1.0, 1.0, 0.2, 0.5, 0.0)], [(1.0, 1.0, 0.3, 0.1, 0.0)])  # minore > maggiore
    with pytest.raises(CrossmatchError) as err:
        crossmatch_ellipses(a, b, ELL, ELL, 3.0, axes="semi")
    assert err.value.code == "ERROR_ELLIPSE_INVALID" and "riga 0" in err.value.message
    a, b = ellipse_tables(tmp_path, [(1.0, 1.0, 0.0, 0.0, 0.0)], [(1.0, 1.0, 0.3, 0.1, 0.0)])  # assi nulli
    with pytest.raises(CrossmatchError) as err:
        crossmatch_ellipses(a, b, ELL, ELL, 3.0, axes="semi")
    assert err.value.code == "ERROR_ELLIPSE_INVALID"
    a, b = ellipse_tables(tmp_path, [(1.0, 1.0, 0.2, 0.1, 0.0)], [(1.0, 1.0, 0.3, 0.1, 0.0)])
    a.table["emaj"].unit = None  # unità mancante
    with pytest.raises(CrossmatchError) as err:
        crossmatch_ellipses(a, b, ELL, ELL, 3.0, axes="semi")
    assert err.value.code == "ERROR_ELLIPSE_INVALID"
    # Valori d'ellisse mancanti: righe escluse e contate come le coordinate mancanti.
    a, b = ellipse_tables(tmp_path, [(1.0, 1.0, 0.2, 0.1, 0.0), (2.0, 1.0, 0.2, 0.1, 0.0)],
                          [(1.0, 1.0, 0.3, 0.1, 0.0)])
    a.table["epa"].mask = [False, True]
    result = crossmatch_ellipses(a, b, ELL, ELL, 3.0, axes="semi", mode="none")
    assert result.report.excluded == (1, 0) and list(result.unmatched) == []


# =============================================================================
# P5 — Servizio CDS XMatch (T21 simulato, T4 di rete)
# =============================================================================

XM_VOTABLE = """<?xml version="1.0"?><VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><TABLE>
<FIELD name="angDist" datatype="double" unit="arcsec" ucd="pos.angDistance"/>
<FIELD name="idx" datatype="int"/><FIELD name="ra" datatype="float"/><FIELD name="dec" datatype="float"/>
<FIELD name="idx" datatype="int"/><FIELD name="ra" datatype="float"/><FIELD name="dec" datatype="float"/>
<DATA><TABLEDATA>{rows}</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""


def uploaded_tables(request):
    """Tabelle caricate (multipart) lette nel test con la libreria standard e astropy."""
    from email.parser import BytesParser
    from email.policy import default

    from astropy.io import ascii as astropy_ascii

    raw = b"Content-Type: " + request["headers"]["Content-Type"].encode() + b"\r\n\r\n" + request["body"]
    message = BytesParser(policy=default).parsebytes(raw)
    parts = {part.get_param("name", header="content-disposition"): part.get_content() for part in message.iter_parts()}
    tables = {k: astropy_ascii.read(v if isinstance(v, str) else v.decode(), format="csv")
              for k, v in parts.items() if k in ("cat1", "cat2")}
    fields = {k: (v if isinstance(v, str) else v.decode()) for k, v in parts.items() if k not in ("cat1", "cat2")}
    return tables, fields


def xmatch_route(log, corrupt=False):
    def route(request):
        tables, fields = uploaded_tables(request)
        log.append((tables, fields))
        t1, t2 = tables["cat1"], tables["cat2"]
        c1, c2 = SkyCoord(t1["ra"] * u.deg, t1["dec"] * u.deg), SkyCoord(t2["ra"] * u.deg, t2["dec"] * u.deg)
        from astropy.coordinates import search_around_sky

        i1, i2, sep, _ = search_around_sky(c1, c2, float(fields["distMaxArcsec"]) * u.arcsec)
        rows = sorted(zip(i1, i2, sep.arcsec), key=lambda r: (r[0], r[2]))
        if fields["selection"] == "best":
            seen, best = set(), []
            for r in rows:
                if r[0] not in seen:
                    seen.add(r[0])
                    best.append(r)
            rows = best
        cells = "".join(
            f"<TR><TD>{d:.6f}</TD><TD>{t1['idx'][i]}</TD><TD>{t1['ra'][i] + (1 if corrupt else 0)}</TD>"
            f"<TD>{t1['dec'][i]}</TD><TD>{t2['idx'][j]}</TD><TD>{t2['ra'][j]}</TD><TD>{t2['dec'][j]}</TD></TR>"
            for i, j, d in rows)
        return 200, "application/x-votable+xml", XM_VOTABLE.format(rows=cells)
    return route


def test_t21_cds_simulated(tmp_path, service, cache, monkeypatch):
    import astrotwo.core.vo_protocols as vo

    assert vo.XMATCH_URL.startswith("https://")  # URL HTTPS di default (il default di astroquery è http://)
    log = []
    service.routes["/xmatch"] = xmatch_route(log)
    monkeypatch.setattr(vo, "XMATCH_URL", service.url + "/xmatch")
    ra = 10 + 0.01 * np.arange(6)
    a = make_table(tmp_path / "a.xml", list(ra) + [None], [0.0] * 7, extra={"mag": ("mag", [1.0] * 7)})
    shifted = [offset(r, 0.0, 10.0, 0.7) for r in ra[[0, 2, 3]]]
    gal = SkyCoord([x[0] for x in shifted] * u.deg, [x[1] for x in shifted] * u.deg).transform_to(Galactic())
    b = make_table(tmp_path / "b.xml", gal.l.deg, gal.b.deg, system="galactic", galactic=True)
    result = crossmatch_cds(a, b, "best", 2 * u.arcsec, cache=cache)
    tables, fields = log[-1]
    assert tables["cat1"].colnames == ["idx", "ra", "dec"] and tables["cat2"].colnames == ["idx", "ra", "dec"]
    assert list(tables["cat1"]["idx"]) == list(range(6))  # la riga senza posizione non si carica
    icrs = gal.transform_to("icrs")  # B caricata in ICRS, convertita (ricalcolo con astropy)
    assert np.allclose(tables["cat2"]["ra"], icrs.ra.deg, atol=1e-12) and fields["selection"] == "best"
    assert list(result.pairs["idx_a"]) == [0, 2, 3] and list(result.pairs["idx_b"]) == [0, 1, 2]
    local = crossmatch(a, b, "best", 2 * u.arcsec)
    assert np.max(np.abs(result.pairs["sep"] - local.pairs["sep"])) <= 1e-3  # entro 1 mas (arcsec)
    assert result.report.service == service.url + "/xmatch" and result.report.request.protocol == "xmatch"
    assert result.report.excluded == (1, 0) and "D15-9" in result.report.describe()
    # none ricavato da all; la stessa richiesta torna dalla cache del 14.
    none = crossmatch_cds(a, b, "none", 2 * u.arcsec, cache=cache)
    assert log[-1][1]["selection"] == "all" and list(none.unmatched) == [1, 4, 5]
    calls = len(log)
    again = crossmatch_cds(a, b, "none", 2 * u.arcsec, cache=cache)
    assert len(log) == calls and again.report.request.from_cache
    with pytest.raises(CrossmatchError) as err:
        crossmatch_cds(a, b, "best", 181 * u.arcsec, cache=cache)
    assert err.value.code == "MAX_SEP_INVALID"
    service.routes["/xmatch"] = xmatch_route(log, corrupt=True)
    with pytest.raises(CrossmatchError) as err:
        crossmatch_cds(a, b, "all", 2 * u.arcsec, cache=cache, refresh=True)
    assert err.value.code == "SERVICE_ERROR"


@pytest.mark.network
def test_t4_local_vs_cds(tmp_path, cache):
    rng = np.random.default_rng(7)
    ra, dec = 150 + 0.02 * rng.random(30), 2 + 0.02 * rng.random(30)
    others = [offset(r, d, float(pa), float(sep)) for r, d, pa, sep in
              zip(ra, dec, 360 * rng.random(30), 3 * rng.random(30))]
    a = make_table(tmp_path / "a.xml", ra, dec)
    b = make_table(tmp_path / "b.xml", [o[0] for o in others], [o[1] for o in others])
    for mode in ("all", "best", "none"):
        local = crossmatch(a, b, mode, 2 * u.arcsec)
        remote = crossmatch_cds(a, b, mode, 2 * u.arcsec, cache=cache)
        if mode == "none":
            assert list(local.unmatched) == list(remote.unmatched)
            continue
        assert list(local.pairs["idx_a"]) == list(remote.pairs["idx_a"])
        assert list(local.pairs["idx_b"]) == list(remote.pairs["idx_b"])
        assert np.max(np.abs(local.pairs["sep"] - remote.pairs["sep"])) <= 1e-3  # 1 mas, in arcsec
