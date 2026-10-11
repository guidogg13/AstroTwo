"""Test del modulo 16 (``mdfiles/16-core-moc.md`` §12).

I file MOC di prova si scrivono nel test secondo il testo dello standard IVOA MOC (1.0/1.1 e 2.0), mai
copiati da altri programmi (regola d'oro n. 8); i valori attesi si ricalcolano con ``mocpy`` e ``numpy``.
"""

import json

import astropy.units as u
import numpy as np
import pytest
from astropy.io import fits
from astropy.time import Time
from mocpy import MOC, STMOC, TimeMOC

from astrotwo.core.moc import (
    VERSION_ASSUMED_11,
    VERSION_NOT_DECLARED,
    Moc,
    MocError,
    read_moc,
    write_moc,
)

# =============================================================================
# P1 — Classe Moc, lettura/scrittura, operazioni insiemistiche (T3, T5, T7)


def random_cells(seed: int, order: int = 5, n: int = 300) -> np.ndarray:
    return np.unique(np.random.default_rng(seed).integers(0, 12 * 4 ** order, n))


def ascii_moc(tmp_path, name: str, order: int, cells) -> Moc:
    path = tmp_path / name
    path.write_text(f"{order}/" + " ".join(str(int(c)) for c in cells))
    return read_moc(path, kind="space")


def cells_at(moc: Moc, order: int) -> np.ndarray:
    """Celle all'ordine dato, ricalcolate nel test con mocpy (MOC portato a quell'ordine)."""
    assert moc.space_order == order
    return np.asarray(moc.moc.flatten(), dtype=np.int64)


def test_t3_set_properties(tmp_path):
    order = 5
    ca, cb = random_cells(1), random_cells(2)
    a, b = ascii_moc(tmp_path, "a.txt", order, ca), ascii_moc(tmp_path, "b.txt", order, cb)
    union, inter = a.union(b), a.intersection(b)
    # Operazioni ricalcolate nel test con numpy sulle celle dell'ordine 5.
    assert np.array_equal(cells_at(union, order), np.union1d(ca, cb))
    assert np.array_equal(cells_at(inter, order), np.intersect1d(ca, cb))
    assert np.array_equal(cells_at(a.difference(b), order), np.setdiff1d(ca, cb))
    assert np.array_equal(cells_at(a.complement(), order), np.setdiff1d(np.arange(12 * 4 ** order), ca))
    # Proprietà: A∪B ⊇ A∩B, (A∖B)∩B = ∅, ¬¬A = A, unione commutativa, intersezione ⊆ operandi.
    assert inter.difference(union).is_empty
    empty = a.difference(b).intersection(b)
    assert empty.is_empty and "MOC_EMPTY" in dict(empty.warnings)
    assert a.complement().complement() == a
    assert a.union(b) == b.union(a)
    assert inter.difference(a).is_empty and inter.difference(b).is_empty
    assert union.space_order == order and "unione con mocpy" in union.history[-1]


def test_t5_type_mismatch(tmp_path):
    space = ascii_moc(tmp_path, "s.txt", 3, [1, 2])
    tpath = tmp_path / "t.json"
    tpath.write_text(json.dumps({"t": {"30": [5, 6]}}))
    time = read_moc(tpath)
    assert time.kind == "time" and time.body is None and time.system == "TCB"
    for op in ("union", "intersection", "difference"):
        with pytest.raises(MocError) as err:
            getattr(space, op)(time)
        assert err.value.code == "MOC_TYPE_MISMATCH"


def test_body_rules(tmp_path):
    a = ascii_moc(tmp_path, "a.txt", 3, [1, 2])
    mars = Moc(moc=a.moc, kind="space", body="Mars", origin="dati di prova")
    with pytest.raises(MocError) as err:
        a.union(mars)
    assert err.value.code == "BODY_MISMATCH"
    forced = a.union(mars, force_body=True)
    assert forced.body == "celestial" and "Mars" in dict(forced.warnings)["BODY_FORCED"]
    with pytest.raises(MocError) as err:
        Moc(moc=a.moc, kind="space", body=None, origin="x")
    assert err.value.code == "BODY_UNKNOWN"
    with pytest.raises(MocError) as err:
        write_moc(mars, tmp_path / "m.fits")
    assert err.value.code == "MOC_BODY_UNSUPPORTED"
    with pytest.raises(TypeError):
        Moc(moc=a.moc, kind="time", body=None, origin="x")  # oggetto mocpy di un altro tipo


def test_empty_moc(tmp_path):
    path = tmp_path / "e.txt"
    path.write_text("5/")  # MOC vuoto all'ordine 5 (convenzione MOCORDER dello standard 1.1)
    empty = read_moc(path, kind="space")
    assert empty.is_empty and empty.area.value == 0 and "MOC_EMPTY" in dict(empty.warnings)
    a = ascii_moc(tmp_path, "a.txt", 5, [10, 11])
    assert a.union(empty) == a and a.intersection(empty).is_empty
    assert empty.complement().sky_fraction == 1.0


