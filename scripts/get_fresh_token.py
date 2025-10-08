"""
Login to get a fresh JWT token
"""
import requests
import json

# Your credentials
EMAIL = "34250115@mynwu.ac.za"
# Replace with your actual password
PASSWORD = "YOUR_PASSWORD_HERE"  # CHANGE THIS

URL = "http://127.0.0.1:8000/api/auth/login"

payload = {
    "email": EMAIL,
    "password": PASSWORD
}

print(f"\n{'='*60}")
print(f"LOGGING IN")
print(f"{'='*60}")
print(f"Email: {EMAIL}")
print(f"\nMaking request...")

try:
    response = requests.post(URL, json=payload, timeout=30)
    
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        print("\n✅ LOGIN SUCCESSFUL!")
        result = response.json()
        token = result.get("access_token")
        
        if token:
            print(f"\n🔑 Your JWT Token:")
            print(f"{token}")
            print(f"\n📋 Use this token in submit_challenge.py")
            
            # Decode to show expiration
            import base64
            parts = token.split('.')
            payload_part = parts[1]
            padding = 4 - len(payload_part) % 4
            if padding != 4:
                payload_part += '=' * padding
            decoded = base64.b64decode(payload_part)
            data = json.loads(decoded)
            
            from datetime import datetime
            exp_timestamp = data.get('exp')
            exp_date = datetime.fromtimestamp(exp_timestamp)
            print(f"\n⏰ Token expires: {exp_date}")
        else:
            print("\n❌ No token in response!")
            print(json.dumps(result, indent=2))
    else:
        print(f"\n❌ LOGIN FAILED!")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")

print(f"\n{'='*60}\n")
