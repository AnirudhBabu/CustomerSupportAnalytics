"""An in-process fake of the Metabase API, used to unit-test metabase/provision.py.

Every request body is validated against the OpenAPI spec published with the
pinned Metabase version (tests/contracts/), plus the "closed" key lists from
Metabase's own source for the endpoints where the spec doesn't say which keys
are rejected. A payload that the real server would refuse fails here too.
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from jsonschema import Draft202012Validator

CONTRACT = json.loads((Path(__file__).parent / "contracts" / "metabase-v0.64.1.5-openapi-subset.json").read_text())

# Keys accepted by endpoints whose request schemas are closed maps in Metabase
# v0.64.1.5 (setup_rest/api.clj, collections_rest/api.clj, warehouses_rest/api.clj,
# dashboards_rest/api.clj). Sending any other key returns a 400.
CLOSED_KEYS = {
    ("post", "/api/setup"): {"token", "user", "prefs"},
    ("post", "/api/collection"): {"name", "description", "parent_id", "namespace", "authority_level"},
    ("post", "/api/database"): {"name", "engine", "details", "is_full_sync", "is_on_demand", "schedules",
                                "auto_run_queries", "cache_ttl", "connection_source", "provider_name", "is_stub"},
    ("put", "/api/dashboard/{id}"): {"name", "description", "caveats", "points_of_interest", "show_in_getting_started",
                                     "enable_embedding", "embedding_type", "embedding_params", "parameters", "position",
                                     "width", "archived", "auto_apply_filters", "collection_id", "collection_position",
                                     "cache_ttl", "dashcards", "tabs"},
}
NESTED_CLOSED_KEYS = {
    ("post", "/api/setup", "user"): {"email", "password", "first_name", "last_name"},
    ("post", "/api/setup", "prefs"): {"site_name", "site_locale"},
}
DASHCARD_KEYS = {"id", "size_x", "size_y", "row", "col", "card_id", "action_id", "dashboard_tab_id",
                 "parameter_mappings", "visualization_settings", "inline_parameters", "series"}
PUBLIC = {("get", "/api/health"), ("get", "/api/session/properties"), ("post", "/api/setup"), ("post", "/api/session")}


def _match_path(path):
    for template in list(CONTRACT["paths"]) + ["/api/health"]:
        pattern = "^" + re.sub(r"\{[^}]+\}", r"([^/]+)", template) + "$"
        m = re.match(pattern, path)
        if m:
            return template, m.groups()
    return None, ()


class ContractViolation(Exception):
    pass


def validate_request(method, template, body):
    op = CONTRACT["paths"].get(template, {}).get(method)
    if op is None and template != "/api/health":
        raise ContractViolation(f"{method.upper()} {template} is not in the Metabase contract")
    schema = (op or {}).get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
    if schema is None:
        return
    wrapped = {"$schema": "https://json-schema.org/draft/2020-12/schema", "components": CONTRACT["components"], **schema}
    errors = sorted(Draft202012Validator(wrapped).iter_errors(body or {}), key=lambda e: list(e.path))
    if errors:
        raise ContractViolation(f"{method.upper()} {template}: {errors[0].message} at {list(errors[0].path)}")
    allowed = CLOSED_KEYS.get((method, template))
    if allowed is not None and set(body) - allowed:
        raise ContractViolation(f"{method.upper()} {template}: unexpected keys {sorted(set(body) - allowed)}")
    for (m, t, key), keys in NESTED_CLOSED_KEYS.items():
        if (m, t) == (method, template) and set(body.get(key, {})) - keys:
            raise ContractViolation(f"{method.upper()} {template}.{key}: unexpected keys {sorted(set(body[key]) - keys)}")
    if (method, template) == ("put", "/api/dashboard/{id}"):
        for dc in body.get("dashcards") or []:
            if set(dc) - DASHCARD_KEYS:
                raise ContractViolation(f"dashcard has unexpected keys {sorted(set(dc) - DASHCARD_KEYS)}")


class FakeMetabase:
    def __init__(self, admin_email="admin@example.com", admin_password="Secret-Pass-123", has_admin=False,
                 healthy_after=0):
        self.admin = (admin_email, admin_password) if has_admin else None
        self.expected_password = admin_password
        self.setup_token = None if has_admin else "setup-token-123"
        self.session = "session-abc"
        self.healthy_after = healthy_after
        self.health_checks = 0
        self.calls = []
        self.violations = []
        self.next_id = 100
        self.databases, self.collections, self.cards, self.dashboards = {}, {}, {}, {}
        self.collections[1] = {"id": 1, "name": "Admin's Personal Collection", "personal_owner_id": 1, "archived": False}

    # -- server lifecycle
    def __enter__(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _handle(self, method):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                body = json.loads(raw) if raw else None
                status, payload = fake.dispatch(method, self.path, body, self.headers)
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._handle("get")

            def do_POST(self):
                self._handle("post")

            def do_PUT(self):
                self._handle("put")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def _id(self):
        self.next_id += 1
        return self.next_id

    # -- request handling
    def dispatch(self, method, raw_path, body, headers):
        url = urlparse(raw_path)
        query = parse_qs(url.query)
        template, params = _match_path(url.path)
        self.calls.append((method.upper(), url.path, body))
        if template is None:
            return 404, {"message": f"no route {url.path}"}
        try:
            validate_request(method, template, body)
        except ContractViolation as e:
            self.violations.append(str(e))
            return 400, {"message": str(e)}
        if (method, template) not in PUBLIC and headers.get("X-Metabase-Session") != self.session:
            return 401, {"message": "Unauthenticated"}
        handler = getattr(self, "_" + method + "_" + re.sub(r"\W+", "_", template).strip("_"), None)
        if handler is None:
            return 404, {"message": f"fake has no handler for {method.upper()} {template}"}
        return handler(body or {}, query, *params)

    def _get_api_health(self, body, query):
        self.health_checks += 1
        if self.health_checks <= self.healthy_after:
            return 503, {"status": "initializing"}
        return 200, {"status": "ok"}

    def _get_api_session_properties(self, body, query):
        return 200, {"setup-token": self.setup_token, "has-user-setup": self.admin is not None}

    def _post_api_setup(self, body, query):
        if self.admin is not None or body["token"] != self.setup_token:
            return 403, {"message": "setup already done"}
        self.admin = (body["user"]["email"], body["user"]["password"])
        self.setup_token = None
        return 200, {"id": self.session}

    def _post_api_session(self, body, query):
        if self.admin != (body["username"], body["password"]):
            return 401, {"errors": {"password": "did not match stored password"}}
        return 200, {"id": self.session}

    def _get_api_database(self, body, query):
        return 200, {"data": list(self.databases.values()), "total": len(self.databases)}

    def _post_api_database(self, body, query):
        db = {"id": self._id(), **body}
        self.databases[db["id"]] = db
        return 200, db

    def _put_api_database_id(self, body, query, db_id):
        self.databases[int(db_id)].update(body)
        return 200, self.databases[int(db_id)]

    def _post_api_database_id_sync_schema(self, body, query, db_id):
        return 200, {"status": "ok"}

    def _get_api_collection(self, body, query):
        return 200, list(self.collections.values())

    def _post_api_collection(self, body, query):
        c = {"id": self._id(), "personal_owner_id": None, "archived": False, **body}
        self.collections[c["id"]] = c
        return 200, c

    def _get_api_collection_id_items(self, body, query, coll_id):
        models = query.get("models", [])
        items = [{"id": d["id"], "name": d["name"], "model": "dashboard"}
                 for d in self.dashboards.values() if d["collection_id"] == int(coll_id)]
        return 200, {"data": [i for i in items if not models or i["model"] in models]}

    def _get_api_card(self, body, query):
        return 200, list(self.cards.values())

    def _post_api_card(self, body, query):
        card = {"id": self._id(), "archived": False, **body}
        self.cards[card["id"]] = card
        return 200, card

    def _put_api_card_id(self, body, query, card_id):
        self.cards[int(card_id)].update(body)
        return 200, self.cards[int(card_id)]

    def _post_api_dashboard(self, body, query):
        d = {"id": self._id(), "dashcards": [], **body}
        self.dashboards[d["id"]] = d
        return 200, d

    def _put_api_dashboard_id(self, body, query, dash_id):
        dash = self.dashboards[int(dash_id)]
        if "dashcards" in body:
            dash["dashcards"] = [{**dc, "id": self._id() if dc["id"] < 0 else dc["id"]} for dc in body["dashcards"]]
        return 200, dash
