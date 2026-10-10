# 15-core-crossmatch.md — incrocio tra cataloghi

**Stato:** approvato

## 2. Scopo

Incrociare due tabelle celesti per due strade (calcolo locale e servizio
CDS XMatch), restituendo risultati riproducibili e con la dichiarazione
esplicita dei criteri usati.

## 3. Cosa fa

- **Cross-match locale (tra due tabelle):** incrociare due tabelle già in
  memoria, con tre modalità:
  - **tutte** (`all`): tutte le coppie entro la distanza massima;
  - **migliore** (`best`): per ogni record della tabella A il candidato più
    vicino;
  - **nessuna** (`none`): solo i record di A senza corrispondente in B (non
    appaiati).
  **Distanza massima (raggio): obbligatoria, senza default** (decisione del
  proprietario del 2026-10-10), con unità esplicita: il raggio giusto dipende
  dalla precisione astrometrica dei due cataloghi, che solo l'utente conosce
  per il suo caso; un valore implicito darebbe coppie diverse senza che
  l'utente lo abbia scelto. Senza raggio: `MAX_SEP_INVALID`.
- **Cross-match tramite servizio CDS:** stessa interfaccia, esecuzione remota
  sui servizi del CDS; parametri e risultato registrati per la riproducibilità.
- **Report dei criteri:** ogni risultato riporta modalità, distanza massima,
  sistema di riferimento, epoca e servizio/URL usati.
- **Distanze di appaiamento:** per ogni coppia si riporta la separazione
  angolare calcolata con il modulo 10 (`astropy.coordinates`).
- **Correlazione per campo (E3, sez. 5.11 del manuale di Aladin, ed. giugno 2022):**
  incrocio di due tabelle per **valori identici** in una colonna di ciascuna
  (es. un identificatore: in termini di basi di dati un *join*), con
  `astropy.table.join`. Modalità: coppie (join interno) oppure record senza
  corrispondenza (`none`). Chiavi ripetute: si producono tutte le
  combinazioni e il report ne dichiara il numero. Le colonne chiave devono
  avere tipo compatibile.
- **Correlazione con ellissi d'errore (E3):** come la correlazione per
  posizione, ma per ciascuna tabella si indicano anche le tre colonne
  dell'ellisse d'errore di posizione: **asse maggiore**, **asse minore** e
  **orientamento rispetto al nord**, con unità. Due sorgenti sono
  associate se la loro **distanza normalizzata** con la **covarianza combinata**
  delle due ellissi (distanza di Mahalanobis) non supera una **soglia
  dichiarata in sigma** (D15-5, decisa il 2026-10-09). Il valore predefinito
  della soglia è D15-6 (Gruppo 3). Il criterio è nostro e scritto per intero
  nel report (formula, covarianza, soglia).
- **Scelta delle colonne da conservare (E3):** per default tutte le colonne
  delle due tabelle, con suffissi `_tab1` e `_tab2` sui nomi in conflitto;
  l'utente può scegliere le colonne e i prefissi o suffissi. Nessuna
  rinomina silenziosa: il report elenca le rinomine.
- **Corrispondenza delle colonne tramite UCD (E3):** le colonne di posizione
  (e d'errore) si propongono in base agli UCD (es. `pos.eq.ra`,
  `pos.eq.dec`); se un UCD che deve essere unico (marcato come principale,
  `meta.main`) compare in entrambe le tabelle, il conflitto è segnalato e
  prevale la prima tabella salvo scelta esplicita dell'utente.

## 4. Cosa NON fa

- Non scarica i cataloghi: il download è di `14-core-protocolli-vo.md`.
- Non esegue query ADQL né MOC (14 e 16).
- Non decide quale catalogo usare (13).
- Non propone soglie "intelligenti": la distanza massima è un parametro
  obbligatorio dell'utente, senza default.
- Non produce valori di probabilità statistica non richiesti dalla modalità
  scelta.

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `10-core-coordinate-wcs.md` (separazioni angolari, frame),
  `13-core-cataloghi.md` (tabelle in ingresso), `14-core-protocolli-vo.md`
  (servizio CDS, registrazione dei parametri).
- **Usato da:** `42-ui-pannello-cataloghi.md`, `50-avanzate-transienti.md`,
  `20-analisi-fotometria.md` (associazione delle sorgenti).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `table_a`, `table_b` | `astropy.table.Table` | con colonne coordinate | per il locale |
