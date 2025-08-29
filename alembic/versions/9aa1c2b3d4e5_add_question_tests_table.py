"""add question_tests table

Revision ID: 9aa1c2b3d4e5
Revises: 1ca7f15eca6b
Create Date: 2025-08-29 04:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '9aa1c2b3d4e5'
down_revision: Union[str, Sequence[str], None] = '1ca7f15eca6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fully idempotent creation using IF NOT EXISTS guards
    bind = op.get_bind()
    bind.execute(text(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'question_tests'
          ) THEN
            CREATE TABLE public.question_tests (
              id uuid PRIMARY KEY,
              question_id uuid NOT NULL REFERENCES public.questions(id) ON DELETE CASCADE,
              input text NOT NULL,
              expected text NOT NULL,
              visibility text NOT NULL,
              created_at timestamptz NOT NULL DEFAULT now(),
              CONSTRAINT ck_question_tests_visibility CHECK (visibility IN ('public','hidden'))
            );
          END IF;
        END
        $$;
        """
    ))
    bind.execute(text("CREATE INDEX IF NOT EXISTS ix_question_tests_question_id ON public.question_tests (question_id)"))
    bind.execute(text("CREATE INDEX IF NOT EXISTS ix_question_tests_visibility ON public.question_tests (visibility)"))


def downgrade() -> None:
    bind = op.get_bind()
    # Drop indexes and table if present
    try:
        bind.execute(text("DROP INDEX IF EXISTS public.ix_question_tests_visibility"))
    except Exception:
        pass
    try:
        bind.execute(text("DROP INDEX IF EXISTS public.ix_question_tests_question_id"))
    except Exception:
        pass
    try:
        bind.execute(text("DROP TABLE IF EXISTS public.question_tests"))
    except Exception:
        pass
