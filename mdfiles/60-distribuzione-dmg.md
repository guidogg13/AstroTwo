# 60-distribuzione-dmg.md — Costruzione e consegna di AstroTwo.app e del `.dmg`

**Stato:** approvato

> Parte A (sprint **60a**, questo file completo): costruzione di `dist/AstroTwo.app` per macOS su Apple Silicon.
> Parte B (sprint **60b**): immagine disco `.dmg`, §3.10, **da completare** prima del suo codice.
> Decisioni del proprietario del 2026-10-25 registrate qui: **A2** (PyInstaller), **A6** (firma ad hoc, nessuna
> notarizzazione per la prima beta; Developer ID rinviata), Python di uv, forma della versione, icona fornita dal
> proprietario.

## 2. Scopo

Produrre con un solo comando ripetibile, partendo da `uv.lock`, un'app macOS `AstroTwo.app` autonoma (Python e tutte
le librerie dentro, l'utente non installa niente) che rispetta le licenze di AstroTwo e delle sue dipendenze.

## 3. Cosa fa

### 3.1 Perimetro

- **Piattaforma:** macOS su Apple Silicon (`arm64`) soltanto. Nessuna app `x86_64` né `universal2`.
- **macOS minimo:** non scelto a mano. Lo script lo **legge** dai binari inclusi: è il massimo dei `minos` di
  `LC_BUILD_VERSION`. Lo scrive in `LSMinimumSystemVersion`, nel rapporto della costruzione e nella finestra Licenze.
  Con le versioni di `uv.lock` del 2026-10-25 vale **26.0** (misurato sull'app costruita il 2026-10-25): le
  librerie di Qt chiedono 14.4 e numpy e scipy 14.0, ma i moduli di collegamento di PySide6 e shiboken6 6.12.0
  (`PySide6/*.abi3.so`, `libpyside6`, `libshiboken6`, `shiboken6/Shiboken.abi3.so`) hanno `minos 26.0` e
  `sdk 26.0` già nella ruota ufficiale, che pure è etichettata `macosx_14_0_universal2`. Si decide con D60-4; se
  una dipendenza cambia, il rapporto lo dice.
- **Firma (A6, decisione del proprietario del 2026-10-25):** solo **ad hoc** (`codesign --sign -`), necessaria perché
  macOS su Apple Silicon non avvia codice non firmato. **Nessuna notarizzazione.** Chi scarica l'app dovrà usare
  "Apri comunque" (Impostazioni di Sistema → Privacy e sicurezza): il sito lo spiegherà (60b). La firma con
  certificato **Developer ID** e la notarizzazione sono **rinviate** (registrate in §13 e in `decisioni-aperte.md`).
- **Strumento (A2, decisione del proprietario del 2026-10-25):** **PyInstaller** in modalità cartella (`onedir`,
  mai file unico), che produce il pacchetto `.app` (`BUNDLE`). Motivi: usa lo stesso ambiente bloccato da `uv.lock`
  su cui girano i test, si ricostruisce senza rete, lascia le librerie Qt come `.framework` separati. Il confronto
  con Briefcase è in §8.

### 3.2 Identità dell'app

| Chiave | Valore | Origine |
|---|---|---|
| Nome (`CFBundleName`, `CFBundleDisplayName`) | `AstroTwo` | proprietario |
| `CFBundleIdentifier` | `dev.pages.astrotwo` | `01` §6, decisione del 2026-10-16 |
| `CFBundleShortVersionString` | `0.1.0` (parte `MAJOR.MINOR.PATCH` della versione) | proprietario, 2026-10-25 |
| `CFBundleVersion` | `1`: numero di build intero, cresce di 1 a ogni app consegnata | proprietario, 2026-10-25 |
| `CFBundleExecutable` | `AstroTwo` | — |
| `LSMinimumSystemVersion` | letto dai binari (§3.1) | — |
| `LSArchitecturePriority` | `arm64` | — |
| `NSHighResolutionCapable` | `true` | — |
| `NSHumanReadableCopyright` | `Copyright © 2026 Guido Ratti. GPL-3.0-or-later.` | `01` §6.1 |
| `CFBundleIconFile` | `AstroTwo.icns`, solo se il file sorgente dell'icona c'è (§3.6) | proprietario |

**Versione (decisione del proprietario del 2026-10-25).** Una sola versione, scritta in due forme che si
corrispondono:

- `pyproject.toml`: `version = "0.1.0b1"` (forma normale PEP 440, quella dei metadati del pacchetto);
- `astrotwo.__version__ = "0.1.0-beta.1"` (SemVer, DC4 di `02-convenzioni.md`): è la versione **mostrata** (About,
  Licenze) e **scritta** nei file (sessioni, FITS, VOTable, PNG, HiPS);
- un test controlla che le due siano la stessa versione (`packaging.version.Version` di entrambe è uguale).

Il numero di build (`CFBundleVersion`) sta in `pyproject.toml`, tabella `[tool.astrotwo.bundle]`, chiave
`build = 1`, e si aumenta a mano quando si consegna una nuova app.

### 3.3 Ambiente di costruzione

Lo script `scripts/build_app.py` (eseguito con `uv run python scripts/build_app.py`) fa, nell'ordine, e si ferma al
primo errore con un messaggio che dice il passo e il motivo:

1. **Controlli iniziali.** macOS su `arm64`; `uv`, `codesign`, `iconutil`, `otool`, `ditto` presenti (strumenti del
   sistema e di Xcode Command Line Tools). Stato di git: il commit corrente si registra. Se ci sono modifiche non
   salvate, la costruzione si ferma, a meno di `--allow-dirty`, che il rapporto e `BUILD_INFO.json` dichiarano.
2. **Python.** `uv python install 3.12.15`, versione fissata in una costante dello script (`PYTHON_VERSION`): è
   CPython di **python-build-standalone** gestito da uv (rilascio `20261003`, decisione del proprietario del
   2026-10-25: **non** il Python di Homebrew del `.venv`, costruito per macOS 26 e legato alle librerie di
   Homebrew). Un aggiornamento si fa solo su richiesta esplicita, come per `uv.lock` (`01` §6).
3. **Ambiente separato** `build/env/`, creato da zero a ogni costruzione con
   `uv sync --frozen --python <Python del passo 2> --group dev --group build` e `UV_PROJECT_ENVIRONMENT=build/env`.
   `--frozen`: si usa `uv.lock` così com'è; se non corrisponde a `pyproject.toml` la costruzione si ferma. Il
   `.venv` di sviluppo non si tocca.
4. **Test.** I test di default (stessi marcatori di `pyproject.toml`: niente rete, Portachiavi, `perf`, `gl`) girano
   **in `build/env/`**, perché il Python dell'app non è quello del `.venv`. Un fallimento ferma la costruzione.
   `--skip-tests` salta questo passo solo per prove ripetute dello script: `BUILD_INFO.json` lo dichiara e il
   rapporto lo scrive in testa.
5. **Licenze.** `scripts/third_party_licenses.py --check` eseguito in `build/env/`: se `THIRD_PARTY_LICENSES` non
   corrisponde all'ambiente che finisce nell'app, la costruzione si ferma.
6. **Icona.** Se esiste `assets/icon/AstroNew.svg` (§3.6), si genera `build/AstroTwo.icns` (immagini PNG disegnate
   con `QSvgRenderer` di Qt in `build/env/`, poi `iconutil`); se manca, si costruisce senza icona e il rapporto lo
   scrive.
7. **PyInstaller** dall'ambiente `build/env/`, con la specifica generata dallo script in `build/AstroTwo.spec`
   (nessun file `.spec` scritto a mano nel repository): contenuto in §3.4, esclusioni in §3.5. Uscita in
   `dist/AstroTwo.app`, che prima si cancella se esiste. La cancellazione tocca solo `dist/AstroTwo.app` e
   `build/`, cartelle ignorate da git.
8. **Qt dalla ruota (D60-3, decisione del proprietario del 2026-10-25):** ogni binario di Qt dell'app (i
   `.framework` e i plugin tenuti, sotto `Contents/Frameworks/PySide6/Qt/`) si sostituisce con la copia esatta del
   file della ruota di PySide6 in `build/env/` (universale `x86_64` + `arm64`, intestazioni originali), perché
   PyInstaller toglie la parte `x86_64` e riscrive le intestazioni Mach-O (§3.7 punto 4). Poi:
   **firma ad hoc** di tutto il pacchetto (`codesign --force --deep --sign -`), poi
   `codesign --verify --deep --strict`.