| in | `mode` | enumerativo | `all` / `best` / `none` | modalità (tutte/migliore/nessuna) |
| in | `max_sep` | float64 (`Quantity`) | angolo con unità, **obbligatorio, senza default** | distanza massima |
| in | `frame` | enumerativo | ICRS di default | sistema usato per il confronto |
| in | `service_url` | stringa | URL servizio CDS | solo per il remoto |
| out | coppie | tabella | indici A, indici B, separazione in arcsec | |
| out | non appaiati | tabella | indici A senza B | modalità `none` |
| out | report | struttura | modalità, soglia, frame, epoca, `body`, eventuale forzatura, servizio, timestamp | per riproducibilità |
| in | `key_a`, `key_b` | nomi di colonna | tipo compatibile | correlazione per campo (E3) |
| in | colonne dell'ellisse d'errore | 3 nomi di colonna per tabella | asse maggiore, asse minore (`Quantity` angolare), orientamento in gradi da nord verso est | correlazione con ellissi (E3) |
| in | `keep_columns`, `suffixes` | liste di stringhe | default: tutte, `_tab1` / `_tab2` | scelta delle colonne (E3) |
| out | colonne proposte | struttura | colonne di posizione/errore proposte via UCD, conflitti di UCD | E3 |
| in | `threshold` | float64 | sigma (adimensionale) | correlazione con ellissi; default: D15-6 |

## 7. Interfaccia pubblica

- **`crossmatch(table_a, table_b, mode, max_sep)`** — incrocio locale;
  restituisce coppie + report. Calcolo: `astropy.coordinates.search_around_sky`
  (o equivalente Astropy) — mai implementazioni approssimate scritte a mano.
- **`crossmatch_cds(table_a, table_b, mode, max_sep, service)`** — incrocio
  tramite servizio CDS; restituisce lo stesso schema di uscita.
- **`CrossMatchResult`** (classe): risultato con coppie, non appaiati, report
  dei criteri; metodi descrittivi per applicare una soglia diversa e
  rieseguire (senza ricaricare i dati).
- **`crossmatch_by_field(table_a, table_b, key_a, key_b, mode)`** (E3) —
  join su valori identici con `astropy.table.join`; restituisce lo stesso
  `CrossMatchResult` (senza separazioni).
- **`crossmatch_ellipses(table_a, table_b, ellipse_a, ellipse_b, threshold)`**
  (E3) — correlazione con ellissi d'errore: distanza di Mahalanobis
  con covarianza combinata, `threshold` in sigma (D15-5).
- **`suggest_columns(table)`** (E3) — colonne di posizione ed errore proposte
  in base agli UCD, con i conflitti trovati.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `astropy.coordinates` (`search_around_sky`) | incrocio locale per separazione angolare | algoritmi verificati della comunità |
| `astroquery.xmatch` (D15-2, decisa) | servizio CDS x-match | client ufficiale del servizio; vedi §13 |
| `astropy.table` | tabelle in ingresso e uscita | unità e metadati |
| `astropy.table.join` | correlazione per campo (E3) | funzione consolidata di `astropy.table` |

## 9. Regole e vincoli

- **Distanza massima: obbligatoria, senza default** (decisione del
  proprietario del 2026-10-10). **Modalità predefinita: `best`** (D15-1,
  motivazione in §13).
- Le separazioni sono calcolate da Astropy in `float64`; soglia espressa con
  unità.
- Nessun incrocio è eseguito se i frame delle due tabelle non sono noti:
  conversione esplicita con il modulo 10 prima del confronto.
- Il report dei criteri accompagna sempre il risultato (riproducibilità).
- Il cross-match remoto registra servizio, parametri e timestamp.
- **Corpo di riferimento (D19-3, esteso al 15 il 2026-10-09):** si incrociano
  solo tabelle con lo stesso `body` (campo obbligatorio del modulo 13); corpi
  diversi danno `BODY_MISMATCH`, forzabile solo con un'opzione esplicita
  citata nel report (D19-4, stesso schema di D13-5).
