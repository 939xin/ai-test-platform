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
        # 一好一坏：验证提取成功，也验证「提取失败不算用例失败」
        "extract_json": [
            {"name": "echo_url", "source": "body", "expression": "$.url"},
            {"name": "resp_status", "source": "status", "expression": ""},
            {"name": "missing", "source": "body", "expression": "$.no.such.path"},
        ],
    }, timeout=10)
    check("新建用例", r.status_code == 201)
    case_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.get(f"{BASE}/cases/{case_id}", timeout=10)
    check("断言 JSON 完整保存", r.status_code == 200 and len(r.json()["assertions_json"]) == 2)

    # 列表接口必须带断言/提取的条数，否则列表页那两列永远显示 0（踩过的真实 bug）
    r = requests.get(f"{BASE}/projects/{pid}/cases", timeout=10)
    row = next((c for c in r.json() if c["id"] == case_id), {})
    check("列表接口带断言与提取条数（列表页展示用）",
          r.status_code == 200
          and len(row.get("assertions_json") or []) == 2
          and len(row.get("extract_json") or []) == 3)

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

        # ---------- 变量提取（3a）----------
        extracted = ex["result_json"].get("extracted") or {}
        check("提取响应体变量（JSONPath）",
              extracted.get("echo_url") == "https://httpbin.org/get", str(extracted.get("echo_url")))
        check("提取状态码变量", extracted.get("resp_status") == 200, str(extracted.get("resp_status")))
        check("提取失败不影响用例结果",
              extracted.get("missing") is None
              and ex["status"] == "pass"
              and len(ex["result_json"].get("extract_errors") or []) >= 1)

        execution_id = ex["id"]
    else:
        execution_id = None

    r = requests.get(f"{BASE}/executions", params={"project_id": pid}, timeout=10)
    check("执行历史可查", r.status_code == 200 and any(e["id"] == execution_id for e in r.json()))
    row = next((e for e in r.json() if e["id"] == execution_id), {})
    check("历史列表带用例名", row.get("case_name") == "GET /get 验收用例", row.get("case_name"))

    r = requests.get(f"{BASE}/executions", params={"project_id": pid, "status": "pass"}, timeout=10)
    check("按状态筛选执行记录",
          r.status_code == 200 and any(e["id"] == execution_id for e in r.json()))
    r = requests.get(f"{BASE}/executions", params={"project_id": pid, "status": "fail"}, timeout=10)
    check("状态筛选排除不匹配记录",
          r.status_code == 200 and all(e["status"] == "fail" for e in r.json()))

    r = requests.get(f"{BASE}/executions/{execution_id}", timeout=10)
    check("执行详情带用例名与结果",
          r.status_code == 200
          and r.json().get("case_name") == "GET /get 验收用例"
          and r.json()["result_json"]["response"]["status"] == 200)

    section("Day 3 · 测试报告")
    report_name = None
    r = requests.post(f"{BASE}/projects/{pid}/reports",
                      json={"execution_ids": [execution_id]}, timeout=30)
    check("生成 HTML 报告", r.status_code == 200 and r.json().get("filename", "").endswith(".html"))
    if r.status_code == 200:
        report_name = r.json()["filename"]
        stats = r.json()["stats"]
        check("报告统计与执行一致",
              stats["total"] == 1 and stats["passed"] == 1 and stats["failed"] == 0,
              f"{stats['passed']}/{stats['total']} 通过率 {stats['rate']}")

    if report_name:
        r = requests.get(f"{BASE}/reports/{report_name}", timeout=10)
        check("报告内容含用例名与断言结论",
              r.status_code == 200
              and "GET /get 验收用例" in r.text
              and "响应体" in r.text
              and "测试报告" in r.text)

        r = requests.get(f"{BASE}/reports", timeout=10)
        check("报告列表能查到新报告",
              r.status_code == 200 and any(f["filename"] == report_name for f in r.json()))

        r = requests.get(f"{BASE}/reports/..%2Fconfig.py", timeout=10)
        check("报告接口挡住路径穿越", r.status_code in (400, 404))

    # ==================== Day 3 · 场景串联（3b）====================
    section("Day 3 · 场景串联 ★")

    # 步骤 1：提取 httpbin 返回的 url；步骤 2：直接把这个变量当 URL 用
    # —— 如果 ${echo_url} 没被解析，请求会因 URL 非法而报错，所以「步骤 2 通过」即证明串联生效
    r = requests.post(f"{BASE}/projects/{pid}/cases", json={
        "name": "串联-步骤1 提取 url",
        "type": "api", "method": "GET", "url": "https://httpbin.org/get",
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""},
        ],
        "extract_json": [{"name": "echo_url", "source": "body", "expression": "$.url"}],
    }, timeout=10)
    step1_case = r.json()["id"]

    r = requests.post(f"{BASE}/projects/{pid}/cases", json={
        "name": "串联-步骤2 引用 ${echo_url}",
        "type": "api", "method": "GET",
        "url": "${echo_url}",  # 上一步提取的变量
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""},
        ],
    }, timeout=10)
    step2_case = r.json()["id"]

    # 一条必然失败的用例，用来验证 fail_strategy=stop
    r = requests.post(f"{BASE}/projects/{pid}/cases", json={
        "name": "串联-必然失败",
        "type": "api", "method": "GET", "url": "https://httpbin.org/get",
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "999", "target": ""},
        ],
    }, timeout=10)
    fail_case = r.json()["id"]

    r = requests.post(f"{BASE}/projects/{pid}/scenarios", json={
        "name": "登录链路串联验收",
        "description": "步骤1 提取变量，步骤2 引用变量",
        "steps": [
            {"case_id": step1_case, "fail_strategy": "stop"},
            {"case_id": step2_case, "fail_strategy": "stop"},
        ],
    }, timeout=10)
    check("新建场景", r.status_code == 201)
    scenario_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.get(f"{BASE}/scenarios/{scenario_id}", timeout=10)
    detail = r.json() if r.status_code == 200 else {}
    check("场景详情带用例名与顺序",
          r.status_code == 200
          and [s["case_name"] for s in detail.get("steps", [])] ==
          ["串联-步骤1 提取 url", "串联-步骤2 引用 ${echo_url}"]
          and [s["step_order"] for s in detail.get("steps", [])] == [1, 2])

    r = requests.get(f"{BASE}/projects/{pid}/scenarios", timeout=10)
    row = next((s for s in r.json() if s["id"] == scenario_id), {})
    check("场景列表带步骤数", r.status_code == 200 and row.get("step_count") == 2)

    r = requests.post(f"{BASE}/scenarios/{scenario_id}/run", json={"env_id": env_id}, timeout=90)
    check("执行场景", r.status_code == 200)
    if r.status_code == 200:
        run = r.json()
        steps = run["steps"]
        check("场景整体通过", run["status"] == "pass")
        check("步骤 1 提取到变量", steps[0]["extracted"].get("echo_url") == "https://httpbin.org/get",
              str(steps[0]["extracted"].get("echo_url")))
        check("串联生效：步骤 2 的 ${echo_url} 被解析成上一步的值",
              steps[1]["status"] == "pass"
              and steps[1]["result"]["request"]["url"] == "https://httpbin.org/get",
              steps[1]["result"]["request"]["url"])
        check("场景变量汇总含提取结果",
              run["variables"].get("echo_url") == "https://httpbin.org/get")

        r2 = requests.get(f"{BASE}/executions", params={"project_id": pid}, timeout=10)
        recorded = {e["case_id"] for e in r2.json()}
        check("场景各步骤落了执行记录",
              step1_case in recorded and step2_case in recorded)

    # fail_strategy=stop：前一步失败，后一步应记为 skip 且不执行
    r = requests.post(f"{BASE}/projects/{pid}/scenarios", json={
        "name": "失败中止验收",
        "steps": [
            {"case_id": fail_case, "fail_strategy": "stop"},
            {"case_id": step2_case, "fail_strategy": "stop"},
        ],
    }, timeout=10)
    stop_scenario = r.json()["id"] if r.status_code == 201 else None

    r = requests.post(f"{BASE}/scenarios/{stop_scenario}/run", json={"env_id": env_id}, timeout=90)
    if r.status_code == 200:
        run = r.json()
        check("失败即中止（fail_strategy=stop）",
              run["status"] == "fail"
              and run["steps"][0]["status"] == "fail"
              and run["steps"][1]["status"] == "skip",
              f"{run['steps'][0]['status']} → {run['steps'][1]['status']}")

    r = requests.delete(f"{BASE}/scenarios/{stop_scenario}", timeout=10)
    check("删除场景", r.status_code == 204)



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

    # 验收生成的报告文件一并清掉，避免 reports/platform 越积越多
    if report_name:
        report_file = Path(__file__).resolve().parents[2] / "reports" / "platform" / report_name
        if report_file.exists():
            report_file.unlink()

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
