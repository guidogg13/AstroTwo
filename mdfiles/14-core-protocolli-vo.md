# 14-core-protocolli-vo.md — protocolli Virtual Observatory

**Stato:** approvato

## 2. Scopo

Fare da unico punto di accesso ai protocolli del Virtual Observatory (VOTable,
cone search, TAP/ADQL, esportazione, SAMP, SSA, schede server), così che ogni
scambio di dati con i servizi astronomici segua gli standard e resti
riproducibile.

## 3. Cosa fa

**Divisione del codice (decisione del proprietario del 2026-10-10):** sette
parti, in quest'ordine, ciascuna con verifiche, codice, test di tutto il
progetto e commit — **P1** lettura/scrittura VOTable ed esportazione CSV,
VOTable, FITS con provenienza (T1, T5); **P2** base di rete: timeout comuni
di `04`, registro delle richieste, cache delle interrogazioni,
`download_table` (T6); **P3** cone search, TAP/ADQL (righe massime,
interrogazioni lunghe), `validate_adql` (T2, T3, T4); **P4** elenco dei
server (D14-4), ricerca nel registro VO, DataLink (D14-3) (T17–T19);
**P5** immagini SIA/SIA2, IDHA, spettri SSA (T9–T12, T15, T16); **P6**
puntatore Simbad e fotometria VizieR (H17) (T13, T14); **P7** SAMP (T7,
T8). Dopo il 14: P6 del `13` (cataloghi da servizio e da URL).

**Regole comuni (decisioni del proprietario del 2026-10-10, D14-9):**

- **Un solo lettore di tabelle:** ogni tabella ricevuta dalla rete o letta
  da file si legge con `read_table` del `13` (anche i VOTable); il 14 si
  occupa solo della rete, dei protocolli e della scrittura. Il risultato è
  una `CatalogTable` del 13 con origine = URL della richiesta e data di
  scaricamento.
