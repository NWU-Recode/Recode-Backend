"""add expected_hash to question_tests

Revision ID: e1c2d3f4add
Revises: 
Create Date: 2025-10-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'e1c2d3f4add'
down_revision = None  # set to previous head manually if needed
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.question_tests
            ADD COLUMN IF NOT EXISTS expected_hash text NULL;
        """
    )


def downgrade() -> None:
    # Leaving column in place to avoid data loss; drop manually if required.
    pass
