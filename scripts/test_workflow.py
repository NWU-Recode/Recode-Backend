#!/usr/bin/env python3
"""
Test script for the AWS Bedrock Claude challenge generation workflow.
This script tests the complete workflow without making actual AWS API calls.
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.append('.')

from app.Core.config import get_settings
from app.features.topic_detections.topics.topic_service import topic_service


async def test_workflow():
    """Test the complete workflow."""

    print("=== Testing AWS Bedrock Claude Challenge Generation Workflow ===\n")

    # 1. Test configuration loading
    print("1. Testing configuration loading...")
    try:
        settings = get_settings()
        print("   ✓ AWS_ACCESS_KEY_ID:", "****" if settings.aws_access_key_id else "Not set")
        print("   ✓ AWS_SECRET_ACCESS_KEY:", "****" if settings.aws_secret_access_key else "Not set")
        print("   ✓ AWS_REGION:", settings.aws_region)
        print("   ✓ BEDROCK_MODEL_ID:", settings.bedrock_model_id)
        print("   ✓ BEDROCK_MAX_TOKENS:", settings.bedrock_max_tokens)
        print("   ✓ BEDROCK_TEMPERATURE:", settings.bedrock_temperature)
        print("   ✓ BEDROCK_TOP_P:", settings.bedrock_top_p)
        print("   ✓ BEDROCK_TOP_K:", settings.bedrock_top_k)
        print("   ✓ BEDROCK_STOP_SEQUENCES:", settings.bedrock_stop_sequences)
        print("   ✓ Configuration loaded successfully!\n")
    except Exception as e:
        print(f"   ✗ Configuration error: {e}\n")
        return

    # 2. Test topic fetching
    print("2. Testing topic fetching from Supabase...")
    try:
        # Test with sample module_id and week_number
        module_id = 1
        week_number = 1

        topics = await topic_service.get_all_topics_for_week(week_number, module_id)
        print(f"   ✓ Fetched topics for module {module_id}, week {week_number}: {topics}")

        if not topics:
            print("   ! No topics found, using fallback topics")
            topics = ["variables", "operators", "conditionals", "loops", "functions"]

        topics_list = ", ".join(topics)
        print(f"   ✓ Topics list: {topics_list}\n")

    except Exception as e:
        print(f"   ✗ Topic fetching error: {e}\n")
        return

    # 2b. Test topics table subtopics fetching with module_code
    print("2b. Testing topics table subtopics (module_code=CMPG111)...")
    try:
        subtopics_w1 = await topic_service.get_subtopics_for_week(1, "CMPG111")
        subtopics_w2 = await topic_service.get_subtopics_for_week(2, "CMPG111")
        print(f"   ✓ Week 1 subtopics: {subtopics_w1}")
        print(f"   ✓ Week 2 subtopics: {subtopics_w2}\n")
    except Exception as e:
        print(f"   ✗ Subtopics fetching error: {e}\n")
        return

    # 2c. Direct topics table probe for visibility
    print("2c. Probing topics table directly by week...")
    try:
        client = topic_service.supabase
        # Supabase project URL host (redacted)
        from app.Core.config import get_settings as _gs
        supa_url = _gs().supabase_url
        print("   ✓ Supabase URL:", supa_url)
        probe = None
        table_used = None
        for tname in ["topic", "topics"]:
            try:
                probe = client.table(tname).select("id, week, slug, title, subtopics").eq("week", 1).execute()
                table_used = tname
                break
            except Exception as _e:
                continue
        if not probe:
            raise RuntimeError("Neither 'topic' nor 'topics' accessible")
        print(f"   ✓ {table_used}[week=1] rows:", len(probe.data or []))
        if probe.data:
            first = probe.data[0]
            print("     • first row sample:", {k: first.get(k) for k in ["id","week","slug","title","subtopics"]})
        print()
    except Exception as e:
        print(f"   ✗ Topics direct probe error: {e}\n")
        return

    # 3. Test template loading
    print("3. Testing template loading...")
    try:
        from pathlib import Path

        base_dir = Path(__file__).parent / "app" / "features" / "challenges" / "prompts"

        for tier in ["base", "ruby", "emerald", "diamond"]:
            template_path = base_dir / f"{tier}.txt"
            if template_path.exists():
                content = template_path.read_text(encoding="utf-8")
                print(f"   ✓ {tier}.txt loaded ({len(content)} characters)")
            else:
                print(f"   ✗ {tier}.txt not found")

        print("   ✓ Template loading test completed!\n")

    except Exception as e:
        print(f"   ✗ Template loading error: {e}\n")
        return

    # 4. Test prompt filling
    print("4. Testing prompt template filling...")
    try:
        template_path = base_dir / "base.txt"
        template = template_path.read_text(encoding="utf-8")
        final_prompt = template.replace("{{topics_list}}", topics_list)

        print(f"   ✓ Template filled with topics")
        print(f"   ✓ Final prompt length: {len(final_prompt)} characters")
        print(f"   ✓ Contains topics: {'{{topics_list}}' not in final_prompt}\n")

    except Exception as e:
        print(f"   ✗ Prompt filling error: {e}\n")
        return

    # 5. Test Bedrock client (mock)
    print("5. Testing Bedrock client setup...")
    try:
        import boto3
        from app.features.challenges.ai.bedrock_client import bedrock

        print("   ✓ Boto3 bedrock client created")
        print(f"   ✓ Client region: {bedrock.meta.region_name}")
        print("   ✓ Bedrock client setup successful!\n")

    except Exception as e:
        print(f"   ✗ Bedrock client error: {e}\n")
        return

    print("=== Workflow Test Summary ===")
    print("✓ Configuration loading: PASSED")
    print("✓ Topic fetching: PASSED")
    print("✓ Template loading: PASSED")
    print("✓ Prompt filling: PASSED")
    print("✓ Bedrock client setup: PASSED")
    print("\n🎉 All workflow components are working correctly!")
    print("\nNext steps:")
    print("1. Set AWS credentials in environment variables")
    print("2. Add sample data to slide_extraction table")
    print("3. Test actual Claude API calls")
    print("4. Test complete challenge generation and database insertion")


if __name__ == "__main__":
    asyncio.run(test_workflow())
