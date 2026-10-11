"""Unit tests for metabase/provision.py, run against a contract-checked fake Metabase."""
import importlib.util
import re
import unittest

from tests.fake_metabase import FakeMetabase, validate_request, ContractViolation
from tests.helpers import REPO_ROOT

_spec = importlib.util.spec_from_file_location("provision", REPO_ROOT / "metabase" / "provision.py")
provision = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(provision)

WAREHOUSE = {"host": "postgres", "port": 5432, "dbname": "support", "user": "metabase_reader",
             "password": "reader-pw", "ssl": False}
PASSWORD = "Secret-Pass-123"


def run(fake, password=PASSWORD):
    mb = provision.MetabaseClient(fake.url, timeout=5)
    mb.wait_until_healthy(timeout_seconds=5, interval=0.01)
    return provision.provision(mb, provision.load_spec(), "admin@example.com", password, WAREHOUSE)


class DashboardSpecTests(unittest.TestCase):
    def setUp(self):
        self.spec = provision.load_spec()

    def test_every_question_has_sql_and_every_sql_is_used(self):
        keys = {q["key"] for q in self.spec["questions"]}
        files = {p.stem for p in (REPO_ROOT / "metabase" / "questions").glob("*.sql")}
        self.assertEqual(keys, files)

    def test_questions_only_read_the_analytics_schema(self):
        for q in self.spec["questions"]:
            sql = (REPO_ROOT / "metabase" / "questions" / f"{q['key']}.sql").read_text().lower()
            schemas = set(re.findall(r"\b(?:from|join)\s+(\w+)\.", sql))
            self.assertEqual(schemas, {"analytics"}, q["key"])

    def test_layout_fits_grid_without_overlaps(self):
        occupied = {}
        for q in self.spec["questions"]:
            lay = q["layout"]
            self.assertLessEqual(lay["col"] + lay["size_x"], 24, q["key"])
            for r in range(lay["row"], lay["row"] + lay["size_y"]):
                for c in range(lay["col"], lay["col"] + lay["size_x"]):
                    self.assertNotIn((r, c), occupied, f"{q['key']} overlaps {occupied.get((r, c))}")
                    occupied[(r, c)] = q["key"]

    def test_line_chart_settings_name_real_columns(self):
        for q in self.spec["questions"]:
            vs = q.get("visualization_settings", {})
            if not vs:
                continue
            sql = (REPO_ROOT / "metabase" / "questions" / f"{q['key']}.sql").read_text()
            for col in vs.get("graph.dimensions", []) + vs.get("graph.metrics", []):
                self.assertRegex(sql, rf"\b{col}\b", f"{q['key']} chart uses {col}")


class ProvisionTests(unittest.TestCase):
    def test_fresh_instance_is_fully_provisioned(self):
        with FakeMetabase(healthy_after=2) as fake:
            result = run(fake)
            self.assertEqual(fake.violations, [])
            self.assertEqual(fake.admin, ("admin@example.com", PASSWORD))
            self.assertEqual(len(fake.databases), 1)
            db = fake.databases[result["database_id"]]
            self.assertEqual(db["engine"], "postgres")
            self.assertEqual(db["details"]["user"], "metabase_reader")
            spec = provision.load_spec()
            self.assertEqual(len(fake.cards), len(spec["questions"]))
            for card in fake.cards.values():
                self.assertEqual(card["collection_id"], result["collection_id"])
                self.assertEqual(card["dataset_query"]["database"], result["database_id"])
                self.assertEqual(card["dataset_query"]["type"], "native")
            dash = fake.dashboards[result["dashboard_id"]]
            self.assertEqual({dc["card_id"] for dc in dash["dashcards"]}, set(result["card_ids"].values()))
            self.assertIn(("POST", f"/api/database/{result['database_id']}/sync_schema", None), fake.calls)

    def test_second_run_updates_in_place(self):
        with FakeMetabase() as fake:
            first = run(fake)
            card_ids = set(fake.cards)
            run_two = run(fake)
            self.assertEqual(fake.violations, [])
            self.assertEqual(first, run_two)
            self.assertEqual(set(fake.cards), card_ids, "no duplicate questions")
            self.assertEqual(len(fake.databases), 1)
            self.assertEqual(len([c for c in fake.collections.values() if c["personal_owner_id"] is None]), 1)
            self.assertEqual(len(fake.dashboards), 1)
            self.assertEqual(len(fake.dashboards[first["dashboard_id"]]["dashcards"]), len(card_ids))
            setup_calls = [c for c in fake.calls if c[:2] == ("POST", "/api/setup")]
            self.assertEqual(len(setup_calls), 1, "setup API only used on the first run")

    def test_sql_changes_are_pushed_on_rerun(self):
        with FakeMetabase() as fake:
            result = run(fake)
            card_id = result["card_ids"]["kpi_tickets"]
            fake.cards[card_id]["dataset_query"]["native"]["query"] = "select 1"
            run(fake)
            self.assertIn("analytics.kpi_summary", fake.cards[card_id]["dataset_query"]["native"]["query"])

    def test_existing_admin_logs_in_without_setup(self):
        with FakeMetabase(has_admin=True) as fake:
            run(fake)
            self.assertFalse(any(c[1] == "/api/setup" for c in fake.calls))
            self.assertEqual(fake.violations, [])

    def test_wrong_password_fails_clearly(self):
        with FakeMetabase(has_admin=True) as fake:
            with self.assertRaises(provision.MetabaseError) as ctx:
                run(fake, password="wrong-password-1")
            self.assertIn("/api/session", str(ctx.exception))
            self.assertEqual(fake.cards, {})

    def test_unhealthy_metabase_times_out(self):
        with FakeMetabase(healthy_after=10**6) as fake:
            mb = provision.MetabaseClient(fake.url, timeout=5)
            with self.assertRaises(provision.MetabaseError):
                mb.wait_until_healthy(timeout_seconds=0.2, interval=0.01)

    def test_archived_collection_is_not_reused(self):
        with FakeMetabase() as fake:
            first = run(fake)
            fake.collections[first["collection_id"]]["archived"] = True
            second = run(fake)
            third = run(fake)
            self.assertNotEqual(first["collection_id"], second["collection_id"])
            self.assertEqual(second["collection_id"], third["collection_id"])


class ContractCheckTests(unittest.TestCase):
    """The fake must reject what the real Metabase rejects, or the tests above prove nothing."""

    def test_rejects_unknown_keys_on_closed_endpoints(self):
        with self.assertRaises(ContractViolation):
            validate_request("post", "/api/collection", {"name": "x", "color": "#509EE3"})
        with self.assertRaises(ContractViolation):
            validate_request("post", "/api/setup", {"token": "t", "user": {"email": "a@b.c", "password": "p",
                                                                           "site_name": "x"}, "prefs": {"site_name": "x"}})

    def test_rejects_missing_required_fields_and_wrong_types(self):
        with self.assertRaises(ContractViolation):
            validate_request("post", "/api/card", {"name": "x", "display": "table"})
        with self.assertRaises(ContractViolation):
            validate_request("put", "/api/dashboard/{id}", {"dashcards": [{"id": -1, "card_id": 5, "row": 0,
                                                                            "col": 0, "size_x": 0, "size_y": 2}]})

    def test_rejects_endpoints_outside_the_contract(self):
        with self.assertRaises(ContractViolation):
            validate_request("post", "/api/not-a-real-endpoint", {})


if __name__ == "__main__":
    unittest.main()
