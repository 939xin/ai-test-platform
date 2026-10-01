import requests
import json

body = {"username": "admin", "password": "1234567", "captcha": "ABCD"}
headers = {"Content-Type": "application/json; charset=utf-8"}

print("Sending POST to http://localhost:5000/api/v1/auth/login")
print(f"Headers: {headers}")
print(f"Body: {json.dumps(body, ensure_ascii=False)}")
print()

try:
    r = requests.post(
        "http://localhost:5000/api/v1/auth/login",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        timeout=10
    )
    print(f"Status: {r.status_code}")
    print(f"Headers: {dict(r.headers)}")
    print(f"Body: {r.text}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
