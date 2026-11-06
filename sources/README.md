# Source lists

Cached public company lists used to name accounts. `generate.py` reads these files and never goes
to the network, so a re-run gives identical output.

| File | Source | License | Script |
|---|---|---|---|
| `wikidata_listed_companies.csv` | [Wikidata](https://query.wikidata.org/): entities with a stock exchange listing (P414), plus country, industry, headquarters and revenue where present | CC0 | `fetch_sources.py` |
| `us_listed_companies.csv` | [datasets/nasdaq-listings](https://github.com/datasets/nasdaq-listings) and [datasets/nyse-other-listings](https://github.com/datasets/nyse-other-listings), with funds, debt and derivative securities removed | ODC-PDDL-1.0 | `fetch_us_listings.py` |

Fetched 2026-11-06.

## Notes

- Wikidata was rate-limiting this endpoint during an outage when these lists were fetched, so the
  Wikidata file holds only the first page of results (5,894 companies). To extend it, run
  `uv run python sources/fetch_sources.py 10000`, then retune and regenerate. As a result, about 40%
  of accounts have fictional names.
- SEC EDGAR was not used. It requires a contact email in automated requests.
- Fortune and Forbes lists are not cached here. `fortune_rank` and `global2000_rank` are approximate
  ranks derived from the Wikidata revenue figures, not the published rankings.
- Wikidata revenue figures are not currency-normalized. They are used only to order companies into
  bands. No revenue figure appears in the dataset.
- When real names run out, the remainder are fictional names in the lowest revenue band. They are
  listed only in `facilitator/fictional_accounts.csv`.
