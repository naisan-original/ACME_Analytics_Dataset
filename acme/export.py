"""Assemble the star schema, write CSVs, the data dictionary and the facilitator files."""
from pathlib import Path

import numpy as np
import pandas as pd

from .accounts import tech_signals
from .common import stream
from .products import list_price

FACT_COLUMNS = [
    "month_id", "account_id", "product_id", "ae_employee_id", "csm_employee_id", "licensed_seats",
    "list_price_per_seat_month", "net_price_per_seat_month", "mrr", "arr", "active_users", "ui_sessions",
    "ui_hours", "api_calls", "work_units", "api_share", "renewal_month_flag", "arr_change_type", "churn_flag",
]


def central_fact(cfg, customers, aggregates, accounts, employees, ae, csm, calendar):
    table = aggregates.sort_values(["account", "product_id", "t"], kind="stable").reset_index(drop=True)
    table["mrr"] = table["seats"] * table["price"]
    table["arr"] = table["mrr"] * 12
    table["churn_flag"] = 0

    renewal_starts = {
        (contract.account, contract.product, contract.start)
        for account in customers for contract in account.contracts if contract.contract_type == "Renewal"
    }
    churn_rows = []
    for account in customers:
        for contract in account.contracts:
            month = contract.end + 1
            if contract.outcome == "Churned" and month < calendar.months:
                churn_rows.append({"account": contract.account, "product_id": contract.product, "t": month,
                                   "seats": 0, "price": contract.price, "mrr": 0.0, "arr": 0.0, "churn_flag": 1})
    if churn_rows:
        table = pd.concat([table, pd.DataFrame(churn_rows)], ignore_index=True)
        table = table.sort_values(["account", "product_id", "t"], kind="stable").reset_index(drop=True)
    for column in ("active_users", "ui_sessions", "ui_hours", "api_calls", "work_units", "api_share"):
        table[column] = table[column].fillna(0)

    previous = table.groupby(["account", "product_id"])["arr"].shift()
    change = np.select(
        [table["churn_flag"] == 1, previous.isna(), table["arr"] > previous * 1.0005, table["arr"] < previous * 0.9995],
        ["churn", "new", "expansion", "contraction"],
        default="none",
    )
    table["arr_change_type"] = change
    keys = zip(table["account"], table["product_id"], table["t"])
    table["renewal_month_flag"] = [
        int(key in renewal_starts or churned == 1) for key, churned in zip(keys, table["churn_flag"])
    ]

    account_ids = accounts["account_id"].to_numpy()
    employee_ids = np.append(employees["employee_id"].to_numpy(), None)
    table["month_id"] = calendar.month_ids[table["t"].to_numpy()]
    table["account_id"] = account_ids[table["account"].to_numpy()]
    table["ae_employee_id"] = employee_ids[ae[table["account"].to_numpy(), table["t"].to_numpy()]]
    table["csm_employee_id"] = employee_ids[csm[table["account"].to_numpy(), table["t"].to_numpy()]]
    table["licensed_seats"] = table["seats"].astype(int)
    table["net_price_per_seat_month"] = table["price"].round(2)
    table["list_price_per_seat_month"] = table["product_id"].map(lambda product: list_price(cfg, product))
    table["mrr"] = table["mrr"].round(2)
    table["arr"] = table["arr"].round(2)
    for column in ("active_users", "ui_sessions", "api_calls", "work_units"):
        table[column] = table[column].astype("int64")
    return table


def dim_account(cfg, accounts, customers, is_ai, calendar):
    rng = stream(cfg, "signals")
    since = {account.index: account.since for account in customers}
    churn = {account.index: account.churn for account in customers if account.churn >= 0}
    status, since_ids, churn_ids = [], [], []
    for index in range(len(accounts)):
        if index in churn:
            status.append("Former Customer")
        elif index in since:
            status.append("Customer")
        else:
            status.append("Prospect")
        since_ids.append(calendar.month_id(since[index]) if index in since else pd.NA)
        churn_ids.append(calendar.month_id(churn[index]) if index in churn else pd.NA)
    return pd.DataFrame(
        {
            "account_id": accounts["account_id"],
            "account_name": accounts["name"],
            "hq_country": accounts["country"],
            "hq_city": accounts["hq_city"],
            "region": accounts["region"],
            "industry": accounts["industry"],
            "sub_industry": accounts["sub_industry"],
            "annual_revenue_band": accounts["annual_revenue_band"],
            "employee_band": accounts["employee_band"],
            "fortune_rank": accounts["fortune_rank"],
            "global2000_rank": accounts["global2000_rank"],
            "segment": accounts["segment"],
            "account_status": status,
            "customer_since_month_id": pd.array(since_ids, dtype="Int64"),
            "churn_month_id": pd.array(churn_ids, dtype="Int64"),
            "tech_signals": tech_signals(cfg, rng, accounts, is_ai),
        }
    )


