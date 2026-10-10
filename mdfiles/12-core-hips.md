# 12-core-hips.md — servizi HiPS all-sky

**Stato:** approvato

## 2. Scopo

Fornire le immagini all-sky HiPS (survey astronomici) con la stessa facilità
di navigazione di Aladin, mantenendo tracciabili provenienza e data di ogni
riquadro mostrato.

## 3. Cosa fa

- **Sfoglio dei survey HiPS (C1):** elencare i survey disponibili, permettere
  di attivarne uno e navigare (zoom/pan) con caricamento progressivo dei
  riquadri (tile).
- **Survey predefiniti (C2):** l'elenco dei survey è **dinamico**, letto dal
  MocServer (H26, D12-3), così resta aggiornato senza una tabella mantenuta
  a mano; il survey attivo all'avvio è **DSS2 a colori** (D12-3).
- **Richiesta dei riquadri:** scaricare i tile necessari al campo visualizzato
  mantenendo la risoluzione appropriata, con timeout e ripiego se la rete
  manca.
- **Cache su disco (A7):** i riquadri HiPS si conservano come file nella
  **cache comune di `04-cache.md`** (`~/Library/Caches/AstroTwo/`, un solo
  limite di 5 GB per tutta la cache, timeout 10 s / 60 s), con eliminazione
  dei dati meno usati e provenienza (origine + data di scaricamento) per ogni
  riquadro servito; il modulo non ha una cache propria (CA4).
- **Impronta del survey (C4):** mostrare la copertura del survey attivo —
  i dati di copertura appartengono a `16-core-moc.md`, questo modulo fornisce
  l'identità e la posizione del survey.
- **Generazione di HiPS (H9):** creare un nuovo HiPS a partire da un set di
  immagini, anche da riga di comando, secondo lo **standard pubblico IVOA
  HiPS 1.0** (D12-1, corretta il 2026-10-10): ricampionamento dei tile con
  `reproject` dove la libreria lo offre, **codice nostro** per il resto
  (struttura delle cartelle e degli ordini, file `properties`, anteprima
  `Allsky`, tile JPEG/PNG da quelli FITS); la copertura MOC del nuovo HiPS si
  calcola con `16-core-moc.md`. Nessuno strumento esterno.
- **Cataloghi HiPS progressivi, mappe e griglie HEALPix (H12):** servire
  cataloghi come livelli progressivi (caricamento per ordine HEALPix) e
  produrre/disegnare mappe e griglie HEALPix. **Confine deciso il 2026-10-04
  (D12-5, pari a D16-5):** i **dati e le computazioni HEALPix vivono in
  `16-core-moc.md`**, qui resta il **servizio dei tile** — nessuna logica
  HEALPix duplicata.
