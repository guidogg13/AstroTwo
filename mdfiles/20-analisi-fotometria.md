# 20-analisi-fotometria.md — Fotometria (parte SED)

**Stato:** approvato (solo la parte SED; il resto del modulo è da specificare, D20-8)

> **Ambito di questa versione (2026-11-07, sprint C1):** il file specifica
> **solo la parte SED** (punti fotometrici da cataloghi, conversione
> magnitudine → flusso con punti zero documentati, grafico), che serve al
> profilo di un oggetto (`25`) e al puntatore fotometrico VizieR (H17,
> decisione del proprietario del 2026-10-08: la SED si costruisce nel 20). La
> fotometria d'apertura e PSF sulle immagini (F4 di `03-parita-aladin.md`),
> la calibrazione e l'estrazione di sorgenti (D12) **non sono ancora
> specificate**: saranno aggiunte a questo file in uno sprint successivo, prima
> della sua approvazione completa (D20-8).

## 2. Scopo

Raccogliere le misure fotometriche di un oggetto da più cataloghi in una SED
in cui ogni punto ha catalogo, banda, sistema, valore, errore e qualità, e
convertirle in flusso solo con punti zero ufficiali citati.

## 3. Cosa fa

### 3.1 Punti della SED

Un **punto** (`SedPoint`) è una misura di una banda per un oggetto:
catalogo/servizio, tabella, identificativo della sorgente e tipo di incrocio
(dal `25`), banda, sistema (`Vega`, `AB`, o «non dichiarato»), valore in
magnitudini o in flusso come fornito, errore, qualità del catalogo (es.
`ph_qual` di 2MASS e AllWISE), epoca della misura se nota, riferimento
bibliografico. Fonti della 1.0:

| Fonte | Bande | Valori letti | Qualità |
|---|---|---|---|
| Gaia DR3 (`gaiadr3.gaia_source`) | G, BP, RP | `phot_*_mean_mag` e `phot_*_mean_flux` (e⁻/s) con `phot_*_mean_flux_error` | `phot_variable_flag`, `phot_bp_rp_excess_factor` |
| 2MASS PSC (IRSA `fp_psc`) | J, H, Ks | `j_m`, `h_m`, `k_m` con `*_msigcom` | `ph_qual`, `rd_flg`, `cc_flg` |
| AllWISE (IRSA `allwise_p3as_psd`) | W1–W4 | `w*mpro` con `w*sigmpro` | `ph_qual` (`U` = limite superiore), `cc_flags`, `ext_flg` |
| SIMBAD (tabella `flux`) | quelle presenti (`U`, `B`, `V`, `R`, `I`, `G`, `J`, `H`, `K`, …) | `flux` (magnitudine), `flux_err`, `system` (`V`/`A`) | `qual`, `bibcode` |
| SED di VizieR (`vizier_photometry` del 14) | quelle dei cataloghi VizieR | flusso in Jy e frequenza **già convertiti da VizieR** | catalogo d'origine (`_tabname`) |

### 3.2 Conversione magnitudine → flusso (solo con punti zero documentati)

Una magnitudine diventa flusso **solo** se la sua banda è nella tabella dei
punti zero sotto, con fonte ufficiale; altrimenti il punto resta in
magnitudini, è mostrato nella tabella e **non entra nel grafico in flusso**
(regola del proprietario del 2026-11-07). Tabella verificata il 2026-11-07
sulle fonti ufficiali (proposta D20-1):

