"""
Debug script to check if achievement tables are being populated
Run this after making a submission to see what data exists
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.DB.supabase import get_supabase

# Replace with your actual student number
STUDENT_ID = "99999999"  # Brandon's student number
USER_UUID = "6f3ac054-c6f5-4b94-b4d4-082c44834c28"  # Brandon's user UUID

async def main():
    client = await get_supabase()
    
    print(f"\n{'='*60}")
    print(f"CHECKING ACHIEVEMENT TABLES FOR STUDENT: {STUDENT_ID}")
    print(f"{'='*60}\n")
    
    # Check user_elo
    print("1. USER_ELO TABLE:")
    try:
        elo_resp = await client.table("user_elo").select("*").eq("student_id", STUDENT_ID).execute()
        if elo_resp.data:
            import json
            print(json.dumps(elo_resp.data[0], indent=2, default=str))
        else:
            print("  ❌ NO DATA FOUND")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    
    # Check elo_events
    print("\n2. ELO_EVENTS TABLE:")
    try:
        events_resp = await client.table("elo_events").select("*").eq("student_id", STUDENT_ID).order("created_at", desc=True).limit(5).execute()
        if events_resp.data:
            import json
            for i, event in enumerate(events_resp.data, 1):
                print(f"  Event {i}:")
                print(json.dumps(event, indent=4, default=str))
        else:
            print("  ❌ NO DATA FOUND")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    
    # Check user_scores
    print("\n3. USER_SCORES TABLE:")
    try:
        scores_resp = await client.table("user_scores").select("*").eq("student_id", STUDENT_ID).execute()
        if scores_resp.data:
            import json
            print(json.dumps(scores_resp.data[0], indent=2, default=str))
        else:
            print("  ❌ NO DATA FOUND")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    
    # Check user_question_progress
    print("\n4. USER_QUESTION_PROGRESS TABLE:")
    try:
        progress_resp = await client.table("user_question_progress").select("*").eq("profile_id", STUDENT_ID).order("created_at", desc=True).limit(5).execute()
        if progress_resp.data:
            import json
            for i, prog in enumerate(progress_resp.data, 1):
                print(f"  Progress {i}:")
                print(json.dumps(prog, indent=4, default=str))
        else:
            print("  ❌ NO DATA FOUND")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    
    # Check user_badge
    print("\n5. USER_BADGE TABLE:")
    try:
        badge_resp = await client.table("user_badge").select("*").eq("profile_id", STUDENT_ID).execute()
        if badge_resp.data:
            import json
            for i, badge in enumerate(badge_resp.data, 1):
                print(f"  Badge {i}:")
                print(json.dumps(badge, indent=4, default=str))
        else:
            print("  ❌ NO DATA FOUND")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    
    print(f"\n{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
