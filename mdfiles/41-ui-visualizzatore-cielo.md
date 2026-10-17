# 41-ui-visualizzatore-cielo.md — visualizzatore del cielo

**Stato:** approvato

## 2. Scopo

Mostrare il cielo — immagine FITS, sfondo HiPS, cataloghi, MOC, griglia e
misure — con spostamento e zoom fluidi anche con un milione di sorgenti,
disegnando soltanto posizioni e valori calcolati dai moduli del livello 1.

## 3. Cosa fa

### 3.1 Perimetro della prima versione (v1)

Perimetro approvato dal proprietario il 2026-10-15.

- **In v1:** immagine FITS con `set_display` dell'11 (funzione di
  trasferimento, palette, limiti, gamma); sfondo HiPS (12); spostamento e
  zoom con mouse e trackpad (A1); coordinate e valore del pixel sotto il
  mouse (A4); griglia con `compute_grid_lines` e `choose_grid_spacing` del
  10 (A6); cataloghi sovrapposti con `display_positions` e `set_plot_rules`
  del 13; clic su una sorgente per vederne i dati (D11, solo clic);
  misura della distanza (17, H11) con aggancio facoltativo al centroide
  dell'11; MOC sovrapposti (16, E6); puntatore Simbad (H17, `simbad_pointer`
  del 14); pannello dei livelli minimo (A11: ordine, visibilità, opacità,
  rimozione); esportazione della vista in PNG (A13, solo PNG);
  **indicatore del nord e barra di scala (A7, dal 2026-10-16**, con
  `compass_and_scale_bar` del 10, §3.18).
- **Fuori dalla v1:** rotazione
  (A8), minimappa (G4), campi strumentali (G5), file di regione (E7),
  albero delle collezioni (H1), cursore dell'epoca (H3), tag e segnalibri,
  mappa cliccabile (H20), frecce del moto proprio (D10), selezione a
  rettangolo (D11), puntatore fotometrico VizieR (H17), più immagini FITS
  sovrapposte e ricampionate (B5, B7: nella v1 una sola immagine FITS alla
  volta, scelta minore 1), altri formati di esportazione e stampa (A13),
  rinomina dei livelli (A11).

**Divisione del codice in sprint (2026-10-17).** **4a (scritto il
2026-10-17):** sfondo HiPS di un survey a colori (JPEG/PNG; un survey FITS
dà l'avviso `HIPS_FITS_NOT_YET` finché non arriva il 4b), zoom (rotella del
mouse 2^(1/4) per scatto, pizzico del trackpad) e spostamento
(trascinamento, due dita sul trackpad) come `view.set_zoom`/`view.set_center`
a fine gesto, scritta "survey · proiezione · campo" nella barra del `40`,
modalità notte nel disegno. **Scelte del proprietario del 2026-10-17:**
vista iniziale a cielo intero (centro ICRS 0°, 0°; scala = 360° / larghezza
della finestra in pixel fisici, prima lo zoom), limiti della scala da
0.01″/pixel a 360° / larghezza, campo nella barra = `field_of_view` dei
comandi di vista del `05` (2 × `field_radius` del 10) in ° con 2 decimali da
1°, in ′ sotto 1°, in ″ sotto 1′. Una nuova dimensione del cielo registra
`view.set_center` con la nuova finestra a fine gesto. **Sprint successivi:**
4b tile FITS con `set_display` e coordinate sotto il mouse (`cursor.read`);
4c griglia e nord/barra di scala; 4d immagine FITS (base del suo WCS); 4e
cataloghi e clic su una sorgente; 4f MOC, corpi diversi e pannello dei
livelli; 4g distanza e puntatore Simbad; 4h PNG, cambio di base in un passo
(T17) e prestazioni (`perf`).

### 3.2 Geometria della vista: base e finestra

Nessuna proiezione è calcolata qui: tutta la geometria viene dal 10
(`make_view_wcs`, aggiunto al 10 il 2026-10-15) e dal 12 (campionamento
dei tile sulla vista, aggiunto al 12 il 2026-10-15).

