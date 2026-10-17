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
| PySide6 (QtWidgets; `QTextDocument` con Markdown) | pannello, testo, schede, finestre | A1; Markdown di Qt senza HTML esterno (**da verificare** che il Markdown di Qt si possa limitare come in §3.2) |
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

## 13. Decisioni aperte

Nessuna decisione dei Gruppi 1 e 2 aperta.

- **Scelte minori: CONFERMATE dal proprietario il 2026-10-16 (come raccomandate):** (1) larghezza di default 400 pt
  (intervallo 380–420); (2) scorciatoia ⌃⌘A per il pannello; (3) Invio
  invia, ⇧Invio va a capo; (4) Markdown semplice senza HTML né immagini,
  collegamenti come testo.
- **Da verificare prima del codice:** Markdown di `QTextDocument`
  limitabile come in §3.2; svuotamento del campo della chiave dalla
  memoria del widget (`31` §3.5); licenze di PySide6/Qt e pytest-qt (`40`).
- **Linee guida visive:** valgono quelle del `40` §3.11; nessuno
  scostamento.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-16 | Claude Code | Creazione del file (stato: bozza) dalla proposta della fase 1 sull'IA approvata dal proprietario il 2026-10-16: pannello a destra di 380–420 pt con intestazione (profilo, modello, lucchetto, "locale"), riga sulla privacy, messaggi, schede dei comandi e di conferma (senza "per questa conversazione" dopo un testo esterno), evidenziazione dei numeri del `34`, token e costo facoltativo, "Cosa è stato inviato", impostazioni con la chiave tramite il `31`, consenso al primo uso, stato "non disponibile" con il resto dell'app invariato, modalità notte rossa. |
| 2026-10-16 | Claude Code | Scelte minori **confermate dal proprietario il 2026-10-16** come raccomandate (§13). **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-16. |
| 2026-10-17 | Claude Code | **Decisione del proprietario del 2026-10-17** (profili predefiniti del `30` §3.1.1; aggiornamento del 44 chiesto dal proprietario): §3.6 voce "Tipo" sostituita da "Provider" (menu con i profili predefiniti e "Altro endpoint compatibile OpenAI…", contrassegno per i provider non `verified`, indirizzo riempito e modificabile); T15. Stato `approvato` invariato. |
