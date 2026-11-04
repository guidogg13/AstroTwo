# Licenze del Python incluso in AstroTwo.app

Testi copiati senza modifiche dalla cartella `python/licenses/` dell'archivio ufficiale di python-build-standalone
`cpython-3.12.16+20261026-aarch64-apple-darwin-pgo+lto-full.tar.zst`
(https://github.com/astral-sh/python-build-standalone/releases/tag/20261026), SHA-256
`016758f4881e5f71d63eddfbcdd53f25c5a9152435a863e4dc0770758eae32c3`, uguale a quella del file `SHA256SUMS` del
rilascio; letti il 2026-11-04 (D60-5; i testi sono identici a quelli della release 20261003) (`mdfiles/60-distribuzione-dmg.md` §3.11, V-a).

Il Python dell'app è l'archivio `install_only_stripped` dello stesso rilascio (SHA-256
`353d5f1b4fd2715e7053f12f068435d5bbad16b91e057006b5d01e0925709a7e`), installato da `uv python install 3.12.16`.

Componenti compilate staticamente in `libpython3.12.dylib` secondo `PYTHON.json` del rilascio, e quindi incluse
nell'app: CPython (PSF), OpenSSL 3 (`_ssl`, `_hashlib`), SQLite (`_sqlite3`), libffi (`_ctypes`), XZ/liblzma
(`_lzma`), bzip2 (`_bz2`), mpdecimal (`_decimal`), expat (`pyexpat`), libuuid (`_uuid`). zlib, libedit e ncurses
vengono da macOS (`/usr/lib`) e non sono incluse; Tcl/Tk (`_tkinter`) è escluso dall'app.
