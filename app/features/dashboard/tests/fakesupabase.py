# app/db/fakesupabase.py

class FakeResult:
    def __init__(self, data):
        self.data = data
        self.count = len(data)

class FakeTable:
    def __init__(self, data):
        self._base = list(data)
        self._filters = []

    def select(self, *args, **kwargs):
        return self

    def eq(self, field, value):
        self._filters.append(lambda r: r.get(field) == value)
        return self

    def in_(self, field, values):
        values_set = set(values or [])
        self._filters.append(lambda r: r.get(field) in values_set)
        return self

    def execute(self):
        filtered = [row for row in self._base if all(f(row) for f in self._filters)]
        return FakeResult(filtered)

class FakeSupabase:
    def __init__(self):
        self._tables = {
            "profiles": [
                {"id": "user1", "full_name": "Alice", "email": "alice@test.com", "is_active": True},
                {"id": "user2", "full_name": "Bob", "email": "bob@test.com", "is_active": True},
                {"id": "user3", "full_name": "Charlie", "email": "charlie@test.com", "is_active": False},
            ],
            "challenges": [
                {"id": "chal1", "title": "Bronze Challenge 1", "tier": "bronze", "sequence_index": 1},
                {"id": "chal2", "title": "Silver Challenge 1", "tier": "silver", "sequence_index": 6},
            ],
            "challenge_attempts": [
                {"id": "att1", "user_id": "user1", "challenge_id": "chal1", "score": 80},
                {"id": "att2", "user_id": "user1", "challenge_id": "chal2", "score": 100},
                {"id": "att3", "user_id": "user2", "challenge_id": "chal1", "score": 50},
            ],
        }

    def table(self, name: str):
        return FakeTable(self._tables.get(name, []))

def get_supabase():
    return FakeSupabase()
