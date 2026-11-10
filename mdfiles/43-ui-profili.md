# 43-ui-profili.md — finestra «Profili» (profilo di un oggetto)

**Stato:** approvato

> Creato il 2026-11-08 (sprint C5, Fase C) per la decisione **D25-7** del
> proprietario (2026-11-07, ribadita il 2026-11-08): la specifica
> dell'interfaccia del profilo di un oggetto sta in questo file. Parte da
> `25-analisi-profilo-oggetto.md` §3.9 (proposta d'interfaccia, approvata con
> il `25`) e lo precisa. Il numero 43 era riservato in `INDICE.md` a un
> «pannello analisi» generico (`non esiste`): il proprietario lo assegna alla
> finestra Profili. Esportazione, «Carica i punti SED come catalogo» e
> «Invia con SAMP»: sprint C6, §3.10.
>
> **Codice dello sprint C5 (2026-11-08):** scritto su **istruzione esplicita
> del proprietario** del 2026-11-08 (brief dello sprint C5, punti a–h, con i
> commit C5a e C5b), nell'ambito dell'autorizzazione D25-12 (sprint C2–C6).
> **File approvato dal proprietario il 2026-11-08** (brief dello sprint C6):
> D43-1…D43-8 e D43-10 confermate, D43-9 decisa (limiti superiori come
> frecce ovunque). Codice in `src/astrotwo/ui/profiles.py`, test in
> `tests/ui/test_profiles.py`, `tests/ui/test_profiles_open.py` e (C6)
> `tests/ui/test_profiles_export.py`.

## 2. Scopo

Mostrare il profilo di un oggetto (comando `object.profile` del `25`) in una
finestra non modale con una scheda per oggetto, in cui le sezioni arrivano una
alla volta mentre i servizi rispondono e **ogni numero, cliccato, dice da dove
viene** (servizio, server, tabella, interrogazione, riferimento, data, cache,
comando).

## 3. Cosa fa

### 3.1 Perimetro dello sprint C5

Dentro: la finestra **Profiles / Profili**, le schede, lo scheletro con gli
stati delle sezioni, l'arrivo progressivo, «Riprova questa sezione», il
riquadro della provenienza, le aperture (§3.2), «Riesegui con dati aggiornati»
e «Mostra nel cielo». Fuori (sprint C6): «Esporta…» (ECSV, PDF, PNG della
SED), «Carica i punti SED come catalogo», «Invia con SAMP», strumento
`object__profile` dell'assistente. Nello sprint C5 questi pulsanti **non
compaiono** (nessun pulsante spento senza funzione).

**Sprint C6 (2026-11-08):** dentro «Esporta…», «Carica i punti SED come
catalogo» e «Invia con SAMP» (§3.10) e, con la seconda parte del brief
(C6b), la scheda dei profili chiesti dall'assistente con lo strumento
`object__profile` (§3.11).

### 3.2 Da dove si apre

Ogni apertura **mette in coda un comando `object.profile`** del `05` (regola
d'oro n. 6) e apre subito la sua scheda (§3.4); nessuna apertura calcola
nulla da sé.

1. **Menu Data → Object profile… / Profilo dell'oggetto…** (nel menu Data del
   `40`, dopo un separatore sotto «Cross-match catalogs…»): dialogo con un
   campo «Name or coordinates» / «Nome o coordinate». Un testo che il 10
   legge come coppia di coordinate (`parse_sexagesimal`, come il campo «Vai
   a» del 40 §3.4, nel frame delle coordinate mostrate, D41-9) diventa
   `position` con sistema dichiarato ed **epoca scelta nel dialogo**
   (campo «Epoch», default J2000.0, scritto nel comando: DC2, mai assunta);
   altrimenti `name`. Sezioni: tutte (default del comando).
