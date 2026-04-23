"""NGER electricity-sector data acquisition.

Fetches 10 annual datasets from the Clean Energy Regulator's public API
(FY2014-15 through FY2023-24) and caches each year's raw JSON payload
to disk, untouched. Year assignment and any other transformations are
performed in the cleaning stage.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import quote

import requests


RAW_DIR = Path("data") / "raw" / "nger"

# The API rejects a literal "?select=*" with HTTP 500; the "=" must be
# percent-encoded. quote(..., safe="") does exactly that.
API_URL = (
    "https://api.cer.gov.au/datahub-public/v1/api"
    "/ODataDataset/NGER/dataset/{dataset_id}"
    f"?{quote('select=*', safe='')}"
)

# Dataset IDs paired with their reporting years. Year is encoded in the
# filename and injected into rows during cleaning.
YEAR_MAP: list[tuple[str, str]] = [
    ("ID0075", "2014-15"),
    ("ID0076", "2015-16"),
    ("ID0077", "2016-17"),
    ("ID0078", "2017-18"),
    ("ID0079", "2018-19"),
    ("ID0080", "2019-20"),
    ("ID0081", "2020-21"),
    ("ID0082", "2021-22"),
    ("ID0083", "2022-23"),
    ("ID0243", "2023-24"),
]

REQUEST_DELAY_SEC = 1.0


def _log(msg: str) -> None:
    print(f"[NGER-acquire] {msg}")


def fetch_nger(use_cache: bool = True) -> None:
    """Fetch NGER data for all ten reporting years.

    Each year is saved as its own JSON file under ``data/raw/nger/``,
    preserving the API response exactly as received.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    _log(f"Acquiring 10 datasets, FY{YEAR_MAP[0][1]} → FY{YEAR_MAP[-1][1]}")

    total_rows = 0
    fresh_fetches = 0

    for dataset_id, year in YEAR_MAP:
        out_path = RAW_DIR / f"nger_{year}.json"

        if use_cache and out_path.exists():
            with out_path.open() as f:
                n = len(json.load(f))
            _log(f"  FY{year} ({dataset_id}) → {n:,} rows [cached]")
            total_rows += n
            continue

        if fresh_fetches > 0:
            time.sleep(REQUEST_DELAY_SEC)

        resp = requests.get(API_URL.format(dataset_id=dataset_id), timeout=60)
        resp.raise_for_status()
        rows = resp.json()

        with out_path.open("w") as f:
            json.dump(rows, f)
        _log(f"  FY{year} ({dataset_id}) → {len(rows):,} rows")
        total_rows += len(rows)
        fresh_fetches += 1

    _log(
        f"Total: {total_rows:,} rows "
        f"({fresh_fetches} fetched, {len(YEAR_MAP) - fresh_fetches} cached)"
    )


if __name__ == "__main__":
    fetch_nger(use_cache=False)
