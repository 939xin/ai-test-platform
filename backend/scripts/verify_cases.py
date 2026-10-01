"""用例管理接口自检。

用 requests 而不是 curl，绕开 Git Bash 的中文编码问题。
脚本会留下一条 httpbin 用例，供后续执行模块使用。
用法（在 backend/ 目录下）：
    venv/Scripts/python.exe scripts/verify_cases.py
"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

BASE = "http://127.0.0.1:8000/api"


def main() -> int:
    checks: list[tuple[str, bool, int]] = []
    print("===== 用例管理接口自检 =====")

    projects = requests.get(f"{BASE}/projects", timeout=10).json()
    if not projects:
        print("  ✗ 没有项目，请先跑 verify_projects.py")
        return 1
    pid = projects[0]["id"]
    print(f"  使用项目 id={pid} 「{projects[0]['name']}」")

    payload = {
        # 刻意不传 project_id —— 前端也不传，这样自检才能覆盖真实的调用方式
        "name": "GET /get 连通性验证",
        "type": "api",
        "priority": "P0",
        "tags": "smoke,httpbin",
        "method": "GET",
        "url": "https://httpbin.org/get",
        "headers_json": {"Accept": "application/json"},
        "body_type": "none",
        "auth_type": "none",
        "assertions_json": [
            {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""},
            {"assertion_type": "response_body", "operator": "eq",
             "expected_value": "https://httpbin.org/get", "target": "$.url"},
        ],
    }

    # 新建
    r = requests.post(f"{BASE}/projects/{pid}/cases", json=payload, timeout=10)
    cid = r.json().get("id") if r.status_code == 201 else None
    checks.append(("新建用例", r.status_code == 201, r.status_code))
    print(f"  新建 → {r.status_code}  {r.text[:100]}")

    # 列表
    r = requests.get(f"{BASE}/projects/{pid}/cases", timeout=10)
    listed = r.status_code == 200 and any(c["id"] == cid for c in r.json())
    checks.append(("用例列表包含新用例", listed, r.status_code))
    print(f"  列表 → {r.status_code}，共 {len(r.json())} 条")

    # 按 type 筛选
    r = requests.get(f"{BASE}/projects/{pid}/cases", params={"type": "api"}, timeout=10)
    checks.append(("按 type 筛选", r.status_code == 200, r.status_code))

    # 按中文关键字筛选（顺带验证中文查询参数）
    r = requests.get(f"{BASE}/projects/{pid}/cases", params={"keyword": "连通性"}, timeout=10)
    kw_ok = r.status_code == 200 and len(r.json()) >= 1
    checks.append(("按中文关键字筛选", kw_ok, r.status_code))

    # 详情
    r = requests.get(f"{BASE}/cases/{cid}", timeout=10)
    detail = r.status_code == 200 and r.json().get("url") == "https://httpbin.org/get"
    checks.append(("用例详情", detail, r.status_code))

    # 断言被完整保存
    saved_assertions = r.json().get("assertions_json") or []
    checks.append(("断言 JSON 完整保存", len(saved_assertions) == 2, r.status_code))

    # 更新
    r = requests.put(f"{BASE}/cases/{cid}", json={"priority": "P1"}, timeout=10)
    checks.append(("更新用例", r.status_code == 200 and r.json().get("priority") == "P1", r.status_code))

    # 404
    r = requests.get(f"{BASE}/cases/999999", timeout=10)
    checks.append(("不存在返回 404", r.status_code == 404, r.status_code))

    # 空名称 422
    r = requests.post(f"{BASE}/projects/{pid}/cases", json={"project_id": pid, "name": ""}, timeout=10)
    checks.append(("空名称返回 422", r.status_code == 422, r.status_code))

    print("\n--- 明细 ---")
    for name, good, code in checks:
        print(f"  {'✅' if good else '❌'} {name} (HTTP {code})")

    passed = sum(1 for _, good, _ in checks if good)
    print(f"\n===== {passed}/{len(checks)} 项通过 =====")
    print(f"保留用例 id={cid}，供执行模块使用")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
