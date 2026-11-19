# ACME Analytics dataset: answer key

**Spoiler. Kept outside the dataset folder on purpose: don't give this file to the analyst or tool under test.** All numbers come from the generated output.

## The story in five sentences

1. ACME's ARR kept growing to $441.2M in FY26, which hides a retention problem.
2. GRR fell from 91.4% in FY24 to 83.4% in FY26, and NDR from 121.8% to 106.9%.
3. The drop is concentrated in 671 AI-forward High Tech customers that were ACME's best accounts until they began moving from people using the UI to agents calling the API.
4. Because every product is seat-priced and API calls consume no seats, activity rose while seats, and then ARR, fell.
5. Excluding that segment, FY26 GRR is 91.8% and NDR is 120.7%, so the core business is healthy and the real issue is a pricing model that no longer matches how these customers work.

## Hidden segment definition

- 671 customers, 12.9% of all customers ever, and 21.5% of FY24 ARR.
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
- The label exists only in `evaluation/truth/segment_truth.csv`, and `evaluation/truth/pivot_truth.csv` has each account's onset. No column in the dataset encodes it.

## KPI results

Overall:

| FY | customers | arr_m | grr | ndr |
|---|---|---|---|---|
| FY21 | 119 | 8.3 | 94.9 | 137.1 |
| FY22 | 453 | 36.4 | 93.5 | 130.6 |
| FY23 | 1209 | 105.7 | 92.5 | 126.4 |
| FY24 | 2414 | 225.4 | 91.4 | 121.8 |
| FY25 | 3535 | 335.0 | 88.0 | 109.6 |
| FY26 | 4476 | 441.2 | 83.4 | 106.9 |

Hidden segment:

| FY | customers | arr_m | grr | ndr |
|---|---|---|---|---|
| FY21 | 36 | 3.5 | 100.0 | 185.5 |
| FY22 | 105 | 11.1 | 93.2 | 127.9 |
| FY23 | 228 | 26.7 | 94.4 | 136.7 |
| FY24 | 357 | 48.5 | 91.2 | 129.4 |
| FY25 | 573 | 62.9 | 75.5 | 85.1 |
| FY26 | 346 | 32.0 | 47.1 | 47.2 |

Rest of base:

| FY | customers | arr_m | grr | ndr |
|---|---|---|---|---|
| FY21 | 83 | 4.7 | 91.8 | 108.4 |
| FY22 | 348 | 25.3 | 93.8 | 132.6 |
| FY23 | 981 | 79.0 | 91.7 | 121.9 |
| FY24 | 2057 | 176.9 | 91.5 | 119.2 |
| FY25 | 2962 | 272.1 | 91.4 | 116.3 |
| FY26 | 4130 | 409.2 | 91.8 | 120.7 |

## Suggested discovery path

1. **Top-line ARR is still growing:** $225.4M in FY24 to $441.2M in FY26.
2. **GRR and NDR are falling:** see the overall table.
3. **Slice by region. EMEA is a red herring:** new-logo share dips in FY25 Q1-Q3 and, excluding High Tech, EMEA GRR goes 95.9% to 91.5% to 93.4%. The hidden segment sits in every region, so compare the whole-region and excl. High Tech columns below.

| Region | FY24 GRR | FY25 GRR | FY26 GRR | FY24 excl. High Tech | FY25 excl. High Tech | FY26 excl. High Tech |
|---|---|---|---|---|---|---|
| APAC | 91.3 | 90.4 | 82.6 | 87.3 | 93.5 | 95.3 |
| EMEA | 96.3 | 87.4 | 87.2 | 95.9 | 91.5 | 93.4 |
| LATAM | 74.3 | 86.9 | 91.6 | 72.8 | 96.2 | 95.8 |
| NA | 90.8 | 87.7 | 82.7 | 90.6 | 91.7 | 91.3 |

4. **Slice by owner. Turnover is a red herring:** US-West lost 9 AEs and CSMs in FY25 H1. Their 541 accounts were reassigned, got fewer touches, and retained visibly worse for about a year, then recovered. It is tempting but explains little of the FY24-to-FY26 decline.

| Group (excl. High Tech) | Accounts at FY25 start | FY25 GRR | FY25 NDR | FY26 NDR |
|---|---|---|---|---|
| Reassigned after a US-West departure | 402 | 86.7 | 109.8 | 117.6 |
| All other accounts | 1493 | 94.0 | 120.3 | 123.1 |

5. **Slice by industry. High Tech stands out:**

