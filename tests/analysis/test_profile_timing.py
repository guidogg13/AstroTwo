# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Tempi del profilo: correzioni dello sprint C7 (``mdfiles/25-analisi-profilo-oggetto.md`` §3.16; §12 T29) e
decisioni D25-21 dello sprint C8 (§3.17; §12 T30–T34).

Servizi simulati con le risposte vere registrate (``tests/analysis/profile_fakes.py``), con ritardi aggiunti nel
server locale per vedere quando parte ogni richiesta. Il difetto di ``cds_down_in_session`` (C7-e) è provato in
``tests/core/test_hips_thumbnail.py``.
"""

from __future__ import annotations

import time

import pytest

from astrotwo.analysis.object_profile import ProfileTarget, build_profile
from tests.analysis.profile_fakes import recorded, scs_params, services, votable  # noqa: F401


@pytest.fixture(scope="module", autouse=True)
def warm_matplotlib():
    """Prima figura di matplotlib fuori dai tempi misurati (cache dei caratteri)."""
    import io

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure = plt.figure()
    figure.text(0.5, 0.5, "λ Fν µm")
    figure.savefig(io.BytesIO(), format="png")
    plt.close(figure)


def stamped(services, service: str, text: str, arrivals: dict, *, delay: float = 0.0, answer=None) -> None:
    """Risposta di ``service`` alle query che contengono ``text``: istante di arrivo in ``arrivals[text]``."""
    def make(query):
        arrivals.setdefault(text, time.monotonic())
        time.sleep(delay)
        return recorded(service, query) if answer is None else answer
    services.overrides[(service, text)] = make


def section(prof, name: str):
    return next(s for s in prof.sections if s.name == name)


# =============================================================================
# C7-a — riga di AllWISE già letta nel passo per posizione: nessuna seconda richiesta a IRSA


def test_t29_allwise_by_position_uses_the_row_of_the_chain(services, cache):
    prof = build_profile(ProfileTarget(name="Vega"), sections=("identity", "photometry"), cache=cache)
    allwise = [q for s, q in services.queries if s == "irsa" and "allwise_p3as_psd" in q]
    assert len(allwise) == 1 and allwise[0].startswith("DEC=")  # un solo cono del Cone Search (25 §3.17 punto 1)
    phot = section(prof, "photometry")
    values = [v for v in phot.values if v.quantity.startswith("AllWISE W")]
    assert values, [v.quantity for v in phot.values]
    for value in values:  # provenanza = la richiesta che ha dato i valori (cerchio, server vero, metodo)
        assert scs_params(value.provenance.query) == allwise[0]
        assert value.provenance.match == "position"
        assert value.provenance.identifier == "WISEA J183656.51+384704.4"
        assert value.provenance.server.startswith(services.url("irsa"))
    # una sola registrazione della richiesta del cerchio nella sezione
    circle = [r for r in phot.requests if "allwise_p3as_psd" in r.url]
    assert len(circle) <= 1


# =============================================================================
# C7-b — la serie VizieR della fotometria non aspetta gli incroci; Gaia, 2MASS e AllWISE sì (un solo archivio
# non deve occupare più posti del semaforo quando non risponde, 25 §3.16)


def test_t29_photometry_vizier_starts_without_waiting_for_the_ids(services, cache):
    arrivals: dict = {}
    stamped(services, "gaia", "best_neighbour", arrivals, delay=2.0)  # incroci ufficiali lenti (2MASS, AllWISE)
    stamped(services, "gaia", "phot_g_mean_flux", arrivals)
    vizier_at = []
    original = services.fake.routes["/vizier/sed"]

    def vizier(request):
        vizier_at.append(time.monotonic())
        return original(request)

    services.fake.routes["/vizier/sed"] = vizier
    resolved_at = {}
    build_profile(ProfileTarget(name="TRAPPIST-1"), sections=("photometry",), cache=cache,
                  on_resolved=lambda r: resolved_at.setdefault("t", time.monotonic()))
    assert vizier_at and vizier_at[0] - resolved_at["t"] < 1.5  # subito, non dopo i 2 s degli incroci
    # Gaia aspetta un posto del suo servizio: i due incroci ufficiali lenti tengono i 2 posti di Gaia (§3.17 punto 5)
    assert arrivals["phot_g_mean_flux"] - resolved_at["t"] >= 1.9


# =============================================================================
# C7-d — con lo stato del CDS non noto, un solo survey prova il MocServer


def test_t29_only_the_first_survey_waits_for_the_mocserver(services, cache, monkeypatch):
    from astrotwo.core import vo_protocols as vo

    calls = []
    original = vo._http

    def counted(protocol, url, *args, **kw):
        if url == vo.MOCSERVER_URL:
            calls.append(url)
        return original(protocol, url, *args, **kw)

    monkeypatch.setattr(vo, "_http", counted)
    prof = build_profile(ProfileTarget(name="51 Peg"), sections=("images",), cache=cache)
    images = section(prof, "images")
    assert images.status == "done" and len(calls) == 1
    reasons = sorted(w.params["reason"] for w in images.warnings if w[0] == "HIPS_MIRROR_FALLBACK")
    assert reasons == ["cds_down", "cds_down", "mocserver"]
    assert [t["hips_id"] for t in images.details["thumbnails"]] == list(images.details["surveys"])


# =============================================================================
# T30 — 2MASS e AllWISE con il Cone Search di IRSA (D25-21 (1), 25 §3.17 punto 1)

_TAP_COLUMN = {"J": "j_m", "H": "h_m", "Ks": "k_m", "W1": "w1mpro", "W2": "w2mpro", "W3": "w3mpro", "W4": "w4mpro"}
_TAP_ERROR = {"j_m": "j_msigcom", "h_m": "h_msigcom", "k_m": "k_msigcom", "w1mpro": "w1sigmpro",
              "w2mpro": "w2sigmpro", "w3mpro": "w3sigmpro", "w4mpro": "w4sigmpro"}


def _tap_rows() -> dict:
    """Righe delle risposte TAP di IRSA registrate il 2026-11-07, per designazione (riferimento della condizione)."""
    import io

    from astropy.io.votable import parse_single_table

    from tests.analysis.profile_fakes import INDEX

    out = {}
    for key in INDEX:
        if key.startswith("irsa|"):
            table = parse_single_table(io.BytesIO(recorded("irsa", key.split("|", 1)[1]))).to_table(
                use_names_over_ids=True)
            for row in table:
                out[str(row["designation"]).strip()] = row
    return out


@pytest.mark.parametrize("name", ["51 Peg", "Vega", "eta Tau", "TRAPPIST-1"])
def test_t30_irsa_cone_search_gives_the_same_points_as_tap(services, cache, name):
    prof = build_profile(ProfileTarget(name=name), sections=("identity", "photometry"), cache=cache)
    irsa = [q for s, q in services.queries if s == "irsa"]
    assert irsa and all(q.startswith("DEC=") for q in irsa)  # solo Cone Search, nessuna richiesta TAP a IRSA
    tap = _tap_rows()
    phot = section(prof, "photometry")
    points = [p for p in phot.details["points"] if p["catalog"] in ("2MASS", "AllWISE")]
    assert points
    for point in points:
        designation = point["identifier"].removeprefix("2MASS J").removeprefix("WISEA ")
        row = tap[designation]
        column = _TAP_COLUMN[point["band"]]
        assert point["magnitude"]["value"] == float(str(row[column])) and point["magnitude"]["unit"] == "mag"
        error = row[_TAP_ERROR[column]]
        if point["magnitude_error"] is None:
            assert getattr(error, "mask", False) is True or str(error) == "--"
        else:
            assert point["magnitude_error"]["value"] == float(str(error))
        assert point["quality"] == str(row["ph_qual"])["JHK".index(point["band"][0]) if point["catalog"] == "2MASS"
                                                       else int(point["band"][1]) - 1]
    for value in phot.values:
        if value.quantity.startswith(("2MASS", "AllWISE")):
            prov = value.provenance
            assert prov.query.startswith(services.url("irsa") + "/SCS?table=") and "&RA=" in prov.query
            assert "&SR=" in prov.query and prov.table in ("fp_psc", "allwise_p3as_psd")
            assert scs_params(prov.query) in irsa


def test_t30_designation_without_a_readable_position_stays_on_tap(services, cache):
    import astrotwo.analysis.object_profile as op

    services.overrides[("irsa", "designation = 'nonvalida'")] = lambda q: votable(
        [(c.strip(), "char", None) for c in op._IRSA_COLUMNS["2mass"].split(",")], [])
    request, query, rows, _ = op._irsa_by_designation("2mass", "2MASS Jnonvalida", cache=cache, refresh=False,
                                                      timeouts=op.NETWORK_TIMEOUTS)
    assert query.startswith("SELECT designation") and "designation = 'nonvalida'" in query and len(rows) == 0
    assert request.url.startswith(services.url("irsa") + "/sync")


def test_t30_cone_search_without_the_columns_is_an_error_not_a_silent_gap(services, cache):
    import astrotwo.analysis.object_profile as op
    from astrotwo.core.vo_protocols import VoProtocolsError

    services.overrides[("irsa", "")] = lambda q: votable([("designation", "char", None)], [])
    with pytest.raises(VoProtocolsError) as info:
        op._irsa_by_designation("2mass", "2MASS J22572795+2046077", cache=cache, refresh=False,
                                timeouts=op.NETWORK_TIMEOUTS)
    assert info.value.code == "VOTABLE_INVALID" and info.value.params["reason"] == "photometry_columns"
    assert "jdate" in info.value.params["missing"]


# =============================================================================
# T31 — dati aggiornati: dal principale una volta per profilo (D25-21 (2), 25 §3.17 punto 2)


def test_t31_refresh_restarts_simbad_from_the_primary_once_per_profile(services, cache, monkeypatch):
    import dataclasses

    from astrotwo.core import vo_protocols as vo
    from astrotwo.core.vo_protocols import ServiceMirrors, simbad_object

    dead = "http://127.0.0.1:9/simbad"  # principale giù (connessione rifiutata), «a Strasburgo» per il test
    entries = tuple(dataclasses.replace(e, url=dead) if e.id == "cds-simbad-tap" else e for e in vo.BUILTIN_SERVERS)
    monkeypatch.setattr(vo, "BUILTIN_SERVERS", entries)
    monkeypatch.setattr(vo, "SERVICE_MIRRORS", {"cds-simbad-tap": ServiceMirrors("simbad", "SIMBAD",
                                                                                  (services.url("simbad"),))})
    monkeypatch.setattr(vo, "_in_strasbourg", lambda url: url.startswith(dead))
    calls = {"primary": 0, "mocserver": 0}
    original = vo._http

    def counted(protocol, url, *args, **kw):
        if url.startswith(dead):
            calls["primary"] += 1
        if url == vo.MOCSERVER_URL:
            calls["mocserver"] += 1
        return original(protocol, url, *args, **kw)

    monkeypatch.setattr(vo, "_http", counted)
    for round_ in (1, 2):
        prof = build_profile(ProfileTarget(name="51 Peg"), cache=cache, refresh=True)
        assert calls["primary"] == round_  # una sola richiesta al principale per profilo
        assert all(not r.from_cache for r in prof.requests)  # tutte senza cache
        images = section(prof, "images")
        assert {w.params["evidence"] for w in images.warnings if w[0] == "HIPS_MIRROR_FALLBACK"} == {
            "simbad_failover"}  # prova raccolta nel profilo: miniature subito dai mirror
        phot = section(prof, "photometry")
        assert [e["code"] for e in phot.errors if e["catalog"] == "vizier_sed"] == ["PROFILE_VIZIER_SKIPPED"]
    assert calls["mocserver"] == 0 and services.count("vizier") == 0
    simbad_object("51 Peg", cache=cache, refresh=True)  # fuori da un profilo: ogni richiesta dal principale
    assert calls["primary"] == 2 + 3


# =============================================================================
# T32 — serie VizieR saltata con il CDS già giù (D25-21 (3), 25 §3.17 punto 3)


SED = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>
<TABLE><FIELD name="_RAJ2000" datatype="double" unit="deg"/><FIELD name="_DEJ2000" datatype="double" unit="deg"/>
<FIELD name="_tabname" datatype="char" arraysize="*"/><FIELD name="_ID" datatype="char" arraysize="*"/>
<FIELD name="_sed_freq" datatype="double" unit="GHz"/><FIELD name="_sed_flux" datatype="float" unit="Jy"/>
<FIELD name="_sed_eflux" datatype="float" unit="Jy"/><FIELD name="_sed_filter" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>
<TR><TD>346.62</TD><TD>-5.04</TD><TD>II/246/out</TD><TD>2MASS=1</TD><TD>136.89e+3</TD><TD>0.05</TD><TD>0.001</TD><TD>2MASS:Ks</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""


def test_t32_vizier_skipped_when_the_cds_is_already_down(services, cache):
    from astrotwo.core import hips

    first = section(build_profile(ProfileTarget(name="TRAPPIST-1"), sections=("photometry",), cache=cache),
                     "photometry")
    assert services.count("vizier") == 1 and first.errors[-1]["code"] == "SERVICE_ERROR"  # stato del CDS non noto
    build_profile(ProfileTarget(name="51 Peg"), sections=("images",), cache=cache)  # MocServer giù: prova
    assert hips.cds_down_in_session()["evidence"] == "mocserver"
    prof = build_profile(ProfileTarget(name="TRAPPIST-1"), sections=("photometry",), cache=cache)
    phot = section(prof, "photometry")
    assert services.count("vizier") == 1  # nessuna nuova richiesta a VizieR
    error = next(e for e in phot.errors if e["catalog"] == "vizier_sed")
    assert error["code"] == "PROFILE_VIZIER_SKIPPED" and error["params"] == {"reason": "cds_down",
                                                                            "evidence": "mocserver"}
    assert phot.details["vizier_sed"] == {"skipped": True, "reason": "cds_down", "evidence": "mocserver"}
    assert phot.status == "partial" and any(p["catalog"] == "2MASS" for p in phot.details["points"])
    # con refresh e nessuna prova raccolta nel profilo: la richiesta si fa (si riprova il CDS)
    build_profile(ProfileTarget(name="TRAPPIST-1"), sections=("photometry",), cache=cache, refresh=True)
    assert services.count("vizier") == 2


def test_t32_vizier_from_the_cache_when_the_cds_is_down(services, cache):
    from astrotwo.core import hips

    services.overrides[("vizier", "")] = lambda q: SED
    build_profile(ProfileTarget(name="TRAPPIST-1"), sections=("photometry",), cache=cache)  # copia in cache
    services.overrides.clear()
    build_profile(ProfileTarget(name="51 Peg"), sections=("images",), cache=cache)
    assert hips.cds_down_in_session() is not None and services.count("vizier") == 1
    phot = section(build_profile(ProfileTarget(name="TRAPPIST-1"), sections=("photometry",), cache=cache),
                   "photometry")
    assert services.count("vizier") == 1 and not phot.errors and "vizier_sed" not in phot.details
    assert any(w[0] == "FROM_CACHE" for w in phot.warnings) and len(phot.details["vizier"]["rows"]) == 1
    assert phot.details["vizier"]["provenance"]["from_cache"] is True


# =============================================================================
# T33 — tempo di una sezione contato dalla sua partenza (D25-21 (4), 25 §3.17 punto 4)

VEGA = (279.234734787025, 38.783688956244)
GAIA_CONE = [("source_id", "long", None), ("ra", "double", "deg"), ("dec", "double", "deg"),
             ("phot_g_mean_mag", "float", "mag")]


def test_t33_waiting_for_the_chain_does_not_count(services, cache, monkeypatch):
    import astropy.units as u

    import astrotwo.analysis.object_profile as op

    limit = op._section_limit
    monkeypatch.setattr(op, "_section_limit", lambda name: 0.4 * u.s if name == "astrometry" else limit(name))
    stamped(services, "gaia", "CONTAINS", {}, delay=0.8)  # incrocio per posizione (Vega) più lento del tempo
    prof = build_profile(ProfileTarget(name="Vega"), sections=("astrometry",), cache=cache)
    astro = section(prof, "astrometry")
    assert astro.status != "error" and not any(e["code"] == "PROFILE_SECTION_TIMEOUT" for e in astro.errors)
    assert astro.started >= 0.75 and astro.elapsed >= astro.started
    assert prof.as_dict()["sections"][0]["started"]["unit"] == "s"


def test_t33_the_deadline_runs_from_the_start(services, cache, monkeypatch):
    import astropy.units as u

    import astrotwo.analysis.object_profile as op

    limit = op._section_limit
    monkeypatch.setattr(op, "_section_limit", lambda name: 0.4 * u.s if name == "astrometry" else limit(name))
    stamped(services, "gaia", "CONTAINS", {}, delay=0.8, answer=votable(GAIA_CONE, [[42, VEGA[0], VEGA[1], 17.0]]))
    stamped(services, "gaia", "source_id = 42", {}, delay=1.5, answer=votable([("source_id", "long", None)], []))
    prof = build_profile(ProfileTarget(name="Vega"), sections=("astrometry",), cache=cache)
    astro = section(prof, "astrometry")
    assert [e["code"] for e in astro.errors] == ["PROFILE_SECTION_TIMEOUT"]
    assert astro.started >= 0.75  # partenza = fine dell'incrocio Gaia
    assert astro.elapsed >= astro.started + 0.4 - 0.06  # scaduta a partenza + tempo massimo, non a 0,4 s
    assert astro.elapsed < astro.started + 1.0


# =============================================================================
# T34 — al più 2 richieste per servizio; partenze anticipate ripristinate (D25-21 (5), 25 §3.17 punto 5)


def test_t34_at_most_two_requests_per_service(services, cache):
    import threading

    state = {"now": 0, "max": 0}
    lock = threading.Lock()
    original = services.fake.routes["/gaia/sync"]

    def slow_gaia(request):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        try:
            time.sleep(0.4)
            return original(request)
        finally:
            with lock:
                state["now"] -= 1

    services.fake.routes["/gaia/sync"] = slow_gaia
    prof = build_profile(ProfileTarget(name="51 Peg"), cache=cache)
    gaia_requests = services.count("gaia")
    assert gaia_requests >= 4 and state["max"] == 2  # mai più di 2 richieste Gaia insieme
    assert section(prof, "images").status == "done" and section(prof, "planets").status in ("done", "partial")


def test_t34_photometry_gaia_starts_before_2mass_and_allwise(services, cache):
    arrivals: dict = {}
    stamped(services, "gaia", "allwise_best_neighbour", arrivals, delay=1.5)  # esito AllWISE lento (1 posto Gaia)
    stamped(services, "gaia", "phot_g_mean_flux", arrivals)
    resolved_at = {}
    prof = build_profile(ProfileTarget(name="TRAPPIST-1"), sections=("photometry",), cache=cache,
                         on_resolved=lambda r: resolved_at.setdefault("t", time.monotonic()))
    assert arrivals["phot_g_mean_flux"] - resolved_at["t"] < 1.0  # non aspetta l'esito di AllWISE (1,5 s)
    phot = section(prof, "photometry")
    assert phot.started >= 1.4  # partenza della sezione = ultimo esito (AllWISE)
    assert any(p["catalog"] == "Gaia DR3" for p in phot.details["points"])


def test_t34_bailer_jones_with_gaia_source_and_discarded_without_the_row(services, cache):
    arrivals: dict = {}
    stamped(services, "gaia", "ruwe", arrivals, delay=0.5)  # gaia_source dell'astrometria
    stamped(services, "gaia", "gaiaedr3_distance", arrivals, delay=0.5)
    prof = build_profile(ProfileTarget(name="51 Peg"), sections=("astrometry",), cache=cache)
    assert abs(arrivals["ruwe"] - arrivals["gaiaedr3_distance"]) < 0.3  # partite insieme
    assert any(v.quantity.startswith("distance") for v in section(prof, "astrometry").values)
    services.overrides.clear()
    services.overrides[("gaia", "ruwe")] = lambda q: votable([("source_id", "long", None)], [])
    prof = build_profile(ProfileTarget(name="51 Peg"), sections=("astrometry",), cache=cache, refresh=True)
    astro = section(prof, "astrometry")
    assert not any("gaiaedr3_distance" in str(r.arguments.get("adql")) for r in astro.requests)
    assert not any(v.provenance.table == "external.gaiaedr3_distance" for v in astro.values)
    assert not astro.errors

