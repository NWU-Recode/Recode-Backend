# Authentication Test Commands & Test Suite

## Prerequisites

1. Start the server: `python server.py`
2. Install HTTPie if not installed: `pip install httpie`
3. Install httpx for Python tests: `pip install httpx`

## 🧪 Python Test Script (Recommended)

### Quick Start

```bash
# Basic authentication flow test
python test_token_rotation.py

# Include dev refresh testing
python test_token_rotation.py refresh

# Complete flow including logout
python test_token_rotation.py full
```

### What the Python Test Script Does

The `test_token_rotation.py` script provides comprehensive testing of:

- ✅ User registration and login
- ✅ Cookie-based authentication
- ✅ **Token rotation demonstration** (shows actual token changes)
- ✅ Protected route access
- ✅ Automatic refresh functionality
- ✅ Logout and session clearing
- ✅ Post-logout security verification

### Sample Output (Token Rotation in Action)

```
🧪 Comprehensive Authentication & Cookie Rotation Test
============================================================

🍪 Cookie Status (Start):
   - No cookies in session

📝 Testing Registration...
📄 Register Response: 201 - {"detail":"Registration successful..."}

🔐 Testing Login...
✅ Login successful!
🍪 Cookies set: 2 cookies
   - access_token: eyJhbGciOiJIUzI1NiIs...
   - refresh_token: gezife3pwfuk              ← INITIAL TOKEN

👤 Testing /auth/me...
✅ /auth/me successful!
📄 User: Brandon Test (brandonvanvuuren7@gmail.com) - Role: admin

🔒 Testing Protected Route (profiles)...
✅ Protected route successful! Found 1 profiles

🔄 Testing Token Refresh...
🍪 Current cookies before refresh:
   - refresh_token: gezife3pwfuk              ← OLD TOKEN
✅ Token refresh successful!
🍪 New cookies set: 2 cookies
   - access_token: eyJhbGciOiJIUzI1NiIs...
   - refresh_token: eb7s4vohupod              ← NEW TOKEN (ROTATED!)

🍪 Cookie Status (After Refresh):
   - refresh_token: eb7s4vohupod              ← CONFIRMED ROTATION

🚪 Testing Logout...
✅ Logout successful!

🍪 Cookie Status (After Logout):
   - No cookies in session                   ← COOKIES CLEARED

🔒 Testing access after logout (should fail)...
❌ /auth/me failed: 401 - {"detail":"Missing token"}  ← SECURITY WORKING
```

### Key Features Demonstrated

1. **Token Rotation**: Watch refresh tokens change (`gezife3pwfuk` → `eb7s4vohupod`)
2. **Cookie Management**: See cookies set, updated, and cleared
3. **Security**: Post-logout requests properly rejected
4. **Session Persistence**: Cookies maintained across requests

## 🌐 HTTPie Commands (Manual Testing)

### Test Sequence (in order)

### 1. Register New User

```bash
http --session=jar POST http://localhost:8000/auth/register email=brandonvanvuuren7@gmail.com password='SecretPassword123!' full_name='Brandon van Vuuren'
```

**Expected:** `201 Created` with registration confirmation message

### 2. Login (Get Tokens)

```bash
http --session=jar POST http://localhost:8000/auth/login email=brandonvanvuuren7@gmail.com password='SecretPassword123!'
```

**Expected:** `200 OK` with login confirmation + access_token in response + cookies set

### 3. Get Current User Info

```bash
http --session=jar GET http://localhost:8000/auth/me
```

**Expected:** `200 OK` with user profile (id, email, role, full_name, avatar_url)

### 4. Test Protected Route (Profiles)

```bash
http --session=jar GET http://localhost:8000/profiles/
```

**Expected:** `200 OK` with profiles list (proves authentication works)

### 5. Refresh Tokens

```bash
http --session=jar POST http://localhost:8000/auth/refresh
```

**Expected:** `200 OK` with refresh confirmation + new cookies set

### 6. Test After Refresh (verify new tokens work)

