"""Thin wrapper around the `psql` client.

Connection settings come from the standard libpq environment variables
(PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE), the same ones dbt's
profile reads, so every step of the pipeline talks to the same database.
Using psql keeps the pipeline free of a Python database driver.
"""
import csv
import io
import os
import shutil
import subprocess


class DatabaseError(RuntimeError):
    pass


def _psql_cmd(extra_args):
    psql = shutil.which("psql")
    if not psql:
        raise DatabaseError("psql was not found on PATH; install the PostgreSQL client")
    return [psql, "-X", "-q", "-v", "ON_ERROR_STOP=1", *extra_args]


def _run(args, env=None):
    proc = subprocess.run(_psql_cmd(args), capture_output=True, text=True,
                          env={**os.environ, **(env or {})})
    if proc.returncode != 0:
        raise DatabaseError(proc.stderr.strip() or f"psql exited with {proc.returncode}")
    return proc.stdout


def execute(sql, env=None):
    """Run one or more SQL statements; raises DatabaseError on the first failure."""
    _run(["-c", sql], env)


def query(sql, env=None):
    """Run a query and return the rows as a list of dicts (all values are strings, NULL is None)."""
    out = _run(["--csv", "-P", "null=\\N", "-c", sql], env)
    rows = list(csv.DictReader(io.StringIO(out)))
    return [{k: (None if v == "\\N" else v) for k, v in r.items()} for r in rows]


def scalar(sql, env=None):
    rows = query(sql, env)
    if len(rows) != 1 or len(rows[0]) != 1:
        raise DatabaseError(f"expected one value, got {rows!r}")
    return next(iter(rows[0].values()))


def _quote_path(path):
    return "'" + str(path).replace("'", "''") + "'"


def copy_in(table, csv_path, env=None):
    """Bulk-load a CSV file with a header row into an existing table."""
    _run(["-c", f"\\copy {table} from {_quote_path(csv_path)} with (format csv, header true)"], env)


def copy_out(select_sql, csv_path, env=None):
    """Write the result of a query to a CSV file with a header row."""
    one_line = " ".join(select_sql.split())
    _run(["-c", f"\\copy ({one_line}) to {_quote_path(csv_path)} with (format csv, header true)"], env)
