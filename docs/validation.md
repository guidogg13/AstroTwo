# Validation of AstroTwo

> **Status: partial measurements.** The tolerances (section 2.1) were fixed and committed on 2026-11-10 before any measurement. Two runs were made the same day (section 5). In the second run (section 5.1) the SIMBAD values were compared with the **Harvard mirror** of SIMBAD, because the CDS was down: 129 SIMBAD rows passed and 2 failed (empty spectral type); after the project owner's rule on empty text (decision D25-24, 2026-11-10) the saved rows were **recompared without network** and all 131 pass (section 5.1, «Correction»). Every one of these rows is **to be repeated against the CDS**. Gaia, VizieR and the NASA Exoplanet Archive rows are still **not measured** and stay to be redone before version 1.0. On 2026-11-11 the services were checked three more times (05:53–05:57, 13:21–13:25 and 14:21–14:37 UTC) and no new run was made, because the CDS and the Gaia archive were still down (section 5.0). By decision of the project owner (2026-11-11), version 1.0 is not released while these rows are not measured, unless the owner decides otherwise.

## 1. Purpose

AstroTwo is meant to be cited in scientific papers, so its results must be checkable by anyone. This page records, for a fixed set of reference objects:

- which values AstroTwo shows;
- which independent source they are compared with;
- the method and the tolerance used;
- the result, with the date, the AstroTwo version and the data release.

The comparison checks that AstroTwo **retrieves, converts and reports** values correctly. It does not re-validate the catalogues themselves. A value that differs because a catalogue was updated is reported as such, not as an error.

AstroTwo works alongside Aladin, TOPCAT and DS9. Comparing results with these tools on the same data is part of validation; it is never the reason for a design choice.

## 2. Method

1. **Same input.** For each object, the same identifier or position, epoch and search radius are used in AstroTwo and in the reference source.
2. **AstroTwo side.** The object profile is run with the same recorded command as in the app (`object.profile`), with an empty cache. The result and its ECSV export, with values, units, source and query, are kept (section 6).
3. **Reference side.** The same values are read directly from the reference source with TAP/ADQL, using plain HTTP and Astropy's VOTable reader: **no AstroTwo code** is used on this side. The server that answered, the time and the query are written down.
4. **Comparison.**
   - Values copied from a catalogue must match the catalogue digit for digit, with the same unit.
   - Values AstroTwo computes, such as unit conversions, fluxes from magnitudes, separations and propagated positions, are compared with an independent computation within a stated tolerance.
   - **Tolerances are fixed before measuring.** They are written in this page and committed to the repository before any measurement is made. They are never changed afterwards to make a result pass: a value outside its tolerance is reported as such, with an explanation.
5. **Record.** Each row of the results tables reports:
   - the date and the AstroTwo version;
   - the data release, for example Gaia DR3;
   - the source and the exact query;
   - the AstroTwo value, the reference value and the difference;
   - the outcome: pass, fail, or explained difference.
6. **Reproducibility.** The session files and exports used for each measurement are listed in section 6, so anyone can rerun them.

**While the CDS is down** (rule of the project owner, 2026-11-10): what has a reachable reference is measured at once. Gaia values are compared with the Gaia archive of ESA queried directly. SIMBAD values are compared with the Harvard mirror of SIMBAD, and every such row says «reference: Harvard mirror, to be repeated against CDS». Everything else stays to be redone. The tolerances do not change.

### 2.1 Tolerances (fixed on 2026-11-10, before any measurement)

These tolerances were committed to the repository **before** the first measurement. They will not be changed to make a result pass. A value outside its tolerance is written in section 5 as **fail** or **explained difference**, with the reason.

AstroTwo values are of two kinds, and the ECSV export says which one each value is (`method` column):

- **read**: copied from a service (SIMBAD, Gaia archive, VizieR, IRSA, NASA Exoplanet Archive). AstroTwo must not change them at all.
- **computed**: calculated by AstroTwo from read values, with the formula written next to the value (`formula` column).

| Quantity | Kind | Tolerance | Why |
|---|---|---|---|
| Position (RA, Dec) and its epoch | read | **Identical**: difference 0 in the native type of the column; same epoch | AstroTwo copies the catalogue position and declares its epoch. Any difference, even in the last bit, would mean that AstroTwo changed a value it should only copy. |
| Parallax and its error | read | **Identical** (difference 0) | Same reason: copied value. |
| Proper motion (pmRA, pmDec) and errors | read | **Identical** (difference 0) | Copied value. |
| Radial velocity and error | read | **Identical** (difference 0) | Copied value. |
| Magnitudes (Gaia G, BP, RP; 2MASS J, H, Ks; AllWISE W1–W4) and errors | read | **Identical in the native precision of the column**: for a `float32` column (Gaia photometry), equal after rounding both values to `float32`; for `float64` and decimal text, difference 0 | Gaia stores magnitudes as `float32`; the same number written as `float32` or as `float64` may print differently but is the same value. Any other difference is an error. |
| Distance, Bailer-Jones et al. (2021) median and 16th–84th percentiles | read | **Identical** (difference 0) | Copied from `external.gaiaedr3_distance`. |
| Distance as 1/parallax (only when declared, parallax/error ≥ 10)¹ | computed | **Relative difference ≤ 1 × 10⁻¹²** against `1000 / parallax[mas]` pc computed independently | One division in `float64`: the only possible difference is rounding, about 10⁻¹⁶. 10⁻¹² leaves room for a different but correct order of operations and still catches any real mistake (wrong unit, wrong column). |
| Planet parameters (orbital period, semi-major axis, eccentricity, radius, mass, equilibrium temperature) and their errors | read | **Identical** (difference 0), same unit | Copied from `pscomppars`. |
| Identifiers (SIMBAD main identifier, Gaia DR3, 2MASS, AllWISE designations, planet names) | read | **Identical text** | A different identifier means a different object. |
| SED flux from a magnitude | computed | **Relative difference ≤ 1 × 10⁻¹⁰** against `F0 × 10^(−0.4 m)` computed independently with the zero point that AstroTwo declares for that band | Two `float64` operations; the zero point itself is a declared choice, checked separately against its published source, not against this tolerance. |
| Angular separations (cross-match to 2MASS and AllWISE) | computed | **≤ 1 µas** (10⁻⁶ arcsec) against an independent Astropy computation from the same two positions | Separations are about 1 arcsec; `float64` rounding is far below 1 µas, and 1 µas is far below any catalogue error. |

¹ *Correction made on 2026-11-10, after the commit of the tolerances and before writing the results:* this row said «parallax/error ≥ 5». AstroTwo declares a distance as 1/parallax only when parallax/error ≥ 10 (`PARALLAX_SNR_MIN`, `mdfiles/25-analisi-profilo-oggetto.md`). The ≥ 5 was a mistake in the description of when the row applies. **The tolerance itself (10⁻¹²) is unchanged**, and no measured value depended on this sentence (no 1/parallax distance could be measured on that day).

**Outcomes.**

- **pass**: within the tolerance.
- **fail**: outside the tolerance with no explanation. It is a defect of AstroTwo until shown otherwise.
- **explained difference**: outside the tolerance for a reason that is not a defect of AstroTwo, written in the row. The only accepted reasons are a different data release or a catalogue updated between the two queries (shown by the query dates), and a value that the reference service returns differently on two identical queries.
- **not measured**: the service did not answer. The row records the service, the time and the error, and stays to be redone.

## 3. Reference objects

| Object | Why it is included |
|---|---|
| **51 Peg** | Bright solar-type star with a planet; full chain SIMBAD → Gaia DR3 → 2MASS/AllWISE → NASA Exoplanet Archive |
| **Vega** | Photometric standard; very bright, so it tests saturated or missing survey photometry and the SED |
| **eta Tau** (Alcyone) | Bright member of a crowded cluster field (Pleiades): identification and cross-match among close neighbours |
| **TRAPPIST-1** | Faint, very red, high proper motion star with seven planets: epoch handling and infrared SED |
| **Barnard's Star** | Highest known proper motion: tests propagation between epochs (J2000.0, J2016.0) and the 2MASS epoch |
| **3C 273** | Extragalactic object (quasar): no meaningful parallax, so the distance must be declared as unavailable rather than invented |
| **M 13** | Dense globular-cluster field: cone search and cross-match row counts against TOPCAT |

## 4. Values compared and reference sources

| Area | Values | Reference source |
|---|---|---|
| Identity | Main identifier, object type, cross-identifications (Gaia DR3, 2MASS, AllWISE designations) | SIMBAD |
| Position | ICRS coordinates with their epoch | Gaia archive (`gaiadr3.gaia_source`); SIMBAD for objects without Gaia data |
| Astrometry | Parallax, proper motions, radial velocity, with errors | Gaia archive |
| Distance | Distance and its method (for example Bailer-Jones et al. 2021, or inverse parallax when declared) | Gaia archive (`external.gaiaedr3_distance`); VizieR (I/352) |
| Photometry | Gaia G, BP, RP; 2MASS J, H, Ks; AllWISE W1–W4, with errors and flags | Gaia archive; VizieR (II/246, II/328) |
| SED | Fluxes and wavelengths of the SED points, upper limits | VizieR photometry service; independent conversion of the magnitudes above |
| Planets | Planet names, orbital period, radius and mass where present | NASA Exoplanet Archive (`pscomppars`) |
| Cone search | Number of rows and values of the first rows for the same centre and radius | TOPCAT (same service) |
| ADQL | Same query, same result table | TOPCAT (same TAP service) |
| Cross-match | Number of pairs and separations for the same two tables and maximum separation | TOPCAT (*Pair Match*) |
| Propagated positions | Position at another epoch from proper motion | Independent computation with Astropy (`SkyCoord.apply_space_motion`); TOPCAT |

## 5. Results

### 5.0 Service checks of 2026-11-11 (05:53–05:57, 13:21–13:25 and 14:21–14:37 UTC): no new run

A new run is made only when the CDS, the Gaia archive and the NASA Exoplanet Archive all answer. They were checked twice with one small TAP query each (plain HTTP, no AstroTwo code), at 05:53 and at 05:57 UTC:

| Service | Address | Answer (both checks) |
|---|---|---|
| SIMBAD at the CDS | `simbad.cds.unistra.fr` (TAP) | HTTP 404 |
| TAPVizieR at the CDS | `tapvizier.cds.unistra.fr` | no answer within 40 s (first check) |
| Gaia archive of ESA | `gea.esac.esa.int` (TAP) | HTTP 503 |
| NASA Exoplanet Archive | `exoplanetarchive.ipac.caltech.edu` (TAP) | HTTP 200 |

**No measurement was made**, and the counts of section 5.1 are unchanged (177 within tolerance after D25-24, 0 outside, 85 not measured). These sections stay **not measured**, to redo when the three services answer:

- **Gaia DR3** (astrometry, photometry, Bailer-Jones distances): the Gaia archive answered HTTP 503;
- **2MASS and AllWISE magnitudes against VizieR** and the **VizieR SED series**: the CDS was down;
- **every SIMBAD row against the CDS** (all SIMBAD rows so far use the Harvard mirror): SIMBAD at the CDS answered HTTP 404;
- **planets** (NASA Exoplanet Archive): the archive answered, but the run is made only with all three services up (instruction of the project owner, 2026-11-11), so these rows were not measured either.

