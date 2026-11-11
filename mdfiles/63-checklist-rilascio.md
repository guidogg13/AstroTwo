# 63-checklist-rilascio.md — Checklist di ogni rilascio di AstroTwo

**Stato:** approvato

> Creato il 2026-11-10 (sprint D5c) su decisione del proprietario: «Il rilascio
> della 1.0 segue una checklist scritta in `mdfiles/`, uguale per ogni rilascio
> futuro». Non è un modulo di codice: le sezioni che parlano di codice dicono
> «non applicabile» con il motivo. Gli esempi usano la versione **1.0.0**; per
> un altro rilascio si sostituisce il numero.

## 2. Scopo

Un elenco unico, nell'ordine in cui si fanno, di tutti i passi di un rilascio:
per ognuno **chi lo fa** (il proprietario o Claude Code) e **il comando**. Serve
a non dimenticare niente e a rendere ogni rilascio uguale al precedente.

## 3. Cosa fa

### 3.1 Regole

- I passi si fanno **nell'ordine**; un passo fallito ferma il rilascio finché
  non è risolto (e, se tocca il codice, si riparte dal passo 3).
- **Chi:** «Proprietario» = Guido Ratti, a mano, nel proprio Terminale o nel
  browser (mai una password scritta in una sessione dell'assistente: finirebbe
  nella conversazione); «Claude Code» = l'assistente, nella sessione di
  sviluppo. I passi verso l'esterno (push, tag pubblicato, release, sito) li
  esegue Claude Code **solo dopo il via del proprietario** dato per quel
  rilascio.
- Ogni passo fatto si spunta in una copia di questa tabella, con la data, nelle
  note di rilascio (passo 13).
- **Ordine del megatest:** il megatest (`62`) si fa sull'app costruita dal
  `.dmg` **candidato** (decisione D62-1 (2)), quindi viene **dopo** la
  costruzione e la firma del `.dmg` e **prima** del tag e della release: un
  `.dmg` candidato diventa il `.dmg` del rilascio solo con il megatest
  superato. Un KO bloccante → correzione → nuovo candidato (dal passo 3, con il
  numero di build aumentato) → megatest di nuovo.

### 3.2 Passi

