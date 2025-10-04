from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

from app.features.judge0.schemas import CodeSubmissionCreate, CodeExecutionResult
from app.features.judge0.service import judge0_service
from app.features.challenges.repository import challenge_repository
from app.features.submissions.code_results_repository import code_results_repository
from app.features.submissions.repository import submissions_repository
from app.DB.supabase import get_supabase
from app.features.submissions.schemas import (
    ChallengeQuestionResultSchema,
    ChallengeSubmissionBreakdown,
    QuestionBundleSchema,
    QuestionEvaluationResponse,
    QuestionTestSchema,
    TestRunResultSchema,
)
from app.features.submissions.comparison import compare, CompareConfig, resolve_mode

DEFAULT_LANGUAGE_ID = 71
MAX_QUESTION_SCORE = 100

MAX_SCORING_ATTEMPTS = 1
DEFAULT_TIME_BUDGET_MS = 5000
DEFAULT_MEMORY_BUDGET_KB = 256 * 1024

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



def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _resolve_tier(tier: Optional[str]) -> str:
    if not tier:
        return "base"
    return str(tier).lower()


def _fail_penalty(tier: Optional[str]) -> int:
    return _FAIL_ELO_BY_TIER.get(_resolve_tier(tier), -10)


def _base_elo(tier: Optional[str]) -> int:
    return _BASE_ELO_BY_TIER.get(_resolve_tier(tier), 12)


