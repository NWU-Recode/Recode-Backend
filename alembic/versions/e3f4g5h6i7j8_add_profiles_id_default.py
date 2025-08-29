"""add server default for profiles.id

Revision ID: e3f4g5h6i7j8
Revises: d2f3e4c5b6a7
Create Date: 2025-08-17 18:15:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e3f4g5h6i7j8'
down_revision: Union[str, Sequence[str], None] = 'd2f3e4c5b6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    with op.batch_alter_table('profiles') as batch_op:
        batch_op.alter_column('id', server_default=sa.text('gen_random_uuid()'))

def downgrade() -> None:
    with op.batch_alter_table('profiles') as batch_op:
        batch_op.alter_column('id', server_default=None)
