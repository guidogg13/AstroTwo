# 19-core-dati-planetari.md — dati planetari: superfici, cataloghi, coperture e sistemi di riferimento planetari

**Stato:** approvato

## 2. Scopo

Permettere di cercare, caricare e sovrapporre dati di corpi del Sistema
solare (superfici, cataloghi, coperture) con il corpo e il sistema di
riferimento planetario sempre dichiarati, senza mai mescolarli con dati
celesti o di un altro corpo.

## 3. Cosa fa

Origine: riga **H21** di `03-parita-aladin.md` (manuale utente di Aladin ed.
giugno 2022, sez. 5.21 "dati planetari", 7.2 opzione `-[no]planet`, 8.1
formati PDS ed EpnTAP); modulo accettato in AM1 il 2026-10-08. In Aladin
questi dati sono forniti "as is", senza garanzia di coerenza della
visualizzazione, e una sovrapposizione dubbia produce solo un avviso.
AstroTwo applica regole più severe (§9).

1. **Corpo di riferimento.** Ogni dato planetario porta il **corpo** a cui si
   riferisce (es. Luna, Marte). Il corpo **si legge dai metadati del dato e
   non si assume mai**, come l'epoca per i dati celesti (DC2 di
   `02-convenzioni.md`). Da quali metadati si legge per ogni tipo di dato:
   regola D19-3 (decisa il 2026-10-08): `body` è un campo obbligatorio nei
   metadati dei moduli 12, 13, 14 e 16; per i dati astronomici vale
   `celestial`, ricavato dal sistema di coordinate, mai assunto. I nomi delle
   proprietà negli standard (HiPS, EPN-TAP, MOC) sono **da verificare**. Se il
   corpo non si può determinare, il dato si può aprire da
   solo ma non sovrapporre ad altri (`BODY_UNKNOWN`).
2. **Sistemi di riferimento planetari.** Coordinate di superficie
   (longitudine e latitudine) nel sistema del corpo dichiarato, con
   convenzioni sempre esplicite: latitudine **planetocentrica** o
   **planetografica**, longitudine **positiva verso est** o **verso ovest**,
   intervallo della longitudine. Conversioni tra queste convenzioni con una
   libreria consolidata (§13, D19-1); forma e orientamento dei corpi dal
   rapporto IAU WGCCRE, letti dalla libreria e mai scritti a mano.
3. **Superfici planetarie (HiPS).** Elenco e caricamento dei HiPS di
   superfici planetarie tramite `12-core-hips.md`, con il corpo dichiarato;
   proiezioni e calcoli HEALPix restano nei moduli 10, 12 e 16.
4. **Cataloghi planetari.** Tabelle con posizioni in coordinate planetarie
   caricate tramite `13-core-cataloghi.md`; interrogazioni ai servizi
   **EPN-TAP** (TAP con lo schema EPN-TAP) tramite `14-core-protocolli-vo.md`.
   Le colonne di posizione si riconoscono dai metadati; se mancano corpo o
   convenzione, errore.
5. **Coperture planetarie (MOC).** Coperture sulla superficie di un corpo
   tramite `16-core-moc.md`, con il corpo dichiarato. Il supporto dei MOC
   planetari in `mocpy` e nello standard IVOA è **da verificare** (D19-7).
6. **Immagini PDS.** Lettura delle immagini nel formato del Planetary Data
   System (formato da leggere per la parità, riga H21); versioni del formato,
   letta **in questo modulo** (D19-2, decisa il 2026-10-08): **PDS4
   obbligatorio**; PDS3 solo se esiste una libreria consolidata; libreria e
   licenza da verificare (§13, D19-2b).
7. **Ramo "Sistema solare".** Classifica le collezioni disponibili per corpo,
   così che l'albero delle collezioni (`41-ui-visualizzatore-cielo.md`) possa
   mostrarle in un ramo dedicato.
8. **Controllo di coerenza delle sovrapposizioni.** Prima di sovrapporre due
   livelli, confronta i loro corpi: **dati celesti e planetari, o di corpi
   diversi, non si sovrappongono** (`BODY_MISMATCH`). Un'eventuale forzatura
   da parte dell'utente è possibile **solo con un'opzione esplicita, citata nel
   risultato** (D19-4, decisa il 2026-10-08; stesso schema di D13-5).
9. **Attivazione.** L'accesso ai dati planetari è un'opzione delle
   preferenze (`40-ui-finestra-principale.md`); **disattivato per default**
   (D19-5, decisa il 2026-10-09; motivazione nostra in §13).

### Decisioni del proprietario del 2026-10-13, verifiche di P0 e divisione in parti

**Divisione in parti (approvata dal proprietario il 2026-10-13):**

| Parte | Contenuto | Test |
|---|---|---|
| P0 | verifiche prima del codice (licenze e installazione di `spiceypy`, kernel PCK, `pds4_tools`, `pdr`; nome della proprietà del corpo nei HiPS; schema EPN-TAP; nessun sistema solidale ai corpi in astropy); nuove dipendenze in `THIRD_PARTY_LICENSES` | — |
| P1 | `PlanetaryBody`, tabella dei nomi (D12-6), `body_of`, `check_overlay` con forzatura esplicita, opzione disattivata per default (D19-5) | T1, T2, T3, T9, T11 |
| P2 | `PlanetaryPosition`, `convert_planetary_coordinates` con `spiceypy` (est/ovest, planetocentrica/planetografica) | T4, T5, T6, T10 |
| P3 | `list_planetary_collections` (tramite il 12) e `query_epntap` (tramite il 14) | T7 |
| P4 | `load_pds_image`: PDS4 con `pds4_tools`, anche da URL (D19-9); PDS3 non ancora supportato (D19-8 rimandata) | T8 |

