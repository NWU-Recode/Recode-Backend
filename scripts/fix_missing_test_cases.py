"""
Fix missing test cases for challenge 6e957ff3-13fc-48e7-9622-b86b43f2d0b5
This script generates and inserts test cases directly into question_tests table.
"""

import asyncio
import sys
import os
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.DB.supabase import get_supabase

CHALLENGE_ID = "6e957ff3-13fc-48e7-9622-b86b43f2d0b5"

# Test cases for each question based on expected_output
TEST_CASES = {
    "830d02fc-6d0e-417f-8f96-8f3a67634492": [  # Student Records
        {"input": "Alice\n85", "expected_output": "('Alice', 85)"},
        {"input": "Bob\n92", "expected_output": "('Bob', 92)"},
        {"input": "Charlie\n78", "expected_output": "('Charlie', 78)"},
    ],
    "1c9b5dbf-32f7-4f6e-aea7-7a64300c2f43": [  # Coordinate Parts
        {"input": "5\n10", "expected_output": "X: 5\nY: 10"},
        {"input": "0\n0", "expected_output": "X: 0\nY: 0"},
        {"input": "-3\n7", "expected_output": "X: -3\nY: 7"},
    ],
    "fbb81d33-3b67-432d-ae5b-d7a827b25a6d": [  # Score Pairs
        {"input": "3\n10 15\n20 25\n30 35", "expected_output": "60\n75"},
        {"input": "2\n5 10\n15 20", "expected_output": "20\n30"},
        {"input": "1\n100 200", "expected_output": "100\n200"},
    ],
    "297db452-f56c-42bb-8c03-b4069f8567c5": [  # Temperature Range
        {"input": "3\nMonday 25\nTuesday 30\nWednesday 20", "expected_output": "Tuesday\nWednesday"},
        {"input": "2\nJan 15\nFeb 10", "expected_output": "Jan\nFeb"},
        {"input": "4\nDay1 22\nDay2 25\nDay3 20\nDay4 28", "expected_output": "Day4\nDay3"},
    ],
    "83853eb0-2444-47bc-b6a7-63db3f48e9ae": [  # Library Books
        {"input": "3\nHarry 1997\nLord 1954\nPython 2020", "expected_output": "Lord 1954\nHarry 1997\nPython 2020"},
        {"input": "2\nBook1 2000\nBook2 1990", "expected_output": "Book2 1990\nBook1 2000"},
        {"input": "1\nSingle 2021", "expected_output": "Single 2021"},
    ],
}

async def main():
    client = await get_supabase()
    
    print(f"\n{'='*60}")
    print(f"FIXING MISSING TEST CASES")
    print(f"Challenge: {CHALLENGE_ID}")
    print(f"{'='*60}\n")
    
    total_inserted = 0
    
    for question_id, test_cases in TEST_CASES.items():
        print(f"\nQuestion: {question_id}")
        print(f"  Inserting {len(test_cases)} test cases...")
        
        for i, test_case in enumerate(test_cases, 1):
            try:
                test_id = str(uuid4())
                
                payload = {
                    "id": test_id,
                    "question_id": question_id,
                    "input": test_case["input"],
                    "expected_output": test_case["expected_output"],  # Correct column name!
                    "visibility": "public",  # public or hidden
                    "valid": False,  # Set to false initially
                }
                
                result = await client.table("question_tests").insert(payload).execute()
                
                if result.data:
                    print(f"    ✅ Test {i} inserted: {test_id}")
                    total_inserted += 1
                else:
                    print(f"    ❌ Test {i} failed: No data returned")
                    
            except Exception as e:
                print(f"    ❌ Test {i} error: {e}")
    
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total test cases inserted: {total_inserted}")
    print(f"Expected: {sum(len(cases) for cases in TEST_CASES.values())}")
    
    # Verify the inserts
    print(f"\n{'='*60}")
    print(f"VERIFICATION")
    print(f"{'='*60}\n")
    
    for question_id in TEST_CASES.keys():
        result = await client.table("question_tests").select("id").eq("question_id", question_id).execute()
        count = len(result.data) if result.data else 0
        print(f"Question {question_id[:8]}: {count} test cases")
    
    print(f"\n✅ DONE! You can now submit to this challenge.\n")

if __name__ == "__main__":
    asyncio.run(main())
