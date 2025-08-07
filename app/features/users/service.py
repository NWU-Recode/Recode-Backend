from app.db.client import supabase

def get_all_users():
    resp = supabase.table('users').select("*").execute()
    return resp.data or []