def user_usage(sampled, accounts, calendar):
    table = sampled
    account_ids = accounts["account_id"].to_numpy()
    numbers = table["account"].to_numpy().astype(np.int64) + 1
    user_ids = numbers * 1_000_000 + table["user_index"].to_numpy()
    output = pd.DataFrame(
        {
            "user_id": ["U" + str(value) for value in user_ids],
            "account_id": account_ids[table["account"].to_numpy()],
            "product_id": table["product_id"],
            "month_id": calendar.month_ids[table["t"].to_numpy()],
            "user_department": table["department"],
            "user_persona": table["persona"],
            "ui_sessions": table["ui_sessions"],
            "ui_hours": table["ui_hours"],
            "api_calls": table["api_calls"],
            "work_units": table["work_units"],
            "sample_weight": table["sample_weight"],
        }
    )
    return output.sort_values(["month_id", "account_id", "product_id", "user_id"], kind="stable").reset_index(drop=True)


DICTIONARY = {
    "fct_account_product_month": (
        "Central fact. One row per account, product and month while a subscription is active, plus the "
        "churn month with arr = 0 and churn_flag = 1.",
        {
            "month_id": "FK to dim_month (YYYYMM)", "account_id": "FK to dim_account", "product_id": "FK to dim_product",
            "ae_employee_id": "FK to dim_employee. Account Executive that month", "csm_employee_id": "FK to dim_employee. Customer Success Manager that month",
            "licensed_seats": "Contracted seats", "list_price_per_seat_month": "List price per seat per month",
            "net_price_per_seat_month": "Net price after volume discount", "mrr": "Monthly recurring revenue",
            "arr": "mrr x 12", "active_users": "Distinct users with at least one UI session in the month",
            "ui_sessions": "UI sessions", "ui_hours": "UI hours", "api_calls": "Monthly API request count",
            "work_units": "Product-specific activity. See dim_product.work_unit_label", "api_share": "API work units / total work units, 0 to 1",
            "renewal_month_flag": "1 in a renewal month", "arr_change_type": "none, new, expansion, contraction or churn. Set by ARR movement, so a price uplift on flat seats is an expansion",
            "churn_flag": "1 in the month a product subscription ends",
        },
    ),
    "dim_account": (
        "One row per account: customers, former customers and prospects.",
        {
            "account_id": "Primary key", "account_name": "Company name", "hq_country": "Headquarters country", "hq_city": "Headquarters city",
            "region": "NA, EMEA, APAC or LATAM", "industry": "Industry", "sub_industry": "Sub-industry",
            "annual_revenue_band": "Revenue band, not a reported figure", "employee_band": "Employee band",
            "fortune_rank": "Approximate US rank from public revenue data. Nullable", "global2000_rank": "Approximate global rank from public revenue data. Nullable",
            "segment": "Strategic, Enterprise or Upper Mid-Market", "account_status": "Customer, Former Customer or Prospect",
            "customer_since_month_id": "First paying month. Nullable", "churn_month_id": "Month the account fully churned. Nullable",
            "tech_signals": "Semicolon list of marketing-enrichment topics",
        },
    ),
    "dim_product": ("The four ACME products. All are seat-priced, and API calls do not consume seats.",
                    {"product_id": "Primary key", "product_name": "Name", "work_unit_label": "What work_units counts", "price_multiplier": "Price multiplier versus the $30 base"}),
    "dim_month": ("72 months, Nov 2020 to Oct 2026. The fiscal year ends Oct 31.",
                  {"month_id": "Primary key (YYYYMM)", "month_start_date": "First day of month", "fiscal_year": "FY21 to FY26", "fiscal_quarter": "Fiscal quarter", "calendar_year": "Calendar year", "calendar_quarter": "Calendar quarter"}),
    "dim_employee": ("Sales and customer success staff, including leavers.",
                     {"employee_id": "Primary key", "name": "Fictional name", "role": "AE, CSM, Sales Leader or CS Leader", "region": "Territory", "hire_month_id": "Hire month", "termination_month_id": "Last month. Nullable", "quota_arr": "Annual quota. AEs only"}),
    "user_usage_month": (
        "Stratified sample of users: one row per user, product and month with activity.",
        {"user_id": "User key", "account_id": "FK to dim_account", "product_id": "FK to dim_product", "month_id": "FK to dim_month",
         "user_department": "Department", "user_persona": "Viewer, Explorer, Creator, Admin or Service Account", "ui_sessions": "UI sessions", "ui_hours": "UI hours",
         "api_calls": "API requests", "work_units": "Activity", "sample_weight": "Multiply measures by this to estimate the full population"},
    ),
    "contracts": ("One row per contract. Sum ACV of active contracts to reconcile to central ARR.",
                  {"contract_id": "Primary key", "account_id": "FK to dim_account", "product_id": "FK to dim_product", "contract_type": "New, Renewal or Expansion Add-on",
                   "start_month_id": "First month", "end_month_id": "Last month, which can fall after the data window", "term_months": "Length in months. Add-ons co-term, so they can be short", "seats": "Seats",
                   "net_price_per_seat_month": "Net price", "acv": "Annual contract value", "outcome": "Renewed Flat, Renewed Up, Renewed Down, Churned or Active. Based on seats", "ae_employee_id": "FK to dim_employee"}),
    "touchpoints": ("Logged customer and prospect interactions.",
                    {"touchpoint_id": "Primary key", "account_id": "FK to dim_account", "employee_id": "FK to dim_employee", "month_id": "FK to dim_month", "touch_date": "Date",
                     "channel": "Call, Email, QBR, Onsite or Support Escalation", "touch_type": "Discovery, Onboarding, Check-in, QBR, Renewal, Expansion or Risk", "sentiment": "-2 to +2", "notes": "Free-text notes"}),
}


