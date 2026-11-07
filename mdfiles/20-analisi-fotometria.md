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
| Gaia G | ZP_AB = 25,8010446445 ± 0,0027590522 mag (ZP_Vega = 25,6873668671 ± 0,0027553202) | λ_p (pivot) = 621,79 nm | punti zero: file `zeropt.dat` di «Gaia (E)DR3 passbands and zero points» (ESA, `cosmos.esa.int/web/gaia/edr3-passbands`, versione 2), Riello et al. 2021, A&A 649, A3; λ_p: documentazione di Gaia DR3, §5.4.1, Tabella 5.4 (D20-2) |
| Gaia BP | ZP_AB = 25,3539555559 ± 0,0023065687 (ZP_Vega = 25,3385422158 ± 0,0027901700) | λ_p = 510,97 nm | idem |
| Gaia RP | ZP_AB = 25,1039837393 ± 0,0015800349 (ZP_Vega = 24,7478955012 ± 0,0037793818) | λ_p = 776,91 nm | idem |
| 2MASS J | Fν(0 mag) = 1594 ± 27,8 Jy | λ_iso = 1,235 ± 0,006 µm | 2MASS All-Sky Explanatory Supplement §VI.4a, Tabella 1 (Cohen, Wheaton & Megeath 2003, AJ 126, 1090) |
| 2MASS H | 1024 ± 20,0 Jy | 1,662 ± 0,009 µm | idem |
| 2MASS Ks | 666,7 ± 12,6 Jy | 2,159 ± 0,011 µm | idem |
| WISE W1 | Fν(0 mag) = 309,540 ± 4,582 Jy | λ_iso = 3,3526 ± 0,0132 µm | WISE All-Sky Explanatory Supplement §IV.4.h, Tabella 1 (colonna 2) e Tabella 9 «WISE Zero Magnitude Attributes (from Jarrett et al. 2011)», colonne Fν(iso) e λ(iso) con le incertezze (Wright et al. 2010; Jarrett et al. 2011, ApJ 735, 112) |
| WISE W2 | 171,787 ± 2,516 Jy | 4,6028 ± 0,0168 µm | idem |
| WISE W3 | 31,674 ± 0,450 Jy | 11,5608 ± 0,0446 µm | idem |
| WISE W4 | 8,363 ± 0,124 Jy | 22,0883 ± 0,1184 µm | idem |

Note della verifica (sprint C1, completata nello sprint C3 il 2026-11-07):
- **Gaia:** `zeropt.dat` scaricato dal pacchetto ufficiale ESA (versione 2) il
  2026-11-07: i sei valori sopra coincidono cifra per cifra. Il `ReadMe` non
  dà lunghezze d'onda; la documentazione ufficiale di Gaia DR3 (§5.4.1
  «Calibration», Tabella 5.4) dà per G, BP, RP la lunghezza d'onda media dei
  fotoni λ₀ (639,07; 518,26; 782,51) e la **lunghezza d'onda di pivot λ_p**
  (621,79; 510,97; 776,91), in nm (unità implicita nelle equazioni 5.48–5.50
  della stessa pagina, fattore 10⁻⁹). Si usa **λ_p**, la lunghezza d'onda per
  cui Fν e Fλ medi si corrispondono (D20-9 (1)); nessun calcolo dalla banda
  passante (D20-2). La Tabella 5.4 ripete i punti zero arrotondati a 4 cifre
  (es. ZP_AB(G) = 25,8010 ± 0,0028), coerenti con `zeropt.dat`.
- **2MASS:** Tabella 1 del supplemento §VI.4a riletta il 2026-11-07: valori
  invariati.
- **WISE:** la Tabella 1 del supplemento (immagine) dà Fν senza incertezze;
  la **Tabella 9** dello stesso §IV.4.h (immagine, «from Jarrett et al.
  2011», letta il 2026-11-07) dà Fν(iso) **con** le incertezze e λ(iso) con
  4 decimali e incertezza: valori sopra. Fν(iso) coincide con la Tabella 1.
- **AllWISE:** AllWISE Explanatory Supplement §V.3.e «Photometric
  Calibration» (letto il 2026-11-07): la calibrazione segue «the same basic
  procedure» dell'All-Sky Release, le magnitudini sono nel sistema Vega e «la
  conversione delle magnitudini AllWISE in densità di flusso […] è descritta in
  IV.4.h.i del supplemento All-Sky»: **la tabella vale per AllWISE**.
- Nessuna correzione di colore WISE (Tabella 2 del supplemento) nella 1.0.
- **Sistema AB:** Fν = 3631 Jy a m_AB = 0 (Oke & Gunn 1983).

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

