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
  `choose_grid_spacing` in base al campo visibile, come fa Aladin;
  **scelta della proiezione del campo** con `choose_projection` — `TAN` per i
  campi piccoli, `AIT` per i campi grandi, con la soglia che è la decisione
  D10-9, da decidere con il `41` (D10-8, decisa il 2026-10-09).
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
  storiche delle lastre (metodo DSS1), come fa Aladin. Il supporto in
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
  `19-core-dati-planetari.md`, tutti i moduli di analisi (20–24),
  `33-ia-query-adql.md`, `41-ui-visualizzatore-cielo.md`,
  `42-ui-pannello-cataloghi.md`.

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
| in | campo di vista, soglia | `Quantity` angolare | gradi | per `choose_projection` (soglia: D10-9) |
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
  dichiara l'epoca usata.
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
  campo visibile, come Aladin: parametri: WCS, dimensioni dell'immagine,
  frame della griglia (con epoca se il frame la richiede), numero di linee
  desiderate per asse; misura l'estensione in longitudine e in latitudine
  del campo nel frame della griglia (360° in longitudine se un polo è nel
  campo) e per ogni asse sceglie **il più piccolo passo "tondo" ≥
  estensione / linee desiderate** dagli elenchi di §9; restituisce i due
  passi, le estensioni misurate e l'elenco usato (orario o in arco).
- **`choose_projection(...)`** — sceglie la proiezione del campo: `TAN` se
  il campo di vista è minore della soglia, `AIT` altrimenti; la soglia è un
  parametro obbligatorio finché D10-9 non ne fissa il valore (si decide con
  il `41`).

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
  **confermati dal proprietario il 2026-10-09**; coincidenza con Aladin **da
  verificare con AP1** (validazione finale della parità).
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
| T22 | Fuori campo | `pixel_to_sky` su un pixel fuori dall'immagine | valore restituito con avviso `OUT_OF_FIELD` | test di unità |

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
- **D10-9 — Soglia di `choose_projection`:** campo di vista oltre il quale
  si passa da `TAN` ad `AIT`. Da decidere (Gruppo 3) **insieme al modulo
  `41-ui-visualizzatore-cielo.md`** (indicazione del proprietario del
  2026-10-09); fino ad allora la soglia è un parametro obbligatorio della
  funzione, senza valore di default.

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
