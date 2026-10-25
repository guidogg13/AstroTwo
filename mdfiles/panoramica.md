# panoramica.md — riassunto di tutto il progetto

**Stato:** bozza

## 1. Scopo

AstroTwo è il successore di Aladin per gli astrofisici: un'app desktop macOS
con un nucleo scientifico pari ad Aladin, un livello di analisi, un livello di
intelligenza artificiale con provider scelti dall'utente e un livello di
funzioni avanzate, consegnata come file `.dmg`.

## 2. Fase attuale

**FASE: CODICE – livello 1** (dichiarata dal proprietario il 2026-10-09);
tutti gli altri livelli restano in **FASE: SPECIFICHE**. Per l'interfaccia
la formula è a parte: **"FASE: CODICE – interfaccia v1"** (regola del
proprietario del 2026-10-15, in `CLAUDE.md`), valida per 40, 41, 42 e 44
`approvato`, per il `05` e, dal 2026-10-16, per i moduli IA della v1 30,
31, 32, 34, 35 `approvato`; **dichiarata dal proprietario il 2026-10-16**.

- **Stato al 2026-10-25 — **sprint 8f (rifiniture, 2026-10-25):** parametro di contesto riservato `layer_context` (`40` §3.7.1) con id, nome e tipo del livello: i messaggi di disegno di cataloghi e MOC e gli avvisi `CATALOG_EPOCH_*` dicono a quale livello si riferiscono («Catalog layer L2 «Gaia DR3»: …»; nome = testo esterno, `<layer_name>` verso l'IA); SkyCoord inutilizzato tolto da `test_messages_catalogs.py`; **test di rete**: 20 passati, 2 falliti — `test_t17_ut1_update_from_iers_network` (`datacenter.iers.org` risponde HTTP 400 «Request Rejected» a ogni percorso, radice compresa, anche da un'altra rete e con intestazioni da browser: non è URL, intestazioni né test; il mirror USNO `maia.usno.navy.mil` risponde 200; ripiego sul mirror USNO deciso dal proprietario il 2026-10-25 e implementato in `update_iers_table` (`18`), dopo il quale il test di rete passa se il mirror risponde) e `test_t7_epntap_real_service` (host `obspm.fr` non raggiungibile: connessione); prima, **sprint 8e della v1 (ultimo della traduzione dei messaggi, D40-3 chiusa):** convertiti a codice + `params` il `04` (cache), il `05` (comandi e sessione), i moduli IA `30`–`35` e i messaggi scritti direttamente da `40`, `41`, `42` e `44`, con la tabella di codici, ragioni e parametri scritta prima del codice in §10.1 di ogni `.md` (`CacheError`/`CacheWarning`, `CommandError`/`ResultMessage`, `KeychainError`, `ProviderError`/`ProviderAdapterError`/`ProviderNotice`/`ProfileError`, `ToolRegistryError`, `VerificationIssue`, `AssistantError`/`Availability`/`Note`, `ValueProblem` per le impostazioni); voci en/it del catalogo (circa 150 nuove: `COMMAND_PARAMETER_INVALID` con 40 ragioni, `SESSION_*` con messaggi annidati, `AI_*`, `KEYCHAIN_*`, `TOOL_*`, `PREFERENCE_*`, `UI_*`, `GL_UNAVAILABLE`, `EXPORT_*`, `CACHE_*`, sotto-voci aggiunte a `WCS_INVALID`, `WCS_MISSING`, `NO_WCS`, `COMMAND_CANCELLED`, `VIEW_UNDEFINED`, `OUT_OF_SKY`, `AI_NO_TOOLS`); codici nuovi non previsti dalle tabelle di §10 (`AI_PROFILE_INVALID`, `AI_RETRY`, `SESSION_SAVE_FAILED`, `PREFERENCE_VALUE_INVALID`, `UI_COMMAND_FAILED`, `MODULE_NOTE`, `SESSION_FINGERPRINT_CHANGE`, `SESSION_STATE_DIFFERENCE`, `KEYCHAIN_OPERATION`); il motivo per cui mancano le coordinate in `PixelGridGeometry.problem` è ora un `ResultMessage`; il pannello del `44` mostra motivo di indisponibilità, note, errori e avvisi dal catalogo (frase italiana aggiornata in `astrotwo_it.ts`/`.qm`). **Controllo finale:** `test_t18_every_code_used_anywhere_in_the_package_has_an_entry` scorre tutto `src/astrotwo` e fallisce per un codice o una ragione senza voce; i messaggi creati nei test sono controllati contro il catalogo (`tests/conftest.py`). Nessun comportamento scientifico cambia. Test di rete non eseguiti nel commit (`--no-network`), eseguiti una volta alla fine (esito in chat).** Restano lo sprint di prestazioni per D41-7 e D41-8 e le specifiche dei gruppi rimanenti.

- **Stato al 2026-10-24, sprint 8d della v1, modulo 18 (8d completo):** **Modulo 18 (calcolatrici) convertito** a codice + `params` (`CalculatorError(code, message, params=...)` con `relayed`; il modulo non ha avvisi con codice); `18` §10 con la tabella scritta prima del codice; voci en/it con sotto-voci aggiunte a `UNIT_UNKNOWN`, `UNIT_INCOMPATIBLE`, `NET_TIMEOUT`, `OPERATION_UNSUPPORTED`, `EPOCH_REQUIRED` e codici nuovi (`CALC_*`, `TIME_*`, `IERS_*`, `UNIT_*`, `PIXEL_*`); errori di 10, 11, 13, 14 e 17 rilanciati con i loro `params`. **Sprint 8d concluso:** 14, 16, 19, 15, 17 e 18 convertiti, T18 comprende tutti i moduli 10–19 e gli errori di 14, 16 e 19 incorporati da 12 e 13 sono messaggi annidati (`40` §3.7.1 aggiornata). Test `tests/core/test_messages_calculators.py`, T18 e `conftest.py` con il 18. Restano il `05` e i moduli dell'interfaccia e dell'IA (sprint 8e). Nessun comportamento scientifico cambia.

- **Stato al 2026-10-24, sprint 8d della v1, modulo 17:** **Modulo 17 (misure) convertito** a codice + `params` (`MeasuresError(code, message, params=...)` con `relayed`, avvisi `ModuleWarning` in `MeasureReport.warnings`); `17` §10 con la tabella scritta prima del codice; voci en/it con sotto-voci aggiunte a `FRAME_UNKNOWN`, `MEMORY_LIMIT_EXCEEDED`, `OPERATION_UNSUPPORTED`, `NO_COORD_COLUMNS`, `EPOCH_REQUIRED`, `BODY_UNKNOWN`, `BODY_MISMATCH`, `NONFINITE_PIXELS` e codici nuovi (`PA_UNDEFINED`, `OFFSET_INVALID`, `POINT_OUT_OF_IMAGE`, `NO_WCS`, `PROFILE_STEP_INVALID`, `SHAPE_INVALID`, `DISTANCE_PRECISION_NOT_REACHED`, `AREA_PRECISION_NOT_REACHED`, `SELECTION_NOT_TWO_SOURCES`); errori del 10, 11 e 13 rilanciati con i loro `params`, `EPOCH_INVALID` del 13 incorporato come messaggio annidato. Test `tests/core/test_messages_measures.py`, T18 e `conftest.py` con il 17. Restano 18, `05`, `30`–`35`. Nessun comportamento scientifico cambia.

- **Stato al 2026-10-24, sprint 8d della v1, modulo 15:** **Modulo 15 (incrocio) convertito** a codice + `params` (`CrossmatchError(code, message, params=...)` con `relayed`, avvisi `ModuleWarning`); `15` §10 con la tabella scritta prima del codice; voci en/it con sotto-voci aggiunte a `TABLE_TOO_LARGE`, `BODY_UNKNOWN`, `BODY_MISMATCH`, `BODY_FORCED`, `MAX_SEP_INVALID`, `NO_COORD_COLUMNS`, `FRAME_UNKNOWN`, `SERVICE_ERROR` e codici nuovi (`KEY_COLUMN_INVALID`, `ERROR_ELLIPSE_INVALID`, avvisi dell'incrocio); errori del 10 e del 14 rilanciati con i loro `params`. Test `tests/core/test_messages_crossmatch.py`, T18 e `conftest.py` con il 15. Restano 17, 18, `05`, `30`–`35`. Nessun comportamento scientifico cambia.

- **Stato al 2026-10-24, sprint 8d della v1, modulo 19:** **Modulo 19 (dati planetari) convertito** a codice + `params` (`PlanetaryDataError(code, message, params=...)` con `relayed`, avvisi `ModuleWarning`); `19` §10 con la tabella scritta prima del codice; nuovi codici annidati `BODY_CAUSE` (motivo del corpo di un livello) e `PDS_DOWNLOAD` (righe di `PDS_DOWNLOADED`, tipo `messages`); voci en/it con sotto-voci aggiunte a `BODY_UNSUPPORTED`, `BODY_UNKNOWN`, `BODY_MISMATCH`, `BODY_NORMALIZED`, `COORD_OUT_OF_RANGE`, `ADQL_INVALID`; errori del 14 rilanciati con i loro `params`. L'errore `BODY_UNSUPPORTED` del 19 incorporato dal 12 passa da esterno a `message`. Test `tests/core/test_messages_planetary.py`, T18 e `conftest.py` con il 19. Restano 15, 17, 18, `05`, `30`–`35`. Nessun comportamento scientifico cambia.

- **Stato al 2026-10-24, sprint 8d della v1, modulo 16:** **Modulo 16 (MOC) convertito** a codice + `params` (`MocError(code, message, params=...)` con `relayed`, avvisi `ModuleWarning`, nuovo codice `BODY_FORCED`); `16` §10 con la tabella di codici, ragioni e parametri scritta prima del codice; voci en/it del catalogo (sotto-voci aggiunte a `HEALPIX_ORDER_INVALID`, `BODY_UNKNOWN`, `REGION_INVALID`, `NO_COORD_COLUMNS`, `FRAME_UNKNOWN`, `PREVIEW_NOT_MEASURABLE`, `MOCSERVER_UNAVAILABLE`, `SERVICE_ERROR`, `FROM_CACHE`); errori del 10 e del 14 rilanciati con i loro `params`. L'errore del 16 incorporato dal 12 (`MOCSERVER_UNAVAILABLE` `coverage`) passa da parametro esterno a `message`. Tolto un ramo di `_read_json` irraggiungibile (con una lista il payload è sempre una lista). Test `tests/core/test_messages_moc.py` (ogni coppia codice/ragione), T18 e `conftest.py` con il 16. Restano 19, 15, 17, 18, `05`, `30`–`35`. Nessun comportamento scientifico cambia.

- **Stato al 2026-10-24, sprint 8d della v1, modulo 14:** **Modulo 14 (protocolli VO) convertito** a codice + `params` (`VoProtocolsError(code, message, params=...)`, avvisi `ModuleWarning`, `AdqlCheck` con `reason` e `quote`); `14` §10 con la tabella di codici, ragioni e parametri scritta prima del codice; voci en/it del catalogo (sotto-voci aggiunte a `NET_TIMEOUT`, `SERVICE_ERROR`, `FROM_CACHE`, `BODY_UNKNOWN`, `FORMAT_DECLARED`, `TABLE_TOO_LARGE`; il suggerimento dell'asincrona è una sotto-voce a parte). Gli errori del 14 che il 12 incorpora (`HIPS_NOT_A_SERVICE` `service_error`, `HIPS_METADATA_INVALID` `metadata_xml_unavailable`, `MOCSERVER_UNAVAILABLE` `resolve` e `index`) e l'avviso `ROW_LIMIT_EXCEEDED` citato dal 13 (`REGION_REQUIRED`, `REGION_TOO_LARGE`) passano da parametro esterno a `message`. Test `tests/core/test_messages_vo_protocols.py` (ogni coppia codice/ragione), T18 e `conftest.py` con il 14. Restano 16, 19, 15, 17, 18, `05`, `30`–`35`. Nessun comportamento scientifico cambia.

- **Stato al 2026-10-24, sprint 8c-bis della v1 (messaggi annidati D40-7 e
  modulo 13):** **D40-7 decisa** dal proprietario (opzione (b)): tipo di
  parametro `message` (e `messages`, elenco) con `code`, `params`, `text`,
  reso in modo ricorsivo nella lingua dell'interfaccia e in inglese verso
  l'IA, profondità massima 3 (`MAX_MESSAGE_DEPTH`); il testo di terzi resta
  `external`, anche dentro un annidato, marcato come esterno verso l'IA
  (elenchi compresi). Nel 12: `REGION_INVALID` (errore del 10),
  `HIPS_COVERAGE_UNKNOWN` (errore del 12) e `HIPS_BAD_TILE` /
  `HIPS_TILE_DISCARDED` (nuovo codice annidato `HIPS_TILE_PROBLEM`) usano il
  tipo `message`; le risposte di 14, 16 e 19 restano esterne finché quei
  moduli non sono convertiti (sprint 8d). Il catalogo accetta graffe
  raddoppiate nel testo (`${{nome}}`) e mostra un elenco vuoto come "—".
  **Modulo 13 convertito** a codice + `params` (`CatalogsError(code, message,
  params=...)`, avvisi `ModuleWarning`, errori del 10 rilanciati nella
  propagazione con `relayed`; nuovo codice annidato `ASTRORES_LINK_PROBLEM`;
  `13` §10 con la tabella generata dal catalogo; sotto-voci del 13 aggiunte
  alle voci condivise `FORMAT_UNSUPPORTED`, `MEMORY_LIMIT_EXCEEDED`,
  `REGION_INVALID`, `BODY_UNKNOWN`, `COORD_UNIT_MISSING`). Test
  `tests/core/test_messages_catalogs.py` (ogni coppia codice/ragione del 13
  provocata), T18 e `conftest.py` con il 13, prove dei messaggi annidati nel
  catalogo e nel registro del 32. Restano 14–19, `05`, `30`–`35`. Test di rete
  non eseguiti (`--no-network`). Decisioni aperte: **16**.
- **Stato al 2026-10-24, sprint 8c della v1 (messaggi dei moduli, D40-3):**
  il **modulo 12** restituisce errori e avvisi come codice + `params`
  (`HiPSError(code, message, params=...)`, avvisi `ModuleWarning`); `12` §10 con
  la tabella di codici, ragioni e parametri; voci del catalogo in inglese e
  italiano con le sotto-voci per `reason` (nuove: HIPS_*, HEALPIX_*, BODY_*,
  `REGION_INVALID`, `SERVICE_ERROR`, `MOCSERVER_UNAVAILABLE` e sotto-voci
  aggiunte a `NET_TIMEOUT`, `WCS_MISSING`, `OPERATION_UNSUPPORTED`,
  `PREVIEW_NOT_MEASURABLE`, `MEMORY_LIMIT_EXCEEDED`, `FROM_CACHE`). Gli errori
  del 14 e del 16 rilanciati dal 12 conservano codice, testo e `params`
  dell'altro modulo (finché non è convertito: nessuna traduzione, §3.7.2);
  gli avvisi dei moduli sotto passano invariati. I messaggi che incorporano
  un altro messaggio (causa, motivo del tile corrotto) usano un parametro
  esterno: **aperta D40-7** (tipo di parametro "messaggio" nel catalogo,
  Gruppo 3, raccomandazione nel 40 §13). Test `tests/core/test_messages_hips.py`
  (ogni coppia codice/ragione del 12 provocata e controllata contro il
  catalogo), T18 e `conftest.py` con il 12; il fake di `test_main_window`
  dà ai suoi errori i `params` veri. Test di rete non eseguiti
  (`--no-network`). Decisioni aperte: **17**.
- **Stato al 2026-10-24, parte 4, sprint 4h della v1 (41, ultimo):**
  **PNG della vista** (`view.export_png` collegato; nuovo `ui/export_view.py`):
  immagine in pixel fisici con riga dei crediti in basso a destra e blocchi
  `tEXt` (versione, data, vista, livelli con sorgente e data, crediti interi
  dei testi di `01` §6.1 o dichiarati dal survey); scrittura atomica;
  errori `EXPORT_PATH_INVALID`, `VIEW_UNDEFINED`, `EXPORT_FAILED`. **Cambio
  di base in un passo** (T17): la base vecchia resta disegnata finché
  campionamento, simboli e MOC della nuova non sono pronti, poi passa tutto
  nello stesso turno degli eventi. **Prestazioni** (`tests/ui/test_perf.py`,
  `perf`): sul Mac minimo (iMac M1 8 GB) P2, P3, P4, P6 raggiunti; **P1
  (46 ms contro 16,7) e P5 (4,46 s contro 3) non raggiunti**, obiettivi non
  abbassati (41 §3.15). **D41-4: due Mac di riferimento** (minimo e MacBook
  Air M5 32 GB dal 2 novembre). Scelte minori dello sprint 4g confermate; quelle
  dello sprint 4h (41, 1–10) da confermare. Test: **831 di default**, di rete
  non eseguiti (`--no-network`). Decisioni aperte: **15**.
- **Stato al 2026-10-23, parte 4, sprint 4g della v1 (41: distanza e
  puntatore Simbad):** nuovo `ui/sky_tools.py`. **Distanza:** con lo
  strumento attivo il trascinamento (o due clic) invia `measure.distance`;
  con un'immagine come base usa i pixel, con solo uno sfondo HiPS le
  posizioni celesti (nuova forma cielo `sky1`/`sky2` del comando, decisione
  del proprietario); barra delle opzioni sul cielo (unità, aggancio al
  centroide, finestra del centroide) ricordata con `prefs.set`; segmento ed
  etichetta (4 cifre significative) disegnati con `QPainter`, rossi di
  notte; la vista non si sposta. **Puntatore Simbad:** mouse fermo 500 ms o
  clic, raggio di 12 pixel logici in angolo (10 e 17), una richiesta alla
  volta, riquadro con oggetto, tipo, coordinate, magnitudini con sistema,
  citazioni, fonte e collegamento (si apre solo la pagina di Simbad).
  `measure.distance` è già tra gli strumenti dell'IA (schema esteso);
  `simbad.pointer` resta fuori (`passive`, regola del 32). Ruff 0.17.2 come
  strumento di sviluppo, 12 errori veri corretti. Scelte minori del 41
  §3.19 da confermare. Test: **822 di default**, di rete non eseguiti
  (`--no-network`). Decisioni aperte: **15**.
- **Stato al 2026-10-23, parte 7, sprint 7c della v1 (decisioni e
  stabilità dei test):** decise **D32-1** (identificativi del gruppo fisso
  nella descrizione di `catalog` di `catalog.load_region`, letti da
  `FIXED_COLLECTIONS`; `CATALOG_UNKNOWN` elenca le tabelle di VizieR che
  cominciano con l'identificativo scritto, da `TAP_SCHEMA.tables`, con la
  risposta vera di VizieR registrata per il test) e **D13-21** (nella v1
  `NO_COORD_COLUMNS` con le colonne candidate per RA e Dec nel messaggio);
  il comando di ricerca nell'elenco dei cataloghi è rinviato a dopo la v1
  (nuova **D32-2**). Confermate le 5 scelte minori dello sprint 7b del 44.
  **Test instabili** (T1 e T2 del 42, T30 del 41): causa comune = i test
  leggevano lo stato dopo `wait_idle`, che aspetta solo i comandi, mentre
  altre cose arrivano dopo da sole (calcolo dei simboli nel gruppo di thread,
  timer di 120 ms del pannello, timer di 300 ms della vista che dopo ogni
  cambio di layout manda un `view.set_center`): su un Mac lento l'ultima voce
  della cronologia non era più il comando atteso. Ora attese su condizioni
  (`wait_settled`, `wait_command`), niente tempi fissi. Test: **810 di
  default**, di rete non eseguiti (`--no-network`). Decisioni aperte: **15**.
- **Stato al 2026-10-23, parte 7, sprint 7b della v1 (44: numeri
  evidenziati e prove):** ogni numero della risposta ha lo stile del suo
  stato del 34 (sottolineatura continua = verificato, tratteggiata =
  dato dell'utente, parametro o testo esterno, sfondo d'avviso = non
  verificato o ambiguo) con suggerimento (valore pieno con unità, `#n`,
  funzioni del modulo) e "Copia il valore pieno" col clic destro, anche in
  modalità notte; sonda di latenza (T14) con risposta lenta e comando
  lungo; test di Aggiorna e "Prova il modello" con il servizio simulato,
  errori del provider, conversazione troppo lunga, conferma in attesa con
  il pannello chiuso, uscita con risposta in corso. Corretto un difetto
  dello sprint 7a: l'esito di un secondo Aggiorna o "Prova il modello" si
  perdeva (oggetto dei segnali distrutto). **Prova reale del proprietario
  ("Carica Gaia DR3 attorno alle Pleiadi"):** causa vera = identificativo
  sbagliato scritto dal modello (`I/355` o `gaiadr3` non sono tabelle);
  con `I/355/gaiadr3` il comando funziona sul servizio reale (`RA_ICRS`/
  `DE_ICRS` da `meta.main`, ICRS epoca J2016). Ora una tabella assente da
  `TAP_SCHEMA` dà `CATALOG_UNKNOWN` (13) e uno strumento sconosciuto torna
  al modello con l'elenco `valid_tools` (32); `catalog__search` esiste ma
  non cerca in VizieR. **Decisione del proprietario del 2026-10-23:** 12
  scelte minori dello sprint 7a del 44 confermate. Aperte **D32-1** (come
  l'IA trova l'identificativo di un catalogo) e **D13-21** (colonne ambigue
  in una regione chiesta dall'IA). Scelte minori dello sprint 7b da
  confermare (44 §13). Test: **808 di default**, di rete non eseguiti
  (`--no-network`). Decisioni aperte: **16**.
- **Stato al 2026-10-22, parte 7, sprint 7a della v1 (44: pannello
  dell'assistente):** `src/astrotwo/ui/ai_panel.py` nell'area a destra
  della finestra (400 pt, ⌃⌘A): intestazione con profilo, modello,
  lucchetto della chiave e simbolo "locale · nulla esce dal Mac", riga
  sulla privacy, messaggi in Markdown semplice (HTML come testo, immagini
  non caricate, indirizzi dei collegamenti scritti per intero, apertura
  solo con un clic), testo grigio durante lo streaming, schede dei comandi
  (`#n`, parametri con unità, esito, fonte; clic → riga del pannello
  Comandi), schede di conferma (Conferma, Annulla, "per questa
  conversazione" assente dopo un testo esterno), riepilogo della verifica
  del 34, note dei limiti, token e costo con il prezzo dell'utente, "Cosa è
  stato inviato" (JSON esatto), Invia/Stop, consenso al primo messaggio
  (salvato con `prefs.set`), stato "non disponibile" con il pulsante
  verso l'impostazione mancante, impostazioni (profili, provider
  predefiniti con contrassegno, modello da `list_models`, chiave solo nel
  Portachiavi, "Prova il modello", modalità rigorosa, limiti, prezzo),
  testo delle conversazioni nel salvataggio della sessione su richiesta,
  modalità notte e italiano. Markdown di Qt verificato (Qt 6.12). Scelte
  minori da confermare nel 44 §3.10, §13. **Decisioni del proprietario del
  2026-10-22 sullo sprint 6c:** 12 scelte minori del 35 confermate; ultima
  richiesta dopo il limite di chiamate con gli strumenti e `tool_choice =
  none` (nuova opzione del turno del 30, T16), da provare con le chiavi
  dell'utente. Resta lo sprint 7b (evidenziazione dei numeri T5, latenza
  T14, prove di modelli/prova/errori). Test: **799 di default**, di rete
  non eseguiti (`--no-network`). Decisioni aperte: **14**.
- **Stato al 2026-10-22, parte 6, sprint 6c della v1 (35: assistente):**
  `src/astrotwo/ai/chat_assistant.py` collega provider (30), chiavi (31),
  strumenti (32) e verifica (34): regole di sistema R1–R9 in inglese
  (versione 1), una richiesta dopo l'altra finché il modello chiede
  strumenti, chiamate eseguite una alla volta nell'ordine ricevuto nella
  coda del 40 (`MainWindow.assistant_executor()`, stesso `CancelToken` della
  risposta), conferme (rete, lungo, modifica di un livello; dopo un testo
  esterno sempre, senza "per questa conversazione"), limiti di 10 chiamate
  (ultima richiesta senza strumenti) e 5 minuti (attese di conferma
  escluse), Stop, verifica del 34 con una sola rigenerazione in modalità
  rigorosa, token per risposta e conversazione con costo solo con il prezzo
  dell'utente, disponibilità (profilo, chiave, Portachiavi, strumenti,
  consenso), testo delle conversazioni nella sessione solo su richiesta.
  Test T1–T14 con un provider simulato a copione (corpo JSON vero del 30),
  senza rete e senza chiavi, più la coda vera della finestra. Precisazioni
  del codice e scelte minori da confermare nel 35 §3.11, §13; **da
  verificare con una chiave di Anthropic** la richiesta senza strumenti dopo
  il limite. **Decisioni del proprietario del 2026-10-22 sullo sprint 6b:**
  34, vale solo l'arrotondamento ("e troncamento" tolto); scelte minori del
  34 confermate; scelte 4, 5, 6 del 32 confermate. Test: **780 di
  default**, di rete non eseguiti (`--no-network`). Decisioni aperte:
  **14**.
- **Stato al 2026-10-22, parte 6, sprint 6b della v1 (34: verifica dei
  numeri):** `src/astrotwo/ai/result_verification.py` estrae ogni numero
  della risposta dell'IA (decimali, notazione scientifica, sessagesimali con
  `parse_sexagesimal` del 10, date ISO, forme ambigue), esclude solo le
  eccezioni dell'elenco chiuso del 34 §3.3 e cerca ogni numero, alla
  precisione scritta e con l'unità scritta (conversioni `astropy.units` solo
  per confrontare), nei risultati completi dei comandi della conversazione,
  nei loro parametri e nei messaggi dell'utente; stati `verified`,
  `verified_other_command`, `command_parameter`, `user_input`,
  `external_text`, `excluded`, `not_verified`, `ambiguous`, con posizioni per
  il 44, riepilogo, controllo delle conferme dopo un testo esterno
  (`ACTION_WITHOUT_CONFIRMATION`) e modalità rigorosa con una sola
  rigenerazione. **Decisioni del proprietario del 2026-10-22:** contrasto
  T5/§3.5 del 34 risolto a favore di §3.5 (numero solo in un testo di terzi =
  `external_text`); in `catalog.rows` la fonte dei testi esterni è scritta
  una volta in testa (32 §3.6); scelta 1 del 32 confermata, 2 e 3 confermate
  come presentazione, restano 4–6; limiti del 35 come da specifica (10
  comandi e 5 minuti per risposta). Scelte minori del 34 e incongruenza
  "troncamento" da confermare (34 §13). Test: **759 di default** (T14
  `perf` 20 ms su 50 ms), di rete non eseguiti (`--no-network`). Decisioni
  aperte: **14**.

- **Stato al 2026-10-22, parte 6, sprint 6a della v1 (32: registro degli
  strumenti per l'IA):** `src/astrotwo/ai/tool_registry.py` espone all'IA
  **solo i 22 comandi del 32 §3.2** (compreso `view.set_overlays`), con nome,
  descrizione e schema presi da `export_schema` del 05 e ridotti al
  sottoinsieme accettato dai provider; ogni chiamata si valida con il 05 come
  quelle dell'utente (errori restituiti al modello, nulla in cronologia),
  diventa un comando con `requested_by = ai` e il suo risultato arriva al
  modello ridotto (≤ 50 elementi, ≤ 20 kB, nessun numero accorciato, file
  senza cartelle, niente SHA-256). **Conferme:** rete, lungo o modifica di un
  livello; dopo un testo esterno ogni comando che non sia di sola lettura
  senza rete chiede conferma, senza "per questa conversazione".
  **Decisione del proprietario del 2026-10-22:** i testi esterni si
  riconoscono con due elenchi chiusi per percorso (campi esterni per
  comando, campi di AstroTwo); una stringa non classificata è esterna e fa
  fallire T12. **Decisioni del proprietario del 2026-10-22 sullo sprint
  5b:** confermate le scelte minori del 42 §13; i sei valori della stella di
  Barnard restano nei test con Gaia DR3 citata come fonte. Divisione della
  parte 6 approvata: **6a 32 (fatto), 6b 34, 6c 35**, poi il 44. Scelte
  minori di 6a da confermare (32 §13). Test: **744 di default**, di rete
  non eseguiti (`--no-network`). Decisioni aperte: **14**.
- **Stato al 2026-10-22, parte 5, sprint 5b della v1 (42: dialoghi delle
  colonne):** all'apertura di un catalogo (`catalog.open_file`,
  `catalog.load_region`) si apre da solo il dialogo delle **colonne di
  posizione** se il 13 non le ha determinate, e quello del **moto proprio**
  se gli UCD indicano un moto in RA e in Dec; il pulsante **"Colonne…"** della
  scheda li apre quando si vuole. Nulla è assunto: sistema, unità, equinozio
  (FK4/FK5) e "include cos δ" li dichiara l'utente (ipotesi dai nomi marcate
  "da confermare"; moto preselezionato solo dagli UCD); un solo
  `catalog.set_columns` per apertura (T7). **Decisioni del proprietario del
  2026-10-22:** confermate le 8 scelte di presentazione del 42 (5a, a–h);
  **dati di test di Gaia (CC BY-NC 3.0 IGO) sostituiti da dati SINTETICI**
  (stelle inventate, stessa struttura VOTable con `COOSYS` J2016.0, generate
  da `scripts/make_synthetic_catalog.py`; file Gaia rimossi dal ramo attuale;
  altri dati di terze parti nei test: nessun file; restano soltanto sei
  numeri astrometrici della stella di Barnard scritti a mano in
  `tests/core/test_coordinates_wcs.py` (valori di Gaia DR3, ricalcolati con
  Astropy; da segnalare al proprietario) e un test di rete che interroga Gaia
  dal vivo senza salvarne i dati). Scelte minori di 5b confermate il 2026-10-22 (42
  §13). Test: **730 di default**, di rete non eseguiti (`--no-network`).
  Decisioni aperte: **14**.
