# 40-ui-finestra-principale.md — finestra principale, menu, barra di stato, preferenze

**Stato:** bozza

## 2. Scopo

Dare all'utente una finestra unica da cui aprire dati, comandare la vista
del cielo, vedere la cronologia dei comandi e i messaggi dei moduli e
regolare le preferenze essenziali, facendo passare ogni azione dal registro
dei comandi (`05`) senza mai bloccare l'interfaccia.

## 3. Cosa fa

### 3.1 Perimetro della prima versione (v1)

Perimetro approvato dal proprietario il 2026-10-15. La v1 dell'interfaccia
(40, 41, 42 minimo) usa **solo il livello 1**.

- **In v1:** menu, barra di stato, campo "Vai a", preferenze essenziali,
  apertura di file (immagine FITS, catalogo, MOC) e di sessioni, pannello
  Comandi (cronologia visibile e rieseguibile), pannello Messaggi, schermo
  intero (A10), coda dei comandi in un thread di lavoro con avanzamento e
  Annulla, spazio riservato al futuro pannello IA (44).
- **Fuori dalla v1** (versioni successive): segnalibri e storico delle
  posizioni (A12, H13, H16), console degli script e modalità demo o guida
  (H13), avvio tramite URL (H18, D40-2), finestre delle calcolatrici (18),
  preferenze non essenziali (cifre di visualizzazione DC3, timeout CA1,
  limiti di memoria e delle tabelle, dati planetari D19-5, server
  predefiniti, tema), pannello analisi (43), pannello IA (44), viste
  multiple (45). Finché non hanno un'interfaccia valgono i default dei
  moduli.

### 3.2 Disposizione

- Al centro il **visualizzatore del cielo** (`41`).
- Pannelli agganciabili (spostabili e richiudibili, comportamento standard
  di Qt): **Livelli** (del `41`), **Tabella** (`42`), **Comandi** e
  **Messaggi** (di questo modulo).
- **Spazio per il pannello IA (44):** un'area agganciabile a destra,
  nascosta, e una voce di menu disattivata "Assistant (available with level
  3)"; nessuna implementazione nella v1. L'area esiste già perché il futuro
  pannello non cambi la disposizione.
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
  Full screen (A10, `ui.set_fullscreen`).
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
  `THIRD_PARTY_LICENSES`); Assistant (disattivata, §3.2).
- Scorciatoie standard di macOS (⌘O apri, ⌘S salva sessione, ⌘Q esci,
  ⌃⌘F schermo intero).

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
  nome, parametri in breve, esito (ok, errore, annullato), numero di
  avvisi. Filtro per classe (`session` di default, `application` a
  richiesta; D05-1).
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
- Lingua dei messaggi dei moduli: D40-1.

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
- **Sessione:** Open session riapre con la riesecuzione del `05` (comando
  lungo, con avanzamento e Annulla); gli stop del `05` si mostrano in una
  finestra modale. Prima di aprire una sessione o di uscire con comandi non
  salvati, richiesta di conferma.

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

Finestra delle preferenze con quattro voci; ogni modifica è un comando
`prefs.set` (classe `application`). Salvate nelle impostazioni dell'app di
macOS con `QSettings` (scelta minore 1), mai nella sessione.

| Preferenza | Valori | Effetto |
|---|---|---|
| Lingua | sistema, inglese, italiano | al riavvio (§3.9) |
| Limite della cache | byte, default 5 × 10⁹ (CA2 del `04`) | mostra spazio usato per modulo e totale (`usage`) e il pulsante "svuota" (`cache.clear`) |
| Sistema di coordinate mostrato | ICRS sessagesimale, ICRS decimale, galattico | valore iniziale di `view.set_coordinate_display` |
| Survey HiPS predefinito | identificativo HiPS; default `CDS/P/DSS2/color` (D12-3) | survey attivato all'avvio con `hips.set_survey` |

## 4. Cosa NON fa

