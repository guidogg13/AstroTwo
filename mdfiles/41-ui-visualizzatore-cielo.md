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
dà l'avviso `HIPS_FITS_NOT_YET` fino al 4b), zoom (rotella del
mouse 2^(1/4) per scatto, pizzico del trackpad) e spostamento
(trascinamento, due dita sul trackpad) come `view.set_zoom`/`view.set_center`
a fine gesto, scritta "survey · proiezione · campo" nella barra del `40`,
modalità notte nel disegno. **Scelte del proprietario del 2026-10-17:**
vista iniziale a cielo intero (centro ICRS 0°, 0°; scala = 360° / larghezza
della finestra in pixel fisici, prima lo zoom), limiti della scala da
0.01″/pixel a 360° / larghezza, campo nella barra = `field_of_view` dei
comandi di vista del `05` (2 × `field_radius` del 10) in ° con 2 decimali da
1°, in ′ sotto 1°, in ″ sotto 1′. Una nuova dimensione del cielo registra
`view.set_center` con la nuova finestra a fine gesto. **4b (scritto il
2026-10-18):** tile FITS portati a colori da `set_display` dell'11 con i limiti scelti da
`hips.set_survey` (§3.7), coordinate e valore del pixel sotto il mouse nella barra di stato
(`cursor.read`, §3.11; il valore si legge all'ordine disegnato, decisione del proprietario del
2026-10-18). **4c (scritto il 2026-10-20):** griglia, nord ed est, barra di scala (§3.10, §3.18). **4d (scritto il 2026-10-20):** immagine FITS locale come base della vista, con inquadratura intera, colori di
`set_display`, coordinate e valore originale sotto il mouse, griglia di pixel senza WCS valido (§3.2, §3.5, §3.6,
§3.11). **4e (scritto il 2026-10-21):** cataloghi disegnati come simboli sulla GPU, clic su una sorgente con
scheda sul cielo, avviso di epoche diverse (§3.8). **4f (scritto il 2026-10-21):** MOC disegnati sulla GPU
(§3.9), pannello dei livelli con visibilità, ordine, opacità e rimozione, sfondo HiPS sotto l'immagine FITS
(§3.5, §3.7), finestra della forzatura per i corpi diversi (§3.5). **Sprint 4g scritto il 2026-10-23** (distanza e puntatore Simbad, §3.19). **Sprint 4h scritto il 2026-10-24** (PNG con crediti §3.14, cambio di base in un passo §3.2 con T17, test `perf` §3.15). Ultimo sprint del 41.

### 3.2 Geometria della vista: base e finestra

Nessuna proiezione è calcolata qui: tutta la geometria viene dal 10
(`make_view_wcs`, aggiunto al 10 il 2026-10-15) e dal 12 (campionamento
dei tile sulla vista, aggiunto al 12 il 2026-10-15).

- **Base:** il piano su cui si calcolano una volta le posizioni dei
  livelli.
  - **Con un'immagine FITS aperta** la base è il **WCS dell'immagine**
    (griglia dei pixel del file, senza ricampionare i pixel
    dell'immagine; orientamento del file).
    **Inquadratura (decisione del proprietario del 2026-10-20, sprint 4d):**
    appena aperta, l'immagine si inquadra **intera nella finestra**: centro =
    centro dei suoi pixel (`pixel_to_sky` del 10), scala = scala della base
    (`make_view_wcs`, 10) × max(colonne immagine / colonne finestra, righe
    immagine / righe finestra). La fa `image.open` (05 §3.6 punto 7) e la
    scrive nel suo risultato (`framing`), così la riapertura della sessione
    dà la stessa vista; senza finestra nota la vista non cambia. **Dallo
    sprint 4f** lo sfondo HiPS si disegna anche con l'immagine come base,
    campionato sulla stessa `ViewGeometry` (§3.7), e i livelli si compongono
    nell'ordine del pannello con la loro opacità (§3.5).
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
  quando il punto di tangenza esce dalla finestra, quando cambia la
  proiezione (§3.3) o quando il nuovo centro non ha posto nella proiezione
  della base attuale (una `TAN` non rappresenta punti a più di 90° dal
  tangente: da Sirius a M31; correzione del 2026-10-19).
- **Cambio di base in un passo:** la vista continua a mostrare la base
  vecchia finché per la nuova non sono pronte posizioni dei cataloghi,
  griglia, MOC e campionamento dei tile; poi passa alla nuova tutta
  insieme. I valori dei tile arrivano poi a mano a mano.
  **Dettagli dello sprint 4h (scritti il 2026-10-24; scelte minori 7–9 DA CONFERMARE):** «pronto» = campionamento
  dei tile arrivato (se lo sfondo ne ha), e per ogni catalogo e MOC **visibili** la risposta del calcolo per la
  base nuova è arrivata, riuscita o con errore (scelta minore 7: un calcolo fallito non tiene ferma la vista,
  l'errore si riporta come oggi e il livello non si disegna). Fino ad allora il renderer non riceve né il piano
  dello sfondo, né quello dell'immagine, né simboli, né poligoni, né la griglia, né l'indicatore e la barra della
  base nuova, e restano disegnati quelli della base vecchia con la trasformazione del gesto. Il passaggio è un solo
  blocco di chiamate al renderer nello stesso turno del ciclo degli eventi, quindi nessun fotogramma mescola due
  basi. I tile della base nuova si richiedono subito (non aspettano gli altri calcoli) e si caricano sulla GPU
  solo al passaggio (scelta minore 8). Se arriva un'altra base prima del passaggio, la precedente in attesa si
  scarta e vale l'ultima (scelta minore 9). Un cambio di visibilità o di livelli durante l'attesa vale per la
  base in attesa.

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

**Diagnostica degli ingressi (2026-10-17, parte 4a-fix2):** con la variabile
d'ambiente `ASTROTWO_DEBUG_INPUT=1` il visualizzatore scrive su stderr, per
ogni rotella, `angleDelta`, `pixelDelta`, fase, `inverted`, modificatori,
sorgente, quale widget la riceve e se è accettata; per ogni passo di zoom,
scala prima/dopo e che cosa fa il ritardo di 300 ms (gesto azzerato o
ripristinato). Spenta di default; nessuna chiave né dato personale nei log.
Temporanea nell'uso, resta nel codice.

**Rotella del mouse su macOS, dati reali (2026-10-17, parte 4a-fix2):**
misurati sul Mac del proprietario: ogni evento ha `phase` = `NoScrollPhase`,
`angleDelta` = ±120 e un `pixelDelta` non nullo e irregolare (da 2 a 1147,
accelerazione di macOS); uno scatto fisico arriva spezzato in 4–7 eventi (34
eventi per 6 scatti). Regola: `NoScrollPhase` = rotella di mouse → zoom, con
`pixelDelta` ignorato; ogni evento vale 1/6 di scatto
(`WHEEL_EVENTS_PER_NOTCH` = 6, scelta nostra tarata sul log; un giro di 3
scatti dà circa 3 scatti, 4 scatti = ×2, con ±20% di scarto da scatto a
scatto; lo zoom resta proporzionale alla velocità). Fasi
Begin/Update/End/Momentum = trackpad a due dita → spostamento; il pizzico
resta lo zoom del trackpad. Sostituisce la regola "ogni evento vale almeno
uno scatto" di (a). Il numero di eventi per scatto può dipendere dalla
velocità della rotella impostata nel sistema: da verificare su altri Mac.

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
- **Sprint 4f (decisioni del proprietario del 2026-10-21):**
  - **Pannello dei livelli** nel pannello "Layers" del `40`: un riga per livello, **in alto il livello disegnato
    sopra** (ordine inverso a quello dello stato, dove il primo è in basso). Per ogni riga: casella della
    visibilità (`layer.set_visible`), nome, tipo, una riga di dettagli (sorgente: file o servizio, con la data per
    i cataloghi; corpo; epoca usata per il disegno: per un catalogo "disegnato all'epoca …" o "posizioni della
    tabella (non propagato)", per un'immagine l'epoca dell'intestazione o "epoca non nota"; conteggi: righe
    disegnate e non disegnabili, ordine di disegno del MOC con "per eccesso"; "sovrapposizione forzata" con
    `force_body`), cursore dell'opacità 0–100 % (`layer.set_opacity` **al rilascio**, un comando per gesto come
    per la vista), pulsanti su e giù e trascinamento (`layer.move`), pulsante di rimozione (`layer.remove`). Ogni
    azione è un comando registrato del `05` (`requested_by` = `mouse`); dopo ogni comando l'elenco si ricostruisce
    dallo stato (il pannello non tiene stato suo). Senza livelli resta lo stato vuoto del `40`.
  - **Ordine di disegno:** tutti i livelli nell'ordine dello stato, dal basso: piani (sfondo HiPS, immagine) come
    texture con la loro opacità, MOC (riempimento e perimetro), simboli dei cataloghi; sopra tutto griglia,
    indicatore, barra, anelli della selezione e scheda.
  - **Finestra della forzatura:** un errore `BODY_MISMATCH` di `moc.open`, `image.open`, `catalog.open_file`,
    `catalog.load_region` o `layer.set_visible` apre la finestra "Layers of different bodies" con il testo del 19 e
    i pulsanti Annulla e **Forza la sovrapposizione**; questo ripete lo stesso comando con `force_body` = vero
    (registrato, citato nel risultato e nel pannello). Con l'opzione dei dati planetari spenta (default, D19-5,
    nessuna preferenza nella v1) il 19 risponde allora `PLANETARY_DATA_DISABLED` (ordine dei controlli del 19,
    decisione del proprietario del 2026-10-21).
