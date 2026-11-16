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


# --- chiavi API: archivio del sistema (D65-1, sprint W2) -----------------------------------------------------------


class _MemoryBackend:
    """Archivio finto in memoria al posto della Gestione credenziali o del Secret Service: mai quello vero."""

    priority = 5
    items: dict = {}

    def get_password(self, service, username):
        return self.items.get((service, username))

    def set_password(self, service, username, password):
        self.items[(service, username)] = password

    def delete_password(self, service, username):
        del self.items[(service, username)]


@pytest.mark.parametrize("system, module_name, class_name, store", [
    ("Windows", "Windows", "WinVaultKeyring", "Windows Credential Manager"),
    ("Linux", "SecretService", "Keyring", "Secret Service")])
def test_keychain_forced_backend_per_system(monkeypatch, system, module_name, class_name, store):
    """Su Windows e Linux il 31 crea **solo** il backend del sistema (simulato in memoria), mai la scelta di keyring."""
    import importlib

    import keyring

    from astrotwo.ai import keychain_keys as kk

    backend_module = importlib.import_module(f"keyring.backends.{module_name}")

    class Fake(_MemoryBackend):
        items = {}

    monkeypatch.setattr(backend_module, class_name, Fake)
    monkeypatch.setattr(kk.platform, "system", lambda: system)
    monkeypatch.setattr(keyring, "get_keyring", lambda: pytest.fail("scelta automatica di keyring usata"))
    store_ = kk.KeychainStore()
    assert isinstance(store_._backend, Fake)
    store_.store_key("p", "  sk-finta-1  ")
    assert Fake.items == {(kk.SERVICE_NAME, "p"): "sk-finta-1"} and store_.get_key("p").reveal() == "sk-finta-1"
    assert store_.delete_key("p") == "deleted" and Fake.items == {}
    assert kk.store_name(system) == store and kk.store_name("Darwin") == "macOS Keychain"


def test_keychain_unavailable_without_system_store(monkeypatch):
    """Archivio del sistema assente (Linux senza Secret Service): ``KEYCHAIN_UNAVAILABLE``, nessun ripiego."""
    from keyring.backends import SecretService

    from astrotwo.ai import keychain_keys as kk

    class Unavailable(type):
        """Classe del backend il cui ``priority`` solleva, come ``SecretService.Keyring`` senza il servizio."""

        @property
        def priority(cls):
            raise RuntimeError("The Secret Service daemon is neither running nor activatable through D-Bus")

    monkeypatch.setattr(kk.platform, "system", lambda: "Linux")
    monkeypatch.setattr(SecretService, "Keyring", Unavailable("Keyring", (), {}))
    with pytest.raises(kk.KeychainError) as err:
        kk.KeychainStore()
    assert err.value.code == "KEYCHAIN_UNAVAILABLE"
    assert err.value.params == {"reason": "store_unavailable", "store": "Secret Service",
                                "detail": "The Secret Service daemon is neither running nor activatable through D-Bus"}
    monkeypatch.setattr(kk.platform, "system", lambda: "FreeBSD")
    with pytest.raises(kk.KeychainError) as err:
        kk.KeychainStore()
    assert err.value.params == {"reason": "unsupported_system", "system": "FreeBSD"}


# --- cartelle dei dati (D65-2, sprint W2) ---------------------------------------------------------------------------


def test_folders_per_system(monkeypatch, tmp_path):
    """macOS invariato; Windows ``%LOCALAPPDATA%``; Linux XDG (variabili assolute, altrimenti i default)."""
    from astrotwo.core.cache import default_cache_root, default_data_root

    home = Path.home()
    assert default_cache_root("Darwin") == home / "Library" / "Caches" / "AstroTwo"
    assert default_data_root("Darwin") == home / "Library" / "Application Support" / "AstroTwo"
    local = tmp_path / "AppData" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    assert default_cache_root("Windows") == local / "AstroTwo" / "Cache"
    assert default_data_root("Windows") == local / "AstroTwo"
    monkeypatch.delenv("LOCALAPPDATA")
    assert default_cache_root("Windows") == home / "AppData" / "Local" / "AstroTwo" / "Cache"
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert default_cache_root("Linux") == home / ".cache" / "astrotwo"
    assert default_data_root("Linux") == home / ".local" / "share" / "astrotwo"
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xc"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xd"))
    assert default_cache_root("Linux") == tmp_path / "xc" / "astrotwo"
    assert default_data_root("Linux") == tmp_path / "xd" / "astrotwo"
    monkeypatch.setenv("XDG_CACHE_HOME", "relativa/cache")  # la specifica XDG vuole percorsi assoluti
    assert default_cache_root("Linux") == home / ".cache" / "astrotwo"


