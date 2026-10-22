# 32-ia-registro-strumenti.md — registro degli strumenti esposti all'IA

**Stato:** approvato

## 2. Scopo

Decidere quali comandi del `05` l'IA può chiedere di eseguire, descriverli
al modello con lo schema del `05`, validarli ed eseguirli esattamente come
quelli dell'utente e restituire al modello risultati ridotti e marcati,
così che ogni numero della risposta venga da un comando registrato.

## 3. Cosa fa

Origine: `01-architettura.md` §7 (gli strumenti per l'IA si dichiarano qui,
non nel §11 dei moduli; decisione del proprietario del 2026-10-10, da
D11-9); `05` §3.5 (schema JSON dei comandi); proposta della fase 1 sull'IA
nella v1, **approvata dal proprietario il 2026-10-16** (punto 3: elenco
esplicito, schema da `export_schema`, nomi tradotti, validazione del `05`,
stessa coda del `40` con `requested_by = ai`, risultati entro 50 righe e
20 kB).

### 3.1 Principio

- **Uno strumento = un comando del `05`.** Il 32 non definisce funzioni
  proprie, non calcola nulla e non ridefinisce parametri: prende nome,
  descrizioni e schema da `export_schema` del `05`.
- **Elenco esplicito e chiuso** (§3.2): un comando che non è nell'elenco
  non esiste per l'IA, anche se è registrato nel `05`. Un comando nuovo del
  `05` non diventa strumento finché questo file non lo aggiunge.

### 3.2 Comandi esposti nella v1

Colonna **Conferma** (regole in §3.5): `sì` = l'utente conferma prima
dell'esecuzione; `no` = eseguito senza conferma (salvo dopo un testo
esterno, §3.6).

| Strumento | Comando del `05` | Classe e indicatori | Conferma | Note |
|---|---|---|---|---|
| `view__go_to` | `view.go_to` | session; vista; rete (nomi) | sì (rete) | testo con nome o coordinate |
| `view__set_center` | `view.set_center` | session; vista | no | |
| `view__set_zoom` | `view.set_zoom` | session; vista | no | |
| `view__set_grid` | `view.set_grid` | session; vista | no | |
| `view__set_overlays` | `view.set_overlays` | session; vista | no | nord ed est e barra di scala; aggiunto il 2026-10-20 (decisione del proprietario) |
| `hips__set_survey` | `hips.set_survey` | session; rete | sì (rete) | identificativo o URL |
| `catalog__load_region` | `catalog.load_region` | session; rete, lungo | sì (rete, lungo) | la scheda mostra `max_rows` |
| `catalog__select` | `catalog.select` | session | no | selezione: non cambia il livello |
| `catalog__set_style` | `catalog.set_style` | session | sì (modifica un livello) | |
| `measure__distance` | `measure.distance` | session | no | |
| `calc__evaluate_expression`, `calc__convert_units`, `calc__convert_pixel_value`, `calc__calculate_coordinates`, `calc__convert_time` | `calc.*` (18) | session | no | **ogni numero derivato** si ottiene da qui (§3.7) |
| `layer__set_visible` | `layer.set_visible` | session | sì (modifica un livello) | |
| `layer__set_opacity` | `layer.set_opacity` | session | sì (modifica un livello) | |
| `coords__resolve_name` | `coords.resolve_name` (nuovo, `05`) | session; sola lettura; rete | no (sola lettura) | posizione ICRS con fonte ed epoca |
| `catalog__search` | `catalog.search` (nuovo, `05`) | session; sola lettura | no | grammatica chiusa del 13 (`search`, D13-1); **al posto del 33 nella v1** |
| `catalog__describe` | `catalog.describe` (nuovo, `05`) | session; sola lettura | no | colonne, unità, UCD, descrizioni, righe, provenienza |
| `catalog__rows` | `catalog.rows` (nuovo, `05`) | session; sola lettura | no | **al più 50 righe** per chiamata |
| `layer__list` | `layer.list` (nuovo, `05`) | session; sola lettura | no | livelli con tipo, nome, visibilità, opacità, ordine, sorgente |

