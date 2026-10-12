# 17-core-misure.md — misure angolari e strumenti di misura

**Stato:** approvato

## 2. Scopo

Fornire gli strumenti di misura su cielo e immagini — distanze angolari, angoli
di posizione, lettura dei valori pixel, profili lungo una linea e forme di
disegno — con risultati in unità esplicite e sempre verificabili.

## 3. Cosa fa

- **Distanza angolare (F1):** misurare la separazione tra due punti celesti;
  unità di uscita a scelta (arcsec, arcmin, gradi) con conversioni esplicite.
- **Position angle (F2):** angolo di posizione tra due punti o, in alternativa,
  tra i due estremi di una **linea** (segmento), misurato **dal nord verso
  est** (convenzione astronomico: 0° = nord, 90° = est) nel frame dichiarato
  (ICRS di default), con unità di uscita esplicita. La misura lungo una linea
  è la stessa angolo della retta che congiunge i due estremi, così da poter
  orientare frecce e tracciati. **Casi limite vicino ai poli:** l'angolo di
  posizione dipende dalla direzione locale del nord celeste, che al polo
  cambia rapidamente con la longitudine; se i punti coincidono, se la
  direzione non è determinata (punto esattamente al polo con secondo punto di
  RA indefinita) o se il frame è ignoto, la funzione restituisce errore
  `PA_UNDEFINED`/`FRAME_UNKNOWN` **senza mai approssimare** un angolo.
  Inclusa per decisione del proprietario (2026-10-04): in Aladin la funzione
  non risulta documentata, ma la parità con Aladin è il minimo → §13-D17-1.
- **Offset angolari e calcolo inverso (A5; da D10-8 del
  `10-core-coordinate-wcs.md`, decisa il 2026-10-09):** (1) gli **offset**
  tra due punti, Δα·cos δ e Δδ (offset sferici nel frame del primo punto,
  `SkyCoord.spherical_offsets_to`); (2) la **posizione ottenuta applicando
  degli offset** a un punto (`SkyCoord.spherical_offsets_by`); (3) il
  **calcolo inverso**: la posizione che si trova a una distanza angolare e a
  un angolo di posizione (nord → est) dati da un punto
  (`SkyCoord.directional_offset_by`). Ogni risultato dichiara frame, epoca e
  unità come le altre misure; queste funzioni erano la parte "offset e
  calcolo inverso" della calcolatrice delle coordinate, tolta dal modulo 10,
  e sono usate da `18-core-calcolatrici.md`.
- **Lettura dei valori pixel (F3):** leggere il valore (o i valori nei pressi)
  in una posizione di un'immagine; la fotometria vera e propria (baricentri,
  ellissi, statistiche su cerchi/poligoni — F4) è **interamente** di
  `20-analisi-fotometria.md` (confine confermato con D17-4 il 2026-10-04),
  che usa la lettura di questo modulo.
- **Distanza con profilo (H11):** misurare la distanza tra due punti e
  restituire contemporaneamente il **profilo di intensità** lungo il segmento
  (campionato a passo dichiarato).
- **Forme di disegno (H11):** cerchi, ellissi, frecce, poligoni, testo e
  **tracciati liberi** come oggetti geometrici con coordinate, con operazioni
  geometriche (appartiene-punto, area, distanza tra forme); il disegno a
  schermo è di `41-ui-visualizzatore-cielo.md`.
- **Tag / marcature (H11):** marcare punti d'interesse con etichetta e
  coordinate; la persistenza è **nel file di sessione di
  `24-analisi-pipeline-riproducibili.md`, condiviso con i segnalibri di
  `40-ui-finestra-principale.md`** (D17-3, decisa il 2026-10-04). **La
  sessione salva riferimenti ai file e operazioni eseguite (non i pixel) e
  deve poter essere rieseguita**; questo modulo non scrive su disco.
- **Unità e frame:** ogni misura dichiara sistema di riferimento (ICRS di
  default) e unità; nessun numero è restituito senza unità.
- **Misura automatica della distanza tra due sorgenti di catalogo (F1, sez.
  5.9 del manuale di Aladin, ed. giugno 2022):** con lo strumento attivo, la selezione
  di **due sorgenti di catalogo** (da `13-core-cataloghi.md`) produce la
  distanza angolare tra le loro posizioni con `angular_distance`, insieme ai
  due estremi del segmento da disegnare (disegno temporaneo nel 41). Le due
  posizioni devono riferirsi alla stessa epoca: se le epoche dei cataloghi
  differiscono, si propagano con il modulo 10 (moto proprio dai metadati) o,
  se mancano i dati, errore `EPOCH_REQUIRED` — l'epoca non si assume mai. Le
  due sorgenti devono avere lo stesso `body` (D19-3). Per misurare oggetti in
  un'immagine con il centroide (consiglio del manuale) serve la fotometria
  del modulo 20.

