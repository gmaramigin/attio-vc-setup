# VC data model for Attio: the single source of truth

Episode 2 of Craftt Live: "How to build Attio for VC teams". Thu 22 Oct 2026, 19:00 Tashkent.
Every other file in this folder (FigJam board, schema.json, seed, script, announcements) follows this spec.
Change it here first.

The fund in the demo is **Northwind Ventures**: a seed and Series A fund, Fund I (2021, $40M, investing out of reserves) and Fund II (2026, $75M target, raising now).

## One workspace, built on air

A Pro workspace with Deals switched on and no VC model yet. On the stream Claude Code runs `apply_schema.py` from a prompt, then `seed.py` loads the fictional fund, and blocks 3–5 run on that data. Nothing is built in advance except the FigJam board.

`seed.py` backdates stage history through Attio's write-values endpoint with `replace_history: true` (beta), so time-in-stage reports have months of data straight after the seed. If the endpoint refuses, `seed.py` falls back to plain stage writes: every deal entered its stage today, and the time-in-stage report is flat. `seed.py` prints which mode ran.

## Objects

### Companies (standard)
Startups we look at, our portfolio, LPs that are institutions, and co-investor funds. One object, split by `company_type`.

| Attribute | api_slug | Type | Values / notes |
|---|---|---|---|
| Company type | `company_type` | select | Startup · LP · Co-investor · Service provider |
| LP type | `lp_type` | select | Fund of funds · Family office · Endowment · Corporate · HNWI vehicle. Only for LPs |
| Sector | `sector` | select, multi | AI infra · Fintech · Climate · Health · Dev tools · Marketplaces · Vertical SaaS |
| Funding stage | `funding_stage` | select | Pre-seed · Seed · Series A · Series B · Series C+ |
| HQ country | `hq_country` | text | |
| Founded year | `founded_year` | number | |
| Total raised | `total_raised` | currency USD | |
| Last round date | `last_round_date` | date | |
| Source | `source` | select | Warm intro · Founder referral · Co-investor · Inbound · Outbound · Event |
| Referred by | `referred_by` | record ref → People | one-way |

### People (standard)
Founders, LP contacts, partners at co-investors, advisors.

| Attribute | api_slug | Type | Values / notes |
|---|---|---|---|
| Role | `vc_role` | select, multi | Founder · LP contact · Co-investor partner · Angel · Advisor |
| Warm intro strength | `intro_strength` | rating | 1–5 |
| LinkedIn | standard | | |

### Deals (standard)
One deal = one company raising one round that we are looking at.

| Attribute | api_slug | Type | Values / notes |
|---|---|---|---|
| Stage | `stage` (standard status) | status | Sourced · First call · Partner meeting · Diligence · IC · Term sheet · Invested · Passed. Archive the four defaults. |
| Round | `round` | select | Pre-seed · Seed · Series A · Series B |
| Round size | `round_size` | currency USD | |
| Our check | `our_check` | currency USD | |
| Pre-money valuation | `pre_money` | currency USD | |
| Lead investor | `lead_investor` | record ref → Companies | one-way |
| Fund | `fund` | record ref → Funds | two-way, many deals → one fund (reverse `deals` on Funds) |
| Deal owner | `owner` (standard) | actor reference (workspace member) | The partner who owns the deal. Required on every deal. |
| Source | `deal_source` | select | same options as Companies · Source |
| Pass reason | `pass_reason` | select | Team · Market size · Valuation · Traction · Outside thesis · Lost to competitor |
| Next step date | `next_step_date` | date | |
| Associated company | standard | | |

Target time in status (drives the red badge on cards): First call 14 d · Partner meeting 14 d · Diligence 30 d · IC 7 d · Term sheet 21 d.

### Funds (custom object)
| Attribute | api_slug | Type | Values / notes |
|---|---|---|---|
| Name | `name` | text | Create it yourself, custom objects have none |
| Vintage | `vintage` | number | |
| Fund size | `fund_size` | currency USD | target for a fund still raising |
| Status | `fund_status` | select | Fundraising · Investing · Harvesting · Closed |
| Strategy | `strategy` | text | |

### Investments (custom object)
One record = one cheque. A follow-on is a second record.

| Attribute | api_slug | Type | Values / notes |
|---|---|---|---|
| Name | `name` | text | "Ledgerline · Seed · Fund I" |
| Company | `company` | record ref → Companies | two-way, reverse `investments` (multi) on Companies |
| Fund | `fund` | record ref → Funds | two-way, reverse `investments` (multi) on Funds |
| Deal | `deal` | record ref → Deals | two-way 1:1, reverse `investment` on Deals |
| Round | `round` | select | Pre-seed · Seed · Series A · Series B · Follow-on |
| Instrument | `instrument` | select | Equity · SAFE · Convertible note |
| Date invested | `date_invested` | date | |
| Amount invested | `amount_invested` | currency USD | |
| Ownership % | `ownership_pct` | number | percent display |
| Current fair value | `fair_value` | currency USD | |
| Board seat | `board_seat` | checkbox | |
| MOIC | formula, UI only | `{Current fair value} / {Amount invested}` | the API cannot create formulas, build this one by hand (callback to episode 1) |

