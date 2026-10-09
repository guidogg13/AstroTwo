# 11-core-immagini-fits.md — immagini FITS e visualizzazione

**Stato:** approvato

## 2. Scopo

Aprire, gestire e regolare la visualizzazione delle immagini astronomiche
(FITS e non solo) con la stessa fedeltà scientifica di Aladin, senza mai
alterare i valori dei pixel memorizzati.

## 3. Cosa fa

- **Lettura FITS:** aprire immagini FITS locali (primarie e, se previsto,
  più HDU), leggere header, WCS, unità dei pixel e lineari; rilevare dati
  corrotti o non supportati.
- **Lettura da rete:** aprire immagini da URL (B2) e immagini in formati non
  FITS come JPEG/PNG (B9), con timeout e gestione degli errori espliciti.
- **Scala di visualizzazione:** regolare luminosità e contrasto (B3),
  istogramma / CTF (B4), palette colori per immagini monocrome (B6),
  trasparenza e sovrapposizione tra layer di immagine (B5), coniugazione /
  composizione multibanda (B11). Le regolazioni sono **solo di presentazione**:
  i pixel memorizzati e i valori usati per le misure non cambiano.
- **Taglio (cutout):** estrarre una sottoparte di un'immagine con WCS coerente
  (B8).
- **Ricampionamento e allineamento:** ricampionare un'immagine sulla soluzione
  astrometrica di un'altra e fare il "match" delle viste (B7). Non esiste
  "align" in Aladin: la funzione è il ricampionamento sulla soluzione
  astrometrica.
- **Operazioni su immagini (H5):** aritmetica tra immagini, convoluzione,
  normalizzazione, cambio formato pixel (es. float64 → float32 per il
  display), specchiatura. Ogni operazione produce un **nuovo** oggetto, mai
  la modifica silenziosa dell'originale.
- **Contorni / isofote (H7):** calcolare le linee di livello di intensità
  sull'immagine.
- **Centroide per la calibrazione astrometrica (H6; D10-8 del
  `10-core-coordinate-wcs.md`, decisa il 2026-10-09):** dato un punto
  indicato dall'utente (pixel, convenzione numpy) e una finestra quadrata
  intorno, calcolare il **baricentro pesato sull'intensità** dei pixel della
  finestra (calcolo in `float64` con `scipy.ndimage.center_of_mass`) e
  restituirlo in convenzione numpy; queste posizioni sono quelle che il
  modulo 10 riceve per la calibrazione per associazione di stelle (il 10 non
  legge pixel). **Fondo cielo (D11-7, decisa il 2026-10-09):** prima del
  baricentro si sottrae il fondo, stimato come **mediana dei pixel di una
  corona circolare attorno alla stella con sigma clipping**
  (`astropy.stats.sigma_clipped_stats`, parametri di default della libreria
  `sigma = 3`, `maxiters = 5`, scritti nel risultato); raggi interno ed
  esterno della corona sono parametri obbligatori. Il
  centroide qui serve solo alla calibrazione: la fotometria resta nel `20`
  (D17-4).
- **Cache su disco (A7):** i riquadri di immagine (tagli, HiPS richiesti,
  immagini da rete) si conservano come file su disco con **limite di default
  5 GB, configurabile**, eliminazione dei dati meno usati e, per ogni dato
  servito dalla cache, origine e data di scaricamento mostrabili all'utente
  (D11-3 decisa il 2026-10-04). La cache è quella comune di `04-cache.md`
  (`~/Library/Caches/AstroTwo/`, un solo limite di 5 GB, timeout 10 s / 60 s):
  il modulo non ha una cache propria (CA4).
