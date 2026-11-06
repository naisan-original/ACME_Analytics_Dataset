"""Customer acquisition and the contract-level simulation (spec Sections 4, 5, 6.2, 6.3, 7).

Every seat and price movement happens at a contract boundary, so contracts and the central fact
reconcile by construction.
"""
from dataclasses import dataclass, field

import numpy as np

from .common import fiscal_index, stream
from .products import draw_price, list_price, size_deal, tier_for


@dataclass
class Contract:
    account: int
    product: str
    contract_type: str
    start: int
    end: int
    seats: int
    price: float
    outcome: str = "Active"
    util: float = 0.3
    ae: int = -1


@dataclass
class Account:
    index: int
    segment: str
    region: str
    is_ai: bool
    since: int
    onset: int = -1
    pivot_months: int = 0
    t80: int = -1
    grower: bool = False
    churn: int = -1
    origin: int = 0
    contracts: list = field(default_factory=list)


def select_customers(cfg, accounts, rng):
    """Choose who becomes a customer and when, hitting the year-end customer targets."""
    growth = cfg["growth"]
    emea = cfg["red_herrings"]["emea"]
    targets = growth["fy_end_customers"]
    chosen = np.zeros(len(accounts), dtype=bool)
    since = np.full(len(accounts), 10_000, dtype=np.int32)
    is_high_tech = (accounts["industry"] == "High Tech").to_numpy()
    boost = np.where(accounts["sub_industry"].isin(cfg["ai_forward"]["sub_industries"]), cfg["ai_forward"]["sub_industry_selection_boost"], 1.0)
    segments = accounts["segment"].to_numpy()
    regions = accounts["region"].to_numpy()

    previous = growth["starting_customers"]
    for fy in range(6):
        new_logos = int(round(targets[fy] - previous * (1 - growth["expected_annual_churn_by_fy"][fy])))
        if fy == 0:
            first = rng.choice(np.where(is_high_tech)[0], size=previous, replace=False)
            chosen[first] = True
            since[first] = 0
        weights = np.zeros(len(accounts))
        ht_share = growth["high_tech_new_logo_share"][fy]
        for segment, share in growth["segment_new_logo_mix"][fy].items():
            for tech, tech_share in ((True, ht_share), (False, 1 - ht_share)):
                cell = (segments == segment) & (is_high_tech == tech) & ~chosen
                if cell.any():
                    weights[cell] = share * tech_share * boost[cell] / boost[cell].sum()
        picks = rng.choice(len(accounts), size=new_logos, replace=False, p=weights / weights.sum())
        ramp = np.linspace(0.7, 1.3, 12)
        months = fy * 12 + rng.choice(12, size=new_logos, p=ramp / ramp.sum())
        for account, month in zip(picks, months):
            in_soft_patch = emea["start_month"] <= month <= emea["end_month"]
            if regions[account] == "EMEA" and in_soft_patch and rng.random() < emea["new_logo_drop"]:
                continue
            chosen[account] = True
            since[account] = month
        previous = targets[fy]
    return chosen, since


def assign_ai_forward(cfg, accounts, chosen, since, rng):
    ai = cfg["ai_forward"]
    eligible = chosen & accounts["sub_industry"].isin(ai["sub_industries"]).to_numpy() & (since <= ai["last_landing_month"])
    return eligible & (rng.random(len(accounts)) < ai["conversion_rate"])


def draw_land_acv(cfg, rng, segment, fy, is_ai):
    bounds = cfg["growth"]["land_acv"][segment]
    low, high = np.log(bounds["low"]), np.log(bounds["high"])
    acv = np.exp(np.clip(rng.normal((low + high) / 2, (high - low) / 4), low - 0.3, high + 0.3))
    acv *= cfg["growth"]["land_acv_scale"][fy]
    return acv * (cfg["ai_forward"]["land_acv_multiplier"] if is_ai else 1.0)


def weighted_pick(rng, weights, exclude=()):
    options = {key: value for key, value in weights.items() if key not in exclude}
    if not options:
        return None
    keys = list(options)
    values = np.array([options[key] for key in keys], dtype=float)
    return keys[rng.choice(len(keys), p=values / values.sum())]


def term_for(cfg, rng, segment):
    if segment == "Strategic" and rng.random() < cfg["growth"]["strategic_multi_year_share"]:
        return int(rng.choice([24, 36]))
    return 12


def utilization_for(cfg, rng, outcome_class):
    return rng.uniform(*cfg["utilization"][outcome_class])


def api_share_at(cfg, account, t):
    """Hidden-segment API share on an S-curve from pivot onset."""
    ai = cfg["ai_forward"]
    if not account.is_ai or t < account.onset:
        return ai["start_api_share"]
    progress = (t - account.onset) / max(account.pivot_months, 1)
    curve = 1 / (1 + np.exp(-8 * (progress - 0.5)))
    return ai["start_api_share"] + (ai["end_api_share"] - ai["start_api_share"]) * curve


