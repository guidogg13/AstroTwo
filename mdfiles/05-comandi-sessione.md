# 05-comandi-sessione.md — registro dei comandi e sessione

**Stato:** approvato

## 2. Scopo

Trasformare ogni azione dell'utente (menu, tastiera, mouse) e ogni
richiesta dell'IA (dal 2026-10-16, `32`) in un **comando** con nome, parametri tipizzati con
unità e risultato strutturato, eseguito chiamando solo funzioni pubbliche
del livello 1, registrato e rieseguibile, e salvare il lavoro come
**sessione** che si riapre rieseguendo i comandi.

## 3. Cosa fa

Origine: proposta AM1 **accettata dal proprietario il 2026-10-15** (modulo
generale di livello 1, come `04-cache.md`); regola d'oro n. 6 (ogni azione
dell'interfaccia = un comando registrato); D17-3 (la sessione salva
riferimenti ai file e operazioni, non i pixel, e si riesegue); righe A12,
E8 e H13 (parte cronologia) di `03-parita-aladin.md`. Prima di questo
modulo il registro e la sessione erano previsti nel `24` (livello 2): il
`24` costruirà pipeline, scripting e API Python **sopra** questo modulo.

### 3.1 Definizione di un comando

Ogni comando è descritto nel registro da una **definizione** (`CommandSpec`):

- **Nome stabile** in inglese, forma `dominio.verbo_oggetto` in minuscolo
  (es. `image.open`, `view.set_center`); il nome non cambia mai. Un
  cambiamento di parametri o di significato aumenta la **versione**
  (intero ≥ 1).
- **Funzioni chiamate:** modulo e funzioni pubbliche del livello 1 che il
  comando esegue, dichiarate (es. `view.set_center` → `make_view_wcs` e
  `choose_projection` del 10). Il comando **non calcola nulla da sé**.
- **Descrizioni** in inglese e in italiano (una frase ciascuna, più una
  riga per parametro): servono all'interfaccia (cronologia, aiuto) e allo
  schema per l'IA (§3.5).
- **Parametri tipizzati**, da un elenco chiuso di tipi:

  | Tipo | Contenuto | Note |
  |---|---|---|
  | `quantity` | valore `float64` + unità (stringa di `astropy.units`, formato FITS o VOUnit come D18-2) | la definizione dichiara la grandezza fisica (es. angolo) e l'intervallo valido; un'unità non convertibile è un errore |
  | `sky_position` | longitudine e latitudine (`quantity` angolari), frame (nome di `astropy.coordinates`), epoca | epoca scritta sempre: valore oppure `null` con il motivo (es. "frame senza epoca"); **mai assunta** (D10-2) |
  | `time` | un istante o un'epoca nella forma "tempo" qui sotto (dal 2026-10-17, precisazione di D05-4: dà un nome al tipo dei campi di epoca) | scala sempre scritta (DC1); epoca mai assunta |
  | `pixel_position` | x, y `float64` + convenzione | nel comando registrato sempre in convenzione `numpy` dichiarata (DC7); la conversione FITS ↔ numpy è del 10 |
  | `file` | percorso assoluto + SHA-256 + dimensione in byte | lo SHA-256 si calcola alla registrazione (§3.4) |
  | `url` | indirizzo | origine e data del dato scaricato stanno nel risultato (cache, `04`) |
  | `layer_ref` | identificativo di un livello prodotto da un comando precedente (`L1`, `L2`, …) | §3.2 |
  | `enum` | un valore di un elenco chiuso dichiarato | |
  | `number` | numero puro `float64` | solo per grandezze adimensionali dichiarate (es. opacità in [0, 1], gamma) |
  | `integer`, `boolean`, `string` | valori semplici | `string` solo per testi (nomi di oggetti, identificativi, espressioni), mai per numeri |
  | `list` | lista di uno dei tipi sopra | |
  | `record` | struttura con **campi tipizzati** dichiarati nella definizione (D05-4, decisa il 2026-10-17) | ogni campo è un parametro con nome, tipo (uno qualsiasi di questa tabella, anche `record` o `list`), unità e grandezza fisica dove servono, intervallo, default e descrizioni EN/IT; validato come gli altri parametri; un campo non dichiarato è un errore |

- **Forma JSON dei valori** (D05-4, decisa dal proprietario il
  2026-10-17, opzione a): ogni valore di un comando registrato, nella
  cronologia e nella sessione, si scrive così:

  | Tipo | Forma JSON | Esempio |
  |---|---|---|
  | `quantity` | `{"value": numero, "unit": "testo"}`; unità nel formato FITS o, se non valida lì, VOUnit (D18-2) | `{"value": 5.0, "unit": "arcmin"}` |
  | `sky_position` | `{"lon": quantity, "lat": quantity, "frame": "nome", "equinox": tempo o null, "obstime": tempo o null, "epoch": tempo o null, "epoch_reason": "testo" o null}`; `epoch_reason` obbligatorio quando `epoch` è `null`; `equinox`/`obstime` obbligatori quando il frame li prevede (regole del 10) | `{"lon": {"value": 56.75, "unit": "deg"}, "lat": {"value": 24.1167, "unit": "deg"}, "frame": "icrs", "equinox": null, "obstime": null, "epoch": null, "epoch_reason": "posizione scritta dall'utente senza epoca"}` |
  | tempo (dentro `sky_position` e nei campi di epoca) | epoca giuliana o besseliana come testo (`"J2000.0"`, `"B1950.0"`, scala TT per definizione) oppure `{"value": numero o testo, "format": "isot", "jd", "mjd", "jyear" o "byear", "scale": "utc", "tai", "tt", "tdb", "tcb", "tcg" o "ut1"}` (scala sempre scritta, DC1); con `"format": "jd"` il valore può essere la coppia `[jd1, jd2]` di `astropy.time`, per la precisione piena | `"J2016.0"` |
  | `pixel_position` | `{"x": numero, "y": numero, "convention": "numpy"}` (nel comando registrato sempre `numpy`, DC7) | `{"x": 10.0, "y": 20.5, "convention": "numpy"}` |
  | `file` | in ingresso `{"path": "assoluto"}`; registrato `{"path": …, "sha256": "…", "size": intero}` (calcolati alla registrazione, §3.4) | |
  | `url` | testo | `"https://…"` |
  | `layer_ref` | testo `L<n>` | `"L3"` |
  | `enum`, `string` | testo | |
  | `number` | numero JSON (§3.4: rappresentazione più breve che si rilegge identica) | |
  | `integer`, `boolean` | numero intero, `true`/`false` | |
  | `list` | array JSON di valori del tipo dichiarato | |
  | `record` | oggetto JSON con i campi dichiarati, ciascuno nella sua forma | `{"vmin": 0.0, "vmax": 100.0, "gamma": 1.0, "stretch": "linear", "palette": "gray"}` |

  Un parametro o un campo **facoltativo senza default** vale `null` quando
  manca (scritto esplicitamente nel comando registrato). Lo schema per il
  `32` (§3.5) esporta un `record` come `object` con `properties`,
  `required` e `additionalProperties: false`, e ogni campo con le stesse
  annotazioni dei parametri (unità, grandezza fisica, intervallo, elenco
  chiuso, default).
