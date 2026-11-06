"""Account universe from cached public lists (spec Sections 2.2 and 3)."""
import re

import numpy as np
import pandas as pd

from .common import stream

REGION_BY_COUNTRY = {
    "EMEA": """United Kingdom|Germany|France|Italy|Spain|Netherlands|Kingdom of the Netherlands|Switzerland|Sweden|
        Norway|Denmark|Finland|Belgium|Austria|Ireland|Poland|Portugal|Greece|Turkey|Russia|Israel|South Africa|
        Saudi Arabia|United Arab Emirates|Qatar|Kuwait|Egypt|Nigeria|Morocco|Czech Republic|Hungary|Romania|
        Luxembourg|Iceland|Croatia|Slovenia|Slovakia|Bulgaria|Serbia|Ukraine|Lithuania|Latvia|Estonia|Cyprus|Malta|
        Kenya|Oman|Bahrain|Jordan|Lebanon""",
    "APAC": """Japan|People's Republic of China|China|India|South Korea|Australia|Taiwan|Singapore|Hong Kong|Indonesia|
        Malaysia|Thailand|Philippines|Vietnam|New Zealand|Pakistan|Bangladesh|Sri Lanka""",
    "LATAM": "Brazil|Mexico|Argentina|Chile|Colombia|Peru|Uruguay|Panama|Costa Rica|Ecuador|Venezuela",
}
COUNTRY_TO_REGION = {
    country.strip(): region
    for region, countries in REGION_BY_COUNTRY.items()
    for country in countries.replace("\n", "").split("|")
}
COUNTRY_ALIASES = {
    "United States of America": "United States",
    "People's Republic of China": "China",
    "Kingdom of the Netherlands": "Netherlands",
}

SUB_INDUSTRIES = {
    "High Tech": {"Software": 0.40, "Internet & Platforms": 0.20, "Semiconductors": 0.14, "IT Services": 0.16, "Hardware": 0.10},
    "Financial Services": {"Banking": 0.4, "Insurance": 0.3, "Asset Management": 0.2, "Payments": 0.1},
    "Healthcare & Life Sciences": {"Pharma & Biotech": 0.4, "Providers": 0.25, "Medical Devices": 0.2, "Payers": 0.15},
    "Retail & CPG": {"Retail": 0.5, "Consumer Packaged Goods": 0.35, "Restaurants & Hospitality": 0.15},
    "Manufacturing": {"Industrial Machinery": 0.35, "Automotive": 0.25, "Aerospace & Defense": 0.15, "Chemicals & Materials": 0.25},
    "Energy & Utilities": {"Oil & Gas": 0.45, "Utilities": 0.4, "Renewables": 0.15},
    "Telecom & Media": {"Telecom": 0.45, "Media & Entertainment": 0.4, "Publishing": 0.15},
    "Transportation & Logistics": {"Logistics": 0.45, "Airlines": 0.2, "Rail & Shipping": 0.35},
    "Public Sector & Education": {"Government Services": 0.5, "Education": 0.5},
    "Professional Services": {"Consulting": 0.45, "Legal & Accounting": 0.25, "Staffing": 0.3},
}

INDUSTRY_KEYWORDS = [
    ("High Tech", "Semiconductors", r"semiconductor|\bchips?\b|integrated circuit|micro devices|photonics"),
    ("High Tech", "Software", r"software|saas|cybersecurity|video game|computer security|\bsystems? software\b|\bai\b"),
    ("High Tech", "Internet & Platforms", r"internet|e-commerce|online|social media|\bweb\b|search engine|\bdigital\b|\bplatforms?\b"),
    ("High Tech", "IT Services", r"information technology|it service|data processing|\bcloud\b|\bdata\b"),
    ("High Tech", "Hardware", r"computer hardware|electronics|computer|consumer electronics|\bdevices?\b(?! medical)"),
    ("Financial Services", "Banking", r"\bbank|bancorp|bancshares|savings"),
    ("Financial Services", "Insurance", r"insurance|reinsurance"),
    ("Financial Services", "Payments", r"payment|fintech|credit card"),
    ("Financial Services", "Asset Management", r"financ|invest|asset management|real estate|private equity|capital\b|properties|realty|reit\b"),
    ("Healthcare & Life Sciences", "Pharma & Biotech", r"pharma|biotech|drug|therapeutic|biosciences?|biologics|oncology|genetics|\bbio"),
    ("Healthcare & Life Sciences", "Medical Devices", r"medical|diagnostic|surgical|\bdental\b"),
    ("Healthcare & Life Sciences", "Providers", r"health|hospital"),
    ("Retail & CPG", "Retail", r"retail|supermarket|department store|fashion|apparel|clothing"),
    ("Retail & CPG", "Restaurants & Hospitality", r"restaurant|hotel|hospitality|casino|gambling|tourism"),
    ("Retail & CPG", "Consumer Packaged Goods", r"food|beverage|brew|tobacco|cosmetic|consumer goods|agricultur"),
    ("Manufacturing", "Automotive", r"automotive|automobile|vehicle|tire"),
    ("Manufacturing", "Aerospace & Defense", r"aerospace|defen[cs]e|arms"),
    ("Manufacturing", "Chemicals & Materials", r"chemical|steel|metal|mining|material|paper|plastic|cement"),
    ("Manufacturing", "Industrial Machinery", r"machinery|engineering|manufactur|industrial|construction|conglomerate"),
    ("Energy & Utilities", "Oil & Gas", r"\boil\b|petroleum|natural gas|\bcoal\b|\bdrilling\b"),
    ("Energy & Utilities", "Renewables", r"\bsolar\b|\bwind\b|renewable"),
    ("Energy & Utilities", "Utilities", r"electric|utility|utilities|energy|\bwater\b|\bpower\b"),
    ("Telecom & Media", "Telecom", r"telecom|\bmobile\b|wireless|broadband|communications"),
    ("Telecom & Media", "Publishing", r"publish|newspaper"),
    ("Telecom & Media", "Media & Entertainment", r"media|entertainment|broadcast|film|television|music"),
    ("Transportation & Logistics", "Airlines", r"airline|aviation|airport"),
    ("Transportation & Logistics", "Rail & Shipping", r"\brail|shipping|maritime|\bport\b|\bports\b"),
    ("Transportation & Logistics", "Logistics", r"logistic|transport|freight|courier|trucking"),
    ("Public Sector & Education", "Education", r"education|university"),
    ("Professional Services", "Consulting", r"consult|advertising|marketing"),
    ("Professional Services", "Legal & Accounting", r"legal|accounting|audit"),
    ("Professional Services", "Staffing", r"staffing|human resource|recruit"),
]
COMPILED_KEYWORDS = [(industry, sub, re.compile(pattern)) for industry, sub, pattern in INDUSTRY_KEYWORDS]

