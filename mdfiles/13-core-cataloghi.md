# 13-core-cataloghi.md — cataloghi e tabelle

**Stato:** approvato

## 2. Scopo

Caricare, gestire e interrogare i cataloghi e le tabelle celesti con gli stessi
strumenti di Aladin (filtri, selezioni, moto proprio, ordinamento), tenendo
sempre separate le regole di disegno dalle selezioni dei record.

## 3. Cosa fa

- **Caricamento cataloghi del CDS (D1):** aprire cataloghi noti (Hipparcos,
  TYCHO-2, Gaia, 2MASS, ecc.) per identificatore; il trasferimento dei dati è
  di `14-core-protocolli-vo.md`, qui si gestisce la tabella risultante.
- **Caricamento tabelle da file locale (D2) e da URL (D3):** VOTable, CSV,
  tabelle FITS; lettura dello schema, delle unità e dei nomi delle colonne.
- **Plottaggio come definizione (D4):** regole per simbolo, colore e dimensione
  in funzione delle colonne (es. magnitudine) — questo modulo produce le
  regole; il disegno è di `42-ui-pannello-cataloghi.md`.
- **Filtri e ricerca, due concetti separati (D6, corretto):**
  - i **filtri** decidono **come disegnare** le sorgenti (quali record e con
    quale aspetto);
  - la **selezione dei record per espressione** è il comando **`search`**,
    che restituisce l'insieme dei record che soddisfano un'espressione.
    **Sintassi decisa con D13-1 (2026-10-04):** stringa con **grammatica
    ristretta basata su quella di Aladin**, validata prima dell'esecuzione —
    testo con i jolly `?` e `*`; colonna con gli operatori `=`, `!=`, `<`,
    `>`, `<=`, `>=`; valore assoluto `|colonna|`; prefissi `+` e `-` per
    aggiungere o togliere il record dalla selezione.
- **Propagazione delle posizioni (D9)** e **freccia del moto proprio (D10):**
  portare le posizioni a un'epoca richiesta e rappresentare il moto proprio;
  **epoca di origine letta dai metadati o richiesta, mai assunta** (D10-2),
  moto proprio ed epoca sempre dichiarati nel risultato (calcolo: modulo
  10/Astropy).
- **Strumenti di tabella avanzati (H8):** colonne calcolate, sottoinsiemi,
  grafico x-y, istogramma delle colonne, vista a record, descrizione delle
  colonne; **DataLink: la colonna vive qui, la risoluzione dei link è di
  `14-core-protocolli-vo.md`** (confine deciso con D13-6 il 2026-10-04).
- **Filtro temporale e cursore epoca (H3):** selezionare i record per epoca di
  osservazione e spostare l'epoca di visualizzazione (con i moduli 10 e 41).
  **Epoca di default decisa con D13-2 (2026-10-04):** l'epoca di ogni dato si
  legge dai suoi metadati e **non si assume mai**; epoca di visualizzazione =
  epoca del dato mostrato (per le immagini: epoca dell'immagine se nota,
  altrimenti J2000; per i cataloghi: la **propria epoca di riferimento**);
  **l'epoca usata è sempre scritta nel risultato**.
- **Cache delle interrogazioni (A7):** le interrogazioni ai cataloghi
  (risultati di query, cone search, sottoinsiemi salvati) si conservano in
  **SQLite**, con limite di spazio configurabile, rimozione dei dati meno
  usati, origine e data di scaricamento per ogni voce servita dalla cache.
- **Formati delle tabelle (H22, sez. 8.1 del manuale di Aladin, ed. giugno 2022):**
  VOTable (lettura tramite `14-core-protocolli-vo.md`), tabelle FITS ASCII e
  binarie, CSV, TSV, **BSV** (valori separati da spazi), **IPAC TBL**,
  **formato SExtractor** e **ASTRORES** (predecessore di VOTable, letto per
  compatibilità). La natura del file si riconosce dal contenuto, non
  dall'estensione. Tutti i formati si leggono con `astropy.io.ascii` e
  `astropy.io.fits`, **tranne ASTRORES**, letto da un lettore nel modulo con
  **`defusedxml`** (D13-7, decisa il 2026-10-09; protezione da file XML non
  fidati), testato su file di esempio del CDS; senza documentazione o esempi
  disponibili, il formato dà solo errore. Limite di riferimento di Aladin: meno di
  1 milione di sorgenti per tabella, coerente con l'obiettivo di
  `01-architettura.md` §8.