- **Esportazione:** salvare la vista come immagine e salvare tagli FITS.
- **Formati e compressioni (H22, sez. 8.1 del manuale di Aladin, ed. giugno 2022):**
  FITS anche compressi (RICE, GZIP, **HCOMPRESS / HCOMP**, letti con le HDU
  compresse di `astropy.io.fits`; file `.gz`), file a più estensioni (MEF,
  D11-4), FITS RGB (tre piani di colore), JPEG, PNG e **GIF**. Per JPEG e PNG
  la calibrazione si legge dal segmento di commento o da un file `.hhh` con
  lo stesso nome (H6, sez. 5.14). La **natura del file si riconosce dal
  contenuto** (firma del file), non dall'estensione. Libreria per JPEG, PNG e
  GIF: **`Pillow`** (D11-6, decisa il 2026-10-09; licenza da verificare
  prima del codice). Limite dichiarato da Aladin come riferimento:
  JPEG/PNG con WCS fino a 100 megapixel.
- **Immagini di qualsiasi dimensione (H27, sez. 8.3.1):** strategia per
  dimensione — immagini piccole in memoria; immagini di centinaia di
  megabyte lette dal disco su richiesta (`memmap` di `astropy.io.fits`);
  immagini di più gigabyte con **due livelli di risoluzione**: prima una vista
  a bassa risoluzione ottenuta leggendo pixel a passo regolare dichiarato,
  poi l'alta risoluzione solo per la porzione visibile quando lo zoom lo
  permette. La bassa risoluzione è **solo di presentazione**: ogni misura usa
  i pixel originali. Soglie tra le strategie: A10 (Gruppo 3). Il modulo
  espone la memoria usata (mostrata da `40-ui-finestra-principale.md`).
- **Immagini a colori RGB e differenza di colori (B11, sez. 5.15):** immagine
  a colori da **2 o 3** immagini monocrome. Le immagini si ricampionano
  sull'immagine di riferimento (per default quella con il pixel angolare più
  piccolo) con il metodo del pixel più vicino (`reproject`, D11-2); se le
  lunghezze d'onda sono note, si ordinano per lunghezza d'onda. Con 2 immagini
  la terza componente è la media delle altre due. **Differenza** (`RGBdiff`):
  le differenze positive vanno nella prima componente, quelle negative nella
  seconda, normalizzate su 0–255. Il risultato è un **nuovo piano di sola
  presentazione**: nessun valore fisico viene mescolato.
- **Mosaico e sequenza animata (B11, sez. 5.16):** mosaico nella griglia
  dell'immagine di riferimento con **media** nelle zone sovrapposte e senza
  correzione del fondo (come Aladin, dichiarato nel risultato); cubo come
  sequenza animata (scorrimento nel 41, analisi nel 23).
- **Convenzione dei pixel e costanti (H25, H4):** coordinate pixel interne in
  convenzione numpy, conversione FITS solo con `convert_pixel_convention` del
  modulo 10 (DC7); `BZERO`, `BSCALE`, `BLANK` e unità dei pixel sono esposti a
  `18-core-calcolatrici.md` per la calcolatrice dei pixel.

## 4. Cosa NON fa

- Non converte i pixel in misure fotometriche: spetta a `20-analisi-fotometria.md`.
- Non gestisce i cubi: quelli vanno a `23-analisi-cubi-di-dati.md`.
- Non scarica i cataloghi né esegue query (14), non fa cross-match (15).
- Non decide quale survey mostrare: l'elenco HiPS è di `12-core-hips.md`.
- Non disegna: la UI applica le regolazioni ricevute (`41-ui-visualizzatore-cielo.md`).
- Non modifica i valori originali dei pixel quando regola la visualizzazione.

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `04-cache.md` (cache comune A7),
  `10-core-coordinate-wcs.md` (WCS, tagli coerenti).
- **Usato da:** `17-core-misure.md`, `18-core-calcolatrici.md`,
  `19-core-dati-planetari.md`, `20-analisi-fotometria.md`,
  `23-analisi-cubi-di-dati.md`, `41-ui-visualizzatore-cielo.md`,
  `43-ui-pannello-analisi.md`.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `path` / `url` | stringa | percorso file o URL | FITS, JPEG, PNG |
