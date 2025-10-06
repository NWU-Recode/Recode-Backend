-- ============================================================================
-- COMPREHENSIVE FIX FOR user_elo, user_badge, and elo_events TABLES
-- ============================================================================
-- Run this in Supabase SQL Editor
-- This will fix all column issues for GPA/ELO/badge persistence

-- ============================================================================
-- FIX 1: user_elo table
-- ============================================================================
-- First, let's see what columns exist
DO $$ 
BEGIN
    RAISE NOTICE 'Checking user_elo table structure...';
END $$;

-- Option A: If table uses user_id (UUID)
-- Add profile_id column and populate it
DO $$ 
BEGIN
    -- Add profile_id if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user_elo' 
        AND column_name = 'profile_id'
    ) THEN
        ALTER TABLE public.user_elo 
        ADD COLUMN profile_id integer;
        
        RAISE NOTICE 'Added profile_id column to user_elo';
        
        -- Try to populate from user_id if it exists
        -- Check the data type of user_id
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'user_elo' 
            AND column_name = 'user_id'
            AND data_type = 'uuid'
        ) THEN
            -- user_id is UUID pointing to auth.users
            -- Since we can't directly cast UUID to integer, we'll leave it NULL
            -- The application code will need to populate this when records are created/updated
            RAISE NOTICE 'user_id is UUID - profile_id will need to be populated by application code';
            
        ELSIF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'user_elo' 
            AND column_name = 'user_id'
            AND (data_type = 'integer' OR data_type = 'bigint')
        ) THEN
            -- user_id is already an integer (profile_id)
            UPDATE public.user_elo
            SET profile_id = user_id
            WHERE profile_id IS NULL;
            
            RAISE NOTICE 'Populated profile_id from integer user_id';
        END IF;
    END IF;
    
    -- Add elo_points column if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user_elo' 
        AND column_name = 'elo_points'
    ) THEN
        ALTER TABLE public.user_elo 
        ADD COLUMN elo_points integer DEFAULT 1500;
        
        RAISE NOTICE 'Added elo_points column to user_elo';
    END IF;
    
    -- Add running_gpa column if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user_elo' 
        AND column_name = 'running_gpa'
    ) THEN
        ALTER TABLE public.user_elo 
        ADD COLUMN running_gpa numeric(5,2) DEFAULT 0.0;
        
        RAISE NOTICE 'Added running_gpa column to user_elo';
    END IF;
    
    -- Add module_code column if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user_elo' 
        AND column_name = 'module_code'
    ) THEN
        ALTER TABLE public.user_elo 
        ADD COLUMN module_code varchar(50);
        
        RAISE NOTICE 'Added module_code column to user_elo';
    END IF;
    
    -- Add created_at if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user_elo' 
        AND column_name = 'created_at'
    ) THEN
        ALTER TABLE public.user_elo 
        ADD COLUMN created_at timestamp with time zone DEFAULT now();
        
        RAISE NOTICE 'Added created_at column to user_elo';
    END IF;
    
    -- Add updated_at if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user_elo' 
        AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE public.user_elo 
        ADD COLUMN updated_at timestamp with time zone DEFAULT now();
        
        RAISE NOTICE 'Added updated_at column to user_elo';
    END IF;
    
END $$;

-- ============================================================================
-- FIX 2: user_badge table
-- ============================================================================

DO $$ 
BEGIN
    -- Remove user_id if it exists (we use profile_id)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user_badge' 
        AND column_name = 'user_id'
    ) THEN
        -- First, populate profile_id from user_id if profile_id is null
        -- Check data type of user_id
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'user_badge' 
            AND column_name = 'user_id'
            AND data_type = 'uuid'
        ) THEN
            -- user_id is UUID, cannot convert to integer profile_id
            -- Leave it NULL, application will populate it
            RAISE NOTICE 'user_id is UUID in user_badge - profile_id left NULL, will be populated by app';
            
        ELSIF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'user_badge' 
            AND column_name = 'user_id'
            AND (data_type = 'integer' OR data_type = 'bigint')
        ) THEN
            -- user_id is integer
            UPDATE public.user_badge
            SET profile_id = user_id
            WHERE profile_id IS NULL;
            
            RAISE NOTICE 'Populated profile_id from integer user_id in user_badge';
        END IF;
        
        -- Then drop the column
        ALTER TABLE public.user_badge DROP COLUMN user_id;
        
        RAISE NOTICE 'Removed user_id column from user_badge';
    END IF;
    
    -- Rename awarded_at to date_earned if needed
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user_badge' 
        AND column_name = 'awarded_at'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user_badge' 
        AND column_name = 'date_earned'
    ) THEN
        ALTER TABLE public.user_badge 
        RENAME COLUMN awarded_at TO date_earned;
        
        RAISE NOTICE 'Renamed awarded_at to date_earned in user_badge';
    END IF;
    
    -- Add date_earned if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'user_badge' 
        AND column_name = 'date_earned'
    ) THEN
        ALTER TABLE public.user_badge 
        ADD COLUMN date_earned timestamp with time zone DEFAULT now();
        
        RAISE NOTICE 'Added date_earned column to user_badge';
    END IF;
    
