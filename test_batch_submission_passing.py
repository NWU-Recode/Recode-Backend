"""
Test batch submission with PASSING solutions
This will demonstrate database population for user_elo, user_badge, user_question_progress, user_scores
"""
import requests
import json

# Your auth token
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IkhNaUlHZ2I2WnZTblhlS3QiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2d0b2VodmxvZHJtbXF6eXhvYWlsLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI3NTk1N2JmZi04NjAyLTQ0NjMtYmY0Yy02MmVjODUzNmQyY2IiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU5ODc1NTk5LCJpYXQiOjE3NTk4NzE5OTksImVtYWlsIjoiYnJhbmRvbnZhbnZ1dXJlbjdAZ21haWwuY29tIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6eyJlbWFpbCI6ImJyYW5kb252YW52dXVyZW43QGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmdWxsX25hbWUiOiJCcmFuZG9uIFRlc3QiLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInN1YiI6Ijc1OTU3YmZmLTg2MDItNDQ2My1iZjRjLTYyZWM4NTM2ZDJjYiJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6InBhc3N3b3JkIiwidGltZXN0YW1wIjoxNzU5ODcxOTk5fV0sInNlc3Npb25faWQiOiIxNGRlMDhkNi0yMjQ4LTRmZDUtOTM5Mi0wZjM1MDZhNTNiNDYiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.ig7pZw-eiKrt8RrW8rVDfvuZ66XXsZoNkFpedrC7dA0"

CHALLENGE_ID = "b40d7802-4c06-460a-befb-373718608ab4"

# CORRECTED PAYLOAD with GENERIC solutions (no hardcoded test data)
# These solutions read from stdin and work with ANY input
payload = {
    "duration_seconds": 120,
    "submissions": {
        # Question 1: Create a tuple from input
        "6363385e-ff33-464b-a106-c6a6ae74018e": {
            "language_id": 71,
            "source_code": """# Read input values
name = input().strip()
age = int(input().strip())
# Create the tuple
student = (name, age)
# Print the tuple
print(student)"""
        },
        # Question 2: Access tuple elements
        "c672ca99-0355-444b-837f-4834e811d872": {
            "language_id": 71,
            "source_code": """# Read input values
x = int(input().strip())
y = int(input().strip())
# Create tuple
point = (x, y)
# Print x and y coordinates
print(f"X: {point[0]}")
print(f"Y: {point[1]}")"""
        },
        # Question 3: Count occurrences in tuple
        "388a2b21-bab3-44a0-bd02-907adeebf686": {
            "language_id": 71,
            "source_code": """# Read all numbers - first is target, rest are tuple
all_numbers = list(map(int, input().strip().split()))
target = all_numbers[0]  # First number is target
numbers = tuple(all_numbers[1:])  # Rest are the tuple
# Count occurrences
count = numbers.count(target)
# Print count
print(count)"""
        },
        # Question 4: Find student with highest score
        "77bdcd12-700e-4215-bf19-2ff134f1f33d": {
            "language_id": 71,
            "source_code": """# Read lines until EOF
import sys
students = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    # Split by whitespace - last item should be score
    parts = line.split()
    if len(parts) < 2:
        continue
    # Last part is score, everything else is name
    score = int(parts[-1])
    name = ' '.join(parts[:-1])
    students.append((name, score))
# Find highest score
if students:
    highest_student = max(students, key=lambda s: s[1])
    print(highest_student[0])"""
        },
        # Question 5: Temperature data analysis
        "7070bee5-088c-471c-af8b-9cbeb69ad4e8": {
            "language_id": 71,
            "source_code": """# Read lines until EOF
import sys
temperature_data = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    # Split by space - last item is temp, first is day
    parts = line.split()
    day = parts[0]
    temp = int(parts[1])
    temperature_data.append((day, temp))
# Find highest
highest_day = max(temperature_data, key=lambda t: t[1])[0]
# Find lowest
lowest_day = min(temperature_data, key=lambda t: t[1])[0]
# Calculate average
average_temp = sum(t[1] for t in temperature_data) / len(temperature_data)
# Count days above 20
days_above_20 = sum(1 for t in temperature_data if t[1] > 20)
# Print results
print(highest_day)
print(lowest_day)
print(round(average_temp, 1))
print(days_above_20)"""
        }
    }
}

def test_submission():
    """Test batch submission with passing solutions"""
    url = f"http://localhost:8000/submissions/challenges/{CHALLENGE_ID}/submit-challenge"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print("=" * 80)
    print("🧪 TESTING BATCH SUBMISSION WITH PASSING SOLUTIONS")
    print("=" * 80)
    print(f"\n📍 URL: {url}")
    print(f"\n🔑 Challenge ID: {CHALLENGE_ID}")
    print(f"\n📦 Payload keys: {list(payload['submissions'].keys())}")
    print(f"✅ Keys WITHOUT 'question_' prefix")
    print(f"✅ Solutions use input() to read test data dynamically")
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
            
            if passed:
                print("\n🎉 PASSED QUESTIONS:")
                for qid in passed:
                    print(f"   ✓ {qid}")
            
            if failed:
                print("\n❌ FAILED QUESTIONS:")
                for qid in failed:
                    print(f"   ✗ {qid}")
                    
            # Check achievement data
            achievement = result.get("achievement_summary", {})
            if achievement:
                summary = achievement.get("summary", {})
                elo_data = summary.get("elo", {})
                gpa_data = summary.get("gpa", {})
                badges_data = summary.get("badges", [])
                
                print("\n" + "=" * 80)
                print("🏆 ACHIEVEMENTS & DATABASE POPULATION")
                print("=" * 80)
                print(f"\n📊 ELO Updates (saved to user_elo table):")
                print(f"   Before: {elo_data.get('before', 0)}")
                print(f"   After:  {elo_data.get('after', 0)}")
                print(f"   Delta:  {elo_data.get('delta', 0)}")
                
                print(f"\n📚 GPA Updates (saved to user_elo & user_scores tables):")
                print(f"   Before: {gpa_data.get('before', 0)}")
                print(f"   After:  {gpa_data.get('after', 0)}")
                
                if badges_data:
                    print(f"\n🏅 Badges Earned (saved to user_badge table):")
                    for badge in badges_data:
                        print(f"   • {badge.get('badge_name', 'Unknown')}: {badge.get('reason', '')}")
                else:
                    print(f"\n🏅 No badges earned this attempt")
                
                print("\n" + "=" * 80)
                print("💾 DATABASE TABLES POPULATED:")
                print("=" * 80)
                print("✓ user_elo - ELO points and GPA tracking")
                print("✓ user_scores - Overall student performance")
                print("✓ user_question_progress - Individual test results")
                if badges_data:
                    print("✓ user_badge - Badge awards")
                
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
