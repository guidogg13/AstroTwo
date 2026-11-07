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
  **Commenti e annullamento (sprint B3, 2026-11-06):** i commenti ADQL
  (`--` fuori dalle virgolette fino a fine riga, come in ADQL 2.1) si
  **tolgono prima dell'invio** (`adql_to_send`): provati il 2026-11-06,
  l'archivio Gaia dell'ESA (HTTP 500), IRSA (`BAD_REQUEST`) e HEASARC
  ("Unsupported syntax") rifiutano una query con una riga di commento, MAST
  la accetta. Il testo scritto resta negli argomenti registrati (`adql`),
  quello inviato nei parametri (`QUERY`); le righe rimaste vuote si
  tolgono, nient'altro cambia. In asincrona `tap_query` accetta `cancel`
  (funzione senza argomenti che dice se l'utente ha annullato): controllata
  almeno ogni 0,25 s durante l'attesa, interrompe il lavoro (`ABORT`), lo
  elimina e dà `QUERY_CANCELLED`; in sincrona non si usa (la richiesta HTTP
  non si interrompe: chi chiama scarta la risposta).
- **`validate_adql` (D14-9):** solo **controlli minimi** lato client —
  testo non vuoto, inizia con `SELECT` (maiuscole o minuscole), virgolette
  semplici e doppie chiuse, parentesi bilanciate (fuori dalle virgolette);
  altrimenti `ADQL_INVALID` con la posizione, senza chiamate di rete. La
  validazione vera è quella del servizio, che prevale. Dal 2026-11-06
  (sprint B3) i commenti `--` fuori dalle virgolette contano come spazio
  (anche prima di `SELECT`): un apostrofo in un commento non è una
  virgoletta aperta; le posizioni restano quelle del testo scritto.
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
  selezione") **vive in `40-ui-finestra-principale.md` §3.12** (menu,
  stato, preferenza, thread, ricezione), con i menu contestuali di
  `41-ui-visualizzatore-cielo.md` e `42-ui-pannello-cataloghi.md` e i
  comandi `samp.*` del `05` (sprint B1, decisioni del proprietario del
  2026-11-05, D40-8); l'interfaccia chiama `SampHub`.
  **Aggiunte per l'interfaccia (sprint B1, 2026-11-05):** (1) ricezione di
  una tabella **senza leggerla** (`on_table_reference`: URL, `table-id`,
  nome e mittente), così l'interfaccia ne fa una copia locale con
  `save_votable` e la apre con `catalog.open_file` del `05` (stessi
  controlli dei file locali del 13); (2) `save_votable(url, path)`: copia
  un VOTable da un URL `file:` o lo scarica da `http(s):` con i timeout del
  04, senza leggerlo e senza cache (sono dati di un altro programma, non di
  un servizio); altri schemi → `SAMP_TABLE_FETCH_FAILED`; (3)
  `client_name(id)`: nome dichiarato (`samp.name`) di un client; (4)
  **eventi dell'hub** (`on_hub_event`): AstroTwo si iscrive anche a
  `samp.hub.event.register`, `samp.hub.event.unregister`,
  `samp.hub.event.metadata` e `samp.hub.event.shutdown`, avvisi
  amministrativi dell'hub usati **solo** per aggiornare l'elenco dei client
  e lo stato del collegamento: non portano dati e non eseguono nulla; (5)
  `SampSendResult.params`: parametri effettivamente inviati (per il
  risultato del comando e per i test). I messaggi di dati restano solo i
  tre tipi di `SAMP_MTYPES`; (6) **niente `client.env.get`:** `pyvo.samp`
  iscrive di default ogni client a `client.env.get`, che restituisce le
  variabili d'ambiente del processo a qualunque programma le chieda;
  AstroTwo toglie la voce **prima** di registrarsi all'hub (sottoclasse di
  `SAMPIntegratedClient` con la stessa `connect` più
  `unbind_receive_call("client.env.get", declare=False)`, API pubblica di
  `pyvo`), così non è mai iscritto. Resta solo `samp.app.ping` (risposta
  vuota, nessun dato), che gli hub usano per sapere se un client è vivo.
  Iscrizioni di AstroTwo = i tre tipi + i quattro avvisi dell'hub +
  `samp.app.ping` (verificato in T22).
  **Correzioni dalla prova con TOPCAT vero (sprint B1b, 2026-11-05;
  TOPCAT 4.10-8, hub JSAMP):** (7) **invio con risposta:** ogni messaggio
  si manda con una **chiamata sincrona** (`callAndWait` dell'hub) a ogni
  destinatario, in parallelo, con un tempo massimo di risposta per
  destinatario (`timeout`, quello del `40`: 10 s; **60 s per
  `table.load.votable`** dal 2026-11-05, D40-9 (7) decisa dal proprietario
  nello sprint B2, costante `SAMP_TABLE_REPLY_TIMEOUT`, default di
  `send_table`); `SampSendResult.recipients`
  = destinatari che hanno risposto `samp.ok`, `SampSendResult.failures` =
  uno `SampFailure` (`id`, `reason` = `rejected` o `no_reply`, `detail` =
  testo del destinatario o dell'hub, testo esterno) per ogni altro; nessun
  destinatario riuscito → `SAMP_NO_PEER` (`rejected` o `no_reply`, del
  primo destinatario fallito; per `table.load.votable` la sotto-voce è
  `no_reply_table`, il cui testo dice che **la tabella potrebbe arrivare
  comunque**: TOPCAT risponde a caricamento finito; sprint B2). **Motivo:** con la sola notifica i rifiuti
  erano muti (TOPCAT rifiuta un `table.load.votable` con un `table-id` già
  ricevuto: "Duplicate table-id … has already been received"; e una
  selezione per una tabella che non ha: "No table with table-id=… is
  loaded"), e una selezione mandata subito dopo la sua tabella arrivava
  **prima** che TOPCAT l'avesse caricata ed era scartata. TOPCAT risponde
  alla chiamata `table.load.votable` solo a caricamento finito, così la
  selezione che segue la trova (verificato con TOPCAT vero il
  2026-11-05). (8) **`clients()` esclude l'hub** con l'identificativo che
  l'hub stesso dà alla registrazione (`samp.hub-id`): `cli#hub` per l'hub
  di `pyvo`, `hub` per quello di TOPCAT (JSAMP); prima si escludeva solo
  `cli#hub` e con TOPCAT l'hub contava come un programma. (9) **iscrizioni
  dichiarate una volta sola:** i gestori si legano **prima** della
  registrazione e `register()` dichiara iscrizioni e metadati in un'unica
  volta; prima ogni legame ridichiarava l'elenco (12 avvisi
  `samp.hub.event.subscriptions` a tutti i client a ogni collegamento, che
  TOPCAT ridisegna ogni volta). La registrazione di AstroTwo resta una sola
  per tutto il collegamento (nessuna uscita e rientro durante gli invii,
  verificato con TOPCAT vero).
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
  `SERVICE_ERROR`. **Codifica delle risposte (verifica del 2026-10-12):** il
  MocServer dichiara le risposte JSON in **ISO-8859-1**
  (`Content-Type: application/json;charset=ISO-8859-1`; alcuni titoli
  contengono ad esempio "µm" in un solo byte, non UTF-8); le risposte si
  leggono **secondo la codifica dichiarata**, con la costante
  `MOCSERVER_CHARSET` di questo modulo, usata anche dal 12 (collezioni HiPS)
  e dal 16 (`query_mocserver`); mai in UTF-8 per presunzione. Il MocServer non entra nell'elenco dei server (che
  copre cone search, TAP, SIA, SSA): l'URL è una costante del modulo,
  come quello del servizio fotometrico di VizieR. L'albero si costruisce
  nel 13 (`collection_tree`).
- **Servizio CDS XMatch (per il modulo 15, decisione del 2026-10-11):**
  `cds_xmatch` invia due tabelle (colonne `idx`, `ra`, `dec` in gradi ICRS,
  preparate dal 15) con `astroquery.xmatch` all'URL **HTTPS**
  `XMATCH_URL` = `https://cdsxmatch.cds.unistra.fr/xmatch/api/v1/sync`
  (il default di `astroquery` è `http://`), con i **timeout comuni di
  `04`**, la **cache di `astroquery` disattivata** e la risposta (VOTable)
  nella **cache del 14** (chiave con l'impronta SHA-256 delle tabelle
  caricate), letta con `read_table` del 13; `selection` `best` o `all`;
  limiti verificati sulla documentazione delle chiamate API il 2026-10-11:
  `distMaxArcsec` ≤ 180 (`MAX_SEP_INVALID`), tabelle caricate ≤ 100 MB
  (`TABLE_TOO_LARGE`); servizio che rifiuta → `SERVICE_ERROR`.
  **Nessun mirror** (sprint B4, verificato il 2026-11-07: nessuna copia di
  XMatch fuori da Strasburgo nell'elenco dei mirror del CDS né nel registro
  VO): con il servizio giù resta l'errore `CROSSMATCH_SERVICE_FAILED` del
  `05`, che propone il metodo locale (testo controllato nello sprint B4).
- **Ripiego sui mirror dei servizi del CDS (sprint B4, regole decise dal
  proprietario il 2026-11-07, D14-14; modello: survey HiPS del `12`, sprint
  10b, e nomi del `10` §7, sprint 10a).** A fine ottobre 2026 il CDS di
  Strasburgo è stato irraggiungibile per giorni, ed è ancora instabile (il
  2026-11-07 tutti gli host `*.cds.unistra.fr` non rispondono in 15 s). Da
  questo sprint un servizio del CDS che ha una **copia verificata** ha un
  **elenco ordinato di server** e passa al successivo quando quello in uso
  non risponde.
  - **Quando si passa al server successivo (D14-14 a):** solo per timeout o
    errore di connessione (`NET_TIMEOUT`, tranne `async_deadline`: una query
    asincrona lunga non è un server giù), HTTP **5xx** o **429**
    (`SERVICE_ERROR` con `status`, anche quando il corpo è un VOTable
    d'errore) o **risposta non valida** (una risposta 2xx che non è un
    VOTable: `VOTABLE_INVALID` `unreadable_response`; una risposta HTTP di
    errore senza VOTable con stato 5xx o 429). **Mai** per un 404 o un altro
    4xx (`SERVICE_ERROR` con stato 4xx, `AUTH_REQUIRED`), **mai** per un
    errore dell'ADQL (`ADQL_INVALID`, anche quando è il servizio a
    rifiutarla), **mai** per "nessun risultato" (una risposta valida senza
    righe è un risultato), né per `QUERY_CANCELLED`, `MAX_ROWS_INVALID` e gli
    altri errori di chi chiama. Funzione pubblica **`is_failover_error(exc)`**
    (usata anche dal `13` per il ripiego di Gaia DR3 e 2MASS). Per le
    richieste di `astroquery` (regione del puntatore): errori di `requests`
    (connessione, timeout) e `DALServiceError` senza codice HTTP o con codice
    5xx/429; un `DALServiceError` con codice 4xx non fa cambiare server.
  - **Solo mirror verificati (D14-14 b):** con richieste reali, URL, data e
    fonte ufficiale scritti nella tabella sotto; un mirror non verificabile
    oggi non entra.
  - **Ordine (D14-14 c):** il principale (CDS) resta primo; tra i mirror
    prima quelli fuori da Strasburgo (oggi l'unico mirror è a Harvard).
  - **Avviso `SERVICE_MIRROR_FALLBACK` (D14-14 d):** `service` (nome del
    servizio, es. `SIMBAD`), `primary` (URL del principale), `mirror` (URL
    del server che ha risposto), `reason` = causa (`network`, `http_status`
    con `status`, `invalid_response`; stessa forma di
    `HIPS_MIRROR_FALLBACK` e di `NAME_RESOLVER_FALLBACK`): **una sola volta
    per servizio e per sessione dell'app** (processo; lo stato vive nel
    modulo, `reset_mirror_state()` lo azzera per i test). La **provenienza**
    di ogni risultato riporta sempre il server che ha davvero risposto:
    `RequestRecord.url` (e quindi `CatalogTable.origin`) è l'URL del mirror;
    `SimbadPointer.source` dice "SIMBAD (mirror di Harvard)".
  - **Servizio in uso per la sessione (D14-15 (1), da confermare):** dopo
    un cambio il servizio **resta sul mirror per il resto della sessione**
    (come i survey del `12`, D12-9): le richieste successive vanno subito al
    mirror, senza aspettare di nuovo il timeout del principale; il puntatore
    SIMBAD (regione e magnitudini) e il catalogo `simbad` condividono lo
    stesso stato (servizio `simbad`). **`refresh=True` riparte dal
    principale** (e, se risponde, il servizio torna sul principale).
  - **Cache (D14-15 (2), da confermare):** chiave di ogni risposta TAP =
    URL del server che ha risposto (come prima: nessuna chiave nuova).
    Senza `refresh` si cerca prima nella cache di **tutti** i server
    dell'elenco, nell'ordine (una risposta già scaricata da un mirror vale
    anche quando il principale torna); poi la rete, server per server,
    **senza** usare copie vecchie; solo se nessun server risponde si usa la
    prima copia in cache nell'ordine dei server (principale prima),
    dichiarata con `FROM_CACHE` (`network_cached`). La regione del puntatore SIMBAD ha
    già una chiave indipendente dal server (`simbad:query_region`).
  - **Ambito (D14-15 (3), da confermare):** il ripiego vale quando il
    servizio è indicato con la **voce dell'elenco** (`cds-simbad-tap`), come
    fanno il puntatore, le magnitudini e il catalogo `simbad` del `13`; un
    **URL scritto** (query ADQL del `05` con l'URL nel comando registrato,
    sprint B3) va solo a quell'URL, così la riesecuzione rifà la stessa
    richiesta.
  - **Se cadono tutti (D14-14 e):** con più di un server, `NET_TIMEOUT`
    con `reason = service_servers`: servizio, **numero dei server provati**,
    i loro URL e l'ultimo errore (messaggio annidato); con un solo server
    (nessun mirror) l'errore di prima.

  **Mirror verificati il 2026-11-07** (fonte dell'elenco dei mirror VizieR:
  pagina del mirror ufficiale `https://vizier.cfa.harvard.edu/viz-bin/VizieR`,
  che riporta l'elenco del CDS: CfA Harvard, NAOJ Giappone, IUCAA India,
  China-VO, IDIA Sudafrica, INASAN Russia, CADC Canada; il sito del CDS non
  rispondeva; ricerca dei servizi TAP con "vizier" o "simbad" nell'URL nel
  registro VO RegTAP `https://dc.g-vo.org/tap`):

  | Servizio | Mirror | Esito del 2026-11-07 | Entra? |
  |---|---|---|---|
  | SIMBAD TAP | `https://simbad.harvard.edu/simbad/sim-tap` (CfA Harvard; fonte: `10` §7 e l'elenco dei server di `astroquery.simbad`, `simbad.harvard.edu`) | `availability` e `capabilities` 200; `SELECT TOP 0 ra, dec FROM basic`: `utype` MANGO ICRS epoca J2000 come il principale (D13-20); M 31 = 10,684708333°, +41,268750000°, 13 836 citazioni, `AGN` (coordinate uguali a quelle di SIMBAD in `10` §7); Vega: 8 magnitudini in `flux` (B, V, U 0,03 … sistema `V`); `* eta Tau` → `Gaia DR3 66714384142368256`, `2MASS J03472908+2406184` (uguali agli archivi originali, sotto) | **sì**, secondo server di SIMBAD |
  | TAPVizieR | nessuno: i 7 mirror ufficiali rispondono 404 o non rispondono a `/TAPVizieR/tap`, `/tap`, `/viz-bin/tap` (CfA e IDIA 404; NAOJ, IUCAA, CADC senza risposta; China-VO 404 in http; INASAN irraggiungibile); il registro VO elenca per VizieR solo `tapvizier.cds.unistra.fr` e `cdsarc.cds.unistra.fr` (Strasburgo) | — | **no**: per Gaia DR3 e 2MASS ripiego sugli archivi originali (`13`); gli altri identificativi danno un errore chiaro |
  | Fotometria (SED) di VizieR | `https://vizier.cfa.harvard.edu/viz-bin/sed`, `https://vizier.idia.ac.za/viz-bin/sed` | rispondono, ma **parziali e diversi tra loro**: per Vega (raggio 5″) CfA 377 righe con 114 errori `NOT AVAILABLE YET` / `(pipe) Request has been interrupted` (sotto-richieste ai cataloghi non disponibili sul mirror; `pyvo` legge gli `INFO name="Error"` come rifiuto); IDIA prima 263 righe senza errori, poi 402 righe con 17 errori e una volta oltre 60 s; principale non confrontabile | **no**: non verificabile (risposte incomplete e diverse); resta solo il CDS |
  | MocServer | nessuno fuori da Strasburgo (`alaskybis` è nello stesso centro dati e non rispondeva) | — | **no**: copia in cache e messaggio chiaro (sotto) |
  | CDS XMatch | nessuno | — | **no**: errore che propone il metodo locale |

  **MocServer senza copia (sprint B4):** `vizier_collections` con il
  MocServer giù usa la copia in cache, dichiarata (`FROM_CACHE`
  `network_cached`, con la data); senza copia `NET_TIMEOUT` con `reason =
  mocserver_no_mirror`, che dice che il MocServer non ha copie fuori da
  Strasburgo e che gli identificativi scritti restano utilizzabili (Gaia DR3
  e 2MASS con il ripiego del `13`). Nessun mirror inventato.
  **Fotometria senza copia:** `vizier_photometry` resta sul solo CDS
  (`NET_TIMEOUT` come prima); dallo sprint C3 la usa la sezione fotometria
  del profilo (25 §3.11, serie separata del `20`), dove un CDS giù resta un
  errore della sola sezione.
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
  async_timeout=600 s, cancel=None, ...)`** (P3) — esecuzione ADQL; restituisce
  `VoResult` o errore con il messaggio del servizio; `url` è un URL TAP o
  una voce TAP dell'elenco dei server; `cancel` solo in asincrona (§3,
  sprint B3).
- **`service_url(service, protocol, servers=None)`** (P3, sprint B3) — URL
  del servizio: un URL http(s) così com'è (TAP senza `/` finale), altrimenti
  la voce dell'elenco con quel protocollo (`SERVER_UNKNOWN` `not_listed` o
  `wrong_protocol`); la usano i comandi del `05` per scrivere l'URL nel
  comando registrato.
- **`adql_to_send(adql)`** (P3, sprint B3) — il testo ADQL senza i
  commenti `--` (fuori dalle virgolette) e senza le righe rimaste vuote; lo
  usa `tap_query` per la `QUERY`.
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
- **`simbad_object(identifier, *, cache, refresh, timeouts)`** (sprint C2,
  2026-11-07, per il profilo del `25`, autorizzato con D25-12) — l'oggetto
  SIMBAD **esatto** di un identificativo (mai il «più citato»): tre
  interrogazioni `tap_query` sulla voce `cds-simbad-tap` (quindi con il ripiego
  sul mirror di Harvard, D14-14): (1) `basic` unita a `ident` (SIMBAD confronta
  `ident.id` normalizzando maiuscole e spazi: verificato il 2026-11-07,
  `'51 Peg'` → `* 51 Peg`, `'vega'` → `NAME Vega`) e a `otypedef` per la
  descrizione del tipo: `oid`, `main_id`, `otype`, descrizione, `sp_type`,
  `sp_bibcode`, `nbref`, `ra`, `dec`, `coo_err_maj`, `coo_err_min`,
  `coo_err_angle`, `coo_qual`, `coo_bibcode`, `plx_value`, `plx_err`,
  `plx_bibcode`, `pmra`, `pmdec`, `pm_err_maj`, `pm_err_min`,
  `pm_err_angle`, `pm_bibcode`, `rvz_radvel`, `rvz_err`, `rvz_bibcode`
  (colonne e unità verificate il 2026-11-07); (2) tutti gli identificativi di
  `ident` per `oidref`; (3) le magnitudini con la stessa interrogazione di
  `simbad_pointer` (`flux` e `filter`, D14-12). Restituisce `SimbadRecord`:
  campi di `basic` con le unità dichiarate dal servizio (un `float` a 32 bit
  del VOTable torna al decimale scritto dal servizio, cioè la rappresentazione
  più corta del valore a 32 bit, poi `float64`, DC6), `identifiers`,
  `magnitudes` (`SimbadMagnitude`), posizione `SkyFrame` ICRS epoca J2000
  (`SIMBAD_COORDINATES_NOTE`), le tre `RequestRecord` (server che ha risposto),
  avvisi (`SERVICE_MIRROR_FALLBACK`, `FROM_CACHE`, avvisi delle magnitudini).
  Nessuna riga → `NAME_NOT_FOUND` (sotto-voce `simbad_identifier`), mai un
  ripiego su un altro servizio né su un oggetto vicino; più righe con `oid`
  diversi (un identificativo di due oggetti) → `NAME_NOT_FOUND`
  (`several_objects`), nessuna scelta.
- **`vizier_collections(*, cache, refresh, timeouts)`** (D13-18) —
  `MocServerRecords` (record del MocServer come dati dal servizio, richiesta
  registrata, avvisi), per l'albero delle collezioni del 13. Risposta letta
  con `MOCSERVER_CHARSET` (ISO-8859-1, la codifica dichiarata dal servizio).
- **`cds_xmatch(cat1, cat2, max_distance, selection, *, cache, refresh,
  timeouts)`** — incrocio con CDS XMatch per il 15; restituisce `VoResult`
  (coppie con `angDist`, `idx`, `idx2`, richiesta registrata).
- **`vizier_photometry(center, radius, ...)`** (P6, H17) — misure di flusso
  dal servizio fotometrico di VizieR, con catalogo d'origine per ogni punto.
- **Ripiego sui mirror (sprint B4, §3):** **`SERVICE_MIRRORS`** (voce
  dell'elenco dei server → servizio, nome e URL dei mirror verificati, in
  ordine: oggi `cds-simbad-tap` → `simbad`, "SIMBAD",
  `https://simbad.harvard.edu/simbad/sim-tap`); **`service_servers(service)`**
  — elenco ordinato dei server di una voce (principale + mirror; una voce
  senza mirror o un URL: solo quello); **`is_failover_error(exc)`** — vero
  per le cause di cambio di §3 (D14-14 a); **`current_server(service)`** —
  server in uso del servizio nella sessione (il principale finché non c'è
  stato un cambio); **`reset_mirror_state()`** — torna al principale e
  riemette l'avviso (test, nuova sessione). `tap_query` con una voce che ha
  mirror li usa da sé (§3); argomento nuovo **`use_stale_cache`** (default
  `True`): con `False` un server che non risponde non restituisce la sua
  copia vecchia (lo usa il ripiego, anche quello del `13`).
  `simbad_pointer` usa per la regione i server di `SIMBAD_SERVERS`
  (`simbad.cds.unistra.fr`, `simbad.harvard.edu`, i nomi di
  `astroquery.simbad`) con le stesse regole e lo stesso stato del servizio
  `simbad`.
