# Supabase Schema Fixes Required

## Issues Identified

The following schema mismatches are causing errors (but not blocking functionality):

### 1. User Badges Table

**Error**: `Could not find the table 'public.user_badges' in the schema cache`
**Hint**: Perhaps you meant the table 'public.user_badge'

**Problem**: Code expects `user_badges` but table is named `user_badge`

**Additional Error**: `column user_badge.user_id does not exist`
**Problem**: The `user_badge` table doesn't have a `user_id` column

**Solution**: Either:

- **Option A**: Rename `user_badge` → `user_badges` and add `user_id` column
- **Option B**: Update code to only use `user_badge` with correct column name

### 2. User ELO Table

**Error**: `Could not find the 'elo_points' column of 'user_elo' in the schema cache`
**Problem**: The `user_elo` table is missing the `elo_points` column

**Additional Error**: `column user_elo.user_id does not exist`
**Problem**: The `user_elo` table doesn't have a `user_id` column

**Solution**: Add missing columns to `user_elo` table:

```sql
ALTER TABLE user_elo
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id),
  ADD COLUMN IF NOT EXISTS elo_points INTEGER DEFAULT 1200;
```

### 3. ELO Events Table

**Error**: `Could not find the table 'public.elo_events' in the schema cache`
**Hint**: Perhaps you meant the table 'public.enrolments'

**Problem**: The `elo_events` table doesn't exist

**Solution**: Create the table:

```sql
CREATE TABLE IF NOT EXISTS public.elo_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  event_type VARCHAR(50),
  elo_change INTEGER,
  challenge_id UUID,
  attempt_id UUID,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Quick Fix SQL Script

Run this in Supabase SQL Editor:

```sql
-- 1. Fix user_badge table (if it exists)
DO $$
BEGIN
  -- Add user_id column if missing
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_badge') THEN
    ALTER TABLE user_badge ADD COLUMN IF NOT EXISTS user_id UUID;
    -- Or rename to user_badges
    -- ALTER TABLE user_badge RENAME TO user_badges;
  END IF;
END $$;

-- 2. Fix user_elo table
ALTER TABLE user_elo
  ADD COLUMN IF NOT EXISTS user_id UUID,
  ADD COLUMN IF NOT EXISTS elo_points INTEGER DEFAULT 1200;

-- 3. Create elo_events table if missing
CREATE TABLE IF NOT EXISTS public.elo_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  event_type VARCHAR(50),
  elo_change INTEGER,
  elo_before INTEGER,
  elo_after INTEGER,
  challenge_id UUID,
  attempt_id UUID,
  submission_id UUID,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Verify schema
SELECT
  'user_badge' as table_name,
  column_name,
  data_type
FROM information_schema.columns
WHERE table_name IN ('user_badge', 'user_badges')
ORDER BY table_name, ordinal_position;

SELECT
  'user_elo' as table_name,
  column_name,
  data_type
FROM information_schema.columns
WHERE table_name = 'user_elo'
ORDER BY ordinal_position;
```

## Expected Schema After Fixes

### user_badges (or user_badge)

```sql
CREATE TABLE user_badges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  badge_id UUID NOT NULL REFERENCES badges(id),
  challenge_id UUID,
  challenge_attempt_id UUID,
  source_submission_id UUID,
  date_earned TIMESTAMPTZ DEFAULT NOW(),
  awarded_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, badge_id, challenge_id)
);
```

### user_elo

```sql
CREATE TABLE user_elo (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  elo_points INTEGER DEFAULT 1200,
  challenge_id UUID,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### elo_events

```sql
CREATE TABLE elo_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  event_type VARCHAR(50),
  elo_change INTEGER,
  elo_before INTEGER,
  elo_after INTEGER,
  challenge_id UUID,
  attempt_id UUID,
  submission_id UUID,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Impact

**Current Status**:

- ⚠️ Warnings logged but requests return 200 OK
- ✅ Core functionality (stdout) works correctly
- ❌ ELO tracking not persisting to database
- ❌ Badge awards not persisting to database
- ❌ Achievement history not being recorded

**After Fixes**:

- ✅ ELO points will be tracked per user
- ✅ Badges will be awarded and stored
- ✅ ELO history will be recorded in elo_events
- ✅ No more schema warnings in logs

## Priority

**Low Priority** - The core batch submission functionality with stdout is working. These schema issues only affect:

- User achievement tracking
- Badge awards
- ELO point persistence

If you're not using these features yet, you can fix them later. If you need achievement tracking, run the SQL fixes above in your Supabase project.

## Verification

After running the fixes, test with:

```powershell
# The warnings should disappear from the logs
$body = @'
{
  "submissions": {
    "388a2b21-bab3-44a0-bd02-907adeebf686": {
      "source_code": "print(2)",
      "language_id": 71
    }
  }
}
'@

$headers = @{ "Authorization" = "Bearer YOUR_TOKEN" }
Invoke-RestMethod -Uri "http://127.0.0.1:8000/submissions/challenges/CHALLENGE_ID/submit-challenge" -Method POST -Headers $headers -Body $body -ContentType "application/json"

# Check logs - should have no schema errors
```

## Alternative: Disable Achievement Tracking

If you don't need achievements/ELO for now, you can temporarily disable them in the code by adding try-except blocks or feature flags.
