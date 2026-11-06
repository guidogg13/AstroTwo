# 42-ui-pannello-cataloghi.md — pannello cataloghi e tabelle

**Stato:** approvato

## 2. Scopo

Mostrare le righe dei cataloghi aperti in una tabella ordinabile,
sincronizzata con la vista del cielo, e il record completo di una sorgente,
senza modificare i dati e senza calcolare nulla.

## 3. Cosa fa

### 3.1 Perimetro della prima versione (v1, minima)

Versione minima approvata dal proprietario il 2026-10-15 (senza tabella un
catalogo è poco usabile).

- **In v1:** tabella in sola lettura con ordinamento (D8, parte
  ordinamento); selezione sincronizzata con la vista (D7); vista del
  record con `record_view` del 13; dialoghi delle colonne di posizione e
  di moto proprio all'apertura di un catalogo.
- **Fuori dalla v1:** ricerca per espressione (`search`, D6) e ricerca in
  tabella (D8, parte ricerca), editor delle regole di disegno (D4),
  etichette (D5), colonne calcolate, sottoinsiemi, istogrammi e grafici
  x-y (H8), DataLink, esportazione delle tabelle. **L'invio con SAMP (G3)
  è entrato il 2026-11-05 (sprint B1, decisioni del proprietario, D40-8 del
  `40`): §3.6. L'incrocio per posizione (E3) è entrato il 2026-11-05
  (sprint B2, D15-10 del `15`): §3.7. Cone search (E1) e query ADQL (E2)
  sono entrate il 2026-11-06 (sprint B3): §3.8.**

### 3.2 Tabella

- **Una scheda per livello di catalogo** del `41`, con il nome del livello
  e la sorgente (file o servizio, origine e data).
- **Modello virtuale** (`QAbstractTableModel` con `QTableView`): le righe
  si leggono dalla tabella del 13 solo quando sono visibili, senza copie;
  fino al tetto di 1 milione di righe del 13.
- **Intestazioni:** nome della colonna e unità; nel suggerimento al
  passaggio del mouse anche UCD e descrizione dai metadati del 13.
- **Valori** (regola decisa dal proprietario il 2026-10-16, che sostituisce
  la scelta minore 1 del 2026-10-15; motivo: il mockup con le cifre di DC3
  la contraddiceva):
  - **colonne di posizione** confermate (`confirm_position_columns` del
    13): scritte con **`format_coordinates` del 10** nel **frame della
    colonna** (nessuna conversione di frame), con lo stile scelto in
    "Coordinates shown" del `40` (sessagesimale o decimale) e le cifre di
    DC3 (RA 0.01 s, Dec 0.1″);
  - **magnitudini** (colonne con UCD che comincia con `phot.mag`):
    **3 decimali** (DC3), arrotondamento di presentazione (`02` §6) con la
    formattazione standard di Python a virgola fissa, sull'unità della
    colonna;
  - **altre colonne:** come sono nella tabella, senza conversioni né unità
    cambiate: formato dichiarato dalla colonna se c'è (`precision`/`width`
    del VOTable, formato FITS), altrimenti la rappresentazione più breve che
    si rilegge identica;
  - sempre con il **punto decimale** (`40` §3.9); valori mancanti come
    cella vuota con un segno grafico;
  - **valore pieno** (`float64` della tabella con l'unità) nel
    **suggerimento** al passaggio del mouse e nella **copia** (`02` §6).
- **Ordinamento** (D8): clic sull'intestazione → `table.sort` (livello,
  colonna, verso) del `05`. L'ordine è quello delle righe **mostrate**: la
  tabella del 13 non cambia (D13-5). Ordine stabile (a pari valore resta
  l'ordine originale), valori mancanti in fondo. Calcolo dell'ordine:
  scelta minore 2.

### 3.3 Selezione sincronizzata (D7)

- Selezionare righe (clic, ⇧ per un intervallo, ⌘ per aggiungere) →
  `catalog.select` (livello, righe) del `05`; le sorgenti si evidenziano
  nel `41`.
- Un clic su una sorgente nel `41` seleziona la riga qui, porta la tabella
  sulla riga e mostra il record.
- Le righe non disegnabili nel `41` (moto proprio mancante, D13-12) sono
  selezionabili qui e marcate come "non disegnata".

### 3.4 Vista del record

Con una sola riga selezionata, un riquadro mostra tutti i valori della
riga con `record_view` del 13 (nome, valore, unità, UCD, mancante sì/no,
unità non riconosciuta se il 13 lo segnala). Lettura senza rete, parte del
risultato di `catalog.select`.

### 3.5 Colonne all'apertura di un catalogo

- **Posizione:** il 13 propone le colonne (`suggest_position_columns`) e
  l'utente le conferma (`confirm_position_columns`, con l'unità angolare
  quando il 13 la richiede); se il 13 le ricava già da UCD o metadati il
  dialogo non appare.
