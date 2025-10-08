"""Find the challenge ID that contains the specific question IDs"""
import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.DB.supabase import get_supabase

async def find_challenge():
    client = await get_supabase()
    
    # Question IDs from the payload
    question_ids = [
        "6363385e-ff33-464b-a106-c6a6ae74018e",
        "c672ca99-0355-444b-837f-4834e811d872",
        "388a2b21-bab3-44a0-bd02-907adeebf686",
        "77bdcd12-700e-4215-bf19-2ff134f1f33d",
        "7070bee5-088c-471c-af8b-9cbeb69ad4e8"
    ]
    
    print("🔍 Searching for challenge containing these questions...\n")
    
    # Get all questions with these IDs
    for qid in question_ids:
        try:
            resp = await client.table("questions").select("id, challenge_id, title, question_number").eq("id", qid).execute()
            if resp.data:
                q = resp.data[0]
                print(f"✅ Question {qid[:8]}...")
                print(f"   Challenge ID: {q.get('challenge_id')}")
                print(f"   Title: {q.get('title')}")
                print(f"   Question #: {q.get('question_number')}")
            else:
                print(f"❌ Question {qid[:8]}... NOT FOUND")
            print()
        except Exception as e:
            print(f"❌ Error checking question {qid[:8]}...: {e}\n")
    
    # Find common challenge_id
    print("\n" + "="*60)
    print("🎯 Finding common challenge ID...")
    print("="*60 + "\n")
    
    try:
        # Query all questions with these IDs
        resp = await client.table("questions").select("challenge_id, id").in_("id", question_ids).execute()
        
        if resp.data:
            challenge_ids = {}
            for q in resp.data:
                cid = q.get('challenge_id')
                if cid:
                    challenge_ids[cid] = challenge_ids.get(cid, 0) + 1
            
            print(f"Found {len(resp.data)} questions across {len(challenge_ids)} challenge(s):\n")
            
            for cid, count in challenge_ids.items():
                print(f"  Challenge {cid}: {count} questions")
                
                # Get challenge details
                try:
                    c_resp = await client.table("challenges").select("id, title, tier, week_number, module_code").eq("id", cid).execute()
                    if c_resp.data:
                        c = c_resp.data[0]
                        print(f"    Title: {c.get('title')}")
                        print(f"    Tier: {c.get('tier')}")
                        print(f"    Week: {c.get('week_number')}")
                        print(f"    Module: {c.get('module_code')}")
                except Exception:
                    pass
                print()
            
            # Find the challenge with most questions
            best_challenge = max(challenge_ids.items(), key=lambda x: x[1])
            print(f"✅ CORRECT CHALLENGE ID: {best_challenge[0]}")
            print(f"   (Contains {best_challenge[1]} out of {len(question_ids)} questions)")
            
            return best_challenge[0]
        else:
            print("❌ No questions found with those IDs!")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    challenge_id = asyncio.run(find_challenge())
    if challenge_id:
        print(f"\n{'='*60}")
        print(f"USE THIS CHALLENGE ID: {challenge_id}")
        print(f"{'='*60}")
