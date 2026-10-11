"""Load the generated ticket CSV into the `raw` landing schema.

Every column lands as text, exactly as it appears in the file. Typing happens
in dbt's staging layer, where it is tested, instead of being guessed at load
time (guessed types are how the original SQLite database ended up storing SLA
flags as the strings 'True'/'False').
"""
import argparse
import csv
import re
from pathlib import Path

from pipeline import db

RAW_SCHEMA = "raw"
RAW_TABLE = "tickets"


def _identifier(name):
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", name):
        raise ValueError(f"unexpected column name in CSV header: {name!r}")
    return name


def load(csv_path):
    csv_path = Path(csv_path).resolve()
    with open(csv_path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    columns = ",\n    ".join(f"{_identifier(c)} text" for c in header)
    db.execute(f"""
        create schema if not exists {RAW_SCHEMA};
        drop table if exists {RAW_SCHEMA}.{RAW_TABLE} cascade;
        create table {RAW_SCHEMA}.{RAW_TABLE} (
            {columns},
            _loaded_at timestamptz not null default now()
        );
    """)
    db.copy_in(f"{RAW_SCHEMA}.{RAW_TABLE} ({', '.join(header)})", csv_path)
    count = int(db.scalar(f"select count(*) from {RAW_SCHEMA}.{RAW_TABLE}"))
    print(f"Loaded {count} rows into {RAW_SCHEMA}.{RAW_TABLE}")
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description="Load the raw ticket CSV into Postgres")
    parser.add_argument("csv_path", type=Path)
    load(parser.parse_args(argv).csv_path)


if __name__ == "__main__":
    main()
