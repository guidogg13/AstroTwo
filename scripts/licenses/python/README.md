# Licenze del Python incluso in AstroTwo.app

Testi copiati senza modifiche dalla cartella `python/licenses/` dell'archivio ufficiale di python-build-standalone
`cpython-3.12.15+20261003-aarch64-apple-darwin-pgo+lto-full.tar.zst`
(https://github.com/astral-sh/python-build-standalone/releases/tag/20261003), SHA-256
`a23a0baff73a5f10c820841cc1889a5b7fc12048fe8c0622f6a481ab82ea367b`, uguale a quella del file `SHA256SUMS` del
rilascio; letti il 2026-10-25 (`mdfiles/60-distribuzione-dmg.md` §3.11, V-a).

Il Python dell'app è l'archivio `install_only_stripped` dello stesso rilascio (SHA-256
`ad8d0c637c0a36b967b310e2c07254f4d2ca8cabaa7699e55ed6290aceb481a2`), installato da `uv python install 3.12.15`.

Componenti compilate staticamente in `libpython3.12.dylib` secondo `PYTHON.json` del rilascio, e quindi incluse
nell'app: CPython (PSF), OpenSSL 3 (`_ssl`, `_hashlib`), SQLite (`_sqlite3`), libffi (`_ctypes`), XZ/liblzma
(`_lzma`), bzip2 (`_bz2`), mpdecimal (`_decimal`), expat (`pyexpat`), libuuid (`_uuid`). zlib, libedit e ncurses
vengono da macOS (`/usr/lib`) e non sono incluse; Tcl/Tk (`_tkinter`) è escluso dall'app.
