"""add question_tests table

Revision ID: add_question_tests_table
Revises: c4af184fbf4e
Create Date: 2025-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_question_tests_table'
down_revision: Union[str, Sequence[str], None] = 'c4af184fbf4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if 'question_tests' not in table_names:
        op.create_table(
            'question_tests',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('question_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('input', sa.Text(), nullable=True),
            sa.Column('expected_output', sa.Text(), nullable=True),
            sa.Column('visibility', sa.String(length=50), server_default='private', nullable=False),
            sa.Column('valid', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('question_tests', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_question_tests_question_id'), ['question_id'], unique=False)
    else:
        existing_indexes = {ix['name'] for ix in inspector.get_indexes('question_tests')}
        index_name = 'ix_question_tests_question_id'
        if index_name not in existing_indexes:
            op.create_index(index_name, 'question_tests', ['question_id'])


def downgrade() -> None:
    with op.batch_alter_table('question_tests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_question_tests_question_id'))
    op.drop_table('question_tests')
