# 40-ui-finestra-principale.md — finestra principale, menu, barra di stato, preferenze

**Stato:** approvato

## 2. Scopo

Dare all'utente una finestra unica da cui aprire dati, comandare la vista
del cielo, vedere la cronologia dei comandi e i messaggi dei moduli e
regolare le preferenze essenziali, facendo passare ogni azione dal registro
dei comandi (`05`) senza mai bloccare l'interfaccia.

## 3. Cosa fa

### 3.1 Perimetro della prima versione (v1)

Perimetro approvato dal proprietario il 2026-10-15. La v1 dell'interfaccia
(40, 41, 42 minimo) usa **solo il livello 1**; **dal 2026-10-16** (proposta
della fase 1 sull'IA approvata) la v1 comprende anche il **pannello
dell'assistente (44)**, che usa il livello 3 (30, 31, 32, 34, 35) sopra i
comandi del livello 1. Senza assistente la finestra funziona identica
(regola d'oro n. 7).

- **In v1:** menu, barra di stato, campo "Vai a", preferenze essenziali,
  apertura di file (immagine FITS, catalogo, MOC) e di sessioni, pannello
  Comandi (cronologia visibile e rieseguibile), pannello Messaggi, schermo
  intero (A10), coda dei comandi in un thread di lavoro con avanzamento e
  Annulla, **pannello dell'assistente (44)** nell'area a destra,
  impostazioni dell'assistente nelle preferenze, colonna "chi" nella
  cronologia.
- **Fuori dalla v1** (versioni successive): segnalibri e storico delle
  posizioni (A12, H13, H16), console degli script e modalità demo o guida
  (H13), avvio tramite URL (H18, D40-2), finestre delle calcolatrici (18),
  preferenze non essenziali (cifre di visualizzazione DC3, timeout CA1,
  limiti di memoria e delle tabelle, dati planetari D19-5, server
  predefiniti, tema), pannello analisi (43), viste
  multiple (45). Finché non hanno un'interfaccia valgono i default dei
  moduli. (Il pannello IA, 44, è entrato nella v1 il 2026-10-16.)

### 3.2 Disposizione

- Al centro il **visualizzatore del cielo** (`41`).
- Pannelli agganciabili (spostabili e richiudibili, comportamento standard
  di Qt): **Livelli** (del `41`), **Tabella** (`42`), **Comandi** e
  **Messaggi** (di questo modulo).
- **Pannello dell'assistente (44, dal 2026-10-16):** nell'area agganciabile
  a destra, larga 380–420 pt, richiudibile, con un pulsante nella barra
  degli strumenti e la voce di menu **Assistant** attiva (contenuto e
  comportamento nel `44`). Senza profilo, chiave o consenso il pannello
  dice perché l'assistente non è disponibile; il resto della finestra non
  cambia.
- Geometria della finestra e dei pannelli salvata nelle impostazioni
  dell'app (non nella sessione).

### 3.3 Menu

Testi in inglese nel codice, tradotti in italiano (A9, §3.9). Ogni voce
che agisce sui dati produce un comando del `05` (nome tra parentesi).

- **File:** Open image… (`image.open`); Open catalog… (`catalog.open_file`);
  Open MOC… (`moc.open`); Open session… / Save session… (sessione del
  `05`, §3.8); Export view as PNG… (`view.export_png`, disegno del `41`);
  Quit.
- **View:** Go to… (porta il fuoco sul campo "Vai a"); Zoom in (⌘+) e Zoom out (⌘−) (zoom del `41` §3.4); Coordinate grid
  (`view.set_grid`, con frame ICRS o galattico); Show north and east e Show scale bar (`view.set_overlays`, 41 §3.18); Coordinates shown (ICRS
  sessagesimale, ICRS decimale, galattico: `view.set_coordinate_display`);
  Full screen (A10, `ui.set_fullscreen`); Night mode (modalità notte rossa,
  `ui.set_appearance`, §3.11; ⌃⌘N, D40-4).
- **Data:** HiPS survey… (finestra con un campo di ricerca sulla copia
  locale delle collezioni, `CollectionIndex.filter` del 12, e un campo per
  identificativo o URL: `hips.set_survey`); Catalog in view… (finestra con
  l'identificativo del catalogo come lo accetta `load_catalog` del 13 —
  VizieR, Simbad, Gaia DR3 dall'elenco dei server del 14, D14-4 — e
  `max_rows` con il default 100 000 di D14-5; centro e raggio sono quelli
  della vista calcolati dal 10: `catalog.load_region`).
- **Tools:** Distance (strumento di misura del `41`); Simbad pointer
  (puntatore del `41`). L'attivazione è `ui.set_tool`.
- **Window:** mostra o nasconde i pannelli.
- **Help:** About AstroTwo (versione SemVer, DC4, e testo di
  `THIRD_PARTY_LICENSES`).
- **Assistant** (voce nel menu Window e pulsante nella barra degli
  strumenti, ⌃⌘A): mostra o nasconde il pannello del `44` (`ui.*`, classe
  `application`).
- Scorciatoie standard di macOS (⌘O apri, ⌘S salva sessione, ⌘Q esci,
  ⌃⌘F schermo intero; ⌃⌘N modalità notte, D40-4).

### 3.4 Campo "Vai a" (A2, A3)

Accetta un nome di oggetto o una coppia di coordinate; produce
`view.go_to` con il testo scritto: il `05` lo interpreta con il 10
(`resolve_name` per un nome, `parse_sexagesimal`/`convert_coordinates` per
le coordinate) e centra la vista. Il risultato mostra la fonte (SIMBAD,
"dalla cache" con origine e data, epoca J2000 dichiarata). Nome non
trovato o rete assente: messaggio del 10 nel pannello Messaggi e, per 10 s, nella barra di stato (2026-10-17). Dopo un "Vai a" riuscito la vista si porta a un campo di circa 1° se era maggiore di 1,25° (`41` §3.4).

### 3.5 Barra di stato

- **Sotto il mouse:** coordinate nel sistema scelto, valore del pixel con
  unità e coordinate pixel in convenzione FITS (DC7), dal risultato di
  `cursor.read` (`41`); testo "fuori dal cielo" o "nessun dato" quando il
  modulo non dà un valore.
- **Attività di rete:** numero di comandi di rete in corso e di tile HiPS
  in arrivo.
- **Comando in corso:** nome, avanzamento (passo n di m o indeterminato) e
  pulsante **Annulla** per ogni comando lungo (regola del proprietario del
  2026-10-15).

### 3.6 Pannello Comandi (cronologia visibile)

- Una riga per comando della cronologia del `05`: numero, ora (UTC),
  **chi** (dal `requested_by` del `05`: "Utente" per menu, tastiera, mouse
  e Riesegui; "IA" per i comandi chiesti dall'assistente; "Sessione" per
  la riapertura), nome, parametri in breve, esito (ok, errore, annullato),
  numero di avvisi. Filtro per classe (`session` di default, `application`
  a richiesta; D05-1) e per chi (tutti di default).
- Per i comandi dell'IA il dettaglio mostra anche conversazione, turno,
  profilo e modello, e se l'utente ha confermato il comando (`32` §3.5).
- Selezionando una riga: parametri completi, risultato, avvisi, provenienza
  (origine e data dei dati di rete o della cache).
- **Riesegui** (uno o più comandi selezionati): li rimette in coda come
  nuovi comandi, con nuovi numeri. **Copia come JSON**: la forma JSON del
  comando (`05`).

### 3.7 Pannello Messaggi ed errori

- Ogni errore e avviso dei moduli compare con **codice e testo del
  modulo, invariati**, e il numero del comando che lo ha prodotto; errori
  in rosso.
- Errore di un comando: segnalazione non bloccante (voce nel pannello
  Messaggi e riga rossa nella cronologia). **Finestra modale solo se
  l'azione non può proseguire** (file illeggibile, sessione fermata dal
  `05` per un file cambiato o mancante).
- **Lingua dei messaggi dei moduli (D40-3, decisa il 2026-10-24; supera
  D40-1):** ogni messaggio mostra il **testo del catalogo dei messaggi
  (§3.7.1) nella lingua dell'interfaccia**, inglese o italiano, con il
  **codice sempre visibile e invariato**. Il testo originale del modulo non
  si perde: è il campo `text` del risultato (§3.7.1) e compare nel
  dettaglio della voce ("Copia come JSON" e dettagli del comando).

#### 3.7.1 Catalogo dei messaggi (D40-3)

**Contratto dei moduli (modifica trasversale ai moduli 10–19, a `04`, `05`,
`30`–`35` e ai messaggi di `40`–`44`: sprint 8b–8e, un modulo alla volta).** Ogni errore e ogni
avviso nasce come **codice + parametri strutturati** (`params`: dizionario
nome → valore JSON, vedi sotto), non solo come testo italiano già
formattato:

- le eccezioni dei moduli (`CommandError`, `CatalogsError`, …) ricevono
  `params=` con tutti i valori che oggi finiscono nel testo; gli avvisi
  (coppie codice/testo) diventano `ResultMessage(code, text, params)`;
- `text` resta, **invariato**: testo di diagnostica del modulo (italiano
  oggi), mai più mostrato come testo principale quando il catalogo ha la
  voce; serve come ripiego (§3.7.2), nei file di sessione già scritti e
  nei test dei moduli esistenti;
- i **valori** in `params` sono quelli del modulo, **mai arrotondati né
  riformattati** dal catalogo: numeri JSON con la loro unità in un
  parametro accanto (`{"value": ..., "unit": ...}`, come nei valori dei
  comandi), stringhe così come sono, punto decimale sempre (§3.9). Un
  valore che arriva da un servizio esterno (messaggio d'errore di un
  servizio, nome di un file, valore di una cella) è un parametro
  contrassegnato **testo esterno** (`external`: true nel catalogo) e si
  inserisce tale e quale, **senza tradurlo**; nel `32` resta classificato
  testo esterno (dato, mai istruzione);
- i moduli scientifici **non** contengono traduzioni né dipendono dal
  catalogo: restituiscono codice e parametri e basta (regola d'oro n. 1:
  nessun numero viene da un testo scritto altrove).

**Catalogo.** Un'unica tabella **codice → testo inglese e testo italiano**
con segnaposto nominati (`{name}`, `{value}`, `{unit}`), in un solo file
(`messages_catalog`) con una voce per codice, formato fisso:
`code`, `en`, `it`, elenco dei parametri attesi (nome, tipo, `external`
sì/no). I segnaposto si riempiono **solo per sostituzione** del valore così
com'è (`str()` della sua rappresentazione JSON, valori con unità: valore,
spazio, unità): nessun arrotondamento, nessuna conversione, nessuna
formattazione locale. Una voce può avere il segnaposto in qualunque
posizione, quindi l'ordine delle parole cambia tra le lingue senza
problemi. Le graffe che fanno parte del testo si scrivono raddoppiate
(`${{nome}}` mostra `${nome}`, `'}}'` mostra `'}'`); un elenco vuoto (parametro
di tipo `list`) si inserisce come "—".