- **Moto proprio e parallasse** (facoltativi): l'utente sceglie le colonne
  di moto proprio in RA e Dec (dicendo se quella in RA include cos δ),
  parallasse ed eventualmente velocità radiale, che il `41` passa a
  `display_positions` del 13; senza scelta vale la scelta minore 3 del
  `41` (posizioni della tabella, "non propagato"). Le colonne scelte sono
  parametri di `catalog.set_columns` del `05`.

### 3.6 SAMP: tabelle e selezioni con altri programmi (sprint B1, 2026-11-05)

Decisioni del proprietario del 2026-11-05 (D40-8); collegamento, thread e ricezione nel `40` §3.12, protocollo nel
14.

- **Menu contestuale della tabella** (clic destro su una scheda): **Send whole table via SAMP** / **Manda tutta
  la tabella via SAMP** (`samp.send_table`), **Send only the selected rows (N) via SAMP** / **Manda solo le righe
  selezionate (N) via SAMP** (`samp.send_selection`; N = righe selezionate, voce spenta con N = 0; testi dello
  sprint B2, prima "Send table via SAMP" e "Send selected rows via SAMP", che si confondevano) e, con una sola riga
  selezionata che ha una posizione,
  **Point SAMP applications at this source** (`samp.point_at`); ogni voce apre l'elenco dei destinatari ("All
  applications" o un client). Spente se AstroTwo non è collegato (con la voce **Connect to SAMP hub**). Le stesse
  azioni sono nel menu Tools → SAMP per la scheda in primo piano.
- **Indici delle righe:** nell'ordine della tabella del 13 (quello del VOTable inviato), da 0, **non** nell'ordine
  mostrato dopo un `table.sort`.
- **Tabella ricevuta** (`table.load.votable`): una nuova scheda come per un file aperto (`catalog.open_file` con
  origine `samp`), con i dialoghi delle colonne di §3.5 se il 13 non ricava le posizioni.
- **Selezione ricevuta** (`table.select.rowList`) per una tabella nota: `catalog.select` con origine `samp`,
  quindi stessa evidenza e stesso record di §3.3–§3.4; il pannello non la rimanda indietro.
- Il pannello non parla con l'hub: emette la richiesta del menu (segnale `context_menu_requested` con il livello e
  il punto sullo schermo) e la finestra (`40`) costruisce il menu e mette in coda i comandi.

### 3.7 Incrocio per posizione: dialogo e report (sprint B2, 2026-11-05)

Decisioni del proprietario del 2026-11-05 (D15-10 del `15`); comando `catalog.crossmatch` del `05` §7; motore del
15. Codice: `src/astrotwo/ui/crossmatch_dialog.py` (`CrossmatchDialog`, `CrossmatchReportDialog`) e la finestra.

- **Dove:** Data → **Cross-match catalogs…** / **Incrocia cataloghi…** (`40` §3.3) e, nel menu contestuale di una
  scheda della tabella, **Cross-match with another catalog…** / **Incrocia con un altro catalogo…** (A = il
  catalogo della scheda; spenta con meno di due cataloghi). Dal menu Data con meno di due cataloghi una finestra
  dice di aprirne prima almeno due.