- 2MASS `ph_qual` diverso da `A`/`B`/`C` (`D`, `E`, `F`, `X`, `U`) e AllWISE
  `ph_qual` diverso da `A`/`B`/`C` (`U`, `X`, `Z`): punto nella tabella,
  **fuori dal grafico**, con il motivo (D20-4); `U` (2MASS e AllWISE) =
  **limite superiore** (`SED_UPPER_LIMIT`): convertito in flusso come limite,
  fuori dal grafico (D20-9 (3)); gli altri `SED_LOW_QUALITY`. Il carattere di
  `ph_qual` è quello della banda (J, H, Ks; W1–W4, nell'ordine). Gaia: nessuna
  esclusione, `phot_variable_flag` e `phot_bp_rp_excess_factor` mostrati.
  Esempi del 2026-11-07: Vega 2MASS `CBC` con J = −0,177 (saturata), Alcyone
  `DCD`, AllWISE di Vega `UUAA`.
- **Duplicati:** un valore SIMBAD con lo stesso riferimento di un catalogo
  interrogato direttamente (es. 51 Peg: SIMBAD `G` = 5,283212 da
  2020yCat.1350, `J/H/K` da 2003yCat.2246, cioè Gaia e 2MASS) è marcato
  «duplicato di» e non entra due volte nel grafico (D20-6). Riferimenti
  (`CATALOG_REFERENCES`, bibcode visti nelle risposte SIMBAD del 2026-11-07):
  Gaia `2022yCat.1355....0G` (catalogo VizieR I/355, Gaia DR3) e
  `2020yCat.1350....0G` (I/350, Gaia EDR3: la fotometria G, BP, RP di DR3 è
  quella di EDR3, D20-9 (2)); 2MASS `2003yCat.2246....0C` (II/246). Bande:
  SIMBAD `G` → Gaia G, `J`/`H`/`K` → 2MASS J/H/Ks. La tabella `filter` di
  SIMBAD (letta il 2026-11-07) non ha bande WISE: nessun duplicato AllWISE
  possibile. Altri riferimenti (es. `2014yCat.2328....0C`, il catalogo
  AllWISE, che SIMBAD cita per J/H/K) **non** sono duplicati: restano
  magnitudini SIMBAD in tabella. «Duplicato» solo se il punto del catalogo
  c'è davvero nella SED.
- Le magnitudini SIMBAD di bande senza punto zero in tabella (es. Johnson
  U, B, V, R, I) restano in magnitudini (D20-6).

### 3.4 Grafico

λ (µm) in ascissa, Fν (Jy) in ordinata, scale logaritmiche; barre d'errore;
colori per catalogo; serie VizieR distinta; limiti superiori come frecce;
tooltip con la provenienza del punto. Alternativa λFλ come opzione (D20-7).

### 3.5 Serie VizieR e avviso di moto proprio

La serie VizieR (`VizierSeries`) contiene le righe del servizio così come
date (`_sed_freq` in GHz, `_sed_flux` e `_sed_eflux` in Jy, `_sed_filter`,
`_tabname`); per il grafico la frequenza si porta in lunghezza d'onda con
`astropy.units.spectral()` (cambio di unità, dichiarato). Se il moto proprio
del bersaglio sposta la posizione di almeno il raggio della serie tra J2000 e
J2016 (|μ| · 16 anni ≥ 2″) → `SED_HIGH_PROPER_MOTION` (D20-5, soglia D25-14
(5)).

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

Codice: `src/astrotwo/analysis/photometry.py` (livello 2; non dipende dal `25`).

- **`ZERO_POINTS`** — tabella di §3.2 (chiave `"Gaia DR3 G"`, `"2MASS J"`,
  `"WISE W1"`, …→ `ZeroPoint`: banda, sistema, tipo di conversione, punto
  zero ed errore, λ di riferimento con tipo ed errore, fonte, riferimento,
  data di verifica), unica fonte delle conversioni; **`AB_FLUX_ZERO`** =
  3631 Jy; **`CATALOG_REFERENCES`** (§3.3).
- **`SedPoint`** — un punto (§3.1) con `provenance` (mappa del chiamante),
  flusso convertito, formula, motivi (`codes`), `in_plot`, `duplicate_of`.
- **`sed_points_from(table, catalog, *, identifier, match, provenance)`** —
  punti di una tabella nota (`gaia_dr3`, `2mass`, `allwise`) o delle
  magnitudini SIMBAD (`simbad`: sequenza di `SimbadMagnitude` del 14).
- **`mag_to_flux(point)`** — punto con Fν ed errore, punto zero e formula
  usati, oppure con il motivo per cui non si converte (`SED_NO_ZERO_POINT`,
  `SED_NO_SYSTEM`).
- **`build_sed(points, vizier=None)`** — `Sed` con conversioni, duplicati e
  qualità marcati; `vizier`: tabella di `vizier_photometry`.
- **`plot_sed(sed, *, quantity="fnu")`** (figura matplotlib, senza pyplot;
  `"lambda_flambda"` in opzione, D20-7), **`sed_png(sed, ...)`** (PNG) e
  **`sed_table(sed)`** (tabella Astropy, una riga per punto).

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
| Moto proprio elevato per la serie VizieR | serie presente, avviso (§3.5) | `SED_HIGH_PROPER_MOTION` |
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
| T10 | Grafico | `sed_png` per 51 Peg | PNG leggibile, solo i punti `in_plot`, serie VizieR distinta | lettura del PNG |

## 13. Decisioni aperte

Decisioni D20-1…D20-8 **prese dal proprietario il 2026-11-07** (dopo il
report dello sprint C1); restano qui come registro. Il codice della parte SED
è dello sprint C3. Aperta: **D20-9** (scelte minori dello sprint C3, da
confermare).

- **D20-1 — Tabella dei punti zero — DECISA (2026-11-07):** come §3.2 (Gaia AB
  tramite il flusso in e⁻/s, 2MASS di Cohen et al. 2003, WISE a spettro
  costante senza correzioni di colore). Le note «da verificare» di §3.2
  (incertezza WISE, validità per AllWISE) **chiuse il 2026-11-07** (sprint
  C3, §3.2).
- **D20-2 — λ di riferimento delle bande Gaia — DECISA (2026-11-07):** valori
  **pubblicati nella documentazione ufficiale di Gaia**, citati; il calcolo
  dalla banda passante (`passband.dat`) solo se mancano **e** la licenza dei
  dati lo permette, dichiarandolo nel risultato. **Valori trovati il
  2026-11-07** (documentazione di Gaia DR3 §5.4.1, Tabella 5.4, §3.2): nessun
  calcolo dalla banda passante.
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

- **D20-9 — Scelte minori dello sprint C3 — da confermare (proprietario).**
  (1) lunghezza d'onda di riferimento di Gaia = pivot λ_p della Tabella 5.4
  della documentazione di Gaia DR3 (non λ₀); WISE con λ(iso) a 4 decimali
  della Tabella 9 (stessa fonte delle incertezze); (2) SIMBAD `G` da Gaia EDR3
  (`2020yCat.1350`) duplicato del punto Gaia DR3 (stessa fotometria);
  (3) limiti superiori `U` convertiti come limiti ma fuori dal grafico (non
  frecce nella 1.0); (4) 2MASS `U` trattato come AllWISE `U`; (5) **da
  decidere — costante del sistema AB:** §3.2 scrive 3631 Jy (valore
  arrotondato); la definizione di Oke & Gunn (m_AB = −2,5 log₁₀ Fν − 48,60, cgs)
  dà 10^(−0,4·48,60) · 10²³ Jy = 3630,78 Jy, che è anche il valore implicito
  nell'equazione 5.48 della documentazione di Gaia DR3 («ZP_AB + 56,10», unità
  SI) e quello di Astropy (`u.ABmag`). Differenza relativa 6·10⁻⁵ (0,00006
  mag), sotto l'incertezza dei punti zero Gaia (0,0016–0,0028 mag). Il codice
  usa 3631 Jy come scritto; proposta: passare a 3630,78 Jy (definizione
  esatta), aggiornando prima §3.2.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-11-07 | Claude Code | **Sprint C3 (autorizzazione D25-12):** punti zero e lunghezze d'onda verificati sulle fonti ufficiali il 2026-11-07 (`zeropt.dat` ESA versione 2 identico; λ_p di Gaia dalla documentazione di Gaia DR3 §5.4.1 Tab. 5.4; incertezze e λ(iso) WISE dalla Tabella 9 del supplemento All-Sky, Jarrett et al. 2011; AllWISE §V.3.e: stessa conversione; 2MASS invariato): note «da verificare» di D20-1 e D20-2 chiuse. §3.3 qualità di 2MASS `U`, riferimenti dei duplicati (`CATALOG_REFERENCES`); nuovo §3.5 (serie VizieR, `SED_HIGH_PROPER_MOTION`); §7 con il codice `photometry.py` e le firme; §10, T10; nuova D20-9 (scelte minori, da confermare). |
| 2026-11-07 | Claude Code | **Decisioni del proprietario del 2026-11-07 (sprint C2):** file `approvato` per la sola parte SED (formula di D25-12 del `25`); D20-1…D20-8 scritte come decise (D20-2: λ di Gaia dalla documentazione ufficiale, calcolo dalla banda passante solo se mancano e la licenza lo permette, dichiarato). Nessun codice in C2 (SED nello sprint C3). |
| 2026-11-07 | Claude Code | Creazione del file (stato: bozza), sprint C1: solo parte SED; punti zero di Gaia (E)DR3, 2MASS e WISE letti sulle fonti ufficiali il 2026-11-07; decisioni aperte D20-1…D20-8. |
