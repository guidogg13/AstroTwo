# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 15 con codice + ``params`` (D40-3; ``40`` §3.7.1, T18–T19; ``15`` §10).

Provoca ogni errore e ogni avviso del modulo; ogni istanza è controllata contro il catalogo alla creazione
(``tests/conftest.py``) e qui si verifica la copertura di tutte le coppie (codice, ragione) del modulo, gli errori
rilanciati dal 10 e dal 14 e il testo italiano invariato.
"""

from __future__ import annotations

import dataclasses

import astropy.units as u
import pytest

import astrotwo.core.vo_protocols as vo
from astrotwo import messages_catalog as mc
from astrotwo.core.cache import NetworkTimeouts
from astrotwo.core.catalogs import TableLimits
from astrotwo.core.coordinates_wcs import ModuleWarning
from astrotwo.core.crossmatch import (
    CrossmatchError,
    crossmatch,
    crossmatch_by_field,
    crossmatch_cds,
    crossmatch_ellipses,
)
from tests.core.test_crossmatch import ELL, ellipse_tables, make_table, offset, xmatch_route
from tests.message_helpers import MODULE_15_SUBVARIANTS, catalog_combinations, check_error, check_message

OWN_CODES = (
    "KEY_COLUMN_INVALID", "ERROR_ELLIPSE_INVALID", "BODY_NOT_CHECKED", "EPOCH_DIFFERS", "COORD_MISSING", "NO_MATCH",
    "BEST_TIE", "B_REUSED", "COLUMNS_RENAMED", "UCD_CONFLICT", "MAIN_UCD_REMOVED", "KEY_MISSING", "KEY_REPEATED",
    "NO_REQUEST",
)


def required_combinations() -> set[tuple[str, str | None]]:
    out = {(c, r) for c, r in catalog_combinations(OWN_CODES) if r is not None or not mc.CATALOG[c].variants}
    return out | MODULE_15_SUBVARIANTS | {("ERROR_ELLIPSE_INVALID", "singular")}


class Seen:
    def __init__(self) -> None:
        self.pairs: set[tuple[str, str | None]] = set()

    def error(self, func, *args, **kwargs) -> CrossmatchError:
        with pytest.raises(CrossmatchError) as info:
            func(*args, **kwargs)
        self.pairs.add(check_error(info.value))
        return info.value

    def notes(self, items) -> None:
        for item in items:
            if isinstance(item, ModuleWarning):
                self.pairs.add(check_message(item[0], item.params, item[1]))


def test_every_error_and_warning_has_code_params_and_catalog_entry(tmp_path, service, cache, monkeypatch):
    seen = Seen()
    a = make_table(tmp_path / "a.xml", [1.0], [1.0])
    mars = dataclasses.replace(make_table(tmp_path / "m.xml", [1.0], [1.0]), body="Mars")

    # --- incrocio locale ---------------------------------------------------------------------------------------------
    seen.error(crossmatch, a, mars, "best", 2 * u.arcsec)  # tables
    seen.notes(crossmatch(a, mars, "best", 2 * u.arcsec, force_body=True).warnings)  # BODY_FORCED tables
    seen.error(crossmatch, a, dataclasses.replace(a, body=None), "best", 2 * u.arcsec)  # BODY_UNKNOWN
    for bad in (None, 2, 0 * u.arcsec, 181 * u.deg):
        seen.error(crossmatch, a, a, "best", bad)  # required, not_angle, range_local
    seen.error(crossmatch_cds, a, a, "best", 200 * u.arcsec)  # range_cds
    seen.error(crossmatch, a, dataclasses.replace(a, positions=None), "best", 1 * u.arcsec)  # no_positions
    unknown = dataclasses.replace(a, positions=dataclasses.replace(a.positions, frame=None))
    seen.error(crossmatch, a, unknown, "best", 1 * u.arcsec)  # FRAME_UNKNOWN
    plain = make_table(tmp_path / "p.xml", [1.0], [1.0])
    plain.table[plain.positions.lon].unit = None
    seen.error(crossmatch, a, plain, "best", 1 * u.arcsec)  # no_angular_unit
    odd = dataclasses.replace(a, positions=dataclasses.replace(a.positions, frame="nessuno"))
    err = seen.error(crossmatch, a, odd, "best", 1 * u.arcsec)
    assert err.relayed and err.code not in ("NO_COORD_COLUMNS", "FRAME_UNKNOWN") and err.message.startswith("tabella B")
    big = dataclasses.replace(make_table(tmp_path / "c.xml", [1.0, 2.0], [1.0, 2.0]), limits=TableLimits(max_rows=1))
    seen.error(crossmatch, big, a, "best", 1 * u.arcsec)  # crossmatch_table
    seen.notes(crossmatch(a, make_table(tmp_path / "e1.xml", [1.0], [1.0], epoch="J2000"), "best",
                          1 * u.arcsec).warnings)  # senza epoca, nessun avviso
    ep_a = make_table(tmp_path / "ea.xml", [1.0], [1.0], epoch="J2016")
    ep_b = make_table(tmp_path / "eb.xml", [1.0], [1.0], epoch="J2000")
    seen.notes(crossmatch(ep_a, ep_b, "best", 1 * u.arcsec).warnings)  # EPOCH_DIFFERS
    miss_a = make_table(tmp_path / "ma.xml", [1.0, None], [1.0, 2.0])
    seen.notes(crossmatch(miss_a, a, "best", 1 * u.arcsec).warnings)  # COORD_MISSING
    far = make_table(tmp_path / "far.xml", [50.0], [40.0])
    seen.notes(crossmatch(a, far, "best", 1 * u.arcsec).warnings)  # NO_MATCH
    left, right = offset(40.0, 0.0, 270.0, 2.0), offset(40.0, 0.0, 90.0, 2.0)
    centre = make_table(tmp_path / "t_a.xml", [40.0], [0.0])
    ties = make_table(tmp_path / "t_b.xml", [right[0], right[0]], [right[1], right[1]])
    seen.notes(crossmatch(centre, ties, "best", 5 * u.arcsec).warnings)  # BEST_TIE
    one = offset(40.0, 0.0, 0.0, 1.0)
    two = make_table(tmp_path / "a2.xml", [40.0, one[0]], [0.0, one[1]])
    single = make_table(tmp_path / "b2.xml", [40.0], [0.0])
    seen.notes(crossmatch(two, single, "best", 5 * u.arcsec).warnings)  # B_REUSED
    assert left is not None

    # --- tabella unita ---------------------------------------------------------------------------------------------
    ja = make_table(tmp_path / "ja.xml", [10.0, 11.0], [0.0, 0.0], extra={"mag": ("mag", [1.0, 2.0])})
    jb = make_table(tmp_path / "jb.xml", [10.0, 12.0], [0.0, 0.0], extra={"mag": ("mag", [5.0, 6.0])})
    result = crossmatch(ja, jb, "best", 1 * u.arcsec)
    seen.notes(result.joined().warnings)  # COLUMNS_RENAMED, UCD_CONFLICT, MAIN_UCD_REMOVED
    seen.error(result.joined, keep_columns=(["nessuna"], None))  # missing_columns
    seen.error(result.joined, prefixes=("", ""), suffixes=("", ""))  # name_repeated
    pairs = crossmatch(two, single, "all", 5 * u.arcsec)
    small = dataclasses.replace(pairs, table_a=dataclasses.replace(two, limits=TableLimits(max_rows=1)))
    seen.error(small.joined)  # joined

    # --- per campo ---------------------------------------------------------------------------------------------------
    ka = make_table(tmp_path / "ka.xml", [1.0] * 3, [1.0] * 3, extra={"n": (None, [7.0, 7.0, None])})
    kb = make_table(tmp_path / "kb.xml", [1.0] * 3, [1.0] * 3, extra={"n": (None, [7.0, 7.0, 8.0])})
    by_field = crossmatch_by_field(ka, kb, "n", "n")
    seen.notes(by_field.warnings)  # KEY_MISSING, KEY_REPEATED
    seen.error(crossmatch_by_field, ka, kb, "id", "n")  # key_types
    seen.error(crossmatch_by_field, ka, kb, "manca", "n")  # key_missing
    no_body = crossmatch_by_field(ka, dataclasses.replace(kb, body=None, positions=None), "n", "n")
    seen.notes(no_body.warnings)  # BODY_NOT_CHECKED
    seen.notes(no_body.joined(main="b").warnings)  # NO_COORD_COLUMNS joined

    # --- ellissi -----------------------------------------------------------------------------------------------------
    good_a, good_b = ellipse_tables(tmp_path, [(1.0, 1.0, 0.2, 0.1, 0.0)], [(1.0, 1.0, 0.3, 0.1, 0.0)])
    for threshold, axes in ((3 * u.arcsec, "semi"), (None, "semi"), (-1.0, "semi"), (3.0, None)):
        seen.error(crossmatch_ellipses, good_a, good_b, ELL, ELL, threshold, axes=axes)
    seen.error(crossmatch_ellipses, good_a, good_b, ELL[:2], ELL, 3.0, axes="semi")  # three_columns
    seen.error(crossmatch_ellipses, good_a, good_b, ("x", "emin", "epa"), ELL, 3.0, axes="semi")  # column_missing
    bad_a, bad_b = ellipse_tables(tmp_path, [(1.0, 1.0, 0.2, 0.5, 0.0)], [(1.0, 1.0, 0.3, 0.1, 0.0)])
    seen.error(crossmatch_ellipses, bad_a, bad_b, ELL, ELL, 3.0, axes="semi")  # minor_larger
    zero_a, zero_b = ellipse_tables(tmp_path, [(1.0, 1.0, 0.0, 0.0, 0.0)], [(1.0, 1.0, 0.3, 0.1, 0.0)])
    seen.error(crossmatch_ellipses, zero_a, zero_b, ELL, ELL, 3.0, axes="semi")  # axes_not_positive
    unit_a, unit_b = ellipse_tables(tmp_path, [(1.0, 1.0, 0.2, 0.1, 0.0)], [(1.0, 1.0, 0.3, 0.1, 0.0)])
    unit_a.table["emaj"].unit = None
    seen.error(crossmatch_ellipses, unit_a, unit_b, ELL, ELL, 3.0, axes="semi")  # column_unit
    deg_a, deg_b = ellipse_tables(tmp_path, [(1.0, 1.0, 1e-200, 1e-200, 0.0)], [(1.0, 1.0, 1e-200, 1e-200, 0.0)])
    seen.notes(crossmatch_ellipses(deg_a, deg_b, ELL, ELL, 3.0, axes="semi").warnings)  # singular

    # --- servizio CDS ------------------------------------------------------------------------------------------------
    log = []
    service.routes["/xmatch"] = xmatch_route(log, corrupt=True)
    monkeypatch.setattr(vo, "XMATCH_URL", service.url + "/xmatch")
    seen.error(crossmatch_cds, a, a, "best", 2 * u.arcsec, cache=cache)  # echo_mismatch
    empty = make_table(tmp_path / "empty.xml", [None], [None])
    seen.notes(crossmatch_cds(empty, a, "best", 2 * u.arcsec, cache=cache).warnings)  # NO_REQUEST
    monkeypatch.setattr(vo, "XMATCH_URL", "http://127.0.0.1:9/xmatch")
    err = seen.error(crossmatch_cds, a, a, "best", 2 * u.arcsec, cache=cache, timeouts=NetworkTimeouts(0.5, 0.5))
    assert err.relayed and err.code == "NET_TIMEOUT"

    missing = required_combinations() - seen.pairs
    assert not missing, f"errori e avvisi del 15 mai provocati nel test: {sorted(missing, key=str)}"


def test_italian_text_is_unchanged_and_catalog_renders_both_languages(tmp_path):
    a = make_table(tmp_path / "a.xml", [1.0], [1.0])
    with pytest.raises(CrossmatchError) as info:
        crossmatch(a, a, "best", 181 * u.deg)
    err = info.value
    assert err.params == {"reason": "range_local", "max_sep": {"value": 181.0, "unit": "deg"},
                          "limit": {"value": 180.0, "unit": "deg"}}
    assert err.message == "max_sep 181.0 deg: ammesso in (0, 180.0 deg] in locale"
    assert mc.message_text(err.code, err.params, "en") == "max_sep 181.0 deg: allowed in (0, 180.0 deg] locally."
    assert mc.message_text(err.code, err.params, "it") == "max_sep 181.0 deg: ammesso in (0, 180.0 deg] in locale."
