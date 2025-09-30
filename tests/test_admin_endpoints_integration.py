import sys
import types
import datetime
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

# Provide a lightweight dummy module for app.demo.timekeeper so importing app.main
# (which imports slides endpoints that reference timekeeper) doesn't fail during test collection.
timekeeper = types.ModuleType("app.demo.timekeeper")
_offsets = {"global": 0, "modules": {}}

def add_demo_week_offset(delta):
    _offsets["global"] += int(delta)
    return _offsets["global"]

def set_demo_week_offset(offset):
    _offsets["global"] = int(offset)
    return _offsets["global"]

def clear_demo_week_offset():
    _offsets["global"] = 0

def get_demo_week_offset():
    return _offsets["global"]

def add_demo_week_offset_for_module(module_code, delta):
    m = _offsets["modules"]
    m[module_code] = m.get(module_code, 0) + int(delta)
    return m[module_code]

def set_demo_week_offset_for_module(module_code, offset):
    _offsets["modules"][module_code] = int(offset)
    return _offsets["modules"][module_code]

def clear_demo_week_offset_for_module(module_code):
    _offsets["modules"][module_code] = 0

def get_demo_week_offset_for_module(module_code):
    return _offsets["modules"].get(module_code, 0)

def apply_demo_offset_to_semester_start(semester_start, module_code=None):
    # semester_start is a date; apply week offset
    weeks = get_demo_week_offset_for_module(module_code) if module_code else get_demo_week_offset()
    return semester_start + datetime.timedelta(weeks=weeks)

timekeeper.add_demo_week_offset = add_demo_week_offset
timekeeper.set_demo_week_offset = set_demo_week_offset
timekeeper.clear_demo_week_offset = clear_demo_week_offset
timekeeper.get_demo_week_offset = get_demo_week_offset
timekeeper.add_demo_week_offset_for_module = add_demo_week_offset_for_module
timekeeper.set_demo_week_offset_for_module = set_demo_week_offset_for_module
timekeeper.clear_demo_week_offset_for_module = clear_demo_week_offset_for_module
timekeeper.get_demo_week_offset_for_module = get_demo_week_offset_for_module
timekeeper.apply_demo_offset_to_semester_start = apply_demo_offset_to_semester_start

# Insert into sys.modules so import paths resolve
sys.modules["app.demo.timekeeper"] = timekeeper

from app.main import app

# Use the admin bearer token provided by the user
ADMIN_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IkhNaUlHZ2I2WnZTblhlS3QiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2d0b2VodmxvZHJtbXF6eXhvYWlsLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiJhM2E4NTM4Yi03YTVkLTQzZWQtODI2Zi0wZGVjNzU0MWFlN2EiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU5MTkxNDQ4LCJpYXQiOjE3NTkxODc4NDgsImVtYWlsIjoicmVjb2RlcHJvamVjdDBAZ21haWwuY29tIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6eyJlbWFpbCI6InJlY29kZXByb2plY3QwQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmdWxsX25hbWUiOiJUZXN0IFVzZXIiLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInN1YiI6ImEzYTg1MzhiLTdhNWQtNDNlZC04MjZmLTBkZWM3NTQxYWU3YSJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6InBhc3N3b3JkIiwidGltZXN0YW1wIjoxNzU5MTg3ODQ4fV0sInNlc3Npb25faWQiOiIxYTg5OTA0MC00YWQzLTQ5MmItOThhMi1mNzkyODcyMmQ1NzQiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.D__ofqtPT2XWYYBOO7_LnbNQf5r3imKZxNEYm8qdasg"


class DummyUser:
    def __init__(self, id, email):
        self.id = id
        self.email = email
        self.user_metadata = {"email": email, "full_name": "Test User"}


class DummyAuthResponse:
    def __init__(self, user):
        self.user = user


@pytest.fixture(autouse=True)
def mock_supabase_and_profiles(monkeypatch):
    """Mock external Supabase client and profile provisioning to avoid network calls."""

    async def fake_get_supabase():
        class Client:
            class auth:
                @staticmethod
                async def get_user(token):
                    # Return a dummy user object similar to supabase client
                    return DummyAuthResponse(DummyUser("a3a8538b-7a5d-43ed-826f-0dec7541ae7a", "recodeproject0@gmail.com"))

        return Client()

    async def fake_ensure_profile_provisioned(supabase_id, email, full_name=None):
        # Mimic a DB-backed profile with admin role and numeric id
        return {"id": 1, "email": email, "role": "admin", "supabase_id": supabase_id}

    # Patch both the DB helper and the name imported into app.common.deps
    monkeypatch.setattr("app.DB.supabase.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.common.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.features.profiles.service.ensure_profile_provisioned", fake_ensure_profile_provisioned)
    monkeypatch.setattr("app.common.deps.ensure_user_provisioned", fake_ensure_profile_provisioned)


