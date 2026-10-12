# 12-core-hips.md — servizi HiPS all-sky

**Stato:** approvato

## 2. Scopo

Fornire le immagini all-sky HiPS (survey astronomici) con la stessa facilità
di navigazione di Aladin, mantenendo tracciabili provenienza e data di ogni
riquadro mostrato.

## 3. Cosa fa

- **Sfoglio dei survey HiPS (C1):** elencare i survey disponibili, permettere
  di attivarne uno e navigare (zoom/pan) con caricamento progressivo dei
  riquadri (tile).
- **Survey predefiniti (C2):** l'elenco dei survey è **dinamico**, letto dal
  MocServer (H26, D12-3), così resta aggiornato senza una tabella mantenuta
  a mano; il survey attivo all'avvio è **DSS2 a colori** (D12-3).
- **Richiesta dei riquadri:** scaricare i tile necessari al campo visualizzato
  mantenendo la risoluzione appropriata, con timeout e ripiego se la rete
  manca.
- **Cache su disco (A7):** i riquadri HiPS si conservano come file nella
  **cache comune di `04-cache.md`** (`~/Library/Caches/AstroTwo/`, un solo
  limite di 5 GB per tutta la cache, timeout 10 s / 60 s), con eliminazione
  dei dati meno usati e provenienza (origine + data di scaricamento) per ogni
  riquadro servito; il modulo non ha una cache propria (CA4).
- **Impronta del survey (C4):** mostrare la copertura del survey attivo —
  i dati di copertura appartengono a `16-core-moc.md`, questo modulo fornisce
  l'identità e la posizione del survey.
- **Generazione di HiPS (H9):** creare un nuovo HiPS a partire da un set di
  immagini, anche da riga di comando, secondo lo **standard pubblico IVOA
  HiPS 1.0** (D12-1, corretta il 2026-10-10): ricampionamento dei tile con
  `reproject` dove la libreria lo offre, **codice nostro** per il resto
  (struttura delle cartelle e degli ordini, file `properties`, anteprima
  `Allsky`, tile JPEG/PNG da quelli FITS); la copertura MOC del nuovo HiPS si
  calcola con `16-core-moc.md`. Nessuno strumento esterno.
- **Cataloghi HiPS progressivi, mappe e griglie HEALPix (H12):** servire
  cataloghi come livelli progressivi (caricamento per ordine HEALPix) e
  produrre/disegnare mappe e griglie HEALPix. **Confine deciso il 2026-10-04
  (D12-5, pari a D16-5):** i **dati e le computazioni HEALPix vivono in
  `16-core-moc.md`**, qui resta il **servizio dei tile** — nessuna logica
  HEALPix duplicata.
