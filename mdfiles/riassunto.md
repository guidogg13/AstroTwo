# riassunto.md — il progetto in 5 righe

**Stato:** bozza

1. **Cos'è:** AstroTwo è il successore di Aladin per gli astrofisici: app desktop per macOS consegnata come `.dmg` (Windows e Linux in arrivo con la 1.1, `65`), con nucleo scientifico Python 3.12 pari ad Aladin e più (P11), interfaccia PySide6, IA a capacità con provider e chiavi scelti dall'utente.
2. **Struttura:** 4 livelli che devono funzionare sempre — 1 nucleo (10–19), 2 analisi (20–24), 3 IA (30–35), 4 avanzate (50–53), più interfaccia (40–45) e distribuzione/test (60–65); le dipendenze vanno solo verso il basso (`4 → 3 → 2 → 1`).
3. **Regole d'oro:** l'IA non calcola mai (ogni numero viene da codice deterministico testato), le chiavi API vivono solo nell'archivio sicuro del sistema (Portachiavi di macOS; Gestione credenziali su Windows, Secret Service su Linux), ogni operazione è registrata e rieseguibile, prima la specifica `.md` approvata poi il codice, AstroTwo è scritto da zero (nulla preso da Aladin, n. 8).
4. **Stato (2026-11-17 — sprint D15):** **AstroTwo 1.0.0 rilasciata** per macOS: tag `v1.0.0` su `499e110`, release su GitHub con il `.dmg` `0a4f78ac…0281`, DOI di Zenodo `10.5281/zenodo.24314750` (concept `10.5281/zenodo.24314749`). Megatest superato (tre prove non fatte per Gaia e CDS giù). Lista «1.0.1»: pannello dell'assistente (righe tagliate), immagini del README. **Windows e Linux** (W1, W2a, W2b su `main`, Mac 1.0 invariato) escono con la 1.1.
5. **Prossimi passi:** passi 15 (ORCID) e 16 (sito) della `63`, di Guido; poi la 1.0.1 (lista del `64` §3.9) e la validazione non misurata quando il CDS risponde. Per Windows e Linux: primo run dei workflow, correzione dei fallimenti reali, D65-6 e D65-11, poi W3 (licenze, megatest in UTM, rilascio 1.1).
