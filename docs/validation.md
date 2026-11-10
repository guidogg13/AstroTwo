# Validation of AstroTwo

> **Status: first measurements, incomplete.** The tolerances (section 2.1) were fixed and committed on 2026-11-10 before any measurement. The first measurements were made the same day (section 5): on that day the CDS (SIMBAD, VizieR), the Gaia archive and the NASA Exoplanet Archive were down or not answering, so most rows are **not measured** and stay to be redone before version 1.0.

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

### 5.1 Run of 2026-11-10 (16:12–16:23 UTC)

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

### 5.2 All rows of the run of 2026-11-10

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
- **Run of 2026-11-10:** [`docs/validation-runs/2026-11-10/`](validation-runs/2026-11-10/)
  - `<object>-result.json`: the result of the `object.profile` command, with values, provenance, warnings and errors (thumbnail images removed);
  - `<object>-profile.ecsv`: the ECSV export of the same profile (values with provenance);
  - `results.json`, `results.md`: every row of section 5.2, with the exact reference query and the error text of the services that did not answer.
- **Reference queries:** written in `results.json` for each row. They go to SIMBAD (`basic`, `ident`), the Gaia archive (`gaiadr3.gaia_source`, `external.gaiaedr3_distance`), VizieR (`II/246/out`, `II/328/allwise`) and the NASA Exoplanet Archive (`pscomppars`).

## 7. Known limits and findings

- **Services down on 2026-11-10.** Most rows are not measured (section 5.1). They are not failures of AstroTwo and not passes: they stay to be redone.
- **SIMBAD mirror not used for HTTP 404.** During the CDS outage, the main SIMBAD server answered HTTP 404 with an HTML page instead of not answering. AstroTwo switches to the Harvard mirror only for time-outs, connection errors, HTTP 5xx and 429, never for a 404 (rule D14-14), so the profiles had no SIMBAD data. The name resolver did switch to the mirror. Open question D14-16 (`mdfiles/14-core-protocolli-vo.md`). **Decided and fixed on 2026-11-10 (after this run):** an HTTP 404 from a service address now counts as a failure, and AstroTwo switches to the mirror with the usual notice; an object not found in a valid answer stays «not found».
- **Planets wrongly reported as absent.** With SIMBAD unavailable and no Gaia DR3 identifier, the Planets section says «no planet in the archive» **without querying the archive**. This happened for 51 Peg, TRAPPIST-1 and Barnard's Star, which have known planets. It is a defect of the statement, not of a value. Open question D25-23 (`mdfiles/25-analisi-profilo-oggetto.md`). Until it is decided, a Planets section without requests must not be read as «no planets». **Decided and fixed on 2026-11-10 (after this run):** an absence is shown only after a real, successful request to the right source; with SIMBAD down the planet archive is asked with the written name or the known Gaia DR3 identifier, otherwise the Planets section says «Not checked» with the reason. The result files of this run are kept as recorded: their «no planet» lines are the defect described here.
- **M 13 photometry by position.** Without SIMBAD, AstroTwo resolved M 13 to a position and took the 2MASS point source nearest to it, as declared in the profile (cross-match by position). For a globular cluster this is one star near the centre, not the cluster. The profile says how the match was made, but the photometry of an extended object should be read with care.
- **3C 273 distance.** It could not be checked because the Gaia archive did not answer. To redo.
