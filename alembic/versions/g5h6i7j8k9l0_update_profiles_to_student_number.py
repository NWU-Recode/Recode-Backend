"""Update profiles to use student number as primary key

Revision ID: g5h6i7j8k9l0
Revises: f4a5b6c7d8e9
Create Date: 2025-08-28 22:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'g5h6i7j8k9l0'
down_revision: Union[str, Sequence[str], None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Create a temporary column for the new integer ID
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('temp_id', sa.Integer(), nullable=True))
    
    # Step 2: Drop foreign key constraints that reference profiles.id
    op.drop_constraint('challenge_attempts_user_id_fkey', 'challenge_attempts', type_='foreignkey')
    op.drop_constraint('question_attempts_user_id_fkey', 'question_attempts', type_='foreignkey')
    op.drop_constraint('code_submissions_user_id_fkey', 'code_submissions', type_='foreignkey')
    
    # Check if challenges table has lecturer_creator column referencing profiles
    try:
        op.drop_constraint('challenges_lecturer_creator_fkey', 'challenges', type_='foreignkey')
    except:
        # Constraint might not exist or have different name
        pass
    
    # Step 3: Drop the old primary key and constraints on profiles
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.drop_constraint('users_pkey', type_='primary')
        batch_op.drop_constraint('profiles_supabase_id_key', type_='unique')
        batch_op.drop_constraint('profiles_supabase_id_fkey', type_='foreignkey')
    
    # Step 4: Drop the old id column
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.drop_column('id')
    
    # Step 5: Rename temp_id to id and make it primary key with constraint
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.alter_column('temp_id', new_column_name='id', nullable=False)
        batch_op.create_primary_key('users_pkey', ['id'])
        batch_op.create_check_constraint(
            'check_student_number_8_digits',
            'id >= 10000000 AND id <= 99999999'
        )
    
    # Step 6: Update foreign key columns to Integer type
    with op.batch_alter_table('challenge_attempts', schema=None) as batch_op:
        batch_op.alter_column('user_id',
               existing_type=sa.UUID(),
               type_=sa.Integer(),
               existing_nullable=False)
    
    with op.batch_alter_table('question_attempts', schema=None) as batch_op:
        batch_op.alter_column('user_id',
               existing_type=sa.UUID(),
               type_=sa.Integer(),
               existing_nullable=False)
    
    with op.batch_alter_table('code_submissions', schema=None) as batch_op:
        batch_op.alter_column('user_id',
               existing_type=sa.UUID(),
               type_=sa.Integer(),
               existing_nullable=False)
    
    # Update challenges table if it has lecturer_creator
    try:
        with op.batch_alter_table('challenges', schema=None) as batch_op:
            batch_op.alter_column('lecturer_creator',
                   existing_type=sa.UUID(),
                   type_=sa.Integer(),
                   existing_nullable=False)
    except:
        # Column might not exist
        pass
    
    # Step 7: Recreate foreign key constraints
    op.create_foreign_key('challenge_attempts_user_id_fkey', 'challenge_attempts', 'profiles', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('question_attempts_user_id_fkey', 'question_attempts', 'profiles', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('code_submissions_user_id_fkey', 'code_submissions', 'profiles', ['user_id'], ['id'], ondelete='CASCADE')
    
    try:
        op.create_foreign_key('challenges_lecturer_creator_fkey', 'challenges', 'profiles', ['lecturer_creator'], ['id'], ondelete='CASCADE')
    except:
        # Column might not exist
        pass


def downgrade() -> None:
    """Downgrade schema."""
    # This is a destructive migration - downgrade would lose data
    # For safety, we'll just raise an error
    raise NotImplementedError("This migration cannot be safely downgraded as it would lose data")
