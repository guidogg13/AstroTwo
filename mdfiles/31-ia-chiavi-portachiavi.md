# 31-ia-chiavi-portachiavi.md — chiavi API nel Portachiavi di macOS

**Stato:** approvato

## 2. Scopo

Conservare, leggere al momento della chiamata e cancellare le chiavi API
dei provider IA scelti dall'utente **solo nel Portachiavi di macOS**, senza
che una chiave finisca mai in un file, in un log, nella cronologia, nella
sessione o nel repository (regola d'oro n. 5).

## 3. Cosa fa

Origine: proposta della fase 1 sull'IA nella v1, **approvata dal
proprietario il 2026-10-16** (punto 2: libreria `keyring` forzata sul solo
Portachiavi di macOS, nessun ripiego su file; se il Portachiavi non è
disponibile, errore esplicito).

### 3.1 Dove sta una chiave

- **Un elemento del Portachiavi per profilo di provider** (`30` §3.1): una
  sola chiave per profilo (più chiavi per lo stesso profilo: fuori dalla
  v1).
- **Nome del servizio:** `dev.pages.astrotwo.ai` (fisso; identificativo
  inverso del progetto `dev.pages.astrotwo`, dal sito `astrotwo.pages.dev`,
  con il suffisso `.ai` per le chiavi dell'IA; decisione del proprietario
  del 2026-10-16, stesso identificativo del bundle dell'app, `01` §6).
  **Nome dell'account:**
  l'identificativo del profilo del `30` (es. `anthropic`,
  `openai-compatible:api.openai.com`). Nessun altro dato nell'elemento.
  Dal 2026-10-17 vale anche per i **profili predefiniti** del `30` §3.1.1
  (es. `openai-compatible:generativelanguage.googleapis.com` per Gemini,
  `openai-compatible:localhost:11434` per Ollama): ogni profilo ha la sua
  chiave, nessuna regola nuova.
- L'elemento sta nel **Portachiavi di login** dell'utente, quello che
  `keyring` usa su macOS; **non è sincronizzato con iCloud** (la
  sincronizzazione è fuori dalla v1). **Da verificare prima del codice:**
  che il backend macOS di `keyring` crei elementi non sincronizzabili e nel
  Portachiavi di login.

### 3.2 Backend forzato, nessun ripiego

- Il modulo **imposta esplicitamente** il backend macOS di `keyring`
  (`keyring.backends.macOS.Keyring`) e usa **solo quello**. Non usa la
  scelta automatica di `keyring`, che può cadere su altri backend.
- **Ignora** ogni configurazione esterna di `keyring`: la variabile
  d'ambiente `PYTHON_KEYRING_BACKEND`, il file `keyringrc.cfg` e i backend
  installati da altri pacchetti (es. `keyrings.alt`, che salva in chiaro su
  file).
- **Nessun ripiego:** se il backend macOS non è disponibile (sistema non
  macOS, Portachiavi bloccato o non raggiungibile, libreria Security non
  caricabile) → errore `KEYCHAIN_UNAVAILABLE` con il motivo. **Mai** un file,
  una variabile d'ambiente o la memoria come alternativa.
- **Mai variabili d'ambiente come sorgente di chiavi:** `ANTHROPIC_API_KEY`
  e `OPENAI_API_KEY` non si leggono (anche il `30` le ignora, §3.6 del
  `30`).

### 3.3 Operazioni

1. **Salvare** (`store_key`): riceve l'identificativo del profilo e la
   chiave scritta dall'utente nel campo mascherato del `44`.
   - Toglie spazi e a capo all'inizio e alla fine (errore di copia
     frequente); rifiuta una chiave vuota, con caratteri di controllo o più
     lunga di 4096 caratteri (`KEY_FORMAT_INVALID`). **Nessun controllo
     del formato specifico del provider** (prefissi, lunghezza): i formati
     cambiano e non sono documentati come stabili; la chiave si verifica
     solo usandola (`AI_AUTH` del `30`).
   - Scrive l'elemento; se esiste già lo sostituisce (una chiave per
     profilo).
2. **Sapere se c'è** (`has_key`): sì/no, per lo stato "chiave presente"
   (lucchetto) del `44`. La libreria non offre una lettura dell'esistenza
   senza leggere il segreto: il segreto letto si scarta subito e non si
   restituisce.
