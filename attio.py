"""Minimal Attio REST client shared by every script in this repo. Standard library only.

The token comes from the ATTIO_API_KEY environment variable, or from a local .env
file. It is sent in the Authorization header and never printed.
"""
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = "https://api.attio.com/v2"
HERE = pathlib.Path(__file__).resolve().parent


def load_dotenv():
    env = HERE / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class AttioError(RuntimeError):
    def __init__(self, status, method, path, body):
        self.status = status
        self.body = body
        super().__init__(f"{status} {method} {path}\n{body}")


class Attio:
    def __init__(self, dry_run=False):
        load_dotenv()
        self.dry_run = dry_run
        self.token = os.environ.get("ATTIO_API_KEY", "").strip()
        if not self.token and not dry_run:
            sys.exit("ATTIO_API_KEY is not set. Put it in .env or in the GitHub secret, never in code.")
        self.writes = 0

    def call(self, method, path, body=None, query=None, retries=6):
        if query:
            path = path + "?" + urllib.parse.urlencode(query)
        is_read = method == "GET" or path.split("?")[0].endswith("/query")
        if self.dry_run and not (is_read and self.token):
            # Dry run: reads still go to Attio when a token is set, so the plan reflects the
            # real workspace. Writes are only printed.
            if is_read:
                return {"data": []}
            print(f"[dry-run] {method} {path}")
            if body is not None:
                print("          " + json.dumps(body, ensure_ascii=False)[:600])
            fake = {"id": {"record_id": str(uuid.uuid4()), "entry_id": str(uuid.uuid4()),
                           "object_id": str(uuid.uuid4()), "list_id": str(uuid.uuid4())}}
            return {"data": [] if path.endswith("/query") else fake}
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(retries):
            req = urllib.request.Request(
                BASE + path, data=data, method=method,
                headers={"Authorization": "Bearer " + self.token,
                         "Content-Type": "application/json",
                         "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    raw = r.read().decode()
                    if not is_read:
                        self.writes += 1
                        time.sleep(0.05)  # stays under the 25 writes/second limit
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                text = e.read().decode()
                if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                    wait = float(e.headers.get("Retry-After") or 0) or 2 ** attempt
                    time.sleep(min(wait, 30))
                    continue
                raise AttioError(e.code, method, path, text) from None
            except urllib.error.URLError:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
        raise RuntimeError("retries exhausted")

    # Convenience wrappers
    def get(self, path, **q):
        return self.call("GET", path, query=q or None)

    def post(self, path, body):
        return self.call("POST", path, body)

    def patch(self, path, body):
        return self.call("PATCH", path, body)

    def put(self, path, body):
        return self.call("PUT", path, body)

    def identify(self):
        """GET /v2/self. Returns the token's workspace and scopes."""
        if self.dry_run and not self.token:
            return {"active": True, "workspace_name": "(dry run, no token)", "scope": "(dry run)"}
        r = self.get("/self")
        return r.get("data", r)

    def query_all(self, path, body=None, limit=500):
        """Page through POST .../records/query or .../entries/query."""
        out, offset = [], 0
        while True:
            payload = dict(body or {}, limit=limit, offset=offset)
            r = self.post(path, payload)
            rows = r.get("data", [])
            out += rows
            if len(rows) < limit:
                return out
            offset += limit


REQUIRED_SCOPES = {
    "schema": ["object_configuration:read-write", "list_configuration:read-write"],
    "seed": ["record_permission:read-write", "list_entry:read-write",
             "object_configuration:read", "list_configuration:read", "user_management:read"],
    "stats": ["record_permission:read", "list_entry:read", "object_configuration:read",
              "list_configuration:read"],
}

LEVEL = {"read": 1, "read-write": 2}


def check_scopes(me, job):
    """Print the workspace and scopes, then stop if a scope the job needs is missing."""
    print(f"Workspace: {me.get('workspace_name')} ({me.get('workspace_slug', '')})")
    granted_raw = me.get("scope") or ""
    print(f"Token scopes: {granted_raw}")
    if granted_raw == "(dry run)":
        return
    granted = {}
    for s in granted_raw.split():
        name, _, level = s.partition(":")
        granted[name] = max(granted.get(name, 0), LEVEL.get(level, 0))
    missing = []
    for need in REQUIRED_SCOPES[job]:
        name, _, level = need.partition(":")
        if granted.get(name, 0) < LEVEL[level]:
            missing.append(need)
    if missing:
        sys.exit("Token is missing scopes: " + ", ".join(missing) +
                 "\nEdit the token in Attio → Workspace settings → Developers and tick them.")
