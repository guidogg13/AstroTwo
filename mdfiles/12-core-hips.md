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
  terze parti (es. SkyView: **rinviato**, vedi sotto, punto 3); la parte protocollo/VO di H10 è in
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
   documentato da NASA. **Rinvio confermato dal proprietario il
   2026-10-12. Motivo:** un URL non documentato dal gestore può cambiare o
   sparire senza avviso, e i risultati costruiti su di esso non sarebbero
   verificabili né riproducibili; si attende che NASA documenti l'URL SIA.
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
| P6 | **riproiezione dei tile sulla vista del `41`** (aggiunta il 2026-10-15 su decisione del proprietario): `view_sampling`, `fill_view` | T17, T18 |

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
  minore, confermata il 2026-10-12):** `hips_frame` in `equatorial`, `galactic`,
  `ecliptic` → `body = "celestial"` (D19-3, ricavato dal sistema); altrimenti
  `body = hips_body` se presente **e uguale** a `hips_frame`, con l'avviso
  `HIPS_BODY_DRAFT` ("`hips_body` è del Working Draft HiPS 2.0, non ancora
  raccomandazione IVOA"); senza `hips_body`, o con valori diversi →
  `body = None` e `BODY_UNKNOWN` (il dato si apre da solo, mai sovrapposto).
  **Nome del corpo (D12-6, tabella del 19 approvata il 2026-10-13):**
  `hips_body` si normalizza con `normalize_body_name` del 19
  (`spiceypy.bodn2c` → identificativo NAIF → nome canonico IAU in inglese
  con l'iniziale maiuscola, es. `mars` → `Mars`), con l'avviso
  `BODY_NORMALIZED`; valore fuori dalla tabella dei corpi o senza codice
  NAIF (es. `mars-stimson`) → `body = None` con l'avviso
  `BODY_UNSUPPORTED` (il dato si apre da solo). La normalizzazione
  funziona anche con l'opzione dei dati planetari spenta (è lettura di
  metadati).
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
  testo dello standard 1.0): **approvata dal proprietario il 2026-10-12,
  verificata su dati reali (2MASS K, confronto con `reproject`); da
  ricontrollare in AP1** (validazione finale della parità). Verificata il
  2026-10-12 in due modi indipendenti. Per un punto, la cella all'ordine K+S (S = log₂ larghezza)
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
  confermata il 2026-10-12). `hips_frame = ecliptic` → `HIPS_FRAME_UNSUPPORTED`: lo
  standard non dice quale eclittica (**D12-7 decisa: non supportato finché
  non è verificato su un HiPS eclittico reale**); frame
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
  (scelta minore, confermata il 2026-10-12).
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
  duplica). Si parte da `hips_order_min` (gli ordini sotto sono omessi e
  **non si chiedono**: il servizio reale `CDS/VI/145/attitude` risponde HTTP
  400, non 404, per l'ordine 0 omesso — test di rete del 2026-10-12); un
  tile assente (404) chiude il ramo: all'ordine successivo si chiedono solo
  i figli dei tile presenti; se nessun tile c'è, ci si ferma. Colonne, tipi, unità, UCD e sistema delle
  posizioni da **`metadata.xml`** (obbligatorio, standard §4.4.3; assente o
  non leggibile → `HIPS_METADATA_INVALID`): i valori TSV si convertono con i
  convertitori VOTable di `astropy` secondo il tipo dichiarato (campo vuoto
  = nullo) e la tabella si legge con il lettore del 13 (posizioni dagli
  UCD, corpo, avvisi; il sistema delle posizioni segue le regole del 13: nel
  servizio reale `CDS/VI/145/attitude` il `COOSYS` sta in `DEFINITIONS` e i
  `FIELD` non lo richiamano con `ref`, quindi `FRAME_UNKNOWN` e conferma con
  `confirm_position_columns` del 13 — test di rete del 2026-10-12). Tile con
  colonne diverse da `metadata.xml` o righe
  con un numero di campi sbagliato: una nuova richiesta, poi
  `HIPS_BAD_TILE`. Le righe **non** sono ritagliate sul cerchio (scelta
  minore, confermata il 2026-10-12): sono tutto il contenuto dei tile.

**P5 — `build_hips` (scritta il 2026-10-12):**

- **Uso di `reproject` (approvato dal proprietario il 2026-10-12 così
  com'è):**
  `reproject_to_hips` non basta per H9 (una sola immagine, tile FITS in
  `float32` contro DC6, nessuna combinazione di tile FITS sovrapposti in
  `coadd_hips`) e la geometria dei tile di `reproject` è in funzioni interne.
  Quindi: per ogni tile un **WCS APE 14** nostro (`_tile_wcs`) in cui ogni
  pixel è il centro della sua cella HEALPix all'ordine K+S
  (`astropy-healpix`, disposizione verificata in §3), e il ricampionamento
  con **`reproject_interp`** (API pubblica) su quella griglia. **Verifica del
  2026-10-12:** per un tile di prova i valori coincidono entro 2 × 10⁻¹³ con
  quelli ottenuti con il WCS HPX interno di `reproject` e in modo esatto con
  un'interpolazione bilineare indipendente (`scipy`). `reproject_exact`
  (metodo `flux`) richiede i contorni dei pixel di uscita, non definiti per
  questa griglia: **il metodo `flux` non è disponibile in `build_hips`**
  (`OPERATION_UNSUPPORTED`); restano `nearest` e `bilinear`.
- **`build_hips(images, output, *, order, hips_id, title, method,
  tile_width=512, formats=(), display=None, status="public master
  clonableOnce")`** → **`BuildResult`** (cartella, ordine, tile per ordine,
  formati, MOC, proprietà, descrizione, avvisi). Immagini dell'11 con WCS
  (colori → `OPERATION_UNSUPPORTED`, due livelli →
  `PREVIEW_NOT_MEASURABLE`, senza WCS → `WCS_MISSING`). **`order`
  obbligatorio** (con `order + log₂ tile_width ≤ 29`), **`tile_width` 512 di
  default**, potenza di 2; `method` obbligatorio, `nearest` o `bilinear`;
  `hips_id` nella forma `AUTORITÀ/P/nome` (diventa `creator_did =
  ivo://…`), `title` obbligatorio (`obs_title`). La cartella deve essere
  **nuova o vuota** (nulla si sovrascrive). Solo frame `equatorial` (scelta
  minore, confermata il 2026-10-12).
- **Tile più profondi:** i tile che toccano l'unione dei MOC delle immagini
  (16, `moc_from_image` all'ordine `order`), **uno alla volta**: per ogni
  immagine `reproject_interp` sul WCS del tile; più immagini → **media
  pesata con la copertura** (`hips_overlay = mean`); tile senza pixel validi
  non scritti. **Tile FITS sempre**, in **`float64`** (valori ricampionati,
  DC6; `hips_pixel_bitpix = -64`), `BUNIT` se tutte le immagini hanno la
  stessa unità (altrimenti avviso `HIPS_UNIT_MIXED`).
- **Ordini inferiori** fino a 0: ogni pixel = **`nanmean` dei 4 pixel**
  dell'ordine sotto (`astropy.nddata.block_reduce`), figlio q nel quadrante
  dato dalla disposizione verificata (`hips_hierarchy = mean`); i tile padre
  si leggono dal disco un figlio alla volta.
- **PNG/JPEG** facoltativi (`formats`), solo con **`display = (vmin, vmax,
  funzione di trasferimento)` espliciti** (`HIPS_DISPLAY_REQUIRED`),
  calcolati da ogni tile FITS con `set_display` dell'11 (palette grigia,
  righe scritte dall'alto come vuole lo standard; PNG con trasparenza dove
  il valore non è finito); `histeq` rifiutata perché dipende dal tile
  (`HIPS_DISPLAY_INVALID`, anche per `vmin ≥ vmax`); `hips_pixel_cut = vmin
  vmax`.
- **Memoria (A10, D11-11):** stima = copie `float64` delle immagini + lavoro
  di un tile; oltre il limite delle operazioni dell'immagine (4 GB di
  default) → `MEMORY_LIMIT_EXCEEDED` prima di scrivere.
- **`Moc.fits`** = unione dei MOC delle immagini all'ordine `order`, scritto
  con `write_moc` del 16 (FITS IVOA 2.0); **`properties`** scritto **per
  ultimo** (un'interruzione non lascia un HiPS valido a metà): le 9 chiavi
  obbligatorie (`hips_version = 1.4`) più `hips_tile_width`,
  `hips_pixel_bitpix`, `hips_builder = AstroTwo <versione>`, date di
  creazione e rilascio, `hips_sampling`, `hips_overlay`, `hips_hierarchy`,
  `moc_sky_fraction`, `hips_order_min = 0`. **`Allsky` non scritto** (avviso
  `HIPS_ALLSKY_NOT_WRITTEN`, **D12-8 decisa: per ora nessun Allsky**). Il HiPS generato si rilegge con
  `read_service`, `fetch_tile`, `pixel_values` (T14).

**P6 — riproiezione dei tile sulla vista (specifica del 2026-10-15, codice
scritto il 2026-10-16, commit `c8cf5ec`).** Decisione del proprietario del 2026-10-15: il visualizzatore
(`41`) non riproietta da sé; i tile si portano sulla finestra della vista
qui, sulla geometria data da `make_view_wcs` del 10 (`ViewGeometry`).

- **Metodo: campionamento al più vicino sulla griglia HEALPix.** Per ogni
  pixel della finestra (centro, convenzione numpy) si prende il valore del
  **pixel HiPS che contiene quel punto del cielo** all'ordine scelto:
  cielo con `window_to_sky` di `ViewGeometry` (10), cella all'ordine K + S
  con `lonlat_to_healpix` di `astropy-healpix` nel frame del HiPS
  (conversione del frame con il 10), tile e colonna/riga nel tile con la
  **disposizione dei pixel verificata** (§3) — la stessa regola di
  `pixel_values`. Così non ci sono fasce vuote tra tile adiacenti (ogni
  pixel della finestra appartiene a un solo tile) e nessun valore è
  inventato. Il metodo usato (`nearest`) è dichiarato nel risultato;
  l'interpolazione bilineare tra tile non è prevista nella prima versione.
- **`view_sampling(service, view, *, order=None, plane=None,
  coverage=None)`** → **`ViewSampling`**: ordine (di default
  `order_for_resolution` alla scala della finestra, con
  `HIPS_RESOLUTION_LIMIT` se serve), elenco dei **tile necessari** (solo
  quelli che contengono almeno un pixel della finestra; con `coverage` solo
  quelli dentro il MOC del servizio) e, per ogni pixel della finestra,
  indice del tile e colonna/riga nel tile, oppure "nessun dato" per i pixel
  fuori dalla proiezione o fuori copertura; frame del HiPS, metodo,
  descrizione. Frame non supportati: come `tiles_for_fov`
  (`HIPS_FRAME_UNSUPPORTED`).
- **`fill_view(sampling, tile)`** → **`ViewTile`**: i valori del tile
  (`HiPSTile` di `fetch_tile`) per i soli pixel della finestra che cadono in
  quel tile, con il riquadro della finestra che li contiene e la maschera;
  tile FITS nel **tipo nativo** (DC6), tile JPEG/PNG come colori RGB(A) a 8
  bit nell'orientamento già capovolto da `fetch_tile`; provenienza del tile
  (URL, data, dalla cache sì/no). Il `41` chiama `fill_view` per ogni tile
  appena arriva (riempimento progressivo).
- **Verificato il 2026-10-16:** le funzioni HiPS pubbliche di `reproject`
  0.21 (`hips_as_dask_array`, `reproject_from_hips`) scaricano i tile da sé
  con `astropy.utils.data.download_file`, quindi **non** con la rete del 14
  e la cache del 04: si usa il metodo descritto qui. **Tempo misurato** di
  `view_sampling` per una finestra di 2560 × 1600 pixel fisici (Mac M1 di
  sviluppo, non ancora il Mac di riferimento): 1.27 s (`TAN`, 1″ per
  pixel, ordine 9, 38 tile), 0.82 s (`TAN`, 30″, ordine 4), 0.57 s
  (`AIT`, 0.15°, ordine 0); obiettivo P6 del `41` (primi tile in ≤ 2 s con
  la cache calda) da misurare con il `41`, margine ridotto: misurare e
  riportare.

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
  `41-ui-visualizzatore-cielo.md` (survey, tile, P6), `05-comandi-sessione.md`
  (comandi dei survey e letture sotto il cursore).

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
- **`build_hips(images, output, *, order, hips_id, title, method,
  tile_width=512, formats=(), display=None, status=…)`** — generazione HiPS
  (H9) secondo D12-1 (corretta il 2026-10-10): standard IVOA HiPS 1.0,
  `reproject` dove possibile, codice nostro per il resto (dettagli in §3,
  P5).
- **`cube_planes(survey)`** (H24) — numero e descrizione dei piani di un
  cubo HiPS; `fetch_tile` accetta l'indice del piano per i cubi.
- **`CollectionIndex`** (classe, H26) — copia locale delle proprietà delle
  collezioni: `sync()` dal MocServer, `filter(rules)` sulle proprietà;
  espone origine e data della sincronizzazione.
- **`view_sampling(service, view, …)`** e **`fill_view(sampling, tile)`**
  (P6, aggiunte il 2026-10-15) — tile necessari per la finestra della
  vista e riempimento dei suoi pixel con i valori del HiPS (campionamento
  al più vicino sulla griglia HEALPix); dettagli in §3, P6.

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
| `hips_body` fuori dalla tabella dei corpi del 19 (D12-6) | `body = None`, dato aperto da solo | avviso `BODY_UNSUPPORTED` |
| Piano del cubo inesistente | rifiuto con il numero di piani disponibili | `HIPS_CUBE_PLANE_INVALID` |
| MocServer non raggiungibile | si usa la copia locale con la sua data e un avviso; senza copia locale, errore | `MOCSERVER_UNAVAILABLE` |
| Identificativo HiPS sconosciuto al MocServer | nessuna voce aggiunta | `HIPS_UNKNOWN` |
| Tile non fornito dal servizio (HTTP 404) | nessun tile | `HIPS_TILE_MISSING` |
| Copertura di un survey senza `Moc.fits` | MOC della collezione dal MocServer, dichiarato | avviso `HIPS_COVERAGE_FROM_MOCSERVER` |
| Copertura di un survey planetario | nessun MOC (MOC IVOA solo ICRS; con il 19) | `HIPS_FRAME_UNSUPPORTED` |
| Operazione per un tipo di HiPS diverso (es. tile immagine di un catalogo, piani di un'immagine) | rifiuto | `HIPS_TYPE_MISMATCH` |
| `metadata.xml` di un catalogo HiPS assente o non leggibile | nessuna tabella | `HIPS_METADATA_INVALID` |
| `build_hips` con tile PNG/JPEG senza parametri di visualizzazione / con `histeq` o `vmin ≥ vmax` | nessun HiPS | `HIPS_DISPLAY_REQUIRED` / `HIPS_DISPLAY_INVALID` |
| `build_hips` con memoria stimata oltre il limite delle operazioni | nessun HiPS | `MEMORY_LIMIT_EXCEEDED` |
| `build_hips` senza pixel validi ricampionati | nessun HiPS | `HIPS_EMPTY` |
| `build_hips` metodo `flux` | nessun HiPS | `OPERATION_UNSUPPORTED` |
| Formato di tile non offerto dal servizio | nessun tile | `HIPS_FORMAT_UNAVAILABLE` |
| Indice del tile fuori dall'ordine | rifiuto con l'intervallo | `HEALPIX_INDEX_INVALID` |
| `hips_frame = ecliptic` (D12-7) o planetario (19) per campi e pixel | rifiuto | `HIPS_FRAME_UNSUPPORTED` |
| Valore del pixel su un survey senza tile FITS o da un tile JPEG/PNG | nessun valore | `HIPS_PIXEL_UNAVAILABLE` |
| Posizione fuori dal tile dato | nessun valore | `HIPS_OUT_OF_TILE` |
| `Moc.fits` assente / HiPS non equatoriale con filtro di copertura | copertura non nota / filtro non applicato, dichiarati | avvisi `HIPS_COVERAGE_UNKNOWN`, `HIPS_COVERAGE_NOT_CHECKED` |
| `hips_tile_width` assente / `hips_version` diverso da `1.4` | 512 (default dello standard) / lettura secondo HiPS 1.0, dichiarati | avvisi `HIPS_DEFAULT_TILE_WIDTH`, `HIPS_VERSION_UNKNOWN` |
| Corpo da `hips_body` (WD HiPS 2.0) | corpo usato, dichiarato come bozza IVOA | avviso `HIPS_BODY_DRAFT` |
| `creator_did` diverso dall'identificativo richiesto | vale quello del servizio | avviso `HIPS_ID_MISMATCH` |

### Parametri dei messaggi (D40-3)

Dal 2026-10-24 (sprint 8c) ogni errore e ogni avviso del modulo nasce come **codice + `params`**
(`HiPSError(code, message, params=..., **details)`; gli avvisi sono `ModuleWarning(code, text, params)`, la coppia
(codice, testo) del 10 con in più `params`, che si confronta e si spacchetta come prima): `params` è un
dizionario nome → valore JSON con tutti i valori che finiscono nel testo, mai
arrotondati; le quantità sono `{"value": numero, "unit": testo}`. Il **testo italiano del modulo resta
invariato** (campo `text`/`message`); il modulo **non** contiene traduzioni e non importa il catalogo
(`src/astrotwo/messages_catalog.py`, `40` §3.7.1). Il parametro riservato `reason` sceglie la sotto-voce
(D40-6); "esterno" = testo di terzi (libreria, file, servizio), inserito tale e quale e senza tradurlo (stessa
regola del 10 e dell'11: `detail`, `cause`); un messaggio di AstroTwo incorporato in un altro è di tipo `message`
(D40-7, sotto). I `details` di prima
(`url`, `hips_id`, `order`, `index`, `outside`, `depth`, `field`, `status`, `format`, `line`) restano.

**Errori rilanciati da un altro modulo (14, 16).** Quando il 12 rilancia l'errore di un modulo sotto di lui
(`_net`: `NET_TIMEOUT`, `SERVICE_ERROR`, …; `HiPSError(exc.code, exc.message)` per il 16) **codice, testo e `params` restano
quelli dell'altro modulo**: il 12 non li riscrive né li inserisce nel catalogo. Il 14 e il 16 sono
convertiti (sprint 8d): i loro errori arrivano con i loro `params`. Gli **avvisi dei moduli sotto** (`response.notes` del 14, `moc.warnings` del 16,
`table.warnings` del 13, gli avvisi dei tile in `pixel_values`) passano **tali e quali**, con il loro `params`.
**Messaggi annidati (D40-7, decisa il 2026-10-24).** Dove il testo del 12 incorpora un altro messaggio **di AstroTwo**
il parametro ha tipo `message` (`{"code", "params", "text"}`, `40` §3.7.1) e il catalogo lo rende in modo
ricorsivo: `REGION_INVALID` con l'errore del 10 (`detail`), `HIPS_NOT_A_SERVICE` (`service_error`), `HIPS_METADATA_INVALID`
(`metadata_xml_unavailable`) e `MOCSERVER_UNAVAILABLE` (`resolve`, `index`, `coverage`) con l'errore del 14 o del 16 (`cause`),
`HIPS_COVERAGE_UNKNOWN` con l'errore del 12 che ha
impedito la copertura (`cause`, con `cause_code` che ne ripete il codice), `HIPS_BAD_TILE` e `HIPS_TILE_DISCARDED` con
la diagnosi del tile (`problem`). La diagnosi ha un codice proprio, **`HIPS_TILE_PROBLEM`**, usato solo come messaggio
annidato (sotto-voci `no_data`, `fits_unreadable`, `size_mismatch`, `format_mismatch`, `image_unreadable`, `not_utf8`,
`no_header`, `columns_mismatch`, `bad_row`; il testo italiano è quello di prima). Restano parametri **esterni**, non
tradotti, il testo di terzi: le eccezioni di astropy e di PIL dentro la diagnosi (`detail`), i nomi delle colonne del
servizio (`header`, `expected`) e le risposte dei moduli 14, 16 e 19 non ancora convertiti (`MOCSERVER_UNAVAILABLE`
`detail`, `HIPS_NOT_A_SERVICE` `service_error`, `HIPS_METADATA_INVALID` `metadata_xml_unavailable`,
`BODY_UNSUPPORTED` `detail`): quando quei moduli saranno convertiti (sprint 8d) diventeranno `message`.

| Codice | `reason` | Parametri (`params`) |
|---|---|---|
| `HIPS_NOT_A_SERVICE` | (generale) | — |
| `HIPS_NOT_A_SERVICE` | `bad_line` | `source` (string), `line` (integer), `content` (string, esterno) |
| `HIPS_NOT_A_SERVICE` | `no_properties` | `source` (string) |
| `HIPS_NOT_A_SERVICE` | `service_error` | `url` (string), `cause` (message: errore del 14) |
| `HIPS_NOT_A_SERVICE` | `not_utf8` | `url` (string), `detail` (string, esterno) |
| `HIPS_NOT_A_SERVICE` | `no_mandatory_keys` | `url` (string) |
| `HIPS_NOT_A_SERVICE` | `no_service_url` | `hips_id` (string) |
| `HIPS_METADATA_INVALID` | (generale) | — |
| `HIPS_METADATA_INVALID` | `missing` | `source` (string), `field` (string) |
| `HIPS_METADATA_INVALID` | `not_integer` | `source` (string), `field` (string), `value` (string, esterno) |
| `HIPS_METADATA_INVALID` | `out_of_range` | `source` (string), `field` (string), `value` (integer), `low` (integer), `high` (integer) |
| `HIPS_METADATA_INVALID` | `below_minimum` | `source` (string), `field` (string), `value` (integer), `low` (integer) |
| `HIPS_METADATA_INVALID` | `not_number` | `source` (string), `field` (string), `value` (string, esterno) |
| `HIPS_METADATA_INVALID` | `release_date` | `source` (string), `value` (string, esterno) |
| `HIPS_METADATA_INVALID` | `product_unknown` | `source` (string), `value` (string, esterno), `allowed` (list) |
| `HIPS_METADATA_INVALID` | `tile_format` | `source` (string), `formats` (string, esterno), `product` (string), `allowed` (list) |
| `HIPS_METADATA_INVALID` | `tile_width_not_power_of_two` | `source` (string), `width` (integer) |
| `HIPS_METADATA_INVALID` | `cube_depth_missing` | `source` (string) |
| `HIPS_METADATA_INVALID` | `cube_first_frame` | `source` (string), `first` (integer), `depth` (integer) |
| `HIPS_METADATA_INVALID` | `metadata_xml_unavailable` | `url` (string), `cause` (message: errore del 14) |
| `HIPS_METADATA_INVALID` | `metadata_xml_unreadable` | `url` (string), `detail` (string, esterno) |
| `HIPS_UNKNOWN` | (generale) | `hips_id` (string) |
| `HIPS_UNKNOWN` | `mocserver` | `hips_id` (string) |
| `HIPS_UNKNOWN` | `not_listed` | `hips_id` (string), `known` (list) |
| `HIPS_UNKNOWN` | `not_listed_empty` | `hips_id` (string) |
| `HEALPIX_ORDER_INVALID` | (generale) | `value` (string), `high` (integer) |
| `HEALPIX_ORDER_INVALID` | `service_maximum` | `value` (string), `high` (integer) |
| `HEALPIX_ORDER_INVALID` | `tile_width` | `value` (string), `high` (integer), `tile_width` (integer) |
| `HEALPIX_ORDER_INVALID` | `plus_tile_bits` | `order` (integer), `width` (integer), `maximum` (integer) |
| `HEALPIX_INDEX_INVALID` | (generale) | `index` (string), `order` (integer), `maximum` (integer) |
| `HIPS_FRAME_UNSUPPORTED` | (generale) | `frame` (string) |
| `HIPS_FRAME_UNSUPPORTED` | `ecliptic` | `frame` (string) |
| `HIPS_FRAME_UNSUPPORTED` | `planetary` | `frame` (string) |
| `HIPS_FRAME_UNSUPPORTED` | `moc_planetary` | `hips_id` (string), `body` (string) |
| `HIPS_FRAME_UNSUPPORTED` | `coverage_planetary` | `hips_id` (string), `body` (string) |
| `REGION_INVALID` | (generale) | — |
| `REGION_INVALID` | `radius` | `radius` (string) |
| `REGION_INVALID` | `center_not_single` | — |
| `REGION_INVALID` | `conversion_center` | `detail` (message: errore del 10) |
| `REGION_INVALID` | `conversion_positions` | `detail` (message: errore del 10) |
| `REGION_INVALID` | `conversion_window` | `detail` (message: errore del 10) |
| `HIPS_OUT_OF_COVERAGE` | (generale) | — |
| `HIPS_OUT_OF_COVERAGE` | `field` | `outside` (integer) |
| `HIPS_OUT_OF_COVERAGE` | `tile` | `hips_id` (string), `index` (integer), `order` (integer) |
| `HIPS_TYPE_MISMATCH` | (generale) | — |
| `HIPS_TYPE_MISMATCH` | `catalog_no_pixels` | `hips_id` (string) |
| `HIPS_TYPE_MISMATCH` | `catalog_tiles` | `hips_id` (string) |
| `HIPS_TYPE_MISMATCH` | `not_a_cube` | `hips_id` (string), `dataproduct_type` (string) |
| `HIPS_TYPE_MISMATCH` | `not_a_catalog` | `hips_id` (string), `dataproduct_type` (string) |
| `SERVICE_ERROR` | (generale) | — |
| `SERVICE_ERROR` | `http_status` | `url` (string), `status` (integer), `status_text` (string, esterno) |
| `SERVICE_ERROR` | `unreadable_response` | `url` (string), `detail` (string, esterno) |
| `HIPS_FORMAT_UNAVAILABLE` | (generale) | `hips_id` (string), `format` (string), `offered` (list) |
| `NET_TIMEOUT` | `url` | `url` (string), `connect` (quantity), `read` (quantity), `detail` (string, esterno) — voce già del 10 e dell'11 |
| `HIPS_TILE_MISSING` | (generale) | `url` (string) |
| `HIPS_BAD_TILE` | (generale) | — |
| `HIPS_BAD_TILE` | `tile_corrupt` | `url` (string), `problem` (message: `HIPS_TILE_PROBLEM`) |
| `HIPS_BAD_TILE` | `file_corrupt` | `url` (string), `problem` (message: `HIPS_TILE_PROBLEM`) |
| `HIPS_BAD_TILE` | `value_not_conformant` | `hips_id` (string), `value` (string, esterno), `column` (string, esterno), `datatype` (string, esterno), `detail` (string, esterno) |
| `HIPS_CUBE_PLANE_INVALID` | (generale) | — |
| `HIPS_CUBE_PLANE_INVALID` | `not_a_cube` | `hips_id` (string), `plane` (string) |
| `HIPS_CUBE_PLANE_INVALID` | `out_of_range` | `hips_id` (string), `plane` (string), `depth` (integer), `last_plane` (integer) |
| `HIPS_PIXEL_UNAVAILABLE` | (generale) | — |
| `HIPS_PIXEL_UNAVAILABLE` | `not_fits` | `url` (string), `format` (string) |
| `HIPS_PIXEL_UNAVAILABLE` | `no_fits_tiles` | `hips_id` (string), `formats` (list) |
| `HIPS_OUT_OF_TILE` | (generale) | — |
| `HIPS_OUT_OF_TILE` | `positions` | `count` (integer), `index` (integer), `order` (integer) |
| `HIPS_OUT_OF_TILE` | `order_mismatch` | `tile_order` (integer), `sampling_order` (integer) |
| `HIPS_OUT_OF_TILE` | `no_window_pixels` | `index` (integer) |
| `MOCSERVER_UNAVAILABLE` | (generale) | — |
| `MOCSERVER_UNAVAILABLE` | `resolve` | `hips_id` (string), `cause` (message: errore del 14) |
| `MOCSERVER_UNAVAILABLE` | `index` | `cause` (message: errore del 14) |
| `MOCSERVER_UNAVAILABLE` | `coverage` | `hips_id` (string), `cause` (message: errore del 16) |
| `MOCSERVER_UNAVAILABLE` | `local_copy` (avviso) | `retrieved_at` (string) |
| `OPERATION_UNSUPPORTED` | `build_method` | `method` (string), `allowed` (list) — voce già dell'11 |
| `OPERATION_UNSUPPORTED` | `build_color_image` | `origin` (string) |
| `HIPS_DISPLAY_REQUIRED` | (generale) | — |
| `HIPS_DISPLAY_INVALID` | (generale) | — |
| `HIPS_DISPLAY_INVALID` | `stretch` | `stretch` (string), `allowed` (list) |
| `HIPS_DISPLAY_INVALID` | `limits` | — |
| `PREVIEW_NOT_MEASURABLE` | `build_hips` | `origin` (string) — voce già dell'11 |
| `WCS_MISSING` | `image_without_wcs` | `origin` (string) — voce già del 10 e dell'11 |
| `MEMORY_LIMIT_EXCEEDED` | `build_hips` | `needed` (quantity, byte), `limit` (quantity, byte) — voce già dell'11 |
| `HIPS_EMPTY` | (generale) | — |
| `HIPS_DISPLAY_UNKNOWN` (sollevato dal 41) | (generale) | — |
| `HIPS_DISPLAY_UNKNOWN` | `no_limits` | — |
| `HIPS_DISPLAY_UNKNOWN` | `reopen` | `hips_id` (string) |
| `BODY_UNKNOWN` (avviso) | (generale) | — |
| `BODY_UNKNOWN` | `no_hips_body` | `source` (string), `frame` (string) |
| `BODY_UNKNOWN` | `body_differs` | `source` (string), `frame` (string), `body` (string) |
| `HIPS_BODY_DRAFT` (avviso) | (generale) | `source` (string), `body` (string) |
| `BODY_UNSUPPORTED` (avviso) | (generale) | `source` (string), `detail` (string, esterno) |
| `BODY_NORMALIZED` (avviso) | (generale) | `source` (string), `body` (string), `canonical` (string) |
| `HIPS_DEFAULT_TILE_WIDTH` (avviso) | (generale) | `source` (string), `width` (integer) |
| `HIPS_VERSION_UNKNOWN` (avviso) | (generale) | `source` (string), `version` (string), `standard` (string) |
| `HIPS_ID_MISMATCH` (avviso) | (generale) | `requested` (string), `service_id` (string) |
| `HIPS_ALREADY_LISTED` (avviso) | (generale) | `hips_id` (string), `origin` (string), `retrieved_at` (string) |
| `HIPS_COVERAGE_NOT_CHECKED` (avviso) | (generale) | `frame` (string) |
| `HIPS_RESOLUTION_LIMIT` (avviso) | (generale) | `hips_id` (string), `resolution` (quantity), `max_order` (integer) |
| `FROM_CACHE` (avviso) | `cached_tile` | `url` (string), `retrieved_at` (string) — voce già dell'11 |
| `HIPS_TILE_DISCARDED` (avviso) | (generale) | — |
| `HIPS_TILE_DISCARDED` | `cache_corrupt` | `url` (string), `problem` (message: `HIPS_TILE_PROBLEM`) |
| `HIPS_TILE_DISCARDED` | `tile_corrupt` | `url` (string), `problem` (message: `HIPS_TILE_PROBLEM`) |
| `HIPS_TILE_DISCARDED` | `cache_invalid` | `url` (string), `problem` (message: `HIPS_TILE_PROBLEM`) |
| `HIPS_TILE_DISCARDED` | `file_invalid` | `url` (string), `problem` (message: `HIPS_TILE_PROBLEM`) |
| `HIPS_COVERAGE_UNKNOWN` (avviso) | (generale) | — |
| `HIPS_COVERAGE_UNKNOWN` | `moc_missing` | `url` (string) |
| `HIPS_COVERAGE_UNKNOWN` | `unavailable` | `hips_id` (string), `cause_code` (string), `cause` (message: errore del 12) |
| `HIPS_COVERAGE_FROM_MOCSERVER` (avviso) | (generale) | `hips_id` (string), `url` (string) |
| `HIPS_DEFAULT_SURVEY` (avviso) | (generale) | `survey` (string) |
| `HIPS_CUBE_UNIT_UNKNOWN` (avviso) | (generale) | — |
| `HIPS_CUBE_UNIT_UNKNOWN` | `not_fits_unit` | `source` (string), `unit` (string) |
| `HIPS_CUBE_UNIT_UNKNOWN` | `missing` | `source` (string) |
| `HIPS_CUBE_AXIS_INCOMPLETE` (avviso) | (generale) | `source` (string) |
| `HIPS_UNIT_MIXED` (avviso) | (generale) | `units` (list) |
| `HIPS_ALLSKY_NOT_WRITTEN` (avviso) | (generale) | — |
| `HIPS_TILE_PROBLEM` (diagnosi, solo annidata) | (generale) | — |
| `HIPS_TILE_PROBLEM` | `no_data` | — |
| `HIPS_TILE_PROBLEM` | `fits_unreadable` | `detail` (string, esterno) |
| `HIPS_TILE_PROBLEM` | `size_mismatch` | `shape` (list), `width` (integer) |
| `HIPS_TILE_PROBLEM` | `format_mismatch` | `found` (string), `expected` (string) |
| `HIPS_TILE_PROBLEM` | `image_unreadable` | `detail` (string, esterno) |
| `HIPS_TILE_PROBLEM` | `not_utf8` | `detail` (string, esterno) |
| `HIPS_TILE_PROBLEM` | `no_header` | — |
| `HIPS_TILE_PROBLEM` | `columns_mismatch` | `header` (string, esterno), `expected` (string, esterno) |
| `HIPS_TILE_PROBLEM` | `bad_row` | `line` (integer), `fields` (integer), `expected` (integer) |

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
| T14 | Generazione e rilettura (H9) | immagine TAN sintetica (11) → `build_hips` all'ordine 4, tile 64; servire la cartella da un server simulato e rileggerla | proprietà valide per `read_service`; valori ai centri delle celle uguali all'interpolazione bilineare indipendente (`scipy`) entro 10⁻⁹; ordine inferiore = media dei 4 pixel (`numpy`) nei quadranti; `Moc.fits` uguale a `moc_from_image` del 16 | ricalcolo con `scipy`, `numpy`, `mocpy` |
| T15 | Più immagini e PNG/JPEG (H9) | due immagini sovrapposte, `nearest`, PNG e JPEG con `(−2, 12, linear)` | pixel della sovrapposizione = media delle due (ricalcolo nel test); PNG = palette grigia di `matplotlib` sul valore normalizzato, righe dall'alto, trasparente dove non finito; JPEG valido; `hips_tile_format`, `hips_pixel_cut` | ricalcolo con `matplotlib` |
| T16 | Errori di `build_hips` | ordine mancante, `flux`, PNG senza parametri, `histeq`, `vmin ≥ vmax`, ordine troppo alto, limite di memoria piccolo, immagine senza WCS, cartella non vuota, valori non validi | `TypeError`, `OPERATION_UNSUPPORTED`, `HIPS_DISPLAY_REQUIRED`, `HIPS_DISPLAY_INVALID`, `HEALPIX_ORDER_INVALID`, `MEMORY_LIMIT_EXCEEDED`, `WCS_MISSING`, `FileExistsError` (file esistente intatto), `ValueError` | test di unità |
| T12 | Valore del pixel su HiPS (H27) | leggere il valore sotto il cursore su un tile FITS in cache | valore uguale a quello del tile FITS letto con `astropy.io.fits` | confronto diretto |
| T17 | Campionamento della vista (P6) | survey FITS simulato; finestre `TAN` e `AIT` (`make_view_wcs` del 10) a scale diverse, anche a cavallo di più tile e del bordo dell'`AIT` | per ogni pixel della finestra valore uguale a `pixel_values` nel suo centro (ricalcolo nel test); tile necessari = insieme dei tile di quei pixel; pixel fuori dal cielo "nessun dato"; nessuna fascia vuota tra tile adiacenti | ricalcolo con `pixel_values` e `astropy-healpix` |
| T18 | Riempimento progressivo e colori (P6) | tile arrivati in ordine diverso; survey JPEG simulato | stesso risultato finale in qualunque ordine; colori uguali a quelli del tile letti con Pillow e capovolti come in `fetch_tile` | confronto diretto |

## 13. Decisioni aperte

- **P6 — Riproiezione dei tile sulla vista (decisione del proprietario
  del 2026-10-15):** aggiunta al 12 per il `41`; metodo e verifica in §3
  (P6). **Codice scritto il 2026-10-16** (commit `c8cf5ec`).
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
- **D12-6 — Nomi dei corpi planetari: DECISA il 2026-10-12 (decisione del
  proprietario).** I HiPS planetari scrivono il corpo in minuscolo (`mars`,
  WD HiPS 2.0); il 19 userà nomi IAU (es. `Mars`). **Esito:** opzione (b) —
  **normalizzazione dei nomi con una tabella di corrispondenza del 19, da
  scrivere insieme al 19**; fino ad allora il 12 conserva il nome del
  servizio e il confronto è sensibile alle maiuscole. **Motivazione:** un
  solo elenco dei corpi (nel 19) evita tabelle duplicate tra i moduli.
- **D12-7 — `hips_frame = ecliptic`: DECISA il 2026-10-12 (decisione del
  proprietario).** Lo standard HiPS 1.0 dice solo "ecliptic", senza indicare
  quale eclittica (es. media J2000 baricentrica, geocentrica, vera della
  data). **Esito:** opzione (a) — **non supportato** (nessun calcolo di
  campo o di pixel, `HIPS_FRAME_UNSUPPORTED`) **finché non è verificato su
  un HiPS eclittico reale**. **Motivazione:** scegliere un'eclittica senza
  verifica produrrebbe posizioni sbagliate in silenzio.
- **D12-8 — File `Allsky` di `build_hips`: DECISA il 2026-10-12 (decisione
  del proprietario).** Lo standard HiPS 1.0 (§4.3.2) dice che l'Allsky è
  facoltativo, ma **non** dice in che verso vanno le righe della matrice né
  come si riempie l'ultima riga, né l'orientamento dentro i tile per il
  FITS. **Esito:** opzione (a) — **`build_hips` per ora non produce
  l'Allsky** (avviso `HIPS_ALLSKY_NOT_WRITTEN`); i client usano i tile
  regolari. Si riapre con una proposta se il 41 ne ha bisogno per la
  velocità (disposizione da ricavare e verificare su un HiPS pubblico,
  validazione e non copia, regola d'oro n. 8).
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
| 2026-10-12 | Claude Code | **P5 scritta — modulo 12 completo tranne i pezzi fermi** (`build_hips`/`BuildResult`, `BUILD_METHODS`; T14–T16 nuovi): WCS APE 14 del tile + `reproject_interp` (verifica del 2026-10-12 contro il WCS HPX interno di `reproject` e un'interpolazione indipendente; uso di `reproject` da confermare), tile FITS `float64`, media pesata con la copertura, ordini inferiori per media di 4 pixel, PNG/JPEG con parametri espliciti (`set_display` dell'11), `Moc.fits` dal 16, `properties` per ultimo; nuova decisione aperta **D12-8** (Allsky, Gruppo 3). Fermi: H10 SkyView (URL SIA non documentato da NASA), D12-6, D12-7, D12-8. Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **Decisioni del proprietario del 2026-10-12** (autorizzazione esplicita a modificare il file approvato): H10 SkyView rinviato finché NASA non documenta l'URL SIA, con il motivo (§3); **D12-6 decisa** (normalizzazione dei nomi dei corpi con una tabella del 19, scritta con il 19), **D12-7 decisa** (`hips_frame = ecliptic` non supportato finché non è verificato su un HiPS reale), **D12-8 decisa** (nessun Allsky da `build_hips` per ora) (§3, §13); uso di `reproject` in `build_hips` approvato com'è, metodo `flux` non disponibile in `build_hips` (§3); disposizione dei pixel nel tile approvata, verificata su dati reali (2MASS K, confronto con `reproject`), da ricontrollare in AP1 (§3); scelte minori del 12 tutte confermate. Nessun codice cambia. Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **D12-6 applicata** (decisione del proprietario del 2026-10-13, autorizzazione esplicita a modificare il file approvato): `hips_body` normalizzato con la tabella dei nomi del 19 (`BODY_NORMALIZED`; fuori tabella `body = None` con `BODY_UNSUPPORTED`) (§3); test aggiornati. Stato `approvato` invariato. |
| 2026-10-15 | Claude Code | **Decisione del proprietario del 2026-10-15** (proposta della fase 1 dell'interfaccia, autorizzazione esplicita a modificare il file approvato; solo specifica, nessun codice): nuova parte **P6, riproiezione dei tile sulla vista del `41`** — `view_sampling` e `fill_view` con campionamento al più vicino sulla griglia HEALPix (disposizione dei pixel verificata, nessuna fascia tra tile), geometria da `make_view_wcs` del 10; verifica delle funzioni HiPS pubbliche di `reproject` prima del codice (§3, §7, §12 T17–T18, §13). Stato `approvato` invariato. |
| 2026-10-16 | Claude Code | **P6 scritta** (FASE: CODICE – interfaccia v1, allineamento del livello 1): `view_sampling` (campionamento al più vicino sulla griglia HEALPix, stessa regola di `pixel_values`, ordine di default da `order_for_resolution`, copertura facoltativa) e `fill_view` (valori nel tipo nativo o colori a 8 bit, riquadro e maschera, provenienza); verifica di `reproject` (scarica da sé: non usabile con la rete del 14 e la cache del 04) e tempi misurati in §3; test T17 (`TAN` e `AIT`, confini tra tile, bordo dell'`AIT`) e T18 (ordine di arrivo, colori PNG) in `tests/core/test_hips.py`. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | §13: tolte le frasi superate "codice da scrivere" per le funzioni della v1, scritte il 2026-10-16 (nessun cambiamento di contenuto). Stato `approvato` invariato. |
| 2026-10-24 | Claude Code | **D40-3, sprint 8c:** §10 — nuova sezione "Parametri dei messaggi" con codice, `reason` e `params` di ogni errore e avviso, regola per gli errori rilanciati dal 14 e dal 16 (codice e `params` restano dell'altro modulo) e per i messaggi annidati (parametri esterni); il codice li restituisce (testo italiano invariato); le traduzioni sono nel catalogo del `40`. Nessun comportamento scientifico cambia. |
| 2026-10-24 | Claude Code | **D40-7, sprint 8c-bis:** §10 — messaggi annidati di tipo `message` (errore del 10 in `REGION_INVALID`, errore del 12 in `HIPS_COVERAGE_UNKNOWN`, diagnosi del tile con il nuovo codice annidato `HIPS_TILE_PROBLEM` in `HIPS_BAD_TILE` e `HIPS_TILE_DISCARDED`); il testo italiano non cambia. |
| 2026-10-24 | Claude Code | **D40-3, sprint 8d (modulo 14):** gli errori del 14 incorporati dal testo del 12 (`HIPS_NOT_A_SERVICE` `service_error`, `HIPS_METADATA_INVALID` `metadata_xml_unavailable`, `MOCSERVER_UNAVAILABLE` `resolve` e `index`) passano da parametro esterno `detail` a parametro `message` `cause`. Nessun comportamento scientifico cambia. |
| 2026-10-24 | Claude Code | **D40-3, sprint 8d (modulo 16):** l'errore del 16 incorporato dal testo del 12 (`MOCSERVER_UNAVAILABLE` `coverage`) passa da parametro esterno `detail` a parametro `message` `cause`; gli errori del 16 rilanciati dal 12 portano i loro `params`. Nessun comportamento scientifico cambia. |