| # | Passo | Chi | Comando o azione |
|---|---|---|---|
| 1 | **Stato pulito** sul ramo `main`, ultimo commit atteso, nessuna modifica in sospeso | Claude Code | `git status --short` (vuoto); `git log -1 --oneline` |
| 2 | **Testi coerenti con il posizionamento** (AstroTwo complementare ad Aladin, TOPCAT e DS9, mai sostituto: `panoramica.md` §2 «Fase D») in `README.md`, `docs/`, `CITATION.cff`, `.zenodo.json`, descrizione in `pyproject.toml`, testi dell'app (About) | Claude Code | `grep -rn -i "successor\|successore\|replace\|sostitu" README.md docs CITATION.cff .zenodo.json pyproject.toml src/astrotwo/ui` e correzione di ogni riga trovata |
| 3 | **Versione 1.0.0** in tutti i punti: `pyproject.toml` (`version = "1.0.0"`, forma PEP 440), `src/astrotwo/__init__.py` (`__version__ = "1.0.0"`, forma SemVer, DC4), `[tool.astrotwo.bundle] build` +1 (`60` §3.2), `CITATION.cff` (`version: "1.0.0"`, `date-released:` = **data del commit della versione del passo 5**, ISO 8601, cioè il giorno in cui si fa quel commit; se il tag del passo 10 arriva in un altro giorno, si corregge al passo 14) | Claude Code | modifica dei quattro file; controllo: `uv run python -m pytest -q tests/test_citation_cff.py tests/test_zenodo_json.py` |
| 4 | **`uv lock` prima di `git add`** (il lockfile contiene la versione del progetto) | Claude Code | `uv lock` poi `git add pyproject.toml uv.lock src/astrotwo/__init__.py CITATION.cff` |
| 5 | **Suite completa** (test di default, ruff, poi i test di rete) e commit della versione | Claude Code | `uv run ruff check .`; `uv run python scripts/commit_checked.py -m "Release 1.0.0: versione"` (senza `--no-network`: esegue anche i test di rete; un test di rete fallito o saltato per un servizio giù si scrive nelle note di rilascio, non si nasconde). **Servizio giù** (decisione del proprietario del 2026-11-11, come D14-16): connessione, timeout, HTTP 429/502/503/504 e **HTTP 404 di un servizio esterno**, ma il 404 solo se una sonda indipendente sullo stesso servizio fallisce anche lei; allora il test è **saltato** con il motivo «servizio giù: HTTP 404 (<host>)» (`tests/conftest.py`, `02` §8). Un 404 con la sonda che risponde resta un errore vero e ferma il commit |
| 6 | **Costruzione dell'app** | Claude Code | `uv run python scripts/build_app.py` (controlli di `60` §3.8; nome «AstroTwo» nell'`Info.plist`) |
| 7 | **Firma Developer ID e notarizzazione** — **non per la 1.0** (A6-b, decisione del proprietario del 2026-11-11: la 1.0 esce senza; si salta e si fa il passo 8). Dalla prima versione firmata: solo con l'account Apple Developer pronto — passi una tantum del proprietario in `60` §3.12 | Claude Code (credenziali già nel Portachiavi del proprietario) | prova a secco: `uv run python scripts/make_dmg.py --signed`; poi `uv run python scripts/make_dmg.py --signed --execute` (firma dell'app, `.dmg`, firma e notarizzazione del `.dmg`, impronta) |
| 8 | **`.dmg`** senza firma Developer ID — **la strada della 1.0** (A6-b, 2026-11-11): app con la firma ad hoc di `build_app.py` (controllo V1 del `60` §3.8), «Apri comunque» in `docs/installation.md` e nelle note di rilascio | Claude Code | `uv run python scripts/make_dmg.py` (prova a secco), poi `uv run python scripts/make_dmg.py --execute` → `dist/AstroTwo-1.0.0.dmg` e `dist/AstroTwo-1.0.0.dmg.sha256` |
| 9 | **Megatest `62` superato** sull'app installata dal `.dmg` del passo 7 o 8 (zero KO, o KO dichiarati non bloccanti dal proprietario) | Proprietario | §3 del `62`; esito con data, versione (About) e macOS in `docs/megatest-runs/1.0.0.md` (D63-1, approvata il 2026-11-11: copia del `62` con OK / KO / non fatta per ogni prova), messo nel repository da Claude Code con un commit di sola documentazione |
| 10 | **Tag** annotato della versione, sul commit del passo 5 (nessun commit di codice dopo) | Claude Code, dopo il via del proprietario | `git tag -a v1.0.0 -m "AstroTwo 1.0.0"`; `git push origin main`; `git push origin v1.0.0` |
| 11 | **Zenodo collegato a GitHub prima della release** (Zenodo archivia solo le release create **dopo** l'attivazione del repository) | Proprietario | zenodo.org → GitHub → attivare `guidogg13/AstroTwo` (una volta sola, al primo rilascio); il codice di licenza `GPL-3.0-or-later` di `.zenodo.json` da verificare lì (D4c) |
| 12 | **Release su GitHub** con il `.dmg`, la sua impronta e le note di rilascio | Claude Code, dopo il via del proprietario | `gh release create v1.0.0 dist/AstroTwo-1.0.0.dmg dist/AstroTwo-1.0.0.dmg.sha256 --title "AstroTwo 1.0.0" --notes-file dist/release-notes-1.0.0.md` |
| 13 | **Note di rilascio** (testo del passo 12): novità, KO non bloccanti del megatest, servizi giù durante i test di rete, firma (Developer ID o ad hoc con «Apri comunque»), impronta SHA-256, link a `docs/validation.md`, a `docs/installation.md` e all'esito del megatest `docs/megatest-runs/1.0.0.md` (D63-1) | Claude Code scrive, proprietario approva | `dist/release-notes-1.0.0.md` (fuori dal repository fino all'approvazione) |
| 14 | **DOI di Zenodo** nei file del progetto, quando Zenodo ha archiviato la release (DOI della versione e DOI «concept» di tutte le versioni) | Proprietario legge i DOI su Zenodo; Claude Code scrive | `CITATION.cff`: `doi:` = DOI della versione (tolto il commento); `README.md`: DOI «concept» nella sezione della citazione; `.zenodo.json`: DOI «concept» in `related_identifiers` con `"relation": "isVersionOf"` e `"scheme": "doi"`, **mai** la chiave `doi` (D63-2; controllo: `uv run python -m pytest -q tests/test_zenodo_json.py`); **`date-released`** in `CITATION.cff` portato alla data del tag del passo 10, solo se il tag è arrivato in un giorno diverso dal commit del passo 5; poi `uv run python scripts/commit_checked.py --no-network -m "DOI di Zenodo per 1.0.0"` e `git push origin main` (dopo il via) |
| 15 | **ORCID** in `CITATION.cff` e `.zenodo.json`, se il proprietario ne ha uno | Proprietario dà l'ORCID; Claude Code scrive | come il passo 14 (stesso commit) |
| 16 | **Sito del progetto** (`astrotwo.pages.dev`): pagina di download con il `.dmg` della release e la sua impronta SHA-256, istruzioni d'installazione (con «Apri comunque» se il `.dmg` non è notarizzato), link a validazione, documentazione e citazione (DOI), e il pulsante **«Sostieni AstroTwo»** (solo sul sito, mai nell'app: decisione del proprietario del 2026-11-10) | Proprietario (il sito non è in questo repository) | pubblicazione del sito; controllo dei link e del download da un altro Mac |
| 17 | **Dopo il rilascio:** file di stato aggiornati (`panoramica.md`, `INDICE.md`, `riassunto.md`), copia spuntata di questa tabella nelle note di rilascio | Claude Code | commit con `scripts/commit_checked.py --no-network` |

