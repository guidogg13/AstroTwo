# 13-core-cataloghi.md — cataloghi e tabelle

**Stato:** approvato

## 2. Scopo

Caricare, gestire e interrogare i cataloghi e le tabelle celesti con gli stessi
strumenti di Aladin (filtri, selezioni, moto proprio, ordinamento), tenendo
sempre separate le regole di disegno dalle selezioni dei record.

## 3. Cosa fa

**Divisione del codice (decisione del proprietario del 2026-10-10):** sei
parti, un commit per parte — **P1** lettura da file locale, formati,
colonne di posizione, limiti; **P2** ASTRORES; **P3** `search` e regole di
disegno; **P4** colonne calcolate, sottoinsiemi (anche salvati su file),
statistiche, istogramma, grafico x-y, vista a record; **P5** epoca, moto
proprio, filtro temporale; **P6** cataloghi da servizio e da URL, albero
delle collezioni, colonna DataLink (D13-11), dati ASTRORES in un `LINK`
esterno (D13-14) — **dopo il codice del `14`**, perché usa la sua rete e il
suo VOTable.

- **Caricamento cataloghi del CDS (D1, P6):** aprire cataloghi noti
  (Hipparcos, TYCHO-2, Gaia, 2MASS, ecc.) per identificatore; il
  trasferimento dei dati è di `14-core-protocolli-vo.md`, qui si gestisce la
  tabella risultante.
  - **Albero delle collezioni (D13-3, D13-18 decisa il 2026-10-11):**
    `collection_tree` legge dal **MocServer del CDS** (client
    `vizier_collections` nel 14) le collezioni di cataloghi `CDS/...` con
    `ID`, titolo e proprietà `vizier_popularity`; l'albero segue i livelli
    dell'identificativo VizieR (es. `I` → `I/355` → `I/355/gaiadr3`; le
    foglie sono le collezioni, utilizzabili con `load_catalog`); i record
    che non sono collezioni VizieR (es. `CDS/Simbad`, già nel gruppo fisso)
    sono esclusi con l'avviso `COLLECTION_SKIPPED`. **Ordine:** fratelli per
    `vizier_popularity` **decrescente** (per un nodo interno: il massimo del
    suo sottoalbero), a pari valore in **ordine naturale**
    dell'identificativo (i numeri contano come numeri: `I/9` prima di
    `I/10`; decisione del proprietario del 2026-10-11);
    le collezioni senza la proprietà dopo le altre, in ordine naturale
    (`POPULARITY_MISSING`); un valore non intero vale come assente
    (`POPULARITY_INVALID`). Il risultato **dichiara** l'ordine: "ordine per
    vizier_popularity, **proprietà non documentata del MocServer**"; se la
    proprietà manca in tutta la risposta, ordine naturale, dichiarato.
    Verifica del 2026-10-11: risposta JSON di 37 306 collezioni (circa
    5 MB, pochi secondi), `vizier_popularity` presente in 37 302; il
    valore è lo stesso per tutte le tabelle di un catalogo (es. 1000 per
    `I/355/*`).
- **Tabelle da file locale (D2, P1) e da URL (D3, P6):** VOTable, CSV,
  tabelle FITS e gli altri formati di H22; lettura dello schema, delle unità,
  dei nomi delle colonne e degli UCD. **I VOTable locali si leggono
  direttamente con `astropy.io.votable`** (decisione del proprietario del
  2026-10-10); da URL passano dal `14` (P6).
  - **Più tabelle nello stesso file** (più `TABLE` in un VOTable, più HDU di
    tabella in un FITS): come per le immagini (D11-4), con una sola tabella
    si apre quella; con più tabelle serve il parametro `table` (indice),
    altrimenti `TABLE_CHOICE_REQUIRED` con l'elenco (indice, nome, righe,
    colonne), che dà anche `list_tables`.
  - **Provenienza dei file locali:** origine = percorso assoluto, data =
    momento della lettura (UTC), più la data di modifica del file.
- **Formati delle tabelle (H22, sez. 8.1 del manuale di Aladin, ed. giugno
  2022):** VOTable, tabelle FITS ASCII e binarie, CSV, TSV, **BSV** (valori
  separati da spazi), **IPAC TBL**, **formato SExtractor** e **ASTRORES**
  (predecessore di VOTable, letto per compatibilità), più **ECSV** di
  `astropy` (D14-10, decisa il 2026-10-11: è il formato in cui il 14
  esporta le tabelle con unità; unità, UCD, descrizioni e valori mancanti
  si leggono dall'intestazione; **colonne di posizione, sistema,
  equinozio ed epoca** di un ECSV scritto da AstroTwo si leggono dai
  metadati YAML `A2POSITIONS` (decisione del proprietario del
  2026-10-11; avviso `POSITIONS_FROM_ECSV`, nessun `FRAME_UNKNOWN`);
  metadati non utilizzabili o in disaccordo con le colonne degli UCD →
  avviso `ECSV_POSITIONS_INVALID`, nessuna scelta). Tutti i
  formati si leggono con `astropy.io.votable`, `astropy.io.ascii` e
  `astropy.io.fits`,
  **tranne ASTRORES**, letto da un lettore nel modulo con **`defusedxml`**
  (D13-7; protezione da file XML non fidati).
  - **Lettore ASTRORES (D13-14, decisa dal proprietario il 2026-10-10,
    tranne il punto b):** segue la **DTD pubblica del CDS** (`astrores.dtd`
    v0.9, 17-04-2000): radice `ASTRO`; `DEFINITIONS`/`COOSYS` (anche dentro
    `RESOURCE` e `TABLE`); `RESOURCE` e `TABLE` (più tabelle → `table`, come
    sopra); `FIELD` con `ID`, `name`, `unit`, `ucd`, `datatype` (`F`, `D`,
    `E` → `float64`; `I` → intero; `L` → booleano; `A` → testo), `width`,
    `precision`, `format`, `ref`; il nome della colonna è il `NAME` del
    campo, altrimenti `name`, altrimenti `ID`; dati in `CSV` (`colsep`,
    default tabulazione; `recsep`, default a capo; `headlines` righe da
    saltare, contate dopo aver tolto i record vuoti) o in
    `TABLEDATA`/`ROW`/`CELL` (anche qui `headlines`); celle vuote = valori
    mancanti; campo senza `datatype` = testo; booleani `T`/`F`, `true`/
    `false`, `1`/`0`; due campi con lo stesso nome → `ASTRORES_UNREADABLE`;
    `COOSYS` senza `system` = `eq_FK5` (default della DTD); equinozio ed
    epoca scritti come numero (es. `2000.`) si leggono come anni
    **giuliani** per FK5 e ICRS e **besseliani** per FK4 (convenzione dei
    due sistemi), dichiarati come `J2000`/`B1950`.
    (a) Un campo dichiarato numerico in gradi (`F`/`D`/`E` con unità `deg`)
    i cui dati sono **sessagesimali** si converte in gradi con il modulo 10
    (`astropy.coordinates.Angle`: ore per l'ascensione retta, gradi per la
    declinazione, secondo l'UCD della posizione), si conserva **anche la
    colonna di testo originale** (`<nome>_text`) e si dà l'avviso
    `ASTRORES_TYPE_MISMATCH` (tipo dichiarato diverso dai dati); un campo
    numerico con dati non numerici e non sessagesimali → testo con lo
    stesso avviso; un campo sessagesimale senza UCD che dica ascensione
    retta o declinazione resta testo con l'avviso (ore o gradi non si
    indovinano). (b) UCD1 → UCD1+ (D13-14b, decisa il 2026-10-10): si
    traducono **solo le parole UCD1 scritte nella raccomandazione IVOA
    sugli UCD** (REC 2005-08-12): `POS_EQ_RA_MAIN` → `pos.eq.ra;meta.main`,
    `POS_EQ_RA` → `pos.eq.ra`, `POS_EQ_DEC_MAIN` → `pos.eq.dec;meta.main`,
    `POS_EQ_DEC` → `pos.eq.dec` (§3.1 elenca le quattro parole e le
    scompone in `POS_EQ_RA`, `POS_EQ_DEC` e `MAIN`; l'appendice A scrive
    esplicitamente solo `POS_EQ_DEC_MAIN` = `pos.eq.dec;meta.main` e
    `pos.eq.dec` per una sola declinazione), con l'avviso
    `UCD1_TRANSLATED` e l'UCD originale conservato; **tutte le altre** restano
    come sono, con `UCD1_NOT_TRANSLATED` e conferma dell'utente. Il servizio
    di traduzione del CDS (opzione esplicita, dichiarata nel risultato come
    "traduzione CDS") è rimandato, a bassa priorità (D13-14c, 2026-10-11). La traduzione avviene prima della
    lettura dei dati, quindi decide anche ore o gradi per i sessagesimali.
    (c) Un
    `ref` scritto `#id(...)` o `#id($...)` (forma non conforme alla DTD, che
    vuole un IDREF) si accetta con l'avviso `ASTRORES_NONCONFORMING_REF`.
    (d) `DATA` con `LINK` esterno (D13-17, decisa il 2026-10-11): si
    leggono **solo i `LINK` con `href`** (`gref` e `action` →
    `ASTRORES_UNREADABLE`); il **formato si decide dal `content-type`
    dichiarato nel `LINK`** (attributo della DTD), con i lettori già
    presenti nel modulo: `text/csv` → CSV, `text/tab-separated-values` →
    TSV, `application/x-votable+xml` → VOTable, `application/fits` → FITS
    (parametri come `charset` ignorati; `text/csv` con `header=absent` di
    RFC 4180 rifiutato, perché il lettore CSV vuole la riga dei nomi);
    `content-type` assente o diverso → `ASTRORES_UNREADABLE`, **niente
    formati indovinati** (né dal contenuto né dall'intestazione HTTP). I
    dati si scaricano con il 14 (prima la cache, `load_table`; `read_table`
    resta senza rete e rimanda a `load_table`); un `href` relativo si
    risolve solo sull'URL di un documento scaricato da URL, altrimenti
    serve un URL `http(s)`. **Accordo tra FIELD e dati collegati** (scelta
    del 2026-10-11, da confermare): la tabella collegata deve avere **le
    stesse colonne, con gli stessi nomi e nello stesso ordine** dei
    `FIELD`; unità e UCD presenti in entrambi devono coincidere, un `FIELD`
    numerico (`F`, `D`, `E`, `I`) vuole dati numerici e uno `L` dati
    booleani; ogni differenza → `ASTRORES_UNREADABLE` con l'elenco, nessuna
    scelta tra i due. Unità, UCD (tradotti come al punto b), descrizioni e
    `ref` dei `FIELD` completano la tabella; i `COOSYS` dell'ASTRORES
    valgono per le posizioni. Avvisi `ASTRORES_LINK` (URL, formato,
    content-type) e `ASTRORES_LINK_SOURCE` (data, copia in cache o no).
    (e) Test su file nostri scritti
    dalla DTD, più l'esempio pubblico del CDS letto in un test di rete,
    **senza copiarlo nel repository**.
  - **Riconoscimento dal contenuto, non dall'estensione (decisione del
    proprietario del 2026-10-10):** FITS = firma `SIMPLE  =` con almeno una
    HDU di tabella; XML = radice `VOTABLE` (VOTable) o `ASTRO` (ASTRORES);
    ECSV = prima riga non vuota che inizia con `# %ECSV` (dichiarazione
    obbligatoria dello standard ECSV; D14-10);
    IPAC = intestazione con righe che iniziano con `\` o `|`; SExtractor =
    righe d'intestazione `# 1 NOME`. Per i testi delimitati la regola si
    applica alle prime 20 righe non vuote e non di commento (`#`): **TSV**
    se tutte contengono una tabulazione e nessuna una virgola; **CSV** se
    tutte contengono lo stesso numero (≥ 1) di virgole e nessuna una
    tabulazione; **BSV** se nessuna contiene tabulazioni o virgole e tutte
    hanno lo stesso numero (≥ 2) di campi separati da spazi; **in ogni altro
    caso** errore `FORMAT_AMBIGUOUS`, che chiede il parametro `format`
    (`csv`, `tsv`, `bsv`, `ipac`, `sextractor`, `ecsv`). Con `format` esplicito il
    riconoscimento non si fa e il formato usato è scritto nel risultato.
- **Unità delle colonne (decisione del proprietario del 2026-10-10):** una
  stringa di unità valida nei formati standard **FITS** o **VOUnit** di
  `astropy.units` (come D18-2) dà l'unità della colonna (la stringa è quella
  fornita dal lettore della libreria: per i VOTable astropy non conserva il
  testo originale e dà la propria lettura, o il testo stesso se non lo
  riconosce — verificato con astropy 8.0.1); una stringa non
  valida (es. `---` di VizieR) lascia la colonna **caricata con la stringa
  originale e l'avviso `UNIT_UNRECOGNIZED`**, senza alcuna conversione; una
  colonna senza unità è dichiarata adimensionale.
