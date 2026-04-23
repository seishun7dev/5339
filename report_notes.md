# Report notes — Assignment 1

Running list of angles, findings, and ideas to pull into the final PDF report. Organised by rubric section. Expand later.

---

## Dataset Description — NGER (Clean Energy Regulator)

- **Source:** 10 annual JSON endpoints on the CER public data API, one per FY from 2014-15 to 2023-24 (dataset IDs `ID0075`–`ID0083` and `ID0243`).
- **Volume:** 5,942 facility-year rows total; per-year count grows steadily from 424 (2014-15) → 775 (2023-24).
- **Row types retained** (not filtered — preserved for integration):
  - `F` — facility-level (4,862 rows)
  - `C` — corporate roll-up (1,056 rows)
  - `FA` — facility aggregate, appears only in 2014-15 and 2016-17 (18 rows)
  - `-` and `""` — 6 sentinel rows (likely source errors)
- **Reporting-year provenance:** the year is not in the payload; we inject it at acquisition time from the filename, documented as provenance not transformation.

## Data Cleaning — NGER quirks worth writing up

### 1. Schema drift across 10 annual endpoints (strong engineering talking point)
The API returns JSON with four different column-naming conventions over the decade:
- **2014-15**: `scope1tCO2e` / `scope2tCO2e` (short form, no `total...Emissions` prefix).
- **2015-16**: entity column is `controllingcorporation`, every other year is `reportingEntity`.
- **2016-17**: typo columns with trailing `2` — `totalScope2EmissionstCO2e2`, `gridConnected2`.
- **2019-20 onward**: all-lowercase column names (`reportingentity`, `facilityname`, …).

Handled by lowercasing column names first, then applying a single rename map that covers every surviving variant. Cleaner than per-year logic and lets new naming shifts be added with one row.

### 2. Placeholder facility names
- `Corporate Total` (1,056 rows) — label the CER applies to every `row_type == 'C'` corporate roll-up. Not a real facility.
- `Facility` (17 rows) — two single-asset Victorian wind-farm entities (`CBWF HOLDINGS PTY LIMITED`, `AWF AUS HOLD OP CO PTY LTD`) with the facility name anonymised. The reporting-entity name still identifies the asset (CBWF ≈ Crowlands/Bulgana WF; AWF ≈ Ararat WF).
- Decision: preserve both — dropping or coercing would lose real rows. Flag them in the report.

### 3. Systematic missingness
- Corporate rows (`C`) have NaN `state` / `grid` / `grid_connected` / `primary_fuel` by construction — they're roll-ups.
- `emission_intensity_tco2e_per_mwh` is NaN in 1,112 rows — mostly when there's no production to divide by.
- `important_notes` is populated in only 37 of 5,942 rows.

### 4. Joint-venture double-counts
30 rows flagged `jv_double_counted` via keyword matching on `important_notes` (`joint venture`, `included the same data`, `reported multiple times`). CER explicitly warns these are duplicates of data reported by another entity. Flagged at clean time, deduplicated at integration time — keeps the cleaning stage transform-free.

## Dataset Description — CER (Large-scale renewables)

- **Source:** four CSVs scraped from the CER website across two landing pages (`…/large-scale-renewable-energy-data` and its `…/historical-…-supply-data` sub-page). Each CSV sits behind a `/document/<slug>` URL.
- **Scraping design (good web-scraping talking point):** we fetch each landing page's HTML, parse `<a href>` tags with BeautifulSoup, and search slug fragments for keyword rules (`must_contain` / `must_not_contain`). The historical page exposes both CSV and XLSX variants of the same file; we HEAD each candidate and keep the one that serves `text/csv` content-type. No fixed URL list — the matcher would still work if CER re-slugs their documents.
- **Four source types, kept distinct via `cer_source_type`:**

  | cer_source_type | rows | has postcode | `use_for_geocoding` |
  |---|---|---|---|
  | `historical_accredited` | 3,432 | ✓ | True |
  | `approved_2026`         | 57    | ✓ | False (post-NGER window, tiny embedded generators) |
  | `committed`             | 38    | ✗ | False (not yet operational, name may change) |
  | `probable`              | 62    | ✗ | False (speculative) |

- **Geocoding pool:** only the 3,432 historical rows have postcodes and a stable identity, so only those are flagged for geocoding.

## Data Cleaning — CER quirks worth writing up

