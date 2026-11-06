# ACME Analytics Synthetic Dataset: Build Spec

Build a seeded, config-driven Python generator that produces a star-schema dataset for a fictional enterprise data/analytics vendor, "ACME Analytics." The dataset is used for analytics-tool exercises. Its purpose: an analyst notices GRR/NDR deteriorating in the last two fiscal years, investigates, and discovers that an AI-forward High Tech customer segment has shifted from UI usage to API usage, compressed seats, and churned.

The pattern must be discoverable but not obvious. Never encode the answer in a single column.

---

## 0. Locked decisions

| Decision | Value |
|---|---|
| Account base | ~15,000 accounts in dim_account; ~4,500 paying customers by end; remainder prospects (some with touchpoints, none with revenue) |
| Output | **Lite only**: CSV files, total ≤ ~4M rows across all tables, every file loadable by a desktop BI tool |
| Difficulty | Moderate, with 2 red herrings (Section 7) |
| Window | Nov 2020 through Oct 2026, 72 months. Fiscal year ends Oct 31 (FY21 through FY26) |
| Determinism | Single global seed in config; identical output on re-run |
| Language | Python 3.11+, pandas/numpy, pyyaml. No paid APIs |

---

## 1. Repo layout

```
acme-dataset/
  config.yaml            # every tunable parameter below
  generate.py            # entry point: python generate.py --config config.yaml
  acme/                  # modules: accounts.py, products.py, people.py, simulate.py, usage.py, contracts.py, touchpoints.py, export.py
  validate.py            # prints KPI tables, asserts targets (Section 9)
  sources/               # cached raw company lists + README noting source/URL/date
  output/lite/*.csv
  output/data_dictionary.md
  facilitator/answer_key.md   # NOT part of the dataset; hidden truth + walkthrough
  facilitator/segment_truth.csv  # account_id, is_ai_forward (hidden label)
```

---

## 2. Star schema (central fact + 7 satellites, every satellite one join from the center)

### 2.1 fct_account_product_month (CENTRAL)
Grain: account × product × month, rows only while the account holds an active subscription to that product (plus the churn month with arr = 0, churn_flag = 1).

| Column | Notes |
|---|---|
| month_id (FK dim_month), account_id (FK), product_id (FK) | |
| ae_employee_id, csm_employee_id (FK dim_employee) | owner as of that month; can change on reassignment/turnover |
| licensed_seats | contracted seats |
| list_price_per_seat_month, net_price_per_seat_month | net reflects volume discount (Section 5) |
| mrr, arr | arr = mrr × 12 |
| active_users | distinct users with ≥1 UI session in month |
| ui_sessions, ui_hours | from population simulation |
| api_calls | monthly API request count (proxy for AI/agent access) |
| work_units | product-specific: transformations run / dashboards viewed+built / compute credits / models trained |
| api_share | api_calls converted to equivalent work units ÷ total work units, 0–1 |
| renewal_month_flag | 1 in the contract anniversary month |
| arr_change_type | none / new / expansion / contraction / churn (at the movement month) |

### 2.2 dim_account (~15,000)
account_id, account_name (real company), hq_country, hq_city, region (NA / EMEA / APAC / LATAM), industry, sub_industry, annual_revenue_band, employee_band, fortune_rank (nullable), global2000_rank (nullable), segment (Strategic / Enterprise / Upper Mid-Market), account_status (Customer / Former Customer / Prospect), customer_since_month_id (nullable), churn_month_id (nullable), tech_signals (a semicolon list of marketing-enrichment style topics, e.g. "Snowflake;dbt;Kubernetes;LLM Ops;Vector DB"). AI-forward accounts skew toward AI-related topics, but **other High Tech and some non-tech accounts have them too**. This is a soft clue, not a label.

**Do NOT include** is_ai_forward or anything equivalent. That lives only in facilitator/segment_truth.csv.

### 2.3 dim_product (4)
| product_id | product_name | work_unit_label | price_multiplier (vs $30 base) |
|---|---|---|---|
| P1 | ACME Data Transformation | transformation_runs | 1.0 |
| P2 | ACME Analytics | dashboards_and_queries | 1.0 |
| P3 | ACME Data Engine | compute_credits | 1.2 |
| P4 | ACME Machine Learning | model_runs | 1.4 |