- **Stato al 2026-10-21, parte 5, sprint 5a della v1 (42: pannello
  Tabella):** il pannello in basso mostra **una scheda per livello di
  catalogo** con la tabella virtuale in sola lettura (nessuna copia: 1 milione
  di righe aperto in 0,3 ms, ordinamento in 114 ms, T6); posizioni scritte con
  `format_coordinates` del 10 nel frame della colonna e nello stile di
  "Coordinates shown", magnitudini a 3 decimali, altre colonne col formato
  dichiarato o la forma più breve, valore pieno nel suggerimento e nella copia;
  **ordinamento** con `table.sort` (clic sull'intestazione), **selezione nei due
  versi** con `catalog.select` (tabella → cielo e cielo → tabella, riga portata
  in vista), **record completo** da `record_view` del 13 accanto alla tabella,
  righe non disegnate marcate "◌". **Decisioni del proprietario del
  2026-10-21:** filtro con la grammatica `search` fuori dalla v1 (come la 42);
  testo di `PLANETARY_DATA_DISABLED` onesto ("i dati planetari non sono
  disponibili in questa versione", solo italiano per D40-1). Scelte minori di
  presentazione del 42 da confermare (42 §13). Corretto un difetto del 13
  (`record_view` con colonne array). Dati di test di terze parti: README in
  `tests/core/data/` (non coperti dalla GPL: Gaia CC BY-NC 3.0 IGO, regole di
  VizieR e del CDS; permesso esplicito di ridistribuzione da verificare) e
  sezione in `THIRD_PARTY_LICENSES`. Resta lo **sprint 5b** (dialoghi delle
  colonne di posizione e di moto proprio, T7). Test: **726 di default** (T6 `perf` a parte), di rete non eseguiti (`--no-network`). Decisioni aperte: **14**.
- **Stato al 2026-10-21, parte 4, sprint 4f della v1 (41: MOC, livelli,
  corpi diversi):** un MOC (File → Open MOC…) si disegna sulla GPU come
  triangoli trasparenti e perimetro (celle di `healpix_grid` del 16, pixel della
  base dal 10, nel gruppo di thread dei tile, una volta per base), con ordine
  ridotto dichiarato "per eccesso" quando le celle superano il tetto del 16.
  **Pannello dei livelli** nel 40: visibilità, opacità (al rilascio), su/giù e
  trascinamento, rimozione, tutti comandi registrati del 05; dettagli con
  sorgente, corpo, epoca e conteggi. **Lo sfondo HiPS torna visibile sotto
  un'immagine FITS** (texture separate composte con l'opacità nell'ordine dei
  livelli). **Decisioni del proprietario del 2026-10-21:** D41-6 (il 13 conserva
  l'epoca del COOSYS con le stesse colonne e lo stesso sistema; `source_epoch`
  annotato per il futuro); stile dei MOC da `moc.open` (Okabe e Ito in ordine
  inverso, riempimento 0,25 × opacità); solo il perimetro (`HealpixGrid.boundary`
  nuovo nel 16); `BODY_MISMATCH` prima dell'opzione dei dati planetari (19); MOC
  di un altro corpo forzato: nel pannello ma non disegnato. Correzioni trovate:
  uniformi float di PySide6 (`setUniformValue1f`), simboli e MOC disegnati anche
  oltre il riquadro dell'immagine. Test: **718 di default** (più 4 `gl`
  eseguiti su `cocoa`: passano), di rete non eseguiti (`--no-network`). Risposta
  di Gaia DR3 registrata in `tests/core/data/` (condizioni di ridistribuzione da
  verificare). Decisioni aperte: **14** (Gruppo 3 = 12).
- **Stato al 2026-10-21, parte 4, sprint 4e della v1 (41: cataloghi e
  clic):** un catalogo caricato (Data → Catalog in view…, `catalog.load_region`,
  o File → Open catalog…) si disegna come simboli sulla GPU (forma nel programma
  di disegno); posizioni dal 13 e pixel della base dal 10 nel gruppo di thread
  dei tile, una volta per base. **Decisioni del proprietario del 2026-10-21:**
  stile iniziale assegnato dal comando di caricamento (Okabe e Ito senza il
  nero, sei forme, 8 pixel logici, in ordine di apertura); clic → `catalog.select`
  con una **scheda della sorgente sul cielo** (nome da UCD `meta.id;meta.main`,
  coordinate della tabella con `format_coordinates`, epoca del catalogo,
  catalogo); avvisi `CATALOG_EPOCH_DIFFERS`/`CATALOG_EPOCH_UNKNOWN`; **D41-5
  rinviata a dopo la v1**; **correzione: l'epoca nella barra di stato è in ISO
  8601 con la scala** (DC1), non più in JD (`time_text` del 05; nessun altro JD
  nell'interfaccia). Trovata la nuova **D41-6** (Gruppo 3: `catalog.set_columns`
  perde l'epoca del COOSYS). Test: **704 di default** (più 3 `gl` eseguiti sulla
  piattaforma `cocoa`: passano), di rete non eseguiti (`--no-network`); T30:
  5000 sorgenti in 5.7 ms per base. Decisioni aperte: **15** (Gruppo 3 = 13).
- **Stato al 2026-10-20, parte 4, sprint 4d della v1 (41: immagine FITS
  locale):** File → Apri su un FITS (`image.open` del 05, già previsto) lo
  rende base della vista con il suo WCS, **inquadrato intero nella finestra**
  (decisione del proprietario del 2026-10-20; lo fa `image.open` e lo scrive
  in `framing`); colori da `set_display` dell'11; sotto il mouse il valore
  **originale** con unità `BUNIT` (o «unit not declared»), la posizione
  `FITS (x, y)` e le coordinate con frame ed epoca letti dall'intestazione,
  mai assunti. **Senza WCS valido** (decisione del proprietario): griglia di
  pixel, nessuna coordinata inventata, `WCS_INVALID` nella barra; zoom e
  spostamento col mouse non ci sono su di essa (nuova **D41-5**, Gruppo 3).
  `view.set_overlays` aggiunto all'elenco degli strumenti dell'IA (32).
  Corretti gli avvisi doppi di `hips.set_survey` (`service.warnings` era
  contato due volte), con test. Test: **690 di default**, di rete non
  eseguiti (`--no-network`). Decisioni aperte: **14** (Gruppo 3 = 12).
- **Stato al 2026-10-20, parte 4, sprint 4c della v1 (41: griglia, nord e
  barra di scala):** la griglia delle coordinate (ICRS o galattica) con
  etichette scritte dal 10 (precisione = passo), l'indicatore del nord e
  dell'est e la barra di scala (`compass_and_scale_bar` del 10) si
  disegnano sul cielo; in modalità notte sono rossi puri, durante un gesto
  indicatore e barra sono grigi. **Decisione del proprietario del
  2026-10-20:** nuovo comando `view.set_overlays` nel 05 per accenderli e
  spegnerli (voci nel menu Vista; non nell'elenco degli strumenti dell'IA,
  32). Verificato: i 4 avvisi di `hips.set_survey` all'avvio sono
  `FROM_CACHE` (2 sorgenti × 2, corretti; con cache vuota nessuno). Decisioni
  aperte invariate: **13**.
- **Stato al 2026-10-20, parte 4b-fix2 della v1:** l'ordine e la risoluzione
  del valore del pixel non comparivano nella barra di stato mentre un comando
  era in corso: i dati arrivavano sempre da `cursor.read`, era il testo a
  essere tagliato a destra (il nome del comando restringeva il campo).
  Barra a due campi: valore · ordine · risoluzione a larghezza fissa e mai
  tagliato, coordinate che si accorciano per prime (senza epoca, poi «…»),
  testo completo nel tooltip, comando in corso a larghezza massima; test a
  1280 e 900 px. Decisioni aperte invariate: **13**.
- **Stato al 2026-10-19, parte 4b-fix della v1:** dopo la prova del
  proprietario. (1) **"Vai a" M31 non funzionava dopo Sirius:** causa trovata
  con il servizio reale — il nome si risolveva bene (M31, m31, M 31,
  Andromeda, NGC 224 danno tutti lo stesso oggetto, come Sirius), ma la base
  `TAN` creata su Sirius non può rappresentare un centro a più di 90°
  (`VIEW_PARAMETERS_INVALID: il centro cade fuori dalla proiezione della
  base`); ora il 05 ricrea la base con il punto di tangenza al centro (test
  con le risposte reali di SIMBAD registrate, senza rete). (2) Il valore del
  pixel dichiara ordine HiPS e risoluzione (`cursor.read`: `resolution`,
  `survey_order`; barra di stato `… · ordine 6 (≈ 3.2″/px)`); il testo della
  barra non ridimensiona più il cielo. (3) Ripiego sul primo tile coperto e
  6 cifre significative confermati. (4) `pytest-timeout` (120 s a test, 600 s
  quelli di rete, metodo `thread`): un blocco diventa un fallimento con il
  nome del test. Decisioni aperte invariate: **13**.
- **Stato al 2026-10-18, parte 4 sprint 4b della v1 (41: tile FITS e
  lettura sotto il mouse):** i tile dei survey FITS si disegnano con i
  colori di `set_display` dell'11 (palette `gray`, funzione `linear`,
  gamma 1; pixel non finiti trasparenti) al posto dell'avviso
  `HIPS_FITS_NOT_YET`; nella barra di stato compaiono frame, coordinate
  scritte da `format_coordinates` del 10, epoca dichiarata e, per i survey
  FITS, il valore del pixel con l'unità. **Decisioni del proprietario del
  2026-10-18:** (1) i limiti di colore li sceglie `hips.set_survey`
  (`hips_pixel_cut`, altrimenti `suggest_display_limits` sul tile di ICRS
  (0°, 0°) all'ordine min(3, massimo)) e li scrive nel comando registrato
  (`vmin`, `vmax`: riapertura della sessione = stessi colori); (2) il
  valore del pixel si legge all'ordine disegnato (`cursor.read` guadagna
  `order`). Aggiornati `05` e `41` (stato `approvato` invariato). Scelta
  minore (confermata il 2026-10-19): se il tile di (0°, 0°) manca, i limiti
  vengono dal primo tile coperto (altrimenti `HIPS_DISPLAY_LIMITS_UNDEFINED`).
  Il test `test_visual_guidelines` faceva una richiesta reale a SIMBAD:
  ora usa il finto servizio (`fake_simbad`), nessun cambiamento all'app.
  Decisioni aperte invariate: **13**.
- **Stato al 2026-10-17, licenza del progetto (A11 decisa):** AstroTwo è distribuito con **GPL-3.0-or-later**, titolare Guido Ratti
  (2026, unico titolare). Creati `LICENSE` (testo ufficiale GPL-3.0), `NOTICE`, `CONTRIBUTING.md` (nessun contributo esterno senza CLA);
  `pyproject.toml` con `license` e `license-files`; intestazione SPDX in tutti i `.py` (test `tests/test_license_headers.py`);
  `THIRD_PARTY_LICENSES` rigenerato; verifica di compatibilità, crediti dei dati e requisiti del `60` in `01` §6.1. Nessun cambiamento
  al comportamento dell'app. Aperte **13** (Gruppo 2 = 2: A2, A6).
- **Stato al 2026-10-17, parte 4 sprint 4a della v1 (visualizzatore 41,
  prima fetta):** scritti `src/astrotwo/ui/sky_viewer.py` (`SkyViewer`,
  `SkyRenderer`, `TilePool` con 6 thread e annullamento per generazione) e
  `src/astrotwo/ui/sky_renderer_gl.py` (`GlSkyRenderer`, OpenGL 4.1 core su
  `QOpenGLWidget`, solo funzioni di PySide6): sfondo HiPS di un survey a
  colori (JPEG/PNG) con `view_sampling`/`fetch_tile`/`fill_view` del 12,
  zoom con rotella e pizzico, trascinamento, comandi `view.set_zoom` e
  `view.set_center` a fine gesto (300 ms), vista iniziale a cielo intero,
  scritta "survey · proiezione · campo" nella barra, modalità notte nel
  disegno. Scelte del proprietario del 2026-10-17: vista iniziale (ICRS
  0°, 0°; scala 360°/larghezza), zoom 2^(1/4) per scatto con limiti
  0.01″/pixel e 360°/larghezza, campo con cifre fisse, `field_of_view`
  della geometria disegnata nel risultato del 05. **D40-4 decisa (⌃⌘N).**
  Barra di stato ad altezza fissa (26 px) perché il cielo non cambi
  dimensione a ogni comando. Test: 633 di default e il test `gl` passano.
  Decisioni aperte: **14** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 11).
- **Stato al 2026-10-17, parte 3b della v1 (correzioni dell'aspetto del
  40 dopo la prova del proprietario; nessuna funzione nuova, comandi
  invariati):** foglio di stile dai colori dei mockup, icone Lucide nel
  colore del tema (licenza verificata: ISC, più MIT di Feather per le icone
  derivate, in `THIRD_PARTY_LICENSES`), intestazioni dei pannelli come nel
  mockup, stati vuoti dei segnaposto con il testo di cosa arriverà, pulsanti
  della barra per azioni già nei menu (anche **Night mode**, che era solo nel
  menu View). **Aperta D40-4** (scorciatoia della modalità notte, Gruppo 3,
  raccomandazione ⌃⌘N). Decisioni aperte: **15** (Gruppo 1 = 0, Gruppo 2 =
  3, Gruppo 3 = 12).
- **Stato al 2026-10-17, parte 3 della v1 (finestra 40):** scritti
  `src/astrotwo/ui/main_window.py` (finestra, menu, barra di stato, "Vai
  a", pannelli Comandi e Messaggi, coda dei comandi in un `QThread` con
  avanzamento e Annulla, preferenze, aspetto sistema/scuro/chiaro/notte
  rossa, inglese e italiano con il punto decimale sempre), la traduzione
  italiana (`ui/i18n/`) e i test `tests/ui/` (T1–T14 del 40; T15 con il
  44); avvio con `uv run astrotwo`. Decisioni del proprietario dello stesso
  giorno: **D05-2 precisata** (impronta = SHA-256 del contenuto restituito
  dal modulo), confermate le scelte minori del 05 sul tipo `time` e sul
  parametro `window` dei comandi di vista; VizieR TAP (HTTP 503 da giorni)
  **endpoint invariato** (`https://tapvizier.cds.unistra.fr/TAPVizieR/tap`,
  guasto temporaneo del bilanciatore del CDS: rispondono 503 anche la
  pagina `adql/about.html` e gli altri nomi del servizio), nessuna modifica.
  Spazi riservati per 41, 42 e 44 fino alle loro parti.

- **Stato al 2026-10-16, dopo l'approvazione:** il proprietario ha
  confermato le 32 scelte minori come raccomandate tranne una (servizio
  del Portachiavi `dev.pages.astrotwo.ai`; identificativo del progetto e
  bundle identifier `dev.pages.astrotwo` in `01` §6), ha **approvato 05,
  30, 31, 32, 34, 35, 40, 41, 42, 44** e le modifiche al 10, e ha dichiarato
  **"FASE: CODICE – interfaccia v1"**. Prima del codice: verifiche e
  allineamento del codice del livello 1 (10, 11, 12, 18), poi proposta di
  divisione del codice della v1.

- **Stato al 2026-10-16: specifiche dell'IA nella v1 (nessun codice
  applicativo).** Proposta della fase 1 sull'IA approvata dal proprietario
  il 2026-10-16 con precisazioni. Scritti in `bozza` **30** (adattatore:
  SDK `anthropic` e `openai` con endpoint configurabile, nessun modello nel
  codice, `AI_NO_TOOLS`, tempi 10/60/30 s), **31** (`keyring` forzato sul
  solo Portachiavi di macOS, nessun ripiego), **32** (elenco esplicito di
  comandi del `05`, nomi `view__go_to`, stessa coda con `requested_by =
  ai`, risultati ≤ 50 righe e 20 kB), **34** (verifica di ogni numero della
  risposta, elenco chiuso delle eccezioni, modalità rigorosa con una
  rigenerazione), **35** (ciclo degli strumenti, regole di sistema R1–R9,
  10 comandi e 5 minuti per risposta, token e prezzo facoltativo, privacy,
  comandi nella sessione e testo solo su richiesta), **44** (pannello a
  destra). **Sicurezza:** testi esterni sempre dati, mai istruzioni;
  conferma obbligatoria per i comandi chiesti dopo un testo esterno; test
  di prompt injection nel 34 e nel 35. 33 rimandato (al suo posto
  `catalog.search`). Modificati 05, 40, 41 (A7 nella v1), 42 (cifre della
  tabella) e gli approvati 01, 02, 03, 10 (`compass_and_scale_bar`) e
  `CLAUDE.md` (formula di fase estesa). **Regola dei commit:** HTTP 429,
  502, 503, 504 contano come connessione (`02` §8, `tests/conftest.py`,
  `scripts/commit_checked.py`). Nessuna decisione nuova dei Gruppi 1–3:
  solo scelte minori da confermare nei §13. Decisioni aperte: **14**
  (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 11).

- **Stato al 2026-10-15, dopo le decisioni del proprietario sulle specifiche
  dell'interfaccia (nessun codice):** decise D05-1 (tre classi di comandi),
  D05-2 (avviso senza fermarsi; impronta dei risultati di rete di ogni
  comando nella sessione), D40-1 (v1: codice + testo del modulo), D41-1
  (puntatore Simbad nel gruppo di thread dei tile), D41-2 (nuova
  `format_coordinates` nel 10, cifre di DC3), D41-3 (nuova
  `suggest_display_limits` nell'11 con `ZScaleInterval`), D41-4 (`perf` e
  `gl` esclusi di default, `gl` blocca, `perf` si riporta; Mac di
  riferimento da compilare); D05-3 e D40-2 rimandate; nuova D40-3 (Gruppo
  3, messaggi dei moduli in inglese con traduzione); scelte minori di 05,
  40, 41, 42 confermate. **Linee guida visive** nel `40` §3.11 (valide per
  tutte le interfacce) e **mockup** in `mdfiles/mockup/` (tema scuro e
  modalità notte rossa). PySide6/Qt (LGPL-3) registrata per A11 e per il
  `60`. 10 e 11 modificati (restano `approvato`). **05, 40, 41, 42 senza
  decisioni dei Gruppi 1 e 2 aperte**: l'approvazione spetta al
  proprietario. Decisioni aperte: **14** (Gruppo 1 = 0, Gruppo 2 = 3,
  Gruppo 3 = 11).