| Industry | FY24 GRR | FY26 GRR |
|---|---|---|
| High Tech | 92.7 | 59.0 |
| Energy & Utilities | 92.2 | 85.3 |
| Financial Services | 90.1 | 91.1 |
| Transportation & Logistics | 95.2 | 91.6 |
| Manufacturing | 88.1 | 92.1 |
| Healthcare & Life Sciences | 95.9 | 93.7 |
| Telecom & Media | 87.9 | 94.0 |
| Professional Services | 91.1 | 94.4 |
| Retail & CPG | 89.9 | 94.6 |
| Public Sector & Education | 83.7 | 95.1 |

6. **Look at product mix. Analytics is falling:** in the hidden segment, Analytics active users went from 23,280 at FY24 end to 5,283 at FY26 end, and seats from 54,729 to 16,161.
7. **Look at API share and Service Account users:** Service Accounts seen in the hidden segment went from 844 to 5,147 between FY24 end and FY26 end.

| FY | Rest of base | Hidden segment |
|---|---|---|
| FY21 | 0.032 | 0.05 |
| FY22 | 0.046 | 0.052 |
| FY23 | 0.061 | 0.064 |
| FY24 | 0.082 | 0.095 |
| FY25 | 0.11 | 0.411 |
| FY26 | 0.135 | 0.706 |

8. **Read the touchpoint notes:** 905 notes mention programmatic or agent themes, and 85% belong to hidden-segment accounts. The rest are deliberate noise, so text search is evidence and not proof.
9. **Slice High Tech by company size. Smaller companies moved first:** the hidden columns use the label, the rest are visible to an analyst.

| Revenue band | High Tech FY26 GRR | High Tech FY26 logo churn | High Tech median API share, Oct 2026 | Hidden: median pivot onset | Hidden: FY26 logo churn |
|---|---|---|---|---|---|
| $200M-2B | 52.1 | 35% | 58% | 202504 | 44% |
| $2-10B | 55.4 | 33% | 17% | 202503 | 48% |
| $10-50B | 65.4 | 19% | 18% | 202506 | 26% |
| $50B+ | 65.5 | 20% | 14% | 202512 | 50% |

10. **Seat compression explains it:** Data Engine work units in the hidden segment moved from 459,607 to 1,272,363 while its ARR moved from $4.8M to $4.9M. Survivorship matters here, because churned accounts leave both totals.

## Trap: counting churn by contract start date

`contracts.outcome` is set when a contract ends, so contracts that start in FY26 are almost all still `Active` at the end of the window. Grouping churned contracts by start year makes recent churn look like zero. Churn runs right to the last month.

| FY | Churned contracts by start year (wrong) | Churned contracts by end year (right) |
|---|---|---|
| FY21 | 10 | 3 |
| FY22 | 27 | 5 |
| FY23 | 108 | 32 |
| FY24 | 306 | 110 |
| FY25 | 703 | 327 |
| FY26 | 0 | 677 |

## Example questions and expected answers

1. What was ARR at the end of FY26? **$441.2M**
2. How many customers were there at the end of FY26? **4,476**
3. What was GRR in FY24 and FY26? **91.4% and 83.4%**
4. What was NDR in FY26? **106.9%**
5. Which industry had the worst GRR in FY26? **High Tech, at 59.0%**
6. Did EMEA recover after its FY25 soft patch? **Yes, once High Tech is excluded: 91.5% in FY25 and 93.4% in FY26.** Whole-region GRR, which includes High Tech, was 87.4% and 87.2%.
7. What is GRR without the problem accounts? **FY26 GRR of 91.8% and NDR of 120.7%** using the hidden label. An analyst approximates this by excluding High Tech accounts with high API share.
8. Why does activity rise while revenue falls? **Agents make API calls that do not consume seats, and pricing is per seat.**
9. Which High Tech companies were hit first? **The smallest: High Tech FY26 GRR is 52.1% in the $200M-2B band against 65.5% in $50B+.**
10. Was there churn in FY26? **Yes, the most of any year: 677 churned contracts ending in FY26.** None appear by start year because those contracts have not ended yet.

## Charts to expect

- ARR rising, with GRR and NDR lines falling after FY24.
- GRR by industry, with High Tech separating from the pack in FY25-FY26.
- High Tech accounts plotted by API share against ARR change, showing a cluster above 50% API share that lost seats.
- Active users against API calls for ACME Analytics over time, in opposite directions.
- Service Account count rising inside the affected accounts.
- Average touchpoint sentiment falling for those accounts roughly two quarters before contraction.