- **Colonne calcolate (H8, sez. 5.13):** nuova colonna con **nome**
  obbligatorio e, facoltativi, **unità**, **UCD** e **numero di decimali**
  mostrati; espressione con riferimenti alle colonne nella forma
  `${nome_colonna}`, con gli operatori e le funzioni della calcolatrice
  algebrica di `18-core-calcolatrici.md` (stesso elenco e stessa tecnica a
  elenco chiuso, D18-1; nessuna esecuzione di codice). Calcolo vettoriale in
  `float64` con `numpy`; se le colonne hanno unità, il calcolo passa da
  `astropy.units` e unità incompatibili danno errore. La colonna è marcata
  come calcolata, con l'espressione come provenienza, ed è salvata con le
  altre; l'operazione è non distruttiva (D13-5). Dove vive nel codice la
  tabella condivisa delle funzioni (senza creare una dipendenza circolare tra
  13 e 18): D13-8, Gruppo 3.

## 4. Cosa NON fa

- Non comunica con la rete: query, cone search e download sono di
  `14-core-protocolli-vo.md`; il cross-match è di `15-core-crossmatch.md`.
- Non disegna: le tabelle e i simboli li rende la UI (41/42).
- Non esporta i file: l'esportazione è di `14-core-protocolli-vo.md` (D13).
- Non calcola coordinate: propagazione e moto proprio passano per il modulo 10.
- Non produce curve di luce: restano `22-analisi-curve-di-luce.md`.
- Non crea MOC: `16-core-moc.md`.

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `10-core-coordinate-wcs.md` (propagazione, moto proprio,
  coordinate di ricerca), `14-core-protocolli-vo.md` (download e VOTable).
- **Usato da:** `15-core-crossmatch.md`, `16-core-moc.md`,
  `18-core-calcolatrici.md`, `19-core-dati-planetari.md`,
  `20-analisi-fotometria.md`, `42-ui-pannello-cataloghi.md`,
  `41-ui-visualizzatore-cielo.md`, `33-ia-query-adql.md`.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `catalog_id` | stringa | id catalogo CDS | es. "I/239/hip_main" (esempio di formato, id da verificare) |
| in | file / URL tabella | stringa | VOTable, CSV, FITS table | |
| in | `expression` | stringa | espressione sui nomi colonna (comando `search`) | sintassi: grammatica ristretta alla Aladin, validata prima dell'esecuzione (D13-1) |
| in | `filter` | struttura regole | regole di disegno | non è una selezione |
| in | `epoch` | epoca | anno giuliano o ISO 8601 | per propagazione/H3 |
| in | moto proprio | float64 | mas/yr, mas | colonne del catalogo |
| out | tabella | `astropy.table.Table` | colonne con unità e nomi | |
| out | `body` | stringa | `celestial` o nome IAU del corpo | obbligatorio (D19-3): ricavato dal sistema di coordinate delle colonne di posizione o dai metadati planetari, mai assunto |
| out | selezione | indici booleani | — | record soddisfacenti |
| out | cache | record SQLite | origine, data, query, dimensione | A7 |
| in | file tabella | percorso o URL | VOTable, FITS, CSV, TSV, BSV, IPAC TBL, SExtractor, ASTRORES | natura riconosciuta dal contenuto (H22) |
| in | colonna calcolata | nome + espressione + unità, UCD, decimali facoltativi | espressione con `${nome}` | H8 |
| out | colonna calcolata | colonna `float64` con unità, UCD, decimali e provenienza (espressione) | unità dichiarata o derivata | H8 |

## 7. Interfaccia pubblica

- **`CatalogTable`** (classe): tabella con schema, unità e provenienza;
  metodi descrittivi: descrivi colonne, calcola colonna, crea sottoinsieme,
  vista a record.
- **`load_catalog(catalog_id)`** / **`load_table(source)`** — caricamento; la
  rete è gestita dal modulo 14.