### Decisioni del proprietario del 2026-10-12 e divisione in parti

**Divisione in 4 parti (approvata dal proprietario il 2026-10-12):**

| Parte | Contenuto | Test |
|---|---|---|
| P1 | `angular_distance` (con `skydist` del 13), `position_angle` con i casi ai poli, `angular_offsets`, `apply_offsets`, `offset_position` | T1, T2, T8, T9, T13–T15 |
| P2 | `read_pixel`, `profile_along_line`, `distance_with_profile` | T3–T6 |
| P3 | forme (`Shape`: `Circle`, `Ellipse`, `Arrow`, `Polygon`, `Text`, `Freehand`) e tag | T7 |
| P4 | `auto_distance` tra due sorgenti di catalogo, con epoca propagata con il 10 e controllo del corpo | T10–T12 |

- **D17-5 decisa** (§13): profili con **interpolazione bilineare** tramite
  `scipy.ndimage.map_coordinates` (`order=1`); **passo obbligatorio, senza
  default**.
- **P3:** prima si verifica come calcolare area e "contiene" per ellissi e
  poligoni sferici con le librerie già presenti (`astropy`, `mocpy`); se
  serve una libreria nuova si ferma solo P3, con la proposta (libreria,
  licenza, motivo), e si continua con P4.

**Codice: `src/astrotwo/core/measures.py`**, errori `MeasuresError` con gli
identificatori di §10. Ogni risultato porta un **report** (`MeasureReport`:
operazione, punti come scritti in ingresso, frame, unità, immagine, data
della misura in UTC, passaggi e avvisi, librerie usate).

**P1 — misure angolari (scritta il 2026-10-12).** Verifiche del 2026-10-12
con `astropy` 8.0.1: `SkyCoord.position_angle` **restituisce sempre un
numero**, anche quando la direzione non è definita (0° per due punti
coincidenti, 90° per due punti antipodali, e dal polo un angolo che dipende
solo dalla longitudine scritta del polo: (30°, 90°) e (0°, 90°) verso lo
stesso punto danno 110° e 80°); quindi i casi di `PA_UNDEFINED` si
controllano **prima** di chiamare Astropy. `spherical_offsets_to` rifiuta due
frame diversi (`ValueError`): la conversione si fa prima, con il 10.
Scelte minori:

1. **Punti:** `SkyFrame` del 10 o `SkyCoord` (avvolto in `SkyFrame`, con le
   regole del 10 sulle epoche); un punto per misura (array → `ValueError`).
   Numeri senza frame → `FRAME_UNKNOWN` (il frame non si assume).
2. **Frame:** le misure sono nel **frame del primo punto**; se il secondo è
   in un altro frame si converte con `convert_coordinates` del 10 (con
   equinozio e `obstime` del primo punto) e la conversione è scritta nel
   report; se il 10 non la può fare, il suo errore (`FRAME_UNSUPPORTED`,
   `EPOCH_REQUIRED`) passa con lo stesso identificatore. Le epoche dei due
   punti (se note) sono scritte nel report; per le sorgenti di catalogo
   l'epoca comune è imposta da `auto_distance` (P4).
3. **Unità di `angular_distance`:** obbligatoria, `arcsec`, `arcmin` o
   `deg`/`degree` (stringa o unità di `astropy`); altro → `ValueError`.
   Calcolo: `skydist` del 13 sulle longitudini e latitudini nel frame del
   primo punto (gradi), poi conversione con `astropy.units`.
4. **`PA_UNDEFINED`** (controlli esatti, nessuna soglia): punti coincidenti
   (separazione 0), punti **antipodali** (separazione 180°: tutte le
   direzioni portano al secondo punto) e **primo punto esattamente al polo**
   (latitudine ±90°: il nord locale non è definito). Il secondo punto al
   polo non è un caso indefinito (PA = 0° verso il polo nord, 180° verso il
   polo sud). PA in gradi in [0°, 360°).
5. **Linea:** `Segment(start, end)`; `position_angle(segment)` dà lo stesso
   valore di `position_angle(start, end)` (T9). Il segmento serve anche al
   profilo (P2) e agli estremi di `auto_distance` (P4).
6. **Offset:** Δα·cos δ e Δδ in gradi nel frame del primo punto (ruotato sul
   primo punto, come `spherical_offsets_to`); `apply_offsets` e
   `offset_position` danno la posizione nel frame del punto di partenza, con
   la sua epoca. Valori senza unità angolare, non finiti, distanza negativa
   o oltre 180° → `OFFSET_INVALID`; l'angolo di posizione è un qualsiasi
   angolo finito (da nord verso est).

