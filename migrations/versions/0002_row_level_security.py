"""Row-level security, runtime grants and append-only audit rows

Guide sections 8 and 11: application authorization is enforced in service
functions, and PostgreSQL row security is a second, independent boundary. The
runtime role is neither the table owner nor a BYPASSRLS role, so the policies
below actually apply to it.

Revision ID: 0002_row_level_security
Revises: 0001_initial_schema
"""

from __future__ import annotations

from alembic import op

revision = "0002_row_level_security"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

RUNTIME_ROLE = "llmfit_app"
TENANT_SETTING = "app.organization_id"

# Private workspace data. Every row carries organization_id.
TENANT_TABLES = (
    "memberships",
    "inventory_items",
    "scenario_revisions",
    "recommendation_runs",
    "recommendation_evidence",
    "idempotency_keys",
)

# Shared data the runtime role may read; writes go through catalog workflows.
READ_MOSTLY_TABLES = (
    "users",
    "sessions",
    "organizations",
    "sources",
    "crawl_jobs",
    "source_snapshots",
    "catalog_items",
    "catalog_revisions",
    "evidence_claims",
    "price_observations",
    "plan_model_access",
    "benchmark_observations",
    "reviews",
)


def upgrade() -> None:
    op.execute(f"GRANT USAGE ON SCHEMA public TO {RUNTIME_ROLE}")

    for table in TENANT_TABLES + READ_MOSTLY_TABLES:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {RUNTIME_ROLE}"
        )

    # Audit rows are append-only for the runtime role: no UPDATE, no DELETE.
    op.execute(f"GRANT SELECT, INSERT ON audit_events TO {RUNTIME_ROLE}")

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE makes the policy apply to the table owner too, so a mistaken
        # connection as the owner does not quietly bypass tenant isolation.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # Fail closed: an empty or unset setting matches no rows at all.
        predicate = (
            f"nullif(current_setting('{TENANT_SETTING}', true), '')::uuid "
            "IS NOT DISTINCT FROM organization_id"
        )
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING ({predicate})
            WITH CHECK ({predicate})
            """
        )

    # Catalog evidence referenced by a saved decision is retired, never deleted.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION refuse_referenced_revision_delete()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM recommendation_evidence WHERE revision_id = OLD.id
          ) THEN
            RAISE EXCEPTION
              'catalog revision % is referenced by a saved recommendation; '
              'supersede it instead of deleting it', OLD.id
              USING ERRCODE = 'restrict_violation';
          END IF;
          RETURN OLD;
        END $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER catalog_revisions_no_referenced_delete
        BEFORE DELETE ON catalog_revisions
        FOR EACH ROW EXECUTE FUNCTION refuse_referenced_revision_delete()
        """
    )

    # A published result is immutable; its stored inputs and outputs never change.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION refuse_result_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.inputs IS DISTINCT FROM OLD.inputs
             OR NEW.outputs IS DISTINCT FROM OLD.outputs THEN
            RAISE EXCEPTION
              'recommendation run % is immutable; create a new run instead', OLD.id
              USING ERRCODE = 'restrict_violation';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER recommendation_runs_immutable
        BEFORE UPDATE ON recommendation_runs
        FOR EACH ROW EXECUTE FUNCTION refuse_result_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS recommendation_runs_immutable ON recommendation_runs"
    )
    op.execute("DROP FUNCTION IF EXISTS refuse_result_mutation()")
    op.execute(
        "DROP TRIGGER IF EXISTS catalog_revisions_no_referenced_delete "
        "ON catalog_revisions"
    )
    op.execute("DROP FUNCTION IF EXISTS refuse_referenced_revision_delete()")

    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    for table in TENANT_TABLES + READ_MOSTLY_TABLES + ("audit_events",):
        op.execute(f"REVOKE ALL ON {table} FROM {RUNTIME_ROLE}")
