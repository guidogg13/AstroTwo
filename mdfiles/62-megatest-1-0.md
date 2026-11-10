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

- **Chi:** il proprietario o una persona da lui indicata, sul Mac, con l'app
  costruita dal `.dmg` candidato alla 1.0 (non da `uv run`).
- **Prima di cominciare:**
  - Mac con macOS 15 o successivo, Apple silicon (`docs/installation.md`);
  - **TOPCAT** installato (per SAMP e per i confronti);
  - per l'assistente: **Ollama** o **LM Studio** con un modello scaricato, e
    una chiave API di un provider cloud;
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

### 3.2 Avvio e installazione (A)

| # | Prova | Risultato atteso |
|---|---|---|
| A1 | Aprire il `.dmg`, trascinare AstroTwo in Applicazioni, primo avvio con «Apri comunque» (`docs/installation.md`) | L'app si apre; nessun messaggio di errore; **AstroTwo → About AstroTwo** dice la versione 1.0 candidata |
| A2 | Chiudere e riaprire l'app | Si riapre con le stesse preferenze; nessuna finestra di errore |
| A3 | **Help → Licenses…** | Elenco delle licenze di terze parti, Qt (LGPL) compresa; si chiude senza errori |
| A4 | Solo se il `.dmg` candidato è firmato Developer ID e notarizzato (A6-b, `60` §3.12; altrimenti «non fatta»): scaricarlo su un altro Mac, aprirlo, primo avvio con doppio clic; poi `spctl --assess --type execute -vv /Applications/AstroTwo.app` | L'app si apre **senza** «Apri comunque»; `spctl` dice `accepted` e `source=Notarized Developer ID` |

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
- Non prova la costruzione del `.dmg` (`60`): parte dal `.dmg` già costruito.

## 5. Livello e dipendenze

- **Livello:** non applicabile (elenco di prove, non un modulo dell'app).
- **Dipende da:** tutti i moduli dell'app in fase codice (05, 10–19, 20 parte SED, 25, 30–35, 40–44, 60).
- **Usato da:** piano dei rilasci (`panoramica.md` §2): la 1.0 si rilascia dopo il megatest.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `.dmg` candidato alla 1.0 | file | — | costruito con `scripts/build_app.py` |
| in | file di prova | FITS, VOTable/CSV, MOC | — | §3.1 |
| out | esito del megatest | testo | una riga per prova: OK / KO / non fatta | con data, versione dell'app e di macOS |

## 7. Interfaccia pubblica

Non applicabile: è un elenco di prove a mano, senza codice.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel megatest | Motivazione |
|---|---|---|
| TOPCAT | confronto di incroci e query (X2, Q2), prove SAMP (S1–S6) | programma di riferimento della comunità, indipendente da AstroTwo |
| SAMP 1.3 (IVOA) | prove S1–S6 | standard dei collegamenti tra programmi VO |
| `shasum -a 256` (macOS) | E3, R3 | confronto byte per byte dei file esportati |

## 9. Regole e vincoli

- Le prove si fanno sull'app costruita, non sul codice.
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

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-11-10 | Claude Code | Creazione del file (stato: bozza), sprint D2, brief del proprietario del 2026-11-10 punto (d): prove brevi con risultato atteso per avvio, atlante, FITS, cataloghi, incrocio, cone search e ADQL, MOC, SAMP con TOPCAT, profili, esportazioni (anche in inglese, byte per byte), assistente locale e con chiave, sessioni, lingue, servizi giù e mirror; D62-1 aperta. |
| 2026-11-10 | Claude Code | **Decisioni del proprietario del 2026-11-10 (dopo D2b):** D62-1 **approvata** (§13; scelte già scritte in §3.1). Nuove prove D6 e D7 (D25-23, assenze solo dopo una richiesta) e D8 (permessi dei file esportati, decisione del 2026-11-10). Stato `bozza` invariato. |
| 2026-11-10 | Claude Code | **Decisioni del proprietario del 2026-11-10 (sprint D3b):** D7 con l'intestazione «Not checked» e la riga di stato del PDF; nuova prova D9 (messaggio del primo server quando cadono tutti). Stato `bozza` invariato. |
| 2026-11-10 | Claude Code | **Sprint D4 (decisioni del proprietario del 2026-11-10):** nuova prova A4 (app firmata Developer ID e notarizzata, solo se la candidata lo è; firma preparata in `60` §3.12, non ancora eseguita). Stato `bozza` invariato. |
