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
