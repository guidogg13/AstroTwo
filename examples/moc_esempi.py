# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Due MOC di prova per lo sprint 4f del 41 (MOC sul cielo e corpi diversi), scritti con il modulo 16.

Uso (dalla radice del progetto)::

    uv run python examples/moc_esempi.py

Scrive in ``examples/output/``:

- ``moc_m31.fits``: cerchio di raggio 1,5° attorno a M31 all'ordine 9 (``moc_from_region`` del 16). Il centro è un
  parametro scritto qui (ICRS 10.6847°, +41.2690°, posizione di M31 in SIMBAD), non un calcolo;
- ``moc_marte.fits``: MOC di Marte (celle 3/1-5, corpo ``Mars`` con la parola chiave nostra ``A2BODY``), per vedere
  l'errore ``BODY_MISMATCH`` quando lo si apre sopra il cielo.

Nessun calcolo scientifico proprio: solo funzioni pubbliche del 16 (regola d'oro n. 1).
"""

from __future__ import annotations

from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from mocpy import MOC

from astrotwo.core.moc import CircleRegion, Moc, moc_from_region, write_moc

OUTPUT = Path(__file__).parent / "output"
M31 = SkyCoord(10.6847 * u.deg, 41.2690 * u.deg, frame="icrs")  # parametro dichiarato (SIMBAD)


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    sky = moc_from_region(CircleRegion(M31, 1.5 * u.deg), 9)
    result = write_moc(sky, OUTPUT / "moc_m31.fits", overwrite=True)
    print(f"{OUTPUT / 'moc_m31.fits'}: {sky.describe()}")
    mars = Moc(moc=MOC.from_string("3/1-5"), kind="space", body="Mars", origin="examples/moc_esempi.py")
    write_moc(mars, OUTPUT / "moc_marte.fits", overwrite=True)
    print(f"{OUTPUT / 'moc_marte.fits'}: MOC di Marte (A2BODY = Mars)")
    for code, text in getattr(result, "warnings", ()):
        print(f"  {code}: {text}")


if __name__ == "__main__":
    main()
