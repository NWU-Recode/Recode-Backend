from __future__ import annotations
from typing import List, Dict, Any
from app.features.profiles.repository import profile_repository as user_repository
from app.features.challenges.repository import challenge_repository
from app.features.questions.repository import question_repository
from app.features.challenges.scoring import AttemptScore, Tier, recompute_semester_mark, summarize, determine_milestones
from app.features.lecturer.schemas import StudentProgressResponse, ChallengeResponse, ModuleModel, AnalyticsResponse

# Ensure all methods return the appropriate schemas

class LecturerService:
    async def list_students_with_progress(self) -> List[StudentProgressResponse]:
        users = await user_repository.list_users(limit=500)
        students = [u for u in users if (u.get("role") or "student") == "student"]
        results: List[StudentProgressResponse] = []
        # Preload plain attempts per student (naive per student for MVP)
        total_plain_planned = await challenge_repository.total_plain_planned()
        for stu in students:
            uid = str(stu["id"])
            attempts = await challenge_repository.list_user_attempts(uid)
            # Gather plain attempts & special correctness
            plain_attempt_scores: List[AttemptScore] = []
            ruby_correct = False
            emerald_correct = False
            diamond_correct = False
            for att in attempts:
                if att.get("status") != "submitted":
                    continue
                challenge_id = str(att.get("challenge_id"))
                # need challenge to know tier AND number of questions
                ch = await challenge_repository.get_challenge(challenge_id)
                if not ch:
                    continue
                tier = ch.get("tier")
                if tier == "plain":
                    # pull latest question attempts to compute correctness count
                    latest_q = await question_repository.list_latest_attempts_for_challenge(challenge_id, uid)
                    total = len(latest_q) or 10
                    correct = sum(1 for qa in latest_q if qa.get("is_correct"))
                    # treat each question as separate attempt score entries
                    for i in range(correct):
                        plain_attempt_scores.append(AttemptScore(tier=Tier.bronze, correct=True))
                    for i in range(total - correct):
                        plain_attempt_scores.append(AttemptScore(tier=Tier.bronze, correct=False))
                elif tier == "ruby":
                    ruby_correct = (att.get("correct_count") or 0) > 0
                elif tier == "emerald":
                    emerald_correct = (att.get("correct_count") or 0) > 0
                elif tier == "diamond":
                    diamond_correct = (att.get("correct_count") or 0) > 0
            plain_completed = await challenge_repository.count_plain_completed(uid)
            unlocks = determine_milestones(plain_completed, total_plain_planned)
            agg = recompute_semester_mark(
                plain_attempts=plain_attempt_scores,
                ruby_correct=ruby_correct and unlocks.ruby,
                emerald_correct=emerald_correct and unlocks.emerald,
                diamond_correct=diamond_correct and unlocks.diamond,
            )
            results.append(StudentProgressResponse(
                student_id=uid,
                email=stu.get("email"),
                plain_pct=agg.plain_pct,
                ruby_correct=int(ruby_correct),
                emerald_correct=int(emerald_correct),
                diamond_correct=int(diamond_correct),
                blended_pct=agg.blended_pct,
            ))
        return results

lecturer_service = LecturerService()
