# 02-convenzioni.md — convenzioni di documentazione, nomi, unità, coordinate, versioni, test

**Stato:** approvato

## 1. Scopo

Fissare le convenzioni usate in tutte le specifiche e nel codice, così che
documenti e implementazioni siano coerenti e confrontabili con la letteratura.

## 2. Convenzioni di documentazione

- **Lingua:** italiano per la prosa; inglese per nomi di file, moduli, classi,
  funzioni, costanti, identificatori di errore e riferimenti a standard.
- **Struttura:** ogni file di modulo segue `TEMPLATE-modulo.md`, 14 sezioni
  nello stesso ordine, nessuna sezione omessa (se non pertinente: "non applicabile").
- **Autosufficienza:** chi legge un file di modulo deve capirlo senza leggere
  il codice né altri file, salvo i rimandi espliciti.
- **Stato in testa:** ogni file dichiara `bozza`, `in revisione` o `approvato`.
  Solo `approvato` autorizza il codice del corrispondente modulo.
- **Numerazione file:**
  `00-09` generali · `10-19` nucleo · `20-29` analisi · `30-39` IA ·
  `40-49` interfaccia · `50-59` funzioni avanzate · `60-69` distribuzione e test.
- **Decisioni:** una scelta tecnica non ancora presa va in "Decisioni aperte"
  del file pertinente (e, se riguarda più moduli, in `panoramica.md`), mai
  decisa in silenzio.
- **Incertezza:** ciò che non è verificato si scrive "da verificare" oppure
  "da verificare con la documentazione ufficiale". Eccezione: in
  `03-parita-aladin.md` lo stato di verifica si esprime con la colonna
  "Copertura" (`nota`, `verificata`, `corretta`, `non trovata`,
  `inclusa (decisione del proprietario)`, `extra`).
- **Aggiornamento:** a ogni progresso si aggiornano `panoramica.md` e lo stato
  in `INDICE.md`. Un progresso = file creato, file che cambia stato, decisione
  presa, modulo completato.

## 3. Convenzioni di nomenclatura (codice)

| Elemento | Convenzione | Esempio |
|---|---|---|
| File di specifica | `NN-nome-con-trattini.md` | `10-core-coordinate-wcs.md` |
| File Python | `snake_case.py` dentro `src/astrotwo/<sotto-pacchetto>/` (struttura decisa con A3 in `01-architettura.md`); stessa radice della specifica senza il numero di gruppo | `10-core-coordinate-wcs.md` → `src/astrotwo/core/coordinates_wcs.py` |
| Sotto-pacchetti | uno per gruppo di specifiche: `core`, `analysis`, `ai`, `ui`, `advanced` (deciso con A3) | `src/astrotwo/analysis/` |
| Cartella dei test | `tests/` con la stessa struttura di `src/astrotwo/` (deciso con A3) | `tests/core/…` |
| Classi | `PascalCase` | `SkyCoordinate` |
| Funzioni e metodi | `snake_case` | `load_fits_image` |
| Costanti | `MAIUSCOLO_CON_TRATTINI` | `MAX_CATALOG_ROWS` |
| Identificatori d'errore | `MAIUSCOLO`, in inglese, prefisso del dominio | `WCS_OUT_OF_RANGE`, `NET_TIMEOUT` |
| Nomi di file di output | `snake_case` con timestamp ISO 8601 quando serve | `lightcurve_2026-10-04T13:00:00Z.csv` |
| Nomi IA (strumenti) | `verbo_oggetto` in inglese | `cone_search`, `plot_lightcurve` |

## 4. Unità di misura

Regola: **unità esplicite sempre**, mai un numero "nudo".

