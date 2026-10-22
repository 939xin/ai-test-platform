"""断言引擎单元测试。

用 SimpleNamespace 伪造 response —— 断言逻辑只读 status_code 和 json()，
不需要真发请求，也就不会因为外网抖动而红。
"""
from types import SimpleNamespace

from app.services.assertion_engine import evaluate


def _resp(status_code=200, body=None):
    return SimpleNamespace(status_code=status_code, json=lambda: body if body is not None else {})


# ---------- status_code ----------

def test_status_code_eq_pass():
    result = evaluate(_resp(200), 10.0, "status_code", "eq", "200")
    assert result["passed"] is True
    assert "200" in result["message"]


def test_status_code_eq_fail():
    result = evaluate(_resp(500), 10.0, "status_code", "eq", "200")
    assert result["passed"] is False
    assert result["actual"] == "500"


def test_status_code_ne_pass():
    result = evaluate(_resp(500), 10.0, "status_code", "ne", "200")
    assert result["passed"] is True


# ---------- response_time ----------

def test_response_time_lt_pass():
    result = evaluate(_resp(), 100.0, "response_time", "lt", "200")
    assert result["passed"] is True


def test_response_time_gt_fail():
    result = evaluate(_resp(), 100.0, "response_time", "gt", "200")
    assert result["passed"] is False


# ---------- response_body ----------

def test_response_body_eq_pass():
    result = evaluate(_resp(body={"a": 1}), 10.0, "response_body", "eq", "1", "$.a")
    assert result["passed"] is True


def test_response_body_contains_fail():
    result = evaluate(_resp(body={"msg": "ok"}), 10.0, "response_body", "contains", "error", "$.msg")
    assert result["passed"] is False


def test_response_body_bad_jsonpath_returns_failed_not_raise():
    """JSONPath 写错是用户配置问题，按断言失败处理，不能把整条执行打挂。"""
    result = evaluate(_resp(body={"a": 1}), 10.0, "response_body", "eq", "1", "$.[")
    assert result["passed"] is False
    assert "JSONPath" in result["message"]


def test_status_code_expected_not_number_returns_failed():
    """期望值填成 abc 是配置问题：判失败，不抛异常（P0-1 前这里会 500）。"""
    result = evaluate(_resp(200), 10.0, "status_code", "eq", "abc")
    assert result["passed"] is False
    assert "不是合法数字" in result["message"]


def test_response_time_expected_not_number_returns_failed():
    result = evaluate(_resp(), 10.0, "response_time", "lt", "200ms")
    assert result["passed"] is False
    assert "不是合法数字" in result["message"]


def test_status_code_expected_with_spaces_still_parsed():
    """前后空格属于手滑，不算非法数字。"""
    assert evaluate(_resp(200), 10.0, "status_code", "eq", " 200 ")["passed"] is True


def test_unknown_assertion_type_skipped():
    result = evaluate(_resp(), 10.0, "not_a_type", "eq", "1")
    assert result["passed"] is True
    assert "未知断言类型" in result["message"]