- **Immagine senza WCS** (`WCS_MISSING` dell'11/10) **o con WCS non utilizzabile**
  (`WCS_INVALID`): si apre come griglia di pixel (scelta del proprietario del
  2026-10-20, sprint 4d); finché è aperta non si sovrappongono HiPS, cataloghi o MOC
  (`VIEW_NO_WCS`) e si mostrano solo le coordinate pixel. **Sprint 4d:** la
  griglia di pixel (`PixelGridGeometry` del 05) inquadra l'immagine intera nella
  finestra; non ha centro, scala in angolo, griglia delle coordinate, nord né barra
  di scala, e **non ha zoom né spostamento col mouse** (D41-5, rinviata a dopo la v1 dal
  proprietario il 2026-10-21); i pixel si leggono
  con il valore originale e la posizione FITS (x, y), mai coordinate celesti:
  `cursor.read` dà `sky = null` e `wcs_problem` con il codice `WCS_INVALID` (anche
  quando manca del tutto il WCS) e il motivo del modulo; la barra di stato scrive
  `WCS_INVALID` al posto delle coordinate.

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
- **Disegno dell'immagine base (sprint 4d):** per ogni pixel della finestra si
  prende il colore del pixel più vicino del piano di `set_display`
  (`window_to_base` del 10, indice `floor(x + 0,5)`): è disegno, nessun numero
  mostrato nasce da qui (§3.4). Fuori dall'immagine il pixel è trasparente;
  visibilità e opacità del livello valgono qui. Il ricalcolo avviene a ogni nuova
  geometria o nuovo piano di colori (`image.set_display`), e il gesto usa la
  stessa traslazione e scala degli altri livelli.
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
- **Sotto un'immagine FITS (sprint 4f):** con l'immagine come base il campionamento usa la `ViewGeometry`
  dell'immagine (`window_to_sky` del 10 è esatto anche con le distorsioni); sfondo e immagine hanno ciascuno la
  sua texture e si compongono sulla GPU nell'ordine dei livelli con la loro opacità (fuori dall'immagine il pixel è
  trasparente, quindi si vede lo sfondo). Visibilità e opacità non richiedono nuovi tile. Con una griglia di pixel
  (§3.5) lo sfondo non si disegna (`VIEW_NO_WCS`).
- **Tile FITS:** valori portati a colori con `set_display` dell'11; limiti
  iniziali da `hips_pixel_cut` del servizio se dichiarato, altrimenti
  `suggest_display_limits` dell'11 (D41-3) sui valori del **tile che
  contiene il centro della prima vista** del survey (scelta fissa, così il
  risultato non dipende dall'ordine di arrivo dei tile), dichiarati nel
  risultato di `hips.set_survey`. **Dove (decisione del proprietario del
  2026-10-18):** i limiti li sceglie `hips.set_survey` (05, §3.6 punto 7), non il
  visualizzatore, e li scrive nel comando registrato (`vmin`, `vmax`), così la
  riapertura della sessione dà gli stessi colori; il "centro della prima vista" è
  ICRS (0°, 0°), il centro fisso della vista iniziale, e il tile è quello
  all'ordine min(3, massimo del survey) che lo contiene. Il visualizzatore
  riceve i limiti nel campo `display` del livello e chiama `set_display` dell'11
  (palette `gray`, funzione `linear`, gamma 1) su ogni tile nel gruppo di thread
  dei tile: nessun calcolo nell'interfaccia. **Tile JPEG o PNG:** colori del tile.
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
- **Sprint 4e (decisioni del proprietario del 2026-10-21):**
  - **Dove si calcola:** posizioni (`display_positions` del 13 se il livello ha le colonne di moto proprio
    scelte con `catalog.set_columns`, altrimenti le posizioni della tabella, scelta minore 3) e pixel della base
    (`sky_to_pixel` del 10) nel **gruppo di thread dei tile**, una volta per base e per livello; nel thread
    principale solo `base_to_window` della `ViewGeometry` (fattore e spostamento, §3.4) e il disegno. Righe
    senza posizione valida o fuori dalla proiezione non si disegnano (pixel non finito del 10; **dallo sprint 4f**
    anche le righe oltre il riquadro dell'immagine base si disegnano, perché attorno si vede lo sfondo). Con una griglia di pixel (§3.5) i cataloghi
    non si disegnano (`VIEW_NO_WCS`, un messaggio).
  - **Stile:** quello del livello (`catalog.load_region`/`catalog.open_file` assegnano lo stile iniziale, `05`
    §7: Okabe e Ito senza il nero, sei forme, 8 pixel logici, in ordine di apertura), con forma, colore e
    dimensione di ogni riga da `set_plot_rules` del 13.
  - **Epoche diverse (D10-2):** se le posizioni non sono propagate e l'epoca del catalogo e quella
    dell'immagine base sono entrambe dichiarate e diverse, avviso `CATALOG_EPOCH_DIFFERS` nel pannello Messaggi
    (una volta per livello e base) e nella scheda della sorgente, con le due epoche in ISO 8601 o come epoca
    giuliana (`J2016.0`) e la scala; epoca del catalogo non dichiarata con un'immagine datata →
    `CATALOG_EPOCH_UNKNOWN`. Con lo sfondo HiPS (epoca non nota) nessun avviso.
    **Dallo sprint 9 (E7-a, 2026-10-25):** quando le posizioni del livello sono propagate (colonne di moto
    proprio scelte con `catalog.set_columns`) all'epoca dichiarata dell'immagine base, il pannello Messaggi
    riceve la nota `CATALOG_EPOCH_PROPAGATED` (una volta per livello e base, non è un avviso e non compare con
    il ⚠ nella scheda) con l'epoca dell'immagine e il numero di righe disegnabili su quelle della tabella: così
    dopo `catalog.set_columns` il pannello non resta con il solo `CATALOG_EPOCH_DIFFERS`/`CATALOG_EPOCH_UNKNOWN`
    di prima, che resta nel registro com'era (era vero quando fu scritto).
  - **Campi densi (D41-10, decisione del proprietario del 2026-10-25, sprint 9b):** quando un catalogo visibile ha più
    di `DENSE_SYMBOLS` = **2 000** simboli disegnati sulla base (scelta minore DA CONFERMARE), il pannello Messaggi
    riceve la nota `CATALOG_DENSE` (una volta per livello e base) con il numero di simboli e la soglia, e i
    suggerimenti: campo più piccolo, meno righe massime, simboli più piccoli con `catalog.set_style`. Nessuno stile
    cambia da solo.
  - **Testi della scheda della sorgente (sprint 9, E7-b):** le righe della scheda vengono tutte dalla lingua
    dell'interfaccia: la fonte dell'epoca di visualizzazione da `epoch_origin` del 13 con la voce
    `DISPLAY_EPOCH_SOURCE`, il motivo della posizione mancante da `position_reason_code` del `05` con la voce
    `SOURCE_NO_POSITION`; i testi italiani della storia della tabella e del risultato restano dove sono.
  - **Clic:** un clic (pressione e rilascio a meno di 3 pixel logici) sceglie il simbolo più vicino entro
    **metà della sua dimensione** (il simbolo disegnato) o, se più grande, entro 4 pixel logici (scelta minore
    5), tra i cataloghi visibili, a pari distanza il livello più in alto; ne nasce `catalog.select`
    (`requested_by` = `mouse`). Un clic nel vuoto con una selezione attiva registra `catalog.select` con righe
    vuote; senza selezione non registra nulla.
  - **Scheda della sorgente (decisione del proprietario del 2026-10-21):** finché il `42` non c'è, e anche
    dopo, un riquadro sul cielo vicino al simbolo con nome/ID, coordinate della tabella scritte da
    `format_coordinates` del 10 nello stile scelto, epoca del catalogo, catalogo con sorgente e data (tutto dal
    risultato di `catalog.select`, `05` §7) e la riga "disegnata all'epoca …" (propagata) o "non propagata";
    si chiude con Esc o con un clic nel vuoto. La sorgente selezionata ha un anello nel colore d'accento.

### 3.9 MOC

- Celle e contorni da `healpix_grid(order, within=moc)` del 16, portati in
  pixel della base con `sky_to_pixel` del 10; disegnati come poligoni
  pieni con l'opacità del livello e il contorno.
- **Ordine del disegno (scelta minore 6):** l'ordine del MOC se le celle
  non superano il tetto del 16 (`GRID_MAX_CELLS`, 196 608); altrimenti
  l'ordine più alto sotto il tetto, con la dichiarazione "disegnato
  all'ordine k, per eccesso" nel pannello dei livelli (le celle a ordine
  più basso che toccano il MOC lo contengono).
- **Sprint 4f (decisioni del proprietario del 2026-10-21):**
  - **Dove si calcola:** nel gruppo di thread dei tile, una volta per base e per livello: `healpix_grid` del 16 con
    `within` = il MOC e pixel della base di ogni punto dei contorni con `sky_to_pixel` del 10; nel thread
    principale solo `base_to_window` (§3.4) e il disegno.
  - **Ordine di disegno:** si prova `healpix_grid` all'ordine `k` e, se il 16 risponde `GRID_TOO_LARGE`, a `k − 1`,
    finché passa. Per non provare ordini enormi si parte da min(ordine del MOC, il più alto `k` con frazione di
    cielo del MOC × 12 × 4^k ≤ `GRID_MAX_CELLS`), con `sky_fraction` del 16 (le celle che toccano il MOC non sono
    mai meno di così). Con `k` minore dell'ordine del MOC il pannello scrive "disegnato all'ordine k, per eccesso".
  - **Punti per lato** (`step` del 16, scelta di disegno): 2^(6 − k) sotto l'ordine 6, altrimenti 1, così le celle
    grandi seguono la curvatura della proiezione.
  - **Riempimento:** ogni cella come ventaglio di triangoli dal primo vertice, colore dello stile del livello
    (`05`) con trasparenza `fill` (0,25) × opacità. **Perimetro:** solo i lati di `HealpixGrid.boundary` del 16
    (vicino non nel MOC), colore pieno × opacità, linee di 1 pixel fisico (il profilo core di OpenGL 4.1 non ha
    linee più spesse). Una cella con un punto fuori dalla proiezione, o tagliata dal bordo dell'`AIT` (un lato più
    lungo di 8 volte la mediana dei lati della griglia in pixel della base), non si disegna: è solo disegno.
  - **Non disegnabili:** MOC solo temporale (`MOC_TYPE_MISMATCH` del 16), MOC di un altro corpo o misto anche se la
    sovrapposizione è forzata (`MOC_BODY_UNSUPPORTED` del 16): livello presente nel pannello, nessun disegno, un
    messaggio. Con una griglia di pixel `VIEW_NO_WCS`.

