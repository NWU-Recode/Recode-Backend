from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, Iterable, List, Optional, Tuple

from app.features.challenges.repository import challenge_repository
from app.features.challenges.tier_utils import normalise_challenge_tier
from app.features.submissions.code_results_repository import code_results_repository
from app.features.submissions.comparison import CompareConfig, compare, resolve_mode
from app.features.submissions.repository import submissions_repository
from app.features.submissions.schemas import (
    BatchSubmissionEntry,
    ChallengeQuestionResultSchema,
    ChallengeSubmissionBreakdown,
    QuestionBundleSchema,
    QuestionEvaluationResponse,
    QuestionTestSchema,
    TestRunResultSchema,
)
from app.features.judge0.schemas import CodeSubmissionCreate, CodeExecutionResult
from app.features.judge0.service import judge0_service

DEFAULT_LANGUAGE_ID = 71
MAX_QUESTION_SCORE = 100
MAX_SCORING_ATTEMPTS = 3

DEFAULT_TIME_LIMIT_SECONDS = 3600

_FAIL_ELO_BY_TIER = {
    "base": -40,
    "bronze": -55,
    "silver": -70,
    "gold": -90,
    "ruby": -150,
    "emerald": -220,
    "diamond": -320,
}

_BASE_ELO_BY_TIER = {
    "base": 25,
    "bronze": 35,
    "silver": 50,
    "gold": 65,
    "ruby": 120,
    "emerald": 190,
    "diamond": 320,
}

_ADVANCED_TIERS = {"ruby", "emerald", "diamond"}


@dataclass
class _GradingWeights:
    gpa_by_tier: Dict[str, int]

    def gpa_weight(self, tier: Optional[str]) -> int:
        if not tier:
            return MAX_QUESTION_SCORE
        return self.gpa_by_tier.get(tier.lower(), MAX_QUESTION_SCORE)


_GRADING_WEIGHTS = _GradingWeights(
    gpa_by_tier={
        "bronze": 120,
        "silver": 140,
        "gold": 160,
        "ruby": 200,
        "emerald": 240,
        "diamond": 300,
    }
)


def _resolve_tier(tier: Optional[str]) -> str:
    return normalise_challenge_tier(tier) or "base"


def _fail_penalty(tier: Optional[str]) -> int:
    return _FAIL_ELO_BY_TIER.get(_resolve_tier(tier), -40)


def _base_elo(tier: Optional[str]) -> int:
    return _BASE_ELO_BY_TIER.get(_resolve_tier(tier), 25)


def _distribute_score(parts: int, total: int) -> List[int]:
    if parts <= 0:
        return []
    base = total // parts
    remainder = total - (base * parts)
    scores = [base] * parts
    for idx in range(remainder):
        scores[idx] += 1
    return scores


def _select_tests(tests: Iterable[QuestionTestSchema], include_private: bool) -> List[QuestionTestSchema]:
    cleaned: List[QuestionTestSchema] = []
    visibility_key = "private"
    for test in tests or []:
        if include_private:
            cleaned.append(test)
            continue
        vis = (test.visibility or "").strip().lower()
        if vis and vis == visibility_key:
            continue
        cleaned.append(test)
    return cleaned


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _late_multiplier(started_at: Optional[datetime], *, limit_seconds: Optional[int]) -> float:
    if started_at is None or limit_seconds is None or limit_seconds <= 0:
        return 1.0
    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    if elapsed <= limit_seconds:
        return 1.0
    return 0.7


def _comparison_attempts_payload(attempts) -> Optional[List[Dict[str, object]]]:
    if not attempts:
        return None
    payload: List[Dict[str, object]] = []
    for att in attempts:
        payload.append(
            {
                "mode": getattr(att, "mode", None),
                "passed": getattr(att, "passed", None),
                "reason": getattr(att, "reason", None),
                "normalisations": getattr(att, "normalisations", None),
                "duration_ms": getattr(att, "duration_ms", None),
            }
        )
    return payload


