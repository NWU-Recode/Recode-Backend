import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load env variables from .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_one_user():
    # Assumes your users table is named 'users'
    response = supabase.table('users').select('*').limit(1).execute()
    print("User(s):", response.data)

if __name__ == "__main__":
    fetch_one_user()