- **Dialogo** (i campi diventano i parametri del comando, senza conversioni):
  - **Catalogo A** e **Catalogo B**: elenco dei cataloghi caricati («`L<n>` · nome»); B propone il primo diverso
    da A.
  - **Modalità** con una spiegazione breve sotto: *Migliore (la più vicina)* = `best` (per ogni riga di A la riga
    di B più vicina entro la separazione; una riga di B può servire più righe di A; a pari distanza l'indice più
    basso di B), *Tutte le coppie* = `all`, *Righe di A senza corrispondenza* = `none` (le righe senza posizione
    sono escluse e contate).
  - **Separazione massima**: numero (punto decimale sempre) e **unità** scelta tra `mas`, `arcsec`, `arcmin`,
    `deg`; proposta **2 arcsec** (D15-10 (a)). Il dialogo non taglia i valori: i limiti li controlla il 15
    (`MAX_SEP_INVALID`), così il messaggio è quello del modulo.
  - **Metodo**: *Locale (astropy, su questo computer)* (default) o *Servizio CDS XMatch (rete, al massimo 180
    arcsec)*.
  - **Sistema di confronto**: ICRS (default) o Galattico; con il servizio CDS bloccato su ICRS.
  - **Epoche**: riga informativa con l'epoca delle posizioni di A e di B **come la dichiara il 13** («non
    dichiarata» se manca, mai assunta) o la nota che un catalogo non ha colonne di posizione confermate (con
    l'indicazione di "Colonne…", §3.5); se le epoche sono dichiarate e diverse, la nota che le posizioni si
    confrontano senza propagazione e che il risultato avrà `EPOCH_DIFFERS`.
  - Pulsante **Incrocia** (OK) e Annulla.
  - **Incrocio per campo (P3) ed ellissi d'errore (P4):** non compaiono nel dialogo, nemmeno come "in arrivo"
    (scelta di Claude Code, D42-1): il motore li ha già, entreranno con un dialogo proprio (scelta delle colonne
    chiave o delle tre colonne dell'ellisse con `axes`, soglia in sigma senza default) quando il proprietario lo
    chiederà; una voce spenta non aiuterebbe l'utente.
- **Risultato:** nuovo livello catalogo nel cielo e nuova scheda nel pannello Tabella come per un file aperto
  (stile iniziale del `05`): `best`/`all` = tabella unita con `xmatch_sep` (arcsec) e i suffissi `_tab1`/`_tab2`
  del 15 sui nomi in conflitto, `none` = le righe di A senza corrispondenza. Si può ordinare, selezionare e
  **mandare via SAMP** come ogni catalogo (§3.6).
- **Report** (D42-1): finestra non modale **Cross-match report** / **Report dell'incrocio** aperta da sola alla
  fine di un incrocio chiesto dall'utente in questa finestra (menu, mouse, Riesegui; non per l'IA né alla
  riapertura di una sessione) e riapribile dal menu contestuale della scheda del nuovo catalogo (**Show cross-match
  report** / **Mostra il report dell'incrocio**). Contiene: riepilogo con etichette nella lingua
  dell'interfaccia e valori del 15 così come sono (cataloghi A e B, metodo, modalità e separazione con unità,
  sistema di confronto e sistemi delle tabelle, epoche, righe ed escluse, coppie o non appaiati, colonna della
  separazione, forzatura del corpo), gli **avvisi** dal catalogo dei messaggi e il **testo del modulo**
  (`MatchReport.describe()`, in italiano come gli altri testi originali dei moduli). Il report resta anche nei
  dettagli del comando nel pannello Comandi (`values.crossmatch.report` e `report_text`).
- **Errori:** finestra "The cross-match was not run" / "L'incrocio non è stato eseguito" con il messaggio del
  modulo (`40` §10), oltre al pannello Messaggi; corpi diversi: offerta di forzatura (D19-4).

### 3.8 Cone search e query ADQL: dialoghi (sprint B3, 2026-11-06)

Decisioni del proprietario del 2026-11-06; comandi `catalog.cone_search`, `catalog.tap_query`, `vo.add_server`,
`vo.remove_server` del `05` §7; protocolli del 14. Codice: `src/astrotwo/ui/vo_query_dialogs.py`
(`ConeSearchDialog`, `AdqlQueryDialog`, esempi `ADQL_EXAMPLES`) e la finestra. Nessun calcolo nei dialoghi: i
campi diventano i parametri dei comandi; i controlli (unità, intervalli, `MAX_ROWS_INVALID`, `SERVER_UNKNOWN`,
`ADQL_INVALID`) sono del `05` e del 14 e arrivano come messaggi. "Catalog in view…" non cambia.

- **Dove:** menu Data del `40` §3.3: **Cone search…** / **Cone search…** e **ADQL query…** / **Query ADQL…**,
  dopo "Catalog in view…" e prima del separatore di "Cross-match catalogs…" (D42-2 (1)).
- **Servizio (entrambi):** elenco a discesa con le voci del 14 del protocollo giusto (`ServerRegistry.find`:
  `scs` per la cone search, `tap` per la query), voci nostre «nome (ente)» e poi i **miei server** «nome (mio
  server)», più l'ultima voce **URL scritto a mano…** / **URL scritto a mano…** che abilita un campo per l'URL
  http(s). Accanto: **Salva tra i miei server…** (attivo con un URL scritto; chiede il nome, proposto l'host
  dell'URL → `vo.add_server`) e **Togli dai miei server** (attivo con un mio server scelto → `vo.remove_server`).
  Nessuna altra gestione (decisione (e)). La voce scelta va nel parametro `service` (identificativo), un URL
  scritto va in `service` così com'è; `url` resta `null` (lo risolve il `05`).
- **Cone search** (`ConeSearchDialog`):
  - **Centro**, tre scelte: **Centro della vista** (default; `ViewState.center` con l'epoca come la scrive il
    `05`, `null` con il motivo); **Sorgente selezionata** (attiva se nella scheda in primo piano del pannello
    Tabella è selezionata una sola riga con una posizione: posizione della tabella con l'epoca dichiarata dal 13,
    senza propagazione, come la scheda della sorgente); **Coordinate scritte**: testo letto come nel campo "Vai a"
    (coppia decimale in gradi o sessagesimale, `parse_sexagesimal` del 10), **sistema** (ICRS, FK5 con equinozio
    J2000.0, Galattico) ed **epoca** (`J…`/`B…`; vuota = epoca non dichiarata, `null` con il motivo, mai
    assunta). Coordinate non leggibili: messaggio nel dialogo, nessun comando.
  - **Raggio** con **unità** (`arcsec`, `arcmin`, `deg`): proposto il raggio del campo della vista
    (`ViewGeometry.field_radius` del 10) in arcmin; il dialogo non taglia i valori (limiti del `05`).
  - **Righe massime**: default **100 000** (D14-5).
  - Pulsante **Cerca** (OK) e Annulla. Senza vista definita il centro della vista è spento.
- **Query ADQL** (`AdqlQueryDialog`):
  - **Editor** a larghezza fissa (`QFontDatabase.FixedFont`), con il testo dell'ultima query della sessione.
  - **Esempi** (menu a discesa): gli esempi del servizio scelto (`ADQL_EXAMPLES`, scritti da Claude Code e provati
    sui servizi veri raggiungibili, §12); sceglierne uno sostituisce il testo (annullabile con ⌘Z). Nessuna
    generazione automatica di query oltre agli esempi (decisione (d)).
  - **Inserisci centro e raggio della vista** / **Insert view centre and radius**: valori numerici del centro della
    vista convertito in ICRS dal 10 e del raggio del campo (`field_radius`) in gradi, con 10 cifre significative;
    se nel testo c'è una `CIRCLE('ICRS', a, b, c)` sostituisce i tre numeri della prima, altrimenti inserisce
    `CIRCLE('ICRS', ra, dec, r)` al cursore; poi scrive in fondo la riga di commento `-- CIRCLE: view centre and
    radius, ICRS, degrees; epoch of the centre: <epoca o "not known (not assumed)">` (la sostituisce se c'è). Il
    commento non arriva al servizio: il 14 toglie i commenti prima dell'invio (14 §3).
  - **Modalità**: **Sincrona** (default) o **Asincrona** con l'**attesa massima** in secondi (default 600, D14-9);
    il lavoro si annulla con il pulsante di annullamento della barra di stato (`40` §3.5).
  - **Righe massime** (`MAXREC`): default **100 000** (D14-5).
  - **Controllo** (anche al clic su **Esegui**): `validate_adql` del 14 prima di mandare il comando; con un errore
    il dialogo resta aperto, il carattere alla posizione si evidenzia nell'editor (sfondo del colore d'errore,
    cursore lì) e sotto compare il messaggio del catalogo (`ADQL_INVALID`, riga e colonna). Nessuna richiesta al
    servizio.
  - Pulsanti **Esegui** (OK) e Annulla.
- **Risultato** (entrambi): nuovo livello catalogo nel cielo e nuova scheda nel pannello Tabella (stile iniziale del
  `05`), con la provenienza nei dettagli del comando (`values.query`: servizio, URL, parametri o query inviata,
  data, righe, troncamento). `ROW_LIMIT_EXCEEDED` nel pannello Messaggi. Colonne di posizione da UCD e `COOSYS`;
  se il 13 non le determina con il sistema, si apre il **dialogo delle colonne** come per i file (§3.5). Si può
  incrociare (§3.7) e mandare via SAMP (§3.6) come ogni catalogo.
- **Errori:** per un comando chiesto in questa finestra (menu, Riesegui) una finestra **The query was not run** /
  **La query non è stata eseguita** con il messaggio; se il servizio ha rifiutato la query, sotto il messaggio,
  dopo una riga vuota e l'etichetta **Message of the service (as received):** / **Messaggio del servizio (tale e
  quale):**, il **testo del servizio tale e quale** (testo esterno). Il messaggio va anche nel pannello Messaggi.

## 4. Cosa NON fa

- Non modifica le tabelle (sola lettura, D13-5) e non calcola valori,
  colonne o statistiche (13).
- Non converte unità né frame; le coordinate delle colonne di posizione le
  scrive il 10 (`format_coordinates`), non questo modulo.
- Non disegna le sorgenti (`41`) e non interroga servizi (13, 14).
- Non salva sottoinsiemi né esporta tabelle su file (fuori dalla v1); l'invio a un altro programma è SAMP (§3.6).

## 5. Livello e dipendenze

- **Livello:** interfaccia; nella v1 usa solo il livello 1.
- **Dipende da:** `10-core-coordinate-wcs.md` (`format_coordinates` per le
  colonne di posizione), `05-comandi-sessione.md` (comandi `table.sort`,
  `catalog.select`, `catalog.set_columns`), `13-core-cataloghi.md`
  (tabelle, `record_view`, colonne di posizione),
  `41-ui-visualizzatore-cielo.md` (selezione sincronizzata),
  `40-ui-finestra-principale.md` (pannello agganciabile); PySide6.
- **Usato da:** `41-ui-visualizzatore-cielo.md` (selezione e record al clic).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | tabella del livello | `CatalogTable` del 13 dallo spazio di lavoro del `05` | unità e UCD delle colonne | sola lettura |
| in | selezione dal `41` | righe | indici di riga | sincronizzazione |
| out | comandi | `table.sort`, `catalog.select`, `catalog.set_columns` | parametri tipizzati | `05` |
| out | record | risultato di `record_view` | valori con unità e UCD | riquadro del record |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole. File Python
`src/astrotwo/ui/catalog_panel.py`; test in `tests/ui/test_catalog_panel.py`.

- **`CatalogPanel`** — schede dei cataloghi, ordinamento, selezione,
  riquadro del record.
- **`CatalogTableModel`** — modello virtuale sulla tabella del 13, con
  l'ordine delle righe mostrate.
- **`PositionColumnsDialog`**, **`ProperMotionColumnsDialog`** — dialoghi
  di §3.5.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| PySide6 (`QAbstractTableModel`, `QTableView`) | tabella virtuale | A1; nessuna copia dei dati |
| `numpy.argsort(kind="stable")` | ordine delle righe mostrate (scelta minore 2) | ordinamento stabile consolidato; non produce valori |
| **pytest-qt** | test | decisione del proprietario del 2026-10-15; licenza da verificare (`40` §8) |

## 9. Regole e vincoli

- **Sola lettura:** nessuna modifica delle tabelle del 13 (D13-5).
- **Nessun calcolo:** i valori sono quelli della tabella; il record è
  quello di `record_view`; l'ordinamento cambia solo l'ordine mostrato.
- **Ogni azione è un comando** (`05`).
- **Punto decimale** in ogni lingua (`40` §3.9).
- **Prestazioni:** una tabella di 1 milione di righe si apre e scorre senza
  copiare i dati (memoria aggiuntiva da misurare, con l'obiettivo P2 del
  `41`); tempo dell'ordinamento di 1 milione di righe da misurare e
  riportare (nessun obiettivo scritto finché non è misurato).
  **Misura del 2026-10-21 (T6, sprint 5a, Mac del proprietario):** modello
  di 1 000 000 di righe aperto in 0,3 ms senza copia dei dati (22,9 MiB di
  dati, 7,7 MiB di memoria aggiuntiva al picco: l'ordine mostrato e i testi
  delle righe visibili); ordinamento di una colonna `float64` con l'1 % di
  mancanti in 114 ms.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Colonna con tipo non ordinabile (es. array) | ordinamento rifiutato con messaggio | `TABLE_SORT_UNSUPPORTED` |
| Valori mancanti nella colonna ordinata | in fondo, in entrambi i versi | — |
| Colonne di posizione non confermate | catalogo aperto in tabella ma non disegnato nel `41`, avviso | codice del 13 |
| Riga selezionata non disegnabile | selezionata qui, marcata "non disegnata" | — |
| Livello rimosso nel `41` | scheda chiusa | — |

### 10.1 Messaggi con codice e `params` (D40-3, sprint 8e, 2026-10-25)

Il pannello non ha messaggi propri: il solo codice è `TABLE_SORT_UNSUPPORTED` del `05` (`05` §10.1, sotto-voci
`array_column` e `not_sortable`), mostrato nella lingua dell'interfaccia dal catalogo. I testi del pannello (etichette,
intestazioni, "non disegnata") sono testi di interfaccia tradotti da Qt, non messaggi dei moduli.

