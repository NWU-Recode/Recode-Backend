from fastapi.testclient import TestClient
from app.main import app
from app.auth import service as auth_service
from app.features.users import endpoints as user_endpoints


client = TestClient(app)


def test_read_users(monkeypatch):
    async def fake_get_all_users():
        return [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "test@example.com",
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]

    async def override_get_current_user():
        return {"id": "test-user"}

    monkeypatch.setattr(user_endpoints, "get_all_users", fake_get_all_users)
    app.dependency_overrides[auth_service.get_current_user] = override_get_current_user

    response = client.get("/users/")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["email"] == "test@example.com"
