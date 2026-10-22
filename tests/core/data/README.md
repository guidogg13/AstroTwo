# Dati di test

**Nessun dato di terze parti.** Dal 2026-10-22 (decisione del proprietario) i dati di test sono **sintetici**: stelle
inventate, generate da [`scripts/make_synthetic_catalog.py`](../../../scripts/make_synthetic_catalog.py) con seme
fisso, e coperti dalla licenza di AstroTwo (GPL-3.0-or-later). I precedenti file di Gaia DR3 (CC BY-NC 3.0 IGO, uso
non commerciale) sono stati rimossi dal ramo attuale.

## `synthetic_vizier/` — risposta TAP sintetica

Usata da T35 del 13 e T34 del 41 (D41-6), senza rete, tramite `tests/core/synthetic_catalog.py`.

- **Struttura:** tre VOTable come quelle di un servizio TAP: `tap_schema.xml` (UCD delle colonne), `top0.xml`
  (`SELECT TOP 0`, con il `COOSYS` ICRS `epoch="2016.0"`), `region.xml` (11 stelle inventate in un cerchio di 1′
  attorno a RA 56.75°, Dec 24.1167°, con moto proprio, parallasse e magnitudini; una riga su quattro senza moto
  proprio né parallasse).
- **Colonne:** `DR3Name`, `RA_ICRS`, `DE_ICRS`, `Source`, `e_RA_ICRS`, `e_DE_ICRS`, `Plx`, `e_Plx`, `pmRA`, `e_pmRA`,
  `pmDE`, `e_pmDE`, `Gmag`, `BPmag`, `RPmag`, con unità e UCD nello stesso stile del catalogo reale. Il nome del
  catalogo `I/355/gaiadr3` serve solo a farlo riconoscere ai test; **i valori non sono quelli di Gaia**.
- **Rigenerare:** `uv run python scripts/make_synthetic_catalog.py`.