## 11. Esposizione all'IA

Non applicabile: è interfaccia. I comandi sono del `05`.

## 12. Test di accettazione

Con **pytest-qt** e piattaforma `offscreen`, in `tests/ui/`.

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Ordinamento | tabella sintetica con valori ripetuti e mancanti; ordinare in salita e in discesa | ordine uguale a `numpy.argsort(kind="stable")` ricalcolato nel test, mancanti in fondo; tabella del 13 invariata; comando `table.sort` in cronologia | ricalcolo nel test |
| T2 | Selezione dalla tabella | selezionare tre righe | `catalog.select` con le tre righe; sorgenti evidenziate nel `41` | ispezione |
| T3 | Selezione dalla vista | clic su una sorgente nel `41` | riga selezionata e visibile; record mostrato | ispezione |
| T4 | Record | selezionare una riga con un valore mancante | contenuto uguale a `record_view` del 13 per quella riga | confronto diretto |
| T5 | Valori mostrati | colonne di posizione ICRS e galattiche, magnitudini (UCD `phot.mag;em.opt.V`), colonne con formato dichiarato, senza formato, mancanti | posizioni identiche ai testi di `format_coordinates` del 10 sugli stessi valori; magnitudini con 3 decimali; altre colonne secondo §3.2; suggerimento e copia con il valore pieno identico al `float64` della tabella; punto decimale anche in italiano | confronto diretto con il 10 e con la tabella |
| T6 | Un milione di righe | tabella sintetica di 1 000 000 di righe | apertura senza copia dei dati; memoria aggiuntiva e tempo di ordinamento misurati e riportati (`perf`) | misura |
| T7 | Colonne all'apertura | CSV senza UCD; scelta delle colonne di moto proprio | `confirm_position_columns` chiamata con le colonne confermate; `catalog.set_columns` registrato | ispezione |
| T9 | Incrocio (§3.7, sprint B2) | vedi T22 del `40`: dialogo dal menu Data e dal menu contestuale, report, errori, Riesegui, testi italiani; catalogo incrociato mandato via SAMP (T21c del `40`) | come T22 e T21c del `40` | test in `tests/ui/test_crossmatch_ui.py` e `tests/ui/test_samp.py` |
| T8 | SAMP (§3.6, sprint B1) | tabella ordinata per una colonna; selezionare righe e mandarle con il menu contestuale a un client simulato; ricevere una selezione | indici inviati nell'ordine della tabella (non mostrato); selezione ricevuta evidenziata con il record; voci spente da scollegati | test in `tests/ui/test_samp.py` |
| T10 | Cone search (§3.8, sprint B3) | vedi T23 del `40`: centro dalla vista, dalla sorgente selezionata e scritto; troncamento; colonne da UCD e dialogo delle colonne; server personale salvato e tolto | come T23 del `40` | `tests/ui/test_vo_queries_ui.py` |
| T11 | Query ADQL (§3.8, sprint B3) | vedi T23 del `40`: query non valida, servizio che rifiuta, sincrona e asincrona, inserimento di centro e raggio, esempi | come T23 del `40`; esempi validati offline con `validate_adql` (test di unità) e eseguiti sui servizi veri (test di rete, marcatore `network`) | `tests/ui/test_vo_queries_ui.py`, `tests/ui/test_adql_examples.py` |

