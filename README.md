# Attio for VC teams: the data model in one run

This repo builds a venture fund's CRM in an empty Attio workspace: 2 new objects, 36 attributes across 5 objects (4 of them two-way links), 3 lists with 13 list attributes, and an 8-stage deal pipeline. It runs from a GitHub Action, so your Attio token never sits in code, in chat or on your screen.

It was built live on [Craftt Live, episode 2](https://www.craftt.io/webinars), 23 Oct 2026. The full spec is in [DATA_MODEL.md](DATA_MODEL.md).

## What you get

| Where | What |
|---|---|
| Companies | Company type (Startup, LP, Co-investor, Service provider), Sector, Funding stage, HQ country, Founded year, Total raised, Last round date, Source, Referred by |
| People | Role (Founder, LP contact, Co-investor partner, Angel, Advisor), Warm intro strength |
| Deals | Stages Sourced → First call → Partner meeting → Diligence → IC → Term sheet → Invested / Passed, with target time per stage. Round, Round size, Our check, Pre-money, Lead investor, Fund, Deal owner (Attio's standard owner), Source, Pass reason, Next step date |
| Funds (new object) | Name, Vintage, Fund size, Status, Strategy |
| Investments (new object) | One record per cheque: Company, Fund, Deal, Round, Instrument, Date, Amount, Ownership %, Fair value, Board seat |
| Lists | Portfolio (health, board owner, last update, runway), Fund II fundraise (LP stages and amounts), Co-investor network |

`seed.py` adds an optional demo fund, Northwind Ventures: about 300 companies, 380 people, 180 deals with backdated stage history, 24 investments and 94 list entries. Every name is invented. Use it in a test workspace only.

## Before you start

- **Attio Pro or Enterprise.** Funds and Investments are custom objects, and Attio's Free and Plus plans do not allow them. On Plus the script stops with a message at the first custom object.
- **Turn on Deals.** Attio → Workspace settings → Objects → Deals → Activate. The API cannot do it.
- **Use an empty or test workspace first.** The script only adds things and never deletes, but a second "Stage" pipeline on top of yours is a mess to undo.

## 1. Create the Attio token

Attio → Workspace settings → Developers → **New access token**. Name it `vc-setup` and tick these scopes:

| Scope | Level | Needed for |
|---|---|---|
| Object configuration | Read-write | objects and attributes |
| List configuration | Read-write | lists and list attributes |
| Records | Read-write | seed only |
| List entries | Read-write | seed only |
| User management | Read | seed only, to assign deal owners |

Attio shows the token once. If you are sharing your screen, stop sharing before you click Create, and copy it straight to the clipboard.

## 2. Put the token into GitHub as a secret

Fork or copy this repo, then do one of the two.

**Terminal** (the token never appears on screen):

```bash
pbpaste | gh secret set ATTIO_API_KEY --repo <you>/attio-vc-setup
gh secret list --repo <you>/attio-vc-setup    # shows the name and date, never the value
```

On Linux use `xclip -o` or `wl-paste` instead of `pbpaste`. On Windows PowerShell: `Get-Clipboard | gh secret set ATTIO_API_KEY`.

**Browser**: your repo → Settings → Secrets and variables → Actions → New repository secret. Name `ATTIO_API_KEY`, paste the token into Secret, click Add secret. The field is not masked while you type, so paste and save with the screen share off.

GitHub never shows the secret again, and if a script ever prints it, the log shows `***`.

## 3. Run it

Repo → Actions → **Attio VC setup** → Run workflow.

1. Job `schema`, Dry run ticked. The log lists every object, attribute, option and status it would create. Nothing is written.
2. Same job, Dry run unticked. Takes about a minute. Run it again and it reports everything as already there.
3. Optional, test workspace only: job `seed`, then job `stats` to print the numbers.

## Run it locally instead

```bash
echo ".env" >> .gitignore                       # already there in this repo
pbpaste | sed 's/^/ATTIO_API_KEY=/' > .env      # the token goes straight from clipboard to file
python3 apply_schema.py --dry-run
python3 apply_schema.py
```

Python 3.10 or newer, no packages to install. The scripts read `ATTIO_API_KEY` from the environment or from `.env`, and print the workspace name and scopes before they write anything.

## What the API cannot build

Attio's API creates objects, attributes, options, statuses and lists. Everything below is UI only, and the episode builds it on screen:

- The record title on Funds and Investments (set **Name** as the title in object settings)
- Formula attributes, such as MOIC = `{Current fair value} / {Amount invested}`
- Percent display on Ownership %
- Views, kanban cards, record page highlights
- Rules (for example "Passed needs a Pass reason") and Workflows
- Reports and dashboards

## When you are done

Revoke the token: Attio → Workspace settings → Developers → the token → Delete. Then remove the secret: `gh secret delete ATTIO_API_KEY`. A token that sits unused for months is a key to your fund's whole pipeline.

## Files

| File | What it does |
|---|---|
| `DATA_MODEL.md` | The spec. Change the model here first. |
| `schema.json` | The spec as data, read by `apply_schema.py` |
| `apply_schema.py` | Creates what is missing, skips what exists |
| `seed.py` | Demo data with backdated stage history |
| `drift.py` | Moves a few deals forward, once a day before a demo |
| `stats.py` | Recounts the demo numbers |
| `CLAUDE.md`, `PROMPT.md` | How Claude Code works in this repo, and the prompt used on air |

Built by [Craftt](https://www.craftt.io). We set Attio up for revenue and investment teams. Free workspace audit: [craftt.io/free-audit](https://www.craftt.io/free-audit).
