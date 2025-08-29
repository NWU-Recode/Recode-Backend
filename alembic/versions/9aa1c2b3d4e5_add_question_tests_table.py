"""add question_tests table

Revision ID: 9aa1c2b3d4e5
Revises: 1ca7f15eca6b
Create Date: 2025-08-29 04:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9aa1c2b3d4e5'
down_revision: Union[str, Sequence[str], None] = '1ca7f15eca6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    visibility_enum = sa.Enum('public', 'hidden', name='questiontestvisibility')
    visibility_enum.create(bind, checkfirst=True)

    op.create_table(
        'question_tests',
        sa.Column('id', sa.UUID(), primary_key=True, nullable=False),
        sa.Column('question_id', sa.UUID(), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('input', sa.Text(), nullable=False),
        sa.Column('expected', sa.Text(), nullable=False),
        sa.Column('visibility', visibility_enum, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    with op.batch_alter_table('question_tests') as batch_op:
        batch_op.create_index(batch_op.f('ix_question_tests_question_id'), ['question_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_question_tests_visibility'), ['visibility'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('question_tests') as batch_op:
        batch_op.drop_index(batch_op.f('ix_question_tests_visibility'))
        batch_op.drop_index(batch_op.f('ix_question_tests_question_id'))
    op.drop_table('question_tests')

    bind = op.get_bind()
    visibility_enum = sa.Enum('public', 'hidden', name='questiontestvisibility')
    visibility_enum.drop(bind, checkfirst=True)

