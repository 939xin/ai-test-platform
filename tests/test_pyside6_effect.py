import json, time

# 先不 import PySide6，发请求
import requests
url = "http://localhost:5000/api/v1/auth/login"
body = '{"username":"admin","password":"1234567","captcha":"ABCD"}'
headers = {"Content-Type": "application/json; charset=utf-8"}

print("=== 1. 导入PySide6之前 ===")
try:
    r = requests.post(url, data=body.encode('utf-8'), headers=headers, timeout=10)
    print(f"  ok status={r.status_code} body={r.text[:80]}")
except Exception as e:
    print(f"  ERROR: {e}")

# 现在 import PySide6
print("\n=== 2. 导入PySide6之后 ===")
from PySide6.QtCore import QThread
try:
    r = requests.post(url, data=body.encode('utf-8'), headers=headers, timeout=10)
    print(f"  ok status={r.status_code} body={r.text[:80]}")
except Exception as e:
    print(f"  ERROR: {e}")