- **Valori di pixel nell'unità dell'immagine** (D05-4): i valori grezzi e
  fisici di un pixel, `BZERO` e i limiti di visualizzazione `vmin`/`vmax`
  sono `number` nella definizione con la nota "nell'unità dell'immagine
  (`BUNIT`)": l'unità non è fissa ma dell'immagine, e il risultato la
  dichiara (o dichiara "non dichiarata", regola del 17).

- **Default:** dichiarati nella definizione e **risolti al momento della
  registrazione**: il comando registrato contiene sempre tutti i valori
  usati, così la riesecuzione non dipende dai default di una versione
  futura.
- **Indicatori** dichiarati nella definizione: usa la rete (`network`),
  comando lungo (`long`: l'interfaccia mostra avanzamento e pulsante
  Annulla, regola del proprietario del 2026-10-15), modifica la vista
  (`changes_view`), solo lettura (`read_only`), **classe** (`session`,
  `passive`, `application`; D05-1, §13), **conferma richiesta quando lo
  chiede l'IA** (`confirm`, dal 2026-10-16: sì per i comandi `network` o
  `long` che non sono `read_only` e per quelli che modificano un livello
  esistente; elenco in §7; usato dal `32`).
- **Chi l'ha chiesto (`requested_by`, dal 2026-10-16):** ogni comando
  registrato porta l'origine: `menu`, `keyboard`, `mouse` (gesti e
  strumenti), `history` (Riesegui del `40`), `session` (riapertura) oppure
  `ai` con identificativo della conversazione, numero del turno,
  identificativo della chiamata, profilo e modello (`30`, `35`).
  `requested_by` è un dato descrittivo: **non cambia** validazione,
  esecuzione né risultato.
- **Risultato strutturato** (`CommandResult`): esito (`ok`, `error`,
  `cancelled`); valori restituiti dal modulo, **ogni numero con unità** e,
  dove pertinente, frame, epoca e convenzione dei pixel; avvisi (codice e
  testo del modulo); errore (codice e testo del modulo); provenienza
  (origine e data dei dati di rete o della cache, "dalla cache sì/no",
  librerie e versioni quando il modulo le dichiara); livelli prodotti;
  istanti di inizio e fine (UTC, ISO 8601, DC1); per i comandi di rete
  l'**impronta dei risultati di rete** (SHA-256 dei byte ricevuti o della
  copia in cache, origine, data, righe per le tabelle; D05-2). **Testi e numeri sono sempre quelli del modulo**: il 05 non
  riscrive messaggi e non arrotonda valori.

### 3.2 Registro, esecuzione, stato

- **`CommandRegistry`**: elenco chiuso delle definizioni. Nella prima
  versione dell'interfaccia contiene i comandi della tabella di §7; un nome
  sconosciuto → `COMMAND_UNKNOWN`.
- **Validazione prima dell'esecuzione:** tipo, unità convertibile nella
  grandezza dichiarata, intervallo, valore dell'elenco chiuso, file
  esistente e leggibile, livello esistente; un parametro non valido →
  `COMMAND_PARAMETER_INVALID` con il nome del parametro, nessuna
  esecuzione.
- **Esecuzione:** il registro chiama solo le funzioni pubbliche dichiarate
  dei moduli 04, 10–19; le eccezioni dei moduli diventano un risultato con
  esito `error`, codice e testo del modulo invariati.
- **Spazio di lavoro (`Workspace`):** gli oggetti prodotti dai comandi
  (immagini dell'11, tabelle del 13, MOC del 16, survey del 12, misure del
  17) con il loro identificativo di livello, più lo stato descrittivo
  (ordine, visibilità e opacità dei livelli, regolazioni di
  visualizzazione, vista, griglia, selezioni). L'interfaccia **legge** lo
  spazio di lavoro e non conserva copie di dati scientifici con logica
  propria (`01-architettura.md` §7). **Gli oggetti sono immutabili:** una
  modifica produce un nuovo stato che sostituisce il precedente in un solo
  passo, così una lettura da un altro thread vede sempre uno stato intero.
- **Identificativi dei livelli:** `L1`, `L2`, … in ordine di creazione, mai
  riusati nella stessa sessione; deterministici nella riesecuzione.
- **Cronologia (`CommandHistory`):** elenco ordinato dei comandi di classe
  `session` e `application` con numero progressivo, `requested_by` e
  risultato, compresi quelli in errore o annullati; i comandi `passive` non
  entrano (D05-1).
- **Annullamento cooperativo** (architettura approvata il 2026-10-15): ogni
  esecuzione riceve un `CancelToken`; il 05 lo controlla prima di iniziare
  e tra i passi dei comandi a più passi. Una funzione di un modulo già in
  corso non si interrompe: al suo ritorno, se il comando è stato annullato,
  il risultato si scarta, **lo stato non cambia** e la cronologia registra
  l'esito `cancelled` (comando non rieseguito alla riapertura). I timeout
  di rete restano quelli di `04-cache.md` (10 s / 60 s).
- **Avanzamento:** i comandi a più passi emettono un `ProgressReport`
  (passo n di m, testo del passo); gli altri dichiarano un avanzamento
  indeterminato.
