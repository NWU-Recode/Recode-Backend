"""Convert profiles.supabase_id to UUID and add FK to auth.users

Revision ID: f4a5b6c7d8e9
Revises: e3f4g5h6i7j8
Create Date: 2025-08-17 20:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, Sequence[str], None] = 'e3f4g5h6i7j8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgcrypto for UUID casting if needed (usually already created)
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    # Cast existing column to uuid (using a safe cast). If any bad rows exist, this will fail; optionally pre-validate.
    op.execute(
        """
        ALTER TABLE public.profiles
          ALTER COLUMN supabase_id TYPE uuid USING supabase_id::uuid;
        """
    )
    op.execute("ALTER TABLE public.profiles ALTER COLUMN supabase_id SET NOT NULL;")
    # Add unique constraint if not exists (avoid duplicate constraint creation)
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'profiles_supabase_id_key'
          ) THEN
            ALTER TABLE public.profiles ADD CONSTRAINT profiles_supabase_id_key UNIQUE (supabase_id);
          END IF;
        END$$;
        """
    )
    # Clean up orphan rows (profiles referencing non-existent auth.users ids) before adding FK
    # NOTE: If you prefer to keep them, move them to an archive table instead of deleting.
    op.execute(
        """
        DELETE FROM public.profiles p
        WHERE NOT EXISTS (
          SELECT 1 FROM auth.users u WHERE u.id = p.supabase_id
        );
        """
    )
    # Add FK to auth.users (on delete cascade) if not exists
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'profiles_supabase_id_fkey'
          ) THEN
            ALTER TABLE public.profiles
              ADD CONSTRAINT profiles_supabase_id_fkey
              FOREIGN KEY (supabase_id) REFERENCES auth.users (id) ON DELETE CASCADE;
          END IF;
        END$$;
        """
    )


def downgrade() -> None:
    # Drop FK and unique, revert to text (varchar)
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'profiles_supabase_id_fkey'
          ) THEN
            ALTER TABLE public.profiles DROP CONSTRAINT profiles_supabase_id_fkey;
          END IF;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'profiles_supabase_id_key'
          ) THEN
            ALTER TABLE public.profiles DROP CONSTRAINT profiles_supabase_id_key;
          END IF;
        END$$;
        """
    )
    op.execute(
        """
        ALTER TABLE public.profiles
          ALTER COLUMN supabase_id TYPE varchar(255) USING supabase_id::text;
        """
    )
