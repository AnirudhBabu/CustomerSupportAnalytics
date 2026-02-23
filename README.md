# 📊 Customer Support Operations Analytics
## A Comparative BI Study: Tableau vs. Metabase
## 🎯 Project Overview
This project was born out of a desire to bridge the gap between raw data processing and professional business intelligence. I simulated a dataset of 5,000 customer support tickets to explore how two industry leading tools, Tableau and Metabase, handle operational data.

By building the same analytics suite in both environments, I gained a deep understanding of when to use visual-first storytelling versus query-driven technical analysis.

The Goal: Extract actionable insights on SLA compliance, agent productivity, and channel performance to optimize support operations.

## 🛠️ The Tech Stack
* Data Generation: Python (Pandas/NumPy) to create a simulated lifecycle for 5,000 tickets, including CSAT scores and multi-stage timestamps.

* BI Tool A (Tableau): Used for executive level dashboarding, focusing on LOD (Level of Detail) expressions and interactive UI/UX.

* BI Tool B (Metabase): Hosted via Docker; used to write complex SQL window functions and build a technical "Deep-Dive" dashboard.

* Database: SQLite (converted from CSV) to provide a relational backend for the Metabase environment.

## 📈 Visualizations & Insights
1. Executive Operations Scorecard (Tableau)
* Designed for high level stakeholders to monitor department health in real time.

* Dynamic KPIs: Real-time tracking of Average First Response Time (FRT), SLA Achievement %, and CSAT.

* Interactive Filtering: Built-in global filters for Date Range, Region, and Priority.

* Geographic Mapping: A distribution map visualizing ticket volume vs. satisfaction scores by country.

2. SQL Analytics Deep-Dive (Metabase)
A technical layer focused on granular performance metrics using raw SQL.

* Trend Analysis: Used SQL window functions (AVG() OVER...) to create a 7-day rolling average of ticket volume.

* Productivity Heatmap: Analyzed "Peak Hours" vs. "Day of Week" to identify the highest pressure windows for support staff.

* Efficiency Metrics: Developed a "Channel-Category" matrix to identify which support channels are most effective for specific issue types.

## 📂 Repository Structure
1. [./data/data_generator.py`](./data/data_generator.py): The Python engine used to generate the simulated dataset.

2. [./data/customer_support_tickets.csv](./data/customer_support_tickets.csv): The raw output data used for Tableau.

3. [./data/support_data.db](./data/support_data.db): The SQLite database used to power the Metabase environment.

4. [./tableau/screenshots/](./tableau/screenshots/): High-resolution captures of the final interactive dashboard.

5. [./tableau/dashboard/](./tableau/dashboard/): Dashboard workbook file containing all views and published to Tableau Public.

6. [./metabase/screenshots/](./metabase/screenshots/): Previews of the SQL-driven questions and dashboards.

7. [./metabase/environment/](./metabase/environment/): Configuration for the metabase setup, including connection to the SQLite DB and questions, dashboard, etc.

8. [./metabase/sql_queries](./metabase/sql_queries): SQL Query Questions used to create most of the questions and visualizations.

9. [./docker-compose.yml](./docker-compose.yml): docker config for starting the metabase environment.

## 🚀 Quick Start for Reviewers
View the Live Tableau Dashboard
Explore the interactive Tableau Public workbook here: [Tableau Dashboard](https://public.tableau.com/app/profile/anirudh.babu8528/viz/KPI_17703308612410/CustomerSupportOperationsScorecard?publish=yes)

### Run the Environment Locally
1. Clone the repo:
  
   `git clone https://github.com/AnirudhBabu/CustomerSupportAnalytics.git`

2. Switch to the cloned repo folder:

  `cd ./CustomerSupportAnalytics`

3. Launch Metabase (requires Docker):

  `docker compose up -d`
  
  Wait for about 5 minutes after running this command and then...

4. Visit - [https://localhost:3000](https://localhost:3000)
   
  Login with the credentials:
  
  Email: `anonymous@example.com`
  
  Password: `Zb6tvel1lJdGGF`

## 🖥 Views

1. Tableau

* Dashboard containing all views
![Tableau Dashboard](./tableau/screenshots/Customer%20Support%20Operations%20Scorecard.png)

* Agent Performance
![Agent Performance by team in Tableau](./tableau/screenshots/Agent%20Performance.png)

* Customer Satisfaction by Country
![Customer Satisfaction Geographical heat map view](./tableau/screenshots/Customer%20Satisfaction%20-%20Country.png)

* First Response Channel
![First Response by Channel view](./tableau/screenshots/First%20Response%20Channel.png)

* KPI Score Card
![Key Performance Indicators View in Tableau](./tableau/screenshots/KPI%20Score%20Card.png)

* Ticket Distribution by Status
![Ticket Distribution view in Tableau](./tableau/screenshots/Ticket%20Distribution.png)

* Weekly Ticket Volume
![Weekly Ticket Volume view](./tableau/screenshots/Weekly%20Ticket%20Volume.png)

2. Metabase
* Metabase dashboard
![Metabase Dashboard](./metabase/screenshots/Metabase%20Support%20Dashboard.png)

* Agent Productivity by Customer Satisfaction
![Agent Productivity Question in Metabase](./metabase/screenshots/Agent%20Productivity.png)

* Category Channel Performance
![Category Channel Performance question in Metabase](./metabase/screenshots/Category%20Channel%20Performance.png)

* Daily Volume Chart
![Daily Volume Combo Chart](./metabase/screenshots/Daily%20Volume.png)

* Escalation Risk Analysis Bubble Chart
![Escalation Risk Analysis Question](./metabase/screenshots/Escalation%20Risk%20Analysis.png)

* Monthly CSAT Trends
![Monthly Trends Question](./metabase/screenshots/Monthly%20CSAT%20Trends.png)

* Peak Hours Analysis
![Peak Hours Analysis Question](./metabase/screenshots/Peak%20Hours%20Analysis.png)


## 🧠 Key Learnings
* Tool Adaptability: I learned how to translate business logic across different BI ecosystems, from Tableau's "Calculated Fields" to Metabase's "Native SQL."

* Operational Strategy: Identifying that a small percentage of "Escalated" tickets consumed 60% of total resolution time, suggesting a need for specialized "Tier 2" training.

* Full-Stack Thinking: Managing the entire pipeline from data generation (Python) to storage (SQLite) to visualization (BI Tools).