### 1. Schema variance across four files
Same conceptual entity (a power station) has different column names per file:
- Station/project name: `Power station name` (historical, approved_2026) vs `Project Name` (committed, probable).
- Capacity: `Installed capacity` (no units) vs `Installed capacity (MW)` vs `MW Capacity`.
- Fuel: `Fuel source(s)` vs `Fuel Source(s)` vs `Fuel Source`.
- Trailing space in `State ` header on the committed and probable files.
Handled by `strip + lower` + a single rename map; same pattern used for NGER.

### 2. Mixed date formats
- `accreditation_start_date`, `approval_date` → DD/MM/YYYY (parsed with `dayfirst=True`).
- `committed_date` → `MMM-YYYY` (parsed with explicit `%b-%Y`).

### 3. Postcode dtype preservation
Australian postcodes include 4-digit codes with a leading zero (NT 08xx, ACT 02xx). We read all CSVs with `dtype=str` so leading zeros survive; CSV round-trips drop them back to numeric, but the final DuckDB load will declare postcode as VARCHAR.

### 4. Historical comments are domain-rich
Of 3,432 historical rows, 145 have non-null `comment` fields — many flag pre-1997 generation with a baseline. Worth keeping for the integration stage (LGC eligibility context).

## Dataset Description — ABS (Data by Region, Population & People)

- **Source:** ABS 2011-24 Data by Region methodology page, hosts 10 topic XLSX workbooks (Population, Economy, Income, Health, etc.). We originally prototyped against the Economy & Industry workbook (124 indicators) and narrowed to Population & People once it became clear the economy themes (business-counts, turnover bands, insolvencies, agriculture census, dwelling stock) were far too wide for the assignment's scope and produced a ~50%-sparse wide table.
- **Scraping design:** filenames are opaque (`14100DO0001_2011-24.xlsx`), so we scrape the page HTML, find the heading whose text contains both `population` and `people`, and pick the first XLSX link that follows it. Same pattern that handled the Economy file — only the keyword list changed. Robust against ABS renumbering file IDs in future releases.
- **Scope decision — Table 1 only:** the workbook has three sheets (`Contents`, `Table 1` ASGS regions, `Table 2` LGAs). We keep Table 1 only (26,181 cleaned rows covering AUS → State → GCCSA → SA4 → SA3 → SA2, 2,909 unique regions) and skip Table 2. LGAs are a parallel geography neither NGER nor CER use natively, so carrying it forward would force us to source an LGA-to-postcode concordance we don't need.
- **Scope decision — ERP banner only:** within Table 1, we keep only the 9 columns sitting under the *"Estimated resident population - year ended 30 June"* banner (row 5, cols 3-11): ERP total, population density, ERP by sex, median age M/F/persons, working-age count and %. The remaining 150 columns on the sheet are filed under unrelated banners (births & deaths, internal/overseas migration, ATSI, overseas-born, religion, citizenship, language, ADF service) and are dropped. Slicing by exact header match against a declared list in `pipeline/clean/abs.py` so the step fails loudly if ABS renames a column.
- **Coverage:** 9 reporting years (2011, 2016, 2018-2024), 2,909 regions across 6 ASGS levels, 9 demographic indicators per (region, year) row. 2011/2016/2018 are sparsely populated at most levels — ABS publishes only a subset of columns for those years and most cells are `-` sentinels → NaN after cleaning.
- **FY alignment win:** ERP is an "as at 30 June" figure, so ABS `year == 2024` = snapshot at 30 June 2024 = end of Australian FY 2023-24. This aligns 1:1 with the NGER reporting-FY convention (`FY 2023-24` ↔ `financial_year_end == 2024`) without any calendar-vs-FY reconciliation.

## Data Cleaning — ABS quirks worth writing up

### 1. Worksheet layout requires careful skipping
- Rows 0-4 are metadata (release title, publication date, table banner).
- Row 6 is the real header.
- Two rows at the bottom are footnotes (`"Note: Main Structure …"`, `"© Commonwealth of Australia 2025"`) that survive a naive `header=6` read. We drop them by filtering rows with a non-null `year` after coercion.

### 2. Narrow slice by exact header match
We slice the loaded DataFrame to 3 identifier columns + 9 ERP columns using a hard-coded exact-match list. Preferred over positional indexing because it fails loudly if ABS renames a column in a future vintage. After slicing, the same slugify pass (lowercase → non-alphanumerics to `_` → collapse runs) converts headers to snake_case.

