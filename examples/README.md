# Esempi di AstroTwo

Script dimostrativi che usano **solo le funzioni pubbliche** del livello 1 di AstroTwo. Gli script non fanno calcoli
scientifici propri: chiamano AstroTwo e si occupano di disegnare e stampare, come farà l'interfaccia (regola d'oro
n. 1). I risultati vanno in `examples/output/`, esclusa da git.

## `demo_pleiadi.py` — Pleiadi (M45) con dati veri

Richiede la rete (SIMBAD, servizio SIA della DSS dell'ESO, archivio Gaia dell'ESA, IRSA). I dati scaricati restano
nella cache comune di AstroTwo (`~/Library/Caches/AstroTwo/`), quindi la seconda esecuzione è più veloce.

```sh
uv run python examples/demo_pleiadi.py            # mostra la figura a schermo se possibile
uv run python examples/demo_pleiadi.py --no-show  # scrive solo i file
```

Passi (modulo di AstroTwo usato):

1. centro del campo con `resolve_name("M45")` (10);
2. immagine DSS2-red di 2° × 2° con WCS: `sia_search` sul servizio SIA della DSS dell'ESO (14, trovato nel registro VO)
   e `load_image` (11). Il 12 non offre una funzione pubblica "HiPS → immagine con WCS" e SkyView (H10) è rinviato;
3. stelle Gaia DR3 entro 1° con G < 11: `tap_query` sull'archivio Gaia dell'ESA (14), tabella del 13;
4. frecce del moto proprio con `proper_motion_arrows` (13), scala dichiarata nella figura (spostamento in 5000 anni);
   medie con `column_statistics` (13), anche sui probabili membri scelti con `search` per parallasse (criterio
   dichiarato);
4b. epoca di visualizzazione (D10-2): posizioni Gaia propagate all'epoca dell'immagine DSS (`MJD-OBS`, 1989-12-17)
    con `propagate` (13); spostamento medio e massimo con `skydist` in `calculated_column` e `column_statistics` (13).
    Le stelle si disegnano alle posizioni propagate; frecce, crossmatch, distanza Alcyone–Atlas e MOC restano
    all'epoca dei dati, dichiarata nel report;
5. crossmatch con 2MASS (`tap_query` su IRSA, `crossmatch` del 15 con raggio esplicito di 2″); percentuale con la
   calcolatrice algebrica del 18;
6. distanza angolare e angolo di posizione Alcyone–Atlas con `angular_distance` e `position_angle` (17);
7. MOC del campo dell'immagine con `moc_from_image` e controllo delle stelle con `filter_by_moc` (16);
8. figura con matplotlib e assi WCS (`astropy.visualization.wcsaxes`): presentazione con `set_display` (11),
   posizioni in pixel con `sky_to_pixel` (10) all'epoca dell'immagine, dimensione dei cerchi con `set_plot_rules` (13);
9. report `examples/output/demo_pleiadi.txt`: ogni numero con unità, sistema/epoca, funzione e libreria.

Uscite: `examples/output/demo_pleiadi.png`, `examples/output/demo_pleiadi.txt`.
Test di rete: `tests/test_demo_pleiadi.py` (marcatore `network`).