- **Aggiunta di un HiPS da identificativo o URL (C3):** aggiungere all'elenco
  un servizio HiPS non presente, indicandone l'**identificativo** (es.
  `CDS/P/PanSTARRS/DR1/r') o l'**URL di base** del servizio. Il modulo
  **legge i metadati del servizio** (titolo del survey, banda, risoluzione
  massima, formato dei tile, versione, pagina di descrizione, copertura),
  **valida** che la risposta corrisponda davvero a un servizio HiPS, registra
  la voce con la sua provenienza e la rende attivabile come le altre; se
  l'URL non risponde, non è un servizio HiPS o i metadati sono incompleti,
  rifiuta l'operazione con errore esplicito (§10) senza aggiungere nulla.
  Inclusa per decisione del proprietario (2026-10-04): in Aladin la funzione
  non risulta documentata, ma la parità con Aladin è il minimo.
- **Schede server (H10, parte HiPS):** aggiungere immagini da servizi di
  terze parti (es. SkyView); la parte protocollo/VO di H10 è in
  `14-core-protocolli-vo.md`.
- **Cubi HiPS (H24, sez. 8.1 del manuale di Aladin, ed. giugno 2022):** survey
  progressivi a cubo secondo lo standard HiPS 1.0 (tile per piano, profondità
  del cubo nelle proprietà del servizio; nomi esatti delle proprietà **da
  verificare** nello standard). Si scarica il tile del piano richiesto;
  scorrimento dei piani nel 41, analisi dei cubi nel 23.
- **Filtro delle collezioni (H26, sez. 8.3.3):** l'elenco delle collezioni
  (proprietà dei servizi HiPS e dei cataloghi) si ottiene dal **MocServer**
  del CDS, si sincronizza all'avvio e se ne conserva una copia locale nella
  cache A7 con origine e data. Il filtro **sulle proprietà** (testo, regole)
  è locale; il filtro **spaziale** per copertura è di `16-core-moc.md`
  (`query_mocserver`). Client: **la rete del 14** (`MOCSERVER_URL`, cache e
  registro comuni), **non `astroquery.mocserver`** (decisione del
  proprietario del 2026-10-12). Senza rete si usa la copia locale con la sua
  data.
- **Immagini di qualsiasi dimensione, parte HiPS (H27, sez. 8.3.1):** si
  scaricano solo i tile del campo visualizzato all'ordine adatto, conservati
  nella cache su disco; il valore del pixel sotto il cursore si legge dal tile
  FITS in cache, mai da una copia ridotta per la visualizzazione.

### Decisioni del proprietario del 2026-10-12 e divisione in parti

1. **MocServer** tramite la rete del 14, non `astroquery.mocserver`.
2. **`healpy` tolto** (§8, §11) e **`healpix_map`/`healpix_grid` tolte dal
   §7**: mappe e griglie HEALPix sono solo del 16 (delega, nessuna funzione
   qui).
3. **H10 SkyView:** tramite SIA nel 14 se l'URL SIA di SkyView è verificato
   sul sito ufficiale NASA, altrimenti rinviato con il motivo. **Esito della
   verifica del 2026-10-12: rinviato.** Le pagine di documentazione di
   SkyView (`skyview.gsfc.nasa.gov`: pagina principale, `docs/batchpage.html`,
   `docs/other_interfaces.html`, `docs/otherservices.html`, `help/help.html`)
   non documentano un URL SIA; un indirizzo `…/current/cgi/vo/sia.pl` risponde
   con un VOTable SIA, ma non è dichiarato sul sito ufficiale, quindi non si
   usa (regola: niente URL non verificati). Si riprende quando l'URL è
   documentato da NASA.
4. **`tiles_for_fov`:** campo **a cerchio** (centro, raggio) finché non
   esiste il 41.
5. **Tile corrotto:** una sola nuova richiesta, poi `HIPS_BAD_TILE`.
6. **`build_hips`:** ordine massimo **obbligatorio**; larghezza dei tile
   **512 pixel di default**, dichiarata; tile **FITS sempre**; PNG/JPEG
   facoltativi, con **parametri di visualizzazione espliciti obbligatori**
   (come per l'RGB dell'11).
7. **Memoria (A10 per gli HiPS, decisa):** tile in memoria entro **512 MB,
   configurabili**; `build_hips` lavora **un tile alla volta** e rispetta il
   **limite delle operazioni** (4 GB, D11-11); su disco la cache comune
   (5 GB).

**Divisione in 5 parti (approvata dal proprietario il 2026-10-12):**

| Parte | Contenuto | Test |
|---|---|---|
| P1 | metadati e `add_hips` (C3), file `properties` dello standard HiPS 1.0, corpo da `hips_frame`, `HIPS_NOT_A_SERVICE`, `HIPS_METADATA_INVALID` | T7, T8 |
| P2 | tile: `tiles_for_fov` (`astropy-healpix`), `fetch_tile` con cache comune e provenienza, tile FITS/PNG/JPEG, tile corrotti, fuori copertura con il MOC del servizio (16), valore del pixel dal tile FITS (H27) | T2–T6, T12 |
| P3 | elenco delle collezioni: `CollectionIndex`, `HiPSList`, `set_survey` con default DSS2 a colori, `survey_coverage` (C4) | T1, T10, T11 |
| P4 | cubi HiPS (H24) e cataloghi HiPS progressivi (H12) | T9 + test nuovo |
| P5 | `build_hips` (H9) secondo HiPS 1.0 con `reproject` | test nuovi |

**Verifiche del 2026-10-12 (prima del codice):**

- **Standard HiPS 1.0** (REC 2017-05-19, testo PDF letto il 2026-10-12;
  è l'ultima raccomandazione: tra i documenti IVOA c'è anche un **Working
  Draft HiPS 2.0 del 2026-05-01**, non raccomandazione):
  - **file `properties`** (§4.4.1): UTF-8, una proprietà per riga `chiave =
    valore`, spazi attorno a `=` ignorati, righe che iniziano con `#` e righe
    vuote ignorate, la chiave non contiene `=` né spazi, ordine libero, alcune
    chiavi ripetibili. **9 chiavi obbligatorie:** `creator_did`, `obs_title`,
    `dataproduct_type` (`image`, `catalog`, `cube`), `hips_version` (`1.4`
    per lo standard 1.0), `hips_release_date` (ISO 8601
    `YYYY-mm-ddTHH:MMZ`), `hips_status`, `hips_tile_format` (tra `fits`,
    `jpeg`, `png` per immagini e cubi, `tsv` per i cataloghi; il primo è il
    formato suggerito), `hips_order` (intero), `hips_frame` (`equatorial` =
    ICRS, `galactic`, `ecliptic`). Obbligatorie in casi particolari:
    `dataproduct_subtype` (`color`, `live`) e `hips_cube_depth` (cubi).
    Facoltative usate qui: `hips_tile_width` (default 512), `obs_regime`,
    `em_min`/`em_max` (metri), `hips_pixel_scale` (gradi), `obs_description`,
    `hips_service_url`, `moc_sky_fraction`, `hips_cube_firstframe`,
    `data_cube_crpix3`/`crval3`/`cdelt3`/`bunit3`.
  - **URL** (§4.1, §6.2): tile `NorderK/DirD/NpixN.ext` con `D =
    (N/10000)×10000` (divisione intera), estensioni minuscole `.fits`,
    `.jpg`, `.png` (e `.tsv` per i cataloghi); `properties`, `Moc.fits`
    (MOC del servizio, consigliato per i HiPS equatoriali o a cielo intero;
    il MOC è solo equatoriale), `NorderK/Allsky.ext` (ordini 0–3, facoltativo);
    numerazione HEALPix **NESTED**; ordini bassi 0–2 omissibili, albero
    parziale ammesso.
  - **Cubi** (§4.2.3): tile di ogni piano con il suffisso `_n` (n = indice del
    piano, il tile senza suffisso è il piano 0), profondità in
    `hips_cube_depth`.
  - **Cataloghi** (§4.2.2): tile TSV UTF-8 (prima riga = nomi delle colonne,
    `#` = commento, campo vuoto = nullo), descrizione delle colonne in
    `metadata.xml` (VOTable); `Allsky` = concatenazione dei tile.