9. **Controlli dell'app costruita** (§3.8). Un controllo fallito ferma la costruzione e lascia l'app per l'esame,
   ma con il nome `dist/AstroTwo.app` sostituito da `dist/AstroTwo-FAILED.app`.
10. **Rapporto** sul terminale e in `dist/build-report.json`: versione, build, commit, impronta SHA-256 di
    `uv.lock`, Python, PyInstaller, macOS minimo, dimensione dell'app (byte e MB, `du -sk`), dimensione delle parti
    più grandi (Qt, scipy, astropy…), durata di ogni passo, esito dei controlli, tempo di avvio (§3.8 punto 7).

### 3.4 Contenuto dell'app

```
AstroTwo.app/Contents/
├── Info.plist                 §3.2
├── MacOS/AstroTwo             bootloader di PyInstaller
├── Frameworks/                Python, estensioni compilate, librerie (sys._MEIPASS)
│   └── PySide6/Qt/lib/*.framework   librerie Qt separate, non modificate (§3.7)
└── Resources/
    ├── AstroTwo.icns          solo con l'icona (§3.6)
    ├── licenses/              §3.7
    │   ├── LICENSE  NOTICE  THIRD_PARTY_LICENSES  SOURCES.txt
    └── BUILD_INFO.json        versione, build, commit, uv.lock, Python, PyInstaller, data, test eseguiti sì/no
```

(Disposizione di PyInstaller 6 per un `.app`: i dati stanno in `Resources/` e sono raggiungibili anche da
`Frameworks/` con collegamenti simbolici; **da verificare** sull'app costruita, punto V3 di §3.11.)

Codice e dati di AstroTwo inclusi:

- il pacchetto `astrotwo` (codice compilato da PyInstaller nel suo archivio; nessun `.py` di `tests/`);
- `astrotwo/ui/i18n/astrotwo_it.qm` (non il `.ts`), `astrotwo/ui/icons/*.svg` con il loro `LICENSE` (Lucide),
  `astrotwo/core/data/naif/pck00011.tpc` con il suo `README.md`, agli stessi percorsi relativi al pacchetto: il
  codice che li trova con `Path(__file__)` (`main_window.py`, `planetary_data.py`) funziona senza modifiche;
- dalle librerie, i file di dati che leggono a runtime: dati di astropy e `astropy-iers-data`, file di
  `astroquery` e `pyvo`, `certifi/cacert.pem`, `libcspice.dylib` di `spiceypy`, dati di `pds4_tools`, i metadati
  (`*.dist-info`) dei pacchetti che leggono la propria versione con `importlib.metadata`. Si usano i "hook" di
  `pyinstaller-hooks-contrib`; quelli che mancano li aggiunge lo script (`collect_data_files`,
  `copy_metadata`), e il punto 4 di §3.8 controlla che il codice li trovi davvero;
- da Qt: i moduli usati dal codice (`QtCore`, `QtGui`, `QtWidgets`, `QtOpenGL`, `QtOpenGLWidgets`, `QtSvg`) con
  le loro dipendenze dirette, i plugin `platforms/libqcocoa`, `styles/libqmacstyle`, `imageformats/libqsvg`,
  `iconengines/libqsvgicon` (e gli altri `imageformats` che il hook di PySide6 include di default) e la
  traduzione `translations/qtbase_it.qm` (usata da `load_translations` del `40`).

### 3.5 Esclusioni (per la dimensione)

Si escludono solo cose che il codice di AstroTwo non importa. L'elenco sta in una costante dello script, ogni voce
con il motivo:

- moduli Qt non usati: `QtQml`, `QtQuick*`, `QtDesigner*`, `QtHelp`, `QtPdf*`, `QtLabs*`, `QtLottie*`,
  `QtNetwork` (la rete passa da `requests`/`httpx2`), `QtDBus` (se non è una dipendenza dei moduli usati: **da
  verificare** con `otool -L`), la cartella `qml/` e le traduzioni di Qt diverse da `qtbase_it.qm`;
- `tkinter` e le librerie Tcl/Tk;
- i test delle librerie (`astropy/tests` e simili) **solo se** nessun modulo usato li importa (**da verificare**
  per astropy, che importa parti di `astropy.tests` in alcuni moduli);
- i backend di matplotlib diversi da quelli che il codice usa (**da verificare** prima del codice: quale backend usa
  AstroTwo).

Un'esclusione sbagliata la scopre il punto 4 di §3.8 (importazione di tutti i moduli di `astrotwo`), oltre ai test
dell'app costruita.

### 3.6 Icona

L'icona la fornisce il proprietario (decisione del 2026-10-25): file **`assets/icon/AstroNew.svg`** (SVG
1024×1024, consegnato il 2026-10-25; contiene solo `circle`, `rect`, `path`, `g` e `linearGradient`, nessuna
immagine esterna, più un manifesto C2PA nei metadati, che non si disegna). Lo script disegna con `QSvgRenderer` di
Qt (stesso PySide6 dell'app) le dimensioni richieste da `iconutil` (`icon_16x16` … `icon_512x512@2x`, cioè da 16
a 1024 pixel) in `build/AstroTwo.iconset/`, poi `iconutil -c icns`. Il file SVG non si modifica e non entra
nell'app (solo l'`.icns`). L'icona è un disegno originale del proprietario, con licenza **GPL-3.0-or-later** come il resto di AstroTwo
(dichiarazione del proprietario del 2026-10-25), scritta in `assets/icon/README.md`. Senza il file l'app si
costruisce con l'icona generica di macOS e il rapporto lo dice. Nessuna immagine presa da altri (regola d'oro 8).

