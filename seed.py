#!/usr/bin/env python3
"""Fill a workspace that already has the VC schema with a fictional fund, Northwind Ventures.

Every name is invented. The dataset is deterministic: the same names, stages and amounts on
every run. Dates are relative to the day you run it.

    python3 seed.py --dry-run        # print every request, send nothing
    python3 seed.py                  # seed (refuses if Funds already has records)
    python3 seed.py --no-history     # skip the stage-history backfill

Stage history: Attio's "write attribute values" endpoint (beta) can backdate a record's value
history, so the time-in-stage report has months of data on day one. If the endpoint refuses,
the script falls back to plain stage writes and history starts on the day you seed.
"""
import argparse
import datetime as dt
import random
import sys
from concurrent.futures import ThreadPoolExecutor

from attio import Attio, AttioError, check_scopes

SEED = 23102026
STAGES = ["Sourced", "First call", "Partner meeting", "Diligence", "IC", "Term sheet", "Invested"]
STAGE_COUNTS = {"Sourced": 52, "First call": 34, "Partner meeting": 22, "Diligence": 14,
                "IC": 6, "Term sheet": 3, "Invested": 24, "Passed": 25}
REACHED = {"Partner meeting", "Diligence", "IC", "Term sheet", "Invested"}
# (total deals, deals that reached Partner meeting or further). Warm intro 30/45 = 67 %,
# Inbound 8/50 = 16 %: about 4x. Totals add up to 180 and 69.
SOURCE_MIX = {"Warm intro": (45, 30), "Inbound": (50, 8), "Founder referral": (25, 12),
              "Co-investor": (25, 11), "Outbound": (20, 5), "Event": (15, 3)}
PLANTED_DILIGENCE = 9          # stuck in Diligence, never moved by drift.py
PASSED_WITHOUT_REASON = 6
PORTFOLIO_HEALTH = ["On track"] * 13 + ["Watch"] * 5 + ["At risk"] * 4 + ["Exited", "Written off"]
UPDATE_OVERDUE = 7             # portfolio companies with no update in 45+ days
OVERDUE_LOW_RUNWAY = 3         # of those, runway under 9 months
LP_STAGES = ["Target"] * 10 + ["Intro made"] * 7 + ["First meeting"] * 7 + ["Data room"] * 5 + \
            ["Soft circle"] * 4 + ["Committed"] * 4 + ["Declined"] * 3
COMMITTED = [6_000_000, 5_000_000, 4_000_000, 3_000_000]       # $18M committed
SOFT_CIRCLED = [4_500_000, 3_500_000, 3_000_000, 2_000_000]    # + $13M soft circle = $31M
TARGET_DAYS = {"First call": 14, "Partner meeting": 14, "Diligence": 30, "IC": 7, "Term sheet": 21}

SECTORS = ["AI infra", "Fintech", "Climate", "Health", "Dev tools", "Marketplaces", "Vertical SaaS"]
COUNTRIES = ["United Kingdom", "Germany", "France", "Netherlands", "Estonia", "Poland", "Spain",
             "Sweden", "United States", "Portugal", "Lithuania", "Ireland"]
PASS_REASONS = ["Team", "Market size", "Valuation", "Traction", "Outside thesis", "Lost to competitor"]

NAME_A = ["Ledger", "Kiln", "Tessel", "Orchard", "Corvid", "Bramble", "Quill", "Harbor", "Lattice",
          "Cinder", "Marrow", "Pylon", "Sorrel", "Tallow", "Umber", "Wicket", "Yarrow", "Zephyr",
          "Alder", "Basalt", "Cobalt", "Drover", "Ember", "Fennel", "Gantry", "Heron", "Ivory",
          "Juniper", "Kestrel", "Loam"]
NAME_B = ["line", "works", "base", "loop", "stack", "grid", "path", "mint", "yard", "field",
          "craft", "labs", "ly", "io", "hq"]
