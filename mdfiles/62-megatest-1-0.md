# 62-megatest-1-0.md — Megatest a mano prima della 1.0

**Stato:** bozza

> Creato il 2026-11-10 (sprint D2, Fase D) su richiesta del proprietario: il
> piano dei rilasci (decisione del 2026-11-09, confermata il 2026-11-10) dice
> che dalla beta 5 si va alla 1.0 **dopo un megatest fatto a mano**. Questo
> file è l'elenco delle prove. Non è un modulo di codice: le sezioni che
> parlano di codice dicono «non applicabile» con il motivo.

## 2. Scopo

Dare a chi prova AstroTwo a mano, prima del rilascio della 1.0, un elenco di
prove brevi, una per riga, con il risultato atteso, che copra tutte le aree
dell'app usate da un astrofisico.

## 3. Cosa fa

### 3.1 Come si fa il megatest

- **Chi:** il proprietario o una persona da lui indicata, sul Mac.
- **Su quale app:** il megatest si fa **sull'app installata dal `.dmg`
  candidato** (`63` passo 9): il `.dmg` prodotto da `scripts/make_dmg.py`
  (`63` passo 7 o 8), controllato con le prove K1–K3, e AstroTwo trascinata
  in `/Applications`. Mai con `uv run astrotwo` né aprendo direttamente
  `dist/AstroTwo.app`.