| Quantità | Unità interna (memoria/calcolo) | Unità di visualizzazione | Nota |
|---|---|---|---|
| Ascensione retta, Declinazione | gradi (float64) | sessagesimali HH:MM:SS.s / ±DD:MM:SS.s | conversione con Astropy |
| Coordinate galattiche l, b | gradi | gradi o sessagesimali | |
| Distanze angolari | gradi interni | arcosecondi / arcminuti / gradi, a scelta dell'utente | |
| Magnitudini | float64, unità del catalogo/sistema fotometrico dichiarato | float con cifre dichiarate | il sistema fotometrico va sempre riportato |
| Lunghezze d'onda | metri interni (conforme ad Astropy/IAU) | Å, nm o μm, a scelta | 1 Å = 1e-10 m, conversione con Astropy |
| Velocità | m/s interni | km/s | |
| Tempi | `astropy.time`, JD numerico (vedi §5) | ISO 8601 con scala dichiarata | scala sempre dichiarata (UTC, TDB, TCB) |
| Flussi | W/m² interni (SI) | Jy, mJy, erg/s/cm²/Å | conversione con Astropy `Unit` |
| Energie | joule interni (SI) | eV, keV | conversione con Astropy |

- Tutte le conversioni passano per `astropy.units`; nessuna conversione manuale.
- L'unità di un dato va memorizzata insieme al dato (schema colonne con unità
  come da `astropy.table`), non solo mostrata.
- Le preferenze di visualizzazione (cifre decimali, unità mostrate) sono
  impostazioni dell'utente salvate nelle preferenze; il loro formato è deciso
  in `40-ui-finestra-principale.md`.

## 5. Sistemi di coordinate, epoche e tempi

| Aspetto | Convenzione |
|---|---|
| Sistema di riferimento celeste predefinito | **ICRS** (equivalente operativo di J2000) |
| Epoca predefinita di posizioni | **mai assunta**: l'epoca di ogni dato si legge dai suoi metadati (decisione D10-2/D13-2 del 2026-10-04); epoca di visualizzazione = epoca dell'immagine se nota, altrimenti **J2000**; ogni catalogo ha **ciascuno la propria epoca di riferimento**; l'epoca usata è sempre scritta nel risultato |
| Coordinate supportate | equatoriali (RA/Dec), galattiche (l, b), eclittiche, e quelle previste da `astropy.coordinates` |
| Conversioni e precessione | solo via `astropy.coordinates` (FrameTransformations) — mai formule scritte a mano |
| Posizioni con moto proprio | propagazione a un'epoca richiesta con `astropy.coordinates.SkyCoord.apply_space_motion`; **epoca di origine e moto proprio letti dai metadati o richiesti, mai assunti** (D10-2) |
| Coordinate di output | sempre con sistema ed epoca dichiarati, mai "gradi e basta" |
| Scala dei tempi | **si dichiara sempre la scala di tempo** (UTC, TDB, TCB; TAI dove serve); UTC come riferimento di visualizzazione; manipolazioni precise con `astropy.time` |
| Formato tempo | **internamente numerico (JD) via `astropy.time`**; ISO 8601 (`YYYY-MM-DDTHH:MM:SS.s`) con scala esplicita **solo** in interfaccia e file (decisione D16-3 del 2026-10-04) |
| Longitudine galattica | l in [0°, 360°); b in [−90°, +90°] |
| RA | in [0°, 360°) internamente; visualizzata in [0h, 24h) |

Epoca di moto proprio delle posizioni propagata: **mai assunta** — epoca di
origine e moto proprio letti dai metadati o richiesti all'utente, altrimenti
errore (D10-2, decisa il 2026-10-04; dettaglio in `10-core-coordinate-wcs.md`).
Ogni catalogo dichiara la **propria epoca di riferimento** (D13-2, decisa il
2026-10-04). La gestione delle epoche nelle curve di luce resta da decidere in
`22-analisi-curve-di-luce.md` (livello 2, non ancora scritto).

## 6. Convenzioni sui numeri

- Precisione (DC6, decisa il 2026-10-04 con D11-1): **in memoria resta il
  tipo nativo del file** (float32 o float64 come da sorgente); **ogni calcolo
  è in `float64`**; **`float32` solo per la visualizzazione**; nelle misure
  `float64` obbligatorio.
