"""Run the whole pipeline: generate -> load raw -> dbt build -> export.

    python -m pipeline.run

Database connection settings come from the PG* environment variables. Any
step that fails stops the run with a non-zero exit code, so a failing dbt
test means no new export is written.
"""
import argparse
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

from pipeline import export, load_raw

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = REPO_ROOT / "build" / "tickets_raw.csv"
TRANSFORM_DIR = REPO_ROOT / "transform"
# --no-partial-parse: always parse from scratch (about a second) so a run can
# never reuse a cached parse from an earlier, broken run
DEFAULT_DBT = (f"dbt build --no-partial-parse --project-dir {shlex.quote(str(TRANSFORM_DIR))} "
               f"--profiles-dir {shlex.quote(str(TRANSFORM_DIR))}")

# dbt only links ref() dependencies for models it parsed after its run started.
# If the system clock steps backwards during parsing (common in Docker Desktop's
# VM after the host sleeps), every model loses its dependencies and the build
# fails with this message, even though the project is fine.
CLOCK_SKEW_SIGNATURE = "unable to infer all dependencies"
CLOCK_SKEW_HINT = """
dbt could not link any model dependencies. This happens when the system clock
jumps backwards while dbt parses the project, which is common in Docker
Desktop after the computer sleeps. Retrying once. If it fails again, resync the
clock (on Windows: `wsl --shutdown`, then restart Docker Desktop) and rerun.
"""


def step(name, fn):
    print(f"\n==> {name}", flush=True)
    started = time.monotonic()
    fn()
    print(f"    done in {time.monotonic() - started:.1f}s", flush=True)


def run_command(command, capture=False):
    """Run a command, streaming its output; returns (exit code, output if captured)."""
    proc = subprocess.Popen(shlex.split(command), cwd=REPO_ROOT, env=os.environ.copy(),
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.STDOUT if capture else None, text=True)
    lines = []
    if capture:
        with proc.stdout:
            for line in proc.stdout:
                print(line, end="", flush=True)
                lines.append(line)
    return proc.wait(), "".join(lines)


def check(command):
    code, _ = run_command(command)
    if code != 0:
        raise SystemExit(f"command failed ({code}): {command}")


def run_dbt(command, retries=1):
    """Run dbt; retry once if the failure is the clock-skew signature, never otherwise."""
    for attempt in range(retries + 1):
        code, output = run_command(command, capture=True)
        if code == 0:
            return
        if CLOCK_SKEW_SIGNATURE not in output or attempt == retries:
            raise SystemExit(f"command failed ({code}): {command}")
        print(CLOCK_SKEW_HINT, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tickets", type=int, default=5000)
    parser.add_argument("--dbt-command", default=os.environ.get("DBT_COMMAND", DEFAULT_DBT),
                        help="command that builds and tests the dbt project")
    parser.add_argument("--skip-export", action="store_true",
                        help="build and test without rewriting data/customer_support_tickets.csv")
    args = parser.parse_args(argv)

    step("Generate raw tickets", lambda: check(
        f"{shlex.quote(sys.executable)} data/data_generator.py --output {shlex.quote(str(RAW_CSV))} "
        f"--seed {args.seed} --tickets {args.tickets}"))
    step("Load raw.tickets", lambda: load_raw.load(RAW_CSV))
    step("dbt build (models + data tests)", lambda: run_dbt(args.dbt_command))
    if not args.skip_export:
        step("Export for Tableau and Power BI", export.export)
    print("\nPipeline finished.")


if __name__ == "__main__":
    main()
