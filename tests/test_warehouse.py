"""Integration tests against the Postgres warehouse built by the pipeline.

Every number the dashboards show is checked against the independent pandas
reference in tests/reference.py, at three levels:
  1. the dbt KPI tables,
  2. the SQL behind each Metabase question, run as the read-only Metabase role,
  3. the exported CSV that Tableau and Power BI read.
"""
import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pipeline import db, export
from tests import reference as ref
from tests.helpers import REPO_ROOT, requires_postgres

QUESTIONS = REPO_ROOT / "metabase" / "questions"
READER = os.environ.get("ANALYTICS_READER_ROLE", "metabase_reader")


def question_sql(key):
    return (QUESTIONS / f"{key}.sql").read_text()


def as_reader(sql):
    """Run a query with the privileges of the role Metabase connects as."""
    return db.query(f"set role {READER};\n{sql}")


class ParityMixin:
    def assertClose(self, actual, expected, label, abs_tol=1e-9):
        self.assertTrue(ref.is_close(actual, expected, abs_tol=abs_tol),
                        f"{label}: warehouse={actual!r} reference={expected!r}")

    def assertRounded(self, actual, expected, decimals, label):
        """A value rounded to `decimals` places must be within half a unit of the reference."""
        if expected is None:
            self.assertIsNone(actual, label)
            return
        self.assertClose(actual, expected, label, abs_tol=0.5 * 10 ** -decimals + 1e-9)


@requires_postgres
class KpiModelParityTests(ParityMixin, unittest.TestCase):
    def test_kpi_summary(self):
        row, = db.query("select * from analytics.kpi_summary")
        for metric, expected in ref.summary().items():
            self.assertClose(row[metric], expected, f"kpi_summary.{metric}")

    def test_kpi_agent(self):
        rows = {r["agent"]: r for r in db.query("select * from analytics.kpi_agent")}
        expected = ref.by_agent()
        self.assertEqual(set(rows), set(expected))
        for agent, exp in expected.items():
            self.assertEqual(rows[agent]["team"], exp["team"])
            for k, v in exp.items():
                if k != "team":
                    self.assertClose(rows[agent][k], v, f"kpi_agent[{agent}].{k}")

    def test_kpi_daily_volume(self):
        rows = {r["ticket_date"]: r for r in db.query("select * from analytics.kpi_daily_volume")}
        expected = ref.daily_volume()
        self.assertEqual(set(rows), set(expected))
        for day, exp in expected.items():
            self.assertEqual(int(rows[day]["daily_tickets"]), exp["daily_tickets"], day)
            self.assertClose(rows[day]["rolling_7day_avg"], exp["rolling_7day_avg"], f"rolling avg {day}")

    def test_kpi_monthly(self):
        rows = {r["month"]: r for r in db.query("select * from analytics.kpi_monthly")}
        expected = ref.monthly()
        self.assertEqual(set(rows), set(expected))
        for month, exp in expected.items():
            for k, v in exp.items():
                self.assertClose(rows[month][k], v, f"kpi_monthly[{month}].{k}")

    def test_kpi_category_channel(self):
        rows = {(r["category"], r["channel"]): r for r in db.query("select * from analytics.kpi_category_channel")}
        expected = ref.category_channel()
        self.assertEqual(set(rows), set(expected))
        for key, exp in expected.items():
            self.assertEqual(rows[key]["channel_fit"], exp["channel_fit"], key)
            for k in ("volume", "avg_resolution_hours", "resolution_sla_pct"):
                self.assertClose(rows[key][k], exp[k], f"kpi_category_channel{key}.{k}")

    def test_kpi_escalation(self):
        rows = {(r["category"], r["priority"]): r for r in db.query("select * from analytics.kpi_escalation")}
        expected = ref.escalation()
        self.assertEqual(set(rows), set(expected))
        for key, exp in expected.items():
            for k, v in exp.items():
                self.assertClose(rows[key][k], v, f"kpi_escalation{key}.{k}")

    def test_kpi_peak_hours(self):
        rows = {(r["day_of_week"], int(r["hour_of_day"])): int(r["tickets"])
                for r in db.query("select * from analytics.kpi_peak_hours")}
        self.assertEqual(rows, ref.peak_hours())

    def test_fact_table_types(self):
        """The bug that started this: SLA flags and numbers must be real types, not text."""
        types = {r["column_name"]: r["data_type"] for r in db.query(
            "select column_name, data_type from information_schema.columns "
            "where table_schema = 'analytics' and table_name = 'fct_tickets'")}
        self.assertEqual(types["response_sla_met"], "boolean")
        self.assertEqual(types["resolution_sla_met"], "boolean")
        self.assertEqual(types["csat_score"], "integer")
        self.assertEqual(types["first_response_minutes"], "double precision")
        self.assertEqual(types["created_at"], "timestamp without time zone")