**Codice: `src/astrotwo/core/planetary_data.py`**, errori `PlanetaryDataError`
con gli identificatori di §10 (gli errori dei moduli 12, 13, 14 passano con
lo stesso identificatore).

**Esiti delle verifiche di P0 (2026-10-13):**

1. **`spiceypy` 8.3.0** (Andrew Annex): licenza **MIT** (file di licenza
   del pacchetto); ruote per macOS arm64 e x86_64, installata con `uv`;
   include il **toolkit CSPICE N0067** della NAIF. Regole d'uso della NAIF
   (pagina "Rules Regarding Use of SPICE", letta il 2026-10-13): uso anche
   commerciale ammesso senza licenze né costi; includere i moduli del
   toolkit in un programma che li usa è ammesso; si riporta la clausola di
   esclusione di garanzia di Caltech/JPL/NASA. Unica dipendenza: `numpy`.
   `bodn2c`/`bodc2n` funzionano con la tabella dei nomi interna del
   toolkit, senza kernel.
2. **Kernel PCK della NAIF:** **`pck00011.tpc`** (NAIF, 27 dicembre 2022,
   basato sul rapporto IAU WGCCRE 2015, Archinal et al. 2018), il più
   recente dei PCK generici, compatibile con il toolkit N0067. **Incluso nel
   progetto senza modifiche** in `src/astrotwo/core/data/naif/pck00011.tpc`
   (SHA-256 `3dff7b1dbeceaa01f25467767d3fa25816051c85d162d1edf04acb310ee28bb1`,
   controllato a ogni caricamento: diverso → `PLANETARY_KERNEL_INVALID`),
   scaricato una sola volta da
   `https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/` per la
   verifica; **nessuna rete** in esecuzione. Regole NAIF: la
   ridistribuzione dei kernel della NAIF è ammessa se **non modificati**.
3. **`pds4_tools` 1.4** (Small Bodies Node, University of Maryland):
   licenza **BSD-3-Clause**; pacchetto Python puro (dipende da `numpy`),
   installato con `uv`. **Non contiene file PDS di esempio**: T8 usa un
   prodotto PDS4 generato nel test (etichetta XML + dati binari) e confronta
   i valori con quelli letti da `pds4_tools` e con i valori scritti.
   Verifica del comportamento: `scaling_factor` e `value_offset`
   dell'`Element_Array` applicati da `pds4_tools`; le costanti speciali
   (`missing_constant`…) restano col valore grezzo non scalato
   nell'array, mascherate da `as_masked()`.
4. **`pdr` 1.4.4** (Million Concepts): licenza **BSD-3-Clause**,
   pacchetto Python puro, ultima versione del 2026-06-24 (mantenuto), ma
   **classificato "Beta"** dagli autori e con dipendenze in più (`pandas`,
   `dustgoggles`, `multidict` Apache-2.0, `rms-vax` Apache-2.0); include una
   propria copia di `pds4_tools`. La verifica **non basta da sola** a dire
   che sia una "libreria consolidata" (D19-2): `pdr` non aggiunto alle
   dipendenze; **PDS3 rimandato** (D19-8, decisione del proprietario del
   2026-10-13, bassa priorità): un'etichetta PDS3 dà un errore esplicito
   "formato PDS3 non ancora supportato".
5. **Corpo nei HiPS:** proprietà **`hips_body`** (Working Draft HiPS 2.0,
   già verificata con il 12 il 2026-10-12). MocServer, 2026-10-13: 78 HiPS
   con `hips_frame` non celeste; i valori di `hips_body` sono in
   **minuscolo** e uguali a `hips_frame` (`mars`, `moon`, `ceres`…); 13 HiPS
   di Marte hanno `hips_frame = mars` senza `hips_body`; tre valori non
   sono corpi (`mars-pia20284`, `mars-stimson`, `moon-pan1`: nessun codice
   NAIF).
6. **EPN-TAP 2.0** (Raccomandazione IVOA del 22 agosto 2022, letta il
   2026-10-13): tabella `<schema>.epn_core`; corpo nel parametro
   obbligatorio **`target_name`** (con `target_class`); tipo di sistema in
   **`spatial_frame_type`** (obbligatorio): con `body`, `c1` = longitudine,
   `c2` = latitudine, **planetocentriche**, **longitudine positiva verso est
   in (0, 360)°** (convenzione IAU 2009), sistema IAU corrente salvo
   diversa indicazione in `spatial_coordinate_description`; con `celestial`
   ascensione retta e declinazione (ICRS di default).
7. **Astropy 8.0.1:** i 28 sistemi del grafo delle trasformazioni sono
   celesti, terrestri (`itrs`, `altaz`, `hadec`) o eclittici; **nessun
   sistema solidale a un altro corpo**: la scelta di `spiceypy` (D19-1)
   resta necessaria.

**Tabella dei nomi dei corpi (D12-6, approvata il 2026-10-13):** nome
canonico = **nome IAU in inglese con l'iniziale maiuscola**;
normalizzazione di un nome scritto (anche in minuscolo, come nei HiPS) con
**`spiceypy.bodn2c` → identificativo NAIF → nome canonico** della tabella.
Nella tabella **solo i corpi con un HiPS nel MocServer e presenti nel
kernel PCK** (D19-6; verificato il 2026-10-13: raggi `RADII` e meridiano `PM`
presenti per tutti), **Luna e Marte obbligatori** per i test;
**`celestial` non è un corpo** (D19-3) e non si normalizza. Nome fuori
tabella o senza codice NAIF → `BODY_UNSUPPORTED` con l'elenco.