```bash
http --session=jar GET http://localhost:8000/auth/me
```

**Expected:** `200 OK` with same user profile (proves refresh worked)

### 7. Dev Refresh (for expired token testing)

```bash
http --session=jar POST http://localhost:8000/auth/dev/refresh-from-file
```

**Expected:** `200 OK` with dev refresh confirmation + new access_token

### 8. Logout

```bash
http --session=jar POST http://localhost:8000/auth/logout
```

**Expected:** `200 OK` with logout confirmation + cookies cleared

### 9. Verify Logout (should fail)

```bash
http --session=jar GET http://localhost:8000/auth/me
```

**Expected:** `401 Unauthorized` (proves logout worked)

## 🔧 Development Utilities

### Dev Token Utility Script

```bash
# Check current dev token status
python dev_token_util.py status

# Refresh using saved dev token
python dev_token_util.py refresh

# Clear saved dev tokens
python dev_token_util.py clear
```

### What the Dev Utility Does

- **Status**: Shows current saved refresh token and usage count
- **Refresh**: Uses saved token to get new tokens (handles rotation)
- **Clear**: Removes saved dev tokens for fresh start

## 📊 Test Results Summary

### ✅ **Successful Test Indicators**

- **Registration**: `201 Created` with confirmation message
- **Login**: `200 OK` + access_token in response + cookies set
- **Authentication**: `200 OK` for `/auth/me` with user data
- **Protected Routes**: `200 OK` for `/profiles/` with data
- **Token Refresh**: `200 OK` + new cookies with rotated tokens
- **Logout**: `200 OK` + cookies cleared
- **Post-Logout Security**: `401 Unauthorized` for protected routes

### 🔄 **Token Rotation Verification**

Look for these patterns in test output:

```
Before: refresh_token: gezife3pwfuk
After:  refresh_token: eb7s4vohupod  ← Different token = rotation working!
```

### 🛡️ **Security Verification**

- HTTP-only cookies (not accessible via JavaScript)
- Secure flag set for HTTPS
- SameSite=Lax for CSRF protection
- Automatic cookie clearing on logout
- 401 errors for expired/missing tokens

## 🚀 **Quick Testing Commands**

### Full Test Suite (One Command)

```bash
# Complete authentication test with token rotation demo
python test_token_rotation.py full
```

### HTTPie Quick Test

```bash
# Login and test in one session
http --session=jar POST http://localhost:8000/auth/login email=brandonvanvuuren7@gmail.com password='SecretPassword123!' && http --session=jar GET http://localhost:8000/auth/me
```

## Advanced Testing

## 🔍 Advanced Testing

### Token Expiry Testing

```bash
# Method 1: Python script with dev refresh
python test_token_rotation.py refresh

# Method 2: Manual HTTPie testing
http --session=jar POST http://localhost:8000/auth/login email=brandonvanvuuren7@gmail.com password='SecretPassword123!'
# Wait for token expiry or clear session
rm ~/.httpie/sessions/localhost_8000/jar.json  # Linux/Mac
# Windows: del %USERPROFILE%\.httpie\sessions\localhost_8000\jar.json
http POST http://localhost:8000/auth/dev/refresh-from-file
```

### Bearer Token Testing (Alternative to Cookies)

```bash
# Get access token from login response
ACCESS_TOKEN="your_access_token_here"
http GET http://localhost:8000/auth/me Authorization:"Bearer $ACCESS_TOKEN"
```

### Manual Refresh Token Testing

```bash
# Use refresh token directly (not recommended for production)
http POST http://localhost:8000/auth/refresh refresh_token="your_refresh_token_here"
```

### Cookie Inspection

```bash
# View HTTPie session file (shows stored cookies)
# Linux/Mac:
cat ~/.httpie/sessions/localhost_8000/jar.json

# Windows PowerShell:
Get-Content $env:USERPROFILE\.httpie\sessions\localhost_8000\jar.json | ConvertFrom-Json
```

## 🐛 Troubleshooting

### If Registration Fails

