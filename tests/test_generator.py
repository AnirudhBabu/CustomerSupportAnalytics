"""Unit tests for the data generator: determinism and the rules the data must follow."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tests.helpers import REPO_ROOT
from tests.reference import _load_generator

gen = _load_generator()


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = gen.generate_tickets()

    def test_same_seed_gives_identical_data(self):
        pd.testing.assert_frame_equal(self.df, gen.generate_tickets())

    def test_different_seed_gives_different_data(self):
        other = gen.generate_tickets(seed=7)
        self.assertFalse(self.df["resolution_hours"].equals(other["resolution_hours"]))

    def test_shape_and_unique_ids(self):
        self.assertEqual(len(self.df), 5000)
        self.assertTrue(self.df["ticket_id"].is_unique)
        self.assertEqual(len(gen.generate_tickets(num_tickets=250)), 250)

    def test_categorical_values(self):
        self.assertLessEqual(set(self.df["channel"]), set(gen.CHANNELS))
        self.assertLessEqual(set(self.df["category"]), set(gen.CATEGORIES))
        self.assertLessEqual(set(self.df["priority"]), set(gen.PRIORITIES))
        self.assertLessEqual(set(self.df["status"]), set(gen.STATUSES))
        for region, country in zip(self.df["region"], self.df["country"]):
            self.assertIn(country, gen.REGION_COUNTRIES[region])

    def test_each_agent_belongs_to_one_team(self):
        teams_per_agent = self.df.groupby("agent")["team"].nunique()
        self.assertEqual(teams_per_agent.max(), 1)
        self.assertEqual(self.df["team"].nunique(), 4)

    def test_csat_only_for_resolved_tickets_and_in_range(self):
        resolved = self.df["status"] == "Resolved"
        self.assertTrue(self.df.loc[resolved, "csat_score"].notna().all())
        self.assertTrue(self.df.loc[~resolved, "csat_score"].isna().all())
        self.assertTrue(self.df["csat_score"].dropna().between(1, 5).all())

    def test_csat_falls_as_resolution_time_grows(self):
        rated = self.df.dropna(subset=["csat_score"])
        buckets = pd.cut(rated["resolution_hours"], [0, 4, 24, 72, float("inf")], right=False)
        means = rated.groupby(buckets, observed=True)["csat_score"].mean().tolist()
        self.assertEqual(means, sorted(means, reverse=True), means)
        self.assertGreater(means[0] - means[-1], 1.5)

    def test_sla_flags_follow_thresholds(self):
        self.assertTrue((self.df["response_sla_met"]
                         == (self.df["first_response_minutes"] < gen.RESPONSE_SLA_MINUTES)).all())
        self.assertTrue((self.df["resolution_sla_met"]
                         == (self.df["resolution_hours"] < gen.RESOLUTION_SLA_HOURS)).all())

    def test_resolved_dates_follow_created_dates(self):
        resolved = self.df[self.df["status"] == "Resolved"]
        delta_hours = (pd.to_datetime(resolved["resolved_date"]) - resolved["created_date"]).dt.total_seconds() / 3600
        self.assertTrue(((delta_hours - resolved["resolution_hours"]).abs() < 1e-6).all())
        self.assertTrue(self.df.loc[self.df["status"] != "Resolved", "resolved_date"].isna().all())

    def test_sla_thresholds_match_dbt_vars(self):
        project = (REPO_ROOT / "transform" / "dbt_project.yml").read_text()
        self.assertIn(f"response_sla_minutes: {gen.RESPONSE_SLA_MINUTES}", project)
        self.assertIn(f"resolution_sla_hours: {gen.RESOLUTION_SLA_HOURS}", project)

    def test_cli_writes_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "tickets.csv"
            subprocess.run([sys.executable, str(REPO_ROOT / "data" / "data_generator.py"),
                            "--output", str(out), "--tickets", "100", "--seed", "3"],
                           check=True, capture_output=True)
            written = pd.read_csv(out)
            self.assertEqual(len(written), 100)
            self.assertEqual(list(written.columns), list(self.df.columns))

    def test_committed_export_is_up_to_date(self):
        """data/customer_support_tickets.csv must be what the pipeline produces today."""
        committed = pd.read_csv(REPO_ROOT / "data" / "customer_support_tickets.csv")
        fresh = self.df.copy()
        fresh["created_date"] = fresh["created_date"].dt.strftime("%Y-%m-%d %H:%M:%S")
        fresh["resolved_date"] = pd.to_datetime(fresh["resolved_date"]).dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        committed["resolved_date"] = pd.to_datetime(committed["resolved_date"]).dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        pd.testing.assert_frame_equal(committed, fresh, check_dtype=False, rtol=1e-12, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
