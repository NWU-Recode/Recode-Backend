# app/features/dashboard/tests/test_dashboard.py

import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.features.dashboard.endpoints import router as dashboard_router
from app.common.deps import CurrentUser, get_current_user


test_app = FastAPI()
test_app.include_router(dashboard_router)


# Fake admin user

fake_admin = CurrentUser(
    id=uuid.UUID("2rgrt5ythu-vsdgdfhgf-jfjh5fbdfgh"),
    email="alice@test.com",
    full_name="Alice",
    role="admin",
)


# Overridin dependency

def override_get_current_user():
    return fake_admin

test_app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(test_app)



# Tests

def test_dashboard_summary():
    resp = client.get("/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    print("\nDashboard Summary:", data)
    # Expected from fakesupabase: 3 profiles (2 active), 2 challenges, 3 attempts
    assert data["total_users"] == 3
    assert data["active_users"] == 2
    assert data["total_challenges"] == 2
    assert data["total_submissions"] == 3


def test_dashboard_leaderboard():
    resp = client.get("/dashboard/leaderboard?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    print("\nLeaderboard:", data)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["score"] >= data[-1]["score"]  #sorted in desending order


def test_dashboard_user_view(monkeypatch):
    # Fake challenge + attempts
    fake_challenges = [
        {"id": "chal1", "title": "Bronze Challenge 1", "tier": "bronze", "sequence_index": 1},
        {"id": "chal2", "title": "Silver Challenge 1", "tier": "silver", "sequence_index": 6},
    ]
    fake_attempts = [{"challenge_id": "chal1", "status": "submitted"}]
    fake_q_attempts = [{"is_correct": True}, {"is_correct": False}]

    
    
    from app.features.challenges import repository as challenge_repo
    from app.features.questions import repository as question_repo
    monkeypatch.setattr(challenge_repo.challenge_repository, "list_challenges", lambda: fake_challenges)
    monkeypatch.setattr(challenge_repo.challenge_repository, "list_user_attempts", lambda uid: fake_attempts)
    monkeypatch.setattr(
        question_repo.question_repository,
        "list_latest_attempts_for_challenge",
        lambda cid, uid: fake_q_attempts,
    )

    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    data = resp.json()
    print("\nDashboard:", data)

    assert isinstance(data, list)
    assert data[0]["state"] == "submitted"
    assert data[0]["progress"] == {"passed": 1, "total": 10}


# Allow running directly

if __name__ == "__main__":
    test_dashboard_summary()
    test_dashboard_leaderboard()
   
    #Couldn't test test_dashboard_user_view() because monkeypatch isn't available outside pytest