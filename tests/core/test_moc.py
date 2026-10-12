"""Test del modulo 16 (``mdfiles/16-core-moc.md`` §12).

I file MOC di prova si scrivono nel test secondo il testo dello standard IVOA MOC (1.0/1.1 e 2.0), mai
copiati da altri programmi (regola d'oro n. 8); i valori attesi si ricalcolano con ``mocpy`` e ``numpy``.
"""

import json
from dataclasses import replace

import astropy.units as u
import numpy as np
import pytest
from astropy.io import fits
from astropy.time import Time
from mocpy import MOC, STMOC, TimeMOC

from astrotwo.core.moc import (
    MIXED_BODY,
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
    assert forced.body == MIXED_BODY and forced.bodies == ("Mars", "celestial")
    assert "Mars" in dict(forced.warnings)["BODY_FORCED"] and forced.moc == a.moc
    with pytest.raises(MocError) as err:
        Moc(moc=a.moc, kind="space", body=None, origin="x")
    assert err.value.code == "BODY_UNKNOWN"
    with pytest.raises(ValueError):
        Moc(moc=a.moc, kind="space", body=MIXED_BODY, origin="x")  # misto senza l'elenco dei corpi
    with pytest.raises(TypeError):
        Moc(moc=a.moc, kind="time", body=None, origin="x")  # oggetto mocpy di un altro tipo


def test_mixed_body_requires_force_again(tmp_path):
    """Scelta 5 (2026-10-12): risultato forzato = corpo misto con l'elenco; ogni operazione successiva su un MOC
    misto richiede di nuovo la forzatura, anche con un MOC dello stesso corpo o un altro MOC misto."""
    a = ascii_moc(tmp_path, "a.txt", 3, [1, 2])
    b = ascii_moc(tmp_path, "b.txt", 3, [2, 3])
    moon = Moc(moc=b.moc, kind="space", body="Moon", origin="dati di prova")
    mars = Moc(moc=b.moc, kind="space", body="Mars", origin="dati di prova")
    mixed = a.intersection(moon, force_body=True)
    assert (mixed.body, mixed.bodies) == (MIXED_BODY, ("Moon", "celestial"))
    assert "misto (Moon, celestial)" in mixed.describe()
    for op in (lambda: mixed.union(a), lambda: a.union(mixed), lambda: mixed.union(mixed),
               lambda: mixed.difference(moon), lambda: mixed.complement(), lambda: mixed.union(mars)):
        with pytest.raises(MocError) as err:
            op()
        assert err.value.code == "BODY_MISMATCH" and "misto" in err.value.message
    again = mixed.union(mars, force_body=True)
    assert again.bodies == ("Mars", "Moon", "celestial") and "BODY_FORCED" in dict(again.warnings)
    same = mixed.union(a, force_body=True)
    assert same.bodies == ("Moon", "celestial")
    comp = mixed.complement(force_body=True)
    assert comp.bodies == mixed.bodies and "BODY_FORCED" in dict(comp.warnings)
    with pytest.raises(MocError) as err:
        mixed.contains(SkyCoord([0.0] * u.deg, [0.0] * u.deg))
    assert err.value.code == "BODY_MISMATCH"
    assert list(mixed.contains(SkyCoord([0.0] * u.deg, [0.0] * u.deg), force_body=True)) == [False]


def test_planetary_and_mixed_round_trip(tmp_path):
    """Scelta 6 (2026-10-12): MOC planetari e misti scritti in FITS 2.0 con la parola chiave nostra A2BODY
    (A2BODIES per i misti), dichiarata come estensione non standard, e riletti con lo stesso corpo."""
    a = ascii_moc(tmp_path, "a.txt", 4, [5, 6, 7])
    mars = Moc(moc=a.moc, kind="space", body="Mars", origin="dati di prova")
    written = write_moc(mars, tmp_path / "mars.fits")
    assert written.path == tmp_path / "mars.fits" and written.version == "2.0"
    assert "MOC_NONSTANDARD_EXTENSION" in dict(written.warnings)
    header = fits.getheader(tmp_path / "mars.fits", 1)
    assert (header["A2BODY"], header["MOCVERS"], header["COORDSYS"]) == ("Mars", "2.0", "C")
    back = read_moc(written)
    assert back == mars and back.body == "Mars" and "MOC_NONSTANDARD_EXTENSION" in dict(back.warnings)
    mixed = a.union(mars, force_body=True)
    back_mixed = read_moc(write_moc(mixed, tmp_path / "mixed.fits"))
    assert back_mixed == mixed and back_mixed.bodies == ("Mars", "celestial")
    st = moc_space_time(Time([2459000.5], format="jd", scale="tcb"), None, SkyCoord([10.0] * u.deg, [20.0] * u.deg),
                        time_order=30, space_order=6)
    moon_st = replace(st, body="Moon")
    assert read_moc(write_moc(moon_st, tmp_path / "moon_st.fits")) == moon_st
    # MOC celeste: nessuna parola chiave nostra, nessun avviso.
    plain = write_moc(a, tmp_path / "a.fits")
    assert plain.warnings == () and "A2BODY" not in fits.getheader(tmp_path / "a.fits", 1)
    for fmt in ("json", "ascii"):  # il corpo non si può dichiarare in JSON e testo
        with pytest.raises(MocError) as err:
            write_moc(mars, tmp_path / f"mars.{fmt}", format=fmt)
        assert err.value.code == "MOC_BODY_UNSUPPORTED"
    hdul = fits.open(tmp_path / "mixed.fits")
    del hdul[1].header["A2BODIES"]
    hdul.writeto(tmp_path / "broken.fits")
    with pytest.raises(MocError) as err:
        read_moc(tmp_path / "broken.fits")
    assert err.value.code == "MOC_UNREADABLE"


def test_d16_7_space_time_complement():
    """D16-7 (2026-10-12): complemento di un ST-MOC = tutto il tempo × tutto il cielo meno il MOC dato, con le
    operazioni di mocpy. Verifica indipendente su istanti e posizioni campione con query_by_time/contains."""
    times = Time([2459000.5, 2459100.5], format="jd", scale="tcb")
    coords = SkyCoord([10.0, 200.0] * u.deg, [20.0, -30.0] * u.deg)
    st = moc_space_time(times, None, coords, time_order=20, space_order=5)
    comp = st.complement()
    assert comp.kind == "space-time" and (comp.time_order, comp.space_order) == (20, 5)
    assert "D16-7" in comp.history[-1]
    assert comp.complement() == st  # ¬¬A = A
    assert comp.intersection(st).is_empty
    full = TimeMOC.new_empty(20).complement()  # tutto il tempo dello standard, ricalcolato con mocpy
    assert comp.union(st).space_during(Moc(moc=full, kind="time", body=None, origin="tutto")).sky_fraction == 1.0
    probe = SkyCoord([10.0, 200.0, 100.0] * u.deg, [20.0, -30.0, 0.0] * u.deg)
    for instant in (times[0], times[1], Time(2459050.5, format="jd", scale="tcb")):
        tm = TimeMOC.from_times(Time([instant.jd], format="jd", scale="tcb"), order=20)
        inside = st.moc.query_by_time(tm).contains_lonlat(lon=probe.ra, lat=probe.dec)
        outside = comp.moc.query_by_time(tm).contains_lonlat(lon=probe.ra, lat=probe.dec)
        assert np.array_equal(np.asarray(outside), ~np.asarray(inside))
    empty = st.difference(st)
    assert empty.complement().complement().is_empty


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


# =============================================================================
# P2 — Creazione da cerchio, poligono, catalogo, immagine (T1, T2)

from astropy.coordinates import ICRS, Galactic, SkyCoord  # noqa: E402
from astropy_healpix import HEALPix  # noqa: E402

from astrotwo.core.moc import CircleRegion, PolygonRegion, moc_from_catalog, moc_from_image, moc_from_region  # noqa: E402


def cell_area(order: int) -> float:
    return 4 * np.pi / (12 * 4 ** order)


def boundary_cells(order: int, candidates, inside) -> int:
    """Celle (tra i candidati) attraversate dal contorno: punti del bordo della cella sia dentro sia fuori.
    Bordi delle celle ricalcolati nel test con astropy-healpix (NESTED, ICRS)."""
    hp = HEALPix(nside=2 ** order, order="nested", frame=ICRS())
    corners = hp.boundaries_skycoord(np.asarray(candidates, dtype=np.int64), step=8)
    flags = inside(corners)
    return int(np.count_nonzero(flags.any(axis=1) & ~flags.all(axis=1)))


def neighbourhood(moc: Moc) -> np.ndarray:
    return np.asarray(moc.moc.extended().flatten(), dtype=np.int64)  # add_neighbours modifica sul posto


def test_t1_circle(tmp_path):
    order = 9
    center = SkyCoord(150 * u.deg, 2 * u.deg, frame=Galactic())  # convertito in ICRS con il modulo 10
    moc = moc_from_region(CircleRegion(center, 1 * u.deg), order)
    expected = 2 * np.pi * (1 - np.cos(np.radians(1.0)))  # steradianti, formula ricalcolata nel test
    icrs = center.icrs
    n_border = boundary_cells(order, neighbourhood(moc), lambda c: c.separation(icrs) <= 1 * u.deg)
    assert n_border > 0
    assert abs(moc.area.to_value(u.sr) - expected) <= n_border * cell_area(order)
    assert moc.space_order == order and moc.body == "celestial" and "galactic" in moc.origin
    assert "from_cone" in moc.history[-1]
    for bad in (0 * u.deg, 181 * u.deg, 1.0, 1 * u.m):
        with pytest.raises(MocError) as err:
            moc_from_region(CircleRegion(center, bad), order)
        assert err.value.code == "REGION_INVALID"
    for bad_order in (None, -1, 30, 2.0, True):
        with pytest.raises(MocError) as err:
            moc_from_region(CircleRegion(center, 1 * u.deg), bad_order)
        assert err.value.code == "HEALPIX_ORDER_INVALID"


def octant(lon0: float, north: bool) -> PolygonRegion:
    pole = 90.0 if north else -90.0
    return PolygonRegion(SkyCoord([lon0, lon0 + 90.0, 0.0] * u.deg, [0.0, 0.0, pole] * u.deg))


def test_t2_full_sky_from_quarters():
    order = 6
    quarters = [moc_from_region(octant(90.0 * q, True), order).union(moc_from_region(octant(90.0 * q, False), order))
                for q in range(4)]
    sky = quarters[0].union(quarters[1]).union(quarters[2]).union(quarters[3])
    # Celle di bordo: attraversate dall'equatore o dai meridiani 0°, 90°, 180°, 270° (ricalcolo nel test).
    all_cells = np.arange(12 * 4 ** order)

    def border(c):
        lon, lat = c.ra.deg, c.dec.deg
        straddle = (lat.min(axis=1) < 0) & (lat.max(axis=1) > 0)
        for m in (0.0, 90.0, 180.0, 270.0):
            d = (lon - m + 180.0) % 360.0 - 180.0
            straddle |= (d.min(axis=1) < 0) & (d.max(axis=1) > 0) & (np.abs(d).max(axis=1) < 90)
        return straddle

    hp = HEALPix(nside=2 ** order, order="nested", frame=ICRS())
    n_border = int(np.count_nonzero(border(hp.boundaries_skycoord(all_cells, step=4))))
    assert abs(sky.area.to_value(u.sr) - 4 * np.pi) <= n_border * cell_area(order)
    assert quarters[0].sky_fraction == pytest.approx(0.25, abs=n_border * cell_area(order) / (4 * np.pi))


def test_polygon_interior_rule():
    order = 7
    tri = SkyCoord([0.0, 90.0, 0.0] * u.deg, [0.0, 0.0, 89.0] * u.deg)
    small = moc_from_region(PolygonRegion(tri), order)
    reversed_ = moc_from_region(PolygonRegion(tri[::-1]), order)
    other = moc_from_region(PolygonRegion(tri), order, complement=True)
    assert small.sky_fraction < 0.5 < other.sky_fraction and reversed_.sky_fraction < 0.5  # regione più piccola
    # Verso dei vertici: stessa regione, celle di bordo che possono differire (comportamento di mocpy).
    border = small.moc.extended().difference(small.moc.contracted())
    assert small.moc.difference(reversed_.moc).difference(border).empty()
    assert reversed_.moc.difference(small.moc).difference(border).empty()
    assert "regione più piccola" in small.history[-1] and "complement=True" in other.history[-1]
    with pytest.raises(MocError) as err:
        moc_from_region(PolygonRegion(tri[:2]), order)
    assert err.value.code == "REGION_INVALID"


def test_moc_from_catalog(tmp_path):
    from test_crossmatch import make_table

    gal = SkyCoord([10.0, 10.001, 200.0] * u.deg, [5.0, 5.0, -30.0] * u.deg, frame=Galactic())
    table = make_table(tmp_path / "c.xml", list(gal.l.deg) + [None], list(gal.b.deg) + [None], system="galactic",
                       galactic=True)
    moc = moc_from_catalog(table, 10)
    icrs = gal.icrs  # ricalcolo nel test con astropy e mocpy
    assert moc.moc == MOC.from_lonlat(lon=icrs.ra, lat=icrs.dec, max_norder=10)
    assert "1 righe senza posizione" in dict(moc.warnings)["ROWS_EXCLUDED"] and "senza raggio" in moc.history[-1]
    import dataclasses

    with pytest.raises(MocError) as err:
        moc_from_catalog(dataclasses.replace(table, positions=None), 10)
    assert err.value.code == "NO_COORD_COLUMNS"
    with pytest.raises(MocError) as err:
        moc_from_catalog(dataclasses.replace(table, body="Mars"), 10)
    assert err.value.code == "MOC_BODY_UNSUPPORTED"
    with pytest.raises(MocError) as err:
        moc_from_catalog(table, None)
    assert err.value.code == "HEALPIX_ORDER_INVALID"


def write_image(path, data, *, wcs=True, blank=None):
    header = fits.Header()
    if wcs:
        ny, nx = data.shape
        header.update({"CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN", "CRVAL1": 150.0, "CRVAL2": 2.0,
                       "CRPIX1": (nx + 1) / 2, "CRPIX2": (ny + 1) / 2, "CDELT1": -0.01, "CDELT2": 0.01,
                       "CUNIT1": "deg", "CUNIT2": "deg", "RADESYS": "ICRS"})
    if blank is not None:
        header["BLANK"] = blank
    fits.PrimaryHDU(data=data, header=header).writeto(path)
    from astrotwo.core.images_fits import load_image

    return load_image(path)


def footprint_polygon(image, x1: float, y1: float, order: int) -> Moc:
    """Poligono degli angoli dei pixel validi: in TAN i bordi rettilinei sono cerchi massimi (ricalcolo con
    astropy.wcs nel test)."""
    corners = image.wcs.wcs.pixel_to_world([-0.5, x1, x1, -0.5], [-0.5, -0.5, y1, y1])
    return moc_from_region(PolygonRegion(corners), order)


def check_against_polygon(moc: Moc, poly: Moc, order: int) -> None:
    outer, inner = poly.moc.extended(), poly.moc.contracted()
    assert moc.moc.difference(outer).empty()  # mai oltre una cella dal contorno
    assert inner.difference(moc.moc).empty()  # l'interno è tutto coperto
    n_border = len(outer.flatten()) - len(inner.flatten())
    assert abs(moc.area.to_value(u.sr) - poly.area.to_value(u.sr)) <= n_border * cell_area(order)


@pytest.mark.parametrize("order", [9, 14])  # pixel più piccolo di metà cella (k = 1) e più grande (k > 1)
def test_moc_from_image(tmp_path, order):
    ny, nx = (100, 200) if order == 9 else (10, 20)
    image = write_image(tmp_path / "i.fits", np.ones((ny, nx), dtype=np.float32))
    moc = moc_from_image(image, order)
    check_against_polygon(moc, footprint_polygon(image, nx - 0.5, ny - 0.5, order), order)
    assert "pixel validi" in moc.history[-1] and moc.body == "celestial"
    # Metà destra non valida (NaN): MOC dei soli pixel validi.
    data = np.ones((ny, nx), dtype=np.float32)
    data[:, nx // 2:] = np.nan
    half = moc_from_image(write_image(tmp_path / "h.fits", data), order)
    check_against_polygon(half, footprint_polygon(image, nx // 2 - 0.5, ny - 0.5, order), order)


def test_moc_from_image_errors(tmp_path):
    data = np.ones((10, 20), dtype=np.int16)
    data[:, 10:] = -1
    blank = moc_from_image(write_image(tmp_path / "b.fits", data, blank=-1), 12)
    full = moc_from_image(write_image(tmp_path / "f.fits", np.ones((10, 20), dtype=np.int16)), 12)
    assert blank.sky_fraction < full.sky_fraction and "100 non validi" in blank.history[-1]
    with pytest.raises(MocError) as err:
        moc_from_image(write_image(tmp_path / "n.fits", np.ones((5, 5)), wcs=False), 8)
    assert err.value.code == "WCS_MISSING"


# =============================================================================
# P3 — Filtro per MOC, mappe e griglie HEALPix (T4, T6)

from astrotwo.core.moc import GRID_MAX_CELLS, filter_by_moc, healpix_grid, healpix_map  # noqa: E402


def random_sky(n: int, seed: int, ra=(0.0, 30.0), dec=(-10.0, 20.0)):
    rng = np.random.default_rng(seed)
    return rng.uniform(*ra, n), rng.uniform(*dec, n)


def test_t4_filter_by_moc(tmp_path):
    from test_crossmatch import make_table

    ra, dec = random_sky(1000, 11)
    table = make_table(tmp_path / "t.xml", list(ra) + [None], list(dec) + [None])
    order = 6
    moc = moc_from_region(CircleRegion(SkyCoord(15 * u.deg, 5 * u.deg), 8 * u.deg), order)
    inside = filter_by_moc(table, moc)
    # Ricalcolo con astropy-healpix: cella NESTED di ogni punto all'ordine del MOC, appartenenza alle sue celle.
    cells = HEALPix(nside=2 ** order, order="nested", frame=ICRS()).lonlat_to_healpix(ra * u.deg, dec * u.deg)
    expected = np.isin(cells, np.asarray(moc.moc.flatten()))
    assert inside.count == int(np.count_nonzero(expected)) and np.array_equal(inside.mask[:1000], expected)
    assert not inside.mask[1000] and inside.excluded == 1 and "ROWS_EXCLUDED" in dict(inside.warnings)
    outside = filter_by_moc(table, moc, inside=False)
    assert outside.count == 1000 - inside.count and not outside.mask[1000]
    assert list(inside.indices) == list(np.flatnonzero(expected)) and table.rows == 1001  # tabella invariata
    assert np.array_equal(moc.contains(SkyCoord(ra * u.deg, dec * u.deg)), expected)
    import dataclasses

    with pytest.raises(MocError) as err:
        filter_by_moc(dataclasses.replace(table, body="Mars"), moc)
    assert err.value.code == "BODY_MISMATCH"
    forced = filter_by_moc(dataclasses.replace(table, body="Mars"), moc, force_body=True)
    assert "BODY_FORCED" in dict(forced.warnings)
    with pytest.raises(MocError) as err:
        filter_by_moc(dataclasses.replace(table, positions=None), moc)
    assert err.value.code == "NO_COORD_COLUMNS"
    tpath = tmp_path / "t.json"
    tpath.write_text('{"t": {"30": [1]}}')
    with pytest.raises(MocError) as err:
        filter_by_moc(table, read_moc(tpath))
    assert err.value.code == "MOC_TYPE_MISMATCH"


def test_t6_healpix_map(tmp_path):
    from test_crossmatch import make_table

    order = 4
    hp = HEALPix(nside=2 ** order, order="nested", frame=ICRS())
    # Distribuzione nota: 3 punti al centro della cella 10, 1 al centro della cella 2000.
    lon, lat = hp.healpix_to_lonlat([10, 10, 10, 2000])
    table = make_table(tmp_path / "m.xml", lon.deg, lat.deg,
                       extra={"flux": ("mJy", [1.0, 2.0, None, 5.0])})
    counts = healpix_map(table, order)
    assert counts.values[10] == 3 and counts.values[2000] == 1 and counts.values.sum() == 4
    assert (counts.scheme, counts.frame, counts.nside, counts.values.size) == ("NESTED", "ICRS", 16, hp.npix)
    flux = healpix_map(table, order, column="flux")
    assert flux.values[10] == 3.0 and flux.values[2000] == 5.0 and str(flux.unit) == "mJy"
    assert "VALUES_EXCLUDED" in dict(flux.warnings) and "NESTED in ICRS" in flux.description
    # Distribuzione casuale: valori uguali a astropy-healpix + numpy ricalcolati nel test.
    ra, dec = random_sky(500, 5)
    rand = healpix_map(make_table(tmp_path / "r.xml", ra, dec), 5)
    cells = HEALPix(nside=32, order="nested", frame=ICRS()).lonlat_to_healpix(ra * u.deg, dec * u.deg)
    assert np.array_equal(rand.values, np.bincount(cells, minlength=12 * 4 ** 5))
    with pytest.raises(MocError) as err:
        healpix_map(table, None)
    assert err.value.code == "HEALPIX_ORDER_INVALID"


def test_healpix_grid():
    grid = healpix_grid(1)
    hp = HEALPix(nside=2, order="nested", frame=ICRS())
    lon, lat = hp.boundaries_lonlat(np.arange(48), step=1)
    assert grid.cells.size == 48 and np.allclose(grid.lon, lon.deg) and np.allclose(grid.lat, lat.deg)
    moc = moc_from_region(CircleRegion(SkyCoord(15 * u.deg, 5 * u.deg), 1 * u.deg), 6)
    before = moc.moc.to_string()
    local = healpix_grid(8, within=moc)
    assert moc.moc.to_string() == before and moc.space_order == 6  # il MOC dato non cambia
    assert local.cells.size == 16 * len(moc.moc.flatten())
    coarse = healpix_grid(3, within=moc)
    assert set(coarse.cells) == set(np.asarray(moc.moc.degrade_to_order(3).flatten()))
    with pytest.raises(MocError) as err:
        healpix_grid(8)
    assert err.value.code == "GRID_TOO_LARGE" and GRID_MAX_CELLS == 12 * 4 ** 7


# =============================================================================
# P4 — MOC temporali e spazio-temporali, mappe di probabilità (D16-3, D16-4)

from astrotwo.core.moc import (  # noqa: E402
    PROBABILITY_SUM_TOLERANCE,
    moc_from_probability,
    moc_from_times,
    moc_space_time,
    read_probability_map,
)


def test_time_moc_scale():
    start = Time(["2020-01-01T00:00:00", "2020-03-01T00:00:00"], scale="utc")
    end = Time(["2020-01-02T00:00:00", "2020-03-01T12:00:00"], scale="utc")
    tmoc = moc_from_times(start, end, order_max=40)
    # Ricalcolo nel test: conversione in TCB con astropy.time, poi mocpy.
    expected = TimeMOC.from_time_ranges(start.tcb, end.tcb, order=40)
    assert tmoc.moc == expected and tmoc.kind == "time" and tmoc.system == "TCB" and tmoc.time_order == 40
    assert "scala d'ingresso UTC, convertiti in TCB" in tmoc.history[-1]
    first, last = tmoc.time_range
    assert first.scale == "tcb" and abs((first - start[0].tcb).to_value(u.s)) <= 2 ** (61 - 40) * 1e-6
    inside = Time(["2020-01-01T12:00:00", "2020-02-01T00:00:00"], scale="utc")
    assert list(tmoc.contains_times(inside)) == [True, False]
    instants = moc_from_times(Time([2459000.5], format="jd", scale="tt"), order_max=61)
    assert instants.moc == TimeMOC.from_times(Time([2459000.5], format="jd", scale="tt").tcb, order=61)
    with pytest.raises(MocError) as err:
        moc_from_times(end, start, order_max=40)
    assert err.value.code == "TIME_RANGE_INVALID"
    with pytest.raises(MocError) as err:
        moc_from_times(start, end, order_max=62)
    assert err.value.code == "HEALPIX_ORDER_INVALID"
    with pytest.raises(TypeError):
        moc_from_times([2459000.5], order_max=30)  # senza scala dichiarata (non Time)


def test_space_time_moc(tmp_path):
    times = Time([2459000.5, 2459100.5], format="jd", scale="tcb")
    coords = SkyCoord([10.0, 200.0] * u.deg, [20.0, -30.0] * u.deg)
    st = moc_space_time(times, None, coords, time_order=30, space_order=8)
    expected = STMOC.from_times_positions(times, 30, coords.ra, coords.dec, 8)
    assert st.moc == expected and (st.time_order, st.space_order) == (30, 8) and st.body == "celestial"
    first_day = moc_from_times(Time([2459000.0], format="jd", scale="tcb"), Time([2459001.0], format="jd", scale="tcb"),
                               order_max=30)
    space = st.space_during(first_day)
    assert space.kind == "space" and space.moc.contains_lonlat(lon=[10.0] * u.deg, lat=[20.0] * u.deg)[0]
    assert not space.moc.contains_lonlat(lon=[200.0] * u.deg, lat=[-30.0] * u.deg)[0]
    around = moc_from_region(CircleRegion(SkyCoord(200 * u.deg, -30 * u.deg), 0.5 * u.deg), 8)
    when = st.time_within(around)
    assert list(when.contains_times(Time([2459100.5, 2459000.5], format="jd", scale="tcb"))) == [True, False]
    back = read_moc(write_moc(st, tmp_path / "st.fits"))
    assert back == st and fits.getheader(tmp_path / "st.fits", 1)["TIMESYS"] == "TCB"


def write_multiorder(path, uniq, density, *, unit="sr-1", coordsys="C"):
    """Mappa multi-ordine nel formato pubblico LIGO/Virgo/KAGRA: UNIQ, PROBDENSITY [sr-1], ORDERING NUNIQ."""
    cols = [fits.Column(name="UNIQ", format="K", array=np.asarray(uniq, dtype=np.int64)),
            fits.Column(name="PROBDENSITY", format="D", array=density, unit=unit)]
    hdu = fits.BinTableHDU.from_columns(cols)
    hdu.header.update({"PIXTYPE": "HEALPIX", "ORDERING": "NUNIQ", "COORDSYS": coordsys})
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(path, overwrite=True)


def synthetic_multiorder(seed=3):
    """Cella 0 dell'ordine 0 divisa in 16 celle dell'ordine 2, le altre 11 all'ordine 0 (tutto il cielo)."""
    uniq = np.array([4 * 4 ** 2 + i for i in range(16)] + [4 + i for i in range(1, 12)], dtype=np.int64)
    order = np.array([2] * 16 + [0] * 11)
    area = 4 * np.pi / (12 * 4.0 ** order)
    weights = np.random.default_rng(seed).random(uniq.size)
    weights[:16] *= 20
    prob = weights / weights.sum()
    return uniq, prob / area, prob, area


def credible_reference(prob, density, level):
    """Calcolo indipendente nel test (guida LIGO): celle per densità decrescente fino a probabilità ≥ livello."""
    order = np.argsort(-density, kind="stable")
    k = int(np.searchsorted(np.cumsum(prob[order]), level))
    return set(order[: k + 1]), float(np.cumsum(prob[order])[k])


def test_probability_multiorder(tmp_path):
    uniq, density, prob, _ = synthetic_multiorder()
    write_multiorder(tmp_path / "m.fits", uniq, density)
    pmap = read_probability_map(tmp_path / "m.fits")
    assert pmap.layout == "multi-order" and pmap.max_order == 2
    assert abs(pmap.total - 1.0) <= PROBABILITY_SUM_TOLERANCE and "entro 1e-06" in pmap.description
    region = moc_from_probability(pmap, 0.9, 2)
    chosen, contained = credible_reference(prob, density, 0.9)
    expected_cells = sorted(int(uniq[i]) for i in chosen)
    assert sorted(int(x) for x in region.moc.uniq_hpx) == sorted(
        int(x) for x in MOC.from_healpix_cells(*_cells(expected_cells), max_depth=2).uniq_hpx)
    reported = float(dict(region.warnings)["CREDIBLE_PROBABILITY"])
    assert reported == pytest.approx(contained, rel=1e-9) and reported >= 0.9
    coarse = moc_from_probability(pmap, 0.9, 1)  # ordine più basso della mappa: per eccesso, dichiarato
    assert "ORDER_DEGRADED" in dict(coarse.warnings) and region.moc.difference(coarse.moc).empty()
    with pytest.raises(MocError) as err:
        moc_from_probability(pmap, 1.5, 2)
    assert err.value.code == "PROBABILITY_OUT_OF_RANGE"


def _cells(uniq_list):
    uniq = np.asarray(uniq_list, dtype=np.int64)
    order = np.searchsorted([4 * 4 ** k for k in range(30)], uniq, side="right") - 1
    return uniq - 4 * 4 ** order, order


def test_probability_flat_ring(tmp_path):
    nside = 16  # 3072 celle: colonna vettoriale di 3 righe da 1024 valori
    npix = 12 * nside ** 2
    prob_ring = np.random.default_rng(9).random(npix)
    prob_ring /= prob_ring.sum()
    hdu = fits.BinTableHDU.from_columns([fits.Column(name="PROB", format="1024D", array=prob_ring.reshape(-1, 1024))])
    hdu.header.update({"PIXTYPE": "HEALPIX", "ORDERING": "RING", "NSIDE": nside, "COORDSYS": "C",
                       "INDXSCHM": "IMPLICIT"})
    fits.HDUList([fits.PrimaryHDU(), hdu]).writeto(tmp_path / "flat.fits")
    pmap = read_probability_map(tmp_path / "flat.fits")
    # Ricalcolo nel test: celle RING → NESTED con astropy-healpix.
    nested = HEALPix(nside=nside, order="nested", frame=ICRS()).ring_to_nested(np.arange(npix))
    prob_nested = np.empty(npix)
    prob_nested[nested] = prob_ring
    assert pmap.layout == "flat" and pmap.max_order == 4
    assert np.allclose(pmap.probability, prob_nested, rtol=1e-12, atol=0)
    region = moc_from_probability(pmap, 0.5, 4)
    chosen, contained = credible_reference(prob_nested, prob_nested, 0.5)
    assert set(np.asarray(region.moc.flatten())) == chosen
    assert float(dict(region.warnings)["CREDIBLE_PROBABILITY"]) == pytest.approx(contained, rel=1e-9)


def test_probability_map_errors(tmp_path):
    uniq, density, _, _ = synthetic_multiorder()
    write_multiorder(tmp_path / "s.fits", uniq, density * (1 + 1e-5))
    with pytest.raises(MocError) as err:
        read_probability_map(tmp_path / "s.fits")
    assert err.value.code == "PROBABILITY_SUM_INVALID"
    bad = density.copy()
    bad[0] = -bad[0]
    write_multiorder(tmp_path / "n.fits", uniq, bad)
    with pytest.raises(MocError) as err:
        read_probability_map(tmp_path / "n.fits")
    assert err.value.code == "PROBABILITY_OUT_OF_RANGE"
    write_multiorder(tmp_path / "u.fits", uniq, density, unit="")
    with pytest.raises(MocError) as err:
        read_probability_map(tmp_path / "u.fits")
    assert err.value.code == "PROBABILITY_MAP_INVALID"
    write_multiorder(tmp_path / "g.fits", uniq, density, coordsys="G")
    with pytest.raises(MocError) as err:
        read_probability_map(tmp_path / "g.fits")
    assert err.value.code == "PROBABILITY_MAP_INVALID"


# =============================================================================
# P5 — Lettura da URL, MocServer (T8, T9), build_moc (H9)

from astrotwo.core.cache import NetworkTimeouts  # noqa: E402
from astrotwo.core.moc import build_moc, query_mocserver  # noqa: E402

MOCSERVER_ANSWER = '[{"ID": "CDS/II/246/out", "obs_title": "2MASS"}, {"ID": "CDS/I/355/gaiadr3", "obs_title": "Gaia"}]'


def test_t8_mocserver_simulated(service, cache, monkeypatch):
    import astrotwo.core.vo_protocols as vo

    service.routes["/ms"] = lambda request: (200, "application/json", MOCSERVER_ANSWER)
    monkeypatch.setattr(vo, "MOCSERVER_URL", service.url + "/ms")
    center = SkyCoord(121.17 * u.deg, -21.57 * u.deg, frame=Galactic())  # convertito in ICRS
    result = query_mocserver(CircleRegion(center, 0.1 * u.deg), properties={"ID": "CDS/*"}, cache=cache)
    params = service.requests[-1]["params"]
    icrs = center.icrs
    assert float(params["RA"]) == pytest.approx(icrs.ra.deg, abs=1e-12)
    assert float(params["DEC"]) == pytest.approx(icrs.dec.deg, abs=1e-12) and float(params["SR"]) == 0.1
    assert (params["intersect"], params["spacesys"], params["get"], params["fmt"], params["ID"]) == \
        ("overlaps", "C", "record", "json", "CDS/*")
    assert result.ids == ("CDS/II/246/out", "CDS/I/355/gaiadr3") and result.request.url == service.url + "/ms"
    assert result.request.retrieved_at is not None and "risposta del" in result.description
    again = query_mocserver(CircleRegion(center, 0.1 * u.deg), properties={"ID": "CDS/*"}, cache=cache)
    assert again.request.from_cache and len(service.requests) == 1 and "FROM_CACHE" in dict(again.warnings)
    # MOC come regione: inviato in POST nel parametro moc (testo dello standard).
    moc = moc_from_region(CircleRegion(SkyCoord(10 * u.deg, 41 * u.deg), 0.2 * u.deg), 8)
    query_mocserver(moc, intersect="enclosed", cache=cache)
    last = service.requests[-1]
    assert last["method"] == "POST" and last["params"]["moc"] == moc.moc.to_string("ascii")
    assert last["params"]["intersect"] == "enclosed"
    with pytest.raises(ValueError):
        query_mocserver(moc, intersect="bogus", cache=cache)
    with pytest.raises(ValueError):
        query_mocserver(moc, properties={"moc": "x"}, cache=cache)
    with pytest.raises(TypeError):
        query_mocserver(PolygonRegion(SkyCoord([0, 1, 1] * u.deg, [0, 0, 1] * u.deg)), cache=cache)
    service.routes["/ms"] = lambda request: (200, "text/html", "<html><body><p>Error: STC parsing</p></body></html>")
    with pytest.raises(MocError) as err:
        query_mocserver(moc, cache=cache, refresh=True)
    assert err.value.code == "SERVICE_ERROR"


def test_t9_mocserver_unavailable(cache, monkeypatch):
    import socket

    import astrotwo.core.vo_protocols as vo

    with socket.socket() as sock:  # porta locale libera, nessun servizio in ascolto
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setattr(vo, "MOCSERVER_URL", f"http://127.0.0.1:{port}/ms")
    with pytest.raises(MocError) as err:
        query_mocserver(CircleRegion(SkyCoord(10 * u.deg, 41 * u.deg), 0.1 * u.deg), cache=cache,
                        timeouts=NetworkTimeouts(connect=1.0, read=1.0))
    assert err.value.code == "MOCSERVER_UNAVAILABLE"


def test_read_moc_url(service, cache, tmp_path):
    moc = ascii_moc(tmp_path, "a.txt", 5, [1, 2, 3])
    payload = write_moc(moc, tmp_path / "a.fits").path.read_bytes()
    service.routes["/a.fits"] = lambda request: (200, "application/fits", payload)
    service.routes["/b.json"] = lambda request: (200, "application/json", '{"s": {"5": [7]}}')
    got = read_moc(service.url + "/a.fits", cache=cache)
    assert got == moc and got.version == "2.0" and got.origin == service.url + "/a.fits"
    again = read_moc(service.url + "/a.fits", cache=cache)
    assert again == moc and "FROM_CACHE" in dict(again.warnings) and len(service.requests) == 1
    from_json = read_moc(service.url + "/b.json", cache=cache)
    assert from_json.version == VERSION_NOT_DECLARED
    cached = cache.get("16", f"url-from-json:{service.url}/b.json")
    assert cached.data.startswith(b"SIMPLE") and cached.origin == service.url + "/b.json"  # FITS IVOA (D16-2)
    service.close()  # rete assente: copia in cache, dichiarata
    offline = read_moc(service.url + "/b.json", cache=cache, refresh=True, timeouts=NetworkTimeouts(1.0, 1.0))
    assert offline.moc == from_json.moc and "rete non disponibile" in dict(offline.warnings)["FROM_CACHE"]
    assert "json originale" in offline.version
    with pytest.raises(MocError) as err:
        read_moc(service.url + "/c.fits", cache=cache, timeouts=NetworkTimeouts(1.0, 1.0))
    assert err.value.code == "NET_TIMEOUT"


def test_build_moc(tmp_path):
    from test_crossmatch import make_table

    table = make_table(tmp_path / "c.xml", [10.0, 200.0], [20.0, -30.0])
    image_path = tmp_path / "i.fits"
    write_image(image_path, np.ones((20, 30), dtype=np.float32))
    circle = CircleRegion(SkyCoord(50 * u.deg, 0 * u.deg), 1 * u.deg)
    built = build_moc([circle, table, ("image", image_path)], order_max=8, output=tmp_path / "out.fits")
    # Ricalcolo nel test: unione dei costruttori del modulo con mocpy.
    from astrotwo.core.images_fits import load_image

    expected = moc_from_region(circle, 8).union(moc_from_catalog(table, 8)).union(moc_from_image(load_image(image_path), 8))
    assert built == expected and read_moc(tmp_path / "out.fits") == expected
    assert "build_moc: unione di 3 MOC" in built.history[-2] and "scritto in" in built.history[-1]
    with pytest.raises(TypeError):
        build_moc([str(image_path)], order_max=8)  # il tipo di un file non si indovina
    with pytest.raises(MocError) as err:
        build_moc([circle], order_max=None)
    assert err.value.code == "HEALPIX_ORDER_INVALID"


@pytest.mark.network
def test_t8_mocserver_network(cache):
    m31 = SkyCoord(10.6847 * u.deg, 41.2690 * u.deg)
    result = query_mocserver(CircleRegion(m31, 0.1 * u.deg), properties={"ID": "CDS/II/246*"}, cache=cache)
    assert "CDS/II/246/out" in result.ids and result.request.url.startswith("https://")
    moc = moc_from_region(CircleRegion(m31, 0.1 * u.deg), 9)
    assert "CDS/II/246/out" in query_mocserver(moc, properties={"ID": "CDS/II/246*"}, cache=cache).ids


@pytest.mark.network
def test_read_moc_url_network(cache):
    url = "https://alasky.cds.unistra.fr/MocServer/query?ID=CDS/II/246/out&get=moc&order=3&fmt=fits"
    moc = read_moc(url, cache=cache)
    assert moc.kind == "space" and moc.body == "celestial" and moc.space_order <= 3 and moc.sky_fraction > 0.9
