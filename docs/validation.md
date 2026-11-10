# Validation of AstroTwo

> **Status: structure only.** This page describes how AstroTwo's results will be checked. **No measurements have been made yet.** They are planned for the next phase of work (D2), before version 1.0. Every table below is empty on purpose.

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
2. **AstroTwo side.** The object profile (or the catalogue query) is run in a recorded session. The ECSV export, with values, units, source and query, is kept with the session file so the run can be replayed.
3. **Reference side.** The same values are read directly from the reference source, by its web interface, TAP/ADQL or TOPCAT, and the query is written down.
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
| Distance as 1/parallax (only when declared, parallax/error ≥ 5) | computed | **Relative difference ≤ 1 × 10⁻¹²** against `1000 / parallax[mas]` pc computed independently | One division in `float64`: the only possible difference is rounding, about 10⁻¹⁶. 10⁻¹² leaves room for a different but correct order of operations and still catches any real mistake (wrong unit, wrong column). |
| Planet parameters (orbital period, semi-major axis, eccentricity, radius, mass, equilibrium temperature) and their errors | read | **Identical** (difference 0), same unit | Copied from `pscomppars`. |
| Identifiers (SIMBAD main identifier, Gaia DR3, 2MASS, AllWISE designations, planet names) | read | **Identical text** | A different identifier means a different object. |
| SED flux from a magnitude | computed | **Relative difference ≤ 1 × 10⁻¹⁰** against `F0 × 10^(−0.4 m)` computed independently with the zero point that AstroTwo declares for that band | Two `float64` operations; the zero point itself is a declared choice, checked separately against its published source, not against this tolerance. |
| Angular separations (cross-match to 2MASS and AllWISE) | computed | **≤ 1 µas** (10⁻⁶ arcsec) against an independent Astropy computation from the same two positions | Separations are about 1 arcsec; `float64` rounding is far below 1 µas, and 1 µas is far below any catalogue error. |

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

*No measurements yet: to be filled in during D2.*

| Object | Area | Value | AstroTwo | Reference | Source and query | Difference | Outcome |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## 6. Files for reproduction

*To be filled in during D2:* session files, ECSV exports and the reference queries used for each measurement.

## 7. Known limits

*To be filled in during D2*, for example values that cannot be compared because a service was unavailable, and differences explained by catalogue updates.
