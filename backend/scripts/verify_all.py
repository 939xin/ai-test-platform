"""一键验收 — 覆盖 Day 1 ~ Day 6 的全部后端能力。

用法（在 backend/ 目录下，需后端已启动）：
    venv/Scripts/python.exe scripts/verify_all.py

每个开发阶段结束后跑一次，确认没有回归。
Day 1-3 段需要外网（httpbin.org）；Day 4 起用后端自带的离线演示页，不依赖外网。
"""
import io
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

BASE = "http://127.0.0.1:8000/api"
# 全站接口已统一校验 JWT，除登录本身外都得带 token。
# 用 Session 挂一次 Authorization 头，比在 100 多处逐个传 headers 可靠得多
# （漏一处就是 401，而且报错信息还会掩盖成「业务失败」）。
# 登录那两次刻意留用裸 requests，别把上一次的 token 带进登录请求。
SESSION = requests.Session()
# Web 验收的靶页：后端静态托管的离线演示页（httpbin 没有 UI，测不了 Web）
DEMO_URL = f"{BASE}/demo/index.html"
SECOND_URL = f"{BASE}/demo/second.html"
REPORT_ROOT = Path(__file__).resolve().parents[2] / "reports" / "platform"
RESULTS: list[tuple[str, bool, str]] = []