### 3.7 Licenze dentro l'app

Requisiti di `01` §6.1, punti 1–5:

1. **`Contents/Resources/licenses/`** contiene, copiati senza modifiche dalla radice del progetto, `LICENSE`
   (GPL-3.0), `NOTICE` e `THIRD_PARTY_LICENSES`, più `SOURCES.txt`, generato dallo script.
2. **`THIRD_PARTY_LICENSES` completato** (generatore `scripts/third_party_licenses.py`, decisione del 2026-10-13):
   - **Python (PSF):** il `LICENSE` di CPython 3.12 (storia e licenza PSF) e, a parte, gli avvisi delle librerie che
     python-build-standalone include nel Python dell'app (per esempio OpenSSL, libffi, SQLite, XZ, bzip2, zlib,
     mpdecimal, expat; l'elenco esatto viene dal file `PYTHON.json` di quel rilascio: **da verificare prima del
     codice**). I testi sono copiati in `scripts/licenses/python/` con fonte, URL e SHA-256, come già per PySide6;
   - **Qt:** avvisi delle componenti di terze parti incluse nei moduli Qt dell'app (elenco "Licenses Used in Qt"),
     presi dai file `qt_attribution.json` e `LICENSES/` dei sorgenti ufficiali `qtbase` e `qtsvg` 6.12.0, con URL e
     SHA-256 degli archivi (**da verificare prima del codice**), copiati in `scripts/licenses/qt/`;
   - **PyInstaller:** il bootloader incluso nell'app (GPL-2.0-or-later con l'eccezione che permette di distribuire
     programmi costruiti con PyInstaller), con il suo testo di licenza. Lo strumento PyInstaller **non** si
     distribuisce: va con gli strumenti di sviluppo in fondo al file;
   - il generatore legge i pacchetti installati: con `build/env/` (passo 5 di §3.3) il file corrisponde a ciò che
     sta nell'app.
3. **`SOURCES.txt`** (inglese, come i testi di licenza) dice:
   - versione, build e commit di AstroTwo e il sorgente corrispondente (GPL-3.0 §6, D60-1): repository
     `https://github.com/guidogg13/AstroTwo`, tag `v<versione SemVer>` e commit, e l'archivio del sorgente accanto
     al `.dmg` (60b);
   - il sorgente esatto di **PySide6 e shiboken6 6.12.0** (`https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/pyside-setup-everywhere-src-6.12.0.zip`,
     SHA-256 già registrata in `scripts/third_party_licenses.py`) e di **Qt 6.12.0**
     (`https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/`, archivi `qtbase` e `qtsvg` con SHA-256);
     la versione di Qt si legge al momento della costruzione (`QLibraryInfo.version()`), e se non è quella dei link
     la costruzione si ferma;
   - **come sostituire le librerie Qt** (LGPL-3): sono i file `Contents/Frameworks/PySide6/Qt/lib/*.framework`;
     si sostituiscono con una versione compatibile (stessa versione minore di Qt, stessa ABI di PySide6) e si firma
     di nuovo l'app ad hoc (`codesign --force --deep --sign - AstroTwo.app`);
   - che le condizioni d'uso di AstroTwo **non vietano** l'analisi, il reverse engineering né la modifica (GPL-3.0;
     `01` §6.1 punto 4): AstroTwo non ha altre condizioni d'uso oltre alla GPL-3.0.
