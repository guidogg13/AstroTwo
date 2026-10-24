# 10-core-coordinate-wcs.md — coordinate, WCS, sistemi e epoche di riferimento

**Stato:** approvato

## 2. Scopo

Tradurre, convertire e rappresentare correttamente le posizioni celesti e la
geometria dei campi d'osservazione, così che ogni coordinata mostrata o usata
da AstroTwo sia determinista, con unità e sistema di riferimento sempre dichiarati.

## 3. Cosa fa

- **Conversioni tra sistemi di coordinate:** equatoriali (RA/Dec), galattiche
  (l, b), eclittiche e gli altri sistemi supportati da `astropy.coordinates`;
  conversioni anche tra epoche diverse (precessione/nutazione) sempre tramite
  Astropy, mai con formule scritte a mano.
- **Risoluzione dei nomi:** tradurre un nome di oggetto (es. "M31", "NGC 224",
  "Aldebaran") in coordinate, con fonte dichiarata (servizio SIMBAD via
  `astroquery`). Le risoluzioni si **cacheano** in una **tabella SQLite
  separata dentro la cache A7** (limite e provenienza unici, schema non
  condiviso con `13-core-cataloghi.md` — D10-3 decisa il 2026-10-04), cioè
  nella cache condivisa descritta in `04-cache.md` (cartella, limite e
  timeout di rete — 10 s connessione, 60 s lettura — sono definiti lì;
  approvato il 2026-10-09). **Politica (decisione del proprietario del
  2026-10-09): prima la cache** — se il nome è già in cache, il risultato
  viene da lì, dichiarato tale con origine e data, senza rete; con
  `refresh=True` si interroga di nuovo SIMBAD e si aggiorna la cache; se la
  rete non risponde e il nome è in cache, si restituisce la copia in cache
  dichiarandolo. Le richieste a SIMBAD (TAP di `astroquery`) usano i timeout
  comuni di `04-cache.md` (10 s connessione, 60 s lettura). Le coordinate
  SIMBAD sono ICRS all'epoca J2000 (documentazione di SIMBAD): l'epoca è
  scritta nel risultato con questa fonte.
- **Letture e raffigurazioni:** coordinate del cursore nel campo visualizzato
  (con `pixel_to_sky`); **geometria della griglia di coordinate** con
  `compute_grid_lines` — meridiani e paralleli a passo dichiarato, come
  tratti di coordinate pixel dentro l'immagine (il disegno resta nel `41`);
  il passo si dà in modo esplicito oppure si sceglie in automatico con
  `choose_grid_spacing` in base al campo visibile, così la griglia resta
  leggibile a ogni ingrandimento senza che l'utente scelga il passo;
  **scelta della proiezione del campo** con `choose_projection` — `TAN` per i
  campi piccoli, `AIT` per i campi grandi, con **soglia di default 30°**
  (D10-9, decisa dal proprietario il 2026-10-15 con il `41`; lo scarto di
  ±10 % attorno alla soglia, per evitare cambi continui, è gestito dal
  `41`, che passa la soglia esplicita) (D10-8, decisa il 2026-10-09).
- **Geometria della vista (`make_view_wcs`, aggiunta il 2026-10-15 su
  decisione del proprietario, per il `41`):** il visualizzatore non
  calcola proiezioni; questo modulo costruisce il piano su cui si
  disegna (**base**: il WCS di un'immagine, oppure un WCS del cielo con
  punto di tangenza, proiezione, frame e scala dati) e la **finestra**
  visibile su quel piano a una scala data, con le funzioni finestra ↔
  cielo, il fattore e lo spostamento tra pixel della base e della
  finestra, il WCS della regione visibile (per la griglia) e il **raggio
  del campo** (per i tile del 12, per `choose_projection` e per il
  catalogo nel campo). Dettagli in §7.
- **Scrittura delle coordinate per l'interfaccia (`format_coordinates`,
  aggiunta il 2026-10-15, D41-2 decisa dal proprietario):** coordinate
  sotto il cursore, etichette della griglia e coordinate nei risultati
  mostrati si scrivono qui, in sessagesimale (o decimale) con le **cifre di
  DC3** (`02-convenzioni.md` §9: RA 0.01 s, Dec 0.1″), con
  `astropy.coordinates.Angle`: l'interfaccia non converte né arrotonda
  coordinate. Dettagli in §7.
- **Indicatore del nord e barra di scala (`compass_and_scale_bar`,
  aggiunta il 2026-10-16, A7 nella v1 per decisione del proprietario):**
  per il `41`, direzione del nord e dell'est al centro della vista e
  lunghezza in pixel della finestra di una barra di scala di lunghezza
  angolare "tonda", con l'etichetta; il `41` disegna soltanto. Dettagli in
  §7.
- **WCS (World Coordinate System):** leggere, validare e applicare la soluzione
  astrometrica (`WCS`) di un'immagine FITS: da pixel a coordinate e viceversa;
  verificare che la soluzione sia internally consistente.
- **Propagazione delle posizioni:** portare una posizione a un'epoca diversa
  usando moto proprio e parallasse (`apply_space_motion`). **L'epoca di ogni
  dato si legge dai suoi metadati e non si assume mai** (D10-2, decisa il
  2026-10-04): epoca di origine e moto proprio devono essere presenti o
  richiesti, altrimenti errore `EPOCH_REQUIRED`; **l'epoca usata è sempre
  scritta nel risultato**.
- **Calibrazione astrometrica (funzione H6 di `03-parita-aladin.md`):**
  determinare o rifinire la soluzione astrometrica di un'immagine e ricavare
  coordinate per tabelle prive di coordinate, usando sorgenti di riferimento.
  Procedura: i tre metodi manuali di Aladin (parametri, associazione di
  stelle, intestazione WCS) — D10-1, decisa il 2026-10-09 (§13).
  - **Il modulo non riceve pixel** (D10-8): nel metodo per associazione di
    stelle le posizioni pixel delle stelle (convenzione numpy) arrivano già
    calcolate dal centroide di `11-core-immagini-fits.md`; qui arrivano solo
    coppie posizione pixel ↔ posizione celeste.
  - **Associazione di stelle (D10-7, decisa il 2026-10-09):** prima un
    adattamento `TAN` con `fit_wcs_from_points`; la sua matrice CD e il suo
    pixel di riferimento sono il punto di partenza dell'adattamento nella
    proiezione richiesta (che altrimenti non converge per `SIN`, `AIT`,
    `ZEA`, `CAR`, `NCP`, `ZPN`). Poi **tre controlli obbligatori**, con
    valori configurabili e scritti nel risultato: (1) **stelle minime** — 6
    per `TAN`/`STG`, 10 per le altre proiezioni; (2) **residui** — RMS ≤ 1
    pixel e residuo massimo ≤ 3 pixel, altrimenti errore con l'elenco delle
    stelle peggiori; (3) **coerenza** — al centro del campo la soluzione
    finale non si scosta da quella `TAN` di più di 5 × l'RMS dei residui
    della soluzione `TAN` (scelta dell'RMS `TAN` del proprietario,
    2026-10-09: con l'RMS della soluzione finale il controllo scatta per
    errore su dati esatti). Se un controllo fallisce: errore, nessuna
    soluzione restituita.
  - **Più soluzioni per immagine (D10-8):** il modulo non conserva stato;
    riceve le soluzioni già calcolate per l'immagine e le restituisce come
    **lista** con la nuova soluzione in coda. Annulla/ripeti stanno in
    `24-analisi-pipeline-riproducibili.md` e `40-ui-finestra-principale.md`.
- **Calcolatrice delle coordinate (A5): non è più in questo modulo** (D10-8,
  decisa il 2026-10-09). Le conversioni restano qui (`convert_coordinates`,
  `propagate_position`); gli offset angolari e il calcolo inverso (posizione
  da distanza + angolo di posizione) sono in `17-core-misure.md`; la
  calcolatrice H4 di `18-core-calcolatrici.md` usa i moduli 10 e 17.
- **Tutti i calcoli angolari interni sono in gradi `float64`**, con unità
  esplicite in ingresso e in uscita come da `02-convenzioni.md`.
- **Calibrazioni storiche (H25, sez. 8.2 del manuale di Aladin, ed. giugno 2022):**
  oltre alle soluzioni WCS standard si riconoscono le soluzioni astrometriche
  storiche delle lastre (metodo DSS1): molte lastre digitalizzate degli
  archivi hanno solo questa calibrazione e senza di essa resterebbero prive
  di coordinate. Il supporto in
  `astropy.wcs` è **da verificare prima del codice**; se manca, la scelta di
  come trattarle diventa una decisione da registrare. **Verificato il
  2026-10-09:** con astropy 8.0.1 (WCSLIB 8.6) un'intestazione DSS1 con
  coefficienti `AMDX`/`AMDY` viene tradotta da WCSLIB in una distorsione
  polinomiale TPD; sul file `dss.14.29.56-62.41.05.fits.gz` (dati di test di
  astropy) la posizione dell'oggetto dichiarata da STScI nell'intestazione
  (`OBJCTRA`/`OBJCTDEC` ↔ `OBJCTX`/`OBJCTY`) è riprodotta entro 0.010″.
- **Convenzione dei pixel (H25, DC7):** le coordinate pixel interne sono in
  convenzione numpy; la conversione da e verso la convenzione FITS avviene
  solo con `convert_pixel_convention` (§7).
- Righe di `03-parita-aladin.md` coperte qui: A2 (vai a per nome, con
  `resolve_name`), A3 (vai a coordinate), A4 (coordinate del cursore), A5
  (parte conversioni; offset e calcolo inverso nel 17, interfaccia nel 18),
  A6 (griglia: calcolo delle linee; disegno nel 41), A9, H6, H25.

## 4. Cosa NON fa

- Non visualizza nulla: non disegna griglie, cursori né etichette (spetta a
  `41-ui-visualizzatore-cielo.md`).
- Non legge né scrive file FITS: la WCS viene accettata come oggetto, la
  gestione dei file è di `11-core-immagini-fits.md`.
- Non scarica né memorizza cataloghi: il download è di `14-core-protocolli-vo.md`,
  la cache dei cataloghi di `13-core-cataloghi.md`.
- Non fa cross-match (`15-core-crossmatch.md`), non misura distanze per utente
  (`17-core-misure.md`), non gestisce MOC (`16-core-moc.md`).