class SubmissionsService:
    async def get_question_bundle(self, challenge_id: str, question_id: str) -> QuestionBundleSchema:
        question = await submissions_repository.get_question(question_id)
        if not question:
            raise ValueError("question_not_found")
        tests_rows = await submissions_repository.list_tests(question_id)
        tests = [QuestionTestSchema(**row) for row in tests_rows]

        tier = _resolve_tier(question.get("tier"))
        points = int(question.get("points") or MAX_QUESTION_SCORE)
        expected_output = question.get("expected_output") or None
        if isinstance(expected_output, str):
            expected_output = expected_output.rstrip("\n")

        return QuestionBundleSchema(
            challenge_id=str(question.get("challenge_id") or challenge_id),
            question_id=str(question_id),
            title=str(question.get("title") or question.get("name") or ""),
            prompt=str(question.get("question_text") or question.get("prompt") or ""),
            starter_code=str(question.get("starter_code") or ""),
            reference_solution=question.get("reference_solution"),
            expected_output=expected_output,
            tier=tier,
            language_id=int(question.get("language_id") or DEFAULT_LANGUAGE_ID),
            points=points,
            max_time_ms=question.get("max_time_ms"),
            max_memory_kb=question.get("max_memory_kb"),
            badge_id=str(question.get("badge_id")) if question.get("badge_id") else None,
            tests=tests,
        )

    async def evaluate_question(
        self,
        *,
        challenge_id: str,
        question_id: str,
        submitted_output: Optional[str],
        source_code: Optional[str] = None,
        language_id: Optional[int] = None,
        include_private: bool = True,
        bundle: Optional[QuestionBundleSchema] = None,
        user_id: int,
        attempt_number: int,
        late_multiplier: float = 1.0,
        attempt_id: Optional[str] = None,
        perform_award: bool = False,
        record_result: bool = True,
    ) -> QuestionEvaluationResponse:
        del perform_award

        if source_code is None and submitted_output is None:
            raise ValueError("submission_requires_output")

        bundle = bundle or await self.get_question_bundle(challenge_id, question_id)
        lang = int(language_id or bundle.language_id or DEFAULT_LANGUAGE_ID)

        tests = _select_tests(bundle.tests, include_private)
        if not tests:
            raise ValueError("question_missing_tests")

        expected_values: List[str] = []
        for test in tests:
            expected_val = test.expected
            if expected_val is None:
                raise ValueError("test_missing_expected_output")
            expected_values.append(expected_val)

        score_shares = _distribute_score(len(tests), bundle.points or MAX_QUESTION_SCORE)
        first_expected_for_logging: Optional[str] = expected_values[0] if expected_values else None

        compare_cfg = CompareConfig()
        results: List[TestRunResultSchema] = []
        passed_count = 0
        execution_second_samples: List[float] = []
        memory_samples: List[int] = []

        use_judge0 = source_code is not None
        judge0_pairs: List[tuple[str, CodeExecutionResult]] = []
        if use_judge0 and tests:
            submissions_payload = [
                CodeSubmissionCreate(
                    source_code=source_code or "",
                    language_id=lang,
                    stdin=tests[idx].input,
                    expected_output=expected_values[idx],
                )
                for idx in range(len(tests))
            ]
            if submissions_payload:
                judge0_pairs = await judge0_service.execute_batch(submissions_payload)
                if len(judge0_pairs) != len(submissions_payload):
                    raise ValueError("judge0_batch_result_mismatch")

        for idx, test in enumerate(tests):
            expected_val = expected_values[idx]

            mode_override = resolve_mode(test.compare_mode)
            config_overrides = test.compare_config or {}

            # Initialize defaults - will be overridden by Judge0 results if using code execution
            stdout_val = ""
            stderr_val = None
            compile_output_val = None
            status_id = 3
            status_description = "comparison_only"
            token_val = None
            exec_time = None
            exec_seconds = None
            memory_used = None

            if use_judge0:
                if idx >= len(judge0_pairs):
                    raise ValueError("judge0_batch_result_mismatch")
                token_val, exec_result = judge0_pairs[idx]
                
                # CRITICAL: Use Judge0 stdout directly, don't fall back to submitted_output
                stdout_val = exec_result.stdout if exec_result.stdout is not None else ""
                stderr_val = exec_result.stderr
                compile_output_val = exec_result.compile_output
                status_id = int(exec_result.status_id or 0)
                status_description = exec_result.status_description or ""
                exec_time = exec_result.execution_time
                try:
                    exec_seconds = float(exec_time) if exec_time is not None else None
                except Exception:
                    exec_seconds = None
                memory_used = exec_result.memory_used

                if not stdout_val:
                    try:
                        raw = await judge0_service.get_submission_result(token_val)
                        hydrated = judge0_service._to_code_execution_result(raw, expected_val, lang)
                        stdout_val = hydrated.stdout or stdout_val
                        stderr_val = hydrated.stderr if hydrated.stderr is not None else stderr_val
                        compile_output_val = hydrated.compile_output if hydrated.compile_output is not None else compile_output_val
                        status_id = int(hydrated.status_id or status_id)
                        status_description = hydrated.status_description or status_description
                        exec_time = hydrated.execution_time or exec_time
                        try:
                            exec_seconds = float(exec_time) if exec_time is not None else exec_seconds
                        except Exception:
                            exec_seconds = exec_seconds
                        memory_used = hydrated.memory_used if hydrated.memory_used is not None else memory_used
                    except Exception:
                        pass

            comparison = await compare(
                expected_val,
                stdout_val,
                compare_cfg,
                mode=mode_override,
                compare_config=config_overrides,
            )

            passed_local = bool(comparison.passed)
            if use_judge0 and status_id != 3:
                passed_local = False

            score_awarded = score_shares[idx] if idx < len(score_shares) and passed_local else 0

            detail_reason = None
            if not passed_local:
                if use_judge0 and status_id != 3:
                    detail_reason = status_description or "execution_failed"
                else:
                    detail_reason = comparison.reason or "outputs_mismatch"

            result = TestRunResultSchema(
                test_id=test.id or f"test:{idx}",
                visibility=test.visibility,
                passed=passed_local,
                stdout=stdout_val,
                expected_output=expected_val,
                stderr=stderr_val,
                compile_output=compile_output_val,
                status_id=status_id,
                status_description=status_description,
                detail=detail_reason,
                score_awarded=score_awarded,
                gpa_contribution=score_awarded,
                token=token_val,
                execution_time=exec_time,
                execution_time_seconds=exec_seconds,
                execution_time_ms=(exec_seconds * 1000.0) if exec_seconds is not None else None,
                memory_used=memory_used,
                memory_used_kb=memory_used,
                compare_mode_applied=comparison.mode_applied,
                normalisations_applied=comparison.normalisations_applied,
                why_failed=None if passed_local else (detail_reason or comparison.reason),
                comparison_attempts=_comparison_attempts_payload(getattr(comparison, "attempts", None)),
            )

            if result.passed:
                passed_count += 1
            if result.execution_time_seconds is not None:
                execution_second_samples.append(result.execution_time_seconds)
            if result.memory_used is not None:
                memory_samples.append(result.memory_used)

            results.append(result)


        tests_total = len(results)
        tests_passed = passed_count
        passed_all = tests_passed == tests_total and tests_total > 0

        gpa_awarded = sum(item.gpa_contribution for item in results)
        gpa_weight = bundle.points or _GRADING_WEIGHTS.gpa_weight(bundle.tier)

        if passed_all:
            gpa_awarded = int(round(gpa_weight * late_multiplier))
        else:
            gpa_awarded = 0 if bundle.tier in _ADVANCED_TIERS else min(gpa_awarded, gpa_weight)

        base_component = _base_elo(bundle.tier)
        attempt_multiplier = math.pow(0.9, max(0, attempt_number - 1))
        if passed_all:
            elo_base = base_component
            elo_delta = int(round(base_component * late_multiplier * attempt_multiplier))
            elo_efficiency = elo_delta - elo_base
        else:
            elo_base = 0
            elo_delta = _fail_penalty(bundle.tier)
            elo_efficiency = elo_delta

        if bundle.tier in _ADVANCED_TIERS and not passed_all:
            gpa_awarded = 0

        badge_tier = bundle.tier if passed_all else None

        average_execution_time_ms = (
            mean(execution_second_samples) * 1000.0 if execution_second_samples else None
        )
        average_memory_used_kb = mean(memory_samples) if memory_samples else None

        summary = {
            "status_id": 3 if passed_all else 4,
            "stdout": results[-1].stdout if results else submitted_output,
            "stderr": None,
            "time": None,
            "memory": None,
            "number_of_runs": tests_total,
            "finished_at": datetime.now(timezone.utc),
            "message": "outputs_matched" if passed_all else "outputs_mismatched",
            "additional_files": {
                "challenge_id": challenge_id,
                "question_id": question_id,
                "tier": bundle.tier,
                "attempt_number": attempt_number,
                "tests_total": tests_total,
                "tests_passed": tests_passed,
                "late_multiplier": late_multiplier,
            },
        }

        submission_id: Optional[str] = None
        if record_result:
            try:
                submission_id = await code_results_repository.log_test_batch(
                    user_id=user_id,
                    language_id=lang,
                    source_code=source_code or submitted_output or "",
                    token=None,
                    test_records=[item.model_dump() for item in results],
                    summary=summary,
                    stdin=None,
                    expected_output=first_expected_for_logging,
                    challenge_id=challenge_id,
                    question_id=question_id,
                )
            except Exception:
                submission_id = None

        return QuestionEvaluationResponse(
            challenge_id=challenge_id,
            question_id=question_id,
            tier=bundle.tier,
            language_id=lang,
            gpa_weight=gpa_weight,
            gpa_awarded=gpa_awarded,
            elo_awarded=elo_delta,
            elo_base=elo_base,
            elo_efficiency_bonus=elo_efficiency,
            public_passed=passed_all,
            tests_passed=tests_passed,
            tests_total=tests_total,
            average_execution_time_ms=average_execution_time_ms,
            average_memory_used_kb=average_memory_used_kb,
            badge_tier_awarded=badge_tier,
            submission_id=submission_id,
            attempt_id=attempt_id,
            attempt_number=attempt_number,
            tests=results,
        )

    async def submit_question(
        self,
        *,
        challenge_id: str,
        question_id: str,
        submitted_output: Optional[str],
        source_code: Optional[str],
        user_id: int,
        language_id: Optional[int] = None,
        include_private: bool = True,
    ) -> QuestionEvaluationResponse:
        challenge = await challenge_repository.get_challenge(challenge_id)
        if not challenge:
            raise ValueError("challenge_not_found")

        attempt = await challenge_repository.create_or_get_open_attempt(challenge_id, user_id)
        status = str(attempt.get("status") or "").lower()
        if status == "submitted":
            raise ValueError("challenge_already_submitted")
        if status == "expired":
            raise ValueError("challenge_attempt_expired")

        snapshot = await challenge_repository.get_snapshot(attempt)
        question_entry = next((item for item in snapshot if str(item.get("question_id")) == str(question_id)), None)
        if not question_entry:
            raise ValueError("question_not_in_snapshot")

        attempts_used = int(question_entry.get("attempts_used") or 0)
        if attempts_used >= MAX_SCORING_ATTEMPTS:
            raise ValueError("attempt_limit_reached")

        started_at = _parse_timestamp(str(attempt.get("started_at")) if attempt.get("started_at") else None)
        late_mult = _late_multiplier(started_at, limit_seconds=DEFAULT_TIME_LIMIT_SECONDS)
        attempt_number = attempts_used + 1

        bundle = await self.get_question_bundle(challenge_id, question_id)
        if question_entry.get("points"):
            try:
                bundle.points = int(question_entry["points"])  # type: ignore[misc]
            except Exception:
                pass

        result = await self.evaluate_question(
            challenge_id=challenge_id,
            question_id=question_id,
            submitted_output=submitted_output,
            source_code=source_code,
            language_id=language_id or question_entry.get("language_id"),
            include_private=include_private,
            bundle=bundle,
            user_id=user_id,
            attempt_number=attempt_number,
            late_multiplier=late_mult,
            attempt_id=str(attempt.get("id")),
            record_result=True,
        )

        try:
            await challenge_repository.record_question_attempts(
                str(attempt.get("id")),
                {str(question_id): 1},
                max_attempts=MAX_SCORING_ATTEMPTS,
            )
        except Exception:
            pass

        return result

    async def submit_challenge(
        self,
        *,
        challenge_id: str,
        attempt_id: str,
        submissions: Dict[str, BatchSubmissionEntry],
        language_overrides: Dict[str, Optional[int]],
        question_weights: Dict[str, int],
        user_id: int,
        tier: str,
        attempt_counts: Dict[str, int],
        max_attempts: int,
        late_multiplier: Optional[float] = None,
        started_at: Optional[datetime] = None,
        time_limit_seconds: Optional[int] = DEFAULT_TIME_LIMIT_SECONDS,
        duration_seconds: Optional[int] = None,
        perform_award: bool = False,
    ) -> ChallengeSubmissionBreakdown:
        del perform_award

        question_ids = list(language_overrides.keys())
        results: List[ChallengeQuestionResultSchema] = []
        passed_questions: List[str] = []
        failed_questions: List[str] = []
        missing_questions: List[str] = []
        badge_tiers: List[str] = []
        attempt_updates: Dict[str, int] = {}

        gpa_total = 0
        gpa_max = 0
        base_elo_total = 0
        efficiency_total = 0
        tests_total = 0
        tests_passed_total = 0
        avg_time_samples: List[float] = []
        avg_memory_samples: List[float] = []

        limit_seconds = time_limit_seconds if time_limit_seconds is not None else DEFAULT_TIME_LIMIT_SECONDS
        effective_late_multiplier = late_multiplier
        if effective_late_multiplier is None:
            effective_late_multiplier = _late_multiplier(started_at, limit_seconds=limit_seconds)
        if effective_late_multiplier is None:
            effective_late_multiplier = 1.0

        effective_duration = None
        if duration_seconds is not None:
            try:
                effective_duration = max(0, int(duration_seconds))
            except Exception:
                effective_duration = None
        if effective_duration is None and started_at is not None:
            try:
                effective_duration = int(max(0, (datetime.now(timezone.utc) - started_at).total_seconds()))
            except Exception:
                effective_duration = None

        for question_id in question_ids:
            bundle = await self.get_question_bundle(challenge_id, question_id)
            if question_weights.get(question_id):
                try:
                    bundle.points = int(question_weights[question_id])  # type: ignore[misc]
                except Exception:
                    pass

            entry = submissions.get(question_id)
            current_attempts = int(attempt_counts.get(question_id, 0))
            gpa_max += bundle.points or MAX_QUESTION_SCORE

            if entry is None:
                missing_questions.append(question_id)
                continue

            if current_attempts >= max_attempts:
                fail_penalty = _fail_penalty(bundle.tier)
                fail_result = ChallengeQuestionResultSchema(
                    challenge_id=challenge_id,
                    question_id=question_id,
                    tier=bundle.tier,
                    language_id=language_overrides.get(question_id) or bundle.language_id,
                    gpa_weight=bundle.points or MAX_QUESTION_SCORE,
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
                    tests=[
                        TestRunResultSchema(
                            test_id="attempt_limit",
                            visibility="public",
                            passed=False,
                            stdout=None,
                            expected_output=None,
                            status_id=4,
                            status_description="attempt_limit_reached",
                            detail="attempt_limit_reached",
                            score_awarded=0,
                            gpa_contribution=0,
                        )
                    ],
                )
                results.append(fail_result)
                failed_questions.append(question_id)
                efficiency_total += fail_penalty
                continue

            eval_result = await self.evaluate_question(
                challenge_id=challenge_id,
                question_id=question_id,
                submitted_output=None,
                source_code=entry.source_code,
                language_id=language_overrides.get(question_id) or entry.language_id,
                include_private=True,
                bundle=bundle,
                user_id=user_id,
                attempt_number=current_attempts + 1,
                late_multiplier=effective_late_multiplier,
                attempt_id=attempt_id,
                record_result=True,
            )

            attempt_updates[question_id] = attempt_updates.get(question_id, 0) + 1
            results.append(ChallengeQuestionResultSchema(**eval_result.model_dump()))

            gpa_total += int(eval_result.gpa_awarded)
            base_elo_total += int(eval_result.elo_base)
            efficiency_total += int(eval_result.elo_efficiency_bonus)
            tests_total += int(eval_result.tests_total)
            tests_passed_total += int(eval_result.tests_passed)

            if eval_result.average_execution_time_ms is not None:
                avg_time_samples.append(eval_result.average_execution_time_ms)
            if eval_result.average_memory_used_kb is not None:
                avg_memory_samples.append(eval_result.average_memory_used_kb)

            if eval_result.public_passed:
                passed_questions.append(question_id)
                if eval_result.badge_tier_awarded:
                    badge_tiers.append(eval_result.badge_tier_awarded)
            else:
                failed_questions.append(question_id)

        if attempt_updates:
            try:
                await challenge_repository.record_question_attempts(
                    attempt_id,
                    attempt_updates,
                    max_attempts=max_attempts,
                )
            except Exception:
                pass

        average_execution_time_ms = mean(avg_time_samples) if avg_time_samples else None
        average_memory_used_kb = mean(avg_memory_samples) if avg_memory_samples else None

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
            time_used_seconds=effective_duration,
            time_limit_seconds=limit_seconds,
            passed_questions=passed_questions,
            failed_questions=failed_questions,
            missing_questions=missing_questions,
            badge_tiers_awarded=dedup_badges,
            question_results=results,
        )


submissions_service = SubmissionsService()

__all__ = ["submissions_service", "SubmissionsService", "MAX_SCORING_ATTEMPTS"]






