"""
Submit challenge with proper authentication
"""
import requests
import json

TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IkhNaUlHZ2I2WnZTblhlS3QiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2d0b2VodmxvZHJtbXF6eXhvYWlsLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI2ZjNhYzA1NC1jNmY1LTRiOTQtYjRkNC0wODJjNDQ4MzRjMjgiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU5ODgzMjk1LCJpYXQiOjE3NTk4Nzk2OTUsImVtYWlsIjoiMzQyNTAxMTVAbXlud3UuYWMuemEiLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsIjoiMzQyNTAxMTVAbXlud3UuYWMuemEiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiZnVsbF9uYW1lIjoiQnJhbmRvbiB2YW4gVnV1cmVuIE5XVSIsInBob25lX3ZlcmlmaWVkIjpmYWxzZSwic3R1ZGVudF9udW1iZXIiOjk5OTk5OTk5LCJzdWIiOiI2ZjNhYzA1NC1jNmY1LTRiOTQtYjRkNC0wODJjNDQ4MzRjMjgifSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc1OTg3OTY5NX1dLCJzZXNzaW9uX2lkIjoiMTdkYWQ3NDEtMDFhMi00NjliLWI0OTAtNWY2ZmIwYzBmZWM1IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.y3FCA05JgyYMYWacnIu7k03ClV4bw-1akH44RE3nOl4"

CHALLENGE_ID = "6e957ff3-13fc-48e7-9622-b86b43f2d0b5"

URL = f"http://127.0.0.1:8000/submissions/challenges/{CHALLENGE_ID}/submit-challenge"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}

# Load payload
with open("CORRECT_submission_payload.json", "r") as f:
    payload = json.load(f)

print(f"\n{'='*60}")
print(f"SUBMITTING CHALLENGE")
print(f"{'='*60}")
print(f"Challenge ID: {CHALLENGE_ID}")
print(f"Student: 99999999")
print(f"Questions: {len(payload['submissions'])}")
print(f"\nMaking request...")

try:
    response = requests.post(URL, headers=headers, json=payload, timeout=120)
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        print("\n✅ SUBMISSION SUCCESSFUL!")
        result = response.json()
        print(json.dumps(result, indent=2))
    else:
        print(f"\n❌ SUBMISSION FAILED!")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")
