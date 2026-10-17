# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Test del modulo 19 (``mdfiles/19-core-dati-planetari.md`` §12).

I valori attesi si ricalcolano nel test con ``spiceypy`` e ``pds4_tools`` (le librerie di D19-1 e D19-2b) o
vengono da definizioni; nessun dato copiato da altri programmi (regola d'oro n. 8). Nessun test di default usa
la rete.
"""

from datetime import UTC, datetime

import astropy.units as u
import numpy as np
import pytest
import spiceypy
from astropy.table import Table
from mocpy import MOC

from astrotwo.core import planetary_data as pd
from astrotwo.core.hips import _service_from_properties, parse_properties
from astrotwo.core.moc import Moc
from astrotwo.core.planetary_data import (
    BODY_TABLE,
    CELESTIAL,
    PlanetaryBody,
    PlanetaryDataError,
    body_of,
    check_overlay,
    normalize_body_name,
)


@pytest.fixture
def planetary_on():
    pd.set_planetary_data_enabled(True)
    yield
    pd.set_planetary_data_enabled(False)


def hips(frame: str, body: str | None, name: str = "prova"):
    """HiPSService dalle proprietà dello standard HiPS 1.0 scritte nel test (modulo 12)."""
    lines = {"creator_did": f"ivo://TEST/P/{name}", "obs_title": name, "dataproduct_type": "image",
             "hips_version": "1.4", "hips_release_date": "2026-10-01T12:00Z", "hips_status": "public master",
             "hips_tile_format": "png", "hips_order": "3", "hips_frame": frame, "hips_tile_width": "64"}
    if body is not None:
        lines["hips_body"] = body
    text = "\n".join(f"{k} = {v}" for k, v in lines.items())
    return _service_from_properties(parse_properties(text), f"http://example.invalid/{name}", "test",
                                    datetime.now(UTC), False)


def celestial_moc():
    return Moc(moc=MOC.from_string("3/1-3"), kind="space", body=CELESTIAL, origin="test")


# =============================================================================
# P1 — tabella dei nomi (D12-6), corpi, body_of, check_overlay, opzione (T1, T2, T3, T9, T11)


def test_body_table_matches_spice_and_kernel(planetary_on):
    assert {"Moon", "Mars"} <= set(BODY_TABLE.values()) and len(BODY_TABLE) == 28
    for code, name in BODY_TABLE.items():
        assert spiceypy.bodc2n(code).lower() == name.lower()  # nome della tabella interna del toolkit
        assert name[0].isupper() and normalize_body_name(name.lower()) == name
        body = PlanetaryBody.from_name(name.upper())
        _, radii = spiceypy.bodvcd(code, "RADII", 3)  # dal kernel caricato
        assert body.naif_id == code and np.array_equal(body.radii.to_value(u.km), radii)
        assert "pck00011.tpc" in body.source and "spiceypy" in body.source
    for name in ("celestial", "mars-stimson", "Bennu", "", None):  # Bennu: codice NAIF ma senza HiPS
        with pytest.raises(PlanetaryDataError) as exc:
            normalize_body_name(name)
        assert exc.value.code == "BODY_UNSUPPORTED"


def test_kernel_integrity(monkeypatch, tmp_path, planetary_on):
    altered = tmp_path / "pck00011.tpc"
    altered.write_bytes(pd.KERNEL_PATH.read_bytes() + b"\n")
    monkeypatch.setattr(pd, "KERNEL_PATH", altered)
    monkeypatch.setattr(pd, "_KERNEL_LOADED", False)
    with pytest.raises(PlanetaryDataError) as exc:
        PlanetaryBody.from_name("Mars")
    assert exc.value.code == "PLANETARY_KERNEL_INVALID"


def test_t1_different_bodies(planetary_on):
    moon, mars = hips("moon", "moon", "luna"), hips("mars", "mars", "marte")
    assert body_of(moon) == "Moon" and body_of(mars) == "Mars"
    with pytest.raises(PlanetaryDataError) as exc:
        check_overlay([moon, mars])
    assert exc.value.code == "BODY_MISMATCH" and set(exc.value.details["bodies"]) == {"Moon", "Mars"}
    same = check_overlay([mars, hips("mars", "mars", "marte2")])
    assert same.body == "Mars" and not same.forced and same.warnings == ()


def test_t2_celestial_and_planetary(planetary_on):
    catalog = pd_catalog(CELESTIAL)
    mars = hips("mars", "mars", "marte")
    with pytest.raises(PlanetaryDataError) as exc:
        check_overlay([catalog, mars])
    assert exc.value.code == "BODY_MISMATCH" and "celestial" in exc.value.message
    # Un MOC con il corpo scritto in minuscolo si normalizza con la tabella.
    mars_moc = Moc(moc=MOC.from_string("3/1"), kind="space", body="mars", origin="test")
    assert check_overlay([mars, mars_moc]).body == "Mars"


def pd_catalog(body):
    from astrotwo.core.catalogs import CatalogTable, TableLimits

    return CatalogTable(table=Table({"a": [1]}), source="test", origin="test", retrieved_at=datetime.now(UTC),
                        file_modified=None, format="votable", table_index=0, table_name="t", positions=None,
                        body=body, limits=TableLimits())


def test_t3_missing_body(planetary_on):
    unknown = hips("mars", None, "senza_corpo")
    assert unknown.body is None
    alone = check_overlay([unknown])  # il dato si apre da solo
    assert alone.body is None and "BODY_UNKNOWN" in dict(alone.warnings)
    with pytest.raises(PlanetaryDataError) as exc:
        body_of(unknown)
    assert exc.value.code == "BODY_UNKNOWN"
    for force in (False, True):  # non forzabile
        with pytest.raises(PlanetaryDataError) as exc:
            check_overlay([unknown, hips("mars", "mars", "marte")], force=force)
        assert exc.value.code == "BODY_UNKNOWN"


def test_t9_option_disabled():
    assert not pd.planetary_data_enabled()  # default: spenta (D19-5)
    mars = hips("mars", "mars", "marte")
    assert mars.body == "Mars"  # il 12 normalizza anche con l'opzione spenta (lettura dei metadati)
    for call in (lambda: PlanetaryBody.from_name("Mars"), lambda: body_of(mars), lambda: check_overlay([mars]),
                 lambda: check_overlay([mars, mars])):
        with pytest.raises(PlanetaryDataError) as exc:
            call()
        assert exc.value.code == "PLANETARY_DATA_DISABLED"
    # Funzioni celesti non toccate.
    sky = hips("equatorial", None, "cielo")
    assert body_of(sky) == CELESTIAL and body_of(celestial_moc()) == CELESTIAL
    assert check_overlay([sky, celestial_moc(), pd_catalog(CELESTIAL)]).body == CELESTIAL


def test_t11_forced_overlay(planetary_on):
    moon, mars = hips("moon", "moon", "luna"), hips("mars", "mars", "marte")
    result = check_overlay([moon, mars], force=True)
    assert result.forced and result.body is None and set(result.bodies) == {"Moon", "Mars"}
    assert "BODY_MISMATCH_FORCED" in dict(result.warnings)
    assert ("force", True) in result.command.arguments and "force=True" in result.command.text
    mixed = Moc(moc=MOC.from_string("3/1"), kind="space", body="mixed", origin="test", bodies=("mars", "moon"))
    with pytest.raises(PlanetaryDataError) as exc:
        body_of(mixed)
    assert exc.value.code == "BODY_MISMATCH"


# =============================================================================
# P2 — posizioni e conversioni di convenzione (T4, T5, T6, T10)

from astrotwo.core.planetary_data import PlanetaryPosition, convert_planetary_coordinates, run_command  # noqa: E402


def position(lon, lat, body="Mars", latitude_type="planetocentric", direction="east"):
    return PlanetaryPosition(lon=lon * u.deg, lat=lat * u.deg, body=body, latitude_type=latitude_type,
                             longitude_direction=direction)


def test_t4_longitude_east_west(planetary_on):
    pd._load_kernel()
    mars = PlanetaryBody.from_name("Mars")
    a, f = mars.radii[0].to_value(u.km), float(mars.flattening)
    for lon in (0.0, 1e-9, 45.0, 137.4, 180.0, 359.5):
        start = position(lon, 12.0)
        west = convert_planetary_coordinates(start, "planetocentric", "west")
        # Marte ruota in senso progrado: la longitudine planetografica di spiceypy è positiva verso ovest.
        rect = spiceypy.latrec(a, np.deg2rad(lon), np.deg2rad(12.0))
        spice_west = np.rad2deg(spiceypy.recpgr("MARS", rect, a, f)[0]) % 360.0
        assert (west.lon.value - spice_west + 180.0) % 360.0 - 180.0 == pytest.approx(0.0, abs=1e-9)  # modulo 360°
        assert west.longitude_direction == "west" and west.lat.value == 12.0
        back = convert_planetary_coordinates(west, "planetocentric", "east")
        assert back.lon.value == pytest.approx(lon % 360.0, abs=1e-9)
    assert position(-90.0, 0.0).lon.value == 270.0  # [−180°, 360°] in ingresso, [0°, 360°) in uscita


def test_t5_latitude_centric_graphic(planetary_on):
    mars = PlanetaryBody.from_name("Mars")
    f = float(mars.flattening)
    assert f > 0.005  # corpo con schiacciamento noto (raggi del kernel)
    for lat in (-89.0, -45.0, -4.6, 0.0, 30.0, 60.0, 90.0):
        graphic = convert_planetary_coordinates(position(137.4, lat), "planetographic", "east")
        # Sulla superficie dello sferoide: tan φg = tan φc / (1 − f)² (definizione), ricalcolata nel test.
        expected = np.rad2deg(np.arctan2(np.tan(np.deg2rad(lat)), (1 - f) ** 2)) if abs(lat) < 90 else lat
        assert graphic.lat.value == pytest.approx(expected, abs=1e-9)
        assert any("spiceypy" in n for n in graphic.notes) and "pck00011.tpc" in graphic.library
        back = convert_planetary_coordinates(graphic, "planetocentric", "east")
        assert abs(back.lat.value - lat) < 1e-9
    # Sfera (Luna): le due latitudini coincidono.
    moon = convert_planetary_coordinates(position(10.0, 33.0, "Moon"), "planetographic", "east")
    assert moon.lat.value == pytest.approx(33.0, abs=1e-12)
    # Corpo triassiale: dichiarato che RADII[1] non entra.
    io = convert_planetary_coordinates(position(10.0, 33.0, "Io"), "planetographic", "east")
    assert any("triassiale" in n for n in io.notes)


def test_t6_convention_required(planetary_on):
    for kwargs in ({"latitude_type": None}, {"latitude_type": "geodetic"}, {"direction": None}):
        with pytest.raises(PlanetaryDataError) as exc:
            position(10.0, 10.0, **kwargs)
        assert exc.value.code == "PLANETARY_CONVENTION_REQUIRED"
    with pytest.raises(PlanetaryDataError) as exc:
        convert_planetary_coordinates(position(10.0, 10.0), None, "east")
    assert exc.value.code == "PLANETARY_CONVENTION_REQUIRED"
    for lon, lat in ((10.0, 90.5), (10.0, -91.0), (-181.0, 0.0), (361.0, 0.0), (np.nan, 0.0)):
        with pytest.raises(PlanetaryDataError) as exc:
            position(lon, lat)
        assert exc.value.code == "COORD_OUT_OF_RANGE"
    with pytest.raises(PlanetaryDataError) as exc:
        position(10.0, 10.0, body="Bennu")
    assert exc.value.code == "BODY_UNSUPPORTED"
    with pytest.raises(TypeError):
        PlanetaryPosition(lon=10.0, lat=10.0, body="Mars", latitude_type="planetocentric", longitude_direction="east")


def test_t10_rerun_recorded_commands(planetary_on):
    first = convert_planetary_coordinates(position(137.4, -4.6), "planetographic", "west")
    second = convert_planetary_coordinates(first, "planetocentric", "east")
    for result in (first, second):
        again = run_command(result.command)
        assert again.lon == result.lon and again.lat == result.lat and again.body == result.body
        assert (again.latitude_type, again.longitude_direction) == (result.latitude_type, result.longitude_direction)


# =============================================================================
# P3 — collezioni per corpo (12) ed EPN-TAP (14) (T7)

import io  # noqa: E402

from astropy.io.votable import from_table  # noqa: E402

from astrotwo.core.hips import CollectionIndex  # noqa: E402
from astrotwo.core.planetary_data import list_planetary_collections, query_epntap  # noqa: E402


def local_index(records):
    index = CollectionIndex()
    index.records, index.origin, index.synced_at = tuple(records), "test", datetime.now(UTC)
    return index


def test_list_planetary_collections(planetary_on):
    records = [
        {"ID": "T/P/DSS", "hips_frame": "equatorial"},
        {"ID": "T/P/Mars/a", "hips_frame": "mars", "hips_body": "mars"},
        {"ID": "T/P/Mars/b", "hips_frame": "mars", "hips_body": "mars"},
        {"ID": "T/P/Mars/c", "hips_frame": "mars"},  # senza hips_body: corpo ignoto
        {"ID": "T/P/Moon/a", "hips_frame": "moon", "hips_body": "moon"},
        {"ID": "T/P/Mars/pano", "hips_frame": "mars-stimson", "hips_body": "mars-stimson"},
    ]
    all_bodies = list_planetary_collections(index=local_index(records))
    assert list(all_bodies.by_body) == ["Mars", "Moon"]
    assert [r["ID"] for r in all_bodies.for_body("mars")] == ["T/P/Mars/a", "T/P/Mars/b"]
    assert {r["ID"] for r, _ in all_bodies.unknown} == {"T/P/Mars/c", "T/P/Mars/pano"}
    only_moon = list_planetary_collections("Moon", index=local_index(records))
    assert list(only_moon.by_body) == ["Moon"] and only_moon.unknown == ()
    pd.set_planetary_data_enabled(False)
    with pytest.raises(PlanetaryDataError) as exc:
        list_planetary_collections(index=local_index(records))
    assert exc.value.code == "PLANETARY_DATA_DISABLED"


def epn_votable(targets, frames):
    n = len(targets)
    table = Table({"granule_uid": [f"g{k}" for k in range(n)], "target_name": targets,
                   "spatial_frame_type": frames, "c1min": np.linspace(10, 20, n), "c1max": np.linspace(11, 21, n),
                   "c2min": np.full(n, -5.0), "c2max": np.full(n, 5.0)})
    buffer = io.BytesIO()
    from_table(table).to_xml(buffer)
    return buffer.getvalue()


def test_t7_epntap_simulated_service(service, cache, planetary_on):
    payloads = {"mars": epn_votable(["Mars", "Mars"], ["body", "body"]),
                "mixed": epn_votable(["Mars", "Moon"], ["body", "body"]),
                "sky": epn_votable(["Ceres", "Ceres"], ["celestial", "celestial"])}
    current = {"name": "mars"}
    service.routes["/epn/sync"] = lambda request: (200, "application/x-votable+xml", payloads[current["name"]])
    adql = "SELECT * FROM mars_data.epn_core WHERE target_name = 'Mars'"
    result = query_epntap(service.url + "/epn", adql, cache=cache)
    assert service.requests[-1]["params"]["QUERY"] == adql
    assert result.table.body == "Mars" and result.table.rows == 2
    meta = result.table.table.meta
    assert meta["planetary_latitude_type"] == "planetocentric" and meta["planetary_longitude_direction"] == "east"
    assert "PLANETARY_CONVENTIONS" in dict(result.table.warnings) and "BODY_UNKNOWN" not in dict(result.table.warnings)
    current["name"] = "mixed"
    mixed = query_epntap(service.url + "/epn", adql.replace("'Mars'", "'Moon'"), cache=cache)
    assert mixed.table.body is None and "BODY_UNKNOWN" in dict(mixed.table.warnings)
    current["name"] = "sky"
    sky = query_epntap(service.url + "/epn", adql.replace("'Mars'", "'Ceres'"), cache=cache)
    assert sky.table.body == CELESTIAL
    with pytest.raises(PlanetaryDataError) as exc:  # non è una tabella EPN-TAP: nessuna rete
        query_epntap(service.url + "/epn", "SELECT * FROM stelle", cache=cache)
    assert exc.value.code == "ADQL_INVALID"
    with pytest.raises(PlanetaryDataError) as exc:  # servizio non raggiungibile: errore del 14
        query_epntap("http://127.0.0.1:9/epn", adql, cache=cache)
    assert exc.value.code == "NET_TIMEOUT"


# =============================================================================
# P4 — immagini PDS4 (T8). pds4_tools non fornisce file di esempio: prodotto PDS4 scritto nel test.

from astrotwo.core.planetary_data import PdsImage, load_pds_image  # noqa: E402

_ARRAY = """    <Array_2D_Image>
      <name>{name}</name>
      <offset unit="byte">{offset}</offset>
      <axes>2</axes>
      <axis_index_order>Last Index Fastest</axis_index_order>
      <Element_Array><data_type>SignedMSB2</data_type><scaling_factor>0.5</scaling_factor><value_offset>10</value_offset></Element_Array>
      <Axis_Array><axis_name>Line</axis_name><elements>3</elements><sequence_number>1</sequence_number></Axis_Array>
      <Axis_Array><axis_name>Sample</axis_name><elements>4</elements><sequence_number>2</sequence_number></Axis_Array>
      <Special_Constants><missing_constant>-20</missing_constant></Special_Constants>
    </Array_2D_Image>
"""


def pds4_product(folder, targets=("Mars",), images=1):
    raw = (np.arange(12).reshape(3, 4) * 7 - 20).astype(">i2")
    (folder / "img.dat").write_bytes(raw.tobytes() * images)
    arrays = "".join(_ARRAY.format(name=f"IMAGE{k + 1}" if images > 1 else "IMAGE", offset=k * raw.nbytes)
                     for k in range(images))
    target_xml = "".join(f"<Target_Identification><name>{t}</name><type>Planet</type></Target_Identification>"
                         for t in targets)
    label = f"""<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">
  <Identification_Area>
    <logical_identifier>urn:nasa:pds:astrotwo_test:data:img</logical_identifier>
    <version_id>1.0</version_id><title>Test</title>
    <information_model_version>1.20.0.0</information_model_version>
    <product_class>Product_Observational</product_class>
  </Identification_Area>
  <Observation_Area>
    <Time_Coordinates><start_date_time>2020-01-01T00:00:00Z</start_date_time><stop_date_time>2020-01-01T00:00:00Z</stop_date_time></Time_Coordinates>
    {target_xml}
  </Observation_Area>
  <File_Area_Observational>
    <File><file_name>img.dat</file_name></File>
{arrays}  </File_Area_Observational>
</Product_Observational>
"""
    path = folder / "img.xml"
    path.write_text(label)
    return path, raw


def test_t8_pds4_image(tmp_path, planetary_on):
    import pds4_tools

    path, raw = pds4_product(tmp_path)
    image = load_pds_image(str(path))
    reference = pds4_tools.read(str(path), quiet=True)[0].as_masked().data  # stessa libreria (D19-2b)
    expected = np.where(raw == -20, np.nan, 10.0 + 0.5 * raw.astype(np.float64))  # valori scritti nel test
    assert image.data.dtype == np.float64 and image.data.shape == (3, 4)
    assert np.array_equal(image.data, np.ma.filled(reference.astype(np.float64), np.nan), equal_nan=True)
    assert np.array_equal(image.data, expected, equal_nan=True)
    assert image.body == "Mars" and image.special_pixels == 1 and image.structure == "IMAGE"
    assert image.element_array["scaling_factor"] == 0.5 and "pds4_tools" in image.library
    assert body_of(image) == "Mars" and check_overlay([image, hips("mars", "mars", "marte")]).body == "Mars"
    assert np.array_equal(run_command(image.command).data, image.data, equal_nan=True)


def test_t8_pds4_errors(tmp_path, planetary_on):
    (tmp_path / "two").mkdir()
    two, _ = pds4_product(tmp_path / "two", images=2)
    with pytest.raises(PlanetaryDataError) as exc:
        load_pds_image(str(two))
    assert exc.value.code == "PDS_STRUCTURE_CHOICE_REQUIRED" and exc.value.details["structures"] == ("IMAGE1",
                                                                                                    "IMAGE2")
    assert load_pds_image(str(two), structure="IMAGE2").structure == "IMAGE2"
    (tmp_path / "multi").mkdir()
    multi, _ = pds4_product(tmp_path / "multi", targets=("Mars", "Phobos"))
    unknown = load_pds_image(str(multi))
    assert unknown.body is None and "BODY_UNKNOWN" in dict(unknown.warnings)
    with pytest.raises(PlanetaryDataError) as exc:
        body_of(unknown)
    assert exc.value.code == "BODY_UNKNOWN"
    pds3 = tmp_path / "old.lbl"
    pds3.write_text("PDS_VERSION_ID = PDS3\nEND\n")
    garbage = tmp_path / "bad.xml"
    garbage.write_text("non è xml")
    for source, hint in ((str(pds3), "PDS3 non ancora supportato"), ("ftp://example.invalid/img.xml", "D19-9"),
                         (str(garbage), "pds4_tools"), (str(tmp_path / "missing.xml"), "non leggibile")):
        with pytest.raises(PlanetaryDataError) as exc:
            load_pds_image(source)
        assert exc.value.code == "PDS_UNREADABLE" and hint in exc.value.message
    pd.set_planetary_data_enabled(False)
    with pytest.raises(PlanetaryDataError) as exc:
        load_pds_image(str(two))
    assert exc.value.code == "PLANETARY_DATA_DISABLED"


def test_t8_pds4_from_url(tmp_path, service, cache, planetary_on):
    """D19-9: etichetta e file nominati dalla stessa cartella dell'URL, rete del 14, cache comune."""
    path, raw = pds4_product(tmp_path)
    label, data = path.read_bytes(), (tmp_path / "img.dat").read_bytes()
    service.routes["/pds/img.xml"] = lambda request: (200, "application/xml", label)
    service.routes["/pds/img.dat"] = lambda request: (200, "application/octet-stream", data)
    url = service.url + "/pds/img.xml"
    image = load_pds_image(url, cache=cache)
    local = load_pds_image(str(path))
    assert np.array_equal(image.data, local.data, equal_nan=True) and image.body == "Mars"
    assert image.origin == url and [d[0] for d in image.downloads] == [url, service.url + "/pds/img.dat"]
    assert not any(d[2] for d in image.downloads) and "PDS_DOWNLOADED" in dict(image.warnings)
    again = load_pds_image(url, cache=cache)  # dalla cache comune: nessuna nuova richiesta
    assert service.hits("/pds/img.xml") == 1 and service.hits("/pds/img.dat") == 1
    assert all(d[2] for d in again.downloads) and "FROM_CACHE" in dict(again.warnings)
    assert np.array_equal(again.data, image.data, equal_nan=True)
    refreshed = load_pds_image(url, cache=cache, refresh=True)
    assert service.hits("/pds/img.dat") == 2 and not any(d[2] for d in refreshed.downloads)
    # Etichetta PDS3 da URL, file fuori dalla cartella, file di dati mancante, servizio non raggiungibile.
    service.routes["/pds/old.lbl"] = lambda request: (200, "text/plain", b"PDS_VERSION_ID = PDS3\nEND\n")
    outside = label.replace(b"<file_name>img.dat</file_name>", b"<file_name>../img.dat</file_name>")
    service.routes["/pds/outside.xml"] = lambda request: (200, "application/xml", outside)
    missing = label.replace(b"<file_name>img.dat</file_name>", b"<file_name>none.dat</file_name>")
    service.routes["/pds/missing.xml"] = lambda request: (200, "application/xml", missing)
    for name, code, hint in (("old.lbl", "PDS_UNREADABLE", "PDS3 non ancora supportato"),
                             ("outside.xml", "PDS_UNREADABLE", "stessa cartella"),
                             ("missing.xml", "SERVICE_ERROR", "404")):
        with pytest.raises(PlanetaryDataError) as exc:
            load_pds_image(f"{service.url}/pds/{name}", cache=cache)
        assert exc.value.code == code and hint in exc.value.message
    with pytest.raises(PlanetaryDataError) as exc:
        load_pds_image("http://127.0.0.1:9/pds/img.xml", cache=cache)
    assert exc.value.code == "NET_TIMEOUT"



# =============================================================================
# Test di rete (alla fine del modulo 19)


@pytest.mark.network
def test_body_table_against_mocserver(cache):
    index = CollectionIndex(cache=cache).sync()
    found = {}
    for record in index.records:
        frames, bodies = record.get("hips_frame"), record.get("hips_body")
        if isinstance(frames, str) and frames == bodies:
            try:
                found[normalize_body_name(frames)] = record["ID"]
            except PlanetaryDataError:
                pass
    assert set(BODY_TABLE.values()) <= set(found)  # ogni corpo della tabella ha un HiPS (D19-6)


@pytest.mark.network
def test_t7_epntap_real_service(cache, planetary_on):
    adql = "SELECT TOP 5 target_name, spatial_frame_type, c1min, c2min FROM mars_craters.epn_core"
    result = query_epntap("http://voparis-tap-planeto.obspm.fr/tap", adql, cache=cache)
    assert result.table.rows == 5 and result.table.body == "Mars"
    assert result.table.table.meta["planetary_longitude_direction"] == "east"
