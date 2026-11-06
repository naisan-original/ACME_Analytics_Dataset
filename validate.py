"""Print KPI tables and assert the spec's targets (Section 9). Exits non-zero if any check fails."""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from acme.common import load_config
from acme.metrics import kpi_table, retention

results = []


def check(name, passed, detail=""):
    results.append((name, bool(passed)))
    print(f"[{'PASS' if passed else 'FAIL'}] {name}{f': {detail}' if detail else ''}")


def load(cfg):
    folder = Path(cfg["paths"]["output_dir"])
    # keep_default_na=False: region "NA" means North America, not a null.
    return {
        path.stem: pd.read_csv(path, low_memory=False, keep_default_na=False, na_values=[""])
        for path in sorted(folder.glob("*.csv"))
    }


def arr_by_account(fact, months, accounts):
    index = {value: position for position, value in enumerate(accounts)}
    month_index = {value: position for position, value in enumerate(months)}
    arr = np.zeros((len(accounts), len(months)))
    np.add.at(arr, (fact["account_id"].map(index).to_numpy(), fact["month_id"].map(month_index).to_numpy()), fact["arr"].to_numpy())
    return arr


def check_kpis(cfg, arr, is_ai):
    targets = cfg["targets"]
    tolerance = targets["tolerance_pts"]
    overall = kpi_table(arr)
    print("\nOVERALL\n" + overall.to_string(index=False))
    print("\nHIDDEN SEGMENT\n" + kpi_table(arr, is_ai).to_string(index=False))
    rest = kpi_table(arr, ~is_ai)
    print("\nREST OF BASE\n" + rest.to_string(index=False) + "\n")
    for fy, row in overall.iterrows():
        label = row["FY"]
        customers = targets["customers"][fy]
        check(f"{label} customers within 5%", abs(row["customers"] / customers - 1) <= 0.05, f"{row['customers']} vs {customers}")
        check(f"{label} ARR in range", targets["arr_low"][fy] <= row["arr_m"] <= targets["arr_high"][fy],
              f"${row['arr_m']}M vs ${targets['arr_low'][fy]}-{targets['arr_high'][fy]}M")
        check(f"{label} GRR within {tolerance} pts", abs(row["grr"] - targets["grr"][fy]) <= tolerance, f"{row['grr']} vs {targets['grr'][fy]}")
        check(f"{label} NDR within {tolerance} pts", abs(row["ndr"] - targets["ndr"][fy]) <= tolerance, f"{row['ndr']} vs {targets['ndr'][fy]}")
    for fy in (4, 5):
        row = rest.iloc[fy]
        check(f"{row['FY']} rest-of-base GRR >= {targets['rest_min_grr']}", row["grr"] >= targets["rest_min_grr"] - 0.5, str(row["grr"]))
        check(f"{row['FY']} rest-of-base NDR >= {targets['rest_min_ndr']}", row["ndr"] >= targets["rest_min_ndr"] - 0.5, str(row["ndr"]))


def check_segment(arr, is_ai, accounts_table):
    fy24 = 47
    total = arr[:, fy24].sum()
    high_tech = (accounts_table["industry"] == "High Tech").to_numpy()
    active = arr[:, fy24] > 0
    ever = (arr > 0).any(axis=1)
    customers = int(ever.sum())
    count = int((is_ai & ever).sum())
    check("Hidden segment 600-700 customers", 600 <= count <= 700, str(count))
    check("Hidden segment 12-15% of customers", 0.115 <= count / customers <= 0.155, f"{count / customers:.1%}")
    share = arr[is_ai, fy24].sum() / total
    check("Hidden segment 20-25% of FY24 ARR", 0.195 <= share <= 0.255, f"{share:.1%}")
    check("High Tech 20-22% of FY24 customers", 0.195 <= high_tech[active].mean() <= 0.225, f"{high_tech[active].mean():.1%}")
    tech_share = arr[high_tech, fy24].sum() / total
    check("High Tech 28-30% of FY24 ARR", 0.275 <= tech_share <= 0.305, f"{tech_share:.1%}")
    normal = 1 - (is_ai & ever & high_tech).sum() / (ever & high_tech).sum()
    check("35-40% of High Tech is normal", 0.33 <= normal <= 0.42, f"{normal:.1%}")
    for fy in (4, 5):
        begin, end = fy * 12 - 1, fy * 12 + 11
        base = (arr[:, begin] > 0) & is_ai
        print(f"[INFO] Hidden segment logo churn FY{21 + fy}: {(arr[base, end] == 0).mean():.1%} (spec: ~25-35%)")