- Le conversioni angolari usano `astropy.units.Quantity`: nessun angolo senza unità.
- La visualizzazione non altera il valore: le cifre mostrate sono arrotondamenti
  di presentazione, il valore pieno resta disponibile (copia, export).
- **L'IA non calcola mai:** ogni numero mostrato o registrato riporta sempre la
  libreria/algoritmo deterministico che lo ha prodotto (regola d'oro n. 1).

### Convenzione dei pixel (DC7, decisa il 2026-10-08, confermata dal proprietario)

Due convenzioni convivono e vanno tenute separate (origine: riga H25 di
`03-parita-aladin.md`, manuale di Aladin ed. giugno 2022, sez. 8.2):

| Convenzione | Primo pixel | Centro del primo pixel | Ordine degli assi | Dove si usa |
|---|---|---|---|---|
| **FITS** (standard FITS/WCS) | indice **1** | (1, 1); angolo inferiore sinistro a (0.5, 0.5) | (x = asse `NAXIS1`, y = asse `NAXIS2`) | intestazioni FITS (`CRPIX`), file di regione e tabelle di posizioni pixel scritte da/per altri programmi, **valori mostrati all'utente** |
| **numpy** (array in memoria) | indice **0** | (0, 0) | `array[y, x]` (riga, colonna) | dati in memoria, calcoli, chiamate pixel ↔ cielo di `astropy.wcs` con origine 0 |

**Regola di conversione unica** (per ogni asse, valori anche non interi):

- `x_fits = x_numpy + 1` e `y_fits = y_numpy + 1`; all'inverso
  `x_numpy = x_fits − 1`, `y_numpy = y_fits − 1`;
- l'indice di array è `array[y_numpy, x_numpy]` (prima la riga, poi la colonna).

Vincoli:

- **Internamente** (memoria, calcoli, scambio tra moduli) le coordinate pixel
  sono **sempre in convenzione numpy (origine 0)**; la conversione verso la
  convenzione FITS avviene **solo ai confini**: visualizzazione, lettura e
  scrittura di file e intestazioni.
- La conversione esiste in **un solo punto del codice**, la funzione
  `convert_pixel_convention` del modulo `10-core-coordinate-wcs.md`; gli altri moduli la richiamano e non la
  riscrivono. Le chiamate di `astropy.wcs` indicano sempre l'origine in modo
  esplicito.
- Ogni coordinata pixel in uscita dichiara la convenzione usata (`fits` o
  `numpy`), come si fa con unità e sistemi di riferimento.
- I file che seguono convenzioni diverse (es. IDL con angolo inferiore
  sinistro a (0.0), citato nella sez. 8.2 del manuale di Aladin) si
  convertono in ingresso dichiarando la convenzione d'origine.

**Moduli che la usano:** `10-core-coordinate-wcs.md` (WCS pixel ↔ cielo,
punto unico di conversione), `11-core-immagini-fits.md` (lettura, ritagli,
valori dei pixel), `13-core-cataloghi.md` (colonne di posizione in pixel, es.
cataloghi SExtractor), `17-core-misure.md` (misure e lettura del valore sotto
il cursore), `18-core-calcolatrici.md` (calcolatrice dei pixel),
`20-analisi-fotometria.md` (aperture e centroidi), `23-analisi-cubi-di-dati.md`
(spettri da cubo), `41-ui-visualizzatore-cielo.md` (coordinate pixel mostrate
e file di regione).

## 7. Convenzioni su versioni

| Cosa | Convenzione | Stato |
|---|---|---|
| Versione dell'app AstroTwo | SemVer `MAJOR.MINOR.PATCH` (es. `0.1.0` finché in sviluppo) | decisa (DC4, 2026-10-09); applicazione in `60-distribuzione-dmg.md` |
| Versione delle specifiche | la data nel "Registro modifiche" di ogni file; nessun numero di versione separato | decisa |
| Versione dei file di output (tabelle, pipeline) | intestazione del file con versione dello schema e versione dell'app | da decidere in `24-analisi-pipeline-riproducibili.md` |
| Dipendenze Python | dichiarate in `pyproject.toml`, ambiente gestito con `uv` (deciso con A4 in `01-architettura.md`) | struttura decisa; politica di blocco delle versioni esatte da definire in `60-distribuzione-dmg.md` |

## 8. Convenzioni sui test

Dettagli in `61-strategia-test.md`; qui le regole di base:

1. Ogni modulo ha i suoi "Test di accettazione" nel proprio `.md`.
2. I valori attesi vanno **ricalcolati con una libreria consolidata**
   (Astropy, astroquery, healpy, scipy): mai numeri scritti a memoria.
3. Nessun test dipende dalla rete di default; i test di rete sono separati e
   marcati come tali.
4. I test non usano mai una chiave API reale; il livello 3 si testa con doppi
   (stub/mock) del provider.
5. Riproducibilità: un test fallito deve poter essere rieseguito identico.
6. Un modulo si considera verificato solo se i suoi test passano **e** il file
   `.md` è `approvato`.
7. I test vivono in `tests/` con la stessa struttura di `src/astrotwo/`
   (deciso con A3 in `01-architettura.md`); **framework ed esecutore: `pytest`**
   (decisione del proprietario del 2026-10-09, anticipata da
   `61-strategia-test.md`, dove restano gli altri dettagli).

## 9. Decisioni aperte

- **DC1 — Scala temporale per le osservazioni:** **regola decisa il
  2026-10-04 (con D16-3):** internamente il tempo è numerico (**JD** tramite
  `astropy.time`), ISO 8601 solo in interfaccia e file, e **si dichiara sempre
  la scala di tempo (UTC, TDB, TCB)**; i **MOC temporali usano la scala dello
  standard IVOA (da verificare)**. **Scala predefinita per le serie temporali:
  DECISA il 2026-10-09 — TDB** (tempi baricentrici, BJD_TDB) per l'analisi,
  conservando sempre la scala originale del dato; applicazione in
  `22-analisi-curve-di-luce.md`.
- **DC2 — Epoca per la propagazione delle posizioni nei cataloghi: DECISA il
  2026-10-04 (con D10-2/D13-2):** l'epoca di ogni dato si legge dai suoi
  metadati e **non si assume mai**; epoca di visualizzazione = epoca
  dell'immagine se nota, altrimenti J2000; ogni catalogo ha la propria epoca
  di riferimento; l'epoca usata è sempre scritta nel risultato (regola
  riportata in §5 qui sopra e in `10-core-coordinate-wcs.md` /
  `13-core-cataloghi.md`).
