#!/usr/bin/env python3
"""Recount the seeded story from the live workspace and print a table for the script.

Run it the morning of the stream. Drift changes the stage counts, so read the numbers
from here, never from DATA_MODEL.md.

    python3 stats.py
"""
import collections
import datetime as dt

from attio import Attio, check_scopes
from seed import REACHED, STAGE_COUNTS, planted_deal_names
from values import scalar, title


def money(n):
    return f"${n / 1e6:.1f}M"


def main():
    api = Attio()
    check_scopes(api.identify(), "stats")
    today = dt.date.today()
    rows = []

    deals = api.query_all("/objects/deals/records/query")
    stages = collections.Counter(title(d["values"], "stage") for d in deals)
    rows.append(("Deals", str(len(deals))))
    rows.append(("Deals by stage", " · ".join(f"{s} {stages.get(s, 0)}" for s in STAGE_COUNTS)))

    by_source = collections.defaultdict(lambda: [0, 0])
    for d in deals:
        src = title(d["values"], "deal_source")
        by_source[src][0] += 1
        by_source[src][1] += title(d["values"], "stage") in REACHED
    rate = {s: r / t for s, (t, r) in by_source.items() if t}
    rows.append(("Reach Partner meeting or further, by source",
                 " · ".join(f"{s} {r}/{t}" for s, (t, r) in sorted(by_source.items(), key=lambda x: str(x[0])))))
    if rate.get("Inbound"):
        rows.append(("Warm intro vs Inbound", f"{rate['Warm intro'] / rate['Inbound']:.1f}×"))

    planted = planted_deal_names()
    stuck = []
    for d in deals:
        if title(d["values"], "stage") != "Diligence":
            continue
        v = api.get(f"/objects/deals/records/{d['id']['record_id']}/attributes/stage/values").get("data", [])
        since = dt.datetime.fromisoformat(v[0]["active_from"][:19]).date() if v else today
        stuck.append(((today - since).days, scalar(d["values"], "name")))
    stuck.sort(reverse=True)
    rows.append(("In Diligence now", str(len(stuck))))
    rows.append(("Diligence past the 30-day target", str(sum(days > 30 for days, _ in stuck))))
    rows.append(("Planted Diligence deals still there", f"{sum(n in planted for _, n in stuck)} of {len(planted)}"))
    rows.append(("Longest in Diligence", ", ".join(f"{n} ({days} d)" for days, n in stuck[:3])))
    rows.append(("Passed with no Pass reason", str(sum(title(d["values"], "stage") == "Passed"
                                                       and not title(d["values"], "pass_reason") for d in deals))))

    port = api.query_all("/lists/portfolio/entries/query")
    overdue = []
    for e in port:
        last = scalar(e["entry_values"], "last_update_received")
        if last and (today - dt.date.fromisoformat(last)).days >= 45:
            overdue.append(scalar(e["entry_values"], "runway_months"))
    rows.append(("Portfolio companies", str(len(port))))
    rows.append(("Portfolio by health", " · ".join(f"{k} {v}" for k, v in
                                                   collections.Counter(title(e["entry_values"], "health") for e in port).items())))
    rows.append(("No update in 45+ days", f"{len(overdue)}, of which runway under 9 months: "
                                          f"{sum(1 for r in overdue if r is not None and r < 9)}"))

    lps = api.query_all("/lists/fund_ii_fundraise/entries/query")
    sums = collections.defaultdict(float)
    for e in lps:
        sums[title(e["entry_values"], "lp_stage")] += scalar(e["entry_values"], "committed_amount") or 0
    rows.append(("LPs in Fund II fundraise", str(len(lps))))
    rows.append(("Fund II committed", money(sums["Committed"])))
    rows.append(("Fund II soft circle (not yet committed)", money(sums["Soft circle"])))
    rows.append(("Fund II committed + soft circle", money(sums["Committed"] + sums["Soft circle"])))

    inv = api.query_all("/objects/investments/records/query")
    paid = sum(scalar(i["values"], "amount_invested") or 0 for i in inv)
    fair = sum(scalar(i["values"], "fair_value") or 0 for i in inv)
    rows.append(("Investments / invested / fair value", f"{len(inv)} / {money(paid)} / {money(fair)}"))
    if paid:
        rows.append(("Fund I gross MOIC", f"{fair / paid:.2f}×"))

    print(f"\n| Claim ({today}) | Number |\n|---|---|")
    for k, v in rows:
        print(f"| {k} | {v} |")


if __name__ == "__main__":
    main()