## 13. Decisioni aperte

Nessuna decisione dei Gruppi 1 e 2 aperta.

- **Valori mostrati: DECISI il 2026-10-16** (decisione del proprietario):
  colonne di posizione con `format_coordinates` del 10, magnitudini (UCD
  `phot.mag`) a 3 decimali, valore pieno nel suggerimento e nella copia,
  altre colonne come sono; sostituisce la scelta minore 1 qui sotto
  (§3.2, T5).
- **Scelte minori: CONFERMATE dal proprietario il 2026-10-15:** (1) ~~valori mostrati come sono nella
  tabella, senza sessagesimali nella v1~~ (sostituita il 2026-10-16); (2) ordine delle righe mostrate calcolato nel 42
  con `numpy.argsort(kind="stable")`: è un ordine di presentazione, non un
  valore mostrato, e la tabella non cambia; in alternativa una funzione di
  ordinamento nel 13 (modifica da autorizzare); (3) selezione e ordinamento
  registrati come comandi di classe `session` (rieseguiti alla
  riapertura).
- **Filtro con la grammatica `search` del 13: resta fuori dalla v1**
  (conferma del proprietario del 2026-10-21, richiesta della parte 5:
  "Fuori, come la 42"); si riapre dopo la v1 con D6/D8.
- **Scelte minori di presentazione dello sprint 5a (2026-10-21):
  CONFERMATE dal proprietario il 2026-10-22** (non scritte sopra; nessun
  valore ne dipende):
  (a) cella mancante = trattino "–" nel colore attenuato del tema, con
  "valore mancante" nel suggerimento; NaN e infiniti non mascherati sono
  scritti come sono ("nan"), perché per il 13 non sono mancanti
  (`record_view`); (b) riga non disegnata = numero della riga della tabella
  del 13 nell'intestazione verticale seguito da "◌", con "non disegnata in
  questa vista" nel suggerimento e nel titolo del record (vale per la base
  corrente del `41`, come la scheda della sorgente); (c) clic
  sull'intestazione: salita, poi discesa sulla stessa colonna; nessun
  ritorno all'ordine della tabella nella v1 (`table.sort` non lo prevede);
  (d) un solo `catalog.select` 120 ms dopo l'ultima modifica della
  selezione (clic, ⇧, ⌘, trascinamento), con le righe nell'ordine
  mostrato; (e) riquadro del record a destra della tabella (divisore
  spostabile), con colonne Campo, Valore (pieno), Unità, UCD; con più righe
  dice quante sono selezionate; (f) copia (⌘C): riga d'intestazione
  "nome [unità]" e una riga per ogni riga selezionata con i valori pieni
  separati da tabulazioni; (g) intestazione delle colonne di posizione con
  l'unità del testo del 10 ("h m s", "° ′ ″" o "deg" in decimale), quella
  della colonna nel suggerimento; (h) riga sopra la tabella con livello,
  sorgente, origine, data di recupero, numero di righe e ordinamento.
