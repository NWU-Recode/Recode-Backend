"""
Direct test to insert into elo_events table
"""
import os
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv
import uuid

load_dotenv()

# Initialize Supabase client
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

print("=" * 80)
print("🧪 TESTING DIRECT INSERT TO elo_events TABLE")
print("=" * 80)

# Test data
student_id = 10000001
test_data = {
    "student_id": student_id,
    "user_id": str(uuid.uuid4()),  # Generate a random UUID
    "event_type": "challenge_completion",
    "elo_change": 50,
    "elo_before": 1500,
    "elo_after": 1550,
    "module_code": "COMP101",
    "semester_id": str(uuid.uuid4()),
    # Don't include challenge_attempt_id - it has a foreign key constraint
    "created_at": datetime.utcnow().isoformat() + "Z",
    "metadata": {
        "test": "direct_insert",
        "challenge_name": "Test Challenge"
    }
}

print(f"\n📝 Inserting test record for student {student_id}...")
print(f"   ELO Change: {test_data['elo_change']}")
print(f"   Module: {test_data['module_code']}")
print(f"   Event Type: {test_data['event_type']}")

try:
    result = supabase.table("elo_events").insert(test_data).execute()
    
    print("\n✅ SUCCESS! Record inserted:")
    print(f"   Record ID: {result.data[0]['id']}")
    print(f"   Student ID: {result.data[0]['student_id']}")
    print(f"   ELO Change: {result.data[0]['elo_change']}")
    print(f"   Module Code: {result.data[0].get('module_code')}")
    print(f"   Semester ID: {result.data[0].get('semester_id')}")
    
    print("\n" + "=" * 80)
    print("🎉 elo_events TABLE IS WORKING!")
    print("=" * 80)
    
    # Now check if we can query it back
    print("\n🔍 Querying back the record...")
    query_result = supabase.table("elo_events").select("*").eq("student_id", student_id).execute()
    
    print(f"✅ Found {len(query_result.data)} record(s) for student {student_id}")
    for record in query_result.data:
        print(f"\n   Record {record['id']}:")
        print(f"   - Student ID: {record['student_id']}")
        print(f"   - ELO Change: {record['elo_change']}")
        print(f"   - ELO Before: {record['elo_before']}")
        print(f"   - ELO After: {record['elo_after']}")
        print(f"   - Module: {record.get('module_code')}")
        print(f"   - Semester: {record.get('semester_id')}")
        print(f"   - Event Type: {record['event_type']}")
        print(f"   - Created: {record['created_at']}")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    if hasattr(e, 'message'):
        print(f"   Message: {e.message}")
    if hasattr(e, 'details'):
        print(f"   Details: {e.details}")

print("\n" + "=" * 80)
