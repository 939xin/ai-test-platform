"""脱敏单元测试：压测与功能执行共用同一套规则（P0-6）。"""
import app.services.api_executor as api_executor
from app.services.sanitize import (
    redact_headers,
    redact_query_params,
    redact_url,
    scrub_message,
)


# ---------- 纯函数 ----------

def test_redact_headers_masks_credentials_only():
    result = redact_headers({
        "Authorization": "Bearer abc",
        "Cookie": "s=1",
        "X-Trace": "1",
    })
    assert result["Authorization"] == "***"
    assert result["Cookie"] == "***"
    assert result["X-Trace"] == "1"


def test_redact_headers_is_case_insensitive():
    result = redact_headers({"authorization": "Bearer abc", "SET-COOKIE": "s=1"})
    assert result == {"authorization": "***", "SET-COOKIE": "***"}


def test_redact_query_params_masks_sensitive_keys():
    assert redact_query_params({"token": "abc", "page": "2"}) == {"token": "***", "page": "2"}


def test_redact_url_keeps_path_and_non_sensitive_query():
    url = redact_url("https://api.example.com/users/7?token=abc&page=2")
    # urlencode 会把 *** 编码成 %2A%2A%2A —— 这是压测一直以来的落库格式，保持不变
    assert "token=%2A%2A%2A" in url
    assert "page=2" in url
    assert "/users/7" in url


def test_scrub_message_masks_inline_password():
    assert "password=***" in scrub_message("connect failed password=hunter2&x=1")


# ---------- 执行结果快照 ----------

class _FakeResponse:
    status_code = 200
    headers = {"Set-Cookie": "sid=secret", "Content-Type": "application/json"}
    text = '{"token": "from-body"}'

    def json(self):
        return {"token": "from-body"}


def test_execute_case_masks_request_and_response_headers(monkeypatch):
    monkeypatch.setattr(
        api_executor.http_requests, "request", lambda *a, **kw: _FakeResponse()
    )

    result = api_executor.execute_case({
        "method": "GET",
        "url": "https://example.com/x",
        "headers_json": {"Authorization": "Bearer real-token", "X-Trace": "1"},
    })

    assert result["status"] == "pass"
    assert result["request"]["headers"]["Authorization"] == "***"
    assert result["request"]["headers"]["X-Trace"] == "1"
    assert result["response"]["headers"]["Set-Cookie"] == "***"
    assert result["response"]["headers"]["Content-Type"] == "application/json"

    # 响应体不动：用例可能要断言里面的 token
    assert result["response"]["body"]["token"] == "from-body"
    # 原始令牌不能再出现在整份结果里
    assert "real-token" not in str(result)
