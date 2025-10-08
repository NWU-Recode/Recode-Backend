# TESTING GUIDE: Database Persistence After Submission

# ====================================================

## Step 1: Get Your Auth Token

First, you need a valid JWT token. If you don't have one, create a test user:

```powershell
# Create or get a test student (student_id: 12345678)
curl -X POST http://127.0.0.1:8000/api/auth/register `
  -H "Content-Type: application/json" `
  -d '{"student_number": 12345678, "email": "test@student.com", "password": "Test123!", "first_name": "Test", "last_name": "Student"}'

# Login to get token
curl -X POST http://127.0.0.1:8000/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{"student_number": 12345678, "password": "Test123!"}'
```

Save the "access_token" from the response!

## Step 2: Submit the Challenge

Replace `YOUR_TOKEN_HERE` with your actual token:

```powershell
curl -X POST 'http://127.0.0.1:8000/submissions/challenges/6e957ff3-13fc-48e7-9622-b86b43f2d0b5/submit-challenge' `
  -H 'Content-Type: application/json' `
  -H 'Authorization: Bearer YOUR_TOKEN_HERE' `
  -d '@CORRECT_submission_payload.json'
```

## Step 3: Check the Logs

The server logs will now show:

```
🎯 STARTING ACHIEVEMENT PROCESSING for student 12345678
   ELO Delta: XX, Badge Tiers: [...]
🏆 check_achievements CALLED for user 12345678, submission xxx
   Loaded attempt summary: tier=base, badges=[...]
   ELO: 1000 + XX = 1050, GPA: 3.5
   Calling update_user_elo...
   ✅ update_user_elo completed
   Calling _maybe_log_elo_event...
📝 Updating question_progress for Q:6363385e
   ✅ Question progress updated
📊 Updating user_scores: attempted=5, passed=3, badges=1
   ✅ user_scores updated successfully
```

## Step 4: Verify Database Tables

Edit `scripts/check_achievement_tables.py` and set your student_id:

```python
STUDENT_ID = "12345678"  # Your actual student number
```

Then run:

```powershell
python scripts/check_achievement_tables.py
```

This will show data from ALL 5 achievement tables:

- user_elo
- elo_events
- user_scores
- user_question_progress
- user_badge

## Common Issues

### ❌ "401 Unauthorized"

- You didn't include the Authorization header
- Your token expired (login again)
- Wrong token format (should be: `Bearer YOUR_TOKEN`)

### ❌ "403 Forbidden"

- User doesn't have "student" role
- Check the profiles table: `SELECT role FROM profiles WHERE id = '12345678'`

### ❌ Tables still empty after submission

- Check server logs for errors in achievement processing
- Verify the user_id in logs matches your student number
- Check if check_achievements was called (look for 🏆 emoji)

### ❌ "missing_questions" in response

- Challenge has no test cases (we fixed this!)
- Verify with: `SELECT COUNT(*) FROM question_tests WHERE question_id IN (SELECT id FROM questions WHERE challenge_id = '6e957ff3...')`

## Expected Response

If everything works, you'll get a response like:

```json
{
  "result": {
    "challenge_id": "6e957ff3-13fc-48e7-9622-b86b43f2d0b5",
    "gpa_score": 85,
    "gpa_max_score": 100,
    "elo_delta": 25,
    "tests_total": 15,
    "tests_passed_total": 13,
    "passed_questions": ["830d02fc", "1c9b5dbf", "fbb81d33"],
    "failed_questions": ["297db452"],
    "missing_questions": []
  },
  "achievement_summary": {
    "updated_elo": 1025,
    "gpa": 3.4,
    "unlocked_badges": [...]
  }
}
```

## Verification SQL Queries

You can also check directly in Supabase:

```sql
-- Check user_elo
SELECT * FROM user_elo WHERE student_id = '12345678';

-- Check latest elo_event
SELECT * FROM elo_events WHERE student_id = '12345678' ORDER BY created_at DESC LIMIT 1;

-- Check user_scores
SELECT * FROM user_scores WHERE student_id = '12345678';

-- Check question progress (last 5)
SELECT * FROM user_question_progress WHERE profile_id = '12345678' ORDER BY created_at DESC LIMIT 5;

-- Check badges
SELECT * FROM user_badge WHERE profile_id = '12345678';
```
