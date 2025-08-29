"""add challenges, questions, question_attempts, challenge_attempts

Revision ID: a1b2c3d4e5f6
Revises: c4af184fbf4e
Create Date: 2025-08-15 00:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c4af184fbf4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Challenges table
    op.create_table(
        'challenges',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('total_points', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('challenges') as batch_op:
        batch_op.create_index(batch_op.f('ix_challenges_title'), ['title'], unique=False)

    # Questions table
    op.create_table(
        'questions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('challenge_id', sa.UUID(), nullable=False),
        sa.Column('language_id', sa.Integer(), nullable=False),
        sa.Column('expected_output', sa.Text(), nullable=True),
        sa.Column('points', sa.Integer(), server_default='0', nullable=False),
        sa.Column('starter_code', sa.Text(), nullable=True),
        sa.Column('max_time_ms', sa.Integer(), nullable=True),
        sa.Column('max_memory_kb', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('questions') as batch_op:
        batch_op.create_index(batch_op.f('ix_questions_challenge_id'), ['challenge_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_questions_language_id'), ['language_id'], unique=False)

    # Question attempts table
    op.create_table(
        'question_attempts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('challenge_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('judge0_token', sa.String(length=255), nullable=True),
        sa.Column('source_code', sa.Text(), nullable=False),
        sa.Column('stdout', sa.Text(), nullable=True),
        sa.Column('stderr', sa.Text(), nullable=True),
        sa.Column('status_id', sa.Integer(), nullable=False),
        sa.Column('status_description', sa.String(length=255), nullable=False),
        sa.Column('time', sa.String(length=50), nullable=True),
        sa.Column('memory', sa.Integer(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('question_attempts') as batch_op:
        batch_op.create_index(batch_op.f('ix_question_attempts_question_id'), ['question_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_question_attempts_challenge_id'), ['challenge_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_question_attempts_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_question_attempts_is_correct'), ['is_correct'], unique=False)
        batch_op.create_index(batch_op.f('ix_question_attempts_token'), ['judge0_token'], unique=False)

    # Challenge attempts table
    op.create_table(
        'challenge_attempts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('challenge_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('score', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_correct', sa.Integer(), server_default='0', nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('challenge_attempts') as batch_op:
        batch_op.create_index(batch_op.f('ix_challenge_attempts_challenge_id'), ['challenge_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_challenge_attempts_user_id'), ['user_id'], unique=False)
        batch_op.create_unique_constraint('uq_challenge_attempts_challenge_user', ['challenge_id', 'user_id'])


def downgrade() -> None:
    with op.batch_alter_table('challenge_attempts') as batch_op:
        batch_op.drop_constraint('uq_challenge_attempts_challenge_user', type_='unique')
        batch_op.drop_index(batch_op.f('ix_challenge_attempts_user_id'))
        batch_op.drop_index(batch_op.f('ix_challenge_attempts_challenge_id'))
    op.drop_table('challenge_attempts')

    with op.batch_alter_table('question_attempts') as batch_op:
        batch_op.drop_index(batch_op.f('ix_question_attempts_token'))
        batch_op.drop_index(batch_op.f('ix_question_attempts_is_correct'))
        batch_op.drop_index(batch_op.f('ix_question_attempts_user_id'))
        batch_op.drop_index(batch_op.f('ix_question_attempts_challenge_id'))
        batch_op.drop_index(batch_op.f('ix_question_attempts_question_id'))
    op.drop_table('question_attempts')

    with op.batch_alter_table('questions') as batch_op:
        batch_op.drop_index(batch_op.f('ix_questions_language_id'))
        batch_op.drop_index(batch_op.f('ix_questions_challenge_id'))
    op.drop_table('questions')

    with op.batch_alter_table('challenges') as batch_op:
        batch_op.drop_index(batch_op.f('ix_challenges_title'))
    op.drop_table('challenges')
