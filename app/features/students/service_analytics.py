from app.features.students import repository, repository_analytics
from app.features.students.schemas import StudentProgress, ModuleProgress

async def compute_elo(user_id: int) -> int:
    data = await repository_analytics.fetch_user_elo(user_id)
    return data.get("current_elo", 1000)

async def compute_student_analytics(user_id: int) -> dict:
    """
    Aggregates all student analytics:
    - Code submissions & results
    - Challenge attempts
    - Achievements / badges
    - ELO info
    - Question progress
    """
    submissions = await repository_analytics.fetch_submissions(user_id)
    code_results = await repository_analytics.fetch_code_results(user_id)
    challenge_attempts = await repository_analytics.fetch_challenge_attempts(user_id)
    achievements = await repository_analytics.fetch_user_achievements(user_id)
    elo_events = await repository_analytics.fetch_elo_events(user_id)
    user_elo = await repository_analytics.fetch_user_elo(user_id)
   
    # Basic aggregates
    total_questions_passed = sum(1 for s in code_results if s.get("is_correct"))
    challenges_completed = sum(1 for c in challenge_attempts if c.get("status") == "submitted")
    total_achievements = len(achievements)

    return {
        "submissions": submissions,
        "code_results": code_results,
        "challenge_attempts": challenge_attempts,
        "achievements": achievements,
        "total_achievements": total_achievements,
        "elo": {
            "current": user_elo.get("current_elo", 0),
            "streak": user_elo.get("current_streak", 0),
            "longest_streak": user_elo.get("longest_streak", 0),
            "events": elo_events,
        },
        "total_questions_passed": total_questions_passed,
        "challenges_completed": challenges_completed,
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
