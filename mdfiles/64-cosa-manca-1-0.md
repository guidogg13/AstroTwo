# 64-cosa-manca-1-0.md — Cosa manca alla 1.0 (rapporto degli sprint D7–D10)

**Stato:** bozza

> Creato il 2026-11-11 (sprint D7) su richiesta del proprietario: per ogni
> passo della checklist `63-checklist-rilascio.md`, fino al passo 9 (megatest
> sul `.dmg` candidato) compreso, se è pronto, cosa manca e chi lo deve fare.
> È una fotografia del 2026-11-11: non è un modulo di codice (le sezioni che
> parlano di codice dicono «non applicabile») e non decide niente. Si
> aggiorna a ogni sprint verso la 1.0 e si archivia con la release.

## 2. Scopo

Sapere in un colpo d'occhio cosa separa AstroTwo 0.1.0-beta.5 dal `.dmg`
candidato della 1.0 e dal megatest superato, e **chi** deve fare ogni cosa:
**Claude Code** (nella sessione di sviluppo) oppure **Guido** (il proprietario:
decisioni, account Apple, Zenodo, Ko-fi, sito).

## 3. Cosa fa

### 3.1 Decisioni del proprietario del 2026-11-11 che valgono qui

- La 1.0 **non si rilascia** con la validazione di Gaia, VizieR/SED,
  SIMBAD contro il CDS e Pianeti mai misurata, salvo decisione diversa del
  proprietario dopo questo rapporto.
- **Nessun `.dmg` candidato** finché il proprietario non lo autorizza.

### 3.2 Prima della checklist: cosa blocca il passo 3

| # | Cosa | Stato al 2026-11-11 | Chi |
|---|---|---|---|
| P1 | **Validazione delle sezioni non misurate** (`docs/validation.md`) | **In parte fatta (sprint D9, D10).** Quarta misura (2026-11-11, 21:28–21:34 UTC, candidato build 7, commit `c43d622`) sui tre oggetti con pianeti, dopo `D05-6`: **72 pianeti su 72 entro la tolleranza**, tolleranze invariate (§5.0ter). Con gli altri quattro oggetti della terza misura: **379 pass, 0 fail, 48 non misurati**. Non misurati: 2MASS/AllWISE contro VizieR e serie SED (TAPVizieR giù, 37 righe); 11 righe senza designazione 2MASS/AllWISE nel mirror di Harvard, **non verificabile contro SIMBAD del CDS** (404 alle 21:04, 21:15, 21:28 UTC; Sesame «Nothing found»): restano «non misurate», non «non applicabili». SIMBAD solo contro il mirror di Harvard. La validazione non blocca il candidato (decisione del 2026-11-11), si riprova prima del rilascio | Guido (rilascio con o senza VizieR/CDS); Claude Code (nuova misura quando il CDS torna) |
| P2 | **Decisioni aperte da chiudere prima** (`decisioni-aperte.md` §0): `D14-15` e `D42-1` (scelte già nel codice, «da confermare»), `A6-b` (passo 7 o passo 8) | **Fatto il 2026-11-11** (sprint D8): `A6-b` decisa (1.0 senza firma Developer ID, passo 8), `D14-15` e `D42-1` confermate; 16 aperte, nessuna blocca la 1.0 | Guido (fatto) |
| P3 | **Testo di posizionamento in `pyproject.toml`**: `description = "AstroTwo: successore di Aladin per gli astrofisici"` (riga 4), contrario al posizionamento «complementare, mai sostituto» del passo 2 | **Fatto nello sprint D8:** descrizione uguale alla prima riga del README; stessa frase tolta dalla docstring di `src/astrotwo/__init__.py`. `CITATION.cff`, `.zenodo.json` e `Info.plist` (generato da `build_app.py`: nomi, versione, copyright) non avevano frasi così | Claude Code (fatto) |
| P4 | **Approvazione del `62`** (megatest): il file è ancora `bozza`, mentre la `63` (approvata) lo usa al passo 9 | Da approvare | Guido |
| P5 | **Via al `.dmg` candidato** | **Dato dal proprietario il 2026-11-11** (versione 1.0.0 e `.dmg` candidato senza firma Developer ID; niente tag, push, release, Zenodo prima del megatest; la validazione non blocca il candidato e si riprova prima del rilascio) | Guido (fatto) |

### 3.3 Passi 1–9 della checklist `63`