- Check if email already exists in Supabase
- Verify Supabase email confirmation settings
- Check server logs for detailed error

### If Login Fails

- Verify email/password combination
- Check if email needs confirmation in Supabase
- Ensure user exists (register first)

### If Protected Routes Fail

- Check if cookies are being set/sent correctly
- Verify access token in cookies hasn't expired
- Try the dev refresh endpoint

## 🐛 Troubleshooting

### Common Issues & Solutions

#### Registration Fails

- **User already exists**: Use different email or login with existing credentials
- **Email confirmation required**: Check Supabase email settings
- **Validation errors**: Verify password meets requirements (SecretPassword123!)

#### Login Fails

- **Invalid credentials**: Verify email/password combination
- **Email not confirmed**: Check if Supabase requires email verification
- **User not found**: Register first with `/auth/register`

#### Protected Routes Return 401

- **Missing cookies**: Ensure login was successful and cookies were set
- **Expired tokens**: Use refresh endpoint or dev refresh utility
- **Cookie domain issues**: Verify server running on correct localhost port

#### Token Refresh Fails

- **Invalid refresh token**: Login again to get fresh tokens
- **Token already used**: Supabase refresh tokens are single-use (this is normal)
- **Token expired**: Use dev refresh or login again

#### Dev Refresh Fails

- **No dev token file**: Login first to generate `.dev_refresh_token.json`
- **Debug mode disabled**: Ensure server is running in debug mode
- **Token rotation**: This is expected behavior with Supabase

### Debugging Commands

```bash
# Check server logs
python server.py  # Watch console output for errors

# Check if dev token file exists
ls -la .dev_refresh_token.json  # Linux/Mac
dir .dev_refresh_token.json     # Windows

# Check HTTPie session
http --print=HhBb --session=jar GET http://localhost:8000/auth/me

# Test without session (should fail)
http GET http://localhost:8000/auth/me
```

### Reset Everything

```bash
# Clear HTTPie session
rm ~/.httpie/sessions/localhost_8000/jar.json     # Linux/Mac
del %USERPROFILE%\.httpie\sessions\localhost_8000\jar.json  # Windows

# Clear dev tokens
python dev_token_util.py clear

# Fresh start
python test_token_rotation.py full
```

## 📈 Expected Test Flow

### Normal Success Pattern

```
Registration → Login → Cookies Set → Protected Access →
Token Refresh → New Cookies → Continued Access →
Logout → Cookies Cleared → Access Denied ✅
```

### Token Rotation Pattern

```
Initial Token: abc123
After Refresh: def456  ← Different = Rotation Working ✅
After 2nd Refresh: ghi789  ← Different Again ✅
```

## 🎯 **TESTING CHECKLIST**

### ✅ **Quick Verification**

```bash
# 1. Start server
python server.py

# 2. Run comprehensive test
python test_token_rotation.py full

# 3. Look for success indicators:
#    - ✅ Login successful!
#    - ✅ Token refresh successful!
#    - Refresh token rotation (different values)
#    - ❌ /auth/me failed: 401 (after logout)
```

### ✅ **Manual Verification**

```bash
# 1. Login
http --session=jar POST http://localhost:8000/auth/login email=brandonvanvuuren7@gmail.com password='SecretPassword123!'

# 2. Check authentication
http --session=jar GET http://localhost:8000/auth/me

# 3. Test protected route
http --session=jar GET http://localhost:8000/profiles/

# 4. Logout
http --session=jar POST http://localhost:8000/auth/logout

# 5. Verify logout (should fail)
http --session=jar GET http://localhost:8000/auth/me
```

---

## 🏆 **SUCCESS CRITERIA**

Your authentication system is working correctly when:

- ✅ Registration creates new users
- ✅ Login returns tokens and sets cookies
- ✅ Protected routes work with cookies
- ✅ Token refresh rotates refresh tokens
- ✅ Logout clears cookies
- ✅ Post-logout requests are rejected (401)

**🎉 All tests passing = Production-ready authentication system!**
