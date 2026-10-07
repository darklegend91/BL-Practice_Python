"""A plan carries a price note too, so a converted price can say so

Revision ID: 0003_plan_price_note
Revises: 0002_adapters
Create Date: 2026-09-21 11:45:48.852560
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0003_plan_price_note'
down_revision = '0002_adapters'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS because a development database may already have this from
    # before the migration was written.
    op.execute("ALTER TABLE plans ADD COLUMN IF NOT EXISTS price_note text")


def downgrade() -> None:
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS price_note")
