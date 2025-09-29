"""
Quick demo script to preview generated challenges for given weeks and tiers
without needing DB or a model runtime. Uses the generator fallback payload.

Run (PowerShell):

$env:GENERATOR_FAKE = "1"
python .\scripts\demo_challenges.py --weeks 1,2,3,4,6,8,10,12 --tiers base,ruby,emerald,diamond --module ABC101

The script prints JSON output and writes per-week files to scripts/demo_output/.
"""
from __future__ import annotations

import os
import argparse
import asyncio
import json
from typing import List

# Force fallback generator to avoid model calls
os.environ.setdefault("GENERATOR_FAKE", "1")

from app.features.challenges.challenge_pack_generator import (
    TopicContext,
    _call_bedrock,
    _normalise_questions,
)


async def preview_for(week: int, tier: str, module_code: str | None):
    context = TopicContext(
        week=week,
        module_code=module_code,
        topic_id=None,
        topic_title=f"Demo Topic Week {week}",
        topic_slug=None,
        prompt_topics=["variables", "loops"],
        topic_ids_used=[],
        topic_titles_used=[],
        topic_history=[],
        topic_week_span=None,
    )
    try:
        payload = await _call_bedrock(tier, context)
        questions = _normalise_questions(tier, payload)
        return {
            "week": week,
            "tier": tier,
            "module_code": module_code,
            "challenge_set_title": payload.get("challenge_set_title"),
            "questions": questions,
            "topics": context.joined_topics(),
        }
    except Exception as exc:
        return {"week": week, "tier": tier, "error": str(exc)}


async def main(weeks: List[int], tiers: List[str], module_code: str | None, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    tasks = []
    for w in weeks:
        for t in tiers:
            tasks.append(preview_for(w, t, module_code))
    results = await asyncio.gather(*tasks)
    # Group results by week for readability and write files
    by_week = {}
    for r in results:
        w = r.get("week")
        by_week.setdefault(w, []).append(r)
    for w, items in sorted(by_week.items()):
        path = os.path.join(out_dir, f"week_{int(w):02d}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(items, fh, indent=2)
    # Print summary to stdout
    print(json.dumps(by_week, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--weeks", required=True, help="Comma-separated list of week numbers, e.g. 1,2,3")
    parser.add_argument("--tiers", required=True, help="Comma-separated tiers: base,ruby,emerald,diamond")
    parser.add_argument("--module", dest="module_code", default=None)
    parser.add_argument("--out", dest="out_dir", default="scripts/demo_output")
    args = parser.parse_args()
    weeks = [int(x) for x in args.weeks.split(",") if x.strip()]
    tiers = [x.strip().lower() for x in args.tiers.split(",") if x.strip()]
    asyncio.run(main(weeks, tiers, args.module_code, args.out_dir))
