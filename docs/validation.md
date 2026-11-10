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
   - Values AstroTwo computes, such as unit conversions, fluxes from magnitudes, separations and propagated positions, are compared with an independent computation within a stated tolerance. The tolerances are to be defined in D2 and written in this page before the measurements.
5. **Record.** Each row of the results tables reports:
   - the date and the AstroTwo version;
   - the data release, for example Gaia DR3;
   - the source and the exact query;
   - the AstroTwo value, the reference value and the difference;
   - the outcome: pass, fail, or explained difference.
6. **Reproducibility.** The session files and exports used for each measurement are listed in section 6, so anyone can rerun them.

## 3. Reference objects

| Object | Why it is included |
|---|---|
| **51 Peg** | Bright solar-type star with a planet; full chain SIMBAD → Gaia DR3 → 2MASS/AllWISE → NASA Exoplanet Archive |
| **Vega** | Photometric standard; very bright, so it tests saturated or missing survey photometry and the SED |
| **eta Tau** (Alcyone) | Bright member of a crowded cluster field (Pleiades): identification and cross-match among close neighbours |
| **TRAPPIST-1** | Faint, very red, high proper motion star with seven planets: epoch handling and infrared SED |
| *Barnard's Star* (proposed) | Highest known proper motion: tests propagation between epochs (J2000.0, J2016.0) and the 2MASS epoch |
| *3C 273* (proposed) | Extragalactic object (quasar): no meaningful parallax, so the distance must be declared as unavailable rather than invented |
| *M 13* (proposed) | Dense globular-cluster field: cone search and cross-match row counts against TOPCAT |

The three proposed objects are to be confirmed by the project owner.

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
