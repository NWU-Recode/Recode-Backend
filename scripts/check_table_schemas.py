"""
Check the actual schemas of all achievement tables to match with repository code
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.DB.supabase import get_supabase

async def main():
    client = await get_supabase()
    
    tables = [
        "user_elo",
        "elo_events",
        "user_scores",
        "user_question_progress",
        "user_badge"
    ]
    
    for table_name in tables:
        print(f"\n{'='*60}")
        print(f"TABLE: {table_name}")
        print(f"{'='*60}")
        
        try:
            # Try to get one row to see the schema
            result = await client.table(table_name).select("*").limit(1).execute()
            
            if result.data and len(result.data) > 0:
                print("Columns found:")
                for col in result.data[0].keys():
                    print(f"  - {col}")
            else:
                # No data, try to insert empty to see required columns
                print("No existing data. Attempting empty insert to see required columns...")
                try:
                    await client.table(table_name).insert({}).execute()
                except Exception as e:
                    error_msg = str(e)
                    print(f"Error (shows required columns): {error_msg}")
        except Exception as e:
            print(f"ERROR accessing table: {e}")

if __name__ == "__main__":
    asyncio.run(main())
