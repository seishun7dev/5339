"""Load the three curated CSVs into a DuckDB warehouse.

Schema (star-ish; grain-driven split across sources):

    facility          dim    4,219 rows   PK facility_id             + geom POINT
    generation        fact   4,850 rows   PK (facility_id, financial_year_end, reporting_entity)
    abs_population    fact   26,181 rows  PK (code, year)

``facility.geom`` is a WGS84 POINT built via ST_Point(lon, lat). The
spatial extension is installed and loaded.

``postcode`` is cast to VARCHAR(4) with zero-padding so NT/ACT codes
(08xx, 02xx) survive the CSV round-trip that would otherwise lose the
leading zero.
"""

from __future__ import annotations

from pathlib import Path

import duckdb


CURATED = Path("data") / "curated"
DB_FILE = CURATED / "warehouse.duckdb"

FACILITY_CSV   = CURATED / "facility.csv"
GENERATION_CSV = CURATED / "generation.csv"
ABS_CSV        = CURATED / "abs_population.csv"


def build_warehouse(db_path: Path = DB_FILE) -> Path:
    if db_path.exists():
        db_path.unlink()

    con = duckdb.connect(str(db_path))

    # Spatial extension — adds GEOMETRY type + ST_* functions. Loaded
    # into the DB file so re-opens don't need a reinstall.
    con.execute("INSTALL spatial;")
    con.execute("LOAD spatial;")

    # ── facility (dim) ────────────────────────────────────────────
    con.execute(f"""
        CREATE TABLE facility AS
        SELECT
            facility_id,
            facility_name,
            state,
            primary_fuel,
            match_status,
            match_score,
            accreditation_code,
            station_name,
            -- postcodes are AU 4-digit incl. leading zeros (NT/ACT)
            CASE WHEN postcode IS NULL THEN NULL
                 ELSE lpad(CAST(CAST(postcode AS INTEGER) AS VARCHAR), 4, '0')
            END AS postcode,
            installed_capacity_mw,
            fuel_source,
            CAST(accreditation_start_date AS DATE) AS accreditation_start_date,
            CAST(approval_date             AS DATE) AS approval_date,
            committed_date,
            suspension_status,
            baseline_mwh,
            cer_source_type,
            CAST(use_for_geocoding AS BOOLEAN) AS use_for_geocoding,
            lat,
            lon,
            geocode_source,
            CASE WHEN lat IS NOT NULL AND lon IS NOT NULL
                 THEN ST_Point(lon, lat)
            END AS geom
        FROM read_csv_auto('{FACILITY_CSV.as_posix()}', header=True);
    """)
    con.execute("CREATE UNIQUE INDEX facility_pk ON facility(facility_id);")

    # ── generation (fact) ─────────────────────────────────────────
    con.execute(f"""
        CREATE TABLE generation AS
        SELECT
            facility_id,
            financial_year_end,
            reporting_year,
            reporting_entity,
            facility_name,
            row_type,
            state,
            grid_connected,
            grid,
            primary_fuel,
            electricity_production_gj,
            electricity_production_mwh,
            scope1_emissions_tco2e,
            scope2_emissions_tco2e,
            total_emissions_tco2e,
            emission_intensity_tco2e_per_mwh,
            CAST(jv_double_counted AS BOOLEAN) AS jv_double_counted
        FROM read_csv_auto('{GENERATION_CSV.as_posix()}', header=True);
    """)
    # Composite PK — JV/ownership splits mean (facility_id, FY) alone
    # is not unique (20 legitimate dupes, e.g. Bayswater 2015 across
    # AGL + Macquarie Generation mid-sale).
    con.execute("""
        CREATE UNIQUE INDEX generation_pk
        ON generation(facility_id, financial_year_end, reporting_entity);
    """)
    con.execute("CREATE INDEX generation_facility_fk ON generation(facility_id);")
    con.execute("CREATE INDEX generation_fy ON generation(financial_year_end);")

    # ── abs_population ────────────────────────────────────────────
    con.execute(f"""
        CREATE TABLE abs_population AS
        SELECT * FROM read_csv_auto('{ABS_CSV.as_posix()}', header=True, all_varchar=False);
    """)
    con.execute("CREATE UNIQUE INDEX abs_population_pk ON abs_population(code, year);")
    con.execute("CREATE INDEX abs_population_level ON abs_population(geography_level);")
    con.execute("CREATE INDEX abs_population_state ON abs_population(state);")

    # ── Sanity: orphan check + row counts ─────────────────────────
    orphans = con.execute("""
        SELECT COUNT(*) FROM generation g
        LEFT JOIN facility f USING (facility_id)
        WHERE f.facility_id IS NULL;
    """).fetchone()[0]
    assert orphans == 0, f"generation has {orphans} rows with no matching facility"

    counts = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("facility", "generation", "abs_population")
    }
    geom_ok = con.execute("SELECT COUNT(*) FROM facility WHERE geom IS NOT NULL").fetchone()[0]

    con.close()
    print(f"[duckdb-load] Built {db_path} — {counts}, facility.geom populated on {geom_ok} rows")
    return db_path


if __name__ == "__main__":
    build_warehouse()