**Second check of 2026-11-11 (13:21–13:25 UTC).** The same small TAP queries (plain HTTP, no AstroTwo code) were sent three times, at 13:21, 13:23 and 13:25 UTC, together with the VizieR photometry service (`vizier.cds.unistra.fr/viz-bin/sed`) at 13:21 and 13:23. The answers were the same every time:

| Service | Address | Answer (all checks) |
|---|---|---|
| SIMBAD at the CDS | `simbad.cds.unistra.fr` (TAP) | HTTP 404 |
| TAPVizieR at the CDS | `tapvizier.cds.unistra.fr` | no answer within 40 s |
| VizieR photometry service at the CDS | `vizier.cds.unistra.fr` (`viz-bin/sed`) | HTTP 404 |
| Gaia archive of ESA | `gea.esac.esa.int` (TAP) | HTTP 503 |
| NASA Exoplanet Archive | `exoplanetarchive.ipac.caltech.edu` (TAP) | HTTP 200 |

The services did not answer in a stable way, so `scripts/validate_profiles.py` was **not** run again and no number on this page changed: **177 within tolerance, 0 outside, 85 not measured** (section 5.1). The four sections listed above stay **not measured**.

**Third check of 2026-11-11 (14:21–14:37 UTC).** The project owner reported that the Gaia archive answered HTTP 200 at about 14:00 UTC, so it was checked again with the same small TAP query (plain HTTP, no AstroTwo code), with the other services:

| Time (UTC) | Gaia archive (`gaiadr3.gaia_source`) | Other services |
|---|---|---|
| 14:21 | HTTP 200 | SIMBAD at the CDS 404, TAPVizieR no answer within 40 s, VizieR photometry service 404, NASA Exoplanet Archive 200 |
| 14:23 | HTTP 503 (also `external.gaiaedr3_distance`) | same; SIMBAD mirror at Harvard 200 |
| 14:27 | HTTP 503 | SIMBAD at the CDS 404 |
| 14:37:00 | HTTP 200 | SIMBAD at the CDS 404 |
| 14:37:09 | HTTP 503, four requests in a row (`gaia_source` and `external.gaiaedr3_distance`) | — |

The Gaia archive alternated between 200 and 503 within seconds (during the same hour a network test received «Error 503: Server overloaded: synchronous job rejected due to maximum number of synchronous queued jobs (150) reached»). That is not a stable answer, so `scripts/validate_profiles.py` was **not** run: a run against a service that answers only some requests would give a mix of measured and «not measured» rows for the same object. The counts stay **177 within tolerance, 0 outside, 85 not measured**.

### 5.1 Second run of 2026-11-10 (19:46–20:04 UTC): SIMBAD against the Harvard mirror

AstroTwo 0.1.0-beta.5 with the code of commit `68dbe7c` (sprint D3b: since sprint D3a an HTTP 404 from the CDS sends AstroTwo to the SIMBAD mirror at Harvard). The values compared do not depend on the uncommitted changes present during the run (error messages of HiPS surveys and the Harvard note of the validation script). Tolerances unchanged (section 2.1).

**Summary as measured: 175 values within tolerance, 2 outside, 85 not measured. After the recomparison of the 2 empty spectral types (D25-24, below): 177 within tolerance, 0 outside, 85 not measured.**

| Object | Within tolerance | Outside | Not measured |
|---|---|---|---|
| 51 Peg | 18 | 0 | 13 |
| Vega | 28 | 0 | 12 |
| eta Tau | 24 | 0 | 10 |
| TRAPPIST-1 | 28 | 0 | 14 |
| Barnard's Star | 28 | 0 | 14 |
| 3C 273 | 26 (27 after D25-24) | 1 (0 after D25-24) | 14 |
| M 13 | 23 (24 after D25-24) | 1 (0 after D25-24) | 8 |
| **Total** | **175** (**177** after D25-24) | **2** (**0** after D25-24) | **85** |

**Correction after decision D25-24 (2026-11-10, recomputed without network).** For 3C 273 and M 13 SIMBAD has no spectral type: the reference answer has an empty text (`''`) and AstroTwo's result had no value (`null`). The comparison counted «one side empty» as a fail. The project owner then decided (D25-24) that **an empty text returned by a source is a value declared absent by the source, never a value**, and that the validation compares it that way; the tolerances (section 2.1) are **unchanged**. The two saved rows were recomputed from the files of this run with `uv run python scripts/validate_profiles.py --recompare docs/validation-runs/2026-11-10-run2` (no network, no new measurement): both become **pass** («both empty»), no other row changes. The measured files (`results.json`, `results.md`) are kept as they were; the recomparison is in `results-recompared.json` and `results-recompared.md` next to them, with the rule and the changed rows in its `meta`. Since the same decision, AstroTwo no longer writes a spectral type that SIMBAD declares absent: the Identity section has no `sp_type` row and shows the note «SIMBAD has no spectral type»; the validation script compares this note-only case with the reference in the same way (pass only if the reference is empty or missing).

**State of the services during the run** (checked by hand at 19:21 UTC and recorded in each row):

- **CDS**: SIMBAD at `simbad.cds.unistra.fr` and the VizieR photometry service answered HTTP 404 with an HTML page; TAPVizieR did not answer within 60 s.
- **SIMBAD mirror at Harvard** (`simbad.harvard.edu`): answered. AstroTwo used it (switch after the 404, rule D14-16), and so did the reference side.
- **Gaia archive** (`gea.esac.esa.int`): answered the check by hand, but during the run it timed out or answered HTTP 503 on the AstroTwo side whenever it was asked; after the first failure AstroTwo did not send further Gaia requests in the same profile (rule D25-22).
- **NASA Exoplanet Archive**: HTTP 503.
- **IRSA**: answered.

**What was measured.**

- **SIMBAD (129 pass, 2 fail as measured; 131 pass after D25-24):** main identifier, object type, spectral type, number of references, position and its errors, parallax, proper motion and radial velocity with errors, compared digit for digit with the same `basic` row read from the **Harvard mirror**. Every row says «reference: Harvard mirror, to be repeated against CDS». The 2 fails were the empty spectral type of 3C 273 and M 13: see «Correction» above and section 7.
- **Distance as 1/parallax (5 pass):** from the SIMBAD parallax (also Harvard), relative difference within 1 × 10⁻¹².
- **Fν from 2MASS and AllWISE magnitudes (41 pass):** conversion recomputed with the zero point declared by AstroTwo, relative difference 0.

**What was not measured, to redo:** Gaia values (the archive did not answer AstroTwo during the run), 2MASS and AllWISE magnitudes against VizieR (TAPVizieR down), the VizieR SED series (CDS down), planets (NASA Exoplanet Archive down), and every SIMBAD row again against the CDS.

### 5.2 All rows of the second run of 2026-11-10

"Server and date": host that answered on the reference side, and UTC time.

