# 18-core-calcolatrici.md — calcolatrici: algebrica, unità, pixel, coordinate e tempo

**Stato:** approvato

## 2. Scopo

Offrire all'utente, all'IA e agli script cinque calcolatrici deterministiche
(algebrica, unità, pixel, coordinate, tempo) che restituiscono sempre valore,
unità e libreria che ha fatto il calcolo, senza mai far calcolare nulla al
modello linguistico.

## 3. Cosa fa

Origine: riga **H4** di `03-parita-aladin.md` (calcolatrici di Aladin, manuale
utente ed. giugno 2022, sezioni 5.7.1–5.7.5); modulo accettato in AM1 il
2026-10-04. Ogni calcolatrice produce un **risultato** che contiene: l'input
ripetuto così come è stato interpretato, il valore in `float64` (o la data),
l'unità o la scala, la libreria che ha eseguito il calcolo con la sua versione
e l'istante della richiesta. Ogni uso è registrato come comando rieseguibile
(regola d'oro n. 6; il registro è di `24-analisi-pipeline-riproducibili.md`).

1. **Calcolatrice algebrica (sez. 5.7.1).** Valuta un'espressione numerica
   scritta dall'utente.
   - Operatori: `+`, `-`, `*`, `/`, `%` (modulo), `^` (potenza), parentesi;
     costanti `pi` ed `e`; numeri in notazione decimale ed esponenziale.
   - Funzioni (stesso elenco di Aladin): `exp`, `ln`, `log` (base 10),
     `sqrt`, `ceil`, `floor`, `round`, `abs`, `min`, `max`; trigonometriche in
     **radianti** `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`;
     trigonometriche in **gradi** `sind`, `cosd`, `tand`, `asind`, `acosd`,
     `atand`, `atan2d`; iperboliche `sinh`, `cosh`, `tanh`; conversioni
     `rad2deg`, `deg2rad`; `dist(x1, y1, x2, y2)` (distanza cartesiana);
     `skydist(ra1, dec1, ra2, dec2)` (distanza sferica, coordinate in gradi o
     sessagesimali con `:`).
   - Regola senza eccezioni sugli angoli: **le funzioni senza `d` lavorano in
     radianti, quelle con `d` in gradi**. Il manuale di Aladin contiene una
     descrizione incoerente (`tan` "in gradi"): AstroTwo non la segue.
   - `skydist` non è calcolata qui: richiama `angular_distance` di
     `17-core-misure.md`; le coordinate sessagesimali si interpretano con il
     modulo `10-core-coordinate-wcs.md`; il risultato è in gradi.
   - L'espressione si **analizza con una grammatica chiusa** e non viene mai
     eseguita come codice Python (nessun `eval`). Analizzatore: modulo `ast`
     con elenco chiuso (D18-1, decisa il 2026-10-09).
   - Come in Aladin, l'espressione si può scrivere preceduta o seguita da `=`
     nel campo comandi; la compatibilità completa con la sintassi degli script
     di Aladin dipende da A8 (rimandata dopo il livello 1).
2. **Convertitore di unità (sez. 5.7.2).** Converte un valore da un'unità a
   un'altra.
   - Le unità e i prefissi (da yocto a yotta) sono quelli di `astropy.units`,
     anche composti con gli operatori usuali (es. `km/s`, `mHz`).
   - Il valore può essere un numero, un'espressione della calcolatrice
     algebrica, un angolo sessagesimale (gradi `d:m:s` o ore `h:m:s`,
     interpretati con `astropy.coordinates.Angle` tramite il modulo 10) o una
     data (convertita con la calcolatrice del tempo).
   - Equivalenze fisiche (es. lunghezza d'onda ↔ frequenza, temperature con
     zero spostato) **solo se richieste esplicitamente**; elenco: §13, D18-3.
   - Le unità di Aladin che non esistono in `astropy.units` (es. `"MM/yy"`,
     `"day"` come giorno del mese, alias come `al`, `Mgeo`) non sono
     accettate tramite alias definiti in un'unica tabella (D18-2, decisa il
     2026-10-09); la sintassi `convert … into …` si decide con A8.