- **Corpo dei HiPS planetari:** lo standard 1.0 non lo prevede; il **WD HiPS
  2.0** (2026-05-01) aggiunge `hips_body` (nome del corpo in minuscolo, es.
  `mars`, `moon`) e ammette in `hips_frame` il "frame del corpo". Nei HiPS
  planetari del MocServer (verifica del 2026-10-12, es. `CDS/P/Mars/MGS-MOLA-DEM`)
  si trovano `hips_frame = mars` e `hips_body = mars`. **Regola (scelta
  minore, da confermare):** `hips_frame` in `equatorial`, `galactic`,
  `ecliptic` → `body = "celestial"` (D19-3, ricavato dal sistema); altrimenti
  `body = hips_body` se presente **e uguale** a `hips_frame`, con l'avviso
  `HIPS_BODY_DRAFT` ("`hips_body` è del Working Draft HiPS 2.0, non ancora
  raccomandazione IVOA"); senza `hips_body`, o con valori diversi →
  `body = None` e `BODY_UNKNOWN` (il dato si apre da solo, mai sovrapposto).
  Il nome resta come scritto dal servizio (minuscolo): l'eventuale
  allineamento ai nomi del 19 si fa con il 19 (**D12-6**, da decidere).
- **DSS2 a colori nel MocServer** (verifica del 2026-10-12): identificativo
  **`CDS/P/DSS2/color`** (`creator_did = ivo://CDS/P/DSS2/color`), servizio
  `https://alasky.cds.unistra.fr/DSS/DSSColor`, `hips_tile_format = jpeg`
  (solo JPEG: il valore del pixel H27 non è disponibile su questo survey),
  `hips_order = 9`, `hips_frame = equatorial`, `dataproduct_subtype = color`.
- **`astropy-healpix` 2.0.1, `cone_search_lonlat`:** restituisce **tutte le
  celle che toccano il cerchio, anche in parte** (documentazione e prova:
  stesse celle di un conteggio indipendente con i contorni campionati);
  quindi `tiles_for_fov` dà un insieme per eccesso.
- **Disposizione dei pixel nel tile** (necessaria per H27, non scritta nel
  testo dello standard 1.0): verificata il 2026-10-12 in due modi
  indipendenti. Per un punto, la cella all'ordine K+S (S = log₂ larghezza)
  è c; tile N = c >> 2S; sotto-indice v = c mod 4^S; a = bit pari di v,
  b = bit dispari (de-interlacciamento dell'ordine NESTED); nell'array letto
  con `astropy.io.fits` (indici da 0, riga = y): **colonna x = b, riga
  y = larghezza − 1 − a**. Prove: (1) quattro stelle brillanti (Betelgeuse,
  Rigel, Aldebaran, Antares) nei tile FITS dell'ordine 6 di
  `CDS/P/2MASS/K`: il massimo del tile cade entro 1–4 pixel dalla posizione
  prevista, e solo per questa delle 8 orientazioni possibili; (2) 400 punti
  casuali: stessa colonna e riga del WCS HPX per tile calcolato da
  `reproject` 0.21 (funzione interna, usata solo per la verifica).
- **`reproject` 0.21.0** (funzioni HiPS pubbliche: `reproject_to_hips`,
  `coadd_hips`, `hips_as_dask_array`): `reproject_to_hips` ricampiona **una
  sola immagine** un tile alla volta, scrive i **tile FITS in `float32`**,
  costruisce gli ordini inferiori con la media dei 4 sotto-tile e il file
  `properties`, ma **non** scrive `Allsky` né `Moc.fits`; `coadd_hips` non
  combina tile FITS sovrapposti (`NotImplementedError`). Esito per P5 da
  fissare prima di P5 (vedi P5).

**P1 — metadati e `add_hips` (scritta il 2026-10-12):**

- **`parse_properties(text)`** → dizionario chiave → tupla dei valori (chiavi
  ripetibili); una riga non vuota, non commento e non nella forma `chiave =
  valore` (es. una pagina HTML) → `HIPS_NOT_A_SERVICE`.
- **`read_service(url, *, cache, refresh, timeouts)`** → **`HiPSService`**:
  legge `URL/properties` con la rete del 14 (protocollo `hips`, cache e
  registro comuni; la risposta va in cache **solo se valida**). Risposta
  HTTP d'errore (es. 404), non UTF-8, non `properties`, o senza nessuna delle
  9 chiavi obbligatorie → `HIPS_NOT_A_SERVICE`; una chiave obbligatoria
  mancante o un valore non valido (`dataproduct_type` fuori da `image`,
  `catalog`, `cube` — i tipi del WD 2.0 non si leggono —, formati non
  ammessi per il tipo, `hips_order` non intero o fuori da [0, 29],
  `hips_tile_width` non potenza di 2, cubo senza `hips_cube_depth`, data non
  ISO 8601, numeri non leggibili) → `HIPS_METADATA_INVALID` con il campo.
  `HiPSService` porta identificativo (`creator_did` senza `ivo://`), URL di
  base, titolo, tipo e sottotipo, versione, data di rilascio, stato,
  formati (il primo è quello suggerito), ordine massimo, frame, larghezza dei
  tile, corpo, profondità del cubo, banda (`obs_regime`, `em_min`/`em_max`
  in metri), scala dei pixel, descrizione, tutte le proprietà, origine, data
  e richiesta registrata. Avvisi: `HIPS_DEFAULT_TILE_WIDTH` (larghezza
  assente → 512, default dello standard), `HIPS_VERSION_UNKNOWN`
  (`hips_version` diverso da `1.4`), `HIPS_BODY_DRAFT`, `BODY_UNKNOWN`.
- **`add_hips(id_o_url)`** (C3): un URL (`http://`, `https://`) si legge
  direttamente; un identificativo (anche con `ivo://`) si risolve con il
  MocServer (rete del 14, `ID=…&get=record&fmt=json`) nell'URL del servizio
  (`hips_service_url`), poi si leggono le proprietà **dal servizio**.
  Identificativo sconosciuto → `HIPS_UNKNOWN`; collezione senza servizio
  HiPS → `HIPS_NOT_A_SERVICE`; MocServer non raggiungibile →
  `MOCSERVER_UNAVAILABLE`; `creator_did` diverso dall'identificativo →
  avviso `HIPS_ID_MISMATCH` (vale quello del servizio).
- **`HiPSList`**: elenco dei servizi per identificativo; `add_hips` aggiunge
  solo un servizio valido (in errore l'elenco non cambia); una voce già
  presente si rilegge solo con `refresh=True` (altrimenti avviso
  `HIPS_ALREADY_LISTED`); `get(id)` → `HIPS_UNKNOWN` con gli identificativi
  noti.

**P2 — tile (scritta il 2026-10-12):**

- **`tile_path(ordine, indice, estensione, *, plane=None)`** → percorso dello
  standard (`NorderK/DirD/NpixN.ext`, suffisso `_n` per i piani dei cubi).
- **`tiles_for_fov(center, radius, order, *, frame="equatorial",
  coverage=None)`** → **`TileSelection`** (ordine, indici ordinati, frame,
  tile esclusi, descrizione): centro convertito nel frame del HiPS con il 10
  (`equatorial` = ICRS, `galactic`), `cone_search_lonlat` di
  `astropy-healpix` (celle che toccano il cerchio); raggio in (0°, 180°]
  (`REGION_INVALID`), ordine in [0, 29]. Con `coverage` (MOC del servizio,
  16) restano solo i tile che toccano il MOC (celle del MOC portate
  all'ordine del tile con `mocpy`); nessuno → `HIPS_OUT_OF_COVERAGE`. Il
  filtro vale solo per i HiPS equatoriali (il MOC è ICRS); per gli altri
  frame non si applica, avviso `HIPS_COVERAGE_NOT_CHECKED` (scelta minore,
  da confermare). `hips_frame = ecliptic` → `HIPS_FRAME_UNSUPPORTED`: lo
  standard non dice quale eclittica (**D12-7**, da decidere); frame
  planetari → `HIPS_FRAME_UNSUPPORTED` fino al 19.
- **`order_for_resolution(service, resolution)`**: ordine più basso con il
  pixel del tile non più grande della risoluzione chiesta
  (`nside_to_pixel_resolution` di `astropy-healpix`); oltre, l'ordine
  massimo con l'avviso `HIPS_RESOLUTION_LIMIT`.
- **`fetch_tile(service, order, index, *, format=None, plane=None,
  coverage=None, cache, refresh, timeouts, memory=None)`** → **`HiPSTile`**
  (dati, intestazione FITS, URL, data, da cache sì/no, corpo, avvisi;
  `provenance()`): prima la memoria (`TileMemory`), poi la cache comune
  (file del modulo `12`, con origine e data; `CACHE_FULL` non blocca), poi
  la rete con i timeout di `04`, scaricamento intero o niente. Formato di
  default = il primo di `hips_tile_format`; un formato non offerto →
  `HIPS_FORMAT_UNAVAILABLE`. Tile FITS nel **tipo nativo** (DC6, es. `>f4`);
  JPEG/PNG letti con Pillow e **capovolti** nell'orientamento FITS (lo
  standard scrive le righe dall'alto in basso). Controlli: FITS leggibile
  con dati, immagine del formato dichiarato, lato = `hips_tile_width`;
  altrimenti tile scartato (`HIPS_TILE_DISCARDED`), **una sola nuova
  richiesta**, poi `HIPS_BAD_TILE` (decisione 5; una copia corrotta in cache
  conta come primo tentativo). HTTP 404 → **`HIPS_TILE_MISSING`** (lo
  standard ammette alberi parziali e ordini bassi omessi; scelta minore, da
  confermare); ordine oltre quello del servizio → `HEALPIX_ORDER_INVALID`;
  indice fuori dall'ordine → `HEALPIX_INDEX_INVALID`; fuori dal MOC dato →
  `HIPS_OUT_OF_COVERAGE` senza richiesta; rete assente senza copia →
  `NET_TIMEOUT`, nessun tile finto.
- **`service_coverage(service)`** → (MOC, avvisi): `Moc.fits` del servizio
  letto con `read_moc` del 16 (cache in FITS IVOA); file assente (HTTP 404)
  → `None` con `HIPS_COVERAGE_UNKNOWN` (il file è solo consigliato).
- **`TileMemory(limit_bytes=512_000_000)`** (A10): tile in memoria, i meno
  usati di recente tolti oltre il limite (contati in `evicted`); un tile più
  grande del limite non si tiene. Non è una cache su disco (CA4).
- **Valore del pixel (H27):** **`pixel_values(service, coords, *,
  order=None, …)`** e **`tile_pixel_values(tile, coords)`** →
  **`PixelValues`** (valori nel tipo del tile, tile, colonna e riga da 0,
  ordine, `BUNIT`, descrizione): solo dai **tile FITS** (altrimenti
  `HIPS_PIXEL_UNAVAILABLE`), ordine di default = il più profondo; tile e
  pixel secondo la disposizione verificata (§3); posizioni fuori dal tile
  dato → `HIPS_OUT_OF_TILE`.

**P3 — collezioni, survey attivo, copertura (scritta il 2026-10-12):**

- **Verifica del 2026-10-12:** il MocServer risponde in JSON dichiarato
  **ISO-8859-1** (`Content-Type: application/json;charset=ISO-8859-1`; es.
  "µm" in un byte): le risposte si leggono con quella codifica
  (`MOCSERVER_CHARSET` del 14; corretti anche `vizier_collections` del 14 e
  `query_mocserver` del 16, che leggevano in UTF-8). Collezioni con un
  servizio HiPS (`expr=hips_service_url=*`): 1582 record, circa 600 kB con
  le proprietà scelte; tipi anche del WD 2.0 (`spectral-cube`, `time-cube`),
  che restano nell'indice ma non si attivano (`HIPS_METADATA_INVALID`).
- **`CollectionIndex(cache, timeouts)`** (H26): **`sync()`** chiede al
  MocServer (rete del 14, sempre dalla rete) le collezioni con un servizio
  HiPS e le proprietà **`INDEX_FIELDS`** (identificativo, titolo, banda,
  tipo e sottotipo, URL del servizio, ordine, frame, corpo, formati,
  `em_min`/`em_max`, frazione di cielo, categoria; **scelta minore, da
  confermare**), ordinate per identificativo, con origine, data e richiesta
  registrata; la risposta resta nella cache comune come **copia locale**.
  Rete assente: si usa la copia locale con la sua data (avviso
  `MOCSERVER_UNAVAILABLE`); senza copia → `MOCSERVER_UNAVAILABLE`.
  **`filter(text=None, **regole)`** solo sulla copia locale: `text` = parole
  (senza maiuscole) tutte presenti in identificativo, titolo o categoria;
  regole = proprietà → modello con `*` e `?` (senza maiuscole), tutte vere
  (scelta minore, da confermare).
- **`survey_coverage(service)`** (C4) → (MOC, avvisi): il `Moc.fits` del
  servizio (16); se manca, il MOC della collezione dal MocServer
  (`ID=…&get=moc&fmt=fits`, verificato il 2026-10-12), avviso
  `HIPS_COVERAGE_FROM_MOCSERVER`. Solo survey celesti (il MOC IVOA è ICRS):
  planetari → `HIPS_FRAME_UNSUPPORTED` (anche in `service_coverage`).
- **`set_survey(hips_id=None, *, hips_list=None, …)`** → **`ActiveSurvey`**
  (servizio, copertura, avvisi): senza identificativo **`DEFAULT_SURVEY` =
  `CDS/P/DSS2/color`** (avviso `HIPS_DEFAULT_SURVEY`); un survey già in
  `hips_list` non si rilegge, altrimenti `add_hips` lo legge e lo aggiunge.
  Una copertura non disponibile non impedisce l'attivazione (avviso
  `HIPS_COVERAGE_UNKNOWN`).

**P4 — cubi e cataloghi progressivi (scritta il 2026-10-12):**

- **Verifiche del 2026-10-12** sui servizi reali: cubi HiPS 1.0 nel
  MocServer (es. `CDS/C/HIPASS`: `dataproduct_type = cube`,
  `hips_cube_depth = 1024`, `hips_cube_firstframe = 512`, tile
  `Npix0_5.fits` presenti); cataloghi HiPS (es. `CDS/VI/145/attitude`): tile
  TSV con righe di commento `#`, intestazione con i nomi delle colonne,
  `metadata.xml` VOTable con `COOSYS`, `hips_order_min = 1` (ordine 0
  omesso), `Allsky.tsv` con le stesse righe dei tile del suo ordine.
- **Cubi (H24):** **`cube_planes(service)`** → **`CubePlanes`** (profondità,
  piano iniziale `hips_cube_firstframe` di default 0, asse fisico,
  descrizione): asse solo se ci sono `data_cube_crpix3`, `crval3`, `cdelt3`,
  con la regola lineare FITS `CRVAL3 + (p − CRPIX3) × CDELT3`, p indice FITS
  del piano (da 1, conversione `convert_pixel_convention` del 10, DC7), unità
  da `data_cube_bunit3` (formato FITS; assente o non valida → avviso
  `HIPS_CUBE_UNIT_UNKNOWN`); chiavi incomplete → `HIPS_CUBE_AXIS_INCOMPLETE`.
  **`fetch_tile(…, plane=n)`**: tile `NpixN_n` (piano 0 = senza suffisso),
  piano fuori da [0, profondità) → `HIPS_CUBE_PLANE_INVALID` con la
  profondità; `pixel_values(…, plane=n)`.
- **Cataloghi progressivi (H12):** **`catalog_tiles(service, center,
  radius, order)`** → **`CatalogTiles`** (tabella del 13, ordine, tile letti
  con URL, righe e cache, completezza, descrizione): dall'ordine 0 fino a
  `order`, i tile TSV che toccano il cerchio (`tiles_for_fov`), dalla cache
  comune o dalla rete; **solo tile regolari, mai `Allsky`** (che li
  duplica). Dall'ordine `hips_order_min` in su un tile assente (404) chiude
  il ramo: all'ordine successivo si chiedono solo i figli dei tile presenti;
  se nessun tile c'è, ci si ferma. Colonne, tipi, unità, UCD e sistema delle
  posizioni da **`metadata.xml`** (obbligatorio, standard §4.4.3; assente o
  non leggibile → `HIPS_METADATA_INVALID`): i valori TSV si convertono con i
  convertitori VOTable di `astropy` secondo il tipo dichiarato (campo vuoto
  = nullo) e la tabella si legge con il lettore del 13 (posizioni dagli
  UCD, corpo, avvisi). Tile con colonne diverse da `metadata.xml` o righe
  con un numero di campi sbagliato: una nuova richiesta, poi
  `HIPS_BAD_TILE`. Le righe **non** sono ritagliate sul cerchio (scelta
  minore, da confermare): sono tutto il contenuto dei tile.

## 4. Cosa NON fa

- Non fa le trasformazioni di coordinate (10) né gestisce i file FITS locali (11).
- Non esegue query sui cataloghi (14), non fa cross-match (15).
- Non decide la colorimetria o le regolazioni di display: le applica la UI (41)
  su ciò che questo modulo restituisce.
- Non genera MOC: fornisce solo le informazioni di copertura richieste a `16`.
- Non analizza i metadati dei survey oltre a quelli serviti dal servizio
  HiPS (nessuna interpretazione scientifica).

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `04-cache.md` (cache comune A7),
  `10-core-coordinate-wcs.md` (calcolo del campo e delle
  coordinate dei tile), `16-core-moc.md` (formati HEALPix condivisi per H12).
- **Usato da:** `16-core-moc.md`, `19-core-dati-planetari.md`,
  `41-ui-visualizzatore-cielo.md`.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `hips_id` / URL servizio | stringa | identificativo HiPS o URL di base | survey attivo |
| in | `hips_id` / URL da aggiungere | stringa | identificativo HiPS o URL di base | C3: aggiunta a elenco |
| in | campo richiesto | float64 | gradi (centro) + FOV in gradi | dal visualizzatore |
| in | livello di dettaglio | intero | ordine HEALPix | risoluzione del tile |
| out | riquadro (tile) | immagine | pixel + WCS + header del servizio | PNG/FITS secondo il servizio |
| out | elenco survey | lista | id, nome, banda, risoluzione, copertura | |
| out | metadati servizio HiPS | struttura | titolo, banda, risoluzione max, formato tile, versione, URL descrizione, copertura | obbligatori per C3 prima di aggiungere |
| out | `body` | stringa | `celestial` o nome IAU del corpo | obbligatorio (D19-3): ricavato dal sistema di coordinate del servizio o dai metadati planetari, mai assunto |
| out | metadati riquadro | struttura | URL sorgente, data di scaricamento, dimensione | obbligatori per A7 |
| out | copertura survey | MOC / regione | gradi | delegata al modulo 16 |
| in | `plane` | intero ≥ 0 | indice del piano del cubo HiPS | solo per i cubi (H24) |
| out | elenco delle collezioni | lista | identificativi e proprietà, origine e data della sincronizzazione | H26 |

## 7. Interfaccia pubblica

- **`HiPSList`** — elenco e ricerca dei survey disponibili; espone i metadati
  di ciascuno.
- **`set_survey(hips_id)`** — attiva un survey; restituisce metadati e copertura.
- **`add_hips(hips_id_or_url)`** (C3) — aggiunge un HiPS da identificativo o
  URL: legge e valida i metadati del servizio, registra la voce in elenco con
  provenienza e la rende attivabile; in caso di errore non aggiunge nulla e
  restituisce il codice di errore di §10.
- **`fetch_tile(survey, order, tile_index)`** — scarica un riquadro; restituisce
  immagine + origine + data; in caso di errore di rete restituisce errore, non
  un tile finto.
- **`tiles_for_fov(center, fov, order)`** — calcola quali riquadri servono per
  un campo. Calcolo deterministico su griglia HEALPix.
- **Cache:** nessuna classe propria (CA4): i riquadri si salvano e si
  rileggono con `SharedCache` di `04-cache.md`.
- **`build_hips(...)`** — generazione HiPS (H9) secondo D12-1 (corretta il
  2026-10-10): standard IVOA HiPS 1.0, `reproject` dove possibile, codice
  nostro per il resto.
- **`cube_planes(survey)`** (H24) — numero e descrizione dei piani di un
  cubo HiPS; `fetch_tile` accetta l'indice del piano per i cubi.
- **`CollectionIndex`** (classe, H26) — copia locale delle proprietà delle
  collezioni: `sync()` dal MocServer, `filter(rules)` sulle proprietà;
  espone origine e data della sincronizzazione.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| Standard IVOA HiPS 1.0 | formato e URL dei riquadri, generazione (H9) | standard pubblico della comunità |
| `reproject` (D11-2, verificato con l'11) | ricampionamento delle immagini nei tile HEALPix per la generazione (H9) | già scelto dal progetto; copertura della generazione **da verificare prima del codice** |
| `astroquery.hips2fits` (D12-4) | solo complemento per i ritagli FITS prodotti dal server; i tile si scaricano con il client diretto | vedi §13 |
| `astropy-healpix` (2.0.1, BSD) | indici dei tile (`cone_search_lonlat`, `lonlat_to_healpix`); mappe e griglie HEALPix solo nel 16 | standard del dominio; `healpy` escluso (GPL, decisione del 2026-10-11) |
| `requests` (o libreria HTTP già usata dal progetto) | richieste HTTP con timeout | pratica consolidata |
| rete del 14 (`MOCSERVER_URL`) | sincronizzazione delle proprietà delle collezioni (H26), identificativi → URL (C3) | cache e registro comuni; **non `astroquery.mocserver`** (decisione del 2026-10-12) |

## 9. Regole e vincoli

- Ogni tile servito (dalla rete o dalla cache) riporta **origine e data di
  scaricamento** (A7).
- I riquadri HiPS stanno su **file su disco** della cache comune, non in
  SQLite (A7); limite unico di 5 GB per tutta la cache (CA2 di `04-cache.md`).
- Nessuna richiesta di rete senza timeout dichiarato; offline ⇒ errore o tile
  già in cache, mai pixel inventati.
- La richiesta dei tile deve seguire il campo di vista calcolato con il
  modulo 10: nessuna assunzione sulla proiezione fatta in modo indipendente.
- I dati di copertura/i MOC non vengono ricalcolati qui: si usano quelli del 16.
- Le operazioni HEALPix (ordini, indici) sono deterministiche e testate con le
  librerie HEALPix, mai riscritte.

- **Corpo di riferimento (`body`, D19-3 decisa il 2026-10-08):** ogni servizio HiPS e ogni tile porta
  nei metadati il campo **obbligatorio** `body`. Per i dati astronomici vale
  `celestial` (sfera celeste) ed è **ricavato dal sistema di coordinate
  dichiarato** (es. ICRS, galattico, eclittico), **mai assunto**; per i dati
  planetari è il corpo letto dai metadati secondo
  `19-core-dati-planetari.md`. Se `body` non si può ricavare, il dato si apre
  ma non si sovrappone né si combina con altri (`BODY_UNKNOWN`); la
  sovrapposizione tra corpi diversi segue D19-4 (`BODY_MISMATCH`, forzabile
  solo con opzione esplicita citata nel risultato).

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Survey sconosciuto | errore con elenco degli id noti | `HIPS_UNKNOWN` |
| HiPS da ID/URL non raggiungibile / timeout | nessuna voce aggiunta, errore con l'URL richiesto | `NET_TIMEOUT` |
| URL che non risponde con un servizio HiPS (metadati mancanti o non HiPS) | rifiuto con la risposta ricevuta, nessuna voce aggiunta | `HIPS_NOT_A_SERVICE` |
| Metadati del servizio incompleti o incoerenti | rifiuto che indica il campo mancante, nessuna voce aggiunta | `HIPS_METADATA_INVALID` |
| Campo fuori dalla copertura del survey | nessun tile, avviso "fuori copertura" | `HIPS_OUT_OF_COVERAGE` |
| Rete assente con cache vuota | errore di rete; la vista resta utilizzabile senza quel layer | `NET_TIMEOUT` |
| Tile corrotto o di dimensione inattesa | scartato e richiesto di nuovo; se persiste, errore | `HIPS_BAD_TILE` |
| Cache oltre il limite | rimozione dei dati meno usati, registrata | `CACHE_FULL` |
| Ordine HEALPix fuori intervallo | rifiuto con l'intervallo valido | `HEALPIX_ORDER_INVALID` |
| Corpo (`body`) non ricavabile dai metadati né dal sistema di coordinate | dato aperto da solo, non sovrapposto né combinato | `BODY_UNKNOWN` |
| Piano del cubo inesistente | rifiuto con il numero di piani disponibili | `HIPS_CUBE_PLANE_INVALID` |
| MocServer non raggiungibile | si usa la copia locale con la sua data e un avviso; senza copia locale, errore | `MOCSERVER_UNAVAILABLE` |
| Identificativo HiPS sconosciuto al MocServer | nessuna voce aggiunta | `HIPS_UNKNOWN` |
| Tile non fornito dal servizio (HTTP 404) | nessun tile | `HIPS_TILE_MISSING` |
| Copertura di un survey senza `Moc.fits` | MOC della collezione dal MocServer, dichiarato | avviso `HIPS_COVERAGE_FROM_MOCSERVER` |
| Copertura di un survey planetario | nessun MOC (MOC IVOA solo ICRS; con il 19) | `HIPS_FRAME_UNSUPPORTED` |
| Operazione per un tipo di HiPS diverso (es. tile immagine di un catalogo, piani di un'immagine) | rifiuto | `HIPS_TYPE_MISMATCH` |
| `metadata.xml` di un catalogo HiPS assente o non leggibile | nessuna tabella | `HIPS_METADATA_INVALID` |
| Formato di tile non offerto dal servizio | nessun tile | `HIPS_FORMAT_UNAVAILABLE` |
| Indice del tile fuori dall'ordine | rifiuto con l'intervallo | `HEALPIX_INDEX_INVALID` |
| `hips_frame = ecliptic` (D12-7) o planetario (19) per campi e pixel | rifiuto | `HIPS_FRAME_UNSUPPORTED` |
| Valore del pixel su un survey senza tile FITS o da un tile JPEG/PNG | nessun valore | `HIPS_PIXEL_UNAVAILABLE` |
| Posizione fuori dal tile dato | nessun valore | `HIPS_OUT_OF_TILE` |
| `Moc.fits` assente / HiPS non equatoriale con filtro di copertura | copertura non nota / filtro non applicato, dichiarati | avvisi `HIPS_COVERAGE_UNKNOWN`, `HIPS_COVERAGE_NOT_CHECKED` |
| `hips_tile_width` assente / `hips_version` diverso da `1.4` | 512 (default dello standard) / lettura secondo HiPS 1.0, dichiarati | avvisi `HIPS_DEFAULT_TILE_WIDTH`, `HIPS_VERSION_UNKNOWN` |
| Corpo da `hips_body` (WD HiPS 2.0) | corpo usato, dichiarato come bozza IVOA | avviso `HIPS_BODY_DRAFT` |
| `creator_did` diverso dall'identificativo richiesto | vale quello del servizio | avviso `HIPS_ID_MISMATCH` |

## 11. Esposizione all'IA

- **`list_surveys`** — output: elenco survey con metadati (nessun calcolo).
- **`add_hips`** (C3) — input: identificativo o URL; output: metadati letti e
  stato dell'aggiunta. Nessun calcolo numerico: solo lettura/validazione
  metadati.
- **`get_coverage(survey)`** — output: copertura del survey come MOC;
  **calcolo: modulo 16** (`mocpy`).
- **`get_tile_provenance(survey, order, tile)`** — output: origine e data del
  riquadro; nessun calcolo.

Nessun altro strumento: l'IA non scarica né interpreta pixel.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Elenco survey | leggere l'elenco dei survey | contiene almeno i survey predefiniti dichiarati, con metadati completi | confronto con la risposta del servizio (test di rete separato) |
| T2 | Calcolo dei tile per un campo | chiedere i tile per centro (0°,0°) e FOV 1° a un ordine fissato | gli indici coincidono con quelli ricalcolati nel test con la libreria HEALPix | ricalcolo con `healpy`/`astropy-healpix` |
| T3 | Cache con provenienza | richiedere due volte lo stesso riquadro | seconda lettura da cache, con origine e data valorizzate e invariate | lettura metadati cache |
| T4 | Limite di cache | impostare un limite piccolo e richiedere riquadri diversi | i dati meno usati vengono rimossi, il totale resta sotto il limite | controllo dimensione directory cache |
| T5 | Campo fuori copertura | chiedere un campo sopra un polo per un survey non polare | `HIPS_OUT_OF_COVERAGE`, nessun tile fasullo | test con servizio simulato |
| T6 | Errore di rete | simulare rete assente con cache vuota | `NET_TIMEOUT` entro il timeout, nessun pixel inventato | test di unità con server simulato |
| T7 | Aggiunta HiPS da URL (C3) | aggiungere un servizio HiPS simulato tramite URL di base | metadati letti e validati, voce presente in elenco e attivabile, tile scaricabili | confronto con i metadati del servizio simulato |
| T8 | Aggiunta HiPS da URL non valido (C3) | passare un URL che non è un servizio HiPS | `HIPS_NOT_A_SERVICE`, nessuna voce aggiunta | test di unità con server simulato |
| T9 | Cubo HiPS (H24) | servizio HiPS simulato a cubo con 3 piani; richiedere il tile del piano 2 | tile del piano 2; richiesta del piano 5 → `HIPS_CUBE_PLANE_INVALID` | servizio simulato |
| T10 | Sincronizzazione delle collezioni (H26) | `CollectionIndex.sync()` contro un MocServer simulato, poi `filter` per testo | elenco filtrato corretto; origine e data della sincronizzazione presenti | servizio simulato (test di rete separato per il servizio reale) |
| T11 | MocServer assente (H26) | sincronizzazione con rete assente e copia locale presente | copia locale usata, avviso `MOCSERVER_UNAVAILABLE` con la data della copia | test di unità |
| T13 | Catalogo HiPS progressivo (H12) | servizio simulato con `metadata.xml` (COOSYS ICRS) e tile TSV agli ordini 0 e 1 attorno a (45°, 20°); lettura fino all'ordine 3; seconda lettura; tile con colonne sbagliate; immagine; catalogo senza `metadata.xml` | righe = tutte quelle dei tile che toccano il cerchio (ricalcolati con `astropy-healpix`); posizioni ICRS, unità e nulli dal VOTable; all'ordine 2 solo figli dei tile presenti, ordine 3 non chiesto; seconda lettura dalla cache; `HIPS_BAD_TILE` dopo una nuova richiesta; `HIPS_TYPE_MISMATCH`; `HIPS_METADATA_INVALID` | servizio simulato |
| T12 | Valore del pixel su HiPS (H27) | leggere il valore sotto il cursore su un tile FITS in cache | valore uguale a quello del tile FITS letto con `astropy.io.fits` | confronto diretto |

## 13. Decisioni aperte

- **D12-1 — Generazione HiPS (H9): DECISA il 2026-10-09, CORRETTA il
  2026-10-10 (decisione del proprietario, regola d'oro n. 8).** La generazione
  segue lo **standard pubblico IVOA HiPS 1.0**, con **`reproject`** dove
  possibile (quali passi copre: **da verificare prima del codice**) e
  **codice nostro** per il resto; **nessun programma di Aladin** (Hipsgen
  tolto), nessuno strumento esterno, nessun ambiente Java dentro il `.dmg`.
- **D12-2 — Caricamento HiPS da ID/URL (C3): DECISA il 2026-10-04 — inclusa
  per decisione del proprietario** (parità con Aladin = minimo). La funzione è
  descritta in §3/§7 con errori in §10; restano solo verifiche tecniche su
  lettura metadati e codici di errore, non sull'esistenza in Aladin.
- **D12-3 — Survey predefiniti (C2): DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** **elenco dinamico dal
  MocServer** (riga H26 di `03-parita-aladin.md`), con **default DSS2 a
  colori**. **Motivazione (nostra, 2026-10-10):** copre il **cielo intero**
  con dati **pubblici**, quindi ogni campo richiesto ha un'immagine di
  sfondo; identificativo esatto **da verificare prima del codice**.
- **D12-4 — Cliente HiPS: DECISA il 2026-10-09 (decisione del proprietario
  sulla checklist del livello 1).** **client HTTP diretto** secondo lo
  standard IVOA HiPS 1.0 (tile, proprietà, ordini); `astroquery.hips2fits`
  solo come complemento per i ritagli FITS prodotti dal server.
- **D12-6 — Nomi dei corpi planetari: DA DECIDERE (aperta il 2026-10-12,
  Gruppo 3).** I HiPS planetari scrivono il corpo in minuscolo (`mars`,
  WD HiPS 2.0); il 19 userà nomi IAU (es. `Mars`). Opzioni: (a) il 12
  conserva il nome del servizio e il confronto dei corpi è sensibile alle
  maiuscole (oggi); (b) il 19 fornisce una tabella di corrispondenza e il 12
  normalizza. **Raccomandazione:** (b) quando si scrive il 19; fino ad allora
  (a). Non blocca il codice del 12.
- **D12-7 — `hips_frame = ecliptic`: DA DECIDERE (aperta il 2026-10-12,
  Gruppo 3).** Lo standard HiPS 1.0 dice solo "ecliptic", senza indicare
  quale eclittica (es. media J2000 baricentrica, geocentrica, vera della
  data). Opzioni: (a) nessun calcolo di campo o di pixel per i HiPS
  eclittici (`HIPS_FRAME_UNSUPPORTED`, oggi); (b) un frame di `astropy`
  scelto dal proprietario, dichiarato nel risultato. **Raccomandazione:**
  (a) finché non si trova un HiPS eclittico reale da cui verificarlo.
  Fermo solo questo pezzo.
- **D12-5 — Cataloghi HiPS progressivi (H12): DECISA il 2026-10-04.**
  **Dati e computazioni HEALPix nel `16`, servizio dei tile nel `12`** (stesso
  confine scritto in `16-core-moc.md`, D16-5). **Motivazione:** un solo
  confine dichiarato, nessuna logica HEALPix duplicata, coerente con §3/§9 di
  questo file. Applicata in §3 qui sopra.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). |
| 2026-10-04 | agente di sviluppo | **C3 inclusa per decisione del proprietario:** aggiunta la funzione "aggiunta di un HiPS da identificativo o URL" (§3), `add_hips` (§7), righe input/output (§6), errori `NET_TIMEOUT`/`HIPS_NOT_A_SERVICE`/`HIPS_METADATA_INVALID` (§10), strumento IA (§11), test T7–T8 (§12); D12-2 chiusa come decisa (§13). Riga C3 in `03-parita-aladin.md` passata a `inclusa (decisione del proprietario)`. |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario: D12-5 passata da aperta a decisa** — dati/computazioni HEALPix nel 16, servizio dei tile nel 12 (§3; pari a D16-5 in `16-core-moc.md`); **cache su disco con limite di default 5 GB** (D11-3 di `11-core-immagini-fits.md`, §3/§9). Decisioni riportate in `decisioni-aperte.md`. |
| 2026-10-08 | Claude Code | §5: aggiunti a "Usato da" i moduli `19-core-dati-planetari.md` (scritti il 2026-10-08, stato bozza). Nessun altro testo cambia. |
| 2026-10-09 | Claude Code | **D19-3 applicata (decisione del proprietario del 2026-10-08):** campo `body` obbligatorio nei metadati di ogni servizio HiPS e di ogni tile (§6, §9, §10); per i dati astronomici `celestial`, ricavato dal sistema di coordinate, mai assunto; errori `BODY_UNKNOWN` e, per le sovrapposizioni, `BODY_MISMATCH` secondo D19-4 (forzabile solo con opzione esplicita citata nel risultato). |
| 2026-10-09 | Claude Code | **D12-1, D12-3, D12-4 DECISE** (checklist del livello 1): generazione HiPS con libreria Python se `reproject` la offre (da verificare), altrimenti Hipsgen esterno; survey dal MocServer con default DSS2 a colori; client HTTP diretto HiPS 1.0 (hips2fits come complemento). §7 aggiornato. |
| 2026-10-09 | Claude Code | **Completamento con gli esiti di AP5** (decisione del proprietario del 2026-10-09): §3, §6, §7, §8, §10, §12 per H24 (cubi HiPS), H26 (collezioni dal MocServer con copia locale; filtro spaziale nel 16; client `astroquery.mocserver`, interfaccia da verificare) e H27 (solo tile del campo; valore del pixel dal tile FITS). §8: riga `hips2fits` allineata a D12-4. Nessuna nuova decisione dei Gruppi 1 e 2. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** (regola del proprietario del 2026-10-09): modulo completato con gli esiti di AP5, nessuna decisione aperta nei Gruppi 1 e 2. |
| 2026-10-09 | Claude Code | **Collegamento alla cache comune `04-cache.md`** (approvato il 2026-10-09; decisione CA4 del proprietario, autorizzazione esplicita a modificare il file approvato): §3, §5, §7, §9 — tolta `HiPSCache`, riquadri nella cache comune `SharedCache`; tolto da "Usato da" l'`11` per la cache. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Regola d'oro n. 8** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): D12-1 corretta — generazione HiPS secondo lo standard IVOA HiPS 1.0, `reproject` dove possibile, codice nostro per il resto, Hipsgen tolto (§3, §7, §8, §13); D12-3 — DSS2 a colori resta, con motivazione nostra (cielo intero, dati pubblici); §3 C2 senza elenco preso da Aladin (elenco dinamico dal MocServer); §8 "Specifica HiPS (CDS)" → standard IVOA HiPS 1.0. Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **Decisioni del proprietario del 2026-10-12** (autorizzazione esplicita a modificare il file approvato): divisione in 5 parti; MocServer con la rete del 14 (non `astroquery.mocserver`, §3, §8); `healpy` tolto e `healpix_map`/`healpix_grid` tolte dal §7 (solo delega al 16, §8, §11); H10 SkyView rinviato (URL SIA non documentato sul sito NASA); `tiles_for_fov` a cerchio; tile corrotto = una nuova richiesta poi `HIPS_BAD_TILE`; `build_hips` con ordine obbligatorio, tile 512 di default, FITS sempre, PNG/JPEG con parametri di visualizzazione espliciti; **A10 per gli HiPS decisa** (512 MB in memoria, un tile alla volta in `build_hips`, limite delle operazioni 4 GB). Verifiche del 2026-10-12: standard HiPS 1.0 (`properties`, URL, cubi, cataloghi), corpo dei HiPS planetari (`hips_body` del WD 2.0, regola da confermare), DSS2 a colori = `CDS/P/DSS2/color`, `cone_search_lonlat`, disposizione dei pixel nel tile (due verifiche indipendenti), funzioni HiPS di `reproject` 0.21. Nuova decisione aperta **D12-6** (nomi dei corpi, Gruppo 3). Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **P1 scritta** (`src/astrotwo/core/hips.py`: `parse_properties`, `read_service`, `HiPSService`, `add_hips`, `HiPSList`, `HiPSError`; T7, T8, chiavi obbligatorie, corpo, risoluzione dell'identificativo con il MocServer, errori di rete): proprietà validate secondo HiPS 1.0, solo le risposte valide in cache; nuovi avvisi in §10. Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **P2 scritta** (`tile_path`, `tiles_for_fov`/`TileSelection`, `order_for_resolution`, `fetch_tile`/`HiPSTile`, `service_coverage`, `TileMemory`, `pixel_values`/`tile_pixel_values`/`PixelValues`; T2–T6, T12, tile corrotti, JPEG/PNG, memoria): cache comune per i tile, una nuova richiesta per un tile corrotto, 404 = `HIPS_TILE_MISSING` (scelta minore), filtro di copertura solo equatoriale (scelta minore); nuova decisione aperta **D12-7** (`hips_frame = ecliptic`, Gruppo 3). Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **P3 scritta** (`CollectionIndex` con `sync`/`filter`, `INDEX_FIELDS`, `survey_coverage`, `set_survey`/`ActiveSurvey`, `DEFAULT_SURVEY`; T1, T10, T11): copia locale delle collezioni HiPS dal MocServer, risposte in ISO-8859-1 come dichiarato dal servizio (verifica del 2026-10-12), copertura dal `Moc.fits` del servizio o dal MocServer; campi dell'indice e regole del filtro come scelte minori. Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **P4 scritta** (`cube_planes`/`CubePlanes`, piani in `fetch_tile` e `pixel_values`, `catalog_tiles`/`CatalogTiles`; T9, nuovo T13): cubi HiPS 1.0 con suffisso `_n` e asse fisico dalle chiavi `data_cube_*` (indice FITS dal 10); cataloghi progressivi dai tile TSV regolari con `metadata.xml`, rami chiusi dai tile assenti, righe non ritagliate (scelta minore). Stato `approvato` invariato. |
