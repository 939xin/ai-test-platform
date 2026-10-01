"""接口执行器 — 搬自旧项目 app/engine/api_runner.py 的请求构造与发送部分。

剥掉 QThread 和 DBManager，改成无状态的纯函数，供 FastAPI 直接调用。
"""
import time

import requests as http_requests

from app.services.assertion_engine import evaluate
from app.services.variable_resolver import VariableResolver

# 单次请求超时上限，防止个别用例把 worker 卡死（旧实现写死 10s，这里放开）
MAX_TIMEOUT = 120


def build_request(case: dict, environment: dict, resolver: VariableResolver) -> tuple:
    """构造请求三要素。返回 (method, full_url, headers, body, auth)。"""
    method = (case.get("method") or "GET").upper()
    raw_url = (case.get("url") or "").strip()
    base_url = (environment.get("base_url") or "").strip().rstrip("/")

    if raw_url.startswith(("http://", "https://")) or not base_url:
        full_url = raw_url
    else:
        full_url = f"{base_url}/{raw_url.lstrip('/')}"

    # 用户可能误输入带空格的 URL
    full_url = resolver.resolve(full_url.replace(" ", ""))

    headers = {}
    for key, value in (case.get("headers_json") or {}).items():
        headers[key] = resolver.resolve(str(value))

    auth_type = case.get("auth_type", "none")
    auth_value = case.get("auth_value") or ""
    auth_obj = None
    if auth_type == "bearer" and auth_value:
        headers["Authorization"] = f"Bearer {resolver.resolve(auth_value)}"
    elif auth_type == "apikey" and auth_value:
        headers["X-API-Key"] = resolver.resolve(auth_value)
    elif auth_type == "basic" and auth_value:
        parts = resolver.resolve(auth_value).split(":", 1)
        auth_obj = (parts[0], parts[1] if len(parts) > 1 else "")

    body_type = case.get("body_type", "none")
    body = resolver.resolve(case.get("body_content") or "")
    if body:
        if body_type == "json":
            headers.setdefault("Content-Type", "application/json; charset=utf-8")
        elif body_type == "form":
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif body_type == "xml":
            headers.setdefault("Content-Type", "application/xml")

    return method, full_url, headers, body, auth_obj


def execute_case(case: dict, environment: dict | None = None,
                 timeout: int = 30, verify_ssl: bool = True) -> dict:
    """执行一条接口用例并断言。

    case:    TestCase 的字段字典（含 assertions_json）
    environment: 环境字典（含 base_url / variables_json）

    返回可直接存进 execution.result_json 的结构。
    """
    environment = environment or {}
    resolver = VariableResolver(global_vars=environment.get("variables_json") or {})
    method, full_url, headers, body, auth_obj = build_request(case, environment, resolver)

    actual_timeout = max(1, min(int(timeout or 30), MAX_TIMEOUT))
    start = time.time()
    response = None
    error_msg = ""

    try:
        kwargs = {"headers": headers, "timeout": actual_timeout, "verify": verify_ssl}
        if auth_obj:
            kwargs["auth"] = auth_obj
        if body:
            kwargs["data"] = body.encode("utf-8")
        response = http_requests.request(method, full_url, **kwargs)
    except http_requests.exceptions.ConnectionError as e:
        error_msg = f"连接失败: {str(e)[:200]}"
    except http_requests.exceptions.Timeout:
        error_msg = f"请求超时 ({actual_timeout}秒)"
    except Exception as e:
        error_msg = f"请求异常: {type(e).__name__}: {str(e)[:150]}"

    elapsed_ms = (time.time() - start) * 1000

    # ---------- 响应快照 ----------
    if response is not None:
        resp_status = response.status_code
        resp_headers = dict(response.headers)
        try:
            resp_body = response.json()
        except Exception:
            resp_body = (response.text or "")[:5000]
    else:
        resp_status, resp_headers, resp_body = 0, {}, ""

    # ---------- 断言 ----------
    assertions = case.get("assertions_json") or []
    assertion_results = []

    if error_msg or response is None:
        status = "error"
    elif assertions:
        status = "pass"
        for rule in assertions:
            expected = str(rule.get("expected_value") or "").strip()
            if not expected:
                continue  # 空期望值静默跳过，保留旧行为
            result = evaluate(
                response, elapsed_ms,
                rule.get("assertion_type"), rule.get("operator"),
                expected, rule.get("target") or "",
            )
            assertion_results.append({
                "type": rule.get("assertion_type"),
                "target": rule.get("target") or "",
                "operator": rule.get("operator"),
                "expected": expected,
                "actual": result.get("actual", ""),
                "passed": result["passed"],
                "message": result["message"],
            })
            if not result["passed"]:
                status = "fail"
    else:
        # 无断言：HTTP >= 400 视为失败（保留旧行为）
        status = "fail" if resp_status >= 400 else "pass"

    return {
        "status": status,
        "duration_ms": int(elapsed_ms),
        "request": {"method": method, "url": full_url, "headers": headers, "body": body},
        "response": {"status": resp_status, "headers": resp_headers, "body": resp_body},
        "assertions": assertion_results,
        "error_msg": error_msg,
    }