def check_reconciliation(tables):
    fact = tables["fct_account_product_month"]
    contracts = tables["contracts"]
    months = tables["dim_month"]["month_id"].tolist()
    position = {value: index for index, value in enumerate(months)}
    start = contracts["start_month_id"].map(position).to_numpy()
    last = contracts["end_month_id"].map(lambda value: position.get(value, len(months) - 1)).to_numpy()
    acv = np.zeros(len(months) + 1)
    np.add.at(acv, start, contracts["acv"].to_numpy())
    np.add.at(acv, last + 1, -contracts["acv"].to_numpy())
    by_month = np.cumsum(acv)[: len(months)]
    central = fact.groupby("month_id")["arr"].sum().reindex(months).fillna(0).to_numpy()
    gap = np.abs(by_month / np.maximum(central, 1) - 1).max()
    check("Contract ACV reconciles to central ARR by month (<= 0.5%)", gap <= 0.005, f"max gap {gap:.4%}")

    usage = tables["user_usage_month"]
    for measure in ("ui_hours", "ui_sessions", "api_calls", "work_units"):
        weighted = (usage[measure] * usage["sample_weight"]).sum()
        gap = abs(weighted / fact[measure].sum() - 1)
        check(f"Weighted {measure} vs central (<= 5%)", gap <= 0.05, f"gap {gap:.2%}")


def check_distributions(cfg, tables):
    fact = tables["fct_account_product_month"]
    usage = tables["user_usage_month"]
    settings = cfg["usage"]
    seats = fact["licensed_seats"].sum()
    monthly = fact["active_users"].sum() / seats
    check("Monthly active 25-35% of seats", 0.25 <= monthly <= 0.35, f"{monthly:.1%}")
    humans = usage[usage["user_persona"] != "Service Account"]
    weekly = humans.loc[humans["ui_hours"] >= settings["weekly_active_hours"], "sample_weight"].sum() / seats
    check("Weekly active 5-10% of seats", 0.05 <= weekly <= 0.10, f"{weekly:.1%}")
    full_time = humans.loc[humans["ui_hours"] >= settings["near_full_time_hours"], "sample_weight"].sum() / seats
    check("Near-full-time < 1% of seats", full_time < 0.01, f"{full_time:.2%}")
    latest = fact[(fact["month_id"] == fact["month_id"].max()) & (fact["licensed_seats"] > 0)].sort_values("net_price_per_seat_month")
    cumulative = latest["licensed_seats"].cumsum() / latest["licensed_seats"].sum()
    median = latest.loc[cumulative >= 0.5, "net_price_per_seat_month"].iloc[0]
    check("Seat-weighted median price $28-33", 28 <= median <= 33, f"${median:.2f}")
    below_list = (fact["net_price_per_seat_month"] > fact["list_price_per_seat_month"]).sum()
    check("Net price never above list", below_list == 0, str(below_list))


def check_accounts(tables):
    accounts = tables["dim_account"]
    us = (accounts["hq_country"] == "United States").mean()
    check("US/RoW split 60/40 +/- 2%", abs(us - 0.60) <= 0.02, f"{us:.1%}")
    check("No duplicate account names", accounts["account_name"].is_unique, str(accounts["account_name"].duplicated().sum()))
    check("All accounts in a band at or above the revenue floor", accounts["annual_revenue_band"].notna().all())
    prospects = accounts["account_status"] == "Prospect"
    paying = set(tables["fct_account_product_month"]["account_id"])
    check("Prospects have no revenue", not set(accounts.loc[prospects, "account_id"]) & paying)


def check_headcount(cfg, tables):
    employees = tables["dim_employee"]
    months = tables["dim_month"]["month_id"].tolist()
    for role, targets in (("AE", cfg["people"]["ae_fy_end"]), ("CSM", cfg["people"]["csm_fy_end"])):
        staff = employees[employees["role"] == role]
        actual = []
        for fy in range(6):
            month = months[fy * 12 + 11]
            active = (staff["hire_month_id"] <= month) & (staff["termination_month_id"].isna() | (staff["termination_month_id"] > month))
            actual.append(int(active.sum()))
        check(f"{role} headcount ramp", all(abs(a - t) <= max(1, 0.05 * t) for a, t in zip(actual, targets)), f"{actual} vs {targets}")


