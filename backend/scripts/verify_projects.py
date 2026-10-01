"""项目管理接口自检 — 用 requests 走一遍 CRUD。

用 Python 发请求而不是 curl，是为了绕开 Git Bash 传递中文参数时的编码问题。
用法（在 backend/ 目录下）：
    venv/Scripts/python.exe scripts/verify_projects.py
"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

BASE = "http://127.0.0.1:8000/api/projects"


def main() -> int:
    checks: list[tuple[str, bool, int]] = []
    print("===== 项目管理接口自检 =====")

    # 新建
    r = requests.post(BASE, json={"name": "电商平台接口测试", "description": "Day 2 验证用项目"}, timeout=10)
    pid = r.json().get("id") if r.status_code == 201 else None
    checks.append(("新建项目", r.status_code == 201, r.status_code))
    print(f"  新建 → {r.status_code}  {r.text[:110]}")

    # 列表
    r = requests.get(BASE, timeout=10)
    listed = r.status_code == 200 and any(p["id"] == pid for p in r.json())
    checks.append(("项目列表包含新项目", listed, r.status_code))
    print(f"  列表 → {r.status_code}，共 {len(r.json())} 条")

    # 更新（中文往返）
    r = requests.put(f"{BASE}/{pid}", json={"description": "更新后的描述"}, timeout=10)
    updated = r.status_code == 200 and r.json().get("description") == "更新后的描述"
    checks.append(("更新项目（中文往返）", updated, r.status_code))
    print(f"  更新 → {r.status_code}")

    # 详情
    r = requests.get(f"{BASE}/{pid}", timeout=10)
    detail = r.status_code == 200 and r.json().get("name") == "电商平台接口测试"
    checks.append(("项目详情（中文往返）", detail, r.status_code))
    print(f"  详情 → {r.status_code}")

    # 不存在的项目
    r = requests.get(f"{BASE}/999999", timeout=10)
    checks.append(("不存在返回 404", r.status_code == 404, r.status_code))

    # 空名称
    r = requests.post(BASE, json={"name": ""}, timeout=10)
    checks.append(("空名称返回 422", r.status_code == 422, r.status_code))

    # 删除
    r = requests.delete(f"{BASE}/{pid}", timeout=10)
    checks.append(("删除项目", r.status_code == 204, r.status_code))
    print(f"  删除 → {r.status_code}")

    # 删除后应查不到
    r = requests.get(f"{BASE}/{pid}", timeout=10)
    checks.append(("删除后返回 404", r.status_code == 404, r.status_code))

    print("\n--- 明细 ---")
    for name, good, code in checks:
        print(f"  {'✅' if good else '❌'} {name} (HTTP {code})")

    passed = sum(1 for _, good, _ in checks if good)
    print(f"\n===== {passed}/{len(checks)} 项通过 =====")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
