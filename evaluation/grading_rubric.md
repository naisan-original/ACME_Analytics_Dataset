# ACME Analytics: grading rubric for analysis outputs

> **Spoiler.** This folder gives away the answer the dataset was built to hide. It sits outside the dataset folder on purpose: don't upload it, or [`answer_key.md`](answer_key.md), to the analyst or tool you're testing.

Use this rubric to score any analysis of the ACME dataset, whether it comes from a human analyst, an AI agent or a BI tool, against what the generator engineered. Score the output as submitted, and don't give credit for what the author probably meant.

Rubric version 1.2, for dataset v1.2. Reference numbers live in [`answer_key.md`](answer_key.md), which is regenerated from the data with every build. Where this rubric and the key disagree, the key wins.

## Test prompt

To compare outputs fairly, give every analyst or tool the same prompt, word for word, with only the dataset folder (`output/lite/` and `data_dictionary.md`, or the release zip). Optionally add `semantic/`. Never add this folder.

```text
I want you to research this dataset and help me find why this company isn't performing as well as it should, then help me communicate this in a series of beautifully designed graphs and analytics. First, do you have all the skills recommended to do this work loaded?
```

Record in the scorecard what the tool answered to the opening question about skills: which skills it said it had, loaded or was missing, and whether it went on to use them. That answer isn't scored, but it explains differences between tools and setups.

## Engineered truth (what a perfect answer finds)

| Element | Truth |
|---|---|
| Symptom | ARR keeps growing, but GRR and NDR fall from FY24 to FY26 |
| Root cause segment | AI-forward High Tech customers. Membership is a weighted random draw: most likely in Software, Internet & Platforms and Semiconductors, less likely in Hardware and IT Services, and less likely the larger the company. No column identifies it |
| Mechanism | Work moves from people in the UI to agents on the API. Pricing is per seat and API calls use no seats, so seats and then ARR fall while activity rises |
| Size gradient | Smaller companies adopt first: they pivot earlier and faster and churn first. Large companies are only starting by FY26, so the damage is still spreading |
| Healthy core | Without the segment, GRR stays at about 92% and NDR above 120% |
| Red herring 1 | EMEA soft patch in FY25 Q1-Q3: fewer new logos and a contraction bump that recovers in FY26 once High Tech is excluded |
| Red herring 2 | US-West rep turnover in FY25: reassigned accounts get fewer touches and churn slightly more, but it explains only a small part of the decline |
| Trap | `contracts.outcome` is set when a contract ends. Grouping churn by contract start year shows no FY26 churn, but FY26 has the most churn of any year |

Engineered signals (used in attribute 2):

1. API share or API calls rising in the segment (≈5% → 90%+)
2. UI active users or sessions falling (70-80%)
3. Seat compression or seat utilization falling
4. Activity rising while ARR falls (the divergence)
5. Service Account users appearing (`user_usage_month.user_persona`)
6. Product mix: the Analytics UI collapses while Data Engine work rises 2-3x
7. Touchpoint drift: sentiment falls, Risk touches rise, notes mention agents, API or seat pricing
8. Timing: contraction before churn, or a stated lead time from the API shift to the revenue loss
9. Size gradient: smaller High Tech companies hit first and hardest, larger ones later

## Proxies an analyst may use

- **Sub-industry is a strong clue, not a label.** About 70% of customers in the three core sub-industries are in the segment, and they hold most of it. Some Hardware and IT Services customers are in it too. An answer that defines the segment by sub-industry alone will be roughly right and will misclassify a visible minority. Credit it on attribute 1, and use attribute 5 to deduct if the misclassification inflates a stated number.
- **AI tags in `tech_signals` are a weaker clue.** Nearly every High Tech account has at least one AI tag, so "High Tech with any AI tag" is only about 65% in the segment. Two or more tags is about 75%, roughly as strong as sub-industry. Treat it like a sub-industry definition.
- **Behavioural definitions are better.** For example, High Tech with API share above 20-50%, or falling seat utilization with rising API calls. Record which proxy the output used.
- **Real patterns that aren't the story.** Don't penalize an output for finding these, but it must not blame them for the retention decline:
  - New-customer land size falls in FY26 (generator tuning).
  - Seat utilization predicts renewal across all customers (built into the healthy renewal model).
  - API share in the rest of the base drifts up gently by design (about 3% → 13%). This is not a second pivot.

## Attributes and weights (100 points)

### 1. Root cause identification (25)