FIRST = ["Amara", "Ben", "Chiara", "Dmitri", "Elif", "Farah", "Gustav", "Hana", "Ivo", "Jonas",
         "Keiko", "Lena", "Marek", "Nadia", "Oskar", "Priya", "Quentin", "Rosa", "Sami", "Tilda",
         "Uri", "Vera", "Wiktor", "Ximena", "Yusuf", "Zofia", "Aiko", "Bruno", "Clara", "Davit",
         "Emeka", "Freya", "Goran", "Helga", "Idris", "Julia", "Kofi", "Leila", "Mateo", "Noor"]
LAST = ["Abara", "Brandt", "Castellano", "Duval", "Ekström", "Fischer", "Grabowski", "Haddad",
        "Ilves", "Jansen", "Kowalczyk", "Lindqvist", "Moreau", "Novak", "Okafor", "Petrov",
        "Quintero", "Rossi", "Sato", "Tamm", "Ueda", "Valdés", "Weber", "Xu", "Yilmaz", "Zielinski",
        "Achterberg", "Bianchi", "Costa", "Delacroix"]
LP_ROOTS = ["Harrowgate", "Merriweather", "Ashcombe", "Linwood", "Thornbury", "Calloway", "Penrose",
            "Fairholme", "Wexley", "Brightmoor", "Stanmere", "Oakhurst", "Redcliffe", "Elmstead",
            "Kingsmoor", "Holloway", "Gresham", "Aldmere", "Westbrook", "Carrow"]
LP_KINDS = {"Fund of funds": "Fund of Funds", "Family office": "Family Office",
            "Endowment": "Endowment Trust", "Corporate": "Corporate Ventures",
            "HNWI vehicle": "Holdings"}
COINV_ROOTS = ["Granite", "Northlight", "Saltmarsh", "Bellwether", "Riverstone", "Foxglove",
               "Highmoor", "Larkspur", "Copperbeech", "Driftwood", "Silverpine", "Stonebridge",
               "Blackthorn", "Clearwater", "Hollin", "Ravensworth", "Tidewater", "Wildmere",
               "Amberley", "Coldharbour", "Fernhill", "Greywater", "Ironbridge", "Kingfisher",
               "Longmeadow", "Marlow", "Nettlebed", "Oxbow", "Pinehurst", "Quarrybank"]
COINV_SUFFIX = ["Capital", "Ventures", "Partners"]


def build_dataset():
    """Everything that does not depend on today's date or on API ids. drift.py imports this."""
    rng = random.Random(SEED)
    names = [a + b for a in NAME_A for b in NAME_B]
    rng.shuffle(names)
    names = [n[0].upper() + n[1:] for n in names]

    # Stages, then sources assigned so the Warm intro / Inbound ratio holds exactly.
    stages = [s for s, n in STAGE_COUNTS.items() for _ in range(n)]
    reached_stages = [s for s in stages if s in REACHED]
    other_stages = [s for s in stages if s not in REACHED]
    rng.shuffle(reached_stages)
    rng.shuffle(other_stages)
    deals = []
    for source, (total, reached) in SOURCE_MIX.items():
        for _ in range(reached):
            deals.append({"source": source, "stage": reached_stages.pop()})
        for _ in range(total - reached):
            deals.append({"source": source, "stage": other_stages.pop()})
    rng.shuffle(deals)
    for i, d in enumerate(deals):
        d["company"] = names[i]
        d["round"] = rng.choices(["Pre-seed", "Seed", "Series A", "Series B"], [3, 5, 3, 1])[0]
        d["name"] = f"{d['company']} · {d['round']}"
    diligence = [d for d in deals if d["stage"] == "Diligence"]
    for d in diligence[:PLANTED_DILIGENCE]:
        d["planted"] = True
    passed = [d for d in deals if d["stage"] == "Passed"]
    for d in passed[PASSED_WITHOUT_REASON:]:
        d["pass_reason"] = rng.choice(PASS_REASONS)
    watchlist = names[len(deals):len(deals) + 40]
    return rng, deals, watchlist


