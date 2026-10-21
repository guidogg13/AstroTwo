# Risposta registrata di TAP VizieR: Gaia DR3 attorno ad Alcyone

Usata da T35 del 13 e T34 del 41 (D41-6), senza rete.

- **Servizio:** `https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync` (CDS, Strasburgo), tabella `I/355/gaiadr3`.
- **Registrata il:** 2026-10-21 da Claude Code con `load_catalog("I/355/gaiadr3", region=(ICRS 56.75°, 24.1167°;
  1′), max_rows=100)` del 13, catturando le tre risposte del 14 (`_http`) senza modificarle.
- **File:** `tap_schema.xml` (UCD delle colonne da `TAP_SCHEMA.columns`), `top0.xml` (`SELECT TOP 0` con il `COOSYS`
  ICRS `epoch="2016.0"`), `region.xml` (11 righe nel cerchio).
- **Crediti:** questi dati vengono dalla missione Gaia dell'ESA (https://www.cosmos.esa.int/gaia), elaborati dal
  Gaia Data Processing and Analysis Consortium (DPAC); il servizio è VizieR del CDS (Strasburgo, Francia).
- **Condizioni d'uso:** questi file non sono coperti dalla GPL di AstroTwo; licenza CC BY-NC 3.0 IGO dei dati Gaia
  e regole d'uso di VizieR, con i link ufficiali, in [`../README.md`](../README.md). Permesso esplicito di
  ridistribuzione in un repository GPL: da verificare.