def write_dictionary(cfg, row_counts):
    lines = ["# ACME Analytics dataset: data dictionary", "", f"synthetic_notice: {cfg['synthetic_notice']}", ""]
    lines += ["Star schema: every satellite joins directly to `fct_account_product_month`.", "",
              "## Metric definitions", "",
              "- GRR: (ARR from accounts active 12 months ago, minus churn and contraction) / their ARR 12 months ago, capped at 100%.",
              "- NDR: the same cohort including expansion.",
              "- Weekly active: at least 10 UI hours in the month, a proxy because the data has no weekly grain.", "",
              "## Sampling in user_usage_month", "",
              "The central fact is computed from the full simulated population. This file holds a sample: every "
              "user with 40 or more UI hours in any month, every Service Account, and a random sample of the rest "
              "within each account and product. Use `sample_weight` to estimate full-population totals.", ""]
    for table, (description, columns) in DICTIONARY.items():
        lines += [f"## {table}", "", f"{description} Rows: {row_counts.get(table, 0):,}.", "", "| Column | Description |", "|---|---|"]
        lines += [f"| {column} | {text} |" for column, text in columns.items()]
        lines.append("")
    path = Path(cfg["paths"]["dictionary"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_facilitator(cfg, accounts, is_ai, customers):
    folder = Path(cfg["paths"]["facilitator_dir"])
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"account_id": accounts["account_id"], "is_ai_forward": is_ai.astype(int)}).to_csv(folder / "segment_truth.csv", index=False)
    pd.DataFrame(
        [{"account_id": accounts["account_id"].iloc[a.index], "onset_month": a.onset, "pivot_months": a.pivot_months} for a in customers if a.is_ai]
    ).to_csv(folder / "pivot_truth.csv", index=False)
    accounts.loc[accounts["is_fictional"], ["account_id", "name"]].to_csv(folder / "fictional_accounts.csv", index=False)


def write_tables(cfg, tables):
    folder = Path(cfg["paths"]["output_dir"])
    folder.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(folder / f"{name}.csv", index=False)
    return {name: len(table) for name, table in tables.items()}
