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
  - **HDU immagine (decisione del proprietario del 2026-10-10):** è
    un'immagine una HDU con **esattamente 2 assi di lunghezza > 1**; gli assi
    di lunghezza 1 (frequenti nelle immagini radio a 4 assi) si tolgono dai
    dati e dal WCS, dichiarandolo nel risultato. Una HDU con 3 o più assi
    utili è un cubo: errore `CUBE_NOT_SUPPORTED`, che rimanda a
    `23-analisi-cubi-di-dati.md` (il caso FITS RGB è in P2).
  - **Più HDU immagine (D11-4, precisata il 2026-10-10):** `load_image`
    apre la HDU indicata dal parametro `hdu`; se il file ha una sola HDU
    immagine la apre anche senza parametro; se ne ha più di una e `hdu` non è
    indicata, errore `HDU_CHOICE_REQUIRED` con l'elenco delle HDU (indice,
    nome, dimensioni), che l'interfaccia mostra per la scelta
    dell'utente; lo stesso elenco lo dà `list_image_hdus`.
  - **Provenienza dei file locali:** origine = percorso assoluto del file,
    data = momento della lettura (UTC), più la data di modifica del file.
  - **Costanti dei pixel:** `BZERO`, `BSCALE`, `BLANK` e `BUNIT` si leggono
    dall'intestazione originale prima che `astropy.io.fits` applichi la
    scala; i dati in memoria sono i valori fisici nel tipo prodotto da
    `astropy.io.fits`, portati all'ordine di byte della macchina (FITS è
    big-endian; tipo e valori non cambiano).
