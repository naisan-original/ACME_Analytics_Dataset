# ACME Analytics dataset: facilitator answer key

**Spoiler. Kept outside the dataset folder on purpose: don't give this file to the analyst or tool under test.** All numbers come from the generated output.

## The story in five sentences

1. ACME's ARR kept growing to $416.7M in FY26, which hides a retention problem.
2. GRR fell from 91.0% in FY24 to 84.6% in FY26, and NDR from 120.1% to 108.2%.
3. The drop is concentrated in 671 AI-forward High Tech customers that were ACME's best accounts until they began moving from people using the UI to agents calling the API.
4. Because every product is seat-priced and API calls consume no seats, activity rose while seats, and then ARR, fell.
5. Excluding that segment, FY26 GRR is 93.4% and NDR is 122.7%, so the core business is healthy and the real issue is a pricing model that no longer matches how these customers work.

## Hidden segment definition

- 671 customers, 12.9% of all customers ever, and 22.6% of FY24 ARR.
- All High Tech. They are 61% of High Tech customers, so High Tech alone is only a partial signal.
- Membership is a random draw, weighted by sub-industry and company size. 72% of Software, Internet & Platforms, Semiconductors customers are in the segment, and those three sub-industries hold 88% of it. Sub-industry is a strong clue, not a label. Share of High Tech customers in the segment:

| Sub-industry | $200M-2B | $2-10B | $10-50B | $50B+ |
|---|---|---|---|---|
| Hardware | 28% | 29% | 10% | 0% |
| IT Services | 28% | 29% | 30% | 25% |
| Internet & Platforms | 78% | 68% | 44% | 0% |
| Semiconductors | 68% | 60% | 40% | 100% |
| Software | 81% | 69% | 76% | 20% |

- Smaller companies adopt first. They are more likely to be in the segment and move through the pivot faster, and the largest accounts start it last. Many small accounts landed late, so their median onset is not the earliest, but they are hit hardest by FY26. The damage shows up as a gradient by revenue band.
- Pivot onset is staggered from Q3 FY24 through Q2 FY26. After onset, API share climbs from about 5% to over 90%, Service Accounts appear, and human Creators and Explorers fade.
- The label exists only in `facilitator/segment_truth.csv` (not published), and `pivot_truth.csv` has each account's onset. No single dataset column encodes it.

## KPI results

Overall:

| FY | customers | arr_m | grr | ndr |
|---|---|---|---|---|
| FY21 | 119 | 8.6 | 93.2 | 134.0 |
| FY22 | 447 | 36.6 | 91.0 | 129.7 |
| FY23 | 1205 | 107.6 | 94.6 | 127.6 |
| FY24 | 2423 | 230.4 | 91.0 | 120.1 |
| FY25 | 3563 | 340.4 | 87.8 | 109.3 |
| FY26 | 4492 | 416.7 | 84.6 | 108.2 |

Hidden segment:

| FY | customers | arr_m | grr | ndr |
|---|---|---|---|---|
| FY21 | 36 | 4.2 | 100.0 | 164.0 |
| FY22 | 105 | 12.1 | 96.0 | 148.4 |
| FY23 | 225 | 29.3 | 96.0 | 141.9 |
| FY24 | 358 | 52.2 | 90.0 | 127.2 |
| FY25 | 578 | 65.4 | 74.2 | 82.6 |
| FY26 | 327 | 32.5 | 47.3 | 47.3 |

Rest of base:

| FY | customers | arr_m | grr | ndr |
|---|---|---|---|---|
| FY21 | 83 | 4.4 | 88.3 | 112.5 |
| FY22 | 342 | 24.4 | 86.3 | 112.1 |
| FY23 | 980 | 78.3 | 94.0 | 120.6 |
| FY24 | 2065 | 178.3 | 91.4 | 117.4 |
| FY25 | 2985 | 275.1 | 91.7 | 117.2 |
| FY26 | 4165 | 384.3 | 93.4 | 122.7 |

## Suggested discovery path

1. **Top-line ARR is still growing:** $230.4M in FY24 to $416.7M in FY26.
2. **GRR and NDR are falling:** see the overall table.
3. **Slice by region. EMEA is a red herring:** new-logo share dips in FY25 Q1-Q3 and, excluding High Tech, EMEA GRR goes 93.1% to 91.1% to 95.7%. The hidden segment sits in every region, so compare the whole-region and excl. High Tech columns below.

| Region | FY24 GRR | FY25 GRR | FY26 GRR | FY24 excl. High Tech | FY25 excl. High Tech | FY26 excl. High Tech |
|---|---|---|---|---|---|---|
| APAC | 85.6 | 87.7 | 82.7 | 91.7 | 91.5 | 92.9 |
| EMEA | 95.1 | 88.1 | 87.8 | 93.1 | 91.1 | 95.7 |
| LATAM | 93.5 | 92.0 | 87.4 | 93.8 | 96.4 | 93.5 |
| NA | 91.2 | 87.6 | 84.2 | 91.8 | 91.6 | 93.3 |