**Data di `date-released` (decisione del proprietario del 2026-11-11).** Nel
commit della versione (passo 5) `date-released` è la data di quel commit. Il
tag (passo 10) va sullo stesso commit, quindi di solito la data coincide. Se il
tag arriva in un giorno diverso, la data in `CITATION.cff` si corregge nel
commit del passo 14, che tocca **solo metadati** (la regola del §9 resta:
nessun commit di codice dopo il passo 5).

## 4. Cosa NON fa

- Non sostituisce il megatest (`62`), la pagina di validazione
  (`docs/validation.md`) né le specifiche di costruzione e firma (`60`).
- Non scrive il sito (non è in questo repository).
- Non contiene credenziali: account Apple, password specifica e profilo di
  `notarytool` restano nel Portachiavi del proprietario (`60` §3.12).

## 5. Livello e dipendenze

- **Livello:** non applicabile (procedura di rilascio, non un modulo dell'app).
- **Dipende da:** `60` (app, `.dmg`, firma e notarizzazione), `62` (megatest),
  `CITATION.cff`, `.zenodo.json`, `docs/validation.md`.
- **Usato da:** ogni rilascio, a partire dalla 1.0.0.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | commit del rilascio | git | — | passo 5 |
| out | `AstroTwo-<versione>.dmg` e `.sha256` | file | — | passi 7–8, allegati alla release |
| out | tag `v<versione>`, release GitHub, archivio Zenodo con DOI | — | — | passi 10–14 |

## 7. Interfaccia pubblica

Non applicabile: procedura a mano, con i comandi degli script già specificati
nel `60` (`build_app.py`, `make_dmg.py`, `sign_notarize.py`) e nel `05`
(`commit_checked.py`).

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso | Motivazione |
|---|---|---|
| `uv` | `uv lock`, esecuzione degli script | gestore dei pacchetti del progetto (A4) |
| `hdiutil`, `codesign`, `notarytool` (macOS) | `.dmg`, firma, notarizzazione | strumenti di Apple, nessuna dipendenza nuova (`60`) |
| `gh` (GitHub CLI) | release | strumento ufficiale di GitHub |
| Zenodo (integrazione con GitHub) | archivio e DOI | archivio scientifico citabile (Fase D) |
| Citation File Format 1.2.0 | `CITATION.cff` | standard di citazione del software (D1b) |

## 9. Regole e vincoli

- Regola d'oro 5: nessuna credenziale in file, comandi o note di rilascio.
- Il tag e la release puntano al commit su cui è stato costruito il `.dmg`
  provato dal megatest: nessun commit di codice tra il passo 5 e il passo 10
  (i commit dei passi 14–17 toccano solo metadati e documentazione; anche
  l'esito del megatest del passo 9, `docs/megatest-runs/<versione>.md`, si
  aggiunge con un commit di sola documentazione).
- `date-released` in `CITATION.cff` è la data del commit della versione
  (passo 5); se il tag del passo 10 arriva in un giorno diverso, si corregge
  nel commit del passo 14 (solo metadati), mai con un commit di codice.
- In `.zenodo.json` mai la chiave `doi`; il DOI «concept», quando esiste, sta
  in `related_identifiers` con relazione `isVersionOf` (D63-2, controllato da
  `tests/test_zenodo_json.py`). Per la 1.0.0 il campo resta assente finché il
  DOI non esiste.
- Il `.dmg` non si sovrascrive mai (`make_dmg.py` rifiuta, `DMG_EXISTS`): un
  nuovo candidato ha un nuovo numero di build e si ricostruisce dal passo 3.

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Megatest con KO bloccante | correzione, nuovo candidato dal passo 3, megatest di nuovo | — |
| Account Apple Developer non pronto | passo 7 saltato, passo 8 senza firma Developer ID, «Apri comunque» nel sito e nelle note | — |
| Notarizzazione rifiutata | `dist/notary-log.json` (`60` §3.12); niente release finché non è risolta, oppure rilascio senza notarizzazione deciso dal proprietario | — |
| Zenodo non attivato prima della release | nessun DOI: si attiva e si crea una nuova release (o un archivio a mano su Zenodo, decisione del proprietario) | — |
| Servizio esterno giù durante i test di rete del passo 5 | scritto nelle note di rilascio; non blocca se il proprietario lo accetta | — |

## 11. Esposizione all'IA

Non applicabile: procedura di rilascio, non una funzione dell'app.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Checklist completa | rileggere §3.2 | ci sono tutti i passi chiesti dal proprietario il 2026-11-10 (versione e data, `uv lock` prima di `git add`, suite completa, megatest, build, firma e notarizzazione, `.dmg`, tag, release, DOI in `CITATION.cff`, `.zenodo.json` e README, sito con «Sostieni AstroTwo»), ciascuno con chi e comando | lettura |
| T2 | Comandi senza effetti in prova | `uv run python scripts/make_dmg.py` e `uv run python scripts/sign_notarize.py app` senza `--execute` | stampano i comandi, non eseguono niente | test `tests/test_make_dmg.py`, `tests/test_sign_notarize.py` |
| T3 | Regola del DOI in `.zenodo.json` (D63-2) | `uv run python -m pytest -q tests/test_zenodo_json.py` | fallisce se c'è la chiave `doi` o se un DOI in `related_identifiers` non ha relazione `isVersionOf` | test |

## 13. Decisioni aperte

Nessuna aperta. Decise:

- **D63-1 — Dove si conserva l'esito del megatest: APPROVATA dal proprietario
  il 2026-11-11** (proposta di Claude Code del 2026-11-10):
  `docs/megatest-runs/<versione>.md` (copia del `62` con OK / KO / non fatta
  per ogni prova, data, versione, macOS), nel repository, con il link nelle
  note di rilascio (passi 9 e 13).
- **D63-2 — DOI in `.zenodo.json`: APPROVATA dal proprietario il 2026-11-11**
  (raccomandazione di Claude Code del 2026-11-10): in `.zenodo.json` il DOI
  «concept» va in `related_identifiers` con relazione `isVersionOf`, **mai**
  la chiave `doi` (un campo `doi` farebbe usare a Zenodo quel DOI per il
  prossimo archivio). Il test `tests/test_zenodo_json.py` lo controlla (T3).
  Per la 1.0.0 il campo resta assente, finché il DOI non esiste (passo 14).

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-11-10 | Claude Code | Creazione del file (stato: bozza), sprint D5c, decisioni del proprietario del 2026-11-10 (checklist in `mdfiles/` uguale per ogni rilascio; pulsante «Sostieni AstroTwo» solo sul sito, passo 16; `.dmg` con `hdiutil`, passi 7–8). Megatest dopo il `.dmg` candidato (D62-1 (2)). Aperte D63-1, D63-2. |
| 2026-11-11 | Claude Code | **Sprint D6 (decisioni del proprietario del 2026-11-11):** **approvato dal proprietario** (stato `approvato`) con una correzione: `date-released` = data del commit della versione (passo 5), corretta nel commit del passo 14 (solo metadati) se il tag del passo 10 arriva in un giorno diverso (passi 3 e 14, nota in §3.2, §9). **D63-1 approvata** (passi 9 e 13, §9); **D63-2 approvata** (passo 14, §9, T3, `tests/test_zenodo_json.py`). §13 senza decisioni aperte. |
| 2026-11-11 | Claude Code | **Sprint D8 (decisioni del proprietario del 2026-11-11):** A6-b decisa: passo 7 «non per la 1.0», passo 8 strada della 1.0 (firma ad hoc, «Apri comunque»); passo 5 con la regola del 404 del CDS = servizio giù, controllato da una sonda, test saltato con il motivo. Bozza delle note di rilascio in `dist/release-notes-1.0.0.md` (passo 13, fuori dal repository fino all'approvazione). Modifica di un file approvato su decisione del proprietario. |
