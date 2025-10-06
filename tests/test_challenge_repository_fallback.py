import pytest

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"

from app.features.challenges import repository as challenge_repo_module
from app.features.challenges.repository import ChallengeRepository


@pytest.mark.anyio("asyncio")
async def test_create_or_get_open_attempt_falls_back_to_local(monkeypatch):
    challenge_repo_module._LOCAL_ATTEMPTS.clear()
    challenge_repo_module._LOCAL_ATTEMPT_IDS.clear()
    challenge_repo_module._LOCAL_FALLBACK_NOTICE_EMITTED = False

    async def fake_get_supabase():
        raise Exception("Could not find the table 'public.challenge_attempts' in the schema cache")

    async def fake_build_snapshot(self, challenge_id):
        return [
            {
                "question_id": "q1",
                "expected_output": "42",
                "language_id": 71,
                "attempts_used": 0,
            }
        ]

    monkeypatch.setattr(challenge_repo_module, "get_supabase", fake_get_supabase)
    monkeypatch.setattr(ChallengeRepository, "_build_snapshot", fake_build_snapshot, raising=False)

    repo = ChallengeRepository()

    attempt = await repo.create_or_get_open_attempt("challenge-1", 12345)

    assert attempt.get("_local") is True
    assert attempt["challenge_id"] == "challenge-1"
    assert str(attempt["user_id"]) == "12345"
    assert attempt.get("snapshot_questions")

    again = await repo.get_open_attempt("challenge-1", 12345)
    assert again is not None
    assert again.get("id") == attempt.get("id")
    assert again.get("_local") is True
