# Evaluation kit (spoilers)

> **This folder gives away the answer.** It is kept out of the dataset folder and out of the dataset zip on purpose. Don't upload it to the analyst or tool you're testing.

| Path | What it is |
|---|---|
| [`grading_rubric.md`](grading_rubric.md) | The standard test prompt, 7 weighted scoring attributes with anchors, caps and a scorecard template |
| [`answer_key.md`](answer_key.md) | The hidden story, the discovery path, red herrings, traps and expected answers, with every number taken from the generated data |
| [`truth/segment_truth.csv`](truth/) | The hidden label: `account_id` and `is_ai_forward` (0 or 1) for all 15,000 accounts |
| [`truth/pivot_truth.csv`](truth/) | For each AI-forward account, the month its shift from seats to API starts (`onset_month`, 0 = Nov 2020) and how many months it takes (`pivot_months`) |
| [`truth/fictional_accounts.csv`](truth/) | Which company names were invented to fill the account list |
| [`grades/`](grades/) | Scorecards of graded outputs, as worked examples of the rubric |

To test an analytics tool:

1. Give it only the dataset: `output/lite/*.csv` and `output/data_dictionary.md`, or the dataset zip from Releases.
2. Paste the test prompt from the rubric, word for word.
3. Score the result with the rubric. Check numbers against the answer key, and use `truth/segment_truth.csv` to check exactly which accounts an analyst's segment caught.

`generate.py` writes `truth/` with every build, and `uv run python tools/answer_key.py` rewrites the answer key, so both always match the data in the same release.
