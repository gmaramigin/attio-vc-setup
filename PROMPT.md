# The prompt used on air

Paste this into Claude Code, opened in this repo. Claude never sees the token: it lives in GitHub as a secret, and the Action reads it from there.

## Build the model

The token is already in GitHub: repo → Settings → Secrets and variables → Actions → `ATTIO_API_KEY`.

```
Read DATA_MODEL.md and CLAUDE.md.

Build this VC data model in our Attio workspace through the GitHub Action.
The ATTIO_API_KEY secret is already set. I approve the changes up front,
so skip the dry run and do not wait for me.

1. Run: gh workflow run "Attio VC setup" -f job=schema -f dry_run=false
2. Watch the run with gh run watch until it finishes.
3. From the run log, show the workspace name and summarise what was created,
   grouped by object and list.
4. List what I still have to do by hand in the Attio UI, in order.
```

## Variations for Q&A

Add an attribute from chat:

```
Add a select attribute "Thesis fit" to Deals with options Core, Adjacent, Opportunistic.
Update DATA_MODEL.md and schema.json, dry-run, show me, then apply.
```

Run it in GitHub instead of locally:

```
Commit and push the schema change. Then tell me the exact clicks to run the
"Attio VC setup" workflow with job = schema, first as a dry run.
```