- **Scelte minori dello sprint 5b (2026-10-22): CONFERMATE dal proprietario
  il 2026-10-22** (§3.5 non dice quando i dialoghi compaiono; nessun valore
  ne dipende): (a) il
  dialogo di **posizione** si apre da solo dopo `catalog.open_file` o
  `catalog.load_region` solo se il 13 non ha determinato colonne e sistema
  (altrimenti non appare, come in §3.5); (b) il dialogo di **moto proprio**
  si apre da solo solo se gli **UCD** indicano sia un moto proprio in RA sia
  uno in Dec (`pos.pm` con `pos.eq.ra`/`pos.eq.dec`, escluse le colonne
  `stat.*`), altrimenti non disturba; (c) il pulsante **"Colonne…"** nella
  riga sopra la tabella apre i due dialoghi in qualsiasi momento (prima
  posizione, poi moto), così la scelta si può rifare e vale anche per
  cataloghi senza UCD; (d) suggerimenti: le ipotesi dai nomi
  (`suggest_position_columns`) sono preselezionate e marcate "da
  confermare", il sistema e l'unità non si indovinano mai (restano da
  scegliere), l'equinozio è richiesto per i frame che ne hanno uno (FK4,
  FK5); (e) il moto proprio si preseleziona **solo dagli UCD** e solo se la
  colonna candidata è una sola; "include cos δ" non è mai preselezionato
  (obbligatorio, `pm_ra_includes_cosdec` del 13); parallasse e velocità
  radiale si usano solo insieme al moto proprio; (f) una sola chiamata di
  `catalog.set_columns` per apertura (posizione e moto insieme); "Salta"
  nel dialogo del moto dopo aver scelto le posizioni conferma comunque le
  posizioni; annullare il dialogo di posizione non registra nulla e il
  catalogo resta in tabella ma non disegnato (§10); (g) il comando è
  registrato con `requested_by` = `mouse`.
