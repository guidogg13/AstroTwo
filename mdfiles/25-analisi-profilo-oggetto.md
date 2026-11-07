# 25-analisi-profilo-oggetto.md — Profilo di un oggetto in un minuto

**Stato:** bozza

> Modulo nuovo proposto il 2026-11-07 (sprint C1, Fase C) con la meccanica AM1
> (`panoramica.md` §6, voce `AM1 (25)`): **numero, nome e livello sono una
> proposta da confermare** (D25-1). Solo specifica: nessun codice finché il file
> non è `approvato` e il proprietario non dichiara la fase codice (D25-12).

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
`running`, `done`, `partial`, `error`, `not_applicable`), i suoi errori e i suoi
avvisi. Se un servizio è giù (dopo i mirror già esistenti), quella sezione
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
ciascuna ha il suo tempo massimo; l'insieme ha un tempo obiettivo di 60 s.
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

### 3.7 Esportazione (proposta D25-6)

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
- **Modifiche richieste a moduli `approvato`** (da autorizzare, D25-12):
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
| in | `sections` | elenco | `identity`, `images`, `astrometry`, `photometry`, `planets` | default tutte |
| in | `match_radius` | angolo | arcsec, con unità | default D25-9; usato solo senza identificativo |
| in | `thumbnail_fov`, `thumbnail_size`, `surveys` | angolo, intero, elenco di id HiPS | arcmin; pixel | default D25-5 |
| in | `refresh` | booleano | — | dati aggiornati dalla rete (B4) |
| out | `ObjectProfile` | struttura | §7 | bersaglio risolto, sezioni, avvisi, comando |
| out | `ProfileValue` | struttura | valore `float64` con `astropy.units`, errori, banda, sistema | provenienza obbligatoria |
| out | file esportati | ECSV, PDF, PNG, VOTable | §3.7 | con fonti e crediti |

## 7. Interfaccia pubblica

### 7.1 Questo modulo (`src/astrotwo/analysis/object_profile.py`, proposta)