def test_sed_and_samp_folders_follow_the_data_root():
    """Punti SED (25) e VOTable ricevuti via SAMP sotto la cartella dei dati del sistema; nessuna ``Library`` fuori
    da macOS."""
    from astrotwo.analysis.profile_export import default_sed_folder
    from astrotwo.core.cache import default_cache_root, default_data_root
    from astrotwo.ui.samp_link import default_received_dir

    assert default_sed_folder() == default_data_root() / "Profiles"
    assert default_received_dir() == default_data_root() / "SAMP" / "received"
    if sys.platform != "darwin":
        for folder in (default_cache_root(), default_data_root()):
            assert "Library" not in folder.relative_to(Path.home()).parts


# --- scorciatoie (D65-9, sprint W2) ---------------------------------------------------------------------------------


def test_shortcuts_per_system(qapp):  # StandardKey vuole la QGuiApplication
    from PySide6.QtGui import QKeySequence

    from astrotwo.ui.main_window import platform_shortcuts

    mac = {k: v.toString(QKeySequence.SequenceFormat.PortableText) for k, v in platform_shortcuts("darwin").items()}
    assert mac["fullscreen"] == "Meta+Ctrl+F" and mac["night"] == "Meta+Ctrl+N" and mac["assistant"] == "Meta+Ctrl+A"
    assert platform_shortcuts("darwin")["settings"] == QKeySequence(QKeySequence.StandardKey.Preferences)
    for name in ("win32", "linux"):
        other = {k: v.toString(QKeySequence.SequenceFormat.PortableText)
                 for k, v in platform_shortcuts(name).items()}
        assert other == {"fullscreen": "F11", "night": "Ctrl+Shift+N", "assistant": "Ctrl+Shift+A",
                         "settings": "Ctrl+,"}
        assert not any("Meta" in text for text in other.values())  # mai il tasto Windows/Super


# --- OpenGL di ripiego (D65-8, sprint W2) ---------------------------------------------------------------------------


def test_opengl_choice_and_software_renderers():
    from astrotwo.ui.sky_renderer_gl import is_software_renderer, opengl_choice

    assert opengl_choice("Darwin", "software", "software") == "native"  # macOS invariato
    for system in ("Windows", "Linux"):
        assert opengl_choice(system, None, None) == "native"
        assert opengl_choice(system, None, "software") == "software"
        assert opengl_choice(system, None, "software_failed") == "native"
        assert opengl_choice(system, " Software ", None) == "software"
        assert opengl_choice(system, "native", "software") == "native"
        assert opengl_choice(system, "altro", None) == "native"
    for name in ("llvmpipe (LLVM 15.0.7, 256 bits)", "Mesa softpipe", "GDI Generic",
                 "Microsoft Basic Render Driver"):
        assert is_software_renderer(name)
    for name in ("Apple M2", "NVIDIA GeForce RTX 3060/PCIe/SSE2", "AMD Radeon", "", None):
        assert not is_software_renderer(name)


def test_apply_software_opengl(monkeypatch):
    from PySide6.QtCore import QCoreApplication, Qt

    from astrotwo.ui import sky_renderer_gl as gl

    calls = []
    monkeypatch.setattr(QCoreApplication, "setAttribute", lambda *args: calls.append(args))
    monkeypatch.delenv("LIBGL_ALWAYS_SOFTWARE", raising=False)
    gl.apply_software_opengl("Darwin")
    assert calls == [] and "LIBGL_ALWAYS_SOFTWARE" not in os.environ
    gl.apply_software_opengl("Linux")
    assert os.environ["LIBGL_ALWAYS_SOFTWARE"] == "1" and calls == []
    monkeypatch.delenv("LIBGL_ALWAYS_SOFTWARE")
    gl.apply_software_opengl("Windows")
    assert calls == [(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)]
    assert "LIBGL_ALWAYS_SOFTWARE" not in os.environ


def test_configure_opengl_reads_nothing_on_macos(monkeypatch):
    from astrotwo.ui import main_window as mw

    monkeypatch.setattr(mw, "QSettings", lambda *a: pytest.fail("QSettings letto su macOS"))
    assert mw.configure_opengl("Darwin") == "native"


def test_configure_opengl_env_on_linux(monkeypatch):
    from astrotwo.ui import main_window as mw

    class Settings:
        def value(self, key):
            return None

    monkeypatch.setattr(mw, "QSettings", Settings)
    monkeypatch.delenv("LIBGL_ALWAYS_SOFTWARE", raising=False)
    monkeypatch.delenv("ASTROTWO_OPENGL", raising=False)
    assert mw.configure_opengl("Linux") == "native" and "LIBGL_ALWAYS_SOFTWARE" not in os.environ
    monkeypatch.setenv("ASTROTWO_OPENGL", "software")
    assert mw.configure_opengl("Linux") == "software" and os.environ["LIBGL_ALWAYS_SOFTWARE"] == "1"