### 3.10 Griglia (A6)

`compute_grid_lines` del 10 sul WCS della regione visibile data da
`ViewGeometry`, con il passo scelto da `choose_grid_spacing` (5 linee per
asse, elenchi del 10), nel frame scelto (ICRS o galattico); ricalcolata a
ogni comando di vista. Le etichette usano il valore della coordinata
restituito dal 10, scritto con `format_coordinates` del 10 (D41-2) con
la precisione uguale al passo della griglia (es. passo di 10′ → gradi e
primi, senza secondi), nello stile scelto in "Coordinate mostrate"
(sessagesimale o decimale). **Sprint 4c:** i meridiani si etichettano vicino al
bordo alto e i paralleli vicino al bordo sinistro (l'angolo in basso a sinistra è
dell'indicatore e della barra, quello in alto a destra dei pulsanti di zoom);
un'etichetta che si sovrappone a una già scritta o a quell'angolo si scarta, e il
testo resta dentro la vista (solo disposizione del disegno). Griglia e testi si
disegnano con `QPainter` sullo stesso widget OpenGL (linee comprese, scelta
dell'implementazione 4c: poche centinaia di punti, spessore e antialiasing
controllati; il passaggio a linee su GPU resta per i MOC dello sprint 4f).

### 3.11 Coordinate e valore sotto il mouse (A4)

- A ogni movimento del mouse una lettura passiva `cursor.read` (D05-1),
  al più una in corso (vale l'ultima posizione): pixel della base dal
  punto dello schermo (§3.4); cielo con `pixel_to_sky` del 10 nel sistema
  scelto; coordinate pixel in convenzione FITS con
  `convert_pixel_convention` del 10 (DC7); valore con `read_pixel` del 17
  sull'immagine, altrimenti con `pixel_values` del 12 sui tile FITS del
  survey; nessun valore per i survey a colori (`HIPS_PIXEL_UNAVAILABLE`).
  **Ordine (decisione del proprietario del 2026-10-18):** il valore si legge
  all'ordine del campionamento disegnato (parametro `order` di `cursor.read`),
  così è quello del pixel che si vede e il tile è già in memoria o in cache.
  **Dichiarazione (decisione del proprietario del 2026-10-19):** la barra di
  stato scrive anche l'ordine HiPS letto e la risoluzione di quel pixel (es.
  `1234.5 ADU · ordine 6 (≈ 3.2″/px)`), perché a ordini bassi il valore non è
  il pixel originale del survey; i numeri vengono dal risultato di `cursor.read`
  (6 cifre significative per il valore, 2 per la risoluzione). Il testo non
  cambia la larghezza minima della finestra. **Due campi (parte 4b-fix2,
  2026-10-20):** a sinistra le coordinate, a destra `valore unità · ordine N
  (≈ X″/px)` in un campo a larghezza fissa (il caso peggiore) che **non si
  taglia mai**, perché senza l'ordine il valore inganna; lo spazio che manca
  lo cede il campo delle coordinate, che prima perde l'epoca e poi si taglia
  con «…»; se l'unità è lunghissima si accorcia l'unità, mai l'ordine. Il
  pixel FITS compare solo se c'è posto. Il testo completo è nel tooltip. Il
  nome del comando in corso ha larghezza massima e non toglie spazio al valore.
- **Immagine FITS base (sprint 4d):** il valore è quello **originale** del pixel
  (`read_pixel` del 17, mai il valore dei colori) con l'unità di `BUNIT` se
  dichiarata, altrimenti «(unit not declared)»; la barra scrive anche la posizione
  pixel `FITS (x, y)` (convenzione FITS, DC7) quando c'è posto, sempre nel tooltip.
  Frame ed epoca sono quelli dell'intestazione (`pixel_to_sky` del 10): l'epoca si
  scrive solo se l'intestazione la dà (MJD-OBS, DATE-OBS, EQUINOX…), altrimenti
  «epoch unknown»; mai assunta. Se il cambio al sistema scelto per le coordinate
  richiede un'epoca che manca (`EPOCH_REQUIRED` del 10), si mostrano le coordinate nel
  frame dell'immagine con l'avviso del 10. **Epoca scritta (correzione del proprietario del 2026-10-21, DC1):**
  un'epoca data come tempo si scrive in **ISO 8601 con la scala** (es. `epoch 1990-12-22T13:49:00 UTC`; i
  millesimi solo se non nulli), un'epoca giuliana o besseliana come `J2000.0`/`B1950.0`; mai il JD, che resta
  interno. Il testo lo scrive `time_text` del `05`. Con l'anteprima di un'immagine a due
  livelli la lettura segue l'11 (`PREVIEW_NOT_MEASURABLE`).
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
  solo per il disegno, DC6; sprint 4e: un punto per sorgente con `gl_PointSize` e la forma disegnata nel
  programma di disegno con `gl_PointCoord`), MOC come triangoli e linee in buffer della GPU (sprint 4f: un
  programma con posizione e colore per vertice, trasparenza, modalità notte), griglia come linee;
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

**Dettagli dello sprint 4h (scritti il 2026-10-24; scelte minori 1–6 DA CONFERMARE):**

- **Due fasi (scelta minore 1).** L'esecutore del comando (thread di lavoro) controlla il percorso e lo stato e
  compone i testi dallo stato dello spazio di lavoro, senza numeri nuovi: percorso assoluto con estensione `.png`
  (`.PNG` accettata), cartella esistente e scrivibile (`EXPORT_PATH_INVALID`), vista con geometria e finestra
  (`VIEW_UNDEFINED`). Il disegno fuori schermo e la scrittura del file li fa la finestra nel thread principale
  quando il comando è `ok`; un errore di scrittura è un messaggio `EXPORT_FAILED` nel pannello Messaggi, non un
  comando fallito. Il file è scritto in un file temporaneo e poi rinominato: mai un PNG a metà.
- **Immagine.** Pixel fisici del disegno (`render_offscreen` del renderer: sfondo, immagine, MOC, simboli, griglia,
  indicatore e barra, nella modalità normale o notte del momento). **Le misure (§3.19) e la scheda della sorgente non
  sono nel PNG** (scelta minore 2): sono sopra il cielo come widget, non nel disegno del renderer.
- **Crediti nell'immagine e nei metadati (scelta minore 3; requisito 6 di `01` §6.1).** Una riga di crediti
  breve in basso a destra, su un fondo scuro semitrasparente, in carattere piccolo, tagliata a metà
  larghezza senza andare a capo se troppo lunga (il testo intero è nei metadati). La riga elenca i servizi
  e i dati dei livelli **visibili** (SIMBAD, VizieR, survey HiPS); nessuna riga se nessun livello ha crediti.
  I testi di riconoscimento sono quelli di `01` §6.1 (letti il 2026-10-17): SIMBAD e VizieR (servizio) con la frase
  richiesta e il riferimento bibliografico; per i cataloghi di VizieR il nome della tabella (l'elenco degli autori
  è nel ReadMe del catalogo: non si inventa); per un survey HiPS **il testo dichiarato dal survey stesso** (`obs_ack`,
  `obs_copyright`, `obs_title` del file `properties`), mai testi nostri; per DSS (identificativo che contiene `DSS`)
  il primo paragrafo del riconoscimento di STScI di `01` §6.1 e l'indirizzo del testo integrale. Un survey senza
  testo dichiarato: solo titolo e identificativo. Immagini e cataloghi da file: nessun credito (nessun servizio).
