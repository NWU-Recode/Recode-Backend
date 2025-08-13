import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "dummy-key")

from app.db import client as db_client
from app.api.endpoints import users as users_endpoint
from main import app

class DummyResult:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error

class DummyTable:
    def select(self, query):
        return self

    def execute(self):
        return DummyResult(data=[{"id": 1, "name": "Alice"}])

class DummySupabase:
    def table(self, name):
        assert name == "users"
        return DummyTable()

def test_list_users_returns_data(monkeypatch):
    dummy_supabase = DummySupabase()
    monkeypatch.setattr(db_client, "supabase", dummy_supabase)
    monkeypatch.setattr(users_endpoint, "supabase", dummy_supabase)

    client = TestClient(app)
    response = client.get("/users")
    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "Alice"}]
