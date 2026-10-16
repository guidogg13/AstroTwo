# 30-ia-adattatore-provider.md — adattatore dei provider IA

**Stato:** bozza

## 2. Scopo

Offrire all'assistente (`35`) un solo contratto "a capacità" — chiamata di
strumenti e streaming — per parlare con il provider IA e il modello scelti
dall'utente, nel cloud o in locale, con errori, tempi massimi e dati
inviati sempre dichiarati.

## 3. Cosa fa

Origine: decisione A5 di `01-architettura.md` (interfaccia a capacità con
due implementazioni iniziali) e proposta della fase 1 sull'IA nella v1,
**approvata dal proprietario il 2026-10-16** (punto 2: SDK `anthropic` e SDK
`openai` con endpoint configurabile; nessun identificativo di modello nel
codice; modelli senza chiamata di strumenti rifiutati).

### 3.1 Profili di provider

Un **profilo** descrive dove e con quale modello parla l'assistente.
L'utente crea e sceglie i profili nelle impostazioni del `44`; i profili
stanno nelle impostazioni dell'app (`QSettings`, `40` §3.10), **mai la
chiave** (che sta nel Portachiavi, `31`) e mai nella sessione.

| Campo | Contenuto | Note |
|---|---|---|
| `kind` | `anthropic` oppure `openai_compatible` | le due implementazioni (§3.2) |
| `base_url` | indirizzo dell'endpoint | `anthropic`: quello predefinito dell'SDK, modificabile; `openai_compatible`: **obbligatorio**, scritto dall'utente (OpenAI in cloud, Ollama, LM Studio, vLLM o altro servizio compatibile) |
| `model` | identificativo del modello | **scelto dall'utente** dall'elenco di `list_models` o scritto a mano; **nessun identificativo di modello è scritto nel codice**, nemmeno come default |
| `id` | identificativo del profilo | `anthropic` oppure `openai-compatible:<host>[:<porta>]` ricavato da `base_url`; è anche il nome dell'account nel Portachiavi (`31` §3.1) |
| `max_output_tokens` | intero > 0 | default 4096 (scelta minore 1), modificabile |
| `local` | sì/no | **ricavato**, non scritto dall'utente: sì solo se l'host di `base_url` è `localhost`, `127.0.0.1` o `::1` |

- **Chiave:** obbligatoria per i profili remoti; facoltativa per quelli
  locali (molti server locali non la chiedono). Senza chiave un profilo
  remoto non è utilizzabile (`KEY_NOT_FOUND` del `31`, mostrato dal `44`).
- **Sicurezza del trasporto:** un endpoint remoto deve essere `https`;
  `http` è ammesso solo per gli host locali. Altrimenti
  `AI_INSECURE_ENDPOINT`, nessuna richiesta.

### 3.2 Le due implementazioni

1. **`AnthropicAdapter`** — API Messages di Anthropic con l'SDK ufficiale
   `anthropic`: messaggi con blocchi di testo, `tool_use` e `tool_result`;
   regole di sistema nel campo `system`; streaming con gli eventi
   dell'SDK.
2. **`OpenAICompatibleAdapter`** — API **Chat Completions** con l'SDK
   ufficiale `openai` e `base_url` del profilo: messaggi `system`, `user`,
   `assistant` (con `tool_calls`) e `tool`; streaming con i frammenti
   (`chunk`) dell'SDK. Si usa Chat Completions, non altre API più recenti
   di OpenAI, perché è quella offerta dai server locali compatibili
   (Ollama, LM Studio, vLLM): un solo formato copre cloud e locale.
   **Da verificare prima del codice:** chiamata di strumenti in streaming
   con almeno Ollama e LM Studio.

Le due implementazioni rispettano lo **stesso contratto** (§3.3–§3.7) e
passano gli **stessi test** (§12) con servizi simulati.

### 3.3 Capacità dichiarate

Ogni adattatore espone per il modello del profilo un `ProviderCapabilities`:

| Capacità | Come si ricava |
|---|---|
| `tool_calling` | **obbligatoria.** Per `anthropic` dichiarata dall'implementazione (l'API Messages la offre; **da verificare** per ogni modello elencato). Per `openai_compatible` non è dichiarata in modo affidabile dall'elenco dei modelli: si scopre alla prima richiesta (il servizio rifiuta il parametro `tools` o risponde senza poter chiamare strumenti) oppure con il pulsante **"Prova il modello"** del `44` (una richiesta minima con uno strumento di prova, avviata dall'utente, con i token mostrati). |
| `streaming` | obbligatoria; un servizio che non trasmette in streaming → `AI_BAD_RESPONSE` |
| `parallel_tool_calls` | se il modello può chiedere più strumenti nello stesso turno; il `35` li esegue comunque **uno alla volta**, nell'ordine ricevuto |
| `max_context_tokens` | dal provider se lo dichiara nell'elenco dei modelli; altrimenti "non dichiarato" (nessun valore inventato) |
| `local` | dal profilo (§3.1) |