@requires_postgres
class MetabaseQuestionSqlTests(ParityMixin, unittest.TestCase):
    """Runs each question's SQL exactly as Metabase would, as the read-only role."""

    def test_every_question_runs_as_reader(self):
        for path in sorted(QUESTIONS.glob("*.sql")):
            with self.subTest(question=path.stem):
                self.assertGreater(len(as_reader(path.read_text())), 0)

    def test_headline_questions(self):
        s = ref.summary()
        self.assertEqual(int(as_reader(question_sql("kpi_tickets"))[0]["Tickets"]), s["tickets"])
        self.assertRounded(as_reader(question_sql("kpi_response_sla"))[0]["Response SLA %"], s["response_sla_pct"], 1, "response SLA")
        self.assertRounded(as_reader(question_sql("kpi_resolution_sla"))[0]["Resolution SLA %"], s["resolution_sla_pct"], 1, "resolution SLA")
        self.assertRounded(as_reader(question_sql("kpi_csat"))[0]["CSAT"], s["avg_csat"], 2, "CSAT")

    def test_agent_productivity(self):
        rows = as_reader(question_sql("agent_productivity"))
        expected = ref.by_agent()
        self.assertEqual(len(rows), len(expected))
        for r in rows:
            exp = expected[r["agent"]]
            self.assertEqual(int(r["total_tickets"]), exp["total_tickets"])
            self.assertRounded(r["frt_sla_compliance"], exp["response_sla_pct"], 1, f"{r['agent']} FRT SLA")
            self.assertRounded(r["avg_csat"], exp["avg_csat"], 2, f"{r['agent']} CSAT")
            self.assertRounded(r["resolution_rate"], exp["resolution_rate_pct"], 1, f"{r['agent']} resolution rate")
        # the original bug: FRT SLA compliance was 0 for every agent
        self.assertTrue(all(float(r["frt_sla_compliance"]) > 0 for r in rows))
        rates = [float(r["resolution_rate"]) for r in rows]
        self.assertEqual(rates, sorted(rates, reverse=True))

    def test_monthly_trends(self):
        rows = as_reader(question_sql("monthly_trends"))
        expected = ref.monthly()
        self.assertEqual([r["month"] for r in rows], sorted(expected))
        for r in rows:
            exp = expected[r["month"]]
            self.assertRounded(r["csat_score"], exp["avg_csat"], 2, f"{r['month']} CSAT")
            self.assertRounded(r["frt_sla_pct"], exp["response_sla_pct"], 1, f"{r['month']} FRT SLA")
            self.assertRounded(r["volume_change_pct"], exp["volume_change_pct"], 1, f"{r['month']} change")

    def test_daily_volume_trend(self):
        rows = as_reader(question_sql("daily_volume_trend"))
        expected = ref.daily_volume()
        self.assertEqual(len(rows), len(expected))
        for r in rows:
            self.assertRounded(r["rolling_7day_avg"], expected[r["ticket_date"]]["rolling_7day_avg"], 2, r["ticket_date"])

    def test_category_channel_and_escalation(self):
        cc = ref.category_channel()
        for r in as_reader(question_sql("category_channel_performance")):
            exp = cc[(r["category"], r["channel"])]
            self.assertEqual(r["channel_fit"], exp["channel_fit"])
            self.assertRounded(r["sla_compliance_pct"], exp["resolution_sla_pct"], 1, "sla")
        esc = ref.escalation()
        rows = as_reader(question_sql("escalation_analysis"))
        self.assertEqual(len(rows), len(esc))
        for r in rows:
            self.assertRounded(r["escalation_rate"], esc[(r["category"], r["priority"])]["escalation_rate_pct"], 2, "rate")

    def test_peak_hours(self):
        rows = {(r["day_of_week"], int(r["hour_of_day"])): int(r["tickets"])
                for r in as_reader(question_sql("peak_hours"))}
        self.assertEqual(rows, ref.peak_hours())


@requires_postgres
class ReaderPrivilegeTests(unittest.TestCase):
    """Metabase connects as a read-only role that only sees the analytics schema."""

    def assertDenied(self, sql):
        with self.assertRaises(db.DatabaseError) as ctx:
            as_reader(sql)
        self.assertIn("permission denied", str(ctx.exception))

    def test_can_read_analytics(self):
        self.assertEqual(len(as_reader("select ticket_id from analytics.fct_tickets limit 1")), 1)

    def test_cannot_read_raw_or_staging(self):
        self.assertDenied("select * from raw.tickets limit 1")
        self.assertDenied("select * from staging.stg_tickets limit 1")

    def test_cannot_write(self):
        self.assertDenied("delete from analytics.fct_tickets")
        self.assertDenied("create table analytics.should_not_exist (x int)")


@requires_postgres
class ExportTests(unittest.TestCase):
    def test_export_reproduces_source_exactly(self):
        """The export is byte-identical to the generator's file: nothing lost or altered in the warehouse."""
        source = REPO_ROOT / "build" / "tickets_raw.csv"
        if not source.exists():
            self.skipTest("run the pipeline first to create build/tickets_raw.csv")
        with tempfile.TemporaryDirectory() as tmp:
            out = export.export(Path(tmp) / "export.csv")
            self.assertEqual(out.read_bytes(), source.read_bytes())

    def test_export_replaces_a_file_it_cannot_overwrite(self):
        """The export swaps in a new file, so a read-only or foreign-owned target is fine."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "customer_support_tickets.csv"
            target.write_text("stale")
            target.chmod(0o444)
            export.export(target)
            self.assertTrue(target.read_text().startswith("ticket_id,"))
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), [target.name], "no temp files left")

    def test_export_matches_what_bi_tools_expect(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pd.read_csv(export.export(Path(tmp) / "export.csv"))
        committed = pd.read_csv(REPO_ROOT / "data" / "customer_support_tickets.csv", nrows=0)
        self.assertEqual(list(out.columns), list(committed.columns))
        self.assertEqual(len(out), ref.summary()["tickets"])
        self.assertEqual(set(out["response_sla_met"].astype(str)), {"True", "False"})


if __name__ == "__main__":
    unittest.main()
