"""initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-19 16:12:28.575539
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # gen_random_uuid() is the server-side default for every primary key.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table('catalog_items',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('slug', sa.String(length=200), nullable=False),
    sa.Column('current_revision_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind in ('hardware','model','plan')", name=op.f('ck_catalog_items_kind_known')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_catalog_items')),
    sa.UniqueConstraint('kind', 'slug', name=op.f('uq_catalog_items_kind_slug'))
    )
    op.create_index('ix_catalog_items_kind', 'catalog_items', ['kind'], unique=False)
    op.create_table('organizations',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('default_region', sa.String(length=2), nullable=False),
    sa.Column('default_currency', sa.String(length=3), nullable=False),
    sa.Column('default_electricity_tariff', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_organizations')),
    sa.UniqueConstraint('name', name=op.f('uq_organizations_name'))
    )
    op.create_table('sources',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('allowed_hosts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('category', sa.String(length=40), nullable=False),
    sa.Column('owner', sa.String(length=200), nullable=False),
    sa.Column('refresh_interval_seconds', sa.Integer(), nullable=False),
    sa.Column('max_page_bytes', sa.Integer(), nullable=False),
    sa.Column('timeout_seconds', sa.Integer(), nullable=False),
    sa.Column('crawl_permission_notes', sa.Text(), server_default=sa.text("''"), nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("category in ('manufacturer','retailer','publisher','provider_plan')", name=op.f('ck_sources_category_known')),
    sa.CheckConstraint('max_page_bytes >= 0', name=op.f('ck_sources_max_page_bytes_nonnegative')),
    sa.CheckConstraint('refresh_interval_seconds >= 0', name=op.f('ck_sources_refresh_interval_seconds_nonnegative')),
    sa.CheckConstraint('timeout_seconds >= 0', name=op.f('ck_sources_timeout_seconds_nonnegative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sources')),
    sa.UniqueConstraint('url', name=op.f('uq_sources_url'))
    )
    op.create_table('users',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('display_name', sa.String(length=200), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('platform_role', sa.String(length=40), server_default=sa.text("'none'"), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("platform_role in ('none','catalog_editor','catalog_reviewer','catalog_admin')", name=op.f('ck_users_platform_role_known')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('audit_events',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('target_type', sa.String(length=60), nullable=False),
    sa.Column('target_id', sa.UUID(), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_events_actor_id'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_audit_events_organization_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events'))
    )
    op.create_index('ix_audit_events_created', 'audit_events', ['created_at'], unique=False)
    op.create_table('catalog_revisions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('schema_version', sa.String(length=40), nullable=False),
    sa.Column('attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('review_status', sa.Enum('draft', 'pending_review', 'published', 'rejected', 'superseded', name='review_status'), nullable=False),
    sa.Column('author_id', sa.UUID(), nullable=False),
    sa.Column('lock_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('specs_reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("(review_status <> 'published') or (published_at is not null)", name=op.f('ck_catalog_revisions_published_has_timestamp')),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], name=op.f('fk_catalog_revisions_author_id'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['item_id'], ['catalog_items.id'], name=op.f('fk_catalog_revisions_item_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_catalog_revisions'))
    )
    op.create_index(op.f('ix_catalog_revisions_item_id'), 'catalog_revisions', ['item_id'], unique=False)
    op.create_index('ix_catalog_revisions_status', 'catalog_revisions', ['item_id', 'review_status'], unique=False)
    op.create_table('crawl_jobs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('state', sa.String(length=20), server_default=sa.text("'queued'"), nullable=False),
    sa.Column('dedupe_key', sa.String(length=200), nullable=False),
    sa.Column('run_after', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('max_attempts', sa.Integer(), server_default=sa.text('5'), nullable=False),
    sa.Column('lease_token', sa.UUID(), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("state in ('queued','running','succeeded','failed')", name=op.f('ck_crawl_jobs_state_known')),
    sa.CheckConstraint('attempts >= 0', name=op.f('ck_crawl_jobs_attempts_nonnegative')),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_crawl_jobs_source_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_crawl_jobs')),
    sa.UniqueConstraint('dedupe_key', name=op.f('uq_crawl_jobs_dedupe_key'))
    )
    op.create_index('ix_crawl_jobs_due', 'crawl_jobs', ['state', 'run_after'], unique=False)
    op.create_index(op.f('ix_crawl_jobs_source_id'), 'crawl_jobs', ['source_id'], unique=False)
    op.create_table('idempotency_keys',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('route', sa.String(length=200), nullable=False),
    sa.Column('key_digest', sa.String(length=128), nullable=False),
    sa.Column('request_hash', sa.String(length=128), nullable=False),
    sa.Column('outcome', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status_code', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_idempotency_keys_organization_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_idempotency_keys')),
    sa.UniqueConstraint('organization_id', 'route', 'key_digest', name=op.f('uq_idempotency_keys_organization_id_route_key_digest'))
    )
    op.create_index('ix_idempotency_keys_expires', 'idempotency_keys', ['expires_at'], unique=False)
    op.create_index(op.f('ix_idempotency_keys_organization_id'), 'idempotency_keys', ['organization_id'], unique=False)
    op.create_table('inventory_items',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('label', sa.String(length=200), nullable=False),
    sa.Column('configuration', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('quantity', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('owned', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('dedicated', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_inventory_items_quantity_positive')),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_inventory_items_organization_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_inventory_items')),
    sa.UniqueConstraint('organization_id', 'label', name=op.f('uq_inventory_items_organization_id_label'))
    )
    op.create_index(op.f('ix_inventory_items_organization_id'), 'inventory_items', ['organization_id'], unique=False)
    op.create_table('memberships',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role in ('owner','analyst','viewer')", name=op.f('ck_memberships_role_known')),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_memberships_organization_id'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_memberships_user_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_memberships')),
    sa.UniqueConstraint('organization_id', 'user_id', name=op.f('uq_memberships_organization_id_user_id'))
    )
    op.create_index(op.f('ix_memberships_organization_id'), 'memberships', ['organization_id'], unique=False)
    op.create_index(op.f('ix_memberships_user_id'), 'memberships', ['user_id'], unique=False)
    op.create_table('scenario_revisions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('label', sa.String(length=200), nullable=False),
    sa.Column('schema_version', sa.String(length=40), nullable=False),
    sa.Column('preset_version', sa.String(length=40), nullable=False),
    sa.Column('inputs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_scenario_revisions_created_by'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_scenario_revisions_organization_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_scenario_revisions')),
    sa.UniqueConstraint('id', 'organization_id', name=op.f('uq_scenario_revisions_id_organization_id'))
    )
    op.create_index('ix_scenario_revisions_org_created', 'scenario_revisions', ['organization_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_scenario_revisions_organization_id'), 'scenario_revisions', ['organization_id'], unique=False)
    op.create_table('sessions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_digest', sa.String(length=128), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sessions_user_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sessions')),
    sa.UniqueConstraint('token_digest', name=op.f('uq_sessions_token_digest'))
    )
    op.create_index('ix_sessions_expires_at', 'sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.create_table('source_snapshots',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('final_url', sa.Text(), nullable=False),
    sa.Column('http_status', sa.Integer(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('markdown', sa.Text(), nullable=False),
    sa.Column('byte_size', sa.Integer(), nullable=False),
    sa.Column('crawler_version', sa.String(length=80), nullable=False),
    sa.CheckConstraint('byte_size >= 0', name=op.f('ck_source_snapshots_byte_size_nonnegative')),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], name=op.f('fk_source_snapshots_source_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_source_snapshots')),
    sa.UniqueConstraint('source_id', 'content_hash', 'fetched_at', name=op.f('uq_source_snapshots_source_id_content_hash_fetched_at'))
    )
    op.create_index('ix_source_snapshots_history', 'source_snapshots', ['source_id', 'fetched_at'], unique=False)
    op.create_index(op.f('ix_source_snapshots_source_id'), 'source_snapshots', ['source_id'], unique=False)
    op.create_table('benchmark_observations',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('model_revision_id', sa.UUID(), nullable=False),
    sa.Column('quantization', sa.String(length=40), nullable=False),
    sa.Column('gpu_model', sa.String(length=120), nullable=False),
    sa.Column('runtime', sa.String(length=60), nullable=False),
    sa.Column('context_tokens', sa.Integer(), nullable=False),
    sa.Column('concurrency', sa.Integer(), nullable=False),
    sa.Column('tokens_per_second', sa.Numeric(precision=12, scale=3), nullable=False),
    sa.Column('measured_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('snapshot_id', sa.UUID(), nullable=True),
    sa.CheckConstraint('concurrency > 0', name=op.f('ck_benchmark_observations_concurrency_positive')),
    sa.CheckConstraint('context_tokens > 0', name=op.f('ck_benchmark_observations_context_tokens_positive')),
    sa.CheckConstraint('tokens_per_second >= 0', name=op.f('ck_benchmark_observations_tokens_per_second_nonnegative')),
    sa.ForeignKeyConstraint(['model_revision_id'], ['catalog_revisions.id'], name=op.f('fk_benchmark_observations_model_revision_id'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['snapshot_id'], ['source_snapshots.id'], name=op.f('fk_benchmark_observations_snapshot_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_benchmark_observations'))
    )
    op.create_index(op.f('ix_benchmark_observations_model_revision_id'), 'benchmark_observations', ['model_revision_id'], unique=False)
    op.create_table('evidence_claims',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('revision_id', sa.UUID(), nullable=False),
    sa.Column('field_name', sa.String(length=120), nullable=False),
    sa.Column('value_text', sa.Text(), nullable=False),
    sa.Column('snapshot_id', sa.UUID(), nullable=True),
    sa.Column('excerpt', sa.Text(), server_default=sa.text("''"), nullable=False),
    sa.Column('review_status', sa.Enum('DRAFT', 'PENDING_REVIEW', 'PUBLISHED', 'REJECTED', 'SUPERSEDED', name='review_status'), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['revision_id'], ['catalog_revisions.id'], name=op.f('fk_evidence_claims_revision_id'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['snapshot_id'], ['source_snapshots.id'], name=op.f('fk_evidence_claims_snapshot_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_evidence_claims')),
    sa.UniqueConstraint('revision_id', 'field_name', name=op.f('uq_evidence_claims_revision_id_field_name'))
    )
    op.create_index(op.f('ix_evidence_claims_revision_id'), 'evidence_claims', ['revision_id'], unique=False)
    op.create_table('plan_model_access',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('plan_revision_id', sa.UUID(), nullable=False),
    sa.Column('model_revision_id', sa.UUID(), nullable=False),
    sa.Column('conditions', sa.Text(), server_default=sa.text("''"), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['model_revision_id'], ['catalog_revisions.id'], name=op.f('fk_plan_model_access_model_revision_id'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plan_revision_id'], ['catalog_revisions.id'], name=op.f('fk_plan_model_access_plan_revision_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_plan_model_access')),
    sa.UniqueConstraint('plan_revision_id', 'model_revision_id', name=op.f('uq_plan_model_access_plan_revision_id_model_revision_id'))
    )
    op.create_index(op.f('ix_plan_model_access_plan_revision_id'), 'plan_model_access', ['plan_revision_id'], unique=False)
    op.create_table('price_observations',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('revision_id', sa.UUID(), nullable=False),
    sa.Column('seller', sa.String(length=200), nullable=False),
    sa.Column('region', sa.String(length=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('amount', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('tax_included', sa.Boolean(), nullable=False),
    sa.Column('billing_interval', sa.Enum('monthly', 'annual', name='billing_interval'), nullable=True),
    sa.Column('in_stock', sa.String(length=12), server_default=sa.text("'unknown'"), nullable=False),
    sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('snapshot_id', sa.UUID(), nullable=True),
    sa.CheckConstraint('amount >= 0', name=op.f('ck_price_observations_amount_nonnegative')),
    sa.ForeignKeyConstraint(['revision_id'], ['catalog_revisions.id'], name=op.f('fk_price_observations_revision_id'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['snapshot_id'], ['source_snapshots.id'], name=op.f('fk_price_observations_snapshot_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_price_observations')),
    sa.UniqueConstraint('revision_id', 'seller', 'region', 'observed_at', name=op.f('uq_price_observations_revision_id_seller_region_observed_at'))
    )
    op.create_index('ix_price_observations_region_currency', 'price_observations', ['region', 'currency'], unique=False)
    op.create_index(op.f('ix_price_observations_revision_id'), 'price_observations', ['revision_id'], unique=False)
    op.create_table('recommendation_runs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('scenario_revision_id', sa.UUID(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('policy_version', sa.String(length=40), nullable=False),
    sa.Column('app_version', sa.String(length=40), nullable=False),
    sa.Column('catalog_snapshot_id', sa.UUID(), nullable=False),
    sa.Column('inputs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('outputs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_recommendation_runs_created_by'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_recommendation_runs_organization_id'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['scenario_revision_id', 'organization_id'], ['scenario_revisions.id', 'scenario_revisions.organization_id'], name='scenario_same_organization', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recommendation_runs')),
    sa.UniqueConstraint('id', 'organization_id', name=op.f('uq_recommendation_runs_id_organization_id'))
    )
    op.create_index('ix_recommendation_runs_org_created', 'recommendation_runs', ['organization_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_recommendation_runs_organization_id'), 'recommendation_runs', ['organization_id'], unique=False)
    op.create_table('reviews',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('revision_id', sa.UUID(), nullable=False),
    sa.Column('reviewer_id', sa.UUID(), nullable=False),
    sa.Column('decision', sa.String(length=20), nullable=False),
    sa.Column('notes', sa.Text(), server_default=sa.text("''"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("decision in ('approved','rejected')", name=op.f('ck_reviews_decision_known')),
    sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], name=op.f('fk_reviews_reviewer_id'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['revision_id'], ['catalog_revisions.id'], name=op.f('fk_reviews_revision_id'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reviews'))
    )
    op.create_index(op.f('ix_reviews_revision_id'), 'reviews', ['revision_id'], unique=False)
    op.create_table('recommendation_evidence',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('revision_id', sa.UUID(), nullable=False),
    sa.Column('observation_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_recommendation_evidence_organization_id'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['revision_id'], ['catalog_revisions.id'], name=op.f('fk_recommendation_evidence_revision_id'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['run_id', 'organization_id'], ['recommendation_runs.id', 'recommendation_runs.organization_id'], name='run_same_organization', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recommendation_evidence')),
    sa.UniqueConstraint('run_id', 'revision_id', 'observation_id', name=op.f('uq_recommendation_evidence_run_id_revision_id_observation_id'))
    )
    op.create_index(op.f('ix_recommendation_evidence_organization_id'), 'recommendation_evidence', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_recommendation_evidence_organization_id'), table_name='recommendation_evidence')
    op.drop_table('recommendation_evidence')
    op.drop_index(op.f('ix_reviews_revision_id'), table_name='reviews')
    op.drop_table('reviews')
    op.drop_index(op.f('ix_recommendation_runs_organization_id'), table_name='recommendation_runs')
    op.drop_index('ix_recommendation_runs_org_created', table_name='recommendation_runs')
    op.drop_table('recommendation_runs')
    op.drop_index(op.f('ix_price_observations_revision_id'), table_name='price_observations')
    op.drop_index('ix_price_observations_region_currency', table_name='price_observations')
    op.drop_table('price_observations')
    op.drop_index(op.f('ix_plan_model_access_plan_revision_id'), table_name='plan_model_access')
    op.drop_table('plan_model_access')
    op.drop_index(op.f('ix_evidence_claims_revision_id'), table_name='evidence_claims')
    op.drop_table('evidence_claims')
    op.drop_index(op.f('ix_benchmark_observations_model_revision_id'), table_name='benchmark_observations')
    op.drop_table('benchmark_observations')
    op.drop_index(op.f('ix_source_snapshots_source_id'), table_name='source_snapshots')
    op.drop_index('ix_source_snapshots_history', table_name='source_snapshots')
    op.drop_table('source_snapshots')
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_index('ix_sessions_expires_at', table_name='sessions')
    op.drop_table('sessions')
    op.drop_index(op.f('ix_scenario_revisions_organization_id'), table_name='scenario_revisions')
    op.drop_index('ix_scenario_revisions_org_created', table_name='scenario_revisions')
    op.drop_table('scenario_revisions')
    op.drop_index(op.f('ix_memberships_user_id'), table_name='memberships')
    op.drop_index(op.f('ix_memberships_organization_id'), table_name='memberships')
    op.drop_table('memberships')
    op.drop_index(op.f('ix_inventory_items_organization_id'), table_name='inventory_items')
    op.drop_table('inventory_items')
    op.drop_index(op.f('ix_idempotency_keys_organization_id'), table_name='idempotency_keys')
    op.drop_index('ix_idempotency_keys_expires', table_name='idempotency_keys')
    op.drop_table('idempotency_keys')
    op.drop_index(op.f('ix_crawl_jobs_source_id'), table_name='crawl_jobs')
    op.drop_index('ix_crawl_jobs_due', table_name='crawl_jobs')
    op.drop_table('crawl_jobs')
    op.drop_index('ix_catalog_revisions_status', table_name='catalog_revisions')
    op.drop_index(op.f('ix_catalog_revisions_item_id'), table_name='catalog_revisions')
    op.drop_table('catalog_revisions')
    op.drop_index('ix_audit_events_created', table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_table('users')
    op.drop_table('sources')
    op.drop_table('organizations')
    op.drop_index('ix_catalog_items_kind', table_name='catalog_items')
    op.drop_table('catalog_items')
    # Enum types are not table-bound, so they are dropped explicitly; otherwise a
    # downgrade followed by an upgrade fails on an already-existing type.
    op.execute("DROP TYPE IF EXISTS billing_interval")
    op.execute("DROP TYPE IF EXISTS review_status")
