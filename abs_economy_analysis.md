# ABS Economy & Industry Dataset — Structure & Schema Design

- Not used in this report, but included in the assignment as a potential data source for future analysis.

## File Overview

| Property | Value |
|---|---|
| **File** | `ECONOMY AND INDUSTRY.xlsx` (14.9 MB) |
| **Source** | ABS Data by Region, 2011-24 (released 27 May 2025) |
| **Sheets** | 3: `Contents`, `Table 1`, `Table 2` |

---

## Sheet Structure

### Table 1 — ASGS Regions (SA2/SA3/SA4, States, GCCSAs)
- **Shape:** 29,097 rows × 127 columns
- **Header row:** Row 6 (0-indexed), rows 0–5 are metadata
- **Regions:** 2,912 unique codes across a geographic hierarchy
- **Years:** 2011, 2016–2024 (10 years; each region has up to 10 rows)

### Table 2 — Local Government Areas (LGAs)
- **Shape:** 5,477 rows × 115 columns
- **Same header structure** as Table 1
- **Regions:** 550 unique LGA codes (e.g., `10050` → Albury)
- **Years:** Same as Table 1
- **Missing columns:** The 12 dwelling stock columns (Houses/Townhouses/Apartments additions/removals/total) are only in Table 1

---

## Region Hierarchy (Table 1)

| Level | Code Format | Count | Examples |
|---|---|---|---|
| **National** | `AUS` | 1 | `AUS` → Australia |
| **State/Territory** | 1 digit (`1`–`9`) | 9 | `1` → NSW, `2` → VIC |
| **GCCSA** | digit + letters | 16 | `1GSYD` → Greater Sydney, `2GMEL` → Greater Melbourne |
| **SA4** | 3 digits | 89 | `101` → Capital Region, `102` → Central Coast |
| **SA3** | 5 digits | 340 | `10102` → Queanbeyan, `10103` → Snowy Mountains |
| **SA2** | 9 digits | 2,454 | `101021007` → Braidwood, `101021008` → Karabar |

> [!TIP]
> The hierarchy is encoded in the code itself: SA2 `101021007` is in SA3 `10102`, which is in SA4 `101`, which is in State `1` (NSW). This makes parent lookups trivial.

---

## All 127 Columns — Grouped by Theme

### 🔑 Identifier Columns (3)
| # | Column | Description |
|---|---|---|
| 0 | `Code` | ASGS region code (see hierarchy above) |
| 1 | `Label` | Region name (e.g. "Greater Sydney") |
| 2 | `Year` | Reference year (2011, 2016–2024) |

---

### 📊 Business Counts — at 30 June (cols 3–7)
Counts of actively trading businesses by employment size.

| # | Column | Fill Rate |
|---|---|---|
| 3 | Number of non-employing businesses | 49% |
| 4 | Number of employing businesses: 1-4 employees | 49% |
| 5 | Number of employing businesses: 5-19 employees | 49% |
| 6 | Number of employing businesses: 20 or more employees | 47% |
| 7 | **Total number of businesses** | 49% |

---

### 📈 Business Entries — year ended 30 June (cols 8–12)
New businesses registered during the year.

| # | Column | Fill Rate |
|---|---|---|
| 8 | Number of non-employing business entries | 39% |
| 9–11 | Employing business entries by size (1-4, 5-19, 20+) | 6–39% |
| 12 | **Total number of business entries** | 39% |

---

### 📉 Business Exits — year ended 30 June (cols 13–17)
Businesses that ceased during the year.

| # | Column | Fill Rate |
|---|---|---|
| 13 | Number of non-employing business exits | 39% |
| 14–16 | Employing business exits by size (1-4, 5-19, 20+) | 6–39% |
| 17 | **Total number of business exits** | 39% |

---

### 🏭 Business Counts by Industry (cols 18–37)
Number of businesses per ANZSIC industry division. **20 industry categories:**

