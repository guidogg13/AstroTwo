# 04-cache.md — cache condivisa dei dati scaricati (A7)

**Stato:** approvato

## 2. Scopo

Conservare in un unico posto, con limite di spazio, origine e data, tutti i
dati scaricati dalla rete dai moduli del livello 1, così che si possano
riusare senza rete e che ogni dato mostrato all'utente dichiari da dove
viene e quando è stato preso.

## 3. Cosa fa

- **Una sola cache per tutta l'app** (decisione A7 di `01-architettura.md`,
  proposta AM1 accettata dal proprietario il 2026-10-09), nella cartella
  standard delle cache di macOS: **`~/Library/Caches/AstroTwo/`**. La
  cartella si può cambiare solo per i test (cartella temporanea) e per
  un'impostazione esplicita dell'utente; mai implicitamente.
- **Due supporti, come prevede A7:**
  - un database **SQLite** (`cache.sqlite`) per i dati tabellari:
    risoluzioni dei nomi (`10`, tabella separata, D10-3), interrogazioni ai
    cataloghi (`13`) e risultati delle query VO (`14`); ogni modulo ha **le
    proprie tabelle**, con schema non condiviso;
  - **file su disco** (sottocartella `files/`, una sottocartella per modulo)
    per immagini e tagli FITS (`11`), riquadri HiPS (`12`) e MOC in formato
    FITS IVOA (`16`, D16-2).
- **Chiavi e proprietà:** la chiave di una voce è unica in tutta la cache
  e appartiene al modulo che l'ha scritta; un altro modulo che la legge o
  la riscrive riceve `CACHE_FORBIDDEN`. I dati in byte si salvano come file
  (`put`/`get`), le righe nelle tabelle SQLite del modulo (`table`), con le
  colonne dichiarate dal modulo (tipi SQLite `TEXT`, `REAL`, `INTEGER`,
  `BLOB`); la dimensione di una riga è la somma dei byte dei suoi valori
  (testo in UTF-8, numeri 8 byte).
- **Origine e data di ogni dato:** ogni voce (riga SQLite o file) ha un
  registro con: modulo proprietario, chiave della richiesta, **origine**
  (servizio, URL o identificativo del servizio interrogato), **data e ora di
  scaricamento** (UTC, ISO 8601 nel registro e in interfaccia, come da DC1 di
  `02-convenzioni.md`), dimensione in byte, data dell'ultimo uso. Un dato
  servito dalla cache restituisce sempre origine e data insieme al valore:
  chi lo mostra (UI) o lo registra (`24`) le riporta.
- **Limite di spazio unico (CA2):** **un solo limite di 5 GB per tutta la
  cache** (D11-3 di `11-core-immagini-fits.md`), configurabile dall'utente;
  **5 GB = 5 × 10⁹ byte** (GB decimale, come nel Finder di macOS). **Il
  totale è la somma delle dimensioni dei dati di tutte le voci** registrate
  (byte dei file + byte delle righe SQLite dei moduli), di tutti i moduli;
  l'overhead fisso del database (registro, indici, pagine libere) non si
  conta (decisione del proprietario del 2026-10-09: misura deterministica,
  indipendente dal funzionamento interno di SQLite). Quando una scrittura supererebbe il limite si eliminano
  le voci **usate meno di recente** (LRU) fino a rientrare; ogni
  eliminazione è registrata nel log. Se una sola voce supera il limite, non
  si scrive e si segnala `CACHE_FULL`.
- **Timeout dichiarati:** ogni operazione di rete dei moduli che usano la
  cache ha un timeout di connessione e uno di lettura **dichiarati**:
  **10 s per la connessione e 60 s per la lettura, configurabili** (CA1),
  riportati nel messaggio d'errore `NET_TIMEOUT`. La cache non
  fa richieste di rete da sé: riceve dai moduli i dati scaricati e li
  restituisce; i timeout sono qui perché siano gli stessi per tutti.
- **Database corrotto:** la cache si ricrea vuota (database e file); i file
  rimasti senza registro non si possono servire, perché non hanno
  provenienza. **Cartella non scrivibile:** la cache resta disattivata
  (scritture ignorate, letture assenti), sempre con avviso.
