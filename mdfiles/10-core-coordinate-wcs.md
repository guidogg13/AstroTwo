# 10-core-coordinate-wcs.md — coordinate, WCS, sistemi e epoche di riferimento

**Stato:** approvato

## 2. Scopo

Tradurre, convertire e rappresentare correttamente le posizioni celesti e la
geometria dei campi d'osservazione, così che ogni coordinata mostrata o usata
da AstroTwo sia determinista, con unità e sistema di riferimento sempre dichiarati.

## 3. Cosa fa

- **Conversioni tra sistemi di coordinate:** equatoriali (RA/Dec), galattiche
  (l, b), eclittiche e gli altri sistemi supportati da `astropy.coordinates`;
  conversioni anche tra epoche diverse (precessione/nutazione) sempre tramite
  Astropy, mai con formule scritte a mano.
- **Risoluzione dei nomi:** tradurre un nome di oggetto (es. "M31", "NGC 224",
  "Aldebaran") in coordinate, con fonte dichiarata (servizio SIMBAD via
  `astroquery`). Le risoluzioni si **cacheano** in una **tabella SQLite
  separata dentro la cache A7** (limite e provenienza unici, schema non
  condiviso con `13-core-cataloghi.md` — D10-3 decisa il 2026-10-04).
- **Letture e raffigurazioni:** coordinate del cursore nel campo visualizzato,
  griglia di coordinate sovrapposta, scelta della proiezione celeste del campo.
- **WCS (World Coordinate System):** leggere, validare e applicare la soluzione
  astrometrica (`WCS`) di un'immagine FITS: da pixel a coordinate e viceversa;
  verificare che la soluzione sia internally consistente.
- **Propagazione delle posizioni:** portare una posizione a un'epoca diversa
  usando moto proprio e parallasse (`apply_space_motion`). **L'epoca di ogni
  dato si legge dai suoi metadati e non si assume mai** (D10-2, decisa il
  2026-10-04): epoca di origine e moto proprio devono essere presenti o
  richiesti, altrimenti errore `EPOCH_REQUIRED`; **l'epoca usata è sempre
  scritta nel risultato**.
- **Calibrazione astrometrica (funzione H6 di `03-parita-aladin.md`):**
  determinare o rifinire la soluzione astrometrica di un'immagine e ricavare
  coordinate per tabelle prive di coordinate, usando sorgenti di riferimento.
  Procedura: i tre metodi manuali di Aladin (parametri, associazione di
  stelle, intestazione WCS) — D10-1, decisa il 2026-10-09 (§13).
- **Calcolatrice delle coordinate (A5):** strumento che, dati degli input
  (coordinate + sistema/epoca, o coordinate + offset angolari), restituisce il
  risultato della conversione richiesta con `astropy.coordinates`. Fa parte
  della conversione (A5) e resta qui; la **calcolatrice H4** (algebrica,
  unità, pixel, coordinate e tempo) è il modulo separato
  `18-core-calcolatrici.md` (accettato in AM1 il 2026-10-04), che per la
  parte coordinate/tempo richiama questo modulo.
- **Tutti i calcoli angolari interni sono in gradi `float64`**, con unità
  esplicite in ingresso e in uscita come da `02-convenzioni.md`.
- **Calibrazioni storiche (H25, sez. 8.2 del manuale di Aladin, ed. giugno 2022):**
  oltre alle soluzioni WCS standard si riconoscono le soluzioni astrometriche
  storiche delle lastre (metodo DSS1), come fa Aladin. Il supporto in
  `astropy.wcs` è **da verificare prima del codice**; se manca, la scelta di
  come trattarle diventa una decisione da registrare.
- **Convenzione dei pixel (H25, DC7):** le coordinate pixel interne sono in
  convenzione numpy; la conversione da e verso la convenzione FITS avviene
  solo con `convert_pixel_convention` (§7).
- Righe di `03-parita-aladin.md` coperte qui: A2 (vai a per nome, con
  `resolve_name`), A3 (vai a coordinate), A4 (coordinate del cursore), A5,
  A6 (griglia: calcolo delle linee; disegno nel 41), A9, H6, H25.

