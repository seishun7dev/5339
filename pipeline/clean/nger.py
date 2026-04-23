"""NGER electricity-sector data cleaning.

Loads the per-year raw JSON files produced by acquire, combines them into
a single tidy DataFrame, applies minimal cleaning (column renaming to
snake_case, sentinel handling, type coercion), flags known data-quality
issues, and writes the result to a single CSV under ``data/cleaned/``.

Column naming varies across the 10 source years (camelCase vs lowercase,
an inconsistent reporting-entity column in 2015-16, scope-emission
columns using different conventions in 2014-15, typo columns ending in
"2" in 2016-17). We normalise by lowercasing first, then apply a single
rename map that covers every surviving variant.

No filtering or aggregation is performed — all row types (F/FA/C) are
retained for downstream use.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


RAW_DIR = Path("data") / "raw" / "nger"
CLEANED_DIR = Path("data") / "cleaned"
CLEANED_FILE = CLEANED_DIR / "nger.csv"

YEARS: list[str] = [
    "2014-15", "2015-16", "2016-17", "2017-18", "2018-19",
    "2019-20", "2020-21", "2021-22", "2022-23", "2023-24",
]

# Applied after df.columns = df.columns.str.lower(). Multiple source
# columns can map to the same target (e.g. controllingcorporation and
# reportingentity both mean the reporting entity).
_RENAME = {
    # reporting entity — 2015-16 names it differently
    "reportingentity":            "reporting_entity",
    "controllingcorporation":     "reporting_entity",
    "facilityname":               "facility_name",
    "type":                       "row_type",
    "state":                      "state",
    "electricityproductiongj":    "electricity_production_gj",
    "electricityproductionmwh":   "electricity_production_mwh",
    # scope 1 — 2014-15 uses a shorter form
    "scope1tco2e":                "scope1_emissions_tco2e",
    "totalscope1emissionstco2e":  "scope1_emissions_tco2e",
    # scope 2 — 2014-15 uses a shorter form; 2016-17 has a trailing-2 typo
    "scope2tco2e":                "scope2_emissions_tco2e",
    "totalscope2emissionstco2e":  "scope2_emissions_tco2e",
    "totalscope2emissionstco2e2": "scope2_emissions_tco2e",
    "totalemissionstco2e":        "total_emissions_tco2e",
    # intensity — pre-2017 omits "co2e" from the column name
    "emissionintensitytmwh":      "emission_intensity_tco2e_per_mwh",
    "emissionintensitytco2emwh":  "emission_intensity_tco2e_per_mwh",
    # grid — 2016-17 has a trailing-2 typo
    "gridconnected":              "grid_connected",
    "gridconnected2":             "grid_connected",
    "grid":                       "grid",
    "primaryfuel":                "primary_fuel",
    "importantnotes":             "important_notes",
}

_STRING_COLS_WITH_SENTINEL = [
    "state", "grid_connected", "grid", "primary_fuel", "important_notes",
]

_NUMERIC_COLS = [
    "electricity_production_gj",
    "electricity_production_mwh",
    "scope1_emissions_tco2e",
    "scope2_emissions_tco2e",
    "total_emissions_tco2e",
    "emission_intensity_tco2e_per_mwh",
]

# Case-insensitive substrings in important_notes that indicate a joint
# venture double-count. Drives integration-stage deduplication.
_JV_KEYWORDS = (
    "joint venture",
    "included the same data",
    "reported multiple times",
)

_FINAL_COLUMNS = [
    "reporting_year",
    "reporting_entity",
    "facility_name",
    "row_type",
    "state",
    "grid_connected",
    "grid",
    "primary_fuel",
    "electricity_production_gj",
    "electricity_production_mwh",
    "scope1_emissions_tco2e",
    "scope2_emissions_tco2e",
    "total_emissions_tco2e",
    "emission_intensity_tco2e_per_mwh",
    "jv_double_counted",
    "important_notes",
]


def _log(msg: str) -> None:
    print(f"[NGER-clean] {msg}")


def _load_year(year: str) -> pd.DataFrame:
    with (RAW_DIR / f"nger_{year}.json").open() as f:
        rows = json.load(f)
    df = pd.DataFrame(rows)
    df.columns = df.columns.str.lower()
    df = df.rename(columns=_RENAME)
    df["reporting_year"] = year
    return df


def _flag_jv_double_count(notes: pd.Series) -> pd.Series:
    lowered = notes.fillna("").str.lower()
    mask = pd.Series(False, index=notes.index)
    for kw in _JV_KEYWORDS:
        mask |= lowered.str.contains(kw, regex=False)
    return mask


def clean_nger() -> pd.DataFrame:
    """Clean raw NGER data and write a single tidy CSV."""
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    _log(f"Loading {len(YEARS)} years from {RAW_DIR}/")
    df = pd.concat([_load_year(y) for y in YEARS], ignore_index=True)
    _log(f"Concatenated {len(df):,} rows")

    # Sentinel "-" → NaN in string columns.
    for col in _STRING_COLS_WITH_SENTINEL:
        df[col] = df[col].replace("-", pd.NA)

    df["reporting_entity"] = df["reporting_entity"].str.strip()
    df["facility_name"] = df["facility_name"].str.strip()

    for col in _NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["jv_double_counted"] = _flag_jv_double_count(df["important_notes"])

    df = df[_FINAL_COLUMNS]

    by_type = df["row_type"].value_counts().to_dict()
    _log(f"Row types: {by_type}")
    _log(f"JV double-count flagged: {df['jv_double_counted'].sum():,} rows")
    _log(
        f"Missing state: {df['state'].isna().sum():,} "
        f"(expected ≈ corporate-total rows: {by_type.get('C', 0):,})"
    )

    df.to_csv(CLEANED_FILE, index=False)
    size_mb = CLEANED_FILE.stat().st_size / (1024 * 1024)
    _log(f"Saved to {CLEANED_FILE} ({size_mb:.2f} MB)")

    return df


if __name__ == "__main__":
    clean_nger()
