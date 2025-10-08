"""
Decode JWT token to see user info
"""
import base64
import json

token = "eyJhbGciOiJIUzI1NiIsImtpZCI6IkhNaUlHZ2I2WnZTblhlS3QiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2d0b2VodmxvZHJtbXF6eXhvYWlsLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI2ZjNhYzA1NC1jNmY1LTRiOTQtYjRkNC0wODJjNDQ4MzRjMjgiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU5ODgzMjk1LCJpYXQiOjE3NTk4Nzk2OTUsImVtYWlsIjoiMzQyNTAxMTVAbXlud3UuYWMuemEiLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsIjoiMzQyNTAxMTVAbXlud3UuYWMuemEiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiZnVsbF9uYW1lIjoiQnJhbmRvbiB2YW4gVnV1cmVuIE5XVSIsInBob25lX3ZlcmlmaWVkIjpmYWxzZSwic3R1ZGVudF9udW1iZXIiOjk5OTk5OTk5LCJzdWIiOiI2ZjNhYzA1NC1jNmY1LTRiOTQtYjRkNC0wODJjNDQ4MzRjMjgifSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc1OTg3OTY5NX1dLCJzZXNzaW9uX2lkIjoiMTdkYWQ3NDEtMDFhMi00NjliLWI0OTAtNWY2ZmIwYzBmZWM1IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.y3FCA05JgyYMYWacnIu7k03ClV4bw-1akH44RE3nOl4"

# Split token
parts = token.split('.')
payload = parts[1]

# Add padding if needed
padding = 4 - len(payload) % 4
if padding != 4:
    payload += '=' * padding

# Decode
decoded = base64.b64decode(payload)
data = json.loads(decoded)

print(json.dumps(data, indent=2))

print("\n" + "="*60)
print("KEY INFO:")
print("="*60)
print(f"Student Number: {data['user_metadata']['student_number']}")
print(f"Email: {data['email']}")
print(f"User ID (sub): {data['sub']}")
print(f"Role: {data['role']}")
