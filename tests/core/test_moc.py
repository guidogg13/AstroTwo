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