def write_fits_v1(path, order: int, cells, extra=None):
    """FITS secondo MOC 1.0/1.1 (§3 dello standard): colonna UNIQ 1J, PIXTYPE, ORDERING, COORDSYS, MOCORDER."""
    uniq = 4 * 4 ** order + np.asarray(cells, dtype=np.int64)
    hdu = fits.BinTableHDU.from_columns([fits.Column(name="UNIQ", format="1J", array=uniq.astype(np.int32))])
    for key, value in {"PIXTYPE": "HEALPIX", "ORDERING": "NUNIQ", "COORDSYS": "C", "MOCORDER": order,
                       **(extra or {})}.items():
        hdu.header[key] = value
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(path)


def write_fits_v2_range(path, dim: str, order: int, ranges, extra=None):
    """FITS secondo MOC 2.0 (tabella 3) con ORDERING RANGE: coppie di interi a 64 bit all'ordine più profondo."""
    data = np.asarray(ranges, dtype=np.int64).ravel()
    hdu = fits.BinTableHDU.from_columns([fits.Column(name="RANGE", format="1K", array=data)])
    keys = {"MOCVERS": "2.0", "MOCDIM": dim, "ORDERING": "RANGE"}
    keys.update({"COORDSYS": "C", "MOCORD_S": order} if dim == "SPACE" else {"TIMESYS": "TCB", "MOCORD_T": order})
    for key, value in {**keys, **(extra or {})}.items():
        hdu.header[key] = value
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(path)


def reference_space(order: int, cells) -> MOC:
    return MOC.from_string(f"{order}/" + " ".join(str(int(c)) for c in cells))


def test_t7_versions_fits(tmp_path):
    order, cells = 6, [100, 101, 102, 4000]
    ref = reference_space(order, cells)
    write_fits_v1(tmp_path / "v1.fits", order, cells)
    v1 = read_moc(tmp_path / "v1.fits")
    assert v1.moc == ref and v1.version == VERSION_ASSUMED_11 and "MOC_VERSION_ASSUMED" in dict(v1.warnings)
    assert (v1.kind, v1.body, v1.system, v1.space_order) == ("space", "celestial", "ICRS", order)
    write_fits_v1(tmp_path / "v10.fits", order, cells, {"MOCVERS": "1.0"})
    assert read_moc(tmp_path / "v10.fits").version == "1.0"
    # 2.0 NUNIQ (con MOCVERS e MOCDIM) e 2.0 RANGE: intervalli all'ordine 29 ricalcolati nel test.
    write_fits_v1(tmp_path / "v2n.fits", order, cells, {"MOCVERS": "2.0", "MOCDIM": "SPACE", "MOCORD_S": order})
    assert read_moc(tmp_path / "v2n.fits").moc == ref
    shift = 2 * (29 - order)
    ranges = [(c << shift, (c + 1) << shift) for c in (100, 4000)]
    ranges[0] = (100 << shift, 103 << shift)  # 100–102 contigue
    write_fits_v2_range(tmp_path / "v2r.fits", "SPACE", order, ranges)
    v2 = read_moc(tmp_path / "v2r.fits")
    assert v2.moc == ref and v2.version == "2.0" and not v2.warnings
    # 2.0 temporale RANGE: microsecondi da JD 0 in TCB (standard 2.0 §4.2), una cella dell'ordine 35.
    t_order, cell = 35, 3_000_000
    tshift = 61 - t_order
    write_fits_v2_range(tmp_path / "t.fits", "TIME", t_order, [(cell << tshift, (cell + 1) << tshift)])
    tmoc = read_moc(tmp_path / "t.fits")
    assert tmoc.kind == "time" and tmoc.time_order == t_order and tmoc.body is None
    assert tmoc.moc == TimeMOC.from_string(f"{t_order}/{cell}")
    assert tmoc.duration.value == pytest.approx((1 << tshift) * 1e-6)  # μs → s
    # Spazio-temporale: file scritto da mocpy (libreria di riferimento) e riletto.
    st = STMOC.from_time_ranges_positions(Time([2459000.5], format="jd", scale="tcb"),
                                          Time([2459001.5], format="jd", scale="tcb"),
                                          np.array([10.0]) * u.deg,
                                          np.array([20.0]) * u.deg,
                                          time_depth=35, spatial_depth=8)
    st.save(tmp_path / "st.fits", format="fits")
    stm = read_moc(tmp_path / "st.fits")
    assert stm.kind == "space-time" and stm.moc == st and (stm.time_order, stm.space_order) == (35, 8)
    with pytest.raises(MocError) as err:
        stm.complement()
    assert err.value.code == "MOC_OPERATION_UNSUPPORTED" and "D16-7" in err.value.message


