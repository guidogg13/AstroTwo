# 01-architettura.md — architettura generale e scelte tecniche

**Stato:** approvato

## 1. Scopo

Descrivere come è organizzato AstroTwo, quali scelte tecniche sono già prese e
perché, e quali restano aperte, così che chi scrive il codice sappia dove
collocare ogni modulo e con quali vincoli.

## 2. Principi non negoziabili

Da `CLAUDE.md`:

1. L'IA non calcola mai: ogni numero viene da codice deterministico e testato.
2. Prima la specifica, poi il codice.
3. Un modulo = un file `.md`.
4. Non reinventare la scienza: si usano librerie consolidate.
5. Le chiavi API vivono solo nel Portachiavi di macOS.
6. Riproducibilità: ogni operazione dell'utente va registrata e rieseguibile.
7. Architettura a livelli: un livello non rompe mai quello sotto.

**Principio aggiunto il 2026-10-04 (decisione del proprietario, P11 in
`panoramica.md`): la parità con Aladin è il minimo, non il traguardo.**
AstroTwo include **tutte** le funzioni elencate in `03-parita-aladin.md`,
anche quelle non confermate nella documentazione di Aladin (righe C3 HiPS da
ID/URL, F2 position angle, G3 invio a strumenti esterni, E4 spettri SSA). Su
queste funzioni resta aperta **solo la verifica tecnica di implementazione**
(come si fanno), mai la domanda se esistano in Aladin (se esistano: è deciso
che esistono in AstroTwo).

## 3. Architettura a livelli

```
Livello 4   Funzioni avanzate     transienti, multi-messaggero, collaborazione, 3D
                |
Livello 3   IA                    adattatore provider, chiavi, strumenti, ADQL,
                |                  verifica risultati, chat  (può essere disattivata)
                |
Livello 2   Analisi               fotometria, spettri, curve di luce, cubi,
                |                  pipeline riproducibili
                |
Livello 1   Nucleo                coordinate/WCS, FITS, HiPS, cataloghi, VO,
                                  cross-match, MOC, misure; generali: cache (04),
                                  comandi e sessione (05)

Interfaccia  UI (40-45)           chiama i livelli, non contiene scienza
```

Regole strutturali:

- Le dipendenze puntano solo verso il basso: `4 → 3 → 2 → 1`.
- Il livello 1 non importa nulla dei livelli superiori e non conosce l'IA.
- Il livello 3 (IA) può essere disabilitato: l'app deve funzionare ugualmente
  ai livelli 1 e 2 senza connessione e senza chiavi.
- L'interfaccia non fa calcoli: chiama i moduli del nucleo e dell'analisi e
  disegna ciò che ricevono.
- Ogni confine tra livelli è un'interfaccia descritta in un file `.md`;
  nessun modulo può usare funzioni interne di un altro modulo.

## 4. Scelte tecniche adottate

### 4.1 Scelte di progetto (da `CLAUDE.md`)

