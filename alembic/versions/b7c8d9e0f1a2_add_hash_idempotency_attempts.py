"""add hash and idempotency columns to question_attempts

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2025-08-15 01:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('question_attempts') as batch_op:
        batch_op.add_column(sa.Column('code_hash', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('idempotency_key', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('latest', sa.Boolean(), server_default='true', nullable=False))
        batch_op.create_index(batch_op.f('ix_question_attempts_code_hash'), ['code_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_question_attempts_idempotency_key'), ['idempotency_key'], unique=False)
        # Composite unique for idempotency per question/user/key
        batch_op.create_unique_constraint('uq_attempt_idempotency', ['question_id', 'user_id', 'idempotency_key'])


def downgrade() -> None:
    with op.batch_alter_table('question_attempts') as batch_op:
        batch_op.drop_constraint('uq_attempt_idempotency', type_='unique')
        batch_op.drop_index(batch_op.f('ix_question_attempts_idempotency_key'))
        batch_op.drop_index(batch_op.f('ix_question_attempts_code_hash'))
        batch_op.drop_column('latest')
        batch_op.drop_column('idempotency_key')
        batch_op.drop_column('code_hash')