### 3.3 Comandi non esposti

| Comando o gruppo | Perché |
|---|---|
| classi `passive` (`cursor.read`, `simbad.pointer`) | letture del mouse, non richieste dell'utente |
| classe `application` (`prefs.set`, `cache.clear`, `ui.*`, `view.export_png`) | preferenze, cache, pannelli e file PNG sono scelte dell'utente, non dell'assistente |
| apertura di file da disco (`image.open`, `catalog.open_file`, `moc.open`) | l'IA lavora sui livelli che l'utente ha già aperto: non sceglie file sul disco |
| sessioni (salva, apri) | non sono comandi (`05` §3.4) |
| `layer.remove`, `layer.move` | rimuovere o riordinare livelli dell'utente resta all'utente nella v1 |
| `image.set_display`, `catalog.set_columns`, `table.sort`, `view.set_coordinate_display` | non servono all'assistente nella v1; si possono aggiungere con una modifica di questo file |
| chiavi del `31` | mai visibili all'IA |

**Strumenti annotati per il 32 dai moduli 11, 13 e 14** (`panoramica.md`
§4, 2026-10-10: `load_image_info`, `get_image_statistics`,
`image_operation`, `cutout`, `describe_table`, `search`,
`get_column_statistics`, `propagate`, `cone_search`, `tap_query`,
`validate_adql`, `describe_services`, `ssa_search`, `ssa_load`): nella v1
entrano solo `describe_table` (come `catalog.describe`) e `search` (come
`catalog.search`); gli altri **non sono comandi del `05`** e restano fuori
dalla v1. Entreranno quando diventano comandi del `05` (regola §3.1); per
`tap_query` e `validate_adql` dopo il `33`.

### 3.4 Dallo schema del `05` allo strumento del provider

1. **Nome:** il nome del comando con `.` sostituito da `__`
   (`view.go_to` → `view__go_to`), perché i provider accettano solo
   lettere, cifre, `_` e `-` (al più 64 caratteri). La corrispondenza
   inversa si fa con la **tabella** di §3.2, non con una sostituzione di
   testo; all'avvio si controlla che i nomi siano unici e validi
   (`TOOL_NAME_INVALID` altrimenti, errore di programmazione).
