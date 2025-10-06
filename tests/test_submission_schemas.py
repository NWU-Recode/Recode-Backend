import pytest

from app.features.submissions.endpoints import BatchSubmissionsPayload
from app.features.submissions.schemas import BatchSubmissionEntry, QuestionEvaluationRequest


def test_question_evaluation_request_allows_empty_output():
    model = QuestionEvaluationRequest(output="")
    assert model.output == ""
    assert model.source_code is None


def test_question_evaluation_request_requires_some_payload():
    with pytest.raises(ValueError):
        QuestionEvaluationRequest()


def test_batch_submission_entry_requires_source_code():
    entry = BatchSubmissionEntry(source_code="print(42)")
    assert entry.source_code == "print(42)"


def test_batch_submission_entry_forbids_blank_source_code():
    with pytest.raises(ValueError):
        BatchSubmissionEntry(source_code=" ")


def test_batch_submissions_payload_casts_entries():
    payload = BatchSubmissionsPayload(submissions={"q1": {"source_code": "print(1)"}})
    assert "q1" in payload.submissions
    sub = payload.submissions["q1"]
    assert isinstance(sub, BatchSubmissionEntry)
    assert sub.source_code == "print(1)"


def test_batch_submissions_payload_limits_size():
    submissions = {f"q{i}": {"source_code": "print(\"a\")"} for i in range(6)}
    with pytest.raises(ValueError):
        BatchSubmissionsPayload(submissions=submissions)
