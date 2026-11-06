# ACME Analytics Synthetic Dataset

A seeded, config-driven Python generator for a star-schema dataset about a fictional enterprise
data and analytics vendor, "ACME Analytics." It exists for exercising analytics tools.

> All commercial relationships, usage, and notes are fictional. Company names are used for realism only.

The build spec is [ACME_DATASET_SPEC.md](ACME_DATASET_SPEC.md).

## Status

Under construction. See the spec, Section 11, for the build order.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

    uv sync
    uv run python generate.py --config config.yaml
    uv run python validate.py

Generated CSVs are written to `output/lite/`. They are not stored in Git. The same seed and
config produce identical output.
