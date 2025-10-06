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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('slide_extractions')}

    if 'module_id' not in existing_columns:
        op.add_column('slide_extractions', sa.Column('module_id', sa.Integer(), nullable=True))
    if 'week_number' not in existing_columns:
        op.add_column('slide_extractions', sa.Column('week_number', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove module_id and week_number columns from slide_extractions table
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('slide_extractions')}

    if 'week_number' in existing_columns:
        op.drop_column('slide_extractions', 'week_number')
    if 'module_id' in existing_columns:
        op.drop_column('slide_extractions', 'module_id')
