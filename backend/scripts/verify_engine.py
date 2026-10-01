"""复用引擎自检 — 验证从旧 PySide6 项目搬来的执行引擎能独立跑通。

用法（在 backend/ 目录下）：
    venv/Scripts/python.exe scripts/verify_engine.py

依赖外网（httpbin.org）。不通时脚本会明确报错，不会静默通过。
"""
import io
import sys
from pathlib import Path

# Windows 控制台默认 GBK，重设为 UTF-8，否则中文和 emoji 会抛 UnicodeEncodeError
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 让脚本能 import app.*（backend/ 加入 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.api_executor import execute_case  # noqa: E402
from app.services.variable_resolver import VariableResolver  # noqa: E402


def check_variable_resolver() -> bool:
    """验证变量解析：运行时变量优先于全局，未命中保留原样。"""
    resolver = VariableResolver(global_vars={"base_url": "https://httpbin.org", "token": "global-token"})
    resolver.set_extra_var("token", "runtime-token")

    got = resolver.resolve("${base_url}/get?t=${token}")
    expect = "https://httpbin.org/get?t=runtime-token"

    kept = resolver.resolve("${unknown_var}")
    ok = got == expect and kept == "${unknown_var}"
    print(f"{'✅' if ok else '❌'} 变量解析: {got!r}")
    if not ok:
        print(f"   期望 {expect!r}，未命中占位符应保留 {kept!r}")
    return ok


def check_api_execution() -> bool:
    """验证接口执行 + 断言。"""
    case = {
        "name": "httpbin 连通性验证",
        "method": "GET",
        "url": "https://httpbin.org/get",
        "headers_json": {"Accept": "application/json"},
        "body_type": "none",
        "body_content": "",
        "auth_type": "none",
        "auth_value": "",
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""},
            {"assertion_type": "response_body", "operator": "eq",
             "expected_value": "https://httpbin.org/get", "target": "$.url"},
            {"assertion_type": "response_time", "operator": "lt", "expected_value": "10000", "target": ""},
        ],
    }
    environment = {"name": "httpbin", "base_url": "https://httpbin.org", "variables_json": {}}

    result = execute_case(case, environment)

    print(f"   请求: {result['request']['method']} {result['request']['url']}")
    print(f"   响应码: {result['response']['status']}  耗时: {result['duration_ms']}ms")
    for a in result["assertions"]:
        print(f"   {'✅' if a['passed'] else '❌'} {a['message']}")
    if result["error_msg"]:
        print(f"   ⚠️ {result['error_msg']}")

    ok = result["status"] == "pass"
    print(f"{'✅' if ok else '❌'} 接口执行: status={result['status']}")
    return ok


def main() -> int:
    print("===== 复用引擎自检 =====")
    results = [check_variable_resolver(), check_api_execution()]
    passed = sum(results)
    print(f"\n===== {passed}/{len(results)} 项通过 =====")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