def planted_deal_names():
    return {d["name"] for d in build_dataset()[1] if d.get("planted")}


def ref(obj, rid):
    return [{"target_object": obj, "target_record_id": rid}]


def actor(member_id):
    return [{"referenced_actor_type": "workspace-member", "referenced_actor_id": member_id}]


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Seeder:
    def __init__(self, api, history):
        self.api = api
        self.history = history
        self.now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.today = self.now.date()

    def create(self, obj, values):
        r = self.api.post(f"/objects/{obj}/records", {"data": {"values": values}})
        return r["data"]["id"]["record_id"]

    def pmap(self, fn, items, workers=6):
        with ThreadPoolExecutor(workers) as ex:
            return list(ex.map(fn, items))

    def write_history(self, path, intervals):
        """intervals: [(value, start, end_or_None)]. Returns False when the beta endpoint refuses."""
        if not self.history:
            return False
        body = {"data": {"values": [{"value": v, "active_from": iso(a), "active_until": iso(b) if b else None}
                                    for v, a, b in intervals], "replace_history": True}}
        try:
            self.api.put(path, body)
            return True
        except AttioError as e:
            if e.status in (400, 403, 404, 405):
                print(f"History backfill refused ({e.status}); falling back to plain stage writes.\n{e.body[:300]}")
                self.history = False
                return False
            raise

    def day(self, days_ago):
        return self.today - dt.timedelta(days=days_ago)

    def stage_path(self, rng, d):
        """Return [(stage, start, end)] ending now, oldest first."""
        final = d["stage"]
        if final == "Passed":
            stop = rng.choices(STAGES[:6], [10, 8, 4, 2, 1, 0.5])[0]
            path = STAGES[:STAGES.index(stop) + 1] + ["Passed"]
        else:
            path = STAGES[:STAGES.index(final) + 1]
        # time in the current stage
        if d.get("planted"):
            current = rng.randint(38, 70)
        elif final == "Invested":
            current = rng.randint(60, 1700)
        elif final == "Passed":
            current = rng.randint(3, 300)
        else:
            current = rng.randint(1, max(2, TARGET_DAYS.get(final, 20) - 2))
        end = self.now
        start = end - dt.timedelta(days=current, hours=rng.randint(0, 20))
        out = [(path[-1], start, None)]
        for s in reversed(path[:-1]):
            end = start
            start = end - dt.timedelta(days=rng.randint(2, TARGET_DAYS.get(s, 10) + 6), hours=rng.randint(0, 20))
            out.append((s, start, end))
        return list(reversed(out))

    def run(self):
        api = self.api
        rng, deals, watchlist = build_dataset()

        if api.token:
            try:
                seeded = api.post("/objects/funds/records/query", {"limit": 1}).get("data")
            except AttioError as e:
                if e.status == 404:
                    sys.exit("There is no Funds object. Run apply_schema.py first.")
                raise
            if seeded:
                sys.exit("Funds already has records, so this workspace looks seeded. Nothing written.")

        members = [m["id"]["workspace_member_id"] for m in api.get("/workspace_members").get("data", [])
                   if m.get("access_level") != "suspended"] or ["00000000-0000-0000-0000-000000000000"]
        pick = lambda: rng.choice(members)

        print("Funds")
        fund1 = self.create("funds", {"name": "Northwind Ventures Fund I", "vintage": 2021, "fund_size": 40_000_000,
                                      "fund_status": "Investing", "strategy": "Seed and Series A, Europe, B2B software."})
        fund2 = self.create("funds", {"name": "Northwind Ventures Fund II", "vintage": 2026, "fund_size": 75_000_000,
                                      "fund_status": "Fundraising", "strategy": "Seed and Series A, Europe, AI-native B2B."})

        print("Companies")
        def startup_values(name, d=None):
            rnd = d.get("round") if d else rng.choice(["Pre-seed", "Seed", "Series A"])
            raised = {"Pre-seed": (300_000, 1_500_000), "Seed": (1_500_000, 6_000_000),
                      "Series A": (6_000_000, 20_000_000), "Series B": (20_000_000, 60_000_000)}[rnd]
            v = {"name": name, "company_type": "Startup", "sector": rng.sample(SECTORS, rng.choice([1, 1, 2])),
                 "funding_stage": rnd, "hq_country": rng.choice(COUNTRIES),
                 "founded_year": rng.randint(2017, 2025), "total_raised": rng.randrange(*raised, 50_000),
                 "last_round_date": str(self.day(rng.randint(30, 700)))}
            if d:
                v["source"] = d["source"]
            return v
        startup_specs = [startup_values(d["company"], d) for d in deals] + [startup_values(n) for n in watchlist]

        lp_specs = []
        for i, stage in enumerate(LP_STAGES):
            kind = rng.choice(list(LP_KINDS))
            lp_specs.append({"name": f"{LP_ROOTS[i % len(LP_ROOTS)]} {LP_KINDS[kind]}" + (" II" if i >= len(LP_ROOTS) else ""),
                             "kind": kind, "stage": stage})
        coinv_specs = [f"{r} {COINV_SUFFIX[i % 3]}" for i, r in enumerate(COINV_ROOTS)]
        service_specs = ["Brightwater Legal", "Ledgerhouse Fund Admin", "Calder Audit", "Northgate Search",
                         "Pinecrest Tax", "Harbourline Insurance"]

        company_values = (startup_specs
                          + [{"name": l["name"], "company_type": "LP", "hq_country": rng.choice(COUNTRIES)} for l in lp_specs]
                          + [{"name": n, "company_type": "Co-investor", "hq_country": rng.choice(COUNTRIES)} for n in coinv_specs]
                          + [{"name": n, "company_type": "Service provider"} for n in service_specs])
        company_ids = self.pmap(lambda v: self.create("companies", v), company_values)
        cid = {v["name"]: i for v, i in zip(company_values, company_ids)}

        print("People")
        used = set()
        def person(company, role, title):
            while True:
                f, l = rng.choice(FIRST), rng.choice(LAST)
                if (f, l) not in used:
                    used.add((f, l))
                    break
            v = {"name": [{"first_name": f, "last_name": l, "full_name": f"{f} {l}"}],
                 "job_title": title, "vc_role": [role], "intro_strength": rng.choices([1, 2, 3, 4, 5], [3, 4, 4, 2, 1])[0]}
            if company:
                v["company"] = ref("companies", cid[company])
            return v
        people_specs = []
        for d in deals:
            people_specs.append(("founder", d["company"], person(d["company"], "Founder", "CEO & Co-founder")))
            if rng.random() < 0.6:
                people_specs.append(("founder", d["company"], person(d["company"], "Founder", rng.choice(["CTO & Co-founder", "COO & Co-founder"]))))
        for l in lp_specs:
            people_specs.append(("lp", l["name"], person(l["name"], "LP contact", rng.choice(["Investment Director", "Principal", "CIO"]))))
        for n in coinv_specs:
            for _ in range(rng.choice([1, 2])):
                people_specs.append(("coinv", n, person(n, "Co-investor partner", rng.choice(["Partner", "General Partner", "Principal"]))))
        for _ in range(20):
            people_specs.append(("angel", None, person(None, rng.choice(["Angel", "Advisor"]), rng.choice(["Angel investor", "Operator in residence", "Advisor"]))))
        people_ids = self.pmap(lambda s: self.create("people", s[2]), people_specs)
        founders, angels = {}, []
        for (kind, company, _), pid in zip(people_specs, people_ids):
            if kind == "founder":
                founders.setdefault(company, []).append(pid)
            elif kind == "angel":
                angels.append(pid)

        # Referred by: warm intros and founder referrals name the person who sent them.
        all_founders = sum(founders.values(), [])
        referrals = [(cid[d["company"]], rng.choice(angels) if d["source"] == "Warm intro" else rng.choice(all_founders))
                     for d in deals if d["source"] in ("Warm intro", "Founder referral")]
        self.pmap(lambda r: api.patch(f"/objects/companies/records/{r[0]}",
                                      {"data": {"values": {"referred_by": ref("people", r[1])}}}), referrals)

        print("Deals")
        coinv_ids = [cid[n] for n in coinv_specs]
        for d in deals:
            size = {"Pre-seed": (500_000, 2_000_000), "Seed": (2_000_000, 6_000_000),
                    "Series A": (8_000_000, 20_000_000), "Series B": (20_000_000, 45_000_000)}[d["round"]]
            d["round_size"] = rng.randrange(*size, 250_000)
            d["our_check"] = min(4_000_000, max(250_000, round(d["round_size"] * rng.uniform(0.15, 0.35), -5)))
            d["pre_money"] = round(d["round_size"] * rng.uniform(3, 5), -5)
            d["lead"] = d["round"] in ("Series A", "Series B") and rng.random() < 0.7
            d["lead_id"] = rng.choice(coinv_ids)
            d["owner"] = pick()
            d["path"] = self.stage_path(rng, d)
            d["next_step"] = str(self.today + dt.timedelta(days=rng.randint(-10, 14)))

        def make_deal(d):
            v = {"name": d["name"], "stage": d["stage"], "owner": actor(d["owner"]), "deal_lead": actor(d["owner"]),
                 "value": d["our_check"], "associated_company": ref("companies", cid[d["company"]]),
                 "associated_people": [x for p in founders.get(d["company"], []) for x in ref("people", p)],
                 "round": d["round"], "round_size": d["round_size"], "our_check": d["our_check"],
                 "pre_money": d["pre_money"], "deal_source": d["source"],
                 "fund": ref("funds", fund1 if d["stage"] in ("Invested", "Passed") else fund2)}
            if d["lead"]:
                v["lead_investor"] = ref("companies", d["lead_id"])
            if d.get("pass_reason"):
                v["pass_reason"] = d["pass_reason"]
            if d["stage"] not in ("Invested", "Passed"):
                v["next_step_date"] = d["next_step"]
            return self.create("deals", v)
        deal_ids = self.pmap(make_deal, deals)
        for d, rid in zip(deals, deal_ids):
            d["id"] = rid

        print("Stage history" if self.history else "Stage values")
        # Probe the beta endpoint once before fanning out.
        first = deals[0]
        ok = self.write_history(f"/objects/deals/records/{first['id']}/attributes/stage/values", first["path"])
        def stage_write(d):
            if not self.write_history(f"/objects/deals/records/{d['id']}/attributes/stage/values", d["path"]):
                # A status sent together with other attributes can be silently dropped; send it alone.
                api.patch(f"/objects/deals/records/{d['id']}", {"data": {"values": {"stage": d["stage"]}}})
        self.pmap(stage_write, deals[1:] if ok else deals)

        print("Investments")
        invested = [d for d in deals if d["stage"] == "Invested"]
        investments = []
        for d in invested:
            multiple = rng.choice([0.0, 0.6, 1.0, 1.0, 1.0, 1.4, 1.8, 2.5, 3.2, 6.0])
            investments.append({
                "name": f"{d['company']} · {d['round']} · Fund I", "company": ref("companies", cid[d["company"]]),
                "fund": ref("funds", fund1), "deal": ref("deals", d["id"]), "round": d["round"],
                "instrument": rng.choice(["Equity", "Equity", "SAFE", "Convertible note"]),
                "date_invested": str(d["path"][-1][1].date()), "amount_invested": d["our_check"],
                "ownership_pct": round(d["our_check"] / (d["pre_money"] + d["round_size"]) * 100, 2),
                "fair_value": round(d["our_check"] * multiple, -3), "board_seat": rng.random() < 0.4})
        self.pmap(lambda v: self.create("investments", v), investments)

        print("Portfolio list")
        health = PORTFOLIO_HEALTH[:]
        rng.shuffle(health)
        live = [i for i, h in enumerate(health) if h not in ("Exited", "Written off")]
        overdue = set(rng.sample(live, UPDATE_OVERDUE))
        low_runway = set(rng.sample(sorted(overdue), OVERDUE_LOW_RUNWAY))
        portfolio = []
        for i, d in enumerate(invested):
            last = self.day(rng.randint(46, 120) if i in overdue else rng.randint(3, 40))
            values = {"board_owner": actor(d["owner"]), "last_update_received": str(last)}
            if health[i] not in ("Exited", "Written off"):
                values["runway_months"] = rng.randint(3, 8) if i in low_runway else rng.randint(10, 30)
                values["next_board_meeting"] = str(self.today + dt.timedelta(days=rng.randint(5, 80)))
            portfolio.append((cid[d["company"]], values, health[i]))
        def make_portfolio(p):
            parent, values, h = p
            r = api.post("/lists/portfolio/entries", {"data": {"parent_record_id": parent,
                                                               "parent_object": "companies", "entry_values": values}})
            eid = r["data"]["id"]["entry_id"]
            # Status in its own PATCH, never alongside other values.
            api.patch(f"/lists/portfolio/entries/{eid}", {"data": {"entry_values": {"health": h}}})
        self.pmap(make_portfolio, portfolio)

        print("Fund II fundraise list")
        committed, soft = COMMITTED[:], SOFT_CIRCLED[:]
        lp_order = ["Target", "Intro made", "First meeting", "Data room", "Soft circle", "Committed"]
        for l in lp_specs:
            values = {"lp_type": l["kind"], "target_ticket": rng.choice([1, 2, 3, 4, 5, 6, 8]) * 1_000_000,
                      "lp_owner": actor(pick())}
            if l["stage"] == "Committed":
                values["committed_amount"] = committed.pop()
            elif l["stage"] == "Soft circle":
                values["committed_amount"] = soft.pop()
            path = lp_order[:lp_order.index(l["stage"]) + 1] if l["stage"] != "Declined" else \
                lp_order[:rng.randint(1, 4)] + ["Declined"]
            end, out = self.now, []
            for s in reversed(path):
                start = end - dt.timedelta(days=rng.randint(3, 25), hours=rng.randint(0, 20))
                out.append((s, start, None if not out else end))
                end = start
            l["values"], l["path"] = values, list(reversed(out))
        def make_lp(l):
            r = api.post("/lists/fund_ii_fundraise/entries", {"data": {"parent_record_id": cid[l["name"]],
                                                                      "parent_object": "companies", "entry_values": l["values"]}})
            eid = r["data"]["id"]["entry_id"]
            if not self.write_history(f"/lists/fund_ii_fundraise/entries/{eid}/attributes/lp_stage/values", l["path"]):
                api.patch(f"/lists/fund_ii_fundraise/entries/{eid}", {"data": {"entry_values": {"lp_stage": l["stage"]}}})
        self.pmap(make_lp, lp_specs, workers=4)

        print("Co-investor network list")
        coinv_entries = [{"parent_record_id": cid[n], "parent_object": "companies",
                          "entry_values": {"relationship_strength": rng.choices([1, 2, 3, 4, 5], [1, 3, 4, 3, 2])[0],
                                           "last_coinvest": str(self.day(rng.randint(20, 900))),
                                           "typical_check": rng.choice([500_000, 1_000_000, 2_000_000, 3_000_000, 5_000_000])}}
                         for n in coinv_specs]
        self.pmap(lambda e: api.post("/lists/co_investor_network/entries", {"data": e}), coinv_entries)

        print(f"\nDone. {api.writes} writes. Stage history backfilled: {'yes' if self.history else 'no'}.")
        print("Run stats.py next and paste its table into the script.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-history", action="store_true", help="do not backdate stage history")
    args = p.parse_args()
    api = Attio(dry_run=args.dry_run)
    check_scopes(api.identify(), "seed")
    Seeder(api, history=not args.no_history).run()


if __name__ == "__main__":
    main()
