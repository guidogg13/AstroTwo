# 15-core-crossmatch.md — incrocio tra cataloghi

**Stato:** approvato

## 2. Scopo

Incrociare due tabelle celesti per due strade (calcolo locale e servizio
CDS XMatch), restituendo risultati riproducibili e con la dichiarazione
esplicita dei criteri usati.

## 3. Cosa fa

**Divisione del codice (decisione del proprietario del 2026-10-11):** cinque
parti, in quest'ordine, ciascuna con verifiche, codice, test di tutto il
progetto e commit — **P1** incrocio locale `all`/`best`/`none`, controlli
d'ingresso, report (T1–T3, T5–T8, T14–T17, T19); **P2** tabella unita
(colonne, suffissi, conflitti di UCD, `suggest_columns`) (T13, T18);
**P3** `crossmatch_by_field` (T9, T10); **P4** `crossmatch_ellipses`
(T11, T12, T20); **P5** `crossmatch_cds` (T4, T21). Codice in
`src/astrotwo/core/crossmatch.py`.

**Regole comuni (decisioni del proprietario del 2026-10-11, raccomandazioni
accettate):**

- **Posizioni:** dalle colonne di posizione della `CatalogTable` del 13
  (`positions`: da UCD e metadati o confermate dall'utente), con il loro
  sistema, equinozio ed epoca; mai dai nomi. Senza colonne
  `NO_COORD_COLUMNS`, senza sistema `FRAME_UNKNOWN`. Le due tabelle si
  portano nel sistema di confronto `frame` (ICRS di default) **con il modulo
  10** (FK5 con il suo equinozio; FK4 con equinozio ed epoca come
  `obstime`, mai assunta).
- **Epoche diverse:** **nessuna propagazione automatica.** Il report porta
  l'epoca delle posizioni di ciascuna tabella (o "non dichiarata") e, se
  entrambe sono dichiarate e diverse, l'avviso `EPOCH_DIFFERS`; chi vuole
  propagare usa prima `propagate` del 13.
- **Coordinate mancanti** (valori mascherati o non finiti in una delle due
  colonne): righe **escluse** dall'incrocio e **contate a parte** nel report
  (avviso `COORD_MISSING` con i conteggi per tabella); in modalità `none`
  non sono elencate tra i non appaiati (senza posizione non si può dire).
- **`max_sep`:** obbligatorio, angolo con unità, **> 0 e ≤ 180°** in locale,
  **≤ 180″ per il servizio CDS** (limite del servizio XMatch); altrimenti
  `MAX_SEP_INVALID`.
- **Modalità `best`:** per ogni riga di A la riga di B più vicina; **a pari
  distanza vince l'indice più basso in B**; **una riga di B può servire più
  righe di A** (l'incrocio non è simmetrico); entrambi i casi sono
  dichiarati (avvisi `BEST_TIE` e `B_REUSED` con i conteggi).
- **Modalità `all`:** tutte le coppie entro `max_sep`, ordinate per indice
  di A, separazione, indice di B. **Modalità `none`:** gli indici di A
  (con posizione valida) senza alcuna riga di B entro `max_sep`.
- **Separazioni:** calcolate da `astropy.coordinates`
  (`search_around_sky`) in `float64` sulle coordinate convertite dal modulo
  10, riportate in arcsec.
- **Corpo (D19-3, D19-4):** si incrociano solo tabelle con lo stesso
  `body`; `BODY_UNKNOWN` se manca, `BODY_MISMATCH` se diverso, forzabile
  solo con `force_body=True`, citato nel report.
- **Tetto (D15-3):** oltre il tetto di righe della tabella
  (`TableLimits.max_rows`, 1 milione di default) `TABLE_TOO_LARGE`, con la
  proposta del servizio CDS o dell'elaborazione a blocchi; mai troncamento.
- **Report (`MatchReport`):** metodo e libreria o servizio, modalità,
  `max_sep` con unità (o soglia e assi per le ellissi), sistema di
  confronto, sistema ed epoca di ogni tabella, corpi ed eventuale
  forzatura, conteggi (righe usate, escluse, coppie, non appaiati, pari
  merito, righe di B riusate), rinomine, data e ora (UTC), avvisi; per il
  servizio anche URL, parametri e richiesta registrata (14).
- **Rielaborazione con soglia diversa:** `CrossMatchResult` conserva i
  riferimenti alle due tabelle e ai parametri; `rematch(max_sep=...)` (o
  `threshold=...` per le ellissi) **riesegue il calcolo** con lo stesso
  metodo, senza ricaricare i dati.

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
- **Cross-match tramite servizio CDS (P5):** stessa interfaccia, esecuzione
  remota sul servizio **CDS XMatch** con `astroquery.xmatch` (D15-2):
  **URL HTTPS** `https://cdsxmatch.cds.unistra.fr/xmatch/api/v1/sync`
  (il default di `astroquery` è `http://`; verificato il 2026-10-11 che
  l'HTTPS risponde con certificato valido), **timeout comuni di `04`**,
  **cache di `astroquery` disattivata**, risposta salvata nella **cache del
  14** (stessa regola del puntatore SIMBAD) con la richiesta registrata. Si
  caricano **solo indice di riga, RA e Dec in ICRS** (gradi, convertiti con
  il modulo 10); il risultato si riporta agli indici locali. Il servizio ha
  `selection=best|all` (verificato sulla documentazione delle chiamate
  API): `best` e `all` si chiedono al servizio, **`none` si ricava da
  `all`**. **Prima di P5:** verifica dei limiti di dimensione dei file
  caricati.
- **Report dei criteri:** ogni risultato riporta modalità, distanza massima,
  sistema di riferimento, epoca e servizio/URL usati.
- **Distanze di appaiamento:** per ogni coppia si riporta la separazione
  angolare calcolata con `astropy.coordinates` sulle coordinate del modulo 10.
- **Correlazione per campo (E3, sez. 5.11 del manuale di Aladin, ed. giugno 2022):**
  incrocio di due tabelle per **valori identici** in una colonna di ciascuna
  (es. un identificatore: in termini di basi di dati un *join*), con
  `astropy.table.join`. Modalità: coppie (`pairs`, join interno) oppure
  record di A senza corrispondenza (`none`). Chiavi ripetute: si producono
  tutte le combinazioni e il report ne dichiara il numero. **Chiavi
  compatibili (2026-10-11):** numeriche con numeriche (interi e reali,
  uguaglianza esatta), testo con testo, booleane con booleane; altrimenti
  `KEY_COLUMN_INVALID`. Il testo si confronta **senza gli spazi finali**
  (riempimento dei testi FITS, come `search` del 13), maiuscole e minuscole
  contano; le **chiavi mancanti** (mascherate o non finite) **non
  coincidono mai** e sono contate.
- **Correlazione con ellissi d'errore (E3):** come la correlazione per
  posizione, ma per ciascuna tabella si indicano anche le tre colonne
  dell'ellisse d'errore di posizione: **asse maggiore**, **asse minore** e
  **orientamento rispetto al nord** (da nord verso est), con unità
  angolari. **Il significato degli assi è dichiarato con il parametro
  obbligatorio `axes`** (`"semi"` = semiassi a 1σ, `"full"` = assi interi,
  cioè due volte il semiasse a 1σ); nulla è assunto. Due sorgenti sono
  associate se la loro **distanza normalizzata** con la **covarianza combinata**
  delle due ellissi (distanza di Mahalanobis) non supera una **soglia
  dichiarata in sigma** (D15-5). **Soglia obbligatoria, senza default**
  (D15-6, decisa il 2026-10-11). **Geometria:** spostamento di B rispetto ad
  A nel piano tangente in A (`SkyCoord.spherical_offsets_to`, componenti
  verso est e verso nord); covarianza di un'ellisse Σ = a²·u·uᵀ + b²·v·vᵀ con
  u = (sin θ, cos θ) direzione dell'asse maggiore e v = (cos θ, −sin θ),
  θ = orientamento da nord verso est, a e b semiassi a 1σ; Σ = Σ_A + Σ_B;
  d = √(Δᵀ Σ⁻¹ Δ). L'uso del piano tangente in A per entrambe le ellissi è
  scritto nel report. **Candidati:** prima un `search_around_sky` con il
  raggio rigoroso k·√(a_A,max² + a_B,max²) (nessuna coppia con d ≤ k ne resta
  fuori). Modalità `all`/`best`/`none` come per la posizione, sulla
  distanza d. **Il report dichiara** formula, covarianza, soglia, assi e
  che **in 2D la soglia k di Mahalanobis non corrisponde alla percentuale
  1D** (frazione attesa entro k per errori gaussiani = 1 − exp(−k²/2):
  per k = 3 circa 98,9 %, non 99,7 %), calcolata dal codice per la soglia
  data. Righe con valori d'ellisse mancanti: escluse e contate come le
  coordinate mancanti.
- **Scelta delle colonne da conservare (E3, P2):** la tabella unita
  (`CrossMatchResult.joined`) ha per default tutte le colonne delle due
  tabelle, con suffissi `_tab1` e `_tab2` sui nomi in conflitto, più la
  colonna della separazione (`xmatch_sep`, arcsec; per le ellissi anche
  `xmatch_mahalanobis`); l'utente può scegliere le colonne
  (`keep_columns`) e i prefissi o suffissi. Nessuna rinomina silenziosa:
  il report elenca le rinomine. La tabella unita è una `CatalogTable` con
  provenienza (le due origini e il report nella storia), `body` e le
  colonne di posizione della tabella principale.
- **Corrispondenza delle colonne tramite UCD (E3):** le colonne di posizione
  (e d'errore) si propongono in base agli UCD (`suggest_columns`: coppie
  `pos.eq.ra`/`pos.eq.dec`, galattiche, eclittiche; colonne d'errore con
  `stat.error` o `pos.errorEllipse` insieme a `phys.size.smajAxis`,
  `phys.size.sminAxis`, `pos.posAng`, marcate come suggerimenti); se un
  UCD con `meta.main` compare in entrambe le tabelle è un conflitto
  (`UCD_CONFLICT`): **prevale la prima tabella** salvo la scelta esplicita
  `main="b"`; nella tabella unita le colonne della tabella non principale
  **perdono la parola `meta.main`** dall'UCD (scritto nel report), così le
  posizioni del risultato sono univoche.

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
| in | `table_a`, `table_b` | `CatalogTable` (13) | colonne di posizione con sistema | posizioni, `body`, epoca dai metadati |
| in | `mode` | enumerativo | `all` / `best` / `none` (`pairs` / `none` per campo) | default `best` (D15-1) |
| in | `max_sep` | `Quantity` angolare | **obbligatorio, senza default**; (0°, 180°] locale, ≤ 180″ CDS | distanza massima |
| in | `frame` | stringa | sistema del modulo 10, `icrs` di default | sistema di confronto |
| in | `force_body` | booleano | default `False` | D19-4, citato nel report |
| in | `key_a`, `key_b` | nomi di colonna | tipo compatibile | correlazione per campo (E3) |
| in | `ellipse_a`, `ellipse_b` | 3 nomi di colonna per tabella | asse maggiore, asse minore, orientamento (nord → est), angoli con unità | correlazione con ellissi (E3) |
| in | `axes` | enumerativo | `semi` (semiassi 1σ) / `full` (assi interi) | **obbligatorio** |
| in | `threshold` | float64 | sigma (adimensionale), > 0 | **obbligatorio, senza default** (D15-6) |
| in | `keep_columns`, `prefixes`, `suffixes`, `main` | liste, coppie di stringhe, `a`/`b` | default: tutte, `""`/`""`, `_tab1`/`_tab2`, `a` | tabella unita (E3) |
| out | coppie | `astropy.table.Table` | `idx_a`, `idx_b`, `sep` (arcsec), per le ellissi `mahalanobis` | indici da 0 |
| out | non appaiati | array di indici di A | — | modalità `none` |
| out | report | `MatchReport` | §3 | riproducibilità |
| out | tabella unita | `CatalogTable` | colonne scelte, rinomine, `xmatch_sep` | P2 |
| out | colonne proposte | struttura | posizione/errore da UCD, conflitti | E3 |

## 7. Interfaccia pubblica

Codice in `src/astrotwo/core/crossmatch.py`.

- **`CrossmatchError`** — errore con identificatore di §10.
- **`crossmatch(table_a, table_b, mode="best", max_sep=None, *,
  frame="icrs", force_body=False)`** (P1) — incrocio locale; restituisce
  `CrossMatchResult`. Calcolo: `astropy.coordinates.search_around_sky` —
  mai implementazioni approssimate scritte a mano.
- **`CrossMatchResult`** (classe) — `pairs`, `unmatched`, `report`,
  `warnings`; `rematch(max_sep=None, threshold=None)` riesegue con una
  soglia diversa sulle stesse tabelle (P1); `joined(keep_columns=None,
  prefixes=("", ""), suffixes=("_tab1", "_tab2"), main="a")` tabella unita
  (P2).
- **`MatchReport`** (struttura) — §3; `as_dict()` e `describe()` (testo per
  l'utente, base di `describe_match_report`).
- **`suggest_columns(table_a, table_b=None)`** (P2, E3) — colonne di
  posizione ed errore proposte dagli UCD, con i conflitti `meta.main` tra
  le due tabelle.
- **`crossmatch_by_field(table_a, table_b, key_a, key_b, mode="pairs", *,
  force_body=False)`** (P3, E3) — join su valori identici con
  `astropy.table.join`; stesso `CrossMatchResult` (senza separazioni).
- **`crossmatch_ellipses(table_a, table_b, ellipse_a, ellipse_b, threshold,
  *, axes, mode="best", frame="icrs", force_body=False)`** (P4, E3) —
  distanza di Mahalanobis con covarianza combinata.
- **`crossmatch_cds(table_a, table_b, mode="best", max_sep=None, *,
  frame="icrs", force_body=False, cache=None, refresh=False,
  timeouts=NETWORK_TIMEOUTS)`** (P5) — incrocio con CDS XMatch; stesso
  `CrossMatchResult`, con la richiesta registrata nel report.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `astropy.coordinates` (`search_around_sky`) | incrocio locale per separazione angolare | algoritmi verificati della comunità |
| `astroquery.xmatch` (D15-2, decisa) | servizio CDS XMatch (URL HTTPS, cache di astroquery disattivata) | client ufficiale del servizio; vedi §13 |
| `numpy` | distanza di Mahalanobis (matrici 2 × 2) e selezioni | consolidato |
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
- Nessuna propagazione automatica delle epoche (avviso `EPOCH_DIFFERS`).
- Le tabelle di ingresso non cambiano mai (D13-5).
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
| Epoche delle posizioni dichiarate e diverse | incrocio eseguito senza propagazione, epoche nel report | avviso `EPOCH_DIFFERS` |
| Righe con coordinate (o valori d'ellisse) mancanti | escluse e contate a parte | avviso `COORD_MISSING` |
| `best` con più righe di B alla stessa distanza | vince l'indice più basso in B, conteggio dichiarato | avviso `BEST_TIE` |
| `best` con una riga di B scelta da più righe di A | ammesso, conteggio dichiarato | avviso `B_REUSED` |
| Chiavi mancanti nella correlazione per campo | mai coincidenti, contate | avviso `KEY_MISSING` |
| Chiavi ripetute nella correlazione per campo | tutte le combinazioni, numero dichiarato | avviso `KEY_REPEATED` |
| `axes` assente o diverso da `semi`/`full`; `threshold` assente, non numerico o ≤ 0 | rifiuto dell'input | `ERROR_ELLIPSE_INVALID` |
| Servizio CDS: `max_sep` oltre 180″ | rifiuto prima della richiesta | `MAX_SEP_INVALID` |
| Servizio CDS che risponde con un errore | messaggio del servizio riportato | `SERVICE_ERROR` |

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
| T4 | Coerenza locale vs CDS | stesso input piccolo nelle due modalità (test di rete separato) | stesse coppie; separazioni uguali entro **1 mas** | confronto diretto tra i due esiti |
| T5 | Frame diversi | una tabella in ICRS e una in galattico | incrocio riuscito dopo conversione, risultato coincidente con l'incrocio fatto dopo aver convertito entrambe manualmente nel test | ricalcolo con Astropy |
| T6 | Report di criteri | eseguire un incrocio | il report riporta modalità, soglia (con unità), frame, servizio e timestamp | controllo del contenuto |
| T7 | Corpi diversi | incrociare una tabella celeste con una tabella di Marte (dati di prova) | `BODY_MISMATCH`, nessuna coppia | test di unità |
| T8 | Forzatura | ripetere T7 con l'opzione di forzatura | incrocio eseguito; il report cita la forzatura e i corpi coinvolti | controllo del report |
| T9 | Correlazione per campo (E3) | due tabelle con una colonna identificatore, 3 valori in comune | 3 coppie; con `none` i record senza corrispondenza | confronto con `astropy.table.join` nel test |
| T10 | Chiavi ripetute (E3) | identificatore ripetuto 2 volte in A e 2 in B | 4 combinazioni, numero dichiarato nel report | test di unità |
| T11 | Ellisse non valida (E3) | asse minore maggiore dell'asse maggiore | `ERROR_ELLIPSE_INVALID` | test di unità |
| T12 | Correlazione con ellissi (E3) | coppie sintetiche con ellissi note | associate solo le coppie con distanza di Mahalanobis (covarianza combinata) ≤ soglia; distanze riportate nel risultato | ricalcolo nel test con `numpy` (matrici di covarianza dalle ellissi) |
| T13 | Suffissi e UCD (E3) | due tabelle con colonne omonime e UCD `pos.eq.ra`/`pos.eq.dec` | colonne in conflitto con `_tab1`/`_tab2`; colonne di posizione proposte dagli UCD; rinomine nel report | controllo del risultato |
| T15 | Epoche diverse | tabelle con epoca J2016 e J2000 | incrocio senza propagazione, epoche nel report, `EPOCH_DIFFERS` | controllo del report |
| T16 | `best` a pari distanza e B riusato | due righe di B equidistanti da una di A; una riga di B più vicina a due righe di A | vince l'indice più basso, `BEST_TIE`; la riga di B appare due volte, `B_REUSED` | ricalcolo con `numpy` |
| T17 | Coordinate mancanti | righe con valori mascherati e NaN in A e B | escluse, contate nel report, non elencate in `none` | test di unità |
| T18 | Tabella unita | `joined` con colonne omonime, scelta di colonne, prefissi, `main="b"`, conflitto `meta.main` | colonne e rinomine nel report, `xmatch_sep`, `meta.main` tolto dalla tabella non principale, posizioni della principale | controllo del risultato |
| T19 | Rielaborazione | `rematch` con raggio più piccolo | stesse coppie dell'incrocio eseguito da capo con quel raggio | confronto diretto |
| T20 | Ellissi: assi e soglia | stesse ellissi date come semiassi e come assi interi (doppi); soglia assente | stesse coppie e stesse distanze; soglia o `axes` assenti → `ERROR_ELLIPSE_INVALID`; frazione 2D nel report = 1 − exp(−k²/2) | ricalcolo con `numpy` |
| T21 | Servizio CDS simulato | richiesta a un XMatch simulato | caricati solo indice, RA e Dec ICRS; URL HTTPS di default; `none` ricavato da `all`; risposta nella cache del 14; `max_sep` > 180″ rifiutato | servizio simulato |
| T14 | Raggio obbligatorio | incrocio senza `max_sep`, con un numero senza unità, con un'unità non angolare, ≤ 0, oltre 180° | `MAX_SEP_INVALID` in tutti i casi, nessun incrocio eseguito | test di unità |

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
- **D15-6 — Soglia predefinita della correlazione con ellissi: DECISA il
  2026-10-11 (decisione del proprietario).** **Nessun default:** la soglia
  è obbligatoria, come `max_sep`; il report dichiara che in 2D k sigma di
  Mahalanobis non corrisponde alla percentuale 1D (per k = 3 circa 98,9 %,
  non 99,7 %).
- **D15-7 — Decisioni del proprietario del 2026-10-11 sulla divisione in
  parti (raccomandazioni accettate):** cinque parti P1–P5; epoche senza
  propagazione automatica (`EPOCH_DIFFERS`); `best` con pari merito
  all'indice più basso di B e righe di B riusate, dichiarati; coordinate
  mancanti escluse e contate; `max_sep` in (0°, 180°] locale e ≤ 180″ per il
  CDS; CDS con `astroquery.xmatch`, URL HTTPS, timeout di `04`, cache di
  astroquery disattivata, risposta nella cache del 14, solo indice/RA/Dec
  ICRS caricati, `none` da `all`, limiti di caricamento da verificare prima
  di P5; soglia delle ellissi obbligatoria (D15-6); assi dichiarati con
  `axes`; geometria nel piano tangente in A con raggio rigoroso dei
  candidati; chiavi del join; conflitti di UCD (`meta.main` tolto dalla
  tabella non principale); `rematch` che riesegue; tolleranza di T4 1 mas.
  Applicate in §3, §6, §7, §9, §10, §12.

- **D15-8 — Corpo nella correlazione per campo: DA DECIDERE (aperta il
  2026-10-11, Gruppo 3).** §9 chiede lo stesso `body` per ogni incrocio, e
  P3 lo applica così; ma una correlazione per identificativo non usa le
  posizioni, e una tabella senza colonne di posizione (es. un CSV di
  fotometria con un identificativo) ha `body` non ricavabile, quindi
  `BODY_UNKNOWN` e nessun join possibile (non forzabile). Opzioni: (a)
  nella correlazione per campo il corpo non si controlla, ed è scritto nel
  report; (b) si controlla solo se entrambe le tabelle hanno un corpo; (c)
  come oggi. **Raccomandazione:** (b): un corpo noto e diverso resta
  `BODY_MISMATCH` (forzabile), un corpo ignoto non blocca un join che non
  usa posizioni, e il report lo dichiara. **Fermo solo questo punto:** oggi
  vale (c), come scritto in §9.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). Distanza massima predefinita 4 arcsec e modalità tutte/migliore/nessuna da `03-parita-aladin.md` E3. |
| 2026-10-09 | Claude Code | **D15-1…D15-4 DECISE** (checklist del livello 1): default `best` (default di Aladin da verificare); `astroquery.xmatch`; tetto 1 milione di righe per tabella senza troncamenti silenziosi; nessuna probabilità nel livello 1. **D19-3 estesa al 15** (decisione del proprietario): incrocio solo tra tabelle con lo stesso `body`, errori `BODY_MISMATCH`/`BODY_UNKNOWN`, forzatura come D19-4, test T7–T8. §6, §8, §9, §10, §12 aggiornati. |
| 2026-10-09 | Claude Code | **Completamento con gli esiti di AP5** (decisione del proprietario del 2026-10-09): §3, §6, §7, §8, §10, §12 per E3 (correlazione per campo con `astropy.table.join`, correlazione con ellissi d'errore, scelta delle colonne con suffissi, corrispondenza tramite UCD). Nuova decisione del Gruppo 2 **D15-5** (criterio delle ellissi): il modulo resta in `bozza`. |
| 2026-10-09 | Claude Code | **D15-5 DECISA** (decisione del proprietario): distanza di Mahalanobis con covarianza combinata e soglia in sigma; criterio di Aladin da verificare con differenza dichiarata. Nuova D15-6 (soglia predefinita, Gruppo 3). §3, §6, §7, §10, §12, §13 aggiornati. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** (regola del proprietario del 2026-10-09): nessuna decisione aperta nei Gruppi 1 e 2. |
| 2026-10-10 | Claude Code | **Regola d'oro n. 8** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): distanza massima **obbligatoria, senza default** (tolto il default di 4 arcsec preso da Aladin) in §3, §4, §6, §9, §10 (`MAX_SEP_INVALID` anche se manca), nuovo test T14; modalità `best` con motivazione nostra (D15-1); D15-4 e D15-5 senza riferimenti ad Aladin; §2 e §3 senza "come Aladin". Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **Decisioni del proprietario sulla divisione in parti (D15-7) e D15-6** (autorizzazione esplicita a modificare il file approvato, prima del codice): cinque parti P1–P5 (§3); regole comuni (posizioni dal 13, conversione con il 10, epoche senza propagazione con `EPOCH_DIFFERS`, coordinate mancanti escluse e contate, `max_sep` in (0°, 180°] e ≤ 180″ per il CDS, `best` con pari merito e B riusato dichiarati, report, `rematch`); CDS con `astroquery.xmatch` in HTTPS e cache del 14; chiavi del join; ellissi con `axes` obbligatorio, soglia obbligatoria (D15-6 decisa), geometria e raggio dei candidati, frazione 2D nel report; tabella unita e conflitti di UCD (§3, §6, §7, §8, §9, §10); T4 con tolleranza 1 mas, nuovi T15–T21 (§12). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **P1 scritta** (`src/astrotwo/core/crossmatch.py`: `crossmatch`, `CrossMatchResult` con `rematch`, `MatchReport`, `CrossmatchError`, `CROSSMATCH_MODES`; test T1–T3, T5–T8, T14–T17, T19 in `tests/core/test_crossmatch.py`): verificato con astropy 8.0.1 che `search_around_sky` include il confine (separazione ≤ `max_sep`) e accetta tabelle vuote; pari merito di `best` = stessa separazione in `float64`. Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **P2 scritta** (`CrossMatchResult.joined`, `suggest_columns`, `ColumnSuggestions`; test T13, T18): rinomine solo dei nomi in conflitto (anche con `xmatch_sep`), avviso `COLUMNS_RENAMED` e voci nella storia; `meta.main` tolto dalle colonne della tabella non principale (`MAIN_UCD_REMOVED`, `UCD_CONFLICT` se lo stesso UCD principale è in entrambe); in modalità `none` solo le colonne di A dei non appaiati; metadati di colonna copiati (tabelle d'ingresso invariate). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **P3 scritta** (`crossmatch_by_field`, `FIELD_MODES`; test T9, T10): join con `astropy.table.join` su chiavi normalizzate (testo senza spazi finali; numeri reali in `float64` se una delle due chiavi è reale; booleani), chiavi mancanti mai coincidenti (`KEY_MISSING`), combinazioni da chiavi ripetute dichiarate (`KEY_REPEATED`, nuovo in §10); regola del corpo di §9 applicata anche qui. Nuova decisione aperta **D15-8** (corpo nella correlazione per campo, Gruppo 3). Stato `approvato` invariato. |