- Non legge pixel e non calcola centroidi: le posizioni delle stelle per la
  calibrazione arrivano dall'`11` (D10-8).
- Non conserva le soluzioni astrometriche né gestisce annulla/ripeti (`24`,
  `40`): le restituisce come lista.
- Non calcola offset angolari né posizioni da distanza + angolo di posizione
  (`17`), non ha una propria calcolatrice (`18`).
- Non gestisce la cache: usa quella condivisa di `04-cache.md`.
- Non calcola nulla con l'IA: ogni numero è prodotto da Astropy/ERFA.

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `04-cache.md` (solo per la cache della risoluzione dei
  nomi); per tutto il resto nessuno (è il fondamento del livello 1).
- **Usato da:** `11-core-immagini-fits.md`, `12-core-hips.md`,
  `13-core-cataloghi.md`, `14-core-protocolli-vo.md`, `15-core-crossmatch.md`,
  `16-core-moc.md`, `17-core-misure.md`, `18-core-calcolatrici.md`,
  `19-core-dati-planetari.md`, `05-comandi-sessione.md` (comandi di vista
  e di coordinate), tutti i moduli di analisi (20–24),
  `33-ia-query-adql.md`, `41-ui-visualizzatore-cielo.md` (`make_view_wcs`,
  `choose_projection`, griglia, coordinate sotto il cursore,
  `compass_and_scale_bar`), `42-ui-pannello-cataloghi.md`
  (`format_coordinates`), `34-ia-verifica-risultati.md`
  (`format_coordinates`, `parse_sexagesimal`).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `name` | stringa | nome di oggetto (es. "M31") | per la risoluzione nomi |
| in | `ra`, `dec` | float64 | gradi, ICRS J2000 | RA ∈ [0,360), Dec ∈ [−90,+90] |
| in | `l`, `b` | float64 | gradi, sistema galattico | l ∈ [0,360), b ∈ [−90,+90] |
| in | `frame` | enumerativo | nome frame Astropy (`icrs`, `fk5`, `fk4`, `galactic`, `barycentricmeanecliptic`, …) | sempre esplicito; i frame con equinozio od `obstime` li richiedono espliciti |
| in | `equinox` / `obstime` | epoca | anno giuliano (es. 2000.0) o data ISO 8601 | sempre dichiarati quando rilevanti |
| in | `pm_ra_cosdec`, `pm_dec`, `parallax` | float64 | mas/yr, mas | per la propagazione |
| in | `wcs` | oggetto WCS | — | soluzione astrometrica di un'immagine |
| in | `x`, `y` | float64 | pixel (origini dichiarate: 0 o 1) | da pixel a coordinate |
| out | coordinate convertite | float64 | gradi + sistema + epoca dichiarati | mai coordinate "nude" |
| out | `name → coordinate` | float64 | gradi, ICRS | con fonte e data della richiesta |
| in | stelle di calibrazione | coppie | pixel (convenzione numpy, dall'`11`) ↔ coordinate celesti con frame | metodo per associazione di stelle |
| in | soglie di calibrazione | struttura | stelle minime, pixel | default D10-7, configurabili |
| in | passo della griglia | `Quantity` angolare | gradi (o altra unità angolare) | uno per le longitudini, uno per le latitudini; se omessi, scelti da `choose_grid_spacing` |
| in | `target_lines` | intero ≥ 1 | numero di linee desiderate per asse | default 5 (vedi §9) |
| in | campo di vista, soglia | `Quantity` angolare | gradi | per `choose_projection` (soglia di default 30°, D10-9) |
| in | centro, scala, dimensioni della finestra | posizione celeste; `Quantity` angolare per pixel; interi | gradi; pixel | per `make_view_wcs` |
| in | base o proiezione | WCS del 10 oppure codice di proiezione (+ frame, punto di tangenza) | — | per `make_view_wcs` |
| out | `ViewGeometry` | struttura | base, finestra, fattore e spostamento, raggio del campo in gradi | geometria per il `41` e per il 12 |
| in | posizioni o valori di un asse da scrivere | `SkyFrame` / `Quantity` angolare + frame + asse | gradi | per `format_coordinates` |
| in | stile, precisione, separatori | enumerativo; `Quantity` di tempo (RA) o angolare; enumerativo | — | default: sessagesimale con le cifre di DC3 |
| out | `FormattedCoordinates` | testi | sessagesimale o decimale, con frame, epoca e precisione usata | per il `41` e il `40` |
| in | geometria della vista, frame, lunghezza massima della barra | `ViewGeometry`; nome del frame; intero | pixel della finestra | per `compass_and_scale_bar` |
| out | `CompassScaleBar` | struttura | vettori unitari nord/est in pixel della finestra (convenzione numpy); lunghezza angolare della barra (`Quantity`) e in pixel della finestra (`float64`); etichetta | per il `41` |
| out | residui calibrazione | float64 | pixel e arcosecondi | RMS e massimo dichiarati, con le soglie usate |
| out | soluzioni astrometriche | lista | — | le precedenti + la nuova in coda |
| out | linee della griglia | lista | tratti in pixel (convenzione numpy) + valore della coordinata | geometria per il `41` |

## 7. Interfaccia pubblica

Funzioni e classi (nomi proposti, descrizione in parole, nessun codice):

- **`SkyFrame`** (classe leggera): incapsula coordinate con sistema, epoca e
  unità; espone conversioni verso altri frame; non permette di creare
  coordinate senza unità.
- **`convert_coordinates(...)`** — converge coordinate tra frame e epoche;
  parametri: coordinate di origine, frame di partenza, frame/epoca di arrivo;
  restituisce coordinate con unità e frame di destinazione.
- **`resolve_name(name)`** — risolve un nome in coordinate ICRS; parametri:
  nome, opzione di fonte (solo `simbad`), cache comune, `refresh`;
  restituisce coordinate (epoca J2000 dichiarata) + identificativo
  principale SIMBAD + fonte + origine + data di scaricamento + "dalla cache
  sì/no" + incertezza dichiarata da SIMBAD se presente, o errore se non
  trovato o se la rete non risponde e il nome non è in cache. Cache e
  timeout: `04-cache.md`.
- **`wcs_from_header(header)`** / **`sky_to_pixel(...)`** / **`pixel_to_sky(...)`**
  — costruiscono la WCS da un header e fanno le trasformazioni in entrambe le
  direzioni. `wcs_from_header` restituisce la parte celeste della WCS con
  l'elenco delle correzioni applicate da WCSLIB (es. `NCP` → `SIN`, DSS →
  TPD); le trasformazioni lavorano in convenzione numpy e dichiarano frame,
  epoca e i punti fuori dal campo.
- **`convert_pixel_convention(x, y, from_convention, to_convention)`** —
  **unico punto di conversione** tra la convenzione FITS (indice da 1) e la
  convenzione numpy (indice da 0) prevista da DC7 di `02-convenzioni.md`:
  `x_fits = x_numpy + 1`, `y_fits = y_numpy + 1` (e inverso), valori anche
  non interi; le convenzioni ammesse sono `fits` e `numpy`; restituisce le
  coordinate con la convenzione di arrivo dichiarata. Ricorda che l'indice
  di array è `array[y_numpy, x_numpy]`. Usata da tutti i moduli che mostrano,
  leggono o scrivono coordinate pixel (elenco in DC7); internamente le
  coordinate pixel sono sempre in convenzione numpy.
- **`propagate_position(...)`** — propaga una posizione a un'epoca target con
  moto proprio e parallasse; restituisce posizione all'epoca richiesta e
  dichiara l'epoca usata. **Opzione esplicita `proper_motion_only=True`
  (decisione del proprietario del 2026-10-10, D13-12 del 13):** propagazione
  **solo con il moto proprio**, senza parallasse né velocità radiale (se
  passate: `PROPAGATION_MODE_CONFLICT`) e quindi **senza effetti
  prospettici**: `SkyCoord` senza distanza e `apply_space_motion` di
  astropy (ERFA `pmsafe` usa una distanza di ripiego e lo segnala: l'avviso
  si riporta nel risultato); il risultato è **marcato**
  (`PropagatedPosition.proper_motion_only = True` e nota esplicita). Per
  default (`False`) parallasse obbligatoria e positiva come prima.
- **`parse_sexagesimal(values, *, hours)`** — angoli sessagesimali scritti
  come testo (es. `00 13 00.93`, `12:30:15.5`) in gradi, con
  `astropy.coordinates.Angle`: `hours=True` per l'ascensione retta (ore),
  `False` per gli angoli in gradi; testo non leggibile →
  `COORD_FORMAT_INVALID`. Aggiunta il 2026-10-10 per D13-14 (lettura
  ASTRORES del 13) ed è anche il punto unico per i sessagesimali del 18.
- **`astrometric_calibration(...)`** — determina/rifinisce la soluzione
  astrometrica (H6) con uno dei tre metodi di D10-1: **parametri** (posizione
  e pixel di riferimento, scala, rotazione, proiezione, verso
  dell'ascensione retta), **associazione di stelle** (coppie pixel ↔ cielo
  ricevute dall'`11`, procedura e controlli di D10-7) o **intestazione WCS**.
  Riceve anche la lista delle soluzioni già calcolate per l'immagine e
  restituisce **la lista con la nuova soluzione in coda**; ogni soluzione
  porta metodo, proiezione, residui (RMS e massimo in pixel e arcosecondi,
  se ci sono stelle), soglie usate ed elenco delle stelle peggiori.
- **`compute_grid_lines(...)`** — geometria della griglia di coordinate (A6):
  parametri: WCS, dimensioni dell'immagine, frame della griglia (con
  epoca se il frame la richiede), passo in longitudine e in latitudine;
  restituisce l'elenco di meridiani e paralleli, ciascuno con il valore
  della coordinata e i tratti visibili come coordinate pixel (convenzione
  numpy). Nessun disegno (`41`). Se i due passi sono omessi li sceglie
  `choose_grid_spacing`; se ne è dato uno solo, errore.
- **`choose_grid_spacing(...)`** — passo automatico della griglia in base al
  campo visibile: parametri: WCS, dimensioni dell'immagine,
  frame della griglia (con epoca se il frame la richiede), numero di linee
  desiderate per asse; misura l'estensione in longitudine e in latitudine
  del campo nel frame della griglia (360° in longitudine se un polo è nel
  campo) e per ogni asse sceglie **il più piccolo passo "tondo" ≥
  estensione / linee desiderate** dagli elenchi di §9; restituisce i due
  passi, le estensioni misurate e l'elenco usato (orario o in arco).