def month_share_reaches(cfg, account, share):
    for t in range(account.onset, account.onset + 60):
        if api_share_at(cfg, account, t) >= share:
            return t
    return account.onset + 60


def open_contract(account, product, contract_type, start, end, seats, price, ae_matrix):
    contract = Contract(account.index, product, contract_type, start, end, seats, price)
    contract.ae = int(ae_matrix[account.index, min(start, ae_matrix.shape[1] - 1)])
    account.contracts.append(contract)
    return contract


def renewed_price(cfg, rng, contract, new_seats, at_risk):
    pricing = cfg["pricing"]
    if at_risk:
        return contract.price * (1 - rng.uniform(*pricing["at_risk_discount"]))
    if new_seats > contract.seats and tier_for(cfg, new_seats) is not tier_for(cfg, contract.seats):
        return min(contract.price, draw_price(cfg, rng, new_seats, contract.product))
    return min(contract.price * (1 + rng.uniform(*pricing["healthy_uplift"])), list_price(cfg, contract.product))


def close_and_renew(cfg, rng, account, live, product, renewal, term, factor, at_risk, util_class, ae_matrix):
    """Close the live contract for a product and open its renewal at the new seat count."""
    contract = live[product]
    seats = max(int(round(contract.seats * factor)), 1)
    if seats > contract.seats:
        contract.outcome = "Renewed Up"
    elif seats < contract.seats:
        contract.outcome = "Renewed Down"
    else:
        contract.outcome = "Renewed Flat"
    if util_class is not None:
        contract.util = utilization_for(cfg, rng, util_class)
    price = renewed_price(cfg, rng, contract, seats, at_risk)
    renewed = open_contract(account, product, "Renewal", renewal, renewal + term - 1, seats, price, ae_matrix)
    renewed.util = contract.util
    live[product] = renewed


def end_product(cfg, rng, live, product):
    live[product].outcome = "Churned"
    live[product].util = utilization_for(cfg, rng, "at_risk")
    del live[product]


def add_product(cfg, rng, account, live, month, renewal_end, ae_matrix, size_range):
    product = weighted_pick(rng, cfg["renewal"]["cross_sell_weights"], exclude=live.keys())
    if product is None:
        return
    base = sum(contract.seats * contract.price * 12 for contract in live.values())
    seats, price = size_deal(cfg, rng, base * rng.uniform(*size_range), product)
    contract = open_contract(account, product, "Expansion Add-on", month, renewal_end, seats, price, ae_matrix)
    contract.util = utilization_for(cfg, rng, "ai_healthy" if account.is_ai else "expand")
    live[product] = contract


def renew_healthy(cfg, rng, account, live, renewal, disrupted, ae_matrix):
    renewal_cfg = cfg["renewal"]
    emea = cfg["red_herrings"]["emea"]
    turnover = cfg["red_herrings"]["rep_turnover"]
    fy = fiscal_index(renewal)
    loss = renewal_cfg["loss_multiplier_by_fy"][fy]
    churn = renewal_cfg["logo_churn"][account.segment] * loss
    contraction = renewal_cfg["contraction_rate"] * loss
    if account.region == "EMEA" and emea["start_month"] <= renewal <= emea["end_month"]:
        contraction += emea["extra_contraction"]
    if disrupted >= 0 and 0 <= renewal - disrupted <= turnover["risk_window_months"]:
        churn += turnover["extra_churn"]

    if rng.random() < churn:
        for product in list(live):
            end_product(cfg, rng, live, product)
        account.churn = renewal
        return 0

    term = term_for(cfg, rng, account.segment)
    age = (renewal - account.origin) / 12
    low_age, high_age = renewal_cfg["grower_age_years"]
    roll = rng.random()
    for product in list(live):
        if roll < contraction:
            factor = 1 - rng.uniform(*renewal_cfg["contraction_cut"])
            close_and_renew(cfg, rng, account, live, product, renewal, term, factor, True, "at_risk", ae_matrix)
        elif account.grower and low_age <= age <= high_age + 0.5:
            factor = 1 + rng.uniform(*renewal_cfg["grower_growth"]) * renewal_cfg["expansion_scale"][fy]
            close_and_renew(cfg, rng, account, live, product, renewal, term, factor, False, "expand", ae_matrix)
        elif roll < contraction + renewal_cfg["expansion_prob"][fy]:
            factor = 1 + rng.uniform(*renewal_cfg["expansion_size"]) * renewal_cfg["expansion_scale"][fy]
            close_and_renew(cfg, rng, account, live, product, renewal, term, factor, False, "expand", ae_matrix)
        else:
            close_and_renew(cfg, rng, account, live, product, renewal, term, 1.0, False, "flat", ae_matrix)
    if rng.random() < renewal_cfg["cross_sell_prob"][fy]:
        add_product(cfg, rng, account, live, renewal, renewal + term - 1, ae_matrix, renewal_cfg["cross_sell_size"])
    return term


