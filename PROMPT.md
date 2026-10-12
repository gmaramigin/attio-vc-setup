# The prompt used on air

Paste this into Claude Code, opened in this repo. The token is already a GitHub secret and in `.env`, so the prompt never contains it.

```
Read DATA_MODEL.md and CLAUDE.md.

Build this VC data model in our Attio workspace.

1. Check schema.json matches DATA_MODEL.md: every object, attribute, select option,
   status, target time and list. Fix schema.json if anything is missing or different,
   and tell me what you changed.
2. Run python3 apply_schema.py --dry-run. Show me the workspace name, the token's
   scopes, and a short summary of what it will create, grouped by object and list.
3. Wait for me to say go.
4. Run python3 apply_schema.py. Then run it a second time and confirm it reports
   nothing left to create.
5. List what I still have to do by hand in the Attio UI, in order.

Never print the token or the contents of .env.
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
