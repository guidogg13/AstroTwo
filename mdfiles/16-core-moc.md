# 16-core-moc.md — mappe di copertura MOC

**Stato:** approvato

## 2. Scopo

Creare, manipolare e interrogare mappe di copertura (MOC) — spaziali,
temporali e spazio-temporali — con operazioni rigorose, così che la copertura
di un dato sia sempre verificabile e confrontabile.

## 3. Cosa fa

- **Tipi di MOC (E6):** MOC **spaziali** (ordine HEALPix sul cielo), **temporali**
  (intervallo di tempo) e **spazio-temporali** (combinazione).
- **Creazione (E6):** generare MOC da immagini, da cataloghi, da poligoni, da
  cerchi e da mappe di probabilità; ogni creazione dichiara ordinamento,
  risoluzione (ordine massimo) e unità.
- **Operazioni insiemistiche (E6):** unione, intersezione, sottrazione,
  complemento tra MOC; risultati sempre normalizzati e validati.
- **Filtro delle sorgenti per MOC (E6):** selezionare i record di una tabella
  che cadono dentro (o fuori) da un MOC — l'operazione restituisce indici, il
  disegno è della UI.
- **Impronta dei survey (C4):** rappresentare la copertura di un survey come
  MOC e mostrarla (il servizio dei tile è di `12-core-hips.md`). **Rinviata
  al modulo 12 (decisione del proprietario del 2026-10-11):** `survey_coverage`
  si scrive con il 12, che conosce l'identità dei survey.
- **Mappe e griglie HEALPix (H12):** produrre mappe HEALPix (conteggi/flussi
  per cella) e griglie di riferimento; **cataloghi HiPS progressivi** (H12):
  **confine deciso il 2026-10-04 (D16-5, pari a D12-5): dati e computazioni
  HEALPix vivono qui, il servizio dei tile resta in `12-core-hips.md`**.
  **I cataloghi HiPS progressivi (H12) sono rinviati al modulo 12** (decisione
  del proprietario del 2026-10-11); qui restano mappe e griglie HEALPix.
  **Mappe HEALPix (decisione del proprietario del 2026-10-11):** schema
  **NESTED** in **ICRS**, **ordine obbligatorio**; schema e sistema dichiarati
  nel risultato.
- **Generazione di MOC da riga di comando (H9):** stesse operazioni
  raggiungibili senza interfaccia grafica; integrazione con lo scripting di
  `24-analisi-pipeline-riproducibili.md`. **Per ora `build_moc` è solo una
  funzione** (decisione del proprietario del 2026-10-11); l'ingresso da riga
  di comando arriverà con il 24.
- **Versioni del formato MOC (H22, sez. 8.1 del manuale di Aladin, ed. giugno 2022):**
  lettura dei MOC nelle versioni dello standard IVOA **da 1.0 a 2.1**
  (spaziali, temporali, spazio-temporali) in FITS e in JSON; la versione letta
  è riportata nel risultato; la scrittura usa la versione corrente dello
  standard (FITS IVOA, D16-2) dichiarata nei metadati. **Verifica del
  2026-10-11** (documenti IVOA e `mocpy` 0.20.0): le versioni pubblicate dello
  standard sono **1.0** (REC 2014-06-02), **1.1** (REC 2019-10-07) e **2.0**
  (REC 2022-07-27), più la Note STMOC 1.0 (2019); **una versione 2.1 non
  esiste** tra i documenti IVOA (→ **D16-6, decisa il 2026-10-12**: verifica
  del 2026-10-12 sull'elenco dei documenti IVOA, nessuna 2.1 nemmeno come
  Working Draft o Proposed Recommendation → un file `2.1` resta rifiutato). Le
  intestazioni FITS di 1.0 e 1.1 sono identiche (`PIXTYPE='HEALPIX'`,
  `ORDERING='NUNIQ'`, `COORDSYS='C'`, `MOCORDER`, colonna `UNIQ` `1J`/`1K`)
  e non hanno `MOCVERS`: lo standard 2.0 dice che senza `MOCVERS` si assume
  1.1 e senza `MOCDIM` si assume `SPACE`. Il 2.0 aggiunge `MOCVERS`,
  `MOCDIM` (`SPACE`, `TIME`, `TIME.SPACE`), `ORDERING` `NUNIQ` o `RANGE`,
  `MOCORD_S`, `MOCORD_T`, `TIMESYS='TCB'`. JSON e testo **non portano la
  versione**: il risultato dice "versione non dichiarata nel formato".
  `mocpy` legge i file 1.x scritti secondo lo standard e i file 2.0
  (`NUNIQ` e `RANGE`), rifiuta `COORDSYS` diverso da `C` e accetta in
  `MOCVERS` solo `1.1`, `2.0` e **`2.1`** (rifiuta `1.0`, che lo standard
  1.0 non scrive: non ha `MOCVERS`). Il controllo della versione lo fa il 16
  leggendo l'intestazione con `astropy.io.fits`; un file con
  `MOCVERS='1.0'` si passa a `mocpy` come copia in memoria senza la parola
  chiave (intestazioni identiche a 1.1). Versioni ammesse: assente (riportata
  come "1.1, assunta dallo standard: `MOCVERS` assente; 1.0 ha le stesse
  intestazioni"), `1.0`, `1.1`, `2.0`; ogni altra → `MOC_VERSION_UNSUPPORTED`
  con la versione trovata.
- **Formati JSON e testo (standard 2.0 §4.3 e appendice F, verificato il
  2026-10-11):** il JSON è `{"ordine": [indici…], …}`, con il livello
  facoltativo `{"s": …}` / `{"t": …}` e, per gli STMOC, una lista di coppie
  `t`/`s`; il testo è `ordine/indici` con intervalli `a-b`, prefissi `t`/`s`
  solo per gli STMOC. Lo standard dice che senza il prefisso "la natura del
  MOC è determinata dal contesto d'uso": **il tipo non si assume mai**, lo
  dichiara il chiamante (`kind`); se manca → `MOC_TYPE_REQUIRED`. `mocpy`
  non legge i prefissi `s`/`t` dei MOC a una dimensione: li toglie il 16.
  In scrittura il JSON porta sempre il prefisso `s`/`t` (lista `t`/`s` per
  gli STMOC); il testo segue lo standard (prefissi solo per gli STMOC).
- **Filtro spaziale delle collezioni tramite MocServer (H26, sez. 8.3.3):**
  interrogazione del MocServer del CDS con una regione o un MOC (più filtri
  sulle proprietà) per ottenere le collezioni che coprono la regione; i MOC
  delle collezioni restano sul server (troppo grandi per il client), le
  proprietà sono nella copia locale di `12-core-hips.md`. **Client: la rete
  del 14** (cache e registro delle richieste, `MOCSERVER_URL` già usato dal
  13), **non `astroquery.mocserver`** (decisione del proprietario del
  2026-10-11); l'interfaccia del MocServer per i filtri per regione si
  verifica prima di P5. Senza rete il filtro spaziale non è disponibile:
  errore esplicito, mai un elenco parziale presentato come completo.

### Decisioni del proprietario del 2026-10-11 e divisione in parti

- **HEALPix:** solo `astropy-healpix` e `mocpy`; **`healpy` escluso** (licenza
  GPL-2.0). Verifiche fatte: `mocpy` 0.20.0 (BSD, wheel macOS arm64, Python
  3.12), `astropy-healpix` 2.0.1 (BSD).
- **`order_max` obbligatorio, senza default**, in ogni costruttore; intero in
  [0, 29] per lo spazio e [0, 61] per il tempo (limiti dello standard 2.0),
  altrimenti `HEALPIX_ORDER_INVALID`.
- **MOC da catalogo:** una cella per sorgente all'ordine dato, **senza
  raggio**.
- **MOC da immagine:** dai **pixel validi**, con il **WCS dell'11** (non solo
  i quattro angoli).