3. **Calcolatrice dei pixel (sez. 5.7.3).**
   - Converte il valore **grezzo** di un pixel nel valore **fisico** con la
     regola dello standard FITS `valore = BZERO + BSCALE × grezzo`, e
     viceversa; tiene conto di `BLANK` (pixel senza valore).
   - Calcola l'indice nella tabella dei colori (0–255, oppure 1–255 se lo 0 è
     riservato alla trasparenza) a partire dai parametri di visualizzazione
     dell'immagine, chiamando `set_display` di `11-core-immagini-fits.md`.
   - Si usa a mano (BZERO, BSCALE, valore inseriti dall'utente) oppure con un
     clic sull'immagine: in quel caso costanti, parametri di visualizzazione e
     valore del pixel arrivano da `11` e `read_pixel` di `17`.
   - Le coordinate pixel mostrate seguono la convenzione FITS (indice da 1);
     internamente sono in convenzione numpy (DC7 di `02-convenzioni.md`, con
     conversione nel modulo 10).
4. **Calcolatrice delle coordinate (sez. 5.7.4).** Interfaccia di calcolo
   che usa i moduli `10-core-coordinate-wcs.md` (conversioni con
   `convert_coordinates`, propagazione con `propagate_position`) e
   `17-core-misure.md` (offset con `angular_offsets`/`apply_offsets`, calcolo
   inverso — posizione da distanza + angolo di posizione — con
   `offset_position`); nessuno di questi calcoli **viene riscritto qui**
   (D10-8 del modulo 10, decisa il 2026-10-09: la vecchia
   `coordinate_calculator` del 10 non esiste più).
   - Raccoglie gli input (coordinate scritte, clic nella vista o riga di un
     catalogo) e restituisce le stesse coordinate in tutti i sistemi ed epoche
     richiesti, in forma decimale e sessagesimale.
   - Cambi di riferimento anche da equinozi storici (es. B1875 → ICRS).
   - Propagazione con moto proprio e velocità radiale quando sono noti: se la
     posizione viene da un catalogo, moto proprio, velocità radiale ed epoca
     si leggono dai suoi metadati (modulo 13). **L'epoca non si assume mai**
     (D10-2): se manca, errore `EPOCH_REQUIRED` del modulo 10.
5. **Calcolatrice del tempo (sez. 5.7.5).** Converte una data tra ISO 8601,
   giorno giuliano (JD), giorno giuliano modificato (MJD), anno giuliano
   decimale e anno besseliano decimale, con `astropy.time`.
   - **La scala di tempo (UTC, TT, TDB, TCB, TAI…) va sempre dichiarata**
     (DC1 di `02-convenzioni.md`); in uscita si può chiedere un cambio di
     scala, eseguito da `astropy.time`.
   - Il risultato riporta la scala in ogni rappresentazione.

## 4. Cosa NON fa

- Non disegna finestre né campi di input: l'interfaccia delle calcolatrici è
  di `40-ui-finestra-principale.md` (menu Strumenti) e, per il clic sulla
  vista, di `41-ui-visualizzatore-cielo.md`.
- Non converte coordinate e non propaga posizioni da sé: lo fa il modulo
  `10-core-coordinate-wcs.md`; non calcola offset né posizioni da distanza +
  angolo di posizione: lo fa `17-core-misure.md`; qui si raccolgono input e
  si presentano i risultati.
- Non legge file FITS né applica funzioni di trasferimento: lo fa
  `11-core-immagini-fits.md`.
- Non misura distanze o angoli tra oggetti della vista (`17-core-misure.md`)
  né fa fotometria (`20-analisi-fotometria.md`).
- Non calcola colonne di tabella (H8, `13-core-cataloghi.md`) né fa
  aritmetica tra immagini (H5, `11-core-immagini-fits.md`).
- Non fa algebra simbolica, non risolve equazioni, non disegna grafici.
- Non converte magnitudini in flussi senza punto zero e sistema fotometrico
  dichiarati (§13, D18-4).
- Non esegue codice arbitrario: un'espressione fuori grammatica è rifiutata.
- Non lascia mai che l'IA produca un numero: l'IA può solo chiamare le
  calcolatrici (§11).

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `10-core-coordinate-wcs.md` (conversioni e propagazione,
  interpretazione dei sessagesimali, conversione dei pixel DC7),
  `11-core-immagini-fits.md` (BZERO, BSCALE, BLANK, parametri di
  visualizzazione), `13-core-cataloghi.md` (moto proprio, velocità radiale ed
  epoca di una riga di catalogo), `17-core-misure.md` (`angular_distance` per
  `skydist`, `read_pixel`, offset e calcolo inverso per la calcolatrice delle
  coordinate).
- **Usato da:** `24-analisi-pipeline-riproducibili.md` (comandi `=` e
  `convert` negli script e nel registro), `32-ia-registro-strumenti.md`
  (strumenti per l'IA), `40-ui-finestra-principale.md` (finestre delle
  calcolatrici), `41-ui-visualizzatore-cielo.md` (riempimento al clic).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `expression` | stringa | grammatica chiusa (§3, punto 1) | lunghezza massima: D18-5 |
| in | `value` | float64, espressione, angolo sessagesimale o data | con unità di partenza esplicita | per il convertitore |
| in | `from_unit`, `to_unit` | stringa | sintassi `astropy.units` | compatibilità Aladin: D18-2 |
| in | `equivalency` | enumerativo, facoltativo | nome dell'equivalenza | solo su richiesta esplicita (D18-3) |
| in | `raw` / `physical` | float64 | unità dell'immagine (`BUNIT`) per il fisico | uno dei due |
| in | `bzero`, `bscale`, `blank` | float64 | adimensionali, come da intestazione FITS | `bscale ≠ 0` |
| in | parametri di visualizzazione | da `11` | vmin, vmax, funzione di trasferimento | per l'indice 0–255 |
| in | coordinate, frame, epoche | come in `10` | gradi o sessagesimali + frame + epoca | epoca mai assunta |
| in | `time_value`, `time_format`, `scale` | stringa o float64 | ISO 8601, JD, MJD, anno giuliano, anno besseliano + scala | scala obbligatoria |
| out | `CalculatorResult` | struttura | valore `float64` o data, unità o scala, input interpretato, libreria e versione, istante | sempre con unità/scala |
| out | indice di colore | intero | 0–255 (o 1–255) | solo presentazione |
| out | comando registrato | testo | formato del modulo 24 | rieseguibile |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole (nessun codice). File Python previsto:
`src/astrotwo/core/calculators.py`.

- **`CalculatorResult`** (classe): contiene input interpretato, valore,
  unità o scala, libreria e versione, istante della richiesta e il comando
  equivalente da registrare; non può esistere senza unità o scala.
- **`evaluate_expression(expression)`** — analizza e valuta un'espressione
  della calcolatrice algebrica; restituisce un `CalculatorResult` adimensionale
  (o in gradi per `skydist`) oppure un errore della famiglia `CALC_…`.
- **`convert_units(value, from_unit, to_unit, equivalency)`** — converte con
  `astropy.units`; restituisce il valore nell'unità di arrivo oppure un errore
  della famiglia `UNIT_…`.
- **`convert_pixel_value(raw o physical, bzero, bscale, blank, display)`** —
  restituisce valore fisico, valore grezzo e, se ci sono i parametri di
  visualizzazione, l'indice di colore; con un'immagine e una posizione legge
  le costanti e il valore dai moduli 11 e 17.
- **`calculate_coordinates(...)`** — raccoglie gli input e chiama
  `convert_coordinates`/`propagate_position` del modulo 10 e, per offset e
  calcolo inverso, `angular_offsets`/`apply_offsets`/`offset_position` del
  modulo 17; restituisce le rappresentazioni
  richieste (sistemi, epoche, decimale e sessagesimale) con frame ed epoca
  dichiarati.
- **`convert_time(time_value, time_format, scale, target_scale)`** —
  restituisce ISO 8601, JD, MJD, anno giuliano e anno besseliano, tutti con
  la scala dichiarata.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `astropy.units` | convertitore di unità, prefissi, equivalenze | regola d'oro n. 4; stessa libreria di unità di tutto il progetto (`02-convenzioni.md` §4) |
| `astropy.time` | calcolatrice del tempo, cambi di scala | regola DC1 del progetto |
| `astropy.coordinates` (tramite il modulo 10) | sessagesimali, coordinate, epoche | nessuna conversione scritta a mano |
| `astropy.io.fits` (tramite il modulo 11) | BZERO, BSCALE, BLANK | standard FITS |
| `numpy` | funzioni matematiche della calcolatrice algebrica in `float64` | base dell'ecosistema scientifico |
| Modulo `ast` della libreria standard (D18-1) | analizzatore con elenco chiuso di nodi e nomi, nessun `eval` | nessuna dipendenza esterna, verificabile |
| Standard FITS (BSCALE/BZERO/BLANK) | regola grezzo ↔ fisico | standard del dominio |

La libreria di unità di VizieR usata da Aladin (nota 8 della sez. 5.7.2 del
manuale) non viene adottata: AstroTwo usa `astropy.units` ovunque.

## 9. Regole e vincoli

- **L'IA non calcola mai** (regola d'oro n. 1): ogni numero viene da una
  delle librerie di §8 e il risultato dichiara quale.
