from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple
import json
import re

from app.DB.supabase import get_supabase
from app.features.topic_detections.slide_extraction.topic_service import slide_extraction_topic_service
from app.features.challenges.ai.generator import generate_question_spec
from app.features.challenges.ai.bedrock_client import invoke_claude
from app.Core.config import get_settings


class ClaudeChallengeGenerator:
    def __init__(self, week: int, slide_stack_id: Optional[int] = None):
        self.week = week
        self.slide_stack_id = slide_stack_id
        self.supabase = None

    async def _get_supabase(self):
        if self.supabase is None:
            self.supabase = await get_supabase()
        return self.supabase

    async def _load_template(self, kind: str) -> str:
        """Load the appropriate Claude prompt template."""
        from pathlib import Path
        base_dir = Path(__file__).parent.parent / "prompts"
        fname = {
            "common": "base.txt",
            "base": "base.txt",
            "ruby": "ruby.txt",
            "emerald": "emerald.txt",
            "diamond": "diamond.txt",
        }.get(kind, "base.txt")
        path = base_dir / fname
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return self._get_fallback_template(kind)

    def _get_fallback_template(self, kind: str) -> str:
        """Fallback template if file not found."""
        if kind == "common":
            return """You are an expert coding tutor. Generate FIVE coding challenges for topics: {{topics_list}}.

Output STRICT JSON:
{
  "challenge_set_title": "Week X Challenge Set",
  "questions": [
    {
      "title": "Challenge Title",
      "question_text": "Full problem description",
      "difficulty_level": "Bronze|Silver|Gold",
      "starter_code": "",
      "reference_solution": "correct solution code",
      "test_cases": [
        {"input": "test input", "expected_output": "expected output"}
      ]
    }
  ]
}"""
        else:
            return """You are an expert coding tutor. Generate ONE coding challenge for topics: {{topics_list}}.

Output STRICT JSON:
{
  "challenge_set_title": "Advanced Challenge",
  "questions": [
    {
      "title": "Challenge Title",
      "question_text": "Full problem description",
      "difficulty_level": "Ruby|Emerald|Diamond",
      "starter_code": "",
      "reference_solution": "correct solution code",
      "test_cases": [
        {"input": "test input", "expected_output": "expected output"}
      ]
    }
  ]
}"""

    async def _get_topics(self) -> List[str]:
        """Get topics from slide extraction or use defaults."""
        if self.slide_stack_id:
            topics = await slide_extraction_topic_service.get_topics_from_slide_extraction(self.slide_stack_id)
            if topics:
                return topics

        # Fallback: get topics for the week
        topics = await slide_extraction_topic_service.get_all_topics_for_week(self.week)
        return topics if topics else ["programming", "algorithms", "data structures"]

    async def _generate_common_challenges(self, topics: List[str]) -> Dict[str, Any]:
        """Generate 5 common challenges (2 Bronze, 2 Silver, 1 Gold)."""
        template = await self._load_template("common")
        topics_str = ", ".join(topics)
        prompt = template.replace("{{topics_list}}", topics_str)

        try:
            response = await invoke_claude(prompt, max_tokens=8000)

            if isinstance(response, dict) and "questions" in response:
                # Validate we have at least 5 questions
                questions = response["questions"]
                if len(questions) >= 5:
                    # Ensure proper difficulty distribution
                    bronze_count = sum(1 for q in questions if q.get("difficulty_level") == "Bronze")
                    silver_count = sum(1 for q in questions if q.get("difficulty_level") == "Silver")
                    gold_count = sum(1 for q in questions if q.get("difficulty_level") == "Gold")

                    # Adjust if needed (this is a simple approach)
                    if bronze_count < 2:
                        for i, q in enumerate(questions):
                            if q.get("difficulty_level") not in ["Bronze", "Silver", "Gold"]:
                                questions[i]["difficulty_level"] = "Bronze"
                                bronze_count += 1
                                if bronze_count >= 2:
                                    break

                    return response

            # Fallback generation
            return await self._generate_fallback_common_challenges(topics)

        except Exception as e:
            print(f"Error generating common challenges: {e}")
            return await self._generate_fallback_common_challenges(topics)

    async def _generate_fallback_common_challenges(self, topics: List[str]) -> Dict[str, Any]:
        """Generate fallback common challenges."""
        return {
            "challenge_set_title": f"Week {self.week} Programming Challenges",
            "questions": [
                {
                    "title": f"Basic {topic.title()} Challenge",
                    "question_text": f"Write a function that demonstrates basic {topic} concepts.",
                    "difficulty_level": "Bronze",
                    "starter_code": "def solution():\n    pass",
                    "reference_solution": "def solution():\n    return 'Hello World'",
                    "test_cases": [
                        {"input": "", "expected_output": "Hello World"}
                    ]
                }
                for topic in topics[:5]
            ]
        }

    async def _generate_single_challenge(self, kind: str, topics: List[str]) -> Dict[str, Any]:
        """Generate a single advanced challenge (Ruby, Emerald, Diamond)."""
        template = await self._load_template(kind)
        topics_str = ", ".join(topics)
        prompt = template.replace("{{topics_list}}", topics_str)

        try:
            response = await invoke_claude(prompt, max_tokens=6000)

            if isinstance(response, dict) and "questions" in response and response["questions"]:
                question = response["questions"][0]
                question["difficulty_level"] = kind.title()  # Ensure correct difficulty
                return response

            # Fallback
            return await self._generate_fallback_single_challenge(kind, topics)

        except Exception as e:
            print(f"Error generating {kind} challenge: {e}")
            return await self._generate_fallback_single_challenge(kind, topics)

    async def _generate_fallback_single_challenge(self, kind: str, topics: List[str]) -> Dict[str, Any]:
        """Generate fallback single challenge."""
        return {
            "challenge_set_title": f"{kind.title()} Challenge",
            "questions": [
                {
                    "title": f"Advanced {kind.title()} Challenge",
                    "question_text": f"Create an advanced solution demonstrating {', '.join(topics)} concepts.",
                    "difficulty_level": kind.title(),
                    "starter_code": "def advanced_solution():\n    pass",
                    "reference_solution": "def advanced_solution():\n    return 'Advanced implementation'",
                    "test_cases": [
                        {"input": "", "expected_output": "Advanced implementation"}
                    ]
                }
            ]
        }

    async def _create_challenge_in_db(self, kind: str, title: str, description: str) -> Dict[str, Any]:
        """Create a challenge record in the database."""
        supabase = await self._get_supabase()

        # Generate slug
        slug = f"w{self.week:02d}-{kind}"
        if kind == "common":
            slug = f"w{self.week:02d}-common"

        payload = {
            "title": title,
            "description": description,
            "slug": slug,
            "kind": kind,
            "status": "draft",
            "tier": "plain" if kind == "common" else kind,
        }

        response = await supabase.table("challenges").insert(payload).execute()
        if not response.data:
            raise RuntimeError(f"Failed to create {kind} challenge")
        return response.data[0]

    async def _create_question_in_db(self, challenge_id: str, question_data: Dict[str, Any], points: int) -> Dict[str, Any]:
        """Create a question record in the database."""
        from app.features.topic_detections.repository import question_repository

        # Prepare question data
        payload = {
            "challenge_id": challenge_id,
            "language_id": 71,  # Python 3.10 for Judge0
            "expected_output": question_data.get("test_cases", [{}])[0].get("expected_output", ""),
            "points": points,
            "starter_code": question_data.get("starter_code", ""),
            "max_time_ms": 2000,
            "max_memory_kb": 256000,
            "tier": question_data.get("difficulty_level", "bronze").lower(),
        }

        question = await question_repository.create_question(payload)

        # Insert test cases
        test_cases = question_data.get("test_cases", [])
        if test_cases:
            await question_repository.insert_tests(str(question["id"]), [
                {
                    "input": tc.get("input", ""),
                    "expected": tc.get("expected_output", ""),
                    "visibility": "public"
                }
                for tc in test_cases
            ])

        return question

    async def generate(self) -> Dict[str, Any]:
        """Main generation method."""
        topics = await self._get_topics()

        created_challenges = {"common": None, "ruby": None, "emerald": None, "diamond": None}

        # Generate common challenges (5 questions)
        try:
            common_data = await self._generate_common_challenges(topics)
            if common_data.get("questions") and len(common_data["questions"]) >= 5:
                # Create common challenge
                common_challenge = await self._create_challenge_in_db(
                    "common",
                    common_data.get("challenge_set_title", f"Week {self.week} Challenges"),
                    f"Auto-generated challenges for Week {self.week}"
                )

                # Create questions
                for i, question in enumerate(common_data["questions"][:5]):
                    points = self._get_points_for_difficulty(question.get("difficulty_level", "Bronze"))
                    await self._create_question_in_db(str(common_challenge["id"]), question, points)

                created_challenges["common"] = {
                    "challenge_id": str(common_challenge["id"]),
                    "question_count": 5
                }
        except Exception as e:
            print(f"Error creating common challenges: {e}")

        # Generate advanced challenges
        for kind in ["ruby", "emerald", "diamond"]:
            try:
                single_data = await self._generate_single_challenge(kind, topics)
                if single_data.get("questions"):
                    question = single_data["questions"][0]

                    # Create challenge
                    challenge = await self._create_challenge_in_db(
                        kind,
                        question.get("title", f"{kind.title()} Challenge"),
                        f"Advanced {kind.title()} challenge for Week {self.week}"
                    )

                    # Create question
                    points = self._get_points_for_difficulty(kind.title())
                    await self._create_question_in_db(str(challenge["id"]), question, points)

                    created_challenges[kind] = {
                        "challenge_id": str(challenge["id"]),
                        "question_count": 1
                    }
            except Exception as e:
                print(f"Error creating {kind} challenge: {e}")

        return {
            "week": self.week,
            "topics_used": topics,
            "created": created_challenges,
            "status": "completed"
        }

    def _get_points_for_difficulty(self, difficulty: str) -> int:
        """Get points for difficulty level."""
        points_map = {
            "Bronze": 10,
            "Silver": 20,
            "Gold": 30,
            "Ruby": 40,
            "Emerald": 60,
            "Diamond": 100
        }
        return points_map.get(difficulty, 10)


# Convenience function
async def generate_challenges_with_claude(week: int, slide_stack_id: Optional[int] = None) -> Dict[str, Any]:
    """Generate challenges using Claude AI."""
    generator = ClaudeChallengeGenerator(week, slide_stack_id)
    return await generator.generate()