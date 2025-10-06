"""ensure challenge_attempts table exists

Revision ID: a1b2c3d4e5f6
Revises: merge_abc123
Create Date: 2025-08-15 00:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "merge_abc123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE_NAME = "challenge_attempts"


def _has_table() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return _TABLE_NAME in inspector.get_table_names()


def upgrade() -> None:
    if _has_table():
        return

    op.create_table(
        _TABLE_NAME,
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("challenge_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column(
            "snapshot_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("tests_total", sa.Integer(), nullable=True),
        sa.Column("tests_passed", sa.Integer(), nullable=True),
        sa.Column("elo_delta", sa.Integer(), nullable=True),
        sa.Column("efficiency_bonus", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_index("ix_challenge_attempts_challenge_id", _TABLE_NAME, ["challenge_id"], unique=False)
    op.create_index("ix_challenge_attempts_user_id", _TABLE_NAME, ["user_id"], unique=False)
    op.create_index("ix_challenge_attempts_status", _TABLE_NAME, ["status"], unique=False)
    op.create_unique_constraint(
        "uq_challenge_attempts_challenge_user",
        _TABLE_NAME,
        ["challenge_id", "user_id"],
    )


def downgrade() -> None:
    if not _has_table():
        return

    op.drop_constraint("uq_challenge_attempts_challenge_user", _TABLE_NAME, type_="unique")
    op.drop_index("ix_challenge_attempts_status", table_name=_TABLE_NAME)
    op.drop_index("ix_challenge_attempts_user_id", table_name=_TABLE_NAME)
    op.drop_index("ix_challenge_attempts_challenge_id", table_name=_TABLE_NAME)
    op.drop_table(_TABLE_NAME)
