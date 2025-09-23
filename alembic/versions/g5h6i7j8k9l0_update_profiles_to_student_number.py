"""Update profiles to use student number as primary key

Revision ID: g5h6i7j8k9l0
Revises: f4a5b6c7d8e9
Create Date: 2025-08-28 22:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'g5h6i7j8k9l0'
down_revision: Union[str, Sequence[str], None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_constraint_if_exists(conn, table: str, constraint: str) -> None:
    conn.execute(text(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = :table AND c.conname = :constraint
            ) THEN
                EXECUTE 'ALTER TABLE ' || quote_ident(:table) || ' DROP CONSTRAINT ' || quote_ident(:constraint);
            END IF;
        END
        $$;
        """
    ), {"table": table, "constraint": constraint})


def upgrade() -> None:
    """No-op for profiles; environment already migrated elsewhere.

    This revision previously attempted to rewrite profiles.id and related
    FKs. To keep compatibility across environments (local DB vs Supabase),
    we perform no changes here.
    """
    pass


def downgrade() -> None:
    """Downgrade schema."""
    # This is a destructive migration - downgrade would lose data
    # For safety, we'll just raise an error
    raise NotImplementedError("This migration cannot be safely downgraded as it would lose data")
