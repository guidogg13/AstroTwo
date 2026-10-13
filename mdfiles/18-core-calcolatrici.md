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
   - Funzioni (elenco che copre quelle della calcolatrice di Aladin, parità
     P11): `exp`, `ln`, `log` (base 10),
     `sqrt`, `ceil`, `floor`, `round`, `abs`, `min`, `max`; trigonometriche in
     **radianti** `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`;
     trigonometriche in **gradi** `sind`, `cosd`, `tand`, `asind`, `acosd`,
     `atand`, `atan2d`; iperboliche `sinh`, `cosh`, `tanh`; conversioni
     `rad2deg`, `deg2rad`; `dist(x1, y1, x2, y2)` (distanza cartesiana);
     `skydist(ra1, dec1, ra2, dec2)` (distanza sferica, coordinate in gradi o
     sessagesimali con l'unità scritta nel testo, D18-7).
   - Regola senza eccezioni sugli angoli: **le funzioni senza `d` lavorano in
     radianti, quelle con `d` in gradi**. Il manuale di Aladin contiene una
     descrizione incoerente (`tan` "in gradi"): AstroTwo non la segue.
   - `skydist` non è calcolata qui: richiama `angular_distance` di
     `17-core-misure.md`; le coordinate sessagesimali si interpretano con il
     modulo `10-core-coordinate-wcs.md`; il risultato è in gradi.
   - L'espressione si **analizza con una grammatica chiusa** e non viene mai
     eseguita come codice Python (nessun `eval`). Analizzatore: modulo `ast`
     con elenco chiuso (D18-1, decisa il 2026-10-09).
   - Nel campo comandi l'espressione si può scrivere preceduta o seguita da
     `=`: il segno distingue un calcolo da un comando senza parole chiave in
     più. La compatibilità con la sintassi degli script di Aladin dipende da
     A8 (rimandata dopo il livello 1).
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
   - **Solo i formati standard di unità** (D18-2, corretta il 2026-10-10):
     una stringa di unità si accetta se è valida nel formato **FITS** o, se
     non lo è, nel formato **VOUnit** di `astropy.units`
     (`Unit(s, format="fits")`, `Unit(s, format="vounit")`); il formato usato
     è scritto nel risultato. Nessuna tabella di alias: le unità fuori da
     questi due standard danno `UNIT_UNKNOWN`. La sintassi
     `convert … into …` si decide con A8.
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

### Decisioni del proprietario del 2026-10-12 e divisione in parti

**Divisione in 5 parti (approvata dal proprietario il 2026-10-12):**

| Parte | Contenuto | Test |
|---|---|---|
| P1 | `CalculatorResult` ed `evaluate_expression` con `ast` a elenco chiuso; `skydist` chiama `angular_distance` del 17 | T1–T5 |
| P2 | `convert_time` con scala obbligatoria | T15–T17 |
| P3 | `convert_units` (FITS/VOUnit, equivalenze solo su richiesta come da D18-3, sessagesimali con il 10, date con P2) | T6–T9 |
| P4 | `convert_pixel_value` (BZERO/BSCALE/BLANK, indice di colore con `set_display` dell'11, clic tramite `read_pixel` del 17) | T10–T12 |
| P5 | `calculate_coordinates` con i moduli 10 e 17 | T13, T14, T18 |

- **D18-5 decisa** (§13): espressioni lunghe al massimo **1000 caratteri**
  e con **profondità di annidamento al massimo 50**, configurabili;
  superamento → `CALC_TOO_COMPLEX` esplicito, prima della valutazione.
- **D18-6 decisa** (§13): il valore **grezzo** di un pixel si legge con
  `astropy.io.fits` e l'opzione **`do_not_scale_image_data=True`** (nessun
  calcolo inverso dal valore fisico); verifica prima del codice di P4.
- **T18:** finché il modulo 24 non esiste, il test **riesegue il comando
  registrato nel `CalculatorResult`** e confronta il risultato.

**Codice: `src/astrotwo/core/calculators.py`**, errori `CalculatorError` con
gli identificatori di §10 (gli errori dei moduli 10, 13 e 17 passano con lo
stesso identificatore).

**P1 — calcolatrice algebrica (scritta il 2026-10-12).** Scelte minori:

1. **`CalculatorResult`:** calcolatrice, input interpretato, valore, unità
   (`astropy.units`, o "non dichiarata" quando la fonte non la dichiara) o
   scala, libreria e versione, note, istante della richiesta in UTC e
   **comando registrato** (`CalculatorCommand`: nome della funzione e
   argomenti come interpretati, con la forma testuale `text`). Senza unità
   né scala → `TypeError` (errore di programmazione, §9).
   **`run_command(command)`** riesegue un comando registrato chiamando solo
   le cinque funzioni delle calcolatrici; il formato del registro resta del
   24.
2. **Grammatica:** la stessa tabella `FUNCTIONS`/`CONSTANTS` del 13 (D13-8),
   numeri solo in notazione decimale o esponenziale (`0x10`, `1_000`, `1j`
   → `CALC_SYNTAX_ERROR`), `^` potenza (`**` rifiutato), un `=` facoltativo
   all'inizio o alla fine. Nomi, funzioni, attributi o indici non previsti
   (es. `__import__(...)`, `open(...)`, `True`) → `CALC_UNKNOWN_FUNCTION`;
   altri costrutti (stringhe, confronti, `lambda`, liste) →
   `CALC_SYNTAX_ERROR` con la posizione. L'albero si controlla tutto prima
   di calcolare.
3. **Limiti (D18-5):** lunghezza (`max_length`, 1000) controllata sul testo
   ricevuto; **profondità di annidamento** = massimo numero di parentesi
   aperte una dentro l'altra, comprese quelle delle funzioni (`max_depth`,
   50), controllata prima dell'analisi. Una catena lunga ma non annidata
   (`1+1+…`) è ammessa entro la lunghezza; una catena che supera la
   ricorsione dell'analizzatore (es. 990 `-` di fila) → `CALC_TOO_COMPLEX`.
