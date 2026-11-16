# 65-windows-linux.md — AstroTwo su Windows e Linux

**Stato:** bozza

> Sprint **W1** (2026-11-16): analisi di portabilità, correzioni piccole e sicure, workflow dei test su tre sistemi.
> Decisioni del proprietario del **2026-11-16** registrate qui: AstroTwo arriva anche su Windows e Linux con **un
> solo codice Python** (cambia solo il pacchetto, decisione del 2026-11-07); pacchetti costruiti con **GitHub
> Actions** (runner `windows-latest` e `ubuntu-latest`); prove a mano in macchine virtuali **UTM** sul Mac, alla fine
> (W3); la **versione Mac 1.0 non si tocca** (nessun cambio di comportamento su macOS, nessun nuovo `.dmg`); sprint
> W1 analisi + prove automatiche, W2 correzioni + pacchetti, W3 megatest + rilascio 1.1.
>
> Sprint **W2** (2026-11-16): il brief del proprietario del 2026-11-16 decide **D65-1, D65-2, D65-3, D65-4, D65-5,
> D65-7, D65-8, D65-9, D65-10** come nel consiglio di §13 e chiede di correggere i punti «bloccante» e «da
> correggere» (§3.7), il test dell'identità dei byte sui tre runner (§3.8), il workflow manuale dei pacchetti (§3.9),
> la documentazione e la sezione Windows/Linux della `62` per il W3. D65-6 (macchine virtuali) resta aperta.

## 2. Scopo

Elencare tutto ciò che in AstroTwo dipende da macOS, con gravità e correzione proposta, e fissare come AstroTwo si
prova, si costruisce e si consegna su Windows e Linux senza cambiare niente su macOS.

## 3. Cosa fa

### 3.1 Metodo dell'analisi (W1)

- Ricerca in `src/`, `scripts/` e `tests/` di: percorsi (`Path.home()`, `~/Library`, separatori, `os.sep`), sistema
  (`sys.platform`, `platform.system`, `ctypes`), Portachiavi/`keyring`, scrittura di file di testo (fine riga,
  codifica), URL `file:`, `QSettings`, scorciatoie (`Meta`, `Ctrl`, `StandardKey`), font, OpenGL, SAMP, provider IA
  locali, nomi di file generati dai dati, processi esterni, `multiprocessing`, permessi POSIX nei test.
- Controllo di `uv.lock`: per ogni pacchetto con codice compilato, presenza delle ruote per `win_amd64`, `win_arm64`,
  `manylinux x86_64` e `aarch64` (§3.4).
- Lettura del codice di Astropy usato nelle esportazioni (`astropy.io.ascii.ui.write`, `astropy.io.votable.util`):
  il writer di testo unisce le righe con `os.linesep` e apre i file con la codifica di default del sistema; il writer
  VOTable apre il file in modalità testo (traduzione `\n` → `\r\n` su Windows).
- Gravità: **bloccante** = dati o file sbagliati, funzione bloccata, crash, oppure niente da consegnare;
  **da correggere** = funziona ma in modo sbagliato per quel sistema (posto dei file, privacy, scorciatoia);
  **solo aspetto** = testo, aspetto, comodità. Stessa scala della regola di stop della `63` §3.1.

### 3.2 Elenco dei punti

Le righe si riferiscono al commit del W1. «W1» nella colonna Stato = corretto in questo sprint (§3.3).

