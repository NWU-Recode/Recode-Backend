from __future__ import annotations

import asyncio
from dataclasses import dataclass
from statistics import mean
from typing import Dict, List, Optional

from app.features.judge0.schemas import CodeSubmissionCreate, CodeExecutionResult
from app.features.judge0.service import judge0_service
from app.features.submissions.repository import submissions_repository
from app.features.submissions.schemas import (
    ChallengeQuestionResultSchema,
    ChallengeSubmissionBreakdown,
    QuestionBundleSchema,
    QuestionEvaluationResponse,
    QuestionTestSchema,
    TestRunResultSchema,
)


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
        "bronze": 10,
        "silver": 20,
        "gold": 40,
        "ruby": 100,
        "emerald": 100,
        "diamond": 100,
    }
)

_ADVANCED_TIERS = {"ruby", "emerald", "diamond"}
_TEST_ELO = {"public": 200, "private": 300}


class SubmissionsService:
    async def get_question_bundle(self, challenge_id: str, question_id: str) -> QuestionBundleSchema:
        question = await submissions_repository.get_question(question_id)
        if not question:
            raise ValueError("question_not_found")
        tests_raw = await submissions_repository.list_tests(question_id)
        tests = [QuestionTestSchema(**test) for test in tests_raw]
        tier = (question.get("tier") or "").lower() or None
        weight = _GRADING_WEIGHTS.gpa_weight(tier)
        if not weight:
            weight = int(question.get("points") or _GRADING_WEIGHTS.default)
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
            language_id=int(question.get("language_id") or 71),
            points=weight,
            max_time_ms=max_time_ms,
            max_memory_kb=max_memory_kb,
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
        status_description = str(result.status_description)
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
        public_tests = [t for t in tests if t.visibility == "public"]
        if not public_tests:
            raise ValueError("question_missing_public_test")
        primary_public = min(public_tests, key=lambda t: t.order_index)
        private_tests = [t for t in tests if t.visibility != "public"]
        if len(private_tests) < 2:
            raise ValueError("question_missing_private_tests")
        ordered_privates = sorted(private_tests, key=lambda t: t.order_index)
        return [primary_public] + ordered_privates

    def _alloc_gpa(self, weight: int, count: int) -> List[int]:
        if count <= 0:
            return []
        if count == 1:
            return [weight]
        if count == 2:
            first = weight // 2
            second = weight - first
            return [first, second]
        first = weight // 2
        second = weight // 4
        remaining = weight - first - second
        shares = [first, second, remaining]
        if count > 3:
            shares.extend([0] * (count - 3))
        return shares[:count]

    def _compute_efficiency(self, times: List[float], memories: List[int]) -> tuple[int, Optional[float], Optional[float]]:
        avg_time_ms = (mean(times) * 1000) if times else None
        avg_memory_kb = mean(memories) if memories else None
        bonus = 0
        if avg_time_ms is not None:
            if avg_time_ms <= 1000:
                bonus += 50
            elif avg_time_ms <= 2000:
                bonus += 25
        if avg_memory_kb is not None:
            if avg_memory_kb <= 65536:
                bonus += 50
            elif avg_memory_kb <= 131072:
                bonus += 25
        return bonus, avg_time_ms, avg_memory_kb

    async def evaluate_question(
        self,
        challenge_id: str,
        question_id: str,
        source_code: str,
        language_id: Optional[int] = None,
        include_private: bool = True,
        bundle: QuestionBundleSchema | None = None,
    ) -> QuestionEvaluationResponse:
        if bundle is None:
            bundle = await self.get_question_bundle(challenge_id, question_id)
        lang = int(language_id or bundle.language_id or 71)
        tests = self._normalise_tests(bundle.tests)
        if not include_private:
            tests = tests[:1]
        if not tests:
            raise ValueError("question_missing_tests")
        executions = await asyncio.gather(
            *[self._execute_test(source_code, lang, test) for test in tests]
        )
        gpa_weight = bundle.points or _GRADING_WEIGHTS.gpa_weight(bundle.tier)
        gpa_shares = self._alloc_gpa(gpa_weight, len(tests))
        scored_results: List[TestRunResultSchema] = []
        times: List[float] = []
        memories: List[int] = []
        for idx, result in enumerate(executions):
            base_score = _TEST_ELO[result.visibility] if result.passed else 0
            gpa_contribution = gpa_shares[idx] if idx < len(gpa_shares) and result.passed else 0
            if result.execution_time_seconds is not None:
                times.append(result.execution_time_seconds)
            if result.memory_used_kb is not None:
                memories.append(result.memory_used_kb)
            scored_results.append(
                result.model_copy(
                    update={
                        "score_awarded": base_score,
                        "gpa_contribution": gpa_contribution,
                    }
                )
            )
        public_result = scored_results[0]
        public_passed = bool(public_result.passed)
        tests_passed = sum(1 for r in scored_results if r.passed)
        tests_total = len(scored_results)
        base_elo = sum(r.score_awarded for r in scored_results)
        efficiency_bonus, avg_time_ms, avg_mem_kb = self._compute_efficiency(times, memories)
        gpa_awarded = sum(r.gpa_contribution for r in scored_results)
        if bundle.tier in _ADVANCED_TIERS and include_private and not public_passed:
            gpa_awarded = 0
        badge_tier = bundle.tier if public_passed else None
        return QuestionEvaluationResponse(
            challenge_id=bundle.challenge_id,
            question_id=bundle.question_id,
            tier=bundle.tier,
            language_id=lang,
            gpa_weight=gpa_weight,
            gpa_awarded=gpa_awarded,
            elo_awarded=base_elo + efficiency_bonus,
            elo_base=base_elo,
            elo_efficiency_bonus=efficiency_bonus,
            public_passed=public_passed,
            tests_passed=tests_passed,
            tests_total=tests_total,
            average_execution_time_ms=avg_time_ms,
            average_memory_used_kb=avg_mem_kb,
            badge_tier_awarded=badge_tier,
            tests=scored_results,
        )

    async def grade_challenge_submission(
        self,
        challenge_id: str,
        attempt_id: str,
        submissions: Dict[str, str],
        language_overrides: Dict[str, int],
        question_weights: Dict[str, int],
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
        for question_id, source_code in submissions.items():
            bundle = bundle_cache.get(question_id)
            eval_result = await self.evaluate_question(
                challenge_id,
                question_id,
                source_code,
                language_overrides.get(question_id),
                include_private=True,
                bundle=bundle,
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
            if eval_result.public_passed:
                passed_questions.append(question_id)
                if eval_result.badge_tier_awarded:
                    badge_tiers.append(eval_result.badge_tier_awarded)
            else:
                failed_questions.append(question_id)
            results.append(ChallengeQuestionResultSchema(**eval_result.model_dump()))
        missing_questions = [qid for qid in language_overrides.keys() if qid not in submissions]
        average_execution_time_ms = mean(avg_time_inputs) if avg_time_inputs else None
        average_memory_used_kb = mean(avg_memory_inputs) if avg_memory_inputs else None
        dedup_badges: List[str] = []
        for tier in badge_tiers:
            if tier and tier not in dedup_badges:
                dedup_badges.append(tier)
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

__all__ = ["submissions_service", "SubmissionsService"]