- **Thread:** il 05 **non usa Qt** (è livello 1 e non dipende
  dall'interfaccia). La coda dei comandi e il thread di lavoro sono del
  `40`: i comandi di classe `session` e `application` si eseguono **uno
  alla volta, nell'ordine di arrivo**, così la cronologia è deterministica.
  I comandi `passive` non passano dalla coda (D05-1).
- **Da verificare prima del codice (richiesta del proprietario del
  2026-10-15): la cache del 04 deve reggere l'accesso da più thread.** Oggi
  `SharedCache` apre una connessione `sqlite3` per istanza, legata dalla
  libreria al thread che la crea, e i moduli creano una `SharedCache` per
  chiamata quando non ne ricevono una. Da verificare con un test: una
  istanza per thread (thread dei comandi, gruppo di thread dei tile e
  delle letture passive), scritture concorrenti senza errori "database is
  locked" entro il timeout di `sqlite3`, limite LRU sempre rispettato,
  nessuna voce parziale. Se la verifica fallisce, la correzione è una
  modifica del `04` (approvato) da autorizzare prima del codice.

### 3.3 Gesti del mouse e del trackpad

Decisione del proprietario del 2026-10-15: spostamento e zoom **non**
registrano ogni movimento. A fine gesto, quando il puntatore resta fermo
per **300 ms**, si registra un comando con lo **stato finale**:
`view.set_center` (centro) e/o `view.set_zoom` (scala). Un gesto che cambia
entrambi (zoom attorno al cursore) registra i due comandi in ordine fisso,
prima `view.set_zoom` poi `view.set_center`; rieseguiti danno lo stesso
stato finale. Un nuovo movimento entro i 300 ms continua lo stesso gesto.
Il disegno durante il gesto è del `41`.

### 3.4 Sessione

- **Formato:** file JSON in UTF-8 (scelta minore 1: estensione
  `.astrotwo.json`), con: versione dello schema della sessione, versione
  dell'app (SemVer, DC4), data di creazione e di salvataggio (UTC, ISO
  8601), **elenco ordinato dei comandi** della cronologia con parametri
  completi, `requested_by`, esito, avvisi, istanti e impronta dei dati di
  rete, **elenco
  dei file** usati (percorso assoluto, SHA-256, dimensione), **stato
  finale** (livelli con ordine, visibilità, opacità e regolazioni; vista
  con centro, scala, proiezione e base; griglia; selezioni).
- **Niente pixel** né contenuti di tabelle, niente dati della cache,
  **nessuna chiave o segreto** (regola d'oro n. 5).
- **Testo delle conversazioni con l'IA (dal 2026-10-16, `35` §3.9):** non
  entra nella sessione, salvo richiesta esplicita dell'utente al
  salvataggio; in quel caso un blocco facoltativo `conversations`
  (messaggi, chiamate, risultati come inviati al modello, rapporti del
  `34`, token) che **non si rilegge mai per rieseguire**. I nomi dei file
  nel blocco sono senza cartelle, come inviati al modello. Tag e segnalibri
  (D17-3) entreranno nella sessione con le versioni successive
  dell'interfaccia (lo schema è versionato).
- **Numeri nel JSON:** `float64` scritti con la rappresentazione più breve
  che si rilegge identica (`repr` di Python): il ritorno file → memoria è
  esatto.
- **Salvare** e **aprire** una sessione non sono comandi della sessione
  stessa.
- **Riapertura = riesecuzione** (decisione del proprietario del
  2026-10-15): in uno spazio di lavoro vuoto si rieseguono in ordine i
  comandi con esito `ok` di classe `session`; quelli in errore o annullati
  si elencano ma non si rieseguono.
  - Prima di ogni comando con file si ricalcola lo SHA-256: **se è cambiato
    ci si ferma** e lo si dichiara (`SESSION_FILE_CHANGED`: comando, file,
    SHA atteso e trovato); file mancante → `SESSION_FILE_MISSING`, stop.
    Lo stato resta quello dei comandi già rieseguiti, dichiarato.
  - I dati di rete seguono le regole dei moduli (prima la cache, con
    origine e data); l'impronta dei risultati di rete si ricalcola e, se
    è diversa da quella registrata, **avviso**
    `SESSION_NETWORK_DATA_DIFFERS` con il comando (numero e nome) e cosa è
    cambiato (impronta, origine e data, righe prima e dopo); la
    riesecuzione **continua** (D05-2, decisa il 2026-10-15).
  - Un comando che era `ok` e ora fallisce → stop, `SESSION_REPLAY_FAILED`
    con l'errore del modulo.
  - Versione di un comando non più supportata →
    `COMMAND_VERSION_UNSUPPORTED`, stop; schema della sessione più recente
    dell'app → `SESSION_SCHEMA_UNSUPPORTED`; JSON non valido →
    `SESSION_INVALID`.
  - I comandi con `requested_by = ai` si rieseguono **come gli altri,
    senza chiamare l'IA** (nessun provider, nessuna chiave necessaria).
  - Alla fine lo stato ottenuto si confronta con lo stato finale
    registrato: se differisce, avviso `SESSION_STATE_DIFFERS` con l'elenco
    delle differenze.
  - La riapertura è un'operazione lunga: avanzamento (comando n di m) e
    Annulla.

### 3.5 Schema per l'IA (predisposizione per il 32)

- `export_schema` esporta ogni definizione come **JSON Schema (draft
  2020-12)**: nome, versione, descrizione in inglese, parametri (tipo,
  unità e grandezza fisica come annotazioni, intervallo, elenco chiuso,
  default), schema del risultato e indicatori.
- Lo schema contiene anche gli indicatori `read_only`, `network`, `long`
  e `confirm`.
- Il `32-ia-registro-strumenti.md` **sceglie** quali comandi esporre
  (elenco chiuso, scritto il 2026-10-16) e li usa **senza ridefinirli**.
  L'IA sceglie un comando e ne propone i parametri; i parametri si
  validano come quelli dell'utente; il comando passa dalla stessa coda del
  `40` con `requested_by = ai`; **i numeri del risultato vengono solo dai
  moduli** (regola d'oro n. 1).

### 3.6 Comandi già rieseguibili dei moduli 10–19

- **18 (decisione del proprietario del 2026-10-15):** il `CalculatorCommand`
  del 18 rimandava al "formato del 24". Il formato è ora quello del 05: le
  calcolatrici sono registrate come `calc.evaluate_expression`,
  `calc.convert_units`, `calc.convert_pixel_value`,
  `calc.calculate_coordinates`, `calc.convert_time`, e `run_command` del 18
  diventa un **adattatore** che riceve un comando nel formato del 05 e
  chiama la funzione della calcolatrice (dettagli nel 18 §3).
  **Nessuna dipendenza circolare nel codice:** il formato del 05 è un dato
  semplice (nome, versione, parametri in JSON); il 18 lo legge senza
  importare il registro. I parametri strutturati delle calcolatrici sono
  `record` (D05-4) e l'elenco dei parametri di ogni `calc.*` è nel 18 §3
  (P1, scelta 1); i parametri `layer_ref` (immagine o catalogo) il 05 li
  **risolve prima** e passa all'adattatore gli oggetti dello spazio di
  lavoro (il 18 non conosce lo spazio di lavoro).
- **19:** `PlanetaryCommand`/`run_command` del 19 ha lo stesso schema; il
  suo adattamento al formato del 05 richiede una modifica del 19
  (approvato) non ancora autorizzata (D05-3). Nella prima versione
  dell'interfaccia non si usano comandi del 19 (solo `check_overlay`,
  chiamata dentro i comandi dei livelli).
- Gli altri moduli non cambiano: il 05 chiama le loro funzioni pubbliche.

## 4. Cosa NON fa

- Non calcola nulla: ogni numero viene dalle funzioni dei moduli 10–19.
- Non usa Qt, non crea thread e non disegna: coda, thread di lavoro,
  cronologia visibile e messaggi sono del `40`; il disegno è del `41`.
- Non fa pipeline, script, macro, API Python né compatibilità con i comandi
  di Aladin (`24`, A8).
- Non ha "annulla/ripeti": Aladin non ha "annulla" (A12) e la prima
  versione non lo prevede; si riesegue la cronologia.
- Non salva pixel, contenuti di tabelle, dati della cache né segreti.
- Non decide quali comandi vede l'IA (`32`) e non chiama mai l'IA, nemmeno
  alla riapertura di una sessione.
- Non gestisce tag e segnalibri nella prima versione (D17-3, versioni
  successive).
- Non gestisce la cache (`04`).

## 5. Livello e dipendenze

- **Livello:** 1 (file generale, come `04-cache.md`; codice previsto in
  `src/astrotwo/core/commands.py`, decisione del proprietario del
  2026-10-15).
- **Dipende da:** `04-cache.md`; le funzioni pubbliche dei moduli che i
  comandi chiamano — nella prima versione `10`, `11`, `12`, `13`, `14`,
  `16`, `17`, `18`, `19` (solo `check_overlay`).
- **Usato da:** `40-ui-finestra-principale.md` (coda, cronologia, sessione),
  `41-ui-visualizzatore-cielo.md`, `42-ui-pannello-cataloghi.md`;
  `18-core-calcolatrici.md` (formato dei comandi, solo come dato);
  in futuro `24-analisi-pipeline-riproducibili.md` (pipeline sopra il
  registro); `32-ia-registro-strumenti.md` (schema JSON, validazione,
  `requested_by`, `confirm`), `35-ia-assistente-chat.md` (blocco
  `conversations` della sessione), `44-ui-pannello-ia.md`.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | comando | nome + versione + parametri + `requested_by` | tipi di §3.1, unità esplicite | dall'interfaccia o dall'IA (`32`) |
| in | `CancelToken` | segnale | — | annullamento cooperativo |
| in | file di sessione | JSON UTF-8 | schema versionato | riapertura |
| out | `CommandResult` | struttura | valori con unità, frame, epoca, convenzione; avvisi ed errori del modulo; provenienza | mai un numero senza unità |
| out | `ProgressReport` | struttura | passo n di m, testo | comandi lunghi |
| out | spazio di lavoro | struttura | livelli, vista, griglia, selezioni | letto dall'interfaccia |
| out | cronologia | lista | comandi con esito | pannello Comandi del `40` |
| out | file di sessione | JSON UTF-8 | §3.4 | senza pixel né segreti |
| out | schema per l'IA | JSON Schema 2020-12 | §3.5 | per il `32` |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole (nessun codice). File Python:
`src/astrotwo/core/commands.py`, test in `tests/core/test_commands.py`.

- **`ParameterSpec`**, **`CommandSpec`** — definizione di parametro e di
  comando (§3.1).
- **`Command`** — un comando con nome, versione e parametri completi
  (default risolti); forma JSON con `to_json`/`from_json`.
- **`CommandResult`**, **`ProgressReport`**, **`CancelToken`** — §3.1–§3.2.
- **`CommandRegistry`** — `register(spec)`, `validate(command)`,
  `execute(command, workspace, cancel, progress)` → `CommandResult`,
  `specs()`, `export_schema(names=None)`.
- **`Workspace`** — oggetti e stato della sessione (§3.2); letture per
  identificativo di livello.
- **`CommandHistory`** — cronologia con numeri progressivi e risultati.
- **`Session`** — `save(path)`, `load(path)`, `replay(registry, cancel,
  progress)` con gli stop e gli avvisi di §3.4.

**Comandi della prima versione dell'interfaccia** (nomi da confermare con
le scelte minori di §13; tutti versione 1):