- **Aggiunta di un HiPS da identificativo o URL (C3):** aggiungere all'elenco
  un servizio HiPS non presente, indicandone l'**identificativo** (es.
  `CDS/P/PanSTARRS/DR1/r') o l'**URL di base** del servizio. Il modulo
  **legge i metadati del servizio** (titolo del survey, banda, risoluzione
  massima, formato dei tile, versione, pagina di descrizione, copertura),
  **valida** che la risposta corrisponda davvero a un servizio HiPS, registra
  la voce con la sua provenienza e la rende attivabile come le altre; se
  l'URL non risponde, non è un servizio HiPS o i metadati sono incompleti,
  rifiuta l'operazione con errore esplicito (§10) senza aggiungere nulla.
  Inclusa per decisione del proprietario (2026-10-04): in Aladin la funzione
  non risulta documentata, ma la parità con Aladin è il minimo.
- **Schede server (H10, parte HiPS):** aggiungere immagini da servizi di
  terze parti (es. SkyView); la parte protocollo/VO di H10 è in
  `14-core-protocolli-vo.md`.
- **Cubi HiPS (H24, sez. 8.1 del manuale di Aladin, ed. giugno 2022):** survey
  progressivi a cubo secondo lo standard HiPS 1.0 (tile per piano, profondità
  del cubo nelle proprietà del servizio; nomi esatti delle proprietà **da
  verificare** nello standard). Si scarica il tile del piano richiesto;
  scorrimento dei piani nel 41, analisi dei cubi nel 23.
- **Filtro delle collezioni (H26, sez. 8.3.3):** l'elenco delle collezioni
  (proprietà dei servizi HiPS e dei cataloghi) si ottiene dal **MocServer**
  del CDS, si sincronizza all'avvio e se ne conserva una copia locale nella
  cache A7 con origine e data. Il filtro **sulle proprietà** (testo, regole)
  è locale; il filtro **spaziale** per copertura è di `16-core-moc.md`
  (`query_mocserver`). Client: `astroquery.mocserver` (astroquery, scelta S6
  di `01-architettura.md`; copertura dell'interfaccia **da verificare prima
  del codice**). Senza rete si usa la copia locale con la sua data.
- **Immagini di qualsiasi dimensione, parte HiPS (H27, sez. 8.3.1):** si
  scaricano solo i tile del campo visualizzato all'ordine adatto, conservati
  nella cache su disco; il valore del pixel sotto il cursore si legge dal tile
  FITS in cache, mai da una copia ridotta per la visualizzazione.

## 4. Cosa NON fa

- Non fa le trasformazioni di coordinate (10) né gestisce i file FITS locali (11).
- Non esegue query sui cataloghi (14), non fa cross-match (15).
- Non decide la colorimetria o le regolazioni di display: le applica la UI (41)
  su ciò che questo modulo restituisce.
- Non genera MOC: fornisce solo le informazioni di copertura richieste a `16`.
- Non analizza i metadati dei survey oltre a quelli serviti dal servizio
  HiPS (nessuna interpretazione scientifica).

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `04-cache.md` (cache comune A7),
  `10-core-coordinate-wcs.md` (calcolo del campo e delle
  coordinate dei tile), `16-core-moc.md` (formati HEALPix condivisi per H12).
- **Usato da:** `16-core-moc.md`, `19-core-dati-planetari.md`,
  `41-ui-visualizzatore-cielo.md`.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `hips_id` / URL servizio | stringa | identificativo HiPS o URL di base | survey attivo |
| in | `hips_id` / URL da aggiungere | stringa | identificativo HiPS o URL di base | C3: aggiunta a elenco |
| in | campo richiesto | float64 | gradi (centro) + FOV in gradi | dal visualizzatore |
| in | livello di dettaglio | intero | ordine HEALPix | risoluzione del tile |
| out | riquadro (tile) | immagine | pixel + WCS + header del servizio | PNG/FITS secondo il servizio |
| out | elenco survey | lista | id, nome, banda, risoluzione, copertura | |
| out | metadati servizio HiPS | struttura | titolo, banda, risoluzione max, formato tile, versione, URL descrizione, copertura | obbligatori per C3 prima di aggiungere |
| out | `body` | stringa | `celestial` o nome IAU del corpo | obbligatorio (D19-3): ricavato dal sistema di coordinate del servizio o dai metadati planetari, mai assunto |
| out | metadati riquadro | struttura | URL sorgente, data di scaricamento, dimensione | obbligatori per A7 |
| out | copertura survey | MOC / regione | gradi | delegata al modulo 16 |
| in | `plane` | intero ≥ 0 | indice del piano del cubo HiPS | solo per i cubi (H24) |
| out | elenco delle collezioni | lista | identificativi e proprietà, origine e data della sincronizzazione | H26 |

## 7. Interfaccia pubblica

- **`HiPSList`** — elenco e ricerca dei survey disponibili; espone i metadati
  di ciascuno.
- **`set_survey(hips_id)`** — attiva un survey; restituisce metadati e copertura.
- **`add_hips(hips_id_or_url)`** (C3) — aggiunge un HiPS da identificativo o
  URL: legge e valida i metadati del servizio, registra la voce in elenco con
  provenienza e la rende attivabile; in caso di errore non aggiunge nulla e
  restituisce il codice di errore di §10.
- **`fetch_tile(survey, order, tile_index)`** — scarica un riquadro; restituisce
  immagine + origine + data; in caso di errore di rete restituisce errore, non
  un tile finto.
- **`tiles_for_fov(center, fov, order)`** — calcola quali riquadri servono per
  un campo. Calcolo deterministico su griglia HEALPix.
- **Cache:** nessuna classe propria (CA4): i riquadri si salvano e si
  rileggono con `SharedCache` di `04-cache.md`.
- **`build_hips(...)`** — generazione HiPS (H9) secondo D12-1 (corretta il
  2026-10-10): standard IVOA HiPS 1.0, `reproject` dove possibile, codice
  nostro per il resto.
- **`healpix_map(...)`** / **`healpix_grid(...)`** — mappe e griglie HEALPix
  (H12), delegando i calcoli HEALPix a `16-core-moc.md`.
- **`cube_planes(survey)`** (H24) — numero e descrizione dei piani di un
  cubo HiPS; `fetch_tile` accetta l'indice del piano per i cubi.
- **`CollectionIndex`** (classe, H26) — copia locale delle proprietà delle
  collezioni: `sync()` dal MocServer, `filter(rules)` sulle proprietà;
  espone origine e data della sincronizzazione.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| Standard IVOA HiPS 1.0 | formato e URL dei riquadri, generazione (H9) | standard pubblico della comunità |
| `reproject` (D11-2, verificato con l'11) | ricampionamento delle immagini nei tile HEALPix per la generazione (H9) | già scelto dal progetto; copertura della generazione **da verificare prima del codice** |
| `astroquery.hips2fits` (D12-4) | solo complemento per i ritagli FITS prodotti dal server; i tile si scaricano con il client diretto | vedi §13 |
| `healpy` / `astropy-healpix` (via modulo 16) | griglie e ordini HEALPix | standard del dominio |
| `requests` (o libreria HTTP già usata dal progetto) | richieste HTTP con timeout | pratica consolidata |
| `astroquery.mocserver` (astroquery, S6) | sincronizzazione delle proprietà delle collezioni (H26) | client del servizio CDS; interfaccia da verificare prima del codice |

## 9. Regole e vincoli

- Ogni tile servito (dalla rete o dalla cache) riporta **origine e data di
  scaricamento** (A7).
- I riquadri HiPS stanno su **file su disco** della cache comune, non in
  SQLite (A7); limite unico di 5 GB per tutta la cache (CA2 di `04-cache.md`).
- Nessuna richiesta di rete senza timeout dichiarato; offline ⇒ errore o tile
  già in cache, mai pixel inventati.
- La richiesta dei tile deve seguire il campo di vista calcolato con il
  modulo 10: nessuna assunzione sulla proiezione fatta in modo indipendente.
- I dati di copertura/i MOC non vengono ricalcolati qui: si usano quelli del 16.
- Le operazioni HEALPix (ordini, indici) sono deterministiche e testate con le
  librerie HEALPix, mai riscritte.

- **Corpo di riferimento (`body`, D19-3 decisa il 2026-10-08):** ogni servizio HiPS e ogni tile porta
  nei metadati il campo **obbligatorio** `body`. Per i dati astronomici vale
  `celestial` (sfera celeste) ed è **ricavato dal sistema di coordinate
  dichiarato** (es. ICRS, galattico, eclittico), **mai assunto**; per i dati
  planetari è il corpo letto dai metadati secondo
  `19-core-dati-planetari.md`. Se `body` non si può ricavare, il dato si apre
  ma non si sovrappone né si combina con altri (`BODY_UNKNOWN`); la
  sovrapposizione tra corpi diversi segue D19-4 (`BODY_MISMATCH`, forzabile
  solo con opzione esplicita citata nel risultato).

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Survey sconosciuto | errore con elenco degli id noti | `HIPS_UNKNOWN` |
| HiPS da ID/URL non raggiungibile / timeout | nessuna voce aggiunta, errore con l'URL richiesto | `NET_TIMEOUT` |
| URL che non risponde con un servizio HiPS (metadati mancanti o non HiPS) | rifiuto con la risposta ricevuta, nessuna voce aggiunta | `HIPS_NOT_A_SERVICE` |
| Metadati del servizio incompleti o incoerenti | rifiuto che indica il campo mancante, nessuna voce aggiunta | `HIPS_METADATA_INVALID` |
| Campo fuori dalla copertura del survey | nessun tile, avviso "fuori copertura" | `HIPS_OUT_OF_COVERAGE` |
| Rete assente con cache vuota | errore di rete; la vista resta utilizzabile senza quel layer | `NET_TIMEOUT` |
| Tile corrotto o di dimensione inattesa | scartato e richiesto di nuovo; se persiste, errore | `HIPS_BAD_TILE` |
| Cache oltre il limite | rimozione dei dati meno usati, registrata | `CACHE_FULL` |
| Ordine HEALPix fuori intervallo | rifiuto con l'intervallo valido | `HEALPIX_ORDER_INVALID` |
| Corpo (`body`) non ricavabile dai metadati né dal sistema di coordinate | dato aperto da solo, non sovrapposto né combinato | `BODY_UNKNOWN` |
| Piano del cubo inesistente | rifiuto con il numero di piani disponibili | `HIPS_CUBE_PLANE_INVALID` |
| MocServer non raggiungibile | si usa la copia locale con la sua data e un avviso; senza copia locale, errore | `MOCSERVER_UNAVAILABLE` |

## 11. Esposizione all'IA

- **`list_surveys`** — output: elenco survey con metadati (nessun calcolo).
- **`add_hips`** (C3) — input: identificativo o URL; output: metadati letti e
  stato dell'aggiunta. Nessun calcolo numerico: solo lettura/validazione
  metadati.
- **`get_coverage(survey)`** — output: copertura del survey come MOC;
  **calcolo: modulo 16** (healpy/astropy-healpix).
- **`get_tile_provenance(survey, order, tile)`** — output: origine e data del
  riquadro; nessun calcolo.

Nessun altro strumento: l'IA non scarica né interpreta pixel.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Elenco survey | leggere l'elenco dei survey | contiene almeno i survey predefiniti dichiarati, con metadati completi | confronto con la risposta del servizio (test di rete separato) |
| T2 | Calcolo dei tile per un campo | chiedere i tile per centro (0°,0°) e FOV 1° a un ordine fissato | gli indici coincidono con quelli ricalcolati nel test con la libreria HEALPix | ricalcolo con `healpy`/`astropy-healpix` |
| T3 | Cache con provenienza | richiedere due volte lo stesso riquadro | seconda lettura da cache, con origine e data valorizzate e invariate | lettura metadati cache |
| T4 | Limite di cache | impostare un limite piccolo e richiedere riquadri diversi | i dati meno usati vengono rimossi, il totale resta sotto il limite | controllo dimensione directory cache |
| T5 | Campo fuori copertura | chiedere un campo sopra un polo per un survey non polare | `HIPS_OUT_OF_COVERAGE`, nessun tile fasullo | test con servizio simulato |
| T6 | Errore di rete | simulare rete assente con cache vuota | `NET_TIMEOUT` entro il timeout, nessun pixel inventato | test di unità con server simulato |
| T7 | Aggiunta HiPS da URL (C3) | aggiungere un servizio HiPS simulato tramite URL di base | metadati letti e validati, voce presente in elenco e attivabile, tile scaricabili | confronto con i metadati del servizio simulato |
| T8 | Aggiunta HiPS da URL non valido (C3) | passare un URL che non è un servizio HiPS | `HIPS_NOT_A_SERVICE`, nessuna voce aggiunta | test di unità con server simulato |
| T9 | Cubo HiPS (H24) | servizio HiPS simulato a cubo con 3 piani; richiedere il tile del piano 2 | tile del piano 2; richiesta del piano 5 → `HIPS_CUBE_PLANE_INVALID` | servizio simulato |
| T10 | Sincronizzazione delle collezioni (H26) | `CollectionIndex.sync()` contro un MocServer simulato, poi `filter` per testo | elenco filtrato corretto; origine e data della sincronizzazione presenti | servizio simulato (test di rete separato per il servizio reale) |
| T11 | MocServer assente (H26) | sincronizzazione con rete assente e copia locale presente | copia locale usata, avviso `MOCSERVER_UNAVAILABLE` con la data della copia | test di unità |
| T12 | Valore del pixel su HiPS (H27) | leggere il valore sotto il cursore su un tile FITS in cache | valore uguale a quello del tile FITS letto con `astropy.io.fits` | confronto diretto |

## 13. Decisioni aperte

- **D12-1 — Generazione HiPS (H9): DECISA il 2026-10-09, CORRETTA il
  2026-10-10 (decisione del proprietario, regola d'oro n. 8).** La generazione
  segue lo **standard pubblico IVOA HiPS 1.0**, con **`reproject`** dove
  possibile (quali passi copre: **da verificare prima del codice**) e
  **codice nostro** per il resto; **nessun programma di Aladin** (Hipsgen
  tolto), nessuno strumento esterno, nessun ambiente Java dentro il `.dmg`.
- **D12-2 — Caricamento HiPS da ID/URL (C3): DECISA il 2026-10-04 — inclusa
  per decisione del proprietario** (parità con Aladin = minimo). La funzione è
  descritta in §3/§7 con errori in §10; restano solo verifiche tecniche su
  lettura metadati e codici di errore, non sull'esistenza in Aladin.
- **D12-3 — Survey predefiniti (C2): DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** **elenco dinamico dal
  MocServer** (riga H26 di `03-parita-aladin.md`), con **default DSS2 a
  colori**. **Motivazione (nostra, 2026-10-10):** copre il **cielo intero**
  con dati **pubblici**, quindi ogni campo richiesto ha un'immagine di
  sfondo; identificativo esatto **da verificare prima del codice**.
- **D12-4 — Cliente HiPS: DECISA il 2026-10-09 (decisione del proprietario
  sulla checklist del livello 1).** **client HTTP diretto** secondo lo
  standard IVOA HiPS 1.0 (tile, proprietà, ordini); `astroquery.hips2fits`
  solo come complemento per i ritagli FITS prodotti dal server.
- **D12-5 — Cataloghi HiPS progressivi (H12): DECISA il 2026-10-04.**
  **Dati e computazioni HEALPix nel `16`, servizio dei tile nel `12`** (stesso
  confine scritto in `16-core-moc.md`, D16-5). **Motivazione:** un solo
  confine dichiarato, nessuna logica HEALPix duplicata, coerente con §3/§9 di
  questo file. Applicata in §3 qui sopra.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). |
| 2026-10-04 | agente di sviluppo | **C3 inclusa per decisione del proprietario:** aggiunta la funzione "aggiunta di un HiPS da identificativo o URL" (§3), `add_hips` (§7), righe input/output (§6), errori `NET_TIMEOUT`/`HIPS_NOT_A_SERVICE`/`HIPS_METADATA_INVALID` (§10), strumento IA (§11), test T7–T8 (§12); D12-2 chiusa come decisa (§13). Riga C3 in `03-parita-aladin.md` passata a `inclusa (decisione del proprietario)`. |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario: D12-5 passata da aperta a decisa** — dati/computazioni HEALPix nel 16, servizio dei tile nel 12 (§3; pari a D16-5 in `16-core-moc.md`); **cache su disco con limite di default 5 GB** (D11-3 di `11-core-immagini-fits.md`, §3/§9). Decisioni riportate in `decisioni-aperte.md`. |
| 2026-10-08 | Claude Code | §5: aggiunti a "Usato da" i moduli `19-core-dati-planetari.md` (scritti il 2026-10-08, stato bozza). Nessun altro testo cambia. |
| 2026-10-09 | Claude Code | **D19-3 applicata (decisione del proprietario del 2026-10-08):** campo `body` obbligatorio nei metadati di ogni servizio HiPS e di ogni tile (§6, §9, §10); per i dati astronomici `celestial`, ricavato dal sistema di coordinate, mai assunto; errori `BODY_UNKNOWN` e, per le sovrapposizioni, `BODY_MISMATCH` secondo D19-4 (forzabile solo con opzione esplicita citata nel risultato). |
| 2026-10-09 | Claude Code | **D12-1, D12-3, D12-4 DECISE** (checklist del livello 1): generazione HiPS con libreria Python se `reproject` la offre (da verificare), altrimenti Hipsgen esterno; survey dal MocServer con default DSS2 a colori; client HTTP diretto HiPS 1.0 (hips2fits come complemento). §7 aggiornato. |
| 2026-10-09 | Claude Code | **Completamento con gli esiti di AP5** (decisione del proprietario del 2026-10-09): §3, §6, §7, §8, §10, §12 per H24 (cubi HiPS), H26 (collezioni dal MocServer con copia locale; filtro spaziale nel 16; client `astroquery.mocserver`, interfaccia da verificare) e H27 (solo tile del campo; valore del pixel dal tile FITS). §8: riga `hips2fits` allineata a D12-4. Nessuna nuova decisione dei Gruppi 1 e 2. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** (regola del proprietario del 2026-10-09): modulo completato con gli esiti di AP5, nessuna decisione aperta nei Gruppi 1 e 2. |
| 2026-10-09 | Claude Code | **Collegamento alla cache comune `04-cache.md`** (approvato il 2026-10-09; decisione CA4 del proprietario, autorizzazione esplicita a modificare il file approvato): §3, §5, §7, §9 — tolta `HiPSCache`, riquadri nella cache comune `SharedCache`; tolto da "Usato da" l'`11` per la cache. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Regola d'oro n. 8** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): D12-1 corretta — generazione HiPS secondo lo standard IVOA HiPS 1.0, `reproject` dove possibile, codice nostro per il resto, Hipsgen tolto (§3, §7, §8, §13); D12-3 — DSS2 a colori resta, con motivazione nostra (cielo intero, dati pubblici); §3 C2 senza elenco preso da Aladin (elenco dinamico dal MocServer); §8 "Specifica HiPS (CDS)" → standard IVOA HiPS 1.0. Stato `approvato` invariato. |
