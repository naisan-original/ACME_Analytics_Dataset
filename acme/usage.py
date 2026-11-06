"""User-level simulation (spec Sections 2.6, 6.1, 6.3).

The full population is simulated one account-product at a time, so central-fact totals come from
every user. Only a stratified sample of users is kept for export.
"""
from statistics import NormalDist

import numpy as np
import pandas as pd

from .common import fiscal_index, stream
from .simulate import api_share_at

DEPARTMENTS = ["Analytics", "Finance", "Ops", "Sales", "Marketing", "Engineering", "Data Eng", "Exec"]
DEPARTMENT_WEIGHTS = {
    "P1": [0.20, 0.05, 0.10, 0.02, 0.03, 0.25, 0.34, 0.01],
    "P2": [0.28, 0.17, 0.14, 0.14, 0.13, 0.06, 0.05, 0.03],
    "P3": [0.18, 0.03, 0.05, 0.01, 0.02, 0.33, 0.37, 0.01],
    "P4": [0.30, 0.03, 0.04, 0.02, 0.05, 0.28, 0.27, 0.01],
}
HUMAN_PERSONAS = np.array(["Viewer", "Explorer", "Creator", "Admin"])
INVERSE_CDF = NormalDist().inv_cdf
SERVICE_ACCOUNT_BASE = 900_000  # keeps service account ids clear of human user ids
FADING_SHARE = 0.45  # Explorers and Creators as a share of human users


def baseline_api_share(cfg, t, account_noise):
    return cfg["usage"]["baseline_api_share_by_fy"][fiscal_index(t)] * account_noise


def seat_timeline(contracts, last_month):
    """Per-month seats, price, utilization and contract for one account-product."""
    start = contracts[0].start
    end = min(contracts[-1].end, last_month)
    months = np.arange(start, end + 1)
    seats = np.zeros(len(months), dtype=np.int64)
    price = np.zeros(len(months))
    util = np.zeros(len(months))
    for contract in contracts:
        lo = max(contract.start - start, 0)
        hi = min(contract.end, end) - start + 1
        seats[lo:hi] = contract.seats
        price[lo:hi] = contract.price
        util[lo:hi] = contract.util
    return months, seats, price, util


def ai_curves(cfg, account, product, months, rng):
    """Per-month UI multiplier and API share for a hidden-segment product.

    Total work follows the product's target multiplier. UI work is what remains once the API share
    is taken out, so share, UI decline and total work always agree with each other.
    """
    ai = cfg["ai_forward"]
    ui = np.ones(len(months))
    share = np.zeros(len(months))
    if not account.is_ai:
        return ui, share
    settings = ai["product_curves"][product]
    target = rng.uniform(*settings["work_multiplier"])
    curve = np.array([api_share_at(cfg, account, t) for t in months])
    start = ai["start_api_share"]
    share = start + (curve - start) * (settings["end_api_share"] - start) / (ai["end_api_share"] - start)
    progress = np.clip((months - account.onset) / max(account.pivot_months, 1), 0, 1)
    ui = (1 - share) / (1 - start) * (1 + (target - 1) * progress)
    return np.clip(ui, 0.03, 1.0), share