| # | Scelta | Motivazione | Stato |
|---|---|---|---|
| S1 | **Nucleo scientifico in Python** | Astropy, astroquery, healpy, scipy, numpy e la maggior parte delle librerie astronomiche sono in Python; riscrivere significherebbe duplicare scienza già validata (regola d'oro n. 4) | adottata (da `CLAUDE.md`) |
| S2 | **App desktop per macOS** | requisito del progetto: gli astrofisici lavorano su macOS; consente di usare il Portachiavi di macOS per le chiavi API | adottata (da `CLAUDE.md`) |
| S3 | **Consegna come file `.dmg`** | distribuzione standard su macOS, installazione trascinando l'icona in Applicazioni | adottata (da `CLAUDE.md`) |
| S4 | **Livello IA separato dal resto, con adattatore per più provider** | l'utente sceglie il provider e inserisce la propria chiave; il nucleo deve restare utilizzabile senza IA; evita di legare la scienza a un fornitore | adottata (da `CLAUDE.md`) |
| S5 | **Chiavi API solo nel Portachiavi di macOS** | regola d'oro n. 5: mai in file, log, repository o variabili d'ambiente persistite | adottata (da `CLAUDE.md`) |
| S6 | **Librerie consolidate per astronomia e matematica** | regola d'oro n. 4: Astropy (WCS, coordinate, unità, FITS), astroquery (servizi CDS/ESA/NASA), healpy (mappe HEALPix/MOC), e le librerie già usate dalla comunità | adottata; l'elenco esteso è nei file dei singoli moduli |
| S7 | **Le specifiche sono file `.md` in `mdfiles/`, una per modulo** | leggibili, versionabili, verificabili senza leggere il codice | adottata (da `CLAUDE.md`) |

### 4.2 Decisioni prese (spostate dalle decisioni aperte)

| Etichetta | Data | Decisione | Motivazione |
|---|---|---|---|
| **A3** | 2026-10-04 | UI e nucleo nello stesso progetto Python: codice in `src/astrotwo/` con sotto-pacchetti `core`, `analysis`, `ai`, `ui`, `advanced` che rispecchiano i gruppi dei file `.md`; test in `tests/` con la stessa struttura | corrispondenza 1:1 tra specifica e codice (un modulo `.md` ↔ un file nel sotto-pacchetto), navigazione e revisione più semplici, un solo ambiente da costruire e da testare |
| **A4** | 2026-10-04 | Python **3.12**; file del progetto `pyproject.toml`; gestore pacchetti **`uv`** | versione stabile e diffusa nell'ecosistema scientifico; `uv` rende creazione dell'ambiente, installazione delle dipendenze ed esecuzione dei test rapide e riproducibili; scelta registrata dal proprietario |
| **A7** | 2026-10-04 | Cache con due media: **SQLite** per le interrogazioni ai cataloghi, **file su disco** per i riquadri HiPS e FITS; **limite di spazio configurabile** con eliminazione dei dati meno usati; ogni dato servito dalla cache espone **origine e data di scaricamento** | SQLite è interrogabile e portabile per le tabelle; i file singoli permettono lettura diretta dei riquadri senza deserializzazione; il limite configurabile impedisce che la cache cresca senza controllo; origine e data garantiscono tracciabilità e riproducibilità dei dati mostrati |
| **A1** | 2026-10-04 | Interfaccia grafica scritta con **PySide6 (Qt)**; il rendering delle mappe con **OpenGL si specifica in `41-ui-visualizzatore-cielo.md`** | un solo ambiente Python coerente con A3/A4, widget maturi per la visualizzazione scientifica; orientamento già espresso qui, confermato dal proprietario prima dei moduli 40–45 |
| **A9** | 2026-10-15 | Lingua dell'interfaccia: **testi in inglese nel codice con `tr()`**, **traduzione italiana nostra** con Qt Linguist, **traduzioni di Qt** per i dialoghi standard; lingua presa dal sistema e cambiabile nelle preferenze; **numeri scientifici sempre con il punto decimale in ogni lingua** | inglese come lingua comune della comunità, italiano per il proprietario; strumenti standard di Qt; il punto decimale evita ambiguità e rende i valori copiabili in modo riproducibile (dettagli in `40-ui-finestra-principale.md` §3.9) |
| **A5** | 2026-10-04 (implementazioni precisate il 2026-10-16) | Interfaccia IA **a capacità** (chiamata di strumenti + streaming) con due implementazioni iniziali: **provider cloud** e **endpoint compatibile OpenAI** (che copre anche i modelli locali). **Dal 2026-10-16:** le due implementazioni usano gli **SDK ufficiali `anthropic` (MIT) e `openai` (Apache-2.0)**, il secondo con **endpoint configurabile** (OpenAI in cloud, Ollama, LM Studio, vLLM…); licenze da verificare e da aggiungere a `THIRD_PARTY_LICENSES`; **nessun identificativo di modello nel codice** (lo sceglie l'utente); modelli senza chiamata di strumenti rifiutati (`AI_NO_TOOLS`); dettagli in `30-ia-adattatore-provider.md` | conforme a `CLAUDE.md` (l'utente sceglie il provider e inserisce la propria chiave), un solo contratto da testare, copertura di cloud e modelli locali; due SDK ufficiali con licenze permissive invece di una libreria che unifica i provider (meno dipendenze, passaggi intermedi sotto controllo); confermata dal proprietario prima dei moduli 30–35 |
| **A11** | 2026-10-17 | Licenza di AstroTwo: **GPL-3.0-or-later**. Titolare del copyright: **Guido Ratti**, anno 2026, unico titolare (per poter offrire in futuro licenze diverse o una versione Pro). Testo in `LICENSE`, avviso in `NOTICE`, intestazione SPDX in ogni file `.py`, contributi esterni solo con accordo di cessione dei diritti (`CONTRIBUTING.md`) | scelta del proprietario; compatibile con tutte le dipendenze (verifica del 2026-10-17 in §6.1); chiude la parte di A11 che bloccava il `60` |

Note residue di A3/A4/A7:

- Con la struttura a progetto unico (`src/astrotwo/`) la domanda "UI e nucleo in
  processo separato oppure IPC" si intende chiusa a favore di **un unico ambiente
  Python**; se in futuro si volesse la UI in un processo proprio, va riaperta A3.
- Non rientra nella decisione la posizione dei codici di **packaging** del modulo
  60: da definire in `60-distribuzione-dmg.md`.
- **Framework dei test: `pytest`** (decisione del proprietario del 2026-10-09,
  anticipata da `61-strategia-test.md`, dove restano gli altri dettagli dei
  test). Resta da definire (in `60-…`) la politica di blocco delle versioni
  esatte delle dipendenze; la struttura `tests/` specchiata a `src/astrotwo/`
  è già decisa con A3.

## 5. Scelte ancora aperte

Ogni voce ha una voce corrispondente in "Decisioni aperte" del file pertinente.
Le etichette sono armonizzate in tutti i file generali: `A1–A9` sono definite
qui, `AP1` in `03-parita-aladin.md`, `AM1` in `panoramica.md`.

| # | Argomento | Opzioni in lizza / orientamento | Coinvolti | Stato |
|---|---|---|---|---|
| A2 | Strumento che produce il `.dmg` | PyInstaller/briefcase + script di creazione dmg · pacchetto nativo Xcode · altro | `60-distribuzione-dmg.md` | **orientamento (2026-10-09): PyInstaller + dmgbuild**; non blocca il livello 1, blocca l'approvazione di `60-distribuzione-dmg.md` |
| A6 | Firma e notarizzazione Apple | account sviluppatore Apple con firma + notarizzazione · senza firma (con limiti d'installazione) | `60-distribuzione-dmg.md` | **orientamento (2026-10-09): sì**, firma e notarizzazione con account Apple Developer **solo al momento della distribuzione**; blocca l'approvazione di `60-distribuzione-dmg.md` |
| A8 | Livello di compatibilità con lo scripting di Aladin | strada già scelta: **scripting principale in Python**; la compatibilità con i comandi di Aladin è **rimandata** | `24-analisi-pipeline-riproducibili.md` | **rimandata: dopo il completamento del livello 1** |
| A10 | Tetti di memoria per immagini, cataloghi e HiPS caricati | valori per modulo, coerenti con l'obiettivo di §8 | `11`, `12`, `13`, `61-strategia-test.md` | **immagini (11): decisa il 2026-10-10** — in memoria fino a 1 GB, `memmap` oltre per i non compressi, due livelli oltre 4 GB o per i compressi oltre 1 GB, anteprima ≤ 4096 pixel (strategia di caricamento; il **limite delle operazioni**, 4 GB configurabile, è separato: D11-11 nell'11); **cataloghi (13): decisa il 2026-10-10** — tetto di 1 milione di righe per tabella, configurabile, più la stima della memoria con il limite delle operazioni (D13-4); **HiPS (12): decisa il 2026-10-12** — tile in memoria entro **512 MB, configurabili**; `build_hips` lavora **un tile alla volta** entro il **limite delle operazioni** (4 GB, D11-11); su disco la **cache comune di 5 GB** (`04-cache.md`). **A10 interamente decisa** |

Fuori da questo file: **AP1** validazione finale della parità con Aladin
(`03-parita-aladin.md`, rimandata) e **AM1** aggiunta/separazione di moduli
(`panoramica.md`, **decisa il 2026-10-04**: accettate `18-core-calcolatrici.md`
da H4 e `45-ui-viste-multiple.md` da H2).

## 6. Struttura delle cartelle del codice (decisa con A3/A4)

```
astrotwo/
├── CLAUDE.md
├── mdfiles/                 tutte le specifiche (questa cartella)
├── pyproject.toml           definizione del progetto e delle dipendenze (Python 3.12, uv)
├── THIRD_PARTY_LICENSES     licenze e avvisi di tutte le dipendenze (dal 2026-10-13)
├── scripts/                 strumenti di sviluppo (commit con i test, file delle licenze)
├── src/astrotwo/
│   ├── core/                livello 1   (moduli 10-19)
│   ├── analysis/            livello 2   (moduli 20-24)
│   ├── ai/                  livello 3   (moduli 30-35)
│   ├── ui/                  interfaccia (moduli 40-45)
│   └── advanced/            livello 4   (moduli 50-53)
└── tests/                   test, con la stessa struttura di src/astrotwo/
```

- Il nome del file Python di un modulo è il nome della specifica senza numero né
  trattini di gruppo ed estensione `.py` (es. `10-core-coordinate-wcs.md` →
  `src/astrotwo/core/coordinates_wcs.py`): la corrispondenza specifica ↔ codice
  va tenuta esplicita. Convenzione completa in `02-convenzioni.md`.
- I test di un modulo vivono nella stessa posizione relativa dentro `tests/`.
- **Identificativo del progetto** (decisione del proprietario del
  2026-10-16): **`dev.pages.astrotwo`**, identificativo inverso ricavato dal
  sito del progetto `astrotwo.pages.dev`. È il **bundle identifier dell'app**
  per il `60-distribuzione-dmg.md` e la radice degli altri identificativi:
  il servizio del Portachiavi per le chiavi dell'IA è
  `dev.pages.astrotwo.ai` (`31` §3.1).
- Dove vivano gli strumenti di packaging del modulo 60: da definire in
  `60-distribuzione-dmg.md`.
- **`THIRD_PARTY_LICENSES`** (decisione del proprietario del 2026-10-13):
  file nella radice del progetto con **nome, versione, licenza e avvisi
  richiesti di tutte le dipendenze** di esecuzione su macOS (chiusura delle
  dipendenze di `pyproject.toml`), con il testo integrale dei file di licenza
  distribuiti con ogni pacchetto (compresi l'avviso della libreria **QD di
  LBNL** inclusa in `spherical-geometry` e la **LGPL-3 di WCSLIB** inclusa in
  astropy) e i componenti non Python inclusi nel progetto (es. kernel della
  NAIF del 19). Si genera con `scripts/third_party_licenses.py`; il test
  `tests/test_third_party_licenses.py` fallisce se il file non è aggiornato.
  **Dal 2026-10-16** il file contiene anche le dipendenze della v1
  dell'interfaccia e dell'IA (`pyside6-essentials`, `shiboken6`,
  `anthropic`, `openai`, `httpx2`, `keyring` e le loro dipendenze; testi
  LGPL-3.0 e GPL-3.0 dal sorgente ufficiale di PySide6) e, a parte, gli
  strumenti di sviluppo non distribuiti (pytest, pytest-qt).
  **Da ora ogni nuova dipendenza va aggiunta a quel file** (rigenerandolo)
  nello stesso commit che la introduce.
  **Verifica di `httpx2` (2026-10-17, decisione del proprietario del
  2026-10-17: accettato come trasporto degli SDK):** è la dipendenza
  dichiarata sia da `anthropic` 1.15.0 (`httpx2>=2.0.0,<3`) sia da `openai`
  3.31.0 (`httpx2>=2.12.0,<3`), nei metadati installati e su PyPI; le
  impronte SHA-256 di `httpx2` 2.13.1 nel `uv.lock` coincidono con quelle
  pubblicate su PyPI; autore Tom Christie (autore di `httpx`), manutentore
  Pydantic Services Inc., licenza BSD-3-Clause, repository
  `github.com/pydantic/httpx2`. È una **prosecuzione dichiarata da
  Pydantic**, non dal progetto `encode/httpx` (che resta attivo e non rimanda
  a `httpx2`); PyPI non mostra **nessuna attestazione di pubblicazione** per
  la 2.13.1. **Regola:** versioni di tutte le dipendenze bloccate nel
  `uv.lock`; un aggiornamento si fa solo su richiesta esplicita e con un
  nuovo controllo delle impronte rispetto a PyPI.
  Serve ad A11 (licenza di AstroTwo,
  compatibilità con le licenze elencate) e al `60` (avvisi da includere nel
  `.dmg`).

### 6.1 Licenza di AstroTwo, crediti dei dati e requisiti per il modulo 60 (A11, decisa il 2026-10-17)

**Decisione del proprietario (2026-10-17, chiude A11).** AstroTwo è distribuito con licenza **GPL-3.0-or-later**; titolare del
copyright **Guido Ratti**, anno **2026**, che resta l'**unico titolare** (per poter offrire in futuro licenze diverse o una versione
Pro). Nessun cambiamento al comportamento dell'app.

