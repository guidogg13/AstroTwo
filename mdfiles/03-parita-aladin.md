# 03-parita-aladin.md — funzioni di Aladin e modulo di AstroTwo che le copre

**Stato:** approvato

## 1. Scopo

Elencare tutte le funzioni di Aladin (CDS, Strasburgo) che AstroTwo deve
riprodurre, indicando per ciascuna il modulo di AstroTwo responsabile, così da
misurare la parità e non dimenticare nulla.

## 2. Fonti, stato della verifica e cautele

**Fonti usate per la verifica documentale (esito del 2026-10-04):**

- Manuale utente di Aladin Desktop, **edizione giugno 2022, sezioni 1–5.8**.
- **Manuale dei comandi di script, versione 12.0.**
- **FAQ ufficiale.**
- Manuale utente di Aladin Desktop, **edizione giugno 2022, sezioni 5.9–8** —
  lettura AP5 completata il 2026-10-08.
- Manuale utente di Aladin Desktop, **edizione febbraio 2021: sezioni 1–5.7.2 e
  indice completo** — esito **parziale** di AP5 (2026-10-04).

**Edizione di riferimento del manuale: giugno 2022 (AP6, decisa il
2026-10-08, §6)** — la più recente ufficiale pubblicata dal CDS (verificato il
2026-10-08 sul sito di Aladin). I numeri di sezione del manuale citati in
questo file si riferiscono a questa edizione; quelli ricavati dall'indice
dell'edizione febbraio 2021 sono stati riportati alla numerazione
dell'edizione giugno 2022 il 2026-10-08 (eccezione: H18, la cui sezione non
esiste più nell'edizione giugno 2022; vedi riga H18).

**Nota sulla numerazione di AP5:** "5.7.3–8" si riferiva all'ed. febbraio
2021, "5.9–8" all'ed. giugno 2022. Le due diciture coprono però parti diverse
del manuale: nelle due edizioni le sezioni 5.7.3–5.8 hanno lo stesso numero
(5.7.3 calcolatrice dei pixel … 5.8 gestore dei filtri di catalogo; l'ed.
giugno 2022 aggiunge 5.7.5 calcolatrice del tempo). La differenza nasce da
quanto era già stato letto: dell'ed. febbraio 2021 le sezioni 1–5.7.2, dell'ed.
giugno 2022 le sezioni 1–5.8 (prima verifica documentale). Con l'edizione di
riferimento giugno 2022 resta quindi da leggere **5.9–8**.

**Stato:** **AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022)
completata il 2026-10-08.** Le sezioni 1–8 dell'edizione di riferimento sono
tutte lette: la verifica documentale delle righe sotto è completa (esistenza e
dettagli). Esiti integrati in §3: note aggiunte alle righe esistenti, correzioni
di D12 (SExtractor su server remoto del CDS), E3 (correlazione per campo e per
ellissi) e F4 (le serie temporali esistono in Aladin), nuove righe H20–H27, una
proposta AM1 (H21, dati planetari), accettata il 2026-10-08 come
`19-core-dati-planetari.md`.

**Colonna "Copertura":**

| Valore | Significato |
|---|---|
| `nota` | funzione già nota alla prima stesura, non oggetto di questo passaggio di verifica (invariata) |
| `verificata` | confermata nella documentazione senza modifiche |
| `corretta` | verificata e corretta rispetto alla formulazione precedente |
| `non trovata` | non trovata nella documentazione letta |
| `inclusa (decisione del proprietario)` | non confermata dalla documentazione, ma inclusa in AstroTwo per decisione del proprietario: resta solo la verifica tecnica su come implementarla, non l'esistenza in Aladin |
| `extra` | non è una funzione di Aladin (vedi §5) |

Conteggio attuale: 59 righe in A–G (`nota` 19, `verificata` 24, `corretta` 12,
`inclusa (decisione del proprietario)` 4) + 27 righe in H + 0 righe extra =
**86 righe** (dal 2026-10-08: H20–H27 dalla lettura AP5). Nessuna riga `non trovata` rimane aperta dal 2026-10-04.

Altre note:

- Il confronto finale dei risultati con Aladin resta la decisione **AP1**
  (§6), **rimandata alla fine del progetto**; è riportata in `panoramica.md`
  sempre come AP1.
- Gli ID della colonna `#` (A1, B3, H10, …) sono identificativi **locali** delle
  righe di questa tabella: la lettera è la sezione (A–H) e il numero è la riga.
  Non c'entrano con le etichette delle decisioni, che in questo file sono solo
  `AP1`–`AP5` e negli altri file `A1`–`A9`/`AM1` (vedi `01-architettura.md`,
  `panoramica.md`).
- Nessuna riga di questa tabella autorizza da sola a scrivere codice: serve il
  file `.md` del modulo in stato `approvato`.

## 3. Tabella di parità

### A. Navigazione e vista di base

| # | Funzione di Aladin | Cosa fa | Modulo AstroTwo | Copertura | Note |
|---|---|---|---|---|---|
| A1 | Pan e zoom | Spostare e ingrandire il campo con mouse/rotella | `41-ui-visualizzatore-cielo.md` | nota | |
| A2 | Vai a per nome oggetto | Risolvere un nome (es. "M31") in coordinate e centrare | `10-core-coordinate-wcs.md`, `41-ui-visualizzatore-cielo.md` | nota | |
| A3 | Vai a coordinate | Centrare su coordinate inserite in diversi sistemi | `10-core-coordinate-wcs.md`, `41-ui-visualizzatore-cielo.md` | nota | |
| A4 | Lettura coordinate del cursore | Mostrare le coordinate puntate, in più sistemi | `10-core-coordinate-wcs.md`, `41-ui-visualizzatore-cielo.md` | nota | |
| A5 | Conversione, precessione e calcolatrice coordinate | Convertire tra sistemi di coordinate ed epoche; calcolatrice delle coordinate (calcolo inverso). Le altre calcolatrici sono in H4 | `10-core-coordinate-wcs.md` | corretta | aggiunte le calcolatrici |
| A6 | Griglia di coordinate | Reticolo di RA/Dec sovrapposto al campo | `10-core-coordinate-wcs.md`, `41-ui-visualizzatore-cielo.md` | verificata | |
| A7 | Barra di scala e indicatore nord | Orientamento e scala angolare in vista | `41-ui-visualizzatore-cielo.md` | verificata | |
| A8 | Rotazione / nord in alto | Orientamento della vista: rotazione libera **solo per le mappe HiPS**; per le immagini classiche **solo nord in alto** | `41-ui-visualizzatore-cielo.md` | corretta | rotazione libera limitata ai HiPS |
| A9 | Scelta della proiezione | Proiezione celeste usata (TAN, AIT, ecc.) | `10-core-coordinate-wcs.md`, `11-core-immagini-fits.md` | verificata | la proiezione cambia l'immagine solo per le mappe HiPS; per le immagini classiche cambia solo il sistema di riferimento; proiezioni gestite (sez. 5.14, ed. giugno 2022): SIN, TAN, AIT, ZEA, STG, CAR, NCP, ZPN e altre (elenco del manuale non esaustivo) — dato utile per D10-4 in `10` |
| A10 | Schermo intero | Modalità a tutto schermo | `40-ui-finestra-principale.md` | verificata | |
| A11 | Pannello layer | Elenco livelli, ordine, visibilità, opacità, rinomina, elimina | `41-ui-visualizzatore-cielo.md` | nota | |
| A12 | Preferenze, cronologia e segnalibri | Impostazioni persistenti, cronologia dei comandi, storico delle posizioni, segnalibri, preferenze. **Aladin non ha "annulla"** | `40-ui-finestra-principale.md` | corretta | rimosso "annulla": non esiste in Aladin |
| A13 | Screenshot / export immagine | Salvare la vista come immagine | `41-ui-visualizzatore-cielo.md` | verificata | include anche la **stampa** (sezione 5.19 "Backups, exports and printing", ed. giugno 2022); formati della vista BMP, JPEG, PNG, EPS; export dei piani: immagini FITS/JPEG/PNG, cataloghi TSV/VOTable, MOC FITS/JSON; backup della pila `.aj` (sez. 5.19, ed. giugno 2022); mappa cliccabile: H20 |