- **`search(table, expression)`** — selezione dei record per espressione
  (D6); l'espressione è **validata prima dell'esecuzione** con la grammatica
  ristretta di §3 (D13-1), altrimenti `EXPRESSION_INVALID`; restituisce
  indici/record, non cambia il disegno.
- **`set_plot_rules(table, rules)`** — regole di disegno (D4), separate dalla
  selezione.
- **`propagate(table, epoch)`** — posizioni all'epoca richiesta (D9);
  **calcolo: modulo 10 / Astropy**.
- **`proper_motion_arrows(table, scale)`** — dati per le frecce del moto
  proprio (D10); il disegno è della UI.
- **`calculated_column(table, name, expression, unit, ucd, decimals)`** / **`subset(table, ...)`**
  — colonne calcolate e sottoinsiemi (H8); **calcolo: `numpy`/`astropy`**.
- **`histogram(column)`** / **`xy_plot(x, y)`** — dati per istogramma e
  grafico x-y (H8): il calcolo numerico è del modulo, il disegno della UI.
- **`time_filter(table, range)`** (H3) — selezione per epoca osservativa.
- **`CatalogCache`** (classe) — cache SQLite delle interrogazioni con limite
  configurabile, rimozione dei dati meno usati, origine e data per voce (A7).
- **`read_table(source)`** (H22) — riconosce il formato dal contenuto e
  carica la tabella con unità e provenienza; ASTRORES con il lettore `defusedxml` (D13-7).

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `astropy.table` | rappresentazione delle tabelle con unità | standard del dominio |
| `astropy.io.votable` / `pyvo` (via modulo 14) | lettura dei formati VO | standard VO |
| `numpy` | espressioni su colonne, istogrammi, grafici dati | consolidato |
| `sqlite3` (libreria standard Python) | cache delle interrogazioni (A7) | persistenza semplice e interrogabile |
| `astropy.units` | unità delle colonne | unità esplicite sempre |
| `astropy.io.ascii` | lettura di CSV, TSV, BSV, IPAC TBL e formato SExtractor (H22) | lettori consolidati della comunità |
| `defusedxml` (D13-7) | lettore ASTRORES (H22) protetto contro file XML malevoli | parser XML sicuro per file non fidati; **licenza da verificare prima del codice** |

## 9. Regole e vincoli

- **Filtri ≠ selezioni:** confondere i due è un errore di progettazione
  (correzione D6 di `03-parita-aladin.md`); le API li tengono separati.
- Unità e nomi delle colonne conservati dal sorgente; una colonna senza unità
  è dichiarata "unitless" e non convertita silenziosamente.
- La propagazione delle posizioni usa solo il modulo 10; **epoca di origine e
  moto proprio si leggono dai metadati o sono richiesti, mai assunti**
  (D10-2/D13-2); ogni catalogo dichiara la **propria epoca di riferimento**;
  l'epoca usata è sempre scritta nel risultato.
- La cache SQLite registra query, data e origine; nessun dato è servito
  senza provenienza (A7).
- Le espressioni `search` sono valutate in codice deterministico (non da un
  modello linguistico) e **validate prima dell'esecuzione** con la grammatica
  ristretta decisa (D13-1): testo con `?`/`*`, operatori `=`, `!=`, `<`, `>`,
  `<=`, `>=`, valore assoluto `|colonna|`, prefissi `+`/`-`.
- **Operazioni sulle tabelle (D13-5, decisa il 2026-10-04):** sempre **non
  distruttive**; la modifica in posto (`in-place`) solo con **flag esplicito
  citato nel report** — nessuna perdita di dati silenziosa, piena
  riproducibilità.