4. **Librerie Qt non modificate e separate** (`01` §6.1 punto 2): restano `.framework` distinti, mai uniti in un
   unico eseguibile né ridotti (`strip` disattivato per Qt, nessun `upx`). La firma ad hoc riscrive la firma
   (obbligatoria su Apple Silicon) e PyInstaller può riscrivere i percorsi delle librerie nelle intestazioni
   Mach-O. **Verificato il 2026-10-25 (V-e):** PyInstaller 6.22.3 toglie la parte `x86_64` dei binari universali
   di Qt e riscrive identificativo (`LC_ID_DYLIB`) e percorsi di ricerca (`LC_RPATH`); il codice `arm64` resta
   identico (differenze solo nei primi ~5 KB, l'intestazione). Per questo lo script rimette i file della ruota
   (§3.3 punto 8, D60-3). Il controllo V5 di §3.8 confronta ogni binario Qt dell'app con quello della ruota, **tolta
   la firma** da entrambe le copie (`codesign --remove-signature`) e ignorato il solo campo `vmsize` del segmento
   `__LINKEDIT`: la firma ad hoc dell'app è più grande di quella del linker della ruota e lo ingrandisce, e
   `--remove-signature` non lo riporta indietro (verificato il 2026-10-25: è l'unica differenza, un campo per
   parte del file universale). Tutto il resto del file deve essere identico; che si carichino lo provano V4 e V7.
   Non si può evitare di rifirmare i binari di Qt: nella ruota i `.framework` come pacchetti non sono firmati
   (lo è solo il binario, dal linker) e macOS chiede che ogni pacchetto annidato nell'app sia firmato.

### 3.8 Controlli sull'app costruita (passo 9 di §3.3)

Ogni controllo ha un nome (V1…V9) che compare nel rapporto con l'esito.

- **V1 — Firma:** `codesign --verify --deep --strict` riuscito; firma ad hoc (`Signature=adhoc`).
- **V2 — Nessun riferimento esterno:** tutti i Mach-O dell'app (`otool -L` e `LC_RPATH`) fanno riferimento solo
  a `@rpath`, `@loader_path`, `@executable_path`, `/System/Library/` e `/usr/lib/`; nessun percorso contiene
  `/opt/homebrew`, `/usr/local`, il `.venv`, `build/env` o la cartella del progetto.
- **V3 — Disposizione:** i file di §3.4 esistono ai loro percorsi; `Info.plist` ha le chiavi di §3.2;
  `LSMinimumSystemVersion` coincide con il massimo dei `minos` dei binari.
- **V4 — Autocontrollo** dell'app (`AstroTwo --self-check`, §7) eseguito con un ambiente vuoto
  (`env -i HOME=<cartella temporanea> PATH=/usr/bin:/bin`, cartella di lavoro `/`), senza `uv` né `.venv` nel
  `PATH`: deve uscire con 0 e un rapporto JSON in cui ogni voce è `ok`. **HOME temporanea anche per V7**
  (2026-10-25): con la HOME vera l'app costruita legge all'avvio la chiave del profilo IA e macOS chiede il permesso
  del Portachiavi (firma ad hoc nuova, §10), cosa vietata nei controlli automatici; con una HOME temporanea macOS
  non trova il Portachiavi di login, e impostazioni e cache sono quelle di un utente nuovo.
- **V5 — Qt non modificato:** §3.7 punto 4 (file della ruota, tolta la firma e ignorato `vmsize` di `__LINKEDIT`).
- **V6 — Nessuna scrittura nell'app:** impronta (percorso, dimensione, SHA-256, data) di ogni file dell'app prima e
  dopo V4 e V7: devono essere uguali. Nessun `__pycache__` né `.pyc` creato.
- **V7 — Avvio reale:** l'app si lancia (`open -n -W --stdout <file> dist/AstroTwo.app --args
  --quit-after-first-view`), mostra la finestra, disegna la prima vista del cielo (segnale `first_shown` del `41`),
  scrive la riga `astrotwo: first_view` ed esce da sola. Si misura con un orologio esterno il tempo dal lancio a
  quella riga (prova che la prima vista c'è stata, non solo che l'app è uscita), una volta "a freddo" (prima
  esecuzione dopo la costruzione) e una "a caldo". La misura **si riporta** e non ferma la costruzione (obiettivo P5 del `41`, D41-8). Se non c'è uno
  schermo (sessione senza interfaccia grafica), V7 è "non eseguito" con il motivo.
- **V8 — Licenze:** i file di `Resources/licenses/` sono uguali byte per byte a quelli del progetto (per
  `SOURCES.txt`: a quello generato); `THIRD_PARTY_LICENSES` contiene le sezioni Python, Qt e PyInstaller.
- **V9 — Dimensione:** riportata, con le dieci cartelle più grandi; nessun limite bloccante (si riporta e basta).

### 3.9 Finestra "Licenses" / "Licenze" (requisito 1 di `01` §6.1; cambia il `40`)

- Nuova voce **Licenses…** / **Licenze…** nel menu dell'app, subito sotto **About AstroTwo** / **Informazioni su
  AstroTwo** (ruolo `ApplicationSpecificRole` di Qt; in un menu Help dove l'About resta nel menu Help, cioè fuori
  da macOS, la voce lo segue lì). Nella finestra About c'è anche un pulsante **Licenses…**.
- La finestra (non modale, una sola aperta) ha schede, ciascuna con testo di sola lettura e un campo di ricerca:
  1. **AstroTwo:** nome, versione SemVer, build, commit (da `BUILD_INFO.json` se c'è), copyright, licenza
     GPL-3.0-or-later; poi `NOTICE` e il testo di `LICENSE`;
  2. **Third-party** / **Terze parti:** `THIRD_PARTY_LICENSES` (comprende Python, Qt, PyInstaller);
  3. **Sources** / **Sorgenti:** `SOURCES.txt` (sorgenti di AstroTwo, PySide6 e Qt, sostituzione di Qt);
  4. **Data credits** / **Crediti dei dati:** i testi di riconoscimento della tabella di `01` §6.1, nella lingua
     originale (inglese), con la fonte di ciascuno; quelli segnati "da verificare" lì compaiono con la scritta
     "acknowledgement text not yet verified" / "testo di riconoscimento non ancora verificato".
- I file si trovano con una sola funzione (`license_files` di §7): nell'app costruita in
  `Contents/Resources/licenses/`; nello sviluppo nella radice del progetto (e `SOURCES.txt` generato al volo nella
  stessa forma). Un file mancante non è un errore che blocca: la scheda mostra il messaggio `LICENSE_FILE_MISSING`
  con il nome del file e il percorso cercato.
- Aprire la finestra non è un comando del `05`: è una lettura che non cambia lo stato (come l'About oggi). Le
  stringhe dell'interfaccia sono tradotte (A9); i testi di licenza no.
- La finestra About di oggi (che mostra tutto `THIRD_PARTY_LICENSES`) diventa: nome, versione, build, copyright,
  una riga di licenza, il pulsante Licenses….

### 3.10 Parte B — immagine disco `.dmg` (sprint 60b, da completare)

Da scrivere prima del codice dello sprint 60b. Punti già noti: strumento di creazione del `.dmg` (orientamento di
A2 del 2026-10-09: `dmgbuild`, **da decidere** in 60b); stessa firma ad hoc dell'app, nessuna notarizzazione (A6);
nel `.dmg` l'app e un collegamento ad Applicazioni; testo "Apri comunque" per il sito; sorgente di AstroTwo
(D60-1) decisa prima di una distribuzione pubblica; verifica del marchio "AstroTwo" (`01` §6.1 punto 7) prima della
distribuzione pubblica.

### 3.11 Verifiche da fare prima del codice

- V-a: elenco esatto delle librerie incluse nel Python di python-build-standalone `20261003` per macOS `aarch64`
  (`PYTHON.json`) e i loro testi di licenza; URL e SHA-256 dell'archivio.
- V-b: URL e SHA-256 degli archivi `qtbase` e `qtsvg` 6.12.0; elenco delle componenti di terze parti dei moduli Qt
  inclusi (da `qt_attribution.json`).
- V-c: versioni di `pyinstaller` e `pyinstaller-hooks-contrib` per il gruppo `build`: **pyinstaller 6.22.3**
  (2026-09-12) e **pyinstaller-hooks-contrib 2026.8** (2026-09-30), le più recenti con almeno due settimane al
  2026-10-25 (la 2026.9 è del 2026-10-20); licenze (GPL-2.0-or-later con eccezione del bootloader; hooks: Apache-2.0 o
  GPL-2.0, **da verificare** per i file inclusi) e impronte nel `uv.lock` uguali a quelle di PyPI.
- V-d: quali moduli Qt dipendono da `QtDBus`; quale backend di matplotlib usa AstroTwo; se astropy funziona senza
  `astropy/tests`.
- V-e: disposizione di PyInstaller 6 dentro `.app` (dati in `Resources/`, collegamenti da `Frameworks/`) e se
  PyInstaller riscrive i percorsi nelle intestazioni dei `.framework` di Qt (V5).

## 4. Cosa NON fa

- Non crea il `.dmg` (60b, §3.10) e non pubblica niente: né sito, né server, né GitHub.
- Non firma con un certificato Developer ID e non notarizza (A6, rinviata).
- Non produce app per Intel, `universal2`, Windows o Linux.
- Non cambia `uv.lock` né aggiorna dipendenze, salvo aggiungere il gruppo `build` (PyInstaller).
- Non installa niente nel sistema dell'utente e non scrive dentro l'app costruita.
- Non aggiorna da solo l'app (nessun aggiornamento automatico nella v1).
- Non tocca il Portachiavi durante la costruzione né nei test automatici; l'autocontrollo lo usa solo con
  `--self-check-keychain`, eseguito a mano (§7).
- Non modifica le librerie Qt (§3.7 punto 4) né il kernel della NAIF.
- Non inventa testi di riconoscimento: quelli "da verificare" in `01` §6.1 restano segnati così nella finestra.

## 5. Livello e dipendenze

- **Livello:** distribuzione (60–69). Non è un livello dell'app: impacchetta i livelli 1–3 e l'interfaccia.
  Funziona senza IA come l'app.
- **Dipende da:** `01-architettura.md` (§6, §6.1: identificativo, licenze, requisiti), `02-convenzioni.md` (DC4),
  `40-ui-finestra-principale.md` (menu, About, traduzioni), `41-ui-visualizzatore-cielo.md` (`first_shown`, P5),
  `31-ia-chiavi-portachiavi.md` (backend macOS, `KeychainKeys` con servizio di prova), `19-core-dati-planetari.md`
  (kernel NAIF), `04-cache.md` (cartella della cache, fuori dall'app); `uv.lock`, `THIRD_PARTY_LICENSES`.
- **Usato da:** nessuno (il 60b userà `dist/AstroTwo.app`).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `uv.lock`, `pyproject.toml` | file | TOML | versioni bloccate, gruppo `build`, `[tool.astrotwo.bundle] build` |
| in | sorgenti `src/astrotwo/` e dati | file | — | §3.4 |
| in | `LICENSE`, `NOTICE`, `THIRD_PARTY_LICENSES` | file | testo UTF-8 | copiati senza modifiche |
| in | `assets/icon/AstroNew.svg` | file, facoltativo | SVG 1024×1024 | §3.6 |
| in | opzioni dello script | riga di comando | `--allow-dirty`, `--skip-tests`, `--keep-build` | §3.3, §7 |
| out | `dist/AstroTwo.app` | pacchetto macOS | `.app` arm64, firmato ad hoc | §3.4 |
| out | `dist/build-report.json` | file | JSON UTF-8 | §3.3 punto 10; dimensioni in byte e MB, tempi in secondi |
| out | `build/` | cartella di lavoro | — | ambiente, specifica, icona; cancellata a ogni costruzione |
| out | codice di uscita dello script | intero | 0 riuscita, 1 controllo fallito, 2 prerequisito mancante | — |

## 7. Interfaccia pubblica

**Strumento di costruzione** — `scripts/build_app.py` (fuori dal pacchetto, non incluso nell'app):

- **`main`** — esegue i passi di §3.3; opzioni `--allow-dirty`, `--skip-tests`, `--keep-build` (non cancella
  `build/env` se esiste ed è stato creato dallo stesso `uv.lock` e dallo stesso Python, per prove ripetute;
  dichiarato nel rapporto); restituisce il codice di uscita di §6.
- **`spec_text`** — testo della specifica di PyInstaller generata (dati, metadati, esclusioni, `Info.plist`).
- **`keep_entry`** — filtro dei file di Qt (plugin, traduzioni, QML) di §3.4–§3.5, usato dalla specifica generata.
- **`make_iconset`** — PNG dell'iconset da un SVG con `QSvgRenderer` (§3.6).
- **`minimum_macos`** — massimo dei `minos` dei Mach-O di una cartella.
- **`check_bundle`** — controlli V1–V9 su un'app; restituisce l'elenco degli esiti (nome, `ok`/`failed`/`not_run`,
  dettaglio). Usabile anche da solo su un'app già costruita (`--check-only dist/AstroTwo.app`).

**Nel pacchetto** — `src/astrotwo/app_bundle.py` (nuovo file, corrispondenza di questo `.md` nel codice dell'app):

- **`is_bundled`** — vero se il codice gira dentro l'app costruita (PyInstaller, `sys.frozen`).
- **`license_files`** — percorsi di `LICENSE`, `NOTICE`, `THIRD_PARTY_LICENSES`, `SOURCES.txt` e di
  `BUILD_INFO.json` (quando c'è), nell'app o nel progetto (§3.9).
- **`sources_text`** — testo di `SOURCES.txt` (generato dallo script per l'app; nello sviluppo, stessa funzione).
- **`self_check(keychain=False)`** — rapporto JSON (voci con nome, `ok`/`failed` e dettaglio): Python e
  `sys.path` dentro l'app; importazione di tutti i moduli di `astrotwo` (`pkgutil.walk_packages`); file di §3.4
  presenti e leggibili; percorsi di `QLibraryInfo` dentro l'app; plugin `cocoa` e SVG caricabili; `qtbase_it.qm`
  e `astrotwo_it.qm` caricabili; `certifi.where()` dentro l'app; dati IERS di `astropy-iers-data` leggibili;
  kernel NAIF caricato dal `19`; backend macOS di `keyring` caricabile **senza** accedere al Portachiavi; cartella
  della cache (`04`) fuori dall'app. Con `keychain=True` (solo a mano): con `KeychainKeys(service=
  "dev.pages.astrotwo.selfcheck")` del `31` scrive, rilegge e cancella una chiave di prova, mai quella delle
  chiavi vere (`dev.pages.astrotwo.ai`).
- **`main`** — punto d'ingresso dell'app: `--self-check` e `--self-check-keychain` stampano il rapporto ed
  escono (0 se tutto `ok`, 1 altrimenti) senza aprire finestre; `--quit-after-first-view` avvia l'app normale ed
  esce dopo il primo `first_shown` del `41` scrivendo `astrotwo: first_view` (per V7), tramite il parametro
  `on_first_view` di `astrotwo.ui.main_window.main` (funzione chiamata con l'applicazione alla prima vista);
  senza opzioni chiama `astrotwo.ui.main_window.main`.

**Interfaccia** — `src/astrotwo/ui/licenses_dialog.py` (nuovo file, parte di §3.9 e del `40`):

- **`LicensesDialog`** — finestra delle Licenze con le quattro schede di §3.9.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| PyInstaller 6.22.3 + pyinstaller-hooks-contrib 2026.8 (gruppo `build`) | costruzione dell'`.app` (`onedir` + `BUNDLE`) | A2: stesso ambiente di `uv.lock`, ricostruzione senza rete, Qt in `.framework` separati, hook pronti per PySide6 e per le librerie scientifiche; bootloader con eccezione di licenza per distribuire |
| uv (`uv python install`, `uv sync --frozen`) | Python 3.12.15 di python-build-standalone e ambiente bloccato | A4; Python costruito per una versione di macOS più vecchia di quella minima delle ruote (da verificare con V-a), senza librerie di Homebrew |
| `codesign`, `iconutil`, `sips`, `otool`, `ditto` (macOS) | firma ad hoc, icona, controlli Mach-O, copie | strumenti di sistema, nessuna dipendenza in più |
| `packaging` | confronto delle due forme della versione | già dipendenza di sviluppo |
| Info.plist (Apple, Bundle Programming Guide) | chiavi di §3.2 | standard del sistema |
| LGPL-3.0 (§4, §6), GPL-3.0 (§6) | §3.7 | `01` §6.1 |

**Confronto con Briefcase (fatto il 2026-10-25, scelta del proprietario: PyInstaller).** Briefcase (BSD-3)
copierebbe le ruote senza modifiche in `site-packages` (Qt più facile da sostituire, nessun dato da dichiarare), ma
usa un proprio Python, installa le librerie con pip dai propri `requires` invece che da `uv.lock`, ha bisogno della
rete a ogni costruzione pulita e produce un'app più grande. PyInstaller invece chiede di dichiarare i dati, e per
questo ci sono i controlli V4 e V5.

## 9. Regole e vincoli

- **Riproducibilità:** due costruzioni dallo stesso commit, dallo stesso `uv.lock` e dallo stesso Python danno
  un'app con gli stessi file, a parte la firma, `BUILD_INFO.json` (data) e i file con data di PyInstaller.
  `BUILD_INFO.json` permette di risalire a commit, lock e strumenti.
- **Nessuna chiave API** né dato dell'utente nell'app, nel rapporto o in `build/` (regola d'oro 5): lo script non
  legge il Portachiavi, `QSettings` né la cache.
- **Nessuna scrittura nell'app** in esecuzione (V6): cache in `~/Library/Caches/AstroTwo/` (`04`), impostazioni in
  `~/Library/Preferences/` (`QSettings`), sessioni dove le salva l'utente; nessun `.pyc` scritto
  (`sys.dont_write_bytecode` impostato all'avvio dall'app costruita).
- **Le versioni nell'app sono quelle di `uv.lock`**; il Python è quello fissato in §3.3 punto 2.
- **Licenze:** §3.7; ogni nuova dipendenza o file incluso aggiorna `THIRD_PARTY_LICENSES` nello stesso commit
  (`01` §6).
- **Nessun numero scientifico** viene calcolato qui; l'autocontrollo verifica che i dati ci siano, non i loro
  valori (quelli li verificano i test dei moduli, eseguiti al passo 4 nello stesso ambiente).

## 10. Casi limite ed errori

Lo script scrive i suoi messaggi in italiano sul terminale (è uno strumento di sviluppo, fuori dal catalogo dei
messaggi dell'app); l'app costruita usa il catalogo (`40` §3.7.1).

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Mac Intel o macOS non `arm64` | lo script si ferma, uscita 2 | `BUILD_UNSUPPORTED_PLATFORM` (script) |
| `uv`, `codesign` o `iconutil` mancanti | si ferma dicendo quale strumento manca e come installarlo, uscita 2 | `BUILD_TOOL_MISSING` (script) |
| Modifiche non salvate in git | si ferma, salvo `--allow-dirty` (dichiarato in `BUILD_INFO.json`) | `BUILD_DIRTY_TREE` (script) |
| `uv.lock` non aggiornato rispetto a `pyproject.toml` | `uv sync --frozen` fallisce: si ferma | `BUILD_LOCK_MISMATCH` (script) |
| Python 3.12.15 non scaricabile (rete assente, primo uso) | si ferma; con il Python già installato da uv la costruzione non usa la rete | `BUILD_PYTHON_UNAVAILABLE` (script) |
| Un test fallisce in `build/env/` | si ferma, uscita 1 | `BUILD_TESTS_FAILED` (script) |
| `THIRD_PARTY_LICENSES` non aggiornato | si ferma, uscita 1 | `BUILD_LICENSES_OUTDATED` (script) |
| Qt di versione diversa da quella dei link di `SOURCES.txt` | si ferma, uscita 1 | `BUILD_QT_VERSION_MISMATCH` (script) |
| Icona mancante | costruisce senza icona, avviso nel rapporto | `BUILD_ICON_MISSING` (avviso) |
| Repository non ancora pubblico o tag non ancora creato (D60-1) | costruisce, avviso nel rapporto (si controlla solo che il tag esista in locale; la visibilità del repository non si controlla dalla rete) | `BUILD_SOURCE_NOT_PUBLIC` (avviso) |
| Un controllo V1–V6 o V8 fallisce | app rinominata `AstroTwo-FAILED.app`, uscita 1 | `BUILD_CHECK_FAILED` con il nome del controllo |
| V7 senza schermo | "non eseguito" con il motivo, nessun fallimento | — |
| Nell'app: file di licenza mancante | la scheda mostra il messaggio, nessun blocco | `LICENSE_FILE_MISSING` (catalogo, `en`/`it`, parametri `file`, `path`) |
| Nell'app: voce dell'autocontrollo fallita | rapporto con la voce `failed` e il dettaglio, uscita 1 | — (rapporto JSON) |
| Prima apertura di una chiave salvata da un altro programma (es. il `.venv` di sviluppo) o da una costruzione precedente | macOS chiede all'utente di permettere l'accesso al Portachiavi: la firma ad hoc cambia a ogni costruzione, quindi la richiesta torna dopo ogni nuova app. Non è un errore del `31`; si spiega nel testo del sito (60b) | — |
| App scaricata (con l'attributo di quarantena) | Gatekeeper la blocca: "Apri comunque" (A6, 60b) | — |

## 11. Esposizione all'IA

Non applicabile: è la costruzione dell'app, non uno strumento che l'IA può invocare. La finestra Licenze non è un
comando del `05`.

## 12. Test di accettazione

Test automatici in `tests/` (di default, senza rete né Portachiavi), salvo quelli segnati "costruzione", che girano
dentro lo script (§3.8) o a mano sull'app costruita.

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Versione coerente | leggere `pyproject.toml` e `astrotwo.__version__` | `Version("0.1.0b1") == Version("0.1.0-beta.1")`; `__version__` è SemVer valido | test |
| T2 | Specifica generata | `spec_text` con un progetto finto | contiene i dati di §3.4, le esclusioni di §3.5, `dev.pages.astrotwo`, `CFBundleShortVersionString` `0.1.0`, `CFBundleVersion` `1`, nessun percorso assoluto del progetto nell'`Info.plist` | test |
| T3 | macOS minimo | `minimum_macos` su una cartella con Mach-O di `minos` noti (copiati da librerie di sistema o della ruota) | il massimo | test |
| T4 | Riferimenti esterni (V2) | `check_bundle` V2 su una cartella con un Mach-O che punta a `/opt/homebrew` | V2 `failed` con il file e il percorso | test |
| T5 | Licenze nello sviluppo | `license_files()` nel progetto | i quattro file trovati; `sources_text` contiene gli URL di PySide6 e Qt 6.12.0 e la frase sulla sostituzione di Qt | test |
| T6 | Finestra Licenze | aprire la voce di menu (pytest-qt, `offscreen`), in inglese e in italiano | quattro schede; testo di `LICENSE` uguale al file; la scheda dei crediti contiene i testi di SIMBAD e DSS di `01` §6.1; voce subito dopo About | ispezione dei widget |
| T7 | File di licenza mancante | `license_files` puntato a una cartella senza `SOURCES.txt` | la scheda mostra `LICENSE_FILE_MISSING` con nome e percorso | test |
| T8 | About ridotto | aprire About | versione `0.1.0-beta.1`, copyright, pulsante Licenses… che apre la finestra | test |
| T9 | Autocontrollo nello sviluppo | `self_check()` senza Portachiavi nel `.venv` | voci comuni `ok` (moduli, dati, traduzioni, kernel, backend caricabile); le voci "dentro l'app" sono `not_bundled` | test |
| T10 | Autocontrollo e Portachiavi | `self_check()` senza `keychain=True` con un backend finto che fallisce se usato | il backend non viene mai chiamato | test |
| T11 | `THIRD_PARTY_LICENSES` | `third_party_licenses.py --check` | contiene le sezioni Python (PSF + componenti di python-build-standalone), Qt (attribuzioni di `qtbase`/`qtsvg`), bootloader di PyInstaller | test esistente esteso |
| T12 | Costruzione completa | `uv run python scripts/build_app.py` su un albero pulito | uscita 0; V1–V6, V8, V9 `ok`; V7 `ok` con schermo; rapporto con dimensione e tempi | costruzione |
| T13 | App autonoma | V4 con `env -i`, poi a mano: `.venv` rinominato, `uv` fuori dal `PATH`, app copiata in un'altra cartella, doppio clic | l'app si apre, il cielo HiPS si carica (con rete), nessun errore nel pannello Messaggi | a mano, esito nel registro |
| T14 | Portachiavi nell'app | a mano: `AstroTwo.app/Contents/MacOS/AstroTwo --self-check-keychain` | voce `keychain_roundtrip` `ok`; nessuna voce rimasta con servizio `dev.pages.astrotwo.selfcheck` | a mano |
| T15 | Nessuna scrittura (V6) | impronte prima/dopo V4 e V7 | identiche | costruzione |
| T16 | Qt non modificato (V5) | binari Qt dell'app contro la ruota, tolte le firme | identici | costruzione |
| T18 | Icona | `make_iconset` su `assets/icon/AstroNew.svg` in una cartella temporanea | dieci PNG con le dimensioni di `iconutil`, non vuote; `.icns` creato | test (salta se `iconutil` manca) |
| T17 | Ripetibilità | due costruzioni di seguito dallo stesso commit | stessi file (stesso elenco e stesse impronte), tranne firma, `BUILD_INFO.json` e file con data | a mano, una volta |

## 13. Decisioni aperte

- **A2 — Strumento di costruzione: DECISA il 2026-10-25** dal proprietario: **PyInstaller** (`onedir` + `BUNDLE`),
  dopo il confronto con Briefcase di §8. Per il `.dmg` lo strumento si decide nel 60b (orientamento `dmgbuild`).
- **A6 — Firma e notarizzazione: DECISA per la prima beta il 2026-10-25** dal proprietario: niente Apple Developer
  Program; firma **ad hoc** soltanto, **nessuna notarizzazione**; il sito spiegherà "Apri comunque". **Firma
  Developer ID e notarizzazione: RINVIATE** (voce `A6-b` in `decisioni-aperte.md`, Gruppo 3), da riprendere prima
  di una versione non beta.
- **Python dell'app: DECISO il 2026-10-25** dal proprietario: CPython 3.12 di python-build-standalone gestito da uv,
  ambiente separato da `uv.lock`, test eseguiti in quell'ambiente; macOS minimo letto dai binari (14.4 oggi).
- **Versione: DECISA il 2026-10-25** dal proprietario: §3.2.
- **Icona: DECISA il 2026-10-25** dal proprietario: la fornisce il proprietario, consegnata lo stesso giorno in
  `assets/icon/AstroNew.svg` (§3.6); disegno originale del proprietario, licenza GPL-3.0-or-later.
- **D60-1 — Sorgente di AstroTwo per la GPL-3.0 (§6): DECISA il 2026-10-25** dal proprietario: **(a) + (b)** —
  repository GitHub pubblico `https://github.com/guidogg13/AstroTwo` con un tag per ogni versione
  (`v0.1.0-beta.1`) e archivio del sorgente (`git archive` del commit) accanto al `.dmg`. Oggi il repository è
  privato: il proprietario lo renderà pubblico al momento della pubblicazione (prima del 60b non serve).
  `SOURCES.txt` riporta l'indirizzo del repository, il tag della versione e il commit; finché il repository non è
  pubblico la costruzione scrive l'avviso `BUILD_SOURCE_NOT_PUBLIC` nel rapporto (non bloccante nel 60a). Opzioni
  che c'erano: (a) repository pubblico con tag; (b) archivio accanto al `.dmg`; (c) offerta scritta.
- **D60-2 — Scelte minori: CONFERMATE dal proprietario il 2026-10-25:** numero di build in `[tool.astrotwo.bundle]`; `--skip-tests`,
  `--allow-dirty` e `--keep-build` come opzioni dichiarate nel rapporto; voce Licenze nel menu dell'app (non in
  Help); V7 e V9 riportati senza bloccare.