- **Poligoni:** lati su **cerchi massimi**. La regola per l'interno si scrive
  dopo la verifica di `mocpy`: **verificata il 2026-10-11**, `mocpy` prende
  come interno **la più piccola delle due regioni** delimitate dal poligono,
  indipendentemente dall'ordine dei vertici (provato con un triangolo e con
  un poligono attorno a un polo, vertici in un verso e nell'altro);
  `complement=True` dà l'altra regione. Regola di AstroTwo: interno = regione
  più piccola, oppure la complementare con `complement=True`, dichiarata nel
  risultato.
- **MOC spaziali sempre in ICRS** (come da standard, `COORDSYS='C'`): le
  posizioni in altri sistemi si convertono prima con il modulo 10.
- **Mappe di probabilità:** somma = 1 entro **10⁻⁶ relativo**, dichiarato nel
  risultato.
- **Tolleranze delle aree in T1 e T2:** calcolate nel test come **numero di
  celle di bordo × area di una cella** all'ordine usato.
- **MocServer:** tramite la rete del 14 (sopra).
- **`build_moc`:** per ora solo funzione (sopra).
- **Mappe HEALPix:** NESTED, ICRS, ordine obbligatorio (sopra).
- **Rinviati al 12:** `survey_coverage` (C4) e cataloghi HiPS progressivi
  (H12).

**Divisione in 5 parti (approvata dal proprietario il 2026-10-11):**

| Parte | Contenuto | Test |
|---|---|---|
| P1 | classe `Moc` (spaziale, temporale, spazio-temporale, con `body`, sistema, origine), lettura/scrittura FITS IVOA, JSON e testo, versioni 1.0–2.1, operazioni insiemistiche, MOC vuoto, tipi diversi | T3, T5, T7 |
| P2 | creazione da cerchio, poligono, catalogo, immagine | T1, T2 |
| P3 | `filter_by_moc`, mappe e griglie HEALPix | T4, T6 |
| P4 | MOC temporali e spazio-temporali (scala dei tempi), mappe di probabilità e regioni di credibilità (D16-4) | test di P4 |
| P5 | `query_mocserver` (H26), `build_moc` (H9), lettura da URL (H22) | T8, T9 |

**Scelte di P1 (scelte minori, confermate dal proprietario il 2026-10-12):**

- `Moc` è immutabile e contiene l'oggetto `mocpy` (`MOC`, `TimeMOC`, `STMOC`),
  il tipo (`space`, `time`, `space-time`), il **sistema** (`ICRS` per lo
  spazio, `TCB` per il tempo), gli ordini massimi, `body`, l'origine, la
  versione letta (o `None` se creato), la storia e gli avvisi.
- **`body` dei MOC solo temporali: "non applicabile"** (`None`, dichiarato):
  un `TMOC` non ha posizioni, la regola del corpo vale per i MOC spaziali e
  spazio-temporali. Un MOC spaziale letto da file con `COORDSYS='C'` ha
  `body = "celestial"` (ricavato dal sistema, D19-3).
- Operazioni tra MOC dello stesso tipo e dello stesso corpo. **Scelta 5
  cambiata dal proprietario il 2026-10-12:** con `force_body=True` tra corpi
  diversi il risultato ha **`body = "mixed"`** con l'**elenco dei corpi**
  (`Moc.bodies`, ordinato) e l'avviso `BODY_FORCED`; **ogni operazione
  successiva su un MOC misto** (unione, intersezione, differenza, complemento,
  `contains`, `space_during`, `time_within`, `filter_by_moc`) **richiede di
  nuovo la forzatura**, anche con un MOC di uno dei suoi corpi
  (`BODY_MISMATCH` altrimenti); un MOC misto non si usa dove serve un MOC
  celeste (griglie, MocServer: `MOC_BODY_UNSUPPORTED`).
- Ordine del risultato di unione, intersezione e differenza = il **massimo**
  degli ordini degli operandi (comportamento di `mocpy`, verificato); il
  complemento conserva l'ordine; dichiarato nella storia.
- Scrittura FITS: standard **2.0**; MOC spaziali in **`NUNIQ`** con anche
  `MOCORDER` (raccomandato dallo standard per la compatibilità con i
  lettori 1.x), temporali e spazio-temporali in `RANGE`; `MOCTOOL` =
  `AstroTwo <versione>`. **Scelta 6 cambiata dal proprietario il
  2026-10-12 (coerente con D19-7):** anche i MOC **planetari** (e misti) si
  scrivono, in FITS **2.0** più la parola chiave nostra **`A2BODY`** (il
  corpo; per un MOC misto `A2BODY = 'mixed'` e **`A2BODIES`** con i corpi
  separati da virgole), dichiarata nel risultato (`MocWriteResult`) come
  **estensione non standard** (avviso `MOC_NONSTANDARD_EXTENSION`); `COORDSYS`
  resta `'C'`, come il formato richiede e come scrive `mocpy`, quindi un
  lettore senza l'estensione vede un MOC celeste (scritto nell'avviso). Il 16
  rilegge `A2BODY`/`A2BODIES` (stesso avviso nel MOC letto); senza `A2BODY`
  il MOC è `celestial`. JSON e testo non hanno dove dichiarare il corpo: un
  MOC non celeste in quei formati → `MOC_BODY_UNSUPPORTED` (scelta minore,
  confermata il 2026-10-12).
- **Scelte minori 1–4 e 7–13 confermate dal proprietario il 2026-10-12.**
- Risultato vuoto: consentito, con l'avviso `MOC_EMPTY`.

**P2 — creazione (scritta il 2026-10-11):**

- **Cerchio:** `moc_from_region(CircleRegion(centro, raggio), order_max)`,
  `mocpy.MOC.from_cone` con calcolo all'ordine + 2: contiene le celle che
  toccano il cerchio (approssimazione per eccesso). Centro in qualsiasi
  sistema del 10, convertito in ICRS; raggio in (0°, 180°].
- **Poligono:** `moc_from_region(PolygonRegion(vertici), order_max,
  complement=False)`, `mocpy.MOC.from_polygon`. Verifica: la regione scelta
  non dipende dal verso dei vertici, ma le **celle di bordo** possono
  differire tra i due versi (186 e 61 celle su 24 910 all'ordine 7 in una
  prova): la differenza resta entro le celle di bordo (T2 e test del
  poligono).
- **Catalogo:** `moc_from_catalog(table, order_max)`, `mocpy.MOC.from_lonlat`;
  colonne e sistema dal 13, conversione in ICRS con il 10, righe senza
  posizione escluse e contate (avviso `ROWS_EXCLUDED`), epoca delle
  posizioni riportata, mai propagata.