- **`SampHub`** (classe, P7) — hub SAMP (H14, G3, D14-2 decisa) con
  `pyvo.samp`: **si collega a un hub già attivo se presente, altrimenti
  avvia il proprio** (profilo web disattivato salvo opzione esplicita);
  `send_table`, `send_selection`, `send_point`, ricezione degli stessi tre
  tipi con funzioni dell'utente, `clients()` e stato dei collegamenti; **le
  immagini sono un'estensione prevista** fuori dal primo perimetro;
  l'interfaccia utente è nel `40` §3.12 (con `41` e `42`). **Dal
  2026-11-05 (sprint B1):** `on_table_reference(function)` —
  `function(reference: SampTableReference, sender)` con `url`, `table_id`,
  `name`; se registrata sostituisce `on_table` (la tabella non si legge);
  `save_votable(url, path) -> Path`; `client_name(client_id) -> str |
  None`; `on_hub_event(function)` — `function(mtype, params)` per i quattro
  eventi dell'hub di §3; `SampSendResult.params` (dizionario dei parametri
  inviati). **Dal 2026-11-05 (sprint B1b):** `send_message`, `send_table`,
  `send_selection` e `send_point` accettano `timeout` (secondi, default 10)
  e mandano con chiamata sincrona a ogni destinatario;
  `SampSendResult.failures` (tupla di `SampFailure(id, reason, detail)`);
  `clients()` esclude l'hub per `samp.hub-id`; iscrizioni dichiarate una
  volta alla registrazione (§3, punti 7–9).
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
| `astroquery.xmatch` (D15-2) | client del servizio CDS XMatch per il 15 | client ufficiale; URL HTTPS e cache del 14 |
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
| TAP asincrona annullata da chi chiama (`cancel`, sprint B3) | lavoro interrotto (`ABORT`) ed eliminato, nessun risultato | `QUERY_CANCELLED` |
| Query che supera il limite di righe | risultato troncato con avviso e conteggio dichiarato (avviso, non errore) | `ROW_LIMIT_EXCEEDED` |
| Formato di esportazione non supportato | elenco dei formati | `EXPORT_FORMAT_UNSUPPORTED` |
| Esportazione in CSV semplice di una tabella con unità | file scritto senza unità; si suggerisce `ecsv` (D14-10) | avviso `CSV_UNITS_NOT_SAVED` |
| Nessun hub SAMP disponibile (né attivo, né avviabile) | funzioni VO non-SAMP operative, avviso | `SAMP_UNAVAILABLE` |
| Nessun client SAMP connesso | azione rifiutata con messaggio chiaro | `SAMP_NO_PEER` |
| Destinatario che rifiuta il messaggio (risposta `samp.error`, es. `table-id` già ricevuto o tabella sconosciuta) o non risponde entro il tempo massimo (dal 2026-11-05, sprint B1b) | nessuno riuscito: errore; altri riusciti: esito con `failures` (avvisi nel `40`) | `SAMP_NO_PEER` (`rejected`, `no_reply`) |
| Tipo di messaggio SAMP non supportato | rifiuto con l'elenco dei tipi supportati | `SAMP_UNSUPPORTED_TYPE` |
| Hub che non risponde entro il tempo massimo (interfaccia, `40` §3.12) | operazione abbandonata, interfaccia libera | `SAMP_UNAVAILABLE` (`timeout`) |
| Hub spento mentre AstroTwo è collegato | collegamento chiuso, stato aggiornato, avviso | `SAMP_UNAVAILABLE` (`hub_shutdown`) |
| Selezione ricevuta per una tabella che AstroTwo non conosce (`40` §3.12) | nessuna selezione, risposta d'errore al mittente e messaggio | `SAMP_TABLE_UNKNOWN` |
| VOTable ricevuto non copiabile (file assente, schema dell'URL non ammesso) | nessun catalogo aperto, risposta d'errore al mittente e messaggio | `SAMP_TABLE_FETCH_FAILED` |
| Servizio SSA non raggiungibile / timeout | nessun elenco di spettri, errore esplicito | `NET_TIMEOUT` |
| Nessuno spettro per i criteri dati | esito vuoto con avviso, non è un errore | `SSA_NO_RESULT` |
| Spettro SSA malformato o senza assi/unità | nessun dato mostrato come valido, errore con la posizione del problema | `SSA_INVALID` |
| Cache non disponibile | query eseguita comunque, cache saltata con avviso | `CACHE_UNAVAILABLE` |
| Corpo (`body`) non ricavabile dai metadati né dal sistema di coordinate | dato aperto da solo, non sovrapposto né combinato | `BODY_UNKNOWN` |
| Nessuna immagine per i criteri SIA/SIA2 | esito vuoto con avviso, non è un errore | `SIA_NO_RESULT` |
| Risposta SIA malformata | nessuna lista mostrata come valida | `SIA_INVALID` |
| Nessun oggetto Simbad nel raggio | esito vuoto con avviso | `SIMBAD_NO_OBJECT` |
| `simbad_object`: identificativo sconosciuto a SIMBAD (server raggiungibile) | errore, nessun ripiego | `NAME_NOT_FOUND` (`simbad_identifier`) |
| `simbad_object`: identificativo di più oggetti | errore, nessuna scelta | `NAME_NOT_FOUND` (`several_objects`) |
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
| Servizio del CDS con mirror che non risponde (timeout, connessione, 5xx, 429, risposta non valida; sprint B4) | si passa al mirror successivo; il servizio resta sul mirror per la sessione | avviso `SERVICE_MIRROR_FALLBACK` (una volta per servizio e sessione) |
| Servizio con mirror: risposta 404 o altro 4xx, ADQL rifiutata, nessun risultato | nessun cambio di server: errore o risultato del server in uso | codice del caso (`SERVICE_ERROR`, `ADQL_INVALID`, …) |
| Tutti i server di un servizio giù (sprint B4) | nessun risultato; copia in cache se c'è (dichiarata) | `NET_TIMEOUT` (`service_servers`) |
| MocServer giù senza copia in cache (sprint B4) | nessun elenco; il messaggio dice che non ci sono copie fuori da Strasburgo | `NET_TIMEOUT` (`mocserver_no_mirror`) |

### Parametri dei messaggi (D40-3)

Dal 2026-10-24 (sprint 8d) ogni errore e ogni avviso del modulo nasce come **codice + `params`**
(`VoProtocolsError(code, message, params=..., **details)`; gli avvisi sono `ModuleWarning(code, text, params)`, la
coppia (codice, testo) del 10 con in più `params`, che si confronta e si spacchetta come prima): `params` è un
dizionario nome → valore JSON con tutti i valori che finiscono nel testo, mai arrotondati; le quantità sono
`{"value": numero, "unit": testo}`. Il **testo italiano del modulo resta invariato** (campo `text`/`message`); il
modulo **non** contiene traduzioni e non importa il catalogo (`src/astrotwo/messages_catalog.py`, `40` §3.7.1).
Il parametro riservato `reason` sceglie la sotto-voce (D40-6); "esterno" = testo di terzi (servizio, libreria,
cella di una tabella), inserito tale e quale senza tradurlo. I `details` di prima (`url`, `path`, `status`,
`position`, `server`, `service_message`) restano.

**Messaggi annidati (D40-7).** Dove il testo incorpora l'errore di un altro modulo di AstroTwo (il 13 che non
legge un VOTable o uno spettro, l'errore di lettura che diventa `SIA_INVALID`) il parametro è di tipo `message`
(`cause`): `{"code", "params", "text"}` del messaggio del 13, che il catalogo rende in modo ricorsivo. Il testo di
terzi (messaggio di un servizio TAP, eccezione di `pyvo`, `astropy`, `requests`, `defusedxml`) resta `external`.
Gli errori del 14 che il 12 e il 13 rilanciano o incorporano (`NET_TIMEOUT`, `SERVICE_ERROR`, …) viaggiano con i
loro `params` e passano nel 12 da parametro esterno a parametro `message` (sprint 8d).

**Suggerimento dell'asincrona.** Il testo italiano di un timeout o di un errore di durata di una query TAP
sincrona termina con il suggerimento `tap_query(..., mode='async')`: nel catalogo è una sotto-voce a parte
(`url_sync_tap`, `service_rejected_async_hint`, `http_message_async_hint`), mai testo nel valore di un parametro.

| Codice | `reason` | Parametri (`params`) |
|---|---|---|
| `VOTABLE_INVALID` | (generale) | — |
| `VOTABLE_INVALID` | `not_votable` | `path` (string), `cause` (message: errore del 13) |
| `VOTABLE_INVALID` | `other_format` | `path` (string), `format` (string) |
| `VOTABLE_INVALID` | `malformed` | `path` (string), `cause` (message: errore del 13) |
| `VOTABLE_INVALID` | `unreadable_response` | `url` (string), `detail` (string, esterno) |
| `VOTABLE_INVALID` | `datalink_columns` | `url` (string), `missing` (list) |
| `VOTABLE_INVALID` | `photometry_columns` | `url` (string), `missing` (list) |
| `EXPORT_FORMAT_UNSUPPORTED` | (generale) | `format` (string), `allowed` (list) |
| `FILE_EXISTS` | (generale) | `path` (string) — voce già del 13 |
| `NET_TIMEOUT` | `url` | `url` (string), `connect` (quantity), `read` (quantity), `detail` (string, esterno) — voce già del 10, 11, 12 |
| `NET_TIMEOUT` | `url_sync_tap` | come `url`, con il suggerimento dell'asincrona |
| `NET_TIMEOUT` | `async_deadline` | `url` (string), `timeout` (quantity, s), `phase` (string) |
| `QUERY_CANCELLED` | `async_aborted` | `url` (string), `phase` (string) — sprint B3 |
| `AUTH_REQUIRED` | (generale) | `url` (string), `status` (integer) |
| `SERVICE_ERROR` | `http_status` | `url` (string), `status` (integer), `status_text` (string, esterno) — voce già del 12 |
| `SERVICE_ERROR` | `unreadable_response` | `url` (string), `detail` (string, esterno) — voce già del 12 |
| `SERVICE_ERROR` | `http_message` | `url` (string), `status` (integer), `message` (string, esterno) |
| `SERVICE_ERROR` | `http_message_async_hint` | come `http_message`, con il suggerimento dell'asincrona |
| `SERVICE_ERROR` | `http_no_votable` | `url` (string), `status` (integer) |
| `SERVICE_ERROR` | `service_rejected` | `url` (string), `detail` (string, esterno) |
| `SERVICE_ERROR` | `request_failed` | `url` (string), `detail` (string, esterno) |
| `SERVICE_ERROR` | `job_phase` | `url` (string), `phase` (string) |
| `SERVICE_ERROR` | `job_result_status` | `uri` (string), `status` (integer) |
| `SERVICE_ERROR` | `descriptor_missing` | `service_def` (string, esterno) |
| `SERVICE_ERROR` | `simbad_no_units` | — |
| `ADQL_INVALID` | (generale) | — |
| `ADQL_INVALID` | `empty` | `position` (integer) |
| `ADQL_INVALID` | `not_select` | `position` (integer) |
| `ADQL_INVALID` | `unmatched_close` | `position` (integer) |
| `ADQL_INVALID` | `unclosed_quote` | `quote` (string), `position` (integer) |
| `ADQL_INVALID` | `unclosed_paren` | `position` (integer) |
| `ADQL_INVALID` | `service_rejected` | `url` (string), `detail` (string, esterno) |
| `ADQL_INVALID` | `service_rejected_async_hint` | come `service_rejected`, con il suggerimento dell'asincrona |
| `MAX_ROWS_INVALID` | (generale) | `value` (string), `maximum` (integer) |
| `MAX_SEP_INVALID` | (generale) | `distance` (quantity, arcsec), `maximum` (quantity, arcsec) |
| `SERVER_UNKNOWN` | (generale) | — |
| `SERVER_UNKNOWN` | `wrong_protocol` | `service` (string), `found` (string), `wanted` (string) |
| `SERVER_UNKNOWN` | `not_listed` | `server` (string), `known` (list) |
| `SERVER_UNKNOWN` | `not_personal` | `server` (string) |
| `TABLE_TOO_LARGE` | `upload` | `total` (quantity, byte), `limit` (quantity, byte) — voce già del 13 |
| `SIA_INVALID` | (generale) | `cause` (message: `VOTABLE_INVALID` del 14) |
| `SSA_INVALID` | (generale) | — |
| `SSA_INVALID` | `axes_dm` | `origin` (string), `columns` (list, esterno) |
| `SSA_INVALID` | `axes_dm_ucd` | `origin` (string), `columns` (list, esterno) |
| `SSA_INVALID` | `no_unit` | `origin` (string), `column` (string, esterno) |
| `SSA_INVALID` | `no_access_column` | — |
| `SSA_INVALID` | `unreadable` | `url` (string), `cause` (message: errore del 13) |
| `SSA_INVALID` | `format` | `url` (string), `format` (string) |
| `IDHA_UNREADABLE` | (generale) | — |
| `IDHA_UNREADABLE` | `xml_error` | `path` (string), `detail` (string, esterno) |
| `IDHA_UNREADABLE` | `format_unknown` | `path` (string) |
| `XML_UNSAFE` | (generale) | `path` (string), `construct` (string) — voce già del 13 |
| `SAMP_UNAVAILABLE` | (generale) | — |
| `SAMP_UNAVAILABLE` | `no_hub` | `detail` (string, esterno) |
| `SAMP_UNAVAILABLE` | `not_connected` | — |
| `SAMP_UNSUPPORTED_TYPE` | (generale) | — |
| `SAMP_UNSUPPORTED_TYPE` | `type` | `mtype` (string), `supported` (list) |
| `SAMP_UNSUPPORTED_TYPE` | `no_handler` | `mtype` (string) |
| `SAMP_NO_PEER` | (generale) | — |
| `SAMP_NO_PEER` | `recipient` | `recipient` (string), `mtype` (string) |
| `SAMP_NO_PEER` | `none` | `mtype` (string) |
| `SAMP_NO_PEER` | `rejected` (dal 2026-11-05, sprint B1b) | `recipient` (string, esterno: nome dichiarato o identificativo), `mtype` (string), `detail` (string, esterno: risposta del destinatario) |
| `SAMP_NO_PEER` | `no_reply` (dal 2026-11-05, sprint B1b) | `recipient` (string, esterno), `mtype` (string), `seconds` (number) |
| `SAMP_NO_PEER` | `no_reply_table` (dal 2026-11-05, sprint B2: `table.load.votable`, "la tabella potrebbe arrivare comunque") | `recipient` (string, esterno), `mtype` (string), `seconds` (number) |
| `SAMP_UNAVAILABLE` | `timeout` (dal 2026-11-05, sollevata dal `40`) | `operation` (string: `connect`, `disconnect`, `send`, `clients`), `seconds` (number) |
| `SAMP_UNAVAILABLE` | `hub_shutdown` (dal 2026-11-05, avviso del `40`) | — |
| `SAMP_TABLE_UNKNOWN` | `unknown` (dal 2026-11-05, sollevata dal `40`) | `table_id` (string, esterno), `url` (string, esterno), `sender` (string, esterno) |
| `SAMP_TABLE_FETCH_FAILED` | `file` | `url` (string, esterno), `detail` (string, esterno) |
| `SAMP_TABLE_FETCH_FAILED` | `scheme` | `url` (string, esterno) |
| `ROW_LIMIT_EXCEEDED` (avviso) | (generale) | — |
| `ROW_LIMIT_EXCEEDED` | `cut` | `received` (integer), `max_rows` (integer) |
| `ROW_LIMIT_EXCEEDED` | `service_overflow` | `received` (integer), `max_rows` (integer) |
| `CSV_UNITS_NOT_SAVED` (avviso) | (generale) | — |
| `SIA_NO_RESULT` (avviso) | (generale) | — |
| `SSA_NO_RESULT` (avviso) | (generale) | — |
| `FROM_CACHE` (avviso) | `cached_origin` | `origin` (string), `retrieved_at` (string) |
| `FROM_CACHE` | `network_cached` | `error` (string, esterno), `retrieved_at` (string) |
| `FROM_CACHE` | `cached_since` | `retrieved_at` (string) |
| `FROM_CACHE` | `network_unavailable` | `error` (string, esterno) — voce già del 12 |
| `BODY_UNKNOWN` (avviso) | `spectrum_without_candidate` | — |
| `FORMAT_DECLARED` (avviso) | `recognized_differs` | `declared` (string, esterno), `recognized` (string) |
| `ASTRORES_LINK_SOURCE` (avviso) | (generale) | — |
| `ASTRORES_LINK_SOURCE` | `cached` | `url` (string), `retrieved_at` (string) |
| `ASTRORES_LINK_SOURCE` | `downloaded` | `url` (string), `retrieved_at` (string) |
| `SIMBAD_NO_OBJECT` (avviso) | (generale) | `radius` (quantity, deg) |
| `NAME_NOT_FOUND` | `simbad_identifier`, `several_objects` | `name`, `service` (sprint C2, `simbad_object`) |
| `SIMBAD_SYSTEM_UNKNOWN` (avviso) | (generale) | `band` (string, esterno), `code` (string, esterno) |
| `SIMBAD_SYSTEM_UNDECLARED` (avviso) | (generale) | `bands` (list, esterno) |
| `SIMBAD_NBREF_MISSING` (avviso) | (generale) | — |
| `SIMBAD_TIE` (avviso) | (generale) | `count` (integer), `nbref` (integer), `main_id` (string, esterno), `separation` (quantity, arcsec) |
| `SIMBAD_TIE` | `nbref_missing` | `count` (integer), `main_id` (string, esterno), `separation` (quantity, arcsec) |
| `SIMBAD_NO_MAGNITUDE` (avviso) | (generale) | `main_id` (string, esterno) |
| `SERVICE_MIRROR_FALLBACK` (avviso, sprint B4) | `network` | `service` (string), `primary` (string), `mirror` (string) |
| `SERVICE_MIRROR_FALLBACK` | `http_status` | `service` (string), `primary` (string), `mirror` (string), `status` (integer) |
| `SERVICE_MIRROR_FALLBACK` | `invalid_response` | `service` (string), `primary` (string), `mirror` (string) |
| `NET_TIMEOUT` | `service_servers` (sprint B4) | `service` (string), `servers` (integer), `tried` (list), `last` (message) |
| `NET_TIMEOUT` | `mocserver_no_mirror` (sprint B4) | `url` (string), `cause` (message) |

`CACHE_FULL` (avviso della cache comune, `04`) passa tale e quale con il codice, il testo e i `params` che ha: il `04`
non è tra i moduli convertiti dello sprint 8, quindi finché non lo è si mostra come in §3.7.2 del `40`.
`HTTP_STATUS` è una nota interna tra `_http` e `_parse_results`: non esce mai dal modulo.

## 11. Esposizione all'IA

Non applicabile in questo file: gli strumenti per l'IA si dichiarano in
`32-ia-registro-strumenti.md` (`01-architettura.md` §7, decisione del
proprietario del 2026-10-10, D14-9 punto 16) e passano sempre da un comando
del `05`. **Dal 2026-11-06 (sprint B3, decisione del proprietario):**
`cone_search` è esposta come `catalog__cone_search` (comando
`catalog.cone_search` del `05`, con conferma come gli altri comandi di
rete); **`tap_query` e `validate_adql` non sono esposte**: l'ADQL scritto
dall'IA è il `33-ia-query-adql.md`, rimandato dal proprietario (la query
ADQL resta all'utente, comando `catalog.tap_query` non esposto).
`describe_services` su `ServerRegistry`, `ssa_search`, `ssa_load` restano
fuori finché non diventano comandi del `05`. Vale sempre la regola d'oro
n. 1: l'IA compone i parametri e spiega l'esito, il contenuto delle tabelle
viene solo dai servizi e dal codice di questo modulo ed è verificato da
`34-ia-verifica-risultati.md`.

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
| T22 | SAMP per l'interfaccia (sprint B1, 2026-11-05) | con hub e client simulati: tabella ricevuta con `on_table_reference` e copiata con `save_votable` (file e URL `http` di un server locale); schema `ftp:` e file assente; eventi dell'hub alla registrazione e all'uscita del client simulato; `client_name`; `SampSendResult.params` di `send_point`; iscrizioni di AstroTwo e chiamata `client.env.get` | copia identica byte per byte; `SAMP_TABLE_FETCH_FAILED` (`scheme`, `file`); eventi `register`/`unregister` ricevuti; nome dichiarato; parametri uguali a quelli ricevuti dal client; iscrizioni = tre tipi + quattro avvisi + `samp.app.ping`, `client.env.get` rifiutata dall'hub | test con client simulato |
| T24 | SAMP con un destinatario come TOPCAT (sprint B1b, 2026-11-05) | hub con identificativo `hub` (come JSAMP) e client simulato che si comporta come TOPCAT 4.10-8: carica la tabella in differita e risponde a caricamento finito, rifiuta un `table-id` già ricevuto, rifiuta la selezione di una tabella che non ha; client morto ancora registrato; conteggio degli avvisi `samp.hub.event.subscriptions` al collegamento | `clients()` senza l'hub; `send_table` poi `send_selection` subito dopo: selezione applicata; `table-id` duplicato e tabella sconosciuta → `SAMP_NO_PEER` (`rejected`) con il testo del destinatario; client morto in `failures` e gli altri raggiunti; un solo avviso di iscrizioni | test con hub e client simulati |
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
| T27 | Ripiego sui mirror (sprint B4, 2026-11-07) | servizi simulati: SIMBAD principale giù (connessione, HTTP 503, 429, risposta 2xx non VOTable) → mirror per `tap_query("cds-simbad-tap")` e per `simbad_pointer` (regione e magnitudini); 404, ADQL rifiutata e risposta senza righe → nessun cambio; principale e mirror giù → `NET_TIMEOUT` `service_servers` con 2 server; copia vecchia in cache e tutti giù → copia dichiarata; avviso dopo il primo cambio, non al secondo; richiesta successiva subito al mirror; `refresh=True` → di nuovo il principale; URL scritto → nessun ripiego; MocServer giù con e senza copia in cache | ordine e conteggio delle richieste ai server finti; `RequestRecord.url` e `source` = server che ha risposto; avvisi; codici | test di unità con server finti; test di rete (marcatore `network`, non nel commit) per il mirror di SIMBAD |
| T28 | `simbad_object` (sprint C2, 2026-11-07) | servizio SIMBAD simulato con le risposte registrate dal mirror di Harvard il 2026-11-07 (51 Peg, eta Tau); nome sconosciuto; principale giù | campi di `basic` con unità, 46/62 identificativi, magnitudini; `NAME_NOT_FOUND` `simbad_identifier` senza ripiego; con il principale giù risponde il mirror e la provenienza è il mirror | confronto con le risposte registrate; test di unità con server finti |
| T26 | Commenti ADQL e annullamento (sprint B3, 2026-11-06) | `validate_adql` con commenti `--` (con apostrofo, prima di `SELECT`, dentro una stringa); `tap_query` sincrona con commenti su un servizio simulato; asincrona su un lavoro UWS simulato che non finisce, con `cancel` che diventa vero | posizioni del testo scritto; `--` dentro le virgolette non è un commento; `QUERY` inviata senza commenti e senza righe vuote, `adql` scritto negli argomenti registrati; `QUERY_CANCELLED` entro 1 s, `ABORT` inviato e lavoro eliminato | test di unità |

**Test di rete:** regola delle ripetizioni in `02-convenzioni.md` §8, punto 8
(implementazione in `tests/conftest.py`, test in `tests/test_network_retries.py`).

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
  il nome di una tabella). **Nona voce (sprint C2, 2026-11-07, autorizzata
  dal proprietario con D25-12 del `25`):** `nasa-exoplanet-tap`, «NASA
  Exoplanet Archive», ente NASA/IPAC (NExScI), protocollo TAP, URL
  `https://exoplanetarchive.ipac.caltech.edu/TAP`, fonte
  `https://exoplanetarchive.ipac.caltech.edu/docs/TAP/usingTAP.html` (URL
  base per pyvo e TOPCAT letto lì il 2026-11-07, tabelle `ps` e
  `pscomppars`), servizio provato in linea il 2026-11-07 (`pscomppars` per
  `hostname` e `gaia_dr3_id`, `SELECT DISTINCT` accettato). **Esclusioni confermate dal proprietario il
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