def simulate_product(cfg, rng, account, product, contracts, last_month, account_people, api_noise):
    """Simulate one account-product. Returns monthly aggregates and sampled user rows."""
    usage = cfg["usage"]
    months, seats, price, util = seat_timeline(contracts, last_month)
    ui_mult, ai_share = ai_curves(cfg, account, product, months, rng)
    fade_keep = 0.35 + 0.65 * ui_mult
    # Humans leave ahead of the seat cuts, so measure the decline against seats held at onset.
    seat_scale = np.ones(len(months))
    if account.is_ai:
        held = seats[months <= account.onset]
        seat_scale = np.where(months > account.onset, (held[-1] if len(held) else seats[0]) / np.maximum(seats, 1), 1.0)
    # Explorers and Creators fade faster than others, so the overall rate is lifted to compensate.
    overall = util * ui_mult * seat_scale / (1 - FADING_SHARE * (1 - fade_keep)) if account.is_ai else util
    target = np.clip(overall + rng.normal(0, cfg["utilization"]["monthly_noise"], len(months)), 0.01, 0.95)

    users = int(seats.max())
    count = len(months)
    latent = rng.normal(0, 1, users)
    noise = usage["active_noise"]
    scale = (1 + noise**2) ** 0.5
    thresholds = np.array([scale * INVERSE_CDF(1 - value) for value in target])
    in_seat = np.arange(users)[:, None] < seats[None, :]
    active = (latent[:, None] + noise * rng.normal(0, 1, (users, count)) > thresholds[None, :]) & in_seat

    personas = account_people["persona"][:users]
    departments = account_people["department"][product][:users]
    if account.is_ai:
        fading = np.isin(personas, ["Explorer", "Creator"])[:, None]
        keep = rng.random((users, count)) < fade_keep[None, :]
        active &= ~fading | keep

    hours = np.where(
        active,
        np.exp(
            usage["hours_log_mean"]
            + usage["hours_user_sigma"] * latent[:, None]
            + usage["hours_month_sigma"] * rng.normal(0, 1, (users, count))
        ),
        0.0,
    )
    hours = np.minimum(hours, 200.0)
    sessions = np.where(active, np.maximum(rng.poisson(hours / usage["session_hours"]), 1), 0)

    rate = usage["work_units_per_hour"][product]
    calls_per_unit = usage["api_calls_per_work_unit"][product]
    user_ui_work = hours * rate
    ui_work = user_ui_work.sum(axis=0)

    baseline = np.array([baseline_api_share(cfg, t, api_noise) for t in months])
    share = np.maximum(baseline, ai_share)
    api_work = ui_work * share / (1 - share)
    if account.is_ai:
        # Size API work from pre-pivot activity, so a few idle humans cannot zero out agent traffic.
        before = ui_work[months < account.onset][-6:]
        typical = np.exp(usage["hours_log_mean"] + (usage["hours_user_sigma"] ** 2 + usage["hours_month_sigma"] ** 2) / 2)
        base = before.mean() if len(before) and before.mean() > 0 else seats[0] * util[0] * typical * rate
        after = months >= account.onset
        api_work[after] = base * ui_mult[after] * share[after] / (1 - share[after])

    capacity = usage["service_account_capacity"] / calls_per_unit
    service_share = usage["service_account_api_share"]
    service_work = api_work * service_share
    service_count = np.ceil(service_work / capacity).astype(np.int64)
    service_count = np.where(api_work > 0, np.maximum(service_count, 1), 0)
    human_api_work = api_work - service_work

    creators = np.isin(personas, ["Creator", "Admin"])[:, None] & active
    weights = np.where(creators, hours + 1.0, 0.0)
    totals = weights.sum(axis=0)
    fallback = totals == 0
    human_api_cells = np.where(totals > 0, weights / np.maximum(totals, 1e-9), 0.0) * human_api_work[None, :]
    # With no eligible human this month, the service accounts take the remainder.
    service_work = service_work + np.where(fallback, human_api_work, 0.0)
    service_count = np.where((service_work > 0) & (service_count == 0), 1, service_count)

    total_work = ui_work + api_work
    aggregates = pd.DataFrame(
        {
            "t": months,
            "seats": seats,
            "price": price,
            "active_users": active.sum(axis=0),
            "ui_sessions": sessions.sum(axis=0),
            "ui_hours": hours.sum(axis=0).round(1),
            "api_calls": np.round(api_work * calls_per_unit).astype(np.int64),
            "work_units": np.round(total_work).astype(np.int64),
            "api_share": np.round(np.where(total_work > 0, api_work / np.maximum(total_work, 1e-9), 0), 4),
            "weekly_active": ((hours >= usage["weekly_active_hours"]).sum(axis=0)),
            "near_full_time": ((hours >= usage["near_full_time_hours"]).sum(axis=0)),
        }
    )

    ever_active = active.any(axis=1)
    heavy = (hours >= usage["heavy_user_hours"]).any(axis=1) & ever_active
    light = np.where(ever_active & ~heavy)[0]
    wanted = max(int(np.ceil(len(light) * usage["sample_rate"])), usage["min_sampled_users"])
    wanted = min(wanted, len(light))
    sampled = rng.choice(light, size=wanted, replace=False) if wanted else np.array([], dtype=np.int64)
    weight = len(light) / wanted if wanted else 1.0

    frames = []
    for group, group_weight in ((np.where(heavy)[0], 1.0), (sampled, weight)):
        if len(group) == 0:
            continue
        rows, columns = np.nonzero(active[group])
        people = group[rows]
        api_units = human_api_cells[people, columns]
        frames.append(
            pd.DataFrame(
                {
                    "user_index": people,
                    "t": months[columns],
                    "department": departments[people],
                    "persona": personas[people],
                    "ui_sessions": sessions[people, columns],
                    "ui_hours": hours[people, columns].round(1),
                    "api_calls": np.round(api_units * calls_per_unit).astype(np.int64),
                    "work_units": np.round(user_ui_work[people, columns] + api_units).astype(np.int64),
                    "sample_weight": round(group_weight, 4),
                }
            )
        )

    service_rows = []
    per_account = np.where(service_count > 0, service_work / np.maximum(service_count, 1), 0.0)
    for column, number in enumerate(service_count):
        if number == 0:
            continue
        spread = rng.dirichlet(np.full(number, 4.0)) * number
        for slot in range(number):
            units = per_account[column] * spread[slot]
            service_rows.append(
                (SERVICE_ACCOUNT_BASE + slot, months[column], "Data Eng" if slot % 2 == 0 else "Engineering", "Service Account",
                 0, 0.0, int(round(units * calls_per_unit)), int(round(units)), 1.0)
            )
    if service_rows:
        frames.append(
            pd.DataFrame(
                service_rows,
                columns=["user_index", "t", "department", "persona", "ui_sessions", "ui_hours",
                         "api_calls", "work_units", "sample_weight"],
            )
        )
    return aggregates, frames


