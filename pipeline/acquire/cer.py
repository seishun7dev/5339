"""CER large-scale renewables data acquisition.

Scrapes four datasets from the Clean Energy Regulator website:

    historical_accredited  — historical power stations (accredited, decades)
    approved_2026          — accredited for the 2026 reporting year
    committed              — projects with financial/grid commitments
    probable               — speculative pipeline

Each dataset is served as a CSV behind a ``/document/<slug>`` URL on one
of two landing pages. Rather than hardcode the slugs, we fetch the page
HTML and search anchor ``href``s for link slugs whose fragments match
keyword rules (``must_contain`` / ``must_not_contain``). When multiple
links match (e.g. the historical page lists both an XLSX and a CSV
variant), we HEAD each candidate and keep the one whose content-type is
CSV.

All four files land in ``data/raw/cer/`` under our canonical names.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


RAW_DIR = Path("data") / "raw" / "cer"

BASE = "https://cer.gov.au"
MAIN_PAGE = f"{BASE}/markets/reports-and-data/large-scale-renewable-energy-data"
HISTORICAL_PAGE = (
    f"{MAIN_PAGE}/historical-large-scale-renewable-energy-supply-data"
)

# Each target names the page to scrape and the slug keywords to match.
# must_not_contain is needed because the main page also exposes historical
# and LGC-total documents whose slugs also contain "accredited".
TARGETS: list[dict] = [
    {
        "name": "historical_accredited",
        "page": HISTORICAL_PAGE,
        "must_contain": ["historical", "accredited"],
        "must_not_contain": [],
    },
    {
        "name": "approved_2026",
        "page": MAIN_PAGE,
        "must_contain": ["accredited"],
        "must_not_contain": ["historical", "total-lgcs"],
    },
    {
        "name": "committed",
        "page": MAIN_PAGE,
        "must_contain": ["committed"],
        "must_not_contain": [],
    },
    {
        "name": "probable",
        "page": MAIN_PAGE,
        "must_contain": ["probable"],
        "must_not_contain": [],
    },
]

REQUEST_TIMEOUT = 60


def _log(msg: str) -> None:
    print(f"[CER-acquire] {msg}")


def _find_csv_url(
    session: requests.Session,
    page_html: str,
    page_url: str,
    must_contain: list[str],
    must_not_contain: list[str],
) -> str:
    """Search the page for a /document/<slug> link serving CSV content."""
    soup = BeautifulSoup(page_html, "html.parser")
    candidates: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        if "/document/" not in href.lower():
            continue
        slug = href.rstrip("/").rsplit("/", 1)[-1].lower()
        if any(kw not in slug for kw in must_contain):
            continue
        if any(kw in slug for kw in must_not_contain):
            continue
        full = urljoin(page_url, href)
        if full in seen:
            continue
        seen.add(full)
        candidates.append(full)

    for url in candidates:
        resp = session.head(url, allow_redirects=True, timeout=REQUEST_TIMEOUT)
        if "csv" in resp.headers.get("content-type", "").lower():
            return url

    raise RuntimeError(
        f"No CSV link on {page_url} matched "
        f"must_contain={must_contain} must_not_contain={must_not_contain}"
    )


def fetch_cer(use_cache: bool = True) -> None:
    """Scrape and download all four CER datasets as raw CSVs."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    _log(f"Acquiring {len(TARGETS)} datasets")

    session = requests.Session()
    page_cache: dict[str, str] = {}  # avoid re-fetching the main page 3×

    fresh = 0
    for t in TARGETS:
        out = RAW_DIR / f"{t['name']}.csv"

        if use_cache and out.exists():
            _log(f"  {t['name']} → {out.stat().st_size // 1024} KB [cached]")
            continue

        page = t["page"]
        if page not in page_cache:
            r = session.get(page, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            page_cache[page] = r.text

        url = _find_csv_url(
            session, page_cache[page], page,
            t["must_contain"], t["must_not_contain"],
        )
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        out.write_bytes(resp.content)
        _log(
            f"  {t['name']} → {url.rsplit('/', 1)[-1]} "
            f"({len(resp.content) // 1024} KB)"
        )
        fresh += 1

    _log(f"Done. ({fresh} fetched, {len(TARGETS) - fresh} cached)")


if __name__ == "__main__":
    fetch_cer(use_cache=False)