4. **Unità del risultato:** adimensionale, o **gradi se l'espressione è una
   sola chiamata di `skydist`**; se `skydist` o le funzioni che danno angoli
   (`asin`, `asind`, `rad2deg`…) stanno dentro un'espressione più grande, i
   loro valori sono numeri puri e il risultato lo dichiara in una nota.
5. **Errori numerici** (`float64`, `numpy.errstate`): `/` e `%` per zero e
   `0^(negativo)` → `CALC_DIVISION_BY_ZERO`; dominio non valido nelle
   funzioni (anche `ln(0)`) o potenza non reale (`(-8)^(1/3)`) →
   `CALC_DOMAIN_ERROR`; risultato o numero scritto oltre `float64` →
   `CALC_OVERFLOW`; l'underflow verso 0 dà 0 (valore finito).
6. **`skydist`:** chiama `angular_distance` del 17 (che usa `skydist` del 13,
   D13-10) con le due coppie in gradi decimali; le due coppie si intendono
   nello stesso sistema (la distanza non dipende da quale: il punto si crea
   in `icrs` solo come contenitore, scritto nella nota). Coordinate fuori
   intervallo → `COORD_OUT_OF_RANGE` del 10. **Sessagesimali con `:`:
   FERMI su D18-7** (§13) → `CALC_SYNTAX_ERROR` che lo dice.

**P2 — calcolatrice del tempo (scritta il 2026-10-12).** Scelte minori:

1. **Formati di ingresso** (`time_format`): `iso` (ISO 8601 con `T`, con lo
   spazio o solo la data; formati `isot`/`iso` di `astropy.time`), `jd`,
   `mjd`, `jyear`, `byear` (numeri finiti; un numero scritto come testo →
   `TIME_INVALID`). Formato non previsto, data inesistente (es. 30
   febbraio) o testo non leggibile → `TIME_INVALID` con il formato atteso.
2. **Scale** (`scale` obbligatoria, `target_scale` facoltativa, maiuscole o
   minuscole): UTC, TAI, TT, TDB, TCB, TCG, UT1. Mancante, vuota o non
   riconosciuta (anche `local`, che non è una scala astronomica) →
   `TIME_SCALE_REQUIRED` con l'elenco.
