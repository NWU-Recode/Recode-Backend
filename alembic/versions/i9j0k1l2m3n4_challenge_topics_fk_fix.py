"""Fix FK for challenge_topics.topic_id to reference topics(id)

Revision ID: i9j0k1l2m3n4
Revises: h7i8j9k0l1m2
Create Date: 2025-10-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'i9j0k1l2m3n4'
down_revision: Union[str, Sequence[str], None] = 'h7i8j9k0l1m2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop wrong FK (if it exists) and recreate the correct FK referencing public.topics(id).

    This migration is defensive: it only creates the FK if it does not already exist.
    """
    # Drop the existing constraint if present
    op.execute(
        """
        ALTER TABLE public.challenge_topics
          DROP CONSTRAINT IF EXISTS challenge_topics_topic_id_fkey;
        """
    )

    # Recreate FK to public.topics(id) with cascade
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'challenge_topics_topic_id_fkey'
          ) THEN
            ALTER TABLE public.challenge_topics
              ADD CONSTRAINT challenge_topics_topic_id_fkey
              FOREIGN KEY (topic_id)
              REFERENCES public.topics (id)
              ON UPDATE CASCADE
              ON DELETE CASCADE;
          END IF;
        END$$;
        """
    )


def downgrade() -> None:
    """Revert the FK change by dropping the constraint if present.

    Downgrade is idempotent / safe; it will drop the FK if it exists.
    """
    op.execute(
        """
        ALTER TABLE public.challenge_topics
          DROP CONSTRAINT IF EXISTS challenge_topics_topic_id_fkey;
        """
    )