- **D60-3 — V5 fallito alla prima costruzione: DECISA il 2026-10-25** dal proprietario: **(b)** — dopo PyInstaller
  i binari di Qt si sostituiscono con le copie esatte della ruota (universali, intestazioni originali) e l'app si
  firma di nuovo (§3.3 punto 8); circa 25–30 MB in più. Causa: PyInstaller toglie la parte `x86_64` e riscrive
  `LC_ID_DYLIB` e `LC_RPATH` (codice `arm64` identico). Opzione scartata: (a) accettare la modifica e dichiararla in
  `SOURCES.txt`.

- **D60-4 — macOS minimo 26.0 per colpa della ruota di PySide6 6.12.0:** i moduli di collegamento di PySide6 e
  shiboken6 6.12.0 dichiarano `minos 26.0` (la ruota è etichettata `macosx_14_0`), quindi `LSMinimumSystemVersion`
  è 26.0 e su macOS 14 e 15 l'app con ogni probabilità non parte (dyld rifiuta librerie costruite per un macOS più
  nuovo; **da verificare** su un Mac con macOS 14 o 15, non disponibile qui). Vale anche per `uv run astrotwo` con
  lo stesso `uv.lock`. Opzioni: (a) accettare macOS 26 come minimo della prima beta e scriverlo sul sito;
  (b) cambiare versione di PySide6 (una con le librerie costruite per macOS 14, da cercare e verificare: è un
  aggiornamento di dipendenza, solo su richiesta esplicita, con nuovo controllo delle impronte e i test); (c)
  segnalarlo al progetto Qt for Python e aspettare una ruota corretta. **Raccomandazione: (a) per la prima beta
  e (c) in parallelo**; (b) solo se servono utenti con macOS 14/15 subito. Da decidere (non blocca il 60a, conta
  per il 60b).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-25 | Claude Code | Creazione del file (stato: bozza), sprint 60a. Decisioni del proprietario del 2026-10-25: A2 (PyInstaller, dopo il confronto con Briefcase), A6 (firma ad hoc senza notarizzazione per la prima beta; Developer ID rinviata), Python di python-build-standalone gestito da uv, forma della versione (`0.1.0b1` / `0.1.0-beta.1`, build `1`), icona fornita dal proprietario. Parte A (app) completa; parte B (`.dmg`, 60b) da completare. Aperte D60-1, D60-2, D60-3. |