## 4. Cosa NON fa

- Non visualizza nulla: non disegna griglie, cursori né etichette (spetta a
  `41-ui-visualizzatore-cielo.md`).
- Non legge né scrive file FITS: la WCS viene accettata come oggetto, la
  gestione dei file è di `11-core-immagini-fits.md`.
- Non scarica né memorizza cataloghi: il download è di `14-core-protocolli-vo.md`,
  la cache dei cataloghi di `13-core-cataloghi.md`.
- Non fa cross-match (`15-core-crossmatch.md`), non misura distanze per utente
  (`17-core-misure.md`), non gestisce MOC (`16-core-moc.md`).
- Non calcola nulla con l'IA: ogni numero è prodotto da Astropy/ERFA.

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** nessuno (è il fondamento del livello 1).
- **Usato da:** `11-core-immagini-fits.md`, `12-core-hips.md`,
  `13-core-cataloghi.md`, `14-core-protocolli-vo.md`, `15-core-crossmatch.md`,
  `16-core-moc.md`, `17-core-misure.md`, `18-core-calcolatrici.md`,
  `19-core-dati-planetari.md`, tutti i moduli di analisi (20–24),
  `33-ia-query-adql.md`, `41-ui-visualizzatore-cielo.md`,
  `42-ui-pannello-cataloghi.md`.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `name` | stringa | nome di oggetto (es. "M31") | per la risoluzione nomi |
| in | `ra`, `dec` | float64 | gradi, ICRS J2000 | RA ∈ [0,360), Dec ∈ [−90,+90] |
| in | `l`, `b` | float64 | gradi, sistema galattico | l ∈ [0,360), b ∈ [−90,+90] |
| in | `frame` | enumerativo | nome frame Astropy (`icrs`, `galactic`, `ecliptic`, …) | sempre esplicito |
| in | `equinox` / `obstime` | epoca | anno giuliano (es. 2000.0) o data ISO 8601 | sempre dichiarati quando rilevanti |
| in | `pm_ra_cosdec`, `pm_dec`, `parallax` | float64 | mas/yr, mas | per la propagazione |
| in | `wcs` | oggetto WCS | — | soluzione astrometrica di un'immagine |
| in | `x`, `y` | float64 | pixel (origini dichiarate: 0 o 1) | da pixel a coordinate |
| out | coordinate convertite | float64 | gradi + sistema + epoca dichiarati | mai coordinate "nude" |
| out | `name → coordinate` | float64 | gradi, ICRS | con fonte e data della richiesta |
| out | residui calibrazione | float64 | arcosecondi | RMS/mediana dichiarati |

## 7. Interfaccia pubblica

Funzioni e classi (nomi proposti, descrizione in parole, nessun codice):

- **`SkyFrame`** (classe leggera): incapsula coordinate con sistema, epoca e
  unità; espone conversioni verso altri frame; non permette di creare
  coordinate senza unità.
- **`convert_coordinates(...)`** — converge coordinate tra frame e epoche;
  parametri: coordinate di origine, frame di partenza, frame/epoca di arrivo;
  restituisce coordinate con unità e frame di destinazione.
- **`resolve_name(name)`** — risolve un nome in coordinate ICRS; parametri:
  nome, opzione di fonte; restituisce coordinate + fonte + timestamp, o errore
  se non trovato o se la rete non risponde.
- **`wcs_from_header(header)`** / **`sky_to_pixel(...)`** / **`pixel_to_sky(...)`**
  — costruiscono la WCS da un header e fanno le trasformazioni in entrambe le
  direzioni.
- **`convert_pixel_convention(x, y, from_convention, to_convention)`** —
  **unico punto di conversione** tra la convenzione FITS (indice da 1) e la
  convenzione numpy (indice da 0) prevista da DC7 di `02-convenzioni.md`:
  `x_fits = x_numpy + 1`, `y_fits = y_numpy + 1` (e inverso), valori anche
  non interi; le convenzioni ammesse sono `fits` e `numpy`; restituisce le
  coordinate con la convenzione di arrivo dichiarata. Ricorda che l'indice
  di array è `array[y_numpy, x_numpy]`. Usata da tutti i moduli che mostrano,
  leggono o scrivono coordinate pixel (elenco in DC7); internamente le
  coordinate pixel sono sempre in convenzione numpy.
