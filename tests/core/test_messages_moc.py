# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 16 con codice + ``params`` (D40-3, D40-7; ``40`` §3.7.1, T18–T19; ``16`` §10).

Provoca ogni errore e ogni avviso del modulo; ogni istanza è controllata contro il catalogo alla creazione
(``tests/conftest.py``) e qui si verifica la copertura di tutte le coppie (codice, ragione) del modulo, i messaggi
annidati, gli errori rilanciati dal 10 e dal 14 e il testo italiano invariato.
"""

from __future__ import annotations

import dataclasses
import socket
from dataclasses import replace
from types import SimpleNamespace

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.table import Table
from astropy.time import Time
from mocpy import MOC

import astrotwo.core.vo_protocols as vo
from astrotwo import messages_catalog as mc
from astrotwo.core.cache import NetworkTimeouts
from astrotwo.core.coordinates_wcs import CoordinatesWcsError, ModuleWarning, SkyFrame
from astrotwo.core.moc import (
    CircleRegion,
    Moc,
    MocError,
    PolygonRegion,
    build_moc,
    filter_by_moc,
    healpix_grid,
    healpix_map,
    moc_from_catalog,
    moc_from_image,
    moc_from_probability,
    moc_from_region,
    moc_from_times,
    moc_space_time,
    query_mocserver,
    read_moc,
    read_probability_map,
    write_moc,
)
from tests.core.test_moc import (  # noqa: F401  (costruttori di file e tabelle di prova del 16)
    ascii_moc,
    reference_space,
    synthetic_multiorder,
    write_fits_v1,
    write_fits_v2_range,
    write_image,
    write_multiorder,
)
from tests.message_helpers import MODULE_14_SUBVARIANTS, MODULE_19_SUBVARIANTS, catalog_combinations, check_error, check_message, nested_pairs

#: Codici che solo il modulo 16 solleva o restituisce.
OWN_CODES = (
    "BODY_MISMATCH", "MOC_TYPE_MISMATCH", "MOC_UNREADABLE", "MOC_VERSION_UNSUPPORTED", "MOC_TYPE_REQUIRED",
    "MOC_BODY_UNSUPPORTED", "GRID_TOO_LARGE", "TIME_RANGE_INVALID", "PROBABILITY_MAP_INVALID",
    "PROBABILITY_OUT_OF_RANGE", "PROBABILITY_SUM_INVALID", "BODY_FORCED", "MOC_EMPTY", "MOC_VERSION_ASSUMED",
    "MOC_NONSTANDARD_EXTENSION", "ROWS_EXCLUDED", "VALUES_EXCLUDED", "POINTS_OUTSIDE_PROJECTION", "ORDER_DEGRADED",
    "CREDIBLE_PROBABILITY",
)
#: Sotto-voci aggiunte a voci condivise con altri moduli.
SHARED = {
    ("HEALPIX_ORDER_INVALID", "moc_order"), ("HEALPIX_ORDER_INVALID", "map_too_large"),
    ("BODY_UNKNOWN", "moc_without_body"), ("BODY_UNKNOWN", "no_moc"), ("BODY_UNKNOWN", "no_filter"),
    ("REGION_INVALID", "conversion"), ("REGION_INVALID", "not_finite"), ("REGION_INVALID", "polygon_vertices"),
    ("REGION_INVALID", "polygon_mocpy"), ("REGION_INVALID", "radius_not_angle"), ("REGION_INVALID", "radius_range"),
    ("REGION_INVALID", "center_not_single"), ("REGION_INVALID", "radius"),
    ("NO_COORD_COLUMNS", "no_positions"), ("NO_COORD_COLUMNS", "no_angular_unit"),
    ("FRAME_UNKNOWN", "columns_without_frame"), ("PREVIEW_NOT_MEASURABLE", "moc_from_image"),
    ("OPERATION_UNSUPPORTED", "color_image"), ("WCS_MISSING", "image_without_wcs"),
    ("MOCSERVER_UNAVAILABLE", "filter"), ("SERVICE_ERROR", "mocserver_response"), ("NET_TIMEOUT", "url"),
    ("FROM_CACHE", "cached_origin"), ("FROM_CACHE", "cached_converted"), ("FROM_CACHE", "network_cached"),
}


def required_combinations() -> set[tuple[str, str | None]]:
    """Coppie (codice, ragione) del 16: ogni sotto-voce; la voce generale solo dove non ha sotto-voci o è usata."""
    out = {(c, r) for c, r in catalog_combinations(OWN_CODES) if r is not None or not mc.CATALOG[c].variants}
    # voci generali usate dal modulo anche se hanno sotto-voci
    return out | {("ROWS_EXCLUDED", None)} | SHARED


class Seen:
    def __init__(self) -> None:
        self.pairs: set[tuple[str, str | None]] = set()

    def error(self, func, *args, **kwargs) -> MocError:
        with pytest.raises(MocError) as info:
            func(*args, **kwargs)
        self.pairs.add(check_error(info.value))
        self.pairs |= nested_pairs(info.value.code, info.value.params)
        return info.value

    def notes(self, items) -> None:
        for item in items:
            if isinstance(item, ModuleWarning):
                self.pairs.add(check_message(item[0], item.params, item[1]))
                self.pairs |= nested_pairs(item[0], item.params)


def test_every_error_and_warning_has_code_params_and_catalog_entry(tmp_path, service, cache, monkeypatch):
    from tests.core.test_crossmatch import make_table

    seen = Seen()
    table = make_table(tmp_path / "c.xml", [10.0, 200.0, None], [20.0, -30.0, None])
    a = ascii_moc(tmp_path, "a.txt", 3, [1, 2])
    b = ascii_moc(tmp_path, "b.txt", 3, [2, 3])
    mars = Moc(moc=b.moc, kind="space", body="Mars", origin="dati di prova")
    moon = Moc(moc=b.moc, kind="space", body="Moon", origin="dati di prova")
    tpath = tmp_path / "t.json"
    tpath.write_text('{"t": {"30": [5, 6]}}')
    time = read_moc(tpath)

    # --- corpi e tipi ------------------------------------------------------------------------------------------------
    seen.error(a.union, mars)  # different_bodies
    seen.notes(a.union(mars, force_body=True).warnings)  # BODY_FORCED forced
    mixed = a.intersection(moon, force_body=True)
    seen.error(mixed.union, a)  # different_bodies (MOC misto)
    seen.error(mixed.complement)  # mixed_operation
    seen.notes(mixed.complement(force_body=True).warnings)  # BODY_FORCED mixed
    seen.error(Moc, moc=a.moc, kind="space", body=None, origin="x")  # moc_without_body
    seen.error(a.union, time)  # operation
    seen.error(time.contains, SkyCoord([0.0] * u.deg, [0.0] * u.deg))  # contains_positions
    seen.error(a.contains_times, Time([2459000.5], format="jd", scale="tcb"))  # contains_times
    times = Time([2459000.5, 2459100.5], format="jd", scale="tcb")
    coords = SkyCoord([10.0, 200.0] * u.deg, [20.0, -30.0] * u.deg)
    st = moc_space_time(times, None, coords, time_order=30, space_order=8)
    seen.error(st.space_during, a)  # space_during
    seen.error(st.time_within, time)  # time_within (tipo)
    around = moc_from_region(CircleRegion(SkyCoord(200 * u.deg, -30 * u.deg), 0.5 * u.deg), 8)
    seen.error(st.time_within, replace(around, body="Mars"))  # different_bodies
    seen.notes(st.time_within(replace(around, body="Mars"), force_body=True).warnings)  # BODY_FORCED within
    write_fits_v1(tmp_path / "s.fits", 4, [1])
    seen.error(read_moc, tmp_path / "s.fits", kind="time")  # file
    seen.error(filter_by_moc, table, time)  # filter
    seen.error(healpix_grid, 3, within=time)  # grid_within
    seen.error(build_moc, [time], order_max=5)  # build_moc
    seen.error(query_mocserver, time, cache=cache)  # mocserver_filter

    # --- lettura -----------------------------------------------------------------------------------------------------
    seen.error(read_moc, tmp_path / "manca.fits")  # read_error
    fits.HDUList([fits.PrimaryHDU()]).writeto(tmp_path / "nobin.fits")
    seen.error(read_moc, tmp_path / "nobin.fits")  # no_binary_table
    write_fits_v2_range(tmp_path / "m1.fits", "SPACE", 4, [[0, 10]], {"A2BODY": "mixed"})
    seen.error(read_moc, tmp_path / "m1.fits")  # mixed_without_bodies
    write_fits_v2_range(tmp_path / "m2.fits", "SPACE", 4, [[0, 10]], {"A2BODY": " "})
    seen.error(read_moc, tmp_path / "m2.fits")  # body_empty
    write_fits_v2_range(tmp_path / "m3.fits", "SPACE", 4, [[0, 10]], {"MOCDIM": "FOO"})
    seen.error(read_moc, tmp_path / "m3.fits")  # mocdim
    write_fits_v1(tmp_path / "g.fits", 4, [1], {"COORDSYS": "G"})
    seen.error(read_moc, tmp_path / "g.fits")  # coordsys
    (tmp_path / "bad.txt").write_text("1/zzz")
    seen.error(read_moc, tmp_path / "bad.txt", kind="space")  # mocpy_error
    (tmp_path / "bad.json").write_text("{")
    seen.error(read_moc, tmp_path / "bad.json")  # json_syntax
    (tmp_path / "cells.json").write_text('{"3": [5, "x"]}')
    seen.error(read_moc, tmp_path / "cells.json", kind="space")  # json_cells
    (tmp_path / "list.json").write_text('[{"x": 1}]')
    seen.error(read_moc, tmp_path / "list.json")  # json_st_list
    (tmp_path / "empty.txt").write_text("")
    seen.error(read_moc, tmp_path / "empty.txt", format="ascii")  # empty_text
    (tmp_path / "latin.txt").write_bytes(b"\xff\xfe 3/1")
    seen.error(read_moc, tmp_path / "latin.txt", format="ascii")  # not_utf8
    write_fits_v1(tmp_path / "v21.fits", 4, [1], {"MOCVERS": "2.1", "MOCDIM": "SPACE", "MOCORD_S": 4})
    seen.error(read_moc, tmp_path / "v21.fits")  # unsupported_2_1
    write_fits_v1(tmp_path / "v3.fits", 4, [1], {"MOCVERS": "3.0"})
    seen.error(read_moc, tmp_path / "v3.fits")  # unsupported
    write_fits_v2_range(tmp_path / "utc.fits", "TIME", 30, [[0, 10]], {"TIMESYS": "UTC"})
    seen.error(read_moc, tmp_path / "utc.fits")  # timesys
    plain = tmp_path / "plain.json"
    plain.write_text('{"3": [5, 6, 7]}')
    seen.error(read_moc, plain)  # TYPE_REQUIRED json
    text = tmp_path / "plain.txt"
    text.write_text("3/5-7")
    seen.error(read_moc, text)  # TYPE_REQUIRED ascii
    write_fits_v1(tmp_path / "v11.fits", 4, [1])
    seen.notes(read_moc(tmp_path / "v11.fits").warnings)  # MOC_VERSION_ASSUMED
    (tmp_path / "e.txt").write_text("5/")
    seen.notes(read_moc(tmp_path / "e.txt", kind="space").warnings)  # MOC_EMPTY source
    seen.notes(a.intersection(read_moc(tmp_path / "e.txt", kind="space")).warnings)  # MOC_EMPTY operation
    seen.notes(moc_from_times(Time(np.array([]), format="jd", scale="tcb"), order_max=30).warnings)  # MOC_EMPTY

    # --- scrittura ---------------------------------------------------------------------------------------------------
    for fmt in ("json", "ascii"):
        seen.error(write_moc, mars, tmp_path / f"mars.{fmt}", format=fmt)  # format
    written = write_moc(mars, tmp_path / "mars.fits")
    seen.notes(written.warnings)  # MOC_NONSTANDARD_EXTENSION write
    seen.notes(read_moc(written).warnings)  # MOC_NONSTANDARD_EXTENSION read

    # --- creazione ---------------------------------------------------------------------------------------------------
    center = SkyCoord(150 * u.deg, 2 * u.deg)
    seen.error(moc_from_region, CircleRegion(center, 1.0), 9)  # radius_not_angle
    seen.error(moc_from_region, CircleRegion(center, 181 * u.deg), 9)  # radius_range
    seen.error(moc_from_region, CircleRegion(SkyCoord([1, 2] * u.deg, [3, 4] * u.deg), 1 * u.deg), 9)  # center_not_single
    seen.error(moc_from_region, PolygonRegion(SkyCoord([0, 90] * u.deg, [0, 0] * u.deg)), 7)  # polygon_vertices
    triangle = SkyCoord([0.0, 90.0, 0.0] * u.deg, [0.0, 0.0, 89.0] * u.deg)
    with monkeypatch.context() as patch:  # mocpy rifiuta i poligoni non validi con un'eccezione (qui simulata)
        patch.setattr(MOC, "from_polygon", classmethod(lambda cls, **kwargs: (_ for _ in ()).throw(ValueError("x"))))
        err = seen.error(moc_from_region, PolygonRegion(triangle), 7)  # polygon_mocpy
    assert err.params["reason"] == "polygon_mocpy"
    seen.error(moc_from_region, CircleRegion(center, 1 * u.deg), None)  # moc_order
    icrs_point = SkyFrame.from_lonlat(10 * u.deg, 5 * u.deg, "icrs")
    with monkeypatch.context() as patch:  # coordinate non finite dopo la conversione (difesa del modulo)
        patch.setattr(SkyFrame, "lon", property(lambda self: np.nan * u.deg))
        seen.error(moc_from_region, CircleRegion(icrs_point, 1 * u.deg), 9)  # not_finite
    galactic_point = SkyFrame.from_lonlat(10 * u.deg, 5 * u.deg, "galactic")
    with monkeypatch.context() as patch:  # errore del 10 nella conversione in ICRS
        def refuse(self, frame, **kwargs):
            raise CoordinatesWcsError("COORD_OUT_OF_RANGE", "coordinate non finite", params={"reason": "not_finite"})

        patch.setattr(SkyFrame, "to", refuse)
        err = seen.error(moc_from_region, CircleRegion(galactic_point, 1 * u.deg), 9)  # conversion
    assert err.params["reason"] == "conversion" and err.params["cause"]["code"] == "COORD_OUT_OF_RANGE"
    seen.error(moc_from_catalog, dataclasses.replace(table, positions=None), 10)  # no_positions
    seen.error(moc_from_catalog, dataclasses.replace(table, body="Mars"), 10)  # not_celestial
    seen.error(moc_from_catalog, dataclasses.replace(table, body=None), 10)  # no_moc
    seen.error(filter_by_moc, dataclasses.replace(table, body=None), a)  # no_filter
    seen.error(filter_by_moc, table, mars)  # table_vs_moc
    seen.notes(filter_by_moc(table, mars, force_body=True).warnings)  # BODY_FORCED filter
    pos = table.positions
    seen.error(moc_from_catalog, dataclasses.replace(table, positions=replace(pos, frame=None)), 10)  # without_frame
    table.table[pos.lon].unit = None
    seen.error(moc_from_catalog, table, 10)  # no_angular_unit
    table.table[pos.lon].unit = u.deg
    err = seen.error(moc_from_catalog, dataclasses.replace(table, positions=replace(pos, frame="nessuno")), 10)
    assert err.relayed and err.code != "MOC_UNREADABLE"  # errore del 10 rilanciato con i suoi params
    seen.notes(moc_from_catalog(table, 10).warnings)  # ROWS_EXCLUDED
    seen.notes(filter_by_moc(table, a).warnings)  # ROWS_EXCLUDED never_selected
    seen.error(healpix_map, table, 13)  # map_too_large
    values = make_table(tmp_path / "v.xml", [10.0, 200.0], [20.0, -30.0], extra={"flux": ("Jy", [1.0, None])})
    seen.notes(healpix_map(values, 4, column="flux").warnings)  # VALUES_EXCLUDED
    seen.error(moc_from_image, SimpleNamespace(is_preview=True), 8)  # moc_from_image
    seen.error(moc_from_image, SimpleNamespace(is_preview=False, color=True), 8)  # color_image
    seen.error(moc_from_image, write_image(tmp_path / "n.fits", np.ones((5, 5)), wcs=False), 8)  # image_without_wcs
    header = fits.Header({"CTYPE1": "RA---SIN", "CTYPE2": "DEC--SIN", "CRVAL1": 150.0, "CRVAL2": 2.0, "CRPIX1": 100.5,
                          "CRPIX2": 100.5, "CDELT1": -1.0, "CDELT2": 1.0, "CUNIT1": "deg", "CUNIT2": "deg",
                          "RADESYS": "ICRS"})
    fits.PrimaryHDU(data=np.ones((200, 200), dtype=np.float32), header=header).writeto(tmp_path / "sin.fits")
    from astrotwo.core.images_fits import load_image

    seen.notes(moc_from_image(load_image(tmp_path / "sin.fits"), 3).warnings)  # POINTS_OUTSIDE_PROJECTION
    seen.error(healpix_grid, 8)  # full_sky
    big = moc_from_region(CircleRegion(SkyCoord(10 * u.deg, 5 * u.deg), 90 * u.deg), 6)
    seen.error(healpix_grid, 8, within=big)  # within

    # --- tempi -------------------------------------------------------------------------------------------------------
    start = Time(["2020-01-01T00:00:00", "2020-03-01T00:00:00"], scale="utc")
    end = Time(["2020-01-02T00:00:00", "2020-03-01T12:00:00"], scale="utc")
    seen.error(moc_from_times, end, start, order_max=40)  # end_before_start
    seen.error(moc_from_times, start, end[:1], order_max=40)  # different_counts
    seen.error(moc_from_times, Time(-1.0, format="jd", scale="tcb"), order_max=40)  # before_jd0
    with monkeypatch.context() as patch:  # astropy non crea istanti non finiti: difesa del modulo (JD simulato)
        patch.setattr(Time, "jd", property(lambda self: np.array([np.inf])), raising=False)
        seen.error(moc_from_times, Time(2459000.5, format="jd", scale="tcb"), order_max=40)  # not_finite
    seen.error(moc_space_time, times, None, coords[:1], time_order=30, space_order=8)  # counts_mismatch
    seen.error(moc_space_time, times, times[::-1], coords, time_order=30, space_order=8)  # invalid_intervals

    # --- mappe di probabilità ------------------------------------------------------------------------------------------
    uniq, density, _, _ = synthetic_multiorder()
    seen.error(read_probability_map, tmp_path / "manca.fits")  # read_error
    fits.HDUList([fits.PrimaryHDU()]).writeto(tmp_path / "pnobin.fits")
    seen.error(read_probability_map, tmp_path / "pnobin.fits")  # no_table
    write_multiorder(tmp_path / "pg.fits", uniq, density, coordsys="G")
    seen.error(read_probability_map, tmp_path / "pg.fits")  # coordsys
    write_multiorder(tmp_path / "pu.fits", uniq, density, unit="m")
    seen.error(read_probability_map, tmp_path / "pu.fits")  # density_unit
    flat = fits.BinTableHDU.from_columns([fits.Column(name="PROB", format="1D", array=np.full(12, 1 / 12))])
    flat.header.update({"PIXTYPE": "HEALPIX", "ORDERING": "FOO", "NSIDE": 1, "COORDSYS": "C"})
    fits.HDUList([fits.PrimaryHDU(), flat]).writeto(tmp_path / "pord.fits")
    seen.error(read_probability_map, tmp_path / "pord.fits")  # ordering
    flat.header["ORDERING"], flat.header["NSIDE"] = "NESTED", 3
    fits.HDUList([fits.PrimaryHDU(), flat]).writeto(tmp_path / "pnside.fits")
    seen.error(read_probability_map, tmp_path / "pnside.fits")  # nside
    flat.header["NSIDE"] = 1
    flat.data["PROB"][0] = 2.0
    fits.HDUList([fits.PrimaryHDU(), flat]).writeto(tmp_path / "pover.fits")
    seen.error(read_probability_map, tmp_path / "pover.fits")  # cell_probability
    other = fits.BinTableHDU.from_columns([fits.Column(name="X", format="1D", array=np.zeros(3))])
    other.header["COORDSYS"] = "C"
    fits.HDUList([fits.PrimaryHDU(), other]).writeto(tmp_path / "pcols.fits")
    seen.error(read_probability_map, tmp_path / "pcols.fits")  # no_columns
    write_multiorder(tmp_path / "pneg.fits", uniq, np.where(np.arange(uniq.size) == 0, -density, density))
    seen.error(read_probability_map, tmp_path / "pneg.fits")  # density
    write_multiorder(tmp_path / "psum.fits", uniq, density * (1 + 1e-5))
    seen.error(read_probability_map, tmp_path / "psum.fits")  # PROBABILITY_SUM_INVALID
    write_multiorder(tmp_path / "pbig.fits", uniq[:1], np.array([1e9]))
    seen.error(read_probability_map, tmp_path / "pbig.fits")  # cell_over_one
    invalid = np.array([4 + i for i in range(12)] + [1], dtype=np.int64)  # ultima cella non valida, densità 0
    write_multiorder(tmp_path / "pbad.fits", invalid, np.array([1.0 / (4 * np.pi)] * 12 + [0.0]))
    seen.error(read_probability_map, tmp_path / "pbad.fits")  # bad_uniq
    write_multiorder(tmp_path / "pok.fits", uniq, density)
    pmap = read_probability_map(tmp_path / "pok.fits")
    seen.error(moc_from_probability, pmap, 1.5, 2)  # level
    coarse = moc_from_probability(pmap, 0.9, 1)
    seen.notes(coarse.warnings)  # ORDER_DEGRADED, CREDIBLE_PROBABILITY

    # --- rete: MocServer e URL -----------------------------------------------------------------------------------------
    monkeypatch.setattr(vo, "MOCSERVER_URL", service.url + "/ms")
    circle = CircleRegion(SkyCoord(10 * u.deg, 41 * u.deg), 0.1 * u.deg)
    seen.error(query_mocserver, CircleRegion(SkyCoord(10 * u.deg, 41 * u.deg), 5), cache=cache)  # radius
    service.routes["/ms"] = lambda request: (200, "text/html", "<html><body><p>Error: STC parsing</p></body></html>")
    err = seen.error(query_mocserver, circle, cache=cache)  # mocserver_response
    assert err.params["reason"] == "mocserver_response" and "Error: STC" in err.params["body"]
    service.routes["/ms"] = lambda request: (500, "text/plain", "boom")
    err = seen.error(query_mocserver, circle, cache=cache, refresh=True)  # errore del 14 rilanciato
    assert err.relayed and err.code == "SERVICE_ERROR" and err.params["reason"] == "http_status"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setattr(vo, "MOCSERVER_URL", f"http://127.0.0.1:{port}/ms")
    err = seen.error(query_mocserver, circle, cache=cache, timeouts=NetworkTimeouts(connect=0.5, read=0.5))
    assert err.params["reason"] == "filter" and err.params["cause"]["code"] == "NET_TIMEOUT"

    moc = ascii_moc(tmp_path, "u.txt", 5, [1, 2, 3])
    payload = write_moc(moc, tmp_path / "u.fits").path.read_bytes()
    service.routes["/a.fits"] = lambda request: (200, "application/fits", payload)
    service.routes["/b.json"] = lambda request: (200, "application/json", '{"s": {"5": [7]}}')
    seen.notes(read_moc(service.url + "/a.fits", cache=cache).warnings)
    seen.notes(read_moc(service.url + "/a.fits", cache=cache).warnings)  # cached_origin
    read_moc(service.url + "/b.json", cache=cache)
    seen.notes(read_moc(service.url + "/b.json", cache=cache).warnings)  # cached_converted
    service.close()
    seen.notes(read_moc(service.url + "/b.json", cache=cache, refresh=True,
                        timeouts=NetworkTimeouts(0.5, 0.5)).warnings)  # network_cached
    seen.error(read_moc, service.url + "/c.fits", cache=cache, timeouts=NetworkTimeouts(0.5, 0.5))  # NET_TIMEOUT url

    missing = required_combinations() - seen.pairs - MODULE_14_SUBVARIANTS - MODULE_19_SUBVARIANTS
    assert not missing, f"errori e avvisi del 16 mai provocati nel test: {sorted(missing, key=str)}"


def test_italian_text_is_unchanged_and_catalog_renders_both_languages(tmp_path):
    a = ascii_moc(tmp_path, "a.txt", 3, [1, 2])
    tpath = tmp_path / "t.json"
    tpath.write_text('{"t": {"30": [5, 6]}}')
    time = read_moc(tpath)
    with pytest.raises(MocError) as info:
        a.union(time)
    err = info.value
    assert err.message == "operazione tra un MOC space e un MOC time: tipi diversi (unità diverse)"
    assert err.params == {"reason": "operation", "kind": "space", "other": "time"}
    assert mc.message_text(err.code, err.params, "en") == (
        "Operation between a space MOC and a time MOC: different types (different units).")
    assert mc.message_text(err.code, err.params, "it") == (
        "Operazione tra un MOC space e un MOC time: tipi diversi (unità diverse).")
    with pytest.raises(MocError) as info:
        read_moc(tmp_path / "manca.fits")
    assert info.value.params["reason"] == "read_error" and info.value.params["path"] == str(tmp_path / "manca.fits")
    assert reference_space(3, [1]) is not None and Table is not None


def test_moc_error_params_are_json(tmp_path):
    import json

    with pytest.raises(MocError) as info:
        read_moc(tmp_path / "manca.fits")
    json.dumps(info.value.params)
