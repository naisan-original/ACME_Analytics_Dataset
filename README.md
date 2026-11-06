# ACME Analytics Synthetic Dataset

A seeded, config-driven Python generator for a star-schema dataset about a fictional enterprise
data and analytics vendor, "ACME Analytics." It exists for exercising analytics tools.

> All commercial relationships, usage, and notes are fictional. Company names are used for realism only.

The build spec is [ACME_DATASET_SPEC.md](ACME_DATASET_SPEC.md).

## Status

The generator is complete. `validate.py` passes 61 of 62 checks. The one miss is FY23 NDR, 0.2 points
outside its tolerance. It exits non-zero until that is resolved.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

    uv sync
    uv run python generate.py --config config.yaml
    uv run python validate.py

Generated CSVs are written to `output/lite/`. They are not stored in Git. The same seed and
config produce identical output.

`tools/tune.py` searches config values toward the KPI targets, and `tools/answer_key.py` writes the
facilitator key from the generated data.

## Loading the data

- `region` uses the value `NA` for North America, as the spec requires. Many tools, including pandas
  by default, read `NA` as null, so check this on import.
- `fct_account_product_month` is the central table. Every other table joins directly to it.
- `user_usage_month` is a sample. Use `sample_weight` to estimate population totals.
