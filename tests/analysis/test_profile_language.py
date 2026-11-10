# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Lingua della scheda del profilo (PDF), DD-1 e DD-3 (a) (``mdfiles/25-analisi-profilo-oggetto.md`` §3.15, T36).

Il PDF in inglese **non contiene nessuna parola italiana**: intestazioni, avvisi ed errori (dal catalogo dei messaggi
con codice e ``params``), note dei valori e fonti, per i profili costruiti con le risposte vere registrate
(``tests/analysis/profile_fakes.py``: 51 Peg, Vega, eta Tau, TRAPPIST-1, CDS giù) e con l'archivio Gaia o il NASA
Exoplanet Archive giù. Lo stesso profilo nella stessa lingua dà lo stesso file, byte per byte; in italiano un file
diverso. Nessuna rete.
"""

from __future__ import annotations

import re

import pytest
from astropy.table import Table
from matplotlib.figure import Figure

from astrotwo.analysis import profile_export as pe
from astrotwo.analysis.profile_export import export_profile, merge_profile_results
from astrotwo.messages_catalog import CATALOG
from tests.analysis.profile_fakes import INDEX, recorded, services, votable  # noqa: F401
from tests.analysis.test_profile_export import profile, session_with_export, values_of

_WORD = re.compile(r"[A-Za-zÀ-ÿ'_0-9]+")  # «r_lo_geo» è una parola sola
#: Parole italiane brevi o comuni che il confronto tra le due lingue del catalogo potrebbe non trovare.
_COMMON_ITALIAN = {"il", "lo", "la", "gli", "le", "un", "una", "di", "del", "della", "dei", "degli", "delle", "da",
                   "dal", "dalla", "nel", "nella", "sul", "sulla", "con", "per", "non", "che", "nessun", "nessuna",
                   "nessuno", "epoca", "sorgente", "sorgenti", "posizione", "parallasse", "errore", "sistema",
                   "qualità", "pianeta", "pianeti", "ospite", "archivio", "incrocio", "mediana", "geometrica",
                   "fotogeometrica", "punto", "zero", "centro", "survey", "entro", "riuscito", "riuscita",
                   "confermato", "coordinate", "scritte", "parametri", "soglia", "correzione", "limite",
                   "superiore", "inferiore", "documentazione", "tabella", "tabelle", "versione", "valida",
                   "trattata", "scala", "dichiarato", "dichiarata", "richiesta", "risposta", "mirror", "Harvard"}


def italian_words() -> set[str]:
    """Parole che compaiono solo nei testi italiani del catalogo dei messaggi e delle intestazioni del PDF, più le
    parole italiane comuni (quelle uguali nelle due lingue, come «Gaia» o «cache», non contano)."""
    english, italian = set(), set()
    for entry in CATALOG.values():
        texts = [(entry.en, entry.it)] + [(v.en, v.it) for v in (entry.variants or {}).values()]
        for en, it in texts:
            english |= {w.lower() for w in _WORD.findall(en)}
            italian |= {w.lower() for w in _WORD.findall(it)}
    for key, text in pe._LABELS["it"].items():
        italian |= {w.lower() for w in _WORD.findall(text)}
        english |= {w.lower() for w in _WORD.findall(pe._LABELS["en"].get(key, ""))}
    found = {w for w in italian - english if len(w) > 2 or w in _COMMON_ITALIAN}
    common = {w.lower() for w in _COMMON_ITALIAN} - english - {"survey", "mirror", "harvard", "zero", "limite"}
    return found | common


def drawn_texts(monkeypatch) -> list[str]:
    """Ogni testo scritto nelle pagine del PDF (``Figure.text``), nell'ordine."""
    texts: list[str] = []
    original = Figure.text

    def record(self, x, y, s, *args, **kwargs):
        texts.append(str(s))
        return original(self, x, y, s, *args, **kwargs)

    monkeypatch.setattr(Figure, "text", record)
    return texts


def italian_in(texts, vocabulary) -> list[tuple[str, str]]:
    return [(w, t) for t in texts for w in _WORD.findall(t) if w.lower() in vocabulary]


CASES = {
    "51 Peg": {},
    "Vega": {},
    "eta Tau": {},
    "TRAPPIST-1": {},
    "51 Peg, Gaia archive down": {("gaia", ""): lambda q: (503, "text/plain", "coda piena")},
    "TRAPPIST-1, exoplanet archive down": {("exoplanet", ""): lambda q: (503, "text/plain", "manutenzione")},
}


