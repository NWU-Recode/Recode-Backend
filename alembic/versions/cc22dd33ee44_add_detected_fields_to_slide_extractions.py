"""add detected_topic and detected_subtopics to slide_extractions

Revision ID: cc22dd33ee44
Revises: bb11cc22dd33
Create Date: 2025-08-29 06:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'cc22dd33ee44'
down_revision: Union[str, Sequence[str], None] = 'bb11cc22dd33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("ALTER TABLE public.slide_extractions ADD COLUMN IF NOT EXISTS detected_topic text"))
    bind.execute(text("ALTER TABLE public.slide_extractions ADD COLUMN IF NOT EXISTS detected_subtopics jsonb"))


def downgrade() -> None:
    bind = op.get_bind()
    try:
        bind.execute(text("ALTER TABLE public.slide_extractions DROP COLUMN IF EXISTS detected_subtopics"))
    except Exception:
        pass
    try:
        bind.execute(text("ALTER TABLE public.slide_extractions DROP COLUMN IF EXISTS detected_topic"))
    except Exception:
        pass

