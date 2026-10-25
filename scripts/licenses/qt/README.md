# Avvisi delle componenti di terze parti di Qt incluse in AstroTwo.app

`QT_THIRD_PARTY_NOTICES.txt` è ricavato il 2026-10-25 (`mdfiles/60-distribuzione-dmg.md` §3.7, §3.11 V-b) dai
sorgenti ufficiali di Qt 6.12.0, la versione delle librerie di PySide6 6.12.0 incluse nell'app:

- `https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qtbase-everywhere-src-6.12.0.tar.xz`,
  SHA-256 `a951bd163c7b80fc6b8c88d7668fb56abf91c152373e13c10666763238131307` (MD5 uguale a `md5sums.txt` del sito);
- `https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qtsvg-everywhere-src-6.12.0.tar.xz`,
  SHA-256 `e4ab39534ec97987b1b9b60ef7f4d3253d5912a69f8c713a01753174a4029331` (MD5 uguale a `md5sums.txt`).

Per ogni file `qt_attribution.json` di `qtbase`: nome, versione, uso in Qt, licenza, copyright e testo integrale
(il `LicenseFile` indicato, altrimenti `LICENSES/<LicenseId>.txt`). Criterio prudente: tutte le componenti dei
moduli inclusi (`QtCore`, `QtGui`, `QtWidgets`, `QtDBus`, `QtOpenGL`, `QtOpenGLWidgets`, plugin `cocoa`) e di
`src/3rdparty`, escluse solo quelle di altre piattaforme o di moduli non inclusi: `cmake/`, `D3D12MemoryAllocator`,
`android`, `gradle`, `wasm`, `wayland`, `wintab`, `xcb`, `libpsl` (QtNetwork), `sqlite` (QtSql), `zlib` (QtCore usa
la zlib di sistema, `otool -L`), `testinternal`, `testlib`, `tests/`, `util/`. L'elenco può quindi comprendere
componenti non compilate nella build di macOS. `qtsvg` non dichiara `qt_attribution.json`: si riporta il suo testo
`LICENSES/HPND-sell-variant.txt`. La licenza di Qt stesso (LGPL-3.0) è nella voce di `pyside6-essentials`.