| in | immagine FITS | array + header | pixel (unità da header, es. MJy/sr o ADU) | + WCS |
| in | taglio | float64 | gradi (centro) + lato in gradi o in pixel | output: nuovo FITS |
| in | parametri di display | float64 | vmin, vmax, gamma, palette | solo presentazione |
| in | immagini da combinarre | array | stesse unità o con fattore di scala dichiarato | operazioni H5 |
| out | immagine in memoria | array nel **tipo nativo del file** (float32 o float64); display in float32 | pixel | con WCS; ogni calcolo in float64 (D11-1) |
| out | cutout | FITS con WCS | pixel + header | |
| out | contorni | list di curve | pixel o coordinate (dichiarare) | H7 |
| out | cache su disco | file immagine + metadati | origine, data di scaricamento, dimensione | A7, limite di default 5 GB |
| in | immagini RGB | 2 o 3 `FitsImage` monocromi | stesse dimensioni non richieste (si ricampiona) | modalità `rgb` o `rgb_diff` |
| out | immagine RGB | array 3 × 8 bit + WCS dell'immagine di riferimento | 0–255 per componente | solo presentazione; origine delle componenti dichiarata |
| out | vista a bassa risoluzione | array + passo di lettura | pixel | marcata `preview`, mai usata per le misure |
| out | costanti dei pixel | `BZERO`, `BSCALE`, `BLANK`, `BUNIT` | come da intestazione FITS | per il modulo 18 |

## 7. Interfaccia pubblica

- **`FitsImage`** (classe): rappresenta un'immagine con array, header, WCS,
  unità; metodi descrittivi per leggere header, chiedere il campo di vista,
  produrre un taglio, produrre una copia con operazione (H5).
- **`load_image(source)`** — carica da file, URL o formato non FITS; restituisce
  `FitsImage` o errore; dichiara origine e data.
