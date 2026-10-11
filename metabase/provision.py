"""Provision Metabase from code: admin user, warehouse connection, questions and dashboard.

Everything Metabase shows is defined in this folder:
  dashboard.json     collection, dashboard, questions and their layout
  questions/*.sql    the SQL behind each question

The script is idempotent. On a fresh instance it runs the setup wizard through
the API; on later runs it logs in and updates the existing objects in place,
so it is safe to run on every deploy.

Configuration (environment variables):
  MB_URL                   default http://localhost:3000
  MB_ADMIN_EMAIL           default admin@example.com
  MB_ADMIN_PASSWORD        required
  MB_SITE_NAME             default "Support Analytics"
  WAREHOUSE_HOST           default localhost
  WAREHOUSE_PORT           default 5432
  WAREHOUSE_DB             default support
  WAREHOUSE_USER           default metabase_reader  (read-only role)
  WAREHOUSE_PASSWORD       required
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "dashboard.json"
QUESTIONS_DIR = HERE / "questions"


class MetabaseError(RuntimeError):
    pass


class MetabaseClient:
    def __init__(self, base_url, timeout=60):
        self.base_url = base_url.rstrip("/")
        self.http = requests.Session()
        self.timeout = timeout

    def request(self, method, path, **kwargs):
        resp = self.http.request(method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
        if resp.status_code >= 400:
            raise MetabaseError(f"{method} {path} -> {resp.status_code}: {resp.text[:500]}")
        return resp.json() if resp.content else None

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, json=body, **kw)

    def put(self, path, body=None, **kw):
        return self.request("PUT", path, json=body, **kw)

    def wait_until_healthy(self, timeout_seconds=600, interval=5):
        deadline = time.monotonic() + timeout_seconds
        last = None
        while time.monotonic() < deadline:
            try:
                resp = self.http.get(f"{self.base_url}/api/health", timeout=10)
                if resp.status_code == 200 and resp.json().get("status") == "ok":
                    return
                last = f"{resp.status_code} {resp.text[:200]}"
            except requests.RequestException as e:
                last = str(e)
            time.sleep(interval)
        raise MetabaseError(f"Metabase not healthy after {timeout_seconds}s (last: {last})")

    def login(self, email, password, site_name="Support Analytics"):
        """Create the first admin via the setup API if needed, then log in."""
        props = self.get("/api/session/properties")
        token = props.get("setup-token")
        if token and not props.get("has-user-setup"):
            self.post("/api/setup", {
                "token": token,
                "user": {"email": email, "password": password,
                         "first_name": "Platform", "last_name": "Admin"},
                "prefs": {"site_name": site_name},
            })
            print("Created the first admin user through the setup API")
        session = self.post("/api/session", {"username": email, "password": password})
        self.http.headers["X-Metabase-Session"] = session["id"]


def _by_name(items, name, **match):
    for item in items:
        if item.get("name") == name and all(item.get(k) == v for k, v in match.items()):
            return item
    return None


def ensure_database(mb, name, details):
    body = {"name": name, "engine": "postgres", "details": details,
            "is_full_sync": True, "is_on_demand": False, "connection_source": "admin"}
    existing = _by_name(mb.get("/api/database")["data"], name)
    if existing:
        mb.put(f"/api/database/{existing['id']}", {"name": name, "engine": "postgres", "details": details})
        db_id = existing["id"]
    else:
        db_id = mb.post("/api/database", body)["id"]
    mb.post(f"/api/database/{db_id}/sync_schema")
    return db_id


def ensure_collection(mb, name):
    active = [c for c in mb.get("/api/collection") if not c.get("archived")]
    existing = _by_name(active, name, personal_owner_id=None)
    if existing:
        return existing["id"]
    return mb.post("/api/collection", {
        "name": name, "description": "Provisioned by metabase/provision.py"})["id"]


def card_payload(question, sql, database_id, collection_id):
    return {
        "name": question["name"],
        "description": f"Source: metabase/questions/{question['key']}.sql",
        "collection_id": collection_id,
        "display": question["display"],
        "visualization_settings": question.get("visualization_settings", {}),
        "dataset_query": {
            "type": "native",
            "database": database_id,
            "native": {"query": sql, "template-tags": {}},
        },
    }


def ensure_cards(mb, questions, database_id, collection_id, questions_dir=QUESTIONS_DIR):
    existing = [c for c in mb.get("/api/card", params={"f": "all"})
                if c.get("collection_id") == collection_id and not c.get("archived")]
    card_ids = {}
    for q in questions:
        sql = (Path(questions_dir) / f"{q['key']}.sql").read_text(encoding="utf-8").strip()
        payload = card_payload(q, sql, database_id, collection_id)
        current = _by_name(existing, q["name"])
        if current:
            mb.put(f"/api/card/{current['id']}", payload)
            card_ids[q["key"]] = current["id"]
        else:
            card_ids[q["key"]] = mb.post("/api/card", payload)["id"]
    return card_ids


def ensure_dashboard(mb, spec, collection_id, card_ids):
    items = mb.get(f"/api/collection/{collection_id}/items", params={"models": "dashboard"})["data"]
    existing = _by_name(items, spec["dashboard"]["name"])
    if existing:
        dash_id = existing["id"]
    else:
        dash_id = mb.post("/api/dashboard", {
            "name": spec["dashboard"]["name"],
            "description": spec["dashboard"]["description"],
            "collection_id": collection_id,
        })["id"]
    # Replacing the full list of dashcards makes the layout match the spec
    # exactly; negative ids tell Metabase these are new dashcards.
    dashcards = [{"id": -(i + 1), "card_id": card_ids[q["key"]], **q["layout"]}
                 for i, q in enumerate(spec["questions"])]
    mb.put(f"/api/dashboard/{dash_id}", {"dashcards": dashcards})
    return dash_id


def load_spec(path=SPEC_PATH):
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    keys = [q["key"] for q in spec["questions"]]
    if len(keys) != len(set(keys)):
        raise ValueError("question keys in dashboard.json must be unique")
    return spec


def _env(name, default=None):
    value = os.environ.get(name, default)
    if value in (None, ""):
        raise SystemExit(f"environment variable {name} is required")
    return value


def provision(mb, spec, admin_email, admin_password, warehouse, site_name="Support Analytics",
              questions_dir=QUESTIONS_DIR):
    mb.login(admin_email, admin_password, site_name)
    database_id = ensure_database(mb, spec["database_name"], warehouse)
    collection_id = ensure_collection(mb, spec["collection"])
    card_ids = ensure_cards(mb, spec["questions"], database_id, collection_id, questions_dir)
    dashboard_id = ensure_dashboard(mb, spec, collection_id, card_ids)
    return {"database_id": database_id, "collection_id": collection_id,
            "dashboard_id": dashboard_id, "card_ids": card_ids}


def main():
    mb = MetabaseClient(os.environ.get("MB_URL", "http://localhost:3000"))
    print(f"Waiting for Metabase at {mb.base_url} ...", flush=True)
    mb.wait_until_healthy()
    warehouse = {
        "host": os.environ.get("WAREHOUSE_HOST", "localhost"),
        "port": int(os.environ.get("WAREHOUSE_PORT", "5432")),
        "dbname": os.environ.get("WAREHOUSE_DB", "support"),
        "user": os.environ.get("WAREHOUSE_USER", "metabase_reader"),
        "password": _env("WAREHOUSE_PASSWORD"),
        "ssl": False,
        "schema-filters-type": "inclusion",
        "schema-filters-patterns": "analytics",
    }
    result = provision(
        mb, load_spec(),
        admin_email=os.environ.get("MB_ADMIN_EMAIL", "admin@example.com"),
        admin_password=_env("MB_ADMIN_PASSWORD"),
        warehouse=warehouse,
        site_name=os.environ.get("MB_SITE_NAME", "Support Analytics"),
    )
    print(json.dumps(result, indent=2))
    print(f"Dashboard: {mb.base_url}/dashboard/{result['dashboard_id']}")


if __name__ == "__main__":
    try:
        main()
    except MetabaseError as e:
        print(f"Provisioning failed: {e}", file=sys.stderr)
        sys.exit(1)