- Calcoli in `float64` (DC6); nessun arrotondamento prima della
  visualizzazione; il valore pieno resta copiabile.
- Ogni risultato ha unità o scala; un risultato "nudo" è un errore di
  programmazione.
- Angoli: radianti per le funzioni senza `d`, gradi per quelle con `d`,
  senza eccezioni.
- **Nessun valore non finito restituito in silenzio:** domini non validi,
  divisione per zero e overflow producono un errore esplicito, mai `NaN` o
  `inf` come risultato.
- Le espressioni non vengono mai eseguite come codice; i nomi ammessi sono
  solo quelli della grammatica.
- Scala di tempo sempre dichiarata (DC1); epoca mai assunta (DC2, D10-2).
- Coordinate pixel: interne in convenzione numpy, mostrate in convenzione
  FITS, conversione solo tramite il modulo 10 (DC7).
- Ogni uso produce un comando registrato e rieseguibile con lo stesso
  risultato (regola d'oro n. 6).
- Deterministico: stesso input e stesse versioni delle librerie, stesso
  output.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Espressione con sintassi non valida | nessun risultato; messaggio con la posizione dell'errore | `CALC_SYNTAX_ERROR` |
| Funzione o nome non previsto dalla grammatica (es. tentativo di eseguire codice) | rifiuto senza esecuzione | `CALC_UNKNOWN_FUNCTION` |
| Argomento fuori dominio (es. `sqrt(-1)`, `ln(0)`, `asin(2)`) | nessun risultato, mai `NaN` | `CALC_DOMAIN_ERROR` |
| Divisione per zero o modulo per zero | nessun risultato | `CALC_DIVISION_BY_ZERO` |
| Risultato oltre i limiti di `float64` | nessun risultato | `CALC_OVERFLOW` |
| Espressione oltre il limite di lunghezza o complessità | rifiuto prima della valutazione | `CALC_TOO_COMPLEX` (limite: D18-5) |
| Unità sconosciuta | elenco delle unità simili note ad `astropy.units` | `UNIT_UNKNOWN` |
| Unità non convertibili tra loro senza equivalenza | rifiuto con le due dimensioni fisiche | `UNIT_INCOMPATIBLE` |
| Magnitudine verso flusso senza punto zero | rifiuto | `UNIT_ZERO_POINT_REQUIRED` |
| Data non valida | rifiuto con il formato atteso | `TIME_INVALID` |
| Scala di tempo mancante | rifiuto: la scala non si assume mai | `TIME_SCALE_REQUIRED` |
| `BSCALE = 0` nel calcolo inverso (fisico → grezzo) | rifiuto | `PIXEL_BSCALE_ZERO` |
| Valore grezzo uguale a `BLANK` | nessun valore fisico; dichiarato "pixel senza valore" | `PIXEL_BLANK` |
| Coordinate fuori intervallo, frame sconosciuto, epoca mancante | errore del modulo 10 inoltrato senza modifiche | `COORD_OUT_OF_RANGE`, `FRAME_UNSUPPORTED`, `EPOCH_REQUIRED` |

## 11. Esposizione all'IA

Le calcolatrici sono lo strumento con cui l'IA ottiene numeri invece di
calcolarli: l'IA sceglie lo strumento e i parametri, il calcolo è sempre
della libreria dichiarata nel risultato.

- **`evaluate_expression`** — input: espressione; output: `CalculatorResult`.
  Calcolo: analizzatore (D18-1) + `numpy`.
- **`convert_units`** — input: valore, unità di partenza e di arrivo,
  equivalenza facoltativa; output: valore con unità. Calcolo:
  `astropy.units`.
- **`convert_pixel_value`** — input: valore grezzo o fisico, BZERO, BSCALE,
  BLANK; output: valori convertiti. Calcolo: regola FITS con `float64`.
- **`convert_time`** — input: data, formato, scala; output: tutte le
  rappresentazioni con la scala. Calcolo: `astropy.time`.
- Le coordinate passano dagli strumenti del modulo 10 (`convert_coordinates`,
  `propagate_position`) e del modulo 17 (`offset_position`,
  `angular_offsets`): questo modulo non ne definisce di nuovi.

## 12. Test di accettazione

I valori attesi si ricalcolano nel test con la libreria indicata; i numeri
scritti qui sotto sono risultati esatti per definizione o aritmetica
elementare.

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Espressione semplice | `evaluate_expression("3*8")` | 24 | aritmetica |
| T2 | Gradi e radianti | `sind(30)` e `sin(pi/6)` | entrambi 0.5 entro 1e-15 | ricalcolo con `numpy` |
| T3 | Nessuna esecuzione di codice | espressione che contiene un nome non previsto (es. una chiamata di funzione Python) | errore `CALC_UNKNOWN_FUNCTION`, nulla eseguito | test di unità |
| T4 | Dominio non valido | `sqrt(-1)`, `ln(0)`, `1/0` | `CALC_DOMAIN_ERROR`, `CALC_DOMAIN_ERROR`, `CALC_DIVISION_BY_ZERO`; nessun `NaN` | test di unità |
| T5 | `skydist` | `skydist` su due coppie di coordinate scelte dal tester | coincide con `angular_distance` del modulo 17 e con `SkyCoord.separation` | ricalcolo con Astropy |
| T6 | Conversione di lunghezza | 0.1 m in nm | 1e8 nm | `astropy.units` |
| T7 | Conversione di tempo | 2 anni giuliani in giorni | 730.5 d (anno giuliano = 365.25 d) | `astropy.units` |
| T8 | Angolo sessagesimale | `10:10:08` (gradi) in gradi decimali | 10 + 10/60 + 8/3600 gradi | `astropy.coordinates.Angle` |
| T9 | Unità incompatibili | metri in secondi | `UNIT_INCOMPATIBLE` | test di unità |
| T10 | Pixel grezzo → fisico | BZERO = 32768, BSCALE = 1, grezzo = −32768 | 0 | regola FITS |
| T11 | `BLANK` | grezzo uguale a `BLANK` | `PIXEL_BLANK`, nessun valore fisico | test di unità |
| T12 | Indice di colore | clic su un'immagine di prova con parametri di visualizzazione noti | stesso indice calcolato da `set_display` del modulo 11 | confronto con il modulo 11 |
| T13 | Coordinate | conversione ICRS → galattico di una posizione scelta dal tester | identica al risultato di `convert_coordinates` del modulo 10 | confronto diretto |
| T14 | Epoca mancante | propagazione senza epoca di origine | `EPOCH_REQUIRED` | test di unità |
| T15 | Tempo | `2000-01-01T12:00:00` in scala TT | JD 2451545.0 e anno giuliano 2000.0 (definizione di J2000.0); anno besseliano come calcolato da `astropy.time` | `astropy.time` |
| T16 | Data in MJD | `2001-12-10T00:00:00` in scala UTC | MJD 52253.0 (esempio del manuale di Aladin, sez. 5.7.2) | `astropy.time` |
| T17 | Scala mancante | data senza scala | `TIME_SCALE_REQUIRED` | test di unità |
| T18 | Riproducibilità | rieseguire il comando registrato di T1–T16 | risultati identici | confronto con il registro del modulo 24 |

## 13. Decisioni aperte

- **D18-1 — Analizzatore delle espressioni: DECISA il 2026-10-09 (decisione
  del proprietario sulla checklist del livello 1).** analizzatore sul modulo
  **`ast`** della libreria standard con **elenco chiuso** di nodi e nomi;
  nessuna dipendenza esterna; `^` tradotto in potenza.
- **D18-2 — Compatibilità con le unità di Aladin: DECISA il 2026-10-09
  (decisione del proprietario sulla checklist del livello 1).** **alias**
  delle unità di Aladin definiti in **un'unica tabella** verso `astropy.units`
  (elenco delle unità mancanti **da verificare prima del codice**); la
  sintassi `convert … into …` si decide con A8.
- **D18-3 — Equivalenze offerte: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** spettrale, densità di flusso
  spettrale, temperatura, parallasse ↔ distanza e Doppler (radio, ottico,
  relativistico; frequenza a riposo obbligatoria), **solo su richiesta
  esplicita**.
- **D18-4 — Magnitudini: DECISA il 2026-10-09 (decisione del proprietario
  sulla checklist del livello 1).** la conversione magnitudine ↔ flusso **sta
  solo nel modulo 20**: il 18 è livello 1 e non può dipendere dal 20; il
  convertitore la rifiuta con `UNIT_ZERO_POINT_REQUIRED`.
- **D18-5 — Limiti delle espressioni:** lunghezza massima e profondità di
  annidamento oltre le quali vale `CALC_TOO_COMPLEX`. Valori da fissare al
  momento del codice.
- **D18-6 — Lettura del valore grezzo:** come ottenere il valore grezzo di un
  pixel quando `astropy.io.fits` applica BSCALE/BZERO in lettura (lettura
  senza scala oppure calcolo inverso con la regola FITS). Da fissare al
  momento del codice, d'accordo con il modulo 11.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-08 | Claude Code | Creazione del file (stato: bozza). Origine: riga H4 di `03-parita-aladin.md` (manuale di Aladin ed. giugno 2022, sez. 5.7.1–5.7.5); cinque calcolatrici, dipendenze da 10, 11, 13 e 17 senza riscriverne le funzioni; convenzione dei pixel DC7; decisioni aperte D18-1…D18-6. |
| 2026-10-09 | Claude Code | **D18-1…D18-4 DECISE** (checklist del livello 1): analizzatore `ast` con elenco chiuso; alias delle unità di Aladin in un'unica tabella (elenco da verificare); equivalenze spettrale, densità di flusso, temperatura, parallasse, Doppler su richiesta; magnitudine ↔ flusso solo nel 20. §3, §8 aggiornati. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-09. |
| 2026-10-09 | Claude Code | **Decisione del proprietario D10-8 (modulo 10) applicata** (autorizzazione esplicita a modificare il file approvato): `coordinate_calculator` tolta dal 10; la calcolatrice delle coordinate usa `convert_coordinates`/`propagate_position` del 10 e `angular_offsets`/`apply_offsets`/`offset_position` del 17 (§3, §4, §5, §7, §11). Stato `approvato` invariato. |