- **Base:** il piano su cui si calcolano una volta le posizioni dei
  livelli.
  - **Con un'immagine FITS aperta** la base è il **WCS dell'immagine**
    (griglia dei pixel del file, senza ricampionare i pixel
    dell'immagine; orientamento del file).
  - **Senza immagine** la base è un WCS del cielo creato da
    `make_view_wcs` del 10 con punto di tangenza, proiezione (`TAN` o
    `AIT` da `choose_projection`, §3.3) e frame ICRS.
- **Finestra:** la parte della base visibile, a una scala data.
  `make_view_wcs` restituisce una `ViewGeometry` con il centro, la scala,
  le dimensioni della finestra in pixel fisici, il **fattore di scala e lo
  spostamento** tra pixel della base e pixel della finestra, le funzioni
  finestra ↔ cielo (esatte anche con le distorsioni del WCS
  dell'immagine), il WCS della regione visibile per la griglia e il
  **raggio del campo** (usato per i tile, per `choose_projection` e per il
  catalogo nel campo).
- **Ogni comando di vista** (`view.set_center`, `view.set_zoom`,
  `view.go_to`) chiama `make_view_wcs` con la base corrente: la nuova
  finestra è esatta e deterministica, ricostruibile dalla cronologia.
- **Ricentramento della base senza immagine (scelta minore 2):** la base
  si ricrea con un nuovo punto di tangenza (il centro della finestra)
  quando il punto di tangenza esce dalla finestra, o quando cambia la
  proiezione (§3.3).
- **Cambio di base in un passo:** la vista continua a mostrare la base
  vecchia finché per la nuova non sono pronte posizioni dei cataloghi,
  griglia, MOC e campionamento dei tile; poi passa alla nuova tutta
  insieme. I valori dei tile arrivano poi a mano a mano.

### 3.3 Scelta della proiezione (D10-9, decisa il 2026-10-15)

- `choose_projection` del 10 con **soglia di 30°** sul campo di vista
  (diametro del cerchio che contiene la finestra, dal raggio del campo di
  `ViewGeometry`): `TAN` sotto, `AIT` da 30° in su.
- **Scarto di ±10 % gestito qui**, per evitare cambi continui vicino alla
  soglia: con la vista in `TAN` si passa ad `AIT` quando il campo
  raggiunge **33°**; con la vista in `AIT` si torna a `TAN` quando il campo
  scende sotto **27°**. Il 41 passa a `choose_projection` la soglia 33° o
  27° secondo la proiezione corrente: sono valori fissi dichiarati, non
  calcoli.
- Con un'immagine aperta la proiezione è quella dell'immagine e non
  cambia (riga A9 di `03-parita-aladin.md`: per le immagini classiche
  cambia solo il sistema di riferimento).

### 3.4 Trasformazioni di disegno

**Traslazione e scala dello schermo sono disegno, non numeri mostrati**
(decisione del proprietario del 2026-10-15). Il visualizzatore porta sullo
schermo posizioni già calcolate dal 10 nei pixel della base, applicando
solo la traslazione e la scala date da `ViewGeometry` (e, durante un
gesto, quelle del gesto in corso). Nessun numero mostrato all'utente
nasce da queste trasformazioni:

- **durante un gesto** (spostamento o zoom) la vista è il piano della base
  traslato e scalato: il disegno è fedele alla base e le coordinate sotto
  il cursore restano esatte, perché il punto dello schermo si riporta in
  pixel della base con la stessa traslazione e scala e il cielo lo dà
  `pixel_to_sky` del 10;
- **a fine gesto** (300 ms fermo, §3.3 del `05`) si registrano
  `view.set_zoom`/`view.set_center`; il comando produce la nuova
  `ViewGeometry` dal 10 e la vista si ridisegna con quella;
- il **fattore di zoom del gesto** (rotella, trackpad) è un dato in
  ingresso scelto dall'utente con la mano, come un numero scritto in un
  campo: la scala che ne risulta è un parametro del comando, non un
  risultato.

**Zoom scopribile e rotella di macOS (decisione del proprietario del
2026-10-17, dopo la prova sul suo Mac):** (a) la rotella del mouse su macOS
non dà 120 per scatto ma valori proporzionali alla velocità: ogni evento
vale almeno uno scatto (2^(1/4)); (b) due pulsanti **+** e **−** in
sovrimpressione nell'angolo in alto a destra del cielo e le voci **Zoom in**
(⌘+) e **Zoom out** (⌘−) del menu View: zoom di ×2 / ÷2 attorno al centro
della finestra, come un gesto (stesso ritardo di 300 ms, poi
`view.set_zoom` e `view.set_center`), entro gli stessi limiti di scala; (c)
dopo un `view.go_to` riuscito, se il campo della vista è maggiore di 1,25°, la
vista si porta a un campo di circa 1° con un `view.set_zoom` registrato
(`requested_by` = `keyboard`), così lo spostamento si vede; se è già
minore, resta com'è (il campo ottenuto è solo vicino a 1°: la proiezione può cambiare). Il `05` e il suo `view.go_to` non cambiano (il
comando centra soltanto).

### 3.5 Livelli

- **Tipi nella v1:** un'immagine FITS (al più una alla volta: aprirne una
  seconda chiede di sostituire la prima), uno sfondo HiPS (il survey
  attivo), cataloghi (quanti se ne vuole, entro il tetto di 1 milione di
  righe per tabella del 13), MOC, misure.
- **Pannello dei livelli (A11, minimo):** elenco con ordine (trascinamento,
  `layer.move`), visibilità (`layer.set_visible`), opacità
  (`layer.set_opacity`, in [0, 1]) e rimozione (`layer.remove`). Per ogni
  livello: nome, sorgente (file o servizio con origine e data), corpo,
  epoca usata per il disegno e conteggi del modulo (es. righe non
  disegnabili).
- **Corpi diversi (D19-4):** prima di sovrapporre un livello si chiama
  `check_overlay` del 19; corpi diversi (o dati celesti e planetari) →
  errore `BODY_MISMATCH` del 19; la finestra d'errore offre la forzatura
  esplicita, che diventa un parametro del comando (`force_body`) citato nel
  risultato e nel pannello dei livelli.
