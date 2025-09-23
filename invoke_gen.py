import requests, json, glob, os, sys, time
url='http://127.0.0.1:8000/challenges/generate/base'
headers={'Authorization':'Bearer eyJhbGciOiJIUzI1NiIsImtpZCI6IkhNaUlHZ2I2WnZTblhlS3QiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2d0b2VodmxvZHJtbXF6eXhvYWlsLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiJhM2E4NTM4Yi03YTVkLTQzZWQtODI2Zi0wZGVjNzU0MWFlN2EiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzU4NjYzOTI0LCJpYXQiOjE3NTg2NjAzMjQsImVtYWlsIjoicmVjb2RlcHJvamVjdDBAZ21haWwuY29tIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6eyJlbWFpbCI6InJlY29kZXByb2plY3QwQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmdWxsX25hbWUiOiJUZXN0IFVzZXIiLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInN1YiI6ImEzYTg1MzhiLTdhNWQtNDNlZC04MjZmLTBkZWM3NTQxYWU3YSJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6InBhc3N3b3JkIiwidGltZXN0YW1wIjoxNzU4NjYwMzI0fV0sInNlc3Npb25faWQiOiIwMzBkN2FlZC00YWJlLTQxZjEtODRkOS1mN2JiYWJhZjRmMDMiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.siQidwumhWAGuOVs_d-hEe6s55qQi32cS7BTN14M3Oo'}
payload={'week_number':1,'persist':False,'module_code':'CMPG111'}
try:
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    print('STATUS', r.status_code)
    print(r.text)
except Exception as e:
    print('REQUEST_ERROR', repr(e))
# give server small time to write dump
time.sleep(1)
files = sorted(glob.glob('logs/bedrock_raw_*.json'), key=os.path.getmtime, reverse=True)
print('DUMP_FILES:', files[:5])
if files:
    fn = files[0]
    print('\n=== OPENING DUMP:', fn, '===\n')
    print(open(fn,'r',encoding='utf-8').read())