- **Metadati: blocchi `tEXt` del PNG (ISO/IEC 15948, scritti con Pillow, D11-6).** Parole chiave in inglese,
  valori in Latin-1 come richiede il formato, con i caratteri fuori Latin-1 resi in ASCII con segnaposto: `Software`
  (`AstroTwo` e versione), `Creation Time` (data ed ora dell'esportazione, ISO 8601 UTC con `Z`), `AstroTwo:View`
  (JSON: centro con frame, scala con unità, proiezione, base, campo di vista, finestra in pixel fisici,
  modalità notte sì o no), `AstroTwo:Layers` (JSON: per ogni livello visibile identificativo, tipo, nome,
  sorgente, origine e data di richiesta dove il modulo li ha), `AstroTwo:Credits` (testi interi), `Comment`
  (frase fissa: immagine per l'occhio, non dati scientifici). Nessuna chiave API né altro dato dell'utente.
  La data della richiesta è quella già registrata nel livello (`retrieved_at` del 11, 12, 13), non una nuova.
- **Dimensione.** Quella reale del disegno al momento della scrittura (può differire dalla finestra dello stato se
  la finestra è stata ridimensionata tra la richiesta e il disegno; nei metadati e nel risultato è scritta quella
  del file).
- **Risultato del comando:** `path`, `width` e `height` in pixel (`quantity`: la finestra dello stato), `metadata` (le
  chiavi e i valori scritti), `credits` (testi interi), `credit_line` (la riga disegnata). Il comando registrato non
  cambia lo stato dello spazio di lavoro.
- **Quarto file Python del 41 (scelta minore 4):** `src/astrotwo/ui/export_view.py` (testi, crediti e scrittura del
  PNG, senza Qt oltre a `QImage` e `QPainter`), per non allungare `sky_viewer.py`.
- **Colori e icona:** nessuna icona nuova (la voce di menu File → Esporta vista come PNG esiste dal 40).

### 3.15 Obiettivi di prestazione (approvati il 2026-10-15)

Misurati sul **Mac di riferimento** con test marcati `perf` (D41-4):

Due Mac (decisione del proprietario del 2026-10-24, D41-4): **Mac minimo** = quello di sviluppo attuale, gli obiettivi
P1–P6 si **rispettano anche qui**; **Mac comodo** = MacBook Air M5 con 32 GB (dal 2 novembre 2026), dove si misura
e si riporta. Ogni misura riporta il Mac su cui è stata fatta; un obiettivo non raggiunto su uno dei due si
misura e si riporta (regola sotto), mai abbassato.

| Mac | Minimo | Comodo |
|---|---|---|
| Modello | iMac21,1 | **da compilare** (MacBook Air M5, dal 2 novembre 2026) |
| Processore | Apple M1 | **da compilare** (M5) |
| Memoria | 8 GB | 32 GB (da confermare con `hw.memsize`) |
| Versione di macOS | 26.6.2 (letta il 2026-10-24) | **da compilare** |
| Schermo (rapporto dei pixel) | Retina 4.5K, rapporto 2 | **da compilare** |

| # | Obiettivo | Condizioni |
|---|---|---|
| P1 | spostamento e zoom ≤ **16,7 ms per fotogramma al 95° percentile** | immagine 4096 × 4096, sfondo HiPS, **1 milione di sorgenti** |
| P2 | memoria aggiuntiva per il milione di sorgenti ≤ **1 GB** | catalogo di 1 milione di righe disegnato (obiettivo minimo di `01` §8) |
| P3 | thread principale **mai fermo più di 100 ms** durante rete o calcoli | sonda di latenza (timer di Qt) durante comandi lunghi e tile |
| P4 | coordinate sotto il mouse aggiornate **entro 50 ms** | movimento del mouse su immagine e su HiPS |
| P5 | finestra pronta in **≤ 3 s senza rete** | avvio a freddo dell'app |
| P6 | primi tile HiPS visibili in **≤ 2 s con la cache calda** | survey di default, tile già in cache |
| P7 | proiezione del milione di sorgenti con `sky_to_pixel` del 10 | **valore da misurare prima di fissarlo** (nessun obiettivo scritto finché non è misurato) |

**Come si misurano (dettagli dello sprint 4h, scritti il 2026-10-24; scelta minore 10 DA CONFERMARE; test in
`tests/ui/test_perf.py`, marcatore `perf`; TP1 e TP2 usano OpenGL vero e si saltano sulla piattaforma `offscreen`: si eseguono con `QT_QPA_PLATFORM=cocoa`, e non hanno il marcatore `gl` perché un test `perf` non blocca mai il commit):** TP1 = tempo di `render_offscreen`
con `glFinish` per 120 trasformazioni di spostamento e zoom (PySide6 su OpenGL vero, finestra 1600 × 1000 logici
al rapporto dei pixel dello schermo), 95° percentile; il tempo include la lettura dei pixel dalla GPU, quindi è
pessimistico. TP2 = differenza di memoria residente (`ps -o rss=`) prima e dopo aver costruito e caricato il
catalogo sintetico di 1 milione di righe (posizioni, colori, dimensioni, forme e punti sulla GPU). TP3 = sonda
con timer di 10 ms durante un tile di 2 s e un calcolo lento di catalogo (come T11), massimo intervallo tra due
scatti. TP4 = tempo da un movimento del mouse al segnale `cursor_read` (immagine e HiPS), massimo su 50 movimenti.
TP5 = avvio a freddo in un processo separato (cartella home vuota, nessuna rete) dall'inizio dello script fino
a finestra mostrata e vista iniziale disegnata (`first_shown` e comandi finiti). TP6 = tempo dal comando che
apre il survey alla prima texture con un tile, con i tile già nella cache e il servizio simulato locale. TP7 =
tempo di `sky_to_pixel` del 10 su 1 milione di posizioni, solo misurato e riportato. I test `perf` scrivono i
valori sul terminale (`-s`) e in `perf-report.json` in una cartella temporanea; il confronto con l'obiettivo è un
`assert` solo per P1–P6, e un test `perf` non blocca il commit (D41-4).


**Risultati misurati il 2026-10-24 sul Mac minimo** (iMac21,1, Apple M1, 8 GB, macOS 26.6.2, schermo Retina 4.5K, rapporto 2,
finestra 3200 × 2000 pixel fisici, `QT_QPA_PLATFORM=cocoa`, 1 milione di sorgenti sintetiche):

| Test | Valore | Obiettivo | Esito |
|---|---|---|---|
| TP1 fotogramma, 95° percentile, con lettura dei pixel | 46,0 ms (mediana 33,9) | ≤ 16,7 ms | **non raggiunto** |
| TP2 memoria aggiuntiva | 313 MB | ≤ 1 GB | raggiunto |
| TP3 intervallo massimo della sonda | 37 ms | < 100 ms | raggiunto |
| TP4 coordinate sotto il mouse, massimo su 50 movimenti | 27,9 ms | ≤ 50 ms | raggiunto |
| TP5 avvio a freddo, dal processo alla finestra pronta | 4,46 s (importazioni 1,8 s, finestra 2,3 s, prima vista 0,3 s); 2,84 s sulla piattaforma `offscreen` | ≤ 3 s | **non raggiunto** |
| TP6 primi tile con la cache calda | 0,10 s | ≤ 2 s | raggiunto |
| TP7 `sky_to_pixel` su 1 milione di posizioni | 0,12 s | nessun obiettivo | solo misurato |

Cause note: **TP1** — il solo disegno con `glFinish` dura 37,9 ms con il milione di simboli e 4,6 ms senza: il costo è nei
simboli sulla GPU del M1 a 3200 × 2000, non nelle texture né nella lettura dei pixel. **TP5** — il tempo comprende la
creazione del contesto OpenGL e dei pannelli (2,3 s) più le importazioni (1,8 s); sulla piattaforma `offscreen` (senza GPU)
è 2,84 s. Obiettivi **non abbassati**: sono aperti per una decisione del proprietario (ottimizzazione dei simboli, avvio
più rapido) e per la misura sul Mac comodo dal 2 novembre.

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
- **Attivazione (decisione del proprietario del 2026-10-20):** comando
  `view.set_overlays` del `05` (`compass`, `scale_bar`, entrambi accesi di
  default), voci "Show north and east" e "Show scale bar" nel menu Vista del
  `40`; spenti entrambi il 10 non è chiamato. Registrato in cronologia e
  rieseguibile; non è nell'elenco degli strumenti dell'assistente (`32`) finché
  il proprietario non lo decide.
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

### 3.19 Strumenti: dettagli di distanza e puntatore Simbad (sprint 4g, 2026-10-23)

Completano §3.12 dove non scendeva nel dettaglio. Decisioni del
proprietario del 2026-10-23: la distanza si misura anche con uno sfondo HiPS
senza immagine (`measure.distance` esteso nel `05` con la forma cielo) e le
opzioni stanno in una barra sul cielo. Il resto è scelta minore (§13).

- **Strumento attivo:** lo dice `ui.set_tool` (menu Strumenti, `40`). Con
  uno strumento attivo il cursore è a croce; la rotella e il pizzico
  continuano a fare zoom, ma il **trascinamento col tasto sinistro non
  sposta la vista** e il clic non seleziona sorgenti (`catalog.select`).
- **Distanza, gesto:** trascinamento da p1 a p2 (almeno `CLICK_SLOP`) oppure
  due clic; durante il gesto una linea di anteprima dal primo punto al
  mouse con la distanza provvisoria non scritta (nessun numero stimato:
  solo la linea). Esc annulla il primo punto. Il comando parte al rilascio
  o al secondo clic e porta `requested_by.source = mouse`.
- **Distanza, comando:** con un'**immagine con WCS come base** si manda la
  forma pixel (`layer` = la base, `p1`, `p2` = pixel della base, che con
  un'immagine base sono i pixel dell'immagine, convenzione numpy); con un
  **altro sfondo** (HiPS) la forma cielo (`sky1`, `sky2` da `window_to_sky`
  del 10). Un punto fuori dal cielo (bordo dell'`AIT`) o una griglia di
  pixel senza WCS: nessun comando e messaggio (`OUT_OF_SKY`, `VIEW_NO_WCS`).
  L'aggancio al centroide è possibile solo con la forma pixel (la casella è
  disattivata con la spiegazione nella descrizione).
- **Barra delle opzioni:** una barra sovrapposta in alto nell'area del
  cielo, visibile solo con lo strumento distanza: unità (″, ′, °; default ′),
  «Snap to centroid» (default spento) e `box_size` (dispari ≥ 3, default 15,
  §3.12). I valori si ricordano con `prefs.set` (`tools/distance_unit`,
  `tools/distance_snap`, `tools/distance_box_size`).
- **Disegno delle misure:** ogni livello `measure` visibile è un segmento fra
  i due punti (posizioni del cielo del suo risultato, portate sullo schermo
  con la geometria corrente, quindi segue spostamento e zoom) con un'etichetta
  al centro: valore con **4 cifre significative** e l'unità (″, ′, °); il
  valore pieno e l'unità sono nella descrizione del livello nel pannello
  dei livelli. Colori: accento in chiaro e scuro, rosso in modalità notte.
  Disegnate con `QPainter` su un widget trasparente sopra il cielo (§3.13).
- **Puntatore Simbad, quando:** con lo strumento attivo, **mouse fermo
  500 ms** oppure **clic** (il clic non aspetta). Una richiesta alla volta:
  durante una richiesta un nuovo arresto aspetta e parte solo l'ultimo.
  Raggio = distanza angolare (17) tra il punto e un punto a 12 pixel
  logici (× rapporto dei pixel) portati in cielo con il 10.
- **Puntatore Simbad, riquadro:** vicino al cursore, con identificatore,
  tipo, coordinate (`format_coordinates` del 10 nello stile scelto), le
  magnitudini con banda e sistema (come le dà il 14, mai assunti), citazioni,
  separazione, origine e data e il collegamento alla pagina SIMBAD (si apre
  solo `https://simbad.cds.unistra.fr/`). Nessun oggetto nel raggio:
  «No SIMBAD object within R» con il raggio, più gli avvisi del 14. Errore del
  comando (rete, WCS): il testo del 14 o del 05 con ⚠. Il riquadro si
  chiude al primo movimento oltre `CLICK_SLOP`, con Esc, a strumento spento o
  quando il mouse esce.
- **Assistente:** `measure.distance` è già nell'elenco del `32` (con lo
  schema esteso); `simbad.pointer` è `passive`, non è nell'elenco e non lo
  diventa (regola del `32` §3.2).
- **Modalità notte e lingue:** barra, etichette e riquadro usano i rossi di
  §3.11 del `40`; i testi sono inglesi con traduzione italiana (`40`, `.ts`).

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
dell'interfaccia di disegno; scelta minore 9), `src/astrotwo/ui/sky_tools.py` (strumenti, sprint 4g) e
`src/astrotwo/ui/export_view.py` (testi, crediti e scrittura del PNG, sprint 4h); test in
`tests/ui/test_sky_viewer.py`.

- **`SkyViewer`** — widget del visualizzatore: tiene la `ViewGeometry`
  corrente, traduce i gesti in comandi (timer dei 300 ms), coordina livelli
  e strumenti.
- **`SkyRenderer`** (interfaccia di disegno) — `set_base`, `set_transform`
  (traslazione e scala), `upload_texture`, `upload_points`,
  `upload_polygons`, `upload_lines`, `draw_labels`, `render`,
  `render_offscreen` (per i test e per il PNG; dallo sprint 4h è nell'interfaccia di base e restituisce una `QImage` in pixel fisici), `drawn_positions` (posizioni
  sullo schermo dei simboli disegnati, per i test). **Sprint 4f:**
  `upload_texture(rgba, key)` (una texture per piano), `set_layers` (ordine dal basso e opacità dei livelli
  disegnati), `upload_polygons` (MOC: triangoli e lati del perimetro), `drawn_polygons` (vertici sullo
  schermo, per i test).
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

### 10.1 Messaggi con codice e `params` (D40-3, sprint 8e, 2026-10-25)

I messaggi del visualizzatore nascono come **codice + `params`**; il testo italiano resta invariato. Gli errori di
12, 10, 13 e 16 incontrati mentre si disegna (tile, campionamento, posizioni dei cataloghi, celle dei MOC) si mostrano
con **il codice e i `params` del modulo** (il catalogo ha già le loro voci); il testo originale, che per cataloghi e MOC
nomina il livello, resta nel dettaglio della voce e in "Copia come JSON"; dallo sprint 8f il livello compare anche nel
testo tradotto grazie al parametro riservato `layer_context` (`40` §3.7.1: «Catalog layer L2 «Gaia DR3»: …»), aggiunto
ai `params` di questi errori e degli avvisi di epoca. Un'eccezione senza codice è `UI_COMMAND_FAILED`
(`40` §10.1). `ext` = testo esterno (nome di livello o di file, testo del sistema grafico).

| Codice | `reason` | Parametri |
|---|---|---|
| `VIEW_NO_WCS` | `hips`, `catalogs`, `moc`, `distance` | — |
| `CATALOG_EPOCH_UNKNOWN` | — | `image_epoch` (+ `layer_context`) |
| `CATALOG_EPOCH_DIFFERS` | — | `catalog_epoch`, `image_epoch` (+ `layer_context`) |
| `CATALOG_DENSE` | — | `drawn` (integer), `threshold` (integer) (+ `layer_context`); nota, sprint 9b |
| `CATALOG_EPOCH_PROPAGATED` | — | `image_epoch`, `drawable` (integer), `rows` (integer) (+ `layer_context`); nota, sprint 9 |
| `DISPLAY_EPOCH_SOURCE` | `image`, `image_undeclared`, `image_no_wcs`, `no_image`, `user` | — ; solo testo della scheda della sorgente, sprint 9 |
| `SOURCE_NO_POSITION` | `columns_not_confirmed`, `row_invalid` | — ; solo testo della scheda della sorgente, sprint 9 |
| `HIPS_DISPLAY_UNKNOWN` (condiviso con 12) | `no_limits`, `reopen` | — / `hips_id` |
| `GL_UNAVAILABLE` | `version` | `found`, `required` |
| | `program`, `points_program`, `moc_program` | `log` (ext) |
| `EXPORT_PATH_INVALID` | `not_png`, `is_directory` | `path` (ext) |
| | `folder_unwritable` | `folder` (ext) |
| `EXPORT_FAILED` | — | `path` (ext), `detail` (ext) |
| `EXPORT_FAILED` | `offscreen` | `path` (ext); disegno fuori schermo non disponibile, sprint 9 |
| `VIEW_UNDEFINED` (condiviso con 05) | `export` | — |
| `OUT_OF_SKY` (condiviso con 05) | `distance_point`, `point` | — |
| `WCS_INVALID` (condiviso con 10 e 05) | `absent` | — |

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
| T14 | PNG della vista (sprint 4h) | `view.export_png` su una vista con sfondo HiPS simulato, un catalogo di Simbad simulato e un'immagine; percorso non valido; vista senza geometria; modalità notte | PNG con dimensioni in pixel fisici (rapporto 1 e 2), blocchi `tEXt` di §3.14 uguali al risultato del comando e allo stato (centro, scala, proiezione, livelli con sorgente, origine e data), crediti dei soli livelli visibili con i testi di `01` §6.1 o del survey, riga dei crediti disegnata, `EXPORT_PATH_INVALID` e `VIEW_UNDEFINED`, nessun file a metà, comando registrato e riesecuzione | lettura del file con Pillow, confronto con lo stato |
| T15 | Livelli | ordine, visibilità, opacità, rimozione | comandi registrati; ordine di disegno e opacità applicati | ispezione del renderer |
| T16 | Clic su una sorgente | clic a 2 pixel logici da una sorgente e lontano da tutte | `catalog.select` della riga giusta; nessuna selezione lontano | test |
| T17 | Cambio di base in un passo (sprint 4h) | catalogo e MOC visibili, sfondo simulato; spostare la vista finché il punto di tangenza esce dalla finestra, con il calcolo delle posizioni del catalogo (poi del MOC) trattenuto | finché il calcolo è trattenuto il renderer non riceve né piano, né simboli, né poligoni, né griglia della base nuova e la base disegnata resta la vecchia; al rilascio tutti arrivano nello stesso passo (stesso turno del ciclo degli eventi), con simboli e poligoni entro 1 pixel dalla base nuova; cambio con errore del calcolo (catalogo senza posizioni) non blocca il passaggio | ispezione del renderer (registro delle chiamate) |
| T18 | Numeri scritti dal 10 | coordinate sotto il cursore, etichette della griglia, coordinate nel puntatore Simbad | testi identici a quelli di `format_coordinates` del 10 sugli stessi valori; punto decimale anche in italiano | confronto diretto |
| T19 | Limiti iniziali | apertura di un FITS sintetico; survey FITS simulato senza `hips_pixel_cut` | limiti uguali a `suggest_display_limits` dell'11 (sull'immagine; sul tile che contiene il centro della prima vista), dichiarati e registrati nel comando; stessi limiti alla riapertura della sessione | ricalcolo con l'11 |
| T20 | Modalità notte (`gl`) | vista con immagine, HiPS a colori, due cataloghi, griglia, in modalità notte, disegnata fuori schermo | nessun pixel con componente verde o blu sopra la soglia bassa dichiarata nel test; posizioni invariate (T1) | lettura dell'immagine fuori schermo |
| T21 | Nord e barra di scala (A7) | viste `TAN` in ICRS e galattico, su un'immagine ruotata con distorsioni SIP, vista `AIT`, vista con il polo nel campo | frecce disegnate con le direzioni di `compass_and_scale_bar` del 10 entro 1° e barra lunga quanto dice il 10 entro 1 pixel; etichetta identica al testo del 10; "al centro" per `AIT`; "polo nel campo" con `NORTH_UNDEFINED`; presenti anche nel PNG | ricalcolo con il 10 |
| T22 | Immagine FITS come base (sprint 4d) | File → Apri su un FITS con WCS | l'immagine è la base, inquadrata intera; i colori di ogni pixel disegnato sono quelli di `set_display` dell'11 con i limiti scritti nel comando; `image.set_display` cambia i colori | test (`tests/ui/test_image_base.py`) |
| T23 | Valore, unità, pixel, epoca e frame (sprint 4d) | mouse su pixel noti di un'immagine con `BUNIT`, con e senza `MJD-OBS`, senza `BUNIT` | valore originale con unità; `FITS (x, y)`; coordinate da `pixel_to_sky` del 10; epoca solo se dichiarata dall'intestazione; «(unit not declared)» senza `BUNIT`; lettura mai in cronologia | test |
| T24 | Senza WCS valido (sprint 4d) | FITS senza WCS e FITS con matrice del WCS nulla | griglia di pixel intera; `sky = null` e `WCS_INVALID` nella barra; valore e pixel (x, y) letti; nessuna griglia, nord o barra; rotella e trascinamento senza comandi; `simbad.pointer` dà `WCS_INVALID` | test (`tests/core/test_commands_image_base.py`, `tests/ui/test_image_base.py`) |
| T25 | Zoom sull'immagine (sprint 4d) | rotella (4 scatti) sull'immagine | `view.set_zoom` e `view.set_center` registrati, scala dimezzata, immagine ancora disegnata, valore del pixel sotto il mouse corretto | test |
| T26 | Cataloghi disegnati (sprint 4e) | catalogo sintetico su base `TAN`, poi sull'immagine FITS base; zoom e spostamento | posizioni disegnate entro 1 pixel da `sky_to_pixel` del 10 composto con `ViewGeometry`; forma, colore e dimensione dallo stile del livello (`set_plot_rules`); stile iniziale nel risultato del caricamento e nella riesecuzione | ricalcolo con il 10 e il 13 |
| T27 | Clic e scheda (sprint 4e) | clic a 2 pixel logici da una sorgente, nel vuoto, Esc | `catalog.select` della riga giusta con `requested_by` = `mouse`; scheda con nome da UCD `meta.id;meta.main`, coordinate uguali a `format_coordinates` del 10, epoca del catalogo e sorgente; clic nel vuoto → selezione vuota; Esc chiude | test |
| T28 | Epoche diverse (sprint 4e) | catalogo con epoca `J2016.0` su un'immagine con `MJD-OBS`; catalogo senza epoca; sfondo HiPS | `CATALOG_EPOCH_DIFFERS` con le due epoche; `CATALOG_EPOCH_UNKNOWN`; nessun avviso su HiPS | test |
| T28d | Campo denso (sprint 9b, D41-10) | catalogo con 2 001 righe nel campo; con 2 000 | nota `CATALOG_DENSE` con 2 001 e 2 000, una volta sola; nessuna nota con 2 000 | test |
| T28b | Epoche dopo `catalog.set_columns` (sprint 9, E7-a) | come T28, poi `catalog.set_columns` con pmRA/pmDE/Plx | nota `CATALOG_EPOCH_PROPAGATED` con l'epoca dell'immagine nel pannello Messaggi, una volta sola; nessun nuovo `CATALOG_EPOCH_DIFFERS`; scheda senza ⚠ | test |
| T28c | Lingua della scheda e delle etichette (sprint 9, E7-b) | interfaccia in inglese: scheda di una riga propagata, di una riga senza posizione, testi del pannello dei livelli; scansione delle stringhe dei moduli dell'interfaccia | nessuna parola italiana nelle righe mostrate; in italiano le stesse righe dal catalogo; la scansione trova solo testi di ripiego dei messaggi con codice, docstring e log | test |
| T29 | Epoca nella barra (correzione del 2026-10-21) | mouse su un'immagine con `MJD-OBS` | `epoch AAAA-MM-GGThh:mm:ss UTC` (ISO 8601 con scala), nessun "JD" nei testi dell'interfaccia | test |
| T31 | MOC disegnato (sprint 4f) | MOC da cerchio all'ordine 8 su base `TAN`, poi sull'immagine FITS base; MOC all'ordine 12 su gran parte del cielo; zoom | vertici dei triangoli e del perimetro entro 1 pixel da `sky_to_pixel` del 10 sui punti di `healpix_grid` del 16; solo i lati di `boundary`; ordine ridotto finché il 16 accetta, "per eccesso" nel pannello; colore e `fill` dallo stile del `05` | ricalcolo con 10 e 16 (`tests/ui/test_layers_moc.py`) |
| T32 | Sfondo sotto l'immagine (sprint 4f) | immagine FITS con WCS e survey a colori simulato; opacità dell'immagine 0,5; spostare lo sfondo sopra | tile richiesti anche con l'immagine base; texture dello sfondo e dell'immagine nell'ordine dei livelli con le opacità scelte; nessun nuovo tile per opacità e visibilità | ispezione del renderer |
| T33 | Pannello dei livelli (sprint 4f) | casella, cursore, su/giù, trascinamento e rimozione | un comando registrato del `05` per azione (opacità al rilascio); elenco con il livello in alto in cima; dettagli con sorgente, corpo, epoca e conteggi; "sovrapposizione forzata" | test |
| T34 | Gaia DR3 propagato (D41-6) | risposta registrata di TAP VizieR (Gaia DR3) caricata con `catalog.load_region`, `catalog.set_columns` con `pmRA`/`pmDE` su un'immagine con `MJD-OBS` | posizioni di `display_positions` del 13 da J2016.0 all'epoca dell'immagine, nessun `EPOCH_INVALID`; scheda e pannello "disegnato all'epoca …" | ricalcolo con il 13 |
| T35 | MOC e notte sulla GPU (`gl`) | MOC, catalogo e sfondo a colori, in modalità normale e notte | riempimento e perimetro visibili nel colore dello stile; in notte nessun pixel con verde o blu sopra la soglia di T20 | lettura dell'immagine fuori schermo |
| T36 | Distanza (sprint 4g) | immagine base con WCS e poi solo HiPS; trascinamento e due clic; opzioni; punto fuori dal cielo | forma pixel o cielo scelta dalla base; distanza = `angular_distance` del 17 ricalcolata nel test; unità e aggancio dalle opzioni; nessuno spostamento della vista; segmento ed etichetta disegnati, rossi in notte | ricalcolo con 10, 11, 17 |
| T37 | Puntatore Simbad (sprint 4g) | servizio simulato; mouse fermo 500 ms, clic, risposta lenta con secondo arresto, nessun oggetto, errore | una richiesta con il raggio di T9; riquadro con i campi del 14 e il collegamento; ultima richiesta sola dopo l'attesa; messaggi di errore; chiusura con Esc | servizio simulato |
| T30 | Qualche migliaio di sorgenti (sprint 4e) | 5000 sorgenti, gesti | un solo caricamento dei punti per base; durante il gesto solo la trasformazione; tempo del calcolo per base misurato e riportato | test (tempo riportato) |
| TP1–TP7 | Prestazioni (`perf`) | condizioni di §3.15 sul Mac di riferimento | obiettivi P1–P6 rispettati; P7 misurato e riportato | misura; risultati riportati, mai obiettivi abbassati |

