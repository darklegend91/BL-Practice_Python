-- Runtime and migration credentials are separate, and the runtime role is
-- neither a table owner nor a BYPASSRLS role (guide section 11).
CREATE ROLE llmfit_app LOGIN PASSWORD 'llmfit_app'
  NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT USAGE ON SCHEMA public TO llmfit_app;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
