"""Fetch and clean US exchange listings. Run manually; generate.py only reads the cache.

Source: github.com/datasets (nasdaq-listings, nyse-other-listings), ODC-PDDL-1.0.
Usage: uv run python sources/fetch_us_listings.py
"""
import csv
import io
import re
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/datasets"
URLS = [
    f"{BASE}/nasdaq-listings/main/data/nasdaq-listed.csv",
    f"{BASE}/nyse-other-listings/main/data/nyse-listed.csv",
    f"{BASE}/nyse-other-listings/main/data/other-listed.csv",
]
OUT = Path(__file__).parent / "us_listed_companies.csv"

# Funds, debt and derivative securities rather than operating companies.
EXCLUDE = re.compile(
    r"\b(etf|etn|fund|trust|warrants?|rights?|units?|notes?|debentures?|preferred|depositary|depository|"
    r"bond|acquisition|spac|index|shares of beneficial|ishares|proshares|invesco|vanguard|spdr|wisdomtree)\b",
    re.IGNORECASE,
)
SHARE_SUFFIX = re.compile(
    r"\s*[-,]?\s*(class [a-z] )?(common stock|ordinary shares?|common shares?|capital stock|"
    r"american depositary.*|new\b.*)\s*$",
    re.IGNORECASE,
)


def read(url):
    request = urllib.request.Request(url, headers={"User-Agent": "ACME-synthetic-dataset-builder/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return list(csv.DictReader(io.StringIO(response.read().decode("utf-8", "replace"))))


def clean(name):
    name = name.split(" - ")[0]
    return " ".join(SHARE_SUFFIX.sub("", name).split()).strip(" ,.-")


def main():
    names = {}
    for url in URLS:
        rows = read(url)
        print(url.rsplit("/", 1)[-1], len(rows), list(rows[0])[:3], flush=True)
        for row in rows:
            raw = row.get("Company Name") or row.get("Security Name") or ""
            if not raw or EXCLUDE.search(raw):
                continue
            name = clean(raw)
            if len(name) >= 3:
                names.setdefault(name.lower(), name)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["qid", "name", "country", "industry", "hq_city", "revenue"])
        for name in sorted(names.values()):
            writer.writerow(["", name, "United States", "", "", 0])
    print(f"wrote {len(names)} companies to {OUT}", flush=True)


if __name__ == "__main__":
    main()
