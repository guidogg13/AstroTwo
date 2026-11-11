# AstroTwo

**A sky atlas and object-profile tool for astrophysicists, with an optional AI assistant that never makes up numbers.**

AstroTwo is a native macOS application to explore the sky, open FITS images, query catalogues and Virtual Observatory services, cross-match tables and build a sourced profile of an astronomical object. Every number it shows comes from tested, deterministic code, with its source declared.

AstroTwo is meant to work **alongside** the tools astronomers already use, such as Aladin, TOPCAT and SAOImage DS9, not to replace them. It talks to them through SAMP, the Virtual Observatory messaging protocol: tables and positions travel between the applications in both directions.

> **Version 1.0.0.** Feedback and bug reports are welcome.

<!-- Screenshots: add 3–4 images here, e.g.
![Gaia DR3 over the Pleiades](docs/screenshots/pleiades-gaia.png)
![Object profile of 51 Peg](docs/screenshots/profile-51peg.png)
![AI assistant with verified numbers](docs/screenshots/ai-panel.png)
-->

---

## Documentation

- [Installation](docs/installation.md): macOS 15 or later, Apple silicon
- [Quick start](docs/quickstart.md): HiPS atlas, FITS, catalogues and cross-match, cone search and ADQL, object profiles, exports, SAMP, AI assistant
- [Validation](docs/validation.md): how AstroTwo's results are checked against reference sources (structure; measurements still to be done)
- [Citing AstroTwo](#citing-astrotwo)

## What AstroTwo does

**Sky atlas**
- HiPS surveys (for example DSS2 and 2MASS), colour and FITS tiles
- Zoom and pan, *Go to* by object name or coordinates
- Coordinate grid (ICRS or Galactic), north and east arrows, scale bar
- Pixel value under the cursor, with unit, HiPS order and resolution
- Distance tool and SIMBAD pointer
- Night mode for the observatory

**Data**
- Your own FITS images with their WCS, catalogues (VOTable, FITS, CSV, TSV, ECSV) and MOC coverage maps
- Catalogues from VizieR, SIMBAD and Gaia DR3; cone search on any Simple Cone Search service; ADQL queries on TAP services
- Cross-match of two catalogues by position, on your computer (Astropy) or with the CDS XMatch service, with a report of the criteria used
- Proper-motion propagation only with the epoch declared by the catalogue
- Layers with visibility, order and opacity; a table panel linked to the sky

**Object profiles**
- Identity, images, astrometry and distance, photometry with a spectral energy distribution (SED), and known planets, collected from SIMBAD, the Gaia archive, IRSA, VizieR and the NASA Exoplanet Archive
- Every value carries its source, the query that produced it and the retrieval date

**Reproducibility**
- Every action, yours or the assistant's, is a recorded command with its parameters, source and time
- Sessions can be saved and replayed

## Without the AI assistant

The AI assistant is optional. **Everything listed above works without it**: the sky atlas, images, catalogues, cone search and ADQL, cross-match, object profiles, exports, sessions and SAMP. You do not need an account with any AI provider, and no API key is required.

Without an assistant configured, AstroTwo makes no requests to AI providers. The only thing missing is the assistant panel itself: asking in plain language for an action, and getting an explanation of the results.

## How AstroTwo avoids invented numbers

Language models can produce plausible numbers that are wrong. AstroTwo is built so that this cannot happen silently:

1. **The AI never computes.** Coordinates, distances, magnitudes, separations and every other scientific value come only from AstroTwo's own tested code or from established libraries (Astropy, astroquery, pyvo, mocpy and others), never from the model.
2. **The assistant can only run AstroTwo commands.** It has an explicit list of commands, the same ones you trigger from the menus. Each command it runs is recorded in the *Commands* panel like yours.
3. **Every number in an answer is checked.** AstroTwo compares the numbers in the assistant's reply with the results of the commands it ran. Each number gets a marker: verified (with the command it comes from), taken from your message, quoted from external text, or *does not come from a command*. Numbers that cannot be traced are flagged, not hidden.
4. **Strict mode** (optional): if some numbers in a reply are not verified, the reply is regenerated once.
5. **External text is data, never instructions.** Text coming from catalogues or services is passed to the model marked as external. Actions requested after reading external text ask for your confirmation.

## Requirements

- macOS 15 or later on Apple silicon (M1 or later). Intel Macs are not supported.
- An internet connection for online surveys, catalogues and services
- Optional, for the AI assistant: an API key from a supported provider, or a local model running in Ollama or LM Studio

See [Installation](docs/installation.md).

## Roadmap

These items are planned **after version 1.0**. None of them is available today, and their details are still to be decided:

- Linux version
- Windows version
- Python API, to use AstroTwo's functions from scripts and notebooks

Before 1.0: a full manual test of the application, a `CITATION.cff` with a DOI from Zenodo, and the measurements of the [validation page](docs/validation.md).

## Licence

AstroTwo is free software, released under the **GNU General Public License v3.0 or later**. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Third-party libraries keep their own licences, listed in [THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES).

## Data credits

AstroTwo uses public data and services. Please acknowledge them in your publications:

- **CDS, Strasbourg Astronomical Observatory, France**: SIMBAD, VizieR, Sesame, HiPS, MocServer and XMatch
- **Gaia**, European Space Agency (ESA), processed by the Gaia DPAC
- **2MASS**, University of Massachusetts and IPAC/Caltech; **WISE/AllWISE**, NASA/JPL-Caltech and UCLA; **IRSA**, NASA/IPAC
- **NASA Exoplanet Archive**, operated by Caltech under contract with NASA
- **Digitized Sky Survey (DSS)**, Space Telescope Science Institute
- **NAIF/SPICE**, NASA Jet Propulsion Laboratory

The exact acknowledgement for each survey is shown in the app and written into exported images and files.

## Citing AstroTwo

If AstroTwo helps your research, please cite it. The citation metadata are in [CITATION.cff](CITATION.cff); GitHub shows them under *Cite this repository*. A DOI will be added when the first version is archived on Zenodo.

## Author

Developed by **Guido Ratti**.