| # | Punto | File e riga | Gravità | Correzione proposta | Stato |
|---|---|---|---|---|---|
| P1 | **Chiavi API**: il 31 usa solo il backend macOS di `keyring`; fuori da macOS `KEYCHAIN_UNAVAILABLE` (l'assistente IA non si usa, il resto funziona). Regola d'oro n. 5 e `01` S2/S5 parlano solo del Portachiavi di macOS | `src/astrotwo/ai/keychain_keys.py:105` | bloccante (per l'IA) | Backend forzato per sistema, mai la scelta automatica di `keyring` né file in chiaro: Gestione credenziali di Windows, Secret Service su Linux; senza Secret Service `KEYCHAIN_UNAVAILABLE` come oggi | **W2** (D65-1) |
| P2 | **Esportazioni con fine riga del sistema**: VOTable (export, SAMP, sottoinsiemi, SED), CSV, ECSV del 14 e del 25, MOC, file di sessione e `properties` dei HiPS scritti in modalità testo o con `os.linesep` di Astropy → `\r\n` su Windows | `catalogs.py` (`save_subset`), `vo_protocols.py:263, 314, 346`, `profile_export.py:927`, `moc.py:670, 672`, `commands.py:3412`, `hips.py:2414` | bloccante | VOTable scritti in memoria e poi in binario (`write_votable_file`, `catalogs.py:1864`); testo di Astropy con `\n` (`ascii_table_text`, `catalogs.py:1877`); `newline="\n"` in ogni `write_text`. Su macOS stessi byte di prima (test) | **W1** |
| P3 | **ECSV nella codifica di default del sistema**: Astropy apre il file senza `encoding` → cp1252 su Windows; un nome o una descrizione non ASCII (η, Å, °) dà `UnicodeEncodeError` o un file non UTF-8 | `vo_protocols.py:346`, `profile_export.py:927` | bloccante | UTF-8 esplicito (insieme a P2) | **W1** |
| P4 | **URL `file:` ricevuti via SAMP**: `unquote("/C:/dati/t.xml")` non è un percorso di Windows → copia del VOTable di TOPCAT non riuscita | `vo_protocols.py:2970` | bloccante | Su Windows `nturl2path.url2pathname` (`file_url_path`, `vo_protocols.py:2714`); su macOS e Linux invariato | **W1** |
| P5 | **Privacy verso l'IA**: i percorsi assoluti nei testi mandati al provider si riducono al nome del file (32 §3.7) solo nella forma POSIX; `C:\Users\…\m45.fits` passerebbe intero | `tool_registry.py:231, 314` | da correggere | Su Windows anche `C:\…`, `C:/…`, `\\server\…`; su macOS e Linux nessun cambio | **W1** |
| P6 | **Cartelle dei dati** sotto `~/Library/…`: cache (`Caches/AstroTwo`), punti SED (`Application Support/AstroTwo/Profiles`), VOTable ricevuti via SAMP (`…/SAMP/received`). Su Windows e Linux funzionano ma creano `Library` nella home | `core/cache.py:134`, `analysis/profile_export.py:181`, `ui/samp_link.py:50` | da correggere | Una funzione per sistema, macOS invariato; posti proposti in **D65-2** | **W2** (D65-2) |
| P7 | **Nessun pacchetto** per Windows e Linux: `build_app.py` si ferma fuori da macOS arm64; `make_dmg.py` e `sign_notarize.py` sono solo macOS | `scripts/build_app.py:367` | bloccante (niente da consegnare) | Nuovo script del W2 con PyInstaller `onedir` (stesso strumento, A2) sui runner; formati in **D65-3**, **D65-4**, architetture in **D65-5** | **W2b** (§3.9, da provare sui runner) |
| P8 | **Controlli dell'app costruita** pensati per il `.app`: plugin `libqcocoa.dylib`/`libqmacstyle.dylib`, backend `keyring.backends.macOS`, cartella `Contents` | `src/astrotwo/app_bundle.py:64, 237, 286` | bloccante (per i pacchetti) | Elenco dei plugin e del backend per sistema (`qwindows.dll`, `libqxcb.so`/`libqwayland*.so`), radice del pacchetto da `sys._MEIPASS` | **W2b** (§3.9) |
| P9 | **`THIRD_PARTY_LICENSES`** descrive l'app per macOS: su Windows `keyring` porta `pywin32-ctypes`, su Linux `SecretStorage`, `jeepney`, `cryptography`, `cffi`; Qt porta altre librerie (xcb, ICU…) | `scripts/third_party_licenses.py`, `THIRD_PARTY_LICENSES` | bloccante (obblighi di licenza) | Un file per pacchetto, generato sul runner; test per sistema | **W2b** (D65-7, §3.9; testi di `QT_PLATFORM_EXTRAS` da completare nel W3) |
| P10 | **OpenGL 4.1 core** obbligatorio per il cielo (41 §3.13): senza GPU (macchina virtuale, desktop remoto, driver vecchi) `GL_UNAVAILABLE`, cielo non disegnato | `ui/sky_renderer_gl.py:29`, `ui/main_window.py:3399` | da correggere (bloccante per le prove in UTM) | **D65-8** | **W2** (D65-8) |
| P11 | **Scorciatoie con `Meta`**: `Meta+Ctrl+F` (schermo intero), `Meta+Ctrl+N` (modo notte), `Meta+Ctrl+A` (assistente). Su macOS `Meta` è ⌃ (⌃⌘F, scorciatoia standard); su Windows e Linux è il tasto Windows/Super, spesso preso dal sistema (Win+Ctrl+F di Windows cerca i computer in rete) | `ui/main_window.py:2142, 2143, 2173` | da correggere | Tabella per sistema, macOS invariato; proposta in **D65-9** | **W2** (D65-9) |
| P12 | **Testi «macOS Keychain»** nell'interfaccia (campo della chiave, avviso) | `ui/ai_panel.py:1014`, `ui/main_window.py:1648`, traduzioni | solo aspetto | Testo per sistema dopo D65-1 | **W2** |
| P13 | **Impostazioni** senza scorciatoia su Windows (`StandardKey.Preferences` vuota lì) | `ui/main_window.py:2110` | solo aspetto | Con D65-9 | **W2** |
| P14 | **File temporanei di SAMP**: `TemporaryDirectory` cancellata all'uscita; su Windows un file ancora aperto da TOPCAT non si cancella (`PermissionError` alla chiusura) | `vo_protocols.py:2915` | da verificare (runner o W3) | `ignore_cleanup_errors=True` solo se la prova lo mostra | da verificare |
| P15 | **File di sessione** con percorsi assoluti dei file: una sessione salvata su un sistema non si riapre su un altro (`file_unreadable`, `path_not_absolute`) | `core/commands.py:554` | solo aspetto | Limite dichiarato in `05` e nella documentazione; nessun cambio | **W2** (D65-10, documentato) |
| P16 | **PNG e PDF** non uguali byte per byte tra sistemi: le etichette del PNG usano i font del sistema; il PDF ha la data di creazione. I dati (CSV, ECSV, VOTable, FITS, MOC, JSON) sì | `ui/export_view.py`, `analysis/profile_export.py` | solo aspetto | Regola in **D65-10** | **W2** (D65-10: fuori dalle impronte) |
| P17 | **Nome nella barra dei menu** (`set_macos_app_name`): solo macOS, altrove non fa niente (già così) | `ui/main_window.py:3354, 3400` | nessuno | — | ok |
| P18 | **Icona e voce di menu del sistema**: `.icns` solo per il `.app`; servono `.ico` (Windows) e `.desktop` + PNG (Linux) | `scripts/build_app.py`, `assets/` | solo aspetto | Nel W2, dal file SVG dell'icona | **W2b** (`.ico` e PNG dall'SVG) |
| P19 | **Font dell'interfaccia** del sistema (SF su macOS, Segoe UI su Windows, quello della distribuzione su Linux); cifre tabellari con `tnum` | `ui/main_window.py:690`, `ui/catalog_panel.py:89` | solo aspetto | Nessuno; si guarda nel W3 | W3 |
| P20 | **Schermi HiDPI con scala frazionaria** (125 %, 150 % su Windows): il disegno usa `devicePixelRatioF`; precisione del clic entro 1 pixel (41) da verificare | `ui/sky_renderer_gl.py:448-516`, `ui/sky_viewer.py:886` | da verificare (W3) | — | da verificare |
| P21 | **Documentazione** per gli utenti solo macOS («Apri comunque», `.dmg`) | `docs/installation.md`, `README.md` | solo aspetto | Nel W2/W3 con i pacchetti (Windows SmartScreen «Ulteriori informazioni → Esegui comunque») | **W2b** (`docs/installation.md`) |
| P22 | **Test** non portabili: `import pwd` (non esiste su Windows), backend Security di macOS importato in testa al file, permessi POSIX (`umask`, `chmod`), confronto di `THIRD_PARTY_LICENSES` | `tests/votable_check.py`, `tests/ai/test_keychain_keys.py`, `tests/ai/test_messages_keychain.py`, `tests/analysis/test_profile_export.py`, `tests/ui/test_export_png.py`, `tests/core/test_cache.py`, `tests/test_third_party_licenses.py` | da correggere (solo test) | `pwd` facoltativo; test del Portachiavi di macOS solo su macOS; permessi POSIX saltati su Windows; confronto delle licenze solo su macOS fino a D65-7 | **W1** |
| P23 | **Estrazione del repository su Windows**: `core.autocrlf` di git sul runner convertirebbe i file in CRLF e i confronti byte per byte dei test fallirebbero | `.github/workflows/tests.yml` | da correggere (solo CI) | `git config --global core.autocrlf false` prima del checkout | **W1** |

**Controllati e senza problemi:** provider IA locali (`provider_adapter.py:227-233`: solo URL `http://localhost:11434/v1`
e `:1234/v1`, AstroTwo non avvia Ollama né LM Studio; su Windows la risoluzione di `localhost` prima in `::1` è da
verificare nel W3); `QSettings` (Qt sceglie il posto nativo: registro `HKCU\Software\pages.dev\astrotwo` su Windows,
`~/.config/pages.dev/astrotwo.conf` su Linux); file temporanei (`tempfile`, `os.replace`: atomico anche su Windows, un
file di destinazione aperto da un altro programma dà l'errore dichiarato); separatori (nessun percorso di file
costruito con `"/"`: le `"/"` trovate sono URL e nomi di tabelle ADQL); nomi di file generati dai dati
(`sed_catalog_path`: solo `[A-Za-z0-9_-]`; VOTable ricevuti: `AAAAMMGGThhmmssZ-n.xml`, senza `:`); scritture
binarie (FITS, PNG, tile); hub SAMP (`pyvo` scrive `~/.samp` nella home, come TOPCAT su ogni sistema; server solo su
`127.0.0.1`); PDF del profilo (font DejaVu dentro matplotlib, uguale ovunque); `multiprocessing` non usato;
`pytest-timeout` con metodo `thread` (funziona su Windows).

### 3.3 Correzioni fatte nel W1 (nessun cambio su macOS)

1. **Scrittura dei file di testo con `\n` e UTF-8 su ogni sistema** (P2, P3). Due funzioni del 13
   (`src/astrotwo/core/catalogs.py`):
   - `write_votable_file(vot, target)`: Astropy scrive in un `BytesIO`, i byte vanno su disco con `write_bytes`.
     Usata da `save_subset` (13), `_write_votable_file` (14: export, SAMP, SED del 25);
   - `ascii_table_text(table, **kwargs)`: testo di `astropy.io.ascii.write` in memoria; se `os.linesep` non è
     `\n` (solo Windows) `\r\n` → `\n`. Usata dal CSV e dall'ECSV del 14 e dall'ECSV del 25, scritti in UTF-8.
   - `newline="\n"` nei `write_text` di MOC JSON e ASCII (16), file di sessione (05), `properties` dei HiPS (12).
   - Su macOS e Linux i byte sono **identici** a quelli di prima: provato dai test `test_votable_bytes_unchanged_where_lf`
     e `test_ascii_bytes_unchanged_where_lf` (confronto con la scrittura diretta di Astropy). Un test statico
     (`test_text_writes_declare_newline`) impedisce nuove scritture di testo senza `newline`.
2. **URL `file:` di SAMP su Windows** (P4): `file_url_path` del 14, chiamata solo con `os.name == "nt"`.
3. **Percorsi di Windows nei testi per l'IA** (P5): seconda espressione `_WINDOWS_PATH` del 32, applicata solo con
   `os.name == "nt"`.
4. **Test portabili** (P22) e **workflow** (P23, §3.5).

Nessuna funzione nuova per l'utente, nessun messaggio nuovo, nessuna dipendenza nuova.

### 3.4 Ruote delle dipendenze in `uv.lock` (2026-11-16)

- `win_amd64` e `manylinux x86_64`: tutte presenti (i soli pacchetti senza ruota Windows, `cffi` e `cryptography`, si
  installano solo su Linux come dipendenze di `SecretStorage`).
- **`win_arm64` mancanti**: `pyerfa` (dipendenza di Astropy), `astropy-healpix`, `mocpy`, `reproject`, `spiceypy`,
  `spherical-geometry`, `numcodecs`, `google-crc32c`. Un pacchetto Windows ARM64 nativo oggi non si fa.
- **`linux aarch64` mancante**: `spherical-geometry` (solo sorgente, da compilare).
- PySide6 6.11.3: `manylinux_2_34_x86_64` → serve **glibc 2.34** o più (Ubuntu 22.04, Debian 12, Fedora 35, RHEL 9 e
  successive). Il pacchetto Linux va costruito sul sistema più vecchio ammesso (D65-4).

### 3.5 Workflow dei test (`.github/workflows/tests.yml`)

- Avvio: push su `main`, pull request, a mano (`workflow_dispatch`). Permessi in sola lettura.
- Matrice `macos-latest`, `windows-latest`, `ubuntu-latest`, `fail-fast: false` (si vede ogni sistema).
- Passi: `core.autocrlf false`; checkout; su Linux le librerie di sistema per Qt (`libegl1 libgl1 libxkbcommon0
  libfontconfig1 libdbus-1-3`); `astral-sh/setup-uv` con uv **0.13.7** (quella del Mac); `uv sync --locked`
  (Python 3.12 di uv); stampa di sistema, `os.linesep`, codifica di default e versione di Qt; `ruff check .`;
  `uv run --frozen python -m pytest -q -p no:cacheprovider -ra --junitxml=…` (test di default di `pyproject.toml`:
  niente rete, Portachiavi reale, prestazioni, OpenGL); rapporto JUnit come artefatto.
- `QT_QPA_PLATFORM=offscreen` su tutti e tre (come `tests/conftest.py`). **Niente `PYTHONUTF8`**: su Windows si prova
  la codifica di default, come nell'app.
- Niente pacchetti, niente rete, niente segreti. Il **push** che lo attiva lo decide il proprietario.

### 3.6 Cosa si è provato sul Mac e cosa resta ai runner

- **Provato sul Mac** (suite di default e `tests/test_platform_portability.py`): stessi byte su macOS; con
  `os.linesep = "\r\n"` simulato, CSV, ECSV e VOTable esportati senza `\r` e in UTF-8; conversione degli URL `file:` di
  Windows (`nturl2path`); riduzione dei percorsi di Windows con `os.name = "nt"` simulato; controllo statico delle
  scritture di testo; workflow letto come YAML valido.
- **Solo sui runner veri:** traduzione `\n` → `\r\n` dei file aperti in modalità testo (dipende da come è compilato
  Python, non si simula); codifica cp1252 di default; caricamento di PySide6 e del plugin `offscreen` su Windows e
  Linux; i ~1400 test di default su Windows e Linux (permessi, percorsi, nomi con `\`, blocchi dei file aperti);
  `KEYCHAIN_UNAVAILABLE` reale fuori da macOS (`test_keychain_unavailable_outside_macos`); copia SAMP di un URL
  `file:///C:/…` (`test_samp_file_url_windows`). I risultati del primo run vanno nel W2.
- **Solo a mano (W3):** OpenGL vero, scorciatoie, font, HiDPI, SAMP con TOPCAT, Ollama, pacchetti.

### 3.7 Correzioni del W2 (sprint W2a; nessun cambio su macOS)

1. **Chiavi API (P1, P12; D65-1).** `_system_backend` del 31: macOS invariato (`_macos_backend`); Windows
   `WinVaultKeyring`, Linux `SecretService.Keyring`, presi da `SYSTEM_STORES` e creati direttamente; `priority` che
   solleva → `KEYCHAIN_UNAVAILABLE` `store_unavailable`; modulo non importabile → `store_not_loadable`; sistema senza
   archivio previsto → `unsupported_system`. Testi «macOS Keychain» solo su macOS, altrove «system key store: …»
   (`store_name`), tradotti. Regola d'oro n. 5 in `CLAUDE.md` e `01` S5 aggiornate.
2. **Cartelle (P6; D65-2).** `default_cache_root(system)` e nuova `default_data_root(system)` del 04: Windows
   `%LOCALAPPDATA%\AstroTwo\Cache\` e `%LOCALAPPDATA%\AstroTwo\`; Linux `$XDG_CACHE_HOME/astrotwo/` e
   `$XDG_DATA_HOME/astrotwo/` (variabili solo se assolute, se no `~/.cache` e `~/.local/share`); punti SED in
   `…/Profiles/`, VOTable SAMP in `…/SAMP/received/`; macOS invariato. Nei test la home finta copre anche
   `USERPROFILE` e `LOCALAPPDATA` (i test non toccano mai le cartelle vere, anche su Windows).
3. **OpenGL di ripiego dichiarato (P10; D65-8)**, solo Windows e Linux: `configure_opengl` prima della `QApplication`
   (variabile `ASTROTWO_OPENGL=software|native`, altrimenti `QSettings` `opengl/fallback`); Windows
   `AA_UseSoftwareOpenGL` (`opengl32sw.dll` di Qt, Mesa llvmpipe), Linux `LIBGL_ALWAYS_SOFTWARE=1`. Dopo un
   `GL_UNAVAILABLE` col disegno nativo: `opengl/fallback=software` e messaggio `GL_SOFTWARE` `next_start` («riavviare
   AstroTwo»); se anche il software non va: `software_failed`, nessun altro tentativo automatico (niente cicli). Un
   renderer software (`llvmpipe`, `softpipe`, `GDI Generic`…, anche scelto da Qt da solo) si dichiara con
   `GL_SOFTWARE` `in_use` e nella barra di stato. Su macOS non si legge niente e non c'è ripiego (41 v1).
   **Da verificare nel W3:** che `opengl32sw.dll` di PySide6 dia OpenGL 4.1 core (il workflow dei pacchetti controlla
   solo che ci sia).
4. **Scorciatoie (P11, P13; D65-9).** `platform_shortcuts`: macOS ⌃⌘F, ⌃⌘N, ⌃⌘A, ⌘, invariate; Windows e Linux F11,
   Ctrl+Shift+N, Ctrl+Shift+A, Ctrl+, (mai il tasto Windows/Super).
5. **Identità dei byte (D65-10, §3.8).**

Messaggi nuovi: `GL_SOFTWARE` (`in_use`, `next_start`), ragioni nuove di `KEYCHAIN_UNAVAILABLE`. Nessuna
dipendenza nuova (le librerie di `keyring` per Windows e Linux erano già in `uv.lock`).

### 3.8 Identità dei byte tra sistemi (D65-10)

- `scripts/export_fingerprints.py` scrive da un **caso fisso** senza rete i file di dati: CSV, ECSV e VOTable del 14,
  sottoinsieme VOTable del 13, MOC FITS, JSON e testo del 16, ECSV dei valori e VOTable della SED del 25 (profilo di
  51 Peg dalle risposte registrate, `tests/data/fingerprint_profile.json`, senza miniature), file di sessione del 05
  (un comando di conversione di unità: nessun percorso). Provenienza fissa (origine `pleiadi.xml`, non il percorso
  della cartella temporanea) e orologio fisso (`datetime.now` dei moduli 04 calcolatrici, 05, 13, 14 → 2026-11-16
  12:00 UTC): la «data fissa» di T9.
- Impronte di riferimento in `tests/data/export_fingerprints.json` (calcolate su macOS);
  `tests/test_export_fingerprints.py` le confronta su ogni sistema, controlla che nei file non ci siano `\r` né il
  percorso della cartella di lavoro.
- Workflow `tests`: ogni sistema scrive `fingerprints-<os>.json` (anche se un test è fallito) e lo carica come
  artefatto; il job `fingerprints` li scarica e li confronta (`--compare`): un file diverso o mancante fa fallire il
  workflow.
- Fuori dalle impronte (D65-10): PNG e PDF (font del sistema, data del PDF: stesso contenuto, non stessi byte) e le
  sessioni con file aperti (percorsi assoluti: **una sessione non si riapre su un altro sistema**, limite dichiarato in
  `docs/installation.md`).

### 3.9 Pacchetti di Windows e Linux (sprint W2b; D65-3, D65-4, D65-5, D65-7)

- **Workflow** `.github/workflows/build-windows-linux.yml`, **solo a mano** (`workflow_dispatch`): nessun avvio
  automatico, nessuna firma (D65-11), nessuna release né tag; i pacchetti restano **artefatti del workflow** (30
  giorni). Job `windows` su `windows-latest`, job `linux` su **`ubuntu-22.04`** (glibc 2.35, D65-4); uv 0.13.7,
  `uv sync --locked` (gruppo `build` compreso), Qt `offscreen`.
- **Script** `scripts/build_windows_linux.py` (gira solo su Windows o Linux x86_64, D65-5; `BuildError` altrove):
  test di default (se non `--skip-tests`), `THIRD_PARTY_LICENSES` del pacchetto generato sul runner
  (`third_party_licenses.py --package`, D65-7), icona dall'SVG (`.ico` 16–256 px su Windows, PNG 256 su Linux),
  PyInstaller **`onedir`** (A2) con gli stessi dati, moduli ed esclusioni del `.app` (`build_app.astrotwo_datas`,
  `DATA_PACKAGES`, `EXCLUDES`), plugin di Qt del sistema (`QT_PLUGINS_KEEP`: `qwindows`, `libqxcb`, Wayland,
  `offscreen` per i controlli, formati d'immagine di qtbase e qtsvg), moduli di `keyring` del sistema
  (`HIDDEN_IMPORTS`), su Windows `opengl32sw.dll` della ruota di PySide6 accanto alle DLL di Qt (D65-8).
- **Pacchetti** (in `dist/`, ognuno con il suo `.sha256` nel formato di `sha256sum`):
  `AstroTwo-<versione>-windows-x86_64.zip` (cartella `AstroTwo\` con `AstroTwo.exe`, D65-3);
  `AstroTwo-<versione>-linux-x86_64.tar.gz` (cartella `AstroTwo/`) e `AstroTwo-<versione>-linux-x86_64.AppImage`
  (AppDir con `AppRun`, `astrotwo.desktop`, icona; `appimagetool` 1.9.1 e runtime statico `type2-runtime` 20251108
  fissati per URL e SHA-256 nel workflow: non serve `libfuse2`, D65-4).
- **Controlli sui pacchetti** (scompattati in una cartella nuova, come li riceve l'utente; l'AppImage lanciata con
  `APPIMAGE_EXTRACT_AND_RUN=1`), con una home finta e il `PATH` del sistema: **W1** contenuto (eseguibile,
  `BUILD_INFO.json`, i quattro file di licenza, plugin di Qt del sistema, `THIRD_PARTY_LICENSES` con le dipendenze
  del sistema); **W2** `opengl32sw.dll` su Windows; **W3** autocontrollo `--self-check` (60 §7, ora per sistema: P8);
  **W4** prova di fumo `--smoke-profile` con le risposte registrate di `tests/analysis/data/profile` (come V10 del
  `.dmg`: Qt `offscreen`, proxy verso una porta chiusa, nessuna rete). Un controllo fallito → workflow rosso; il
  rapporto è in `dist/build-report-<sistema>.json` (anche lui artefatto).
- **Autocontrollo per sistema (P8, 60):** `QT_PLUGINS_NEEDED` e `KEYRING_BACKENDS` di `app_bundle` per
  `sys.platform`; su Linux senza Secret Service in esecuzione (runner) il backend incluso basta (`store_unavailable`
  annotato, voce `ok`). Nuova opzione `--report-file FILE` dell'avvio: il rapporto di `--self-check` e
  `--smoke-profile` va anche in un file, perché l'eseguibile di Windows senza console può non avere lo standard
  output. Su macOS nessun cambio di comportamento (l'opzione non si usa).
- **Licenze per pacchetto (D65-7):** `third_party_licenses.py --package FILE` scrive il file del sistema corrente
  (dipendenze installate lì, Python del runner, avvisi di Qt, bootloader di PyInstaller con l'eseguibile giusto);
  il file nella radice resta quello di macOS (stessi byte). **Da completare prima del rilascio 1.1 (W3):** testi
  integrali delle componenti elencate in `QT_PLATFORM_EXTRAS` (Windows: zlib, D3D12MemoryAllocator e wintab, Mesa
  llvmpipe di `opengl32sw.dll`; Linux: xcb e xkbcommon, ICU, runtime dell'AppImage), oggi dichiarate per nome e
  licenza nel file del pacchetto.
- **Non provato sul Mac** (solo sui runner, al primo run dopo il push): PyInstaller su Windows e Linux, nomi esatti
  dei plugin di Qt 6.11.3 (es. `qmodernwindowsstyle.dll`, plugin Wayland), presenza di `opengl32sw.dll` nella ruota,
  standard output dell'eseguibile senza console, `appimagetool` sul runner. Sul Mac: test di unità dello script
  (`tests/test_build_windows_linux.py`: filtro dei plugin, nomi, zip e tar, AppDir, `.sha256`, ambiente, specifica,
  `--report-file`) e dei file delle licenze per sistema.

### 3.10 Megatest di Windows e Linux (W3)

Nuova sezione **§3.16 della `62`** (prove W1–W16): pacchetti scaricati dagli artefatti, due VM UTM (Windows 11 ARM
con l'emulazione x86_64, Ubuntu 24.04 x86_64 emulato; configurazione da D65-6), limiti delle VM scritti (OpenGL solo
software, emulazione lenta, niente HiDPI vero). Le prove della 1.0 per macOS non cambiano.

## 4. Cosa NON fa

- Non cambia niente su macOS: nessun comportamento nuovo, nessun nuovo `.dmg`, la 1.0 resta quella del build 9.
- Non costruisce pacchetti nel W1 e non li firma (Authenticode di Windows: non previsto; da decidere se servirà).
- Non sceglie in silenzio posti dei file, backend delle chiavi, formati dei pacchetti, scorciatoie: sono D65-n.
- Non porta AstroTwo su Windows ARM64 nativo né su Linux ARM64 (§3.4, D65-5).
- Non fa il push del workflow, non crea tag né release.

## 5. Livello e dipendenze

- **Livello:** trasversale (distribuzione e test, fascia 60–69); tocca il codice dei livelli 1–3 solo nei punti di §3.2.
- **Dipende da:** `01-architettura.md` (S2, S5, A2), `04-cache.md`, `05-comandi-sessione.md`, `13`, `14`, `16`, `12`,
  `25`, `31`, `32`, `40`, `41`, `60-distribuzione-dmg.md`, `62-megatest-1-0.md`, `63-checklist-rilascio.md`.
- **Usato da:** sprint W2 e W3; `62` e `63` per la 1.1.

## 6. Input e output

- **Input:** il codice di `main`, `uv.lock`, i runner di GitHub Actions.
- **Output del W1:** questo file; le correzioni di §3.3; `tests/test_platform_portability.py`;
  `.github/workflows/tests.yml`. **Output previsti del W2:** pacchetti Windows e Linux (formati D65-3, D65-4) con
  impronta SHA-256, file di licenze per pacchetto (D65-7).

## 7. Interfaccia pubblica

- `astrotwo.core.catalogs.write_votable_file(vot, target) -> None`
- `astrotwo.core.catalogs.ascii_table_text(table, **kwargs) -> str`
- `astrotwo.core.vo_protocols.file_url_path(path: str) -> str` (solo Windows)
- Workflow `tests` di GitHub Actions (§3.5, §3.8).
- W2: `astrotwo.ai.keychain_keys.SYSTEM_STORES`, `store_name(system=None) -> str`;
  `astrotwo.core.cache.default_cache_root(system=None)`, `default_data_root(system=None) -> Path`;
  `astrotwo.ui.main_window.platform_shortcuts(platform_name=None)`, `configure_opengl(system=None) -> str`;
  `astrotwo.ui.sky_renderer_gl.opengl_choice`, `apply_software_opengl`, `is_software_renderer`, `SOFTWARE_GL_KEY`,
  `SOFTWARE_GL_ENV`; `scripts/export_fingerprints.py` (`fingerprints()`, `write_case(folder)`, `--output`,
  `--compare`).

## 8. Librerie e standard di riferimento

- Python `nturl2path` (conversione URL `file:` ↔ percorso di Windows), `pathlib`, `io`.
- Astropy `io.ascii` e `io.votable` (writer invariati, solo la destinazione cambia).
- `keyring` 25.x: backend `Windows.WinVaultKeyring` e `SecretService.Keyring` (per D65-1).
- PyInstaller 6.22.3 (A2) per i pacchetti del W2; AppImage (D65-4).
- XDG Base Directory Specification; cartelle note di Windows (`%LOCALAPPDATA%`, `%APPDATA%`) per D65-2.
- GitHub Actions: `actions/checkout@v4`, `astral-sh/setup-uv@v6`, `actions/upload-artifact@v4` (versioni da
  ricontrollare al primo run).

## 9. Regole e vincoli

- **macOS invariato:** ogni correzione o è identica su macOS (provato da un test che confronta i byte) o è dietro
  `os.name == "nt"` / `sys.platform`. Un cambio che non si può provare così va al W2 come decisione.
- **Esportazioni di dati identiche byte per byte su tutti i sistemi** (CSV, ECSV, VOTable, FITS, MOC, sessione,
  `properties`): fine riga `\n`, UTF-8. Per PNG e PDF vale D65-10.
- Regola d'oro n. 5 (chiavi solo in un archivio sicuro del sistema, mai in file): resta, la forma per Windows e Linux è
  D65-1 e cambia `CLAUDE.md` e `01` solo con la decisione del proprietario.
- Test: `uv run python -m pytest -q`, ruff pulito; il numero di test non scende.

## 10. Casi limite ed errori

- Un valore di testo con `\r\n` dentro (raro) in un CSV o ECSV esportato su Windows diventa `\n`: su macOS e Linux
  non cambia niente. Da ricontrollare quando i runner Windows girano.
- Un VOTable salvato con un nome che finisce in `.gz` va ancora ad Astropy, che lo comprime come prima (su macOS
  invariato); su Windows il testo dentro il gzip avrebbe ancora `\r\n`: caso raro, da ricontrollare nel W2.
- Linux senza Secret Service (server senza sessione grafica): l'IA dà `KEYCHAIN_UNAVAILABLE` `store_unavailable`;
  il resto funziona (regola d'oro n. 7). Mai un ripiego su file.
- Windows o Linux senza OpenGL 4.1: `GL_UNAVAILABLE`, poi disegno software dal prossimo avvio (D65-8, §3.7); se
  anche il software non arriva a 4.1 core, `GL_UNAVAILABLE` e nessun altro tentativo (`ASTROTWO_OPENGL` per forzare).
- `LOCALAPPDATA` o `XDG_*` relativi o vuoti: si usano i default del sistema (specifica XDG).
- Sessione aperta su un altro sistema: errori `file_unreadable` / `path_not_absolute` del 05 (D65-10).

## 11. Esposizione all'IA

Non applicabile: nessuno strumento nuovo; P5 rafforza solo la riduzione dei percorsi del 32 §3.7 su Windows.

## 12. Test di accettazione

- **T1** (W1) Esportazioni VOTable e testo con gli stessi byte di prima su macOS e Linux
  (`test_votable_bytes_unchanged_where_lf`, `test_ascii_bytes_unchanged_where_lf`).
- **T2** (W1) Con `os.linesep` di Windows simulato, CSV/ECSV/VOTable senza `\r`, UTF-8
  (`test_ascii_text_lf_with_windows_linesep`, `test_exports_without_cr_with_windows_linesep`).
- **T3** (W1) Nessuna scrittura di testo senza `newline` in `src/` (`test_text_writes_declare_newline`).
- **T4** (W1) URL `file:` di Windows → percorso (`test_file_url_path_windows`; `test_samp_file_url_windows` sul runner).
- **T5** (W1) Percorsi di Windows ridotti al nome solo su Windows
  (`test_windows_paths_reduced_to_file_names_only_on_windows`).
- **T6** (runner) Suite di default verde su `macos-latest`; elenco dei fallimenti di `windows-latest` e
  `ubuntu-latest` portato nel W2.
- **T7** (W2b, runner) Pacchetti: controlli W1–W4 di §3.9 sui pacchetti scompattati (contenuto e licenze,
  `opengl32sw.dll`, `--self-check`, `--smoke-profile`); sul Mac `tests/test_build_windows_linux.py`.
- **T8** (W3) Megatest a mano in UTM (D65-6), `62` §3.16 (W1–W16).
- **T9** (W2, runner) Stessa esportazione con data fissa → stessa impronta SHA-256 sui tre sistemi (D65-10):
  `test_t9_fingerprints_equal_reference` su ogni runner e job `fingerprints` del workflow (§3.8).
- **T10** (W2) Chiavi: solo il backend del sistema, mai la scelta di `keyring` (`test_keychain_forced_backend_per_system`,
  `test_keychain_unavailable_without_system_store`); cartelle per sistema (`test_folders_per_system`,
  `test_sed_and_samp_folders_follow_the_data_root`); scorciatoie (`test_shortcuts_per_system`); OpenGL
  (`test_opengl_choice_and_software_renderers`, `test_apply_software_opengl`, `test_configure_opengl_*`,
  `test_opengl_fallback_declared`).

## 13. Decisioni aperte

**Decise dal proprietario il 2026-11-16 (brief del W2), come nel consiglio:** D65-1 (a), D65-2 (a), D65-3 (a), D65-4
(a) su `ubuntu-22.04` con `.tar.gz`, D65-5 (a), D65-7 (a), D65-8 (b), D65-9 come proposto, D65-10 (a). **Aperte:**
D65-6 e la nuova D65-11 (W2). La tabella resta come memoria delle proposte.

| ID | Domanda | Proposte | Consiglio |
|---|---|---|---|
| **D65-1** | Dove tenere le **chiavi API** su Windows e Linux (regola d'oro n. 5, `01` S2/S5, 31)? | (a) backend forzato per sistema, come oggi su macOS: **Gestione credenziali di Windows** (`keyring.backends.Windows.WinVaultKeyring`), **Secret Service** su Linux (`keyring.backends.SecretService.Keyring`: GNOME Keyring, KWallet ≥ 5.97, KeePassXC); mai `keyrings.alt` né file; senza servizio `KEYCHAIN_UNAVAILABLE`. (b) IA solo su macOS nella 1.1 | **(a)**: stesse garanzie del Portachiavi (archivio cifrato dell'utente, nessun file nostro); le librerie sono già in `uv.lock`. Cambia il testo della regola d'oro n. 5 («archivio sicuro del sistema: Portachiavi su macOS, Gestione credenziali su Windows, Secret Service su Linux») |
| **D65-2** | **Cartelle** di cache, punti SED e VOTable ricevuti via SAMP su Windows e Linux | (a) Windows: `%LOCALAPPDATA%\AstroTwo\Cache\`, `%LOCALAPPDATA%\AstroTwo\Profiles\`, `%LOCALAPPDATA%\AstroTwo\SAMP\received\`; Linux (XDG): `$XDG_CACHE_HOME/astrotwo/` (di default `~/.cache/astrotwo/`), `$XDG_DATA_HOME/astrotwo/Profiles/` e `…/SAMP/received/` (di default `~/.local/share/astrotwo/`); macOS invariato. (b) `QStandardPaths` di Qt. (c) lasciare `~/Library/…` | **(a)**: posti standard di ciascun sistema, calcolati dalle variabili d'ambiente senza Qt (il 04 è livello 1) e senza dipendenze nuove; `LOCALAPPDATA` e non `APPDATA` perché sono dati grandi o locali, da non copiare nei profili di rete |
| **D65-3** | **Pacchetto Windows** | (a) `.zip` della cartella `onedir` di PyInstaller (si scompatta e si avvia `AstroTwo.exe`); (b) installatore Inno Setup per utente (senza diritti di amministratore, menu Start, disinstallazione); (c) MSI/MSIX | **(a) per la 1.1**, (b) dopo se gli utenti lo chiedono: lo zip non richiede diritti di amministratore (PC universitari), non lascia tracce, si costruisce e si prova in modo più semplice; senza firma Authenticode Windows mostra SmartScreen in entrambi i casi |
| **D65-4** | **Pacchetto Linux** | (a) **AppImage** (un file, tutte le distribuzioni con glibc ≥ 2.34); (b) `.tar.gz` della cartella `onedir`; (c) Flatpak; (d) `.deb`/`.rpm` | **(a)**, costruito su **`ubuntu-22.04`** (glibc 2.35, la più vecchia compatibile con PySide6 6.11.3: con `ubuntu-latest` = 24.04 il pacchetto non partirebbe su Ubuntu 22.04 e Debian 12), con il runtime statico (non serve `libfuse2`, assente di default da Ubuntu 22.04); più (b) come copia dello stesso contenuto, a costo quasi zero. Flatpak e `.deb` chiedono un pacchetto per sistema e manutenzione |
| **D65-5** | **Architetture** | (a) solo **x86_64** (Windows e Linux) nella 1.1; (b) anche ARM64 | **(a)**: le ruote `win_arm64` di 8 dipendenze non esistono (§3.4); Windows 11 ARM esegue i programmi x86_64 in emulazione. Linux ARM64 da riconsiderare quando `spherical-geometry` avrà la ruota |
| **D65-6** | **Macchine virtuali UTM** per il W3 (Mac con Apple Silicon) | (a) Windows 11 ARM in UTM (virtualizzazione, AstroTwo x86_64 in emulazione Prism) + Ubuntu 24.04 x86_64 **emulato** in UTM (QEMU, lento); (b) Ubuntu 24.04 ARM64 con Rosetta per Linux e librerie `amd64` in multiarch; (c) runner ARM di GitHub (`windows-11-arm`, `ubuntu-24.04-arm`) per le prove automatiche, se il repository è pubblico | **(a)** per il megatest, con una prova breve all'inizio del W2 per sapere se l'emulazione regge; in nessuna delle due VM c'è una GPU con OpenGL 4.1: serve D65-8 per vedere il cielo. (b) solo se (a) è troppo lento; (c) utile ma da verificare (visibilità del repository) |
| **D65-7** | **Licenze di terze parti** per Windows e Linux | (a) un `THIRD_PARTY_LICENSES` per pacchetto, generato da `scripts/third_party_licenses.py` sul runner, con le dipendenze di quel sistema e i componenti di Qt inclusi; test per sistema; (b) un file unico con le dipendenze di tutti i sistemi | **(a)**: ogni pacchetto dichiara esattamente ciò che contiene (come il `.dmg`, `60` §3.7); il file di macOS resta quello di oggi |
| **D65-8** | **OpenGL** senza GPU adatta (VM, desktop remoto, driver vecchi) | (a) come oggi: `GL_UNAVAILABLE` e cielo non disegnato; (b) Windows: Mesa `llvmpipe` di Qt (`opengl32sw.dll`, se è nelle ruote di PySide6: **da verificare**) quando l'OpenGL nativo è sotto 4.1, dichiarato nella barra di stato; Linux: Mesa `llvmpipe` del sistema (già 4.5 core) | **(b)**, solo Windows e Linux: senza, il cielo non si vede nelle VM del W3; un ripiego dichiarato e lento è meglio di niente. Prima va verificato che `opengl32sw.dll` ci sia (altrimenti va incluso Mesa per Windows, licenza MIT) |
| **D65-9** | **Scorciatoie** su Windows e Linux (40) | Schermo intero **F11** (`StandardKey.FullScreen`), modo notte **Ctrl+Shift+N**, assistente **Ctrl+Shift+A**, impostazioni **Ctrl+,**; macOS invariato (⌃⌘F, ⌃⌘N, ⌃⌘A, ⌘,) | Come proposto: niente tasto Windows/Super (preso dal sistema), F11 è la convenzione di Windows e dei desktop Linux |
| **D65-10** | **Identità byte per byte** tra sistemi | (a) dati (CSV, ECSV, VOTable, FITS, MOC, sessione, `properties`) identici, provati con impronte sui tre runner; PNG e PDF «stesso contenuto», non stessi byte (font del sistema, data del PDF); sessioni non portabili tra sistemi (percorsi assoluti), dichiarato; (b) anche PNG identici, con un font dentro l'app | **(a)**: i dati scientifici sono quelli che devono essere riproducibili; per il PNG servirebbe disegnare tutto il testo con un font nostro, lavoro grande per un guadagno piccolo |
| **D65-11** | **Firma dei pacchetti** di Windows (Authenticode) e di Linux (W2) | (a) nessuna firma nella 1.1: impronta SHA-256 accanto a ogni pacchetto, istruzioni per SmartScreen in `docs/installation.md` (come il `.dmg` 1.0 senza Developer ID); (b) certificato Authenticode (OV/EV, a pagamento, o Azure Trusted Signing) per lo `.zip`; (c) firma GPG dell'AppImage | **(a)** per la 1.1: stessa scelta del Mac 1.0 (A6-b), nessun costo; SmartScreen chiede una volta sola. (b) da riconsiderare se gli utenti Windows lo chiedono; (c) poco usata dagli utenti dell'AppImage |

## 14. Registro modifiche

| Data | Autore | Modifica |
|---|---|---|
| 2026-11-16 | Claude Code | Creazione del file (stato: bozza), sprint W1, su richiesta del proprietario (decisioni del 2026-11-16 nella nota in testa). Analisi di portabilità: 23 punti (P1–P23) con file, riga, gravità e correzione; ruote di `uv.lock` per sistema; correzioni del W1 senza cambi su macOS (P2–P5, P22, P23); workflow `.github/workflows/tests.yml` (non spinto); D65-1…D65-10 aperte con consiglio. |
| 2026-11-16 | Claude Code | **Sprint W2a** (brief del proprietario del 2026-11-16): D65-1, 2, 3, 4, 5, 7, 8, 9, 10 decise come nel consiglio (D65-6 aperta). Correzioni senza cambi su macOS (§3.7): chiavi per sistema (31), cartelle per sistema (04, 25, 40), OpenGL di ripiego dichiarato (41), scorciatoie (40), testi della chiave (40, 44). Identità dei byte (§3.8): `scripts/export_fingerprints.py`, impronte di riferimento, test T9 e job `fingerprints` del workflow `tests`. Stati P1, P6, P10–P13, P15, P16 → W2. Stato del file: bozza. |
| 2026-11-16 | Claude Code | **Sprint W2b:** §3.9 pacchetti (workflow manuale `build-windows-linux.yml`, `scripts/build_windows_linux.py`, `.zip` di Windows, AppImage e `.tar.gz` di Linux su `ubuntu-22.04`, `.sha256`, controlli W1–W4 sui pacchetti scompattati, autocontrollo per sistema e `--report-file` nel 60, licenze per pacchetto con le componenti da completare); §3.10 megatest W1–W16 nella `62` §3.16; `docs/installation.md` per Windows e Linux con i limiti; P7, P8, P9, P18, P21 → W2b; T7, T8. Stato del file: bozza. |