### B. Immagini

| # | Funzione di Aladin | Cosa fa | Modulo AstroTwo | Copertura | Note |
|---|---|---|---|---|---|
| B1 | Caricamento FITS locali | Aprire un file FITS dal disco | `11-core-immagini-fits.md` | nota | |
| B2 | Caricamento immagini da URL | Aprire un'immagine da un indirizzo remoto | `11-core-immagini-fits.md` | verificata | |
| B3 | Regolazione luminosità e contrasto | Regolare la scala di visualizzazione | `11-core-immagini-fits.md` | nota | |
| B4 | Istogramma / CTF | Regolazione della trasferenza tramite istogramma | `11-core-immagini-fits.md` | verificata | |
| B5 | Trasparenza e sovrapposizione | Miscelare più layer di immagine | `11-core-immagini-fits.md`, `41-ui-visualizzatore-cielo.md` | nota | |
| B6 | Palette / color map | Colorizzazione di immagini monocrome | `11-core-immagini-fits.md` | verificata | |
| B7 | Ricampionamento e match delle viste | **Non esiste "align"**: si ricampiona una immagine sulla soluzione astrometrica di un'altra e si fa il match delle viste | `11-core-immagini-fits.md` | corretta | "align" non esiste; metodi: pixel più vicino o bilineare; il manuale avverte che **il flusso non è conservato**; alternativa più rapida e meno precisa: semitrasparenza basata sui 4 angoli (sez. 5.17, ed. giugno 2022) |
| B8 | Cutout / stamp FITS | Estrarre una sottoparte dell'immagine | `11-core-immagini-fits.md` | verificata | |
| B9 | Immagini non FITS (JPEG, PNG) | Caricamento di immagini in altri formati | `11-core-immagini-fits.md` | verificata | |
| B10 | Visualizzazione cubi di dati | Cursore per scorrere le immagini del cubo e strumento **Spect** per il profilo in profondità | `23-analisi-cubi-di-dati.md` | corretta | niente "iper-scala" |
| B11 | Coniugazione / composizione multibanda | Combinare immagini a bande diverse; comprende **mosaici e sequenze animate (blink)** | `11-core-immagini-fits.md` | verificata | mosaici e sequenze animate con blink; RGB da 2 o 3 immagini con ricampionamento sul pixel più vicino (con 2 immagini la terza componente è la media; modalità differenza `RGBdiff`) (sez. 5.15); mosaico con media nelle sovrapposizioni e senza correzione del fondo; cubo come sequenza animata (sez. 5.16, ed. giugno 2022) |

### C. Servizi di immagini all-sky (HiPS)

| # | Funzione di Aladin | Cosa fa | Modulo AstroTwo | Copertura | Note |
|---|---|---|---|---|---|
| C1 | Sfoglio dei survey HiPS | Navigare le immagini all-sky per survey | `12-core-hips.md` | nota | |
| C2 | Survey predefiniti | HiPS noti (DSS, SDSS, Pan-STARRS, Gaia, ecc.) | `12-core-hips.md` | nota | |
| C3 | Caricamento HiPS da ID/URL | Aggiungere un HiPS non in elenco | `12-core-hips.md` | inclusa (decisione del proprietario) | inclusa il 2026-10-04; implementazione in `12-core-hips.md` §3/§7/§10 |
| C4 | Impronta (footprint) del survey | Vedere la copertura del survey | `16-core-moc.md` | verificata | |

### D. Cataloghi e tabelle

| # | Funzione di Aladin | Cosa fa | Modulo AstroTwo | Copertura | Note |
|---|---|---|---|---|---|
| D1 | Cataloghi del CDS | Caricare cataloghi noti (Hipparcos, TYCHO-2, Gaia, 2MASS, ecc.) | `13-core-cataloghi.md` | nota | |
| D2 | Tabelle da file locale | Aprire VOTable, CSV, tabelle FITS | `13-core-cataloghi.md`, `14-core-protocolli-vo.md` | nota | |
| D3 | Tabelle da URL | Caricare una tabella da rete | `13-core-cataloghi.md`, `14-core-protocolli-vo.md` | verificata | |
| D4 | Plottaggio delle sorgenti | Simboli, colori e dimensioni in funzione dei campi (es. magnitudine) | `13-core-cataloghi.md`, `42-ui-pannello-cataloghi.md` | nota | |
| D5 | Etichette | Testo accanto alle sorgenti | `42-ui-pannello-cataloghi.md` | nota | |
| D6 | Filtri del catalogo e ricerca per espressione | I **filtri** decidono **come disegnare** le sorgenti; la selezione dei record per espressione è il comando **`search`** | `13-core-cataloghi.md`, `42-ui-pannello-cataloghi.md` | corretta | in precedenza filtraggio e selezione erano mescolati |
| D7 | Tabella sincronizzata con la vista | Selezionare in tabella evidenzia in vista e viceversa | `42-ui-pannello-cataloghi.md` | nota | |
| D8 | Ordinamento e ricerca in tabella | Ordinare/ricercare righe | `42-ui-pannello-cataloghi.md` | verificata | |
| D9 | Propagazione delle posizioni | Portare le posizioni a un'epoca con i moto propri | `13-core-cataloghi.md` | verificata | |
| D10 | Freccia del moto proprio | Rappresentare il moto proprio delle sorgenti | `13-core-cataloghi.md` | verificata | |
| D11 | Selezione grafica | Selezione con **clic** e con **rettangolo**; cerchio e poligono servono per la fotometria e per i MOC | `41-ui-visualizzatore-cielo.md`, `42-ui-pannello-cataloghi.md` | corretta | cerchio e poligono non sono strumenti di selezione |
| D12 | Estrazione di sorgenti dall'immagine | Soglia / region growing per trovare le sorgenti nell'immagine | `20-analisi-fotometria.md` | verificata | In Aladin l'estrazione **esiste** (sezione 6.6, ed. giugno 2022) **tramite SExtractor eseguito su un server remoto del CDS** (il manuale precisa che Aladin non ha strumenti nativi di estrazione automatica); in AstroTwo sarà **nativa**, nel modulo 20, senza programmi esterni — libreria da decidere |
| D13 | Esportazione tabelle | Salvare in CSV, VOTable, FITS | `14-core-protocolli-vo.md` | verificata | |