All products are **seat-priced**. API calls do not consume seats. This drives the key clue: activity rises while ARR falls.

### 2.4 dim_month (72)
month_id (YYYYMM), month_start_date, fiscal_year (FY21–FY26), fiscal_quarter, calendar_year, calendar_quarter.

### 2.5 dim_employee (~150 incl. turnover)
employee_id, name (fictional), role (AE / CSM / Sales Leader / CS Leader), region, hire_month_id, termination_month_id (nullable), quota_arr (AEs only, nullable otherwise).
Headcount ramp (active at FY end): AEs 3 → 6 → 12 → 22 → 38 → 55; CSMs 2 → 4 → 9 → 18 → 32 → 50; 2–3 leaders appear as the org scales. Annual attrition ~12–15% with backfills. Goal: users can compute ARR per CSM, new ARR per AE, accounts per CSM, and see efficiency drift.

### 2.6 user_usage_month (Lite target ≤ 2.5M rows)
Grain: user × product × month, rows only when the user has any activity that month.
Columns: user_id, account_id, product_id, month_id, user_department (Analytics / Finance / Ops / Sales / Marketing / Engineering / Data Eng / Exec), user_persona (Viewer / Explorer / Creator / Admin / Service Account), ui_sessions, ui_hours, api_calls, work_units, sample_weight.
Lite approach: simulate the **full** user population in memory (central fact aggregates come from the full population), then export a stratified sample of users per account (every customer account represented; keep 100% of users with ≥ 40 hrs/month and 100% of Service Account users). Write sample_weight so weighted sums approximate the central fact within ±5%. Document this in the dictionary.
**Service Account users** (persona = Service Account, department = Data Eng/Engineering) carry most API calls. Their rise inside AI-forward accounts is a strong user-level clue.

### 2.7 contracts (~20–25K)
contract_id, account_id, product_id, contract_type (New / Renewal / Expansion Add-on), start_month_id, end_month_id, term_months (12 standard; ~10% of Strategic are 24 or 36), seats, net_price_per_seat_month, acv, outcome (Renewed Flat / Renewed Up / Renewed Down / Churned / Active), ae_employee_id.
Must reconcile to the central fact: sum of active contract ACV by account-product-month = central arr (± rounding).

### 2.8 touchpoints (~100–150K)
touchpoint_id, account_id, employee_id, month_id, touch_date, channel (Call / Email / QBR / Onsite / Support Escalation), touch_type (Discovery / Onboarding / Check-in / QBR / Renewal / Expansion / Risk), sentiment (-2 to +2), notes (1–3 sentences, templated with variation; use phrase banks with 30+ variants per theme so text-search is useful but not trivially uniform).
Cadence: customers ~4–10 touches/yr scaling with ARR; prospects 0–3/yr from AEs.
Note themes drift over time (Section 6.4).

---

## 3. Account universe (real companies)

Source real company names from public lists, cached in /sources with provenance:
- Fortune 500 / Fortune 1000 (US), Forbes Global 2000, Wikipedia "List of largest companies by revenue" and per-country lists, SEC EDGAR company_tickers.json for US mid-caps, major exchange constituents (Russell 1000/2000, STOXX 600, FTSE 350, Nikkei 225, ASX 200, TSX, etc.).

Rules:
- Revenue floor ~$200–300M. Size distribution is a long tail: ~500 in $50B+, ~1,500 in $10–50B, ~3,500 in $2–10B, ~9,500 in $200M–2B.
- 60% US HQ / 40% rest of world (EMEA ~22%, APAC ~14%, LATAM ~4%).
- Revenue figures are **bands**, not reported numbers.
- If real lists can't reach 15K after dedupe, fill the remainder with plausible fictional names in the lowest band and flag them in facilitator files only.
- Industry taxonomy (~10 industries, ~40 sub-industries): High Tech (Software, Internet & Platforms, Semiconductors, IT Services, Hardware), Financial Services, Healthcare & Life Sciences, Retail & CPG, Manufacturing, Energy & Utilities, Telecom & Media, Transportation & Logistics, Public Sector & Education, Professional Services.
- High Tech should be ~20–22% of customers by count and ~28–30% of ARR by FY24.

