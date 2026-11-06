"""Employee roster and account ownership (spec Sections 2.5 and 7)."""
import numpy as np
import pandas as pd

from .common import fiscal_index, stream

FIRST_NAMES = (
    "Avery Blake Casey Dakota Elliot Finley Gray Harper Indigo Jordan Kai Lane Morgan Noel Oakley "
    "Parker Quinn Reese Sage Taylor Umi Val Wren Yael Zion Amari Bellamy Corin Devon Emery"
).split()
LAST_NAMES = (
    "Ashgrove Brindle Calloway Dunmore Eastlake Fairwood Greaves Holloway Ironwood Jessop Kestrel "
    "Larkspur Merriweather Northcote Oakhurst Pemberton Quillfeather Ravenscroft Stonebridge "
    "Thistledown Underhill Vanterpool Westerby Yarrowfield Zellweger"
).split()


def _target(fy_end, t, start):
    """Interpolate the headcount target between fiscal year ends."""
    fy = fiscal_index(t)
    previous = start if fy == 0 else fy_end[fy - 1]
    return int(round(previous + (fy_end[fy] - previous) * ((t % 12) + 1) / 12))


def build_employees(cfg, calendar):
    rng = stream(cfg, "people")
    people_cfg = cfg["people"]
    turnover = cfg["red_herrings"]["rep_turnover"]
    hazard = 1 - (1 - people_cfg["attrition_annual"]) ** (1 / 12)
    staff = []
    names = set()

    def new_name():
        while True:
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if name not in names:
                names.add(name)
                return name

    def hire(role, t, territory=None):
        if territory is None:
            weights = people_cfg["territory_weights_by_fy"][fiscal_index(t)]
            territory = rng.choice(list(weights), p=list(weights.values()))
        quota = rng.uniform(*people_cfg["quota_per_ae"]) if role == "AE" else None
        staff.append(
            {"role": role, "region": str(territory), "hire": t, "term": None, "name": new_name(),
             "quota_arr": None if quota is None else round(quota, -4), "scripted_leaver": False}
        )

    def active(role, t):
        return [person for person in staff if person["role"] == role and person["term"] is None and person["hire"] <= t]

    plans = {"AE": (people_cfg["ae_fy_end"], 2, turnover["ae_leavers"]),
             "CSM": (people_cfg["csm_fy_end"], 1, turnover["csm_leavers"])}

    for t in range(calendar.months):
        for role, (fy_end, start, leavers) in plans.items():
            current = active(role, t)
            for person in current:
                if t - person["hire"] >= people_cfg["attrition_min_tenure_months"] and rng.random() < hazard:
                    person["term"] = t
            if t == turnover["start_month"]:
                local = [p for p in active(role, t) if p["region"] == turnover["territory"]]
                for person in rng.permutation(np.array(local, dtype=object))[:leavers]:
                    person["term"] = int(rng.integers(turnover["start_month"], turnover["end_month"] + 1))
                    person["scripted_leaver"] = True
            while len([p for p in active(role, t)]) < _target(fy_end, t, start):
                hire(role, t)
        for role, months in people_cfg["leader_hire_months"].items():
            if t in months:
                hire(role, t, "US-East" if rng.random() < 0.6 else "EMEA")

    table = pd.DataFrame(staff)
    table.insert(0, "employee_index", np.arange(len(table)))
    table["employee_id"] = [f"E{index + 1:04d}" for index in table["employee_index"]]
    return table


def dim_employee(employees, calendar):
    return pd.DataFrame(
        {
            "employee_id": employees["employee_id"],
            "name": employees["name"],
            "role": employees["role"],
            "region": employees["region"],
            "hire_month_id": [calendar.month_id(t) for t in employees["hire"]],
            "termination_month_id": [
                pd.NA if pd.isna(t) else calendar.month_id(int(t)) for t in employees["term"]
            ],
            "quota_arr": employees["quota_arr"],
        }
    ).astype({"termination_month_id": "Int64"})


def assign_owners(cfg, employees, territories, since, calendar):
    """Assign an AE and CSM per account per month, reassigning when an owner leaves.

    Returns owner matrices (accounts x months) and, per account, the month a scripted US-West
    leaver stopped owning it (-1 if never).
    """
    rng = stream(cfg, "owners")
    count = len(territories)
    owners = {role: np.full((count, calendar.months), -1, dtype=np.int32) for role in ("AE", "CSM")}
    disrupted = np.full(count, -1, dtype=np.int32)
    term = employees["term"].fillna(10_000).to_numpy()
    hire = employees["hire"].to_numpy()
    scripted = employees["scripted_leaver"].to_numpy()

    for role, matrix in owners.items():
        role_index = employees.index[employees["role"] == role].to_numpy()
        regions = employees.loc[role_index, "region"].to_numpy()
        current = np.full(count, -1, dtype=np.int32)
        for t in range(calendar.months):
            working = role_index[(hire[role_index] <= t) & (term[role_index] > t)]
            working_regions = regions[(hire[role_index] <= t) & (term[role_index] > t)]
            pools = {region: working[working_regions == region] for region in set(territories)}
            needs_owner = np.where(
                (since <= t) & ((current < 0) | (term[np.maximum(current, 0)] <= t))
            )[0]
            for account in needs_owner:
                lost = current[account]
                if lost >= 0 and scripted[lost] and disrupted[account] < 0:
                    disrupted[account] = t
                pool = pools[territories[account]]
                if len(pool) == 0:
                    pool = working
                current[account] = rng.choice(pool)
            matrix[:, t] = current
    return owners["AE"], owners["CSM"], disrupted