| # | Column | Fill Rate |
|---|---|---|
| 18 | Agriculture, forestry and fishing (no.) | ~49% |
| 19 | Mining (no.) | ~49% |
| 20 | Manufacturing (no.) | ~49% |
| **21** | **Electricity, gas, water and waste services (no.)** ⚡ | ~49% |
| 22 | Construction (no.) | ~49% |
| 23 | Wholesale trade (no.) | ~49% |
| 24 | Retail trade (no.) | ~49% |
| 25 | Accommodation and food services (no.) | ~49% |
| 26 | Transport, postal and warehousing (no.) | ~49% |
| 27 | Information media and telecommunications (no.) | ~49% |
| 28 | Financial and insurance services (no.) | ~49% |
| 29 | Rental, hiring and real estate services (no.) | ~49% |
| 30 | Professional, scientific and technical services (no.) | ~49% |
| 31 | Administrative and support services (no.) | ~49% |
| 32 | Public administration and safety (no.) | ~49% |
| 33 | Education and training (no.) | ~49% |
| 34 | Health care and social assistance (no.) | ~49% |
| 35 | Arts and recreation services (no.) | ~49% |
| 36 | Other services (no.) | ~49% |
| 37 | Currently unknown (no.) | ~49% |

---

### 💰 Business Counts by Turnover (cols 38–55)
Counts, entries, and exits broken down by annual turnover bands.

| # | Columns | Bands |
|---|---|---|
| 38–43 | Businesses by turnover | 6 bands: <$50k … $10m+ |
| 44–49 | Business entries by turnover | Same 6 bands (sparse: 6–39%) |
| 50–55 | Business exits by turnover | Same 6 bands (sparse: 7–39%) |

---

### 🏗️ Building Approvals (cols 56–65)
Dwelling approvals and building values.

| # | Column | Fill Rate |
|---|---|---|
| 56 | Private sector houses (no.) | 55% |
| 57 | Private sector dwellings excluding houses (no.) | 37% |
| 58 | Total private sector dwelling units (no.) | 56% |
| 59 | Total dwelling units (no.) | 56% |
| 60 | Value of private sector houses ($m) | 55% |
| 61 | Value of private sector dwellings excl. houses ($m) | 35% |
| 62 | Total value of private sector dwelling units ($m) | 56% |
| 63 | Value of residential building ($m) | 57% |
| 64 | Value of non-residential building ($m) | 51% |
| 65 | Value of total building ($m) | 57% |

---

### 🏠 Property Transfers (cols 66–69)

| # | Column | Fill Rate |
|---|---|---|
| 66 | Number of established house transfers (no.) | 56% |
| 67 | Median price of established house transfers ($) | 56% |
| 68 | Number of attached dwelling transfers (no.) | 47% |
| 69 | Median price of attached dwelling transfers ($) | 47% |

---

### ⚖️ Personal Insolvencies (cols 70–81)
Insolvency debtors by business-relatedness and occupation (very sparse).

| # | Column | Fill Rate |
|---|---|---|
| 70–72 | Business/non-business/total insolvencies | ~9% |
| 73–81 | Debtors by occupation (Managers…Labourers, Other) | ~8% |

---

### 🌾 Agriculture (cols 82–93)
Census-year agriculture data (2011, 2016, 2021 only → very sparse).

| # | Column | Fill Rate |
|---|---|---|
| 82 | Area of holding (ha) | 5% |
| 83–87 | Livestock counts (dairy cattle, meat cattle, sheep, pigs, chickens) | 1–4% |
| 88–90 | Crop areas (broadacre, vegetables, orchards) | 2–3% |
| 91–93 | Gross value of production (total, crops, livestock) | 4% |

---

### 👷 Employment by Industry — Census % (cols 94–114)
Percentage of employed persons by ANZSIC industry. Census years only (2011, 2016, 2021).

| # | Column | Fill Rate |
|---|---|---|
| 94–113 | 20 industry divisions (%) | ~28% |
| 114 | **Total persons employed aged 15+ (no.)** | 29% |

---

### 🏘️ Estimated Dwelling Stock (cols 115–126) — *Table 1 only*
Annual dwelling stock estimates with additions and removals.

| # | Column | Fill Rate |
|---|---|---|
| 115–117 | Houses: additions, removals, total | 47–59% |
| 118–120 | Townhouses: additions, removals, total | 6–57% |
| 121–123 | Apartments: additions, removals, total | 3–54% |
| 124–126 | Total: additions, removals, total dwellings | 47–59% |

---

## Schema Recommendation

Given the data is wide (127 cols) but not enormously deep (~29K rows for Table 1, ~5.5K for Table 2), a **single wide table** is perfectly fine. No normalisation needed — this is essentially a fact table keyed by `(region_code, year)`.

