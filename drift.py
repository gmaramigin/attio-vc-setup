#!/usr/bin/env python3
"""Move a few deals and LPs one stage forward, so the pipeline looks alive on the night.

Run once a day from 13 to 22 Oct. Each run moves about 8 open deals and 2 Fund II commitments.
It never touches the 9 deals planted in Diligence, never moves anything into Invested,
Passed, Soft circle or Committed, and picks the same records if run twice on one day.

    python3 drift.py --dry-run
    python3 drift.py
"""
import argparse
import datetime as dt
import random

from attio import Attio, check_scopes
from seed import planted_deal_names
from values import scalar, title

DEAL_NEXT = {"Sourced": "First call", "First call": "Partner meeting", "Partner meeting": "Diligence",
             "Diligence": "IC", "IC": "Term sheet"}
LP_NEXT = {"Target": "Intro made", "Intro made": "First meeting", "First meeting": "Data room"}
DEALS_PER_RUN, LPS_PER_RUN = 8, 2


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    api = Attio(dry_run=args.dry_run)
    check_scopes(api.identify(), "seed")
    rng = random.Random(dt.date.today().isoformat())
    planted = planted_deal_names()

    deals = api.query_all("/objects/deals/records/query")
    movable = [d for d in deals if title(d["values"], "stage") in DEAL_NEXT
               and scalar(d["values"], "name") not in planted]
    for d in rng.sample(movable, min(DEALS_PER_RUN, len(movable))):
        cur = title(d["values"], "stage")
        # Status alone in its own PATCH: Attio can drop it when sent with other attributes.
        api.patch(f"/objects/deals/records/{d['id']['record_id']}", {"data": {"values": {"stage": DEAL_NEXT[cur]}}})
        print(f"deal  {scalar(d['values'], 'name')}: {cur} → {DEAL_NEXT[cur]}")

    entries = api.query_all("/objects/commitments/records/query")
    movable = [e for e in entries if title(e["values"], "lp_stage") in LP_NEXT]
    for e in rng.sample(movable, min(LPS_PER_RUN, len(movable))):
        cur = title(e["values"], "lp_stage")
        api.patch(f"/objects/commitments/records/{e['id']['record_id']}",
                  {"data": {"values": {"lp_stage": LP_NEXT[cur]}}})
        print(f"LP    {scalar(e['values'], 'name')}: {cur} → {LP_NEXT[cur]}")

if __name__ == "__main__":
    main()
