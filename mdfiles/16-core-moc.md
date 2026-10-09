# 16-core-moc.md — mappe di copertura MOC

**Stato:** approvato

## 2. Scopo

Creare, manipolare e interrogare mappe di copertura (MOC) — spaziali,
temporali e spazio-temporali — con operazioni rigorose, così che la copertura
di un dato sia sempre verificabile e confrontabile.

## 3. Cosa fa

- **Tipi di MOC (E6):** MOC **spaziali** (ordine HEALPix sul cielo), **temporali**
  (intervallo di tempo) e **spazio-temporali** (combinazione).
- **Creazione (E6):** generare MOC da immagini, da cataloghi, da poligoni, da
  cerchi e da mappe di probabilità; ogni creazione dichiara ordinamento,
  risoluzione (ordine massimo) e unità.
- **Operazioni insiemistiche (E6):** unione, intersezione, sottrazione,
  complemento tra MOC; risultati sempre normalizzati e validati.
- **Filtro delle sorgenti per MOC (E6):** selezionare i record di una tabella
  che cadono dentro (o fuori) da un MOC — l'operazione restituisce indici, il
  disegno è della UI.
- **Impronta dei survey (C4):** rappresentare la copertura di un survey come
  MOC e mostrarla (il servizio dei tile è di `12-core-hips.md`).
- **Mappe e griglie HEALPix (H12):** produrre mappe HEALPix (conteggi/flussi
  per cella) e griglie di riferimento; **cataloghi HiPS progressivi** (H12):
  **confine deciso il 2026-10-04 (D16-5, pari a D12-5): dati e computazioni
  HEALPix vivono qui, il servizio dei tile resta in `12-core-hips.md`**.
- **Generazione di MOC da riga di comando (H9):** stesse operazioni
  raggiungibili senza interfaccia grafica; integrazione con lo scripting di
  `24-analisi-pipeline-riproducibili.md`.
- **Versioni del formato MOC (H22, sez. 8.1 del manuale di Aladin, ed. giugno 2022):**
  lettura dei MOC nelle versioni dello standard IVOA **da 1.0 a 2.1**
  (spaziali, temporali, spazio-temporali) in FITS e in JSON; la versione letta
  è riportata nel risultato; la scrittura usa la versione corrente dello
  standard (FITS IVOA, D16-2) dichiarata nei metadati. Il supporto di tutte le
  versioni in `mocpy` è **da verificare prima del codice**.
- **Filtro spaziale delle collezioni tramite MocServer (H26, sez. 8.3.3):**
  interrogazione del MocServer del CDS con una regione o un MOC (più filtri
  sulle proprietà) per ottenere le collezioni che coprono la regione; i MOC
  delle collezioni restano sul server (troppo grandi per il client), le
  proprietà sono nella copia locale di `12-core-hips.md`. Client
  `astroquery.mocserver` (astroquery, S6; interfaccia **da verificare prima
  del codice**). Senza rete il filtro spaziale non è disponibile: errore
  esplicito, mai un elenco parziale presentato come completo.

## 4. Cosa NON fa

- Non scarica immagini né cataloghi (11, 12, 14).
- Non disegna: i MOC e le griglie li rende la UI (41).
- Non gestisce le query ADQL (14/33) né i cross-match (15).
- Non calcola fotometria o curve di luce (20, 22).
- Non memorizza i MOC nella cache dei cataloghi: la persistenza segue la
  **stessa politica della cache immagini/dati (A7)** — **formato FITS
  standard IVOA su file, nella cache con origine e data** (D16-2, decisa il
  2026-10-04).

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `10-core-coordinate-wcs.md` (coordinate di cerchi/poligoni),
  `13-core-cataloghi.md` (tabelle per creare MOC da cataloghi e per il filtro),
  `12-core-hips.md` (identità dei survey per C4/H12), `14-core-protocolli-vo.md`
  (eventuali MOC scaricati dai servizi).
- **Usato da:** `11-core-immagini-fits.md`, `12-core-hips.md`,
  `19-core-dati-planetari.md`,
  `41-ui-visualizzatore-cielo.md`, `16` è usato anche da
  `50-avanzate-transienti.md` (copertura delle osservazioni).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | regione | poligono/cerchio | gradi (coordinate) | per creare MOC |
