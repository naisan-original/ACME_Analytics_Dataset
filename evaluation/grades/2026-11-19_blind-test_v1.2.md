# Scorecard: blind test of dataset v1.2

Rubric:            v1.2 (9 signals)
Output:            report.html (17 charts) and findings.md (71 claims) from a blind run by a Claude Opus 5.5 general-purpose agent, 2026-11-19. Not published
Dataset version:   v1.2
Prompt:            the rubric's test prompt, word for word, with only the dataset folder (no semantic/)
Skills answer:     Loaded data:explore-data, data:analyze and dataviz. Said dataviz's palette files and validator sat outside the allowed folder, so it wrote a stand-in colour-vision checker. Noted that artifact-design didn't apply because publishing was ruled out
Proxy for segment: firmographic (High Tech + any AI tag in tech_signals), plus a behavioural API-share cut shown in any industry
Signals evidenced: 1 API share 11% → 68%, 2 active humans −40%, 3 utilisation 44% → 21%, 4 work +70% with ARR flat, 5 Service Accounts 63% of work, 7 notes theme and sentiment, 8 a 12-month lead (48% API share and 12% utilisation at the prior renewal). Missing: 6 product split, 9 size gradient

| Attribute                  | Weight | Score | Note |
|----------------------------|--------|-------|------|
| 1. Root cause              | 25     | 24    | Segment, seat-pricing mechanism and healthy rest (123% NDR, 93% GRR) all stated. −1: segment by AI tags is loose (65% precision), so segment NDR is diluted to 68% against a true 47% |
| 2. Evidence depth          | 15     | 12    | 7 of 9 signals |
| 3. Red herrings            | 15     | 15    | EMEA: dip in new ARR, budget-freeze notes and recovery, all with numbers. Turnover: reassigned accounts compared with peers, and it found no retention harm |
| 4. Numerical accuracy      | 15     | 15    | GRR/NDR FY22-FY26, ARR, customers and FY26 churn all match the key exactly |
| 5. Rigor and honesty       | 10     | 9     | Method for all 71 claims, what-ifs labeled, land-size cause left as an open question. −1: the "work +70%, ARR flat" index is over paying customers, so survivors and new lands are mixed in (partly flagged) |
| 6. Actionability           | 10     | 9     | Usage pricing for machine traffic, a save programme triggered by API share and utilisation, health score on usage mix, gap sized at $49.7M. Thresholds implied by the buckets rather than stated as a rule |
| 7. Communication           | 10     | 9     | Answer first, 17 inline charts with tables, light and dark themes. Missing the sentiment-before-contraction chart (it reported that sentiment hid the risk instead) |
| Total (after caps)         | 100    | 93    | Excellent |

What the test says about the dataset:
- **The segment is no longer one column away.** The analyst never used sub-industry. It reached the answer through behaviour and an imperfect enrichment tag.
- **The size gradient went unnoticed, which is the intended subtlety.** The analyst didn't slice by revenue band, so this is a discovery that separates excellent answers.
- **The FY26 land-size step is very visible.** Median land fell from 24 to 11 seats overnight on 1 Nov 2025, because `land_acv_scale` steps from 0.78 to 0.41 at the fiscal-year boundary. The analyst treated it as a second cause and a suspected policy change. It was a tuning artifact. Fixed in v1.3: land size now changes month by month, with no step at the year boundary.
- **The rep-turnover red herring may be too faint.** Reassigned NA accounts retained better than peers (119% vs 115% NDR), so the herring isn't tempting. Fixed in v1.3: reassigned accounts now retain visibly worse for about a year (FY25 NDR 109.8% vs 120.3% outside High Tech).
- **The README row-count mismatch it flagged was a test-setup error.** The test folder was copied before the counts were updated, and the release zip is correct.