| Comando | Funzioni chiamate | Classe | Indicatori |
|---|---|---|---|
| `image.open` (file, HDU) | 11 `list_image_hdus`, `load_image`; 19 `check_overlay` | session | lungo |
| `image.set_display` (livello, vmin, vmax, funzione di trasferimento, palette, gamma) | 11 `set_display` | session | |
| `hips.set_survey` (identificativo o URL) | 12 `set_survey` (`add_hips` per un URL) | session | rete |
| `catalog.open_file` (file, tabella, formato) | 13 `load_table`, `suggest_position_columns`, `confirm_position_columns` | session | lungo |
| `catalog.load_region` (catalogo, centro, raggio, `max_rows`) | 13 `load_catalog` con regione (rete del 14) | session | rete, lungo |
| `catalog.set_columns` (livello, colonne di posizione, moto proprio, parallasse) | 13 `confirm_position_columns` | session | |
| `catalog.set_style` (livello, forma, colore, dimensione) | 13 `set_plot_rules` | session | |
| `catalog.select` (livello, righe) | — (stato della selezione) | session | |
| `table.sort` (livello, colonna, verso) | — (ordine delle righe mostrate, `42`) | session | |
| `moc.open` (file) | 16 `read_moc`; 19 `check_overlay` | session | |
| `view.go_to` (testo: nome o coordinate) | 10 `resolve_name` o `parse_sexagesimal`/`convert_coordinates`; poi come `view.set_center` | session | rete (nomi) |
| `view.set_center` (posizione) | 10 `make_view_wcs`, `choose_projection` | session | vista |
| `view.set_zoom` (scala) | 10 `make_view_wcs`, `choose_projection` | session | vista |
| `view.set_grid` (visibile, frame) | 10 `choose_grid_spacing`, `compute_grid_lines` | session | vista |
| `view.set_coordinate_display` (frame, formato) | — | session | |
| `layer.set_visible`, `layer.set_opacity`, `layer.move`, `layer.remove` | 19 `check_overlay` (quando un livello torna visibile) | session | |
| `measure.distance` (p1, p2, unità, aggancio al centroide, `box_size`) | 11 `star_centroid` (se aggancio), 10 `pixel_to_sky`, 17 `angular_distance` | session | |
| `view.export_png` (file) | disegno del `41` | application | |
| `cache.clear` (modulo) | 04 `clear` | application | |
| `prefs.set` (chiave, valore) | — | application | |
| `ui.*` (strumento attivo, pannelli, schermo intero) | — | application | |
| `cursor.read` (posizione sullo schermo) | 10 `pixel_to_sky`, `convert_pixel_convention`; 17 `read_pixel` o 12 `pixel_values` | passive | |
| `simbad.pointer` (posizione, raggio) | 10 `pixel_to_sky`, 17 `angular_distance`, 14 `simbad_pointer` | passive | rete |
| `calc.*` (cinque calcolatrici) | 18 (adattatore `run_command`) | session | |
| `coords.resolve_name` (testo del nome) — nuovo, 2026-10-16 | 10 `resolve_name` | session | sola lettura, rete |
| `catalog.search` (livello, espressione, maiuscole sì/no) — nuovo | 13 `search` (grammatica chiusa, D13-1): numero delle righe che soddisfano l'espressione e i primi 50 indici; la selezione non cambia | session | sola lettura |
| `catalog.describe` (livello) — nuovo | metadati della tabella del 13 (colonne con nome, tipo, unità, UCD, descrizione; righe; colonne di posizione; epoca; sorgente con origine e data) | session | sola lettura |
| `catalog.rows` (livello, prima riga, numero di righe ≤ 50, colonne facoltative, ordine della tabella o mostrato) — nuovo | 13 `record_view` per ogni riga | session | sola lettura |
| `layer.list` — nuovo | — (stato dello spazio di lavoro: livelli con identificativo, tipo, nome, visibilità, opacità, ordine, sorgente, righe) | session | sola lettura |

