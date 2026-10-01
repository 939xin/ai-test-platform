"""对比: 主线程 vs Python原生线程 vs QThread"""
import json, time, threading
import requests as http_requests
from PySide6.QtCore import QThread, Signal

url = "http://localhost:5000/api/v1/auth/login"
body = '{"username": "admin", "password": "1234567", "captcha": "ABCD"}'
headers = {"Content-Type": "application/json; charset=utf-8"}

def do_request(label):
    """发请求，返回 (ok, status, body, time, error)"""
    start = time.time()
    response = None
    error = ""
    try:
        response = http_requests.request('POST', url, data=body.encode('utf-8'),
                                         headers=headers, timeout=30)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    elapsed = (time.time() - start) * 1000
    if response:
        return (True, response.status_code, response.text[:100], elapsed, error)
    else:
        return (False, 0, "", elapsed, error)

# ---------- 测试1: 主线程 ----------
print("=== [1] 主线程直接调用 ===")
ok, status, text, elapsed, err = do_request("main")
print(f"  ok={ok} status={status} time={elapsed:.0f}ms body={text[:60]} error={err}")

# ---------- 测试2: Python原生线程 ----------
print("\n=== [2] Python threading.Thread ===")
result2 = {}
def thread2_run():
    result2['data'] = do_request("py_thread")
t2 = threading.Thread(target=thread2_run)
t2.start()
t2.join(timeout=35)
data = result2.get('data', (False, 0, "", 0, "thread did not complete"))
print(f"  ok={data[0]} status={data[1]} time={data[3]:.0f}ms body={data[2][:60]} error={data[4]}")

# ---------- 测试3: QThread ----------
print("\n=== [3] QThread 不启动Qt事件循环 ===")
class SimpleQThread(QThread):
    def __init__(self):
        super().__init__()
        self.result = None
    def run(self):
        self.result = do_request("qthread_no_loop")

qt = SimpleQThread()
qt.start()
qt.wait(35000)
data = qt.result if qt.result else (False, 0, "", 0, "no result")
print(f"  ok={data[0]} status={data[1]} time={data[3]:.0f}ms body={data[2][:60]} error={data[4]}")

print("\n=== 结论 ===")
print("如果[2]正常[3]失败 -> QThread特有bug，需绕过")
print("如果[2]也失败 -> threading通用bug")
print("如果都正常 -> 工具代码某处有bug")
