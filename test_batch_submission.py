"""
Test batch submission endpoint with correct payload format
"""
import requests
import json

# Your auth token
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IkhNaUlHZ2I2WnZTblhlS3QiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2d0b2VodmxvZHJtbXF6eXhvYWlsLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI3NTk1N2JmZi04NjAyLTQ0NjMtYmY0Yy02MmVjODUzNmQyY2IiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU5ODc1NTk5LCJpYXQiOjE3NTk4NzE5OTksImVtYWlsIjoiYnJhbmRvbnZhbnZ1dXJlbjdAZ21haWwuY29tIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6eyJlbWFpbCI6ImJyYW5kb252YW52dXVyZW43QGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmdWxsX25hbWUiOiJCcmFuZG9uIFRlc3QiLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInN1YiI6Ijc1OTU3YmZmLTg2MDItNDQ2My1iZjRjLTYyZWM4NTM2ZDJjYiJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6InBhc3N3b3JkIiwidGltZXN0YW1wIjoxNzU5ODcxOTk5fV0sInNlc3Npb25faWQiOiIxNGRlMDhkNi0yMjQ4LTRmZDUtOTM5Mi0wZjM1MDZhNTNiNDYiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.ig7pZw-eiKrt8RrW8rVDfvuZ66XXsZoNkFpedrC7dA0"

CHALLENGE_ID = "b40d7802-4c06-460a-befb-373718608ab4"

# CORRECTED PAYLOAD - Remove "question_" prefix from keys!
payload = {
    "duration_seconds": 306,
    "submissions": {
        "6363385e-ff33-464b-a106-c6a6ae74018e": {
            "language_id": 71,
            "source_code": "# Use example values\nname = \"Alice\"\nage = 20\n# Create the tuple\nstudent = (name, age)\n# Print the tuple\nprint(student)"
        },
        "c672ca99-0355-444b-837f-4834e811d872": {
            "language_id": 71,
            "source_code": "# Use example values\nx = 5\ny = 3\n# Create tuple\npoint = (x, y)\n# Print x and y coordinates\nprint(\"X:\", point[0])\nprint(\"Y:\", point[1])"
        },
        "388a2b21-bab3-44a0-bd02-907adeebf686": {
            "language_id": 71,
            "source_code": "# Use example values\nnumbers = (1, 2, 3, 2, 4)\ntarget = 2\n# Count occurrences of target in the tuple\ncount = numbers.count(target)\n# Print the count\nprint(count)"
        },
        "77bdcd12-700e-4215-bf19-2ff134f1f33d": {
            "language_id": 71,
            "source_code": "# Use example values\nstudents = [\n    (\"Alice\", 85),\n    (\"Bob\", 92),\n    (\"Charlie\", 78)\n]\n# Find the student with the highest score\nhighest_student = max(students, key=lambda s: s[1])\n# Print the name\nprint(highest_student[0])"
        },
        "7070bee5-088c-471c-af8b-9cbeb69ad4e8": {
            "language_id": 71,
            "source_code": "# Use example values\ntemperature_data = [\n    (\"Monday\", 18),\n    (\"Tuesday\", 22),\n    (\"Wednesday\", 25),\n    (\"Thursday\", 19),\n    (\"Friday\", 28),\n    (\"Saturday\", 24),\n    (\"Sunday\", 21)\n]\n# Find day with highest temperature\nhighest_day = max(temperature_data, key=lambda t: t[1])[0]\n# Find day with lowest temperature\nlowest_day = min(temperature_data, key=lambda t: t[1])[0]\n# Calculate average temperature\naverage_temp = sum(t[1] for t in temperature_data) / len(temperature_data)\n# Count number of days with temperature above 20\ndays_above_20 = sum(1 for t in temperature_data if t[1] > 20)\n# Print results\nprint(highest_day)\nprint(lowest_day)\nprint(round(average_temp, 1))\nprint(days_above_20)"
        }
    }
}

def test_submission():
    """Test batch submission with corrected payload"""
    url = f"http://localhost:8000/submissions/challenges/{CHALLENGE_ID}/submit-challenge"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print("=" * 80)
    print("🧪 TESTING BATCH SUBMISSION")
    print("=" * 80)
    print(f"\n📍 URL: {url}")
    print(f"\n🔑 Challenge ID: {CHALLENGE_ID}")
    print(f"\n📦 Payload keys: {list(payload['submissions'].keys())}")
    print(f"✅ Keys are now WITHOUT 'question_' prefix (CORRECT FORMAT)")
    print("\n🚀 Sending request...")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        print(f"\n📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ SUCCESS! Response:")
            print(json.dumps(result, indent=2))
            
            # Check if questions were processed
            submission_result = result.get("result", {})
            passed = submission_result.get("passed_questions", [])
            failed = submission_result.get("failed_questions", [])
            missing = submission_result.get("missing_questions", [])
            
            print("\n" + "=" * 80)
            print("📈 RESULTS SUMMARY")
            print("=" * 80)
            print(f"✅ Passed: {len(passed)} questions")
            print(f"❌ Failed: {len(failed)} questions")
            print(f"⚠️  Missing: {len(missing)} questions")
            
            if missing:
                print("\n⚠️  WARNING: Questions still marked as missing!")
                print("This means the keys might still be wrong or the snapshot has different IDs")
                
            # Check achievement data
            achievement = result.get("achievement_summary", {})
            if achievement:
                summary = achievement.get("summary", {})
                elo_data = summary.get("elo", {})
                gpa_data = summary.get("gpa", {})
                
                print("\n" + "=" * 80)
                print("🏆 ACHIEVEMENTS")
                print("=" * 80)
                print(f"ELO: {elo_data.get('before', 0)} → {elo_data.get('after', 0)} (Δ{elo_data.get('delta', 0)})")
                print(f"GPA: {gpa_data.get('before', 0)} → {gpa_data.get('after', 0)}")
                
        else:
            print(f"\n❌ FAILED: {response.status_code}")
            try:
                error = response.json()
                print(json.dumps(error, indent=2))
            except:
                print(response.text)
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_submission()
