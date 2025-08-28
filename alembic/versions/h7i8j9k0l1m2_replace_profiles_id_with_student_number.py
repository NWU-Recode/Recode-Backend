"""Replace profiles id with student number

Revision ID: h7i8j9k0l1m2
Revises: f4a5b6c7d8e9
Create Date: 2025-08-28 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'h7i8j9k0l1m2'
down_revision: Union[str, Sequence[str], None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Add student_number column
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('student_number', sa.Integer(), nullable=True))
    
    # Step 2: Assign temporary sequential student numbers (you'll update to real values in Supabase)
    op.execute("""
        WITH numbered_profiles AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at) as rn
            FROM profiles
        )
        UPDATE profiles 
        SET student_number = 10000000 + np.rn
        FROM numbered_profiles np
        WHERE profiles.id = np.id
    """)
    
    # Step 3: Create a mapping table to store old id -> new student_number relationships
    op.execute("""
        CREATE TEMPORARY TABLE id_mapping AS 
        SELECT id as old_id, student_number as new_id FROM profiles
    """)
    
    # Step 4: Drop foreign key constraints
    op.drop_constraint('challenge_attempts_user_id_fkey', 'challenge_attempts', type_='foreignkey')
    op.drop_constraint('question_attempts_user_id_fkey', 'question_attempts', type_='foreignkey')
    op.drop_constraint('code_submissions_user_id_fkey', 'code_submissions', type_='foreignkey')
    
    # Check if challenges table has lecturer_creator
    try:
        op.drop_constraint('challenges_lecturer_creator_fkey', 'challenges', type_='foreignkey')
    except:
        pass
    
    # Step 5: Update foreign key columns using the mapping
    op.execute("""
        UPDATE challenge_attempts 
        SET user_id = (SELECT new_id::text::uuid FROM id_mapping WHERE old_id = user_id)
    """)
    
    op.execute("""
        UPDATE question_attempts 
        SET user_id = (SELECT new_id::text::uuid FROM id_mapping WHERE old_id = user_id)
    """)
    
    op.execute("""
        UPDATE code_submissions 
        SET user_id = (SELECT new_id::text::uuid FROM id_mapping WHERE old_id = user_id)
    """)
    
    # Update challenges if it exists
    try:
        op.execute("""
            UPDATE challenges 
            SET lecturer_creator = (SELECT new_id::text::uuid FROM id_mapping WHERE old_id = lecturer_creator)
        """)
    except:
        pass
    
    # Step 6: Drop old constraints and id column from profiles
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.drop_constraint('users_pkey', type_='primary')
        batch_op.drop_constraint('profiles_supabase_id_key', type_='unique')
        batch_op.drop_constraint('profiles_supabase_id_fkey', type_='foreignkey')
        batch_op.drop_column('id')
    
    # Step 7: Rename student_number to id and make it primary key
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.alter_column('student_number', new_column_name='id', nullable=False)
        batch_op.create_primary_key('users_pkey', ['id'])
        batch_op.create_check_constraint(
            'check_student_number_8_digits',
            'id >= 10000000 AND id <= 99999999'
        )
    
    # Step 8: Update foreign key column types to Integer using explicit casting
    op.execute("ALTER TABLE challenge_attempts ALTER COLUMN user_id TYPE INTEGER USING user_id::text::integer")
    op.execute("ALTER TABLE question_attempts ALTER COLUMN user_id TYPE INTEGER USING user_id::text::integer") 
    op.execute("ALTER TABLE code_submissions ALTER COLUMN user_id TYPE INTEGER USING user_id::text::integer")
    
    try:
        op.execute("ALTER TABLE challenges ALTER COLUMN lecturer_creator TYPE INTEGER USING lecturer_creator::text::integer")
    except:
        pass
    
    # Step 9: Recreate foreign key constraints
    op.create_foreign_key('challenge_attempts_user_id_fkey', 'challenge_attempts', 'profiles', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('question_attempts_user_id_fkey', 'question_attempts', 'profiles', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('code_submissions_user_id_fkey', 'code_submissions', 'profiles', ['user_id'], ['id'], ondelete='CASCADE')
    
    try:
        op.create_foreign_key('challenges_lecturer_creator_fkey', 'challenges', 'profiles', ['lecturer_creator'], ['id'], ondelete='CASCADE')
    except:
        pass


def downgrade() -> None:
    """Downgrade schema."""
    raise NotImplementedError("This migration cannot be safely downgraded as it would lose data")