| Object | Area | Value | AstroTwo | Reference | Server and date | Difference | Outcome |
|---|---|---|---|---|---|---|---|
| 51 Peg | Identity | main_id | *  51 Peg | *  51 Peg | simbad.harvard.edu · 2026-11-10T19:46:52Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| 51 Peg | Identity | main_id (SIMBAD) | *  51 Peg | '*  51 Peg' | simbad.harvard.edu · 2026-11-10T19:46:52Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| 51 Peg | Identity | otype (SIMBAD) | PM* | 'PM*' | simbad.harvard.edu · 2026-11-10T19:46:52Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| 51 Peg | Identity | sp_type (SIMBAD) | G2IV | 'G2IV' | simbad.harvard.edu · 2026-11-10T19:46:52Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| 51 Peg | Identity | nbref (SIMBAD) | 1227 | 1227 | simbad.harvard.edu · 2026-11-10T19:46:52Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 51 Peg | Identity | ra (SIMBAD) | 344.36658535524 deg | 344.36658535524 deg | simbad.harvard.edu · 2026-11-10T19:46:52Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 51 Peg | Identity | dec (SIMBAD) | 20.768832511140005 deg | 20.768832511140005 deg | simbad.harvard.edu · 2026-11-10T19:46:52Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 51 Peg | Identity | coo_err_maj (SIMBAD) | 0.0535 mas | 0.05350000038743019 mas | simbad.harvard.edu · 2026-11-10T19:46:52Z | float32: Δ = -3.8743019209475094e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 51 Peg | Identity | coo_err_min (SIMBAD) | 0.0543 mas | 0.05429999902844429 mas | simbad.harvard.edu · 2026-11-10T19:46:52Z | float32: Δ = 9.715557108824768e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 51 Peg | Identity | coo_err_angle (SIMBAD) | 90.0 deg | 90 deg | simbad.harvard.edu · 2026-11-10T19:46:52Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 51 Peg | Identity | coo_qual (SIMBAD) | A | 'A' | simbad.harvard.edu · 2026-11-10T19:46:52Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| 51 Peg | Identity | section identity (allwise) | None | — | — · 2026-11-10T19:49:54Z | — | not measured (AstroTwo side: NET_TIMEOUT: https://gea.esac.esa.int/tap-server/tap/sync is not reachable (timeout 10.0 s connection, 30.0 s read): HTTPSConnectionPool(host='gea.esac.esa.int', port=443): Read timed out. (read timeout=30.0) — for long queries use tap_query(..., mode='async')) |
| 51 Peg | Identity | section identity (exoplanet) | None | — | — · 2026-11-10T19:49:54Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| 51 Peg | Astrometry | section astrometry (all values) | None | — | — · 2026-11-10T19:49:54Z | — | not measured (AstroTwo side: PROFILE_SECTION_TIMEOUT: Section astrometry: no answer within 35.0 s (gaia).) |
| 51 Peg | Photometry | 2MASS J magnitude (VizieR II/246/out) | 4.655 mag | — | — · 2026-11-10T19:49:54Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:48:54Z: URLError: <urlopen error timed out>) |
| 51 Peg | Photometry | 2MASS J flux_nu (recomputed) | 21.90222908169949 Jy | 21.90222908169949 Jy | — · 2026-11-10T19:49:54Z | relative 0 | pass |
| 51 Peg | Photometry | 2MASS H magnitude (VizieR II/246/out) | 4.234 mag | — | — · 2026-11-10T19:49:54Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:48:54Z: URLError: <urlopen error timed out>) |
| 51 Peg | Photometry | 2MASS H flux_nu (recomputed) | 20.734805058872933 Jy | 20.734805058872933 Jy | — · 2026-11-10T19:49:54Z | relative 0 | pass |
| 51 Peg | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 3.911 mag | — | — · 2026-11-10T19:49:54Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:48:54Z: URLError: <urlopen error timed out>) |
| 51 Peg | Photometry | 2MASS Ks flux_nu (recomputed) | 18.177345212012884 Jy | 18.177345212012884 Jy | — · 2026-11-10T19:49:54Z | relative 0 | pass |
| 51 Peg | Photometry | AllWISE W1 magnitude (VizieR II/328/allwise) | 3.909 mag | — | — · 2026-11-10T19:49:54Z | — | not measured (no AllWISE designation in SIMBAD) |
| 51 Peg | Photometry | AllWISE W1 flux_nu (recomputed) | 8.455061643334856 Jy | 8.455061643334856 Jy | — · 2026-11-10T19:49:54Z | relative 0 | pass |
| 51 Peg | Photometry | AllWISE W2 magnitude (VizieR II/328/allwise) | 3.624 mag | — | — · 2026-11-10T19:49:54Z | — | not measured (no AllWISE designation in SIMBAD) |
| 51 Peg | Photometry | AllWISE W2 flux_nu (recomputed) | 6.100849272570437 Jy | 6.100849272570437 Jy | — · 2026-11-10T19:49:54Z | relative 0 | pass |
| 51 Peg | Photometry | AllWISE W3 magnitude (VizieR II/328/allwise) | 3.929 mag | — | — · 2026-11-10T19:49:54Z | — | not measured (no AllWISE designation in SIMBAD) |
| 51 Peg | Photometry | AllWISE W3 flux_nu (recomputed) | 0.8493817245257934 Jy | 0.8493817245257934 Jy | — · 2026-11-10T19:49:54Z | relative 0 | pass |
| 51 Peg | Photometry | AllWISE W4 magnitude (VizieR II/328/allwise) | 3.904 mag | — | — · 2026-11-10T19:49:54Z | — | not measured (no AllWISE designation in SIMBAD) |
| 51 Peg | Photometry | AllWISE W4 flux_nu (recomputed) | 0.22948911797879706 Jy | 0.22948911797879706 Jy | — · 2026-11-10T19:49:54Z | relative 0 | pass |
| 51 Peg | Photometry | section photometry (Gaia DR3) | None | — | — · 2026-11-10T19:49:54Z | — | not measured (AstroTwo side: PROFILE_GAIA_SKIPPED: Gaia archive: request not sent, the archive did not answer in this profile (NET_TIMEOUT).) |
| 51 Peg | Photometry | section photometry (vizier_sed) | None | — | — · 2026-11-10T19:49:54Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (simbad_failover); no copy in the cache.) |
| 51 Peg | Planets | section planets (exoplanet) | None | — | — · 2026-11-10T19:49:54Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| Vega | Identity | main_id | * alf Lyr | * alf Lyr | simbad.harvard.edu · 2026-11-10T19:50:28Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Identity | main_id (SIMBAD) | * alf Lyr | '* alf Lyr' | simbad.harvard.edu · 2026-11-10T19:50:28Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Identity | otype (SIMBAD) | dS* | 'dS*' | simbad.harvard.edu · 2026-11-10T19:50:28Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Identity | sp_type (SIMBAD) | A0V | 'A0V' | simbad.harvard.edu · 2026-11-10T19:50:28Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Identity | nbref (SIMBAD) | 2817 | 2817 | simbad.harvard.edu · 2026-11-10T19:50:28Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Identity | ra (SIMBAD) | 279.234734787025 deg | 279.234734787025 deg | simbad.harvard.edu · 2026-11-10T19:50:28Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Identity | dec (SIMBAD) | 38.783688956244 deg | 38.783688956244 deg | simbad.harvard.edu · 2026-11-10T19:50:28Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Identity | coo_err_maj (SIMBAD) | 3.51118 mas | 3.5111799240112305 mas | simbad.harvard.edu · 2026-11-10T19:50:28Z | float32: Δ = 7.598876949899136e-08 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Identity | coo_err_min (SIMBAD) | 2.81205 mas | 2.8120501041412354 mas | simbad.harvard.edu · 2026-11-10T19:50:28Z | float32: Δ = -1.0414123519097984e-07 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Identity | coo_err_angle (SIMBAD) | 90.0 deg | 90 deg | simbad.harvard.edu · 2026-11-10T19:50:28Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Identity | coo_qual (SIMBAD) | A | 'A' | simbad.harvard.edu · 2026-11-10T19:50:28Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Identity | section identity (gaia_dr3) | None | — | — · 2026-11-10T19:51:29Z | — | not measured (AstroTwo side: NET_TIMEOUT: https://gea.esac.esa.int/tap-server/tap/sync is not reachable (timeout 10.0 s connection, 30.0 s read): HTTPSConnectionPool(host='gea.esac.esa.int', port=443): Read timed out. (read timeout=30.0) — for long queries use tap_query(..., mode='async')) |
| Vega | Identity | section identity (exoplanet) | None | — | — · 2026-11-10T19:51:29Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| Vega | Astrometry | parallax (SIMBAD) | 130.23 mas | 130.23 mas | simbad.harvard.edu · 2026-11-10T19:50:28Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Astrometry | parallax error (SIMBAD) | 0.36 mas | 0.36000001430511475 mas | simbad.harvard.edu · 2026-11-10T19:50:28Z | float32: Δ = -1.4305114759416426e-08 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Astrometry | pmra (SIMBAD) | 200.94 mas yr-1 | 200.94 mas / yr | simbad.harvard.edu · 2026-11-10T19:50:28Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Astrometry | pmdec (SIMBAD) | 286.23 mas yr-1 | 286.23 mas / yr | simbad.harvard.edu · 2026-11-10T19:50:28Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Astrometry | pm_err_maj (SIMBAD) | 0.32 mas yr-1 | 0.3199999928474426 mas / yr | simbad.harvard.edu · 2026-11-10T19:50:28Z | float32: Δ = 7.152557379708213e-09 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Astrometry | pm_err_min (SIMBAD) | 0.4 mas yr-1 | 0.4000000059604645 mas / yr | simbad.harvard.edu · 2026-11-10T19:50:28Z | float32: Δ = -5.960464455334602e-09 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Astrometry | pm_err_angle (SIMBAD) | 0.0 deg | 0 deg | simbad.harvard.edu · 2026-11-10T19:50:28Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Astrometry | radial_velocity (SIMBAD) | -13.5 km s-1 | -13.5 km / s | simbad.harvard.edu · 2026-11-10T19:50:28Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Astrometry | radial_velocity error (SIMBAD) | 0.4 km s-1 | 0.4000000059604645 km / s | simbad.harvard.edu · 2026-11-10T19:50:28Z | float32: Δ = -5.960464455334602e-09 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Distance | distance_parallax (1/parallax) | 7.6787222606158325 pc | 7.678722260615834 pc | simbad.harvard.edu · 2026-11-10T19:50:28Z | relative 2.31e-16 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Vega | Astrometry | section astrometry (all values) | None | — | — · 2026-11-10T19:51:29Z | — | not measured (AstroTwo side: NET_TIMEOUT: https://gea.esac.esa.int/tap-server/tap/sync is not reachable (timeout 10.0 s connection, 30.0 s read): HTTPSConnectionPool(host='gea.esac.esa.int', port=443): Read timed out. (read timeout=30.0) — for long queries use tap_query(..., mode='async')) |
| Vega | Photometry | 2MASS J magnitude (VizieR II/246/out) | -0.177 mag | — | — · 2026-11-10T19:51:29Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:50:29Z: URLError: <urlopen error timed out>) |
| Vega | Photometry | 2MASS J flux_nu (recomputed) | 1876.239682504227 Jy | 1876.239682504227 Jy | — · 2026-11-10T19:51:29Z | relative 0 | pass |
| Vega | Photometry | 2MASS H magnitude (VizieR II/246/out) | -0.029 mag | — | — · 2026-11-10T19:51:29Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:50:29Z: URLError: <urlopen error timed out>) |
| Vega | Photometry | 2MASS H flux_nu (recomputed) | 1051.7195735309126 Jy | 1051.7195735309126 Jy | — · 2026-11-10T19:51:29Z | relative 0 | pass |
| Vega | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 0.129 mag | — | — · 2026-11-10T19:51:29Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:50:29Z: URLError: <urlopen error timed out>) |
| Vega | Photometry | 2MASS Ks flux_nu (recomputed) | 592.0119253334886 Jy | 592.0119253334886 Jy | — · 2026-11-10T19:51:29Z | relative 0 | pass |
| Vega | Photometry | AllWISE W1 magnitude (VizieR II/328/allwise) | -2.034 mag | — | — · 2026-11-10T19:51:29Z | — | not measured (no AllWISE designation in SIMBAD) |
| Vega | Photometry | AllWISE W1 flux_nu (recomputed) | 2015.1936140552696 Jy | 2015.1936140552696 Jy | — · 2026-11-10T19:51:29Z | relative 0 | pass |
| Vega | Photometry | AllWISE W2 magnitude (VizieR II/328/allwise) | -2.082 mag | — | — · 2026-11-10T19:51:29Z | — | not measured (no AllWISE designation in SIMBAD) |
| Vega | Photometry | AllWISE W2 flux_nu (recomputed) | 1168.9348198705388 Jy | 1168.9348198705388 Jy | — · 2026-11-10T19:51:29Z | relative 0 | pass |
| Vega | Photometry | AllWISE W3 magnitude (VizieR II/328/allwise) | 0.017 mag | — | — · 2026-11-10T19:51:29Z | — | not measured (no AllWISE designation in SIMBAD) |
| Vega | Photometry | AllWISE W3 flux_nu (recomputed) | 31.181924264714503 Jy | 31.181924264714503 Jy | — · 2026-11-10T19:51:29Z | relative 0 | pass |
| Vega | Photometry | AllWISE W4 magnitude (VizieR II/328/allwise) | -0.157 mag | — | — · 2026-11-10T19:51:29Z | — | not measured (no AllWISE designation in SIMBAD) |
| Vega | Photometry | AllWISE W4 flux_nu (recomputed) | 9.664115167028003 Jy | 9.664115167028003 Jy | — · 2026-11-10T19:51:29Z | relative 0 | pass |
| Vega | Photometry | section photometry (vizier_sed) | None | — | — · 2026-11-10T19:51:29Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (simbad_failover); no copy in the cache.) |
| Vega | Planets | section planets (exoplanet) | None | — | — · 2026-11-10T19:51:29Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| eta Tau | Identity | main_id | * eta Tau | * eta Tau | simbad.harvard.edu · 2026-11-10T19:52:02Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Identity | main_id (SIMBAD) | * eta Tau | '* eta Tau' | simbad.harvard.edu · 2026-11-10T19:52:02Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Identity | otype (SIMBAD) | Be* | 'Be*' | simbad.harvard.edu · 2026-11-10T19:52:02Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Identity | sp_type (SIMBAD) | B7III | 'B7III' | simbad.harvard.edu · 2026-11-10T19:52:02Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Identity | nbref (SIMBAD) | 559 | 559 | simbad.harvard.edu · 2026-11-10T19:52:02Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Identity | ra (SIMBAD) | 56.871152303749994 deg | 56.871152303749994 deg | simbad.harvard.edu · 2026-11-10T19:52:02Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Identity | dec (SIMBAD) | 24.105135651944444 deg | 24.105135651944444 deg | simbad.harvard.edu · 2026-11-10T19:52:02Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Identity | coo_err_maj (SIMBAD) | 0.39 mas | 0.38999998569488525 mas | simbad.harvard.edu · 2026-11-10T19:52:02Z | float32: Δ = 1.4305114759416426e-08 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Identity | coo_err_min (SIMBAD) | 0.25 mas | 0.25 mas | simbad.harvard.edu · 2026-11-10T19:52:02Z | float32: Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Identity | coo_err_angle (SIMBAD) | 90.0 deg | 90 deg | simbad.harvard.edu · 2026-11-10T19:52:02Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Identity | coo_qual (SIMBAD) | A | 'A' | simbad.harvard.edu · 2026-11-10T19:52:02Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Identity | section identity (2mass) | None | — | — · 2026-11-10T19:55:04Z | — | not measured (AstroTwo side: NET_TIMEOUT: https://gea.esac.esa.int/tap-server/tap/sync is not reachable (timeout 10.0 s connection, 30.0 s read): HTTPSConnectionPool(host='gea.esac.esa.int', port=443): Read timed out. (read timeout=30.0) — for long queries use tap_query(..., mode='async')) |
| eta Tau | Identity | section identity (allwise) | None | — | — · 2026-11-10T19:55:04Z | — | not measured (AstroTwo side: NET_TIMEOUT: https://gea.esac.esa.int/tap-server/tap/sync is not reachable (timeout 10.0 s connection, 30.0 s read): HTTPSConnectionPool(host='gea.esac.esa.int', port=443): Read timed out. (read timeout=30.0) — for long queries use tap_query(..., mode='async')) |
| eta Tau | Identity | section identity (exoplanet) | None | — | — · 2026-11-10T19:55:04Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| eta Tau | Astrometry | parallax (SIMBAD) | 8.09 mas | 8.09 mas | simbad.harvard.edu · 2026-11-10T19:52:02Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Astrometry | parallax error (SIMBAD) | 0.42 mas | 0.41999998688697815 mas | simbad.harvard.edu · 2026-11-10T19:52:02Z | float32: Δ = 1.3113021835042815e-08 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Astrometry | pmra (SIMBAD) | 19.34 mas yr-1 | 19.34 mas / yr | simbad.harvard.edu · 2026-11-10T19:52:02Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Astrometry | pmdec (SIMBAD) | -43.67 mas yr-1 | -43.67 mas / yr | simbad.harvard.edu · 2026-11-10T19:52:02Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Astrometry | pm_err_maj (SIMBAD) | 0.39 mas yr-1 | 0.38999998569488525 mas / yr | simbad.harvard.edu · 2026-11-10T19:52:02Z | float32: Δ = 1.4305114759416426e-08 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Astrometry | pm_err_min (SIMBAD) | 0.33 mas yr-1 | 0.33000001311302185 mas / yr | simbad.harvard.edu · 2026-11-10T19:52:02Z | float32: Δ = -1.3113021835042815e-08 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Astrometry | pm_err_angle (SIMBAD) | 90.0 deg | 90 deg | simbad.harvard.edu · 2026-11-10T19:52:02Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Astrometry | radial_velocity (SIMBAD) | 5.4 km s-1 | 5.4 km / s | simbad.harvard.edu · 2026-11-10T19:52:02Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Astrometry | radial_velocity error (SIMBAD) | 1.2 km s-1 | 1.2000000476837158 km / s | simbad.harvard.edu · 2026-11-10T19:52:02Z | float32: Δ = -4.768371586472142e-08 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Distance | distance_parallax (1/parallax) | 123.60939431396787 pc | 123.60939431396787 pc | simbad.harvard.edu · 2026-11-10T19:52:02Z | relative 0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| eta Tau | Astrometry | section astrometry (all values) | None | — | — · 2026-11-10T19:55:04Z | — | not measured (AstroTwo side: PROFILE_GAIA_SKIPPED: Gaia archive: request not sent, the archive did not answer in this profile (NET_TIMEOUT).) |
| eta Tau | Photometry | 2MASS J magnitude (VizieR II/246/out) | 2.735 mag | — | — · 2026-11-10T19:55:04Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:54:04Z: URLError: <urlopen error timed out>) |
| eta Tau | Photometry | 2MASS J flux_nu (recomputed) | 128.3773235271312 Jy | 128.3773235271312 Jy | — · 2026-11-10T19:55:04Z | relative 0 | pass |
| eta Tau | Photometry | 2MASS H magnitude (VizieR II/246/out) | 2.735 mag | — | — · 2026-11-10T19:55:04Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:54:04Z: URLError: <urlopen error timed out>) |
| eta Tau | Photometry | 2MASS H flux_nu (recomputed) | 82.47075237878441 Jy | 82.47075237878441 Jy | — · 2026-11-10T19:55:04Z | relative 0 | pass |
| eta Tau | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 2.636 mag | — | — · 2026-11-10T19:55:04Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:54:04Z: URLError: <urlopen error timed out>) |
| eta Tau | Photometry | 2MASS Ks flux_nu (recomputed) | 58.82073610427519 Jy | 58.82073610427519 Jy | — · 2026-11-10T19:55:04Z | relative 0 | pass |
| eta Tau | Photometry | section photometry (Gaia DR3) | None | — | — · 2026-11-10T19:55:04Z | — | not measured (AstroTwo side: PROFILE_GAIA_SKIPPED: Gaia archive: request not sent, the archive did not answer in this profile (NET_TIMEOUT).) |
| eta Tau | Photometry | section photometry (vizier_sed) | None | — | — · 2026-11-10T19:55:04Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (simbad_failover); no copy in the cache.) |
| eta Tau | Planets | section planets (exoplanet) | None | — | — · 2026-11-10T19:55:04Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| TRAPPIST-1 | Identity | main_id | TRAPPIST-1 | TRAPPIST-1 | simbad.harvard.edu · 2026-11-10T19:55:38Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Identity | main_id (SIMBAD) | TRAPPIST-1 | 'TRAPPIST-1' | simbad.harvard.edu · 2026-11-10T19:55:38Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Identity | otype (SIMBAD) | LM* | 'LM*' | simbad.harvard.edu · 2026-11-10T19:55:38Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Identity | sp_type (SIMBAD) | M7.5e | 'M7.5e' | simbad.harvard.edu · 2026-11-10T19:55:38Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Identity | nbref (SIMBAD) | 1373 | 1373 | simbad.harvard.edu · 2026-11-10T19:55:38Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Identity | ra (SIMBAD) | 346.62236872857875 deg | 346.62236872857875 deg | simbad.harvard.edu · 2026-11-10T19:55:38Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Identity | dec (SIMBAD) | -5.041399250518334 deg | -5.041399250518334 deg | simbad.harvard.edu · 2026-11-10T19:55:38Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Identity | coo_err_maj (SIMBAD) | 0.0616 mas | 0.06159999966621399 mas | simbad.harvard.edu · 2026-11-10T19:55:38Z | float32: Δ = 3.337860127183845e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Identity | coo_err_min (SIMBAD) | 0.0536 mas | 0.053599998354911804 mas | simbad.harvard.edu · 2026-11-10T19:55:38Z | float32: Δ = 1.6450881976104448e-09 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Identity | coo_err_angle (SIMBAD) | 90.0 deg | 90 deg | simbad.harvard.edu · 2026-11-10T19:55:38Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Identity | coo_qual (SIMBAD) | A | 'A' | simbad.harvard.edu · 2026-11-10T19:55:38Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Identity | section identity (2mass) | None | — | — · 2026-11-10T19:57:43Z | — | not measured (AstroTwo side: NET_TIMEOUT: https://gea.esac.esa.int/tap-server/tap/sync is not reachable (timeout 10.0 s connection, 30.0 s read): HTTPSConnectionPool(host='gea.esac.esa.int', port=443): Read timed out. (read timeout=30.0) — for long queries use tap_query(..., mode='async')) |
| TRAPPIST-1 | Identity | section identity (allwise) | None | — | — · 2026-11-10T19:57:43Z | — | not measured (AstroTwo side: NET_TIMEOUT: https://gea.esac.esa.int/tap-server/tap/sync is not reachable (timeout 10.0 s connection, 30.0 s read): HTTPSConnectionPool(host='gea.esac.esa.int', port=443): Read timed out. (read timeout=30.0) — for long queries use tap_query(..., mode='async')) |
| TRAPPIST-1 | Identity | section identity (exoplanet) | None | — | — · 2026-11-10T19:57:43Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| TRAPPIST-1 | Astrometry | parallax (SIMBAD) | 80.2123 mas | 80.2123 mas | simbad.harvard.edu · 2026-11-10T19:55:38Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Astrometry | parallax error (SIMBAD) | 0.0716 mas | 0.07159999758005142 mas | simbad.harvard.edu · 2026-11-10T19:55:38Z | float32: Δ = 2.4199485748610527e-09 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Astrometry | pmra (SIMBAD) | 930.788 mas yr-1 | 930.788 mas / yr | simbad.harvard.edu · 2026-11-10T19:55:38Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Astrometry | pmdec (SIMBAD) | -479.038 mas yr-1 | -479.038 mas / yr | simbad.harvard.edu · 2026-11-10T19:55:38Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Astrometry | pm_err_maj (SIMBAD) | 0.087 mas yr-1 | 0.08699999749660492 mas / yr | simbad.harvard.edu · 2026-11-10T19:55:38Z | float32: Δ = 2.503395074571202e-09 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Astrometry | pm_err_min (SIMBAD) | 0.07 mas yr-1 | 0.07000000029802322 mas / yr | simbad.harvard.edu · 2026-11-10T19:55:38Z | float32: Δ = -2.98023217215615e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Astrometry | pm_err_angle (SIMBAD) | 90.0 deg | 90 deg | simbad.harvard.edu · 2026-11-10T19:55:38Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Astrometry | radial_velocity (SIMBAD) | -52.003101 km s-1 | -52.003101 km / s | simbad.harvard.edu · 2026-11-10T19:55:38Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Astrometry | radial_velocity error (SIMBAD) | 0.134416 km s-1 | 0.13441599905490875 km / s | simbad.harvard.edu · 2026-11-10T19:55:38Z | float32: Δ = 9.45091255255548e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Distance | distance_parallax (1/parallax) | 12.46691592187233 pc | 12.466915921872332 pc | simbad.harvard.edu · 2026-11-10T19:55:38Z | relative 1.42e-16 | pass (reference: Harvard mirror, to be repeated against CDS) |
| TRAPPIST-1 | Astrometry | section astrometry (all values) | None | — | — · 2026-11-10T19:57:43Z | — | not measured (AstroTwo side: PROFILE_GAIA_SKIPPED: Gaia archive: request not sent, the archive did not answer in this profile (NET_TIMEOUT).) |
| TRAPPIST-1 | Photometry | 2MASS J magnitude (VizieR II/246/out) | 11.354 mag | — | — · 2026-11-10T19:56:43Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:55:43Z: URLError: <urlopen error timed out>) |
| TRAPPIST-1 | Photometry | 2MASS J flux_nu (recomputed) | 0.045802408633597455 Jy | 0.045802408633597455 Jy | — · 2026-11-10T19:57:43Z | relative 0 | pass |
| TRAPPIST-1 | Photometry | 2MASS H magnitude (VizieR II/246/out) | 10.718 mag | — | — · 2026-11-10T19:56:43Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:55:43Z: URLError: <urlopen error timed out>) |
| TRAPPIST-1 | Photometry | 2MASS H flux_nu (recomputed) | 0.05285668920285924 Jy | 0.05285668920285924 Jy | — · 2026-11-10T19:57:43Z | relative 0 | pass |
| TRAPPIST-1 | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 10.296 mag | — | — · 2026-11-10T19:56:43Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:55:43Z: URLError: <urlopen error timed out>) |
| TRAPPIST-1 | Photometry | 2MASS Ks flux_nu (recomputed) | 0.05076103342185157 Jy | 0.05076103342185157 Jy | — · 2026-11-10T19:57:43Z | relative 0 | pass |
| TRAPPIST-1 | Photometry | AllWISE W1 magnitude (VizieR II/328/allwise) | 10.068 mag | — | — · 2026-11-10T19:57:43Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:56:43Z: URLError: <urlopen error timed out>) |
| TRAPPIST-1 | Photometry | AllWISE W1 flux_nu (recomputed) | 0.02907480283019595 Jy | 0.02907480283019595 Jy | — · 2026-11-10T19:57:43Z | relative 0 | pass |
| TRAPPIST-1 | Photometry | AllWISE W2 magnitude (VizieR II/328/allwise) | 9.807 mag | — | — · 2026-11-10T19:57:43Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:56:43Z: URLError: <urlopen error timed out>) |
| TRAPPIST-1 | Photometry | AllWISE W2 flux_nu (recomputed) | 0.02052061136529633 Jy | 0.02052061136529633 Jy | — · 2026-11-10T19:57:43Z | relative 0 | pass |
| TRAPPIST-1 | Photometry | AllWISE W3 magnitude (VizieR II/328/allwise) | 9.51 mag | — | — · 2026-11-10T19:57:43Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:56:43Z: URLError: <urlopen error timed out>) |
| TRAPPIST-1 | Photometry | AllWISE W3 flux_nu (recomputed) | 0.0049739671464460915 Jy | 0.0049739671464460915 Jy | — · 2026-11-10T19:57:43Z | relative 0 | pass |
| TRAPPIST-1 | Photometry | AllWISE W4 magnitude (VizieR II/328/allwise) | 8.565 mag | — | — · 2026-11-10T19:57:43Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:56:43Z: URLError: <urlopen error timed out>) |
| TRAPPIST-1 | Photometry | AllWISE W4 flux_nu (recomputed) | 0.0031358992177789773 Jy | 0.0031358992177789773 Jy | — · 2026-11-10T19:57:43Z | relative 0 | pass |
| TRAPPIST-1 | Photometry | section photometry (Gaia DR3) | None | — | — · 2026-11-10T19:57:43Z | — | not measured (AstroTwo side: PROFILE_GAIA_SKIPPED: Gaia archive: request not sent, the archive did not answer in this profile (NET_TIMEOUT).) |
| TRAPPIST-1 | Photometry | section photometry (vizier_sed) | None | — | — · 2026-11-10T19:57:43Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (simbad_failover); no copy in the cache.) |
| TRAPPIST-1 | Planets | section planets (exoplanet) | None | — | — · 2026-11-10T19:57:43Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| Barnard's Star | Identity | main_id | NAME Barnard's star | NAME Barnard's star | simbad.harvard.edu · 2026-11-10T19:58:17Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Identity | main_id (SIMBAD) | NAME Barnard's star | "NAME Barnard's star" | simbad.harvard.edu · 2026-11-10T19:58:17Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Identity | otype (SIMBAD) | BY* | 'BY*' | simbad.harvard.edu · 2026-11-10T19:58:17Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Identity | sp_type (SIMBAD) | M4V | 'M4V' | simbad.harvard.edu · 2026-11-10T19:58:17Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Identity | nbref (SIMBAD) | 924 | 924 | simbad.harvard.edu · 2026-11-10T19:58:17Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Identity | ra (SIMBAD) | 269.4520769586187 deg | 269.4520769586187 deg | simbad.harvard.edu · 2026-11-10T19:58:17Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Identity | dec (SIMBAD) | 4.693364966576667 deg | 4.693364966576667 deg | simbad.harvard.edu · 2026-11-10T19:58:17Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Identity | coo_err_maj (SIMBAD) | 0.0262 mas | 0.026200000196695328 mas | simbad.harvard.edu · 2026-11-10T19:58:17Z | float32: Δ = -1.9669532669297496e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Identity | coo_err_min (SIMBAD) | 0.029 mas | 0.028999999165534973 mas | simbad.harvard.edu · 2026-11-10T19:58:17Z | float32: Δ = 8.344650283265143e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Identity | coo_err_angle (SIMBAD) | 90.0 deg | 90 deg | simbad.harvard.edu · 2026-11-10T19:58:17Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Identity | coo_qual (SIMBAD) | A | 'A' | simbad.harvard.edu · 2026-11-10T19:58:17Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Identity | section identity (2mass) | None | — | — · 2026-11-10T20:01:18Z | — | not measured (AstroTwo side: NET_TIMEOUT: https://gea.esac.esa.int/tap-server/tap/sync is not reachable (timeout 10.0 s connection, 30.0 s read): HTTPSConnectionPool(host='gea.esac.esa.int', port=443): Read timed out. (read timeout=30.0) — for long queries use tap_query(..., mode='async')) |
| Barnard's Star | Identity | section identity (allwise) | None | — | — · 2026-11-10T20:01:18Z | — | not measured (AstroTwo side: NET_TIMEOUT: https://gea.esac.esa.int/tap-server/tap/sync is not reachable (timeout 10.0 s connection, 30.0 s read): HTTPSConnectionPool(host='gea.esac.esa.int', port=443): Read timed out. (read timeout=30.0) — for long queries use tap_query(..., mode='async')) |
| Barnard's Star | Identity | section identity (exoplanet) | None | — | — · 2026-11-10T20:01:18Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| Barnard's Star | Astrometry | parallax (SIMBAD) | 546.9759 mas | 546.9759 mas | simbad.harvard.edu · 2026-11-10T19:58:17Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Astrometry | parallax error (SIMBAD) | 0.0401 mas | 0.04010000079870224 mas | simbad.harvard.edu · 2026-11-10T19:58:17Z | float32: Δ = -7.987022432320856e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Astrometry | pmra (SIMBAD) | -801.551 mas yr-1 | -801.551 mas / yr | simbad.harvard.edu · 2026-11-10T19:58:17Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Astrometry | pmdec (SIMBAD) | 10362.394 mas yr-1 | 10362.394 mas / yr | simbad.harvard.edu · 2026-11-10T19:58:17Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Astrometry | pm_err_maj (SIMBAD) | 0.032 mas yr-1 | 0.03200000151991844 mas / yr | simbad.harvard.edu · 2026-11-10T19:58:17Z | float32: Δ = -1.5199184411063271e-09 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Astrometry | pm_err_min (SIMBAD) | 0.036 mas yr-1 | 0.035999998450279236 mas / yr | simbad.harvard.edu · 2026-11-10T19:58:17Z | float32: Δ = 1.5497207614401098e-09 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Astrometry | pm_err_angle (SIMBAD) | 90.0 deg | 90 deg | simbad.harvard.edu · 2026-11-10T19:58:17Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Astrometry | radial_velocity (SIMBAD) | -110.11 km s-1 | -110.11 km / s | simbad.harvard.edu · 2026-11-10T19:58:17Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Astrometry | radial_velocity error (SIMBAD) | 0.0002 km s-1 | 0.00019999999494757503 km / s | simbad.harvard.edu · 2026-11-10T19:58:17Z | float32: Δ = 5.052424976873318e-12 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Distance | distance_parallax (1/parallax) | 1.828234114153841 pc | 1.828234114153841 pc | simbad.harvard.edu · 2026-11-10T19:58:17Z | relative 0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| Barnard's Star | Astrometry | section astrometry (all values) | None | — | — · 2026-11-10T20:01:18Z | — | not measured (AstroTwo side: PROFILE_GAIA_SKIPPED: Gaia archive: request not sent, the archive did not answer in this profile (NET_TIMEOUT).) |
| Barnard's Star | Photometry | 2MASS J magnitude (VizieR II/246/out) | 5.244 mag | — | — · 2026-11-10T20:00:18Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:59:18Z: URLError: <urlopen error timed out>) |
| Barnard's Star | Photometry | 2MASS J flux_nu (recomputed) | 12.731756297414343 Jy | 12.731756297414343 Jy | — · 2026-11-10T20:01:18Z | relative 0 | pass |
| Barnard's Star | Photometry | 2MASS H magnitude (VizieR II/246/out) | 4.834 mag | — | — · 2026-11-10T20:00:18Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:59:18Z: URLError: <urlopen error timed out>) |
| Barnard's Star | Photometry | 2MASS H flux_nu (recomputed) | 11.931634923776006 Jy | 11.931634923776006 Jy | — · 2026-11-10T20:01:18Z | relative 0 | pass |
| Barnard's Star | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 4.524 mag | — | — · 2026-11-10T20:00:18Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T19:59:18Z: URLError: <urlopen error timed out>) |
| Barnard's Star | Photometry | 2MASS Ks flux_nu (recomputed) | 10.335475340403235 Jy | 10.335475340403235 Jy | — · 2026-11-10T20:01:18Z | relative 0 | pass |
| Barnard's Star | Photometry | AllWISE W1 magnitude (VizieR II/328/allwise) | 4.358 mag | — | — · 2026-11-10T20:01:18Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T20:00:18Z: URLError: <urlopen error timed out>) |
| Barnard's Star | Photometry | AllWISE W1 flux_nu (recomputed) | 5.591351284244348 Jy | 5.591351284244348 Jy | — · 2026-11-10T20:01:18Z | relative 0 | pass |
| Barnard's Star | Photometry | AllWISE W2 magnitude (VizieR II/328/allwise) | 3.658 mag | — | — · 2026-11-10T20:01:18Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T20:00:18Z: URLError: <urlopen error timed out>) |
| Barnard's Star | Photometry | AllWISE W2 flux_nu (recomputed) | 5.912760601646863 Jy | 5.912760601646863 Jy | — · 2026-11-10T20:01:18Z | relative 0 | pass |
| Barnard's Star | Photometry | AllWISE W3 magnitude (VizieR II/328/allwise) | 4.376 mag | — | — · 2026-11-10T20:01:18Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T20:00:18Z: URLError: <urlopen error timed out>) |
| Barnard's Star | Photometry | AllWISE W3 flux_nu (recomputed) | 0.562733684700413 Jy | 0.562733684700413 Jy | — · 2026-11-10T20:01:18Z | relative 0 | pass |
| Barnard's Star | Photometry | AllWISE W4 magnitude (VizieR II/328/allwise) | 3.969 mag | — | — · 2026-11-10T20:01:18Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T20:00:18Z: URLError: <urlopen error timed out>) |
| Barnard's Star | Photometry | AllWISE W4 flux_nu (recomputed) | 0.2161534127394319 Jy | 0.2161534127394319 Jy | — · 2026-11-10T20:01:18Z | relative 0 | pass |
| Barnard's Star | Photometry | section photometry (Gaia DR3) | None | — | — · 2026-11-10T20:01:18Z | — | not measured (AstroTwo side: PROFILE_GAIA_SKIPPED: Gaia archive: request not sent, the archive did not answer in this profile (NET_TIMEOUT).) |
| Barnard's Star | Photometry | section photometry (vizier_sed) | None | — | — · 2026-11-10T20:01:18Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (simbad_failover); no copy in the cache.) |
| Barnard's Star | Planets | section planets (exoplanet) | None | — | — · 2026-11-10T20:01:18Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| 3C 273 | Identity | main_id | 3C 273 | 3C 273 | simbad.harvard.edu · 2026-11-10T20:01:53Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Identity | main_id (SIMBAD) | 3C 273 | '3C 273' | simbad.harvard.edu · 2026-11-10T20:01:53Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Identity | otype (SIMBAD) | BLL | 'BLL' | simbad.harvard.edu · 2026-11-10T20:01:53Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Identity | sp_type (SIMBAD) |  | '' | simbad.harvard.edu · 2026-11-10T20:01:53Z | one is empty | fail as measured → **pass** after the D25-24 recomparison (both empty; reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Identity | nbref (SIMBAD) | 6064 | 6064 | simbad.harvard.edu · 2026-11-10T20:01:53Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Identity | ra (SIMBAD) | 187.27791594049 deg | 187.27791594049 deg | simbad.harvard.edu · 2026-11-10T20:01:53Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Identity | dec (SIMBAD) | 2.05238823055 deg | 2.05238823055 deg | simbad.harvard.edu · 2026-11-10T20:01:53Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Identity | coo_err_maj (SIMBAD) | 0.0181 mas | 0.01810000091791153 mas | simbad.harvard.edu · 2026-11-10T20:01:53Z | float32: Δ = -9.179115280366634e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Identity | coo_err_min (SIMBAD) | 0.0129 mas | 0.012900000438094139 mas | simbad.harvard.edu · 2026-11-10T20:01:53Z | float32: Δ = -4.380941390907944e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Identity | coo_err_angle (SIMBAD) | 90.0 deg | 90 deg | simbad.harvard.edu · 2026-11-10T20:01:53Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Identity | coo_qual (SIMBAD) | A | 'A' | simbad.harvard.edu · 2026-11-10T20:01:53Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Identity | section identity (2mass) | None | — | — · 2026-11-10T20:03:55Z | — | not measured (AstroTwo side: NET_TIMEOUT: https://gea.esac.esa.int/tap-server/tap/sync is not reachable (timeout 10.0 s connection, 30.0 s read): HTTPSConnectionPool(host='gea.esac.esa.int', port=443): Read timed out. (read timeout=30.0) — for long queries use tap_query(..., mode='async')) |
| 3C 273 | Identity | section identity (allwise) | None | — | — · 2026-11-10T20:03:55Z | — | not measured (AstroTwo side: NET_TIMEOUT: https://gea.esac.esa.int/tap-server/tap/sync is not reachable (timeout 10.0 s connection, 30.0 s read): HTTPSConnectionPool(host='gea.esac.esa.int', port=443): Read timed out. (read timeout=30.0) — for long queries use tap_query(..., mode='async')) |
| 3C 273 | Identity | section identity (exoplanet) | None | — | — · 2026-11-10T20:03:55Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| 3C 273 | Astrometry | parallax (SIMBAD) | 0.0108 mas | 0.0108 mas | simbad.harvard.edu · 2026-11-10T20:01:53Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Astrometry | parallax error (SIMBAD) | 0.0408 mas | 0.040800001472234726 mas | simbad.harvard.edu · 2026-11-10T20:01:53Z | float32: Δ = -1.4722347230211597e-09 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Astrometry | pmra (SIMBAD) | -0.023 mas yr-1 | -0.023 mas / yr | simbad.harvard.edu · 2026-11-10T20:01:53Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Astrometry | pmdec (SIMBAD) | 0.098 mas yr-1 | 0.098 mas / yr | simbad.harvard.edu · 2026-11-10T20:01:53Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Astrometry | pm_err_maj (SIMBAD) | 0.027 mas yr-1 | 0.027000000700354576 mas / yr | simbad.harvard.edu · 2026-11-10T20:01:53Z | float32: Δ = -7.003545764161512e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Astrometry | pm_err_min (SIMBAD) | 0.018 mas yr-1 | 0.017999999225139618 mas / yr | simbad.harvard.edu · 2026-11-10T20:01:53Z | float32: Δ = 7.748603807200549e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Astrometry | pm_err_angle (SIMBAD) | 90.0 deg | 90 deg | simbad.harvard.edu · 2026-11-10T20:01:53Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Astrometry | radial_velocity (SIMBAD) | 43555.48595565044 km s-1 | 43555.48595565044 km / s | simbad.harvard.edu · 2026-11-10T20:01:53Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Astrometry | radial_velocity error (SIMBAD) | 0.0005 km s-1 | 0.0005000000237487257 km / s | simbad.harvard.edu · 2026-11-10T20:01:53Z | float32: Δ = -2.374872564228636e-11 | pass (reference: Harvard mirror, to be repeated against CDS) |
| 3C 273 | Astrometry | section astrometry (all values) | None | — | — · 2026-11-10T20:03:55Z | — | not measured (AstroTwo side: PROFILE_GAIA_SKIPPED: Gaia archive: request not sent, the archive did not answer in this profile (NET_TIMEOUT).) |
| 3C 273 | Photometry | 2MASS J magnitude (VizieR II/246/out) | 11.766 mag | — | — · 2026-11-10T20:02:55Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T20:01:55Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | 2MASS J flux_nu (recomputed) | 0.03133922966403283 Jy | 0.03133922966403283 Jy | — · 2026-11-10T20:03:55Z | relative 0 | pass |
| 3C 273 | Photometry | 2MASS H magnitude (VizieR II/246/out) | 11.047 mag | — | — · 2026-11-10T20:02:55Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T20:01:55Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | 2MASS H flux_nu (recomputed) | 0.039039114353080225 Jy | 0.039039114353080225 Jy | — · 2026-11-10T20:03:55Z | relative 0 | pass |
| 3C 273 | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 9.976 mag | — | — · 2026-11-10T20:02:55Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T20:01:55Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | 2MASS Ks flux_nu (recomputed) | 0.06816013707001028 Jy | 0.06816013707001028 Jy | — · 2026-11-10T20:03:55Z | relative 0 | pass |
| 3C 273 | Photometry | AllWISE W1 magnitude (VizieR II/328/allwise) | 8.395 mag | — | — · 2026-11-10T20:03:55Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T20:02:55Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | AllWISE W1 flux_nu (recomputed) | 0.13574279218926905 Jy | 0.13574279218926905 Jy | — · 2026-11-10T20:03:55Z | relative 0 | pass |
| 3C 273 | Photometry | AllWISE W2 magnitude (VizieR II/328/allwise) | 7.425 mag | — | — · 2026-11-10T20:03:55Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T20:02:55Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | AllWISE W2 flux_nu (recomputed) | 0.18407308688885263 Jy | 0.18407308688885263 Jy | — · 2026-11-10T20:03:55Z | relative 0 | pass |
| 3C 273 | Photometry | AllWISE W3 magnitude (VizieR II/328/allwise) | 5.147 mag | — | — · 2026-11-10T20:03:55Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T20:02:55Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | AllWISE W3 flux_nu (recomputed) | 0.27663231578353836 Jy | 0.27663231578353836 Jy | — · 2026-11-10T20:03:55Z | relative 0 | pass |
| 3C 273 | Photometry | AllWISE W4 magnitude (VizieR II/328/allwise) | 2.942 mag | — | — · 2026-11-10T20:03:55Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T20:02:55Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | AllWISE W4 flux_nu (recomputed) | 0.5566242164419136 Jy | 0.5566242164419136 Jy | — · 2026-11-10T20:03:55Z | relative 0 | pass |
| 3C 273 | Photometry | section photometry (Gaia DR3) | None | — | — · 2026-11-10T20:03:55Z | — | not measured (AstroTwo side: PROFILE_GAIA_SKIPPED: Gaia archive: request not sent, the archive did not answer in this profile (NET_TIMEOUT).) |
| 3C 273 | Photometry | section photometry (vizier_sed) | None | — | — · 2026-11-10T20:03:55Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (simbad_failover); no copy in the cache.) |
| 3C 273 | Planets | section planets (exoplanet) | None | — | — · 2026-11-10T20:03:55Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| M 13 | Identity | main_id | M  13 | M  13 | simbad.harvard.edu · 2026-11-10T20:04:00Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Identity | main_id (SIMBAD) | M  13 | 'M  13' | simbad.harvard.edu · 2026-11-10T20:04:00Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Identity | otype (SIMBAD) | GlC | 'GlC' | simbad.harvard.edu · 2026-11-10T20:04:00Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Identity | sp_type (SIMBAD) |  | '' | simbad.harvard.edu · 2026-11-10T20:04:00Z | one is empty | fail as measured → **pass** after the D25-24 recomparison (both empty; reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Identity | nbref (SIMBAD) | 2316 | 2316 | simbad.harvard.edu · 2026-11-10T20:04:00Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Identity | ra (SIMBAD) | 250.42347499999994 deg | 250.42347499999994 deg | simbad.harvard.edu · 2026-11-10T20:04:00Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Identity | dec (SIMBAD) | 36.46131944444445 deg | 36.46131944444445 deg | simbad.harvard.edu · 2026-11-10T20:04:00Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Identity | coo_err_maj (SIMBAD) |  | None mas | simbad.harvard.edu · 2026-11-10T20:04:00Z | both empty | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Identity | coo_err_min (SIMBAD) |  | None mas | simbad.harvard.edu · 2026-11-10T20:04:00Z | both empty | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Identity | coo_err_angle (SIMBAD) |  | None deg | simbad.harvard.edu · 2026-11-10T20:04:00Z | both empty | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Identity | coo_qual (SIMBAD) | C | 'C' | simbad.harvard.edu · 2026-11-10T20:04:00Z | text | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Identity | section identity (gaia_dr3) | None | — | — · 2026-11-10T20:04:01Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://gea.esac.esa.int/tap-server/tap/sync: HTTP response 503 without a VOTable) |
| M 13 | Identity | section identity (exoplanet) | None | — | — · 2026-11-10T20:04:01Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |
| M 13 | Astrometry | parallax (SIMBAD) | 0.127 mas | 0.127 mas | simbad.harvard.edu · 2026-11-10T20:04:00Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Astrometry | parallax error (SIMBAD) | 0.01 mas | 0.009999999776482582 mas | simbad.harvard.edu · 2026-11-10T20:04:00Z | float32: Δ = 2.2351741811588166e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Astrometry | pmra (SIMBAD) | -3.18 mas yr-1 | -3.18 mas / yr | simbad.harvard.edu · 2026-11-10T20:04:00Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Astrometry | pmdec (SIMBAD) | -2.56 mas yr-1 | -2.56 mas / yr | simbad.harvard.edu · 2026-11-10T20:04:00Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Astrometry | pm_err_maj (SIMBAD) | 0.01 mas yr-1 | 0.009999999776482582 mas / yr | simbad.harvard.edu · 2026-11-10T20:04:00Z | float32: Δ = 2.2351741811588166e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Astrometry | pm_err_min (SIMBAD) | 0.01 mas yr-1 | 0.009999999776482582 mas / yr | simbad.harvard.edu · 2026-11-10T20:04:00Z | float32: Δ = 2.2351741811588166e-10 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Astrometry | pm_err_angle (SIMBAD) | 90.0 deg | 90 deg | simbad.harvard.edu · 2026-11-10T20:04:00Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Astrometry | radial_velocity (SIMBAD) | -244.4 km s-1 | -244.4 km / s | simbad.harvard.edu · 2026-11-10T20:04:00Z | Δ = 0.0 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Astrometry | radial_velocity error (SIMBAD) | 0.3 km s-1 | 0.30000001192092896 km / s | simbad.harvard.edu · 2026-11-10T20:04:00Z | float32: Δ = -1.1920928966180355e-08 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Distance | distance_parallax (1/parallax) | 7874.015748031495 pc | 7874.015748031496 pc | simbad.harvard.edu · 2026-11-10T20:04:00Z | relative 1.16e-16 | pass (reference: Harvard mirror, to be repeated against CDS) |
| M 13 | Astrometry | section astrometry (all values) | None | — | — · 2026-11-10T20:04:01Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://gea.esac.esa.int/tap-server/tap/sync: HTTP response 503 without a VOTable) |
| M 13 | Photometry | 2MASS J magnitude (VizieR II/246/out) | 10.647 mag | — | — · 2026-11-10T20:04:01Z | — | not measured (no 2MASS designation in SIMBAD) |
| M 13 | Photometry | 2MASS J flux_nu (recomputed) | 0.08783918893556711 Jy | 0.08783918893556711 Jy | — · 2026-11-10T20:04:01Z | relative 0 | pass |
| M 13 | Photometry | 2MASS H magnitude (VizieR II/246/out) | 10.452 mag | — | — · 2026-11-10T20:04:01Z | — | not measured (no 2MASS designation in SIMBAD) |
| M 13 | Photometry | 2MASS H flux_nu (recomputed) | 0.06753049865722717 Jy | 0.06753049865722717 Jy | — · 2026-11-10T20:04:01Z | relative 0 | pass |
| M 13 | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 10.08 mag | — | — · 2026-11-10T20:04:01Z | — | not measured (no 2MASS designation in SIMBAD) |
| M 13 | Photometry | 2MASS Ks flux_nu (recomputed) | 0.06193418900661836 Jy | 0.06193418900661836 Jy | — · 2026-11-10T20:04:01Z | relative 0 | pass |
| M 13 | Photometry | section photometry (vizier_sed) | None | — | — · 2026-11-10T20:04:01Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (simbad_failover); no copy in the cache.) |
| M 13 | Planets | section planets (exoplanet) | None | — | — · 2026-11-10T20:04:01Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://exoplanetarchive.ipac.caltech.edu/TAP/sync: HTTP response 503 without a VOTable) |

### 5.3 First run of 2026-11-10 (16:12–16:23 UTC)

AstroTwo 0.1.0-beta.5 with the code of sprint D2 (after commit `ff0aee8`, which fixed the tolerances). The values compared do not depend on the D2 changes, which concern only the language of notes and messages.

**Summary: 22 values within tolerance, 0 outside, 49 not measured.**

| Object | Within tolerance | Outside | Not measured |
|---|---|---|---|
| 51 Peg | 3 | 0 | 7 |
| Vega | 3 | 0 | 6 |
| eta Tau | 3 | 0 | 7 |
| TRAPPIST-1 | 3 | 0 | 7 |
| Barnard's Star | 0 | 0 | 4 |
| 3C 273 | 7 | 0 | 11 |
| M 13 | 3 | 0 | 7 |
| **Total** | **22** | **0** | **49** |

**State of the services during the run** (checked by hand before and after it, and recorded in each row):

- **CDS** (SIMBAD at `simbad.cds.unistra.fr`, VizieR, the VizieR photometry service): SIMBAD and the photometry service answered **HTTP 404** with an HTML page; TAPVizieR did not answer within 60 s. The SIMBAD mirror at Harvard (`simbad.harvard.edu`) answered.
- **Gaia archive** (`gea.esac.esa.int`): HTTP 503 or no answer within the time limit.
- **NASA Exoplanet Archive**: HTTP 503, page «Under Maintenance».
- **IRSA**: answered (AstroTwo reads 2MASS and AllWISE from IRSA).

**What was measured.** Only the conversions of 2MASS and AllWISE magnitudes into flux densities (Fν), recomputed independently with the zero point that AstroTwo declares. All 22 match **exactly** (relative difference 0). The magnitudes themselves could not be compared with VizieR, which was down, so these 22 rows check the conversion, not the catalogue values.

**What was not measured, to redo.** Every value read from SIMBAD, the Gaia archive (positions, parallaxes, proper motions, Gaia photometry, distances) and the NASA Exoplanet Archive, and the 2MASS and AllWISE magnitudes against VizieR. The rows below say, for each, which service did not answer, on which side (AstroTwo or reference) and when. The same script, run again when the services answer, fills them in with the same tolerances (section 2.1).

A first run the same day (15:48–16:03 UTC, before the change of the profile notes to English, DD-3) gave the same outcome: 22 within tolerance, 0 outside, 52 not measured.

### 5.4 All rows of the first run of 2026-11-10

"Server and date": host that answered on the reference side, and UTC time. "—" for the server means that the row has no reference answer (service down) or that the check is a recomputation that needs none.

| Object | Area | Value | AstroTwo | Reference | Server and date | Difference | Outcome |
|---|---|---|---|---|---|---|---|
| 51 Peg | Identity | main_id | — | — | — · 2026-11-10T16:13:46Z | — | not measured (AstroTwo side: SIMBAD did not answer (SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable)) |
| 51 Peg | Identity | section identity (all values) | — | — | — · 2026-11-10T16:13:46Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable) |
| 51 Peg | Astrometry | section astrometry (all values) | — | — | — · 2026-11-10T16:13:46Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://gea.esac.esa.int/tap-server/tap/sync: HTTP response 503 without a VOTable) |
| 51 Peg | Photometry | 2MASS J magnitude (VizieR II/246/out) | 4.655 mag | — | — · 2026-11-10T16:13:46Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:12:46Z: URLError: <urlopen error timed out>) |
| 51 Peg | Photometry | 2MASS J flux_nu (recomputed) | 21.90222908169949 Jy | 21.90222908169949 Jy | — · 2026-11-10T16:13:46Z | relative 0 | pass |
| 51 Peg | Photometry | 2MASS H magnitude (VizieR II/246/out) | 4.234 mag | — | — · 2026-11-10T16:13:46Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:12:46Z: URLError: <urlopen error timed out>) |
| 51 Peg | Photometry | 2MASS H flux_nu (recomputed) | 20.734805058872933 Jy | 20.734805058872933 Jy | — · 2026-11-10T16:13:46Z | relative 0 | pass |
| 51 Peg | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 3.911 mag | — | — · 2026-11-10T16:13:46Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:12:46Z: URLError: <urlopen error timed out>) |
| 51 Peg | Photometry | 2MASS Ks flux_nu (recomputed) | 18.177345212012884 Jy | 18.177345212012884 Jy | — · 2026-11-10T16:13:46Z | relative 0 | pass |
| 51 Peg | Photometry | section photometry (vizier_sed) | — | — | — · 2026-11-10T16:13:46Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://vizier.cds.unistra.fr/viz-bin/sed: HTTP response 404 without a VOTable) |
| Vega | Identity | main_id | — | — | — · 2026-11-10T16:15:06Z | — | not measured (AstroTwo side: SIMBAD did not answer (SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable)) |
| Vega | Identity | section identity (all values) | — | — | — · 2026-11-10T16:15:06Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable) |
| Vega | Photometry | 2MASS J magnitude (VizieR II/246/out) | -0.177 mag | — | — · 2026-11-10T16:15:06Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:14:06Z: URLError: <urlopen error timed out>) |
| Vega | Photometry | 2MASS J flux_nu (recomputed) | 1876.239682504227 Jy | 1876.239682504227 Jy | — · 2026-11-10T16:15:06Z | relative 0 | pass |
| Vega | Photometry | 2MASS H magnitude (VizieR II/246/out) | -0.029 mag | — | — · 2026-11-10T16:15:06Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:14:06Z: URLError: <urlopen error timed out>) |
| Vega | Photometry | 2MASS H flux_nu (recomputed) | 1051.7195735309126 Jy | 1051.7195735309126 Jy | — · 2026-11-10T16:15:06Z | relative 0 | pass |
| Vega | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 0.129 mag | — | — · 2026-11-10T16:15:06Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:14:06Z: URLError: <urlopen error timed out>) |
| Vega | Photometry | 2MASS Ks flux_nu (recomputed) | 592.0119253334886 Jy | 592.0119253334886 Jy | — · 2026-11-10T16:15:06Z | relative 0 | pass |
| Vega | Photometry | section photometry (vizier_sed) | — | — | — · 2026-11-10T16:15:06Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (mocserver); no copy in the cache.) |
| eta Tau | Identity | main_id | — | — | — · 2026-11-10T16:16:40Z | — | not measured (AstroTwo side: SIMBAD did not answer (SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable)) |
| eta Tau | Identity | section identity (all values) | — | — | — · 2026-11-10T16:16:40Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable) |
| eta Tau | Astrometry | section astrometry (all values) | — | — | — · 2026-11-10T16:16:40Z | — | not measured (AstroTwo side: NET_TIMEOUT: https://gea.esac.esa.int/tap-server/tap/sync is not reachable (timeout 10.0 s connection, 30.0 s read): HTTPSConnectionPool(host='gea.esac.esa.int', port=443): Read timed out. (read timeout=30.0) — for long queries use tap_query(..., mode='async')) |
| eta Tau | Photometry | 2MASS J magnitude (VizieR II/246/out) | 2.735 mag | — | — · 2026-11-10T16:16:40Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:15:40Z: URLError: <urlopen error timed out>) |
| eta Tau | Photometry | 2MASS J flux_nu (recomputed) | 128.3773235271312 Jy | 128.3773235271312 Jy | — · 2026-11-10T16:16:40Z | relative 0 | pass |
| eta Tau | Photometry | 2MASS H magnitude (VizieR II/246/out) | 2.735 mag | — | — · 2026-11-10T16:16:40Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:15:40Z: URLError: <urlopen error timed out>) |
| eta Tau | Photometry | 2MASS H flux_nu (recomputed) | 82.47075237878441 Jy | 82.47075237878441 Jy | — · 2026-11-10T16:16:40Z | relative 0 | pass |
| eta Tau | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 2.636 mag | — | — · 2026-11-10T16:16:40Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:15:40Z: URLError: <urlopen error timed out>) |
| eta Tau | Photometry | 2MASS Ks flux_nu (recomputed) | 58.82073610427519 Jy | 58.82073610427519 Jy | — · 2026-11-10T16:16:40Z | relative 0 | pass |
| eta Tau | Photometry | section photometry (vizier_sed) | — | — | — · 2026-11-10T16:16:40Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (mocserver); no copy in the cache.) |
| TRAPPIST-1 | Identity | main_id | — | — | — · 2026-11-10T16:18:47Z | — | not measured (AstroTwo side: SIMBAD did not answer (SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable)) |
| TRAPPIST-1 | Identity | section identity (all values) | — | — | — · 2026-11-10T16:18:47Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable) |
| TRAPPIST-1 | Astrometry | section astrometry (all values) | — | — | — · 2026-11-10T16:18:47Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://gea.esac.esa.int/tap-server/tap/sync: HTTP response 503 without a VOTable) |
| TRAPPIST-1 | Photometry | 2MASS J magnitude (VizieR II/246/out) | 11.354 mag | — | — · 2026-11-10T16:17:47Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:16:47Z: URLError: <urlopen error timed out>) |
| TRAPPIST-1 | Photometry | 2MASS J flux_nu (recomputed) | 0.045802408633597455 Jy | 0.045802408633597455 Jy | — · 2026-11-10T16:18:47Z | relative 0 | pass |
| TRAPPIST-1 | Photometry | 2MASS H magnitude (VizieR II/246/out) | 10.718 mag | — | — · 2026-11-10T16:17:47Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:16:47Z: URLError: <urlopen error timed out>) |
| TRAPPIST-1 | Photometry | 2MASS H flux_nu (recomputed) | 0.05285668920285924 Jy | 0.05285668920285924 Jy | — · 2026-11-10T16:18:47Z | relative 0 | pass |
| TRAPPIST-1 | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 10.296 mag | — | — · 2026-11-10T16:17:47Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:16:47Z: URLError: <urlopen error timed out>) |
| TRAPPIST-1 | Photometry | 2MASS Ks flux_nu (recomputed) | 0.05076103342185157 Jy | 0.05076103342185157 Jy | — · 2026-11-10T16:18:47Z | relative 0 | pass |
| TRAPPIST-1 | Photometry | section photometry (vizier_sed) | — | — | — · 2026-11-10T16:18:47Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (mocserver); no copy in the cache.) |
| Barnard's Star | Identity | main_id | — | — | — · 2026-11-10T16:20:53Z | — | not measured (AstroTwo side: SIMBAD did not answer (SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable)) |
| Barnard's Star | Identity | section identity (all values) | — | — | — · 2026-11-10T16:20:53Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable) |
| Barnard's Star | Astrometry | section astrometry (all values) | — | — | — · 2026-11-10T16:20:53Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://gea.esac.esa.int/tap-server/tap/sync: HTTP response 503 without a VOTable) |
| Barnard's Star | Photometry | section photometry (vizier_sed) | — | — | — · 2026-11-10T16:20:53Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (mocserver); no copy in the cache.) |
| 3C 273 | Identity | main_id | — | — | — · 2026-11-10T16:22:59Z | — | not measured (AstroTwo side: SIMBAD did not answer (SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable)) |
| 3C 273 | Identity | section identity (all values) | — | — | — · 2026-11-10T16:22:59Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable) |
| 3C 273 | Astrometry | section astrometry (all values) | — | — | — · 2026-11-10T16:22:59Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://gea.esac.esa.int/tap-server/tap/sync: HTTP response 503 without a VOTable) |
| 3C 273 | Photometry | 2MASS J magnitude (VizieR II/246/out) | 11.766 mag | — | — · 2026-11-10T16:21:59Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:20:59Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | 2MASS J flux_nu (recomputed) | 0.03133922966403283 Jy | 0.03133922966403283 Jy | — · 2026-11-10T16:22:59Z | relative 0 | pass |
| 3C 273 | Photometry | 2MASS H magnitude (VizieR II/246/out) | 11.047 mag | — | — · 2026-11-10T16:21:59Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:20:59Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | 2MASS H flux_nu (recomputed) | 0.039039114353080225 Jy | 0.039039114353080225 Jy | — · 2026-11-10T16:22:59Z | relative 0 | pass |
| 3C 273 | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 9.976 mag | — | — · 2026-11-10T16:21:59Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:20:59Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | 2MASS Ks flux_nu (recomputed) | 0.06816013707001028 Jy | 0.06816013707001028 Jy | — · 2026-11-10T16:22:59Z | relative 0 | pass |
| 3C 273 | Photometry | AllWISE W1 magnitude (VizieR II/328/allwise) | 8.395 mag | — | — · 2026-11-10T16:22:59Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:21:59Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | AllWISE W1 flux_nu (recomputed) | 0.13574279218926905 Jy | 0.13574279218926905 Jy | — · 2026-11-10T16:22:59Z | relative 0 | pass |
| 3C 273 | Photometry | AllWISE W2 magnitude (VizieR II/328/allwise) | 7.425 mag | — | — · 2026-11-10T16:22:59Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:21:59Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | AllWISE W2 flux_nu (recomputed) | 0.18407308688885263 Jy | 0.18407308688885263 Jy | — · 2026-11-10T16:22:59Z | relative 0 | pass |
| 3C 273 | Photometry | AllWISE W3 magnitude (VizieR II/328/allwise) | 5.147 mag | — | — · 2026-11-10T16:22:59Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:21:59Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | AllWISE W3 flux_nu (recomputed) | 0.27663231578353836 Jy | 0.27663231578353836 Jy | — · 2026-11-10T16:22:59Z | relative 0 | pass |
| 3C 273 | Photometry | AllWISE W4 magnitude (VizieR II/328/allwise) | 2.942 mag | — | — · 2026-11-10T16:22:59Z | — | not measured (https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync at 2026-11-10T16:21:59Z: URLError: <urlopen error timed out>) |
| 3C 273 | Photometry | AllWISE W4 flux_nu (recomputed) | 0.5566242164419136 Jy | 0.5566242164419136 Jy | — · 2026-11-10T16:22:59Z | relative 0 | pass |
| 3C 273 | Photometry | section photometry (vizier_sed) | — | — | — · 2026-11-10T16:22:59Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (mocserver); no copy in the cache.) |
| M 13 | Identity | main_id | — | — | — · 2026-11-10T16:23:04Z | — | not measured (AstroTwo side: SIMBAD did not answer (SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable)) |
| M 13 | Identity | section identity (all values) | — | — | — · 2026-11-10T16:23:04Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://simbad.cds.unistra.fr/simbad/sim-tap/sync: HTTP response 404 without a VOTable) |
| M 13 | Astrometry | section astrometry (all values) | — | — | — · 2026-11-10T16:23:04Z | — | not measured (AstroTwo side: SERVICE_ERROR: https://gea.esac.esa.int/tap-server/tap/sync: HTTP response 503 without a VOTable) |
| M 13 | Photometry | 2MASS J magnitude (VizieR II/246/out) | 10.647 mag | — | — · 2026-11-10T16:23:04Z | — | not measured (no 2MASS designation in SIMBAD) |
| M 13 | Photometry | 2MASS J flux_nu (recomputed) | 0.08783918893556711 Jy | 0.08783918893556711 Jy | — · 2026-11-10T16:23:04Z | relative 0 | pass |
| M 13 | Photometry | 2MASS H magnitude (VizieR II/246/out) | 10.452 mag | — | — · 2026-11-10T16:23:04Z | — | not measured (no 2MASS designation in SIMBAD) |
| M 13 | Photometry | 2MASS H flux_nu (recomputed) | 0.06753049865722717 Jy | 0.06753049865722717 Jy | — · 2026-11-10T16:23:04Z | relative 0 | pass |
| M 13 | Photometry | 2MASS Ks magnitude (VizieR II/246/out) | 10.08 mag | — | — · 2026-11-10T16:23:04Z | — | not measured (no 2MASS designation in SIMBAD) |
| M 13 | Photometry | 2MASS Ks flux_nu (recomputed) | 0.06193418900661836 Jy | 0.06193418900661836 Jy | — · 2026-11-10T16:23:04Z | relative 0 | pass |
| M 13 | Photometry | section photometry (vizier_sed) | — | — | — · 2026-11-10T16:23:04Z | — | not measured (AstroTwo side: PROFILE_VIZIER_SKIPPED: VizieR SED series not requested: the CDS is already unreachable (mocserver); no copy in the cache.) |

## 6. Files for reproduction

- **Script:** [`scripts/validate_profiles.py`](../scripts/validate_profiles.py). Run it from the repository with `uv run python scripts/validate_profiles.py` (all seven objects) or with object names as arguments. It uses the network, so it is **not** part of the automatic test suite. It writes into `docs/validation-runs/<date>/`.
- **Second run of 2026-11-10:** [`docs/validation-runs/2026-11-10-run2/`](validation-runs/2026-11-10-run2/), same files as below (rows of section 5.2), plus `results-recompared.json` and `results-recompared.md`: the same rows recompared without network with the empty-text rule of D25-24 (`--recompare`, section 5.1).
- **First run of 2026-11-10:** [`docs/validation-runs/2026-11-10/`](validation-runs/2026-11-10/)
  - `<object>-result.json`: the result of the `object.profile` command, with values, provenance, warnings and errors (thumbnail images removed);
  - `<object>-profile.ecsv`: the ECSV export of the same profile (values with provenance);
  - `results.json`, `results.md`: every row of section 5.4, with the exact reference query and the error text of the services that did not answer.
- **Reference queries:** written in `results.json` for each row. They go to SIMBAD (`basic`, `ident`), the Gaia archive (`gaiadr3.gaia_source`, `external.gaiaedr3_distance`), VizieR (`II/246/out`, `II/328/allwise`) and the NASA Exoplanet Archive (`pscomppars`).

## 7. Known limits and findings

- **Spectral type empty in SIMBAD: 2 fails as measured, resolved by decision D25-24 (second run).** For 3C 273 and M 13 SIMBAD has no spectral type: the reference reads an empty text (`''`), while AstroTwo wrote the value as absent (`null`) in its result. With the text tolerance «identical» these 2 rows were **fail**. **Decided on 2026-11-10 (D25-24, `mdfiles/25-analisi-profilo-oggetto.md`):** an empty text from a source is a value declared absent, never a value; AstroTwo does not write it and adds the note «SIMBAD has no spectral type»; the validation compares empty text and missing value as the same outcome. The tolerances are not changed. Recomputed without network from the saved files: both rows pass (section 5.1, «Correction»).
- **Gaia archive unstable during the second run.** It answered a check by hand, then timed out or answered HTTP 503 whenever AstroTwo asked it, so no Gaia value could be compared. To redo.
- **Services down on 2026-11-10.** Most rows of the first run are not measured (section 5.3). They are not failures of AstroTwo and not passes: they stay to be redone.
- **SIMBAD mirror not used for HTTP 404.** During the CDS outage, the main SIMBAD server answered HTTP 404 with an HTML page instead of not answering. AstroTwo switches to the Harvard mirror only for time-outs, connection errors, HTTP 5xx and 429, never for a 404 (rule D14-14), so the profiles had no SIMBAD data. The name resolver did switch to the mirror. Open question D14-16 (`mdfiles/14-core-protocolli-vo.md`). **Decided and fixed on 2026-11-10 (after this run):** an HTTP 404 from a service address now counts as a failure, and AstroTwo switches to the mirror with the usual notice; an object not found in a valid answer stays «not found».
- **Planets wrongly reported as absent.** With SIMBAD unavailable and no Gaia DR3 identifier, the Planets section says «no planet in the archive» **without querying the archive**. This happened for 51 Peg, TRAPPIST-1 and Barnard's Star, which have known planets. It is a defect of the statement, not of a value. Open question D25-23 (`mdfiles/25-analisi-profilo-oggetto.md`). Until it is decided, a Planets section without requests must not be read as «no planets». **Decided and fixed on 2026-11-10 (after this run):** an absence is shown only after a real, successful request to the right source; with SIMBAD down the planet archive is asked with the written name or the known Gaia DR3 identifier, otherwise the Planets section says «Not checked» with the reason. The result files of this run are kept as recorded: their «no planet» lines are the defect described here.
- **M 13 photometry by position.** Without SIMBAD, AstroTwo resolved M 13 to a position and took the 2MASS point source nearest to it, as declared in the profile (cross-match by position). For a globular cluster this is one star near the centre, not the cluster. The profile says how the match was made, but the photometry of an extended object should be read with care.
- **3C 273 distance.** It could not be checked because the Gaia archive did not answer. To redo.
