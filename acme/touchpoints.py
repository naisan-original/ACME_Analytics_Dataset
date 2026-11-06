"""Customer and prospect touchpoints (spec Sections 2.8, 6.4, 7)."""
import numpy as np
import pandas as pd

from .common import stream
from .phrases import AI_THEMES, note

CHANNELS = ["Call", "Email", "QBR", "Onsite", "Support Escalation"]
THEME_TO_TYPE = {
    "discovery": "Discovery", "onboarding": "Onboarding", "adoption": "Check-in", "qbr": "QBR",
    "renewal": "Renewal", "expansion": "Expansion", "budget": "Risk", "champion": "Risk", "support": "Check-in",
    "macro": "Risk", "transition": "Check-in", "programmatic": "Check-in", "seat_pressure": "Risk",
    "llm_alternatives": "Risk",
}


def channel_for(rng, theme):
    if theme == "qbr":
        return "QBR"
    if theme == "support":
        return "Support Escalation" if rng.random() < 0.6 else "Call"
    return ["Call", "Email", "Onsite"][rng.choice(3, p=[0.55, 0.35, 0.10])]


def first_cut_month(account):
    """First contraction after onset, which sentiment leads by about two quarters."""
    cuts = [c.end + 1 for c in account.contracts if c.outcome in ("Renewed Down", "Churned") and c.end + 1 >= account.onset]
    return min(cuts) if cuts else account.onset + 12


def base_sentiment(rng, util):
    if util >= 0.35:
        return int(rng.choice([0, 1, 2], p=[0.2, 0.5, 0.3]))
    if util >= 0.20:
        return int(rng.choice([-1, 0, 1, 2], p=[0.1, 0.4, 0.4, 0.1]))
    return int(rng.choice([-2, -1, 0, 1], p=[0.15, 0.45, 0.3, 0.1]))


def ai_sentiment(rng, t, cut, lead):
    """Trend from +1/+2 down to 0/-1, starting about two quarters ahead of the first cut."""
    if t < cut - lead:
        return int(rng.choice([1, 2], p=[0.55, 0.45]))
    progress = min((t - (cut - lead)) / lead, 1.0)
    weights = np.array([0.4 * (1 - progress), 0.5, 0.1 + 0.4 * progress])
    return int(rng.choice([1, 0, -1], p=weights / weights.sum()))


def customer_theme(rng, cfg, account, t, renewal_soon, seeded, disrupted, region):
    settings = cfg["touchpoints"]
    emea = cfg["red_herrings"]["emea"]
    turnover = cfg["red_herrings"]["rep_turnover"]
    if t - account.since < 3:
        return "onboarding"
    if disrupted >= 0 and 0 <= t - disrupted < turnover["touch_dip_months"] and rng.random() < 0.5:
        return "transition"
    if region == "EMEA" and emea["start_month"] <= t <= emea["end_month"] and rng.random() < 0.3:
        return "macro"
    if account.is_ai and t >= account.onset:
        progress = min((t - account.onset) / max(account.pivot_months, 1), 1.0)
        if rng.random() < settings["ai_theme_prob_max"] * (0.3 + 0.7 * progress):
            return AI_THEMES[rng.integers(len(AI_THEMES))]
    if seeded and t >= 40 and rng.random() < 0.18:
        return AI_THEMES[rng.integers(len(AI_THEMES))]
    if renewal_soon and rng.random() < 0.55:
        return "renewal"
    options = ["adoption", "qbr", "expansion", "budget", "champion", "support"]
    return options[rng.choice(6, p=[0.32, 0.2, 0.15, 0.11, 0.07, 0.15])]


def run(cfg, customers, accounts, employees, ae, csm, disrupted, arr, calendar):
    rng = stream(cfg, "touchpoints")
    settings = cfg["touchpoints"]
    turnover = cfg["red_herrings"]["rep_turnover"]
    low, high = settings["customer_touches_per_year"]
    employee_ids = employees["employee_id"].to_numpy()
    account_ids = accounts["account_id"].to_numpy()
    lead = settings["sentiment_lead_months"]
    rows = []

    def add(account_index, employee, t, channel, theme, sentiment):
        day = int(rng.integers(1, 29))
        rows.append((account_ids[account_index], employee_ids[employee], calendar.month_id(t),
                     f"{str(calendar.month_id(t))[:4]}-{str(calendar.month_id(t))[4:]}-{day:02d}",
                     channel, THEME_TO_TYPE[theme], sentiment, note(rng, theme)))

    for account in customers:
        index = account.index
        last = account.churn - 1 if account.churn >= 0 else calendar.months - 1
        seeded = (not account.is_ai) and rng.random() < settings["ai_language_seed_share"]
        cut = first_cut_month(account) if account.is_ai else 0
        renewals = {c.end + 1 for c in account.contracts}
        region = account.region
        for t in range(account.since, last + 1):
            value = max(arr[index, t], 1.0)
            scale = np.clip(np.log(value / 15_000) / np.log(settings["full_touch_arr"] / 15_000), 0, 1)
            monthly = (low + (high - low) * scale) / 12
            lost = int(disrupted[index])
            if lost >= 0 and 0 <= t - lost < turnover["touch_dip_months"]:
                monthly *= 1 - turnover["touch_dip"]
            if rng.random() >= monthly:
                continue
            soon = any(0 <= r - t <= 2 for r in renewals)
            theme = customer_theme(rng, cfg, account, t, soon, seeded, lost, region)
            if account.is_ai:
                sentiment = ai_sentiment(rng, t, cut, lead)
            else:
                util = next((c.util for c in account.contracts if c.start <= t <= c.end), 0.3)
                sentiment = base_sentiment(rng, util)
            owner = csm[index, t] if rng.random() < 0.7 else ae[index, t]
            if owner < 0:
                owner = ae[index, t]
            add(index, owner, t, channel_for(rng, theme), theme, sentiment)

    chosen = np.zeros(len(accounts), dtype=bool)
    chosen[[account.index for account in customers]] = True
    ae_people = employees.index[employees["role"] == "AE"].to_numpy()
    hire = employees["hire"].to_numpy()
    term = employees["term"].fillna(10_000).to_numpy()
    for index in np.where(~chosen)[0]:
        if rng.random() >= settings["prospect_share_with_touches"]:
            continue
        for t in range(settings["prospect_first_month"], calendar.months):
            if rng.random() >= np.mean(settings["prospect_touches_per_year"]) / 12:
                continue
            working = ae_people[(hire[ae_people] <= t) & (term[ae_people] > t)]
            add(int(index), rng.choice(working), t, "Email" if rng.random() < 0.6 else "Call", "discovery",
                int(rng.choice([-1, 0, 1], p=[0.15, 0.6, 0.25])))

    table = pd.DataFrame(rows, columns=["account_id", "employee_id", "month_id", "touch_date", "channel",
                                        "touch_type", "sentiment", "notes"])
    table = table.sort_values(["touch_date", "account_id"], kind="stable").reset_index(drop=True)
    table.insert(0, "touchpoint_id", [f"T{index + 1:07d}" for index in range(len(table))])
    return table
