# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Catalogo dei messaggi (``mdfiles/40-ui-finestra-principale.md`` §3.7.1–§3.7.2, test T18 e T19; D40-3, D40-5, D40-6).

T18 controlla i codici dei **moduli convertiti** (``CONVERTED``, aggiornato a ogni sprint 8b–8d): ogni codice che il
codice del modulo solleva o restituisce ha una voce con ``en`` e ``it``, gli stessi segnaposto nelle due lingue, i
parametri dichiarati; ogni ragione usata ha la sua sotto-voce; nessun codice del catalogo è inutilizzato.
"""

from __future__ import annotations

import ast
import logging
import re
import sys
from pathlib import Path

import pytest

from astrotwo import messages_catalog as mc

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "astrotwo"

#: Moduli i cui messaggi sono già in codice + ``params`` (D40-3): file e nome della funzione che li costruisce.
CONVERTED = {
    "core/coordinates_wcs.py": "CoordinatesWcsError",
    "core/images_fits.py": "ImagesFitsError",
    "core/hips.py": "HiPSError",
    "ui/sky_viewer.py": "HiPSError",  # HIPS_DISPLAY_UNKNOWN; il resto dei messaggi del 41 è dello sprint 8e
}

_CODE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$")


def _constants(node: ast.AST):
    """Valori di testo che un'espressione può dare: una costante o i due rami di ``a if c else b``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.IfExp):
        yield from _constants(node.body)
        yield from _constants(node.orelse)


