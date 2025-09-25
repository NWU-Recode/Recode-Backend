from typing import List, Dict
from app.features.students import repository_analytics

async def compute_elo(user_id: int) -> int:
    elo_data = await repository_analytics.fetch_user_elo(user_id)
    return elo_data.get("current_elo", 1000)

async def compute_student_progress(user_id: int) -> dict:
    submissions = await repository_analytics.fetch_submissions(user_id)
    code_subs = await repository_analytics.fetch_code_submissions(user_id)

    total_questions_passed = sum(1 for s in code_subs if s.get("is_correct"))
    total_challenges_completed = len([s for s in submissions if s.get("status_id") == 3])  # assuming 3=completed
    return {
        "total_questions_passed": total_questions_passed,
        "challenges_completed": total_challenges_completed,
    }

async def compute_student_analytics(user_id: int) -> dict:
    return await repository_analytics.fetch_student_analytics(user_id)
