from __future__ import annotations
from typing import List, Dict, Any
from app.features.challenges.repository import challenge_repository
from app.features.questions.repository import question_repository

class DashboardService:
    async def get_dashboard(self, user_id: str) -> List[Dict[str, Any]]:
        challenges = await challenge_repository.list_challenges()
        attempts = await challenge_repository.list_user_attempts(user_id)
        attempt_map: Dict[str, Any] = {}
        for a in attempts:
            cid = str(a.get("challenge_id"))
            attempt_map[cid] = a
        bronze_submitted = sum(1 for a in attempts if any(c for c in challenges if str(c.get("id")) == str(a.get("challenge_id")) and c.get("tier") == "bronze" and a.get("status") == "submitted"))
        silver_submitted = sum(1 for a in attempts if any(c for c in challenges if str(c.get("id")) == str(a.get("challenge_id")) and c.get("tier") == "silver" and a.get("status") == "submitted"))
        gold_submitted = sum(1 for a in attempts if any(c for c in challenges if str(c.get("id")) == str(a.get("challenge_id")) and c.get("tier") == "gold" and a.get("status") == "submitted"))
        result: List[Dict[str, Any]] = []
        for ch in challenges:
            cid = str(ch.get("id"))
            tier = ch.get("tier")
            state = "locked"
            attempt = attempt_map.get(cid)
            if attempt:
                if attempt.get("status") == "submitted":
                    state = "submitted"
                elif attempt.get("status") == "expired":
                    state = "expired"
                else:
                    state = "open"
            else:
                if tier == "bronze":
                    state = "open" if ch.get("sequence_index") == bronze_submitted + 1 else "locked"
                elif tier == "silver" and bronze_submitted == 5:
                    state = "open" if (ch.get("sequence_index") - 5) == silver_submitted + 1 else "locked"
                elif tier == "gold" and bronze_submitted == 5 and silver_submitted == 3:
                    state = "open" if (ch.get("sequence_index") - 8) == gold_submitted + 1 else "locked"
            progress = None
            if attempt and attempt.get("status") in ("open", "submitted"):
                # Recompute from latest question attempts for accuracy
                latest_q_attempts = await question_repository.list_latest_attempts_for_challenge(cid, user_id)
                passed = sum(1 for qa in latest_q_attempts if qa.get("is_correct"))
                progress = {"passed": passed, "total": 10}
            result.append({
                "challenge_id": cid,
                "title": ch.get("title"),
                "tier": tier,
                "sequence_index": ch.get("sequence_index"),
                "state": state,
                "progress": progress,
            })
        return result

dashboard_service = DashboardService()