**P2 — pixel e profili (scritta il 2026-10-12).** Scelte minori:

1. **Posizione:** `SkyFrame`/`SkyCoord` (serve il WCS dell'immagine,
   altrimenti `NO_WCS`; conversione con `sky_to_pixel` del 10) oppure
   `PixelPosition` del 10 con la convenzione dichiarata (`fits` o `numpy`,
   convertita con `convert_pixel_convention`); una tupla di numeri senza
   convenzione → `TypeError`. Le posizioni in uscita sono in convenzione
   numpy, dichiarata.
2. **`read_pixel`:** il pixel che contiene la posizione (centro del pixel
   `i` in `i`, bordi a `i ± 0,5`: indice `floor(x + 0,5)`); fuori da
   [−0,5, n − 0,5) → `POINT_OUT_OF_IMAGE` con il riquadro dell'immagine.
   Parametro facoltativo `half_size` (default 0) per i "valori nei pressi":
   la finestra (2·`half_size` + 1)² centrata sul pixel, intera dentro
   l'immagine. I pixel si leggono con `read_region` dell'11 (pixel originali
   anche per le immagini a due livelli e in `memmap`); valore in `float64`,
   mai modificato. Unità: `BUNIT` come scritta nell'intestazione e unità di
   `astropy` se riconosciuta; senza `BUNIT` → `"unitless"`. Valore non
   finito → restituito com'è con l'avviso `NONFINITE_PIXELS`.
3. **`profile_along_line`:** campioni lungo il **segmento rettilineo in
   pixel** tra i due estremi, a distanza `k · step` dal primo estremo per
   k = 0 … floor(L / step) (L = lunghezza in pixel; il secondo estremo è un
   campione solo se L è multiplo del passo); `step` in pixel (numero o
   `Quantity` in `pix`) obbligatorio, finito e > 0, altrimenti
   `PROFILE_STEP_INVALID`. Interpolazione bilineare con
   `scipy.ndimage.map_coordinates(order=1, prefilter=False)` (D17-5) sui
   pixel originali letti con `read_region`; gli estremi devono stare tra i
   centri dei pixel del bordo, [0, n − 1] su ogni asse (dove la bilineare
   non estrapola), altrimenti `POINT_OUT_OF_IMAGE`. Campioni con un vicino
   non finito → NaN con l'avviso `NONFINITE_PIXELS`. Memoria: campioni e
   regione letta entro il limite delle operazioni dell'immagine (4 GB, D11-11),
   altrimenti `MEMORY_LIMIT_EXCEEDED` prima di leggere. Con il WCS, ogni
   campione ha anche la sua posizione celeste (`pixel_to_sky` del 10).
4. **`distance_with_profile`:** estremi celesti → distanza angolare con
   `angular_distance` (in gradi) + profilo; estremi in pixel → distanza in
   pixel (`u.pix`, dichiarata "pixel space", nessuna conversione implicita)
   + profilo. Il "grafico esportabile" (D17-6) è dato come tabella
   (`to_table()`: `astropy.table.Table` con offset lungo il segmento, x, y,
   valore e, con il WCS, posizione celeste, unità e metadati del report): il
   grafico è disegnato dal 41 e il file si scrive fuori da questo modulo.

**P3 — forme e tag: FERMA (verifica del 2026-10-12).** Con le librerie già
presenti non c'è un calcolo **esatto** di area e "contiene" per ellissi e
poligoni sferici: `astropy` non ha geometria di poligoni sulla sfera; `mocpy`
(`from_polygon`, `from_elliptical_cone`, `contains_lonlat`, `sky_fraction`)
lavora per celle HEALPix, quindi dà una regione approssimata per eccesso alla
risoluzione dell'ordine scelto, e per l'ellisse non dichiara la definizione
geometrica usata. Il cerchio si calcola esattamente con Astropy (separazione
≤ raggio; area 2π(1 − cos r)). **Proposta (da decidere, D17-7):** libreria
**`spherical-geometry`** (Space Telescope Science Institute, licenza
**BSD-3-Clause**, versione 1.4.0 del 2026-03, ruote per Python 3.12 su macOS
arm64 e x86_64) per poligoni e tracciati chiusi (`SphericalPolygon`:
`contains_point`, `area`, lati di cerchio massimo); per l'**ellisse** serve
anche una **definizione** sulla sfera, che nessuna delle librerie fissa
(D17-7, punto b). Fermo solo P3; P4 continua.

**P4 — distanza automatica (scritta il 2026-10-12).** Scelte minori:

1. **Ingresso:** `auto_distance(selection, unit, *, epoch=None)` con
   `selection` = sequenza delle sorgenti selezionate (`CatalogSource(table,
   row, …)`), così il caso di T11 è controllabile: un numero di sorgenti
   diverso da 2 → `SELECTION_NOT_TWO_SOURCES` con il numero selezionato.
