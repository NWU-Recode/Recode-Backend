import asyncio
import sys
sys.path.insert(0, 'c:\\Users\\brand\\Desktop\\323\\RECODE\\Recode-Backend')

from app.DB.supabase import get_supabase

async def get_questions_for_challenge():
    client = await get_supabase()
    
    challenge_id = "6e957ff3-13fc-48e7-9622-b86b43f2d0b5"
    
    # Get questions for this challenge with their test cases
    resp = await client.table("questions").select(
        "id, title, question_text, question_number, expected_output"
    ).eq("challenge_id", challenge_id).order("question_number").execute()
    
    questions = resp.data
    
    print(f"\n{'='*80}")
    print(f"Challenge ID: {challenge_id}")
    print(f"Found {len(questions)} questions")
    print(f"{'='*80}\n")
    
    for q in questions:
        print(f"Question {q['question_number']}: {q['title']}")
        print(f"  ID: {q['id']}")
        print(f"  Expected Output: {q.get('expected_output', 'N/A')[:100]}")
        
        # Get test cases
        test_resp = await client.table("question_tests").select(
            "id, input, expected_output, visibility"
        ).eq("question_id", q['id']).execute()
        
        tests = test_resp.data
        print(f"  Test Cases: {len(tests)}")
        
        if tests:
            for i, test in enumerate(tests[:2], 1):  # Show first 2 tests
                test_input = test.get('input', '')
                test_expected = test.get('expected_output', '')
                print(f"    Test {i}: input='{test_input[:50]}' → expected='{test_expected[:50]}'")
        
        print()

if __name__ == "__main__":
    asyncio.run(get_questions_for_challenge())
