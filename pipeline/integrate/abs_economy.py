"""Integration: ABS cleaned → abs_economy (curated).

Takes the cleaned wide ABS table and adds a 2-letter ``state`` abbrev
column so that joins against ``facility.state`` and ``generation.state``
(both NGER/CER 2-letter form) work without a separate dim_state lookup.

The ASGS code encodes the containing state in its leading digit
(1=NSW, 2=VIC, …, 9=OT) — for STATE rows the code itself is that
single digit; for GCCSA/SA4/SA3/SA2 rows the leading digit of the
longer code is the same state.

The AUS row and any OTHER rows get a NULL state.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


CLEANED_FILE = Path("data") / "cleaned" / "abs.csv"
CURATED_DIR = Path("data") / "curated"
CURATED_FILE = CURATED_DIR / "abs_economy.csv"

# Single-digit ASGS state code → 2-letter abbrev. Mirrors NGER/CER
# state values (NT + ACT split, plus "OT" = Other Territories).
_STATE_DIGIT_TO_ABBREV: dict[str, str] = {
    "1": "NSW",
    "2": "VIC",
    "3": "QLD",
    "4": "SA",
    "5": "WA",
    "6": "TAS",
    "7": "NT",
    "8": "ACT",
    "9": "OT",
}


def _log(msg: str) -> None:
    print(f"[integrate-abs] {msg}")


def _state_abbrev(code: str, level: str) -> object:
    """Return the 2-letter state abbrev for any ASGS code, or NA.

    The first character of every non-AUS ASGS code is its state digit.
    AUS is national; anything not matching falls through to NA.
    """
    if level == "AUS" or not isinstance(code, str) or not code:
        return pd.NA
    return _STATE_DIGIT_TO_ABBREV.get(code[0], pd.NA)


def integrate_abs_economy() -> pd.DataFrame:
    """Add ``state`` abbrev column and write the curated CSV."""
    CURATED_DIR.mkdir(parents=True, exist_ok=True)

    # Keep postcode-like numeric strings as strings on re-read so we
    # don't lose leading zeros in future (no postcode here, but the
    # principle: let the reader control dtype).
    df = pd.read_csv(CLEANED_FILE, dtype={"code": str, "year": "Int64"})
    _log(f"Loaded {len(df):,} rows × {df.shape[1]} cols")

    # Defragment before adding a new column (read_csv on a 128-col
    # frame leaves it fragmented).
    df = df.copy()
    df = df.assign(state=df.apply(
        lambda r: _state_abbrev(r["code"], r["geography_level"]), axis=1,
    ))

    # Reorder so state sits right after geography_level.
    cols = list(df.columns)
    cols.remove("state")
    insert_at = cols.index("geography_level") + 1
    df = df[cols[:insert_at] + ["state"] + cols[insert_at:]]

    non_null = df["state"].notna().sum()
    _log(f"state abbrev populated: {non_null:,} rows (AUS rows left NULL)")
    _log(f"state distribution (unique): {sorted(df['state'].dropna().unique().tolist())}")

    df.to_csv(CURATED_FILE, index=False)
    size_mb = CURATED_FILE.stat().st_size / (1024 * 1024)
    _log(f"Saved to {CURATED_FILE} ({size_mb:.2f} MB)")

    return df


if __name__ == "__main__":
    integrate_abs_economy()
