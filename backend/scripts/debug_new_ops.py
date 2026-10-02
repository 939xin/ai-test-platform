"""单独复跑「新增 16 种操作」那条 Web 用例，打印每一步的结果。

跑完整 verify_all.py 要等前面一百多项（还有外网依赖），排查时太慢，
所以把步骤表提到 verify_all.new_ops_steps()，这里直接拿来复跑。

    venv/Scripts/python.exe scripts/debug_new_ops.py
"""
import sys
import tempfile
from pathlib import Path

# 本脚本与 verify_all 同目录，加进来才能直接 import。
# 注意：verify_all 在被导入时会把 sys.stdout 重新包成 UTF-8，
# 这里不要再包一次 —— 重复包装会把前一个流关掉，print 直接报错。
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from verify_all import BASE, new_ops_steps  # noqa: E402


def main() -> int:
    upload_file = Path(tempfile.gettempdir()) / "verify_upload.txt"
    upload_file.write_text("upload demo", encoding="utf-8")

    # 借演示项目的 id（没有就临时建一个）
    projects = requests.get(f"{BASE}/projects", timeout=10).json()
    if not projects:
        print("没有可用项目，先在页面上建一个演示项目再跑")
        return 1
    pid = projects[0]["id"]
    print(f"使用项目 {pid} - {projects[0]['name']}")

    r = requests.post(f"{BASE}/projects/{pid}/cases", json={
        "name": "DEBUG-新增 16 种操作",
        "type": "web",
        "steps_json": new_ops_steps(str(upload_file)),
    }, timeout=10)
    if r.status_code != 201:
        print("建用例失败:", r.status_code, r.text[:300])
        return 1
    case_id = r.json()["id"]
    print(f"用例 {case_id} 已建，开始执行…")

    try:
        r = requests.post(f"{BASE}/cases/{case_id}/run-web",
                          json={"browser": "chrome", "headless": True, "timeout": 300},
                          timeout=600)
        if r.status_code != 200:
            print("执行失败:", r.status_code, r.text[:300])
            return 1
        ex = r.json()
        print(f"\n整体: {ex['status']}  {ex['duration_ms']}ms")
        print(f"提取到的变量: {ex['result_json'].get('extracted')}\n")

        failed = 0
        for s in ex["result_json"]["steps"]:
            flag = "✅" if s["status"] == "pass" else "❌"
            if s["status"] != "pass":
                failed += 1
            print(f"  {flag} {s['step_order']:>2} {s['action_type']:<22} "
                  f"{s['duration_ms']:>6}ms  {s['desc'][:70]}")
            if s["status"] != "pass":
                print(f"       └─ {s['message'][:220]}")
        print(f"\n失败步骤数: {failed}")
        return 1 if failed else 0
    finally:
        requests.delete(f"{BASE}/cases/{case_id}", timeout=10)
        print("已删除调试用例")


if __name__ == "__main__":
    sys.exit(main())