- **Immagine (scelta minore, confermata il 2026-10-12):** `moc_from_image(image,
  order_max)`. Pixel validi = valori finiti, non mascherati e diversi da
  `BLANK` per i dati interi. Si campiona a passo non più grande di **metà
  del lato di una cella** all'ordine dato (pixel = lato più grande del pixel
  dal WCS, cella = risoluzione dell'ordine):
  - **pixel grande (pixel ≥ cella / 2):** per ogni pixel valido si
    campionano **angoli e punti interni**, `k` passi per pixel,
    `k` = ⌈2 × pixel / cella⌉ (i punti sul bordo tra un pixel valido e uno
    non valido contano);
  - **pixel piccolo (pixel < cella / 2; decisione del proprietario del
    2026-10-14):** si lavora su **blocchi di b × b pixel**,
    `b` = ⌊cella / (2 × pixel)⌋ (almeno 1), a partire dal pixel (0, 0); sul
    bordo destro e superiore restano **blocchi parziali**, più piccoli. Un
    blocco è **valido se contiene almeno un pixel valido**; si campionano
    gli **angoli dei blocchi validi**, compresi i blocchi parziali (un
    angolo comune a più blocchi conta se almeno uno è valido). Passo = b ×
    pixel ≤ cella / 2. **Contorno (D16-8, decisa il 2026-10-14):** si
    aggiungono gli **angoli dei pixel lungo il contorno della regione dei
    blocchi validi** (angoli di pixel che toccano sia un pixel di un blocco
    valido sia un pixel di un blocco non valido o l'esterno dell'immagine),
    pixel per pixel solo lì: senza di essi le celle che toccano il contorno
    con una striscia più stretta del passo andrebbero perse (misure in §13).
    Punti: angoli dei blocchi, al massimo (⌈nx / b⌉ + 1) × (⌈ny / b⌉ + 1),
    più angoli di contorno, 2 × (nx + ny) per un'immagine tutta valida;
    un punto presente in entrambi gli insiemi si conta due volte.
    Conseguenza dichiarata: ai bordi della maschera dei pixel validi il MOC
    **può crescere, mai perdere celle**: un blocco valido è campionato
    intero, quindi i punti stanno al massimo **b − 1 pixel** oltre i pixel
    validi (meno di un blocco, cioè meno di metà cella; non "mezzo blocco").
    Il riferimento è il MOC calcolato pixel per pixel (angoli di ogni pixel
    valido): il MOC a blocchi lo contiene e sta dentro quello della maschera
    estesa ai blocchi validi interi.
  Il risultato dichiara il modo usato (`k` passi per pixel, oppure blocchi
  di b × b pixel con la **dimensione del blocco** b), il passo e il numero di
  punti (con i blocchi: angoli dei blocchi e angoli di contorno). I punti si
  convertono con il WCS dell'11 (`pixel_to_sky` del 10) e in ICRS; il MOC
  contiene **ogni cella che contiene un punto**. Motivo dei blocchi:
  campionare ogni pixel quando il pixel è molto più piccolo della cella
  converte decine di milioni di punti senza cambiare il risultato (10 s per
  l'immagine DSS2 di 2° × 2° della demo delle Pleiadi all'ordine 11, misura
  del 2026-10-13). Motivo del campionamento: un poligono per
  pixel con `mocpy.MOC.from_polygons` è troppo lento (oltre 200 s per 200 000
  pixel in una prova del 2026-10-11) e `mocpy.MOC.from_fits_image` con
  maschera usa solo i centri dei pixel (approssimazione dichiarata dalla sua
  documentazione). Lo scarto dal contorno vero è limitato alle celle di
  bordo (test: il MOC sta dentro il poligono degli angoli allargato di una
  cella e contiene il poligono ristretto di una cella, per un'immagine TAN,
  dove i bordi sono cerchi massimi). Punti fuori dalla proiezione: esclusi,
  avviso `POINTS_OUTSIDE_PROJECTION`. Immagini a due livelli: rifiuto
  (`PREVIEW_NOT_MEASURABLE`, come nell'11).
- MOC da catalogo o immagine di un corpo diverso da `celestial`:
  `MOC_BODY_UNSUPPORTED` (i MOC spaziali sono ICRS).
- Nota di verifica: `mocpy.MOC.add_neighbours` modifica il MOC sul posto;
  il 16 non lo usa (si usano `extended`/`contracted`, che restituiscono un
  nuovo MOC). Verifica estesa: anche `refine_to_order` modifica il MOC sul
  posto; tutte le altre operazioni usate restituiscono un nuovo oggetto. Il
  16 non chiama mai i due metodi che modificano sul posto sui MOC
  dell'utente.

**P3 — filtro, mappe e griglie (scritta il 2026-10-11):**

- **`filter_by_moc(table, moc, inside=True, *, force_body=False)`** →
  `FilterResult` (maschera booleana, `indices`, `count`, righe escluse,
  descrizione); posizioni del 13 convertite in ICRS con il 10;
  `mocpy.MOC.contains_lonlat`; righe senza posizione **mai selezionate**, né
  dentro né fuori (avviso `ROWS_EXCLUDED`); la tabella non cambia; solo MOC
  spaziali (`MOC_TYPE_MISMATCH`); regola del corpo come per le operazioni.
  Anche **`Moc.contains(coords)`** per posizioni sciolte.
- **`healpix_map(table, order, *, column=None)`** → `HealpixMap`: conteggi
  per cella o somma della colonna `column` (es. flussi, unità conservata),
  NESTED in ICRS, `order` obbligatorio (fino a 12 in questa funzione, 201
  milioni di celle); righe senza posizione o con valore mancante escluse e
  contate (`ROWS_EXCLUDED`, `VALUES_EXCLUDED`). Calcolo: `astropy-healpix`
  (`lonlat_to_healpix`) e `numpy.bincount`.
- **`healpix_grid(order, *, within=None, step=1)`** → `HealpixGrid`: celle
  NESTED e contorni in ICRS (`boundaries_lonlat` di `astropy-healpix`) per il
  disegno del 41. **Scelta minore (confermata il 2026-10-12):** senza `within` la
  griglia di tutto il cielo è ammessa fino a 12 × 4⁷ = 196 608 celle
  (ordine 7), oltre → `GRID_TOO_LARGE`; con `within` (MOC spaziale) solo le
  celle che toccano il MOC all'ordine dato.

**P4 — tempo e probabilità (scritta il 2026-10-11):**

- **`moc_from_times(start, end=None, *, order_max)`** → MOC temporale da
  istanti o intervalli `astropy.time.Time` (la scala fa parte dell'oggetto e
  si dichiara nella storia); conversione in **TCB** con `astropy.time` prima
  di `mocpy.TimeMOC`; ordine 0–61 obbligatorio (61 = 1 μs); fine prima
  dell'inizio, istanti non finiti o prima di JD 0 → `TIME_RANGE_INVALID`.
  `Moc.time_range` (TCB) e `Moc.contains_times`.
- **`moc_space_time(start, end, coords, *, time_order, space_order)`** →
  MOC spazio-temporale da osservazioni (una posizione per istante o
  intervallo, convertita in ICRS con il 10), `mocpy.STMOC`; proiezioni
  `Moc.space_during(moc_temporale)` e `Moc.time_within(moc_spaziale)`
  (`query_by_time`/`query_by_space` di `mocpy`).
- **`read_probability_map(path)`** → `ProbabilityMap` (celle NUNIQ e densità
  per sr): formato pubblico LIGO/Virgo/KAGRA verificato il 2026-10-11 sulla
  guida utente (`emfollow.docs.ligo.org`): **multi-ordine** con `UNIQ`,
  `PROBDENSITY` in `sr-1`, `ORDERING='NUNIQ'`, `COORDSYS='C'`; **piatte** con
  `PROB` per cella, `NSIDE`, `ORDERING` RING o NESTED (RING convertito in
  NESTED con `astropy-healpix`; anche colonne vettoriali da 1024 valori per
  riga). Probabilità per cella in [0, 1] e densità ≥ 0
  (`PROBABILITY_OUT_OF_RANGE`); **somma = 1 entro 10⁻⁶ relativo**, dichiarata
  (`PROBABILITY_SUM_INVALID` altrimenti); `PROBDENSITY` senza unità di
  densità per sr, `COORDSYS` diverso da `C` o colonne mancanti →
  `PROBABILITY_MAP_INVALID`.
- **`moc_from_probability(pmap, level, order_max)`** → regione di
  credibilità: **la più piccola insieme di celle intere**, prese per densità
  decrescente, con probabilità **≥ livello** (stesso calcolo della guida
  LIGO; `mocpy.MOC.from_valued_healpix_cells` con `strict=False,
  no_split=True`, verificato contro un calcolo indipendente). **Scelta minore
  (confermata il 2026-10-12):** celle intere e probabilità ≥ livello (con `strict=True`
  `mocpy` dà invece la regione con probabilità ≤ livello); la probabilità
  contenuta è ricalcolata con `mocpy.probability_in_multiordermap` e
  dichiarata (avviso `CREDIBLE_PROBABILITY`). Con `order_max` minore
  dell'ordine della mappa la regione si porta a `order_max` per eccesso
  (`ORDER_DEGRADED`).

**P5 — rete e `build_moc` (scritta il 2026-10-11):**

- **Interfaccia del MocServer verificata il 2026-10-11** (pagina del
  servizio, v5.10 giugno 2024, e richieste di prova): cono `RA`, `DEC`, `SR`
  in gradi ICRS; `stc=` (Circle/Polygon); `moc=` in testo o JSON, anche in
  POST; `intersect` = `overlaps` (default), `enclosed`, `covers`;
  `spacesys=C`; filtri sulle proprietà (`campo=modello`, `*` e `?`);
  `get=record`, `fmt=json`, `fields=`. Due comportamenti non documentati:
  un valore sconosciuto di `intersect` è **ignorato in silenzio** (il 16 lo
  rifiuta prima dell'invio) e lo STC con il sistema dichiarato (`Polygon
  ICRS …`, `Circle ICRS …`, come indica la pagina) dà "STC parsing error",
  mentre senza sistema è accettato. **Scelta minore (confermata il 2026-10-12):**
  cerchi inviati come cono `RA`/`DEC`/`SR`, MOC spaziali come `moc=` in
  POST; **i poligoni si passano come MOC** (`moc_from_region`, interno
  secondo la nostra regola), mai come STC.
- **`query_mocserver(region, *, properties=None, intersect="overlaps",
  fields=("ID", "obs_title"), cache, refresh, timeouts)`** →
  `MocServerResult` (record, `ids`, richiesta registrata del 14 con URL,
  parametri e data, descrizione). Rete con `_http`/`_store`/`_record` del
  14 (`MOCSERVER_URL`), cache e registro comuni; senza rete e senza copia in
  cache → `MOCSERVER_UNAVAILABLE`; con la copia in cache si usa quella
  (risposta completa di una data precedente, dichiarata `FROM_CACHE`);
  risposta non JSON (es. pagina d'errore HTML) → `SERVICE_ERROR`.
  **Codifica (verifica del 2026-10-12):** il MocServer dichiara le risposte
  JSON in **ISO-8859-1** (`Content-Type: application/json;charset=ISO-8859-1`;
  es. "µm" in un solo byte); si leggono **secondo la codifica dichiarata**,
  con `MOCSERVER_CHARSET` del 14, mai in UTF-8 per presunzione.
- **Lettura da URL (H22):** `read_moc(url, …, cache, refresh, timeouts)`;
  prima la cache comune (modulo `16`), download intero o niente con i
  timeout di `04`; in cache il MOC si conserva **in FITS IVOA** (D16-2): il
  FITS originale così com'è, un JSON o un testo convertito in FITS 2.0 (la
  versione riletta dalla cache resta "non dichiarata nel formato" con il
  formato originale); rete assente → copia in cache dichiarata, senza copia
  `NET_TIMEOUT`.
- **`build_moc(sources, *, order_max, output=None, format="fits",
  overwrite=False)`** (H9): unione dei MOC di cerchi, poligoni, cataloghi,
  immagini e MOC; i file si indicano con il tipo esplicito
  (`("image", percorso)`, `("catalog", percorso)`, `("moc", percorso)`):
  **il tipo di un file non si indovina** (scelta minore); scrittura
  facoltativa con `write_moc`. Solo funzione; riga di comando con il 24.

## 4. Cosa NON fa

- Non scarica immagini né cataloghi (11, 12, 14).
- Non disegna: i MOC e le griglie li rende la UI (41).
- Non gestisce le query ADQL (14/33) né i cross-match (15).
- Non calcola fotometria o curve di luce (20, 22).
- Non memorizza i MOC nella cache dei cataloghi: la persistenza segue la
  **stessa politica della cache immagini/dati (A7)** — **formato FITS
  standard IVOA su file, nella cache con origine e data** (D16-2, decisa il
  2026-10-04).

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `04-cache.md` (cache comune A7),
  `10-core-coordinate-wcs.md` (coordinate di cerchi/poligoni),
  `13-core-cataloghi.md` (tabelle per creare MOC da cataloghi e per il filtro),
  `12-core-hips.md` (identità dei survey per C4/H12), `14-core-protocolli-vo.md`
  (eventuali MOC scaricati dai servizi).
- **Usato da:** `11-core-immagini-fits.md`, `12-core-hips.md`,
  `19-core-dati-planetari.md`,
  `41-ui-visualizzatore-cielo.md`, `16` è usato anche da
  `50-avanzate-transienti.md` (copertura delle osservazioni).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | regione | poligono/cerchio | gradi (coordinate) | per creare MOC |
| in | catalogo | `astropy.table.Table` | con coordinate | per creare MOC da cataloghi |
| in | immagine | `FitsImage` (modulo 11) | pixel + WCS | per creare MOC da immagini |
| in | mappa di probabilità | mappa HEALPix | probabilità per cella ∈ [0,1] | |
| in | intervallo temporale | istante/intervallo | ISO 8601 (interfaccia/file) o JD | MOC temporali: internamente **JD** via `astropy.time` (D16-3) |
| in | `order_max` | intero | ordine HEALPix | risoluzione |
| out | MOC | oggetto MOC | unità: degree (spaziale), tempo (temporale) | serializzazione cache: **FITS standard IVOA**; export anche **JSON** e **testo** (D16-2) |
| out | `body` | stringa | `celestial` o nome IAU del corpo | obbligatorio (D19-3): ricavato dal sistema di coordinate o dai metadati planetari, mai assunto; operazioni solo tra MOC dello stesso corpo |
| out | operazioni | MOC | stesso formato dell'input | |
| out | selezione | indici booleani | — | filtro per MOC |
| out | mappa HEALPix | array + ordine | valori per cella | H12 |
| in | file MOC | percorso o URL | FITS o JSON, versioni 1.0–2.1 | H22 |
| out | versione del MOC letto | stringa | versione dello standard | H22 |
| in | regione o MOC + filtri per il MocServer | struttura | coordinate in gradi con frame | H26 |
| out | collezioni che coprono la regione | lista | identificativi, origine e data della risposta | H26 |

## 7. Interfaccia pubblica

- **`Moc`** (classe): MOC spaziale/temporale/spazio-temporale; metodi
  descrittivi `union`, `intersection`, `difference`, `complement`, `contains`.
- **`moc_from_catalog(table, order_max)`**, **`moc_from_region(region,
  order_max, *, complement=False)`** (`CircleRegion`, `PolygonRegion`),
  **`moc_from_image(image, order_max)`**, **`moc_from_probability(map)`**
  — costruttori (E6); `order_max` obbligatorio; ciascuno dichiara
  risoluzione e unità nella storia.
- **`moc_from_times`**, **`moc_space_time`**, **`read_probability_map`**,
  **`moc_from_probability(pmap, level, order_max)`** (P4); metodi
  `time_range`, `contains_times`, `space_during`, `time_within`.
- **`filter_by_moc(table, moc, inside=True, *, force_body=False)`** — filtro
  delle sorgenti (E6); restituisce indici (`FilterResult`); `Moc.contains`.
- **`survey_coverage(survey)`** — copertura di un survey come MOC (C4).
- **`healpix_map(...)`** / **`healpix_grid(...)`** — mappe e griglie HEALPix
  (H12), NESTED in ICRS con ordine obbligatorio. **Calcolo: `astropy-healpix`**
  (`healpy` escluso, licenza GPL).
- **`build_moc(...)`** — generazione senza interfaccia (H9), delegata alle
  funzioni sopra; per ora solo funzione, la riga di comando arriva con il 24.
- **Persistenza e export (D16-2):** i MOC si salvano in cache in **formato
  FITS standard IVOA** (file nella cache comune di `04-cache.md`, con origine
  e data come gli altri dati; nessuna cache propria, CA4); l'export
  dell'utente offre anche **JSON** e **testo**.
- **`read_moc(source, *, format=None, kind=None)`** (H22) — legge un MOC
  FITS, JSON o testo e ne dichiara la versione; `kind` (`space`, `time`,
  `space-time`) obbligatorio solo per JSON e testo senza prefisso.
- **`write_moc(moc, path, format="fits", overwrite=False)`** — scrive in FITS
  IVOA 2.0, JSON o testo (D16-2); restituisce **`MocWriteResult`** (percorso,
  formato, versione, avvisi; utilizzabile come percorso). MOC non celesti
  solo in FITS con `A2BODY` (scelta 6).
- **`Moc.complement(*, force_body=False)`**, **`Moc.contains(coords, *,
  force_body=False)`** — `force_body` serve solo per un MOC misto (scelta 5);
  complemento degli ST-MOC secondo D16-7.
- **`Moc.describe()`** — tipo, sistema, ordini, corpo, area (steradianti e
  frazione di cielo) o durata, numero di celle, origine e versione.
- **`query_mocserver(region, *, properties=None, intersect="overlaps",
  fields=("ID", "obs_title"), cache=None, refresh=False, timeouts=None)`**
  (H26) — collezioni che coprono la regione (`CircleRegion` o MOC
  spaziale), con provenienza della risposta (`MocServerResult`).
- **`build_moc(sources, *, order_max, output=None, format="fits",
  overwrite=False)`** (H9).

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| Standard IVOA MOC | formato delle mappe di copertura (cache in **FITS IVOA**, export JSON/testo — D16-2) | standard della comunità |
| `astropy-healpix` (2.0.1, BSD) | operazioni HEALPix, mappe e griglie | mantenuto da AstroPy; **`healpy` escluso** (GPL-2.0, decisione del proprietario del 2026-10-11) |
| `mocpy` (**scelto con D16-1**; 0.20.0, BSD, wheel macOS arm64 per Python 3.12, verificato il 2026-10-11) | creazione/operazioni MOC, incluso i MOC temporali | libreria MOC dedicata allineata allo standard IVOA |
| `astropy.coordinates` (via 10) | cerchi/poligoni in coordinate | conversioni verificate |
| rete del 14 (`MOCSERVER_URL`) | filtro spaziale delle collezioni (H26) | cache e registro delle richieste comuni; **non `astroquery.mocserver`** (decisione del proprietario del 2026-10-11) |

## 9. Regole e vincoli

- Le operazioni insiemistiche devono rispettare le proprietà matematiche:
  unione commutativa, intersezione ⊆ operandi, complemento di complemento =
  originale (test T3).
- Ogni MOC dichiara unità, ordine massimo, sistema di riferimento e corpo
  (`body`); un MOC senza queste informazioni è un errore.
- Le creazioni da cerchio/poligono usano la geometria celeste del modulo 10
  (nessuna approssimazione piana).
- I calcoli HEALPix sono delegati alle librerie HEALPix (regola d'oro n. 4).
- Le selezioni per MOC restituiscono solo indici: nessuna modifica della
  tabella sorgente.
- I valori di probabilità devono restare in [0,1]; fuori range ⇒ errore.
- **Tempo (D16-3, decisa il 2026-10-04):** internamente **numerico, JD tramite
  `astropy.time`**; **ISO 8601 solo nell'interfaccia e nei file**; **la scala
  di tempo si dichiara sempre** (UTC, TDB, TCB); i **MOC temporali usano la
  scala dello standard IVOA: TCB** (verificato il 2026-10-11 sul testo dello
  standard 2.0 §4.2: JD, scala TCB, baricentro del Sistema Solare, 1 μs
  all'ordine 61). `mocpy` converte in TCB i tempi in altre scale (verificato). Regola di progetto in
  `02-convenzioni.md` DC1.
- **Formato in cache:** FITS standard IVOA su file nella cache comune di
  `04-cache.md` (limite unico di 5 GB), con origine e data come gli altri
  dati (D16-2).

- **Corpo di riferimento (`body`, D19-3 decisa il 2026-10-08):** ogni MOC porta
  nei metadati il campo **obbligatorio** `body`. Per i dati astronomici vale
  `celestial` (sfera celeste) ed è **ricavato dal sistema di coordinate
  dichiarato** (es. ICRS, galattico, eclittico), **mai assunto**; per i dati
  planetari è il corpo letto dai metadati secondo
  `19-core-dati-planetari.md`. Se `body` non si può ricavare, il dato si apre
  ma non si sovrappone né si combina con altri (`BODY_UNKNOWN`); la
  sovrapposizione tra corpi diversi segue D19-4 (`BODY_MISMATCH`, forzabile
  solo con opzione esplicita citata nel risultato).
- Le operazioni insiemistiche e i filtri si fanno solo tra MOC e dati dello
  stesso corpo; corpi diversi danno `BODY_MISMATCH` (stesso schema di D19-4).

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| MOC vuoto | consentito; contiene niente, operazioni definite | esito `MOC_EMPTY` |
| Ordine HEALPix non valido (negativo o oltre il max dello standard) | rifiuto con l'intervallo | `HEALPIX_ORDER_INVALID` |
| Regione fuori dal cielo o coordinate invalide | rifiuto dell'input | `REGION_INVALID` |
| Probabilità fuori [0,1] (o livello di credibilità fuori da (0, 1]) | rifiuto dell'input | `PROBABILITY_OUT_OF_RANGE` |
| Somma delle probabilità diversa da 1 oltre 10⁻⁶ relativo | rifiuto della mappa | `PROBABILITY_SUM_INVALID` |
| Mappa di probabilità senza le colonne o le parole chiave del formato | rifiuto della mappa | `PROBABILITY_MAP_INVALID` |
| Tempi non validi (fine prima dell'inizio, prima di JD 0, non finiti, numeri diversi) | rifiuto | `TIME_RANGE_INVALID` |
| Operazione tra MOC di unità diverse (spaziale vs temporale) | rifiuto con descrizione | `MOC_TYPE_MISMATCH` |
| MOC corrotto in lettura | errore con il file/la riga problematica | `MOC_UNREADABLE` |
| Tabella senza coordinate per il filtro o per la creazione | rifiuto prima del calcolo | `NO_COORD_COLUMNS` |
| Colonne di posizione senza sistema dichiarato | rifiuto | `FRAME_UNKNOWN` |
| Immagine senza WCS | nessun MOC | `WCS_MISSING` |
| Immagine aperta a due livelli (solo anteprima in memoria) | nessun MOC | `PREVIEW_NOT_MEASURABLE` |
| Immagine a colori | nessun MOC | `OPERATION_UNSUPPORTED` |
| Righe senza posizione / punti fuori dalla proiezione | esclusi e contati | avvisi `ROWS_EXCLUDED`, `POINTS_OUTSIDE_PROJECTION` |
| Griglia HEALPix troppo grande senza MOC che la limiti | rifiuto con il limite | `GRID_TOO_LARGE` |
| Corpo (`body`) non ricavabile dai metadati né dal sistema di coordinate | dato aperto da solo, non sovrapposto né combinato | `BODY_UNKNOWN` |
| Operazione o filtro tra MOC/dati di corpi diversi | rifiuto; forzatura solo con opzione esplicita citata nel risultato (D19-4) | `BODY_MISMATCH` |
| Versione del MOC non supportata | nessun MOC letto, errore con la versione trovata | `MOC_VERSION_UNSUPPORTED` |
| MocServer non raggiungibile | nessun filtro spaziale, errore esplicito | `MOCSERVER_UNAVAILABLE` |
| Risposta del MocServer non leggibile (es. pagina d'errore) | nessun elenco | `SERVICE_ERROR` |
| URL di un MOC non raggiungibile e senza copia in cache | nessun MOC | `NET_TIMEOUT` |
| JSON o testo senza prefisso di tipo e senza `kind` | nessuna lettura: il tipo non si assume | `MOC_TYPE_REQUIRED` |
| Scrittura in JSON o testo di un MOC di un corpo diverso da `celestial` | rifiuto (il corpo non si può dichiarare in quei formati) | `MOC_BODY_UNSUPPORTED` |
| Scrittura o lettura FITS di un MOC planetario o misto (`A2BODY`) | scritto/letto, estensione non standard dichiarata | avviso `MOC_NONSTANDARD_EXTENSION` |
| `A2BODY = 'mixed'` senza `A2BODIES` con almeno due corpi | nessun MOC letto | `MOC_UNREADABLE` |
| Operazione su un MOC misto senza `force_body=True` | rifiuto (scelta 5) | `BODY_MISMATCH` |
| File con `MOCVERS = '2.1'` | rifiuto: nessuna 2.1 tra i documenti IVOA (D16-6, decisa il 2026-10-12) | `MOC_VERSION_UNSUPPORTED` |

## 11. Esposizione all'IA

- **`moc_from_catalog`** / **`moc_from_region`** — input: tabella o regione +
  ordine; output: MOC. **Calcolo: libreria MOC/HEALPix.**
- **`moc_operations`** — input: due MOC + operazione; output: MOC.
  **Calcolo: libreria MOC.**
- **`filter_by_moc`** — input: tabella + MOC + dentro/fuori; output: conteggio
  e indici. **Calcolo: libreria MOC/NumPy.**
- **`describe_moc`** — input: MOC; output: superficie coperta (in steradianti
  o frazione di cielo), numero di celle, ordine. **Calcolo: libreria MOC.**

L'IA non calcola né approssima mai superfici o coperture.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | MOC da cerchio | creare un MOC di raggio 1° attorno a un punto (centro galattico, convertito in ICRS) all'ordine 9 | area ≈ 2π(1 − cos 1°) steradianti entro **celle di bordo × area di una cella** (celle attraversate dal cerchio contate nel test con `astropy-healpix`) | area ricalcolata nel test con la formula e con `astropy.units` |
| T2 | Circolo completo | unione di quattro quarti di cielo, ognuno da due triangoli d'ottante (poligoni), all'ordine 6 | area ≈ 4π steradianti entro celle di bordo (attraversate da equatore e meridiani 0°, 90°, 180°, 270°, contate con `astropy-healpix`) × area di una cella | ricalcolo con Astropy/`math` nel test |
| T3 | Proprietà insiemistiche | generare due MOC casuali con semina fissa; verificare A∪B ⊇ A∩B, (A∖B)∩B = ∅, ¬¬A = A | tutte le proprietà vere | controllo con le operazioni ricalcolate nel test |
| T4 | Filtro per Moc | 1000 punti casuali (semina fissa) e una riga senza posizione, MOC da cerchio all'ordine 6; dentro e fuori; corpo diverso; MOC temporale | conteggio e maschera coincidenti con quelli ricalcolati nel test con `astropy-healpix` (cella NESTED di ogni punto ∈ celle del MOC); riga senza posizione mai selezionata; tabella invariata; `BODY_MISMATCH` (forzabile), `MOC_TYPE_MISMATCH` | ricalcolo con la libreria HEALPix |
| T5 | Mismatch di unità | unire un MOC spaziale con uno temporale | `MOC_TYPE_MISMATCH` | test di unità |
| T6 | Mappe HEALPix | punti ai centri di celle note (3 e 1) con flussi, uno mancante; 500 punti casuali; griglia dell'ordine 1 e griglia limitata da un MOC | conteggi e somme esatti; valori uguali a `astropy-healpix` + `numpy` ricalcolati nel test; schema NESTED e sistema ICRS dichiarati; contorni uguali a `boundaries_lonlat`; il MOC dato non cambia; `GRID_TOO_LARGE` | ricalcolo con la libreria scelta |
| T7 | Versioni MOC (H22) | file di prova **scritti nel test secondo il testo dello standard** (mai file di Aladin): FITS 1.x (intestazioni di 1.0/1.1, colonna `UNIQ` `1J`), 2.0 `NUNIQ` e `RANGE` (spaziale, temporale, spazio-temporale), JSON con e senza prefisso, testo; `MOCVERS='2.1'`; versione sconosciuta; `kind` mancante | stesse celle lette da `mocpy`; versione riportata ("1.1, assunta…", "2.0", "non dichiarata nel formato"); 2.1 → `MOC_VERSION_UNSUPPORTED` (D16-6); `MOC_TYPE_REQUIRED`; andata e ritorno in scrittura | confronto con `mocpy` |
| T8 | Filtro MocServer (H26) | `query_mocserver` con un cerchio galattico e con un MOC su un servizio simulato; seconda richiesta uguale; `intersect` sconosciuto; proprietà riservata; poligono; risposta HTML d'errore; lettura di un MOC da URL (FITS e JSON, poi servizio spento); `build_moc` | parametri inviati (centro convertito in ICRS uguale ad astropy, `intersect`, `spacesys=C`, `moc` in POST); elenco delle collezioni con origine e data; seconda dalla cache; errori del §10; in cache solo FITS IVOA; `build_moc` uguale all'unione dei costruttori | servizio simulato (test di rete separati sul MocServer vero: collezioni attorno a M31 e lettura di un MOC da URL) |
| T11 | Tempo e probabilità (P4) | intervalli UTC e istanti TT; ST-MOC da due osservazioni con proiezioni; mappa multi-ordine sintetica nel formato LIGO; mappa piatta RING con colonna vettoriale; somma sbagliata, densità negativa, unità mancante, `COORDSYS='G'` | celle uguali a `mocpy` sui tempi convertiti in TCB con `astropy.time` nel test; regione di credibilità uguale al calcolo indipendente del test (densità decrescente, probabilità ≥ livello) e probabilità contenuta uguale; RING→NESTED uguale ad `astropy-healpix`; errori del §10 | ricalcolo con astropy, `astropy-healpix` e `numpy` |
| T10 | Creazione da catalogo e immagine (P2) | catalogo galattico con una riga senza posizione; immagine TAN tutta valida e con metà NaN, agli ordini 9 (blocchi) e 14 (k > 1); immagine intera con `BLANK`; immagine senza WCS; con i blocchi (D16-8): almeno 300 maschere casuali piccole (strisce sottili sul bordo, buchi interni, pixel isolati, blocchi parziali, rotazioni e ordini diversi) e, nei test di rete, l'immagine DSS della demo delle Pleiadi all'ordine 11 | celle uguali a `mocpy.MOC.from_lonlat` sulle posizioni ICRS ricalcolate con astropy; MOC dell'immagine tra il poligono degli angoli ristretto e allargato di una cella, area entro le celle di bordo; con i blocchi: b, passo e punti attesi dichiarati, nessuna cella persa rispetto al MOC pixel per pixel (angoli di ogni pixel valido) in nessun caso, MOC dentro quello pixel per pixel della maschera estesa ai blocchi validi (crescita ≤ b − 1 pixel); DSS: MOC identico al calcolo pixel per pixel (area 4,1399 deg²); `ROWS_EXCLUDED`, `WCS_MISSING`, `MOC_BODY_UNSUPPORTED` | ricalcolo con astropy e `mocpy` |
| T9 | MocServer assente (H26) | `query_mocserver` senza rete | `MOCSERVER_UNAVAILABLE`, nessun elenco parziale | test di unità |
| T12 | Corpo misto (scelta 5) | intersezione forzata celeste × Luna; poi unione, differenza, complemento, `contains` senza forzatura; con forzatura e un terzo corpo | `body = "mixed"` con i corpi ordinati; ogni operazione successiva senza forzatura → `BODY_MISMATCH`; con forzatura elenco dei corpi aggiornato e `BODY_FORCED` | test di unità |
| T13 | MOC planetari e misti in FITS (scelta 6) | scrivere e rileggere un MOC di Marte, un MOC misto e uno ST-MOC della Luna; JSON e testo di Marte; `A2BODIES` tolto | stesso MOC e stesso corpo dopo andata e ritorno; `A2BODY`, `MOCVERS='2.0'`, `COORDSYS='C'`; `MOC_NONSTANDARD_EXTENSION` in scrittura e lettura; nessuna parola chiave per un MOC celeste; `MOC_BODY_UNSUPPORTED`; `MOC_UNREADABLE` | lettura dell'intestazione con `astropy.io.fits` |
| T14 | Complemento ST-MOC (D16-7) | ST-MOC da due osservazioni; complemento | ordini conservati; ¬¬A = A; A ∩ ¬A = ∅; A ∪ ¬A copre tutto il cielo in tutto il tempo; su istanti e posizioni campione il complemento contiene esattamente ciò che A non contiene | ricalcolo con `mocpy` (`query_by_time`, `contains_lonlat`, `TimeMOC` di tutto il tempo) |

## 13. Decisioni aperte

- **D16-1 — Libreria MOC: DECISA il 2026-10-04.** **`mocpy`** (creazione e
  operazioni MOC, incluso i MOC temporali); le librerie HEALPix (`healpy` /
  `astropy-healpix`) restano per mappe e griglie. **Motivazione:** E6 richiede
  MOC spaziali **e temporali**, `mocpy` è allineato allo standard IVOA.
  **Verificato il 2026-10-11:** `mocpy` 0.20.0, licenza BSD, wheel macOS
  arm64 per Python 3.12; `healpy` escluso (GPL-2.0), mappe e griglie con
  `astropy-healpix`. Applicata in §8 qui sopra.
- **D16-2 — Serializzazione: DECISA il 2026-10-04.** I MOC vivono in cache in
  **formato FITS standard IVOA** (file su disco, con origine e data come gli
  altri dati della cache A7); l'export offre anche **JSON** e **testo**.
  **Motivazione:** formato standard della comunità (regola d'oro n. 4),
  tracciabilità A7 già prevista per i file; SQLite resta per le tabelle.
  Applicata in §4/§6/§7/§9 qui sopra.
- **D16-3 — MOC temporali: DECISA il 2026-10-04.** **Tempo numerico
  internamente (JD tramite `astropy.time`), ISO 8601 solo nell'interfaccia e
  nei file**; **si dichiara sempre la scala di tempo**; i **MOC temporali
  usano la scala dello standard IVOA (da verificare)**. **Motivazione:** i
  calcoli insiemistici devono restare numerici e deterministici; la
  leggibilità la risolvono le conversioni di presentazione. Regola scritta in
  `02-convenzioni.md` DC1 (aggiornata). Applicata in §6/§9 qui sopra.
- **D16-4 — Mappe di probabilità: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** mappe LIGO/Virgo/KAGRA in
  HEALPix **piatte e multi-ordine** (sez. 8.1 del manuale di Aladin); somma
  delle probabilità verificata uguale a 1 entro una tolleranza dichiarata;
  regioni di credibilità calcolate con `mocpy` (funzione **da verificare prima
  del codice**).
- **D16-5 — Cataloghi HiPS progressivi (H12): DECISA il 2026-10-04, insieme
  a D12-5.** **Computazioni HEALPix nel `16`, servizio dei tile nel `12`**
  (stesso confine scritto in `12-core-hips.md`). **Motivazione:** due
  decisioni sullo stesso confine devono dare lo stesso risultato, altrimenti i
  due file si contraddicono; nessuna logica HEALPix duplicata. Applicata in
  §3 qui sopra.

- **D16-6 — Versione "2.1" del formato MOC: DECISA il 2026-10-12
  (decisione del proprietario).** Cercare la 2.1 sul sito IVOA tra Working
  Draft e Proposed Recommendation (non nel manuale di Aladin, regola d'oro
  n. 8): se esiste come bozza, leggerla con l'avviso "versione non ancora
  raccomandazione IVOA" citando il documento; se non esiste, resta
  rifiutata. **Esito della verifica del 2026-10-12:** l'elenco dei documenti
  IVOA (`https://www.ivoa.net/documents/`) riporta per MOC solo WD/PR/REC
  1.0 (2013–2014), WD-MOC-1.1-20190215, PR-MOC-1.1 (2019-04-04, 2019-06-21,
  2019-09-03), REC-MOC-1.1-20191007, WD-MOC-2.0 (2020-11-12, 2021-03-24,
  2021-10-14, 2021-10-18), PR-MOC-2.0 (2021-11-01, 2022-01-25),
  REC-MOC-2.0-20220727 e la Note STMOC 1.0 (2019-05-15); il repository
  pubblico del testo dello standard (`ivoa-std/MOC`) dichiara versione 2.0,
  REC del 2022-07-27. **Nessuna 2.1, nemmeno come bozza → un file con
  `MOCVERS='2.1'` resta rifiutato** (`MOC_VERSION_UNSUPPORTED`, con l'esito
  della verifica nel messaggio).

- **D16-7 — Complemento dei MOC spazio-temporali: DECISA il 2026-10-12
  (decisione del proprietario, opzione c).** Complemento = differenza tra lo
  ST-MOC "tutto il tempo × tutto il cielo" (agli stessi ordini del MOC dato,
  costruito con il lettore di testo di `mocpy`: `t0/0-1 <ordine>/ s0/0-11
  <ordine>/`) e il MOC dato, **solo con operazioni di `mocpy`**; il tempo
  "tutto" è quello dello standard (JD 0 – circa JD 5,3 × 10⁷, uguale al
  complemento del `TimeMOC` vuoto, verificato). **Verifica del 2026-10-12:**
  `mocpy` 0.20.0 lascia nei risultati delle operazioni tra ST-MOC elementi
  con un insieme di tempi vuoto (stessa copertura, rappresentazione non
  normalizzata, per cui `==` dà falso tra MOC uguali); il 16 normalizza ogni
  risultato spazio-temporale con la rilettura JSON di `mocpy`, che li toglie.
  Test T14.

- **D16-8 — MOC da immagine con i blocchi: celle perse al bordo — DECISA il 2026-10-14.** La regola dei
  blocchi (b × b pixel, b = ⌊cella / (2 × pixel)⌋, angoli dei blocchi validi) da sola non garantisce "mai
  perdere celle": una cella che tocca il contorno solo con una striscia più stretta del passo non contiene
  angoli di blocco (misure del 2026-10-14: DSS2 della demo all'ordine 11, area 4,1104 deg² contro 4,1399;
  celle perse in 15 immagini casuali su 30). **Decisione del proprietario:** al MOC a blocchi si aggiungono
  gli **angoli dei pixel lungo il contorno della regione dei blocchi validi**; crescita massima ai bordi
  **b − 1 pixel** (non mezzo blocco); il risultato dichiara la dimensione del blocco. Applicata in §3,
  test in §12 (T10).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). Perimetro da E6/H9/H12 di `03-parita-aladin.md`. |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario: D16-1, D16-2, D16-3 e D16-5 passate da aperte a decise.** D16-1: `mocpy` per MOC (spaziali e temporali), licenza e installazione su macOS da verificare prima dell'approvazione (§8). D16-2: MOC in cache in **FITS standard IVOA**, export anche JSON e testo (§4/§6/§7/§9). D16-3: tempo numerico interno (JD via `astropy.time`), ISO 8601 solo in interfaccia/file, scala sempre dichiarata, scala IVOA per i MOC temporali (da verificare) — regola in `02-convenzioni.md` DC1 (§6/§9). D16-5: computazioni HEALPix nel 16, servizio dei tile nel 12 (§3; pari a D12-5 in `12-core-hips.md`). Decisioni riportate in `decisioni-aperte.md`. |
| 2026-10-08 | Claude Code | §5: aggiunti a "Usato da" i moduli `19-core-dati-planetari.md` (scritti il 2026-10-08, stato bozza). Nessun altro testo cambia. |
| 2026-10-09 | Claude Code | **D19-3 applicata (decisione del proprietario del 2026-10-08):** campo `body` obbligatorio nei metadati di ogni MOC; operazioni e filtri solo tra lo stesso corpo (§6, §9, §10); per i dati astronomici `celestial`, ricavato dal sistema di coordinate, mai assunto; errori `BODY_UNKNOWN` e, per le sovrapposizioni, `BODY_MISMATCH` secondo D19-4 (forzabile solo con opzione esplicita citata nel risultato). |
| 2026-10-09 | Claude Code | **D16-4 DECISA** (checklist del livello 1): mappe LIGO/Virgo/KAGRA piatte e multi-ordine, somma verificata = 1, regioni di credibilità con `mocpy` (da verificare). |
| 2026-10-09 | Claude Code | **Completamento con gli esiti di AP5** (decisione del proprietario del 2026-10-09): §3, §6, §7, §8, §10, §12 per H22 (versioni MOC 1.0–2.1, FITS e JSON; supporto in `mocpy` da verificare) e H26 (filtro spaziale delle collezioni con il MocServer, client `astroquery.mocserver`). Nessuna nuova decisione dei Gruppi 1 e 2. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** (regola del proprietario del 2026-10-09): modulo completato con gli esiti di AP5, nessuna decisione aperta nei Gruppi 1 e 2. |
| 2026-10-09 | Claude Code | **Collegamento alla cache comune `04-cache.md`** (approvato il 2026-10-09; decisione CA4 del proprietario, autorizzazione esplicita a modificare il file approvato): §5, §7, §9 — MOC salvati come file nella cache comune `SharedCache`. Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **Decisioni del proprietario del 2026-10-11 applicate** (autorizzazione esplicita a modificare il file approvato): divisione in 5 parti; `healpy` escluso (GPL), solo `astropy-healpix` e `mocpy`; `order_max` obbligatorio; MOC da catalogo una cella per sorgente; MOC da immagine dai pixel validi con il WCS dell'11; poligoni a lati di cerchio massimo (interno = regione più piccola, verificato in `mocpy`); MOC spaziali sempre ICRS; somma delle probabilità entro 10⁻⁶ relativo; tolleranze di T1/T2 dalle celle di bordo; MocServer con la rete del 14; `build_moc` solo funzione; mappe NESTED ICRS; C4 e cataloghi HiPS progressivi rinviati al 12. Verifiche del 2026-10-11: versioni dello standard (1.0, 1.1, 2.0; nessuna 2.1), intestazioni FITS, JSON e testo, scala TCB dei MOC temporali. Nuovi `MOC_TYPE_REQUIRED`, `MOC_BODY_UNSUPPORTED`; nuove decisioni aperte **D16-6** (versione 2.1) e **D16-7** (complemento degli ST-MOC), Gruppo 3. Scelte minori di P1 elencate in §3. Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **P2 scritta** (`moc_from_region` con `CircleRegion`/`PolygonRegion`, `moc_from_catalog`, `moc_from_image`; T1, T2, T10): cerchio con `from_cone` (per eccesso), poligono con `from_polygon` (celle di bordo diverse tra i due versi, verificato), catalogo una cella per sorgente, immagine dai pixel validi campionati a passo ≤ metà cella con il WCS dell'11 (scelta minore da confermare, motivi in §3). Nuovi casi in §10. Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **P3 scritta** (`filter_by_moc`/`FilterResult`, `Moc.contains`, `healpix_map`/`HealpixMap`, `healpix_grid`/`HealpixGrid`; T4, T6): NESTED in ICRS con `astropy-healpix`; righe senza posizione mai selezionate; limite della griglia senza MOC (scelta minore, `GRID_TOO_LARGE`); verificato che `refine_to_order` di `mocpy` modifica sul posto. Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **P4 scritta** (`moc_from_times`, `moc_space_time`, `read_probability_map`/`ProbabilityMap`, `moc_from_probability`; metodi temporali di `Moc`; T11): TCB con `astropy.time`; formato delle mappe LIGO/Virgo/KAGRA verificato sulla guida pubblica; regione di credibilità a celle intere con probabilità ≥ livello (scelta minore da confermare), probabilità contenuta dichiarata; nuovi `TIME_RANGE_INVALID`, `PROBABILITY_SUM_INVALID`, `PROBABILITY_MAP_INVALID`. Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **P5 scritta — modulo 16 completo tranne i pezzi fermi D16-6 e D16-7** (`query_mocserver`/`MocServerResult`, lettura da URL in `read_moc`, `build_moc`; T8, T9): interfaccia del MocServer verificata (due comportamenti non documentati: `intersect` sconosciuto ignorato, STC con sistema rifiutato), rete e cache del 14; poligoni inviati come MOC (scelta minore); MOC da URL in cache sempre in FITS IVOA; tipo dei file di `build_moc` esplicito. Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **Decisioni del proprietario del 2026-10-12** (autorizzazione esplicita a modificare il file approvato): **D16-6 decisa** — verifica sul sito IVOA, nessuna 2.1 tra WD e PR, resta rifiutata (§3, §10, §13); **D16-7 decisa** — complemento degli ST-MOC come differenza da "tutto il tempo × tutto il cielo" con `mocpy`, normalizzazione dei risultati ST (§7, §13, T14); **scelta 5 cambiata** — risultato forzato con `body = "mixed"` ed elenco dei corpi, nuova forzatura per ogni operazione successiva (§3, §10, T12); **scelta 6 cambiata** — MOC planetari e misti scritti in FITS 2.0 con `A2BODY`/`A2BODIES`, estensione non standard dichiarata (`MocWriteResult`, `MOC_NONSTANDARD_EXTENSION`), riletti dal 16; JSON e testo non celesti rifiutati (scelta minore da confermare) (§3, §7, §10, T13); scelte minori 1–4 e 7–13 confermate. Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **Allineamento specifica–codice** (decisione del proprietario del 2026-10-12, autorizzazione esplicita a modificare il file approvato): §3 P5 — risposte del MocServer dichiarate ISO-8859-1 e lette secondo la codifica dichiarata (`MOCSERVER_CHARSET` del 14), regola già applicata nel codice di `query_mocserver`; **scelte minori del 16 tutte confermate** dal proprietario (le voci "da confermare" di §3 diventano confermate). Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **Difetto trovato dalla demo delle Pleiadi** (correzione che rispetta la specifica; registrata su indicazione del proprietario): la descrizione di `FilterResult` diceva "righe dentrol MOC" per `inside=True`; ora "righe dentro il MOC" ("fuori dal MOC" invariato). Test T4 esteso col controllo del testo. Nessun cambiamento di comportamento o di valori. Stato `approvato` invariato. |
| 2026-10-14 | Claude Code | **D16-8 aperta (Gruppo 3)**: la regola dei blocchi per `moc_from_image` decisa il 2026-10-14 perde celle sul bordo (misure in §13); regola e codice dei blocchi non applicati, in attesa della decisione del proprietario. §3 invariato. Stato `approvato` invariato. |
| 2026-10-14 | Claude Code | **D16-8 decisa e applicata** (decisione del proprietario del 2026-10-14, autorizzazione esplicita a modificare il file approvato): §3 — MOC da immagine con pixel piccolo su blocchi di b × b pixel (regola del proprietario del 2026-10-14) più gli angoli dei pixel lungo il contorno della regione dei blocchi validi; crescita massima ai bordi b − 1 pixel (corretto "mezzo blocco"); dimensione del blocco, passo e punti dichiarati nel risultato. §12 T10 esteso (300 maschere casuali contro il MOC pixel per pixel; immagine DSS della demo con test di rete). §13 D16-8 decisa. Stato `approvato` invariato. |