- **Corpo di riferimento (`body`, D19-3 decisa il 2026-10-08):** ogni tabella porta
  nei metadati il campo **obbligatorio** `body`. Per i dati astronomici vale
  `celestial` (sfera celeste) ed è **ricavato dal sistema di coordinate
  dichiarato** (es. ICRS, galattico, eclittico), **mai assunto**; per i dati
  planetari è il corpo letto dai metadati secondo
  `19-core-dati-planetari.md`. Se `body` non si può ricavare, il dato si apre
  ma non si sovrappone né si combina con altri (`BODY_UNKNOWN`); la
  sovrapposizione tra corpi diversi segue D19-4 (`BODY_MISMATCH`, forzabile
  solo con opzione esplicita citata nel risultato).

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Catalogo sconosciuto | errore con riferimento all'id | `CATALOG_UNKNOWN` |
| Tabella senza colonne coordinate | caricamento riuscito, funzioni di posizione disabilitate con avviso | `NO_COORD_COLUMNS` |
| Espressione `search` sintatticamente errata | rifiuto con la posizione dell'errore nell'espressione | `EXPRESSION_INVALID` |
| Mancano le colonne di moto proprio per la propagazione | errore che indica le colonne mancanti | `PROPER_MOTION_MISSING` |
| Epoca richiesta non valida | rifiuto dell'input | `EPOCH_INVALID` |
| Cache SQLite non scrivibile o corrotta | la cache viene ricreata/ignorata con avviso; il dato è riletto dal sorgente | `CACHE_UNAVAILABLE` |
| Cache oltre il limite | rimozione dei record meno usati, registrata | `CACHE_FULL` |
| Tipo colonna non supportato per un'operazione | errore con tipo atteso e trovato | `COLUMN_TYPE_UNSUPPORTED` |
| Corpo (`body`) non ricavabile dai metadati né dal sistema di coordinate | dato aperto da solo, non sovrapposto né combinato | `BODY_UNKNOWN` |
| Formato di tabella non riconosciuto | elenco dei formati supportati | `FORMAT_UNSUPPORTED` |
| File ASTRORES non conforme, o lettore non disponibile per mancanza di documentazione ed esempi | rifiuto esplicito con la causa | `ASTRORES_UNREADABLE` |
| File XML con costrutti pericolosi (es. espansione di entità) | lettura interrotta, nessun dato caricato | `XML_UNSAFE` |
| Espressione di colonna non valida o colonna citata inesistente | rifiuto con la posizione dell'errore o il nome mancante | `COLUMN_EXPRESSION_INVALID` |
| Nome della nuova colonna già presente | rifiuto, nessuna sovrascrittura silenziosa | `COLUMN_NAME_EXISTS` |
| Unità incompatibili nell'espressione | rifiuto con le due unità | `UNIT_INCOMPATIBLE` |

## 11. Esposizione all'IA

- **`describe_table`** — output: schema, unità, numero di righe, provenienza.
- **`search`** — input: tabella + espressione; output: record/indici.
  **Calcolo: motore di espressioni del modulo (numpy/astropy), mai l'IA.**
- **`get_column_statistics`** — input: colonna; output: min, max, media,
  deviazione standard, conteggio. **Calcolo: `numpy`/`astropy.stats`.**
- **`propagate`** — input: tabella + epoca; output: posizioni propagate.
  **Calcolo: modulo 10 / Astropy.**