| NAIF | Nome canonico | NAIF | Nome canonico | NAIF | Nome canonico | NAIF | Nome canonico |
|---|---|---|---|---|---|---|---|
| 10 | Sun | 501 | Io | 603 | Tethys | 703 | Titania |
| 199 | Mercury | 502 | Europa | 604 | Dione | 704 | Oberon |
| 299 | Venus | 503 | Ganymede | 605 | Rhea | 705 | Miranda |
| 399 | Earth | 504 | Callisto | 606 | Titan | 801 | Triton |
| 301 | Moon | 599 | Jupiter | 608 | Iapetus | 899 | Neptune |
| 499 | Mars | 601 | Mimas | 701 | Ariel | 901 | Charon |
| 2000001 | Ceres | 602 | Enceladus | 702 | Umbriel | 999 | Pluto |

La tabella si applica anche al **12** (`_body` di `hips.py`): `hips_body`
normalizzato al nome canonico; valore fuori tabella → `body = None` con
l'avviso `BODY_UNSUPPORTED` (il dato si apre da solo).

**Scelte minori (proposte da Claude Code il 2026-10-13, confermate tutte dal proprietario il 2026-10-13):**

1. **Opzione D19-5:** stato del modulo (`set_planetary_data_enabled`,
   `planetary_data_enabled`), **spento all'avvio**; l'impostazione delle
   preferenze del 40 lo accende. Con l'opzione spenta, ogni funzione che
   tocca dati planetari dà `PLANETARY_DATA_DISABLED`; restano attivi solo
   `normalize_body_name` (lettura dei metadati del 12) e `body_of` /
   `check_overlay` **quando tutti i livelli sono celesti** (il livello 1
   celeste funziona come sempre). **Ordine dei controlli in `check_overlay`
   (decisione del proprietario del 2026-10-21, sprint 4f del 41):** con due o
   più livelli di corpi diversi (o celeste + planetario) e senza forzatura
   l'esito è **sempre `BODY_MISMATCH`** con i corpi coinvolti, anche con
   l'opzione spenta: l'errore dice che cosa non va; l'opzione si controlla
   solo quando la sovrapposizione passerebbe (stesso corpo planetario, o
   forzatura), e allora con l'opzione spenta → `PLANETARY_DATA_DISABLED`.
2. **`PlanetaryBody.from_name(name)`:** nome normalizzato con la tabella,
   identificativo NAIF, raggi `RADII` (km) letti dal kernel con
   `bodvrd`, fonte (`pck00011.tpc`, SHA-256, `spiceypy` e CSPICE con le
   versioni); nessun altro modo di crearlo.
3. **`body_of(dataset)`:** `HiPSService` (12), `CatalogTable` (13),
   `Moc` (16), `FitsImage` (11: `celestial` solo con un WCS celeste),
   `PdsImage` (19); restituisce `celestial` o il nome canonico; corpo
   assente o non normalizzabile → `BODY_UNKNOWN` (con il motivo); MOC misto
   (`mixed`) → `BODY_MISMATCH` (più corpi in un livello).
4. **`check_overlay(layers, force=False)`:** un solo livello → sempre
   compatibile (anche senza corpo: il dato si apre da solo); due o più:
   corpo ignoto → `BODY_UNKNOWN` (non forzabile); corpi diversi o celeste +
   planetario → `BODY_MISMATCH` con i corpi coinvolti, oppure, con
   `force=True`, esito `OverlayCheck` con l'avviso `BODY_MISMATCH_FORCED`,
   i corpi e il **comando registrato** con `force=True`.
5. **Conversioni (P2):** latitudine planetocentrica ↔ planetografica con
   `spiceypy` sullo **sferoide** del kernel (raggio equatoriale `RADII[0]`,
   polare `RADII[2]`, schiacciamento `(RADII[0] − RADII[2]) / RADII[0]`;
   per i corpi triassiali il secondo raggio equatoriale non entra, scritto
   nel risultato): planetocentrica → punto della superficie con `surfpt`
   lungo la direzione (`latrec`) → `recpgr`; planetografica → `pgrrec` a
   quota 0 → `reclat`. Il verso della longitudine (est ↔ ovest) è una
   **definizione** (λ_ovest = (360° − λ_est) mod 360°), non un modello: si
   applica così, e il test la confronta con la longitudine planetografica di
   `recpgr` per un corpo a rotazione prograda (Marte, dove è positiva verso
   ovest). Longitudine in ingresso in [−180°, 360°], in uscita in
   **[0°, 360°)** (dichiarato); fuori → `COORD_OUT_OF_RANGE`.
6. **Comandi registrati:** ogni risultato porta il comando
   (`PlanetaryCommand`, funzione e argomenti) rieseguibile con
   `run_command`, come nel 18 (T10).
7. **`list_planetary_collections(body=None, *, index)`:** usa la copia
   locale delle collezioni del 12 (`CollectionIndex`, già sincronizzata dal
   chiamante; nessuna rete qui); corpo di ogni collezione con la stessa
   regola del 12 (`hips_frame` non celeste e `hips_body` uguale, poi
   tabella dei nomi); senza `body` → dizionario corpo → collezioni (ramo
   "Sistema solare"); collezioni con corpo ignoto elencate a parte.
