"""Generate the simulated customer support ticket dataset.

The output is the *raw* landing file for the pipeline: it is loaded into the
`raw` schema in Postgres and typed, tested and modelled by dbt from there.

Usage:
    python data/data_generator.py                     # writes build/tickets_raw.csv
    python data/data_generator.py --output some.csv --seed 7 --tickets 1000
"""
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "build" / "tickets_raw.csv"

CHANNELS = ['Chat', 'Email', 'Phone', 'Social Media', 'Self-Service']
CATEGORIES = ['Booking Modification', 'Payment Issue', 'Cancellation Request',
              'Property Question', 'Technical Issue', 'Refund Request',
              'Account Access', 'General Inquiry']
PRIORITIES = ['Low', 'Medium', 'High', 'Critical']
TEAMS = ['Team_Alpha', 'Team_Beta', 'Team_Gamma', 'Team_Delta']
STATUSES = ['Resolved', 'In Progress', 'Escalated']
REGION_COUNTRIES = {
    'APAC': ['Thailand', 'Singapore', 'Japan', 'Australia', 'India'],
    'EMEA': ['UK', 'Germany', 'France', 'UAE'],
    'Americas': ['USA', 'Canada', 'Brazil'],
}

# Service levels used to derive the SLA flags (dbt reads the same values from
# its project vars; a data test checks the two agree)
RESPONSE_SLA_MINUTES = 30
RESOLUTION_SLA_HOURS = 24


def _response_time(priority):
    """Minutes to first response; faster for higher priorities."""
    scale = {'Critical': 5, 'High': 15, 'Medium': 45}.get(priority, 120)
    return max(1, np.random.exponential(scale))


def _resolution_time(priority, category):
    """Hours to resolution; payments and refunds take longer."""
    base_time = {'Critical': 2, 'High': 6, 'Medium': 24, 'Low': 48}[priority]
    if category in ['Payment Issue', 'Refund Request']:
        base_time *= 1.5
    return max(0.5, np.random.exponential(base_time))


def _status(resolution_hours):
    if resolution_hours < 1:
        return 'Resolved'
    if resolution_hours < 24:
        return np.random.choice(['Resolved', 'In Progress'], p=[0.8, 0.2])
    return np.random.choice(STATUSES, p=[0.6, 0.3, 0.1])


def _csat(resolution_hours):
    """CSAT 1-5: customers whose tickets are resolved faster tend to be happier."""
    if resolution_hours < 4:
        mean = 4.4
    elif resolution_hours < 24:
        mean = 3.8
    elif resolution_hours < 72:
        mean = 2.9
    else:
        mean = 2.1
    return int(np.clip(np.rint(np.random.normal(mean, 0.9)), 1, 5))


def generate_tickets(num_tickets=5000, seed=42):
    """Return the simulated tickets as a DataFrame.

    The random draws happen in a fixed order from NumPy's legacy global
    generator, so the same seed always produces the same data.
    """
    np.random.seed(seed)

    hours = pd.date_range(datetime(2024, 1, 1), datetime(2024, 12, 31), freq='h')
    created_dates = pd.to_datetime(np.random.choice(hours, size=num_tickets)).to_pydatetime()
    channels = np.random.choice(CHANNELS, size=num_tickets, p=[0.35, 0.30, 0.20, 0.10, 0.05])
    categories = np.random.choice(CATEGORIES, size=num_tickets,
                                  p=[0.20, 0.15, 0.18, 0.12, 0.10, 0.15, 0.05, 0.05])
    priorities = np.random.choice(PRIORITIES, size=num_tickets, p=[0.40, 0.35, 0.20, 0.05])

    # 25 agents; each belongs to exactly one team (round-robin: 7/6/6/6)
    agents = [f"Agent_{i:03d}" for i in range(1, 26)]
    agent_team = {agent: TEAMS[i % len(TEAMS)] for i, agent in enumerate(agents)}
    assigned_agents = np.random.choice(agents, size=num_tickets)

    first_response = [_response_time(p) for p in priorities]
    resolution = [_resolution_time(p, c) for p, c in zip(priorities, categories)]
    statuses = [_status(rt) for rt in resolution]
    csat = [_csat(rt) if s == 'Resolved' else None for s, rt in zip(statuses, resolution)]
    resolved_dates = [created + timedelta(hours=rt) if s == 'Resolved' else None
                      for created, rt, s in zip(created_dates, resolution, statuses)]

    regions = np.random.choice(list(REGION_COUNTRIES), size=num_tickets, p=[0.50, 0.30, 0.20])
    countries = [np.random.choice(REGION_COUNTRIES[r]) for r in regions]

    df = pd.DataFrame({
        'ticket_id': [f'TKT-{i:06d}' for i in range(1, num_tickets + 1)],
        'created_date': created_dates,
        'channel': channels,
        'category': categories,
        'priority': priorities,
        'agent': assigned_agents,
        'team': [agent_team[a] for a in assigned_agents],
        'first_response_minutes': first_response,
        'resolution_hours': resolution,
        'status': statuses,
        'resolved_date': resolved_dates,
        'csat_score': csat,
        'region': regions,
        'country': countries,
    })
    df['response_sla_met'] = df['first_response_minutes'] < RESPONSE_SLA_MINUTES
    df['resolution_sla_met'] = df['resolution_hours'] < RESOLUTION_SLA_HOURS
    df['month'] = df['created_date'].dt.to_period('M').astype(str)
    df['week'] = df['created_date'].dt.to_period('W').astype(str)
    df['day_of_week'] = df['created_date'].dt.day_name()
    df['hour_of_day'] = df['created_date'].dt.hour
    return df


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--tickets', type=int, default=5000)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args(argv)

    df = generate_tickets(args.tickets, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Generated {len(df)} tickets -> {args.output}")
    print(f"Status mix: { {str(k): int(v) for k, v in df['status'].value_counts().items()} }")
    print(f"Average CSAT: {df['csat_score'].mean():.2f}")


if __name__ == '__main__':
    main()
