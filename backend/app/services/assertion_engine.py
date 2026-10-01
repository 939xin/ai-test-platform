"""断言引擎 — 搬自旧项目 app/engine/api_runner.py 的 _evaluate_assertion()。

原方法不依赖 Qt、不依赖数据库，只吃 requests.Response 和断言参数，可整段复用。
"""
import re

try:
    from jsonpath_ng import parse as jsonpath_parse

    HAS_JSONPATH = True
except ImportError:
    HAS_JSONPATH = False


def evaluate(response, elapsed_ms: float, atype: str, op: str, expected: str, target: str = "") -> dict:
    """执行单条断言，返回 {passed, message, actual}。

    atype: status_code / response_time / response_body
    op:    eq / ne / contains / regex / lt / gt
    """
    if atype == "status_code":
        actual = response.status_code
        expected_int = int(expected)
        if op == "ne":
            passed = actual != expected_int
        else:
            passed = actual == expected_int
        msg = f"状态码: 期望={expected_int}, 实际={actual} → {'通过' if passed else '失败'}"
        return {"passed": passed, "message": msg, "actual": str(actual)}

    if atype == "response_time":
        actual = f"{elapsed_ms:.0f}"
        expected_float = float(expected)
        if op == "gt":
            passed = elapsed_ms > expected_float
        else:
            passed = elapsed_ms < expected_float
        symbol = ">" if op == "gt" else "<"
        msg = f"响应时间: 期望{symbol}{expected}ms, 实际={actual}ms → {'通过' if passed else '失败'}"
        return {"passed": passed, "message": msg, "actual": actual}

    if atype == "response_body":
        if not HAS_JSONPATH:
            return {"passed": True, "message": "jsonpath-ng 未安装，跳过", "actual": ""}

        actual_val = None
        actual = ""
        try:
            resp_json = response.json()
            matches = jsonpath_parse(target).find(resp_json)
            actual_val = matches[0].value if matches else None
            actual = str(actual_val) if actual_val is not None else "None"
        except Exception as e:
            return {"passed": False, "message": f"JSONPath 解析失败: {str(e)[:100]}", "actual": str(e)}

        if op == "ne":
            passed = str(actual_val) != expected
        elif op == "contains":
            passed = expected in str(actual_val)
        elif op == "regex":
            passed = bool(re.search(expected, str(actual_val)))
        else:  # eq / equals / 兜底
            passed = str(actual_val) == expected

        msg = f"响应体 [{target}]: 期望{op}={expected}, 实际={actual[:100]} → {'通过' if passed else '失败'}"
        return {"passed": passed, "message": msg, "actual": actual}

    return {"passed": True, "message": f"未知断言类型: {atype}", "actual": ""}
