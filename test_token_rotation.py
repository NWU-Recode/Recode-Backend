#!/usr/bin/env python3
"""
Comprehensive test script for Supabase authentication with cookie rotation.
Tests the complete authentication flow with persistent session cookies.
"""

import asyncio
import httpx
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"
DEV_TOKEN_FILE = Path(".dev_refresh_token.json")


async def test_register(client):
    """Test user registration."""
    print("📝 Testing Registration...")
    
    response = await client.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": "brandonvanvuuren7@gmail.com",
            "password": "SecretPassword123!",
            "full_name": "Brandon van Vuuren"
        }
    )
    
    print(f"📄 Register Response: {response.status_code} - {response.text}")
    return response.status_code in [201, 400]  # 400 might be "user already exists"


async def test_login(client):
    """Test login and save initial tokens."""
    print("\n🔐 Testing Login...")
    
    response = await client.post(
        f"{BASE_URL}/auth/login",
        json={
            "email": "brandonvanvuuren7@gmail.com",
            "password": "SecretPassword123!"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Login successful!")
        print(f"📄 Response: {data}")
        print(f"🍪 Cookies set: {len(response.cookies)} cookies")
        for name, value in response.cookies.items():
            value_preview = value[:20] + "..." if len(value) > 20 else value
            print(f"   - {name}: {value_preview}")
        
        # Check if dev token was saved
        if DEV_TOKEN_FILE.exists():
            token_data = json.loads(DEV_TOKEN_FILE.read_text())
            print(f"💾 Dev token saved: {token_data['note']}")
        
        return True
    else:
        print(f"❌ Login failed: {response.status_code} - {response.text}")
        return False


async def test_me_endpoint(client):
    """Test the /auth/me endpoint."""
    print("\n👤 Testing /auth/me...")
    
    response = await client.get(f"{BASE_URL}/auth/me")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ /auth/me successful!")
        print(f"📄 User: {data.get('full_name')} ({data.get('email')}) - Role: {data.get('role')}")
        return True
    else:
        print(f"❌ /auth/me failed: {response.status_code} - {response.text}")
        return False


async def test_protected_route(client):
    """Test accessing a protected route."""
    print("\n🔒 Testing Protected Route (profiles)...")
    
    response = await client.get(f"{BASE_URL}/profiles/")
    
    if response.status_code == 200:
        data = response.json()
        profiles_count = len(data) if isinstance(data, list) else "N/A"
        print(f"✅ Protected route successful! Found {profiles_count} profiles")
        return True
    else:
        print(f"❌ Protected route failed: {response.status_code} - {response.text[:100]}...")
        return False


async def test_refresh_endpoint(client):
    """Test the /auth/refresh endpoint."""
    print("\n🔄 Testing Token Refresh...")
    
    print("🍪 Current cookies before refresh:")
    if client.cookies:
        for name, value in client.cookies.items():
            value_preview = value[:20] + "..." if len(value) > 20 else value
            print(f"   - {name}: {value_preview}")
    else:
        print("   - No cookies in session")
    
    response = await client.post(f"{BASE_URL}/auth/refresh")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Token refresh successful!")
        print(f"📄 Response: {data}")
        
        # Show new cookies set
        if response.cookies:
            print(f"🍪 New cookies set: {len(response.cookies)} cookies")
            for name, value in response.cookies.items():
                value_preview = value[:20] + "..." if len(value) > 20 else value
                print(f"   - {name}: {value_preview}")
        else:
            print("🍪 No new cookies in response (may be using existing ones)")
        
        return True
    else:
        print(f"❌ Token refresh failed: {response.status_code} - {response.text}")
        return False


async def test_dev_refresh(client):
    """Test the dev refresh endpoint."""
    print("\n🔄 Testing Dev Refresh (from file)...")
    
    if not DEV_TOKEN_FILE.exists():
        print("❌ No dev token file found. Login first.")
        return False
    
    response = await client.post(f"{BASE_URL}/auth/dev/refresh-from-file")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Dev refresh successful!")
        print(f"📄 Response: {data}")
        
        # Show new cookies
        if response.cookies:
            print(f"🍪 New cookies from dev refresh: {len(response.cookies)} cookies")
            for name, value in response.cookies.items():
                value_preview = value[:20] + "..." if len(value) > 20 else value
                print(f"   - {name}: {value_preview}")
        
        return True
    else:
        print(f"❌ Dev refresh failed: {response.status_code} - {response.text}")
        return False


async def test_logout(client):
    """Test the logout endpoint."""
    print("\n🚪 Testing Logout...")
    
    response = await client.post(f"{BASE_URL}/auth/logout")
    
    if response.status_code == 200:
        print("✅ Logout successful!")
        print(f"📄 Response: {response.json()}")
        
        # Check if cookies were cleared
        if response.cookies:
            print(f"🍪 Logout cookies: {len(response.cookies)} cookies")
            for name, value in response.cookies.items():
                print(f"   - {name}: {value} (cleared)")
        
        return True
    else:
        print(f"❌ Logout failed: {response.status_code} - {response.text}")
        return False


async def show_cookie_status(client, step_name):
    """Show current cookie status."""
    print(f"\n🍪 Cookie Status ({step_name}):")
    if client.cookies:
        for name, value in client.cookies.items():
            value_preview = value[:20] + "..." if len(value) > 20 else value
            print(f"   - {name}: {value_preview}")
    else:
        print("   - No cookies in session")


async def main():
    """Main test function with comprehensive cookie testing."""
    print("🧪 Comprehensive Authentication & Cookie Rotation Test")
    print("=" * 60)
    
    # Use a persistent client session to maintain cookies
    async with httpx.AsyncClient() as client:
        
        # Initial cookie status
        await show_cookie_status(client, "Start")
        
        # Step 1: Register (might fail if user exists, that's OK)
        await test_register(client)
        
        # Step 2: Login and get initial cookies
        login_success = await test_login(client)
        if not login_success:
            print("❌ Cannot continue without successful login")
            return
        
        await show_cookie_status(client, "After Login")
        
        # Step 3: Test /auth/me endpoint (should work with cookies)
        await test_me_endpoint(client)
        
        # Step 4: Test protected route (should work with cookies)
        await test_protected_route(client)
        
        # Step 5: Test standard refresh endpoint
        await test_refresh_endpoint(client)
        await show_cookie_status(client, "After Refresh")
        
        # Step 6: Verify authentication still works after refresh
        await test_me_endpoint(client)
        await test_protected_route(client)
        
        # Step 7: Test dev refresh (if requested)
        if len(__import__('sys').argv) > 1 and 'refresh' in __import__('sys').argv[1]:
            await test_dev_refresh(client)
            await show_cookie_status(client, "After Dev Refresh")
            await test_me_endpoint(client)
            await test_protected_route(client)
        
        # Step 8: Test logout (if full test requested)
        if len(__import__('sys').argv) > 1 and 'full' in __import__('sys').argv[1]:
            await test_logout(client)
            await show_cookie_status(client, "After Logout")
            
            # Step 9: Verify logout worked (should fail)
            print("\n🔒 Testing access after logout (should fail)...")
            await test_me_endpoint(client)
            await test_protected_route(client)
        
        print("\n🎉 Test sequence complete!")
        print("\n💡 Usage:")
        print("   python test_token_rotation.py          # Basic flow")
        print("   python test_token_rotation.py refresh  # Include dev refresh test")
        print("   python test_token_rotation.py full     # Complete flow including logout")


if __name__ == "__main__":
    asyncio.run(main())
