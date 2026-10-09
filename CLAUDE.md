# CLAUDE.md — AstroTwo

## Cos'è AstroTwo

AstroTwo è il nuovo programma di riferimento per gli astrofisici, successore di **Aladin** (CDS di Strasburgo).
Deve fare tutto ciò che fa Aladin, molto di più, e avere un livello di intelligenza artificiale.
Si consegna come app macOS (file `.dmg`). Per l'IA l'utente sceglie il provider e inserisce la propria API key.

Obiettivo: qualità da software scientifico professionale. Ogni risultato mostrato all'utente deve essere corretto, verificabile e riproducibile.

Principio P11: **la parità con Aladin è il minimo, non il traguardo.** Tutte le funzioni di `mdfiles/03-parita-aladin.md` sono incluse.

## Fase attuale

**FASE: SPECIFICHE (nessun codice)** — per tutti i livelli finché il proprietario non dichiara la fase codice di un livello.

- La fase codice si dichiara **per livello**: il proprietario scrive testualmente "FASE: CODICE – livello N". Da quel momento si può scrivere codice **solo per i moduli `approvato` di quel livello**; tutti gli altri livelli restano in fase specifiche.
- Senza quella dichiarazione non si scrive codice applicativo, nemmeno per moduli `approvato`.
- Nei livelli in fase specifiche si lavora solo sui file `.md` in `mdfiles/`.
- Se ti viene chiesto codice per un livello ancora in fase specifiche, ricorda la regola e proponi di completare prima il `.md` del modulo.
- Solo i file con stato `approvato` autorizzano a scrivere il codice di quel modulo; le verifiche segnate "da verificare prima del codice" nel `.md` si fanno prima di scriverlo.
- Livelli in fase codice: **nessuno**.

## Regole d'oro (non negoziabili)

1. **L'IA non calcola mai.** Ogni numero, coordinata, misura o risultato scientifico viene da codice deterministico e testato. L'IA interpreta richieste, sceglie gli strumenti e spiega i risultati; non produce valori numerici da sola.
2. **Prima la specifica, poi il codice.** Nessun modulo viene scritto senza il suo `.md` completo e `approvato`.
3. **Un modulo = un file `.md`** in `mdfiles/`, che spiega esattamente cosa fa e cosa non fa.
4. **Non reinventare la scienza.** Si usano librerie consolidate (Astropy, astroquery, healpy, pyvo, mocpy, reproject…). Scelte e motivazioni in `mdfiles/01-architettura.md`.
5. **Le API key non vanno mai in file, log o repository.** Solo nel Portachiavi di macOS.
6. **Riproducibilità.** Ogni operazione dell'utente deve poter essere registrata e rieseguita (ogni azione dell'interfaccia = un comando registrato).
7. **Il progetto è a livelli e deve funzionare sempre.** Livello 1 nucleo (pari ad Aladin), 2 analisi, 3 IA, 4 funzioni avanzate. Dipendenze solo verso il basso (`4 → 3 → 2 → 1`). Un livello non rompe mai quello sotto; senza IA l'app funziona ai livelli 1 e 2.

## Come lavorare

- **Prima di toccare un modulo** leggi `mdfiles/riassunto.md`, `mdfiles/INDICE.md`, e il `.md` di quel modulo (più quelli da cui dipende). Non caricare tutti i file: `panoramica.md` e `03-parita-aladin.md` sono lunghi, leggine solo le sezioni che servono.
- Se il `.md` di un modulo manca, è incompleto o ambiguo: **fermati e chiedi**. Non inventare funzioni, interfacce o comportamenti.
- Se il comportamento di un modulo cambia, aggiorna prima il suo `.md`, poi il resto.
- Non aggiungere funzioni né moduli non previsti. Proposte di moduli nuovi → registrale in `panoramica.md` (meccanica AM1) e aspetta la decisione del proprietario.
- Una decisione tecnica aperta si scrive "da decidere" nel `.md` pertinente e in `mdfiles/decisioni-aperte.md`; **mai sceglierla in silenzio**. Puoi proporre una raccomandazione, la decisione è del proprietario.
- Ciò che non è verificato si scrive "da verificare".
- Lavora **un gruppo di moduli alla volta**, poi fermati e chiedi la validazione.

### Aggiornamento obbligatorio a ogni progresso

Un progresso è: un file creato, un file che cambia stato, una decisione presa, un modulo completato. Ogni volta aggiorna:

