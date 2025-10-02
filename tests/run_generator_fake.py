import os
import sys
import asyncio
import pprint
from pathlib import Path

# Ensure project root is on sys.path so `import app` finds local package
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure generator uses the fallback payload (no external model calls)
os.environ.setdefault("GENERATOR_FAKE", "1")

from app.features.challenges import challenge_pack_generator as genmod

class Resp:
    def __init__(self, data):
        self.data = data

class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self._select_args = None
        self._filters = []
        self._order = None
        self._limit = None
        self._insert_payload = None
        self._update_payload = None

    def select(self, *args, **kwargs):
        self._select_args = args
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        return self

    def order(self, *args, **kwargs):
        self._order = (args, kwargs)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def update(self, payload):
        self._update_payload = payload
        return self

    async def execute(self):
        # Simulate behavior based on table and operation
        # Existence checks should return empty list (no duplicates)
        if self._insert_payload is not None:
            # Simulate create: attach an id
            payload = dict(self._insert_payload)
            payload.setdefault('id', 9999)
            # simple tracking
            self.client._data.setdefault(self.table_name, []).append(payload)
            return Resp([payload])
        if self._update_payload is not None:
            # Simulate update returning updated rows
            # naive: find first row matching eq id filter and apply update
            for (f,v) in self._filters:
                if f == 'id':
                    rows = self.client._data.get(self.table_name, [])
                    for row in rows:
                        if str(row.get('id')) == str(v):
                            row.update(self._update_payload)
                            return Resp([row])
            return Resp([])
        # Default: return rows matching filters
        rows = self.client._data.get(self.table_name, [])
        # naive filter: if filters present, filter exact matches
        def match(row):
            for f,v in self._filters:
                # support nested trigger_event->>week check by key name
                if '->>' in f:
                    # e.g., trigger_event->>week
                    left, right = f.split('->>')
                    left = left.strip()
                    right = right.strip()
                    val = None
                    te = row.get(left)
                    if isinstance(te, dict):
                        val = te.get(right)
                    if val is None:
                        return False
                    if str(val) != str(v):
                        return False
                    continue
                if str(row.get(f)) != str(v):
                    return False
            return True
        matched = [r for r in rows if match(r)]
        return Resp(matched)

class FakeClient:
    def __init__(self):
        # seed with an empty challenges table
        self._data = {
            # 'challenges': []
        }

    def table(self, name):
        return FakeQuery(self, name)

async def fake_get_supabase():
    return FakeClient()

# Monkeypatch the module's get_supabase to avoid real DB usage
genmod.get_supabase = fake_get_supabase

async def main():
    print('Running generate_and_save_tier with GENERATOR_FAKE=1 and fake DB client')
    try:
        result = await genmod.generate_and_save_tier(
            tier='diamond',
            week=12,
            slide_stack_id=None,
            module_code='CS101',
            lecturer_id=42,
            semester_id='2025S1',
        )
        pprint.pprint(result)
    except Exception as exc:
        print('Error during generation:')
        raise

if __name__ == '__main__':
    asyncio.run(main())