END $$;

-- ============================================================================
-- FIX 3: elo_events table
-- ============================================================================

DO $$ 
BEGIN
    -- Add challenge_attempt_id if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'elo_events' 
        AND column_name = 'challenge_attempt_id'
    ) THEN
        ALTER TABLE public.elo_events 
        ADD COLUMN challenge_attempt_id uuid;
        
        -- Add foreign key if challenge_attempts table exists
        IF EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'challenge_attempts'
        ) THEN
            ALTER TABLE public.elo_events 
            ADD CONSTRAINT fk_elo_events_challenge_attempt 
            FOREIGN KEY (challenge_attempt_id) 
            REFERENCES challenge_attempts(id) 
            ON DELETE CASCADE;
        END IF;
        
        RAISE NOTICE 'Added challenge_attempt_id column to elo_events';
    END IF;
    
    -- Ensure other key columns exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'elo_events' 
        AND column_name = 'user_id'
    ) THEN
        ALTER TABLE public.elo_events 
        ADD COLUMN user_id integer;
        
        RAISE NOTICE 'Added user_id column to elo_events';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'elo_events' 
        AND column_name = 'event_type'
    ) THEN
        ALTER TABLE public.elo_events 
        ADD COLUMN event_type varchar(50);
        
        RAISE NOTICE 'Added event_type column to elo_events';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'elo_events' 
        AND column_name = 'elo_change'
    ) THEN
        ALTER TABLE public.elo_events 
        ADD COLUMN elo_change integer DEFAULT 0;
        
        RAISE NOTICE 'Added elo_change column to elo_events';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'elo_events' 
        AND column_name = 'elo_before'
    ) THEN
        ALTER TABLE public.elo_events 
        ADD COLUMN elo_before integer;
        
        RAISE NOTICE 'Added elo_before column to elo_events';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'elo_events' 
        AND column_name = 'elo_after'
    ) THEN
        ALTER TABLE public.elo_events 
        ADD COLUMN elo_after integer;
        
        RAISE NOTICE 'Added elo_after column to elo_events';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'elo_events' 
        AND column_name = 'created_at'
    ) THEN
        ALTER TABLE public.elo_events 
        ADD COLUMN created_at timestamp with time zone DEFAULT now();
        
        RAISE NOTICE 'Added created_at column to elo_events';
    END IF;
    
END $$;

-- ============================================================================
-- CREATE INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_user_elo_profile_id 
ON public.user_elo(profile_id);

CREATE INDEX IF NOT EXISTS idx_user_badge_profile_id 
ON public.user_badge(profile_id);

CREATE INDEX IF NOT EXISTS idx_user_badge_badge_id 
ON public.user_badge(badge_id);

CREATE INDEX IF NOT EXISTS idx_elo_events_user_id 
ON public.elo_events(user_id);

CREATE INDEX IF NOT EXISTS idx_elo_events_challenge_attempt_id 
ON public.elo_events(challenge_attempt_id);

-- ============================================================================
-- VERIFY FINAL STRUCTURE
-- ============================================================================

-- Show user_elo columns
SELECT 'user_elo columns:' as info;
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_schema = 'public' AND table_name = 'user_elo'
ORDER BY ordinal_position;

-- Show user_badge columns
SELECT 'user_badge columns:' as info;
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_schema = 'public' AND table_name = 'user_badge'
ORDER BY ordinal_position;

-- Show elo_events columns
SELECT 'elo_events columns:' as info;
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_schema = 'public' AND table_name = 'elo_events'
ORDER BY ordinal_position;
