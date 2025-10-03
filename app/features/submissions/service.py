from __future__ import annotations

import math
from datetime import datetime, timezone
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, List, Optional

from app.features.challenges.repository import challenge_repository
from app.features.submissions.code_results_repository import code_results_repository
from app.features.submissions.repository import submissions_repository
from app.features.submissions.schemas import (
    ChallengeQuestionResultSchema,
    ChallengeSubmissionBreakdown,
    QuestionBundleSchema,
    QuestionEvaluationResponse,
    TestRunResultSchema,
    BatchSubmissionEntry,
)

MAX_SCORING_ATTEMPTS = 1

_FAIL_ELO_BY_TIER = {
    "base": -40,
    "plain": -40,
    "common": -40,
    "bronze": -55,
    "silver": -70,
    "gold": -90,
    "ruby": -150,
    "emerald": -220,
    "diamond": -320,
}

_BASE_ELO_BY_TIER = {
    "base": 25,
    "plain": 25,
    "common": 25,
    "bronze": 35,
    "silver": 50,
    "gold": 65,
    "ruby": 120,
    "emerald": 190,
    "diamond": 320,
}


_TIME_LIMIT_BY_TIER = {
    "base": 3600,
    "plain": 3600,
    "common": 3600,
    "bronze": 3600,
    "silver": 3600,
    "gold": 3600,
    "ruby": 5400,
    "emerald": 7200,
    "diamond": 10800,
}


@dataclass
class _GradingWeights:
    gpa_by_tier: Dict[str, int]

    @property
    def default(self) -> int:
        return 0

    def gpa_weight(self, tier: Optional[str]) -> int:
        if not tier:
            return 0
        return self.gpa_by_tier.get(tier.lower(), 0)


_GRADING_WEIGHTS = _GradingWeights(
    gpa_by_tier={
        "bronze": 12,
        "silver": 18,
        "gold": 24,
        "ruby": 40,
        "emerald": 50,
        "diamond": 60,
    }
)

_ADVANCED_TIERS = {"ruby", "emerald", "diamond"}


def _time_limit_for_tier(tier: Optional[str]) -> Optional[int]:
    if not tier:
        return _TIME_LIMIT_BY_TIER.get("base")
    key = str(tier).lower()
    return _TIME_LIMIT_BY_TIER.get(key, _TIME_LIMIT_BY_TIER.get("base"))


def _parse_iso_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _late_multiplier(duration_seconds: Optional[int], limit_seconds: Optional[int]) -> float:
    if duration_seconds is None or limit_seconds is None:
        return 1.0
    return 0.7 if duration_seconds > limit_seconds else 1.0

def _resolve_tier(tier: Optional[str]) -> str:
    if not tier:
        return "base"
    return str(tier).lower()


def _fail_penalty(tier: Optional[str]) -> int:
    return _FAIL_ELO_BY_TIER.get(_resolve_tier(tier), -10)


def _base_elo(tier: Optional[str]) -> int:
    return _BASE_ELO_BY_TIER.get(_resolve_tier(tier), 12)