4. **Slice by owner. Turnover is a red herring:** US-West lost AEs and CSMs in FY25. Reassigned accounts show fewer touches and a modest churn bump, but it does not explain the decline.
5. **Slice by industry. High Tech stands out:**

| Industry | FY24 GRR | FY26 GRR |
|---|---|---|
| High Tech | 89.4 | 62.3 |
| Public Sector & Education | 77.2 | 85.9 |
| Telecom & Media | 89.5 | 92.8 |
| Financial Services | 90.1 | 93.1 |
| Healthcare & Life Sciences | 94.9 | 93.6 |
| Professional Services | 97.2 | 93.7 |
| Retail & CPG | 90.0 | 94.0 |
| Transportation & Logistics | 94.7 | 94.0 |
| Manufacturing | 95.0 | 94.1 |
| Energy & Utilities | 91.6 | 95.8 |

6. **Look at product mix. Analytics is falling:** in the hidden segment, Analytics active users went from 23,106 at FY24 end to 6,253 at FY26 end, and seats from 50,752 to 14,682.
7. **Look at API share and Service Account users:** Service Accounts seen in the hidden segment went from 900 to 6,840 between FY24 end and FY26 end.

| FY | Rest of base | Hidden segment |
|---|---|---|
| FY21 | 0.034 | 0.05 |
| FY22 | 0.046 | 0.055 |
| FY23 | 0.061 | 0.065 |
| FY24 | 0.08 | 0.093 |
| FY25 | 0.106 | 0.384 |
| FY26 | 0.133 | 0.763 |

8. **Read the touchpoint notes:** 881 notes mention programmatic or agent themes, and 89% belong to hidden-segment accounts. The rest are deliberate noise, so text search is evidence and not proof.
9. **Slice High Tech by company size. Smaller companies moved first:** the hidden columns use the label, the rest are visible to an analyst.

| Revenue band | High Tech FY26 GRR | High Tech FY26 logo churn | High Tech median API share, Oct 2026 | Hidden: median pivot onset | Hidden: FY26 logo churn |
|---|---|---|---|---|---|
| $200M-2B | 48.9 | 41% | 20% | 202504 | 52% |
| $2-10B | 58.9 | 29% | 18% | 202502 | 41% |
| $10-50B | 69.0 | 22% | 16% | 202506 | 38% |
| $50B+ | 80.0 | 10% | 13% | 202509 | 50% |

10. **Seat compression explains it:** Data Engine work units in the hidden segment moved from 1,085,044 to 2,598,711 while its ARR moved from $8.3M to $6.2M. Survivorship matters here, because churned accounts leave both totals.

## Trap: counting churn by contract start date

`contracts.outcome` is set when a contract ends, so contracts that start in FY26 are almost all still `Active` at the end of the window. Grouping churned contracts by start year makes recent churn look like zero. Churn runs right to the last month.

| FY | Churned contracts by start year (wrong) | Churned contracts by end year (right) |
|---|---|---|
| FY21 | 16 | 4 |
| FY22 | 28 | 14 |
| FY23 | 108 | 30 |
| FY24 | 263 | 108 |
| FY25 | 707 | 297 |
| FY26 | 0 | 669 |

## Example questions and expected answers

1. What was ARR at the end of FY26? **$416.7M**
2. How many customers were there at the end of FY26? **4,492**
3. What was GRR in FY24 and FY26? **91.0% and 84.6%**
4. What was NDR in FY26? **108.2%**
5. Which industry had the worst GRR in FY26? **High Tech, at 62.3%**
6. Did EMEA recover after its FY25 soft patch? **Yes, once High Tech is excluded: 91.1% in FY25 and 95.7% in FY26.** Whole-region GRR, which includes High Tech, was 88.1% and 87.8%.
7. What is GRR without the problem accounts? **FY26 GRR of 93.4% and NDR of 122.7%** using the hidden label. An analyst approximates this by excluding High Tech accounts with high API share.
8. Why does activity rise while revenue falls? **Agents make API calls that do not consume seats, and pricing is per seat.**
9. Which High Tech companies were hit first? **The smallest: High Tech FY26 GRR is 48.9% in the $200M-2B band against 80.0% in $50B+.**
10. Was there churn in FY26? **Yes, the most of any year: 669 churned contracts ending in FY26.** None appear by start year because those contracts have not ended yet.

## Charts to expect

- ARR rising, with GRR and NDR lines falling after FY24.
- GRR by industry, with High Tech separating from the pack in FY25-FY26.
- High Tech accounts plotted by API share against ARR change, showing a cluster above 50% API share that lost seats.
- Active users against API calls for ACME Analytics over time, in opposite directions.
- Service Account count rising inside the affected accounts.
- Average touchpoint sentiment falling for those accounts roughly two quarters before contraction.
