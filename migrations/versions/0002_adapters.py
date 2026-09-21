"""Per-source adapters, and board power kept apart from whole-machine power

Revision ID: 0002_adapters
Revises: 0001_initial
Create Date: 2026-09-21 01:59:53.348332
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002_adapters'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('hardware', sa.Column('gpu_board_watts', sa.Numeric(precision=12, scale=3), nullable=True))
    op.add_column('hardware', sa.Column('price_note', sa.Text(), nullable=True))
    op.add_column('sources', sa.Column('adapter', sa.String(length=40), server_default=sa.text("'factblock'"), nullable=False))
    op.add_column('sources', sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))


def downgrade() -> None:
    op.drop_column('sources', 'config')
    op.drop_column('sources', 'adapter')
    op.drop_column('hardware', 'price_note')
    op.drop_column('hardware', 'gpu_board_watts')
