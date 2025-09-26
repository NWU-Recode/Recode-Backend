from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from app.features.challenges.repository import challenge_repository
from app.features.challenges.scoring import (
    AttemptScore,
    Tier,
    recompute_semester_mark,
    determine_milestones,
    summarize,
)


@dataclass
class WeekReleaseState:
    week: int
    common_challenge_id: Optional[str]
    ruby_challenge_id: Optional[str]
    emerald_challenge_id: Optional[str]
    status: str  # draft | published


class SemesterOrchestrator:
    async def get_release_overview(self, user_id: str) -> Dict[str, Any]:
        # Fetch all challenges and normalize tiers so 'plain' is presented as 'base'
        challenges = await challenge_repository.list_challenges()
        def _normalize_tier(ch: Dict[str, Any]) -> str:
            t = (ch.get("tier") or "").strip().lower()
            if t in {"plain", "common", "base"}:
                return "base"
            return t or "base"

        base_challenges = [c for c in challenges if _normalize_tier(c) == "base"]
        ruby = [c for c in challenges if _normalize_tier(c) == "ruby"]
        emerald = [c for c in challenges if _normalize_tier(c) == "emerald"]

        # Summaries per user
        attempts = await challenge_repository.list_user_attempts(user_id)
        by_ch = {str(a.get("challenge_id")): a for a in attempts if a}

        base_attempt_scores: List[AttemptScore] = []
        for c in base_challenges:
            cid = str(c.get("id"))
            att = by_ch.get(cid)
            if not att or att.get("status") != "submitted":
                continue
            correct = bool((att.get("correct_count") or 0) >= 3)  # heuristic if not computed
            # sum 5 questions -> total=5 for averaging; correctness used only as boolean in blend here
            # Tier enum uses 'plain' as the challenge-tier label
            base_attempt_scores.append(AttemptScore(tier=Tier.plain, correct=correct, total=5))

        ruby_correct = False
        for c in ruby:
            att = by_ch.get(str(c.get("id")))
            if att and att.get("status") == "submitted" and (att.get("correct_count") or 0) >= 1:
                ruby_correct = True
                break

        emerald_correct = False
        for c in emerald:
            att = by_ch.get(str(c.get("id")))
            if att and att.get("status") == "submitted" and (att.get("correct_count") or 0) >= 1:
                emerald_correct = True
                break

        diamond_correct = False  # reserved for future diamond support

        agg = recompute_semester_mark(
            plain_attempts=base_attempt_scores,
            ruby_correct=ruby_correct,
            emerald_correct=emerald_correct,
            diamond_correct=diamond_correct,
        )

        # completed plain should count submitted attempts for base challenges
        completed_plain = 0
        for a in attempts:
            if a.get("status") == "submitted":
                # determine the challenge tier for this attempt
                ch = a.get("challenge") or {}
                t = (ch.get("tier") if isinstance(ch, dict) else None) or (ch[0].get("tier") if isinstance(ch, list) and ch else None)
                if (str(t).strip().lower() in {"plain", "base", "common"}) or t is None:
                    completed_plain += 1
        total_plain = len(base_challenges)
        unlocks = determine_milestones(completed_plain, total_plain)

        return {
            "counts": {
                "base": total_plain,
                "ruby": len(ruby),
                "emerald": len(emerald),
            },
            "milestones": {
                "ruby": unlocks.ruby,
                "emerald": unlocks.emerald,
                "diamond": unlocks.diamond,
            },
            "aggregate": summarize(agg),
        }


semester_orchestrator = SemesterOrchestrator()