- **Limiti (D13-4 e A10 per i cataloghi, decisi dal proprietario il
  2026-10-10):** **tetto di 1 milione di righe per tabella, configurabile**
  (`TableLimits.max_rows`), più la **stima della memoria** confrontata con il
  **limite delle operazioni** (`TableLimits.operation_bytes`, **4 GB di
  default, configurabile**: stesso valore e stesso significato del limite
  delle operazioni dell'11, D11-11; l'interfaccia `40` li imposta con
  un'unica preferenza). Oltre il tetto: `TABLE_TOO_LARGE`; oltre il limite
  delle operazioni: `MEMORY_LIMIT_EXCEEDED`; **mai un troncamento
  silenzioso, nessun caricamento progressivo nel livello 1**. Il controllo
  si fa **prima di caricare** quando il file lo permette: FITS dalle parole
  chiave dell'intestazione (`NAXIS2` e larghezza della riga); testi
  delimitati, IPAC e SExtractor contando righe e colonne con una lettura in
  sequenza che non conserva nulla (stima: righe × colonne × 8 byte, i
  numeri in `float64`, più la dimensione del file per i testi); VOTable e
  ASTRORES (XML) con la dimensione del file come stima prima della lettura e
  il numero di righe dichiarato controllato subito dopo il parsing. **Dopo
  ogni lettura** si ricontrollano righe e memoria esatte della tabella
  (somma dei byte delle colonne).
- **Colonne di posizione e corpo (decisione del proprietario del
  2026-10-10):** il nucleo ricava le colonne di posizione **solo da UCD e
  metadati, mai dai nomi**: coppie `pos.eq.ra`/`pos.eq.dec`,
  `pos.galactic.lon`/`pos.galactic.lat`, `pos.ecliptic.lon`/`pos.ecliptic.lat`
  (con più coppie vale quella con `meta.main`; più coppie senza `meta.main`
  → nessuna scelta, avviso); il sistema di riferimento dal `COOSYS` del
  VOTable collegato alle colonne (sistema, equinozio, epoca; per
  `system` valgono i termini del **vocabolario IVOA `refframe`** —
  `ICRS`, `FK5`, `FK4`, `GALACTIC`, `SUPER_GALACTIC`, usati per esempio da
  TAPVizieR — e i vecchi termini VOTable `eq_FK5`, `eq_FK4`, `galactic`,
  `supergalactic`, verificato il 2026-10-11; equinozio ed epoca scritti
  come numero si leggono giuliani per FK5 e ICRS e besseliani per FK4,
  come per ASTRORES) o, per le
  coordinate galattiche, dall'UCD stesso; senza sistema dichiarato le
  colonne sono note ma il sistema resta **sconosciuto** (le funzioni che lo
  richiedono danno `FRAME_UNKNOWN`). **In più** `suggest_position_columns`
  **suggerisce** colonne candidate **dal nome** (es. `ra`/`dec`,
  `raj2000`/`dej2000`, `ra_icrs`/`de_icrs`, `glon`/`glat`, `elon`/`elat`,
  senza distinguere maiuscole e minuscole), ciascuna **marcata come
  suggerimento**, con il sistema eventualmente indicato dal nome come sola
  ipotesi: l'interfaccia le propone, l'utente conferma con
  `confirm_position_columns` (colonne e sistema espliciti; la conferma è
  scritta nella provenienza). **Epoca ed equinozio dei metadati conservati
  (D41-6, decisione del proprietario del 2026-10-21):** se le colonne
  confermate sono le stesse già trovate nei metadati (`positions` con
  `source = "ucd"`, cioè collegate al `COOSYS`, all'`utype` MANGO o ai
  metadati ECSV) e il sistema confermato è lo stesso, la nuova tabella
  **conserva l'epoca dichiarata** (e l'equinozio, se `equinox` non è dato)
  e la usa per la propagazione (`propagate`, `display_positions`), con
  l'avviso `EPOCH_FROM_METADATA` e la voce nella storia; con colonne o
  sistema diversi l'epoca **non si conserva** e non si assume mai (le
  funzioni di propagazione danno `EPOCH_INVALID` senza un'altra fonte).
  Possibile aggiunta futura, non ora: un parametro `source_epoch` esplicito. **Senza UCD né conferma:**
  `NO_COORD_COLUMNS` (avviso al caricamento; errore per le funzioni di
  posizione) e `body` non ricavabile (`BODY_UNKNOWN`). **Corpo:** `celestial`
  quando le colonne di posizione sono celesti (UCD `pos.eq`, `pos.galactic`,
  `pos.ecliptic`, o conferma con un sistema celeste); coordinate planetarie
  (UCD `pos.bodyrc`) secondo `19-core-dati-planetari.md`, finché il 19 non
  c'è solo con `body` dichiarato dall'utente, altrimenti `BODY_UNKNOWN`.
- **Plottaggio come definizione (D4, P3):** regole per simbolo, colore e
  dimensione in funzione delle colonne — questo modulo produce le regole e
  il loro esito per ogni record; il disegno è di
  `42-ui-pannello-cataloghi.md`. **Regola (decisione del proprietario del
  2026-10-10):** un'espressione di `search` (senza prefisso) che dice a
  quali record si applica (assente = tutti) + **forma** dall'elenco chiuso
  `circle`, `square`, `diamond`, `triangle`, `cross`, `plus`, `dot` +
  **colore** `#RRGGBB` + **dimensione** in pixel, costante oppure funzione
  lineare di una colonna con intervallo esplicito (`column`, `vmin`, `vmax`,
  `size_min`, `size_max`, entrambe positive; `size_min` > `size_max` è
  ammesso, per i simboli più grandi alle magnitudini più piccole; valori
  fuori intervallo portati agli estremi). Le
  regole sono ordinate: ogni record prende **la prima regola che lo
  seleziona**; i record senza regola non si disegnano; un record con il
  valore della colonna della dimensione mancante o non finito non si
  disegna con quella regola e **non passa alla regola successiva**
  (conteggio nel risultato). La tabella non cambia.
- **Filtri e ricerca, due concetti separati (D6, corretto):**
  - i **filtri** decidono **come disegnare** le sorgenti (regole di disegno
    qui sopra);
  - la **selezione dei record per espressione** è il comando **`search`**,
    che restituisce l'insieme dei record che soddisfano un'espressione.
  - **Grammatica di `search` (D13-1; forma formale scritta il 2026-10-10,
    decisione del proprietario):**

    ```
    espressione  = [ prefisso ] , disgiunzione ;
    prefisso     = "+" | "-" ;                 (solo come primo carattere)
    disgiunzione = congiunzione , { "||" , congiunzione } ;
    congiunzione = termine , { "&&" , termine } ;
    termine      = "(" , disgiunzione , ")" | confronto | testo ;
    confronto    = operando , operatore , valore ;
    operando     = colonna | "|" , colonna , "|" ;
    colonna      = "${" , nome , "}" | parola ;
    operatore    = "=" | "!=" | "<=" | ">=" | "<" | ">" ;
    valore       = numero | stringa | parola ;
    testo        = stringa | parola ;
    stringa      = '"' , { carattere | '\"' | '\\' } , '"'
                 | "'" , { carattere | "\'" | '\\' } , "'" ;
    parola       = carattere-parola , { carattere-parola } ;
    numero       = [ "+" | "-" ] , cifre , [ "." , cifre ] , [ ( "e" | "E" ) , [ "+" | "-" ] , cifre ]
                 | [ "+" | "-" ] , "." , cifre , [ esponente ] ;
    ```

    `carattere-parola` = ogni carattere tranne gli spazi e `( ) | & = ! < > " '`;
    `nome` = ogni carattere tranne `}`. Gli spazi tra i simboli sono
    liberi. **Precedenza:** `&&` prima di `||`; le parentesi la cambiano.
    **Significato:**
    - una **colonna** scritta come `parola` deve essere il nome esatto di
      una colonna (maiuscole e minuscole contano); `${…}` serve per i nomi
      con spazi o simboli; colonna inesistente → `EXPRESSION_INVALID`;
    - **confronto numerico** (colonne numeriche e booleane, queste ultime
      come 0/1): il valore deve essere un `numero`, **nell'unità della
      colonna** (nessuna unità nell'espressione); `=` è l'uguaglianza
      esatta; `|colonna|` è il valore assoluto e vale solo per le colonne
      numeriche;
    - **confronto di testo** (colonne di testo): solo `=` e `!=` (gli altri
      operatori → `EXPRESSION_INVALID`); il valore è un modello con i jolly
      `*` (qualsiasi sequenza, anche vuota) e `?` (un carattere), `\*` e
      `\?` per i caratteri stessi; il modello deve coprire **tutto** il
      valore della cella, di cui si ignorano gli spazi finali (riempimento
      dei testi FITS);
    - **testo da solo** (`testo` senza operatore): il record è selezionato
      se **almeno una colonna di testo** corrisponde al modello;
    - **maiuscole e minuscole:** nel testo con i jolly **non contano per
      default** (decisione del proprietario del 2026-10-10); l'opzione
      `case_sensitive=True` le fa contare;
    - **valori mancanti** (mascherati) **e non finiti** (NaN): mai
      selezionati, da nessun confronto (neppure `!=`) né dal testo;
    - **prefissi** `+` e `-`: aggiungono i record trovati alla selezione
      corrente (`+`) o li tolgono (`-`); la selezione corrente si passa
      come parametro `selection` (una maschera booleana per record) ed è
      **obbligatoria** con un prefisso (altrimenti `EXPRESSION_INVALID`);
      senza prefisso il risultato è il solo insieme trovato;
    - espressione vuota o non conforme → `EXPRESSION_INVALID` con la
      posizione (carattere) dell'errore; l'espressione è **validata per
      intero prima dell'esecuzione** e non è mai eseguita come codice.
- **Propagazione delle posizioni (D9, P5)** e **freccia del moto proprio
  (D10, P5):** portare le posizioni a un'epoca richiesta e rappresentare il
  moto proprio; calcolo: modulo 10/Astropy.
  - **Epoca di origine (decisione del proprietario del 2026-10-10):** dalla
    colonna con UCD `time.epoch` (un'epoca per riga) o dall'epoca del
    `COOSYS`; altrimenti parametro obbligatorio; **mai assunta** (D10-2);
    scala di tempo sempre dichiarata (DC1). Precisazioni (2026-10-10, P5):
    la colonna d'epoca dev'essere in anni (anni giuliani, letti con la
    regola del modulo 10); con l'epoca nei metadati il parametro
    `source_epoch` non si usa (passarlo → `EPOCH_INVALID`, nessuna scelta
    silenziosa); più colonne `time.epoch` → `EPOCH_INVALID`.
  - **Moto proprio in ascensione retta:** se include il fattore cos δ va
    **dichiarato** (metadati della colonna o parametro
    `pm_ra_includes_cosdec`, senza default); mai assunto.
  - **Parallasse mancante o non positiva (decisione del proprietario del
    2026-10-10):** le righe **non si escludono**: si propagano **solo con il
    moto proprio, senza effetti prospettici**, marcate riga per riga, con il
    loro conteggio nel risultato. Il calcolo è del modulo 10
    (`propagate_position(..., proper_motion_only=True)`, D13-12).
  - **Righe senza moto proprio** (valore mancante o non finito in una delle
    due colonne; stesso trattamento per posizione o epoca mancanti):
    nella posizione propagata diventano **valore mancante marcato**, con
    conteggio nel risultato; **non si assume un moto proprio nullo**
    (D13-12).
  - **Risultato di `propagate`:** una **nuova** tabella con due colonne
    aggiunte, `<lon>_prop` e `<lat>_prop` (stesse unità delle originali,
    epoca di arrivo nei metadati della colonna), e una colonna
    `<lon>_prop_mode` con il modo di ogni riga: `full` (moto proprio e
    parallasse), `pm_only` (solo moto proprio), `missing` (nessun moto
    proprio: posizione mascherata); le colonne originali restano intatte;
    nomi già presenti → `COLUMN_NAME_EXISTS`. Il report dà epoca di origine
    (e la sua fonte), epoca di arrivo, uso del cos δ, conteggi per modo e le
    note del modulo 10.
  - **Frecce del moto proprio:** dalla posizione all'epoca della tabella
    alla posizione propagata di `scale` anni (**parametro obbligatorio**,
    un intervallo di tempo con unità, non nullo), con le stesse regole di
    `propagate` per parallasse e righe mancanti.
  - **Posizioni all'epoca di visualizzazione (`display_positions`,
    decisione del proprietario del 2026-10-14):** applica **D10-2** in un
    solo passo, perché chi disegna un catalogo su un'immagine non debba
    ricomporre a mano epoca, propagazione e conteggi. Epoca di
    visualizzazione: **l'epoca dell'immagine se nota** (`image_epoch` del
    WCS del 10, cioè `MJD-OBS`/`DATE-OBS`, con la sua scala di tempo);
    **altrimenti J2000** (`J2000.0`, scala TT), anche senza immagine; oppure
    un'epoca **indicata dall'utente**. L'epoca usata e la sua **fonte**
    (immagine, J2000 per epoca dell'immagine non dichiarata, J2000 senza
    immagine, utente) sono sempre scritte nel risultato. Il calcolo è
    quello di `propagate` (stesse regole per epoca di origine, cos δ,
    parallasse e righe mancanti; modulo 10). Il risultato dà in un passo:
    le **posizioni all'epoca di visualizzazione** (gradi, nel sistema della
    tabella), **quali righe si possono disegnare** (quelle non `missing`),
    il **modo** di ogni riga e i **conteggi per modo**, l'epoca usata con
    la sua fonte, l'epoca di origine con la sua fonte, e lo **spostamento**
    di ogni riga tra l'epoca della tabella e quella di visualizzazione
    (separazione angolare in arcosecondi con `astropy`, mancante per le
    righe non disegnabili), con media e massimo sulle righe disegnabili.
    Le posizioni disegnabili sono date anche come coordinate del 10
    (`SkyFrame`) all'epoca di visualizzazione, pronte per la conversione in
    pixel. Le colonne originali restano intatte (nuova tabella come in
    `propagate`). Le misure (crossmatch, distanze, MOC) **non** usano le
    posizioni di visualizzazione: restano all'epoca dei dati.
  - **Filtro temporale `time_filter` (D13-16, decisa il 2026-10-10):**
    colonna **indicata dall'utente**; formato e scala di tempo dal
    **`TIMESYS`** del VOTable collegato alla colonna (`timeorigin`
    `MJD-origin`, `JD-origin` o numero JD con valori in giorni; senza
    `timeorigin`, valori in anni giuliani; scale TT, TDB, TCB, TCG, TAI, UTC,
    UT), altrimenti **parametri obbligatori** `time_format` (formato di
    `astropy.time`) e `scale`; con il `TIMESYS` i parametri non si passano;
    intervallo **chiuso `[inizio, fine]`** di oggetti `Time`; valori mancanti
    mai selezionati e contati; il risultato dichiara formato, scala e
    fonte.