| Banda | Punto zero | λ di riferimento | Fonte ufficiale |
|---|---|---|---|
| Gaia G | ZP_AB = 25,8010446445 ± 0,0027590522 mag (ZP_Vega = 25,6873668671 ± 0,0027553202) | dalla documentazione ufficiale Gaia (D20-2 decisa; valori da trovare e citare nello sprint C3) | file `zeropt.dat` di «Gaia (E)DR3 passbands and zero points» (ESA, `cosmos.esa.int/web/gaia/edr3-passbands`, versione 2), Riello et al. 2021, A&A 649, A3 |
| Gaia BP | ZP_AB = 25,3539555559 ± 0,0023065687 (ZP_Vega = 25,3385422158 ± 0,0027901700) | D20-2 | idem |
| Gaia RP | ZP_AB = 25,1039837393 ± 0,0015800349 (ZP_Vega = 24,7478955012 ± 0,0037793818) | D20-2 | idem |
| 2MASS J | Fν(0 mag) = 1594 ± 27,8 Jy | λ_iso = 1,235 ± 0,006 µm | 2MASS All-Sky Explanatory Supplement §VI.4a, Tabella 1 (Cohen, Wheaton & Megeath 2003, AJ 126, 1090) |
| 2MASS H | 1024 ± 20,0 Jy | 1,662 ± 0,009 µm | idem |
| 2MASS Ks | 666,7 ± 12,6 Jy | 2,159 ± 0,011 µm | idem |
| WISE W1 | Fν(0 mag) = 309,540 Jy | λ_iso = 3,35 µm | WISE All-Sky Explanatory Supplement §IV.4.h, Tabella 1 (colonna 2) e §IV.4.h.v (Wright et al. 2010; Jarrett et al. 2011, ApJ 735, 112) |
| WISE W2 | 171,787 Jy | 4,60 µm | idem |
| WISE W3 | 31,674 Jy | 11,56 µm | idem |
| WISE W4 | 8,363 Jy | 22,08 µm | idem |

Note della verifica: la tabella WISE è un'immagine nella pagina del
supplemento (letta il 2026-11-07) e **non dà l'incertezza** dei punti zero
(da verificare in Jarrett et al. 2011); la pagina è quella dell'All-Sky
Release: **che valga senza cambi per AllWISE è da verificare** sul supplemento
AllWISE (la pagina ha rediretto e non è stata letta). Nessuna correzione di
colore WISE (Tabella 2 del supplemento) nella 1.0.

**Formule (deterministiche, da testare):**
- 2MASS e WISE (sistema Vega): Fν = Fν(0) · 10^(−0,4 m);
- Gaia: m_AB = −2,5 log₁₀(F_e) + ZP_AB, con F_e = `phot_*_mean_flux` in e⁻/s;
  Fν = 3631 Jy · 10^(−0,4 m_AB) (definizione del sistema AB, Oke & Gunn 1983,
  ApJ 266, 713);
- errore: σ_F = F · 0,4 ln 10 · √(σ_m² + σ_ZP²) per Gaia, e
  √((0,4 ln 10 · σ_m)² + (σ_F0/F0)²) · F per 2MASS/WISE (proposta D20-3).

I punti della **SED di VizieR** sono già in flusso: si mostrano **così come
li dà VizieR** (conversione di VizieR, non nostra), in una serie separata
con il catalogo d'origine, **senza fonderli** con i nostri (D20-5).

### 3.3 Qualità, limiti e duplicati

- 2MASS `ph_qual` `D`, `E`, `F`, `X` e AllWISE `ph_qual` diverso da `A`/`B`/`C`:
  punto nella tabella, **fuori dal grafico** di default, con il motivo
  (proposta D20-4); AllWISE `U` = **limite superiore** (freccia, se mostrato).
  Esempi del 2026-11-07: Vega 2MASS `CBC` con J = −0,177 (saturata), Alcyone
  `DCD`, AllWISE di Vega `UUAA`.
- **Duplicati:** un valore SIMBAD con lo stesso riferimento di un catalogo
  interrogato direttamente (es. 51 Peg: SIMBAD `G` = 5,283212 da
  2020yCat.1350, `J/H/K` da 2003yCat.2246, cioè Gaia e 2MASS) è marcato
  «duplicato di» e non entra due volte nel grafico (D20-6).
- Le magnitudini SIMBAD di bande senza punto zero in tabella (es. Johnson
  U, B, V, R, I) restano in magnitudini (D20-6).

### 3.4 Grafico

λ (µm) in ascissa, Fν (Jy) in ordinata, scale logaritmiche; barre d'errore;
colori per catalogo; serie VizieR distinta; limiti superiori come frecce;
tooltip con la provenienza del punto. Alternativa λFλ come opzione (D20-7).

