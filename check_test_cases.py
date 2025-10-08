"""Check if questions have test cases in question_tests table"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.DB.supabase import get_supabase

async def check_test_cases():
    client = await get_supabase()
    
    challenge_id = "b40d7802-4c06-460a-befb-373718608ab4"
    
    print(f"🔍 Checking test cases for challenge: {challenge_id}\n")
    print("="*80 + "\n")
    
    # Get all questions for this challenge
    try:
        q_resp = await client.table("questions").select("id, title, question_number").eq("challenge_id", challenge_id).order("question_number").execute()
        
        if not q_resp.data:
            print("❌ No questions found for this challenge!")
            return
        
        print(f"Found {len(q_resp.data)} questions:\n")
        
        total_tests = 0
        
        for q in q_resp.data:
            qid = q.get('id')
            title = q.get('title')
            qnum = q.get('question_number')
            
            print(f"Question {qnum}: {title}")
            print(f"  ID: {qid}")
            
            # Check for test cases
            try:
                t_resp = await client.table("question_tests").select("*").eq("question_id", qid).execute()
                
                if t_resp.data:
                    print(f"  ✅ {len(t_resp.data)} test case(s) found:")
                    total_tests += len(t_resp.data)
                    
                    for i, test in enumerate(t_resp.data[:3], 1):  # Show first 3 tests
                        inp = test.get('input', '')
                        exp = test.get('expected') or test.get('expected_output', '')
                        vis = test.get('visibility', 'unknown')
                        
                        # Truncate long values
                        inp_display = inp[:50] + "..." if len(str(inp)) > 50 else inp
                        exp_display = exp[:50] + "..." if len(str(exp)) > 50 else exp
                        
                        print(f"    Test {i} ({vis}):")
                        print(f"      Input: {inp_display}")
                        print(f"      Expected: {exp_display}")
                else:
                    print(f"  ❌ NO TEST CASES FOUND!")
                    
            except Exception as e:
                print(f"  ❌ Error checking tests: {e}")
            
            print()
        
        print("="*80)
        print(f"\n📊 SUMMARY:")
        print(f"  Total Questions: {len(q_resp.data)}")
        print(f"  Total Test Cases: {total_tests}")
        
        if total_tests == 0:
            print(f"\n⚠️  WARNING: This challenge has NO test cases in question_tests table!")
            print(f"  The AI model may not have generated tests, or they failed to persist.")
            print(f"  Check logs for: 'Has X tests in generated data' and 'Persisted X/Y test cases'")
        else:
            print(f"\n✅ Challenge has test cases and is ready for submission!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_test_cases())
