"""Independent reference implementation of every KPI, in pandas.

The parity tests compare the warehouse, the Metabase questions and the
Metabase API against these numbers. They are computed straight from the
generator's output with no SQL involved, so a bug in a dbt model or a
question's SQL shows up as a mismatch instead of being copied into the
expected values.
"""
import importlib.util
from functools import lru_cache

import numpy as np
import pandas as pd

from tests.helpers import REPO_ROOT

RESPONSE_SLA_MINUTES = 30
RESOLUTION_SLA_HOURS = 24


def _load_generator():
    spec = importlib.util.spec_from_file_location("data_generator", REPO_ROOT / "data" / "data_generator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def tickets():
    df = _load_generator().generate_tickets().copy()
    df["response_sla"] = df["first_response_minutes"] < RESPONSE_SLA_MINUTES
    df["resolution_sla"] = df["resolution_hours"] < RESOLUTION_SLA_HOURS
    df["resolved"] = df["status"] == "Resolved"
    df["escalated"] = df["status"] == "Escalated"
    df["date"] = df["created_date"].dt.normalize()
    return df


def _pct(series):
    return 100.0 * series.mean()


def _agent_score(df):
    rated = df[df["csat_score"].notna()]
    return (0.4 * rated["response_sla"] + 0.4 * rated["resolution_sla"]
            + 0.2 * rated["csat_score"] / 5).mean()


def summary():
    df = tickets()
    return {
        "tickets": len(df),
        "avg_first_response_minutes": df["first_response_minutes"].mean(),
        "avg_resolution_hours": df["resolution_hours"].mean(),
        "response_sla_pct": _pct(df["response_sla"]),
        "resolution_sla_pct": _pct(df["resolution_sla"]),
        "avg_csat": df["csat_score"].mean(),
        "resolution_rate_pct": _pct(df["resolved"]),
        "escalation_rate_pct": _pct(df["escalated"]),
        "escalated_share_of_resolution_hours_pct":
            100.0 * df.loc[df["escalated"], "resolution_hours"].sum() / df["resolution_hours"].sum(),
        "agent_performance_score": _agent_score(df),
    }


def by_agent():
    rows = {}
    for (agent, team), g in tickets().groupby(["agent", "team"]):
        rows[agent] = {
            "team": team,
            "total_tickets": len(g),
            "resolved_count": int(g["resolved"].sum()),
            "resolution_rate_pct": _pct(g["resolved"]),
            "avg_resolution_hours": g["resolution_hours"].mean(),
            "avg_csat": g["csat_score"].mean(),
            "response_sla_pct": _pct(g["response_sla"]),
            "agent_performance_score": _agent_score(g),
        }
    return rows


def daily_volume():
    df = tickets()
    start = pd.Timestamp(year=df["date"].min().year, month=1, day=1)
    end = pd.Timestamp(year=df["date"].max().year, month=12, day=31)
    counts = df.groupby("date").size().reindex(pd.date_range(start, end, freq="D"), fill_value=0)
    rolling = counts.rolling(7, min_periods=1).mean()
    return {d.strftime("%Y-%m-%d"): {"daily_tickets": int(c), "rolling_7day_avg": float(r)}
            for d, c, r in zip(counts.index, counts.values, rolling.values)}


def monthly():
    df = tickets()
    out = {}
    previous = None
    for month, g in sorted(df.groupby(df["created_date"].dt.strftime("%Y-%m"))):
        total = len(g)
        out[month] = {
            "total_tickets": total,
            "avg_first_response_minutes": g["first_response_minutes"].mean(),
            "avg_resolution_hours": g["resolution_hours"].mean(),
            "response_sla_pct": _pct(g["response_sla"]),
            "resolution_sla_pct": _pct(g["resolution_sla"]),
            "avg_csat": g["csat_score"].mean(),
            "volume_change_pct": None if previous is None else 100.0 * (total - previous) / previous,
        }
        previous = total
    return out


def category_channel():
    resolved = tickets()[tickets()["resolved"]]
    out = {}
    for (category, channel), g in resolved.groupby(["category", "channel"]):
        avg_res = g["resolution_hours"].mean()
        sla = _pct(g["resolution_sla"])
        if avg_res < 12 and sla > 80:
            fit = "Optimal"
        elif avg_res < 24 and sla > 60:
            fit = "Acceptable"
        else:
            fit = "Needs Improvement"
        out[(category, channel)] = {"volume": len(g), "avg_resolution_hours": avg_res,
                                    "resolution_sla_pct": sla, "channel_fit": fit}
    return out


def escalation():
    out = {}
    for (category, priority), g in tickets().groupby(["category", "priority"]):
        if len(g) < 20:
            continue
        esc = g[g["escalated"]]
        out[(category, priority)] = {
            "total_tickets": len(g),
            "escalated_count": len(esc),
            "escalation_rate_pct": _pct(g["escalated"]),
            "avg_escalated_resolution_hours": esc["resolution_hours"].mean() if len(esc) else None,
        }
    return out


def peak_hours():
    df = tickets()
    counts = df.groupby([df["created_date"].dt.day_name(), df["created_date"].dt.hour]).size()
    return {(day, int(hour)): int(n) for (day, hour), n in counts.items()}


def is_close(a, b, abs_tol=1e-9, rel_tol=1e-9):
    """Compare numbers that may be None/NaN or strings from psql or JSON."""
    def norm(x):
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return None
        return float(x)
    a, b = norm(a), norm(b)
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))
