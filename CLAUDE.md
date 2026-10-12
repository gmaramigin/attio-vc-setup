# Working in this repo

This repo turns `DATA_MODEL.md` into an Attio workspace through Attio's REST API (`https://api.attio.com/v2`). Python standard library only.

## The token

- The token is `ATTIO_API_KEY`: a GitHub Actions secret in CI, a line in `.env` locally. `attio.py` reads it.
- Never print, echo, `cat`, log or paste it, and never put it in a file other than `.env`. Do not run `env`, `printenv` or `cat .env`.
- To check which workspace the token points at, run `python3 apply_schema.py --dry-run`: it calls `GET /v2/self` and prints the workspace name and scopes only.
- If the token is missing, ask the user to add it. Do not ask them to paste it into the chat.

## How to change the model

1. `DATA_MODEL.md` is the spec. Edit it first, then mirror the change in `schema.json`. They must agree.
2. Run `python3 apply_schema.py --dry-run` and show the user the plan before any write.
3. Apply only after the user says yes. `apply_schema.py` is idempotent: it skips what exists and never deletes.
4. Never delete or archive attributes, options or records unless the user asks for that exact item. Archiving a select option blanks every record that held it.

## Attio API rules that bite

- `config` is required on every attribute create. Send `{}` for text, number, date, checkbox, select, status, rating and actor-reference.
- A two-way link is a record-reference with a top-level `relationship` block beside `config`, not inside it. Without it the link is one-way and the API still returns 200.
- `is_unique: true` is refused on create.
- Select options and statuses are separate calls after the attribute exists (`/options`, `/statuses`). Statuses carry `target_time_in_status` as an ISO 8601 duration, such as `P14D`.
- Standard objects (Companies, People, Deals) cannot be renamed through the API. Deals must be activated in the UI first.
- Custom objects need the Pro plan, and they get no name or title attribute: create `name` yourself and set it as the title in the UI.
- Write a status attribute in a PATCH of its own. Sent together with other attributes it can be dropped silently with a 200. Re-query to confirm.
- PATCH appends to multi-select values; PUT overwrites.
- The API cannot create formulas, views, Rules, workflows or reports. Say so and give the UI steps instead.
- Stage history can be backdated with `PUT .../attributes/{attr}/values` and `replace_history: true` (beta). It destroys the existing history of that attribute, so use it only on records the seed just created.
- When unsure whether an endpoint exists, read `https://docs.attio.com/llms.txt`.
