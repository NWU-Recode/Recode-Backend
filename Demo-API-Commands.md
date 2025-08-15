# Demo API Commands for RecCode Backend

## 1. Sign Up

```powershell
curl "http://localhost:8000/auth/register" --header "Content-Type: application/json" --data '{"email":"brandon.vanvuuren60@gmail.com","password":"Password123!","full_name":"Brandon van Vuuren"}'
```

## 2. Login and Save Token

```powershell
$loginResponse = curl "http://localhost:8000/auth/login" --header "Content-Type: application/json" --data '{"email":"brandon.vanvuuren60@gmail.com","password":"Password123!"}'
$token = ($loginResponse | ConvertFrom-Json).access_token
```

## 3. Get Current User (Get User ID)

```powershell
curl "http://localhost:8000/users/me" --header "Authorization: Bearer $token"
```

## 4. Parse Slides

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/slides/extract/raw" -Method Post -Form @{ file = Get-Item '.\Assets\SU1+T (1).pptx' } -Headers @{ Authorization = "Bearer $token" }
```

## 5. Judge0 Execute Code

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/judge0/execute" -Method Post -Body (@{ source_code = (Get-Content -Raw '.\Assets\code_submission.txt'); language_id = 28; expected_output = 'Hello from Judge0 Marking Service' } | ConvertTo-Json) -ContentType 'application/json' -Headers @{ Authorization = "Bearer $token" } | ConvertTo-Json -Depth 6
```

## 6. Judge0 Submit and Save Code

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/judge0/submit/full?user_id=<USER_ID>" -Method Post -Body (@{ source_code = (Get-Content -Raw '.\Assets\code_submission.txt'); language_id = 28; expected_output = 'Hello from Judge0 Marking Service' } | ConvertTo-Json) -ContentType 'application/json' -Headers @{ Authorization = "Bearer $token" }
```

Replace `<USER_ID>` with your actual user ID from `/users/me`.

---

**Tip:**

- Use `$token` for all authenticated requests.
- Get `<USER_ID>` from the `/users/me` response.
- All commands are ready for PowerShell.
