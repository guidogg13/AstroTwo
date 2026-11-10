# AstroTwo quick start

This guide walks through the main functions of AstroTwo 0.1.0-beta.5. Menu names are those of the English interface; AstroTwo is also available in Italian (*Settings → Language*).

Everything in sections 1–8 works **without the AI assistant**. Section 9 is optional.

Every action, whether it comes from a menu, the mouse or the assistant, is recorded in the **Commands** panel with its parameters, source and time. **File → Save session…** writes these commands to a file, and **File → Open session…** replays them.

## 1. The HiPS sky atlas

- **Go to an object or position:** type a name (`M 31`, `Vega`) or coordinates (`10.6847 41.2690`, `00:42:44.3 +41:16:09`) in the *Go to* field at the top (⌘L) and press Return.
- **Change survey:** **Data → HiPS survey…**, then search the list of HiPS collections or type an identifier such as `CDS/P/DSS2/color` or `CDS/P/2MASS/color`.
- **Move around:** drag to pan, scroll or use ⌘+ / ⌘− to zoom.
- **Overlays:** **View → Coordinate grid** (ICRS or Galactic), **View → Show north and east**, **View → Show scale bar**, and **View → Coordinates shown** for the format of the coordinates under the cursor.
- **Measure:** **Tools → Distance** for the angular distance between two points, and **Tools → Simbad pointer** to identify the SIMBAD object under the mouse.
- **Night mode:** **View → Night mode** (⌃⌘N) turns the interface red for the observatory.

The status bar shows the position and the pixel value under the cursor, with its unit, the HiPS order and the resolution.

## 2. FITS images

**File → Open image…** (⌘O) opens a FITS file (`.fits`, `.fit`, `.fts`, `.fits.gz`). AstroTwo reads the WCS from the header and places the image on the sky. Each image is a layer in the **Layers** panel, where you set visibility, order and opacity.

## 3. Catalogues and cross-match

- **Catalogue in the current view:** **Data → Catalog in view…** loads SIMBAD, Gaia DR3 or 2MASS in the circle of the current view, up to a maximum number of rows.
- **Your own table:** **File → Open catalog…** opens VOTable, FITS, CSV, TSV, ECSV or plain-text tables.
- The **Table** panel is linked to the sky: selecting a row highlights the source, and clicking a source selects its row.
- **Epochs are never assumed.** Positions are propagated with proper motions only when the catalogue declares its epoch. Otherwise they are drawn as they are, and the Layers panel says so.
- **Cross-match:** **Data → Cross-match catalogs…** matches two loaded catalogues by position. You choose:
  - the mode: best match, all pairs, or rows of A without a match;
  - the maximum separation;
  - the method: local, computed with Astropy on your Mac, or the CDS XMatch service;
  - the comparison frame.

  The result is a new catalogue, with a report of the criteria, the epochs and the counts.

## 4. Cone search and ADQL

- **Cone search:** **Data → Cone search…** queries a Simple Cone Search service. Choose the service from the list, save your own servers, or type a URL. The centre can be the centre of the view, the selected source, or coordinates you type with their frame and epoch.
- **ADQL:** **Data → ADQL query…** runs a query on a TAP service, in synchronous or asynchronous mode. **Insert view centre and radius** fills in the current region, **Check** runs minimal checks before sending the query, and the *Examples* list has ready queries for Gaia DR3, SIMBAD, VizieR, IRSA, HEASARC and MAST.

The results are new catalogue layers with the query recorded in their provenance.

## 5. Object profiles

An object profile collects what public archives know about one object, with the source of every value.

- Open it with **Data → Object profile…** (name or coordinates), or right-click a source and choose **Profile of this source**. Profiles open in the **Profiles** window (**Window → Profiles**).
- The sections are:
  - **Identity:** SIMBAD identifiers, the chain of cross-identifications and the method of each one;
  - **Images:** thumbnails from DSS2, 2MASS and AllWISE;
  - **Astrometry and distance:** Gaia DR3, with the distance method declared;
  - **Photometry:** with the SED, where upper limits are shown as arrows;
  - **Planets:** from the NASA Exoplanet Archive.
- Sections arrive in parallel. **Cancel** keeps the sections already received.
- If a service is down, AstroTwo uses an official mirror where one exists and says so, or declares the section as skipped. It never fills the gap silently.
- **Rerun with fresh data** repeats the profile without using the cache.

## 6. Exports

- **Sky view:** **File → Export view as PNG…** saves the view with the data credits and provenance metadata.
- **Object profile** (**Export…** button in the Profiles window):
  - values with provenance (**ECSV**);
  - a profile sheet (**PDF**);
  - the SED plot (**PNG**).
- **SED as a catalogue:** **Load SED points as catalog** turns the SED into a catalogue layer.
- **Sessions:** **File → Save session…** saves the recorded commands so that the work can be replayed.

## 7. SAMP: working with Aladin, TOPCAT and DS9

AstroTwo is designed to work alongside other Virtual Observatory tools through SAMP.

- **Tools → SAMP → Connect.** AstroTwo uses the SAMP hub already running, for example TOPCAT's, or starts its own. The hub and AstroTwo listen only on your Mac (`127.0.0.1`).
- **Send:**
  - from **Tools → SAMP**: a whole table, only the selected rows, or a position (the view centre or the selected source), to one application or to all;
  - from the Profiles window: **Send via SAMP** sends the SED points.
- **Receive:** tables (`table.load.votable`), row selections (`table.select.rowList`) and positions (`coord.pointAt.sky`) sent by other applications.
- **Tools → SAMP → Connected applications** lists the applications on the hub.

## 8. Settings

**AstroTwo → Settings…** (⌘,) sets the interface language (applied at the next start), the appearance (system, dark, light or red night mode), the coordinates shown, the default HiPS survey, whether to connect to SAMP at startup, and the cache limit, with a button to clear the cache (`~/Library/Caches/AstroTwo/`).

## 9. The AI assistant (optional)

The assistant runs AstroTwo commands for you from a request in plain language, and explains the results. It does not compute anything itself: see [How AstroTwo avoids invented numbers](../README.md#how-astrotwo-avoids-invented-numbers).

**With a cloud provider** (Anthropic, OpenAI, Google Gemini, Mistral AI, DeepSeek, xAI, Groq or OpenRouter):

1. Open the assistant panel (⌃⌘A).
2. Click the gear icon, then **Add**, and choose the provider.
3. Paste your API key and click **Save**. The key goes straight to the **macOS Keychain**; AstroTwo never writes it to files or logs.
4. Click **Refresh**, choose a model and click **Test the model**.

Using a cloud provider costs tokens on your own account with that provider.

**With a local model** (Ollama or LM Studio, running on your Mac): add the *Ollama* or *LM Studio* provider in the same way. Most local servers need no key. The panel shows *local · nothing leaves the Mac*.

**What to expect:**

- **Confirmation cards:** actions that use the network or take long ask for confirmation first.
- **Number markers:** each number in an answer carries a marker. It says whether the number was verified against a command result, came from your message, or does not come from a command.
- **Strict mode:** when it is on, an answer with unverified numbers is regenerated once.
- **What was sent:** this button shows the exact request sent to the provider.

Try, for example:

- *"Go to the Pleiades and load Gaia DR3"*
- *"Show the Galactic grid and hide the scale bar"*
- *"Make a profile of 51 Peg"*
