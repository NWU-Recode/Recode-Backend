import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from app.features.module import repository as repo
from app.features.module.service import ModuleService


def test_assign_and_remove_by_code(monkeypatch):
    # Mock repository ModuleRepository staticmethods
    monkeypatch.setattr(repo.ModuleRepository, 'assign_lecturer_by_code', AsyncMock(return_value={'id': 'mod-uuid', 'lecturer_id': 123}))
    monkeypatch.setattr(repo.ModuleRepository, 'remove_lecturer_by_code', AsyncMock(return_value={'id': 'mod-uuid', 'lecturer_id': None}))

    async def run():
        res = await ModuleService.assign_lecturer_by_code('CS101', 123)
        assert res is not None
        assert res.get('lecturer_id') == 123

        res2 = await ModuleService.remove_lecturer_by_code('CS101')
        assert res2 is not None
        assert res2.get('lecturer_id') is None

    asyncio.get_event_loop().run_until_complete(run())
