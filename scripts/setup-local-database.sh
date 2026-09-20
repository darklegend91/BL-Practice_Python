#!/usr/bin/env bash
# Creates the development and test databases with separate roles, then applies
# migrations. Safe to re-run.
set -euo pipefail

HOST="${PGHOST:-localhost}"
PORT="${PGPORT:-5432}"

psql -h "$HOST" -p "$PORT" -d postgres -v ON_ERROR_STOP=1 <<'SQL'
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='llmfit_migrate') THEN
    CREATE ROLE llmfit_migrate LOGIN PASSWORD 'llmfit_migrate';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='llmfit_app') THEN
    CREATE ROLE llmfit_app LOGIN PASSWORD 'llmfit_app'
      NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
END $$;
SQL

for database in llmfit llmfit_test; do
  if ! psql -h "$HOST" -p "$PORT" -d postgres -tAc \
       "SELECT 1 FROM pg_database WHERE datname='${database}'" | grep -q 1; then
    psql -h "$HOST" -p "$PORT" -d postgres -v ON_ERROR_STOP=1 \
      -c "CREATE DATABASE ${database} OWNER llmfit_migrate"
  fi
  psql -h "$HOST" -p "$PORT" -d "${database}" -v ON_ERROR_STOP=1 \
    -c "CREATE EXTENSION IF NOT EXISTS pgcrypto" >/dev/null
done

export LLMFIT_MIGRATION_DATABASE_URL="postgresql+psycopg://llmfit_migrate:llmfit_migrate@${HOST}:${PORT}/llmfit"
alembic upgrade head

export LLMFIT_MIGRATION_DATABASE_URL="postgresql+psycopg://llmfit_migrate:llmfit_migrate@${HOST}:${PORT}/llmfit_test"
alembic upgrade head

echo "Databases llmfit and llmfit_test are ready."
