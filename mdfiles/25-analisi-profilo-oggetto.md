# 25-analisi-profilo-oggetto.md — Profilo di un oggetto in un minuto

**Stato:** approvato

> Modulo nuovo proposto il 2026-11-07 (sprint C1, Fase C) con la meccanica AM1;
> **AM1 accettata e file approvato dal proprietario il 2026-11-07** (D25-1:
> numero 25, livello 2, codice in `src/astrotwo/analysis/object_profile.py`).
> Fase codice dichiarata con la formula di D25-12 (§13). Lo sprint C2 scrive il
> motore (bersaglio, identificativi, identità, astrometria, distanza) e il
> comando `object.profile`; le precisazioni nate scrivendo C2 sono in §3.10,
> quelle di C3 (fotometria e SED) in §3.11, quelle di C4 (parallelismo e
> Annulla) in §3.12, Immagini e Pianeti in §3.13, la ricerca dei pianeti
> senza attendere Gaia (D25-17 (10), sprint C5) in §3.14, esportazione, SED
> come catalogo e SAMP (sprint C6) in §3.15. L'interfaccia è specificata in
> `43-ui-profili.md` (D25-7, `approvato` il 2026-11-08).

## 2. Scopo

Dato un nome, una sorgente selezionata o una coppia di coordinate, costruire in
circa un minuto il **profilo** di un oggetto (identità, immagini, astrometria,
distanza, fotometria e SED, pianeti noti) in cui ogni numero ha la sua fonte, la
sua incertezza e il comando che lo ha prodotto, ed è riproducibile con un clic.

## 3. Cosa fa

### 3.1 Principio