| in | catalogo | `astropy.table.Table` | con coordinate | per creare MOC da cataloghi |
| in | immagine | `FitsImage` (modulo 11) | pixel + WCS | per creare MOC da immagini |
| in | mappa di probabilità | mappa HEALPix | probabilità per cella ∈ [0,1] | |
| in | intervallo temporale | istante/intervallo | ISO 8601 (interfaccia/file) o JD | MOC temporali: internamente **JD** via `astropy.time` (D16-3) |
| in | `order_max` | intero | ordine HEALPix | risoluzione |
| out | MOC | oggetto MOC | unità: degree (spaziale), tempo (temporale) | serializzazione cache: **FITS standard IVOA**; export anche **JSON** e **testo** (D16-2) |
| out | `body` | stringa | `celestial` o nome IAU del corpo | obbligatorio (D19-3): ricavato dal sistema di coordinate o dai metadati planetari, mai assunto; operazioni solo tra MOC dello stesso corpo |
| out | operazioni | MOC | stesso formato dell'input | |
| out | selezione | indici booleani | — | filtro per MOC |
| out | mappa HEALPix | array + ordine | valori per cella | H12 |
| in | file MOC | percorso o URL | FITS o JSON, versioni 1.0–2.1 | H22 |
| out | versione del MOC letto | stringa | versione dello standard | H22 |
| in | regione o MOC + filtri per il MocServer | struttura | coordinate in gradi con frame | H26 |
| out | collezioni che coprono la regione | lista | identificativi, origine e data della risposta | H26 |

## 7. Interfaccia pubblica

- **`Moc`** (classe): MOC spaziale/temporale/spazio-temporale; metodi
  descrittivi `union`, `intersection`, `difference`, `complement`, `contains`.
- **`moc_from_catalog(table, order_max)`**, **`moc_from_region(...)`**
  (cerchi/poligoni), **`moc_from_image(image)`**, **`moc_from_probability(map)`**
  — costruttori (E6); ciascuno dichiara risoluzione e unità.
- **`filter_by_moc(table, moc, inside)`** — filtro delle sorgenti (E6);
  restituisce indici.
- **`survey_coverage(survey)`** — copertura di un survey come MOC (C4).
- **`healpix_map(...)`** / **`healpix_grid(...)`** — mappe e griglie HEALPix
  (H12). **Calcolo: `healpy` o `astropy-healpix`.**
- **`build_moc(...)`** — ingresso da riga di comando (H9), delegato alle
  funzioni sopra.
- **Persistenza e export (D16-2):** i MOC si salvano in cache in **formato
  FITS standard IVOA** (file, con origine e data come gli altri dati della
  cache A7); l'export dell'utente offre anche **JSON** e **testo**.
- **`read_moc(source)`** (H22) — legge un MOC FITS o JSON e ne dichiara la
  versione.
- **`query_mocserver(region_or_moc, property_filter)`** (H26) — collezioni
  che coprono la regione, con provenienza della risposta.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| Standard IVOA MOC | formato delle mappe di copertura (cache in **FITS IVOA**, export JSON/testo — D16-2) | standard della comunità |
| `astropy-healpix` | operazioni HEALPix | mantenuto da AstroPy/ESA |
| `healpy` | mappe HEALPix, mappe di probabilità | consolidato in astronomia |
| `mocpy` (**scelto con D16-1**) | creazione/operazioni MOC, incluso i MOC temporali | libreria MOC dedicata allineata allo standard IVOA; **licenza e installazione su macOS da verificare prima di approvare `16`** |
| `astropy.coordinates` (via 10) | cerchi/poligoni in coordinate | conversioni verificate |
| `astroquery.mocserver` (astroquery, S6) | filtro spaziale delle collezioni (H26) | client del servizio CDS; interfaccia da verificare prima del codice |

## 9. Regole e vincoli

- Le operazioni insiemistiche devono rispettare le proprietà matematiche:
  unione commutativa, intersezione ⊆ operandi, complemento di complemento =
  originale (test T3).
- Ogni MOC dichiara unità, ordine massimo, sistema di riferimento e corpo
  (`body`); un MOC senza queste informazioni è un errore.
- Le creazioni da cerchio/poligono usano la geometria celeste del modulo 10
  (nessuna approssimazione piana).