2. **Descrizione:** la descrizione inglese del `05`, più una riga fissa
   sugli indicatori ("requires user confirmation", "read-only", "uses the
   network").
3. **Parametri:** lo schema JSON del `05` (draft 2020-12) ridotto al
   sottoinsieme accettato da entrambi i provider: `type`, `properties`,
   `required`, `enum`, `minimum`, `maximum`, `items`, `description`,
   `default`. Le annotazioni di **unità e grandezza fisica** del `05`
   passano nel testo `description` del parametro (es. "angle; value with
   unit, e.g. {\"value\": 10, \"unit\": \"arcmin\"}"). Un `quantity` resta
   un oggetto con `value` (numero) e `unit` (stringa): **l'IA non sceglie
   numeri senza unità**. Modalità rigida dei provider (`strict`) non usata
   (scelta minore 1). **Da verificare prima del codice:** che entrambi i
   provider accettino questo sottoinsieme senza errori.
   **Riduzione delle parole dello schema del `05` fuori dal sottoinsieme**
   (sprint 6a): `anyOf` con `null` → `type` con `"null"` aggiunto (o `null`
   nell'`enum`); altri `anyOf` (tempi) → `type` con l'unione dei tipi, le
   `properties` della forma a oggetto e le forme scritte nella
   descrizione; `const` → `enum` di un valore; `exclusiveMinimum` →
   `minimum` più "(exclusive)" nella descrizione; `pattern`, `maxItems`,
   tipi di livello ammessi e regole (`x-*`) → testo nella descrizione;
   `additionalProperties` tolto (la validazione resta del `05`).
4. Lo schema si ricalcola all'avvio dell'assistente da `export_schema`:
   nessuna copia scritta a mano.

### 3.5 Chiamata di uno strumento

1. Il `35` riceve dal `30` una `ToolCallRequest` (nome, argomenti JSON).
2. **Nome sconosciuto o non esposto** → risultato d'errore al modello
   (`TOOL_NOT_EXPOSED`), nessuna esecuzione.
3. **Argomenti:** JSON illeggibile → `TOOL_ARGUMENTS_INVALID`; altrimenti
   il comando si costruisce e si **valida con il `05`** esattamente come
   quelli dell'utente (`COMMAND_PARAMETER_INVALID`, `LAYER_UNKNOWN`). Un
   errore di validazione **torna al modello come risultato d'errore** (con
   codice, testo e parametro), così può correggersi; non entra in
   cronologia perché il comando non è stato eseguito.
4. **Conferma** (regola decisa il 2026-10-16): servono la conferma
   dell'utente i comandi con indicatore `network` o `long` e quelli che
   **modificano un livello esistente**; **i comandi di sola lettura non
   chiedono conferma** (anche `coords.resolve_name`, che usa la rete:
   interpretazione da confermare, §13). La regola è scritta nel `05` come
   indicatore `confirm` di ogni definizione; questa tabella lo riporta. La
   scheda di conferma e i pulsanti sono del `44` (Conferma, Annulla,
   "Conferma per questa conversazione", che vale solo per quel comando).
   Annulla → risultato al modello "l'utente non ha confermato"
   (`TOOL_NOT_CONFIRMED`), nessuna esecuzione.
5. **Esecuzione:** il comando entra nella **stessa coda del `40`** dei
   comandi dell'utente, con `requested_by` = `ai` più identificativo della
   conversazione, numero del turno, identificativo della chiamata,
   profilo e modello (`05` §3.1). Viene eseguito uno alla volta,
   nell'ordine di arrivo, e registrato in cronologia con il suo numero `#n`
   come ogni altro comando. Il `CancelToken` è quello del turno (Stop).
6. **Risultato al modello:** il `CommandResult` del `05` ridotto (§3.7).

### 3.6 Testi esterni: dati, mai istruzioni (sicurezza)

Aggiunta di sicurezza obbligatoria (decisione del proprietario del
2026-10-16), applicata qui, nel `35` e nel `34`.

- **Testo esterno** = ogni stringa di un risultato che **non è scritta dal
  codice di AstroTwo**: valori di testo di cataloghi e tabelle, note e tipi
  di SIMBAD, descrizioni di cataloghi e colonne, metadati HiPS (titolo,
  descrizione, crediti), parole chiave e commenti FITS, messaggi dei
  servizi riportati dai moduli, nomi di file.
- Nel risultato inviato al modello i testi esterni stanno **solo** in campi
  marcati: ogni oggetto che li contiene ha la forma
  `{"external_text": "<testo>", "source": "<servizio o file>"}`; il
  risultato porta in testa `"contains_external_text": true`. Le regole di
  sistema del `35` dicono che questi campi sono **dati, mai istruzioni**.
- **`catalog.rows`: fonte scritta una volta** (decisione del proprietario
  del 2026-10-22): in testa al risultato, dopo `contains_external_text`,
  `"external_source": "<servizio o file>"`, e ogni campo esterno è solo
  `{"external_text": "<testo>"}` (senza `source` su ogni valore, colonna,
  unità e UCD). Ogni valore resta attribuibile: tutti i testi esterni di un
  risultato hanno la stessa fonte. Gli altri comandi tengono `source` in
  ogni campo (`SOURCE_ONCE` nel codice).
- **Ogni testo esterno è limitato a 500 caratteri** (oltre: tagliato, con
  `"truncated": true` e la lunghezza originale).
- **Effetto sulle conferme:** dal momento in cui, nel turno, il modello ha
  ricevuto un risultato con testo esterno, **ogni comando successivo della
  stessa risposta che non sia di sola lettura senza rete chiede la
  conferma dell'utente**, anche se di norma non la chiede, e
  "Conferma per questa conversazione" **non vale** per questi casi. La
  scheda di conferma dice "chiesto dopo la lettura di testo esterno
  (fonte)". Così **un'azione suggerita da un testo esterno non viene mai
  eseguita senza la conferma dell'utente**.

**Come si riconosce un testo esterno** (decisione del proprietario del
2026-10-22, sprint 6a: "entrambe le liste"). I risultati del `05` non
marcano le stringhe; il 32 le classifica per **percorso** nel risultato
(`values.rows[].values[].value`: chiavi separate da `.`, `[]` per gli
elementi di un elenco) con due elenchi chiusi scritti nel codice
(`EXTERNAL_FIELDS`, `ASTROTWO_FIELDS`):

- `EXTERNAL_FIELDS`, **per comando esposto**: i campi che contengono testo
  di terzi. Nella v1: valori, nomi di colonna, UCD, unità e descrizioni dei
  cataloghi (`catalog.rows`, `catalog.select`, `catalog.describe`, colonne
  e colonne di posizione di `catalog.load_region`, epoca ed equinozio letti
  dal file o dal servizio); titolo, identificativo, frame e formati dei
  tile e unità `BUNIT` di un survey (`hips.set_survey`); identificativo
  principale e bibcode di SIMBAD (`coords.resolve_name`, `view.go_to`);
  nomi dei livelli, colonne e unità in `layer.list`.
- `ASTROTWO_FIELDS`, per comando o comuni: i campi scritti dal codice di
  AstroTwo (identificativi `L<n>`, frame normalizzati, unità dei valori
  calcolati, metodi, note dei moduli, date ISO, URL dei servizi
  configurati, parametri ripetuti dal comando, tutti i campi delle
  calcolatrici).
- **Una stringa che non è in nessuno dei due elenchi è testo esterno**
  (nel dubbio, esterno) e un test (`T12`) esegue ogni comando esposto su
  dati sintetici e **fallisce** finché ogni sua stringa non è classificata.
- **Avvisi ed errori:** il codice è sempre di AstroTwo; il testo è di
  AstroTwo solo per l'elenco chiuso dei codici scritti dal `05` e dai
  moduli senza testo di terzi (`ASTROTWO_MESSAGE_CODES`), altrimenti è
  testo esterno (un servizio può scrivere nel messaggio d'errore).
- **Fonte** (`source`) del testo esterno: l'origine dei dati del risultato
  (provenienza), altrimenti la sorgente del livello del comando, con il
  solo nome del file (§3.7).

### 3.7 Risultati ridotti per il modello

Il modello riceve un JSON con:

- `command`: numero `#n` della cronologia, nome, parametri completi come
  registrati (default risolti, unità), esito;
- `values`: valori del modulo, **ogni numero con la sua unità**, scritto
  con la rappresentazione più breve che si rilegge identica (`repr` di
  Python, come nella sessione del `05`): **nessun arrotondamento**, così il
  `34` può confrontare alla precisione scritta dal modello; frame, epoca,
  convenzione dei pixel dove pertinenti;
- `provenance`: origine e data dei dati di rete o della cache, "dalla cache
  sì/no", libreria che ha calcolato (modulo · libreria);
- `warnings`, `error`: codice e testo del modulo, invariati;
- `layers`: livelli prodotti (`L<n>`).

**Limiti fissi** (decisi il 2026-10-16):

- **al più 50 righe** di una tabella o 50 elementi di un elenco; oltre,
  il risultato porta il totale e `"truncated": true` (per vedere altre righe
  il modello chiama `catalog.rows` con un altro intervallo);
- **al più 20 kB** di JSON in UTF-8: se il risultato è più grande si
  tolgono prima righe ed elementi in coda, poi i testi esterni, mai i
  valori numerici restanti né le loro unità, e si dichiara cosa è stato
  tolto. **Nessun numero viene accorciato** nelle sue cifre.
- **Nomi dei file senza cartelle** (privacy): un parametro o un valore di
  tipo `file` diventa il solo nome del file (es. `pleiadi.fits`), senza
  percorso né SHA-256. In pratica (sprint 6a): ogni percorso assoluto
  (`/…`, `~/…`, `file://…`) in qualunque stringa del risultato o dei
  parametri diventa il suo ultimo elemento, e le chiavi `sha256` non si
  inviano.
- **Forma degli elenchi accorciati** (sprint 6a): gli elenchi restano al
  loro posto con i primi elementi; l'elenco dei tagli sta in testa al
  risultato, `"truncated": [{"path", "total", "kept"}]`; i testi esterni
  tolti per il limite di 20 kB diventano `{"external_text": null,
  "removed": true, "source"}` (senza `source` in `catalog.rows`, §3.6).
- La riduzione riguarda **solo ciò che vede il modello**: la cronologia e
  la sessione hanno il risultato completo del `05`.

### 3.8 Nuovi comandi di sola lettura (definiti nel `05`)

Aggiunti al `05` il 2026-10-16 per l'assistente; usabili anche
dall'interfaccia. Funzioni chiamate e parametri sono nel `05` §7:
`coords.resolve_name` (10 `resolve_name`), `catalog.search` (13 `search`:
numero delle righe che soddisfano l'espressione e i primi 50 indici, senza
cambiare la selezione), `catalog.describe` (metadati della tabella del 13),
`catalog.rows` (righe con `record_view` del 13, al più 50), `layer.list`
(stato dello spazio di lavoro del `05`).

## 4. Cosa NON fa

- Non calcola nulla: i numeri vengono dai moduli attraverso il `05`.
- Non definisce strumenti che non sono comandi del `05`.
- Non espone apertura di file, sessioni, preferenze, cache, rimozione di
  livelli né chiavi.
- Non esegue comandi fuori dalla coda del `40` né scavalca la validazione
  del `05`.
- Non decide il dialogo con il modello (`35`) né verifica i numeri della
  risposta (`34`).
- Non scrive ADQL (il `33` è rimandato).

## 5. Livello e dipendenze

- **Livello:** 3 (IA); usa solo comandi del livello 1 nella v1.
- **Dipende da:** `05-comandi-sessione.md` (definizioni, `export_schema`,
  validazione, `requested_by`, indicatore `confirm`), moduli 10, 13, 17, 18
  e 12 attraverso i comandi; `40-ui-finestra-principale.md` (coda dei
  comandi, tramite il `35`).
- **Usato da:** `35-ia-assistente-chat.md` (strumenti e chiamate),
  `34-ia-verifica-risultati.md` (risultati completi e testi esterni
  marcati), `44-ui-pannello-ia.md` (schede dei comandi e conferme).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | definizioni dei comandi | `export_schema` del `05` | JSON Schema 2020-12 con unità come annotazioni | §3.4 |
| in | richiesta di strumento | `ToolCallRequest` del `30` | nome, argomenti JSON | §3.5 |
| in | conferma dell'utente | sì / no / per la conversazione | — | dal `44` |
| out | strumenti per il provider | lista | nome tradotto, descrizione, schema ridotto | §3.4 |
| out | comando | `Command` del `05` con `requested_by = ai` | parametri con unità | in coda del `40` |
| out | risultato per il modello | JSON | ≤ 50 righe, ≤ 20 kB, testi esterni marcati, nomi di file senza cartelle | §3.6, §3.7 |
| out | richiesta di conferma | struttura | comando, parametri con unità, righe massime, motivo | per il `44` |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole. File Python
`src/astrotwo/ai/tool_registry.py`; test in `tests/ai/test_tool_registry.py`.

- **`EXPOSED_COMMANDS`** — la tabella di §3.2 (comando, nome dello
  strumento).
- **`ToolRegistry`** — costruito dal `CommandRegistry` del `05`:
  `tools()` → strumenti per il provider; `command_for(tool_name, arguments,
  requested_by)` → comando validato o errore per il modello;
  `needs_confirmation(command, after_external_text)` → sì/no con il
  motivo; `reduce_result(command_result)` → JSON per il modello (§3.6,
  §3.7).
- **`ToolCallOutcome`** — esito di una chiamata: risultato per il modello,
  numero `#n` (se eseguito), errore, conferma chiesta e risposta.
- **`ToolRegistryError`** — errori di §10.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| JSON Schema draft 2020-12 (dal `05`) | schema degli strumenti | standard pubblico, accettato dai provider con chiamata di strumenti (A5) |
| `json` (libreria standard) | risultati per il modello | nessuna dipendenza nuova |

## 9. Regole e vincoli

- **L'IA non calcola mai** (regola d'oro n. 1): ogni numero che il modello
  riceve viene da un comando eseguito; i numeri derivati (differenze,
  rapporti, conversioni) si chiedono ai comandi `calc.*`.
- **Stessa strada dell'utente:** stessa validazione, stessa coda, stessa
  cronologia, stessa riesecuzione (regola d'oro n. 6). Alla riapertura di
  una sessione i comandi chiesti dall'IA si rieseguono **senza chiamare
  l'IA**.
- **Testi esterni = dati** (§3.6); nessuna azione chiesta da un testo
  esterno senza conferma.
- **Limiti fissi** dei risultati per il modello (§3.7); nessun numero
  accorciato.
- **Privacy:** nomi di file senza cartelle; nessuna chiave, nessun pixel,
  nessun contenuto della cache oltre ai valori del risultato.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Strumento sconosciuto o non esposto | risultato d'errore al modello, nessuna esecuzione | `TOOL_NOT_EXPOSED` |
| Argomenti non JSON | risultato d'errore al modello | `TOOL_ARGUMENTS_INVALID` |
| Parametro non valido, livello inesistente | risultato d'errore del `05` al modello | `COMMAND_PARAMETER_INVALID`, `LAYER_UNKNOWN` |
| L'utente non conferma | risultato al modello, nessuna esecuzione | `TOOL_NOT_CONFIRMED` |
| Errore del modulo durante l'esecuzione | risultato `error` del `05` (codice e testo del modulo) al modello e in cronologia | codice del modulo |
| Comando annullato (Stop) | esito `cancelled` in cronologia; il turno si ferma | `COMMAND_CANCELLED` |
| Risultato oltre 50 righe o 20 kB | ridotto e dichiarato (§3.7) | — |
| Testo esterno oltre 500 caratteri | tagliato e dichiarato | — |
| Nome di strumento non valido o duplicato all'avvio | errore di programmazione, assistente non disponibile | `TOOL_NAME_INVALID` |

## 11. Esposizione all'IA

Questo modulo **è** l'esposizione all'IA: la tabella di §3.2 è l'elenco
completo degli strumenti; per ogni strumento il calcolo è della funzione
del modulo chiamata dal comando del `05` (colonna "Funzioni chiamate" del
`05` §7), mai dell'IA.

## 12. Test di accettazione

In `tests/ai/test_tool_registry.py`, senza rete (servizi simulati) e senza
provider (richieste di strumenti scritte nei test).

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Elenco chiuso | `tools()` | esattamente gli strumenti di §3.2; nessun comando di §3.3 | confronto con la tabella |
| T2 | Nomi tradotti | per ogni strumento, nome → comando → nome | corrispondenza biunivoca; nomi validi per i due provider (regex `^[A-Za-z0-9_-]{1,64}$`) | test di unità |
| T3 | Schema dal `05` | confronto tra `tools()` ed `export_schema()` | stessi parametri, tipi, intervalli, elenchi chiusi; unità nella descrizione; nessun parametro aggiunto | confronto diretto |
| T4 | Validazione come l'utente | raggio senza unità; unità `m`; livello `L9` inesistente; JSON rotto | errori `COMMAND_PARAMETER_INVALID`, `LAYER_UNKNOWN`, `TOOL_ARGUMENTS_INVALID` come risultato al modello; nessun comando in cronologia | test di unità |
| T5 | Stessa coda, `requested_by` | un comando dall'utente e uno dall'IA | eseguiti in ordine di arrivo; il secondo in cronologia con `requested_by = ai`, conversazione, turno, chiamata, profilo, modello | ispezione della cronologia |
| T6 | Conferme | `catalog.load_region`, `layer.set_opacity`, `view.set_center`, `catalog.rows` | conferma chiesta per i primi due, non per gli altri; Annulla → `TOOL_NOT_CONFIRMED`, nessuna esecuzione | test di unità |
| T7 | Testo esterno → conferma | `catalog.rows` con una colonna di testo, poi `view.set_center` nella stessa risposta | `contains_external_text` nel primo risultato; il secondo chiede conferma con il motivo, e "Conferma per questa conversazione" non vale | test di unità |
| T8 | Riduzione | `catalog.rows` su 200 righe; risultato sintetico di 100 kB | 50 righe con totale e `truncated`; ≤ 20 kB; nessun numero accorciato (confronto con il risultato completo) | test di unità |
| T9 | Nomi dei file | comando con parametro `file` `/Users/nome/dati/pleiadi.fits` | il modello riceve `pleiadi.fits`; nessuna cartella, nessun SHA-256 | ricerca nel JSON |
| T10 | Numeri pieni | risultato con `23.18526...′` | nel JSON per il modello lo stesso `float64` (rilettura identica) con l'unità | confronto bit per bit |
| T11 | Riesecuzione senza IA | sessione con comandi chiesti dall'IA, riaperta senza profilo IA | stessi comandi rieseguiti, nessuna chiamata a un provider | `05` T4 con un provider simulato che fallisce se chiamato |
| T12 | Ogni stringa classificata (2026-10-22) | ogni strumento esposto eseguito su dati sintetici (catalogo con un'istruzione nel nome di una riga), poi `reduce_result` | nessuna stringa fuori da `EXTERNAL_FIELDS` e `ASTROTWO_FIELDS`; testi esterni marcati nei risultati di cataloghi, survey e SIMBAD, nessuno nei risultati di vista, misure e calcolatrici; nessuna cartella nel JSON | test di unità |

## 13. Decisioni aperte

Nessuna decisione dei Gruppi 1 e 2 aperta.

- **Scelte minori: CONFERMATE dal proprietario il 2026-10-16 (come raccomandate):** (1) modalità rigida (`strict`) dei
  provider non usata; (2) `coords.resolve_name` senza conferma pur usando
  la rete, perché di sola lettura (interpretazione della regola "i comandi
  di sola lettura non chiedono conferma"; dopo un testo esterno la chiede,
  §3.6); (3) testi esterni limitati a 500 caratteri; (4) `layer.remove`,
  `layer.move`, `image.set_display`, `catalog.set_columns`, `table.sort`
  fuori dalla v1; (5) `catalog.search` restituisce il conteggio e i primi
  50 indici senza cambiare la selezione (selezionare tutte le righe di
  un'espressione: versione successiva).
- **Da verificare con le chiavi dell'utente:** sottoinsieme di JSON Schema
  accettato da entrambi i provider (§3.4). Senza chiavi né rete si
  controlla solo che lo schema ridotto usi le parole del sottoinsieme (T3);
  la prova con i provider reali è nella lista di controllo manuale del
  `35` §12.
- **Scelte minori dello sprint 6a (2026-10-22):**
  - **CONFERMATE dal proprietario il 2026-10-22:** (1) argomenti vuoti
    (`""`, mandati da alcuni provider per gli strumenti senza parametri)
    letti come `{}`, cioè "nessun parametro".
  - **DECISA dal proprietario il 2026-10-22:** (7) in `catalog.rows` la
    fonte dei testi esterni è scritta una volta in testa al risultato
    (`external_source`) invece che in ogni campo, purché ogni valore resti
    attribuibile alla sua fonte (§3.6; T7 aggiornato).
  - **Solo di presentazione, CONFERMATE** (incarico del proprietario del
    2026-10-22 di togliere "da confermare" alle scelte di sola
    presentazione): (2) motivi della conferma scritti come codici
    `network`, `long`, `modifies_layer`, `after_external_text` (il `44` li
    traduce); (3) fonte del testo esterno = origine della provenienza,
    altrimenti sorgente del livello del comando (§3.6).
  - **Restano DA CONFERMARE** (toccano la privacy o la sicurezza, non solo
    la presentazione): (4) chiavi `sha256` mai inviate, percorsi assoluti
    con almeno due elementi ridotti al nome del file (§3.7); (5) nelle
    calcolatrici tutte le stringhe sono di AstroTwo (l'ingresso è quello
    scritto dal modello o dall'utente); il nome cercato da
    `coords.resolve_name` è un parametro ripetuto, quindi di AstroTwo,
    mentre l'identificativo principale e il bibcode di SIMBAD sono esterni;
    (6) elenco `ASTROTWO_MESSAGE_CODES` (§3.6).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-16 | Claude Code | Creazione del file (stato: bozza) dalla proposta della fase 1 sull'IA approvata dal proprietario il 2026-10-16: elenco esplicito dei comandi esposti e non esposti, schema da `export_schema` del `05`, nomi tradotti (`view.go_to` → `view__go_to`), validazione del `05`, stessa coda del `40` con `requested_by = ai`, conferme (rete, lungo, modifica di un livello; sola lettura senza conferma), risultati entro 50 righe e 20 kB senza numeri accorciati, nomi di file senza cartelle, `catalog.search` al posto del 33; **sicurezza**: testi esterni marcati come dati, conferma obbligatoria per i comandi chiesti dopo un testo esterno. |
| 2026-10-16 | Claude Code | Scelte minori **confermate dal proprietario il 2026-10-16** come raccomandate (§13). **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-16. |
| 2026-10-20 | Claude Code | **`view.set_overlays` aggiunto all'elenco degli strumenti** (§3.2, decisione del proprietario del 2026-10-20): classe session, vista, nessuna conferma. Il codice dell'elenco non esiste ancora (si scrive con il 32): niente da cambiare. Stato `approvato` invariato. |
| 2026-10-22 | Claude Code | **Codice dello sprint 6a** ("FASE: CODICE – interfaccia v1", parte 6): `src/astrotwo/ai/tool_registry.py` (`EXPOSED_COMMANDS` con i 22 strumenti di §3.2, `ToolRegistry` con `tools()`, `command_for`, `needs_confirmation`, `confirmation_request`, `reduce_result`, `ToolCallOutcome`, `ToolRegistryError`) e `tests/ai/test_tool_registry.py` (T1–T12; T5 copre la cronologia del `05`, la coda del `40` si prova con il `35` nello sprint 6c). **Decisione del proprietario del 2026-10-22:** testi esterni riconosciuti con due elenchi chiusi per percorso (`EXTERNAL_FIELDS` per comando, `ASTROTWO_FIELDS`), una stringa in nessuno dei due è esterna e fa fallire T12 (§3.6). Precisazioni in §3.4 (riduzione delle parole dello schema) e §3.7 (percorsi, `sha256`, forma dei tagli); scelte minori da confermare in §13. Stato `approvato` invariato. |
| 2026-10-22 | Claude Code | **Decisioni del proprietario del 2026-10-22 sullo sprint 6a** (applicate nello sprint 6b): argomenti vuoti = "nessun parametro" (scelta 1 confermata); in `catalog.rows` fonte dei testi esterni scritta una volta in testa (`external_source`, §3.6, §3.7; scelta 7 decisa; codice `SOURCE_ONCE` e test T7 aggiornati); scelte 2 e 3 confermate come solo di presentazione; restano da confermare 4, 5, 6 (§13). `external_source` reso pubblico per il `34`. Stato `approvato` invariato. |
