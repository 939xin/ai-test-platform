"""测试QThread内发请求是否正常"""
import json, time
import requests as http_requests
from PySide6.QtCore import QThread, Signal

class TestThread(QThread):
    log = Signal(str)
    done = Signal(dict)

    def run(self):
        body = '{"username": "admin", "password": "1234567", "captcha": "ABCD"}'
        headers = {"Content-Type": "application/json; charset=utf-8"}
        url = "http://localhost:5000/api/v1/auth/login"

        self.log.emit(f"QThread: 开始请求 {url}")
        start = time.time()
        response = None
        error = ""

        try:
            response = http_requests.request(
                'POST', url,
                data=body.encode('utf-8'),
                headers=headers,
                timeout=30,
                verify=True
            )
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            self.log.emit(f"QThread: 异常 - {error}")

        elapsed = (time.time() - start) * 1000

        if response:
            self.log.emit(f"QThread: Status={response.status_code} Time={elapsed:.0f}ms")
            self.done.emit({"ok": True, "status": response.status_code, "body": response.text, "time": elapsed})
        else:
            self.log.emit(f"QThread: 无响应! error={error} Time={elapsed:.0f}ms")
            self.done.emit({"ok": False, "error": error, "time": elapsed})

print("=== QThread 请求测试 ===")
print("主线程: 创建 TestThread...")

from PySide6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)

result = {}
def on_done(data):
    global result
    result = data
    print(f"主线程收到结果: {data}")
    app.quit()

def on_log(text):
    print(f"  {text}")

thread = TestThread()
thread.log.connect(on_log)
thread.done.connect(on_done)
thread.start()

print("主线程: QThread 已启动，等待结果...")
app.exec()

print()
if result.get("ok"):
    print(f"结论: QThread内requests正常! status={result['status']}")
else:
    print(f"结论: QThread内requests失败! error={result.get('error')}")