- **Filtro temporale e cursore epoca (H3, P5):** selezionare i record per
  epoca di osservazione e spostare l'epoca di visualizzazione (con i moduli
  10 e 41). **Epoca di default decisa con D13-2 (2026-10-04):** l'epoca di
  ogni dato si legge dai suoi metadati e **non si assume mai**; epoca di
  visualizzazione = epoca del dato mostrato (per le immagini: epoca
  dell'immagine se nota, altrimenti J2000; per i cataloghi: la **propria
  epoca di riferimento**); **l'epoca usata è sempre scritta nel risultato**.
- **Strumenti di tabella avanzati (H8, P4):** colonne calcolate,
  sottoinsiemi, grafico x-y, istogramma delle colonne (**bin obbligatori**:
  numero o bordi espliciti), vista a record, descrizione delle colonne,
  **statistiche di una colonna** (minimo, massimo, media, deviazione
  standard di `numpy` con `ddof = 0`, scritto nel risultato, conteggio dei
  valori validi e dei mancanti); **DataLink: la
  colonna vive qui, la risoluzione dei link è di `14-core-protocolli-vo.md`**
  (confine deciso con D13-6 il 2026-10-04; riconoscimento della colonna:
  in **P6**, dopo il 14, D13-11).
- **Colonne calcolate (H8, sez. 5.13, P4):** nuova colonna con **nome**
  obbligatorio e, facoltativi, **unità**, **UCD** e **numero di decimali**
  mostrati; espressione con riferimenti alle colonne nella forma
  `${nome_colonna}`, con gli operatori e le funzioni della calcolatrice
  algebrica di `18-core-calcolatrici.md` (stesso elenco e stessa tecnica a
  elenco chiuso, D18-1; nessuna esecuzione di codice). **La tabella delle
  funzioni vive in `catalogs.py` e il 18 la importa** (D13-8, decisa il
  2026-10-10: il 18 dipende già dal 13, nessuna dipendenza circolare).
  **`skydist(ra1, dec1, ra2, dec2)`** (gradi in ingresso e in uscita) si
  calcola qui con `astropy.coordinates.angular_separation`; il 17
  (`angular_distance`) usa **questa stessa implementazione**, nessun
  duplicato (D13-10, decisa il 2026-10-10). La tabella (`FUNCTIONS`,
  `CONSTANTS`) lavora su valori `float64` senza unità; `min` e `max`
  accettano due o più argomenti; `round` è oggi `numpy.round` (metà al
  pari, decisa con D13-15).
  - **Numeri e unità (D13-15, decisa il 2026-10-10):** in `+`, `-`, `%`,
    `min`, `max` un **numero scritto** (o un'espressione di soli numeri e
    costanti) **prende l'unità dell'altro operando** (come in `search`);
    in `*`, `/` e come esponente di `^` resta adimensionale. Così
    `${mag} - 0.12` dà una colonna in `mag` (T4). `sin`/`sind`: su colonne
    angolari stesso risultato (astropy converte l'angolo); su numeri senza
    unità `sin` in radianti e `sind` in gradi, come nel 18. `skydist` dà
    gradi.
  - **Altre regole (2026-10-10):** espressione analizzata con `ast` a
    elenco chiuso (operatori, funzioni di `FUNCTIONS`, costanti, numeri,
    `${colonna}`; `**` non ammesso, la potenza è `^`), validata per intero
    prima del calcolo; posizione dell'errore sul testo originale (fine
    dell'espressione quando il parser non la indica); un valore mancante in
    una colonna usata dà un valore mancante; colonne con unità non
    riconosciuta → `UNIT_INCOMPATIBLE` (nessun calcolo con unità ignote);
    `unit` facoltativa: converte il risultato o lo dichiara se è senza
    unità; stima della memoria con il limite delle operazioni.
  Calcolo vettoriale in `float64` con `numpy`; se le colonne hanno unità, il
  calcolo passa da `astropy.units` e unità incompatibili danno errore. La
  colonna è marcata come calcolata, con l'espressione come provenienza, ed
  è salvata con le altre.
- **Operazioni non distruttive (D13-5; precisazione del proprietario del
  2026-10-10):** `calculated_column` e `subset` restituiscono una **nuova**
  tabella; con `inplace=True` modificano quella data e **il report lo
  cita**.
- **Cache (A7; decisione del proprietario del 2026-10-10):** **una sola
  cache delle interrogazioni, nel `14`**; nessuna cache propria (CA4).
- **Sottoinsiemi salvati (D13-13, decisa il 2026-10-10):** **non** nella
  cache (che può eliminarli): si salvano in un **file scelto dall'utente**,
  in **VOTable con provenienza** (origine e data della tabella di partenza,
  operazioni, selezione usata, data del salvataggio come `INFO`; UCD e
  `COOSYS` delle colonne di posizione conservati, così il file riletto con
  `read_table` ha le stesse posizioni). La sessione di
  `05-comandi-sessione.md` conterrà solo il riferimento al file (D17-3).

## 4. Cosa NON fa

- Non comunica con la rete: query, cone search e download sono di
  `14-core-protocolli-vo.md`; il cross-match è di `15-core-crossmatch.md`.
- Non conserva in cache i risultati delle interrogazioni: è del `14`.
- Non disegna: le tabelle e i simboli li rende la UI (41/42).
- Non esporta i file: l'esportazione è di `14-core-protocolli-vo.md` (D13).
- Non calcola coordinate: propagazione e moto proprio passano per il modulo 10.
- Non ricava le colonne di posizione dai nomi: dai nomi le **suggerisce** e
  basta.
- Non produce curve di luce: restano `22-analisi-curve-di-luce.md`.
- Non crea MOC: `16-core-moc.md`.

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `04-cache.md` (cache comune A7, sottoinsiemi salvati),
  `10-core-coordinate-wcs.md` (propagazione, moto proprio, coordinate di
  ricerca), `14-core-protocolli-vo.md` (download e servizi; solo P6).
- **Usato da:** `15-core-crossmatch.md`, `16-core-moc.md`,
  `18-core-calcolatrici.md` (anche la tabella delle funzioni, D13-8),
  `19-core-dati-planetari.md`, `20-analisi-fotometria.md`,
  `42-ui-pannello-cataloghi.md`, `41-ui-visualizzatore-cielo.md`
  (`display_positions`, `set_plot_rules`, `record_view`),
  `05-comandi-sessione.md` (comandi dei cataloghi), `33-ia-query-adql.md`.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `catalog_id` | stringa | id catalogo CDS | es. "I/239/hip_main" (esempio di formato, id da verificare); P6 |
| in | file tabella | percorso (URL in P6) | VOTable, FITS, CSV, TSV, BSV, IPAC TBL, SExtractor, ECSV, ASTRORES | natura riconosciuta dal contenuto (H22) o `format` esplicito |
| in | `table` | intero ≥ 0 | indice della tabella nel file | obbligatorio con più tabelle |
| in | `limits` | `TableLimits` | righe, byte | 1 milione di righe, 4 GB |
| in | `expression` | stringa | grammatica di §3 (comando `search`) | validata prima dell'esecuzione (D13-1) |
| in | `selection` | maschera booleana | una per record | obbligatoria con i prefissi `+`/`-` |
| in | `case_sensitive` | booleano | default `False` | testo con i jolly |
| in | regole di disegno | lista di `PlotRule` | §3 | non è una selezione |
| in | colonne di posizione confermate | 2 nomi + sistema (+ equinozio) | — | conferma dell'utente |
| in | `epoch` | epoca | anno giuliano o ISO 8601 con scala | per propagazione/H3 |
| in | moto proprio | float64 | mas/yr, mas | colonne del catalogo; cos δ dichiarato |
| out | tabella | `CatalogTable` (`astropy.table.Table` + metadati) | colonne con unità, UCD e nomi | con provenienza, posizioni, `body`, avvisi |
| out | `body` | stringa o assente | `celestial` o nome IAU del corpo | obbligatorio (D19-3): mai assunto; assente → `BODY_UNKNOWN` |
| out | suggerimenti di posizione | lista | coppie di colonne, sistema ipotizzato, motivo | marcati "suggerimento" |
| out | selezione | maschera booleana | — | record soddisfacenti |
| out | esito delle regole di disegno | array per record | indice della regola, forma, colore, dimensione | tabella invariata |
| in | colonna calcolata | nome + espressione + unità, UCD, decimali facoltativi | espressione con `${nome}` | H8 |
| out | colonna calcolata | colonna `float64` con unità, UCD, decimali e provenienza (espressione) | unità dichiarata o derivata | H8 |
| out | statistiche di una colonna | struttura | min, max, media, deviazione standard, conteggi | unità della colonna |

## 7. Interfaccia pubblica

- **`CatalogTable`** (classe): tabella (`astropy.table.Table`) con schema,
  unità, UCD, provenienza (origine, data di lettura, data di modifica del
  file, formato, indice della tabella), colonne di posizione
  (`PositionColumns` o assente), `body`, avvisi, storia delle operazioni,
  limiti usati; `describe_columns()` (nome, tipo, unità o stringa non
  riconosciuta, UCD, descrizione).
- **`TableLimits`** (struttura) — `max_rows` (1 000 000) e `operation_bytes`
  (4 × 10⁹), configurabili.
- **`read_table(source, *, table=None, format=None, limits=TableLimits())`**
  (H22, P1) — file locale: riconosce il formato dal contenuto (o usa
  `format`), controlla i limiti prima di caricare, legge unità, UCD,
  colonne di posizione e corpo; ASTRORES con il lettore `defusedxml` (D13-7,
  P2).
- **`list_tables(source)`** — tabelle del file (indice, nome, righe,
  colonne), per la scelta dell'utente.
- **`load_catalog(catalog_id, *, region=None, max_rows=None,
  allow_partial=False, limits=None, cache=None, refresh=False,
  timeouts=None)`** (P6) — catalogo
  VizieR per identificativo (es. `"II/246/out"`) con `SELECT * FROM "<id>"`
  su TAP VizieR tramite `tap_query` del 14 (D14-9 punto 6), o una voce di
  `FIXED_COLLECTIONS`; `max_rows` di default quello del 14 (100 000);
  identificativo non valido o rifiutato dal servizio → `CATALOG_UNKNOWN`.
  **Con regione (`region=(centro, raggio)`, D13-19 decisa il
  2026-10-11):** solo le righe nel cerchio. Le colonne di posizione si
  trovano dagli **UCD di `TAP_SCHEMA.columns`** del servizio
  (`pos.eq.ra`/`pos.eq.dec`, con più candidate quella `meta.main`; mai dai
  nomi; nessuna univoca → `NO_COORD_COLUMNS`; **nessuna colonna della tabella
  in `TAP_SCHEMA`** → `CATALOG_UNKNOWN`, perché il servizio non conosce
  l'identificativo, come la regola sopra (precisazione del 2026-10-23: prima
  usciva `NO_COORD_COLUMNS`, un messaggio sbagliato; verifica sul servizio
  reale del 2026-10-23: `I/355` e `gaiadr3` non sono tabelle, mentre
  `I/355/gaiadr3` ha due coppie `RA_ICRS`/`DE_ICRS` `;meta.main` e
  `RAJ2000`/`DEJ2000` senza `meta.main`, e vale la prima); il **sistema si legge dal
  `COOSYS`** che il servizio collega a quelle colonne (interrogazione
  `SELECT TOP 0`), mai assunto (assente → `FRAME_UNKNOWN`); il centro si
  converte in quel sistema con il modulo 10 (FK5 con il suo equinozio, FK4
  con equinozio ed epoca) e l'ADQL è `CONTAINS(POINT(sistema, ra, dec),
  CIRCLE(sistema, centro, raggio))`. Raggio angolare con unità in (0°,
  180°], altrimenti `REGION_INVALID`. Il risultato **dichiara** colonne,
  sistema, equinozio, epoca delle posizioni, centro convertito e raggio
  (avviso `REGION`, voce nella storia; `CatalogRegion`). Oltre `max_rows`
  nella regione: `REGION_TOO_LARGE`, oppure `allow_partial=True` come
  sotto. Verifica del 2026-10-11: TAPVizieR scrive in `TAP_SCHEMA` i nomi
  tra virgolette (`"II/246/out"`, `"RAJ2000"`) e collega i campi a un
  `COOSYS` (2MASS `FK5` equinozio `2000.0`; Gaia DR3 `ICRS` epoca
  `2016.0`). **SIMBAD** non collega le colonne a un `COOSYS`: il sistema
  si legge dall'`utype` del modello IVOA MANGO delle due colonne
  (`mango:EpochPosition.longitude[CS.spaceSys=ICRS CT.epoch=J2000]`, D13-20
  decisa il 2026-10-11) ed è dichiarato (avviso `POSITIONS_FROM_MANGO`).
  Vale per ogni tabella senza `COOSYS`: i due `utype` devono coincidere e
  il sistema deve essere `ICRS`, `GALACTIC` o `SUPER_GALACTIC` (FK4/FK5
  richiederebbero un equinozio che MANGO non dà in questa forma); altrimenti
  nessuna scelta (`FRAME_UNKNOWN`). Verifica del 2026-10-11 sulla risposta
  di SIMBAD (`SELECT TOP 0 ra, dec FROM basic`).
  **Senza regione (decisione del proprietario del 2026-10-11):** il
  catalogo si carica solo se il suo numero totale di righe è entro
  `max_rows`; il superamento si conosce dal **troncamento dichiarato dal
  servizio** (`OVERFLOW` di TAP, `MAXREC = max_rows`) o da più righe del
  massimo; allora errore `REGION_REQUIRED`, che indica il parametro
  `region=(centro, raggio)`, oppure `allow_partial=True` esplicito,
  che restituisce le prime `max_rows` righe ricevute dichiarandolo nel
  risultato (avvisi `PARTIAL_CATALOG` e `ROW_LIMIT_EXCEEDED`, voce nella
  storia). Un servizio che troncasse senza dichiararlo non sarebbe
  conforme a TAP e non si può riconoscere: si usano solo i servizi
  dell'elenco del 14.
- **`load_table(source, *, table=None, format=None, limits=None, cache=None,
  refresh=False, timeouts=None)`** (P6) — come `read_table` per un file
  locale (con i descrittori di servizio del VOTable); un URL passa da
  `download_table` del 14 (prima la cache). È anche la via per gli
  ASTRORES con i dati in un `LINK` esterno (D13-17), scaricati con il 14.
- **`CatalogTable.request`** / **`CatalogTable.descriptors`** (P6) —
  richiesta registrata dal 14 (`RequestRecord`) per i dati da rete e
  descrittori di servizio del VOTable.
- **`collection_tree(*, cache=None, refresh=False, timeouts=None)`** (P6,
  D13-18) — `CollectionTree` (`roots` di `CollectionNode` con `id`,
  `title`, `popularity`, `table`, `children`; `ordering` dichiarato;
  fonte, data, richiesta registrata, avvisi; `find(id)`), ordinato come in
  §3.
- **`FIXED_COLLECTIONS`** (P6, D13-3) — gruppo fisso: `simbad` (tabella
  `basic` del TAP di SIMBAD), `I/355/gaiadr3` (Gaia DR3), `II/246/out`
  (2MASS), ognuno con la voce TAP dell'elenco del 14.
- **`datalink_column(table)`** (P6, D13-11, D14-9 punto 14) — colonna
  DataLink: quella citata da un descrittore di servizio DataLink del
  VOTable; altrimenti la colonna degli URL di accesso (UCD `meta.ref.url`,
  o `access_url`) le cui righe dichiarano nella colonna del formato (UCD
  `meta.code.mime`, o `access_format`) il content-type
  `application/x-votable+xml;content=datalink` (forma di ObsCore), con la
  maschera delle righe; nessuna → `None`. La risoluzione dei link è del 14
  (`DataLinkClient`).
- **`suggest_position_columns(table)`** — candidate dal nome, ognuna marcata
  come suggerimento, con il motivo; **`confirm_position_columns(table, lon,
  lat, frame, equinox=None)`** — nuova `CatalogTable` con le colonne
  confermate dall'utente (scritto nella provenienza) e il corpo ricavato;
  epoca ed equinozio dei metadati conservati quando colonne e sistema sono
  gli stessi (D41-6, §3).
- **`search(table, expression, selection=None, case_sensitive=False)`** —
  selezione dei record per espressione (D6); l'espressione è **validata
  prima dell'esecuzione** con la grammatica di §3 (D13-1), altrimenti
  `EXPRESSION_INVALID`; restituisce una maschera booleana, non cambia il
  disegno.
- **`PlotRule`** (struttura) e **`set_plot_rules(table, rules)`** — regole
  di disegno (D4), separate dalla selezione; restituisce per ogni record la
  regola applicata e forma, colore e dimensione, con i conteggi.
- **`propagate(table, epoch, *, pm_ra, pm_dec, pm_ra_includes_cosdec,
  parallax=None, radial_velocity=None, source_epoch=None)`** — posizioni
  all'epoca richiesta (D9, P5); colonne di moto proprio, parallasse e
  velocità radiale per nome; epoca di origine dai metadati (§3) o
  `source_epoch`; restituisce la nuova tabella con le colonne propagate e il
  report (§3); **calcolo: modulo 10 / Astropy**.
- **`proper_motion_arrows(table, scale, *, pm_ra, pm_dec,
  pm_ra_includes_cosdec, parallax=None, radial_velocity=None,
  source_epoch=None)`** — dati per le frecce del moto proprio (D10, P5);
  `scale` intervallo di tempo obbligatorio; il disegno è della UI.
- **`display_positions(table, image_or_epoch, *, pm_ra, pm_dec,
  pm_ra_includes_cosdec, parallax=None, radial_velocity=None,
  source_epoch=None)`** — posizioni all'epoca di visualizzazione (D10-2,
  decisione del proprietario del 2026-10-14; regola in §3).
  `image_or_epoch`: un'immagine con WCS (attributo `wcs`), il WCS del 10
  (`WcsSolution`), un'epoca (`astropy.time.Time` o valore accettato da
  `propagate`, "utente") oppure `None` (nessuna immagine → J2000).
  Restituisce **`DisplayPositions`**: `table` (nuova tabella con le colonne
  di `propagate`), `lon`, `lat` (gradi, NaN per le righe non disegnabili),
  `frame`, `drawable` (maschera), `mode`, `counts`, `epoch`,
  `epoch_source`, `source_epoch`, `pm_ra_includes_cosdec`, `shift`
  (arcosecondi per riga, NaN se non disegnabile), `shift_mean`,
  `shift_max` (`None` se nessuna riga è disegnabile), `coords` (`SkyFrame`
  del 10 delle sole righe disegnabili, nell'ordine di
  `numpy.flatnonzero(drawable)`, all'epoca di visualizzazione), `notes`.
  Nessuna dipendenza dal modulo 11: l'immagine si riconosce dal suo
  attributo `wcs`. **Calcolo: modulo 10 / Astropy.**
- **`calculated_column(table, name, expression, unit=None, ucd=None,
  decimals=None, inplace=False)`** / **`subset(table, selection,
  inplace=False)`** — colonne calcolate e sottoinsiemi (H8, P4);
  **calcolo: `numpy`/`astropy`**.
- **`save_subset(table, selection, path)`** (P4, D13-13) — salva il
  sottoinsieme in un VOTable scelto dall'utente, con provenienza; si
  rilegge con `read_table`.
- **`column_statistics(table, column)`** (P4) — minimo, massimo, media,
  deviazione standard, numero di valori validi e mancanti, con unità.
- **`histogram(table, column, bins)`** / **`xy_plot(table, x, y)`** — dati
  per istogramma (bin obbligatori) e grafico x-y (H8, P4): il calcolo
  numerico è del modulo, il disegno della UI.
- **`record_view(table, index)`** (P4) — tutti i valori di un record con
  unità e UCD; per una colonna array (una maschera per elemento) il valore
  è "mancante" solo se lo sono tutti gli elementi (correzione del
  2026-10-21).
- **`time_filter(table, start, end, *, column, time_format=None,
  scale=None)`** (H3, P5) — selezione per epoca osservativa (D13-16);
  restituisce maschera, formato, scala, fonte e mancanti esclusi.
- **Cache:** nessuna classe propria (CA4); le interrogazioni sono in cache
  nel 14.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `astropy.table` | rappresentazione delle tabelle con unità | standard del dominio |
| `astropy.io.votable` | lettura dei VOTable locali (UCD, `COOSYS`) | standard VO; da URL tramite il 14 |
| `astropy.io.fits` | tabelle FITS ASCII e binarie | standard FITS |
| `astropy.io.ascii` | lettura di CSV, TSV, BSV, IPAC TBL, formato SExtractor (H22) ed ECSV (D14-10) | lettori consolidati della comunità |
| `numpy` | espressioni su colonne, istogrammi, grafici dati | consolidato |
| `astropy.units` | unità delle colonne (formati FITS e VOUnit) | unità esplicite sempre |
| `sqlite3` (tramite `04-cache.md`) | sottoinsiemi salvati (se D13-13 lo conferma) | persistenza semplice e interrogabile |
| `defusedxml` (D13-7) | lettore ASTRORES (H22) protetto contro file XML malevoli | parser XML sicuro per file non fidati; **licenza da verificare prima del codice di P2** |

## 9. Regole e vincoli

- **Filtri ≠ selezioni:** confondere i due è un errore di progettazione
  (correzione D6 di `03-parita-aladin.md`); le API li tengono separati.
- Unità e nomi delle colonne conservati dal sorgente; una colonna senza unità
  è dichiarata adimensionale e non convertita silenziosamente; un'unità non
  riconosciuta resta come stringa, con avviso.
- Le colonne di posizione vengono da UCD e metadati o dalla conferma
  dell'utente; **mai dai nomi**.
- La propagazione delle posizioni usa solo il modulo 10; **epoca di origine e
  moto proprio si leggono dai metadati o sono richiesti, mai assunti**
  (D10-2/D13-2); ogni catalogo dichiara la **propria epoca di riferimento**;
  l'epoca usata è sempre scritta nel risultato.
- Nessuna tabella oltre il tetto di righe o il limite delle operazioni:
  errore prima di caricare, mai un troncamento silenzioso.
- Le espressioni `search` sono valutate in codice deterministico (non da un
  modello linguistico) e **validate per intero prima dell'esecuzione** con
  la grammatica di §3 (D13-1).
- **Operazioni sulle tabelle (D13-5, decisa il 2026-10-04):** sempre **non
  distruttive**; la modifica in posto (`inplace=True`) solo con **flag
  esplicito citato nel report** — nessuna perdita di dati silenziosa, piena
  riproducibilità.

- **Corpo di riferimento (`body`, D19-3 decisa il 2026-10-08):** ogni tabella porta
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
| Catalogo sconosciuto | errore con riferimento all'id | `CATALOG_UNKNOWN` |
| `load_catalog` senza regione su un catalogo con più di `max_rows` righe | nessuna tabella; si chiede una regione o `allow_partial=True` | `REGION_REQUIRED` |
| `load_catalog` con `allow_partial=True` oltre `max_rows` | prime `max_rows` righe, dichiarate | avvisi `PARTIAL_CATALOG`, `ROW_LIMIT_EXCEEDED` |
| Regione con raggio senza unità angolare, non positivo o oltre 180° | rifiuto | `REGION_INVALID` |
| Regione con più di `max_rows` righe | nessuna tabella; ridurre il raggio o `allow_partial=True` | `REGION_TOO_LARGE` |
| Regione: colonne di posizione non univoche negli UCD di `TAP_SCHEMA` | rifiuto | `NO_COORD_COLUMNS` |
| Regione: nessuna colonna della tabella in `TAP_SCHEMA` (identificativo che non è una tabella, es. `I/355`) | rifiuto con riferimento all'id (2026-10-23) | `CATALOG_UNKNOWN` |
| Regione: sistema delle colonne non dichiarato con un `COOSYS` né con l'`utype` MANGO (D13-20) | rifiuto, nessun sistema assunto | `FRAME_UNKNOWN` |
| Regione usata | righe nel cerchio; colonne, sistema, centro convertito e raggio dichiarati | avviso `REGION` |
| Record del MocServer che non è una collezione VizieR | escluso dall'albero | avviso `COLLECTION_SKIPPED` |
| Collezioni senza `vizier_popularity` (o con un valore non intero) | dopo le altre, in ordine naturale | avvisi `POPULARITY_MISSING`, `POPULARITY_INVALID` |
| File assente o non leggibile | nessuna tabella aperta, errore con il percorso | `TABLE_UNREADABLE` |
| Tabella senza colonne di posizione da UCD/metadati né confermate | caricamento riuscito con avviso; le funzioni di posizione danno errore | `NO_COORD_COLUMNS` |
| Colonne di posizione senza sistema di riferimento dichiarato | funzioni che lo richiedono rifiutate | `FRAME_UNKNOWN` |
| Più tabelle nel file e `table` non indicato | nessuna tabella aperta; errore con l'elenco | `TABLE_CHOICE_REQUIRED` |
| `table` inesistente | rifiuto con l'elenco delle tabelle | `TABLE_CHOICE_REQUIRED` |
| Testo delimitato non classificabile con la regola di §3 | nessuna tabella aperta; si chiede `format` | `FORMAT_AMBIGUOUS` |
| Formato di tabella non riconosciuto | elenco dei formati supportati | `FORMAT_UNSUPPORTED` |
| Righe oltre il tetto (`max_rows`) | nessuna tabella aperta, errore con righe e tetto | `TABLE_TOO_LARGE` |
| Memoria stimata oltre il limite delle operazioni | nessun dato caricato, errore con stima e limite | `MEMORY_LIMIT_EXCEEDED` |
| Unità di colonna non valida in FITS/VOUnit | colonna caricata con la stringa originale, nessuna conversione | avviso `UNIT_UNRECOGNIZED` |
| Espressione `search` non conforme alla grammatica | rifiuto con la posizione dell'errore nell'espressione | `EXPRESSION_INVALID` |
| Regola di disegno non valida (forma o colore fuori elenco, intervallo della dimensione non valido) | rifiuto con il campo non valido | `PLOT_RULE_INVALID` |
| Mancano le colonne di moto proprio per la propagazione | errore che indica le colonne mancanti | `PROPER_MOTION_MISSING` |
| Epoca richiesta non valida | rifiuto dell'input | `EPOCH_INVALID` |
| `display_positions` con un'immagine senza epoca dichiarata (o senza WCS) o senza immagine | epoca di visualizzazione J2000 (D10-2), fonte dichiarata nel risultato | — |
| `display_positions` con `image_or_epoch` di tipo non riconosciuto | rifiuto, nessuna epoca assunta | `EPOCH_INVALID` |
| Tipo colonna non supportato per un'operazione | errore con tipo atteso e trovato | `COLUMN_TYPE_UNSUPPORTED` |
| Corpo (`body`) non ricavabile dai metadati né dal sistema di coordinate | dato aperto da solo, non sovrapposto né combinato | `BODY_UNKNOWN` |
| File ASTRORES non conforme alla DTD | rifiuto esplicito con la causa | `ASTRORES_UNREADABLE` |
| `LINK` ASTRORES senza `href`, senza `content-type` o con un `content-type` non ammesso, dati non leggibili nel formato dichiarato, FIELD diversi dai dati collegati, o letto con `read_table` (senza rete) | rifiuto esplicito con la causa (D13-17) | `ASTRORES_UNREADABLE` |
| `LINK` ASTRORES letto | dati collegati con URL, formato e data | avvisi `ASTRORES_LINK`, `ASTRORES_LINK_SOURCE` |
| ASTRORES: dati diversi dal tipo dichiarato (es. sessagesimali in un campo `F` in gradi) | conversione in gradi con il modulo 10 e colonna di testo conservata, oppure testo | avviso `ASTRORES_TYPE_MISMATCH` |
| ASTRORES: `ref` scritto `#id(...)` | riferimento accettato | avviso `ASTRORES_NONCONFORMING_REF` |
| ASTRORES con UCD1 della raccomandazione IVOA | tradotti, originale conservato | avviso `UCD1_TRANSLATED` |
| ASTRORES con altri UCD1 | UCD lasciati come sono, posizioni da confermare | avviso `UCD1_NOT_TRANSLATED` |
| Riga senza moto proprio nella propagazione | posizione propagata mascherata, riga marcata `missing`, conteggio | avviso `PROPER_MOTION_ROW_MISSING` |
| File XML con costrutti pericolosi (es. espansione di entità) | lettura interrotta, nessun dato caricato | `XML_UNSAFE` |
| Espressione di colonna non valida o colonna citata inesistente | rifiuto con la posizione dell'errore o il nome mancante | `COLUMN_EXPRESSION_INVALID` |
| Nome della nuova colonna già presente | rifiuto, nessuna sovrascrittura silenziosa | `COLUMN_NAME_EXISTS` |
| `save_subset` su un file esistente senza `overwrite=True` | nessuna scrittura | `FILE_EXISTS` |
| Operazione con `inplace=True` | tabella data modificata, citato nel report | avviso `INPLACE` |
| Unità incompatibili nell'espressione | rifiuto con le due unità | `UNIT_INCOMPATIBLE` |