## 13. Decisioni aperte

Nessuna decisione dei Gruppi 1 e 2 aperta (dal 2026-10-15). Mac di riferimento deciso il 2026-10-24 (§3.15); i dati del Mac comodo si compilano dal 2 novembre.

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
  `perf` si riporta (§12). **Mac di riferimento: DECISO il 2026-10-24** (decisione del proprietario): due
  riferimenti, **minimo** = iMac21,1 con Apple M1 e 8 GB (dati nel §3.15, obiettivi P1–P6 da rispettare anche lì) e
  **comodo** = MacBook Air M5 con 32 GB (dal 2 novembre 2026; dati da compilare allora).
- **Sprint 4h (2026-10-24): scelte minori CONFERMATE dal proprietario il 2026-10-24 (1–10)** — PNG (§3.14): (1) due fasi, esecutore che controlla e
  finestra che scrive, errore di scrittura = messaggio `EXPORT_FAILED`; (2) misure e scheda non nel PNG; (3) riga dei
  crediti in basso a destra e testi interi nei metadati; (4) quarto file Python `export_view.py`; (5) chiavi `tEXt`
  elencate in §3.14; (6) testo del survey dichiarato dal survey stesso (`obs_ack`…). Cambio di base (§3.2): (7)
  un calcolo fallito non tiene ferma la vista; (8) tile richiesti subito e caricati al passaggio; (9) l'ultima base
  in attesa scarta le precedenti. Prestazioni (§3.15): (10) modalità di misura di TP1–TP7.
