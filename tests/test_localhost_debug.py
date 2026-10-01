"""
逐步模拟工具内部调用，找出哪个环节导致 localhost 无响应
"""
import json, time
import requests as http_requests  # 完全和 api_runner.py 一样的 import 方式

body_content = '{"username": "admin", "password": "1234567", "captcha": "ABCD"}'
url = "http://localhost:5000/api/v1/auth/login"
method = "POST"
headers = {"Content-Type": "application/json; charset=utf-8"}
timeout = 30

print("=== 逐步对比测试 ===")

# 步骤1: 和测试脚本完全一样的方式（已验证能通）
print("\n[1] requests.post(data=...)  -- 参考基准")
try:
    r = http_requests.post(url, data=body_content.encode('utf-8'), headers=headers, timeout=10)
    print(f"    Status: {r.status_code}, Body: {r.text[:100]}")
except Exception as e:
    print(f"    ERROR: {type(e).__name__}: {e}")

# 步骤2: 用 requests.request() 代替 .post()（工具用的是 .request()）
print("\n[2] requests.request('POST', data=...)  -- 换用 .request()")
try:
    r = http_requests.request('POST', url, data=body_content.encode('utf-8'), headers=headers, timeout=10)
    print(f"    Status: {r.status_code}, Body: {r.text[:100]}")
except Exception as e:
    print(f"    ERROR: {type(e).__name__}: {e}")

# 步骤3: 加上 verify=True（工具默认传 verify=self.verify_ssl）
print("\n[3] requests.request() + verify=True  -- 工具传来的参数")
try:
    r = http_requests.request('POST', url, data=body_content.encode('utf-8'),
                              headers=headers, timeout=10, verify=True)
    print(f"    Status: {r.status_code}, Body: {r.text[:100]}")
except Exception as e:
    print(f"    ERROR: {type(e).__name__}: {e}")

# 步骤4: 用 **kwargs 展开（工具内部用 req_kwargs 展开）
print("\n[4] requests.request() with **kwargs  -- 完全模拟工具方式")
req_kwargs = {
    'headers': headers,
    'timeout': 30,
    'data': body_content.encode('utf-8'),
}
try:
    r = http_requests.request(method='POST', url=url, verify=True, **req_kwargs)
    print(f"    Status: {r.status_code}, Body: {r.text[:100]}")
except Exception as e:
    print(f"    ERROR: {type(e).__name__}: {e}")

# 步骤5: 加 try/except 框架（和工具一模一样的异常处理）
print("\n[5] 和工具完全一样的 try/except 框架")
response = None
error_msg = ""
try:
    response = http_requests.request(method='POST', url=url, verify=True, **req_kwargs)
except http_requests.exceptions.ConnectionError as e:
    error_msg = f"连接失败: {str(e)[:200]}"
    print(f"    {error_msg}")
except http_requests.exceptions.Timeout:
    error_msg = "请求超时"
    print(f"    {error_msg}")
except Exception as e:
    error_msg = f"请求异常: {type(e).__name__}: {str(e)[:150]}"
    print(f"    {error_msg}")

print(f"    response is None: {response is None}")
print(f"    response: {response}")
if response is None and not error_msg:
    print(f"    >>> 这就是BUG！response=None 但没抓异常 <<<")
if response is not None:
    print(f"    Status: {response.status_code}, Body: {response.text[:100]}")

print("\n=== 对比结论 ===")
print("如果步骤1-4都正常但步骤5出问题，说明异常处理框架有bug")
print("如果步骤4就出问题，说明 **kwargs 展开有问题")
print("如果都正常，说明工具运行时环境有额外变量（代理/环境变量）影响")