## 11. Esposizione all'IA

Non applicabile in questo file: gli strumenti per l'IA si dichiarano in
`32-ia-registro-strumenti.md` (`01-architettura.md` §7, decisione del
proprietario del 2026-10-10). Finché il 32 non esiste, l'elenco da
riportarvi (nomi provvisori: `describe_table`, `search`,
`get_column_statistics` su `column_statistics`, `propagate`) è annotato
nella riga del 32 in `panoramica.md` §4. Vale sempre la regola d'oro n. 1:
l'IA scrive la richiesta e spiega, i numeri vengono dalle funzioni di §7 e
sono verificati da `34-ia-verifica-risultati.md`.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Caricamento VOTable | caricare un VOTable di prova | nomi colonne, unità, UCD e numero righe coincidono con quelli letti direttamente con `astropy.io.votable` nel test | ricalcolo con Astropy |
| T2 | `search` vs filtri | applicare regole di disegno ed eseguire una `search` | le regole non cambiano i record della tabella; la `search` restituisce solo i record che soddisfano l'espressione (confronto con `numpy` ricalcolato nel test) | confronto con `numpy` |
| T3 | Propagazione | propagare 100 posizioni con moto proprio dichiarato a un'epoca +10 anni | coincidenza con `SkyCoord.apply_space_motion` ricalcolato nel test (tolleranza 1e-9 gradi) | ricalcolo con Astropy |
| T4 | Colonna calcolata | calcolare `mag_corr = ${mag} - 0.12` su una tabella di prova | risultato coincidente con `numpy` ricalcolato nel test, unità `mag` | confronto con `numpy` |
| T5 | Istogramma | istogramma di una colonna con bin noti; senza bin | conteggi coincidenti con `numpy.histogram` ricalcolato nel test; senza bin → errore | ricalcolo con NumPy |
| T6 | Sottoinsiemi salvati | `save_subset` su un file scelto nel test, poi `read_table` | stessi record e valori; provenienza (origine, data, selezione) negli `INFO`; colonne di posizione e sistema ritrovati; nessuna voce nella cache | confronto con `astropy.io.votable` |
| T7 | Moto proprio mancante | chiedere la propagazione senza colonne di moto proprio | `PROPER_MOTION_MISSING`, nessun valore inventato | test di unità |
| T8 | IPAC TBL (H22) | leggere un file IPAC di prova | colonne, unità e valori uguali a quelli letti con `astropy.io.ascii` (formato `ipac`) | confronto con `astropy.io.ascii` |
| T9 | SExtractor (H22) | leggere un catalogo SExtractor di prova | colonne e valori uguali a `astropy.io.ascii` (formato `sextractor`) | confronto con `astropy.io.ascii` |
| T10 | BSV (H22) | leggere una tabella separata da spazi | colonne e valori uguali a `astropy.io.ascii` con separatore spazio | confronto con `astropy.io.ascii` |
| T11 | Riconoscimento dal contenuto (H22) | una VOTable con estensione `.csv`, un FITS con estensione `.txt`, CSV/TSV/BSV senza estensione, un testo ambiguo | formato riconosciuto dal contenuto; il testo ambiguo → `FORMAT_AMBIGUOUS`; con `format` esplicito si legge | test di unità |
| T12 | Colonna calcolata (H8) | colonne `B` e `V` in magnitudini; nuova colonna `B-V` con espressione `${B} - ${V}`, UCD e 3 decimali | valori = `B - V` calcolati con `numpy`; UCD, decimali e provenienza registrati; tabella originale invariata | ricalcolo con `numpy` |
| T13 | Espressione non valida (H8) | espressione con una colonna inesistente o con un nome non previsto | `COLUMN_EXPRESSION_INVALID`, nulla eseguito | test di unità |
| T14 | Unità incompatibili (H8) | somma di una colonna in gradi e una in magnitudini | `UNIT_INCOMPATIBLE` | test di unità |
| T15 | ASTRORES (H22, D13-17) | file nostri scritti dalla DTD (`CSV` con `colsep`/`headlines`, `TABLEDATA`, più tabelle, valori mancanti); `LINK` a dati CSV, TSV, VOTable e FITS scritti con astropy nel test e serviti da un servizio simulato, anche con `href` relativo in un documento da URL; `LINK` senza `content-type`, con `content-type` sconosciuto, `gref`, `action`, `href` relativo in un file locale, formato dichiarato diverso dai dati, nomi o unità diversi dai FIELD; test di rete: l'esempio pubblico del CDS scaricato nel test (non copiato nel repository) | colonne, unità, tipi e valori uguali a quelli scritti nel test; `LINK` letto con `load_table` (unità, UCD e `COOSYS` dei FIELD), con `read_table` → `ASTRORES_UNREADABLE`; casi rifiutati → `ASTRORES_UNREADABLE`; l'esempio pubblico si legge con gli avvisi previsti | confronto con i valori del test |
| T16 | XML malevolo (H22) | leggere un file ASTRORES con espansione di entità | `XML_UNSAFE`, nessun dato caricato | test di unità |
| T17 | Grammatica di `search` | ogni costrutto di §3 (confronti numerici e di testo, `|colonna|`, `${nome}`, `&&`/`||` con parentesi e precedenza, testo da solo su tutte le colonne di testo, jolly ed escape, spazi finali) ed espressioni non conformi | maschere uguali a quelle ricalcolate nel test con `numpy` e `re`; errori `EXPRESSION_INVALID` con la posizione | ricalcolo con `numpy` |
| T18 | Maiuscole e minuscole | testo con i jolly con e senza `case_sensitive=True` | per default non contano; con l'opzione contano | test di unità |
| T19 | Prefissi e valori mancanti | `+` e `-` su una selezione data; prefisso senza selezione; colonne con valori mascherati e NaN | unione e differenza corrette; senza selezione `EXPRESSION_INVALID`; mancanti mai selezionati (anche con `!=`) | confronto con `numpy` |
| T20 | Regole di disegno | due regole sovrapposte, dimensione da colonna con valori fuori intervallo e mancanti, regola non valida | prima regola che seleziona; dimensioni lineari portate agli estremi; mancanti non disegnati e contati; tabella invariata; `PLOT_RULE_INVALID` | ricalcolo con `numpy` |
| T21 | Limiti | tetto di righe e limite delle operazioni piccoli nel test, file FITS, CSV e VOTable | `TABLE_TOO_LARGE` e `MEMORY_LIMIT_EXCEEDED` prima di caricare (FITS e testi) o subito dopo la lettura (VOTable); nessun troncamento | test di unità |
| T22 | Colonne di posizione | VOTable con UCD e `COOSYS`; CSV con colonne `RAJ2000`/`DEJ2000` | dal VOTable colonne, sistema e `body = celestial`; dal CSV solo suggerimenti marcati, `NO_COORD_COLUMNS` e `BODY_UNKNOWN` finché l'utente non conferma; dopo la conferma colonne, sistema e corpo, conferma nella provenienza | test di unità |
| T23 | Parallasse e moto proprio mancanti | tabella con righe senza parallasse, con parallasse negativa e senza moto proprio | nessuna riga esclusa; righe senza parallasse valida propagate solo con il moto proprio (`pm_only`), valori uguali ad Astropy senza distanza; righe senza moto proprio mascherate (`missing`); conteggi nel report; colonne originali intatte | ricalcolo con Astropy |
| T28 | ASTRORES non conforme | campo `F` in gradi con dati sessagesimali; `ref` `#id(...)` | colonna in gradi uguale ad `astropy.coordinates.Angle` (ore per RA, gradi per Dec), colonna `_text` conservata, `ASTRORES_TYPE_MISMATCH`; `ref` accettato con `ASTRORES_NONCONFORMING_REF` | ricalcolo con Astropy |
| T30 | Filtro temporale | VOTable con `TIMESYS` (MJD, TDB) e colonna ISO senza `TIMESYS`; intervallo `[inizio, fine]` | estremi inclusi, mancanti esclusi e contati; con `TIMESYS` parametri rifiutati; senza `TIMESYS` formato e scala obbligatori; inizio > fine → `EPOCH_INVALID` | confronto con `astropy.time` |
| T31 | Albero delle collezioni (D13-18) | MocServer simulato con popolarità diverse, uguali, assenti, un record `CDS/Simbad`; poi senza la proprietà; poi risposta non JSON; test di rete sul MocServer | ordine decrescente, a pari valore ordine naturale (`I/9` prima di `I/10`), assenti in fondo; ordine dichiarato "proprietà non documentata del MocServer"; senza proprietà ordine naturale dichiarato; `CDS/Simbad` escluso; seconda chiamata dalla cache; risposta non valida → `SERVICE_ERROR` del 14 | test con servizio simulato (più un test di rete) |
| T32 | `load_catalog` senza regione | TAP VizieR simulato con 3 righe e `max_rows` 2 e 3; con `allow_partial=True`; test di rete su 2MASS con `max_rows` 5 | `max_rows` 2 → `REGION_REQUIRED`; con `allow_partial=True` 2 righe, `PARTIAL_CATALOG`, `ROW_LIMIT_EXCEEDED` e voce nella storia; `max_rows` 3 → catalogo intero senza avvisi; in rete stesso comportamento | test con servizio simulato (più un test di rete) |
| T33 | `load_catalog` con regione (D13-19) | TAP simulato con `TAP_SCHEMA` (nomi tra virgolette) e `COOSYS` `FK5` equinozio `2000.0`; centro ICRS; poi senza `COOSYS`, con due RA senza `meta.main`, con due coppie di cui una `meta.main` come Gaia DR3 (2026-10-23), con una tabella assente da `TAP_SCHEMA` (2026-10-23), raggi non validi, regione oltre `max_rows`; termini `refframe` nel `COOSYS`; SIMBAD simulato con l'`utype` MANGO e senza `COOSYS` (D13-20), poi con `utype` diversi sulle due colonne e con `FK5`; test di rete su 2MASS attorno a M31 e su SIMBAD | ADQL con il centro convertito in FK5 J2000 uguale ad astropy; sistema e colonne dichiarati; `FRAME_UNKNOWN`, `NO_COORD_COLUMNS`, `REGION_INVALID`, `REGION_TOO_LARGE`; coppia `meta.main` scelta; tabella assente → `CATALOG_UNKNOWN`; in rete tutte le righe entro il raggio (separazione ricalcolata con astropy); SIMBAD: centro convertito in ICRS, sistema ICRS epoca J2000 dichiarato (`POSITIONS_FROM_MANGO`), `utype` diversi o `FK5` → `FRAME_UNKNOWN` | test con servizio simulato (più un test di rete) |
| T29 | `skydist` | colonna calcolata con `skydist(${ra}, ${dec}, 10, 20)` | valori uguali ad `astropy.coordinates.angular_separation` ricalcolato nel test | ricalcolo con Astropy |
| T34 | Posizioni all'epoca di visualizzazione (D10-2) | tabella con righe `full`, `pm_only` e `missing`; immagine con `MJD-OBS`, immagine senza epoca, nessuna immagine, epoca dell'utente, tipo non valido | con l'immagine: epoca = `MJD-OBS` (scala del WCS), fonte "immagine"; senza epoca o senza immagine: J2000 (TT) con la fonte dichiarata; posizioni uguali a `propagate` alla stessa epoca; `drawable` = righe non `missing`; conteggi per modo; spostamento uguale ad `astropy.coordinates.angular_separation` ricalcolato nel test, media e massimo sulle righe disegnabili; `coords` alle stesse posizioni con l'epoca di visualizzazione; tipo non valido → `EPOCH_INVALID` | ricalcolo con Astropy |
| T35 | Epoca del `COOSYS` dopo la conferma delle colonne (D41-6) | risposta di TAP VizieR registrata (Gaia DR3 `I/355/gaiadr3`, 11 righe attorno ad Alcyone, `COOSYS` ICRS `epoch="2016.0"`), servita da un servizio simulato; `confirm_position_columns` con le stesse colonne `RA_ICRS`/`DE_ICRS` e `icrs`, poi con un altro sistema, poi su colonne diverse | stesse colonne e sistema: epoca `J2016` conservata, `EPOCH_FROM_METADATA`, `display_positions` uguale a `propagate` ricalcolato da J2016.0; sistema o colonne diversi: epoca non conservata e `EPOCH_INVALID` nella propagazione | test con risposta registrata, senza rete |
| T24 | Unità non riconosciute | colonne con `---` e con un'unità VOUnit valida | la prima con la stringa originale e `UNIT_UNRECOGNIZED`, la seconda con l'unità di `astropy.units` | test di unità |
| T25 | `inplace` nel report | `calculated_column` e `subset` con e senza `inplace=True` | senza: nuova tabella, originale invariata; con: tabella data modificata e report che lo cita | test di unità |
| T26 | Statistiche di una colonna | colonna con valori mascherati e NaN | minimo, massimo, media, deviazione standard e conteggi uguali a `numpy` sui valori validi | ricalcolo con `numpy` |
| T27 | Più tabelle | VOTable con due `TABLE`, FITS con due HDU di tabella | senza `table` → `TABLE_CHOICE_REQUIRED` con l'elenco; con `table` la tabella giusta; `list_tables` | confronto con Astropy |