- **Un modello senza chiamata di strumenti viene rifiutato** con
  `AI_NO_TOOLS`: senza comandi l'assistente potrebbe rispondere solo
  "a mente", cioè calcolando, il che è vietato (regola d'oro n. 1).
- **Immagini inviate al modello:** fuori dalla v1 (nessuna capacità di
  visione usata).

### 3.4 Elenco dei modelli (`list_models`)

- Chiede l'elenco all'endpoint dei modelli del provider (`models.list`
  dell'SDK `anthropic`; `models.list` dell'SDK `openai` sull'indirizzo del
  profilo) e restituisce identificativo e, se c'è, nome leggibile e
  contesto massimo.
- **Nessun elenco scritto nel codice.** Se l'endpoint non offre l'elenco
  (alcuni servizi compatibili) → avviso `AI_MODELS_UNAVAILABLE` e l'utente
  scrive l'identificativo a mano.

### 3.5 Un turno in streaming (`stream_turn`)

`stream_turn(messages, tools, options, cancel)` invia **una** richiesta al
provider e restituisce, man mano che arrivano, **eventi normalizzati**:

| Evento | Contenuto |
|---|---|
| `TextDelta` | frammento di testo della risposta |
| `ToolCallRequest` | identificativo della chiamata, nome dello strumento, argomenti come **testo JSON completo** (l'adattatore ricompone i frammenti dello streaming; non interpreta né corregge gli argomenti, che valida il `32`) |
| `Usage` | token in ingresso e in uscita del turno (e in cache, se il provider li dichiara) |
| `ProviderNotice` | fatto da dichiarare all'utente (es. "ripetuta dopo HTTP 429, attesa 4 s") |
| `TurnEnd` | motivo: `end` (risposta finita), `tool_use` (aspetta i risultati degli strumenti), `max_tokens`, `refusal` (il modello rifiuta), `cancelled` |
| `ProviderError` | codice di §10, testo, eventuale attesa suggerita dal provider (`retry-after`) |

- **Formato dei messaggi in ingresso** (normalizzato, uguale per i due
  adattatori): regole di sistema; messaggi dell'utente; messaggi
  dell'assistente con testo e chiamate di strumenti; **risultati degli
  strumenti** (identificativo della chiamata, contenuto JSON del `32`, esito
  d'errore sì/no). L'adattatore li traduce nel formato del provider senza
  aggiungere, togliere o riscrivere contenuti.
- **Strumenti in ingresso:** nome, descrizione e schema JSON preparati dal
  `32`; l'adattatore li traduce nel formato del provider senza cambiarli.
- **Nessun parametro di campionamento** inviato (temperatura e simili):
  vale il default del provider (scelta minore 2). La correttezza dei numeri
  non dipende dal modello: i numeri vengono dai comandi e li controlla il
  `34`.

### 3.6 Chiave, variabili d'ambiente, log

- La chiave si legge dal `31` **all'inizio di ogni turno** e si passa
  esplicitamente al client dell'SDK; il client vive solo per il turno.
  Per un profilo locale senza chiave si passa un segnaposto fisso non
  segreto (l'SDK `openai` ne richiede uno).
- **Variabili d'ambiente ignorate:** `ANTHROPIC_API_KEY`,
  `ANTHROPIC_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` e simili non
  si usano mai (chiave e indirizzo si passano sempre in modo esplicito).
- **Log degli SDK e di `httpx`:** livello `WARNING` al massimo e un filtro
  che toglie intestazioni e corpi; nessun log contiene chiave, intestazioni
  di autenticazione o testi della conversazione.
- **Registro di ciò che è stato inviato (`RequestRecord`):** per ogni turno
  l'adattatore conserva in memoria il **corpo JSON esatto** inviato al
  provider (modello, regole, messaggi, strumenti, opzioni), **senza
  intestazioni** e senza chiave, più indirizzo e ora (UTC, ISO 8601). Il
  `44` lo mostra in "Cosa è stato inviato" (`35` §3.8). Non si salva su
  disco.

### 3.7 Tempi massimi, ripetizioni, annullamento

- **Tempi massimi** (decisi il 2026-10-16, configurabili): **10 s** per la
  connessione, **60 s** per la lettura, **30 s di silenzio** nello streaming
  (nessun evento) → `AI_TIMEOUT`.
- **Ripetizioni:** quelle interne degli SDK sono **disattivate**
  (`max_retries = 0`); l'adattatore ripete **al massimo 2 volte**, e solo
  **prima del primo evento ricevuto**, per errori di connessione e per le
  risposte HTTP 429, 500, 502, 503, 504 e 529 (servizio sovraccarico),
  aspettando il `retry-after` del provider (al più 30 s) oppure 1 s e poi
  4 s. Ogni ripetizione è un `ProviderNotice`. Dopo il primo evento non si
  ripete mai (si duplicherebbe testo già mostrato): l'errore arriva al
  `35`.
- **Annullamento:** con il `CancelToken` (lo stesso del `05`) l'adattatore
  chiude lo streaming e la connessione ed emette `TurnEnd(cancelled)`;
  i token consumati fino a lì si dichiarano se il provider li ha inviati.

## 4. Cosa NON fa

- Non sceglie gli strumenti né li esegue (`32`, `35`), non decide cosa
  mandare al modello (`35`) e non verifica i numeri (`34`).
- Non calcola nulla e non interpreta il testo del modello.
- Non conserva chiavi (`31`) né conversazioni su disco.
- Non contiene identificativi di modelli né prezzi.
- Non invia immagini, file o pixel al modello.
- Non usa librerie che unificano i provider (es. LiteLLM): due SDK ufficiali
  con licenze permissive, passaggi intermedi sotto controllo.
- Non supporta modelli senza chiamata di strumenti.

## 5. Livello e dipendenze

- **Livello:** 3 (IA). Nella v1 l'assistente lavora sopra il livello 1
  (comandi del `05`); le dipendenze restano solo verso il basso e senza IA
  l'app funziona ai livelli 1 e 2 (regola d'oro n. 7).
- **Dipende da:** `31-ia-chiavi-portachiavi.md` (chiave al momento della
  chiamata); `05-comandi-sessione.md` (solo il tipo `CancelToken`);
  librerie `anthropic`, `openai` (e `httpx`, che usano entrambe).
- **Usato da:** `35-ia-assistente-chat.md` (turni), `44-ui-pannello-ia.md`
  (profili, elenco dei modelli, "Prova il modello", "Cosa è stato
  inviato").

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | profilo | `ProviderProfile` | §3.1 | da `QSettings`, senza chiave |
| in | chiave | `SecretKey` del `31` | — | letta a ogni turno |
| in | messaggi | lista normalizzata | testo UTF-8; risultati come JSON del `32` | §3.5 |
| in | strumenti | lista | nome, descrizione, JSON Schema dal `32` | §3.5 |
| in | opzioni | struttura | `max_output_tokens` (intero), tempi massimi (s) | §3.1, §3.7 |
| in | `CancelToken` | segnale | — | Stop del `44` |
| out | eventi | `TextDelta`, `ToolCallRequest`, `Usage`, `ProviderNotice`, `TurnEnd`, `ProviderError` | token come interi | §3.5 |
| out | elenco dei modelli | lista | identificativo, nome, contesto massimo se dichiarato | §3.4 |
| out | `ProviderCapabilities` | struttura | §3.3 | |
| out | `RequestRecord` | struttura | JSON esatto inviato, indirizzo, ora UTC ISO 8601 | senza intestazioni né chiave |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole. File Python
`src/astrotwo/ai/provider_adapter.py`; test in
`tests/ai/test_provider_adapter.py`.

- **`ProviderProfile`** — i campi di §3.1; `local` ricavato.
- **`ProviderCapabilities`** — le capacità di §3.3.
- **`ProviderAdapter`** (interfaccia) — `capabilities()`, `list_models()`,
  `stream_turn(messages, tools, options, cancel)` → eventi,
  `probe_tools()` (la prova di "Prova il modello"), `last_request()` →
  `RequestRecord`.
- **`AnthropicAdapter`**, **`OpenAICompatibleAdapter`** — le due
  implementazioni.
- **`make_adapter(profile, keychain)`** — crea l'adattatore del profilo;
  controlla `https` (§3.1).
- **Eventi:** `TextDelta`, `ToolCallRequest`, `Usage`, `ProviderNotice`,
  `TurnEnd`, `ProviderError`.
- **`ProviderErrorCode`** — i codici di §10.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| **`anthropic`** (SDK ufficiale) | API Messages, streaming, chiamata di strumenti, elenco dei modelli | decisione del proprietario del 2026-10-16; **licenza MIT da verificare** e da aggiungere a `THIRD_PARTY_LICENSES` con le dipendenze |
| **`openai`** (SDK ufficiale) | API Chat Completions su endpoint configurabile, streaming, chiamata di strumenti, elenco dei modelli | decisione del proprietario del 2026-10-16; copre OpenAI in cloud e i server locali compatibili; **licenza Apache-2.0 da verificare** e da aggiungere a `THIRD_PARTY_LICENSES` con le dipendenze |
| `httpx` (dipendenza dei due SDK) | trasporto HTTP, tempi massimi | licenza BSD-3 da verificare; nessun uso diretto oltre a tempi massimi e log |
| JSON Schema | descrizione degli strumenti verso i provider | formato accettato da entrambe le API (sottoinsieme preparato dal `32`) |

**Dipendenze dei due SDK** (da verificare con le licenze, es. `pydantic`,
`anyio`, `distro`, `jiter`, `sniffio`, `typing-extensions`, `tqdm`): tutte
da aggiungere a `THIRD_PARTY_LICENSES` nello stesso commit che introduce
gli SDK (`01` §6).

## 9. Regole e vincoli

- **L'adattatore non calcola e non interpreta:** traduce formati e
  trasporta testo ed eventi.
- **Nessun identificativo di modello nel codice;** il modello lo sceglie
  l'utente.
- **Chiave solo dal `31`,** mai da variabili d'ambiente, mai nei log né nel
  `RequestRecord`.
- **`https` per gli endpoint remoti.**
- **Ciò che esce è solo ciò che il `35` passa,** registrato esattamente nel
  `RequestRecord` (privacy, `35` §3.8).
- **Tempi massimi sempre applicati;** le ripetizioni sono dichiarate e mai
  dopo il primo evento.
- I test **non usano mai un provider reale né una chiave reale** (`02` §8,
  punto 4): servizi simulati locali.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Chiave rifiutata (HTTP 401/403) | turno fermato, messaggio "chiave non valida o senza permessi" | `AI_AUTH` |
| Troppe richieste (HTTP 429) dopo le ripetizioni | turno fermato con l'attesa suggerita | `AI_RATE_LIMIT` |
| Connessione impossibile, rete assente | turno fermato; il resto dell'app funziona | `AI_CONNECTION` |
| Tempo massimo superato (connessione, lettura, silenzio) | turno fermato con il tempo superato | `AI_TIMEOUT` |
| Errore del servizio (HTTP 5xx, 529) dopo le ripetizioni | turno fermato | `AI_SERVICE` |
| Modello inesistente (HTTP 404 sul modello) | turno fermato | `AI_MODEL_NOT_FOUND` |
| Conversazione oltre il contesto del modello | turno fermato, il `44` propone una nuova conversazione | `AI_CONTEXT_TOO_LONG` |
| Modello senza chiamata di strumenti | profilo non utilizzabile | `AI_NO_TOOLS` |
| Risposta non conforme (evento sconosciuto, streaming assente, JSON dello streaming illeggibile) | turno fermato | `AI_BAD_RESPONSE` |
| Endpoint remoto in `http` | nessuna richiesta | `AI_INSECURE_ENDPOINT` |
| Elenco dei modelli non disponibile | avviso, identificativo scritto a mano | `AI_MODELS_UNAVAILABLE` |
| Argomenti di uno strumento che non sono JSON valido | passati al `35` come sono; il `32` li rifiuta e il modello riceve l'errore | — |
| Il modello rifiuta di rispondere | `TurnEnd(refusal)`, mostrato come tale | — |
| Stop dell'utente | streaming chiuso, `TurnEnd(cancelled)` | `AI_CANCELLED` |

## 11. Esposizione all'IA

Non applicabile: l'adattatore è il canale verso l'IA, non uno strumento
che l'IA può chiamare.

## 12. Test di accettazione

In `tests/ai/test_provider_adapter.py`, **senza rete e senza chiavi
reali**: due servizi HTTP simulati locali (come `FakeService` di
`tests/conftest.py`) che imitano lo streaming dell'API Messages di
Anthropic e di Chat Completions, con risposte registrate a mano nei test.
Ogni test vale per **entrambi** gli adattatori, salvo dove indicato.

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Testo in streaming | risposta simulata in 20 frammenti | 20 `TextDelta` nell'ordine, poi `Usage` e `TurnEnd(end)`; testo ricomposto identico | confronto diretto |
| T2 | Chiamata di strumento | argomenti JSON spezzati in 7 frammenti; due chiamate nello stesso turno | due `ToolCallRequest` con argomenti identici al JSON del servizio, nell'ordine; `TurnEnd(tool_use)` | confronto diretto |
| T3 | Risultati degli strumenti | conversazione con un risultato d'errore e uno riuscito | corpo inviato con `tool_result`/`tool` nel formato di ciascun provider, contenuto identico | ispezione del corpo ricevuto dal servizio simulato |
| T4 | Errori | il servizio risponde 401, 403, 404 sul modello, 429 con `retry-after`, 500, 529, contesto superato, corpo non conforme | codici di §10; 429 e 5xx ripetuti al più 2 volte con le attese, ciascuna dichiarata in un `ProviderNotice` | orologio simulato, conteggio delle richieste |
| T5 | Nessuna ripetizione dopo il primo evento | 503 simulato dopo 3 frammenti di testo | nessuna ripetizione; `AI_SERVICE` | conteggio delle richieste |
| T6 | Tempi massimi | servizio che non accetta la connessione; che non risponde per 61 s; che tace 31 s a metà streaming | `AI_TIMEOUT` con il tempo superato | orologio simulato |
| T7 | Annullamento | Stop dopo 5 frammenti | connessione chiusa, `TurnEnd(cancelled)`, nessun evento dopo | ispezione del servizio |
| T8 | Nessun modello nel codice | ricerca nel codice sorgente di `src/astrotwo/ai/` di identificativi di modelli noti dei due provider (elenco del test) | nessuna occorrenza | analisi del testo |
| T9 | Variabili d'ambiente ignorate | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` impostate a valori di prova | il servizio simulato riceve la chiave finta del `31` simulato e l'indirizzo del profilo, mai i valori delle variabili | ispezione delle richieste |
| T10 | Nessuna chiave nei log e nel registro | turno completo con log al livello più dettagliato | la chiave finta non compare nei log né nel `RequestRecord`; il `RequestRecord` è identico al corpo ricevuto dal servizio | confronto diretto e ricerca nel testo |
| T11 | `https` obbligatorio | profilo remoto `http://example.org`; profilo `http://127.0.0.1:11434` | `AI_INSECURE_ENDPOINT`; il secondo accettato e `local` = sì | test di unità |
| T12 | Elenco dei modelli | servizio con e senza endpoint dei modelli | elenco del servizio; `AI_MODELS_UNAVAILABLE` | servizio simulato |
| T13 | Modello senza strumenti (`openai_compatible`) | il servizio rifiuta `tools` come fanno i server senza chiamata di strumenti (risposta registrata nel test) | `AI_NO_TOOLS` | servizio simulato |
| T14 | Contratto uguale | stessa conversazione normalizzata sui due servizi simulati con risposte equivalenti | stessa sequenza di eventi normalizzati | confronto diretto |

**Lista di controllo manuale** (prima di approvare il codice, con le
chiavi dell'utente e a sue spese): un turno con strumenti con un modello
Anthropic scelto dall'utente; uno con OpenAI in cloud; uno con Ollama o LM
Studio in locale. Esito annotato nel registro modifiche.

## 13. Decisioni aperte

Nessuna decisione dei Gruppi 1 e 2 aperta.

- **Scelte minori da confermare:** (1) `max_output_tokens` di default 4096,
  modificabile nel profilo; (2) nessun parametro di campionamento inviato
  (vale il default del provider); (3) ripetizioni dell'adattatore al più 2,
  solo prima del primo evento, per connessione e HTTP 429, 500, 502, 503,
  504, 529 (attese: `retry-after` fino a 30 s, altrimenti 1 s e 4 s); (4)
  identificativo del profilo `openai-compatible:<host>[:<porta>]` (un
  profilo per endpoint).
- **Da verificare prima del codice:** licenze di `anthropic`, `openai`,
  `httpx` e delle loro dipendenze (da aggiungere a `THIRD_PARTY_LICENSES`);
  chiamata di strumenti in streaming con Ollama e LM Studio; chiamata di
  strumenti per i modelli elencati dall'API di Anthropic; come i server
  compatibili segnalano un modello senza strumenti (per `AI_NO_TOOLS`).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-16 | Claude Code | Creazione del file (stato: bozza) dalla proposta della fase 1 sull'IA approvata dal proprietario il 2026-10-16: profili senza chiave, due implementazioni (SDK `anthropic`, SDK `openai` con endpoint configurabile e Chat Completions), capacità dichiarate, `list_models`, `stream_turn` con eventi normalizzati, `AI_NO_TOOLS`, tempi massimi 10/60/30 s, ripetizioni solo prima del primo evento, `RequestRecord` per "Cosa è stato inviato", `https` per gli endpoint remoti, nessun modello nel codice. |
