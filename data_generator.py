import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

# Configuration
num_tickets = 5000
start_date = datetime(2024, 1, 1)
end_date = datetime(2024, 12, 31)

# Generate timestamps
date_range = pd.date_range(start_date, end_date, freq='h')
created_dates = pd.to_datetime(
    np.random.choice(date_range, size=num_tickets)
).to_pydatetime()

# Support channels (weighted by real-world distribution)
channels = np.random.choice(
    ['Chat', 'Email', 'Phone', 'Social Media', 'Self-Service'],
    size=num_tickets,
    p=[0.35, 0.30, 0.20, 0.10, 0.05]
)

# Issue categories relevant to travel booking
categories = np.random.choice(
    ['Booking Modification', 'Payment Issue', 'Cancellation Request',
     'Property Question', 'Technical Issue', 'Refund Request',
     'Account Access', 'General Inquiry'],
    size=num_tickets,
    p=[0.20, 0.15, 0.18, 0.12, 0.10, 0.15, 0.05, 0.05]
)

# Priority levels
priorities = np.random.choice(
    ['Low', 'Medium', 'High', 'Critical'],
    size=num_tickets,
    p=[0.40, 0.35, 0.20, 0.05]
)

# Agent assignments (simulate 25 agents)
agents = [f"Agent_{i:03d}" for i in range(1, 26)]
assigned_agents = np.random.choice(agents, size=num_tickets)

# Response times (in minutes) - vary by priority


def generate_response_time(priority):
    if priority == 'Critical':
        return max(1, np.random.exponential(5))
    elif priority == 'High':
        return max(1, np.random.exponential(15))
    elif priority == 'Medium':
        return max(1, np.random.exponential(45))
    else:
        return max(1, np.random.exponential(120))


first_response_times = [generate_response_time(p) for p in priorities]

# Resolution times (in hours)


def generate_resolution_time(priority, category):
    base_time = {
        'Critical': 2,
        'High': 6,
        'Medium': 24,
        'Low': 48
    }[priority]

    # Some categories take longer
    if category in ['Payment Issue', 'Refund Request']:
        base_time *= 1.5

    return max(0.5, np.random.exponential(base_time))


resolution_times = [generate_resolution_time(
    p, c) for p, c in zip(priorities, categories)]

# Resolution status
statuses = []
for rt in resolution_times:
    if rt < 1:
        statuses.append('Resolved')
    elif rt < 24:
        statuses.append(np.random.choice(
            ['Resolved', 'In Progress'], p=[0.8, 0.2]))
    else:
        statuses.append(np.random.choice(
            ['Resolved', 'In Progress', 'Escalated'], p=[0.6, 0.3, 0.1]))

# Customer satisfaction (CSAT) - only for resolved tickets
csat_scores = []
for status in statuses:
    if status == 'Resolved':
        # Higher satisfaction for faster resolution
        csat_scores.append(np.random.randint(1, 6))
    else:
        csat_scores.append(None)

# Calculate resolved dates
resolved_dates = []
for i, status in enumerate(statuses):
    if status == 'Resolved':
        resolved_dates.append(
            created_dates[i] + timedelta(hours=resolution_times[i]))
    else:
        resolved_dates.append(None)

# Geography (simulate global support)
regions = np.random.choice(
    ['APAC', 'EMEA', 'Americas'],
    size=num_tickets,
    p=[0.50, 0.30, 0.20]  # Agoda is APAC-heavy
)

countries = []
for region in regions:
    if region == 'APAC':
        countries.append(np.random.choice(
            ['Thailand', 'Singapore', 'Japan', 'Australia', 'India']))
    elif region == 'EMEA':
        countries.append(np.random.choice(['UK', 'Germany', 'France', 'UAE']))
    else:
        countries.append(np.random.choice(['USA', 'Canada', 'Brazil']))

# Agent team assignments
teams = np.random.choice(
    ['Team_Alpha', 'Team_Beta', 'Team_Gamma', 'Team_Delta'],
    size=num_tickets
)

# Create DataFrame
df = pd.DataFrame({
    'ticket_id': [f'TKT-{i:06d}' for i in range(1, num_tickets + 1)],
    'created_date': created_dates,
    'channel': channels,
    'category': categories,
    'priority': priorities,
    'agent': assigned_agents,
    'team': teams,
    'first_response_minutes': first_response_times,
    'resolution_hours': resolution_times,
    'status': statuses,
    'resolved_date': resolved_dates,
    'csat_score': csat_scores,
    'region': regions,
    'country': countries
})

# Add calculated fields
df['response_sla_met'] = df['first_response_minutes'] < 30  # 30 min SLA
df['resolution_sla_met'] = df['resolution_hours'] < 24  # 24 hour SLA
df['month'] = df['created_date'].dt.to_period('M').astype(str)
df['week'] = df['created_date'].dt.to_period('W').astype(str)
df['day_of_week'] = df['created_date'].dt.day_name()
df['hour_of_day'] = df['created_date'].dt.hour

# Save to CSV
df.to_csv('customer_support_tickets.csv', index=False)
print(f"Generated {len(df)} tickets")
print(f"Columns: {df.columns.tolist()}")
print(f"\nSample data:")
print(df.head())
print(f"\nStatus distribution:")
print(df['status'].value_counts())
print(f"\nAverage CSAT: {df['csat_score'].mean():.2f}")
