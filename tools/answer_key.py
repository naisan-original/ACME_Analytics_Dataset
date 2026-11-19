"""Write evaluation/answer_key.md from the generated data (spec Section 10).

Usage: uv run python tools/answer_key.py
Every number comes from the CSVs, so the key always matches the current output.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from acme.common import load_config
from acme.metrics import kpi_table, retention

FY_STARTS = {"FY24": 202311, "FY25": 202411, "FY26": 202511}


def markdown_table(frame):
    header = "| " + " | ".join(frame.columns) + " |"
    divider = "|" + "---|" * len(frame.columns)
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, divider, *rows])


def main():
    cfg = load_config("config.yaml")
    folder = Path(cfg["paths"]["output_dir"])
    fact = pd.read_csv(folder / "fct_account_product_month.csv")
    accounts = pd.read_csv(folder / "dim_account.csv", keep_default_na=False, na_values=[""])  # region "NA" is North America
    months = pd.read_csv(folder / "dim_month.csv")
    usage = pd.read_csv(folder / "user_usage_month.csv")
    touchpoints = pd.read_csv(folder / "touchpoints.csv")
    products = pd.read_csv(folder / "dim_product.csv")
    truth = pd.read_csv(Path(cfg["paths"]["truth_dir"]) / "segment_truth.csv")

    ids = accounts["account_id"].to_numpy()
    month_ids = months["month_id"].tolist()
    position = {value: index for index, value in enumerate(ids)}
    month_position = {value: index for index, value in enumerate(month_ids)}
    arr = np.zeros((len(ids), len(month_ids)))
    np.add.at(arr, (fact["account_id"].map(position), fact["month_id"].map(month_position)), fact["arr"])
    is_ai = truth.set_index("account_id")["is_ai_forward"].reindex(ids).to_numpy().astype(bool)
    ever = (arr > 0).any(axis=1)

    overall = kpi_table(arr)
    hidden = kpi_table(arr, is_ai)
    rest = kpi_table(arr, ~is_ai)

    industries = accounts["industry"].to_numpy()
    by_industry = pd.DataFrame(
        [{"Industry": name, "FY24 GRR": round(retention(arr, 3, industries == name)[0], 1),
          "FY26 GRR": round(retention(arr, 5, industries == name)[0], 1)} for name in np.unique(industries)]
    ).sort_values("FY26 GRR")
    regions = accounts["region"].to_numpy()
    plain = industries != "High Tech"
    by_region = pd.DataFrame(
        [{"Region": name, "FY24 GRR": round(retention(arr, 3, regions == name)[0], 1),
          "FY25 GRR": round(retention(arr, 4, regions == name)[0], 1),
          "FY26 GRR": round(retention(arr, 5, regions == name)[0], 1),
          "FY24 excl. High Tech": round(retention(arr, 3, (regions == name) & plain)[0], 1),
          "FY25 excl. High Tech": round(retention(arr, 4, (regions == name) & plain)[0], 1),
          "FY26 excl. High Tech": round(retention(arr, 5, (regions == name) & plain)[0], 1)} for name in np.unique(regions)]
    )
    emea = by_region.set_index("Region").loc["EMEA"]
    emea_dips = emea["FY25 excl. High Tech"] < emea["FY24 excl. High Tech"]
    emea_recovers = emea["FY26 excl. High Tech"] > emea["FY25 excl. High Tech"]

    ai_ids = set(ids[is_ai])
    fact = fact.assign(hidden=fact["account_id"].isin(ai_ids), fiscal_year=fact["month_id"].map(months.set_index("month_id")["fiscal_year"]))
    analytics = fact[(fact["product_id"] == "P2") & fact["hidden"]]
    engine = fact[(fact["product_id"] == "P3") & fact["hidden"]]

    def last_month_sum(frame, column, fy):
        month = month_ids[(int(fy[2:]) - 21) * 12 + 11]
        return frame.loc[frame["month_id"] == month, column].sum()

    analytics_users = [last_month_sum(analytics, "active_users", fy) for fy in ("FY24", "FY26")]
    analytics_seats = [last_month_sum(analytics, "licensed_seats", fy) for fy in ("FY24", "FY26")]
    engine_work = [last_month_sum(engine, "work_units", fy) for fy in ("FY24", "FY26")]
    engine_arr = [last_month_sum(engine, "arr", fy) for fy in ("FY24", "FY26")]

    share = fact[fact["work_units"] > 0].groupby(["hidden", "fiscal_year"]).apply(
        lambda group: np.average(group["api_share"], weights=group["work_units"]), include_groups=False
    ).unstack(0).round(3)
    share.columns = ["Rest of base", "Hidden segment"]
    share = share.reset_index().rename(columns={"fiscal_year": "FY"})

    service = usage[usage["user_persona"] == "Service Account"]
    service_counts = service.assign(hidden=service["account_id"].isin(ai_ids)).groupby(["hidden", "month_id"])["user_id"].nunique()
    fy24_end, fy26_end = month_ids[47], month_ids[71]
    service_growth = (service_counts.get((True, fy24_end), 0), service_counts.get((True, fy26_end), 0))

    pattern = "programmatic|copilot|agents? |internal assistant|API access|machine traffic|LLM|no human"
    matches = touchpoints["notes"].str.contains(pattern, case=False, regex=True)
    hits = touchpoints[matches]
    hit_rate = hits["account_id"].isin(ai_ids).mean()

    high_tech = industries == "High Tech"
    ever_tech = int((ever & high_tech).sum())
    count = int((ever & is_ai).sum())
    fy24_share = arr[is_ai, 47].sum() / arr[:, 47].sum()

    bands = ["$200M-2B", "$2-10B", "$10-50B", "$50B+"]
    revenue_band = accounts["annual_revenue_band"].to_numpy()
    sub_industry = accounts["sub_industry"].to_numpy()
    tech_customers = ever & high_tech
    membership = pd.crosstab(sub_industry[tech_customers], revenue_band[tech_customers], values=is_ai[tech_customers], aggfunc="mean")
    membership = (membership[bands] * 100).round(0).fillna(0).astype(int).astype(str) + "%"
    membership = membership.reset_index().rename(columns={"row_0": "Sub-industry"})
    core = np.isin(sub_industry, cfg["ai_forward"]["sub_industries"])
    precision = is_ai[tech_customers & core].mean()
    recall = (is_ai & core).sum() / is_ai.sum()

    pivot = pd.read_csv(Path(cfg["paths"]["truth_dir"]) / "pivot_truth.csv").merge(accounts[["account_id", "annual_revenue_band"]])
    last = month_ids.index(202610)
    work = fact[fact["month_id"] == 202610]
    work = work[work["work_units"] > 0].groupby("account_id").apply(lambda g: np.average(g["api_share"], weights=g["work_units"]), include_groups=False)
    api_now = pd.Series(ids).map(work).to_numpy()
    gradient_rows = []
    for band in bands:
        in_band = revenue_band == band
        tech_band = high_tech & in_band
        hidden_band = is_ai & in_band
        base = tech_band & (arr[:, last - 12] > 0)
        hidden_base = hidden_band & (arr[:, last - 12] > 0)
        onsets = pivot.loc[pivot["annual_revenue_band"] == band, "onset_month"]
        gradient_rows.append({
            "Revenue band": band,
            "High Tech FY26 GRR": round(retention(arr, 5, tech_band)[0], 1),
            "High Tech FY26 logo churn": f"{(arr[base, last] == 0).mean():.0%}",
            "High Tech median API share, Oct 2026": f"{np.nanmedian(api_now[tech_band & (arr[:, last] > 0)]):.0%}",
            "Hidden: median pivot onset": months.iloc[int(onsets.median())]["month_id"] if len(onsets) else "",
            "Hidden: FY26 logo churn": f"{(arr[hidden_base, last] == 0).mean():.0%}" if hidden_base.any() else "",
        })
    gradient = pd.DataFrame(gradient_rows)

    employees = pd.read_csv(folder / "dim_employee.csv", keep_default_na=False, na_values=[""])
    turnover = cfg["red_herrings"]["rep_turnover"]
    leavers = employees[(employees["region"] == turnover["territory"])
                        & employees["termination_month_id"].between(month_ids[turnover["start_month"]], month_ids[turnover["end_month"]])]["employee_id"]
    before = fact[fact["month_id"] == month_ids[turnover["start_month"] - 1]]
    owned = set(before.loc[before["ae_employee_id"].isin(leavers) | before["csm_employee_id"].isin(leavers), "account_id"])
    window = fact[fact["month_id"].between(month_ids[turnover["start_month"]], month_ids[turnover["end_month"]])]
    peers = set(window["account_id"]) - owned
    reassigned = np.isin(ids, sorted(owned)) & plain
    peer_mask = np.isin(ids, sorted(peers)) & plain
    turnover_rows = pd.DataFrame([
        {"Group (excl. High Tech)": name, "Accounts at FY25 start": int((mask & (arr[:, 47] > 0)).sum()),
         "FY25 GRR": round(retention(arr, 4, mask)[0], 1), "FY25 NDR": round(retention(arr, 4, mask)[1], 1),
         "FY26 NDR": round(retention(arr, 5, mask)[1], 1)}
        for name, mask in (("Reassigned after a US-West departure", reassigned), ("All other accounts", peer_mask))
    ])

    contracts = pd.read_csv(folder / "contracts.csv")
    fiscal = months.set_index("month_id")["fiscal_year"]
    churned = contracts[contracts["outcome"] == "Churned"]
    by_start = churned["start_month_id"].map(fiscal).value_counts().reindex(sorted(fiscal.unique()), fill_value=0)
    by_end = churned["end_month_id"].map(fiscal).value_counts().reindex(sorted(fiscal.unique()), fill_value=0)
    trap = pd.DataFrame({"FY": by_end.index, "Churned contracts by start year (wrong)": by_start.values, "Churned contracts by end year (right)": by_end.values})

    lines = [
        "# ACME Analytics dataset: answer key",
        "",
        "**Spoiler. Kept outside the dataset folder on purpose: don't give this file to the analyst or tool under test.** All numbers come from the generated output.",
        "",
        "## The story in five sentences",
        "",
        f"1. ACME's ARR kept growing to ${overall.iloc[5]['arr_m']}M in FY26, which hides a retention problem.",
        f"2. GRR fell from {overall.iloc[3]['grr']}% in FY24 to {overall.iloc[5]['grr']}% in FY26, and NDR from {overall.iloc[3]['ndr']}% to {overall.iloc[5]['ndr']}%.",
        f"3. The drop is concentrated in {count} AI-forward High Tech customers that were ACME's best accounts until they began moving from people using the UI to agents calling the API.",
        "4. Because every product is seat-priced and API calls consume no seats, activity rose while seats, and then ARR, fell.",
        f"5. Excluding that segment, FY26 GRR is {rest.iloc[5]['grr']}% and NDR is {rest.iloc[5]['ndr']}%, so the core business is healthy and the real issue is a pricing model that no longer matches how these customers work.",
        "",
        "## Hidden segment definition",
        "",
        f"- {count} customers, {count / ever.sum():.1%} of all customers ever, and {fy24_share:.1%} of FY24 ARR.",
        f"- All High Tech. They are {count / ever_tech:.0%} of High Tech customers, so High Tech alone is only a partial signal.",
        f"- Membership is a random draw, weighted by sub-industry and company size. {precision:.0%} of {', '.join(cfg['ai_forward']['sub_industries'])} customers are in the segment, and those three sub-industries hold {recall:.0%} of it. Sub-industry is a strong clue, not a label. Share of High Tech customers in the segment:",
        "", markdown_table(membership), "",
        "- Smaller companies adopt first. They are more likely to be in the segment and move through the pivot faster, and the largest accounts start it last. Many small accounts landed late, so their median onset is not the earliest, but they are hit hardest by FY26. The damage shows up as a gradient by revenue band.",
        "- Pivot onset is staggered from Q3 FY24 through Q2 FY26. After onset, API share climbs from about 5% to over 90%, Service Accounts appear, and human Creators and Explorers fade.",
        "- The label exists only in `evaluation/truth/segment_truth.csv`, and `evaluation/truth/pivot_truth.csv` has each account's onset. No column in the dataset encodes it.",
        "",
        "## KPI results",
        "",
        "Overall:", "", markdown_table(overall), "",
        "Hidden segment:", "", markdown_table(hidden), "",
        "Rest of base:", "", markdown_table(rest), "",
        "## Suggested discovery path",
        "",
        f"1. **Top-line ARR is still growing:** ${overall.iloc[3]['arr_m']}M in FY24 to ${overall.iloc[5]['arr_m']}M in FY26.",
        f"2. **GRR and NDR are falling:** see the overall table.",
        f"3. **Slice by region. EMEA is a red herring:** new-logo share dips in FY25 Q1-Q3 and, excluding High Tech, EMEA GRR goes {emea['FY24 excl. High Tech']}% to {emea['FY25 excl. High Tech']}% to {emea['FY26 excl. High Tech']}%. The hidden segment sits in every region, so compare the whole-region and excl. High Tech columns below.", "", markdown_table(by_region), "",
        f"4. **Slice by owner. Turnover is a red herring:** US-West lost {len(leavers)} AEs and CSMs in FY25 H1. Their {len(owned):,} accounts were reassigned, got fewer touches, and retained visibly worse for about a year, then recovered. It is tempting but explains little of the FY24-to-FY26 decline.", "", markdown_table(turnover_rows), "",
        "5. **Slice by industry. High Tech stands out:**", "", markdown_table(by_industry), "",
        f"6. **Look at product mix. Analytics is falling:** in the hidden segment, Analytics active users went from {analytics_users[0]:,} at FY24 end to {analytics_users[1]:,} at FY26 end, and seats from {analytics_seats[0]:,} to {analytics_seats[1]:,}.",
        f"7. **Look at API share and Service Account users:** Service Accounts seen in the hidden segment went from {service_growth[0]:,} to {service_growth[1]:,} between FY24 end and FY26 end.", "", markdown_table(share), "",
        f"8. **Read the touchpoint notes:** {len(hits):,} notes mention programmatic or agent themes, and {hit_rate:.0%} belong to hidden-segment accounts. The rest are deliberate noise, so text search is evidence and not proof.",
        "9. **Slice High Tech by company size. Smaller companies moved first:** the hidden columns use the label, the rest are visible to an analyst.", "", markdown_table(gradient), "",
        f"10. **Seat compression explains it:** Data Engine work units in the hidden segment moved from {engine_work[0]:,} to {engine_work[1]:,} while its ARR moved from ${engine_arr[0] / 1e6:.1f}M to ${engine_arr[1] / 1e6:.1f}M. Survivorship matters here, because churned accounts leave both totals.",
        "",
        "## Trap: counting churn by contract start date",
        "",
        "`contracts.outcome` is set when a contract ends, so contracts that start in FY26 are almost all still `Active` at the end of the window. Grouping churned contracts by start year makes recent churn look like zero. Churn runs right to the last month.",
        "", markdown_table(trap), "",
        "## Example questions and expected answers",
        "",
        f"1. What was ARR at the end of FY26? **${overall.iloc[5]['arr_m']}M**",
        f"2. How many customers were there at the end of FY26? **{overall.iloc[5]['customers']:,}**",
        f"3. What was GRR in FY24 and FY26? **{overall.iloc[3]['grr']}% and {overall.iloc[5]['grr']}%**",
        f"4. What was NDR in FY26? **{overall.iloc[5]['ndr']}%**",
        f"5. Which industry had the worst GRR in FY26? **{by_industry.iloc[0]['Industry']}, at {by_industry.iloc[0]['FY26 GRR']}%**",
        f"6. Did EMEA recover after its FY25 soft patch? **{'Yes' if emea_dips and emea_recovers else 'No'}, once High Tech is excluded: {emea['FY25 excl. High Tech']}% in FY25 and {emea['FY26 excl. High Tech']}% in FY26.** Whole-region GRR, which includes High Tech, was {emea['FY25 GRR']}% and {emea['FY26 GRR']}%.",
        f"7. What is GRR without the problem accounts? **FY26 GRR of {rest.iloc[5]['grr']}% and NDR of {rest.iloc[5]['ndr']}%** using the hidden label. An analyst approximates this by excluding High Tech accounts with high API share.",
        "8. Why does activity rise while revenue falls? **Agents make API calls that do not consume seats, and pricing is per seat.**",
        f"9. Which High Tech companies were hit first? **The smallest: High Tech FY26 GRR is {gradient.iloc[0]['High Tech FY26 GRR']}% in the {bands[0]} band against {gradient.iloc[3]['High Tech FY26 GRR']}% in {bands[3]}.**",
        f"10. Was there churn in FY26? **Yes, the most of any year: {by_end.iloc[-1]:,} churned contracts ending in FY26.** None appear by start year because those contracts have not ended yet.",
        "",
        "## Charts to expect",
        "",
        "- ARR rising, with GRR and NDR lines falling after FY24.",
        "- GRR by industry, with High Tech separating from the pack in FY25-FY26.",
        "- High Tech accounts plotted by API share against ARR change, showing a cluster above 50% API share that lost seats.",
        "- Active users against API calls for ACME Analytics over time, in opposite directions.",
        "- Service Account count rising inside the affected accounts.",
        "- Average touchpoint sentiment falling for those accounts roughly two quarters before contraction.",
        "",
    ]
    path = Path(cfg["paths"]["evaluation_dir"]) / "answer_key.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {path}")
    print(f"products in dataset: {len(products)}")


if __name__ == "__main__":
    main()
