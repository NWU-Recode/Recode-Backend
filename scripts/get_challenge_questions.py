"""
Script to fetch challenge questions and their test cases for submission testing
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.DB.supabase import get_supabase

async def get_challenge_details(challenge_id: str):
    """Fetch challenge details including questions and test cases"""
    client = await get_supabase()
    
    # Get challenge info
    print(f"\n{'='*80}")
    print(f"CHALLENGE ID: {challenge_id}")
    print(f"{'='*80}\n")
    
    challenge_resp = await client.table("challenges").select("*").eq("id", challenge_id).execute()
    if not challenge_resp.data:
        print(f"❌ Challenge {challenge_id} not found!")
        return
    
    challenge = challenge_resp.data[0]
    print(f"📋 Challenge: {challenge.get('title')}")
    print(f"   Tier: {challenge.get('tier')}")
    print(f"   Week: {challenge.get('week_number')}")
    print(f"   Module: {challenge.get('module_code')}")
    print(f"   Status: {challenge.get('status')}")
    
    # Get questions
    questions_resp = await client.table("questions").select("*").eq("challenge_id", challenge_id).order("question_number").execute()
    
    if not questions_resp.data:
        print("\n❌ No questions found for this challenge!")
        return
    
    questions = questions_resp.data
    print(f"\n📝 Found {len(questions)} questions:\n")
    
    submissions_dict = {}
    
    for i, q in enumerate(questions, 1):
        q_id = q.get('id')
        print(f"\n{'─'*80}")
        print(f"Question {i}: {q.get('title')}")
        print(f"ID: {q_id}")
        print(f"{'─'*80}")
        print(f"\n📖 Description:")
        print(q.get('question_text', 'N/A'))
        print(f"\n💻 Starter Code:")
        print(q.get('starter_code', 'N/A'))
        print(f"\n✅ Reference Solution:")
        print(q.get('reference_solution', 'N/A'))
        
        # Get test cases
        tests_resp = await client.table("question_tests").select("*").eq("question_id", q_id).execute()
        
        if tests_resp.data:
            print(f"\n🧪 Test Cases ({len(tests_resp.data)}):")
            for j, test in enumerate(tests_resp.data, 1):
                visibility = test.get('visibility', 'public')
                input_val = test.get('input', 'N/A')
                expected = test.get('expected_output') or test.get('expected', 'N/A')
                print(f"\n  Test {j} ({visibility}):")
                print(f"    Input: {input_val}")
                print(f"    Expected: {expected}")
        else:
            print("\n⚠️  No test cases found!")
        
        # Add to submissions dict with reference solution
        ref_solution = q.get('reference_solution', '')
        if ref_solution:
            submissions_dict[f"question_{q_id}"] = {
                "language_id": q.get('language_id', 71),
                "source_code": ref_solution
            }
    
    # Generate submission payload
    print(f"\n\n{'='*80}")
    print("📤 SUBMISSION PAYLOAD")
    print(f"{'='*80}\n")
    
    import json
    payload = {
        "duration_seconds": 300,
        "submissions": submissions_dict
    }
    
    print(json.dumps(payload, indent=2))
    
    # Generate curl command
    print(f"\n\n{'='*80}")
    print("🚀 CURL COMMAND")
    print(f"{'='*80}\n")
    
    token = "eyJhbGciOiJIUzI1NiIsImtpZCI6IkhNaUlHZ2I2WnZTblhlS3QiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2d0b2VodmxvZHJtbXF6eXhvYWlsLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI2ZjNhYzA1NC1jNmY1LTRiOTQtYjRkNC0wODJjNDQ4MzRjMjgiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU5ODgzMjk1LCJpYXQiOjE3NTk4Nzk2OTUsImVtYWlsIjoiMzQyNTAxMTVAbXlud3UuYWMuemEiLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsIjoiMzQyNTAxMTVAbXlud3UuYWMuemEiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiZnVsbF9uYW1lIjoiQnJhbmRvbiB2YW4gVnV1cmVuIE5XVSIsInBob25lX3ZlcmlmaWVkIjpmYWxzZSwic3R1ZGVudF9udW1iZXIiOjk5OTk5OTk5LCJzdWIiOiI2ZjNhYzA1NC1jNmY1LTRiOTQtYjRkNC0wODJjNDQ4MzRjMjgifSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc1OTg3OTY5NX1dLCJzZXNzaW9uX2lkIjoiMTdkYWQ3NDEtMDFhMi00NjliLWI0OTAtNWY2ZmIwYzBmZWM1IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.y3FCA05JgyYMYWacnIu7k03ClV4bw-1akH44RE3nOl4"
    
    print(f"curl -X POST \"http://localhost:8000/api/challenges/{challenge_id}/submit-challenge\" \\")
    print(f"  -H \"Content-Type: application/json\" \\")
    print(f"  -H \"Authorization: Bearer {token}\" \\")
    print(f"  -d '{json.dumps(payload)}'")
    
    print(f"\n{'='*80}\n")

if __name__ == "__main__":
    load_dotenv()
    
    challenge_id = "b40d7802-4c06-460a-befb-373718608ab4"
    
    if len(sys.argv) > 1:
        challenge_id = sys.argv[1]
    
    asyncio.run(get_challenge_details(challenge_id))
