from __future__ import annotations

from dataclasses import dataclass
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

    def elo_per_private(self, tier: Optional[str], private_count: int) -> int:
        weight = self.gpa_weight(tier)
        if private_count <= 0:
            return 0
        return int(round(weight / private_count))


_GRADING_WEIGHTS = _GradingWeights(
    gpa_by_tier={
        "bronze": 10,
        "silver": 20,
        "gold": 40,
        "ruby": 40,
        "emerald": 60,
        "diamond": 100,
    }
)


class SubmissionsService:
    """Wrapper responsible for bundling tests and grading submissions."""

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
            memory_used=result.memory_used,
        )

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
        tests = bundle.tests
        if not tests:
            raise ValueError("question_missing_tests")
        ordered_tests: List[QuestionTestSchema] = tests if include_private else [tests[0]]
        results: List[TestRunResultSchema] = []
        for test in ordered_tests:
            results.append(await self._execute_test(source_code, lang, test))
        public_result = next((r for r in results if r.visibility == "public"), None)
        public_passed = bool(public_result.passed) if public_result else False
        private_results = [r for r in results if r.visibility != "public"]
        private_passes = sum(1 for r in private_results if r.passed)
        gpa_weight = _GRADING_WEIGHTS.gpa_weight(bundle.tier)
        gpa_awarded = gpa_weight if public_passed else 0
        elo_increment_per = _GRADING_WEIGHTS.elo_per_private(bundle.tier, len(private_results))
        elo_awarded = elo_increment_per * private_passes
        return QuestionEvaluationResponse(
            challenge_id=bundle.challenge_id,
            question_id=bundle.question_id,
            tier=bundle.tier,
            language_id=lang,
            gpa_weight=gpa_weight,
            gpa_awarded=gpa_awarded,
            elo_awarded=elo_awarded,
            public_passed=public_passed,
            tests=results,
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
        bundle_cache: Dict[str, QuestionBundleSchema] = {}
        for qid in language_overrides.keys():
            try:
                bundle_cache[qid] = await self.get_question_bundle(challenge_id, qid)
            except ValueError:
                continue
        gpa_total = 0
        gpa_max = sum(
            _GRADING_WEIGHTS.gpa_weight(bundle_cache[qid].tier)
            if qid in bundle_cache
            else question_weights.get(qid, 0)
            for qid in language_overrides.keys()
        )
        elo_total = 0
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
            elo_total += int(eval_result.elo_awarded)
            if eval_result.public_passed:
                passed_questions.append(question_id)
            else:
                failed_questions.append(question_id)
            results.append(ChallengeQuestionResultSchema(**eval_result.model_dump()))
        missing_questions = [qid for qid in language_overrides.keys() if qid not in submissions]
        return ChallengeSubmissionBreakdown(
            challenge_id=challenge_id,
            attempt_id=attempt_id,
            gpa_score=gpa_total,
            gpa_max_score=gpa_max,
            elo_delta=elo_total,
            passed_questions=passed_questions,
            failed_questions=failed_questions,
            missing_questions=missing_questions,
            question_results=results,
        )


submissions_service = SubmissionsService()

__all__ = ["submissions_service", "SubmissionsService"]
