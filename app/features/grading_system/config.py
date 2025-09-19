# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # loads the .env file

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# Database
DATABASE_URL = os.getenv("DATABASE_URL")

# Judge0
JUDGE0_BASE_URL = os.getenv("JUDGE0_BASE_URL")
JUDGE0_KEY = os.getenv("JUDGE0_KEY")
JUDGE0_HOST = os.getenv("JUDGE0_HOST")

# Debug/Dev flags
DEBUG = os.getenv("DEBUG") == "True"
DEV_AUTO_CONFIRM = os.getenv("DEV_AUTO_CONFIRM") == "True"