Il profilo è **un comando registrato del `05`** (`object.profile`, §7) che
esegue in parallelo **sezioni indipendenti**. Ogni sezione interroga servizi
pubblici attraverso le funzioni già esistenti del livello 1 (10, 12, 13, 14, con
i loro mirror) e restituisce **valori con provenienza** (`ProfileValue`, §7).
Nessun numero è prodotto fuori dal codice deterministico (regola d'oro n. 1):
i valori sono **letti** dai servizi (con unità, errore e riferimento) oppure
**calcolati** da funzioni testate di questo modulo o del `20` (distanza da
parallasse, conversione magnitudine → flusso), con il metodo scritto nel
risultato.

### 3.2 Bersaglio e identificazione (regola a, decisa il 2026-11-07)

1. **Nome:** risolto da SIMBAD (`simbad_object` del 14, nuova, §7.2) con il
   ripiego Strasburgo → Harvard già in uso (D14-14). Il risultato dà
   l'oggetto SIMBAD (`main_id`, `oid`) e **l'elenco completo dei suoi
   identificativi** (tabella `ident`). Se SIMBAD non è raggiungibile su nessun
   server, il nome si risolve con `resolve_name` del 10 (fino a NED) e il
   profilo continua **per posizione**, dichiarandolo (§3.3, avviso
   `PROFILE_NO_IDENTIFIERS`).
2. **Sorgente selezionata** in un catalogo caricato: se la riga ha un
   identificativo riconosciuto (colonna `source_id` di Gaia DR3, `designation`
   di 2MASS o AllWISE, `main_id` di SIMBAD), si parte da quello; altrimenti
   dalla sua posizione (con epoca del livello, D10-2).
3. **Coordinate:** sistema ed epoca dichiarati (DC2, mai assunti). Si cercano i
   candidati SIMBAD entro un raggio (D25-9, proposta 10″ dopo la propagazione
   del moto proprio all'epoca di SIMBAD J2000). **Più candidati: nessuna scelta
   silenziosa** — l'utente sceglie da un elenco (nome, tipo, distanza, numero di
   citazioni); senza scelta (es. riesecuzione da script) il profilo si ferma con
   `PROFILE_AMBIGUOUS_TARGET` e l'elenco. Un solo candidato: si usa, con la
   distanza dichiarata. Nessun candidato: profilo per posizione (§3.3).

**Catena degli identificativi (proposta D25-4).** Per ogni catalogo, in ordine:

| Catalogo | 1° identificativo SIMBAD | 2° incrocio ufficiale dell'archivio | 3° posizione (§3.3) |
|---|---|---|---|
| Gaia DR3 | `Gaia DR3 <source_id>` | — | sì |
| 2MASS PSC | `2MASS J<designation>` | `gaiadr3.tmass_psc_xsc_best_neighbour` (archivio Gaia ESA) dal `source_id` | sì |
| AllWISE | `WISEA J<designation>` | `gaiadr3.allwise_best_neighbour` (archivio Gaia ESA) dal `source_id` | sì |
| NASA Exoplanet Archive | `gaia_dr3_id` = `Gaia DR3 <source_id>` | `hostname` uguale a un identificativo SIMBAD | no (i pianeti solo per identificativo) |

Gli incroci ufficiali dell'archivio Gaia sono anch'essi incroci per posizione,
ma fatti e pubblicati dal consorzio Gaia: il profilo li usa come identificativi
**dichiarando il metodo** (`match = official_crossmatch`, tabella e
`angular_distance` restituiti dall'archivio). Se SIMBAD e l'incrocio ufficiale
indicano due sorgenti diverse, **nessuna scelta**: la sezione mostra entrambe
e l'avviso `PROFILE_IDENTIFIER_CONFLICT`.

### 3.3 Incrocio per posizione (solo se l'identificativo manca)

Solo quando la catena di §3.2 non dà un identificativo. Regole:

- raggio **esplicito** (D25-9) scritto nel comando e nel risultato;
- **propagazione dell'epoca dichiarata** (D10-2, `propagate_position` del 10):
  la posizione del bersaglio (con il moto proprio di Gaia DR3 o, se assente,
  di SIMBAD, con la fonte) è portata all'epoca del catalogo interrogato
  (2MASS: `jdate` della sorgente; AllWISE: epoca dichiarata dall'archivio, da
  verificare prima del codice; Gaia DR3: J2016.0). Senza moto proprio noto: nessuna
  propagazione e avviso `PROFILE_NO_PROPER_MOTION`;
- **avviso** `PROFILE_POSITIONAL_MATCH` con raggio, separazione ed epoche;
- **più candidati nel raggio:** nessuna scelta silenziosa (come §3.2).

Esempio verificato il 2026-11-07 (§12, T4): Vega non è in Gaia DR3; un cerchio
di 36″ trova solo stelle di G ≈ 16–17 a 30–36″ che **non** sono Vega. La regola
dell'identificativo evita di attribuirle a Vega: la sezione Gaia dice «nessuna
sorgente Gaia DR3 associata in SIMBAD» e, se si prova la posizione, nessun
candidato entro il raggio.

### 3.4 Sezioni del profilo (versione 1.0)

Ogni sezione è **indipendente** (regola c): ha il suo stato (`pending`,
`running`, `done`, `partial`, `error`, `not_applicable`, `cancelled` — §3.12),
i suoi errori e i suoi avvisi. Se un servizio è giù (dopo i mirror già esistenti), quella sezione
mostra l'errore e il resto del profilo arriva comunque.

1. **Identità** (SIMBAD, con mirror): nome principale, tipo di oggetto
   (`otype`, con la descrizione della nomenclatura di SIMBAD), tipo spettrale
   (`sp_type` con `sp_bibcode`), numero di citazioni (`nbref`), coordinate
   SIMBAD (ICRS, epoca J2000, `coo_bibcode`), elenco degli identificativi
   (raggruppati per catalogo: nomi propri `NAME`, HD, HIP, HR, Gaia DR2/DR3,
   2MASS, WISE, TIC, …), collegamento alla pagina SIMBAD del server che ha
   risposto (come il 41).
2. **Immagini:** miniature da più survey HiPS (proposta D25-5: DSS2 colore,
   2MASS colore, AllWISE colore), centrate sul bersaglio **all'epoca della
   survey quando nota** (altrimenti posizione SIMBAD J2000, dichiarato), campo e
   dimensione fissi nel comando, disegnate con il codice HiPS esistente del 12
   (`view_sampling`/`fill_view`, senza OpenGL) e i suoi mirror (D12-9). Ogni
   miniatura con survey, server, ordine HEALPix, campo, crediti.
3. **Astrometria** (Gaia DR3 dall'archivio Gaia ESA, `gaiadr3.gaia_source`, per
   `source_id`): posizione con epoca (`ref_epoch` J2016.0) ed errori, parallasse,
   moto proprio, velocità radiale se presente, con errori; **indicatori di
   qualità** (D25-11): `ruwe`, `astrometric_params_solved` (2, 5 o 6
   parametri), `duplicated_source`, `ipd_frac_multi_peak`,
   `phot_variable_flag`. Una soluzione a **2 parametri** (es. Alcyone, §12 T3)
   non ha parallasse né moto proprio: la sezione lo dice con
   `PROFILE_GAIA_TWO_PARAMETER`. Senza Gaia DR3 (Vega): la sezione mostra i valori
   astrometrici di SIMBAD con la loro fonte (`plx_bibcode`, `pm_bibcode`) e
   l'avviso `PROFILE_NO_GAIA`.
4. **Distanza** (sotto-sezione dell'astrometria), **solo con metodo dichiarato**
   (proposta D25-2, in ordine):
   1. **Bailer-Jones et al. (2021)**, distanze da Gaia EDR3, tabella
      `external.gaiaedr3_distance` dell'archivio Gaia ESA, per `source_id`
      (stesso `source_id` di DR3): mediana geometrica `r_med_geo` con
      `r_lo_geo`/`r_hi_geo` (16° e 84° percentile) e, se presente, fotogeometrica
      `r_med_photogeo`; `flag` mostrato; riferimento 2021AJ....161..147B;
   2. altrimenti **1/parallasse** solo se `parallasse / errore ≥ 10` (errore
      relativo ≤ 10 %, soglia dichiarata), con la parallasse di Gaia DR3 o, in
      mancanza, quella di SIMBAD con il suo riferimento (es. Hipparcos,
      van Leeuwen 2007); intervallo da 1/(ϖ ± σ); nessuna correzione dello zero
      point di parallasse nella 1.0 (D25-10), dichiarato;
   3. altrimenti **nessuna distanza**, con il motivo
      (`PROFILE_NO_DISTANCE`: `no_parallax`, `low_snr` con il rapporto,
      `negative_parallax`).
5. **Fotometria e SED:** costruite dal **modulo `20`** (`20-analisi-fotometria.md`,
   parte SED). Punti da Gaia DR3 (G, BP, RP), 2MASS (J, H, Ks, dall'IRSA
   `fp_psc`), AllWISE (W1–W4, dall'IRSA `allwise_p3as_psd`), SIMBAD (tabella
   `flux`) e, quando il CDS risponde, dal servizio SED di VizieR (serie separata,
   per posizione). Ogni punto con catalogo, banda, sistema, valore, errore,
   qualità; conversione in flusso **solo** con i punti zero documentati del `20`.
6. **Pianeti noti** (NASA Exoplanet Archive, servizio TAP, proposta D25-3:
   tabella `pscomppars`): per ogni pianeta nome, metodo e anno di scoperta,
   periodo, semiasse, eccentricità, massa (o `M sin i`, campo `pl_bmassprov`),
   raggio, temperatura di equilibrio, ciascuno con errori superiore e inferiore
   e **riferimento per parametro** (`*_reflink`, testo esterno: se ne legge solo
   il bibcode/URL ADS, §9). Nessun pianeta: «nessun pianeta nell'archivio» (non
   è un errore).

### 3.5 Tempi e parallelismo

Le sezioni partono insieme (al più 4 richieste di rete contemporanee, D25-8);
ciascuna ha il suo tempo massimo; l'insieme ha un tempo obiettivo di 60 s
(regole precise dello sprint C4 in §3.12).
Tempi osservati il 2026-11-07 (§12, verifiche): SIMBAD Harvard ≈ 0,35 s per
interrogazione, archivio Gaia 0,4–6,7 s (con rifiuti HTTP 503 per coda piena,
riusciti al secondo tentativo), IRSA 10–18 s per un cerchio AllWISE e 16 s per
2MASS per `designation`, Exoplanet Archive 1,3–2 s. **L'interrogazione AllWISE
per `designation` non termina in 90 s** (colonna non indicizzata): per AllWISE
si usa un cerchio piccolo intorno alla posizione propagata e si controlla che
la `designation` coincida (proposta, D25-4).

### 3.6 Riproducibilità (regola d)

Il comando registrato contiene il bersaglio come scritto dall'utente **e** gli
identificativi risolti (SIMBAD `main_id`, `source_id`, designazioni) e i server
che hanno risposto: la riesecuzione rifà le stesse richieste (dalla cache se
presenti, A7); **«Riesegui con dati aggiornati»** (`refresh`, sprint B4) le
rifà dalla rete e segnala le differenze (`DATA_REFRESHED`). Ogni valore porta
il comando (`command_id`) che lo ha prodotto.

### 3.7 Esportazione (D25-6, decisa; precisata in §3.15)

- **Tabella dei dati con provenienza** in ECSV (una riga per valore: sezione,
  grandezza, valore, errore inferiore/superiore, unità, banda e sistema, metodo,
  servizio, server, tabella, interrogazione ADQL, identificativo usato, tipo di
  incrocio, riferimento bibliografico, data, cache sì/no, `command_id`);
- **scheda in PDF** (una pagina A4 per sezione al più), con le miniature, il
  grafico della SED e le fonti in nota; PNG della SED con i crediti (come il 41);
- punti della SED come **nuovo livello catalogo** (parità H17) e invio con SAMP
  (VOTable, `14`).

### 3.8 Fuori dalla 1.0 (estensioni annotate)

Eccesso infrarosso (confronto SED/modello), curve di luce (TESS, ZTF, Gaia
epoch photometry; modulo 22), articoli scientifici (ADS), spettri (SSA, modulo
21), profilo dei pianeti con gli spettri del JWST. Annotati in `panoramica.md`
(Fase C) come estensioni; nessuno è specificato qui.

### 3.9 Interfaccia (proposta; dove scriverla: D25-7)

> Dal 2026-11-08 la specifica dell'interfaccia è **`43-ui-profili.md`**
> (D25-7, sprint C5), che parte da questo paragrafo e lo precisa; in caso di
> differenza vale il `43`.

**Da dove si apre:**
- menu **Data → Object profile…** / **Profilo dell'oggetto…** (campo nome o
  coordinate con sistema ed epoca);
- campo **«Vai a»** del 40: dopo la risoluzione di un nome, pulsante
  «Profilo» accanto al risultato;
- clic destro nel cielo (41) e sul **riquadro del puntatore SIMBAD**: «Profilo
  di <nome>» (usa l'oggetto del puntatore, per identificativo);
- clic destro su una riga della tabella (42): «Profilo di questa sorgente»
  (identificativo della riga se riconosciuto, altrimenti posizione);
- **assistente** (35): strumento `object__profile` con conferma (rete).

**Come si presenta:** una **finestra non modale «Profili»** con una scheda per
oggetto (più profili aperti insieme), sezioni impilate in verticale: Identità
(con miniature a destra), Astrometria e distanza, Fotometria (tabella dei punti
e grafico della SED: λ in µm contro Fν in Jy, log-log, punti con barre
d'errore, limiti superiori come frecce, serie VizieR in un colore diverso),
Pianeti (tabella). **Clic su un numero** → riquadro con valore, errori, unità,
metodo, servizio, server, tabella, interrogazione, riferimento (link ADS), data,
cache, comando.

**Mentre i servizi rispondono:** la scheda si apre subito con lo scheletro
delle sezioni; ogni intestazione mostra lo stato (in attesa → in corso con
il servizio interrogato e i secondi trascorsi → arrivata con fonte e tempo →
errore con il messaggio del catalogo e il pulsante «Riprova questa sezione»,
che registra un comando `object.profile` limitato a quella sezione). Le
sezioni arrivano una alla volta, nell'ordine in cui rispondono. L'avanzamento
e Annulla stanno nella barra di stato come per gli altri comandi (40).

**Pulsanti della scheda:** «Riesegui con dati aggiornati», «Esporta…» (ECSV,
PDF, PNG della SED), «Mostra nel cielo» (`view.set_center`), «Carica i punti
SED come catalogo», «Invia con SAMP».

### 3.10 Precisazioni dello sprint C2 (motore, 2026-11-07)

Scritte prima del codice dello sprint C2; le scelte minori sono raccolte in
D25-13 (decisa il 2026-11-07). In C2 esistono le sezioni **Identità** e
**Astrometria** (con la distanza); immagini, fotometria e pianeti arrivano
negli sprint C3–C4.

**Bersaglio.**
1. **Nome:** `simbad_object` del 14 (§7.2). SIMBAD confronta gli
   identificativi della tabella `ident` **normalizzandoli** (verificato il
   2026-11-07 sul mirror di Harvard: `'51 Peg'` → `* 51 Peg`, `'vega'` →
   `NAME Vega`, `'eta Tau'` → `* eta Tau`): il nome si passa così come
   scritto. Nessun oggetto → `NAME_NOT_FOUND` (sotto-voce `simbad_identifier`),
   profilo non creato. SIMBAD giù su tutti i server → `resolve_name` del 10
   (fino a NED), sezione Identità in errore con l'errore del 14, profilo per
   posizione con `PROFILE_NO_IDENTIFIERS`.
2. **Coordinate** (sistema ed epoca dichiarati, convertite in ICRS dal 10):
   candidati SIMBAD dalla tabella `basic` in un cerchio di raggio
   `match_radius + PM_SEARCH_MAX · |Δt|`, con Δt = epoca del bersaglio −
   J2000.0 e **`PM_SEARCH_MAX` = 10,5″/anno** (sopra il moto proprio più grande
   noto, la stella di Barnard: 10,393″/anno da SIMBAD, `pm_bibcode`
   2020yCat.1350....0G, letto il 2026-11-07). Ogni candidato con moto proprio
   SIMBAD è portato **all'epoca del bersaglio** con `propagate_position` del 10
   (`proper_motion_only=True`, dichiarato); senza moto proprio resta a J2000
   (dichiarato nel candidato). Entrano i candidati con separazione ≤
   `match_radius` (Astropy), in ordine di separazione e poi di `main_id`.
   **Pianeti esclusi (D25-13 (8), decisione del proprietario del
   2026-11-07):** gli oggetti della famiglia «Planet» della gerarchia
   ufficiale dei tipi di SIMBAD — tipi il cui percorso `otypedef.path`
   contiene il nodo `Pl` (verificato il 2026-11-07 sul mirror di Harvard:
   `Pl` «Extra-solar Planet» e `Pl?` «Extra-solar Planet Candidate», entrambi
   con percorso `* > Pl`; `PN` ha percorso `* > Ev* > PN` e non è un pianeta)
   — sono tolti dai candidati **in modo dichiarato**: avviso
   `PROFILE_PLANETS_EXCLUDED` con il numero e i nomi degli esclusi. Il
   percorso si legge nella stessa richiesta dei candidati (`LEFT OUTER JOIN
   otypedef`), mai da un elenco scritto nel codice. L'ambiguità tra oggetti
   non pianeti resta (`PROFILE_AMBIGUOUS_TARGET`, es. eta Tau con la nebulosa
   `GN 03.44.2`). Uno
   → usato, con la separazione nel risultato; più di uno →
   `PROFILE_AMBIGUOUS_TARGET` con l'elenco (`main_id`, `otype`, separazione,
   `nbref`), nessuna scelta; nessuno → profilo per posizione. Epoca del
   bersaglio non nota (`null` con motivo): nessuna propagazione, raggio =
   `match_radius`, avviso `PROFILE_NO_PROPER_MOTION` (`target_epoch_unknown`).
3. **Riga di catalogo** (`layer` + `row`): in C2 vale **per posizione**, con
   l'epoca del livello (13, D10-2); il riconoscimento delle colonne
   identificative della riga arriva con l'interfaccia (C5, D25-13 (3)).
4. **`simbad_id`** (parametro del comando): `main_id` SIMBAD dell'oggetto. Il
   comando lo **scrive** nel comando registrato dopo la risoluzione;
   l'interfaccia lo passa dopo la scelta dell'utente tra più candidati.
   **Con un nome**, la riesecuzione risolve di nuovo **il nome** (stessa
   richiesta, quindi dalla cache, A7) e `simbad_id` fa da controllo: se SIMBAD
   dà un oggetto diverso (tipicamente con «Riesegui con dati aggiornati»),
   avviso `PROFILE_TARGET_CHANGED` con i due `main_id` e il profilo usa
   l'oggetto di oggi, dichiarato. **Con coordinate o una riga**, `simbad_id`
   decide l'oggetto (nessuna nuova ricerca dei candidati): è la scelta
   registrata.

**Catena degli identificativi in C2** (`cross_identify`).
- **Gaia DR3:** `Gaia DR3 <source_id>` dagli identificativi SIMBAD; se manca,
  **passo per posizione**: posizione SIMBAD (J2000) portata a J2016.0 con
  `propagate_position` (con parallasse SIMBAD positiva; altrimenti solo moto
  proprio, dichiarato; senza moto proprio nessuna propagazione e
  `PROFILE_NO_PROPER_MOTION`), cerchio di `crossmatch_radius` (default 2″,
  D25-9) su `gaiadr3.gaia_source`. Nessuna sorgente → `PROFILE_NO_GAIA`
  (`no_counterpart`); una → usata con `PROFILE_POSITIONAL_MATCH` (raggio,
  separazione, epoche); più di una → **nessuna scelta**, elenco nel risultato
  e `PROFILE_POSITIONAL_MATCH` (`several_candidates`), astrometria da SIMBAD.
  Un `source_id` indicato da SIMBAD ma assente dall'archivio →
  `PROFILE_NO_GAIA` (`not_in_archive`).
- **2MASS e AllWISE:** identificativo SIMBAD (`2MASS J…`, `WISEA J…`) e, con
  un `source_id` Gaia, **sempre anche** l'incrocio ufficiale
  (`gaiadr3.tmass_psc_xsc_best_neighbour`, `gaiadr3.allwise_best_neighbour`,
  colonne verificate il 2026-11-07: `original_ext_source_id`,
  `angular_distance` in arcsec, `number_of_neighbours`, `xm_flag`), così un
  disaccordo si vede. Confronto sulle designazioni senza prefisso
  (`2MASS J22572795+2046077` ↔ `22572795+2046077`; `WISEA
  J230630.02-050234.1` ↔ `J230630.02-050234.1`, formati verificati). Diversi →
  `PROFILE_IDENTIFIER_CONFLICT` con entrambi, nessuna scelta. Nessuno dei due
  → «non trovato» con la nota che il passo per posizione arriva con la
  fotometria (C3, D25-13 (4)).
- **NASA Exoplanet Archive** (voce `nasa-exoplanet-tap` del 14): `SELECT
  DISTINCT hostname, gaia_dr3_id FROM pscomppars WHERE gaia_dr3_id = 'Gaia DR3
  <source_id>'`; senza righe (o senza `source_id`), `hostname` uguale a un
  identificativo SIMBAD (confronto sugli identificativi senza i prefissi
  SIMBAD `*`, `**`, `V*`, `NAME` e con gli spazi ridotti a uno). Nessuna
  riga: «nessun ospite nell'archivio», non è un errore. In C2 la catena dà
  solo l'ospite; i pianeti sono dello sprint C4.

**Sezione Identità:** `main_id`, `otype` con la descrizione della tabella
`otypedef` di SIMBAD, `sp_type` con `sp_bibcode`, `nbref`, posizione ICRS
J2000 con `coo_err_maj`/`coo_err_min`/`coo_err_angle`, `coo_qual`,
`coo_bibcode`; identificativi raggruppati per catalogo (prima parola
dell'identificativo, `NAME` = nomi propri, `*`/`**`/`V*` = nomi di stelle);
collegamento alla pagina SIMBAD del server che ha risposto.

**Sezione Astrometria:** dal `source_id`, `gaiadr3.gaia_source` dell'archivio
Gaia ESA: `ra`, `dec` (con `ra_error`, `dec_error` in mas) a `ref_epoch`,
`parallax`, `pmra`, `pmdec`, `radial_velocity` con gli errori; indicatori
`ruwe` (senza soglia, D25-11), numero di parametri = bit a 1 di
`astrometric_params_solved` (definizione del modello dei dati Gaia DR3),
`duplicated_source`, `ipd_frac_multi_peak`. Soluzione a 2 parametri →
`PROFILE_GAIA_TWO_PARAMETER` e **anche** parallasse e moto proprio di SIMBAD
con la loro fonte (D25-13 (7)); nessuna sorgente Gaia → valori di SIMBAD
(`plx_*`, `pm*`, `rvz_*` con i bibcode) e `PROFILE_NO_GAIA`.

**Distanza** (`distance_from`): Bailer-Jones per `source_id` da
`external.gaiaedr3_distance` (colonne verificate il 2026-11-07: `r_med_geo`,
`r_lo_geo`, `r_hi_geo`, `r_med_photogeo`, `r_lo_photogeo`, `r_hi_photogeo`
in pc, `flag`); altrimenti 1/ϖ con la parallasse di Gaia DR3 (soluzioni a 5
o 6 parametri) o, **se Gaia non la dà**, quella di SIMBAD con il suo
`plx_bibcode`, solo se ϖ/σ ≥ `PARALLAX_SNR_MIN` = 10: distanza =
`(ϖ).to(u.pc, u.parallax())` e intervallo [1/(ϖ+σ), 1/(ϖ−σ)], con la nota
«nessuna correzione dello zero point di parallasse (D25-10)»; altrimenti
`PROFILE_NO_DISTANCE` (`no_parallax`, `low_snr` con il rapporto,
`negative_parallax`). Una parallasse di Gaia con rapporto < 10 **non** passa a
quella di SIMBAD (la regola dice «in mancanza»).

**Valori e provenienza.** Ogni `ProfileValue` ha grandezza, valore e unità
(Astropy, `float64`), errore (simmetrico o inferiore/superiore), metodo
(`read` = letto dal servizio; `computed` = calcolato, con la funzione e la
formula), riferimento bibliografico se il servizio lo dà, e la `Provenance`:
servizio (con il server che ha risposto), URL, tabella, interrogazione ADQL,
identificativo usato e tipo di incrocio, data, cache sì/no. Il `command_id`
è il numero del comando nella cronologia del 05 (il risultato appartiene al
comando); l'esportazione (C6) lo scrive in ogni riga.

**Esecuzione in C2:** sezioni una dopo l'altra (il parallelismo è dello
sprint C4, §3.12, che sostituisce questo paragrafo per l'ordine e
l'annullamento); l'annullamento si controlla tra le richieste; un errore di una
sezione resta nella sezione (stato `error`, messaggio del modulo invariato) e
il comando termina `ok`; solo un bersaglio non risolvibile
(`NAME_NOT_FOUND`, `PROFILE_AMBIGUOUS_TARGET`, `PROFILE_TARGET_INVALID`) fa
terminare il comando in errore.

### 3.11 Precisazioni dello sprint C3 (fotometria e SED, 2026-11-07)

Scritte prima del codice dello sprint C3; le scelte minori sono raccolte in
D25-14 (decisa il 2026-11-07). La sezione **`photometry`** si aggiunge a `sections`
(D25-13 (5): l'elenco si allarga senza cambiare versione del comando). I punti,
le conversioni, la qualità, i duplicati e il grafico sono del `20` (parte SED,
§3 e §7 del `20`); il `25` sceglie le sorgenti e fa le richieste.

**Richieste per identificativo.**
- **Gaia DR3** (solo con un `source_id` della catena): `SELECT source_id,
  phot_g_mean_mag, phot_g_mean_flux, phot_g_mean_flux_error, phot_bp_mean_mag,
  phot_bp_mean_flux, phot_bp_mean_flux_error, phot_rp_mean_mag,
  phot_rp_mean_flux, phot_rp_mean_flux_error, phot_variable_flag,
  phot_bp_rp_excess_factor FROM gaiadr3.gaia_source WHERE source_id = N`
  (archivio Gaia ESA). Una soluzione astrometrica a 2 parametri ha comunque la
  fotometria (Alcyone).
- **2MASS** (IRSA `fp_psc`) e **AllWISE** (IRSA `allwise_p3as_psd`), servizio
  `nasa-irsa-tap` del 14: `designation = '…'` **dentro un cerchio di
  `DESIGNATION_RADIUS` = 2″ attorno alla posizione scritta nella designazione**
  (2MASS `hhmmssss±ddmmsss`, AllWISE `Jhhmmss.ss±ddmmss.s`: posizione del
  catalogo troncata, formati verificati il 2026-11-07). Il cerchio viene
  dall'identificativo, non dal bersaglio; serve perché la sola condizione sulla
  designazione non usa l'indice spaziale (AllWISE: timeout a 90 s il
  2026-11-07; con il cerchio risposta in meno di 2 s). Colonne: 2MASS
  `designation, ra, dec, j_m, j_msigcom, h_m, h_msigcom, k_m, k_msigcom,
  ph_qual, rd_flg, cc_flg, jdate`; AllWISE `designation, ra, dec, w1mpro,
  w1sigmpro, …, w4mpro, w4sigmpro, ph_qual, cc_flags, ext_flg`. Nessuna riga
  → avviso `PROFILE_NO_PHOTOMETRY` (`not_in_catalog`) con l'identificativo.
- **SIMBAD:** magnitudini della tabella `flux` già lette da `simbad_object`
  (nessuna nuova richiesta), con `system`, `qual`, `bibcode`.

**Passo per posizione di 2MASS e AllWISE** (D25-13 (4)), nella catena
(`cross_identify`, quindi visibile anche nella sezione Identità), **solo se**
né SIMBAD né l'incrocio ufficiale di Gaia danno l'identificativo (mai per
superare un `PROFILE_IDENTIFIER_CONFLICT`):
- **AllWISE:** posizione del bersaglio portata all'epoca **MJD 55400,0 UTC
  (2010,5589)** con `propagate_position` (come per Gaia, §3.10). Fonte: AllWISE
  Explanatory Supplement §II.1 (letto il 2026-11-07): è l'epoca delle
  posizioni «motion-fit» ed «è vicina al punto medio delle osservazioni», per
  cui le posizioni stazionarie `ra`/`dec` «dovrebbero essere molto simili».
  Cerchio di `crossmatch_radius` su `ra`, `dec`.
- **2MASS:** le posizioni sono all'epoca di ciascuna misura (`jdate`, giorno
  giuliano «±30 s»; il servizio non dichiara la scala: trattata come UTC,
  dichiarato nel risultato; la differenza con TT, circa un minuto, è
  trascurabile per il moto proprio). Cerchio di ricerca centrato sulla
  posizione del bersaglio con raggio `crossmatch_radius + |μ| · Δt_max`, dove
  Δt_max è la distanza in anni dall'epoca del bersaglio all'estremo più
  lontano delle osservazioni 2MASS (**1997-06-01 – 2001-03-01**: «giugno 1997
  – febbraio 2001», 2MASS Explanatory Supplement §I.1, letto il 2026-11-07);
  poi ogni riga si confronta con il bersaglio portato al suo `jdate` ed entra
  se la separazione è ≤ `crossmatch_radius`.
- Esito come per Gaia: una sorgente → usata con `PROFILE_POSITIONAL_MATCH`
  (raggio, separazione, epoche); più sorgenti → nessuna scelta, elenco e
  `PROFILE_POSITIONAL_MATCH` (`several_candidates`); nessuna → «nessuna
  sorgente entro il raggio». Senza moto proprio: nessuna propagazione,
  `PROFILE_NO_PROPER_MOTION`.

**Serie VizieR** (D20-5): `vizier_photometry` del 14 con centro = posizione
del bersaglio **a J2000** (la posizione SIMBAD; coordinate scritte a un'altra
epoca portate a J2000 con il moto proprio SIMBAD se noto, altrimenti lasciate
dove sono con `PROFILE_NO_PROPER_MOTION`) e raggio **`VIZIER_SED_RADIUS` =
2″**. Avviso `SED_HIGH_PROPER_MOTION` quando |μ| · 16 anni (J2000 → J2016,
epoca di Gaia) ≥ raggio: i punti di cataloghi con epoche lontane da J2000
possono mancare. CDS giù → l'errore del 14 resta **nella sola sezione**
(stato `partial`), il resto della fotometria è presente.

**Risultato della sezione.** `values`: per ogni punto una `ProfileValue`
letta (magnitudine o flusso come dato dal catalogo, con errore, banda,
sistema, qualità) e, se convertita, una calcolata (`flux_nu`, metodo
`computed` con formula, punto zero e fonte del `20`). `details`: `points`
(tabella del `20`, una riga per punto con provenienza, motivi di esclusione
dal grafico), `vizier` (serie separata, così come data da VizieR),
`zero_points` (voci di `ZERO_POINTS` usate), `plot_png` (grafico Fν–λ del
`20` come immagine PNG in base64, **esclusa dall'impronta di rete** come i
tempi: è disegnata dai valori, che restano nell'impronta). Stato: `done`;
`partial` se un servizio non ha risposto e ci sono punti; `error` se nessun
punto ed errori; `not_applicable` senza punti né errori.

**Codice** (`object_profile.py`): `profile_photometry`, `designation_position`,
`is_planet_path`; costanti `ALLWISE_EPOCH`, `TMASS_OBSERVATIONS`,
`DESIGNATION_RADIUS`; la SED è di `astrotwo.analysis.photometry` (20 §7).

### 3.12 Precisazioni dello sprint C4 (parallelismo e Annulla, 2026-11-07)

Scritte prima del codice dello sprint C4, dalle decisioni del proprietario del
2026-11-07 (D25-8 con la serie VizieR, D25-15); le scelte minori sono raccolte
in **D25-16** (da confermare). Le sezioni **Immagini** e **Pianeti** sono in
§3.13 (stesso sprint) e usano i tempi HiPS 30 s ed Exoplanet 30 s della
tabella.

**Tempi massimi per servizio** (`SERVICE_TIME_LIMITS`, D25-8 e D25-15):

| Servizio | Voce del 14 | Tempo massimo |
|---|---|---|
| SIMBAD | `cds-simbad-tap` (con il mirror di Harvard) | 15 s |
| Archivio Gaia (ESA) | `esa-gaia-tap` | 30 s |
| IRSA (2MASS, AllWISE) | `nasa-irsa-tap` | 60 s |
| NASA Exoplanet Archive | `nasa-exoplanet-tap` | 30 s |
| HiPS (miniature, sezione Immagini) | survey del 12 | 30 s |
| Serie SED di VizieR | `vizier_photometry` del 14 | 30 s (D25-15) |

**Obiettivo complessivo** `PROFILE_TARGET_TIME` = 60 s: è un obiettivo, non un
limite; il tempo totale (`elapsed` del profilo) è scritto nel risultato fuori
dall'impronta di rete, come i tempi delle sezioni.

**Regole.**
1. **Bersaglio prima.** La risoluzione del bersaglio (§3.10) precede le
   sezioni, che ne dipendono tutte. Le sue richieste a SIMBAD hanno il tempo
   di lettura di SIMBAD (15 s per richiesta); non ha un limite complessivo
   proprio, perché il ripiego su `resolve_name` (NED) dopo SIMBAD giù (§3.10)
   deve poter avvenire. È annullabile (regola 6).
2. **Sezioni insieme.** Poi tutte le sezioni richieste partono **insieme**
   (stesso istante di partenza, `sections_started`). La catena degli
   identificativi è condivisa: l'esito per Gaia DR3 si calcola **una volta**
   e serve a tutte le sezioni; 2MASS, AllWISE ed Exoplanet Archive partono
   appena è noto Gaia, in parallelo tra loro. Ogni sezione aspetta solo gli
   esiti che le servono (Astrometria: Gaia; Fotometria: Gaia, 2MASS,
   AllWISE; Identità: tutti e quattro). Nella fotometria le quattro richieste
   (Gaia, 2MASS, AllWISE, VizieR) partono insieme.
3. **Al più 4 richieste di rete contemporanee** (`MAX_CONCURRENT_REQUESTS`
   = 4) in tutto il profilo: un semaforo comune attorno a ogni chiamata ai
   servizi del livello 1 (`simbad_object`, `tap_query`, `vizier_photometry`,
   `resolve_name`). Una chiamata `simbad_object` (che fa le sue richieste una
   dopo l'altra, 14) occupa un solo posto.
4. **Tempo massimo di una richiesta:** il tempo di connessione e di lettura
   di ogni richiesta è il minimo tra quello del chiamante (`timeouts`, default
   del 04) e il tempo massimo del suo servizio (tabella sopra).
5. **Tempo massimo di una sezione** = il più grande tra i tempi dei servizi
   che la sezione può interrogare, contato da `sections_started`
   (`SECTION_SERVICES`): Identità — SIMBAD, Gaia, IRSA, Exoplanet → **60 s**;
   Astrometria — Gaia → **30 s**; Fotometria — Gaia, IRSA, VizieR → **60 s**;
   Immagini — HiPS → **30 s**; Pianeti — Exoplanet → **30 s** (§3.13; il
   tempo comprende l'attesa dell'esito di Gaia della catena).
   Una sezione non arrivata entro il suo tempo passa a `error` con
   `PROFILE_SECTION_TIMEOUT` (sezione, tempo massimo, servizi), è annunciata
   con `on_section` e le sue richieste ancora in corso, quando finiscono, sono
   scartate; le altre sezioni continuano (regola c).
6. **`on_section(section)`** è chiamato **una volta per sezione**, nel thread
   di chi ha chiamato `build_profile` (mai da un thread di lavoro), nell'ordine
   in cui le sezioni finiscono (arrivate, in errore, scadute). Un errore di una
   sezione non ferma le altre (T10).
7. **Annulla** (`cancel`, controllato almeno ogni 0,05 s): le sezioni già
   arrivate **restano** come sono; quelle in corso passano allo stato
   **`cancelled`** (nuovo stato di sezione) e sono annunciate con
   `on_section`; nessuna nuova richiesta parte (il semaforo non concede più
   posti e le sezioni controllano l'annullamento tra le richieste); una
   richiesta HTTP già partita non si interrompe (come in sincrona nel 05), la
   sua risposta si scarta. `build_profile` restituisce subito l'`ObjectProfile`
   con `cancelled = True`; se l'annullamento arriva prima che il bersaglio sia
   risolto non c'è nessuna sezione e restituisce `None`.
8. **Comando:** `object.profile` annullato termina con esito `cancelled` ed
   errore **`COMMAND_CANCELLED`** (05 §10.1). Con almeno una sezione arrivata
   la ragione è **`partial`**: il risultato **conserva** il profilo (sezioni
   arrivate e sezioni `cancelled`), lo stato del lavoro non cambia (il comando
   è di sola lettura) e `simbad_id` si scrive nel comando registrato; senza
   sezioni arrivate la ragione resta `discarded` (05). L'avanzamento nella
   barra di stato è «passo k di n» con una sezione per passo
   (`ProgressReport`, testo `object_profile/<sezione>`), e **Annulla della
   barra di stato** (40, `CancelToken`) è quello degli altri comandi: nessuna
   modifica all'interfaccia.
9. **Cache da più thread:** la `SharedCache` del 04 è legata al thread che la
   apre (connessione `sqlite3`); il profilo usa **un'istanza per thread
   sulla stessa cartella** (come la `ThreadCache` del 40) quando riceve una
   `SharedCache`, e passa invariato un oggetto che lo gestisce già.
10. **Un thread alla volta sulla CPU** (turno `cpu_turn`/`network_wait` del
   14, §7): i thread del profilo, e il thread di chi chiama quando elabora gli
   arrivi e chiama `on_section`, lavorano solo con il turno; lo lasciano
   durante l'attesa delle risposte HTTP, del semaforo e degli esiti degli
   altri thread. Le richieste restano parallele (al più 4); la lettura dei
   VOTable, le unità di Astropy e il grafico di matplotlib (non sicuri tra
   thread) non girano mai insieme. Motivo verificato il 2026-11-07 nei test
   (14 §7: unità `'electron'.s**-1` di Gaia mal interpretata con le letture in
   parallelo).

**Codice** (`object_profile.py`): costanti `MAX_CONCURRENT_REQUESTS`,
`SERVICE_TIME_LIMITS`, `SECTION_SERVICES`, `PROFILE_TARGET_TIME`; `build_profile`
con il pianificatore (pool di thread, semaforo, scadenze, annullamento);
`ObjectProfile.cancelled` ed `ObjectProfile.elapsed`.

### 3.13 Precisazioni dello sprint C4: Immagini e Pianeti (2026-11-07)

Scritte prima del codice; scelte minori in **D25-17** (da confermare).
`sections` si allarga con `images` e `planets` (D25-13 (5), stessa
versione del comando); ordine del profilo: Identità, Immagini, Astrometria,
Fotometria, Pianeti (§3.4).

**Immagini** (`profile_images`, D25-5).
- Survey (`IMAGE_SURVEYS`): `CDS/P/DSS2/color`, `CDS/P/2MASS/color` e
  `CDS/P/allWISE/color`. **AllWISE colore entra** perché il mirror ESASky è
  stato **verificato il 2026-11-07 con richieste reali** con la regola del
  12 (elenco ufficiale, `properties` confrontato, tile scaricati; anche IRSA,
  stessi SHA-256; CDS giù, principale non confrontabile): esito scritto nel
  registro e nella tabella `MIRROR_FALLBACKS` del 12.
- Per ogni survey, insieme agli altri (§3.12): `add_hips` (MocServer, poi i
  mirror) e **`hips_thumbnail`** del 12 (TAN, campo `thumbnail_fov` = 5′,
  `thumbnail_size` = 256 pixel; stesso codice della vista, senza OpenGL, con
  i mirror di D12-9). Ogni chiamata occupa un posto del semaforo.
- **Centro all'epoca della survey quando nota:** epoca = punto medio di
  `t_min`/`t_max` del `properties` (MJD, scala non dichiarata: UTC, scritta)
  **solo se le osservazioni durano al più un anno** (`SURVEY_EPOCH_MAX_SPAN`
  del 12): oggi AllWISE (MJD 55378–55414 → 2010,545); DSS2 (1974–1998) e
  2MASS (1997–2001) non hanno un'epoca. Con l'epoca e il moto proprio SIMBAD
  la posizione è portata all'epoca con `propagate_position` (come §3.10);
  altrimenti il centro è la **posizione SIMBAD J2000** (o le coordinate
  scritte), **dichiarato** nella miniatura (`center_note`), e senza moto
  proprio `PROFILE_NO_PROPER_MOTION`.
- Ogni miniatura nel risultato (`details.thumbnails`): survey, titolo,
  **server reali** dei tile, ordine HEALPix, campo, dimensione, WCS (testo
  FITS), centro con epoca e nota, provenienza dei tile, tile assenti,
  **crediti** dichiarati dal survey (`obs_title`, `obs_ack`,
  `obs_copyright`, `obs_copyright_url`) e il PNG (nord in alto) in base64,
  **fuori dall'impronta di rete** come il grafico della SED.
- **CDS già giù nella sessione (D25-18, decisione del proprietario del
  2026-11-08):** se nella sessione dell'app il CDS risulta già giù —
  MocServer già non raggiungibile una volta, survey HiPS già passato da un
  server di Strasburgo a un mirror, o SIMBAD già sul mirror di Harvard (14) —
  le miniature **non interrogano di nuovo il MocServer** e aprono subito il
  survey dai mirror verificati (`MIRROR_FALLBACKS`), con l'avviso dichiarato
  `HIPS_MIRROR_FALLBACK` ragione `cds_down` (prova: `mocserver`,
  `hips_failover`, `simbad_failover`). Opzione `cds_down_shortcut` di
  `add_hips` del 12, attivata solo dal profilo; con «Riesegui con dati
  aggiornati» (`refresh`) si riprova il MocServer. L'avviso, legato
  all'esecuzione, resta fuori dall'impronta di rete come gli altri avvisi di
  ripiego. Misura del 2026-11-08 (CDS giù): miniature 13,6 s nel primo profilo
  della sessione, poi 2,6–4,6 s.
- Survey irraggiungibile su tutti i server: **miniatura mancante** con
  l'errore del 12 (`NET_TIMEOUT` `hips_servers`) nella sezione, le altre
  presenti (stato `partial`; `error` se nessuna).

**Pianeti** (`profile_planets`, D25-3).
- Dall'esito Exoplanet della catena (§3.10): ospite trovato per
  `gaia_dr3_id` → `WHERE gaia_dr3_id = 'Gaia DR3 <source_id>'`; trovato per
  `hostname` → `WHERE hostname = '<ospite>'`; tabella **`pscomppars`**,
  ordine `pl_name`. Nessun ospite: sezione **`done`** con «nessun pianeta
  nell'archivio» (non è un errore) e nessuna richiesta.
- Per ogni pianeta: `pl_name`, `pl_letter`, `discoverymethod`, `disc_year`
  (letti) e i parametri **periodo** (`pl_orbper`), **semiasse**
  (`pl_orbsmax`), **eccentricità** (`pl_orbeccen`), **massa** (`pl_bmasse`
  con `pl_bmassprov`, che dice se è la massa, `M sin i` o una stima da
  relazione massa-raggio), **raggio** (`pl_rade`), **temperatura di
  equilibrio** (`pl_eqt`), ciascuno con **errore superiore** (`…err1`) e
  **inferiore** (`…err2`, così come dato, negativo), indicatore di limite
  (`…lim`: 1 limite superiore, −1 inferiore, 0 misura; letto e scritto) e
  **riferimento per parametro** (`…_reflink`).
- **Unità** (`PLANET_PARAMETERS`): quelle dichiarate dall'archivio nel suo
  `TAP_SCHEMA.columns` (letto il 2026-11-07): giorni, au, adimensionale,
  masse terrestri, raggi terrestri, K. L'archivio non dichiara l'unità di
  alcune colonne (`pl_orbsmax`, gli errori di `pl_bmasse`): si usa l'unità
  che lo stesso schema dichiara per le altre colonne della stessa grandezza
  (`pl_orbsmaxerr1` au, `pl_bmasse` masse terrestri), scritto qui.
- **`*_reflink` è testo esterno (HTML):** si estraggono solo il testo
  visibile (senza tag, entità decodificate) e, se il collegamento è di ADS
  (`adsabs.harvard.edu`), l'URL e il **bibcode** (`/abs/<bibcode>/`); un
  collegamento non ADS non si conserva; nulla viene eseguito (T16).
- Avviso **`PROFILE_PLANETS_COMPOSITE`** con il numero dei pianeti e dei
  riferimenti distinti: i parametri di `pscomppars` possono venire da lavori
  diversi (D25-3).
- Valori: una `ProfileValue` letta per parametro e pianeta (grandezza
  `<pl_name> <parametro>`), con `error_upper`/`error_lower` (nuovi campi,
  così come dati) e il riferimento; dettagli in `details.planets`.

**Codice:** `profile_images`, `profile_planets`, costanti `IMAGE_SURVEYS`,
`DEFAULT_THUMBNAIL_FOV`, `DEFAULT_THUMBNAIL_SIZE`, `PLANET_PARAMETERS`,
`parse_reflink`; nel 12 `hips_thumbnail`.

### 3.14 Pianeti senza attendere Gaia (D25-17 (10), sprint C5, 2026-11-08)

Decisione del proprietario del 2026-11-08: se l'archivio Gaia non risponde,
o il bersaglio non ha `Gaia DR3` tra gli identificativi SIMBAD, la sezione
Pianeti cerca **subito** l'ospite per `hostname`, senza aspettare la catena
di Gaia; se poi arriva un `gaia_dr3_id` che dà un risultato diverso, avviso
dichiarato.

- **Quando** (`exoplanet_host_early`): SIMBAD ha risposto, i suoi
  identificativi **non** contengono `Gaia DR3 …` e ci sono identificativi
  da confrontare con `hostname`. Con `Gaia DR3` in SIMBAD l'esito di Gaia
  della catena è immediato (nessuna richiesta all'archivio, §3.10): la
  catena resta quella di §3.10 (prima `gaia_dr3_id`, poi `hostname`) e
  l'archivio Gaia giù non la ferma. Il caso «archivio Gaia giù» che faceva
  attendere i Pianeti è quindi sempre quello senza `Gaia DR3` in SIMBAD
  (passo per posizione su Gaia, Vega il 2026-11-08). SIMBAD giù: nessun
  identificativo da confrontare, catena come prima.
- **Come** (`build_profile`): la ricerca per `hostname` (stessa richiesta
  di §3.10, `_exoplanet_by_hostname`) parte con le altre all'inizio delle
  sezioni; la sezione Pianeti usa il suo esito (`profile_planets` con
  `WHERE hostname = …`, come in §3.13). In parallelo, quando l'esito di Gaia
  arriva, **`check_exoplanet_host`** fa la richiesta per `gaia_dr3_id` se
  la catena ha trovato un `source_id` (per posizione):
  - nessuna riga, o **lo stesso ospite**: resta l'esito per `hostname`
    (nella catena normale `hostname` è il secondo passo dopo `gaia_dr3_id`
    senza righe, quindi l'esito è lo stesso); stesso ospite → nota
    «confermato da gaia_dr3_id»;
  - **ospite diverso**, o ospite trovato **solo** per `gaia_dr3_id`:
    l'esito per `hostname` resta quello usato dai Pianeti (nessuna scelta
    silenziosa: non si cambia l'ospite dopo che la sezione è arrivata),
    l'altro ospite è in `conflict` (`hostname`, `gaia_dr3_id`, `by_gaia`)
    e c'è l'avviso **`PROFILE_PLANET_HOST_MISMATCH`** (ragioni `different`
    e `only_gaia`, con i due ospiti e il `gaia_dr3_id`);
  - richiesta per `gaia_dr3_id` non riuscita: resta l'esito per `hostname`,
    con l'errore del servizio nell'esito della catena e la nota «verifica
    con gaia_dr3_id non riuscita»; l'errore dell'archivio Gaia, se c'è, è
    già nell'Identità (§3.10).
- **Dove si vede l'avviso:** nell'**Identità** (che aspetta sempre tutta
  la catena, §3.12 regola 2, e mostra i conflitti della catena) e tra gli
  avvisi del profilo (`ObjectProfile.warnings`, quindi del comando). Se
  l'Identità non è tra le sezioni richieste, la verifica entra nel profilo
  **solo se è finita** quando l'ultima sezione arriva; altrimenti l'esito
  della catena per l'Exoplanet Archive è quello per `hostname` (scelta
  minore, D25-19 (1)).
- **Test:** T25 (§12): Vega con l'archivio Gaia fermo, Pianeti arrivati in
  meno di 2 s (non 30 s) con la sola richiesta per `hostname`; ospite
  trovato solo dal `gaia_dr3_id` arrivato dopo → avviso dichiarato.

**Codice** (`object_profile.py`): `exoplanet_host_early`,
`check_exoplanet_host`, `_exoplanet_by_gaia`, `_exoplanet_by_hostname`
(la catena di §3.10 resta `_exoplanet_host`, ora composta dalle due).

### 3.15 Esportazione, SED come catalogo e SAMP (sprint C6, 2026-11-08)

Precisa §3.7 (D25-6, decisa il 2026-11-07) per lo sprint C6 (brief del
proprietario del 2026-11-08). Le scelte minori sono in **D25-20** (§13), da
confermare. L'interfaccia (pulsanti della scheda) è nel `43` §3.10.

**Da dove vengono i dati (regola d'oro n. 1).** Ogni file esportato si
costruisce **dalla forma JSON del risultato** di uno o più comandi
`object.profile` già eseguiti (la stessa che mostra la finestra Profili),
mai rifacendo richieste né ricalcolando valori: numeri, unità, errori,
provenienza e PNG (miniature, grafico) sono quelli del risultato registrato.
Una scheda può avere sezioni di più comandi («Riprova questa sezione», `43`
§3.6): l'elenco **`commands`** (numeri `#n` della cronologia) dice quali,
nell'ordine; il primo è il profilo di base, ogni comando successivo
**sostituisce le sezioni che contiene** (`merge_profile_results`, §7.1), e
ogni sezione porta il numero del comando che l'ha prodotta (`command_id`).
Bersaglio, catena degli identificativi e avvisi del profilo vengono dal
primo comando.

**Comando `object.export`** (versione 1, classe `application`, eseguito
dall'interfaccia: `bound_by = 43`, perché la cronologia è della finestra
principale; definito in `command_specs()` di questo modulo). Parametri:
`commands` (elenco di interi ≥ 1, almeno uno), `format` (`ecsv`, `pdf`,
`sed_png`, `sed_votable`), `path` (percorso assoluto del file da scrivere),
`language` (`en`, `it`: lingua delle intestazioni del PDF, default `en`;
l'interfaccia passa la lingua dell'app). Come `view.export_png` del 41 è un
comando registrato in cronologia, **rieseguibile** con Riesegui del 40
(riscrive lo stesso file dagli stessi risultati registrati: stesso
contenuto, byte per byte) e, come ogni comando `application`, **non
rieseguito alla riapertura di una sessione** (scrivere file alla riapertura
non è un'azione chiesta dall'utente). Non usa la rete, non crea livelli,
non è esposto all'IA (classe `application`, 32 §3.3). Controlli prima di
scrivere (`PROFILE_EXPORT_INVALID`, §10): ogni numero esiste in cronologia
(`command_missing`), è un `object.profile` (`not_profile`) e ha un profilo
nel risultato — esito `ok` o `cancelled` `partial` (`no_profile`);
percorso assoluto con l'estensione del formato (`.ecsv`, `.pdf`, `.png`,
`.xml` o `.vot`; `extension`), cartella esistente e scrivibile
(`folder_unwritable`), non una cartella (`is_directory`); per `sed_png` e
`sed_votable` serve la sezione Fotometria con almeno un punto (`no_sed`).
Un file esistente si sovrascrive (la conferma è del dialogo di salvataggio
del 43). Errore di scrittura (disco pieno, permessi) → `PROFILE_EXPORT_FAILED`
con il percorso e il motivo, nessun file a metà (scrittura in un file
temporaneo nella stessa cartella e rinomina). Risultato: `path`, `format`,
`commands`, `sha256` e dimensione del file scritto, `rows` (ECSV, VOTable)
o `pages` (PDF).

**1. ECSV dei valori con provenienza** (`format = ecsv`): una riga per ogni
`ProfileValue` delle sezioni, nell'ordine fisso delle sezioni (Identità,
Immagini, Astrometria e distanza, Fotometria, Pianeti) e dei valori nel
risultato, più una riga per ogni riga della serie VizieR (quando c'è:
grandezza `VizieR SED <filtro> flux_nu`, metodo `read`, valore e errore in
Jy così come dati da VizieR, `table` = `_tabname`, frequenza nella nota).
Colonne (D25-20 (3)):

| Colonna | Tipo | Contenuto |
|---|---|---|
| `section` | testo | nome della sezione (`identity`, `astrometry`, …) |
| `quantity` | testo | grandezza come nel risultato (es. `parallax`, `2MASS J flux_nu`, `TRAPPIST-1 b period`) |
| `value` | `float64` | il valore numerico, **vuoto (mascherato)** per testi, booleani e interi che un `float64` non rappresenta esattamente (es. `source_id`) |
| `value_text` | testo | il valore esattamente come nel risultato: `repr` del `float64` (rappresentazione più corta), intero in cifre, testo, `true`/`false` |
| `unit` | testo | unità del valore come nel risultato (vuota se senza unità) |
| `error`, `error_lower`, `error_upper` | `float64` | errore simmetrico, oppure inferiore e superiore così come dati (pianeti), nell'unità del valore; vuoti se assenti |
| `interval_lower`, `interval_upper`, `interval_kind` | `float64`, testo | intervallo dichiarato (Bailer-Jones 16°–84° percentile, 1/(ϖ ± σ)) |
| `band`, `system` | testo | per i valori della fotometria: banda e sistema del punto della SED (letti da `details.points` per etichetta `<catalogo> <banda>`), altrimenti vuoti |
| `upper_limit` | booleano | punto della SED che è un limite superiore (`SED_UPPER_LIMIT`): **mai una misura** (D43-9) |
| `method`, `formula` | testo | `read` o `computed` e la formula scritta dal motore |
| `service`, `server`, `table`, `query` | testo | servizio, URL del server che ha risposto davvero (anche un mirror), tabella, interrogazione ADQL |
| `identifier`, `match` | testo | identificativo usato e tipo di incrocio (`simbad_identifier`, `official_crossmatch`, `position`) |
| `reference` | testo | riferimento bibliografico (bibcode) |
| `note` | testo | nota del valore |
| `retrieved_at` | testo | data della risposta, ISO 8601 UTC (DC1) |
| `from_cache` | testo | `true`, `false` o vuoto (sconosciuto) |
| `command_id` | intero | numero del comando `object.profile` che ha prodotto il valore |

Nell'intestazione ECSV (metadati YAML): `A2VERS` (versione di AstroTwo),
`A2KIND = object_profile`, il bersaglio come scritto, `main_id`, posizione
risolta con epoca e fonte, `commands`. Nessuna data di esportazione nel file
(così Riesegui riscrive lo stesso file; la data è nel risultato del comando,
05). La tabella si rilegge con `astropy.table.Table.read(..., format="ascii.ecsv")`.

**2. PDF della scheda** (`format = pdf`): disegnato con matplotlib
(`PdfPages`, backend PDF senza pyplot), **non** con `QPdfWriter` di Qt
(proposta di §8): il modulo resta di livello 2 senza dipendere
dall'interfaccia e il grafico della SED è lo stesso del 20 (D25-20 (1)).
Formato A4 verticale, **al più una pagina per sezione**, nell'ordine:
(1) **Identità e Immagini** (nome, tipo con la descrizione, tipo spettrale
con il bibcode, citazioni, posizione con epoca e fonte, identificativi per
catalogo — al più 8 per gruppo e 30 gruppi, oltre «… N in più: elenco
completo nella scheda» —, catena degli identificativi; a destra le
miniature dal PNG del risultato con survey, campo, centro con epoca,
server, `obs_copyright` e, per DSS, la prima frase del testo di STScI del
`01` §6.1); (2) **Astrometria e distanza** (tabella grandezza, valore,
errore, unità, note; distanza con il metodo scritto); (3) **Fotometria**
(grafico della SED del 20 in Fν contro λ con i limiti superiori come
frecce, D43-9, e la tabella dei punti: catalogo, banda, sistema, valore con
errore, qualità, λ, Fν con errore, nel grafico sì/no e motivo); (4)
**Pianeti** (una riga per pianeta: valori con errori `+a / −b` così come
dati, segno di limite); più una pagina finale **«Fonti e crediti»**
(crediti completi dei survey `obs_ack`, punti zero usati con la fonte,
elenco delle interrogazioni: servizio, server, tabella, data, cache,
comando). In fondo a ogni pagina, in nota, le fonti di quella sezione
(servizi, server, tabelle, date, cache, `#n`). Sezioni non presenti nella
scheda (non richieste) o senza valori: pagina con lo stato e i messaggi
(errore, annullata). Una tabella più lunga di quanto sta nella pagina si
tronca con la riga «… N righe in più: tabella completa nell'ECSV». Numeri
scritti con la rappresentazione più corta del `float64` del risultato (come
la finestra, D43-7): nessun arrotondamento, nessun ricalcolo. Testi esterni
(nomi SIMBAD, crediti, riferimenti) come testo semplice. Metadati del PDF:
titolo (`Profile of <main_id>`), `Creator` = `AstroTwo <versione>`, nessuna
data di creazione (stesso file a ogni Riesegui).

**3. PNG della SED** (`format = sed_png`): `plot_sed_rows` del 20 dalla
forma JSON dei punti e della serie VizieR, con i limiti superiori come
frecce (D43-9) e la riga dei crediti dei punti zero e dei servizi già scritta
dal 20; titolo = `main_id`. PNG senza metadati del programma che cambiano.

**4. Tabella dei punti della SED** (`format = sed_votable`, usata da
«Carica i punti SED come catalogo» e da «Invia con SAMP»): VOTable 1.4
scritto con `export_table` del 14 da una `CatalogTable` costruita da
`sed_catalog_table` (§7.1), una riga per punto della SED (anche i punti
rimasti in magnitudini) e una per riga della serie VizieR. Colonne (con UCD):
`ra`, `dec` (`pos.eq.ra;meta.main`, `pos.eq.dec;meta.main`: la posizione
del bersaglio risolto, uguale per tutte le righe, con il sistema e l'epoca
del risultato nel `COOSYS`; serve a mostrare il livello nel cielo, non è la
posizione della misura), `series` (`astrotwo` o `vizier`), `catalog`
(fonte: catalogo del punto o `_tabname` di VizieR), `band`
(`instr.bandpass`), `system`, `wavelength` (µm, `em.wl`), `flux_nu` (Jy,
`phot.flux.density`), `flux_nu_error` (Jy, `stat.error;phot.flux.density`),
`magnitude`, `magnitude_error` (mag, `phot.mag`), `quality`, `upper_limit`,
`in_plot`, `reasons` (codici `SED_*`), `zero_point`, `reference`,
`identifier`, `match`, `server`, `table`, `retrieved_at`, `from_cache`,
`command_id`. Nessun valore calcolato qui: λ e Fν sono quelli del risultato
(conversioni del 20, serie VizieR così come data). Provenienza della tabella
(14 §3, `A2ORIGIN`, `A2DATE`, `A2HIST`): «punti della SED del profilo di
<main_id>, comandi #n…», data della risposta più recente dei punti,
servizi interrogati. Corpo `celestial` (posizioni ICRS).

**«Carica i punti SED come catalogo»** (parità H17): due comandi registrati
in coda, senza logica propria dell'interfaccia: `object.export` con
`format = sed_votable` in un file della cartella dell'app
`~/Library/Application Support/AstroTwo/Profiles/` (mai cancellato da
AstroTwo: serve per riaprire la sessione, come i VOTable ricevuti con SAMP,
40 §3.12), poi, se è riuscito, **`catalog.open_file`** del 05 su quel file
(classe `session`, SHA-256 registrato, rieseguito alla riapertura). Il
livello si chiama come la tabella (`SED <main_id>`), con la provenienza del
VOTable. Nome del file: `<main_id ridotto a lettere, cifre, - e _>-sed-<n>.xml`
con `<n>` = ultimo numero di `commands` (un numero già usato si riscrive
con gli stessi dati).

**Comando `object.send_sed`** («Invia con SAMP»; versione 1, classe
`application`, eseguito dall'interfaccia: `bound_by = 40`, che possiede il
collegamento SAMP; definito in `command_specs()` di questo modulo).
Parametri: `commands` (come sopra) e `recipient` (identificativo pubblico di
un client SAMP, `null` = tutti gli iscritti; come `samp.send_table` del 05).
Manda la tabella dei punti della SED (`sed_catalog_table`) con
**`table.load.votable`** tramite `SampHub.send_table` del 14: chiamata
sincrona (`callAndWait`) a ogni destinatario con **60 s** di tempo di
risposta per le tabelle (`SAMP_TABLE_REPLY_TIMEOUT`, D40-9 (7)),
identificativo `astrotwo-<avvio>-sed<n>-<k>` (40 §3.12), nome
`SED <main_id>`. Esiti come `samp.send_table`: destinatari che hanno
accettato, rifiuti con `SAMP_NO_PEER` (`rejected`, `no_reply_table`),
non collegato → `SAMP_UNAVAILABLE` (`not_connected`). Stessi controlli di
`commands` e `no_sed` di `object.export`. Non rieseguito alla riapertura,
non esposto all'IA.

**Test:** T15 (ECSV), T26 (PDF e PNG), T27 (comando `object.export`:
controlli, Riesegui identico, sezioni da più comandi), T28 (tabella dei
punti, catalogo e SAMP), §12.

**Codice:** `src/astrotwo/analysis/profile_export.py` (stesso modulo 25,
file a parte per la lunghezza di `object_profile.py`): `results_from_history`,
`merge_profile_results`, `export_profile`, `profile_values_table`,
`sed_catalog_table`, `check_export_path`, `sed_catalog_path`,
`default_sed_folder`, `ProfileExportError`; specifiche `object.export` e
`object.send_sed` in `command_specs()` di `object_profile.py`. Il testo di
STScI per i survey DSS (`STSCI_DSS_TEXT`, 01 §6.1) è definito qui e la
finestra Profili lo importa (prima era nel 43). Test:
`tests/analysis/test_profile_export.py`.
**Correzione trovata scrivendo il PDF:** nella tabella dei punti l'errore
accanto a una magnitudine Gaia era quello del flusso in e⁻/s
(`phot_*_mean_flux_error`), perché Gaia non dà l'errore della magnitudine;
ora si mostra l'errore del valore mostrato (nessuno per la magnitudine
Gaia), nel PDF e nella finestra del 43.

## 4. Cosa NON fa

- Non sceglie mai in silenzio tra più candidati né tra identificativi in
  conflitto.
- Non calcola né stima con l'IA alcun valore; l'IA può solo chiedere il profilo.
- Non converte in flusso magnitudini senza punto zero documentato nel `20`.
- Non applica correzioni non dichiarate: niente zero point di parallasse
  (Lindegren et al. 2021) nella 1.0, niente estinzione, niente correzioni di colore WISE.
- Non sceglie l'oggetto «più citato» come il puntatore SIMBAD (lì è dichiarato,
  qui serve l'oggetto esatto).
- Non costruisce la SED (è del `20`) né le immagini HiPS (è del `12`).
- Non tratta oggetti estesi in modo specifico (galassie: la fotometria di
  catalogo può essere parziale; avviso `PROFILE_EXTENDED_OBJECT` se SIMBAD dà un
  tipo esteso, testi da definire).
- Non fa le estensioni di §3.8.

## 5. Livello e dipendenze

- **Livello:** 2 (analisi) — proposta (D25-1). Senza IA funziona completo.
- **Dipende da:** `02` (DC1, DC2, DC6), `04` (cache), `05` (comando e
  sessione), `10` (`resolve_name`, `propagate_position`, formato coordinate),
  `12` (miniature HiPS e mirror), `13` (lettura delle tabelle, `COOSYS`), `14`
  (`tap_query`, `cone_search`, `simbad_object` nuova, `vizier_photometry`,
  `ServerRegistry` con la nuova voce dell'Exoplanet Archive, mirror D14-14),
  `20` (punti della SED e conversioni).
- **Usato da:** `32`/`35` (strumento `object__profile`), `34` (verifica dei
  numeri), `40`/`41`/`42` (aperture), `43` o modulo d'interfaccia del profilo
  (D25-7).
- **Modifiche richieste a moduli `approvato`** (autorizzate, D25-12; in C4:
  `05` risultato parziale annullato, `14` turno della CPU, `20` costante AB):
  `14` — `simbad_object` (oggetto per identificativo: `basic`, `ident`,
  `flux`, con mirror), voce `nasa-exoplanet-tap`
  (`https://exoplanetarchive.ipac.caltech.edu/TAP`), raggio di
  `vizier_photometry`; `12` — funzione per una miniatura fuori dalla vista; `05` —
  comandi `object.profile` ed `object.profile_export`; `32` — strumento
  `object__profile`; `34` — riconoscere i numeri del profilo nel risultato
  ridotto; `40`, `41`, `42` — voci di menu; `03` — nota su H17.

## 6. Input e output

| Direzione | Nome | Tipo | Unità / formato | Note |
|---|---|---|---|---|
| in | `target` | testo, oppure coordinate, oppure riferimento a una riga | nome; coordinate con sistema ed epoca (DC2); `layer_id` + riga | uno solo dei tre |
| in | `sections` | elenco | `identity`, `images`, `astrometry`, `photometry`, `planets` (C2–C4) | default tutte |
| in | `match_radius` | angolo | arcsec, con unità | default 10″ (D25-9): candidati SIMBAD da coordinate |
| in | `crossmatch_radius` | angolo | arcsec, con unità | default 2″ (D25-9): incroci per posizione dopo la propagazione (§3.10) |
| in | `simbad_id` | testo | identificativo SIMBAD | facoltativo; scritto dal comando dopo la risoluzione (§3.10) |
| in | `thumbnail_fov`, `thumbnail_size`, `surveys` | angolo, intero, elenco di id HiPS | arcmin; pixel | default D25-5 |
| in | `refresh` | booleano | — | dati aggiornati dalla rete (B4) |
| out | `ObjectProfile` | struttura | §7 | bersaglio risolto, sezioni, avvisi, comando |
| out | `ProfileValue` | struttura | valore `float64` con `astropy.units`, errori, banda, sistema | provenienza obbligatoria |
| out | file esportati | ECSV, PDF, PNG, VOTable | §3.7, §3.15 | con fonti e crediti; comando `object.export` (dai risultati registrati, mai nuove richieste) |
| in | `commands` | elenco di interi | numeri `#n` della cronologia | `object.export`, `object.send_sed` (§3.15): profilo di base e sezioni riprovate |
| in | `format`, `path`, `language` | enum, testo, enum | `ecsv`, `pdf`, `sed_png`, `sed_votable`; percorso assoluto; `en`/`it` | `object.export` (§3.15) |
| out | tabella dei punti SED via SAMP | `table.load.votable` | VOTable 1.4 | `object.send_sed` (§3.15) |

## 7. Interfaccia pubblica

### 7.1 Questo modulo (`src/astrotwo/analysis/object_profile.py`; esportazione in `profile_export.py`, sprint C6)

- **`resolve_target(target, *, match_radius, ...)`** — dal nome, dalla riga o
  dalle coordinate all'oggetto: `ResolvedTarget` (oggetto SIMBAD con
  identificativi, posizione con epoca e fonte) oppure `TargetCandidates`
  (elenco per la scelta dell'utente).
- **`build_profile(target, *, sections, options, on_section, cancel)`** —
  esegue le sezioni in parallelo (§3.12: al più 4 richieste contemporanee,
  tempo massimo per sezione); chiama `on_section(section)` a ogni sezione
  terminata (arrivo progressivo, nel thread del chiamante) e, dallo sprint
  C5, `on_resolved(resolved)` una volta, a bersaglio risolto e prima delle
  sezioni (nel thread del chiamante; `object.profile` lo manda come evento
  `resolved` nel campo `detail` dell'avanzamento, con le sezioni come eventi
  `section`, per la finestra Profili del `43` §3.5); restituisce
  `ObjectProfile` (con `cancelled = True` se annullato dopo la risoluzione
  del bersaglio) o `None` (annullato prima).
- **`profile_identity`, `profile_images`, `profile_astrometry`,
  `profile_distance`, `profile_photometry`, `profile_planets`** — una funzione
  per sezione, ciascuna con lo stesso contratto (`ProfileSection`).
- **`cross_identify(resolved, catalog)`** — catena di §3.2/§3.3:
  `CrossIdentification` (identificativo, metodo `simbad_identifier` |
  `official_crossmatch` | `position`, separazione, epoche, candidati, conflitti).
- **`distance_from(astrometry, *, rules)`** — §3.4.4: `ProfileValue` con il metodo
  o il motivo dell'assenza.
- **`merge_profile_results(results)`** (sprint C6, §3.15) — da un elenco di
  `(command_id, values)` di comandi `object.profile` (primo = base) alla
  forma JSON della scheda: sezioni dei comandi successivi al posto di quelle
  del base, `command_id` in ogni sezione.
- **`export_profile(data, path, format, *, language="en")`** — scrive
  ECSV, PDF, PNG della SED o VOTable dei punti (§3.15) dalla forma JSON
  unita; restituisce `ProfileExport` (percorso, formato, SHA-256, byte,
  righe o pagine). Scrittura atomica (file temporaneo e rinomina).
- **`profile_values_table(data)`** — tabella Astropy dei valori con
  provenienza (colonne di §3.15, punto 1).
- **`sed_catalog_table(data)`** — `CatalogTable` del 13 con i punti della
  SED (§3.15, punto 4), per il VOTable, il livello catalogo e SAMP.
- **`check_export_path(path, format)`**, **`results_from_history(history,
  commands)`** — controlli di §3.15 (`PROFILE_EXPORT_INVALID`): percorso, e
  risultati dei comandi `object.profile` presi dalla cronologia del 05.
- Classi: **`ObjectProfile`** (bersaglio, sezioni, avvisi, `command_id`,
  date), **`ProfileSection`** (nome, stato, valori, errori, avvisi, tempo,
  servizi), **`ProfileValue`** (grandezza, valore, errori, unità, banda,
  sistema, metodo, `Provenance`), **`Provenance`** (servizio, server, tabella,
  interrogazione, identificativo, tipo di incrocio, riferimento, data, cache).

### 7.2 Nuove funzioni richieste ad altri moduli (descritte qui, da scrivere nei loro `.md`)

- `14` **`simbad_object(identifier, *, cache, refresh, timeouts)`** — righe di
  `basic` (incluse `sp_type`, `sp_bibcode`, `plx_*`, `pm*`, `coo_bibcode`,
  `nbref`), `ident` e `flux` (colonne verificate il 2026-11-07: `filter`,
  `flux`, `flux_err`, `system`, `qual`, `bibcode`) per un identificativo; con
  i server di `SIMBAD_SERVERS` (D14-14). Nessun risultato → `NAME_NOT_FOUND`
  (mai ripiego).
- `14` voce **`nasa-exoplanet-tap`** nell'elenco dei server (URL e pagina
  ufficiale da citare nella voce; servizio provato il 2026-11-07).
- `12` **miniatura**: campionamento di un survey su una griglia TAN centrata
  (campo, dimensione), con la stessa logica di `view_sampling`/`fill_view` e i
  mirror; restituisce immagine RGB o valori con WCS, crediti, server.

## 8. Librerie e standard di riferimento

| Libreria / standard | Uso nel modulo | Motivazione |
|---|---|---|
| Astropy (`units`, `coordinates`, `time`, `table`) | unità, propagazione (tramite il 10), ECSV | regola d'oro n. 4, già in uso |
| pyvo / TAP (IVOA) | interrogazioni tramite `tap_query` del 14 | già in uso, standard IVOA |
| ADQL 2.1 | interrogazioni a SIMBAD, Gaia, IRSA, Exoplanet Archive | standard IVOA |
| matplotlib (già dipendenza) | grafico della SED e PDF | proposta, D20-7 |
| matplotlib (`backend_pdf.PdfPages`) | PDF della scheda (§3.15) | D25-20 (1): stesso grafico del 20, nessuna dipendenza dall'interfaccia; al posto di `QPdfWriter` proposto qui nel C1 |
| Bailer-Jones et al. 2021 (AJ 161, 147) | distanze | D25-2 |

## 9. Regole e vincoli

- **Regola d'oro n. 1:** nessun numero dall'IA; ogni valore con provenienza; i
  valori calcolati (distanza da 1/ϖ, flussi) dicono la funzione e i dati usati.
- **Identificativo prima della posizione** (regola a); nessuna scelta
  silenziosa.
- **Epoca mai assunta** (DC2, D10-2): ogni posizione con epoca e fonte.
- Calcoli in `float64`, unità esplicite (DC6).
- **Testi esterni = dati** (32/35): nomi di SIMBAD, `*_reflink` dell'Exoplanet
  Archive (frammenti HTML: se ne estraggono solo URL ADS e testo, senza
  eseguire nulla), descrizioni dei servizi.
- Indipendenza delle sezioni: un errore resta nella sua sezione.
- Le soglie (10 % per 1/ϖ, raggi, RUWE) sono costanti con nome, scritte nel
  risultato.
- Le risposte dei servizi vanno nella cache comune (`04`) con origine e data.

## 10. Casi limite ed errori

Codici (testi en/it nel catalogo dei messaggi, D40-3; quelli delle sezioni di C2 scritti nello sprint C2, gli altri negli sprint che li usano):

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Nome sconosciuto a SIMBAD (server raggiungibile) | profilo non creato, suggerimento coordinate | `NAME_NOT_FOUND` (10/14) |
| SIMBAD giù su tutti i server | nome da `resolve_name` (NED), sezione Identità in errore, resto per posizione | `NET_TIMEOUT` `service_servers` + `PROFILE_NO_IDENTIFIERS` |
| Più candidati per coordinate | elenco da scegliere; da script errore | `PROFILE_AMBIGUOUS_TARGET` |
| Pianeti tra i candidati per coordinate (famiglia `Pl` di SIMBAD) | esclusi, avviso con numero e nomi (D25-13 (8)) | `PROFILE_PLANETS_EXCLUDED` |
| 2MASS o AllWISE: identificativo senza riga nel catalogo | punti assenti, avviso con l'identificativo (§3.11) | `PROFILE_NO_PHOTOMETRY` (`not_in_catalog`) |
| Moto proprio elevato per la serie VizieR | serie presente, avviso | `SED_HIGH_PROPER_MOTION` (20) |
| Identificativo SIMBAD e incrocio ufficiale in disaccordo | entrambi mostrati, nessuna scelta | `PROFILE_IDENTIFIER_CONFLICT` |
| Oggetto non in Gaia DR3 (Vega) | astrometria da SIMBAD con fonte | `PROFILE_NO_GAIA` |
| Soluzione Gaia a 2 parametri (Alcyone) | niente parallasse/moto proprio da Gaia | `PROFILE_GAIA_TWO_PARAMETER` |
| Parallasse assente, negativa o con errore relativo > 10 % | nessuna distanza, motivo | `PROFILE_NO_DISTANCE` |
| RUWE oltre la soglia | valore mostrato con avviso **solo con una soglia da fonte ufficiale verificata** (D25-11: oggi nessuna, avviso non emesso) | `PROFILE_GAIA_QUALITY` (non usato in C2) |
| Bersaglio assente, doppio (nome e coordinate insieme) o riga senza posizione | profilo non creato | `PROFILE_TARGET_INVALID` |
| Riesecuzione di un nome: SIMBAD dà un oggetto diverso da `simbad_id` registrato | profilo dell'oggetto di oggi, avviso con i due `main_id` | `PROFILE_TARGET_CHANGED` |
| Nessuna sorgente Gaia entro `crossmatch_radius`, o `source_id` di SIMBAD assente dall'archivio | astrometria da SIMBAD | `PROFILE_NO_GAIA` (`no_counterpart`, `not_in_archive`) |
| Incrocio per posizione | avviso con raggio, separazione, epoche | `PROFILE_POSITIONAL_MATCH` |
| Moto proprio sconosciuto per la propagazione | nessuna propagazione, avviso | `PROFILE_NO_PROPER_MOTION` |
| Archivio Gaia HTTP 503 (coda piena, visto il 2026-11-07) | nuovo tentativo come connessione (`02` §8), poi errore della sezione | `SERVICE_ERROR` / `NET_TIMEOUT` |
| CDS giù (SED di VizieR, nessun mirror) | serie VizieR assente, resto della fotometria presente | `SERVICE_ERROR` + `vizier_no_mirror` |
| Survey HiPS non disponibile su alcun server | miniatura mancante con messaggio | `NET_TIMEOUT` `hips_servers` |
| Tempo massimo di una sezione superato (§3.12 regola 5) | quella sezione in errore, le altre continuano; risposte tardive scartate | `PROFILE_SECTION_TIMEOUT` |
| Annulla (§3.12 regole 7–8) | sezioni in corso `cancelled`, arrivate conservate; nessuna nuova richiesta | `COMMAND_CANCELLED` (`partial` con sezioni arrivate, altrimenti `discarded`) |
| Nessun pianeta | sezione `done` con «nessun pianeta nell'archivio», non errore | — |
| Pianeti trovati (`pscomppars`) | parametri con il loro riferimento, avviso che possono venire da lavori diversi | `PROFILE_PLANETS_COMPOSITE` |
| Ospite trovato subito per `hostname` (§3.14) e poi diverso per `gaia_dr3_id` (o trovato solo per `gaia_dr3_id`) | pianeti dell'esito per `hostname`, l'altro ospite mostrato, nessuna scelta | `PROFILE_PLANET_HOST_MISMATCH` (`different`, `only_gaia`) |
| Epoca della survey non nota (osservazioni più lunghe di un anno) | miniatura centrata sulla posizione SIMBAD J2000, dichiarato | — (`center_note`) |
| Esportazione: numero di comando assente, non `object.profile`, senza profilo nel risultato; percorso non assoluto o con estensione diversa dal formato, cartella non scrivibile, percorso che è una cartella; SED vuota per `sed_png`/`sed_votable` (§3.15) | nessun file scritto | `PROFILE_EXPORT_INVALID` (`command_missing`, `not_profile`, `no_profile`, `not_absolute`, `extension`, `folder_unwritable`, `is_directory`, `no_sed`) |
| Errore di scrittura del file esportato (disco pieno, permessi) | nessun file a metà (temporaneo rimosso) | `PROFILE_EXPORT_FAILED` |
| «Invia con SAMP» senza collegamento o senza destinatari che accettano | come `samp.send_table` (40 §3.12) | `SAMP_UNAVAILABLE` (`not_connected`), `SAMP_NO_PEER` |

## 11. Esposizione all'IA

Strumento **`object__profile`** (nel `32`, da aggiungere): parametri `target`
(nome o coordinate con sistema ed epoca), `sections`; classe di rete, **con
conferma**. Restituisce un **riassunto** entro i limiti del 32 (≤ 50 righe,
20 kB): identità, astrometria, distanza con metodo, punti della SED in tabella,
pianeti; ogni numero esattamente come nel profilo, così che il `34` lo possa
verificare. L'IA non calcola né converte nulla; i testi di SIMBAD e
dell'Exoplanet Archive le arrivano marcati come dati esterni. Più candidati:
l'IA riceve l'elenco e chiede all'utente; non sceglie (regola a).

## 12. Test di accettazione

Verifiche dal vivo del 2026-11-07 (richieste reali, dettagli in
`panoramica.md`, Fase C): i valori sotto sono **osservati** quel giorno e
servono da risposte registrate per i test offline; i test di rete li
confrontano solo per identificativi e struttura, non per valore (i servizi
cambiano).

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Identità di 51 Peg | `resolve_target("51 Peg")` con SIMBAD simulato (risposta registrata da Harvard) | `main_id` `* 51 Peg`, `otype` `PM*`, `sp_type` `G2IV` (1989ApJS...71..245K), identificativi con `Gaia DR3 2835207319109249920`, `2MASS J22572795+2046077`, `HIP 113357`, `NAME Helvetios` | confronto con la risposta registrata |
| T2 | Catena 51 Peg | `cross_identify` per Gaia, 2MASS, AllWISE, Exoplanet | Gaia e 2MASS da SIMBAD; AllWISE da `allwise_best_neighbour` (`J225728.12+204608.6`, 0,238″) perché SIMBAD non ha `WISEA`; Exoplanet da `gaia_dr3_id` | metodo dichiarato per ciascuno |
| T3 | Alcyone (eta Tau), Gaia a 2 parametri | astrometria con risposta registrata (`source_id` 66714384142368256, `astrometric_params_solved` = 3) | niente parallasse/moto proprio Gaia, `PROFILE_GAIA_TWO_PARAMETER`; distanza da SIMBAD 8,09 ± 0,42 mas (2007A&A...474..653V): rapporto 19,3 ≥ 10 → 1/ϖ con metodo dichiarato | valore = `(1/(8.09*u.mas)).to(u.pc, u.parallax())` con Astropy |
| T4 | Vega senza Gaia | identificativi SIMBAD senza `Gaia DR3`; cerchio Gaia registrato (3 stelle a 30–36″, G 15,8–17,3) | nessuna sorgente Gaia attribuita, `PROFILE_NO_GAIA`; con `match_radius` 10″ nessun candidato | nessuna scelta silenziosa |
| T5 | Distanza Bailer-Jones | `distance_from` per 51 Peg con `external.gaiaedr3_distance` registrata | `r_med_geo` 15,514698 pc [15,494703; 15,533528], metodo e riferimento 2021AJ....161..147B | lettura, nessun calcolo |
| T6 | Soglia 1/ϖ | parallassi simulate con ϖ/σ = 9,9 e 10,0 e ϖ < 0 | nessuna distanza (`low_snr`), distanza, nessuna distanza (`negative_parallax`) | confronto |
| T7 | AllWISE per posizione con propagazione | Vega: posizione SIMBAD J2000 + moto proprio SIMBAD, epoca AllWISE MJD 55400,0 (verificata il 2026-11-07, §3.11), cerchio registrato con `J183656.51+384704.4` a ≈ 3,8″ dalla posizione J2000 | candidato trovato solo dopo la propagazione, `PROFILE_POSITIONAL_MATCH` con raggio, separazione ed epoche | separazione ricalcolata con Astropy |
| T8 | Pianeti TRAPPIST-1 | sezione pianeti con `pscomppars` registrata | 7 pianeti b–h, ognuno con periodo, massa ed errori e riferimento (Agol et al. 2021) | confronto |
| T9 | Nessun pianeta | Vega, eta Tau | sezione `done`, «nessun pianeta» | stato |
| T10 | Sezioni indipendenti | archivio Gaia simulato giù (503 ripetuti), CDS giù | astrometria in errore, identità/fotometria (2MASS, AllWISE)/pianeti presenti | stati delle sezioni |
| T11 | Arrivo progressivo | servizi simulati con ritardi diversi (Gaia lento, IRSA veloce, e il contrario) | `on_section` chiamato nell'ordine dei tempi, ogni sezione una volta, nel thread del chiamante | ordine |
| T21 | Al più 4 richieste contemporanee (§3.12) | servizi simulati che contano le richieste aperte nello stesso istante, con un ritardo | massimo osservato ≤ 4 e > 1 (le sezioni girano davvero insieme) | contatore del server simulato |
| T22 | Tempo massimo di una sezione | `SERVICE_TIME_LIMITS` ridotti nel test; archivio Gaia simulato più lento del suo tempo | Astrometria `error` con `PROFILE_SECTION_TIMEOUT` (sezione, tempo, servizi) prima della risposta; Identità presente | stati e tempi |
| T23 | Annulla (§3.12) | annullamento dopo l'arrivo della prima sezione, con le altre ferme su un servizio lento; poi `object.profile` annullato dal `CancelToken` | sezione arrivata conservata, le altre `cancelled`, `cancelled = True`, ritorno prima della risposta lenta, nessuna nuova richiesta dopo l'annullamento; comando con esito `cancelled`, `COMMAND_CANCELLED` `partial` con il profilo nel risultato; annullamento prima della risoluzione → `None` e `discarded` | stati, contatore delle richieste, sessione del 05 |
| T12 | Più candidati | coordinate tra due oggetti SIMBAD entro il raggio | `TargetCandidates` con 2 voci; da script `PROFILE_AMBIGUOUS_TARGET` | nessuna scelta |
| T18 | Pianeti esclusi dai candidati (D25-13 (8)) | coordinate di 51 Peg e di TRAPPIST-1 (risposte registrate con `otypedef.path`); coordinate di eta Tau | 51 Peg e TRAPPIST-1: un solo candidato (la stella), `PROFILE_PLANETS_EXCLUDED` con 1 e 8 nomi; eta Tau: `PROFILE_AMBIGUOUS_TARGET` con la stella e `GN 03.44.2` | nessuna scelta tra non pianeti |
| T19 | Sezione fotometria | 51 Peg, Vega, eta Tau, TRAPPIST-1 con risposte registrate (archivio Gaia, IRSA, SIMBAD) e CDS giù | punti Gaia/2MASS/AllWISE/SIMBAD con banda, sistema, errore, qualità e provenienza; eta Tau 2MASS J e Ks (`ph_qual` `D`, saturate) fuori dal grafico con il motivo; Vega 2MASS saturata ma con `ph_qual` `CBC`: nel grafico per la regola D20-4, `rd_flg` mostrato; AllWISE `U` (Vega W1–W2, TRAPPIST-1 W4) limiti superiori fuori dal grafico; serie VizieR in errore nella sola sezione (`partial`); grafico PNG presente | confronto con le risposte registrate |
| T20 | Passo per posizione di 2MASS | 2MASS senza identificativo da SIMBAD né dall'incrocio ufficiale, risposta registrata con `jdate` | sorgente trovata confrontando il bersaglio portato al `jdate` della riga, `PROFILE_POSITIONAL_MATCH` | separazione ricalcolata con Astropy |
| T24 | Miniature (§3.13) | 51 Peg con le risposte vere di ESASky registrate il 2026-11-07 (DSS2, 2MASS, AllWISE colore); un survey con tutti i server giù | tre miniature 256 × 256 con survey, server reale, ordine, campo, crediti; AllWISE centrata all'epoca 2010,545 con la propagazione, DSS2 e 2MASS alla posizione J2000 dichiarata; survey giù → miniatura mancante con `NET_TIMEOUT` `hips_servers`, sezione `partial` | confronto, propagazione ricalcolata con Astropy |
| T25 | Pianeti senza attendere Gaia (§3.14, D25-17 (10)) | Vega (senza `Gaia DR3` in SIMBAD) con l'archivio Gaia simulato fermo 3 s; poi Gaia per posizione che dà una sorgente sintetica il cui `gaia_dr3_id` ha un ospite nell'archivio | Pianeti arrivati prima della risposta di Gaia (< 2 s, non 30 s), `done`, «nessun pianeta», una sola richiesta (per `hostname`); nel secondo caso pianeti per `hostname` (nessuno), `PROFILE_PLANET_HOST_MISMATCH` `only_gaia` nell'Identità e tra gli avvisi del profilo | tempi, richieste, avvisi |
| T13 | Conflitto di identificativi | SIMBAD dà 2MASS X, l'incrocio Gaia dà 2MASS Y | entrambi, `PROFILE_IDENTIFIER_CONFLICT` | |
| T14 | Riproducibilità | `object.profile` registrato, rieseguito dalla sessione, poi con `refresh` | stesse richieste e stessi valori dalla cache; con `refresh` nuove richieste e `DATA_REFRESHED` | sessione del 05 |
| T15 | Esportazione ECSV (§3.15) | `export_profile` ECSV di 51 Peg e TRAPPIST-1 (risposte registrate); una serie VizieR sintetica | una riga per valore (più una per riga VizieR) con tutte le colonne di provenienza di §3.15; `value_text` uguale al valore del risultato (anche `source_id` intero esatto, `value` vuoto); errori `+a / −b` dei pianeti; banda e sistema dei punti; limite superiore di TRAPPIST-1 W4 con `upper_limit` vero; `command_id`; rilettura con `astropy.table` | ECSV valido, confronto con il risultato |
| T26 | PDF e PNG (§3.15) | `export_profile` PDF e `sed_png` di TRAPPIST-1; scheda con una sezione in errore | PDF A4 di 5 pagine (4 sezioni + fonti e crediti) leggibile, titolo nei metadati, nessuna data di creazione; pagina della sezione in errore con il messaggio; PNG leggibile; due esportazioni uguali byte per byte | lettura del PDF (`pypdf` se presente, altrimenti struttura del file) e del PNG, SHA-256 |
| T27 | Comando `object.export` (§3.15) | registro con `object.export` legato a una cronologia di prova: `object.profile` di 51 Peg, poi «Riprova» dell'astrometria; numeri sbagliati, comando non profilo, profilo in errore; percorsi sbagliati; Riesegui | file scritto con le sezioni del secondo comando al posto di quelle del primo (`command_id`); `PROFILE_EXPORT_INVALID` con ogni ragione, nessun file; Riesegui → stesso SHA-256; comando `application` in cronologia, non rieseguito alla riapertura | comando registrato, SHA-256 |
| T28 | Punti SED come catalogo e SAMP (§3.15) | `sed_catalog_table` di 51 Peg e TRAPPIST-1; `object.export` `sed_votable` poi `catalog.open_file`; `object.send_sed` con un hub e un client SAMP simulati (`tests/core/samp_fakes.py`) | una riga per punto con λ, Fν, errori, banda, fonte, `upper_limit`; livello catalogo con posizioni ICRS riconosciute dagli UCD e la provenienza; `table.load.votable` con chiamata sincrona e 60 s, tabella ricevuta uguale; senza collegamento `SAMP_UNAVAILABLE` | confronto con il risultato del profilo |
| T16 | Testi esterni | `*_reflink` con HTML | solo URL ADS e testo estratti; nessun tag eseguito; marcati esterni verso l'IA | |
| T17 | Rete (marcato `network`) | 3 oggetti veri | struttura e identificativi come T1–T9; tempo totale registrato (obiettivo 60 s) | non nel commit (`--no-network`) |

## 13. Decisioni aperte

Tutte le decisioni D25-1…D25-19 sono state **prese dal proprietario**
(D25-1…D25-15 il 2026-11-07: D25-1…D25-12 dopo il report dello sprint C1,
D25-13 dopo lo sprint C2, D25-14 e D25-15 dopo lo sprint C3; D25-16, D25-17
e D25-18 il 2026-11-08; D25-19 confermata il 2026-11-08 con il brief dello
sprint C6). Restano qui come registro. Aperta: **D25-20** (scelte minori
dello sprint C6, da confermare).

- **D25-1 — Numero, nome e livello del modulo — DECISA (2026-11-07):**
  `25-analisi-profilo-oggetto.md`, **livello 2**, codice in
  `src/astrotwo/analysis/object_profile.py` (come raccomandato: usa la SED del
  20, che è analisi). AM1 accettata.
- **D25-2 — Metodo della distanza — DECISA (2026-11-07):** come §3.4.4:
  Bailer-Jones et al. (2021) → 1/ϖ solo con ϖ/σ ≥ 10 (Gaia DR3 o, in
  mancanza, SIMBAD con la fonte) → nessuna distanza con il motivo. Nessuna riga
  `distance_gspphot`.
- **D25-3 — Tabella dei pianeti — DECISA (2026-11-07):** `pscomppars` con
  l'avviso che i parametri possono venire da lavori diversi (sprint C4).
- **D25-4 — Catena degli identificativi — DECISA (2026-11-07):** come §3.2:
  incroci ufficiali di Gaia (`tmass_psc_xsc_best_neighbour`,
  `allwise_best_neighbour`) usati come identificativi dichiarati
  (`official_crossmatch`); AllWISE per posizione con un cerchio piccolo e
  controllo della `designation` (sprint C3).
- **D25-5 — Miniature — DECISA (2026-11-07):** DSS2 colore e 2MASS colore;
  **AllWISE colore solo se il mirror ESASky viene verificato con richieste
  reali** (stessa regola dei mirror del 12), altrimenti AllWISE solo quando
  risponde il CDS. Campo 5′, 256 × 256 pixel, TAN centrata (sprint C4).
- **D25-6 — Esportazione — DECISA (2026-11-07):** ECSV dei valori con
  provenienza + PDF della scheda + PNG della SED (sprint C6, precisata in
  §3.15; scelte minori in D25-20).
- **D25-7 — Specifica dell'interfaccia — DECISA (2026-11-07), ribadita il
  2026-11-08:** nel nuovo `43-ui-profili.md` (template a 14 sezioni), scritto
  nello sprint C5 e aggiunto a `INDICE.md`.
- **D25-8 — Tempi — DECISA (2026-11-07):** obiettivo 60 s; tempo massimo per
  sezione SIMBAD 15 s, Gaia 30 s, IRSA 60 s, Exoplanet 30 s, HiPS 30 s e
  (D25-15) serie SED di VizieR 30 s; 4 richieste contemporanee (parallelismo
  nello sprint C4, §3.12; in C2–C3 le sezioni giravano una dopo l'altra).
- **D25-9 — Raggi — DECISA (2026-11-07):** 10″ per i candidati SIMBAD da
  coordinate; 2″ per gli incroci per posizione dopo la propagazione.
- **D25-10 — Zero point di parallasse — DECISA (2026-11-07):** non applicato
  nella 1.0, **dichiarato** nel risultato (nota del metodo 1/ϖ).
- **D25-11 — Indicatori di qualità di Gaia — DECISA (2026-11-07):** si
  mostrano `ruwe`, numero di parametri (da `astrometric_params_solved`),
  `duplicated_source`, `ipd_frac_multi_peak`. **La soglia RUWE 1,4 si mostra
  solo con una fonte ufficiale verificata** (documentazione Gaia o nota
  tecnica), citata; altrimenti il valore senza soglia. **Verifica del
  2026-11-07 (sprint C2):** la descrizione di `ruwe` nel modello dei dati di
  Gaia DR3 (§20.1.1 `gaia_source`) definisce il valore, dice che è nullo per le
  soluzioni a 2 parametri e cita Lindegren (2018) «Re-normalising the
  astrometric chi-square in Gaia DR2» (GAIA-C3-TN-LU-LL-124-01), **senza
  soglia**; neppure le sezioni 4.5.2 (proprietà dei dati astrometrici) e
  11.1.9 della documentazione EDR3 la danno; la nota tecnica LL-124 **non è
  stata raggiungibile** (pagina ESA 404, archivio dei documenti non
  disponibile). Quindi **nella 1.0 di oggi RUWE si mostra senza soglia** e
  l'avviso `PROFILE_GAIA_QUALITY` non si emette; la soglia entra solo dopo la
  lettura della nota tecnica (**da verificare**). `phot_variable_flag` si legge
  con la fotometria (`20`, sprint C3), non tra gli indicatori astrometrici.
- **D25-12 — Autorizzazioni per il codice — DECISA (2026-11-07), formula del
  proprietario:** «Il proprietario approva 20-analisi-fotometria.md (solo la
  parte SED) e 25-analisi-profilo-oggetto.md per la fase codice, e autorizza
  le modifiche ai file approvati 03, 05, 12, 14, 32, 34, 40, 41, 42
  limitatamente a quanto serve agli sprint C2–C6, con annotazione nel registro
  di ciascun file.»
- **D25-13 — Scelte minori dello sprint C2 — DECISA (proprietario, 2026-11-07).**
  Punti (1)–(7) **confermati** come scritti in §3.10: (1) parametri
  `crossmatch_radius` e `simbad_id` del comando; (2) raggio di ricerca dei
  candidati allargato dal moto proprio massimo noto (`PM_SEARCH_MAX`); (3) una
  riga di catalogo come bersaglio vale per posizione in C2 (riconoscimento
  degli identificativi delle righe con l'interfaccia, C5); (4) passo
  «posizione» della catena solo per Gaia DR3 in C2 (2MASS e AllWISE nello
  sprint C3, §3.11); (5) l'elenco `sections` del comando contiene solo le
  sezioni già scritte, allargato negli sprint successivi senza cambiare
  versione; (6) registrazione dei comandi dei livelli 2–4 da parte di chi
  costruisce il registro (05 §3.2); (7) astrometria di SIMBAD mostrata anche
  quando Gaia ha una soluzione a 2 parametri. (8) **Candidati da coordinate e
  pianeti — deciso:** per un bersaglio dato per coordinate gli oggetti SIMBAD
  della famiglia «Planet» (verificata sulla gerarchia ufficiale dei tipi di
  SIMBAD, `otypedef.path`) sono **esclusi** dai candidati in modo dichiarato,
  con avviso del numero e dei nomi degli esclusi (`PROFILE_PLANETS_EXCLUDED`);
  l'ambiguità tra oggetti non pianeti resta e si ferma con l'elenco
  (`PROFILE_AMBIGUOUS_TARGET`). Scritto in §3.10, test T12 e T18.
- **D25-14 — Scelte minori dello sprint C3 — DECISA (proprietario, 2026-11-07):
  confermata tutta** come scritta in §3.11: (1) 2MASS e AllWISE per
  designazione con il cerchio di 2″ attorno alla posizione scritta nella
  designazione (`DESIGNATION_RADIUS`); (2) epoca AllWISE MJD 55400,0 UTC per
  le posizioni stazionarie `ra`/`dec`; (3) 2MASS confrontato al `jdate` di
  ogni riga, scala trattata come UTC e dichiarata, raggio di ricerca allargato
  con il periodo delle osservazioni 2MASS; (4) passo per posizione di 2MASS e
  AllWISE dentro `cross_identify`, quindi mostrato anche nella sezione
  Identità; (5) centro della serie VizieR a J2000 e avviso
  `SED_HIGH_PROPER_MOTION` con |μ| · 16 anni ≥ 2″; (6) grafico come PNG in
  base64 nel risultato, fuori dall'impronta di rete; (7) senza riga nel
  catalogo per un identificativo noto: avviso `PROFILE_NO_PHOTOMETRY`, nessun
  passo per posizione.
- **D25-15 — Tempo massimo della serie SED di VizieR — DECISA (proprietario,
  2026-11-07):** 30 s, aggiunto alla tabella dei tempi di D25-8 (§3.12).
- **D25-17 — Scelte minori di Immagini e Pianeti (sprint C4) — DECISA
  (proprietario, 2026-11-08): punti (1)–(9) confermati, punto (10) deciso**
  (Pianeti subito per `hostname` senza attendere Gaia, avviso se poi
  `gaia_dr3_id` dà un risultato diverso; scritto in §3.14, test T25).
  Testo delle scelte, scritte in §3.13: (1) epoca della survey = punto medio di
  `t_min`/`t_max` solo se le osservazioni durano al più un anno, scala UTC
  dichiarata (oggi solo AllWISE); (2) PNG delle miniature in base64 nel
  risultato, fuori dall'impronta (circa 100–150 kB l'una nella sessione);
  (3) crediti = soli testi dichiarati dal survey (il testo di STScI per DSS
  del `01` §6.1 lo aggiunge l'interfaccia, C5); (4) unità dei parametri dei
  pianeti dal `TAP_SCHEMA` dell'archivio, con l'unità della stessa grandezza
  dove una colonna non la dichiara; (5) dai `*_reflink` solo testo, URL e
  bibcode di ADS; collegamenti non ADS non conservati; (6) errori dei
  pianeti come dati (`error_upper`, `error_lower` negativo) con l'indicatore
  di limite; (7) massa = `pl_bmasse` (masse terrestri) con `pl_bmassprov`,
  raggio = `pl_rade`; (8) ricerca dei pianeti con lo stesso criterio che ha
  trovato l'ospite (`gaia_dr3_id` o `hostname`); (9) `add_hips` e ogni
  miniatura occupano un posto del semaforo; con il CDS giù il primo profilo
  della sessione attende il timeout di connessione del MocServer, i successivi
  no (D25-18); (10) la sezione Pianeti attende l'esito di Gaia della catena:
  con l'archivio Gaia giù e senza `Gaia DR3` negli identificativi SIMBAD (Vega,
  2026-11-08) scade a 30 s (`PROFILE_SECTION_TIMEOUT`); proposta: in quel caso
  cercare subito l'ospite per `hostname`, senza attendere Gaia — **decisa
  così dal proprietario il 2026-11-08** (§3.14).
- **D25-18 — Miniature con il CDS già giù — DECISA (proprietario,
  2026-11-08):** quando nella sessione il CDS risulta già giù (ripiego già
  avvenuto o MocServer già scaduto una volta), le miniature non aspettano di
  nuovo il timeout del MocServer e vanno subito sui mirror verificati, con
  avviso dichiarato. Scritto in §3.13; test in `tests/core/test_hips_thumbnail.py`.
- **D25-16 — Scelte minori dello sprint C4 — DECISA (proprietario,
  2026-11-08): confermata tutta, punti (1)–(9).** Scritte in §3.12: (1) tempo massimo di una sezione = il più grande tra i
  tempi dei servizi che può interrogare (Identità 60 s, Astrometria 30 s,
  Fotometria 60 s), contato dalla partenza comune delle sezioni; (2) tempo
  massimo di ogni richiesta = minimo tra il timeout del chiamante e quello
  del servizio; (3) la risoluzione del bersaglio non ha un limite complessivo
  (solo 15 s per richiesta a SIMBAD), per non impedire il ripiego su NED;
  (4) l'obiettivo di 60 s è misurato e scritto (`elapsed`), non è un limite e
  non dà avvisi; (5) nuovo stato di sezione `cancelled`; il comando annullato
  con sezioni arrivate conserva il profilo nel risultato
  (`COMMAND_CANCELLED` `partial`, 05 §3.2), senza sezioni arrivate resta
  `discarded`; (6) una `simbad_object` (tre richieste in fila) occupa un solo
  posto dei 4; (7) una istanza della cache per thread sulla stessa cartella;
  (8) avanzamento «passo k di n» con una sezione per passo; (9) un thread alla
  volta sulla CPU con il turno del 14 (`cpu_turn`/`network_wait`), lasciato
  durante le attese di rete (regola 10, motivo verificato nei test).

- **D25-19 — Scelte minori dello sprint C5 (motore) — DECISA (proprietario,
  2026-11-08): confermate tutte.** Scritte in §3.14: (1) se l'Identità non è richiesta, la
  verifica dell'ospite per `gaia_dr3_id` entra nel profilo solo se finita
  quando arriva l'ultima sezione (il profilo non aspetta Gaia per lei);
  (2) con un ospite diverso i Pianeti restano quelli dell'esito per
  `hostname` (già mostrati), l'altro ospite è nel conflitto della catena e
  nell'avviso; (3) un ospite trovato per `hostname` e nessuna riga per
  `gaia_dr3_id` non dà avviso (è l'esito della catena normale).

- **D25-20 — Scelte minori dello sprint C6 (esportazione, SED come
  catalogo, SAMP) — da confermare (proprietario).** Scritte in §3.15.
  Raccomandazioni di Claude Code:
  (1) **PDF con matplotlib** (`PdfPages`) invece di `QPdfWriter` di Qt: il
  25 resta di livello 2 senza dipendere dall'interfaccia, il grafico è lo
  stesso del 20, si prova senza finestra; alternativa: `QPdfWriter` nel 43;
  (2) **i file si costruiscono dai risultati registrati** dei comandi
  `object.profile` indicati da `commands` (numeri `#n`, sezioni riprovate
  al posto di quelle del base), mai rifacendo le richieste; per questo
  `object.export` e `object.send_sed` sono comandi `application` eseguiti
  dall'interfaccia (che ha la cronologia), rieseguibili con Riesegui ma non
  alla riapertura di una sessione (come `view.export_png`); alternativa:
  comandi `session` che rifanno il profilo dalla cache;
  (3) **colonne dell'ECSV** come §3.15 punto 1: `value` numerico (vuoto per
  testi e interi non esatti in `float64`) più `value_text` esatto; banda e
  sistema dai punti della SED; una riga per riga della serie VizieR;
  (4) **«Carica i punti SED come catalogo» = `object.export`
  (`sed_votable`) in `~/Library/Application Support/AstroTwo/Profiles/` +
  `catalog.open_file`** del 05 (stesso schema dei VOTable ricevuti con
  SAMP): il livello è riaperto con la sessione dal file con SHA-256; righe
  con la posizione del bersaglio risolto (uguale per tutte, dichiarata) per
  vedere il livello nel cielo;
  (5) **«Invia con SAMP» = nuovo comando `object.send_sed`** (non un livello
  creato e poi mandato con `samp.send_table`): niente livello non chiesto;
  stesse regole del 14 (callAndWait, 60 s); destinatari dal sottomenu come
  le altre voci SAMP;
  (6) **PDF**: una pagina per sezione più «Fonti e crediti», fonti in nota a
  ogni pagina, tabelle troncate con rimando all'ECSV (identificativi: 8 per
  gruppo, 30 gruppi), intestazioni in inglese o italiano secondo la lingua
  dell'app (parametro `language` del comando);
  (7) **nessuna data di esportazione nei file** (ECSV, PDF, PNG): Riesegui
  riscrive lo stesso file byte per byte; la data è nel risultato del
  comando.

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-11-08 | Claude Code | **Sprint C6 (decisioni del proprietario del 2026-11-08, autorizzazione D25-12):** D25-19 confermata; `43-ui-profili.md` approvato (D43-9 decisa: limiti superiori come frecce ovunque, D20-9 (3) cambiata nel 20). Nuovo §3.15 (esportazione dai risultati registrati: comando `object.export` con ECSV dei valori con provenienza, PDF della scheda, PNG della SED e VOTable dei punti; «Carica i punti SED come catalogo» = `object.export` `sed_votable` + `catalog.open_file`; «Invia con SAMP» = comando `object.send_sed` con `table.load.votable`, callAndWait, 60 s); §3.7, §6, §7.1, §8 (PDF con matplotlib), §10 (`PROFILE_EXPORT_INVALID`, `PROFILE_EXPORT_FAILED`), §12 (T15 precisato, nuovi T26–T28); nuova D25-20 (scelte minori di C6, da confermare). |
| 2026-11-08 | Claude Code | **Sprint C5, interfaccia (istruzione del proprietario del 2026-11-08):** `build_profile` con `on_resolved`; `object.profile` manda nell'avanzamento (`ProgressReport.detail` del 05) l'evento `resolved` (passo 0) e ogni sezione arrivata (evento `section`, stessa forma JSON del risultato) per la finestra Profili (`43` §3.5); test T29 del 05 aggiornati. |
| 2026-11-08 | Claude Code | **Sprint C5 (decisioni del proprietario del 2026-11-08, autorizzazione D25-12):** D25-16 decisa (confermata tutta, (1)–(9)); D25-17 decisa ((1)–(9) confermati, (10) deciso: Pianeti subito per `hostname` senza attendere Gaia, avviso se poi `gaia_dr3_id` dà un risultato diverso); D25-7 ribadita (interfaccia in `43-ui-profili.md`, creato in bozza lo stesso giorno). Nuovo §3.14 (`exoplanet_host_early`, `check_exoplanet_host`, avviso `PROFILE_PLANET_HOST_MISMATCH` con ragioni `different` e `only_gaia`); §3.9 rimanda al `43`; §10 e §12 (T25); nuova D25-19 (scelte minori del motore in C5, da confermare). Codice e test in `object_profile.py` e `tests/analysis/test_object_profile_images_planets.py` (T25). |
| 2026-11-08 | Claude Code | **Sprint C4, chiusura:** D25-18 decisa dal proprietario (miniature subito sui mirror verificati se il CDS risulta già giù nella sessione, avviso `HIPS_MIRROR_FALLBACK` `cds_down`; §3.13, §13); D25-17 (10) aggiunto (Pianeti con Gaia giù); test T8, T9, T16, T24 in `tests/analysis/test_object_profile_images_planets.py`. |
| 2026-11-07 | Claude Code | **Sprint C4, Immagini e Pianeti (decisioni del proprietario del 2026-11-07):** nuovo §3.13 (miniature DSS2, 2MASS e AllWISE colore con `hips_thumbnail` del 12, centro all'epoca della survey quando nota, crediti dichiarati; **mirror ESASky di AllWISE colore verificato il 2026-11-07** con richieste reali — elenco ufficiale, `properties` uguale a quello di IRSA, stessi SHA-256 di due tile — quindi AllWISE entra; pianeti da `pscomppars` per `gaia_dr3_id` o `hostname`, errori e riferimento per parametro, `PROFILE_PLANETS_COMPOSITE`); §3.12 tempi di Immagini e Pianeti; §6, §10, §12 (T24); nuova D25-17. |
| 2026-11-07 | Claude Code | **Sprint C4 (decisioni del proprietario del 2026-11-07):** D25-14 decisa (confermata tutta); nuova D25-15 decisa (serie SED di VizieR 30 s, aggiunta a D25-8). Nuovo §3.12 (parallelismo: bersaglio prima, sezioni insieme con la catena degli identificativi condivisa, al più 4 richieste contemporanee, tempo massimo per servizio e per sezione con `PROFILE_SECTION_TIMEOUT`, `on_section` nel thread del chiamante, Annulla con le sezioni arrivate conservate e lo stato `cancelled`, `COMMAND_CANCELLED` `partial`, cache per thread, un thread alla volta sulla CPU con il turno del 14 — unità di Astropy non sicure tra thread, verificato nei test); §3.5, §3.10, §6, §7.1, §10 aggiornati; §12 T11 precisato, nuovi T21–T23; nuova D25-16 (scelte minori di C4, da confermare). |
| 2026-11-07 | Claude Code | **Sprint C3 (decisioni del proprietario del 2026-11-07):** D25-13 decisa: punti (1)–(7) confermati, punto (8) deciso (pianeti della famiglia `Pl` di SIMBAD esclusi dai candidati da coordinate, dichiarati con `PROFILE_PLANETS_EXCLUDED`; §3.10, T12, nuovo T18); RUWE resta senza soglia (D25-11). Nuovo §3.11 (sezione `photometry`: richieste per identificativo a Gaia, IRSA 2MASS e AllWISE con il cerchio della designazione, passo per posizione di 2MASS e AllWISE con le epoche verificate — AllWISE MJD 55400,0, 2MASS `jdate` e periodo 1997-06/2001-02 —, serie VizieR a J2000 con raggio 2″, grafico PNG fuori dall'impronta); §6 `sections`; §10 `PROFILE_PLANETS_EXCLUDED`, `PROFILE_NO_PHOTOMETRY`, `SED_HIGH_PROPER_MOTION`; §12 T7 con l'epoca verificata, nuovi T18–T20; nuova D25-14 (scelte minori di C3, da confermare). |
| 2026-11-07 | Claude Code | **Sprint C2 (decisioni del proprietario del 2026-11-07):** file `approvato` dal proprietario (D25-12, formula in §13); D25-1…D25-12 scritte come decise (D25-5 con la condizione su AllWISE colore, D25-11 con la soglia RUWE solo da fonte ufficiale: verifica senza esito, RUWE senza soglia); nuovo §3.10 (precisazioni del motore: nome con `simbad_object`, candidati da coordinate con `PM_SEARCH_MAX`, `simbad_id`, catena di C2, identità, astrometria, distanza, provenienza, esecuzione); §6 con `crossmatch_radius` e `simbad_id`; §10 con `PROFILE_TARGET_INVALID` e `PROFILE_NO_GAIA` con sotto-voci; nuova D25-13 (scelte minori, da confermare). |
| 2026-11-07 | Claude Code | Creazione del file (stato: bozza), sprint C1 (Fase C, decisione del proprietario del 2026-11-07): regole a–d scritte come decise; verifiche dal vivo su Alcyone, Vega, 51 Peg, TRAPPIST-1 (SIMBAD Harvard, archivio Gaia ESA con `external.gaiaedr3_distance` e incroci ufficiali, IRSA 2MASS/AllWISE, NASA Exoplanet Archive; CDS giù); interfaccia proposta in §3.9; decisioni aperte D25-1…D25-12. |