L'IA scrive la richiesta e spiega il risultato; i numeri vengono sempre da
questi strumenti deterministici e poi verificati da
`34-ia-verifica-risultati.md`.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Caricamento VOTable | caricare un VOTable di prova | nomi colonne, unità e numero righe coincidono con quelli letti direttamente con `astropy.io.votable` nel test | ricalcolo con Astropy |
| T2 | `search` vs filtri | applicare un filtro di disegno ed eseguire una `search` | il filtro non cambia i record della tabella; la `search` restituisce solo i record che soddisfano l'espressione (confronto con `numpy` ricalcolato nel test) | confronto con `numpy` |
| T3 | Propagazione | propagare 100 posizioni con moto proprio dichiarato a un'epoca +10 anni | coincidenza con `SkyCoord.apply_space_motion` ricalcolato nel test (tolleranza 1e-9 gradi) | ricalcolo con Astropy |
| T4 | Colonna calcolata | calcolare una colonna `mag_bright = mag < 10` (esempio) su una tabella di prova | risultato coincidente con `numpy` ricalcolato nel test | confronto con `numpy` |
| T5 | Istogramma | istogramma di una colonna con bin noti | conteggi coincidenti con `numpy.histogram` ricalcolato nel test | ricalcolo con NumPy |
| T6 | Cache SQLite con provenienza | eseguire due volte la stessa interrogazione | seconda lettura dalla cache con origine e data valorizzate e invariate | lettura record SQLite |
| T7 | Moto proprio mancante | chiedere la propagazione senza colonne di moto proprio | `PROPER_MOTION_MISSING`, nessun valore inventato | test di unità |
| T8 | IPAC TBL (H22) | leggere un file IPAC di prova | colonne, unità e valori uguali a quelli letti con `astropy.io.ascii` (formato `ipac`) | confronto con `astropy.io.ascii` |
| T9 | SExtractor (H22) | leggere un catalogo SExtractor di prova | colonne e valori uguali a `astropy.io.ascii` (formato `sextractor`) | confronto con `astropy.io.ascii` |
| T10 | BSV (H22) | leggere una tabella separata da spazi | colonne e valori uguali a `astropy.io.ascii` con separatore spazio | confronto con `astropy.io.ascii` |
| T11 | Riconoscimento dal contenuto (H22) | una VOTable con estensione `.csv` | letta come VOTable | test di unità |
| T12 | Colonna calcolata (H8) | colonne `B` e `V` in magnitudini; nuova colonna `B-V` con espressione `${B} - ${V}`, UCD e 3 decimali | valori = `B - V` calcolati con `numpy`; UCD, decimali e provenienza registrati; tabella originale invariata | ricalcolo con `numpy` |
| T13 | Espressione non valida (H8) | espressione con una colonna inesistente o con un nome non previsto | `COLUMN_EXPRESSION_INVALID`, nulla eseguito | test di unità |
| T14 | Unità incompatibili (H8) | somma di una colonna in gradi e una in magnitudini | `UNIT_INCOMPATIBLE` | test di unità |
| T15 | ASTRORES (H22) | leggere un file ASTRORES di esempio del CDS | colonne, unità e valori coerenti con la VOTable equivalente dello stesso catalogo | confronto con la VOTable (file di esempio **da reperire**) |
| T16 | XML malevolo (H22) | leggere un file ASTRORES con espansione di entità | `XML_UNSAFE`, nessun dato caricato | test di unità |

## 13. Decisioni aperte

- **D13-1 — Sintassi delle espressioni `search`: DECISA il 2026-10-04.**
  **Stringa con grammatica ristretta basata su quella di Aladin:** testo con i
  jolly `?` e `*`; colonna con gli operatori `=`, `!=`, `<`, `>`, `<=`, `>=`;
  valore assoluto `|colonna|`; prefissi `+` e `-` per aggiungere o togliere
  dalla selezione; **validata prima dell'esecuzione** (`EXPRESSION_INVALID`).
  **Motivazione:** fedeltà al comportamento "espressioni" di Aladin (D6) e un
  solo validatore deterministico per UI, IA (§11) e pipeline. Applicata in
  §3/§6/§7/§9 qui sopra.
- **D13-2 — Epoca di default per H3 (cursore epoca): DECISA il 2026-10-04,
  insieme a D10-2.** Epoca di ogni dato **letta dai metadati e mai assunta**;
  epoca di visualizzazione = epoca del dato mostrato (immagine: epoca
  dell'immagine se nota, altrimenti J2000; cataloghi: **propria epoca di
  riferimento**); **l'epoca usata è sempre scritta nel risultato**.
  **Motivazione:** una sola convenzione d'epoca per tutto il progetto
  (DC2 di `02-convenzioni.md`), con valore sempre dichiarato (regola d'oro
  n. 6). Applicata in §3/§9 qui sopra.
- **D13-3 — Cataloghi predefiniti (D1): DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** **albero dinamico delle
  collezioni ordinato per popolarità**, come Aladin (sez. 5.1.1), con un
  piccolo gruppo fisso: Simbad, Gaia, 2MASS (identificativi esatti **da
  verificare prima del codice**).
- **D13-4 — Limite di righe in memoria:** tetto massimo di righe caricate per
  tabella (con caricamento progressivo oltre il limite). Valore: da decidere.
