# 11-core-immagini-fits.md — immagini FITS e visualizzazione

**Stato:** approvato

## 2. Scopo

Aprire, gestire e regolare la visualizzazione delle immagini astronomiche
(FITS e non solo) con fedeltà scientifica, senza mai alterare i valori dei
pixel memorizzati.

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
- **Calibrazione esterna (D14-11, decisa dal proprietario il 2026-10-11):**
  `load_image` riceve il parametro facoltativo `calibration`, un oggetto
  con `header` (intestazione FITS con WCS celeste e `NAXIS1`/`NAXIS2`) e
  `source` (da dove viene, obbligatorio), per esempio la `SiaCalibration`
  che il 14 costruisce dalle colonne `VOX:WCS_*` di una lista SIA 1. Si usa
  **solo se l'immagine non ha una calibrazione propria** (altrimenti
  avviso `EXTERNAL_CALIBRATION_IGNORED`), con le stesse regole del `.hhh`:
  `NAXIS1`/`NAXIS2` uguali alle dimensioni dell'immagine e WCS celeste
  valido per il modulo 10, altrimenti l'immagine resta senza WCS con
  `WCS_MISSING` e il motivo; se il 14 non ha potuto costruirla (`header`
  assente) lo stesso avviso cita il motivo. Usata: avviso
  `EXTERNAL_CALIBRATION_USED` con la fonte, `calibration_source =
  "external"` e una voce nella storia dell'immagine (scritta anche da
  `save_fits`).
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
    `plasma`, `inferno`, `magma` (van der Walt e Smith); `cividis` (Nuñez,
    Anderton e Renslow 2018, adatta ai daltonici); `cubehelix` (Green
    2011); `afmhot` (colori del corpo nero); `coolwarm` (Moreland 2009,
    divergente). **Licenza verificata il 2026-10-10:** con `matplotlib`
    3.11.2 tutte queste tabelle sono distribuite con la licenza di
    `matplotlib` (derivata dalla PSF, permissiva); i valori si leggono dalla
    libreria (`matplotlib.colormaps`, con `bytes=True`), non si copiano.
  - **Dettagli di `set_display` (P4):** il piano di presentazione è
    `stretch(intervallo(dati))` con l'intervallo `vmin`–`vmax` di
    `astropy.visualization.ManualInterval` e la funzione di trasferimento
    scelta, ritagliato su [0, 1]; **`gamma`** è un'ulteriore potenza
    `PowerStretch(gamma)` di `astropy.visualization` applicata dopo la
    funzione di trasferimento (`gamma = 1` non cambia nulla); il risultato
    è in `float32` (solo presentazione) e poi in colori RGBA a 8 bit con la
    palette; **il calcolo è a blocchi di righe (al più 2²⁰ pixel per blocco)
    interamente in `float32`** (DC6), senza copiare l'immagine intera
    (decisione del proprietario del 2026-10-10: un'immagine 6000 × 6000 deve
    visualizzarsi); l'unica eccezione è l'equalizzazione dell'istogramma
    (`histeq`), che per definizione usa la distribuzione di tutto il piano:
    si raccolgono i valori finiti normalizzati del piano in `float32`; i pixel non finiti diventano **trasparenti** (alfa 0), mai un
    valore inventato; la disposizione delle righe è quella dei dati (dal
    basso). Per le immagini a colori la funzione di trasferimento si
    applica a ogni piano con lo stesso intervallo e la palette non si usa.
  - **Limiti iniziali di visualizzazione (D41-3, decisa dal proprietario
    il 2026-10-15):** all'apertura di un'immagine, e per i tile FITS di un
    HiPS senza `hips_pixel_cut`, vmin e vmax si propongono con
    **`suggest_display_limits`** (§7): intervallo **`ZScaleInterval` di
    `astropy.visualization`** con i parametri di default della libreria
    (scritti nel risultato), calcolato sui soli pixel finiti in `float64`
    (DC6); il campionamento della libreria è regolare, quindi stesso
    ingresso → stessi limiti. **I limiti scelti, il metodo e i parametri
    sono dichiarati nel risultato.** Immagini a colori: un solo intervallo
    su tutti i piani insieme (come `set_display`, che usa lo stesso
    intervallo per ogni piano), dichiarato. Immagini a due livelli (P6): il
    calcolo si fa sull'anteprima, dichiarato. La scelta finale dei limiti
    resta all'utente: `set_display` accetta qualsiasi vmin < vmax.
  - **Sovrapposizione con trasparenza (B5, `blend`):** piani RGBA della
    stessa griglia (ricampionati prima, P7), composti dal basso verso l'alto
    con l'operatore "over" di Porter e Duff (1984): colore = α·sopra +
    (1 − α)·sotto, con l'opacità α di ciascun piano in [0, 1].