- **D14-13 — URL in http con reindirizzamento a https che codifica due volte l'URL (servizi dell'ESO) —
  DA DECIDERE** (aperta il 2026-10-14, Gruppo 3). Il registro VO dà per la DSS dell'ESO
  (`ivo://eso.org/dss`) l'URL del servizio SIA in `http://archive.eso.org/…`, e il servizio restituisce
  anche gli URL delle immagini in http. Dal 2026-10-14 (verifica con `curl` lo stesso giorno) il server
  risponde `307` verso `https://…` codificando una seconda volta l'URL (`%2C` → `%252C`, `%20` → `%2520`):
  la richiesta SIA viene rifiutata (`POS` non nella forma "ra,de", `SERVICE_ERROR`) e il download
  dell'immagine non restituisce un FITS (`FORMAT_UNSUPPORTED` dall'11). Con `https://` direttamente entrambe
  funzionano. **Oggi:** la demo delle Pleiadi usa https direttamente (servizio e immagine), dichiarato nel
  report; **nessuna modifica al codice del 14**. Da decidere se e come il 14 debba gestire il caso (per
  esempio provare https per un URL http dello stesso host, oppure non seguire un reindirizzamento che
  cambia la richiesta e segnalarlo con un errore dedicato), sempre dichiarato nel risultato.