- **Lettura da rete:** aprire immagini da URL (B2) e immagini in formati non
  FITS come JPEG/PNG (B9), con timeout e gestione degli errori espliciti.
  **Politica (decisione del proprietario del 2026-10-10, come
  `resolve_name` del 10): prima la cache** — se l'URL è nella cache comune
  di `04-cache.md`, si usa la copia, dichiarata tale con origine (l'URL) e
  data del download, senza rete; `refresh=True` riscarica; se la rete non
  risponde si usa la copia in cache se c'è (dichiarandolo), altrimenti
  `NET_TIMEOUT`. Download con i timeout comuni (10 s connessione, 60 s
  lettura); un download interrotto o con errore HTTP non lascia nulla in
  cache né dati parziali. Per gli URL non si cerca il file `.hhh`.
- **Scala di visualizzazione:** regolare luminosità e contrasto (B3),
  istogramma / CTF (B4), palette colori per immagini monocrome (B6),
  trasparenza e sovrapposizione tra layer di immagine (B5), coniugazione /
  composizione multibanda (B11). Le regolazioni sono **solo di presentazione**:
  i pixel memorizzati e i valori usati per le misure non cambiano.
  - **Funzioni di trasferimento (decisione del proprietario del
    2026-10-10):** quelle di `astropy.visualization` — lineare
    (`LinearStretch`), logaritmica (`LogStretch`), radice quadrata
    (`SqrtStretch`), quadrato (`SquaredStretch`), arcoseno iperbolico
    (`AsinhStretch`) ed equalizzazione dell'istogramma (`HistEqStretch`);
    l'intervallo di visualizzazione è dato da `vmin`/`vmax`.
  - **Palette (D11-5, corretta il 2026-10-10):** non si riproducono le
    palette di Aladin (regola d'oro n. 8). Si offrono palette scientifiche
    da fonti con licenza libera, equivalenti per uso a quelle di Aladin, con
    **default `gray`**, ciascuna anche invertita (`_r`). Elenco e fonte (tutte
    distribuite con `matplotlib`): `gray` (scala di grigi); `viridis`,
    `plasma`, `inferno`, `magma` (van der Walt e Smith, CC0); `cividis`
    (Nuñez, Anderton e Renslow 2018, adatta ai daltonici); `cubehelix`
    (Green 2011); `afmhot` (colori del corpo nero); `coolwarm` (Moreland
    2009, divergente). Licenze **da verificare prima del codice di P4**.
- **Taglio (cutout):** estrarre una sottoparte di un'immagine con WCS coerente
  (B8).
- **Ricampionamento e allineamento:** ricampionare un'immagine sulla soluzione
  astrometrica di un'altra e fare il "match" delle viste (B7). Non esiste
  "align" in Aladin: la funzione è il ricampionamento sulla soluzione
  astrometrica. **Qualità** del ricampionamento (decisione del proprietario
  del 2026-10-10): la **mappa di copertura** restituita da `reproject` e la
  **percentuale di pixel coperti** dell'immagine di riferimento.
- **Operazioni su immagini (H5) — elenco chiuso (decisione del proprietario
  del 2026-10-10, funzioni scelte in base al manuale di Aladin, sez. 5.18):**
  (1) **aritmetica tra immagini** — somma, differenza, prodotto, rapporto,
  pixel per pixel, tra immagini con la stessa griglia; (2) **aritmetica con
  costanti** — le stesse quattro operazioni con un numero; (3)
  **convoluzione** con un kernel di `astropy.convolution` (oggetto
  `Kernel2D`, es. `Gaussian2DKernel`, `Box2DKernel`, `Tophat2DKernel`),
  calcolata con `astropy.convolution.convolve`; (4) **normalizzazione** —
  definizione esatta **da verificare con il manuale (sez. 5.18) prima del
  codice di P5**; (5) **specchiature** orizzontale e verticale, che
  **aggiornano anche il WCS** (il cielo resta agganciato agli stessi pixel
  fisici). Ogni operazione produce un **nuovo** oggetto, calcolato in
  `float64`, mai la modifica silenziosa dell'originale. Il passaggio a
  `float32` per il display non è un'operazione H5: è di `set_display`.
- **Contorni / isofote (H7):** calcolare le linee di livello di intensità
  sull'immagine con **`contourpy`** (decisione del proprietario del
  2026-10-10; licenza da verificare prima del codice di P5); le linee sono
  in coordinate pixel (convenzione numpy), con la conversione in coordinate
  celesti tramite il modulo 10 su richiesta.
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
- **Esportazione:** salvare tagli e immagini come FITS con WCS e
  provenienza (`save_fits`). L'esportazione **della vista** come immagine è
  del `41-ui-visualizzatore-cielo.md` (decisione del proprietario del
  2026-10-10).
- **Formati e compressioni (H22, sez. 8.1 del manuale di Aladin, ed. giugno 2022):**
  FITS anche compressi (RICE, GZIP, **HCOMPRESS / HCOMP**, letti con le HDU
  compresse di `astropy.io.fits`; file `.gz`), file a più estensioni (MEF,
  D11-4), FITS RGB (tre piani di colore), JPEG, PNG e **GIF**. Per JPEG e PNG
  la calibrazione si legge dal segmento di commento o da un file `.hhh` con
  lo stesso nome (H6, sez. 5.14): **solo in lettura, per compatibilità con i
  file esistenti** (decisione del proprietario del 2026-10-10; regola d'oro
  n. 8, eccezione della lettura di file prodotti da Aladin). Il formato si
  descrive qui a partire da standard pubblici (intestazione FITS scritta come
  testo) **prima del codice di P2**; se non è documentato in modo pubblico,
  P2 si ferma. I file di prova si generano nei test con `Pillow`.
  - **Formato letto (decisione del proprietario del 2026-10-10, solo
    standard pubblici).** La documentazione pubblica di Aladin (pagina man,
    comando `-mocgen`) dice solo "WCS header in the comment segment" per
    JPEG/PNG e ".hhh = FITS header files without pixels"; non c'è una
    specifica formale. Il lettore usa quindi soltanto standard pubblici:
    **JPEG** = segmento di commento `COM` (standard JPEG, ISO/IEC 10918-1);
    **PNG** = blocco di testo (`tEXt`, `zTXt` o `iTXt`) con la parola chiave
    predefinita **`Comment`** (standard PNG, ISO/IEC 15948); **`.hhh`** = file
    con lo stesso nome dell'immagine ed estensione `.hhh`, contenente
    un'intestazione FITS come testo (standard FITS 4.0). In tutti i casi il
    testo si accetta come schede FITS da 80 caratteri attaccate oppure
    separate da a capo (`astropy.io.fits.Header.fromstring`). Se c'è il
    commento nel file, vale quello e il `.hhh` si ignora (dichiarato); se il
    testo non è un'intestazione FITS valida con WCS celeste, o i suoi
    `NAXIS1`/`NAXIS2` non sono le dimensioni dell'immagine, l'immagine si
    apre senza WCS con avviso `WCS_MISSING`.
  - **Orientamento dei pixel:** JPEG, PNG e GIF memorizzano le righe
    dall'alto verso il basso, il FITS dal basso verso l'alto. In memoria le
    righe si mettono **dal basso verso l'alto** (la riga 0 dell'array è
    l'ultima del file), così l'immagine ha la stessa disposizione di un FITS
    e il WCS letto dal commento vale con la convenzione dei pixel FITS
    (DC7). Coincidenza con il comportamento di Aladin **da verificare con
    AP1**.
  - **Modi di colore (`Pillow`):** grigi a 8, 16 o 32 bit e float → immagine
    monocroma 2-D con i valori del file; bianco e nero (`1`) → 0/1 in 8
    bit; tavolozza (`P`, tipica delle GIF) → grigi se la tavolozza è tutta
    grigia, altrimenti RGB, con la conversione di `Pillow`; RGB → immagine a
    colori; il canale alfa (`RGBA`, `LA`) si scarta, dichiarandolo; CMYK e
    altri → RGB con la conversione di `Pillow`. GIF animate: si legge il
    primo fotogramma, con il numero di fotogrammi nel risultato.
- **Immagini a colori (JPEG/PNG/GIF a colori e FITS RGB):** si tengono come
  array `3 × righe × colonne` (piani R, G, B) marcati `color`, **solo di
  presentazione**: misure, centroide e operazioni H5 richiedono un'immagine
  monocroma. Un **FITS RGB** è una HDU con 3 piani letta **solo su richiesta
  esplicita** (`load_image(..., rgb=True)`, decisione del proprietario del
  2026-10-10): senza la richiesta resta un cubo (`CUBE_NOT_SUPPORTED`);
  nessuna convenzione si indovina. La **natura del file si riconosce dal
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
  i pixel originali. **Soglie (A10 per le immagini, decisa dal proprietario
  il 2026-10-10):** in memoria fino a **1 GB** di dati; oltre, `memmap` per i
  file non compressi; **due livelli** oltre **4 GB**, oppure per i file
  compressi oltre **1 GB** (la decompressione impedisce il `memmap`);
  anteprima di **al massimo 4096 pixel sul lato lungo** (passo di lettura
  intero, il più piccolo che rispetta il limite). Valori configurabili e
  scritti nel risultato (1 GB = 10⁹ byte, come in `04-cache.md`). Il modulo
  espone la memoria usata (mostrata da `40-ui-finestra-principale.md`).
- **Immagini a colori RGB e differenza di colori (B11, sez. 5.15):** immagine
  a colori da **2 o 3** immagini monocrome. Le immagini si ricampionano
  sull'immagine di riferimento (per default quella con il pixel angolare più
  piccolo) con il metodo del pixel più vicino (`reproject`, D11-2); se le
  lunghezze d'onda sono note, si ordinano per lunghezza d'onda. Con 2 immagini
  la terza componente è la media delle altre due. **Differenza** (`RGBdiff`):
  le differenze positive vanno nella prima componente, quelle negative nella
  seconda, normalizzate su 0–255 con **un solo fattore di scala per le due
  componenti**, scritto nel risultato (decisione del proprietario del
  2026-10-10). Il risultato è un **nuovo piano di sola
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
| out | contorni | list di curve | pixel (convenzione numpy) o coordinate celesti (dichiarato) | H7, `contourpy` |
| in | funzione di trasferimento, palette | enumerativi | elenchi chiusi di §3 | solo presentazione |
| in | operazione H5 | enumerativo + operandi | elenco chiuso di §3 | kernel come oggetto `astropy.convolution.Kernel2D` |
| out | qualità del ricampionamento | mappa + percentuale | copertura 0–1 per pixel, % di pixel coperti | da `reproject` |
| out | cache su disco | file immagine + metadati | origine, data di scaricamento, dimensione | A7, limite di default 5 GB |
| in | immagini RGB | 2 o 3 `FitsImage` monocromi | stesse dimensioni non richieste (si ricampiona) | modalità `rgb` o `rgb_diff` |
| out | immagine RGB | array 3 × 8 bit + WCS dell'immagine di riferimento | 0–255 per componente | solo presentazione; origine delle componenti dichiarata; per `rgb_diff` il fattore di scala unico |
| out | vista a bassa risoluzione | array + passo di lettura | pixel | marcata `preview`, mai usata per le misure; strategia e soglie (A10) scritte nel risultato |
| out | costanti dei pixel | `BZERO`, `BSCALE`, `BLANK`, `BUNIT` | come da intestazione FITS | per il modulo 18 |

