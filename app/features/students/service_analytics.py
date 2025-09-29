from app.features.students import repository, repository_analytics
from app.features.students.schemas import StudentProgress, ModuleProgress

async def compute_elo(user_id: int) -> int:
    data = await repository_analytics.fetch_user_elo(user_id)
    return data.get("current_elo", 1000)

async def compute_student_progress(user_id: int) -> dict:
    submissions = await repository_analytics.fetch_submissions(user_id)
    code_subs = await repository_analytics.fetch_code_submissions(user_id)
    return {
        "total_questions_passed": sum(1 for s in code_subs if s.get("is_correct")),
        "challenges_completed": sum(1 for s in submissions if s.get("status_id") == 3),
    }

async def compute_student_analytics(user_id: int) -> dict:
    return await repository_analytics.fetch_student_analytics(user_id)

async def get_full_student_progress(user_id: int) -> StudentProgress:
    profile = await repository.get_student_profile(user_id)
    modules = await repository.get_student_modules(user_id)
    elo_data = await repository_analytics.fetch_user_elo(user_id)
    return StudentProgress(
        profile=profile,
        modules=modules,
        elo=elo_data.get("current_elo", 1000),
        gpa=elo_data.get("gpa"),
        streak=elo_data.get("current_streak", 0),
        longest_streak=elo_data.get("longest_streak", 0),
        topics_mastered=[],
        recent_challenges=[]
    )