3. **Leggere al momento** (`get_key`): chiamata dal `30` **all'inizio di
   ogni turno** verso il provider. Restituisce un `SecretKey`: un
   contenitore il cui testo leggibile (`str`, `repr`, formattazione, log) è
   sempre `"••••"`; il valore si ottiene solo con un metodo esplicito
   (`reveal`), usato dal `30` solo per costruire il client del provider. Il
   modulo **non tiene copie** della chiave: niente cache in memoria tra un
   turno e l'altro.
4. **Cancellare** (`delete_key`): toglie l'elemento; cancellare una chiave
   che non c'è non è un errore (esito "nessuna chiave da cancellare").

### 3.4 Permessi di macOS

- La prima volta che l'app legge l'elemento, macOS può chiedere all'utente
  il permesso ("AstroTwo vuole usare la tua password del portachiavi").
  Un rifiuto → `KEYCHAIN_ACCESS_DENIED`, nessun ripiego.
- Il permesso è legato alla firma dell'app: un'app non firmata o rifirmata
  può far ripetere la richiesta a ogni aggiornamento. **Da verificare prima
  del codice**, insieme ad A6 (firma e notarizzazione) nel `60`.

### 3.5 Nessuna traccia della chiave

- Le operazioni del modulo **non sono comandi del `05`**: salvare o
  cancellare una chiave non entra in cronologia né nella sessione (come
  "Salva sessione", `05` §3.4), così nessun segreto può finire lì.
- Messaggi d'errore e avvisi **non contengono mai la chiave**, nemmeno in
  parte (né prefisso né ultime cifre).
- Il campo del `44` è mascherato e non si copia negli appunti; il testo
  scritto si cancella dalla memoria del widget dopo il salvataggio (per
  quanto Qt lo consenta: **da verificare** nel `44`).

## 4. Cosa NON fa

- Non decide quali provider o profili esistono (`30`) e non mostra
  interfaccia (`44`).
- Non verifica che una chiave sia valida presso il provider (lo fa il `30`
  alla prima chiamata, `AI_AUTH`).
- Non sincronizza le chiavi con iCloud né le esporta.
- Non conserva più chiavi per lo stesso profilo né chiavi diverse dalle
  chiavi API dei provider IA (es. credenziali dei servizi VO: fuori dalla
  v1).
- Non usa file, variabili d'ambiente o backend diversi dal Portachiavi di
  macOS, nemmeno come ripiego.
- Non registra nulla nella cronologia, nella sessione o nei log.

## 5. Livello e dipendenze

