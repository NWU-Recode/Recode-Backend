from __future__ import annotations
from typing import Dict, Any, List
from .repository import challenge_repository
from .schemas import ChallengeSubmitRequest, ChallengeSubmitResponse


async def get_current_elo(self, user_id: str) -> int:
    """Get user's current ELO from user_elo table"""
    query = "SELECT current_elo FROM user_elo WHERE student_id = $1"
    row = await self.db.fetchrow(query, user_id)
    return row['current_elo'] if row else 0  # return 0 if not found

async def get_current_title_from_profile(self, user_id: str) -> dict:
    
    """Get user's current title from profiles table (after trigger updated it)"""
    query = """
        SELECT t.id, t.name, t.min_elo, t.icon_url
        FROM profiles p
        JOIN titles t ON p.title_id = t.id
        WHERE p.id = $1
    """
    row = await self.db.fetchrow(query, user_id)
    if row:
        return {
            "id": row['id'],
            "name": row['name'],
            "min_elo": row['min_elo'],
            "icon_url": row['icon_url']
        }
    return await self.get_default_title()

async def get_title_for_elo(self, elo: int) -> dict:
    """Gets the appropriate title for given ELO"""
    query = """
        SELECT id, name, min_elo, icon_url
        FROM titles
        WHERE min_elo <= $1
        ORDER BY min_elo DESC
        LIMIT 1
    """
    row = await self.db.fetchrow(query, elo)
    if row:
        return {
            "id": row['id'],
            "name": row['name'],
            "min_elo": row['min_elo'],
            "icon_url": row['icon_url']
        }
    return await self.get_default_title()

async def check_title_after_elo_update(self, user_id: str, old_elo: int):
    #get current ELO,after elo changed from grading or badge
    current_elo = await self.get_current_elo(user_id)
    
    #gets current title from profiles table ,after trigger ran
    current_title = await self.get_current_title_from_profile(user_id)
    
    #old elo title
    old_expected_title = await self.get_title_for_elo(old_elo)
    
    #Checks if title changed
    title_changed = old_expected_title['id'] != current_title['id']
    
    return {
        "user_id": user_id,
        "current_title": current_title,
        "title_changed": title_changed,
        "old_title": old_expected_title if title_changed else None,
        "new_title": current_title if title_changed else None,
    }