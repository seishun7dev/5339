"""ABS Economy & Industry data cleaning.

Loads Table 1 (ASGS regions: AUS → State → GCCSA → SA4 → SA3 → SA2) from
the Economy & Industry workbook and writes a single tidy wide CSV under
``data/cleaned/``. Table 2 (Local Government Areas) is skipped — it's a
parallel geography that neither NGER nor CER use natively, and carrying
it forward would force an LGA-postcode concordance we don't need.

Cleaning steps:
  1. Read ``Table 1`` with ``header=6`` (rows 0–5 are metadata: title,
     release date, section banner).
  2. Drop trailing empty rows (all of Code/Label/Year are NaN).
  3. Slugify column names (lowercase + non-alphanumerics → ``_``). All
     127 columns produce unique slugs, so a hand-written rename map
     isn't needed.
  4. Replace ABS's ``"-"`` suppressed-value sentinel with NaN.
  5. Coerce dtypes: ``code`` → str (preserves leading zeros and
     alphanumeric region codes), ``year`` → nullable Int, every
     remaining metric column → float.
  6. Derive ``geography_level`` from the code pattern (AUS / STATE /
     GCCSA / SA4 / SA3 / SA2) so downstream queries can filter by level
     without regex.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


RAW_FILE = Path("data") / "raw" / "abs" / "economy_and_industry.xlsx"
CLEANED_DIR = Path("data") / "cleaned"
CLEANED_FILE = CLEANED_DIR / "abs.csv"

SHEET = "Table 1"
HEADER_ROW = 6

# Regex patterns for classifying ASGS codes. Order matters — AUS is
# literal, single digits are states, a digit followed by letters is a
# GCCSA ("1GSYD"), and the N-digit codes are SA4/3/2.
_LEVEL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("AUS",   re.compile(r"^AUS$")),
    ("STATE", re.compile(r"^\d$")),
    ("GCCSA", re.compile(r"^\d[A-Z]+$")),
    ("SA4",   re.compile(r"^\d{3}$")),
    ("SA3",   re.compile(r"^\d{5}$")),
    ("SA2",   re.compile(r"^\d{9}$")),
]


def _log(msg: str) -> None:
    print(f"[ABS-clean] {msg}")


def _slugify(col: str) -> str:
    s = col.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")


def _classify(code: str) -> str:
    for level, pat in _LEVEL_PATTERNS:
        if pat.match(code):
            return level
    return "OTHER"


def clean_abs() -> pd.DataFrame:
    """Clean the ABS Economy & Industry workbook and write a tidy CSV."""
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    _log(f"Loading {SHEET} from {RAW_FILE}")
    df = pd.read_excel(RAW_FILE, sheet_name=SHEET, header=HEADER_ROW)
    _log(f"Raw shape: {df.shape}")

    # Drop trailing empty rows (seen after the last region in the sheet).
    df = df.dropna(subset=["Code", "Label", "Year"], how="all").reset_index(drop=True)

    # Slugify 127 column names to snake_case.
    df.columns = [_slugify(c) for c in df.columns]

    # ABS sentinel for suppressed/unavailable data.
    df = df.replace("-", pd.NA)

    # code: string (preserves alphanumeric codes like "AUS", "1GSYD").
    # Numeric-looking codes may arrive as ints/floats from Excel; strip
    # any ".0" suffix. NaN codes (trailing blank rows) become empty.
    def _code_to_str(v: object) -> str:
        if pd.isna(v):
            return ""
        s = str(v).strip()
        return s[:-2] if s.endswith(".0") else s

    df["code"] = df["code"].apply(_code_to_str)
    df["label"] = df["label"].astype(str).str.strip()

    # Drop any remaining rows with an empty code (defensive — no valid
    # region has an empty code).
    df = df[df["code"] != ""].reset_index(drop=True)

    # year: nullable integer. Rows without a valid year are footer notes
    # ("Note: …", "© Commonwealth of Australia …") — drop them.
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["year"]).reset_index(drop=True)

    # All remaining columns are numeric metrics. Assign in one go to
    # avoid frame fragmentation from 120+ column-by-column writes.
    metric_cols = [c for c in df.columns if c not in ("code", "label", "year")]
    df = df.assign(**{c: pd.to_numeric(df[c], errors="coerce") for c in metric_cols})

    # Defragment before adding more columns (read_excel + per-column
    # coercion leaves the internal block structure fragmented).
    df = df.copy()

    # Derive geography level from code pattern, then reorder so that
    # the identifier block sits at the front.
    df = df.assign(geography_level=df["code"].map(_classify))
    ids = ["code", "label", "year", "geography_level"]
    df = df[ids + [c for c in df.columns if c not in ids]]

    _log(f"Cleaned shape: {df.shape}")
    by_level = df.drop_duplicates("code")["geography_level"].value_counts().to_dict()
    _log(f"Unique regions by level: {by_level}")
    _log(f"Years: {sorted(df['year'].dropna().unique().tolist())}")

    df.to_csv(CLEANED_FILE, index=False)
    size_mb = CLEANED_FILE.stat().st_size / (1024 * 1024)
    _log(f"Saved to {CLEANED_FILE} ({size_mb:.2f} MB)")

    return df


if __name__ == "__main__":
    clean_abs()
