"""add_module_id_week_number_to_slide_extractions

Revision ID: 9fb950e72b50
Revises: cc22dd33ee44
Create Date: 2025-09-20 23:54:03.690249

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9fb950e72b50'
down_revision: Union[str, Sequence[str], None] = 'cc22dd33ee44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add module_id and week_number columns to slide_extractions table
    op.add_column('slide_extractions', sa.Column('module_id', sa.Integer(), nullable=True))
    op.add_column('slide_extractions', sa.Column('week_number', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove module_id and week_number columns from slide_extractions table
    op.drop_column('slide_extractions', 'week_number')
    op.drop_column('slide_extractions', 'module_id')