2. **Posizioni** dalle colonne di posizione del 13 (`positions`, frame
   dichiarato; senza colonne → `NO_COORD_COLUMNS`, senza frame →
   `FRAME_UNKNOWN`); **epoca** di ogni sorgente dai metadati del 13
   (colonna con UCD `time.epoch`, COOSYS) o, solo se assente, da
   `source_epoch` della `CatalogSource` (stessa regola del 13); nessuna →
   `EPOCH_REQUIRED`.
3. **Epoca comune:** `epoch` se dato, altrimenti l'**epoca della prima
   sorgente selezionata**; ogni sorgente a un'epoca diversa si propaga con
   `propagate` del 13 (che usa `propagate_position` del 10) su una tabella
   di una sola riga, con le colonne del moto proprio indicate nella
   `CatalogSource` (`pm_ra`, `pm_dec`, `pm_ra_includes_cosdec` obbligatori;
   `parallax`, `radial_velocity` facoltativi: senza parallasse solo moto
   proprio, dichiarato). Colonne non indicate o valori mancanti →
   `EPOCH_REQUIRED`. Epoca usata, modo e note della propagazione nel
   risultato.
4. **Corpo:** stesso `body` per le due tabelle, altrimenti `BODY_MISMATCH`;
   `body` non dichiarato (`None`, es. coordinate planetarie prima del 19) →
   `BODY_UNKNOWN`.
5. **Risultato:** distanza (`angular_distance`, nel frame della prima
   sorgente), estremi del segmento (`Segment` alle posizioni all'epoca
   usata), epoca usata, report.

## 4. Cosa NON fa

- Non fa la fotometria (20), né le misure da cubo (23 — spettro/profilo da
  cubo è F5, assegnato al 23).
- Non disegna: restituisce geometria e dati alla UI (41) che rende le forme.
- Non converte coordinate né calcola WCS (10); le misure in gradi passano per
  il modulo 10.
- Non carica le immagini (11) né le tabelle (13).
- Non salva la sessione né le marcature su disco (24, 40).
- Non gestisce MOC, cataloghi HiPS o query (16, 12, 14).

## 5. Livello e dipendenze

