# riassunto.md — il progetto in 5 righe

**Stato:** bozza

1. **Cos'è:** AstroTwo è il successore di Aladin per gli astrofisici: app desktop macOS consegnata come `.dmg`, con nucleo scientifico Python 3.12 pari ad Aladin e più (P11), interfaccia PySide6, IA a capacità con provider e chiavi scelti dall'utente.
2. **Struttura:** 4 livelli che devono funzionare sempre — 1 nucleo (10–19), 2 analisi (20–24), 3 IA (30–35), 4 avanzate (50–53), più interfaccia (40–45) e distribuzione/test (60–61); le dipendenze vanno solo verso il basso (`4 → 3 → 2 → 1`).
3. **Regole d'oro:** l'IA non calcola mai (ogni numero viene da codice deterministico testato), le chiavi API vivono solo nel Portachiavi di macOS, ogni operazione è registrata e rieseguibile, prima la specifica `.md` approvata poi il codice, AstroTwo è scritto da zero (nulla preso da Aladin, n. 8).
4. **Stato (2026-11-14 — sprint D14):** D62-8 decisa e corretta (VOTable validi rispetto allo schema con ID univoci, «Immagini: completata» nel PDF italiano, nessuna etichetta italiana nell'interfaccia inglese; controlli nella suite per lo schema dei VOTable e per la lingua); lettura 180 s per i provider IA locali; build 8 scartato, **candidato 1.0.0 build 9** autorizzato; **regola di stop**: dopo il build 9 solo un difetto bloccante giustifica un build 10, gli altri vanno nella lista «1.0.1». 16 decisioni aperte, nessuna blocca la 1.0.
5. **Prossimi passi:** candidato build 9 e parte automatica del megatest sul build 9 (sprint D14); megatest a mano di Guido (con le tre immagini del README); approvazione del `62` e delle note di rilascio; nuova misura di VizieR e SIMBAD contro il CDS quando torna; poi, con il via del proprietario, tag e release.
