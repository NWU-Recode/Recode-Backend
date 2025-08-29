#!/usr/bin/env python3
"""
Judge0 API Testing Script with Authentication
"""

import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000"

async def test_judge0_features():
    """Test Judge0 features with authentication."""
    print("🔧 Judge0 API Testing with Authentication")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        
        # Step 1: Login to get authentication cookies
        print("🔐 Logging in...")
        login_response = await client.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": "brandonvanvuuren7@gmail.com",
                "password": "SecretPassword123!"
            }
        )
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.status_code}")
            return
        
        print(f"✅ Login successful! Cookies: {len(login_response.cookies)} set")
        
        # Step 2: Test public endpoints
        print("\n📋 Testing Public Endpoints...")
        
        # Get languages
        langs_response = await client.get(f"{BASE_URL}/judge0/languages")
        if langs_response.status_code == 200:
            languages = langs_response.json()
            print(f"✅ Languages: Found {len(languages)} supported languages")
            # Show first few
            for lang in languages[:3]:
                print(f"   - {lang['name']} (ID: {lang['id']})")
        else:
            print(f"❌ Languages failed: {langs_response.status_code}")
        
        # Get statuses
        status_response = await client.get(f"{BASE_URL}/judge0/statuses")
        if status_response.status_code == 200:
            statuses = status_response.json()
            print(f"✅ Statuses: Found {len(statuses)} status types")
        else:
            print(f"❌ Statuses failed: {status_response.status_code}")
        
        # Step 3: Test protected endpoints
        print("\n🔒 Testing Protected Endpoints...")
        
        # Test simple execution
        test_code = {
            "source_code": 'print("Hello from Judge0!")',
            "language_id": 71  # Python 3
        }
        
        # Submit and wait
        print("⏱️  Testing submit/wait...")
        wait_response = await client.post(
            f"{BASE_URL}/judge0/submit/wait",
            json=test_code
        )
        
        if wait_response.status_code == 200:
            result = wait_response.json()
            print(f"✅ Submit/wait successful!")
            print(f"   Output: {result.get('stdout', 'No output')}")
            print(f"   Status: {result.get('status_description', 'Unknown')}")
            print(f"   Success: {result.get('success', False)}")
        else:
            print(f"❌ Submit/wait failed: {wait_response.status_code} - {wait_response.text}")
        
        # Submit with persistence
        print("\n💾 Testing submit/full (with persistence)...")
        full_response = await client.post(
            f"{BASE_URL}/judge0/submit/full",
            json=test_code
        )
        
        if full_response.status_code == 200:
            submission = full_response.json()
            print(f"✅ Submit/full successful!")
            print(f"   Token: {submission.get('judge0_token', 'No token')}")
            print(f"   Submission ID: {submission.get('id', 'No ID')}")
            
            # Get result by token
            if submission.get('judge0_token'):
                token = submission['judge0_token']
                print(f"\n🔍 Getting result for token: {token}")
                
                result_response = await client.get(f"{BASE_URL}/judge0/result/{token}")
                if result_response.status_code == 200:
                    result = result_response.json()
                    print(f"✅ Result retrieved!")
                    print(f"   Output: {result.get('stdout', 'No output')}")
                    print(f"   Status: {result.get('status_description', 'Unknown')}")
                    print(f"   Execution Time: {result.get('execution_time', 'Unknown')}s")
                else:
                    print(f"❌ Result retrieval failed: {result_response.status_code}")
        else:
            print(f"❌ Submit/full failed: {full_response.status_code} - {full_response.text}")
        
        # Test different languages
        print("\n🐍 Testing different languages...")
        
        test_cases = [
            {"name": "Python", "code": 'print("Python works!")', "language_id": 71},
            {"name": "JavaScript", "code": 'console.log("JavaScript works!");', "language_id": 63},
            {"name": "C++", "code": '#include<iostream>\nint main(){std::cout<<"C++ works!";return 0;}', "language_id": 54},
        ]
        
        for test_case in test_cases:
            print(f"   Testing {test_case['name']}...")
            lang_response = await client.post(
                f"{BASE_URL}/judge0/execute/stdout",
                json={
                    "source_code": test_case["code"],
                    "language_id": test_case["language_id"]
                }
            )
            
            if lang_response.status_code == 200:
                result = lang_response.json()
                print(f"   ✅ {test_case['name']}: {result.get('stdout', 'No output').strip()}")
            else:
                print(f"   ❌ {test_case['name']}: Failed ({lang_response.status_code})")
        
        print("\n🎉 Judge0 testing complete!")
        print("\n💡 Available endpoints:")
        print("   GET  /judge0/languages     - List supported languages")
        print("   GET  /judge0/statuses      - List status types")
        print("   POST /judge0/submit        - Submit code (get token)")
        print("   POST /judge0/submit/wait   - Submit and wait for result")
        print("   POST /judge0/submit/full   - Submit with persistence")
        print("   GET  /judge0/result/{token} - Get result by token")
        print("   POST /judge0/execute       - Execute code immediately")
        print("   POST /judge0/execute/stdout - Execute and get stdout only")


if __name__ == "__main__":
    asyncio.run(test_judge0_features())
