"""Configurazione comune dei test.

Ogni test gira con una cartella home temporanea: così nessun test può
scrivere nella vera cache ``~/Library/Caches/AstroTwo/`` (04-cache.md §12).
"""

import pytest


@pytest.fixture(autouse=True)
def _temporary_home(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    return home
