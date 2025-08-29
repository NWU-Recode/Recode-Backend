from __future__ import annotations

"""Semester scoring + milestone blending.
Lightweight implementation sufficient for MVP lecturer dashboards.

Weights:
	- Plain only: 100% plain average
	- Ruby unlocked (>=1 ruby attempt existing): 75% plain + 25% ruby
	- Emerald unlocked: 65% plain + 35% avg(ruby, emerald)
	- Diamond unlocked: 50% plain + 50% avg(ruby, emerald, diamond)

Plain average = sum(correct)/sum(total) across submitted plain challenges.
Special tiers (ruby/emerald/diamond) each single-question challenges (score 1 or 0).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List


class Tier(str, Enum):
	bronze = "bronze"  # question tier inside plain challenge
	silver = "silver"
	gold = "gold"
	ruby = "ruby"
	emerald = "emerald"
	diamond = "diamond"
	plain = "plain"  # challenge tier convenience label


@dataclass
class AttemptScore:
	tier: Tier
	correct: bool
	total: int = 1


@dataclass
class MilestoneUnlocks:
	ruby: bool
	emerald: bool
	diamond: bool


def determine_milestones(plain_completed: int, total_plain_planned: int) -> MilestoneUnlocks:
	"""Derive which milestones are eligible based on count of completed plain challenges.

	Simple rule (can evolve):
	- ruby after >=2 plain
	- emerald after >=4 plain
	- diamond only after all planned plain done (and at least 1 planned)
	"""
	return MilestoneUnlocks(
		ruby=plain_completed >= 2,
		emerald=plain_completed >= 4,
		diamond=plain_completed >= total_plain_planned and total_plain_planned > 0,
	)


@dataclass
class AggregateSemester:
	plain_pct: float
	ruby_correct: bool
	emerald_correct: bool
	diamond_correct: bool
	blended_pct: float

def recompute_semester_mark(
	plain_attempts: Iterable[AttemptScore],
	ruby_correct: bool,
	emerald_correct: bool,
	diamond_correct: bool,
) -> AggregateSemester:
	plain_attempts = list(plain_attempts)
	# Compute plain average
	plain_total_questions = sum(a.total for a in plain_attempts) or 0
	plain_correct_questions = sum(a.total for a in plain_attempts if a.correct)
	plain_pct = (plain_correct_questions / plain_total_questions * 100.0) if plain_total_questions else 0.0

	# Determine weight stage
	if diamond_correct:
		# final blend 50/50 among plain and avg of ruby/emerald/diamond
		specials = [ruby_correct, emerald_correct, diamond_correct]
		specials_avg = (sum(1 for s in specials if s) / len(specials)) * 100.0
		blended = 0.50 * plain_pct + 0.50 * specials_avg
	elif emerald_correct:
		# blend with ruby+emerald
		specials = [ruby_correct, emerald_correct]
		specials_avg = (sum(1 for s in specials if s) / len(specials)) * 100.0
		blended = 0.65 * plain_pct + 0.35 * specials_avg
	elif ruby_correct:
		specials_avg = (1 if ruby_correct else 0) * 100.0
		blended = 0.75 * plain_pct + 0.25 * specials_avg
	else:
		blended = plain_pct

	return AggregateSemester(
		plain_pct=round(plain_pct, 2),
		ruby_correct=ruby_correct,
		emerald_correct=emerald_correct,
		diamond_correct=diamond_correct,
		blended_pct=round(blended, 2),
	)


def summarize(agg: AggregateSemester) -> dict:
	return {
		"plain_pct": agg.plain_pct,
		"ruby_correct": agg.ruby_correct,
		"emerald_correct": agg.emerald_correct,
		"diamond_correct": agg.diamond_correct,
		"blended_pct": agg.blended_pct,
	}

