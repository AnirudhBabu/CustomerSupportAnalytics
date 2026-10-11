"""End-to-end tests against a running Metabase that has been provisioned.

Runs in CI after `docker compose up`, and locally with:

    MB_URL=http://localhost:3000 MB_ADMIN_PASSWORD=... WAREHOUSE_PASSWORD=... \
        python -m unittest tests.test_metabase_e2e -v

Each question is executed through Metabase's API, so this checks the whole
path: Metabase -> read-only connection -> analytics schema -> numbers on screen.
"""
import importlib.util
import os
import unittest

from tests import reference as ref
from tests.helpers import REPO_ROOT, requires_metabase

_spec = importlib.util.spec_from_file_location("provision", REPO_ROOT / "metabase" / "provision.py")
provision = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(provision)


@requires_metabase
class MetabaseEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mb = provision.MetabaseClient(os.environ["MB_URL"])
        cls.mb.wait_until_healthy(timeout_seconds=300)
        cls.mb.login(os.environ.get("MB_ADMIN_EMAIL", "admin@example.com"), os.environ["MB_ADMIN_PASSWORD"])
        cls.spec = provision.load_spec()
        collections = [c for c in cls.mb.get("/api/collection")
                       if c.get("name") == cls.spec["collection"] and not c.get("archived")]
        assert len(collections) == 1, f"expected one '{cls.spec['collection']}' collection, found {len(collections)}"
        cls.collection_id = collections[0]["id"]
        cards = [c for c in cls.mb.get("/api/card", params={"f": "all"})
                 if c.get("collection_id") == cls.collection_id and not c.get("archived")]
        cls.cards = {c["name"]: c for c in cards}

    def run_question(self, key):
        name = next(q["name"] for q in self.spec["questions"] if q["key"] == key)
        result = self.mb.post(f"/api/card/{self.cards[name]['id']}/query", {"ignore_cache": True})
        self.assertEqual(result.get("status"), "completed", result.get("error"))
        cols = [c["name"] for c in result["data"]["cols"]]
        return [dict(zip(cols, row)) for row in result["data"]["rows"]]

    def assertRounded(self, actual, expected, decimals, label):
        self.assertTrue(ref.is_close(actual, expected, abs_tol=0.5 * 10 ** -decimals + 1e-9),
                        f"{label}: metabase={actual!r} reference={expected!r}")

    def test_every_question_exists_once_and_is_on_the_dashboard(self):
        names = [q["name"] for q in self.spec["questions"]]
        self.assertEqual(sorted(self.cards), sorted(names))
        items = self.mb.get(f"/api/collection/{self.collection_id}/items", params={"models": "dashboard"})["data"]
        dashboards = [d for d in items if d["name"] == self.spec["dashboard"]["name"]]
        self.assertEqual(len(dashboards), 1)
        dash = self.mb.get(f"/api/dashboard/{dashboards[0]['id']}")
        self.assertEqual({dc["card_id"] for dc in dash["dashcards"]}, {c["id"] for c in self.cards.values()})

    def test_metabase_queries_as_read_only_role(self):
        db = next(d for d in self.mb.get("/api/database")["data"] if d["name"] == self.spec["database_name"])
        self.assertEqual(db["engine"], "postgres")
        self.assertEqual(db["details"]["user"], os.environ.get("WAREHOUSE_USER", "metabase_reader"))

    def test_every_question_runs(self):
        for q in self.spec["questions"]:
            with self.subTest(question=q["key"]):
                self.assertGreater(len(self.run_question(q["key"])), 0)

    def test_headline_numbers(self):
        s = ref.summary()
        self.assertEqual(self.run_question("kpi_tickets")[0]["Tickets"], s["tickets"])
        self.assertRounded(self.run_question("kpi_response_sla")[0]["Response SLA %"], s["response_sla_pct"], 1, "response SLA")
        self.assertRounded(self.run_question("kpi_resolution_sla")[0]["Resolution SLA %"], s["resolution_sla_pct"], 1, "resolution SLA")
        self.assertRounded(self.run_question("kpi_csat")[0]["CSAT"], s["avg_csat"], 2, "CSAT")

    def test_agent_productivity_matches_reference(self):
        expected = ref.by_agent()
        rows = self.run_question("agent_productivity")
        self.assertEqual(len(rows), len(expected))
        for r in rows:
            exp = expected[r["agent"]]
            self.assertEqual(r["total_tickets"], exp["total_tickets"])
            self.assertRounded(r["frt_sla_compliance"], exp["response_sla_pct"], 1, f"{r['agent']} FRT SLA")
            self.assertRounded(r["avg_csat"], exp["avg_csat"], 2, f"{r['agent']} CSAT")

    def test_daily_and_monthly_trends_match_reference(self):
        daily = ref.daily_volume()
        rows = self.run_question("daily_volume_trend")
        self.assertEqual(len(rows), len(daily))
        for r in rows:
            day = str(r["ticket_date"])[:10]
            self.assertEqual(r["daily_tickets"], daily[day]["daily_tickets"], day)
            self.assertRounded(r["rolling_7day_avg"], daily[day]["rolling_7day_avg"], 2, day)
        monthly = ref.monthly()
        for r in self.run_question("monthly_trends"):
            self.assertRounded(r["csat_score"], monthly[r["month"]]["avg_csat"], 2, r["month"])

    def test_peak_hours_match_reference(self):
        rows = {(r["day_of_week"], r["hour_of_day"]): r["tickets"] for r in self.run_question("peak_hours")}
        self.assertEqual(rows, ref.peak_hours())

    def test_provisioning_is_idempotent_against_real_metabase(self):
        if not os.environ.get("WAREHOUSE_PASSWORD"):
            self.skipTest("set WAREHOUSE_PASSWORD to re-run provisioning")
        warehouse = {
            "host": os.environ.get("WAREHOUSE_HOST", "postgres"), "port": int(os.environ.get("WAREHOUSE_PORT", "5432")),
            "dbname": os.environ.get("WAREHOUSE_DB", "support"), "user": os.environ.get("WAREHOUSE_USER", "metabase_reader"),
            "password": os.environ["WAREHOUSE_PASSWORD"], "ssl": False,
            "schema-filters-type": "inclusion", "schema-filters-patterns": "analytics",
        }
        before = {c["id"] for c in self.cards.values()}
        result = provision.provision(self.mb, self.spec, os.environ.get("MB_ADMIN_EMAIL", "admin@example.com"),
                                     os.environ["MB_ADMIN_PASSWORD"], warehouse)
        self.assertEqual(set(result["card_ids"].values()), before)
        self.assertEqual(result["collection_id"], self.collection_id)


if __name__ == "__main__":
    unittest.main()
