# riassunto.md — il progetto in 5 righe

**Stato:** bozza

1. **Cos'è:** AstroTwo è il successore di Aladin per gli astrofisici: app desktop macOS consegnata come `.dmg`, con nucleo scientifico Python 3.12 pari ad Aladin e più (P11), interfaccia PySide6, IA a capacità con provider e chiavi scelti dall'utente.
2. **Struttura:** 4 livelli che devono funzionare sempre — 1 nucleo (10–19), 2 analisi (20–24), 3 IA (30–35), 4 avanzate (50–53), più interfaccia (40–45) e distribuzione/test (60–61); le dipendenze vanno solo verso il basso (`4 → 3 → 2 → 1`).
3. **Regole d'oro:** l'IA non calcola mai (ogni numero viene da codice deterministico testato), le chiavi API vivono solo nel Portachiavi di macOS, ogni operazione è registrata e rieseguibile, prima la specifica `.md` approvata poi il codice, AstroTwo è scritto da zero (nulla preso da Aladin, n. 8).
4. **Stato (2026-11-09 — sprint C8, tempi del profilo):** `20` (solo parte SED), `25` e `43` approvati; profilo di un oggetto completo con esportazione, SAMP e strumento IA `object__profile`; D25-21 approvata e applicata (`25` §3.17: Cone Search di IRSA, `refresh` dal principale una volta per profilo, VizieR saltata con il CDS giù, tempo di sezione dalla partenza, al più 2 richieste per servizio); 1229 test passati; aperte 20 (nuova D25-22, scelte minori e due proposte, da confermare).
5. **Prossimi passi:** il proprietario conferma D25-22 (in particolare (12): niente altre richieste Gaia con l'archivio già fermo nel profilo e/o Astrometria 35 s); misura T17 da rifare quando l'archivio Gaia risponde (il 2026-11-09 era fermo); prove a mano del profilo e di C6b (esportazione, catalogo dei punti, SAMP con TOPCAT vero, profilo chiesto all'assistente); quando il CDS torna, D43-3 e SED vera di VizieR per T8 del 20.