### E. Query e protocolli VO

| # | Funzione di Aladin | Cosa fa | Modulo AstroTwo | Copertura | Note |
|---|---|---|---|---|---|
| E1 | Cone search | Interrogare un catalogo in un raggio attorno a un punto | `14-core-protocolli-vo.md` | nota | |
| E2 | Advanced query / ADQL | Scrivere ed eseguire query ADQL sui servizi TAP | `14-core-protocolli-vo.md`, `33-ia-query-adql.md` | nota | |
| E3 | Cross-match | Due modalità: **locale** tra due tabelle e **servizio CDS**; il locale ha le modalità tutte / migliore / nessuna e distanza massima predefinita 4 arcsec; il correlatore locale ha anche la correlazione **per campo** (join su valori identici, es. un identificatore) e la correlazione **per posizione con ellissi d'errore** (asse maggiore, asse minore, orientamento); scelta delle colonne da tenere con suffissi/prefissi; corrispondenza delle colonne tramite UCD | `15-core-crossmatch.md` | corretta | distanza massima predefinita locale: 4 arcsec; tre modalità del correlatore locale (sez. 5.11, ed. giugno 2022): posizione, campo, ellissi — aggiunte il 2026-10-08 (lettura AP5) |
| E4 | Spettri (SSA) | Caricare e mostrare spettri dai servizi VO | `21-analisi-spettroscopia.md` (caricamento SSA: `14-core-protocolli-vo.md`) | inclusa (decisione del proprietario) | inclusa il 2026-10-04; ricerca/caricamento in `14-core-protocolli-vo.md`, analisi in `21`. Secondo una **FAQ vecchia**, Aladin carica gli spettri ma per **mostrarli** serve un programma esterno via SAMP; **AstroTwo li mostra nel modulo 21**; SAMP trasporta anche spettri (sez. 6.4); estrazione di spettri da cubo con spect/phot/draw e analisi nel programma esterno CASSIS, installabile come plugin (sez. 6.5, ed. giugno 2022) |
| E5 | VOTable | Lettura e scrittura di VOTable | `14-core-protocolli-vo.md` | nota | |
| E6 | MOC | MOC **spaziali, temporali e spazio-temporali**; creazione da immagini, cataloghi, poligoni, cerchi e mappe di probabilità; operazioni di unione, intersezione, sottrazione e complemento; filtro delle sorgenti per MOC | `16-core-moc.md` | corretta | molto più ampio del "sovrapponi MOC" della prima stesura |
| E7 | File di regione (es. DS9) | Sovrapporre regioni annotate | `41-ui-visualizzatore-cielo.md` | verificata | |
| E8 | Save/load della sessione | Salvare e ripristinare lo stato della finestra | `24-analisi-pipeline-riproducibili.md`, `40-ui-finestra-principale.md` | verificata | il formato `.AJ` conserva solo i pixel a 8 bit |

### F. Misure e strumenti

| # | Funzione di Aladin | Cosa fa | Modulo AstroTwo | Copertura | Note |
|---|---|---|---|---|---|
| F1 | Distanza angolare | Misurare la separazione tra due punti | `17-core-misure.md` | nota | misura automatica della distanza tra due sorgenti di catalogo selezionate (sez. 5.9, ed. giugno 2022); su immagine il manuale consiglia il centroide baricentrico dello strumento phot |
| F2 | Position angle | Misurare l'angolo di posizione | `17-core-misure.md` | inclusa (decisione del proprietario) | inclusa il 2026-10-04; implementazione in `17-core-misure.md` §3/§7/§10 |
| F3 | Lettura di valori pixel / fotometria | Leggere il valore in un punto dell'immagine | `17-core-misure.md`, `20-analisi-fotometria.md` | verificata | |
| F4 | Fotometria | Automatica su stella (centro baricentrico, ellisse) e statistica su cerchio o poligono (conteggio, media, deviazione standard, minimo, massimo, somma). Le **serie temporali** esistono come grafici (vedi H8 e H17) | `20-analisi-fotometria.md` | corretta | **corretto il 2026-10-08 (lettura AP5):** Aladin ha grafici di serie temporali (sez. 5.12 "Scatter plot / time series") e grafici flusso-tempo dal puntatore VizieR (sez. 5.10, ed. giugno 2022); l'analisi delle curve di luce in AstroTwo resta nel modulo 22. **Su HiPS in Aladin la fotometria è solo con cerchio manuale e alla risoluzione della vista**; AstroTwo deve **dichiarare la risoluzione usata** e, quando possibile, **misurare alla risoluzione nativa** |
| F5 | Misure da cubo | Spettro o profilo da un cubo | `23-analisi-cubi-di-dati.md` | verificata | spettro da cubo anche come media su cerchio o poligono (strumenti phot e draw, sez. 6.5, ed. giugno 2022) |

### G. Automazione, integrazioni, sessione

