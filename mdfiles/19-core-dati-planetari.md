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
| in | file PDS | percorso o URL | PDS4 (obbligatorio); PDS3 solo con libreria consolidata (D19-2) | |
| out | coordinate planetarie convertite | float64 | gradi + corpo + convenzioni dichiarati | mai coordinate "nude" |
| out | esito del controllo di sovrapposizione | struttura | compatibile / errore con i corpi coinvolti | |
| out | elenco delle collezioni per corpo | lista | identificativi e proprietà delle collezioni | per il ramo "Sistema solare" |

## 7. Interfaccia pubblica

Nomi proposti, descrizione in parole (nessun codice). File Python previsto:
`src/astrotwo/core/planetary_data.py`.

- **`PlanetaryBody`** (classe): nome IAU del corpo e costanti di forma e
  rotazione lette dalla libreria scelta (D19-1); non si crea senza fonte.
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
- **`load_pds_image(source)`** — legge un'immagine PDS4 (PDS3 se ammesso da
  D19-2b) in questo modulo; restituisce immagine, metadati e corpo.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| Rapporto IAU WGCCRE (coordinate cartografiche ed elementi di rotazione) | forma, orientamento e convenzioni dei corpi | riferimento ufficiale della comunità planetaria |
| EPN-TAP (standard IVOA) | interrogazioni ai servizi planetari | standard del Virtual Observatory planetario |
| HiPS (standard IVOA) | superfici planetarie | stesso formato dei HiPS celesti; metadati del corpo **da verificare** nello standard |
| MOC (standard IVOA) | coperture planetarie | supporto planetario **da verificare** (D19-7) |
| Formato PDS (Planetary Data System) | immagini planetarie | formato standard degli archivi planetari della NASA |
| `spiceypy` + kernel PCK generici della NAIF (D19-1) | conversioni di convenzione, costanti dei corpi | licenze e installazione **da verificare prima del codice** |
| `pds4_tools` (PDS4), `pdr` da valutare (PDS3) (D19-2b) | lettura delle immagini PDS | licenze e installazione **da verificare prima del codice** |
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
| File PDS illeggibile o versione non supportata | nessuna immagine aperta | `PDS_UNREADABLE` |
| Servizio EPN-TAP non raggiungibile | errore del modulo 14 inoltrato | `NET_TIMEOUT` |
| Opzione dei dati planetari disattivata | rifiuto con indicazione della preferenza | `PLANETARY_DATA_DISABLED` |
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
| T5 | Latitudine planetocentrica ↔ planetografica | convertire una latitudine scelta dal tester per un corpo con schiacciamento noto | coincide con la libreria di D19-1; ritorno entro 1e-9 gradi | ricalcolo con la libreria |
| T6 | Convenzione mancante | posizione senza tipo di latitudine | `PLANETARY_CONVENTION_REQUIRED` | test di unità |
| T7 | EPN-TAP | query EPN-TAP su un servizio simulato | tabella con corpo e convenzioni dichiarati | servizio simulato (test di rete separato per il servizio reale) |
| T8 | Immagine PDS | leggere un file PDS di esempio fornito dalla libreria scelta | immagine aperta con metadati del corpo; valori uguali a quelli letti dalla libreria | confronto con la libreria di D19-2 |
| T9 | Opzione disattivata | chiamare una funzione del modulo con l'opzione disattivata | `PLANETARY_DATA_DISABLED`; funzioni celesti non toccate | test di unità |
| T11 | Sovrapposizione forzata | ripetere T1 con l'opzione di forzatura | sovrapposizione eseguita, avviso `BODY_MISMATCH_FORCED` nel risultato e nel comando registrato | test di unità |
| T10 | Riproducibilità | rieseguire il comando registrato di T4 e T5 | risultati identici | confronto con il registro del modulo 24 |

## 13. Decisioni aperte

- **D19-1 — Libreria per i sistemi planetari: DECISA il 2026-10-09 (decisione
  del proprietario sulla checklist del livello 1).** **`spiceypy`** con i
  **kernel PCK generici della NAIF**, versione dichiarata nel risultato. **Da
  verificare prima del codice:** licenze di `spiceypy` e dei kernel,
  installazione su macOS, assenza di sistemi fissi ai corpi in Astropy.
- **D19-2 — Formato PDS: DECISA il 2026-10-08 (decisione del proprietario).**
  Lettura PDS **nel modulo 19**, non nell'11; **PDS4 obbligatorio**; PDS3 solo
  se esiste una libreria consolidata.
- **D19-2b — Libreria PDS e licenza: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** **`pds4_tools`** per PDS4;
  per PDS3 si valuta **`pdr`**. **Da verificare prima del codice:** licenze,
  manutenzione e installazione su macOS di entrambe.
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
  test.
- **D19-7 — MOC planetari: DECISA il 2026-10-09 (decisione del proprietario
  sulla checklist del livello 1).** **prima verificare** lo standard MOC 2.0 e
  `mocpy` (vincolo prima del codice); se non supportano coperture planetarie,
  MOC HEALPix con metadato `body` (D19-3), dichiarato come estensione di
  AstroTwo.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-08 | Claude Code | Creazione del file (stato: bozza). Origine: riga H21 di `03-parita-aladin.md` (manuale di Aladin ed. giugno 2022, sez. 5.21, 7.2, 8.1), modulo accettato in AM1 il 2026-10-08. Corpo mai assunto, nessuna sovrapposizione tra corpi diversi o tra dati celesti e planetari, convenzioni sempre dichiarate; dipendenze da 10, 11, 12, 13, 14, 16; decisioni aperte D19-1…D19-7. |
| 2026-10-09 | Claude Code | **Decisioni del proprietario del 2026-10-08:** D19-2 (PDS letto qui, PDS4 obbligatorio, PDS3 solo con libreria consolidata; resta aperta D19-2b su libreria e licenza, Gruppo 2), D19-3 (campo `body` obbligatorio nei moduli 12, 13, 14, 16; `celestial` ricavato dal sistema di coordinate) e D19-4 (errore di default, forzabile con opzione esplicita citata nel risultato; nuovo avviso `BODY_MISMATCH_FORCED`, test T11). §3, §5, §6, §7, §8, §9, §10, §12, §13 aggiornati. |
| 2026-10-09 | Claude Code | **D19-1, D19-2b, D19-5, D19-6, D19-7 DECISE** (checklist del livello 1): `spiceypy` + kernel PCK della NAIF; `pds4_tools` (PDS4) e `pdr` da valutare (PDS3); dati planetari disattivati per default; corpi con HiPS nel MocServer e nel kernel PCK, Luna e Marte obbligatori per i test; MOC planetari da verificare, altrimenti estensione con `body`. Le verifiche di licenza e supporto restano vincoli prima del codice. §3, §8 aggiornati. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-09. |
| 2026-10-10 | Claude Code | **Regola d'oro n. 8** (decisione del proprietario, autorizzazione esplicita a modificare il file approvato): D19-5 (dati planetari disattivati per default) resta, con motivazione nostra al posto di "come in Aladin" (§3 punto 9, §13); formato PDS motivato come standard degli archivi planetari (§3, §8). Stato `approvato` invariato. |