### Commitments (custom object)
One record = one LP's commitment to one fund. An LP in Fund I that is back for Fund II has two records. That is why this is an object and not a list: a list holds a company once, and a list per fund means a new list for Fund III and no total per LP.

| Attribute | api_slug | Type | Values / notes |
|---|---|---|---|
| Name | `name` | text | "Harrowgate Family Office · Fund II" |
| LP | `lp` | record ref → Companies | two-way, reverse `commitments` (multi) on Companies |
| Fund | `fund` | record ref → Funds | two-way, reverse `commitments` (multi) on Funds |
| LP contact | `lp_contact` | record ref → People | one-way |
| Stage | `lp_stage` | status | Target · Intro made · First meeting · Data room · Soft circle · Committed · Declined |
| Target ticket | `target_ticket` | currency USD | |
| Committed amount | `committed_amount` | currency USD | |
| Owner | `lp_owner` | actor reference | |

## Lists

### Portfolio (parent: Companies)
| Attribute | api_slug | Type | Values |
|---|---|---|---|
| Health | `health` | status | On track · Watch · At risk · Exited · Written off |
| Board owner | `board_owner` | actor reference | |
| Last update received | `last_update_received` | date | |
| Next board meeting | `next_board_meeting` | date | |
| Runway (months) | `runway_months` | number | |

### Co-investor network (parent: Companies, `company_type = Co-investor`)
| Attribute | api_slug | Type | Values |
|---|---|---|---|
| Relationship strength | `relationship_strength` | rating | 1–5 |
| Last co-invest | `last_coinvest` | date | |
| Typical check | `typical_check` | currency USD | |

## Views (block 3)
- Deals · **Pipeline** kanban by Stage. Card: Associated company, Round, Our check, Deal owner, Next step date. Column sum on Our check.
- Deals · **My deals** table, filter Deal owner = me, Stage not Invested/Passed, sort Next step date.
- Deals · **Passed, last 90 days** table, filter Stage = Passed, grouped by Pass reason.
- Portfolio · table grouped by Health, columns Board owner, Last update received, Runway.
- Portfolio · **Update overdue** filter Last update received older than 45 days.
- Commitments · **Fund II fundraise** kanban by Stage, filter Fund = Fund II, column sums on Target ticket and Committed amount.
- Record page: Companies highlights Company type, Funding stage, Sector, Total raised, Source. Deals highlights Stage, Round, Our check, Deal owner, Fund. Investments highlights Amount, Fair value, MOIC, Ownership.

## Automations (block 4)
1. **Deal reaches IC** → task "Write IC memo" for Deal owner, due +2 days → Slack message to #ic with the deal link.
2. **Passed needs a reason** → object Rule on Deals: Stage = Passed requires Pass reason. Then a workflow: task "Send pass note to founder" due +1 day. (Rules apply to UI edits only, the API bypasses them.)
3. **Invested** → create Investments record linked to the deal, company and fund → add company to Portfolio with Health = On track and Board owner = Deal owner.
4. **Monthly update chase** → recurring, 1st of the month: Portfolio entries with Last update received older than 45 days → task for Board owner.
5. **LP committed** (Commitments, Stage becomes Committed) → Slack message to #fundraise with amount, and a task to send the subscription docs.

## Reports (block 5), one dashboard "Monday partner meeting"
1. Funnel Sourced → Invested, last 12 months.
2. Deals by Source, stacked by Stage: which source reaches Partner meeting.
3. Time in stage on Deals: where deals stall.
4. Pass reasons, last 90 days.
5. Fund II: Commitments where Fund = Fund II, sum of Committed amount vs Target ticket by Stage.
6. Investments: sum of Current fair value and Amount invested by Fund.

## Seeded story
The seed plants these, and `stats.py` re-counts them:
- 180 deals: Sourced 52 · First call 34 · Partner meeting 22 · Diligence 14 · IC 6 · Term sheet 3 · Invested 24 · Passed 25.
- Warm intro deals reach Partner meeting about 4× as often as Inbound.
- 9 deals have sat in Diligence for 38–70 days, past the 30-day target, and top the time-in-stage report. `seed.py` backdates their history (beta endpoint, `replace_history: true`), and `drift.py` never moves them. Fallback, if the endpoint refuses: they enter Diligence on seed day and no deal is past its target. `seed.py` prints which mode ran.
- 7 of 24 portfolio companies have not sent an update in 45+ days, 3 of them with runway under 9 months.
- Fund I: $40M from 12 LPs, closed 2021; some of them are back in the Fund II pipeline.
- Fund II: $75M target, $31M soft-circled, $18M committed.
- 6 deals in Passed have no Pass reason (made before the Rule existed).