**Indicatore `confirm`** (dal 2026-10-16, regola del `32` §3.5): **sì** per
`image.open`, `catalog.open_file`, `catalog.load_region`, `hips.set_survey`,
`view.go_to` (rete o lungo), `image.set_display`, `catalog.set_columns`,
`catalog.set_style`, `layer.set_visible`, `layer.set_opacity`, `layer.move`,
`layer.remove` (modificano un livello esistente); **no** per tutti gli altri,
compresi i comandi di sola lettura (anche `coords.resolve_name`, che usa la
rete). L'indicatore vale solo quando il comando lo chiede l'IA; quali
comandi l'IA può chiedere è nel `32`.

I comandi di sola lettura sono di classe `session`: entrano in cronologia
(i numeri che l'IA cita vengono da lì, `#n`) e si rieseguono alla
riapertura come gli altri (prima la cache, D05-2).

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `json` (libreria standard) | file di sessione e forma JSON dei comandi | nessuna dipendenza esterna |
| `hashlib` (libreria standard) | SHA-256 dei file | standard, nessuna dipendenza |
| `astropy.units` | validazione e conversione delle unità dei parametri | regola d'oro n. 4, `02` §4 |
| `astropy.coordinates` (tramite il 10) | frame ammessi nei parametri di posizione | elenco dei frame del 10 |
| JSON Schema draft 2020-12 | formato dell'esportazione per il 32 | standard pubblico, leggibile dai provider IA con chiamata di strumenti (A5) |
| ISO 8601 (UTC) | istanti nei risultati e nella sessione | DC1 |

Nessuna nuova dipendenza: la validazione dei file di sessione si fa con il
codice del modulo sui tipi chiusi di §3.1.

## 9. Regole e vincoli

- **Il 05 non calcola:** chiama solo funzioni pubbliche del livello 1 e ne
  riporta i risultati invariati (regola d'oro n. 1, `01` §3).
- **Ogni azione dell'interfaccia è un comando** (regola d'oro n. 6); le
  letture passive seguono D05-1.
- **Determinismo:** stessi comandi, stessi file, stessa versione dell'app →
  stesso stato finale; ordine di esecuzione = ordine di arrivo.
- **Unità sempre esplicite** nei parametri e nei risultati; epoca mai
  assunta (D10-2); pixel in convenzione `numpy` dichiarata (DC7); tempi UTC
  ISO 8601 con scala dichiarata (DC1).
- **Riproducibilità completa del comando registrato:** default risolti,
  numeri esatti nel JSON, file con SHA-256, dati di rete con origine, data
  e impronta.
- **Nessun segreto** nei comandi, nella cronologia, nella sessione o nei
  log (regola d'oro n. 5).
- **Livelli:** il 05 è livello 1 e non importa nulla dei livelli 2–4 né
  dell'interfaccia.
- **Prestazioni:** il costo del registro per comando (validazione e
  registrazione, esclusa la funzione del modulo) va misurato nei test; i
  valori da rispettare per l'interfaccia sono nel `41`.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Nome di comando non registrato | nessuna esecuzione | `COMMAND_UNKNOWN` |
| Parametro di tipo sbagliato, unità non convertibile, fuori intervallo, file inesistente | nessuna esecuzione, messaggio con il parametro | `COMMAND_PARAMETER_INVALID` |
| Riferimento a un livello inesistente o rimosso | nessuna esecuzione | `LAYER_UNKNOWN` |
| Errore di un modulo | risultato `error` con codice e testo del modulo invariati | codice del modulo |
| Annullamento durante l'esecuzione | risultato scartato, stato invariato, esito `cancelled` in cronologia | `COMMAND_CANCELLED` |
| Riapertura con file cambiato | stop dichiarato, stato fino al comando precedente | `SESSION_FILE_CHANGED` |
| Riapertura con file mancante | stop dichiarato | `SESSION_FILE_MISSING` |
| Riapertura: comando prima `ok` ora in errore | stop dichiarato con l'errore del modulo | `SESSION_REPLAY_FAILED` |
| Versione del comando non supportata | stop | `COMMAND_VERSION_UNSUPPORTED` |
| Schema della sessione più recente dell'app | nessuna riesecuzione | `SESSION_SCHEMA_UNSUPPORTED` |
| File di sessione non leggibile o non valido | nessuna riesecuzione | `SESSION_INVALID` |
| Stato finale diverso da quello registrato | avviso con le differenze | `SESSION_STATE_DIFFERS` |
| Dati di rete diversi da quelli registrati | avviso con comando e differenze (impronta, origine e data, righe), la riesecuzione continua (D05-2) | `SESSION_NETWORK_DATA_DIFFERS` |
| Comando dell'interfaccia (`view.export_png`, `prefs.set`, `ui.*`) senza esecuzione collegata dal 40/41 (2026-10-17) | nessuna esecuzione | `COMMAND_UNKNOWN` |
| Lettura sotto il cursore senza vista definita (centro, scala o finestra mancanti) (2026-10-17) | nessuna lettura | `VIEW_UNDEFINED` |
| Punto del cursore fuori dalla proiezione (2026-10-17) | avviso "fuori dal cielo", nessuna coordinata | `OUT_OF_SKY` |
| Catalogo da file senza colonne di posizione dai metadati (2026-10-17) | livello aperto con i suggerimenti del 13; avviso: confermare con `catalog.set_columns` | `POSITION_COLUMNS_REQUIRED` |
| Ordinamento di una colonna non ordinabile (dal 42) | nessun ordinamento | `TABLE_SORT_UNSUPPORTED` |
| Parametro rifiutato dalla funzione del modulo con `TypeError`/`ValueError` (senza codice) (2026-10-17) | risultato `error` con il testo del modulo | `COMMAND_PARAMETER_INVALID` |

## 11. Esposizione all'IA

Non applicabile come strumento: il 05 non è uno strumento per l'IA. È la
**base del `32-ia-registro-strumenti.md`**: lo schema JSON di §3.5 descrive
i comandi che il 32 sceglierà di esporre; i numeri restano dei moduli.

## 12. Test di accettazione

Tutti senza Qt e senza rete (servizi simulati), in `tests/core/test_commands.py`.

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Tipi e unità | comandi con raggio in `arcmin`, in `deg`, senza unità, in `m`; posizione senza epoca e senza motivo; numero puro per un parametro angolare | i primi due validi (unità conservata); gli altri `COMMAND_PARAMETER_INVALID` con il parametro | test di unità |
| T2 | Default risolti | comando registrato senza un parametro facoltativo | il comando registrato contiene il default esplicito | confronto diretto |
| T3 | Schema JSON | `export_schema()` | per ogni comando nome, versione, descrizione inglese, parametri con tipo, unità e intervallo, schema del risultato; JSON valido | controllo strutturale nel test |
| T4 | Salva e riapri | sessione con immagine FITS sintetica, catalogo da file, MOC, vista, griglia, opacità; salvare e riaprire in uno spazio di lavoro vuoto | stesso stato finale (livelli, vista, regolazioni, selezioni); nessun pixel nel file | confronto dello stato; ricerca nel JSON |
| T5 | File cambiato | modificare un byte del FITS dopo il salvataggio, riaprire | `SESSION_FILE_CHANGED` con SHA atteso e trovato; comandi successivi non eseguiti | test di unità |
| T6 | File mancante | rinominare il file, riaprire | `SESSION_FILE_MISSING`, stop | test di unità |
| T7 | Letture passive | 100 `cursor.read` e 1 `view.set_center` | cronologia con il solo `view.set_center` (D05-1) | test di unità |
| T8 | Annullamento | comando lungo simulato annullato a metà | esito `cancelled`, stato invariato, non rieseguito alla riapertura | test di unità |
| T9 | Adattatore del 18 | i comandi di T18 del 18 scritti nel formato del 05 ed eseguiti dal registro | risultati uguali a quelli di `run_command` con `CalculatorCommand` | confronto diretto |
| T10 | Identificativi dei livelli | aprire tre livelli, rimuoverne uno, aprirne un altro; riaprire la sessione | `L1`, `L2`, `L3`, poi `L4` (mai `L2` riusato); stessi identificativi dopo la riapertura | test di unità |
| T11 | Numeri esatti | 10 000 valori `float64` casuali (semina fissa) scritti e riletti dal JSON | identici bit per bit | test di unità |
| T12 | Versioni | sessione con un comando in versione 2 non registrata; schema più recente | `COMMAND_VERSION_UNSUPPORTED`; `SESSION_SCHEMA_UNSUPPORTED` | test di unità |
| T13 | Errori dei moduli invariati | comando che provoca `COORD_OUT_OF_RANGE` del 10 | risultato `error` con codice e testo identici a quelli del 10 | confronto diretto |
| T14 | Stato finale diverso | alterare lo stato finale registrato nel file | `SESSION_STATE_DIFFERS` con la differenza | test di unità |
| T15 | Dati di rete diversi (D05-2) | servizio simulato che alla riapertura risponde con una riga in più; poi cache svuotata e stessa risposta | avviso `SESSION_NETWORK_DATA_DIFFERS` con numero e nome del comando, impronte, origine e data, righe prima e dopo; riesecuzione completata; nessun avviso se la risposta è identica | test di unità |
| T16 | Nessun segreto | sessione completa | nessuna chiave, nessun contenuto del Portachiavi, nessun dato della cache nel file | ispezione del JSON |
| T17 | Cache da più thread (verifica di §3.2) | comandi nel thread di lavoro e letture passive in altri thread che leggono e scrivono la cache del 04 | nessun errore, limite rispettato, nessuna voce parziale | test di unità con cartella temporanea |
| T18 | `requested_by` | comandi da menu, mouse, Riesegui e IA (conversazione, turno, chiamata, profilo, modello); salvare e riaprire | `requested_by` in cronologia e nella sessione; stessi risultati qualunque sia l'origine | test di unità |
| T19 | Comandi di sola lettura | `coords.resolve_name` (SIMBAD simulato), `catalog.search` con espressione valida e non valida, `catalog.describe`, `catalog.rows` con 60 righe chieste, `layer.list` | risultati uguali alle funzioni del 10 e del 13 chiamate nel test; `EXPRESSION_INVALID` del 13; `catalog.rows` oltre 50 → `COMMAND_PARAMETER_INVALID`; selezione e spazio di lavoro invariati | confronto diretto |
| T20 | Indicatore `confirm` nello schema | `export_schema()` | `confirm` come nell'elenco di §7; `read_only` per i comandi nuovi | test di unità |
| T22 | Tipo `record` e forme JSON (D05-4) | comando con un `record` valido, con un campo in più, con un campo mancante senza default, con un campo `quantity` in unità non convertibile; forma JSON di ogni tipo scritta e riletta; `export_schema()` | il primo valido (default dei campi risolti); gli altri `COMMAND_PARAMETER_INVALID` con il nome del campo (`parametro.campo`); forme di §3.1 identiche dopo la rilettura; nello schema `object` con `properties`, `required`, `additionalProperties: false` | test di unità |
| T21 | Conversazioni nella sessione | sessione con e senza il blocco `conversations`; riapertura con un provider simulato che fallisce se chiamato | blocco presente solo se chiesto, senza cartelle nei nomi dei file; riesecuzione identica nei due casi, nessuna chiamata al provider | test di unità |

## 13. Decisioni aperte

Nessuna decisione dei Gruppi 1 e 2 aperta (dal 2026-10-15).

- **D05-1 — Classi dei comandi e letture passive: DECISA il 2026-10-15
  (decisione del proprietario, opzione proposta).** Tre classi: `session`
  (registrati in cronologia e rieseguiti alla riapertura), `passive`
  (letture causate dal solo passaggio del mouse: eseguite tramite il
  registro, con risultato strutturato, ma **non** registrate in cronologia
  né nella sessione; quelle senza rete nel thread principale, quelle con
  rete — il puntatore Simbad — nel gruppo di thread dei tile del `41`,
  D41-1), `application` (preferenze, pannelli, esportazioni, svuotamento
  della cache: registrati in cronologia ma **non** rieseguiti alla
  riapertura). **Motivazione:** la cronologia resta leggibile, le letture
  passano comunque dal registro (stessa strada dell'IA) e il cursore resta
  entro 50 ms anche con la coda occupata. Applicata in §3.1, §3.2, §7.
- **D05-2 — Dati di rete diversi alla riapertura: DECISA il 2026-10-15
  (decisione del proprietario).** **Avviso senza fermarsi.** Ogni comando
  che usa la rete salva nel risultato, e quindi nella sessione,
  un'**impronta dei suoi risultati di rete** (§3.4): SHA-256 dei byte
  ricevuti dal servizio (o della copia in cache usata), con origine, data,
  "dalla cache sì/no" e, per le tabelle, il numero di righe. Alla
  riapertura il comando si riesegue e l'impronta si ricalcola; se è
  diversa, avviso `SESSION_NETWORK_DATA_DIFFERS` che dice **quale comando**
  (numero e nome) e **cosa è cambiato** (impronta prima e dopo, origine e
  data prima e dopo, righe prima e dopo per le tabelle); la riesecuzione
  continua. Applicata in §3.1, §3.4, §10, §12 (T15).
- **D05-3 — Adattatore del 19: RIMANDATA il 2026-10-15** (decisione del
  proprietario, come proposto: si fa quando l'interfaccia userà i dati
  planetari). `PlanetaryCommand`/`run_command` del 19
  segue lo schema del 18. Per usarlo dal registro serve una modifica del 19
  (approvato), non compresa nell'autorizzazione del 2026-10-15.
  **Raccomandazione:** stesso adattatore del 18, da autorizzare quando
  l'interfaccia userà i dati planetari (non nella prima versione). Gruppo 3.
- **D05-4 — Forma JSON dei valori dei parametri e parametri strutturati:
  DECISA il 2026-10-17 (decisione del proprietario, opzione a).** Nuovo tipo
  `record` (campi tipizzati, con unità dove serve, validati dal 05 come gli
  altri parametri ed esportati nello schema JSON per il 32) e forma JSON di
  ogni tipo in §3.1; elenco dei parametri dei `calc.*` nel 18. Applicata in
  §3.1, §3.6, §12 (T22). Testo della domanda com'era (aperta il 2026-10-16
  da Claude Code durante l'allineamento del 18, Gruppo 1: tocca il 05 e il
  18): §3.1 elenca i tipi dei parametri ma non dice
  **come si scrive in JSON il valore** di ciascuno (`quantity`,
  `sky_position`, `pixel_position`, `file`, `layer_ref`, …), e l'elenco
  chiuso **non ha un tipo per una struttura con campi**. Le calcolatrici del
  18 hanno parametri strutturati (`CoordinateInput`, `CoordinateTarget`,
  `ProperMotion`, `DisplaySettings`) e uno che è un livello (l'immagine di
  `convert_pixel_value`): senza questa definizione l'adattatore
  `run_command` del 18 dovrebbe inventare il formato del 05. **Opzioni:**
  (a) aggiungere il tipo **`record`** (struttura con campi tipizzati
  dichiarati nella definizione, ricorsiva sugli stessi tipi) e scrivere in
  §3.1 la forma JSON di ogni tipo: `quantity` = `{"value": …, "unit":
  "…"}`; `sky_position` = `{"lon": quantity, "lat": quantity, "frame":
  "…", "equinox": …|null, "obstime": …|null, "epoch": …|null,
  "epoch_reason": "…"}`; `pixel_position` = `{"x": …, "y": …,
  "convention": "numpy"}`; `layer_ref` = `"L3"`; `record` = oggetto con i
  campi; (b) **appiattire** i parametri strutturati delle calcolatrici in
  parametri semplici (es. `position_lon`, `position_lat`,
  `position_frame`, …), senza nuovo tipo. **Raccomandazione: (a)**, che
  conserva la forma delle funzioni del 18 e serve anche ai comandi futuri
  (es. regole di disegno, `catalog.set_style`); l'adattatore del 18 riceve i
  livelli già risolti dal 05 (il 18 non conosce lo spazio di lavoro). Ferma
  solo l'adattatore del 18 e i comandi `calc.*` del 05.
- **Scelte minori: CONFERMATE dal proprietario il 2026-10-15:** (1) estensione `.astrotwo.json` del
  file di sessione; (2) nomi dei comandi della tabella di §7; (3)
  identificativi dei livelli `L<n>`; (4) gesto che cambia centro e scala
  registrato come `view.set_zoom` seguito da `view.set_center`; (5) un
  comando annullato resta in cronologia con l'esito `cancelled`.
- **Proposta della fase 1 sull'IA, approvata dal proprietario il
  2026-10-16:** campo `requested_by`, indicatore `confirm`, cinque comandi
  di sola lettura per l'assistente (`coords.resolve_name`,
  `catalog.search`, `catalog.describe`, `catalog.rows`, `layer.list`) e
  blocco facoltativo `conversations` della sessione; applicata in §3.1,
  §3.2, §3.4, §3.5, §7, §12 (T18–T21). **Scelte minori: CONFERMATE dal proprietario il 2026-10-16 (come raccomandate):** (1)
  valori di `requested_by` (`menu`, `keyboard`, `mouse`, `history`,
  `session`, `ai`); (2) comandi di sola lettura in classe `session`
  (rieseguiti alla riapertura).
- **Scelte minori della parte 1 (codice del 05, 2026-10-17): DA
  CONFERMARE dal proprietario.** Dettagli che la specifica lasciava aperti,
  scelti scrivendo `src/astrotwo/core/commands.py`:
  1. **Tipo `time`** nell'elenco chiuso (precisazione di D05-4): la forma
     JSON "tempo" del §3.1 è il tipo dei campi di epoca (`epoch`,
     `equinox`, `obstime`), anche dei `calc.*`.
  2. **Vista:** `view.set_center`, `view.set_zoom` e `view.go_to` hanno il
     parametro facoltativo `window` (`record` larghezza × altezza in pixel
     fisici; senza: quella dello stato), così la geometria del 10 è
     ricostruibile dalla cronologia. Scala = angolo per pixel della
     finestra. Con un'immagine con WCS la base è il suo WCS; senza, base
     creata in ICRS che parte da `TAN` e segue `choose_projection` con le
     soglie fisse 33° (da `TAN`) e 27° (da `AIT`) del 41 §3.3, ricreata con
     il punto di tangenza al centro quando la proiezione cambia o il punto
     esce dalla finestra. La griglia visibile si ricalcola a ogni comando di
     vista.
  3. **"Vai a":** coppia decimale = gradi; coppia sessagesimale `h:m:s
     ±d:m:s` o `h m s ±d m s` = longitudine in ore nei frame equatoriali;
     frame delle coordinate mostrate; epoca non nota (non assunta); il
     resto è un nome per `resolve_name`.
  4. **Impronta dei risultati di rete (D05-2):** i moduli 10–14 non
     restituiscono i byte ricevuti, quindi l'impronta è lo SHA-256 del
     **contenuto restituito dal modulo** (colonne, tipi, unità, valori e
     maschere della tabella; posizione del nome risolto; proprietà del
     HiPS), con origine, data, "dalla cache" e righe. Rileva gli stessi
     cambiamenti dei dati.
  5. **Riapertura:** i comandi rieseguiti conservano il loro
     `requested_by` (chi li aveva chiesti); `Session.load(path, registry)`
     legge il file, `replay` riesegue.
  6. **Comandi dell'interfaccia:** `view.export_png`, `prefs.set`,
     `ui.set_tool`, `ui.set_panel`, `ui.set_fullscreen`,
     `ui.set_appearance` sono definiti qui (classe `application`) e
     l'esecuzione la collega il 40/41 con `CommandRegistry.bind`; senza →
     `COMMAND_UNKNOWN`.
  7. **Livelli:** `image.open` sostituisce l'immagine aperta (al più una,
     41 §3.5) e scrive nel comando registrato i limiti scelti da
     `suggest_display_limits` (D41-3); `hips.set_survey` sostituisce lo
     sfondo e lo mette in fondo all'ordine; `measure.distance` misura tra due
     pixel di un'immagine con WCS e crea un livello `measure`.
  8. **Firma:** `execute` restituisce il `CommandResult` (§7); `run`
     restituisce anche il comando registrato (con i valori scelti dal
     modulo) per la cronologia; `Session.run` esegue e registra.