File nella radice: `LICENSE` (testo integrale e non modificato della GPL-3.0, scaricato da
`https://www.gnu.org/licenses/gpl-3.0.txt`; SHA-256 `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`),
`NOTICE` (avviso standard GNU), `CONTRIBUTING.md` (nessun contributo esterno senza un accordo scritto di cessione dei diritti, CLA,
con il proprietario; il testo del CLA non è scritto), `THIRD_PARTY_LICENSES` (intestazione "Licenza di AstroTwo:
GPL-3.0-or-later"). `pyproject.toml`: `license = "GPL-3.0-or-later"` e `license-files = ["LICENSE", "NOTICE", "THIRD_PARTY_LICENSES"]`
(PEP 639). Ogni file `.py` di `src/`, `tests/`, `scripts/`, `examples/` inizia (dopo un eventuale shebang) con
`# SPDX-License-Identifier: GPL-3.0-or-later` e `# Copyright (C) 2026 Guido Ratti`; `tests/test_license_headers.py` fallisce se
manca. Le icone Lucide in `src/astrotwo/ui/icons/` restano sotto la loro licenza (ISC/MIT, file `LICENSE` nella cartella).

**Verifica di compatibilità con le dipendenze (2026-10-17, sull'elenco di `THIRD_PARTY_LICENSES`).** Nessuna dipendenza di
esecuzione è incompatibile con la GPL-3.0:

- PySide6 e shiboken6: "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only" → si usa l'opzione LGPL-3.0 (o GPL-3.0-only), compatibile; i testi
  completi LGPL-3.0 e GPL-3.0 sono nel file. WCSLIB (LGPL-3, in astropy): testo completo nel file, compatibile.
- Apache-2.0 (`openai`, `requests`, `google-crc32c`, `opentelemetry-api`, `packaging`): compatibile con la GPL-3.0
  (non con la GPL-2.0): per questo l'insieme distribuito è effettivamente sotto la GPL **versione 3**.
- MPL-2.0 (`certifi`): compatibile con la GPL-3.0 (clausola "Secondary License" della MPL-2.0).
- Tutte le altre (MIT, BSD, ISC, PSF, MIT-CMU, Zlib, 0BSD, CC0): permissive e compatibili. QD/LBNL in `spherical-geometry`
  (BSD modificata): compatibile; resta **da verificare** la frase sull'uso commerciale (fuori dalle clausole) e il segnaposto
  `<COPYRIGHT HOLDER>` non compilato nel testo di `pims`.
- Escluse e da non aggiungere: `healpy` (GPL-2.0-only, già escluso: incompatibile con la GPL-3.0 insieme alle librerie Apache-2.0)
  e ogni licenza non libera o con divieto di uso commerciale.
- Il kernel `pck00011.tpc` (NAIF) è un **dato** distribuito senza modifiche con le regole d'uso della NAIF, non è coperto dalla
  GPL-3.0 di AstroTwo.

**Crediti dei dati e dei servizi (da mostrare nell'app e nelle immagini esportate; testi letti il 2026-10-17).**

| Servizio / dato | Testo di riconoscimento richiesto o richiesto/gradito | Fonte |
|---|---|---|
| Simbad (CDS) | "This research has made use of the SIMBAD database, CDS, Strasbourg Astronomical Observatory, France" + 2000, A&AS, 143, 9, "The SIMBAD astronomical database", Wenger et al. | `https://cds.unistra.fr/help/acknowledgement/` |
| VizieR (CDS), servizio | "This research has made use of the VizieR catalogue access tool, CDS, Strasbourg Astronomical Observatory, France (DOI : 10.26093/cds/vizier)." + 2000, A&AS, 143, 23, "The VizieR database of astronomical catalogues", Ochsenbein et al. | `https://cds.unistra.fr/help/acknowledgement/`, `https://cds.unistra.fr/vizier-org/licences_vizier.html` |
| VizieR, dati dei singoli cataloghi | citare autori, produttore ed editore del catalogo (file ReadMe); alcuni cataloghi hanno una sezione "Acknowledging"; **l'uso commerciale dei dati dipende dall'origine di ciascun catalogo** | `https://cds.unistra.fr/vizier-org/licences_vizier.html` |
| Sesame (risolutore di nomi del CDS) | testo ufficiale proprio **non trovato**: **da verificare** (nel frattempo vale il riconoscimento di Simbad, di cui Sesame interroga la base) | `https://cds.unistra.fr/help/acknowledgement/` |
| HiPS (CDS) | testo ufficiale **non trovato** nella pagina dei riconoscimenti del CDS: **da verificare** (articolo di riferimento: Fernique et al. 2015, A&A 578, A114, **da verificare**) | — |
| MocServer (CDS) | testo ufficiale **non trovato**: **da verificare** | — |
| Servizio X-Match del CDS (se usato) | "This research has made use of the CDS cross-match service, Strasbourg Astronomical Observatory, France." + 2012, ASPC, 461, 291 (Boch et al.) e 2020, ASPC, 522, 125 (Pineau et al.) | `https://cds.unistra.fr/help/acknowledgement/` |
| Survey DSS2 (STScI/MAST) | "The Digitized Sky Surveys were produced at the Space Telescope Science Institute under U.S. Government grant NAG W-2166. The images of these surveys are based on photographic data obtained using the Oschin Schmidt Telescope on Palomar Mountain and the UK Schmidt Telescope. The plates were processed into the present compressed digital form with the permission of these institutions." seguito dai paragrafi su POSS-I, POSS-II, Oschin Schmidt, UK Schmidt e ESO (testo integrale alla fonte) | `https://archive.stsci.edu/dss/acknowledging.html` |
| DSS: copyright | le immagini sono protette da copyright (Caltech 1993-1995 per la parte nord, AAO Board 1993-5, UK SERC/PPARC e AAT Board 1992-5, AURA 1995 per il resto), "distribuite per accordo"; la pagina **non dice nulla sull'uso commerciale** → **uso commerciale delle immagini DSS: da verificare** (da chiarire con STScI prima di una versione Pro o di una distribuzione commerciale) | `https://archive.stsci.edu/dss/copyright.html` |
| NAIF / SPICE (kernel e toolkit) | riconoscimento incoraggiato, non obbligatorio; uso anche commerciale ammesso senza licenze né costi; testo preciso nella pagina "credit" della NAIF: **da verificare** | `https://naif.jpl.nasa.gov/naif/rules.html` |

**Requisiti del modulo 60 (registrati il 2026-10-17, non implementati ora).** Il `60-distribuzione-dmg.md` dovrà prevedere:

1. finestra **"Licenze"** nel menu Informazioni (licenza di AstroTwo, `THIRD_PARTY_LICENSES`, crediti dei dati);
2. librerie **Qt/PySide6 separate e sostituibili** dall'utente, **non modificate**;
3. **link o offerta scritta** per il sorgente esatto di PySide6/Qt corrispondente alle librerie incluse nel `.dmg`;
4. **nessun divieto di reverse engineering** nelle condizioni d'uso (richiesto dalla LGPL-3 per le librerie Qt);
5. note di **Python (PSF)** e di **Qt** (avvisi delle componenti incluse, elenco "Licenses Used in Qt") in `THIRD_PARTY_LICENSES`;
6. **crediti anche nelle immagini esportate** (testo di riconoscimento del survey e dei servizi usati);
7. **verifica del marchio "AstroTwo"** (disponibilità, prima della distribuzione pubblica).

## 7. Come si collegano i livelli

- **Registro strumenti (livello 3):** gli strumenti esposti all'IA si
  dichiarano **nel `32-ia-registro-strumenti.md`**, non nel §11 dei moduli
  (decisione del proprietario del 2026-10-10, da D11-9): il §11 di un modulo
  rimanda al 32, che descrive per ogni strumento la funzione deterministica
  del modulo chiamata; il registro non ricalcola nulla. **Dal 2026-10-16:**
  ogni strumento è un **comando del `05`** scelto da un **elenco esplicito**
  nel 32, descritto con lo schema di `export_schema`, validato dal `05` ed
  eseguito nella stessa coda dei comandi dell'utente con `requested_by =
  ai`; i testi esterni nei risultati sono dati, mai istruzioni.
- **Verifica risultati (livello 3):** ogni valore numerico prodotto su richiesta
  dell'IA passa da un calcolo deterministico del livello 1/2 (un comando
  del `05`); `34-ia-verifica-risultati.md` controlla che **ogni numero
  scritto nella risposta** corrisponda a un risultato di comando (o alla
  domanda dell'utente) ed evidenzia quelli che non corrispondono.
- **Livello 3 nella v1 (dal 2026-10-16):** il livello 3 (30, 31, 32, 34,
  35, con il pannello 44) si costruisce **adesso sopra il livello 1**, prima
  del livello 2: usa solo comandi del `05` che chiamano i moduli 10–19. Le
  dipendenze restano solo verso il basso; quando il livello 2 esisterà, i
  suoi comandi entreranno nel 32 con una modifica del 32. Il 33 (ADQL
  scritto dall'IA) è rimandato.
- **Riproducibilità (livello 1, dal 2026-10-15):** ogni azione
  dell'interfaccia è un comando del registro di `05-comandi-sessione.md`
  (livello 1, AM1 accettata il 2026-10-15), con nome, parametri tipizzati con
  unità e risultato strutturato, registrato e rieseguibile; la sessione si
  riapre rieseguendo i comandi. `24-analisi-pipeline-riproducibili.md`
  (livello 2) costruirà pipeline, scripting e API Python sopra il `05`; il
  `32` userà lo schema JSON dei comandi del `05`.
- **Interfaccia:** la UI legge gli stati dei moduli e invoca le loro funzioni
  pubbliche; non conserva copie di dati scientifici con logica propria.

## 8. Prestazioni e risorse (vincoli generali)

- Il livello 1 deve restare interattivo: zoom/pan e sovrapposizione cataloghi
  senza attese percepite su dati già in memoria. **Valori quantitativi
  decisi il 2026-10-15 (decisione del proprietario) in
  `41-ui-visualizzatore-cielo.md` §3.15** (obiettivi P1–P7 con test
  marcati `perf`: es. ≤ 16,7 ms per fotogramma al 95° percentile con 1
  milione di sorgenti, thread principale mai fermo più di 100 ms); se un
  obiettivo non si raggiunge si misura e si riporta, mai abbassarlo in
  silenzio.
- Le reti sono sempre considerate non disponibili: ogni funzione di rete ha un
  timeout dichiarato e un messaggio d'errore esplicito (vedi moduli 11–14).
- **Obiettivi di prestazioni (requisito non funzionale):** devono essere
  **almeno pari ad Aladin**. **Obiettivo minimo (decisione del proprietario,
  2026-10-08): almeno 1 milione di sorgenti di catalogo con 1 GB di RAM**
  (fonte: manuale utente di Aladin, ed. giugno 2022, sezione 8.3). Gli altri
  obiettivi (dimensione di immagini e cubi caricabili) e il dettaglio di tutti
  i test misurabili restano in `61-strategia-test.md`.
- La memoria deve essere limitata e dichiarata: non si caricano interi cataloghi
  HiPS/FITS in RAM senza un tetto. Tetti precisi: decisione **A10**, decisa
  per immagini (11), cataloghi (13) e HiPS (12); valori nei moduli
  interessati e nella riga A10 di §5.
- **Cache (vincoli da A7):** SQLite per le interrogazioni ai cataloghi, file su
  disco per i riquadri HiPS e FITS; limite di spazio configurabile
  dall'utente con eliminazione dei dati meno usati; ogni dato servito dalla
  cache mostra origine e data di scaricamento (da mostrare anche nei registri
  di riproducibilità). Dettagli operativi nei moduli `11`, `12`, `13`, `14`.

## 9. Dettaglio delle decisioni (chiuse e aperte)

- **DA-01 — A1, Toolkit UI: DECISA il 2026-10-04** — `PySide6 (Qt)`, con il
  rendering delle mappe in OpenGL da specificare in
  `41-ui-visualizzatore-cielo.md`; spostata in §4.2.
- **DA-02 — A5, Provider IA: DECISA il 2026-10-04** — interfaccia a capacità
  (chiamata di strumenti, streaming) con due implementazioni iniziali
  (provider cloud + endpoint compatibile OpenAI); spostata in §4.2. Dettagli
  e vincoli in `30-ia-adattatore-provider.md`.
- **DA-03 — A6, Firma Apple:** orientamento del 2026-10-09: sì, firma e
  notarizzazione con account Apple Developer solo al momento della
  distribuzione; si decide con l'approvazione di `60-distribuzione-dmg.md`.
- **DA-04 — A9, Lingua dell'interfaccia: DECISA il 2026-10-15** (decisione
  del proprietario): testi in inglese con `tr()`, traduzione italiana nostra
  con Qt Linguist, traduzioni di Qt per i dialoghi standard, lingua dal
  sistema cambiabile nelle preferenze, numeri scientifici sempre con il
  punto decimale; spostata in §4.2, dettagli in `40-ui-finestra-principale.md`.
- **DA-05 — A2, Strumento di packaging del `.dmg`:** orientamento del
  2026-10-09: PyInstaller + dmgbuild; si decide con l'approvazione di
  `60-distribuzione-dmg.md`, insieme ad A6.
- **DA-07 — A10, Tetti di memoria:** valori per immagini, cataloghi e HiPS,
  coerenti con l'obiettivo di §8; **per le immagini decisi il 2026-10-10**
  (valori in `11-core-immagini-fits.md` §3); **per i cataloghi il
  2026-10-10** (D13-4 nel 13); **per gli HiPS il 2026-10-12** (512 MB di tile
  in memoria, configurabili; `build_hips` un tile alla volta entro il limite
  delle operazioni di 4 GB; cache comune di 5 GB su disco; valori nel 12).
- **DA-08 — A11, Licenza di AstroTwo: DECISA il 2026-10-17** (decisione del proprietario) — **GPL-3.0-or-later**, titolare
  Guido Ratti (anno 2026, unico titolare). Dettagli, verifica di compatibilità con le dipendenze, crediti dei dati e requisiti
  per il `60` in §6.1. Collegata alla regola d'oro n. 8 di `CLAUDE.md` (nessun codice né dato preso da Aladin, che è GPL).
- **DA-06 — A8, Compatibilità con lo scripting di Aladin:** rimandata a dopo il
  completamento del livello 1; la strada "scripting principale in Python" resta
  valida nel frattempo.

## 10. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). Confermate S1–S7; aperte A1–A9. |
| 2026-10-04 | agente di sviluppo | Decisioni prese: A3 (struttura `src/astrotwo/` + `tests/`), A4 (Python 3.12, `pyproject.toml`, `uv`), A7 (cache SQLite/file con limite configurabile e provenienza). Orientamento provvisorio: A1 = PySide6, A5 = interfaccia a capacità con provider cloud + endpoint compatibile OpenAI. Rimandata A8 (scripting Aladin) a dopo il livello 1. Etichette armonizzate con `panoramica.md` e `03-parita-aladin.md`: prima A5 = firma Apple → ora A6; prima A6 = provider IA → ora A5. |
| 2026-10-04 | agente di sviluppo | **Nuovo principio (§2, decisione del proprietario P11):** la parità con Aladin è il minimo, non il traguardo — AstroTwo include tutte le funzioni di `03-parita-aladin.md`, anche non confermate nella documentazione (C3, F2, G3, E4 diventano `inclusa (decisione del proprietario)`); sulle funzioni non documentate resta solo la verifica tecnica di implementazione. |
| 2026-10-04 | agente di sviluppo | §5: **AM1 decisa** — accettate le proposte `18-core-calcolatrici.md` (H4) e `45-ui-viste-multiple.md` (H2), registrati in `panoramica.md` e `INDICE.md` con stato `non esiste`. |
| 2026-10-04 | agente di sviluppo | **Decisioni del proprietario: A1 e A5 passate da aperte a prese.** A1 = `PySide6 (Qt)` con rendering OpenGL delle mappe da specificare in `41-ui-visualizzatore-cielo.md`; A5 = interfaccia a capacità (chiamata di strumenti, streaming) con due implementazioni iniziali (provider cloud + endpoint compatibile OpenAI). Spostate dalla tabella §5 a §4.2, DA-01/DA-02 aggiornati in §9; moduli dipendenti (40–45, 30–35, 61) ancora da scrivere, nessun testo da cambiare. |
| 2026-10-04 | agente di sviluppo | §8: nuovo **requisito non funzionale sulle prestazioni** — obiettivi di prestazioni (righe di catalogo, dimensione di immagini e cubi) da definire in `61-strategia-test.md` e **almeno pari ad Aladin** (centinaia di migliaia di righe; sezione 8.3 del manuale, da leggere). |
| 2026-10-08 | Claude Code | Manutenzione: riferimenti ad `AGENTS.md` sostituiti con `CLAUDE.md` (§2, §4.1, §4.2, §6); dopo AM1 interfaccia = moduli **40–45** (§3 e §6) e nucleo = moduli **10–18** (§6); refuso "igualmente" → "ugualmente" (§3). |
| 2026-10-08 | Claude Code | §8: indicata l'edizione del manuale di Aladin accanto alla sezione 8.3 (ed. giugno 2022, AP6 decisa in `03-parita-aladin.md`). |
| 2026-10-08 | Claude Code | §8: **obiettivo minimo di prestazioni** (decisione del proprietario) = almeno 1 milione di sorgenti di catalogo con 1 GB di RAM (manuale Aladin ed. giugno 2022, sez. 8.3); dettaglio dei test in `61-strategia-test.md`. §6: nucleo = moduli 10-19 (AM1: accettato `19-core-dati-planetari.md`). |
| 2026-10-09 | Claude Code | **Decisioni del proprietario (checklist del livello 1):** A2, A6, A9 non bloccano il livello 1 e passano come bloccanti dell'approvazione di `60` (A2, A6) e `40` (A9), con orientamento: A2 = PyInstaller + dmgbuild; A6 = sì, notarizzazione con account Apple Developer solo al momento della distribuzione; A9 = inglese di base + italiano con le traduzioni di Qt (§5, §9). Nuova **A10** (tetti di memoria, Gruppo 3) al posto del rinvio senza etichetta in §8. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-09. |
| 2026-10-09 | Claude Code | §4.2 (note): **framework dei test = `pytest`** (decisione del proprietario), anticipata da `61-strategia-test.md`. Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Decisioni del proprietario:** nuova decisione aperta **A11 — Licenza di AstroTwo** (Gruppo 2, blocca il 60, §5 e §9 DA-08); **A10 decisa per le immagini** (valori nell'11), resta aperta per cataloghi e HiPS. Nuova regola d'oro n. 8 in `CLAUDE.md` (AstroTwo scritto da zero, nulla preso da Aladin). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | **Decisioni del proprietario** (autorizzazione esplicita a modificare il file approvato): §7 — gli strumenti per l'IA si dichiarano nel 32, non nel §11 dei moduli (da D11-9). A10 resta la strategia di caricamento delle immagini; il limite delle operazioni (4 GB) è separato, D11-11 nell'11. Stato `approvato` invariato. |
| 2026-10-12 | Claude Code | **A10 per gli HiPS** (decisione del proprietario del 2026-10-12, autorizzazione esplicita a modificare il file approvato): riga A10 di §5, §8 e DA-07 aggiornate con l'esito — tile in memoria entro 512 MB configurabili, `build_hips` un tile alla volta entro il limite delle operazioni di 4 GB, cache comune di 5 GB su disco; A10 interamente decisa. Stato `approvato` invariato. |
| 2026-10-13 | Claude Code | **Decisione del proprietario del 2026-10-13** (autorizzazione esplicita a modificare il file approvato): creato `THIRD_PARTY_LICENSES` nella radice (nome, versione, licenza e avvisi di tutte le dipendenze, compreso l'avviso QD/LBNL di `spherical-geometry`), generato da `scripts/third_party_licenses.py` e controllato da un test; registrato in §6, annotato per A11 (§9 DA-08) e per il 60; regola: ogni nuova dipendenza va aggiunta al file. Stato `approvato` invariato. |
| 2026-10-15 | Claude Code | **Decisioni del proprietario del 2026-10-15** (proposta della fase 1 dell'interfaccia, autorizzazione esplicita a modificare il file approvato): **A9 decisa** (inglese con `tr()`, italiano nostro con Qt Linguist, traduzioni di Qt, lingua dal sistema, punto decimale sempre) e spostata da §5 a §4.2, DA-04 chiusa; §8 — valori quantitativi delle prestazioni decisi nel `41` §3.15; §7 — riproducibilità con il registro dei comandi di `05-comandi-sessione.md` (livello 1, AM1 accettata), il `24` sopra il `05`; §3 — livello 1 con i file generali 04 e 05; DA-08 — PySide6/Qt e pytest-qt da verificare per A11. Stato `approvato` invariato. |
| 2026-10-16 | Claude Code | **Decisioni del proprietario del 2026-10-16** (proposta della fase 1 sull'IA nella v1, autorizzazione esplicita a modificare il file approvato): A5 precisata (SDK `anthropic` e `openai` con endpoint configurabile, nessun modello nel codice, `AI_NO_TOOLS`); §7 — registro degli strumenti del 32 come elenco esplicito di comandi del `05`, verifica del 34 sui numeri della risposta, livello 3 costruito ora sopra il livello 1 (33 rimandato). Stato `approvato` invariato. |
| 2026-10-16 | Claude Code | **Decisione del proprietario del 2026-10-16** (autorizzazione esplicita a modificare il file approvato): §6 — identificativo del progetto `dev.pages.astrotwo` (sito `astrotwo.pages.dev`), bundle identifier dell'app per il 60, servizio del Portachiavi `dev.pages.astrotwo.ai` per il 31. Stato `approvato` invariato. |
| 2026-10-16 | Claude Code | §6: `THIRD_PARTY_LICENSES` con le dipendenze della v1 dell'interfaccia e dell'IA e la sezione degli strumenti di sviluppo (verifiche del 2026-10-16, nell'ambito di "FASE: CODICE – interfaccia v1"). Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **Decisione del proprietario del 2026-10-17** (autorizzazione esplicita a modificare il file approvato): §6 — verifica di `httpx2` registrata (dipendenza ufficiale di `anthropic` e `openai`, impronte del `uv.lock` uguali a PyPI, autore Tom Christie, manutentore Pydantic Services Inc., repository `github.com/pydantic/httpx2`, prosecuzione dichiarata da Pydantic e non da `encode/httpx`, nessuna attestazione di pubblicazione su PyPI) e accettata; regola: versioni bloccate nel `uv.lock`, aggiornamento solo esplicito e con nuovo controllo delle impronte. Stato `approvato` invariato. |
| 2026-10-17 | Claude Code | **A11 decisa dal proprietario: GPL-3.0-or-later**, titolare Guido Ratti 2026 (autorizzazione esplicita a modificare il file approvato): riga A11 spostata da §5 a §4.2; nuova §6.1 (licenza, verifica di compatibilità con le dipendenze, crediti dei dati, requisiti del modulo 60); DA-08 chiusa. Stato `approvato` invariato. |
