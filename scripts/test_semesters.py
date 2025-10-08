"""
Test the semesters list endpoint
"""
import requests
import json

URL = "http://127.0.0.1:8000/semesters/"

print(f"\n{'='*60}")
print(f"TESTING SEMESTERS ENDPOINT")
print(f"{'='*60}")
print(f"URL: {URL}")
print(f"\nMaking request...")

try:
    response = requests.get(URL, timeout=10)
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        print("\n✅ SUCCESS! Semesters endpoint is working!")
        result = response.json()
        print(f"\nFound {len(result)} semester(s):")
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\n❌ FAILED!")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")

print(f"\n{'='*60}\n")
