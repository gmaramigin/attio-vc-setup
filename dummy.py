#!/usr/bin/env python3
"""Create one dummy record in each custom object (Funds, Investments, Commitments), linked to
dummy Companies, People and a Deal, with every attribute filled. Then re-read the custom
records and print any attribute that came back empty.

    python3 dummy.py --dry-run       # print every request, send nothing
    python3 dummy.py                 # create (refuses if "Dummy Fund" already exists)

Every record name starts with "Dummy" so they are easy to find and delete. seed.py refuses to
run while Funds has any record, so delete these before seeding.
"""
import argparse
import datetime as dt
import sys

from attio import Attio, check_scopes
from seed import actor, ref

FUND = "Dummy Fund"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    api = Attio(dry_run=args.dry_run)
    check_scopes(api.identify(), "seed")
    today = dt.date.today()

    if api.token and api.post("/objects/funds/records/query",
                              {"filter": {"name": FUND}, "limit": 1}).get("data"):
        sys.exit(f'"{FUND}" already exists. Nothing written.')

    members = [m["id"]["workspace_member_id"] for m in api.get("/workspace_members").get("data", [])
               if m.get("access_level") != "suspended"] or ["00000000-0000-0000-0000-000000000000"]
    owner = members[0]

    def create(obj, values):
        r = api.post(f"/objects/{obj}/records", {"data": {"values": values}})
        rid = r["data"]["id"]["record_id"]
        print(f"  + {obj}: {values.get('name') if isinstance(values.get('name'), str) else rid}")
        return rid

    def set_status(obj, rid, slug, title):
        # A status sent together with other attributes can be silently dropped; send it alone.
        api.patch(f"/objects/{obj}/records/{rid}", {"data": {"values": {slug: title}}})

    print("Default objects")
    angel = create("people", {"name": [{"first_name": "Dummy", "last_name": "Angel", "full_name": "Dummy Angel"}],
                              "job_title": "Angel investor", "vc_role": ["Angel", "Advisor"], "intro_strength": 4})
    startup = create("companies", {"name": "Dummy Startup", "company_type": "Startup",
                                   "sector": ["AI infra", "Dev tools"], "funding_stage": "Seed",
                                   "hq_country": "Estonia", "founded_year": 2023, "total_raised": 3_500_000,
                                   "last_round_date": str(today - dt.timedelta(days=30)),
                                   "source": "Warm intro", "referred_by": ref("people", angel)})
    founder = create("people", {"name": [{"first_name": "Dummy", "last_name": "Founder", "full_name": "Dummy Founder"}],
                                "job_title": "CEO & Co-founder", "vc_role": ["Founder"], "intro_strength": 3,
                                "company": ref("companies", startup)})
    lead = create("companies", {"name": "Dummy Co-investor", "company_type": "Co-investor",
                                "hq_country": "United Kingdom", "founded_year": 2012, "source": "Co-investor"})
    lp = create("companies", {"name": "Dummy LP", "company_type": "LP", "lp_type": "Family office",
                              "hq_country": "Switzerland", "founded_year": 2005, "source": "Warm intro"})
    lp_contact = create("people", {"name": [{"first_name": "Dummy", "last_name": "LP Contact", "full_name": "Dummy LP Contact"}],
                                   "job_title": "Investment Director", "vc_role": ["LP contact"], "intro_strength": 5,
                                   "company": ref("companies", lp)})

    print("Custom objects")
    fund = create("funds", {"name": FUND, "vintage": 2026, "fund_size": 50_000_000, "fund_status": "Investing",
                            "strategy": "Dummy record: Seed and Series A, Europe, B2B software."})
    deal = create("deals", {"name": "Dummy Startup · Seed", "stage": "Invested", "owner": actor(owner),
                            "value": 1_000_000, "associated_company": ref("companies", startup),
                            "associated_people": ref("people", founder), "round": "Seed",
                            "round_size": 4_000_000, "our_check": 1_000_000, "pre_money": 16_000_000,
                            "lead_investor": ref("companies", lead), "fund": ref("funds", fund),
                            "deal_source": "Warm intro", "pass_reason": "Valuation",
                            "next_step_date": str(today + dt.timedelta(days=14))})
    set_status("deals", deal, "stage", "Invested")
    investment = create("investments", {"name": "Dummy Startup · Seed · Dummy Fund",
                                         "company": ref("companies", startup), "fund": ref("funds", fund),
                                         "deal": ref("deals", deal), "round": "Seed", "instrument": "Equity",
                                         "date_invested": str(today - dt.timedelta(days=30)),
                                         "amount_invested": 1_000_000, "ownership_pct": 5.0,
                                         "fair_value": 1_500_000, "board_seat": True})
    commitment = create("commitments", {"name": "Dummy LP · Dummy Fund", "lp": ref("companies", lp),
                                        "fund": ref("funds", fund), "lp_contact": ref("people", lp_contact),
                                        "lp_stage": "Committed", "target_ticket": 5_000_000,
                                        "committed_amount": 4_000_000, "lp_owner": actor(owner)})
    set_status("commitments", commitment, "lp_stage", "Committed")

    if not api.token:
        return
    print("\nCheck: empty attributes on the custom records")
    gaps = 0
    for obj, rid in (("funds", fund), ("investments", investment), ("commitments", commitment)):
        attrs = [a["api_slug"] for a in api.get(f"/objects/{obj}/attributes").get("data", [])
                 if a.get("is_writable") and not a.get("is_archived")]
        values = api.get(f"/objects/{obj}/records/{rid}")["data"]["values"]
        empty = [s for s in attrs if not values.get(s)]
        gaps += len(empty)
        print(f"  {obj}: {len(attrs) - len(empty)}/{len(attrs)} filled" + (f", empty: {', '.join(empty)}" if empty else ""))
    print(f"\nDone. {api.writes} writes. {'All attributes filled.' if not gaps else f'{gaps} empty attributes.'}")


if __name__ == "__main__":
    main()