**Test di rete:** regola delle ripetizioni (al massimo 2, solo per
connessione o timeout, dichiarate nel risultato) e regola dei commit in
`02-convenzioni.md` §8, punti 8 e 9 (decisioni del proprietario del
2026-10-11); implementazione in `tests/conftest.py` e
`scripts/commit_checked.py`, test in `tests/test_network_retries.py`.

## 13. Decisioni aperte

- **D13-1 — Sintassi delle espressioni `search`: DECISA il 2026-10-04,
  RISCRITTA il 2026-10-10 (decisione del proprietario, regola d'oro n. 8),
  FORMA FORMALE il 2026-10-10.** **Stringa con grammatica ristretta,
  descritta da zero come nostra** (grammatica e significato in §3): testo
  con i jolly `?` e `*`, che **non distingue maiuscole e minuscole per
  default** (opzione `case_sensitive`); colonna con gli operatori di
  confronto `=`, `!=`, `<`, `>`, `<=`, `>=`; valore assoluto `|colonna|`;
  `&&`, `||` e parentesi; prefissi `+` e `-` sulla selezione corrente;
  **validata prima dell'esecuzione** (`EXPRESSION_INVALID`).
  **Motivazione (nostra):** gli operatori di confronto e i jolly sono quelli
  universali, che un astronomo già conosce; una grammatica piccola e chiusa
  si valida per intero prima di eseguire (nessuna esecuzione di codice) e dà
  un solo validatore deterministico per UI, IA e pipeline.
- **D13-2 — Epoca di default per H3 (cursore epoca): DECISA il 2026-10-04,
  insieme a D10-2.** Epoca di ogni dato **letta dai metadati e mai assunta**;
  epoca di visualizzazione = epoca del dato mostrato (immagine: epoca
  dell'immagine se nota, altrimenti J2000; cataloghi: **propria epoca di
  riferimento**); **l'epoca usata è sempre scritta nel risultato**.
  **Motivazione:** una sola convenzione d'epoca per tutto il progetto
  (DC2 di `02-convenzioni.md`), con valore sempre dichiarato (regola d'oro
  n. 6). Applicata in §3/§9 qui sopra.
- **D13-3 — Cataloghi predefiniti (D1): DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** **albero dinamico delle
  collezioni ordinato per popolarità**, con un piccolo gruppo fisso: Simbad,
  Gaia, 2MASS (identificativi esatti **da verificare prima del codice di
  P6**). **Esito delle verifiche (2026-10-10, P6):** identificativi del
  gruppo fisso verificati sui servizi del CDS — `I/355/gaiadr3` (Gaia DR3
  Part 1, MocServer e TAPVizieR), `II/246/out` (2MASS PSC, MocServer e
  TAPVizieR, interrogabile con il nome diretto), SIMBAD = tabella `basic` del
  suo TAP; il criterio di popolarità: vedi D13-18 (decisa il 2026-10-11). **Motivazione (nostra, 2026-10-10):** le collezioni sono migliaia e
  cambiano nel tempo, quindi l'albero si legge dal servizio invece di una
  tabella mantenuta a mano; l'ordine per popolarità mette in alto i
  cataloghi più usati dalla comunità (criterio di popolarità: proprietà del
  servizio, **da verificare prima del codice di P6**); il gruppo fisso
  garantisce l'accesso immediato ai riferimenti di base (oggetti nominati,
  astrometria e fotometria su tutto il cielo).