- **Registro delle richieste (riproducibilità, regola d'oro n. 6):** ogni
  richiesta di rete produce un `RequestRecord` con protocollo, funzione
  chiamata e suoi argomenti, URL effettivo del servizio, parametri inviati,
  data e ora (UTC), numero di righe ricevute e provenienza dalla cache; con
  la funzione e gli argomenti registrati la richiesta si riesegue identica.
- **Cache delle interrogazioni (una sola, qui; D14-9 punto 7):** prima la
  cache, `refresh=True` per rifare la richiesta (stessa regola di
  `resolve_name` del 10 e delle immagini da URL dell'11). Chiave =
  protocollo, URL del servizio e parametri della richiesta. Si salvano solo
  le risposte riuscite, come byte della risposta in una tabella SQLite del
  modulo dentro `SharedCache` (`04-cache.md`). Se la rete non risponde e la
  risposta è in cache, si usa la copia dichiarandola; altrimenti
  `NET_TIMEOUT`.
- **Righe massime (D14-5, decisa il 2026-10-10):** `max_rows` di default
  **100 000**, configurabile da 1 fino al tetto di righe del `13`
  (`TableLimits.max_rows`, 1 000 000 di default); fuori intervallo
  `MAX_ROWS_INVALID`. Il superamento è **sempre dichiarato** con l'avviso
  `ROW_LIMIT_EXCEEDED` (righe restituite e, quando il servizio lo dice,
  troncamento lato servizio); mai una riduzione silenziosa.
- **Credenziali:** nel livello 1 solo servizi pubblici senza
  autenticazione (il livello 1 non può dipendere dal `31`); un servizio che
  chiede autenticazione dà `AUTH_REQUIRED`.

- **VOTable (E5):** leggere e scrivere VOTable conservando nomi, unità,
  metadati e risorse; rifiutare i file malformati con errore esplicito.
  `read_votable` usa `read_table` del 13 e accetta solo VOTable
  (`VOTABLE_INVALID` con la posizione del problema per un file malformato o
  di altro formato).
- **Cone search (E1):** interrogare un catalogo in un raggio attorno a un
  punto; centro e raggio con unità; risultato come tabella con provenienza.
  Il parametro `catalog` è **una voce dell'elenco dei server** (protocollo
  cone search) **oppure un URL di servizio SCS esplicito**; gli
  identificativi VizieR (es. `I/239/hip_main`) non si accettano qui:
  passano da TAP VizieR in P6 del 13. Righe oltre `max_rows`: tabella
  ridotta alle prime `max_rows` righe ricevute, con `ROW_LIMIT_EXCEEDED` e il
  numero di righe ricevute.
- **TAP / ADQL (E2):** eseguire query ADQL sui servizi TAP; gestione di
  sintassi errata, timeout, limiti di righe e stati lunghi della query.
  La costruzione/validazione assistita della query è di `33-ia-query-adql.md`,
  qui vive l'esecuzione deterministica. **Modalità (D14-9):** sincrona di
  default; asincrona su richiesta (`mode="async"`), con **attesa massima
  complessiva di 600 s, configurabile**, oltre la quale il lavoro si
  interrompe (`NET_TIMEOUT`); se il servizio rifiuta o interrompe la
  sincrona per durata, l'errore suggerisce la modalità asincrona.
  `max_rows` va al servizio come `MAXREC`; il troncamento dichiarato dal
  servizio (`OVERFLOW`) dà `ROW_LIMIT_EXCEEDED`.
- **`validate_adql` (D14-9):** solo **controlli minimi** lato client —
  testo non vuoto, inizia con `SELECT` (maiuscole o minuscole), virgolette
  semplici e doppie chiuse, parentesi bilanciate (fuori dalle virgolette);
  altrimenti `ADQL_INVALID` con la posizione, senza chiamate di rete. La
  validazione vera è quella del servizio, che prevale.
- **Download tabelle (D3) ed export (D13):** scaricare tabelle da URL e
  salvare tabelle in CSV, VOTable e FITS con intestazione che riporta origine,
  data e versione dello schema. **Provenienza nei file esportati (D14-9):**
  origine e data della tabella, operazioni registrate, data
  dell'esportazione, **versione di AstroTwo e versione del formato**, più
  la **versione di `astropy`** che scrive il file (`A2WRITER`):
  VOTable scritto in versione **1.4** con `INFO`; FITS con parole chiave
  dell'intestazione e versione del formato **"FITS Standard 4.0"**
  (decisione del proprietario del 2026-10-11); **CSV con righe di commento
  `#` all'inizio**. **Unità (D14-10, decisa il 2026-10-11):** per le
  tabelle con unità si esporta in **ECSV** di `astropy` (formato `ecsv`:
  CSV con intestazione YAML in righe `#`, che conserva unità, UCD,
  descrizioni e valori mancanti; provenienza nei metadati della tabella;
  versione del formato "ECSV 1.0"); il 13 rilegge l'ECSV. Il **CSV
  semplice resta disponibile**: con colonne che hanno unità dà l'avviso
  `CSV_UNITS_NOT_SAVED` (le unità non vengono salvate). L'ECSV non ha un
  posto standard per il sistema delle posizioni (il `COOSYS` del VOTable):
  **AstroTwo lo scrive nei metadati YAML** come `A2POSITIONS` (colonne,
  sistema, termine originale, equinozio, epoca, fonte: UCD o conferma
  dell'utente; decisione del proprietario del 2026-10-11) e il 13 lo
  rilegge, quindi un ECSV scritto da AstroTwo non dà `FRAME_UNKNOWN`; il
  testo resta anche nella provenienza `A2POS`.
- **Schede server (H10):** gestire i collegamenti a servizi esterni con un
  **elenco di server nostro**, tratto dai servizi pubblici del VO (D14-4,
  corretta il 2026-10-10), più i server personali dell'utente; le immagini
  HiPS restano in `12-core-hips.md`. La ricerca nel registro VO usa
  `pyvo.registry` (protocollo RegTAP). **Registro di default (verifica
  chiusa dal proprietario il 2026-10-11):** `DEFAULT_REGISTRY_URL` =
  `https://dc.g-vo.org/tap` (RegTAP del GAVO in HTTPS, certificato valido
  verificato il 2026-10-11, lo stesso del test di rete), **configurabile**
  con `registry_url`; nessun servizio senza HTTPS valido come default: il
  default di `pyvo` (`http://reg.g-vo.org/tap`) non ha un certificato
  valido per il suo nome in HTTPS e da questa rete risponde "Request
  Denied". I server personali sono voci con gli
  stessi campi, tenute da `ServerRegistry`; il loro salvataggio nelle
  preferenze è di `40-ui-finestra-principale.md`.
- **DataLink (H8, parte VO):** leggere e risolvere i link di DataLink
  associati alle tabelle, con i descrittori di servizio (D14-3); versione
  dello standard supportata da `pyvo` verificata prima del codice di P4.
  **Colonna DataLink (per P6 del 13, D14-9 punto 14):** è quella citata da
  un **descrittore di servizio DataLink** del VOTable (risorsa `meta` con
  `standardID` DataLink e parametro `ID` riferito a una colonna), oppure la
  colonna con **content-type
  `application/x-votable+xml;content=datalink`**.
- **SAMP (H14, G3):** interoperabilità con altri strumenti (TOPCAT, DS9,
  SPLAT, CASSIS e simili): AstroTwo **si collega a un hub SAMP già attivo se
  presente, altrimenti avvia il proprio hub** (D14-2, decisa il 2026-10-04).
  **Primo perimetro: invio e ricezione di tabelle, selezioni e puntamenti**
  (gli oggetti selezionati in vista o in tabella; centri/coordinate verso cui
  far puntare il programma remoto), da e verso altri programmi; **le immagini
  restano un'estensione prevista**, fuori dal primo perimetro. Elenco dei
  client connessi e stato dei collegamenti. Incluso per decisione del
  proprietario (2026-10-04): in Aladin la funzione "apertura in strumenti
  esterni" (G3) non è documentata come SAMP in tutti i dettagli, ma la parità
  con Aladin è il minimo. **Libreria e messaggi (D14-9):** `pyvo.samp`
  (`astropy.samp` è deprecato da astropy 8.0); solo i messaggi standard
  **`table.load.votable`**, **`table.select.rowList`** e
  **`coord.pointAt.sky`**; ogni altro tipo → `SAMP_UNSUPPORTED_TYPE`.
  **Profilo web disattivato** di default nell'hub avviato da AstroTwo, per
  sicurezza (accesso dai browser solo con opzione esplicita).
  **L'interfaccia utente** (es. comando "invia la
  selezione") **vive in `42-ui-pannello-cataloghi.md`**, che chiama
  `SampHub`.
- **Spettri SSA (E4):** ricerca e caricamento di spettri dai servizi VO con
  il protocollo **SSA** (Simple Spectral Access): interrogare il servizio con
  posizione/oggetto e raggio (con unità), selezionare lo spettro richeriesto e
  caricarlo con flusso, assi, unità, metadati e provenienza; risposta vuota o
  spettro malformato gestiti con errori espliciti (§10). Incluso per decisione
  del proprietario (2026-10-04): la riga E4 non era confermata dalla
  documentazione di Aladin, ma la parità con Aladin è il minimo — parte
  tecnica decisa il 2026-10-09: SSA 1.1 con `pyvo` (§13-D14-6).
  **Formati degli spettri (D14-9):** VOTable secondo lo **Spectrum Data
  Model IVOA** (assi riconosciuti dagli `utype` del modello) e **FITS
  tabellari con colonne riconosciute da UCD o `utype`**; tutto il resto
  `SSA_INVALID`. Nessuna dipendenza nuova (niente `specutils`).
  **L'analisi degli spettri** (dereddening, misure di linea) **vive in
  `21-analisi-spettroscopia.md`**, che riceve lo spettro caricato qui.
- **Cache delle interrogazioni (A7):** i risultati delle query si conservano
  nelle tabelle SQLite di questo modulo dentro la **cache comune di
  `04-cache.md`** (limite unico di 5 GB, rimozione dei dati meno usati,
  origine/data per ogni voce); le richieste di rete usano i timeout comuni
  (10 s connessione, 60 s lettura, configurabili); nessuna cache propria (CA4).
- **Liste di immagini SIA e SIA2 (H23, sez. 5.14 e 8.1 del manuale di
  Aladin, ed. giugno 2022):** ricerca di immagini per posizione e raggio (SIA) e per
  posizione, banda e intervallo di tempo (SIA2) con `pyvo` (D14-1). Il
  risultato è una tabella di immagini con URL di accesso, formato, campo,
  banda e, se presente, calibrazione astrometrica fornita dalla lista; il
  caricamento delle immagini è di `11-core-immagini-fits.md`, che usa la
  calibrazione della lista quando l'immagine non ne ha una propria.
  **Calibrazione della lista (D14-11, decisa il 2026-10-11):**
  `sia_calibration` costruisce un'intestazione WCS dalle colonne di una
  riga SIA 1, riconosciute dagli UCD della raccomandazione **SIA 1.0** (§4.2,
  verificata il 2026-10-11): `VOX:WCS_CoordProjection` (codice di tre
  caratteri di FITS WCS), `VOX:WCS_CoordRefPixel` (= `CRPIX`, convenzione
  FITS), `VOX:WCS_CoordRefValue` (= `CRVAL`, gradi; convertito se la
  colonna dichiara un'altra unità angolare), `VOX:WCS_CDMatrix` (= `CD`,
  ordine [1,1], [1,2], [2,1], [2,2]), `VOX:STC_CoordRefFrame` (tradotti
  `ICRS`, `FK5`, `FK4` → `RADESYS`, `GAL` → assi `GLON`/`GLAT`; `ECL` e
  `SGAL` non tradotti: lo standard non dice quale eclittica),
  `VOX:STC_CoordEquinox` (obbligatorio per FK5 e FK4, mai assunto) e
  `VOX:Image_Naxis` (dimensioni, per il controllo nell'11). Validata con
  `wcs_from_header` del modulo 10. Un dato mancante o non valido → nessuna
  calibrazione, con il motivo (`reason`). L'11 la riceve con il parametro
  `calibration` di `load_image` e la dichiara nel risultato. **SIA 2**
  (ObsCore) non ha colonne WCS: `sia_calibration` vale solo per SIA 1. Il
  formato storico IDHA (alternativa a SIA supportata da Aladin per
  compatibilità): **nessuna documentazione pubblica trovata** (D14-9 punto
  13, 2026-10-10), quindi **solo l'errore `IDHA_UNREADABLE`**; il file si
  apre comunque con `defusedxml` prima di rifiutarlo, così che un XML
  pericoloso dia `XML_UNSAFE` (D14-8).
- **Puntatori Simbad e VizieR, parte VO (H17, sez. 5.10):** interrogazione
  di **Simbad** per posizione con **raggio sempre esplicito, passato
  dall'interfaccia (41)**, che ne decide il default; nessun valore preso dal
  manuale di Aladin (regola d'oro n. 8; D14-9). Con `astroquery.simbad`,
  restituendo identificativo, magnitudini (D14-12), tipo,
  coordinate e numero di riferimenti bibliografici dell'oggetto più citato
  (campo bibliografico **da verificare** nell'interfaccia di Simbad); **più
  oggetti con lo stesso numero di citazioni: vince il più vicino al
  centro**, e il risultato lo dichiara;
  interrogazione del **servizio fotometrico di VizieR** attorno a una
  posizione o alla posizione Simbad, restituendo la tabella delle misure di
  flusso con frequenza o lunghezza d'onda, unità, catalogo d'origine e data
  quando presente. Il client è quello HTTP diretto già usato nel 12 (D12-4);
  interfaccia del servizio **da verificare prima del codice**. **Esito della
  verifica (2026-10-10, P6):** documentazione del CDS
  (`vizier/sed/doc`) e servizio in linea `https://vizier.cds.unistra.fr/viz-bin/sed`:
  parametri `-c` (posizione) e `-c.rs` (raggio in arcsec, **al massimo 30
  arcsec** secondo la documentazione: oltre, rifiuto, nessuna riduzione
  silenziosa); risposta VOTable con `_sed_freq` (GHz), `_sed_flux` e
  `_sed_eflux` (Jy), `_sed_filter`, catalogo d'origine `_tabname`, data
  `_time` (JD, `TIMESYS` TCB baricentrico) quando presente, posizione
  `_RAJ2000`/`_DEJ2000` (FK5 J2000). Client: la sessione `requests` di P2
  (il 12 non è ancora scritto). **Campo delle citazioni in `astroquery.simbad`
  (verificato il 2026-10-10 con `Simbad.list_columns`):** `nbref` della
  tabella `basic` ("number of references"), aggiunto con
  `add_votable_fields`. **Magnitudini (D14-12, decisa il 2026-10-11):**
  **tutte le magnitudini disponibili** in SIMBAD per l'oggetto scelto,
  ognuna con **nome della banda e sistema dichiarati**, da una seconda
  interrogazione al TAP di SIMBAD (voce dell'elenco dei server, con
  `tap_query`: stessa cache e richiesta registrata) sulle tabelle `flux`
  (filtro, valore, errore, sistema, qualità, riferimento) e `filter`
  (descrizione della banda, unità). **Verifica del 2026-10-11** sul
  `TAP_SCHEMA` di SIMBAD: la colonna `system` di `flux` è descritta "flux
  system A=AB V=Vega" ed è vuota per una parte delle misure (circa 4,4
  milioni su 85 milioni); il sistema si dichiara quindi `AB` o `Vega` dal
  codice, **non dichiarato** (`None`, avviso `SIMBAD_SYSTEM_UNDECLARED`)
  se il codice manca, mai assunto; un codice diverso → `None` con
  l'avviso `SIMBAD_SYSTEM_UNKNOWN`. Nessuna magnitudine → avviso
  `SIMBAD_NO_MAGNITUDE`. La
  costruzione della SED è del modulo 20 (deciso il 2026-10-08).
- **Collezioni del MocServer (D13-18, decisa il 2026-10-11):**
  `vizier_collections` interroga il **MocServer del CDS**
  (`MOCSERVER_URL` = `https://alasky.cds.unistra.fr/MocServer/query`,
  verificato in linea il 2026-10-11) con l'espressione `ID=CDS/* &&
  dataproduct_type=catalog`, risposta JSON con `ID`, `obs_title` e
  `vizier_popularity`; stessa sessione, cache e registro delle richieste
  delle altre funzioni (protocollo `mocserver`); risposta non leggibile →
  `SERVICE_ERROR`. Il MocServer non entra nell'elenco dei server (che
  copre cone search, TAP, SIA, SSA): l'URL è una costante del modulo,
  come quello del servizio fotometrico di VizieR. L'albero si costruisce
  nel 13 (`collection_tree`).
- **Equivalente di VOApp/VOObserver (H19):** per i programmi non Python lo
  scambio passa da SAMP (questo modulo); per i programmi Python dall'API del
  24; nessuna interfaccia nuova (decisione del 2026-10-08).
- **Sistema di plugin (H14):** in Aladin le estensioni sono plugin Java
  (sez. 7.3). **Nel livello 1 AstroTwo non ha un sistema di plugin** (D14-7,
  decisa il 2026-10-09): le estensioni passano dall'API Python di
  `24-analisi-pipeline-riproducibili.md`, dove è spostata la parte "plugin"
  di H14. Questo modulo copre solo la parte SAMP di H14.

## 4. Cosa NON fa

- Non interpreta i risultati scientificamente (13/15/20).
- Non analizza gli spettri: carica SSA qui, l'analisi è di
  `21-analisi-spettroscopia.md`.
- Non scrive le query ADQL al posto dell'utente o dell'IA: la validazione e
  l'assistenza sono di `33-ia-query-adql.md`.
- Non fa il cross-match: `15-core-crossmatch.md`.
- Non gestisce i MOC: `16-core-moc.md`.
- Non disegna né visualizza: la UI (41/42) mostra ciò che questo modulo restituisce.
- Non conserva chiavi API e, nel livello 1, non usa servizi con
  autenticazione (D14-9 punto 12): il livello 1 non può dipendere dal `31`.
- Non legge i file IDHA: nessuna documentazione pubblica (D14-9 punto 13).
- Non decide il raggio di default del puntatore Simbad: lo passa il `41`.

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `04-cache.md` (cache comune A7 e timeout di rete),
  `10-core-coordinate-wcs.md` (centri e raggi in coordinate),
  `13-core-cataloghi.md` (rappresentazione delle tabelle ricevute).
- **Usato da:** `13-core-cataloghi.md`, `15-core-crossmatch.md`,
  `16-core-moc.md`, `19-core-dati-planetari.md`,
  `21-analisi-spettroscopia.md`, `33-ia-query-adql.md`,
  `42-ui-pannello-cataloghi.md`, `50-avanzate-transienti.md` (per i servizi).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `center` | float64 | gradi, ICRS | centro della cone search |
| in | `radius` | float64 | gradi/arcmin/arcsec (`Quantity`) | raggio |
| in | `adql` | stringa | testo ADQL | validato prima dell'esecuzione |
| in | `tap_url` | stringa | URL del servizio TAP | |
| in | file tabella | percorso/URL | VOTable, CSV, FITS | lettura/scrittura |
| in | messaggio SAMP | struttura | tipo + payload (tabella/selezione/puntamento/coordinate) | G3: invio e ricezione |
| in | criteri ricerca spettri | struttura | posizione/oggetto + raggio con unità | E4: SSA |
| out | spettro | `astropy.table.Table` | flusso vs lunghezza d'onda/frequenza + unità + metadati | E4: l'analisi è in `21` |
| out | stato SAMP | enumerativo | client connessi / invio riuscito / nessun peer | G3 |
| out | tabella | `astropy.table.Table` | con unità e provenienza | |
| out | `body` | stringa | `celestial` o nome IAU del corpo | obbligatorio (D19-3) per tabelle, spettri e risultati di query: ricavato dal sistema di coordinate dichiarato dal servizio o dai metadati EPN-TAP, mai assunto |
| out | righe | intero | conteggio | con limite dichiarato |
| out | file esportato | VOTable/ECSV/CSV/FITS | con header di provenienza e data | ECSV per le unità (D14-10) |
| out | stato query | enumerativo | eseguita / in corso / fallita + errore | |
| in | criteri SIA/SIA2 | struttura | posizione + raggio con unità; per SIA2 anche banda e intervallo di tempo (JD, scala dichiarata) | H23 |
| out | lista di immagini | `astropy.table.Table` | URL di accesso, formato, campo, banda, eventuale calibrazione, `body` | H23 |
| in | posizione per i puntatori | float64 | gradi + frame + raggio | H17 |
| out | oggetto Simbad | struttura | identificativo, tipo, magnitudini (banda, descrizione, valore, errore, unità, sistema, qualità, riferimento), coordinate, numero di riferimenti, fonte e data | H17, D14-12 |
| out | misure fotometriche VizieR | `astropy.table.Table` | flusso con unità, frequenza o lunghezza d'onda, catalogo d'origine, data | H17; la SED si costruisce nel 20 |

## 7. Interfaccia pubblica

Codice in `src/astrotwo/core/vo_protocols.py` (tabella di `02` §3). Ogni
funzione di rete accetta `cache` (`SharedCache`, default la cache comune),
`refresh` (default `False`) e `timeouts` (`NETWORK_TIMEOUTS` di `04`).

- **`VoProtocolsError`** — errore con identificatore di §10.
- **`RequestRecord`** (struttura, P2) — protocollo, funzione e argomenti,
  URL, parametri, data (UTC), righe, `from_cache`; `as_dict()` per la
  registrazione (regola d'oro n. 6).
- **`VoResult`** (struttura, P2) — `table` (`CatalogTable` del 13),
  `request` (`RequestRecord`), avvisi (es. `ROW_LIMIT_EXCEEDED`,
  `FROM_CACHE`), `truncated`, `max_rows`.
- **`read_votable(path, *, table=None)`** / **`write_votable(table, path,
  overwrite=False)`** (P1) — I/O VOTable; la lettura passa da `read_table`
  del 13 (D14-9 punto 5); la scrittura è `export_table(..., "votable")`.
- **`export_table(table, path, format, overwrite=False)`** (P1, D13) —
  `format` in `csv`, `ecsv`, `votable`, `fits`; provenienza come in §3; file
  esistente senza `overwrite=True` → `FILE_EXISTS`. Restituisce
  `ExportResult` (percorso, formato, avvisi come `CSV_UNITS_NOT_SAVED`;
  vale anche come percorso).
- **`download_table(url, *, table=None, format=None, ...)`** (P2) — scarica
  una tabella da URL e la legge con `read_table` del 13; restituisce
  `VoResult`.
- **`cone_search(center, radius, catalog, *, max_rows=100_000, ...)`** (P3)
  — `center` posizione celeste (`SkyCoord`/`SkyFrame` del 10, convertita in
  ICRS dal 10), `radius` angolo con unità, `catalog` voce dell'elenco dei
  server o URL SCS; restituisce `VoResult`.
- **`tap_query(url, adql, *, max_rows=100_000, mode="sync",
  async_timeout=600 s, ...)`** (P3) — esecuzione ADQL; restituisce
  `VoResult` o errore con il messaggio del servizio; `url` è un URL TAP o
  una voce TAP dell'elenco dei server.
- **`validate_adql(adql)`** (P3) — controlli minimi di §3; restituisce
  l'esito (valido, messaggio, posizione); `tap_query` lo chiama prima
  dell'invio.
- **`ServerRegistry`** (classe, P4) — schede server H10: elenco nostro
  (`builtin`), server personali (`add_personal`, `remove_personal`),
  `get(id)`, `find(protocol=None, provider=None)`, `search_registry(
  keywords, servicetype, registry_url=None)` nel registro VO (`None` =
  `DEFAULT_REGISTRY_URL`, HTTPS); voce `ServerEntry` con `id`,
  nome, ente, protocollo, URL, fonte dell'URL (pagina ufficiale dell'ente)
  e data di verifica.
- **`DataLinkClient`** (P4) — `links(source)` (URL DataLink o riga con
  colonna DataLink): tabella dei link (semantica, URL, content-type,
  descrizione, descrittore di servizio); `service_descriptors(...)`;
  `call_service(descriptor, params)` per le elaborazioni lato server (D14-3).
- **`sia_search(center, radius, *, version, service, band=None,
  time=None, max_rows=100_000, ...)`** (P5, H23) — `version` `1` (SIA) o `2`
  (SIA2); `band` intervallo di lunghezze d'onda con unità e `time`
  intervallo di `Time` con scala dichiarata (solo SIA2); restituisce
  `VoResult` con la lista di immagini.
- **`sia_calibration(result, index)`** (D14-11) — `SiaCalibration`
  (`header` FITS con WCS e dimensioni, o `None`; `source` = URL della lista
  e riga; colonne usate; `reason` se non costruibile) dalla riga `index` di
  una lista SIA 1; da passare a `load_image(..., calibration=...)` dell'11.
- **`read_idha(path)`** (P5) — apre il file con `defusedxml` e lo
  rifiuta: `XML_UNSAFE` o `IDHA_UNREADABLE` (D14-9 punto 13).
- **`ssa_search(center, radius, *, service, max_rows=100_000, ...)`** (P5,
  E4) — ricerca spettri SSA 1.1; restituisce `VoResult` con i candidati.
- **`ssa_load(candidate, ...)`** (P5, E4) — `candidate` è una riga del
  risultato di `ssa_search` (o l'URL di accesso con il formato dichiarato);
  restituisce lo spettro (`Spectrum`: tabella con asse spettrale e flusso
  con unità, metadati, provenienza) per il `21`.
- **`simbad_pointer(center, radius, ...)`** (P6, H17) — `radius`
  obbligatorio, passato dal 41; oggetto Simbad più citato nel raggio
  (a pari citazioni il più vicino, dichiarato), con fonte e data;
  `SimbadObject.magnitudes` = tutte le magnitudini (`SimbadMagnitude`:
  banda, descrizione, valore, errore, unità, sistema `AB`/`Vega`/`None`,
  qualità, riferimento), richiesta registrata in `magnitudes_request`
  (D14-12).
- **`vizier_collections(*, cache, refresh, timeouts)`** (D13-18) —
  `MocServerRecords` (record del MocServer come dati dal servizio, richiesta
  registrata, avvisi), per l'albero delle collezioni del 13.
- **`vizier_photometry(center, radius, ...)`** (P6, H17) — misure di flusso
  dal servizio fotometrico di VizieR, con catalogo d'origine per ogni punto.
- **`SampHub`** (classe, P7) — hub SAMP (H14, G3, D14-2 decisa) con
  `pyvo.samp`: **si collega a un hub già attivo se presente, altrimenti
  avvia il proprio** (profilo web disattivato salvo opzione esplicita);
  `send_table`, `send_selection`, `send_point`, ricezione degli stessi tre
  tipi con funzioni dell'utente, `clients()` e stato dei collegamenti; **le
  immagini sono un'estensione prevista** fuori dal primo perimetro;
  l'interfaccia utente è in `42-ui-pannello-cataloghi.md`.
- **Cache:** nessuna classe propria (CA4): le risposte si salvano nella
  tabella SQLite del modulo dentro `SharedCache` di `04-cache.md`.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `astropy.io.votable` | lettura/scrittura VOTable | implementazione di riferimento |
| `pyvo` 1.9.1 (**scelto con D14-1**; BSD-3, verificato il 2026-10-10) | client SCS, TAP, SIA, SIA2, SSA, DataLink/SODA, registro VO | libreria VO consolidata IVOA |
| `pyvo.samp` (D14-1 aggiornata il 2026-10-10) | hub e client SAMP | `astropy.samp` è deprecato da astropy 8.0; `pyvo.samp` è la stessa implementazione mantenuta in `pyvo` (BSD-3) |
| `astroquery` | alcuni servizi (es. cone search via CDS) | integrazione consolidata |
| `astropy.table` | tabelle in uscita | unità e metadati |
| Protocolli IVOA (VOTable, TAP, DataLink, SAMP, SSA) | standard di scambio | standard della comunità |
| `sqlite3` (tramite `04-cache.md`) | cache delle query (A7) | scelta A7 |
| `pyvo` (D14-1) | ricerche SIA e SIA2 (H23) | stessa libreria VO già scelta |
| `astroquery.simbad` | puntatore Simbad (H17) | servizio CDS ufficiale, già usato dal modulo 10 |
| Servizio fotometrico di VizieR (CDS) | misure di flusso per la SED (H17) | servizio pubblico che raccoglie in un'unica risposta le misure di flusso dei cataloghi di VizieR; interfaccia da verificare prima del codice |
| MocServer del CDS (D13-18) | elenco delle collezioni VizieR con `vizier_popularity` per l'albero del 13 | unico servizio trovato che elenca le collezioni con una popolarità; proprietà non documentata, dichiarata nel risultato |
| `defusedxml` 0.7.1 (D14-8; licenza PSF, già tra le dipendenze) | apertura sicura dei file IDHA prima del rifiuto (H23) | parser XML sicuro per file non fidati |
| `requests` (già tra le dipendenze) | sessione HTTP con i timeout comuni di `04` | client HTTP consolidato, usato anche da `pyvo` |

## 9. Regole e vincoli

- Ogni risposta di rete registra: URL del servizio, parametri, timestamp,
  numero di righe — sufficiente a rieseguire la richiesta (riproducibilità).
- Timeout dichiarati per ogni protocollo; nessuna chiamata "senza limite".
- Nessuna chiave API letta da file o log (regola d'oro n. 5).
- Le query con risultato enorme sono troncate con avviso esplicito di
  `max_rows`, mai ridotte in silenzio.
- I file esportati portano versione dello schema e origine dei dati.
- L'ADQL viene validato prima dell'invio e validato di nuovo dal servizio:
  l'esito del servizio prevale.
- Nessun risultato è mostrato come "dato" se non è accompagnato da provenienza
  e data (vincolo A7 anche per la cache).

- **Corpo di riferimento (`body`, D19-3 decisa il 2026-10-08):** ogni tabella, spettro o risultato di query ricevuto, letto o inviato porta
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
| VOTable malformato | nessun dato letto, errore con posizione del problema | `VOTABLE_INVALID` |
| ADQL sintatticamente errata | rifiuto lato client con il messaggio, o errore del servizio riportato | `ADQL_INVALID` |
| Servizio TAP non raggiungibile / timeout | errore di rete, nessun risultato parziale mostrato come valido | `NET_TIMEOUT` |
| Query che supera il limite di righe | risultato troncato con avviso e conteggio dichiarato (avviso, non errore) | `ROW_LIMIT_EXCEEDED` |
| Formato di esportazione non supportato | elenco dei formati | `EXPORT_FORMAT_UNSUPPORTED` |
| Esportazione in CSV semplice di una tabella con unità | file scritto senza unità; si suggerisce `ecsv` (D14-10) | avviso `CSV_UNITS_NOT_SAVED` |
| Nessun hub SAMP disponibile (né attivo, né avviabile) | funzioni VO non-SAMP operative, avviso | `SAMP_UNAVAILABLE` |
| Nessun client SAMP connesso | azione rifiutata con messaggio chiaro | `SAMP_NO_PEER` |
| Tipo di messaggio SAMP non supportato | rifiuto con l'elenco dei tipi supportati | `SAMP_UNSUPPORTED_TYPE` |
| Servizio SSA non raggiungibile / timeout | nessun elenco di spettri, errore esplicito | `NET_TIMEOUT` |
| Nessuno spettro per i criteri dati | esito vuoto con avviso, non è un errore | `SSA_NO_RESULT` |
| Spettro SSA malformato o senza assi/unità | nessun dato mostrato come valido, errore con la posizione del problema | `SSA_INVALID` |
| Cache non disponibile | query eseguita comunque, cache saltata con avviso | `CACHE_UNAVAILABLE` |
| Corpo (`body`) non ricavabile dai metadati né dal sistema di coordinate | dato aperto da solo, non sovrapposto né combinato | `BODY_UNKNOWN` |
| Nessuna immagine per i criteri SIA/SIA2 | esito vuoto con avviso, non è un errore | `SIA_NO_RESULT` |
| Risposta SIA malformata | nessuna lista mostrata come valida | `SIA_INVALID` |
| Nessun oggetto Simbad nel raggio | esito vuoto con avviso | `SIMBAD_NO_OBJECT` |
| Magnitudine Simbad senza codice di sistema | magnitudine restituita con sistema non dichiarato (`None`) | avviso `SIMBAD_SYSTEM_UNDECLARED` |
| Codice di sistema Simbad diverso da `A`/`V` | magnitudine con sistema `None` | avviso `SIMBAD_SYSTEM_UNKNOWN` |
| Oggetto Simbad senza magnitudini | oggetto restituito senza magnitudini | avviso `SIMBAD_NO_MAGNITUDE` |
| Servizio fotometrico di VizieR non raggiungibile | errore di rete, nessun punto inventato | `NET_TIMEOUT` |
| File IDHA non conforme, o lettore non disponibile per mancanza di documentazione ed esempi | rifiuto esplicito con la causa | `IDHA_UNREADABLE` |
| File XML con costrutti pericolosi (es. espansione di entità) | lettura interrotta, nessun dato caricato | `XML_UNSAFE` |
| File di destinazione già esistente senza `overwrite=True` | nessuna scrittura | `FILE_EXISTS` |
| `max_rows` fuori da 1…tetto del 13 | rifiuto con l'intervallo ammesso | `MAX_ROWS_INVALID` |
| Servizio che chiede autenticazione | rifiuto: nel livello 1 solo servizi pubblici | `AUTH_REQUIRED` |
| Servizio raggiungibile che risponde con un errore (HTTP o `QUERY_STATUS = ERROR` non dovuto all'ADQL) | nessun risultato, messaggio del servizio riportato | `SERVICE_ERROR` |
| Voce dell'elenco dei server inesistente o con protocollo diverso da quello richiesto | rifiuto con le voci ammesse | `SERVER_UNKNOWN` |
| Spettro, immagine o risultato servito dalla cache | dato restituito con origine e data della copia | avviso `FROM_CACHE` |

## 11. Esposizione all'IA

Non applicabile in questo file: gli strumenti per l'IA si dichiarano in
`32-ia-registro-strumenti.md` (`01-architettura.md` §7, decisione del
proprietario del 2026-10-10, D14-9 punto 16). Finché il 32 non esiste,
l'elenco da riportarvi (nomi provvisori: `cone_search`, `tap_query`,
`validate_adql`, `describe_services` su `ServerRegistry`, `ssa_search`,
`ssa_load`) è annotato nella riga del 32 in `panoramica.md` §4. Vale sempre
la regola d'oro n. 1: l'IA compone i parametri e spiega l'esito, il
contenuto delle tabelle viene solo dai servizi e dal codice di questo
modulo ed è verificato da `34-ia-verifica-risultati.md`.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Round-trip VOTable | scrivere una tabella di prova con unità e rileggerla | nomi, unità e valori identici | confronto con `astropy.io.votable` nel test |
| T2 | Cone search nota | cone search di raggio 10 arcsec attorno a una posizione presa dal tester | numero di righe coincidente con quanto ricalcolato dal test contro lo stesso servizio | doppia chiamata confrontata (test di rete separato) |
| T3 | Troncamento | eseguire una query con `max_rows` piccolo su un catalogo fitto | `ROW_LIMIT_EXCEEDED`/avviso e numero di righe = `max_rows` | test con servizio simulato |
| T4 | ADQL non valida | inviare ADQL malformata | rifiuto con messaggio, nessuna chiamata di rete inutile | test di unità con server simulato |
| T5 | Export CSV/ECSV/VOTable/FITS (D14-10) | esportare la stessa tabella nei quattro formati e rileggere con `read_table` del 13; andata e ritorno ECSV con unità (anche non riconosciute), UCD, valori mancanti e sistema delle posizioni (ICRS con epoca, FK5 con equinozio, colonne confermate dall'utente) | valori equivalenti nei quattro casi; unità identiche in ECSV, VOTable e FITS; CSV senza unità con `CSV_UNITS_NOT_SAVED`; versione "FITS Standard 4.0" e `A2WRITER` | ricalcolo con Astropy |
| T6 | Riproducibilità | eseguire una query, poi rilesare i parametri registrati | la seconda esecuzione usa gli stessi URL, parametri e restituisce lo stesso schema | confronto dei metadati registrati |
| T7 | SAMP | avviare l'hub, collegare un client simulato, inviare una tabella | il client riceve lo stesso contenuto | test con client simulato |
| T8 | SAMP selezione e puntamento (G3) | inviare al client simulato una selezione e un puntamento, poi riceverne uno | contenuti identici a quelli inviati, tipi supportati | test con client simulato |
| T9 | Ricerca e caricamento SSA (E4) | eseguire ricerca e caricamento su servizio SSA simulato | elenco candidati e spettro con assi, unità e provenienza corretti | confronto con il servizio simulato |
| T10 | Spettro SSA non valido (E4) | servire uno spettro senza assi/unità | `SSA_INVALID`, nessun dato mostrato come valido | test con servizio simulato |
| T11 | SIA (H23, D14-11) | ricerca SIA su un servizio simulato; `sia_calibration` su righe complete, senza equinozio (FK5), con sistema `ECL`, con dimensioni diverse dall'immagine; immagine FITS senza WCS servita dal servizio e caricata dall'11 con `calibration` | lista con URL, formato, campo e provenienza; intestazione con `CTYPE`, `CRPIX`, `CRVAL`, `CD`, `RADESYS` della riga; immagine con il WCS uguale ad `astropy.wcs` costruito nel test e `EXTERNAL_CALIBRATION_USED`; righe incomplete senza calibrazione con il motivo; dimensioni diverse → `WCS_MISSING`; immagine con WCS proprio → `EXTERNAL_CALIBRATION_IGNORED` | servizio simulato (test di rete separato) |
| T12 | SIA2 (H23) | ricerca SIA2 con banda e intervallo di tempo su un servizio simulato | parametri inviati secondo lo standard; tempo con scala dichiarata | servizio simulato |
| T13 | Puntatore Simbad (H17, D14-12) | `simbad_pointer` su una posizione con risposta simulata di due oggetti e magnitudini simulate in sistema Vega, AB e senza sistema; test di rete su Vega | restituito l'oggetto con più riferimenti, con fonte e data; tutte le magnitudini con banda, sistema (`Vega`, `AB`, `None` con `SIMBAD_SYSTEM_UNDECLARED`), errore e riferimento; seconda chiamata dalla cache | servizio simulato (più un test di rete) |
| T14 | Fotometria VizieR (H17) | `vizier_photometry` con risposta simulata | tabella con flusso, unità, frequenza o lunghezza d'onda e catalogo d'origine per ogni punto | servizio simulato |
| T15 | IDHA (H23) | leggere un file XML ben formato (scritto nel test) con `read_idha` | `IDHA_UNREADABLE` con la causa (nessuna documentazione pubblica, D14-9 punto 13), nessun dato | test di unità |
| T16 | XML malevolo (H23) | leggere un file IDHA con espansione di entità | `XML_UNSAFE`, nessun dato caricato | test di unità |
| T17 | Elenco dei server (H10, D14-4) | leggere l'elenco nostro; aggiungere e togliere un server personale; cone search con una voce TAP | ogni voce con ente, protocollo, URL, fonte e data di verifica; personali aggiunti e tolti; protocollo sbagliato → `SERVER_UNKNOWN` | test di unità |
| T18 | Registro VO (H10) | `search_registry` con parole chiave e tipo di servizio su un registro simulato; test di rete con il registro di default | elenco di servizi con URL e protocollo; parametri inviati secondo RegTAP; default `https://dc.g-vo.org/tap` | servizio simulato (più un test di rete) |
| T19 | DataLink (H8, D14-3) | `links` su un documento DataLink simulato con un descrittore di servizio; `call_service` | link con semantica, URL e content-type; chiamata con i parametri del descrittore | servizio simulato |
| T20 | Validazione ADQL minima | testi vuoti, senza `SELECT`, con virgolette o parentesi non chiuse, e validi | esiti e posizioni attesi; nessuna richiesta di rete | test di unità |
| T21 | Cache delle interrogazioni | stessa query due volte, poi con `refresh=True`, poi con il servizio spento | la seconda dalla cache (origine e data), la terza dal servizio, la quarta dalla cache con avviso | servizio simulato |

**Test di rete (decisione del proprietario del 2026-10-11):** i test con il
marcatore `network` si ripetono **al massimo 2 volte** e **solo** per un
errore di connessione o di timeout (eccezioni di connessione/timeout di
`requests` e della libreria standard, errori `NET_TIMEOUT` dei moduli, i
due messaggi fissi di `pyvo` "Connection failed" e "Request timed out"),
**mai** per un risultato sbagliato (un `AssertionError` non si ripete);
ogni ripetizione è scritta nel risultato del test (sezione "ripetizioni di
rete" e riepilogo finale di `pytest`). Implementata in `tests/conftest.py`
senza dipendenze nuove (`pytester` fa parte di `pytest`); test in
`tests/test_network_retries.py`.

## 13. Decisioni aperte

- **D14-1 — Libreria client VO: DECISA il 2026-10-04.** **`pyvo` per TAP e
  DataLink**; per **SAMP si valuta `astropy.samp` (da verificare)**.
  **Motivazione:** `pyvo` è lo stack VO di riferimento IVOA, un solo punto da
  fare da mock nei test (`61`) e riuso diretto da `33-ia-query-adql.md`;
  `astropy.samp` è già nell'ecosistema del progetto. **Le licenze si
  riverificano prima di approvare `14`.** Applicata in §8 qui sopra.
  **AGGIORNATA il 2026-10-10 (decisione del proprietario):** SAMP con
  **`pyvo.samp`**, non con `astropy.samp` (deprecato da astropy 8.0);
  licenze verificate: `pyvo` 1.9.1 BSD-3, `astroquery` 0.4.11 BSD.
- **D14-2 — Copertura SAMP (H14, G3): DECISA il 2026-10-04 (parte tecnica).**
  **Collegarsi a un hub SAMP già attivo se c'è, altrimenti avviarne uno
  proprio**; **primo perimetro: tabelle, selezioni e puntamenti**; **le
  immagini restano un'estensione prevista**. **Motivazione:** riuso dell'hub
  di sistema quando esiste (meno codice, interoperabilità con i client già in
  esecuzione) con ripiego controllato e testabile con client simulato (T7/T8);
  perimetro coerente con la riga G3 `inclusa (decisione del proprietario)` e
  con H14. La parte "includere la funzione" era già decisa (P11). Applicata in
  §3/§7/§10 qui sopra; l'interfaccia resta in `42-ui-pannello-cataloghi.md`.
  Eventuali dettagli residui su tipi di immagine e su H14 restano da leggere
  con AP5 — AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata
  il 2026-10-08 (esiti SAMP nelle righe G3/H14 di `03-parita-aladin.md`).
- **D14-3 — DataLink (H8): DECISA il 2026-10-09 (decisione del proprietario
  sulla checklist del livello 1).** DataLink **con descrittori di servizio**
  (anche ritagli e altre elaborazioni offerte dal servizio), con `pyvo`.
  **Motivazione (nostra):** lo standard IVOA DataLink descrive con i
  descrittori di servizio come chiamare queste elaborazioni lato server,
  senza codice specifico per ciascun archivio; versione dello standard **da
  verificare prima del codice**. **Esito della verifica (2026-10-10, P4):**
  la documentazione di `pyvo` 1.9.1 non dichiara una versione; il codice
  legge i campi del documento `{links}` di **DataLink 1.0** (`ID`,
  `access_url`, `service_def`, `error_message`, `semantics`, `description`,
  `content_type`, `content_length`) e riconosce i descrittori DataLink dal
  prefisso `ivo://ivoa.net/std/datalink` (quindi anche gli identificativi
  di DataLink 1.1); i campi aggiunti da DataLink 1.1 si leggono come
  colonne della tabella. I SODA si riconoscono da `ivo://ivoa.net/std/SODA#sync-1`.
- **D14-4 — Schede server (H10): DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1), CORRETTA il 2026-10-10
  (decisione del proprietario, regola d'oro n. 8).** **Elenco di server
  nostro**, costruito dai **servizi pubblici del VO**: CDS (Simbad, VizieR,
  XMatch, MocServer), ESA (archivio Gaia, ESASky), NASA (MAST, IRSA,
  HEASARC) e simili; ogni voce con protocollo (cone search, TAP, SIA, SSA),
  URL e ente, dichiarati; più i **server personali** salvati nelle
  preferenze e la ricerca nel registro VO. Nessuna copia del selettore di
  Aladin. Elenco esatto e URL **da verificare prima del codice** sui siti
  degli enti. **Esito della verifica (2026-10-10, P4):** otto voci, ognuna
  con l'URL letto sulla pagina ufficiale dell'ente (citata nella voce) e il
  servizio provato in linea: CDS SIMBAD TAP, CDS VizieR TAP (TAPVizieR), ESA
  archivio Gaia TAP, NASA/IPAC IRSA TAP, IRSA AllWISE cone search, IRSA
  immagini SIA 2, NASA/GSFC HEASARC TAP, NASA/STScI MAST CAOM TAP.
  **Escluse, da verificare:** ESASky TAP (servizio in linea, ma URL non
  trovato sulle pagine ufficiali ESA), MAST CAOM SIA 2 (URL ufficiale, ma
  nessuna risposta in 60 s il 2026-10-10), cone search di SIMBAD (in linea,
  non documentato sulle pagine del CDS); XMatch e MocServer (il MocServer
  serve anche all'albero delle collezioni del 13, D13-18) non sono servizi
  dei protocolli dell'elenco (cone search, TAP, SIA, SSA) e restano ai moduli
  15 e 16; nessun servizio SSA generale trovato (quelli di HEASARC chiedono
  il nome di una tabella). **Esclusioni confermate dal proprietario il
  2026-10-11, da ricontrollare in futuro** (a ogni revisione dell'elenco):
  ESASky TAP — URL non pubblicato sulle pagine ufficiali dell'ESA, quindi
  senza una fonte ufficiale da citare nella voce; MAST CAOM SIA 2 — URL
  ufficiale, ma nessuna risposta entro 60 s il 2026-10-10; cone search di
  SIMBAD — in linea, ma non documentato sulle pagine del CDS (SIMBAD resta
  raggiungibile con il suo TAP); SSA generale — nessun servizio SSA che
  risponda senza il nome di una tabella. Un servizio escluso si può sempre
  aggiungere come server personale.
- **D14-5 — Limiti di riga predefiniti: DECISA il 2026-10-10 (decisione
  del proprietario).** `max_rows` di default **100 000**, configurabile fino
  al tetto del `13` (1 000 000); superamento sempre dichiarato con
  `ROW_LIMIT_EXCEEDED`. Applicata in §3, §7, §10.
- **D14-6 — Spettri SSA (E4): DECISA il 2026-10-09 (decisione del proprietario
  sulla checklist del livello 1).** inclusione decisa il 2026-10-04; parte
  tecnica: **SSA 1.1 con `pyvo.dal.SSAService`**, spettri in VOTable e FITS.
  L'analisi resta in `21-analisi-spettroscopia.md`.
- **D14-7 — Sistema di plugin (H14): DECISA il 2026-10-09 (decisione del
  proprietario).** **Nessun sistema di plugin nel livello 1**; le estensioni
  passano dall'API Python di `24-analisi-pipeline-riproducibili.md`. La parte
  "plugin" di H14 è spostata nel 24 (anche in `03-parita-aladin.md`).
- **D14-8 — Formato IDHA (H23): DECISA il 2026-10-09 (decisione del
  proprietario).** Come D13-7: lettore nel modulo con **`defusedxml`**,
  testato su file di esempio del CDS; senza documentazione o esempi, solo
  errore (`IDHA_UNREADABLE`). **Da verificare prima del codice:** licenza di
  `defusedxml`, disponibilità di documentazione ed esempi IDHA. **Esito
  (2026-10-10):** `defusedxml` 0.7.1, licenza PSF; nessuna documentazione
  pubblica IDHA trovata → solo `IDHA_UNREADABLE` (D14-9 punto 13).
- **D14-9 — Decisioni del proprietario del 2026-10-10 sulla divisione in
  parti:** (1) SAMP con `pyvo.samp` (D14-1); (2) raggio del puntatore Simbad
  sempre esplicito, default deciso nel 41, nessun valore dal manuale di
  Aladin; (3) D14-5 decisa; (4) `validate_adql` con soli controlli minimi;
  (5) un solo lettore VOTable, `read_table` del 13; (6) `catalog` della cone
  search = voce dell'elenco o URL SCS, identificativi VizieR via TAP in P6
  del 13; (7) una sola cache delle interrogazioni, prima la cache,
  `refresh=True`; (8) TAP sincrona di default, asincrona su richiesta con
  attesa massima 600 s configurabile, suggerimento dell'asincrona; (9) file
  esportati con versione di AstroTwo e del formato, CSV con commenti `#`;
  (10) SAMP solo `table.load.votable`, `table.select.rowList`,
  `coord.pointAt.sky`, profilo web disattivato di default; (11) spettri SSA
  in VOTable Spectrum DM e FITS tabellari con UCD/`utype`, niente
  `specutils`; (12) solo servizi pubblici senza autenticazione nel livello
  1; (13) IDHA: solo `IDHA_UNREADABLE`, T15 riscritto; (14) colonna DataLink
  da descrittore di servizio o content-type DataLink; (15) Simbad a pari
  citazioni: il più vicino, dichiarato; (16) §11 nel 32. Applicate in §3,
  §4, §7, §8, §10–§12.
- **D14-10 — Unità delle colonne nel CSV esportato: DECISA il 2026-10-11
  (decisione del proprietario).** Esportazione in **ECSV** di `astropy`
  quando la tabella ha unità; il 13 legge l'ECSV (riconosciuto dalla prima
  riga `# %ECSV`), con test di andata e ritorno delle unità; il CSV semplice
  resta disponibile con l'avviso `CSV_UNITS_NOT_SAVED`. T5 completo.
  Applicata in §3, §6, §7, §10, §12. (Aperta il 2026-10-10: opzioni riga
  di commento, ECSV, nessuna unità; raccomandazione ECSV.)
- **D14-11 — Calibrazione della lista SIA usata dall'11: DECISA il
  2026-10-11 (decisione del proprietario, con autorizzazione a modificare
  l'11).** Il 14 costruisce l'intestazione WCS dalle colonne `VOX:WCS_*` di
  SIA 1 (`sia_calibration`); l'11 riceve un parametro facoltativo con la
  calibrazione esterna (`calibration` di `load_image`), dichiarata nel
  risultato. Seconda metà di T11 completa. Applicata in §3, §7, §12 e
  nell'11. (Aperta il 2026-10-10: opzioni intestazione da `VOX:WCS_*` +
  parametro nell'11, solo SIA 1 su richiesta, nessun uso; raccomandazione
  la prima.)
- **D14-12 — Magnitudine dell'oggetto del puntatore Simbad: DECISA il
  2026-10-11 (decisione del proprietario).** Il puntatore restituisce
  **tutte le magnitudini disponibili**, ognuna con nome della banda e
  sistema dichiarati (§3). Applicata in §3, §6, §7, §10, §12. (Aperta il
  2026-10-10: opzioni tutte le bande, banda scelta dall'utente, banda
  fissa; raccomandazione tutte le bande.)

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). |
| 2026-10-04 | agente di sviluppo | **G3 (SAMP) ed E4 (SSA) incluse per decisione del proprietario:** SAMP = invio/ricezione di tabelle, selezioni e puntamenti da e verso altri programmi, interfaccia in `42-ui-pannello-cataloghi.md` (§3/§7); SSA = ricerca e caricamento di spettri dai servizi VO, analisi in `21-analisi-spettroscopia.md` (§3/§7); nuovi errori `SAMP_UNSUPPORTED_TYPE`, `NET_TIMEOUT`/`SSA_NO_RESULT`/`SSA_INVALID` (§10); strumenti IA `ssa_search`/`ssa_load` (§11); test T8–T10 (§12); D14-2 perimetro deciso e nuova D14-6 (§13). Righe G3 ed E4 in `03-parita-aladin.md` passate a `inclusa (decisione del proprietario)`. |
| 2026-10-04 | agente di sviluppo | **D14-2 RIAPERTA (solo scelta tecnica):** restano due scelte non decise — (a) tipi di messaggio SAMP per primo (fuori dal perimetro: immagini, estensione coordinate), (b) hub interno su libreria consolidata vs libreria esterna; l'inclusione della funzione resta decisa. |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario: D14-1 e D14-2 (parte tecnica) passate da aperte a decise.** D14-1: `pyvo` per TAP e DataLink, `astropy.samp` da valutare per SAMP, licenze da riverificare prima dell'approvazione di `14` (§8). D14-2: collegamento a un hub SAMP già attivo se presente, altrimenti avvio del proprio; primo perimetro tabelle/selezioni/puntamenti; immagini come estensione prevista (§3/§7/§10). Restano aperte D14-3, D14-4, D14-5, D14-6. Decisioni riportate in `decisioni-aperte.md`. |
| 2026-10-04 | agente di sviluppo | Riferimento AP5 aggiornato in §13 (D14-2): le sezioni ancora da leggere sono **5.7.3–8** (prima indicate 5.9–8), in linea con l'esito parziale di AP5 in `03-parita-aladin.md` (lette 1–5.7.2 e indice completo, ed. febbraio 2021). Nessun altro testo cambia. |
| 2026-10-08 | Claude Code | §13: titolo di D14-6 rinominato in "inclusione decisa; parte tecnica aperta" (contenuto invariato); riferimento AP5 in D14-2 scritto in forma uniforme ("AP5 decisa; lettura delle sezioni 5.7.3–8 ancora da fare", manuale ed. giugno 2022). |
| 2026-10-08 | Claude Code | §13 (D14-2): riferimento AP5 aggiornato a "AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) ancora da fare". |
| 2026-10-08 | Claude Code | §13 (D14-2): riferimento AP5 aggiornato a lettura completata, con rimando agli esiti SAMP in `03-parita-aladin.md` (G3/H14: SAMP trasporta cataloghi, immagini e spettri). Nessuna decisione cambiata. |
| 2026-10-08 | Claude Code | §5: aggiunti a "Usato da" i moduli `19-core-dati-planetari.md` (scritti il 2026-10-08, stato bozza). Nessun altro testo cambia. |
| 2026-10-09 | Claude Code | **D19-3 applicata (decisione del proprietario del 2026-10-08):** campo `body` obbligatorio nei metadati di tabelle, spettri e risultati di query (§6, §9, §10); per i dati astronomici `celestial`, ricavato dal sistema di coordinate, mai assunto; errori `BODY_UNKNOWN` e, per le sovrapposizioni, `BODY_MISMATCH` secondo D19-4 (forzabile solo con opzione esplicita citata nel risultato). |
| 2026-10-09 | Claude Code | **D14-3, D14-4, D14-6 DECISE** (checklist del livello 1): DataLink con descrittori di servizio via `pyvo` (versione da verificare); schede del selettore di Aladin più server personali; SSA 1.1 con `pyvo.dal.SSAService`. §3 aggiornato. |
| 2026-10-09 | Claude Code | **Completamento con gli esiti di AP5** (decisione del proprietario del 2026-10-09): §3, §6, §7, §8, §10, §12 per H23 (SIA e SIA2 con `pyvo`), H17 (puntatori Simbad e VizieR, parte VO; SED nel 20), H19 (SAMP come equivalente di VOApp per i programmi non Python) e H14 (sistema di plugin). Nuove decisioni del Gruppo 2: **D14-7** (sistema di plugin) e **D14-8** (formato IDHA). Il modulo resta in `bozza`. |
| 2026-10-09 | Claude Code | **D14-7 DECISA** (decisione del proprietario): nessun sistema di plugin nel livello 1, estensioni tramite l'API Python del 24 (parte "plugin" di H14 spostata nel 24). **D14-8 DECISA**: lettore IDHA con `defusedxml`, altrimenti solo errore. §3, §8, §10 (`IDHA_UNREADABLE`, `XML_UNSAFE`), §12, §13 aggiornati. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** (regola del proprietario del 2026-10-09): nessuna decisione aperta nei Gruppi 1 e 2. |
| 2026-10-09 | Claude Code | **Collegamento alla cache comune `04-cache.md`** (approvato il 2026-10-09; decisione CA4 del proprietario, autorizzazione esplicita a modificare il file approvato): §3, §5, §7, §8 — tolta `QueryCache`, risultati nella cache comune `SharedCache`, timeout comuni 10 s / 60 s. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Regola d'oro n. 8** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): D14-4 corretta — elenco di server nostro dai servizi pubblici del VO (CDS, ESA, NASA/MAST e simili) più server personali, al posto del selettore di Aladin (§3, §13); D14-3 e §8 (servizio fotometrico di VizieR) con motivazione nostra al posto di "come in Aladin" / "usato da Aladin". Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Decisioni del proprietario sulla divisione in parti (D14-9)** (autorizzazione esplicita a modificare il file approvato): sette parti P1–P7 (§3); SAMP con `pyvo.samp` (D14-1 aggiornata, §8); raggio Simbad esplicito dal 41; D14-5 decisa (100 000 righe, fino al tetto del 13); `validate_adql` minima; un solo lettore (`read_table` del 13); `catalog` della cone search; una sola cache delle interrogazioni (prima la cache, `refresh`); TAP sincrona/asincrona con attesa di 600 s; provenienza dei file esportati; tre messaggi SAMP e profilo web disattivato; formati degli spettri SSA; solo servizi pubblici; IDHA solo errore (T15 riscritto, riga H23 di `03`); colonna DataLink; Simbad a pari citazioni; §11 nel 32. §7 riscritto con le firme; nuovi errori `FILE_EXISTS`, `MAX_ROWS_INVALID`, `AUTH_REQUIRED`, `SERVICE_ERROR`, `SERVER_UNKNOWN`, avviso `FROM_CACHE` (§10); nuovi T17–T21 (§12). Nuova decisione aperta **D14-10** (unità nel CSV, Gruppo 3). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P1 scritta** (`src/astrotwo/core/vo_protocols.py`: `read_votable`, `write_votable`, `export_table`, `VoProtocolsError`; test T1, T5 e casi d'errore in `tests/core/test_vo_protocols.py`): provenienza con le stesse chiavi nei tre formati (`A2VERS`, `A2FORMAT`, `A2ORIGIN`, `A2DATE`, `A2EXPORT`, `A2HIST`, `A2BODY`, `A2POS`: `INFO` nel VOTable 1.4, parole chiave e `HISTORY` nel FITS, righe `#` nel CSV); UCD nel FITS come `TUCDn`; testi a lunghezza variabile resi a larghezza fissa nel FITS; scrittore VOTable condiviso con `save_subset` del 13. Unità nel CSV ferme su D14-10. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P2 scritta** (`RequestRecord`, `VoResult`, `download_table`, `DEFAULT_MAX_ROWS`; test T6, T21 e casi d'errore con un servizio HTTP simulato locale): sessione `requests` con i timeout comuni di `04` e `User-Agent` di AstroTwo; prima la cache, `refresh=True`, copia in cache dichiarata (`FROM_CACHE`) se la rete non risponde; in cache solo le risposte lette con successo (tabella SQLite `query_results` del modulo 14: protocollo, URL, parametri, byte della risposta); HTTP 401/403 → `AUTH_REQUIRED`, altri errori HTTP → `SERVICE_ERROR`. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P3 scritta** (`cone_search`, `tap_query` sincrona e asincrona, `validate_adql`, `AdqlCheck`, `DEFAULT_ASYNC_TIMEOUT`; test T3, T4, T20, cone search e TAP asincrona su servizi simulati, T2 di rete sul cone search pubblico di Simbad): parametri costruiti con `pyvo` (`SCSQuery`, `TAPQuery`, `AsyncTAPJob`), stato della risposta letto da `pyvo` (`QUERY_STATUS`, `OVERFLOW`; per SCS 1.03 anche `INFO` `Error`); servizio che rifiuta la query TAP → `ADQL_INVALID` con il messaggio del servizio (HTTP 5xx → `SERVICE_ERROR`); suggerimento dell'asincrona su timeout di lettura o messaggio di durata; lavoro asincrono interrotto (`ABORT`) oltre l'attesa massima ed eliminato alla fine; voci dell'elenco dei server come `catalog` in P4. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P4 scritta** (`ServerRegistry`, `ServerEntry`, `BUILTIN_SERVERS`, `PROTOCOLS`, `RegistrySearch`, `DataLinkClient`, `DataLinks`, `ServiceDescriptor`, `ServiceParam`, `DataProduct`; `VoResult.descriptors`; parametro `servers` di `cone_search` e `tap_query`; test T17, T18, T19 su servizi simulati e T18 di rete): verifiche DataLink e URL dei server (esiti in D14-3 e D14-4); ricerca nel registro con l'ADQL RegTAP costruito da `pyvo` ed eseguito con `tap_query` (stessa cache e stesso registro); `call_service` con i parametri riferiti a colonne, poi quelli dati, poi i valori fissi, vuoti non inviati (testo originale dei valori letto con `defusedxml`, perché `astropy` rende zeri un `value=""` numerico). **Da verificare:** il registro di default di `pyvo` (`http://reg.g-vo.org/tap`) risponde "Request Denied" (HTML, HTTP 403) alla query RegTAP da questa rete e non ha HTTPS valido; il test di rete usa `https://dc.g-vo.org/tap`. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P5 scritta** (`sia_search` SIA 1 e SIA 2, `read_idha`, `ssa_search`, `ssa_load`, `Spectrum`; test T9–T12, T15, T16, `SIA_NO_RESULT`, `SIA_INVALID`, `SSA_NO_RESULT`): parametri costruiti con `pyvo`; SIA 1 con `SIZE` = 2 × raggio (lato del quadrato che contiene il cerchio), SSA con `SIZE` = diametro = 2 × raggio; SIA 2 con banda convertita in metri e tempo convertito in **UTC** prima dell'MJD (SIA 2.0 e DALI: MJD sulla scala UTC; verificato sul testo della raccomandazione), parametri ripetuti (es. `POS`) inviati tutti; spettri: VOTable dagli `utype` dello Spectrum DM (`…Data.SpectralAxis.Value`, `…Data.FluxAxis.Value`, `…Accuracy.StatError`), FITS anche dagli UCD (`em.wl`/`em.freq`/`em.energy`/`em.wavenumber`, `phot.flux*`), una sola colonna per asse e unità obbligatoria, FITS con una riga di colonne vettoriali svolto in una riga per campione; corpo dello spettro = corpo della lista dei candidati, `BODY_UNKNOWN` se caricato da solo URL. Nel 13 si conservano `utype` (VOTable) e `TUCDn`/`TUTYPn` (FITS). Nuova decisione aperta **D14-11** (calibrazione della lista nell'11; seconda metà di T11 ferma). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P6 scritta** (`simbad_pointer`, `SimbadPointer`, `SimbadObject`, `vizier_photometry`, `VIZIER_PHOTOMETRY_URL`; test T13, T14, pari citazioni, nessun oggetto, test di rete su Vega): verifiche in §3 (servizio fotometrico) e campo `nbref`; SIMBAD interrogato con `astroquery` (`query_region` con `otype` e `nbref`) tramite la sessione con i timeout comuni del 10 (`_simbad_with_timeouts`, unico punto con il campo interno di astroquery), risposta salvata nella cache del 14 come VOTable e letta con `read_table`; coordinate ICRS J2000 dichiarate come nel 10; distanza con `astropy.coordinates.angular_separation`; a pari citazioni il più vicino (`SIMBAD_TIE`), a pari distanza l'identificativo in ordine alfabetico; senza `nbref` il più vicino (`SIMBAD_NBREF_MISSING`); nessun oggetto → `SIMBAD_NO_OBJECT`. Nuova decisione aperta **D14-12** (magnitudine del puntatore). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P7 scritta — modulo 14 completo tranne i pezzi fermi su D14-10, D14-11, D14-12** (`SampHub`, `SampClient`, `SampSelection`, `SampSendResult`, `SAMP_MTYPES`; test T7, T8, hub proprio ed errori, con un hub locale `pyvo.samp` nella cartella home temporanea dei test): verifica dell'hub locale nei test riuscita; collegamento all'hub attivo (file di blocco SAMP), altrimenti hub proprio con profilo web disattivato; invio a uno o a tutti i programmi iscritti al tipo (`SAMP_NO_PEER` se nessuno); tabelle inviate come VOTable temporaneo con provenienza (P1), ricevute con `read_votable` (file) o `download_table` (URL); selezioni con indici di riga da 0 come nel messaggio SAMP; puntamenti in gradi ICRS; un errore nella funzione di ricezione torna al mittente come risposta d'errore SAMP. Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **D14-10 decisa e applicata; versione FITS** (decisioni del proprietario del 2026-10-11, autorizzazione esplicita a modificare il file approvato): nuovo formato di esportazione `ecsv` (ECSV di `astropy`, unità, UCD e provenienza nell'intestazione), CSV semplice con l'avviso `CSV_UNITS_NOT_SAVED`; `export_table` restituisce `ExportResult`; versione del formato FITS = "FITS Standard 4.0" e, per tutti i formati, versione di `astropy` in `A2WRITER`; T5 completo con l'andata e ritorno ECSV (§3, §6, §7, §10, §12, §13). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **D14-11 decisa e applicata** (decisione del proprietario del 2026-10-11, autorizzazione esplicita a modificare i file approvati 11 e 14): `sia_calibration` / `SiaCalibration` (intestazione WCS dalle colonne `VOX:WCS_*` di SIA 1, verificate sulla raccomandazione SIA 1.0 §4.2; ICRS, FK5, FK4, GAL tradotti, ECL e SGAL no; equinozio mai assunto; validazione con il modulo 10); seconda metà di T11 completa con l'immagine caricata dall'11 (§3, §7, §12, §13). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **D14-12 decisa e applicata** (decisione del proprietario del 2026-10-11, autorizzazione esplicita a modificare il file approvato): `simbad_pointer` restituisce tutte le magnitudini di SIMBAD (`SimbadMagnitude`, tabelle `flux` e `filter` dal TAP di SIMBAD con `tap_query`, `magnitudes_request`), con banda e sistema dichiarati; verificato sul `TAP_SCHEMA` di SIMBAD che `system` vale A = AB, V = Vega ed è vuoto per una parte delle misure (sistema `None`, avviso `SIMBAD_SYSTEM_UNDECLARED`; nuovi anche `SIMBAD_SYSTEM_UNKNOWN`, `SIMBAD_NO_MAGNITUDE`); T13 aggiornato (§3, §6, §7, §10, §12, §13). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **Con D13-17** (13): `download_table` passa al lettore del 13 la funzione di rete per i dati in un `LINK` ASTRORES (stessa cache e stessi timeout, `href` relativo risolto sull'URL scaricato). Nessun altro comportamento cambia. Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **Con D13-18** (13; decisione del proprietario del 2026-10-11, autorizzazione esplicita a modificare il file approvato): `vizier_collections`, `MocServerRecords`, `MOCSERVER_URL` — collezioni dal MocServer del CDS (JSON, protocollo `mocserver`, cache e registro comuni), verificato in linea il 2026-10-11 (§3, §7, §8, D14-4). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **Verifiche chiuse dal proprietario** (2026-10-11, autorizzazione esplicita a modificare il file approvato): registro VO di default `DEFAULT_REGISTRY_URL` = `https://dc.g-vo.org/tap` (HTTPS con certificato valido, verificato), configurabile con `registry_url`, nessun default senza HTTPS valido (§3, §7; test T18 sul default); server esclusi (ESASky TAP, MAST CAOM SIA 2, cone search di SIMBAD, SSA generale) confermati fuori, con il motivo, da ricontrollare in futuro (D14-4). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **Scelte minori del 2026-10-11 cambiate dal proprietario** (autorizzazione esplicita a modificare il file approvato): l'esportazione ECSV scrive il sistema delle posizioni nei metadati YAML `A2POSITIONS` (riletti dal 13, T5 esteso); regola delle ripetizioni dei test di rete (solo connessione o timeout, al massimo 2, dichiarate nel risultato). Stato `approvato` invariato. |