- **D13-5 — Comportamento delle operazioni in posto: DECISA il 2026-10-04.**
  Operazioni **sempre non distruttive**; modifica `in-place` solo con **flag
  esplicito citato nel report**. **Motivazione:** nessuna perdita di dati,
  riproducibilità (regola d'oro n. 6) e coerenza con `15`, `16`, `17` che
  dichiarano di non modificare la sorgente. Applicata in §9 qui sopra.
- **D13-6 — Colonne di DataLink: DECISA il 2026-10-04.** **Colonna nel 13,
  risoluzione dei link nel `14-core-protocolli-vo.md`.** **Motivazione:**
  nessuna duplicazione di client VO, coerente con D14-3 e con il perimetro
  "protocolli VO" del 14. Applicata in §3 qui sopra.
- **D13-7 — Lettore ASTRORES (H22): DECISA il 2026-10-09 (decisione del
  proprietario).** Lettore nel modulo con **`defusedxml`** (non il parser XML
  della libreria standard, per sicurezza su file non fidati), testato su file
  di esempio del CDS; senza documentazione o esempi, solo errore
  (`ASTRORES_UNREADABLE`). **Da verificare prima del codice:** licenza di
  `defusedxml`, disponibilità di documentazione ed esempi ASTRORES.
- **D13-8 — Posizione della tabella delle funzioni condivisa con il 18:**
  dove tenere nel codice l'elenco unico di operatori e funzioni usato da
  colonne calcolate (13) e calcolatrice algebrica (18) senza dipendenza
  circolare. Da fissare al momento del codice (Gruppo 3).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario: D13-1, D13-2, D13-5 e D13-6 passate da aperte a decise.** D13-1: grammatica `search` ristretta alla Aladin (`?`/`*`, `=`/`!=`/`<`/`>`/`<=`/`>=`, `\|colonna\|`, prefissi `+`/`-`), validata prima dell'esecuzione (§3/§6/§7/§9). D13-2: epoca dai metadati, mai assunta, epoca di visualizzazione = epoca del dato (immagine se nota, altrimenti J2000; cataloghi con propria epoca di riferimento), epoca sempre scritta nel risultato (§3/§9; insieme a D10-2 e a DC2). D13-5: operazioni sempre non distruttive, in-place solo con flag esplicito citato nel report (§9). D13-6: colonna DataLink nel 13, risoluzione nel 14 (§3). Decisioni riportate in `decisioni-aperte.md`. |
| 2026-10-08 | Claude Code | §5: aggiunti a "Usato da" i moduli `18-core-calcolatrici.md` e `19-core-dati-planetari.md` (scritti il 2026-10-08, stato bozza). Nessun altro testo cambia. |
| 2026-10-09 | Claude Code | **D19-3 applicata (decisione del proprietario del 2026-10-08):** campo `body` obbligatorio nei metadati di ogni tabella (§6, §9, §10); per i dati astronomici `celestial`, ricavato dal sistema di coordinate, mai assunto; errori `BODY_UNKNOWN` e, per le sovrapposizioni, `BODY_MISMATCH` secondo D19-4 (forzabile solo con opzione esplicita citata nel risultato). |
| 2026-10-09 | Claude Code | **D13-3 DECISA** (checklist del livello 1): albero dinamico ordinato per popolarità con gruppo fisso Simbad, Gaia, 2MASS. |
| 2026-10-09 | Claude Code | **Completamento con gli esiti di AP5** (decisione del proprietario del 2026-10-09): §3, §6, §7, §8, §10, §12 per H22 (formati CSV, TSV, BSV, IPAC TBL, SExtractor con `astropy.io.ascii`; ASTRORES; riconoscimento dal contenuto) e H8 (colonne calcolate con unità, UCD, decimali ed espressioni `${colonna}` con la tecnica di D18-1). Nuove decisioni: **D13-7** (lettore ASTRORES, Gruppo 2) e D13-8 (Gruppo 3). Il modulo resta in `bozza`. |
| 2026-10-09 | Claude Code | **D13-7 DECISA** (decisione del proprietario): lettore ASTRORES con `defusedxml` (licenza da verificare), testato su esempi del CDS, altrimenti solo errore. §3, §7, §8, §10 (`ASTRORES_UNREADABLE`, `XML_UNSAFE`), §12, §13 aggiornati. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** (regola del proprietario del 2026-10-09): nessuna decisione aperta nei Gruppi 1 e 2. |
