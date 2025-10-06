"""add compare_mode and compare_config to question_tests

Revision ID: j1k2l3m4n5o6
Revises: e1c2d3f4add
Create Date: 2025-03-09 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "j1k2l3m4n5o6"
down_revision = "e1c2d3f4add"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "question_tests",
        sa.Column(
            "compare_mode",
            sa.String(length=32),
            nullable=False,
            server_default="AUTO",
        ),
    )
    op.add_column(
        "question_tests",
        sa.Column(
            "compare_config",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("question_tests", "compare_config")
    op.drop_column("question_tests", "compare_mode")