| Passo | Cosa | Pronto? | Cosa manca | Chi |
|---|---|---|---|---|
| 1 | Stato pulito su `main` | **Fatto** (sprint D10) | Albero pulito su `fe542ff` (D10a, correzione di `D05-6`) prima del passo 3. `origin/main` resta indietro: il push si fa solo al passo 10, dopo il megatest | Claude Code |
| 2 | Testi coerenti con il posizionamento | **Fatto** (sprint D9) | Comando del passo 2 ripetuto: nessuna frase «successore/sostituto» nei metadati; resta un falso positivo in un commento del codice (`main_window.py`, «un sostituto» del Portachiavi) | Claude Code |
| 3 | Versione 1.0.0 in quattro punti | **Fatto** (sprint D9; build 7 nello sprint D10) | `pyproject.toml` `1.0.0`, `__init__.py` `1.0.0`, **build `7`** (il build 6 è scartato), `CITATION.cff` `1.0.0` con `date-released: "2026-11-11"` (data del commit della versione `c43d622`, invariata); `test_build_app.py::test_versions` aggiornato al build 7 | Claude Code |
| 4 | `uv lock` prima di `git add` | **Fatto** (sprint D10) | `uv lock`: lockfile invariato (versione del progetto invariata, cambia solo il build) | Claude Code |
| 5 | Suite completa con i test di rete e commit della versione | **Fatto** (sprint D10) | **Commit della versione `c43d622`** («Release 1.0.0: versione (build 7)», 2026-11-11), **1352** test di default passati, ruff pulito, `--no-network`. Test di rete **a parte** (20:54–21:07 UTC, sul codice del commit): **37 passati, 5 saltati** per servizio giù (404 del CDS con la sonda), **9 falliti solo per connessione** (MocServer, TAPVizieR, XMatch del CDS), **1 fallito** (`test_adql_examples[gaia_circle]`): l'archivio Gaia interrompe la query d'esempio al suo limite di 60 s («Maximum execution time (60 s) reached. Job aborted»), due volte; la stessa ADQL inviata direttamente all'archivio, senza AstroTwo, è interrotta anche lei (21:13–21:15 UTC) e la query è invariata dal build 6, quando il test passava → limite del servizio, non un errore di AstroTwo, scritto nelle note di rilascio. Prima: commit `8e08ddb` (build 6, sprint D9) | Claude Code |
| 6 | Costruzione dell'app | **Fatto** (sprint D10) | `uv run python scripts/build_app.py` dal commit `c43d622`, albero pulito (`BUILD_INFO.json`: 1.0.0, build 7, `dirty: false`, CPython 3.12.16, PySide6 6.11.3, PyInstaller 6.22.3, costruita alle 21:25:53 UTC); 1352 test passati nell'ambiente di build; V1–V9 ok; app 246,2 MB; prima vista 1,22 s a freddo, 1,19 s a caldo. Avviso atteso `BUILD_SOURCE_NOT_PUBLIC` (il tag `v1.0.0` non esiste ancora) | Claude Code |
| 7 | Firma Developer ID e notarizzazione | **Non per la 1.0** (A6-b, decisione del 2026-11-11: si salta) | Per una versione successiva: Su questo Mac `security find-identity -v -p codesigning` dà **0 identità valide** (2026-11-11); `notarytool` c'è (Command Line Tools). Mancano i passi una tantum del `60` §3.12: iscrizione all'**Apple Developer Program**, certificato «Developer ID Application», password specifica per l'app, `xcrun notarytool store-credentials astrotwo-notary`. `sign_notarize.py` resta com'è | **Guido** (account Apple, certificato, credenziali), quando vuole; poi Claude Code |
| 8 | `.dmg` (senza Developer ID) — **strada della 1.0** (A6-b) | **Fatto: `.dmg` candidato build 7** (sprint D10) | `uv run python scripts/make_dmg.py` (prova a secco) poi `--execute`. **`dist/AstroTwo-1.0.0.dmg`**, 121 491 995 byte (115,9 MiB); **`dist/AstroTwo-1.0.0.dmg.sha256`**; SHA-256 `89daad42cd2813b6e45f6ea625b8dd5efa83bc76d60987c0cee67aee0756174f`. Controlli: `shasum -a 256 -c` → OK; volume (montato in sola lettura) con solo `AstroTwo.app` e `Applications` → `/Applications`; `codesign --verify --deep --strict` valido, firma ad hoc (`TeamIdentifier` non impostato); `Info.plist`: AstroTwo, 1.0.0, build 7; nessun volume rimasto montato. Il candidato build 6 (`1bf583b2…a097a`) è in `dist/scartati/AstroTwo-1.0.0-build6.dmg` con il suo `.sha256` (che cita ancora il nome vecchio: `shasum -c` va fatto con quel nome) | Claude Code |
| 9 | Megatest `62` sull'app installata dal `.dmg` candidato | **No — tocca a Guido** | `.dmg` candidato pronto (passo 8). Mancano: `62` approvato (P4); sul Mac della prova **TOPCAT**, **Ollama** o **LM Studio** con un modello, una **chiave API** cloud, un FITS con WCS e un VOTable/CSV (`62` §3.1); per A4 il `.dmg` va **scaricato** (quarantena), possibilmente su un Mac con macOS 15. Le prove che dipendono dal CDS (profili, D1–D3, X3) risultano «non fatte» se il CDS è ancora giù. Esito in `docs/megatest-runs/1.0.0.md` (D63-1). **Un KO bloccante → nuovo candidato dal passo 3 con build 7** (`63` §3.1; il `.dmg` 1.0.0 non si sovrascrive: `DMG_EXISTS`) | **Guido** (prova); Claude Code (file dell'esito, commit di sola documentazione) |

