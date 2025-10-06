from __future__ import annotations

"""
Semester scoring + milestone blending.
Lightweight implementation sufficient for MVP lecturer dashboards.

Blending rules (per product spec):
	- Base only: 100% base average
	- Ruby unlocked: 60% base + 40% ruby
	- Emerald unlocked: 50% base + 50% avg(ruby, emerald)
	- Diamond unlocked: 40% base + 60% avg(ruby, emerald, diamond)

Base average = sum(correct)/sum(total) across submitted base challenges.
Special tiers (ruby/emerald/diamond) are single-question challenges (score 1 or 0).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Tier(str, Enum):
    bronze = "bronze"
    silver = "silver"
    gold = "gold"
    ruby = "ruby"
    emerald = "emerald"
    diamond = "diamond"
    base = "base"


@dataclass
class AttemptScore:
    tier: Tier | None
    correct: bool
    total: int = 1


@dataclass
class MilestoneUnlocks:
    ruby: bool
    emerald: bool
    diamond: bool


def determine_milestones(base_completed: int, total_base_planned: int) -> MilestoneUnlocks:
    return MilestoneUnlocks(
        ruby=base_completed >= 2,
        emerald=base_completed >= 4,
        diamond=base_completed >= total_base_planned and total_base_planned > 0,
    )


@dataclass
class AggregateSemester:
    base_pct: float
    ruby_correct: bool
    emerald_correct: bool
    diamond_correct: bool
    blended_pct: float


def recompute_semester_mark(
    base_attempts: Iterable[AttemptScore],
    ruby_correct: bool,
    emerald_correct: bool,
    diamond_correct: bool,
) -> AggregateSemester:
    base_attempts = list(base_attempts)
    base_total_questions = sum(a.total for a in base_attempts) or 0
    base_correct_questions = sum(a.total for a in base_attempts if a.correct)
    base_pct = (base_correct_questions / base_total_questions * 100.0) if base_total_questions else 0.0

    # Apply blending according to milestone completion
    if diamond_correct:
        specials = [ruby_correct, emerald_correct, diamond_correct]
        specials_avg = (sum(1 for s in specials if s) / len(specials)) * 100.0
        blended = 0.40 * base_pct + 0.60 * specials_avg
    elif emerald_correct:
        specials = [ruby_correct, emerald_correct]
        specials_avg = (sum(1 for s in specials if s) / len(specials)) * 100.0
        blended = 0.50 * base_pct + 0.50 * specials_avg
    elif ruby_correct:
        specials_avg = (1 if ruby_correct else 0) * 100.0
        blended = 0.60 * base_pct + 0.40 * specials_avg
    else:
        blended = base_pct

    return AggregateSemester(
        base_pct=round(base_pct, 2),
        ruby_correct=ruby_correct,
        emerald_correct=emerald_correct,
        diamond_correct=diamond_correct,
        blended_pct=round(blended, 2),
    )


def summarize(agg: AggregateSemester) -> dict:
    return {
        "base_pct": agg.base_pct,
        "ruby_correct": agg.ruby_correct,
        "emerald_correct": agg.emerald_correct,
        "diamond_correct": agg.diamond_correct,
        "blended_pct": agg.blended_pct,
    }