- **Da verificare prima del codice:** testi delle licenze di PySide6/Qt
  (LGPL-3) e di pytest-qt (`40` §8).
- **Linee guida visive:** valgono quelle del `40` §3.11 (cifre tabulari
  nelle colonne numeriche, spaziature di 4 punti, accento unico per la
  selezione, modalità notte rossa).

- **D42-1 — Scelte minori dell'incrocio nell'interfaccia (sprint B2):
  PROPOSTE da Claude Code il 2026-11-05, da confermare (Gruppo 3).** (1)
  posizione: Data → Cross-match catalogs… (menu dei dati e dei cataloghi,
  nessun menu nuovo) più il menu contestuale della scheda; (2) report in una
  **finestra non modale** aperta alla fine dell'incrocio chiesto
  dall'utente e riapribile dal menu contestuale, più i dettagli del comando
  (alternativa scartata: scheda fissa nel pannello Tabella, che occupa
  spazio per un testo letto una volta); (3) nessuna voce "in arrivo" per
  incrocio per campo ed ellissi; (4) unità proposte `mas`, `arcsec`,
  `arcmin`, `deg`; (5) sistemi di confronto ICRS e Galattico (quelli della
  vista, `_FRAMES_VIEW` del `05`); (6) nome del nuovo livello
  «A × B · modalità»; (7) un incrocio senza coppie crea comunque il
  livello (vuoto) con `NO_MATCH`, così la riesecuzione dà gli stessi
  livelli.
- **D42-2 — Scelte minori della cone search e della query ADQL (sprint B3):
  PROPOSTE da Claude Code il 2026-11-06, da confermare (Gruppo 3).** (1)
  ordine del menu Data: HiPS survey…, Catalog in view…, Cone search…, ADQL
  query…, separatore, Cross-match catalogs… (prima i modi per portare un
  catalogo, dal più semplice al più esperto, poi le operazioni sui
  cataloghi caricati); (2) commenti `--` tolti prima dell'invio dal 14
  (necessario: Gaia ESA, IRSA e HEASARC rifiutano una query con un
  commento, provato il 2026-11-06) e contati come spazio da `validate_adql`;
  (3) raggio proposto = raggio del campo della vista in arcmin; (4) nomi dei
  livelli «<nome della voce o host> · cone search» e «… · ADQL»; (5)
  identificativi dei miei server `my-<protocollo>-<n>`, nome chiesto con una
  finestra (proposto l'host), elenco salvato in `QSettings`
  (`vo/personal_servers`, JSON); (6) la riesecuzione legge prima la cache
  del 14 (stessa richiesta, `FROM_CACHE` dichiarato; per interrogare di nuovo
  il servizio si svuota la cache del 14 dalle Impostazioni); (7) esempi:
  uno per servizio TAP dell'elenco, senza `TOP` (così decide `max_rows` e il
  troncamento è dichiarato), centrati sulle Pleiadi (M45); (8) valori di
  "Inserisci centro e raggio della vista" con 10 cifre significative, prima
  `CIRCLE('ICRS', …)` del testo o inserimento al cursore, commento in
  inglese (lingua della query) in fondo; (9) sistemi delle coordinate
  scritte ICRS, FK5 J2000.0, Galattico, epoca facoltativa (`null` con il
  motivo); (10) la finestra dell'errore ripete il testo del servizio sotto il
  messaggio, con la sua etichetta; (11) la query si riapre con l'ultimo testo e servizio
  della sessione.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-15 | Claude Code | Creazione del file (stato: bozza) come versione minima approvata dal proprietario il 2026-10-15: tabella in sola lettura con ordinamento (D8), selezione sincronizzata con la vista (D7), vista del record con `record_view` del 13, dialoghi delle colonne di posizione e di moto proprio; fuori dalla v1 ricerca, editor delle regole, colonne calcolate, grafici, SAMP. |