| # | Funzione di Aladin | Cosa fa | Modulo AstroTwo | Copertura | Note |
|---|---|---|---|---|---|
| G1 | Linguaggio di scripting | Eseguire sequenze di azioni scriptate | `24-analisi-pipeline-riproducibili.md` | verificata | comandi da console, campo comandi, file, standard input e metodo Java `execCommand`; piani della pila usabili come variabili (`Nome = comando`, `@n`), anche per l'aritmetica tra immagini (sez. 7.1, ed. giugno 2022) |
| G2 | Integrazione con altri programmi | Trovati **plugin Java**, **hub SAMP interno**, **libreria IDL-Aladin**; **API Python non trovata** | `14-core-protocolli-vo.md` (hub SAMP); eventuale API Python di AstroTwo: `24-analisi-pipeline-riproducibili.md` | corretta | plugin Java e libreria IDL non riproducibili in Python; plugin Java con Plugin Manager (sez. 7.3), libreria IDL (sez. 7.5, ed. giugno 2022) |
| G3 | Apertura in strumenti esterni | Inviare la selezione ad altri strumenti (es. TOPCAT) | `42-ui-pannello-cataloghi.md` (protocollo SAMP: `14-core-protocolli-vo.md`) | inclusa (decisione del proprietario) | inclusa il 2026-10-04; SAMP in `14-core-protocolli-vo.md`, interfaccia in `42`; SAMP (sez. 6.4, ed. giugno 2022): elenco di applicazioni installabili e avviabili dal menu, invio e ricezione di cataloghi, immagini e spettri (non HiPS), selezione sincronizzata tra applicazioni |
| G4 | Panoramica / mappa di riferimento | Minimappa con il campo corrente | `41-ui-visualizzatore-cielo.md` | verificata | |
| G5 | Riquadro campo e campi strumentali (FoV) | Riquadro del campo nella minimappa e **campi strumentali (FoV) di telescopi, anche personalizzati in XML** | `41-ui-visualizzatore-cielo.md` | corretta | aggiunti i FoV dei telescopi |

### H. Funzioni di Aladin trovate nella documentazione e mancanti

Trovate nella verifica documentale del 2026-10-04 (H1–H19) e nella lettura AP5
del 2026-10-08 (H20–H27), **mancanti nella prima stesura di questo file**. Sono tutte funzioni esistenti in Aladin: il modulo
indicato è quello che dovrà coprirle (da aggiungere alle rispettive specifiche).

