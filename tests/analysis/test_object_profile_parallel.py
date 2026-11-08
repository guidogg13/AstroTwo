# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Profilo in parallelo e Annulla (``mdfiles/25-analisi-profilo-oggetto.md`` §3.12; §12: T10, T11, T21–T23; 05 T29).

Servizi simulati con le risposte vere registrate il 2026-11-07 (``tests/analysis/profile_fakes.py``), con ritardi
aggiunti nel server locale per rendere osservabili ordine di arrivo, richieste contemporanee, scadenze e annullamento.
"""

from __future__ import annotations

import threading
import time

import astropy.units as u
import pytest

import astrotwo.analysis.object_profile as op
from astrotwo.analysis.object_profile import (
    MAX_CONCURRENT_REQUESTS,
    SECTION_SERVICES,
    SERVICE_TIME_LIMITS,
    ProfileTarget,
    build_profile,
    command_specs,
)
from astrotwo.core.commands import CancelToken, Command, RequestedBy, Session, default_registry
from tests.analysis.profile_fakes import recorded, services  # noqa: F401
from tests.message_helpers import check_message

ALL = ("simbad", "gaia", "irsa", "exoplanet", "vizier")
#: Le tre sezioni del pianificatore verificate qui (Immagini e Pianeti hanno i loro test, T8, T9, T24).
THREE = ("identity", "astrometry", "photometry")


@pytest.fixture(scope="module", autouse=True)
def warm_matplotlib():
    """Il primo disegno di matplotlib in un processo di test costruisce la cache dei caratteri (alcuni secondi, fuori
    dal profilo): lo si fa prima, così i tempi misurati qui sono quelli dei servizi simulati."""
    import io

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure = plt.figure()
    figure.text(0.5, 0.5, "λ Fν µm")
    figure.savefig(io.BytesIO(), format="png")
    plt.close(figure)


def delayed(services, service: str, seconds: float, *, text: str = "", before=None) -> None:
    """Risposta registrata di ``service`` dopo ``seconds`` (VizieR: 503, CDS giù come il 2026-11-07)."""
    def make(query):
        if before is not None:
            before()
        time.sleep(seconds)
        if service == "vizier":
            return 503, "text/plain", "CDS non raggiungibile (come il 2026-11-07)"
        return recorded(service, query)
    services.overrides[(service, text)] = make


def profile(cache, **kw):
    kw.setdefault("sections", THREE)
    return build_profile(ProfileTarget(name="TRAPPIST-1"), cache=cache, **kw)


def statuses(prof) -> dict:
    return {s.name: s.status for s in prof.sections}


# =============================================================================
# T11 — arrivo progressivo: nell'ordine dei tempi, una volta, nel thread di chi chiama


@pytest.mark.parametrize("slow_service, last", [("exoplanet", "identity"), ("irsa", "photometry")])
def test_t11_sections_arrive_in_the_order_of_their_times(services, cache, slow_service, last):
    delayed(services, slow_service, 3.0)
    seen, threads = [], []

    def on_section(section):
        seen.append(section.name)
        threads.append(threading.get_ident())

    prof = profile(cache, on_section=on_section)
    assert sorted(seen) == ["astrometry", "identity", "photometry"]  # ogni sezione una volta
    assert seen[-1] == last
    assert set(threads) == {threading.get_ident()}  # mai da un thread di lavoro
    elapsed = {s.name: s.elapsed for s in prof.sections}
    assert [elapsed[n] for n in seen] == sorted(elapsed[n] for n in seen)
    assert statuses(prof) == {"identity": "done", "astrometry": "done", "photometry": "partial"}  # VizieR giù
    assert [s.name for s in prof.sections] == ["identity", "astrometry", "photometry"]  # ordine del profilo fisso
    assert not prof.cancelled and prof.elapsed >= 3.0


def test_t11_parallel_profile_equals_the_serial_values(services, cache):
    """Stessi valori, avvisi e incroci indipendentemente dai ritardi (risultati applicati in ordine fisso)."""
    from astrotwo.analysis.object_profile import profile_content

    first = profile_content(profile(cache).as_dict())
    delayed(services, "gaia", 0.3)  # ora dalla cache: nessuna richiesta, stesso contenuto
    again = profile_content(profile(cache).as_dict())
    assert first == again


# =============================================================================
# T21 — al più 4 richieste di rete contemporanee


def test_t21_at_most_four_requests_at_the_same_time(services, cache):
    lock = threading.Lock()
    state = {"open": 0, "max": 0}

    def enter():
        with lock:
            state["open"] += 1
            state["max"] = max(state["max"], state["open"])

    def counted(service):
        def make(query):
            enter()
            try:
                time.sleep(0.3)
                if service == "vizier":
                    return 503, "text/plain", "CDS non raggiungibile"
                return recorded(service, query)
            finally:
                with lock:
                    state["open"] -= 1
        return make

    for service in ALL:
        services.overrides[(service, "")] = counted(service)
    prof = profile(cache)
    assert statuses(prof) == {"identity": "done", "astrometry": "done", "photometry": "partial"}
    assert MAX_CONCURRENT_REQUESTS == 4
    assert 1 < state["max"] <= MAX_CONCURRENT_REQUESTS  # le sezioni girano davvero insieme, mai più di 4


def test_t21_time_limits_of_the_services_and_of_the_sections():
    assert {k: float(v.to_value(u.s)) for k, v in SERVICE_TIME_LIMITS.items()} == {
        "simbad": 15.0, "gaia": 30.0, "irsa": 60.0, "exoplanet": 30.0, "hips": 30.0, "vizier_sed": 30.0}
    assert {name: float(op._section_limit(name).to_value(u.s)) for name in SECTION_SERVICES} == {
        "identity": 60.0, "astrometry": 30.0, "photometry": 60.0, "images": 30.0, "planets": 30.0}
    timeouts = op._limited(op.NETWORK_TIMEOUTS, "simbad")
    assert (timeouts.connect, timeouts.read) == (10.0, 15.0)  # minimo tra il 04 (10 s / 60 s) e il servizio
    assert float(op.PROFILE_TARGET_TIME.to_value(u.s)) == 60.0


# =============================================================================
# T22 — tempo massimo di una sezione


def test_t22_section_over_its_time_is_an_error_and_the_others_continue(services, cache, monkeypatch):
    limit = op._section_limit
    monkeypatch.setattr(op, "_section_limit", lambda name: 0.5 * u.s if name == "astrometry" else limit(name))
    delayed(services, "gaia", 2.0, text="FROM gaiadr3.gaia_source WHERE source_id")  # astrometria e fotometria
    seen = []
    started = time.monotonic()
    prof = profile(cache, on_section=lambda s: seen.append((s.name, s.status, time.monotonic() - started)))
    arrival = {name: (status, at) for name, status, at in seen}
    assert arrival["astrometry"][0] == "error" and arrival["astrometry"][1] < 1.5  # prima della risposta lenta (2 s)
    assert [n for n, _, _ in seen].index("astrometry") < [n for n, _, _ in seen].index("photometry")
    astrometry = next(s for s in prof.sections if s.name == "astrometry")
    error = astrometry.errors[0]
    assert error["code"] == "PROFILE_SECTION_TIMEOUT"
    assert error["params"] == {"section": "astrometry", "limit": {"value": 0.5, "unit": "s"},
                               "services": ["gaia"]}
    check_message(error["code"], error["params"], error["text"])
    assert statuses(prof)["identity"] == "done" and statuses(prof)["photometry"] == "partial"
    assert not astrometry.values  # la risposta tardiva è scartata


# =============================================================================
# T10 — sezioni indipendenti in parallelo: un servizio giù non ferma le altre


def test_t10_a_failing_service_does_not_stop_the_parallel_sections(services, cache):
    services.overrides[("gaia", "FROM gaiadr3.gaia_source WHERE source_id")] = (
        lambda q: (400, "text/plain", "archivio Gaia rifiuta la richiesta"))
    prof = profile(cache)
    st = statuses(prof)
    assert st["identity"] == "done" and st["astrometry"] in ("partial", "error") and st["photometry"] == "partial"
    photometry = next(s for s in prof.sections if s.name == "photometry")
    assert {e["catalog"] for e in photometry.errors} == {"Gaia DR3", "vizier_sed"}
    assert any(v.quantity.startswith("2MASS") for v in photometry.values)


# =============================================================================
# T23 — Annulla: arrivate conservate, le altre annullate, nessuna nuova richiesta


def test_t23_cancel_keeps_the_arrived_sections(services, cache):
    for service in ("exoplanet", "irsa"):
        delayed(services, service, 2.0)
    stop = threading.Event()
    seen = []

    def on_section(section):
        seen.append((section.name, section.status))
        if section.name == "astrometry":
            stop.set()

    started = time.monotonic()
    prof = profile(cache, on_section=on_section, cancel=stop.is_set)
    took = time.monotonic() - started
    sent = services.count()
    assert prof is not None and prof.cancelled
    assert seen[0] == ("astrometry", "done")
    assert statuses(prof) == {"identity": "cancelled", "astrometry": "done", "photometry": "cancelled"}
    assert sorted(n for n, _ in seen) == ["astrometry", "identity", "photometry"]  # annullate annunciate anche loro
    assert took < 1.5  # ritorno prima delle risposte lente (2 s)
    astrometry = next(s for s in prof.sections if s.name == "astrometry")
    assert astrometry.values and astrometry.elapsed is not None
    time.sleep(2.5)
    assert services.count() == sent  # nessuna nuova richiesta dopo Annulla
    assert prof.as_dict()["cancelled"] is True


def test_t23_cancel_before_the_target_is_resolved_returns_none(services, cache):
    stop = threading.Event()
    delayed(services, "simbad", 1.0, before=stop.set)
    started = time.monotonic()
    assert profile(cache, cancel=stop.is_set) is None
    assert time.monotonic() - started < 0.9


# =============================================================================
# T29 del 05 / T23 del 25 — object.profile annullato dalla barra di stato (CancelToken)


def registry_with_profile(cache):
    registry = default_registry(cache=cache)
    for spec in command_specs():
        registry.register(spec)
    return registry


def test_t29_cancelled_command_keeps_the_partial_profile(services, cache):
    for service in ("exoplanet", "irsa"):
        delayed(services, service, 2.0)
    session = Session(registry_with_profile(cache))
    token = CancelToken()
    reports = []

    def progress(report):
        reports.append(report)
        if report.text == "object_profile/astrometry":
            token.cancel()

    before = session.workspace.state
    result = session.run(Command("object.profile", 1, {"name": "TRAPPIST-1", "sections": list(THREE)}, RequestedBy("menu")), cancel=token,
                         progress=progress)
    assert result.status == "cancelled"
    assert result.error.code == "COMMAND_CANCELLED" and result.error.params == {"reason": "partial"}
    check_message(result.error.code, result.error.params, result.error.text)
    sections = {s["name"]: s["status"] for s in result.values["sections"]}
    assert sections == {"identity": "cancelled", "astrometry": "done", "photometry": "cancelled"}
    assert result.values["cancelled"] is True
    entry = session.history.entries[-1]
    assert entry.result.status == "cancelled"
    assert entry.command.parameters["simbad_id"] == "TRAPPIST-1"  # scritto anche se annullato
    assert session.workspace.state is before  # sola lettura: stato invariato
    steps = [(r.step, r.total, r.text) for r in reports if r.total]
    assert steps[0] == (1, 3, "object_profile/astrometry")
    assert len(steps) == 3  # una sezione per passo, anche quelle annullate


def test_t29_progress_is_one_step_per_section(services, cache):
    registry = registry_with_profile(cache)
    assert registry.spec("object.profile").steps is None  # n di m dalle sezioni scelte
    reports = []
    result = Session(registry).run(Command("object.profile", 1, {"name": "TRAPPIST-1", "sections": list(THREE)}, RequestedBy("menu")),
                                   progress=reports.append)
    assert result.status == "ok"
    texts = [r.text for r in reports if r.total]
    assert sorted(texts) == ["object_profile/astrometry", "object_profile/identity", "object_profile/photometry"]
    assert [r.step for r in reports if r.total] == [1, 2, 3]


def test_t29_cancelled_before_the_target_is_discarded(services, cache):
    token = CancelToken()
    delayed(services, "simbad", 1.0, before=token.cancel)
    result = Session(registry_with_profile(cache)).run(
        Command("object.profile", 1, {"name": "TRAPPIST-1", "sections": list(THREE)}, RequestedBy("menu")), cancel=token)
    assert result.status == "cancelled" and result.error.params == {"reason": "discarded"}
    assert not result.values