def renew_ai_before_pivot(cfg, rng, account, live, renewal, ae_matrix):
    ai = cfg["ai_forward"]
    if rng.random() < ai["pre_pivot_churn"]:
        for product in list(live):
            end_product(cfg, rng, live, product)
        account.churn = renewal
        return 0
    term = term_for(cfg, rng, account.segment)
    for product in list(live):
        grows = rng.random() < ai["pre_pivot_expansion_prob"]
        factor = 1 + rng.uniform(*ai["pre_pivot_expansion"]) if grows else 1.0
        close_and_renew(cfg, rng, account, live, product, renewal, term, factor, False, "ai_healthy", ae_matrix)
    if rng.random() < ai["pre_pivot_cross_sell_prob"]:
        add_product(cfg, rng, account, live, renewal, renewal + term - 1, ae_matrix, cfg["renewal"]["cross_sell_size"])
    return term


def renew_ai_after_pivot(cfg, rng, account, live, renewal, ae_matrix):
    """Analytics contracts first, then churns. Other products follow; logo churn lags API share."""
    ai = cfg["ai_forward"]
    lag = rng.integers(ai["logo_churn_lag"][0], ai["logo_churn_lag"][1] + 1)
    analytics_only = list(live) == ["P2"] and api_share_at(cfg, account, renewal) >= ai["analytics_only_exit_share"]
    leaves = renewal >= account.t80 + lag and rng.random() < ai["logo_churn_prob"]
    if leaves or (analytics_only and rng.random() < ai["analytics_only_exit_prob"]):
        for product in list(live):
            end_product(cfg, rng, live, product)
        account.churn = renewal
        return 0

    term = 12
    for product in list(live):
        contract = live[product]
        already_cut = contract.contract_type == "Renewal" and contract.start > account.onset
        if product == "P2":
            if already_cut and rng.random() < ai["analytics_churn_prob"]:
                end_product(cfg, rng, live, product)
                continue
            factor = 1 - rng.uniform(*ai["analytics_seat_cut"])
        elif product == "P3":
            factor = 1 - rng.uniform(*ai["engine_seat_cut"])
        elif product == "P1":
            factor = 1 - rng.uniform(*ai["transformation_seat_cut"]) if already_cut else 1.0
        else:
            factor = 1 + rng.uniform(*ai["ml_seat_change"])
        close_and_renew(cfg, rng, account, live, product, renewal, term, factor, True, None, ae_matrix)
    if not live:
        account.churn = renewal
        return 0
    return term


def run(cfg, accounts, ae_matrix, disrupted, chosen, since, is_ai, calendar):
    """Simulate every customer's contract history. Returns one Account per customer."""
    rng = stream(cfg, "simulate")
    growth = cfg["growth"]
    ai = cfg["ai_forward"]
    renewal_cfg = cfg["renewal"]
    last_month = calendar.months - 1
    customers = []

    for index in np.where(chosen)[0]:
        row = accounts.iloc[index]
        account = Account(int(index), row["segment"], row["region"], bool(is_ai[index]), int(since[index]))
        account.grower = rng.random() < renewal_cfg["grower_share"]
        account.origin = account.since
        if account.is_ai:
            draw = rng.beta(*ai["onset_beta"])
            account.onset = int(ai["onset_start"] + draw * (ai["onset_end"] - ai["onset_start"]))
            account.onset = max(account.onset, account.since + ai["min_months_before_onset"])
            account.pivot_months = int(rng.integers(ai["pivot_months"][0], ai["pivot_months"][1] + 1))
            account.t80 = month_share_reaches(cfg, account, 0.80)

        fy = fiscal_index(account.since)
        acv = draw_land_acv(cfg, rng, account.segment, fy, account.is_ai)
        first = weighted_pick(rng, growth["land_product_weights"])
        products = [first]
        if rng.random() < growth["two_product_land_share"]:
            products.append(weighted_pick(rng, growth["land_product_weights"], exclude=products))
        term = term_for(cfg, rng, account.segment)
        if account.since == 0:
            # Opening customers signed before the window, so their first renewals fall inside FY21.
            term = int(rng.integers(1, 12))
            account.origin = -int(rng.integers(12, 25))
            account.grower = rng.random() < growth["starting_customer_grower_share"]
        live = {}
        for product in products:
            seats, price = size_deal(cfg, rng, acv / len(products), product)
            contract = open_contract(account, product, "New", account.since, account.since + term - 1, seats, price, ae_matrix)
            contract.util = utilization_for(cfg, rng, "ai_healthy" if account.is_ai else "flat")
            live[product] = contract

        renewal = account.since + term
        while renewal <= last_month and live:
            if account.is_ai and renewal >= account.onset:
                term = renew_ai_after_pivot(cfg, rng, account, live, renewal, ae_matrix)
            elif account.is_ai:
                term = renew_ai_before_pivot(cfg, rng, account, live, renewal, ae_matrix)
            else:
                term = renew_healthy(cfg, rng, account, live, renewal, int(disrupted[index]), ae_matrix)
            if account.churn >= 0:
                break
            renewal += term
        customers.append(account)
    return customers