- **Immagine senza WCS** (`WCS_MISSING` dell'11/10): si apre come griglia
  di pixel; finché è aperta non si sovrappongono HiPS, cataloghi o MOC
  (`VIEW_NO_WCS`) e si mostrano solo le coordinate pixel.

### 3.6 Immagine FITS

- Il disegno usa il piano di presentazione di `set_display` dell'11
  (valori `float32` e colori RGBA a 8 bit) come texture sulla GPU, in più
  texture se l'immagine supera la dimensione massima della GPU.
- **Regolazioni:** una barra con vmin, vmax, funzione di trasferimento,
  palette e gamma → `image.set_display`. **Limiti iniziali (D41-3, decisa
  il 2026-10-15):** `suggest_display_limits` dell'11 con `ZScaleInterval` di
  astropy; i limiti scelti, il metodo e i suoi parametri sono dichiarati nel
  risultato di `image.open` e registrati nel comando, così la riapertura
  della sessione dà la stessa visualizzazione.
- **Immagini a due livelli** (anteprima dell'11 per le immagini enormi):
  si disegna l'anteprima con la dichiarazione dell'11 nel pannello dei
  livelli; le letture sotto il cursore seguono le regole dell'11
  (`PREVIEW_NOT_MEASURABLE` dove previsto).

### 3.7 Sfondo HiPS

- Per ogni finestra il 12 dà il **campionamento della vista**: ordine
  scelto con `order_for_resolution` alla scala della finestra in pixel
  fisici, tile necessari e, per ogni pixel della finestra, tile e pixel del
  tile che lo contengono (nuova funzione del 12, P6). I tile si chiedono
  con `fetch_tile` del 12 (memoria entro 512 MB, poi cache del 04, poi
  rete) nel **gruppo di thread dei tile** (§3.13) e ciascuno, appena
  arriva, riempie i suoi pixel della finestra (funzione del 12).
- **Tile FITS:** valori portati a colori con `set_display` dell'11; limiti
  iniziali da `hips_pixel_cut` del servizio se dichiarato, altrimenti
  `suggest_display_limits` dell'11 (D41-3) sui valori del **tile che
  contiene il centro della prima vista** del survey (scelta fissa, così il
  risultato non dipende dall'ordine di arrivo dei tile), dichiarati nel
  risultato di `hips.set_survey`. **Tile JPEG o PNG:** colori del tile.
- Un cambio di finestra **annulla le richieste di tile non più
  necessarie** (annullamento cooperativo: i risultati si scartano).
- Tile mancanti o scartati (`HIPS_TILE_MISSING`, `HIPS_BAD_TILE` del 12):
  zona vuota; un solo messaggio per survey nel pannello Messaggi, non uno
  per tile.

### 3.8 Cataloghi

- **Posizioni:** `display_positions` del 13 all'epoca di visualizzazione
  (D10-2: epoca dell'immagine se nota, altrimenti J2000), poi
  `sky_to_pixel` del 10 sulla base, **una volta per base**; durante
  spostamento e zoom cambiano solo traslazione e scala (§3.4).
- **Righe non disegnabili** (moto proprio mancante, D13-12): non si
  disegnano; il conteggio del 13 compare nel pannello dei livelli.
- **Catalogo senza colonne di moto proprio** (scelta minore 3): si
  disegnano le posizioni della tabella, con l'epoca del catalogo dichiarata
  e la nota "non propagato" nel pannello dei livelli.
- **Colonne di moto proprio e parallasse:** scelte dall'utente nel
  dialogo del `42` (`catalog.set_columns`); senza scelta vale la scelta
  minore 3.
- **Simboli:** `set_plot_rules` del 13 con una regola per catalogo
  (`catalog.set_style`): forma dell'elenco del 13, colore da una tavolozza
  fissa assegnata in ordine di apertura, dimensione in pixel logici
  (scelta minore 4). L'editor delle regole è fuori dalla v1.
- **Clic su una sorgente:** si sceglie il simbolo disegnato più vicino al
  clic entro la sua dimensione o, se più grande, entro 4 pixel logici
  (scelta minore 5), con un indice spaziale delle posizioni sullo schermo
  (`scipy.spatial.cKDTree`): è una scelta sullo schermo, non un numero
  mostrato. Ne nasce `catalog.select`; la riga si evidenzia nel `42`, che
  mostra il record con `record_view` del 13. Selezioni fatte nel `42` si
  evidenziano qui (D7).
- **Catalogo nel campo** (menu Data del `40`): centro e raggio della
  finestra da `ViewGeometry` del 10.

### 3.9 MOC

- Celle e contorni da `healpix_grid(order, within=moc)` del 16, portati in
  pixel della base con `sky_to_pixel` del 10; disegnati come poligoni
  pieni con l'opacità del livello e il contorno.
- **Ordine del disegno (scelta minore 6):** l'ordine del MOC se le celle
  non superano il tetto del 16 (`GRID_MAX_CELLS`, 196 608); altrimenti
  l'ordine più alto sotto il tetto, con la dichiarazione "disegnato
  all'ordine k, per eccesso" nel pannello dei livelli (le celle a ordine
  più basso che toccano il MOC lo contengono).

### 3.10 Griglia (A6)

`compute_grid_lines` del 10 sul WCS della regione visibile data da
`ViewGeometry`, con il passo scelto da `choose_grid_spacing` (5 linee per
asse, elenchi del 10), nel frame scelto (ICRS o galattico); ricalcolata a
ogni comando di vista. Le etichette usano il valore della coordinata
restituito dal 10, scritto con `format_coordinates` del 10 (D41-2) con
la precisione uguale al passo della griglia (es. passo di 10′ → gradi e
primi, senza secondi).

### 3.11 Coordinate e valore sotto il mouse (A4)

- A ogni movimento del mouse una lettura passiva `cursor.read` (D05-1),
  al più una in corso (vale l'ultima posizione): pixel della base dal
  punto dello schermo (§3.4); cielo con `pixel_to_sky` del 10 nel sistema
  scelto; coordinate pixel in convenzione FITS con
  `convert_pixel_convention` del 10 (DC7); valore con `read_pixel` del 17
  sull'immagine, altrimenti con `pixel_values` del 12 sui tile FITS del
  survey; nessun valore per i survey a colori (`HIPS_PIXEL_UNAVAILABLE`).
- Fuori dalla proiezione (bordo dell'`AIT`): "fuori dal cielo".
- Il risultato va nella barra di stato del `40`; il formato dei numeri
  è quello di `format_coordinates` del 10 con le cifre di DC3 (D41-2).

### 3.12 Strumenti

- **Misura della distanza (F1, H11):** trascinamento da p1 a p2 (o due
  clic) → `measure.distance`: cielo dai pixel con `pixel_to_sky` del 10,
  distanza con `angular_distance` del 17 nell'unità scelta nelle opzioni
  dello strumento (″, ′ o °; default ′, scelta minore 7). **Aggancio al
  centroide** (facoltativo, solo su un'immagine): ogni punto passa prima da
  `star_centroid` dell'11 con **`box_size` iniziale 15 pixel**, modificabile
  nelle opzioni e dichiarato nel risultato, e con la **corona di default
  dell'11** (raggio interno 1 × `box_size`, esterno 1,5 × `box_size`;
  D11-8, decisa il 2026-10-15). Errori del centroide (`CENTROID_OUT_OF_IMAGE`,
  `CENTROID_UNDEFINED`): nessuna misura, messaggio dell'11. La misura si
  disegna come segmento con etichetta in un livello "Measures" rimovibile.
- **Puntatore Simbad (H17):** con lo strumento attivo, quando il mouse
  resta fermo **500 ms** parte una lettura passiva `simbad.pointer`
  (D05-1) con raggio **12 pixel logici convertiti in angolo**: centro e
  punto a 12 pixel logici (moltiplicati per il rapporto dei pixel fisici
  dello schermo) portati in cielo con `pixel_to_sky` del 10, distanza con
  `angular_distance` del 17. **Una sola richiesta alla volta**: un nuovo
  arresto durante una richiesta aspetta e poi parte solo l'ultimo. Esito
  in un riquadro vicino al cursore: identificatore, tipo, coordinate,
  magnitudini con banda e sistema, numero di citazioni (dal 14), con il
  collegamento alla pagina SIMBAD; nessun oggetto → testo del 14. Dove si
  esegue: nel **gruppo di thread dei tile**, come comando `passive`
  (D41-1, decisa il 2026-10-15).

### 3.13 Rendering e thread

- **Interfaccia di disegno nostra** (`SkyRenderer`), con
  un'implementazione **OpenGL su `QOpenGLWidget`** (OpenGL 4.1 core
  profile, il massimo su macOS): immagine e tile come texture, cataloghi
  come punti in buffer della GPU (posizioni nei pixel della base, `float32`
  solo per il disegno, DC6), MOC e griglia come linee e poligoni;
  traslazione e scala come una matrice sulla GPU. Testi (etichette della
  griglia, misure) con `QPainter` sullo stesso widget. Il resto del
  visualizzatore usa solo l'interfaccia, così un futuro passaggio a
  **QRhi** (Metal) non tocca il resto (decisione del proprietario del
  2026-10-15).
- **Funzioni OpenGL:** prima quelle incluse in PySide6
  (`QOpenGLFunctions`, `QOpenGLExtraFunctions`, `QOpenGLShaderProgram`,
  `QOpenGLBuffer`, `QOpenGLTexture`, `QOpenGLVertexArrayObject`);
  **PyOpenGL solo se non bastano**, con licenza verificata. **Da
  verificare prima del codice:** che le funzioni di PySide6 coprano punti
  con dimensione dal programma di disegno, oggetti dei vertici, buffer e
  texture `float32`.
- **Retina:** si disegna in pixel fisici (rapporto dei pixel dello
  schermo); dimensioni dei simboli e tolleranze in pixel logici.
- **Temi e modalità notte** (linee guida visive, `40` §3.11): colori di
  griglia, simboli ed etichette dal tema; in **modalità notte rossa** il
  renderer porta ogni colore disegnato (anche il piano dell'immagine e dei
  tile) sulla sua luminosità in una scala di rossi: è una trasformazione
  di disegno, i valori e i risultati non cambiano; i cataloghi si
  distinguono per forma del simbolo. I colori dei cataloghi nei temi
  normali sono la tavolozza di Okabe e Ito (scelta minore 4).
- **Thread** (architettura approvata il 2026-10-15): i comandi passano
  dalla coda del `40`; i **tile HiPS** (richiesta e riempimento) girano in
  un **gruppo di thread separato** (`QThreadPool`, 6 thread: scelta minore
  8); i risultati tornano con i segnali di Qt; nessun calcolo nel thread
  principale oltre alle letture passive senza rete.
- **Da verificare prima del codice (richiesta del proprietario del
  2026-10-15):** la cache del 04 (SQLite) deve reggere l'accesso da più
  thread (thread dei comandi e gruppo di thread dei tile); verifica e test
  descritti nel `05` §3.2 (T17).

### 3.14 Esportazione della vista in PNG (A13)

`view.export_png`: la vista corrente disegnata fuori schermo in pixel
fisici e scritta in PNG con metadati testuali (versione dell'app, centro,
scala, proiezione, livelli con sorgente, origine e data, data
dell'esportazione). È un'immagine per l'occhio: i valori dei pixel del PNG
non sono dati scientifici. Altri formati e stampa: fuori dalla v1.

Nel PNG si disegnano anche l'indicatore del nord e la barra di scala
(§3.18), come sullo schermo.

### 3.15 Obiettivi di prestazione (approvati il 2026-10-15)

Misurati sul **Mac di riferimento** con test marcati `perf` (D41-4):

| Mac di riferimento | Valore |
|---|---|
| Modello | **da compilare** (lo indica il proprietario) |
| Processore | **da compilare** |
| Memoria | **da compilare** |
| Versione di macOS | **da compilare** |
| Schermo (rapporto dei pixel) | **da compilare** |



| # | Obiettivo | Condizioni |
|---|---|---|
| P1 | spostamento e zoom ≤ **16,7 ms per fotogramma al 95° percentile** | immagine 4096 × 4096, sfondo HiPS, **1 milione di sorgenti** |
| P2 | memoria aggiuntiva per il milione di sorgenti ≤ **1 GB** | catalogo di 1 milione di righe disegnato (obiettivo minimo di `01` §8) |
| P3 | thread principale **mai fermo più di 100 ms** durante rete o calcoli | sonda di latenza (timer di Qt) durante comandi lunghi e tile |
| P4 | coordinate sotto il mouse aggiornate **entro 50 ms** | movimento del mouse su immagine e su HiPS |
| P5 | finestra pronta in **≤ 3 s senza rete** | avvio a freddo dell'app |
| P6 | primi tile HiPS visibili in **≤ 2 s con la cache calda** | survey di default, tile già in cache |
| P7 | proiezione del milione di sorgenti con `sky_to_pixel` del 10 | **valore da misurare prima di fissarlo** (nessun obiettivo scritto finché non è misurato) |

**Regola del proprietario (2026-10-15):** se un obiettivo non si
raggiunge, **si misura e si riporta** (valore ottenuto, condizioni, causa
se nota); **mai abbassarlo in silenzio**: un obiettivo cambia solo con una
decisione del proprietario.

### 3.16 Lista di controllo manuale

Da eseguire a mano prima di ogni rilascio dell'interfaccia (approvata il
2026-10-15): aspetto e leggibilità di simboli, griglia ed etichette;
schermo Retina e schermo normale; gesti del trackpad (spostamento a due
dita, pinza, rotella del mouse); reti reali (survey e cataloghi veri,
rete lenta e assente); revisione della traduzione italiana; accessibilità
di base (navigazione da tastiera, contrasto, testo ingrandito di macOS).

### 3.17 Righe di parità coperte

A1, A2/A3 (con il campo "Vai a" del `40`), A4, A6, A11 (minimo), A13 (solo
PNG), B5 (opacità di immagine e HiPS), C1 (survey attivo), D11 (solo
clic), E6 (MOC sovrapposti), F1 e H11 (distanza), H17 (solo puntatore
Simbad), **A7** (nord e barra di scala, dal 2026-10-16). Le altre righe
assegnate al 41 sono fuori dalla v1 (§3.1).

### 3.18 Indicatore del nord e barra di scala (A7)

Decisione del proprietario del 2026-10-16 (A7 nella v1, opzione b della
proposta della fase 1 sull'IA): **tutto il calcolo è del 10**, con la nuova
funzione `compass_and_scale_bar`; qui solo il disegno.

- **Dove:** nell'**angolo in basso a sinistra** della vista (scelta minore
  10), sopra i livelli e sotto le etichette degli strumenti; nessuna
  interazione.
- **Quando:** ricalcolato a **ogni comando di vista** (`view.set_center`,
  `view.set_zoom`, `view.go_to`, cambio di base) chiamando
  `compass_and_scale_bar` del 10 sulla `ViewGeometry` corrente, nel frame
  della griglia se è visibile, altrimenti ICRS; durante un gesto resta
  quello dell'ultimo comando di vista, in grigio, e si ricalcola alla fine
  del gesto (nessun valore stimato durante il gesto).
- **Nord ed est:** due frecce dal **centro della vista** (dove il 10 li
  calcola) disegnate nell'angolo con le direzioni restituite dal 10
  (vettori unitari in pixel della finestra) ed etichette "N" ed "E"; la
  lunghezza delle frecce (40 pixel logici, scelta minore 11) è solo
  disegno. Vicino al polo il 10 restituisce `NORTH_UNDEFINED`: al posto
  delle frecce la scritta "polo nel campo".
- **Barra di scala:** segmento orizzontale lungo quanti pixel della
  finestra dice il 10, con l'etichetta scritta dal 10 (es. "10′"); la barra
  vale al centro della vista: con proiezione `AIT` o campo oltre 30° il 10
  lo dichiara e l'etichetta aggiunge "al centro".
- **Disegno:** colori del tema (in modalità notte rossa solo rossi), cifre
  tabulari; nessun numero calcolato qui.

## 4. Cosa NON fa

- Non calcola proiezioni, coordinate, distanze, valori, epoche né scale da
  mostrare: tutto viene dal 10, 11, 12, 13, 14, 16, 17 (regola d'oro n. 1,
  `01` §3, D17-2: geometria nel 17, disegno qui).
- Non ricampiona l'immagine FITS sulla vista e non mescola più immagini
  (B5, B7 fuori dalla v1).
- Non ruota la vista (A8) e non calcola direzione del nord né lunghezza
  della barra di scala (10, `compass_and_scale_bar`).
- Non registra ogni movimento del mouse (gesti a fine gesto, `05` §3.3).
- Non salva la sessione né gestisce la coda dei comandi (`05`, `40`).
- Non mostra tabelle (`42`).
- Non ha un ripiego senza OpenGL nella v1.

## 5. Livello e dipendenze

- **Livello:** interfaccia; nella v1 usa solo il livello 1.
- **Dipende da:** `05-comandi-sessione.md`; `10-core-coordinate-wcs.md`
  (`make_view_wcs`, `choose_projection`, `pixel_to_sky`, `sky_to_pixel`,
  `convert_pixel_convention`, `format_coordinates`, `compass_and_scale_bar`,
  griglia),
  `11-core-immagini-fits.md` (`set_display`, `suggest_display_limits`,
  `star_centroid`), `12-core-hips.md` (survey, tile,
  campionamento della vista, valori dei pixel), `13-core-cataloghi.md`
  (`display_positions`, `set_plot_rules`, `record_view`),
  `14-core-protocolli-vo.md` (`simbad_pointer`), `16-core-moc.md`
  (`healpix_grid`), `17-core-misure.md` (`angular_distance`, `read_pixel`),
  `19-core-dati-planetari.md` (`check_overlay`),
  `40-ui-finestra-principale.md` (finestra, coda, barra di stato);
  PySide6 (QtOpenGL, QtOpenGLWidgets), `numpy`, `scipy`.
- **Usato da:** `40-ui-finestra-principale.md`, `42-ui-pannello-cataloghi.md`
  (selezione sincronizzata); in futuro `45-ui-viste-multiple.md`.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | gesti e clic | eventi di Qt | pixel logici dello schermo | diventano comandi del `05` |
| in | `ViewGeometry` | struttura del 10 | base, finestra, fattore e spostamento, raggio del campo in gradi | per ogni comando di vista |
| in | piano di presentazione | `float32` + RGBA a 8 bit | dall'11 | solo disegno |
| in | posizioni dei livelli | pixel della base, convenzione numpy | dal 10 su posizioni del 13/16 | una volta per base |
| in | campionamento e tile | strutture del 12 | tile, pixel, valori nativi | gruppo di thread dei tile |
| out | comandi | `Command` del `05` | parametri con unità | §3 |
| out | lettura sotto il cursore | `CommandResult` passivo | coordinate con frame ed epoca, valore con unità, pixel FITS | barra di stato del `40` |
| out | PNG della vista | file PNG | pixel fisici, metadati testuali | `view.export_png` |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole. File Python
`src/astrotwo/ui/sky_viewer.py` (visualizzatore, livelli, strumenti) e
`src/astrotwo/ui/sky_renderer_gl.py` (implementazione OpenGL
dell'interfaccia di disegno; scelta minore 9); test in
`tests/ui/test_sky_viewer.py`.

- **`SkyViewer`** — widget del visualizzatore: tiene la `ViewGeometry`
  corrente, traduce i gesti in comandi (timer dei 300 ms), coordina livelli
  e strumenti.
- **`SkyRenderer`** (interfaccia di disegno) — `set_base`, `set_transform`
  (traslazione e scala), `upload_texture`, `upload_points`,
  `upload_polygons`, `upload_lines`, `draw_labels`, `render`,
  `render_offscreen` (per i test e per il PNG), `drawn_positions` (posizioni
  sullo schermo dei simboli disegnati, per i test).
- **`GlSkyRenderer`** — implementazione su `QOpenGLWidget`.
- **`LayerPanel`** — pannello dei livelli (A11 minimo).
- **`TilePool`** — gruppo di thread dei tile, con annullamento delle
  richieste superate.
- **`DistanceTool`**, **`SimbadPointerTool`** — strumenti di §3.12.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| PySide6: `QOpenGLWidget`, `QOpenGLFunctions`, `QOpenGLExtraFunctions`, `QOpenGLShaderProgram`, `QOpenGLBuffer`, `QOpenGLTexture`, `QOpenGLVertexArrayObject`, `QPainter`, `QThreadPool` | disegno e thread | A1; funzioni incluse in PySide6 per non aggiungere licenze (decisione del proprietario del 2026-10-15); licenza di PySide6/Qt da verificare (`40` §8) |
| OpenGL 4.1 core profile | disegno sulla GPU | versione massima disponibile su macOS; OpenGL è deprecato da Apple ma funziona: per questo l'interfaccia di disegno è nostra (passaggio futuro a QRhi) |
| PyOpenGL | **solo se** le funzioni di PySide6 non bastano | licenza da verificare prima di usarlo |
| `numpy` | buffer dei vertici (`float32` solo per il disegno) | già dipendenza |
| `scipy.spatial.cKDTree` | scelta del simbolo cliccato sullo schermo | già dipendenza; consolidato |
| PNG (ISO/IEC 15948) con blocchi `tEXt` | esportazione della vista | formato standard con metadati testuali |
| **pytest-qt** | test (piattaforma `offscreen`) | decisione del proprietario del 2026-10-15; licenza da verificare (`40` §8) |

## 9. Regole e vincoli

- **Il visualizzatore non calcola numeri da mostrare**: proiezioni,
  coordinate, valori, distanze ed epoche vengono dai moduli; traslazione e
  scala dello schermo sono solo disegno (§3.4).
- **Disegno entro 1 pixel** dalle posizioni calcolate dal 10 (a vista
  ferma, dopo il comando di vista); controllato dai test (§12), senza
  confronti di immagini intere.
- **Epoca dichiarata** per ogni livello disegnato (D10-2): epoca di
  visualizzazione e sua fonte dal 13.
- **Corpi diversi** solo con forzatura esplicita citata (D19-4).
- **`float64`** in ogni calcolo dei moduli; `float32` solo nei buffer di
  disegno (DC6).
- **Prestazioni:** §3.15, con la regola "misurare e riportare, mai abbassare
  in silenzio".
- **Ogni azione è un comando** (`05`); le letture del cursore e del
  puntatore Simbad sono passive (D05-1).
- **Punto decimale** e cifre DC3 nei numeri mostrati (`40` §3.9).

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| OpenGL 4.1 non disponibile | messaggio all'avvio, visualizzatore non disponibile (nessun ripiego nella v1) | `GL_UNAVAILABLE` |
| Immagine più grande della texture massima della GPU | divisa in più texture | — |
| Immagine senza WCS | griglia di pixel; niente HiPS, cataloghi o MOC sovrapposti | `VIEW_NO_WCS` |
| Corpi diversi tra livelli | errore del 19, forzatura esplicita possibile | `BODY_MISMATCH` |
| Tile mancante o corrotto | zona vuota, un messaggio per survey | `HIPS_TILE_MISSING`, `HIPS_BAD_TILE` |
| Rete assente | tile e cataloghi dalla cache se ci sono, dichiarati; altrimenti errore del modulo | `NET_TIMEOUT` |
| Cursore fuori dalla proiezione | "fuori dal cielo", nessun valore | — |
| Valore del pixel su survey a colori | nessun valore, testo del 12 | `HIPS_PIXEL_UNAVAILABLE` |
| Epoca dell'immagine non dichiarata | cataloghi a J2000 con la fonte del 13 | — |
| Catalogo con righe senza moto proprio | righe non disegnate, conteggio nel pannello dei livelli | — |
| Simbad senza oggetti nel raggio | testo del 14 nel riquadro | codice del 14 |
| Centroide non calcolabile | nessuna misura, messaggio dell'11 | `CENTROID_OUT_OF_IMAGE`, `CENTROID_UNDEFINED` |
| Seconda immagine FITS aperta | richiesta di sostituire la prima | — |
| MOC troppo fine per il disegno | ordine ridotto dichiarato "per eccesso" | — |

## 11. Esposizione all'IA

Non applicabile: è interfaccia. I comandi che usa (vista, livelli, misure)
sono del `05` e potranno essere esposti dal `32`.

## 12. Test di accettazione

Con **pytest-qt** e piattaforma `offscreen`; servizi e tile simulati.
Marcatori: `gl` per i test che richiedono la GPU, `perf` per le
prestazioni (§3.15). **Regola (D41-4, decisa il 2026-10-15):** `perf` e
`gl` sono **esclusi dai test di default** (come `network`) e si eseguono a
parte; **un test `gl` che fallisce blocca il commit** quando è eseguito;
**i test `perf` si riportano** (valori ottenuti nel messaggio di commit e
nella panoramica), senza bloccare, secondo la regola "misurare e riportare,
mai abbassare in silenzio".

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Disegno dei cataloghi entro 1 pixel | catalogo sintetico di 1000 sorgenti su base `TAN`, poi `AIT`, poi su un'immagine con distorsioni SIP; varie scale e spostamenti | posizioni disegnate (`drawn_positions`) entro 1 pixel da `sky_to_pixel` del 10 composto con fattore e spostamento di `ViewGeometry` | ricalcolo nel test con il 10 |
| T2 | Disegno sulla GPU (`gl`) | 50 sorgenti isolate, ciascuna con un colore diverso, disegnate fuori schermo | centro di ogni macchia di colore entro 1 pixel dalla posizione attesa | lettura dell'immagine fuori schermo, solo attorno alle sorgenti |
| T3 | Griglia e MOC entro 1 pixel | griglia ICRS e MOC sintetico | vertici disegnati entro 1 pixel dai punti del 10 e del 16 | ricalcolo nel test |
| T4 | Sfondo HiPS | survey FITS simulato; vista ferma | ogni pixel della finestra uguale al valore del pixel HiPS che contiene il suo centro (`pixel_values` del 12); nessuna fascia vuota tra tile adiacenti | ricalcolo con il 12 |
| T5 | Gesti → comandi | trascinamento e rotella con orologio simulato | nessun comando durante il gesto; dopo 300 ms fermi un `view.set_center` e/o `view.set_zoom` (prima lo zoom) con lo stato finale | ispezione della cronologia |
| T6 | Riesecuzione della vista | rieseguire la cronologia di T5 in una nuova finestra | stessa `ViewGeometry` (centro, scala, proiezione, base) | confronto |
| T7 | Isteresi della proiezione | zoom indietro e avanti attorno a 30° | `TAN` → `AIT` a 33°, `AIT` → `TAN` sotto 27°, mai cambi tra 27° e 33° | test |
| T8 | Coordinate sotto il cursore | punti dello schermo anche durante un gesto | coordinate uguali a `pixel_to_sky` del 10 sul pixel della base; pixel FITS da `convert_pixel_convention`; aggiornamento ≤ 50 ms (`perf`) | ricalcolo con il 10 |
| T9 | Puntatore Simbad | mouse fermo 500 ms con rapporto dei pixel 1 e 2; secondo arresto durante una richiesta | una richiesta con raggio uguale all'angolo calcolato nel test con il 10 e il 17 per 12 pixel logici; mai due richieste insieme | servizio simulato |
| T10 | Distanza con aggancio | immagine con due stelle gaussiane sintetiche; clic vicino ai centri | punti = `star_centroid` dell'11 con `box_size` 15 e corona di default (15 e 22,5 pixel) dichiarati; distanza = `angular_distance` del 17 | ricalcolo con 11 e 17 |
| T11 | Interfaccia reattiva | tile simulati lenti (2 s ciascuno) e catalogo lento | sonda del thread principale < 100 ms | sonda di latenza |
| T12 | Annullamento dei tile | spostare la vista mentre i tile arrivano | richieste superate annullate, nessun tile vecchio disegnato sulla nuova finestra | ispezione |
| T13 | Corpi diversi | aprire un MOC marziano su un'immagine celeste | `BODY_MISMATCH`; con la forzatura, livello aperto e forzatura citata | test |
| T14 | PNG della vista | `view.export_png` | PNG con dimensioni in pixel fisici e metadati testuali attesi | lettura del file con Pillow |
| T15 | Livelli | ordine, visibilità, opacità, rimozione | comandi registrati; ordine di disegno e opacità applicati | ispezione del renderer |
| T16 | Clic su una sorgente | clic a 2 pixel logici da una sorgente e lontano da tutte | `catalog.select` della riga giusta; nessuna selezione lontano | test |
| T17 | Cambio di base in un passo | spostare la vista finché il punto di tangenza esce dalla finestra | per tutto il cambio, nessun fotogramma con livelli su basi diverse | ispezione del renderer |
| T18 | Numeri scritti dal 10 | coordinate sotto il cursore, etichette della griglia, coordinate nel puntatore Simbad | testi identici a quelli di `format_coordinates` del 10 sugli stessi valori; punto decimale anche in italiano | confronto diretto |
| T19 | Limiti iniziali | apertura di un FITS sintetico; survey FITS simulato senza `hips_pixel_cut` | limiti uguali a `suggest_display_limits` dell'11 (sull'immagine; sul tile che contiene il centro della prima vista), dichiarati e registrati nel comando; stessi limiti alla riapertura della sessione | ricalcolo con l'11 |
| T20 | Modalità notte (`gl`) | vista con immagine, HiPS a colori, due cataloghi, griglia, in modalità notte, disegnata fuori schermo | nessun pixel con componente verde o blu sopra la soglia bassa dichiarata nel test; posizioni invariate (T1) | lettura dell'immagine fuori schermo |
| T21 | Nord e barra di scala (A7) | viste `TAN` in ICRS e galattico, su un'immagine ruotata con distorsioni SIP, vista `AIT`, vista con il polo nel campo | frecce disegnate con le direzioni di `compass_and_scale_bar` del 10 entro 1° e barra lunga quanto dice il 10 entro 1 pixel; etichetta identica al testo del 10; "al centro" per `AIT`; "polo nel campo" con `NORTH_UNDEFINED`; presenti anche nel PNG | ricalcolo con il 10 |
| TP1–TP7 | Prestazioni (`perf`) | condizioni di §3.15 sul Mac di riferimento | obiettivi P1–P6 rispettati; P7 misurato e riportato | misura; risultati riportati, mai obiettivi abbassati |

## 13. Decisioni aperte

Nessuna decisione dei Gruppi 1 e 2 aperta (dal 2026-10-15). Resta da
compilare il Mac di riferimento (§3.15).

- **D10-9 — Soglia `TAN`/`AIT`: DECISA il 2026-10-15** (decisione del
  proprietario): 30°, con lo scarto di ±10 % gestito qui (§3.3).
- **D11-8 — Corona del centroide: DECISA il 2026-10-15** (decisione del
  proprietario): raggio interno 1 × `box_size`, esterno 1,5 × `box_size`
  (default dell'11); `box_size` iniziale dello strumento 15 pixel,
  modificabile e dichiarato (§3.12).
- **Raggio del puntatore Simbad: DECISO il 2026-10-15** (decisione del
  proprietario; D14-9 punto 2 lo assegnava al 41): 12 pixel logici
  convertiti in angolo, richiesta dopo 500 ms fermo, una alla volta
  (§3.12).
- **D41-1 — Letture passive con rete: DECISA il 2026-10-15** (decisione
  del proprietario): il puntatore Simbad è un comando `passive` eseguito nel
  **gruppo di thread dei tile**, con le stesse regole dei tile (non
  registrato, annullabile, risultati con i segnali di Qt). Applicata in
  §3.12, §3.13.
- **D41-2 — Scrittura dei numeri mostrati: DECISA il 2026-10-15**
  (decisione del proprietario): nuova funzione **`format_coordinates`** nel
  10, che scrive le coordinate in sessagesimale (o decimale) con le cifre
  di DC3; nessuna conversione nell'interfaccia. Applicata in §3.10, §3.11.
- **D41-3 — Limiti iniziali di visualizzazione: DECISA il 2026-10-15**
  (decisione del proprietario): nuova funzione
  **`suggest_display_limits`** nell'11 con `ZScaleInterval` di astropy; i
  limiti scelti sono dichiarati nel risultato. Applicata in §3.6, §3.7.
- **D41-4 — Test `perf` e `gl`: DECISA il 2026-10-15** (decisione del
  proprietario): esclusi di default; `gl` blocca il commit quando eseguito,
  `perf` si riporta (§12). **Dati del Mac di riferimento: da compilare**
  (§3.15), li indica il proprietario.
- **Scelte minori: CONFERMATE dal proprietario il 2026-10-15:** (1) una sola immagine FITS alla volta
  nella v1; (2) ricentramento della base quando il punto di tangenza esce
  dalla finestra; (3) catalogo senza moto proprio disegnato alle posizioni
  della tabella, epoca del catalogo dichiarata, "non propagato"; (4) una
  regola di stile per catalogo con colore da tavolozza fissa; (5)
  tolleranza del clic = dimensione del simbolo o 4 pixel logici; (6) MOC
  disegnato al più all'ordine sotto il tetto `GRID_MAX_CELLS` del 16, per
  eccesso dichiarato; (7) unità della distanza scelta nelle opzioni,
  default ′; (8) 6 thread per i tile; (9) due file Python (`sky_viewer.py`,
  `sky_renderer_gl.py`) per tenere l'OpenGL separato.
- **A7 nella v1: DECISA il 2026-10-16** (decisione del proprietario,
  opzione b): indicatore del nord e barra di scala con la nuova
  `compass_and_scale_bar` del 10 (§3.18, T21). **Scelte minori: CONFERMATE dal proprietario il 2026-10-16 (come raccomandate):** (10) angolo in basso a sinistra; (11) frecce di 40 pixel
  logici.
- **Verificato il 2026-10-16:** cache del 04 da più thread (§3.13, `05`
  T17; corretta con D04 nel 04); **funzioni OpenGL incluse in PySide6
  sufficienti** (PySide6 6.12.0, Mac M1: contesto 4.1 core fuori schermo,
  programma con `gl_PointSize`, VAO e buffer `float32` con
  `setAttributeBuffer`, texture `R32F` campionata, rilettura del
  framebuffer: punti al pixel esatto, valori della texture esatti, nessun
  errore GL; PyOpenGL non serve).
- **Da verificare prima del codice:**
  funzioni HiPS pubbliche di `reproject` rispetto al campionamento del 12
  (12, P6); licenze di PySide6/Qt e di pytest-qt.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-15 | Claude Code | Creazione del file (stato: bozza) dalla proposta della fase 1 approvata dal proprietario il 2026-10-15: perimetro v1; geometria con base e finestra da `make_view_wcs` del 10 e campionamento dei tile del 12; traslazione e scala dello schermo scritte esplicitamente come disegno; D10-9 (30° con scarto ±10 %), D11-8 (corona 1×/1,5× `box_size`, box 15 pixel) e raggio Simbad (12 pixel logici, 500 ms, una richiesta alla volta) decisi; rendering con `QOpenGLWidget` dietro un'interfaccia di disegno nostra, funzioni OpenGL di PySide6; obiettivi di prestazione P1–P7 con marcatori `perf` e `gl` e regola "misurare e riportare"; test con pytest-qt in `offscreen` e controllo entro 1 pixel; lista di controllo manuale; verifica della cache da più thread. Nuove decisioni D41-1…D41-4. |
| 2026-10-15 | Claude Code | **Decisioni del proprietario del 2026-10-15:** D41-1 (puntatore Simbad `passive` nel gruppo di thread dei tile), D41-2 (`format_coordinates` nel 10), D41-3 (`suggest_display_limits` con `ZScaleInterval` nell'11, limiti dichiarati e registrati; per i survey FITS senza `hips_pixel_cut`, sul tile del centro della prima vista), D41-4 (`perf` e `gl` esclusi di default, `gl` blocca, `perf` si riporta; Mac di riferimento da compilare) decise; scelte minori confermate; temi e modalità notte rossa nel renderer (linee guida visive del `40` §3.11), colori dei cataloghi di Okabe e Ito; test T18–T20. Nessuna decisione dei Gruppi 1 e 2 resta aperta. |
| 2026-10-16 | Claude Code | **Proposta della fase 1 sull'IA approvata dal proprietario il 2026-10-16** (autorizzazione a modificare la bozza come proposto): **A7 nella v1** (opzione b) — nuova §3.18 con indicatore del nord e barra di scala disegnati nell'angolo dai risultati di `compass_and_scale_bar` del 10 (nuova funzione), anche nel PNG; §3.1, §3.17, §4, §5 aggiornati; test T21; scelte minori 10 e 11 da confermare. |
| 2026-10-16 | Claude Code | Scelte minori **confermate dal proprietario il 2026-10-16** come raccomandate (§13). **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-16. |
| 2026-10-16 | Claude Code | Verifiche del 2026-10-16: funzioni OpenGL di PySide6 sufficienti (§13), cache da più thread corretta con D04 del 04. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **Sprint 4a del codice** (§3.1): `ui/sky_viewer.py` e `ui/sky_renderer_gl.py`, sfondo HiPS a colori, zoom e spostamento come comandi del `05`, vista iniziale e limiti dello zoom (scelte del proprietario del 2026-10-17), scritta del survey; test T4, T5, T12 parziali e test `gl` del disegno in `tests/ui/test_sky_viewer.py`. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **Parte 4a-fix del codice della v1 (41, FASE: CODICE – interfaccia v1):** dopo la prova del proprietario (zoom e "Vai a" non funzionavano). Cause trovate con eventi Qt reali passati dalla finestra: (1) la rotella del mouse su macOS dà eventi con valori piccoli (non 120 per scatto): ora ogni evento vale almeno uno scatto; il pizzico è ora accettato; (2) uno spostamento o un ridimensionamento dei pannelli ancora da registrare, a fine gesto, rimetteva il centro in un altro punto dopo "Vai a" (e al primo avvio): ora una vista cambiata da altro azzera il gesto in sospeso e la finestra diversa è compensata; (3) l'errore di "Vai a" compare anche nella barra di stato. Nessun comando né spec cambiati; 3 test nuovi in `tests/ui/test_sky_viewer.py`. Aperta la domanda al proprietario su pulsanti + / − e ⌘+ / ⌘− (non nel 41). |
| 2026-10-17 | Claude Code | **Parte 4a-fix (seconda parte), decisioni del proprietario dello stesso giorno:** pulsanti **+** e **−** sul cielo e voci Zoom in/out del menu View (⌘+, ⌘=, ⌘−; ×2 e ÷2 come un gesto); dopo un "Vai a" riuscito con campo > 1,25° la vista va a circa 1° con un `view.set_zoom` registrato (`05` invariato). Specifiche aggiornate prima: `41` §3.4 e `40` (menu View, §3.4). Icone Lucide `plus` e `minus` (ISC), traduzioni italiane, 2 test nuovi. |