### 3. Sentinel handling
ABS uses `"-"` for suppressed or unavailable values (e.g. counts <3 suppressed for privacy; demographic indicators not published for 2011/2016/2018 in this workbook). Replaced with NaN before numeric coercion.

### 4. Code column preserves mixed string/numeric region IDs
The `code` column contains both alphanumerics (`AUS`, `1GSYD`) and numeric-looking strings (`1`, `101`, `10102`, `101021007`). Excel returns the latter as floats (`1.0`, `101.0`), which would break `str.match`-based classification. We coerce to string defensively (handling both NaN and trailing `.0`).

### 5. Derived `geography_level` column
The ASGS code format encodes the level, so we classify each row at clean time rather than making every downstream query re-parse the code:

| Pattern | Level | Count |
|---|---|---|
| `AUS` | AUS | 1 |
| single digit (`1`, `2`, …, `9`) | STATE | 9 |
| digit + letters (`1GSYD`) | GCCSA | 16 |
| 3 digits | SA4 | 89 |
| 5 digits | SA3 | 340 |
| 9 digits | SA2 | 2,454 |

### 6. Sparsity is temporal, not random
Headline ERP is populated for 2019-2024 at every level, but 2011, 2016, and 2018 are sparse — ABS did not publish demographic breakdowns at all levels for those years. The 2024 vintage also has the sex-split and median-age columns NaN at STATE level (headline ERP is published earlier than the demographic breakdowns). We preserve NaNs rather than filling — the sparsity pattern is editorial.

## Database Design — ABS schema choice

Justified for the report:
- **Single narrow table, composite PK `(code, year)`.** Denormalised but only 9 metric columns, so sparsity is incidental rather than structural.
- **Why not long format?** Natural grain is `(region, year)`; every metric shares that grain. At 9 metrics × 26K rows long-format would only yield ~235K rows, not a blow-up — but it forces downstream queries to filter by `metric_key`, which is clumsy column indirection for so few metrics.
- **Sparsity trade-off:** the 2011/2016/2018 rows are mostly NaN but retaining them keeps the year axis dense and avoids surprises at join time. CSV size ~1.85 MB on disk (down from ~9 MB under the old Economy scope).
- **Integration point for NGER/CER:** `estimated_resident_population_no` at STATE level is the natural denominator for per-capita emissions (NGER `total_emissions_tco2e / ERP`) and per-capita renewable capacity (CER `installed_capacity_mw / ERP`). More interpretable than the old business-count pivot and supports the comparative state-level narrative the report pitches in Section 5.

## Data Exploration — visual ideas
- **Bar chart**: NGER facility count per reporting year (shows sector growth / broadening reporting).
- **Bar chart** or stacked: total emissions by primary fuel over time.
- **Map**: facility locations coloured by fuel type, once geocoded (Section 4).
- **Scatter / bar**: NGER per-capita emissions per state (total emissions / ABS ERP) for 2023 — shows which states lean high-emission relative to population. Cleaner read than absolute emissions, which are dominated by NSW/VIC/QLD by sheer size.
- **Line chart**: CER `historical_accredited` capacity commissioned per year vs NGER facility count per year — policy/sector growth co-movement.

## Data Augmentation — Geocoding

### 1. API choice — Nominatim (OpenStreetMap)
- Free, no API key, public — satisfies the assignment's "public geocoding API" criterion and keeps the submission reproducible by markers without secrets.
- Considered Google Geocoding (faster, ~95% coverage on named facilities, free under the $200/month credit) but rejected to keep the project key-free.
- Nominatim usage policy strictly observed: custom `User-Agent: COMP5339-A1-geocoder/1.0 (rohansev11@gmail.com)`, ≤1 request/second (1.1 s sleep between live calls).

### 2. Two-tier query strategy
For every row flagged `use_for_geocoding == True` (3,432 — the CER `historical_accredited` set, the only CER subset with both a stable identity and a postcode):
1. **Precise:** `"<facility_name>, <postcode>, <state>, Australia"` with `countrycodes=au`. Hits when the facility itself is tagged in OSM (e.g. "Waubra Wind Farm", "Bogong Power Station").
2. **Postcode-centroid fallback** (only on tier-1 miss): `"<postcode>, Australia"`. Always resolves for a valid AU postcode — gives a suburb-level location for facilities OSM doesn't carry by name.

