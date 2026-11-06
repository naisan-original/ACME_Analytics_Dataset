"""Product catalog and seat pricing (spec Sections 2.3 and 5)."""
import pandas as pd

PRODUCTS = [
    ("P1", "ACME Data Transformation", "transformation_runs", 1.0),
    ("P2", "ACME Analytics", "dashboards_and_queries", 1.0),
    ("P3", "ACME Data Engine", "compute_credits", 1.2),
    ("P4", "ACME Machine Learning", "model_runs", 1.4),
]
MULTIPLIER = {product[0]: product[3] for product in PRODUCTS}


def dim_product():
    return pd.DataFrame(PRODUCTS, columns=["product_id", "product_name", "work_unit_label", "price_multiplier"])


def tier_for(cfg, seats):
    for tier in cfg["pricing"]["tiers"]:
        if tier["min_seats"] <= seats <= tier["max_seats"]:
            return tier
    return cfg["pricing"]["tiers"][-1]


def draw_price(cfg, rng, seats, product):
    tier = tier_for(cfg, seats)
    noise = cfg["pricing"]["deal_noise"]
    price = rng.uniform(tier["low"], tier["high"]) * MULTIPLIER[product] * (1 + rng.uniform(-noise, noise))
    return min(price, list_price(cfg, product))


def size_deal(cfg, rng, acv, product):
    """Find seats and net price for a target ACV, respecting the volume tier the seats land in."""
    multiplier = MULTIPLIER[product]
    tiers = cfg["pricing"]["tiers"]
    seats = None
    for tier in tiers:
        midpoint = (tier["low"] + tier["high"]) / 2 * multiplier
        candidate = acv / (12 * midpoint)
        if candidate <= tier["max_seats"]:
            seats = max(candidate, tier["min_seats"])
            break
    seats = int(round(seats if seats is not None else acv / (12 * tiers[-1]["low"] * multiplier)))
    seats = max(seats, 5)
    return seats, draw_price(cfg, rng, seats, product)


def list_price(cfg, product):
    return round(cfg["pricing"]["list_price"] * MULTIPLIER[product], 2)
