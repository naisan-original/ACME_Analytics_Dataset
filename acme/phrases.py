"""Phrase banks for touchpoint notes (spec Sections 2.8 and 6.4).

A note is an opener, a theme sentence and sometimes a closer. Each theme yields far more than the
30 variants the spec asks for once openers and closers combine.
"""
OPENERS = [
    "", "", "", "Spoke with the account team.", "Follow-up from last week.", "Monthly sync.",
    "Quick call with the sponsor.", "Met with the data lead.", "Notes from today's session.",
    "Touched base with the champion.",
]
CLOSERS = [
    "", "", "", "Will follow up next month.", "Next step is on us.", "Sending a recap today.",
    "Scheduling time with the wider team.", "No action needed yet.", "Logged in the account plan.",
    "Flagged to the account lead.",
]

THEMES = {
    "discovery": [
        "Exploring options for a central analytics platform.", "Current stack is fragmented and they want to simplify.",
        "Team is comparing vendors for next year's budget.", "Interested in a proof of concept once scope is set.",
        "Early conversation about reporting pain across business units.", "They asked for pricing guidance and references.",
        "Sponsor wants a view of total cost before going further.", "Evaluating whether to replace a legacy BI tool.",
    ],
    "onboarding": [
        "Kickoff completed and the workspace is provisioned.", "First users are through training and building content.",
        "SSO is live and data sources are connected.", "Rollout plan agreed for the first two departments.",
        "Admins finished setup and first dashboards are published.", "Migration of existing reports is on schedule.",
        "Enablement sessions are booked for the next cohort.", "Initial use cases are defined with named owners.",
    ],
    "adoption": [
        "Usage is steady and the team sees good value.", "A new department wants access next quarter.",
        "Champion shared a strong internal success story.", "Power users are building more reusable content.",
        "Adoption is healthy across the core team.", "They asked for advanced training for analysts.",
        "Weekly active usage is trending in the right direction.", "Leadership now reviews dashboards in staff meetings.",
    ],
    "qbr": [
        "Reviewed goals, usage trends and the roadmap.", "QBR went well and sponsors are engaged.",
        "Walked through value delivered this quarter.", "Agreed priorities for the next two quarters.",
        "Executive sponsor attended and asked good questions.", "Roadmap review drew interest in new capabilities.",
        "Scorecard is mostly green with a few open items.", "Discussed success metrics for the coming year.",
    ],
    "renewal": [
        "Renewal discussion started and terms look standard.", "Procurement engaged on paperwork for the renewal.",
        "Customer expects to renew at current scope.", "Working through renewal timing with finance.",
        "Renewal is on track with no major objections.", "Discussing a multi-year option at renewal.",
        "Redlines came back with only minor changes.", "Sponsor confirmed budget for next term.",
    ],
    "expansion": [
        "Good appetite for more seats next term.", "New team wants licenses for a regional rollout.",
        "Interested in adding the Data Engine alongside Analytics.", "Exploring the Machine Learning product for a pilot.",
        "Usage growth supports a larger footprint.", "Sponsor asked for a proposal covering more users.",
        "Second business unit is asking to join the contract.", "They want to standardize more teams on the platform.",
    ],
    "budget": [
        "Finance is reviewing all software spend this year.", "Budget owner wants to right-size ahead of renewal.",
        "Spend review is underway across the department.", "They are asking for flexibility on price.",
        "Cost pressure came up several times in the meeting.", "Sponsor must justify the line item to the CFO.",
        "Headcount cuts may reduce license needs.", "Vendor consolidation is on the agenda this year.",
    ],
    "champion": [
        "Our champion is moving to a new role.", "New data leader started and is reviewing tools.",
        "Sponsor left the company and we are rebuilding the relationship.", "Reorg changed who owns this budget.",
        "Need to re-establish executive coverage.", "New stakeholder is unfamiliar with the platform.",
        "Primary contact is changing teams next month.", "We lost our main advocate after the restructure.",
    ],
    "support": [
        "Open ticket on slow dashboard load times.", "Escalation on a failed data refresh was resolved.",
        "They raised concerns about response times.", "Connector issue is blocking one team.",
        "Permissions problem affected several users.", "Performance degraded during month-end close.",
        "Bug fix shipped and the customer confirmed it.", "Support escalation is closed and the team is satisfied.",
    ],
    "macro": [
        "Budget freeze is in place through the next quarter.", "Procurement delay pushed the decision out.",
        "New purchasing controls are slowing all approvals.", "Regional spending is on hold pending a review.",
        "Macro uncertainty has paused new initiatives.", "Finance froze discretionary software purchases.",
        "Decision moved to next quarter because of budget timing.", "Procurement added another approval step.",
    ],
    "transition": [
        "Introduced myself as the new account owner.", "Picking up this account after the previous owner left.",
        "Transition call to reset contacts and priorities.", "Customer asked who now covers their account.",
        "Reviewing history after inheriting this account.", "Rebuilding context following the coverage change.",
        "Customer noted a gap in contact during the handover.", "Handover is complete and cadence is restarting.",
    ],
    "programmatic": [
        "They are building an internal copilot on top of their data.",
        "Agents now query the Data Engine directly rather than going through dashboards.",
        "Fewer analysts are logging in as work moves to automated workflows.",
        "Most consumption is now programmatic.", "Traffic has shifted heavily toward API access.",
        "Service accounts now drive the bulk of their activity.",
        "Their engineers are wiring models straight into the warehouse layer.",
        "Dashboard use is fading as teams ask questions through an internal assistant.",
        "Team is prototyping agent workflows against our APIs.",
        "They mentioned pipelines that run with no human in the loop.",
    ],
    "seat_pressure": [
        "They want to consolidate seats at renewal.", "Sponsor asked why seats are needed when usage is automated.",
        "Expect a renewal at reduced seats.", "They see less need for named users going forward.",
        "Finance questioned paying per seat for machine traffic.", "Licensed seats are well above active humans now.",
        "They asked whether pricing can reflect API usage rather than seats.",
        "A seat reduction request is coming with the renewal.",
    ],
    "llm_alternatives": [
        "They are evaluating LLM-native analytics tools.", "A pilot with an AI analytics startup is underway.",
        "Leadership wants a conversational interface in place of dashboards.",
        "They may replace the BI layer with something built in-house.",
        "Team is testing natural language querying from another vendor.",
        "Asked about our roadmap for agent-based access.",
        "Internal AI team is proposing to retire several tools.",
        "They are benchmarking in-house assistants against our product.",
    ],
}

AI_THEMES = ["programmatic", "seat_pressure", "llm_alternatives"]


def note(rng, theme):
    parts = [
        OPENERS[rng.integers(len(OPENERS))],
        THEMES[theme][rng.integers(len(THEMES[theme]))],
        CLOSERS[rng.integers(len(CLOSERS))],
    ]
    return " ".join(part for part in parts if part)
