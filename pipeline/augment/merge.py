"""Augmentation: merge cached geocodes back into facility.csv.

Reads ``data/raw/geocode/nominatim_cache.json`` and fills
``lat`` / ``lon`` / ``geocode_source`` on every facility row.

Two-index lookup:
    1. (facility_name, state) → precise OSM hit  → ``nominatim_facility``
    2. postcode               → suburb centroid  → ``nominatim_postcode``

Indexing by name + state (instead of reconstructing the original
precise query string) lets rows with a missing postcode still
match — useful for nger_only facilities that NGER doesn't carry
postcodes for, but whose name happens to coincide with a CER-side
entry that was geocoded.

Postcode is the right fallback key because a single Nominatim
postcode response services every facility in that postcode.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


FACILITY_FILE = Path("data") / "curated" / "facility.csv"
CACHE_FILE    = Path("data") / "raw" / "geocode" / "nominatim_cache.json"


def merge_geocodes() -> pd.DataFrame:
    cache = json.loads(CACHE_FILE.read_text())

    by_name_state: dict[tuple[str, str], dict] = {}
    by_postcode:   dict[str, dict] = {}
    for entry in cache.values():
        if not entry:
            continue
        if entry["source"] == "facility":
            by_name_state[(entry["name"], entry["state"])] = entry
        else:
            by_postcode[entry["postcode"]] = entry

    facility = pd.read_csv(FACILITY_FILE)

    def lookup(row: pd.Series) -> pd.Series:
        hit = by_name_state.get((row["facility_name"], row["state"]))
        if hit:
            return pd.Series([hit["lat"], hit["lon"], "nominatim_facility"])
        if pd.notna(row["postcode"]):
            hit = by_postcode.get(str(int(row["postcode"])))
            if hit:
                return pd.Series([hit["lat"], hit["lon"], "nominatim_postcode"])
        return pd.Series([None, None, None])

    facility[["lat", "lon", "geocode_source"]] = facility.apply(lookup, axis=1)
    facility.to_csv(FACILITY_FILE, index=False)

    counts = facility["geocode_source"].value_counts(dropna=False).to_dict()
    print(f"[augment-merge] Wrote {FACILITY_FILE.name}: {counts}")
    return facility


if __name__ == "__main__":
    merge_geocodes()
