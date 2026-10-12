#!/usr/bin/env python3
"""Create the VC data model from schema.json in an Attio workspace.

Safe to run twice: it reads what exists first and only creates what is missing.

    python3 apply_schema.py --dry-run   # print every request, send nothing
    python3 apply_schema.py             # apply
"""
import argparse
import json
import pathlib
import sys

from attio import Attio, AttioError, check_scopes

HERE = pathlib.Path(__file__).resolve().parent
created, skipped = [], []


def attr_body(a):
    body = {
        "title": a["title"],
        "description": a.get("description") or None,
        "api_slug": a["api_slug"],
        "type": a["type"],
        "is_required": False,
        "is_unique": False,  # Attio refuses is_unique on create; dedupe at import time instead
        "is_multiselect": a.get("is_multiselect", False),
        "config": a.get("config", {}),  # required on every type, even when empty
    }
    if a.get("relationship"):
        body["relationship"] = a["relationship"]  # top level, not inside config
    return {"data": body}


def read(api, path, **q):
    """GET that treats 404 as empty. In a dry run, objects and attributes the plan would
    create do not exist yet, so reading them returns 404."""
    try:
        return api.get(path, **q).get("data", [])
    except AttioError as e:
        if e.status == 404:
            return []
        raise


def existing_attributes(api, target, ident):
    rows, offset = [], 0
    while True:
        page = read(api, f"/{target}/{ident}/attributes", show_archived="true",
                    limit=100, offset=offset)
        rows += page
        if len(page) < 100:
            return {r["api_slug"]: r for r in rows}
        offset += 100


def ensure_options(api, target, ident, slug, options):
    have = {o["title"] for o in read(api, f"/{target}/{ident}/attributes/{slug}/options",
                                     show_archived="true")}
    for title in options:
        if title in have:
            skipped.append(f"{ident}.{slug} option {title}")
            continue
        api.post(f"/{target}/{ident}/attributes/{slug}/options", {"data": {"title": title}})
        created.append(f"{ident}.{slug} option {title}")


def ensure_statuses(api, target, ident, slug, statuses, archive=()):
    rows = read(api, f"/{target}/{ident}/attributes/{slug}/statuses", show_archived="true")
    have = {r["title"]: r for r in rows}
    for s in statuses:
        body = {"title": s["title"], "celebration_enabled": s.get("celebration_enabled", False),
                "target_time_in_status": s.get("target_time_in_status")}
        if s["title"] in have:
            row = have[s["title"]]
            if row.get("is_archived") or row.get("target_time_in_status") != body["target_time_in_status"]:
                sid = row["id"]["status_id"]
                api.patch(f"/{target}/{ident}/attributes/{slug}/statuses/{sid}",
                          {"data": {"target_time_in_status": body["target_time_in_status"],
                                    "is_archived": False}})
                created.append(f"{ident}.{slug} status {s['title']} (updated)")
            else:
                skipped.append(f"{ident}.{slug} status {s['title']}")
            continue
        api.post(f"/{target}/{ident}/attributes/{slug}/statuses", {"data": body})
        created.append(f"{ident}.{slug} status {s['title']}")
    for title in archive:
        row = have.get(title)
        if not row or row.get("is_archived"):
            continue
        sid = row["id"]["status_id"]
        api.patch(f"/{target}/{ident}/attributes/{slug}/statuses/{sid}", {"data": {"is_archived": True}})
        created.append(f"{ident}.{slug} status {title} (archived)")


def ensure_attributes(api, target, ident, attrs):
    have = existing_attributes(api, target, ident)
    for a in attrs:
        slug = a["api_slug"]
        if a.get("existing"):
            if slug not in have and api.token:
                sys.exit(f"{ident}.{slug} should already exist but does not.")
        elif slug in have:
            skipped.append(f"{ident}.{slug}")
        else:
            rel = a.get("relationship")
            if rel and api.token:
                far = existing_attributes(api, "objects", rel["object"])
                if rel["api_slug"] in far:
                    sys.exit(f"{rel['object']}.{rel['api_slug']} already exists, so the two-way link "
                             f"{ident}.{slug} cannot be created. Rename or delete one side first.")
            api.post(f"/{target}/{ident}/attributes", attr_body(a))
            created.append(f"{ident}.{slug} ({a['type']})" + (f" ↔ {rel['object']}.{rel['api_slug']}" if rel else ""))
        if a.get("options"):
            ensure_options(api, target, ident, slug, a["options"])
        if a.get("statuses"):
            ensure_statuses(api, target, ident, slug, a["statuses"], a.get("archive_statuses", ()))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="print requests, send nothing")
    p.add_argument("--schema", default=str(HERE / "schema.json"))
    args = p.parse_args()

    schema = json.loads(pathlib.Path(args.schema).read_text())
    api = Attio(dry_run=args.dry_run)
    check_scopes(api.identify(), "schema")

    objects = {o["api_slug"] for o in api.get("/objects").get("data", [])}
    if "deals" not in objects and api.token:
        sys.exit("The Deals object is switched off. Turn it on in Attio → Workspace settings → "
                 "Objects → Deals, then run this again. The API cannot activate it.")

    # 1. Custom objects first, so relationships below can point at them.
    for o in schema["objects"]:
        if o.get("standard") or o["api_slug"] in objects:
            continue
        try:
            api.post("/objects", {"data": {"api_slug": o["api_slug"], "singular_noun": o["singular_noun"],
                                           "plural_noun": o["plural_noun"]}})
        except AttioError as e:
            if e.status == 403:
                sys.exit("Attio refused to create a custom object. Custom objects need the Pro plan.")
            raise
        objects.add(o["api_slug"])
        created.append(f"object {o['api_slug']}")

    # 2. Attributes, options and statuses, object by object in file order.
    for o in schema["objects"]:
        ensure_attributes(api, "objects", o["api_slug"], o["attributes"])

    # 3. Lists and their own attributes.
    lists = {l["api_slug"] for l in api.get("/lists").get("data", [])}
    for l in schema["lists"]:
        if l["api_slug"] not in lists:
            api.post("/lists", {"data": {"name": l["name"], "api_slug": l["api_slug"],
                                         "parent_object": l["parent_object"],
                                         "workspace_access": "full-access",
                                         "workspace_member_access": []}})
            created.append(f"list {l['api_slug']}")
        ensure_attributes(api, "lists", l["api_slug"], l["attributes"])

    print()
    for line in created:
        print("  + " + line)
    print(f"\nCreated or changed: {len(created)}. Already there: {len(skipped)}.")
    if not api.dry_run:
        print("\nStill to do by hand in the UI (the API cannot): set Name as the record title on Funds and "
              "Investments, percent display on Ownership %, the MOIC formula, views, Rules, workflows, reports.")


if __name__ == "__main__":
    main()