3. **Uscita** (`TimeRepresentations`): ISO 8601 al nanosecondo, JD, MJD,
   anno giuliano e besseliano in `float64` (risoluzione del JD ≈ 40 µs,
   dichiarata) e il JD in due parti `jd1 + jd2` a precisione piena; la
   scala in ogni rappresentazione (`text`).
4. **Avvisi** di `astropy`/ERFA (es. "dubious year" per UTC oltre la tabella
   dei secondi intercalari) riportati nelle note, mai nascosti.
5. **UT1:** con le tabelle IERS già disponibili ad `astropy`, **senza
   scaricamento automatico** durante la conversione (nessun accesso alla
   rete nascosto); se la conversione non si può fare → `TIME_INVALID`.

**P3 — convertitore di unità (scritta il 2026-10-12/13).** Scelte minori:

1. **Firma:** `convert_units(value, from_unit, to_unit, equivalency=None, *,
   reference=None, sexagesimal=None, scale=None, target_scale=None)`.
2. **Unità (D18-2):** prima formato FITS, poi VOUnit; il formato usato è
   nelle note. Non valida in entrambi → `UNIT_UNKNOWN` con fino a 5 **unità
   simili** (l'unità come la legge il formato generico di `astropy`, se la
   riconosce, e le più vicine del registro di `astropy.units` con
   `difflib`, purché valide in FITS o VOUnit).
3. **Valore:** numero finito; testo = espressione della calcolatrice
   algebrica (P1; se è una sola `skydist`, in gradi, `from_unit` deve essere
   un angolo); **angolo sessagesimale** (`d:m:s` o `h:m:s`): `hourangle` non
   esiste in FITS/VOUnit, quindi si dichiara `sexagesimal="degrees"` o
   `"hours"` (mancante → `UNIT_SEXAGESIMAL_UNIT_REQUIRED`), `from_unit=None`,
   lettura con `parse_sexagesimal` del 10; **data ISO 8601**:
   `from_unit=None`, `to_unit` ∈ `iso`, `jd`, `mjd`, `jyear`, `byear`,
   `scale` obbligatoria, calcolo di `convert_time` (P2), risultato con scala.
4. **Equivalenze (D18-3)** solo con `equivalency` esplicita: `spectral`,
   `spectral_density`, `temperature`, `parallax`, `doppler_radio`,
   `doppler_optical`, `doppler_relativistic`; per densità spettrale e
   Doppler il riferimento (`reference`, `Quantity`) è obbligatorio
   (`UNIT_REFERENCE_REQUIRED`); nome sconosciuto →
   `UNIT_EQUIVALENCY_UNKNOWN`. Senza equivalenza, unità di dimensioni
   diverse (anche °C ↔ K) → `UNIT_INCOMPATIBLE` con le due grandezze
   fisiche.
5. **Magnitudini (D18-4):** un lato logaritmico (`mag`, `dex`: in `astropy`
   si decompongono in `dex`) e l'altro no → `UNIT_ZERO_POINT_REQUIRED`;
   `mag` ↔ `mmag` ammessa.