- **`propagate_position(...)`** — propaga una posizione a un'epoca target con
  moto proprio e parallasse; restituisce posizione all'epoca richiesta e
  dichiara l'epoca usata.
- **`astrometric_calibration(...)`** — determina/rifinisce la soluzione
  astrometrica (H6); restituisce soluzione + qualità (residui in arcosecondi).
  Implementazione: D10-1, decisa il 2026-10-09 (§13).
- **`coordinate_calculator(...)`** — calcolatrice coordinate (A5): conversioni
  e calcoli inversi; nessun calcolo fatto dal modello linguistico. Le altre
  calcolatrici (H4: algebrica, unità, pixel, tempo) vivono in
  `18-core-calcolatrici.md` (modulo accettato in AM1 il 2026-10-04), che
  richiama questa funzione per la parte coordinate.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `astropy.coordinates` | tutte le conversioni, precessione, propagazione con moto proprio | standard de facto, implementa le trasformazioni IAU |
| `astropy.units` | unità e `Quantity` ovunque | niente angoli senza unità |
| `astropy.wcs` | lettura/applicazione delle soluzioni WCS | standard di fatto per FITS WCS |
| `astropy.erfa` (via Astropy) | trasformazioni di riferimento a basso livello | librerie IAU verificate |
| `astroquery.simbad` | risoluzione dei nomi | servizio CDS ufficiale |
| Standard FITS WCS (paper I/IV) | struttura delle soluzioni | standard IAU/OHSA |

## 9. Regole e vincoli

- Sistema predefinito **ICRS**; **le epoche non si assumono mai**: si leggono
  dai metadati del dato (D10-2 decisa il 2026-10-04; regola in
  `02-convenzioni.md` DC2). Epoca di visualizzazione = **epoca dell'immagine se
  nota, altrimenti J2000**; ogni catalogo ha la propria epoca di riferimento;
  ogni output riporta l'epoca usata.
