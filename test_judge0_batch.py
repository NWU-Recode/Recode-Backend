import asyncio
import sys
import os

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.features.judge0.service import judge0_service
from app.features.judge0.schemas import CodeSubmissionCreate

async def main():
    # Test code that should produce stdout
    test_code = """# Read the data
n = int(input())
numbers = tuple(map(int, input().split()))
target = int(input())

# Count occurrences
count = numbers.count(target)
print(count)"""

    submission = CodeSubmissionCreate(
        source_code=test_code,
        language_id=71,  # Python
        stdin="5\n1 2 3 2 4\n2",
        expected_output="2"
    )

    print("Testing single submission...")
    token, result = await judge0_service.execute_code_sync(submission)
    print(f"Token: {token}")
    print(f"Stdout: {result.stdout!r}")
    print(f"Status: {result.status_id} - {result.status_description}")
    print(f"Success: {result.success}")
    print()

    print("Testing batch submission...")
    submissions = [submission] * 3
    results = await judge0_service.execute_batch(submissions)
    for idx, (tok, res) in enumerate(results):
        print(f"Result {idx}: token={tok}, stdout={res.stdout!r}, status={res.status_id}")

if __name__ == "__main__":
    asyncio.run(main())
