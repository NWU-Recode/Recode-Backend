"""Run an end-to-end submission against the local backend services.

Steps:
1. Finds the most recently created question that has a reference solution.
2. Picks an arbitrary student profile (role == "student").
3. Calls the submissions service to submit the reference solution for that question.
4. Prints the evaluation result and inspects Supabase tables for persistence
   (`code_submissions`, `code_results`, `user_scores`, `user_badge`).

Assumes:
- Supabase credentials in environment/.env are valid.
- Judge0 is reachable via configured settings (scripts uses submissions_service which
  already handles Judge0 execution).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure project root on PYTHONPATH when executed as standalone script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.DB.supabase import get_supabase
from app.features.submissions.service import submissions_service


async def _pick_student_id(client) -> int:
    resp = await (
        client.table("profiles")
        .select("id, role")
        .eq("role", "student")
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        raise RuntimeError("No student profiles found in Supabase (role == 'student').")
    return int(rows[0]["id"])


async def _pick_question(client) -> Dict[str, Any]:
    resp = await (
        client.table("questions")
        .select("id, challenge_id, reference_solution, starter_code, language_id, title")
        .order("id", desc=True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        raise RuntimeError("No questions found in Supabase.")
    question = rows[0]
    if not question.get("reference_solution") and not question.get("starter_code"):
        raise RuntimeError("Question has no reference_solution or starter_code to submit.")
    return question


async def _fetch_code_submission(client, submission_id: str) -> Dict[str, Any] | None:
    resp = await (
        client.table("code_submissions")
        .select("*")
        .eq("id", submission_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


async def _fetch_code_results(client, submission_id: str) -> list[Dict[str, Any]]:
    resp = await (
        client.table("code_results")
        .select("*")
        .eq("submission_id", submission_id)
        .execute()
    )
    return resp.data or []


async def _fetch_user_scores(client, student_id: int) -> Dict[str, Any] | None:
    resp = await (
        client.table("user_scores")
        .select("*")
        .eq("student_id", student_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


async def _fetch_user_badges(client, student_id: int) -> list[Dict[str, Any]]:
    resp = await (
        client.table("user_badge")
        .select("*")
        .eq("profile_id", student_id)
        .execute()
    )
    return resp.data or []


async def main():
    client = await get_supabase()

    student_id = await _pick_student_id(client)
    question = await _pick_question(client)
    question_id = str(question["id"])
    challenge_id = str(question.get("challenge_id"))
    if challenge_id in {"", "None", None}:
        raise RuntimeError("Question is missing challenge_id (required for submission flow).")

    source_code = question.get("reference_solution") or question.get("starter_code") or ""
    language_id = int(question.get("language_id") or 71)

    print(f"Using student_id={student_id}, challenge_id={challenge_id}, question_id={question_id}")

    result = await submissions_service.submit_question(
        challenge_id=challenge_id,
        question_id=question_id,
        submitted_output=None,
        source_code=source_code,
        user_id=student_id,
        language_id=language_id,
        include_private=True,
    )

    print("Submission result:")
    print(json.dumps(result.model_dump(), indent=2, default=str))

    submission_id = result.submission_id
    if submission_id:
        code_submission = await _fetch_code_submission(client, submission_id)
        code_results = await _fetch_code_results(client, submission_id)
        print("\nPersisted code_submissions row:")
        print(json.dumps(code_submission, indent=2, default=str))
        print("\nPersisted code_results rows:")
        print(json.dumps(code_results, indent=2, default=str))
    else:
        print("No submission_id returned (check Judge0 execution).")

    user_scores = await _fetch_user_scores(client, student_id)
    user_badges = await _fetch_user_badges(client, student_id)

    print("\nUser scores entry:")
    print(json.dumps(user_scores, indent=2, default=str))
    print("\nUser badges (all):")
    print(json.dumps(user_badges, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