DEFAULT_CITIES = {
    "United States": ["New York", "Chicago", "Dallas", "Atlanta", "Boston", "Houston", "Denver", "Minneapolis",
                      "Charlotte", "Columbus", "Philadelphia", "Phoenix", "San Diego", "Seattle", "Austin", "San Jose"],
    "Canada": ["Toronto", "Vancouver", "Montreal", "Calgary"],
    "EMEA": ["London", "Paris", "Frankfurt", "Amsterdam", "Zurich", "Stockholm", "Madrid", "Milan", "Dubai"],
    "APAC": ["Tokyo", "Singapore", "Sydney", "Seoul", "Mumbai", "Shanghai", "Hong Kong"],
    "LATAM": ["Sao Paulo", "Mexico City", "Santiago", "Bogota", "Buenos Aires"],
}
WEST_CITIES = {"Seattle", "San Jose", "San Diego", "Phoenix", "Denver", "San Francisco", "Los Angeles", "Portland"}

FICTIONAL_FIRST = """Northgate Stonebrook Redfield Lakemont Silverline Harborview Pinecrest Ridgeway Oakmere Bluewater
    Ironbridge Clearpoint Summit Westhaven Eastmark Fairmont Brightwater Copperfield Highland Meridian Tallgrass
    Cedarline Granite Horizon Keystone Lighthouse Mapleton Palisade Quarry Rivermark Sagebrook Timberline Vantage
    Windmere Yellowstone Ashford Beacon Crestline Dovetail Evergreen Foxhollow Glenmoor Hawthorn""".split()
FICTIONAL_LAST = """Holdings Group Industries Partners Systems Logistics Foods Materials Brands Services Energy Health
    Financial Technologies Solutions Manufacturing Supply Retail Networks Labs""".split()


def normalize(name):
    cleaned = re.sub(r"[^a-z0-9 ]", "", name.lower())
    cleaned = re.sub(r"\b(inc|incorporated|corp|corporation|ltd|limited|plc|llc|ag|sa|nv|se|co|company|holdings?|group)\b", "", cleaned)
    return " ".join(cleaned.split())


def load_sources(cfg):
    frames = [pd.read_csv(path, dtype=str, keep_default_na=False) for path in cfg["paths"]["company_sources"]]
    table = pd.concat(frames, ignore_index=True)
    table["revenue"] = pd.to_numeric(table["revenue"], errors="coerce").fillna(0.0)
    table["country"] = table["country"].replace(COUNTRY_ALIASES)
    table["key"] = table["name"].map(normalize)
    valid = (table["key"].str.len() >= 3) & ~table["name"].str.fullmatch(r"Q\d+") & (table["country"] != "")
    table = table[valid].sort_values("revenue", ascending=False, kind="stable")
    return table.drop_duplicates("key").reset_index(drop=True)


def classify(label, rng, weights):
    lowered = label.lower()
    if lowered:
        for industry, sub, pattern in COMPILED_KEYWORDS:
            if pattern.search(lowered):
                return industry, sub
    names = list(weights)
    probabilities = np.array(list(weights.values()), dtype=float)
    industry = names[rng.choice(len(names), p=probabilities / probabilities.sum())]
    subs = SUB_INDUSTRIES[industry]
    sub_names = list(subs)
    return industry, sub_names[rng.choice(len(sub_names), p=list(subs.values()))]