Each query (precise OR fallback) is cached separately under its literal query string. Fallback queries are deduplicated by postcode at the cache layer: 3,432 facilities → 1,143 unique postcodes, so a single fallback fetch services every facility sharing that postcode.

### 3. Cache design — `data/raw/geocode/nominatim_cache.json`
Single JSON file, key = full query string, value =
```
{"lat": float, "lon": float, "name": str, "state": str,
 "postcode": str, "area": str, "source": "facility"|"postcode"}
```
or `null` for a definitive miss.
- `area` = Nominatim `display_name`, kept so we can sanity-check matches by eye.
- `source` distinguishes precise vs centroid for the merge step.
- HTTP errors (DNS blips, timeouts) are *not* cached — they're retried on the next run.
- Cache rewritten to disk after every successful API call. The mandated 1.1 s inter-request sleep absorbs the disk I/O, so no async/threading is needed and Ctrl-C never loses progress.

### 4. Coverage results (preliminary, run in progress)
On the first ~1,500 facilities processed:
| Outcome | Count | Share |
|---|---|---|
| Precise (facility tagged in OSM) | 346 | ~23% |
| Fallback (postcode centroid) | 634 | ~42% |
| Miss (neither tier returned anything) | 1,153 | ~35% |

The combined ~65% coverage is consistent with the slice composition — NGER-rooted facilities (~282 of 3,432) lean precise; CER-only rows (~3,150 of 3,432, mostly rooftop solar) lean fallback or miss.

### 5. Why precise coverage is moderate
Median installed capacity in the CER-only majority is 0.34 MW — i.e. rooftop solar on warehouses, business premises, schools, treatment plants. These aren't businesses with addresses; they're panels on roofs. Neither Nominatim nor Google has them in any address database. Postcode-centroid is the best any public geocoder can do for that segment.

### 6. Postcode collisions limit map precision
3,432 facilities collapse onto 1,143 unique postcodes. Worst offender: postcode 3175 (Dandenong VIC) holds 36 facilities; under fallback they'd all stack on the same lat/lon. For a publication-quality map, aggregate by postcode (count or installed-capacity) and use marker size, rather than plotting raw points.

### 7. Operational quirks observed during the run
- **DNS resolution failures** in clusters (~55 in the first 30 min): macOS `mDNSResponder` blips, not Nominatim. Errors are skipped (not cached) so re-running the script naturally recovers them.
- **Throughput** ~21 calls/min in practice, vs the theoretical ceiling of 55/min from the 1.1 s sleep alone — Nominatim itself adds ~1.5 s of round-trip latency per request. Full cold run is ~3 hours, not 1.

### 8. Future improvements (mention in report)
- **Hybrid backend:** Google Geocoding for the ~282 NGER-rooted facilities (push precise coverage past 90% on the rows that matter), Nominatim postcode-centroid for the small-solar majority.
- **Third query tier:** CER `comment` field (free-text, ~145 of 3,432 rows populated) sometimes contains a town name absent from the facility name — could be parsed for an alternative query.
- **Cross-check fuzzy NGER↔CER matches with proximity:** lat/lon within ~5 km confirms a fuzzy match; >50 km apart rejects it. Would catch the known false-positive tail (e.g. `Bomen Solar Farm` ↔ `Wellington North Solar Farm` @ 85.7).

## Database Design

### Three-table star-schema-lite
Grain-driven split, same pattern used across all three sources:

- **`facility`** (4,219 rows) — one row per unique physical facility. Star-schema dimension + all CER attributes preserved.
- **`generation`** (4,850 rows) — one row per facility-year (NGER F/FA only). Star-schema fact; FK to `facility`.
- **`abs_population`** (26,181 rows) — one row per region-year (ABS narrow). Separate fact keyed by `(code, year)` and joinable to the other two via `state` at STATE-level filter.

**Shared join key:** `state` as 2-letter abbrev (`NSW`, `VIC`, …, `OT`) on all three tables. For `abs_population`, derived from the leading digit of the ASGS code. Skipped a separate `dim_state` lookup — 2-letter abbrev directly embedded is simpler and still gives consistent cross-source joins.

**Why not a single monolithic table?** The three sources have fundamentally different grains (facility vs facility-year vs region-year). Forcing a single shape would force nonsensical Cartesian joins or massive NULL inflation. The 3-table split respects each source's grain while sharing keys for integration.

### NGER ↔ CER matching (entity resolution)