- **Accesso alla cache del 04 da più thread (§3.2, T17): verificato il
  2026-10-16.** La prima prova è fallita (orfani cancellati durante le
  scritture di altri thread); corretto nel 04 con D04 (orfani solo oltre 10
  minuti, pulizia una volta per processo); T17 è nei test della cache
  (`tests/core/test_cache.py`, T9 del 04).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-15 | Claude Code | Creazione del file (stato: bozza) su decisione del proprietario del 2026-10-15 (AM1 accettata: modulo generale di livello 1, codice previsto in `src/astrotwo/core/commands.py`): comandi con nome, versione, parametri tipizzati con unità, descrizioni EN/IT, risultato strutturato, indicatori; registro senza Qt con annullamento cooperativo e avanzamento; spazio di lavoro immutabile; gesti registrati a fine gesto dopo 300 ms fermo; sessione JSON senza pixel, riapertura = riesecuzione con stop se lo SHA di un file è cambiato; schema JSON per il 32; `run_command` del 18 come adattatore. Verifica della cache del 04 da più thread prima del codice. Nuove decisioni D05-1, D05-2, D05-3. |
| 2026-10-15 | Claude Code | **Decisioni del proprietario del 2026-10-15:** D05-1 decisa (tre classi `session`/`passive`/`application`); D05-2 decisa (avviso senza fermarsi; impronta dei risultati di rete di ogni comando salvata nella sessione, l'avviso dice quale comando e cosa è cambiato; §3.1, §3.4, §10, T15); D05-3 rimandata; scelte minori confermate. Nessuna decisione dei Gruppi 1 e 2 resta aperta in questo file. |
| 2026-10-16 | Claude Code | **Proposta della fase 1 sull'IA approvata dal proprietario il 2026-10-16** (autorizzazione a modificare la bozza come proposto): campo `requested_by` nel comando, nella cronologia e nella sessione; indicatore `confirm` con il suo elenco; nuovi comandi di sola lettura `coords.resolve_name`, `catalog.search`, `catalog.describe`, `catalog.rows` (al più 50 righe), `layer.list`; blocco facoltativo `conversations` della sessione (solo su richiesta, mai riletto per rieseguire); riesecuzione dei comandi dell'IA senza chiamare l'IA; schema con gli indicatori per il `32`; test T18–T21. |
| 2026-10-16 | Claude Code | Scelte minori **confermate dal proprietario il 2026-10-16** come raccomandate (§13). **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-16. |
| 2026-10-16 | Claude Code | Verifica "cache del 04 da più thread" (§3.2, T17) chiusa: fallita alla prima prova, corretta nel 04 con D04 (decisione del proprietario del 2026-10-16); T17 nella suite come T9 del 04. Stato `approvato` invariato. |
| 2026-10-16 | Claude Code | Nuova decisione aperta **D05-4** (Gruppo 1): forma JSON dei valori dei parametri e tipo per i parametri strutturati, trovata scrivendo l'adattatore del 18; raccomandazione (a) tipo `record` e forme JSON in §3.1. Ferma solo l'adattatore del 18 e i comandi `calc.*`. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **D05-4 decisa dal proprietario il 2026-10-17** (opzione a; autorizzazione esplicita a modificare il file approvato): nuovo tipo `record` con campi tipizzati validati ed esportati nello schema; forma JSON di ogni tipo in §3.1 (tempo con scala sempre scritta, file con SHA-256 e dimensione, `null` per i facoltativi senza default); valori di pixel come `number` nell'unità dell'immagine; §3.6 con i `layer_ref` risolti dal 05 prima dell'adattatore del 18; T22. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **Codice della parte 1 della v1** (divisione approvata dal proprietario il 2026-10-17): `src/astrotwo/core/commands.py` (39 comandi della tabella di §7, registro, spazio di lavoro immutabile, cronologia, sessione con riapertura, schema JSON) e `tests/core/test_commands.py` (T1–T22 più vista, misura, comandi collegati e costo del registro, 26 test). Tipo `time` nell'elenco chiuso (precisazione di D05-4); nuovi casi in §10 (`VIEW_UNDEFINED`, `OUT_OF_SKY`, `POSITION_COLUMNS_REQUIRED`, comandi non collegati); scelte minori della parte 1 in §13, da confermare. Stato `approvato` invariato. |
