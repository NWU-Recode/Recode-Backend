from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from .repository import achievements_repository, _parse_datetime
from .schemas import (
    AchievementsResponse,
    BadgeBatchAddRequest,
    BadgeBatchAddResponse,
    BadgeRequest,
    BadgeResponse,
    CheckAchievementsRequest,
    CheckAchievementsResponse,
    EloResponse,
    EloUpdateRequest,
    TitleInfo,
    TitleResponse,
)

logger = logging.getLogger("achievements.service")

BASE_ELO = 1200

_TIER_COMPLETION_THRESHOLDS = {
    "bronze": 3,
    "silver": 3,
    "gold": 2,
    "platinum": 2,
    "emerald": 1,
    "diamond": 1,
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except Exception:  # pragma: no cover - defensive fallback
        return default


def _normalise_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


def _normalise_slug(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    slug = "".join(ch for ch in str(value).lower() if ch.isalnum() or ch in {"-", "_"})
    return slug or None


def _extract_snapshot_count(raw: Any) -> int:
    if raw is None:
        return 0
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:  # pragma: no cover - defensive fallback
            return 0
        return _extract_snapshot_count(parsed)
    if isinstance(raw, Sequence):
        return len(list(raw))
    return 0


@dataclass
class AttemptSummary:
    attempt_id: str
    challenge_id: str
    user_id: str
    tier: str
    correct: int
    total: int
    ratio: float
    status: str
    submitted_at: Optional[datetime]
    module_code: Optional[str]
    week_number: Optional[int]
    metadata: Dict[str, Any]


class AchievementsService:
    def __init__(self):
        self.repo = achievements_repository
        self.log = logger

    # ------------------------------------------------------------------
    # Public API used by FastAPI endpoints
    # ------------------------------------------------------------------

    async def get_achievements(self, user_id: str) -> AchievementsResponse:
        elo_record = await self._ensure_user_elo_record(user_id)
        elo_points = _safe_int(elo_record.get("elo_points"), default=BASE_ELO)
        gpa = elo_record.get("running_gpa")
        if gpa is None:
            gpa = await self._compute_running_gpa(user_id)
            try:
                await self.repo.update_user_elo(user_id, elo_points=elo_points, gpa=gpa)
            except Exception:  # pragma: no cover - supabase failure tolerance
                pass
        badges_rows = await self.repo.get_badges_for_user(user_id)
        badges = [self._serialise_badge_row(row) for row in badges_rows]
        title_info = await self.get_title(user_id)
        return AchievementsResponse(elo=elo_points, gpa=gpa, badges=badges, title=title_info)

    async def get_elo(self, user_id: str) -> EloResponse:
        elo_record = await self._ensure_user_elo_record(user_id)
        elo_points = _safe_int(elo_record.get("elo_points"), default=BASE_ELO)
        gpa = elo_record.get("running_gpa")
        if gpa is None:
            gpa = await self._compute_running_gpa(user_id)
        return EloResponse(elo=elo_points, gpa=gpa)

    async def update_elo(self, user_id: str, req: EloUpdateRequest) -> EloResponse:
        summary = await self._load_attempt_summary(req.submission_id, user_id)
        elo_record = await self._ensure_user_elo_record(user_id)
        old_elo = _safe_int(elo_record.get("elo_points"), default=BASE_ELO)
        delta = self._compute_elo_delta(summary)
        new_elo = max(0, old_elo + delta)
        gpa = await self._compute_running_gpa(user_id)
        await self.repo.update_user_elo(user_id, elo_points=new_elo, gpa=gpa)
        await self._maybe_log_elo_event(user_id, summary, delta, new_elo, gpa)
        return EloResponse(elo=new_elo, gpa=gpa)

    async def get_badges(self, user_id: str) -> List[BadgeResponse]:
        rows = await self.repo.get_badges_for_user(user_id)
        return [self._serialise_badge_row(row) for row in rows]

    async def add_badge(self, user_id: str, req: BadgeRequest) -> BadgeResponse:
        awarded = await self._evaluate_badges(user_id, req.submission_id)
        if not awarded:
            raise ValueError("no_badge_awarded")
        return awarded[0]

    async def add_badges_batch(self, user_id: str, req: BadgeBatchAddRequest) -> BadgeBatchAddResponse:
        awarded = await self._evaluate_badges(user_id, req.submission_id)
        return BadgeBatchAddResponse(badges=awarded)

    async def get_title(self, user_id: str) -> Optional[TitleInfo]:
        titles = await self.repo.list_titles()
        profile = await self.repo.get_user_elo(user_id)
        current_id = None
        if profile:
            current_id = profile.get("title_id") or profile.get("current_title_id")
        if not current_id:
            try:
                from app.features.profiles.repository import profile_repository

                profile_row = await profile_repository.get_by_id(int(user_id))
                current_id = profile_row.get("title_id") if profile_row else None
            except Exception:  # pragma: no cover - best effort fallback
                current_id = None
        if not current_id:
            return self._default_title(titles)
        title_row = self._find_title_by_id(titles, current_id)
        if not title_row:
            return self._default_title(titles)
        return self._serialise_title(title_row)

    async def check_title_after_elo_update(self, user_id: str, old_elo: int) -> TitleResponse:
        titles = await self.repo.list_titles()
        current_record = await self._ensure_user_elo_record(user_id)
        current_elo = _safe_int(current_record.get("elo_points"), default=BASE_ELO)
        current_title = await self.get_title(user_id)
        expected_old_title = self._title_for_elo(titles, old_elo)
        expected_new_title = self._title_for_elo(titles, current_elo)
        changed = False
        if expected_new_title and expected_old_title:
            changed = expected_new_title.id != expected_old_title.id
        if changed and expected_new_title:
            try:
                await self.repo.update_profile_title(user_id, expected_new_title.id)
            except Exception:  # pragma: no cover - Supabase failure resilience
                pass
        fallback_current = current_title or expected_new_title or expected_old_title or self._default_title(titles)
        return TitleResponse(
            user_id=user_id,
            current_title=fallback_current,
            title_changed=changed,
            old_title=expected_old_title if changed else None,
            new_title=expected_new_title if changed else None,
            message=(
                f"Title upgraded to {expected_new_title.name}" if changed and expected_new_title else None
            ),
        )

    async def check_achievements(self, user_id: str, req: CheckAchievementsRequest) -> CheckAchievementsResponse:
        summary = await self._load_attempt_summary(req.submission_id, user_id)
        elo_record = await self._ensure_user_elo_record(user_id)
        old_elo = _safe_int(elo_record.get("elo_points"), default=BASE_ELO)
        delta = self._compute_elo_delta(summary)
        new_elo = max(0, old_elo + delta)
        gpa = await self._compute_running_gpa(user_id)
        await self.repo.update_user_elo(user_id, elo_points=new_elo, gpa=gpa)
        await self._maybe_log_elo_event(user_id, summary, delta, new_elo, gpa)
        badges = await self._evaluate_badges(user_id, req.submission_id)
        title_resp = await self.check_title_after_elo_update(user_id, old_elo)
        return CheckAchievementsResponse(
            updated_elo=new_elo,
            gpa=gpa,
            unlocked_badges=badges or None,
            new_title=title_resp if title_resp.title_changed else None,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_user_elo_record(self, user_id: str) -> Dict[str, Any]:
        record = await self.repo.get_user_elo(user_id)
        if record:
            return record
        inserted = await self.repo.insert_user_elo(user_id, elo_points=BASE_ELO, gpa=0.0)
        return inserted or {"user_id": user_id, "elo_points": BASE_ELO, "running_gpa": 0.0}

    async def _compute_running_gpa(self, user_id: str) -> float:
        attempts = await self.repo.list_submitted_attempts(user_id)
        if not attempts:
            return 0.0
        ratios: List[float] = []
        for attempt in attempts:
            total = _extract_snapshot_count(attempt.get("snapshot_questions"))
            if total <= 0:
                total = _safe_int(attempt.get("total_public_tests"), default=0)
            if total <= 0:
                total = _safe_int(attempt.get("total_questions"), default=0)
            correct = _safe_int(attempt.get("correct_count"), default=0)
            ratio = _normalise_ratio(correct, total if total > 0 else 1)
            ratios.append(ratio)
        if not ratios:
            return 0.0
        avg_ratio = sum(ratios) / len(ratios)
        return round(avg_ratio * 4.0, 2)

    async def _load_attempt_summary(self, submission_id: str, user_id: str) -> AttemptSummary:
        attempt = await self.repo.fetch_challenge_attempt(submission_id)
        if not attempt:
            raise ValueError("challenge_attempt_not_found")
        owner_id = str(attempt.get("user_id"))
        if owner_id != str(user_id):
            raise ValueError("attempt_user_mismatch")
        challenge_id = attempt.get("challenge_id")
        challenge = await self.repo.fetch_challenge(str(challenge_id)) if challenge_id else None
        tier = (challenge or {}).get("tier") or attempt.get("tier") or "plain"
        total = _extract_snapshot_count(attempt.get("snapshot_questions"))
        if total <= 0:
            total = _safe_int(attempt.get("total_public_tests"), default=0)
        if total <= 0:
            total = _safe_int(attempt.get("total_questions"), default=0)
        correct = _safe_int(attempt.get("correct_count"), default=0)
        ratio = _normalise_ratio(correct, total if total > 0 else 1)
        submitted_at = _parse_datetime(attempt.get("submitted_at")) or _parse_datetime(attempt.get("updated_at"))
        module_code = (challenge or {}).get("module_code") or attempt.get("module_code")
        week_number_raw = attempt.get("week_number") or (challenge or {}).get("week_number")
        try:
            week_number = int(week_number_raw) if week_number_raw is not None else None
        except Exception:
            week_number = None
        metadata = {
            "score": attempt.get("score"),
            "hints_used": attempt.get("hints_used"),
            "resubmissions": attempt.get("resubmissions") or attempt.get("retry_count"),
            "duration_seconds": attempt.get("duration_seconds"),
            "tier": tier,
        }
        return AttemptSummary(
            attempt_id=str(submission_id),
            challenge_id=str(challenge_id),
            user_id=str(user_id),
            tier=str(tier),
            correct=correct,
            total=total,
            ratio=ratio,
            status=str(attempt.get("status")),
            submitted_at=submitted_at,
            module_code=module_code,
            week_number=week_number,
            metadata=metadata,
        )

    def _compute_elo_delta(self, summary: AttemptSummary) -> int:
        tier = _normalise_slug(summary.tier) or "plain"
        tier_weights: Dict[str, int] = {
            "plain": 15,
            "bronze": 8,
            "silver": 12,
            "gold": 18,
            "ruby": 24,
            "emerald": 30,
            "diamond": 36,
        }
        base = tier_weights.get(tier, tier_weights["plain"])
        ratio = summary.ratio
        delta = round(base * (ratio * 2 - 1))
        hints_used = _safe_int(summary.metadata.get("hints_used"), default=0)
        resubmissions = _safe_int(summary.metadata.get("resubmissions"), default=0)
        duration = _safe_int(summary.metadata.get("duration_seconds"), default=0)
        if hints_used:
            delta -= min(hints_used, 5)
        if resubmissions:
            delta -= min(resubmissions, 5)
        if duration and summary.total > 0 and duration > 60 * summary.total:
            penalty_steps = (duration - 60 * summary.total) // 120
            delta -= int(penalty_steps)
        return delta

    async def _maybe_log_elo_event(
        self,
        user_id: str,
        summary: AttemptSummary,
        delta: int,
        new_elo: int,
        gpa: float,
    ) -> None:
        payload = {
            "user_id": user_id,
            "challenge_id": summary.challenge_id,
            "challenge_attempt_id": summary.attempt_id,
            "tier": summary.tier,
            "delta": delta,
            "result_ratio": summary.ratio,
            "new_elo": new_elo,
            "gpa_snapshot": gpa,
            "recorded_at": datetime.utcnow().isoformat() + "Z",
        }
        try:
            await self.repo.log_elo_event(payload)
        except Exception:  # pragma: no cover - logging best effort
            self.log.debug("failed to log elo event", exc_info=True)


    async def _tier_completion_counts(self, user_id: str) -> Dict[str, int]:
        attempts = await self.repo.list_submitted_attempts(user_id)
        counts: Dict[str, int] = {}
        for attempt in attempts:
            tier = _normalise_slug(attempt.get("tier") or (attempt.get("challenge") or {}).get("tier")) or "plain"
            total = _extract_snapshot_count(attempt.get("snapshot_questions"))
            if total <= 0:
                total = _safe_int(attempt.get("total_questions"), default=0)
            tests_total = _safe_int(attempt.get("tests_total"), default=0)
            if tests_total > 0:
                total = tests_total
            correct = _safe_int(attempt.get("correct_count"), default=0)
            tests_passed = _safe_int(attempt.get("tests_passed"), default=0)
            ratio = _normalise_ratio(correct, total if total > 0 else 1)
            success = False
            if total > 0 and correct >= total:
                success = True
            if tests_total > 0 and tests_passed >= tests_total:
                success = True
            if ratio >= 0.999:
                success = True
            if not success:
                continue
            counts[tier] = counts.get(tier, 0) + 1
        return counts
    async def _award_badges_for_tiers(self, user_id: str, summary: AttemptSummary, tiers: List[str]) -> List[BadgeResponse]:
        if not tiers:
            return []
        counts = await self._tier_completion_counts(user_id)
        badge_defs = await self.repo.list_badge_definitions()
        slug_map: Dict[str, Dict[str, Any]] = {}
        for definition in badge_defs:
            slug = _normalise_slug(definition.get("slug") or definition.get("code") or definition.get("name"))
            if slug and definition.get("id"):
                slug_map[slug] = definition
        owned_rows = await self.repo.get_badges_for_user(user_id)
        owned_ids = {row.get("badge_id") or (row.get("badge") or {}).get("id") for row in owned_rows}
        awarded: List[BadgeResponse] = []
        for tier in tiers:
            slug = _normalise_slug(tier)
            if not slug:
                continue
            definition = slug_map.get(slug)
            if not definition:
                continue
            criteria = definition.get("criteria") or definition.get("metadata") or {}
            if isinstance(criteria, str):
                try:
                    criteria = json.loads(criteria)
                except Exception:  # pragma: no cover
                    criteria = {}
            threshold = criteria.get("required_passes") or _TIER_COMPLETION_THRESHOLDS.get(slug, 1)
            if counts.get(slug, 0) < threshold:
                continue
            badge_id = definition.get("id")
            if badge_id in owned_ids or badge_id is None:
                continue
            row = await self.repo.add_badge_to_user(
                user_id,
                badge_id,
                challenge_id=summary.challenge_id,
                attempt_id=summary.attempt_id,
                source_submission_id=summary.attempt_id,
            )
            if row:
                owned_ids.add(badge_id)
                awarded.append(self._serialise_badge_insert(row, definition))
        return awarded


    async def _evaluate_badges(self, user_id: str, submission_id: str) -> List[BadgeResponse]:
        summary = await self._load_attempt_summary(submission_id, user_id)
        badge_defs = await self.repo.list_badge_definitions()
        owned_rows = await self.repo.get_badges_for_user(user_id)
        owned_ids = {row.get("badge_id") or (row.get("badge") or {}).get("id") for row in owned_rows}
        awarded: List[BadgeResponse] = []
        eligible = self._resolve_badges_to_award(summary, badge_defs)
        new_ids = [bd.get("id") for bd in eligible if bd.get("id") not in owned_ids]
        if not new_ids:
            return []
        inserted_rows = await self.repo.add_badges_batch(
            user_id,
            badge_ids=new_ids,
            challenge_id=summary.challenge_id,
            attempt_id=summary.attempt_id,
            source_submission_id=summary.attempt_id,
        )
        if not inserted_rows:
            for badge_id in new_ids:
                try:
                    row = await self.repo.add_badge_to_user(
                        user_id,
                        badge_id,
                        challenge_id=summary.challenge_id,
                        attempt_id=summary.attempt_id,
                        source_submission_id=summary.attempt_id,
                    )
                except Exception:  # pragma: no cover - constraint violation etc
                    row = None
                if row:
                    inserted_rows.append(row)
        def_map = {bd.get("id"): bd for bd in badge_defs if bd.get("id")}
        for row in inserted_rows:
            badge_id = row.get("badge_id")
            definition = def_map.get(badge_id, {})
            awarded.append(self._serialise_badge_insert(row, definition))
        return awarded

    def _resolve_badges_to_award(self, summary: AttemptSummary, definitions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ratio = summary.ratio
        tier = _normalise_slug(summary.tier) or "plain"
        eligible: List[Dict[str, Any]] = []
        for badge in definitions:
            slug = _normalise_slug(badge.get("slug") or badge.get("code") or badge.get("name"))
            metadata = badge.get("metadata") or badge.get("criteria") or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:  # pragma: no cover - ignore malformed json
                    metadata = {}
            badge_tier = _normalise_slug(metadata.get("tier") or badge.get("tier") or slug)
            min_ratio = metadata.get("min_ratio") or metadata.get("min_correct_ratio")
            if min_ratio is not None:
                try:
                    min_ratio = float(min_ratio)
                except Exception:
                    min_ratio = None
            if min_ratio is None:
                if slug in {"gold", "gold-finisher"}:
                    min_ratio = 0.95
                elif slug in {"silver", "silver-finisher"}:
                    min_ratio = 0.75
                elif slug in {"bronze", "bronze-finisher"}:
                    min_ratio = 0.5
                elif slug in {"ruby", "emerald", "diamond"}:
                    min_ratio = 1.0
            if badge_tier and badge_tier not in {tier, "plain"}:
                continue
            if min_ratio is not None and ratio + 1e-9 < min_ratio:
                continue
            eligible.append(badge)
        return eligible

    def _serialise_badge_row(self, row: Dict[str, Any]) -> BadgeResponse:
        badge_info = row.get("badge") if isinstance(row.get("badge"), dict) else row.get("badges")
        if not isinstance(badge_info, dict):
            badge_info = row
        badge_id = badge_info.get("id") or row.get("badge_id")
        name = badge_info.get("name") or badge_info.get("badge_name") or badge_info.get("title")
        description = badge_info.get("description") or badge_info.get("badge_descrip")
        earned_dt = _parse_datetime(row.get("date_earned") or row.get("created_at") or row.get("awarded_at"))
        return BadgeResponse(
            badge_id=badge_id,
            badge_name=name or "Unknown Badge",
            badge_descrip=description,
            date_earned=earned_dt or datetime.utcnow(),
        )

    def _serialise_badge_insert(self, row: Dict[str, Any], definition: Dict[str, Any]) -> BadgeResponse:
        combined = dict(definition)
        combined.update(row)
        return self._serialise_badge_row(combined)

    def _default_title(self, titles: List[Dict[str, Any]]) -> Optional[TitleInfo]:
        if not titles:
            return None
        sorted_titles = sorted(titles, key=lambda r: _safe_int(r.get("min_elo") or r.get("elo_threshold")))
        return self._serialise_title(sorted_titles[0]) if sorted_titles else None

    def _serialise_title(self, row: Dict[str, Any]) -> TitleInfo:
        title_id = row.get("id") or row.get("title_id")
        min_elo = _safe_int(row.get("min_elo") or row.get("elo_threshold"))
        return TitleInfo(
            id=str(title_id),
            name=row.get("name") or row.get("title_name") or "Title",
            min_elo=min_elo,
            icon_url=row.get("icon_url") or row.get("icon"),
        )

    def _find_title_by_id(self, titles: List[Dict[str, Any]], title_id: Any) -> Optional[Dict[str, Any]]:
        for row in titles:
            rid = row.get("id") or row.get("title_id")
            if str(rid) == str(title_id):
                return row
        return None

    def _title_for_elo(self, titles: List[Dict[str, Any]], elo: int) -> Optional[TitleInfo]:
        eligible = []
        for row in titles:
            threshold = _safe_int(row.get("min_elo") or row.get("elo_threshold"))
            if elo >= threshold:
                eligible.append((threshold, row))
        if not eligible:
            return self._default_title(titles)
        _, best = max(eligible, key=lambda item: item[0])
        return self._serialise_title(best)


achievements_service = AchievementsService()

__all__ = ["achievements_service", "AchievementsService", "BASE_ELO"]