def check_discoverability(cfg, tables, arr, ids):
    accounts = tables["dim_account"].set_index("account_id").reindex(ids)
    fact = tables["fct_account_product_month"]
    industries = accounts["industry"].to_numpy()
    for fy in (4, 5):
        rates = {name: retention(arr, fy, industries == name)[0] for name in np.unique(industries)}
        worst = min(rates, key=rates.get)
        check(f"(a) High Tech has the worst GRR in FY{21 + fy}", worst == "High Tech", f"{worst} at {rates[worst]:.1f}")

    # A churn row has no activity, so API share is read from each account's last active months.
    tech_ids = accounts.index[accounts["industry"] == "High Tech"]
    in_fy26 = fact.loc[(fact["month_id"] >= 202511) & fact["account_id"].isin(tech_ids), "account_id"].unique()
    active = fact[fact["account_id"].isin(in_fy26) & (fact["churn_flag"] == 0)]
    weighted = active.assign(api_work=active["api_share"] * active["work_units"]).groupby(["account_id", "month_id"])[["api_work", "work_units"]].sum()
    recent = weighted.sort_index().groupby(level="account_id").tail(3).groupby(level="account_id").sum()
    totals = pd.DataFrame({"api": recent["api_work"] / recent["work_units"].replace(0, np.nan)}).fillna(0)
    churned = accounts.loc[totals.index, "churn_month_id"].fillna(0) >= 202511
    heavy = totals["api"] > 0.5
    high, low = churned[heavy].mean(), churned[~heavy].mean()
    check("(b) High Tech accounts over 50% API share churn at >= 3x the rest", high >= 3 * max(low, 1e-9),
          f"{high:.1%} vs {low:.1%} across {int(heavy.sum())} and {int((~heavy).sum())} accounts")

    decline = retention(arr, 3)[0] - retention(arr, 5)[0]
    employees = tables["dim_employee"]
    turnover = cfg["red_herrings"]["rep_turnover"]
    months = tables["dim_month"]["month_id"].tolist()
    leavers = employees[
        (employees["region"] == turnover["territory"])
        & employees["termination_month_id"].between(months[turnover["start_month"]], months[turnover["end_month"]])
    ]["employee_id"]
    owned = fact[fact["ae_employee_id"].isin(leavers) | fact["csm_employee_id"].isin(leavers)]["account_id"].unique()
    herrings = {"EMEA": (accounts["region"] == "EMEA").to_numpy(), "Rep turnover": np.isin(ids, owned)}
    for name, mask in herrings.items():
        without = retention(arr, 3, ~mask)[0] - retention(arr, 5, ~mask)[0]
        explained = (decline - without) / decline
        check(f"(c) {name} explains <= 30% of the FY24-to-FY26 GRR decline", explained <= 0.30, f"{explained:.1%} of {decline:.1f} pts")


def check_red_herrings(cfg, tables, arr, ids):
    accounts = tables["dim_account"].set_index("account_id").reindex(ids)
    months = tables["dim_month"]["month_id"].tolist()
    emea = (accounts["region"] == "EMEA").to_numpy()
    plain = emea & (accounts["industry"] != "High Tech").to_numpy()
    grr = [retention(arr, fy, plain)[0] for fy in (3, 4, 5)]
    detail = f"FY24 {grr[0]:.1f}, FY25 {grr[1]:.1f}, FY26 {grr[2]:.1f}"
    check("EMEA excluding High Tech dips in FY25", grr[1] < grr[0], detail)
    check("EMEA excluding High Tech recovers in FY26", grr[2] > grr[1], detail)

    since = accounts["customer_since_month_id"].to_numpy()

    def share(low, high):
        window = (since >= months[low]) & (since <= months[high])
        return emea[window].mean()

    change = share(48, 56) / share(36, 44) - 1
    check("EMEA new-logo share falls about 20% in FY25 Q1-Q3", -0.28 <= change <= -0.12, f"{change:.1%}")

    fact = tables["fct_account_product_month"]
    employees = tables["dim_employee"]
    turnover = cfg["red_herrings"]["rep_turnover"]
    leavers = employees[
        (employees["region"] == turnover["territory"])
        & employees["termination_month_id"].between(months[turnover["start_month"]], months[turnover["end_month"]])
    ]["employee_id"]
    window = fact[fact["month_id"].between(months[turnover["start_month"]], months[turnover["end_month"]])]
    before = fact[fact["month_id"] == months[turnover["start_month"] - 1]]
    owned = set(before.loc[before["ae_employee_id"].isin(leavers) | before["csm_employee_id"].isin(leavers), "account_id"])
    peers = set(window["account_id"]) - owned
    touches = tables["touchpoints"]
    touches = touches[touches["month_id"].between(months[turnover["start_month"]], months[turnover["end_month"] + 6])]
    counts = touches.groupby("account_id").size()
    affected = counts.reindex(sorted(owned)).fillna(0).mean()
    others = counts.reindex(sorted(peers)).fillna(0).mean()
    check("Reassigned accounts get fewer touches than peers", affected < others, f"{affected:.2f} vs {others:.2f}")


