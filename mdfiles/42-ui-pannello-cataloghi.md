# 42-ui-pannello-cataloghi.md — pannello cataloghi e tabelle

**Stato:** bozza

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
- **Valori:** come sono nella tabella, senza conversioni né unità
  cambiate (scelta minore 1): numeri con il formato dichiarato dalla
  colonna se c'è (`precision`/`width` del VOTable, formato FITS),
  altrimenti con la rappresentazione più breve che si rilegge identica,
  sempre con il punto decimale (`40` §3.9); valori mancanti come cella
  vuota con un segno grafico; il valore pieno si copia (`02` §6).
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
- Non converte unità né scrive coordinate in sessagesimale nella tabella
  (v1).
- Non disegna le sorgenti (`41`) e non interroga servizi (13, 14).
- Non salva sottoinsiemi né esporta tabelle (fuori dalla v1).

## 5. Livello e dipendenze

- **Livello:** interfaccia; nella v1 usa solo il livello 1.
- **Dipende da:** `05-comandi-sessione.md` (comandi `table.sort`,
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

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Colonna con tipo non ordinabile (es. array) | ordinamento rifiutato con messaggio | `TABLE_SORT_UNSUPPORTED` |
| Valori mancanti nella colonna ordinata | in fondo, in entrambi i versi | — |
| Colonne di posizione non confermate | catalogo aperto in tabella ma non disegnato nel `41`, avviso | codice del 13 |
| Riga selezionata non disegnabile | selezionata qui, marcata "non disegnata" | — |
| Livello rimosso nel `41` | scheda chiusa | — |

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
| T5 | Valori mostrati | colonne con formato dichiarato, senza formato, mancanti | testo secondo §3.2, sempre con il punto decimale anche in italiano | lettura del modello |
| T6 | Un milione di righe | tabella sintetica di 1 000 000 di righe | apertura senza copia dei dati; memoria aggiuntiva e tempo di ordinamento misurati e riportati (`perf`) | misura |
| T7 | Colonne all'apertura | CSV senza UCD; scelta delle colonne di moto proprio | `confirm_position_columns` chiamata con le colonne confermate; `catalog.set_columns` registrato | ispezione |

## 13. Decisioni aperte

Nessuna decisione aperta nuova oltre alle scelte minori.

- **Scelte minori da confermare:** (1) valori mostrati come sono nella
  tabella (formato della colonna o rappresentazione più breve), senza
  sessagesimali nella v1; (2) ordine delle righe mostrate calcolato nel 42
  con `numpy.argsort(kind="stable")`: è un ordine di presentazione, non un
  valore mostrato, e la tabella non cambia; in alternativa una funzione di
  ordinamento nel 13 (modifica da autorizzare); (3) selezione e ordinamento
  registrati come comandi di classe `session` (rieseguiti alla
  riapertura).
- **Da verificare prima del codice:** licenze di PySide6/Qt e di
  pytest-qt (`40` §8).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-15 | Claude Code | Creazione del file (stato: bozza) come versione minima approvata dal proprietario il 2026-10-15: tabella in sola lettura con ordinamento (D8), selezione sincronizzata con la vista (D7), vista del record con `record_view` del 13, dialoghi delle colonne di posizione e di moto proprio; fuori dalla v1 ricerca, editor delle regole, colonne calcolate, grafici, SAMP. |
