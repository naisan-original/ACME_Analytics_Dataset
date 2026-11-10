"""Write the Apache Ossie (formerly Open Semantic Interchange, OSI) semantic model for the dataset.

Usage:
    uv run python tools/semantic_model.py           # write semantic/*.yaml
    uv run python tools/semantic_model.py --check   # also check them against the official schemas and the CSVs

Column descriptions come from acme/export.py, so the model always matches the data dictionary.
Two files are written from one definition:
    semantic/acme_analytics.ossie.yaml      current Ossie draft (0.3.0.dev0), the shape today's converters read
    semantic/acme_analytics.osi-0.1.1.yaml  OSI 0.1.1, the only released version of the spec
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from acme.common import load_config
from acme.export import DICTIONARY

OUT_DIR = ROOT / "semantic"
DRAFT_FILE = OUT_DIR / "acme_analytics.ossie.yaml"
RELEASED_FILE = OUT_DIR / "acme_analytics.osi-0.1.1.yaml"
DRAFT_VERSION = "0.3.0.dev0"
RELEASED_VERSION = "0.1.1"

# Official schemas, pinned to the commits these files were checked against.
SCHEMAS = {
    DRAFT_VERSION: "https://raw.githubusercontent.com/apache/ossie/ee89dbdc2844d8b7d293ed42c8613928bb99505f/core-spec/ossie-schema.json",
    RELEASED_VERSION: "https://raw.githubusercontent.com/apache/ossie/faf581054dcf7964d5fe0ceae7d6f415c8ce32a5/core-spec/osi-schema.json",
}

# Placeholder location for each table. Snowflake and other tools require database.schema.table;
# replace acme_analytics.public with wherever the CSVs are loaded.
SOURCE_PREFIX = "acme_analytics.public"

FACT = "fct_account_product_month"
USAGE = "user_usage_month"

# ---------------------------------------------------------------- datasets

DATASETS = {
    FACT: {
        "primary_key": ["month_id", "account_id", "product_id"],
        "synonyms": ["subscriptions", "revenue", "ARR", "product usage by month", "account product month"],
        "instructions": (
            "Main fact table, one row per account, product and month. ARR, MRR, licensed_seats and active_users are "
            "month-end snapshots: filter to one month or group by month, and never add them up across months. "
            "Paying customers are accounts with arr > 0. Each product subscription has one final row with arr = 0 "
            "and churn_flag = 1."
        ),
    },
    "dim_account": {
        "primary_key": ["account_id"],
        "synonyms": ["accounts", "customers", "companies", "logos", "clients"],
        "instructions": (
            "Includes customers, former customers and prospects. Prospects have no revenue rows, so count "
            "customers from the fact table (arr > 0), not from this table. region 'NA' means North America, not "
            "a missing value. Do not join customer_since_month_id or churn_month_id to dim_month; they are "
            "descriptive and mostly blank."
        ),
    },
    "dim_product": {
        "primary_key": ["product_id"],
        "synonyms": ["products", "SKUs", "product lines"],
        "instructions": "Four products, all priced per seat. API calls do not consume seats.",
    },
    "dim_month": {
        "primary_key": ["month_id"],
        "synonyms": ["calendar", "dates", "months", "fiscal calendar"],
        "instructions": (
            "One row per month from 202011 to 202610. The fiscal year ends October 31, so FY26 runs from "
            "November 2025 to October 2026. The latest month is 202610."
        ),
    },
    "dim_employee": {
        "primary_key": ["employee_id"],
        "synonyms": ["employees", "reps", "account executives", "customer success managers", "owners", "staff"],
        "instructions": (
            "Plays two roles for the main fact table: Account Executive (ae_employee_id) and Customer Success "
            "Manager (csm_employee_id). Do not join hire_month_id or termination_month_id to dim_month."
        ),
    },
    USAGE: {
        "primary_key": ["user_id", "product_id", "month_id"],
        "synonyms": ["user activity", "user usage", "seat usage", "users"],
        "instructions": (
            "A stratified sample of users, not the full population. Multiply measures by sample_weight to "
            "estimate full-population totals, or use the estimated_* metrics. To compare with the main fact "
            "table, total both to account, product and month first; do not join the two row by row."
        ),
    },
    "contracts": {
        "primary_key": ["contract_id"],
        "synonyms": ["deals", "bookings", "agreements", "orders"],
        "instructions": (
            "One row per contract. A contract is active in a month when start_month_id <= month <= end_month_id; "
            "summing acv over active contracts reconciles to ARR. The relationship to dim_month uses "
            "start_month_id only, so it slices bookings by start month."
        ),
    },
    "touchpoints": {
        "primary_key": ["touchpoint_id"],
        "synonyms": ["interactions", "activities", "meetings", "CRM notes", "customer touches"],
        "instructions": (
            "Interactions with customers and prospects, so about 40% of rows belong to accounts with no revenue. "
            "Join to the main fact table only after totalling both to account and month."
        ),
    },
}

# Logical type of each column (Ossie DataType names).
DATE_COLUMNS = {"month_start_date", "touch_date"}
DECIMAL_COLUMNS = {"list_price_per_seat_month", "net_price_per_seat_month", "mrr", "arr", "acv", "quota_arr", "price_multiplier"}
FLOAT_COLUMNS = {"ui_hours", "api_share", "sample_weight"}
INTEGER_COLUMNS = {
    "month_id", "licensed_seats", "active_users", "ui_sessions", "api_calls", "work_units", "renewal_month_flag",
    "churn_flag", "fortune_rank", "global2000_rank", "customer_since_month_id", "churn_month_id", "calendar_year",
    "hire_month_id", "termination_month_id", "start_month_id", "end_month_id", "term_months", "seats", "sentiment",
}

FIELD_SYNONYMS = {
    "arr": ["annual recurring revenue", "run rate", "revenue"],
    "mrr": ["monthly recurring revenue"],
    "licensed_seats": ["seats", "licenses"],
    "api_share": ["API percentage", "programmatic share"],
    "account_name": ["company", "customer name"],
    "industry": ["vertical", "sector"],
    "segment": ["tier", "customer segment"],
    "region": ["geo", "territory"],
    "fiscal_year": ["FY"],
    "fiscal_quarter": ["FQ", "quarter"],
    "acv": ["annual contract value", "booking value"],
    "sentiment": ["sentiment score", "tone"],
    "user_persona": ["persona", "user type"],
}

# Fields computed from source columns, added after the CSV columns.
COMPUTED_FIELDS = {
    "dim_month": [
        {"name": "is_fiscal_year_end", "sql": "month_id % 100 = 10", "datatype": "Boolean",
         "description": "True for October, the last month of the fiscal year. Filter on it to read ARR at year end"},
        {"name": "is_fiscal_quarter_end", "sql": "month_id % 100 IN (1, 4, 7, 10)", "datatype": "Boolean",
         "description": "True for the last month of each fiscal quarter (January, April, July, October)"},
    ],
}

# ---------------------------------------------------------------- relationships
# Every relationship is many-to-one, from a fact table to a dimension. Fact tables never join to each other.

RELATIONSHIPS = [
    ("fct_to_account", FACT, "dim_account", "account_id", "account_id", None),
    ("fct_to_product", FACT, "dim_product", "product_id", "product_id", None),
    ("fct_to_month", FACT, "dim_month", "month_id", "month_id", None),
    ("fct_to_account_executive", FACT, "dim_employee", "ae_employee_id", "employee_id",
     "Role-playing join: the Account Executive who owned the account that month."),
    ("fct_to_customer_success_manager", FACT, "dim_employee", "csm_employee_id", "employee_id",
     "Role-playing join: the Customer Success Manager who owned the account that month."),
    ("usage_to_account", USAGE, "dim_account", "account_id", "account_id", None),
    ("usage_to_product", USAGE, "dim_product", "product_id", "product_id", None),
    ("usage_to_month", USAGE, "dim_month", "month_id", "month_id", None),
    ("contract_to_account", "contracts", "dim_account", "account_id", "account_id", None),
    ("contract_to_product", "contracts", "dim_product", "product_id", "product_id", None),
    ("contract_to_start_month", "contracts", "dim_month", "start_month_id", "month_id",
     "Slices contracts by the month they start, not by the months they are active."),
    ("contract_to_account_executive", "contracts", "dim_employee", "ae_employee_id", "employee_id", None),
    ("touchpoint_to_account", "touchpoints", "dim_account", "account_id", "account_id", None),
    ("touchpoint_to_employee", "touchpoints", "dim_employee", "employee_id", "employee_id", None),
    ("touchpoint_to_month", "touchpoints", "dim_month", "month_id", "month_id", None),
]

# ---------------------------------------------------------------- metrics

SNAPSHOT = "Month-end snapshot: filter to one month or group by month. Never add it up across months."
F, U, C, T = FACT, USAGE, "contracts", "touchpoints"

METRICS = [
    ("arr", f"SUM({F}.arr)", "Decimal",
     "Annual recurring revenue (MRR x 12).", ["annual recurring revenue", "revenue", "run rate"],
     SNAPSHOT + " For a fiscal year, use fiscal_year_end_arr. The latest month is 202610."),
    ("mrr", f"SUM({F}.mrr)", "Decimal", "Monthly recurring revenue.", ["monthly recurring revenue"], SNAPSHOT),
    ("fiscal_year_end_arr", f"SUM(CASE WHEN {F}.month_id % 100 = 10 THEN {F}.arr END)", "Decimal",
     "ARR in October, the last month of each fiscal year.", ["ending ARR", "year-end ARR", "closing ARR"],
     "Group by dim_month.fiscal_year to get ARR at each year end."),
    ("fiscal_quarter_end_arr", f"SUM(CASE WHEN {F}.month_id % 100 IN (1, 4, 7, 10) THEN {F}.arr END)", "Decimal",
     "ARR in the last month of each fiscal quarter.", ["quarter-end ARR"],
     "Group by dim_month.fiscal_quarter."),
    ("paying_customers", f"COUNT(DISTINCT CASE WHEN {F}.arr > 0 THEN {F}.account_id END)", "Integer",
     "Accounts with ARR above zero.", ["customers", "customer count", "logos", "active customers"],
     SNAPSHOT + " Use fiscal_year_end_customers for fiscal years."),
    ("fiscal_year_end_customers",
     f"COUNT(DISTINCT CASE WHEN {F}.month_id % 100 = 10 AND {F}.arr > 0 THEN {F}.account_id END)", "Integer",
     "Paying customers in October, the last month of each fiscal year.", ["year-end customers", "ending logos"],
     "Group by dim_month.fiscal_year."),
    ("licensed_seats", f"SUM({F}.licensed_seats)", "Integer", "Contracted seats.", ["seats", "licenses"], SNAPSHOT),
    ("active_users", f"SUM({F}.active_users)", "Integer",
     "Users with at least one UI session. A person using two products counts once per product.",
     ["MAU", "monthly active users"], SNAPSHOT),
    ("ui_hours", f"SUM({F}.ui_hours)", "Float", "Hours spent in the product UI.", ["UI time", "hours"], None),
    ("ui_sessions", f"SUM({F}.ui_sessions)", "Integer", "UI sessions.", ["sessions", "logins"], None),
    ("api_calls", f"SUM({F}.api_calls)", "Integer", "API requests.", ["API requests", "API volume"], None),
    ("work_units", f"SUM({F}.work_units)", "Integer",
     "Product-specific activity; dim_product.work_unit_label says what each product counts.", ["activity", "usage"],
     "Compare work units within one product; units differ between products."),
    ("api_share", f"SUM({F}.api_share * {F}.work_units) / NULLIF(SUM({F}.work_units), 0)", "Float",
     "Share of work done through the API, weighted by work units. 0 to 1.", ["API share", "programmatic share"],
     "Use this weighted metric rather than averaging the api_share column."),
    ("average_discount",
     f"1 - SUM({F}.net_price_per_seat_month * {F}.licensed_seats) / "
     f"NULLIF(SUM({F}.list_price_per_seat_month * {F}.licensed_seats), 0)", "Float",
     "Seat-weighted discount from list price. 0 to 1.", ["discount", "price realization gap"], None),
    ("product_churns", f"SUM({F}.churn_flag)", "Integer",
     "Product subscriptions that ended.", ["churn events", "lost subscriptions"],
     "Counts product subscriptions, not accounts. An account churns fully when all its products have ended."),
    ("renewals_due", f"SUM({F}.renewal_month_flag)", "Integer",
     "Account-product months in which a renewal falls.", ["renewals"], None),
    ("estimated_users", f"SUM({U}.sample_weight)", "Float",
     "Estimated number of users in the full population, from the weighted sample.", ["users", "user count"],
     "Per month: filter to one month or group by month. A person using two products counts once per product."),
    ("estimated_ui_hours", f"SUM({U}.ui_hours * {U}.sample_weight)", "Float",
     "Estimated full-population UI hours from the weighted user sample.", None, None),
    ("estimated_api_calls", f"SUM({U}.api_calls * {U}.sample_weight)", "Float",
     "Estimated full-population API calls from the weighted user sample.", None, None),
    ("sampled_users", f"COUNT(DISTINCT {U}.user_id)", "Integer",
     "Distinct users in the sample. Not a population count.", None,
     "Use estimated_users for population counts."),
    ("contract_count", f"COUNT({C}.contract_id)", "Integer", "Contracts.", ["deals", "bookings count"], None),
    ("booked_acv", f"SUM({C}.acv)", "Decimal",
     "Annual contract value of contracts, by start month.", ["bookings", "ACV"],
     "This is bookings, not ARR. Use the arr metric for recurring revenue."),
    ("touchpoint_count", f"COUNT({T}.touchpoint_id)", "Integer",
     "Logged interactions.", ["interactions", "activities", "touches"], None),
    ("average_sentiment", f"AVG({T}.sentiment)", "Float",
     "Average touchpoint sentiment, from -2 to +2.", ["sentiment", "customer sentiment"], None),
    ("touched_accounts", f"COUNT(DISTINCT {T}.account_id)", "Integer",
     "Accounts with at least one logged interaction, including prospects.", None, None),
    ("account_count", "COUNT(DISTINCT dim_account.account_id)", "Integer",
     "Accounts of every status, including prospects.", ["accounts"],
     "Use paying_customers to count customers."),
    ("employee_count", "COUNT(DISTINCT dim_employee.employee_id)", "Integer",
     "Sales and customer success staff, including leavers.", ["headcount", "reps"], None),
]

MODEL_INSTRUCTIONS = """\
SYNTHETIC DATA. ACME Analytics is a fictional software company. Real company names appear for realism only, and no record describes a real company.
Star schema: four fact tables (fct_account_product_month, user_usage_month, contracts, touchpoints) share four dimensions (dim_account, dim_product, dim_month, dim_employee). Every relationship is many-to-one from a fact table to a dimension.
Never join two fact tables row by row; it inflates totals. Total each fact table to a shared level (account, product, month) first, then combine.
ARR, MRR, seats and active users are month-end snapshots. Filter to one month or group by month, and use fiscal_year_end_arr for fiscal years.
The fiscal year ends October 31. FY26 runs from November 2025 to October 2026, the last month in the data (202610).
Count customers with paying_customers (arr > 0). dim_account also holds prospects, which have no revenue.
user_usage_month is a sample; use the estimated_* metrics or multiply by sample_weight.
GRR and NDR compare each account's ARR with its ARR 12 months earlier, over accounts paying 12 months earlier. GRR caps each account at its earlier ARR, so it ignores expansion; NDR includes expansion. Neither can be written as a single metric in this specification, so compute them per account first (see semantic/README.md).
region 'NA' means North America, not a missing value."""

MODEL_EXAMPLES = [
    "What was ARR at the end of FY26?",
    "How many paying customers did we have at the end of each fiscal year?",
    "Show ARR by region and fiscal year.",
    "Which products have the highest API share?",
    "How has average touchpoint sentiment changed by quarter?",
    "What were GRR and NDR in FY26?",
]


def datatype(column):
    if column in DATE_COLUMNS:
        return "Date"
    if column in DECIMAL_COLUMNS:
        return "Decimal"
    if column in FLOAT_COLUMNS:
        return "Float"
    if column in INTEGER_COLUMNS:
        return "Integer"
    return "String"


def expression(sql):
    """The portable `sql` form the spec prefers, repeated as ANSI_SQL for converters that only read dialects."""
    return {"sql": sql, "dialects": [{"dialect": "ANSI_SQL", "expression": sql}]}


def context(synonyms=None, instructions=None, examples=None):
    value = {}
    if instructions:
        value["instructions"] = instructions
    if synonyms:
        value["synonyms"] = list(synonyms)
    if examples:
        value["examples"] = list(examples)
    return value or None


def build_model(cfg):
    """The model in the current draft shape, with portable `sql` expressions and data types."""
    datasets = []
    for name, spec in DATASETS.items():
        description, columns = DICTIONARY[name]
        fields = []
        for column, text in columns.items():
            field = {"name": column, "expression": expression(column), "datatype": datatype(column), "description": text}
            # Every dim_month column is a time grain. In fact tables, month keys are plain keys, as in the TPC-DS example.
            field["dimension"] = {"is_time": name == "dim_month" or column in DATE_COLUMNS}
            extra = context(FIELD_SYNONYMS.get(column))
            if extra:
                field["ai_context"] = extra
            fields.append(field)
        for computed in COMPUTED_FIELDS.get(name, []):
            fields.append({"name": computed["name"], "expression": expression(computed["sql"]), "datatype": computed["datatype"],
                           "description": computed["description"], "dimension": {"is_time": True}})
        datasets.append({
            "name": name,
            "source": f"{SOURCE_PREFIX}.{name}",
            "primary_key": spec["primary_key"],
            "description": description,
            "ai_context": context(spec["synonyms"], spec["instructions"]),
            "fields": fields,
        })
    relationships = []
    for name, source, target, from_column, to_column, note in RELATIONSHIPS:
        relationship = {"name": name, "from": source, "to": target, "from_columns": [from_column], "to_columns": [to_column]}
        if note:
            relationship["ai_context"] = note
        relationships.append(relationship)
    metrics = []
    for name, sql, kind, description, synonyms, instructions in METRICS:
        metric = {"name": name, "expression": expression(sql), "datatype": kind, "description": description}
        extra = context(synonyms, instructions)
        if extra:
            metric["ai_context"] = extra
        metrics.append(metric)
    return {
        "version": DRAFT_VERSION,
        "name": "acme_analytics",
        "description": (
            "ACME Analytics synthetic SaaS dataset: subscriptions, usage, contracts and customer interactions for a "
            "fictional analytics software vendor, November 2020 to October 2026. " + cfg["synthetic_notice"]
        ),
        "ai_context": context(instructions=MODEL_INSTRUCTIONS, examples=MODEL_EXAMPLES),
        "datasets": datasets,
        "relationships": relationships,
        "metrics": metrics,
    }


def to_released(model):
    """Convert the draft-shaped model to OSI 0.1.1: wrapped in semantic_model, ANSI_SQL dialects, no data types."""
    def released_expression(node):
        return {"dialects": [{"dialect": "ANSI_SQL", "expression": node["expression"]["sql"]}]}

    def strip(item):
        copy = {key: value for key, value in item.items() if key != "datatype"}
        copy["expression"] = released_expression(item)
        return copy

    body = {key: value for key, value in model.items() if key != "version"}
    body["datasets"] = [{**dataset, "fields": [strip(field) for field in dataset["fields"]]} for dataset in model["datasets"]]
    body["metrics"] = [strip(metric) for metric in model["metrics"]]
    return {"version": RELEASED_VERSION, "semantic_model": [body]}


class Dumper(yaml.SafeDumper):
    pass


def _string(dumper, value):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


Dumper.add_representer(str, _string)


def write(path, document, version):
    header = [
        f"# yaml-language-server: $schema={SCHEMAS[version]}",
        "#",
        "# ACME Analytics semantic model, Apache Ossie (formerly Open Semantic Interchange, OSI) format.",
        f"# Specification version {version}. Generated by tools/semantic_model.py; do not edit by hand.",
        "# SYNTHETIC DATA: every record is fictional. See README.md.",
        "",
    ]
    text = yaml.dump(document, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=120)
    path.write_text("\n".join(header) + text, encoding="utf-8")


# ---------------------------------------------------------------- checks


# DuckDB's CSV types that fit each declared type. Integer columns with blanks can read as DOUBLE.
CSV_TYPES = {
    "String": {"VARCHAR"}, "Date": {"DATE"}, "Boolean": {"BOOLEAN"}, "Integer": {"BIGINT", "DOUBLE"},
    "Decimal": {"DOUBLE", "BIGINT"}, "Float": {"DOUBLE", "BIGINT"},
}


def load_schema(version):
    cache = ROOT / ".cache" / "ossie" / Path(SCHEMAS[version]).name.replace(".json", f"-{version}.json")
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(SCHEMAS[version], timeout=30) as response:
            cache.write_bytes(response.read())
    return json.loads(cache.read_text())


def check(model, cfg):
    import duckdb
    import numpy as np
    import pandas as pd
    from jsonschema import Draft202012Validator

    from acme.metrics import kpi_table

    failures = []

    def expect(condition, message):
        print(("ok    " if condition else "FAIL  ") + message)
        if not condition:
            failures.append(message)

    # 1. Official JSON schemas.
    for path, version in ((DRAFT_FILE, DRAFT_VERSION), (RELEASED_FILE, RELEASED_VERSION)):
        document = yaml.safe_load(path.read_text())
        errors = list(Draft202012Validator(load_schema(version)).iter_errors(document))
        expect(not errors, f"{path.name} matches the official {version} schema" + (f": {errors[0].message}" if errors else ""))

    # 2. Names and references.
    fields = {d["name"]: {f["name"] for f in d["fields"]} for d in model["datasets"]}
    names = [d["name"] for d in model["datasets"]]
    expect(len(names) == len(set(names)), "dataset names are unique")
    for dataset in model["datasets"]:
        listed = [f["name"] for f in dataset["fields"]]
        expect(len(listed) == len(set(listed)) and set(dataset["primary_key"]) <= fields[dataset["name"]],
               f"{dataset['name']}: field names unique and primary key fields exist")
    metric_names = [m["name"] for m in model["metrics"]]
    expect(len(metric_names) == len(set(metric_names)), "metric names are unique")
    relationship_names = [r["name"] for r in model["relationships"]]
    expect(len(relationship_names) == len(set(relationship_names)), "relationship names are unique")
    broken = [r["name"] for r in model["relationships"]
              if not (set(r["from_columns"]) <= fields.get(r["from"], set()) and set(r["to_columns"]) <= fields.get(r["to"], set()))]
    expect(not broken, f"all {len(model['relationships'])} relationships refer to existing fields" + (f" (check {broken})" if broken else ""))
    broken = []
    for m in model["metrics"]:
        refs = re.findall(r"\b([a-z_]+)\.([a-z_0-9]+)\b", m["expression"]["sql"])
        if not refs or not all(field in fields.get(dataset, set()) for dataset, field in refs):
            broken.append(m["name"])
    expect(not broken, f"all {len(model['metrics'])} metrics refer to existing fields" + (f" (check {broken})" if broken else ""))

    # 3. The model matches the CSVs and the data dictionary.
    folder = ROOT / cfg["paths"]["output_dir"]
    db = duckdb.connect()
    for name in names:
        db.execute(f"CREATE VIEW {name} AS SELECT * FROM read_csv('{folder / (name + '.csv')}', header = true)")
    for dataset in model["datasets"]:
        columns = list(pd.read_csv(folder / f"{dataset['name']}.csv", nrows=0).columns)
        computed = {f["name"] for f in COMPUTED_FIELDS.get(dataset["name"], [])}
        expect([f["name"] for f in dataset["fields"] if f["name"] not in computed] == columns,
               f"{dataset['name']}: one field per CSV column, in order")
        key = ", ".join(dataset["primary_key"])
        duplicates, nulls = db.execute(
            f"SELECT COUNT(*) - COUNT(DISTINCT ({key})), COUNT(*) FILTER (WHERE {' OR '.join(c + ' IS NULL' for c in dataset['primary_key'])}) FROM {dataset['name']}"
        ).fetchone()
        expect(duplicates == 0 and nulls == 0, f"{dataset['name']}: primary key ({key}) is unique and never blank")
        for field in dataset["fields"]:
            db.execute(f"SELECT {field['expression']['sql']} FROM {dataset['name']} LIMIT 1")
        types = dict(db.execute(f"SELECT column_name, column_type FROM (DESCRIBE {dataset['name']})").fetchall())
        wrong = [f["name"] for f in dataset["fields"] if f["name"] in types and types[f["name"]] not in CSV_TYPES[f["datatype"]]]
        expect(not wrong, f"{dataset['name']}: declared data types fit the CSV" + (f" (check {wrong})" if wrong else ""))

    # 4. Every relationship is many-to-one with no orphaned keys.
    for r in model["relationships"]:
        source, target = r["from_columns"][0], r["to_columns"][0]
        orphans, blanks = db.execute(
            f"SELECT COUNT(*) FILTER (WHERE f.{source} IS NOT NULL AND t.{target} IS NULL), COUNT(*) FILTER (WHERE f.{source} IS NULL) "
            f"FROM {r['from']} f LEFT JOIN {r['to']} t ON f.{source} = t.{target}"
        ).fetchone()
        expect(orphans == 0, f"relationship {r['name']}: no orphaned keys ({blanks:,} blank keys)")

    # 5. Every metric runs, and the headline metrics match the answer key.
    for m in model["metrics"]:
        dataset = re.findall(r"\b([a-z_]+)\.", m["expression"]["sql"])[0]  # every metric reads one dataset
        db.execute(f"SELECT {m['expression']['sql']} FROM {dataset}").fetchone()
    expect(True, f"all {len(model['metrics'])} metrics run as SQL")

    fact = pd.read_csv(folder / f"{FACT}.csv")
    months = pd.read_csv(folder / "dim_month.csv")
    accounts = pd.read_csv(folder / "dim_account.csv", keep_default_na=False, na_values=[""])
    ids = accounts["account_id"].to_numpy()
    month_ids = months["month_id"].tolist()
    arr = np.zeros((len(ids), len(month_ids)))
    np.add.at(arr, (fact["account_id"].map({v: i for i, v in enumerate(ids)}), fact["month_id"].map({v: i for i, v in enumerate(month_ids)})), fact["arr"])
    kpis = kpi_table(arr).set_index("FY")

    metric = {m["name"]: m["expression"]["sql"] for m in model["metrics"]}
    by_year = db.execute(
        f"SELECT dim_month.fiscal_year, {metric['fiscal_year_end_arr']}, {metric['fiscal_year_end_customers']} "
        f"FROM {FACT} JOIN dim_month ON {FACT}.month_id = dim_month.month_id GROUP BY 1 ORDER BY 1"
    ).fetchall()
    for year, year_arr, customers in by_year:
        expect(round(year_arr / 1e6, 1) == kpis.loc[year, "arr_m"] and customers == kpis.loc[year, "customers"],
               f"{year}: fiscal_year_end_arr ${year_arr / 1e6:,.2f}M and {customers:,} customers match the answer key")
    latest = db.execute(f"SELECT {metric['arr']} FROM {FACT} WHERE month_id = 202610").fetchone()[0]
    expect(round(latest / 1e6, 1) == kpis.loc["FY26", "arr_m"], f"arr filtered to 202610 is ${latest / 1e6:,.2f}M")

    # 6. The GRR and NDR SQL in semantic/README.md reproduces the answer key.
    readme = (OUT_DIR / "README.md").read_text()
    blocks = re.findall(r"```sql\n(.*?)```", readme, re.S)
    expect(len(blocks) == 1, "semantic/README.md has one SQL block for GRR and NDR")
    if blocks:
        for year, grr, ndr in db.execute(blocks[0]).fetchall():
            expect(round(grr, 1) == kpis.loc[year, "grr"] and round(ndr, 1) == kpis.loc[year, "ndr"],
                   f"{year}: README SQL gives GRR {grr:.1f}% and NDR {ndr:.1f}%")

    # 7. Sample estimates land near the full-population totals (information only).
    estimated, actual = db.execute(
        f"SELECT (SELECT {metric['estimated_ui_hours']} FROM {USAGE}), (SELECT {metric['ui_hours']} FROM {FACT})"
    ).fetchone()
    print(f"info  estimated_ui_hours is {estimated / actual:.1%} of the full-population ui_hours")

    # 8. Hidden labels stay out of the public files.
    for path in (DRAFT_FILE, RELEASED_FILE):
        text = path.read_text().lower()
        expect("ai_forward" not in text and "segment_truth" not in text and "ai-forward" not in text, f"{path.name} has no hidden labels")

    print(f"\n{len(failures)} failures")
    return not failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    cfg = load_config(str(ROOT / "config.yaml"))
    model = build_model(cfg)
    OUT_DIR.mkdir(exist_ok=True)
    write(DRAFT_FILE, model, DRAFT_VERSION)
    write(RELEASED_FILE, to_released(model), RELEASED_VERSION)
    print(f"wrote {DRAFT_FILE.relative_to(ROOT)} and {RELEASED_FILE.relative_to(ROOT)}")
    if args.check and not check(model, cfg):
        sys.exit(1)


if __name__ == "__main__":
    main()
