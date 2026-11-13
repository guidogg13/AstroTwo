# riassunto.md — il progetto in 5 righe

**Stato:** bozza

1. **Cos'è:** AstroTwo è il successore di Aladin per gli astrofisici: app desktop macOS consegnata come `.dmg`, con nucleo scientifico Python 3.12 pari ad Aladin e più (P11), interfaccia PySide6, IA a capacità con provider e chiavi scelti dall'utente.
2. **Struttura:** 4 livelli che devono funzionare sempre — 1 nucleo (10–19), 2 analisi (20–24), 3 IA (30–35), 4 avanzate (50–53), più interfaccia (40–45) e distribuzione/test (60–61); le dipendenze vanno solo verso il basso (`4 → 3 → 2 → 1`).
3. **Regole d'oro:** l'IA non calcola mai (ogni numero viene da codice deterministico testato), le chiavi API vivono solo nel Portachiavi di macOS, ogni operazione è registrata e rieseguibile, prima la specifica `.md` approvata poi il codice, AstroTwo è scritto da zero (nulla preso da Aladin, n. 8).
4. **Stato (2026-11-13 — sprint D13):** decise e corrette D05-7 e D62-2…D62-7; **candidato 1.0.0 build 8** (`2784e5a`, `.dmg` `96419e22…8c58`, V1–V10 ok con la prova di fumo della finestra Profili dentro l'app); prove automatiche sul build 8: D62-2 corretto (grafico SED, Export… e catalogo SED dal menu), unità di Gaia via SAMP presenti; nuova **D62-8** (ID `A2NOTE` ripetuti nei VOTable dei cataloghi, «Immagini: done» nel PDF italiano; consiglio build 9). 17 decisioni aperte, D62-8 da decidere prima del rilascio.
5. **Prossimi passi:** decisione su **D62-8** (build 9 o limiti dichiarati); megatest a mano di Guido (con le tre immagini del README e I2 con un modello locale più piccolo); approvazione del `62` e delle note di rilascio; nuova misura di VizieR e SIMBAD contro il CDS quando torna; poi, con il via del proprietario, tag e release.