- Non calcola nulla: coordinate, valori, misure e testi vengono dai moduli
  attraverso il `05` (regola d'oro n. 1, `01` §3).
- Non disegna il cielo né gestisce i livelli (`41`), non mostra tabelle
  (`42`).
- Non riscrive né traduce i messaggi dei moduli (D40-1).
- Non ha "annulla/ripeti" (A12): si riesegue la cronologia.
- Non implementa il pannello IA (44) né chiama l'IA.
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
  `42-ui-pannello-cataloghi.md`; libreria PySide6.
- **Usato da:** nessuno nella v1 (in futuro `43`, `44`, `45` si agganciano a
  questa finestra).

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
- **`PreferencesDialog`** — le quattro preferenze di §3.10.
- **`load_translations(language)`** — carica la traduzione nostra e quella
  di Qt; senza file di traduzione resta l'inglese con un avviso.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| **PySide6** (Qt 6: QtWidgets, QtCore) | finestra, menu, pannelli, thread (`QThread`), segnali, `QSettings`, `QLocale`, `QTranslator` | decisione A1; **licenza (LGPL-3 per i binding e per Qt) da verificare prima del codice** e da aggiungere a `THIRD_PARTY_LICENSES`; da valutare con A11 e per il `60` |
| Qt Linguist (`pyside6-lupdate`, `pyside6-lrelease`) | file di traduzione `.ts`/`.qm` | strumento standard di Qt (A9) |
| Traduzioni di Qt (`qtbase_it`) | dialoghi standard in italiano | distribuite con Qt |
| **pytest-qt** | test dell'interfaccia | decisione del proprietario del 2026-10-15; **licenza da verificare** e da aggiungere a `THIRD_PARTY_LICENSES` |

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
| T8 | Preferenze | cambiare le quattro preferenze, riavviare la finestra (impostazioni in cartella temporanea) | valori ritrovati; comandi `prefs.set` in cronologia di classe `application` | test |
| T9 | Sessione fermata | riaprire una sessione con un file cambiato | finestra modale con `SESSION_FILE_CHANGED` | test |
| T10 | Spazio IA | avvio | area riservata presente e nascosta; voce di menu disattivata | ispezione dei widget |
| T11 | Vai a | nome noto (SIMBAD simulato), coordinate sessagesimali, testo non valido | vista centrata con fonte dichiarata; errore del 10 per il testo non valido | ispezione |
| T12 | Avvio (`perf`) | avvio senza rete sul Mac di riferimento | finestra pronta in ≤ 3 s | misura (marcatore `perf`, D41-4) |

## 13. Decisioni aperte

- **A9 — Lingua dell'interfaccia: DECISA il 2026-10-15 (decisione del
  proprietario).** Testi in inglese con `tr()`, traduzione italiana nostra
  con Qt Linguist, traduzioni di Qt per i dialoghi standard, lingua dal
  sistema cambiabile nelle preferenze, numeri scientifici sempre con il
  punto decimale in ogni lingua. Applicata in §3.9.
- **D40-1 — Lingua dei messaggi dei moduli:** i testi degli errori e degli
  avvisi dei moduli 10–19 sono oggi in italiano; con l'interfaccia in
  inglese comparirebbero in italiano. La regola "testo del modulo mai
  riscritto" vieta di tradurli nell'interfaccia. Opzioni: (a) nella v1
  mostrare **codice (sempre in inglese) e testo del modulo invariato**,
  rimandando la traduzione; (b) testi dei moduli tradotti con tabelle
  codice → testo dentro i moduli (modifica di tutti i moduli 10–19); (c)
  testi dei moduli riscritti in inglese. **Raccomandazione: (a) per la
  v1**, con (b) da valutare dopo: il codice d'errore basta a capire e
  cercare il problema, e nessun modulo approvato va modificato ora.
  Gruppo 2 (blocca l'approvazione del 40).
- **D40-2 — Avvio tramite URL (H18):** l'equivalente in AstroTwo (app
  `.dmg`, senza Java WebStart) resta da definire; **fuori dalla v1**.
  Raccomandazione: rimandare alla versione successiva del 40. Gruppo 3.
- **Scelte minori da confermare:** (1) preferenze in `QSettings` (file
  delle preferenze di macOS); (2) cambio di lingua al riavvio; (3) voci e
  scorciatoie dei menu di §3.3; (4) filtro della cronologia con la sola
  classe `session` di default; (5) catalogo nel campo con centro e raggio
  della vista (`ViewGeometry` del 10).
- **Da verificare prima del codice:** licenze di PySide6/Qt e di
  pytest-qt (da aggiungere a `THIRD_PARTY_LICENSES`).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-15 | Claude Code | Creazione del file (stato: bozza) dalla proposta della fase 1 approvata dal proprietario il 2026-10-15: perimetro v1 (menu, barra di stato, campo "Vai a", preferenze essenziali, apertura di file e sessioni, pannelli Comandi e Messaggi, schermo intero, spazio per il 44), coda dei comandi in un thread di lavoro con segnali di Qt, avanzamento e Annulla per ogni comando lungo, A9 decisa (inglese con `tr()`, italiano nostro con Qt Linguist, traduzioni di Qt, punto decimale sempre). Nuove decisioni D40-1, D40-2. |
