"""一键验收 — 覆盖 Day 1 + Day 2 的全部后端能力。

用法（在 backend/ 目录下，需后端已启动）：
    venv/Scripts/python.exe scripts/verify_all.py

每个开发阶段结束后跑一次，确认没有回归。
"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

BASE = "http://127.0.0.1:8000/api"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(condition), detail))
    print(f"  {'✅' if condition else '❌'} {name}" + (f"   {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n【{title}】")


def main() -> int:
    print("=" * 54)
    print("  验收：Day 1 基础能力 + Day 2 业务闭环")
    print("=" * 54)

    # ==================== Day 1 ====================
    section("Day 1 · 健康检查与认证")
    try:
        r = requests.get(f"{BASE}/health", timeout=10)
        data = r.json()
        check("健康检查", r.status_code == 200 and data.get("status") == "ok",
              f"database={data.get('database')}")
    except Exception as e:
        print(f"  ✗ 后端未启动：{e}")
        return 1

    r = requests.post(f"{BASE}/auth/login",
                      json={"username": "admin", "password": "admin123"}, timeout=10)
    check("登录成功返回 token", r.status_code == 200 and "access_token" in r.json())

    r = requests.post(f"{BASE}/auth/login",
                      json={"username": "admin", "password": "wrong"}, timeout=10)
    check("错误密码返回 401", r.status_code == 401)

    section("Day 1 · 复用引擎（离线，不依赖后端）")
    from app.services.api_executor import execute_case
    from app.services.variable_resolver import VariableResolver

    resolver = VariableResolver(global_vars={"base_url": "https://httpbin.org", "token": "global"})
    resolver.set_extra_var("token", "runtime")
    check("变量解析：运行时优先",
          resolver.resolve("${base_url}/get?t=${token}") == "https://httpbin.org/get?t=runtime")
    check("变量解析：未命中保留原样", resolver.resolve("${unknown}") == "${unknown}")

    engine_result = execute_case(
        {
            "method": "GET",
            "url": "https://httpbin.org/get",
            "headers_json": {"Accept": "application/json"},
            "body_type": "none",
            "body_content": "",
            "auth_type": "none",
            "auth_value": "",
            "assertions_json": [
                {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""},
            ],
        },
        {"name": "httpbin", "base_url": "https://httpbin.org", "variables_json": {}},
    )
    check("引擎真实执行 + 断言", engine_result["status"] == "pass",
          f"{engine_result['duration_ms']}ms")

    # ==================== Day 2 ====================
    section("Day 2 · 项目管理")
    r = requests.post(f"{BASE}/projects",
                      json={"name": "验收项目", "description": "verify_all 创建"}, timeout=10)
    check("新建项目", r.status_code == 201)
    pid = r.json().get("id") if r.status_code == 201 else None

    r = requests.get(f"{BASE}/projects/{pid}", timeout=10)
    check("项目详情（中文往返）", r.status_code == 200 and r.json().get("name") == "验收项目")

    r = requests.put(f"{BASE}/projects/{pid}", json={"description": "已更新"}, timeout=10)
    check("更新项目", r.status_code == 200 and r.json().get("description") == "已更新")

    r = requests.post(f"{BASE}/projects", json={"name": ""}, timeout=10)
    check("空名称返回 422", r.status_code == 422)

    section("Day 2 · 环境管理")
    r = requests.post(f"{BASE}/projects/{pid}/environments",
                      json={"name": "dev", "base_url": "https://httpbin.org",
                            "variables_json": {"token": "abc"}}, timeout=10)
    check("新建环境", r.status_code == 201)
    env_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.get(f"{BASE}/projects/{pid}/environments", timeout=10)
    check("环境列表", r.status_code == 200 and len(r.json()) == 1)

    r = requests.get(f"{BASE}/environments/{env_id}", timeout=10)
    check("环境变量保存正确", r.status_code == 200 and r.json()["variables_json"].get("token") == "abc")

    section("Day 2 · 用例管理")
    r = requests.post(f"{BASE}/projects/{pid}/cases", json={
        # 刻意不传 project_id，模拟前端的真实调用
        "name": "GET /get 验收用例",
        "type": "api",
        "priority": "P0",
        "tags": "smoke",
        "method": "GET",
        "url": "https://httpbin.org/get",
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""},
            {"assertion_type": "response_body", "operator": "eq",
             "expected_value": "https://httpbin.org/get", "target": "$.url"},
        ],
    }, timeout=10)
    check("新建用例", r.status_code == 201)
    case_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.get(f"{BASE}/cases/{case_id}", timeout=10)
    check("断言 JSON 完整保存", r.status_code == 200 and len(r.json()["assertions_json"]) == 2)

    r = requests.get(f"{BASE}/projects/{pid}/cases", params={"type": "api"}, timeout=10)
    check("按类型筛选", r.status_code == 200 and len(r.json()) == 1)

    r = requests.get(f"{BASE}/projects/{pid}/cases", params={"keyword": "验收"}, timeout=10)
    check("按中文关键字筛选", r.status_code == 200 and len(r.json()) == 1)

    section("Day 2 · 执行闭环 ★")
    r = requests.post(f"{BASE}/cases/{case_id}/run", json={"env_id": env_id, "timeout": 30}, timeout=60)
    check("执行用例", r.status_code == 200)
    if r.status_code == 200:
        ex = r.json()
        check("执行结果 pass", ex["status"] == "pass", f"{ex['duration_ms']}ms")
        assertions = ex["result_json"]["assertions"]
        check("断言全部通过", len(assertions) == 2 and all(a["passed"] for a in assertions))
        check("请求/响应已记录",
              ex["result_json"]["response"]["status"] == 200
              and ex["result_json"]["request"]["url"] == "https://httpbin.org/get")
        execution_id = ex["id"]
    else:
        execution_id = None

    r = requests.get(f"{BASE}/executions", params={"project_id": pid}, timeout=10)
    check("执行历史可查", r.status_code == 200 and any(e["id"] == execution_id for e in r.json()))

    # ==================== 清理 ====================
    section("清理验收数据")
    if case_id:
        requests.delete(f"{BASE}/cases/{case_id}", timeout=10)
    if env_id:
        requests.delete(f"{BASE}/environments/{env_id}", timeout=10)
    if pid:
        requests.delete(f"{BASE}/projects/{pid}", timeout=10)
    r = requests.get(f"{BASE}/projects/{pid}", timeout=10)
    check("级联删除生效（项目 404）", r.status_code == 404)

    # ==================== 汇总 ====================
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print("\n" + "=" * 54)
    if passed == total:
        print(f"  ✅ 全部通过：{passed}/{total}")
    else:
        print(f"  ❌ 存在失败：{passed}/{total}")
        for name, ok, _ in RESULTS:
            if not ok:
                print(f"     - {name}")
    print("=" * 54)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