def region_of(country):
    if country == "United States":
        return "US"
    if country == "Canada":
        return "Canada"
    return COUNTRY_TO_REGION.get(country, "")


def fictional_names(rng, count, taken):
    names = []
    while len(names) < count:
        name = f"{rng.choice(FICTIONAL_FIRST)} {rng.choice(FICTIONAL_FIRST)} {rng.choice(FICTIONAL_LAST)}"
        key = normalize(name)
        if key not in taken:
            taken.add(key)
            names.append(name)
    return names


def build(cfg):
    """Return the 15,000-account table, with internal columns the export step removes."""
    rng = stream(cfg, "accounts")
    settings = cfg["accounts"]
    sources = load_sources(cfg)
    sources["bucket"] = sources["country"].map(region_of)
    sources = sources[sources["bucket"] != ""]

    parts = []
    taken = set(sources["key"])
    for bucket, quota in settings["region_counts"].items():
        pool = sources[sources["bucket"] == bucket].head(quota).copy()
        pool["is_fictional"] = False
        short = quota - len(pool)
        if short > 0:
            names = fictional_names(rng, short, taken)
            country = {"US": "United States", "Canada": "Canada"}.get(bucket, "")
            fill = pd.DataFrame(
                {"name": names, "country": country, "industry": "", "hq_city": "", "revenue": 0.0,
                 "bucket": bucket, "is_fictional": True}
            )
            if not country:
                real = pool["country"].to_numpy()
                fill["country"] = rng.choice(real, size=short) if len(real) else bucket
            pool = pd.concat([pool, fill], ignore_index=True)
        parts.append(pool)
    table = pd.concat(parts, ignore_index=True)

    # Rank real companies with known revenue first, then fill bands down the long tail.
    order = np.lexsort((rng.random(len(table)), table["is_fictional"].astype(int), -table["revenue"].to_numpy()))
    table = table.iloc[order].reset_index(drop=True)
    bands = np.concatenate([[band] * count for band, count in settings["band_counts"].items()])
    table["annual_revenue_band"] = bands[: len(table)]
    table["segment"] = table["annual_revenue_band"].map(settings["segment_by_band"])

    classified = [
        classify(label or name, rng, settings["industry_weights"])
        for label, name in zip(table["industry"], table["name"])
    ]
    table["industry"] = [pair[0] for pair in classified]
    table["sub_industry"] = [pair[1] for pair in classified]

    table["region"] = table["bucket"].replace({"US": "NA", "Canada": "NA"})
    cities = []
    for city, bucket in zip(table["hq_city"], table["bucket"]):
        if city:
            cities.append(city)
        else:
            options = DEFAULT_CITIES["United States" if bucket == "US" else bucket]
            cities.append(options[rng.integers(len(options))])
    table["hq_city"] = cities

    us_west = (table["bucket"] == "US") & (
        table["hq_city"].isin(WEST_CITIES) | (rng.random(len(table)) < settings["us_west_share"] * 0.8)
    )
    table["territory"] = np.where(
        table["region"] == "NA", np.where(us_west, "US-West", "US-East"), table["region"]
    )

    employee_band = {"$50B+": "100K+", "$10-50B": "25K-100K", "$2-10B": "5K-25K", "$200M-2B": "1K-5K"}
    table["employee_band"] = table["annual_revenue_band"].map(employee_band)

    real_us = (table["bucket"] == "US") & ~table["is_fictional"] & (table["revenue"] > 0)
    table["fortune_rank"] = pd.array([pd.NA] * len(table), dtype="Int64")
    table.loc[real_us, "fortune_rank"] = np.arange(1, real_us.sum() + 1)
    table.loc[table["fortune_rank"] > 1000, "fortune_rank"] = pd.NA
    real = ~table["is_fictional"] & (table["revenue"] > 0)
    table["global2000_rank"] = pd.array([pd.NA] * len(table), dtype="Int64")
    table.loc[real, "global2000_rank"] = np.arange(1, real.sum() + 1)
    table.loc[table["global2000_rank"] > 2000, "global2000_rank"] = pd.NA

    table = table.iloc[rng.permutation(len(table))].reset_index(drop=True)
    table["account_id"] = [f"A{index + 1:05d}" for index in range(len(table))]
    return table


def tech_signals(cfg, rng, table, is_ai):
    settings = cfg["tech_signals"]
    probability = settings["ai_topic_prob"]
    signals = []
    high_tech = (table["industry"] == "High Tech").to_numpy()
    for index in range(len(table)):
        size = int(rng.integers(settings["count_range"][0], settings["count_range"][1] + 1))
        share = probability["ai_forward"] if is_ai[index] else probability["high_tech"] if high_tech[index] else probability["other"]
        picks = set()
        for _ in range(size):
            pool = settings["ai"] if rng.random() < share else settings["general"]
            picks.add(pool[rng.integers(len(pool))])
        signals.append(";".join(sorted(picks)))
    return signals