> [!NOTE]
> **Why a single table works here:**
> - 29K + 5.5K = ~35K rows total — trivially small for DuckDB
> - All 124 data columns share the same grain: one value per (region, year)
> - No repeating groups or multi-valued attributes
> - Queries like "total businesses in NSW in 2023" are simple column lookups

### Proposed DuckDB Table

```sql
CREATE TABLE abs_economy (
    -- Identifiers
    region_code         VARCHAR NOT NULL,     -- ASGS code or LGA code
    region_name         VARCHAR NOT NULL,     -- Human-readable label
    year                INTEGER NOT NULL,     -- 2011, 2016-2024
    geography_level     VARCHAR NOT NULL,     -- 'AUS','STATE','GCCSA','SA4','SA3','SA2','LGA'
    source_table        VARCHAR NOT NULL,     -- 'Table 1' or 'Table 2'

    -- Business Counts (at 30 June)
    biz_non_employing           INTEGER,
    biz_employing_1_4           INTEGER,
    biz_employing_5_19          INTEGER,
    biz_employing_20_plus       INTEGER,
    biz_total                   INTEGER,

    -- Business Entries
    biz_entries_non_employing   INTEGER,
    biz_entries_1_4             INTEGER,
    biz_entries_5_19            INTEGER,
    biz_entries_20_plus         INTEGER,
    biz_entries_total           INTEGER,

    -- Business Exits
    biz_exits_non_employing     INTEGER,
    biz_exits_1_4               INTEGER,
    biz_exits_5_19              INTEGER,
    biz_exits_20_plus           INTEGER,
    biz_exits_total             INTEGER,

    -- Business Counts by Industry (ANZSIC)
    biz_agriculture             INTEGER,
    biz_mining                  INTEGER,
    biz_manufacturing           INTEGER,
    biz_electricity_gas_water   INTEGER,      -- ⚡ key for your assignment
    biz_construction            INTEGER,
    biz_wholesale_trade         INTEGER,
    biz_retail_trade            INTEGER,
    biz_accommodation_food      INTEGER,
    biz_transport_postal        INTEGER,
    biz_info_media_telecomms    INTEGER,
    biz_financial_insurance     INTEGER,
    biz_rental_real_estate      INTEGER,
    biz_professional_scientific INTEGER,
    biz_admin_support           INTEGER,
    biz_public_admin_safety     INTEGER,
    biz_education_training      INTEGER,
    biz_health_social           INTEGER,
    biz_arts_recreation         INTEGER,
    biz_other_services          INTEGER,
    biz_unknown                 INTEGER,

    -- Business Counts by Turnover
    biz_turnover_0_50k          INTEGER,
    biz_turnover_50k_200k       INTEGER,
    biz_turnover_200k_2m        INTEGER,
    biz_turnover_2m_5m          INTEGER,
    biz_turnover_5m_10m         INTEGER,
    biz_turnover_10m_plus       INTEGER,

    -- Business Entries by Turnover
    biz_entries_turnover_0_50k      INTEGER,
    biz_entries_turnover_50k_200k   INTEGER,
    biz_entries_turnover_200k_2m    INTEGER,
    biz_entries_turnover_2m_5m      INTEGER,
    biz_entries_turnover_5m_10m     INTEGER,
    biz_entries_turnover_10m_plus   INTEGER,

    -- Business Exits by Turnover
    biz_exits_turnover_0_50k        INTEGER,
    biz_exits_turnover_50k_200k     INTEGER,
    biz_exits_turnover_200k_2m      INTEGER,
    biz_exits_turnover_2m_5m        INTEGER,
    biz_exits_turnover_5m_10m       INTEGER,
    biz_exits_turnover_10m_plus     INTEGER,

    -- Building Approvals
    building_private_houses         INTEGER,
    building_private_other          INTEGER,
    building_private_total          INTEGER,
    building_total_units            INTEGER,
    building_value_private_houses   DOUBLE,   -- $m
    building_value_private_other    DOUBLE,
    building_value_private_total    DOUBLE,
    building_value_residential      DOUBLE,
    building_value_non_residential  DOUBLE,
    building_value_total            DOUBLE,

    -- Property Transfers
    house_transfers_count           INTEGER,
    house_transfers_median_price    DOUBLE,   -- $
    attached_transfers_count        INTEGER,
    attached_transfers_median_price DOUBLE,

    -- Personal Insolvencies
    insolvency_business             INTEGER,
    insolvency_non_business         INTEGER,
    insolvency_total                INTEGER,
    insolvency_managers             INTEGER,
    insolvency_professionals        INTEGER,
    insolvency_technicians          INTEGER,
    insolvency_community_services   INTEGER,
    insolvency_clerical             INTEGER,
    insolvency_sales                INTEGER,
    insolvency_machinery_operators  INTEGER,
    insolvency_labourers            INTEGER,
    insolvency_other_unknown        INTEGER,

    -- Agriculture
    agri_holding_area_ha            DOUBLE,
    agri_dairy_cattle               INTEGER,
    agri_meat_cattle                INTEGER,
    agri_sheep_lambs                INTEGER,
    agri_pigs                       INTEGER,
    agri_meat_chickens              INTEGER,
    agri_broadacre_crops_ha         DOUBLE,
    agri_vegetables_ha              DOUBLE,
    agri_orchard_fruit_nut_ha       DOUBLE,
    agri_production_gross_value     DOUBLE,   -- $m
    agri_crops_gross_value          DOUBLE,
    agri_livestock_gross_value      DOUBLE,

    -- Employment by Industry (Census %)
    emp_pct_agriculture             DOUBLE,
    emp_pct_mining                  DOUBLE,
    emp_pct_manufacturing           DOUBLE,
    emp_pct_electricity_gas_water   DOUBLE,
    emp_pct_construction            DOUBLE,
    emp_pct_wholesale               DOUBLE,
    emp_pct_retail                  DOUBLE,
    emp_pct_accommodation_food      DOUBLE,
    emp_pct_transport               DOUBLE,
    emp_pct_info_media              DOUBLE,
    emp_pct_financial               DOUBLE,
    emp_pct_rental_real_estate      DOUBLE,
    emp_pct_professional            DOUBLE,
    emp_pct_admin_support           DOUBLE,
    emp_pct_public_admin            DOUBLE,
    emp_pct_education               DOUBLE,
    emp_pct_health_social           DOUBLE,
    emp_pct_arts_recreation         DOUBLE,
    emp_pct_other_services          DOUBLE,
    emp_pct_not_stated              DOUBLE,
    emp_total_persons               INTEGER,

    -- Dwelling Stock (Table 1 only, NULL for Table 2)
    dwellings_houses_additions      INTEGER,
    dwellings_houses_removals       INTEGER,
    dwellings_houses_total          INTEGER,
    dwellings_townhouses_additions  INTEGER,
    dwellings_townhouses_removals   INTEGER,
    dwellings_townhouses_total      INTEGER,
    dwellings_apartments_additions  INTEGER,
    dwellings_apartments_removals   INTEGER,
    dwellings_apartments_total      INTEGER,
    dwellings_total_additions       INTEGER,
    dwellings_total_removals        INTEGER,
    dwellings_total                 INTEGER,

    PRIMARY KEY (region_code, year, source_table)
);
```

> [!TIP]
> **Computed column `geography_level`** — derive it from the code format at insert time:
> ```python
> def classify_region(code):
>     code = str(code)
>     if code == 'AUS': return 'AUS'
>     if re.match(r'^\d$', code): return 'STATE'
>     if re.match(r'^\d[A-Z]', code): return 'GCCSA'
>     if re.match(r'^\d{3}$', code): return 'SA4'
>     if re.match(r'^\d{5}$', code): return 'SA3'
>     if re.match(r'^\d{9}$', code): return 'SA2'
>     return 'LGA'  # Table 2 codes
> ```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| **Single table, not normalised** | Only ~35K rows, same grain everywhere; normalising would add complexity with no performance benefit |
| **`geography_level` column** | Lets you filter queries by level (e.g., state-level only) without parsing codes |
| **`source_table` column** | Distinguishes Table 1 (ASGS) vs Table 2 (LGA) rows; dwelling stock cols are NULL for LGA rows |
| **`-` values → NULL** | The Excel uses `"-"` for suppressed/unavailable data; store as SQL NULL |
| **Composite PK** | `(region_code, year, source_table)` uniquely identifies every row |
