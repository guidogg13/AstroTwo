# decisioni-aperte.md — tutte le decisioni aperte, smistate in tre gruppi

**Stato:** bozza

## 1. Scopo

Raccogliere **tutte** le decisioni ancora aperte del progetto in un unico
elenco e smistarle in tre gruppi, così che si sappia cosa va deciso **prima**
di scrivere altri file, cosa blocca **solo** l'approvazione del modulo
interessato e cosa può aspettare il codice.

Fonti:

- §13 dei file `10-…`–`17-…` (decisioni `D10-1`…`D17-6`): 40 aperte alla
  creazione di questo file, **19 decise il 2026-10-04** → 21 ancora aperte.
- `01-architettura.md` §5: `A1`, `A2`, `A5`, `A6`, `A8`, `A9` → **`A1` e
  `A5` decise il 2026-10-04**, restano 4.
- `03-parita-aladin.md` §6: `AP5` → **AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08** (decisa il
  2026-10-04; esito parziale 2026-10-04 = lette sezioni 1–5.7.2 e indice
  completo del manuale ed. febbraio 2021).
- `03-parita-aladin.md` §6: `AP6` (edizione di riferimento del manuale di
  Aladin) → aggiunta e **decisa il 2026-10-08**: edizione **giugno 2022**, la
  più recente ufficiale (§6).
