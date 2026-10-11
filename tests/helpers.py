"""Shared test helpers.

Run the whole suite from the repository root:

    python -m unittest discover -s tests -t . -v

Tests that need a database are skipped unless the PG* environment variables
point at a Postgres where the pipeline has run. Tests that need Metabase are
skipped unless MB_URL is set.
"""
import functools
import os
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@functools.lru_cache(maxsize=1)
def postgres_available():
    if not os.environ.get("PGHOST") or not shutil.which("psql"):
        return False
    probe = subprocess.run(
        ["psql", "-X", "-At", "-c", "select to_regclass('analytics.fct_tickets') is not null"],
        capture_output=True, text=True)
    return probe.returncode == 0 and probe.stdout.strip() == "t"


def requires_postgres(cls):
    return unittest.skipUnless(
        postgres_available(),
        "set PGHOST/PGUSER/PGDATABASE for a Postgres where the pipeline has run")(cls)


def requires_metabase(cls):
    return unittest.skipUnless(os.environ.get("MB_URL"), "set MB_URL to run against a live Metabase")(cls)