| # | Funzione di Aladin | Cosa fa | Modulo AstroTwo | Copertura | Note |
|---|---|---|---|---|---|
| H1 | Albero delle collezioni | Albero delle collezioni con oltre 20.000 voci, filtri per regole, ordinamento, colori dei dati nel campo | `41-ui-visualizzatore-cielo.md` | verificata | estensione del pannello layer (A11); filtraggio delle collezioni tramite MocServer: H26 |
| H2 | Viste multiple | Viste multiple 2/4/9/16 con sincronizzazione, blocco e miniature | `45-ui-viste-multiple.md` | verificata | modulo accettato in AM1 il 2026-10-04 (stato `non esiste`, si scrive col gruppo interfaccia); miniature: una vista bloccata per oggetto (oggetti selezionati o tutto un catalogo), comando `thumbnail` (sez. 6.7, ed. giugno 2022) |
| H3 | Filtro temporale e cursore epoca | Filtro temporale sui dati e cursore per spostare l'epoca di visualizzazione | `13-core-cataloghi.md`, `41-ui-visualizzatore-cielo.md` | verificata | |
| H4 | Calcolatrici | Calcolatrici algebrica, unità, pixel, coordinate e tempo | `18-core-calcolatrici.md`; coordinate e tempo rientrano anche in A5 (`10-core-coordinate-wcs.md`), pixel in `11-core-immagini-fits.md` | verificata | modulo accettato in AM1 il 2026-10-04 (stato `non esiste`, si scrive col nucleo) |
| H5 | Operazioni su immagini | Aritmetica tra immagini, convoluzione, normalizzazione, cambio formato pixel, specchiatura | `11-core-immagini-fits.md` | verificata | somma, differenza, prodotto, divisione con ricampionamento automatico e normalizzazione opzionale; convoluzione con matrici predefinite (Gauss, Mex, Tophat) o personali, il cui risultato sostituisce l'immagine (sez. 5.18, ed. giugno 2022) |
| H6 | Calibrazione astrometrica | Calibrazione astrometrica di immagini e di tabelle prive di coordinate | `10-core-coordinate-wcs.md` | verificata | se il perimetro di 10 diventa troppo ampio → valutare modulo dedicato (AM1); dettagli (sez. 5.14, ed. giugno 2022): calibrazione da intestazione WCS, commento JPEG/PNG, file `.hhh` o liste SIA; più soluzioni per immagine; creazione o modifica per parametri, per associazione di stelle (centroide baricentrico) o per intestazione WCS; annulla/ripeti |
| H7 | Contorni (isofote) | Contorni / isofote sull'immagine | `11-core-immagini-fits.md` | verificata | |
| H8 | Strumenti di tabella avanzati | Colonne calcolate, sottoinsiemi, grafico x-y, istogramma delle colonne, DataLink, vista a record, descrizione delle colonne | `13-core-cataloghi.md`, `42-ui-pannello-cataloghi.md` | verificata | grafico x-y e serie temporali con sovrapposizione dei MOC temporali (sez. 5.12); colonne calcolate con nome, unità, UCD, decimali ed espressione `${colonna}` (sez. 5.13, ed. giugno 2022) |
| H9 | Generazione di HiPS e MOC | Generazione di HiPS e di MOC, anche da riga di comando | `12-core-hips.md`, `16-core-moc.md` | verificata | Hipsgen da interfaccia (schede: dati, tile FITS, tile JPEG/PNG, pubblicazione, HiPS RGB classico o Lupton) o con `-hipsgen`; parametri BLANK, HDU, fondo cielo automatico, dissolvenza, bordi, regione; Mocgen per MOC spaziali da collezioni di immagini, anche MOC temporali e spazio-temporali (sez. 6.2–6.3, ed. giugno 2022) — utile per D12-1 |
| H10 | Schede server | SkyView, Gaia, SkyBot, VO generica, server personali | `14-core-protocolli-vo.md`, `12-core-hips.md` | verificata | |
| H11 | Strumenti grafici | Distanza con profilo, disegno libero, tag, spettro da cubo, forme di disegno | `17-core-misure.md`, `41-ui-visualizzatore-cielo.md`, `23-analisi-cubi-di-dati.md` | verificata | |
| H12 | Cataloghi HiPS progressivi e HEALPix | Cataloghi HiPS progressivi, mappe HEALPix, griglia HEALPix | `12-core-hips.md`, `16-core-moc.md` | verificata | |
| H13 | Strumenti di sessione e aiuto | Segnalibri, console con cronologia, tour guidato, modalità demo, interfaccia multilingua | `40-ui-finestra-principale.md` | verificata | in parte sovrappone A12; da chiarire in 40; console degli script con tutte le azioni dell'interfaccia come comandi, anche delle sessioni precedenti (sez. 5.22); segnalibri = funzioni di script con `$TARGET` e `$RADIUS` (sez. 5.20); modalità "Wizard" di aiuto contestuale ed editor delle traduzioni dell'interfaccia (sez. 5.21, ed. giugno 2022) |
| H14 | Interoperabilità SAMP e plugin | Hub SAMP verso TOPCAT, DS9, SPLAT, CASSIS; sistema di plugin | `14-core-protocolli-vo.md` (SAMP); `24-analisi-pipeline-riproducibili.md` (estensioni tramite API Python, al posto dei plugin) | verificata | SAMP letto (sez. 6.4, vedi G3); plugin Java (sez. 7.3); CASSIS come plugin (sez. 6.5, ed. giugno 2022); **D14-7 (2026-10-09): nessun sistema di plugin nel livello 1**, la parte "plugin" è spostata nel 24 (estensioni tramite l'API Python) |
| H15 | Righe di comando | `-script`, `-nogui`, macro con file di parametri, funzioni utente | `24-analisi-pipeline-riproducibili.md` | verificata | legata ad A8 (compatibilità rimandata dopo il livello 1); opzioni da riga di comando (sez. 7.2, ed. giugno 2022): `-script`, `-nogui`, `-hipsgen`, `-mocgen`, `-local`, `-theme`, `-screen`, `-nosamp`, `-noplugin`, `-[no]planet` e altre; macro con variabili `$1`, `$2` su liste di valori, anche prese da un catalogo (sez. 6.1) |
| H16 | Impostazioni di sessione e preferenze utente | Segnalibri, funzioni, colori e altre preferenze utente | `40-ui-finestra-principale.md` | verificata | in parte sovrappone A12; da chiarire in 40; preferenze (sez. 5.21, ed. giugno 2022): lingua, tema, scala dell'interfaccia, cartella predefinita, sistema e proiezione predefiniti, server predefiniti, stile della griglia, dimensione della cache, filtro delle estensioni FITS, statistiche d'uso anonime verso il CDS (opzionali), dati planetari (H21); file `.aladin.conf` |
| H17 | Strumento "Exam" | Strumento **Exam** (sezione 5.10, ed. giugno 2022: "study" in inglese, « examen » in francese; era la 5.9 nell'ed. febbraio 2021): **puntatore Simbad** (tenendo fermo il mouse: identificatore, magnitudine, tipo e coordinate dell'oggetto più citato entro 1/20 della vista; link alla pagina Simbad e alla bibliografia) e **puntatore fotometrico VizieR** (SED costruita dalle misure di flusso dei cataloghi vicini, in lunghezza d'onda o frequenza; punti salvabili come nuovo piano di catalogo; grafico flusso-tempo se le misure sono datate) | `41-ui-visualizzatore-cielo.md` (puntatore), `14-core-protocolli-vo.md` (interrogazioni Simbad/VizieR), `20-analisi-fotometria.md` (costruzione della SED), `43-ui-pannello-analisi.md` (grafico) | verificata | dettagli letti il 2026-10-08 (AP5). Il manuale avverte che i punti della SED non sono garantiti dello stesso oggetto né confrontabili: in AstroTwo ogni punto con origine dichiarata; la costruzione della SED è un calcolo deterministico (regola d'oro n. 1), **la SED si costruisce nel modulo 20 (fotometria)**, ogni punto con origine dichiarata (decisione del proprietario, 2026-10-08) |
| H18 | Avvio tramite URL | Apertura di Aladin da un URL / collegamento (ed. febbraio 2021 sezione 7.2 "Launch of Aladin by URL"; **nell'ed. giugno 2022 la sezione non esiste più**: la 7.2 è "Launch of Aladin from the command line" e l'avvio da URL compare solo nella sezione 2 "Installation", come link Java WebStart) — **dettagli da leggere** | `40-ui-finestra-principale.md` (modulo proposto) | verificata | nell'ed. giugno 2022 la sezione "Launch of Aladin by URL" non c'è più: resta solo il link Java WebStart di installazione e avvio (sez. 2 "Installation"); nell'ed. febbraio 2021 (sez. 7.2) l'URL accettava anche un parametro `script=` eseguito all'avvio. **Riga mantenuta per P11**; in AstroTwo (app `.dmg`, senza Java WebStart) l'equivalente va definito in `40` — da decidere |
| H19 | Interfacce VOApp e VOObserver | Interfacce Java **VOApp** (9 metodi: invio e ricezione di VOTable e FITS, mostra/seleziona oggetti, visibilità, esecuzione di comandi, registrazione di osservatori) e **VOObserver** (posizione e valore del pixel al clic) — sezione 7.4, ed. giugno 2022 | `24-analisi-pipeline-riproducibili.md` (API Python), `14-core-protocolli-vo.md` (SAMP) | verificata | dettagli letti il 2026-10-08 (AP5): interfacce Java nella stessa macchina virtuale, secondo il manuale 100–1000 volte più veloci di SAMP; in AstroTwo (Python) non riproducibili tali e quali: **equivalente deciso il 2026-10-08 (decisione del proprietario): API Python nel `24` come strada principale + SAMP nel `14` per gli altri programmi; nessuna interfaccia nuova** |
| H20 | Mappa cliccabile (PNG+LINK) | Salvataggio della vista in PNG con un file `.lnk` che elenca le sorgenti cliccabili (posizione nell'immagine e URL del record), per mappe web (sez. 5.19, ed. giugno 2022) | `41-ui-visualizzatore-cielo.md` (modulo proposto) | verificata | trovata con la lettura AP5 del 2026-10-08 |
| H21 | Dati planetari | Accesso a superfici, cataloghi e coperture planetarie: ramo "Solar System" dell'albero delle collezioni, attivabile nelle preferenze, fornito dal manuale "as is" senza garanzia di coerenza; immagini PDS; EpnTAP (sez. 5.21, 7.2, 8.1, ed. giugno 2022) | `19-core-dati-planetari.md` | verificata | **AM1 accettata il 2026-10-08 (decisione del proprietario):** nuovo modulo `19-core-dati-planetari.md`, livello 1 (stato `non esiste` alla registrazione); i sistemi di riferimento planetari non previsti in `10` stanno nel 19 |
| H22 | Formati di dati e riconoscimento automatico | Formati supportati (sez. 8.1, ed. giugno 2022): immagini FITS (anche compresse RICE/GZIP/HCOMP, MEF, RGB, cubi), JPEG/PNG/GIF con WCS; cataloghi VOTable, ASTRORES, IPAC TBL, FITS ASCII e binari, TSV/CSV/BSV, formato SExtractor; MOC 1.0–2.1 (anche JSON); mappe HEALPix e mappe di probabilità multi-ordine (LIGO/Virgo); regioni DS9 e IDL; FoV; script AJS; backup AJ; GZIP. La **natura del file si riconosce dal contenuto**, non dall'estensione (eccezione: script AJS) | `11-core-immagini-fits.md`, `13-core-cataloghi.md`, `14-core-protocolli-vo.md`, `16-core-moc.md` | verificata | limiti dichiarati dal manuale (es. meno di 1 milione di sorgenti per catalogo, cubi fino a 1024×512×512): riferimento per gli obiettivi di `61-strategia-test.md` |
| H23 | Liste di immagini SIA/SIA2 | Accesso a liste di immagini con i protocolli IVOA SIA e SIA2 (IDHA per compatibilità), con calibrazione presa dalla lista (sez. 5.14, 8.1, ed. giugno 2022) | `14-core-protocolli-vo.md` | verificata | IDHA: nessuna documentazione pubblica del formato trovata (2026-10-10); AstroTwo apre il file in modo sicuro e lo rifiuta con `IDHA_UNREADABLE` (D14-9 punto 13 del 14); SIA e SIA2 coperti per intero |
| H24 | Cubi HiPS | Survey progressivi a cubo (HiPS cube, tile FITS/JPEG/PNG) (sez. 8.1, ed. giugno 2022) | `12-core-hips.md`, `23-analisi-cubi-di-dati.md` | verificata | |
| H25 | Convenzione dei pixel FITS e calibrazioni storiche | Primo pixel (1,1) centrato sulla posizione, angolo inferiore sinistro a (0.5, 0.5) come nello standard FITS (IDL usa 0.0); riconoscimento di calibrazioni storiche (metodo DSS1) (sez. 8.2, ed. giugno 2022) | `10-core-coordinate-wcs.md`, `11-core-immagini-fits.md` | verificata | convenzione da riportare anche in `02-convenzioni.md` (proposta); regola scritta come **DC7** in `02-convenzioni.md` §6 il 2026-10-08 (FITS indice da 1, numpy indice da 0, conversione unica nel modulo 10) |
| H26 | Filtraggio delle collezioni tramite MocServer | Filtro spaziale delle collezioni sul server remoto MocServer del CDS e filtro locale delle proprietà, sincronizzate all'avvio (sez. 8.3.3, ed. giugno 2022) | `12-core-hips.md`, `16-core-moc.md`, `41-ui-visualizzatore-cielo.md` | verificata | collegata a H1 |
| H27 | Immagini di qualsiasi dimensione | Strategie per dimensione: in memoria, su disco, lettura a due livelli di risoluzione per immagini di più gigabyte; HiPS caricati per tile con cache su disco; contatore della memoria usata (sez. 8.3–8.3.1, ed. giugno 2022) | `11-core-immagini-fits.md`, `12-core-hips.md` | verificata | obiettivi misurabili in `61-strategia-test.md` (`01-architettura.md` §8); per i cataloghi il manuale indica circa 1 milione di sorgenti con 1 GB di RAM (sez. 8.3.2) |

## 4. Funzioni di Aladin non ancora inquadrate e nota di licenza

- **Aladin Lite** (widget web incorporabile in pagine HTML): **escluso dalla
  parità** (AP3, decisa il 2026-10-08) — AstroTwo è un'app desktop;
  un'eventuale versione web richiederà una proposta AM1.
- Qualsiasi altra funzione emersa dalla verifica documentale (**AP5 decisa;
  lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08**:
  l'unica funzione senza modulo trovata è H21, dati planetari, accettata in
  AM1 il 2026-10-08 come `19-core-dati-planetari.md`) che non
  trovi posto in un modulo esistente va segnalata in "Decisioni aperte" di
  `panoramica.md` (voce **AM1**), non aggiunta di iniziativa.
- **Nota di licenza:** Aladin Desktop e Aladin Lite sono distribuiti in
  **GPL v3**. Se si copia codice da Aladin, anche AstroTwo dovrebbe essere
  distribuito in GPL. Riscrivere una funzione partendo dalla **documentazione**
  è consentito. **Da ricontrollare sempre prima di copiare qualsiasi codice.**

## 5. Funzioni extra di AstroTwo (non in Aladin)

Funzioni previste da AstroTwo che **non risultano in Aladin**: non contano nella
misurazione della parità. Sono di **livello 2** e vanno nella specifica del
modulo indicato.

**Al 2026-10-04 nessuna riga extra:** l'unica riga `X1` (estrazione di
sorgenti) è tornata nella sezione D come **D12 `verificata`** — in Aladin
l'estrazione esiste (sezione 6.6, ed. giugno 2022), ma **tramite il programma esterno
SExtractor**; in AstroTwo sarà nativa nel modulo 20 (vedi §3, D12).

## 6. Decisioni aperte

- **AP1 — Validazione finale della parità: RIMANDATA.** Si esegue **alla fine
  del progetto**, confrontando AstroTwo e Aladin sugli **stessi dati** (stessi
  file FITS, stesse coordinate, stessi cataloghi, stesse query) e verificando
  che i risultati coincidano entro le tolleranze definite nei singoli moduli.
  Nel frattempo resta fermo l'obbligo di §2: ogni riga `non trovata` va chiusa
  prima dell'approvazione del modulo interessato (al 2026-10-04 nessuna riga
  `non trovata`: C3, F2, G3, E4 sono `inclusa (decisione del proprietario)`);
  le righe `verificata` e `corretta` sono a posto per la parte documentale.