## 4. Cosa NON fa

- Non converte bande senza punto zero ufficiale in tabella.
- Non ricalcola né corregge i flussi della SED di VizieR.
- Non applica estinzione, correzioni di colore, modelli o fit (eccesso
  infrarosso: estensione, `25` §3.8).
- Non sceglie la sorgente: riceve dal `25` (o dal puntatore) le sorgenti già
  identificate con il tipo di incrocio.
- In questa versione: niente fotometria d'apertura/PSF, calibrazione,
  estrazione di sorgenti (D20-8).

## 5. Livello e dipendenze

- **Livello:** 2 (analisi).
- **Dipende da:** `02` (unità, DC6), `13` (tabelle), `14` (`tap_query`,
  `vizier_photometry`, `simbad_object` proposta nel `25`), `04` (cache).
- **Usato da:** `25` (profilo), `41`/`43` (puntatore fotometrico VizieR,
  grafico), `32` tramite il `25`.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | righe di catalogo identificate | tabelle Astropy con provenienza | colonne del catalogo, unità dichiarate | dal `25` |
| in | punti VizieR | tabella del 14 | Jy, GHz | serie separata |
| out | `Sed` | elenco di `SedPoint` + serie VizieR | magnitudini e, se convertibili, Fν in Jy con λ in µm | `float64` |
| out | grafico | figura matplotlib | PNG con crediti | per il 25 e il 43 |
| out | tabella | ECSV / VOTable | una riga per punto con provenienza | anche come livello catalogo |

## 7. Interfaccia pubblica

- **`ZERO_POINTS`** — tabella di §3.2 (banda → sistema, punto zero, errore,
  λ di riferimento, fonte, data di verifica), unica fonte delle conversioni.
- **`sed_points_from(table, catalog, *, provenance)`** — punti di una tabella
  nota (Gaia DR3, 2MASS, AllWISE, flux di SIMBAD).
- **`mag_to_flux(point)`** — Fν ed errore con il punto zero e la formula
  usati, oppure il motivo per cui non si converte (`SED_NO_ZERO_POINT`).
- **`build_sed(points, vizier=None)`** — `Sed` con duplicati e qualità marcati.
- **`plot_sed(sed, ...)`** e **`sed_table(sed)`**.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| Astropy `units` | Jy, µm, magnitudini, `spectral()` | regola d'oro n. 4 |
| matplotlib (già dipendenza) | grafico | proposta D20-7 |
| Fonti ufficiali dei punti zero | §3.2 | regola del proprietario del 2026-11-07 |

## 9. Regole e vincoli

- Nessun flusso senza punto zero ufficiale citato; ogni conversione porta
  formula, punto zero, errore e fonte.
- Calcoli in `float64`, unità con Astropy (DC6).
- Le costanti di §3.2 si cambiano solo aggiornando prima questo file.
- Nessun numero dall'IA (regola d'oro n. 1).

## 10. Casi limite ed errori

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Banda senza punto zero | resta in magnitudini, fuori dal grafico | `SED_NO_ZERO_POINT` |
| Magnitudine senza errore (es. SIMBAD B, U di 51 Peg) | punto senza barra, marcato | `SED_NO_ERROR` |
| Qualità bassa o saturazione | in tabella, fuori dal grafico di default | `SED_LOW_QUALITY` |
| Limite superiore (AllWISE `U`) | freccia o fuori dal grafico | `SED_UPPER_LIMIT` |
| Duplicato SIMBAD | marcato, una sola volta nel grafico | `SED_DUPLICATE` |
| Sistema non dichiarato | resta in magnitudini | `SED_NO_SYSTEM` |
| CDS giù | nessuna serie VizieR | dal 14 (`vizier_no_mirror`) |

## 11. Esposizione all'IA

Non direttamente: la SED arriva all'IA dentro il risultato di
`object__profile` del `25` (punti con banda, valore, errore, fonte). L'IA non
converte né calcola flussi.