def test_admin_demo_endpoints_auth_success():
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

    # Skip weeks (POST /admin/demo/skip)
    r = client.post("/admin/demo/skip", headers=headers, params={"delta": 2})
    assert r.status_code == 200
    assert "offset_weeks" in r.json()

    # Set weeks (POST /admin/demo/set)
    r2 = client.post("/admin/demo/set", headers=headers, params={"offset": 3})
    assert r2.status_code == 200
    assert r2.json().get("offset_weeks") == 3

    # Clear weeks (DELETE /admin/demo/clear)
    r3 = client.delete("/admin/demo/clear", headers=headers)
    assert r3.status_code == 200
    assert r3.json().get("offset_weeks") == 0


def test_admin_demo_endpoints_forbidden_when_not_admin(monkeypatch):
    # Make ensure_profile_provisioned return non-admin role
    async def fake_ensure_profile_provisioned_nonadmin(supabase_id, email, full_name=None):
        return {"id": 2, "email": email, "role": "student", "supabase_id": supabase_id}

    # Patch the function used by the auth dependency so role is honored
    monkeypatch.setattr("app.common.deps.ensure_user_provisioned", fake_ensure_profile_provisioned_nonadmin)

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

    r = client.post("/admin/demo/skip", headers=headers, params={"delta": 1})
    assert r.status_code == 403


def test_admin_create_semester_and_module_and_assign_lecturer(monkeypatch):
    """Test flow: create semester -> create module referencing that semester -> assign lecturer to module.

    We'll mock repository methods to simulate Supabase insert/select calls and ensure the endpoints
    return the expected shapes and status codes.
    """
    from uuid import uuid4
    import datetime

    # Prepare dummy semester row returned by repository
    sem_id = str(uuid4())
    semester_row = {
        "id": sem_id,
        "year": 2026,
        "term_name": "Test Term",
        "start_date": datetime.date(2026, 1, 1),
        "end_date": datetime.date(2026, 6, 30),
        "is_current": True,
    }

    # Mock ModuleRepository.create_semester to return our semester_row
    async def fake_create_semester(year, term_name, start_date, end_date, is_current=False):
        return {**semester_row}

    # For module creation, return a module dict including the semester id
    module_id = str(uuid4())
    module_row = {
        "id": module_id,
        "code": "CS999",
        "name": "Integration Test Module",
        "description": "Test module",
        "semester_id": sem_id,
        "lecturer_id": 0,
        "code_language": "Python",
        "credits": 8,
        "created_at": datetime.datetime.now(datetime.timezone.utc),
        "updated_at": datetime.datetime.now(datetime.timezone.utc),
    }

    async def fake_create_module(module_payload, lecturer_id):
        return {**module_row}

    # For assign_lecturer_by_code, return the module updated with lecturer_id
    assigned_row = {**module_row, "lecturer_id": 123}

    async def fake_assign_lecturer_by_code(module_code, lecturer_profile_id, fallback_module_id=None):
        return [assigned_row]

    # Patch repository methods used by ModuleService
    monkeypatch.setattr("app.features.admin.repository.ModuleRepository.create_semester", fake_create_semester)
    monkeypatch.setattr("app.features.admin.repository.ModuleRepository.create_module", fake_create_module)
    monkeypatch.setattr("app.features.admin.repository.ModuleRepository.assign_lecturer_by_code", fake_assign_lecturer_by_code)

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

    # Create semester via admin endpoint
    payload = {
        "year": 2026,
        "term_name": "Test Term",
        "start_date": "2026-01-01T00:00:00",
        "end_date": "2026-06-30T00:00:00",
        "is_current": True,
    }
    r_sem = client.post("/admin/semesters", headers=headers, json=payload)
    assert r_sem.status_code == 200, r_sem.text
    sem_json = r_sem.json()
    assert sem_json.get("year") == 2026

    # Create module via admin endpoint
    module_payload = {
        "code": "CS999",
        "name": "Integration Test Module",
        "description": "Test module",
        "semester_id": sem_id,
        "lecturer_id": 0,
        "code_language": "Python",
        "credits": 8,
    }
    r_mod = client.post("/admin/", headers=headers, json=module_payload)
    assert r_mod.status_code == 200, r_mod.text
    mod_json = r_mod.json()
    assert mod_json.get("code") == "CS999"

    # Assign lecturer to module (module_code path based)
    assign_payload = {"lecturer_id": 123}
    r_assign = client.post(f"/admin/{module_row['code']}/assign-lecturer", headers=headers, json=assign_payload)
    assert r_assign.status_code == 200, r_assign.text
    assign_json = r_assign.json()
    # assign_lecturer_by_code returns list (from repo select), ensure lecturer_id updated
    # If repo returns list, the endpoint returns that list; otherwise it'll return object
    if isinstance(assign_json, list):
        assert assign_json[0].get("lecturer_id") == 123
    else:
        assert assign_json.get("lecturer_id") == 123