- **`resolve_target(target, *, match_radius, ...)`** — dal nome, dalla riga o
  dalle coordinate all'oggetto: `ResolvedTarget` (oggetto SIMBAD con
  identificativi, posizione con epoca e fonte) oppure `TargetCandidates`
  (elenco per la scelta dell'utente).
- **`build_profile(target, *, sections, options, on_section, cancel)`** —
  esegue le sezioni in parallelo; chiama `on_section(section)` a ogni sezione
  terminata (arrivo progressivo); restituisce `ObjectProfile`.
- **`profile_identity`, `profile_images`, `profile_astrometry`,
  `profile_distance`, `profile_photometry`, `profile_planets`** — una funzione
  per sezione, ciascuna con lo stesso contratto (`ProfileSection`).
- **`cross_identify(resolved, catalog)`** — catena di §3.2/§3.3:
  `CrossIdentification` (identificativo, metodo `simbad_identifier` |
  `official_crossmatch` | `position`, separazione, epoche, candidati, conflitti).
- **`distance_from(astrometry, *, rules)`** — §3.4.4: `ProfileValue` con il metodo
  o il motivo dell'assenza.
- **`export_profile(profile, path, format)`** — ECSV, PDF, PNG (SED).
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
| Qt (`QPdfWriter`) | PDF della scheda | proposta, D25-6 |
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

Codici proposti (testi en/it nel catalogo dei messaggi, D40-3, da scrivere nello sprint del codice):

| Caso limite | Comportamento | Identificatore errore |
|---|---|---|
| Nome sconosciuto a SIMBAD (server raggiungibile) | profilo non creato, suggerimento coordinate | `NAME_NOT_FOUND` (10/14) |
| SIMBAD giù su tutti i server | nome da `resolve_name` (NED), sezione Identità in errore, resto per posizione | `NET_TIMEOUT` `service_servers` + `PROFILE_NO_IDENTIFIERS` |
| Più candidati per coordinate | elenco da scegliere; da script errore | `PROFILE_AMBIGUOUS_TARGET` |
| Identificativo SIMBAD e incrocio ufficiale in disaccordo | entrambi mostrati, nessuna scelta | `PROFILE_IDENTIFIER_CONFLICT` |
| Oggetto non in Gaia DR3 (Vega) | astrometria da SIMBAD con fonte | `PROFILE_NO_GAIA` |
| Soluzione Gaia a 2 parametri (Alcyone) | niente parallasse/moto proprio da Gaia | `PROFILE_GAIA_TWO_PARAMETER` |
| Parallasse assente, negativa o con errore relativo > 10 % | nessuna distanza, motivo | `PROFILE_NO_DISTANCE` |
| RUWE oltre la soglia | valore mostrato con avviso | `PROFILE_GAIA_QUALITY` |
| Incrocio per posizione | avviso con raggio, separazione, epoche | `PROFILE_POSITIONAL_MATCH` |
| Moto proprio sconosciuto per la propagazione | nessuna propagazione, avviso | `PROFILE_NO_PROPER_MOTION` |
| Archivio Gaia HTTP 503 (coda piena, visto il 2026-11-07) | nuovo tentativo come connessione (`02` §8), poi errore della sezione | `SERVICE_ERROR` / `NET_TIMEOUT` |
| CDS giù (SED di VizieR, nessun mirror) | serie VizieR assente, resto della fotometria presente | `SERVICE_ERROR` + `vizier_no_mirror` |
| Survey HiPS non disponibile su alcun server | miniatura mancante con messaggio | `NET_TIMEOUT` `hips_servers` |
| Tempo totale superato | sezioni non arrivate in errore, le altre restano | `PROFILE_SECTION_TIMEOUT` |
| Annulla | sezioni in corso annullate, arrivate conservate | `COMMAND_CANCELLED` |
| Nessun pianeta | sezione `done` con «nessun pianeta», non errore | — |

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
| T7 | AllWISE per posizione con propagazione | Vega: posizione SIMBAD J2000 + moto proprio SIMBAD, epoca AllWISE (da verificare), cerchio registrato con `J183656.51+384704.4` a ≈ 3,8″ dalla posizione J2000 | candidato trovato solo dopo la propagazione, `PROFILE_POSITIONAL_MATCH` con raggio, separazione ed epoche | separazione ricalcolata con Astropy |
| T8 | Pianeti TRAPPIST-1 | sezione pianeti con `pscomppars` registrata | 7 pianeti b–h, ognuno con periodo, massa ed errori e riferimento (Agol et al. 2021) | confronto |
| T9 | Nessun pianeta | Vega, eta Tau | sezione `done`, «nessun pianeta» | stato |
| T10 | Sezioni indipendenti | archivio Gaia simulato giù (503 ripetuti), CDS giù | astrometria in errore, identità/fotometria (2MASS, AllWISE)/pianeti presenti | stati delle sezioni |
| T11 | Arrivo progressivo | servizi simulati con ritardi diversi | `on_section` chiamato nell'ordine dei tempi, ogni sezione una volta | ordine |
| T12 | Più candidati | coordinate tra due oggetti SIMBAD entro il raggio | `TargetCandidates` con 2 voci; da script `PROFILE_AMBIGUOUS_TARGET` | nessuna scelta |
| T13 | Conflitto di identificativi | SIMBAD dà 2MASS X, l'incrocio Gaia dà 2MASS Y | entrambi, `PROFILE_IDENTIFIER_CONFLICT` | |
| T14 | Riproducibilità | `object.profile` registrato, rieseguito dalla sessione, poi con `refresh` | stesse richieste e stessi valori dalla cache; con `refresh` nuove richieste e `DATA_REFRESHED` | sessione del 05 |
| T15 | Esportazione | `export_profile` ECSV | una riga per valore con tutte le colonne di provenienza; rilettura con `astropy.table` | ECSV valido |
| T16 | Testi esterni | `*_reflink` con HTML | solo URL ADS e testo estratti; nessun tag eseguito; marcati esterni verso l'IA | |
| T17 | Rete (marcato `network`) | 3 oggetti veri | struttura e identificativi come T1–T9; tempo totale registrato (obiettivo 60 s) | non nel commit (`--no-network`) |

## 13. Decisioni aperte

- **D25-1 — Numero, nome e livello del modulo** (AM1): proposta
  `25-analisi-profilo-oggetto.md`, livello 2, codice in
  `src/astrotwo/analysis/object_profile.py`. Alternative: livello 1 (è fatto
  solo di interrogazioni) | file d'interfaccia 4x. Raccomandazione: 25, livello 2
  (usa la SED del 20, che è analisi). **Da decidere.**
- **D25-2 — Metodo della distanza:** proposta §3.4.4 (Bailer-Jones 2021 →
  1/ϖ con ϖ/σ ≥ 10 da Gaia o SIMBAD con fonte → nessuna). Alternative: solo
  Bailer-Jones | anche `distance_gspphot` di Gaia DR3 (verificata: esiste,
  15,5181 pc per 51 Peg) come terza riga informativa. **Da decidere.**
- **D25-3 — Tabella dei pianeti:** `pscomppars` (un valore per parametro, dal
  lavoro scelto dall'archivio, riferimento per parametro; parametri da lavori
  diversi possono non essere coerenti tra loro, avviso) | `ps` con
  `default_flag = 1` (una soluzione coerente per pianeta, un riferimento; verificata
  per 51 Peg). Raccomandazione `pscomppars` con l'avviso. **Da decidere.**
- **D25-4 — Catena degli identificativi** (§3.2): uso degli incroci ufficiali
  di Gaia (`tmass_psc_xsc_best_neighbour`, `allwise_best_neighbour`) come
  identificativi dichiarati; AllWISE con cerchio piccolo + controllo della
  `designation`. **Da decidere.**
- **D25-5 — Miniature:** survey DSS2 colore, 2MASS colore, AllWISE colore; campo
  5′; 256 × 256 pixel; TAN centrata. AllWISE colore ha oggi come copia solo
  ESASky (`skies.esac.esa.int/AllWISEColor`, `properties` HTTP 200 il
  2026-11-07; IRSA 404): confronto dei tile **da verificare** prima del codice.
  **Da decidere.**
- **D25-6 — Esportazione:** ECSV dei valori con provenienza + PDF della scheda +
  PNG della SED; JSON del risultato del 05 escluso (già nella sessione).
  **Da decidere.**
- **D25-7 — Dove vive la specifica dell'interfaccia** di §3.9: nel `43`
  (pannello analisi, oggi `non esiste`, che nascerebbe con profilo e SED) |
  nuovo file d'interfaccia | resta qui. Raccomandazione: `43`, scritto nello
  sprint C5. **Da decidere.**
- **D25-8 — Tempi:** obiettivo 60 s; tempo massimo per sezione (SIMBAD 15 s,
  Gaia 30 s, IRSA 60 s, Exoplanet 30 s, HiPS 30 s); 4 richieste contemporanee.
  **Da decidere.**
- **D25-9 — Raggi:** 10″ per i candidati SIMBAD da coordinate; 2″ per gli
  incroci per posizione dopo la propagazione. **Da decidere.**
- **D25-10 — Zero point di parallasse** (Lindegren et al. 2021): non applicato
  nella 1.0, dichiarato | applicato con la libreria ufficiale
  `gaiadr3-zeropoint` (licenza da verificare). **Da decidere.**
- **D25-11 — Indicatori di qualità di Gaia:** quali mostrare (§3.4.3) e soglia
  RUWE 1,4 con fonte (documentazione Gaia DR3 / Lindegren et al. 2021: **da
  verificare** sul testo). **Da decidere.**
- **D25-12 — Autorizzazioni per il codice:** formula di fase (es. «FASE:
  CODICE – livello 2» limitata ad approvati 20 e 25) e autorizzazione a
  modificare gli approvati `03`, `05`, `12`, `14`, `32`, `34`, `40`, `41`,
  `42` per §5. **Da decidere (proprietario).**

## 14. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-11-07 | Claude Code | Creazione del file (stato: bozza), sprint C1 (Fase C, decisione del proprietario del 2026-11-07): regole a–d scritte come decise; verifiche dal vivo su Alcyone, Vega, 51 Peg, TRAPPIST-1 (SIMBAD Harvard, archivio Gaia ESA con `external.gaiaedr3_distance` e incroci ufficiali, IRSA 2MASS/AllWISE, NASA Exoplanet Archive; CDS giù); interfaccia proposta in §3.9; decisioni aperte D25-1…D25-12. |
