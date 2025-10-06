"""
Check the actual structure of user_elo, user_badge, and elo_events tables
"""
import asyncio
from app.DB.supabase import get_supabase

async def check_table_structures():
    try:
        client = await get_supabase()
        
        tables = ["user_elo", "user_badge", "elo_events"]
        
        for table_name in tables:
            print("=" * 80)
            print(f"TABLE: {table_name}")
            print("=" * 80)
            
            try:
                # Get a sample row to see the actual columns
                resp = await client.table(table_name).select("*").limit(1).execute()
                
                if resp.data and len(resp.data) > 0:
                    print(f"\nColumns found:")
                    for key in resp.data[0].keys():
                        print(f"  - {key}")
                    print(f"\nSample row:")
                    print(resp.data[0])
                else:
                    print(f"\n✅ Table exists but is EMPTY")
                    print("Cannot determine columns from empty table")
                    
            except Exception as e:
                error_str = str(e).lower()
                if "does not exist" in error_str:
                    print(f"\n❌ Table DOES NOT EXIST")
                else:
                    print(f"\n❌ Error: {e}")
            
            print()
                
    except Exception as e:
        print(f"❌ Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(check_table_structures())