- **DC3 — Cifre di visualizzazione predefinite: DECISA il 2026-10-09
  (decisione del proprietario sulla checklist del livello 1).** RA con 0.01 s,
  Dec con 0.1″, magnitudini con 3 decimali; valori configurabili dall'utente
  nelle preferenze (`40-ui-finestra-principale.md`); il valore pieno resta
  sempre copiabile (§6).
- **DC4 — Formato di versione dell'app: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** **SemVer**
  `MAJOR.MINOR.PATCH` (es. `0.1.0` in sviluppo): permette di confrontare le
  versioni registrate nei comandi riproducibili; applicazione in
  `60-distribuzione-dmg.md`.
- **DC5 — Nomi dei file Python e delle cartelle:** **risolta il 2026-10-04** con
  A3/A4 in `01-architettura.md`: `src/astrotwo/` con sotto-pacchetti
  `core`, `analysis`, `ai`, `ui`, `advanced`, `pyproject.toml`, `uv`, test in
  `tests/` con la stessa struttura (riportato in §3 e §7 qui sopra).
- **DC6 — Precisione float32/float64 nelle immagini: DECISA il 2026-10-04
  (con D11-1):** in memoria il **tipo nativo del file**; **ogni calcolo in
  `float64`**; **`float32` solo per la visualizzazione**; nelle misure
  `float64` obbligatorio (regola riportata in §6 qui sopra e in
  `11-core-immagini-fits.md`).