1. `mdfiles/panoramica.md` — stato (§2), tabella moduli (§4), decisioni prese (§5) e aperte (§6), prossimi passi (§7), registro modifiche (§8);
2. `mdfiles/INDICE.md` — stato del file e riepilogo dei conteggi;
3. `mdfiles/riassunto.md` — se cambiano stato generale o prossimi passi;
4. `mdfiles/decisioni-aperte.md` — se una decisione viene aperta o chiusa (prima il file di origine, poi questo).

Non chiudere un lavoro senza averli aggiornati. Nel registro modifiche scrivi come autore `Claude Code`.

## Struttura della cartella

```
astrotwo/
├── CLAUDE.md            questo file (sostituisce il vecchio AGENTS.md)
└── mdfiles/             tutte le specifiche
    ├── riassunto.md         il progetto in 5 righe
    ├── panoramica.md        riassunto completo, sempre aggiornato
    ├── INDICE.md            elenco di tutti i file con stato
    ├── decisioni-aperte.md  tutte le decisioni aperte, in 3 gruppi
    ├── TEMPLATE-modulo.md   modello obbligatorio (14 sezioni)
    └── NN-*.md              un file per ogni modulo
```

Struttura del codice (già decisa, A3/A4) — da creare solo in FASE: CODICE:

```
├── pyproject.toml       Python 3.12, gestore pacchetti uv
├── src/astrotwo/
│   ├── core/            livello 1  (moduli 10-19)
│   ├── analysis/        livello 2  (moduli 20-24)
│   ├── ai/              livello 3  (moduli 30-35)
│   ├── ui/              interfaccia (moduli 40-45)
│   └── advanced/        livello 4  (moduli 50-53)
└── tests/               stessa struttura di src/astrotwo/
```

Corrispondenza specifica ↔ codice: `10-core-coordinate-wcs.md` → `src/astrotwo/core/coordinates_wcs.py`.

## Regole per i file `.md`

- Lingua: italiano. Nomi di codice (classi, funzioni, file, errori) in inglese.
- Ogni file di modulo segue `mdfiles/TEMPLATE-modulo.md`: 14 sezioni, stesso ordine, nessuna saltata (se non pertinente: "non applicabile" con motivo).
- Numerazione: `00-09` generali, `10-19` nucleo, `20-29` analisi, `30-39` IA, `40-49` interfaccia, `50-59` avanzate, `60-69` distribuzione e test.
- Stato in testa a ogni file: `bozza`, `in revisione` o `approvato`. I file nuovi nascono `bozza`. Solo il proprietario porta un file ad `approvato`.
- Ogni file deve bastare da solo: chi lo legge capisce il modulo senza leggere il codice.
- `AGENTS.md` è stato rimosso il 2026-10-08: eventuali citazioni rimaste nelle voci storiche dei registri modifiche vanno intese come riferimenti a questo `CLAUDE.md`.

## Scelte tecniche già decise (dettagli nei file indicati)

- Python 3.12, `pyproject.toml`, `uv` (A4); UI **PySide6 (Qt)**, rendering mappe OpenGL specificato in `41` (A1).
- IA: interfaccia "a capacità" (tool calling + streaming), provider cloud + endpoint compatibile OpenAI (A5).
- Cache: SQLite per i cataloghi, file su disco per tile HiPS/FITS, 5 GB di default configurabili, origine e data sempre mostrate (A7, D11-3).
- Coordinate: ICRS di default; **epoca mai assunta**, letta dai metadati e sempre scritta nel risultato (D10-2/D13-2, `02-convenzioni.md` DC2).
- Tempo: JD interno via `astropy.time`, ISO 8601 solo in UI/file, scala sempre dichiarata (DC1).
- Numeri: tipo nativo in memoria, calcoli in `float64`, `float32` solo per il display (DC6). Unità sempre esplicite via `astropy.units`.
- Pixel: in memoria indice da 0 (numpy), convenzione FITS (indice da 1) solo ai bordi, conversione unica nel modulo 10 (DC7).
- Corpo: campo `body` obbligatorio nei metadati; `celestial` per i dati astronomici, ricavato dal sistema di coordinate, mai assunto; sovrapposizioni tra corpi diversi = errore, forzabile solo con opzione esplicita citata nel risultato (D19-3, D19-4).
- Elenco completo: `mdfiles/panoramica.md` §5; decisioni ancora aperte: `mdfiles/decisioni-aperte.md`.

## Definizione di "fatto" per un modulo

Un modulo è fatto solo se: il suo `.md` è `approvato`, il codice rispetta il `.md`, i test descritti nel `.md` passano, nessuna regola d'oro è violata, e `mdfiles/panoramica.md` è aggiornata.
