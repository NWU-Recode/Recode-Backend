"""add topics table; extend challenges; add questions.valid

Revision ID: aa01bb02cc03
Revises: 9aa1c2b3d4e5
Create Date: 2025-08-29 04:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'aa01bb02cc03'
down_revision: Union[str, Sequence[str], None] = '9aa1c2b3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Create topics (singular 'topic' to match SQLAlchemy model)
    op.create_table(
        'topic',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        # extra column for convenience (not in model but harmless)
        sa.Column('subtopics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    with op.batch_alter_table('topic') as batch_op:
        batch_op.create_index(batch_op.f('ix_topic_slug'), ['slug'], unique=True)
        batch_op.create_index(batch_op.f('ix_topic_week'), ['week'], unique=False)

    # Challenge enums (kind, status)
    challengekind = sa.Enum('common', 'ruby', 'emerald', 'diamond', name='challengekind')
    challengestatus = sa.Enum('draft', 'published', name='challengestatus')
    challengekind.create(bind, checkfirst=True)
    challengestatus.create(bind, checkfirst=True)

    # Extend challenges table with new columns commonly used in services
    with op.batch_alter_table('challenges') as batch_op:
        if not hasattr(sa, 'does_not_exist'):
            batch_op.add_column(sa.Column('slug', sa.String(), nullable=True))
            batch_op.add_column(sa.Column('kind', challengekind, nullable=True))
            batch_op.add_column(sa.Column('status', challengestatus, nullable=True))
            batch_op.add_column(sa.Column('topic_id', sa.Integer(), nullable=True))
            # Best-effort unique index on slug
            batch_op.create_index(batch_op.f('ix_challenges_slug'), ['slug'], unique=True)
            # Foreign key to topic
            batch_op.create_foreign_key(None, 'topic', ['topic_id'], ['id'])

    # Add questions.valid flag (used after validation)
    with op.batch_alter_table('questions') as batch_op:
        batch_op.add_column(sa.Column('valid', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    bind = op.get_bind()
    challengekind = sa.Enum('common', 'ruby', 'emerald', 'diamond', name='challengekind')
    challengestatus = sa.Enum('draft', 'published', name='challengestatus')

    # Revert questions
    with op.batch_alter_table('questions') as batch_op:
        batch_op.drop_column('valid')

    # Revert challenges columns
    with op.batch_alter_table('challenges') as batch_op:
        try:
            batch_op.drop_constraint(None, type_='foreignkey')
        except Exception:
            pass
        try:
            batch_op.drop_index(batch_op.f('ix_challenges_slug'))
        except Exception:
            pass
        try:
            batch_op.drop_column('topic_id')
        except Exception:
            pass
        for col in ('status', 'kind', 'slug'):
            try:
                batch_op.drop_column(col)
            except Exception:
                pass

    # Drop enums
    try:
        challengestatus.drop(bind, checkfirst=True)
    except Exception:
        pass
    try:
        challengekind.drop(bind, checkfirst=True)
    except Exception:
        pass

    # Drop topic table
    with op.batch_alter_table('topic') as batch_op:
        try:
            batch_op.drop_index(batch_op.f('ix_topic_week'))
            batch_op.drop_index(batch_op.f('ix_topic_slug'))
        except Exception:
            pass
    op.drop_table('topic')