@pytest.mark.parametrize("case", list(CASES))
def test_t36_english_pdf_has_no_italian_word(cache, services, tmp_path, monkeypatch, case):  # noqa: F811
    services.overrides.update(CASES[case])
    session = session_with_export(cache)
    number, result = profile(session, {"name": case.split(",")[0]})
    assert result.status == "ok", result.error
    data = merge_profile_results([(number, values_of(result))])
    vocabulary = italian_words()
    assert {"nessun", "epoca", "parallasse", "della"} <= vocabulary  # il rivelatore riconosce l'italiano
    texts = drawn_texts(monkeypatch)
    english = export_profile(data, tmp_path / "en.pdf", "pdf", language="en")
    assert texts and italian_in(texts, vocabulary) == []
    assert b"/Title (Profile of " in (tmp_path / "en.pdf").read_bytes()
    # stesso profilo, stessa lingua: stesso file byte per byte (D25-20 (7), DD-1)
    again = export_profile(data, tmp_path / "en2.pdf", "pdf", language="en")
    assert again.sha256 == english.sha256 and (tmp_path / "en.pdf").read_bytes() == (tmp_path / "en2.pdf").read_bytes()
    # in italiano: intestazioni e avvisi in italiano, file diverso
    texts.clear()
    italian = export_profile(data, tmp_path / "it.pdf", "pdf", language="it")
    assert italian.sha256 != english.sha256 and italian_in(texts, vocabulary)
    # l'ECSV (che non dipende dalla lingua) ha note e servizi in inglese
    table = Table.read(export_profile(data, tmp_path / "v.ecsv", "ecsv").path, format="ascii.ecsv")
    cells = [str(table[c][i]) for c in ("note", "service", "formula", "interval_kind") for i in range(len(table))]
    assert italian_in(cells, vocabulary) == []


def test_t36_warnings_follow_the_pdf_language(cache, services):  # noqa: F811
    services.overrides[("gaia", "")] = lambda q: (503, "text/plain", "coda piena")
    session = session_with_export(cache)
    number, result = profile(session, {"name": "51 Peg"})
    data = merge_profile_results([(number, values_of(result))])
    astrometry = next(s for s in data["sections"] if s["name"] == "astrometry")
    assert astrometry["errors"]  # l'errore del 14 ha codice e params (D40-3)
    error = astrometry["errors"][0]
    en = pe._message_line(error, pe._LABELS["en"])
    it = pe._message_line(error, pe._LABELS["it"])
    assert en.startswith(error["code"] + ": ") and it.startswith(error["code"] + ": ") and en != it
    from astrotwo.messages_catalog import message_text

    assert en == f"{error['code']}: {message_text(error['code'], error['params'], 'en', text=error['text'])}"


def test_t36_simbad_down_name_resolver_path_is_english(cache, services, tmp_path, monkeypatch):  # noqa: F811
    """SIMBAD giù (come il 2026-11-10, misure di validazione): bersaglio dal risolutore di nomi del 10, la cui fonte
    porta una nota italiana; nel profilo e nel PDF inglese la fonte della posizione e gli avvisi sono in inglese."""
    from astropy.time import Time

    from astrotwo.analysis import object_profile as op
    from astrotwo.core import coordinates_wcs as cw
    from astrotwo.core.coordinates_wcs import ResolvedName, SkyFrame

    services.overrides[("simbad", "")] = lambda q: (503, "text/plain", "giù")
    services.overrides[("gaia", "CONTAINS")] = lambda q: votable(  # nessuna sorgente Gaia per posizione
        [("source_id", "long", None), ("ra", "double", "deg"), ("dec", "double", "deg"),
         ("phot_g_mean_mag", "float", "mag")], [])
    coords = SkyFrame.from_lonlat(344.36658535524 * cw.u.deg, 20.768832511140005 * cw.u.deg, "icrs",
                                  epoch=Time("J2000.0"))
    source = f"SIMBAD (Harvard mirror) via astroquery; {cw._SIMBAD_EPOCH_NOTE}"  # testo del 10, in italiano
    monkeypatch.setattr(op, "resolve_name", lambda name, **kw: ResolvedName(
        name, "* 51 Peg", coords, source, "https://simbad.harvard.edu/simbad/sim-tap", Time.now().datetime, False,
        None, None, None, None, service="simbad_harvard"))
    # D25-23: con SIMBAD giù i pianeti si cercano con il nome scritto; risposta sintetica dell'ospite, pianeti dalla
    # risposta vera registrata per 51 Peg (stesse righe di pscomppars)
    services.overrides[("exoplanet", "hostname IN ('51 Peg')")] = lambda q: votable(
        [("hostname", "char", None), ("gaia_dr3_id", "char", None)], [["51 Peg", "Gaia DR3 2835207319109249920"]])
    services.overrides[("exoplanet", "WHERE hostname = '51 Peg'")] = lambda q: recorded("exoplanet", next(
        k.split("|", 1)[1] for k in INDEX if k.startswith("exoplanet|SELECT pl_name")
        and "2835207319109249920" in k))
    session = session_with_export(cache)
    number, result = profile(session, {"name": "51 Peg", "sections": ["identity", "astrometry", "planets"]})
    assert result.status == "ok", result.error
    resolved = result.values["resolved"]
    assert resolved["method"] == "name_resolver"
    assert resolved["position_source"] == ("SIMBAD (Harvard mirror), name resolver, ICRS J2000 "
                                           "(https://simbad.harvard.edu/simbad/sim-tap)")
    data = merge_profile_results([(number, values_of(result))])
    texts = drawn_texts(monkeypatch)
    export_profile(data, tmp_path / "en.pdf", "pdf", language="en")
    vocabulary = italian_words()
    assert any("PROFILE_NO_IDENTIFIERS" in t for t in texts) and italian_in(texts, vocabulary) == []
    # D25-23: ospite trovato con il nome scritto, dichiarato in inglese; i pianeti di 51 Peg nel PDF
    assert any("PROFILE_PLANETS_BY_WRITTEN_NAME: Planet host 51 Peg found by the written name" in t for t in texts)
    assert any("51 Peg b" in t for t in texts)
