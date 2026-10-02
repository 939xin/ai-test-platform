"""演示数据种子。

造一个可直接演示的项目：httpbin 环境 + 4 条接口用例（1 条故意失败）+ 若干执行记录。
可重复执行：已存在同名项目时复用，不会重复建项目。

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
    },
]


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

    # 3. 用例（同名则复用，避免重复执行时堆一堆副本）
    current = requests.get(f"{BASE}/projects/{pid}/cases", timeout=10).json()
    case_ids: list[int] = []
    for spec in CASES:
        found = next((c for c in current if c["name"] == spec["name"]), None)
        if found:
            case_ids.append(found["id"])
            continue
        payload = {"type": "api", "body_type": "", "body_content": ""}
        payload.update(spec)
        r = requests.post(f"{BASE}/projects/{pid}/cases", json=payload, timeout=10)
        r.raise_for_status()
        case_ids.append(r.json()["id"])
        print(f"  用例 {spec['name']} (id={case_ids[-1]})")

    # 4. 执行一遍，留下历史记录
    print("\n执行用例：")
    for cid in case_ids:
        r = requests.post(f"{BASE}/cases/{cid}/run", json={"env_id": env_id, "timeout": 30}, timeout=60)
        if r.status_code != 200:
            print(f"  用例 {cid} 执行失败：HTTP {r.status_code}")
            continue
        ex = r.json()
        n_pass = sum(1 for a in ex["result_json"].get("assertions", []) if a["passed"])
        n_all = len(ex["result_json"].get("assertions", []))
        print(f"  执行 #{ex['id']}  {ex['status']:<5} {ex['duration_ms']:>5}ms  断言 {n_pass}/{n_all}")

    print(f"\n完成。打开 http://localhost:5173/executions 查看（项目选「{PROJECT_NAME}」）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