def test_t7_versions_refused(tmp_path):
    write_fits_v1(tmp_path / "v21.fits", 4, [1], {"MOCVERS": "2.1", "MOCDIM": "SPACE", "MOCORD_S": 4})
    with pytest.raises(MocError) as err:
        read_moc(tmp_path / "v21.fits")
    assert err.value.code == "MOC_VERSION_UNSUPPORTED" and "D16-6" in err.value.message
    write_fits_v1(tmp_path / "v3.fits", 4, [1], {"MOCVERS": "3.0"})
    with pytest.raises(MocError) as err:
        read_moc(tmp_path / "v3.fits")
    assert err.value.code == "MOC_VERSION_UNSUPPORTED" and err.value.details["version"] == "3.0"
    write_fits_v1(tmp_path / "g.fits", 4, [1], {"COORDSYS": "G"})
    with pytest.raises(MocError) as err:
        read_moc(tmp_path / "g.fits")
    assert err.value.code == "MOC_UNREADABLE"
    (tmp_path / "bad.fits").write_bytes(b"SIMPLE  = garbage")
    with pytest.raises(MocError) as err:
        read_moc(tmp_path / "bad.fits")
    assert err.value.code == "MOC_UNREADABLE"
    with pytest.raises(MocError) as err:
        read_moc(tmp_path / "v21.fits", kind="time")
    assert err.value.code == "MOC_VERSION_UNSUPPORTED"
    write_fits_v1(tmp_path / "s.fits", 4, [1])
    with pytest.raises(MocError) as err:
        read_moc(tmp_path / "s.fits", kind="time")
    assert err.value.code == "MOC_TYPE_MISMATCH"


def test_t7_json_and_text(tmp_path):
    ref = reference_space(3, [5, 6, 7])
    plain = tmp_path / "p.json"
    plain.write_text('{"3": [5, 6, 7]}')
    with pytest.raises(MocError) as err:  # senza prefisso il tipo non si assume (standard 2.0, appendice F)
        read_moc(plain)
    assert err.value.code == "MOC_TYPE_REQUIRED"
    got = read_moc(plain, kind="space")
    assert got.moc == ref and got.version == VERSION_NOT_DECLARED
    prefixed = tmp_path / "s.json"
    prefixed.write_text('{"s": {"3": [5, 6, 7]}}')
    assert read_moc(prefixed).moc == ref
    with pytest.raises(MocError) as err:
        read_moc(prefixed, kind="time")
    assert err.value.code == "MOC_TYPE_MISMATCH"
    text = tmp_path / "m.txt"
    text.write_text("3/5-7")
    with pytest.raises(MocError) as err:
        read_moc(text)
    assert err.value.code == "MOC_TYPE_REQUIRED"
    assert read_moc(text, kind="space").moc == ref
    st_text = tmp_path / "st.txt"
    st_text.write_text("t61/1 s29/0-2 t61/3 s28/0")  # forma dell'esempio dello standard 2.0 §5.1
    st = read_moc(st_text)
    assert st.kind == "space-time" and st.moc == STMOC.from_string("t61/1 s29/0-2 t61/3 s28/0")
    bad = tmp_path / "bad.json"
    bad.write_text('{"3": [5, "x"]}')
    with pytest.raises(MocError) as err:
        read_moc(bad, kind="space")
    assert err.value.code == "MOC_UNREADABLE"


@pytest.mark.parametrize("fmt", ["fits", "json", "ascii"])
def test_write_round_trip(tmp_path, fmt):
    space = ascii_moc(tmp_path, "a.txt", 6, [1, 2, 3, 900])
    tpath = tmp_path / "t.json"
    tpath.write_text(json.dumps({"t": {"35": [3000000, 3000001]}}))
    time = read_moc(tpath)
    for moc in (space, time):
        target = write_moc(moc, tmp_path / f"{moc.kind}.{fmt}", format=fmt)
        back = read_moc(target, kind=None if fmt != "ascii" else moc.kind)
        assert back == moc
        with pytest.raises(FileExistsError):
            write_moc(moc, target, format=fmt)
        write_moc(moc, target, format=fmt, overwrite=True)
    if fmt == "fits":
        header = fits.getheader(tmp_path / "space.fits", 1)
        assert (header["MOCVERS"], header["MOCDIM"], header["ORDERING"], header["COORDSYS"]) == \
            ("2.0", "SPACE", "NUNIQ", "C")
        assert header["MOCORDER"] == 6 and header["MOCTOOL"].startswith("AstroTwo")
        theader = fits.getheader(tmp_path / "time.fits", 1)
        assert (theader["MOCDIM"], theader["ORDERING"], theader["TIMESYS"]) == ("TIME", "RANGE", "TCB")
    if fmt == "json":
        assert list(json.loads((tmp_path / "time.json").read_text())) == ["t"]


def test_describe(tmp_path):
    a = ascii_moc(tmp_path, "a.txt", 0, [0])  # una cella dell'ordine 0 = 1/12 del cielo
    text = a.describe()
    assert a.sky_fraction == pytest.approx(1 / 12) and a.area.value == pytest.approx(4 * np.pi / 12)
    assert "MOC space" in text and "ICRS" in text and "corpo celestial" in text and "1 celle" in text
