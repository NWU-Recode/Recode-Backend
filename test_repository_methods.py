#!/usr/bin/env python3
"""
Test database writes with explicit error handling.
"""
import asyncio
import logging
from app.features.achievements.repository import AchievementsRepository

# Enable logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def main():
    print("=" * 80)
    print("🧪 TESTING ACHIEVEMENTS REPOSITORY METHODS")
    print("=" * 80)
    
    repo = AchievementsRepository()
    student_id = "10000001"
    
    # Test 1: Update user ELO
    print("\n📊 Test 1: update_user_elo")
    print("-" * 80)
    try:
        result = await repo.update_user_elo(
            user_id=student_id,
            elo_points=123,
            gpa=3.5,
            module_code="COMP101",
        )
        print(f"✅ Result: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Get user ELO
    print("\n📊 Test 2: get_user_elo")
    print("-" * 80)
    try:
        result = await repo.get_user_elo(user_id=student_id)
        print(f"✅ Result: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Update user scores
    print("\n📊 Test 3: update_user_scores")
    print("-" * 80)
    try:
        await repo.update_user_scores(
            user_id=student_id,
            elo=123,
            gpa=3.5,
            questions_attempted=10,
            questions_passed=8,
            challenges_completed=2,
            badges=3,
        )
        print(f"✅ Completed successfully")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Log ELO event
    print("\n📊 Test 4: log_elo_event")
    print("-" * 80)
    try:
        await repo.log_elo_event({
            "student_id": int(student_id),
            "event_type": "challenge_complete",
            "elo_delta": 50,
            "reason": "Test event",
        })
        print(f"✅ Completed successfully")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