- **Prima di cominciare:**
  - Mac con macOS 15 o successivo, Apple silicon (`docs/installation.md`);
  - **TOPCAT** installato (per SAMP e per i confronti);
  - per l'assistente: **Ollama** o **LM Studio** con un modello scaricato, e
    una chiave API di un provider cloud;
  - il `.dmg` candidato **e** il suo file `.sha256`, nella stessa cartella
    (per esempio *Downloads*), e nessuna copia precedente di AstroTwo in
    `/Applications` (spostarla nel Cestino prima di cominciare);
  - un file FITS con WCS (per esempio un'immagine DSS scaricata da SkyView) e
    un catalogo VOTable o CSV con colonne di posizione;
  - cache vuota: **AstroTwo → Settings… → Clear cache**.
- **Come si scrive l'esito:** una copia di questo elenco con, per ogni prova,
  **OK**, **KO** con una riga di descrizione, oppure **non fatta** con il
  motivo (es. servizio giù). Si annotano la data, la versione dell'app
  (**About AstroTwo**) e la versione di macOS.
- **Regole:** una prova si fa **una volta sola, come scritta**; se il
  risultato non è quello atteso si scrive KO e si va avanti (niente
  correzioni durante il megatest). Il servizio che non risponde è
  «non fatta», non KO, salvo che l'app non lo dica (allora è KO).
- **Durata prevista:** circa due ore.
- **Esito della 1.0:** si rilascia solo con **zero KO**, oppure con i KO
  che il proprietario dichiara non bloccanti, scritti nelle note di rilascio.

### 3.1bis Il `.dmg` candidato (K)

Prove aggiunte nello sprint D6 (decisione D60-7 del proprietario del
2026-11-11). Si fanno per prime, nell'ordine.

| # | Prova | Risultato atteso |
|---|---|---|
| K1 | Nel Terminale, nella cartella del `.dmg`: `shasum -a 256 -c AstroTwo-<versione>.dmg.sha256` | Una riga `AstroTwo-<versione>.dmg: OK`; nessun `FAILED` (`docs/installation.md`) |
| K2 | Doppio clic sul `.dmg` | Si monta il volume **«AstroTwo <versione>»**; la finestra del Finder mostra **solo** due voci: **AstroTwo** e il collegamento **Applications** (icona con la freccia del collegamento); nessuno sfondo né disposizione speciale delle icone (D60-7) |
| K3 | Trascinare **AstroTwo** sul collegamento **Applications** della stessa finestra, poi espellere il volume | AstroTwo è copiata in `/Applications` (`ls -d /Applications/AstroTwo.app` la trova); il volume si espelle senza errori |

### 3.2 Avvio e installazione (A)

| # | Prova | Risultato atteso |
|---|---|---|
| A1 | Primo avvio di AstroTwo da `/Applications` (installata in K3), con «Apri comunque» se il `.dmg` non è notarizzato (`docs/installation.md`) | L'app si apre; nessun messaggio di errore; **AstroTwo → About AstroTwo** dice la versione 1.0 candidata |
| A2 | Chiudere e riaprire l'app | Si riapre con le stesse preferenze; nessuna finestra di errore |
| A3 | **Help → Licenses…** | Elenco delle licenze di terze parti, Qt (LGPL) compresa; si chiude senza errori |
| A4 | **App senza firma Developer ID (la 1.0, A6-b decisa il 2026-11-11).** Portare il `.dmg` candidato su un Mac come lo riceve un utente, cioè **scaricato** (browser, AirDrop o posta: solo così macOS gli mette l'attributo di quarantena; controllo: `xattr -p com.apple.quarantine AstroTwo-<versione>.dmg` stampa una riga). Possibilmente un altro Mac; senza AstroTwo in `/Applications`. Poi K1–K3 e primo avvio con doppio clic, seguendo `docs/installation.md` («First launch») | Al primo doppio clic macOS **mostra l'avviso** e non apre l'app; in **Impostazioni di Sistema → Privacy e sicurezza → Sicurezza** c'è **«Apri comunque»**; dopo la conferma e la password l'app si apre; i passi coincidono con quelli di `docs/installation.md` (una differenza nei nomi dei pulsanti o nell'ordine è KO **non bloccante**, da correggere nella pagina); al secondo avvio nessun avviso. Annotare la versione di macOS |
| A4bis | **Solo per una versione firmata Developer ID e notarizzata** (A6-b: non la 1.0; altrimenti «non fatta»): come A4, poi `spctl --assess --type execute -vv /Applications/AstroTwo.app` | L'app si apre **senza** avviso né «Apri comunque»; `spctl` dice `accepted` e `source=Notarized Developer ID` |

### 3.3 Atlante HiPS (H)

| # | Prova | Risultato atteso |
|---|---|---|
| H1 | Avvio con la cache vuota | Compare il survey di default; la barra di stato mostra posizione, valore del pixel con unità, ordine HiPS e risoluzione sotto il cursore |
| H2 | Campo *Go to* (⌘L): `M 31`, Invio | La vista si centra su M 31; il comando `view.goto` compare nel pannello Comandi |
| H3 | *Go to*: `00:42:44.3 +41:16:09` | Stessa posizione di H2 entro pochi secondi d'arco |
| H4 | **Data → HiPS survey…**, `CDS/P/2MASS/color` | Il survey cambia; i crediti del survey sono visibili |
| H5 | Trascinare, zoom con la rotella e con ⌘+ / ⌘− | La vista si muove senza scatti visibili; nessun riquadro nero che resta |
| H6 | **View → Coordinate grid** in ICRS, poi in Galactic | Griglia visibile con le etichette; cambio di sistema immediato |
| H7 | **Tools → Distance** tra due stelle note (per esempio le due componenti di Albireo) | Distanza angolare con unità; il comando è registrato |
| H8 | **Tools → Simbad pointer** su una stella brillante | Compare il nome SIMBAD dell'oggetto con la fonte |
| H9 | **View → Night mode** (⌃⌘N), poi di nuovo | Tutta l'interfaccia diventa rossa, poi torna com'era |

### 3.4 Immagini FITS (F)

| # | Prova | Risultato atteso |
|---|---|---|
| F1 | **File → Open image…** (⌘O) con il FITS preparato | L'immagine compare al posto giusto nel cielo, sopra il survey; un livello nuovo nel pannello Layers |
| F2 | Puntare una stella dell'immagine | Il valore del pixel dell'immagine (con l'unità di `BUNIT`, se c'è) nella barra di stato; le coordinate coincidono con quelle del survey sotto |
| F3 | Nel pannello Layers: opacità al 50 %, poi visibilità spenta | L'immagine diventa trasparente, poi sparisce; il survey resta |
| F4 | Aprire un file che non è un FITS rinominato `.fits` | Finestra con un messaggio chiaro; l'app non si chiude; nessun livello nuovo |

### 3.5 Cataloghi (C)

| # | Prova | Risultato atteso |
|---|---|---|
| C1 | *Go to* `Pleiades`, **Data → Catalog in view…** Gaia DR3 | Simboli sulle stelle; nel pannello Layers il numero di righe, il servizio e l'epoca dichiarata (J2016.0) |
| C2 | Selezionare una riga nel pannello Table | La sorgente si evidenzia nel cielo; cliccare una sorgente nel cielo seleziona la sua riga |
| C3 | **File → Open catalog…** con il VOTable o CSV preparato | Nuovo livello catalogo; se il file non dichiara sistema o epoca, il pannello Layers lo dice (nessuna epoca assunta) |
| C4 | Catalogo SIMBAD nella stessa vista | Secondo livello catalogo con colore diverso; i due livelli si accendono e si spengono a parte |

### 3.6 Incrocio (X)

| # | Prova | Risultato atteso |
|---|---|---|
| X1 | **Data → Cross-match catalogs…** Gaia DR3 × SIMBAD (C1, C4), migliore corrispondenza, 2″, metodo locale | Nuovo catalogo con le coppie e la colonna della separazione; report con criteri, epoche e conteggi |
| X2 | Stessi due cataloghi in TOPCAT (*Pair Match*, 2″, *Best match*) | Stesso numero di coppie di X1 (una differenza si scrive con le coppie in più o in meno) |
| X3 | Stesso incrocio con il metodo XMatch del CDS | Risultato con lo stesso numero di coppie di X1, oppure, se il CDS è giù, un messaggio chiaro e nessun risultato parziale presentato come completo |
| X4 | Modo «righe di A senza corrispondenza» | Catalogo con le sole righe senza coppia; conteggio = righe di A − coppie di X1 |

### 3.7 Cone search e ADQL (Q)

| # | Prova | Risultato atteso |
|---|---|---|
| Q1 | **Data → Cone search…** su un servizio della lista, centro della vista, 5′ | Nuovo livello catalogo; la query è nella provenienza del livello |
| Q2 | **Data → ADQL query…**, esempio Gaia DR3, **Insert view centre and radius**, **Check**, poi invio sincrono | Tabella con le righe; numero di righe uguale a quello della stessa query in TOPCAT |
| Q3 | ADQL con un errore di sintassi | Messaggio di errore del servizio, leggibile; nessun livello vuoto creato |
| Q4 | La stessa query in modo asincrono | Stesso risultato di Q2; la finestra mostra l'avanzamento e permette di annullare |

### 3.8 MOC (M)

| # | Prova | Risultato atteso |
|---|---|---|
| M1 | **File → Open MOC…** con un MOC FITS (per esempio quello di un survey, scaricato dal MocServer) | Area colorata nel cielo; nel pannello Layers l'ordine del MOC e l'ordine a cui è disegnato |
| M2 | Zoom molto vicino al bordo del MOC | Il bordo resta coerente; la nota «disegnato all'ordine …, per eccesso» quando l'ordine di disegno è minore |
| M3 | Aprire un file `.json` che non è un MOC | Messaggio chiaro; nessun livello |

### 3.9 SAMP con TOPCAT (S)

| # | Prova | Risultato atteso |
|---|---|---|
| S1 | Avviare TOPCAT, poi **Tools → SAMP → Connect** | AstroTwo usa l'hub di TOPCAT; **Connected applications** elenca TOPCAT |
| S2 | Inviare il catalogo Gaia DR3 di C1 a TOPCAT | La tabella compare in TOPCAT con lo stesso numero di righe |
| S3 | In TOPCAT selezionare alcune righe di quella tabella | Le stesse righe si selezionano in AstroTwo |
| S4 | Da TOPCAT inviare una posizione (*coord.pointAt.sky*) | La vista di AstroTwo si centra su quella posizione |
| S5 | Da TOPCAT inviare una sua tabella | Nuovo livello catalogo in AstroTwo, con il nome dichiarato come testo esterno |
| S6 | Chiudere TOPCAT | AstroTwo lo dice; nessun blocco; **Connect** di nuovo avvia un hub suo |

### 3.10 Profili di un oggetto (P)

| # | Prova | Risultato atteso |
|---|---|---|
| P1 | **Data → Object profile…** `51 Peg` | Le cinque sezioni arrivano in parallelo, in meno di un minuto; ogni valore ha la sua provenienza (servizio, server, tabella, data) |
| P2 | Profilo di `TRAPPIST-1` | Sette pianeti nella sezione Pianeti; distanza con il metodo dichiarato; SED con punti infrarossi |
| P3 | Profilo di `3C 273` | Nessuna distanza inventata: o la distanza di Bailer-Jones dichiarata come tale, o «nessuna distanza» con il motivo |
| P4 | Profilo da coordinate (`10.684708 41.268750`) | Bersaglio risolto per posizione, dichiarato (avviso «per posizione») |
| P5 | Avviare un profilo e premere **Cancel** subito dopo l'arrivo della prima sezione | Le sezioni già arrivate restano; le altre risultano annullate |
| P6 | **Rerun with fresh data** su 51 Peg | Nuovo comando; i valori non vengono dalla cache (provenienza senza «cache») |
| P7 | Tasto destro su una sorgente del catalogo di C1 → **Profile of this source** | Profilo della sorgente selezionata, con l'identificativo Gaia DR3 |

### 3.11 Esportazioni (E)

| # | Prova | Risultato atteso |
|---|---|---|
| E1 | Profilo di 51 Peg → **Export… → Values with provenance (ECSV)** | File ECSV leggibile in TOPCAT; una riga per valore con servizio, server, interrogazione, data |
| E2 | **Export… → Profile sheet (PDF)**, lasciando la lingua proposta | La lingua proposta è **inglese**, anche con l'app in italiano (L2); il PDF è tutto in inglese: intestazioni, avvisi e note |
| E3 | Esportare di nuovo lo stesso PDF in inglese con un altro nome, poi confrontare i due file (`shasum -a 256`) | Impronte **identiche** |
| E4 | Lo stesso PDF scegliendo «italiano» | Intestazioni e avvisi in italiano; impronta diversa da E3 |
| E5 | **Export… → SED plot (PNG)** e **Load SED points as catalog** | PNG con i limiti superiori come frecce; nuovo livello `SED 51 Peg` nel cielo e nella tabella |
| E6 | **File → Export view as PNG…** | PNG della vista con i crediti dei dati |
| E7 | Esportare in una cartella senza permesso di scrittura | Finestra «The export was not written» con il motivo; nessun file a metà |

### 3.12 Assistente IA (I)

| # | Prova | Risultato atteso |
|---|---|---|
| I1 | Pannello dell'assistente (⌃⌘A), provider **Ollama** o **LM Studio**, nessuna chiave | Il pannello dice *local · nothing leaves the Mac*; **Test the model** riesce |
| I2 | Con il modello locale: *«Go to the Pleiades and load Gaia DR3»* | Carta di conferma (rete), poi i due comandi nel pannello Comandi con origine IA |
| I3 | Provider cloud: **Add**, chiave incollata, **Save** | La chiave è nel Portachiavi di macOS (Accesso Portachiavi, voce di AstroTwo); in nessun file di `~/Library/Application Support/AstroTwo/` e in nessun log |
| I4 | Con il provider cloud: *«Make a profile of 51 Peg»* | Profilo eseguito come comando; nella risposta ogni numero ha il segno «verificato» rispetto al risultato del comando |
| I5 | Chiedere un numero che nessun comando ha dato (es. *«what is the mass of 51 Peg b in kg?»* senza profilo) | Il numero è segnato come «non viene da un comando»; con la modalità rigorosa la risposta si rigenera una volta |
| I6 | **What was sent** | Mostra la richiesta esatta mandata al provider, senza la chiave |
| I7 | Spegnere la rete e chiedere qualcosa | Messaggio chiaro di provider non raggiungibile; l'app resta usabile senza assistente |

### 3.13 Sessioni (R)

| # | Prova | Risultato atteso |
|---|---|---|
| R1 | Dopo H2, C1, X1 e P1: **File → Save session…** | File di sessione scritto |
| R2 | Chiudere l'app, riaprirla, **File → Open session…** | I comandi vengono rieseguiti nello stesso ordine; stessi livelli, stessi conteggi di righe; le esportazioni non si rieseguono da sole |
| R3 | Nel pannello Comandi, **Rerun** sull'esportazione PDF di E2 | Il file è riscritto **identico** (stessa impronta di E2) |

### 3.14 Lingue (L)

| # | Prova | Risultato atteso |
|---|---|---|
| L1 | **Settings… → Language → Italiano**, riavvio | Menu, pannelli, finestre e messaggi in italiano; i numeri con il punto decimale |
| L2 | Con l'app in italiano, ripetere E2 | Lingua proposta per il PDF: **inglese**; nessuna parola italiana nel PDF |
| L3 | Provocare un errore (es. F4) con l'app in italiano | Messaggio in italiano, con il codice dell'errore nei dettagli |
| L4 | Tornare all'inglese, riavvio | Tutto in inglese |
| L5 | Guardare la barra dei menu di macOS con l'app **installata in `/Applications`** dal `.dmg` (K3) aperta (correzione del D5b) | Il primo menu si chiama **AstroTwo**, non «python» (`40` §3.9; chi prova dal codice con `uv run astrotwo` vede lo stesso nome) |
| L6 | (Correzione del D5b.) Con l'app in italiano e in inglese, caricare un catalogo con **una sola** riga (es. cone search di 2″ su una stella isolata) e guardare barra di stato e pannello Layers | Singolare giusto: «Rete: 1 comando, …» / «Network: 1 command, …», «1 riga» / «1 row»; mai «1 comandi», «1 apps» (`40` §3.9) |

### 3.14bis Barra di stato e pannello Messaggi (U)

Prove aggiunte dopo la prova a mano del proprietario del 2026-11-10 (app dal codice, M45, CDS giù).
Insieme a L5 e L6 controllano, **sull'app installata dal `.dmg`**, le quattro
correzioni dello sprint D5b: barra in basso che non copre **Annulla** e mostra
un testo leggibile (U1, U2); «Rete: 1 comando» al singolare (L6); errore lungo
che si legge tutto (U3); nome **AstroTwo** nella barra dei menu (L5).

| # | Prova | Risultato atteso |
|---|---|---|
| U1 | *Go to* `M 45`, **Data → Catalog in view…** Gaia DR3, e guardare la barra di stato in basso a destra mentre carica | Titolo leggibile e tradotto («Loading catalog…» / «Caricamento catalogo…»), mai il nome interno `catalog.load_region` (che compare solo nel suggerimento); il titolo non copre la barra di avanzamento né **Cancel** / **Annulla** |
| U2 | Come U1 con la finestra stretta al minimo (trascinare il bordo) | Il titolo si accorcia con «…», **Annulla** resta intero e cliccabile; nessuna scritta sovrapposta |
| U3 | Provocare un errore con un testo lungo (es. D9, o il CDS giù con un catalogo VizieR) e guardare il pannello **Messages** / **Messaggi** | Passando sopra la riga, il suggerimento mostra tutto il testo; con la riga selezionata **Details…** / **Dettagli…** (o doppio clic) apre una finestra con il testo completo selezionabile; **Copy** / **Copia** (o ⌘C) mette il testo completo negli appunti (incollarlo in TextEdit per controllare) |

### 3.15 Servizi giù e mirror (D)

| # | Prova | Risultato atteso |
|---|---|---|
| D1 | Se il CDS è giù il giorno della prova: profilo di Vega | SIMBAD dal mirror di Harvard, dichiarato nella provenienza; la serie SED di VizieR saltata, con l'avviso; mai un vuoto in silenzio |
| D2 | Se il CDS è su: simulare il guasto bloccando `cds.unistra.fr` nel file `/etc/hosts`, poi profilo di Vega | Come D1 |
| D3 | Survey HiPS con il CDS giù (D1 o D2) | Il survey si apre da un mirror ufficiale, dichiarato |
| D4 | Rete spenta: *Go to* `M 31` dopo averlo già visitato | Tile dalla cache, con l'indicazione della cache; nomi non in cache → messaggio chiaro |
| D5 | Rete spenta: profilo nuovo | Sezioni in errore con il motivo; nessun valore inventato; l'app resta usabile |
| D6 | SIMBAD irraggiungibile (bloccare `simbad.cds.unistra.fr` e `simbad.harvard.edu` nel file `/etc/hosts`): profilo di `51 Peg` | La sezione Pianeti mostra il pianeta 51 Peg b trovato con il nome scritto, con l'avviso «identity not verified»; **mai** «No planet in the archive» se l'archivio dei pianeti non è stato interrogato (D25-23) |
| D7 | Come D6, bloccando anche l'archivio Gaia (`gea.esac.esa.int`): profilo da coordinate `346.6223 -5.0414` | Intestazione della sezione Pianeti «Planets · Not checked» (non «Arrived»), avviso con il motivo, mai «No planet in the archive»; nel PDF «Status: not checked» |
| D9 | Bloccare solo il mirror di Harvard (`simbad.harvard.edu`) in `/etc/hosts` in un giorno in cui il CDS risponde 404 (o bloccare entrambi): profilo di `Vega` | Errore della sezione Identità «no server answers (tried 2 …)» che riporta anche il **primo errore** (il messaggio del server del CDS) |
| D8 | Esportare un PDF e un PNG (E2, E6), poi `ls -l` sui file | Permessi `-rw-r--r--` (0644 con l'umask normale), non `-rw-------` |

## 4. Cosa NON fa

- Non sostituisce i test automatici (`uv run python -m pytest -q`) né le
  misure della pagina di validazione (`docs/validation.md`).
- Non misura i tempi in modo preciso: i tempi del profilo sono nel `25`
  §3.17; qui si scrive solo un ritardo evidente.
- Non prova la costruzione del `.dmg` (`60`): parte dal `.dmg` già costruito;
  ne controlla solo l'impronta e il contenuto (K1–K3).

## 5. Livello e dipendenze

- **Livello:** non applicabile (elenco di prove, non un modulo dell'app).
- **Dipende da:** tutti i moduli dell'app in fase codice (05, 10–19, 20 parte SED, 25, 30–35, 40–44, 60).
- **Usato da:** piano dei rilasci (`panoramica.md` §2): la 1.0 si rilascia dopo il megatest.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `.dmg` candidato alla 1.0 e il suo `.sha256` | file | — | app costruita con `scripts/build_app.py`, `.dmg` e impronta con `scripts/make_dmg.py` (`63` passi 6–8) |
| in | file di prova | FITS, VOTable/CSV, MOC | — | §3.1 |
| out | esito del megatest | testo | una riga per prova: OK / KO / non fatta | con data, versione dell'app e di macOS |

## 7. Interfaccia pubblica

Non applicabile: è un elenco di prove a mano, senza codice.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel megatest | Motivazione |
|---|---|---|
| TOPCAT | confronto di incroci e query (X2, Q2), prove SAMP (S1–S6) | programma di riferimento della comunità, indipendente da AstroTwo |
| SAMP 1.3 (IVOA) | prove S1–S6 | standard dei collegamenti tra programmi VO |
| `shasum -a 256` (macOS) | K1, E3, R3 | impronta del `.dmg` (K1); confronto byte per byte dei file esportati |

## 9. Regole e vincoli

- Le prove si fanno sull'app installata in `/Applications` dal `.dmg`
  candidato (`63` passo 9), non sul codice né su `dist/AstroTwo.app`.
- Un risultato atteso che dipende da un servizio esterno si giudica solo se il
  servizio risponde; altrimenti «non fatta», con il servizio e l'ora.
- Ogni KO si scrive con la prova, cosa si è visto e, se possibile, il file di
  sessione o lo screenshot fatto dalla persona che prova.
- Regola d'oro n. 1: in I4 e I5 nessun numero dell'assistente deve comparire
  come verificato se non viene da un comando.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Servizio esterno giù durante una prova | prova «non fatta», con servizio e ora; D1–D3 se è il CDS | — |
| TOPCAT non installato | prove S e X2, Q2 «non fatte» | — |
| Nessun modello locale o nessuna chiave | prove I1–I2 o I3–I6 «non fatte» | — |
| L'app si chiude da sola | KO bloccante, con la prova in corso | — |
| K1 dà `FAILED` o K2 mostra altre voci | KO bloccante: il `.dmg` non è il candidato giusto; si ricostruisce (`63` passo 7 o 8) | — |

## 11. Esposizione all'IA

Non applicabile: il megatest è fatto da una persona; le prove dell'assistente sono in §3.12.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Elenco completo | rileggere §3 | tutte le aree chieste dal proprietario (atlante, FITS, cataloghi, incrocio, ADQL, MOC, SAMP con TOPCAT, profili, esportazioni anche in inglese, assistente locale e con chiave, sessioni, lingue, servizi giù e mirror) hanno almeno una prova | lettura |
| T2 | Prove eseguibili | una persona che non ha scritto il file fa il megatest | ogni prova si capisce senza chiedere | esito del megatest |

## 13. Decisioni aperte

- **D62-1 — Scelte minori del megatest: APPROVATE dal proprietario il
  2026-11-10** (proposte da Claude Code lo stesso giorno, approvate così
  come sono): (1) numero 62 (il 61 resta alla strategia
  dei test); (2) prove sull'app costruita dal `.dmg`, non su `uv run`;
  (3) rilascio con zero KO o con i KO dichiarati non bloccanti dal
  proprietario nelle note di rilascio; (4) servizio esterno giù = «non
  fatta», non KO; (5) prove di confronto con TOPCAT (X2, Q2) dentro il
  megatest, oltre alla pagina di validazione.

**Decisioni aperte dalle prove automatiche dello sprint D12 (2026-11-12)**
(esito e dettagli in `docs/megatest-runs/1.0.0.md`, «Prove automatiche»;
nessuna correzione fatta; le decide il proprietario):

- **D62-2 — Grafico della SED assente nell'app costruita: DA DECIDERE, bloccante,
  richiede un build 8.** In `scripts/build_app.py` (`EXCLUDES`, righe 71–73)
  sono esclusi `matplotlib.backends.backend_qtagg`, `backend_qt` e
  `matplotlib.pyplot`. `PhotometryView._plot` (`43`, `src/astrotwo/ui/profiles.py:604`)
  importa `backend_qtagg`. Nel build 7 (PYZ verificato) l'import fallisce: la
  finestra Profili resta «Running», **Export…** e **Load SED points as
  catalog** restano disattivati per ogni profilo con punti SED (P1, P2, E1–E5).
  Proposta: **(a)** togliere `backend_qtagg` e `backend_qt` da `EXCLUDES`
  (`pyplot` può restare escluso, perché il codice non lo usa), aggiungere
  all'autocontrollo V4 (`60` §3.8) l'import dei moduli caricati solo dentro le
  funzioni (almeno `backend_qtagg`) e un test che lo controlla; nuovo candidato
  build 8 dal passo 3 della `63`, poi megatest a mano sul build 8. **(b)**
  Disegnare il grafico come immagine con `backend_agg` (già nel bundle) invece
  del widget Qt: anche questo vuole un build 8 e cambia il `43`. Consiglio di
  Claude Code: **(a)**, la correzione più piccola, che non cambia il
  comportamento specificato.
- **D62-3 — «Profile of this source» su righe Gaia DR3 assenti da SIMBAD:
  DA DECIDERE.** Il `43` (§3.2 punto 5, §10) manda `name = "Gaia DR3 <id>"`. Se
  SIMBAD non conosce la sorgente, il profilo finisce in `NAME_NOT_FOUND` senza
  sezioni (P7, provato su due righe delle Pleiadi). Proposta: **(a)** se il nome
  riconosciuto dalla riga dà `NAME_NOT_FOUND`, ripartire con `layer` + `row`
  (profilo per posizione, già previsto per le righe senza identificativo),
  dichiarandolo; cambia `43` e codice, quindi va nel build 8 se D62-2 lo apre;
  **(b)** lasciare così e dichiararlo nelle note di rilascio e nella `62` (P7 con
  una stella nota a SIMBAD). Consiglio: (a) se si fa comunque il build 8,
  altrimenti (b).
- **D62-4 — Un livello con il corpo ignoto blocca gli altri caricamenti:
  DA DECIDERE, non bloccante.** Con un CSV aperto e le colonne non confermate,
  cone search, ADQL, FITS e MOC falliscono tutti con un `BODY_UNKNOWN` che parla
  del CSV. È la regola del `13` §10 e del `19`. Proposta: **(a)** nessun build,
  dirlo in `docs/quickstart.md` e nelle note di rilascio; dopo la 1.0, un
  messaggio che dica quale livello blocca e come sbloccarlo (confermare le
  colonne o togliere il livello); **(b)** cambiare la regola (un dato a corpo
  ignoto non impedisce agli altri di aprirsi): decisione di specifica sul `19`.
  Consiglio: (a).
- **D62-5 — Immagini del README assenti: DA DECIDERE, non bloccante (solo
  documentazione, nessun build).** `README.md` righe 12–14 citano
  `docs/screenshots/pleiades-gaia.png`, `profile-51peg.png` e `ai-panel.png`,
  che non esistono. Proposta: **(a)** tre immagini fatte da Guido durante il
  megatest a mano, aggiunte con un commit di sola documentazione prima del tag;
  **(b)** togliere le tre righe. Consiglio: (a).
- **D62-6 — Dettagli minori di lingua e di aspetto: DA DECIDERE, non
  bloccante.** PDF in italiano con «done» non tradotto, una nota in inglese e
  le intestazioni «Separazione» e «Note» che si toccano; riga italiana nel
  dialogo «Position columns» inglese; nomi di servizi in italiano nei livelli
  dell'interfaccia inglese; messaggio tecnico di `MOC_TYPE_REQUIRED`; ultimo
  carattere del titolo della barra di stato forse tagliato senza «…» (U1, da
  vedere a mano). Consiglio: correggerli nel build 8 se D62-2 lo apre e se non
  allargano il lavoro, altrimenti dopo la 1.0.
- **D62-7 — Testo di alcune prove di questo file: DA DECIDERE (solo questo
  file).** C1: dire di stringere il campo (con il campo delle Pleiadi Gaia ha
  più di 5000 righe: `REGION_TOO_LARGE`); P4: le coordinate del nucleo di M 31
  danno 40 candidati SIMBAD (finestra di scelta), quindi l'atteso va riscritto
  o va scelta un'altra posizione; E5: usare un oggetto con limiti superiori
  (51 Peg non ne ha); M1: il MocServer risponde 413 al MOC di un survey intero,
  meglio il `Moc.fits` del survey HiPS; I1–I2: Ollama **o** LM Studio. Consiglio:
  correggere il testo prima della prova a mano (stato `bozza` invariato).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-11-10 | Claude Code | Creazione del file (stato: bozza), sprint D2, brief del proprietario del 2026-11-10 punto (d): prove brevi con risultato atteso per avvio, atlante, FITS, cataloghi, incrocio, cone search e ADQL, MOC, SAMP con TOPCAT, profili, esportazioni (anche in inglese, byte per byte), assistente locale e con chiave, sessioni, lingue, servizi giù e mirror; D62-1 aperta. |
| 2026-11-10 | Claude Code | **Decisioni del proprietario del 2026-11-10 (dopo D2b):** D62-1 **approvata** (§13; scelte già scritte in §3.1). Nuove prove D6 e D7 (D25-23, assenze solo dopo una richiesta) e D8 (permessi dei file esportati, decisione del 2026-11-10). Stato `bozza` invariato. |
| 2026-11-10 | Claude Code | **Decisioni del proprietario del 2026-11-10 (sprint D3b):** D7 con l'intestazione «Not checked» e la riga di stato del PDF; nuova prova D9 (messaggio del primo server quando cadono tutti). Stato `bozza` invariato. |
| 2026-11-10 | Claude Code | **Sprint D4 (decisioni del proprietario del 2026-11-10):** nuova prova A4 (app firmata Developer ID e notarizzata, solo se la candidata lo è; firma preparata in `60` §3.12, non ancora eseguita). Stato `bozza` invariato. |
| 2026-11-10 | Claude Code | **Sprint D5b (prova a mano del proprietario del 2026-11-10):** nuove prove L5 (nome «AstroTwo» nella barra dei menu, corretto anche avviando dal codice), L6 (plurali) e §3.14bis U1–U3 (titolo leggibile del comando senza coprire Annulla, finestra stretta, messaggi lunghi con suggerimento, Dettagli…, doppio clic e Copia). Stato `bozza` invariato. |
| 2026-11-11 | Claude Code | **Sprint D6 (decisioni del proprietario del 2026-11-11):** il megatest si fa sull'app installata dal `.dmg` candidato (`63` passo 9; §3.1, §9); nuove prove **K1–K3** del `.dmg` (impronta con `shasum -a 256 -c`, volume con sole due voci AstroTwo e Applications, trascinamento in `/Applications`; D60-7), A1 riscritta di conseguenza; le quattro correzioni del D5b richiamate in §3.14bis (U1, U2, U3) e in L5, L6, L5 sull'app installata; §4, §6, §8, §10 aggiornati. Stato `bozza` invariato. |
| 2026-11-11 | Claude Code | **Sprint D8 (A6-b decisa dal proprietario il 2026-11-11: 1.0 senza firma Developer ID):** A4 riscritta per l'app senza firma (avviso al primo avvio e «Apri comunque» secondo `docs/installation.md`, `.dmg` scaricato con l'attributo di quarantena); la prova «nessun avviso» resta come A4bis per la prima versione firmata. |
| 2026-11-12 | Claude Code | **Sprint D12 (decisioni del proprietario del 2026-11-12: prove automatiche prima del megatest a mano, sul candidato build 7):** esito delle prove automatiche in `docs/megatest-runs/1.0.0.md` (84 prove: 48 ok, 9 problema, 27 non fatte, da fare a mano); nuove decisioni aperte **D62-2** (grafico della SED assente nell'app costruita, bloccante, build 8), **D62-3** (profilo di una riga Gaia assente da SIMBAD), **D62-4** (livello a corpo ignoto che blocca gli altri), **D62-5** (immagini del README), **D62-6** (dettagli di lingua e di aspetto), **D62-7** (testo di C1, P4, E5, M1, I1–I2) in §13. Nessuna correzione al codice né alle prove. Stato `bozza` invariato. |
