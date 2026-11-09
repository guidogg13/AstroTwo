# riassunto.md — il progetto in 5 righe

**Stato:** bozza

1. **Cos'è:** AstroTwo è il successore di Aladin per gli astrofisici: app desktop macOS consegnata come `.dmg`, con nucleo scientifico Python 3.12 pari ad Aladin e più (P11), interfaccia PySide6, IA a capacità con provider e chiavi scelti dall'utente.
2. **Struttura:** 4 livelli che devono funzionare sempre — 1 nucleo (10–19), 2 analisi (20–24), 3 IA (30–35), 4 avanzate (50–53), più interfaccia (40–45) e distribuzione/test (60–61); le dipendenze vanno solo verso il basso (`4 → 3 → 2 → 1`).
3. **Regole d'oro:** l'IA non calcola mai (ogni numero viene da codice deterministico testato), le chiavi API vivono solo nel Portachiavi di macOS, ogni operazione è registrata e rieseguibile, prima la specifica `.md` approvata poi il codice, AstroTwo è scritto da zero (nulla preso da Aladin, n. 8).
4. **Stato (2026-11-09 — sprint C8b, tempi del profilo):** `20` (solo parte SED), `25` e `43` approvati; profilo di un oggetto completo con esportazione, SAMP e strumento IA `object__profile`; D25-21 e D25-22 decise e applicate (`25` §3.17: Cone Search di IRSA, `refresh` una volta per profilo, VizieR saltata con il CDS giù, tempo di sezione dalla partenza, 2 richieste per servizio, Gaia non richiesta con l'archivio già fermo, Astrometria 35 s); profili tra 4 e 29 s con l'archivio Gaia su (misure del 2026-11-09 sera); aperte 19. Piano dei rilasci: niente beta 6, dalla beta 5 alla 1.0 con megatest; Fase D registrata (`CITATION.cff`, pagina di validazione, documentazione in inglese).
5. **Prossimi passi:** prove a mano del profilo e di C6b; specifica del megatest prima della 1.0 e delle voci della Fase D quando il proprietario lo chiede; quando il CDS torna, D43-3 e SED vera di VizieR per T8 del 20.