- **Uso senza rete:** se la rete non risponde, il modulo chiamante può
  chiedere alla cache l'ultima copia disponibile; la risposta dichiara che
  il dato viene dalla cache, con origine e data, mai come se fosse fresco.
- **Nessuna cache propria nei moduli (CA4):** i moduli 10–14 e 16 non hanno
  classi di cache proprie; tutti usano `SharedCache` direttamente.
- **Pulizia su richiesta:** svuotare tutta la cache o la parte di un modulo
  (comando registrato, regola d'oro n. 6).
- **Accesso da più thread e da più processi (D04, decisa dal proprietario
  il 2026-10-16, opzioni a + b):** ogni istanza di `SharedCache` ha la
  propria connessione SQLite (una per thread, o una per operazione come
  fanno i moduli che non ricevono una cache); le scritture usano
  transazioni `BEGIN IMMEDIATE` e la libreria aspetta il lucchetto del
  database fino al suo timeout (5 s, quello di `sqlite3`). I **file orfani**
  (file temporanei `.tmp-*` e file senza voce nel registro, che non hanno
  provenienza e non si possono servire) si eliminano con due regole:
  - **(a) solo se più vecchi di una soglia:** di default **10 minuti**
    (600 s), configurabile con il parametro `orphan_min_age` di
    `SharedCache` (secondi, > 0); la soglia usata si scrive nel log a ogni
    eliminazione. Un file più giovane può essere la scrittura in corso di
    un altro thread o processo (file temporaneo, o file già rinominato con
    la voce del registro non ancora confermata) e non si tocca;
  - **(b) una sola volta per processo**, alla **prima apertura** di
    `SharedCache` per quella cartella (nell'app la cartella è una sola, quindi
    una volta per processo; i test, che usano cartelle diverse, la
    ripetono per ciascuna). Le aperture successive nello stesso processo
    non puliscono.
  Motivo: con la pulizia a ogni apertura e senza soglia, una nuova istanza
  cancellava il file temporaneo di una scrittura in corso in un altro thread
  (`FileNotFoundError` in `put`: 5 errori su 1200 operazioni con un'istanza
  per thread, 250 con un'istanza per operazione, prova del 2026-10-16).

## 4. Cosa NON fa

- Non scarica nulla e non conosce i protocolli: le richieste di rete restano
  nei moduli `10`, `11`, `12`, `13`, `14`, `16`.
- Non interpreta i dati che conserva (non legge FITS, VOTable, MOC): li
  salva e li restituisce come byte o righe.
- Non conserva le chiavi API né altri segreti (regola d'oro n. 5): restano
  solo nel Portachiavi di macOS (`31-ia-chiavi-portachiavi.md`).
- Non conserva la sessione dell'utente, i tag o i segnalibri (`24`, `40`).
- Non è un archivio permanente: i dati possono essere eliminati in qualsiasi
  momento dal limite di spazio o dal sistema.
- Non mostra nulla: le impostazioni (limite, svuotamento) le disegna
  `40-ui-finestra-principale.md`.

## 5. Livello e dipendenze

- **Livello:** 1 (file generale; è un servizio del nucleo e non dipende da
  livelli superiori).
- **Dipende da:** nessuno.
- **Usato da:** `10-core-coordinate-wcs.md` (risoluzione dei nomi, D10-3),
  `11-core-immagini-fits.md` (immagini e tagli), `12-core-hips.md` (riquadri
  HiPS), `13-core-cataloghi.md` (interrogazioni ai cataloghi),
  `14-core-protocolli-vo.md` (query VO), `16-core-moc.md` (MOC),
  `18-core-calcolatrici.md` (tabella IERS aggiornata su richiesta con
  `update_iers_table`, file nella sottocartella del modulo `18`; aggiunto il
  2026-10-13), `19-core-dati-planetari.md` (prodotti PDS4 da URL, D19-9,
  tramite le risposte del 14);
  impostazioni in `40-ui-finestra-principale.md`; origine e data riportate da
  `24-analisi-pipeline-riproducibili.md`. Tutti questi moduli rimandano a
  questo file (collegamento completato il 2026-10-09).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `module` | stringa | identificativo del modulo (`"10"`, `"11"`, …) | proprietario della voce |
| in | `key` | stringa | chiave canonica della richiesta | costruita dal modulo chiamante |
| in | dato | byte (file) o righe (SQLite) | — | come scaricato |
| in | `origin` | stringa | servizio, URL o identificativo | obbligatoria |
| in | `retrieved_at` | data e ora | UTC, ISO 8601 | obbligatoria |
| in | `limit` | intero | byte; default 5 GB | configurabile |
| out | dato + provenienza | struttura | dato, `origin`, `retrieved_at`, `from_cache = vero` | mai un dato senza provenienza |
| out | stato | struttura | spazio usato e limite in byte, per modulo | per l'interfaccia |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole, nessun codice:

- **`SharedCache`** (classe) — apre (o crea) la cache nella cartella
  indicata, `~/Library/Caches/AstroTwo/` di default; parametro
  `orphan_min_age` (secondi, default 600, §3); metodi principali:
  - **`put(module, key, data, origin, retrieved_at)`** — salva una voce e la
    sua provenienza; applica il limite (LRU) prima di scrivere;
  - **`get(module, key)`** — restituisce dato + `origin` + `retrieved_at`
    oppure "assente"; aggiorna la data dell'ultimo uso;
  - **`table(module, name)`** — dà a un modulo accesso alla propria tabella
    SQLite (schema definito dal modulo), con lo stesso registro di
    provenienza;
  - **`usage()`** — spazio usato per modulo e totale, limite;
  - **`clear(module=None)`** — svuota tutto o la parte di un modulo.
- **`NETWORK_TIMEOUTS`** — timeout di connessione (**10 s**) e di lettura
  (**60 s**) usati da tutti i moduli di rete del livello 1, configurabili
  (CA1).
- **Posizione del codice (CA3):** `src/astrotwo/core/cache.py`, test in
  `tests/core/`.
- **`CachedValue`** (struttura) — dato + `origin` + `retrieved_at` +
  `from_cache`.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `sqlite3` (libreria standard Python) | database dei dati tabellari | scelta A7; nessuna dipendenza esterna |
| `pathlib` / `os` (libreria standard) | file su disco, spazio occupato | nessuna dipendenza esterna |
| Linee guida Apple sulle cartelle (`~/Library/Caches`) | posizione della cache | il sistema può liberare quello spazio; non va nel backup di Time Machine |
| ISO 8601 (UTC) | data di scaricamento | DC1 di `02-convenzioni.md` |

## 9. Regole e vincoli

- **Nessun dato senza provenienza:** `origin` e `retrieved_at` sono
  obbligatori in scrittura e sempre restituiti in lettura (vincolo A7).
- **Limite sempre rispettato:** il totale (somma dei dati delle voci, §3)
  non supera mai il limite dopo una scrittura riuscita.
- **Separazione per modulo:** un modulo legge e scrive solo le proprie voci;
  nessuno schema SQLite condiviso tra moduli (D10-3).
- **Nessun segreto in cache** (regola d'oro n. 5).
- **Riproducibilità:** chi registra un'operazione (`24`) registra anche se
  il dato veniva dalla cache, con origine e data.
- **Scritture sicure:** una voce si scrive per intero o non si scrive (file
  temporaneo poi rinominato; transazione SQLite), così che un arresto
  improvviso non lasci voci a metà.
- **Più thread e più processi:** nessuna voce parziale, limite rispettato
  e nessun errore con letture e scritture concorrenti (§3, D04).
- **Prestazioni:** la lettura di una voce presente non deve richiedere rete;
  valori misurabili in `61-strategia-test.md`.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Cartella non scrivibile o database corrotto | la cache viene ricreata o ignorata con avviso; il dato si rilegge dalla sorgente | `CACHE_UNAVAILABLE` |
| Scrittura oltre il limite | eliminazione LRU registrata; se una sola voce supera il limite, nessuna scrittura | `CACHE_FULL` |
| Scrittura senza `origin` o `retrieved_at` | rifiuto | `CACHE_PROVENANCE_MISSING` |
| Rete assente nel modulo chiamante | il modulo può servire la copia in cache dichiarandola tale; se manca, errore del modulo | `NET_TIMEOUT` (del modulo) |
| Voce richiesta da un modulo diverso dal proprietario | rifiuto | `CACHE_FORBIDDEN` |
| File orfano più giovane della soglia (scrittura in corso altrove) | non eliminato | — |
| `orphan_min_age` non positivo | rifiuto | `ValueError` |

### 10.1 Messaggi con codice e `params` (D40-3, sprint 8e, 2026-10-25)

`CacheError(code, message, params=...)` e `CacheWarning(code, message, params)` portano `params`; il testo italiano
resta invariato. Il modulo non importa il catalogo dei messaggi. `detail` = testo di SQLite o del sistema, `key` =
chiave scelta dal modulo chiamante (spesso un indirizzo): testi esterni (`ext`).

| Codice | `reason` | Parametri |
|---|---|---|
| `CACHE_UNAVAILABLE` (avviso) | `corrupt`, `unusable`, `recreate_failed` | `detail` (ext) |
| | `folder_unwritable` | `folder` (ext), `detail` (ext) |
| | `entry_not_saved`, `row_not_saved` | — |
| `CACHE_FULL` | — | `key` (ext), `size` (int), `limit` (int) |
| `CACHE_PROVENANCE_MISSING` | `origin`, `retrieved_at`, `no_timezone` | — |
| `CACHE_FORBIDDEN` | `other_module` | `key` (ext), `owner`, `module` |
| | `file_is_row`, `wrong_table` | `key` (ext), `table` |

## 11. Esposizione all'IA

Non applicabile: la cache è un servizio interno; l'IA vede solo origine e
data dei dati restituiti dagli strumenti dei moduli che la usano.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Provenienza | scrivere e rileggere una voce con origine e data | stessi byte, stessa origine, stessa data, `from_cache` vero | confronto diretto |
| T2 | Provenienza obbligatoria | scrivere senza `origin` | `CACHE_PROVENANCE_MISSING` | test di unità |
| T3 | Limite LRU | limite piccolo (es. 10 kB), scrivere voci oltre il limite usandone alcune | eliminate le voci usate meno di recente; totale ≤ limite | somma delle dimensioni dei file nella cartella di prova e delle righe registrate |
| T4 | Voce troppo grande | una voce più grande del limite | `CACHE_FULL`, nessuna scrittura | test di unità |
| T5 | Separazione per modulo | il modulo `"13"` chiede una voce del `"10"` | `CACHE_FORBIDDEN` | test di unità |
| T6 | Database corrotto | sovrascrivere `cache.sqlite` con byte casuali e riaprire | `CACHE_UNAVAILABLE` con avviso, cache ricreata | test di unità |
| T7 | Scrittura interrotta | simulare un errore a metà scrittura | nessuna voce parziale leggibile | test di unità |
| T8 | Posizione | aprire senza cartella esplicita | percorso = `~/Library/Caches/AstroTwo/` (i test usano sempre una cartella temporanea) | test di unità con cartella home simulata |
| T9 | Più thread (D04; è anche il T17 del `05`) | 8 thread con letture e scritture concorrenti di file e righe, sia un'istanza per thread sia un'istanza per operazione, almeno 1200 operazioni per modo | 0 errori; nessuna voce parziale (contenuto letto sempre intero); totale ≤ limite; nessuna voce del registro senza file | test di unità con cartella temporanea |
| T10 | Due processi (D04) | due processi che usano insieme la stessa cartella con lo stesso carico | 0 errori in entrambi; nessuna voce parziale; totale ≤ limite | test con `multiprocessing` |
| T11 | Soglia degli orfani (D04) | un `.tmp-*` e un file senza registro più vecchi della soglia, gli stessi più giovani; prima apertura nel processo; poi un nuovo orfano vecchio e una seconda apertura | alla prima apertura eliminati solo i vecchi, soglia nel log; alla seconda apertura nessuna pulizia | test di unità (date dei file impostate con `os.utime`) |

## 13. Decisioni aperte

Nessuna decisione aperta. Decise dal proprietario il 2026-10-09:

- **CA1 — Timeout di rete: DECISA.** 10 s per la connessione, 60 s per la
  lettura, configurabili; comuni ai moduli 10–14 e 16.
- **CA2 — Limite: DECISA.** Un solo limite di 5 GB per tutta la cache
  (database e file), configurabile.
- **CA3 — Posizione del codice: DECISA.** `src/astrotwo/core/cache.py`.
- **CA4 — Cache nei moduli: DECISA.** Nessuna cache propria nei moduli:
  `ImageCache` (`11`), `HiPSCache` (`12`), `CatalogCache` (`13`),
  `QueryCache` (`14`) e la cache dei MOC (`16`) sono tolte dalle specifiche;
  tutti usano la cache comune `SharedCache`.
- **D04 — Cache da più thread e da più processi: DECISA il 2026-10-16**
  (decisione del proprietario, opzioni a + b): orfani eliminati solo se più
  vecchi di 10 minuti (configurabile, dichiarata) e una sola volta per
  processo alla prima apertura. Applicata in §3, §7, §9, §10, §12
  (T9–T11).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-09 | Claude Code | Creazione del file (stato: bozza) su decisione del proprietario (AM1 accettata il 2026-10-09, da D10-8 punto 2): cache A7 condivisa in `~/Library/Caches/AstroTwo/`, limite 5 GB (D11-3), timeout dichiarati, origine e data di ogni dato; usata da 10–14 e 16. Decisioni aperte CA1–CA4. In attesa dell'approvazione del proprietario. |
| 2026-10-09 | Claude Code | **Decisioni del proprietario CA1–CA4 applicate:** timeout 10 s/60 s configurabili (§3, §7), un solo limite di 5 GB (§3), codice in `src/astrotwo/core/cache.py` (§7), nessuna cache propria nei moduli (§3, §13). Collegati 10, 11, 12, 13, 14, 16 (§5). **Stato portato ad `approvato`** su decisione del proprietario. |
| 2026-10-09 | Claude Code | **Precisazioni del proprietario prima del codice:** il totale del limite è la somma dei dati delle voci (overhead di SQLite escluso); 5 GB = 5 × 10⁹ byte; descritti chiavi uniche con modulo proprietario, righe con colonne dichiarate dal modulo, ricreazione della cache corrotta e cache disattivata se la cartella non è scrivibile (§3, §9, §12-T3). Stato `approvato` invariato. |
| 2026-10-09 | Claude Code | **Codice scritto:** `src/astrotwo/core/cache.py` (`SharedCache`, `CacheTable`, `CachedValue`, `CacheUsage`, `NETWORK_TIMEOUTS`) con i test T1–T8 di §12 e casi aggiuntivi in `tests/core/test_cache.py` (18 superati; sempre in cartella temporanea o home simulata). Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **Decisione del proprietario del 2026-10-13** (autorizzazione esplicita a modificare il file approvato): §5 "Usato da" con `18-core-calcolatrici.md` (tabella IERS di `update_iers_table`) e `19-core-dati-planetari.md` (PDS4 da URL, D19-9, attraverso la rete e la cache del 14). Nessun altro cambiamento. Stato `approvato` invariato. |
| 2026-10-16 | Claude Code | **D04 decisa dal proprietario il 2026-10-16** (autorizzazione esplicita a modificare il file approvato): accesso da più thread e da più processi — orfani eliminati solo se più vecchi di `orphan_min_age` (600 s di default, configurabile, nel log) e una sola volta per processo alla prima apertura; motivo: la verifica del 2026-10-16 (5 errori su 1200 operazioni con un'istanza per thread, 250 con un'istanza per operazione); test T9 (è il T17 del 05), T10, T11. Stato `approvato` invariato. |
| 2026-10-16 | Claude Code | **Codice di D04:** `SharedCache(orphan_min_age=600)` in `src/astrotwo/core/cache.py` (orfani eliminati solo se più vecchi della soglia, nel log; pulizia una volta per processo e per cartella); test T9 (8 thread, istanza per thread e per operazione, 1200 operazioni, 0 errori), T10 (due processi, 400 operazioni ciascuno, 0 errori), T11 (soglia e una sola pulizia per processo) in `tests/core/test_cache.py`, falliti prima della correzione e superati dopo. Stato `approvato` invariato. |
| 2026-10-25 | Claude Code | **Sprint 8e (D40-3):** `CacheError` e `CacheWarning` portano `params`; nuova §10.1 con la tabella di codici, ragioni e parametri (`CACHE_UNAVAILABLE`, `CACHE_FULL`, `CACHE_PROVENANCE_MISSING`, `CACHE_FORBIDDEN`) scritta prima del codice; voci del catalogo en/it e test `tests/core/test_messages_cache.py`. Il modulo non importa il catalogo; testo italiano invariato. Stato `approvato` invariato. |