def _normalise_output(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Trim trailing whitespace without collapsing intentional internal spaces
    lines = text.split("\n")
    cleaned = [line.rstrip() for line in lines]
    # Strip leading/trailing blank lines but keep meaningful spacing
    while cleaned and cleaned[0] == "":
        cleaned.pop(0)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    return "\n".join(cleaned)


class SubmissionsService:
    async def get_question_bundle(self, challenge_id: str, question_id: str) -> QuestionBundleSchema:
        question = await submissions_repository.get_question(question_id)
        if not question:
            raise ValueError("question_not_found")
        tier = (question.get("tier") or "").lower() or None
        weight = _GRADING_WEIGHTS.gpa_weight(tier)
        if not weight:
            weight = int(question.get("points") or _GRADING_WEIGHTS.default)
        max_time = question.get("max_time_ms")
        max_memory = question.get("max_memory_kb")
        max_time_ms = int(max_time) if max_time not in (None, "") else None
        max_memory_kb = int(max_memory) if max_memory not in (None, "") else None
        expected_output = question.get("expected_output")
        if isinstance(expected_output, str):
            expected_output = expected_output.strip("\n")
        return QuestionBundleSchema(
            challenge_id=str(question.get("challenge_id") or challenge_id),
            question_id=str(question_id),
            title=str(question.get("title") or ""),
            prompt=str(question.get("question_text") or ""),
            starter_code=str(question.get("starter_code") or ""),
            reference_solution=question.get("reference_solution"),
            expected_output=expected_output,
            tier=tier,
            language_id=int(question.get("language_id") or 71),
            points=weight,
            max_time_ms=max_time_ms,
            max_memory_kb=max_memory_kb,
            badge_id=str(question.get("badge_id")) if question.get("badge_id") else None,
        )

    async def submit_question(
        self,
        challenge_id: str,
        question_id: str,
        submitted_output: str,
        *,
        user_id: int,
        language_id: Optional[int] = None,
        include_private: bool = True,
        perform_award: bool = True,
    ) -> QuestionEvaluationResponse:
        challenge = await challenge_repository.get_challenge(challenge_id)
        if not challenge:
            raise ValueError('challenge_not_found')
        tier = (challenge.get('tier') or 'base').lower()
        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, user_id)
        attempt_id = str(attempt.get('id'))
        status = str(attempt.get('status') or '').lower()
        if status == 'submitted':
            raise ValueError('challenge_already_submitted')
        if status == 'expired':
            raise ValueError('challenge_attempt_expired')
        snapshot = await challenge_repository.get_snapshot(attempt)
        target_qid = str(question_id)
        snapshot_entry = next((item for item in snapshot if str(item.get('question_id')) == target_qid), None)
        if not snapshot_entry:
            raise ValueError('question_not_in_snapshot')
        attempts_used = int(snapshot_entry.get('attempts_used') or 0)
        if attempts_used >= MAX_SCORING_ATTEMPTS:
            raise ValueError('attempt_limit_reached')
        bundle = await self.get_question_bundle(challenge_id, question_id)
        lang = int(language_id or snapshot_entry.get('language_id') or bundle.language_id or 71)
        expected_output = snapshot_entry.get('expected_output') or bundle.expected_output
        started_at = _parse_iso_timestamp(attempt.get('started_at'))
        finished_at = datetime.now(timezone.utc)
        duration_seconds = int((finished_at - started_at).total_seconds()) if started_at else None
        time_limit_seconds = _time_limit_for_tier(tier)
        late_multiplier = _late_multiplier(duration_seconds, time_limit_seconds)
        attempt_number = attempts_used + 1
        result = await self.evaluate_question(
            challenge_id,
            question_id,
            submitted_output,
            lang,
            include_private=include_private,
            bundle=bundle,
            expected_output=expected_output,
            user_id=user_id,
            attempt_number=attempt_number,
            late_multiplier=late_multiplier,
            attempt_id=attempt_id,
            perform_award=perform_award,
        )
        try:
            await challenge_repository.record_question_attempts(
                attempt_id,
                {target_qid: 1},
                max_attempts=MAX_SCORING_ATTEMPTS,
            )
        except Exception:
            pass
        return result

    async def evaluate_question(
        self,
        challenge_id: str,
        question_id: str,
        submitted_output: str,
        language_id: Optional[int] = None,
        include_private: bool = True,
        bundle: QuestionBundleSchema | None = None,
        *,
        expected_output: Optional[str] = None,
        user_id: int,
        attempt_number: int,
        late_multiplier: float,
        attempt_id: Optional[str] = None,
        perform_award: bool = True,
        record_result: bool = True,
    ) -> QuestionEvaluationResponse:
        bundle = bundle or await self.get_question_bundle(challenge_id, question_id)
        lang = int(language_id or bundle.language_id or 71)
        resolved_expected = expected_output if expected_output is not None else bundle.expected_output
        if resolved_expected is None:
            raise ValueError("question_missing_expected_output")

        expected_norm = _normalise_output(resolved_expected)
        actual_norm = _normalise_output(submitted_output)
        passed_all = expected_norm == actual_norm

        tests_total = 1
        tests_passed = 1 if passed_all else 0

        gpa_weight = bundle.points or _GRADING_WEIGHTS.gpa_weight(bundle.tier)
        time_multiplier = 1.0
        memory_multiplier = 1.0
        attempt_multiplier = math.pow(0.9, max(0, attempt_number - 1))
        base_component = _base_elo(bundle.tier)

        if not passed_all:
            elo_delta = _fail_penalty(bundle.tier)
            elo_base = 0
            efficiency_bonus = elo_delta
            gpa_awarded = 0
        else:
            raw_delta = base_component * time_multiplier * memory_multiplier * late_multiplier * attempt_multiplier
            elo_delta = int(round(raw_delta))
            elo_base = base_component
            efficiency_bonus = elo_delta - elo_base
            perf = (tests_passed / tests_total) * time_multiplier * memory_multiplier * late_multiplier
            gpa_awarded = int(round(perf * gpa_weight))

        if bundle.tier in _ADVANCED_TIERS and include_private and not passed_all:
            gpa_awarded = 0

        badge_tier = bundle.tier if passed_all else None

        detail_message = None
        if not passed_all:
            detail_message = "Submitted output does not match expected output."

        execution_record = TestRunResultSchema(
            test_id="expected_output",
            visibility="public",
            passed=passed_all,
            stdout=submitted_output,
            expected_output=resolved_expected,
            status_id=3 if passed_all else 1,
            status_description="accepted" if passed_all else "mismatch",
            detail=detail_message,
            score_awarded=int(gpa_awarded if passed_all else 0),
            gpa_contribution=int(gpa_awarded if passed_all else 0),
        )
        executions = [execution_record]
        avg_time_ms = None
        avg_memory_kb = None

        summary = {
            "status_id": 3 if passed_all else 1,
            "stdout": submitted_output,
            "stderr": None,
            "time": None,
            "wall_time": None,
            "memory": None,
            "number_of_runs": 1,
            "finished_at": datetime.now(timezone.utc),
            "message": "outputs_matched" if passed_all else "outputs_mismatched",
            "additional_files": {
                "challenge_id": challenge_id,
                "question_id": question_id,
                "attempt_id": attempt_id,
                "attempt_number": attempt_number,
                "tests_total": tests_total,
                "tests_passed": tests_passed,
                "tier": bundle.tier,
                "late_multiplier": late_multiplier,
                "include_private": include_private,
                "gpa_awarded": gpa_awarded,
            },
        }

        submission_id = None
        test_records = [execution_record.model_dump()]
        if record_result:
            try:
                submission_id = await code_results_repository.log_test_batch(
                    user_id=user_id,
                    language_id=lang,
                    source_code=submitted_output,
                    token=None,
                    test_records=test_records,
                    summary=summary,
                    stdin=None,
                    expected_output=resolved_expected,
                    challenge_id=challenge_id,
                    question_id=question_id,
                )
            except Exception:
                submission_id = None

        # perform_award retained for compatibility; external awarders rely on challenge finalisation
        if perform_award and passed_all:
            # Achievements are processed when the challenge attempt is finalised.
            # Keep the branch for API compatibility even though no immediate action is required.
            pass

        return QuestionEvaluationResponse(
            challenge_id=bundle.challenge_id,
            question_id=bundle.question_id,
            tier=bundle.tier,
            language_id=lang,
            gpa_weight=gpa_weight,
            gpa_awarded=gpa_awarded,
            elo_awarded=elo_delta,
            elo_base=elo_base,
            elo_efficiency_bonus=efficiency_bonus,
            public_passed=passed_all,
            tests_passed=tests_passed,
            tests_total=tests_total,
            average_execution_time_ms=avg_time_ms,
            average_memory_used_kb=avg_memory_kb,
            badge_tier_awarded=badge_tier,
            submission_id=submission_id,
            attempt_id=attempt_id,
            attempt_number=attempt_number,
            tests=executions,
        )

    async def submit_challenge(
        self,
        challenge_id: str,
        attempt_id: str,
        submissions: Dict[str, BatchSubmissionEntry],
        language_overrides: Dict[str, int],
        question_weights: Dict[str, int],
        expected_outputs: Dict[str, Optional[str]],
        *,
        user_id: int,
        tier: str,
        attempt_counts: Dict[str, int],
        max_attempts: int,
        late_multiplier: float,
        perform_award: bool = True,
    ) -> ChallengeSubmissionBreakdown:
        return await self.grade_challenge_submission(
            challenge_id=challenge_id,
            attempt_id=attempt_id,
            submissions=submissions,
            language_overrides=language_overrides,
            question_weights=question_weights,
            expected_outputs=expected_outputs,
            user_id=user_id,
            tier=tier,
            attempt_counts=attempt_counts,
            max_attempts=max_attempts,
            late_multiplier=late_multiplier,
            perform_award=perform_award,
        )

    async def grade_challenge_submission(
        self,
        challenge_id: str,
        attempt_id: str,
        submissions: Dict[str, BatchSubmissionEntry],
        language_overrides: Dict[str, int],
        question_weights: Dict[str, int],
        expected_outputs: Dict[str, Optional[str]],
        *,
        user_id: int,
        tier: str,
        attempt_counts: Dict[str, int],
        max_attempts: int,
        late_multiplier: float,
        perform_award: bool = True,
    ) -> ChallengeSubmissionBreakdown:
        _ = perform_award  # Awarding handled by achievements service after finalisation.
        results: List[ChallengeQuestionResultSchema] = []
        passed_questions: List[str] = []
        failed_questions: List[str] = []
        missing_questions: List[str] = []
        badge_tiers: List[str] = []
        bundle_cache: Dict[str, QuestionBundleSchema] = {}
        for qid in language_overrides.keys():
            try:
                bundle_cache[qid] = await self.get_question_bundle(challenge_id, qid)
            except ValueError:
                continue
        gpa_max = 0
        for qid in language_overrides.keys():
            bundle = bundle_cache.get(qid)
            if bundle:
                gpa_max += bundle.points or _GRADING_WEIGHTS.gpa_weight(bundle.tier)
            else:
                gpa_max += question_weights.get(qid, 0)
        gpa_total = 0
        base_elo_total = 0
        efficiency_total = 0
        tests_total = 0
        tests_passed_total = 0
        avg_time_inputs: List[float] = []
        avg_memory_inputs: List[float] = []

        for question_id in language_overrides.keys():
            bundle = bundle_cache.get(question_id)
            entry = submissions.get(question_id)
            current_attempts = attempt_counts.get(question_id, 0)
            if entry is None:
                missing_questions.append(question_id)
                continue
            submitted_output = entry.output
            if current_attempts >= max_attempts:
                fail_penalty = _fail_penalty(bundle.tier if bundle else tier)
                placeholder = TestRunResultSchema(
                    test_id="attempt_limit",
                    visibility="public",
                    passed=False,
                    stdout=None,
                    expected_output=None,
                    status_id=1,
                    status_description="mismatch",
                    detail="attempt_limit_reached",
                    score_awarded=0,
                    gpa_contribution=0,
                )
                eval_result = QuestionEvaluationResponse(
                    challenge_id=challenge_id,
                    question_id=question_id,
                    tier=bundle.tier if bundle else tier,
                    language_id=language_overrides.get(question_id, 71),
                    gpa_weight=bundle.points if bundle else question_weights.get(question_id, 0),
                    gpa_awarded=0,
                    elo_awarded=fail_penalty,
                    elo_base=0,
                    elo_efficiency_bonus=fail_penalty,
                    public_passed=False,
                    tests_passed=0,
                    tests_total=0,
                    average_execution_time_ms=None,
                    average_memory_used_kb=None,
                    badge_tier_awarded=None,
                    submission_id=None,
                    attempt_id=attempt_id,
                    attempt_number=current_attempts,
                    tests=[placeholder],
                )
            else:
                eval_result = await self.evaluate_question(
                    challenge_id,
                    question_id,
                    submitted_output,
                    language_overrides.get(question_id),
                    include_private=True,
                    bundle=bundle,
                    expected_output=expected_outputs.get(question_id),
                    user_id=user_id,
                    attempt_number=current_attempts + 1,
                    late_multiplier=late_multiplier,
                    attempt_id=attempt_id,
                )

            gpa_total += int(eval_result.gpa_awarded)
            base_elo_total += int(eval_result.elo_base)
            efficiency_total += int(eval_result.elo_efficiency_bonus)
            tests_total += int(eval_result.tests_total)
            tests_passed_total += int(eval_result.tests_passed)
            if eval_result.average_execution_time_ms is not None:
                avg_time_inputs.append(eval_result.average_execution_time_ms)
            if eval_result.average_memory_used_kb is not None:
                avg_memory_inputs.append(eval_result.average_memory_used_kb)
            if eval_result.public_passed and eval_result.tests_passed == eval_result.tests_total and eval_result.badge_tier_awarded:
                passed_questions.append(question_id)
                badge_tiers.append(eval_result.badge_tier_awarded)
            else:
                failed_questions.append(question_id)
            results.append(ChallengeQuestionResultSchema(**eval_result.model_dump()))

        average_execution_time_ms = mean(avg_time_inputs) if avg_time_inputs else None
        average_memory_used_kb = mean(avg_memory_inputs) if avg_memory_inputs else None
        dedup_badges: List[str] = []
        for tier_value in badge_tiers:
            if tier_value and tier_value not in dedup_badges:
                dedup_badges.append(tier_value)
        return ChallengeSubmissionBreakdown(
            challenge_id=challenge_id,
            attempt_id=attempt_id,
            gpa_score=gpa_total,
            gpa_max_score=gpa_max,
            elo_delta=base_elo_total + efficiency_total,
            base_elo_total=base_elo_total,
            efficiency_bonus_total=efficiency_total,
            tests_total=tests_total,
            tests_passed_total=tests_passed_total,
            average_execution_time_ms=average_execution_time_ms,
            average_memory_used_kb=average_memory_used_kb,
            passed_questions=passed_questions,
            failed_questions=failed_questions,
            missing_questions=missing_questions,
            badge_tiers_awarded=dedup_badges,
            question_results=results,
        )


submissions_service = SubmissionsService()

__all__ = ["submissions_service", "SubmissionsService", "MAX_SCORING_ATTEMPTS"]


