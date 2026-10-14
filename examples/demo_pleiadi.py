"""Demo delle Pleiadi (M45): primo test di AstroTwo con dati veri.

Uso (dalla radice del progetto)::

    uv run python examples/demo_pleiadi.py            # figura a schermo se possibile
    uv run python examples/demo_pleiadi.py --no-show  # solo i file

Scrive ``examples/output/demo_pleiadi.png`` (figura) e ``examples/output/demo_pleiadi.txt`` (report).

Lo script **non fa calcoli scientifici propri**: chiama solo funzioni pubbliche di AstroTwo (livello 1) e si occupa
di disegnare e stampare, come farà l'interfaccia (regola d'oro n. 1: ogni numero viene da codice deterministico e
testato). Anche la percentuale del crossmatch e le medie del moto proprio vengono da funzioni di AstroTwo
(calcolatrice algebrica del 18, ``column_statistics`` del 13). Le uniche scelte scritte qui sono parametri
dichiarati dall'utente (raggi, soglie, scala delle frecce, limiti di visualizzazione), riportati nel report.

Immagine: la via supportata dalle API pubbliche è il **SIA del 14** (``sia_search``) + ``load_image`` dell'11. Il 12
non ha una funzione pubblica "HiPS → immagine con WCS" (il WCS dei tile è interno a ``build_hips``) e SkyView (H10)
è rinviato: si usa il servizio SIA della DSS dell'ESO, trovato nel registro VO (``ivo://eso.org/dss``).
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import astropy.units as u
import matplotlib
import numpy as np

from astrotwo.core.calculators import evaluate_expression
from astrotwo.core.catalogs import (
    PlotRule,
    SizeScale,
    column_statistics,
    confirm_position_columns,
    display_positions,
    search,
    set_plot_rules,
    subset,
)
from astrotwo.core.coordinates_wcs import SkyFrame, resolve_name, sky_to_pixel
from astrotwo.core.crossmatch import crossmatch
from astrotwo.core.images_fits import load_image, set_display
from astrotwo.core.measures import angular_distance, position_angle
from astrotwo.core.moc import filter_by_moc, moc_from_image
from astrotwo.core.vo_protocols import sia_search, tap_query

OUTPUT = Path(__file__).resolve().parent / "output"

# --- Parametri dichiarati dall'utente (non calcolati: scritti nel report) ---------------------------------------
TARGET = "M45"
IMAGE_RADIUS = 1.0 * u.deg  # SIA: regione di lato 2 × raggio = 2° × 2°
DSS_SIA = "https://archive.eso.org/bin/dss_sia/dss.sia?VERSION=1.0&"  # ivo://eso.org/dss (registro VO); https: dal 2026-10-14 il reindirizzamento da http codifica due volte la virgola di POS
DSS_SURVEY, DSS_FORMAT = "DSS2-red", "image/gz-fits"
GAIA_RADIUS_DEG, GAIA_G_MAX = 1.0, 11.0
TWOMASS_FRAME = "icrs"  # 2MASS PSC: astrometria riferita a Tycho-2, cioè all'ICRS (2MASS Explanatory Supplement)
MATCH_RADIUS = 2.0 * u.arcsec
ARROW_YEARS = 5000 * u.yr  # le frecce mostrano lo spostamento in 5000 anni (solo moto proprio)
MEMBER_SELECTION = "parallax > 6.5 && parallax < 8.5"  # selezione dichiarata dei probabili membri (mas)
MOC_ORDER = 11
DISPLAY = {"vmin": 4000.0, "vmax": 16000.0, "stretch": "sqrt", "palette": "gray"}  # valori grezzi DSS (BUNIT assente)
SIZE_SCALE = SizeScale(column="phot_g_mean_mag", vmin=2.0, vmax=11.0, size_min=14.0, size_max=3.0)
STAR_COLOR, ARROW_COLOR = "#38bdf8", "#f59e0b"


class Report:
    """Righe del report: ogni numero con unità, sistema/epoca, funzione e libreria."""

    def __init__(self) -> None:
        self.lines: list[str] = [
            "AstroTwo — demo delle Pleiadi (M45): report",
            f"creato il {datetime.now(UTC).isoformat(timespec='seconds')}",
            "Ogni numero viene da una funzione pubblica di AstroTwo (indicata con la libreria): lo script non calcola.",
            "",
        ]

    def section(self, title: str) -> None:
        self.lines += ["", title, "-" * len(title)]

    def add(self, text: str) -> None:
        self.lines.append(text)
        print(text)

    def write(self, path: Path) -> None:
        path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def _deg(angle) -> str:
    return f"{float(angle.to_value(u.deg))!r}°"


def run(output: Path, show: bool) -> tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=True)
    report = Report()

    # 1. Risoluzione del nome (modulo 10).
    report.section("1. Centro del campo: resolve_name (modulo 10)")
    center = resolve_name(TARGET)
    c = center.coords
    report.add(f"{TARGET} = {center.main_id.strip()}: RA {_deg(c.lon)}, Dec {_deg(c.lat)} ({c.frame_name}, epoca "
               f"{c.epoch.jyear_str if c.epoch is not None else 'non dichiarata'})")
    report.add(f"fonte: {center.source}; {center.origin}; {c.provenance}")

    # 2. Immagine DSS2 del campo (SIA del 14 + load_image dell'11).
    report.section("2. Immagine DSS2: sia_search (modulo 14) + load_image (modulo 11)")
    images = sia_search(c, IMAGE_RADIUS, version=1, service=DSS_SIA, max_rows=100)
    table = images.table.table
    rows = [k for k in range(len(table))
            if str(table["SurveyName"][k]) == DSS_SURVEY and str(table["Format"][k]) == DSS_FORMAT]
    if not rows:
        raise SystemExit(f"nessuna immagine {DSS_SURVEY} ({DSS_FORMAT}) dal servizio SIA {DSS_SIA}")
    url = str(table["Url"][rows[0]])
    # Dal 2026-10-14 il reindirizzamento http → https dell'ESO codifica due volte gli spazi e le virgole dell'URL:
    # si chiede direttamente l'indirizzo https (stesso server, stesso prodotto), dichiarato nel report.
    url_https = url.replace("http://archive.eso.org/", "https://archive.eso.org/", 1)
    image = load_image(url_https)
    wcs = image.wcs
    report.add(f"servizio SIA 1.0 {DSS_SIA}: {len(table)} prodotti, scelto {DSS_SURVEY} ({DSS_FORMAT}); "
               f"regione richiesta: lato 2 × {IMAGE_RADIUS}")
    report.add(f"immagine {image.data.shape[1]} × {image.data.shape[0]} pixel ({image.data.dtype}), unità "
               f"{image.bunit or 'non dichiarata (BUNIT assente)'}; WCS {wcs.projection} nel sistema {wcs.frame_name} "
               f"(equinozio {wcs.equinox.jyear_str if wcs.equinox is not None else '—'}), epoca dell'immagine "
               f"{wcs.image_epoch.iso if wcs.image_epoch is not None else 'non dichiarata'}; {wcs.provenance}")
    for fix in wcs.fixes:
        report.add(f"  nota WCS: {' '.join(fix.split())}")
    if url_https != url:
        report.add(f"URL dell'immagine dal servizio in http, scaricato in https (il reindirizzamento dell'ESO codifica due "
                   f"volte l'URL): {url}")
    report.add(f"origine: {image.origin}")

    # 3. Stelle Gaia DR3 entro 1° e G < 11 (tap_query del 14, tabella del 13).
    report.section("3. Gaia DR3: tap_query (modulo 14) sull'archivio Gaia dell'ESA")
    ra, dec = float(c.lon.to_value(u.deg)), float(c.lat.to_value(u.deg))  # solo testo dell'ADQL
    gaia = tap_query("esa-gaia-tap", (
        "SELECT source_id, ra, dec, pmra, pmdec, parallax, phot_g_mean_mag, ref_epoch FROM gaiadr3.gaia_source "
        f"WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra!r}, {dec!r}, {GAIA_RADIUS_DEG!r})) "
        f"AND phot_g_mean_mag < {GAIA_G_MAX!r}")).table
    report.add(f"{gaia.rows} stelle entro {GAIA_RADIUS_DEG}° dal centro con G < {GAIA_G_MAX} mag; posizioni "
               f"{gaia.positions.lon}/{gaia.positions.lat} nel sistema {gaia.positions.system} all'epoca "
               f"{gaia.positions.epoch} (dai metadati del servizio); origine {gaia.origin}")

    # 4. Moto proprio: medie (column_statistics del 13).
    report.section("4. Moto proprio: column_statistics (modulo 13)")
    members = subset(gaia, search(gaia, MEMBER_SELECTION))
    for label, table_pm in (("tutte le stelle selezionate (anche di campo)", gaia),
                            (f"probabili membri ({MEMBER_SELECTION} mas, {members.rows} stelle)", members)):
        for column in ("pmra", "pmdec"):
            stats = column_statistics(table_pm, column)
            report.add(f"{column}, {label}: media {float(stats.mean)!r} {stats.unit}, deviazione standard {float(stats.std)!r} "
                       f"{stats.unit} (ddof {stats.ddof}), {stats.valid} valori validi, {stats.missing} mancanti "
                       f"(column_statistics del 13, numpy){'; include cos(Dec) (Gaia DR3)' if column == 'pmra' else ''}; "
                       f"epoca {gaia.positions.epoch}")

    # 4b. Epoca di visualizzazione (D10-2): display_positions del 13, epoca dell'immagine se nota, altrimenti J2000.
    report.section("4b. Epoca di visualizzazione: display_positions (modulo 13, D10-2)")
    motion = {"pm_ra": "pmra", "pm_dec": "pmdec", "pm_ra_includes_cosdec": True, "parallax": "parallax"}
    shown = display_positions(gaia, image, **motion)
    report.add(f"epoca di visualizzazione {shown.epoch.isot} ({shown.epoch.scale}), fonte: {shown.epoch_source}; "
               f"origine {shown.source_epoch}; cos δ incluso; righe {shown.counts} (full = moto proprio e parallasse, "
               f"pm_only = solo moto proprio, missing = non disegnate); disegnabili {int(shown.drawable.sum())} su "
               f"{gaia.rows}")
    for note in shown.notes:
        report.add(f"  nota: {note}")
    report.add(f"spostamento epoca della tabella → epoca di visualizzazione: media {float(shown.shift_mean.value)!r} "
               f"{shown.shift_mean.unit}, massimo {float(shown.shift_max.value)!r} {shown.shift_max.unit} su "
               f"{int(shown.drawable.sum())} stelle (display_positions del 13, astropy)")
    # Frecce: dalla posizione all'epoca di visualizzazione a quella ARROW_YEARS dopo (stesse regole, modulo 13).
    arrow_epoch = shown.epoch.tt + ARROW_YEARS
    arrows = display_positions(gaia, arrow_epoch, **motion)
    report.add(f"frecce del moto proprio: dalla posizione all'epoca di visualizzazione a quella all'epoca "
               f"{arrow_epoch.jyear_str} ({arrow_epoch.scale}), cioè lo spostamento in {ARROW_YEARS} (scala dichiarata "
               f"nella figura; display_positions del 13 con epoca {arrows.epoch_source}, moto proprio e parallasse, "
               f"senza velocità radiale); righe {arrows.counts}")
    for note in arrows.notes:
        report.add(f"  nota (frecce): {note}")
    report.add("cerchi e frecce della figura all'epoca di visualizzazione; misure (crossmatch, Alcyone–Atlas, MOC) "
               "all'epoca dei dati, non propagate")

    # 5. Crossmatch con 2MASS (tap_query del 14 su IRSA, crossmatch del 15).
    report.section("5. Crossmatch Gaia DR3 – 2MASS: crossmatch (modulo 15)")
    twomass = tap_query("nasa-irsa-tap", (
        "SELECT designation, ra, dec, j_m, h_m, k_m FROM fp_psc "
        f"WHERE CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra!r}, {dec!r}, {GAIA_RADIUS_DEG!r})) = 1")).table
    twomass = confirm_position_columns(twomass, "ra", "dec", TWOMASS_FRAME)
    report.add(f"2MASS PSC (IRSA): {twomass.rows} sorgenti entro {GAIA_RADIUS_DEG}°; il servizio non dichiara il "
               f"sistema: dichiarato {TWOMASS_FRAME} con confirm_position_columns (documentazione 2MASS); epoca non "
               "dichiarata (date di osservazione 1997–2001 per sorgente, nessuna propagazione)")
    match = crossmatch(gaia, twomass, "best", MATCH_RADIUS)
    rep = match.report
    percent = evaluate_expression(f"100 * {rep.pairs} / {rep.rows[0]}")
    report.add(f"criterio {rep.criterion} (raggio esplicito), modo {rep.mode}, sistema {rep.frame}; epoche "
               f"{rep.epochs[0]} (Gaia) e {rep.epochs[1] or 'non dichiarata'} (2MASS), nessuna propagazione (15)")
    report.add(f"stelle Gaia appaiate: {rep.pairs} su {rep.rows[0]} = {float(percent.value)!r} % "
               f"(calcolatrice algebrica del 18, {percent.library}); metodo: {rep.method}")
    for code, text in match.warnings:
        report.add(f"  avviso {code}: {text}")

    # 6. Alcyone–Atlas: distanza angolare e angolo di posizione (modulo 17).
    report.section("6. Alcyone – Atlas: angular_distance e position_angle (modulo 17)")
    alcyone, atlas = resolve_name("Alcyone"), resolve_name("Atlas")
    distance = angular_distance(alcyone.coords, atlas.coords, "arcmin")
    pa = position_angle(alcyone.coords, atlas.coords)
    for name, resolved in (("Alcyone", alcyone), ("Atlas", atlas)):
        report.add(f"{name} = {resolved.main_id.strip()}: RA {_deg(resolved.coords.lon)}, Dec "
                   f"{_deg(resolved.coords.lat)} ({resolved.coords.frame_name}, epoca "
                   f"{resolved.coords.epoch.jyear_str}); {resolved.source}")
    report.add(f"distanza Alcyone–Atlas: {float(distance.value.to_value(u.arcmin))!r} arcmin = "
               f"{float(distance.value.to_value(u.deg))!r}° ({distance.report.frame}; {'; '.join(distance.report.notes)}; "
               f"{distance.report.provenance})")
    report.add(f"angolo di posizione di Atlas da Alcyone: {float(pa.value.to_value(u.deg))!r}° "
               f"({pa.report.frame}; {'; '.join(pa.report.notes)}; {pa.report.provenance})")

    # 7. MOC del campo dell'immagine (modulo 16) e stelle dentro.
    report.section("7. MOC del campo: moc_from_image e filter_by_moc (modulo 16)")
    moc = moc_from_image(image, MOC_ORDER)
    inside = filter_by_moc(gaia, moc)
    report.add(f"MOC all'ordine {MOC_ORDER}: {moc.history[-1]}; {moc.provenance}")
    report.add(f"{inside.description}")
    report.add(f"stelle Gaia dentro il MOC: {inside.count} su {gaia.rows}"
               f"{' — tutte dentro' if inside.count == gaia.rows else ' — ATTENZIONE: non tutte dentro'}")

    # 8. Figura (solo disegno: posizioni in pixel con sky_to_pixel del 10, presentazione con set_display dell'11).
    report.section("8. Figura")
    figure = output / "demo_pleiadi.png"
    _draw(figure, image, gaia, shown, arrows, (alcyone, atlas), show)
    report.add(f"figura: {figure}")
    report.add(f"presentazione: set_display dell'11 con vmin {DISPLAY['vmin']}, vmax {DISPLAY['vmax']} (valori grezzi, "
               f"scelta dell'utente), funzione {DISPLAY['stretch']}, palette {DISPLAY['palette']}; dimensione dei "
               f"cerchi da set_plot_rules del 13 ({SIZE_SCALE}); posizioni in pixel con sky_to_pixel del 10 "
               f"(conversione {gaia.positions.system} → {wcs.frame_name} di astropy); stelle Gaia e frecce all'epoca "
               f"di visualizzazione {shown.epoch.isot} ({shown.epoch.scale}, {shown.epoch_source}); Alcyone e Atlas "
               "alla posizione SIMBAD (J2000, resolve_name non dà il moto proprio), dichiarato")

    text = output / "demo_pleiadi.txt"
    report.write(text)
    print(f"\nreport: {text}\nfigura: {figure}")
    return figure, text


def _pixels(wcs, frame: SkyFrame):
    pixels = sky_to_pixel(wcs, frame, convention="numpy").pixels
    return pixels.x, pixels.y


def _draw(path: Path, image, gaia, shown, arrows, named, show: bool) -> None:
    """``shown`` e ``arrows``: ``DisplayPositions`` del 13 all'epoca di visualizzazione e ARROW_YEARS dopo."""
    if not show:
        matplotlib.use("Agg")
    import matplotlib.patheffects as effects
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    wcs = image.wcs
    plane = set_display(image, **DISPLAY)
    style = set_plot_rules(gaia, [PlotRule(shape="circle", color=STAR_COLOR, size=SIZE_SCALE)])
    halo = [effects.withStroke(linewidth=3, foreground="black")]

    figure = plt.figure(figsize=(10, 10.5))
    ax = figure.add_subplot(projection=wcs.wcs)
    ax.imshow(plane.rgba, origin="lower")
    ax.coords.grid(color="white", alpha=0.25, linestyle=":")
    ax.coords[0].set_axislabel(f"RA ({wcs.frame_name.upper()} J2000)")
    ax.coords[1].set_axislabel(f"Dec ({wcs.frame_name.upper()} J2000)")

    rows = np.flatnonzero(shown.drawable)  # ordine di shown.coords
    x, y = _pixels(wcs, shown.coords)
    sized = style.drawn[rows]
    ax.scatter(x[sized], y[sized], s=style.size[rows][sized] ** 2, facecolors="none", edgecolors=STAR_COLOR,
               linewidths=1.2)

    if not np.array_equal(arrows.drawable, shown.drawable):  # stesse regole del 13: stesse righe
        raise SystemExit("frecce e stelle con righe disegnabili diverse")
    x1, y1 = _pixels(wcs, arrows.coords)
    for xs, ys, xe, ye in zip(x, y, x1, y1):
        ax.annotate("", xy=(xe, ye), xytext=(xs, ys),
                    arrowprops={"arrowstyle": "-|>", "color": ARROW_COLOR, "lw": 1.2, "mutation_scale": 8})

    for label, resolved in zip(("Alcyone", "Atlas"), named):
        px, py = (float(np.ravel(v)[0]) for v in _pixels(wcs, resolved.coords))
        ax.plot([px], [py], marker="+", markersize=14, markeredgewidth=1.5, color="white")
        ax.annotate(label, xy=(px, py), xytext=(-30, 45), textcoords="offset points", color="white", fontsize=12,
                    fontweight="bold", path_effects=halo,
                    arrowprops={"arrowstyle": "-", "color": "white", "lw": 1, "shrinkA": 2, "shrinkB": 6})

    legend = [
        Line2D([], [], marker="o", linestyle="none", markerfacecolor="none", markeredgecolor=STAR_COLOR,
               markersize=9, label=f"Gaia DR3, G < {GAIA_G_MAX:g}, all'epoca di visualizzazione {shown.epoch.iso[:10]} "
                     "(cerchio più grande = più brillante)"),
        Line2D([], [], color=ARROW_COLOR, marker=">", markersize=6,
               label=f"moto proprio: spostamento in {ARROW_YEARS.value:g} anni dall'epoca di visualizzazione"),
    ]
    ax.legend(handles=legend, loc="lower left", fontsize=10, framealpha=0.85)
    ax.set_title(f"Pleiadi (M45) — DSS2 red (ESO SIA), stelle Gaia DR3 entro {GAIA_RADIUS_DEG:g}°\n"
                 f"frecce: moto proprio × {ARROW_YEARS.value:g} anni (scala dichiarata)", fontsize=12)
    figure.savefig(path, dpi=150, bbox_inches="tight")
    if show:
        try:
            plt.show()
        except Exception as exc:  # nessuno schermo disponibile: la figura è comunque salvata
            print(f"figura non mostrata a schermo ({exc})")
    plt.close(figure)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=OUTPUT, help="cartella dei risultati")
    parser.add_argument("--no-show", action="store_true", help="non mostrare la figura a schermo")
    args = parser.parse_args(argv)
    run(args.output, show=not args.no_show)
    return 0


if __name__ == "__main__":
    sys.exit(main())