| Points | Anchor |
|---|---|
| 23-25 | Names the segment (AI-forward or API-heavy High Tech, by sub-industry or behaviour), states the seat-pricing mechanism, and quantifies that the rest of the base is healthy |
| 17-22 | Segment and mechanism correct, but the healthy core isn't quantified, or the segment is loose (all of High Tech) |
| 10-16 | Finds High Tech or API share as the locus but misses or garbles the mechanism |
| 4-9 | Notes the decline and a partial correlate (industry, product) with no causal story |
| 0-3 | Wrong root cause, or describes the symptom only |

### 2. Evidence and mechanism depth (15)

Points = round(15 × signals evidenced ÷ 9), using the 9 engineered signals above. A signal counts only if the output shows data for it, as a number or a chart. Asserting it isn't enough.

### 3. Red herring handling (15, 7.5 per herring)

| Points per herring | Anchor |
|---|---|
| 7.5 | Tested explicitly and shown with numbers to be minor or temporary |
| 5 | Mentioned and dismissed qualitatively |
| 3 | Not mentioned, and not blamed |
| 1 | Offered as a contributing cause without testing |
| 0 | Presented as a main cause |

### 4. Numerical accuracy (15)

Check up to 10 headline figures the output states against the answer key or a direct query: FY26 ARR, GRR and NDR, an earlier year's GRR or NDR, segment size, segment retention, core retention, churn. Each must be within 0.5 points for rates and 2% for amounts, or come with a stated definition that explains the gap.

| Points | Anchor |
|---|---|
| 15 | All checked figures correct |
| 11-14 | One or two errors that don't change conclusions |
| 6-10 | Several errors, or one that changes a conclusion |
| 0-5 | Headline numbers wrong |

### 5. Analytical rigor and honesty (10)

Start at 10. Deduct per issue:
- −2 for each material claim the data doesn't support (verify by query)
- −2 for a censoring error, such as grouping contract outcomes by start year and concluding that recent churn is zero or can't be assessed
- −1 for each segment or cohort definition that misclassifies a material group and inflates a stated number
- −1 if counterfactuals or estimates aren't labeled as such
- −1 if method or definitions aren't visible to the reader
- −1 if survivorship or mix effects matter to a stated trend and aren't addressed

### 6. Actionability (10)

| Points | Anchor |
|---|---|
| 9-10 | Fixes the cause (usage- or work-based pricing for API-heavy accounts), gives an early-warning rule with thresholds, and sizes what's at stake |
| 6-8 | Right direction but generic, or missing the warning rule or the sizing |
| 3-5 | Actions aimed at symptoms (more CSM coverage, discounts, EMEA fixes) |
| 0-2 | No actions, or actions that would make things worse |

### 7. Communication and deliverable quality (10)

| Points | Anchor |
|---|---|
| 9-10 | Answer first, a logical sequence, charts that match the "Charts to expect" list in `answer_key.md`, readable and searchable in its delivered form |
| 6-8 | Clear story with format problems (unreadable export, missing labels, hidden method), or one important chart missing |
| 3-5 | Correct content that's hard to follow |
| 0-2 | Data dump or unreadable |

## Caps

Apply these after summing:
- Root cause blamed on a red herring (score 0 on either herring): total capped at 40.
- FY26 GRR or NDR misstated by more than 3 points: total capped at 60.

## Grading procedure

1. Read the whole output. If it's an image-only PDF, render it at high zoom (for example with `pymupdf`) and read every section.
2. List each quantitative claim. Check the headline numbers against `answer_key.md`, and query the CSVs (DuckDB works well) for any claim beyond the key.
3. Fill in the scorecard below. Keep scorecards for outputs you don't want to publish outside the repo, or in the git-ignored `facilitator/` folder.

## Scorecard template

```text
Output:            <file, author/tool, model, date>
Dataset version:   <v1.2>
Prompt:            <the test prompt above, or what was used instead>
Skills answer:     <what it said about skills, and whether it loaded or used them>
Proxy for segment: behavioural (API share) | firmographic (sub-industry) | both | none
Signals evidenced: <which of the 9>

| Attribute                  | Weight | Score | Note |
|----------------------------|--------|-------|------|
| 1. Root cause              | 25     |       |      |
| 2. Evidence depth          | 15     |       |      |
| 3. Red herrings            | 15     |       |      |
| 4. Numerical accuracy      | 15     |       |      |
| 5. Rigor and honesty       | 10     |       |      |
| 6. Actionability           | 10     |       |      |
| 7. Communication           | 10     |       |      |
| Total (after caps)         | 100    |       |      |

Grade bands: 85+ excellent, 70-84 strong, 55-69 partial, 40-54 weak, under 40 missed it.
```
