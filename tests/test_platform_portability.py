# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Portabilità su Windows e Linux, sprint W1 (``mdfiles/65-windows-linux.md`` §12).

Sul Mac si prova che le correzioni del W1 **non cambiano niente su macOS** (stessi byte di prima) e si **simula**
Windows dove si può (``os.linesep`` di Windows, conversione degli URL ``file:``, riduzione dei percorsi per l'IA).
Quello che si vede solo sui runner veri (traduzione del testo di Python su Windows, Portachiavi assente) è nei test
con ``skipif`` qui sotto e nel workflow ``.github/workflows/tests.yml``.
"""

from __future__ import annotations

import ast
import os
import sys
import warnings
from pathlib import Path

import astropy.units as u
import pytest
from astropy.io import ascii as astropy_ascii
from astropy.io.votable import from_table
from astropy.table import Table

from astrotwo.core.catalogs import ascii_table_text, read_table, write_votable_file
from astrotwo.core.vo_protocols import SampHub, export_table, file_url_path

ROOT = Path(__file__).resolve().parent.parent

VOTABLE = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><COOSYS ID="s" system="ICRS" epoch="J2016.0"/>
<TABLE>
<FIELD name="ra" datatype="double" unit="deg" ucd="pos.eq.ra;meta.main" ref="s"/>
<FIELD name="dec" datatype="double" unit="deg" ucd="pos.eq.dec;meta.main" ref="s"/>
<FIELD name="name" datatype="char" arraysize="*"><DESCRIPTION>Nome (Ångström, 5′)</DESCRIPTION></FIELD>
<DATA><TABLEDATA>
<TR><TD>56.75</TD><TD>24.1167</TD><TD>Alcyone η Tau</TD></TR>
<TR><TD>56.80</TD><TD>24.1200</TD><TD>Merope 23 Tau</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""


@pytest.fixture
def catalog(tmp_path):
    path = tmp_path / "pleiadi.xml"
    path.write_text(VOTABLE, encoding="utf-8")
    return read_table(path)


def _sample_table() -> Table:
    table = Table({"ra": [56.75, 56.80] * u.deg, "name": ["Alcyone η Tau", "Merope, 23 Tau"]})
    table["ra"].description = "Ascensione retta (°)"
    return table


# --- stessi byte su macOS e Linux (dove os.linesep è "\n") ---------------------------------------------------------


@pytest.mark.skipif(os.linesep != "\n", reason="confronto con la scrittura diretta di Astropy: solo dove è già LF")
def test_votable_bytes_unchanged_where_lf(tmp_path):
    """``write_votable_file`` = ``vot.to_xml(nome)`` byte per byte su macOS e Linux (nessun cambio su macOS)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        vot = from_table(_sample_table())
        vot.to_xml(str(tmp_path / "direct.xml"))
    write_votable_file(vot, tmp_path / "new.xml")
    assert (tmp_path / "new.xml").read_bytes() == (tmp_path / "direct.xml").read_bytes()
    assert b"\r" not in (tmp_path / "new.xml").read_bytes()


def test_votable_gz_name_still_compressed_by_astropy(tmp_path):
    """Un nome ``.gz`` resta ad Astropy, che comprime con gzip, come prima del W1 (65 §10)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        write_votable_file(from_table(_sample_table()), tmp_path / "t.xml.gz")
    assert (tmp_path / "t.xml.gz").read_bytes()[:2] == b"\x1f\x8b"


@pytest.mark.skipif(os.linesep != "\n", reason="confronto con la scrittura diretta di Astropy: solo dove è già LF")
@pytest.mark.parametrize("kwargs", [{"format": "ecsv"}, {"format": "ecsv", "delimiter": ","},
                                    {"format": "csv", "fast_writer": False}])
def test_ascii_bytes_unchanged_where_lf(tmp_path, kwargs):
    """``ascii_table_text`` in UTF-8 = file scritto da ``astropy.io.ascii.write`` su macOS e Linux."""
    table = _sample_table()
    astropy_ascii.write(table, str(tmp_path / "direct.txt"), **kwargs)
    assert ascii_table_text(table, **kwargs).encode("utf-8") == (tmp_path / "direct.txt").read_bytes()


# --- Windows simulato: os.linesep = "\r\n" ------------------------------------------------------------------------


@pytest.mark.parametrize("kwargs", [{"format": "ecsv"}, {"format": "csv", "fast_writer": False}])
def test_ascii_text_lf_with_windows_linesep(monkeypatch, kwargs):
    """Il writer di Astropy unisce le righe con ``os.linesep``: con quello di Windows il testo resta identico."""
    table = _sample_table()
    expected = ascii_table_text(table, **kwargs)
    monkeypatch.setattr(os, "linesep", "\r\n")
    simulated = ascii_table_text(table, **kwargs)
    assert "\r" not in simulated and simulated == expected


@pytest.mark.parametrize("fmt", ["csv", "ecsv", "votable"])
def test_exports_without_cr_with_windows_linesep(monkeypatch, catalog, tmp_path, fmt):
    """Esportazioni di testo del 14 senza ``\\r`` anche con ``os.linesep`` di Windows, UTF-8 con i caratteri non ASCII.

    La traduzione ``\\n`` → ``\\r\\n`` dei file aperti in modalità testo si vede solo su Windows (runner del workflow):
    i file di testo si scrivono in binario o con ``newline`` esplicito (``test_text_writes_declare_newline``)."""
    monkeypatch.setattr(os, "linesep", "\r\n")
    path = export_table(catalog, tmp_path / f"t.{fmt}", fmt).path
    data = path.read_bytes()
    assert b"\r" not in data
    assert "Alcyone η Tau" in data.decode("utf-8")


def _text_writes_without_newline(source: str) -> list[int]:
    """Righe con ``write_text(...)`` o ``open(..., "w"/"a"/"x")`` in modalità testo senza ``newline=``."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        keywords = {k.arg for k in node.keywords}
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "write_text" and "newline" not in keywords:
            lines.append(node.lineno)
        if isinstance(func, ast.Name) and func.id == "open" and len(node.args) >= 2:
            mode = node.args[1]
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and "b" not in mode.value \
                    and set(mode.value) & set("wax") and "newline" not in keywords:
                lines.append(node.lineno)
    return lines


def test_text_writes_declare_newline():
    """Nessun file di testo scritto da AstroTwo con la fine riga del sistema (65 §3.2): stessi byte ovunque."""
    found = {}
    for path in sorted((ROOT / "src" / "astrotwo").rglob("*.py")):
        lines = _text_writes_without_newline(path.read_text(encoding="utf-8"))
        if lines:
            found[str(path.relative_to(ROOT))] = lines
    assert found == {}


def test_text_writes_check_finds_the_old_forms():
    assert _text_writes_without_newline('p.write_text("a\\n", encoding="utf-8")\nopen(f, "w")\n') == [1, 2]
    assert _text_writes_without_newline('p.write_text("a", newline="\\n")\nopen(f, "wb")\nopen(f)\n') == []


# --- URL file: di SAMP --------------------------------------------------------------------------------------------


def test_file_url_path_windows():
    assert file_url_path("/C:/Users/ada/Dati%20VO/t.xml") == "C:\\Users\\ada\\Dati VO\\t.xml"
    assert file_url_path("//nas/condivisa/t.xml") == "\\\\nas\\condivisa\\t.xml"


@pytest.mark.skipif(sys.platform == "win32", reason="percorso POSIX")
def test_samp_file_url_posix_unchanged(tmp_path):
    """Su macOS e Linux la copia di un ``file:`` resta quella di prima (``unquote``), anche con spazi e accenti."""
    source = tmp_path / "Dati VO" / "tabella è.xml"
    source.parent.mkdir()
    source.write_text(VOTABLE, encoding="utf-8")
    copied = SampHub.save_votable(source.as_uri(), tmp_path / "copia.xml")
    assert copied.read_bytes() == source.read_bytes()


@pytest.mark.skipif(sys.platform != "win32", reason="URL file: di Windows: solo sul runner Windows")
def test_samp_file_url_windows(tmp_path):
    source = tmp_path / "Dati VO" / "tabella è.xml"
    source.parent.mkdir()
    source.write_text(VOTABLE, encoding="utf-8", newline="\n")
    copied = SampHub.save_votable(source.as_uri(), tmp_path / "copia.xml")
    assert copied.read_bytes() == source.read_bytes()


# --- percorsi nei testi per l'IA (32 §3.7) ------------------------------------------------------------------------


def test_windows_paths_reduced_to_file_names_only_on_windows(monkeypatch):
    from astrotwo.ai import tool_registry as tr

    text = "apri C:\\Users\\ada\\dati\\m45.fits e \\\\nas\\vo\\cat.xml; file:///D:/x/y.fits; rapporto 3:2, 10/2"
    if os.name != "nt":  # macOS e Linux: percorsi di Windows invariati (il file:/// era già ridotto prima del W1)
        assert tr._file_name(text) == text.replace("file:///D:/x/y.fits", "y.fits")
    monkeypatch.setattr(os, "name", "nt")
    assert tr._file_name(text) == "apri m45.fits e cat.xml; y.fits; rapporto 3:2, 10/2"


# --- Portachiavi fuori da macOS ------------------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "darwin", reason="fuori da macOS")
def test_keychain_unavailable_outside_macos():
    """Fino a D65-1 l'assistente IA non ha dove tenere la chiave: errore dichiarato, il resto dell'app funziona."""
    from astrotwo.ai.keychain_keys import KeychainError, KeychainStore

    with pytest.raises(KeychainError) as err:
        KeychainStore()
    assert err.value.code == "KEYCHAIN_UNAVAILABLE" and err.value.params["reason"] == "not_macos"