### 3.4 Dopo il passo 9 (solo per sapere cosa prepara Guido)

Non richiesti in dettaglio, elencati perché si preparano prima: **Zenodo**
collegato a GitHub prima della release (passo 11, Guido: attivare
`guidogg13/AstroTwo`, verificare la licenza `GPL-3.0-or-later`); **ORCID**,
se c'è (passo 15, Guido); **sito** `astrotwo.pages.dev` (risponde HTTP 200
il 2026-11-11) con pagina di download, impronta, istruzioni e il pulsante
**«Sostieni AstroTwo»** solo sul sito (passo 16, Guido: account **Ko-fi** o
equivalente; nel repository nessun riferimento a Ko-fi, com'è giusto).

### 3.5 Numero di test dei commit dello sprint D5 (verificato il 2026-11-11)

I messaggi dei commit non riportano il numero di test. Verificato
riportando ogni commit in una copia separata (`git worktree`) ed eseguendo
lì `python -m pytest -q` con l'ambiente del progetto (test di default, senza
`network`, `keychain`, `perf`, `gl`):

| Commit | Sprint | Test raccolti (default) | Esito della suite di default |
|---|---|---|---|
| `155a710` | D5a | 1285 (68 esclusi dai marcatori) | 1285 passati, 0 falliti (9 min 15 s) |
| `5a4baab` | D5b | 1304 (68 esclusi) | 1304 passati, 0 falliti (9 min 13 s) |
| `cf82c35` | D5c | 1316 (68 esclusi) | 1316 passati, 0 falliti (9 min 15 s) |
| `ba86ab8` | D6 (per confronto) | 1322 (68 esclusi) | 1322 passati (commit dello sprint D7, che non ha toccato i test) |

**Da 1316 a 1322 (verificato nello sprint D8).** Confronto degli identificativi dei test raccolti a `cf82c35` e a `ba86ab8`: **6 test in più, nessuno tolto**, nessuno spostato tra quelli esclusi (68 in entrambi; 1384 e 1390 raccolti in tutto). I 6 sono `test_make_dmg.py::test_staged_folder_holds_only_the_app_and_the_applications_link`, `test_zenodo_json.py::test_doi_rule_d63_2` e `test_zenodo_json.py::test_doi_rule_rejects_wrong_forms` con 4 casi. Il numero «11 test nuovi» del report del D6 non è scritto in nessun file del repository e non corrisponde ai test raccolti: era un conteggio sbagliato del report (funzioni nuove più casi, o righe del diff: non ricostruibile).

### 3.6 Come si distingue il 404 del CDS da un indirizzo sbagliato nostro (sprint D8)

Un 404 da solo non lo dice: un servizio giù e un percorso scritto male danno la
stessa risposta. Per questo `tests/conftest.py` usa una **sonda**: per ogni
servizio del CDS un indirizzo valido e noto (`CDS_PROBES`: TAP di SIMBAD, TAP
di TAPVizieR, pagina di VizieR di II/246, MocServer). Se il test riceve un 404
da quell'host **e** la sonda fallisce anche lei (404, 429, 5xx, connessione,
timeout), il servizio è giù e il test è saltato con il motivo; se la sonda
risponde, il 404 è nostro e il test fallisce. Limiti: un host del CDS senza
sonda (per esempio `cdsxmatch.cds.unistra.fr`) non si può distinguere e fallisce;
se il servizio è giù **e** il nostro indirizzo è sbagliato, il secondo errore
si vede solo quando il servizio torna. Regola in `02` §8 punto 8; test senza
rete in `tests/test_network_retries.py` e `tests/test_commit_checked.py`.

