"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-09-20 23:10:15.528075
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # gen_random_uuid() supplies the default for every primary key.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table('hardware',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('slug', sa.String(length=120), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('vram_gb', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('ram_gb', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('active_watts', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('idle_watts', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('price', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=True),
    sa.Column('region', sa.String(length=2), nullable=True),
    sa.Column('setup_hours', sa.Numeric(precision=12, scale=3), server_default=sa.text('2'), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role in ('gpu','system')", name=op.f('ck_hardware_role_known')),
    sa.CheckConstraint('price is null or price >= 0', name=op.f('ck_hardware_price_not_negative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_hardware')),
    sa.UniqueConstraint('slug', name=op.f('uq_hardware_slug'))
    )
    op.create_table('models',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('slug', sa.String(length=120), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('params_b', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('quantization', sa.String(length=40), nullable=True),
    sa.Column('weights_gb', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('max_context', sa.Integer(), nullable=True),
    sa.Column('layers', sa.Integer(), nullable=True),
    sa.Column('kv_heads', sa.Integer(), nullable=True),
    sa.Column('head_dim', sa.Integer(), nullable=True),
    sa.Column('commercial_use', sa.Boolean(), nullable=True),
    sa.Column('suitable_for', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('setup_hours', sa.Numeric(precision=12, scale=3), server_default=sa.text('3'), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_models')),
    sa.UniqueConstraint('slug', name=op.f('uq_models_slug'))
    )
    op.create_table('pages',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('markdown', sa.Text(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('changed', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('rows_found', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pages')),
    sa.UniqueConstraint('url', name=op.f('uq_pages_url'))
    )
    op.create_table('plans',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('slug', sa.String(length=120), nullable=False),
    sa.Column('provider', sa.String(length=120), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('price', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=True),
    sa.Column('billing_interval', sa.String(length=10), server_default=sa.text("'monthly'"), nullable=False),
    sa.Column('min_seats', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('regions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('max_context', sa.Integer(), nullable=True),
    sa.Column('messages_per_day', sa.Integer(), nullable=True),
    sa.Column('supports_api', sa.Boolean(), nullable=True),
    sa.Column('commercial_use', sa.Boolean(), nullable=True),
    sa.Column('suitable_for', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('setup_hours', sa.Numeric(precision=12, scale=3), server_default=sa.text('1'), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("billing_interval in ('monthly','annual')", name=op.f('ck_plans_billing_interval_known')),
    sa.CheckConstraint('min_seats >= 1', name=op.f('ck_plans_min_seats_at_least_one')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_plans')),
    sa.UniqueConstraint('provider', 'name', name=op.f('uq_plans_provider_name')),
    sa.UniqueConstraint('slug', name=op.f('uq_plans_slug'))
    )
    op.create_table('sources',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('label', sa.String(length=200), server_default=sa.text("''"), nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sources')),
    sa.UniqueConstraint('url', name=op.f('uq_sources_url'))
    )


def downgrade() -> None:
    op.drop_table('sources')
    op.drop_table('plans')
    op.drop_table('pages')
    op.drop_table('models')
    op.drop_table('hardware')