8. **`query_epntap(service, adql, ...)`:** ADQL su una tabella
   `epn_core` (altrimenti `ADQL_INVALID`), eseguita con `tap_query` del 14;
   corpo della tabella = nome canonico di `target_name` se tutte le righe
   hanno lo stesso corpo e `spatial_frame_type = body` (convenzioni
   dichiarate nei metadati della tabella: planetocentrica, est, 0–360°,
   fonte EPN-TAP 2.0); tutte `celestial` → `celestial`; altrimenti (corpi o
   tipi diversi, colonne mancanti) → `body = None` con `BODY_UNKNOWN` e il
   motivo (la tabella si apre da sola).
9. **`load_pds_image(source, *, structure=None)`:** percorso locale
   dell'etichetta PDS4 (`.xml`); immagini = strutture `Array_2D*` lette con
   `pds4_tools`; più immagini senza `structure` →
   `PDS_STRUCTURE_CHOICE_REQUIRED` con l'elenco; valori fisici in `float64`
   (scala dell'etichetta applicata da `pds4_tools`), costanti speciali →
   NaN (maschera di `as_masked`), il conteggio nel risultato; corpo da
   `Target_Identification/name` normalizzato (più corpi o nessuno →
   `body = None` con `BODY_UNKNOWN`). **Da URL (D19-9, decisa il
   2026-10-13):** solo `http(s)`; si scarica l'etichetta e poi **tutti i
   file nominati** in `File/file_name`, **dalla stessa cartella dell'URL**
   (un nome con `/`, `\`, `..` o che inizia con `.` → `PDS_UNREADABLE`: si
   scarica solo dalla cartella dell'etichetta), con la rete del 14
   (`_http`, timeout comuni, `refresh`) e la **cache comune** (04, tabella
   delle risposte del 14); i file si scrivono in una cartella temporanea
   cancellata dopo la lettura; nel risultato `origin` = URL, `downloads` =
   (URL, data di scaricamento, da cache) di ogni file e l'avviso
   `PDS_DOWNLOADED`; errori di rete del 14 con lo stesso identificatore
   (`NET_TIMEOUT`, `SERVICE_ERROR`…). `cache`, `refresh`, `timeouts` come
   nel 14. **PDS3** (locale o da URL): `PDS_UNREADABLE` "formato PDS3 non
   ancora supportato" (D19-8 rimandata).

## 4. Cosa NON fa

- Non calcola posizioni o effemeridi dei corpi del Sistema solare nel cielo
  (oggetti sulla sfera celeste, es. il servizio SkyBot della riga H10: modulo
  `14-core-protocolli-vo.md`).
- Non fa geometria di missione (puntamenti di sonde, angoli di illuminazione
  e di vista, kernel di missione).
- Non fa analisi scientifica di superfici (geologia, correzioni fotometriche,
  modelli di terreno) né viste 3D (`53-avanzate-vista-3d.md`).
- Non gestisce le coordinate celesti: restano in `10-core-coordinate-wcs.md`.
- Non scarica né mette in cache da sé: rete e cache sono dei moduli 12, 13,
  14 e 16 (cache A7).
- Non genera HiPS o MOC planetari (H9: moduli 12 e 16).
- Non disegna nulla: albero, vista e avvisi sono dei moduli 40–42.
- Non usa l'IA per stabilire il corpo di un dato o convertire coordinate.

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `10-core-coordinate-wcs.md` (proiezioni, WCS, conversione
  dei pixel DC7), `11-core-immagini-fits.md` (immagini già lette; la
  lettura PDS è in questo modulo, D19-2), `12-core-hips.md` (HiPS planetari),
  `13-core-cataloghi.md` (tabelle), `14-core-protocolli-vo.md` (EPN-TAP),
  `16-core-moc.md` (coperture).
- **Usato da:** `40-ui-finestra-principale.md` (opzione nelle preferenze),
  `41-ui-visualizzatore-cielo.md` (ramo "Sistema solare", controllo delle
  sovrapposizioni), `42-ui-pannello-cataloghi.md` (cataloghi planetari),
  `32-ia-registro-strumenti.md` (strumenti per l'IA).

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `body` | stringa | nome IAU del corpo | letto dai metadati, mai assunto |
| in | `lon`, `lat` | float64 | gradi | con convenzione di latitudine e di longitudine dichiarate; lat ∈ [−90, +90] |
| in | `latitude_type` | enumerativo | `planetocentric` / `planetographic` | obbligatorio |
| in | `longitude_direction` | enumerativo | `east` / `west` positiva | obbligatorio |
| in | collezione HiPS, tabella, MOC | oggetti dei moduli 12, 13, 16 | come nei moduli di origine | con corpo dichiarato |
| in | query EPN-TAP | stringa ADQL + servizio | standard EPN-TAP | eseguita dal modulo 14 |
| in | file PDS | percorso o URL `http(s)` (D19-9) | PDS4 (obbligatorio); PDS3 non ancora supportato (D19-8 rimandata) | da URL: etichetta + file nominati nella stessa cartella |
| out | coordinate planetarie convertite | float64 | gradi + corpo + convenzioni dichiarati | mai coordinate "nude" |
| out | esito del controllo di sovrapposizione | struttura | compatibile / errore con i corpi coinvolti | |
| out | elenco delle collezioni per corpo | lista | identificativi e proprietà delle collezioni | per il ramo "Sistema solare" |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole (nessun codice). File Python previsto:
`src/astrotwo/core/planetary_data.py`.

- **`PlanetaryBody`** (classe): nome IAU del corpo e costanti di forma e
  rotazione lette dalla libreria scelta (D19-1); non si crea senza fonte
  (`from_name`, §3 scelta 2).
- **`normalize_body_name(name)`** — nome canonico della tabella dei corpi
  (D12-6, §3), usato anche dal 12.
- **`set_planetary_data_enabled(flag)`**, **`planetary_data_enabled()`** —
  opzione D19-5 (§3 scelta 1).
- **`PlanetaryPosition`** (classe): longitudine, latitudine, corpo e
  convenzioni; non si crea senza corpo e convenzioni.
- **`body_of(dataset)`** — restituisce il corpo dichiarato nei metadati di un
  HiPS, di una tabella, di un MOC o di un'immagine, oppure `BODY_UNKNOWN`.
- **`convert_planetary_coordinates(position, latitude_type,
  longitude_direction)`** — cambia convenzione di latitudine e/o longitudine
  con la libreria scelta; restituisce una nuova `PlanetaryPosition`.
- **`check_overlay(layers, force)`** — verifica che tutti i livelli abbiano lo stesso
  corpo (o siano tutti celesti); restituisce esito o errore.
- **`list_planetary_collections(body)`** — collezioni disponibili per corpo,
  dai metadati delle collezioni (moduli 12 e 14).
- **`query_epntap(service, query)`** — prepara e passa al modulo 14 una query
  EPN-TAP; restituisce la tabella con corpo e convenzioni dichiarati.
- **`load_pds_image(source)`** — legge un'immagine PDS4 da percorso o da URL
  (D19-9) in questo modulo; restituisce immagine, metadati, corpo e, da URL,
  origine e data di ogni file; PDS3 non ancora supportato (D19-8).

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| Rapporto IAU WGCCRE (coordinate cartografiche ed elementi di rotazione) | forma, orientamento e convenzioni dei corpi | riferimento ufficiale della comunità planetaria |
| EPN-TAP (standard IVOA) | interrogazioni ai servizi planetari | standard del Virtual Observatory planetario |
| HiPS (standard IVOA) | superfici planetarie | stesso formato dei HiPS celesti; metadati del corpo **da verificare** nello standard |
| MOC (standard IVOA) | coperture planetarie | supporto planetario **da verificare** (D19-7) |
| Formato PDS (Planetary Data System) | immagini planetarie | formato standard degli archivi planetari della NASA |
| `spiceypy` 8.3.0 (MIT, con il toolkit CSPICE N0067 della NAIF) + kernel PCK `pck00011.tpc` della NAIF incluso nel progetto (D19-1) | nomi e identificativi NAIF, raggi, conversioni di latitudine | verificati il 2026-10-13 (§3, P0); avvisi in `THIRD_PARTY_LICENSES` |
| `pds4_tools` 1.4 (BSD-3-Clause) (D19-2b) | lettura delle immagini PDS4 | verificato il 2026-10-13 (§3, P0) |
| `pdr` (PDS3) (D19-2b) | lettura PDS3 | verificato il 2026-10-13 ma **non adottato**: PDS3 rimandato (D19-8, bassa priorità) |
| Rete del 14 (`vo_protocols._http`, `_store`) e cache comune (04) | PDS4 da URL (D19-9) | una sola implementazione della rete e della cache |
| `astropy.units` | unità di angoli e distanze | regola d'oro n. 4 |

## 9. Regole e vincoli

- **Il corpo non si assume mai:** si legge dai metadati; senza corpo il dato
  non si sovrappone a nessun altro.
- **Nessuna sovrapposizione tra corpi diversi né tra dati celesti e planetari**
  per default (errore, non avviso); forzatura solo con un'opzione esplicita,
  citata nel risultato e nel comando registrato (D19-4, stesso schema di D13-5).
- Convenzioni di latitudine e longitudine **sempre dichiarate** in ingresso e
  in uscita; nessuna convenzione implicita.
- Costanti dei corpi (raggi, poli, meridiani) dalla libreria scelta e dal
  rapporto IAU WGCCRE, mai scritte a mano; la fonte e la sua versione sono
  riportate nel risultato.
- Calcoli in `float64`, unità esplicite (`02-convenzioni.md`); coordinate
  pixel secondo DC7.
- Rete: ogni accesso passa dai moduli 12, 13, 14 e 16 con i loro timeout ed
  errori; nessun dato inventato se la rete manca.
- **L'IA non calcola mai** (regola d'oro n. 1): corpo e coordinate vengono
  dai metadati e dalla libreria.
- Ogni operazione è registrata come comando rieseguibile (regola d'oro n. 6).
- Se l'opzione dei dati planetari è disattivata, le funzioni di questo modulo
  rispondono con un errore esplicito e il livello 1 celeste funziona come
  sempre.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Corpo assente o non leggibile nei metadati | il dato si apre da solo, non si sovrappone | `BODY_UNKNOWN` |
| Sovrapposizione di corpi diversi o di dati celesti e planetari | sovrapposizione rifiutata, con i corpi coinvolti | `BODY_MISMATCH` |
| Corpo non supportato dalla libreria scelta | rifiuto con l'elenco dei corpi supportati | `BODY_UNSUPPORTED` |
| Convenzione di latitudine o longitudine mancante | rifiuto: la convenzione non si assume | `PLANETARY_CONVENTION_REQUIRED` |
| Latitudine fuori [−90, +90] | rifiuto prima del calcolo | `COORD_OUT_OF_RANGE` |
| File PDS illeggibile o versione non supportata (PDS3: "formato PDS3 non ancora supportato", D19-8); da URL, file nominato fuori dalla cartella dell'etichetta o schema diverso da `http(s)` | nessuna immagine aperta | `PDS_UNREADABLE` |
| PDS4 da URL: file non raggiungibile o risposta HTTP di errore (D19-9) | nessuna immagine aperta; errore del 14 inoltrato | `NET_TIMEOUT`, `SERVICE_ERROR` |
| Servizio EPN-TAP non raggiungibile | errore del modulo 14 inoltrato | `NET_TIMEOUT` |
| Pixel con costanti speciali PDS4 (`missing_constant`…) | NaN nell'immagine, conteggio nel risultato | avviso `PDS_SPECIAL_CONSTANTS` |
| Opzione dei dati planetari disattivata | rifiuto; testo "i dati planetari non sono disponibili in questa versione" finché la preferenza non esiste (nessuna nella v1; decisione del proprietario del 2026-10-21) | `PLANETARY_DATA_DISABLED` |
| Più immagini nel prodotto PDS4 senza `structure` | rifiuto con l'elenco delle strutture | `PDS_STRUCTURE_CHOICE_REQUIRED` |
| Kernel PCK incluso alterato (SHA-256 diverso) | nessuna costante dei corpi | `PLANETARY_KERNEL_INVALID` |
| Query EPN-TAP non rivolta a una tabella `epn_core` | rifiuto prima della rete | `ADQL_INVALID` |
| Sovrapposizione forzata con l'opzione esplicita | eseguita; il risultato e il comando registrato citano la forzatura e i corpi coinvolti | avviso `BODY_MISMATCH_FORCED` |

## 11. Esposizione all'IA

L'IA può cercare dati planetari e chiedere conversioni; non stabilisce mai il
corpo di un dato né calcola coordinate.

- **`list_planetary_collections`** — input: corpo; output: collezioni con i
  loro metadati. Calcolo: nessuno (lettura di metadati).
- **`query_epntap`** — input: servizio, query; output: tabella con corpo e
  convenzioni. Esecuzione: modulo 14.
- **`convert_planetary_coordinates`** — input: posizione con corpo e
  convenzioni, convenzioni di arrivo; output: posizione convertita. Calcolo:
  libreria scelta (D19-1).
- **`check_overlay`** — input: livelli; output: esito. Calcolo: confronto
  dei metadati.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Corpo diverso | sovrapporre un HiPS di superficie lunare e un HiPS di Marte (dati di prova) | `BODY_MISMATCH` | test di unità |
| T2 | Celeste e planetario | sovrapporre un catalogo celeste a un HiPS di Marte | `BODY_MISMATCH` | test di unità |
| T3 | Corpo mancante | dato planetario di prova senza corpo nei metadati | `BODY_UNKNOWN`; il dato si apre da solo | test di unità |
| T4 | Longitudine est ↔ ovest | convertire longitudini note da positive a est a positive a ovest e ritorno | ritorno al valore iniziale; valore intermedio come calcolato dalla libreria scelta | ricalcolo con la libreria di D19-1 |
| T5 | Latitudine planetocentrica ↔ planetografica | convertire una latitudine scelta dal tester per un corpo con schiacciamento noto | coincide con la libreria di D19-1 e con la definizione sulla superficie dello sferoide tan φg = tan φc / (1 − f)² entro 1e-9 gradi; ritorno entro 1e-9 gradi | ricalcolo con la libreria e con la definizione |
| T6 | Convenzione mancante | posizione senza tipo di latitudine | `PLANETARY_CONVENTION_REQUIRED` | test di unità |
| T7 | EPN-TAP e collezioni | query EPN-TAP su un servizio simulato (un corpo; corpi diversi; `celestial`; tabella non `epn_core`; servizio irraggiungibile); collezioni per corpo da una copia locale del 12 | tabella con corpo e convenzioni dichiarati (planetocentrica, est, 0–360°); corpi diversi → `body = None` con `BODY_UNKNOWN`; `ADQL_INVALID` senza rete; `NET_TIMEOUT` del 14; collezioni raggruppate per nome canonico, corpi ignoti a parte | servizio simulato (test di rete separati per i servizi reali) |
| T8 | Immagine PDS | leggere un file PDS4 di esempio (`pds4_tools` non ne fornisce: prodotto generato nel test, §3 P0 punto 3); più immagini, più corpi, PDS3, file illeggibile; **da URL (D19-9)** con un server HTTP locale: prima lettura, seconda dalla cache, `refresh`, PDS3 da URL, file fuori dalla cartella, file di dati mancante, servizio non raggiungibile | immagine aperta con metadati del corpo; valori uguali a quelli letti dalla libreria; da URL valori uguali alla lettura locale, origine e date dei file, nessuna nuova richiesta dalla cache; PDS3 → "non ancora supportato"; errori `PDS_UNREADABLE`, `SERVICE_ERROR`, `NET_TIMEOUT` | confronto con la libreria di D19-2 |
| T9 | Opzione disattivata | chiamare una funzione del modulo con l'opzione disattivata | `PLANETARY_DATA_DISABLED` con il testo "i dati planetari non sono disponibili in questa versione" (nessun rinvio alle preferenze); funzioni celesti non toccate | test di unità |
| T11 | Sovrapposizione forzata | ripetere T1 con l'opzione di forzatura | sovrapposizione eseguita, avviso `BODY_MISMATCH_FORCED` nel risultato e nel comando registrato | test di unità |
| T10 | Riproducibilità | rieseguire il comando registrato di T4 e T5 | risultati identici | confronto con il registro del modulo 24 |
| T12 | Corpi diversi con l'opzione spenta (sprint 4f del 41) | opzione spenta: MOC celeste + MOC di Marte senza e con forzatura; due MOC di Marte | senza forzatura `BODY_MISMATCH` con i due corpi (mai `PLANETARY_DATA_DISABLED`); con forzatura `PLANETARY_DATA_DISABLED`; due MOC di Marte `PLANETARY_DATA_DISABLED`; con l'opzione accesa come T1, T11 | test di unità |

## 13. Decisioni aperte

- **D19-1 — Libreria per i sistemi planetari: DECISA il 2026-10-09 (decisione
  del proprietario sulla checklist del livello 1).** **`spiceypy`** con i
  **kernel PCK generici della NAIF**, versione dichiarata nel risultato. **Da
  verificare prima del codice:** licenze di `spiceypy` e dei kernel,
  installazione su macOS, assenza di sistemi fissi ai corpi in Astropy.
  **Verificato il 2026-10-13** (§3, P0 punti 1, 2, 7).
- **D19-2 — Formato PDS: DECISA il 2026-10-08 (decisione del proprietario).**
  Lettura PDS **nel modulo 19**, non nell'11; **PDS4 obbligatorio**; PDS3 solo
  se esiste una libreria consolidata.
- **D19-2b — Libreria PDS e licenza: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** **`pds4_tools`** per PDS4;
  per PDS3 si valuta **`pdr`**. **Da verificare prima del codice:** licenze,
  manutenzione e installazione su macOS di entrambe. **Verificato il
  2026-10-13** (§3, P0 punti 3, 4): `pds4_tools` adottato; `pdr` lecito
  ma "Beta" → D19-8.
- **D19-3 — Metadati del corpo: DECISA il 2026-10-08 (decisione del
  proprietario).** Campo `body` obbligatorio nei metadati dei moduli 12, 13,
  14 e 16; per i dati astronomici vale `celestial` (sfera celeste), ricavato
  dal sistema di coordinate, mai assunto. Applicata in quei quattro file.
- **D19-4 — Forzatura delle sovrapposizioni: DECISA il 2026-10-08 (decisione
  del proprietario).** Sovrapposizione tra corpi diversi, o tra dati celesti e
  planetari, = **errore di default**, forzabile con un'**opzione esplicita
  citata nel risultato** (stesso schema di D13-5). Applicata in §3, §9, §10,
  §12.
- **D19-5 — Valore predefinito dell'opzione: DECISA il 2026-10-09 (decisione
  del proprietario sulla checklist del livello 1; motivazione riscritta il
  2026-10-10, regola d'oro n. 8).** dati planetari **disattivati per
  default**, attivabili nelle preferenze. **Motivazione (nostra):** la
  maggior parte del lavoro è sul cielo; con l'opzione spenta l'elenco delle
  collezioni mostra solo dati celesti e non si apre per errore un dato di un
  altro corpo, che poi non si potrebbe sovrapporre (D19-4); chi lavora sui
  pianeti la accende una volta.
- **D19-6 — Corpi supportati inizialmente: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** i corpi che hanno un HiPS nel
  MocServer e sono presenti nel kernel PCK; **Luna e Marte obbligatori** per i
  test. **Tabella (28 corpi) approvata il 2026-10-13** con la regola dei
  nomi di D12-6 (§3).
- **D19-7 — MOC planetari: DECISA il 2026-10-09 (decisione del proprietario
  sulla checklist del livello 1).** **prima verificare** lo standard MOC 2.0 e
  `mocpy` (vincolo prima del codice); se non supportano coperture planetarie,
  MOC HEALPix con metadato `body` (D19-3), dichiarato come estensione di
  AstroTwo.

- **D19-8 — PDS3 con `pdr`: RIMANDATA, bassa priorità (decisione del
  proprietario del 2026-10-13).** Per ora niente `pdr`: un'etichetta PDS3 dà
  `PDS_UNREADABLE` con "formato PDS3 non ancora supportato". Resta nel
  Gruppo 3 come rimandata. Testo della domanda (aperta lo stesso giorno):
  La verifica di P0 (§3 punto 4) trova licenze compatibili, installazione
  semplice e manutenzione attiva, ma gli autori classificano `pdr` come
  **"Beta"** e porta `pandas` e altre tre dipendenze. D19-2 ammette PDS3
  "solo con libreria consolidata". **Raccomandazione:** ammetterlo come
  **dipendenza facoltativa** (installata solo se l'utente apre PDS3), con
  l'avviso nel risultato che la lettura è di una libreria Beta e un test
  su file PDS3 reali piccoli prima dell'adozione; in alternativa, PDS3 non
  supportato nel livello 1. Ferma solo la lettura PDS3 di P4.
- **D19-9 — `load_pds_image` da URL: DECISA il 2026-10-13 (decisione del
  proprietario: la raccomandazione).** Etichetta e file nominati dalla stessa
  cartella dell'URL, rete del 14, cache comune, origine e data; applicata in
  §3 (scelta 9), §6, §7, §8, §10, T8. Testo della domanda: §6 ammette "percorso o URL", ma un prodotto PDS4 è
  un'etichetta più uno o più file di dati: non è descritto come scaricarli
  (tutti i file nominati nell'etichetta, dalla stessa cartella dell'URL,
  con la rete e la cache del 14?). **Raccomandazione:** sì, scaricare
  l'etichetta e i file che nomina dalla stessa cartella con la rete del 14
  e la cache comune (04), con origine e data. Ferma solo gli URL.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-08 | Claude Code | Creazione del file (stato: bozza). Origine: riga H21 di `03-parita-aladin.md` (manuale di Aladin ed. giugno 2022, sez. 5.21, 7.2, 8.1), modulo accettato in AM1 il 2026-10-08. Corpo mai assunto, nessuna sovrapposizione tra corpi diversi o tra dati celesti e planetari, convenzioni sempre dichiarate; dipendenze da 10, 11, 12, 13, 14, 16; decisioni aperte D19-1…D19-7. |
| 2026-10-09 | Claude Code | **Decisioni del proprietario del 2026-10-08:** D19-2 (PDS letto qui, PDS4 obbligatorio, PDS3 solo con libreria consolidata; resta aperta D19-2b su libreria e licenza, Gruppo 2), D19-3 (campo `body` obbligatorio nei moduli 12, 13, 14, 16; `celestial` ricavato dal sistema di coordinate) e D19-4 (errore di default, forzabile con opzione esplicita citata nel risultato; nuovo avviso `BODY_MISMATCH_FORCED`, test T11). §3, §5, §6, §7, §8, §9, §10, §12, §13 aggiornati. |
| 2026-10-09 | Claude Code | **D19-1, D19-2b, D19-5, D19-6, D19-7 DECISE** (checklist del livello 1): `spiceypy` + kernel PCK della NAIF; `pds4_tools` (PDS4) e `pdr` da valutare (PDS3); dati planetari disattivati per default; corpi con HiPS nel MocServer e nel kernel PCK, Luna e Marte obbligatori per i test; MOC planetari da verificare, altrimenti estensione con `body`. Le verifiche di licenza e supporto restano vincoli prima del codice. §3, §8 aggiornati. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-09. |
| 2026-10-10 | Claude Code | **Regola d'oro n. 8** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): D19-5 (dati planetari disattivati per default) resta, con motivazione nostra al posto di "come in Aladin" (§3 punto 9, §13); formato PDS motivato come standard degli archivi planetari (§3, §8). Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **Decisioni del proprietario del 2026-10-13** (autorizzazione esplicita a modificare il file approvato): divisione in P0–P4; **tabella dei nomi (D12-6)** approvata e scritta (28 corpi, nome IAU inglese con iniziale maiuscola, `bodn2c` → NAIF → nome canonico), applicata anche al 12. **Esiti di P0** in §3 (spiceypy MIT con CSPICE e regole NAIF; kernel `pck00011.tpc` incluso con SHA-256; `pds4_tools` BSD-3 senza file di esempio; `pdr` Beta; `hips_body` minuscolo nel MocServer; EPN-TAP 2.0; nessun sistema solidale ai corpi in astropy); scelte minori proposte in §3; nuove `PDS_STRUCTURE_CHOICE_REQUIRED`, `PLANETARY_KERNEL_INVALID` (§10); nuove **D19-8** (PDS3 con `pdr`) e **D19-9** (PDS da URL), Gruppo 3. Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **P1 scritta** (`planetary_data.py`: `PlanetaryDataError`, `BODY_TABLE`, `normalize_body_name`, `PlanetaryBody.from_name`, `body_of`, `check_overlay`/`OverlayCheck`, opzione D19-5, `PlanetaryCommand`/`run_command`; T1, T2, T3, T9, T11, tabella dei nomi e integrità del kernel); tabella applicata al 12. Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **P2 scritta** (`PlanetaryPosition`, `convert_planetary_coordinates`, `LATITUDE_TYPES`, `LONGITUDE_DIRECTIONS`; T4, T5, T6, T10): latitudine con `spiceypy` sullo sferoide del kernel, verso della longitudine per definizione confrontato con `recpgr` per Marte. T5 precisato con il controllo sulla definizione. Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **P3 scritta** (`list_planetary_collections`/`PlanetaryCollections` con la copia locale delle collezioni del 12, `query_epntap` con `tap_query` del 14 ed `EPNTAP_CONVENTIONS`; T7 esteso alle collezioni). Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **P4 scritta — modulo 19 completo tranne PDS3 (D19-8) e PDS da URL (D19-9)** (`load_pds_image`/`PdsImage`, `body_of` sulle immagini PDS; T8). Test di rete: tabella dei corpi contro il MocServer (ogni corpo ha un HiPS), EPN-TAP reale (`mars_craters.epn_core` del servizio TAP di VO-Paris). Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **Decisioni del proprietario del 2026-10-13** (autorizzazione esplicita a modificare il file approvato): scelte minori 1–9 di §3 confermate; **D19-9 decisa e scritta** (PDS4 da URL: etichetta + file nominati nella stessa cartella, rete del 14, cache comune, `downloads` e `PDS_DOWNLOADED` nel risultato; T8 esteso con un server HTTP locale); **D19-8 rimandata** (bassa priorità): PDS3 → `PDS_UNREADABLE` "formato PDS3 non ancora supportato". Stato `approvato` invariato. |
| 2026-10-21 | Claude Code | **Ordine dei controlli di `check_overlay` (decisione del proprietario del 2026-10-21, autorizzazione esplicita a modificare il file approvato, sprint 4f del 41):** con corpi diversi senza forzatura `BODY_MISMATCH` anche con l'opzione dei dati planetari spenta; l'opzione si controlla solo se la sovrapposizione passerebbe (scelta minore 1); T12. Stato `approvato` invariato. |
| 2026-10-21 | Claude Code | **Testo di `PLANETARY_DATA_DISABLED` (decisione del proprietario del 2026-10-21, parte 5 della v1):** nella v1 la preferenza dei dati planetari non esiste, quindi il testo non dice più "attivarli nelle preferenze" ma "i dati planetari non sono disponibili in questa versione"; solo italiano (D40-1; inglese con D40-3). Comportamento invariato. §10 e T9 aggiornati. Stato `approvato` invariato. |
