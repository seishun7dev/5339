"""Augmentation: geocode NGER-rooted facilities via Nominatim.

Two-tier strategy per facility:
    1. Precise: "<name>, <postcode>, <state>, Australia"
    2. Fallback (only on miss): "<postcode>, Australia"  → suburb centroid

Each query (precise OR fallback) is cached separately under its
literal query string in ``data/raw/geocode/nominatim_cache.json``.
Cache value: {lat, lon, name, state, postcode, area, source} or null.
``source`` is "facility" for precise hits, "postcode" for centroids.

Scope: every row with ``use_for_geocoding == True``. Most of these
won't have a precise OSM match — they're small commercial-rooftop
solar — but the postcode-centroid fallback still gives them a
location for region-level visualisations.

Cache rewrites after every live call — the 1.1 s Nominatim sleep
absorbs the disk write. HTTP errors are not cached (retry next run);
empty responses cache as null (definitive miss).

Policy: https://operations.osmfoundation.org/policies/nominatim/
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests


FACILITY_FILE = Path("data") / "curated" / "facility.csv"
CACHE_FILE    = Path("data") / "raw" / "geocode" / "nominatim_cache.json"

URL        = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "COMP5339-A1-geocoder/1.0 (USYD-semester-1-2026;)"
DELAY      = 1.1


def _fetch(query: str, *, name: str, state: str, postcode: str, source: str) -> dict | None:
    r = requests.get(
        URL,
        params={
            "q": query, "format": "json", "limit": 1,
            "countrycodes": "au", "addressdetails": 1,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    top = data[0]
    return {
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "name": name,
        "state": state,
        "postcode": postcode,
        "area": top.get("display_name", ""),
        "source": source,
    }


def _resolve(cache: dict, query: str, **fetch_kwargs) -> tuple[dict | None, bool]:
    """Return (result, did_live_call). Caches the result either way (None on miss)."""
    if query in cache:
        return cache[query], False
    try:
        cache[query] = _fetch(query, **fetch_kwargs)
    except requests.RequestException as e:
        print(f"  HTTP ERROR {query!r}: {e}")
        return None, True  # don't poison cache; sleep & move on
    CACHE_FILE.write_text(json.dumps(cache, indent=2, sort_keys=True))
    return cache[query], True


def geocode_facilities(*, limit: int | None = None) -> dict:
    df = pd.read_csv(FACILITY_FILE)
    targets = df[df["use_for_geocoding"] == True].reset_index(drop=True)
    if limit:
        targets = targets.head(limit)

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}

    live = precise_hits = fallback_hits = misses = 0
    for n, row in enumerate(targets.itertuples(index=False), 1):
        pc = str(int(row.postcode)) if pd.notna(row.postcode) else ""
        precise_q  = f"{row.facility_name}, {pc}, {row.state}, Australia"
        fallback_q = f"{pc}, Australia"

        result, did_call = _resolve(
            cache, precise_q,
            name=row.facility_name, state=row.state, postcode=pc, source="facility",
        )
        if did_call:
            live += 1
            time.sleep(DELAY)

        if result is None and pc:
            result, did_call = _resolve(
                cache, fallback_q,
                name=row.facility_name, state=row.state, postcode=pc, source="postcode",
            )
            if did_call:
                live += 1
                time.sleep(DELAY)
            if result:
                fallback_hits += 1
            else:
                misses += 1
        elif result:
            precise_hits += 1
        else:
            misses += 1

        if n % 25 == 0:
            print(f"[{n}/{len(targets)}] live={live} precise={precise_hits} "
                  f"fallback={fallback_hits} miss={misses}")

    total = precise_hits + fallback_hits
    print(f"Done. live={live}  precise={precise_hits}  fallback={fallback_hits}  "
          f"miss={misses}  coverage={total}/{len(targets)} ({total/len(targets):.1%})")
    return cache


if __name__ == "__main__":
    geocode_facilities()