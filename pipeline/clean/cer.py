"""CER large-scale renewables data cleaning.

Loads the four raw CSVs produced by acquire (one per ``cer_source_type``),
normalises each to the same canonical schema, concatenates them, coerces
dtypes, and writes a single tidy CSV under ``data/cleaned/``.

Source columns vary across the four files (e.g. ``Power station name``
vs ``Project Name``; ``Installed capacity`` vs ``Installed capacity (MW)``
vs ``MW Capacity``). We normalise by lowercasing and stripping each
column name, then applying a single rename map that maps every source
variant to the canonical snake_case name.

A ``use_for_geocoding`` flag is stamped per source type — only
``historical_accredited`` rows are retained for geocoding (the other
three sets are out of NGER scope, not yet operational, or speculative).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


RAW_DIR = Path("data") / "raw" / "cer"
CLEANED_DIR = Path("data") / "cleaned"
CLEANED_FILE = CLEANED_DIR / "cer.csv"

# One source file per cer_source_type.
SOURCES: list[str] = [
    "historical_accredited",
    "approved_2026",
    "committed",
    "probable",
]

# Categorical flag — only historical_accredited rows are geocoded:
#   approved_2026 → post-NGER window, tiny embedded generators
#   committed     → not yet operational, name may still change
#   probable      → speculative, no postcode
_GEOCODE_FLAG: dict[str, bool] = {
    "historical_accredited": True,
    "approved_2026":         False,
    "committed":             False,
    "probable":              False,
}

# Applied after df.columns = df.columns.str.strip().str.lower(). Multiple
# source columns can map to the same target (e.g. "power station name"
# and "project name" both mean the station/project name).
_RENAME = {
    "accreditation code":           "accreditation_code",
    "power station name":           "station_name",
    "project name":                 "station_name",
    "state":                        "state",
    "postcode":                     "postcode",
    # capacity — three different spellings, all in MW
    "installed capacity":           "installed_capacity_mw",
    "installed capacity (mw)":      "installed_capacity_mw",
    "mw capacity":                  "installed_capacity_mw",
    # fuel source
    "fuel source(s)":               "fuel_source",
    "fuel source":                  "fuel_source",
    "accreditation start date":     "accreditation_start_date",
    "approval date":                "approval_date",
    "committed date (month/year)":  "committed_date",
    "suspension status":            "suspension_status",
    "baseline (mwh)":               "baseline_mwh",
    "comment":                      "comment",
}

# Date columns and their source formats. committed_date arrives as
# "Dec-2019"; every other date column is DD/MM/YYYY (dayfirst=True).
_DATE_COLS_DAYFIRST = [
    "accreditation_start_date",
    "approval_date",
]
_DATE_COL_MONTH_YEAR = "committed_date"

_NUMERIC_COLS = [
    "installed_capacity_mw",
    "baseline_mwh",
]

_FINAL_COLUMNS = [
    "cer_source_type",
    "accreditation_code",
    "station_name",
    "state",
    "postcode",
    "installed_capacity_mw",
    "fuel_source",
    "accreditation_start_date",
    "approval_date",
    "committed_date",
    "suspension_status",
    "baseline_mwh",
    "comment",
    "use_for_geocoding",
]


def _log(msg: str) -> None:
    print(f"[CER-clean] {msg}")


def _load_source(source: str) -> pd.DataFrame:
    # Read everything as string so we preserve postcode leading zeros
    # (NT/ACT postcodes like "0800") and don't guess dtypes prematurely.
    df = pd.read_csv(RAW_DIR / f"{source}.csv", dtype=str)
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns=_RENAME)
    df["cer_source_type"] = source
    return df


# Match SGU suffix variants (" w SGU", " w/ SGU", " W SGU", " wSGU", etc.)
# that sit between the fuel token and the end of the string.
_SGU_TAIL = r"(?:\s*[wW][/ ]?\s*SGU)?"

# One-or-more of: whitespace, comma, hyphen, en-dash. Used as the
# delimiter between a station name and a trailing state/fuel token.
_DELIM = r"[\s,\-–]+"


def _strip_name_suffix(name: object, state: object, fuel: object) -> object:
    """Drop trailing fuel/state tokens from a station name.

    Case-insensitive. Only strips a token if it matches the row's own
    ``state`` or ``fuel_source`` value — so informative descriptors like
    "Wind and Solar", "LFG", "Mini Hydro", "Solar Farm" are left alone.
    Delimiter-tolerant: handles dashes, commas, or just spaces between
    the station name and the trailing token (e.g. "Foo - Solar - NSW",
    "Foo, VIC", "Foo Solar NSW").
    """
    if not isinstance(name, str):
        return name
    state_rx = re.escape(state) if isinstance(state, str) else None
    fuel_rx = (re.escape(fuel) + _SGU_TAIL) if isinstance(fuel, str) else None

    # Trailing " STATE" (delimiter-tolerant).
    if state_rx:
        name = re.sub(rf"{_DELIM}{state_rx}\s*$", "", name, flags=re.IGNORECASE)
    # Trailing " FUEL STATE" (covers "Solar NSW" with no dash/comma).
    if fuel_rx and state_rx:
        name = re.sub(
            rf"{_DELIM}{fuel_rx}\s+{state_rx}\s*$", "", name, flags=re.IGNORECASE,
        )
    # Trailing " FUEL".
    if fuel_rx:
        name = re.sub(rf"{_DELIM}{fuel_rx}\s*$", "", name, flags=re.IGNORECASE)

    return name.strip()


def clean_cer() -> pd.DataFrame:
    """Clean raw CER data and write a single tidy CSV."""
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    _log(f"Loading {len(SOURCES)} sources from {RAW_DIR}/")
    frames = [_load_source(s) for s in SOURCES]
    df = pd.concat(frames, ignore_index=True)
    _log(f"Concatenated {len(df):,} rows")

    # Whitespace hygiene. All columns are still string at this point
    # (we read with dtype=str; coercion happens below).
    for col in df.columns:
        df[col] = df[col].str.strip()

    # Dates.
    for col in _DATE_COLS_DAYFIRST:
        df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    df[_DATE_COL_MONTH_YEAR] = pd.to_datetime(
        df[_DATE_COL_MONTH_YEAR], errors="coerce", format="%b-%Y"
    )

    # Numerics.
    for col in _NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Categorical geocoding flag.
    df["use_for_geocoding"] = df["cer_source_type"].map(_GEOCODE_FLAG)

    # Strip redundant " - Fuel - State" / " - State" suffixes from names
    # (the state and fuel already live in their own columns).
    before = df["station_name"].copy()
    df["station_name"] = df.apply(
        lambda r: _strip_name_suffix(r["station_name"], r["state"], r["fuel_source"]),
        axis=1,
    )
    _log(f"Station names trimmed: {(before != df['station_name']).sum():,} rows")

    df = df[_FINAL_COLUMNS]

    by_source = df["cer_source_type"].value_counts().to_dict()
    _log(f"Rows by source: {by_source}")
    _log(f"use_for_geocoding=True: {df['use_for_geocoding'].sum():,} rows")
    _log(f"Missing postcode (geocode pool): "
         f"{df[df.use_for_geocoding]['postcode'].isna().sum():,}")

    df.to_csv(CLEANED_FILE, index=False)
    size_kb = CLEANED_FILE.stat().st_size // 1024
    _log(f"Saved to {CLEANED_FILE} ({size_kb} KB)")

    return df


if __name__ == "__main__":
    clean_cer()
