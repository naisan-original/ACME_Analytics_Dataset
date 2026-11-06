"""Hill-climb config parameters toward the Section 8 targets. Contract level only, so it is fast.

Usage: uv run python tools/tune.py [iterations]
Writes improved values back into config.yaml.
"""
import copy
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from acme import accounts as accounts_module
from acme import metrics, people, simulate
from acme.common import build_calendar, load_config, stream

CONFIG = Path("config.yaml")
VECTORS = [("renewal", "expansion_scale"), ("renewal", "loss_multiplier_by_fy"), ("growth", "land_acv_scale")]
SCALARS = [("ai_forward", "land_acv_multiplier"), ("growth", "starting_customer_grower_share")]


def evaluate(cfg, table, employees, calendar):
    rng = stream(cfg, "selection")
    chosen, since = simulate.select_customers(cfg, table, rng)
    is_ai = simulate.assign_ai_forward(cfg, table, chosen, since, rng)
    ae, _, disrupted = people.assign_owners(cfg, employees, table["territory"].to_numpy(), since, calendar)
    customers = simulate.run(cfg, table, ae, disrupted, chosen, since, is_ai, calendar)
    rows = [(c.account, c.start, c.end, c.seats, c.price) for a in customers for c in a.contracts]
    arr = metrics.arr_matrix(rows, len(table), calendar.months)
    return arr, is_ai


def score(cfg, arr, is_ai, table):
    targets = cfg["targets"]
    overall = metrics.kpi_table(arr)
    rest = metrics.kpi_table(arr, ~is_ai)
    total = 0.0
    for fy, row in overall.iterrows():
        total += max(abs(row["grr"] - targets["grr"][fy]) - 0.5, 0) ** 2
        total += max(abs(row["ndr"] - targets["ndr"][fy]) - 0.5, 0) ** 2
        low, high = targets["arr_low"][fy], targets["arr_high"][fy]
        middle = (low + high) / 2
        total += (max(abs(row["arr_m"] - middle) - (high - low) * 0.35, 0) / (high - low) * 20) ** 2
        total += (max(abs(row["customers"] / targets["customers"][fy] - 1) - 0.03, 0) * 100) ** 2
    for fy in (4, 5):
        total += max(targets["rest_min_grr"] + 0.3 - rest.iloc[fy]["grr"], 0) ** 2 * 3
        total += max(targets["rest_min_ndr"] + 0.5 - rest.iloc[fy]["ndr"], 0) ** 2 * 3
    fy24 = 47
    tech = (table["industry"] == "High Tech").to_numpy()
    ai_share = arr[is_ai, fy24].sum() / arr[:, fy24].sum()
    tech_share = arr[tech, fy24].sum() / arr[:, fy24].sum()
    total += (max(abs(ai_share - 0.225) - 0.02, 0) * 300) ** 2
    total += (max(abs(tech_share - 0.29) - 0.008, 0) * 300) ** 2
    return total


def mutate(cfg, rng):
    candidate = copy.deepcopy(cfg)
    if rng.random() < 0.8:
        section, key = VECTORS[rng.integers(len(VECTORS))]
        values = candidate[section][key]
        position = rng.integers(len(values))
        values[position] = round(float(values[position] * np.exp(rng.normal(0, 0.08))), 3)
    else:
        section, key = SCALARS[rng.integers(len(SCALARS))]
        candidate[section][key] = round(float(candidate[section][key] * np.exp(rng.normal(0, 0.06))), 3)
    return candidate


def save(cfg):
    text = CONFIG.read_text(encoding="utf-8")
    for section, key in VECTORS:
        values = ", ".join(f"{value:g}" for value in cfg[section][key])
        text = re.sub(rf"(^\s+{key}: )\[[^\]]*\]", lambda match: f"{match.group(1)}[{values}]", text, flags=re.M)
    for section, key in SCALARS:
        text = re.sub(rf"(^\s+{key}: )[\d.]+", lambda match: f"{match.group(1)}{cfg[section][key]:g}", text, flags=re.M)
    CONFIG.write_text(text, encoding="utf-8")


def main():
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    cfg = load_config(CONFIG)
    calendar = build_calendar(cfg)
    table = accounts_module.build(cfg)
    employees = people.build_employees(cfg, calendar)
    rng = np.random.default_rng(1)
    best = score(cfg, *evaluate(cfg, table, employees, calendar), table)
    print(f"start score {best:.1f}", flush=True)
    for step in range(iterations):
        candidate = mutate(cfg, rng)
        value = score(candidate, *evaluate(candidate, table, employees, calendar), table)
        if value < best:
            best, cfg = value, candidate
            save(cfg)
            print(f"step {step}: {best:.1f}", flush=True)
        if best < 0.5:
            break
    print(f"final score {best:.1f}")
    arr, is_ai = evaluate(cfg, table, employees, calendar)
    print(metrics.kpi_table(arr).to_string(index=False))
    print(metrics.kpi_table(arr, ~is_ai).to_string(index=False))


if __name__ == "__main__":
    main()