- **Taglio (cutout):** estrarre una sottoparte di un'immagine con WCS coerente
  (B8), con `astropy.nddata.Cutout2D`; centro in coordinate celesti (serve il
  WCS) o in pixel (convenzione dichiarata), lato in unità angolari (serve il
  WCS) o in pixel. Taglio in parte fuori dall'immagine → si restituisce
  l'intersezione, dichiarata; del tutto fuori → `CUTOUT_OUT_OF_RANGE`.
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
  calcolata con `astropy.convolution.convolve` con i suoi valori di default
  (bordo riempito con 0, pixel non finiti interpolati, kernel normalizzato),
  scritti nel risultato; (4) **normalizzazione** — divisione per la media dei
  pixel finiti, così che i valori siano distribuiti attorno a 1
  (verificato il 2026-10-10 con il manuale di Aladin, ed. giugno 2022, sez.
  5.18: «normalisation … par division préalable par la moyenne»); media
  nulla o non finita → errore; (5) **specchiature** orizzontale e verticale, che
  **aggiornano anche il WCS** (il cielo resta agganciato agli stessi pixel
  fisici): astropy non inverte gli assi di un WCS, quindi si aggiorna la
  parte lineare secondo lo standard FITS WCS (Paper I) — `CRPIX` riflesso
  (`n + 1 − CRPIX`) e segno cambiato della colonna corrispondente della
  matrice `CD` o `PC`; un WCS con distorsioni (SIP, TPD, tabelle) non si
  specchia: errore `OPERATION_UNSUPPORTED`. Le operazioni tra immagini
  richiedono la **stessa griglia** (stesse dimensioni e, se c'è, stesso
  WCS): altrimenti si ricampiona prima con P7, in modo **esplicito**, perché
  il ricampionamento cambia i valori e il suo metodo va scelto e dichiarato
  (decisione confermata dal proprietario il 2026-10-10); per somma e
  differenza servono le stesse unità. Ogni operazione produce un **nuovo** oggetto, calcolato in
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
  esterno della corona **facoltativi, con default raggio interno = 1 ×
  `box_size` ed esterno = 1,5 × `box_size`** (D11-8, decisa il 2026-10-15),
  sempre scritti nel risultato; chi li passa (es. il `20`) usa i propri. Il
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
  provenienza (`save_fits`): origine e data di scaricamento si scrivono
  nelle parole chiave `A2ORIGIN` e `A2DATE` (ISO 8601, UTC) e in una riga
  `HISTORY`; le immagini a colori si salvano come FITS a 3 piani. L'esportazione **della vista** come immagine è
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
    commento nel file, vale quello e il `.hhh` si ignora (dichiarato,
    `HHH_IGNORED`); **se i due WCS sono diversi** (decisione del
    proprietario del 2026-10-10) il risultato porta anche l'avviso
    `HHH_WCS_DIFFERS` con le parole chiave diverse. Criterio: i due WCS si
    confrontano sulle parole chiave normalizzate da `astropy.wcs`
    (`WCS.to_header(relax=True)`), valore per valore; sono diversi anche
    quando uno solo dei due testi è una calibrazione valida. Se il
    testo non è un'intestazione FITS valida con WCS celeste, o i suoi
    `NAXIS1`/`NAXIS2` non sono le dimensioni dell'immagine, l'immagine si
    apre senza WCS con avviso `WCS_MISSING`.
  - **Orientamento dei pixel:** JPEG, PNG e GIF memorizzano le righe
    dall'alto verso il basso, il FITS dal basso verso l'alto. In memoria le
    righe si mettono **dal basso verso l'alto** (la riga 0 dell'array è
    l'ultima del file), così l'immagine ha la stessa disposizione di un FITS
    e il WCS letto dal commento vale con la convenzione dei pixel FITS
    (DC7): una sola disposizione delle righe per tutte le immagini, qualunque
    sia il formato (confermata dal proprietario il 2026-10-10).
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
  prima del codice). Obiettivo minimo di dimensione (parità, `01-architettura.md`
  §8): JPEG/PNG con WCS fino a 100 megapixel.
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
  - **Regole precise (decisioni del proprietario del 2026-10-10):** la
    dimensione è quella dei dati decompressi (righe × colonne × byte per
    pixel). File compressi (a riquadri o `.gz`): in memoria fino a 1 GB,
    altrimenti due livelli. File non compressi: in memoria fino a 1 GB; tra
    1 e 4 GB `memmap`, **ma** se l'intestazione ha `BZERO`, `BSCALE` o
    `BLANK` `astropy.io.fits` rifiuta il `memmap` (verificato con astropy
    8.0.1) e si usano i due livelli, con il motivo scritto nel risultato;
    oltre 4 GB due livelli. `load_image` applica da sé queste regole ai file
    FITS locali oltre il limite della memoria.
  - **Lettura per regione:** i pixel originali di una regione si leggono con
    `section` di `astropy.io.fits` (senza caricare il resto del file, con la
    scala applicata dalla libreria; verificato per dati semplici, con scala,
    interi senza segno e compressi).
  - **Immagini a due livelli nel resto del modulo:** l'anteprima è solo di
    presentazione (`set_display` la usa); il centroide e il taglio leggono i
    pixel originali della regione che serve; le operazioni sull'intera
    immagine (H5, contorni) e `save_fits` danno `PREVIEW_NOT_MEASURABLE`.
    Il pixel `(x, y)` dell'anteprima corrisponde al pixel `(x · passo,
    y · passo)` dell'originale.
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
  - **Precisazioni del proprietario (2026-10-10):** in modalità `rgb` ogni
    componente si porta su 0–255 con **parametri espliciti** (vmin, vmax e
    funzione di trasferimento dell'elenco di §3, come `set_display`),
    senza default; con 2 immagini, che vanno in R e G, la **terza
    componente (B)** è la media delle due componenti a 8 bit
    (arrotondata). In `rgb_diff` la differenza è prima immagine − seconda,
    dopo il ricampionamento e con le stesse unità; positivi in R, negativi
    (in valore assoluto) in G, con il fattore unico 255 / max |differenza|;
    **B = 0**. Le lunghezze d'onda per l'ordine delle componenti arrivano da
    un parametro opzionale (`wavelengths`): la più lunga va in R; senza,
    vale l'ordine dato (nessuna parola chiave indovinata). Il ricampionamento
    dell'RGB usa il pixel più vicino; i pixel di riferimento non coperti da
    una componente valgono 0 e sono segnati nella maschera di copertura.
  - **Metodo di ricampionamento** di `resample_to_reference`, `reproject` e
    `mosaic`: **obbligatorio, senza default** (`nearest`, `bilinear` con
    `reproject_interp`; `flux` con `reproject_exact`, che conserva il
    flusso come dichiarato da `reproject`), scritto nel risultato. La
    percentuale di pixel coperti conta i pixel del riferimento con
    copertura > 0.
- **Mosaico e sequenza animata (B11, sez. 5.16):** mosaico nella griglia
  dell'immagine di riferimento con **media** nelle zone sovrapposte e senza
  correzione del fondo, dichiarato nel risultato: correggere il fondo
  richiede un modello del cielo di ciascuna immagine, che è una scelta di
  analisi e non va fatta in silenzio; senza correzione i valori restano
  quelli delle immagini ricampionate. Cubo come sequenza animata
  (scorrimento nel 41, analisi nel 23).
- **Limite delle operazioni (D11-11, decisione del proprietario del
  2026-10-10), separato da A10:** A10 resta la **strategia di caricamento**
  (in memoria fino a 1 GB, poi `memmap` o due livelli). Il **limite delle
  operazioni** è un valore nuovo, **4 GB di default, configurabile**
  (`LargeImageLimits.operation_bytes`): prima di ogni operazione H5, dei
  contorni, di `set_display`, di `save_fits`, del ricampionamento, dell'RGB,
  del mosaico e del taglio si **stima la memoria necessaria**; se supera il
  limite (con più immagini vale il più piccolo dei loro limiti)
  l'operazione **non carica nulla** e dà `MEMORY_LIMIT_EXCEEDED`, con la
  stima e il limite nel messaggio. La stima conta gli array presenti insieme
  durante il calcolo (`N` = pixel di un piano; 8 byte per ogni array
  `float64`, 4 per `float32`):

  | Operazione | Stima (byte) |
  |---|---|
  | H5 tra due immagini (somma, differenza, prodotto, rapporto) | 3 × 8 × `N` (due operandi e risultato) |
  | H5 con costante, normalizzazione, specchiature | 2 × 8 × `N` |
  | H5 convoluzione | 3 × 8 × `N` (operando, risultato, copia di lavoro di `astropy.convolution`) |
  | contorni | 2 × 8 × `N` (copia `float64` con maschera, strutture di `contourpy`) |
  | `set_display` | (4 × piani + 4) × `N` (valori `float32` e RGBA) + 8 × `N` con `histeq` (valori raccolti e ordinati) + 16 × pixel di un blocco |
  | `save_fits` | 2 × byte per pixel × `N` (dati e copia nell'ordine di byte del FITS) |
  | ricampionamento | 8 × `N` dell'ingresso + 2 × 8 × `N` del riferimento (risultato e copertura) |
  | mosaico e RGB | 8 × Σ `N` degli ingressi + (2 × numero di ingressi + 2) × 8 × `N` del riferimento |
  | taglio | byte per pixel × pixel del taglio (× 3 per le immagini a colori) |

  La stima è un ordine di grandezza dichiarato, non una misura: serve a
  rifiutare prima di caricare. Le immagini a due livelli restano rifiutate
  da `PREVIEW_NOT_MEASURABLE` prima di questo controllo; `set_display` su di
  esse conta solo l'anteprima.
- **Convenzione dei pixel e costanti (H25, H4):** coordinate pixel interne in
  convenzione numpy, conversione FITS solo con `convert_pixel_convention` del
  modulo 10 (DC7); `BZERO`, `BSCALE`, `BLANK` e unità dei pixel sono esposti a
  `18-core-calcolatrici.md` per la calcolatrice dei pixel.
- **Valore grezzo di un pixel (D18-6; spostato qui dal 18 per decisione del
  proprietario del 2026-10-13):** `read_raw_pixel(image, x, y)` legge dal
  file il valore **scritto nel file**, senza `BZERO`/`BSCALE`, con
  `astropy.io.fits` e l'opzione **`do_not_scale_image_data=True`**, solo la
  regione 1 × 1 (`section`, anche per le immagini con assi degeneri tolti).
  `x`, `y` interi in convenzione numpy (DC7). Il valore uguale a `BLANK` è
  restituito com'è (lo interpreta chi chiama). Immagine non FITS, a colori o
  **derivata** (`history` non vuota: taglio, operazioni H5, calibrazione
  esterna — i pixel non sono più quelli del file), posizione fuori
  dall'immagine o file non leggibile → `PIXEL_RAW_UNAVAILABLE`. Il modulo 18
  la richiama per la calcolatrice dei pixel.

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
  `23-analisi-cubi-di-dati.md`, `41-ui-visualizzatore-cielo.md`
  (`set_display`, `star_centroid` con la corona di default),
  `05-comandi-sessione.md` (comandi delle immagini),
  `43-ui-pannello-analisi.md`.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `path` / `url` | stringa | percorso file o URL | FITS, JPEG, PNG |
| in | immagine FITS | array + header | pixel (unità da header, es. MJy/sr o ADU) | + WCS |
| in | taglio | float64 | gradi (centro) + lato in gradi o in pixel | output: nuovo FITS |
| in | parametri di display | float64 | vmin, vmax, gamma, palette | solo presentazione |
| out | limiti iniziali proposti | float64 | vmin, vmax nell'unità dell'immagine (`BUNIT` o "non dichiarata"), metodo `zscale`, parametri, pixel usati | `suggest_display_limits` (D41-3) |
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
  per JPEG/PNG legge la calibrazione dal commento o dal `.hhh`;
  `calibration=None` (parola chiave, D14-11) = calibrazione esterna usata
  solo se l'immagine non ne ha una propria (§3).
- **`list_image_hdus(source)`** — elenco delle HDU immagine del file
  (indice, nome, dimensioni, compressione), per la scelta dell'utente.
- **`set_display(image, vmin, vmax, gamma, palette, stretch="linear")`** —
  calcola i parametri di visualizzazione (non modifica l'originale):
  funzione di trasferimento (`linear`, `log`, `sqrt`, `squared`, `asinh`,
  `histeq`) e palette dagli elenchi chiusi di §3; restituisce il piano di
  presentazione (`float32` in [0, 1] e colori RGBA a 8 bit) con i parametri
  usati, senza toccare l'array dell'immagine.
- **`suggest_display_limits(image, *, method="zscale")`** (aggiunta il
  2026-10-15, D41-3) — propone vmin e vmax per `set_display`. `image` è
  un'immagine dell'11 o un array 2-D (anche i dati di un tile FITS del 12).
  Unico metodo nella v1: `zscale` (`ZScaleInterval` di
  `astropy.visualization` con i parametri di default della libreria:
  numero di campioni, contrasto, rigetto, iterazioni). Restituisce
  **`DisplayLimits`**: vmin, vmax (`float64`), unità, metodo e parametri,
  numero di pixel finiti usati, note (colori: intervallo comune; due
  livelli: calcolato sull'anteprima). Non modifica l'immagine.
- **`resample_to_reference(image, reference, method)`** — ricampiona su una
  soluzione astrometrica di riferimento (B7); restituisce nuova immagine +
  qualità (mappa di copertura di `reproject` + percentuale di pixel coperti).
- **`reproject(images, reference, method)`** — ricampiona più immagini sulla
  stessa griglia di riferimento (base comune di RGB, mosaico e
  sovrapposizione); **`blend(planes, opacities)`** — sovrapposizioni con
  alpha (B5): compone piani RGBA della stessa griglia con l'operatore
  "over" (§3).
- **`cutout(image, center, size)`** — taglio con WCS coerente.
- **`image_operation(a, b, op)`** — aritmetica/convoluzione/normalizzazione/
  specchiatura (H5); `op` dall'elenco chiuso di §3; `b` è un'immagine, una
  costante o un kernel secondo l'operazione; le specchiature aggiornano il
  WCS.
- **`save_fits(image, path)`** — salva un'immagine o un taglio come FITS con
  WCS e provenienza (origine, data) nell'intestazione.
- **`contours(image, levels)`** — isofote (H7) con `contourpy`; `levels` in
  unità dell'immagine; restituisce le curve in pixel (convenzione numpy),
  con il metodo `to_sky(image)` per averle in coordinate celesti (modulo 10).
- **`star_centroid(image, position, box_size, annulus_inner=None, annulus_outer=None)`**
  — baricentro pesato sull'intensità, dopo la sottrazione del fondo (D11-7),
  nella finestra quadrata di lato `box_size` pixel (intero dispari ≥ 3)
  centrata sul pixel più vicino a `position` (convenzione numpy); il fondo è
  la mediana con sigma clipping dei pixel a distanza da `position` in
  [`annulus_inner`, `annulus_outer`) pixel (omessi: 1 × e 1,5 × `box_size`,
  D11-8); `image` è un array 2-D o un
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
- **`open_large_image(source, hdu=None, limits=LargeImageLimits())`** — apre
  un'immagine FITS locale scegliendo la strategia per dimensione (H27,
  A10); restituisce un `FitsImage` con strategia, motivo e soglie usate,
  vista a bassa risoluzione marcata (due livelli) e accesso all'alta
  risoluzione per regione (`FitsImage.read_region`).
- **`LargeImageLimits`** (struttura) — soglie configurabili della strategia
  di caricamento (A10): memoria 1 GB, due livelli 4 GB, compressi 1 GB, lato
  massimo dell'anteprima 4096 pixel; più il **limite delle operazioni**
  `operation_bytes`, 4 GB (D11-11, `MEMORY_LIMIT_EXCEEDED`, §3).
- **`FitsImage.read_region(x0, x1, y0, y1)`** — pixel originali della
  regione `[y0:y1, x0:x1]` (convenzione numpy), qualunque sia la strategia;
  **`FitsImage.memory_bytes`** — memoria occupata dai dati in RAM.
- **`rgb_composite(images, reference=None, mode="rgb", display=None,
  wavelengths=None)`** — immagine a colori da 2 o 3 immagini (`mode` = `rgb`
  o `rgb_diff`), con ricampionamento sul riferimento (di default l'immagine
  con il pixel angolare più piccolo); `display` = (vmin, vmax, funzione di
  trasferimento) per ogni componente in `rgb`; restituisce un nuovo piano di
  presentazione con origine delle componenti, parametri, fattore di scala
  (`rgb_diff`) e maschera di copertura.
- **`mosaic(images, reference, method)`** — mosaico nella griglia del
  riferimento con media nelle sovrapposizioni (`reproject_and_coadd`), senza
  correzione del fondo.
- **`pixel_scaling(image)`** — restituisce `BZERO`, `BSCALE`, `BLANK` e unità
  dei pixel (per il modulo 18).
- **`read_raw_pixel(image, x, y)`** — valore grezzo di un pixel letto dal file
  con `do_not_scale_image_data=True` (D18-6), `float64`; per il modulo 18.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `astropy.io.fits` | lettura/scrittura FITS | standard di fatto |
| `astropy.wcs` (via modulo 10) | WCS dei tagli | coerente con il nucleo |
| `numpy` | manipolazione array | base dell'ecosistema scientifico |
| `scipy.ndimage` | convoluzione, ricampionamento semplice, baricentro del centroide (`center_of_mass`) | consolidato e testato |
| `astropy.stats` | fondo cielo del centroide con `sigma_clipped_stats` (D11-7) | libreria di riferimento |
| `reproject` (D11-2, decisa; licenza da verificare prima del codice) | ricampionamento tra proiezioni (B7), mappa di copertura, mosaico (`reproject_and_coadd`) | pensato per questo scopo; vedi §13 |
| `astropy.visualization` | funzioni di trasferimento e intervalli (B3, B4); `ZScaleInterval` per i limiti iniziali (D41-3) | libreria di riferimento |
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
- Nessuna operazione sull'immagine intera carica dati oltre il limite delle
  operazioni (D11-11, 4 GB di default): prima la stima, poi il calcolo (§3).

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
| `suggest_display_limits` senza pixel finiti | nessun limite proposto, messaggio | `DISPLAY_LIMITS_UNDEFINED` |
| `suggest_display_limits` con vmin = vmax (immagine costante) | nessun limite proposto, messaggio con il valore costante; l'utente sceglie i limiti | `DISPLAY_LIMITS_UNDEFINED` |
| Metodo diverso da `zscale` | rifiuto con l'elenco dei metodi | `DISPLAY_METHOD_UNKNOWN` |
| Finestra o corona del centroide fuori dall'immagine | rifiuto con la finestra e i limiti dell'immagine | `CENTROID_OUT_OF_IMAGE` |
| Centroide non definito (somma dei pesi ≤ 0 dopo la sottrazione del fondo, pixel non finiti nella finestra, nessun pixel finito nella corona) | nessuna posizione prodotta | `CENTROID_UNDEFINED` |
| Memoria stimata di un'operazione oltre il limite delle operazioni (D11-11) | nessun dato caricato, errore con stima e tetto | `MEMORY_LIMIT_EXCEEDED` |
| JPEG/PNG con commento e `.hhh` che descrivono WCS diversi | vale il commento; avviso con le parole chiave diverse | avviso `HHH_WCS_DIFFERS` |
| Calibrazione esterna (D14-11) usata su un'immagine senza WCS | WCS dalla calibrazione, fonte dichiarata | avviso `EXTERNAL_CALIBRATION_USED` |
| Calibrazione esterna data per un'immagine che ha già il WCS | vale il WCS proprio | avviso `EXTERNAL_CALIBRATION_IGNORED` |
| Calibrazione esterna assente, con dimensioni diverse o non valida | immagine senza WCS, motivo nell'avviso | `WCS_MISSING` |
| Valore grezzo chiesto per un'immagine non FITS, a colori o derivata, fuori dall'immagine o con indici non interi | nessun valore | `PIXEL_RAW_UNAVAILABLE` |

### Parametri dei messaggi (D40-3)

Dal 2026-10-24 (sprint 8b) ogni errore e ogni avviso del modulo nasce come **codice + `params`**
(`ImagesFitsError(code, message, params=...)`; le note in `FitsImage.warnings` sono `ModuleWarning(code, text, params)`, una coppia (codice, testo) con in più `params`): `params` è un
dizionario nome → valore JSON con tutti i valori che finiscono nel testo, mai
arrotondati; le quantità sono `{"value": numero o elenco, "unit": testo}`. Il
**testo italiano del modulo resta invariato** (campo `text`/`message`, usato
come ripiego e nei file di sessione); il modulo **non** contiene traduzioni e
non importa il catalogo: la traduzione inglese/italiana sta in
`src/astrotwo/messages_catalog.py` (`40` §3.7.1). I codici che il modulo
solleva per ragioni diverse portano in `params` il parametro riservato
`reason` (identificatore stabile, D40-6) che sceglie la sotto-voce del
catalogo; "esterno" = testo di terzi (libreria, file, servizio), inserito tale
e quale e senza tradurlo. Nessun identificatore di errore cambia.

Nessun messaggio di questo modulo ne incorpora un altro **di AstroTwo** (D40-7): `detail` è testo di terzi
(eccezioni di librerie) e `cause` di `WCS_MISSING` `external_unavailable` è il motivo scritto da chi fornisce la
calibrazione esterna (il 14 finché non è convertito), quindi resta parametro esterno; diventerà `message` quando quel
motivo sarà un messaggio di AstroTwo con codice (sprint 8d).

| Codice | `reason` | Parametri (`params`) |
|---|---|---|
| `FITS_UNREADABLE` | (generale) | `path` (string) |
| `FITS_UNREADABLE` | `file_unreadable` | `path` (string), `detail` (string, esterno) |
| `FITS_UNREADABLE` | `fits_unreadable` | `path` (string), `detail` (string, esterno) |
| `FITS_UNREADABLE` | `file_missing` | `path` (string) |
| `FITS_UNREADABLE` | `data_unreadable` | `path` (string), `detail` (string, esterno) |
| `FORMAT_UNSUPPORTED` | (generale) | `supported` (list) |
| `FORMAT_UNSUPPORTED` | `gzip_unreadable` | `detail` (string, esterno) |
| `HDU_CHOICE_REQUIRED` | (generale) | — |
| `HDU_CHOICE_REQUIRED` | `rgb` | `path` (string), `count` (integer) |
| `HDU_CHOICE_REQUIRED` | `images` | `path` (string), `count` (integer), `hdus` (list) |
| `HDU_NOT_IMAGE` | (generale) | — |
| `HDU_NOT_IMAGE` | `no_such_hdu` | `hdu` (string) |
| `HDU_NOT_IMAGE` | `no_image_hdu` | `path` (string) |
| `HDU_NOT_IMAGE` | `no_such_hdu_listed` | `hdu` (string), `hdus` (list) |
| `HDU_NOT_IMAGE` | `not_an_image` | `hdu` (string), `hdus` (list) |
| `CUBE_NOT_SUPPORTED` | (generale) | — |
| `CUBE_NOT_SUPPORTED` | `only_cubes` | `path` (string) |
| `CUBE_NOT_SUPPORTED` | `hdu_is_cube` | `hdu` (string) |
| `RGB_INPUT_INVALID` | (generale) | — |
| `RGB_INPUT_INVALID` | `no_rgb_hdu` | `path` (string) |
| `RGB_INPUT_INVALID` | `hdu_not_rgb` | `hdu` (string) |
| `RGB_INPUT_INVALID` | `monochrome_required` | `operation` (string) |
| `RGB_INPUT_INVALID` | `monochrome_images_required` | — |
| `RGB_INPUT_INVALID` | `mode_unknown` | `mode` (string) |
| `RGB_INPUT_INVALID` | `image_count` | `count` (integer), `mode` (string) |
| `RGB_INPUT_INVALID` | `wavelengths` | — |
| `RGB_INPUT_INVALID` | `display_required` | — |
| `CUTOUT_OUT_OF_RANGE` | (generale) | — |
| `CUTOUT_OUT_OF_RANGE` | `region` | `x0` (integer), `x1` (integer), `y0` (integer), `y1` (integer), `nx` (integer), `ny` (integer) |
| `CUTOUT_OUT_OF_RANGE` | `outside` | `center` (string) |
| `CUTOUT_OUT_OF_RANGE` | `invalid` | `center` (string), `detail` (string, esterno) |
| `IMAGE_SHAPE_MISMATCH` | (generale) | — |
| `IMAGE_SHAPE_MISMATCH` | `planes` | `shapes` (list) |
| `IMAGE_SHAPE_MISMATCH` | `sizes` | `shape_a` (string), `shape_b` (string) |
| `IMAGE_SHAPE_MISMATCH` | `grids` | — |
| `UNIT_MISMATCH` | (generale) | — |
| `UNIT_MISMATCH` | `operands` | `unit_a` (string), `unit_b` (string) |
| `UNIT_MISMATCH` | `rgb_diff` | `unit_a` (string), `unit_b` (string) |
| `UNIT_MISMATCH` | `mosaic` | `units` (list) |
| `OPERATION_UNSUPPORTED` | (generale) | — |
| `OPERATION_UNSUPPORTED` | `color_image` | `operation` (string) |
| `OPERATION_UNSUPPORTED` | `flip_distortion` | — |
| `OPERATION_UNSUPPORTED` | `operation_unknown` | `operation` (string), `allowed` (list) |
| `OPERATION_UNSUPPORTED` | `operand_required` | `operation` (string) |
| `OPERATION_UNSUPPORTED` | `kernel_required` | — |
| `OPERATION_UNSUPPORTED` | `no_operands` | `operation` (string) |
| `OPERATION_UNSUPPORTED` | `normalization_undefined` | `mean` (number) |
| `OPERATION_UNSUPPORTED` | `resampling_method_unknown` | `method` (string), `allowed` (list) |
| `DISPLAY_OPTION_UNKNOWN` | (generale) | `option` (string), `value` (string), `allowed` (list) |
| `DISPLAY_METHOD_UNKNOWN` | (generale) | `method` (string), `allowed` (list) |
| `DISPLAY_LIMITS_UNDEFINED` | (generale) | — |
| `DISPLAY_LIMITS_UNDEFINED` | `no_finite_pixels` | — |
| `DISPLAY_LIMITS_UNDEFINED` | `constant` | `value` (number) |
| `MEMORY_LIMIT_EXCEEDED` | (generale) | `operation` (string), `needed` (quantity), `limit` (quantity) |
| `PREVIEW_NOT_MEASURABLE` | (generale) | `operation` (string), `preview_step` (integer) |
| `COMPRESSION_UNSUPPORTED` | (generale) | `path` (string), `compression` (string), `detail` (string, esterno) |
| `IMAGE_UNREADABLE` | (generale) | `path` (string), `detail` (string, esterno) |
| `PIXEL_RAW_UNAVAILABLE` | (generale) | — |
| `PIXEL_RAW_UNAVAILABLE` | `not_fits` | `format` (string) |
| `PIXEL_RAW_UNAVAILABLE` | `color_image` | — |
| `PIXEL_RAW_UNAVAILABLE` | `derived` | `history` (list) |
| `PIXEL_RAW_UNAVAILABLE` | `position` | `x` (string), `y` (string), `nx` (integer), `ny` (integer) |
| `PIXEL_RAW_UNAVAILABLE` | `unreadable` | `origin` (string), `detail` (string, esterno) |
| `CENTROID_OUT_OF_IMAGE` | (generale) | `nx` (integer), `ny` (integer) |
| `CENTROID_OUT_OF_IMAGE` | `window_and_annulus` | `x0` (integer), `x1` (integer), `y0` (integer), `y1` (integer), `radius` (quantity), `nx` (integer), `ny` (integer) |
| `CENTROID_UNDEFINED` | (generale) | — |
| `CENTROID_UNDEFINED` | `non_finite_window` | — |
| `CENTROID_UNDEFINED` | `no_background_pixels` | — |
| `CENTROID_UNDEFINED` | `no_flux` | — |
| `EXTERNAL_CALIBRATION_IGNORED` | (generale) | `source` (string) |
| `EXTERNAL_CALIBRATION_USED` | (generale) | `source` (string) |
| `STRATEGY` | (generale) | `strategy` (string) |
| `STRATEGY` | `compressed` | `strategy` (string), `size` (quantity), `limit` (quantity) |
| `STRATEGY` | `scaled_keywords` | `strategy` (string), `size` (quantity), `keywords` (list) |
| `STRATEGY` | `over_memory` | `strategy` (string), `size` (quantity), `limit` (quantity) |
| `STRATEGY` | `over_two_level` | `strategy` (string), `size` (quantity), `limit` (quantity) |
| `AXES_DROPPED` | (generale) | `axes` (list) |
| `NONFINITE_PIXELS` | (generale) | — |
| `NONFINITE_PIXELS` | `excluded` | — |
| `NONFINITE_PIXELS` | `operation_result` | `operation` (string) |
| `ALPHA_DROPPED` | (generale) | `mode` (string) |
| `FRAMES` | (generale) | `frames` (integer) |
| `HHH_IGNORED` | (generale) | `name` (string) |
| `HHH_WCS_DIFFERS` | (generale) | `name` (string), `differences` (string) |
| `FROM_CACHE` | (generale) | — |
| `FROM_CACHE` | `network_unavailable` | `error` (string) |
| `FROM_CACHE` | `cached_url` | `retrieved_at` (string) |
| `UNIT_UNKNOWN` | (generale) | `unit_a` (string), `unit_b` (string) |
| `CUTOUT_TRIMMED` | (generale) | `shape` (string), `requested_shape` (string) |
| `WCS_MISSING` | (generale) | — |
| `WCS_MISSING` | `header_required` | — |
| `WCS_MISSING` | `no_celestial_wcs` | — |
| `WCS_MISSING` | `not_celestial` | — |
| `WCS_MISSING` | `wcs_required` | — |
| `WCS_MISSING` | `cutout_center` | — |
| `WCS_MISSING` | `cutout_size` | — |
| `WCS_MISSING` | `contours_sky` | — |
| `WCS_MISSING` | `resampling` | `operation` (string), `origin` (string) |
| `WCS_MISSING` | `reference` | — |
| `WCS_MISSING` | `rgb` | `origin` (string) |
| `WCS_MISSING` | `external_unavailable` | `source` (string), `cause` (string, esterno) |
| `WCS_MISSING` | `external_no_header` | `source` (string) |
| `WCS_MISSING` | `hhh_unreadable` | `name` (string), `detail` (string, esterno) |
| `WCS_MISSING` | `no_calibration` | — |
| `WCS_MISSING` | `calibration_invalid_header` | `kind` (string) |
| `WCS_MISSING` | `calibration_size_differs` | `kind` (string), `naxis1` (string), `naxis2` (string), `nx` (integer), `ny` (integer) |
| `WCS_MISSING` | `celestial_axes` | `celestial_axes` (list), `useful_axes` (list) |
| `NET_TIMEOUT` | (generale) | `service` (string), `target` (string), `connect` (quantity), `read` (quantity), `detail` (string, esterno) |
| `NET_TIMEOUT` | `url` | `url` (string), `connect` (quantity), `read` (quantity), `detail` (string, esterno) |

## 11. Esposizione all'IA

Non applicabile in questo file: gli strumenti per l'IA del modulo sono
descritti in `32-ia-registro-strumenti.md` (D11-9, spostamento eseguito il
2026-10-10). Finché il 32 non esiste, l'elenco da riportarvi (nomi
provvisori: `load_image_info`, `get_image_statistics`, `image_operation`,
`cutout`) è annotato nella riga del 32 in `panoramica.md` §4. Vale sempre la
regola d'oro n. 1: l'IA sceglie i parametri e spiega, i numeri vengono dalle
funzioni di §7.

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
| T24 | Funzioni di trasferimento e palette | ogni funzione e palette dell'elenco, con e senza `gamma`, pixel non finiti | valori uguali a `astropy.visualization` e alle tabelle di `matplotlib`; non finiti trasparenti; nome fuori elenco → `DISPLAY_OPTION_UNKNOWN` | ricalcolo con le librerie |
| T31 | Sovrapposizione (B5) | due piani RGBA con opacità note | colore uguale all'operatore "over" ricalcolato nel test; griglie diverse → `IMAGE_SHAPE_MISMATCH` | ricalcolo con `numpy` |
| T25 | Strategie per dimensione (A10) | soglie configurate piccole nel test, file sintetici non compressi e compressi | strategia scelta secondo le regole di §3; soglie scritte nel risultato | test di unità |
| T26 | Salvataggio FITS | `save_fits` su un taglio, poi rilettura | dati e WCS uguali, origine e data nell'intestazione | confronto con `astropy.io.fits` |
| T27 | Calibrazione nel commento (H6) | PNG e JPEG generati con `Pillow` con un'intestazione WCS nel commento, e un `.hhh` | WCS uguale a quella costruita dallo stesso testo con `astropy.wcs` | ricalcolo con Astropy |
| T28 | Più HDU (D11-4) | file MEF sintetico con due HDU immagine e una tabella | `list_image_hdus` elenca le due immagini; `load_image` senza `hdu` → `HDU_CHOICE_REQUIRED`; con `hdu` apre quella giusta (confronto con `astropy.io.fits`) | test di unità |
| T29 | Assi degeneri e cubi | immagine a 4 assi con due assi di lunghezza 1; cubo 3 × N × M con 3 assi utili | la prima si apre in 2-D con WCS celeste uguale a quello di `astropy.wcs` (parte celeste) e assi tolti dichiarati; il cubo → `CUBE_NOT_SUPPORTED` | ricalcolo con Astropy |
| T32 | Commento contro `.hhh` | PNG con WCS nel commento e `.hhh` con lo stesso WCS, poi con `CRVAL1` diverso, poi non valido | vale sempre il commento (WCS uguale a quello costruito dal commento con `astropy.wcs`); nessun `HHH_WCS_DIFFERS` con lo stesso WCS; avviso che cita `CRVAL1` (e non `CRVAL2`) con WCS diverso; avviso anche con `.hhh` non valido | ricalcolo con Astropy |
| T33 | Limite delle operazioni (D11-11) | limite piccolo configurato nel test; ogni operazione sull'immagine intera; immagine in `memmap` | `MEMORY_LIMIT_EXCEEDED` con la stima della tabella di §3 e il limite; nessun dato caricato; taglio piccolo e `save_fits` sotto il limite riescono; con il limite di default le stesse operazioni riescono e l'immagine in `memmap` si visualizza (strategia A10 e limite separati) | test di unità |
| T34 | Visualizzazione a blocchi in `float32` | `set_display` su un array 6000 × 6000 con il limite di default; `histeq` con blocchi piccoli | si visualizza; valori uguali ad `astropy.visualization` in `float32`; picco di memoria (misurato con `tracemalloc`) sotto 8 byte per pixel + 64 MB, cioè senza copia `float64` dell'immagine; `histeq` a blocchi uguale all'equalizzazione su tutto il piano | ricalcolo con Astropy, `tracemalloc` |
| T35 | Calibrazione esterna (D14-11) | FITS senza WCS caricato con una calibrazione esterna; stessa calibrazione su un FITS con WCS; oggetto senza `source`; nel 14 (T11) calibrazione della lista SIA su un'immagine scaricata | WCS uguale ad `astropy.wcs` costruito dall'intestazione del test, `EXTERNAL_CALIBRATION_USED`; con WCS proprio `EXTERNAL_CALIBRATION_IGNORED`; senza `source` errore; dimensioni diverse → `WCS_MISSING` | ricalcolo con Astropy |
| T36 | Valore grezzo (D18-6) | FITS `int16` con `BZERO`, `BSCALE`, `BLANK`; stesso dato con un asse degenere; posizioni fuori, non intere; immagine derivata | `read_raw_pixel` uguale a `astropy.io.fits` con `do_not_scale_image_data=True` in ogni pixel (anche quello uguale a `BLANK`); `PIXEL_RAW_UNAVAILABLE` negli altri casi | confronto con Astropy |
| T37 | Corona di default (D11-8) | `star_centroid` della stella di T16 con `box_size` 15 senza raggi, poi con raggi espliciti 15 e 22,5 | risultati identici; raggi usati (15 e 22,5 pixel) scritti nel risultato | confronto diretto |
| T38 | Limiti iniziali (D41-3) | `suggest_display_limits` su un'immagine sintetica con rumore e sorgenti (semina fissa), con pixel NaN | vmin, vmax uguali a `ZScaleInterval().get_limits` calcolato nel test sui pixel finiti in `float64`; parametri e numero di pixel dichiarati; immagine invariata | ricalcolo con astropy |
| T39 | Limiti ripetibili e casi limite | stessa immagine due volte; immagine costante; tutta NaN; metodo `minmax` | limiti identici; `DISPLAY_LIMITS_UNDEFINED` (due casi); `DISPLAY_METHOD_UNKNOWN` | test di unità |
| T40 | Colori e due livelli | immagine RGB sintetica; immagine a due livelli (P6) | intervallo comune ricalcolato nel test su tutti i piani; per i due livelli calcolo sull'anteprima dichiarato | ricalcolo con astropy |
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
  (pacchetto affiliato ad Astropy): metodi pixel più vicino e bilineare, più
  un metodo che conserva il flusso, utile quando i valori servono a misure
  successive. Licenza e installazione verificate il 2026-10-10 (P7).
- **D11-3 — Cache su disco: DECISA il 2026-10-04 (parte valori).** Limite di
  default **5 GB**, **configurabile** dall'utente, con **eliminazione dei
  dati meno usati** (estensione di A7). **Motivazione:** A7 richiede un limite
  configurabile con rimozione dei dati meno usati; un limite in GB è
  prevedibile e testabile (T4 di `12-core-hips.md`). Applicata in §3/§6/§9 qui
  sopra; l'interfaccia di configurazione resta in `40-ui-finestra-principale.md`
  e `60-distribuzione-dmg.md`.
- **D11-4 — HDU multiple: DECISA il 2026-10-09 (decisione del proprietario
  sulla checklist del livello 1).** si aprono **tutte le HDU immagine** del
  file (file a più estensioni MEF), con scelta dell'utente: un MEF contiene
  spesso più immagini scientifiche (es. rivelatori diversi) e sceglierne una
  in silenzio sarebbe un'assunzione; i cubi restano a
  `23-analisi-cubi-di-dati.md`.
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
- **D11-8 — Valori di default dei raggi della corona del centroide: DECISA
  il 2026-10-15 (decisione del proprietario, con il `41`).** Raggio interno
  = **1 × `box_size`**, esterno = **1,5 × `box_size`**, usati quando i raggi
  sono omessi e sempre scritti nel risultato; il `20` potrà passare valori
  propri. Il `box_size` resta obbligatorio: il valore iniziale dello
  strumento di misura del `41` è **15 pixel**, modificabile e dichiarato.
  **Motivazione (nostra):** il raggio interno supera la semidiagonale della
  finestra (≈ 0,71 × `box_size`), quindi la luce della stella cercata nella
  finestra non entra nella corona; la corona ha un'area di circa 3,9 volte
  la finestra, abbastanza pixel per la mediana con sigma clipping.
  Applicata in §3, §7, §12 (T37). **Codice aggiornato il 2026-10-16**
  (raggi facoltativi con il default, commit `f4c42b2`).
- **D41-3 — Limiti iniziali di visualizzazione: DECISA il 2026-10-15
  (decisione del proprietario, dal `41`).** Nuova funzione
  `suggest_display_limits` con `ZScaleInterval` di astropy; limiti scelti
  dichiarati nel risultato. Applicata in §3, §6, §7, §8, §10, §12
  (T38–T40). **Motivazione:** intervallo consolidato della comunità per
  mostrare il fondo cielo e le sorgenti deboli senza saturare; calcolo di
  libreria, nessun valore inventato. **Codice scritto il 2026-10-16**
  (commit `f4c42b2`).
- **D11-9 — Decisioni del 2026-10-10 sulla divisione in parti (proprietario):**
  funzioni di trasferimento di `astropy.visualization`; contorni con
  `contourpy`; elenco chiuso delle operazioni H5 con specchiature che
  aggiornano il WCS; soglie A10 per le immagini (1 GB, 4 GB, compressi oltre
  1 GB, anteprima ≤ 4096 pixel); qualità del ricampionamento = copertura di
  `reproject` + percentuale; fattore unico di `rgb_diff`; calibrazione di
  JPEG/PNG solo in lettura; esportazione della vista nel `41`; gli strumenti
  per l'IA di §11 vanno in `32-ia-registro-strumenti.md` (**spostamento
  eseguito il 2026-10-10**: §11 rimanda al 32, elenco annotato in
  `panoramica.md` §4). Applicate in §3, §6–§8, §10, §11, §12.
- **D11-10 — Decisioni del 2026-10-10 dopo il codice (proprietario):**
  confermate le scelte di P1–P7 (righe dal basso, RGB a 2 immagini con B =
  media, `gamma` dopo la funzione di trasferimento, pixel non finiti
  trasparenti, convoluzione con bordo dichiarato, specchiature rifiutate con
  SIP/TPD, operazioni solo sulla stessa griglia); commento contro `.hhh`:
  vale il commento, con l'avviso `HHH_WCS_DIFFERS` se i WCS sono diversi;
  stima della memoria prima delle operazioni sull'immagine intera
  (`MEMORY_LIMIT_EXCEEDED`, limite in D11-11). Applicate in §3, §9, §10,
  §12 (T32, T33).
- **D11-11 — Limite delle operazioni e visualizzazione: DECISA il 2026-10-10
  (decisione del proprietario).** A10 resta la strategia di caricamento; il
  limite delle operazioni è separato, **4 GB di default, configurabile**
  (`operation_bytes`), usato dalla stima di `MEMORY_LIMIT_EXCEEDED`;
  `set_display` si calcola **a blocchi in `float32`** (DC6) senza copia
  intera, così un 6000 × 6000 si visualizza. Criterio commento/`.hhh`
  confermato. Applicata in §3, §7, §9, §10, §12 (T33, T34).

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
| 2026-10-10 | Claude Code | **P4, verifiche:** `matplotlib` 3.11.2 (licenza PSF-like) e `contourpy` 1.4.0 (BSD-3) installati; le palette scelte sono tutte distribuite con la licenza di `matplotlib` (tolta la menzione CC0, non riscontrata nella distribuzione); tutte le funzioni di trasferimento sono in `astropy.visualization`. §3/§7: dettagli di `set_display` (parametro `stretch`, `gamma` come `PowerStretch` dopo la funzione di trasferimento, non finiti trasparenti, immagini a colori) e di `blend` (operatore "over"); §12 T24 precisato, nuovo T31. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P5, verifiche:** normalizzazione = divisione per la media (manuale di Aladin ed. giugno 2022, sez. 5.18, letta solo per la definizione della funzione); `contourpy` 1.4.0 BSD-3; astropy non inverte gli assi di un WCS → specchiature con aggiornamento della parte lineare (Paper I), WCS con distorsioni rifiutati. §3: convoluzione con i default di astropy dichiarati, stessa griglia per le operazioni tra immagini (in Aladin ricampionamento automatico), taglio con `Cutout2D` e intersezione dichiarata, parole chiave di provenienza di `save_fits`; §7 `to_sky` dei contorni. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P6, verifiche e decisioni del proprietario:** astropy 8.0.1 rifiuta il `memmap` con `BZERO`/`BSCALE`/`BLANK` → per quei file non compressi tra 1 e 4 GB due livelli (decisione del proprietario); `section` con `memmap=False` legge le regioni senza caricare il file (verificato su dati semplici, con scala, uint16 e compressi). Immagini a due livelli: anteprima solo per il display, centroide e taglio sui pixel originali per regione, H5/contorni/`save_fits` → `PREVIEW_NOT_MEASURABLE` (decisione del proprietario). §3 regole precise, §7 `LargeImageLimits`, `read_region`, `memory_bytes`. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P7, verifiche e decisioni del proprietario:** `reproject` 0.21.0 verificato (BSD-3, wheel per macOS arm64, dipendenze permissive); RGB con parametri di display espliciti per componente, B = media delle due componenti a 8 bit con 2 immagini; `rgb_diff` con B = 0; metodo di ricampionamento obbligatorio; `reproject` = lista sulla stessa griglia; lunghezze d'onda come parametro opzionale (§3, §7). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Codice completo** in `src/astrotwo/core/images_fits.py` (P1–P7, un commit per parte): tutto il §7, test T1–T31 in `tests/core/test_images_fits.py` superati (progetto: 197 di default, 200 con la rete). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Decisioni del proprietario dopo il codice** (autorizzazione esplicita a modificare il file approvato): confermate le scelte di P1–P7 (D11-10); avviso `HHH_WCS_DIFFERS` quando commento e `.hhh` hanno WCS diversi (criterio: parole chiave normalizzate da `WCS.to_header`); tetto di memoria A10 con stima prima delle operazioni sull'immagine intera e del taglio, errore `MEMORY_LIMIT_EXCEEDED` (tabella delle stime in §3); §11 spostato nel 32 (D11-9); regola d'oro n. 8: tolti i motivi "come Aladin" (§2, ricampionamento esplicito, righe dal basso, mosaico senza correzione del fondo, D11-2, D11-4). Codice e test T32–T33 in `images_fits.py` / `test_images_fits.py`. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **D11-11** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): limite delle operazioni separato da A10, 4 GB di default, configurabile (`LargeImageLimits.operation_bytes`); `set_display` a blocchi di righe in `float32` senza copia intera (eccezione dichiarata: `histeq` raccoglie i valori del piano); stima di `set_display` aggiornata in §3; criterio commento/`.hhh` confermato; test T33 aggiornato, nuovo T34 (6000 × 6000, picco di memoria con `tracemalloc`). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **D14-11** (decisione del proprietario del 2026-10-11, autorizzazione esplicita a modificare il file approvato): parametro facoltativo `calibration` di `load_image` (calibrazione esterna con `header` e `source`, es. `SiaCalibration` del 14), usata solo se l'immagine non ha WCS proprio, con le regole del `.hhh` (dimensioni, WCS celeste valido); avvisi `EXTERNAL_CALIBRATION_USED` e `EXTERNAL_CALIBRATION_IGNORED`, `calibration_source = "external"`, voce nella storia (§3, §7, §10, §12 T35). Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **Decisione del proprietario del 2026-10-13** (autorizzazione esplicita a modificare il file approvato): la lettura del valore grezzo di un pixel (D18-6) passa dal 18 all'11 come funzione pubblica `read_raw_pixel` (§3, §7, §10, T36); il 18 la richiama. Stato `approvato` invariato. |
| 2026-10-15 | Claude Code | **D11-8 decisa dal proprietario il 2026-10-15** (autorizzazione esplicita a modificare il file approvato; solo specifica, nessun codice): raggi della corona del centroide facoltativi con default 1 × e 1,5 × `box_size`, sempre dichiarati; `box_size` iniziale dello strumento del `41` 15 pixel (§3, §7, §13); test T37 (§12). Codice di `star_centroid` da aggiornare. Stato `approvato` invariato. |
| 2026-10-15 | Claude Code | **D41-3 decisa dal proprietario il 2026-10-15** (autorizzazione esplicita a modificare il file approvato; solo specifica, nessun codice): nuova **`suggest_display_limits`** con `ZScaleInterval` di astropy, limiti e parametri dichiarati nel risultato, pixel finiti in `float64`, intervallo comune per i colori, anteprima per le immagini a due livelli (§3, §6, §7, §8); errori `DISPLAY_LIMITS_UNDEFINED`, `DISPLAY_METHOD_UNKNOWN` (§10); test T38–T40 (§12); §13. Stato `approvato` invariato. |
| 2026-10-16 | Claude Code | **Codice scritto** (FASE: CODICE – interfaccia v1, allineamento del livello 1): `suggest_display_limits` con `ZScaleInterval` (parametri di default dichiarati, pixel finiti in `float64`, intervallo comune per i colori, anteprima per i due livelli) e raggi della corona di default 1 × / 1,5 × `box_size` in `star_centroid` (D11-8); test T37–T40 in `tests/core/test_images_fits.py` (118 superati). Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | §13: tolte le frasi superate "codice da scrivere" per le funzioni della v1, scritte il 2026-10-16 (nessun cambiamento di contenuto). Stato `approvato` invariato. |
| 2026-10-24 | Claude Code | **D40-3, sprint 8b:** §10 — nuova sezione "Parametri dei messaggi" con codice, `reason` e `params` di ogni errore e avviso; il codice li restituisce (testo italiano invariato); le traduzioni sono nel catalogo del `40`. Nessun comportamento scientifico cambia. |
| 2026-10-24 | Claude Code | **D40-7, sprint 8c-bis:** §10 — `cause` di `WCS_MISSING` resta esterno finché il 14 non è convertito; nessun codice cambia. |