Add a header row to the dictionary and a `synthetic_notice` line: "All commercial relationships, usage, and notes are fictional. Company names are used for realism only."

---

## 4. Growth and customer acquisition

- Customers: ~25 at FY21 start; FY-end counts ≈ 120 / 450 / 1,200 / 2,400 / 3,600 / ~4,500 (net of churn).
- New logo ACV distribution log-normal, skewed by segment: Strategic land $150K–1M, Enterprise $40–200K, Upper MM $15–60K.
- Land usually with 1–2 products (Analytics most common, then Transformation); expand into Data Engine and ML over time.
- Ending total ARR target: ~$350–450M (FY26).
- Early adopters skew High Tech (tech buys first), so High Tech is overrepresented in FY21–FY23 cohorts and in the largest accounts.

---

## 5. Pricing

Net price per seat per month by product-level seat count, then × product price_multiplier, with ±10% deal noise:

| Seats | Base net $/seat/month |
|---|---|
| < 50 | 80–100 |
| 50–249 | 45–60 |
| 250–999 | 28–35 (center of mass ≈ $30) |
| 1,000–4,999 | 20–25 |
| 5,000+ | 15–18 |

Price set at contract start; renewals carry 0–5% uplift when healthy, and a 5–15% discount when at-risk.

---

## 6. Behavior simulation

### 6.1 Seats and usage population (all accounts)
- Each account-product has a seat pool. Per-user monthly hours ~ log-normal, calibrated so ~5–10% of seats are weekly active, ~25–35% monthly active, and <1% are near full-time (≥ 120 hrs/month).
- Seat utilization (monthly active ÷ seats) drives renewal: utilization ≥ 35% → likely expansion; 20–35% → flat; < 20% → contraction or churn risk.
- **Baseline API drift (everyone):** api_share rises from ~3% (FY21) to ~10–15% (FY26) across the whole base, so API growth alone does not isolate the problem.

### 6.2 Healthy population targets
- Overall logo churn ~5–6%/yr; separate contraction cohort ~5–6% of customers/yr with seat cuts of 10–40%.
- Strong growers: top ~15% of accounts expand 30–100%+/yr in years 2–4.

### 6.3 Hidden AI-forward segment (the nugget)
- ~600–700 customers (≈ 12–15% of customers, ≈ 20–25% of FY24 ARR). All in High Tech, concentrated in Software, Internet & Platforms, and Semiconductors. Not every High Tech account is AI-forward (keep ~35–40% of High Tech normal so "High Tech" alone is a partial signal).
- **FY21–FY24:** best customers in the base. High utilization (40–60%), heavy Analytics UI use, fast expansion. They inflate early NDR.
- **Pivot onset:** staggered per account, drawn from Q3 FY24 through Q2 FY26 (an S-curve, not a cliff).
- **After onset (per account, over 6–18 months):**
  - api_share: ~5% → ~60% → 90%+.
  - Service Account users appear and grow. Human Creator and Explorer users decline.
  - ACME Analytics: UI sessions and active users fall 70–80%, then seats contract, then the product churns first.
  - ACME Data Engine: compute work units rise 2–3x (agents query it directly), but seats stay flat or fall, so ARR does not follow activity.
  - Transformation stays roughly flat, then contracts. ML is mixed.
  - Logo churn 6–12 months after api_share passes ~80%.
- **Segment churn:** ~3%/yr through FY24 → ~25–35%/yr in FY25–FY26. Contraction precedes churn, so GRR falls before logo counts do.

### 6.4 Touchpoint language drift
- Generic themes for everyone: onboarding, adoption, QBR, renewal, budget, champion change, support issues.
- AI-forward accounts after onset, increasing in frequency: building an internal copilot, agents querying the Data Engine directly, fewer analysts logging in, consolidating seats, "most consumption is now programmatic," evaluating LLM-native analytics, renewal at reduced seats. Phrase these many ways and also seed ~5% of non-AI accounts with similar phrases, so text search gives evidence, not proof.
- CSM sentiment for the segment trends from +1/+2 to 0/−1 about two quarters before contraction.

