"""Integration: NGER + CER → facility + generation.

Builds two curated tables by matching NGER facility-year rows against
CER power-station metadata.

Outputs (under ``data/curated/``):

    facility.csv   — one row per unique physical facility.
    generation.csv — one row per facility-year (NGER F/FA rows only).

Matching algorithm, applied per NGER facility:

    1. Exact match: normalised name == normalised CER name
       AND  state == state
       AND  fuel-category == fuel-category.
    2. Fuzzy match (rapidfuzz token_set_ratio ≥ 85) within the same
       state + fuel-category pool.
    3. Otherwise, nger_only.

CER rows unclaimed after the two-stage pass become cer_only.

The three-key conjunction (name + state + fuel) prevents cross-fuel
collisions — e.g. a hypothetical "Sunraysia" Wind facility will never
match a "Sunraysia" Solar facility even if the name normalises the
same.

Name normalisation is used only for matching. Display names in
``facility.facility_name`` keep the original NGER or CER casing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process


NGER_CLEANED = Path("data") / "cleaned" / "nger.csv"
CER_CLEANED  = Path("data") / "cleaned" / "cer.csv"
CURATED_DIR  = Path("data") / "curated"
FACILITY_FILE   = CURATED_DIR / "facility.csv"
GENERATION_FILE = CURATED_DIR / "generation.csv"

FUZZY_THRESHOLD = 85

# Map NGER primary_fuel → CER fuel_source category for matching.
# NGER fuels not in this map have no CER counterpart (Coal, Gas,
# Diesel, Battery, etc.) and automatically fall through to nger_only.
_NGER_TO_CER_FUEL: dict[str, str] = {
    "Wind":                "Wind",
    "Solar":               "Solar",
    "Hydro":               "Hydro",
    "Landfill Gas":        "Biomass",
    "Waste Coal Mine Gas": "Biomass",
}

# Trailing descriptors stripped during name normalisation (longest
# first — order matters). Case-insensitive via the lowercase step.
_NAME_SUFFIXES = (
    "solar power station", "hydro power station", "wind power station",
    "power station", "power plant",
    "solar farm", "wind farm",
    "solar pv", "solar park",
    "pv",
)


def _log(msg: str) -> None:
    print(f"[integrate-facility] {msg}")


def _normalise_name(name: object) -> str:
    """Strip to a matching key — punctuation out, trailing descriptors out."""
    if not isinstance(name, str):
        return ""
    s = name.lower()
    s = re.sub(r"[.,'\"()/\\&\-–]", " ", s)
    for suffix in _NAME_SUFFIXES:
        s = re.sub(rf"\s+{re.escape(suffix)}\s*$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _load_and_prepare() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (nger_rows, nger_facilities, cer_stations) ready for matching."""
    nger = pd.read_csv(NGER_CLEANED)
    cer = pd.read_csv(CER_CLEANED, dtype={"postcode": str})

    # Drop corporate roll-ups, JV double-counts, and sentinel row-types.
    mask = (
        nger["row_type"].isin(["F", "FA"])
        & (~nger["jv_double_counted"].astype(bool))
        & nger["facility_name"].notna()
    )
    nger_rows = nger[mask].reset_index(drop=True)
    _log(f"NGER rows after filter (F/FA, non-JV, named): {len(nger_rows):,}")

    # Unique facility identity = (name, state, primary_fuel).
    nger_facilities = (
        nger_rows[["facility_name", "state", "primary_fuel"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    nger_facilities["norm_name"] = nger_facilities["facility_name"].apply(_normalise_name)
    nger_facilities["fuel_match"] = nger_facilities["primary_fuel"].map(_NGER_TO_CER_FUEL)
    _log(f"Unique NGER facilities: {len(nger_facilities):,}")

    cer_stations = cer.reset_index(drop=True).copy()
    cer_stations["norm_name"] = cer_stations["station_name"].apply(_normalise_name)
    cer_stations["fuel_match"] = cer_stations["fuel_source"]
    _log(f"CER station candidates: {len(cer_stations):,}")

    return nger_rows, nger_facilities, cer_stations


def _match(
    nger_facilities: pd.DataFrame, cer_stations: pd.DataFrame,
) -> pd.DataFrame:
    """Greedy match: for each NGER facility, find best unclaimed CER row.

    Returns a DataFrame aligned with ``nger_facilities`` with columns:
        cer_index, match_status, match_score
    where cer_index is -1 for nger_only.
    """
    taken: set[int] = set()
    results = []
    # Pre-bucket CER by (state, fuel) for fast lookup.
    cer_by_key = cer_stations.groupby(["state", "fuel_match"], dropna=False)

    for nger_row in nger_facilities.itertuples(index=False):
        if pd.isna(nger_row.fuel_match):
            results.append((-1, "nger_only", None))
            continue

        key = (nger_row.state, nger_row.fuel_match)
        try:
            pool = cer_by_key.get_group(key)
        except KeyError:
            results.append((-1, "nger_only", None))
            continue

        pool = pool[~pool.index.isin(taken)]
        if pool.empty:
            results.append((-1, "nger_only", None))
            continue

        # Stage 1 — exact normalised-name match in the pool.
        exact = pool.index[pool["norm_name"] == nger_row.norm_name]
        if len(exact) > 0:
            idx = int(exact[0])
            taken.add(idx)
            results.append((idx, "exact", 100.0))
            continue

        # Stage 2 — fuzzy within the pool.
        best = process.extractOne(
            nger_row.norm_name,
            pool["norm_name"].tolist(),
            scorer=fuzz.token_set_ratio,
        )
        if best and best[1] >= FUZZY_THRESHOLD:
            _, score, pool_pos = best
            idx = int(pool.index[pool_pos])
            taken.add(idx)
            results.append((idx, "fuzzy", float(score)))
            continue

        results.append((-1, "nger_only", None))

    return pd.DataFrame(
        results,
        columns=["cer_index", "match_status", "match_score"],
        index=nger_facilities.index,
    )


def _build_facility_table(
    nger_facilities: pd.DataFrame,
    cer_stations: pd.DataFrame,
    match: pd.DataFrame,
) -> pd.DataFrame:
    """Assemble the facility table from matched + unmatched rows."""
    nf = nger_facilities.drop(columns=["norm_name", "fuel_match"]).copy()
    cs = cer_stations.drop(columns=["norm_name", "fuel_match"]).copy()

    # Columns pulled from CER. Everything that isn't an identity key.
    cer_cols = [c for c in cs.columns if c not in ("station_name", "state", "fuel_source")]

    # --- Matched + nger_only rows (rooted in NGER) ---
    rooted = pd.concat([nf, match], axis=1).copy()
    matched_mask = rooted["cer_index"] >= 0
    # Attach CER attrs for matched rows; leave nulls for nger_only.
    cer_attached = cs.loc[rooted.loc[matched_mask, "cer_index"].astype(int)].reset_index(drop=True)
    cer_attached.index = rooted.index[matched_mask]
    for col in ["station_name", "fuel_source"] + cer_cols:
        rooted[col] = pd.NA
        rooted.loc[matched_mask, col] = cer_attached[col]

    # --- cer_only rows (CER stations nobody claimed) ---
    claimed = set(match.loc[match["cer_index"] >= 0, "cer_index"].astype(int))
    unclaimed_idx = [i for i in cs.index if i not in claimed]
    cer_only = cs.loc[unclaimed_idx].reset_index(drop=True)
    cer_only["facility_name"] = cer_only["station_name"]
    cer_only["primary_fuel"] = cer_only["fuel_source"]
    cer_only["match_status"] = "cer_only"
    cer_only["match_score"] = pd.NA

    facility = pd.concat([rooted, cer_only], ignore_index=True)
    facility = facility.drop(columns=["cer_index"])

    # Assign surrogate IDs.
    facility.insert(0, "facility_id", range(1, len(facility) + 1))

    # Geocoding placeholders (Task 4).
    facility["lat"] = pd.NA
    facility["lon"] = pd.NA
    facility["geocode_source"] = pd.NA

    # Column order: identity → match → CER attrs → geocoding. Drop
    # CER `comment` — free-text that isn't useful for integration.
    ordered = [
        "facility_id", "facility_name", "state", "primary_fuel",
        "match_status", "match_score",
        "accreditation_code", "station_name", "postcode",
        "installed_capacity_mw", "fuel_source",
        "accreditation_start_date", "approval_date", "committed_date",
        "suspension_status", "baseline_mwh",
        "cer_source_type", "use_for_geocoding",
        "lat", "lon", "geocode_source",
    ]
    facility = facility[ordered]

    return facility


def _build_generation_table(
    nger_rows: pd.DataFrame, facility: pd.DataFrame,
) -> pd.DataFrame:
    """Attach facility_id to every NGER facility-year row and derive FY end."""
    # Lookup key: (facility_name, state, primary_fuel) → facility_id.
    key_cols = ["facility_name", "state", "primary_fuel"]
    lookup = facility.dropna(subset=key_cols)[key_cols + ["facility_id"]]
    gen = nger_rows.merge(lookup, on=key_cols, how="left")
    missing = gen["facility_id"].isna().sum()
    if missing:
        _log(f"WARN: {missing:,} generation rows have no facility_id match")

    gen["facility_id"] = gen["facility_id"].astype("Int64")
    gen["financial_year_end"] = gen["reporting_year"].str[:4].astype(int) + 1

    # Drop NGER `important_notes` — free-text; jv_double_counted already
    # captures the integration-relevant signal.
    gen = gen.drop(columns=["important_notes"], errors="ignore")

    # Put the keys first, keep every NGER column after.
    nger_cols = [c for c in gen.columns if c not in ("facility_id", "financial_year_end")]
    gen = gen[["facility_id", "financial_year_end"] + nger_cols]
    return gen


def integrate_facility_generation() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the full NGER ↔ CER integration and write both curated CSVs."""
    CURATED_DIR.mkdir(parents=True, exist_ok=True)

    nger_rows, nger_facilities, cer_stations = _load_and_prepare()

    match = _match(nger_facilities, cer_stations)
    status_counts = match["match_status"].value_counts().to_dict()
    _log(f"NGER match outcomes: {status_counts}")

    facility = _build_facility_table(nger_facilities, cer_stations, match)
    cer_only = (facility["match_status"] == "cer_only").sum()
    _log(f"Final match mix: {facility['match_status'].value_counts().to_dict()}")
    _log(f"Facility table: {len(facility):,} rows ({cer_only:,} cer_only)")

    generation = _build_generation_table(nger_rows, facility)
    _log(f"Generation table: {len(generation):,} rows")

    facility.to_csv(FACILITY_FILE, index=False)
    generation.to_csv(GENERATION_FILE, index=False)
    _log(f"Saved {FACILITY_FILE} ({FACILITY_FILE.stat().st_size // 1024} KB)")
    _log(f"Saved {GENERATION_FILE} ({GENERATION_FILE.stat().st_size // 1024} KB)")

    return facility, generation


if __name__ == "__main__":
    integrate_facility_generation()
