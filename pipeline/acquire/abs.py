"""ABS Data by Region — Economy and Industry acquisition.

The ABS hosts ten XLSX files on its 2011-24 Data by Region methodology
page, one per topic (Population, Economy, Income, Health, etc.). Each
file link sits below a heading that names the topic. The filename alone
(``14100DO0003_2011-24.xlsx``) does not encode the topic, so we scrape
the page for the heading we want ("Economy and industry, ASGS and LGA,
…") and pick the first XLSX link after it.

Only one file is downloaded — ``economy_and_industry.xlsx`` — landing
under ``data/raw/abs/``.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


RAW_DIR = Path("data") / "raw" / "abs"
OUT_FILE = RAW_DIR / "economy_and_industry.xlsx"

PAGE_URL = "https://www.abs.gov.au/methodologies/data-region-methodology/2011-24"

# Heading must contain all of these (case-insensitive) to match.
HEADING_KEYWORDS = ["economy", "industry"]

REQUEST_TIMEOUT = 120


def _log(msg: str) -> None:
    print(f"[ABS-acquire] {msg}")


def _find_xlsx_url(page_html: str, page_url: str, keywords: list[str]) -> str:
    """Find the first XLSX link following a heading matching keywords."""
    soup = BeautifulSoup(page_html, "html.parser")
    for heading in soup.find_all(["h2", "h3", "h4"]):
        text = heading.get_text().lower()
        if not all(kw in text for kw in keywords):
            continue
        for a in heading.find_all_next("a", href=True):
            if a["href"].lower().endswith(".xlsx"):
                return urljoin(page_url, a["href"])
        break
    raise RuntimeError(
        f"No XLSX link followed a heading matching {keywords} on {page_url}"
    )


def fetch_abs(use_cache: bool = True) -> None:
    """Scrape the ABS methodology page and download the Economy & Industry XLSX."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if use_cache and OUT_FILE.exists():
        _log(f"  economy_and_industry.xlsx → {OUT_FILE.stat().st_size // 1024} KB [cached]")
        return

    session = requests.Session()
    _log(f"GET {PAGE_URL}")
    page = session.get(PAGE_URL, timeout=REQUEST_TIMEOUT)
    page.raise_for_status()

    url = _find_xlsx_url(page.text, PAGE_URL, HEADING_KEYWORDS)
    _log(f"Found: {url.rsplit('/', 1)[-1]}")

    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    OUT_FILE.write_bytes(resp.content)
    _log(f"Saved to {OUT_FILE} ({len(resp.content) // 1024} KB)")


if __name__ == "__main__":
    fetch_abs(use_cache=False)