- **D13-4 — Limite di righe in memoria: DECISA il 2026-10-10 (decisione del
  proprietario).** **1 milione di righe per tabella, configurabile**, più la
  stima della memoria con il **limite delle operazioni** (4 GB, come
  D11-11); oltre, errore esplicito, nessun caricamento progressivo nel
  livello 1. Chiude anche A10 per i cataloghi. Applicata in §3, §7, §10.
- **D13-5 — Comportamento delle operazioni in posto: DECISA il 2026-10-04.**
  Operazioni **sempre non distruttive**; modifica `in-place` solo con **flag
  esplicito citato nel report**. **Motivazione:** nessuna perdita di dati,
  riproducibilità (regola d'oro n. 6) e coerenza con `15`, `16`, `17` che
  dichiarano di non modificare la sorgente. Applicata in §3, §9 qui sopra.
- **D13-6 — Colonne di DataLink: DECISA il 2026-10-04.** **Colonna nel 13,
  risoluzione dei link nel `14-core-protocolli-vo.md`.** **Motivazione:**
  nessuna duplicazione di client VO, coerente con D14-3 e con il perimetro
  "protocolli VO" del 14. Applicata in §3 qui sopra.
- **D13-7 — Lettore ASTRORES (H22): DECISA il 2026-10-09 (decisione del
  proprietario).** Lettore nel modulo con **`defusedxml`** (non il parser XML
  della libreria standard, per sicurezza su file non fidati), testato su file
  di esempio del CDS; senza documentazione o esempi, solo errore
  (`ASTRORES_UNREADABLE`). **Da verificare prima del codice di P2:** licenza
  di `defusedxml`, disponibilità di documentazione ed esempi ASTRORES.
- **D13-8 — Posizione della tabella delle funzioni condivisa con il 18:
  DECISA il 2026-10-10 (decisione del proprietario).** In `catalogs.py`; il
  18 la importa (il 18 dipende già dal 13, nessuna dipendenza circolare).
- **D13-9 — Decisioni del 2026-10-10 sulla divisione in parti
  (proprietario):** sei parti, P6 dopo il 14; una sola cache delle
  interrogazioni, nel 14; grammatica di `search` con il testo che non
  distingue maiuscole e minuscole per default; regole di disegno; T4
  aritmetico; tetto di righe e limite delle operazioni; colonne di
  posizione solo da UCD e metadati, con suggerimenti dal nome da confermare;
  epoca e cos δ dichiarati; parallasse mancante o non positiva → solo moto
  proprio, righe marcate; unità non valide con avviso; riconoscimento
  CSV/TSV/BSV con errore se ambiguo; `inplace` citato nel report; bin e
  scala obbligatori; §11 nel 32; statistiche di una colonna nel §7.
  Applicate in §3–§12.
- **D13-10 — `skydist` nelle colonne calcolate: DECISA il 2026-10-10
  (decisione del proprietario).** Si calcola ora con
  `astropy.coordinates.angular_separation` nella tabella delle funzioni del
  13; il 17 usa la stessa implementazione (scritto nel 17).
- **D13-11 — Colonna DataLink: DECISA il 2026-10-10 (decisione del
  proprietario).** Spostata in P6, dopo il 14.
- **D13-12 — Propagazione senza parallasse: DECISA il 2026-10-10 (decisione
  del proprietario).** Opzione esplicita `proper_motion_only` di
  `propagate_position` nel 10 (astropy senza distanza, nessun effetto
  prospettico, risultato marcato); righe senza moto proprio → valore
  mancante marcato con conteggio, mai moto proprio nullo assunto; colonne
  originali intatte.
- **D13-13 — Sottoinsiemi salvati: DECISA il 2026-10-10 (decisione del
  proprietario).** In un file scelto dall'utente, VOTable con provenienza;
  mai nella cache; la sessione del `05` conterrà solo il riferimento al
  file (D17-3; prima "del 24", aggiornato il 2026-10-15).
- **D13-14 — Lettura ASTRORES: DECISA il 2026-10-10 (decisione del
  proprietario), tranne il punto b.** (a) sessagesimali in campi in gradi
  convertiti con il modulo 10, colonna di testo conservata, avviso; (c)
  `#id(...)` accettato con avviso; (d) `LINK` esterno tramite il 14 in P6,
  fino ad allora errore; (e) test su file nostri dalla DTD più l'esempio
  pubblico in un test di rete, senza copiarlo. Verifiche: DTD pubblica del
  CDS (v0.9), esempio pubblico, `defusedxml` 0.7.1 (licenza PSF, puro
  Python).
- **D13-14b — UCD1 → UCD1+: DECISA il 2026-10-10 (decisione del
  proprietario).** Solo le parole UCD1 scritte nella raccomandazione IVOA
  sugli UCD (quattro, §3); le altre non tradotte con `UCD1_NOT_TRANSLATED`
  e conferma dell'utente; servizio del CDS da valutare come opzione
  esplicita ("traduzione CDS"): rimandato il 2026-10-11 (D13-14c).
- **D13-15 — Numeri e unità nelle colonne calcolate: DECISA il 2026-10-10
  (decisione del proprietario).** In `+`, `-`, `%`, `min`, `max` il numero
  prende l'unità della colonna; in `*` e `/` resta adimensionale; T4
  invariato; `sin`/`sind` come in §3; `round` = metà al pari (`numpy`).
- **D13-16 — Filtro temporale: DECISA il 2026-10-10 (decisione del
  proprietario).** Colonna indicata dall'utente; formato e scala dal
  `TIMESYS`, altrimenti parametri obbligatori; intervallo chiuso
  `[inizio, fine]`.
- **D13-17 — Dati ASTRORES in un `LINK` esterno: DECISA il 2026-10-11
  (decisione del proprietario).** Solo tramite `href`; il formato si decide
  dal `content-type` dichiarato con i lettori già presenti nel 13 (CSV,
  TSV, VOTable, FITS); `content-type` assente o sconosciuto →
  `ASTRORES_UNREADABLE`; niente formati indovinati. Applicata in §3 (punto
  d), §7, §10, §12. Regola di accordo tra FIELD e dati collegati (stesse
  colonne, nessuna differenza di unità, UCD e tipo): scelta del
  2026-10-11, da confermare. (Aperta il 2026-10-10.)
- **D13-18 — Albero delle collezioni e criterio di popolarità (D13-3):
  DECISA il 2026-10-11 (decisione del proprietario).** L'albero usa la
  proprietà `vizier_popularity` del MocServer del CDS, dichiarata nel
  risultato come "proprietà non documentata del MocServer"; se manca,
  ordinamento alfabetico (dal 2026-10-11 ordine naturale, anche a pari
  popolarità). Client nel 14 (`vizier_collections`). Applicata
  in §3, §7, §10, §12 (T31). (Aperta il 2026-10-10: opzioni MocServer con
  popolarità, senza popolarità, `TAP_SCHEMA`; raccomandazione la prima.)
- **D13-19 — Parametro di regione di `load_catalog`: DECISA il 2026-10-11
  (decisione del proprietario).** `region=(centro, raggio)`; colonne di
  posizione dagli UCD in `TAP_SCHEMA`; sistema letto dai metadati e
  dichiarato nel risultato; `REGION_REQUIRED` indica il parametro.
  Applicata in §3, §7, §10, §12 (T33). Con la verifica, il 13 legge anche
  i termini del vocabolario IVOA `refframe` nel `COOSYS` (prima TAPVizieR
  dava `FRAME_UNKNOWN`).
- **D13-20 — Sistema delle colonne di SIMBAD per la regione: DECISA il
  2026-10-11 (decisione del proprietario).** Il sistema delle posizioni si
  legge dall'`utype` del modello IVOA MANGO
  (`mango:EpochPosition.longitude[CS.spaceSys=ICRS CT.epoch=J2000]`) e si
  **dichiara** nel risultato (avviso `POSITIONS_FROM_MANGO`, colonne,
  sistema ed epoca); `load_catalog("simbad", region=...)` non dà più
  `FRAME_UNKNOWN`. La lettura vale per ogni tabella senza `COOSYS` con gli
  `utype` MANGO (opzione (a) della raccomandazione). Applicata in §3, §10,
  §12 (T33).
- **D13-14c — Traduzione UCD1 con il servizio del CDS: RIMANDATA (decisione
  del proprietario del 2026-10-11, bassa priorità, Gruppo 3).** Il servizio
  di traduzione UCD1 → UCD1+ del CDS (opzione esplicita prevista da
  D13-14b, "traduzione CDS") non si scrive ora; restano le quattro parole
  della raccomandazione IVOA e `UCD1_NOT_TRANSLATED` per le altre.
- **Scelte minori del 2026-10-11 confermate dal proprietario:** tutte,
  tranne due cambiate dal proprietario: versione del formato dei FITS
  esportati "FITS Standard 4.0" più la versione di `astropy` (nel 14), e
  `load_catalog` senza regione (§7, T32).
- **Scelte minori del 2026-10-10 confermate dal proprietario:** epoca di
  origine (parametro vietato se è nei metadati, colonna in anni giuliani);
  equinozio ed epoca ASTRORES numerici giuliani (FK5/ICRS) o besseliani
  (FK4); colonne `_prop`/`_prop_mode`; `size_min` > `size_max` ammesso;
  nessun passaggio alla regola successiva, con i record non disegnati per
  dimensione mancante **contati nel risultato** delle regole
  (`PlotStyle.missing_size`); `FILE_EXISTS` senza `overwrite=True`.

- **D41-6 — Epoca del `COOSYS` dopo `confirm_position_columns`: DECISA il 2026-10-21** (decisione del
  proprietario, autorizzazione esplicita a modificare questo file approvato): con le stesse colonne e lo stesso
  sistema dei metadati si conservano epoca ed equinozio dichiarati e si usano per la propagazione; mai un'epoca
  assunta se i metadati non la dichiarano (`EPOCH_INVALID`). Applicata in §3, §7, T35. **Possibile aggiunta
  futura** (non ora): parametro `source_epoch` esplicito in `confirm_position_columns`/`catalog.set_columns`.

- **D13-21 — Colonne di posizione ambigue in una regione chiesta dall'assistente: DA DECIDERE** (aperta il 2026-10-23, Gruppo 3). Con più coppie candidate negli UCD di `TAP_SCHEMA` e nessuna `meta.main` univoca `load_catalog` con regione dà `NO_COORD_COLUMNS` (nulla assunto); dal menu lo stesso caso non si può risolvere con la finestra delle colonne del 42, perché le colonne servono **prima** della query. Caso non riprodotto su VizieR (Gaia DR3 ha una sola coppia `meta.main`, verificato il 2026-10-23). Opzioni: (a) come oggi, con le coppie candidate scritte nel messaggio d'errore, così il modello le riferisce all'utente; (b) parametri facoltativi `lon`/`lat` di `catalog.load_region` (05, 13) scelti dall'utente in una finestra aperta dal pannello del 44 quando l'errore arriva da una richiesta dell'IA, e comando rieseguito come richiesta dell'utente. **Raccomandazione:** (a) nella v1, (b) se un catalogo reale lo richiede. La decisione è del proprietario.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario: D13-1, D13-2, D13-5 e D13-6 passate da aperte a decise.** D13-1: grammatica `search` ristretta alla Aladin (`?`/`*`, `=`/`!=`/`<`/`>`/`<=`/`>=`, `\|colonna\|`, prefissi `+`/`-`), validata prima dell'esecuzione (§3/§6/§7/§9). D13-2: epoca dai metadati, mai assunta, epoca di visualizzazione = epoca del dato (immagine se nota, altrimenti J2000; cataloghi con propria epoca di riferimento), epoca sempre scritta nel risultato (§3/§9; insieme a D10-2 e a DC2). D13-5: operazioni sempre non distruttive, in-place solo con flag esplicito citato nel report (§9). D13-6: colonna DataLink nel 13, risoluzione nel 14 (§3). Decisioni riportate in `decisioni-aperte.md`. |
| 2026-10-08 | Claude Code | §5: aggiunti a "Usato da" i moduli `18-core-calcolatrici.md` e `19-core-dati-planetari.md` (scritti il 2026-10-08, stato bozza). Nessun altro testo cambia. |
| 2026-10-09 | Claude Code | **D19-3 applicata (decisione del proprietario del 2026-10-08):** campo `body` obbligatorio nei metadati di ogni tabella (§6, §9, §10); per i dati astronomici `celestial`, ricavato dal sistema di coordinate, mai assunto; errori `BODY_UNKNOWN` e, per le sovrapposizioni, `BODY_MISMATCH` secondo D19-4 (forzabile solo con opzione esplicita citata nel risultato). |
| 2026-10-09 | Claude Code | **D13-3 DECISA** (checklist del livello 1): albero dinamico ordinato per popolarità con gruppo fisso Simbad, Gaia, 2MASS. |
| 2026-10-09 | Claude Code | **Completamento con gli esiti di AP5** (decisione del proprietario del 2026-10-09): §3, §6, §7, §8, §10, §12 per H22 (formati CSV, TSV, BSV, IPAC TBL, SExtractor con `astropy.io.ascii`; ASTRORES; riconoscimento dal contenuto) e H8 (colonne calcolate con unità, UCD, decimali ed espressioni `${colonna}` con la tecnica di D18-1). Nuove decisioni: **D13-7** (lettore ASTRORES, Gruppo 2) e D13-8 (Gruppo 3). Il modulo resta in `bozza`. |
| 2026-10-09 | Claude Code | **D13-7 DECISA** (decisione del proprietario): lettore ASTRORES con `defusedxml` (licenza da verificare), testato su esempi del CDS, altrimenti solo errore. §3, §7, §8, §10 (`ASTRORES_UNREADABLE`, `XML_UNSAFE`), §12, §13 aggiornati. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** (regola del proprietario del 2026-10-09): nessuna decisione aperta nei Gruppi 1 e 2. |
| 2026-10-09 | Claude Code | **Collegamento alla cache comune `04-cache.md`** (approvato il 2026-10-09; decisione CA4 del proprietario, autorizzazione esplicita a modificare il file approvato): §3, §5, §7, §8 — tolta `CatalogCache`, interrogazioni nelle tabelle del modulo dentro `SharedCache`. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Regola d'oro n. 8** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): D13-1 riscritta come grammatica nostra (operatori di confronto universali, motivazione nostra; tolto "basata su Aladin"; forma formale da scrivere prima del codice di `search`) in §3, §6, §13; D13-3 con motivazione nostra al posto di "come Aladin"; limite di riga riferito solo a `01` §8. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Decisioni del proprietario sulla divisione in parti** (autorizzazione esplicita a modificare il file approvato): sei parti (P6 dopo il 14); VOTable locali con `astropy.io.votable`; più tabelle con `table`/`TABLE_CHOICE_REQUIRED` (come D11-4); riconoscimento dei formati con la regola CSV/TSV/BSV e `FORMAT_AMBIGUOUS`; unità non valide con `UNIT_UNRECOGNIZED`; D13-4 deciso (1 milione di righe, limite delle operazioni 4 GB, A10 per i cataloghi); colonne di posizione solo da UCD e metadati, suggerimenti dal nome da confermare; grammatica formale di `search` (testo che non distingue maiuscole e minuscole per default); regole di disegno; epoca e cos δ dichiarati; parallasse mancante → solo moto proprio, righe marcate; `inplace` citato nel report; bin e scala obbligatori; `column_statistics` e `record_view` nel §7; una sola cache delle interrogazioni nel 14; D13-8 deciso (tabella delle funzioni in `catalogs.py`); §11 nel 32; T4 aritmetico, nuovi T17–T27, T6 per i sottoinsiemi salvati. Nuove decisioni aperte del Gruppo 3: D13-10 (`skydist`), D13-11 (colonna DataLink), D13-12 (propagazione senza parallasse nel 10, righe senza moto proprio), D13-13 (dove si salvano i sottoinsiemi). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P1 scritta** (`src/astrotwo/core/catalogs.py`, test T1, T8–T11, T21, T22, T24, T27): verifiche — astropy 8.0.1 espone UCD e riferimento al `COOSYS` di ogni campo, non la stringa originale dell'unità (§3 precisato); lettori `csv`, `tab`, `basic`, `ipac`, `sextractor` presenti; §3 precisato sulla stima prima della lettura dei testi. `confirm_position_columns` chiede `unit` angolare se le colonne non hanno unità (mai assunta). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P2, verifiche:** DTD ASTRORES pubblica (CDS, v0.9) ed esempio pubblico del CDS trovati; `defusedxml` 0.7.1 (licenza PSF, puro Python). L'esempio è incoerente con la DTD (coordinate sessagesimali in campi `F`, UCD1, `ref` non IDREF) e T15 non ha una VOTable equivalente: nuova decisione aperta **D13-14** (Gruppo 3); P2 ferma in attesa del proprietario. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Decisioni del proprietario D13-10…D13-14** (autorizzazione esplicita a modificare il file approvato): `skydist` con `astropy.coordinates` nella tabella delle funzioni, usato anche dal 17; colonna DataLink e `LINK` ASTRORES in P6; propagazione senza parallasse con l'opzione `proper_motion_only` del 10, righe senza moto proprio mascherate e contate, colonne `_prop` e `_prop_mode` (§3, §7); sottoinsiemi salvati in un VOTable scelto dall'utente (`save_subset`); lettore ASTRORES secondo la DTD con i punti a, c, d, e; nuovi avvisi `ASTRORES_TYPE_MISMATCH`, `ASTRORES_NONCONFORMING_REF`, `PROPER_MOTION_ROW_MISSING`; T6, T15, T23 riscritti, nuovi T28–T29. **Verifica:** nessuna tabella ufficiale IVOA UCD1 → UCD1+ trovata → nuova **D13-14b** (da decidere, blocca P2). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P3 scritta** (`search`, `PlotRule`, `SizeScale`, `set_plot_rules`; test T2, T17–T20): precisati in §3 l'intervallo invertito della dimensione (`size_min` > `size_max`) e che un record senza valore per la dimensione non passa alla regola successiva. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P4 scritta tranne `calculated_column`** (`FUNCTIONS`, `CONSTANTS`, `skydist`, `subset`, `save_subset`, `column_statistics`, `histogram`, `xy_plot`, `record_view`; test T5, T6, T25, T26, T29 per `skydist`): verificato con astropy 8.0.1 che un numero scritto è adimensionale (`${mag} - 0.12` → errore di unità) → nuova **D13-15** (da decidere); nuovi `FILE_EXISTS` e avviso `INPLACE` (§10); deviazione standard con `ddof = 0` dichiarato. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P5 scritta tranne `time_filter`** (`propagate`, `proper_motion_arrows`; test T3, T7, T23 e frecce): epoca in anni giuliani, `source_epoch` vietato se l'epoca è nei metadati, righe con posizione o epoca mancante trattate come `missing` (§3, §7). `time_filter` attende la nuova **D13-16** (da decidere). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P2 scritta** (lettore ASTRORES con `defusedxml` 0.7.1, aggiunto a `pyproject.toml`; sessagesimali con la nuova `parse_sexagesimal` del 10; test T15, T16, T28 e test di rete sull'esempio pubblico del CDS, non copiato nel repository): regole precisate in §3 (righe d'intestazione, booleani, nomi duplicati, `COOSYS` di default, anni giuliani/besseliani); UCD1 non tradotti in attesa di D13-14b (`UCD1_NOT_TRANSLATED`, §10). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Decisioni del proprietario D13-14b, D13-15, D13-16 e conferma delle scelte minori** (autorizzazione esplicita a modificare il file approvato): traduzione dei soli UCD1 della raccomandazione IVOA (`UCD1_TRANSLATED`); regola dei numeri e delle unità nelle colonne calcolate e `round` metà al pari; `time_filter` con colonna indicata, `TIMESYS` o parametri, intervallo chiuso. **Codice completo di P4 e P5** (`calculated_column`, `time_filter`) e di P2 (traduzione UCD1); test T4, T12–T14, T28, T29, T30 e test di rete aggiornato. Moduli P1–P5 completi; P6 dopo il 14. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Con P1 del 14** (autorizzazione esplicita a modificare il file approvato): le righe `#` dei testi delimitati (CSV, TSV, BSV) sono commenti anche nella lettura con `astropy.io.ascii`, come già nel riconoscimento di §3 (prima un CSV con commenti all'inizio non si leggeva); lo scrittore VOTable di `save_subset` (UCD e `COOSYS`) è condiviso con l'esportazione del 14. Comportamento di §3 invariato. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Con P4 del 14** (autorizzazione esplicita a modificare il file approvato): correzione — un VOTable senza l'attributo facoltativo `nrows` (dati `BINARY`, es. le risposte TAP del registro VO) dava un errore nel controllo del tetto di righe; ora le righe si contano dai dati letti. Nuovo test. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Con P5 del 14** (autorizzazione esplicita a modificare il file approvato): la lettura conserva nei metadati di colonna anche l'`utype` dei campi VOTable e gli UCD/utype delle tabelle FITS (parole chiave `TUCDn`, `TUTYPn`), che servono a riconoscere gli assi degli spettri SSA; nessun altro comportamento cambia. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **P6 scritta tranne l'albero dinamico (D13-18) e il `LINK` ASTRORES (D13-17)** (autorizzazione esplicita a modificare il file approvato): `load_table` (file locale o URL tramite `download_table` del 14), `load_catalog` (TAP VizieR o gruppo fisso tramite `tap_query` del 14; `CATALOG_UNKNOWN`), `FIXED_COLLECTIONS` con identificativi verificati, `datalink_column` (descrittore DataLink o content-type DataLink nella colonna del formato, forma ObsCore), campi `request` e `descriptors` di `CatalogTable` (§7); test con servizi simulati e test di rete su 2MASS. Nuove decisioni aperte **D13-17** e **D13-18** (Gruppo 3). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **Con D14-10** (decisione del proprietario del 2026-10-11, autorizzazione esplicita a modificare il file approvato): lettura dell'**ECSV** di `astropy` (formato `ecsv`, riconosciuto dalla prima riga `# %ECSV`, anche come `format` esplicito), con unità, UCD e valori mancanti; sistema delle posizioni non presente nell'ECSV (`FRAME_UNKNOWN`). Test di andata e ritorno nel 14 (T5). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **D13-17 decisa e applicata** (decisione del proprietario del 2026-10-11, autorizzazione esplicita a modificare il file approvato): `LINK` ASTRORES letti solo con `href`, formato dal `content-type` del `LINK` (verificato come attributo nella DTD v0.9) con i lettori CSV, TSV, VOTable e FITS del modulo, nessun formato indovinato; dati scaricati con il 14 tramite `load_table` (anche per un ASTRORES scaricato da URL, con `href` relativo risolto sull'URL); `read_table` senza rete rimanda a `load_table`; accordo stretto tra FIELD e dati collegati (scelta da confermare); avvisi `ASTRORES_LINK`, `ASTRORES_LINK_SOURCE`; T15 completo (§3, §7, §10, §12, §13). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **D13-18 decisa e applicata** (decisione del proprietario del 2026-10-11, autorizzazione esplicita a modificare il file approvato): `collection_tree`, `CollectionTree`, `CollectionNode` — albero delle collezioni dal MocServer del CDS (client `vizier_collections` nel 14), ordinato per `vizier_popularity` decrescente (nodi interni: massimo del sottoalbero; pari valore e assenti in ordine alfabetico), dichiarato come "proprietà non documentata del MocServer", ordine alfabetico se la proprietà manca; `CDS/Simbad` escluso; avvisi `COLLECTION_SKIPPED`, `POPULARITY_MISSING`, `POPULARITY_INVALID`; verifica in linea del MocServer; nuovo T31 (§3, §7, §10, §12, §13). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **Scelte minori del 2026-10-11** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): `load_catalog` senza regione solo entro `max_rows` (troncamento dichiarato dal servizio), altrimenti `REGION_REQUIRED` o `allow_partial=True` dichiarato (`PARTIAL_CATALOG`); nuovo T32. Nuova decisione aperta **D13-19** (parametro di regione di `load_catalog`, Gruppo 3; fermo solo il parametro). Traduzione UCD1 del CDS rimandata a bassa priorità come **D13-14c** (Gruppo 3). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **D13-19 decisa e applicata** (decisione del proprietario del 2026-10-11, autorizzazione esplicita a modificare il file approvato): `load_catalog(..., region=(centro, raggio))` con colonne dagli UCD di `TAP_SCHEMA`, sistema dal `COOSYS` del servizio, centro convertito con il modulo 10, `CatalogRegion` dichiarata; nuovi `REGION_INVALID`, `REGION_TOO_LARGE`, avviso `REGION`; `REGION_REQUIRED` indica il parametro; il lettore riconosce i termini del vocabolario IVOA `refframe` (`FK5`, `FK4`, `GALACTIC`, `SUPER_GALACTIC`) e legge l'equinozio numerico come per ASTRORES (verifica su TAPVizieR); T33. Nuova decisione aperta **D13-20** (sistema di SIMBAD nell'`utype` MANGO, Gruppo 3). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **Scelte minori del 2026-10-11 cambiate dal proprietario** (autorizzazione esplicita a modificare il file approvato): ECSV scritto da AstroTwo con colonne, sistema, equinozio ed epoca delle posizioni nei metadati YAML `A2POSITIONS`, riletti senza `FRAME_UNKNOWN` (avvisi `POSITIONS_FROM_ECSV`, `ECSV_POSITIONS_INVALID`); albero delle collezioni in ordine naturale a pari popolarità (e per le collezioni senza popolarità); regola delle ripetizioni dei test di rete (solo connessione o timeout, al massimo 2, dichiarate). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | Regola delle ripetizioni dei test di rete spostata in `02-convenzioni.md` §8 (punto 8) insieme alla regola dei commit (punto 9); qui resta il rimando (decisione del proprietario del 2026-10-11, autorizzazione esplicita). Stato `approvato` invariato. |
| 2026-10-11 | Claude Code | **D13-20 decisa e applicata** (decisione del proprietario del 2026-10-11, autorizzazione esplicita a modificare il file approvato): sistema delle posizioni dall'`utype` MANGO (ICRS, epoca J2000 per SIMBAD) quando manca il `COOSYS`, dichiarato con l'avviso `POSITIONS_FROM_MANGO`; regione su SIMBAD attiva; T33 esteso. Stato `approvato` invariato. |
| 2026-10-14 | Claude Code | **`display_positions` aggiunta** (decisione del proprietario del 2026-10-14, autorizzazione esplicita a modificare il file approvato): §3 (regola: D10-2 in un passo, epoca dell'immagine se nota altrimenti J2000 o epoca dell'utente, fonte dichiarata, calcolo di `propagate`, posizioni, righe disegnabili, conteggi per modo e spostamento), §7 (firma e `DisplayPositions`, nessuna dipendenza dall'11), §10 (epoca dell'immagine assente; tipo non riconosciuto → `EPOCH_INVALID`), §12 (T34). Stato `approvato` invariato. |
| 2026-10-15 | Claude Code | **Decisione del proprietario del 2026-10-15** (proposta della fase 1 dell'interfaccia, autorizzazione esplicita a modificare il file approvato; solo specifica): D17-3 rimanda alla sessione di `05-comandi-sessione.md` invece che al `24` (§3, §13); `05` e funzioni usate dal `41` in "Usato da" (§5). Stato `approvato` invariato. |
| 2026-10-21 | Claude Code | **D41-6 decisa dal proprietario (autorizzazione esplicita a modificare il file approvato):** `confirm_position_columns` conserva epoca ed equinozio dei metadati (`COOSYS`, `utype` MANGO, ECSV) quando colonne e sistema confermati sono gli stessi, con l'avviso `EPOCH_FROM_METADATA`; altrimenti nessuna epoca (mai assunta). `source_epoch` annotato come possibile aggiunta futura. Nuovo T35 con la risposta registrata di Gaia DR3. Stato `approvato` invariato. |
| 2026-10-21 | Claude Code | **Correzione di `record_view` (parte 5 della v1, pannello della tabella del 42):** con una colonna array (VOTable `arraysize`, maschera per elemento) `record_view` andava in errore ("truth value of an array…") e con lui `catalog.select`; ora una cella array è mancante solo se lo sono tutti i suoi elementi, gli elementi mancanti restano mascherati nel valore. Test `test_record_view_array_column`. Stato `approvato` invariato. |
| 2026-10-23 | Claude Code | **Precisazione di `load_catalog` con regione** (parte 7, sprint 7b; il proprietario ha chiesto di aggiornare prima il 13, messaggio del 2026-10-23): una tabella senza colonne in `TAP_SCHEMA` dà `CATALOG_UNKNOWN` (identificativo non trovato, regola di §7 già scritta) invece di `NO_COORD_COLUMNS`. Causa della prova reale del proprietario ("Carica Gaia DR3 attorno alle Pleiadi" dall'assistente → `NO_COORD_COLUMNS`): con `I/355/gaiadr3` il comando funziona sul servizio reale (colonne `RA_ICRS`/`DE_ICRS` da `meta.main`, ICRS epoca J2016 dal `COOSYS`); l'errore esce solo con un identificativo che non è una tabella (`I/355`, `gaiadr3`). T33 esteso con la struttura reale di `TAP_SCHEMA` di Gaia DR3 (due coppie, una `meta.main`) in dati sintetici, senza dati di terzi (decisione del 2026-10-22). Stato `approvato` invariato. |
| 2026-10-23 | Claude Code | Aperta **D13-21** (colonne di posizione ambigue in una regione chiesta dall'assistente, Gruppo 3, §13). Stato `approvato` invariato. |
