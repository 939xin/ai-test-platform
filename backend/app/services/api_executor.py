"""接口执行器 — 搬自旧项目 app/engine/api_runner.py 的请求构造与发送部分。

剥掉 QThread 和 DBManager，改成无状态的纯函数，供 FastAPI 直接调用。
"""
import time

import requests as http_requests

from app.services.assertion_engine import evaluate
from app.services.variable_resolver import VariableResolver

try:
    from jsonpath_ng import parse as jsonpath_parse
except ImportError:  # 与 assertion_engine 保持一致：缺库时降级而不是整个应用起不来
    jsonpath_parse = None

# 单次请求超时上限，防止个别用例把 worker 卡死（旧实现写死 10s，这里放开）
MAX_TIMEOUT = 120


def build_request(case: dict, environment: dict, resolver: VariableResolver) -> tuple:
    """构造请求三要素。返回 (method, full_url, headers, body, auth)。"""
    method = (case.get("method") or "GET").upper()

    # 必须先解析变量、再判断要不要拼 base_url。
    # 反过来的话，URL 完全由 ${变量} 组成时（场景串联的典型用法）字面上不以 http 开头，
    # 会被误判成相对路径，拼出 https://base/https://real-url 这种畸形地址。
    resolved_url = resolver.resolve((case.get("url") or "").strip()).replace(" ", "")
    resolved_base = resolver.resolve((environment.get("base_url") or "").strip().rstrip("/"))

    if resolved_url.startswith(("http://", "https://")) or not resolved_base:
        full_url = resolved_url
    else:
        full_url = f"{resolved_base}/{resolved_url.lstrip('/')}"

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


def _extract_variables(response, rules: list) -> tuple[dict, list[str]]:
    """按用例的 extract_json 规则从响应里取运行时变量。

    rules 元素形如 {"name": "token", "source": "body", "expression": "$.token"}
    source 取 body（JSONPath）/ header（响应头名）/ status（状态码，无需 expression）。

    提取失败**不算用例失败**（与「空期望值的断言静默跳过」保持同一风格）：
    值记为 None，原因写进返回的 errors 里供调用方记录。
    返回 (变量字典, 错误说明列表)。
    """
    extracted: dict = {}
    errors: list[str] = []

    for rule in rules or []:
        name = str(rule.get("name") or "").strip()
        if not name:
            continue
        source = str(rule.get("source") or "body").strip()
        expression = str(rule.get("expression") or "").strip()

        try:
            if source == "status":
                extracted[name] = response.status_code if response is not None else None
            elif source == "header":
                extracted[name] = response.headers.get(expression) if response is not None else None
            elif jsonpath_parse is None:
                extracted[name] = None
                errors.append(f"{name}: jsonpath-ng 未安装，无法从响应体提取")
                continue
            elif response is None:
                extracted[name] = None
            else:
                matches = jsonpath_parse(expression).find(response.json())
                extracted[name] = matches[0].value if matches else None
        except Exception as e:
            extracted[name] = None
            errors.append(f"{name}: {type(e).__name__}: {str(e)[:100]}")
            continue

        if extracted[name] is None:
            errors.append(f"{name}: 未匹配到值（{source} {expression or '-'}）")

    return extracted, errors


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
            # 期望值也过一遍变量解析：数据驱动时最常见的写法就是「断言返回值等于本行的某个值」
            # （旧实现不解析，这里补上；只会让原本必然失败的断言变正确，不影响已有行为）
            expected = resolver.resolve(str(rule.get("expected_value") or "")).strip()
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

    # ---------- 变量提取 ----------
    # 提取失败不影响用例状态，只记录原因（场景串联时靠 extracted 传参给下一步）
    extracted, extract_errors = _extract_variables(response, case.get("extract_json") or [])

    return {
        "status": status,
        "duration_ms": int(elapsed_ms),
        "request": {"method": method, "url": full_url, "headers": headers, "body": body},
        "response": {"status": resp_status, "headers": resp_headers, "body": resp_body},
        "assertions": assertion_results,
        "extracted": extracted,
        "extract_errors": extract_errors,
        "error_msg": error_msg,
    }
