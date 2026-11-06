"""Shared calendar helpers and deterministic random streams."""
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yaml


def load_config(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def stream(cfg, name):
    """Return a generator for one named stage, so editing one stage leaves the others unchanged."""
    key = [ord(character) for character in name]
    return np.random.default_rng(np.random.SeedSequence([cfg["seed"], *key]))


@dataclass(frozen=True)
class Calendar:
    months: int
    month_ids: np.ndarray

    def month_id(self, t):
        return int(self.month_ids[t])


def build_calendar(cfg):
    window = cfg["window"]
    dates = pd.date_range(
        f"{window['start_year']}-{window['start_month']:02d}-01", periods=window["months"], freq="MS"
    )
    return Calendar(window["months"], (dates.year * 100 + dates.month).to_numpy())


def future_month_id(cfg, t):
    """Month id for any offset from the window start, including past the window end."""
    window = cfg["window"]
    index = window["start_year"] * 12 + (window["start_month"] - 1) + t
    return (index // 12) * 100 + index % 12 + 1


def dim_month(cfg):
    window = cfg["window"]
    dates = pd.date_range(
        f"{window['start_year']}-{window['start_month']:02d}-01", periods=window["months"], freq="MS"
    )
    t = np.arange(window["months"])
    return pd.DataFrame(
        {
            "month_id": dates.year * 100 + dates.month,
            "month_start_date": dates.strftime("%Y-%m-%d"),
            "fiscal_year": [f"FY{21 + i // 12}" for i in t],
            "fiscal_quarter": [f"FY{21 + i // 12}-Q{(i % 12) // 3 + 1}" for i in t],
            "calendar_year": dates.year,
            "calendar_quarter": [f"{d.year}-Q{d.quarter}" for d in dates],
        }
    )


def fiscal_index(t):
    return min(int(t) // 12, 5)
