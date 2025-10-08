"""Check the user profile to see the ID mappings"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.DB.supabase import get_supabase

UUID = "6f3ac054-c6f5-4b94-b4d4-082c44834c28"
STUDENT_NUMBER = 99999999

async def main():
    client = await get_supabase()
    
    print("\n=== Listing profiles table structure ===")
    profile_resp = await client.table("profiles").select("*").limit(1).execute()
    
    if profile_resp.data:
        import json
        print("Sample profile:")
        print(json.dumps(profile_resp.data[0], indent=2, default=str))
        
        print("\n=== Column names ===")
        for key in profile_resp.data[0].keys():
            print(f"  - {key}")
    else:
        print("❌ NO PROFILES FOUND")
    
    print("\n=== Checking by id (student number) ===")
    profile2_resp = await client.table("profiles").select("*").eq("id", STUDENT_NUMBER).execute()
    
    if profile2_resp.data:
        import json
        print("Found by ID:")
        print(json.dumps(profile2_resp.data[0], indent=2, default=str))
    else:
        print("❌ NO PROFILE FOUND for id=99999999")
    
    print("\n=== Checking by supabase_id (UUID) ===")
    profile3_resp = await client.table("profiles").select("*").eq("supabase_id", UUID).execute()
    
    if profile3_resp.data:
        import json
        print("Found by supabase_id:")
        print(json.dumps(profile3_resp.data[0], indent=2, default=str))
    else:
        print("❌ NO PROFILE FOUND for supabase_id")

if __name__ == "__main__":
    asyncio.run(main())