- **Livello:** 1
- **Dipende da:** `10-core-coordinate-wcs.md` (coordinate, frame, distanze
  angolari), `11-core-immagini-fits.md` (accesso ai pixel e WCS dell'immagine),
  `13-core-cataloghi.md` (posizioni delle sorgenti da misurare).
- **Usato da:** `18-core-calcolatrici.md` (`skydist`, lettura pixel, offset
  e calcolo inverso per la calcolatrice delle coordinate),
  `20-analisi-fotometria.md` (lettura pixel), `41-ui-visualizzatore-cielo.md`
  (forme, tag, distanza con profilo), `42-ui-pannello-cataloghi.md`,
  `34-ia-verifica-risultati.md`.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `p1`, `p2` | float64 | gradi, ICRS (o `SkyCoord`) | punti da misurare |
| in | `unit` | enumerativo | arcsec / arcmin / degree | unità di uscita |
| in | `position` | float64 | gradi (immagine con WCS) o pixel | per lettura pixel |
| in | `line` | due punti + passo | gradi o pixel + passo in pixel | per il profilo |
| in | forma | struttura geometrica | cerchio/ellisse/freccia/poligono/testo/tracciato con coordinate | H11 |
| out | distanza | float64 + unità (`Quantity`) | arcsec/arcmin/degree | |
| out | position angle | float64 + unità angolare | gradi, da nord verso est | tra due punti o lungo una linea (segmento) |
| out | valore pixel | float64 | unità della immagine (header BUNIT) | o "unitless" se assente |
| out | profilo | serie (posizione, valore) | pixel lungo il segmento + valori | campionato a passo dichiarato |
| out | forma/tag | oggetto geometrico | coordinate + attributi | |
| in | due sorgenti di catalogo | righe di `CatalogTable` | posizioni con frame, epoca e `body` | F1 automatica |
| out | distanza automatica | struttura | distanza con unità + estremi del segmento + epoca usata | F1 automatica |
| in | offset | due `Quantity` angolari | Δα·cos δ e Δδ, unità angolare esplicita | per `apply_offsets` |
| in | distanza + angolo di posizione | due `Quantity` angolari | distanza ≥ 0; PA da nord verso est | per `offset_position` |
| out | offset | due `Quantity` angolari | Δα·cos δ e Δδ nel frame del primo punto | da `angular_offsets` |
| out | posizione calcolata | coordinate | gradi + frame + epoca del punto di partenza | da `apply_offsets` / `offset_position` |

## 7. Interfaccia pubblica

- **`angular_distance(p1, p2, unit)`** — separazione angolare.
  **Calcolo: la funzione `skydist` della tabella delle funzioni di
  `13-core-cataloghi.md` (`catalogs.py`), che usa
  `astropy.coordinates.angular_separation`** (decisione del proprietario del
  2026-10-10, D13-10 del 13): **una sola implementazione**, nessun
  duplicato; il 17 converte le posizioni nel frame del primo punto e
  chiama quella.
- **`position_angle(p1, p2)`** — angolo di posizione tra due punti (o tra gli
  estremi di una linea/segmento), da nord verso est, nel frame dichiarato;
  errore `PA_UNDEFINED` se i punti coincidono o la direzione non è determinata
  (casi limite ai poli), `FRAME_UNKNOWN` se il frame è ignoto.
  **Calcolo: `SkyCoord.position_angle` (Astropy).**
- **`read_pixel(image, position)`** — valore in un punto; se `image` ha WCS,
  si può passare una posizione celeste, altrimenti si passa in pixel e
  l'output è dichiarato "pixel space" (nessuna conversione implicita).
- **`profile_along_line(image, p1, p2, step)`** — profilo di intensità lungo
  un segmento; interpolazione dichiarata (vede §13-D17-5).
- **`distance_with_profile(image, p1, p2, step)`** — misura H11: distanza +
  profilo in un'unica struttura con report (posizioni, unità, immagine, data).
- **`Shape`** (classe base; `Circle`, `Ellipse`, `Arrow`, `Polygon`, `Text`,
  `Freehand`) — forme H11 con metodi `contains(point)`, `area()`,
  `distance_to(...)`; calcolo geometrico con Astropy/geometria celeste.
- **`tag(point, label)`** — marcatura con coordinate e etichetta; la UI la
  rende, la **sessione del 24** la persiste insieme ai segnalibri di 40
  (D17-3).
- **`angular_offsets(p1, p2)`** — offset Δα·cos δ e Δδ da `p1` a `p2` nel
  frame di `p1`. **Calcolo: `SkyCoord.spherical_offsets_to` (Astropy).**
- **`apply_offsets(p, d_lon, d_lat)`** — posizione ottenuta applicando a `p`
  gli offset dati. **Calcolo: `SkyCoord.spherical_offsets_by`.**
- **`offset_position(p, distance, position_angle)`** — calcolo inverso:
  posizione a distanza e angolo di posizione dati da `p`. **Calcolo:
  `SkyCoord.directional_offset_by`.**
- **`auto_distance(selection, unit, *, epoch=None)`** (F1) — distanza tra
  le due sorgenti di catalogo selezionate (`selection` = sequenza di
  `CatalogSource`; scelta minore di P4 in §3); restituisce distanza, estremi
  del segmento ed epoca usata.
- **`Segment(start, end)`** — linea tra due punti (PA lungo una linea,
  profilo, estremi della distanza automatica); **`MeasureReport`** — report
  di ogni misura (§9).

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| `astropy.coordinates` | distanze angolari, position angle, frame | standard del dominio |
| `astropy.units` | unità di ogni misura | unità esplicite sempre |
| `numpy` | campionamento dei profili, valori pixel | consolidato |
| `scipy.ndimage.map_coordinates` | interpolazione bilineare dei profili (D17-5) | consolidato, già nel progetto |
| `skydist` del 13 (`astropy.coordinates.angular_separation`) | distanza angolare (D13-10) | implementazione unica |
| Convenzione astronomica del PA | angolo di posizione da nord verso est | convenzione della comunità |

## 9. Regole e vincoli

- Nessuna misura è restituita senza unità e, per le misure celesti, senza
  sistema di riferimento.
- Nessuna approssimazione piana: le distanze angolari usano la geometria
  sferica di Astropy (regola d'oro n. 4).
- Le misure "a schermo" (pixel) e "celestiali" (gradi) sono due ambiti
  distinti: passare dall'uno all'altro richiede il WCS del modulo 10/11,
  mai una conversione approssimata.
- I valori letti dai pixel sono quelli memorizzati nell'array (`float64` nelle
  misure): nessuna modifica, nessun arrotondamento al display (vincolo di
  `11-core-immagini-fits.md`).
- Le misure restituiscono sempre il report (punti, unità, frame, immagine,
  timestamp) per la riproducibilità.
- Le forme di disegno contengono solo coordinate e attributi: nessuna
  logica di disegno vive in questo modulo.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Punto fuori dall'immagine per lettura pixel | errore con il bounding box dell'immagine | `POINT_OUT_OF_IMAGE` |
| Immagine senza WCS e richiesta in gradi | errore che chiede il WCS o una posizione in pixel | `NO_WCS` |
| Punti identici per distanza/PA | distanza 0; PA non definita → errore esplicito | `PA_UNDEFINED` |
| Direzione non determinata vicino ai poli (punto esattamente al polo o secondo punto di RA indefinita) | errore esplicito, nessun angolo approssimato | `PA_UNDEFINED` |
| Passo del profilo non positivo | rifiuto dell'input | `PROFILE_STEP_INVALID` |
| Forma geometrica malformata (raggio ≤ 0, vertici < 3) | rifiuto con il campo invalido | `SHAPE_INVALID` |
| Frame dei due punti diversi o ignoto | errore/convertito esplicitamente con il modulo 10 | `FRAME_UNKNOWN` |
| Valore pixel non finito (NaN) | restituito come tale con avviso, mai sostituito | `NONFINITE_PIXELS` |
| Selezione diversa da due sorgenti di catalogo | nessuna misura, messaggio con il numero selezionato | `SELECTION_NOT_TWO_SOURCES` |
| Epoche diverse senza dati per propagare | nessuna misura: l'epoca non si assume | `EPOCH_REQUIRED` |
| Sorgenti di corpi diversi | nessuna misura | `BODY_MISMATCH` |
| Offset, distanza o angolo senza unità, non finiti, distanza negativa o oltre 180° | rifiuto dell'input | `OFFSET_INVALID` |
| Punti antipodali per la PA | errore esplicito, nessun angolo | `PA_UNDEFINED` |
| Passo del profilo assente o non finito | rifiuto dell'input | `PROFILE_STEP_INVALID` |
| Estremo del profilo fuori da [0, n − 1] (bilineare senza estrapolazione) | nessun profilo | `POINT_OUT_OF_IMAGE` |
| Profilo o regione oltre il limite delle operazioni (D11-11) | nessun profilo, prima di leggere | `MEMORY_LIMIT_EXCEEDED` |
| Tabella senza colonne di posizione (F1) | nessuna misura | `NO_COORD_COLUMNS` |
| Corpo non dichiarato in una delle due tabelle (F1) | nessuna misura | `BODY_UNKNOWN` |
| Immagine a colori per lettura pixel o profilo | nessun valore (solo presentazione, 11) | `OPERATION_UNSUPPORTED` |

## 11. Esposizione all'IA

- **`angular_distance`** — input: due punti (gradi, ICRS) + unità; output:
  separazione con unità. **Calcolo: `astropy.coordinates`, mai l'IA.**
- **`position_angle`** — input: due punti; output: PA in gradi (nord→est).
  **Calcolo: Astropy.**
- **`read_pixel_value`** — input: immagine + posizione; output: valore con
  unità dell'header. **Calcolo: accesso all'array del modulo 11.**
- **`distance_with_profile`** — input: due punti; output: distanza + profilo.
  **Calcolo: Astropy + NumPy.**
- **`offset_position`** — input: punto, distanza, angolo di posizione;
  output: posizione con frame. **Calcolo: Astropy.**
- **`angular_offsets`** — input: due punti; output: Δα·cos δ, Δδ.
  **Calcolo: Astropy.**
- **`describe_shape`** — input: forma; output: parametri geometrici (raggio,
  assi, centro, vertici). Nessun calcolo inferenziale.

Come sempre: l'IA formula la richiesta e spiega il risultato; i numeri
arrivano solo da questi strumenti e vengono poi verificati da
`34-ia-verifica-risultati.md`.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Distanza nota | distanza tra (0°,0°) e (1°,0°) in gradi | ≈ 1 grado | ricalcolo nel test con `astropy.coordinates.angular_separation` (tolleranza 1e-12) |
| T2 | Position angle | PA da (0°,0°) verso (0°,1°) (nord) e verso (1°,0°) (est) | 0° e 90° rispettivamente | ricalcolo nel test con `SkyCoord.position_angle` |
| T3 | Lettura pixel | immagine sintetica 10×10 con valori noti, lettura al centro | valore esatto della cella centrale | confronto con l'array `numpy` costruito nel test |
| T4 | Profilo lineare | profilo lungo una linea su un gradiente noto | valori coincidenti con `numpy.linspace`/interpolazione ricalcolata nel test | ricalcolo con NumPy |
| T5 | Distanza con profilo | eseguire H11 su due punti | distanza coincidente con T1 e profilo lungo il numero atteso di campioni | confronto diretto con le funzioni di base |
| T6 | Immagine senza WCS | chiedere una misura in gradi su immagine senza WCS | `NO_WCS`; la lettura in pixel continua a funzionare | test di unità |
| T7 | Forme | `contains` di punti noti dentro/fuori un cerchio | risultati coincidenti con il calcolo ricalcolato nel test con `astropy.units` | ricalcolo nel test |
| T8 | Position angle non definita | chiedere la PA tra due punti identici e tra un punto esattamente al polo e un punto di RA indefinita | errore `PA_UNDEFINED` in entrambi i casi, nessun numero prodotto | test di unità |
| T9 | Position angle lungo una linea | PA della stessa coppia di punti come coppia e come segmento | stesso valore (coerenza tra i due modi d'uso) | confronto diretto nel test |
| T10 | Distanza automatica (F1) | selezionare due sorgenti di un catalogo di prova | distanza uguale a `SkyCoord.separation` sulle stesse posizioni; estremi = posizioni delle sorgenti | ricalcolo con Astropy |
| T11 | Selezione errata (F1) | selezionare una o tre sorgenti | `SELECTION_NOT_TWO_SOURCES` | test di unità |
| T12 | Epoche diverse (F1) | due sorgenti di cataloghi con epoche diverse e moto proprio noto | distanza calcolata dopo la propagazione del modulo 10; epoca usata nel risultato | ricalcolo con `apply_space_motion` nel test |
| T13 | Offset tra due punti | `angular_offsets` su coppie scelte dal tester | uguali a `SkyCoord.spherical_offsets_to` ricalcolato nel test; `apply_offsets` con quegli offset torna al secondo punto entro 1e-9 gradi | ricalcolo con Astropy |
| T14 | Calcolo inverso | `offset_position` con distanza e PA dati | uguale a `SkyCoord.directional_offset_by`; `angular_distance` e `position_angle` dal punto di partenza restituiscono distanza e PA dati entro 1e-9 gradi | ricalcolo con Astropy |
| T15 | Input non valido | distanza negativa o senza unità | `OFFSET_INVALID` | test di unità |

## 13. Decisioni aperte

- **D17-1 — Position angle (F2): DECISA il 2026-10-04 — inclusa per decisione
  del proprietario** (parità con Aladin = minimo). Funzione descritta in §3/§7
  con casi limite in §10; la riga F2 in `03-parita-aladin.md` è passata da
  `non trovata` a `inclusa (decisione del proprietario)` — non serve riga
  extra X. Restano verifiche tecniche di implementazione (polidi, frame).
- **D17-2 — Confini con 41: DECISA il 2026-10-04.** **Geometria nel `17`,
  rendering nel `41`.** **Motivazione:** la regola strutturale
  "l'interfaccia non fa calcoli" (`01-architettura.md` §3) e il riuso delle
  forme geometriche da parte di `16-core-moc.md` e `20-analisi-fotometria.md`.
  Conferma §3/§4/§9 di questo file.
- **D17-3 — Persistenza dei tag/marcature: DECISA il 2026-10-04.** Tag
  **nel file di sessione di `24-analisi-pipeline-riproducibili.md`,
  condiviso con i segnalibri di `40-ui-finestra-principale.md`**; la sessione
  salva **riferimenti ai file e operazioni eseguite (non i pixel) e deve
  poter essere rieseguita**. **Motivazione:** A12 e H13 prevedono persistenza
  insieme alla sessione, un formato unico evita divergenze e il 17 resta senza
  I/O su disco. Applicata in §3/§7 qui sopra.
- **D17-4 — Confini con 20: DECISA il 2026-10-04.** La lettura pixel resta
  qui; **la fotometria (F4) sta interamente nel `20-analisi-fotometria.md`**,
  statistiche su cerchio/poligono comprese. **Motivazione:** la fotometria è
  livello 2 per definizione (panoramica §3), evita test duplicati e mantiene
  `17` al livello 1. Applicata in §3 qui sopra.
- **D17-5 — Interpolazione dei profili: DECISA il 2026-10-12 (decisione del
  proprietario).** **Interpolazione bilineare** tramite
  `scipy.ndimage.map_coordinates` (`order=1`); **passo obbligatorio, senza
  default** (`PROFILE_STEP_INVALID` se non positivo o non finito).
  **Motivazione:** la bilineare non inventa strutture tra i pixel e coincide
  con il valore del pixel nei centri; senza un default il passo è sempre una
  scelta dichiarata dell'utente. Applicata in §3 (P2).
- **D17-7 — Geometria sferica delle forme (P3): DA DECIDERE (aperta il
  2026-10-12, Gruppo 3).** (a) **Libreria per poligoni e tracciati chiusi:**
  proposta `spherical-geometry` (STScI, BSD-3-Clause, 1.4.0) per area e
  "contiene" esatti con lati di cerchio massimo; alternativa: `mocpy`
  (già presente) con risultato approssimato per celle, dichiarato con
  l'ordine usato. (b) **Definizione dell'ellisse sulla sfera:** per esempio
  insieme dei punti la cui somma delle distanze angolari dai due fuochi è
  ≤ 2a (definizione intrinseca, "contiene" esatto con Astropy, area con
  integrazione numerica dichiarata), oppure ellisse nel piano tangente
  (proiezione gnomonica) al centro. (c) Senso di `contains` e `area` per
  `Arrow`, `Text` e `Freehand` aperto (oggi non definiti: proposta
  `OPERATION_UNSUPPORTED` per freccia e testo; tracciato libero come
  poligono solo se chiuso). **Raccomandazione:** (a) `spherical-geometry`,
  (b) somma delle distanze dai fuochi, (c) come proposto. Ferma solo P3.
- **D17-6 — Tag "distanza con profilo" (H11): DECISA il 2026-10-09 (decisione
  del proprietario sulla checklist del livello 1).** **distanza + profilo di
  intensità lungo il segmento + grafico esportabile**. **Motivazione
  (nostra, 2026-10-10):** il profilo lungo un segmento è il modo diretto per
  misurare estensione e separazione di strutture (bordi, getti, coppie di
  sorgenti) insieme alla loro distanza; il grafico esportabile con i valori
  rende la misura riusabile e riproducibile fuori dall'applicazione. La
  funzione copre la riga H11 di `03-parita-aladin.md` (parità).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). Perimetro da F1–F3 e H11 di `03-parita-aladin.md`. |
| 2026-10-04 | agente di sviluppo | **F2 inclusa per decisione del proprietario:** position angle tra due punti o lungo una linea, convenzione nord→est e casi limite ai poli descritti in §3/§7; nuovo caso limite `PA_UNDEFINED` ai poli (§10); test T8–T9 (§12); D17-1 chiusa come decisa (§13). Riga F2 in `03-parita-aladin.md` passata a `inclusa (decisione del proprietario)`. |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario: D17-2, D17-3 e D17-4 passate da aperte a decise.** D17-2: geometria nel 17, rendering nel 41 (conferma §3/§4/§9). D17-3: tag nel file di sessione del 24, condiviso con i segnalibri di 40; la sessione salva riferimenti a file e operazioni (non i pixel) ed è rieseguibile (§3/§7). D17-4: fotometria F4 interamente nel 20 (§3). Decisioni riportate in `decisioni-aperte.md`. |
| 2026-10-08 | Claude Code | §5: aggiunti a "Usato da" i moduli `18-core-calcolatrici.md` (scritti il 2026-10-08, stato bozza). Nessun altro testo cambia. |
| 2026-10-09 | Claude Code | **D17-6 DECISA** (checklist del livello 1): distanza + profilo + grafico esportabile, come lo strumento "dist" di Aladin. |
| 2026-10-09 | Claude Code | **Completamento con gli esiti di AP5** (decisione del proprietario del 2026-10-09): §3, §6, §7, §10, §12 per F1 (misura automatica della distanza tra due sorgenti di catalogo selezionate, con epoca mai assunta e stesso `body`). Nessuna nuova decisione dei Gruppi 1 e 2. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** (regola del proprietario del 2026-10-09): modulo completato con gli esiti di AP5, nessuna decisione aperta nei Gruppi 1 e 2. |
| 2026-10-09 | Claude Code | **Decisione del proprietario D10-8 (modulo 10) applicata** (autorizzazione esplicita a modificare il file approvato): offset angolari e calcolo inverso (posizione da distanza + angolo di posizione) spostati qui dalla calcolatrice delle coordinate del 10 — §3, §5, §6, §7 (`angular_offsets`, `apply_offsets`, `offset_position`), §10 (`OFFSET_INVALID`), §11, §12 (T13–T15). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Regola d'oro n. 8** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): D17-6 con motivazione nostra al posto di "come lo strumento dist di Aladin". Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **D13-10** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): `angular_distance` usa l'implementazione unica di `skydist` del 13 (`astropy.coordinates.angular_separation`), nessun duplicato. Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **Decisioni del proprietario del 2026-10-12** (autorizzazione esplicita a modificare il file approvato): divisione in 4 parti (P1 misure angolari, P2 pixel e profili, P3 forme e tag, P4 distanza automatica); **D17-5 decisa** (bilineare con `scipy.ndimage.map_coordinates`, passo obbligatorio senza default); verifiche di Astropy per la PA (casi indefiniti controllati prima) e per gli offset; scelte minori di P1, P2, P4 in §3; nuovi casi in §10; **P3 ferma** dopo la verifica (nessun calcolo esatto con `astropy`/`mocpy`), nuova decisione aperta **D17-7** (Gruppo 3) con la proposta `spherical-geometry` (BSD-3-Clause). Stato `approvato` invariato. |
