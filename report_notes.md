# Report notes — Assignment 1

Short notes per pipeline step. Pull into the final PDF report.

## 1. Acquisition

- **NGER** — 10 annual JSON endpoints (FY2014-15 → FY2023-24, IDs `ID0075`–`ID0083`, `ID0243`). 5,942 rows total. Reporting year injected at acquisition (not in payload).
- **CER** — 4 CSVs scraped from 2 landing pages. Slugs discovered by keyword rules on `<a href>`, robust to URL changes. HEAD check picks CSV variant over XLSX on the historical page.
- **ABS** — 1 XLSX (Population & People) from Data by Region methodology page. Found by scanning headings for "population"+"people". Switched away from Economy & Industry workbook (too wide, ~50% sparse).

## 2. Cleaning

- **NGER schema drift** — 4 naming conventions across 10 years (camelCase vs lowercase, `controllingcorporation` 2015-16, trailing-`2` typos 2016-17). Solved with lowercase + single rename map.
- **NGER row types preserved** — `F` (4,862), `C` (1,056 corporate roll-ups), `FA` (18), 6 sentinel rows. Filtered at integration, not cleaning.
- **NGER JV double-counts** — 30 rows flagged via keyword match on `important_notes`; dropped at integration.
- **CER schema variance** — 4 files use different column names for the same concept (`Power station name` vs `Project Name`, `Installed capacity` vs `MW Capacity`). Same lowercase + rename-map pattern.
- **CER postcode dtype** — read with `dtype=str` so leading zeros survive (NT `08xx`, ACT `02xx`); declared `VARCHAR(4)` in DuckDB.
- **ABS scope** — Table 1 only (ASGS regions); Table 2 (LGAs) skipped because neither NGER nor CER use LGA natively. Within Table 1, narrow slice to 9 ERP-banner columns.
- **ABS sentinels** — `-` → NaN before numeric coercion.
- **ABS derived `geography_level`** — classified from ASGS code pattern (`AUS`, single digit → STATE, `1GSYD` → GCCSA, 3/5/9 digits → SA4/SA3/SA2). Avoids re-parsing in every downstream query.

## 3. Integration

- **3 curated tables, grain-driven split:** `facility` (4,219), `generation` (4,850 facility-years), `abs_population` (26,181 region-years).
- **Shared join key** — 2-letter `state` on all three (derived from ASGS leading digit on ABS).
- **NGER ↔ CER matching** — three-key conjunction: normalised name AND state AND fuel category. Algorithm: exact match → `rapidfuzz.token_set_ratio ≥ 85` → `nger_only`. Greedy first-match.
- **Fuel mapping** — NGER `Landfill Gas` / `Waste Coal Mine Gas` → CER `Biomass`. NGER fossil fuels have no CER counterpart.
- **Match outcomes** — exact 151, fuzzy 131, nger_only 630, cer_only 3,307.
- **Known matching weakness** — `token_set_ratio` can collide on generic tokens (e.g. `Bomen Solar Farm` ↔ `Wellington North Solar Farm` @ 85.7). `match_score` exposed for review; geocoding gives proximity as a corroborating signal in Section 4.
- **Year reconciliation** — NGER `financial_year_end` (int) aligns 1:1 with ABS `year` (30 June snapshot). FY 2023-24 ↔ ABS year 2024.
- **Composite PK on `generation`** — `(facility_id, FY)` not unique: 20 legit duplicates from JV / mid-year ownership splits (e.g. Bayswater 2015 across AGL + MacGen). Added `reporting_entity` to PK.

## 4. Augmentation — Geocoding

- **API** — Nominatim (OSM). Free, no key, key-free reproducibility. Custom User-Agent, 1.1 s sleep.
- **Two-tier query** — precise `"<name>, <postcode>, <state>, Australia"`, then postcode-centroid fallback.
- **Cache** — JSON, key = literal query string, value carries lat/lon/source or `null` for definitive miss. HTTP errors not cached so they retry. Survives Ctrl-C.
- **Coverage (3,432 facilities)** — 859 precise (25%), 2,573 postcode-fallback (75%), 0 misses. Precise hits skew to large named NGER assets; fallback covers the small-rooftop CER majority (median 0.34 MW).
- **Postcode collisions** — 3,432 facilities → 1,143 unique postcodes. For maps, aggregate by postcode rather than plotting raw points.
- **Operational quirk** — macOS DNS clusters in cold runs (skipped, not cached). Real throughput ~21 calls/min, cold run ~3 h.

## 5. Storage — DuckDB warehouse

- Single file `data/curated/warehouse.duckdb`. Built from curated CSVs by `pipeline/load/duckdb_load.py`. Idempotent.
- **Spatial extension** — `facility.geom` populated as `ST_Point(lon, lat)` for the 3,432 geocoded rows. Ready for Assignment 2 spatial joins against ASGS polygons.
- **PK enforcement** — DuckDB CTAS doesn't enforce PK constraints, so `UNIQUE INDEX` added post-hoc. Helper indexes on `generation(facility_id)`, `generation(financial_year_end)`, `abs_population(geography_level)`, `abs_population(state)`.
- **Type coercions at load** — `postcode VARCHAR(4)` via `lpad`, `accreditation_start_date`/`approval_date` → `DATE`, booleans typed.

## 6. Exploration — visual ideas

- Bar: NGER facility count per FY (sector growth).
- Stacked bar: total emissions by primary fuel over time.
- Map: facility locations coloured by fuel type (postcode-aggregated).
- Bar: per-capita emissions by state for FY23 (NGER total / ABS ERP).
- Line: CER `historical_accredited` capacity per commissioning year vs NGER facility count per FY.

## Caveats to flag

- 787 facilities without `geom` — by construction (NGER-only with no postcode + CER `committed`/`probable`/`approved_2026`). Not a defect.
- Postcode-centroid collisions persist in `geom`. Fine for SA2 spatial joins; aggregate before mapping.
- 2011/2016/2018 ABS rows are sparse — ABS only published a subset of demographic columns those years.

## Challenges & lessons

- NGER data portal is a Blazor SPA — used the backing JSON API instead of HTML scraping.
- NGER API quirk: `?select=*` must be percent-encoded (`?select%3D*`) or returns HTTP 500.
- Same cleaning pattern (lowercase → single rename map) worked across all three sources despite different shapes.
- Composite PK on `generation` was a late catch — initial `(facility_id, FY)` would have rejected 20 legitimate JV rows.