- **Livello:** 3 (IA). Senza questo modulo, o senza chiave, l'app funziona
  ai livelli 1 e 2 (regola d'oro n. 7).
- **Dipende da:** nessun altro modulo di AstroTwo; libreria `keyring`
  (backend macOS).
- **Usato da:** `30-ia-adattatore-provider.md` (lettura al momento della
  chiamata), `44-ui-pannello-ia.md` (salvare, cancellare, stato "chiave
  presente"), `40-ui-finestra-principale.md` (preferenze dell'assistente,
  tramite il `44`).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | identificativo del profilo | stringa | identificativo del `30` §3.1 | nome dell'account nel Portachiavi |
| in | chiave | stringa | testo, 1–4096 caratteri senza caratteri di controllo | dal campo mascherato del `44` |
| out | `SecretKey` | contenitore | testo leggibile sempre `"••••"` | valore solo con `reveal()` |
| out | chiave presente | booleano | — | stato del lucchetto nel `44` |
| out | errore | `KeychainError` | codice di §10 + testo senza la chiave | |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole. File Python
`src/astrotwo/ai/keychain_keys.py`; test in `tests/ai/test_keychain_keys.py`.

- **`KeychainStore`** — accesso al Portachiavi con il backend macOS forzato
  (§3.2). Alla creazione controlla il backend e, se non è disponibile,
  solleva `KEYCHAIN_UNAVAILABLE`. Metodi: `store_key(profile_id, key)`,
  `has_key(profile_id)` → booleano, `get_key(profile_id)` → `SecretKey`,
  `delete_key(profile_id)` → esito.
- **`SecretKey`** — contenitore del segreto: `reveal()` restituisce il
  valore; ogni altra forma di testo è `"••••"`; non si serializza in JSON
  (errore se si prova).
- **`KeychainError`** — errore con codice di §10 e testo senza segreti.
- **`SERVICE_NAME`** — costante `"dev.pages.astrotwo.ai"`.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| **`keyring`** (backend `keyring.backends.macOS`) | lettura, scrittura e cancellazione degli elementi del Portachiavi | decisione del proprietario del 2026-10-16; libreria consolidata e diffusa; **licenza MIT da verificare** e da aggiungere a `THIRD_PARTY_LICENSES` con le sue dipendenze (per Python 3.12, da verificare: `jaraco.classes`, `jaraco.functools`, `jaraco.context`) |
| Portachiavi di macOS (Security framework) | dove vivono le chiavi | regola d'oro n. 5, S5 di `01` |

**Da verificare prima del codice:** che il backend macOS di `keyring`
funzioni dentro l'app costruita per il `.dmg` (PyInstaller, A2 del `01`).

## 9. Regole e vincoli

- **Solo il Portachiavi di macOS** (regola d'oro n. 5): nessun file,
  nessuna variabile d'ambiente, nessun ripiego.
- **Nessuna copia della chiave** in memoria oltre il tempo della chiamata
  al provider; nessuna chiave in log, eccezioni, cronologia, sessione,
  `QSettings`, appunti o messaggi.
- **Errore esplicito** quando il Portachiavi non c'è o nega l'accesso.
- I test **non usano mai una chiave reale** (`02` §8, punto 4).

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Sistema non macOS, backend macOS non caricabile, Portachiavi non raggiungibile | nessuna operazione, motivo nel messaggio; l'assistente non è disponibile, il resto dell'app funziona | `KEYCHAIN_UNAVAILABLE` |
| L'utente nega il permesso di macOS | nessuna chiave letta né scritta | `KEYCHAIN_ACCESS_DENIED` |
| Nessuna chiave per il profilo | `get_key` fallisce; `has_key` = no | `KEY_NOT_FOUND` |
| Chiave vuota, con caratteri di controllo o troppo lunga | rifiuto, nulla scritto | `KEY_FORMAT_INVALID` |
| Scrittura o cancellazione fallita nel Portachiavi | errore con il motivo del sistema (senza la chiave) | `KEYCHAIN_WRITE_FAILED` |
| `PYTHON_KEYRING_BACKEND` o `keyringrc.cfg` puntano a un backend su file | ignorati: si usa solo il backend macOS | — |
| Variabili `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` presenti | ignorate | — |
| Cancellare una chiave che non c'è | esito "nessuna chiave da cancellare", nessun errore | — |

## 11. Esposizione all'IA

Non applicabile: le chiavi non sono mai visibili all'IA né a uno
strumento; il modulo non è nel registro del `32`.

## 12. Test di accettazione

Test di default in `tests/ai/test_keychain_keys.py` con un **backend
simulato in memoria** che sostituisce le funzioni del backend macOS (mai il
Portachiavi reale, mai una chiave reale). Test sul Portachiavi reale solo
con il marcatore **`keychain`** (scelta minore 2), esclusi di default.

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Salva, leggi, cancella | `store_key("test-profile", "sk-finta-123")`, `has_key`, `get_key`, `delete_key`, `has_key` | sì; `reveal()` = `"sk-finta-123"`; poi no | backend simulato |
| T2 | Spazi tolti, formati rifiutati | chiave con spazi e a capo ai bordi; chiave vuota; chiave con `\x00`; 4097 caratteri | la prima salvata senza spazi; le altre `KEY_FORMAT_INVALID`, nulla scritto | backend simulato |
| T3 | Backend forzato | `PYTHON_KEYRING_BACKEND` impostato su un backend su file di prova; un backend su file registrato | il modulo usa solo il backend macOS (simulato); nessun file creato nella cartella home temporanea | ispezione della cartella |
| T4 | Nessun ripiego | backend macOS non disponibile (simulato) | `KEYCHAIN_UNAVAILABLE`; nessun file creato; nessuna chiave restituita | test di unità |
| T5 | Permesso negato | il backend simulato solleva l'errore di accesso negato | `KEYCHAIN_ACCESS_DENIED` | test di unità |
| T6 | Nessuna traccia | salvare e leggere una chiave riconoscibile con log al livello più dettagliato; provocare tutti gli errori di §10 | la chiave (e ogni sua sottostringa di 4 o più caratteri) non compare in log, messaggi d'errore, `str`/`repr` di `SecretKey`; serializzare `SecretKey` in JSON è un errore | ricerca nel testo catturato |
| T7 | Variabili d'ambiente ignorate | `ANTHROPIC_API_KEY` impostata, nessuna chiave nel Portachiavi | `KEY_NOT_FOUND` | test di unità |
| T8 | Portachiavi reale (`keychain`) | sul Mac: salvare, leggere, cancellare una chiave finta con un nome di servizio di test | operazioni riuscite; elemento rimosso alla fine; nessun elemento sincronizzabile | marcatore `keychain`, eseguito a mano |

## 13. Decisioni aperte

Nessuna decisione dei Gruppi 1 e 2 aperta.

- **Scelte minori: CONFERMATE dal proprietario il 2026-10-16:** (1) **modificata dal proprietario:** nome del servizio
  `dev.pages.astrotwo.ai` (identificativo inverso del progetto con suffisso
  `.ai`) e nome dell'account = identificativo del profilo del `30`; (2) nuovo
  marcatore di test `keychain` per il Portachiavi reale, escluso di default
  come `network` (si aggiunge a `pyproject.toml` con il codice); (3) spazi
  e a capo ai bordi tolti in silenzio al salvataggio (sono sempre errori di
  copia).
- **Verifiche prima del codice (2026-10-16):** licenza di `keyring` 25.7.0
  (MIT) e delle dipendenze (`jaraco.classes`, `jaraco.context`,
  `jaraco.functools`, `more-itertools`, MIT) **verificate** e in
  `THIRD_PARTY_LICENSES`; backend `keyring.backends.macOS` usato
  direttamente: scrive nel **Portachiavi di login**
  (`login.keychain-db`), elemento **non sincronizzabile**, lettura e
  cancellazione riuscite con un servizio di prova; **la forzatura serve**:
  con `PYTHON_KEYRING_BACKEND` la scelta automatica di `keyring` cade su un
  altro backend (provato con quello nullo); **dentro un'app costruita con
  PyInstaller** 6.22.3 (cartella, senza firma) il backend funziona. Resta
  per il `60`: richiesta di permesso di macOS con l'app firmata (A6).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-16 | Claude Code | Creazione del file (stato: bozza) dalla proposta della fase 1 sull'IA approvata dal proprietario il 2026-10-16: `keyring` con il solo backend macOS forzato, nessun ripiego (`KEYCHAIN_UNAVAILABLE`), una chiave per profilo del `30`, lettura al momento della chiamata con `SecretKey` mascherato, nessuna traccia in log, cronologia o sessione. |
| 2026-10-16 | Claude Code | **Decisioni del proprietario del 2026-10-16:** scelta minore 1 modificata (servizio del Portachiavi `dev.pages.astrotwo.ai`, identificativo inverso del progetto con suffisso `.ai`; account = profilo del `30`), 2 e 3 confermate. **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-16. |
| 2026-10-16 | Claude Code | Verifiche prima del codice (§13) superate: licenze, Portachiavi di login non sincronizzabile, forzatura necessaria (variabile d'ambiente), backend funzionante in un'app PyInstaller. Resta per il 60 il permesso con l'app firmata. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | §3.1: i profili predefiniti del `30` §3.1.1 (decisione del proprietario del 2026-10-17) usano lo stesso identificativo e quindi una chiave ciascuno; nessuna regola nuova. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **Codice della parte 2 della v1:** `src/astrotwo/ai/keychain_keys.py` (`KeychainStore` con il solo backend macOS di `keyring` creato direttamente, `SecretKey` opaco, `KeychainError`, `SERVICE_NAME`; messaggi d'errore ripuliti da ogni parte della chiave) e `tests/ai/test_keychain_keys.py` (T1–T7 con l'API Security simulata in memoria, 8 test; T8 con il marcatore `keychain`, aggiunto a `pyproject.toml` ed escluso di default). **T8 sul Portachiavi reale non ancora eseguito:** al primo tentativo il test è rimasto in attesa (probabile finestra di permesso di macOS), fermato senza lasciare elementi; da eseguire a mano dal proprietario. Stato `approvato` invariato. |
