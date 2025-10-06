import pytest

from app.features.judge0.schemas import CodeExecutionResult
from app.features.judge0.service import judge0_service
from app.features.submissions.schemas import QuestionBundleSchema, QuestionTestSchema
from app.features.submissions.service import submissions_service

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_evaluate_question_uses_tests_not_question_expected():
    bundle = QuestionBundleSchema(
        challenge_id="challenge-1",
        question_id="question-1",
        title="",
        prompt="",
        starter_code="",
        reference_solution=None,
        expected_output="WRONG",
        tier="base",
        language_id=71,
        points=100,
        tests=[
            QuestionTestSchema(
                id="test-1",
                question_id="question-1",
                input="",
                expected="EXPECTED",
                visibility="public",
                order_index=0,
            )
        ],
    )

    result = await submissions_service.evaluate_question(
        challenge_id="challenge-1",
        question_id="question-1",
        submitted_output="EXPECTED",
        source_code=None,
        language_id=None,
        include_private=True,
        bundle=bundle,
        user_id=12345,
        attempt_number=1,
        attempt_id=None,
        late_multiplier=1.0,
        record_result=False,
    )

    assert result.public_passed is True
    assert result.tests_total == 1
    assert result.tests[0].expected_output == "EXPECTED"


@pytest.mark.anyio("asyncio")
async def test_evaluate_question_requires_tests():
    bundle = QuestionBundleSchema(
        challenge_id="challenge-1",
        question_id="question-1",
        title="",
        prompt="",
        starter_code="",
        reference_solution=None,
        expected_output=None,
        tier="base",
        language_id=71,
        points=100,
        tests=[],
    )

    with pytest.raises(ValueError, match="question_missing_tests"):
        await submissions_service.evaluate_question(
            challenge_id="challenge-1",
            question_id="question-1",
            submitted_output="whatever",
            source_code=None,
            language_id=None,
            include_private=True,
            bundle=bundle,
            user_id=12345,
            attempt_number=1,
            attempt_id=None,
            late_multiplier=1.0,
            record_result=False,
        )


@pytest.mark.anyio("asyncio")
async def test_evaluate_question_populates_stdout_with_judge0(monkeypatch):
    bundle = QuestionBundleSchema(
        challenge_id="challenge-stdout",
        question_id="question-stdout",
        title="",
        prompt="",
        starter_code="",
        reference_solution=None,
        expected_output=None,
        tier="base",
        language_id=71,
        points=100,
        tests=[
            QuestionTestSchema(
                id="test-1",
                question_id="question-stdout",
                input="2\n",
                expected="4",
                visibility="public",
                order_index=0,
            ),
            QuestionTestSchema(
                id="test-2",
                question_id="question-stdout",
                input="3\n",
                expected="9",
                visibility="public",
                order_index=1,
            ),
        ],
    )

    expected_outs = ["4", "9"]

    async def fake_execute_batch(submissions, timeout_seconds=None):
        assert len(submissions) == 2
        results = []
        for idx, submission in enumerate(submissions):
            results.append(
                (
                    f"tok-{idx}",
                    CodeExecutionResult(
                        submission_id=None,
                        stdout=expected_outs[idx],
                        stderr=None,
                        compile_output=None,
                        execution_time="0.01",
                        memory_used=64,
                        status_id=3,
                        status_description="Accepted",
                        language_id=submission.language_id,
                        success=True,
                    ),
                )
            )
        return results

    monkeypatch.setattr(judge0_service, "execute_batch", fake_execute_batch)

    result = await submissions_service.evaluate_question(
        challenge_id="challenge-stdout",
        question_id="question-stdout",
        submitted_output=None,
        source_code="print(int(input()) ** 2)",
        language_id=71,
        include_private=True,
        bundle=bundle,
        user_id=1234,
        attempt_number=1,
        attempt_id=None,
        late_multiplier=1.0,
        record_result=False,
    )

    assert [test.stdout for test in result.tests] == expected_outs
    assert all(test.token.startswith("tok-") for test in result.tests if test.token)
    assert result.public_passed is True
