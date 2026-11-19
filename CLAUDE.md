# Project rules

- `ACME_DATASET_SPEC.md` is the source of truth. Follow its build order (Section 11).
- This repository is public. Never commit `output/`, credentials, or client information.
- `evaluation/` (answer key, grading rubric, hidden-label CSVs in `truth/`, scorecards in `grades/`) is committed and published on purpose, as a spoiler kit. Keep it at the repo root, never inside `output/`, `semantic/` or the dataset zip, so uploading the data folder never carries the answers. Ship it as its own release asset.
- Keep hidden labels out of the dataset. Before finishing a build, grep `output/` for `ai_forward` and `segment_truth`. The label files live only in `evaluation/truth/`. Scorecards in `evaluation/grades/` are public: no private file paths or client details.
- Output must be deterministic: every random draw comes from the global seed in `config.yaml`.
- Run Python through `uv run`, not the system `python3`.