Le etichette `A…` citate in questo file sono quelle di `01-architettura.md`;
`AP1` è in `03-parita-aladin.md`.

- **DC7 — Convenzione dei pixel: DECISA il 2026-10-08 (decisione del
  proprietario).** FITS (indice da 1) contro numpy (indice da 0), con regola
  di conversione unica nel modulo 10 e uso interno in convenzione numpy;
  testo completo in §6.

DC1 (parte residua), DC3 e DC4 sono decise dal 2026-10-09 (checklist del
livello 1): nessuna decisione di questo file resta aperta.

## 10. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). |
| 2026-10-04 | agente di sviluppo | Allineamento alle decisioni A3/A4/A7: convenzioni file Python e sotto-pacchetti in §3, dipendenze (`pyproject.toml` + `uv`) in §7, struttura `tests/` in §8; DC5 risolta. |
| 2026-10-04 | agente di sviluppo | §2: le incertezze su Aladin si esprimono con la colonna "Copertura" di `03-parita-aladin.md`. |
| 2026-10-04 | agente di sviluppo | §2: aggiunto il valore `inclusa (decisione del proprietario)` alla colonna "Copertura" (decisione P11: parità con Aladin = minimo, non traguardo). |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario (con D10-2/D10-3/D11-1/D13-2/D16-3):** DC2 decisa — epoca letta dai metadati, mai assunta, epoca di visualizzazione = epoca dell'immagine se nota altrimenti J2000, catalogo con propria epoca di riferimento, epoca sempre scritta nel risultato (§5); DC6 decisa — tipo nativo del file in memoria, ogni calcolo in `float64`, `float32` solo per il display (§6); DC1 aggiornata — tempo numerico (JD via `astropy.time`) in memoria, ISO 8601 solo in interfaccia/file, scala di tempo sempre dichiarata (UTC, TDB, TCB), MOC temporali con la scala IVOA (da verificare); resta aperta solo la scala predefinita delle serie temporali (22). |
| 2026-10-08 | Claude Code | Refuso in §4 (lunghezze d'onda): "Ånm" → "Å, nm". |
| 2026-10-08 | Claude Code | §9: la parte aperta di DC1 (scala predefinita delle serie temporali), DC3 e DC4 registrate anche in `decisioni-aperte.md` (Gruppo 2). |
| 2026-10-08 | Claude Code | **DC7 decisa (decisione del proprietario, origine H25 di `03-parita-aladin.md`):** convenzione dei pixel FITS (indice da 1) contro numpy (indice da 0) in §6, con la regola di conversione unica (`fits = numpy + 1` per asse, `array[y, x]`), uso interno in convenzione numpy, conversione solo ai confini e in un solo punto (modulo 10), elenco dei moduli che la usano; voce DC7 in §9. |
| 2026-10-09 | Claude Code | DC7 **confermata dal proprietario** (pixel da 0 in memoria, conversione FITS solo ai bordi); indicata la funzione unica `convert_pixel_convention` del modulo 10. |
| 2026-10-09 | Claude Code | **Decisioni del proprietario (checklist del livello 1):** DC1 parte residua = **TDB** per le serie temporali (scala originale sempre conservata); DC3 = RA 0.01 s, Dec 0.1″, magnitudini 3 decimali, configurabili; DC4 = SemVer. §7 e §9 aggiornati: nessuna decisione aperta in questo file. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-09. |
| 2026-10-09 | Claude Code | §8: **framework dei test = `pytest`** (decisione del proprietario), anticipata da `61-strategia-test.md`. Stato `approvato` invariato. |
