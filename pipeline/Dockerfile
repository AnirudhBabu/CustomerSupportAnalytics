# One image for the pipeline (generate -> load -> dbt build -> export) and for
# provisioning Metabase.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements/pipeline.txt requirements/pipeline.txt
RUN pip install --no-cache-dir -r requirements/pipeline.txt

COPY data/data_generator.py data/data_generator.py
COPY pipeline/ pipeline/
COPY transform/ transform/
COPY metabase/provision.py metabase/dashboard.json metabase/
COPY metabase/questions/ metabase/questions/

# Run as an unprivileged user; dbt writes its target/ and logs/ inside transform/
RUN useradd --create-home --uid 1000 app \
 && mkdir -p build \
 && chown -R app:app /app
USER app

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "pipeline.run"]