- **AP2 — Profondità della parità: DECISA il 2026-10-09 (decisione del
  proprietario sulla checklist del livello 1).** Parità **funzionale** per
  default (stesso risultato, interfaccia di AstroTwo); parità **completa**
  solo per i formati di file e, con A8, per i comandi di script.
- **AP3 — Aladin Lite: DECISA il 2026-10-08 (decisione del proprietario).**
  Aladin Lite è **escluso dalla parità** perché AstroTwo è un'app desktop;
  un'eventuale versione web richiederà una proposta AM1 (`panoramica.md`).
- **AP4 — Scripting legacy:** decidere se AstroTwo esegue gli script di Aladin
  oppure ha solo il proprio formato di pipeline. Rinvia ad **A8**
  (`01-architettura.md` e `panoramica.md`): strada scelta = scripting
  principale in Python; compatibilità con i comandi di Aladin da decidere dopo
  il livello 1.
- **AP5 — Verifica documentale residua:** **AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) completata il 2026-10-08** (decisa il
  2026-10-04). Le sezioni **5.9–8 (ed. giugno 2022)** del manuale utente di Aladin **si leggono
  e si integrano in questo file prima di scrivere i gruppi successivi** (prima
  di `20-analisi-fotometria.md` … `24-analisi-pipeline-riproducibili.md` e dei
  gruppi successivi). **Motivazione:** il costo della lettura è basso ora,
  mentre dopo costringerebbe a modificare specifiche già scritte e a rischiare
  i test T2/T5; finché la lettura non è fatta la parità documentale non si
  dichiara completa. Le funzioni nuove trovate che non hanno modulo vanno in
  AM1. **Esito parziale (2026-10-04):** fonte = manuale utente **edizione
  febbraio 2021**; lette le **sezioni 1–5.7.2 e l'indice completo**; l'esistenza
  di tutte le funzioni è verificata dall'indice; restavano da leggere i
  dettagli delle sezioni 5.7.3–8 di quell'edizione (vedi nota in §2).
  **Esito finale (2026-10-08):** lette le sezioni 5.9–8 dell'ed. giugno 2022;
  esiti in §2 e §3 (note, correzioni D12/E3/F4, righe H20–H27, proposta AM1
  per H21).
