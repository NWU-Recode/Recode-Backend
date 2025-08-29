"""add slides_key column to slide_extractions

Revision ID: bb11cc22dd33
Revises: merge_abc123
Create Date: 2025-08-29 06:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'bb11cc22dd33'
down_revision: Union[str, Sequence[str], None] = 'merge_abc123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Add column if not exists (Postgres)
    bind.execute(text("ALTER TABLE public.slide_extractions ADD COLUMN IF NOT EXISTS slides_key text"))


def downgrade() -> None:
    bind = op.get_bind()
    try:
        bind.execute(text("ALTER TABLE public.slide_extractions DROP COLUMN IF EXISTS slides_key"))
    except Exception:
        pass