---

## 7. Red herrings (moderate difficulty)

1. **EMEA soft patch:** FY25 Q1–Q3, EMEA new-logo bookings −20% and a small contraction bump (macro/budget notes: "budget freeze," "procurement delay"). It recovers by FY26 and explains only a small slice of the GRR drop.
2. **Rep turnover:** in FY25, 4–5 AEs and 3 CSMs in US-West leave within two quarters. Their accounts get reassigned (owner change visible in the central fact) and show a temporary dip in touch frequency and a modest churn bump. It's a plausible but incomplete explanation.

Both should be findable and should fail to explain most of the GRR/NDR deterioration once the analyst controls for industry and API share.

---

## 8. Top-line KPI targets (computed on the central fact, trailing 12 months at FY end)

| FY | Customers (end) | ARR (end) | GRR | NDR |
|---|---|---|---|---|
| FY21 | ~120 | ~$8–12M | ~94% | ~135% |
| FY22 | ~450 | ~$35–45M | ~93% | ~130% |
| FY23 | ~1,200 | ~$100–130M | ~93% | ~126% |
| FY24 | ~2,400 | ~$200–250M | ~91% | ~120% |
| FY25 | ~3,600 | ~$290–350M | ~87% | ~110% |
| FY26 | ~4,500 | ~$350–450M | ~84–86% | ~104–107% |

Definitions:
- GRR = (ARR from accounts active 12 months ago − churned − contracted) ÷ their ARR 12 months ago, capped at 100%.
- NDR = same cohort including expansion.

Segment check: excluding the AI-forward segment, FY25–FY26 GRR should stay ≥ ~91% and NDR ≥ ~115%. This is the "aha" for the analyst.

Real-world analog for narrative realism: Snowflake's reported NRR fell from 178% (FY22) to 126% (FY25).

---

## 9. Validation (validate.py must print and assert)

1. KPI table above, overall and split by AI-forward vs. rest (using the hidden label), with each target inside ±2 pts.
2. Reconciliation: contracts ACV vs. central ARR by month (≤ 0.5% gap); weighted user_usage vs. central usage (≤ 5% gap).
3. Distribution checks: weekly-active share 5–10%; near-full-time < 1%; price-per-seat median $28–33.
4. US/RoW split 60/40 ±2%; no duplicate account names; no account below the revenue floor.
5. Headcount ramp matches Section 2.5 at FY ends.
6. Discoverability smoke test, run without the hidden label:
   - (a) GRR by industry shows High Tech worst in FY25–26.
   - (b) Within High Tech, accounts with FY26 api_share > 50% have ≥ 3x the churn rate of the rest.
   - (c) Neither red herring alone explains > 30% of the FY24→FY26 GRR decline.
7. Row counts per table, and total CSV size. Target: total ≤ ~4M rows, ≤ ~400MB.

---

## 10. Facilitator answer key (facilitator/answer_key.md)

Include:
- The story in five sentences.
- The hidden segment definition.
- The suggested discovery path:
  1. Top-line ARR is still growing.
  2. GRR/NDR are falling.
  3. Slice by region: EMEA is a red herring.
  4. Slice by owner: turnover is a red herring.
  5. Slice by industry: High Tech stands out.
  6. Look at product mix: Analytics is falling.
  7. Look at API share and Service Account users.
  8. Read the touchpoint notes.
  9. Seat compression explains it.
- 6–8 example questions with expected answers (numbers from the actual generated output).
- Charts the facilitator should expect to see.

---

## 11. Build order for Claude Code

1. Scaffold the repo and config.yaml with every parameter above.
2. Build the account universe from public sources; cache the raw lists; print the size and region distribution.
3. Run the population and contract simulation at account-product-month level.
4. Run the user-level simulation and stratified export.
5. Generate touchpoints.
6. Export CSVs plus the data dictionary.
7. Run validate.py. Iterate parameters until all assertions pass. Report the final KPI table.
8. Write the answer key using the actual generated numbers.

Keep the final dataset free of hidden labels. Grep the output for "ai_forward" / "segment_truth" before finishing.
