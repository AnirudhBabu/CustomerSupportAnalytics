"""Export the modelled tickets to the CSV that Tableau and Power BI read.

The file keeps the original column names, order and value formatting, so the
existing Tableau workbook and the Power BI model work unchanged, but every
value now comes from the tested fct_tickets table rather than straight from
the generator.
"""
import argparse
import os
import tempfile
from pathlib import Path

from pipeline import db

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "data" / "customer_support_tickets.csv"

def float_text(column):
    """Format a double like Python does, keeping a trailing '.0' on whole numbers.

    Postgres writes 1.0 as '1'; matching the generator's formatting keeps the
    exported file byte-identical to its source, so regenerating it does not
    produce noisy Git diffs.
    """
    return rf"regexp_replace({column}::text, '^(-?\d+)$', '\1.0')"


EXPORT_SQL = f"""
select
    ticket_id,
    created_at                                                      as created_date,
    channel,
    category,
    priority,
    agent,
    team,
    {float_text('first_response_minutes')}                          as first_response_minutes,
    {float_text('resolution_hours')}                                as resolution_hours,
    status,
    to_char(resolved_at, 'YYYY-MM-DD HH24:MI:SS.US')                as resolved_date,
    csat_score::numeric(2, 1)                                       as csat_score,
    region,
    country,
    case when response_sla_met then 'True' else 'False' end         as response_sla_met,
    case when resolution_sla_met then 'True' else 'False' end       as resolution_sla_met,
    month,
    week,
    day_of_week,
    hour_of_day
from analytics.fct_tickets
order by ticket_id
"""


def export(output=DEFAULT_OUTPUT):
    """Write the export atomically: to a temporary file beside the target, then swap it in.

    Readers never see a half-written file, and the target is replaced rather
    than overwritten, so this works when the existing file belongs to another
    user (e.g. a repo checked out by the host and mounted into a container),
    as long as the folder itself is writable.
    """
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not os.access(output.parent, os.W_OK):
        raise PermissionError(f"cannot write to {output.parent}; make the folder writable "
                              f"for this user (e.g. `chmod a+w {output.parent.name}`)")
    fd, tmp = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    os.close(fd)
    try:
        db.copy_out(EXPORT_SQL, tmp)
        os.chmod(tmp, 0o644)
        os.replace(tmp, output)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    print(f"Exported analytics.fct_tickets -> {output}")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export fct_tickets to CSV for Tableau and Power BI")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    export(parser.parse_args(argv).output)


if __name__ == "__main__":
    main()
