-- ============================================================================
-- SIMPLE FIX FOR elo_events TABLE - RUN THIS IN SUPABASE SQL EDITOR
-- ============================================================================
-- This adds ALL missing columns to elo_events table

-- Add student_id column
ALTER TABLE public.elo_events 
ADD COLUMN IF NOT EXISTS student_id integer;

-- Add elo_change column  
ALTER TABLE public.elo_events 
ADD COLUMN IF NOT EXISTS elo_change integer DEFAULT 0;

-- Add elo_before column
ALTER TABLE public.elo_events 
ADD COLUMN IF NOT EXISTS elo_before integer;

-- Add elo_after column
ALTER TABLE public.elo_events 
ADD COLUMN IF NOT EXISTS elo_after integer;

-- Add event_type column
ALTER TABLE public.elo_events 
ADD COLUMN IF NOT EXISTS event_type varchar(50) DEFAULT 'challenge_completion';

-- Add module_code column for linking to modules
ALTER TABLE public.elo_events 
ADD COLUMN IF NOT EXISTS module_code varchar(50);

-- Add semester_id column for linking to semesters
ALTER TABLE public.elo_events 
ADD COLUMN IF NOT EXISTS semester_id uuid;

-- Add challenge_attempt_id column
ALTER TABLE public.elo_events 
ADD COLUMN IF NOT EXISTS challenge_attempt_id uuid;

-- Add user_id for UUID compatibility
ALTER TABLE public.elo_events 
ADD COLUMN IF NOT EXISTS user_id uuid;

-- Add semester date tracking
ALTER TABLE public.elo_events 
ADD COLUMN IF NOT EXISTS semester_start date;

ALTER TABLE public.elo_events 
ADD COLUMN IF NOT EXISTS semester_end date;

-- Add created_at timestamp
ALTER TABLE public.elo_events 
ADD COLUMN IF NOT EXISTS created_at timestamp with time zone DEFAULT now();

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_elo_events_student_id ON public.elo_events(student_id);
CREATE INDEX IF NOT EXISTS idx_elo_events_module_code ON public.elo_events(module_code);
CREATE INDEX IF NOT EXISTS idx_elo_events_semester_id ON public.elo_events(semester_id);
CREATE INDEX IF NOT EXISTS idx_elo_events_challenge_attempt ON public.elo_events(challenge_attempt_id);

-- Show success message
DO $$ 
BEGIN
    RAISE NOTICE '✅ Successfully added all columns to elo_events table!';
END $$;

-- Verify columns exist
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_schema = 'public' 
  AND table_name = 'elo_events'
ORDER BY column_name;