6. **Non finiti:** valore in ingresso o risultato non finito (es. 0 Hz in
   lunghezza d'onda) → `CALC_DOMAIN_ERROR`.

**P4 — calcolatrice dei pixel (scritta il 2026-10-13).** Verifica di D18-6
del 2026-10-13 con `astropy` 8.0.1: con `do_not_scale_image_data=True`,
`section` restituisce il valore intero scritto nel file (anche quello
uguale a `BLANK`), mentre il modulo 11 tiene in memoria il valore fisico nel
tipo prodotto da `astropy.io.fits` (`float32` per `BITPIX = 16` scalato) con
NaN al posto di `BLANK`. Scelte minori:

1. **A mano:** `raw` oppure `physical` (uno solo), `bzero` e `bscale`
   **obbligatori** (nessun valore assunto), `blank` intero facoltativo,
   `bunit` facoltativo (senza: unità "non dichiarata"). Fisico → grezzo con
   BSCALE = 0 → `PIXEL_BSCALE_ZERO`; grezzo non intero restituito senza
   arrotondamento, con nota; grezzo uguale a `BLANK` → `PIXEL_BLANK`.
2. **Clic** (`image`, `position`): posizione e valore in memoria con
   `read_pixel` del 17; `BZERO`, `BSCALE`, `BLANK` dall'intestazione con
   `pixel_scaling` dell'11 (assenti: 0 e 1 come da standard FITS, scritto
   nelle note); **valore grezzo dal file** con `read_raw_pixel` dell'11
   (`astropy.io.fits` e `do_not_scale_image_data=True`, D18-6; errori
   dell'11 inoltrati con lo stesso identificatore). Il fisico è ricalcolato con la
   regola FITS in `float64`; se differisce dal valore tenuto dall'11 (tipo
   di `astropy.io.fits`), entrambi sono nel risultato. Immagine non FITS o
   **derivata** (taglio, operazioni: `history` non vuota, i pixel non sono
   più quelli del file) → `PIXEL_RAW_UNAVAILABLE`. Posizione mostrata in
   convenzione FITS (`fits_position`), interna numpy (DC7).
3. **Indice di colore** (`DisplaySettings`: vmin, vmax, gamma, stretch,
   palette): valore normalizzato di `set_display` dell'11 — sul solo valore
   per le funzioni di trasferimento punto per punto, sull'immagine intera
   per `histeq` (che dipende da tutta l'immagine: a mano o su
   un'anteprima a due livelli → `OPERATION_UNSUPPORTED`); indice =
   floor(v · N) della palette di `matplotlib` (N = 256; v = 1 → 255), la
   regola con cui la palette sceglie il colore. **Lo 0 non è riservato:** il
   modulo 11 rende trasparenti i pixel non finiti con l'alfa, quindi la
   variante 1–255 non si applica; pixel non finito → nessun indice, con nota.
4. **Nessuna lettura di file nel 18** (decisione del proprietario del
   2026-10-13): il valore grezzo lo legge `read_raw_pixel` dell'11; dati,
   intestazione e visualizzazione vengono dall'11.

**P5 — calcolatrice delle coordinate (scritta il 2026-10-13).** Scelte
minori:

1. **Firma:** `calculate_coordinates(position, targets, *, epoch=None,
   motion=None, offsets=None, direction=None, to_point=None)`.
   `position`: `SkyFrame`/`SkyCoord`, `CoordinateInput` (coordinate scritte:
   numeri in gradi o testo sessagesimale; per la longitudine in testo si
   dichiara `lon_sexagesimal="hours"` o `"degrees"`, altrimenti
   `UNIT_SEXAGESIMAL_UNIT_REQUIRED`; latitudine sessagesimale in gradi;
   lettura con `parse_sexagesimal` del 10) oppure `CatalogSource` del 17
   (riga di catalogo: epoca e moto proprio dai metadati del 13, come
   `auto_distance`). `targets`: almeno un `CoordinateTarget(frame,
   equinox, obstime)`.
2. **Ordine fisso:** propagazione all'`epoch` (coordinate scritte:
   `ProperMotion` + `propagate_position` del 10; riga di catalogo:
   `propagate` del 13); poi **offset** (`offsets` = Δα·cos δ, Δδ con
   `apply_offsets` del 17) **oppure** calcolo inverso (`direction` =
   distanza, angolo di posizione con `offset_position` del 17), non entrambi;
   poi la conversione in ogni sistema richiesto con `convert_coordinates` del
   10; `to_point` dà gli offset verso quel punto (`angular_offsets` del 17).
   `epoch` senza moto proprio → `EPOCH_REQUIRED` (nessun moto nullo
   assunto); `motion` senza `epoch` → `TypeError`.
