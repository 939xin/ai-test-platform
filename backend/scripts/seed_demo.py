"""演示数据种子。

造一个可直接演示的项目：httpbin 环境 + 用例（含 1 条故意失败）+ 场景串联 + 数据驱动
+ 若干执行记录。可重复执行：已存在同名项目时复用，不会重复建项目。

用法：backend> venv/Scripts/python.exe scripts/seed_demo.py
"""
import io
import sys
from pathlib import Path

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000/api"
PROJECT_NAME = "演示项目 · httpbin 接口测试"

# 数据驱动用的 CSV（表头为列名，每行执行一次）
DATA_FILE_NAME = "demo_params.csv"
DATA_CSV = "keyword,note\n苹果,第一个\n香蕉,第二个\n橙子,第三个\n"

# 每条用例：名称 / 方法 / URL / 断言（最后一条断言故意写错，用来演示失败态）
CASES = [
    {
        "name": "GET /get 连通性检查",
        "method": "GET",
        "url": "https://httpbin.org/get",
        "priority": "P0",
        "tags": "smoke",
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""},
            {"assertion_type": "response_body", "operator": "eq",
             "expected_value": "https://httpbin.org/get", "target": "$.url"},
        ],
        # 提取响应里的 url，供场景里的下一步用 ${echo_url} 引用
        "extract_json": [{"name": "echo_url", "source": "body", "expression": "$.url"}],
    },
    {
        "name": "GET /status/404 校验状态码",
        "method": "GET",
        "url": "https://httpbin.org/status/404",
        "priority": "P1",
        "tags": "回归",
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "404", "target": ""},
        ],
    },
    {
        "name": "POST /post 回显校验",
        "method": "POST",
        "url": "https://httpbin.org/post",
        "priority": "P1",
        "tags": "回归",
        "body_type": "json",
        "body_content": '{"username": "demo", "action": "login"}',
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""},
            {"assertion_type": "response_body", "operator": "eq",
             "expected_value": "demo", "target": "$.json.username"},
        ],
    },
    {
        "name": "GET /get 断言错误示例（预期失败）",
        "method": "GET",
        "url": "https://httpbin.org/get?page=2",
        "priority": "P2",
        "tags": "演示",
        "assertions_json": [
            # url 里没有 page=99，这条断言必然失败 —— 用来演示失败态与报告
            {"assertion_type": "response_body", "operator": "contains",
             "expected_value": "page=99", "target": "$.url"},
        ],
        "extract_json": [{"name": "echo_url", "source": "body", "expression": "$.url"}],
    },
    {
        # URL 整个由上一阶段提取的变量组成 —— 用来演示场景串联
        "name": "串联·引用上一步提取的 url",
        "method": "GET",
        "url": "${echo_url}",
        "priority": "P1",
        "tags": "演示",
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""},
        ],
        # 这条用例的 URL 靠场景里的上一步提供变量，单独跑必然失败 —— 不单独执行
        "skip_standalone": True,
    },
    {
        # 按数据文件逐行执行，URL 与断言都用本行的 ${keyword}
        "name": "数据驱动·按行请求 httpbin",
        "method": "GET",
        "url": "https://httpbin.org/get?keyword=${keyword}",
        "priority": "P1",
        "tags": "演示,数据驱动",
        "assertions_json": [
            {"assertion_type": "response_body", "operator": "eq",
             "expected_value": "${keyword}", "target": "$.args.keyword"},
        ],
        "data_file": DATA_FILE_NAME,
        "skip_standalone": True,  # 单独跑没有行数据，靠数据驱动接口执行
    },
]

# 场景：步骤 1 提取变量，步骤 2 直接引用它 —— 演示「用例之间传参」
SCENARIO_NAME = "演示场景：提取 url → 引用 url"
SCENARIO_STEPS = ["GET /get 连通性检查", "串联·引用上一步提取的 url"]


