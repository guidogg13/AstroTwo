# 40-ui-finestra-principale.md — finestra principale, menu, barra di stato, preferenze

**Stato:** approvato

## 2. Scopo

Dare all'utente una finestra unica da cui aprire dati, comandare la vista
del cielo, vedere la cronologia dei comandi e i messaggi dei moduli e
regolare le preferenze essenziali, facendo passare ogni azione dal registro
dei comandi (`05`) senza mai bloccare l'interfaccia.

## 3. Cosa fa

### 3.1 Perimetro della prima versione (v1)

Perimetro approvato dal proprietario il 2026-10-15. La v1 dell'interfaccia
(40, 41, 42 minimo) usa **solo il livello 1**; **dal 2026-10-16** (proposta
della fase 1 sull'IA approvata) la v1 comprende anche il **pannello
dell'assistente (44)**, che usa il livello 3 (30, 31, 32, 34, 35) sopra i
comandi del livello 1. Senza assistente la finestra funziona identica
(regola d'oro n. 7).

- **In v1:** menu, barra di stato, campo "Vai a", preferenze essenziali,
  apertura di file (immagine FITS, catalogo, MOC) e di sessioni, pannello
  Comandi (cronologia visibile e rieseguibile), pannello Messaggi, schermo
  intero (A10), coda dei comandi in un thread di lavoro con avanzamento e
  Annulla, **pannello dell'assistente (44)** nell'area a destra,
  impostazioni dell'assistente nelle preferenze, colonna "chi" nella
  cronologia.
- **Fuori dalla v1** (versioni successive): segnalibri e storico delle
  posizioni (A12, H13, H16), console degli script e modalità demo o guida
  (H13), avvio tramite URL (H18, D40-2), finestre delle calcolatrici (18),
  preferenze non essenziali (cifre di visualizzazione DC3, timeout CA1,
  limiti di memoria e delle tabelle, dati planetari D19-5, server
  predefiniti, tema), pannello analisi (43), viste
  multiple (45). Finché non hanno un'interfaccia valgono i default dei
  moduli. (Il pannello IA, 44, è entrato nella v1 il 2026-10-16.)

### 3.2 Disposizione

- Al centro il **visualizzatore del cielo** (`41`).
- Pannelli agganciabili (spostabili e richiudibili, comportamento standard
  di Qt): **Livelli** (del `41`), **Tabella** (`42`), **Comandi** e
  **Messaggi** (di questo modulo).
- **Pannello dell'assistente (44, dal 2026-10-16):** nell'area agganciabile
  a destra, larga 380–420 pt, richiudibile, con un pulsante nella barra
  degli strumenti e la voce di menu **Assistant** attiva (contenuto e
  comportamento nel `44`). Senza profilo, chiave o consenso il pannello
  dice perché l'assistente non è disponibile; il resto della finestra non
  cambia.
- Geometria della finestra e dei pannelli salvata nelle impostazioni
  dell'app (non nella sessione).

### 3.3 Menu

Testi in inglese nel codice, tradotti in italiano (A9, §3.9). Ogni voce
che agisce sui dati produce un comando del `05` (nome tra parentesi).

- **File:** Open image… (`image.open`); Open catalog… (`catalog.open_file`);
  Open MOC… (`moc.open`); Open session… / Save session… (sessione del
  `05`, §3.8); Export view as PNG… (`view.export_png`, disegno del `41`);
  Quit.
- **View:** Go to… (porta il fuoco sul campo "Vai a"); Coordinate grid
  (`view.set_grid`, con frame ICRS o galattico); Coordinates shown (ICRS
  sessagesimale, ICRS decimale, galattico: `view.set_coordinate_display`);
  Full screen (A10, `ui.set_fullscreen`); Night mode (modalità notte rossa,
  `ui.set_appearance`, §3.11; ⌃⌘N, D40-4).
- **Data:** HiPS survey… (finestra con un campo di ricerca sulla copia
  locale delle collezioni, `CollectionIndex.filter` del 12, e un campo per
  identificativo o URL: `hips.set_survey`); Catalog in view… (finestra con
  l'identificativo del catalogo come lo accetta `load_catalog` del 13 —
  VizieR, Simbad, Gaia DR3 dall'elenco dei server del 14, D14-4 — e
  `max_rows` con il default 100 000 di D14-5; centro e raggio sono quelli
  della vista calcolati dal 10: `catalog.load_region`).
- **Tools:** Distance (strumento di misura del `41`); Simbad pointer
  (puntatore del `41`). L'attivazione è `ui.set_tool`.
- **Window:** mostra o nasconde i pannelli.
- **Help:** About AstroTwo (versione SemVer, DC4, e testo di
  `THIRD_PARTY_LICENSES`).
- **Assistant** (voce nel menu Window e pulsante nella barra degli
  strumenti, ⌃⌘A): mostra o nasconde il pannello del `44` (`ui.*`, classe
  `application`).
- Scorciatoie standard di macOS (⌘O apri, ⌘S salva sessione, ⌘Q esci,
  ⌃⌘F schermo intero; ⌃⌘N modalità notte, D40-4).

### 3.4 Campo "Vai a" (A2, A3)

Accetta un nome di oggetto o una coppia di coordinate; produce
`view.go_to` con il testo scritto: il `05` lo interpreta con il 10
(`resolve_name` per un nome, `parse_sexagesimal`/`convert_coordinates` per
le coordinate) e centra la vista. Il risultato mostra la fonte (SIMBAD,
"dalla cache" con origine e data, epoca J2000 dichiarata). Nome non
trovato o rete assente: messaggio del 10 nel pannello Messaggi.

### 3.5 Barra di stato

- **Sotto il mouse:** coordinate nel sistema scelto, valore del pixel con
  unità e coordinate pixel in convenzione FITS (DC7), dal risultato di
  `cursor.read` (`41`); testo "fuori dal cielo" o "nessun dato" quando il
  modulo non dà un valore.
- **Attività di rete:** numero di comandi di rete in corso e di tile HiPS
  in arrivo.
- **Comando in corso:** nome, avanzamento (passo n di m o indeterminato) e
  pulsante **Annulla** per ogni comando lungo (regola del proprietario del
  2026-10-15).

### 3.6 Pannello Comandi (cronologia visibile)

- Una riga per comando della cronologia del `05`: numero, ora (UTC),
  **chi** (dal `requested_by` del `05`: "Utente" per menu, tastiera, mouse
  e Riesegui; "IA" per i comandi chiesti dall'assistente; "Sessione" per
  la riapertura), nome, parametri in breve, esito (ok, errore, annullato),
  numero di avvisi. Filtro per classe (`session` di default, `application`
  a richiesta; D05-1) e per chi (tutti di default).
- Per i comandi dell'IA il dettaglio mostra anche conversazione, turno,
  profilo e modello, e se l'utente ha confermato il comando (`32` §3.5).
- Selezionando una riga: parametri completi, risultato, avvisi, provenienza
  (origine e data dei dati di rete o della cache).
- **Riesegui** (uno o più comandi selezionati): li rimette in coda come
  nuovi comandi, con nuovi numeri. **Copia come JSON**: la forma JSON del
  comando (`05`).

### 3.7 Pannello Messaggi ed errori

- Ogni errore e avviso dei moduli compare con **codice e testo del
  modulo, invariati**, e il numero del comando che lo ha prodotto; errori
  in rosso.
- Errore di un comando: segnalazione non bloccante (voce nel pannello
  Messaggi e riga rossa nella cronologia). **Finestra modale solo se
  l'azione non può proseguire** (file illeggibile, sessione fermata dal
  `05` per un file cambiato o mancante).
- **Lingua dei messaggi dei moduli (D40-1, decisa il 2026-10-15):** nella
  v1 si mostrano **codice e testo del modulo invariati**, anche con
  l'interfaccia in inglese; la traduzione dei messaggi dei moduli in
  inglese è la decisione aperta D40-3 (Gruppo 3).

### 3.8 Coda dei comandi e thread

Architettura approvata dal proprietario il 2026-10-15:

- **Una coda dei comandi in un thread di lavoro** (`QThread`): i comandi
  di classe `session` e `application` si eseguono con il registro del `05`,
  uno alla volta, nell'ordine di arrivo.
- **I risultati tornano al thread principale con i segnali di Qt**
  (connessioni in coda); il thread principale non esegue mai un comando
  della coda.
- Le letture passive senza rete (`cursor.read`) si eseguono con il
  registro nel thread principale perché durano pochi millisecondi; quelle
  con rete vanno nel gruppo di thread del `41` (D05-1, D41-1).
- **Annulla:** imposta il `CancelToken` del `05` (annullamento cooperativo:
  il risultato si scarta, lo stato non cambia).
- **Uscita con comandi in corso:** richiesta di conferma; se confermata,
  annullamento e attesa del ritorno della funzione in corso entro i
  timeout di rete del `04`.
- **Comandi dell'assistente:** entrano nella **stessa coda** con
  `requested_by = ai` (`32` §3.5); l'assistente (`35`) gira in un thread
  proprio e aspetta il risultato con i segnali di Qt; Annulla nella barra di
  stato e Stop del `44` impostano lo stesso `CancelToken` del comando.
- **Sessione:** Open session riapre con la riesecuzione del `05` (comando
  lungo, con avanzamento e Annulla); gli stop del `05` si mostrano in una
  finestra modale. Prima di aprire una sessione o di uscire con comandi non
  salvati, richiesta di conferma. **Save session** ha la casella "Includi il
  testo delle conversazioni" (spenta di default, `35` §3.9).

### 3.9 Lingua (A9, decisa il 2026-10-15)

- **Testi dell'interfaccia in inglese nel codice**, marcati con `tr()`.
- **Traduzione italiana nostra** con Qt Linguist (file `.ts` nel progetto,
  compilati in `.qm`).
- **Traduzioni di Qt** per i dialoghi standard (apertura file, conferme).
- **Lingua presa dal sistema** (`QLocale`), cambiabile nelle preferenze
  (inglese o italiano); il cambio vale al riavvio dell'app.
- **Numeri scientifici sempre con il punto decimale, in ogni lingua**:
  l'interfaccia non usa le regole numeriche della lingua per i valori
  scientifici (coordinate, misure, valori dei pixel, parametri), così i
  valori si copiano e si incollano senza ambiguità.

### 3.10 Preferenze essenziali

Finestra delle preferenze con cinque voci e, dal 2026-10-16, la sezione
**Assistant** (profili, modello, modalità rigorosa, limiti, prezzo
facoltativo: tabella del `44` §3.6; la chiave va **solo** nel Portachiavi
tramite il `31`, mai in `QSettings`); ogni modifica è un comando
`prefs.set` (classe `application`). Salvate nelle impostazioni dell'app di
macOS con `QSettings` (scelta minore 1), mai nella sessione.

| Preferenza | Valori | Effetto |
|---|---|---|
| Lingua | sistema, inglese, italiano | al riavvio (§3.9) |
| Limite della cache | byte, default 5 × 10⁹ (CA2 del `04`) | mostra spazio usato per modulo e totale (`usage`) e il pulsante "svuota" (`cache.clear`) |
| Sistema di coordinate mostrato | ICRS sessagesimale, ICRS decimale, galattico | valore iniziale di `view.set_coordinate_display` |
| Survey HiPS predefinito | identificativo HiPS; default `CDS/P/DSS2/color` (D12-3) | survey attivato all'avvio con `hips.set_survey` |
| Aspetto | sistema (default), scuro, chiaro, notte rossa | §3.11; cambia subito, senza riavvio |

### 3.11 Linee guida visive

Decisione del proprietario del 2026-10-15. **Valgono per 40, 41, 42 e per
tutte le interfacce future** (43, 44, 45 e successive): un modulo di
interfaccia che se ne discosta lo dichiara nel suo §13 come decisione
aperta.

- **Aspetto generale:** moderno e pulito, coerente con macOS (controlli
  nativi di Qt con lo stile di macOS, finestra con barra degli strumenti
  sottile unita alla barra del titolo, menu nella barra dei menu di
  sistema). **Nessun valore, colore, icona o stile preso da Aladin**
  (regola d'oro n. 8).
- **Temi:**
  - l'aspetto **segue la modalità chiaro/scuro del sistema** (preferenza
    "Aspetto" = sistema, default); il **tema scuro è quello di
    riferimento**: è il tema progettato per primo, mostrato nei mockup e
    usato quando il sistema non dichiara una preferenza; il tema chiaro ne
    è la versione con gli stessi elementi;
  - **modalità notte rossa** per l'osservazione al telescopio, scelta
    dall'utente (menu View o preferenza "Aspetto"): fondo nero, testi,
    linee, icone e accento solo in toni di rosso a bassa luminosità, nessun
    bianco né blu; anche il cielo si disegna in rosso (luminosità del piano
    di presentazione portata su una scala di rossi: trasformazione di
    disegno del `41`, i valori non cambiano); i colori dei cataloghi
    diventano toni di rosso e i cataloghi si distinguono per forma del
    simbolo. È un comando `ui.set_appearance` (classe `application`).
- **Disposizione:** **il cielo al centro**, con il massimo dello spazio;
  **pannelli laterali e inferiori richiudibili** (Livelli a sinistra,
  spazio dell'IA a destra, Tabella, Comandi e Messaggi in basso); **barre
  sottili** (barra degli strumenti e barra di stato di una riga).
- **Carattere:** il **carattere di sistema** di macOS (nessun carattere
  incluso nell'app); cifre a larghezza fissa (tabulari) per coordinate e
  valori nelle barre e nelle tabelle, così le colonne restano allineate
  (supporto in Qt da verificare prima del codice); dimensioni del testo che
  seguono le impostazioni di accessibilità del sistema.
- **Colore:** **un solo colore di accento** per selezione, elementi attivi e
  pulsante predefinito (nel tema scuro e chiaro un blu; in modalità notte
  il rosso dell'accento); errori nel colore di errore del sistema. I
  **colori dei cataloghi** (tavolozza fissa del `41`, scelta minore 4) sono
  la tavolozza di **Okabe e Ito (2008)**, pubblicata per essere distinguibile
  anche da chi non vede alcuni colori; sono colori dei dati, non accenti.
- **Spaziature:** griglia regolare di **4 punti** (margini e distanze
  multipli di 4: 4, 8, 12, 16, 24), stesse altezze di riga in tutti i
  pannelli.
- **Icone:** da una sola raccolta con licenza libera. **Proposta: Lucide**
  (icone a linea in SVG, licenza ISC, permissiva; raccolta ampia e
  coerente, adatta alle barre sottili); alternative Phosphor (MIT) e Tabler
  Icons (MIT). **Licenza verificata il 2026-10-17** (pacchetto
  `lucide-static` 1.59.0: ISC, più MIT del progetto Feather per le icone
  derivate elencate nel file) e scritta in `THIRD_PARTY_LICENSES` con il
  testo integrale; icone copiate senza modifiche in `src/astrotwo/ui/icons/`
  con il file `LICENSE`. Le icone si disegnano con `QtSvg` di PySide6 e
  prendono il colore del tema (anche il rosso della modalità notte).
- **Numeri:** sempre con il punto decimale (§3.9) e con le cifre di DC3;
  coordinate scritte con la funzione del 10 (D41-2).
- **Mockup di riferimento:** `mdfiles/mockup/finestra-principale.html` (tema
  scuro) e `mdfiles/mockup/finestra-principale-notte.html` (modalità notte
  rossa): pagine HTML statiche con valori fittizi, solo immagine di
  riferimento, non codice dell'app.

## 4. Cosa NON fa

- Non calcola nulla: coordinate, valori, misure e testi vengono dai moduli
  attraverso il `05` (regola d'oro n. 1, `01` §3).
- Non disegna il cielo né gestisce i livelli (`41`), non mostra tabelle
  (`42`).
- Non riscrive né traduce i messaggi dei moduli (D40-1).
- Non ha "annulla/ripeti" (A12): si riesegue la cronologia.
- Non contiene il pannello dell'assistente (è del `44`, che il 40 ospita)
  e non chiama l'IA.
- Non conserva chiavi API (regola d'oro n. 5).
- Non salva la sessione da sé: formato e riesecuzione sono del `05`.

## 5. Livello e dipendenze

- **Livello:** interfaccia (attraversa i livelli senza logica scientifica,
  `01` §3); nella v1 usa solo il livello 1.
- **Dipende da:** `05-comandi-sessione.md` (registro, cronologia,
  sessione), `04-cache.md` (uso e svuotamento della cache, tramite
  comandi), `10-core-coordinate-wcs.md` (campo "Vai a", tramite comandi),
  `12-core-hips.md` (collezioni e survey, tramite comandi),
  `13-core-cataloghi.md` e `14-core-protocolli-vo.md` (catalogo nel campo,
  tramite comandi), `41-ui-visualizzatore-cielo.md`,
  `42-ui-pannello-cataloghi.md`, `44-ui-pannello-ia.md` (pannello
  dell'assistente, dal 2026-10-16), `35-ia-assistente-chat.md` (comandi
  dell'IA nella coda); libreria PySide6.
- **Usato da:** `44-ui-pannello-ia.md` (area a destra, preferenze, pannello
  Comandi); in futuro `43`, `45` si agganciano a questa finestra.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | azioni dell'utente | menu, tastiera, campo "Vai a", preferenze | — | diventano comandi del `05` |
| in | risultati dei comandi | `CommandResult` del `05` | valori con unità, avvisi ed errori del modulo | dal thread di lavoro con i segnali di Qt |
| in | `ProgressReport` | struttura | passo n di m | barra di stato |
| out | comandi | `Command` del `05` | parametri tipizzati con unità | in coda |
| out | preferenze | impostazioni dell'app (`QSettings`) | chiave → valore | non nella sessione |
| out | file di sessione | JSON del `05` | `.astrotwo.json` | tramite il `05` |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole. File Python
`src/astrotwo/ui/main_window.py`; traduzioni in `src/astrotwo/ui/i18n/`
(`astrotwo_it.ts`, compilato in `.qm`); test in `tests/ui/test_main_window.py`.

- **`MainWindow`** — finestra, menu, pannelli agganciabili, area riservata
  al pannello IA; crea il registro e lo spazio di lavoro del `05`.
- **`CommandRunner`** — oggetto nel thread di lavoro: riceve i comandi in
  coda, li esegue con il `05`, emette i segnali `started`, `progress`,
  `finished` (risultato) e gestisce Annulla.
- **`StatusBar`** — coordinate e valore sotto il mouse, attività di rete,
  comando in corso con avanzamento e Annulla.
- **`HistoryPanel`** — cronologia con dettagli, Riesegui e Copia come JSON.
- **`MessagesPanel`** — errori e avvisi con codice, testo e numero del
  comando.
- **`GoToField`** — campo "Vai a".
- **`PreferencesDialog`** — le cinque preferenze di §3.10.
- **`load_translations(language)`** — carica la traduzione nostra e quella
  di Qt; senza file di traduzione resta l'inglese con un avviso.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| **PySide6** (Qt 6: QtWidgets, QtCore) | finestra, menu, pannelli, thread (`QThread`), segnali, `QSettings`, `QLocale`, `QTranslator` | decisione A1; **licenza LGPL-3 (binding e Qt), registrata il 2026-10-15 per A11 e per il `60`** (obblighi LGPL nel `.dmg`, come per WCSLIB); testo da verificare prima del codice e da aggiungere a `THIRD_PARTY_LICENSES` |
| Qt Linguist (`pyside6-lupdate`, `pyside6-lrelease`) | file di traduzione `.ts`/`.qm` | strumento standard di Qt (A9) |
| Traduzioni di Qt (`qtbase_it`) | dialoghi standard in italiano | distribuite con Qt |
| **pytest-qt** | test dell'interfaccia | decisione del proprietario del 2026-10-15; **licenza da verificare** e da aggiungere a `THIRD_PARTY_LICENSES` |
| PySide6 `QtSvg`; raccolta di icone **Lucide** (`lucide-static` 1.59.0, ISC; MIT di Feather per le icone derivate) | icone dell'interfaccia (§3.11) | linee guida visive del 2026-10-15; licenza verificata il 2026-10-17 e scritta in `THIRD_PARTY_LICENSES` |
| `QStyleHints.colorScheme` di Qt | modalità chiaro/scuro del sistema | segue il sistema senza codice proprio; disponibilità nella versione di PySide6 da verificare |

## 9. Regole e vincoli

- **L'interfaccia non calcola** e mostra solo valori e testi dei moduli.
- **Ogni azione passa dal `05`** (regola d'oro n. 6), con le classi di
  D05-1.
- **Il thread principale non resta mai fermo più di 100 ms** durante rete o
  calcoli (obiettivo del `41`, misurato con una sonda di latenza).
- **Finestra pronta in ≤ 3 s senza rete** (obiettivo del `41`, test `perf`).
- **Punto decimale** per tutti i numeri scientifici in ogni lingua (§3.9).
- **Cifre di visualizzazione:** DC3 (RA 0.01 s, Dec 0.1″, magnitudini 3
  decimali); il valore pieno resta copiabile (`02` §6).
- **Nessun segreto** in preferenze, cronologia, log o sessione.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Uscita con comandi in corso | conferma; annullamento e attesa del ritorno entro i timeout di rete | — |
| Sessione fermata dal `05` (file cambiato o mancante) | finestra modale con il messaggio del `05`; stato fino all'ultimo comando rieseguito | `SESSION_FILE_CHANGED`, `SESSION_FILE_MISSING` |
| File da aprire illeggibile | finestra modale con il messaggio del modulo | codice del modulo (es. dell'11) |
| Rete assente | errore del modulo nel pannello Messaggi; l'interfaccia resta usabile | `NET_TIMEOUT` (del modulo) |
| Cache non disponibile | avviso nel pannello Messaggi; si continua senza cache | `CACHE_UNAVAILABLE` |
| File di traduzione mancante | interfaccia in inglese, avviso | `UI_TRANSLATION_MISSING` |
| Preferenza con valore non valido (es. limite della cache negativo) | rifiuto, valore precedente | `PREFERENCE_INVALID` |
| Comando lungo annullato | voce "annullato" nella cronologia, stato invariato | `COMMAND_CANCELLED` |

## 11. Esposizione all'IA

Non applicabile: è interfaccia. L'IA userà i comandi del `05` attraverso il
`32`; questo modulo riserva solo lo spazio per il pannello `44`.

## 12. Test di accettazione

Con **pytest-qt** e piattaforma Qt `offscreen` (senza schermo), servizi
simulati, in `tests/ui/`.

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Menu → comandi | attivare ogni voce di menu di §3.3 con file e servizi simulati | ogni voce produce il comando atteso del `05` con i parametri attesi | ispezione della cronologia |
| T2 | Riesegui | rieseguire tre comandi selezionati | tre nuovi comandi in coda con nuovi numeri; stesso stato del registro | confronto dello spazio di lavoro |
| T3 | Interfaccia reattiva | servizio simulato che risponde dopo 5 s a `catalog.load_region` | sonda di latenza del thread principale sempre < 100 ms; barra di stato con avanzamento e Annulla | sonda con timer di Qt |
| T4 | Annulla | annullare il comando di T3 | esito `cancelled`, stato invariato, voce in cronologia | ispezione |
| T5 | Messaggi invariati | comando che produce un errore del 10 e un avviso del 13 | codice e testo identici a quelli dei moduli nel pannello Messaggi; finestra modale solo per un file illeggibile | confronto diretto |
| T6 | Traduzioni complete | `pyside6-lupdate` sul codice | nessuna stringa non tradotta nel file italiano; traduzione di Qt caricata | controllo del file `.ts` |
| T7 | Punto decimale | interfaccia in italiano con località `it_IT` | coordinate, valori e parametri mostrati con il punto decimale | lettura dei testi dei widget |
| T8 | Preferenze | cambiare le cinque preferenze, riavviare la finestra (impostazioni in cartella temporanea) | valori ritrovati; comandi `prefs.set` in cronologia di classe `application` | test |
| T9 | Sessione fermata | riaprire una sessione con un file cambiato | finestra modale con `SESSION_FILE_CHANGED` | test |
| T10 | Pannello IA | avvio con e senza profilo dell'assistente | area a destra con il pannello del `44`, richiudibile; voce Assistant attiva; senza profilo il pannello dice perché e tutti gli altri test di questa tabella passano | ispezione dei widget |
| T14 | Colonna "chi" | un comando da menu, uno dal mouse, uno dall'IA (provider simulato), Riesegui | colonna "Utente", "Utente", "IA", "Utente"; filtro per chi; dettaglio del comando IA con conversazione, turno, profilo, modello, conferma | ispezione della cronologia |
| T15 | Preferenze dell'assistente | modificare profilo, modalità rigorosa, limiti; scrivere una chiave | comandi `prefs.set` in cronologia; nessuna chiave in `QSettings` né in cronologia | ispezione |
| T11 | Vai a | nome noto (SIMBAD simulato), coordinate sessagesimali, testo non valido | vista centrata con fonte dichiarata; errore del 10 per il testo non valido | ispezione |
| T12 | Avvio (`perf`) | avvio senza rete sul Mac di riferimento | finestra pronta in ≤ 3 s | misura (marcatore `perf`, D41-4) |
| T13 | Aspetto | sistema in modalità scura e chiara (simulata); poi modalità notte | tema che segue il sistema; in modalità notte nessun colore dei widget con componente verde o blu sopra una soglia bassa dichiarata nel test; comando `ui.set_appearance` di classe `application` | lettura della tavolozza dei widget |

## 13. Decisioni aperte

Nessuna decisione dei Gruppi 1 e 2 aperta (dal 2026-10-15).

- **A9 — Lingua dell'interfaccia: DECISA il 2026-10-15 (decisione del
  proprietario).** Testi in inglese con `tr()`, traduzione italiana nostra
  con Qt Linguist, traduzioni di Qt per i dialoghi standard, lingua dal
  sistema cambiabile nelle preferenze, numeri scientifici sempre con il
  punto decimale in ogni lingua. Applicata in §3.9.
- **D40-1 — Lingua dei messaggi dei moduli: DECISA il 2026-10-15
  (decisione del proprietario).** Nella v1 si mostrano **codice e testo del
  modulo invariati**. Applicata in §3.7.
- **D40-3 — Messaggi dei moduli in inglese con traduzione (aperta il
  2026-10-15 dal proprietario, Gruppo 3):** portare i testi degli errori e
  degli avvisi dei moduli in inglese con traduzione italiana, coerente con
  A9. Opzioni da valutare: tabelle codice → testo dentro i moduli, oppure
  testi inglesi con `tr()` nei moduli. Riguarda i moduli 10–19 (approvati):
  da decidere dopo la v1.
- **D40-2 — Avvio tramite URL (H18): RIMANDATA il 2026-10-15** (decisione
  del proprietario, come proposto): l'equivalente in AstroTwo (app `.dmg`,
  senza Java WebStart) si definisce nella versione successiva del 40.
  Gruppo 3.
- **Scelte minori: CONFERMATE dal proprietario il 2026-10-15:** (1) preferenze in `QSettings` (file
  delle preferenze di macOS); (2) cambio di lingua al riavvio; (3) voci e
  scorciatoie dei menu di §3.3; (4) filtro della cronologia con la sola
  classe `session` di default; (5) catalogo nel campo con centro e raggio
  della vista (`ViewGeometry` del 10).
- **Proposta della fase 1 sull'IA, approvata dal proprietario il
  2026-10-16:** pannello del `44` nella disposizione, voce Assistant attiva,
  colonna "chi" nella cronologia, sezione Assistant nelle preferenze,
  comandi dell'IA nella stessa coda, casella per il testo delle
  conversazioni in Save session; applicata in §3.1, §3.2, §3.3, §3.6, §3.8,
  §3.10, §12 (T10, T14, T15).
- **Licenze verificate il 2026-10-16:** si usa **`pyside6-essentials`**
  6.12.0 (con `shiboken6`), che contiene QtWidgets, QtOpenGL,
  QtOpenGLWidgets e QtSvg, invece del pacchetto `pyside6` completo (che
  aggiunge Addons, WebEngine e PDF, non usati); licenza
  `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`, usata come LGPL-3.0; la
  ruota non contiene i testi: LGPL-3.0 e GPL-3.0 presi dal sorgente
  ufficiale di PySide6 6.12.0 (`scripts/licenses/`) e scritti in
  `THIRD_PARTY_LICENSES`; avvisi delle componenti incluse nelle librerie Qt
  da completare con il `60`. **pytest-qt** 4.5.0 MIT, nella sezione degli
  strumenti di sviluppo di `THIRD_PARTY_LICENSES`.
- **Verifiche prima del codice, fatte il 2026-10-17 (parte 3 della v1):**
  `QStyleHints.colorScheme` c'è in PySide6 6.12.0 (usato per seguire il
  sistema, T13); cifre tabulari con la funzione OpenType `tnum` di
  `QFont.setFeature` (impostazione verificata dai test; la resa a schermo
  con il carattere di sistema si controlla a occhio sul Mac). Licenza della
  raccolta di icone **verificata il 2026-10-17** con la parte 3b (§3.11, §8).
- **Codice della parte 3 (2026-10-17):** T1–T14 in `tests/ui/`; **T15**
  (preferenze dell'assistente) si scrive con il `44`, che porta la sezione
  Assistant delle preferenze. Le conferme dei comandi chiesti dall'IA
  (indicatore `confirm` del `05`, schede del `44`) arrivano con 32/35/44;
  i comandi chiesti dall'utente non chiedono conferma (l'azione dell'utente
  è la conferma), salvo uscita con comandi in corso o non salvati e
  apertura di una sessione sopra lavoro non salvato (§3.8).
- **Parte 3b (2026-10-17), correzioni dell'aspetto chieste dal proprietario
  dopo la prova della finestra (nessuna funzione nuova, comandi invariati):**
  foglio di stile dai colori dei mockup (barre, pannelli, tabelle con righe di
  24 punti senza griglia, schede dei pannelli in basso in alto, barra di
  stato), margini sulla griglia di 4 punti, icone Lucide nel colore del tema,
  intestazioni dei pannelli come nel mockup (titolo piccolo in maiuscolo,
  pulsanti per staccare e chiudere; i pannelli a schede usano le schede),
  stati vuoti con icona e testo che dice cosa arriverà (cielo 41, Livelli
  41, Tabella 42, Assistente 44, Comandi e Messaggi senza righe). Nella
  barra degli strumenti, come nel mockup, pulsanti per azioni già nei menu
  di §3.3 (Open image, pannello Layers, griglia, Distance, Simbad pointer,
  **Night mode**, Assistant). **Differenze dal mockup lasciate:** la scritta
  del survey nella barra ("DSS2 colore · TAN · campo") arriva con il 41 che
  dà quei valori; nella colonna "chi" restano "Utente/IA/Sessione" di §3.6
  (il mockup mostra "menu/mouse").
- **Sprint 4a del 41 (2026-10-17):** il segnaposto del cielo è sostituito
  dal visualizzatore del 41; la scritta del survey nella barra
  ("titolo · proiezione · campo") ora c'è; la **barra di stato ha altezza
  fissa di 26 px** (come il mockup), così mostrare Annulla e l'avanzamento
  non cambia la dimensione del cielo (che a ogni nuova dimensione registra
  la nuova finestra).
- **D40-4 — Scorciatoia della modalità notte: DECISA il 2026-10-17
  (decisione del proprietario): ⌃⌘N** per View → Night mode (stessa
  famiglia di ⌃⌘F schermo intero e ⌃⌘A assistente; non usata da altre voci
  né dalle scorciatoie standard di macOS per le app). La voce resta anche
  nel menu View e nel pulsante con la luna nella barra degli strumenti.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-15 | Claude Code | Creazione del file (stato: bozza) dalla proposta della fase 1 approvata dal proprietario il 2026-10-15: perimetro v1 (menu, barra di stato, campo "Vai a", preferenze essenziali, apertura di file e sessioni, pannelli Comandi e Messaggi, schermo intero, spazio per il 44), coda dei comandi in un thread di lavoro con segnali di Qt, avanzamento e Annulla per ogni comando lungo, A9 decisa (inglese con `tr()`, italiano nostro con Qt Linguist, traduzioni di Qt, punto decimale sempre). Nuove decisioni D40-1, D40-2. |
| 2026-10-15 | Claude Code | **Decisioni del proprietario del 2026-10-15:** D40-1 decisa (v1: codice + testo del modulo invariato); nuova **D40-3** (Gruppo 3: messaggi dei moduli in inglese con traduzione); D40-2 rimandata; scelte minori confermate; **nuova §3.11 "Linee guida visive"** (valide per tutte le interfacce: macOS, tema che segue il sistema con lo scuro di riferimento, modalità notte rossa, cielo al centro con pannelli richiudibili e barre sottili, carattere di sistema, un solo accento, spaziature di 4 punti, icone Lucide proposte con licenza da verificare, colori dei cataloghi di Okabe e Ito, nulla da Aladin); preferenza "Aspetto" e voce Night mode; PySide6/Qt LGPL-3 registrata per A11 e per il 60; mockup in `mdfiles/mockup/`; test T13. Nessuna decisione dei Gruppi 1 e 2 resta aperta. |
| 2026-10-16 | Claude Code | **Proposta della fase 1 sull'IA approvata dal proprietario il 2026-10-16** (autorizzazione a modificare la bozza come proposto): il pannello dell'assistente (`44`) entra nella v1 nell'area a destra, voce Assistant attiva (⌃⌘A); colonna "chi" (da `requested_by` del `05`) e dettagli dei comandi dell'IA nel pannello Comandi; sezione Assistant nelle preferenze (chiave solo nel Portachiavi, `31`); comandi dell'IA nella stessa coda con lo stesso `CancelToken`; casella "Includi il testo delle conversazioni" in Save session; test T10 aggiornato, T14 e T15 nuovi. |
| 2026-10-16 | Claude Code | **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-16. |
| 2026-10-16 | Claude Code | Verifiche del 2026-10-16: licenze di PySide6 (`pyside6-essentials`, LGPL-3.0 con i testi dal sorgente ufficiale) e di pytest-qt (MIT) verificate e in `THIRD_PARTY_LICENSES`. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **Codice della parte 3 della v1** ("FASE: CODICE – interfaccia v1"): `src/astrotwo/ui/main_window.py` (finestra, menu, barra di stato, "Vai a", pannelli Comandi e Messaggi, coda dei comandi in un `QThread` con avanzamento e Annulla, preferenze, aspetto scuro/chiaro/sistema/notte rossa, lingua inglese/italiano con punto decimale sempre), traduzione `src/astrotwo/ui/i18n/astrotwo_it.ts`/`.qm`, avvio `uv run astrotwo`, test `tests/ui/test_main_window.py` (T1–T14, T12 con marcatore `perf`). Verifiche di §13 fatte (colorScheme, cifre tabulari); icone ancora da verificare quando si aggiungono. Visualizzatore (41), tabella (42) e assistente (44) restano spazi riservati fino alle loro parti. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **Parte 3b del codice della v1** (correzioni dell'aspetto dopo la prova del proprietario; nessuna funzione nuova, comandi invariati): foglio di stile dai mockup, icone Lucide (licenza verificata: ISC più MIT di Feather, in `THIRD_PARTY_LICENSES`; §3.11, §8), intestazioni dei pannelli, stati vuoti dei segnaposto, pulsanti della barra per azioni già nei menu (anche Night mode); test T13 esteso al foglio di stile e alle icone in modalità notte, nuovo test delle linee guida visive. **Aperta D40-4** (scorciatoia della modalità notte, Gruppo 3, raccomandazione ⌃⌘N). Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **D40-4 decisa dal proprietario: ⌃⌘N** per View → Night mode (§3.3, §13); codice e test T13 aggiornati. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | Sprint 4a del 41: visualizzatore al posto del segnaposto, scritta del survey nella barra, barra di stato ad altezza fissa (26 px, §13). Stato `approvato` invariato. |
