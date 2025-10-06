-- Supabase Schema Fixes for Achievement System
-- Run this in Supabase SQL Editor to fix schema mismatches

-- ============================================
-- 1. FIX USER_BADGE/USER_BADGES TABLE
-- ============================================

-- Check if user_badge exists and needs fixing
DO $$ 
BEGIN
  -- Add user_id column if table exists but column is missing
  IF EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name = 'user_badge'
  ) THEN
    -- Add user_id if missing
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns 
      WHERE table_name = 'user_badge' AND column_name = 'user_id'
    ) THEN
      ALTER TABLE public.user_badge ADD COLUMN user_id UUID;
      RAISE NOTICE 'Added user_id column to user_badge table';
    END IF;
    
    -- Optionally rename to user_badges for consistency
    -- Uncomment the next line if you want to rename the table
    -- ALTER TABLE public.user_badge RENAME TO user_badges;
  END IF;
  
  -- Create user_badges table if it doesn't exist at all
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name IN ('user_badge', 'user_badges')
  ) THEN
    CREATE TABLE public.user_badges (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id UUID NOT NULL,
      badge_id UUID NOT NULL,
      challenge_id UUID,
      challenge_attempt_id UUID,
      source_submission_id UUID,
      date_earned TIMESTAMPTZ DEFAULT NOW(),
      awarded_at TIMESTAMPTZ DEFAULT NOW(),
      created_at TIMESTAMPTZ DEFAULT NOW(),
      CONSTRAINT unique_user_badge_challenge UNIQUE(user_id, badge_id, challenge_id)
    );
    
    -- Add index for performance
    CREATE INDEX idx_user_badges_user_id ON public.user_badges(user_id);
    CREATE INDEX idx_user_badges_badge_id ON public.user_badges(badge_id);
    
    RAISE NOTICE 'Created user_badges table';
  END IF;
END $$;

-- ============================================
-- 2. FIX USER_ELO TABLE
-- ============================================

-- Add missing columns to user_elo
ALTER TABLE public.user_elo 
  ADD COLUMN IF NOT EXISTS user_id UUID,
  ADD COLUMN IF NOT EXISTS elo_points INTEGER DEFAULT 1200,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_elo_user_id ON public.user_elo(user_id);

-- Add comment
COMMENT ON COLUMN public.user_elo.elo_points IS 'Current ELO rating for the user';
COMMENT ON COLUMN public.user_elo.user_id IS 'Reference to auth.users';

-- ============================================
-- 3. CREATE ELO_EVENTS TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS public.elo_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  event_type VARCHAR(50) NOT NULL,
  elo_change INTEGER NOT NULL DEFAULT 0,
  elo_before INTEGER NOT NULL,
  elo_after INTEGER NOT NULL,
  challenge_id UUID,
  attempt_id UUID,
  submission_id UUID,
  question_id UUID,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_elo_events_user_id ON public.elo_events(user_id);
CREATE INDEX IF NOT EXISTS idx_elo_events_challenge_id ON public.elo_events(challenge_id);
CREATE INDEX IF NOT EXISTS idx_elo_events_created_at ON public.elo_events(created_at DESC);

-- Add comments
COMMENT ON TABLE public.elo_events IS 'Historical log of ELO rating changes';
COMMENT ON COLUMN public.elo_events.event_type IS 'Type of event: challenge_complete, question_submit, etc.';

-- ============================================
-- 4. VERIFICATION QUERY
-- ============================================

-- Check user_badge/user_badges schema
SELECT 
  table_name,
  column_name,
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
  AND table_name IN ('user_badge', 'user_badges')
ORDER BY table_name, ordinal_position;

-- Check user_elo schema
SELECT 
  column_name,
  data_type,
  is_nullable,
  column_default
FROM information_schema.columns
WHERE table_schema = 'public' 
  AND table_name = 'user_elo'
ORDER BY ordinal_position;

-- Check elo_events schema
SELECT 
  column_name,
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
  AND table_name = 'elo_events'
ORDER BY ordinal_position;

-- ============================================
-- 5. OPTIONAL: ADD FOREIGN KEY CONSTRAINTS
-- ============================================

-- Uncomment these if you want to enforce referential integrity
-- Note: This requires that referenced tables exist

/*
-- Add foreign key for user_badges
ALTER TABLE public.user_badges
  ADD CONSTRAINT fk_user_badges_user_id 
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_user_badges_badge_id 
  FOREIGN KEY (badge_id) REFERENCES public.badges(id) ON DELETE CASCADE;

-- Add foreign key for user_elo
ALTER TABLE public.user_elo
  ADD CONSTRAINT fk_user_elo_user_id 
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

-- Add foreign key for elo_events
ALTER TABLE public.elo_events
  ADD CONSTRAINT fk_elo_events_user_id 
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
*/

-- ============================================
-- 6. GRANT PERMISSIONS
-- ============================================

-- Grant access to authenticated users (adjust as needed)
GRANT SELECT, INSERT, UPDATE ON public.user_badges TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.user_elo TO authenticated;
GRANT SELECT, INSERT ON public.elo_events TO authenticated;

-- Grant access to service role
GRANT ALL ON public.user_badges TO service_role;
GRANT ALL ON public.user_elo TO service_role;
GRANT ALL ON public.elo_events TO service_role;

-- ============================================
-- DONE!
-- ============================================

-- Display success message
DO $$ 
BEGIN
  RAISE NOTICE '✅ Schema fixes applied successfully!';
  RAISE NOTICE 'Tables updated: user_badges, user_elo, elo_events';
  RAISE NOTICE 'Run verification queries above to confirm changes';
END $$;
