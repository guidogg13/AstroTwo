# AstroTwo

**A sky atlas for astrophysicists, with an AI assistant that never makes up numbers.**

AstroTwo is a native macOS application to explore the sky, open FITS images, overlay catalogues and coverage maps, and ask an AI assistant to do it for you, while every number it shows comes from tested, deterministic code.

> **Status: beta (v0.1).** Feedback and bug reports are welcome.

<!-- Screenshots: add 3–4 images here, e.g.
![Gaia DR3 over the Pleiades](docs/screenshots/pleiades-gaia.png)
![Horsehead Nebula with coordinate grid](docs/screenshots/horsehead-grid.png)
![AI assistant with verified numbers](docs/screenshots/ai-panel.png)
![Night mode](docs/screenshots/night-mode.png)
-->

---

## What makes AstroTwo different

- **The AI never computes.** Coordinates, distances and measurements come only from AstroTwo's scientific code. Every number in an AI answer is checked automatically: verified numbers are marked, invented ones are highlighted.
- **Every action is a recorded command.** Whatever you or the assistant do is logged with its parameters, source and time, and a session can be replayed exactly.
- **Protected against prompt injection.** Text coming from catalogues or external services is treated as data, never as instructions. Actions requested after reading external text always ask for your confirmation.
- **Your keys stay on your Mac.** API keys are stored only in the macOS Keychain, never in files or logs. With a local model (Ollama, LM Studio) nothing leaves your Mac.
- **Nothing is assumed.** Epochs, frames, units and coordinate columns are read from the data or asked to you, and always declared in the results.

## Features

**Sky viewer**
- HiPS surveys (DSS2, 2MASS and more), colour and FITS tiles
- Smooth zoom and pan, *Go to* by object name or coordinates
- Coordinate grid (ICRS and Galactic), north/east arrows, scale bar
- Pixel value under the cursor, with unit, HiPS order and resolution
- Distance tool and SIMBAD pointer
- PNG export with data credits and provenance metadata

**Data**
- Open your own FITS images with their WCS
- Catalogues from VizieR, SIMBAD and Gaia DR3, or your own CSV/VOTable files
- Proper-motion propagation using the epoch declared by the catalogue
- MOC coverage maps
- Layers with visibility, order and opacity
- Table panel linked to the sky (select a row, see the source, and vice versa)

**AI assistant**
- Works with many providers: Anthropic, OpenAI, Google Gemini, Mistral, DeepSeek, xAI, Groq, OpenRouter, Ollama, LM Studio
- Uses only an explicit list of AstroTwo commands
- Confirmation cards for network and long-running actions
- Shows exactly what was sent to the provider

**Interface**
- Dark theme and red **night mode** for the observatory (⌃⌘N)
- English and Italian
- Colour-blind-safe palette (Okabe–Ito)

## Requirements

- macOS 26 or later, Apple Silicon (M1 or later). Intel Macs are not supported.
- Internet connection for online surveys and catalogues
- For the AI assistant: an API key from a supported provider, or a local model with Ollama or LM Studio

## Installation

### Download the app

<!-- Replace with the real link when the .dmg is published -->
Download the latest `.dmg` from the [Releases](../../releases) page, open it and drag **AstroTwo** to *Applications*. Python and all libraries are included.

> While the app is not yet signed by Apple, macOS may block the first launch. Go to **System Settings → Privacy & Security** and click **Open Anyway**.

### Run from source

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/guidogg13/AstroTwo.git
cd AstroTwo
uv run astrotwo
```

## Using the AI assistant

1. Open the assistant panel with **⌃⌘A**.
2. Click the gear icon, then **Add**, and choose a provider.
3. Paste your API key and click **Save**: it goes straight to the macOS Keychain.
4. Click **Refresh**, choose a model and click **Test the model**.

Try: *"Go to the Pleiades and load Gaia DR3"*, or *"Show the Galactic grid and hide the scale bar"*.

Using a paid provider costs tokens on your own account. With Ollama everything runs locally and for free.

## Licence

AstroTwo is free software, released under the **GNU General Public License v3.0 or later**. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Third-party libraries keep their own licences, listed in [THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES).

## Data credits

AstroTwo uses public data and services. Please acknowledge them in your publications:

- **CDS, Strasbourg Astronomical Observatory, France**: SIMBAD, VizieR, Sesame, HiPS and MocServer
- **Digitized Sky Survey (DSS)**, Space Telescope Science Institute
- **2MASS**, University of Massachusetts and IPAC/Caltech
- **Gaia**, European Space Agency (ESA), processed by the Gaia DPAC
- **NAIF/SPICE**, NASA Jet Propulsion Laboratory

The exact acknowledgement for each survey is shown in the app and written into exported images.

## Citing AstroTwo

If AstroTwo helps your research, please cite it. <!-- A CITATION.cff file will add a "Cite this repository" button. -->

## Author

Developed by **Guido Ratti**.