**Lingua.** `message_text(code, params, lang)` restituisce il testo nella
lingua richiesta; il pannello Messaggi, la cronologia, le finestre modali e
le righe di errore dei pannelli usano la lingua dell'interfaccia (§3.9,
cambio al riavvio). **Verso l'IA la lingua è sempre l'inglese**, qualunque
sia quella dell'interfaccia (regole R1–R9 e `SYSTEM_RULES` sono in
inglese, `35` §3.4): il risultato di un comando consegnato al modello
contiene il codice, i parametri e il testo **inglese** del catalogo
(`32` §3.7: campo `text` sostituito con `message_text(..., "en")`; i
parametri `external` restano nella lingua originale, come testo esterno).
Il pannello dell'assistente (`44`) mostra invece ciò che mostra il resto
dell'interfaccia, nella lingua scelta.

**Varianti per ragione (D40-6, decisa il 2026-10-24).** Un codice che i moduli
sollevano per ragioni diverse (es. `COORD_UNIT_MISSING`: unità mancante,
unità non angolare, argomento mancante) ha **una voce con testo generale e
sotto-voci**: ogni sotto-voce ha `en`, `it` e i propri parametri, ed è scelta
dal parametro riservato `reason`, un identificatore stabile in inglese
minuscolo (es. `"not_angular"`), mai un testo. Senza `reason`, o con un
`reason` che la voce non conosce, vale il testo generale. `reason` fa parte
di `params` (quindi dei file di sessione e dei risultati verso l'IA) ma non
si inserisce nel testo. Il codice resta quello dei `.md` dei moduli:
nessun identificatore cambia. Ogni sotto-voce ha le stesse regole della
voce (segnaposto uguali nelle due lingue, parametri dichiarati, test T18).

**Messaggi annidati (D40-7, decisa il 2026-10-24).** Quando il testo di un messaggio
incorpora un altro messaggio **di AstroTwo** (la causa di una copertura non
disponibile, la diagnosi di un tile corrotto, un errore di un altro modulo di
AstroTwo rilanciato o citato), il parametro ha tipo `message`: un oggetto
`{"code": <codice>, "params": {...}, "text": <testo originale del modulo>}`
con gli stessi `code` e `params` del messaggio che descrive (e quindi, a sua
volta, `reason` e parametri `message`). `message_text` lo rende **in modo
ricorsivo** con la stessa lingua, la stessa voce e le stesse regole del messaggio
di primo livello (sotto-voci per `reason`, sostituzione senza modifiche dei
valori); `text` serve solo come ripiego (§3.7.2) quando il codice annidato non
ha voce o non ha `params` (modulo non ancora convertito: nota "(no translation)"
/ "(nessuna traduzione)"). **Profondità massima: 3 livelli** di annidamento
sotto il messaggio di primo livello (`MAX_MESSAGE_DEPTH`); oltre il limite si
mostra il solo codice. Un codice usato **solo come messaggio annidato**
(diagnosi, es. `HIPS_TILE_PROBLEM` del 12) ha la sua voce e le sue sotto-voci
come ogni altro, ed è dichiarato nel `.md` del suo modulo.
Un parametro può anche essere un **elenco di messaggi annidati** (tipo `messages`,
es. le differenze tra FIELD e dati collegati di un ASTRORES): si rende un
messaggio dopo l'altro, separati da "; ", con le stesse regole e lo stesso
limite di profondità. Il **testo di terzi resta parametro `external`**, non tradotto (eccezioni di
librerie come astropy, risposte dei servizi, motivi `ASTRORES`, valori di
file): anche dentro un messaggio annidato un suo parametro `external` resta
esterno. **Verso l'IA** (`32` §3.7): il messaggio annidato è reso in inglese
col resto del testo; i suoi parametri `external` viaggiano marcati come testo
esterno (`{"external_text": ...}`) e nel testo restano `<nome>`; un annidato
ripiegato su `text` (senza voce) è testo esterno e nel testo resta `<nome del
parametro>`. Gli errori di 14, 16 e 19 incorporati da 12 e 13 sono messaggi annidati (sprint 8d, fatto).

**Contesto di livello (sprint 8f, 2026-10-25).** Un messaggio che nasce mentre si lavora su un livello
(disegno di un catalogo o di un MOC, avvisi di epoca) porta nei `params` il parametro di contesto riservato
`layer_context`: `{"id": "L2", "name": "Gaia DR3", "kind": "catalog"}` con `kind` tra `catalog`, `moc`, `image`,
`hips`. Come `reason` **non si dichiara nelle voci** e vale per qualunque codice; `message_text` lo premette al testo,
nella lingua richiesta: «Catalog layer L2 «Gaia DR3»: …» / «Livello catalogo L2 «Gaia DR3»: …» (etichette: *Catalog /
MOC / Image / HiPS layer*, *Livello catalogo / MOC / immagine / HiPS*); con il nome vuoto si omette («MOC layer L2: …»).
Il nome del livello (scelto dall'utente o letto da un file) è **testo esterno**: verso l'IA nel testo resta
`<layer_name>` e nei `params` viaggia come `{"external_text": ...}` (`32` §3.7). Non va confuso con un parametro
dichiarato di nome `layer` (identificativo `L<n>` citato nel testo, es. `LAYER_UNKNOWN`). `validate_params` (T18) rifiuta un
`layer_context` malformato. Il testo originale `text` continua a cominciare con il nome del livello (ripiego, §3.7.2).

**Posizione del catalogo (D40-5, decisa il 2026-10-24).** L'IA (livello 3)
non può importare l'interfaccia (dipendenze solo verso il basso, regola d'oro
n. 7): il catalogo sta nel modulo neutro `src/astrotwo/messages_catalog.py`,
senza dipendenze (solo dati e `message_text`), importato sia da `ui/` sia da
`ai/`; i moduli 10–19 e il `05` non lo importano (restituiscono solo codice e
`params`). La tabella è una sola.

**Passaggio graduale (sprint 8b–8e, concluso il 2026-10-25).** Finché un modulo non era convertito i suoi codici
non erano nel catalogo e si mostravano come in §3.7.2 (testo originale con la nota "(nessuna traduzione)"). Gli
sprint 8b–8d hanno convertito i moduli 10–19, lo sprint 8e il `04`, il `05`, i moduli IA `30`–`35` e i messaggi
scritti direttamente da `40`, `41`, `42` e `44` (§10.1 di ognuno). Il test T18 controlla ora **tutto**
`src/astrotwo`, non più un elenco di moduli: ogni codice che un file solleva o restituisce ha la voce con `en` e
`it`; un modulo nuovo con un codice senza voce fa fallire il test.

#### 3.7.2 Codice senza voce nel catalogo

- Un codice non presente nel catalogo non deve esistere (test T18): se
  compare comunque (errore di programmazione o sessione scritta da una
  versione più recente), l'interfaccia mostra il codice, il testo
  originale `text` e la nota "(no translation)" / "(nessuna traduzione)";
  all'IA va il testo originale. Non si inventa mai una traduzione.
- Un parametro atteso ma assente dal messaggio: segnaposto lasciato visibile
  (`{name}`) e voce di log; il messaggio si mostra comunque.
- Sessioni scritte prima di D40-3: i messaggi senza `params` si mostrano
  con il testo originale (come sopra); la riesecuzione non cambia.

### 3.8 Coda dei comandi e thread

Architettura approvata dal proprietario il 2026-10-15:

- **Una coda dei comandi in un thread di lavoro** (`QThread`): i comandi
  di classe `session` e `application` si eseguono con il registro del `05`,
  uno alla volta, nell'ordine di arrivo.
- **I risultati tornano al thread principale con i segnali di Qt**
  (connessioni in coda); il thread principale non esegue mai un comando
  della coda.
- Le letture passive senza rete (`cursor.read`) si eseguono con il
  registro nel thread principale perché durano pochi millisecondi; quelle
  con rete vanno nel gruppo di thread del `41` (D05-1, D41-1).
- **Annulla:** imposta il `CancelToken` del `05` (annullamento cooperativo:
  il risultato si scarta, lo stato non cambia).
- **Uscita con comandi in corso:** richiesta di conferma; se confermata,
  annullamento e attesa del ritorno della funzione in corso entro i
  timeout di rete del `04`.
- **Comandi dell'assistente:** entrano nella **stessa coda** con
  `requested_by = ai` (`32` §3.5); l'assistente (`35`) gira in un thread
  proprio e aspetta il risultato con i segnali di Qt; Annulla nella barra di
  stato e Stop del `44` impostano lo stesso `CancelToken` del comando.
  Nel codice (sprint 6c del 2026-10-22): `MainWindow.assistant_executor()`
  dà al `35` l'esecutore della coda; `submit_command(command, cancel)`
  accetta il `CancelToken` della risposta, così Stop annulla anche un
  comando dell'assistente ancora in coda; il thread dell'assistente riprende
  dopo che la finestra ha mostrato il risultato; all'uscita le attese
  dell'assistente si chiudono come annullate.
- **Sessione:** Open session riapre con la riesecuzione del `05` (comando
  lungo, con avanzamento e Annulla); gli stop del `05` si mostrano in una
  finestra modale. Prima di aprire una sessione o di uscire con comandi non
  salvati, richiesta di conferma. **Save session** ha la casella "Includi il
  testo delle conversazioni" (spenta di default, `35` §3.9).

### 3.9 Lingua (A9, decisa il 2026-10-15)

- **Testi dell'interfaccia in inglese nel codice**, marcati con `tr()`.
- **Traduzione italiana nostra** con Qt Linguist (file `.ts` nel progetto,
  compilati in `.qm`).
- **Traduzioni di Qt** per i dialoghi standard (apertura file, conferme).
- **Lingua presa dal sistema** (`QLocale`), cambiabile nelle preferenze
  (inglese o italiano); il cambio vale al riavvio dell'app.
- **Numeri scientifici sempre con il punto decimale, in ogni lingua**:
  l'interfaccia non usa le regole numeriche della lingua per i valori
  scientifici (coordinate, misure, valori dei pixel, parametri), così i
  valori si copiano e si incollano senza ambiguità.

### 3.10 Preferenze essenziali

Finestra delle preferenze con cinque voci e, dal 2026-10-16, la sezione
**Assistant** (profili, modello, modalità rigorosa, limiti, prezzo
facoltativo: tabella del `44` §3.6; la chiave va **solo** nel Portachiavi
tramite il `31`, mai in `QSettings`); ogni modifica è un comando
`prefs.set` (classe `application`). Salvate nelle impostazioni dell'app di
macOS con `QSettings` (scelta minore 1), mai nella sessione. Nel codice
(sprint 7a del `44`, 2026-10-22) la sezione Assistant è un pulsante che
apre la finestra delle impostazioni del `44`; le sue impostazioni hanno
chiavi `assistant/…` controllate dal `44` (§3.10 del `44`) e passano dallo
stesso `prefs.set`.

| Preferenza | Valori | Effetto |
|---|---|---|
| Lingua | sistema, inglese, italiano | al riavvio (§3.9) |
| Limite della cache | byte, default 5 × 10⁹ (CA2 del `04`) | mostra spazio usato per modulo e totale (`usage`) e il pulsante "svuota" (`cache.clear`) |
| Sistema di coordinate mostrato | ICRS sessagesimale, ICRS decimale, galattico | valore iniziale di `view.set_coordinate_display` |
| Survey HiPS predefinito | identificativo HiPS; default `CDS/P/DSS2/color` (D12-3) | survey attivato all'avvio con `hips.set_survey` |
| Aspetto | sistema (default), scuro, chiaro, notte rossa | §3.11; cambia subito, senza riavvio |

### 3.11 Linee guida visive

Decisione del proprietario del 2026-10-15. **Valgono per 40, 41, 42 e per
tutte le interfacce future** (43, 44, 45 e successive): un modulo di
interfaccia che se ne discosta lo dichiara nel suo §13 come decisione
aperta.

- **Aspetto generale:** moderno e pulito, coerente con macOS (controlli
  nativi di Qt con lo stile di macOS, finestra con barra degli strumenti
  sottile unita alla barra del titolo, menu nella barra dei menu di
  sistema). **Nessun valore, colore, icona o stile preso da Aladin**
  (regola d'oro n. 8).
- **Temi:**
  - l'aspetto **segue la modalità chiaro/scuro del sistema** (preferenza
    "Aspetto" = sistema, default); il **tema scuro è quello di
    riferimento**: è il tema progettato per primo, mostrato nei mockup e
    usato quando il sistema non dichiara una preferenza; il tema chiaro ne
    è la versione con gli stessi elementi;
  - **modalità notte rossa** per l'osservazione al telescopio, scelta
    dall'utente (menu View o preferenza "Aspetto"): fondo nero, testi,
    linee, icone e accento solo in toni di rosso a bassa luminosità, nessun
    bianco né blu; anche il cielo si disegna in rosso (luminosità del piano
    di presentazione portata su una scala di rossi: trasformazione di
    disegno del `41`, i valori non cambiano); i colori dei cataloghi
    diventano toni di rosso e i cataloghi si distinguono per forma del
    simbolo. È un comando `ui.set_appearance` (classe `application`).
- **Disposizione:** **il cielo al centro**, con il massimo dello spazio;
  **pannelli laterali e inferiori richiudibili** (Livelli a sinistra,
  spazio dell'IA a destra, Tabella, Comandi e Messaggi in basso); **barre
  sottili** (barra degli strumenti e barra di stato di una riga).
- **Carattere:** il **carattere di sistema** di macOS (nessun carattere
  incluso nell'app); cifre a larghezza fissa (tabulari) per coordinate e
  valori nelle barre e nelle tabelle, così le colonne restano allineate
  (supporto in Qt da verificare prima del codice); dimensioni del testo che
  seguono le impostazioni di accessibilità del sistema.
- **Colore:** **un solo colore di accento** per selezione, elementi attivi e
  pulsante predefinito (nel tema scuro e chiaro un blu; in modalità notte
  il rosso dell'accento); errori nel colore di errore del sistema. I
  **colori dei cataloghi** (tavolozza fissa del `41`, scelta minore 4) sono
  la tavolozza di **Okabe e Ito (2008)**, pubblicata per essere distinguibile
  anche da chi non vede alcuni colori; sono colori dei dati, non accenti.
- **Spaziature:** griglia regolare di **4 punti** (margini e distanze
  multipli di 4: 4, 8, 12, 16, 24), stesse altezze di riga in tutti i
  pannelli.
- **Icone:** da una sola raccolta con licenza libera. **Proposta: Lucide**
  (icone a linea in SVG, licenza ISC, permissiva; raccolta ampia e
  coerente, adatta alle barre sottili); alternative Phosphor (MIT) e Tabler
  Icons (MIT). **Licenza verificata il 2026-10-17** (pacchetto
  `lucide-static` 1.59.0: ISC, più MIT del progetto Feather per le icone
  derivate elencate nel file) e scritta in `THIRD_PARTY_LICENSES` con il
  testo integrale; icone copiate senza modifiche in `src/astrotwo/ui/icons/`
  con il file `LICENSE`. Le icone si disegnano con `QtSvg` di PySide6 e
  prendono il colore del tema (anche il rosso della modalità notte).
- **Numeri:** sempre con il punto decimale (§3.9) e con le cifre di DC3;
  coordinate scritte con la funzione del 10 (D41-2).
- **Mockup di riferimento:** `mdfiles/mockup/finestra-principale.html` (tema
  scuro) e `mdfiles/mockup/finestra-principale-notte.html` (modalità notte
  rossa): pagine HTML statiche con valori fittizi, solo immagine di
  riferimento, non codice dell'app.

## 4. Cosa NON fa

- Non calcola nulla: coordinate, valori, misure e testi vengono dai moduli
  attraverso il `05` (regola d'oro n. 1, `01` §3).
- Non disegna il cielo né gestisce i livelli (`41`), non mostra tabelle
  (`42`).
- Non riscrive i messaggi dei moduli: li mostra tradotti dal catalogo con i
  parametri così come sono, senza modificarne i valori (D40-3, §3.7.1).
- Non ha "annulla/ripeti" (A12): si riesegue la cronologia.
- Non contiene il pannello dell'assistente (è del `44`, che il 40 ospita)
  e non chiama l'IA.
- Non conserva chiavi API (regola d'oro n. 5).
- Non salva la sessione da sé: formato e riesecuzione sono del `05`.

## 5. Livello e dipendenze

- **Livello:** interfaccia (attraversa i livelli senza logica scientifica,
  `01` §3); nella v1 usa solo il livello 1.
- **Dipende da:** `05-comandi-sessione.md` (registro, cronologia,
  sessione), `04-cache.md` (uso e svuotamento della cache, tramite
  comandi), `10-core-coordinate-wcs.md` (campo "Vai a", tramite comandi),
  `12-core-hips.md` (collezioni e survey, tramite comandi),
  `13-core-cataloghi.md` e `14-core-protocolli-vo.md` (catalogo nel campo,
  tramite comandi), `41-ui-visualizzatore-cielo.md`,
  `42-ui-pannello-cataloghi.md`, `44-ui-pannello-ia.md` (pannello
  dell'assistente, dal 2026-10-16), `35-ia-assistente-chat.md` (comandi
  dell'IA nella coda); libreria PySide6.
- **Usato da:** `44-ui-pannello-ia.md` (area a destra, preferenze, pannello
  Comandi); in futuro `43`, `45` si agganciano a questa finestra.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | azioni dell'utente | menu, tastiera, campo "Vai a", preferenze | — | diventano comandi del `05` |
| in | risultati dei comandi | `CommandResult` del `05` | valori con unità, avvisi ed errori del modulo | dal thread di lavoro con i segnali di Qt |
| in | `ProgressReport` | struttura | passo n di m | barra di stato |
| out | comandi | `Command` del `05` | parametri tipizzati con unità | in coda |
| out | preferenze | impostazioni dell'app (`QSettings`) | chiave → valore | non nella sessione |
| out | file di sessione | JSON del `05` | `.astrotwo.json` | tramite il `05` |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole. File Python
`src/astrotwo/ui/main_window.py`; traduzioni in `src/astrotwo/ui/i18n/`
(`astrotwo_it.ts`, compilato in `.qm`); test in `tests/ui/test_main_window.py`.

- **`MainWindow`** — finestra, menu, pannelli agganciabili, area riservata
  al pannello IA; crea il registro e lo spazio di lavoro del `05`.
- **`CommandRunner`** — oggetto nel thread di lavoro: riceve i comandi in
  coda, li esegue con il `05`, emette i segnali `started`, `progress`,
  `finished` (risultato) e gestisce Annulla.
- **`StatusBar`** — coordinate e valore sotto il mouse, attività di rete,
  comando in corso con avanzamento e Annulla.
- **`HistoryPanel`** — cronologia con dettagli, Riesegui e Copia come JSON.
- **`MessagesPanel`** — errori e avvisi con codice, testo e numero del
  comando.
- **`GoToField`** — campo "Vai a".
- **`PreferencesDialog`** — le cinque preferenze di §3.10.
- **`load_translations(language)`** — carica la traduzione nostra e quella
  di Qt; senza file di traduzione resta l'inglese con un avviso.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| **PySide6** (Qt 6: QtWidgets, QtCore) | finestra, menu, pannelli, thread (`QThread`), segnali, `QSettings`, `QLocale`, `QTranslator` | decisione A1; **licenza LGPL-3 (binding e Qt), registrata il 2026-10-15 per A11 e per il `60`** (obblighi LGPL nel `.dmg`, come per WCSLIB); testo da verificare prima del codice e da aggiungere a `THIRD_PARTY_LICENSES` |
| Qt Linguist (`pyside6-lupdate`, `pyside6-lrelease`) | file di traduzione `.ts`/`.qm` | strumento standard di Qt (A9) |
| Traduzioni di Qt (`qtbase_it`) | dialoghi standard in italiano | distribuite con Qt |
| **pytest-qt** | test dell'interfaccia | decisione del proprietario del 2026-10-15; **licenza da verificare** e da aggiungere a `THIRD_PARTY_LICENSES` |
| PySide6 `QtSvg`; raccolta di icone **Lucide** (`lucide-static` 1.59.0, ISC; MIT di Feather per le icone derivate) | icone dell'interfaccia (§3.11) | linee guida visive del 2026-10-15; licenza verificata il 2026-10-17 e scritta in `THIRD_PARTY_LICENSES` |
| `QStyleHints.colorScheme` di Qt | modalità chiaro/scuro del sistema | segue il sistema senza codice proprio; disponibilità nella versione di PySide6 da verificare |

## 9. Regole e vincoli

- **L'interfaccia non calcola** e mostra solo valori e testi dei moduli.
- **Ogni azione passa dal `05`** (regola d'oro n. 6), con le classi di
  D05-1.
- **Il thread principale non resta mai fermo più di 100 ms** durante rete o
  calcoli (obiettivo del `41`, misurato con una sonda di latenza).
- **Finestra pronta in ≤ 3 s senza rete** (obiettivo del `41`, test `perf`).
- **Punto decimale** per tutti i numeri scientifici in ogni lingua (§3.9).
- **Cifre di visualizzazione:** DC3 (RA 0.01 s, Dec 0.1″, magnitudini 3
  decimali); il valore pieno resta copiabile (`02` §6).
- **Nessun segreto** in preferenze, cronologia, log o sessione.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Uscita con comandi in corso | conferma; annullamento e attesa del ritorno entro i timeout di rete | — |
| Sessione fermata dal `05` (file cambiato o mancante) | finestra modale con il messaggio del `05`; stato fino all'ultimo comando rieseguito | `SESSION_FILE_CHANGED`, `SESSION_FILE_MISSING` |
| File da aprire illeggibile | finestra modale con il messaggio del modulo | codice del modulo (es. dell'11) |
| Rete assente | errore del modulo nel pannello Messaggi; l'interfaccia resta usabile | `NET_TIMEOUT` (del modulo) |
| Cache non disponibile | avviso nel pannello Messaggi; si continua senza cache | `CACHE_UNAVAILABLE` |
| File di traduzione mancante | interfaccia in inglese, avviso | `UI_TRANSLATION_MISSING` |
| Preferenza con valore non valido (es. limite della cache negativo) | rifiuto, valore precedente | `PREFERENCE_INVALID` |
| Comando lungo annullato | voce "annullato" nella cronologia, stato invariato | `COMMAND_CANCELLED` |

### 10.1 Messaggi con codice e `params` (D40-3, sprint 8e, 2026-10-25)

I messaggi scritti direttamente dalla finestra nascono come **codice + `params`** (`ResultMessage(code, text, params)`,
`CommandError(..., params=...)`); il testo italiano resta invariato e il catalogo (§3.7.1) ha la voce di ognuno.
Un'eccezione di un modulo (con `code`, `message`, `params`) si mostra con **il suo codice e i suoi `params`**
(`exception_message` di `message_view`); un'eccezione senza codice diventa `UI_COMMAND_FAILED`. Le impostazioni
controllate dalla finestra e dal pannello dell'assistente sollevano `ValueProblem` (sottoclasse di `ValueError` con
`code`, `message` e `params`): il valore non valido è un messaggio annidato (`cause`) di `PREFERENCE_INVALID`.
`ext` = testo esterno (nome di file o di cartella, testo di una libreria).

| Codice | `reason` | Parametri |
|---|---|---|
| `PREFERENCE_INVALID` | `unknown_assistant_key`, `unknown_key` | `key`, `allowed` (list) |
| | `invalid_value` | `key`, `cause` (messaggio: `PREFERENCE_VALUE_INVALID`) |
| | `invalid_value_other` | `key`, `detail` (ext) |
| `PREFERENCE_VALUE_INVALID` | `choice` | `value`, `allowed` (list) |
| | `cache_not_integer`, `box_not_integer`, `int_not_integer`, `true_false` | `value` |
| | `cache_not_positive` | `value` (int) |
| | `box_range`, `int_range` | `value` (int), `low` (int), `high` (int) |
| | `survey_empty` | — |
| | `profiles_json`, `consents_json` | `detail` (ext) |
| | `profiles_object`, `consents_shape` | — |
| | `profile_fields` | `profile`, `allowed` (list) |
| | `profile_invalid` | `profile`, `cause` (messaggio: `AI_PROFILE_INVALID` del `30`) |
| | `profile_other` | `profile`, `error_type`, `detail` (ext) |
| | `profile_id` | `profile`, `id` |
| `UI_COMMAND_FAILED` | — | `error_type`, `detail` (ext) |
| `SESSION_SAVE_FAILED` | — | `error_type`, `detail` (ext) |
| `UI_TRANSLATION_MISSING` | `italian` | `path` (ext) |
| | `qt` | `folder` (ext) |
| `COMMAND_CANCELLED` (condiviso con 05) | `window_closed`, `replay` | — |
| `COMMAND_PARAMETER_INVALID` (condiviso con 05) | `choice` | `parameter`, `given`, `allowed` (list) |

## 11. Esposizione all'IA

Non applicabile: è interfaccia. L'IA userà i comandi del `05` attraverso il
`32`; questo modulo riserva solo lo spazio per il pannello `44`.

## 12. Test di accettazione

Con **pytest-qt** e piattaforma Qt `offscreen` (senza schermo), servizi
simulati, in `tests/ui/`.

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Menu → comandi | attivare ogni voce di menu di §3.3 con file e servizi simulati | ogni voce produce il comando atteso del `05` con i parametri attesi | ispezione della cronologia |
| T2 | Riesegui | rieseguire tre comandi selezionati | tre nuovi comandi in coda con nuovi numeri; stesso stato del registro | confronto dello spazio di lavoro |
| T3 | Interfaccia reattiva | servizio simulato che risponde dopo 5 s a `catalog.load_region` | sonda di latenza del thread principale sempre < 100 ms; barra di stato con avanzamento e Annulla | sonda con timer di Qt |
| T4 | Annulla | annullare il comando di T3 | esito `cancelled`, stato invariato, voce in cronologia | ispezione |
| T5 | Messaggi (D40-3) | comando che produce un errore del 10 e un avviso del 13, interfaccia in inglese poi in italiano | codice invariato; testo del catalogo nella lingua dell'interfaccia; valori dei parametri identici a quelli dei moduli (stringa per stringa); testo originale nei dettagli; finestra modale solo per un file illeggibile | confronto diretto |
| T18 | Catalogo completo (D40-3) | scansione del codice di **tutto** `src/astrotwo` (moduli 04, 05, 10–19, 30–35 e interfaccia 40–44) | ogni codice ha voce con `en` e `it`, stessi segnaposto nelle due lingue, parametri attesi dichiarati; il test **fallisce** per un codice o una ragione senza voce o con una lingua mancante; nessun codice nel catalogo senza uso (avviso) | test |
| T19 | Valori dei parametri (D40-3) | messaggio con numero, unità, nome e testo esterno, in `en` e `it` | i valori compaiono identici al parametro (nessun arrotondamento, punto decimale); testo esterno non tradotto | test |
| T20 | Lingua verso l'IA (D40-3) | interfaccia in italiano, comando in errore eseguito dall'assistente (provider simulato) | il modello riceve codice, parametri e testo **inglese**; il pannello (`44`) mostra l'italiano | ispezione del corpo |
| T6 | Traduzioni complete | `pyside6-lupdate` sul codice | nessuna stringa non tradotta nel file italiano; traduzione di Qt caricata | controllo del file `.ts` |
| T7 | Punto decimale | interfaccia in italiano con località `it_IT` | coordinate, valori e parametri mostrati con il punto decimale | lettura dei testi dei widget |
| T8 | Preferenze | cambiare le cinque preferenze, riavviare la finestra (impostazioni in cartella temporanea) | valori ritrovati; comandi `prefs.set` in cronologia di classe `application` | test |
| T9 | Sessione fermata | riaprire una sessione con un file cambiato | finestra modale con `SESSION_FILE_CHANGED` | test |
| T10 | Pannello IA | avvio con e senza profilo dell'assistente | area a destra con il pannello del `44`, richiudibile; voce Assistant attiva; senza profilo il pannello dice perché e tutti gli altri test di questa tabella passano | ispezione dei widget |
| T14 | Colonna "chi" | un comando da menu, uno dal mouse, uno dall'IA (provider simulato), Riesegui | colonna "Utente", "Utente", "IA", "Utente"; filtro per chi; dettaglio del comando IA con conversazione, turno, profilo, modello, conferma | ispezione della cronologia |
| T15 | Preferenze dell'assistente | modificare profilo, modalità rigorosa, limiti; scrivere una chiave | comandi `prefs.set` in cronologia; nessuna chiave in `QSettings` né in cronologia | ispezione |
| T11 | Vai a | nome noto (SIMBAD simulato), coordinate sessagesimali, testo non valido | vista centrata con fonte dichiarata; errore del 10 per il testo non valido | ispezione |
| T12 | Avvio (`perf`) | avvio senza rete sul Mac di riferimento | finestra pronta in ≤ 3 s | misura (marcatore `perf`, D41-4) |
| T13 | Aspetto | sistema in modalità scura e chiara (simulata); poi modalità notte | tema che segue il sistema; in modalità notte nessun colore dei widget con componente verde o blu sopra una soglia bassa dichiarata nel test; comando `ui.set_appearance` di classe `application` | lettura della tavolozza dei widget |

## 13. Decisioni aperte

Nessuna decisione dei Gruppi 1 e 2 aperta (dal 2026-10-15).

- **A9 — Lingua dell'interfaccia: DECISA il 2026-10-15 (decisione del
  proprietario).** Testi in inglese con `tr()`, traduzione italiana nostra
  con Qt Linguist, traduzioni di Qt per i dialoghi standard, lingua dal
  sistema cambiabile nelle preferenze, numeri scientifici sempre con il
  punto decimale in ogni lingua. Applicata in §3.9.
- **D40-1 — Lingua dei messaggi dei moduli: DECISA il 2026-10-15
  (decisione del proprietario).** Nella v1 si mostrano **codice e testo del
  modulo invariati**. Applicata in §3.7; **superata il 2026-10-24 da D40-3**.
- **D40-3 — Messaggi dei moduli in inglese e italiano: DECISA il
  2026-10-24 (decisione del proprietario; sprint 8 della v1).** Tutti i
  messaggi dei moduli (errori e avvisi con codice) si mostrano nella lingua
  dell'interfaccia; un'unica tabella codice → testo inglese/italiano con i
  parametri inseriti senza modificarne i valori; i moduli scientifici
  restituiscono codice e parametri; un test fallisce per un codice senza
  traduzione; l'IA riceve sempre l'inglese. Verifica del 2026-10-24: i
  moduli 10–19 oggi restituiscono codice + testo italiano già formattato
  (~613 punti, solo ~152 con `details`), non codice + parametri;
  **scelta del proprietario: modificare i moduli perché restituiscano
  `params`** (testo originale conservato). Applicata in §3.7, §3.7.1,
  §3.7.2, §12 (T5, T18–T20); il codice si scrive dopo l'approvazione dei
  `.md` modificati, un modulo per sprint (8b–8d).
  **CHIUSA il 2026-10-25 (sprint 8e):** applicata a tutti i moduli — `04`,
  `05`, 10–19 (sprint 8b–8d), `30`–`35`, `40`, `41`, `42`, `44` (sprint 8e) —
  e controllata da T18 su tutto `src/astrotwo`.
- **D40-5 — Posizione del catalogo dei messaggi: DECISA il 2026-10-24
  (decisione del proprietario, come raccomandato).** Modulo neutro
  `src/astrotwo/messages_catalog.py`, usato da `ui/` e `ai/`; i moduli
  10–19 non lo importano. Applicata in §3.7.1.
- **D40-6 — Varianti per ragione nel catalogo: DECISA il 2026-10-24
  (decisione del proprietario, come raccomandato; sprint 8b).** Le voci del
  catalogo possono avere sotto-voci scelte dal parametro `reason`
  (identificatore stabile), per i codici sollevati per ragioni diverse;
  nessun codice cambia. Applicata in §3.7.1.
- **D40-7 — Messaggi annidati nel catalogo: DECISA il 2026-10-24
  (decisione del proprietario: opzione (b), sprint 8c-bis).** Tipo di
  parametro `message` (`code`, `params`, `text` di un altro messaggio di
  AstroTwo), reso in modo ricorsivo nella lingua dell'interfaccia e in
  inglese verso l'IA, profondità massima 3; il testo di terzi (eccezioni di
  librerie, risposte dei servizi, motivi `ASTRORES`) resta parametro
  `external`, non tradotto e marcato come esterno anche verso l'IA. Applicata
  in §3.7.1; 10, 11, 12 aggiornati; 14, 16, 19 la useranno alla conversione.
- **D40-2 — Avvio tramite URL (H18): RIMANDATA il 2026-10-15** (decisione
  del proprietario, come proposto): l'equivalente in AstroTwo (app `.dmg`,
  senza Java WebStart) si definisce nella versione successiva del 40.
  Gruppo 3.
- **Scelte minori: CONFERMATE dal proprietario il 2026-10-15:** (1) preferenze in `QSettings` (file
  delle preferenze di macOS); (2) cambio di lingua al riavvio; (3) voci e
  scorciatoie dei menu di §3.3; (4) filtro della cronologia con la sola
  classe `session` di default; (5) catalogo nel campo con centro e raggio
  della vista (`ViewGeometry` del 10).
- **Proposta della fase 1 sull'IA, approvata dal proprietario il
  2026-10-16:** pannello del `44` nella disposizione, voce Assistant attiva,
  colonna "chi" nella cronologia, sezione Assistant nelle preferenze,
  comandi dell'IA nella stessa coda, casella per il testo delle
  conversazioni in Save session; applicata in §3.1, §3.2, §3.3, §3.6, §3.8,
  §3.10, §12 (T10, T14, T15).
- **Licenze verificate il 2026-10-16:** si usa **`pyside6-essentials`**
  6.12.0 (con `shiboken6`), che contiene QtWidgets, QtOpenGL,
  QtOpenGLWidgets e QtSvg, invece del pacchetto `pyside6` completo (che
  aggiunge Addons, WebEngine e PDF, non usati); licenza
  `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`, usata come LGPL-3.0; la
  ruota non contiene i testi: LGPL-3.0 e GPL-3.0 presi dal sorgente
  ufficiale di PySide6 6.12.0 (`scripts/licenses/`) e scritti in
  `THIRD_PARTY_LICENSES`; avvisi delle componenti incluse nelle librerie Qt
  da completare con il `60`. **pytest-qt** 4.5.0 MIT, nella sezione degli
  strumenti di sviluppo di `THIRD_PARTY_LICENSES`.
- **Verifiche prima del codice, fatte il 2026-10-17 (parte 3 della v1):**
  `QStyleHints.colorScheme` c'è in PySide6 6.12.0 (usato per seguire il
  sistema, T13); cifre tabulari con la funzione OpenType `tnum` di
  `QFont.setFeature` (impostazione verificata dai test; la resa a schermo
  con il carattere di sistema si controlla a occhio sul Mac). Licenza della
  raccolta di icone **verificata il 2026-10-17** con la parte 3b (§3.11, §8).
- **Codice della parte 3 (2026-10-17):** T1–T14 in `tests/ui/`; **T15**
  (preferenze dell'assistente) si scrive con il `44`, che porta la sezione
  Assistant delle preferenze. Le conferme dei comandi chiesti dall'IA
  (indicatore `confirm` del `05`, schede del `44`) arrivano con 32/35/44;
  i comandi chiesti dall'utente non chiedono conferma (l'azione dell'utente
  è la conferma), salvo uscita con comandi in corso o non salvati e
  apertura di una sessione sopra lavoro non salvato (§3.8).
- **Parte 3b (2026-10-17), correzioni dell'aspetto chieste dal proprietario
  dopo la prova della finestra (nessuna funzione nuova, comandi invariati):**
  foglio di stile dai colori dei mockup (barre, pannelli, tabelle con righe di
  24 punti senza griglia, schede dei pannelli in basso in alto, barra di
  stato), margini sulla griglia di 4 punti, icone Lucide nel colore del tema,
  intestazioni dei pannelli come nel mockup (titolo piccolo in maiuscolo,
  pulsanti per staccare e chiudere; i pannelli a schede usano le schede),
  stati vuoti con icona e testo che dice cosa arriverà (cielo 41, Livelli
  41, Tabella 42, Assistente 44, Comandi e Messaggi senza righe). Nella
  barra degli strumenti, come nel mockup, pulsanti per azioni già nei menu
  di §3.3 (Open image, pannello Layers, griglia, Distance, Simbad pointer,
  **Night mode**, Assistant). **Differenze dal mockup lasciate:** la scritta
  del survey nella barra ("DSS2 colore · TAN · campo") arriva con il 41 che
  dà quei valori; nella colonna "chi" restano "Utente/IA/Sessione" di §3.6
  (il mockup mostra "menu/mouse").
- **Sprint 4a del 41 (2026-10-17):** il segnaposto del cielo è sostituito
  dal visualizzatore del 41; la scritta del survey nella barra
  ("titolo · proiezione · campo") ora c'è; la **barra di stato ha altezza
  fissa di 26 px** (come il mockup), così mostrare Annulla e l'avanzamento
  non cambia la dimensione del cielo (che a ogni nuova dimensione registra
  la nuova finestra).
- **D40-4 — Scorciatoia della modalità notte: DECISA il 2026-10-17
  (decisione del proprietario): ⌃⌘N** per View → Night mode (stessa
  famiglia di ⌃⌘F schermo intero e ⌃⌘A assistente; non usata da altre voci
  né dalle scorciatoie standard di macOS per le app). La voce resta anche
  nel menu View e nel pulsante con la luna nella barra degli strumenti.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-15 | Claude Code | Creazione del file (stato: bozza) dalla proposta della fase 1 approvata dal proprietario il 2026-10-15: perimetro v1 (menu, barra di stato, campo "Vai a", preferenze essenziali, apertura di file e sessioni, pannelli Comandi e Messaggi, schermo intero, spazio per il 44), coda dei comandi in un thread di lavoro con segnali di Qt, avanzamento e Annulla per ogni comando lungo, A9 decisa (inglese con `tr()`, italiano nostro con Qt Linguist, traduzioni di Qt, punto decimale sempre). Nuove decisioni D40-1, D40-2. |
| 2026-10-15 | Claude Code | **Decisioni del proprietario del 2026-10-15:** D40-1 decisa (v1: codice + testo del modulo invariato); nuova **D40-3** (Gruppo 3: messaggi dei moduli in inglese con traduzione); D40-2 rimandata; scelte minori confermate; **nuova §3.11 "Linee guida visive"** (valide per tutte le interfacce: macOS, tema che segue il sistema con lo scuro di riferimento, modalità notte rossa, cielo al centro con pannelli richiudibili e barre sottili, carattere di sistema, un solo accento, spaziature di 4 punti, icone Lucide proposte con licenza da verificare, colori dei cataloghi di Okabe e Ito, nulla da Aladin); preferenza "Aspetto" e voce Night mode; PySide6/Qt LGPL-3 registrata per A11 e per il 60; mockup in `mdfiles/mockup/`; test T13. Nessuna decisione dei Gruppi 1 e 2 resta aperta. |
| 2026-10-16 | Claude Code | **Proposta della fase 1 sull'IA approvata dal proprietario il 2026-10-16** (autorizzazione a modificare la bozza come proposto): il pannello dell'assistente (`44`) entra nella v1 nell'area a destra, voce Assistant attiva (⌃⌘A); colonna "chi" (da `requested_by` del `05`) e dettagli dei comandi dell'IA nel pannello Comandi; sezione Assistant nelle preferenze (chiave solo nel Portachiavi, `31`); comandi dell'IA nella stessa coda con lo stesso `CancelToken`; casella "Includi il testo delle conversazioni" in Save session; test T10 aggiornato, T14 e T15 nuovi. |
| 2026-10-16 | Claude Code | **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-16. |
| 2026-10-16 | Claude Code | Verifiche del 2026-10-16: licenze di PySide6 (`pyside6-essentials`, LGPL-3.0 con i testi dal sorgente ufficiale) e di pytest-qt (MIT) verificate e in `THIRD_PARTY_LICENSES`. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **Codice della parte 3 della v1** ("FASE: CODICE – interfaccia v1"): `src/astrotwo/ui/main_window.py` (finestra, menu, barra di stato, "Vai a", pannelli Comandi e Messaggi, coda dei comandi in un `QThread` con avanzamento e Annulla, preferenze, aspetto scuro/chiaro/sistema/notte rossa, lingua inglese/italiano con punto decimale sempre), traduzione `src/astrotwo/ui/i18n/astrotwo_it.ts`/`.qm`, avvio `uv run astrotwo`, test `tests/ui/test_main_window.py` (T1–T14, T12 con marcatore `perf`). Verifiche di §13 fatte (colorScheme, cifre tabulari); icone ancora da verificare quando si aggiungono. Visualizzatore (41), tabella (42) e assistente (44) restano spazi riservati fino alle loro parti. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **Parte 3b del codice della v1** (correzioni dell'aspetto dopo la prova del proprietario; nessuna funzione nuova, comandi invariati): foglio di stile dai mockup, icone Lucide (licenza verificata: ISC più MIT di Feather, in `THIRD_PARTY_LICENSES`; §3.11, §8), intestazioni dei pannelli, stati vuoti dei segnaposto, pulsanti della barra per azioni già nei menu (anche Night mode); test T13 esteso al foglio di stile e alle icone in modalità notte, nuovo test delle linee guida visive. **Aperta D40-4** (scorciatoia della modalità notte, Gruppo 3, raccomandazione ⌃⌘N). Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **D40-4 decisa dal proprietario: ⌃⌘N** per View → Night mode (§3.3, §13); codice e test T13 aggiornati. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | Sprint 4a del 41: visualizzatore al posto del segnaposto, scritta del survey nella barra, barra di stato ad altezza fissa (26 px, §13). Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **Parte 4a-fix (seconda parte), decisioni del proprietario dello stesso giorno:** pulsanti **+** e **−** sul cielo e voci Zoom in/out del menu View (⌘+, ⌘=, ⌘−; ×2 e ÷2 come un gesto); dopo un "Vai a" riuscito con campo > 1,25° la vista va a circa 1° con un `view.set_zoom` registrato (`05` invariato). Specifiche aggiornate prima: `41` §3.4 e `40` (menu View, §3.4). Icone Lucide `plus` e `minus` (ISC), traduzioni italiane, 2 test nuovi. |
| 2026-10-20 | Claude Code | **Sprint 4c del 41:** menu Vista con "Show north and east" e "Show scale bar" (`view.set_overlays`, 05); 4 testi nuovi tradotti nel file `.ts`/`.qm`. |
| 2026-10-21 | Claude Code | **Parte 5, sprint 5a (42):** il pannello Tabella contiene il pannello del 42 (schede dei cataloghi); senza cataloghi resta lo stato vuoto, con il testo aggiornato ("Open a catalog file or load a catalog region…"); dopo l'apertura di una sessione anche il pannello dei livelli e la tabella si ricostruiscono dallo stato; 15 testi nuovi tradotti nel `.ts`/`.qm`. Stato `approvato` invariato. |
| 2026-10-22 | Claude Code | **Parte 6, sprint 6c (35):** collegamento dell'assistente alla coda (§3.8): `assistant_executor()`, `submit_command` con il `CancelToken` della risposta, attese chiuse all'uscita; test in `tests/ui/test_assistant_queue.py`. Nessun cambiamento di comportamento per l'utente. Stato `approvato` invariato. |
| 2026-10-22 | Claude Code | **Sprint 7a del `44`:** l'area a destra ospita il pannello dell'assistente (`AiPanel`, larghezza iniziale 400 pt) al posto dello stato vuoto; preferenze Assistant come pulsante verso le impostazioni del `44` (§3.10), chiavi `assistant/…` accettate da `prefs.set`; Save session con il testo delle conversazioni del `35` quando la casella è attiva; uscita con una risposta in corso: stessa conferma dei comandi in corso, poi Stop; `HistoryPanel.select_number` per il clic sulle schede del `44`. T6 controlla anche le traduzioni di `ui/ai_panel.py`. Stato `approvato` invariato. |
| 2026-10-23 | Claude Code | **Sprint 4g del 41:** `ui.set_tool` attiva davvero lo strumento nel visualizzatore (`SkyViewer.set_tool`); tre impostazioni nuove controllate da `prefs.set` e ricordate in `QSettings` per le opzioni della distanza (`tools/distance_unit`, `tools/distance_snap`, `tools/distance_box_size`, §3.10); 12 testi nuovi tradotti nel `.ts`/`.qm`. Stato `approvato` invariato. |
| 2026-10-25 | Claude Code | **Sprint 8f (rifinitura):** parametro di contesto riservato `layer_context` (§3.7.1) per i messaggi che nascono su un livello; nome del livello testo esterno. Stato `approvato` invariato. |
| 2026-10-24 | Claude Code | **D40-3 decisa (sprint 8, solo specifiche):** messaggi dei moduli nella lingua dell'interfaccia (inglese/italiano) da un catalogo codice → testo con parametri (nuove §3.7.1 e §3.7.2), verso l'IA sempre inglese; i moduli 10–19 e il `05` passano da codice + testo a codice + `params` (testo originale conservato, vedi `05`); D40-1 superata; test T5 riscritto, nuovi T18–T20; aperta D40-5 (posizione del catalogo, raccomandato un modulo neutro). Nessun codice scritto. |
| 2026-10-24 | Claude Code | **Sprint 8b (codice):** approvati i `.md` dello sprint 8; D40-5 decisa (catalogo in `src/astrotwo/messages_catalog.py`); nuova e decisa D40-6 (varianti per `reason`); §3.7.1 aggiornata e passaggio graduale di T18 (solo moduli convertiti). |
| 2026-10-24 | Claude Code | **Sprint 8c (codice):** modulo 12 convertito a codice + `params` (voci del catalogo e test T18 aggiornati, `12` §10); aperta D40-7 (messaggi annidati, Gruppo 3). Nessun comportamento cambia. |
| 2026-10-24 | Claude Code | **Sprint 8c-bis:** D40-7 decisa dal proprietario (opzione (b)): tipo di parametro `message` ricorsivo con profondità massima 3, testo di terzi sempre `external` (§3.7.1). Nessun comportamento visibile cambia. |
| 2026-10-24 | Claude Code | **Sprint 8c-bis (13):** §3.7.1 — tipo di parametro `messages` (elenco di messaggi annidati), graffe raddoppiate nel testo, elenco vuoto mostrato come "—" (necessari ai messaggi del 13). |
| 2026-10-24 | Claude Code | **Sprint 8d (codice):** moduli 14, 16, 19, 15, 17 e 18 convertiti a codice + `params`; T18 comprende tutti i moduli 10–19 e gli errori di 14, 16 e 19 incorporati da 12 e 13 sono messaggi annidati (§3.7.1 aggiornata). Restano il `05` e i moduli dell'interfaccia e dell'IA (sprint 8e). Nessun comportamento visibile cambia. |
| 2026-10-25 | Claude Code | **Sprint 8e, ultimo della traduzione (D40-3):** nuova §10.1 con la tabella dei messaggi scritti dalla finestra (`PREFERENCE_INVALID`, `PREFERENCE_VALUE_INVALID` con `ValueProblem`, `UI_COMMAND_FAILED`, `SESSION_SAVE_FAILED`, `UI_TRANSLATION_MISSING`) scritta prima del codice; §3.7.1 e T18 estese a tutto `src/astrotwo`; **D40-3 chiusa**. Test `tests/ui/test_messages_ui.py`. Stato `approvato` invariato. |
