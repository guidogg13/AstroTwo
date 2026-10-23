# 44-ui-pannello-ia.md — pannello dell'assistente IA

**Stato:** approvato

## 2. Scopo

Dare all'utente, a destra della finestra principale, un pannello per
parlare con l'assistente in cui ogni comando eseguito, ogni conferma, ogni
numero verificato e ogni dato inviato al provider sia visibile, senza
togliere nulla al resto dell'app quando l'assistente non è disponibile.

## 3. Cosa fa

Origine: proposta della fase 1 sull'IA nella v1, **approvata dal
proprietario il 2026-10-16** (punto 7: pannello come proposto); linee guida
visive del `40` §3.11; mockup `mdfiles/mockup/finestra-principale-ia.html`.

### 3.1 Posizione

- Nell'**area agganciabile a destra** già riservata dal `40` (§3.2 del
  `40`), larga **380–420 pt** (default 400 pt, scelta minore 1),
  richiudibile; pulsante nella barra degli strumenti e voce di menu
  **Assistant** (⌃⌘A, scelta minore 2) attiva.
- Aperto o chiuso: stato salvato con la geometria della finestra
  (impostazioni dell'app, non sessione).

### 3.2 Contenuto

Dall'alto in basso:

1. **Intestazione:** nome del profilo, provider e modello; **lucchetto**
   dello stato della chiave (presente sì/no, dal `31` `has_key`); simbolo
   **"locale · nulla esce dal Mac"** per gli endpoint locali (`30` §3.1);
   pulsanti Nuova conversazione e Impostazioni.
2. **Riga fissa sulla privacy** (una riga, con collegamento al dettaglio):
   "Al provider vanno il testo e i risultati dei comandi; mai file, pixel,
   chiavi o cartelle."
3. **Messaggi** (area che scorre):
   - messaggi dell'utente e risposte dell'assistente (Markdown semplice:
     paragrafi, elenchi, tabelle, codice; nessun HTML, nessuna immagine,
     **collegamenti mostrati come testo**, aperti solo con un clic
     dell'utente);
   - per ogni comando chiesto dall'IA una **scheda del comando**: numero
     `#n`, nome, parametri con unità, esito, risultato in breve, fonte
     (modulo · libreria; origine e data se dalla rete o dalla cache);
     un clic apre la riga corrispondente nel pannello Comandi del `40`;
   - **schede di conferma** (§3.3);
   - sotto ogni risposta: **riepilogo della verifica** del `34` ("✓ 3
     numeri su 3 verificati" o "⚠ …"), **token** della risposta (e costo se
     l'utente ha inserito un prezzo, con la nota), eventuali note dei
     limiti ("limite di 10 comandi raggiunto", "risposta interrotta"),
     collegamento **"Cosa è stato inviato"** (§3.5).
4. **Campo di testo** (più righe; Invio invia, ⇧Invio va a capo) e
   pulsante **Invia**, che durante una risposta diventa **Stop**.

### 3.3 Schede di conferma

- Mostrano: nome del comando, **parametri con unità**, righe massime (per
  i cataloghi), motivo della conferma (rete, comando lungo, modifica di un
  livello, oppure "chiesto dopo la lettura di testo esterno (fonte)").
- Pulsanti: **Conferma** (predefinito), **Annulla**, **"Conferma per
  questa conversazione"** (vale solo per quel comando e quella
  conversazione; **assente** quando il motivo è un testo esterno, `32`
  §3.6).
- Una conferma in attesa non blocca il resto dell'app: si può continuare a
  usare la vista; la risposta riprende quando l'utente sceglie.

### 3.4 Numeri verificati ed evidenziati

- Durante lo streaming il testo è grigio chiaro ("in verifica").
- A fine risposta, secondo il rapporto del `34`:
  - numeri `verified`: sottolineatura sottile nel colore d'accento; al
    passaggio del mouse, **valore pieno con unità**, comando `#n`, modulo
    · libreria;
  - `user_input`, `command_parameter`, `external_text`: sottolineatura
    tratteggiata con la nota del `34`;
  - `not_verified` e `ambiguous`: **evidenziati** con il colore d'avviso
    del sistema e la nota "non viene da un comando" (o "formato ambiguo");
  - `ACTION_WITHOUT_CONFIRMATION`: riga rossa nel riepilogo.
- In modalità notte rossa le evidenziazioni usano solo toni di rosso e si
  distinguono per stile della linea (continua, tratteggiata, sfondo).

### 3.5 "Cosa è stato inviato"

Finestra con, per ogni richiesta della risposta, il **JSON esatto**
(`RequestRecord` del `30`: corpo senza intestazioni né chiave), indirizzo e
ora UTC; pulsante **Copia**. In sola lettura.

### 3.6 Impostazioni dell'assistente

Finestra (aperta dal pannello e dalla sezione **Assistant** delle
preferenze del `40`); ogni modifica è un comando `prefs.set` di classe
`application` (**mai la chiave**):

| Voce | Valori | Note |
|---|---|---|
| Profili | elenco; aggiungi, modifica, rimuovi | campi del `30` §3.1 |
| Provider | menu a comparsa: i profili predefiniti del `30` §3.1.1 (Anthropic, OpenAI, Google Gemini, Mistral AI, DeepSeek, xAI, Groq, OpenRouter, Ollama, LM Studio) e, in fondo, "Altro endpoint compatibile OpenAI…" | dal 2026-10-17 (decisione del proprietario); accanto a ogni provider che non è `verified` un **contrassegno** con il suo stato ("chiamata di strumenti dichiarata dal provider, non provata da AstroTwo" per `documented`; "chiamata di strumenti non dichiarata: potrebbe non funzionare" per `unverified`) e la fonte del `30` nel suggerimento |
| Indirizzo dell'endpoint | URL | riempito dal profilo predefinito e modificabile; obbligatorio per "Altro endpoint compatibile OpenAI"; `https` per gli endpoint remoti |
| Modello | elenco da `list_models` (pulsante Aggiorna) o testo | nessun modello predefinito |
| Chiave API | campo **mascherato**; Salva, Cancella | tramite il `31`; il testo non si copia e si svuota dopo il salvataggio; nessun comando registrato |
| Prova il modello | pulsante | `probe_tools` del `30`; mostra esito e token |
| Massimo di token in uscita | intero | default 4096 |
| Modalità rigorosa | sì/no, default no | `34` §3.6 |
| Limiti | chiamate per risposta (10), minuti per risposta (5) | `35` §3.3 |
| Prezzo per milione di token | facoltativo, ingresso e uscita, valuta | `35` §3.6 |

### 3.7 Consenso al primo uso

Al primo messaggio con un profilo senza consenso: finestra modale con
l'elenco di cosa esce e cosa no (`35` §3.8), indirizzo del provider e
pulsanti **Accetto** / **Non ora**. Senza consenso il pannello mostra il
motivo e non invia nulla.

### 3.8 Assistente non disponibile

Al posto del campo di testo: "L'assistente non è disponibile: <motivo>.
Il resto di AstroTwo funziona normalmente." con il pulsante che porta
all'impostazione che manca (profilo, chiave, consenso). Motivi dal `35`
§3.7. La finestra principale, la vista e i comandi non cambiano (regola
d'oro n. 7).

### 3.9 Aspetto

Linee guida visive del `40` §3.11: carattere di sistema, cifre tabulari
nelle schede, un solo accento, spaziature di 4 punti, icone della raccolta
scelta nel `40`, temi scuro/chiaro e **modalità notte rossa**; i messaggi
dell'utente e dell'assistente si distinguono per allineamento e sfondo
leggero, non per colori forti.

### 3.10 Precisazioni del codice (sprint 7a, 2026-10-22)

Come il codice applica §3.1–§3.9 dove la specifica non scende nel
dettaglio (scelte minori **confermate dal proprietario il 2026-10-23**, §13):

1. **Impostazioni in `QSettings`** (sezione `assistant/`, scritte solo con
   `prefs.set`): `assistant/profiles` (oggetto JSON `{id: profilo}` con i
   campi del `30` §3.1 e il prezzo facoltativo `price_input`,
   `price_output`, `currency`; un profilo per endpoint, scelta minore 4 del
   `30`), `assistant/active` (identificativo del profilo in uso),
   `assistant/strict` (`true`/`false`), `assistant/max_calls` (1–100),
   `assistant/max_minutes` (1–60), `assistant/consents` (`{id: {version,
   given_at}}`). **Modalità rigorosa e limiti valgono per tutti i
   profili; il prezzo è del profilo** (`35` §3.6: "nel profilo"). Un
   indirizzo remoto in `http` si rifiuta già nel controllo di `prefs.set`
   (`AI_INSECURE_ENDPOINT`). La chiave non è mai tra queste impostazioni.
2. **Consenso:** "Accetto" scrive `assistant/consents` con un `prefs.set`
   (classe `application`, come ogni impostazione: resta nella cronologia
   dell'app, regola d'oro n. 6); il messaggio scritto prima del consenso
   parte quando il comando è applicato; "Non ora" lo scarta e il pannello
   mostra il motivo con il pulsante "Dai il consenso…".
3. **Messaggi dell'utente** mostrati come testo semplice (non Markdown):
   si vede esattamente ciò che è stato scritto.
4. **Collegamenti e immagini** (Markdown di Qt con `MarkdownDialectGitHub`
   e `MarkdownNoHTML`): il testo del collegamento è seguito
   dall'indirizzo **scritto per intero** (`testo <indirizzo>`), così nessun
   indirizzo è nascosto; un clic apre solo `http`/`https` nel browser del
   sistema (altri schemi ignorati); un'immagine diventa il testo
   "[immagine non mostrata: indirizzo]" e non si carica. Al cambio di tema
   le risposte si riconvertono (Qt scrive il colore dei collegamenti nel
   documento: in modalità notte solo rossi).
5. **Scheda del comando:** risultato in breve = i primi 4 valori `nome =
   valore` scritti per intero (unità accanto alle quantità `{value,
   unit}`), tutti i valori nel suggerimento; fonte = funzioni dei moduli
   dichiarate dal registro del `05` ("modulo 17 angular_distance") più
   origine, data e "dalla cache" dalla provenienza del risultato. Il
   registro del `05` non dichiara la libreria: la scheda mostra modulo e
   funzione (la libreria resta nel `.md` del modulo). Chiamate non
   eseguite (validazione, limite, non confermate): scheda senza `#n` con
   codice e testo dell'errore.
6. **Testi sotto la risposta tradotti dal 44** (`35` §3.11 punto 12): il
   riepilogo della verifica si ricompone dai conteggi del rapporto del
   `34` (stessa regola del §3.5 del `34`), le note dei limiti dai codici
   (`AI_TOOL_LIMIT`, `AI_TIME_LIMIT`, `AI_CANCELLED`), i token con "token
   non dichiarati dal provider"; token della risposta e della
   conversazione; costo solo con il prezzo dell'utente, valore pieno con
   la nota. Errori del provider: codice e testo del `30` invariati (D40-1).
7. **Rigenerazione** (modalità rigorosa): la prima risposta resta visibile
   in grigio con la nota "il testo sopra è sostituito da quello sotto".
8. **Uscita con una risposta in corso:** stessa conferma dei comandi in
   corso del `40`, poi Stop.
9. **Icone:** 8 icone in più della stessa raccolta Lucide (`lock`,
   `lock-open`, `shield`, `send`, `square`, `settings`,
   `message-square-plus`, `laptop`), copiate senza modifiche dallo stesso
   pacchetto `lucide-static` 1.59.0 verificato il 2026-10-17 (SHA-1
   identico), licenza già in `THIRD_PARTY_LICENSES`.
10. **Preferenze del `40`:** la sezione Assistant è un pulsante che apre la
    stessa finestra delle impostazioni del pannello.
11. **Elenco dei modelli e "Prova il modello"** girano in un thread
    (`QThreadPool`), non sono comandi (non modificano nulla) e mostrano
    esito, avvisi e token nella finestra.
12. **Campo della chiave:** mascherato, senza menu contestuale (nessuna
    copia), svuotato con `setText("")` dopo Salva (anche la cronologia di
    annulla del campo); la stringa Python letta dal campo non si può
    cancellare dalla memoria (testo immutabile) e si lascia al garbage
    collector, senza altre copie.

### 3.11 Precisazioni del codice (sprint 7b, 2026-10-23)

Come il codice applica §3.4 e §10 dove la specifica non scende nel
dettaglio (scelte minori **da confermare** in §13):

1. **Dal testo della risposta al documento:** il rapporto del `34` dà le
   posizioni nel testo Markdown (NFC). Prima della conversione il pannello
   mette attorno a ogni numero non `excluded` dei **segni invisibili**
   (caratteri dell'area privata di Unicode, U+E000–U+E019, con il numero
   d'ordine del numero); dopo la conversione li cerca nel documento, applica
   lo stile a ciò che sta fra i segni e li toglie, anche dagli indirizzi dei
   collegamenti. Così ogni numero si ritrova anche dopo elenchi, tabelle,
   grassetti e codice. Un numero che sparisce nella conversione (testo
   alternativo di un'immagine, titolo di un collegamento) non è mostrato e
   quindi non si evidenzia; il riepilogo lo conta lo stesso.
2. **Più blocchi di testo:** il testo verificato è l'unione dei blocchi
   mostrati tra le schede dei comandi; le posizioni si dividono fra i
   blocchi. Se l'unione non coincide con il testo del rapporto (caso solo
   teorico della normalizzazione NFC al confine fra due blocchi) il testo
   verificato si mostra intero nel primo blocco, così nessun numero resta
   senza stile. La prima risposta della rigenerazione (§3.10 punto 7) si
   evidenzia con il suo rapporto.
3. **Stili** (colori del tema del `40`): `verified` e
   `verified_other_command` sottolineatura continua nel colore d'accento
   (`focus`); `user_input`, `command_parameter`, `external_text`
   sottolineatura **tratteggiata** nel colore del testo secondario;
   `not_verified` e `ambiguous` **sfondo** nel colore d'errore del tema
   (trasparente al 30 %) con sottolineatura ondulata; `excluded` nessuno
   stile. In modalità notte gli stessi stili con i colori rossi del tema.
4. **Suggerimento** (al passaggio del mouse sul numero), tradotto dal `44`
   (gli stati e le note del `34` non si mostrano in italiano fisso):
   `verified`: "Verificato: <valore pieno> <unità> · comando #n · <funzioni
   del modulo>"; `verified_other_command`: lo stesso con "con un altro
   comando"; `command_parameter`: "Parametro del comando #n: <valore>";
   `user_input`: "Dal tuo messaggio"; `external_text`: "Da testo esterno,
   non calcolato (<fonte>)"; `not_verified`: "Non viene da un comando";
   `ambiguous`: "Formato ambiguo". Note in più del `34`: "unità non
   riconosciuta", "comando inesistente: #n". Valore pieno = valore del
   risultato completo del `05` (`repr` di Python) con la sua unità; funzioni
   del modulo come nella scheda del comando (§3.10 punto 5).
5. **Copiabile** (`02` §6, §9 qui): clic destro su un numero → "Copia il
   valore pieno" (valore e unità) e "Copia la nota"; il resto del menu è
   quello del testo in sola lettura.
6. **Errori del provider** (§10): codice e testo del `30` in rosso sotto la
   risposta, con il testo arrivato prima dell'errore verificato come gli
   altri; `AI_CONTEXT_TOO_LONG` con il pulsante "Nuova conversazione".
7. **Sonda di latenza (T14):** un temporizzatore di 10 ms sul thread
   principale durante una risposta che arriva lentamente e un comando
   lungo confermato; nessun intervallo oltre 100 ms (`41` P). Il testo in
   arrivo si ridisegna al più ogni 50 ms.

## 4. Cosa NON fa

- Non parla con il provider e non esegue comandi da sé (`35`, `32`, coda
  del `40`).
- Non verifica i numeri (`34`) e non calcola nulla: mostra testi e numeri
  dei moduli e del `34`.
- Non conserva chiavi (`31`) e non le mostra mai.
- Non apre collegamenti da solo; non mostra HTML né immagini delle
  risposte.
- Non accetta voce o allegati (fuori dalla v1).
- Non salva la conversazione (`35` §3.9, tramite il salvataggio della
  sessione del `40`).

## 5. Livello e dipendenze

- **Livello:** interfaccia; usa il livello 3 (30, 31, 32, 34, 35) e, tramite
  i comandi, il livello 1.
- **Dipende da:** `35-ia-assistente-chat.md`, `34-ia-verifica-risultati.md`
  (rapporto), `32-ia-registro-strumenti.md` (schede di conferma),
  `30-ia-adattatore-provider.md` (profili, modelli, "Cosa è stato
  inviato"), `31-ia-chiavi-portachiavi.md` (chiave),
  `40-ui-finestra-principale.md` (area a destra, preferenze, pannello
  Comandi, salvataggio della sessione); PySide6.
- **Usato da:** `40-ui-finestra-principale.md` (lo ospita).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | eventi del `35` | testo, schede, richieste di conferma, rapporti, token | valori con unità | |
| in | profili e capacità | `30` | | impostazioni |
| in | stato della chiave | sì/no dal `31` | — | lucchetto |
| out | messaggi, conferme, Stop | segnali al `35` | — | |
| out | chiave | testo dal campo mascherato al `31` | — | mai altrove |
| out | preferenze | `prefs.set` (`05`, classe `application`) | | senza chiave |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole. File Python `src/astrotwo/ui/ai_panel.py`;
test in `tests/ui/test_ai_panel.py`.

- **`AiPanel`** — pannello agganciabile a destra (§3.1–§3.2).
- **`MessageView`** — messaggi in Markdown semplice con evidenziazione dei
  numeri (§3.4).
- **`CommandCard`**, **`ConfirmationCard`** — schede di §3.2 e §3.3.
- **`SentDataDialog`** — "Cosa è stato inviato" (§3.5).
- **`AssistantSettingsDialog`** — impostazioni (§3.6).
- **`ConsentDialog`** — consenso al primo uso (§3.7).

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| PySide6 (QtWidgets; `QTextDocument` con Markdown) | pannello, testo, schede, finestre | A1; Markdown di Qt senza HTML esterno: **verificato il 2026-10-22** (Qt 6.12, md4c) che con `MarkdownDialectGitHub \| MarkdownNoHTML` l'HTML resta testo; immagini e indirizzi dei collegamenti trattati dopo la conversione (§3.10 punto 4) |
| **pytest-qt** | test | come nel `40` (licenza da verificare) |

## 9. Regole e vincoli

- **Nessun numero proprio:** testi e numeri vengono dal `35`, dai moduli e
  dal `34`; il valore pieno è sempre nel suggerimento e copiabile (`02`
  §6).
- **Nessuna chiave** visibile, copiabile o registrata.
- **Mai bloccare il thread principale** (`41` P: ≤ 100 ms).
- **Tutto ciò che esce è mostrabile** ("Cosa è stato inviato").
- **Punto decimale** e cifre DC3 nelle schede (`40` §3.9).
- **Senza assistente il resto dell'app è identico** (regola d'oro n. 7).

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Assistente non disponibile | messaggio di §3.8 con il motivo | codice del `35` |
| Errore del provider in un turno | messaggio d'errore sotto la risposta con codice e testo del `30` | codici del `30` |
| Conversazione troppo lunga | messaggio e pulsante Nuova conversazione | `AI_CONTEXT_TOO_LONG` |
| Endpoint remoto in `http` | rifiuto nelle impostazioni | `AI_INSECURE_ENDPOINT` |
| Chiave rifiutata dal Portachiavi o permesso negato | messaggio del `31` | `KEYCHAIN_UNAVAILABLE`, `KEYCHAIN_ACCESS_DENIED` |
| Risposta con HTML o immagini | mostrati come testo, mai interpretati | — |
| Conferma in attesa e chiusura del pannello | la conferma resta in attesa; riaprendo il pannello si vede | — |
| Uscita dall'app con una risposta in corso | come i comandi in corso del `40` (conferma, Stop) | — |

## 11. Esposizione all'IA

Non applicabile: è interfaccia. Gli strumenti sono del `32`.

## 12. Test di accettazione

Con **pytest-qt** e piattaforma `offscreen`, provider simulato del `35`,
Portachiavi simulato del `31`, in `tests/ui/`.

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Pannello e voce di menu | avvio con un profilo | area a destra larga tra 380 e 420 pt, richiudibile; voce Assistant attiva | ispezione dei widget |
| T2 | Schede dei comandi | risposta finta con due comandi | due schede con `#n`, parametri con unità, esito, fonte; clic → riga del pannello Comandi | ispezione |
| T3 | Conferma | `catalog__load_region` | scheda con `max_rows` e motivo; Conferma, Annulla, "per questa conversazione" | test |
| T4 | Conferma dopo testo esterno | caso T8 del `35` | scheda con "chiesto dopo la lettura di testo esterno", **senza** "Conferma per questa conversazione" | ispezione |
| T5 | Evidenziazione | rapporto del `34` con un numero per ogni stato | stili di §3.4; suggerimento con valore pieno, `#n`, modulo · libreria; riepilogo | ispezione del documento |
| T6 | Cosa è stato inviato | aprire la finestra | JSON identico al `RequestRecord`; nessuna chiave | confronto diretto |
| T7 | Chiave | scrivere una chiave, Salva | `store_key` del `31` simulato; campo vuoto; nessun comando con la chiave in cronologia; la chiave non è in `QSettings` | ispezione |
| T8 | Consenso | primo messaggio con un profilo nuovo; Non ora; poi Accetto | nulla inviato al primo; inviato dopo Accetto; consenso salvato con versione | provider simulato |
| T9 | Non disponibile | nessuna chiave | messaggio di §3.8; vista, menu e comandi funzionano (T1 del `40` passa) | test |
| T10 | Stop | Stop durante una risposta | pulsante torna Invia; nota "risposta interrotta" | test |
| T11 | Locale | profilo `http://127.0.0.1:11434` | simbolo "locale · nulla esce dal Mac" | ispezione |
| T12 | Collegamenti e HTML | risposta con un link e un tag HTML | link non aperto da solo; HTML mostrato come testo | ispezione |
| T13 | Modalità notte | modalità notte rossa | colori del pannello senza componente verde o blu sopra la soglia di T13 del `40` | lettura della tavolozza |
| T14 | Reattività | risposta lenta e comando lungo | sonda del thread principale < 100 ms | sonda di latenza |
| T15 | Scelta del provider (2026-10-17) | aprire il menu Provider; scegliere ogni voce | voci nell'ordine di §3.6 più "Altro endpoint…"; indirizzo riempito come nel `30` §3.1.1; contrassegno su ogni provider non `verified` con il suo stato; nessun modello preselezionato; il lucchetto segue la chiave del profilo scelto | ispezione dei widget |

Note sul codice (sprint 7a, 2026-10-22): test in `tests/ui/test_ai_panel.py`
con la finestra del `40`, il provider simulato a copione del `35`
(`ScriptedAdapter`, corpo JSON vero del `30`) e il Portachiavi simulato
(`FakeKeychain`; nei test nessuna finestra usa il Portachiavi vero,
`tests/conftest.py`). Scritti nello sprint 7a: T1, T2, T3 (con Annulla e
Conferma), T4 (catalogo con l'istruzione, opacità invariata), T6, T7, T8,
T9, T10, T11, T12, T13 (anche i collegamenti dei messaggi), T15 (con il
rifiuto di `http` remoto), più sessione con il testo delle conversazioni,
nuova conversazione e traduzione italiana. Sprint 7b (2026-10-23): T5 (un
numero per ogni stato, stili, suggerimenti, copia, anche dopo il cambio di
tema e in modalità notte), T14 (sonda con risposta lenta e comando lungo),
Aggiorna e "Prova il modello" con il servizio simulato del `30`
(`StreamingService`), errori del provider (`AI_AUTH`) e
`AI_CONTEXT_TOO_LONG`, conferma in attesa con il pannello chiuso, uscita
con una risposta in corso.

## 13. Decisioni aperte

Nessuna decisione dei Gruppi 1 e 2 aperta.

- **Scelte minori: CONFERMATE dal proprietario il 2026-10-16 (come raccomandate):** (1) larghezza di default 400 pt
  (intervallo 380–420); (2) scorciatoia ⌃⌘A per il pannello; (3) Invio
  invia, ⇧Invio va a capo; (4) Markdown semplice senza HTML né immagini,
  collegamenti come testo.
- **Verifiche prima del codice (2026-10-22):** Markdown di `QTextDocument`
  limitabile come in §3.2: **verificato** (§8; immagini e collegamenti
  trattati dopo la conversione, §3.10 punto 4); svuotamento del campo
  della chiave: il widget si svuota (testo e annulla), la stringa Python
  letta non si può cancellare (§3.10 punto 12); licenze di PySide6/Qt e
  pytest-qt già verificate per il `40`.
- **Scelte minori dello sprint 7a (2026-10-22): CONFERMATE dal proprietario
  il 2026-10-23** (§3.10): (1) impostazioni in `QSettings` con le chiavi
  `assistant/…`, modalità rigorosa e limiti comuni a tutti i profili,
  prezzo nel profilo, limiti 1–100 comandi e 1–60 minuti; (2) consenso
  scritto con `prefs.set` e messaggio in attesa inviato dopo "Accetto";
  (3) messaggi dell'utente come testo semplice; (4) indirizzo dei
  collegamenti scritto per intero, clic solo `http`/`https`, immagini come
  testo; (5) contenuto della scheda del comando (primi 4 valori, fonte =
  modulo e funzione dal registro del `05`, senza libreria); (6) testi sotto
  la risposta ricomposti e tradotti dal 44; (7) prima risposta della
  rigenerazione visibile in grigio; (8) uscita con risposta in corso
  come i comandi in corso; (9) 8 icone Lucide in più; (10) pulsante nelle
  preferenze del `40`; (11) modelli e prova in un thread, non comandi;
  (12) campo della chiave senza menu contestuale.
- **Sprint 7b (2026-10-23), scritto:** evidenziazione dei numeri per stato
  con il suggerimento e la copia (§3.4, §3.11, T5), sonda di latenza
  (T14), elenco dei modelli e "Prova il modello" con un servizio simulato,
  errori del provider e conversazione troppo lunga (§10), conferma in
  attesa con il pannello chiuso, uscita con risposta in corso.
- **Scelte minori dello sprint 7b (2026-10-23), DA CONFERMARE** (§3.11; la
  specifica non le dice): (1) segni invisibili dell'area privata di
  Unicode per ritrovare i numeri dopo la conversione del Markdown; (2)
  testo intero nel primo blocco se i blocchi non coincidono con il
  rapporto, prima risposta della rigenerazione evidenziata; (3) stili
  (continua nell'accento, tratteggiata nel testo secondario, sfondo
  d'errore al 30 % con ondulata); (4) testi dei suggerimenti; (5) clic
  destro "Copia il valore pieno" e "Copia la nota".
- **Resta:** lista di controllo manuale con le chiavi dell'utente.
- **Linee guida visive:** valgono quelle del `40` §3.11; nessuno
  scostamento.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-16 | Claude Code | Creazione del file (stato: bozza) dalla proposta della fase 1 sull'IA approvata dal proprietario il 2026-10-16: pannello a destra di 380–420 pt con intestazione (profilo, modello, lucchetto, "locale"), riga sulla privacy, messaggi, schede dei comandi e di conferma (senza "per questa conversazione" dopo un testo esterno), evidenziazione dei numeri del `34`, token e costo facoltativo, "Cosa è stato inviato", impostazioni con la chiave tramite il `31`, consenso al primo uso, stato "non disponibile" con il resto dell'app invariato, modalità notte rossa. |
| 2026-10-16 | Claude Code | Scelte minori **confermate dal proprietario il 2026-10-16** come raccomandate (§13). **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-16. |
| 2026-10-17 | Claude Code | **Decisione del proprietario del 2026-10-17** (profili predefiniti del `30` §3.1.1; aggiornamento del 44 chiesto dal proprietario): §3.6 voce "Tipo" sostituita da "Provider" (menu con i profili predefiniti e "Altro endpoint compatibile OpenAI…", contrassegno per i provider non `verified`, indirizzo riempito e modificabile); T15. Stato `approvato` invariato. |
| 2026-10-22 | Claude Code | **Codice dello sprint 7a** ("FASE: CODICE – interfaccia v1", parte 7): `src/astrotwo/ui/ai_panel.py` (`AiPanel` nell'area a destra al posto dello stato vuoto, `MessageView` con Markdown semplice e sicuro, `CommandCard`, `ConfirmationCard`, `SentDataDialog`, `ConsentDialog`, `AssistantSettingsDialog`), collegamento alla finestra del `40` (impostazioni `assistant/…` con `prefs.set`, pulsante nelle preferenze, testo delle conversazioni nel salvataggio della sessione, uscita con risposta in corso, clic su una scheda → riga del pannello Comandi), traduzione italiana, 8 icone Lucide. Verifica del Markdown di Qt fatta (§8, §13). Precisazioni in §3.10, scelte minori da confermare e resto per lo sprint 7b in §13, note ai test in §12. Stato `approvato` invariato. |
| 2026-10-23 | Claude Code | **Decisione del proprietario del 2026-10-23:** confermate le 12 scelte minori dello sprint 7a (§3.10, §13). **Codice dello sprint 7b** ("FASE: CODICE – interfaccia v1", parte 7): evidenziazione di ogni numero secondo lo stato del `34` con suggerimento (valore pieno con unità, `#n`, funzioni del modulo) e copia, sonda di latenza, test di Aggiorna, "Prova il modello", errori del provider e conversazione troppo lunga. Precisazioni in §3.11, scelte minori dello sprint 7b da confermare in §13, note ai test in §12. Stato `approvato` invariato. |
