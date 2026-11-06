# Project rules

- `ACME_DATASET_SPEC.md` is the source of truth. Follow its build order (Section 11).
- This repository is public. Never commit `output/`, `facilitator/`, credentials, or client information.
- Keep hidden labels out of the dataset. Before finishing a build, grep `output/` for `ai_forward` and `segment_truth`.
- Output must be deterministic: every random draw comes from the global seed in `config.yaml`.
- Run Python through `uv run`, not the system `python3`.