- Le due modalità (locale e CDS) devono produrre risultati coerenti sullo
  stesso input: divergenze > soglia dichiarata = anomalia (test T4).

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Nessuna coppia entro la soglia | risultato vuoto con conteggio 0, non è un errore | esito `NO_MATCH` |
| Tabella senza colonne coordinate | rifiuto prima del calcolo | `NO_COORD_COLUMNS` |
| Frame sconosciuto per una tabella | errore che chiede il frame | `FRAME_UNKNOWN` |
| Soglia mancante, senza unità angolare, non positiva o fuori range | rifiuto dell'input | `MAX_SEP_INVALID` |
| Servizio CDS non raggiungibile | errore di rete; si propone di riprovare o usare il locale | `NET_TIMEOUT` |
| Tabelle molto grandi (oltre 1 milione di righe, D15-3) | errore con il tetto dichiarato; proposta del servizio CDS o dell'elaborazione a blocchi; mai troncamento silenzioso | `TABLE_TOO_LARGE` |
| Tabelle di corpi diversi (`body` diverso, D19-3) | incrocio rifiutato; forzabile solo con opzione esplicita citata nel report (D19-4) | `BODY_MISMATCH` |
| Tabella con `body` non ricavabile | incrocio rifiutato | `BODY_UNKNOWN` |
| Colonna chiave mancante o di tipo incompatibile | rifiuto prima del calcolo | `KEY_COLUMN_INVALID` |
| Ellisse d'errore non valida (assi negativi o nulli, asse minore > asse maggiore, unità mancanti) | rifiuto con la riga e la colonna | `ERROR_ELLIPSE_INVALID` |
| Conflitto di UCD principali tra le due tabelle | avviso; prevale la prima tabella salvo scelta esplicita | `UCD_CONFLICT` |
| Ellissi con covarianza combinata singolare (es. assi nulli) | coppia esclusa con avviso, mai una distanza infinita silenziosa | `ERROR_ELLIPSE_INVALID` |

## 11. Esposizione all'IA

- **`crossmatch`** — input: due tabelle (o i loro riferimenti in memoria),
  modalità, soglia con unità; output: coppie + separazioni + report.
  **Calcolo: `astropy.coordinates`, mai l'IA.**
