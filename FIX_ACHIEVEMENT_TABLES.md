# Fix Achievement Tables - Instructions

## Problem

The `user_elo`, `user_badge`, and `elo_events` tables are missing columns needed for GPA/ELO/badge persistence.

## Solution

### Step 1: Run the SQL Migration

1. Open **Supabase Dashboard** → **SQL Editor**
2. Copy and paste the contents of `fix_achievement_tables.sql`
3. Click **Run**
4. Check for success messages

### Step 2: Verify the Tables

The migration will output the final structure of all three tables. You should see:

**user_elo columns:**

- `id` (primary key)
- `profile_id` (integer) ← ADDED
- `elo_points` (integer) ← ADDED
- `running_gpa` (numeric) ← ADDED
- `module_code` (varchar) ← ADDED
- `created_at` (timestamp)
- `updated_at` (timestamp)

**user_badge columns:**

- `id` (primary key)
- `profile_id` (integer)
- `badge_id` (uuid)
- `date_earned` (timestamp) ← RENAMED from awarded_at
- `question_id` (uuid)
- ❌ `user_id` ← REMOVED (duplicate of profile_id)

**elo_events columns:**

- `id` (primary key)
- `user_id` (integer)
- `event_type` (varchar)
- `elo_change` (integer)
- `elo_before` (integer)
- `elo_after` (integer)
- `challenge_id` (uuid)
- `attempt_id` (uuid)
- `challenge_attempt_id` (uuid) ← ADDED
- `submission_id` (uuid)
- `question_id` (uuid)
- `metadata` (jsonb)
- `created_at` (timestamp)

### Step 3: Restart Your Server

After running the migration, restart your FastAPI server to pick up the changes.

## What This Fixes

✅ GPA tracking in `user_elo.running_gpa`
✅ ELO points storage in `user_elo.elo_points`
✅ Badge awards linked to attempts via `elo_events.challenge_attempt_id`
✅ Proper profile_id references throughout
✅ Performance indexes on all foreign keys

## Testing

After migration, test a batch submission:

```bash
python test_batch_db_insert.py
```

Then check the database:

```sql
SELECT * FROM user_elo WHERE profile_id = 10000001;
SELECT * FROM elo_events WHERE user_id = 10000001;
SELECT * FROM user_badge WHERE profile_id = 10000001;
```