### 3.7 Documenti della 1.0 scritti nello sprint D8

- `docs/installation.md` (inglese): la 1.0 non è firmata da Apple e perché;
  passi di «Open Anyway» per macOS 15 e successivi, dopo il controllo
  SHA-256. **Da verificare:** i passi vengono dalla guida di Apple per macOS
  Sequoia 15 (support.apple.com, «Open a Mac app from an unknown developer»,
  letta il 2026-11-11), non provati su un Mac con macOS 15 (questo Mac ha
  macOS 27): il testo esatto dell'avviso si controlla nella prova A4 del
  megatest.
- `dist/release-notes-1.0.0.md` (inglese, **bozza**, fuori dal repository
  fino all'approvazione, `63` passo 13): app non firmata con il rimando a
  `docs/installation.md`; «Known limitations» con AP1, D41-7 (46,0 ms contro
  16,7 ms) e D41-8 (4,46 s contro 3 s); stato della validazione.

## 4. Cosa NON fa

- Non chiude decisioni (`decisioni-aperte.md` §0 dà solo i consigli).
- Non costruisce l'app né il `.dmg` e non cambia la versione.
- Non copre i passi 10–17 della `63` oltre all'elenco di §3.4.

## 5. Livello e dipendenze

- **Livello:** non applicabile (rapporto, non un modulo dell'app).
- **Dipende da:** `63` (passi), `62` (megatest), `60` §3.12 (firma),
  `decisioni-aperte.md` §0, `docs/validation.md` §5.0.
- **Usato da:** il proprietario, per decidere il via al `.dmg` candidato.

## 6. Input e output

Non applicabile: testo di stato, senza dati in ingresso o in uscita.

## 7. Interfaccia pubblica

Non applicabile: nessun codice.

## 8. Librerie e standard di riferimento

Non applicabile: nessun codice; gli strumenti citati sono quelli della `63` §8.

## 9. Regole e vincoli

- Ogni stato scritto qui è stato **controllato il 2026-11-11** (comandi in
  §3); ciò che non è stato controllato è scritto «da verificare».
- Il rapporto non sostituisce la `63`: in caso di differenza vale la `63`.

## 10. Casi limite ed errori

Non applicabile: nessun codice.

## 11. Esposizione all'IA

Non applicabile: documento di progetto.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Copertura | rileggere §3.3 | una riga per ognuno dei passi 1–9 della `63`, con pronto / cosa manca / chi | lettura |

## 13. Decisioni aperte

Nessuna nuova. Le decisioni che riguardano la 1.0 sono in
`decisioni-aperte.md` §0 (`D14-15`, `D42-1`, `A6-b`); il rilascio senza la
validazione completa resta una scelta del proprietario (§3.1).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-11-11 | Claude Code | Creazione del file (stato: bozza), sprint D7: passi 1–9 della `63` con stato, cosa manca e chi; prerequisiti P1–P5; numero di test dei commit del D5. |
| 2026-11-11 | Claude Code | **Sprint D8:** P2 e P3 fatti; passo 2 pronto; passo 5 pronto (esiti dei test di rete prima e dopo la regola del 404 del CDS); passi 7 (non per la 1.0) e 8 (strada della 1.0, firma ad hoc controllata); P1 con i controlli delle 14:21–14:37 UTC; §3.5 con la spiegazione di 1316 → 1322; nuove §3.6 (sonda del CDS) e §3.7 (documenti della 1.0). |
| 2026-11-11 | Claude Code | **Sprint D9 (via del proprietario al candidato):** passi 1–6 e 8 fatti (commit della versione `8e08ddb`, build 6, `.dmg` candidato `dist/AstroTwo-1.0.0.dmg` con impronta e controlli), passo 7 saltato (A6-b), P5 dato, P1 in parte (terza misura, `D05-6`); passo 9 al proprietario. |
| 2026-11-11 | Claude Code | **Sprint D10 (decisioni del proprietario del 2026-11-11: D05-6 (a), build 6 scartato, nuovo candidato build 7):** passi 1, 3–6 e 8 rifatti (D10a `fe542ff`, commit della versione `c43d622`, build 7, `.dmg` `89daad42…174f`), passo 7 saltato (A6-b); P1 con la quarta misura (379 pass, 0 fail, 48 non misurati); passo 9 al proprietario sul nuovo candidato. |
