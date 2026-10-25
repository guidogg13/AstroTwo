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
  x-y (H8), DataLink, esportazione delle tabelle, invio con SAMP (G3).

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

## 4. Cosa NON fa

- Non modifica le tabelle (sola lettura, D13-5) e non calcola valori,
  colonne o statistiche (13).
- Non converte unità né frame; le coordinate delle colonne di posizione le
  scrive il 10 (`format_coordinates`), non questo modulo.
- Non disegna le sorgenti (`41`) e non interroga servizi (13, 14).
- Non salva sottoinsiemi né esporta tabelle (fuori dalla v1).

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
