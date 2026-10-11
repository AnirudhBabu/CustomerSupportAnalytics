"""Unit tests for pipeline/run.py's handling of dbt failures."""
import shlex
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from pipeline import run


def fake_dbt(script_dir, outputs):
    """A stand-in dbt that prints outputs[n] and exits with its code on the n-th call."""
    state = Path(script_dir) / "calls"
    script = Path(script_dir) / "fake_dbt.py"
    script.write_text(
        "import pathlib, sys\n"
        f"state = pathlib.Path({str(state)!r})\n"
        "n = int(state.read_text()) if state.exists() else 0\n"
        "state.write_text(str(n + 1))\n"
        f"outputs = {outputs!r}\n"
        "text, code = outputs[min(n, len(outputs) - 1)]\n"
        "print(text)\n"
        "sys.exit(code)\n")
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}", state


class RunDbtTests(unittest.TestCase):
    def calls(self, state):
        return int(state.read_text())

    def test_success_runs_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd, state = fake_dbt(tmp, [("Done. PASS=45", 0)])
            with redirect_stdout(StringIO()):
                run.run_dbt(cmd)
            self.assertEqual(self.calls(state), 1)

    def test_clock_skew_failure_is_retried_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd, state = fake_dbt(tmp, [(f"dbt was {run.CLOCK_SKEW_SIGNATURE} for the model", 1),
                                        ("Done. PASS=45", 0)])
            out = StringIO()
            with redirect_stdout(out):
                run.run_dbt(cmd)
            self.assertEqual(self.calls(state), 2)
            self.assertIn("wsl --shutdown", out.getvalue())

    def test_persistent_clock_skew_still_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd, state = fake_dbt(tmp, [(f"{run.CLOCK_SKEW_SIGNATURE}", 1)])
            with redirect_stdout(StringIO()), self.assertRaises(SystemExit):
                run.run_dbt(cmd)
            self.assertEqual(self.calls(state), 2)

    def test_real_test_failures_are_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd, state = fake_dbt(tmp, [("Failure in test assert_csat_in_range", 1)])
            with redirect_stdout(StringIO()), self.assertRaises(SystemExit):
                run.run_dbt(cmd)
            self.assertEqual(self.calls(state), 1)

    def test_default_command_never_reuses_a_cached_parse(self):
        self.assertIn("--no-partial-parse", run.DEFAULT_DBT)


if __name__ == "__main__":
    unittest.main()