- I calcoli HEALPix sono delegati alle librerie HEALPix (regola d'oro n. 4).
- Le selezioni per MOC restituiscono solo indici: nessuna modifica della
  tabella sorgente.
- I valori di probabilità devono restare in [0,1]; fuori range ⇒ errore.
- **Tempo (D16-3, decisa il 2026-10-04):** internamente **numerico, JD tramite
  `astropy.time`**; **ISO 8601 solo nell'interfaccia e nei file**; **la scala
  di tempo si dichiara sempre** (UTC, TDB, TCB); i **MOC temporali usano la
  scala dello standard IVOA (da verificare)**. Regola di progetto in
  `02-convenzioni.md` DC1.
- **Formato in cache:** FITS standard IVOA su file, con origine e data come
  gli altri dati della cache A7 (D16-2).

- **Corpo di riferimento (`body`, D19-3 decisa il 2026-10-08):** ogni MOC porta
  nei metadati il campo **obbligatorio** `body`. Per i dati astronomici vale
  `celestial` (sfera celeste) ed è **ricavato dal sistema di coordinate
  dichiarato** (es. ICRS, galattico, eclittico), **mai assunto**; per i dati
  planetari è il corpo letto dai metadati secondo
  `19-core-dati-planetari.md`. Se `body` non si può ricavare, il dato si apre
  ma non si sovrappone né si combina con altri (`BODY_UNKNOWN`); la
  sovrapposizione tra corpi diversi segue D19-4 (`BODY_MISMATCH`, forzabile
  solo con opzione esplicita citata nel risultato).
- Le operazioni insiemistiche e i filtri si fanno solo tra MOC e dati dello
  stesso corpo; corpi diversi danno `BODY_MISMATCH` (stesso schema di D19-4).

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| MOC vuoto | consentito; contiene niente, operazioni definite | esito `MOC_EMPTY` |
| Ordine HEALPix non valido (negativo o oltre il max dello standard) | rifiuto con l'intervallo | `HEALPIX_ORDER_INVALID` |
| Regione fuori dal cielo o coordinate invalide | rifiuto dell'input | `REGION_INVALID` |
| Probabilità fuori [0,1] | rifiuto dell'input | `PROBABILITY_OUT_OF_RANGE` |
| Operazione tra MOC di unità diverse (spaziale vs temporale) | rifiuto con descrizione | `MOC_TYPE_MISMATCH` |
| MOC corrotto in lettura | errore con il file/la riga problematica | `MOC_UNREADABLE` |
| Tabella senza coordinate per il filtro | rifiuto prima del calcolo | `NO_COORD_COLUMNS` |
| Corpo (`body`) non ricavabile dai metadati né dal sistema di coordinate | dato aperto da solo, non sovrapposto né combinato | `BODY_UNKNOWN` |
| Operazione o filtro tra MOC/dati di corpi diversi | rifiuto; forzatura solo con opzione esplicita citata nel risultato (D19-4) | `BODY_MISMATCH` |
| Versione del MOC non supportata | nessun MOC letto, errore con la versione trovata | `MOC_VERSION_UNSUPPORTED` |
| MocServer non raggiungibile | nessun filtro spaziale, errore esplicito | `MOCSERVER_UNAVAILABLE` |

## 11. Esposizione all'IA

- **`moc_from_catalog`** / **`moc_from_region`** — input: tabella o regione +
  ordine; output: MOC. **Calcolo: libreria MOC/HEALPix.**
- **`moc_operations`** — input: due MOC + operazione; output: MOC.
  **Calcolo: libreria MOC.**
- **`filter_by_moc`** — input: tabella + MOC + dentro/fuori; output: conteggio
  e indici. **Calcolo: libreria MOC/NumPy.**
- **`describe_moc`** — input: MOC; output: superficie coperta (in steradianti
  o frazione di cielo), numero di celle, ordine. **Calcolo: libreria MOC.**

L'IA non calcola né approssima mai superfici o coperture.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | MOC da cerchio | creare un MOC di raggio 1° attorno a un punto | area ≈ 2π(1 − cos 1°) steradianti (entro la tolleranza legata all'ordine usato) | area ricalcolata nel test con la formula e con `astropy.units` |
| T2 | Circolo completo | unione di quattro quarti di cielo (regioni che coprono tutto) | area ≈ 4π steradianti (entro la tolleranza dell'ordine) | ricalcolo con Astropy/`math` nel test |
| T3 | Proprietà insiemistiche | generare due MOC casuali con semina fissa; verificare A∪B ⊇ A∩B, (A∖B)∩B = ∅, ¬¬A = A | tutte le proprietà vere | controllo con le operazioni ricalcolate nel test |
| T4 | Filtro per Moc | 1000 punti casuali (semina fissa) dentro un MOC noto | conteggio coincidente con quello ricalcolato nel test con `healpy`/`astropy-healpix` | ricalcolo con la libreria HEALPix |
| T5 | Mismatch di unità | unire un MOC spaziale con uno temporale | `MOC_TYPE_MISMATCH` | test di unità |
| T6 | Mappe HEALPix | produrre una mappa HEALPix su una distribuzione nota | valori per cella coincidenti con `healpy`/`astropy-healpix` ricalcolato nel test | ricalcolo con la libreria scelta |
| T7 | Versioni MOC (H22) | leggere MOC di prova nelle versioni 1.0, 2.0 e 2.1, in FITS e JSON | stesse celle lette da `mocpy`; versione riportata | confronto con `mocpy` |
| T8 | Filtro MocServer (H26) | `query_mocserver` su una regione con risposta simulata | elenco delle collezioni con origine e data | servizio simulato (test di rete separato) |
| T9 | MocServer assente (H26) | `query_mocserver` senza rete | `MOCSERVER_UNAVAILABLE`, nessun elenco parziale | test di unità |

## 13. Decisioni aperte

- **D16-1 — Libreria MOC: DECISA il 2026-10-04.** **`mocpy`** (creazione e
  operazioni MOC, incluso i MOC temporali); le librerie HEALPix (`healpy` /
  `astropy-healpix`) restano per mappe e griglie. **Motivazione:** E6 richiede
  MOC spaziali **e temporali**, `mocpy` è allineato allo standard IVOA.
  **Da verificare prima di approvare `16`:** licenza e installazione su macOS.
  Applicata in §8 qui sopra.
- **D16-2 — Serializzazione: DECISA il 2026-10-04.** I MOC vivono in cache in
  **formato FITS standard IVOA** (file su disco, con origine e data come gli
  altri dati della cache A7); l'export offre anche **JSON** e **testo**.
  **Motivazione:** formato standard della comunità (regola d'oro n. 4),
  tracciabilità A7 già prevista per i file; SQLite resta per le tabelle.
  Applicata in §4/§6/§7/§9 qui sopra.
- **D16-3 — MOC temporali: DECISA il 2026-10-04.** **Tempo numerico
  internamente (JD tramite `astropy.time`), ISO 8601 solo nell'interfaccia e
  nei file**; **si dichiara sempre la scala di tempo**; i **MOC temporali
  usano la scala dello standard IVOA (da verificare)**. **Motivazione:** i
  calcoli insiemistici devono restare numerici e deterministici; la
  leggibilità la risolvono le conversioni di presentazione. Regola scritta in
  `02-convenzioni.md` DC1 (aggiornata). Applicata in §6/§9 qui sopra.
- **D16-4 — Mappe di probabilità: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** mappe LIGO/Virgo/KAGRA in
  HEALPix **piatte e multi-ordine** (sez. 8.1 del manuale di Aladin); somma
  delle probabilità verificata uguale a 1 entro una tolleranza dichiarata;
  regioni di credibilità calcolate con `mocpy` (funzione **da verificare prima
  del codice**).
- **D16-5 — Cataloghi HiPS progressivi (H12): DECISA il 2026-10-04, insieme
  a D12-5.** **Computazioni HEALPix nel `16`, servizio dei tile nel `12`**
  (stesso confine scritto in `12-core-hips.md`). **Motivazione:** due
  decisioni sullo stesso confine devono dare lo stesso risultato, altrimenti i
  due file si contraddicono; nessuna logica HEALPix duplicata. Applicata in
  §3 qui sopra.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). Perimetro da E6/H9/H12 di `03-parita-aladin.md`. |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario: D16-1, D16-2, D16-3 e D16-5 passate da aperte a decise.** D16-1: `mocpy` per MOC (spaziali e temporali), licenza e installazione su macOS da verificare prima dell'approvazione (§8). D16-2: MOC in cache in **FITS standard IVOA**, export anche JSON e testo (§4/§6/§7/§9). D16-3: tempo numerico interno (JD via `astropy.time`), ISO 8601 solo in interfaccia/file, scala sempre dichiarata, scala IVOA per i MOC temporali (da verificare) — regola in `02-convenzioni.md` DC1 (§6/§9). D16-5: computazioni HEALPix nel 16, servizio dei tile nel 12 (§3; pari a D12-5 in `12-core-hips.md`). Decisioni riportate in `decisioni-aperte.md`. |
| 2026-10-08 | Claude Code | §5: aggiunti a "Usato da" i moduli `19-core-dati-planetari.md` (scritti il 2026-10-08, stato bozza). Nessun altro testo cambia. |
| 2026-10-09 | Claude Code | **D19-3 applicata (decisione del proprietario del 2026-10-08):** campo `body` obbligatorio nei metadati di ogni MOC; operazioni e filtri solo tra lo stesso corpo (§6, §9, §10); per i dati astronomici `celestial`, ricavato dal sistema di coordinate, mai assunto; errori `BODY_UNKNOWN` e, per le sovrapposizioni, `BODY_MISMATCH` secondo D19-4 (forzabile solo con opzione esplicita citata nel risultato). |
| 2026-10-09 | Claude Code | **D16-4 DECISA** (checklist del livello 1): mappe LIGO/Virgo/KAGRA piatte e multi-ordine, somma verificata = 1, regioni di credibilità con `mocpy` (da verificare). |
| 2026-10-09 | Claude Code | **Completamento con gli esiti di AP5** (decisione del proprietario del 2026-10-09): §3, §6, §7, §8, §10, §12 per H22 (versioni MOC 1.0–2.1, FITS e JSON; supporto in `mocpy` da verificare) e H26 (filtro spaziale delle collezioni con il MocServer, client `astroquery.mocserver`). Nessuna nuova decisione dei Gruppi 1 e 2. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** (regola del proprietario del 2026-10-09): modulo completato con gli esiti di AP5, nessuna decisione aperta nei Gruppi 1 e 2. |
