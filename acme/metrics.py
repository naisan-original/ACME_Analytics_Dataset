"""KPI definitions from spec Section 8, shared by calibration and validate.py."""
import numpy as np
import pandas as pd


def arr_matrix(contracts, accounts_count, months):
    """ARR per account per month from contracts, in dollars."""
    arr = np.zeros((accounts_count, months))
    for account, start, end, seats, price in contracts:
        arr[account, start : min(end, months - 1) + 1] += seats * price * 12
    return arr


def retention(arr, fy, mask=None):
    """GRR and NDR at a fiscal year end, over accounts active 12 months earlier."""
    end = fy * 12 + 11
    begin = max(end - 12, 0)
    selected = arr if mask is None else arr[mask]
    cohort = selected[:, begin] > 0
    base = selected[cohort, begin].sum()
    if base == 0:
        return np.nan, np.nan
    now = selected[cohort, end]
    grr = np.minimum(now, selected[cohort, begin]).sum() / base
    return min(grr, 1.0) * 100, now.sum() / base * 100


def kpi_table(arr, mask=None):
    selected = arr if mask is None else arr[mask]
    rows = []
    for fy in range(6):
        end = fy * 12 + 11
        grr, ndr = retention(arr, fy, mask)
        rows.append(
            {
                "FY": f"FY{21 + fy}",
                "customers": int((selected[:, end] > 0).sum()),
                "arr_m": round(selected[:, end].sum() / 1e6, 1),
                "grr": round(grr, 1),
                "ndr": round(ndr, 1),
            }
        )
    return pd.DataFrame(rows)
