# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Tempi del profilo: correzioni dello sprint C7 (``mdfiles/25-analisi-profilo-oggetto.md`` §3.16; §12 T29).

Servizi simulati con le risposte vere registrate (``tests/analysis/profile_fakes.py``), con ritardi aggiunti nel
server locale per vedere quando parte ogni richiesta. Il difetto di ``cds_down_in_session`` (C7-e) è provato in
``tests/core/test_hips_thumbnail.py``.
"""

from __future__ import annotations

import time

import pytest

from astrotwo.analysis.object_profile import ProfileTarget, build_profile
from tests.analysis.profile_fakes import recorded, services, votable  # noqa: F401


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
    assert len(allwise) == 1 and "CONTAINS" in allwise[0] and "designation =" not in allwise[0]
    phot = section(prof, "photometry")
    values = [v for v in phot.values if v.quantity.startswith("AllWISE W")]
    assert values, [v.quantity for v in phot.values]
    for value in values:  # provenanza = la richiesta che ha dato i valori (cerchio, server vero, metodo)
        assert value.provenance.query == allwise[0]
        assert value.provenance.match == "position"
        assert value.provenance.identifier == "WISEA J183656.51+384704.4"
        assert value.provenance.server.startswith(services.url("irsa"))
    # una sola registrazione della richiesta del cerchio nella sezione
    circle = [r for r in phot.requests if "allwise_p3as_psd" in str(r.arguments.get("adql"))]
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
    assert arrivals["phot_g_mean_flux"] - resolved_at["t"] >= 1.9  # Gaia dopo gli incroci, come prima


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
