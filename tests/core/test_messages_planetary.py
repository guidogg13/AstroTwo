# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Messaggi del modulo 19 con codice + ``params`` (D40-3, D40-7; ``40`` §3.7.1, T18–T19; ``19`` §10).

Provoca ogni errore e ogni avviso del modulo; ogni istanza è controllata contro il catalogo alla creazione
(``tests/conftest.py``) e qui si verifica la copertura di tutte le coppie (codice, ragione) del modulo, i messaggi
annidati, gli errori del 14 rilanciati e il testo italiano invariato.
"""

from __future__ import annotations

from types import SimpleNamespace

import astropy.units as u
import numpy as np
import pytest

from astrotwo import messages_catalog as mc
from astrotwo.core import planetary_data as pd
from astrotwo.core.coordinates_wcs import ModuleWarning
from astrotwo.core.moc import Moc
from astrotwo.core.planetary_data import (
    CELESTIAL,
    PlanetaryBody,
    PlanetaryDataError,
    PlanetaryPosition,
    _bodies_of,
    body_of,
    check_overlay,
    load_pds_image,
    normalize_body_name,
    query_epntap,
)
from tests.core.test_moc import write_image
from tests.core.test_planetary_data import (  # noqa: F401  (costruttori di dati di prova del 19)
    epn_votable,
    hips,
    pd_catalog,
    pds4_product,
    planetary_on,
)
from tests.message_helpers import MODULE_14_SUBVARIANTS, MODULE_15_SUBVARIANTS, catalog_combinations, check_error, check_message, nested_pairs

#: Codici che solo il modulo 19 solleva o restituisce (sotto-voci di voci condivise in ``SHARED``).
OWN_CODES = (
    "PLANETARY_DATA_DISABLED", "PLANETARY_KERNEL_INVALID", "BODY_CAUSE", "BODY_MISMATCH_FORCED",
    "PLANETARY_CONVENTION_REQUIRED", "PDS_UNREADABLE", "PDS_STRUCTURE_CHOICE_REQUIRED", "PLANETARY_CONVENTIONS",
    "PDS_SPECIAL_CONSTANTS", "PDS_DOWNLOADED", "PDS_DOWNLOAD",
)
SHARED = (
    {("BODY_UNSUPPORTED", r) for r in ("no_name", "celestial", "no_naif", "not_in_table")}
    | {("BODY_UNKNOWN", r) for r in ("layer", "overlay_unknown", "layer_alone", "epntap_columns", "epntap_frames",
                                     "epntap_target", "pds_target", "pds_targets")}
    | {("BODY_MISMATCH", "multiple_in_layer"), ("BODY_MISMATCH", "overlay"), ("ADQL_INVALID", "epntap_core"),
       ("BODY_NORMALIZED", "pds_target"), ("BODY_NORMALIZED", "epntap_target")}
    | {("COORD_OUT_OF_RANGE", r) for r in ("planetary_not_finite", "planetary_latitude", "planetary_longitude")}
)


def required_combinations() -> set[tuple[str, str | None]]:
    out = {(c, r) for c, r in catalog_combinations(OWN_CODES) if r is not None or not mc.CATALOG[c].variants}
    return out | SHARED


class Seen:
    def __init__(self) -> None:
        self.pairs: set[tuple[str, str | None]] = set()

    def error(self, func, *args, **kwargs) -> PlanetaryDataError:
        with pytest.raises(PlanetaryDataError) as info:
            func(*args, **kwargs)
        self.pairs.add(check_error(info.value))
        self.pairs |= nested_pairs(info.value.code, info.value.params)
        return info.value

    def notes(self, items) -> None:
        for item in items:
            if isinstance(item, ModuleWarning):
                self.pairs.add(check_message(item[0], item.params, item[1]))
                self.pairs |= nested_pairs(item[0], item.params)

    def cause(self, layer) -> None:
        _, text, cause = _bodies_of(layer)
        self.pairs.add(check_message(cause["code"], cause["params"], text))
        self.pairs |= nested_pairs(cause["code"], cause["params"])


def test_every_error_and_warning_has_code_params_and_catalog_entry(tmp_path, service, cache, monkeypatch):
    seen = Seen()
    # --- opzione, kernel, nomi ---------------------------------------------------------------------------------------
    seen.error(PlanetaryBody.from_name, "Mars")  # PLANETARY_DATA_DISABLED
    pd.set_planetary_data_enabled(True)
    try:
        altered = tmp_path / "pck00011.tpc"
        altered.write_bytes(pd.KERNEL_PATH.read_bytes() + b"\n")
        with monkeypatch.context() as patch:
            patch.setattr(pd, "KERNEL_PATH", altered)
            patch.setattr(pd, "_KERNEL_LOADED", False)
            seen.error(PlanetaryBody.from_name, "Mars")  # digest
            patch.setattr(pd, "KERNEL_PATH", tmp_path / "manca.tpc")
            seen.error(PlanetaryBody.from_name, "Mars")  # unreadable
        seen.error(normalize_body_name, "")  # no_name
        seen.error(normalize_body_name, "celestial")  # celestial
        seen.error(normalize_body_name, "Foobar")  # no_naif
        seen.error(normalize_body_name, "Vesta")  # not_in_table

        # --- corpi e sovrapposizioni -----------------------------------------------------------------------------------
        unknown = hips("mars", None, "senza_corpo")
        seen.error(body_of, unknown)  # layer
        seen.notes(check_overlay([unknown]).warnings)  # layer_alone
        seen.error(check_overlay, [unknown, hips("mars", "mars", "marte")])  # overlay_unknown
        mars, moon = hips("mars", "mars", "marte"), hips("moon", "moon", "luna")
        seen.error(check_overlay, [mars, moon])  # overlay
        seen.notes(check_overlay([mars, moon], force=True).warnings)  # BODY_MISMATCH_FORCED
        mixed = Moc(moc=__import__("mocpy").MOC.from_string("3/1"), kind="space", body="mixed",
                    bodies=("Mars", "Moon"), origin="misto")
        seen.error(body_of, mixed)  # multiple_in_layer
        # motivi (BODY_CAUSE): ogni tipo di livello
        image_wcs = write_image(tmp_path / "w.fits", np.ones((4, 4)))
        image_plain = write_image(tmp_path / "n.fits", np.ones((4, 4)), wcs=False)
        time_moc = Moc(moc=__import__("mocpy").TimeMOC.from_string("30/5"), kind="time", body=None, origin="tempo") \
            if hasattr(__import__("mocpy").TimeMOC, "from_string") else None
        for layer in (image_wcs, image_plain, pd_catalog(None), pd_catalog("Foobar"), mars, mixed):
            seen.cause(layer)
        if time_moc is not None:
            seen.cause(time_moc)
        pds_dir = tmp_path / "pds"
        pds_dir.mkdir()
        path, _ = pds4_product(pds_dir)
        image = load_pds_image(str(path))
        seen.cause(image)  # pds_label
        seen.notes(image.warnings)  # BODY_NORMALIZED pds_target, PDS_SPECIAL_CONSTANTS
        seen.cause(pd.dataclasses.replace(image, body=None))  # pds_no_body

        # --- convenzioni e coordinate ---------------------------------------------------------------------------------
        seen.error(PlanetaryPosition, 10 * u.deg, 5 * u.deg, "Mars", "boh", "east")  # PLANETARY_CONVENTION_REQUIRED
        seen.error(PlanetaryPosition, 10 * u.deg, np.nan * u.deg, "Mars", "planetocentric", "east")
        seen.error(PlanetaryPosition, 10 * u.deg, 95 * u.deg, "Mars", "planetocentric", "east")
        seen.error(PlanetaryPosition, 400 * u.deg, 5 * u.deg, "Mars", "planetocentric", "east")

        # --- EPN-TAP ---------------------------------------------------------------------------------------------------
        current = {"payload": epn_votable(["Mars", "Mars"], ["body", "body"])}
        service.routes["/epn/sync"] = lambda request: (200, "application/x-votable+xml", current["payload"])
        adql = "SELECT * FROM mars_data.epn_core WHERE target_name = 'Mars'"
        seen.notes(query_epntap(service.url + "/epn", adql, cache=cache).table.warnings)  # epntap_target, CONVENTIONS
        seen.error(query_epntap, service.url + "/epn", "SELECT * FROM stelle", cache=cache)  # epntap_core
        err = seen.error(query_epntap, "http://127.0.0.1:9/epn", adql, cache=cache)
        assert err.relayed and err.code == "NET_TIMEOUT"
        current["payload"] = epn_votable(["Mars", "Moon"], ["body", "body"])
        seen.notes(query_epntap(service.url + "/epn", adql.replace("'Mars'", "'Moon'"), cache=cache).table.warnings)
        current["payload"] = epn_votable(["Foobar", "Foobar"], ["body", "body"])
        seen.notes(query_epntap(service.url + "/epn", adql.replace("'Mars'", "'Foobar'"), cache=cache).table.warnings)
        current["payload"] = epn_votable(["Mars"], ["body"]).replace(b"target_name", b"altro_nome")
        seen.notes(query_epntap(service.url + "/epn", adql.replace("'Mars'", "'X'"), cache=cache).table.warnings)

        # --- PDS4 ------------------------------------------------------------------------------------------------------
        (tmp_path / "two").mkdir()
        two, _ = pds4_product(tmp_path / "two", images=2)
        seen.error(load_pds_image, str(two))  # several
        seen.error(load_pds_image, str(two), structure="NOPE")  # absent
        (tmp_path / "multi").mkdir()
        multi, _ = pds4_product(tmp_path / "multi", targets=("Mars", "Phobos"))
        seen.notes(load_pds_image(str(multi)).warnings)  # pds_targets
        (tmp_path / "foo").mkdir()
        foo, _ = pds4_product(tmp_path / "foo", targets=("Foobar",))
        seen.notes(load_pds_image(str(foo)).warnings)  # BODY_UNKNOWN pds_target
        pds3 = tmp_path / "old.lbl"
        pds3.write_text("PDS_VERSION_ID = PDS3\nEND\n")
        seen.error(load_pds_image, str(pds3))  # pds3
        seen.error(load_pds_image, "ftp://example.invalid/img.xml")  # url_form
        garbage = tmp_path / "bad.xml"
        garbage.write_text("non è xml")
        seen.error(load_pds_image, str(garbage))  # pds4_tools_error
        seen.error(load_pds_image, str(tmp_path / "missing.xml"))  # file_unreadable
        import pds4_tools

        with monkeypatch.context() as patch:
            patch.setattr(pds4_tools, "read", lambda *a, **k: SimpleNamespace(structures=[], label=None))
            seen.error(load_pds_image, str(path))  # no_image

            def broken_as_masked():
                raise ValueError("dati illeggibili")

            fake = SimpleNamespace(is_array=lambda: True, type="Array_2D_Image", id="IMG", as_masked=broken_as_masked)
            patch.setattr(pds4_tools, "read", lambda *a, **k: SimpleNamespace(structures=[fake], label=None))
            seen.error(load_pds_image, str(path))  # data_unreadable
        label, data = path.read_bytes(), (pds_dir / "img.dat").read_bytes()
        service.routes["/pds/img.xml"] = lambda request: (200, "application/xml", label)
        service.routes["/pds/img.dat"] = lambda request: (200, "application/octet-stream", data)
        service.routes["/pds/outside.xml"] = lambda request: (200, "application/xml", label.replace(
            b"<file_name>img.dat</file_name>", b"<file_name>../img.dat</file_name>"))
        service.routes["/pds/nofiles.xml"] = lambda request: (200, "application/xml", label.replace(
            b"<File><file_name>img.dat</file_name></File>", b"<File></File>"))
        service.routes["/pds/missing.xml"] = lambda request: (200, "application/xml", label.replace(
            b"<file_name>img.dat</file_name>", b"<file_name>none.dat</file_name>"))
        service.routes["/pds/old.lbl"] = lambda request: (200, "text/plain", b"PDS_VERSION_ID = PDS3\nEND\n")
        service.routes["/pds/garbage.xml"] = lambda request: (200, "application/xml", b"non e xml")
        for name in ("outside.xml", "nofiles.xml", "old.lbl", "garbage.xml"):
            seen.error(load_pds_image, f"{service.url}/pds/{name}", cache=cache)  # file_outside, no_files, pds3, label_unreadable
        err = seen.error(load_pds_image, f"{service.url}/pds/missing.xml", cache=cache)
        assert err.relayed and err.code == "SERVICE_ERROR"
        first = load_pds_image(service.url + "/pds/img.xml", cache=cache)
        seen.notes(first.warnings)  # PDS_DOWNLOADED con PDS_DOWNLOAD downloaded
        seen.notes(load_pds_image(service.url + "/pds/img.xml", cache=cache).warnings)  # cached, FROM_CACHE del 14
    finally:
        pd.set_planetary_data_enabled(False)

    missing = required_combinations() - seen.pairs - MODULE_14_SUBVARIANTS - MODULE_15_SUBVARIANTS
    assert not missing, f"errori e avvisi del 19 mai provocati nel test: {sorted(missing, key=str)}"


def test_italian_text_is_unchanged_and_catalog_renders_both_languages(planetary_on):
    with pytest.raises(PlanetaryDataError) as info:
        check_overlay([hips("mars", "mars", "marte"), hips("moon", "moon", "luna")])
    err = info.value
    assert err.message.startswith("livelli di corpi diversi (") and "forzabile solo con force=True" in err.message
    assert mc.message_text(err.code, err.params, "en").startswith("Layers of different bodies (")
    assert mc.message_text(err.code, err.params, "it").startswith("Livelli di corpi diversi (")
    with pytest.raises(PlanetaryDataError) as info:
        body_of(hips("mars", None, "senza"))
    text = mc.message_text(info.value.code, info.value.params, "en")
    assert "the data open on their own, they are not overlaid." in text and CELESTIAL not in text