| 2026-10-15 | Claude Code | **Decisioni del proprietario del 2026-10-15:** scelte minori confermate; rimando alle linee guida visive del `40` §3.11. Nessuna decisione dei Gruppi 1 e 2 aperta. |
| 2026-10-16 | Claude Code | **Decisione del proprietario del 2026-10-16** (proposta della fase 1 sull'IA, autorizzazione a modificare la bozza come proposto): valori della tabella — colonne di posizione con `format_coordinates` del 10 nel frame della colonna, magnitudini (UCD `phot.mag`) a 3 decimali, valore pieno nel suggerimento e nella copia, altre colonne come sono; sostituisce la scelta minore 1 del 2026-10-15; dipendenza dal 10; test T5 aggiornato. |
| 2026-10-16 | Claude Code | **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-16. |
| 2026-10-21 | Claude Code | **Codice dello sprint 5a** ("FASE: CODICE – interfaccia v1", parte 5): `src/astrotwo/ui/catalog_panel.py` (`CatalogPanel`, `CatalogTab`, `CatalogTableModel` virtuale con l'ordine di `shown_order` del 05), pannello Tabella del 40 al posto dello stato vuoto; valori di §3.2 (posizioni con `format_coordinates` del 10 nel frame della colonna e nello stile di "Coordinates shown", magnitudini a 3 decimali, formato dichiarato o rappresentazione più breve, valore pieno nel suggerimento e nella copia), ordinamento con `table.sort`, selezione nei due versi con `catalog.select`, record da `record_view` nel risultato del comando, righe non disegnate marcate. Test T1–T6 in `tests/ui/test_catalog_panel.py` (T6 `perf`, misura in §9), modalità notte e punto decimale in italiano. Filtro `search` fuori dalla v1 confermato dal proprietario; scelte minori di presentazione da confermare (§13). Trovato e corretto un difetto del 13 (`record_view` con colonne array). **Resta lo sprint 5b:** dialoghi delle colonne di posizione e di moto proprio (§3.5, `PositionColumnsDialog`, `ProperMotionColumnsDialog`, T7). Stato `approvato` invariato. |
| 2026-10-22 | Claude Code | **Sprint 5b** ("FASE: CODICE – interfaccia v1", parte 5): `PositionColumnsDialog` e `ProperMotionColumnsDialog` in `src/astrotwo/ui/catalog_panel.py`, aperti dalla finestra principale dopo `catalog.open_file`/`catalog.load_region` e dal pulsante "Colonne…" della scheda; un solo `catalog.set_columns` per apertura, nulla assunto (sistema, unità, equinozio e cos δ sempre dichiarati dall'utente; ipotesi dai nomi marcate; moto preselezionato solo dagli UCD). Test T7 e correlati in `tests/ui/test_column_dialogs.py`; traduzioni italiane. **Decisione del proprietario del 2026-10-22:** le 8 scelte di presentazione dello sprint 5a (a–h) sono confermate (tolto "da confermare"). Scelte minori dello sprint 5b da confermare in §13. Stato `approvato` invariato. |
| 2026-10-22 | Claude Code | **Decisione del proprietario del 2026-10-22 (ripresa della parte 6):** confermate le scelte minori dello sprint 5b (§13, tolto "da confermare"). Stato `approvato` invariato. |
| 2026-10-25 | Claude Code | **Sprint 8e (D40-3):** nuova §10.1: il pannello non ha messaggi propri (solo `TABLE_SORT_UNSUPPORTED` del `05`). Stato `approvato` invariato. |
| 2026-11-05 | Claude Code | **Sprint B1 — SAMP nell'interfaccia** (decisioni del proprietario del 2026-11-05, D40-8): l'invio con SAMP esce da "fuori dalla v1" (§3.1); nuova §3.6 (menu contestuale della tabella, indici nell'ordine della tabella, tabella e selezione ricevute); §4 aggiornato; T8 (§12). Stato `approvato` invariato. |
| 2026-11-05 | Claude Code | **Sprint B2 — incrocio per posizione e voci SAMP** (decisioni del proprietario del 2026-11-05, D15-10 del `15`): §3.1; nuova §3.7 (dialogo "Cross-match catalogs…" dal menu Data e dal menu contestuale, report in finestra, nuovo catalogo come gli altri, errori); §3.6 voci «Send whole table via SAMP» e «Send only the selected rows (N) via SAMP», spenta con N = 0; T9 (§12); nuova **D42-1** (scelte minori, da confermare). Stato `approvato` invariato. |
| 2026-11-06 | Claude Code | **Sprint B3 — cone search e query ADQL** (decisioni del proprietario del 2026-11-06): nuovo §3.8 (dialoghi "Cone search…" e "Query ADQL…" del menu Data: servizio dall'elenco del 14 o URL scritto, miei server con `vo.add_server`/`vo.remove_server`, centro della vista/sorgente selezionata/coordinate scritte con sistema ed epoca, raggio con unità, editor a larghezza fissa, esempi, inserimento di centro e raggio della vista, `validate_adql` con la posizione evidenziata, sincrona/asincrona, testo del servizio tale e quale); nuovi T10, T11 (§12); nuova **D42-2** (scelte minori, da confermare). Stato `approvato` invariato. |