def build_people(cfg, rng, max_users):
    """Stable personas across an account's products, so one person keeps one role."""
    latent = rng.random(max_users)
    persona = np.where(latent < 0.02, "Admin", np.where(latent < 0.17, "Creator", np.where(latent < 0.47, "Explorer", "Viewer")))
    return {
        "persona": persona,
        "department": {
            product: np.array(DEPARTMENTS)[rng.choice(len(DEPARTMENTS), size=max_users, p=weights)]
            for product, weights in DEPARTMENT_WEIGHTS.items()
        },
    }


def run(cfg, customers, ids, calendar):
    """Simulate all users. Returns per-product monthly aggregates and exported sampled rows."""
    rng = stream(cfg, "usage")
    usage = cfg["usage"]
    last_month = calendar.months - 1
    aggregates = []
    sampled = []
    for account in customers:
        by_product = {}
        for contract in account.contracts:
            by_product.setdefault(contract.product, []).append(contract)
        max_users = max(contract.seats for contract in account.contracts) + 1
        people = build_people(cfg, rng, max_users)
        api_noise = float(np.exp(rng.normal(0, usage["api_share_noise"])))
        for product, contracts in by_product.items():
            contracts.sort(key=lambda contract: contract.start)
            monthly, frames = simulate_product(cfg, rng, account, product, contracts, last_month, people, api_noise)
            monthly["account"] = account.index
            monthly["product_id"] = product
            aggregates.append(monthly)
            for frame in frames:
                frame["account"] = account.index
                frame["product_id"] = product
                sampled.append(frame)
    return pd.concat(aggregates, ignore_index=True), pd.concat(sampled, ignore_index=True)