def new_ops_steps(upload_path: str) -> list[dict]:
    """覆盖新增 16 种操作的一条 Web 用例的步骤表。

    定义在模块级是为了能单独复跑排查（见 scripts/debug_new_ops.py）——
    每次跑完整验收都要等前面 100 多项，出问题定位太慢。
    """
    return [
        {"step_order": 1, "action_type": "open_url", "input_value": DEMO_URL},
        # 下拉框选择（按可见文本）
        {"step_order": 2, "action_type": "select_option", "input_value": "label",
         "input_value2": "上海", "locator_type": "id", "locator_value": "city-select"},
        {"step_order": 3, "action_type": "force_wait", "wait_seconds": 0.4},
        {"step_order": 4, "action_type": "assert_text_contains", "input_value": "已选：sh",
         "locator_type": "id", "locator_value": "city-echo"},
        # 键盘按键：先输入，再回车提交
        {"step_order": 5, "action_type": "input", "input_value": "关键字",
         "locator_type": "id", "locator_value": "search-key"},
        {"step_order": 6, "action_type": "press_key", "input_value": "ENTER"},
        {"step_order": 7, "action_type": "force_wait", "wait_seconds": 0.4},
        {"step_order": 8, "action_type": "assert_text_contains", "input_value": "已搜索：关键字",
         "locator_type": "id", "locator_value": "search-echo"},
        # 上传文件
        {"step_order": 9, "action_type": "upload_file", "input_value": upload_path,
         "locator_type": "id", "locator_value": "upload"},
        {"step_order": 10, "action_type": "assert_text_contains", "input_value": "verify_upload.txt",
         "locator_type": "id", "locator_value": "upload-echo"},
        # 悬停
        {"step_order": 11, "action_type": "hover", "locator_type": "id", "locator_value": "hover-box"},
        {"step_order": 12, "action_type": "assert_visible", "input_value": "true",
         "locator_type": "id", "locator_value": "hover-menu"},
        # 双击 / 右键
        {"step_order": 13, "action_type": "double_click", "locator_type": "id",
         "locator_value": "dbl-box"},
        {"step_order": 14, "action_type": "force_wait", "wait_seconds": 0.4},
        {"step_order": 15, "action_type": "assert_text_contains", "input_value": "已双击",
         "locator_type": "id", "locator_value": "dbl-box"},
        {"step_order": 16, "action_type": "context_click", "locator_type": "id",
         "locator_value": "ctx-box"},
        {"step_order": 17, "action_type": "force_wait", "wait_seconds": 0.4},
        {"step_order": 18, "action_type": "assert_text_contains", "input_value": "已右键",
         "locator_type": "id", "locator_value": "ctx-box"},
        # 拖拽
        {"step_order": 19, "action_type": "drag_and_drop",
         "locator_type": "id", "locator_value": "drag-src",
         "target_locator_type": "id", "target_locator_value": "drop-target"},
        {"step_order": 20, "action_type": "force_wait", "wait_seconds": 0.4},
        {"step_order": 21, "action_type": "assert_text_contains", "input_value": "已放置",
         "locator_type": "id", "locator_value": "drop-target"},
        # 断言元素数量 / 属性
        {"step_order": 22, "action_type": "assert_element_count", "input_value": "3",
         "locator_type": "css_selector", "locator_value": "li.item"},
        {"step_order": 23, "action_type": "assert_attribute", "input_value": "placeholder",
         "input_value2": "占位文本",
         "locator_type": "id", "locator_value": "attr-field"},
        {"step_order": 24, "action_type": "assert_attribute", "input_value": "disabled",
         "locator_type": "id", "locator_value": "attr-field"},
        # 弹窗：alert 确认 + prompt 取消
        {"step_order": 25, "action_type": "click", "locator_type": "id", "locator_value": "alert-btn"},
        {"step_order": 26, "action_type": "alert_accept"},
        {"step_order": 27, "action_type": "force_wait", "wait_seconds": 0.4},
        {"step_order": 28, "action_type": "assert_text_contains", "input_value": "alert 已关闭",
         "locator_type": "id", "locator_value": "dialog-echo"},
        {"step_order": 29, "action_type": "click", "locator_type": "id", "locator_value": "prompt-btn"},
        {"step_order": 30, "action_type": "alert_dismiss"},
        {"step_order": 31, "action_type": "force_wait", "wait_seconds": 0.4},
        {"step_order": 32, "action_type": "assert_text_contains", "input_value": "prompt 已取消",
         "locator_type": "id", "locator_value": "dialog-echo"},
        # 等待元素消失
        {"step_order": 33, "action_type": "click", "locator_type": "id", "locator_value": "remove-btn"},
        {"step_order": 34, "action_type": "wait_invisible", "wait_seconds": 5,
         "locator_type": "id", "locator_value": "loading-box"},
        # 滚动到页面底部
        {"step_order": 35, "action_type": "scroll_to_bottom"},
        {"step_order": 36, "action_type": "force_wait", "wait_seconds": 0.5},
        {"step_order": 37, "action_type": "assert_text_contains", "input_value": "已到达底部",
         "locator_type": "id", "locator_value": "scroll-echo"},
        # 刷新：前后各取一次页面加载标记，两次不同才说明真的重载了
        {"step_order": 38, "action_type": "extract_variable", "input_value": "mark_before",
         "locator_type": "id", "locator_value": "reload-mark"},
        {"step_order": 39, "action_type": "refresh"},
        {"step_order": 40, "action_type": "extract_variable", "input_value": "mark_after",
         "locator_type": "id", "locator_value": "reload-mark"},
        # 后退
        {"step_order": 41, "action_type": "open_url", "input_value": SECOND_URL},
        {"step_order": 42, "action_type": "back"},
        {"step_order": 43, "action_type": "assert_url_contains", "input_value": "/demo/index.html"},
    ]


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(condition), detail))
    print(f"  {'✅' if condition else '❌'} {name}" + (f"   {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n【{title}】")


def main() -> int:
    print("=" * 54)
    print("  验收：Day 1-3 接口闭环 + Day 4 Web UI 执行 + Day 5 测试计划 + 缺陷管理")
    print("=" * 54)

    # ==================== Day 1 ====================
    section("Day 1 · 健康检查与认证")
    try:
        r = SESSION.get(f"{BASE}/health", timeout=10)
        data = r.json()
        check("健康检查", r.status_code == 200 and data.get("status") == "ok",
              f"database={data.get('database')}")
    except Exception as e:
        print(f"  ✗ 后端未启动：{e}")
        return 1

    r = requests.post(f"{BASE}/auth/login",
                      json={"username": "admin", "password": "admin123"}, timeout=10)
    check("登录成功返回 token", r.status_code == 200 and "access_token" in r.json())
    token = r.json().get("access_token", "")

    r = requests.post(f"{BASE}/auth/login",
                      json={"username": "admin", "password": "wrong"}, timeout=10)
    check("错误密码返回 401", r.status_code == 401)

    section("Day 1 · 全站 JWT 校验边界")
    # 其余 100 多项都靠 SESSION 的 token 通过，所以这里必须证明「不带 token 真会被拦」，
    # 否则万一守卫没挂上，整份验收会因为误放行而全绿。
    SESSION.headers["Authorization"] = f"Bearer {token}"
    no_auth = requests.get(f"{BASE}/projects", timeout=10)
    check("无 token 访问业务接口返回 401", no_auth.status_code == 401,
          f"status={no_auth.status_code}")
    forged = requests.get(f"{BASE}/projects", timeout=10,
                          headers={"Authorization": "Bearer not.a.real.token"})
    check("伪造 token 返回 401", forged.status_code == 401, f"status={forged.status_code}")
    # 两处豁免：健康检查（start.bat 与登录前探活用）和登录本身
    check("健康检查不需要 token", requests.get(f"{BASE}/health", timeout=10).status_code == 200)
    check("带 token 访问业务接口正常",
          SESSION.get(f"{BASE}/projects", timeout=10).status_code == 200)

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
    r = SESSION.post(f"{BASE}/projects",
                      json={"name": "验收项目", "description": "verify_all 创建"}, timeout=10)
    check("新建项目", r.status_code == 201)
    pid = r.json().get("id") if r.status_code == 201 else None

    r = SESSION.get(f"{BASE}/projects/{pid}", timeout=10)
    check("项目详情（中文往返）", r.status_code == 200 and r.json().get("name") == "验收项目")

    r = SESSION.put(f"{BASE}/projects/{pid}", json={"description": "已更新"}, timeout=10)
    check("更新项目", r.status_code == 200 and r.json().get("description") == "已更新")

    r = SESSION.post(f"{BASE}/projects", json={"name": ""}, timeout=10)
    check("空名称返回 422", r.status_code == 422)

    section("Day 2 · 环境管理")
    r = SESSION.post(f"{BASE}/projects/{pid}/environments",
                      json={"name": "dev", "base_url": "https://httpbin.org",
                            "variables_json": {"token": "abc"}}, timeout=10)
    check("新建环境", r.status_code == 201)
    env_id = r.json().get("id") if r.status_code == 201 else None

    r = SESSION.get(f"{BASE}/projects/{pid}/environments", timeout=10)
    check("环境列表", r.status_code == 200 and len(r.json()) == 1)

    r = SESSION.get(f"{BASE}/environments/{env_id}", timeout=10)
    check("环境变量保存正确", r.status_code == 200 and r.json()["variables_json"].get("token") == "abc")

    section("Day 2 · 用例管理")
    r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
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

    r = SESSION.get(f"{BASE}/cases/{case_id}", timeout=10)
    check("断言 JSON 完整保存", r.status_code == 200 and len(r.json()["assertions_json"]) == 2)

    # 列表接口必须带断言/提取的条数，否则列表页那两列永远显示 0（踩过的真实 bug）
    r = SESSION.get(f"{BASE}/projects/{pid}/cases", timeout=10)
    row = next((c for c in r.json()["items"] if c["id"] == case_id), {})
    check("列表接口带断言与提取条数（列表页展示用）",
          r.status_code == 200
          and len(row.get("assertions_json") or []) == 2
          and len(row.get("extract_json") or []) == 3)
    check("列表接口带 data_file（执行弹窗判断数据驱动用）",
          "data_file" in row, str(sorted(row.keys()))[:120])

    r = SESSION.get(f"{BASE}/projects/{pid}/cases", params={"type": "api"}, timeout=10)
    check("按类型筛选", r.status_code == 200 and len(r.json()["items"]) == 1)

    r = SESSION.get(f"{BASE}/projects/{pid}/cases", params={"keyword": "验收"}, timeout=10)
    check("按中文关键字筛选", r.status_code == 200 and len(r.json()["items"]) == 1)

    section("Day 2 · 执行闭环 ★")
    r = SESSION.post(f"{BASE}/cases/{case_id}/run", json={"env_id": env_id, "timeout": 30}, timeout=60)
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

    r = SESSION.get(f"{BASE}/executions", params={"project_id": pid}, timeout=10)
    check("执行历史可查",
          r.status_code == 200 and any(e["id"] == execution_id for e in r.json()["items"]))
    row = next((e for e in r.json()["items"] if e["id"] == execution_id), {})
    check("历史列表带用例名", row.get("case_name") == "GET /get 验收用例", row.get("case_name"))

    r = SESSION.get(f"{BASE}/executions", params={"project_id": pid, "status": "pass"}, timeout=10)
    check("按状态筛选执行记录",
          r.status_code == 200 and any(e["id"] == execution_id for e in r.json()["items"]))
    r = SESSION.get(f"{BASE}/executions", params={"project_id": pid, "status": "fail"}, timeout=10)
    check("状态筛选排除不匹配记录",
          r.status_code == 200 and all(e["status"] == "fail" for e in r.json()["items"]))

    r = SESSION.get(f"{BASE}/executions/{execution_id}", timeout=10)
    check("执行详情带用例名与结果",
          r.status_code == 200
          and r.json().get("case_name") == "GET /get 验收用例"
          and r.json()["result_json"]["response"]["status"] == 200)

    section("Day 3 · 测试报告")
    report_name = None
    burst_report_names = []
    r = SESSION.post(f"{BASE}/projects/{pid}/reports",
                      json={"execution_ids": [execution_id]}, timeout=30)
    check("生成 HTML 报告", r.status_code == 200 and r.json().get("filename", "").endswith(".html"))
    if r.status_code == 200:
        report_name = r.json()["filename"]
        stats = r.json()["stats"]
        check("报告统计与执行一致",
              stats["total"] == 1 and stats["passed"] == 1 and stats["failed"] == 0,
              f"{stats['passed']}/{stats['total']} 通过率 {stats['rate']}")

    if report_name:
        r = SESSION.get(f"{BASE}/reports/{report_name}", timeout=10)
        check("报告内容含用例名与断言结论",
              r.status_code == 200
              and "GET /get 验收用例" in r.text
              and "响应体" in r.text
              and "测试报告" in r.text)

        r = SESSION.get(f"{BASE}/reports", params={"limit": 200}, timeout=10)
        check("报告列表能查到新报告",
              r.status_code == 200
              and any(f["filename"] == report_name for f in r.json()["items"]))

        r = SESSION.get(f"{BASE}/reports/..%2Fconfig.py", timeout=10)
        check("报告接口挡住路径穿越", r.status_code in (400, 404))

        # 报告文件名只精确到秒。连发三次如果撞名，磁盘上只会剩最后一份 ——
        # 用户连点两次「生成报告」，前一份就被静默吃掉了，页面上完全看不出来。
        burst = [
            SESSION.post(f"{BASE}/projects/{pid}/reports",
                         json={"execution_ids": [execution_id]}, timeout=30).json()["filename"]
            for _ in range(3)
        ]
        burst_report_names = burst  # 收尾时跟着 report_name 一起删
        check("同一秒连生多份报告自动错开文件名",
              len(set(burst)) == len(burst), " / ".join(burst))

        r = SESSION.get(f"{BASE}/reports", params={"limit": 200}, timeout=10)
        listed = {f["filename"] for f in r.json()["items"]}
        check("连生的报告都真的落盘了", all(name in listed for name in burst))

    # ==================== Day 3 · 场景串联（3b）====================
    section("Day 3 · 场景串联 ★")

    # 步骤 1：提取 httpbin 返回的 url；步骤 2：直接把这个变量当 URL 用
    # —— 如果 ${echo_url} 没被解析，请求会因 URL 非法而报错，所以「步骤 2 通过」即证明串联生效
    r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
        "name": "串联-步骤1 提取 url",
        "type": "api", "method": "GET", "url": "https://httpbin.org/get",
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""},
        ],
        "extract_json": [{"name": "echo_url", "source": "body", "expression": "$.url"}],
    }, timeout=10)
    step1_case = r.json()["id"]

    r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
        "name": "串联-步骤2 引用 ${echo_url}",
        "type": "api", "method": "GET",
        "url": "${echo_url}",  # 上一步提取的变量
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""},
        ],
    }, timeout=10)
    step2_case = r.json()["id"]

    # 一条必然失败的用例，用来验证 fail_strategy=stop
    r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
        "name": "串联-必然失败",
        "type": "api", "method": "GET", "url": "https://httpbin.org/get",
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "999", "target": ""},
        ],
    }, timeout=10)
    fail_case = r.json()["id"]

    r = SESSION.post(f"{BASE}/projects/{pid}/scenarios", json={
        "name": "登录链路串联验收",
        "description": "步骤1 提取变量，步骤2 引用变量",
        "steps": [
            {"case_id": step1_case, "fail_strategy": "stop"},
            {"case_id": step2_case, "fail_strategy": "stop"},
        ],
    }, timeout=10)
    check("新建场景", r.status_code == 201)
    scenario_id = r.json().get("id") if r.status_code == 201 else None

    r = SESSION.get(f"{BASE}/scenarios/{scenario_id}", timeout=10)
    detail = r.json() if r.status_code == 200 else {}
    check("场景详情带用例名与顺序",
          r.status_code == 200
          and [s["case_name"] for s in detail.get("steps", [])] ==
          ["串联-步骤1 提取 url", "串联-步骤2 引用 ${echo_url}"]
          and [s["step_order"] for s in detail.get("steps", [])] == [1, 2])

    r = SESSION.get(f"{BASE}/projects/{pid}/scenarios", timeout=10)
    row = next((s for s in r.json()["items"] if s["id"] == scenario_id), {})
    check("场景列表带步骤数", r.status_code == 200 and row.get("step_count") == 2)

    r = SESSION.post(f"{BASE}/scenarios/{scenario_id}/run", json={"env_id": env_id}, timeout=90)
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

        r2 = SESSION.get(f"{BASE}/executions", params={"project_id": pid}, timeout=10)
        recorded = {e["case_id"] for e in r2.json()["items"]}
        check("场景各步骤落了执行记录",
              step1_case in recorded and step2_case in recorded)

    # fail_strategy=stop：前一步失败，后一步应记为 skip 且不执行
    r = SESSION.post(f"{BASE}/projects/{pid}/scenarios", json={
        "name": "失败中止验收",
        "steps": [
            {"case_id": fail_case, "fail_strategy": "stop"},
            {"case_id": step2_case, "fail_strategy": "stop"},
        ],
    }, timeout=10)
    stop_scenario = r.json()["id"] if r.status_code == 201 else None

    r = SESSION.post(f"{BASE}/scenarios/{stop_scenario}/run", json={"env_id": env_id}, timeout=90)
    if r.status_code == 200:
        run = r.json()
        check("失败即中止（fail_strategy=stop）",
              run["status"] == "fail"
              and run["steps"][0]["status"] == "fail"
              and run["steps"][1]["status"] == "skip",
              f"{run['steps'][0]['status']} → {run['steps'][1]['status']}")

    r = SESSION.delete(f"{BASE}/scenarios/{stop_scenario}", timeout=10)
    check("删除场景", r.status_code == 204)

    # ==================== Day 3 · 数据驱动（任务 4）====================
    section("Day 3 · 数据驱动 ★")

    csv_text = "keyword,note\n苹果,第一个\n香蕉,第二个\n橙子,第三个\n"
    r = SESSION.post(f"{BASE}/projects/{pid}/datasets",
                      files={"file": ("demo_params.csv", csv_text.encode("utf-8"), "text/csv")},
                      timeout=10)
    check("上传 CSV 数据文件", r.status_code == 201, r.text[:100] if r.status_code != 201 else "")
    ds = r.json() if r.status_code == 201 else {}
    check("识别出数据行数与列名",
          ds.get("rows") == 3 and ds.get("columns") == ["keyword", "note"],
          f"{ds.get('rows')} 行 / {ds.get('columns')}")

    r = SESSION.get(f"{BASE}/projects/{pid}/datasets", timeout=10)
    check("数据文件列表可查",
          r.status_code == 200 and any(d["filename"] == "demo_params.csv" for d in r.json()))

    r = SESSION.get(f"{BASE}/projects/{pid}/datasets/demo_params.csv/preview", timeout=10)
    check("预览数据文件",
          r.status_code == 200
          and len(r.json()["sample"]) == 3
          and r.json()["sample"][0]["keyword"] == "苹果")

    # 只有表头 → 应当报错，而不是静默跑 0 次
    r = SESSION.post(f"{BASE}/projects/{pid}/datasets",
                      files={"file": ("empty.csv", "keyword,note\n".encode("utf-8"), "text/csv")},
                      timeout=10)
    check("只有表头的文件被拒（400）", r.status_code == 400, str(r.status_code))

    # 文件名越界 → 应当被挡
    r = SESSION.post(f"{BASE}/projects/{pid}/datasets",
                      files={"file": ("../evil.csv", "a\n1\n".encode("utf-8"), "text/csv")},
                      timeout=10)
    check("数据文件名挡路径穿越", r.status_code == 400, str(r.status_code))

    # 绑定数据文件并按行执行：URL 里用 ${keyword}，断言也用 ${keyword}（两者都要被解析）
    r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
        "name": "数据驱动-逐行请求",
        "type": "api",
        "method": "GET",
        "url": "https://httpbin.org/get?keyword=${keyword}",
        "assertions_json": [
            {"assertion_type": "response_body", "operator": "eq",
             "expected_value": "${keyword}", "target": "$.args.keyword"},
        ],
        "data_file": "demo_params.csv",
    }, timeout=10)
    check("用例绑定数据文件", r.status_code == 201)
    dd_case = r.json().get("id") if r.status_code == 201 else None

    r = SESSION.post(f"{BASE}/cases/{dd_case}/run-data-driven", json={"env_id": env_id}, timeout=120)
    check("按数据行执行", r.status_code == 200, r.text[:120] if r.status_code != 200 else "")
    if r.status_code == 200:
        run = r.json()
        check("执行次数等于数据行数",
              run["total"] == 3 and len(run["rows"]) == 3, f"total={run['total']}")
        check("每行都通过（行变量在 URL 与断言里都被解析）",
              run["passed"] == 3 and run["failed"] == 0,
              f"{run['passed']}/{run['total']}")
        check("row_index 依次编号",
              [row["result_json"]["row_index"] for row in run["rows"]] == [1, 2, 3])
        urls = [row["result_json"]["request"]["url"] for row in run["rows"]]
        check("每行注入了各自的变量值",
              urls == ["https://httpbin.org/get?keyword=苹果",
                       "https://httpbin.org/get?keyword=香蕉",
                       "https://httpbin.org/get?keyword=橙子"],
              " | ".join(urls))

    # 没绑数据文件的用例走该接口应当明确报错
    r = SESSION.post(f"{BASE}/cases/{case_id}/run-data-driven", json={"env_id": env_id}, timeout=30)
    check("未绑定数据文件时返回 400", r.status_code == 400, str(r.status_code))

    r = SESSION.delete(f"{BASE}/projects/{pid}/datasets/demo_params.csv", timeout=10)
    check("删除数据文件", r.status_code == 204)

    # ==================== Day 4 · Web UI 执行（Selenium）====================
    section("Day 4 · Web UI 执行 ★")

    # 本段跑完要清理的东西：截图按 execution 分目录，得记下来
    web_execution_ids: list[int] = []
    web_report_name = None
    web_case = None  # 浏览器不可用时整段跳过，先占位，Day 5 段要用

    r = SESSION.get(f"{BASE}/web/status", timeout=15)
    if r.status_code != 200 or not r.json().get("available"):
        # 没有浏览器就跳过整段，且**不计入总数** —— 让无 GUI 的机器上仍是全绿
        reason = r.json().get("error", r.status_code) if r.status_code == 200 else r.status_code
        print(f"  ⚠️ 跳过 Web 段：本机没有可用的浏览器（{reason}）")
    else:
        check("Web 环境探测（浏览器可用）", True,
              r.json()["browsers"]["chrome"]["detail"])

        r = SESSION.get(DEMO_URL, timeout=10)
        check("离线演示页可访问", r.status_code == 200 and 'id="login-btn"' in r.text)

        r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
            "name": "Web-覆盖全部 15 种操作",
            "type": "web",
            "steps_json": [
                {"step_order": 1, "action_type": "open_url", "input_value": DEMO_URL,
                 "locator_type": "", "locator_value": ""},
                {"step_order": 2, "action_type": "input", "input_value": "admin",
                 "locator_type": "id", "locator_value": "username"},
                {"step_order": 3, "action_type": "input", "input_value": "secret",
                 "locator_type": "id", "locator_value": "password"},
                {"step_order": 4, "action_type": "click", "input_value": "",
                 "locator_type": "id", "locator_value": "login-btn"},
                {"step_order": 5, "action_type": "extract_variable", "input_value": "welcome_text",
                 "locator_type": "id", "locator_value": "welcome"},
                {"step_order": 6, "action_type": "assert_text_contains", "input_value": "欢迎 admin",
                 "locator_type": "id", "locator_value": "welcome"},
                {"step_order": 7, "action_type": "assert_exists", "input_value": "true",
                 "locator_type": "id", "locator_value": "status"},
                {"step_order": 8, "action_type": "assert_visible", "input_value": "false",
                 "locator_type": "id", "locator_value": "hidden"},
                {"step_order": 9, "action_type": "clear", "input_value": "",
                 "locator_type": "id", "locator_value": "city"},
                {"step_order": 10, "action_type": "force_wait", "input_value": "0.3",
                 "locator_type": "", "locator_value": ""},
                {"step_order": 11, "action_type": "smart_wait", "input_value": "",
                 "locator_type": "id", "locator_value": "bottom", "wait_seconds": 5},
                {"step_order": 12, "action_type": "scroll_to", "input_value": "",
                 "locator_type": "id", "locator_value": "bottom"},
                {"step_order": 13, "action_type": "execute_js", "input_value": "window.scrollTo(0,0);",
                 "locator_type": "", "locator_value": ""},
                {"step_order": 14, "action_type": "click", "input_value": "",
                 "locator_type": "id", "locator_value": "newlink"},
                {"step_order": 15, "action_type": "switch_window", "input_value": "1",
                 "locator_type": "", "locator_value": ""},
                {"step_order": 16, "action_type": "switch_window", "input_value": "0",
                 "locator_type": "", "locator_value": ""},
                {"step_order": 17, "action_type": "switch_iframe", "input_value": "",
                 "locator_type": "id", "locator_value": "frame"},
                {"step_order": 18, "action_type": "switch_iframe", "input_value": "default",
                 "locator_type": "", "locator_value": ""},
                {"step_order": 19, "action_type": "screenshot", "input_value": "demo",
                 "locator_type": "", "locator_value": ""},
            ],
        }, timeout=10)
        check("新建 Web 用例（19 步，覆盖 15 种操作）", r.status_code == 201,
              r.text[:120] if r.status_code != 201 else "")
        web_case = r.json().get("id") if r.status_code == 201 else None

        if web_case:
            detail = SESSION.get(f"{BASE}/cases/{web_case}", timeout=10).json()
            steps = detail.get("steps_json") or []
            check("Web 步骤原样保存", detail.get("type") == "web" and len(steps) == 19,
                  f'type={detail.get("type")} steps={len(steps)}')
            # 字段名漂移的回归防线：前后端对不上会静默跑偏，所以在验收里钉死
            check("Web 步骤字段名与执行引擎一致",
                  set(steps[0]) >= {"step_order", "enabled", "action_type", "input_value",
                                    "wait_seconds", "description", "locator_type", "locator_value"},
                  str(sorted(steps[0])))

            r = SESSION.post(f"{BASE}/cases/{web_case}/run-web",
                              json={"browser": "chrome", "headless": True, "timeout": 180},
                              timeout=300)
            check("执行 Web 用例", r.status_code == 200)
            if r.status_code == 200:
                ex = r.json()
                web_execution_ids.append(ex["id"])
                check("Web 用例整体通过", ex["status"] == "pass",
                      f'{ex["status"]} {ex["duration_ms"]}ms')
                step_results = ex["result_json"]["steps"]
                check("19 个步骤全部通过",
                      len(step_results) == 19 and all(s["status"] == "pass" for s in step_results),
                      " | ".join(f'{s["step_order"]}:{s["status"]}' for s in step_results
                                 if s["status"] != "pass") or "全部 pass")
                check("步骤间变量提取生效",
                      ex["result_json"]["extracted"].get("welcome_text") == "欢迎 admin",
                      str(ex["result_json"]["extracted"]))

                shots = [s for step in step_results for s in step["screenshots"]]
                check("手动截图步骤产出了文件", bool(shots), str(shots[:1]))
                if shots:
                    r2 = SESSION.get(f"{BASE}/reports/{shots[0]}", timeout=10)
                    check("截图可通过接口取到",
                          r2.status_code == 200 and "image" in r2.headers.get("content-type", ""),
                          f'{r2.status_code} {r2.headers.get("content-type")}')

        # 一条必然失败的用例：这条断言守的就是「失败自动截图从未生效」那个老 bug
        r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
            "name": "Web-必然失败", "type": "web",
            "steps_json": [
                {"step_order": 1, "action_type": "open_url", "input_value": DEMO_URL,
                 "locator_type": "", "locator_value": ""},
                {"step_order": 2, "action_type": "assert_text_contains",
                 "input_value": "页面里绝对没有这句话",
                 "locator_type": "id", "locator_value": "status"},
            ],
        }, timeout=10)
        fail_case = r.json().get("id") if r.status_code == 201 else None

        if fail_case:
            r = SESSION.post(f"{BASE}/cases/{fail_case}/run-web",
                              json={"browser": "chrome", "headless": True, "timeout": 120},
                              timeout=300)
            check("失败 Web 用例记为 fail", r.status_code == 200 and r.json()["status"] == "fail")
            if r.status_code == 200:
                ex = r.json()
                web_execution_ids.append(ex["id"])
                failed_step = next((s for s in ex["result_json"]["steps"]
                                    if s["status"] == "fail"), {})
                check("失败步骤自动截图（老 bug 回归防线）",
                      bool(failed_step.get("screenshots")),
                      str(failed_step.get("screenshots") or "没有截图"))

        # 类型守卫 + 空步骤守卫
        if case_id:
            r = SESSION.post(f"{BASE}/cases/{case_id}/run-web", json={}, timeout=30)
            check("接口用例调 run-web 返回 400", r.status_code == 400, str(r.status_code))
        r = SESSION.post(f"{BASE}/projects/{pid}/cases",
                          json={"name": "Web-空步骤", "type": "web", "steps_json": []}, timeout=10)
        if r.status_code == 201:
            r = SESSION.post(f"{BASE}/cases/{r.json()['id']}/run-web", json={}, timeout=30)
            check("无步骤 Web 用例返回 400", r.status_code == 400, str(r.status_code))

        # 步骤校验：未知操作 / 缺定位，都应在写库前被 422 挡下
        r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
            "name": "Web-非法操作", "type": "web",
            "steps_json": [{"step_order": 1, "action_type": "no_such_action"}]}, timeout=10)
        check("未知操作类型返回 422", r.status_code == 422, str(r.status_code))
        r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
            "name": "Web-缺定位", "type": "web",
            "steps_json": [{"step_order": 1, "action_type": "click", "input_value": ""}]}, timeout=10)
        check("需要定位却没填返回 422", r.status_code == 422, str(r.status_code))

        # 截图接口的路径穿越防护
        r = SESSION.get(f"{BASE}/reports/screenshots/..%2F..%2F..%2Fconfig.py", timeout=10)
        check("截图接口挡住路径穿越", r.status_code in (400, 404), str(r.status_code))

        # Web 报告：步骤表 + 截图都要出现在 HTML 里
        if web_execution_ids:
            r = SESSION.post(f"{BASE}/projects/{pid}/reports",
                              json={"execution_ids": web_execution_ids, "test_type": "web"},
                              timeout=60)
            check("生成 Web 报告", r.status_code == 200)
            if r.status_code == 200:
                web_report_name = r.json()["filename"]
                html = SESSION.get(f"{BASE}/reports/{web_report_name}", timeout=10).text
                check("Web 报告含步骤描述与截图",
                      "打开 URL" in html and "<img src=" in html and "screenshots/" in html)

        # ---------- Day 6 · 新增的 16 种操作 ----------
        # 一条用例跑完全部新操作，逐个操作单独断言 —— 哪个挂了能一眼看出是哪个。
        upload_file = Path(tempfile.gettempdir()) / "verify_upload.txt"
        upload_file.write_text("upload demo", encoding="utf-8")

        new_ops_case = None
        r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
            "name": "Web-新增 16 种操作",
            "type": "web",
            "steps_json": new_ops_steps(str(upload_file)),
        }, timeout=10)
        check("新建 Web 用例（43 步，覆盖新增 16 种操作）", r.status_code == 201,
              r.text[:200] if r.status_code != 201 else "")
        new_ops_case = r.json().get("id") if r.status_code == 201 else None

        if new_ops_case:
            r = SESSION.post(f"{BASE}/cases/{new_ops_case}/run-web",
                              json={"browser": "chrome", "headless": True, "timeout": 300},
                              timeout=480)
            check("执行新增操作用例", r.status_code == 200)
            if r.status_code == 200:
                ex = r.json()
                web_execution_ids.append(ex["id"])
                steps_by_order = {s["step_order"]: s for s in ex["result_json"]["steps"]}

                def passed(*orders: int) -> bool:
                    return all(steps_by_order.get(o, {}).get("status") == "pass" for o in orders)

                def why(*orders: int) -> str:
                    bad = [f'{o}:{steps_by_order.get(o, {}).get("message", "缺失")[:80]}'
                           for o in orders if steps_by_order.get(o, {}).get("status") != "pass"]
                    return " | ".join(bad)

                check("下拉框选择生效", passed(4), why(4))
                check("键盘按键（回车）生效", passed(8), why(8))
                check("上传文件生效", passed(10), why(10))
                check("鼠标悬停让菜单出现", passed(12), why(12))
                check("双击生效", passed(15), why(15))
                check("右键生效", passed(18), why(18))
                check("拖拽生效", passed(21), why(21))
                check("断言元素数量（3 个）通过", passed(22), why(22))
                check("断言元素属性（值 + 仅存在）通过", passed(23, 24), why(23, 24))
                check("弹窗确认（alert）后页面继续", passed(28), why(28))
                check("弹窗取消（prompt）后页面继续", passed(32), why(32))
                check("等待元素消失", passed(34), why(34))
                check("滚动到页面底部", passed(37), why(37))
                extracted = ex["result_json"]["extracted"]
                check("刷新页面确实重载（加载标记变了）",
                      bool(extracted.get("mark_before")) and extracted.get("mark_before") != extracted.get("mark_after"),
                      f'{extracted.get("mark_before")} → {extracted.get("mark_after")}')
                check("浏览器后退回到上一页", passed(43), why(43))
                check("新增操作用例整体通过", ex["status"] == "pass",
                      f'{ex["status"]} {ex["duration_ms"]}ms')

        # 新字段的校验：规格里标了 required 的字段没填，应在写库前被 422 挡下
        r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
            "name": "Web-拖拽缺目标元素", "type": "web",
            "steps_json": [{"step_order": 1, "action_type": "drag_and_drop",
                            "locator_type": "id", "locator_value": "drag-src"}]}, timeout=10)
        check("拖拽缺目标元素返回 422", r.status_code == 422, str(r.status_code))
        r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
            "name": "Web-下拉缺选项值", "type": "web",
            "steps_json": [{"step_order": 1, "action_type": "select_option",
                            "locator_type": "id", "locator_value": "city-select"}]}, timeout=10)
        check("下拉框选择缺选项值返回 422", r.status_code == 422, str(r.status_code))

        r = SESSION.get(f"{BASE}/web/status", timeout=15)
        actions = {a["value"]: a for a in r.json().get("actions", [])}
        check("操作枚举已扩到 31 种", len(actions) == 31, f"{len(actions)} 种")
        check("每个操作都下发了字段规格",
              all("fields" in a and "group" in a for a in actions.values()),
              str([k for k, a in actions.items() if "fields" not in a]))
        check("操作按分组下发",
              bool(r.json().get("action_groups")),
              str(r.json().get("action_groups")))
        check("下拉框选择声明了选择方式与选项值",
              [f["name"] for f in actions.get("select_option", {}).get("fields", [])]
              == ["locator", "value", "value2"],
              str(actions.get("select_option", {}).get("fields")))

    # ==================== Day 5 · 测试计划 ====================
    section("Day 5 · 测试计划 ★")
    # 计划用「一组互不依赖的用例 + 一个默认环境」，这里凑一条接口 + 一条 Web
    plan_case_ids = [case_id] + ([web_case] if web_case else [])

    r = SESSION.post(f"{BASE}/projects/{pid}/plans", json={
        "name": "验收计划·混合", "description": "接口 + Web",
        "env_id": env_id,
        "cases": [{"case_id": c} for c in plan_case_ids],
    }, timeout=10)
    check("新建计划", r.status_code == 201)
    plan_id = r.json().get("id") if r.status_code == 201 else None

    r = SESSION.get(f"{BASE}/projects/{pid}/plans", timeout=10)
    row = next((p for p in r.json()["items"] if p["id"] == plan_id), {})
    check("计划列表带用例数与环境名",
          row.get("case_count") == len(plan_case_ids) and row.get("env_name") is not None,
          f"{row.get('case_count')} 条 / 环境 {row.get('env_name')}")

    r = SESSION.get(f"{BASE}/plans/{plan_id}", timeout=10)
    detail = r.json()
    check("计划详情带用例名与类型",
          len(detail["cases"]) == len(plan_case_ids)
          and all(c["case_name"] and c["case_type"] for c in detail["cases"]))
    check("step_order 按提交顺序由后端编号",
          [c["step_order"] for c in detail["cases"]] == list(range(1, len(plan_case_ids) + 1)))

    r = SESSION.post(f"{BASE}/plans/{plan_id}/run", json={"timeout": 30}, timeout=600)
    check("执行计划（接口 + Web 混合）", r.status_code == 200)
    run = r.json() if r.status_code == 200 else {}
    if run:
        check("计划整体通过", run["status"] == "pass",
              f"通过 {run['passed']}/{run['total']}  {run['total_duration_ms']}ms")
        # plan_id 这个字段在 Day 4 之前一直是空的，这里钉死它确实写进去了
        check("每条执行记录都带 plan_id",
              all(c["plan_id"] == plan_id for c in run["cases"]),
              str([c["plan_id"] for c in run["cases"]]))
        # limit 给足：计划一次跑出多条执行记录，默认 20 条一页可能盖不全
        history = {e["id"] for e in SESSION.get(
            f"{BASE}/executions", params={"project_id": pid, "limit": 200},
            timeout=10).json()["items"]}
        check("计划产生的执行记录出现在执行中心",
              all(c["id"] in history for c in run["cases"]))
        web_execution_ids.extend(c["id"] for c in run["cases"])

    # ---------- 边界 ----------
    tmp_plan = SESSION.post(f"{BASE}/projects/{pid}/plans",
                             json={"name": "验收计划·边界"}, timeout=10).json()["id"]

    r = SESSION.post(f"{BASE}/plans/{tmp_plan}/run", json={}, timeout=10)
    check("空计划执行返回 400", r.status_code == 400, r.json().get("detail", ""))

    SESSION.put(f"{BASE}/plans/{tmp_plan}", json={
        "cases": [{"case_id": case_id, "enabled": False}]}, timeout=10)
    r = SESSION.post(f"{BASE}/plans/{tmp_plan}/run", json={}, timeout=10)
    check("用例全停用时执行返回 400", r.status_code == 400, r.json().get("detail", ""))

    # 停用的用例只计数、不执行（同一条用例挂两条，其中一条停用）
    SESSION.put(f"{BASE}/plans/{tmp_plan}", json={
        "cases": [{"case_id": case_id, "enabled": True},
                  {"case_id": case_id, "enabled": False}]}, timeout=10)
    r = SESSION.post(f"{BASE}/plans/{tmp_plan}/run", json={"timeout": 30}, timeout=120)
    run2 = r.json()
    check("停用的用例被跳过并计数",
          r.status_code == 200 and run2["total"] == 1 and run2["skipped"] == 1,
          f"执行 {run2['total']} 条 / 跳过 {run2['skipped']} 条")
    web_execution_ids.extend(c["id"] for c in run2["cases"])

    r = SESSION.get(f"{BASE}/plans/999999", timeout=10)
    check("不存在的计划返回 404", r.status_code == 404)
    r = SESSION.delete(f"{BASE}/plans/{tmp_plan}", timeout=10)
    check("删除计划", r.status_code == 204)
    r = SESSION.get(f"{BASE}/plans/{tmp_plan}", timeout=10)
    check("删除后计划查不到（404）", r.status_code == 404)

    # 删用例时计划里的关联被外键级联清掉 —— 这正是用关联表而不是 JSON 串的理由
    doomed = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
        "name": "验收·待删用例", "type": "api",
        "method": "GET", "url": "https://httpbin.org/status/204"}, timeout=10).json()["id"]
    r = SESSION.put(f"{BASE}/plans/{plan_id}", json={
        "cases": [{"case_id": c} for c in plan_case_ids] + [{"case_id": doomed}]}, timeout=10)
    check("计划加入一条临时用例", len(r.json()["cases"]) == len(plan_case_ids) + 1)
    SESSION.delete(f"{BASE}/cases/{doomed}", timeout=10)
    r = SESSION.get(f"{BASE}/plans/{plan_id}", timeout=10)
    check("用例被删后，计划里的关联自动清掉（外键级联）",
          len(r.json()["cases"]) == len(plan_case_ids),
          f"剩 {len(r.json()['cases'])} 条")

    # ==================== 缺陷管理 ====================
    section("缺陷管理 · 一键转入与状态流转")

    # 先造一条注定失败的执行：断言 500 响应等于 200
    r = SESSION.post(f"{BASE}/projects/{pid}/cases", json={
        "name": "验收·注定失败用例", "type": "api",
        "method": "GET", "url": "https://httpbin.org/status/500",
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""},
        ],
    }, timeout=10)
    fail_case_id = r.json().get("id")
    r = SESSION.post(f"{BASE}/cases/{fail_case_id}/run", json={"timeout": 30}, timeout=60)
    fail_execution = r.json() if r.status_code == 200 else {}
    check("造出一条失败的执行记录", fail_execution.get("status") == "fail",
          str(fail_execution.get("status")))
    fail_exec_id = fail_execution.get("id")

    r = SESSION.post(f"{BASE}/executions/{fail_exec_id}/defect", json={}, timeout=10)
    check("从失败的执行一键提缺陷", r.status_code == 201, r.text[:120])
    defect = r.json() if r.status_code == 201 else {}
    defect_id = defect.get("id")
    check("标题按用例名自动生成", defect.get("title") == "[fail] 验收·注定失败用例",
          str(defect.get("title")))
    check("描述带执行上下文与未通过断言",
          "来源执行记录" in defect.get("description", "")
          and "未通过的断言" in defect.get("description", ""))
    check("自动关联执行与用例",
          defect.get("execution_id") == fail_exec_id and defect.get("case_id") == fail_case_id)
    check("默认状态新建 / 严重程度一般 / 优先级 P1",
          defect.get("status") == "新建" and defect.get("severity") == "一般"
          and defect.get("priority") == "P1")
    check("详情回填用例名", defect.get("case_name") == "验收·注定失败用例",
          str(defect.get("case_name")))

    r = SESSION.post(f"{BASE}/executions/{fail_exec_id}/defect", json={}, timeout=10)
    check("同一执行重复提缺陷返回 409", r.status_code == 409)
    conflict = r.json().get("detail") if r.status_code == 409 else {}
    check("409 带上已有缺陷 id（前端据此跳转）",
          isinstance(conflict, dict) and conflict.get("defect_id") == defect_id, str(conflict))

    r = SESSION.post(f"{BASE}/executions/{execution_id}/defect", json={}, timeout=10)
    check("通过的执行记录拒绝提缺陷（400）", r.status_code == 400, r.text[:80])

    r = SESSION.get(f"{BASE}/projects/{pid}/defects", timeout=10)
    check("缺陷列表",
          r.status_code == 200 and any(d["id"] == defect_id for d in r.json()["items"]))
    row = next((d for d in r.json()["items"] if d["id"] == defect_id), {})
    check("列表带关联用例名", row.get("case_name") == "验收·注定失败用例", str(row.get("case_name")))

    r = SESSION.get(f"{BASE}/projects/{pid}/defects", params={"status": "新建"}, timeout=10)
    check("按状态筛选", r.status_code == 200
          and all(d["status"] == "新建" for d in r.json()["items"]))
    r = SESSION.get(f"{BASE}/projects/{pid}/defects", params={"keyword": "注定失败"}, timeout=10)
    check("按标题关键字筛选", r.status_code == 200 and len(r.json()["items"]) == 1,
          f"{len(r.json()['items'])} 条")
    r = SESSION.get(f"{BASE}/projects/{pid}/defects", params={"severity": "致命"}, timeout=10)
    check("按严重程度筛选排除不匹配", r.status_code == 200 and len(r.json()["items"]) == 0)

    r = SESSION.put(f"{BASE}/defects/{defect_id}",
                     json={"status": "处理中", "severity": "严重"}, timeout=10)
    check("更新缺陷（状态流转 + 严重程度）",
          r.status_code == 200 and r.json()["status"] == "处理中"
          and r.json()["severity"] == "严重")

    r = SESSION.put(f"{BASE}/defects/{defect_id}", json={"status": "瞎写的状态"}, timeout=10)
    check("非法状态值返回 422", r.status_code == 422)
    r = SESSION.post(f"{BASE}/projects/{pid}/defects", json={"title": ""}, timeout=10)
    check("空标题返回 422", r.status_code == 422)

    r = SESSION.post(f"{BASE}/projects/{pid}/defects", json={
        "title": "手工缺陷", "description": "不关联执行", "severity": "轻微", "priority": "P3",
    }, timeout=10)
    check("手工新建缺陷（不关联执行）",
          r.status_code == 201 and r.json().get("execution_id") is None)

    r = SESSION.post(f"{BASE}/executions/999999/defect", json={}, timeout=10)
    check("不存在的执行提缺陷返回 404", r.status_code == 404)
    r = SESSION.get(f"{BASE}/defects/999999", timeout=10)
    check("不存在的缺陷返回 404", r.status_code == 404)

    # 用例被删后缺陷仍在，只有 case_id 被外键置空（SET NULL）——执行记录也还在
    SESSION.delete(f"{BASE}/cases/{fail_case_id}", timeout=10)
    r = SESSION.get(f"{BASE}/defects/{defect_id}", timeout=10)
    check("用例被删后缺陷保留，case_id 置空（外键 SET NULL）",
          r.status_code == 200 and r.json()["case_id"] is None
          and r.json()["execution_id"] == fail_exec_id,
          f"case_id={r.json().get('case_id')}")

    # ==================== 分页 ====================
    section("列表分页 · 参数与边界")
    # 单独建一个项目塞 25 条用例来验分页。用主项目的话条数会被前面各段影响，
    # 断言里的具体数字就不稳了 —— 这样每次跑都是确定的 25 条。
    page_pid = SESSION.post(f"{BASE}/projects", json={"name": "验收·分页"},
                            timeout=10).json()["id"]
    try:
        for i in range(25):
            SESSION.post(f"{BASE}/projects/{page_pid}/cases",
                         json={"name": f"分页用例 {i + 1:02d}", "type": "api",
                               "method": "GET", "url": "https://httpbin.org/get"},
                         timeout=10)

        cases_url = f"{BASE}/projects/{page_pid}/cases"

        r = SESSION.get(cases_url, timeout=10)
        body = r.json()
        check("默认一页 20 条", r.status_code == 200 and len(body["items"]) == 20,
              f"{len(body.get('items', []))} 条")
        check("total 是全部条数、不受 limit 影响", body["total"] == 25,
              f"total={body.get('total')}")

        r = SESSION.get(cases_url, params={"limit": 10, "offset": 10}, timeout=10)
        page2 = r.json()
        check("limit + offset 生效",
              len(page2["items"]) == 10 and page2["total"] == 25,
              f"{len(page2['items'])} 条 / total={page2['total']}")

        r = SESSION.get(cases_url, params={"limit": 10}, timeout=10)
        first_ids = {c["id"] for c in r.json()["items"]}
        check("翻页取到的是另一批数据",
              first_ids.isdisjoint({c["id"] for c in page2["items"]}))

        r = SESSION.get(cases_url, params={"limit": 10, "offset": 20}, timeout=10)
        check("最后一页不足一整页也正常", len(r.json()["items"]) == 5)

        r = SESSION.get(cases_url, params={"offset": 999}, timeout=10)
        tail = r.json()
        check("offset 越界返回空数组且 total 不变",
              r.status_code == 200 and tail["items"] == [] and tail["total"] == 25,
              str(tail)[:80])

        r = SESSION.get(cases_url, params={"type": "web", "limit": 5}, timeout=10)
        check("筛选与分页叠加时 total 只算筛选后的",
              r.json()["total"] == 0 and r.json()["items"] == [])

        r = SESSION.get(cases_url, params={"limit": 0}, timeout=10)
        check("limit=0 被拒（422）", r.status_code == 422, f"status={r.status_code}")
        r = SESSION.get(cases_url, params={"limit": 201}, timeout=10)
        check("limit 超上限被拒（422）", r.status_code == 422, f"status={r.status_code}")
        r = SESSION.get(cases_url, params={"offset": -1}, timeout=10)
        check("offset 为负被拒（422）", r.status_code == 422, f"status={r.status_code}")

        # 执行统计：口径必须和列表的 total 一致，且不能被 limit 带偏
        # （执行中心那张统计卡原来拿「加载到的那一页」在算，分页后会翻一页变一次）
        stats = SESSION.get(f"{BASE}/executions/stats",
                            params={"project_id": pid}, timeout=10).json()
        listed = SESSION.get(f"{BASE}/executions",
                             params={"project_id": pid, "limit": 1}, timeout=10).json()
        check("执行统计与列表 total 一致（limit=1 也不影响）",
              stats.get("total") == listed.get("total"),
              f"stats.total={stats.get('total')} list.total={listed.get('total')}")
        check("执行统计的通过 + 失败 = 总数",
              stats.get("passed", 0) + stats.get("failed", 0) == stats.get("total"),
              str(stats))

        # 不分页的三个接口（项目 / 环境 / 数据文件）必须还是裸数组 ——
        # 它们同时是下拉数据源，一旦改成 {items,total} 前端选择器会静默取空
        r = SESSION.get(f"{BASE}/projects", timeout=10)
        check("项目列表仍是裸数组（下拉数据源，不分页）", isinstance(r.json(), list))
        r = SESSION.get(f"{BASE}/projects/{pid}/environments", timeout=10)
        check("环境列表仍是裸数组", isinstance(r.json(), list))
    finally:
        SESSION.delete(f"{BASE}/projects/{page_pid}", timeout=10)

    # ==================== 清理 ====================
    section("清理验收数据")
    if case_id:
        SESSION.delete(f"{BASE}/cases/{case_id}", timeout=10)
    if env_id:
        SESSION.delete(f"{BASE}/environments/{env_id}", timeout=10)
    if pid:
        SESSION.delete(f"{BASE}/projects/{pid}", timeout=10)
    r = SESSION.get(f"{BASE}/projects/{pid}", timeout=10)
    check("级联删除生效（项目 404）", r.status_code == 404)

    # 验收生成的报告文件与截图目录一并清掉，避免 reports/platform 越积越多
    # burst_report_names 是「同一秒连生多份」那条断言额外产出的，一起收走
    for name in (report_name, web_report_name, *burst_report_names):
        if not name:
            continue
        report_file = REPORT_ROOT / name
        if report_file.exists():
            report_file.unlink()
    for execution_id in web_execution_ids:
        shot_dir = REPORT_ROOT / "screenshots" / f"execution_{execution_id}"
        if shot_dir.exists():
            shutil.rmtree(shot_dir, ignore_errors=True)

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