| 2026-10-25 | Claude Code | **Approvato dal proprietario** (stato `approvato`). Icona: disegno originale del proprietario, GPL-3.0-or-later (§3.6). D60-1 decisa (a) + (b): repository GitHub pubblico con tag per versione e archivio del sorgente accanto al `.dmg` (§3.7, §10, §13). D60-2 confermata. |
| 2026-10-25 | Claude Code | Codice dello sprint 60a: verifiche V-a…V-e fatte (§3.7, §3.11); D60-3 aperta dal fallimento di V5 alla prima costruzione e decisa (b) dal proprietario (§3.3 punto 8, §3.7 punto 4, §13); V7 misura fino alla riga `first_view`, `on_first_view` di `main_window.main`, `keep_entry` (§3.8, §7). Stato `approvato` invariato. |
| 2026-10-25 | Claude Code | **Costruzione e verifica dello sprint 60a (commit `3b697a7`, albero pulito, nessuna opzione):** 943 test di default passati in `build/env` (Python 3.12.15 di python-build-standalone); V1–V9 tutti `ok`: firma ad hoc, nessun riferimento esterno, autocontrollo in ambiente vuoto, 14 binari di Qt uguali alla ruota (tolta la firma, D60-3), nessuna scrittura nell'app, avvio, licenze. **Dimensione 248,1 MB** (260 100 096 byte; PySide6 82,7 MB di cui Qt 50,3, scipy 32,8, Pillow 11,5). **Avvio fino alla prima vista: 2,59 s a freddo, 1,96 s a caldo** (eseguibile, ambiente vuoto con HOME temporanea, cache vuota, iMac di sviluppo); lancio con `open` riuscito. Prove a mano: T13 — `.venv` rinominato, `uv` fuori dal `PATH`, app copiata fuori dal progetto e aperta con `open`: scaricati in HTTPS i 12 tile di ordine 0 di DSS2 (cielo intero), `properties` e `Moc.fits`; copia identica prima e dopo (1951 file); T14 — `--self-check-keychain` con il Portachiavi di login: `keychain_roundtrip` ok, nessuna voce rimasta. Controlli V4 e V7 con HOME temporanea (con la HOME vera l'app leggeva la chiave del profilo IA e macOS chiedeva il permesso, §10). Aperta D60-4 (macOS minimo 26.0 per la ruota di PySide6). T17 (ripetibilità) non ancora eseguito. Stato `approvato` invariato. |