- **`set_display(image, vmin, vmax, gamma, palette)`** — calcola i parametri di
  visualizzazione (non modifica l'originale).
- **`resample_to_reference(image, reference)`** — ricampiona su una soluzione
  astrometrica di riferimento (B7); restituisce nuova immagine + qualità.
- **`reproject(...)`** / **`blend(...)`** — composizioni multibanda (B11) e
  sovrapposizioni con alpha (B5).
- **`cutout(image, center, size)`** — taglio con WCS coerente.
- **`image_operation(a, b, op)`** — aritmetica/convoluzione/normalizzazione/
  specchiatura (H5); `op` da un elenco chiuso.
- **`contours(image, levels)`** — isofote (H7); `levels` in unità dell'immagine.
- **`star_centroid(image, position, box_size, annulus_inner, annulus_outer)`**
  — baricentro pesato sull'intensità, dopo la sottrazione del fondo (D11-7),
  nella finestra quadrata di lato `box_size` pixel (intero dispari ≥ 3)
  centrata sul pixel più vicino a `position` (convenzione numpy); il fondo è
  la mediana con sigma clipping dei pixel a distanza da `position` in
  [`annulus_inner`, `annulus_outer`) pixel; `image` è un array 2-D o un
  oggetto con l'attributo `data` (`FitsImage`). Restituisce la posizione in
  convenzione numpy, dichiarata, con la finestra, il fondo, la sua
  deviazione standard, il numero di pixel della corona e i parametri del
  sigma clipping; le posizioni vanno al modulo 10 per
  `astrometric_calibration`.
- **Cache:** nessuna classe propria (CA4 di `04-cache.md`): immagini e tagli
  scaricati si salvano con `SharedCache`, che espone origine, data e
  dimensione di ogni voce.
- **`detect_format(source)`** — riconosce la natura del file dal contenuto
  (FITS, FITS compresso, JPEG, PNG, GIF); restituisce il formato o
  `FORMAT_UNSUPPORTED`.
- **`open_large_image(source)`** — apre un'immagine scegliendo la strategia
  per dimensione (H27); restituisce un `FitsImage` con vista a bassa
  risoluzione marcata e accesso all'alta risoluzione per regione.
- **`rgb_composite(images, reference, mode)`** — immagine a colori da 2 o 3
  immagini (`mode` = `rgb` o `rgb_diff`), con ricampionamento sul
  riferimento; restituisce un nuovo piano di presentazione.
- **`mosaic(images, reference)`** — mosaico con media nelle sovrapposizioni.
- **`pixel_scaling(image)`** — restituisce `BZERO`, `BSCALE`, `BLANK` e unità
  dei pixel (per il modulo 18).

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `astropy.io.fits` | lettura/scrittura FITS | standard di fatto |
| `astropy.wcs` (via modulo 10) | WCS dei tagli | coerente con il nucleo |
| `numpy` | manipolazione array | base dell'ecosistema scientifico |
| `scipy.ndimage` | convoluzione, ricampionamento semplice, baricentro del centroide (`center_of_mass`) | consolidato e testato |
| `astropy.stats` | fondo cielo del centroide con `sigma_clipped_stats` (D11-7) | libreria di riferimento |
| `reproject` (D11-2, decisa; licenza da verificare prima del codice) | ricampionamento tra proiezioni (B7) | pensato per questo scopo; vedi §13 |
| Standard FITS | formato di tagli ed export | formato del dominio |
| `Pillow` (D11-6) | lettura di JPEG, PNG e GIF e del segmento di commento con la calibrazione | libreria di riferimento per questi formati; **licenza da verificare prima del codice** |

## 9. Regole e vincoli

- **Separazione display/dati:** le regolazioni di visualizzazione non cambiano
  mai i valori usati per misure o esportazioni.
- Precisione (D11-1, decisa il 2026-10-04; regola in `02-convenzioni.md`
  DC6): **in memoria il tipo nativo del file** (float32 o float64 come da
  sorgente); **ogni calcolo in `float64`**; **`float32` solo per la
  visualizzazione**; nelle misure `float64` obbligatorio.
- Ogni immagine da rete/cache porta con sé origine e data di scaricamento
  (vincolo A7) — mostrabili e registrabili per la riproducibilità.
- Le operazioni H5 sono pure: input → nuovo output, nessuna modifica in posto.
- Timeout dichiarato per ogni accesso di rete; offline ⇒ errore chiaro.
- Cache su disco con **limite di default 5 GB, configurabile** dall'utente e
  rimozione dei dati meno usati (D11-3); nessun dato è servito dalla cache
  senza che origine e data siano note.
- Le immagini caricate devono risultare con WCS o senza WCS dichiarato: non si
  indovina.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| File FITS assente o corrotto | nessun'immagine aperta, errore con percorso | `FITS_UNREADABLE` |
| Header senza WCS | l'immagine si apre come griglia di pixel con avviso | `WCS_MISSING` |
| URL non raggiungibile / timeout | errore di rete, nessun dato parziale mostrato come valido | `NET_TIMEOUT` |
| Formato non supportato | elenco dei formati supportati | `FORMAT_UNSUPPORTED` |
| Taglio fuori dall'immagine | errore o ritaglio intersezionale dichiarato | `CUTOUT_OUT_OF_RANGE` |
| Operazione tra immagini di dimensioni/unità diverse | rifiuto con descrizione del conflitto | `IMAGE_SHAPE_MISMATCH` / `UNIT_MISMATCH` |
| Cache piena oltre il limite | eliminazione dei dati meno usati (dichiarata in log) o errore se il limite non consente | `CACHE_FULL` |
| Valori non finiti nei pixel (NaN) | gestiti nel display senza propagarli alle misure | avviso `NONFINITE_PIXELS` |
| Compressione FITS non supportata dalla libreria | nessuna immagine aperta, errore con il tipo di compressione | `COMPRESSION_UNSUPPORTED` |
| RGB con meno di 2 o più di 3 immagini, o immagini non monocrome | rifiuto con il numero e il tipo ricevuti | `RGB_INPUT_INVALID` |
| RGB o mosaico con un'immagine senza WCS | rifiuto: il ricampionamento richiede la calibrazione | `WCS_MISSING` |
| Misura richiesta su una vista a bassa risoluzione | la misura usa i pixel originali; se non disponibili, errore | `PREVIEW_NOT_MEASURABLE` |
| Finestra o corona del centroide fuori dall'immagine | rifiuto con la finestra e i limiti dell'immagine | `CENTROID_OUT_OF_IMAGE` |
| Centroide non definito (somma dei pesi ≤ 0 dopo la sottrazione del fondo, pixel non finiti nella finestra, nessun pixel finito nella corona) | nessuna posizione prodotta | `CENTROID_UNDEFINED` |

## 11. Esposizione all'IA

- **`load_image_info`** — input: percorso/URL; output: dimensioni, unità,
  WCS, campo di vista, origine e data. Nessun calcolo numerico nuovo.
- **`get_image_statistics`** — input: immagine (+eventuale regione); output:
  min, max, media, deviazione standard. **Calcolo: `numpy`/`astropy.stats`**,
  mai l'IA.
- **`image_operation`** (H5) — input: due immagini/parametri, operazione da
  elenco chiuso; output: nuova immagine. **Calcolo: `numpy`/`scipy`.**
- **`cutout`** — input: immagine + centro/lato; output: FITS con WCS.

L'IA può scegliere i parametri e spiegare il risultato; non produce mai il
numero mostrato.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Apertura FITS | aprire un FITS di prova con WCS | header, WCS e dimensioni letti correttamente | confronto con `astropy.io.fits` letto dal test |
| T2 | Il display non altera i dati | applicare vmin/vmax/gamma/palette, poi rileggere l'array | array identico byte per byte a prima dell'operazione | confronto diretto nel test |
| T3 | Cutout con WCS | tagliare un rettangolo e convertire i suoi angoli in coordinate | le coordinate dei angoli coincidono con quelle dell'originale ricalcolate con `astropy.wcs` (errore < 1e-6 pixel) | ricalcolo con Astropy |
| T4 | Operazione aritmetica | sommare due immagini di prova con valori noti (es. tutte 1.0 e tutte 2.0) | risultato tutto 3.0; nessuna modifica degli input | confronto con `numpy` |
| T5 | Convoluzione | convolvere con un kernel normalizzato noto (es. media 3×3 su un gradiente lineare) | risultato coincidente con `scipy.ndimage.convolve` ricalcolato nel test | ricalcolo con SciPy |
| T6 | Cache con provenienza | scaricare un riquadro, servirlo dalla cache | elenco cache con origine e data di scaricamento valorizzate | lettura dei metadati della cache |
| T7 | Timeout di rete | richiedere un URL irraggiungibile | errore `NET_TIMEOUT` entro il timeout dichiarato, nessun dato fasullo | test di unità con server simulato |
| T8 | Riconoscimento dal contenuto (H22) | aprire un FITS rinominato `.png` e un PNG rinominato `.fits` | formato riconosciuto correttamente in entrambi i casi | test di unità |
| T9 | FITS compresso HCOMPRESS (H22) | comprimere un'immagine di prova con HCOMPRESS tramite `astropy.io.fits` e riaprirla | valori dei pixel uguali a quelli restituiti da `astropy.io.fits` sulla stessa HDU | confronto con `astropy.io.fits` |
| T10 | GIF (H22) | aprire una GIF di prova | immagine aperta con dimensioni e valori uguali a quelli letti con `Pillow` | confronto con la libreria scelta |
| T11 | Due livelli di risoluzione (H27) | aprire un FITS sintetico di dimensione superiore alla soglia (A10) | vista a bassa risoluzione marcata `preview`; misura su un pixel = valore del pixel originale | confronto con `astropy.io.fits` in `memmap` |
| T12 | RGB con 3 immagini (B11) | tre immagini sintetiche con WCS diverse | componenti ricampionate sul riferimento con il pixel più piccolo; valori uguali a `reproject` (pixel più vicino) | ricalcolo con `reproject` |
| T13 | RGB con 2 immagini (B11) | due immagini sintetiche | terza componente = media delle due | ricalcolo con `numpy` |
| T14 | Differenza di colori (B11) | due immagini con differenze note di segno opposto | positivi nella prima componente, negativi nella seconda, normalizzati 0–255 | ricalcolo con `numpy` |
| T15 | Costanti per il 18 (H4) | `pixel_scaling` su un FITS con `BZERO` = 32768, `BSCALE` = 1 | valori dell'intestazione restituiti senza modifiche | test di unità |
| T16 | Centroide (H6, D10-8, D11-7) | stella gaussiana sintetica con centro non intero noto su fondo costante con rumore | posizione uguale a `scipy.ndimage.center_of_mass` sulla finestra meno la mediana di `sigma_clipped_stats` sulla corona, ricalcolati nel test; vicina al centro vero; fondo uguale alla mediana ricalcolata | ricalcolo con SciPy e `astropy.stats` |
| T17 | Centroide fuori immagine | finestra o corona che esce dal bordo | `CENTROID_OUT_OF_IMAGE` | test di unità |
| T18 | Centroide non definito | finestra con un NaN; finestra senza stella (tutta fondo) con pesi a somma ≤ 0 | `CENTROID_UNDEFINED` | test di unità |
| T19 | Fondo robusto | stella vicina dentro la corona | fondo stimato entro 3 deviazioni standard dal fondo vero (sigma clipping la esclude) | confronto con il fondo costante del test |

## 13. Decisioni aperte

- **D11-1 — Precisione dei pixel: DECISA il 2026-10-04.** **Tipo nativo del
  file in memoria** (float32 o float64 come da sorgente); **ogni calcolo in
  `float64`**; **`float32` solo per la visualizzazione**. **Motivazione:**
  nessuna conversione inutile all'ingresso, precisione piena dov'è richiesta
  (calcoli e misure) e risparmio di memoria nel solo display. Regola scritta
  in `02-convenzioni.md` DC6; applicata in §6/§9 qui sopra.
- **D11-2 — Libreria di ricampionamento (B7): DECISA il 2026-10-09 (decisione
  del proprietario sulla checklist del livello 1).** **`reproject`**
  (pacchetto affiliato ad Astropy): metodi pixel più vicino e bilineare come
  Aladin, più un metodo che conserva il flusso (Aladin non lo garantisce, sez.
  5.17). **Da verificare prima del codice:** licenza e installazione su macOS.
- **D11-3 — Cache su disco: DECISA il 2026-10-04 (parte valori).** Limite di
  default **5 GB**, **configurabile** dall'utente, con **eliminazione dei
  dati meno usati** (estensione di A7). **Motivazione:** A7 richiede un limite
  configurabile con rimozione dei dati meno usati; un limite in GB è
  prevedibile e testabile (T4 di `12-core-hips.md`). Applicata in §3/§6/§9 qui
  sopra; l'interfaccia di configurazione resta in `40-ui-finestra-principale.md`
  e `60-distribuzione-dmg.md`.
- **D11-4 — HDU multiple: DECISA il 2026-10-09 (decisione del proprietario
  sulla checklist del livello 1).** si aprono **tutte le HDU immagine** del
  file, con scelta dell'utente (file a più estensioni MEF, come in Aladin,
  sez. 8.1); i cubi restano a `23-analisi-cubi-di-dati.md`.