- **AP6 — Edizione di riferimento del manuale di Aladin: DECISA il
  2026-10-08 (decisione del proprietario).** Edizione di riferimento = la più
  recente ufficiale del manuale utente di Aladin Desktop. Verifica del
  2026-10-08 sul sito del CDS: i manuali pubblicati (inglese
  `AladinManual.pdf`, francese `AladinManuel.pdf`) sono l'**edizione giugno
  2022** e non risulta un'edizione più recente → riferimento = **giugno
  2022**. I numeri di sezione citati in questo file (AP5, righe A13, D12,
  H17–H19, §5) e in `01-architettura.md` §8 (sezione 8.3) si riferiscono a
  questa edizione (riportati alla sua numerazione il 2026-10-08; per H18 la
  sezione dell'ed. febbraio 2021 non esiste più).
- AP1 e AP4 sono registrate anche in `decisioni-aperte.md` (Gruppo 3);
  AP2 (2026-10-09) e AP3 (2026-10-08) sono chiuse.

## 7. Test di accettazione

| # | Descrizione | Passi | Atteso | Verifica |
|---|---|---|---|---|
| T1 | Ogni riga ha un modulo esistente o una proposta esplicita | Confrontare la colonna "Modulo AstroTwo" con l'elenco file in `INDICE.md` | nessun riferimento a un file inesistente, salvo le righe marcate `proposta (→ AM1)` (nessuna dal 2026-10-08: H21 punta a `19-core-dati-planetari.md`; H2, H4 e H21 puntano ai moduli accettati in AM1) | rilevamento manuale o script di controllo sui riferimenti |
| T2 | Nessuna riga irrisolta quando un modulo è approvato | Filtrare la colonna "Copertura" sulle righe che puntano al modulo da approvare | 0 righe `non trovata` e 0 righe con Copertura vuota o diversa da `nota`/`verificata`/`corretta`/`inclusa (decisione del proprietario)`/`extra` | rilevamento manuale |
| T3 | Parità minima del livello 1 | Confrontare le righe A–F con i file `10-…`–`19-…` | tutte le righe con Copertura `nota`, `verificata` o `corretta` che puntano a un modulo di livello 1 con file in stato `approvato` | rilevamento manuale |
| T4 | Confronto finale con Aladin (AP1, rimandata) | Scegliere una serie di casi (es. stesso campo, stessa coppia di coordinate, stessa query) ed eseguirli in Aladin e in AstroTwo | stessi risultati entro le tolleranze dichiarate nei moduli 10–19; tolleranze e casi da definire al momento di eseguire il test | confronto diretto sui medesimi dati, registrato in `panoramica.md` |
| T5 | Nessuna riga della sezione H senza modulo | Contare le righe H con modulo assegnato o proposta AM1 | 27 su 27 | rilevamento manuale |

## 8. Registro modifiche

| Data | Chi | Cosa è cambiato |
|---|---|---|
| 2026-10-04 | agente di sviluppo | Creazione del file (stato: bozza). Elenco provvisorio: 59 righe, di cui 38 "da verificare" da validare con la documentazione ufficiale. |
| 2026-10-04 | agente di sviluppo | AP1 ridefinita e **rimandata**: validazione finale della parità alla fine del progetto, per confronto dei risultati sugli stessi dati (prima: verifica documentale da fare subito). AP4 rinvia ad A8 (scripting in Python, compatibilità Aladin dopo il livello 1). Riferimento in §2 e §4 aggiornato da A7/A8 di `panoramica.md` ad AP1/AM1. Aggiunto il test T4. |
| 2026-10-04 | agente di sviluppo | **Esito della verifica documentale** (manuale utente Aladin Desktop ed. giugno 2022 sezioni 1–5.8, manuale script v12.0, FAQ): nuova colonna Copertura con valori `nota`/`verificata`/`corretta`/`non trovata`/`extra`; 23 righe verificate; 12 righe corrette (A5, A8, A12, B7, B10, D6, D11, E3, E6, F4, G2, G5); 4 righe non trovate (C3, E4, F2, G3); D12 spostata in §5 come extra AstroTwo; aggiunta la sezione H con 16 funzioni mancanti (H1–H16); nota di licenza GPL v3 in §4; nuova decisione AP5 (sezioni 5.7.3–8 [indicate in origine come 5.9–8] ancora da leggere); test T2 aggiornato e aggiunto T5. Colonne: aggiunta la colonna Note. |
| 2026-10-04 | agente di sviluppo | **Decisione del proprietario: la parità con Aladin è il minimo, non il traguardo — AstroTwo include tutte le funzioni di questo file, anche non confermate nella documentazione.** Nuovo valore di Copertura `inclusa (decisione del proprietario)`; le 4 righe `non trovata` (C3, E4, F2, G3) passano a `inclusa (decisione del proprietario)`: restano solo verifiche tecniche su come implementarle. Aggiornati conteggio §2, legenda, AP1/AP2 e test T2; funzioni descritte per intero in `12-core-hips.md` (C3), `17-core-misure.md` (F2), `14-core-protocolli-vo.md` (G3 SAMP, E4 SSA). Principio registrato in `panoramica.md` (P11) e `01-architettura.md` §2. |
| 2026-10-04 | agente di sviluppo | **AM1 decisa:** accettate le proposte H2 e H4 — le righe H2 e H4 ora puntano a `45-ui-viste-multiple.md` e `18-core-calcolatrici.md` (registrati in `panoramica.md` e `INDICE.md` con stato `non esiste`); aggiornato il test T1 (nessuna riga `proposta (→ AM1)` residua). |
| 2026-10-04 | agente di sviluppo | **AP5 DECISA (decisione del proprietario):** le sezioni 5.7.3–8 [indicate in origine come 5.9–8] del manuale utente di Aladin si leggono e si integrano in questo file **prima di scrivere i gruppi successivi** (prima di 20–24 e dei gruppi seguenti); motivazione: evitare riscritture di specifiche già scritte e proteggere i test T2/T5. §2 e §4 aggiornati di conseguenza; nessun conteggio righe cambia. |
| 2026-10-04 | agente di sviluppo | **Esito parziale di AP5 + correzioni dalla verifica (manuale utente ed. febbraio 2021, sezioni 1–5.7.2 e indice completo):** AP5 resta **aperta** per i dettagli delle sezioni 5.7.3–8, mentre l'esistenza di tutte le funzioni è verificata dall'indice (§2, §4, §6). **D12 correzione:** l'estrazione di sorgenti in Aladin **esiste** (sezione 6.5, tramite il programma esterno SExtractor) → la riga **D12 è tornata nella sezione D come `verificata`** (AstroTwo: estrazione **nativa** nel modulo 20, senza programmi esterni, libreria da decidere) e §5 "funzioni extra" è ora senza righe. Aggiunte **H17** (strumento Exam, 5.9), **H18** (avvio tramite URL, 7.2), **H19** (interfacce VOApp/VOObserver, 7.5), tutte con "dettagli da leggere" e modulo proposto. Note aggiunte alle righe **A13** (stampa, 5.18), **B11** (mosaici e sequenze animate con blink), **E4** (vecchia FAQ: mostra gli spettri via programmi esterni SAMP; AstroTwo li mostra nel 21), **F4** (fotometria su HiPS in Aladin = cerchio manuale e risoluzione della vista; AstroTwo dichiara la risoluzione usata e, se possibile, misura alla risoluzione nativa). Conteggi §2: 59 righe A–G (`verificata` 24) + 19 H + 0 extra = 78; test T5 → 19 su 19. |
| 2026-10-08 | Claude Code | Manutenzione: nuova decisione aperta **AP6 — edizione di riferimento del manuale di Aladin** (giugno 2022 o febbraio 2021), nota in §2 e voce in §6; nessuna edizione scelta. Nei registri precedenti il riferimento AP5 "5.9–8" è annotato come 5.7.3–8 (riferimento corretto). Nessun conteggio righe cambia. |
| 2026-10-08 | Claude Code | **AP6 DECISA (decisione del proprietario):** edizione di riferimento = la più recente ufficiale del manuale utente di Aladin Desktop; verifica sul sito del CDS: **giugno 2022** (nessuna edizione più recente). §2 e §6 aggiornati. Accanto ai numeri di sezione del manuale (A13, D12, H17–H19, §5) indicata l'edizione; dove nell'ed. giugno 2022 numero o titolo è diverso, marcato "numerazione da verificare" (non corretto). AP5 scritta in modo uniforme ("AP5 decisa; lettura delle sezioni 5.7.3–8 ancora da fare") in §2, §4, §6. Test T3/T4: moduli 10–18. AP1–AP4 registrate anche in `decisioni-aperte.md`. Refusi: "reproducerlo" → "riprodurlo" (§4), "mostro" → "mostra" (registro). |
| 2026-10-08 | Claude Code | **Numeri di sezione riportati all'ed. giugno 2022** (decisione del proprietario): A13 → 5.19, D12 → 6.6 (riga e §5), H19 → 7.4, H17 → 5.10 ("study"/« examen »; era 5.9 nell'ed. febbraio 2021); tolta la marcatura "numerazione da verificare". H18: la sezione 7.2 "Launch of Aladin by URL" dell'ed. febbraio 2021 non esiste nell'ed. giugno 2022 (7.2 = avvio da riga di comando; l'avvio da URL compare solo in §2 "Installation") → riga mantenuta (P11) con la fonte 2021. AP5 scritta come "AP5 decisa; lettura delle sezioni 5.9–8 (ed. giugno 2022) ancora da fare"; nota sulla numerazione in §2. **AP3 DECISA:** Aladin Lite escluso dalla parità (app desktop; versione web → proposta AM1), §4 e §6. |
| 2026-10-08 | Claude Code | **Lettura AP5 completata:** sezioni 5.9–8 del manuale utente ed. giugno 2022. §2: fonti, stato e conteggi (59 A–G + 27 H + 0 extra = 86). §3: note aggiunte con sezione ed edizione ad A9, A13, B7, B11, E4, F1, F5, G1, G2, G3, H1, H2, H5, H6, H8, H9, H13, H14, H15, H16; **D12 corretta** (SExtractor eseguito su server remoto del CDS); **E3 estesa** (correlazione per campo e per ellissi d'errore); **F4 corretta** (le serie temporali esistono in Aladin, sez. 5.10 e 5.12); H17 (puntatori Simbad e VizieR/SED), H18 (sezione assente nell'ed. 2022, riga mantenuta per P11) e H19 (VOApp/VOObserver) con i dettagli letti; nuove righe **H20–H27** (mappa cliccabile, dati planetari, formati, SIA/SIA2, cubi HiPS, convenzione dei pixel FITS, MocServer, immagini di qualsiasi dimensione); **H21 proposta AM1** (nessun file creato). §4 e §6 (AP5 completata), test T1 e T5 (27 su 27) aggiornati. |
| 2026-10-08 | Claude Code | **Decisioni del proprietario:** H21 → `19-core-dati-planetari.md` (AM1 accettata; §2, §4, test T1 aggiornati); H17: SED costruita nel modulo 20, ogni punto con origine dichiarata (modulo aggiunto alla riga); H19: equivalente di VOApp = API Python nel 24 (strada principale) + SAMP nel 14, nessuna interfaccia nuova; H25: convenzione dei pixel scritta come DC7 in `02-convenzioni.md`. Conteggi invariati (86 righe). |
| 2026-10-09 | Claude Code | **AP2 DECISA** (checklist del livello 1): parità funzionale per default, completa solo per i formati di file e, con A8, per i comandi di script. |
| 2026-10-09 | Claude Code | **Stato portato ad `approvato`** su decisione del proprietario del 2026-10-09. |
| 2026-10-09 | Claude Code | Riga H14: la parte "plugin" è spostata in `24-analisi-pipeline-riproducibili.md` (D14-7, (decisione del proprietario): nessun sistema di plugin nel livello 1, estensioni tramite l'API Python). Stato `approvato` invariato. |
| 2026-10-10 | Claude Code | Riga H23 (autorizzazione esplicita del proprietario a modificare il file approvato, solo questa riga): annotato che il formato IDHA non ha documentazione pubblica e che AstroTwo dà solo `IDHA_UNREADABLE` (D14-9 punto 13 del 14). Stato `approvato` invariato. |