- **D41-7 — P1 non raggiunto (fotogramma con 1 milione di simboli): APERTA il 2026-10-24 (Gruppo 3).** Misurato
  sull'iMac21,1 M1 8 GB (TP1): 46,0 ms al 95° percentile (mediana 33,9) contro l'obiettivo di 16,7 ms; solo il
  disegno 37,9 ms, 4,6 ms senza simboli. Causa nota: il disegno dei simboli. Obiettivo **invariato**. Si risolve in uno
  sprint di prestazioni dopo la prova completa.
- **D41-8 — P5 non raggiunto (avvio a freddo): APERTA il 2026-10-24 (Gruppo 3).** Misurato sullo stesso Mac (TP5):
  4,46 s (importazioni 1,8 s, finestra 2,3 s, prima vista 0,3 s; 2,84 s su `offscreen`) contro l'obiettivo di 3 s.
  Cause note: importazioni e creazione della finestra. Obiettivo **invariato**; stesso sprint di prestazioni.
- **D41-5 — Zoom e spostamento su una griglia di pixel: RINVIATA a dopo la v1** (decisione del proprietario del
  2026-10-21; aperta il 2026-10-20, sprint 4d).
  Un'immagine senza WCS valido si apre come griglia di pixel (scelta del proprietario), ma i comandi
  di vista del 05 (`view.set_center`, `view.set_zoom`) lavorano in coordinate celesti e scala in angolo.
  Nella v1 la griglia di pixel è inquadrata intera e **senza zoom né spostamento col mouse**.
  Raccomandazione: versione successiva, con un modo «pixel» dei comandi di vista (centro in pixel, scala
  in pixel dello schermo per pixel dell'immagine) da proporre in `panoramica.md` (AM1) e specificare nel 05.
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
- **Sprint 4g (2026-10-23): decisioni del proprietario** — distanza anche su sfondo HiPS con `measure.distance`
  esteso (`05`); opzioni dello strumento in una barra sul cielo (§3.19). **Scelte minori CONFERMATE dal proprietario il 2026-10-24** (§3.19):
  (1) 4 cifre significative nell'etichetta; (2) opzioni ricordate con `prefs.set`; (3) anche il clic fa partire il
  puntatore Simbad, senza aspettare i 500 ms; (4) il trascinamento non sposta la vista con uno strumento attivo;
  (5) il riquadro Simbad si chiude al primo movimento oltre `CLICK_SLOP`; (6) un livello `measure` per ogni misura.
- **D41-6 — Epoca del COOSYS persa da `catalog.set_columns`: DECISA il 2026-10-21 (sotto).** Aperta il 2026-10-21, sprint 4e:
  `confirm_position_columns` del 13 crea colonne di posizione senza l'epoca del COOSYS e `catalog.set_columns` del
  `05` non ha `source_epoch`: per un catalogo con l'epoca solo nel COOSYS (es. Gaia DR3 da VizieR, `J2016.0`), scegliere
  le colonne di moto proprio porta a `EPOCH_INVALID` del 13 e il catalogo non si disegna (nessuna epoca assunta).
  Funziona con una colonna `time.epoch`. Raccomandazione: `confirm_position_columns` conserva equinozio ed epoca del
  COOSYS quando le colonne confermate sono quelle collegate al COOSYS (modifica del 13, approvato, da autorizzare);
  in alternativa un parametro `source_epoch` in `catalog.set_columns` (modifica del `05`).
- **D41-6 — DECISA il 2026-10-21** (decisione del proprietario): il 13 conserva l'epoca del `COOSYS` quando
  colonne e sistema confermati sono quelli dei metadati e la usa per la propagazione; mai un'epoca assunta
  (`EPOCH_INVALID`). Applicata nel 13 (§3, T35 del 13) e qui (T34). `source_epoch` come parametro: possibile
  aggiunta futura, non ora.
- **Sprint 4f: decisioni del proprietario del 2026-10-21:** stile dei MOC dal comando `moc.open` (Okabe e Ito
  in ordine inverso, riempimento 0,25 × opacità, contorno pieno); solo il perimetro della regione (nuovo
  `HealpixGrid.boundary` nel 16); con corpi diversi `BODY_MISMATCH` prima dell'opzione dei dati planetari (19); un
  MOC di un altro corpo forzato sul cielo resta nel pannello senza disegno (`MOC_BODY_UNSUPPORTED` del 16).
  Scelte di disegno nostre, scritte in §3.9: ordine di partenza dalla frazione di cielo, punti per lato, taglio
  dell'`AIT`, opacità al rilascio del cursore.
- **Sprint 4e: decisioni del proprietario del 2026-10-21:** scheda della sorgente sul cielo (§3.8); stile
  iniziale assegnato dal comando di caricamento (`05` §7); Okabe e Ito senza il nero, sei forme, 8 pixel logici;
  nome da UCD `meta.id;meta.main` e posizione della tabella con l'epoca del catalogo. Precisazione della
  scelta minore 5: "entro la sua dimensione" = entro il simbolo disegnato (metà della dimensione).
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

- **D41-9 — "Vai a" fuori dalla proiezione dell'immagine base (B3): DECISA il 2026-10-25** dal proprietario:
  **(b)** — `VIEW_CENTER_OUTSIDE_IMAGE` del `05` con il frame di lettura e il frame scritto nel testo d'aiuto del
  campo "Vai a" (`40` §3.4); codice nello sprint 9b. Testo della domanda com'era (aperta lo stesso giorno, Gruppo 3,
  sprint 9):
  Nella prova del proprietario "Go to" `85.25 -2.46` con HorseHead.fits come base ha dato `VIEW_PARAMETERS_INVALID`
  (`center_outside_projection`). **Causa riprodotta** (test `test_b3_go_to_with_image_base_and_galactic_display`):
  "Vai a" legge le coppie di numeri nel frame delle coordinate mostrate (`05`, `view.set_coordinate_display`); con il
  galattico il punto (l = 85.25°, b = −2.46°) è a circa 119° dal punto di tangenza della `TAN` dell'immagine, che
  non lo rappresenta; il ricentramento della base (§3.2, correzione del 2026-10-19) vale **solo senza immagine**.
  Lo stesso errore viene da qualsiasi punto a più di 90° dall'immagine, anche in ICRS. Dopo il riavvio il frame
  mostrato torna ICRS, per questo non si è ripresentato (ipotesi coerente, non verificabile dalla cronologia).
  Opzioni: **(a)** errore più chiaro: ragione propria (`center_outside_image_base`) con il frame in cui la coppia è
  stata letta e il suggerimento (controllare il frame delle coordinate, o togliere l'immagine dalla base);
  **(b)** (a) più il frame scritto nel campo "Vai a" (testo d'aiuto «Go to (Galactic)…»), così l'utente sa come
  vengono lette le coordinate; **(c)** passare da soli a una base creata centrata sul punto, con l'immagine che resta
  livello ma non si vede finché non si torna sul suo campo (cambia la regola «con un'immagine aperta la base è il suo
  WCS» e serve il disegno di un'immagine su una base non sua). Raccomandazione: **(b)**; (c) è una funzione nuova.
- **D41-10 — Campi larghi con migliaia di simboli (E5): DECISA il 2026-10-25** dal proprietario: **(d)** — nota
  `CATALOG_DENSE` (§3.8) e righe massime di default 5 000 nella finestra Catalog in view (`40` §3.3); soglia della
  nota e valore del default sono scelte minori DA CONFERMARE; codice nello sprint 9b. Testo della domanda com'era
  (aperta lo stesso giorno, Gruppo 3, sprint 9): Con un campo di
  circa 4.6° SIMBAD dà migliaia di oggetti e il cielo diventa illeggibile. Opzioni: **(a)** simboli più piccoli
  oltre una densità (es. più di N simboli per 100 × 100 pixel logici → dimensione 3 pixel), scritta nel pannello dei
  livelli; **(b)** nota `CATALOG_DENSE` nel pannello Messaggi con il numero di simboli disegnati e i suggerimenti
  (raggio minore, regole di stile per magnitudine con `catalog.set_style`, righe massime); **(c)** default più basso
  delle righe massime nella finestra «Catalogo nel campo» (oggi 100 000, `DEFAULT_MAX_ROWS` del 14), es. 5 000, con il
  troncamento già dichiarato dal 13 (`PARTIAL_CATALOG`/`ROW_LIMIT_EXCEEDED`); l'utente può alzarlo; **(d)** (b) + (c).
  Raccomandazione: **(d)**: nessun cambiamento nascosto di ciò che si disegna, tutto dichiarato; (a) cambia lo stile
  scelto dall'utente senza un comando.
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
| 2026-10-18 | Claude Code | **Sprint 4b del codice** (§3.1): tile FITS con `set_display`, limiti scelti da `hips.set_survey` (05) e registrati nel comando, coordinate e valore sotto il mouse nella barra di stato con `format_coordinates`; decisioni del proprietario del 2026-10-18 su dove si scelgono i limiti e su quale ordine si legge il valore (§3.7, §3.11); test T4 (tile FITS), T8, T19. Stato `approvato` invariato. |
| 2026-10-19 | Claude Code | **Sprint 4b-fix:** "Vai a" M31 dopo Sirius non funzionava (la base `TAN` non rappresenta il nuovo centro): ricreazione della base nel 05 (§3.2); ordine e risoluzione del valore del pixel nella barra di stato (§3.11); la barra non ridimensiona più il cielo. Ripiego sul primo tile coperto e 6 cifre significative confermati dal proprietario. Stato `approvato` invariato. |
| 2026-10-20 | Claude Code | **Sprint 4b-fix2:** l'ordine e la risoluzione del valore sparivano dalla barra quando un comando era in corso (il nome del comando restringeva il campo e il testo veniva tagliato a destra; i dati arrivavano sempre da `cursor.read`). Barra a due campi, valore a larghezza fissa mai tagliato, coordinate che si accorciano, comando in corso a larghezza massima (§3.11); test a 1280 e 900 px. Stato `approvato` invariato. |
| 2026-10-20 | Claude Code | **Sprint 4c del codice (decisione del proprietario del 2026-10-20: comando nuovo `view.set_overlays`):** griglia con etichette del 10 (passo e precisione, stile delle coordinate mostrate), nord ed est e barra di scala disegnati nell'angolo in basso a sinistra (§3.10, §3.18), grigi durante il gesto, rossi puri in modalità notte; disegno con `QPainter` sul widget OpenGL, etichette che non si sovrappongono. T3 (punti entro 1 pixel dalle linee del 10), T18 (testi di `format_coordinates`), T20 (`gl`) e T21 nei test; il test `gl` ha trovato e fatto correggere un rosso con verde nella notte. |
| 2026-10-20 | Claude Code | **Sprint 4d del codice (decisioni del proprietario del 2026-10-20: inquadratura intera, griglia di pixel senza WCS):** File → Apri su un FITS locale (`image.open` del 05, già previsto) lo rende base della vista con il suo WCS e lo inquadra intero; colori da `set_display`; disegno a pixel più vicino (`sample_image`); `cursor.read` con valore originale, unità (`BUNIT` o «non dichiarata»), pixel FITS (x, y), frame ed epoca dall'intestazione senza assunzioni; senza WCS valido griglia di pixel (`PixelGridGeometry`) con `WCS_INVALID` e nessuna coordinata; nuova D41-5 (zoom e spostamento sulla griglia di pixel). T22–T25 nei test. Stato `approvato` invariato. |
| 2026-10-21 | Claude Code | **Sprint 4e del codice (decisioni del proprietario del 2026-10-21):** cataloghi disegnati come punti sulla GPU con forma nel programma di disegno, posizioni e pixel della base nel gruppo di thread dei tile (una volta per base), stile iniziale dal comando di caricamento, clic con `catalog.select` e scheda della sorgente sul cielo, avvisi `CATALOG_EPOCH_DIFFERS`/`CATALOG_EPOCH_UNKNOWN` (§3.8, §3.13); epoca nella barra in ISO 8601 con la scala invece del JD (§3.11, DC1); D41-5 rinviata a dopo la v1; test T26–T30. Stato `approvato` invariato. |
| 2026-10-21 | Claude Code | **Sprint 4f del codice (decisioni del proprietario del 2026-10-21):** MOC sulla GPU (triangoli e perimetro, ordine ridotto dichiarato, stile da `moc.open`), pannello dei livelli con visibilità, ordine, opacità e rimozione come comandi del `05`, sfondo HiPS sotto l'immagine FITS con composizione per opacità, finestra della forzatura per `BODY_MISMATCH`; D41-6 decisa (13). §3.1, §3.2, §3.5, §3.7, §3.9, §3.13, §7, §13; test T31–T35. Stato `approvato` invariato. |
| 2026-10-23 | Claude Code | **Sprint 4g (decisioni del proprietario del 2026-10-23):** distanza anche con sfondo HiPS (`measure.distance` esteso nel `05`) e opzioni dello strumento in una barra sul cielo; nuova §3.19 con i dettagli di distanza e puntatore Simbad, scelte minori da confermare in §13, test T36 e T37. Stato `approvato` invariato. |
| 2026-10-23 | Claude Code | **Codice dello sprint 4g** ("FASE: CODICE – interfaccia v1", parte 4): `src/astrotwo/ui/sky_tools.py` (`DistanceTool`, `SimbadPointerTool`, `MeasureOverlay`, `DistanceOptionsBar`; terzo file Python del 41 oltre ai due della scelta minore 9, per non gonfiare `sky_viewer.py`) e collegamento in `sky_viewer.py`; `Bridge.simbad` e `TilePool.read(..., signal)`; descrizione del livello `measure` con valore pieno e unità; test T36 e T37 in `tests/ui/test_sky_tools.py`. Scelte minori di §3.19 da confermare in §13. Stato `approvato` invariato. |
| 2026-10-24 | Claude Code | **Sprint 4h, specifica (decisioni del proprietario del 2026-10-24):** scelte minori dello sprint 4g confermate (§13); D41-4: **due Mac di riferimento** (minimo = iMac21,1 M1 8 GB, comodo = MacBook Air M5 32 GB dal 2 novembre), tabella di §3.15 compilata per il minimo; §3.14 con i dettagli del PNG (due fasi, crediti nell'immagine e nei metadati, chiavi `tEXt`, errori `EXPORT_PATH_INVALID`, `VIEW_UNDEFINED`, `EXPORT_FAILED`); §3.2 con le regole del cambio di base in un passo; §3.15 con il modo di misura di TP1–TP7; T14 e T17 riscritti; scelte minori 1–10 da confermare. `05` §7 e §10 aggiornati. Stato `approvato` invariato. |
| 2026-10-24 | Claude Code | **Codice dello sprint 4h** ("FASE: CODICE – interfaccia v1", parte 4, ultimo sprint del 41): `ui/export_view.py` (testi, crediti, scrittura atomica del PNG), `view.export_png` collegato in `main_window.py`, `render_offscreen` nell'interfaccia di disegno; cambio di base in un passo in `sky_viewer.py` (`_stage`, `_try_commit`, `_base_ready`); test `tests/ui/test_export_png.py` (T14, più un test `gl`), `tests/ui/test_base_switch.py` (T17), `tests/ui/test_perf.py` (TP1–TP7, `perf`); risultati misurati nel §3.15 (P1 e P5 non raggiunti sul Mac minimo). 831 test di default. |
| 2026-10-25 | Claude Code | **Sprint 8e (D40-3):** nuova §10.1 con la tabella dei messaggi del visualizzatore (`VIEW_NO_WCS`, `CATALOG_EPOCH_*`, `GL_UNAVAILABLE`, `EXPORT_*`, sotto-voci condivise); gli errori dei moduli incontrati mentre si disegna si mostrano con il loro codice e i loro `params`. Stato `approvato` invariato. |
| 2026-10-25 | Claude Code | **Sprint 8f:** i messaggi di disegno di cataloghi e MOC e `CATALOG_EPOCH_*` portano `layer_context` (`40` §3.7.1); tabella di §10.1 aggiornata. Stato `approvato` invariato. |
| 2026-10-25 | Claude Code | **Sprint 9 (E7-a, E7-b):** nota `CATALOG_EPOCH_PROPAGATED` nel pannello Messaggi dopo la propagazione all'epoca dell'immagine (§3.8); scheda della sorgente tutta nella lingua dell'interfaccia (`DISPLAY_EPOCH_SOURCE`, `SOURCE_NO_POSITION`); tabella di §10.1 e test T28b, T28c. Stato `approvato` invariato. |
| 2026-10-25 | Claude Code | **Sprint 9:** aperte **D41-9** (B3, "Vai a" fuori dalla proiezione dell'immagine base: causa riprodotta, opzioni) e **D41-10** (E5, campi larghi con migliaia di simboli: opzioni), §13. Stato `approvato` invariato. |
| 2026-10-25 | Claude Code | **Sprint 9b:** D41-9 decisa (b) e D41-10 decisa (d) dal proprietario (§13); nota `CATALOG_DENSE` sopra 2 000 simboli (§3.8, scelta minore da confermare), tabella di §10.1, T28d. Stato `approvato` invariato. |