- **`crossmatch_cds`** — stesso input/output con servizio remoto dichiarato.
- **`describe_match_report`** — output: criteri usati (testo per l'utente).

L'IA sceglie la modalità e la soglia e spiega il risultato; non produce le
coppie né le separazioni.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Coppia nota | due tabelle ciascuna con una sorgente separata da 5 arcsec, soglia 10 arcsec, modalità `best` | 1 coppia, separazione ≈ 5 arcsec | separazione ricalcolata nel test con `astropy.coordinates.angular_separation` |
| T2 | Soglia superata | stesse tabelle con soglia 1 arcsec | 0 coppie, esito `NO_MATCH` | test di unità |
| T3 | Modalità `none` | tabella A con 10 sorgenti, B con 3 coincidenti | 7 record non appaiati | confronto con `numpy` ricalcolato nel test |
| T4 | Coerenza locale vs CDS | stesso input piccolo nelle due modalità (test di rete separato) | stesse coppie, entro la tolleranza del servizio | confronto diretto tra i due esiti |
| T5 | Frame diversi | una tabella in ICRS e una in galattico | incrocio riuscito dopo conversione, risultato coincidente con l'incrocio fatto dopo aver convertito entrambe manualmente nel test | ricalcolo con Astropy |
| T6 | Report di criteri | eseguire un incrocio | il report riporta modalità, soglia (con unità), frame, servizio e timestamp | controllo del contenuto |
| T7 | Corpi diversi | incrociare una tabella celeste con una tabella di Marte (dati di prova) | `BODY_MISMATCH`, nessuna coppia | test di unità |
| T8 | Forzatura | ripetere T7 con l'opzione di forzatura | incrocio eseguito; il report cita la forzatura e i corpi coinvolti | controllo del report |
| T9 | Correlazione per campo (E3) | due tabelle con una colonna identificatore, 3 valori in comune | 3 coppie; con `none` i record senza corrispondenza | confronto con `astropy.table.join` nel test |
| T10 | Chiavi ripetute (E3) | identificatore ripetuto 2 volte in A e 2 in B | 4 combinazioni, numero dichiarato nel report | test di unità |
| T11 | Ellisse non valida (E3) | asse minore maggiore dell'asse maggiore | `ERROR_ELLIPSE_INVALID` | test di unità |
| T12 | Correlazione con ellissi (E3) | coppie sintetiche con ellissi note | associate solo le coppie con distanza di Mahalanobis (covarianza combinata) ≤ soglia; distanze riportate nel risultato | ricalcolo nel test con `numpy` (matrici di covarianza dalle ellissi) |
| T13 | Suffissi e UCD (E3) | due tabelle con colonne omonime e UCD `pos.eq.ra`/`pos.eq.dec` | colonne in conflitto con `_tab1`/`_tab2`; colonne di posizione proposte dagli UCD; rinomine nel report | controllo del risultato |
| T14 | Raggio obbligatorio | incrocio senza `max_sep`, con un numero senza unità, con un'unità non angolare | `MAX_SEP_INVALID` in tutti i casi, nessun incrocio eseguito | test di unità |

## 13. Decisioni aperte

- **D15-1 — Modalità predefinita: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1; motivazione riscritta il
  2026-10-10, regola d'oro n. 8).** **`best`** (sorgente più vicina).
  **Motivazione (nostra):** è il caso d'uso più comune — trovare per ogni
  sorgente di A la sua controparte in B — e dà al più una riga per record di
  A, quindi un risultato che si confronta direttamente con la tabella di
  partenza senza altri filtri; le altre modalità restano a un parametro di
  distanza e la modalità usata è sempre nel report.
- **D15-2 — Libreria per il servizio CDS: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** **`astroquery.xmatch`**,
  client ufficiale del servizio CDS XMatch; modalità supportate **da
  verificare prima del codice**.
- **D15-3 — Tetto dimensionale: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** tetto = **1 milione di righe
  per tabella** (obiettivo di `01-architettura.md` §8); oltre il tetto si
  propone il servizio CDS o l'elaborazione a blocchi, **mai un troncamento
  silenzioso**.
- **D15-4 — Probabilità di associazione: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** **no nel livello 1**: solo
  separazioni (ed ellissi, riga E3). **Motivazione (nostra):** una
  probabilità di associazione richiede un modello statistico (densità delle
  sorgenti, distribuzione degli errori, ipotesi a priori) che è una scelta di
  analisi; una stima con metodo dichiarato potrà essere un modulo del
  livello 2.
- **D15-5 — Criterio della correlazione con ellissi d'errore (E3): DECISA il
  2026-10-09 (decisione del proprietario).** **Distanza normalizzata con
  covarianza combinata** delle due ellissi (distanza di Mahalanobis), **soglia
  dichiarata in sigma**; valore predefinito della soglia in D15-6 (Gruppo 3).
  Criterio nostro, scritto per intero nel report (2026-10-10: tolto il
  confronto con il criterio di Aladin, regola d'oro n. 8).
- **D15-6 — Soglia predefinita della correlazione con ellissi:** valore in
  sigma usato quando l'utente non lo indica. Da fissare al momento del codice
  (Gruppo 3).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). Distanza massima predefinita 4 arcsec e modalità tutte/migliore/nessuna da `03-parita-aladin.md` E3. |
| 2026-10-09 | Claude Code | **D15-1…D15-4 DECISE** (checklist del livello 1): default `best` (default di Aladin da verificare); `astroquery.xmatch`; tetto 1 milione di righe per tabella senza troncamenti silenziosi; nessuna probabilità nel livello 1. **D19-3 estesa al 15** (decisione del proprietario): incrocio solo tra tabelle con lo stesso `body`, errori `BODY_MISMATCH`/`BODY_UNKNOWN`, forzatura come D19-4, test T7–T8. §6, §8, §9, §10, §12 aggiornati. |
| 2026-10-09 | Claude Code | **Completamento con gli esiti di AP5** (decisione del proprietario del 2026-10-09): §3, §6, §7, §8, §10, §12 per E3 (correlazione per campo con `astropy.table.join`, correlazione con ellissi d'errore, scelta delle colonne con suffissi, corrispondenza tramite UCD). Nuova decisione del Gruppo 2 **D15-5** (criterio delle ellissi): il modulo resta in `bozza`. |
| 2026-10-09 | Claude Code | **D15-5 DECISA** (decisione del proprietario): distanza di Mahalanobis con covarianza combinata e soglia in sigma; criterio di Aladin da verificare con differenza dichiarata. Nuova D15-6 (soglia predefinita, Gruppo 3). §3, §6, §7, §10, §12, §13 aggiornati. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** (regola del proprietario del 2026-10-09): nessuna decisione aperta nei Gruppi 1 e 2. |
| 2026-10-10 | Claude Code | **Regola d'oro n. 8** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): distanza massima **obbligatoria, senza default** (tolto il default di 4 arcsec preso da Aladin) in §3, §4, §6, §9, §10 (`MAX_SEP_INVALID` anche se manca), nuovo test T14; modalità `best` con motivazione nostra (D15-1); D15-4 e D15-5 senza riferimenti ad Aladin; §2 e §3 senza "come Aladin". Stato `approvato` invariato. |
