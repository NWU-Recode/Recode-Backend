"""normalize base tier naming"""
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure enum types know about the canonical base label
    op.execute("ALTER TYPE challengetier ADD VALUE IF NOT EXISTS 'base'")
    op.execute("ALTER TYPE challengekind ADD VALUE IF NOT EXISTS 'base'")

    # Coerce legacy tier/kind values to the new canonical label
    op.execute("UPDATE challenges SET tier = 'base' WHERE tier IN ('plain', 'common')")
    op.execute("UPDATE challenges SET kind = 'base' WHERE kind IN ('plain', 'common')")


def downgrade() -> None:
    # Cannot easily remove enum values; leave data as-is.
    pass
