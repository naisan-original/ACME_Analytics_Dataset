"""Generate the ACME Analytics dataset: python generate.py --config config.yaml"""
import argparse
import time

import numpy as np

from acme import accounts as accounts_module
from acme import contracts as contracts_module
from acme import export, people, simulate, touchpoints, usage
from acme.common import build_calendar, dim_month, load_config, stream
from acme.metrics import arr_matrix, kpi_table
from acme.products import dim_product


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    started = time.time()

    cfg = load_config(args.config)
    calendar = build_calendar(cfg)

    accounts = accounts_module.build(cfg)
    print(f"accounts: {len(accounts):,} ({int(accounts['is_fictional'].sum()):,} fictional)", flush=True)
    print(accounts["bucket"].value_counts().to_string(), flush=True)

    employees = people.build_employees(cfg, calendar)
    rng = stream(cfg, "selection")
    chosen, since = simulate.select_customers(cfg, accounts, rng)
    is_ai = simulate.assign_ai_forward(cfg, accounts, chosen, since, rng)
    ae, csm, disrupted = people.assign_owners(cfg, employees, accounts["territory"].to_numpy(), since, calendar)
    customers = simulate.run(cfg, accounts, ae, disrupted, chosen, since, is_ai, calendar)
    print(f"customers ever: {len(customers):,}", flush=True)

    rows = [(c.account, c.start, c.end, c.seats, c.price) for a in customers for c in a.contracts]
    arr = arr_matrix(rows, len(accounts), calendar.months)
    print(kpi_table(arr).to_string(index=False), flush=True)

    aggregates, sampled = usage.run(cfg, customers, accounts, calendar)
    print(f"usage: {len(aggregates):,} account-product months, {len(sampled):,} sampled user rows", flush=True)

    tables = {
        "fct_account_product_month": export.central_fact(cfg, customers, aggregates, accounts, employees, ae, csm, calendar)[export.FACT_COLUMNS],
        "dim_account": export.dim_account(cfg, accounts, customers, is_ai, calendar),
        "dim_product": dim_product(),
        "dim_month": dim_month(cfg),
        "dim_employee": people.dim_employee(employees, calendar),
        "user_usage_month": export.user_usage(sampled, accounts, calendar),
        "contracts": contracts_module.build(cfg, customers, accounts, employees, calendar),
        "touchpoints": touchpoints.run(cfg, customers, accounts, employees, ae, csm, disrupted, arr, calendar),
    }
    counts = export.write_tables(cfg, tables)
    export.write_dictionary(cfg, counts)
    export.write_facilitator(cfg, accounts, is_ai, customers)
    print({name: f"{count:,}" for name, count in counts.items()})
    print(f"total rows: {sum(counts.values()):,} in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