- **D11-5 — Palette predefinite (B6): DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** le **9 tabelle di colori di
  Aladin** (sez. 5.5): Gray, BB, A, Stern, Rainbow, Eosb, Fire, Cubhlx, Polar,
  anche invertite; **default Gray**.
- **D11-6 — Libreria per JPEG, PNG e GIF: DECISA il 2026-10-09 (decisione del
  proprietario).** **`Pillow`** per JPEG, PNG e GIF e per il segmento di
  commento con la calibrazione (H6). **Da verificare prima del codice:**
  licenza e installazione su macOS.
- **D11-7 — Fondo cielo nel centroide: DECISA il 2026-10-09 (decisione del
  proprietario).** Mediana in una corona attorno alla stella con sigma
  clipping (`astropy.stats.sigma_clipped_stats`); applicata in §3, §7, §8,
  §10, §12.
- **D11-8 — Valori di default dei raggi della corona del centroide:** oggi
  `annulus_inner` e `annulus_outer` sono parametri obbligatori. Da decidere
  (Gruppo 3) **insieme a `20-analisi-fotometria.md` e
  `41-ui-visualizzatore-cielo.md`** (decisione del proprietario del
  2026-10-09).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario: D11-1 e D11-3 passate da aperte a decise.** D11-1: tipo nativo del file in memoria, ogni calcolo in `float64`, `float32` solo per il display (§6/§9; regola in `02-convenzioni.md` DC6). D11-3: cache su disco con limite di default **5 GB**, configurabile, eliminazione dei dati meno usati (§3/§6/§9; interfaccia in `40`/`60`). Decisioni riportate in `decisioni-aperte.md`. |
