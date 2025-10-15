"""Add challenge_notifications table and trigger to auto-populate schedules.

Replace down_revision with latest existing revision id if you already have migrations.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20251014_add_challenge_notifications"
down_revision = None  # <-- if you already have migrations, replace with your last revision id
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create schedule table (one row per challenge per notification type)
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.challenge_notifications (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      challenge_id uuid NOT NULL REFERENCES public.challenges(id) ON DELETE CASCADE,
      notification_type text NOT NULL CHECK (notification_type IN ('start', 'end')),
      notification_time timestamptz NOT NULL,
      sent boolean DEFAULT false,
      sent_at timestamptz,
      created_at timestamptz DEFAULT now()
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_challenge_notifications_unique ON public.challenge_notifications(challenge_id, notification_type);
    CREATE INDEX IF NOT EXISTS idx_challenge_notifications_time_sent ON public.challenge_notifications (notification_time, sent);
    """)

    # function + trigger to populate schedule for new/updated challenges
    op.execute("""
    CREATE OR REPLACE FUNCTION populate_challenge_notifications()
    RETURNS TRIGGER AS $$
    BEGIN
      -- compute start notification at release_date (immediate at release)
      INSERT INTO public.challenge_notifications (challenge_id, notification_type, notification_time, created_at, sent)
      VALUES (NEW.id, 'start', NEW.release_date, now(), false)
      ON CONFLICT (challenge_id, notification_type) DO UPDATE
      SET notification_time = EXCLUDED.notification_time, created_at = now(), sent = false;

      -- compute end notification at due_date - 24 hours
      INSERT INTO public.challenge_notifications (challenge_id, notification_type, notification_time, created_at, sent)
      VALUES (NEW.id, 'end', NEW.due_date - interval '24 hours', now(), false)
      ON CONFLICT (challenge_id, notification_type) DO UPDATE
      SET notification_time = EXCLUDED.notification_time, created_at = now(), sent = false;

      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    DROP TRIGGER IF EXISTS trg_challenge_notifications ON public.challenges;
    CREATE TRIGGER trg_challenge_notifications
    AFTER INSERT OR UPDATE ON public.challenges
    FOR EACH ROW
    EXECUTE FUNCTION populate_challenge_notifications();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_challenge_notifications ON public.challenges;")
    op.execute("DROP FUNCTION IF EXISTS populate_challenge_notifications;")
    op.execute("DROP TABLE IF EXISTS public.challenge_notifications;")