- **Aggiunte il 2026-10-08 (completamento dell'elenco):** `AP1`, `AP2`,
  `AP3`, `AP4` da `03-parita-aladin.md` §6; parte aperta di `DC1`, `DC3`,
  `DC4` da `02-convenzioni.md` §9. `AP1` va nel Gruppo 3 con `A8`
  (decisione del proprietario); per le altre lo smistamento segue i criteri
  di §2 (proposto da Claude Code, **confermato dal proprietario il
  2026-10-08**): `AP2`,
  `AP3`, `DC1`, `DC3`, `DC4` nel Gruppo 2 (bloccano l'approvazione del file
  in cui si decidono), `AP4` nel Gruppo 3 (rinvia ad `A8`). **`AP3` decisa
  lo stesso giorno** (Aladin Lite escluso dalla parità) e tolta dal Gruppo 2.

**Raccolte alla creazione: 47 decisioni — Gruppo 1: 22 · Gruppo 2: 20 ·
Gruppo 3: 5.**

**Dopo le decisioni del 2026-10-04: 25 ancora aperte** — Gruppo 1: **0**
(le 22 sono tutte decise, §3) · Gruppo 2: 20 · Gruppo 3: 5.

**Dal 2026-10-24, con lo sprint 8c: 17 aperte** — Gruppo 1: **0** · Gruppo 2: **2** (`A2`, `A6`) · Gruppo 3: **15** (nuova `D40-7` — messaggi annidati nel catalogo, oggi parametri esterni nella lingua del modulo; prima nel file di origine 40 §13).

Prima, **dal 2026-10-24, con lo sprint 8b: 16 aperte** — Gruppo 1: **0** · Gruppo 2: **2** (`A2`, `A6`) · Gruppo 3: **14** (decisa `D40-5` — catalogo dei messaggi nel modulo neutro `src/astrotwo/messages_catalog.py`; nuova e decisa subito `D40-6` — varianti per `reason` nelle voci del catalogo; prima nel file di origine 40 §13).

Prima, **dal 2026-10-24, con lo sprint 8 (D40-3): 17 aperte** — Gruppo 1: **0** · Gruppo 2: **2** (`A2`, `A6`) · Gruppo 3: **15** (decisa `D40-3` — messaggi dei moduli in inglese e italiano con `params` nei moduli, solo specifiche; nuove `D40-5` posizione del catalogo, `D41-7` P1 e `D41-8` P5 non raggiunti; prima nei file di origine 40 §13 e 41 §13).

Prima, **dal 2026-10-23, con lo sprint 7c: 15 aperte** — Gruppo 1: **0** · Gruppo 2: **2** (`A2`, `A6`) · Gruppo 3: **13** (decise `D32-1` — (c) identificativi del gruppo fisso nella descrizione, (b) tabelle che cominciano con l'identificativo in `CATALOG_UNKNOWN` — e `D13-21` — colonne candidate nel messaggio di `NO_COORD_COLUMNS`; prima nei file di origine 32 §13 e 13 §13; nuova `D32-2`, comando di ricerca nell'elenco dei cataloghi, rinviata a dopo la v1).

Prima, **dal 2026-10-23, con lo sprint 7b del 44: 16 aperte** — Gruppo 1: **0** · Gruppo 2: **2** (`A2`, `A6`) · Gruppo 3: **14** (nuove `D32-1`, identificativo di un catalogo VizieR per l'assistente, e `D13-21`, colonne ambigue in una regione chiesta dall'assistente).

Prima, **dal 2026-10-21, con lo sprint 4f del 41: 14 aperte** — Gruppo 1: **0** · Gruppo 2: **2** (`A2`, `A6`) · Gruppo 3: **12** (`D41-6` decisa dal proprietario il 2026-10-21: il 13 conserva l'epoca del COOSYS; prima nel file di origine, 13 §13 e 41 §13).

Prima, **dal 2026-10-21, con lo sprint 4e del 41: 15 aperte** — Gruppo 1: **0** · Gruppo 2: **2** (`A2`, `A6`) · Gruppo 3: **13** (nuova `D41-6`, epoca del COOSYS persa da `catalog.set_columns`; `D41-5` rinviata a dopo la v1, contata tra le aperte).

Prima, **dal 2026-10-20, con lo sprint 4d del 41: 14 aperte** — Gruppo 1: **0** · Gruppo 2: **2** (`A2`, `A6`) · Gruppo 3: **12** (nuova `D41-5`, zoom e spostamento su una griglia di pixel).

Prima, **dal 2026-10-17, con la decisione di A11 (GPL-3.0-or-later): 13 aperte** — Gruppo 1: **0** · Gruppo 2: **2** (`A2`, `A6`) · Gruppo 3:
**11**. A11 decisa dal proprietario il 2026-10-17 (prima nel file di origine `01` §6.1); il `60` resta bloccato solo da `A2` e `A6`.

Prima, **dal 2026-10-17, con la decisione di D40-4 (⌃⌘N): 14 aperte** — Gruppo 1: **0** · Gruppo 2: **3** · Gruppo 3:
**11**.

Prima, **dal 2026-10-17, con la parte 3b del codice della v1: 15 aperte** — Gruppo 1: **0** · Gruppo 2: **3** · Gruppo 3:
**12** (nuova `D40-4`, scorciatoia della modalità notte).

Prima, **dal 2026-10-15, dopo le decisioni del proprietario sulle specifiche dell'interfaccia: 14 aperte** — Gruppo 1:
**0** · Gruppo 2: **3** (`A2`, `A6`, `A11`; decise `D05-1`, `D05-2`, `D40-1`, `D41-1`, `D41-2`, `D41-3`) · Gruppo 3:
**11** (decisa `D41-4`, resta da compilare il Mac di riferimento; rimandate `D05-3` e `D40-2`; nuova `D40-3` messaggi
dei moduli in inglese con traduzione). **05, 40, 41, 42 non hanno più decisioni dei Gruppi 1 e 2 aperte.**

Prima, **sempre il 2026-10-15, con le specifiche della prima versione dell'interfaccia (05, 40, 41, 42): 20 aperte** — Gruppo 1:
**0** · Gruppo 2: **9** (`A2`, `A6`, `A11`; decisa `A9`; nuove `D05-1` classi dei comandi e letture passive, `D05-2`
dati di rete diversi alla riapertura, `D40-1` lingua dei messaggi dei moduli, `D41-1` thread delle letture passive
di rete, `D41-2` scrittura dei numeri mostrati, `D41-3` limiti iniziali di visualizzazione) · Gruppo 3: **11**
(decise `D10-9` soglia `TAN`/`AIT` 30° e `D11-8` corona del centroide 1 × / 1,5 × `box_size`; nuove `D05-3` adattatore
del 19, `D40-2` avvio tramite URL, `D41-4` Mac di riferimento e test `perf`/`gl`).

Prima, **dal 2026-10-14, dopo la decisione su D16-8: 14 aperte** — Gruppo 1: **0** · Gruppo 2: **4** (`A2`, `A6`, `A9`,
`A11`) · Gruppo 3: **10** (decisa `D16-8`, MOC da immagine con i blocchi più gli angoli di contorno; nuova `D14-13`,
reindirizzamento http → https dell'ESO).

Prima, **sempre il 2026-10-14: 14 aperte** — Gruppo 3: **10** (nuova `D16-8`).

Prima, **dal 2026-10-13, livello 1 chiuso (decisioni del proprietario su D17-9, D19-8, D19-9): 13 aperte** — Gruppo 1:
**0** · Gruppo 2: **4** (`A2`, `A6`, `A9`, `A11`) · Gruppo 3: **9** (decise `D17-9` `distance_to` per ellisse,
freccia, testo e tracciato aperto e `D19-9` PDS da URL; `D19-8` PDS3 **rimandata, bassa priorità**, resta nel
Gruppo 3 come `D13-14c`).

Prima, **dal 2026-10-13, con i pezzi fermi di 17 e 18 chiusi e il modulo 19: 15 aperte** — Gruppo 1: **0** · Gruppo 2:
**4** (`A2`, `A6`, `A9`, `A11`) · Gruppo 3: **11** (decise dal proprietario il 2026-10-13 `D17-8` significato di
`distance_to` e `D18-7` sessagesimali in `skydist`; nuove `D17-9` `distance_to` per le altre forme, `D19-8` PDS3
con `pdr`, `D19-9` PDS da URL, che fermano solo quei pezzi).

Prima, **dal 2026-10-13, con P3 del 17 e il modulo 18: 14 aperte** — Gruppo 1: **0** · Gruppo 2: **4** (`A2`, `A6`, `A9`,
`A11`) · Gruppo 3: **10** (decise dal proprietario il 2026-10-12 `D17-7` geometria sferica delle forme, `D18-5`
limiti delle espressioni, `D18-6` valore grezzo con `do_not_scale_image_data`; nuove `D17-8` significato di
`distance_to` e `D18-7` sessagesimali in `skydist`, che fermano solo quei pezzi).

Prima, **dal 2026-10-12, con il modulo 17: 15 aperte** — Gruppo 1: **0** · Gruppo 2: **4** (`A2`, `A6`, `A9`,
`A11`) · Gruppo 3: **11** (decise dal proprietario `D12-6` nomi dei corpi con una tabella del 19, `D12-7`
eclittica non supportata finché non verificata, `D12-8` nessun Allsky per ora, `D17-5` profili bilineari
con passo obbligatorio; nuova dal 17 `D17-7` geometria sferica delle forme, che ferma solo P3).

Prima, **sempre il 2026-10-12: 18 aperte** — Gruppo 1: **0** · Gruppo 2: **4** (`A2`, `A6`, `A9`, `A11`) ·
Gruppo 3: **14** (decise dal proprietario `D16-6`, nessuna versione 2.1 tra i documenti IVOA
nemmeno come bozza, resta rifiutata, e `D16-7`, complemento degli ST-MOC con le operazioni di
`mocpy`; `A10` decisa anche per gli HiPS e tolta; nuove dal codice del 12 `D12-6` nomi dei corpi
planetari, `D12-7` `hips_frame = ecliptic`, `D12-8` file `Allsky`).

Prima, **dal 2026-10-11, con il modulo 16 scritto: 18 aperte** — Gruppo 1: **0** · Gruppo 2: **4**
(`A2`, `A6`, `A9`, `A11`) · Gruppo 3: **14** (decise dal proprietario `D13-20` sistema di SIMBAD
dall'`utype` MANGO, `D15-8` corpo nel join solo se entrambe le tabelle lo hanno, `D15-9`
`selection=all` e `best` in locale; nuove dal codice del 16 `D16-6` versione 2.1 del formato
MOC e `D16-7` complemento dei MOC spazio-temporali).

Prima, sempre il 2026-10-11, con il modulo 15 scritto: 19 aperte — Gruppo 1: **0** · Gruppo 2: **4**
(`A2`, `A6`, `A9`, `A11`) · Gruppo 3: **15** (decise `D13-19` regione di `load_catalog` e
`D15-6` soglia delle ellissi; nuove `D13-20` sistema di SIMBAD, `D15-8` corpo nella
correlazione per campo, `D15-9` `best` con il servizio CDS).

Prima, sempre il 2026-10-11, con le decisioni del proprietario sui pezzi fermi: 18 aperte — Gruppo 1:
**0** · Gruppo 2: **4** (`A2`, `A6`, `A9`, `A11`) · Gruppo 3: **14** (decise `D14-10`,
`D14-11`, `D14-12`, `D13-17`, `D13-18`; nuove `D13-19` regione di `load_catalog` e
`D13-14c` traduzione UCD1 del CDS, rimandata a bassa priorità).

Prima, il 2026-10-10, con il modulo 14 scritto e P6 del 13: 21 aperte — Gruppo 1: **0** ·
Gruppo 2: **4** (`A2`, `A6`, `A9`, `A11`) · Gruppo 3: **17** (decisa `D14-5`; nuove `D14-10`,
`D14-11`, `D14-12`, `D13-17`, `D13-18`).

Prima, sempre il 2026-10-10, con il modulo 13 completo fino a P5: 17 aperte — Gruppo 1: **0** ·
Gruppo 2: **4** (`A2`, `A6`, `A9`, `A11`) · Gruppo 3: **13** (decise `D13-14b`, `D13-15`,
`D13-16`).

Prima, sempre il 2026-10-10, dopo P2–P5 del modulo 13: 20 aperte — Gruppo 1: **0** ·
Gruppo 2: **4** (`A2`, `A6`, `A9`, `A11`) · Gruppo 3: **16** (decise `D13-10`…`D13-14`
tranne il punto b; nuove `D13-14b` UCD1 → UCD1+, `D13-15` numeri e unità nelle colonne
calcolate, `D13-16` filtro temporale).

Prima, sempre il 2026-10-10, dopo le decisioni sul modulo 13: 22 aperte — Gruppo 1: **0** ·
Gruppo 2: **4** (`A2`, `A6`, `A9`, `A11`) · Gruppo 3: **18** (chiuse `D13-4` e `D13-8`;
`A10` ora solo per gli HiPS; nuove `D13-10`…`D13-14`, che bloccano P2, P4, P5 e i
sottoinsiemi salvati del 13).

Prima, sempre il 2026-10-10, con la nuova `A11` (licenza): 19 aperte — Gruppo 1: **0** ·
Gruppo 2: **4** (`A2`, `A6`, `A9`, `A11`, che bloccano solo `60` e `40`) · Gruppo 3:
**15** (`A10` ora solo per cataloghi e HiPS).

Prima, sempre il 2026-10-09, con la nuova `D11-8`: 18 aperte — Gruppo 1: **0** · Gruppo 2:
**3** (`A2`, `A6`, `A9`, che bloccano solo `60` e `40`) · Gruppo 3: **15** (`D10-9`
si decide con il `41`; `D11-8` con `20` e `41`).

Prima, sempre il 2026-10-09, dopo le decisioni su `04-cache.md` (CA1–CA4) e D11-7: 17 aperte.

Prima, sempre il 2026-10-09, dopo le decisioni D10-7 e D10-8: 22 aperte — Gruppo 1: **0** ·
Gruppo 2: **7** (`A2`, `A6`, `A9`; `CA1`–`CA4` di `04-cache.md`) · Gruppo 3: **15**
(chiuse `D10-7` e `D10-8`; nuove `D10-9` e `D11-7`).

Prima, sempre il 2026-10-09, FASE: CODICE – livello 1 (verifiche del modulo 10): 18 aperte
— Gruppo 1: **0** · Gruppo 2: **3** (`A2`, `A6`, `A9`) · Gruppo 3: **15** (nuove
`D10-7` e `D10-8`, che bloccano ora parti del codice del modulo 10).

Prima, sempre il 2026-10-09 (decisioni su D11-6, D13-7, D14-7, D14-8, D15-5): 16 aperte
— Gruppo 1: **0** · Gruppo 2: **3** (`A2`, `A6`, `A9`, che bloccano solo `60` e
`40`) · Gruppo 3: **13** (nuova `D15-6`). **Nessuna decisione dei Gruppi 1 e 2
riguarda il livello 1.**

Prima, sempre il 2026-10-09 (completamento dei moduli 11–17 con gli esiti di AP5): 20
aperte — Gruppo 1: **0** · Gruppo 2: **8** (`A2`, `A6`, `A9` per `60`/`40`;
nuove `D11-6`, `D13-7`, `D14-7`, `D14-8`, `D15-5`, che lasciano in bozza 11,
13, 14 e 15) · Gruppo 3: **12** (nuova `D13-8`).

Prima, sempre il 2026-10-09 (checklist del livello 1): 14 aperte — Gruppo 1: **0** ·
Gruppo 2: **3** (`A2`, `A6`, `A9`: bloccano solo `60` e `40`, con
orientamento) · Gruppo 3: **11** (aggiunte `A10`, `D10-6`). Decise 30
raccomandazioni della checklist: DC1, DC3, DC4, AP2, D10-1, D11-2, D11-4,
D11-5, D12-1, D12-3, D12-4, D13-3, D14-3, D14-4, D14-6, D15-1…D15-4, D16-4,
D17-6, D18-1…D18-4, D19-1, D19-2b, D19-5, D19-6, D19-7 (testo nei file di
origine; le verifiche "da verificare" restano vincoli prima del codice).
**Nessuna decisione dei Gruppi 1 e 2 blocca più 01, 02, 03 e 10–19.**

Prima, sempre il 2026-10-09 (decisioni su D19-2, D19-3, D19-4): 42 aperte — Gruppo 1: **0** · Gruppo 2: **33** (tolta `D19-4`,
aggiunta `D19-2b`) · Gruppo 3: 9. Smistamento delle 13 decisioni dei moduli 18
e 19 **confermato dal proprietario**.

Dopo la scrittura di 18 e 19, il 2026-10-08: 44 aperte — Gruppo 1:
**2** (`D19-2`, `D19-3`) · Gruppo 2: **33** (+ `D18-1`…`D18-4`, `D19-1`,
`D19-4`…`D19-7`) · Gruppo 3: **9** (+ `D18-5`, `D18-6`). Smistamento delle 13
nuove decisioni proposto da Claude Code secondo §2 (poi confermato).

Dopo le decisioni del proprietario, sempre il 2026-10-08: 31 aperte — Gruppo 1:
**0** (AM1 per H21 accettata: nuovo modulo `19-core-dati-planetari.md`) ·
Gruppo 2: 24 · Gruppo 3: 7.

Dopo la lettura AP5, sempre il 2026-10-08: 32 aperte — Gruppo 1: 1 (proposta
AM1 per H21, dati planetari) · Gruppo 2: 24 · Gruppo 3: 7.

Prima della lettura AP5, sempre il 2026-10-08: 31 aperte — Gruppo 1: 0 · Gruppo 2: **24** (aggiunte
`AP2`, `DC1` parte aperta, `DC3`, `DC4`; `AP3` e `AP6` aggiunte e decise lo
stesso giorno) · Gruppo 3: **7** (aggiunte `AP1`, `AP4`).

Fuori da questo elenco (già chiuse): **D12-2** (HiPS da ID/URL, inclusa) e
**D17-1** (position angle, inclusa); **D14-2** è chiusa dal 2026-10-04 (parte
tecnica decisa).

## 2. Criteri di smistamento

- **GRUPPO 1 — BLOCCANTI PER ALTRI MODULI:** la scelta cambia le specifiche
  di moduli successivi (convenzioni di coordinate, unità, formati dati,
  cache, librerie condivise, interfacce tra moduli). Vanno decise **prima**
  di scrivere i file che ne dipendono. **Stato: 0 aperte — le 22 decisioni
  del gruppo sono state decise il 2026-10-04 (§3).**
- **GRUPPO 2 — BLOCCANTI SOLO PER L'APPROVAZIONE DEL MODULO STESSO:** non
  impediscono di scrivere altri file, ma quel modulo non è `approvato` finché
  non sono risolte.
- **GRUPPO 3 — RIMANDABILI AL MOMENTO DEL CODICE:** dettagli implementativi o
  valori numerici che nessun altro `.md` richiede; si fissano quando si
  scrive il codice e si registrano nel file.

Nessuna decisione è risolta **in questo file**: le raccomandazioni del
Gruppo 1 sono state **confermate dal proprietario il 2026-10-04** (esiti in
§3, dettaglio nei file di origine); le decisioni dei Gruppi 2 e 3 restano da
decidere (regola: le decisioni aperte si decidono, non si scelgono in
silenzio).

## 3. GRUPPO 1 — bloccanti per altri moduli (0 aperte: 22 decise il 2026-10-04; AM1 per H21, D19-2 e D19-3 decise il 2026-10-08; D05-4 aperta il 2026-10-16 e decisa il 2026-10-17)

**Decise di recente:** `D05-4` (forma JSON dei valori dei parametri del 05 e
parametri strutturati) — **decisa dal proprietario il 2026-10-17, opzione
(a)**: nuovo tipo `record` con campi tipizzati e forme JSON di ogni tipo in
`05-comandi-sessione.md` §3.1; parametri dei `calc.*` nel 18 §3.

**Decise:**

Tutte le decisioni di questo gruppo sono state **prese dal proprietario il
2026-10-04**. Sotto l'elenco sintetico con l'esito; la formulazione completa e
la motivazione restano nei file di origine (§13 dei moduli, §4.2/§9 di
`01-architettura.md`, §6 di `03-parita-aladin.md`) e il riepilogo in
`panoramica.md` §5. Ogni file di origine riporta anche dove la decisione è
stata applicata nel testo.

| # | Etichetta | Esito (2026-10-04) | File di origine |
|---|---|---|---|
| 1 | `A1` | **PySide6 (Qt)**; il rendering delle mappe con OpenGL si specifica in `41-ui-visualizzatore-cielo.md` | `01-architettura.md` §4.2, §9 |
| 2 | `A5` | Interfaccia **a capacità** (chiamata di strumenti, streaming); due implementazioni iniziali: **provider cloud** e **endpoint compatibile OpenAI** | `01-architettura.md` §4.2, §9 |
| 3 | `AP5` | **AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08**: le sezioni si leggono prima di scrivere i gruppi successivi (prima di 20–24 e dei gruppi seguenti). Esito parziale 2026-10-04: lette sezioni 1–5.7.2 e indice completo (ed. febbraio 2021); esistenza di tutte le funzioni verificata dall'indice | `03-parita-aladin.md` §2, §6 |
| 4 | `D10-2` | Epoca di ogni dato **letta dai suoi metadati, mai assunta**; epoca di visualizzazione = epoca dell'immagine se nota, altrimenti **J2000**; **epoca usata sempre scritta nel risultato**; ogni catalogo ha la **propria epoca di riferimento** (insieme a `D13-2`) | `10-core-coordinate-wcs.md` §13, `02-convenzioni.md` DC2 |
| 5 | `D10-3` | Cache della risoluzione nomi in **tabella SQLite separata dentro la cache A7** | `10-core-coordinate-wcs.md` §13 |
| 6 | `D10-4` | **Stessa lista di proiezioni di Aladin** (da verificare con `AP5`); **`TAN`** default per le immagini, **`AIT`** per le viste a cielo intero; **un test per proiezione** (T7) | `10-core-coordinate-wcs.md` §13, §12 |
| 7 | `D11-1` | **Tipo nativo del file in memoria**; **ogni calcolo in `float64`**; **`float32` solo per la visualizzazione** (regola scritta in DC6) | `11-core-immagini-fits.md` §13, `02-convenzioni.md` DC6 |
| 8 | `D11-3` | Limite cache su disco **5 GB di default**, **configurabile**, con **eliminazione dei dati meno usati** | `11-core-immagini-fits.md` §13 |
| 9 | `D12-5` | **Calcoli HEALPix nel 16, servizio dei tile nel 12** (stesso confine di `D16-5`) | `12-core-hips.md` §13 |
| 10 | `D13-1` | **Stringa con grammatica ristretta** (in origine "basata su quella di Aladin"; **riscritta il 2026-10-10 come grammatica nostra**, regola d'oro n. 8): testo con jolly `?` e `*`; colonna con operatori `=`, `!=`, `<`, `>`, `<=`, `>=`; valore assoluto `\|colonna\|`; prefissi `+` e `-` per aggiungere/togliere dalla selezione; **validata prima dell'esecuzione** | `13-core-cataloghi.md` §13 |
| 11 | `D13-2` | Con `D10-2`: epoca dai metadati e **mai assunta**; epoca di visualizzazione = epoca del dato mostrato; **epoca usata sempre scritta nel risultato** | `13-core-cataloghi.md` §13, `02-convenzioni.md` DC2 |
| 12 | `D13-5` | Operazioni sulle tabelle **sempre non distruttive**; in-place solo con **flag esplicito citato nel report** | `13-core-cataloghi.md` §13 |
| 13 | `D13-6` | **Colonna DataLink nel 13, risoluzione dei link nel 14** | `13-core-cataloghi.md` §13 |
| 14 | `D14-1` | **`pyvo` per TAP e DataLink**; per SAMP si **valuta `astropy.samp` (da verificare)**; **licenze da riverificare prima di approvare il 14** — **aggiornata il 2026-10-10:** SAMP con **`pyvo.samp`** (`astropy.samp` deprecato da astropy 8.0); licenze verificate (`pyvo` BSD-3, `astroquery` BSD) | `14-core-protocolli-vo.md` §13, §8 |
| 15 | `D14-2` | **Collegarsi a un hub SAMP già attivo se c'è, altrimenti avviarne uno proprio**; **primo perimetro: tabelle, selezioni, puntamenti**; **le immagini restano un'estensione prevista** | `14-core-protocolli-vo.md` §13, §3, §7 |
| 16 | `D16-1` | **`mocpy`**; **licenza e installazione su macOS da verificare prima di approvare il 16** | `16-core-moc.md` §13, §8 |
| 17 | `D16-2` | **MOC in cache in formato FITS standard IVOA**; **export anche JSON e testo** | `16-core-moc.md` §13 |
| 18 | `D16-3` | **Tempo numerico internamente (JD tramite `astropy.time`)**; **ISO 8601 solo nell'interfaccia e nei file**; **scala di tempo sempre dichiarata (UTC, TDB, TCB)**; **MOC temporali con la scala dello standard IVOA (da verificare)** (regola in DC1) | `16-core-moc.md` §13, `02-convenzioni.md` DC1 |
| 19 | `D16-5` | Con `D12-5`: **calcoli HEALPix nel 16, servizio dei tile nel 12** | `16-core-moc.md` §13 |
| 20 | `D17-2` | **Geometria nel 17, rendering nel 41** | `17-core-misure.md` §13 |
| 21 | `D17-3` | **Tag nel file di sessione del 24**, condiviso con i segnalibri di 40; la sessione salva **riferimenti ai file e operazioni eseguite (non i pixel)** e deve poter essere **rieseguita** | `17-core-misure.md` §13 |
| 22 | `D17-4` | **La fotometria (F4) sta interamente nel 20** | `17-core-misure.md` §13 |

**Aperte nel Gruppo 1 il 2026-10-08 (dalla scrittura di `19-core-dati-planetari.md`) e decise lo stesso giorno dal proprietario:**

| Etichetta | Domanda | Modulo |
|---|---|---|
| `D19-2` | Formato PDS: quali versioni, con quale libreria e in quale modulo? — **DECISA:** lettura nel modulo 19 (non nell'11), PDS4 obbligatorio, PDS3 solo con libreria consolidata; libreria e licenza restano aperte come `D19-2b` (Gruppo 2) | `19-core-dati-planetari.md` |
| `D19-3` | Campo "corpo" nei moduli 12, 13, 14, 16? — **DECISA:** campo `body` obbligatorio nei metadati dei quattro moduli; per i dati astronomici `celestial` (sfera celeste), ricavato dal sistema di coordinate, mai assunto; applicata nei quattro file | `19-core-dati-planetari.md` (e 12, 13, 14, 16) |

**Aperta nel Gruppo 1 il 2026-10-08 e decisa lo stesso giorno:**

| Etichetta | Domanda | Modulo |
|---|---|---|
| `AM1` (H21) | Dati planetari (riga H21 di `03-parita-aladin.md`, trovata con la lettura AP5): modulo dedicato oppure estensione di `10` (sistemi di riferimento planetari), `12` e `13`? | `panoramica.md` §6 (AM1), `03-parita-aladin.md` H21 |

**Esito (decisione del proprietario, 2026-10-08): AM1 accettata** — nuovo
modulo `19-core-dati-planetari.md`, livello 1, registrato con stato `non
esiste` in `panoramica.md` e `INDICE.md`; riga H21 di `03-parita-aladin.md`
collegata al 19. Il Gruppo 1 era tornato vuoto; la scrittura del 19 ha poi
aperto `D19-2` e `D19-3` (tabella sopra).

Con il passo del 2026-10-04 il Gruppo 1 era rimasto **vuoto**: nessun'altra decisione blocca
la scrittura di moduli futuri oltre a quanto già previsto (AP5 prima dei
gruppi successivi, A8 dopo il livello 1).

## 4. GRUPPO 2 — bloccanti solo per l'approvazione del modulo (2)

| Etichetta | Domanda | Modulo |
|---|---|---|
| `A2` | Quale strumento produce il file `.dmg`? **Orientamento (2026-10-09): PyInstaller + dmgbuild** | `60-distribuzione-dmg.md` (blocca solo l'approvazione del 60) |
| `A6` | Si fa firma e notarizzazione Apple per il `.dmg`? **Orientamento (2026-10-09): sì, con account Apple Developer solo al momento della distribuzione** | `60-distribuzione-dmg.md` (blocca solo l'approvazione del 60) |

## 5. GRUPPO 3 — rimandabili al momento del codice (13)

| Etichetta | Domanda | Modulo |
|---|---|---|
| `D10-5` | Quale catalogo di riferimento e quali limiti di magnitudine per la calibrazione astrometrica (H6)? | `10-core-coordinate-wcs.md` |
| `A8` | Quale livello di compatibilità con lo scripting di Aladin? (già rimandata: dopo il completamento del livello 1) | `24-analisi-pipeline-riproducibili.md` (e `01-architettura.md`) |
| `AP1` | Validazione finale della parità: confronto di AstroTwo e Aladin sugli stessi dati (già rimandata: alla fine del progetto) | `03-parita-aladin.md` §6 |
| `AP4` | AstroTwo esegue gli script di Aladin o ha solo il proprio formato di pipeline? (rinvia ad `A8`: si decide insieme, dopo il livello 1) | `03-parita-aladin.md` §6 (e `24-analisi-pipeline-riproducibili.md`) |
| `D10-6` | Tempo massimo per le conversioni di massa di posizioni (valore e test)? | `10-core-coordinate-wcs.md` §9 (e `61`) |
| `D05-3` | Adattatore del 19 (`PlanetaryCommand`) al formato del 05: **rimandata** (2026-10-15) a quando l'interfaccia userà i dati planetari; modifica del 19 da autorizzare | `05-comandi-sessione.md` §13 |
| `D40-2` | Avvio tramite URL (H18): equivalente in AstroTwo, **rimandata** (2026-10-15) alla versione successiva del 40 | `40-ui-finestra-principale.md` §13 |
| `D41-5` | Zoom e spostamento su una griglia di pixel (immagine FITS senza WCS valido): i comandi di vista del 05 lavorano in coordinate celesti; nella v1 la griglia è inquadrata intera e senza zoom né spostamento col mouse. Aperta il 2026-10-20 (sprint 4d); **rinviata a dopo la v1** (decisione del proprietario del 2026-10-21); raccomandazione: modo «pixel» dei comandi di vista nella versione successiva (AM1) | `41-ui-visualizzatore-cielo.md` §13 |
| `D40-7` | Messaggi annidati nel catalogo (D40-3): i testi che incorporano un altro messaggio (causa di una copertura non disponibile, motivo di un tile corrotto, risposta del 14) usano un parametro esterno, nella lingua del modulo; opzione (b): tipo di parametro `message` (`{"code","params"}`) reso in modo ricorsivo nella lingua dell'interfaccia, raccomandata se l'inglese è un requisito della v1. Aperta il 2026-10-24 (sprint 8c) | `40-ui-finestra-principale.md` §13, `12-core-hips.md` §10 |
| `D41-7` | P1 non raggiunto: fotogramma con 1 milione di simboli 46,0 ms (95°) contro 16,7 ms sull'iMac M1 8 GB (disegno 37,9 ms, 4,6 ms senza simboli); causa nota: disegno dei simboli; obiettivo invariato; sprint di prestazioni dopo la prova completa. Aperta il 2026-10-24; da annotare per lo stesso sprint: `test_ai_panel::test_t14_latency` fallito una volta (170 ms) | `41-ui-visualizzatore-cielo.md` §13, §3.15 |
| `D41-8` | P5 non raggiunto: avvio a freddo 4,46 s contro 3 s sull'iMac M1 8 GB (importazioni 1,8 s, finestra 2,3 s, prima vista 0,3 s); obiettivo invariato; stesso sprint di prestazioni. Aperta il 2026-10-24 | `41-ui-visualizzatore-cielo.md` §13, §3.15 |
| `D19-8` | PDS3 con `pdr`: **rimandata, bassa priorità** (decisione del proprietario del 2026-10-13): per ora niente `pdr`, un'etichetta PDS3 dà `PDS_UNREADABLE` "formato PDS3 non ancora supportato" | `19-core-dati-planetari.md` §13 |
| `D14-13` | URL dei servizi dell'ESO in http (dal registro VO e nelle risposte SIA): il reindirizzamento a https codifica due volte l'URL e la richiesta viene rifiutata; oggi la demo usa https direttamente, nessuna modifica al codice del 14 | `14-core-protocolli-vo.md` §13 |
| `D32-2` | Comando di ricerca nell'elenco dei cataloghi per l'assistente (nuovo comando di sola lettura del `05` sull'albero delle collezioni del 13, poi esposto nel 32). Nata il 2026-10-23 dalla decisione su D32-1 (opzione (a)); **rinviata a dopo la v1** per decisione del proprietario | `32-ia-registro-strumenti.md` §13 |
| `D13-14c` | Traduzione UCD1 → UCD1+ con il servizio del CDS come opzione esplicita (D13-14b): **rimandata, bassa priorità** (decisione del proprietario del 2026-10-11) | `13-core-cataloghi.md` §13 |

## 6. Note

- Le decisioni chiuse non compaiono nei Gruppi 2 e 3: **D12-2** e **D17-1**
  (funzioni incluse con P11) e, dal 2026-10-04, tutte e 22 le decisioni del
  Gruppo 1 (§3), incluse **D14-2** (parte tecnica SAMP) e **D13-6**.
- Le 22 decisioni del Gruppo 1 **non sono state risolte in questo file**: sono
  state decise dal proprietario e riportate con data e motivazione nei file di
  origine (§13 dei moduli, §4.2/§9 di `01-architettura.md`, §6 di
  `03-parita-aladin.md`) e riepilogate in `panoramica.md` §5.
- Quando una decisione viene chiusa, si aggiorna il file di origine e poi
  questo elenco.
- Resta un impegno temporale legato a una decisione chiusa: **AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08**,
  prima di scrivere i gruppi successivi (prima di 20–24). Esito parziale 2026-10-04:
  lette sezioni 1–5.7.2 e indice completo (edizione febbraio 2021), esistenza
  di tutte le funzioni verificata dall'indice.
- **AP6** è chiusa dal 2026-10-08 (edizione di riferimento del manuale di
  Aladin = **giugno 2022**, la più recente ufficiale; dettaglio in
  `03-parita-aladin.md` §6, riepilogo in `panoramica.md` §5) e non compare più
  nel Gruppo 2.
- **AP3** è chiusa dal 2026-10-08: Aladin Lite **escluso dalla parità**
  (AstroTwo è un'app desktop; un'eventuale versione web richiederà una
  proposta AM1); dettaglio in `03-parita-aladin.md` §4/§6, riepilogo in
  `panoramica.md` §5.
- **D19-4** è chiusa dal 2026-10-08: sovrapposizione tra corpi diversi (o tra
  dati celesti e planetari) = errore di default, forzabile con un'opzione
  esplicita citata nel risultato (stesso schema di D13-5); dettaglio in
  `19-core-dati-planetari.md` §13.

## 7. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). Raccolte 47 decisioni aperte (§13 di `10`–`17`: 40; `A1`, `A2`, `A5`, `A6`, `A8`, `A9` da `01-architettura.md`; `AP5` da `03-parita-aladin.md`) e smistate: Gruppo 1 = 22 (con opzioni, raccomandazioni e dipendenze), Gruppo 2 = 20, Gruppo 3 = 5. Escluse le chiuse D12-2 e D17-1. Registrato in `INDICE.md` e linkato da `panoramica.md`. |
| 2026-10-04 | agente di sviluppo | **Gruppo 1 interamente deciso dal proprietario (22 decisioni):** `A1` (PySide6 con rendering OpenGL da specificare in 41), `A5` (interfaccia a capacità, provider cloud + endpoint compatibile OpenAI), `AP5` (sezioni 5.7.3–8 [indicate in origine come 5.9–8] del manuale di Aladin da leggere prima dei gruppi successivi), `D10-2`/`D13-2` (epoca dai metadati, mai assunta; epoca di visualizzazione = epoca dell'immagine se nota, altrimenti J2000; epoca sempre nel risultato; cataloghi con propria epoca di riferimento), `D10-3` (cache nomi in tabella SQLite separata dentro A7), `D10-4` (lista proiezioni = Aladin da verificare con AP5, `TAN` immagini/`AIT` all-sky, un test per proiezione), `D11-1` (tipo nativo in memoria, calcoli in float64, float32 solo display → DC6), `D11-3` (cache su disco 5 GB di default, configurabile), `D12-5`/`D16-5` (HEALPix nel 16, tile nel 12), `D13-1` (grammatica `search` alla Aladin validata prima dell'esecuzione), `D13-5` (operazioni non distruttive, in-place con flag nel report), `D13-6` (colonna DataLink nel 13, risoluzione nel 14), `D14-1` (`pyvo` per TAP/DataLink, `astropy.samp` da valutare, licenze da riverificare), `D14-2` (hub SAMP già attivo o proprio; perimetro tabelle/selezioni/puntamenti, immagini come estensione), `D16-1` (`mocpy`, licenza/macOS da verificare), `D16-2` (MOC in cache FITS IVOA, export JSON/testo), `D16-3` (JD interno via `astropy.time`, ISO 8601 in UI/file, scala sempre dichiarata, scala IVOA per i MOC temporali → DC1), `D17-2` (geometria 17, rendering 41), `D17-3` (tag nella sessione del 24, riferimenti e operazioni non pixel, rieseguibile), `D17-4` (fotometria F4 interamente nel 20). §3 riscritto come elenco degli esiti; conteggi §1/§2 aggiornati (aperte: 25 — Gruppo 1 = 0, Gruppo 2 = 20, Gruppo 3 = 5). File di origine, `panoramica.md` e `INDICE.md` aggiornati. |
| 2026-10-04 | agente di sviluppo | **Esito parziale di AP5** (riga 3 di §3): fonte = manuale utente Aladin Desktop edizione **febbraio 2021**, lette **sezioni 1–5.7.2 e l'indice completo**; AP5 resta aperta per i dettagli delle **5.7.3–8**, esistenza di tutte le funzioni verificata dall'indice. In `03-parita-aladin.md`: **D12 correzione** (estrazione in Aladin esiste, sezione 6.5, via SExtractor esterno → riga `verificata` tornata nella sezione D, AstroTwo nativo nel 20, libreria da decidere; sezione "funzioni extra" vuota), nuove righe **H17**/**H18**/**H19** (Exam 5.9, avvio via URL 7.2, VOApp/VOObserver 7.5; "dettagli da leggere"), note su **A13**, **B11**, **E4**, **F4**; conteggi §2 → 59 A–G + 19 H + 0 extra = 78. Aggiornati `01-architettura.md` §8 (obiettivi di prestazioni ≥ Aladin in `61-strategia-test.md`), `panoramica.md` e `INDICE.md`. Nessuna decisione di questo file cambia stato: aperte sempre 25 (Gruppo 1 = 0, Gruppo 2 = 20, Gruppo 3 = 5). |
| 2026-10-08 | Claude Code | Aggiunta la decisione aperta **`AP6` — edizione di riferimento del manuale di Aladin** (giugno 2022 o febbraio 2021) nel Gruppo 2 (§4), su richiesta del proprietario, senza scegliere; fonte `03-parita-aladin.md` §6. Conteggi: aperte 26 (Gruppo 1 = 0, Gruppo 2 = 21, Gruppo 3 = 5). Nel registro il riferimento AP5 "5.9–8" è annotato come 5.7.3–8. |
| 2026-10-08 | Claude Code | **Decisioni del proprietario:** `AP6` decisa (edizione di riferimento del manuale di Aladin = giugno 2022, la più recente ufficiale dopo verifica sul sito del CDS) e tolta dal Gruppo 2; elenco completato con `AP2`, `AP3`, parte aperta di `DC1`, `DC3`, `DC4` (Gruppo 2, smistamento proposto secondo §2, da confermare) e `AP1`, `AP4` (Gruppo 3; `AP1` con `A8` per decisione del proprietario). AP5 scritta in forma uniforme ("AP5 decisa; lettura delle sezioni 5.7.3–8 ancora da fare") in §1, §3, §6. Conteggi: aperte **32** (Gruppo 1 = 0, Gruppo 2 = 25, Gruppo 3 = 7). |
| 2026-10-08 | Claude Code | Smistamento di AP2, AP3, AP4, DC1, DC3, DC4 **confermato dal proprietario**. **`AP3` decisa** (Aladin Lite escluso dalla parità; versione web → proposta AM1) e tolta dal Gruppo 2. AP5 scritta come "AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) ancora da fare" in §1, §3, §6. Conteggi: aperte **31** (Gruppo 1 = 0, Gruppo 2 = 24, Gruppo 3 = 7). |
| 2026-10-08 | Claude Code | **Lettura AP5 completata** (sezioni 5.9–8, ed. giugno 2022): AP5 scritta come "AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08" in §1, §3, §6. Nuova decisione aperta **AM1 (H21, dati planetari)** nel Gruppo 1 (smistamento proposto, da confermare). Conteggi: aperte **32** (Gruppo 1 = 1, Gruppo 2 = 24, Gruppo 3 = 7). |
| 2026-10-08 | Claude Code | **AM1 per H21 decisa (accettata)** dal proprietario: nuovo modulo `19-core-dati-planetari.md`, livello 1; Gruppo 1 di nuovo vuoto. Conteggi: aperte **31** (Gruppo 1 = 0, Gruppo 2 = 24, Gruppo 3 = 7). Le altre decisioni del giorno (obiettivo di prestazioni in `01` §8, D10-4 precisata, DC7 in `02`, SED nel 20, equivalente di VOApp) non erano voci di questo elenco. |
| 2026-10-08 | Claude Code | Aggiunte le 13 decisioni aperte dei nuovi moduli `18-core-calcolatrici.md` (D18-1…D18-6) e `19-core-dati-planetari.md` (D19-1…D19-7). Smistamento proposto secondo §2, da confermare: Gruppo 1 = `D19-2`, `D19-3` (toccano i moduli 11, 12, 13, 14, 16); Gruppo 2 = `D18-1`…`D18-4`, `D19-1`, `D19-4`…`D19-7`; Gruppo 3 = `D18-5`, `D18-6`. Conteggi: aperte **44** (Gruppo 1 = 2, Gruppo 2 = 33, Gruppo 3 = 9). |
| 2026-10-09 | Claude Code | **Decisioni del proprietario del 2026-10-08:** smistamento delle 13 decisioni di 18 e 19 confermato; **D19-3 decisa** (campo `body` obbligatorio nei moduli 12, 13, 14, 16; `celestial` ricavato dal sistema di coordinate) e **D19-2 decisa** (PDS nel 19, PDS4 obbligatorio, PDS3 solo con libreria consolidata) → Gruppo 1 vuoto; resta **`D19-2b`** (libreria e licenza PDS) nel Gruppo 2; **D19-4 decisa** (errore di default, forzabile con opzione esplicita citata nel risultato) e tolta dal Gruppo 2. Conteggi: aperte **42** (Gruppo 1 = 0, Gruppo 2 = 33, Gruppo 3 = 9). |
| 2026-10-09 | Claude Code | **Checklist del livello 1 (decisioni del proprietario):** chiuse 30 decisioni del Gruppo 2 (elenco in §1, testo nei file di origine); A2, A6, A9 restano nel Gruppo 2 ma bloccano solo `60` (A2, A6) e `40` (A9), con orientamento registrato; nuove `A10` (tetti di memoria) e `D10-6` (prestazioni delle conversioni di massa) nel Gruppo 3. Conteggi: aperte **14** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 11). |
| 2026-10-09 | Claude Code | **Completamento dei moduli 11–17 con gli esiti di AP5:** nuove decisioni del Gruppo 2 `D11-6` (libreria JPEG/PNG/GIF), `D13-7` (lettore ASTRORES), `D14-7` (sistema di plugin), `D14-8` (formato IDHA), `D15-5` (criterio delle ellissi d'errore); nuova `D13-8` nel Gruppo 3. Conteggi: aperte **20** (Gruppo 1 = 0, Gruppo 2 = 8, Gruppo 3 = 12). |
| 2026-10-09 | Claude Code | **Decise dal proprietario** D11-6 (`Pillow`), D13-7 e D14-8 (lettori ASTRORES e IDHA con `defusedxml`, altrimenti solo errore), D14-7 (nessun sistema di plugin nel livello 1; estensioni tramite l'API Python del 24), D15-5 (Mahalanobis con covarianza combinata, soglia in sigma) e tolte dal Gruppo 2; nuova `D15-6` (soglia predefinita, Gruppo 3). Framework dei test `pytest` registrato in `01`/`02`. Conteggi: aperte **16** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 13). |
| 2026-10-09 | Claude Code | **FASE: CODICE – livello 1, verifiche del modulo 10:** nuove `D10-7` (calibrazione per associazione di stelle, verifica di `fit_wcs_from_points` non superata) e `D10-8` (parti del 10 senza interfaccia in §7) nel Gruppo 3, entrambe bloccanti per il codice delle parti interessate. Conteggi: aperte **18** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 15). |
| 2026-10-09 | Claude Code | **Decise dal proprietario `D10-7`** (partenza `TAN` + tre controlli; coerenza con l'RMS della `TAN`) e **`D10-8`** (griglia e scelta della proiezione nel 10, cache in `04-cache.md` con AM1 accettata, centroide nell'11, soluzioni come lista, offset e calcolo inverso nel 17) e tolte dal Gruppo 3; nuove `D10-9` e `D11-7` (Gruppo 3) e `CA1`–`CA4` di `04-cache.md` (Gruppo 2, bloccano l'approvazione del 04). Conteggi: aperte **22** (Gruppo 1 = 0, Gruppo 2 = 7, Gruppo 3 = 15). |
| 2026-10-09 | Claude Code | **Decise dal proprietario** `CA1` (timeout 10 s / 60 s, configurabili), `CA2` (un solo limite di 5 GB), `CA3` (`src/astrotwo/core/cache.py`), `CA4` (nessuna cache propria nei moduli) — `04-cache.md` approvato — e `D11-7` (fondo = mediana con sigma clipping in una corona); tolte dai Gruppi 2 e 3. `D10-9` resta aperta, da decidere con il 41. Conteggi: aperte **17** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 14). |
| 2026-10-09 | Claude Code | Nuova `D11-8` (default dei raggi della corona del centroide, Gruppo 3, da fissare con 20 e 41) su decisione del proprietario. Conteggi: aperte **18** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 15). |
| 2026-10-10 | Claude Code | Nuova `A11` — licenza di AstroTwo (Gruppo 2, blocca il 60), aperta dal proprietario; `A10` decisa per le immagini, resta per cataloghi e HiPS. Conteggi: aperte **19** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 15). |
| 2026-10-10 | Claude Code | Regola d'oro n. 8 applicata a decisioni già prese (nessuna riaperta): D12-1 (Hipsgen tolto), D12-3, D13-1 (riga 10 di §3 aggiornata), D13-3, D14-3, D14-4, D15-1, D15-4, D15-5, D18-2, D19-5 con motivazioni nostre nei file di origine; nel 15 il raggio del cross-match diventa obbligatorio. Nuova decisione del proprietario D11-10 (11, già decisa). Conteggi invariati: aperte **19** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 15). |
| 2026-10-10 | Claude Code | Decisioni del proprietario sul 13: **D13-4** (1 milione di righe, limite delle operazioni 4 GB) e **D13-8** (tabella delle funzioni in `catalogs.py`) decise; **A10** decisa anche per i cataloghi, resta per gli HiPS; **D11-11** (11) decisa. Nuove nel Gruppo 3: `D13-10` (`skydist`), `D13-11` (colonna DataLink), `D13-12` (propagazione senza parallasse), `D13-13` (sottoinsiemi salvati), `D13-14` (lettura ASTRORES). Conteggi: aperte **22** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 18). |
| 2026-10-10 | Claude Code | Decise dal proprietario `D13-10` (`skydist` con astropy, usato anche dal 17), `D13-11` (DataLink in P6), `D13-12` (`proper_motion_only` nel 10; righe senza moto proprio mascherate), `D13-13` (sottoinsiemi in un VOTable scelto dall'utente), `D13-14` (lettura ASTRORES, punti a, c, d, e). Nuove nel Gruppo 3: `D13-14b`, `D13-15`, `D13-16`. Conteggi: aperte **20** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 16). |
| 2026-10-10 | Claude Code | Decise dal proprietario `D13-14b` (solo gli UCD1 della raccomandazione IVOA), `D13-15` (numeri con l'unità della colonna in `+`, `-`, `%`, `min`, `max`), `D13-16` (`time_filter`). Conteggi: aperte **17** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 13). |
| 2026-10-10 | Claude Code | Decisa dal proprietario `D14-5` (`max_rows` 100 000, fino al tetto del 13) e tolta dal Gruppo 3; `D14-1` aggiornata (SAMP con `pyvo.samp`). Nuove nel Gruppo 3, dal codice del 14 e di P6 del 13: `D14-10` (unità nel CSV), `D14-11` (calibrazione della lista SIA nell'11), `D14-12` (magnitudine del puntatore Simbad), `D13-17` (`LINK` ASTRORES), `D13-18` (albero delle collezioni e popolarità). Conteggi: aperte **21** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 17). |
| 2026-10-11 | Claude Code | **Decise dal proprietario** `D14-10` (ECSV per le tabelle con unità, CSV semplice con avviso), `D14-11` (WCS dalle colonne `VOX:WCS_*` di SIA 1, parametro `calibration` nell'11), `D14-12` (tutte le magnitudini SIMBAD con banda e sistema), `D13-17` (`LINK` ASTRORES solo con `href`, formato dal `content-type` dichiarato), `D13-18` (albero dal MocServer per `vizier_popularity`, dichiarata non documentata; altrimenti alfabetico) e tolte dal Gruppo 3. Nuove nel Gruppo 3: `D13-19` (parametro di regione di `load_catalog`) e `D13-14c` (traduzione UCD1 del CDS, rimandata). Conteggi: aperte **18** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 14). |
| 2026-10-11 | Claude Code | **Decise dal proprietario** `D13-19` (`region=(centro, raggio)` in `load_catalog`) e `D15-6` (soglia delle ellissi obbligatoria) e tolte dal Gruppo 3. Nuove nel Gruppo 3, dal codice: `D13-20` (sistema di SIMBAD nell'`utype` MANGO), `D15-8` (corpo nella correlazione per campo), `D15-9` (`best` con il servizio CDS). `D13-14c` resta rimandata. Conteggi: aperte **19** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 15). |
| 2026-10-11 | Claude Code | **Decise dal proprietario** `D13-20` (sistema di SIMBAD dall'`utype` MANGO, dichiarato), `D15-8` (corpo nella correlazione per campo controllato solo se entrambe le tabelle ne hanno uno), `D15-9` (servizio CDS sempre `selection=all`, `best` in locale) e tolte dal Gruppo 3 (prima nei file di origine 13 e 15). Nuove nel Gruppo 3, dal codice del modulo 16: `D16-6` (versione 2.1 del formato MOC) e `D16-7` (complemento dei MOC spazio-temporali). Conteggi: aperte **18** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 14). |
| 2026-10-12 | Claude Code | **Decise dal proprietario** `D16-6` (verifica sul sito IVOA: nessuna 2.1 tra WD e PR, resta rifiutata), `D16-7` (complemento degli ST-MOC come differenza da "tutto il tempo × tutto il cielo" con `mocpy`) e `A10` per gli HiPS (tile in memoria entro 512 MB configurabili, `build_hips` un tile alla volta entro il limite delle operazioni di 4 GB, su disco la cache comune di 5 GB; scritta nel `12`) e tolte dal Gruppo 3 (prima nei file di origine 16 e 12). Nuove nel Gruppo 3, dal codice del 12: `D12-6` (nomi dei corpi), `D12-7` (`hips_frame = ecliptic`), `D12-8` (Allsky). Conteggi: aperte **18** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 14). |
| 2026-10-12 | Claude Code | **Decise dal proprietario** `D12-6` (normalizzazione dei nomi dei corpi con una tabella del 19, da scrivere con il 19), `D12-7` (`hips_frame = ecliptic` non supportato finché non verificato su un HiPS reale), `D12-8` (nessun Allsky da `build_hips` per ora) e `D17-5` (bilineare con `scipy.ndimage.map_coordinates`, passo obbligatorio senza default) e tolte dal Gruppo 3 (prima nei file di origine 12 e 17). Nuova nel Gruppo 3, dalla verifica di P3 del 17: `D17-7` (geometria sferica delle forme). Conteggi: aperte **15** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 11). |
| 2026-10-13 | Claude Code | **Decise dal proprietario** (2026-10-12) `D17-7` (`spherical-geometry` per poligoni e tracciati chiusi, ellisse sferica, freccia/testo `OPERATION_UNSUPPORTED`), `D18-5` (1000 caratteri, annidamento 50, configurabili) e `D18-6` (valore grezzo con `do_not_scale_image_data=True`) e tolte dal Gruppo 3 (prima nei file di origine 17 e 18). Nuove nel Gruppo 3: `D17-8` (significato di `distance_to`) e `D18-7` (sessagesimali in `skydist`). Conteggi: aperte **14** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 10). |
| 2026-10-13 | Claude Code | **Decise dal proprietario il 2026-10-13** `D17-8` (`distance_to` = distanza angolare minima, cerchi con Astropy, poligoni con la distanza punto–arco) e `D18-7` (unità scritta nel testo, due punti solo con un parametro esplicito, nessuna convenzione sulla posizione) e tolte dal Gruppo 3 (prima nei file di origine 17 e 18). Nuove nel Gruppo 3: `D17-9` (`distance_to` per ellisse, freccia, testo, tracciato aperto), `D19-8` (PDS3 con `pdr`), `D19-9` (PDS da URL). `A11` annotata con `THIRD_PARTY_LICENSES`. Conteggi: aperte **15** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 11). |
| 2026-10-13 | Claude Code | **Decisioni del proprietario del 2026-10-13** (prima nei file di origine 17 e 19): `D17-9` decisa (ellisse numerica con precisione dichiarata, freccia e tracciato aperto come archi di cerchio massimo, testo `OPERATION_UNSUPPORTED`) e `D19-9` decisa (PDS da URL con la rete del 14 e la cache comune), tolte dal Gruppo 3; `D19-8` **rimandata, bassa priorità** (PDS3 non ancora supportato), resta nel Gruppo 3. `A11` annotata: testo di licenza di `pims` trovato (segnaposto non compilato da valutare). Conteggi: aperte **13** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 9). |
| 2026-10-14 | Claude Code | **Nuova nel Gruppo 3: `D16-8`** (prima nel file di origine 16 §13): la regola dei blocchi per `moc_from_image` decisa il 2026-10-14 perde celle sul bordo; raccomandazione con le misure. Conteggi: aperte **14** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 10). |
| 2026-10-14 | Claude Code | **Decisa dal proprietario `D16-8`** (blocchi più angoli dei pixel lungo il contorno della regione dei blocchi validi; crescita ≤ b − 1 pixel) e tolta dal Gruppo 3 (prima nel file di origine 16). **Nuova nel Gruppo 3: `D14-13`** (prima nel file di origine 14): reindirizzamento http → https dell'ESO che codifica due volte l'URL. Conteggi: aperte **14** (Gruppo 1 = 0, Gruppo 2 = 4, Gruppo 3 = 10). |
| 2026-10-15 | Claude Code | **Decisioni del proprietario del 2026-10-15** (proposta della fase 1 dell'interfaccia; prima nei file di origine 01, 10, 11, 40, 41): decise e tolte `A9` (Gruppo 2; inglese con `tr()`, italiano nostro, punto decimale sempre), `D10-9` (30°, scarto ±10 % nel 41) e `D11-8` (corona 1 × / 1,5 × `box_size`, box 15 pixel nel 41) (Gruppo 3). Nuove dalle specifiche 05, 40, 41: Gruppo 2 `D05-1`, `D05-2`, `D40-1`, `D41-1`, `D41-2`, `D41-3`; Gruppo 3 `D05-3`, `D40-2`, `D41-4`. Conteggi: aperte **20** (Gruppo 1 = 0, Gruppo 2 = 9, Gruppo 3 = 11). |
| 2026-10-15 | Claude Code | **Decisioni del proprietario del 2026-10-15 sulle specifiche dell'interfaccia** (prima nei file di origine 05, 40, 41, 10, 11): decise e tolte `D05-1`, `D05-2`, `D40-1`, `D41-1`, `D41-2`, `D41-3` (Gruppo 2) e `D41-4` (Gruppo 3; Mac di riferimento da compilare); `D05-3` e `D40-2` rimandate (restano nel Gruppo 3); nuova `D40-3` (Gruppo 3, messaggi dei moduli in inglese con traduzione); `A11` annotata con PySide6/Qt (LGPL-3), pytest-qt e icone. Conteggi: aperte **14** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 11). |
| 2026-10-16 | Claude Code | **Proposta della fase 1 sull'IA nella v1 approvata dal proprietario il 2026-10-16** (file 30, 31, 32, 34, 35, 44 in bozza; modifiche a 01, 02, 03, 05, 10, 40, 41, 42): **nessuna decisione nuova né chiusa in questo elenco** — le scelte della proposta sono decise dal proprietario e registrate nei file di origine e in `panoramica.md` §5 (A5 precisata, A7 nella v1, perimetro dell'IA con il 33 rimandato, regola dei commit con HTTP 429/502/503/504); nei §13 dei nuovi file restano solo scelte minori da confermare e verifiche prima del codice. Conteggi invariati: aperte **14** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 11). |
| 2026-10-16 | Claude Code | Scelte minori della v1 confermate, 05, 30, 31, 32, 34, 35, 40, 41, 42, 44 approvati e "FASE: CODICE – interfaccia v1" dichiarata dal proprietario il 2026-10-16: nessuna voce di questo elenco cambia. Conteggi invariati: aperte **14**. |
| 2026-10-16 | Claude Code | **D04** (cache da più thread, aperta e decisa lo stesso giorno dal proprietario nella conversazione, opzioni a + b; registrata nel file di origine 04): non entra nei conteggi. Aperte **14**. |
| 2026-10-16 | Claude Code | **Nuova nel Gruppo 1: `D05-4`** (prima nel file di origine 05 §13): forma JSON dei valori dei parametri e parametri strutturati, trovata allineando il 18; ferma solo l'adattatore del 18 e i comandi `calc.*`. Conteggi: aperte **15** (Gruppo 1 = 1, Gruppo 2 = 3, Gruppo 3 = 11). |
| 2026-10-17 | Claude Code | **`D05-4` decisa dal proprietario il 2026-10-17** (opzione a, prima nel file di origine 05 §13 e nel 18): tolta dalle aperte del Gruppo 1. Decisioni del 2026-10-17 su `httpx2` (01, 30) e sui profili predefiniti dei provider (30, 31, 44): decise e registrate nei file di origine, non entrano in questo elenco. Conteggi: aperte **14** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 11). |
| 2026-10-17 | Claude Code | **Nuova nel Gruppo 3: `D40-4`** (prima nel file di origine 40 §13): scorciatoia della modalità notte chiesta dal proprietario con la parte 3b, raccomandazione ⌃⌘N. `A11` annotata: licenza di Lucide verificata. Conteggi: aperte **15** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 12). |
| 2026-10-17 | Claude Code | **`D40-4` decisa dal proprietario: ⌃⌘N** (prima nel file di origine 40 §13), tolta dal Gruppo 3. Conteggi: aperte **14** (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 11). |
| 2026-10-17 | Claude Code | **`A11` decisa dal proprietario: GPL-3.0-or-later**, titolare Guido Ratti (prima nel file di origine `01` §4.2 e §6.1), tolta dal Gruppo 2. Conteggi: aperte **13** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 11). |
| 2026-10-20 | Claude Code | **Nuova nel Gruppo 3: `D41-5`** (prima nel file di origine 41 §13): zoom e spostamento su una griglia di pixel, aperta con lo sprint 4d. Conteggi: aperte **14** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 12). |
| 2026-10-21 | Claude Code | **`D41-5` rinviata a dopo la v1** (decisione del proprietario del 2026-10-21; resta nel Gruppo 3). **Nuova nel Gruppo 3: `D41-6`** (prima nel file di origine 41 §13): epoca del COOSYS persa da `catalog.set_columns`, trovata con lo sprint 4e. Conteggi: aperte **15** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 13). |
| 2026-10-21 | Claude Code | **`D41-6` decisa** (decisione del proprietario del 2026-10-21, prima nei file di origine 13 §13 e 41 §13): `confirm_position_columns` conserva l'epoca del COOSYS con le stesse colonne e lo stesso sistema; tolta dal Gruppo 3. Conteggi: aperte **14** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 12). |
| 2026-10-23 | Claude Code | **Aperte `D32-1` e `D13-21`** (Gruppo 3), prima nei file di origine 32 §13 e 13 §13, dalla prova reale del proprietario ("Carica Gaia DR3 attorno alle Pleiadi" dall'assistente). Conteggi: aperte **16** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 14). |
| 2026-10-23 | Claude Code | **`D32-1` e `D13-21` decise** (proprietario, 2026-10-23; prima nei file di origine 32 §13 e 13 §13): D32-1 = (c) identificativi del gruppo fisso nella descrizione di `catalog` più (b) tabelle che cominciano con l'identificativo in `CATALOG_UNKNOWN`; D13-21 = (a) colonne candidate nel messaggio. **Nuova `D32-2`** (comando di ricerca nell'elenco dei cataloghi, opzione (a) di D32-1), **rinviata a dopo la v1** (Gruppo 3). Conteggi: aperte **15** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 13). |
| 2026-10-24 | Claude Code | **`D41-4` completata** (proprietario, 2026-10-24; prima nel file di origine 41 §13): due Mac di riferimento (minimo iMac21,1 M1 8 GB; comodo MacBook Air M5 32 GB dal 2 novembre). Scelte minori dello sprint 4g confermate. Nessuna decisione nuova aperta; da decidere dal proprietario (non registrate come decisioni): cosa fare di **P1** e **P5** non raggiunti (41 §3.15). Conteggi invariati: aperte **15** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 13). |
| 2026-10-24 | Claude Code | **`D40-3` decisa** (proprietario, 2026-10-24; prima nel file di origine 40 §13): catalogo codice → testo inglese/italiano, `params` nei moduli, inglese verso l'IA; solo specifiche (40, 05, 32). **Nuove nel Gruppo 3:** `D40-5` (posizione del catalogo), `D41-7` (P1) e `D41-8` (P5), registrate su richiesta del proprietario; annotato `test_t14_latency` (170 ms una volta). Conteggi: aperte **17** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 15). |
| 2026-10-24 | Claude Code | **`D40-5` decisa** (proprietario, 2026-10-24; sprint 8b): modulo neutro `src/astrotwo/messages_catalog.py` usato da `ui/` e `ai/`, i moduli 10–19 non lo importano. **`D40-6` decisa subito** (proprietario, 2026-10-24, tra le opzioni proposte): voci del catalogo con sotto-voci scelte dal parametro `reason` per i codici sollevati per ragioni diverse; nessun codice cambia. Conteggi: aperte **16** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 14). |
| 2026-10-24 | Claude Code | **Aperta `D40-7`** (Gruppo 3; sprint 8c, modulo 12): messaggi annidati nel catalogo (parametro esterno oggi; tipo `message` ricorsivo raccomandato se l'inglese è un requisito della v1). Conteggi: aperte **17** (Gruppo 1 = 0, Gruppo 2 = 2, Gruppo 3 = 15). |
