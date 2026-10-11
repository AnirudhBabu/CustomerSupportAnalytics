#!/usr/bin/env bash
# Runs once, when the Postgres volume is first created (docker-entrypoint-initdb.d).
# CI runs the same script against its Postgres service.
#
#   metabase_reader  read-only login Metabase uses to query the analytics schema
#   metabase_app     owns the metabase_app database, where Metabase keeps its own state
set -euo pipefail

: "${METABASE_READER_PASSWORD:?METABASE_READER_PASSWORD must be set}"
: "${METABASE_APP_DB_PASSWORD:?METABASE_APP_DB_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 \
     --username "${POSTGRES_USER:-${PGUSER:-postgres}}" \
     --dbname "${POSTGRES_DB:-${PGDATABASE:-support}}" \
     -v reader_password="$METABASE_READER_PASSWORD" \
     -v app_password="$METABASE_APP_DB_PASSWORD" <<'SQL'
select 'create role metabase_reader login'
where not exists (select from pg_roles where rolname = 'metabase_reader') \gexec
alter role metabase_reader with login password :'reader_password';

select 'create role metabase_app login'
where not exists (select from pg_roles where rolname = 'metabase_app') \gexec
alter role metabase_app with login password :'app_password';

select 'create database metabase_app owner metabase_app'
where not exists (select from pg_database where datname = 'metabase_app') \gexec

-- dbt builds into this schema and grants select on each model to the reader
create schema if not exists analytics;
grant usage on schema analytics to metabase_reader;
SQL