Three-key conjunction: **normalised name** AND **state** AND **fuel category**. The fuel check is what prevents a Wind facility from matching a Solar facility of the same name/state.

**Name normalisation** (for matching only; display names preserved):
- lowercase; strip punctuation `. , ' " ( ) / \\ & - –`
- strip trailing descriptors in order of decreasing length: `"solar power station"`, `"hydro power station"`, `"wind power station"`, `"power station"`, `"power plant"`, `"solar farm"`, `"wind farm"`, `"solar pv"`, `"solar park"`, `"pv"`
- collapse whitespace

**Fuel category mapping** (NGER → CER):
- Direct equality: `Wind`, `Solar`, `Hydro`.
- NGER `Landfill Gas` and `Waste Coal Mine Gas` → CER `Biomass`.
- NGER fossil fuels (`Coal`, `Gas`, `Diesel`, `Battery`, `Liquid Fuel`, …) have no CER counterpart — fall through to `nger_only`.

**Match algorithm** (applied per NGER facility):
1. Exact normalised-name match in the (state, fuel) pool → `exact`, score 100.
2. Fuzzy `rapidfuzz.fuzz.token_set_ratio ≥ 85` in the same pool → `fuzzy`, score recorded.
3. Otherwise → `nger_only`.

Greedy: once a CER row is claimed, later NGER facilities cannot claim it. Unclaimed CER rows at the end become `cer_only`.

**Match outcomes:**

| status | rows | notes |
|---|---|---|
| `exact` | 151 | normalised name identical |
| `fuzzy` | 131 | token_set_ratio ≥ 85; some false positives at the low end (85-88) to review |
| `nger_only` | 630 | mostly fossil-fuel facilities (coal, gas, diesel) with no CER counterpart, plus a minority of renewables that didn't fuzzy-match |
| `cer_only` | 3,307 | sub-NGER-threshold embedded generators (mostly rooftop Solar in `historical_accredited`) |

**Known matching weaknesses** (worth flagging in report):
- `token_set_ratio` biases toward shared tokens — names like "X Solar Farm Pty Ltd" and "Y Solar Farm Pty Ltd" can collide on the generic tokens. Example false positive: `Bomen Solar Farm Pty Ltd` ↔ `Wellington North Solar Farm Pty Ltd` @ 85.71. Mitigation: `match_score` column exposes these for review.
- Greedy first-match doesn't globally optimise. If NGER A matches CER X at 89 but NGER B would score 95 on the same X, A wins. In practice with same-state+same-fuel pools this is rare.
- These are expected to be resolved in Task 4 (Data Augmentation) when geocoding gives us a second corroborating signal (proximity within ~5 km can confirm a fuzzy match; >50 km apart can reject it).

### Row-drop rules at integration

Documented in the report:
- NGER `row_type = 'C'` (1,056 corporate roll-ups) — excluded from `generation`. Reconstructable as `SUM(generation) GROUP BY reporting_entity`.
- NGER `jv_double_counted = True` (30 rows) — excluded; would inflate state totals.
- NGER sentinel `row_type` (`-`, blank, 6 rows) — excluded.
- All 9 ABS metric columns preserved. Any `-` suppressed values already resolved to NULL at clean stage.

### Year reconciliation
NGER `reporting_year` stored as string (`"2014-15"`, …, `"2023-24"`) plus a derived integer `financial_year_end` (2015, …, 2024). ABS `year` for Population & People is the "as at 30 June" snapshot year — `year == 2024` is the 30 June 2024 ERP, which coincides exactly with the end of NGER FY 2023-24. Join convention: `financial_year_end == abs_year` directly. No calendar/FY offset needed, unlike the Economy workbook which mixed calendar-year and FY metrics.



## Challenges & lessons
- NGER data portal (`data.cer.gov.au`) is a Blazor WebAssembly SPA — CSV download links are unreachable via static HTML parsing. For NGER we use the backing JSON API instead; the column-drift problem is then solved in cleaning.
- NGER API quirk: query string `?select=*` must have its `=` percent-encoded (`?select%3D*`) or the server returns HTTP 500.
- CER content site (`cer.gov.au/markets/…`) is plain server-rendered HTML, so BeautifulSoup works there. Each dataset sits behind a `/document/<slug>` URL, making keyword-search on slug fragments a robust discovery method.
- Same cleaning pattern (lowercase → single rename map) works well across completely different data shapes (NGER 10-year JSON and CER 4-file CSV).