- **D14-14 — Ripiego dei servizi del CDS sui mirror (sprint B4): DECISA il
  2026-11-07 dal proprietario** (testo dello sprint B4, aperta e decisa lo
  stesso giorno). **Esito:** (a) si passa al server successivo solo per
  timeout, errore di connessione, HTTP 5xx, HTTP 429 o risposta non valida;
  mai per 404 o altri 4xx, mai per un errore di sintassi ADQL, mai per
  "nessun risultato"; (b) solo mirror verificati con richieste reali, con
  URL, data e fonte ufficiale scritti nella spec; un mirror non verificabile
  oggi non entra; (c) prima le copie fuori da Strasburgo; (d) avviso a ogni
  cambio, una volta per servizio e per sessione, voci en/it, provenienza =
  server che ha davvero risposto; (e) tutti giù: errore che dice quanti
  server sono stati provati e, dove ha senso, suggerisce un'alternativa.
  Per Gaia DR3 e 2MASS, se nessun mirror VizieR risponde, ripiego sugli
  archivi originali (`13`, D14-15 (5)–(7)). Applicata in §3, §7, §10, §12.
- **D14-15 — Scelte minori del ripiego sui mirror e di "Riesegui con dati
  aggiornati" (sprint B4): PROPOSTE da Claude Code il 2026-11-07, da
  confermare (Gruppo 3).** (1) dopo un cambio il servizio resta sul mirror
  per tutta la sessione (come D12-9), `refresh=True` riparte dal principale;
  (2) cache: prima la cache di tutti i server dell'elenco, poi la rete senza
  copie vecchie, poi la prima copia in cache nell'ordine dei server
  (principale prima), dichiarata; (3) ripiego solo per le voci dell'elenco, non per un URL
  scritto (la query ADQL del B3 rifà la stessa richiesta); (4) codice nuovo
  `SERVICE_MIRROR_FALLBACK` (stesse sotto-voci di `HIPS_MIRROR_FALLBACK`) e
  `NET_TIMEOUT` `service_servers` (come `hips_servers`); (5) Gaia DR3 e
  2MASS dagli archivi originali **senza rinominare** le colonne: i nomi
  restano quelli dell'archivio (es. `ra`, `dec`, `phot_g_mean_mag` invece di
  `RA_ICRS`, `DE_ICRS`, `Gmag`), dichiarato nell'avviso
  `CATALOG_ORIGINAL_ARCHIVE` e nella storia della tabella; (6) 2MASS
  dall'IRSA: l'IRSA non collega le colonne a un `COOSYS` (descrizione
  "right ascension (J2000 decimal deg)", verificato il 2026-11-07), quindi
  la regione si chiede con `CIRCLE('ICRS', …)` e centro in ICRS
  (dichiarato), le posizioni restano senza sistema e si confermano con il
  dialogo delle colonne (`POSITION_COLUMNS_REQUIRED`); (7) identificativi
  VizieR diversi da Gaia DR3 e 2MASS con TAPVizieR giù: errore
  `NET_TIMEOUT` `vizier_no_mirror` che suggerisce Gaia DR3/2MASS e la query
  ADQL sull'archivio originale; (8) "Riesegui con dati aggiornati" del `40`:
  campo `refresh` del comando del `05` (scritto solo quando vale `true`),
  pulsante attivo solo se tutti i comandi scelti usano la rete, avviso
  `DATA_REFRESHED` (`fresh` o `cache_used`) nel risultato; non esposto
  all'IA. (9) riquadro del puntatore SIMBAD (`41` §3.19): collegamento alla
  pagina SIMBAD del server che ha risposto (CDS o Harvard).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-11-07 | Claude Code | **Sprint C3 (autorizzazione D25-12 del `25`, limitata agli sprint C2–C6):** nota «Fotometria senza copia» aggiornata: `vizier_photometry` usata dalla sezione fotometria del profilo (25 §3.11); IRSA `nasa-irsa-tap` e `vizier_photometry` già esistenti; correzione: le magnitudini SIMBAD (`flux`, `flux_err`, colonne `float32`) tornano al decimale scritto da SIMBAD come le altre celle (es. 6,16 e non 6,159999847…), regola di `simbad_object` (sprint C2) estesa a `_simbad_magnitudes`. |
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
| 2026-10-11 | Claude Code | **Per il modulo 15** (decisione del proprietario del 2026-10-11, autorizzazione esplicita a modificare il file approvato): `cds_xmatch`, `XMATCH_URL` — CDS XMatch con `astroquery.xmatch` in HTTPS, timeout di `04`, cache di astroquery disattivata, risposta nella cache del 14 con l'impronta delle tabelle caricate; limiti verificati (180″, 100 MB) (§3, §7, §8). Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | §12: il paragrafo sulle ripetizioni dei test di rete sostituito da un rimando a `02-convenzioni.md` §8 (decisione del proprietario del 2026-10-12, autorizzazione esplicita a modificare il file approvato). Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **Allineamento specifica–codice** (decisione del proprietario del 2026-10-12, autorizzazione esplicita a modificare il file approvato; regola: le specifiche si aggiornano sempre insieme al codice): §3 e §7 — risposte del MocServer dichiarate ISO-8859-1 e lette secondo la codifica dichiarata (`MOCSERVER_CHARSET`, usata anche da 12 e 16), regola già applicata nel codice con il modulo 12. Stato `approvato` invariato. |
| 2026-10-14 | Claude Code | **D14-13 aperta (Gruppo 3)** (indicazione del proprietario del 2026-10-14, autorizzazione esplicita a modificare il file approvato): servizi dell'ESO in http con reindirizzamento a https che codifica due volte l'URL (richiesta SIA rifiutata, immagine non scaricata); la demo usa https direttamente; nessuna modifica al codice. Stato `approvato` invariato. |
| 2026-10-24 | Claude Code | **D40-3 e D40-7, sprint 8d:** §10 — nuova sezione "Parametri dei messaggi" con codice, `reason` e `params` di ogni errore e avviso (messaggi annidati di tipo `message` per gli errori del 13 incorporati; suggerimento dell'asincrona come sotto-voce); il codice li restituisce (testo italiano invariato); le traduzioni sono nel catalogo del `40`. `AdqlCheck` ha in più `reason` e `quote` (per scegliere la sotto-voce). Nessun comportamento scientifico cambia. |
| 2026-11-05 | Claude Code | **Sprint B1 — SAMP nell'interfaccia** (decisioni del proprietario del 2026-11-05, D40-8 del `40`; autorizzazione esplicita del proprietario ad aggiornare il 14 "se cambia qualcosa"): §3 e §7 — interfaccia nel `40` §3.12 con `41`/`42`; aggiunte a `SampHub` per l'interfaccia (`on_table_reference`, `save_votable`, `client_name`, `on_hub_event` con i quattro eventi amministrativi dell'hub, `SampSendResult.params`); **corretto: `pyvo.samp` iscriveva AstroTwo anche a `client.env.get` (variabili d'ambiente a chi le chiede), ora tolta prima della registrazione**; §10 — nuove sotto-voci `SAMP_UNAVAILABLE` `timeout` e `hub_shutdown`, nuovi codici `SAMP_TABLE_UNKNOWN` e `SAMP_TABLE_FETCH_FAILED`; §12 — nuovo T22. I tipi di messaggio di dati restano i tre di D14-9 punto 10; le immagini restano un'estensione prevista (D14-2). Stato `approvato` invariato. |
| 2026-11-05 | Claude Code | **Sprint B1b — correzioni dalla prova con TOPCAT vero** (incarico del proprietario del 2026-11-05: "spec prima se cambia un comportamento descritto"): §3 punti (7) invio con chiamata sincrona e `failures`, (8) `clients()` senza l'hub per `samp.hub-id`, (9) iscrizioni dichiarate una volta; §6 firme; §10 errori e codici `SAMP_NO_PEER` (`rejected`, `no_reply`); nuovo T24. Stato `approvato` invariato. |
| 2026-11-05 | Claude Code | **Sprint B2 — rifiniture SAMP** (decisione del proprietario del 2026-11-05, D40-9 (7)): tempo di risposta di **60 s per `table.load.votable`** (`SAMP_TABLE_REPLY_TIMEOUT`, default di `SampHub.send_table`), 10 s per gli altri tipi; nuova sotto-voce `SAMP_NO_PEER` `no_reply_table` (la tabella potrebbe arrivare comunque) per `table.load.votable`. Stato `approvato` invariato. |
| 2026-11-06 | Claude Code | **Sprint B3 — cone search e query ADQL nell'interfaccia** (decisioni del proprietario del 2026-11-06; autorizzazione esplicita ad aggiornare il 14 "se cambia qualcosa"): §3 — commenti `--` tolti prima dell'invio (`adql_to_send`; provato il 2026-11-06: Gaia ESA, IRSA e HEASARC rifiutano una query con un commento, MAST la accetta) e contati come spazio da `validate_adql`; annullamento della TAP asincrona (`cancel`, `QUERY_CANCELLED`); §7 firme; §10 `QUERY_CANCELLED`; §11 riscritto: solo `cone_search` esposta all'IA (come `catalog.cone_search` del `05`), `tap_query`/`validate_adql` no (`33` rimandato); §12 nuovo T26. Server personali salvati dal `40` (`vo/personal_servers`). Stato `approvato` invariato. |
| 2026-11-07 | Claude Code | **Sprint C2 (autorizzazione del proprietario del 2026-11-07, D25-12 del `25`, limitata agli sprint C2–C6):** §7 nuova `simbad_object` (oggetto esatto per identificativo: `basic` + `otypedef`, `ident`, magnitudini, con il ripiego D14-14; `NAME_NOT_FOUND` `simbad_identifier`/`several_objects`); D14-4 nona voce `nasa-exoplanet-tap` (URL dalla pagina ufficiale, provata il 2026-11-07); §10 sotto-voce; §12 T28. Stato `approvato` invariato. |
| 2026-11-07 | Claude Code | **Sprint B4 — ripiego sui mirror per SIMBAD e VizieR** (regole decise dal proprietario il 2026-11-07, D14-14; autorizzazione esplicita ad aggiornare il 14): §3 — nuova voce "Ripiego sui mirror dei servizi del CDS" (cause del cambio, ordine, avviso `SERVICE_MIRROR_FALLBACK` una volta per servizio e sessione, provenienza = server reale, servizio in uso per la sessione, cache, ambito, tutti giù → `NET_TIMEOUT` `service_servers`); **mirror verificati il 2026-11-07** con richieste reali (CDS irraggiungibile): SIMBAD TAP di Harvard **entra**; nessun TAPVizieR fuori da Strasburgo (7 mirror ufficiali e registro VO); SED di VizieR su CfA e IDIA parziale e incoerente → **non entra**; MocServer e XMatch senza copie; MocServer giù senza cache → `NET_TIMEOUT` `mocserver_no_mirror`. §7 (`SERVICE_MIRRORS`, `service_servers`, `is_failover_error`, `current_server`, `reset_mirror_state`, `use_stale_cache` di `tap_query`, `SIMBAD_SERVERS`), §10, T27 (§12), D14-14 decisa e D14-15 proposta (§13). Stato `approvato` invariato. |