- Internamente gradi `float64`; nessun arrotondamento prima del display.
- Nessuna conversione scritta a mano: solo Astropy/ERFA (regola d'oro n. 4).
- Ogni output riporta frame, epoca e unità; un output senza frame è un errore.
- **Proiezioni celesti (D10-4 decisa il 2026-10-04):** stessa lista di
  proiezioni di Aladin secondo il manuale utente ed. giugno 2022 (sez. 5.14):
  `SIN`, `TAN`, `AIT`, `ZEA`, `STG`, `CAR`, `NCP`, `ZPN` (precisata il 2026-10-08; il manuale chiude l'elenco con
  "…": eventuali altre proiezioni **da verificare con la documentazione
  ufficiale**; supporto di `NCP` in `astropy.wcs` **da verificare**); default **`TAN` per le immagini** e **`AIT` per le viste a cielo
  intero**; **un test per proiezione** (§12).
- La risoluzione nomi è un'operazione di rete: timeout dichiarato, errore
  esplicito se offline; nessun nome risolto "approssimativamente"; i risultati
  si cacheano nella tabella SQLite separata della cache A7 (D10-3).
- Le conversioni devono essere deterministe e riproducibili: stesso input,
  stessa libreria, stesso output (test di round-trip in §12).
- Prestazioni: conversioni di massa (migliaia di posizioni) in tempi da
  misurare nei test di accettazione del modulo (valore: decisione D10-6,
  Gruppo 3, da fissare con `61-strategia-test.md`).

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Nome non trovato | nessuna coordinata prodotta, messaggio con il nome e la fonte interrogata | `NAME_NOT_FOUND` |
| Rete assente durante la risoluzione nomi | errore esplicito, nessun valore inventato | `NET_TIMEOUT` |
| Dec fuori [−90,+90] o RA fuori intervallo | rifiuto dell'input prima del calcolo | `COORD_OUT_OF_RANGE` |
| Header senza WCS o WCS incoerente | la WCS non viene costruita; l'immagine si apre solo come griglia di pixel | `WCS_MISSING` / `WCS_INVALID` |
| Conversione a un frame sconosciuto | errore con elenco dei frame supportati | `FRAME_UNSUPPORTED` |
| Epoca mancante dove richiesta (es. propagazione) | errore che chiede l'epoca: **l'epoca non si assume mai** (D10-2) | `EPOCH_REQUIRED` |
| Fuori campo (pixel → cielo) | valore restituito con avviso "fuori dal campo" | `OUT_OF_FIELD` |
| Convenzione pixel diversa da `fits` o `numpy`, o mancante | rifiuto: la convenzione non si assume | `PIXEL_CONVENTION_UNKNOWN` |
| Intestazione con soluzione storica (DSS1) non supportata dalla libreria | nessuna WCS costruita, l'immagine si apre come griglia di pixel con avviso che indica il tipo di soluzione | `WCS_LEGACY_UNSUPPORTED` |

## 11. Esposizione all'IA

Il modulo espone strumenti deterministici; **l'IA non calcola coordinate**:
propone i parametri e interpreta il risultato.

- **`resolve_name`** — input: nome oggetto; output: coordinate ICRS + fonte.
  Calcolo: SIMBAD via `astroquery`.
- **`convert_coordinates`** — input: coordinate, frame/epoca sorgente e target;
  output: coordinate convertite. Calcolo: `astropy.coordinates`.
- **`propagate_position`** — input: posizione, moto proprio, parallasse, epoca
  target; output: posizione all'epoca target. Calcolo: Astropy.
- **`wcs_pixel_to_sky`** — input: WCS + pixel; output: coordinate. Calcolo:
  `astropy.wcs`.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Round-trip ICRS → galattico → ICRS | convertire un campo di 1000 coordinate casuali con semina fissa in galattico e tornare a ICRS | scostamento massimo < 1e-9 gradi (limite numerico `float64`) | ricalcolo con `astropy.coordinates` nel test |
| T2 | Conversione nota | convertire le coordinate di una sorgente presa da SIMBAD (fonte scelta dal tester) da ICRS a galattico | coincidenza con il valore ricalcolato dallo stesso test con Astropy, entro 1e-9 gradi | confronto con `astropy.coordinates` + seconda lettura da SIMBAD |
| T3 | Round-trip pixel ↔ cielo | costruire la WCS da un header FITS di prova, passare da pixel a cielo e ritorno | errore < 1e-6 pixel | ricalcolo con `astropy.wcs` |
| T4 | Propagazione con moto proprio | propagare una posizione con moto proprio noto (valori presi dal tester da un catalogo Gaia) a un'epoca +10 anni | coincidenza con `SkyCoord.apply_space_motion` calcolata nel test | ricalcolo con Astropy |
| T5 | Risoluzione nome | `resolve_name("M31")` con rete disponibile | coordinate coerenti con quelle di SIMBAD entro la precisione dichiarata da SIMBAD | confronto incrociato con SIMBAD (dipende dalla rete: test separato, marcato di rete) |
| T6 | Input fuori range | passare Dec = 95° | errore `COORD_OUT_OF_RANGE`, nessun output numerico | test di unità |
| T7 | Una prova per proiezione (D10-4) | per ciascuna delle 8 proiezioni dell'elenco D10-4 (`SIN`, `TAN`, `AIT`, `ZEA`, `STG`, `CAR`, `NCP`, `ZPN`), convertire lo stesso campo pixel ↔ cielo | round-trip entro 1e-6 pixel per **ogni** proiezione; `TAN` di default per le immagini, `AIT` per le viste all-sky | ricalcolo con `astropy.wcs` per ciascuna proiezione |
| T8 | Convenzione dei pixel (DC7) | `convert_pixel_convention` su (1, 1) da `fits` a `numpy` e su (−0.5, −0.5) da `numpy` a `fits` | (0, 0) e (0.5, 0.5) | aritmetica esatta della regola DC7 |
| T9 | Round-trip delle convenzioni | 1000 coordinate pixel non intere (semina fissa) `numpy` → `fits` → `numpy` | identiche (differenza 0 in `float64` per valori rappresentabili) | test di unità |
| T10 | Coerenza con `astropy.wcs` | stessa posizione: `pixel_to_sky` in convenzione numpy (origine 0) e `wcs_pix2world` di `astropy.wcs` con origine 1 sulla coordinata convertita in FITS | stesse coordinate celesti entro 1e-12 gradi | ricalcolo con `astropy.wcs` |
| T11 | Convenzione non valida | `convert_pixel_convention` con convenzione `idl` o mancante | `PIXEL_CONVENTION_UNKNOWN` | test di unità |
| T12 | Calibrazione storica DSS1 (H25) | aprire un'intestazione DSS1 di prova e convertire alcuni pixel in coordinate | coordinate coincidenti con quelle di riferimento fornite con il file di prova; se la libreria non supporta il metodo, `WCS_LEGACY_UNSUPPORTED` | confronto con valori di riferimento (file di prova da individuare, **da verificare**) |

## 13. Decisioni aperte

- **D10-1 — Calibrazione astrometrica (H6): DECISA il 2026-10-09 (decisione
  del proprietario sulla checklist del livello 1).** I **tre metodi di
  Aladin** (manuale ed. giugno 2022, sez. 5.14): per **parametri** (posizione
  e pixel di riferimento, scala, proiezione, rotazione, verso dell'ascensione
  retta), per **associazione di stelle** (coppie pixel ↔ cielo con centroide
  baricentrico, soluzione con `astropy.wcs.utils.fit_wcs_from_points`) e per
  **intestazione WCS**; più soluzioni per immagine, annulla/ripeti. La
  risoluzione automatica "alla cieca" (es. astrometry.net) è un'estensione
  successiva, non prevista ora. **Da verificare prima del codice:** che
  `fit_wcs_from_points` copra le proiezioni dell'elenco D10-4 usate dalla
  calibrazione.
- **D10-2 — Epoca per la propagazione: DECISA il 2026-10-04.** L'epoca di
  ogni dato si legge dai suoi metadati e **non si assume mai**; epoca di
  visualizzazione = epoca dell'immagine se nota, altrimenti J2000; l'epoca
  usata è sempre scritta nel risultato; i cataloghi hanno ciascuno la propria
  epoca di riferimento. **Motivazione:** nessuna epoca implicita (regola
  d'oro n. 6, riproducibilità) e una sola convenzione di progetto (DC2 di
  `02-convenzioni.md`, aggiornata). Applicata in §3/§9/§10 qui sopra.
- **D10-3 — Risoluzione nomi offline: DECISA il 2026-10-04.** Cache in una
  **tabella SQLite separata dentro la cache A7** (limite e provenienza unici
  come richiede A7, schema non condiviso con `13-core-cataloghi.md`).
  **Motivazione:** confine netto con il 13 e vincolo A7 rispettato. Applicata
  in §3/§9 qui sopra.
- **D10-4 — Proiezioni supportate: DECISA il 2026-10-04.** Stessa lista di
  proiezioni di Aladin secondo il manuale utente ed. giugno 2022 (sez. 5.14):
  `SIN`, `TAN`, `AIT`, `ZEA`, `STG`, `CAR`, `NCP`, `ZPN` (precisata il 2026-10-08; il manuale chiude l'elenco con
  "…": eventuali altre proiezioni **da verificare con la documentazione
  ufficiale**; supporto di `NCP` in `astropy.wcs` **da verificare**), default **`TAN` per le immagini** e **`AIT` per le viste a cielo
  intero**,
  **un test per proiezione** (T7). **Motivazione:** la parità documentale è
  il minimo (P11) e il test per proiezione verifica `astropy.wcs` in modo
  sistematico. Applicata in §9/§12 qui sopra.
- **D10-5 — Sorgenti di riferimento per H6:** quale catalogo usare come
  riferimento (Gaia, ecc.) e con quali limiti di magnitudine.
- **D10-6 — Prestazioni delle conversioni di massa:** tempo massimo per
  convertire migliaia di posizioni (valore e test misurabile). Da fissare al
  momento del codice insieme a `61-strategia-test.md` (Gruppo 3).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario: D10-2, D10-3 e D10-4 passate da aperte a decise.** D10-2: epoca letta dai metadati, mai assunta, epoca di visualizzazione = epoca dell'immagine se nota altrimenti J2000, epoca sempre scritta nel risultato, cataloghi con propria epoca di riferimento (§3/§9/§10; regola in `02-convenzioni.md` DC2). D10-3: cache dei nomi in tabella SQLite separata dentro A7 (§3/§9). D10-4: stessa lista di proiezioni di Aladin (da verificare con AP5), `TAN` default immagini, `AIT` viste all-sky, un test per proiezione (§9/§12-T7). `13-core-cataloghi.md` allineato su epoche e DataLink; decisioni riportate in `decisioni-aperte.md`. |
| 2026-10-04 | agente di sviluppo | Riferimenti AP5 aggiornati in §3 e §13 (D10-4): le sezioni ancora da leggere sono **5.7.3–8** (prima indicate 5.9–8), in linea con l'esito parziale di AP5 in `03-parita-aladin.md` (lette 1–5.7.2 e indice completo, ed. febbraio 2021). Nessun altro testo cambia. |
| 2026-10-08 | Claude Code | §3 e §13 (D10-4): riferimento AP5 scritto in forma uniforme ("AP5 decisa; lettura delle sezioni 5.7.3–8 ancora da fare") con l'edizione del manuale (giugno 2022, AP6). Nessun altro testo cambia. |
| 2026-10-08 | Claude Code | §3 e §13 (D10-4): riferimento AP5 aggiornato a "AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) ancora da fare" (con l'ed. giugno 2022 le sezioni 1–5.8 risultano già lette). |
| 2026-10-08 | Claude Code | §3 e §13 (D10-4): riferimento AP5 aggiornato a lettura completata, con rimando all'elenco delle proiezioni trovato nel manuale (riga A9 di `03-parita-aladin.md`). La lista di D10-4 non è stata cambiata. |
| 2026-10-08 | Claude Code | **D10-4 precisata (decisione del proprietario):** lista delle proiezioni = quella del manuale di Aladin ed. giugno 2022, sez. 5.14 (`SIN`, `TAN`, `AIT`, `ZEA`, `STG`, `CAR`, `NCP`, `ZPN`); resta un test per proiezione (T7, ora con l'elenco esplicito). Da verificare: eventuali proiezioni oltre l'elenco (il manuale chiude con "…") e il supporto di `NCP` in `astropy.wcs`. Testo aggiornato in §3 e §13. |
| 2026-10-08 | Claude Code | §5: aggiunti a "Usato da" i moduli `18-core-calcolatrici.md` e `19-core-dati-planetari.md` (scritti il 2026-10-08, stato bozza). Nessun altro testo cambia. |
| 2026-10-09 | Claude Code | §7: nuova funzione `convert_pixel_convention`, unico punto di conversione FITS (indice da 1) ↔ numpy (indice da 0) previsto da DC7 (confermata dal proprietario il 2026-10-08); §10: errore `PIXEL_CONVENTION_UNKNOWN`; §12: test T8–T11. |
| 2026-10-09 | Claude Code | **D10-1 DECISA** (checklist del livello 1): i tre metodi di calibrazione di Aladin (parametri, associazione di stelle con `fit_wcs_from_points`, intestazione WCS); risoluzione automatica rimandata; verifica sulle proiezioni prima del codice. §3, §7 aggiornati. Nuova **D10-6** (prestazioni delle conversioni di massa, Gruppo 3) al posto del rinvio senza etichetta in §9. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-09. |
| 2026-10-09 | Claude Code | Completamento dalla verifica di copertura di `03-parita-aladin.md` (decisione del proprietario del 2026-10-09): §3 calibrazioni storiche DSS1 (H25, supporto in `astropy.wcs` da verificare prima del codice), convenzione dei pixel (H25/DC7) e righe di parità coperte (A2–A6, A9, H6, H25); §10 errore `WCS_LEGACY_UNSUPPORTED`; §12 nuovo test. Nessuna nuova decisione dei Gruppi 1 e 2: stato `approvato` invariato. |
