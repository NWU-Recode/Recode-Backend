"""Check the actual schema of question_tests table"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.DB.supabase import get_supabase

CHALLENGE_WITH_TESTS = "b40d7802-4c06-460a-befb-373718608ab4"

async def main():
    client = await get_supabase()
    
    # Get questions for this challenge
    q_resp = await client.table("questions").select("id").eq("challenge_id", CHALLENGE_WITH_TESTS).limit(1).execute()
    
    if not q_resp.data:
        print("No questions found")
        return
    
    qid = q_resp.data[0]["id"]
    print(f"Question ID: {qid}")
    
    # Get ONE test case to see the schema
    test_resp = await client.table("question_tests").select("*").eq("question_id", qid).limit(1).execute()
    
    if not test_resp.data:
        print("No tests found")
        return
    
    print("\nActual test case structure:")
    import json
    print(json.dumps(test_resp.data[0], indent=2))
    
    print("\nColumn names:")
    for key in test_resp.data[0].keys():
        print(f"  - {key}")

if __name__ == "__main__":
    asyncio.run(main())
