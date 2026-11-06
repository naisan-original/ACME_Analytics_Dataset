"""Generate the ACME Analytics dataset: python generate.py --config config.yaml"""
import argparse
import copy
import os
import shutil
import time
from pathlib import Path

import numpy as np

from acme import accounts as accounts_module
from acme import contracts as contracts_module
from acme import export, people, simulate, touchpoints, usage
from acme.common import build_calendar, dim_month, load_config, stream
from acme.metrics import arr_matrix, kpi_table
from acme.products import dim_product


BUILD_DIR = Path("output.building")


def staging_config(cfg):
    """Same config, with every output path pointed at the build folder."""
    staged = copy.deepcopy(cfg)
    staged["paths"].update(
        output_dir=str(BUILD_DIR / "lite"),
        dictionary=str(BUILD_DIR / "data_dictionary.md"),
        facilitator_dir=str(BUILD_DIR / "facilitator"),
    )
    return staged


def publish(cfg):
    """Swap the finished build into place, so nobody can pick up a half-written dataset."""
    final = Path(cfg["paths"]["output_dir"])
    final.parent.mkdir(parents=True, exist_ok=True)
    if final.exists():
        final.rename(BUILD_DIR / "lite.previous")
    (BUILD_DIR / "lite").rename(final)
    os.replace(BUILD_DIR / "data_dictionary.md", cfg["paths"]["dictionary"])
    facilitator = Path(cfg["paths"]["facilitator_dir"])
    facilitator.mkdir(parents=True, exist_ok=True)
    for path in (BUILD_DIR / "facilitator").iterdir():
        os.replace(path, facilitator / path.name)
    # The answer key quotes the data, so it must be rebuilt for each new dataset.
    (facilitator / "answer_key.md").unlink(missing_ok=True)
    shutil.rmtree(BUILD_DIR)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    started = time.time()

    cfg = load_config(args.config)
    calendar = build_calendar(cfg)
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    staged = staging_config(cfg)

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
    counts = export.write_tables(staged, tables)
    export.write_dictionary(staged, counts)
    export.write_facilitator(staged, accounts, is_ai, customers)
    publish(cfg)
    print({name: f"{count:,}" for name, count in counts.items()})
    print(f"total rows: {sum(counts.values()):,} in {time.time() - started:.0f}s")
    print("Next: uv run python validate.py, then uv run python tools/answer_key.py")


if __name__ == "__main__":
    main()