def main() -> int:
    # 1. 项目（同名则复用）
    existing = requests.get(f"{BASE}/projects", timeout=10).json()
    project = next((p for p in existing if p["name"] == PROJECT_NAME), None)
    if project:
        print(f"复用已有项目：{PROJECT_NAME} (id={project['id']})")
    else:
        r = requests.post(f"{BASE}/projects",
                          json={"name": PROJECT_NAME,
                                "description": "用于演示与自测的示例项目，接口均指向 httpbin.org"},
                          timeout=10)
        r.raise_for_status()
        project = r.json()
        print(f"新建项目：{PROJECT_NAME} (id={project['id']})")
    pid = project["id"]

    # 2. 环境
    envs = requests.get(f"{BASE}/projects/{pid}/environments", timeout=10).json()
    env = next((e for e in envs if e["name"] == "httpbin"), None)
    if env is None:
        env = requests.post(f"{BASE}/projects/{pid}/environments",
                            json={"name": "httpbin",
                                  "base_url": "https://httpbin.org",
                                  "variables_json": {"base_url": "https://httpbin.org"}},
                            timeout=10).json()
        print(f"  环境 httpbin (id={env['id']})")
    env_id = env["id"]

    # 3. 用例：同名则「收敛到本脚本的定义」（PUT 覆盖），避免重复执行时堆副本，
    #    也保证旧数据里缺的提取规则能被补上 —— 否则场景串联会跑不通
    current = requests.get(f"{BASE}/projects/{pid}/cases", timeout=10).json()
    case_ids: list[int] = []
    for spec in CASES:
        payload = {"type": "api", "body_type": "", "body_content": ""}
        payload.update({k: v for k, v in spec.items() if k != "skip_standalone"})
        found = next((c for c in current if c["name"] == spec["name"]), None)
        if found:
            r = requests.put(f"{BASE}/cases/{found['id']}", json=payload, timeout=10)
            r.raise_for_status()
            case_ids.append(found["id"])
            print(f"  用例 {spec['name']} （已存在，已同步定义，id={found['id']}）")
            continue
        r = requests.post(f"{BASE}/projects/{pid}/cases", json=payload, timeout=10)
        r.raise_for_status()
        case_ids.append(r.json()["id"])
        print(f"  用例 {spec['name']} (id={case_ids[-1]})")

    # 4. 执行一遍，留下历史记录（依赖场景变量的用例跳过，见 skip_standalone）
    print("\n执行用例：")
    for spec, cid in zip(CASES, case_ids):
        if spec.get("skip_standalone"):
            print(f"  跳过 {spec['name']}（需在场景/数据驱动下执行）")
            continue
        r = requests.post(f"{BASE}/cases/{cid}/run", json={"env_id": env_id, "timeout": 30}, timeout=60)
        if r.status_code != 200:
            print(f"  用例 {cid} 执行失败：HTTP {r.status_code}")
            continue
        ex = r.json()
        n_pass = sum(1 for a in ex["result_json"].get("assertions", []) if a["passed"])
        n_all = len(ex["result_json"].get("assertions", []))
        print(f"  执行 #{ex['id']}  {ex['status']:<5} {ex['duration_ms']:>5}ms  断言 {n_pass}/{n_all}")

    # 5. 数据文件（同名则覆盖重传）
    by_name = {spec["name"]: cid for spec, cid in zip(CASES, case_ids)}
    existing_ds = requests.get(f"{BASE}/projects/{pid}/datasets", timeout=10).json()
    if any(d["filename"] == DATA_FILE_NAME for d in existing_ds):
        requests.delete(f"{BASE}/projects/{pid}/datasets/{DATA_FILE_NAME}", timeout=10)
    r = requests.post(f"{BASE}/projects/{pid}/datasets",
                      files={"file": (DATA_FILE_NAME,
                                      DATA_CSV.encode("utf-8-sig"), "text/csv")},
                      timeout=10)
    r.raise_for_status()
    print(f"\n数据文件 {DATA_FILE_NAME}（{r.json()['rows']} 行，列名 {r.json()['columns']}）")

    # 数据驱动执行：一条用例按每行各跑一次
    dd_case = by_name.get("数据驱动·按行请求 httpbin")
    if dd_case:
        r = requests.post(f"{BASE}/cases/{dd_case}/run-data-driven",
                          json={"env_id": env_id}, timeout=120)
        if r.status_code == 200:
            run = r.json()
            print(f"  数据驱动执行：{run['passed']}/{run['total']} 通过")
            for row in run["rows"]:
                data = row["result_json"].get("row_data", {})
                print(f"    第{row['result_json']['row_index']}行 {row['status']:<5} "
                      f"keyword={data.get('keyword')}  {row['duration_ms']}ms")

    # 6. 场景（同名则复用）
    scenarios = requests.get(f"{BASE}/projects/{pid}/scenarios", timeout=10).json()
    scenario = next((s for s in scenarios if s["name"] == SCENARIO_NAME), None)
    if scenario is None:
        r = requests.post(f"{BASE}/projects/{pid}/scenarios", json={
            "name": SCENARIO_NAME,
            "description": "步骤 1 提取 url，步骤 2 用 ${echo_url} 引用",
            "steps": [{"case_id": by_name[n], "fail_strategy": "stop"} for n in SCENARIO_STEPS],
        }, timeout=10)
        r.raise_for_status()
        scenario = r.json()
        print(f"\n新建场景：{SCENARIO_NAME} (id={scenario['id']}，{len(SCENARIO_STEPS)} 步)")

        r = requests.post(f"{BASE}/scenarios/{scenario['id']}/run",
                          json={"env_id": env_id}, timeout=90)
        if r.status_code == 200:
            run = r.json()
            print(f"  执行场景：{run['status']}  {run['total_duration_ms']}ms")
            for s in run["steps"]:
                print(f"    步骤{s['step_order']} {s['status']:<5} {s['case_name']}")

    print(f"\n完成。打开 http://localhost:5173/executions 查看（项目选「{PROJECT_NAME}」）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