| 2026-10-08 | Claude Code | §5: aggiunti a "Usato da" i moduli `18-core-calcolatrici.md` e `19-core-dati-planetari.md` (scritti il 2026-10-08, stato bozza). Nessun altro testo cambia. |
| 2026-10-09 | Claude Code | **D11-2, D11-4, D11-5 DECISE** (checklist del livello 1): `reproject` per il ricampionamento (licenza da verificare prima del codice); tutte le HDU immagine con scelta dell'utente; le 9 tabelle di colori di Aladin con default Gray. §8 aggiornato. |
| 2026-10-09 | Claude Code | **Completamento con gli esiti di AP5** (decisione del proprietario del 2026-10-09): §3, §6, §7, §10, §12 per H22 (formati e compressioni, compreso GIF e HCOMPRESS; riconoscimento dal contenuto), H27 (immagini di qualsiasi dimensione a due livelli di risoluzione), B11 (RGB, differenza di colori, mosaico), H25/H4 (convenzione dei pixel e costanti per il 18). Nuova decisione aperta **D11-6** (libreria per JPEG, PNG e GIF, Gruppo 2): il modulo resta in `bozza`. |
| 2026-10-09 | Claude Code | **D11-6 DECISA** (decisione del proprietario): `Pillow` (licenza da verificare prima del codice). §3, §8, §12, §13 aggiornati. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** (regola del proprietario del 2026-10-09): nessuna decisione aperta nei Gruppi 1 e 2. |
| 2026-10-09 | Claude Code | **Decisione del proprietario D10-8 (modulo 10) applicata** (autorizzazione esplicita a modificare il file approvato): nuovo centroide baricentrico per la calibrazione astrometrica (§3, §7 `star_centroid`, §10 `CENTROID_OUT_OF_IMAGE`/`CENTROID_UNDEFINED`, §12 T16–T17), nuova D11-7 (fondo cielo, Gruppo 3); cache collegata a `04-cache.md` (§3, §5). Stato `approvato` invariato. |
| 2026-10-09 | Claude Code | **Collegamento alla cache comune `04-cache.md`** (approvato il 2026-10-09; decisione CA4 del proprietario, autorizzazione esplicita a modificare il file approvato): §3, §5 e §7 — tolta `ImageCache`, immagini e tagli nella cache comune `SharedCache`; tolta da §5 la dipendenza da `12` per la cache. Stato `approvato` invariato. |
| 2026-10-09 | Claude Code | **D11-7 DECISA** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): fondo cielo del centroide = mediana con sigma clipping in una corona attorno alla stella; `star_centroid` con raggi della corona obbligatori (§3, §7), `astropy.stats` (§8), casi limite (§10), test T16–T19 (§12). Codice di `star_centroid` scritto in `src/astrotwo/core/images_fits.py` (solo questa funzione). Stato `approvato` invariato. |
| 2026-10-09 | Claude Code | Centroide **confermato** dal proprietario (D11-7 e parametri); nuova **D11-8** (valori di default dei raggi della corona, Gruppo 3, da fissare con 20 e 41). Stato `approvato` invariato. |
