"""Fetch and cache public company lists. Run manually; generate.py only reads the cache.

Usage: uv run python sources/fetch_sources.py [resume_offset]
"""
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "ACME-synthetic-dataset-builder/0.1 (research script)"
PAGE = 10000
# Wikidata limits this endpoint to 1 request per minute during outages. Stay under that.
REQUEST_GAP_SECONDS = 70
OUT = Path(__file__).parent / "wikidata_listed_companies.csv"

QUERY = """
SELECT ?c ?cLabel ?countryLabel ?industryLabel ?hqLabel ?rev WHERE {{
  ?c wdt:P414 ?ex .
  OPTIONAL {{ ?c wdt:P17 ?country }}
  OPTIONAL {{ ?c wdt:P452 ?industry }}
  OPTIONAL {{ ?c wdt:P159 ?hq }}
  OPTIONAL {{ ?c wdt:P2139 ?rev }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}} LIMIT {limit} OFFSET {offset}
"""


def fetch_page(offset):
    query = QUERY.format(limit=PAGE, offset=offset)
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query})
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=70) as response:
                # strict=False: some Wikidata labels contain raw control characters.
                return json.loads(response.read().decode("utf-8"), strict=False)["results"]["bindings"]
        except urllib.error.HTTPError as error:
            wait = int(error.headers.get("Retry-After") or 0) + REQUEST_GAP_SECONDS * (attempt + 1)
            print(f"offset {offset} attempt {attempt + 1}: HTTP {error.code}, waiting {wait}s", flush=True)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            print(f"offset {offset} attempt {attempt + 1}: {error}", flush=True)
            time.sleep(REQUEST_GAP_SECONDS * (attempt + 1))
    return None


def value(row, key):
    return row.get(key, {}).get("value", "")


def save(companies):
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["qid", "name", "country", "industry", "hq_city", "revenue"])
        writer.writeheader()
        writer.writerows(sorted(companies.values(), key=lambda c: int(c["qid"][1:])))


def load_cache():
    if not OUT.exists():
        return {}
    with OUT.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["revenue"] = float(row["revenue"] or 0)
    return {row["qid"]: row for row in rows}


def main():
    # Pass a starting offset to resume; companies already cached are kept.
    offset = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    companies = load_cache() if offset else {}
    while True:
        rows = fetch_page(offset)
        if rows is None:
            print(f"stopping at offset {offset}; keeping {len(companies)} companies", flush=True)
            break
        print(f"offset {offset}: {len(rows)} rows, {len(companies)} companies so far", flush=True)
        for row in rows:
            qid = value(row, "c").rsplit("/", 1)[-1]
            name = value(row, "cLabel")
            if name == qid:  # no English label
                continue
            entry = companies.setdefault(
                qid,
                {"qid": qid, "name": name, "country": "", "industry": "", "hq_city": "", "revenue": 0.0},
            )
            entry["country"] = entry["country"] or value(row, "countryLabel")
            entry["industry"] = entry["industry"] or value(row, "industryLabel")
            entry["hq_city"] = entry["hq_city"] or value(row, "hqLabel")
            try:
                entry["revenue"] = max(entry["revenue"], float(value(row, "rev") or 0))
            except ValueError:
                pass
        save(companies)
        if len(rows) < PAGE:
            break
        offset += PAGE
        time.sleep(REQUEST_GAP_SECONDS)

    save(companies)
    print(f"wrote {len(companies)} companies to {OUT}", flush=True)


if __name__ == "__main__":
    main()