## 7. Interfaccia pubblica

- **`FitsImage`** (classe): rappresenta un'immagine con array, header, WCS,
  unità; metodi descrittivi per leggere header, chiedere il campo di vista,
  produrre un taglio, produrre una copia con operazione (H5).
- **`load_image(source, hdu=None, rgb=False, cache=None, refresh=False,
  timeouts=NETWORK_TIMEOUTS)`** — carica da file, URL o formato non FITS;
  restituisce `FitsImage` o errore; dichiara origine e data (per gli URL
  anche se la copia viene dalla cache); con più HDU immagine serve `hdu` (indice o nome), altrimenti
  `HDU_CHOICE_REQUIRED`; `rgb=True` legge una HDU di 3 piani come FITS RGB;
  per JPEG/PNG legge la calibrazione dal commento o dal `.hhh`.
- **`list_image_hdus(source)`** — elenco delle HDU immagine del file
  (indice, nome, dimensioni, compressione), per la scelta dell'utente.
- **`set_display(image, vmin, vmax, gamma, palette)`** — calcola i parametri di
  visualizzazione (non modifica l'originale): funzione di trasferimento e
  palette dagli elenchi chiusi di §3; restituisce il piano di presentazione
  (`float32`, poi colori) senza toccare l'array dell'immagine.
- **`resample_to_reference(image, reference)`** — ricampiona su una soluzione
  astrometrica di riferimento (B7); restituisce nuova immagine + qualità
  (mappa di copertura di `reproject` + percentuale di pixel coperti).
- **`reproject(...)`** / **`blend(...)`** — composizioni multibanda (B11) e
  sovrapposizioni con alpha (B5).
- **`cutout(image, center, size)`** — taglio con WCS coerente.
- **`image_operation(a, b, op)`** — aritmetica/convoluzione/normalizzazione/
  specchiatura (H5); `op` dall'elenco chiuso di §3; `b` è un'immagine, una
  costante o un kernel secondo l'operazione; le specchiature aggiornano il
  WCS.
- **`save_fits(image, path)`** — salva un'immagine o un taglio come FITS con
  WCS e provenienza (origine, data) nell'intestazione.
- **`contours(image, levels)`** — isofote (H7) con `contourpy`; `levels` in
  unità dell'immagine; restituisce le curve in pixel (convenzione numpy).
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
| `reproject` (D11-2, decisa; licenza da verificare prima del codice) | ricampionamento tra proiezioni (B7), mappa di copertura, mosaico (`reproject_and_coadd`) | pensato per questo scopo; vedi §13 |
| `astropy.visualization` | funzioni di trasferimento e intervalli (B3, B4) | libreria di riferimento |
| `astropy.convolution` | kernel e convoluzione (H5) | libreria di riferimento, gestisce i NaN |
| `contourpy` (licenza da verificare prima del codice di P5) | contorni / isofote (H7) | libreria usata da `matplotlib` |
| `matplotlib` (solo le tabelle delle palette; licenza da verificare prima del codice di P4) | palette di §3 (B6) | fonte con licenza libera delle palette scientifiche |
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
| Più HDU immagine e `hdu` non indicata | nessuna immagine aperta; errore con l'elenco delle HDU per la scelta | `HDU_CHOICE_REQUIRED` |
| HDU indicata inesistente o non immagine | rifiuto con l'elenco delle HDU immagine | `HDU_NOT_IMAGE` |
| HDU con 3 o più assi di lunghezza > 1 | rifiuto: i cubi sono del `23` | `CUBE_NOT_SUPPORTED` |
| Compressione FITS non supportata dalla libreria | nessuna immagine aperta, errore con il tipo di compressione | `COMPRESSION_UNSUPPORTED` |
| RGB con meno di 2 o più di 3 immagini, o immagini non monocrome; `rgb=True` su una HDU che non ha 3 piani | rifiuto con il numero e il tipo ricevuti | `RGB_INPUT_INVALID` |
| Immagine JPEG/PNG/GIF non decodificabile | nessuna immagine aperta, errore con il percorso | `IMAGE_UNREADABLE` |
| RGB o mosaico con un'immagine senza WCS | rifiuto: il ricampionamento richiede la calibrazione | `WCS_MISSING` |
| Misura richiesta su una vista a bassa risoluzione | la misura usa i pixel originali; se non disponibili, errore | `PREVIEW_NOT_MEASURABLE` |
| Operazione H5 fuori dall'elenco chiuso o operando del tipo sbagliato | rifiuto con l'elenco delle operazioni | `OPERATION_UNSUPPORTED` |
| Funzione di trasferimento o palette fuori dagli elenchi di §3 | rifiuto con l'elenco ammesso | `DISPLAY_OPTION_UNKNOWN` |
| Calibrazione nel commento di JPEG/PNG o nel `.hhh` non leggibile | l'immagine si apre senza WCS, con avviso che cita la calibrazione scartata | `WCS_MISSING` |
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
| T20 | Specchiature e WCS (H5) | specchiare in orizzontale e in verticale un'immagine con WCS | pixel specchiati come `numpy.flip`; le coordinate celesti di ogni pixel fisico restano le stesse (ricalcolo con `astropy.wcs`, errore < 1e-9 gradi) | ricalcolo con NumPy e Astropy |
| T21 | Mosaico (B11) | due immagini sintetiche sovrapposte, con WCS diverse | valori uguali a `reproject_and_coadd` con media, ricalcolato nel test | ricalcolo con `reproject` |
| T22 | Fattore unico di `rgb_diff` | differenze positive e negative di ampiezza diversa | stessa scala per le due componenti, fattore scritto nel risultato | ricalcolo con `numpy` |
| T23 | Qualità del ricampionamento | ricampionare un'immagine che copre metà del riferimento | mappa di copertura uguale a quella di `reproject`; percentuale ricalcolata nel test | ricalcolo con `reproject` |
| T24 | Funzioni di trasferimento e palette | ogni funzione e palette dell'elenco | valori uguali a `astropy.visualization` e alle tabelle di `matplotlib`; nome fuori elenco → `DISPLAY_OPTION_UNKNOWN` | ricalcolo con le librerie |
| T25 | Strategie per dimensione (A10) | soglie configurate piccole nel test, file sintetici non compressi e compressi | strategia scelta secondo le regole di §3; soglie scritte nel risultato | test di unità |
| T26 | Salvataggio FITS | `save_fits` su un taglio, poi rilettura | dati e WCS uguali, origine e data nell'intestazione | confronto con `astropy.io.fits` |
| T27 | Calibrazione nel commento (H6) | PNG e JPEG generati con `Pillow` con un'intestazione WCS nel commento, e un `.hhh` | WCS uguale a quella costruita dallo stesso testo con `astropy.wcs` | ricalcolo con Astropy |
| T28 | Più HDU (D11-4) | file MEF sintetico con due HDU immagine e una tabella | `list_image_hdus` elenca le due immagini; `load_image` senza `hdu` → `HDU_CHOICE_REQUIRED`; con `hdu` apre quella giusta (confronto con `astropy.io.fits`) | test di unità |
| T29 | Assi degeneri e cubi | immagine a 4 assi con due assi di lunghezza 1; cubo 3 × N × M con 3 assi utili | la prima si apre in 2-D con WCS celeste uguale a quello di `astropy.wcs` (parte celeste) e assi tolti dichiarati; il cubo → `CUBE_NOT_SUPPORTED` | ricalcolo con Astropy |
| T30 | FITS RGB | HDU sintetica 3 × N × M con WCS, aperta con e senza `rgb=True` | con `rgb=True` immagine a colori con i tre piani uguali a `astropy.io.fits` e WCS celeste; senza → `CUBE_NOT_SUPPORTED`; `rgb=True` su 2 o 4 piani → `RGB_INPUT_INVALID` | confronto con Astropy |

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
- **D11-5 — Palette predefinite (B6): DECISA il 2026-10-09, CORRETTA il
  2026-10-10 (decisione del proprietario, regola d'oro n. 8).** Non si
  riproducono le palette di Aladin: si offrono palette scientifiche da fonti
  con licenza libera (`matplotlib`), equivalenti per uso, con **default
  `gray`**; elenco e fonte in §3.
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
- **D11-9 — Decisioni del 2026-10-10 sulla divisione in parti (proprietario):**
  funzioni di trasferimento di `astropy.visualization`; contorni con
  `contourpy`; elenco chiuso delle operazioni H5 con specchiature che
  aggiornano il WCS; soglie A10 per le immagini (1 GB, 4 GB, compressi oltre
  1 GB, anteprima ≤ 4096 pixel); qualità del ricampionamento = copertura di
  `reproject` + percentuale; fattore unico di `rgb_diff`; calibrazione di
  JPEG/PNG solo in lettura; esportazione della vista nel `41`; gli strumenti
  per l'IA di §11 vanno in `32-ia-registro-strumenti.md` (il testo di §11 si
  aggiorna con il 32). Applicate in §3, §6–§8, §10, §12.

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
| 2026-10-10 | Claude Code | **Decisioni del proprietario sulla divisione in parti** (autorizzazione esplicita a modificare §3, §6–§8, §10, §12, §13): D11-5 corretta (palette scientifiche da `matplotlib`, non quelle di Aladin, regola d'oro n. 8); funzioni di trasferimento di `astropy.visualization`; elenco chiuso H5 con specchiature che aggiornano il WCS (normalizzazione da verificare con la sez. 5.18 prima di P5); `contourpy`; soglie A10 per le immagini; qualità del ricampionamento; fattore unico di `rgb_diff`; calibrazione di JPEG/PNG solo in lettura, formato da standard pubblici prima di P2; `save_fits` nel §7, vista esportata dal 41; strumenti IA nel 32 (D11-9, §11 non modificato). Nuovi errori `OPERATION_UNSUPPORTED`, `DISPLAY_OPTION_UNKNOWN`; test T20–T27. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Precisazioni del proprietario prima del codice di P1:** HDU immagine = 2 assi di lunghezza > 1 (assi degeneri tolti e dichiarati, cubi → `CUBE_NOT_SUPPORTED`); più HDU immagine → parametro `hdu` di `load_image`, altrimenti `HDU_CHOICE_REQUIRED`; nuova `list_image_hdus`; provenienza dei file locali; costanti dei pixel lette prima della scala (§3, §7, §10 con `HDU_NOT_IMAGE`, §12 T28–T29). Verifica: HCOMPRESS, RICE, GZIP, PLIO e `.gz` supportati da `astropy.io.fits` 8.0.1. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P2, decisioni del proprietario e verifiche:** `Pillow` 12.3.0 verificata (licenza MIT-CMU, wheel per macOS arm64, JPEG/PNG/GIF attivi); documentazione pubblica di Aladin sulla calibrazione solo parziale (pagina man) → lettore su soli standard pubblici (JPEG `COM`, PNG `Comment`, FITS 4.0 per `.hhh`), approvato; FITS RGB solo con `rgb=True`. Scritti in §3 anche l'orientamento dei pixel (righe dal basso, da verificare con AP1), la precedenza del commento sul `.hhh` e i modi di colore; §7 `load_image(..., rgb=False)`; §10 `IMAGE_UNREADABLE`; §12 T30. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P3, decisione del proprietario:** immagini da URL con **prima la cache** (come `resolve_name`), `refresh=True`, copia in cache se la rete manca, timeout comuni di `04`, nessun dato parziale (§3, §7). Stato `approvato` invariato. |
