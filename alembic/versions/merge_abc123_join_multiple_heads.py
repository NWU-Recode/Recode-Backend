"""merge heads aa01bb02cc03, g5h6i7j8k9l0, h7i8j9k0l1m2

Revision ID: merge_abc123
Revises: aa01bb02cc03, g5h6i7j8k9l0, h7i8j9k0l1m2
Create Date: 2025-08-29 04:55:00.000000

"""
from typing import Sequence, Union

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'merge_abc123'
down_revision: Union[str, Sequence[str], None] = (
    'aa01bb02cc03',
    'g5h6i7j8k9l0',
    'h7i8j9k0l1m2',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge revision: no-op
    pass


def downgrade() -> None:
    # Merge revision: no-op
    pass