class SubmissionsService:
    async def get_question_bundle(self, challenge_id: str, question_id: str) -> QuestionBundleSchema:
        question = await submissions_repository.get_question(question_id)
        if not question:
            raise ValueError("question_not_found")
        tests_raw = await submissions_repository.list_tests(question_id)
        tests = [QuestionTestSchema(**test) for test in tests_raw]
        tier = (question.get("tier") or "").lower() or None
        weight = MAX_QUESTION_SCORE
        max_time = question.get("max_time_ms")
        max_memory = question.get("max_memory_kb")
        max_time_ms = int(max_time) if max_time not in (None, "") else None
        max_memory_kb = int(max_memory) if max_memory not in (None, "") else None
        return QuestionBundleSchema(
            challenge_id=str(question.get("challenge_id") or challenge_id),
            question_id=str(question_id),
            title=str(question.get("title") or ""),
            prompt=str(question.get("question_text") or ""),
            starter_code=str(question.get("starter_code") or ""),
            reference_solution=question.get("reference_solution"),
            tier=tier,
            language_id=int(question.get("language_id") or DEFAULT_LANGUAGE_ID),
            points=weight,
            max_time_ms=max_time_ms,
            max_memory_kb=max_memory_kb,
            badge_id=str(question.get("badge_id")) if question.get("badge_id") else None,
            tests=tests,
        )

    async def _execute_test(
        self,
        source_code: str,
        language_id: int,
        test: QuestionTestSchema,
    ) -> TestRunResultSchema:
        submission = CodeSubmissionCreate(
            source_code=source_code,
            language_id=language_id,
            stdin=test.input,
            expected_output=test.expected,
        )
        waited = await judge0_service.submit_code_wait(submission)
        result: CodeExecutionResult = judge0_service._to_code_execution_result(  # type: ignore[attr-defined]
            waited, test.expected, language_id
        )
        passed = bool(result.success)
        status_id = int(result.status_id)
        status_description = self._status_description(status_id, str(result.status_description))
        exec_value = result.execution_time
        exec_seconds: Optional[float]
        try:
            exec_seconds = float(exec_value) if exec_value is not None else None
        except Exception:
            exec_seconds = None
        memory_value = result.memory_used
        memory_kb: Optional[int]
        try:
            memory_kb = int(memory_value) if memory_value is not None else None
        except Exception:
            memory_kb = None
        return TestRunResultSchema(
            test_id=test.id,
            visibility=test.visibility,
            passed=passed,
            stdout=result.stdout,
            stderr=result.stderr,
            compile_output=result.compile_output,
            status_id=status_id,
            status_description=status_description,
            token=getattr(waited, "token", None),
            execution_time=result.execution_time,
            execution_time_seconds=exec_seconds,
            execution_time_ms=(exec_seconds * 1000) if exec_seconds is not None else None,
            memory_used=memory_kb,
            memory_used_kb=memory_kb,
        )

    def _normalise_tests(self, tests: List[QuestionTestSchema]) -> List[QuestionTestSchema]:
        if not tests:
            return []
        indexed = list(enumerate(tests))

        def _order_key(item: tuple[int, QuestionTestSchema]) -> tuple[int, int]:
            idx, test = item
            try:
                return (int(test.order_index), idx)
            except Exception:
                return (0, idx)

        sorted_items = sorted(indexed, key=_order_key)
        return [test for _, test in sorted_items]

    async def submit_question(
        self,
        challenge_id: str,
        question_id: str,
        source_code: str,
        *,
        user_id: int,
        language_id: Optional[int] = None,
    include_private: bool = True,
    perform_award: bool = False,
    persist: bool = False,
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
        started_at = _parse_iso_timestamp(attempt.get('started_at'))
        finished_at = datetime.now(timezone.utc)
        duration_seconds = int((finished_at - started_at).total_seconds()) if started_at else None
        time_limit_seconds = _time_limit_for_tier(tier)
        late_multiplier = _late_multiplier(duration_seconds, time_limit_seconds)
        attempt_number = attempts_used + 1
        include_private_flag = True

        result = await self.evaluate_question(
            challenge_id,
            question_id,
            source_code,
            lang,
            include_private=include_private_flag,
            bundle=bundle,
            user_id=user_id,
            attempt_number=attempt_number,
            late_multiplier=late_multiplier,
            attempt_id=attempt_id,
            perform_award=perform_award,
            persist=persist,
        )
        return result

    async def evaluate_question(
        self,
        challenge_id: str,
        question_id: str,
        source_code: str,
        language_id: Optional[int] = None,
        include_private: bool = True,
        bundle: QuestionBundleSchema | None = None,
        *,
        user_id: int,
        attempt_number: int,
        late_multiplier: float,
        attempt_id: Optional[str] = None,
        perform_award: bool = True,
        persist: bool = True,
    ) -> QuestionEvaluationResponse:
        bundle = bundle or await self.get_question_bundle(challenge_id, question_id)
        lang = int(language_id or bundle.language_id or DEFAULT_LANGUAGE_ID)
        tests = self._normalise_tests(bundle.tests)
        if not include_private:
            tests = tests[:1]
        if not tests:
            raise ValueError("question_missing_tests")

        executions_raw: List[TestRunResultSchema] = await asyncio.gather(
            *[self._execute_test(source_code, lang, test) for test in tests]
        )

        score_splits: List[int] = []
        run_count = len(executions_raw)
        if run_count > 0:
            base_value = MAX_QUESTION_SCORE // run_count
            remainder = MAX_QUESTION_SCORE - (base_value * run_count)
            score_splits = [base_value] * run_count
            for idx in range(remainder):
                score_splits[idx] += 1
        else:
            score_splits = []

        executions: List[TestRunResultSchema] = []
        gpa_awarded = 0
        for idx, run in enumerate(executions_raw):
            run_dict = run.model_dump()
            test_meta = tests[idx]
            compare_cfg = CompareConfig()
            stdout_val = run.stdout or ""
            expected_val = test_meta.expected or ""
            mode_override = resolve_mode(getattr(test_meta, "compare_mode", None))
            config_overrides = getattr(test_meta, "compare_config", None) or {}
            comparison = await compare(
                expected_val,
                stdout_val,
                compare_cfg,
                mode=mode_override,
                compare_config=config_overrides,
            )
            override_pass = comparison.passed if run.status_id == 3 else run.passed
            run_dict["passed"] = override_pass
            run_dict["compare_mode_applied"] = comparison.mode_applied
            run_dict["normalisations_applied"] = comparison.normalisations_applied
            run_dict["comparison_attempts"] = [
                {
                    "mode": att.mode,
                    "passed": att.passed,
                    "reason": att.reason,
                    "normalisations": att.normalisations,
                    "duration_ms": att.duration_ms,
                }
                for att in (comparison.attempts or [])
            ] or None
            run_dict["why_failed"] = None if override_pass else comparison.reason
            per_test_score = score_splits[idx] if idx < len(score_splits) and override_pass else 0
            run_dict["score_awarded"] = per_test_score
            run_dict["gpa_contribution"] = per_test_score
            gpa_awarded += per_test_score
            executions.append(TestRunResultSchema(**run_dict))

        gpa_weight = MAX_QUESTION_SCORE
        times = [r.execution_time_ms for r in executions if r.execution_time_ms is not None]
        memories = [r.memory_used_kb for r in executions if r.memory_used_kb is not None]
        avg_time_ms = mean(times) if times else None
        avg_memory_kb = mean(memories) if memories else None

        time_budget_ms = bundle.max_time_ms or DEFAULT_TIME_BUDGET_MS
        memory_budget_kb = bundle.max_memory_kb or DEFAULT_MEMORY_BUDGET_KB
        if time_budget_ms <= 0:
            time_budget_ms = DEFAULT_TIME_BUDGET_MS
        if memory_budget_kb <= 0:
            memory_budget_kb = DEFAULT_MEMORY_BUDGET_KB

        if avg_time_ms is None:
            time_multiplier = 1.0
        else:
            time_multiplier = _clamp(1.0 - (avg_time_ms / time_budget_ms) * 0.4, 0.6, 1.0)
        if avg_memory_kb is None:
            memory_multiplier = 1.0
        else:
            memory_multiplier = _clamp(1.0 - (avg_memory_kb / memory_budget_kb) * 0.2, 0.7, 1.0)

        tests_passed = sum(1 for r in executions if r.passed)
        tests_total = len(executions)
        passed_all = tests_passed == tests_total and tests_total > 0
        score_ratio = (tests_passed / tests_total) if tests_total else 0.0

        attempt_multiplier = math.pow(0.9, max(0, attempt_number - 1))
        base_component = _base_elo(bundle.tier)

        if not passed_all:
            elo_delta = _fail_penalty(bundle.tier)
            elo_base = 0
            efficiency_bonus = elo_delta
        else:
            raw_delta = base_component * time_multiplier * memory_multiplier * late_multiplier * attempt_multiplier
            elo_delta = int(round(raw_delta))
            elo_base = base_component
            efficiency_bonus = elo_delta - elo_base
            perf = score_ratio * time_multiplier * memory_multiplier * late_multiplier
            scaled_score = int(round(perf * gpa_weight))
            gpa_awarded = max(gpa_awarded, scaled_score)

        if bundle.tier in _ADVANCED_TIERS and include_private and not passed_all:
            gpa_awarded = 0

        badge_tier = bundle.tier if passed_all else None

        judge0_token = next((r.token for r in executions if r.token), None)

        def _as_float(value):
            try:
                if value is None:
                    return None
                if isinstance(value, (int, float)):
                    return float(value)
                return float(str(value))
            except (TypeError, ValueError):
                return None

        status_sequence = [run.status_id for run in executions if getattr(run, 'status_id', None) is not None]
        first_failure = next((run for run in executions if not run.passed), None)
        if passed_all:
            overall_status_id = 3
        elif first_failure and first_failure.status_id is not None:
            overall_status_id = first_failure.status_id
        elif status_sequence:
            overall_status_id = status_sequence[-1]
        else:
            overall_status_id = 0

        overall_status_desc = self._status_description(overall_status_id, "unknown")

        time_candidates = []
        for run in executions:
            if run.execution_time_seconds is not None:
                time_candidates.append(run.execution_time_seconds)
            else:
                time_candidates.append(_as_float(run.execution_time))
        time_candidates = [val for val in time_candidates if val is not None]
        max_time_seconds = max(time_candidates) if time_candidates else None

        memory_candidates = [run.memory_used_kb for run in executions if run.memory_used_kb is not None]
        max_memory_kb = max(memory_candidates) if memory_candidates else None

        stdout_lines = [run.stdout for run in executions if run.stdout]
        stderr_lines = [run.stderr for run in executions if run.stderr]

        test_records = [run.model_dump() for run in executions]

        summary = {
            'status_id': overall_status_id,
            'status_description': overall_status_desc,
            'stdout': stdout_lines if stdout_lines else None,
            'stderr': stderr_lines if stderr_lines else None,
            'time': max_time_seconds,
            'wall_time': max_time_seconds,
            'memory': int(max_memory_kb) if max_memory_kb is not None else None,
            'number_of_runs': len(executions),
            'finished_at': datetime.now(timezone.utc),
            'message': 'tests_passed' if passed_all else 'tests_failed',
            'additional_files': {
                'challenge_id': challenge_id,
                'question_id': question_id,
                'attempt_id': attempt_id,
                'attempt_number': attempt_number,
                'tests_total': tests_total,
                'tests_passed': tests_passed,
                'tier': bundle.tier,
                'late_multiplier': late_multiplier,
                'include_private': include_private,
                'gpa_awarded': gpa_awarded,
            },
        }

        submission_id = None
        if persist:
            try:
                submission_id = await code_results_repository.log_test_batch(
                    user_id=user_id,
                    language_id=lang,
                    source_code=source_code,
                    token=judge0_token,
                    test_records=test_records,
                    summary=summary,
                    stdin=None,
                    expected_output=None,
                    challenge_id=challenge_id,
                    question_id=question_id,
                )
            except Exception:
                submission_id = None

        # For each passed test, optionally call the stored procedure to record progress and award ELO/badges.
        # When perform_award is False the caller intends to handle awarding in a consolidated post-step.
        if perform_award:
            try:
                client = await get_supabase()
                for tr in executions:
                    try:
                        if tr.passed:
                            badge_id_to_pass = bundle.badge_id if getattr(bundle, "badge_id", None) else None
                            await client.rpc(
                                "record_test_result_and_award",
                                {
                                    "p_profile_id": int(user_id),
                                    "p_question_id": str(question_id),
                                    "p_test_id": str(tr.test_id),
                                    "p_is_public": True,
                                    "p_passed": True,
                                    "p_public_badge_id": badge_id_to_pass,
                                },
                            ).execute()
                    except Exception:
                        # avoid failing the entire evaluation if RPC fails; log in future
                        continue
            except Exception:
                # ignore supabase client errors to keep grading robust
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
            public_passed=bool(executions and executions[0].passed),
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


    async def evaluate_question_output(
        self,
        challenge_id: str,
        question_id: str,
        output: str,
        include_private: bool = True,
        *,
        user_id: Optional[int] = None,
        perform_award: bool = True,
    ) -> QuestionEvaluationResponse:
        """Grade a provided output string against the question's tests (no Judge0 run).

        This is intended for frontends that precompute output and want immediate grading.
        """
        bundle = await self.get_question_bundle(challenge_id, question_id)
        tests = self._normalise_tests(bundle.tests)
        if not include_private:
            tests = tests[:1]
        executions_raw: List[TestRunResultSchema] = []
        for test in tests:
            expected_val = test.expected or ""
            actual_val = output or ""
            mode_override = resolve_mode(getattr(test, "compare_mode", None))
            config_overrides = getattr(test, "compare_config", None) or {}
            comparison = await compare(
                expected_val,
                actual_val,
                CompareConfig(),
                mode=mode_override,
                compare_config=config_overrides,
            )
            executions_raw.append(
                TestRunResultSchema(
                    test_id=test.id,
                    visibility=test.visibility,
                    passed=bool(comparison.passed),
                    stdout=output,
                    stderr=None,
                    compile_output=None,
                    status_id=3 if comparison.passed else 1,
                    status_description="accepted" if comparison.passed else "failed",
                    token=None,
                    execution_time=None,
                    execution_time_seconds=None,
                    execution_time_ms=None,
                    memory_used=None,
                    memory_used_kb=None,
                    compare_mode_applied=comparison.mode_applied,
                    normalisations_applied=comparison.normalisations_applied,
                    why_failed=None if comparison.passed else comparison.reason,
                    comparison_attempts=[
                        {
                            "mode": att.mode,
                            "passed": att.passed,
                            "reason": att.reason,
                            "normalisations": att.normalisations,
                            "duration_ms": att.duration_ms,
                        }
                        for att in (comparison.attempts or [])
                    ]
                    or None,
                )
            )

        run_count = len(executions_raw)
        score_splits: List[int] = []
        if run_count > 0:
            base_value = MAX_QUESTION_SCORE // run_count
            remainder = MAX_QUESTION_SCORE - (base_value * run_count)
            score_splits = [base_value] * run_count
            for idx in range(remainder):
                score_splits[idx] += 1

        executions: List[TestRunResultSchema] = []
        gpa_awarded = 0
        for idx, run in enumerate(executions_raw):
            run_dict = run.model_dump()
            per_score = score_splits[idx] if idx < len(score_splits) and run.passed else 0
            run_dict["score_awarded"] = per_score
            run_dict["gpa_contribution"] = per_score
            gpa_awarded += per_score
            executions.append(TestRunResultSchema(**run_dict))

        gpa_weight = MAX_QUESTION_SCORE
        tests_passed = sum(1 for r in executions if r.passed)
        tests_total = len(executions)
        passed_all = tests_passed == tests_total and tests_total > 0
        score_ratio = (tests_passed / tests_total) if tests_total else 0.0

        time_multiplier = 1.0
        memory_multiplier = 1.0
        attempt_multiplier = 1.0
        base_component = _base_elo(bundle.tier)

        if not passed_all:
            elo_delta = _fail_penalty(bundle.tier)
            elo_base = 0
            efficiency_bonus = elo_delta
        else:
            raw_delta = base_component * time_multiplier * memory_multiplier * 1.0 * attempt_multiplier
            elo_delta = int(round(raw_delta))
            elo_base = base_component
            efficiency_bonus = elo_delta - elo_base
            scaled_score = int(round(score_ratio * gpa_weight))
            gpa_awarded = max(gpa_awarded, scaled_score)

        if bundle.tier in _ADVANCED_TIERS and include_private and not passed_all:
            gpa_awarded = 0

        badge_tier = bundle.tier if passed_all else None

        if user_id is not None and perform_award:
            try:
                client = await get_supabase()
                for tr in executions:
                    try:
                        if tr.passed:
                            badge_id_to_pass = bundle.badge_id if getattr(bundle, "badge_id", None) else None
                            await client.rpc(
                                "record_test_result_and_award",
                                {
                                    "p_profile_id": int(user_id),
                                    "p_question_id": str(question_id),
                                    "p_test_id": str(tr.test_id),
                                    "p_is_public": True,
                                    "p_passed": True,
                                    "p_public_badge_id": badge_id_to_pass,
                                },
                            ).execute()
                    except Exception:
                        continue
            except Exception:
                pass

        return QuestionEvaluationResponse(
            challenge_id=bundle.challenge_id,
            question_id=bundle.question_id,
            tier=bundle.tier,
            language_id=bundle.language_id or DEFAULT_LANGUAGE_ID,
            gpa_weight=gpa_weight,
            gpa_awarded=gpa_awarded,
            elo_awarded=elo_delta,
            elo_base=elo_base,
            elo_efficiency_bonus=efficiency_bonus,
            public_passed=bool(executions and executions[0].passed),
            tests_passed=tests_passed,
            tests_total=tests_total,
            average_execution_time_ms=None,
            average_memory_used_kb=None,
            badge_tier_awarded=badge_tier,
            submission_id=None,
            attempt_id=None,
            attempt_number=None,
            tests=executions,
        )

    @staticmethod
    def _status_description(status_id: int, fallback: str) -> str:
        mapping = {
            1: "In Queue",
            2: "Processing",
            3: "Accepted",
            4: "Wrong Answer",
            5: "Time Limit Exceeded",
            6: "Compilation Error",
            7: "Runtime Error",
        }
        return mapping.get(status_id, fallback or "unknown")

    async def submit_challenge(
        self,
        challenge_id: str,
        attempt_id: str,
        submissions: Dict[str, str],
        language_overrides: Dict[str, int],
        question_weights: Dict[str, int],
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
        submissions: Dict[str, str],
        language_overrides: Dict[str, int],
        question_weights: Dict[str, int],
        *,
        user_id: int,
        tier: str,
        attempt_counts: Dict[str, int],
        max_attempts: int,
        late_multiplier: float,
        perform_award: bool = True,
    ) -> ChallengeSubmissionBreakdown:
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
        gpa_max = len(language_overrides) * MAX_QUESTION_SCORE
        gpa_total = 0
        base_elo_total = 0
        efficiency_total = 0
        tests_total = 0
        tests_passed_total = 0
        avg_time_inputs: List[float] = []
        avg_memory_inputs: List[float] = []
        attempt_updates: Dict[str, int] = {}

        for question_id in language_overrides.keys():
            bundle = bundle_cache.get(question_id)
            source_code = submissions.get(question_id)
            current_attempts = attempt_counts.get(question_id, 0)
            if source_code is None:
                missing_questions.append(question_id)
                continue
            if current_attempts >= max_attempts:
                fail_penalty = _fail_penalty(bundle.tier if bundle else tier)
                placeholder = TestRunResultSchema(
                    test_id=None,
                    visibility="public",
                    passed=False,
                    stdout=None,
                    stderr=None,
                    compile_output=None,
                    status_id=0,
                    status_description="attempt_limit_reached",
                    token=None,
                    execution_time=None,
                    execution_time_seconds=None,
                    execution_time_ms=None,
                    memory_used=None,
                    memory_used_kb=None,
                    score_awarded=0,
                    gpa_contribution=0,
                )
                eval_result = QuestionEvaluationResponse(
                    challenge_id=challenge_id,
                    question_id=question_id,
                    tier=bundle.tier if bundle else tier,
                    language_id=language_overrides.get(question_id) or DEFAULT_LANGUAGE_ID,
                    gpa_weight=MAX_QUESTION_SCORE,
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
                    source_code,
                    language_overrides.get(question_id) or DEFAULT_LANGUAGE_ID,
                    include_private=True,
                    bundle=bundle,
                    user_id=user_id,
                    attempt_number=current_attempts + 1,
                    late_multiplier=late_multiplier,
                    attempt_id=attempt_id,
                    perform_award=perform_award,
                    persist=True,
                )
                attempt_updates[question_id] = attempt_updates.get(question_id, 0) + 1

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

        if attempt_updates:
            try:
                await challenge_repository.record_question_attempts(
                    attempt_id,
                    attempt_updates,
                    max_attempts=max_attempts,
                )
            except Exception:
                pass

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


