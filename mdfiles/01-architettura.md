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
                                  cross-match, MOC, misure

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
| **A5** | 2026-10-04 | Interfaccia IA **a capacità** (chiamata di strumenti + streaming) con due implementazioni iniziali: **provider cloud** e **endpoint compatibile OpenAI** (che copre anche i modelli locali) | conforme a `CLAUDE.md` (l'utente sceglie il provider e inserisce la propria chiave), un solo contratto da testare, copertura di cloud e modelli locali; confermata dal proprietario prima dei moduli 30–35 |

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
| A9 | Lingua dell'interfaccia | solo inglese · solo italiano · entrambe (internazionalizzazione) | `40-ui-finestra-principale.md` | **orientamento (2026-10-09): inglese di base + italiano** con le traduzioni di Qt; blocca l'approvazione di `40-ui-finestra-principale.md` |
| A10 | Tetti di memoria per immagini, cataloghi e HiPS caricati | valori per modulo, coerenti con l'obiettivo di §8 | `11`, `12`, `13`, `61-strategia-test.md` | da fissare al momento del codice (Gruppo 3) |

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
- Dove vivano gli strumenti di packaging del modulo 60: da definire in
  `60-distribuzione-dmg.md`.

## 7. Come si collegano i livelli

- **Registro strumenti (livello 3):** i moduli del livello 1 e 2 che espongono
  funzioni all'IA lo dichiarano nel proprio file `.md`, sezione "Esposizione
  all'IA". Il registro (`32-ia-registro-strumenti.md`) raccoglie queste
  descrizioni; non ricalcola nulla.
- **Verifica risultati (livello 3):** ogni valore numerico prodotto su richiesta
  dell'IA passa da un calcolo deterministico del livello 1/2 e viene
  ri-verificato da `34-ia-verifica-risultati.md` prima di essere mostrato.
- **Riproducibilità (livello 2):** ogni operazione registrata da
  `24-analisi-pipeline-riproducibili.md` richiama moduli del livello 1/2 per
  nome e parametri, così può essere rieseguita.
- **Interfaccia:** la UI legge gli stati dei moduli e invoca le loro funzioni
  pubbliche; non conserva copie di dati scientifici con logica propria.

## 8. Prestazioni e risorse (vincoli generali)

- Il livello 1 deve restare interattivo: zoom/pan e sovrapposizione cataloghi
  senza attese percepite su dati già in memoria. Valori quantitativi: da
  decidere nel file `41-ui-visualizzatore-cielo.md` con test misurabili.
- Le reti sono sempre considerate non disponibili: ogni funzione di rete ha un
  timeout dichiarato e un messaggio d'errore esplicito (vedi moduli 11–14).
- **Obiettivi di prestazioni (requisito non funzionale):** devono essere
  **almeno pari ad Aladin**. **Obiettivo minimo (decisione del proprietario,
  2026-10-08): almeno 1 milione di sorgenti di catalogo con 1 GB di RAM**
  (fonte: manuale utente di Aladin, ed. giugno 2022, sezione 8.3). Gli altri
  obiettivi (dimensione di immagini e cubi caricabili) e il dettaglio di tutti
  i test misurabili restano in `61-strategia-test.md`.
- La memoria deve essere limitata e dichiarata: non si caricano interi cataloghi
  HiPS/FITS in RAM senza un tetto. Tetti precisi: decisione **A10** (Gruppo 3), da
  fissare al momento del codice nei moduli interessati.
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
- **DA-04 — A9, Lingua dell'interfaccia:** orientamento del 2026-10-09:
  inglese di base + italiano con le traduzioni di Qt; si decide con
  l'approvazione di `40-ui-finestra-principale.md`.
- **DA-05 — A2, Strumento di packaging del `.dmg`:** orientamento del
  2026-10-09: PyInstaller + dmgbuild; si decide con l'approvazione di
  `60-distribuzione-dmg.md`, insieme ad A6.
- **DA-07 — A10, Tetti di memoria:** valori per immagini, cataloghi e HiPS,
  coerenti con l'obiettivo di §8; da fissare al momento del codice (Gruppo 3).
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