2. **Campo «Vai a» (40 §3.4):** dopo un `view.go_to` riuscito con un **nome**,
   un pulsante «Profile» / «Profilo» accanto al campo per 30 s (o fino al
   prossimo «Vai a»): `object.profile` con `name` = il testo scritto.
   Con coordinate il pulsante non compare (il profilo da coordinate si apre
   dal menu, dove l'epoca si dichiara).
3. **Clic destro nel cielo (41 §3.20):** voce «Profile at this position» /
   «Profilo in questa posizione»: `position` = punto sotto il mouse
   (`window_to_sky` del 10, portata nel frame delle coordinate mostrate con
   `convert_coordinates` del 10, scritta come coppia decimale in gradi) e
   l'**epoca chiesta nel dialogo** della voce 1, precompilato con la
   posizione e J2000.0. Leggere l'epoca da un'immagine
   base (`DATE-OBS`/`MJD-OBS`) **non** si fa in C5: l'11 oggi non la
   espone (verificato il 2026-11-08 nel `11`, nessuna voce sull'epoca);
   l'epoca non si assume mai (DC2).
4. **Riquadro del puntatore SIMBAD (41 §3.19):** collegamento «Profile of
   <main_id>» / «Profilo di <main_id>»: `name` = `main_id` dell'oggetto del
   riquadro **e** `simbad_id` = lo stesso `main_id` (per identificativo,
   nessuna ricerca per posizione).
5. **Clic destro su una riga della tabella (42):** voce «Profile of this
   source» / «Profilo di questa sorgente». Riconoscimento dell'identificativo
   della riga (D25-13 (3), rimandato a C5): se il livello viene da un
   catalogo **riconosciuto dalla sua origine** (metadati del livello del 13:
   servizio e tabella) **e** la riga ha la colonna identificativa con un
   valore, si usa `name` = identificativo; altrimenti `layer` + `row` (per
   posizione, con l'epoca del livello, D10-2). Tabella del riconoscimento
   (proposta, D43-3):

   | Origine del livello (13) | Colonna | `name` |
   |---|---|---|
   | Gaia DR3 (`gaiadr3.gaia_source` dell'archivio ESA o `I/355/gaiadr3` di VizieR) | `source_id` (o `Source` di VizieR) | `Gaia DR3 <valore>` |
   | 2MASS PSC (`fp_psc` dell'IRSA o `II/246/out` di VizieR) | `designation` (o `2MASS`) | `2MASS J<valore>` |
   | AllWISE (`allwise_p3as_psd` dell'IRSA o `II/328/allwise` di VizieR) | `designation` (o `AllWISE`) | `WISEA <valore>` |
   | SIMBAD (`basic`) | `main_id` | `<valore>` |

   Il nome della colonna non basta da solo (un `source_id` di un altro
   catalogo non è Gaia DR3): serve l'origine. I nomi delle colonne VizieR
   indicati sono **da verificare prima del codice** sui metadati veri dei
   tre cataloghi.

Più profili si aprono insieme: ogni apertura una scheda nuova (D43-1).

### 3.3 La finestra

- Finestra **non modale** di primo livello (`QWidget` con barra del titolo
  propria, non un pannello agganciato), titolo «Profiles» / «Profili»;
  si apre alla prima apertura di un profilo; voce **Window → Profiles** del
  40 per mostrarla o nasconderla; dimensioni di default 760 × 900 pt
  (D43-6), geometria ricordata nelle impostazioni dell'app (`QSettings`
  `profiles/geometry`, non nella sessione), come il pannello del 44.
- Una **scheda per profilo** (`QTabWidget`, schede chiudibili e riordinabili).
  Titolo della scheda: il bersaglio come scritto (nome, o coordinate con
  `format_coordinates` del 10) fino alla risoluzione, poi il `main_id` di
  SIMBAD (testo esterno = dato, mostrato come testo semplice, mai HTML).
  Il suggerimento della scheda dice il numero del comando e lo stato.
- **Chiudere una scheda** con il suo profilo in coda o in corso annulla quel
  comando (`CancelToken` del 05, come Annulla della barra di stato) dopo una
  conferma; il comando resta nella cronologia (esito annullato). Chiudere
  una scheda finita non tocca nulla (il comando resta nella cronologia).
- Aspetto: linee guida visive del 40 §3.11 (temi chiaro, scuro, notte rossa;
  griglia di 4 punti; carattere di sistema con cifre tabulari; colori del
  grafico della SED dal 20 e, in modalità notte, toni di rosso con le
  serie distinte per forma del simbolo, come i cataloghi del 41).

### 3.4 La scheda

Dall'alto in basso, in un'area che scorre:

1. **Testata:** bersaglio come scritto, `main_id` e tipo (dopo la
   risoluzione), numero del comando (`#n`, collegamento alla riga del
   pannello Comandi del 40 con `show_command`), stato complessivo (in coda,
   in corso, finito con il tempo totale `elapsed`, annullato, errore) e i
   pulsanti **«Rerun with fresh data» / «Riesegui con dati aggiornati»**
   (mette in coda lo stesso comando registrato con `refresh: true`, come il
   pulsante del pannello Comandi, 40 §3.6; apre una scheda nuova, D43-1) e
   **«Show in sky» / «Mostra nel cielo»** (`view.set_center` del 05 sulla
   posizione del bersaglio risolto con la sua epoca e fonte; attivo dopo la
   risoluzione).
2. **Avvisi del profilo** (bersaglio cambiato, pianeti esclusi, identificativi
   assenti…): righe di messaggi con codice e `params` (D40-3), resi con il
   catalogo dei messaggi nella lingua dell'app.
3. **Sezioni impilate in ordine fisso** (§3.5): **Identità** (con le
   **Immagini** a destra), **Astrometria e distanza**, **Fotometria**,
   **Pianeti**. Ogni sezione ha un'intestazione con lo stato (§3.6) e un
   corpo che si riempie quando la sezione arriva.

Bersaglio **ambiguo** (`PROFILE_AMBIGUOUS_TARGET`, 25 §3.2; brief del
2026-11-08 punto e): si apre un **dialogo** «Choose the object» / «Scegli
l'oggetto» con l'elenco dei candidati del messaggio (nome, tipo,
separazione, citazioni), **nessuno scelto in partenza** (il pulsante
«Profile of this object» / «Profilo di questo oggetto» è spento finché
l'utente non sceglie una riga); la scelta mette in coda un nuovo
`object.profile` con lo stesso bersaglio (posizione o riga) e `simbad_id` =
il candidato scelto, in una scheda nuova (la scelta dell'utente è
registrata nel comando, 25 §3.10). Annullare il dialogo non fa nulla: la
scheda resta con l'errore. **Nome non trovato** (`NAME_NOT_FOUND`) o bersaglio non
valido: il messaggio nella scheda, nessuna sezione.

### 3.5 Scheletro e arrivo progressivo

- La scheda si apre **subito**, al momento della richiesta, con lo
  scheletro di tutte le sezioni richieste nello stato «in attesa».
- Le sezioni stanno **sempre nello stesso posto** (ordine fisso, così la
  pagina non salta mentre si legge); il **contenuto** compare nell'ordine in
  cui le sezioni arrivano (`on_section` del 25 §3.12 regola 6). È la lettura
  proposta di «le sezioni compaiono nell'ordine in cui arrivano» (D43-2).
- **Canale dei dati parziali (proposta, D43-4):** il comando
  `object.profile` gira nella coda del 40 (thread di lavoro); oggi il suo
  avanzamento porta solo «passo k di n» (`ProgressReport` del 05, testo
  `object_profile/<sezione>`). Per riempire la scheda prima della fine:
  - `ProgressReport` del 05 riceve un campo facoltativo **`detail`**
    (valore JSON, `None` per tutti gli altri comandi), che la barra di stato
    ignora;
  - `object.profile` lo usa per due eventi: **`resolved`** (bersaglio
    risolto: forma JSON di `ResolvedTarget`, avvisi del profilo, istante di
    partenza delle sezioni) con il nuovo richiamo `on_resolved` di
    `build_profile` (25, chiamato nel thread di chi chiama, prima delle
    sezioni); **`section`** (forma JSON della `ProfileSection` arrivata,
    quella che entra nel risultato, PNG compresi);
  - il segnale `progress` del 40 li porta al thread principale (connessione
    in coda, 40 §3.8), che aggiorna la scheda del comando.
  Il **risultato finale** del comando (`CommandDone`) resta l'unica fonte
  definitiva: all'arrivo la scheda si ridisegna da `result.values` (stessi
  dati), prende il numero del comando e mostra gli avvisi. Un comando
  annullato con sezioni arrivate (`COMMAND_CANCELLED` `partial`, 25 §3.12
  regola 8) conserva il profilo nel risultato e la scheda lo mostra.
- **Avanzamento e Annulla** restano nella barra di stato del 40 come per gli
  altri comandi lunghi («object.profile · passo k di n», pulsante Annulla):
  nessun controllo nuovo nella scheda per annullare (chiudere la scheda
  annulla, §3.3).
- **Una coda sola (40 §3.8):** i comandi si eseguono uno alla volta. Più
  profili chiesti insieme hanno ciascuno la sua scheda subito, ma il secondo
  parte quando il primo finisce; la sua testata dice «In coda» / «Queued»
  (D43-1). Lo stesso vale per «Riprova questa sezione».

### 3.6 Stato nell'intestazione di ogni sezione

| Stato (25 §3.4, §3.12) | Testo dell'intestazione | Quando |
|---|---|---|
| in attesa | «Waiting» / «In attesa» | comando in coda o bersaglio non ancora risolto |
| in corso | «Running · <servizi> · <s> s» / «In corso · <servizi> · <s> s» | dall'evento `resolved` all'arrivo della sezione; secondi da `sections_started`, aggiornati ogni secondo |
| arrivata (`done`, `not_applicable`) | «Arrived · <fonte> · <s> s» / «Arrivata · <fonte> · <s> s» | sezione arrivata; tempo = `elapsed` della sezione |
| arrivata in parte (`partial`) | come arrivata, più «in part» / «in parte» e i messaggi degli errori sotto l'intestazione | almeno un servizio non ha risposto, ci sono valori |
| errore (`error`) | «Error» / «Errore» e il **messaggio del catalogo** di ogni errore (codice + `params`, D40-3), più il pulsante «Retry this section» / «Riprova questa sezione» | nessun valore ed errori, o `PROFILE_SECTION_TIMEOUT` |
| annullata (`cancelled`) | «Cancelled» / «Annullata», più «Riprova questa sezione» (D43-5) | Annulla con la sezione non arrivata |

- **<servizi>** = i servizi che la sezione può interrogare
  (`SECTION_SERVICES` del 25: SIMBAD, archivio Gaia, IRSA, Exoplanet Archive,
  HiPS, VizieR SED), con i nomi leggibili. Il motore non dice quale
  richiesta è aperta in quell'istante: mostrare «il servizio interrogato
  adesso» chiederebbe un evento per ogni richiesta (D43-4, alternativa (b)).
- **<fonte>** = i server che hanno risposto (host delle richieste della
  sezione, es. `simbad.harvard.edu`, `gea.esac.esa.int`), con «dalla cache»
  se tutte le richieste venivano dalla cache.
- **«Riprova questa sezione»** mette in coda un `object.profile` con gli
  stessi parametri del comando registrato della scheda (bersaglio come
  scritto, `simbad_id` già scritto dal comando, raggi, survey, miniature) e
  **`sections` = [quella sezione]**. Il suo risultato sostituisce **solo
  quella sezione** nella stessa scheda; i valori nuovi portano il numero del
  comando che li ha prodotti (riquadro §3.8), così una scheda può avere
  sezioni di due comandi diversi, dichiarato nell'intestazione della
  sezione («#m»). Durante il nuovo tentativo l'intestazione torna «in
  attesa» → «in corso».

### 3.7 Corpo delle sezioni

Tutti i numeri sono quelli del risultato del comando: la scheda **non
calcola nulla** (regola d'oro n. 1), neppure unità diverse. Formato dei
numeri: coordinate con `format_coordinates` del 10 nello stile delle
coordinate mostrate (D41-2); gli altri valori con la **rappresentazione
decimale più corta** del `float64` del risultato (quella che il servizio ha
scritto, perché il 14 legge i `float32` al decimale scritto) e la loro
unità come la dà il risultato (D43-7); sempre il punto decimale (40 §3.9).
Ogni numero è un collegamento al suo riquadro (§3.8).

**Identità** (a sinistra): `main_id`; tipo `otype` con la descrizione di
`otypedef`; tipo spettrale con il bibcode; citazioni `nbref`; posizione ICRS
J2000 con errore ellittico, qualità e bibcode; **identificativi raggruppati
per catalogo** (gruppi chiusi oltre 8 voci, D43-6); tabella della **catena
degli identificativi** (catalogo, identificativo, metodo `simbad_identifier`
| `official_crossmatch` | `position`, separazione, epoche, candidati,
conflitti, errori del servizio) con gli avvisi
`PROFILE_IDENTIFIER_CONFLICT`, `PROFILE_POSITIONAL_MATCH`,
`PROFILE_PLANET_HOST_MISMATCH`; collegamento alla pagina SIMBAD **del server
che ha risposto** (prefissi ammessi come nel 41 §3.19: `https://simbad.cds.unistra.fr/`,
`https://simbad.harvard.edu/`; si apre nel browser di sistema).

**Immagini** (a destra dell'Identità, colonna larga 200 pt, D43-6): le
miniature del 25 §3.13 in colonna, ciascuna disegnata dal PNG del risultato
(nessun ridisegno dai tile), nord in alto, con sotto: titolo del survey,
campo e dimensione, centro con epoca e `center_note`, server reale dei
tile, e i **crediti dichiarati dal survey** (`obs_copyright`, con
`obs_copyright_url` come collegamento, `obs_ack`). Per i survey DSS (`DSS2`
nell'identificativo, D25-17 (3)) si aggiunge il **testo di STScI del `01`
§6.1** («The Digitized Sky Surveys were produced at the Space Telescope
Science Institute under U.S. Government grant NAG W-2166. …», primo
paragrafo come scritto nel `01`, con il collegamento alla pagina
`https://archive.stsci.edu/dss/acknowledging.html` per il testo integrale).
Miniatura mancante: riquadro vuoto delle stesse dimensioni con il messaggio
del 12 (`NET_TIMEOUT` `hips_servers`). La sezione Immagini ha la sua
intestazione di stato (§3.6) in cima alla colonna.

**Astrometria e distanza:** tabella con grandezza, valore, errore, unità,
epoca e note: posizione Gaia DR3 a `ref_epoch`, parallasse, moti propri,
velocità radiale; indicatori `ruwe` (senza soglia, D25-11), numero di
parametri, `duplicated_source`, `ipd_frac_multi_peak`; valori di SIMBAD con
il bibcode quando Gaia manca o ha 2 parametri; poi la **distanza** con il
metodo scritto per intero (Bailer-Jones 2021 con `flag`, oppure 1/ϖ con la
soglia e la nota sullo zero point) o il motivo dell'assenza
(`PROFILE_NO_DISTANCE`). Avvisi della sezione sotto la tabella.

**Fotometria:** tabella dei punti (`details.points` del 25/20): catalogo,
banda, sistema, valore come dato dal catalogo con errore, qualità, λ di
riferimento, Fν con errore se convertito, «nel grafico» sì/no con il
motivo (messaggi `SED_*`), duplicati marcati. Sotto, il **grafico della
SED** come lo disegna il `20` (D20-7: matplotlib incorporato in Qt, λ in µm
contro Fν in Jy, log-log, barre d'errore, colori per catalogo, serie VizieR
distinta in un altro colore e simbolo, così come data da VizieR). La scheda
lo disegna con la funzione del 20 (`plot_sed`) su una figura incorporata
(`FigureCanvasQTAgg`), ricostruendo la SED dalla forma JSON del risultato
con una funzione del 20 (D43-8); il PNG `plot_png` del risultato resta per
l'esportazione (C6). **Limiti superiori (D43-9, decisa dal proprietario
il 2026-11-08):** i limiti superiori convertiti (`upper_limit` con un
flusso) si disegnano come **frecce verso il basso** nel colore del loro
catalogo **ovunque** — grafico della finestra, PNG del risultato (20) ed
esportazione (25 §3.15) —, distinti dai punti misurati e mai usati come
misure; nella tabella restano con `SED_UPPER_LIMIT` e «nel grafico: no ·
limite superiore» (non sono punti della serie misurata). Funzione del 20:
`plot_sed_rows(points, vizier)`. Serie VizieR in errore (CDS giù): il messaggio nella
sezione (stato `partial`), il resto del grafico presente.

**Pianeti:** «Nessun pianeta nell'archivio» quando non ce ne sono (non è un
errore); altrimenti una tabella con una riga per pianeta (nome, metodo e
anno di scoperta, periodo, semiasse, eccentricità, massa con `pl_bmassprov`,
raggio, temperatura di equilibrio), ogni parametro con **errore superiore e
inferiore così come dati** (`+a / −b`) e il segno di limite (`<`, `>`)
quando `…lim` lo dice; sopra la tabella l'avviso
**`PROFILE_PLANETS_COMPOSITE`** quando c'è («i parametri possono venire da
lavori diversi», con il numero dei riferimenti). Riferimento per parametro
nel riquadro (§3.8).

### 3.8 Riquadro della provenienza (clic su un numero)

Un clic su un numero apre un **riquadro** (finestrella non modale ancorata
al numero, si chiude con Esc o con un clic fuori) che mostra, dalla
`ProfileValue` del risultato e dalla sua `Provenance`:

- grandezza; **valore**; **errori** (simmetrico, oppure superiore e
  inferiore così come dati); **unità**; banda e sistema se presenti;
- **metodo**: `read` («letto dal servizio») oppure `computed` con la
  funzione e la formula scritte dal motore;
- **servizio** e **server reale** che ha risposto (anche il mirror),
  URL, **tabella**, **interrogazione ADQL** (testo selezionabile e
  copiabile, in carattere a larghezza fissa), identificativo usato e tipo di
  incrocio;
- **riferimento**: il bibcode come **collegamento ADS cliccabile**
  (`https://ui.adsabs.harvard.edu/abs/<bibcode>/abstract`, costruito solo
  da un bibcode del risultato, il testo esterno non diventa mai HTML;
  per i pianeti l'URL ADS già estratto dal `*_reflink`, 25 §3.13);
- **data** della risposta (ISO 8601 UTC, DC1), **cache sì/no**;
- **comando**: numero del comando (`command_id`, collegamento alla riga
  del pannello Comandi) che ha prodotto il valore; nota del valore se c'è.

Pulsante «Copy» / «Copia» che copia il contenuto del riquadro come testo
(stesse righe, nessun numero ricalcolato).

### 3.9 Testi

Testi in inglese nel codice con `tr()` e italiano nostro (A9, 40 §3.9);
messaggi dei moduli resi dal catalogo con codice e `params` (D40-3, 40
§10.1); nomi dei servizi e delle sezioni tradotti (Identity / Identità,
Images / Immagini, Astrometry and distance / Astrometria e distanza,
Photometry / Fotometria, Planets / Pianeti).

### 3.10 Esporta, Carica i punti SED come catalogo, Invia con SAMP (sprint C6, 2026-11-08)

Tre pulsanti nella testata della scheda, dopo «Mostra nel cielo», **attivi
quando la scheda ha un profilo** (risultato finale con esito `ok` o
`cancelled` `partial`, cioè con il numero del comando); «Carica i punti SED
come catalogo» e «Invia con SAMP» solo se la Fotometria ha almeno un punto
(suggerimento sul pulsante spento: «nessun punto della SED»). Ogni azione è
un **comando registrato** (regola d'oro n. 6): la scheda non scrive file e
non manda messaggi da sé. Regole dei file e dei comandi nel `25` §3.15.

- **Elenco dei comandi della scheda (`commands`):** il numero del comando
  di base, poi, per ogni sezione riprovata, il numero dell'ultimo
  «Riprova questa sezione» riuscito (con la sezione nel risultato),
  nell'ordine in cui sono finiti. È quello che la scheda mostra (sezioni
  con «#m», §3.6).
- **«Export…» / «Esporta…»:** menu con tre voci — «Values with provenance
  (ECSV)…» / «Valori con provenienza (ECSV)…», «Profile sheet (PDF)…» /
  «Scheda del profilo (PDF)…», «SED plot (PNG)…» / «Grafico della SED
  (PNG)…» (spenta senza punti) — ciascuna con il dialogo di salvataggio di
  Qt (nome proposto `<main_id ridotto>-profile.ecsv`, `-profile.pdf`,
  `-sed.png`, conferma della sovrascrittura del dialogo), poi in coda
  **`object.export`** con `commands`, `format` (`ecsv`, `pdf`, `sed_png`),
  `path` e `language`. **Lingua del PDF (DD-1, decisa dal proprietario il
  2026-11-10):** solo per «Scheda del profilo (PDF)…» il dialogo di
  salvataggio ha una scelta «PDF language: English / Italian» / «Lingua del
  PDF: inglese / italiano», con **inglese proposto di default a ogni
  apertura**, qualunque sia la lingua dell'app (il PDF è il file da allegare
  a un articolo); la scelta va in `language`. Per ECSV e PNG, che non
  dipendono dalla lingua, nessuna scelta e `language = en`. Stesso profilo
  nella stessa lingua = stesso file byte per byte (`25` §3.15); quanto del
  testo del PDF segue la lingua scelta è in DD-3 (`panoramica.md` §2). Esito: messaggio nel pannello
  Messaggi del 40 come gli altri comandi; errori (`PROFILE_EXPORT_INVALID`,
  `PROFILE_EXPORT_FAILED`) in una finestra «The export was not written» /
  «L'esportazione non è stata scritta» con il messaggio del catalogo.
- **«Load SED points as catalog» / «Carica i punti SED come catalogo»:**
  in coda `object.export` con `format = sed_votable` e il file della
  cartella `~/Library/Application Support/AstroTwo/Profiles/` (25 §3.15),
  poi, quando finisce con esito `ok`, **`catalog.open_file`** su quel
  file; il nuovo livello compare nel cielo e nel pannello Tabella come ogni
  catalogo (42), con il nome `SED <main_id>`. Origine dei due comandi:
  `menu`.
- **«Send via SAMP» / «Invia con SAMP»:** menu dei destinatari come le
  altre voci SAMP del 40 §3.12 («All» / «Tutti» e un'azione per programma
  collegato, nomi dichiarati come testo); senza collegamento il pulsante è
  spento con il suggerimento «SAMP not connected» / «SAMP non collegato».
  In coda **`object.send_sed`** con `commands` e `recipient`; esiti e
  avvisi (`SAMP_NO_PEER`, `no_reply_table`) come `samp.send_table` (40
  §3.12).

### 3.11 Profilo chiesto dall'assistente (sprint C6, 2026-11-08)

Quando l'assistente (35) mette in coda `object.profile` (strumento
`object__profile` del 32, dopo la conferma dell'utente), la finestra
Profili **apre una scheda per quel comando** come per le altre aperture
(scheletro subito, arrivo progressivo, risultato definitivo, pulsanti), senza
mettere in coda un secondo comando: è lo stesso lavoro della coda. La
testata dice l'origine («Asked by the assistant» / «Chiesto
dall'assistente»). L'assistente riceve il suo risultato come per gli altri
strumenti; chiudere la scheda in corso annulla il comando (§3.3), e
l'assistente riceve `COMMAND_CANCELLED`.

## 4. Cosa NON fa

- Non calcola, converte o arrotonda valori scientifici: mostra quelli del
  risultato del comando (regola d'oro n. 1).
- Non sceglie tra candidati né tra identificativi in conflitto: mostra
  l'elenco e lascia scegliere (25 regola a).
- Non esegue comandi fuori dalla coda del 40 e non fa richieste di rete
  proprie (le miniature e il grafico vengono dal risultato).
- Non scrive file né manda messaggi SAMP da sé: esportazione, catalogo e
  SAMP sono comandi registrati (`object.export`, `catalog.open_file`,
  `object.send_sed`, §3.10) che rileggono i risultati registrati.
- Non è uno strumento dell'IA: lo strumento è `object__profile` del 32; la
  finestra mostra i profili chiesti dall'assistente (§3.11).
- Non riapre le schede alla riapertura di una sessione: la sessione del 05
  contiene i comandi `object.profile` (sola lettura) e li riesegue, ma la
  finestra Profili non fa parte dello stato della sessione (D43-10).
- Non interpreta come HTML nessun testo dei servizi (nomi SIMBAD,
  riferimenti dell'Exoplanet Archive, crediti dei survey): testo semplice,
  collegamenti solo dagli URL ammessi.

## 5. Livello e dipendenze

- **Livello:** interfaccia (sopra il livello 2: usa il `25`, che è
  analisi). Senza IA funziona completa.
- **Dipende da:** `25` (comando `object.profile`, forme JSON di profilo,
  sezioni e valori, `SECTION_SERVICES`, nuovo richiamo `on_resolved`), `20`
  (grafico della SED), `05` (comandi, `ProgressReport` con il nuovo campo
  `detail`, `CancelToken`), `40` (coda, barra di stato, menu, pannello
  Comandi, linee guida visive, catalogo dei messaggi), `41` (menu
  contestuale del cielo, puntatore SIMBAD), `42` (menu contestuale della
  tabella), `10` (`format_coordinates`, `parse_sexagesimal`,
  `window_to_sky`), `13` (origine dei livelli catalogo per il
  riconoscimento degli identificativi), `01` §6.1 (testo di STScI).
- **Usato da:** nessuno. Esegue (`bound_by = 43`) il comando `object.export`
  del 25 con la cronologia della finestra principale (sprint C6).
- **Modifiche richieste a moduli `approvato`** (autorizzate da D25-12 per
  C2–C6, con annotazione nei registri): `05` — campo `detail` di
  `ProgressReport`; `25` — `on_resolved` di `build_profile` ed eventi di
  avanzamento di `object.profile`; `20` — SED dalla forma JSON per il
  grafico; `40` — voce Data → Object profile…, Window → Profiles, pulsante
  «Profilo» del campo «Vai a»; `41` — voce del menu contestuale e
  collegamento nel riquadro del puntatore SIMBAD; `42` — voce del menu
  contestuale della tabella. Sprint C6: `40` — esecutore di `object.send_sed`
  (collegamento SAMP) e `SampLink.send_catalog`; `20` — frecce dei limiti
  superiori ovunque (D43-9).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | richiesta di profilo | nome, coordinate con sistema ed epoca, riga di un livello, oggetto del puntatore | come `object.profile` (25 §6) | §3.2 |
| in | eventi di avanzamento | `ProgressReport` con `detail` (`resolved`, `section`) | JSON | §3.5 |
| in | risultato del comando | `CommandDone` del 40 con `result.values` = forma JSON di `ObjectProfile` | JSON | fonte definitiva |
| out | comandi | `object.profile` (anche con `sections` = una, o `refresh`), `view.set_center` | 05 | ogni azione è un comando registrato |
| out | finestra | schede, sezioni, riquadri | Qt | nessun file scritto dalla finestra |
| out | comandi dello sprint C6 | `object.export` (`ecsv`, `pdf`, `sed_png`, `sed_votable`), `catalog.open_file`, `object.send_sed` | 05, 25 §3.15 | §3.10 |

## 7. Interfaccia pubblica

Codice previsto in `src/astrotwo/ui/profiles.py` (proposta):

- **`ProfilesWindow`** — finestra non modale con le schede; `open_profile(params, *, source)` mette in coda
  `object.profile` tramite la finestra principale (`submit`) e apre la scheda; `job_progress(job_id, report)` e
  `job_finished(done)` ricevono avanzamento e risultato dalla finestra principale; `tab_for(job_id)`.
- **`ProfileTab`** — una scheda: testata, avvisi, sezioni; `show_resolved(data)`, `show_section(data, command_id)`,
  `show_result(result, command_id)`, `retry(section)`.
- **`SectionView`** — intestazione con lo stato (§3.6) e corpo; un tipo per sezione (`IdentityView`,
  `ImagesView`, `AstrometryView`, `PhotometryView`, `PlanetsView`).
- **`ProvenancePopup`** — riquadro di §3.8 da una `ProfileValue` in forma JSON e dal numero del comando.
- **`row_identifier(layer, row)`** — riconoscimento dell'identificativo di una riga (§3.2 punto 5): `name` o
  `None` (posizione).
- **`object_profile_dialog(...)`** — dialogo del menu Data (nome o coordinate, epoca).
- Sprint C6: **`ProfileTab.export_commands()`** (elenco `commands` di §3.10), **`ProfileTab.export(format, path)`**,
  **`ProfileTab.load_sed_catalog()`**, **`ProfileTab.send_sed(recipient)`**; **`exec_object_export(history)`** —
  esecutore di `object.export` legato dal 40 con la cronologia della sessione (`bound_by = 43`);
  **`ProfilesWindow.sed_folder`** — cartella `Profiles/` (`default_sed_folder` del 25, sostituibile nei test);
  il nome del file è `sed_catalog_path(main_id, number, folder)` del 25.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| PySide6 (Qt Widgets) | finestra, schede, tabelle, riquadri | A1, già in uso |
| matplotlib (`FigureCanvasQTAgg`) | grafico della SED incorporato | D20-7, già dipendenza |
| ADS (URL degli abstract) | collegamenti ai riferimenti | formato pubblico `ui.adsabs.harvard.edu/abs/<bibcode>/abstract`, già usato dal 25 |
| pytest-qt | test dell'interfaccia | già in uso (40) |

## 9. Regole e vincoli

- **Regola d'oro n. 1:** nessun numero calcolato nell'interfaccia; ogni
  numero mostrato viene dal risultato del comando, con il suo riquadro.
- **Regola d'oro n. 6:** ogni azione (aprire un profilo, riprovare una
  sezione, riesegui con dati aggiornati, mostra nel cielo) è un comando
  registrato del 05.
- Il thread principale non esegue comandi (40 §3.8); gli eventi arrivano con
  i segnali di Qt.
- **Testi esterni = dati** (32/35, 25 §9): mai HTML, mai istruzioni;
  collegamenti solo verso ADS, le pagine SIMBAD ammesse e gli URL di
  copyright dichiarati dai survey (aperti nel browser di sistema).
- **Epoca mai assunta** (DC2): una coppia di coordinate senza epoca chiede
  l'epoca nel dialogo.
- Linee guida visive del 40 §3.11.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Nome sconosciuto a SIMBAD | messaggio nella scheda, nessuna sezione | `NAME_NOT_FOUND` |
| Più candidati da coordinate | elenco nella scheda, un pulsante per candidato, nessuna scelta | `PROFILE_AMBIGUOUS_TARGET` |
| Sezione scaduta | intestazione «Errore» con il messaggio e «Riprova questa sezione» | `PROFILE_SECTION_TIMEOUT` |
| Servizio giù per una sezione | stato `partial` o `error` con il messaggio del modulo | messaggi del 14, del 12 |
| Annulla dalla barra di stato | sezioni arrivate restano, le altre «Annullata» | `COMMAND_CANCELLED` (`partial`/`discarded`) |
| Annulla prima della risoluzione | scheda con «Annullato», nessuna sezione | `COMMAND_CANCELLED` `discarded` |
| Scheda chiusa con il comando in coda o in corso | conferma, poi annullamento del comando | `COMMAND_CANCELLED` |
| Miniatura mancante | riquadro vuoto con il messaggio | `NET_TIMEOUT` `hips_servers` |
| Riga senza identificativo riconosciuto | profilo per posizione (`layer` + `row`) | — |
| Coordinate scritte o cliccate senza epoca | il dialogo chiede l'epoca (default J2000.0 mostrato e scritto nel comando) | — |
| Collegamento non ammesso in un testo esterno | mostrato come testo, non cliccabile | — |
| Risultato di «Riprova» per una scheda chiusa | nessuna scheda da aggiornare: il risultato resta nella cronologia | — |
| Esportazione non valida o non scritta (§3.10) | finestra «L'esportazione non è stata scritta» con il messaggio | `PROFILE_EXPORT_INVALID`, `PROFILE_EXPORT_FAILED` |
| «Carica i punti SED come catalogo» con l'esportazione fallita | nessun `catalog.open_file` | come sopra |
| «Invia con SAMP» senza collegamento | pulsante spento con il suggerimento | `SAMP_UNAVAILABLE` (`not_connected`) se chiesto lo stesso |
| Nessun punto della SED | «Carica…», «Invia con SAMP» e la voce PNG spenti | — |

## 11. Esposizione all'IA

La finestra non è uno strumento, e `object.export` e `object.send_sed`
sono comandi `application`, non esposti all'IA (32 §3.3). Lo strumento
`object__profile` (25 §11, 32 §3.2, sprint C6b) apre la sua scheda come in
§3.11.

## 12. Test di accettazione

Test con pytest-qt e servizi simulati con le risposte vere registrate del 25
(`tests/analysis/profile_fakes.py`), in `tests/ui/test_profiles.py` (T1–T4,
stati) e `tests/ui/test_profiles_open.py` (aperture, T5, T6, T8, T9, T11,
pulsanti, chiusura in corso, traduzioni). Scritti nello sprint C5 (2026-11-08)
e verdi; T7, T10, T14 e T15 sono coperti in parte (numeri della tabella
dell'astrometria e dei pianeti confrontati con il risultato; pianeti di
TRAPPIST-1; nessun collegamento SIMBAD verso un server non ammesso), T12 e
T13 con l'apertura dalla tabella e dal riquadro del puntatore.

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Scheletro subito | richiesta di profilo di 51 Peg con il servizio Gaia simulato lento | scheda aperta prima di ogni risposta, quattro sezioni + Immagini «In attesa», poi «In corso» con i servizi | stati delle intestazioni |
| T2 | Arrivo progressivo | Gaia lento, IRSA veloce | il corpo di ogni sezione compare all'evento `section`, nell'ordine di arrivo; posizioni fisse | ordine dei riempimenti |
| T3 | Risultato definitivo | fine del comando | scheda ridisegnata da `result.values`, uguale a quella degli eventi; numero del comando nella testata | confronto |
| T4 | Errore e Riprova | archivio Gaia simulato giù per l'astrometria | «Errore» con il messaggio del catalogo; «Riprova questa sezione» mette in coda `object.profile` con `sections = ["astrometry"]` e lo stesso `simbad_id`; con Gaia tornato la sezione arriva e porta il numero del nuovo comando | comando registrato, stati |
| T5 | Annulla | Annulla della barra di stato dopo la prima sezione | arrivate conservate, altre «Annullata» | stati |
| T6 | Riquadro della provenienza | clic sulla parallasse di 51 Peg e su un periodo di TRAPPIST-1 b | valore, errori, unità, metodo, servizio, server reale, tabella, ADQL, collegamento ADS (2021PSJ.....2....1A per TRAPPIST-1), data, cache, numero del comando: uguali alla `ProfileValue` | confronto campo per campo |
| T7 | Nessun numero calcolato | ogni numero mostrato nella scheda di 51 Peg | ogni testo numerico è la rappresentazione di un valore del risultato | confronto con `result.values` |
| T8 | Candidati | coordinate di eta Tau | **dialogo** con la stella e `GN 03.44.2`, nessuno scelto e pulsante spento; la scelta mette in coda `object.profile` con la stessa posizione e `simbad_id` in una scheda nuova | comando registrato |
| T9 | Crediti delle miniature | 51 Peg | ogni miniatura con titolo, server, crediti del survey; DSS2 con il testo di STScI del `01` | testi |
| T10 | Pianeti | TRAPPIST-1; Vega | tabella di 7 pianeti con errori `+a / −b` e `PROFILE_PLANETS_COMPOSITE`; Vega «Nessun pianeta nell'archivio» | testi |
| T11 | Grafico | TRAPPIST-1 | figura incorporata con assi in µm e Jy logaritmici, serie per catalogo, **limite superiore AllWISE W4 come freccia** (D43-9, anche nel PNG del risultato) e fuori dalla serie dei punti | proprietà della figura |
| T12 | Riconoscimento delle righe | livello Gaia DR3 (origine `gaiadr3.gaia_source`) e livello sconosciuto con una colonna `source_id` | il primo dà `name = "Gaia DR3 <id>"`, il secondo `layer` + `row` | comando registrato |
| T13 | Puntatore SIMBAD | collegamento «Profilo di <main_id>» nel riquadro | `object.profile` con `name` e `simbad_id` = `main_id` | comando registrato |
| T14 | Più schede e coda | due profili chiesti insieme | due schede subito; la seconda «In coda» finché la prima non finisce | stati |
| T15 | Testi esterni | `main_id` e crediti con `<b>` e un URL non ammesso | mostrati come testo, nessun collegamento non ammesso | testi |
| T16 | Messaggi | ogni messaggio mostrato dalla finestra | voce del catalogo nelle due lingue (D40-3) | `check_message` |
| T17 | Esporta (sprint C6; lingua del PDF DD-1, 2026-11-10) | 51 Peg finito; «Esporta…» → ECSV, PDF, PNG con il dialogo di salvataggio simulato; app in italiano, PDF esportato due volte con la scelta di default e una volta con «italiano» | tre `object.export` in cronologia con `commands = [#n]`, `format`, `path`, `language`; tre file scritti; voce PNG spenta senza punti; **scelta di default = inglese** anche con l'app in italiano (`language = en`); i due PDF inglesi **identici byte per byte**, il PDF italiano diverso; Riesegui del PDF italiano lo riscrive identico | comandi registrati, file, SHA-256 |
| T18 | Esporta dopo «Riprova» | astrometria in errore, «Riprova questa sezione» riuscito, poi ECSV | `commands = [#n, #m]`; le righe dell'astrometria con `command_id = m` | ECSV |
| T19 | Carica i punti SED come catalogo | 51 Peg | `object.export` `sed_votable` nella cartella `Profiles/` (sostituita nel test), poi `catalog.open_file`; nuovo livello `SED * 51 Peg` con posizioni riconosciute e una riga per punto | cronologia, spazio di lavoro |
| T20 | Invia con SAMP | hub e client simulati; senza collegamento | pulsante spento senza collegamento; con un client `object.send_sed` con `recipient`, tabella ricevuta con le righe dei punti | messaggi SAMP |
| T22 | Profilo chiesto dall'assistente (C6b) | comando `object.profile` con `requested_by = ai` messo nella coda dall'esecutore dell'assistente | scheda aperta subito con «Chiesto dall'assistente», nessun secondo comando in cronologia, risultato all'assistente | cronologia, schede |
| T21 | Pulsanti attivi | scheda in coda, in corso, finita, in errore | pulsanti spenti finché non c'è un profilo; attivi alla fine (anche annullata con sezioni) | stato dei pulsanti |

## 13. Decisioni aperte

**Tutte decise dal proprietario il 2026-11-08** (brief dello sprint C6):
D43-1…D43-8 e D43-10 **confermate** come scritte; **D43-9 decisa**
(limiti superiori come frecce ovunque). Restano qui come registro. Nessuna
decisione aperta.

- **D43-1 — Più schede, coda unica — CONFERMATA (proprietario, 2026-11-08).** Ogni apertura
  (anche «Riesegui con dati aggiornati») apre una **scheda nuova**, mai
  riusata per lo stesso oggetto (una scheda = un comando, riproducibile);
  i profili si eseguono uno alla volta nella coda unica del 40, la scheda
  in attesa dice «In coda». Alternativa: riusare la scheda dello stesso
  `main_id`.
- **D43-2 — Ordine delle sezioni — CONFERMATA (proprietario, 2026-11-08).** Posizioni fisse
  (Identità con Immagini, Astrometria e distanza, Fotometria, Pianeti) e
  contenuto che compare nell'ordine di arrivo. Alternativa: riordinare le
  sezioni secondo l'arrivo (la pagina si sposta mentre si legge).
- **D43-3 — Riconoscimento degli identificativi delle righe — CONFERMATA (proprietario, 2026-11-08).** **Promemoria del
  proprietario (2026-11-08):** quando il CDS torna, verificare sui metadati veri i nomi delle colonne VizieR usati per
  riconoscere l'identificativo di una riga. Tabella di §3.2 punto 5 (origine del livello + colonna);
  nomi delle colonne VizieR da verificare prima del codice.
- **D43-4 — Canale dei dati parziali — CONFERMATA (proprietario, 2026-11-08).** (a) **campo
  `detail` di `ProgressReport` del 05** con gli eventi `resolved` e
  `section`, e richiamo `on_resolved` nel 25 (raccomandata: usa il segnale
  `progress` già esistente, nessun canale nuovo); (b) in più, un evento per
  ogni richiesta di rete aperta, per mostrare «il servizio interrogato
  adesso» invece dei servizi della sezione (più eventi dai thread del
  profilo, più codice nel motore).
- **D43-5 — Riprova anche per le sezioni annullate — CONFERMATA (proprietario, 2026-11-08).** Il
  brief lo dice per l'errore; proposto anche per `cancelled`.
- **D43-6 — Misure — CONFERMATA (proprietario, 2026-11-08).** Finestra 760 × 900 pt, colonna delle
  miniature 200 pt (miniature da 256 pixel mostrate a 192 pt), gruppi di
  identificativi chiusi oltre 8 voci, pulsante «Profilo» del «Vai a» per
  30 s.
- **D43-7 — Formato dei numeri — CONFERMATA (proprietario, 2026-11-08).** Rappresentazione decimale
  più corta del `float64` del risultato, con l'unità del risultato;
  coordinate con `format_coordinates`.
- **D43-8 — Grafico dalla forma JSON — CONFERMATA (proprietario, 2026-11-08).** Nuova funzione del
  20 che ricostruisce la `Sed` dalla forma JSON del risultato per
  `plot_sed` (stesso disegno del PNG); alternativa: mostrare il PNG
  `plot_png` (niente tooltip sui punti, 20 §3.4).
- **D43-9 — Limiti superiori nel grafico — DECISA (proprietario,
  2026-11-08): frecce verso il basso ovunque** (finestra, PNG del risultato
  del 20, esportazione del 25); D20-9 (3) cambiata di conseguenza nel 20.
  Testo della proposta, come registro: Il brief di C5 (2026-11-08, ripetuto nei
  punti b e h) chiede «limiti superiori come frecce»; **D20-9 (3)**, decisa
  dal proprietario il 2026-11-07, dice «convertiti come limiti ma fuori dal
  grafico (non frecce nella 1.0)». Applicata l'istruzione più recente
  **solo nel grafico della finestra Profili** (opzione (b) limitata); il
  PNG del risultato resta D20-9 (3). Da confermare: (b) anche nel PNG e nel
  `20` (cambia D20-9 (3), `20` §3.3–§3.4, T10 del 20); oppure (a) tornare a
  D20-9 (3) anche nella finestra.
- **D43-10 — Sessione — CONFERMATA (proprietario, 2026-11-08).** La finestra Profili non è nello
  stato della sessione: riaprire una sessione non riapre le schede (i
  comandi restano nella cronologia).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-11-10 | Claude Code | **DD-1 decisa dal proprietario il 2026-11-10 (lettura (b)); modifica a un file approvato da approvare insieme a DD-3:** §3.10 — scelta «Lingua del PDF» nel dialogo di «Scheda del profilo (PDF)…», inglese di default a ogni apertura qualunque sia la lingua dell'app; ECSV e PNG con `language = en`; T17 esteso (default inglese, byte per byte per lingua). Nessun codice scritto. Stato `approvato` invariato. |
| 2026-11-08 | Claude Code | **Sprint C6b (brief del proprietario del 2026-11-08, punto d):** nuovo §3.11 (scheda per i profili chiesti dall'assistente, nessun secondo comando), §3.1, §4, §11, T22. Stato `approvato` invariato (autorizzazione D25-12, brief di C6). |
| 2026-11-08 | Claude Code | **Sprint C6 (decisioni del proprietario del 2026-11-08):** file **approvato** dal proprietario; D43-1…D43-8 e D43-10 confermate; D43-9 decisa (limiti superiori come frecce verso il basso ovunque: finestra, PNG del 20, esportazione del 25). Nuovo §3.10 (pulsanti «Esporta…» con ECSV, PDF e PNG della SED, «Carica i punti SED come catalogo», «Invia con SAMP», tutti comandi registrati: `object.export`, `catalog.open_file`, `object.send_sed` del 25 §3.15; elenco `commands` della scheda con le sezioni riprovate); §3.1, §3.7, §4, §5, §6, §7, §10, §11 (strumento `object__profile` non nel brief di C6), §12 (T11 precisato, nuovi T17–T21), §13. |
| 2026-11-08 | Claude Code | **Sprint C5b:** §12 con i file di test reali (`test_profiles.py`, `test_profiles_open.py`) e T8, T11 come provati (dialogo dei candidati, freccia del limite superiore di TRAPPIST-1 W4); test dei pulsanti della scheda e della chiusura di una scheda in corso. |
| 2026-11-08 | Claude Code | **Codice dello sprint C5 (istruzione del proprietario del 2026-11-08, punti a–h):** `src/astrotwo/ui/profiles.py` (finestra, schede, sezioni, riquadro della provenienza, dialoghi dei candidati e del profilo), aggancio nel 40 (menu Data e Window, pulsante «Profilo» del «Vai a», coda), 41 (clic destro e riquadro del puntatore SIMBAD), 42 (clic destro su una riga), 05 (`ProgressReport.detail`), 25 (`on_resolved` ed eventi `resolved`/`section`), 20 (`plot_sed_rows`); §3.4 bersaglio ambiguo in un dialogo (punto e); §3.7 e D43-9: frecce dei limiti superiori solo nel grafico della finestra (istruzione più recente del proprietario, da confermare). Il file resta `bozza`. |
| 2026-11-08 | Claude Code | Creazione del file (stato: bozza), sprint C5, decisione D25-7 del proprietario (specifica dell'interfaccia del profilo nel `43`): finestra Profili non modale con una scheda per profilo, aperture (menu Data, «Vai a», cielo, puntatore SIMBAD, tabella con riconoscimento degli identificativi), scheletro e stati delle sezioni, arrivo progressivo (proposta: `detail` di `ProgressReport`), «Riprova questa sezione», corpo delle sezioni con miniature e crediti (testo di STScI per DSS, D25-17 (3)), grafico della SED del 20, riquadro della provenienza; decisioni D43-1…D43-10 (D43-9: conflitto tra il brief e D20-9 (3)). |
