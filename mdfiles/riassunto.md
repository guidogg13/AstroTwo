# riassunto.md — il progetto in 5 righe

**Stato:** bozza

1. **Cos'è:** AstroTwo è il successore di Aladin per gli astrofisici: app desktop macOS consegnata come `.dmg`, con nucleo scientifico Python 3.12 pari ad Aladin e più (P11), interfaccia PySide6, IA a capacità con provider e chiavi scelti dall'utente.
2. **Struttura:** 4 livelli che devono funzionare sempre — 1 nucleo (10–19), 2 analisi (20–24), 3 IA (30–35), 4 avanzate (50–53), più interfaccia (40–45) e distribuzione/test (60–61); le dipendenze vanno solo verso il basso (`4 → 3 → 2 → 1`).
3. **Regole d'oro:** l'IA non calcola mai (ogni numero viene da codice deterministico testato), le chiavi API vivono solo nel Portachiavi di macOS, ogni operazione è registrata e rieseguibile, prima la specifica `.md` approvata poi il codice, AstroTwo è scritto da zero (nulla preso da Aladin, n. 8).
4. **Stato (2026-11-13 — sprint D13a):** il proprietario ha deciso D05-7 e D62-2…D62-7; corrette nel codice: `backend_qtagg` di nuovo nell'app e **prova di fumo V10 della finestra Profili dentro l'app costruita** (fa fallire il build), unità esatte nei VOTable e FITS di tabella e unità di Gaia conservate, messaggio «il profilo richiede un oggetto SIMBAD», CSV non confermato che non blocca gli altri caricamenti, lingua e aspetto, testo della `62`. 16 decisioni aperte, nessuna blocca la 1.0. Candidato ancora da ricostruire (build 8).
5. **Prossimi passi:** candidato 1.0.0 **build 8** (`63` passi 3–8, passo 7 saltato) e parte automatica del megatest sul build 8; poi megatest a mano di Guido (con le tre immagini del README); test `gaia_circle` da riprovare prima del rilascio; approvazione del `62` e delle note di rilascio; nuova misura di VizieR e SIMBAD contro il CDS quando torna; poi, con il via del proprietario, tag e release.