## 12. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | 2MASS → flusso | J = 4,655 ± 0,296 (51 Peg, 2026-11-07) | Fν = 1594 Jy · 10^(−0,4 · 4,655), errore con la formula di §3.2 | ricalcolo con Astropy |
| T2 | WISE → flusso | W3 = 3,929 ± 0,016 (51 Peg) | Fν = 31,674 Jy · 10^(−0,4 · 3,929) | ricalcolo |
| T3 | Gaia → flusso | `phot_g_mean_flux` registrato | m_AB e Fν con ZP_AB di G | ricalcolo |
| T4 | Banda senza punto zero | SIMBAD `V` | `SED_NO_ZERO_POINT`, punto in magnitudini | |
| T5 | Qualità | 2MASS di Vega `CBC`, Alcyone `DCD` | punti `D` fuori dal grafico con motivo | |
| T6 | Limite superiore | AllWISE TRAPPIST-1 W4 `U` (8,565, senza errore) | `SED_UPPER_LIMIT` | |
| T7 | Duplicati | flux SIMBAD di 51 Peg + Gaia + 2MASS | G, J, H, K di SIMBAD marcati duplicati | |
| T8 | Serie VizieR | risposta registrata del servizio SED (quando il CDS risponde) | punti non convertiti né fusi, catalogo d'origine | |
| T9 | Tabella dei punti zero | `ZERO_POINTS` | ogni voce con fonte e data | ispezione |

## 13. Decisioni aperte

Decisioni D20-1…D20-8 **prese dal proprietario il 2026-11-07** (dopo il
report dello sprint C1); restano qui come registro. Il codice della parte SED
è dello sprint C3.

- **D20-1 — Tabella dei punti zero — DECISA (2026-11-07):** come §3.2 (Gaia AB
  tramite il flusso in e⁻/s, 2MASS di Cohen et al. 2003, WISE a spettro
  costante senza correzioni di colore). Le note «da verificare» di §3.2
  (incertezza WISE, validità per AllWISE) si chiudono prima del codice (C3).
- **D20-2 — λ di riferimento delle bande Gaia — DECISA (2026-11-07):** valori
  **pubblicati nella documentazione ufficiale di Gaia**, citati; il calcolo
  dalla banda passante (`passband.dat`) solo se mancano **e** la licenza dei
  dati lo permette, dichiarandolo nel risultato. Ricerca dei valori: sprint C3.
- **D20-3 — Propagazione degli errori — DECISA (2026-11-07):** con l'errore
  del punto zero, come §3.2.
- **D20-4 — Soglie di qualità — DECISA (2026-11-07):** come §3.3.
- **D20-5 — Serie VizieR — DECISA (2026-11-07):** separata e non convertita,
  raggio 2″ dalla posizione propagata, avviso di moto proprio elevato.
- **D20-6 — Magnitudini di SIMBAD — DECISA (2026-11-07):** solo in tabella,
  duplicati marcati; Johnson senza conversione nella 1.0.
- **D20-7 — Grafico — DECISA (2026-11-07):** matplotlib incorporato in Qt, Fν
  contro λ log-log, λFλ in opzione.
- **D20-8 — Resto del modulo — DECISA (2026-11-07):** si approva ora la sola
  parte SED; fotometria d'apertura e PSF, calibrazione ed estrazione si
  specificano in questo file in uno sprint successivo, prima della loro fase
  codice.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-11-07 | Claude Code | **Decisioni del proprietario del 2026-11-07 (sprint C2):** file `approvato` per la sola parte SED (formula di D25-12 del `25`); D20-1…D20-8 scritte come decise (D20-2: λ di Gaia dalla documentazione ufficiale, calcolo dalla banda passante solo se mancano e la licenza lo permette, dichiarato). Nessun codice in C2 (SED nello sprint C3). |
| 2026-11-07 | Claude Code | Creazione del file (stato: bozza), sprint C1: solo parte SED; punti zero di Gaia (E)DR3, 2MASS e WISE letti sulle fonti ufficiali il 2026-11-07; decisioni aperte D20-1…D20-8. |