- Stato precedente, sempre il 2026-10-15: **specifiche della prima versione dell'interfaccia
  (nessun codice).** Proposta della fase 1 approvata dal proprietario il
  2026-10-15 con precisazioni. **AM1 accettata:** nuovo file generale
  **`05-comandi-sessione.md`** (livello 1, codice previsto in
  `src/astrotwo/core/commands.py`): comandi con nome, versione, parametri
  tipizzati con unità, descrizioni EN/IT, risultato strutturato e
  indicatori; schema JSON per il 32; sessione JSON senza pixel, riapertura
  = riesecuzione, stop se lo SHA di un file è cambiato; gesti registrati a
  fine gesto dopo 300 ms fermo; `run_command` del 18 come adattatore.
  **Scritti in `bozza`:** `05`, `40` (finestra, menu, barra di stato,
  preferenze essenziali, cronologia, messaggi, coda dei comandi in un
  thread di lavoro con avanzamento e Annulla, spazio per il 44), `41`
  (immagine, HiPS, cataloghi, MOC, griglia, coordinate sotto il mouse,
  distanza, puntatore Simbad, livelli minimi, PNG; `QOpenGLWidget` dietro
  un'interfaccia di disegno nostra; obiettivi P1–P7 con marcatori `perf` e
  `gl`; lista di controllo manuale), `42` minimo (tabella ordinabile,
  selezione sincronizzata, record). **Decise:** A9, D10-9 (30°, ±10 % nel
  41), D11-8 (corona 1 × / 1,5 × `box_size`, box 15 pixel), raggio del
  puntatore Simbad (12 pixel logici, 500 ms, una richiesta alla volta).
  **File approvati modificati** (restano `approvato`): 01 (A9, prestazioni
  nel 41, riproducibilità nel 05), 02 (tabella specifica ↔ codice, test
  dell'interfaccia; corretto `measures.py`), 03 (note v1, `05` in A12, E8,
  H13), 10 (`make_view_wcs`, default 30°), 11 (default della corona), 12
  (P6, tile sulla vista), 13 e 17 (sessione del 05 per D17-3), 18
  (adattatore); `CLAUDE.md` (formula di fase dell'interfaccia). **Codice
  da allineare** quando il proprietario lo chiede: `make_view_wcs` e
  default di `choose_projection` (10), default della corona (11), P6 (12);
  adattatore del 18 dopo l'approvazione del 05. **Verifiche prima del
  codice:** cache del 04 da più thread (05, 41), funzioni OpenGL di
  PySide6, funzioni HiPS di `reproject`, licenze di PySide6/Qt e pytest-qt.
  Decisioni aperte: **20** (Gruppo 1 = 0, Gruppo 2 = 9, Gruppo 3 = 11).
  Test: 494 di default (nessun codice cambiato).

- **Stato al 2026-10-14, dopo D16-8:** **MOC da immagine con i blocchi
  (16, D16-8 decisa):** blocchi di b × b pixel più gli angoli dei pixel lungo
  il contorno della regione dei blocchi validi; crescita ai bordi ≤ b − 1
  pixel; dimensione del blocco dichiarata. Test su 300 maschere casuali
  contro il MOC pixel per pixel (nessuna cella persa) e, in rete, sulla DSS
  della demo (MOC identico, 4,1399 deg²). `moc_from_image` sulla DSS da
  10,3 s a 0,21–0,27 s; demo a cache calda da 18,5–19,5 s a 8,5–9,5 s;
  valori del report invariati. **D14-13 aperta** (Gruppo 3): servizi
  dell'ESO in http con reindirizzamento a https che codifica due volte
  l'URL; la demo usa https, nessuna modifica al 14. 16 e 14 modificati,
  restano `approvato`. Test: **494 di default**. Decisioni aperte: **14**
  (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 10).

- Stato precedente, sempre il 2026-10-14: **`display_positions` nel 13** (decisione del
  proprietario del 2026-10-14; 13 modificato e resta `approvato`): D10-2 in
  un passo (epoca dell'immagine se nota, altrimenti J2000, o dell'utente,
  con la fonte), posizioni, righe disegnabili, conteggi per modo e
  spostamento; T34. La demo delle Pleiadi la usa per stelle e frecce del
  moto proprio (frecce dalle posizioni all'epoca di visualizzazione);
  valori del report invariati (spostamento medio 0,880″, massimo 2,165″).
  **MOC da immagine con i blocchi (16): non applicato**, la regola decisa
  perde celle sul bordo → **D16-8 aperta** (Gruppo 3) con raccomandazione
  (aggiungere gli angoli dei pixel sul contorno). Test: **492 di default**.
  Decisioni aperte: **14** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 10).

- **Primo test con dati veri (2026-10-13): demo delle Pleiadi** in
  `examples/demo_pleiadi.py` (con `examples/README.md`; uscite in
  `examples/output/`, esclusa da git): solo funzioni pubbliche del livello 1
  (10, 11, 13, 14, 15, 16, 17, 18), nessun calcolo nello script. Immagine
  DSS2-red con il SIA del 14 (servizio dell'ESO trovato nel registro VO) e
  `load_image` dell'11; Gaia DR3 e 2MASS con `tap_query`; crossmatch 2″:
  190 su 193 (98,45 %); Alcyone–Atlas 23,185′, PA 97,61°; moto proprio medio
  dei probabili membri (parallasse 6,5–8,5 mas, 95 stelle) +19,28 / −44,54
  mas/anno; 193 stelle su 193 nel MOC dell'immagine. **Difetto trovato:** testo
  di `filter_by_moc` (16) "righe dentrol MOC", riprodotto con un test e
  corretto. Test di rete della demo in `tests/test_demo_pleiadi.py`.

- **Stato al 2026-10-13, dopo le ultime decisioni del proprietario: livello 1
  chiuso.** D17-9 decisa e scritta (`distance_to` per freccia e tracciato
  aperto come archi di cerchio massimo, per l'ellisse minimo numerico sul
  bordo con precisione dichiarata, testo escluso); D19-9 decisa e scritta
  (PDS4 da URL con la rete del 14 e la cache comune); **D19-8 rimandata**
  (PDS3 non ancora supportato, bassa priorità); H10 SkyView resta rinviato;
  scelte minori di 18 (`colon_units`, UT1 con `iers_table`) e 19 (§3, 1–9)
  confermate; 04 con 18 e 19 tra gli utenti della cache; testo di licenza di
  `pims` trovato nel sorgente ufficiale su PyPI e aggiunto a
  `THIRD_PARTY_LICENSES` (segnaposto `<COPYRIGHT HOLDER>` non compilato, da
  valutare con A11). Test: **491 di default**. Decisioni aperte: **13**
  (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 9).

- Stato precedente, sempre il 2026-10-13 (decisioni del proprietario del
  2026-10-13): **livello 1 scritto per intero, moduli 04 e 10–19.** Chiusi D17-8
  (`distance_to`: distanza angolare minima, cerchi con Astropy, poligoni
  con la distanza punto–arco) e D18-7 (sessagesimali di `skydist` con
  l'unità scritta nel testo, due punti solo con `colon_units`); creato
  **`THIRD_PARTY_LICENSES`** nella radice (generato da
  `scripts/third_party_licenses.py`, controllato da un test; regola: ogni
  nuova dipendenza va aggiunta lì, `01` §6); lettura del valore grezzo di
  un pixel spostata nell'11 (`read_raw_pixel`); UT1 con le tabelle IERS
  incluse in astropy, `IERS_RANGE` fuori copertura, aggiornamento solo su
  richiesta (`update_iers_table`, rete del 14); **modulo 19 scritto in
  P0–P4** (`planetary_data.py`; nuove dipendenze `spiceypy` 8.3.0 MIT e
  `pds4-tools` 1.4 BSD-3, kernel `pck00011.tpc` della NAIF incluso senza
  modifiche; tabella dei nomi dei corpi D12-6, applicata anche al 12).
  Pezzi fermi: nel 12 H10 SkyView; nel 17 `distance_to` per ellisse,
  freccia, testo e tracciato aperto (D17-9); nel 19 PDS3 (D19-8) e PDS da
  URL (D19-9). Test: **485 di default, 505 con la rete**, tutti superati.
  Decisioni aperte: **15** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 11).

- Stato del codice al 2026-10-10: base del progetto (`pyproject.toml` con
  Python 3.12 e `uv`, `uv.lock`, `src/astrotwo/` con i sotto-pacchetti,
  `tests/` specchiato). **Completi secondo la definizione di "fatto" di
  `CLAUDE.md`: `04` (cache comune, `cache.py`), modulo 10
  (`coordinates_wcs.py`) e modulo 11 (`images_fits.py`, scritto in 7 parti
  P1–P7, un commit per parte).** Dipendenze dichiarate: `astropy`,
  `astroquery`, `numpy`, `scipy`, `requests`, `pyvo`, `pillow`,
  `matplotlib` (palette; porta `contourpy`), `reproject`; `pytest` per i
  test; licenze verificate, tutte permissive salvo WCSLIB (LGPL-3, vedi
  sotto). **Modulo 14 (`vo_protocols.py`) scritto in 7 parti P1–P7** e,
  il 2026-10-11, con i pezzi fermi chiusi (D14-10 ECSV, D14-11
  `sia_calibration` con il parametro `calibration` dell'11, D14-12
  magnitudini SIMBAD; registro VO di default `https://dc.g-vo.org/tap`).
  **Modulo 13: P1–P6 scritte per intero** (D13-17 `LINK` ASTRORES, D13-18
  albero delle collezioni dal MocServer, `load_catalog` con
  `allow_partial`, `region` con UCD di `TAP_SCHEMA` e `COOSYS`); fermo
  solo la regione su SIMBAD (D13-20); traduzione UCD1 del CDS rimandata
  (D13-14c). **Modulo 15 (`crossmatch.py`) scritto in 5 parti P1–P5**
  (incrocio locale, tabella unita, per campo, ellissi, CDS XMatch), fermi
  poi chiusi il 2026-10-11 (D15-8 corpo nel join, D15-9 `selection=all`).
  Nel 13 chiusa D13-20 (sistema di SIMBAD dall'`utype` MANGO). **Modulo 16
  (`moc.py`) scritto in 5 parti P1–P5 il 2026-10-11** (classe `Moc`, FITS
  IVOA 1.0/1.1/2.0, JSON e testo, operazioni; creazione da cerchio,
  poligono, catalogo, immagine; filtro e mappe/griglie HEALPix; MOC
  temporali in TCB e spazio-temporali, mappe di probabilità e regioni di
  credibilità; MocServer, lettura da URL, `build_moc`); il 2026-10-12
  D16-6 (nessuna 2.1 tra i documenti IVOA, resta rifiutata) e D16-7
  (complemento degli ST-MOC con `mocpy`) decise e scritte, con il corpo
  misto delle operazioni forzate e i MOC planetari in FITS con `A2BODY`.
  **Modulo 12 (`hips.py`) scritto in 5 parti P1–P5 il 2026-10-12**
  (metadati HiPS 1.0 e `add_hips`; tile, cache, copertura, memoria 512 MB e
  valore del pixel dai tile FITS; collezioni dal MocServer e `set_survey`
  con `CDS/P/DSS2/color`; cubi e cataloghi progressivi; `build_hips` con
  `reproject_interp` su un WCS APE 14 del tile); il 2026-10-12 decise dal
  proprietario D12-6 (nomi dei corpi con una tabella del 19), D12-7
  (eclittica non supportata finché non verificata), D12-8 (nessun Allsky per
  ora), H10 SkyView rinviato finché NASA non documenta l'URL SIA; le risposte del MocServer
  si leggono in ISO-8859-1 come dichiarato (corretti anche 14 e 16, ora
  scritto anche nelle loro specifiche). **Modulo 17 (`measures.py`) scritto
  il 2026-10-12 in P1, P2, P4** (distanza con `skydist` del 13, angolo di
  posizione con i casi indefiniti, offset e calcolo inverso; lettura dei
  pixel, profili bilineari con `scipy.ndimage.map_coordinates` e passo
  obbligatorio, distanza con profilo; distanza automatica tra due sorgenti
  di catalogo con epoca propagata dal 13/10 e controllo del corpo) **e P3
  (forme e tag) il 2026-10-12 con D17-7** (cerchio esatto con Astropy,
  ellisse sferica con area integrata e stima dell'errore dichiarata,
  poligoni e tracciati chiusi con **`spherical-geometry` 1.4.0**); fermo
  solo `distance_to` (D17-8). **Modulo 18 (`calculators.py`) scritto in 5
  parti P1–P5 il 2026-10-12/13** (espressioni con `ast` a elenco chiuso,
  tempo, unità, pixel con il valore grezzo dal file, coordinate con 10 e
  17; comandi registrati rieseguibili); fermi solo i sessagesimali in
  `skydist` (D18-7). Nel 10 aggiunte
  `proper_motion_only` e `parse_sexagesimal`. Dipendenze nuove:
  `defusedxml` 0.7.1 (PSF), **`mocpy` 0.20.0 e `astropy-healpix` 2.0.1
  (BSD)**, **`spherical-geometry` 1.4.0 (BSD-3-Clause, con la libreria QD
  di LBNL, BSD modificata: avviso da riportare nel `.dmg`, da verificare
  con A11)**; **`healpy` escluso (GPL-2.0)**. Test: **457 di default, 474 con
  la rete (17 test di rete, tutti superati), 0 saltati** (2026-10-13). Regole dei test di rete e dei commit in
  `02-convenzioni.md` §8 punti 8–9: commit solo con
  `scripts/commit_checked.py`, che esegue i test e chiama `git commit` solo
  se l'esito lo consente.
- **Vincolo per `60-distribuzione-dmg.md`:** WCSLIB, incluso in astropy, è
  **LGPL-3**; tutte le altre dipendenze sono permissive (BSD, MIT, Apache,
  MPL-2.0 per `certifi`). Gli obblighi LGPL per il `.dmg` vanno specificati
  nel 60.

Regole della fase specifiche (livelli 2, 3, 4, interfaccia, distribuzione):

- Si scrivono e si approvano solo file `.md` in `mdfiles/`.
- Nessun codice applicativo prima che il proprietario dichiari per iscritto
  "FASE: CODICE".
- Solo i file con stato `approvato` autorizzano a scrivere il codice del modulo corrispondente.
- Regole complete in `CLAUDE.md`; modello dei moduli in `TEMPLATE-modulo.md`.

Stato al 2026-10-04: creati i file generali (panoramica, indice, architettura,
convenzioni, parità con Aladin) e il template. Prese le decisioni A3, A4 e A7
(struttura del codice, Python e dipendenze, cache); **il 2026-10-04 sono state
decise anche A1 (PySide6) e A5 (provider IA)**; rimandate A8 (scripting
Aladin) e AP1 (validazione parità). Elenco completo in §5 e §6.

Sempre al 2026-10-04: **gruppo nucleo scritto** — gli 8 file `10–17` sono in
stato `bozza` (coordinate/WCS, immagini FITS, HiPS, cataloghi, protocolli VO,
cross-match, MOC, misure). Restano 24 file di modulo da scrivere (`18`,
20–24, 30–35, 40–45, 50–53, 60–61); `18` e `45` sono registrati con stato
`non esiste` (accettati in AM1).

Sempre al 2026-10-04: completata la **prima verifica documentale** di
`03-parita-aladin.md` (manuale utente Aladin Desktop ed. giugno 2022 sezioni
1–5.8, manuale script v12.0, FAQ): 58 righe in A–G (19 `nota`, 23 `verificata`,
12 `corretta`, 4 `non trovata`), 16 funzioni nuove trovate e messe in sezione H,
1 funzione extra AstroTwo (allora D12, rientrata nella sezione D il 2026-10-04:
vedi esito parziale di AP5 qui sotto). **AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08**; esito
parziale 2026-10-04 qui sotto. Dalla
verifica sono emerse due proposte di nuovo modulo in AM1,
**accettate il 2026-10-04** (AM1 decisa: `18-core-calcolatrici.md` da H4,
`45-ui-viste-multiple.md` da H2 — vedi §6 e §8).

Sempre al 2026-10-04: **decisione del proprietario P11** — la parità con Aladin
è il minimo, non il traguardo: AstroTwo include tutte le funzioni di
`03-parita-aladin.md`, anche quelle non confermate nella documentazione. Le 4
righe `non trovata` (C3 HiPS da ID/URL, F2 position angle, G3 invio a strumenti
esterni, E4 spettri SSA) passano a `inclusa (decisione del proprietario)`; nei
moduli 12, 17 e 14 le funzioni sono descritte per intero e restano aperte solo
verifiche tecniche di implementazione.

Sempre al 2026-10-04: **decisioni del proprietario su tutto il Gruppo 1 di
`decisioni-aperte.md`** — le 22 decisioni che bloccavano altri moduli sono
tutte decise (A1, A5, AP5, D10-2 … D17-4; esiti in §5, dettagli nei file di
origine e in `decisioni-aperte.md` §3). Restano 25 decisioni aperte (Gruppo 2
= 20, Gruppo 3 = 5). Impegno collegato: **AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08**,
prima di scrivere il gruppo analisi (20–24).

Sempre al 2026-10-04: **esito parziale di AP5 e correzioni in
`03-parita-aladin.md`** (fonte: manuale utente Aladin Desktop **edizione
febbraio 2021**, lette **sezioni 1–5.7.2 e l'indice completo**). **AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08**; l'esistenza di tutte le
funzioni elencate è però verificata dall'indice. **D12 corretta:** in Aladin
l'estrazione di sorgenti **esiste** (sezione 6.6, ed. giugno 2022) **tramite il programma
esterno SExtractor** → la riga D12 è tornata nella sezione D come `verificata`
(in AstroTwo estrazione **nativa** nel modulo 20, senza programmi esterni,
libreria da decidere) e la sezione "funzioni extra" è ora senza righe. Aggiunte
in H: **H17** strumento Exam (5.10, ed. giugno 2022), **H18** avvio
tramite URL (7.2 dell'ed. febbraio 2021, sezione assente nell'ed. giugno 2022), **H19** interfacce VOApp/VOObserver
(7.4, ed. giugno 2022) — tutte con "dettagli da leggere" e modulo
proposto. Note su **A13** (stampa, 5.19, ed. giugno 2022), **B11** (mosaici e sequenze animate
con blink), **E4** (vecchia FAQ: Aladin mostra gli spettri con programmi
esterni via SAMP; AstroTwo li mostra nel modulo 21), **F4** (fotometria su HiPS:
in Aladin solo con cerchio manuale e alla risoluzione della vista; AstroTwo
dichiara la risoluzione usata e, se possibile, misura alla risoluzione nativa).
In `01-architettura.md` §8 nuovo **requisito non funzionale**: obiettivi di
prestazioni (righe di catalogo, dimensione di immagini e cubi) **almeno pari ad
Aladin** (sezione 8.3 del manuale, ed. giugno 2022, da leggere) da definire in
`61-strategia-test.md`. In `INDICE.md` la voce di
`24-analisi-pipeline-riproducibili.md` annota il principio: in Aladin la
cronologia dei comandi registra anche le azioni con il mouse come comandi di
script; **AstroTwo adotta lo stesso principio (ogni azione dell'interfaccia =
un comando registrato)**.

Al 2026-10-08: **manutenzione delle specifiche** (nessun modulo nuovo, nessuno
stato cambiato). `AGENTS.md` sostituito da `CLAUDE.md` nella cartella radice e
in tutti i riferimenti; intervalli dei moduli allineati ad AM1 (nucleo
**10–18**, interfaccia **40–45**) in `01-architettura.md` e qui in §3;
riferimento AP5 uniformato a **5.7.3–8**; refusi corretti in `01` e `02`.
Nuova decisione aperta **AP6 — edizione di riferimento del manuale di
Aladin** (giugno 2022 o febbraio 2021), decisa lo stesso giorno (sotto).

Sempre al 2026-10-08: **decisioni del proprietario sui punti aperti della
manutenzione.** **AP6 decisa:** edizione di riferimento = la più recente
ufficiale del manuale utente di Aladin Desktop; verifica sul sito del CDS →
**giugno 2022** (nessuna edizione più recente). Accanto ai numeri di sezione
del manuale è indicata l'edizione; dove nell'edizione giugno 2022 numero o
titolo è diverso (A13 5.18, D12 6.5, H17 5.9, H18 7.2, H19 7.5) è marcato
"numerazione da verificare", senza correggere. `decisioni-aperte.md`
completato con AP1–AP4 e con la parte aperta di DC1, DC3, DC4 (AP1 nel Gruppo
3 con A8): **32 decisioni aperte** (Gruppo 1 = 0, Gruppo 2 = 25, Gruppo 3 =
7). AP5 scritta ovunque come "AP5 decisa; lettura delle sezioni 5.7.3–8
ancora da fare". Test T3/T4 di `03` estesi a 10–18; D14-6 rinominata
"inclusione decisa; parte tecnica aperta"; calcolatrici (18) aggiunte al
nucleo in §3; refusi corretti in questo file e in `03`.

Sempre al 2026-10-08: **numeri di sezione riportati all'ed. giugno 2022**
(A13 → 5.19, D12 → 6.6, H17 → 5.10, H19 → 7.4; tolta la marcatura
"numerazione da verificare"). **H18**: la sezione 7.2 "Launch of Aladin by
URL" dell'ed. febbraio 2021 non esiste nell'ed. giugno 2022 (lì 7.2 = avvio da
riga di comando; l'avvio da URL compare solo nella sezione 2 "Installation"):
riga mantenuta per P11. **AP5** ora: "AP5 decisa; lettura delle sezioni 5.9–8
(ed. giugno 2022) ancora da fare" (con l'ed. giugno 2022 le sezioni 1–5.8
risultano già lette). **AP3 decisa:** Aladin Lite escluso dalla parità (app
desktop; versione web → proposta AM1). Smistamento dei gruppi confermato:
**31 decisioni aperte** (Gruppo 1 = 0, Gruppo 2 = 24, Gruppo 3 = 7).

Sempre al 2026-10-08: **lettura AP5 completata** — lette le sezioni 5.9–8 del
manuale utente ed. giugno 2022 e integrate in `03-parita-aladin.md`: note con
sezione ed edizione su 20 righe; **correzioni** di D12 (SExtractor eseguito su
un server remoto del CDS), E3 (correlazione anche per campo e per ellissi
d'errore) e F4 (le serie temporali esistono in Aladin, sez. 5.10 e 5.12);
dettagli di H17 (puntatori Simbad e VizieR con SED), H18 e H19; **8 nuove
righe H20–H27** (mappa cliccabile, dati planetari, formati e riconoscimento dal
contenuto, SIA/SIA2, cubi HiPS, convenzione dei pixel FITS, MocServer, immagini
di qualsiasi dimensione) → 86 righe in tutto. **Nuova proposta AM1: H21, dati
planetari** (nessun file creato). Decisioni aperte: **32** (Gruppo 1 = 1,
Gruppo 2 = 24, Gruppo 3 = 7). Nessun modulo del gruppo analisi è stato scritto:
si attende la validazione del proprietario.

Sempre al 2026-10-08: **decisioni del proprietario sugli esiti di AP5.**
**AM1 accettata per H21:** nuovo modulo `19-core-dati-planetari.md` (livello
1, stato `non esiste`) → il nucleo è ora **10–19**. In `01-architettura.md` §8
**obiettivo minimo di prestazioni: almeno 1 milione di sorgenti di catalogo con
1 GB di RAM** (manuale Aladin ed. giugno 2022, sez. 8.3; test in `61`). In
`10-core-coordinate-wcs.md` **D10-4 precisata** con le proiezioni del manuale
(SIN, TAN, AIT, ZEA, STG, CAR, NCP, ZPN; un test per proiezione). In
`02-convenzioni.md` nuova **DC7: convenzione dei pixel** FITS (indice da 1)
contro numpy (indice da 0) con regola di conversione unica nel modulo 10.
**H17:** la SED si costruisce nel modulo 20, ogni punto con origine
dichiarata. **H19:** equivalente di VOApp = API Python nel 24 + SAMP nel 14,
nessuna interfaccia nuova. Decisioni aperte: **31** (Gruppo 1 = 0, Gruppo 2 =
24, Gruppo 3 = 7).

Sempre al 2026-10-08: **scritti `18-core-calcolatrici.md` e
`19-core-dati-planetari.md`** (stato `bozza`, 14 sezioni ciascuno): il nucleo
10–19 è ora tutto in bozza. Il 18 copre le cinque calcolatrici di Aladin (sez.
5.7) richiamando i moduli 10, 11, 13 e 17 senza riscriverne le funzioni; il 19
copre i dati planetari con corpo mai assunto e nessuna sovrapposizione tra
corpi diversi o tra dati celesti e planetari. Nuove decisioni aperte: D18-1…
D18-6 e D19-1…D19-7 → **44 aperte** (Gruppo 1 = 2: D19-2, D19-3; Gruppo 2 =
33; Gruppo 3 = 9; smistamento proposto, da confermare). Nessun modulo del
gruppo analisi è stato scritto.

Al 2026-10-09: applicate le **decisioni del proprietario del 2026-10-08** —
smistamento delle 13 decisioni di 18 e 19 confermato; **D19-3**: campo `body`
obbligatorio nei metadati dei moduli 12, 13, 14 e 16 (`celestial` per i dati
astronomici, ricavato dal sistema di coordinate, mai assunto); **D19-2**: PDS
letto nel 19, PDS4 obbligatorio, PDS3 solo con libreria consolidata (resta
aperta `D19-2b`, libreria e licenza); **D19-4**: sovrapposizione tra corpi
diversi = errore di default, forzabile con opzione esplicita citata nel
risultato; **DC7 confermata** e nuova funzione `convert_pixel_convention` nel
modulo 10 (test T8–T11); `CLAUDE.md` aggiornato (nucleo 10–19, nota su
`AGENTS.md`, regole su pixel e corpo). Decisioni aperte: **42** (Gruppo 1 = 0,
Gruppo 2 = 33, Gruppo 3 = 9).

Sempre al 2026-10-09: **checklist di approvazione del livello 1 decisa dal
proprietario.** Accettate 30 raccomandazioni (DC1, DC3, DC4, AP2, D10-1,
D11-2, D11-4, D11-5, D12-1, D12-3, D12-4, D13-3, D14-3, D14-4, D14-6,
D15-1…D15-4, D16-4, D17-6, D18-1…D18-4, D19-1, D19-2b, D19-5, D19-6, D19-7),
scritte nei file di origine; le verifiche "da verificare" restano vincoli
prima del codice di ciascun modulo. A2, A6, A9 non bloccano il livello 1:
bloccano `60` (A2, A6) e `40` (A9), con orientamento registrato. D19-3 esteso
al modulo 15 (crossmatch: `BODY_MISMATCH` forzabile come D19-4). Nuove
decisioni del Gruppo 3: A10 (tetti di memoria) e D10-6 (prestazioni delle
conversioni di massa). `CLAUDE.md`: la fase codice si dichiara **per
livello** ("FASE: CODICE – livello N"). Decisioni aperte: **14** (Gruppo 1 = 0,
Gruppo 2 = 3, Gruppo 3 = 11). **Nessuna decisione dei Gruppi 1 e 2 blocca più
01, 02, 03 e 10–19**, ma i file **restano in bozza**: le funzioni emerse dalla
lettura AP5 e assegnate ai moduli 11–17 (H22, H23, H24, H26, H27, E3, F1) non
sono ancora descritte in quei moduli; l'approvazione attende l'indicazione del
proprietario.

Sempre al 2026-10-09: **approvati 01, 02, 03, 10, 18 e 19** (decisione del
proprietario). **Moduli 11–17 completati** con le funzioni assegnate dalla
lettura AP5 (11: H22, H27, B11, H25; 12: H24, H26, H27; 13: H22, H8; 14: H23,
H17, H19, H14; 15: E3; 16: H22, H26; 17: F1) e **10 completato** con H25
(calibrazioni storiche DSS1, supporto da verificare). Verifica di copertura di
`03` sui moduli 10–19: nessun'altra funzione mancante. **Approvati anche 12, 16
e 17**; restano **in bozza 11, 13, 14 e 15** per nuove decisioni del Gruppo 2
(D11-6, D13-7, D14-7, D14-8, D15-5). Decisioni aperte: **20** (Gruppo 1 = 0,
Gruppo 2 = 8, Gruppo 3 = 12).

Sempre al 2026-10-09: **livello 1 interamente approvato.** Decise dal
proprietario D11-6 (`Pillow`), D13-7 e D14-8 (lettori ASTRORES e IDHA con
`defusedxml`, testati su esempi del CDS, altrimenti solo errore), D14-7
(nessun sistema di plugin nel livello 1: estensioni tramite l'API Python del
24, parte "plugin" di H14 spostata nel 24 anche in `03`), D15-5 (distanza di
Mahalanobis con covarianza combinata, soglia in sigma; nuova D15-6 nel Gruppo
3); **framework dei test `pytest`** (anticipato da 61, registrato in `01` e
`02` §8). **Approvati 11, 13, 14 e 15**: ora sono `approvato` 01, 02, 03 e
10–19. Decisioni aperte: **16** (Gruppo 1 = 0, Gruppo 2 = 3: A2, A6, A9 per
`60`/`40`; Gruppo 3 = 13). Nessun livello in fase codice: serve la
dichiarazione "FASE: CODICE – livello 1".

## 3. Struttura a 4 livelli

Regola n. 7 di `CLAUDE.md`: il progetto è a livelli e deve funzionare sempre.
Un livello superiore non rompe mai quello inferiore; se un livello superiore
fallisce, i livelli sotto continuano a funzionare.

| Livello | Nome | Cosa contiene | Moduli |
|---|---|---|---|
| 1 | Nucleo | tutto ciò che Aladin già fa: coordinate/WCS, immagini FITS, HiPS, cataloghi, protocolli VO, cross-match, MOC, misure, calcolatrici, dati planetari | 10–19 |
| 2 | Analisi | fotometria, spettroscopia, curve di luce, cubi di dati, pipeline riproducibili | 20–24 |
| 3 | IA | adattatore provider, chiavi nel Portachiavi, registro strumenti, query ADQL, verifica risultati, assistente chat | 30–35 |
| 4 | Funzioni avanzate | transienti, multi-messaggero, collaborazione, vista 3D | 50–53 |
| — | Interfaccia | UI (attraversa i livelli, ma senza logica scientifica propria) | 40–45 |
| — | Distribuzione e test | pacchetto `.dmg`, strategia dei test | 60–61 |

Direzione delle dipendenze: `4 → 3 → 2 → 1`; l'interfaccia chiama i livelli ma
non viene chiamata da nessuno; il livello 1 non dipende da nulla di sopra.

**Regola d'oro n. 1 (riassunto):** l'IA non calcola mai. Ogni numero mostrato
all'utente viene da codice deterministico e testato; l'IA interpreta richieste,
sceglie gli strumenti e spiega i risultati. Ogni modulo che produce numeri deve
dichiarare libreria o algoritmo deterministico responsabile del calcolo.

## 4. Tabella dei moduli

Stati: `non esiste` (file non ancora scritto) → `bozza` → `in revisione` → `approvato`.

| File | Titolo | Livello | Stato |
|---|---|---|---|
| `TEMPLATE-modulo.md` | Modello obbligatorio per ogni modulo | — | bozza |
| `panoramica.md` | Questo file | — | bozza |
| `INDICE.md` | Elenco di tutti i file con stato | — | bozza |
| `riassunto.md` | Il progetto in 5 righe: cos'è, struttura, regole d'oro, stato, prossimi passi | — | bozza |
| `01-architettura.md` | Architettura generale e scelte tecniche | — | approvato |
| `02-convenzioni.md` | Convenzioni di documentazione, nomi, unità, test | — | approvato |
| `03-parita-aladin.md` | Funzioni di Aladin e modulo coprente | — | approvato |
| `04-cache.md` | Cache A7 comune (`~/Library/Caches/AstroTwo/`, un solo limite di 5 GB, timeout 10 s / 60 s, origine e data; nessuna cache propria nei moduli), usata da 10–14, 16, 18 e 19 | 1 (generale) | approvato |
| `05-comandi-sessione.md` | Registro dei comandi e sessione (AM1 accettata il 2026-10-15): comandi tipizzati con unità e risultato strutturato, sessione JSON rieseguibile senza pixel, schema JSON per il 32; usato da 40, 41, 42; **codice scritto il 2026-10-17** (`core/commands.py`, 39 comandi, parte 1 della v1) | 1 (generale) | approvato |
| `decisioni-aperte.md` | Decisioni aperte, smistate in tre gruppi; §3 = esiti delle decisioni prese il 2026-10-04 | — | bozza |
| **Nucleo (livello 1)** | | | |
| `10-core-coordinate-wcs.md` | Coordinate, WCS, sistemi di riferimento | 1 | approvato |
| `11-core-immagini-fits.md` | Immagini FITS e visualizzazione | 1 | approvato |
| `12-core-hips.md` | Servizi HiPS all-sky | 1 | approvato |
| `13-core-cataloghi.md` | Cataloghi e tabelle | 1 | approvato |
| `14-core-protocolli-vo.md` | Protocolli Virtual Observatory (VOTable, TAP, cone search, SAMP, SSA) | 1 | approvato |
| `15-core-crossmatch.md` | Incrocio tra cataloghi | 1 | approvato |
| `16-core-moc.md` | Mappe di copertura MOC | 1 | approvato |
| `17-core-misure.md` | Misure angolari e strumenti di misura (codice completo il 2026-10-13; `distance_to` per tutte le forme con D17-8 e D17-9, testo escluso) | 1 | approvato |
| `18-core-calcolatrici.md` | Calcolatrici: algebrica, unità, pixel, coordinate, tempo — origine: H4 di `03-parita-aladin.md`; dipende da `10` (coordinate/tempo) e `11` (pixel); codice completo il 2026-10-13 | 1 | approvato |
| `19-core-dati-planetari.md` | Dati planetari: superfici, cataloghi e coperture planetarie, sistemi di riferimento planetari — origine: H21 di `03-parita-aladin.md` (AM1 accettata il 2026-10-08); codice P0–P4 scritto il 2026-10-13 (`planetary_data.py`), PDS4 anche da URL (D19-9), PDS3 non ancora supportato (D19-8 rimandata) | 1 | approvato |
| **Analisi (livello 2)** | | | |
| `20-analisi-fotometria.md` | Fotometria | 2 | non esiste |
| `21-analisi-spettroscopia.md` | Spettroscopia | 2 | non esiste |
| `22-analisi-curve-di-luce.md` | Curve di luce | 2 | non esiste |
| `23-analisi-cubi-di-dati.md` | Cubi di dati (λ o velocità) | 2 | non esiste |
| `24-analisi-pipeline-riproducibili.md` | Pipeline riproducibili, scripting e API Python, costruiti sopra il registro dei comandi e la sessione del `05` (dal 2026-10-15) | 2 | non esiste |
| **IA (livello 3)** | | | |
| `30-ia-adattatore-provider.md` | Adattatore per provider IA (v1): profili, SDK `anthropic` e `openai` con endpoint configurabile, capacità, `list_models`, `stream_turn` con eventi normalizzati | 3 | approvato |
| `31-ia-chiavi-portachiavi.md` | Chiavi API nel Portachiavi di macOS (v1): `keyring` col solo backend macOS, nessun ripiego | 3 | approvato |
| `32-ia-registro-strumenti.md` | Registro strumenti esposti all'IA (v1, dal 2026-10-16: elenco esplicito di comandi del `05`; **codice scritto con lo sprint 6a il 2026-10-22** (`ai/tool_registry.py`, `valid_tools` nell'errore `TOOL_NOT_EXPOSED` dal 2026-10-23, testi esterni con due elenchi chiusi per percorso; fonte una volta in testa in `catalog.rows` dal 2026-10-22); dei candidati qui sotto entrano solo `describe_table` → `catalog.describe` e `search` → `catalog.search`, gli altri quando diventano comandi del `05`). **Da includere (D11-9, spostati dal §11 dell'11 il 2026-10-10):** `load_image_info` (dimensioni, unità, WCS, campo, origine e data; nessun calcolo nuovo), `get_image_statistics` (min, max, media, deviazione standard; calcolo `numpy`/`astropy.stats`), `image_operation` (H5, elenco chiuso; calcolo `numpy`/`scipy`/`astropy.convolution`), `cutout` (taglio con WCS); **dal 13 (2026-10-10):** `describe_table` (schema, unità, righe, provenienza), `search` (grammatica del 13), `get_column_statistics` (su `column_statistics`), `propagate` (calcolo modulo 10); **dal 14 (2026-10-10, D14-9 punto 16):** `cone_search` (centro, raggio con unità, catalogo; tabella con provenienza), `tap_query` (URL TAP, ADQL, `max_rows`; tabella o errore del servizio), `validate_adql` (controlli minimi), `describe_services` (elenco dei server, `ServerRegistry`), `ssa_search` / `ssa_load` (spettri con provenienza; analisi nel 21) | 3 | approvato |
| `33-ia-query-adql.md` | Costruzione ed esecuzione di query ADQL (**rimandato** il 2026-10-16: nella v1 `catalog.search`) | 3 | non esiste |
| `34-ia-verifica-risultati.md` | Verifica dei numeri delle risposte dell'IA (v1): ogni numero contro i risultati dei comandi, eccezioni chiuse, evidenziazione, modalità rigorosa; **codice scritto con lo sprint 6b il 2026-10-22** (`ai/result_verification.py`) | 3 | approvato |
| `35-ia-assistente-chat.md` | Assistente conversazionale (v1): ciclo degli strumenti, regole di sistema, limiti, privacy, sicurezza contro le istruzioni nei testi esterni; **codice scritto con lo sprint 6c il 2026-10-22** (`ai/chat_assistant.py`, coda del 40) | 3 | approvato |
| **Interfaccia** | | | |
| `40-ui-finestra-principale.md` | Finestra, menu, barra di stato, preferenze essenziali, cronologia e messaggi, coda dei comandi (v1); **codice scritto il 2026-10-17** (`ui/main_window.py`, parte 3 della v1) | — | approvato |
| `41-ui-visualizzatore-cielo.md` | Visualizzatore del cielo (v1): immagine, HiPS, cataloghi, MOC, griglia, misure, puntatore Simbad; OpenGL; obiettivi di prestazione | — | approvato |
| `42-ui-pannello-cataloghi.md` | Pannello cataloghi e tabelle (v1 minima: tabella ordinabile, selezione sincronizzata, record); **sprint 5a scritto il 2026-10-21, 5b (dialoghi delle colonne) il 2026-10-22** (`ui/catalog_panel.py`) | — | approvato |
| `43-ui-pannello-analisi.md` | Pannello analisi | — | non esiste |
| `44-ui-pannello-ia.md` | Pannello dell'assistente (v1): messaggi, schede dei comandi e di conferma, verifica, token, "Cosa è stato inviato", impostazioni, consenso; codice degli sprint 7a (2026-10-22, `ui/ai_panel.py`) e 7b (2026-10-23: numeri evidenziati, latenza, prove) | — | approvato |
| `45-ui-viste-multiple.md` | Viste multiple 2/4/9/16 con sincronizzazione, blocco e miniature — origine: H2 di `03-parita-aladin.md`; dipende da `41` (un visualizzatore per vista) e `40` (finestra) | — | non esiste |
| **Funzioni avanzate (livello 4)** | | | |
| `50-avanzate-transienti.md` | Caccia ai transienti | 4 | non esiste |
| `51-avanzate-multi-messaggero.md` | Dati multi-messaggero | 4 | non esiste |
| `52-avanzate-collaborazione.md` | Collaborazione tra utenti | 4 | non esiste |
| `53-avanzate-vista-3d.md` | Vista 3D | 4 | non esiste |
| **Distribuzione e test** | | | |
| `60-distribuzione-dmg.md` | Pacchetto macOS `.dmg` | — | non esiste |
| `61-strategia-test.md` | Strategia dei test | — | non esiste |

## 5. Decisioni prese

| # | Decisione | Data | Fonte | Note |
|---|---|---|---|---|
| P1 | Nucleo scientifico in Python | 2026-10-04 | `CLAUDE.md`, confermata in `01-architettura.md` | usare librerie consolidate, non riscrivere la scienza |
| P2 | App desktop per macOS, consegna come `.dmg` | 2026-10-04 | `CLAUDE.md`, confermata in `01-architettura.md` | |
| P3 | Livello IA separato dal resto, con adattatore per più provider | 2026-10-04 | `CLAUDE.md`, confermata in `01-architettura.md` | l'utente sceglie il provider e inserisce la propria chiave |
| P4 | Le chiavi API vivono solo nel Portachiavi di macOS | 2026-10-04 | `CLAUDE.md` | mai in file, log o repository |
| P5 | Numerazione dei file per gruppi (00-09 generali, 10-19 nucleo, ecc.) | 2026-10-04 | `CLAUDE.md` | |
| P6 | Un modulo = un file `.md`, modello unico in `TEMPLATE-modulo.md` | 2026-10-04 | `CLAUDE.md` | 14 sezioni obbligatorie |
| P7 | Unità, sistemi di coordinate e convenzioni tecniche | 2026-10-04 | `02-convenzioni.md` | quelle marcate "provvisorie" sono ancora da ratificare |
| P8 (A3) | UI e nucleo nello stesso progetto Python: codice in `src/astrotwo/` con sotto-pacchetti `core`, `analysis`, `ai`, `ui`, `advanced`; test in `tests/` con la stessa struttura | 2026-10-04 | decisione del proprietario, dettagli in `01-architettura.md` §4.2 | motivazione: corrispondenza 1:1 tra specifica e codice, un solo ambiente da costruire e testare |
| P9 (A4) | Python 3.12, `pyproject.toml`, gestore pacchetti `uv` | 2026-10-04 | decisione del proprietario, dettagli in `01-architettura.md` §4.2 | motivazione: versione stabile dell'ecosistema scientifico; installazione e test rapidi e riproducibili |
| P10 (A7) | Cache su due media: SQLite per le interrogazioni ai cataloghi, file su disco per i riquadri HiPS e FITS; limite di spazio configurabile con eliminazione dei dati meno usati; origine e data di scaricamento mostrate per ogni dato dalla cache | 2026-10-04 | decisione del proprietario, dettagli in `01-architettura.md` §4.2 e §8 | motivazione: media adatte al tipo di dato, cache sotto controllo, tracciabilità e riproducibilità |
| P11 | **La parità con Aladin è il minimo, non il traguardo: AstroTwo include TUTTE le funzioni di `03-parita-aladin.md`, anche quelle non confermate nella documentazione di Aladin** (righe C3, F2, G3, E4) | 2026-10-04 | decisione del proprietario, applicata in `03-parita-aladin.md` | sulle funzioni non documentate resta solo la verifica tecnica su come implementarle, non l'esistenza in Aladin |
| A1 | Interfaccia con **PySide6 (Qt)**; il rendering delle mappe con OpenGL si specifica in `41-ui-visualizzatore-cielo.md` | 2026-10-04 | decisione del proprietario, `01-architettura.md` §4.2/§9 | un solo ambiente Python coerente con A3/A4; prima orientamento, ora confermata |
| A5 | Interfaccia IA **a capacità** (chiamata di strumenti, streaming) con due implementazioni iniziali: **provider cloud** e **endpoint compatibile OpenAI** | 2026-10-04 | decisione del proprietario, `01-architettura.md` §4.2/§9 | conforme a CLAUDE.md (l'utente sceglie il provider); prima orientamento, ora confermata |
| AP5 | **AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08**; le sezioni si leggono e si integrano in `03-parita-aladin.md` **prima di scrivere i gruppi successivi** (prima di 20–24) | 2026-10-04 | decisione del proprietario, `03-parita-aladin.md` §2/§6 | evita riscritture di specifiche già scritte e protegge i test T2/T5. **Esito parziale 2026-10-04:** lette sezioni 1–5.7.2 e indice completo (manuale ed. febbraio 2021); esistenza di tutte le funzioni verificata dall'indice; restano i dettagli di 5.7.3–8 |
| AP6 | Edizione di riferimento del manuale di Aladin = **la più recente ufficiale del manuale utente di Aladin Desktop**: verificata sul sito del CDS il 2026-10-08 → **edizione giugno 2022** (nessuna più recente) | 2026-10-08 | decisione del proprietario, `03-parita-aladin.md` §2/§6 | i numeri di sezione del manuale si riferiscono a questa edizione (riportati alla sua numerazione il 2026-10-08; H18: sezione presente solo nell'ed. febbraio 2021) |
| AP3 | **Aladin Lite escluso dalla parità**: AstroTwo è un'app desktop; un'eventuale versione web richiederà una proposta AM1 | 2026-10-08 | decisione del proprietario, `03-parita-aladin.md` §4/§6 | chiusa anche in `decisioni-aperte.md` |
| AM1 (H21) | **Nuovo modulo `19-core-dati-planetari.md`, livello 1** (dati planetari, riga H21 di `03-parita-aladin.md`) | 2026-10-08 | decisione del proprietario, §6 qui sotto | registrato con stato `non esiste` |
| Prestazioni | **Obiettivo minimo: almeno 1 milione di sorgenti di catalogo con 1 GB di RAM** (manuale Aladin ed. giugno 2022, sez. 8.3) | 2026-10-08 | decisione del proprietario, `01-architettura.md` §8 | dettaglio dei test in `61-strategia-test.md` |
| D10-4 (precisata) | Proiezioni = quelle del manuale Aladin ed. giugno 2022, sez. 5.14: `SIN`, `TAN`, `AIT`, `ZEA`, `STG`, `CAR`, `NCP`, `ZPN`; un test per proiezione | 2026-10-08 | decisione del proprietario, `10-core-coordinate-wcs.md` §13 | da verificare: altre proiezioni oltre l'elenco del manuale e supporto `NCP` in `astropy.wcs` |
| D14-5 | **`max_rows` di default 100 000**, configurabile fino al tetto del 13 (1 000 000); superamento sempre dichiarato con `ROW_LIMIT_EXCEEDED` | 2026-10-10 | decisione del proprietario, `14-core-protocolli-vo.md` §13 | |
| D14-9 | **Decisioni sul modulo 14:** sette parti; SAMP con `pyvo.samp` (D14-1 aggiornata); raggio Simbad dal 41; `validate_adql` minima; un solo lettore (`read_table` del 13); `catalog` = voce dell'elenco o URL SCS; una sola cache delle interrogazioni (prima la cache, `refresh`); TAP sincrona/asincrona (600 s); provenienza nei file esportati; tre messaggi SAMP, profilo web disattivato; spettri Spectrum DM/FITS; solo servizi pubblici; IDHA solo errore; colonna DataLink; Simbad a pari citazioni il più vicino; §11 nel 32 | 2026-10-10 | decisione del proprietario, `14-core-protocolli-vo.md` §13 | riga H23 di `03` annotata (IDHA) |
| DC7 | **Convenzione dei pixel:** FITS indice da 1, numpy indice da 0; `fits = numpy + 1` per asse, `array[y, x]`; uso interno numpy, conversione solo ai confini e in un solo punto (modulo 10) | 2026-10-08 | decisione del proprietario, `02-convenzioni.md` §6/§9 | origine H25 di `03-parita-aladin.md` |
| H17 (SED) | La SED del puntatore VizieR si costruisce nel **modulo 20** (fotometria), ogni punto con origine dichiarata | 2026-10-08 | decisione del proprietario, `03-parita-aladin.md` H17 | |
| H19 (VOApp) | Equivalente di VOApp/VOObserver = **API Python nel 24** (strada principale) + **SAMP nel 14** per gli altri programmi; nessuna interfaccia nuova | 2026-10-08 | decisione del proprietario, `03-parita-aladin.md` H19 | |
| D19-2 | Lettura PDS **nel modulo 19** (non nell'11); **PDS4 obbligatorio**, PDS3 solo con libreria consolidata | 2026-10-08 | decisione del proprietario, `19-core-dati-planetari.md` §13 | libreria e licenza aperte come D19-2b (candidata `pds4_tools`) |
| D19-3 | Campo **`body` obbligatorio** nei metadati dei moduli 12, 13, 14, 16; `celestial` (sfera celeste) per i dati astronomici, ricavato dal sistema di coordinate, mai assunto | 2026-10-08 | decisione del proprietario, `19-core-dati-planetari.md` §13 | applicata nei moduli 12, 13, 14, 16 il 2026-10-09 |
| D19-4 | Sovrapposizione tra corpi diversi (o tra dati celesti e planetari) = **errore di default**, forzabile con **opzione esplicita citata nel risultato** (schema di D13-5) | 2026-10-08 | decisione del proprietario, `19-core-dati-planetari.md` §13 | applicata anche alle operazioni tra MOC nel 16 |
| DC7 (conferma) | Pixel da 0 in memoria, convenzione FITS solo ai bordi; funzione unica `convert_pixel_convention` nel modulo 10 | 2026-10-08 | decisione del proprietario, `02-convenzioni.md` §6, `10-core-coordinate-wcs.md` §7 | test T8–T11 del 10 |
| Checklist livello 1 | Accettate 30 raccomandazioni: DC1 (TDB), DC3 (RA 0.01 s, Dec 0.1″, mag 3 decimali), DC4 (SemVer), AP2 (parità funzionale), D10-1 (tre metodi di calibrazione di Aladin), D11-2 (`reproject`), D11-4 (tutte le HDU immagine), D11-5 (9 tabelle di colori, default Gray), D12-1 (HiPS con libreria Python o Hipsgen esterno), D12-3 (MocServer, default DSS2 a colori), D12-4 (client HiPS diretto), D13-3 (albero per popolarità), D14-3 (DataLink con descrittori), D14-4 (schede di Aladin + server personali), D14-6 (SSA 1.1 con `pyvo`), D15-1 (`best`), D15-2 (`astroquery.xmatch`), D15-3 (tetto 1 milione di righe), D15-4 (nessuna probabilità nel livello 1), D16-4 (mappe LIGO/Virgo/KAGRA), D17-6 (distanza + profilo + grafico), D18-1 (`ast`), D18-2 (alias delle unità), D18-3 (equivalenze), D18-4 (magnitudini solo nel 20), D19-1 (`spiceypy` + PCK), D19-2b (`pds4_tools`, `pdr` da valutare), D19-5 (disattivati), D19-6 (corpi con HiPS e PCK; Luna e Marte), D19-7 (MOC planetari da verificare) | 2026-10-09 | decisione del proprietario, file di origine §13 (e §9 per 01/02/03) | le verifiche "da verificare" restano vincoli prima del codice del modulo |
| A2, A6, A9 (orientamento) | A2 = PyInstaller + dmgbuild; A6 = sì, notarizzazione con account Apple Developer solo alla distribuzione; A9 = inglese di base + italiano con Qt. Non bloccano il livello 1; bloccano `60` (A2, A6) e `40` (A9) | 2026-10-09 | decisione del proprietario, `01-architettura.md` §5/§9 | restano nel Gruppo 2 di `decisioni-aperte.md` |
| D19-3 esteso al 15 | Il crossmatch tra tabelle di corpi diversi dà `BODY_MISMATCH`, forzabile come D19-4 | 2026-10-09 | decisione del proprietario, `15-core-crossmatch.md` §9/§10/§12 | test T7–T8 del 15 |
| Fase codice per livello | "FASE: CODICE – livello N" autorizza il codice solo per i moduli `approvato` di quel livello; gli altri livelli restano in fase specifiche | 2026-10-09 | decisione del proprietario, `CLAUDE.md` | livelli in fase codice: nessuno |
| Approvazione livello 1 (parziale) | **Approvati** 01, 02, 03, 10, 18, 19 (decisione del proprietario) e 12, 16, 17 (completati, nessuna decisione dei Gruppi 1 e 2); 11, 13, 14, 15 in bozza fino a D11-6, D13-7, D14-7, D14-8, D15-5 | 2026-10-09 | decisione e regola del proprietario | nessun livello in fase codice |
| D11-6 | `Pillow` per JPEG, PNG e GIF | 2026-10-09 | decisione del proprietario, `11-core-immagini-fits.md` §13 | licenza da verificare prima del codice |
| D13-7 / D14-8 | Lettori ASTRORES (13) e IDHA (14) con **`defusedxml`**, testati su esempi del CDS; senza documentazione o esempi, solo errore | 2026-10-09 | decisione del proprietario, `13` e `14` §13 | sicurezza su file XML non fidati; licenza da verificare |
| D14-7 | **Nessun sistema di plugin nel livello 1**; estensioni tramite l'API Python del 24 (parte "plugin" di H14 spostata nel 24) | 2026-10-09 | decisione del proprietario, `14` §13, `03` H14 | |
| D15-5 | Correlazione con ellissi: distanza di Mahalanobis con covarianza combinata, soglia in sigma (default D15-6, Gruppo 3) | 2026-10-09 | decisione del proprietario, `15` §13 | criterio nostro, scritto nel report (confronto con Aladin tolto il 2026-10-10) |
| Test | Framework dei test **`pytest`** (anticipato da 61) | 2026-10-09 | decisione del proprietario, `01` §4, `02` §8 | dettagli in `61-strategia-test.md` |
| Approvazione livello 1 | **01, 02, 03 e 10–19 tutti `approvato`** | 2026-10-09 | decisione e regola del proprietario | livelli in fase codice: nessuno |
| D10-2 + D13-2 | Epoca di ogni dato **letta dai suoi metadati e mai assunta**; epoca di visualizzazione = epoca dell'immagine se nota, altrimenti **J2000**; **epoca usata sempre scritta nel risultato**; ogni catalogo ha la **propria epoca di riferimento** | 2026-10-04 | decisione del proprietario, `10-core-coordinate-wcs.md` §13 e `13-core-cataloghi.md` §13 | regola scritta anche in `02-convenzioni.md` DC2 (§5); riproducibilità (regola d'oro n. 6) |
| D10-3 | Cache della risoluzione nomi in **tabella SQLite separata dentro la cache A7** | 2026-10-04 | decisione del proprietario, `10-core-coordinate-wcs.md` §13 | limite e provenienza unici come A7, schema non condiviso con il 13 |
| D10-4 | **Stessa lista di proiezioni di Aladin** (da verificare con AP5); **`TAN`** default immagini, **`AIT`** viste a cielo intero; **un test per proiezione** (T7) | 2026-10-04 | decisione del proprietario, `10-core-coordinate-wcs.md` §13 | parità documentale = minimo (P11) |
| D11-1 | **Tipo nativo del file in memoria; ogni calcolo in `float64`; `float32` solo per la visualizzazione** | 2026-10-04 | decisione del proprietario, `11-core-immagini-fits.md` §13 | regola scritta anche in `02-convenzioni.md` DC6 (§6) |
| D11-3 | Limite cache su disco **5 GB di default, configurabile**, con eliminazione dei dati meno usati | 2026-10-04 | decisione del proprietario, `11-core-immagini-fits.md` §13 | estensione di A7; interfaccia di configurazione in `40`/`60` |
| D12-5 + D16-5 | **Calcoli HEALPix nel 16, servizio dei tile nel 12** (stesso confine in entrambi i file) | 2026-10-04 | decisione del proprietario, `12-core-hips.md` e `16-core-moc.md` §13 | nessuna logica HEALPix duplicata, un solo confine dichiarato |
| D13-1 | **Stringa con grammatica ristretta, nostra** (riscritta il 2026-10-10, regola d'oro n. 8) per `search` (jolly `?`/`*`; operatori `=`, `!=`, `<`, `>`, `<=`, `>=`; valore assoluto; prefissi `+`/`-` per aggiungere/togliere), **validata prima dell'esecuzione** | 2026-10-04 | decisione del proprietario, `13-core-cataloghi.md` §13 | un solo validatore deterministico per UI, IA e pipeline |
| D13-5 | Operazioni sulle tabelle **sempre non distruttive**; in-place solo con **flag esplicito citato nel report** | 2026-10-04 | decisione del proprietario, `13-core-cataloghi.md` §13 | coerenza con 15/16/17 e con la riproducibilità |
| D13-6 | **Colonna DataLink nel 13, risoluzione dei link nel 14** | 2026-10-04 | decisione del proprietario, `13-core-cataloghi.md` §13 | nessuna duplicazione di client VO |
| D14-1 | **`pyvo` per TAP e DataLink**; per SAMP si **valuta `astropy.samp` (da verificare)**; **licenze da riverificare prima di approvare il 14** | 2026-10-04 | decisione del proprietario, `14-core-protocolli-vo.md` §13 | stack VO IVOA, un solo punto da mockare nei test |
| D14-2 | **Hub SAMP: collegarsi a uno già attivo se c'è, altrimenti avviarne uno proprio**; primo perimetro **tabelle, selezioni, puntamenti**; **immagini come estensione prevista** | 2026-10-04 | decisione del proprietario, `14-core-protocolli-vo.md` §13 | parte tecnica residua chiusa; l'inclusione era già decisa con P11 |
| D16-1 | **`mocpy`** per i MOC; **licenza e installazione su macOS da verificare prima di approvare il 16** | 2026-10-04 | decisione del proprietario, `16-core-moc.md` §13 | copre MOC spaziali e temporali (E6), allineato allo standard IVOA |
| D16-2 | **MOC in cache in formato FITS standard IVOA; export anche JSON e testo** | 2026-10-04 | decisione del proprietario, `16-core-moc.md` §13 | formato standard della comunità e tracciabilità A7 sui file |
| D16-3 | **Tempo numerico internamente (JD via `astropy.time`); ISO 8601 solo in interfaccia e file; scala di tempo sempre dichiarata (UTC, TDB, TCB); MOC temporali con la scala IVOA (da verificare)** | 2026-10-04 | decisione del proprietario, `16-core-moc.md` §13 | regola scritta anche in `02-convenzioni.md` DC1 |
| D17-2 | **Geometria nel 17, rendering nel 41** | 2026-10-04 | decisione del proprietario, `17-core-misure.md` §13 | "l'interfaccia non fa calcoli" (`01-architettura.md` §3) e riuso delle forme da 16 e 20 |
| D17-3 | **Tag nel file di sessione del 24, condiviso con i segnalibri di 40**; la sessione salva **riferimenti ai file e operazioni eseguite (non i pixel)** e deve poter essere **rieseguita** | 2026-10-04 | decisione del proprietario, `17-core-misure.md` §13 | un solo formato di sessione; il 17 resta senza I/O su disco |
| D17-4 | **La fotometria (F4) sta interamente nel 20** | 2026-10-04 | decisione del proprietario, `17-core-misure.md` §13 | la fotometria è livello 2; nessun test duplicato |
| AM1 (cache) | **Nuovo file generale `04-cache.md`**: cache A7 condivisa in `~/Library/Caches/AstroTwo/`, limite 5 GB (D11-3), timeout dichiarati, origine e data di ogni dato; usata da 10–14 e 16 | 2026-10-09 | decisione del proprietario (da D10-8) | file in `bozza`, in attesa di approvazione; decisioni aperte CA1–CA4 |
| D10-7 | Calibrazione per associazione di stelle: partenza da un adattamento `TAN`, poi tre controlli obbligatori configurabili — stelle minime 6 (`TAN`/`STG`) o 10; RMS ≤ 1 px e massimo ≤ 3 px; scostamento al centro ≤ 5 × RMS della `TAN` | 2026-10-09 | decisione del proprietario, `10-core-coordinate-wcs.md` §13 | RMS della `TAN` precisato dal proprietario dopo la prova su dati esatti |
| D10-8 | `compute_grid_lines` e `choose_projection` nel 10; cache in `04`; centroide nell'11, soluzioni come lista (annulla/ripeti in 24/40); `coordinate_calculator` tolta, offset e calcolo inverso nel 17, calcolatrice del 18 su 10 e 17 | 2026-10-09 | decisione del proprietario, `10` §13 | applicata in 10, 11, 17, 18 (restano `approvato`) |
| LGPL | WCSLIB (in astropy) è LGPL-3: **vincolo da rispettare nel modulo 60** | 2026-10-09 | decisione del proprietario | da specificare in `60-distribuzione-dmg.md` |
| CA1–CA4 | Cache comune (`04-cache.md`): timeout 10 s connessione e 60 s lettura, configurabili; **un solo limite di 5 GB**; codice in `src/astrotwo/core/cache.py`; **nessuna cache propria nei moduli** (tolte `ImageCache`, `HiPSCache`, `CatalogCache`, `QueryCache` e la cache MOC) | 2026-10-09 | decisione del proprietario, `04-cache.md` §13 | `04` approvato; 11, 12, 13, 14, 16 collegati (restano approvati) |
| D11-7 | Fondo cielo del centroide = **mediana con sigma clipping in una corona** attorno alla stella (`astropy.stats.sigma_clipped_stats`) | 2026-10-09 | decisione del proprietario, `11-core-immagini-fits.md` §13 | `star_centroid` scritto e testato |
| Griglia | **`choose_grid_spacing`** nel 10: passo automatico in base al campo visibile, come Aladin; il passo esplicito resta possibile | 2026-10-09 | decisione del proprietario, `10` §7/§9 | elenchi dei valori tondi e 5 linee per asse: proposta, coincidenza con Aladin da verificare |
| 10 (interpretazioni) | Confermate: proiezioni WCSLIB fuori da D10-4 accettate in lettura; `obstime` esplicito per i frame che lo hanno; velocità radiale assente = 0 km/s dichiarata; `PV2_m` obbligatori per `ZPN` | 2026-10-09 | decisione del proprietario, `10` §9 | D10-9 resta aperta e si decide con il 41 |
| Nomi Python | **Nomi dei file Python in inglese**: traduzione inglese del nome della specifica, `snake_case`; tabella per 04 e 10–19 in `02-convenzioni.md` §3 | 2026-10-09 | decisione del proprietario, `02` §3 | es. `11` → `images_fits.py`, `13` → `catalogs.py` |
| Cache (precisazioni) | Limite = **somma dei dati delle voci** (overhead di SQLite escluso); **5 GB = 5 × 10⁹ byte**; `resolve_name` con **prima la cache** (`refresh=True` per forzare SIMBAD) | 2026-10-09 | decisione del proprietario, `04-cache.md` §3, `10` §3 | applicate nel codice di `cache.py` e `resolve_name` |
| Regola d'oro n. 8 | **AstroTwo è scritto da zero:** da Aladin non si prende niente (codice, tabelle di valori, file, immagini); il manuale dice solo quali funzioni servono; unica eccezione la lettura di file prodotti da Aladin | 2026-10-10 | decisione del proprietario, `CLAUDE.md` | collegata ad A11 (licenza) |
| 11 (divisione) | Modulo 11 in 7 parti (P1 lettura FITS → P7 ricampionamento/RGB/mosaico); D11-5 corretta (palette `matplotlib`); funzioni di trasferimento di `astropy.visualization`; `contourpy`; elenco chiuso H5; A10 per le immagini; qualità = copertura `reproject`; fattore unico `rgb_diff`; vista esportata dal 41; strumenti IA nel 32 | 2026-10-10 | decisione del proprietario, `11` §3/§13 (D11-9) | normalizzazione H5 da verificare con il manuale prima di P5 |
| 11 (P1–P7) | HDU immagine = 2 assi utili, più HDU → parametro `hdu` (`HDU_CHOICE_REQUIRED`); FITS RGB solo con `rgb=True`; calibrazione JPEG/PNG/`.hhh` da soli standard pubblici (JPEG `COM`, PNG `Comment`, FITS 4.0); immagini da URL con prima la cache; `memmap` impossibile con `BZERO`/`BSCALE`/`BLANK` → due livelli; due livelli: misure sui pixel originali per regione, altrimenti `PREVIEW_NOT_MEASURABLE`; RGB con parametri di display espliciti, B = media con 2 immagini, `rgb_diff` con B = 0; metodo di ricampionamento obbligatorio; `reproject` = lista sulla stessa griglia; lunghezze d'onda come parametro | 2026-10-10 | decisioni del proprietario durante P1–P7, `11` §3/§7 | modulo 11 completo |

| 11 (dopo il codice) | Confermate le scelte di P1–P7 (D11-10); commento contro `.hhh`: vale il commento, avviso `HHH_WCS_DIFFERS` se i WCS sono diversi; **stima della memoria** prima delle operazioni sull'immagine intera e del taglio, oltre il tetto A10 `MEMORY_LIMIT_EXCEEDED`; §11 dell'11 spostato nel 32 (D11-9) | 2026-10-10 | decisione del proprietario, `11` §3/§10/§13 | test T32–T33; criterio di confronto dei WCS e tabella delle stime scritti nell'11 §3 |
| Regola d'oro n. 8 (applicazione) | Nei file 11–15, 18, 19: D12-1 generazione HiPS da standard IVOA HiPS 1.0 (`reproject` + codice nostro, **Hipsgen tolto**); D12-3 DSS2 a colori motivato da noi; D13-1 grammatica nostra; D13-3, D14-3, D19-5 con motivazione nostra; D14-4 **elenco di server nostro** dai servizi pubblici del VO; 15 **raggio obbligatorio senza default**, `best` motivata da noi; D18-2 **solo formati FITS e VOUnit** di `astropy.units`; T16 del 18 con esempio nostro | 2026-10-10 | decisione del proprietario, §13 dei file | restano motivi "come Aladin" nei file non autorizzati 10 e 17 (elenco consegnato al proprietario) |

| D11-11 | Limite delle operazioni **separato da A10**: 4 GB di default, configurabile, per `MEMORY_LIMIT_EXCEEDED`; `set_display` **a blocchi in `float32`** senza copia intera (un 6000 × 6000 si visualizza); criterio commento/`.hhh` confermato | 2026-10-10 | decisione del proprietario, `11` §3/§13 | test T33–T34 |
| Strumenti IA | Gli strumenti per l'IA si dichiarano **nel 32**, non nel §11 dei moduli | 2026-10-10 | decisione del proprietario, `01` §7 | §11 di 11 e 13 rimandano al 32 |
| Regola d'oro n. 8 (validazione) | **Confrontare i risultati con Aladin è validazione, non copia** (AP1 resta); tolti i motivi "come Aladin" anche nel 10 (`choose_grid_spacing`, DSS1) e nel 17 (D17-6); `*.pdf` nel `.gitignore` | 2026-10-10 | decisione del proprietario, `CLAUDE.md`, `10`, `17` | nessun motivo "come Aladin" resta nei file approvati |
| 13 (divisione) | Sei parti (P6 dopo il 14); VOTable locali con `astropy.io.votable`; una sola cache delle interrogazioni, nel 14; grammatica formale di `search` (testo che non distingue maiuscole e minuscole per default); regole di disegno; **D13-4** 1 milione di righe + limite delle operazioni 4 GB (A10 per i cataloghi); **D13-8** tabella delle funzioni in `catalogs.py`; colonne di posizione solo da UCD/metadati, suggerimenti dal nome da confermare; parallasse mancante → solo moto proprio, righe marcate; unità non valide con avviso; CSV/TSV/BSV con errore se ambiguo; `inplace` nel report; bin e scala obbligatori; §11 nel 32 | 2026-10-10 | decisione del proprietario, `13` §3/§13 (D13-9) | aperte D13-10…D13-14 |

| D13-10…D13-14 | `skydist` con `astropy.coordinates` nel 13, unica implementazione anche per il 17; colonna DataLink in P6; propagazione **solo moto proprio** come opzione esplicita del 10, righe senza moto proprio **mascherate e contate**, colonne originali intatte; sottoinsiemi salvati in un **VOTable scelto dall'utente** con provenienza (mai nella cache); ASTRORES: sessagesimali convertiti con il 10 (testo conservato), `#id(...)` accettato con avviso, `LINK` in P6, test su file nostri più l'esempio pubblico in rete | 2026-10-10 | decisione del proprietario, `13` §13, `10`, `17` | aperte D13-14b, D13-15, D13-16 |
| Scelte minori di P1 (13) | `table` con `TABLE_CHOICE_REQUIRED`; unità angolare richiesta in `confirm_position_columns`; `TableLimits` separato, unificato dalla preferenza del 40 | 2026-10-10 | decisione del proprietario, `13` §3 | confermate |

| D13-14b, D13-15, D13-16 | UCD1 tradotti solo se scritti nella raccomandazione IVOA (servizio CDS in P6, opzione esplicita); nelle colonne calcolate un numero scritto prende l'unità della colonna in `+`, `-`, `%`, `min`, `max`, `round` metà al pari; `time_filter` con colonna indicata, `TIMESYS` o parametri, intervallo chiuso; scelte minori confermate | 2026-10-10 | decisione del proprietario, `13` §13 | 13 completo fino a P5 |

| D14-10, D14-11, D14-12, D13-17, D13-18 | ECSV per le tabelle con unità (CSV semplice con avviso `CSV_UNITS_NOT_SAVED`); WCS dalle colonne `VOX:WCS_*` di SIA 1 e parametro `calibration` dell'11 dichiarato; tutte le magnitudini SIMBAD con banda e sistema (AB/Vega/non dichiarato); `LINK` ASTRORES solo con `href`, formato dal `content-type` dichiarato, nessun formato indovinato; albero delle collezioni dal MocServer per `vizier_popularity` ("proprietà non documentata del MocServer"), altrimenti alfabetico | 2026-10-11 | decisione del proprietario, `11`, `13`, `14` §13 | applicate nel codice; T5, T11, T13, T15, T31 |
| Verifiche e scelte minori (13, 14) | Registro VO di default `https://dc.g-vo.org/tap` (HTTPS, configurabile); server esclusi confermati con il motivo, da ricontrollare; FITS esportati "FITS Standard 4.0" più versione di `astropy`; `load_catalog` senza regione solo entro `max_rows`, altrimenti `REGION_REQUIRED` o `allow_partial=True` dichiarato; altre scelte minori confermate | 2026-10-11 | decisione del proprietario, `13`, `14` | aperte D13-19 (regione) e D13-14c (UCD1 CDS, rimandata) |

| D13-19, D15-6, D15-7 | `load_catalog(region=(centro, raggio))` con colonne dagli UCD di `TAP_SCHEMA` e sistema dal `COOSYS` (termini `refframe` riconosciuti); ECSV con il sistema delle posizioni nei metadati YAML; albero in ordine naturale; ripetizioni dei test di rete solo per connessione/timeout (massimo 2, dichiarate); modulo 15 in 5 parti con tutte le raccomandazioni accettate (epoche senza propagazione, `best` con pari merito e B riusato dichiarati, mancanti esclusi, `max_sep` ≤ 180° / 180″, CDS in HTTPS con cache del 14, soglia e assi delle ellissi obbligatori, tolleranza T4 1 mas) | 2026-10-11 | decisione del proprietario, `13`, `14`, `15` §13 | aperte D13-20, D15-8, D15-9 |
| D16-6, D16-7, scelte del 16, decisioni del 12, A10 (HiPS) | 16: nessuna 2.1 tra WD/PR IVOA (resta rifiutata); complemento degli ST-MOC come differenza da "tutto il tempo × tutto il cielo" con `mocpy`; operazione forzata → corpo misto con l'elenco, nuova forzatura per ogni operazione successiva; MOC planetari in FITS 2.0 con la parola chiave `A2BODY` (estensione dichiarata); scelte minori 1–4 e 7–13 confermate. 12: 5 parti; MocServer con la rete del 14; `healpy` tolto e mappe/griglie solo nel 16; H10 SkyView solo con URL SIA verificato sul sito NASA (non trovato: rinviato); campo a cerchio; tile corrotto = una nuova richiesta; `build_hips` con ordine obbligatorio, tile 512, FITS sempre, PNG/JPEG con parametri espliciti; A10 per gli HiPS: 512 MB in memoria, un tile alla volta, limite delle operazioni 4 GB. 14: rimando a `02` §8 per le ripetizioni dei test di rete | 2026-10-12 | decisioni del proprietario | file di origine: `12`, `14`, `16` (restano `approvato`); aperte D12-6, D12-7, D12-8 |
| D12-6, D12-7, D12-8, H10, scelte del 12 e del 16, D17-5, divisione del 17 | 12: nomi dei corpi normalizzati con una tabella del 19 (scritta con il 19); `hips_frame = ecliptic` non supportato finché non verificato su un HiPS reale; nessun Allsky da `build_hips` per ora; H10 SkyView rinviato finché NASA non documenta l'URL SIA (motivo scritto); `reproject` in `build_hips` approvato, metodo `flux` non disponibile; disposizione dei pixel nel tile approvata (verificata su 2MASS K e con `reproject`, da ricontrollare in AP1); scelte minori di 12 e 16 confermate. 14 e 16: codifica del MocServer (ISO-8859-1 dichiarata) scritta nelle specifiche. 01: riga A10 con l'esito per gli HiPS. 17: 4 parti; profili bilineari con `scipy.ndimage.map_coordinates`, passo obbligatorio senza default; P3 solo dopo la verifica delle librerie | 2026-10-12 | decisioni del proprietario | file di origine: `01`, `12`, `14`, `16`, `17` (restano `approvato`); aperta D17-7 |
| D17-7, D18-5, D18-6, scelte minori del 17, divisione del 18 | 17: `spherical-geometry` per poligoni e tracciati chiusi; ellisse sferica (somma delle distanze dai fuochi ≤ 2a, definizione sempre dichiarata, area integrata con precisione dichiarata); cerchio esatto con Astropy; freccia e testo `OPERATION_UNSUPPORTED`, tracciato libero come poligono solo se chiuso; scelte minori di P1/P2/P4 confermate, con `read_pixel` senza `BUNIT` → unità "non dichiarata" e `auto_distance` che dichiara l'uso dell'epoca della prima sorgente. 18: 5 parti; espressioni al massimo 1000 caratteri e annidamento 50, configurabili; valore grezzo con `do_not_scale_image_data=True`; T18 con la riesecuzione del comando registrato finché il 24 non esiste | 2026-10-12 | decisioni del proprietario | file di origine: `17`, `18` (restano `approvato`); aperte D17-8, D18-7 |
| D17-8, D18-7, licenze, lettura FITS nell'11, scelte di 17 e 18, UT1, modulo 19 (divisione, tabella dei nomi D12-6) | 17: `distance_to` = distanza angolare minima (0 se sovrapposte o punto dentro), cerchi esatti con Astropy, poligoni con la distanza punto–arco di cerchio massimo; 18: sessagesimali con l'unità scritta nel testo, due punti ambigui (errore) salvo parametro esplicito, nessuna convenzione sulla posizione; `THIRD_PARTY_LICENSES` con tutte le dipendenze e l'avviso QD/LBNL; valore grezzo letto dall'11 (`read_raw_pixel`); scelte minori di 17 e 18 confermate; UT1 con le tabelle IERS di astropy senza rete, `IERS_RANGE`, aggiornamento solo su richiesta con la rete del 14, tabella dichiarata; 19 in P0–P4; nomi canonici IAU inglesi con iniziale maiuscola via `spiceypy.bodn2c`, solo corpi con HiPS e nel PCK, applicata al 12 | 2026-10-13 | decisioni del proprietario | file di origine: `01`, `11`, `12`, `17`, `18`, `19` (restano `approvato`) |
| D17-9, D19-8, D19-9, scelte minori di 18 e 19, 04, `pims` | 17: `distance_to` per freccia e tracciato aperto = archi di cerchio massimo; ellisse = distanza dal bordo calcolata numericamente con precisione dichiarata (`atol` 1e-9° di default, stima dell'errore nel risultato); testo `OPERATION_UNSUPPORTED`; 19: PDS3 **rimandato** (bassa priorità, errore "formato PDS3 non ancora supportato"); PDS4 da URL con etichetta + file nominati nella stessa cartella, rete del 14, cache comune; 18: `colon_units` e UT1 con `iers_table` confermati; 19: scelte minori 1–9 confermate; 04: 18 tra gli utenti della cache; `pims`: testo di licenza dal sorgente ufficiale | 2026-10-13 | decisione del proprietario, `17` §13, `19` §13, `04` §5 | prese |
| D13-20, D15-8, D15-9, regola dei commit, decisioni del 16 | SIMBAD: sistema dall'`utype` MANGO, dichiarato; join per campo: corpo controllato solo se entrambe le tabelle lo hanno; CDS XMatch sempre `selection=all`, `best` in locale; commit solo se tutti i test di default passano (rete a parte, dichiarata); 16: `healpy` escluso, `order_max` obbligatorio, MOC da catalogo una cella per sorgente, da immagine dai pixel validi con il WCS dell'11, poligoni su cerchi massimi, MOC spaziali sempre ICRS, probabilità con somma = 1 entro 10⁻⁶, MocServer con la rete del 14, `build_moc` solo funzione, mappe NESTED ICRS; C4 e H12 progressivi rinviati al 12 | 2026-10-11 | decisioni del proprietario | file di origine: `02`, `13`, `15`, `16` (restano `approvato`) |
| AM1 (05) | **Nuovo file generale `05-comandi-sessione.md`, livello 1** (registro dei comandi e sessione), codice in `src/astrotwo/core/commands.py`; `run_command` del 18 diventa un adattatore del formato del 05; gesti registrati a fine gesto (300 ms fermo) come `view.set_center`/`view.set_zoom` | 2026-10-15 | decisione del proprietario, `05` | il `24` costruirà pipeline e scripting sopra il 05 |
| Interfaccia v1 (perimetro) | 40, 41, 42 minimo; fuori: A7, A8, G4, G5, E7, H1, H3, tag, segnalibri, 43, 44, 45 (**A7 e 44 nella v1 dal 2026-10-16**) | 2026-10-15 | decisione del proprietario, `40`, `41`, `42` §3.1 | |
| Interfaccia (architettura) | Tutto passa dal registro del 05; coda dei comandi in un thread di lavoro; gruppo di thread separato per i tile HiPS; risultati con i segnali di Qt; annullamento cooperativo; ogni comando lungo con avanzamento e Annulla; verifica della cache del 04 da più thread prima del codice | 2026-10-15 | decisione del proprietario, `05` §3.2, `40` §3.8, `41` §3.13 | |
| Interfaccia (rendering) | `QOpenGLWidget` dietro un'interfaccia di disegno nostra (passaggio futuro a QRhi); funzioni OpenGL di PySide6, PyOpenGL solo se non bastano; `make_view_wcs` nel 10 e tile sulla vista nel 12; traslazione e scala dello schermo = disegno; obiettivi P1–P7 con test, mai abbassati in silenzio | 2026-10-15 | decisione del proprietario, `41` §3.2–§3.15, `10`, `12` | |
| Interfaccia (test) | pytest-qt (licenza da verificare), piattaforma `offscreen`, disegno entro 1 pixel dalle posizioni del 10, niente confronti di immagini intere, lista di controllo manuale nel 41 | 2026-10-15 | decisione del proprietario, `02` §8 punto 10, `41` §12 | |
| D10-9 | Soglia `TAN`/`AIT` = **30°**, scarto ±10 % (33°/27°) gestito nel 41 | 2026-10-15 | decisione del proprietario, `10` §13, `41` §3.3 | |
| D11-8 | Corona del centroide: interno **1 × `box_size`**, esterno **1,5 × `box_size`**; `box_size` iniziale 15 pixel nel 41, modificabile e dichiarato | 2026-10-15 | decisione del proprietario, `11` §13, `41` §3.12 | |
| Puntatore Simbad | Raggio **12 pixel logici** convertiti in angolo dal 10 (con il 17 per la distanza); richiesta dopo 500 ms fermo, una alla volta | 2026-10-15 | decisione del proprietario, `41` §3.12 | D14-9 punto 2 lo assegnava al 41 |
| A9 | Testi in inglese con `tr()`, traduzione italiana nostra (Qt Linguist), traduzioni di Qt per i dialoghi standard, lingua dal sistema cambiabile nelle preferenze; **numeri scientifici sempre con il punto decimale** | 2026-10-15 | decisione del proprietario, `01` §4.2, `40` §3.9 | |
| D05-1, D05-2 | Tre classi di comandi `session`/`passive`/`application`; alla riapertura, dati di rete cambiati → **avviso senza fermarsi**, con l'impronta dei risultati di rete di ogni comando salvata nella sessione (l'avviso dice quale comando e cosa è cambiato); **precisazione del 2026-10-17:** l'impronta è lo SHA-256 del contenuto restituito dal modulo (i moduli 10–14 non restituiscono i byte ricevuti) | 2026-10-15 | decisione del proprietario, `05` §13 | |
| D40-1 | v1: codice + testo del modulo invariati; traduzione in D40-3 | 2026-10-15 | decisione del proprietario, `40` §13 | |
| D41-1…D41-4 | Puntatore Simbad `passive` nel gruppo di thread dei tile; `format_coordinates` nel 10; `suggest_display_limits` con `ZScaleInterval` nell'11, limiti dichiarati; `perf` e `gl` esclusi di default, `gl` blocca, `perf` si riporta | 2026-10-15 | decisione del proprietario, `41`, `10`, `11` §13 | Mac di riferimento da compilare |
| Linee guida visive | macOS, tema che segue il sistema con lo scuro di riferimento, modalità notte rossa, cielo al centro con pannelli richiudibili e barre sottili, carattere di sistema, un solo accento, spaziature regolari, icone con licenza libera (proposta Lucide, da verificare), nulla da Aladin; valgono per tutte le interfacce | 2026-10-15 | decisione del proprietario, `40` §3.11 | mockup in `mdfiles/mockup/` |
| Licenza di AstroTwo (A11) | **GPL-3.0-or-later**, titolare Guido Ratti 2026 (unico titolare); `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, intestazione SPDX nei `.py`; crediti dei dati e requisiti del `60` in `01` §6.1 | 2026-10-17 | decisione del proprietario, `01` §4.2 e §6.1 | |
| Licenze dell'interfaccia | PySide6/Qt (LGPL-3) registrata per A11 e per il `60` | 2026-10-15 | decisione del proprietario, `decisioni-aperte.md` (A11), `40` §8 | |
| Fase codice dell'interfaccia | Formula "FASE: CODICE – interfaccia v1", valida solo per i moduli di interfaccia `approvato` (40, 41, 42) e per il 05 | 2026-10-15 | regola del proprietario, `CLAUDE.md` | non ancora dichiarata; estesa il 2026-10-16 |
| IA nella v1 (perimetro) | 30, 31, 32, 34, 35, 44; **33 rimandato**, al suo posto `catalog.search` del 13 | 2026-10-16 | decisione del proprietario, `32`, `03` (E2) | |
| A5 (implementazioni) | SDK `anthropic` (MIT) e `openai` (Apache-2.0) con endpoint configurabile (cloud e locale), licenze da verificare; nessun modello nel codice; `ProviderAdapter` con capacità, `list_models`, `stream_turn`, eventi normalizzati; modelli senza strumenti rifiutati (`AI_NO_TOOLS`); `keyring` (MIT, da verificare) col solo Portachiavi, errore esplicito senza ripiego | 2026-10-16 | decisione del proprietario, `01` §4.2, `30`, `31` | |
| Strumenti dell'IA | Elenco esplicito nel 32 (esposti e non esposti), schema da `export_schema`, nomi `view__go_to`, validazione del 05, stessa coda con `requested_by = ai`, risultati ≤ 50 righe e 20 kB | 2026-10-16 | decisione del proprietario, `32`, `05` | |
| Verifica dei numeri | Ogni numero della risposta contro i risultati dei comandi; numeri non verificati evidenziati; modalità rigorosa con una rigenerazione; elenco chiuso delle eccezioni nel 34, nel dubbio si verifica | 2026-10-16 | decisione del proprietario, `34` | |
| Conferme, limiti, costi | Conferma per comandi `network`/`long` e modifiche ai livelli; 10 comandi e 5 minuti per risposta; tempi 10/60/30 s; solo token, prezzo facoltativo dell'utente; Stop con `CancelToken` | 2026-10-16 | decisione del proprietario, `32`, `35`, `30` | |
| Privacy dell'IA | Cosa esce (testo, regole, strumenti, risultati ridotti) e cosa no (file, pixel, cache, chiavi, cartelle); consenso al primo uso di ogni profilo; "Cosa è stato inviato" con il JSON esatto; simbolo "locale"; nella sessione solo i comandi, il testo solo su richiesta | 2026-10-16 | decisione del proprietario, `35` §3.8–§3.9, `44` | |
| Sicurezza dell'IA (prompt injection) | Risultati e testi esterni = dati, mai istruzioni (regola R4); testi esterni marcati; nessuna azione chiesta da un testo esterno senza conferma; test con istruzioni malevole | 2026-10-16 | decisione del proprietario, `32` §3.6, `34` §3.7, `35` §3.10 | |
| A7 nella v1 | Nord e barra di scala nel 41 con la nuova `compass_and_scale_bar` del 10 | 2026-10-16 | decisione del proprietario, `10`, `41` §3.18, `03` (A7) | |
| Cifre della tabella (42) | Colonne di posizione con `format_coordinates`, magnitudini (UCD `phot.mag`) a 3 decimali, valore pieno nel suggerimento e nella copia, altre colonne come sono | 2026-10-16 | decisione del proprietario, `42` §3.2 | sostituisce la scelta minore 1 del 42 |
| Fase codice IA | "FASE: CODICE – interfaccia v1" vale anche per 30, 31, 32, 34, 35 e 44 `approvato` | 2026-10-16 | decisione del proprietario, `CLAUDE.md` | |
| Regola dei commit (HTTP) | HTTP 429, 502, 503, 504 dei servizi esterni = "connessione" (stesse ripetizioni, dichiarazione nel commit); altri 4xx = risultato sbagliato | 2026-10-16 | decisione del proprietario, `02` §8, `tests/conftest.py`, `scripts/commit_checked.py` | |
| Scelte minori della v1 (32) | Confermate come raccomandate, tranne la #6: servizio del Portachiavi `dev.pages.astrotwo.ai` | 2026-10-16 | decisione del proprietario, §13 di 05, 10, 30, 31, 32, 34, 35, 41, 44 | |
| Identificativo del progetto | `dev.pages.astrotwo` (sito `astrotwo.pages.dev`), bundle identifier dell'app (60) | 2026-10-16 | decisione del proprietario, `01` §6 | |
| Approvazione e fase codice della v1 | 05, 30, 31, 32, 34, 35, 40, 41, 42, 44 `approvato`; "FASE: CODICE – interfaccia v1" dichiarata | 2026-10-16 | decisione del proprietario, `CLAUDE.md` | |
| D05-4 | Forma JSON dei valori dei parametri del 05: nuovo tipo `record` (campi tipizzati con unità, validati e nello schema per il 32), forme JSON di ogni tipo; parametri dei `calc.*` nel 18 | 2026-10-17 | decisione del proprietario (opzione a), `05` §3.1, `18` §3 | |
| `httpx2` | Accettato come trasporto degli SDK `anthropic` e `openai` dopo la verifica dell'origine (Pydantic, non `encode/httpx`); versioni bloccate nel `uv.lock`, aggiornamento solo esplicito con nuovo controllo delle impronte | 2026-10-17 | decisione del proprietario, `01` §6, `30` §13 | |
| Profili predefiniti dei provider IA | Anthropic, OpenAI, Gemini, Mistral, DeepSeek, xAI, Groq, OpenRouter, Ollama, LM Studio; indirizzi dalla documentazione ufficiale con la fonte; stato della chiamata di strumenti `verified`/`documented`/`unverified`, marcato nel 44; nessun modello fisso; una chiave per profilo | 2026-10-17 | decisione del proprietario, `30` §3.1.1, `31` §3.1, `44` §3.6 | |
| D04 | Cache da più thread e processi: orfani eliminati solo se più vecchi di 10 minuti (configurabile, nel log), pulizia una volta per processo alla prima apertura | 2026-10-16 | decisione del proprietario, `04` §3 | dalla verifica fallita del 05 §3.2 |
| Filtro della tabella (42) nella v1 | Fuori dalla v1, come scritto nella 42 §3.1 (D6/D8 dopo la v1) | 2026-10-21 | decisione del proprietario, `42` §13 | richiesta della parte 5 |
| Numeri dei testi di terzi (34) | Un numero trovato solo in un testo di terzi è `external_text`, mai `verified`: in contrasto tra T5 e §3.5 vince §3.5 (T5 e §3.3 corretti); i valori numerici dei risultati, anche di un catalogo, si verificano | 2026-10-22 | decisione del proprietario, `34` §3.3, §12 | sprint 6b |
| Fonte dei testi esterni in `catalog.rows` (32) | Scritta una volta in testa al risultato (`external_source`) invece che su ogni colonna, unità e UCD; ogni valore resta attribuibile | 2026-10-22 | decisione del proprietario, `32` §3.6, §13 | sprint 6b |
| Limiti dell'assistente (35) | Valgono le specifiche: 10 comandi e 5 minuti per risposta | 2026-10-22 | decisione del proprietario, `35` §3 | sprint 6c |
| Tolleranza di R2 (34) | Vale solo l'arrotondamento (mezza unità dell'ultima cifra scritta); "e troncamento" tolto dalla scelta (3) | 2026-10-22 | decisione del proprietario, `34` §13 | sprint 6c |
| Scelte minori dello sprint 6b (34) e scelte 4, 5, 6 del 32 | Confermate: identificativi solo per testo, numeri nelle stringhe solo per testi esterni, parametri e utente, ordine delle categorie e altre (34 §3.6bis); niente SHA-256, stringhe delle calcolatrici di AstroTwo, `ASTROTWO_MESSAGE_CODES` (32 §13) | 2026-10-22 | decisione del proprietario | sprint 6c |
| Ultima richiesta dopo il limite di chiamate (30, 35) | Gli strumenti restano nella richiesta con `tool_choice = none` (`{"type": "none"}` per Anthropic, `"none"` per Chat Completions) invece di una richiesta senza strumenti; da provare con le chiavi dell'utente | 2026-10-22 | decisione del proprietario, `30` §3.5, `35` §3.3 | sprint 7a |
| Scelte minori dello sprint 6c (35) | Confermate tutte e 12 (§3.11 del 35) | 2026-10-22 | decisione del proprietario, `35` §13 | sprint 7a |
| Scelte minori dello sprint 7a (44) | Confermate tutte e 12 (§3.10 del 44) | 2026-10-23 | decisione del proprietario, `44` §13 | sprint 7b |
| Scelte minori dello sprint 7b (44) | Confermate tutte e 5 (§3.11 del 44) | 2026-10-23 | decisione del proprietario, `44` §13 | sprint 7c |
| D32-1 | (c) identificativi del gruppo fisso nella descrizione di `catalog` (05, 32); (b) `CATALOG_UNKNOWN` con le tabelle che cominciano con l'identificativo (13); (a) comando di ricerca nell'elenco dei cataloghi dopo la v1 (D32-2) | 2026-10-23 | decisione del proprietario, `32` §13, `13` §7 | sprint 7c |
| D13-21 | (a) nella v1 `NO_COORD_COLUMNS` con le colonne candidate per RA e Dec nel messaggio; (b) `lon`/`lat` scelti dall'utente solo se un catalogo reale lo richiede | 2026-10-23 | decisione del proprietario, `13` §13 | sprint 7c |
| Distanza su sfondo HiPS (05, 41) | `measure.distance` ha due forme: pixel di un'immagine o posizioni celesti (`sky1`, `sky2`), così si misura anche senza immagine | 2026-10-23 | decisione del proprietario, `05` §7, `41` §3.19 | sprint 4g |
| Mac di riferimento (D41-4, 41) | Due riferimenti: **minimo** iMac21,1 con M1 e 8 GB (obiettivi P1–P6 da rispettare anche lì), **comodo** MacBook Air M5 con 32 GB dal 2 novembre 2026 | 2026-10-24 | decisione del proprietario, `41` §3.15, §13 | sprint 4h |
| Opzioni della distanza (41) | Barra sul cielo con unità, aggancio e finestra del centroide, ricordate con `prefs.set` (`tools/…`) | 2026-10-23 | decisione del proprietario, `41` §3.19 | sprint 4g |
| Strumento sconosciuto (32) | Il risultato d'errore `TOOL_NOT_EXPOSED` porta l'elenco `valid_tools`; nulla eseguito | 2026-10-23 | richiesta del proprietario, `32` §3.5 | sprint 7b |
| Testo di `PLANETARY_DATA_DISABLED` | "i dati planetari non sono disponibili in questa versione" finché la preferenza non esiste; solo italiano (D40-1, inglese con D40-3); comportamento invariato | 2026-10-21 | decisione del proprietario, `19` §10 | |

## 6. Decisioni aperte

Ogni decisione qui ha una voce corrispondente nel file `.md` pertinente.
Etichette: `A1–A9` definite in `01-architettura.md`, `AP1` in
`03-parita-aladin.md`, `AM1` qui sotto. Le decisioni già prese sono in §5.

L'elenco completo e aggiornato di **tutte** le decisioni aperte — con opzioni,
raccomandazioni e dipendenze — è in `decisioni-aperte.md`. Alla creazione
erano 47, smistate in tre gruppi; **il 2026-10-04 sono state decise tutte e 22
le decisioni del Gruppo 1** (A1, A5, AP5, D10-2 … D17-4 — esiti in §5 qui
sopra): restavano 25 aperte. Il 2026-10-08 AP6 è stata aggiunta e decisa
(§5) e l'elenco è stato completato con AP1–AP4 e con la parte aperta di DC1,
DC3, DC4; AP3 decisa lo stesso giorno → 31 aperte; dopo la lettura AP5 si è
aggiunta la proposta AM1 per H21 (32 aperte), accettata lo stesso giorno →
31 aperte; con i moduli 18 e 19 se ne aggiungono 13 (44); il 2026-10-09
applicate le decisioni su D19-2, D19-3, D19-4 (42); con la checklist del
livello 1 (14); con il completamento dei moduli 11–17 (20); con le decisioni
su D11-6, D13-7, D14-7, D14-8, D15-5 → 16 aperte; con le verifiche del
modulo 10 in fase codice (D10-7, D10-8) → 18 aperte; con D10-7 e D10-8
decise, le nuove D10-9 e D11-7 e le CA1–CA4 di `04-cache.md` → 22 aperte;
con CA1–CA4 e D11-7 decise → 17; con la nuova D11-8 → 18; con la nuova
**A11 — licenza di AstroTwo** (decisa poi il 2026-10-17: GPL-3.0-or-later) → **19 aperte** (Gruppo 1 = 0, Gruppo 2 = 4: A2,
A6, A9, A11 per `60`/`40`; Gruppo 3 = 15, con D10-9 da decidere con il 41,
D11-8 con 20 e 41, A10 ormai solo per cataloghi e HiPS). Il 2026-10-10, dopo
il modulo 13 fino a P5: 17; **dopo il modulo 14 e P6 del 13: 21 aperte**
(decisa D14-5; nuove D14-10, D14-11, D14-12, D13-17, D13-18 nel Gruppo 3:
Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 17). Il 2026-10-11, decise le cinque
e aperte D13-19 e D13-14c: 18 aperte; poi, con il modulo 15, decise D13-19
e D15-6 e aperte D13-20, D15-8, D15-9: 19 aperte; poi, con il modulo 16,
decise D13-20, D15-8, D15-9 e aperte D16-6, D16-7: 18 aperte. Il
2026-10-12, decise D16-6, D16-7 e A10 (HiPS) e aperte dal codice del 12
D12-6 (nomi dei corpi), D12-7 (`hips_frame = ecliptic`), D12-8 (Allsky):
18 aperte; poi, sempre il 2026-10-12, decise D12-6, D12-7, D12-8 e D17-5 e
aperta dal 17 D17-7 (geometria sferica delle forme): 15 aperte. Il
2026-10-13 (decisioni del 2026-10-12), decise D17-7, D18-5, D18-6 e aperte
D17-8 (`distance_to`) e D18-7 (sessagesimali in `skydist`): 14 aperte. Il
2026-10-13 (decisioni del 2026-10-13), decise D17-8 e D18-7 e aperte D17-9
(`distance_to` per ellisse, freccia, testo, tracciato aperto), D19-8 (PDS3
con `pdr`) e D19-9 (PDS da URL): 15 aperte. Lo stesso giorno decise D17-9 e
D19-9, D19-8 rimandata (resta nel Gruppo 3): 13 aperte. Il 2026-10-14 aperta
D16-8 (MOC da immagine con i blocchi): 14 aperte. Lo stesso giorno decisa
D16-8 e aperta D14-13 (reindirizzamento http → https dell'ESO): 14 aperte.
Il 2026-10-15, con le specifiche della prima versione dell'interfaccia,
decise A9, D10-9 e D11-8 e aperte D05-1, D05-2, D05-3, D40-1, D40-2,
D41-1…D41-4: 20 aperte. Lo stesso giorno decise D05-1, D05-2, D40-1,
D41-1…D41-4, rimandate D05-3 e D40-2, aperta D40-3: **14 aperte** (Gruppo
1 = 0, Gruppo 2 = 3, Gruppo 3 = 11). Il 2026-10-16 aperta D05-4 (15 aperte),
decisa il 2026-10-17: **14 aperte** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 11).
Lo stesso giorno, con la parte 3b del codice della v1, aperta D40-4
(scorciatoia della modalità notte): **15 aperte** (Gruppo 1 = 0, Gruppo 2 =
3, Gruppo 3 = 12). Il 2026-10-23 aperte D32-1 (come l'assistente trova
l'identificativo di un catalogo VizieR) e D13-21 (colonne di posizione ambigue
in una regione chiesta dall'assistente): **16 aperte** (Gruppo 1 = 0, Gruppo 2 =
2, Gruppo 3 = 14). Lo stesso giorno, con lo sprint 7c, decise D32-1 e D13-21 e
rinviata a dopo la v1 la nuova D32-2 (comando di ricerca nell'elenco dei
cataloghi): **15 aperte** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 13).
Quando una decisione viene chiusa, si aggiorna prima il file di origine e
poi `decisioni-aperte.md`.

| # | Decisione | File pertinente | Stato |
|---|---|---|---|
| A2 | Strumento di packaging del `.dmg` | `01-architettura.md`, `60-distribuzione-dmg.md` | orientamento (2026-10-09): PyInstaller + dmgbuild; non blocca il livello 1, blocca l'approvazione di `60` |
| A6 | Firma e notarizzazione Apple | `01-architettura.md`, `60-distribuzione-dmg.md` | orientamento (2026-10-09): sì, notarizzazione con account Apple Developer solo al momento della distribuzione; blocca l'approvazione di `60` |
| A8 | Livello di compatibilità con lo scripting di Aladin | `01-architettura.md`, `24-analisi-pipeline-riproducibili.md` | rimandata: strada scelta = scripting principale in Python; compatibilità con i comandi Aladin da decidere **dopo il completamento del livello 1** |
| D05-3, D40-2 | Adattatore del 19; avvio tramite URL (H18) | `05`, `40` §13 | **rimandate** il 2026-10-15 (Gruppo 3) |
| D40-3 | Messaggi dei moduli in inglese e italiano: catalogo codice → testo con `params`; i moduli 10–19 e il `05` restituiscono codice + `params` (testo originale conservato); inglese verso l'IA | `40-ui-finestra-principale.md` §13, §3.7.1 | **decisa il 2026-10-24; chiusa il 2026-10-25** (applicata a `04`, `05`, 10–19, `30`–`35`, `40`, `41`, `42`, `44` negli sprint 8b–8e; T18 su tutto `src/astrotwo`) |
| D40-5 | Posizione del catalogo dei messaggi (non in `ui/`, serve anche all'IA): modulo neutro `src/astrotwo/messages_catalog.py` | `40-ui-finestra-principale.md` §13 | **decisa il 2026-10-24** (proprietario, come raccomandato) |
| D40-7 | Messaggi annidati (causa, motivo del tile corrotto, risposta di un altro modulo) nel catalogo: tipo di parametro `message`/`messages` reso in modo ricorsivo (profondità massima 3), testo di terzi sempre esterno | `40-ui-finestra-principale.md` §13, §3.7.1 | **decisa il 2026-10-24** (proprietario, opzione (b)) |
| D40-6 | Varianti per ragione nel catalogo: sotto-voci scelte dal parametro `reason`, nessun codice cambia | `40-ui-finestra-principale.md` §13, §3.7.1 | **decisa il 2026-10-24** (proprietario, tra tre opzioni) |
| D41-7, D41-8 | P1 (1 milione di simboli, 46,0 ms contro 16,7) e P5 (avvio a freddo, 4,46 s contro 3) non raggiunti sull'iMac M1 8 GB; obiettivi invariati; sprint di prestazioni dopo la prova completa (annotato anche `test_t14_latency`, 170 ms una volta) | `41-ui-visualizzatore-cielo.md` §13 | **da decidere** (Gruppo 3, aperte il 2026-10-24) |
| D41-5, D41-6 | Zoom e spostamento su una griglia di pixel; epoca del COOSYS persa da `catalog.set_columns` | `41-ui-visualizzatore-cielo.md` §13 | D41-5 **rinviata a dopo la v1** il 2026-10-21; D41-6 **da decidere** (Gruppo 3, aperta il 2026-10-21) |
| D40-4 | Scorciatoia da tastiera della modalità notte (View → Night mode) | `40-ui-finestra-principale.md` §13 | **decisa il 2026-10-17: ⌃⌘N** |
| AM1 | Separazione di un modulo o creazione di moduli nuovi (vedi nota sotto) | `panoramica.md` | **decisa il 2026-10-04:** accettate entrambe le proposte — `18-core-calcolatrici.md` (da H4) e `45-ui-viste-multiple.md` (da H2): file registrati in questo file e in `INDICE.md` con stato `non esiste` (si scrivono con il rispettivo gruppo). La meccanica AM1 resta valida per proposte future, che richiedono però una nuova decisione esplicita del proprietario (vedi nota sotto). **Proposta del 2026-10-08, ACCETTATA lo stesso giorno (decisione del proprietario):** riga **H21 — dati planetari** di `03-parita-aladin.md` (trovata con la lettura AP5): modulo dedicato oppure estensione di `10` (sistemi di riferimento planetari), `12` e `13`; accettata come nuovo modulo `19-core-dati-planetari.md` (livello 1), registrato in §4 e in `INDICE.md`. **Proposta del 2026-10-15, ACCETTATA lo stesso giorno:** nuovo file generale `05-comandi-sessione.md` (livello 1, registro dei comandi e sessione), scritto in `bozza` |
| D32-1, D13-21, D32-2 | Come l'assistente trova l'identificativo di un catalogo VizieR; colonne ambigue in una regione chiesta dall'assistente; comando di ricerca nell'elenco dei cataloghi | `32` §13, `13` §13 | D32-1 e D13-21 **decise il 2026-10-23**; D32-2 **rinviata a dopo la v1** (Gruppo 3, proposta di comando nuovo del `05`: attende la decisione del proprietario) |
| D14-13 | URL dei servizi dell'ESO in http: il reindirizzamento a https codifica due volte l'URL e la richiesta viene rifiutata | `14-core-protocolli-vo.md` §13 | **da decidere** (aperta il 2026-10-14); oggi la demo usa https, nessuna modifica al codice del 14 |
| AP1 | Validazione della parità con Aladin | `03-parita-aladin.md` | rimandata: **alla fine**, confrontando i risultati di AstroTwo e di Aladin sugli stessi dati |

Le altre decisioni aperte di `03-parita-aladin.md` (AP2 profondità della
parità, AP4 scripting legacy; AP3 Aladin Lite è decisa, §5) e di `02-convenzioni.md`
(parte aperta di DC1, DC3, DC4) sono elencate nel file di origine e, dal
2026-10-08, in `decisioni-aperte.md` (AP2, DC1, DC3, DC4 nel Gruppo 2;
AP1 e AP4 nel Gruppo 3). **AP5** (verifica documentale residua) è in §5:
**AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08**, prima di scrivere i gruppi successivi; esito
parziale 2026-10-04 = lette 1–5.7.2 e indice completo, esistenza di tutte le
funzioni verificata.

**Nota su AM1:** durante la scrittura delle specifiche potrebbe emergere che un
modulo va diviso o che serve un modulo aggiuntivo. Non si aggiungono file di
propria iniziativa: la proposta va registrata qui e approvata dal proprietario.

## 7. Prossimi passi

**Prossimo (2026-10-25, dopo lo sprint 8e):** la traduzione dei messaggi (D40-3) è conclusa (8b–8e); resta lo sprint di prestazioni per D41-7 e D41-8, poi D14-13, le verifiche con le chiavi dell'utente (modelli di Anthropic, JSON Schema, LM Studio) e le specifiche dei gruppi rimanenti.

0. **Subito (FASE: CODICE – interfaccia v1, 2026-10-17):** verifiche
   prima del codice fatte (licenze, `keyring`, OpenGL, Ollama, cache con
   D04; origine di `httpx2` verificata e accettata il 2026-10-17); livello 1
   allineato (10, 11, 12; adattatore del 18 con D05-4 decisa il
   2026-10-17). **Divisione del codice della v1 approvata dal proprietario
   il 2026-10-17:** 05 registro e sessione → 31/30 chiavi e provider (con i
   profili predefiniti) → finestra 40 → visualizzatore 41 → 42 → 32/34/35
   → pannello 44. **Parti 1 (05) e 2 (31, 30 con i profili predefiniti)
   scritte il 2026-10-17** (scelte minori nel §13 di 05 e 30, da
   confermare; T8 del 31 sul Portachiavi reale, corretto il 2026-10-17 per
   la cartella home temporanea dei test, e lista di controllo manuale del 30
   con le chiavi dell'utente da fare a mano). **Parte 3 (finestra 40)
   scritta il 2026-10-17** (verificati `QStyleHints.colorScheme` e cifre
   tabulari; prova a mano fatta dal proprietario). **Parte 3b
   (correzioni dell'aspetto del 40) scritta il 2026-10-17** (icone Lucide
   con licenza verificata); D40-4 decisa il 2026-10-17 (⌃⌘N). **Parte 4,
   sprint 4a (41: sfondo HiPS, zoom, spostamento) scritta il 2026-10-17,
   sprint 4b (tile FITS, coordinate e valore sotto il mouse) scritto il
   2026-10-18, con correzioni il 2026-10-19, sprint 4c (griglia, nord e
   barra di scala) scritto il 2026-10-20, sprint 4d (immagine FITS locale) scritto il
   2026-10-20, sprint 4e (cataloghi e clic) scritto il 2026-10-21, sprint 4f (MOC, pannello dei livelli, corpi diversi) scritto il 2026-10-21** (D41-6 decisa); sprint 4g scritto il 2026-10-23 (strumenti: distanza, Simbad), **sprint 4h scritto il 2026-10-24 (PNG, cambio di base in un passo, test `perf`): il 41 è completo**. **Parte 5 (42), sprint 5a (tabella, ordinamento, selezione sincronizzata, record) scritto
   il 2026-10-21, sprint 5b (dialoghi delle colonne, T7) il 2026-10-22**; scelte minori di 5b confermate il 2026-10-22. **Parte 6 (IA: 32, 34, 35), sprint 6a (32: registro degli strumenti, `ai/tool_registry.py`) sprint 6b (34: verifica dei numeri, `ai/result_verification.py`) e sprint 6c (35: assistente, `ai/chat_assistant.py`, collegato alla coda del 40) scritti il 2026-10-22**; **Parte 7 (44: pannello dell'assistente), sprint 7a scritto il 2026-10-22** (`ui/ai_panel.py`; Markdown di Qt verificato; scelte minori confermate il 2026-10-23) **e sprint 7b scritto il 2026-10-23** (numeri evidenziati per stato, latenza, prove con il servizio simulato; scelte minori confermate il 2026-10-23) **e sprint 7c scritto il 2026-10-23** (D32-1 e D13-21 decise, test instabili resi deterministici); prossimo: le prove con le chiavi dell'utente (lista di controllo manuale del 35 §12 e del 30 §12, con `tool_choice = none`). Da verificare all'inizio delle parti che li usano: sottoinsieme di JSON Schema e modelli di Anthropic
   con le chiavi dell'utente (30, 32), LM Studio.
1. Revisione e approvazione dei file generali (`01`, `02`, `03`, questo file, `INDICE.md`).
2. **Prima di scrivere il gruppo analisi (20–24):** **AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08**;
   dettagli integrati in `03-parita-aladin.md` (righe H20–H27 e correzioni
   D12/E3/F4). Esiti validati e AM1 per H21 accettata il 2026-10-08
   (`19-core-dati-planetari.md`).
3. Scrittura dei file di modulo in gruppi, un gruppo alla volta:
   nucleo 10–19 in bozza (18 e 19 scritti il 2026-10-08); poi analisi (20–24), poi IA
   (30–35), poi interfaccia (40–45, con `45-ui-viste-multiple.md`), poi
   avanzate (50–53), poi distribuzione e test (60–61). Il Gruppo 1 è vuoto
   e nessuna decisione del Gruppo 2 blocca più 01–03 e 10–19 (checklist del
   2026-10-09). **Livello 1 approvato** (01, 02, 03, 10–19). Prossimo passo:
   la dichiarazione "FASE: CODICE – livello 1" del proprietario (`CLAUDE.md`);
   le verifiche "da verificare prima del codice" dei moduli si fanno prima di
   scrivere ciascun modulo. **A1 (PySide6) e A5 (interfaccia a capacità) sono già decise:
   i moduli 40–45 e 30–35 possono essere scritti senza attendere conferme.**
4. Dopo ogni gruppo: aggiornare questo file e `INDICE.md`, fermarsi e far validare.
5. Quando tutti i file necessari sono `approvato`, chiedere per iscritto
   "FASE: CODICE" e iniziare dal livello 1 (struttura `src/astrotwo/` già decisa).
6. Dopo il completamento del livello 1: decidere A8 (compatibilità con i comandi
   di Aladin).
7. Alla fine del progetto: validazione della parità con Aladin (AP1),
   confrontando i risultati sugli stessi dati.
8. Decisioni ancora aperte (15, al 2026-10-17): elenco in `decisioni-aperte.md` (Gruppo 1 =
   0, Gruppo 2 = 3, Gruppo 3 = 12); vanno chiuse prima dell'approvazione del modulo
   interessato o, per il Gruppo 3, al momento del codice.

## 8. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione di `TEMPLATE-modulo.md`, `panoramica.md`, `INDICE.md`, `01-architettura.md`, `02-convenzioni.md`, `03-parita-aladin.md` (tutti in stato bozza). Nessun file di modulo ancora scritto. |
| 2026-10-04 | agente di sviluppo | Decisioni del proprietario registrate. **Prese** (da aperte a prese): A3 struttura `src/astrotwo/` con sotto-pacchetti `core/analysis/ai/ui/advanced` e `tests/` specchiato; A4 Python 3.12 + `pyproject.toml` + `uv`; A7 cache SQLite (cataloghi) + file su disco (riquadri HiPS/FITS) con limite configurabile e provenienza mostrata. **Orientamento, da confermare:** A1 = PySide6 (Qt); A5 = interfaccia a capacità (chiamata di strumenti, streaming) con provider cloud + endpoint compatibile OpenAI. **Rimandate:** A8 = scripting principale in Python, compatibilità con i comandi Aladin dopo il livello 1; AP1 = validazione parità alla fine, su stessi dati. **Rietichettatura per coerenza tra i file:** A5 ora = provider IA (prima in `01` era A6), A6 ora = firma Apple (prima in `01` era A5), A8 ora = scripting (prima era A6 in questo file), AM1 = aggiunta/separazione moduli (prima era A8 in questo file), AP1 = parità (prima era A7 in questo file). |
| 2026-10-04 | agente di sviluppo | `03-parita-aladin.md` aggiornato con l'esito della verifica documentale (fonti: manuale utente Aladin Desktop ed. giugno 2022 sezioni 1–5.8, manuale comandi script v12.0, FAQ). Nuovi valori di Copertura; 23 righe verificate, 12 corrette, 4 non trovate; D12 spostata in una sezione "funzioni extra AstroTwo" (livello 2, modulo 20); nuova sezione H con 16 funzioni trovate e mancanti (H1–H16); nota di licenza GPL v3; nuova decisione AP5 (sezioni 5.7.3–8 [indicate in origine come 5.9–8] del manuale ancora da leggere); test T2 aggiornato, aggiunto T5. Proposte di nuovi moduli da H2 e H4 registrate in AM1 (`45-ui-viste-multiple.md`, `18-core-calcolatrici.md`). |
| 2026-10-04 | agente di sviluppo | **Gruppo nucleo scritto:** creati `10-core-coordinate-wcs.md`, `11-core-immagini-fits.md`, `12-core-hips.md`, `13-core-cataloghi.md`, `14-core-protocolli-vo.md`, `15-core-crossmatch.md`, `16-core-moc.md`, `17-core-misure.md` (tutti `bozza`, 14 sezioni ciascuno). Vincoli A7 (cache) e regole d'oro riflessi in ogni file; perimetri allineati alle assegnazioni di `03-parita-aladin.md` (inclusi C4/H9/H10/H11/H12/H14); decisioni aperte nuove: D12-1…D17-6. Stati aggiornati in questo file e in `INDICE.md` (bozza 14, non esiste 22). |
| 2026-10-04 | agente di sviluppo | **Decisione del proprietario P11:** la parità con Aladin è il minimo, non il traguardo — AstroTwo include tutte le funzioni di `03-parita-aladin.md`, anche non confermate nella documentazione (principio scritto anche in `01-architettura.md` §2). In `03-parita-aladin.md` nuovo valore `inclusa (decisione del proprietario)`: C3, F2, G3 ed E4 passate da `non trovata` (nessuna riga `non trovata` resta). Funzioni descritte per intero nei moduli: C3 in `12-core-hips.md` (`add_hips`, errori, test T7–T8), F2 in `17-core-misure.md` (PA nord→est, casi limite ai poli, test T8–T9), G3 SAMP in `14-core-protocolli-vo.md` (tabelle/selezioni/puntamenti, interfaccia in `42`), E4 SSA in `14-core-protocolli-vo.md` (ricerca e caricamento spettri, analisi in `21`). D12-2, D17-1 e D14-2 chiuse come decise; nuova D14-6 (dettagli tecnici SSA). Titolo del 14 aggiornato in §4; `INDICE.md` aggiornato. Stati invariati (bozza 14, non esiste 22). |
| 2026-10-04 | agente di sviluppo | **AM1 DECISA:** accettate le due proposte — creati gli elenchi `18-core-calcolatrici.md` (H4: calcolatrice algebrica, unità, pixel, coordinate, tempo; livello 1; dipende da `10` e `11`) e `45-ui-viste-multiple.md` (H2: viste 2/4/9/16 con sincronizzazione, blocco, miniature; interfaccia; dipende da `41` e `40`) in §4 di questo file e in `INDICE.md`, entrambi `non esiste` (file veri da scrivere col gruppo). Righe H2 e H4 di `03-parita-aladin.md` puntano ai nuovi moduli; §7 passi aggiornati; `10-core-coordinate-wcs.md` corretto nei riferimenti A5/H4. In parallelo: **D14-2 riaperta** in `14-core-protocolli-vo.md` §13 (scelte tecniche residue: tipi di messaggio SAMP, hub interno vs libreria); D12-2 e D17-1 restano chiuse (nessuna scelta tecnica residua). Stati: bozza 14, non esiste 24. |
| 2026-10-04 | agente di sviluppo | Creato `decisioni-aperte.md` (stato: bozza): raccolte tutte le 47 decisioni ancora aperte — §13 di `10`–`17` (40), `01-architettura.md` §5 (`A1`, `A2`, `A5`, `A6`, `A8`, `A9`), `03-parita-aladin.md` §6 (`AP5`) — e smistate in tre gruppi: Gruppo 1 = 22 bloccanti per altri moduli (con opzioni, pro/contro, raccomandazioni da confermare e dipendenze), Gruppo 2 = 20 bloccanti solo per l'approvazione del modulo, Gruppo 3 = 5 rimandabili al momento del codice; escluse le chiuse D12-2 e D17-1, D14-2 mantenuta per la parte tecnica residua. Registrato in `INDICE.md` (bozza 15, totale 39) e linkato in §4 e §6 di questo file. Nessuna decisione risolta qui: le raccomandazioni sono proposte da confermare dal proprietario. |
| 2026-10-04 | agente di sviluppo | **22 DECISIONI DEL PROPRIETARIO (Gruppo 1 di `decisioni-aperte.md`) passate da aperte a prese.** A1 = PySide6 (Qt), rendering OpenGL delle mappe da specificare in 41; A5 = interfaccia a capacità (chiamata di strumenti, streaming) con provider cloud + endpoint compatibile OpenAI; AP5 = sezioni 5.7.3–8 [indicate in origine come 5.9–8] del manuale di Aladin da leggere **prima di scrivere i gruppi successivi**; D10-2/D13-2 = epoca dai metadati e mai assunta, epoca di visualizzazione = epoca dell'immagine se nota altrimenti J2000, epoca sempre nel risultato, cataloghi con propria epoca di riferimento; D10-3 = cache nomi in tabella SQLite separata in A7; D10-4 = lista proiezioni = Aladin (da verificare con AP5), TAN immagini / AIT all-sky, un test per proiezione; D11-1 = tipo nativo in memoria, calcoli in float64, float32 solo display; D11-3 = cache su disco 5 GB di default, configurabile; D12-5/D16-5 = HEALPix nel 16, tile nel 12; D13-1 = grammatica `search` alla Aladin validata prima dell'esecuzione; D13-5 = operazioni non distruttive, in-place con flag nel report; D13-6 = colonna DataLink nel 13, risoluzione nel 14; D14-1 = `pyvo` per TAP/DataLink, `astropy.samp` da valutare, licenze da riverificare; D14-2 = hub SAMP attivo o proprio, perimetro tabelle/selezioni/puntamenti, immagini come estensione; D16-1 = `mocpy` (licenza/macOS da verificare); D16-2 = MOC in cache FITS IVOA, export JSON/testo; D16-3 = JD interno, ISO 8601 in UI/file, scala sempre dichiarata, scala IVOA per i MOC temporali; D17-2 = geometria 17 / rendering 41; D17-3 = tag nella sessione del 24 (riferimenti e operazioni, non pixel, rieseguibile); D17-4 = fotometria F4 interamente nel 20. Aggiornati §5 (esiti), §6 (A1/A5/AP5 rimosse dalle aperte), §2 e §7 (AP5 prima del gruppo analisi); file di origine `01`, `02` (DC1/DC2/DC6), `03`, `10`, `11`, `12`, `13`, `14`, `16`, `17` e `decisioni-aperte.md` allineati. Aperte rimaste: 25 (Gruppo 1 = 0, Gruppo 2 = 20, Gruppo 3 = 5). Stati invariati. |
| 2026-10-04 | agente di sviluppo | **Esito parziale di AP5 e correzioni alla parità** (`03-parita-aladin.md`): fonte manuale utente Aladin Desktop ed. **febbraio 2021**, lette **sezioni 1–5.7.2 e indice completo** — AP5 resta **aperta** per i dettagli di **5.7.3–8**, esistenza di tutte le funzioni verificata dall'indice. **D12 corretta** (l'estrazione in Aladin esiste, sezione 6.5, via SExtractor esterno): riga tornata nella sezione D come `verificata` (AstroTwo: estrazione nativa nel 20, libreria da decidere), sezione "funzioni extra" vuota. Aggiunte **H17** (Exam, 5.9), **H18** (avvio via URL, 7.2), **H19** (VOApp/VOObserver, 7.5) con "dettagli da leggere" e modulo proposto; note su **A13** (stampa 5.18), **B11** (mosaici e blink), **E4** (spettri mostrati nel 21), **F4** (risoluzione fotometria su HiPS). `01-architettura.md` §8: nuovo **requisito non funzionale** — obiettivi di prestazioni ≥ Aladin (righe di catalogo, immagini, cubi; sezione 8.3 da leggere) da definire in `61-strategia-test.md`. `INDICE.md`: annotato in `24-analisi-pipeline-riproducibili.md` che ogni azione dell'interfaccia = un comando registrato (come la cronologia di Aladin). Conteggi 03: 59 righe A–G + 19 H + 0 extra = 78. Stati invariati (bozza 15, non esiste 24, totale 39). |
| 2026-10-04 | agente di sviluppo | Creato `riassunto.md` (bozza): il progetto in 5 righe — cos'è (successore di Aladin, `.dmg`, Python 3.12, PySide6, IA a capacità con provider scelti dall'utente), struttura a 4 livelli con dipendenze solo verso il basso, regole d'oro (l'IA non calcola, chiavi nel Portachiavi, riproducibilità, specifica approvata prima del codice), stato (16 `bozza`, 24 `non esiste`, 0 `approvato`, 25 decisioni aperte) e prossimi passi (AP5 prima del gruppo analisi, poi "FASE: CODICE"). Registrato in §4 qui sopra e in `INDICE.md` (bozza 16, totale 40). |
| 2026-10-08 | Claude Code | **Manutenzione delle specifiche** (nessun modulo nuovo, stati invariati: bozza 16, non esiste 24, totale 40). (1) Migrazione `AGENTS.md` → `CLAUDE.md`: riferimenti sostituiti in `01-architettura.md`, `INDICE.md`, `TEMPLATE-modulo.md` e qui (§2, §3, §5); `AGENTS.md` rimosso dalla radice (spostato nel Cestino). (2) Intervalli dopo AM1: nucleo 10–18 e interfaccia 40–45 in `01-architettura.md` §3/§6 e qui in §3. (3) Riferimento AP5: corretto = **5.7.3–8**; nelle voci di registro di `03-parita-aladin.md`, `decisioni-aperte.md`, `INDICE.md` e qui la vecchia dicitura "5.9–8" è annotata come "5.7.3–8 [indicate in origine come 5.9–8]". (4) Nuova decisione aperta **AP6 — edizione di riferimento del manuale di Aladin** (giugno 2022 o febbraio 2021), non scelta: in `03-parita-aladin.md` §2/§6, `decisioni-aperte.md` Gruppo 2 e §6 qui; aperte 26 (Gruppo 2 = 21, Gruppo 3 = 5). (5) Refusi: "igualmente" in `01`, "Ånm" → "Å, nm" in `02`. Aggiornati §2, §6, §7, `INDICE.md` e `riassunto.md`. |
| 2026-10-08 | Claude Code | **Decisioni del proprietario sui punti aperti della manutenzione.** **AP6 decisa:** edizione di riferimento = la più recente ufficiale del manuale utente di Aladin Desktop → verificata sul sito del CDS: **giugno 2022** (§5; file di origine `03-parita-aladin.md` §2/§6). Edizione indicata accanto ai numeri di sezione del manuale in `01` §8, `03`, `10`, `14`, `decisioni-aperte.md` e qui (§2); numeri con numerazione diversa nell'ed. giugno 2022 marcati "numerazione da verificare" senza correggerli (A13 5.18, D12 6.5, H17 5.9, H18 7.2, H19 7.5). `decisioni-aperte.md` completato: AP2, AP3, DC1 (parte aperta), DC3, DC4 nel Gruppo 2; AP1 e AP4 nel Gruppo 3 → aperte **32** (Gruppo 1 = 0, Gruppo 2 = 25, Gruppo 3 = 7); §6 corretto (non più "elencate solo in quel file"). AP5 scritta in forma uniforme ("AP5 decisa; lettura delle sezioni 5.7.3–8 ancora da fare") in §2, §5, §6, §7 e nei file `03`, `10`, `14`, `decisioni-aperte.md`, `INDICE.md`, `riassunto.md` (voci di registro non toccate). `03` T3/T4 → moduli 10–18; §7 punto 3 → "nucleo 10–17 in bozza, 18 da scrivere"; §3 nucleo con le calcolatrici (18); D14-6 rinominata "inclusione decisa; parte tecnica aperta" in `14`; DC1/DC3/DC4 rimandati a `decisioni-aperte.md` in `02` §9. Refusi: "i 8" → "gli 8", "approvato" → "approvazione", "uno gruppo" → "un gruppo" (qui); "reproducerlo" → "riprodurlo", "mostro" → "mostra" (`03`). Stati invariati: bozza 16, non esiste 24, totale 40. |
| 2026-10-08 | Claude Code | **Decisioni del proprietario (seguito):** numeri di sezione del manuale riportati all'ed. giugno 2022 in `03` e qui (A13 → 5.19, D12 → 6.6, H17 → 5.10 "study"/« examen », H19 → 7.4), marcatura "numerazione da verificare" tolta; H18 lasciata con la fonte dell'ed. febbraio 2021 (sezione 7.2 "Launch of Aladin by URL", assente nell'ed. giugno 2022, dove l'avvio da URL compare solo nella sezione 2). AP5 riscritta ovunque come "AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) ancora da fare" (`03`, `10`, `14`, `decisioni-aperte.md`, `INDICE.md`, `riassunto.md`, qui §2/§5/§6/§7); nota sulla numerazione in `03` §2. **AP3 decisa** (Aladin Lite escluso dalla parità; versione web → AM1): §5 qui, `03` §4/§6, tolta dal Gruppo 2. Smistamento dei gruppi confermato. Aperte: **31** (Gruppo 1 = 0, Gruppo 2 = 24, Gruppo 3 = 7). Stati invariati. |
| 2026-10-08 | Claude Code | **Lettura AP5 completata** (sezioni 5.9–8 del manuale utente ed. giugno 2022), integrata in `03-parita-aladin.md`: note su 20 righe, correzioni D12/E3/F4, dettagli H17–H19, nuove righe H20–H27 (86 righe in tutto). **Nuova proposta AM1: H21, dati planetari** (§6; nessun file creato), registrata anche in `decisioni-aperte.md` Gruppo 1 (smistamento proposto). AP5 scritta come "AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08" in §2/§5/§6/§7 e in `10`, `14`, `decisioni-aperte.md`, `INDICE.md`, `riassunto.md`. Aperte: **32** (Gruppo 1 = 1, Gruppo 2 = 24, Gruppo 3 = 7). Nessun modulo del gruppo analisi scritto. Stati invariati: bozza 16, non esiste 24, totale 40. |
| 2026-10-08 | Claude Code | **Decisioni del proprietario sugli esiti di AP5:** AM1 per H21 **accettata** → `19-core-dati-planetari.md` (livello 1, `non esiste`) registrato in §4 e in `INDICE.md`, riga H21 di `03` collegata, decisione chiusa nel Gruppo 1 di `decisioni-aperte.md`; nucleo = 10–19 (§3, `01` §6, test T3/T4 di `03`). `01` §8: obiettivo minimo di prestazioni = almeno 1 milione di sorgenti con 1 GB di RAM. `10`: D10-4 precisata con le 8 proiezioni del manuale (T7 esplicito). `02`: nuova DC7 (convenzione dei pixel FITS/numpy, conversione unica nel 10, moduli che la usano). `03`: H17 → SED nel 20; H19 → API Python nel 24 + SAMP nel 14. §5 con le nuove decisioni, §6 AM1, §7 aggiornati. Aperte: **31** (Gruppo 1 = 0, Gruppo 2 = 24, Gruppo 3 = 7). Stati: bozza 16, non esiste 25, totale 41. |
| 2026-10-08 | Claude Code | **Scritti `18-core-calcolatrici.md` e `19-core-dati-planetari.md`** (stato `bozza`, da `non esiste`), secondo `TEMPLATE-modulo.md`: 18 = calcolatrici algebrica, unità, pixel, coordinate (tramite 10) e tempo (H4, sez. 5.7); 19 = dati planetari (H21, sez. 5.21/7.2/8.1). Decisioni aperte nei file: D18-1…D18-6, D19-1…D19-7, registrate in `decisioni-aperte.md` (smistamento proposto) → aperte **44** (Gruppo 1 = 2, Gruppo 2 = 33, Gruppo 3 = 9). "Usato da" aggiornato in `10`, `11`, `12`, `13`, `14`, `16`, `17`. §2, §4, §6, §7 aggiornati. Stati: bozza 18, non esiste 23, totale 41. Nessun modulo del gruppo analisi scritto. |
| 2026-10-09 | Claude Code | **Decisioni del proprietario del 2026-10-08 applicate:** smistamento delle 13 decisioni di 18/19 confermato; D19-3 (campo `body` in `12`, `13`, `14`, `16`: §6, §9, §10 e registri), D19-2 (PDS nel 19, PDS4 obbligatorio; resta D19-2b), D19-4 (errore di default, forzabile con opzione esplicita; nel 16 anche per operazioni tra MOC) in `19`; DC7 confermata in `02` e funzione `convert_pixel_convention` con test T8–T11 in `10`; `CLAUDE.md` aggiornato (nucleo 10–19, nota su `AGENTS.md`, regole su pixel e corpo). §2, §5, §6, §7 aggiornati. Aperte **42** (Gruppo 1 = 0, Gruppo 2 = 33, Gruppo 3 = 9). Stati invariati: bozza 18, non esiste 23, totale 41. |
| 2026-10-09 | Claude Code | **Checklist del livello 1 applicata (decisioni del proprietario):** 30 raccomandazioni scritte nei file di origine (`02`, `03`, `10`–`19`), con le verifiche come vincoli prima del codice; A2/A6/A9 con orientamento, bloccanti solo per `60`/`40` (§5, §6, `01`); D19-3 esteso al `15` (regola, errori, test T7–T8); nuove A10 e D10-6 (Gruppo 3); `CLAUDE.md`: fase codice per livello. Aperte **14** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 11). **Approvazione non eseguita:** nessuna decisione dei Gruppi 1 e 2 blocca 01, 02, 03 e 10–19, ma i moduli 11–17 non descrivono ancora le funzioni assegnate loro dalla lettura AP5 (H22, H23, H24, H26, H27, E3, F1); si attende l'indicazione del proprietario. Stati invariati: bozza 18, non esiste 23, totale 41. |
| 2026-10-09 | Claude Code | **Approvati 01, 02, 03, 10, 18, 19** (decisione del proprietario). **Moduli 11–17 completati** con gli esiti di AP5 (§3, §6, §7, §10, §12) e 10 con H25; verifica di copertura di `03` sui moduli 10–19 senza altre lacune. **Approvati 12, 16, 17**; **11, 13, 14, 15 restano in bozza** per le nuove decisioni del Gruppo 2 D11-6, D13-7, D14-7, D14-8, D15-5 (nuova D13-8 nel Gruppo 3). §2, §4, §5, §6, §7 aggiornati. Aperte **20** (Gruppo 1 = 0, Gruppo 2 = 8, Gruppo 3 = 12). Stati: approvato 9, bozza 9, non esiste 23, totale 41. |
| 2026-10-09 | Claude Code | **Livello 1 interamente approvato:** applicate D11-6 (`Pillow`), D13-7 e D14-8 (`defusedxml`), D14-7 (nessun plugin; parte "plugin" di H14 nel 24, anche in `03`), D15-5 (Mahalanobis, soglia in sigma; nuova D15-6 Gruppo 3) e il framework `pytest` (`01`, `02` §8); approvati 11, 13, 14, 15. §2, §4, §5, §6, §7 aggiornati. Aperte **16** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 13). Stati: approvato 13, bozza 5, non esiste 23, totale 41. |
| 2026-10-09 | Claude Code | **FASE: CODICE – livello 1** dichiarata dal proprietario. Creata la base del progetto: `pyproject.toml` (Python 3.12, `uv`, build `hatchling`, `pytest` con marcatore `network` escluso di default), `uv.lock`, `.python-version`, `src/astrotwo/` con `core`, `analysis`, `ai`, `ui`, `advanced`, `tests/` specchiato; dipendenze del modulo 10 (`astropy` 8.0.1, `astroquery` 0.4.11, `numpy` 2.5.3, `scipy` 1.18.1 per `fit_wcs_from_points`) e `pytest` 9.1.1. **Verifiche del modulo 10:** `NCP` supportata (tradotta in `SIN` + `PV2_2`), DSS1 supportata (WCSLIB 8.6, riferimento STScI entro 0.010″), licenze permissive con WCSLIB LGPL-3 da considerare in `60`; **`fit_wcs_from_points` non copre `SIN`, `AIT`, `ZEA`, `CAR`, `NCP`, `ZPN`** → nuova D10-7; lacune di §7 → nuova D10-8 (Gruppo 3, bloccanti ora). `coordinates_wcs.py` non scritto: ci si ferma per la decisione del proprietario. §2, §6, §7 aggiornati; `10`, `decisioni-aperte.md`, `INDICE.md`, `riassunto.md`, `CLAUDE.md` allineati. Aperte **18** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 15). Stati invariati: approvato 13, bozza 5, non esiste 23, totale 41. |
| 2026-10-09 | Claude Code | **Decisioni del proprietario D10-7 e D10-8 applicate** (con autorizzazione a modificare 10, 11, 17, 18, che restano `approvato`): calibrazione per associazione di stelle con partenza `TAN` e tre controlli (coerenza con l'RMS della `TAN`, precisazione del proprietario); `compute_grid_lines`, `choose_projection` (nuova D10-9); centroide `star_centroid` nell'11 (nuova D11-7); offset e calcolo inverso nel 17; calcolatrice del 18 su 10 e 17. **AM1 accettata: creato `04-cache.md`** (bozza; CA1–CA4); collegati per ora solo 10 e 11 (12, 13, 14, 16 all'approvazione di 04, scelta del proprietario). Vincolo LGPL-3 di WCSLIB registrato per il 60. **Modulo 10 scritto** (`src/astrotwo/core/coordinates_wcs.py`, tutto il §7 tranne `resolve_name`) con test T1–T22: 60 superati, 1 saltato (T5), 2 di rete superati. §2, §4, §5, §6, §7 aggiornati. Aperte **22** (Gruppo 1 = 0, Gruppo 2 = 7, Gruppo 3 = 15). Stati: approvato 13, bozza 6, non esiste 23, totale 42. |
| 2026-10-09 | Claude Code | **Decisioni del proprietario:** confermate le interpretazioni 1, 3, 4, 5 del modulo 10; nuova `choose_grid_spacing` (passo automatico come Aladin, test T23); **D11-7 decisa** (mediana con sigma clipping in una corona) e `star_centroid` scritto con test T16–T19; D10-9 resta aperta (si decide con il 41); **CA1–CA4 decise e `04-cache.md` approvato**; 11, 12, 13, 14, 16 collegati alla cache comune senza cache proprie (restano approvati, modifica nel registro). Test: 80 superati, 1 saltato (T5), 0 falliti; rete: 2 superati. Codice della cache non scritto (in attesa della scelta del prossimo passo). §2, §4, §5, §6, §7 aggiornati. Aperte **17** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 14). Stati: approvato 14, bozza 5, non esiste 23, totale 42. |
| 2026-10-09 | Claude Code | **Decisioni del proprietario:** nomi dei file Python in inglese con tabella in `02` §3 (04 e 10–19); passo automatico della griglia confermato (da verificare con AP1); centroide confermato, nuova **D11-8** (default dei raggi della corona, da fissare con 20 e 41). Aperte **18** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 15). Stati invariati. |
| 2026-10-09 | Claude Code | **Decisioni del proprietario:** nomi dei file Python in inglese (tabella in `02` §3); griglia automatica confermata (da verificare con AP1); centroide confermato e nuova D11-8; precisazioni della cache (limite sui dati, 5 × 10⁹ byte) e di `resolve_name` (prima la cache). **Codice:** `src/astrotwo/core/cache.py` (test T1–T8 di `04`) e `resolve_name` nel modulo 10 (T5 simulato + di rete); dipendenze dichiarate `requests` e `pyvo`; `tests/conftest.py` con home temporanea per tutti i test. Test: 103 superati di default, 106 con la rete, 0 saltati, 0 falliti. Primo commit `e029808`; secondo commit con questo lavoro. Aperte **18** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 15). Stati invariati: approvato 14, bozza 5, non esiste 23, totale 42. |
| 2026-10-10 | Claude Code | Modulo 10: verificato che `conf.timeout` di astroquery non applica i timeout HTTP di `04`; il campo interno `_session` resta isolato in `_simbad_with_timeouts` (registro del 10). Test: 106 superati con la rete. |
| 2026-10-10 | Claude Code | **Decisioni del proprietario:** regola d'oro n. 8 in `CLAUDE.md` (AstroTwo scritto da zero); divisione dell'11 in 7 parti e decisioni collegate applicate nell'11 (D11-5 corretta, D11-9); **A11 — licenza di AstroTwo** aperta (Gruppo 2, blocca il 60) in `01`; A10 decisa per le immagini. Controllo dei file approvati per contenuti presi da Aladin: elenco consegnato al proprietario, nessuna correzione. Aperte **19** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 15). Stati invariati. |
| 2026-10-10 | Claude Code | **Modulo 11 scritto in 7 parti** (P1 lettura FITS/HDU, P2 JPEG/PNG/GIF e FITS RGB, P3 rete e cache, P4 visualizzazione, P5 taglio/operazioni/contorni/salvataggio, P6 immagini grandi, P7 ricampionamento/RGB/mosaico), un commit per parte, con le verifiche prima di ciascuna (HCOMPRESS, Pillow, documentazione pubblica della calibrazione, matplotlib e palette, manuale sez. 5.18 per la normalizzazione, contourpy, `memmap`/`section` di astropy, reproject) e le precisazioni del proprietario registrate nell'11. Modulo 10: campo interno di astroquery isolato in `_simbad_with_timeouts`. Test: 197 superati di default, 200 con la rete. `04`, 10 e 11 completi. Aperte **19** (invariate). Stati invariati: approvato 14, bozza 5, non esiste 23, totale 42. |
| 2026-10-10 | Claude Code | **Decisioni del proprietario applicate** (autorizzazione a modificare 11, 12, 13, 14, 15, 18, 19, che restano `approvato`): 11 — scelte di P1–P7 confermate (D11-10), avviso `HHH_WCS_DIFFERS`, tetto di memoria A10 con `MEMORY_LIMIT_EXCEEDED` (codice e test T32–T33), §11 spostato nel 32 (elenco nella riga del 32, §4); regola d'oro n. 8 — D12-1 senza Hipsgen, D12-3, D13-1, D13-3, D14-3, D14-4, raggio obbligatorio nel 15, D15-1, D15-4, D15-5, D18-2 (solo FITS e VOUnit), T16 del 18, D19-5. Nessun PDF del manuale di Aladin nella cartella né nella storia git (punto C: nulla da fare). Test: 200 di default, 203 con la rete. Prossimo modulo: 13. Aperte invariate **19**. |
| 2026-10-10 | Claude Code | **Decisioni del proprietario applicate** (autorizzazione a modificare 01, 10, 11, 13, 17 e `CLAUDE.md`): D11-11 (limite delle operazioni 4 GB separato da A10, `set_display` a blocchi in `float32`, test T34); `01` §7 (strumenti IA nel 32); regola d'oro n. 8 nel 10 e nel 17 e distinzione validazione/copia in `CLAUDE.md`; `*.pdf` nel `.gitignore`. **Modulo 13:** specifica aggiornata (D13-4, D13-8, D13-9; nuove aperte D13-10…D13-14); **P1 scritta e testata**; P2 ferma su D13-14 (esempio ASTRORES del CDS incoerente con la DTD). Test: 213 di default, 216 con la rete. Aperte **22**. |
| 2026-10-10 | Claude Code | **Modulo 13, P2–P5** (decisioni D13-10…D13-14 applicate in 10, 13, 17): P2 lettore ASTRORES (`defusedxml`, `parse_sexagesimal` nuova nel 10); P3 `search` e regole di disegno; P4 senza `calculated_column` (nuova D13-15: numeri accanto a colonne con unità); P5 senza `time_filter` (nuova D13-16); nel 10 `proper_motion_only` (T24) e `parse_sexagesimal` (T25). Verifica: nessuna tabella ufficiale IVOA UCD1 → UCD1+ → nuova D13-14b. Un commit per parte. Test: 247 di default, 251 con la rete. Aperte **20**. |
| 2026-10-10 | Claude Code | **Modulo 13 completo fino a P5:** D13-14b, D13-15, D13-16 applicate (traduzione UCD1, `calculated_column`, `time_filter`); P6 dopo il 14. Test: 253 di default, 257 con la rete. Aperte **17**. Prossimo: proposta di divisione del modulo 14. |
| 2026-10-10 | Claude Code | **Modulo 14 scritto (P1–P7) e P6 del 13** (decisioni del proprietario D14-5 e D14-9 applicate in 14, 13 e nella riga H23 di `03`; strumenti IA del 14 annotati nella riga del 32): VOTable ed esportazione, rete con registro e cache, cone search e TAP, elenco dei server e registro VO, DataLink, SIA/SIA2, IDHA (solo errore), SSA, puntatore Simbad, fotometria VizieR, SAMP; nel 13 `load_table`, `load_catalog`, gruppo fisso, `datalink_column`, più correzioni (commenti `#` nei testi delimitati, VOTable senza `nrows`, `utype` e `TUCDn`). Fermi: D14-10, D14-11, D14-12, D13-17, D13-18 (nuove, Gruppo 3). Test: 293 di default, 301 con la rete. Aperte **21**. |
| 2026-10-11 | Claude Code | **Pezzi fermi di 13 e 14 chiusi** (decisioni del proprietario D14-10, D14-11, D14-12, D13-17, D13-18; autorizzazione a modificare 11, 13, 14, che restano `approvato`): esportazione ECSV e lettura nel 13; `sia_calibration` e parametro `calibration` di `load_image`; magnitudini SIMBAD; `LINK` ASTRORES; albero delle collezioni dal MocServer; registro VO di default in HTTPS; FITS Standard 4.0; `load_catalog` con `allow_partial`. Nuove aperte D13-19 e D13-14c. Test: 299 di default, 308 con la rete. Aperte **18**. Prossimo: modulo 15 (proposta in attesa). |
| 2026-10-11 | Claude Code | **Modulo 15 scritto (P1–P5) e decisioni del proprietario applicate in 13, 14, 15** (restano `approvato`): D13-19 regione di `load_catalog`; termini `refframe` nel `COOSYS`; ECSV con il sistema delle posizioni; albero in ordine naturale; ripetizioni dei test di rete; crossmatch locale, tabella unita, per campo, ellissi (D15-6 decisa), CDS XMatch (`cds_xmatch` nel 14). Nuove aperte D13-20, D15-8, D15-9. Test: 325 di default, 337 con la rete. Aperte **19**. Prossimo: modulo 16 (proposta in attesa). |
| 2026-10-11 | Claude Code | **Regola dei commit e modulo 16** (decisioni del proprietario del 2026-10-11; 02, 13, 15, 16 modificati e restano `approvato`): `02` §8 punti 8–9 (ripetizioni dei test di rete, commit solo se i test di default passano, `scripts/commit_checked.py` con `--no-network` per le parti intermedie); D13-20, D15-8, D15-9 decise e applicate; **modulo 16 scritto in 5 parti** con `mocpy` 0.20.0 e `astropy-healpix` 2.0.1 (`healpy` escluso); nuove aperte D16-6 (versione 2.1 del formato MOC) e D16-7 (complemento degli ST-MOC). Scelte minori della sessione precedente (moduli 13–15) confermate dal proprietario. Test 359 di default, 373 con la rete. Aperte 18. Prossimo: modulo 12 (proposta di divisione in attesa del proprietario). |
| 2026-10-12 | Claude Code | **Decisioni del proprietario del 2026-10-12 e modulo 12** (12, 14, 16 modificati e restano `approvato`): 14 §12 rimanda a `02` §8; 16 — D16-6 (verifica sul sito IVOA: nessuna 2.1, resta rifiutata), D16-7 (complemento ST-MOC con `mocpy`; normalizzazione dei risultati ST), corpo misto e MOC planetari in FITS con `A2BODY`, scelte minori confermate; **modulo 12 scritto in 5 parti** (`hips.py`; verifiche dello standard HiPS 1.0 e del WD 2.0 per `hips_body`, DSS2 a colori `CDS/P/DSS2/color`, `cone_search_lonlat`, disposizione dei pixel nel tile con due verifiche indipendenti, funzioni HiPS di `reproject`); H10 SkyView rinviato (URL SIA non documentato da NASA); A10 decisa per gli HiPS; nuove aperte D12-6, D12-7, D12-8; MocServer letto in ISO-8859-1 come dichiarato (correzione anche in 14 e 16). Test 405 di default, 422 con la rete. Aperte 18. Prossimo: modulo 17 (proposta di divisione in attesa del proprietario). |
| 2026-10-12 | Claude Code | **Decisioni del proprietario del 2026-10-12 e modulo 17** (01, 12, 14, 16, 17 modificati e restano `approvato`): codifica del MocServer scritta in 14 e 16; A10 per gli HiPS nella riga di `01`; 12 — H10 rinviato con il motivo, D12-6/D12-7/D12-8 decise, `reproject` e disposizione dei pixel approvati, scelte minori confermate (anche del 16); 17 — divisione in 4 parti, D17-5 decisa, **P1, P2, P4 scritte** (`measures.py`, T1–T6, T8–T15), **P3 ferma** con la nuova D17-7 (proposta `spherical-geometry`, BSD-3-Clause). §2, §5, §6, §7 aggiornati; aperte 15 (Gruppo 2 = 4, Gruppo 3 = 11); test 427 di default, 444 con la rete. |
| 2026-10-13 | Claude Code | **Decisioni del proprietario del 2026-10-12, modulo 17 completato e modulo 18 scritto** (17 e 18 modificati e restano `approvato`): 17 — scelte minori B, **P3 scritta** con D17-7 (forme sferiche, `spherical-geometry` 1.4.0 nuova dipendenza, licenza verificata; T7, T16–T19), nuova D17-8 (`distance_to`); 18 — divisione in 5 parti, D18-5 e D18-6 decise, **P1–P5 scritte** (`calculators.py`, T1–T18), nuova D18-7 (sessagesimali in `skydist`). §2, §5, §6, §7 aggiornati; aperte 14 (Gruppo 2 = 4, Gruppo 3 = 10); test 457 di default, 474 con la rete. Prossimo: modulo 19 (proposta di divisione in attesa del proprietario). |
| 2026-10-13 | Claude Code | **Decisioni del proprietario del 2026-10-13: pezzi fermi di 17 e 18, licenze, modulo 19** (01, 11, 12, 17, 18, 19 modificati e restano `approvato`): D17-8 e D18-7 decise e scritte; `THIRD_PARTY_LICENSES` creato (con script e test), registrato nel 01 e annotato per A11 e il 60; `read_raw_pixel` nell'11; UT1 con le tabelle IERS incluse (`IERS_RANGE`, `update_iers_table`); scelte minori di 17 e 18 confermate; **modulo 19 scritto in P0–P4** (spiceypy, pds4-tools, kernel NAIF `pck00011.tpc`; tabella dei nomi D12-6 applicata al 12). Nuove aperte D17-9, D19-8, D19-9 (Gruppo 3). Test 485 di default, 505 con la rete. Aperte 15. Riepilogo invariato: approvato 14, bozza 5, non esiste 23, totale 42. |
| 2026-10-13 | Claude Code | **Chiusura del livello 1 (decisioni del proprietario del 2026-10-13)** (04, 17, 19 modificati e restano `approvato`): D17-9 decisa e scritta (`distance_to` per freccia, tracciato aperto ed ellisse, testo escluso; T21; il test ha trovato che lo zero a spigolo della distanza tra bordi incrociati non raggiungeva la precisione dichiarata: incroci riconosciuti con la funzione liscia dei fuochi); D19-9 decisa e scritta (PDS4 da URL, T8 esteso); D19-8 rimandata (PDS3 non ancora supportato); scelte minori di 18 e 19 confermate; 04 con 18 e 19 tra gli utenti della cache; licenza di `pims` dal sorgente ufficiale su PyPI in `THIRD_PARTY_LICENSES` (script aggiornato). Test 491 di default. Aperte 13 (Gruppo 3 = 9). |
| 2026-10-13 | Claude Code | **Demo delle Pleiadi (primo test con dati veri)**: `examples/demo_pleiadi.py`, `examples/README.md`, test di rete `tests/test_demo_pleiadi.py`, `examples/output/` in `.gitignore`; matplotlib era già una dipendenza (licenza già in `THIRD_PARTY_LICENSES`). Difetto trovato: testo di `filter_by_moc` del 16 ("dentrol"), test e correzione, registro del 16. Valori principali in §2. |
| 2026-10-13 | Claude Code | **Demo delle Pleiadi, epoca di visualizzazione (D10-2)** (nessuna specifica cambiata): le stelle Gaia (J2016.0) si disegnano propagate all'epoca dell'immagine DSS (1989-12-17, da `MJD-OBS`) con `propagate` del 13; report con epoca usata e spostamento medio (0,88″, massimo 2,17″) da `skydist` in `calculated_column` e `column_statistics`; misure all'epoca dei dati, dichiarata. README e test di rete aggiornati. |
| 2026-10-14 | Claude Code | **`display_positions` nel 13** (decisione del proprietario del 2026-10-14, autorizzazione esplicita; 13 resta `approvato`): §3, §7, §10, T34; codice in `catalogs.py`. Demo delle Pleiadi con `display_positions` per stelle e frecce (frecce dalle posizioni all'epoca di visualizzazione; Alcyone e Atlas a J2000 SIMBAD, dichiarato); report invariato nei valori. **MOC da immagine con i blocchi non applicato:** la regola decisa perde celle sul bordo (DSS 4,1104 contro 4,1399 deg²; 15 immagini casuali su 30) → **D16-8 aperta** nel 16 §13 e nel Gruppo 3, con raccomandazione e misure. Test 492 di default. Aperte 14. |
| 2026-10-14 | Claude Code | **D16-8 decisa e applicata** (decisione del proprietario del 2026-10-14; 16 resta `approvato`): §3 (blocchi più angoli dei pixel lungo il contorno della regione dei blocchi validi, crescita ≤ b − 1 pixel, dimensione del blocco dichiarata), §12 T10, §13; codice in `moc.py`; test su 300 maschere casuali e test di rete sulla DSS (MOC identico, 4,1399 deg²). Tempi a cache calda: `moc_from_image` 10,3 → 0,21–0,27 s, demo 18,5–19,5 → 8,5–9,5 s; valori del report invariati. **D14-13 aperta** nel 14 (Gruppo 3; 14 resta `approvato`). Test 494 di default. Aperte 14. |
| 2026-10-15 | Claude Code | **Specifiche della prima versione dell'interfaccia** (proposta della fase 1 approvata dal proprietario il 2026-10-15; nessun codice): **AM1 accettata, creato `05-comandi-sessione.md`** (bozza); **scritti `40`, `41`, `42`** (bozza, 14 sezioni); decise A9, D10-9, D11-8, raggio del puntatore Simbad; modificati i file approvati 01, 02, 03, 10, 11, 12, 13, 17, 18 (restano `approvato`) e `CLAUDE.md` (formula "FASE: CODICE – interfaccia v1"); nuove aperte D05-1, D05-2, D05-3, D40-1, D40-2, D41-1…D41-4. §2, §4, §5, §6, §7 aggiornati. Aperte **20** (Gruppo 1 = 0, Gruppo 2 = 9, Gruppo 3 = 11). Stati: approvato 14, bozza 9, non esiste 20, totale 43. |
| 2026-10-15 | Claude Code | **Decisioni del proprietario sulle specifiche dell'interfaccia** (autorizzazione a modificare 10 e 11; nessun codice): decise D05-1, D05-2, D40-1, D41-1…D41-4; D05-3 e D40-2 rimandate; nuova D40-3; scelte minori di 05, 40, 41, 42 confermate; nuove `format_coordinates` (10) e `suggest_display_limits` (11); linee guida visive nel `40` §3.11; mockup `mdfiles/mockup/finestra-principale.html` e `finestra-principale-notte.html`; PySide6/Qt (LGPL-3) registrata per A11 e per il 60. §2, §5, §6, §7 aggiornati. Aperte **14** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 11). Stati invariati: approvato 14, bozza 9, non esiste 20, totale 43. |
| 2026-10-16 | Claude Code | **Proposta della fase 1 sull'IA nella v1 approvata dal proprietario il 2026-10-16** (nessun codice applicativo): scritti in `bozza` 30, 31, 32, 34, 35, 44; modificati 05 (`requested_by`, `confirm`, cinque comandi di sola lettura, blocco `conversations`), 40 (pannello 44, colonna "chi", preferenze dell'assistente), 41 (A7 nella v1, §3.18), 42 (cifre della tabella) e, con autorizzazione esplicita, gli approvati 01 (A5, §7), 02 (tabella specifica ↔ codice, test del livello 3), 03 (E2, A7), 10 (`compass_and_scale_bar`) e `CLAUDE.md` (formula di fase estesa a 30, 31, 32, 34, 35, 44); **sicurezza** contro le istruzioni nei testi esterni nel 32, 34, 35. **Regola dei commit:** HTTP 429/502/503/504 = connessione (`02` §8; `tests/conftest.py` e `scripts/commit_checked.py` con i test; commit `83f15df` insieme ai mockup, bloccati prima dal 503 di TAP VizieR). §2, §4, §5, §7 aggiornati. Nessuna nuova decisione aperta (solo scelte minori nei §13); aperte 14. |
| 2026-10-16 | Claude Code | **Decisioni del proprietario del 2026-10-16:** 32 scelte minori confermate (la #6 modificata: servizio del Portachiavi `dev.pages.astrotwo.ai`; identificativo del progetto e bundle identifier `dev.pages.astrotwo` in `01` §6); **approvati 05, 30, 31, 32, 34, 35, 40, 41, 42, 44** e le modifiche al 10; **dichiarata "FASE: CODICE – interfaccia v1"** (`CLAUDE.md`). §2, §4, §5 aggiornati. |
| 2026-10-16 | Claude Code | **D04 decisa dal proprietario** (cache da più thread e processi: orfani solo oltre 10 minuti, pulizia una volta per processo); 04 modificato (resta `approvato`) con codice e test T9–T11; verifica del 05 §3.2 (T17) chiusa. |
| 2026-10-16 | Claude Code | **Verifiche prima del codice della v1:** licenze di `anthropic` (MIT), `openai` (Apache-2.0), `httpx2` (BSD-3), `keyring` (MIT), PySide6 (`pyside6-essentials`, LGPL-3.0, testi dal sorgente ufficiale), pytest-qt (MIT) in `THIRD_PARTY_LICENSES`; `keyring` forzato sul Portachiavi di login e funzionante in un'app PyInstaller; OpenGL di PySide6 sufficiente; Ollama con chiamata di strumenti in streaming verificato; LM Studio rimandato (non installato). |
| 2026-10-16 | Claude Code | **Allineamento del livello 1 alla v1:** codice e test di 10 (`make_view_wcs`, `format_coordinates`, `compass_and_scale_bar`, `choose_projection` con default 30°), 11 (`suggest_display_limits`, corona di default), 12 (P6, con la verifica di `reproject` e i tempi misurati); adattatore del 18 fermo sulla nuova **D05-4** (Gruppo 1). Aperte 15. §7 con la proposta di divisione del codice della v1 in attesa del proprietario. |
| 2026-10-17 | Claude Code | **Decisioni del proprietario del 2026-10-17:** (A) `httpx2` accettato dopo la verifica dell'origine (01, 30); (B) profili predefiniti dei provider IA (30 §3.1.1, 31, 44 §3.6) con indirizzi dalla documentazione ufficiale; **D05-4 decisa** (tipo `record`, forme JSON nel 05 §3.1, parametri dei `calc.*` nel 18); adattatore `run_command` del 18 scritto e testato (T18 nel formato del 05); note superate "codice da scrivere" tolte da 10, 11, 12. Aperte **14**. §5, §6, §7 aggiornati. |
| 2026-10-17 | Claude Code | **Parte 1 del codice della v1: modulo 05** (`src/astrotwo/core/commands.py`, `tests/core/test_commands.py`, 26 test): registro con i 39 comandi di §7 del 05, validazione con le forme JSON di D05-4 (più il tipo `time`), spazio di lavoro immutabile, cronologia, sessione (salva, apri, riesecuzione con stop e avvisi), schema JSON per il 32; scelte minori della parte 1 nel 05 §13 (da confermare). |
| 2026-10-17 | Claude Code | **Parte 2 del codice della v1: moduli 31 e 30** (`ai/keychain_keys.py`, `ai/provider_adapter.py` con i dieci profili predefiniti; test con Portachiavi e provider simulati, 34 test; marcatore `keychain`). Precisazioni del 30 dalle fonti e dal codice degli SDK (indirizzo di Anthropic, `max_completion_tokens` per OpenAI, variabili d'ambiente neutralizzate); scelte minori della parte 2 nel 30 §13, da confermare. |
| 2026-10-17 | Claude Code | **Correzione del test T8 del 31** (solo test, nessuna funzione nuova): la finestra di macOS "Impossibile trovare un portachiavi" veniva dalla cartella home temporanea che `tests/conftest.py` dà a ogni test (`HOME` cambiata: macOS cerca il Portachiavi di login in `$HOME/Library/Keychains` e non lo trova). T8 ora usa la vera home dell'utente letta dal sistema (`pwd`). Codice del 31 invariato (servizio `dev.pages.astrotwo.ai`, nessun portachiavi impostato esplicitamente). T8 da rieseguire a mano dal proprietario. |
| 2026-10-17 | Claude Code | **Parte 3 del codice della v1: modulo 40** (`src/astrotwo/ui/main_window.py`, traduzione `ui/i18n/astrotwo_it.ts`/`.qm`, `tests/ui/test_main_window.py` con T1–T14, T12 `perf`; voce `astrotwo` in `[project.scripts]`, marcatori `perf` e `gl` esclusi di default in `pyproject.toml`). Decisioni del proprietario: D05-2 precisata (impronta sul contenuto restituito dal modulo; 05 §3.1 e §13), scelte minori del 05 confermate (tipo `time`, parametro `window`); VizieR TAP: endpoint invariato, 503 = guasto temporaneo del CDS, nessuna modifica. Verifiche del 40 §13 fatte (colorScheme, cifre tabulari); icone ancora da verificare. §2, §4, §5, §7 aggiornati. Aperte 14 invariate. Stati invariati: approvato 24, bozza 5, non esiste 14, totale 43. |
| 2026-10-17 | Claude Code | **Parte 3b del codice della v1: correzioni dell'aspetto del 40** dopo la prova del proprietario (nessuna funzione nuova, comandi invariati): foglio di stile dai mockup, icone Lucide (`src/astrotwo/ui/icons/`, licenza ISC + MIT di Feather verificata e in `THIRD_PARTY_LICENSES`, script delle licenze aggiornato), intestazioni dei pannelli, stati vuoti dei segnaposto, pulsanti della barra per azioni dei menu (anche Night mode); traduzioni italiane aggiornate; test T13 esteso e nuovo test delle linee guida visive. **Aperta D40-4** (scorciatoia della modalità notte, Gruppo 3). §2, §6, §7 aggiornati. Aperte 15 (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 12). Stati invariati: approvato 24, bozza 5, non esiste 14, totale 43. |
| 2026-10-17 | Claude Code | **Parte 4, sprint 4a del codice della v1 (41, prima fetta):** `ui/sky_viewer.py` e `ui/sky_renderer_gl.py` (sfondo HiPS a colori, zoom e spostamento come comandi del 05, vista iniziale a cielo intero, scritta del survey nella barra); scelte del proprietario (vista iniziale, passo e limiti dello zoom, cifre del campo, `field_of_view` nel risultato dei comandi di vista del 05); **D40-4 decisa (⌃⌘N)**; barra di stato ad altezza fissa; test `tests/ui/test_sky_viewer.py` (e `gl`). §2, §6, §7 aggiornati. Aperte 14 (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 11). Stati invariati: approvato 24, bozza 5, non esiste 14, totale 43. |
| 2026-10-17 | Claude Code | **Parte 4a-fix del codice della v1 (41, FASE: CODICE – interfaccia v1):** dopo la prova del proprietario (zoom e "Vai a" non funzionavano). Cause trovate con eventi Qt reali passati dalla finestra: (1) la rotella del mouse su macOS dà eventi con valori piccoli (non 120 per scatto): ora ogni evento vale almeno uno scatto; il pizzico è ora accettato; (2) uno spostamento o un ridimensionamento dei pannelli ancora da registrare, a fine gesto, rimetteva il centro in un altro punto dopo "Vai a" (e al primo avvio): ora una vista cambiata da altro azzera il gesto in sospeso e la finestra diversa è compensata; (3) l'errore di "Vai a" compare anche nella barra di stato. Nessun comando né spec cambiati; 3 test nuovi in `tests/ui/test_sky_viewer.py`. Aperta la domanda al proprietario su pulsanti + / − e ⌘+ / ⌘− (non nel 41). |
| 2026-10-17 | Claude Code | **Parte 4a-fix (seconda parte), decisioni del proprietario dello stesso giorno:** pulsanti **+** e **−** sul cielo e voci Zoom in/out del menu View (⌘+, ⌘=, ⌘−; ×2 e ÷2 come un gesto); dopo un "Vai a" riuscito con campo > 1,25° la vista va a circa 1° con un `view.set_zoom` registrato (`05` invariato). Specifiche aggiornate prima: `41` §3.4 e `40` (menu View, §3.4). Icone Lucide `plus` e `minus` (ISC), traduzioni italiane, 2 test nuovi. |
| 2026-10-17 | Claude Code | **Parte 4a-fix2:** la rotella di un mouse vero non zooma sul Mac del proprietario; aggiunto il log diagnostico `ASTROTWO_DEBUG_INPUT=1` (spento di default) in `sky_viewer.py`, descritto nel `41` §3.4. Causa **da verificare** con i dati reali; nessun file cambia stato. |
| 2026-10-17 | Claude Code | **Parte 4a-fix2 (correzione):** causa trovata con il log del proprietario: la rotella del mouse su macOS ha `pixelDelta` non nullo e il codice la trattava come trackpad (solo spostamento). Ora `NoScrollPhase` = rotella → zoom (1/6 di scatto per evento, 6 eventi per scatto misurati), fasi = trackpad → spostamento. Specifica `41` §3.4 aggiornata prima; test con i valori reali. Nessun file cambia stato. |
| 2026-10-17 | Claude Code | **A11 decisa dal proprietario: GPL-3.0-or-later**, titolare Guido Ratti 2026. Creati `LICENSE`, `NOTICE`, `CONTRIBUTING.md`; `pyproject.toml` (PEP 639); intestazioni SPDX in tutti i `.py` con test; `THIRD_PARTY_LICENSES` rigenerato; `01` §4.2/§6.1 (compatibilità, crediti dei dati con "da verificare" per Sesame, HiPS, MocServer, uso commerciale DSS, requisiti del `60`). Nessun cambiamento di comportamento. Aperte **13** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 11). Stati invariati. |
| 2026-10-18 | Claude Code | **Parte 4, sprint 4b del codice della v1 (41):** tile FITS a colori con `set_display` (`ui/sky_viewer.py`, `colorize`), limiti di colore scelti da `hips.set_survey` e registrati nel comando (`core/commands.py`: parametri `vmin`/`vmax`), coordinate e valore del pixel sotto il mouse nella barra di stato (`cursor.read` con `order` e sistema scelto, `format_coordinates` del 10; `ui/main_window.py`), traduzioni; test nuovi in `tests/ui/test_sky_viewer.py` e `tests/core/test_commands_hips_display.py` (T4 FITS, T8, T19). Decisioni del proprietario del 2026-10-18 in `05` e `41`. Corretto `test_visual_guidelines` (rete reale verso SIMBAD → `fake_simbad`). |
| 2026-10-19 | Claude Code | **Parte 4b-fix della v1 (41):** correzione di "Vai a" da una vista `TAN` verso un centro lontano (`_recompute_view` del 05 ricrea la base), ordine e risoluzione del valore del pixel in `cursor.read` e nella barra di stato, barra di stato che non ridimensiona il cielo, `pytest-timeout` come dipendenza di sviluppo (`pyproject.toml`, `uv.lock`, `THIRD_PARTY_LICENSES`, `tests/conftest.py`, `tests/test_timeout_config.py`); test nuovi. Scelte minori dell'sprint 4b confermate dal proprietario. |
| 2026-10-20 | Claude Code | **Parte 4b-fix2 della v1 (41):** barra di stato a due campi (coordinate; valore · ordine · risoluzione a larghezza fissa, mai tagliato), comando in corso a larghezza massima, test a 1280 e 900 px; 41 §3.11 e registro aggiornati, resta `approvato`. |
| 2026-10-20 | Claude Code | **Parte 4, sprint 4c della v1 (41):** griglia con etichette, nord/est e barra di scala disegnati; nuovo comando `view.set_overlays` nel `05` (decisione del proprietario del 2026-10-20), voci di menu nel `40`; `05`, `40`, `41` modificati nel registro, restano `approvato`; verificati i 4 avvisi `FROM_CACHE` di `hips.set_survey`. |
| 2026-10-20 | Claude Code | **Parte 4, sprint 4d della v1 (41):** immagine FITS locale come base della vista (inquadratura intera, colori di `set_display`, valore originale con unità, pixel FITS, frame ed epoca dall'intestazione), griglia di pixel con `WCS_INVALID` senza WCS valido; `view.set_overlays` nell'elenco del 32; avvisi doppi di `hips.set_survey` eliminati; nuova D41-5 (Gruppo 3, aperte 14); `05`, `32`, `41` modificati nel registro, restano `approvato`. |
| 2026-10-21 | Claude Code | **Parte 4, sprint 4e della v1 (41):** cataloghi disegnati come simboli sulla GPU, clic con `catalog.select` e scheda della sorgente sul cielo, avvisi di epoche diverse; stile iniziale nel comando di caricamento e scheda della sorgente in `catalog.select` (05); decisioni del proprietario del 2026-10-21 (scheda sul cielo, stile nel comando, Okabe e Ito + sei forme + 8 px, nome da UCD e posizione della tabella); D41-5 rinviata; epoca della barra in ISO 8601 con la scala (DC1); nuova D41-6. Test 704 di default e 3 `gl` (piattaforma `cocoa`). |
| 2026-10-21 | Claude Code | **Parte 4, sprint 4f della v1 (41):** MOC sulla GPU (riempimento e perimetro, ordine per eccesso dichiarato), pannello dei livelli (visibilità, opacità, ordine, rimozione come comandi del 05), sfondo HiPS sotto l'immagine FITS con composizione per opacità, finestra della forzatura per `BODY_MISMATCH`. Decisioni del proprietario del 2026-10-21: **D41-6 decisa** (13), stile dei MOC in `moc.open` (05), perimetro `HealpixGrid.boundary` (16), ordine dei controlli di `check_overlay` (19), MOC di un altro corpo forzato non disegnato; 05, 13, 16, 19, 41 modificati nel registro, restano `approvato`. Esempio `examples/moc_esempi.py`. Aperte 14. |
| 2026-10-21 | Claude Code | **Parte 5, sprint 5a della v1 (42):** pannello Tabella (`ui/catalog_panel.py`) con schede per catalogo, modello virtuale, valori di §3.2, ordinamento (`table.sort`), selezione sincronizzata (`catalog.select`), record (`record_view`), righe non disegnate marcate; test T1–T6 (T6 `perf`). Decisioni del proprietario del 2026-10-21: filtro `search` fuori dalla v1; testo di `PLANETARY_DATA_DISABLED` senza rinvio alle preferenze (19). Correzioni: `record_view` con colonne array (13), attesa instabile di T30 del 41 nei test. README dei dati di test di terze parti e sezione in `THIRD_PARTY_LICENSES`. 13, 19, 40, 42 modificati nel registro, restano `approvato`. Aperte 14. |
| 2026-10-22 | Claude Code | **Parte 5, sprint 5b della v1 (42):** `PositionColumnsDialog` e `ProperMotionColumnsDialog` (`ui/catalog_panel.py`), aperti dopo `catalog.open_file`/`catalog.load_region` e dal pulsante "Colonne…"; un solo `catalog.set_columns`; test T7 e correlati (`tests/ui/test_column_dialogs.py`), traduzioni italiane. Decisioni del proprietario del 2026-10-22: confermate le 8 scelte di presentazione del 42; dati di test di Gaia sostituiti da dati sintetici (`scripts/make_synthetic_catalog.py`, `tests/core/data/synthetic_vizier/`, file Gaia rimossi), README dei dati e `THIRD_PARTY_LICENSES` aggiornati (nessun dato di terze parti nei test). 42 modificato nel registro, resta `approvato`. Aperte 14. |
| 2026-10-22 | Claude Code | **Parte 6, sprint 6a della v1 (32):** `src/astrotwo/ai/tool_registry.py` (22 strumenti dell'elenco chiuso, schema ridotto da `export_schema`, validazione del 05, conferme, testi esterni marcati, risultati ridotti) e `tests/ai/test_tool_registry.py` (T1–T12), con `tests/ai/ai_workspace.py` (spazio di lavoro senza rete con un catalogo che contiene un'istruzione). Decisioni del proprietario del 2026-10-22: testi esterni con due elenchi chiusi per percorso (32 §3.6, nuovo T12); divisione della parte 6 in 6a/6b/6c; confermate le scelte minori dello sprint 5b (42 §13); Gaia DR3 citata come fonte dei sei valori della stella di Barnard nei test. 32 e 42 modificati nel registro, restano `approvato`. Aperte 14. |
| 2026-10-22 | Claude Code | **Parte 6, sprint 6b della v1 (34):** `src/astrotwo/ai/result_verification.py` (estrazione dei numeri, eccezioni chiuse, confronto alla precisione e con l'unità scritte, stati, riepilogo, controllo delle conferme, modalità rigorosa) e `tests/ai/test_result_verification.py` (T1–T14, T14 `perf` 20 ms; flusso con un finto provider che inventa un numero, segnalato). Decisioni del proprietario del 2026-10-22: T5 del 34 corretto (vince §3.5), fonte dei testi esterni una volta in testa in `catalog.rows` (32, codice e T7), scelte 1–3 del 32 confermate, limiti del 35 come da specifica; scelte del 42 §13 (a–g) già registrate come confermate. 32 e 34 modificati nel registro, restano `approvato`. Aperte 14. |
| 2026-10-22 | Claude Code | **Parte 6, sprint 6c della v1 (35):** `src/astrotwo/ai/chat_assistant.py` (assistente: regole R1–R9, ciclo degli strumenti uno alla volta nella coda del 40, conferme, limiti di 10 chiamate e 5 minuti, Stop, verifica del 34 con rigenerazione rigorosa, token e costo, disponibilità e consenso, blocco `conversations`), `AssistantQueueExecutor` nel 40; T1–T14 in `tests/ai/test_chat_assistant.py` e `tests/ui/test_assistant_queue.py`. Decisioni del proprietario sullo sprint 6b applicate (34: solo arrotondamento, scelte confermate; 32: scelte 4–6 confermate). `35`, `40`, `32`, `34` modificati nel registro, stato `approvato` invariato. Test 780 di default. |
| 2026-10-22 | Claude Code | **Parte 7, sprint 7a della v1 (44):** `src/astrotwo/ui/ai_panel.py` (`AiPanel`, `MessageView`, `CommandCard`, `ConfirmationCard`, `SentDataDialog`, `ConsentDialog`, `AssistantSettingsDialog`) nell'area a destra del 40, impostazioni `assistant/…` con `prefs.set`, testo delle conversazioni nel salvataggio, uscita con risposta in corso, 8 icone Lucide, traduzione italiana; `tests/ui/test_ai_panel.py` (T1–T4, T6–T13, T15 e altri; Portachiavi simulato per tutte le finestre dei test in `tests/conftest.py`). **Decisioni del proprietario del 2026-10-22:** 12 scelte minori del 35 confermate; ultima richiesta dopo il limite con gli strumenti e `tool_choice = none` (`TurnOptions.tool_choice` del 30, T16; T4 del 35 con entrambi i formati). `30`, `35`, `40`, `44` modificati nel registro, stato `approvato` invariato. Test: 799 di default. |
| 2026-10-23 | Claude Code | **Parte 7, sprint 7b della v1 (44):** in `ui/ai_panel.py` evidenziazione di ogni numero secondo lo stato del 34 (segni invisibili prima della conversione del Markdown, numeri negli indirizzi cercati dopo), suggerimento con valore pieno, `#n` e funzioni del modulo, copia col clic destro, colori della modalità notte; esiti di Aggiorna e "Prova il modello" su un oggetto dei segnali figlio della finestra (prima il secondo esito si perdeva); T5, T14 e test di Aggiorna, "Prova il modello", errori del provider, `AI_CONTEXT_TOO_LONG`, conferma con il pannello chiuso e uscita in `tests/ui/test_ai_panel.py`; traduzioni italiane. **Prova reale del proprietario:** causa di `NO_COORD_COLUMNS` = identificativo che non è una tabella (verificato sul servizio reale di VizieR); `load_catalog` con regione dà ora `CATALOG_UNKNOWN` (13, T33 esteso con la struttura di `TAP_SCHEMA` di Gaia DR3 senza dati di terzi); `TOOL_NOT_EXPOSED` con `valid_tools` (32, T4; anche nel 35). **Decisione del proprietario del 2026-10-23:** scelte minori dello sprint 7a confermate. Aperte D32-1 e D13-21 (16 aperte). `13`, `32`, `44` modificati nel registro, stato `approvato` invariato. Test 808 di default. |
| 2026-10-23 | Claude Code | **Parte 7, sprint 7c della v1 (decisioni e stabilità dei test).** Decisioni del proprietario: D32-1 (c) identificativi del gruppo fisso nella descrizione di `catalog` (05 §7, `commands.py`, 32 §3.4) e (b) `CATALOG_UNKNOWN` con le tabelle che cominciano con l'identificativo (13 §7, `catalogs.py`, risposta registrata di VizieR per `I/355`, T33); D13-21 (a) colonne candidate nel messaggio di `NO_COORD_COLUMNS`; (a) di D32-1 rinviata a dopo la v1 come nuova D32-2; 5 scelte minori dello sprint 7b del 44 confermate. Test instabili (T1, T2 del 42, T30 del 41): attese su condizioni (`wait_settled`, `wait_command`) invece di `wait_idle` e `history[-1]`; causa comune descritta in §2. Aperte 15 (Gruppo 3 = 13). Stati invariati: approvato 24, bozza 5, non esiste 14, totale 43. |
| 2026-10-23 | Claude Code | **Lint con ruff** (decisione del proprietario del 2026-10-23): ruff 0.17.2 (MIT) tra le dipendenze di sviluppo, `THIRD_PARTY_LICENSES` rigenerato; configurazione in `pyproject.toml` con solo errori veri (regole E e F, senza lunghezza della riga né ordine degli import). Corretti 12 errori veri senza cambiare il comportamento (import inutilizzati, una variabile inutilizzata, una f-string vuota, `field` ridefinito da una variabile di ciclo in `hips.py`). **D32-2 resta aperta** come promemoria (comando di ricerca nell'elenco dei cataloghi, dopo la v1). |
| 2026-10-23 | Claude Code | **Parte 4, sprint 4g della v1 (41):** `measure.distance` esteso con la forma cielo (05, 32), `ui/sky_tools.py` con `DistanceTool`, `SimbadPointerTool`, `MeasureOverlay` e barra delle opzioni, collegamento in `sky_viewer.py` e `main_window.py` (`ui.set_tool`, preferenze `tools/…`), 12 testi tradotti, T36 e T37; 05, 32, 40, 41 modificati nel registro, stato `approvato` invariato. Aperte 15 invariate. Stati invariati: approvato 24, bozza 5, non esiste 14, totale 43. |
| 2026-10-24 | Claude Code | **Parte 4, sprint 4h della v1 (41, ultimo):** specifica e codice di `view.export_png` (`ui/export_view.py`, collegamento nella finestra, `render_offscreen` nel renderer, `05` §7 e §10), cambio di base in un passo (`sky_viewer.py`), `tests/ui/test_export_png.py`, `tests/ui/test_base_switch.py`, `tests/ui/test_perf.py`; D41-4 con due Mac di riferimento; scelte minori del 4g confermate; risultati `perf` sul Mac minimo nel 41 §3.15 (P1 e P5 non raggiunti). 831 test di default; test di rete non eseguiti (`--no-network`). |
| 2026-10-24 | Claude Code | **Sprint 8 della v1, solo specifiche (D40-3 decisa):** nel `40` nuove §3.7.1 (catalogo dei messaggi codice → testo inglese/italiano con segnaposto, contratto dei moduli con `params`, inglese verso l'IA) e §3.7.2 (codice senza voce), test T5 riscritto e T18–T20; `05` (`ResultMessage` e `CommandError` con `params`) e `32` (testo inglese del catalogo nel risultato) aggiornati; verifica: i moduli 10–19 oggi restituiscono codice + testo italiano (~613 punti, ~152 con `details`), scelto dal proprietario di modificarli. Aperte D40-5 (posizione del catalogo), D41-7 e D41-8 (P1 e P5 non raggiunti, obiettivi invariati, sprint di prestazioni); scelte minori 1–10 dello sprint 4h confermate; annotato `test_t14_latency`. Aperte **17** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 15). **Nessun codice scritto**: si ferma per l'approvazione dei `.md` (e di 10–19 `§10`). |
| 2026-10-24 | Claude Code | **Sprint 8b (codice, FASE: CODICE – interfaccia v1):** `src/astrotwo/messages_catalog.py` (catalogo `en`/`it`, segnaposto, valori inseriti senza arrotondare, sotto-voci per `reason`, nota "(nessuna traduzione)"), `ui/message_view.py` (lingua dell'interfaccia: pannello Messaggi con dettaglio, stato, finestre, pannello IA), `ai/tool_registry.py` (verso il modello: codice, `params`, testo inglese, parametri esterni marcati); `ResultMessage`/`CommandError` con `params`; moduli **10 e 11** convertiti a codice + `params` (testo italiano invariato; `ModuleWarning` = coppia con `params`); D40-5 e D40-6 decise; test T18 (solo moduli convertiti), T19, T20, T5 riscritto; controllo automatico di ogni errore dei moduli convertiti contro il catalogo (`tests/conftest.py`). Test di rete non eseguiti (--no-network). |
| 2026-10-24 | Claude Code | **Sprint 8c (codice, FASE: CODICE – interfaccia v1):** modulo **12** convertito a codice + `params` (`HiPSError` con `params` e `relayed`, avvisi `ModuleWarning`; testo italiano invariato; errori del 14 e del 16 rilanciati con codice, testo e `params` dell'altro modulo); `12` §10 con la tabella dei parametri; voci del catalogo del 12 (e sotto-voci aggiunte a sei voci condivise); T18 e `conftest.py` con il 12; `tests/core/test_messages_hips.py`; aperta D40-7 (messaggi annidati). Aperte **17** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 15). Test di rete non eseguiti (`--no-network`). |
| 2026-10-24 | Claude Code | **Sprint 8c-bis (codice, FASE: CODICE – interfaccia v1):** D40-7 decisa (tipo `message`/`messages` ricorsivo, profondità 3, testo di terzi sempre esterno); `40` §3.7.1, `32`, `10`, `11`, `12` aggiornati; modulo **13** convertito a codice + `params` (`13` §10 con la tabella, voci del catalogo, `HIPS_TILE_PROBLEM` e `ASTRORES_LINK_PROBLEM` annidati, T18, `conftest.py`, `tests/core/test_messages_catalogs.py`). Aperte **16** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 14). Test di rete non eseguiti (`--no-network`). |
| 2026-10-24 | Claude Code | **Sprint 8d, modulo 14 (codice, FASE: CODICE – interfaccia v1):** modulo **14** convertito a codice + `params` (`14` §10 con la tabella, voci del catalogo, test, T18, `conftest.py`); errori e avvisi del 14 incorporati da 12 e 13 passano da `external` a `message`. Nessuna decisione cambia (16 aperte). Test di rete non eseguiti (`--no-network`). |
| 2026-10-24 | Claude Code | **Sprint 8d, modulo 16 (codice, FASE: CODICE – interfaccia v1):** modulo **16** convertito a codice + `params` (`16` §10 con la tabella, voci del catalogo, test, T18, `conftest.py`); l'errore del 16 incorporato dal 12 passa da `external` a `message`. Nessuna decisione cambia (16 aperte). Test di rete non eseguiti (`--no-network`). |
| 2026-10-24 | Claude Code | **Sprint 8d, modulo 19 (codice, FASE: CODICE – interfaccia v1):** modulo **19** convertito a codice + `params` (`19` §10 con la tabella, voci del catalogo, test, T18, `conftest.py`); errore del 19 incorporato dal 12 passa da `external` a `message`. Con 14, 16 e 19 convertiti, tutti gli errori che 12 e 13 incorporano da loro sono `message`. Nessuna decisione cambia (16 aperte). Test di rete non eseguiti (`--no-network`). |
| 2026-10-24 | Claude Code | **Sprint 8d, modulo 15 (codice, FASE: CODICE – interfaccia v1):** modulo **15** convertito a codice + `params` (`15` §10 con la tabella, voci del catalogo, test, T18, `conftest.py`). Nessuna decisione cambia (16 aperte). Test di rete non eseguiti (`--no-network`). |
| 2026-10-24 | Claude Code | **Sprint 8d, modulo 17 (codice, FASE: CODICE – interfaccia v1):** modulo **17** convertito a codice + `params` (`17` §10 con la tabella, voci del catalogo, test, T18, `conftest.py`). Nessuna decisione cambia (16 aperte). Test di rete non eseguiti (`--no-network`). |
| 2026-10-24 | Claude Code | **Sprint 8d concluso, modulo 18 (codice, FASE: CODICE – interfaccia v1):** modulo **18** convertito a codice + `params` (`18` §10 con la tabella, voci del catalogo, test, T18, `conftest.py`); `40` §3.7.1 aggiornata. Nessuna decisione cambia (16 aperte). Test di rete non eseguiti (`--no-network`). |
| 2026-10-25 | Claude Code | **Sprint 8e concluso (codice, FASE: CODICE – interfaccia v1):** `04`, `05`, `30`–`35` e i messaggi di `40`, `41`, `42` e `44` convertiti a codice + `params` (§10.1 di ognuno prima del codice, voci del catalogo, test, T18 su tutto `src/astrotwo`, `conftest.py`, traduzione italiana della frase di indisponibilità del `44`); **D40-3 chiusa**. Codici nuovi: `AI_PROFILE_INVALID`, `AI_RETRY`, `SESSION_SAVE_FAILED`, `PREFERENCE_VALUE_INVALID`, `UI_COMMAND_FAILED`, `MODULE_NOTE`, `SESSION_FINGERPRINT_CHANGE`, `SESSION_STATE_DIFFERENCE`, `KEYCHAIN_OPERATION`. Nessun'altra decisione cambia (16 aperte). Test di rete non eseguiti nel commit (`--no-network`). |
| 2026-10-25 | Claude Code | **Sprint 8f (rifiniture):** `layer_context` (`40` §3.7.1) nei messaggi di disegno di cataloghi e MOC e negli avvisi `CATALOG_EPOCH_*` (voci senza più il segnaposto `layer`); SkyCoord inutilizzato tolto da un test; test di rete: IERS `datacenter.iers.org` HTTP 400 per ogni percorso (causa lato server, non URL/intestazioni/test), ripiego sul mirror USNO deciso dal proprietario e implementato (`18`); EPN-TAP non raggiungibile. Nessun valore di UT1 assunto. |