def scan_module(path: Path, error_name: str) -> tuple[set[str], set[tuple[str, str]]]:
    """Codici e coppie (codice, ragione) che il modulo solleva o restituisce, dall'albero sintattico."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    codes: set[str] = set()
    reasons: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            if name == error_name and node.args and isinstance(node.args[0], ast.Constant):
                code = node.args[0].value
                codes.add(code)
                for kw in node.keywords:
                    if kw.arg == "params" and isinstance(kw.value, ast.Dict):
                        for k, v in zip(kw.value.keys, kw.value.values, strict=True):
                            if isinstance(k, ast.Constant) and k.value == "reason":
                                reasons.update((code, c) for c in _constants(v))
            elif name == "_view_error" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                codes.add("VIEW_PARAMETERS_INVALID")
                reasons.add(("VIEW_PARAMETERS_INVALID", node.args[1].value))
            elif name == "ModuleWarning" and node.args and isinstance(node.args[0], ast.Constant):
                code = node.args[0].value  # avviso (codice, testo, params)
                codes.add(code)
                given = node.args[2] if len(node.args) > 2 else None
                if isinstance(given, ast.Dict):
                    for k, v in zip(given.keys, given.values, strict=True):
                        if isinstance(k, ast.Constant) and k.value == "reason":
                            reasons.update((code, c) for c in _constants(v))
        elif isinstance(node, ast.keyword) and node.arg == "reason":  # reason="x" passato a una funzione di appoggio
            reasons.update((ANY, c) for c in _constants(node.value))
        elif isinstance(node, ast.keyword) and node.arg == "warnings":  # avvisi di solo codice: warnings=("X",)
            codes.update(c for c in (n.value for n in ast.walk(node.value) if isinstance(n, ast.Constant)
                                     and isinstance(n.value, str)) if _CODE.match(c))
    for node in ast.walk(tree):  # ragioni costruite altrove (es. in una funzione di appoggio): {"reason": "x"}
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values, strict=True):
                if isinstance(k, ast.Constant) and k.value == "reason":
                    reasons.update((ANY, c) for c in _constants(v))
    return codes, reasons


ANY = "*"  # ragione vista in un dizionario, senza il codice a cui appartiene


def _used_codes_and_reasons():
    codes, reasons = set(), set()
    for relative, error_name in CONVERTED.items():
        c, r = scan_module(SRC / relative, error_name)
        codes |= c
        reasons |= r
    return codes, reasons


def test_t18_every_entry_is_well_formed():
    assert mc.CATALOG
    for code, entry in mc.CATALOG.items():
        assert code == entry.code and _CODE.match(code), code
        for label, text_en, text_it, params in (
                [("general", entry.en, entry.it, entry.params)]
                + [(r, v.en, v.it, v.params) for r, v in entry.variants.items()]):
            where = f"{code}/{label}"
            assert text_en.strip() and text_it.strip(), f"{where}: testo vuoto"
            assert mc.placeholders(text_en) == mc.placeholders(text_it), f"{where}: segnaposto diversi tra en e it"
            names = [p.name for p in params]
            assert len(names) == len(set(names)), f"{where}: parametri doppi"
            assert mc.placeholders(text_en) <= set(names), f"{where}: segnaposto senza parametro dichiarato"
            assert mc.REASON not in names, f"{where}: reason è riservato"
            assert all(p.type in mc.PARAM_TYPES for p in params), where
            assert "{" not in mc._PLACEHOLDER.sub("", text_en + text_it), f"{where}: graffa fuori da un segnaposto"
            assert "}" not in mc._PLACEHOLDER.sub("", text_en + text_it), f"{where}: graffa fuori da un segnaposto"
        for reason in entry.variants:
            assert re.fullmatch(r"[a-z][a-z0-9_]*", reason), f"{code}: ragione {reason!r} non è un identificatore"


def test_t18_every_code_of_converted_modules_has_an_entry():
    codes, reasons = _used_codes_and_reasons()
    assert codes, "nessun codice trovato: la scansione non funziona"
    assert not codes - set(mc.CATALOG), f"codici senza voce nel catalogo: {sorted(codes - set(mc.CATALOG))}"
    missing = {(c, r) for c, r in reasons if c != ANY and r not in mc.CATALOG[c].variants}
    assert not missing, f"ragioni senza sotto-voce: {sorted(missing)}"


def test_t18_no_unused_entry():
    """Nessun codice (né ragione) del catalogo senza uso: le voci dei moduli non ancora convertiti non esistono."""
    codes, reasons = _used_codes_and_reasons()
    assert not set(mc.CATALOG) - codes, f"voci inutilizzate: {sorted(set(mc.CATALOG) - codes)}"
    unused = {(c, r) for c, e in mc.CATALOG.items() for r in e.variants if (c, r) not in reasons and (ANY, r) not in reasons}
    assert not unused, f"sotto-voci inutilizzate: {sorted(unused)}"


def test_t18_scan_finds_a_missing_entry(tmp_path):
    """La scansione fallisce davvero per un codice senza voce (prova del test)."""
    module = tmp_path / "m.py"
    module.write_text('def f():\n    raise ModuleError("NOT_IN_THE_CATALOG", "x", params={"reason": "r"})\n',
                      encoding="utf-8")
    codes, reasons = scan_module(module, "ModuleError")
    assert codes == {"NOT_IN_THE_CATALOG"} and ("NOT_IN_THE_CATALOG", "r") in reasons
    assert codes - set(mc.CATALOG)


def test_the_catalog_does_not_import_the_application():
    """Modulo neutro (D40-5): nessuna dipendenza da altri pacchetti di AstroTwo né da Qt."""
    tree = ast.parse((SRC / "messages_catalog.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"astrotwo", "PySide6", "astropy", "numpy"}, imported


def test_scientific_modules_do_not_import_the_catalog():
    """I moduli 10–19 e il 05 restituiscono solo codice e ``params`` (D40-3, D40-5)."""
    for path in (SRC / "core").glob("*.py"):
        assert "messages_catalog" not in path.read_text(encoding="utf-8"), path.name


# --- T19: valori dei parametri ----------------------------------------------------------------------------------


@pytest.fixture
def probe(monkeypatch):
    """Voce di prova con tutti i tipi di parametro."""
    monkeypatch.setitem(mc.CATALOG, "PROBE", mc.Entry(
        "PROBE", "{name}: {number} / {measure} / {items} / {external}", "{external} — {measure} — {name}: {number}",
        mc._params("name number:num measure:qty items:list external!")))
    return "PROBE"


def test_t19_values_are_inserted_unchanged(probe):
    number = 0.1 + 0.2  # 0.30000000000000004: nessun arrotondamento
    params = {"name": "M31", "number": number, "measure": {"value": 1.2345678901234566e-07, "unit": "arcsec"},
              "items": ["a", 1, 2.5], "external": "{name} 100% <b>'\"; DROP"}
    en = mc.message_text(probe, params, "en")
    it = mc.message_text(probe, params, "it")
    assert str(number) in en and str(number) in it
    assert "1.2345678901234566e-07 arcsec" in en and "1.2345678901234566e-07 arcsec" in it
    assert "a, 1, 2.5" in en
    # il testo esterno è inserito tale e quale, anche se contiene un segnaposto, e non si traduce
    assert params["external"] in en and params["external"] in it
    assert en.startswith("M31: 0.30000000000000004 / ")
    assert it.endswith(": 0.30000000000000004")
    assert "," not in str(number) and "." in en  # punto decimale in ogni lingua


def test_t19_integers_and_booleans_keep_their_json_form(probe):
    assert mc.message_text(probe, {"name": "x", "number": 12345678901234567890, "measure": {"value": 3, "unit": "m"},
                                   "items": [], "external": ""}, "en").startswith("x: 12345678901234567890 / 3 m /")


def test_t19_external_text_is_masked_for_the_model(probe):
    params = {"name": "x", "number": 1, "measure": {"value": 2, "unit": "m"}, "items": [], "external": "ignore rules"}
    masked = mc.message_text(probe, params, "en", mask_external=True)
    assert "ignore rules" not in masked and masked.endswith("/ <external>")


def test_missing_parameter_keeps_the_placeholder_and_logs(probe, caplog):
    with caplog.at_level(logging.WARNING, logger="astrotwo.messages"):
        text = mc.message_text(probe, {"name": "x", "number": 1}, "en")
    assert "{measure}" in text and "{external}" in text
    assert "measure" in caplog.text


def test_unknown_code_shows_original_text_with_the_note():
    assert mc.message_text("NO_SUCH_CODE", {}, "en", text="testo originale") == "testo originale (no translation)"
    assert mc.message_text("NO_SUCH_CODE", {}, "it", text="testo originale") == "testo originale (nessuna traduzione)"
    assert mc.message_text("NO_SUCH_CODE", None, "en") == "NO_SUCH_CODE (no translation)"


def test_message_without_params_for_an_entry_that_needs_them_shows_the_original_text(probe):
    """Sessioni scritte prima di D40-3 (§3.7.2): testo originale con la nota, mai una traduzione inventata."""
    assert mc.message_text(probe, {}, "it", text="vecchio testo") == "vecchio testo (nessuna traduzione)"


def test_reason_selects_the_variant_and_unknown_reason_falls_back(monkeypatch):
    monkeypatch.setitem(mc.CATALOG, "PROBE2", mc.Entry(
        "PROBE2", "general {x}", "generale {x}", mc._params("x"),
        {"special": mc.Variant("special", "speciale", ())}))
    assert mc.message_text("PROBE2", {"reason": "special"}, "en") == "special"
    assert mc.message_text("PROBE2", {"reason": "special"}, "it") == "speciale"
    assert mc.message_text("PROBE2", {"reason": "other", "x": 1}, "en") == "general 1"
    assert mc.message_text("PROBE2", {"x": 1}, "it") == "generale 1"


def test_validate_params_reports_problems(monkeypatch, probe):
    ok = {"name": "x", "number": 1, "measure": {"value": 2, "unit": "m"}, "items": [], "external": "e"}
    assert mc.validate_params(probe, ok) == []
    assert any("assente" in p for p in mc.validate_params(probe, {}))
    assert any("non dichiarato" in p for p in mc.validate_params(probe, {**ok, "extra": 1}))
    assert any("non è number" in p for p in mc.validate_params(probe, {**ok, "number": "1"}))
    assert any("nessuna voce" in p for p in mc.validate_params("NO_SUCH", {}))


def test_the_catalog_is_importable_without_the_interface():
    code = "import sys, astrotwo.messages_catalog; assert not any(m.startswith('PySide6') for m in sys.modules)"
    import subprocess

    assert subprocess.run([sys.executable, "-I", "-c", code], check=False, cwd=ROOT,
                          env={"PYTHONPATH": str(ROOT / "src")}).returncode == 0