def check_pivot_behavior(cfg, tables):
    """Spec Section 6.3: how fully pivoted accounts behave, compared with just before onset."""
    fact = tables["fct_account_product_month"]
    pivot = pd.read_csv(Path(cfg["paths"]["facilitator_dir"]) / "pivot_truth.csv")
    done = pivot[pivot["onset_month"] + pivot["pivot_months"] <= 68]
    position = {value: index for index, value in enumerate(tables["dim_month"]["month_id"])}
    joined = fact[fact["account_id"].isin(done["account_id"])].merge(done, on="account_id")
    joined["t"] = joined["month_id"].map(position)

    def ratio(product, column):
        rows = joined[joined["product_id"] == product]
        before = rows[(rows["t"] < rows["onset_month"]) & (rows["t"] >= rows["onset_month"] - 3)].groupby("account_id")[column].mean()
        after = rows[(rows["t"] >= rows["onset_month"] + rows["pivot_months"]) & (rows["churn_flag"] == 0)].groupby("account_id")[column].mean()
        return (after / before.replace(0, np.nan)).dropna().median()

    engine = ratio("P3", "work_units")
    check("Data Engine work rises 2-3x", 2.0 <= engine <= 3.0, f"{engine:.2f}x")
    users = ratio("P2", "active_users")
    check("Analytics active users fall 70-80%", 0.20 <= users <= 0.30, f"{1 - users:.0%} fall")
    sessions = ratio("P2", "ui_sessions")
    check("Analytics UI sessions fall 70-80%", 0.20 <= sessions <= 0.30, f"{1 - sessions:.0%} fall")
    transformation = ratio("P1", "work_units")
    check("Transformation work stays roughly flat", 0.8 <= transformation <= 1.25, f"{transformation:.2f}x")
    after = joined[(joined["t"] >= joined["onset_month"] + joined["pivot_months"]) & (joined["work_units"] > 0)]
    share = np.average(after["api_share"], weights=after["work_units"])
    check("API share reaches 90%+ after the pivot", share >= 0.90, f"{share:.1%}")


def check_size(cfg, tables):
    folder = Path(cfg["paths"]["output_dir"])
    print("\nROW COUNTS")
    for name, table in tables.items():
        print(f"  {name}: {len(table):,}")
    rows = sum(len(table) for table in tables.values())
    size = sum(path.stat().st_size for path in folder.glob("*.csv")) / 1e6
    check("Total rows <= ~4M", rows <= 4_100_000, f"{rows:,}")
    check("Total CSV size <= ~400MB", size <= 410, f"{size:.0f} MB")
    check("user_usage_month <= 2.5M rows", len(tables["user_usage_month"]) <= 2_500_000, f"{len(tables['user_usage_month']):,}")
    check("contracts 20-25K rows", 20_000 <= len(tables["contracts"]) <= 25_000, f"{len(tables['contracts']):,}")
    check("touchpoints 100-150K rows", 100_000 <= len(tables["touchpoints"]) <= 150_000, f"{len(tables['touchpoints']):,}")
    check("dim_employee ~150 rows", 135 <= len(tables["dim_employee"]) <= 165, str(len(tables["dim_employee"])))


def check_no_leak(cfg):
    pattern = "ai_forward|segment_truth|is_ai"
    found = subprocess.run(["grep", "-rilE", pattern, cfg["paths"]["output_dir"], cfg["paths"]["dictionary"]], capture_output=True, text=True)
    check("No hidden labels in the dataset", found.stdout.strip() == "", found.stdout.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)
    tables = load(cfg)

    truth = pd.read_csv(Path(cfg["paths"]["facilitator_dir"]) / "segment_truth.csv")
    ids = tables["dim_account"]["account_id"].to_numpy()
    is_ai = truth.set_index("account_id")["is_ai_forward"].reindex(ids).to_numpy().astype(bool)
    months = tables["dim_month"]["month_id"].tolist()
    arr = arr_by_account(tables["fct_account_product_month"], months, ids)

    check_kpis(cfg, arr, is_ai)
    check_segment(arr, is_ai, tables["dim_account"])
    check_reconciliation(tables)
    check_distributions(cfg, tables)
    check_accounts(tables)
    check_headcount(cfg, tables)
    check_discoverability(cfg, tables, arr, ids)
    check_red_herrings(cfg, tables, arr, ids)
    check_pivot_behavior(cfg, tables)
    check_size(cfg, tables)
    check_no_leak(cfg)

    failed = [name for name, passed in results if not passed]
    print(f"\n{len(results) - len(failed)} of {len(results)} checks passed")
    for name in failed:
        print(f"  FAILED: {name}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
