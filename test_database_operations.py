#!/usr/bin/env python3
"""
Test direct database operations to see if writes are working.
"""
import asyncio
from app.DB.supabase import get_supabase

async def main():
    print("=" * 80)
    print("🧪 TESTING DIRECT DATABASE OPERATIONS")
    print("=" * 80)
    
    student_id = 10000001
    client = await get_supabase()
    
    # Test 1: Try to insert into user_elo
    print("\n📝 Test 1: Insert into user_elo")
    print("-" * 80)
    try:
        payload = {
            "student_id": student_id,
            "elo_points": 999,
            "running_gpa": 4.0,
            "updated_at": "2025-01-01T00:00:00+00:00",
        }
        result = await client.table('user_elo').insert(payload).execute()
        print(f"✅ Insert successful: {result.data}")
    except Exception as e:
        print(f"❌ Insert failed: {e}")
    
    # Test 2: Query the record we just inserted
    print("\n📝 Test 2: Query user_elo")
    print("-" * 80)
    try:
        result = await client.table('user_elo').select('*').eq('student_id', student_id).execute()
        if result.data:
            print(f"✅ Found {len(result.data)} records:")
            for record in result.data:
                print(f"   ELO: {record.get('elo_points')}, GPA: {record.get('running_gpa')}")
        else:
            print("❌ No records found")
    except Exception as e:
        print(f"❌ Query failed: {e}")
    
    # Test 3: Try to update
    print("\n📝 Test 3: Update user_elo")
    print("-" * 80)
    try:
        result = await client.table('user_elo').update({"elo_points": 1234}).eq('student_id', student_id).execute()
        print(f"✅ Update successful: {result.data}")
    except Exception as e:
        print(f"❌ Update failed: {e}")
    
    # Test 4: Clean up
    print("\n📝 Test 4: Delete test record")
    print("-" * 80)
    try:
        result = await client.table('user_elo').delete().eq('student_id', student_id).execute()
        print(f"✅ Delete successful: {result.data}")
    except Exception as e:
        print(f"❌ Delete failed: {e}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