3. **Uscita** (`CoordinatesOutput`): posizione di base e, per ogni sistema,
   `CoordinateRepresentation` con gradi decimali (`float64`) e
   sessagesimale — longitudine in **h:m:s** nei sistemi equatoriali (che
   hanno `ra`, precisione 0,00001 s) e in d:m:s negli altri (0,0001″),
   latitudine d:m:s con segno (0,0001″) — con frame ed epoca dichiarati.
   Unità del risultato: gradi.
4. **T18:** il test riesegue con `run_command` i comandi registrati dei
   risultati di T1–T16 (espressioni, unità, pixel anche con clic, coordinate,
   tempo) e confronta input interpretato, valore, unità e scala.

## 4. Cosa NON fa

- Non disegna finestre né campi di input: l'interfaccia delle calcolatrici è
  di `40-ui-finestra-principale.md` (menu Strumenti) e, per il clic sulla
  vista, di `41-ui-visualizzatore-cielo.md`.
- Non converte coordinate e non propaga posizioni da sé: lo fa il modulo
  `10-core-coordinate-wcs.md`; non calcola offset né posizioni da distanza +
  angolo di posizione: lo fa `17-core-misure.md`; qui si raccolgono input e
  si presentano i risultati.
- Non legge file FITS né applica funzioni di trasferimento: lo fa
  `11-core-immagini-fits.md` (anche il valore grezzo di un pixel, D18-6:
  `read_raw_pixel` dell'11).
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
  `11-core-immagini-fits.md` (BZERO, BSCALE, BLANK, valore grezzo con
  `read_raw_pixel`, parametri di visualizzazione), `13-core-cataloghi.md` (moto proprio, velocità radiale ed
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
| in | `from_unit`, `to_unit` | stringa | formato FITS o VOUnit di `astropy.units` | D18-2 |
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

AstroTwo usa `astropy.units` ovunque, con i soli formati standard FITS e
VOUnit per le stringhe di unità (D18-2).

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
| Equivalenza non offerta | rifiuto con l'elenco di D18-3 | `UNIT_EQUIVALENCY_UNKNOWN` |
| Densità spettrale o Doppler senza riferimento | rifiuto: il riferimento è obbligatorio | `UNIT_REFERENCE_REQUIRED` |
| Angolo sessagesimale senza `sexagesimal` (gradi o ore) | rifiuto | `UNIT_SEXAGESIMAL_UNIT_REQUIRED` |
| Sessagesimale con i due punti in `skydist` senza `colon_units`, o `colon_units` non valido (D18-7) | rifiuto: con i due punti l'unità è ambigua | `UNIT_SEXAGESIMAL_UNIT_REQUIRED` |
| Unità non convertibili tra loro senza equivalenza | rifiuto con le due dimensioni fisiche | `UNIT_INCOMPATIBLE` |
| Magnitudine verso flusso senza punto zero | rifiuto | `UNIT_ZERO_POINT_REQUIRED` |
| Data non valida | rifiuto con il formato atteso | `TIME_INVALID` |
| Scala di tempo mancante | rifiuto: la scala non si assume mai | `TIME_SCALE_REQUIRED` |
| `BSCALE = 0` nel calcolo inverso (fisico → grezzo) | rifiuto | `PIXEL_BSCALE_ZERO` |
| Valore grezzo uguale a `BLANK` | nessun valore fisico; dichiarato "pixel senza valore" | `PIXEL_BLANK` |
| Clic su un'immagine non FITS o derivata (taglio, operazioni) | nessun valore grezzo | `PIXEL_RAW_UNAVAILABLE` |
| Indice di colore con `histeq` senza l'immagine intera | rifiuto: l'equalizzazione dipende da tutta l'immagine | `OPERATION_UNSUPPORTED` |
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
| T5 | `skydist` | `skydist` su due coppie di coordinate scelte dal tester; anche sessagesimali con l'unità nel testo (ore e gradi, `d/m/s` e `°′″`) e con i due punti con e senza `colon_units` (D18-7) | coincide con `angular_distance` del modulo 17 e con `SkyCoord.separation`; due punti senza unità → `UNIT_SEXAGESIMAL_UNIT_REQUIRED` | ricalcolo con Astropy |
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
| T16 | Data in MJD | `2024-02-29T18:00:00` in scala UTC (giorno bisestile, frazione di giorno) | MJD 60369.75, ricalcolato nel test con `astropy.time.Time(..., scale="utc").mjd` | `astropy.time` |
| T17 | Scala mancante | data senza scala | `TIME_SCALE_REQUIRED` | test di unità |
| T18 | Riproducibilità | rieseguire il comando registrato di T1–T16 | risultati identici | confronto con il registro del modulo 24 |

## 13. Decisioni aperte

- **D18-1 — Analizzatore delle espressioni: DECISA il 2026-10-09 (decisione
  del proprietario sulla checklist del livello 1).** analizzatore sul modulo
  **`ast`** della libreria standard con **elenco chiuso** di nodi e nomi;
  nessuna dipendenza esterna; `^` tradotto in potenza.
- **D18-2 — Formati delle unità: DECISA il 2026-10-09, CORRETTA il
  2026-10-10 (decisione del proprietario, regola d'oro n. 8).** **Nessuna
  tabella di alias di Aladin**: solo i formati standard di unità **FITS** e
  **VOUnit** di `astropy.units`, con il formato usato scritto nel risultato;
  le altre stringhe danno `UNIT_UNKNOWN`. **Motivazione:** sono gli standard
  pubblici usati da FITS e dal Virtual Observatory, già implementati e
  testati in `astropy.units`. La sintassi `convert … into …` si decide con
  A8.
- **D18-3 — Equivalenze offerte: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** spettrale, densità di flusso
  spettrale, temperatura, parallasse ↔ distanza e Doppler (radio, ottico,
  relativistico; frequenza a riposo obbligatoria), **solo su richiesta
  esplicita**.
- **D18-4 — Magnitudini: DECISA il 2026-10-09 (decisione del proprietario
  sulla checklist del livello 1).** la conversione magnitudine ↔ flusso **sta
  solo nel modulo 20**: il 18 è livello 1 e non può dipendere dal 20; il
  convertitore la rifiuta con `UNIT_ZERO_POINT_REQUIRED`.
- **D18-5 — Limiti delle espressioni: DECISA il 2026-10-12 (decisione del
  proprietario).** Lunghezza massima **1000 caratteri**, profondità di
  annidamento massima **50**, entrambe configurabili; superamento →
  `CALC_TOO_COMPLEX` prima della valutazione. **Motivazione:** limiti ampi
  per ogni uso reale della calcolatrice, che impediscono di bloccare
  l'analizzatore con un testo patologico.
- **D18-6 — Lettura del valore grezzo: DECISA il 2026-10-12 (decisione del
  proprietario).** Il valore grezzo si legge con `astropy.io.fits` e
  `do_not_scale_image_data=True`; verifica prima del codice di P4.
  **Motivazione:** il valore grezzo è quello scritto nel file, non una
  ricostruzione dal valore fisico (che in `float32` può non tornare
  esatta).

- **D18-7 — Sessagesimali in `skydist`: DECISA il 2026-10-13 (decisione
  del proprietario).** Nei sessagesimali **l'unità deve essere scritta nel
  testo** (`h`/`m`/`s` per le ore, `d`/`m`/`s` o `°′″` per i gradi), letti
  con `parse_sexagesimal` del 10. Il formato con i due punti (es.
  `10:30:00`) è ambiguo: **errore**, a meno che l'unità sia dichiarata con
  un **parametro esplicito** (`colon_units`). **Nessuna convenzione basata
  sulla posizione dell'argomento** (la raccomandazione "1° e 3° in ore" non
  è stata adottata). Test. Applicata in §3 (P1, scelta 6), §10, §12 (T5).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-08 | Claude Code | Creazione del file (stato: bozza). Origine: riga H4 di `03-parita-aladin.md` (manuale di Aladin ed. giugno 2022, sez. 5.7.1–5.7.5); cinque calcolatrici, dipendenze da 10, 11, 13 e 17 senza riscriverne le funzioni; convenzione dei pixel DC7; decisioni aperte D18-1…D18-6. |
| 2026-10-09 | Claude Code | **D18-1…D18-4 DECISE** (checklist del livello 1): analizzatore `ast` con elenco chiuso; alias delle unità di Aladin in un'unica tabella (elenco da verificare); equivalenze spettrale, densità di flusso, temperatura, parallasse, Doppler su richiesta; magnitudine ↔ flusso solo nel 20. §3, §8 aggiornati. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-09. |
| 2026-10-09 | Claude Code | **Decisione del proprietario D10-8 (modulo 10) applicata** (autorizzazione esplicita a modificare il file approvato): `coordinate_calculator` tolta dal 10; la calcolatrice delle coordinate usa `convert_coordinates`/`propagate_position` del 10 e `angular_offsets`/`apply_offsets`/`offset_position` del 17 (§3, §4, §5, §7, §11). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Regola d'oro n. 8** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): D18-2 corretta — niente tabella di alias di Aladin, solo i formati standard FITS e VOUnit di `astropy.units` (§3, §6, §8, §13); T16 con un esempio nostro (`2024-02-29T18:00:00` UTC → MJD 60369.75, ricalcolato con `astropy.time`) al posto di quello del manuale; `=` prima o dopo l'espressione con motivazione nostra. Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **Decisioni del proprietario del 2026-10-12** (autorizzazione esplicita a modificare il file approvato): divisione in 5 parti (P1 espressioni, P2 tempo, P3 unità, P4 pixel, P5 coordinate) in §3; **D18-5 decisa** (1000 caratteri, annidamento 50, configurabili, `CALC_TOO_COMPLEX`); **D18-6 decisa** (valore grezzo con `do_not_scale_image_data=True`); T18 con la riesecuzione del comando registrato finché il 24 non esiste. Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **P1 scritta** (`calculators.py`: `CalculatorError`, `CalculatorCommand`, `CalculatorResult`, `run_command`, `evaluate_expression`; T1–T5 e limiti di D18-5). Scelte minori di P1 in §3. Nuova **D18-7** (sessagesimali in `skydist`, Gruppo 3), che ferma solo quel pezzo. Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **P2 scritta** (`convert_time`, `TimeRepresentations`; T15–T17). Scelte minori di P2 in §3. Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **P3 scritta** (`convert_units`, `EQUIVALENCIES`; T6–T9). Scelte minori di P3 in §3; nuovi casi in §10 (`UNIT_EQUIVALENCY_UNKNOWN`, `UNIT_REFERENCE_REQUIRED`, `UNIT_SEXAGESIMAL_UNIT_REQUIRED`). Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **P4 scritta** (`convert_pixel_value`, `DisplaySettings`, `PixelValues`; T10–T12); D18-6 verificata prima del codice. Scelte minori di P4 in §3; §4 con l'eccezione del valore grezzo (D18-6); nuovi casi in §10 (`PIXEL_RAW_UNAVAILABLE`, `histeq` senza immagine). Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **P5 scritta — modulo 18 completo tranne i sessagesimali in `skydist` (D18-7)** (`calculate_coordinates`, `CoordinateInput`, `CoordinateTarget`, `ProperMotion`, `CoordinatesOutput`; T13, T14, T18 con la riesecuzione dei comandi registrati). Scelte minori di P5 in §3. Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **D18-7 decisa dal proprietario il 2026-10-13** (autorizzazione esplicita a modificare il file approvato) e scritta: sessagesimali di `skydist` con l'unità scritta nel testo (h/m/s, d/m/s, °′″) letti con `parse_sexagesimal` del 10; due punti → `UNIT_SEXAGESIMAL_UNIT_REQUIRED` salvo il parametro esplicito `colon_units`; nessuna convenzione sulla posizione; sessagesimali solo negli argomenti di `skydist` (§3 P1 scelta 6, §10, T5). Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **Decisione del proprietario del 2026-10-13** (autorizzazione esplicita a modificare il file approvato): la lettura del valore grezzo passa all'11 (`read_raw_pixel`); il 18 la richiama; tolta l'eccezione dal §4 (§3 P4 scelte 2 e 4, §5). Stato `approvato` invariato. |
