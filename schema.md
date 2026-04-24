# Warehouse Schema

Three tables in `data/curated/warehouse.duckdb` — one dimension and two facts.

---

## `facility` (Dimension)

| Column                      | Type       | Notes                                                        |
|-----------------------------|------------|--------------------------------------------------------------|
| `facility_id`               | VARCHAR    | **PK**                                                       |
| `facility_name`             | VARCHAR    |                                                              |
| `state`                     | VARCHAR    |                                                              |
| `primary_fuel`              | VARCHAR    |                                                              |
| `match_status`              | VARCHAR    |                                                              |
| `match_score`               | DOUBLE     |                                                              |
| `accreditation_code`        | VARCHAR    |                                                              |
| `station_name`              | VARCHAR    |                                                              |
| `postcode`                  | VARCHAR(4) | Zero-padded (preserves NT/ACT leading zeros)                 |
| `installed_capacity_mw`     | DOUBLE     |                                                              |
| `fuel_source`               | VARCHAR    |                                                              |
| `accreditation_start_date`  | DATE       |                                                              |
| `approval_date`             | DATE       |                                                              |
| `committed_date`            | VARCHAR    |                                                              |
| `suspension_status`         | VARCHAR    |                                                              |
| `baseline_mwh`              | DOUBLE     |                                                              |
| `cer_source_type`           | VARCHAR    |                                                              |
| `use_for_geocoding`         | BOOLEAN    |                                                              |
| `lat`                       | DOUBLE     |                                                              |
| `lon`                       | DOUBLE     |                                                              |
| `geocode_source`            | VARCHAR    |                                                              |
| `geom`                      | GEOMETRY   | WGS84 POINT via `ST_Point(lon, lat)`; NULL if lat/lon missing |

---

## `generation` (Fact)

| Column                          | Type    | Notes                              |
|---------------------------------|---------|------------------------------------|
| `facility_id`                   | VARCHAR | **FK** → `facility.facility_id`    |
| `financial_year_end`            | INTEGER | Composite **PK** part 1            |
| `reporting_year`                | INTEGER |                                    |
| `reporting_entity`              | VARCHAR | Composite **PK** part 2            |
| `facility_name`                 | VARCHAR |                                    |
| `row_type`                      | VARCHAR |                                    |
| `state`                         | VARCHAR |                                    |
| `grid_connected`                | BOOLEAN |                                    |
| `grid`                          | VARCHAR |                                    |
| `primary_fuel`                  | VARCHAR |                                    |
| `electricity_production_gj`     | DOUBLE  |                                    |
| `electricity_production_mwh`    | DOUBLE  |                                    |
| `scope1_emissions_tco2e`        | DOUBLE  |                                    |
| `scope2_emissions_tco2e`        | DOUBLE  |                                    |
| `total_emissions_tco2e`         | DOUBLE  |                                    |
| `emission_intensity_tco2e_per_mwh` | DOUBLE  |                                 |
| `jv_double_counted`             | BOOLEAN |                                    |

Composite PK: `(facility_id, financial_year_end, reporting_entity)`

> JV/ownership splits mean `(facility_id, financial_year_end)` alone is not unique — e.g. Bayswater 2015 appears under both AGL and Macquarie Generation.

---

## `abs_population` (Fact)

| Column                                       | Type    | Notes                  |
|----------------------------------------------|---------|------------------------|
| `code`                                       | VARCHAR | Composite **PK** part 1 |
| `label`                                      | VARCHAR |                        |
| `year`                                       | INTEGER | Composite **PK** part 2 |
| `geography_level`                            | VARCHAR | Indexed                |
| `state`                                      | VARCHAR | Indexed                |
| `estimated_resident_population_no`           | DOUBLE  |                        |
| `population_density_persons_km2`             | DOUBLE  |                        |
| `estimated_resident_population_males_no`     | DOUBLE  |                        |
| `estimated_resident_population_females_no`   | DOUBLE  |                        |
| `median_age_males_years`                     | DOUBLE  |                        |
| `median_age_females_years`                   | DOUBLE  |                        |
| `median_age_persons_years`                   | DOUBLE  |                        |
| `working_age_population_aged_15_64_years_no` | DOUBLE  |                        |
| `working_age_population_aged_15_64_years`    | DOUBLE  | % of population        |

Composite PK: `(code, year)`

---

## Relationships

```
facility
  facility_id (PK)
       ↑
generation
  facility_id (FK) ──┐
  financial_year_end  ├── composite PK
  reporting_entity   ──┘

abs_population
  code + year (composite PK)
  [no FK — joins to facility/generation via state]
```

`abs_population` has no foreign key to `facility`. It links indirectly through `state`.
