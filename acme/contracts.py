"""Contracts table (spec Section 2.7)."""
import pandas as pd

from .common import future_month_id


def build(cfg, customers, accounts, employees, calendar):
    account_ids = accounts["account_id"].to_numpy()
    employee_ids = employees["employee_id"].to_numpy()
    rows = []
    for account in customers:
        for contract in sorted(account.contracts, key=lambda item: (item.start, item.product)):
            months = contract.end - contract.start + 1
            rows.append(
                {
                    "account_id": account_ids[contract.account],
                    "product_id": contract.product,
                    "contract_type": contract.contract_type,
                    "start_month_id": calendar.month_id(contract.start),
                    "end_month_id": future_month_id(cfg, contract.end),
                    "term_months": months,
                    "seats": contract.seats,
                    "net_price_per_seat_month": round(contract.price, 2),
                    "acv": round(contract.seats * contract.price * 12, 2),
                    "outcome": contract.outcome,
                    "ae_employee_id": employee_ids[contract.ae] if contract.ae >= 0 else None,
                }
            )
    table = pd.DataFrame(rows)
    table = table.sort_values(["start_month_id", "account_id", "product_id"], kind="stable").reset_index(drop=True)
    table.insert(0, "contract_id", [f"C{index + 1:06d}" for index in range(len(table))])
    return table
