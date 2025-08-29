"""rename users table to profiles

Revision ID: d2f3e4c5b6a7
Revises: 1ca7f15eca6b
Create Date: 2025-08-17 18:05:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd2f3e4c5b6a7'
down_revision: Union[str, Sequence[str], None] = '1ca7f15eca6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Rename table users -> profiles
    op.rename_table('users', 'profiles')
    # Rename indexes (Alembic doesn't auto-rename)
    with op.batch_alter_table('profiles') as batch_op:
        batch_op.drop_index('ix_users_email')
        batch_op.drop_index('ix_users_role')
        batch_op.drop_index('ix_users_supabase_id')
        batch_op.create_index('ix_profiles_email', ['email'], unique=True)
        batch_op.create_index('ix_profiles_role', ['role'], unique=False)
        batch_op.create_index('ix_profiles_supabase_id', ['supabase_id'], unique=True)
    # Update foreign keys referencing users.id (code_submissions, challenge_attempts, question_attempts)
    # Drop and recreate FKs
    with op.batch_alter_table('code_submissions') as batch_op:
        batch_op.drop_constraint('code_submissions_user_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(None, 'profiles', ['user_id'], ['id'], ondelete='CASCADE')
    # Similar adjustments if other tables reference users
    try:
        with op.batch_alter_table('challenge_attempts') as batch_op:
            batch_op.drop_constraint('challenge_attempts_user_id_fkey', type_='foreignkey')
            batch_op.create_foreign_key(None, 'profiles', ['user_id'], ['id'], ondelete='CASCADE')
    except Exception:
        pass
    try:
        with op.batch_alter_table('question_attempts') as batch_op:
            batch_op.drop_constraint('question_attempts_user_id_fkey', type_='foreignkey')
            batch_op.create_foreign_key(None, 'profiles', ['user_id'], ['id'], ondelete='CASCADE')
    except Exception:
        pass

def downgrade() -> None:
    # Revert FK changes
    with op.batch_alter_table('code_submissions') as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key('code_submissions_user_id_fkey', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    for tbl, fkname in [('challenge_attempts','challenge_attempts_user_id_fkey'), ('question_attempts','question_attempts_user_id_fkey')]:
        try:
            with op.batch_alter_table(tbl) as batch_op:
                batch_op.drop_constraint(None, type_='foreignkey')
                batch_op.create_foreign_key(fkname, 'users', ['user_id'], ['id'], ondelete='CASCADE')
        except Exception:
            pass
    # Drop new indexes, recreate old
    with op.batch_alter_table('profiles') as batch_op:
        batch_op.drop_index('ix_profiles_email')
        batch_op.drop_index('ix_profiles_role')
        batch_op.drop_index('ix_profiles_supabase_id')
        batch_op.create_index('ix_users_email', ['email'], unique=True)
        batch_op.create_index('ix_users_role', ['role'], unique=False)
        batch_op.create_index('ix_users_supabase_id', ['supabase_id'], unique=True)
    # Rename table back
    op.rename_table('profiles', 'users')
