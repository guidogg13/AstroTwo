# INDICE.md — elenco di tutti i file di `mdfiles/`

**Stato:** bozza

Una riga di descrizione e lo stato per ogni file. Stati ammessi:
`bozza` | `in revisione` | `approvato`. Per i file non ancora scritti si usa
`non esiste`. Lo stato qui deve sempre corrispondere alla testa del file.

Aggiornare questo file a ogni creazione o cambio di stato (regola di `CLAUDE.md`).

**Ultimo aggiornamento:** 2026-10-17 — **codice del 05 scritto** (parte 1 della v1, 39 comandi; scelte minori da confermare nel 05 §13). Prima: **D05-4 decisa** (tipo `record` nel 05, parametri dei `calc.*` nel 18,
adattatore scritto); `httpx2` accettato (01, 30); profili predefiniti dei provider IA (30, 31, 44). Aperte 14 (Gruppo 1 = 0).
Riepilogo invariato: approvato 24, bozza 5, non esiste 14, totale 43.
Prima di questo aggiornamento: 2026-10-16 — **D04 (cache da più thread) decisa e scritta; verifiche prima del codice della
v1; livello 1 allineato (10, 11, 12)**; adattatore del 18 fermo sulla nuova D05-4 (Gruppo 1). Aperte 15. Riepilogo
invariato: approvato 24, bozza 5, non esiste 14, totale 43.
Prima di questo aggiornamento: 2026-10-16 — **approvati dal proprietario 05, 30, 31, 32, 34, 35, 40, 41, 42, 44** (scelte
minori confermate, servizio del Portachiavi `dev.pages.astrotwo.ai`, identificativo `dev.pages.astrotwo` nel 01);
**"FASE: CODICE – interfaccia v1" dichiarata**. Riepilogo: approvato 24, bozza 5, non esiste 14, totale 43.
Prima di questo aggiornamento: 2026-10-16 — **specifiche dell'IA nella v1** (proposta della fase 1 sull'IA approvata dal
proprietario il 2026-10-16; nessun codice applicativo): creati in `bozza` `30`, `31`, `32`, `34`, `35`, `44`; modificati
05, 40, 41, 42 e gli approvati 01, 02, 03, 10 (restano `approvato`) e `CLAUDE.md`; nuovo mockup
`mockup/finestra-principale-ia.html`; regola dei commit con HTTP 429/502/503/504 come connessione (02 §8). Nessuna
nuova decisione aperta; aperte 14. Riepilogo: approvato 14, bozza 15, non esiste 14, totale 43.
Prima di questo aggiornamento: 2026-10-15 — **decisioni del proprietario sulle specifiche dell'interfaccia**: decise D05-1,
D05-2, D40-1, D41-1…D41-4 (05, 40, 41, 42 senza decisioni dei Gruppi 1 e 2 aperte); nuova D40-3; `format_coordinates`
nel 10 e `suggest_display_limits` nell'11 (restano `approvato`); linee guida visive nel 40; mockup in
`mdfiles/mockup/` (due pagine HTML statiche, non contate tra i file di specifica). Aperte 14. Riepilogo invariato:
approvato 14, bozza 9, non esiste 20, totale 43.
Prima di questo aggiornamento: 2026-10-15 — **specifiche della prima versione dell'interfaccia** (proposta della fase 1
approvata dal proprietario il 2026-10-15): nuovo file generale **`05-comandi-sessione.md`** (AM1 accettata, livello 1)
e **`40`, `41`, `42`** scritti in `bozza`; decise A9, D10-9, D11-8 e il raggio del puntatore Simbad; modificati i file
approvati 01, 02, 03, 10, 11, 12, 13, 17, 18 (restano `approvato`) e `CLAUDE.md` (formula "FASE: CODICE –
interfaccia v1"). Nessun codice. Aperte 20 (Gruppo 2 = 9, Gruppo 3 = 11). Riepilogo: approvato 14, bozza 9, non
esiste 20, totale 43.
Prima di questo aggiornamento: 2026-10-14 — **D16-8 decisa e applicata** (MOC da immagine: blocchi più angoli di
contorno; `moc_from_image` sulla DSS da 10,3 a 0,2 s) e **D14-13 aperta** (reindirizzamento http → https
dell'ESO); 16 e 14 modificati nel registro e restano `approvato`. Test 494 di default. Aperte 14. Riepilogo
invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-14 — **`display_positions` nel 13** (D10-2 in un passo; T34) usata dalla demo
delle Pleiadi; **D16-8 aperta** (MOC da immagine con i blocchi: la regola decisa perde celle sul bordo, regola e
codice non applicati); 13 e 16 modificati nel registro e restano `approvato`. Test 492 di default. Aperte 14.
Riepilogo invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-13 — **demo delle Pleiadi** (`examples/`, primo test con dati veri); difetto
del 16 trovato e corretto (testo di `filter_by_moc`), 16 modificato nel registro e resta `approvato`. Riepilogo
invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-13 — **livello 1 chiuso** (decisioni del proprietario del 2026-10-13): D17-9
decisa e scritta (`distance_to` per ellisse, freccia, tracciato aperto; testo escluso), D19-9 decisa e scritta
(PDS4 da URL), D19-8 rimandata (PDS3 non ancora supportato); scelte minori di 18 e 19 confermate; 04 con 18 e
19 tra gli utenti della cache; testo di licenza di `pims` trovato e aggiunto a `THIRD_PARTY_LICENSES`; 04, 17, 19
modificati e restano `approvato`. Test 491 di default. Aperte 13. Riepilogo invariato: approvato 14, bozza 5,
non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-13 — **livello 1 scritto per intero (04, 10–19)**: D17-8 e D18-7
decise e scritte; `THIRD_PARTY_LICENSES` creato (01 §6); `read_raw_pixel` nell'11; UT1 con le tabelle IERS
incluse; **modulo 19 scritto in P0–P4** (`planetary_data.py`, tabella dei nomi D12-6 anche nel 12); nuove aperte
D17-9, D19-8, D19-9 (Gruppo 3); 01, 11, 12, 17, 18, 19 modificati e restano `approvato`. Test 485 di default,
505 con la rete. Aperte 15. Riepilogo invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-12 — **modulo 17 scritto in P1, P2, P4** (`measures.py`), **P3 (forme e
tag) ferma su D17-7** (nuova, Gruppo 3: geometria sferica, proposta `spherical-geometry`); decise D12-6,
D12-7, D12-8, D17-5; H10 SkyView rinviato con il motivo; codifica del MocServer scritta in 14 e 16; A10
HiPS nella riga di `01`; scelte minori di 12 e 16 confermate; 01, 12, 14, 16, 17 modificati e restano
`approvato`. Test 427 di default, 444 con la rete. Aperte 15. Prossimo: modulo 18 (proposta in attesa del
proprietario). Riepilogo invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-12 — **modulo 12 scritto (P1–P5)** tranne i pezzi fermi H10 SkyView
(URL SIA non documentato da NASA), D12-6, D12-7, D12-8 (nuove, Gruppo 3); **D16-6, D16-7 decise**,
corpo misto e MOC planetari in FITS nel 16; A10 decisa per gli HiPS; 14 §12 rimanda a `02` §8; 12, 14,
16 modificati e restano `approvato`. Test 405 di default, 422 con la rete. Aperte 18. Prossimo: modulo
17 (proposta in attesa del proprietario). Riepilogo invariato: approvato 14, bozza 5, non esiste 23,
totale 42.
Prima di questo aggiornamento: 2026-10-11 — **regola dei commit in `02` §8 e modulo 16 scritto (P1–P5)**
tranne i pezzi fermi D16-6 (versione 2.1 del formato MOC) e D16-7 (complemento degli ST-MOC);
D13-20, D15-8, D15-9 decise; 02, 13, 15, 16 modificati e restano `approvato`. Test 359 di default,
373 con la rete. Aperte 18. Prossimo: modulo 12 (proposta in attesa del proprietario).
Riepilogo invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-11 — **modulo 15 scritto (P1–P5)** tranne i pezzi fermi D15-8 e
D15-9; D13-19 (regione di `load_catalog`) e D15-6 decise; ECSV con il sistema delle posizioni,
ordine naturale dell'albero, ripetizioni dei test di rete solo per connessione/timeout; 13, 14,
15 modificati e restano `approvato`. Nuove aperte D13-20, D15-8, D15-9. Test 325 di default,
337 con la rete. Aperte 19. Prossimo: modulo 16 (proposta in attesa del proprietario).
Riepilogo invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-11 — **pezzi fermi di 13 e 14 chiusi** (decisioni del
proprietario D14-10, D14-11, D14-12, D13-17, D13-18; 11, 13, 14 modificati e restano `approvato`):
ECSV, calibrazione della lista SIA nell'11, magnitudini SIMBAD, `LINK` ASTRORES, albero delle
collezioni; registro VO di default in HTTPS; `load_catalog` senza regione con `allow_partial`.
Nuove aperte D13-19 e D13-14c (Gruppo 3). Test 299 di default, 308 con la rete. Aperte 18.
Prossimo: modulo 15 (proposta di divisione in attesa del proprietario). Riepilogo invariato:
approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-10 — **modulo 14 scritto (P1–P7) e P6 del 13**, tranne i
pezzi fermi su D14-10, D14-11, D14-12, D13-17, D13-18 (nuove, Gruppo 3); D14-5 decisa; riga
H23 di `03` annotata (IDHA). Test 293 di default, 301 con la rete. Aperte 21. Riepilogo
invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-10 — **modulo 13 completo fino a P5** (P6 dopo il 14);
D13-14b, D13-15, D13-16 decise. Test 253 di default, 257 con la rete. Aperte 17.
Prossimo: modulo 14. Riepilogo invariato: approvato 14, bozza 5, non esiste 23,
totale 42.
Prima di questo aggiornamento: 2026-10-10 — **modulo 13: P1–P3 scritte, P4 e P5 quasi
complete** (mancano `calculated_column`, D13-15, e `time_filter`, D13-16); P6 dopo il
14; nel 10 `proper_motion_only` e `parse_sexagesimal`; D13-10…D13-14 decise, nuove
D13-14b, D13-15, D13-16. Test 247 di default, 251 con la rete. Aperte 20. Riepilogo
invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-10 — D11-11 (limite delle operazioni 4 GB, display a
blocchi in `float32`); strumenti IA nel 32 (`01` §7); regola d'oro n. 8 anche in 10 e
17, validazione ≠ copia in `CLAUDE.md`; **modulo 13: specifica aggiornata, P1 scritta**,
P2 ferma su D13-14. Test 213 di default, 216 con la rete. Aperte 22. Riepilogo
invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-10 — decisioni del proprietario applicate a 11, 12,
13, 14, 15, 18, 19 (restano `approvato`): nell'11 avviso `HHH_WCS_DIFFERS`, tetto di
memoria A10 (`MEMORY_LIMIT_EXCEEDED`), §11 nel 32; regola d'oro n. 8 (Hipsgen tolto,
grammatica di `search` nostra, server VO nostri, raggio del cross-match obbligatorio,
unità solo FITS/VOUnit, motivazioni nostre). Test 200 di default, 203 con la rete.
Prossimo modulo: 13. Aperte 19. Riepilogo invariato: approvato 14, bozza 5, non
esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-10 — **modulo 11 completo** (7 parti, un commit per
parte; test 197 di default, 200 con la rete); `04`, 10 e 11 completi. Aperte 19.
Riepilogo invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-10 — regola d'oro n. 8 (AstroTwo scritto da zero);
decisioni sull'11 (divisione in 7 parti); nuova A11 (licenza). Aperte 19 (Gruppo
1 = 0, Gruppo 2 = 4, Gruppo 3 = 15). Riepilogo invariato: approvato 14, bozza 5,
non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-09 — **codice della cache comune (`04`) e di
`resolve_name` (modulo 10) scritto**; precisazioni di `04` (limite sui dati, 5 × 10⁹
byte) e del `10` (prima la cache). Test: 103 superati di default, 106 con la rete.
Aperte 18. Riepilogo invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-09 — nomi dei file Python in inglese (tabella in
`02` §3); nuova D11-8. Aperte 18 (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 15).
Riepilogo invariato: approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-09 — **`04-cache.md` approvato** (CA1–CA4 decise);
12, 13, 14, 16 (e 11) collegati alla cache comune, senza cache proprie (restano
approvati); D11-7 decisa; nel 10 nuova `choose_grid_spacing` e conferme delle
interpretazioni; codice: `choose_grid_spacing` (modulo 10) e `star_centroid`
(modulo 11). Aperte 17 (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 14). Riepilogo:
approvato 14, bozza 5, non esiste 23, totale 42.
Prima di questo aggiornamento: 2026-10-09 — decise D10-7 e D10-8; **AM1 accettata: creato
`04-cache.md`** (bozza); applicate le decisioni in 10, 11, 17, 18 (restano
approvati); **modulo 10 scritto e testato** (60 superati, 1 saltato, 2 di rete
superati); vincolo LGPL-3 di WCSLIB per il 60. Aperte 22 (Gruppo 1 = 0,
Gruppo 2 = 7, Gruppo 3 = 15). Riepilogo: approvato 13, bozza 6, non esiste 23,
totale 42.
Prima di questo aggiornamento: 2026-10-09 — **FASE: CODICE – livello 1** dichiarata dal
proprietario: creata la base del progetto (`pyproject.toml`, `src/astrotwo/`,
`tests/`); verifiche del modulo 10 eseguite, aperte nel `10` le nuove D10-7
(calibrazione per associazione di stelle) e D10-8 (parti senza interfaccia in
§7), Gruppo 3. Aperte 18 (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 15).
Riepilogo invariato: approvato 13, bozza 5, non esiste 23, totale 41.
Prima di questo aggiornamento: 2026-10-09 — **livello 1 interamente approvato** (01, 02,
03, 10–19): decise D11-6, D13-7, D14-7, D14-8, D15-5 e il framework `pytest`;
approvati 11, 13, 14, 15. Aperte 16 (Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 =
13). Riepilogo: approvato 13, bozza 5, non esiste 23, totale 41.
Prima di questo aggiornamento: 2026-10-09 — **approvati 01, 02, 03, 10, 12, 16, 17, 18,
19**; moduli 11–17 completati con gli esiti di AP5 e 10 con H25; **11, 13, 14,
15 in bozza** per le nuove decisioni del Gruppo 2 D11-6, D13-7, D14-7, D14-8,
D15-5 (più D13-8 nel Gruppo 3). Aperte 20 (Gruppo 1 = 0, Gruppo 2 = 8, Gruppo
3 = 12). Riepilogo: approvato 9, bozza 9, non esiste 23, totale 41.
Prima di questo aggiornamento: 2026-10-09 — **checklist del livello 1 applicata:** 30
decisioni del Gruppo 2 chiuse nei file di origine; A2/A6/A9 con orientamento,
bloccanti solo per `60`/`40`; D19-3 esteso al `15`; nuove A10 e D10-6 (Gruppo
3); `CLAUDE.md` con la fase codice per livello. Aperte 14 (Gruppo 1 = 0,
Gruppo 2 = 3, Gruppo 3 = 11). Approvazione di 01, 02, 03 e 10–19 **non
eseguita** (moduli 11–17 da completare con gli esiti di AP5). Stati
invariati: bozza 18, non esiste 23, totale 41.
Prima di questo aggiornamento: 2026-10-09 — applicate le decisioni del proprietario del
2026-10-08: D19-3 (campo `body` obbligatorio in `12`, `13`, `14`, `16`), D19-2
(PDS nel 19, PDS4 obbligatorio; resta D19-2b), D19-4 (errore di default,
forzabile con opzione esplicita), DC7 confermata con la funzione
`convert_pixel_convention` nel `10`; `CLAUDE.md` aggiornato. Aperte 42 (Gruppo
1 = 0, Gruppo 2 = 33, Gruppo 3 = 9). Stati invariati: bozza 18, non esiste 23,
totale 41.
Prima di questo aggiornamento: 2026-10-08 — **scritti `18-core-calcolatrici.md` e
`19-core-dati-planetari.md`** (stato `bozza`): nucleo 10–19 tutto in bozza;
nuove decisioni aperte D18-1…D18-6 e D19-1…D19-7 (aperte 44: Gruppo 1 = 2,
Gruppo 2 = 33, Gruppo 3 = 9); "Usato da" aggiornato nei moduli 10–14, 16, 17.
Riepilogo: bozza 18, non esiste 23, totale 41.
Prima di questo aggiornamento: 2026-10-08 — **decisioni del proprietario sugli esiti
di AP5:** AM1 per H21 accettata → registrato `19-core-dati-planetari.md`
(livello 1, `non esiste`); `01` §8 obiettivo minimo di prestazioni (1 milione
di sorgenti con 1 GB di RAM); `10` D10-4 precisata (8 proiezioni del manuale);
`02` nuova DC7 (convenzione dei pixel); `03` H17 (SED nel 20), H19 (API Python
nel 24 + SAMP nel 14), H21 (→ 19), H25 (→ DC7). Aperte 31 (Gruppo 1 = 0,
Gruppo 2 = 24, Gruppo 3 = 7). Riepilogo: bozza 16, non esiste 25, totale 41.
Prima di questo aggiornamento: 2026-10-08 — **lettura AP5 completata** (sezioni
5.9–8 del manuale di Aladin, ed. giugno 2022) e integrata in
`03-parita-aladin.md`: note su 20 righe, correzioni D12/E3/F4, nuove righe
H20–H27 (86 righe in tutto); **nuova proposta AM1: H21, dati planetari**
(nessun file creato); aperte 32 (Gruppo 1 = 1, Gruppo 2 = 24, Gruppo 3 = 7).
Stati invariati: bozza 16, non esiste 24, totale 40.
Prima di questo aggiornamento: 2026-10-08 — numeri di sezione del manuale di
Aladin riportati all'ed. giugno 2022 in `03-parita-aladin.md` e
`panoramica.md` (A13 5.19, D12 6.6, H17 5.10, H19 7.4; H18 con fonte ed.
febbraio 2021, sezione assente nel 2022); AP5 = "AP5 decisa; lettura delle
sezioni 5.9–8 (ed. giugno 2022) ancora da fare"; **AP3 decisa** (Aladin Lite
escluso dalla parità); smistamento dei gruppi confermato; aperte 31 (Gruppo 2
= 24, Gruppo 3 = 7). Stati invariati: bozza 16, non esiste 24, totale 40.
Prima di questo aggiornamento: 2026-10-08 — **decisioni del proprietario sui punti
aperti della manutenzione** (nessun file nuovo, stati invariati): **AP6 decisa**
(edizione di riferimento del manuale di Aladin = giugno 2022, la più recente
ufficiale dopo verifica sul sito del CDS); edizione indicata accanto ai numeri
di sezione del manuale, con "numerazione da verificare" dove l'ed. giugno 2022
differisce; `decisioni-aperte.md` completato con AP1–AP4, DC1 (parte aperta),
DC3, DC4 (aperte 32: Gruppo 2 = 25, Gruppo 3 = 7); AP5 scritta ovunque come
"AP5 decisa; lettura delle sezioni 5.7.3–8 ancora da fare"; `03` T3/T4 su
10–18; D14-6 rinominata; calcolatrici nel nucleo di `panoramica.md` §3; refusi
in `panoramica.md` e `03`. Riepilogo: bozza 16, non esiste 24, totale 40.
Prima di questo aggiornamento: 2026-10-08 — **manutenzione delle specifiche**
(nessun file nuovo, stati invariati): `AGENTS.md` sostituito da `CLAUDE.md`
(file rimosso dalla radice, riferimenti aggiornati); intervalli nucleo 10–18 e
interfaccia 40–45 in `01-architettura.md` e `panoramica.md`; riferimento AP5
uniformato a 5.7.3–8; refusi in `01` e `02`; nuova decisione aperta **AP6**
(edizione di riferimento del manuale di Aladin) in `03-parita-aladin.md` e
`decisioni-aperte.md` (aperte 26). Riepilogo: bozza 16, non esiste 24,
totale 40.
Prima di questo aggiornamento: 2026-10-04 — creato `riassunto.md` (bozza): il
progetto in 5 righe (cos'è, struttura a 4 livelli, regole d'oro, stato,
prossimi passi). Riepilogo: bozza 16, non esiste 24, totale 40.
Prima di questo aggiornamento: 2026-10-04 — **esito parziale di AP5 e correzioni
alla parità** (`03-parita-aladin.md`): fonte = manuale utente Aladin Desktop
**edizione febbraio 2021**, lette **sezioni 1–5.7.2 e l'indice completo**; AP5
resta **aperta** per i dettagli delle sezioni **5.7.3–8**, l'esistenza di tutte
le funzioni è verificata dall'indice. **D12 corretta:** in Aladin l'estrazione
di sorgenti esiste (sezione 6.5) **tramite il programma esterno SExtractor** →
riga tornata nella sezione D come `verificata` (AstroTwo: estrazione **nativa**
nel modulo 20, senza programmi esterni, libreria da decidere); la sezione
"funzioni extra" è ora senza righe. Aggiunte **H17** (strumento Exam, 5.9),
**H18** (avvio tramite URL, 7.2), **H19** (interfacce VOApp/VOObserver, 7.5)
con "dettagli da leggere" e modulo proposto; note su **A13** (stampa, 5.18),
**B11** (mosaici e sequenze animate con blink), **E4** (spettri mostrati nel
modulo 21), **F4** (risoluzione della fotometria su HiPS). In
`01-architettura.md` §8 nuovo requisito non funzionale: **obiettivi di
prestazioni almeno pari ad Aladin** (righe di catalogo, dimensione di immagini
e cubi; sezione 8.3 del manuale, da leggere) da definire in
`61-strategia-test.md`. Voce di indice di
`24-analisi-pipeline-riproducibili.md`: in Aladin la cronologia dei comandi
registra anche le azioni fatte con il mouse come comandi di script; AstroTwo
adotta lo stesso principio (ogni azione dell'interfaccia = un comando
registrato). Aggiornati `panoramica.md` e i registri. Stati invariati: bozza 15,
non esiste 24, totale 39.
Prima di questo aggiornamento: **22 decisioni del proprietario
(Gruppo 1 di `decisioni-aperte.md`) passate da aperte a prese:** `A1`
(PySide6, rendering OpenGL da specificare in 41), `A5` (interfaccia a
capacità, provider cloud + endpoint compatibile OpenAI), `AP5` (sezioni
5.7.3–8 [indicate in origine come 5.9–8] del manuale di Aladin da leggere prima dei gruppi successivi),
`D10-2`/`D13-2` (epoca dai metadati, mai assunta; epoca di visualizzazione =
epoca dell'immagine se nota, altrimenti J2000; epoca sempre nel risultato;
cataloghi con propria epoca di riferimento), `D10-3` (cache nomi in tabella
SQLite separata), `D10-4` (proiezioni = Aladin da verificare con AP5, TAN/AIT,
un test per proiezione), `D11-1` (tipo nativo in memoria, float64 nei
calcoli, float32 solo display → DC6), `D11-3` (cache su disco 5 GB di
default, configurabile), `D12-5`/`D16-5` (HEALPix nel 16, tile nel 12),
`D13-1` (grammatica `search` alla Aladin), `D13-5` (operazioni non
distruttive), `D13-6` (DataLink: colonna 13, risoluzione 14), `D14-1`
(`pyvo` TAP/DataLink, `astropy.samp` da valutare), `D14-2` (hub SAMP attivo o
proprio; tabelle/selezioni/puntamenti), `D16-1` (`mocpy`), `D16-2` (MOC in
cache FITS IVOA), `D16-3` (JD interno, ISO 8601 in UI/file, scala sempre
dichiarata → DC1), `D17-2` (geometria 17 / rendering 41), `D17-3` (tag nella
sessione del 24), `D17-4` (fotometria F4 nel 20). Aggiornati `01`, `02`
(DC1/DC2/DC6), `03`, `10`–`14`, `16`, `17`, `decisioni-aperte.md`
(Gruppo 1 vuoto; aperte 25) e `panoramica.md`. Stati invariati: bozza 15,
non esiste 24, totale 39.
Prima di questo aggiornamento: creato `decisioni-aperte.md`: tutte
le 47 decisioni ancora aperte raccolte in un unico file e smistate in tre
gruppi (Gruppo 1 = 22 bloccanti per altri moduli, Gruppo 2 = 20 bloccanti
solo per l'approvazione del modulo, Gruppo 3 = 5 rimandabili al codice);
fonti: §13 di `10`–`17`, `01-architettura.md` §5, `03-parita-aladin.md` §6;
escluse le chiuse D12-2 e D17-1; linkato da `panoramica.md` §4 e §6;
riepilogo: bozza 15, non esiste 24, totale 39.
Prima di questo aggiornamento: **AM1 decisa:** accettate le proposte
H2 e H4, registrati `18-core-calcolatrici.md` (livello 1, dipende da `10`,
`11`) e `45-ui-viste-multiple.md` (interfaccia, dipende da `41`, `40`) con
stato `non esiste`; righe H2/H4 di `03-parita-aladin.md` puntate ai nuovi
moduli; riepilogo: bozza 14, non esiste 24, totale 38.
Prima di questo aggiornamento: **decisione del proprietario (P11):**
la parità con Aladin è il minimo, non il traguardo; AstroTwo include tutte le
funzioni di `03-parita-aladin.md`. Righe C3, F2, G3, E4 →
`inclusa (decisione del proprietario)`; funzioni descritte per intero in
`12-core-hips.md` (C3), `17-core-misure.md` (F2), `14-core-protocolli-vo.md`
(G3 SAMP, E4 SSA); descrizioni aggiornate sotto; stati invariati.
Prima di questo aggiornamento: scritto il **gruppo nucleo**:
`10-core-coordinate-wcs.md`, `11-core-immagini-fits.md`, `12-core-hips.md`,
`13-core-cataloghi.md`, `14-core-protocolli-vo.md`, `15-core-crossmatch.md`,
`16-core-moc.md`, `17-core-misure.md` (tutti `bozza`); decisioni aperte
D12-1…D17-6 nei rispettivi file; stati aggiornati anche in `panoramica.md`.
Prima di questo aggiornamento: `03-parita-aladin.md` con l'esito della verifica
documentale (manuale utente Aladin Desktop ed. giugno 2022 sezioni 1–5.8,
manuale script v12.0, FAQ): 58 righe in A–G, 16 funzioni
nuove in sezione H, 1 funzione extra, 4 righe `non trovata` (ora incluse),
nuova decisione AP5 (sezioni 5.7.3–8 [indicate in origine come 5.9–8] ancora da leggere); due proposte di nuovo
modulo in AM1 (`45-ui-viste-multiple.md`, `18-core-calcolatrici.md`).
Prima ancora: decisioni A3 (struttura `src/astrotwo/` +
`tests/`), A4 (Python 3.12, `pyproject.toml`, `uv`) e A7 (cache SQLite/file con
limite e provenienza); orientamento provvisorio A1 (PySide6) e A5 (provider IA);
rimandate A8 e AP1. Elenco completo: `panoramica.md` §5–§6 e
`01-architettura.md` §4–§5.

Dove si trovano le decisioni:

| Etichette | File |
|---|---|
| `A1`–`A9` | `01-architettura.md` |
| `AP1`–`AP6` | `03-parita-aladin.md` |
| `AM1`, `P1`–`P10` | `panoramica.md` |
| `DC1`–`DC7` | `02-convenzioni.md` |
| `CA1`–`CA4` | `04-cache.md` |

## File generali

| File | Descrizione | Stato |
|---|---|---|
| `CLAUDE.md` | Regole di lavoro del progetto, sostituisce il vecchio `AGENTS.md` (si trova nella cartella radice, non in `mdfiles/`) | — |
| `TEMPLATE-modulo.md` | Modello obbligatorio con le 14 sezioni per ogni file di modulo | bozza |
| `panoramica.md` | Riassunto di tutto il progetto: livelli, tabella moduli, decisioni, prossimi passi | bozza |
| `riassunto.md` | Il progetto in 5 righe: cos'è, struttura, regole d'oro, stato, prossimi passi | bozza |
| `INDICE.md` | Questo elenco | bozza |
| `01-architettura.md` | Architettura generale, scelte tecniche e motivazioni; decisioni `A1`–`A9` (prese, aperte, rimandate) | approvato |
| `02-convenzioni.md` | Convenzioni di documentazione, nomi, unità, coordinate, versioni, test | approvato |
| `03-parita-aladin.md` | Funzioni di Aladin e modulo di AstroTwo che le copre; esito della verifica documentale (colonne Copertura e Note, sezioni A–H, "funzioni extra" vuota); AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08 (prima lette 1–5.8 dell'ed. giugno 2022; esito parziale: ed. febbraio 2021, sezioni 1–5.7.2 + indice); AP6 decisa: edizione di riferimento del manuale = giugno 2022; AP3 decisa: Aladin Lite escluso dalla parità; 86 righe (H20–H27 dalla lettura AP5; H21 → `19-core-dati-planetari.md`) | approvato |
| `04-cache.md` | Cache A7 condivisa: `~/Library/Caches/AstroTwo/`, SQLite + file, limite 5 GB, timeout dichiarati, origine e data di ogni dato; usata da 10–14, 16, 18 e 19 (AM1 accettata il 2026-10-09; timeout 10 s / 60 s, un solo limite, nessuna cache propria nei moduli, codice in `src/astrotwo/core/cache.py`) | approvato |
| `05-comandi-sessione.md` | Registro dei comandi e sessione (livello 1, file generale come il 04; AM1 accettata il 2026-10-15; codice previsto in `src/astrotwo/core/commands.py`): comandi con nome, versione, parametri tipizzati con unità, descrizioni EN/IT, risultato strutturato, indicatori; sessione JSON senza pixel, riapertura = riesecuzione con stop se lo SHA di un file è cambiato; schema JSON per il 32; `run_command` del 18 come adattatore; D05-1 e D05-2 decise (impronta dei risultati di rete nella sessione), D05-3 rimandata; dal 2026-10-16 `requested_by`, indicatore `confirm`, comandi di sola lettura per l'assistente e blocco facoltativo `conversations`; dal 2026-10-17 tipo `record` (D05-4) e **codice scritto** | approvato |
| `decisioni-aperte.md` | Decisioni aperte (14: Gruppo 1 = 0, Gruppo 2 = 3, Gruppo 3 = 11, aggiornate il 2026-10-17) e, in §3, gli esiti delle 22 decisioni prese il 2026-10-04 | bozza |

## Nucleo (livello 1)

| File | Descrizione | Stato |
|---|---|---|
| `10-core-coordinate-wcs.md` | Coordinate celesti, WCS, sistemi e epoche di riferimento | approvato |
| `11-core-immagini-fits.md` | Lettura, gestione e visualizzazione di immagini FITS | approvato |
| `12-core-hips.md` | Servizio HiPS per immagini all-sky, incluso aggiungere un HiPS da ID/URL (C3) (codice scritto in 5 parti il 2026-10-12, `src/astrotwo/core/hips.py`; D12-6, D12-7, D12-8 decise; fermo H10 SkyView, rinviato) | approvato |
| `13-core-cataloghi.md` | Cataloghi e tabelle: caricamento, plottaggio, filtri | approvato |
| `14-core-protocolli-vo.md` | Protocolli Virtual Observatory: VOTable, cone search, TAP/ADQL, esportazione, elenco dei server e registro VO, DataLink, SIA/SIA2, SAMP (G3), spettri SSA (E4), puntatori Simbad/VizieR | approvato |
| `15-core-crossmatch.md` | Incrocio tra cataloghi (cross-match) | approvato |
| `16-core-moc.md` | Mappe di copertura MOC (codice scritto in 5 parti il 2026-10-11, `src/astrotwo/core/moc.py`; D16-6 e D16-7 decise e scritte il 2026-10-12) | approvato |
| `17-core-misure.md` | Misure angolari: distanza, position angle, strumenti di misura (codice completo, `src/astrotwo/core/measures.py`; `distance_to` con D17-8 e D17-9 il 2026-10-13: tutte le forme, testo escluso) | approvato |
| `18-core-calcolatrici.md` | Calcolatrici: algebrica, unità, pixel, coordinate, tempo (livello 1; origine H4 di `03-parita-aladin.md`; codice P1–P5 scritto il 2026-10-12/13, `src/astrotwo/core/calculators.py`; completo il 2026-10-13 con D18-7, UT1 con le tabelle IERS incluse) | approvato |
| `19-core-dati-planetari.md` | Dati planetari: superfici, cataloghi e coperture planetarie, sistemi di riferimento planetari (livello 1; origine H21 di `03-parita-aladin.md`, AM1 accettata il 2026-10-08; codice P0–P4 scritto il 2026-10-13, `src/astrotwo/core/planetary_data.py`; PDS4 anche da URL (D19-9); PDS3 non ancora supportato, D19-8 rimandata) | approvato |

## Analisi (livello 2)

| File | Descrizione | Stato |
|---|---|---|
| `20-analisi-fotometria.md` | Fotometria di apertura e PSF, calibrazione | non esiste |
| `21-analisi-spettroscopia.md` | Analisi degli spettri: lettura, dereddening, misure di linea | non esiste |
| `22-analisi-curve-di-luce.md` | Curve di luce: fasi, detrending, periodogrammi | non esiste |
| `23-analisi-cubi-di-dati.md` | Cubi di dati: estrazione spettri, maschere, moment maps | non esiste |
| `24-analisi-pipeline-riproducibili.md` | Pipeline riproducibili, registro e riesecuzione delle operazioni. In Aladin la cronologia dei comandi registra anche le azioni fatte con il mouse come comandi di script; **AstroTwo adotta lo stesso principio: ogni azione dell'interfaccia = un comando registrato** (dal 2026-10-15 registro dei comandi e sessione nel `05-comandi-sessione.md`, livello 1; il 24 costruirà pipeline e scripting sopra il 05) | non esiste |

## IA (livello 3)

| File | Descrizione | Stato |
|---|---|---|
| `30-ia-adattatore-provider.md` | Adattatore per i provider IA (v1): profili senza chiave, SDK `anthropic` e `openai` con endpoint configurabile, capacità, `list_models`, `stream_turn` con eventi normalizzati, `AI_NO_TOOLS`, tempi 10/60/30 s, `RequestRecord` | approvato |
| `31-ia-chiavi-portachiavi.md` | Chiavi API nel Portachiavi di macOS (v1): `keyring` con il solo backend macOS forzato, nessun ripiego, `SecretKey` mascherato | approvato |
| `32-ia-registro-strumenti.md` | Registro degli strumenti (v1): elenco esplicito di comandi del `05`, nomi tradotti, validazione del `05`, stessa coda con `requested_by = ai`, conferme, risultati ≤ 50 righe e 20 kB; testi esterni marcati come dati | approvato |
| `33-ia-query-adql.md` | Costruzione, validazione ed esecuzione di query ADQL (**rimandato** il 2026-10-16; nella v1 `catalog.search`) | non esiste |
| `34-ia-verifica-risultati.md` | Verifica dei numeri delle risposte (v1): estrazione di tutti i numeri, elenco chiuso delle eccezioni, confronto alla precisione scritta, evidenziazione, modalità rigorosa; nessuna istruzione letta dai risultati | approvato |
| `35-ia-assistente-chat.md` | Assistente conversazionale (v1): ciclo degli strumenti, regole di sistema R1–R9, limiti (10 comandi, 5 minuti), token e prezzo facoltativo, privacy, sessione, sicurezza contro le istruzioni nei testi esterni | approvato |

## Interfaccia

| File | Descrizione | Stato |
|---|---|---|
| `40-ui-finestra-principale.md` | Finestra principale (v1): menu, barra di stato, campo "Vai a", preferenze essenziali, pannelli Comandi e Messaggi, coda dei comandi in un thread di lavoro con avanzamento e Annulla, spazio per il 44; A9 decisa (inglese con `tr()`, italiano nostro, punto decimale sempre); D40-1 decisa, D40-2 rimandata, D40-3 aperta (Gruppo 3); **linee guida visive** (§3.11) per tutte le interfacce; mockup in `mdfiles/mockup/`; dal 2026-10-16 pannello dell'assistente (44) nella v1, colonna "chi" nella cronologia, preferenze dell'assistente | approvato |
| `41-ui-visualizzatore-cielo.md` | Visualizzatore del cielo (v1): immagine FITS, sfondo HiPS, cataloghi, MOC, griglia, coordinate sotto il mouse, distanza, puntatore Simbad, livelli minimi, PNG; geometria da `make_view_wcs` (10) e tile dal 12 (P6); OpenGL dietro un'interfaccia di disegno nostra; obiettivi di prestazione P1–P7; D10-9, D11-8 e D41-1…D41-4 decise (Mac di riferimento da compilare); modalità notte rossa nel disegno; dal 2026-10-16 nord e barra di scala (A7) con `compass_and_scale_bar` del 10 | approvato |
| `42-ui-pannello-cataloghi.md` | Pannello cataloghi (v1 minima): tabella in sola lettura con ordinamento, selezione sincronizzata con la vista, vista del record; colonne di posizione e moto proprio; dal 2026-10-16 posizioni con `format_coordinates` del 10 e magnitudini a 3 decimali | approvato |
| `mockup/finestra-principale.html`, `mockup/finestra-principale-notte.html`, `mockup/finestra-principale-ia.html` | Mockup statici della finestra principale (tema scuro, modalità notte rossa, pannello dell'assistente), valori fittizi; solo immagine di riferimento per il 40 §3.11 e il 44, non codice dell'app né file di specifica (non contati nel riepilogo) | — |
| `43-ui-pannello-analisi.md` | Pannello analisi: grafici e risultati dei moduli di livello 2 | non esiste |
| `44-ui-pannello-ia.md` | Pannello dell'assistente (v1): a destra, 380–420 pt; messaggi, schede dei comandi e di conferma, numeri verificati ed evidenziati, token, "Cosa è stato inviato", impostazioni con la chiave tramite il `31`, consenso al primo uso; mockup `mockup/finestra-principale-ia.html` | approvato |
| `45-ui-viste-multiple.md` | Viste multiple 2/4/9/16 con sincronizzazione, blocco e miniature (interfaccia; origine H2 di `03-parita-aladin.md`; dipende da `41`, `40`) | non esiste |

## Funzioni avanzate (livello 4)

| File | Descrizione | Stato |
|---|---|---|
| `50-avanzate-transienti.md` | Caccia e monitoraggio di transienti | non esiste |
| `51-avanzate-multi-messaggero.md` | Integrazione di dati multi-messaggero (ad es. neutrini, onde gravitazionali, FRB) | non esiste |
| `52-avanzate-collaborazione.md` | Collaborazione e condivisione tra utenti | non esiste |
| `53-avanzate-vista-3d.md` | Vista 3D dello spazio stellare | non esiste |

## Distribuzione e test

| File | Descrizione | Stato |
|---|---|---|
| `60-distribuzione-dmg.md` | Costruzione, firma, notarizzazione e consegna del `.dmg`; **bundle identifier `dev.pages.astrotwo`** (decisione del proprietario del 2026-10-16, `01` §6); **vincolo (2026-10-09): WCSLIB, incluso in astropy, è LGPL-3** — obblighi di distribuzione da rispettare nel `.dmg`; **vincolo (2026-10-15): PySide6 e Qt sono LGPL-3** (interfaccia), stessi obblighi; **dal 2026-10-13 il `.dmg` deve includere `THIRD_PARTY_LICENSES`** (avvisi di tutte le dipendenze, compresi QD/LBNL, NAIF, LGPL-3 con la GPL-3 per riferimento; testo di `pims` da recuperare) | non esiste |
| `61-strategia-test.md` | Strategia dei test: unitari, integrazione, confronto con riferimenti; qui vanno definiti gli obiettivi di prestazioni **almeno pari ad Aladin** (righe di catalogo, dimensione di immagini e cubi — §8 di `01-architettura.md`) | non esiste |

## Riepilogo

| Stato | Quanti |
|---|---|
| bozza | 5 |
| in revisione | 0 |
| approvato | 24 |
| non esiste | 14 |
| **Totale file in `mdfiles/`** | **43** |
