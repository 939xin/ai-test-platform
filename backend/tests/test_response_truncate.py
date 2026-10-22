"""响应体入库上限（P1-4）：JSON 与非 JSON 同一口径，超限存预览并打标。"""
import json

import app.services.api_executor as api_executor


class _JsonResponse:
    status_code = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, payload):
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _TextResponse:
    status_code = 200
    headers = {"Content-Type": "text/plain"}

    def __init__(self, text):
        self.text = text

    def json(self):
        raise ValueError("not json")


def _run(monkeypatch, response, limit=100):
    monkeypatch.setattr(api_executor.settings, "response_body_max_chars", limit)
    monkeypatch.setattr(api_executor.http_requests, "request", lambda *a, **kw: response)
    return api_executor.execute_case({"method": "GET", "url": "https://example.com/x"})


def test_large_json_body_is_truncated(monkeypatch):
    result = _run(monkeypatch, _JsonResponse({"data": "x" * 500}))

    body = result["response"]["body"]
    assert result["response_truncated"] is True
    assert body["_truncated"] is True
    assert body["_original_chars"] > 100
    assert len(body["preview"]) == 100
    # 整份结果序列化后的长度受控（就是这条卡要保住的东西）
    assert len(json.dumps(result, ensure_ascii=False, default=str)) < 5000


def test_large_text_body_is_truncated(monkeypatch):
    result = _run(monkeypatch, _TextResponse("y" * 500))

    assert result["response_truncated"] is True
    assert result["response"]["body"] == "y" * 100


def test_small_body_untouched(monkeypatch):
    result = _run(monkeypatch, _JsonResponse({"ok": True}))

    assert result["response_truncated"] is False
    assert result["response"]["body"] == {"ok": True}