- **`choose_projection(...)`** — sceglie la proiezione del campo: `TAN` se
  il campo di vista è minore della soglia, `AIT` altrimenti; **soglia di
  default 30°** (D10-9, decisa il 2026-10-15), sempre scritta nel risultato;
  una soglia esplicita resta possibile (il `41` passa 33° o 27° per lo
  scarto di ±10 %). Campo di vista = diametro del cerchio che contiene la
  vista (due volte il raggio del campo di `ViewGeometry`).
- **`make_view_wcs(center, scale, shape, *, projection=None, frame="icrs",
  tangent_point=None, base=None)`** (aggiunta il 2026-10-15) — geometria
  della vista per il `41`, restituita come **`ViewGeometry`**. Parametri:
  `center` posizione celeste del centro della finestra (con frame);
  `scale` angolo per pixel della finestra (`Quantity` angolare > 0),
  riferito al pixel di riferimento della base; `shape` dimensioni della
  finestra in pixel (righe, colonne; interi ≥ 1). Due modi:
  - **senza `base`** (vista del cielo): crea una base nuova con
    `projection` obbligatoria tra `TAN`, `SIN`, `AIT`, `ZEA`, `STG`, `CAR`
    (elenco D10-4 senza `NCP`, forma storica di `SIN`, e senza `ZPN`, che
    richiede coefficienti: `PROJECTION_UNSUPPORTED` con il motivo), `frame`
    `icrs` o `galactic`, punto di tangenza `tangent_point` (di default il
    centro), scala della base = `scale`, nord in alto ed est a sinistra
    (`CDELT1` = −scala, `CDELT2` = +scala), pixel di riferimento nel pixel
    (0, 0) in convenzione numpy (FITS (1, 1), DC7), `LONPOLE`/`LATPOLE`
    secondo le regole di default dello standard FITS WCS (Paper II),
    applicate da WCSLIB e dichiarate;
  - **con `base`** (il WCS di un'immagine dell'11, o una base creata prima
    con il primo modo): la base non cambia; `projection`, `frame` e
    `tangent_point` non si danno (altrimenti `VIEW_PARAMETERS_INVALID`).
  In entrambi i modi `ViewGeometry` contiene: la **base**; proiezione,
  frame e punto di tangenza; la **scala della base** al suo pixel di
  riferimento (per un'immagine da `astropy.wcs.utils.proj_plane_pixel_scales`,
  media geometrica dei due assi, metodo dichiarato); centro, scala e
  dimensioni della finestra; il **fattore** (pixel della finestra per pixel
  della base = scala della base / `scale`) e l'**origine** (pixel della
  base, convenzione numpy, che corrisponde al pixel (0, 0) della finestra,
  scelta in modo che `center` cada al centro della finestra); le funzioni
  **`window_to_sky`** e **`sky_to_window`** (trasformazione lineare verso i
  pixel della base, poi `pixel_to_sky`/`sky_to_pixel` della base: esatte
  anche con le distorsioni del WCS dell'immagine, es. SIP o DSS → TPD);
  il **WCS della regione visibile** (la base con il pixel di riferimento
  spostato all'origine della regione visibile in pixel della base, senza
  cambiare scala né distorsioni) e le sue dimensioni, per
  `compute_grid_lines`; il **raggio del campo** = massima distanza
  angolare (`astropy.coordinates`) tra il centro e i punti del bordo della
  finestra campionati con 64 punti per lato, oppure **180°** se un punto
  del bordo è fuori dalla proiezione (es. bordo dell'`AIT`), con il metodo
  dichiarato. Nessun disegno (`41`).
- **`format_coordinates(coords=None, *, values=None, frame=None,
  axis=None, style="sexagesimal", precision=None, separators="symbols")`**
  (aggiunta il 2026-10-15, D41-2) — scrive coordinate come testo per
  l'interfaccia e restituisce **`FormattedCoordinates`**. Ingresso:
  posizioni con frame (`coords`, anche più di una) oppure i valori di un
  solo asse (`values`, `Quantity` angolare) con `frame` e `axis`
  (`lon` o `lat`), per le etichette della griglia. Regole:
  - **frame equatoriali** (`icrs`, `fk5`, `fk4`): longitudine in **ore**
    (h m s, in [0h, 24h)), latitudine in **gradi** con segno (± d ′ ″);
    **altri frame** (galattico, eclittici): longitudine in gradi in [0°,
    360°) senza segno, latitudine in gradi con segno;
  - **precisione di default = DC3:** RA a **0.01 s**, Dec a **0.1″**;
    longitudini e latitudini degli altri frame a **0.1″** (scelta minore 1
    di questa funzione); stile `decimal`: gradi con **6 decimali** (≈
    0.0036″, non meno fine di DC3; scelta minore 2);
  - **`precision` esplicita** (es. il passo della griglia): si scrive la
    forma più corta il cui ultimo campo non è più grossolano della
    precisione (passo 10′ → gradi e primi; passo 1 s → h m s senza
    decimali; 0.01 s → due decimali);
  - **arrotondamento** di presentazione (`02` §6) con riporto tra i campi
    (59.996 s → minuto successivo) e **ritorno a 0h** a 24h e a 0° a 360°;
    il **segno** della latitudine è quello del valore prima
    dell'arrotondamento (−0.04″ → "−00°00′00.0″", l'emisfero non si perde);
  - **separatori:** simboli (`h m s`, `° ′ ″`) di default, oppure i due punti
    (`separators="colons"`); **punto decimale** sempre (A9);
  - il risultato porta i testi per asse, frame ed epoca dei dati (mai
    assunta), stile e precisione usati. **Calcolo:**
    `astropy.coordinates.Angle.wrap_at` e `Angle.to_string`; nessuna
    formula scritta a mano. **Verificato il 2026-10-16 (astropy 8.0.1):**
    `Angle.to_string` fa il riporto tra i campi ma **non** il ritorno a 0
    (scrive "24h00m00.00s" e "360°00′00.0″"): il ritorno si fa nel codice
    riscrivendo con `Angle` il valore 0, dichiarato nel codice. Il segno si
    scrive con il trattino ASCII (`-`, `+`), copiabile come chiede A9 (il
    "−" degli esempi è tipografico).

- **`compass_and_scale_bar(geometry, *, frame=None, max_bar_pixels=None)`**
  (aggiunta il 2026-10-16, A7) — restituisce **`CompassScaleBar`**.
  `geometry` è la `ViewGeometry` di `make_view_wcs`; `frame` (`icrs`,
  `galactic` o un altro frame dell'elenco di questo modulo; default: il
  frame della vista) è il sistema in cui si intende "nord";
  `max_bar_pixels` (intero ≥ 1) è la lunghezza massima della barra in pixel
  della finestra (default: un quinto della larghezza della finestra,
  arrotondato per difetto; scelta minore 3 di questa funzione). Regole:
  - **punto di riferimento:** il centro della finestra (`center` di
    `ViewGeometry`);
  - **nord ed est:** con `SkyCoord.directional_offset_by` si prendono i
    punti a distanza δ dal centro con angolo di posizione 0° (nord) e 90°
    (est) nel `frame`, con **δ = 10 pixel della finestra alla scala della
    finestra** (dichiarato); `sky_to_window` dà i loro pixel; i **vettori
    unitari** dal centro a quei pixel (convenzione numpy della finestra:
    x = colonna, y = riga) sono le direzioni restituite, insieme a
    `east_left` (vero se l'est sta a sinistra del nord guardando lo schermo,
    dal segno del prodotto vettoriale). Se il polo del `frame` dista dal
    centro meno di δ, o un punto cade fuori dalla proiezione, nessuna
    direzione: avviso **`NORTH_UNDEFINED`** con il motivo;
  - **barra di scala:** per ogni valore tondo dell'elenco **in arco** di
    `choose_grid_spacing` (§9, da 0.01″ a 90°) si cerca la lunghezza L in
    pixel della finestra di un **segmento orizzontale centrato nel centro
    della finestra** i cui estremi (con `window_to_sky`) distano
    esattamente quel valore (distanza angolare con
    `SkyCoord.separation`; L trovata con `scipy.optimize.brentq` entro
    1e-6 pixel); si sceglie il **valore più grande con L ≤
    `max_bar_pixels`**. Se nemmeno il più piccolo ci sta, si usa il più
    piccolo e lo si dichiara (`SCALE_BAR_TOO_LONG`); un valore i cui estremi
    escono dalla proiezione non si usa;
  - **etichetta:** il valore tondo con il suo simbolo (`″`, `′`, `°`) e la
    rappresentazione più breve (es. "0.01″", "15′", "1°"), punto decimale;
  - **validità:** la barra vale al centro; con proiezione `AIT` o raggio
    del campo maggiore di 15° (campo oltre i 30° di D10-9) il risultato ha
    `local_only` = vero, che il `41` scrive "al centro";
  - il risultato porta frame, δ, metodo e i valori usati. Nessun disegno
    (`41`).

La calcolatrice delle coordinate (A5) non è più in questo modulo (D10-8): le
sue funzioni sono `convert_coordinates` e `propagate_position` qui, gli
offset e il calcolo inverso in `17-core-misure.md`, l'interfaccia in
`18-core-calcolatrici.md`.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `astropy.coordinates` | tutte le conversioni, precessione, propagazione con moto proprio | standard de facto, implementa le trasformazioni IAU |
| `astropy.units` | unità e `Quantity` ovunque | niente angoli senza unità |
| `astropy.wcs` | lettura/applicazione delle soluzioni WCS | standard di fatto per FITS WCS |
| `astropy.erfa` (via Astropy) | trasformazioni di riferimento a basso livello | librerie IAU verificate |
| `astropy.wcs.utils.fit_wcs_from_points` (richiede `scipy`) | calibrazione per associazione di stelle (D10-1, D10-7) | adattamento consolidato di Astropy |
| `numpy` | campionamento delle linee della griglia, residui | consolidato |
| `astroquery.simbad` | risoluzione dei nomi | servizio CDS ufficiale |
| Standard FITS WCS (paper I/IV) | struttura delle soluzioni | standard IAU/OHSA |

## 9. Regole e vincoli

- Sistema predefinito **ICRS**; **le epoche non si assumono mai**: si leggono
  dai metadati del dato (D10-2 decisa il 2026-10-04; regola in
  `02-convenzioni.md` DC2). Epoca di visualizzazione = **epoca dell'immagine se
  nota, altrimenti J2000**; ogni catalogo ha la propria epoca di riferimento;
  ogni output riporta l'epoca usata.
- Internamente gradi `float64`; nessun arrotondamento prima del display.
- Nessuna conversione scritta a mano: solo Astropy/ERFA (regola d'oro n. 4).
- Ogni output riporta frame, epoca e unità; un output senza frame è un errore.
- **Epoche dei frame:** se il frame prevede un equinozio (`fk5`, `fk4`, i
  frame eclittici…) o un `obstime`, va dato in modo esplicito: i valori di
  default di Astropy non si usano (errore `EPOCH_REQUIRED`). Fa eccezione
  solo la WCS letta da un header: lì valgono le regole di default dello
  standard FITS WCS (Paper II, `RADESYS`/`EQUINOX`), applicate da WCSLIB e
  dichiarate nel risultato.
- **Calibrazione per associazione di stelle (D10-7):** soglie di default 6
  stelle per `TAN`/`STG` e 10 per le altre proiezioni, RMS ≤ 1 pixel,
  residuo massimo ≤ 3 pixel, scostamento al centro ≤ 5 × RMS della soluzione
  `TAN`; configurabili, sempre scritte nel risultato. `ZPN` richiede i
  coefficienti della proiezione (`PV2_m`) espliciti: non si adattano e non
  si assumono (confermato dal proprietario il 2026-10-09).
- **Passo automatico della griglia (`choose_grid_spacing`):** per ogni asse
  il più piccolo valore "tondo" ≥ estensione del campo / linee desiderate
  (default **5** linee per asse). Valori tondi **in arco** (latitudini e
  longitudini dei frame non equatoriali): 0.01″, 0.02″, 0.05″, 0.1″, 0.2″,
  0.5″, 1″, 2″, 5″, 10″, 15″, 30″, 1′, 2′, 5′, 10′, 15′, 30′, 1°, 2°, 5°,
  10°, 15°, 30°, 45°, 90°; **in tempo** (ascensione retta dei frame
  equatoriali): 0.001 s, 0.002 s, 0.005 s, 0.01 s, 0.02 s, 0.05 s, 0.1 s,
  0.2 s, 0.5 s, 1 s, 2 s, 5 s, 10 s, 15 s, 30 s, 1 m, 2 m, 5 m, 10 m, 15 m,
  30 m, 1 h, 2 h, 3 h, 4 h, 6 h (1 s = 15″). Se l'estensione richiede più
  del valore massimo, si usa il massimo. Elenchi e numero di linee:
  **confermati dal proprietario il 2026-10-09**. **Motivazione (nostra):**
  poche linee per asse (5) non coprono l'immagine e lasciano spazio alle
  etichette; i valori tondi (1, 2, 5 per decade e le suddivisioni
  sessagesimali 15, 30, 45) danno etichette brevi e facili da leggere in
  gradi o in ore. Il confronto dei risultati con Aladin resta **da fare con
  AP1** (validazione finale della parità: confronto, non copia).
- **Interpretazioni confermate dal proprietario il 2026-10-09:**
  `wcs_from_header` accetta anche le proiezioni di WCSLIB fuori dall'elenco
  D10-4 (l'elenco limita calibrazione e scelta della proiezione, non la
  lettura dei dati); i frame con `obstime` lo richiedono esplicito (es. FK4:
  equinozio e `obstime`), salvo le coordinate di una WCS letta da header;
  senza velocità radiale la propagazione usa 0 km/s (ERFA) e lo dichiara in
  una nota del risultato; `ZPN` richiede i `PV2_m` espliciti.
- **Proiezioni celesti (D10-4 decisa il 2026-10-04):** stessa lista di
  proiezioni di Aladin secondo il manuale utente ed. giugno 2022 (sez. 5.14):
  `SIN`, `TAN`, `AIT`, `ZEA`, `STG`, `CAR`, `NCP`, `ZPN` (precisata il 2026-10-08; il manuale chiude l'elenco con
  "…": eventuali altre proiezioni **da verificare con la documentazione
  ufficiale**; supporto di `NCP` in `astropy.wcs` **verificato il
  2026-10-09**: WCSLIB lo traduce, come prevede lo standard FITS WCS Paper
  II, in `SIN` con `PV2_2 = cot δ₀`, round-trip pixel ↔ cielo entro 1.3e-9
  pixel); default **`TAN` per le immagini** e **`AIT` per le viste a cielo
  intero**; **un test per proiezione** (§12).
- La risoluzione nomi è un'operazione di rete: timeout dichiarato, errore
  esplicito se offline; nessun nome risolto "approssimativamente"; i risultati
  si cacheano nella tabella SQLite separata della cache A7 (D10-3).
- Le conversioni devono essere deterministe e riproducibili: stesso input,
  stessa libreria, stesso output (test di round-trip in §12).
- Prestazioni: conversioni di massa (migliaia di posizioni) in tempi da
  misurare nei test di accettazione del modulo (valore: decisione D10-6,
  Gruppo 3, da fissare con `61-strategia-test.md`).

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Nome non trovato | nessuna coordinata prodotta, messaggio con il nome e la fonte interrogata | `NAME_NOT_FOUND` |
| Rete assente durante la risoluzione nomi | errore esplicito, nessun valore inventato | `NET_TIMEOUT` |
| Dec fuori [−90,+90] o RA fuori intervallo | rifiuto dell'input prima del calcolo | `COORD_OUT_OF_RANGE` |
| Header senza WCS o WCS incoerente (matrice di scala singolare, andata e ritorno al centro oltre 1e-6 pixel, matrice CD tutta nulla — che WCSLIB sostituirebbe in silenzio con l'identità) | la WCS non viene costruita; l'immagine si apre solo come griglia di pixel | `WCS_MISSING` / `WCS_INVALID` |
| Conversione a un frame sconosciuto | errore con elenco dei frame supportati | `FRAME_UNSUPPORTED` |
| Epoca mancante dove richiesta (es. propagazione) | errore che chiede l'epoca: **l'epoca non si assume mai** (D10-2) | `EPOCH_REQUIRED` |
| Testo sessagesimale non leggibile in `parse_sexagesimal` | nessun valore prodotto, errore con il testo | `COORD_FORMAT_INVALID` |
| `proper_motion_only=True` con parallasse o velocità radiale | rifiuto: le due modalità non si mescolano | `PROPAGATION_MODE_CONFLICT` |
| Fuori campo (pixel → cielo) | valore restituito con avviso "fuori dal campo" | `OUT_OF_FIELD` |
| Convenzione pixel diversa da `fits` o `numpy`, o mancante | rifiuto: la convenzione non si assume | `PIXEL_CONVENTION_UNKNOWN` |
| Intestazione con soluzione storica (DSS1) non supportata dalla libreria | nessuna WCS costruita, l'immagine si apre come griglia di pixel con avviso che indica il tipo di soluzione | `WCS_LEGACY_UNSUPPORTED` |
| Valore angolare senza unità | rifiuto: nessun angolo senza unità | `COORD_UNIT_MISSING` |
| Proiezione fuori dall'elenco D10-4 | rifiuto con l'elenco delle proiezioni supportate | `PROJECTION_UNSUPPORTED` |
| `ZPN` senza coefficienti `PV2_m` | rifiuto: i coefficienti non si assumono | `PROJECTION_PARAMETERS_MISSING` |
| Calibrazione con meno stelle del minimo | nessuna soluzione; messaggio con stelle date e minimo richiesto | `CALIB_TOO_FEW_STARS` |
| Residui oltre le soglie | nessuna soluzione; messaggio con RMS, massimo, soglie e stelle peggiori | `CALIB_RESIDUALS_TOO_LARGE` |
| Soluzione finale incoerente con la `TAN` al centro del campo | nessuna soluzione; messaggio con scostamento e soglia | `CALIB_INCONSISTENT` |
| Adattamento che non converge | nessuna soluzione, messaggio della libreria | `CALIB_FIT_FAILED` |
| Passo della griglia non positivo o senza unità | rifiuto | `GRID_SPACING_INVALID` |
| `make_view_wcs` con scala non positiva o senza unità, dimensioni non intere o < 1, `base` insieme a `projection`/`frame`/`tangent_point`, `projection` mancante senza `base` | rifiuto con il parametro | `VIEW_PARAMETERS_INVALID` |
| `make_view_wcs` con `NCP` o `ZPN` | rifiuto con il motivo (forma storica di `SIN`; coefficienti richiesti) | `PROJECTION_UNSUPPORTED` |
| `format_coordinates` con precisione non positiva, senza unità o di unità non adatta (tempo per una latitudine) | rifiuto con il parametro | `FORMAT_PRECISION_INVALID` |
| `format_coordinates` senza frame, con `values` senza `axis`, o con frame sconosciuto | rifiuto | `FRAME_UNSUPPORTED` / `COORD_UNIT_MISSING` |
| `compass_and_scale_bar` con il polo del frame entro δ dal centro o direzione fuori dalla proiezione | nessuna direzione, barra calcolata se possibile, avviso con il motivo | `NORTH_UNDEFINED` (avviso) |
| `compass_and_scale_bar` con il più piccolo valore tondo più lungo di `max_bar_pixels` | barra del valore più piccolo, dichiarata | `SCALE_BAR_TOO_LONG` (avviso) |
| `compass_and_scale_bar` con `max_bar_pixels` < 1 o non intero, frame sconosciuto | rifiuto | `VIEW_PARAMETERS_INVALID` / `FRAME_UNSUPPORTED` |

### Parametri dei messaggi (D40-3)

Dal 2026-10-24 (sprint 8b) ogni errore e ogni avviso del modulo nasce come **codice + `params`**
(`CoordinatesWcsError(code, message, params=...)`; gli avvisi di `compass_and_scale_bar` sono `ModuleWarning(code, text, params)`, una coppia (codice, testo) con in più `params`): `params` è un
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

| Codice | `reason` | Parametri (`params`) |
|---|---|---|
| `PIXEL_CONVENTION_UNKNOWN` | (generale) | `value` (string), `allowed` (list) |
| `FRAME_UNSUPPORTED` | (generale) | `frame` (string), `supported` (list) |
| `FRAME_UNSUPPORTED` | `no_attribute` | `frame` (string), `attribute` (string) |
| `FRAME_UNSUPPORTED` | `conversion_failed` | `from_frame` (string), `to_frame` (string), `detail` (string, esterno) |
| `FRAME_UNSUPPORTED` | `equatorial_required` | `frame` (string) |
| `FRAME_UNSUPPORTED` | `not_for_view` | `frame` (string), `allowed` (list) |
| `FRAME_UNSUPPORTED` | `differs_from_coordinates` | `frame` (string), `coordinates_frame` (string) |
| `FRAME_UNSUPPORTED` | `frame_required` | — |
| `EPOCH_REQUIRED` | (generale) | — |
| `EPOCH_REQUIRED` | `invalid_value` | `argument` (string), `value` (string) |
| `EPOCH_REQUIRED` | `explicit_required` | `frame` (string), `attribute` (string) |
| `EPOCH_REQUIRED` | `frame_default` | `frame` (string), `attribute` (string) |
| `EPOCH_REQUIRED` | `not_time` | — |
| `EPOCH_REQUIRED` | `origin_unknown` | — |
| `EPOCH_REQUIRED` | `missing_for_propagation` | `argument` (string) |
| `EPOCH_REQUIRED` | `target_missing` | — |
| `COORD_UNIT_MISSING` | (generale) | — |
| `COORD_UNIT_MISSING` | `no_unit` | `argument` (string) |
| `COORD_UNIT_MISSING` | `not_angular` | `argument` (string), `unit` (string) |
| `COORD_UNIT_MISSING` | `skycoord_required` | — |
| `COORD_UNIT_MISSING` | `skyframe_required` | `argument` (string) |
| `COORD_UNIT_MISSING` | `single_skyframe_required` | `argument` (string) |
| `COORD_UNIT_MISSING` | `column_no_unit` | `column` (string) |
| `COORD_UNIT_MISSING` | `coordinates_required` | — |
| `COORD_UNIT_MISSING` | `coords_or_values` | — |
| `COORD_UNIT_MISSING` | `axis_required` | — |
| `COORD_OUT_OF_RANGE` | (generale) | — |
| `COORD_OUT_OF_RANGE` | `not_finite` | — |
| `COORD_OUT_OF_RANGE` | `latitude_range` | `values` (quantity) |
| `COORD_OUT_OF_RANGE` | `longitude_range` | `values` (quantity) |
| `COORD_OUT_OF_RANGE` | `parallax_not_positive` | — |
| `COORD_OUT_OF_RANGE` | `fov_threshold_positive` | — |
| `NAME_NOT_FOUND` | (generale) | `name` (string) |
| `NAME_NOT_FOUND` | `empty_name` | — |
| `NAME_NOT_FOUND` | `source_unsupported` | `source` (string) |
| `NAME_NOT_FOUND` | `ambiguous` | `name` (string) |
| `NAME_NOT_FOUND` | `no_coordinates` | `name` (string) |
| `NET_TIMEOUT` | (generale) | `service` (string), `target` (string), `connect` (quantity), `read` (quantity), `detail` (string, esterno) |
| `NET_TIMEOUT` | `url` | `url` (string), `connect` (quantity), `read` (quantity), `detail` (string, esterno) |
| `COORD_FORMAT_INVALID` | (generale) | `detail` (string, esterno) |
| `PROPAGATION_MODE_CONFLICT` | (generale) | — |
| `WCS_INVALID` | (generale) | — |
| `WCS_INVALID` | `singular_matrix` | — |
| `WCS_INVALID` | `not_coherent` | `tolerance` (quantity) |
| `WCS_INVALID` | `cd_all_zero` | — |
| `WCS_INVALID` | `not_constructible` | `detail` (string, esterno) |
| `WCS_INVALID` | `pixel_shape_required` | — |
| `WCS_INVALID` | `east_left_required` | — |
| `WCS_INVALID` | `scale_not_positive` | — |
| `WCS_INVALID` | `no_valid_pixels` | — |
| `WCS_INVALID` | `method_unknown` | `method` (string), `allowed` (list) |
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
| `WCS_LEGACY_UNSUPPORTED` | (generale) | `legacy` (string) |
| `WCS_LEGACY_UNSUPPORTED` | `library_failed` | `legacy` (string), `detail` (string, esterno) |
| `PROJECTION_UNSUPPORTED` | (generale) | `projection` (string), `supported` (list) |
| `PROJECTION_UNSUPPORTED` | `not_for_view_ncp` | `projection` (string) |
| `PROJECTION_UNSUPPORTED` | `not_for_view_zpn` | `projection` (string) |
| `PROJECTION_UNSUPPORTED` | `not_for_view` | `projection` (string), `allowed` (list) |
| `PROJECTION_PARAMETERS_MISSING` | (generale) | — |
| `CALIB_INCONSISTENT` | (generale) | `deviation` (quantity), `factor` (number), `limit` (quantity) |
| `CALIB_TOO_FEW_STARS` | (generale) | `n_stars` (integer), `minimum` (integer), `projection` (string) |
| `CALIB_TOO_FEW_STARS` | `count_mismatch` | `pixel_positions` (integer), `sky_positions` (integer) |
| `CALIB_FIT_FAILED` | (generale) | `detail` (string, esterno) |
| `CALIB_RESIDUALS_TOO_LARGE` | (generale) | `rms` (quantity), `rms_threshold` (quantity), `maximum` (quantity), `maximum_threshold` (quantity), `worst_indices` (list), `worst_residuals` (quantity) |
| `GRID_SPACING_INVALID` | (generale) | — |
| `GRID_SPACING_INVALID` | `no_angular_unit` | `argument` (string) |
| `GRID_SPACING_INVALID` | `out_of_range` | `argument` (string), `value` (quantity) |
| `GRID_SPACING_INVALID` | `target_lines` | — |
| `GRID_SPACING_INVALID` | `both_or_none` | — |
| `GRID_SPACING_INVALID` | `samples` | `samples_per_line` (integer) |
| `VIEW_PARAMETERS_INVALID` | (generale) | — |
| `VIEW_PARAMETERS_INVALID` | `shape` | `shape` (string) |
| `VIEW_PARAMETERS_INVALID` | `scale_unit` | — |
| `VIEW_PARAMETERS_INVALID` | `scale_positive` | — |
| `VIEW_PARAMETERS_INVALID` | `center_skyframe` | — |
| `VIEW_PARAMETERS_INVALID` | `base_exclusive` | — |
| `VIEW_PARAMETERS_INVALID` | `projection_required` | — |
| `VIEW_PARAMETERS_INVALID` | `tangent_skyframe` | — |
| `VIEW_PARAMETERS_INVALID` | `center_outside_projection` | — |
| `VIEW_PARAMETERS_INVALID` | `geometry_required` | — |
| `VIEW_PARAMETERS_INVALID` | `max_bar_pixels` | — |
| `FORMAT_PRECISION_INVALID` | (generale) | — |
| `FORMAT_PRECISION_INVALID` | `decimal_needs_angle` | `unit` (string) |
| `FORMAT_PRECISION_INVALID` | `ra_unit` | `unit` (string) |
| `FORMAT_PRECISION_INVALID` | `unit_unsuitable` | `axis` (string), `unit` (string) |
| `FORMAT_PRECISION_INVALID` | `not_positive` | — |
| `FORMAT_PRECISION_INVALID` | `style_unknown` | `style` (string), `allowed` (list) |
| `FORMAT_PRECISION_INVALID` | `separators_unknown` | `separators` (string), `allowed` (list) |
| `FORMAT_PRECISION_INVALID` | `no_unit` | — |
| `NORTH_UNDEFINED` | (generale) | — |
| `NORTH_UNDEFINED` | `center_outside` | — |
| `NORTH_UNDEFINED` | `pole_near` | `frame` (string), `delta` (quantity) |
| `NORTH_UNDEFINED` | `direction_outside` | — |
| `SCALE_BAR_TOO_LONG` | (generale) | `step` (quantity), `max_bar_pixels` (integer) |
| `OUT_OF_FIELD` | (generale) | — |

## 11. Esposizione all'IA

Il modulo espone strumenti deterministici; **l'IA non calcola coordinate**:
propone i parametri e interpreta il risultato.

- **`resolve_name`** — input: nome oggetto; output: coordinate ICRS + fonte.
  Calcolo: SIMBAD via `astroquery`.
- **`convert_coordinates`** — input: coordinate, frame/epoca sorgente e target;
  output: coordinate convertite. Calcolo: `astropy.coordinates`.
- **`propagate_position`** — input: posizione, moto proprio, parallasse, epoca
  target; output: posizione all'epoca target. Calcolo: Astropy.
- **`wcs_pixel_to_sky`** — input: WCS + pixel; output: coordinate. Calcolo:
  `astropy.wcs`.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Round-trip ICRS → galattico → ICRS | convertire un campo di 1000 coordinate casuali con semina fissa in galattico e tornare a ICRS | scostamento massimo < 1e-9 gradi (limite numerico `float64`) | ricalcolo con `astropy.coordinates` nel test |
| T2 | Conversione nota | convertire le coordinate di una sorgente presa da SIMBAD (fonte scelta dal tester) da ICRS a galattico | coincidenza con il valore ricalcolato dallo stesso test con Astropy, entro 1e-9 gradi | confronto con `astropy.coordinates` + seconda lettura da SIMBAD |
| T3 | Round-trip pixel ↔ cielo | costruire la WCS da un header FITS di prova, passare da pixel a cielo e ritorno | errore < 1e-6 pixel | ricalcolo con `astropy.wcs` |
| T4 | Propagazione con moto proprio | propagare una posizione con moto proprio noto (valori presi dal tester da un catalogo Gaia) a un'epoca +10 anni | coincidenza con `SkyCoord.apply_space_motion` calcolata nel test | ricalcolo con Astropy |
| T5 | Risoluzione nome | `resolve_name("M31")` con rete disponibile | coordinate coerenti con quelle di SIMBAD entro la precisione dichiarata da SIMBAD | confronto incrociato con SIMBAD (test marcato di rete); nei test di default, risposte simulate di SIMBAD: prima la cache, `refresh`, nome non trovato o ambiguo, rete assente con e senza copia in cache, timeout applicati alla sessione HTTP, colonna senza unità |
| T6 | Input fuori range | passare Dec = 95° | errore `COORD_OUT_OF_RANGE`, nessun output numerico | test di unità |
| T7 | Una prova per proiezione (D10-4) | per ciascuna delle 8 proiezioni dell'elenco D10-4 (`SIN`, `TAN`, `AIT`, `ZEA`, `STG`, `CAR`, `NCP`, `ZPN`), convertire lo stesso campo pixel ↔ cielo | round-trip entro 1e-6 pixel per **ogni** proiezione; `TAN` di default per le immagini, `AIT` per le viste all-sky | ricalcolo con `astropy.wcs` per ciascuna proiezione |
| T8 | Convenzione dei pixel (DC7) | `convert_pixel_convention` su (1, 1) da `fits` a `numpy` e su (−0.5, −0.5) da `numpy` a `fits` | (0, 0) e (0.5, 0.5) | aritmetica esatta della regola DC7 |
| T9 | Round-trip delle convenzioni | 1000 coordinate pixel non intere (semina fissa) `numpy` → `fits` → `numpy` | identiche (differenza 0 in `float64` per valori rappresentabili) | test di unità |
| T10 | Coerenza con `astropy.wcs` | stessa posizione: `pixel_to_sky` in convenzione numpy (origine 0) e `wcs_pix2world` di `astropy.wcs` con origine 1 sulla coordinata convertita in FITS | stesse coordinate celesti entro 1e-12 gradi | ricalcolo con `astropy.wcs` |
| T11 | Convenzione non valida | `convert_pixel_convention` con convenzione `idl` o mancante | `PIXEL_CONVENTION_UNKNOWN` | test di unità |
| T12 | Calibrazione storica DSS1 (H25) | aprire un'intestazione DSS1 di prova e convertire alcuni pixel in coordinate | coordinate coincidenti con quelle di riferimento fornite con il file di prova; se la libreria non supporta il metodo, `WCS_LEGACY_UNSUPPORTED` | file di prova: `dss.14.29.56-62.41.05.fits.gz` dei dati di test di astropy; riferimento = posizione dell'oggetto scritta da STScI (`OBJCTRA`/`OBJCTDEC` ↔ `OBJCTX`/`OBJCTY`), tolleranza 0.02″ (arrotondamenti del riferimento) |
| T13 | Calibrazione per associazione di stelle (D10-7) | per ognuna delle 8 proiezioni: 30 stelle generate da una WCS nota, con e senza rumore di 0.2 pixel | soluzione accettata; scarto dalla WCS nota piccolo rispetto al rumore; soglie scritte nel risultato | ricalcolo con `astropy.wcs` della WCS nota |
| T14 | Caso dei 780″ (D10-7) | 6 stelle su `SIN` | errore `CALIB_TOO_FEW_STARS`, nessuna soluzione | test di unità |
| T15 | Residui oltre soglia | 30 stelle con una coppia sbagliata (stella scambiata) | `CALIB_RESIDUALS_TOO_LARGE` con la stella sbagliata tra le peggiori | test di unità |
| T16 | Controllo di coerenza | soluzione finale spostata al centro oltre 5 × RMS `TAN` | `CALIB_INCONSISTENT` | test di unità sul controllo |
| T17 | Metodi "parametri" e "intestazione" | costruire la soluzione dai parametri e dall'header | coincide con la WCS costruita dal test con `astropy.wcs` sugli stessi valori (1e-9 gradi) | ricalcolo con `astropy.wcs` |
| T18 | Lista delle soluzioni | due calibrazioni successive | lista di 2 soluzioni, le precedenti invariate | test di unità |
| T19 | Linee della griglia | griglia ICRS e galattica su un campo `TAN` | ogni punto di un meridiano/parallelo ha la coordinata dichiarata entro 1e-9 gradi e sta dentro l'immagine | ricalcolo con `astropy.wcs` + `astropy.coordinates` |
| T20 | Scelta della proiezione | `choose_projection` con campo sotto e sopra la soglia data dal test | `TAN` e `AIT` | test di unità |
| T21 | Unità ed epoche obbligatorie | coordinate senza unità; `fk5` senza equinozio | `COORD_UNIT_MISSING`; `EPOCH_REQUIRED` | test di unità |
| T23 | Passo automatico della griglia | `choose_grid_spacing` su un campo `TAN` di 2°, su un campo piccolo, con un polo nel campo e in galattico | per ogni asse il più piccolo valore tondo ≥ estensione / linee, con l'estensione ricalcolata nel test con `astropy.wcs`; campo più piccolo → passo non maggiore; polo → estensione 360°; `compute_grid_lines` senza passi usa questi | ricalcolo con `astropy.wcs` + elenchi di §9 |
| T24 | Propagazione solo con moto proprio | `propagate_position(..., parallax=None, proper_motion_only=True)` su posizioni con moto proprio noto; poi con una parallasse passata | posizioni uguali ad `apply_space_motion` di `SkyCoord` senza distanza (ricalcolo nel test, 1e-12 gradi); risultato marcato con nota; con parallasse `PROPAGATION_MODE_CONFLICT`; senza l'opzione la parallasse mancante resta un errore | ricalcolo con Astropy |
| T25 | Sessagesimali | `parse_sexagesimal` su ore (`00 13 00.93`, `12:30:15.5`) e gradi (`+72 31 19.9`, `-05:06:07`); testo non valido | gradi uguali ad `astropy.coordinates.Angle` ricalcolato nel test; `COORD_FORMAT_INVALID` | ricalcolo con Astropy |
| T22 | Fuori campo | `pixel_to_sky` su un pixel fuori dall'immagine | valore restituito con avviso `OUT_OF_FIELD` | test di unità |
| T26 | Vista del cielo (`make_view_wcs` senza base) | per `TAN`, `SIN`, `AIT`, `ZEA`, `STG`, `CAR`, in ICRS e galattico | base uguale al WCS costruito nel test con `astropy.wcs` sulle stesse parole chiave (1e-9 gradi su una griglia di pixel); `window_to_sky` del centro della finestra = `center` entro 1e-9 gradi; ritorno finestra → cielo → finestra entro 1e-6 pixel | ricalcolo con `astropy.wcs` |
| T27 | Vista su un'immagine con distorsioni | WCS con SIP e WCS DSS1 (T12); varie scale e centri | `window_to_sky(x, y)` = `pixel_to_sky` della base in `origine + (x, y) / fattore` entro 1e-12 gradi; WCS della regione visibile e base danno lo stesso cielo per pixel corrispondenti entro 1e-9 gradi | ricalcolo con il 10 e `astropy.wcs` |
| T28 | Raggio del campo | finestra `TAN` di campo noto; finestra `AIT` che mostra tutto il cielo | raggio = massimo delle distanze ricalcolate nel test con `astropy.coordinates` sugli stessi 4 × 64 punti del bordo; `AIT` con un angolo fuori dal cielo → 180° dichiarato | ricalcolo con Astropy |
| T29 | Soglia di default (D10-9) | `choose_projection` senza soglia con campo 29.999° e 30°; con soglia esplicita 33° | `TAN` e `AIT`; soglia usata scritta nel risultato; la soglia esplicita vale | test di unità |
| T31 | Scrittura con le cifre di DC3 (`format_coordinates`) | 1000 posizioni ICRS e galattiche casuali (semina fissa) | testi uguali a quelli prodotti nel test con `Angle.to_string` alle precisioni di DC3 (0.01 s, 0.1″); punto decimale; frame ed epoca nel risultato | ricalcolo con Astropy |
| T32 | Riporto, 24h e segno | RA 23h59m59.996s, RA 10h59m59.996s, Dec −0.04″, Dec +89°59′59.96″, l = 359.99999999° | "00h00m00.00s", "11h00m00.00s", "−00°00′00.0″", "+90°00′00.0″", "0°00′00.0″" | valori attesi scritti dalla regola di §7 |
| T33 | Precisione esplicita e stile decimale | etichette della griglia con passi 10′, 1 s, 0.01 s; stile `decimal`; separatori a due punti | forma più corta coerente con il passo; 6 decimali in gradi; due punti; precisione sbagliata → `FORMAT_PRECISION_INVALID` | test di unità |
| T34 | Nord ed est (`compass_and_scale_bar`) | viste `TAN` in ICRS e in galattico; vista su un'immagine ruotata di 30° con SIP; base con `CDELT1` positivo (est a destra) | vettori uguali a quelli ricalcolati nel test con `directional_offset_by` e `sky_to_window` (1e-9); `east_left` vero, vero, vero, falso | ricalcolo con Astropy e il 10 |
| T35 | Barra di scala | finestre `TAN` a scale diverse; `max_bar_pixels` 120 | gli estremi del segmento restituito distano il valore tondo entro 1e-9 gradi (ricalcolo con `SkyCoord.separation`); L ≤ 120 e il valore tondo successivo dell'elenco darebbe L > 120; etichetta attesa | ricalcolo con Astropy |
| T36 | Polo, `AIT`, casi limite | centro sul polo nord ICRS; vista `AIT` di tutto il cielo; scala minuscola; `max_bar_pixels` 0 | `NORTH_UNDEFINED`; `local_only` vero; `SCALE_BAR_TOO_LONG`; `VIEW_PARAMETERS_INVALID` | test di unità |
| T30 | Errori di `make_view_wcs` | scala 0, scala senza unità, dimensioni 0, `base` con `projection`, `NCP`, `ZPN` | `VIEW_PARAMETERS_INVALID`; `PROJECTION_UNSUPPORTED` | test di unità |

## 13. Decisioni aperte

- **D10-1 — Calibrazione astrometrica (H6): DECISA il 2026-10-09 (decisione
  del proprietario sulla checklist del livello 1).** I **tre metodi di
  Aladin** (manuale ed. giugno 2022, sez. 5.14): per **parametri** (posizione
  e pixel di riferimento, scala, proiezione, rotazione, verso dell'ascensione
  retta), per **associazione di stelle** (coppie pixel ↔ cielo con centroide
  baricentrico, soluzione con `astropy.wcs.utils.fit_wcs_from_points`) e per
  **intestazione WCS**; più soluzioni per immagine, annulla/ripeti. La
  risoluzione automatica "alla cieca" (es. astrometry.net) è un'estensione
  successiva, non prevista ora. **Da verificare prima del codice:** che
  `fit_wcs_from_points` copra le proiezioni dell'elenco D10-4 usate dalla
  calibrazione. **Esito del 2026-10-09: verifica NON superata**; risolta con
  D10-7 (decisa il 2026-10-09). Il centroide è dell'`11` e annulla/ripeti
  di `24`/`40` (D10-8).
- **D10-2 — Epoca per la propagazione: DECISA il 2026-10-04.** L'epoca di
  ogni dato si legge dai suoi metadati e **non si assume mai**; epoca di
  visualizzazione = epoca dell'immagine se nota, altrimenti J2000; l'epoca
  usata è sempre scritta nel risultato; i cataloghi hanno ciascuno la propria
  epoca di riferimento. **Motivazione:** nessuna epoca implicita (regola
  d'oro n. 6, riproducibilità) e una sola convenzione di progetto (DC2 di
  `02-convenzioni.md`, aggiornata). Applicata in §3/§9/§10 qui sopra.
- **D10-3 — Risoluzione nomi offline: DECISA il 2026-10-04.** Cache in una
  **tabella SQLite separata dentro la cache A7** (limite e provenienza unici
  come richiede A7, schema non condiviso con `13-core-cataloghi.md`).
  **Motivazione:** confine netto con il 13 e vincolo A7 rispettato. Applicata
  in §3/§9 qui sopra.
- **D10-4 — Proiezioni supportate: DECISA il 2026-10-04.** Stessa lista di
  proiezioni di Aladin secondo il manuale utente ed. giugno 2022 (sez. 5.14):
  `SIN`, `TAN`, `AIT`, `ZEA`, `STG`, `CAR`, `NCP`, `ZPN` (precisata il 2026-10-08; il manuale chiude l'elenco con
  "…": eventuali altre proiezioni **da verificare con la documentazione
  ufficiale**; supporto di `NCP` in `astropy.wcs` **verificato il
  2026-10-09**, vedi §9), default **`TAN` per le immagini** e **`AIT` per le viste a cielo
  intero**,
  **un test per proiezione** (T7). **Motivazione:** la parità documentale è
  il minimo (P11) e il test per proiezione verifica `astropy.wcs` in modo
  sistematico. Applicata in §9/§12 qui sopra.
- **D10-5 — Sorgenti di riferimento per H6:** quale catalogo usare come
  riferimento (Gaia, ecc.) e con quali limiti di magnitudine.
- **D10-6 — Prestazioni delle conversioni di massa:** tempo massimo per
  convertire migliaia di posizioni (valore e test misurabile). Da fissare al
  momento del codice insieme a `61-strategia-test.md` (Gruppo 3).
- **D10-7 — Calibrazione per associazione di stelle: DECISA il 2026-10-09
  (decisione del proprietario, opzione a).** Origine: la verifica di D10-1
  con astropy 8.0.1 — `fit_wcs_from_points` converge da sé solo per `TAN` e
  `STG`; `SIN`, `AIT`, `ZEA`, `CAR` falliscono ("Residuals are not finite in
  the initial point", stima iniziale CD = identità), `NCP` e `ZPN` non sono
  accettati come codici; partendo da un adattamento `TAN` convergono tutte,
  ma con 6 stelle `SIN` è arrivata in silenzio a una soluzione sbagliata
  (780″). **Decisione:** punto di partenza dal primo adattamento `TAN`, poi
  tre controlli obbligatori, configurabili e scritti nel risultato — stelle
  minime 6 (`TAN`/`STG`) o 10 (altre); RMS ≤ 1 pixel e residuo massimo ≤ 3
  pixel, con elenco delle stelle peggiori; scostamento al centro del campo
  tra soluzione finale e `TAN` ≤ 5 × RMS **della soluzione `TAN`**
  (precisazione del proprietario del 2026-10-09). Test T13–T16. Applicata in
  §3, §7, §9, §10, §12.
- **D10-8 — Parti del modulo senza interfaccia in §7: DECISA il 2026-10-09
  (decisione del proprietario).** (1) Nuove funzioni `compute_grid_lines`
  (geometria; disegno nel `41`) e `choose_projection` (`TAN` campi piccoli,
  `AIT` grandi; soglia in D10-9). (2) Cache: proposta AM1 accettata, nuovo
  file generale `04-cache.md` (cache A7 condivisa in
  `~/Library/Caches/AstroTwo/`); `resolve_name` si scrive dopo la sua
  approvazione. (3) Il modulo non riceve pixel: il centroide è nell'`11`, che
  passa le posizioni; le soluzioni multiple si restituiscono come lista,
  annulla/ripeti in `24` e `40`. (4) `coordinate_calculator` tolta: offset e
  calcolo inverso nel `17`, la calcolatrice del `18` usa `10` e `17`.
  Applicata in §3–§7, §10, §12.
- **D10-9 — Soglia di `choose_projection`: DECISA il 2026-10-15
  (decisione del proprietario, con il `41`).** **30°** di campo di vista
  (diametro del cerchio che contiene la vista), default della funzione e
  scritto nel risultato; lo **scarto di ±10 %** (33° in uscita da `TAN`, 27°
  in uscita da `AIT`) per evitare cambi continui vicino alla soglia è
  gestito dal `41`. **Motivazione (nostra):** la scala radiale della `TAN`
  cresce come 1/cos²θ (θ = metà campo): a 30° di campo l'aumento al bordo è
  del 7,2 %, a 60° del 33 %; oltre i 30° la distorsione diventa evidente.
  Applicata in §3, §6, §7, §12 (T29).
- **`format_coordinates` (D41-2, decisa dal proprietario il 2026-10-15):**
  nuova funzione per scrivere le coordinate con le cifre di DC3; §3, §6,
  §7, §10, §12 (T31–T33). **Scelte minori: CONFERMATE dal proprietario il 2026-10-16 (come raccomandate):** (1) 0.1″ anche
  per longitudini e latitudini dei frame non equatoriali (DC3 fissa solo RA
  e Dec); (2) 6 decimali in gradi nello stile decimale. **Codice scritto il
  2026-10-16** (commit `d1e4c0e`).
- **`compass_and_scale_bar` (A7 nella v1, decisione del proprietario del
  2026-10-16, opzione b della proposta della fase 1 sull'IA):** §3, §5,
  §6, §7, §10, §12 (T34–T36). **Scelte minori: CONFERMATE dal proprietario il 2026-10-16 (come raccomandate):** (3)
  lunghezza massima di default = un quinto della larghezza della finestra;
  (4) δ = 10 pixel della finestra; (5) "solo al centro" oltre 15° di raggio
  del campo o con `AIT`. **Codice scritto il 2026-10-16** (commit
  `d1e4c0e`).
- **`make_view_wcs` (2026-10-15, decisione del proprietario sulla
  proposta della fase 1 dell'interfaccia):** aggiunta perché il `41` non
  calcoli proiezioni; §3, §6, §7, §10, §12 (T26–T30). **Codice scritto il
  2026-10-16** con il default di D10-9 (commit `d1e4c0e`).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario: D10-2, D10-3 e D10-4 passate da aperte a decise.** D10-2: epoca letta dai metadati, mai assunta, epoca di visualizzazione = epoca dell'immagine se nota altrimenti J2000, epoca sempre scritta nel risultato, cataloghi con propria epoca di riferimento (§3/§9/§10; regola in `02-convenzioni.md` DC2). D10-3: cache dei nomi in tabella SQLite separata dentro A7 (§3/§9). D10-4: stessa lista di proiezioni di Aladin (da verificare con AP5), `TAN` default immagini, `AIT` viste all-sky, un test per proiezione (§9/§12-T7). `13-core-cataloghi.md` allineato su epoche e DataLink; decisioni riportate in `decisioni-aperte.md`. |
| 2026-10-04 | agente di sviluppo | Riferimenti AP5 aggiornati in §3 e §13 (D10-4): le sezioni ancora da leggere sono **5.7.3–8** (prima indicate 5.9–8), in linea con l'esito parziale di AP5 in `03-parita-aladin.md` (lette 1–5.7.2 e indice completo, ed. febbraio 2021). Nessun altro testo cambia. |
| 2026-10-08 | Claude Code | §3 e §13 (D10-4): riferimento AP5 scritto in forma uniforme ("AP5 decisa; lettura delle sezioni 5.7.3–8 ancora da fare") con l'edizione del manuale (giugno 2022, AP6). Nessun altro testo cambia. |
| 2026-10-08 | Claude Code | §3 e §13 (D10-4): riferimento AP5 aggiornato a "AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) ancora da fare" (con l'ed. giugno 2022 le sezioni 1–5.8 risultano già lette). |
| 2026-10-08 | Claude Code | §3 e §13 (D10-4): riferimento AP5 aggiornato a lettura completata, con rimando all'elenco delle proiezioni trovato nel manuale (riga A9 di `03-parita-aladin.md`). La lista di D10-4 non è stata cambiata. |
| 2026-10-08 | Claude Code | **D10-4 precisata (decisione del proprietario):** lista delle proiezioni = quella del manuale di Aladin ed. giugno 2022, sez. 5.14 (`SIN`, `TAN`, `AIT`, `ZEA`, `STG`, `CAR`, `NCP`, `ZPN`); resta un test per proiezione (T7, ora con l'elenco esplicito). Da verificare: eventuali proiezioni oltre l'elenco (il manuale chiude con "…") e il supporto di `NCP` in `astropy.wcs`. Testo aggiornato in §3 e §13. |
| 2026-10-08 | Claude Code | §5: aggiunti a "Usato da" i moduli `18-core-calcolatrici.md` e `19-core-dati-planetari.md` (scritti il 2026-10-08, stato bozza). Nessun altro testo cambia. |
| 2026-10-09 | Claude Code | §7: nuova funzione `convert_pixel_convention`, unico punto di conversione FITS (indice da 1) ↔ numpy (indice da 0) previsto da DC7 (confermata dal proprietario il 2026-10-08); §10: errore `PIXEL_CONVENTION_UNKNOWN`; §12: test T8–T11. |
| 2026-10-09 | Claude Code | **D10-1 DECISA** (checklist del livello 1): i tre metodi di calibrazione di Aladin (parametri, associazione di stelle con `fit_wcs_from_points`, intestazione WCS); risoluzione automatica rimandata; verifica sulle proiezioni prima del codice. §3, §7 aggiornati. Nuova **D10-6** (prestazioni delle conversioni di massa, Gruppo 3) al posto del rinvio senza etichetta in §9. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-09. |
| 2026-10-09 | Claude Code | Completamento dalla verifica di copertura di `03-parita-aladin.md` (decisione del proprietario del 2026-10-09): §3 calibrazioni storiche DSS1 (H25, supporto in `astropy.wcs` da verificare prima del codice), convenzione dei pixel (H25/DC7) e righe di parità coperte (A2–A6, A9, H6, H25); §10 errore `WCS_LEGACY_UNSUPPORTED`; §12 nuovo test. Nessuna nuova decisione dei Gruppi 1 e 2: stato `approvato` invariato. |
| 2026-10-09 | Claude Code | **Verifiche "da verificare prima del codice" eseguite** (FASE: CODICE – livello 1, astropy 8.0.1 / WCSLIB 8.6): `NCP` supportata (§9, D10-4); calibrazioni storiche DSS1 supportate, riproduzione del riferimento STScI entro 0.010″ (§3; file di prova candidato per T12: `dss.14.29.56-62.41.05.fits.gz` dei dati di test di astropy); **`fit_wcs_from_points` non copre `SIN`, `AIT`, `ZEA`, `CAR`, `NCP`, `ZPN`** → nuova **D10-7** (da decidere); lacune dell'interfaccia di §7 → nuova **D10-8** (da decidere). Codice del modulo non scritto in attesa delle decisioni. Stato `approvato` invariato (decisione del proprietario). |
| 2026-10-09 | Claude Code | **Decisioni del proprietario D10-7 e D10-8 applicate** (autorizzazione esplicita a modificare il file approvato): D10-7 = partenza da un adattamento `TAN` + tre controlli obbligatori (stelle minime 6/10, RMS ≤ 1 px e massimo ≤ 3 px, coerenza al centro ≤ 5 × RMS `TAN`), nuovi errori `CALIB_*`, test T13–T16; D10-8 = nuove `compute_grid_lines` e `choose_projection` (soglia: nuova **D10-9**, Gruppo 3), cache in `04-cache.md` (AM1 accettata; `resolve_name` dopo la sua approvazione), centroide nell'`11` e soluzioni come lista (annulla/ripeti in `24`/`40`), `coordinate_calculator` tolta (offset e calcolo inverso nel `17`). Precisate le epoche dei frame (§9), aggiunti `COORD_UNIT_MISSING`, `PROJECTION_UNSUPPORTED`, `PROJECTION_PARAMETERS_MISSING`, `GRID_SPACING_INVALID`; T12 con il file di prova individuato; test T17–T22. Esempio di frame in §6 corretto (`ecliptic` non è un nome di frame di Astropy). Stato `approvato` invariato. |
| 2026-10-09 | Claude Code | **Codice scritto** (FASE: CODICE – livello 1): `src/astrotwo/core/coordinates_wcs.py` con tutto il §7 tranne `resolve_name` (attende `04-cache.md`); test T1–T22 in `tests/core/test_coordinates_wcs.py`: 60 superati, 1 saltato (T5), 2 di rete superati a parte (SIMBAD per T2, archivio Gaia DR3 per T4). Emerso nei test e aggiunto in §10: una matrice CD tutta nulla viene sostituita da WCSLIB con l'identità senza errore → ora `WCS_INVALID`. Interpretazioni applicate (da confermare): `wcs_from_header` accetta anche proiezioni di WCSLIB fuori dall'elenco D10-4 (l'elenco limita calibrazione e scelta della proiezione, non la lettura dei dati); `compute_grid_lines` richiede il passo esplicito (scelta automatica del passo non prevista). Stato `approvato` invariato. |
| 2026-10-09 | Claude Code | **Decisioni del proprietario** (autorizzazione esplicita a modificare il file approvato): confermate le interpretazioni 1, 3, 4, 5 (proiezioni WCSLIB in lettura, `obstime` esplicito, velocità radiale 0 dichiarata, `PV2_m` per `ZPN`) in §9; **nuova `choose_grid_spacing`** (passo automatico come Aladin; elenchi di valori tondi e 5 linee per asse in §9, coincidenza con Aladin da verificare) in §3, §6, §7, §12 (T23); `compute_grid_lines` sceglie il passo da sé se i passi sono omessi; D10-9 da decidere con il 41; `04-cache.md` approvato (`resolve_name` dopo il codice della cache). Stato `approvato` invariato. |
| 2026-10-09 | Claude Code | §9: passo automatico della griglia **confermato** dal proprietario, coincidenza con Aladin da verificare con AP1. Stato `approvato` invariato. |
| 2026-10-09 | Claude Code | `resolve_name`: politica **prima la cache** con `refresh=True` (decisione del proprietario), timeout comuni di `04`, epoca J2000 delle coordinate SIMBAD dichiarata (§3, §7). Stato `approvato` invariato. |
| 2026-10-09 | Claude Code | **`resolve_name` scritto** con la cache comune di `04` (prima la cache, `refresh`, timeout 10 s / 60 s sulla sessione HTTP di SIMBAD, unità lette dalle colonne SIMBAD): tutto il §7 è ora nel codice. T5 non più saltato (simulato di default, reale con il marcatore `network`). Test del modulo: 75 superati di default + 3 di rete. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Verifica dei timeout di SIMBAD** (richiesta del proprietario): l'impostazione pubblica `conf.timeout` di `astroquery.simbad` **non basta** — è il limite di esecuzione lato server delle query asincrone, non un timeout HTTP; inoltre `query_object` legge sempre `hardlimit` tramite la sessione interna di astroquery (anche con `get_query_payload=True`), quindi neppure l'esecuzione con `pyvo` e sessione pubblica evita una richiesta senza timeout. Il campo interno `_session` resta, **isolato nella sola funzione `_simbad_with_timeouts`** con un commento che spiega il motivo; il test `test_t5_timeouts_reach_the_http_session` controlla che i timeout arrivino a ogni richiesta. Test: 106 superati con la rete. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Regola d'oro n. 8** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): tolti i "come Aladin" usati come motivo — `choose_grid_spacing` (§3, §7, §9, con motivazione nostra degli elenchi di valori tondi e delle 5 linee) e calibrazioni storiche DSS1 (§3, motivazione: lastre d'archivio calibrate solo così); resta il confronto finale con AP1, che è validazione e non copia. Docstring di `choose_grid_spacing` in `coordinates_wcs.py` allineata. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **D13-12** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): `propagate_position` con l'opzione esplicita `proper_motion_only` (astropy senza distanza, nessun effetto prospettico, risultato marcato); nuovo errore `PROPAGATION_MODE_CONFLICT` (§10), test T24 (§12). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **D13-14 (a)** (decisione del proprietario: sessagesimali ASTRORES convertiti con il modulo 10; autorizzazione esplicita a modificare il file approvato): nuova `parse_sexagesimal` (§7) con `astropy.coordinates.Angle`, errore `COORD_FORMAT_INVALID` (§10), test T25 (§12). Stato `approvato` invariato. |
| 2026-10-15 | Claude Code | **Decisioni del proprietario del 2026-10-15** (proposta della fase 1 dell'interfaccia, autorizzazione esplicita a modificare il file approvato; solo specifica, nessun codice): **D10-9 decisa** (soglia di default 30°, scarto ±10 % nel `41`); nuova **`make_view_wcs`** con `ViewGeometry` (base e finestra, funzioni finestra ↔ cielo esatte anche con distorsioni, WCS della regione visibile, raggio del campo) in §3, §6, §7; errori `VIEW_PARAMETERS_INVALID` e `PROJECTION_UNSUPPORTED` (§10); test T26–T30 (§12). Codice da scrivere (`make_view_wcs` e default di `choose_projection`). Stato `approvato` invariato. |
| 2026-10-15 | Claude Code | **D41-2 decisa dal proprietario il 2026-10-15** (autorizzazione esplicita a modificare il file approvato; solo specifica, nessun codice): nuova **`format_coordinates`** (sessagesimale o decimale con le cifre di DC3, ore per i frame equatoriali, riporto e ritorno a 0h, segno dell'emisfero conservato, precisione esplicita per la griglia, `Angle.to_string` di astropy) in §3, §6, §7; errore `FORMAT_PRECISION_INVALID` (§10); test T31–T33 (§12); due scelte minori da confermare (§13). Stato `approvato` invariato. |
| 2026-10-16 | Claude Code | **A7 nella v1 decisa dal proprietario il 2026-10-16** (opzione b della proposta della fase 1 sull'IA, autorizzazione esplicita a modificare il file approvato; solo specifica, nessun codice): nuova **`compass_and_scale_bar`** (nord ed est al centro della vista con `directional_offset_by`, `east_left`, barra di scala con il più grande valore tondo dell'elenco in arco che sta nella lunghezza massima, lunghezza del segmento orizzontale trovata con `brentq`, etichetta, `local_only`) in §3, §6, §7; avvisi `NORTH_UNDEFINED`, `SCALE_BAR_TOO_LONG` (§10); test T34–T36 (§12); tre scelte minori (§13); §5 con 34 e 42. Stato `approvato` invariato. |
| 2026-10-16 | Claude Code | Scelte minori di `format_coordinates` (1, 2) e di `compass_and_scale_bar` (3, 4, 5) **confermate dal proprietario il 2026-10-16**, che approva anche le modifiche del 2026-10-16. Stato `approvato` invariato. |
| 2026-10-16 | Claude Code | **Codice scritto** (FASE: CODICE – interfaccia v1, allineamento del livello 1): `make_view_wcs` con `ViewGeometry` (regione visibile = base con il pixel di riferimento spostato all'origine intera che contiene la finestra, anche per SIP; `WCS.slice` per le distorsioni a tabella), `format_coordinates` (verifica di `Angle.to_string`: riporto sì, ritorno a 0 no, gestito nel codice; segno ASCII), `compass_and_scale_bar`, `choose_projection` con default 30° che restituisce `ProjectionChoice` (proiezione, campo, soglia e sua fonte); test T20 aggiornato e T26–T36 in `tests/core/test_coordinates_wcs.py` (100 superati). Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | §13: tolte le frasi superate "codice da scrivere" per le funzioni della v1, scritte il 2026-10-16 (nessun cambiamento di contenuto). Stato `approvato` invariato. |
| 2026-10-24 | Claude Code | **D40-3, sprint 8b:** §10 — nuova sezione "Parametri dei messaggi" con codice, `reason` e `params` di ogni errore e avviso; il codice li restituisce (testo italiano invariato); le traduzioni sono nel catalogo del `40`. Nessun comportamento scientifico cambia. |
