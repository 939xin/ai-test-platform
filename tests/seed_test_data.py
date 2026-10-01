"""
预填充测试数据 — 一键创建示例环境和用例，方便快速验证
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.models import init_db, DBManager


def seed():
    init_db()
    print("创建测试数据...\n")

    # ---- 环境 ----
    env_id = DBManager.insert("environments", {
        'name': 'HTTPBin 测试环境',
        'base_url': 'https://httpbin.org',
        'description': '用于接口测试的公开 HTTP 服务'
    })
    print(f"[1] 环境: HTTPBin 测试环境 (id={env_id})")

    env_id2 = DBManager.insert("environments", {
        'name': '本地开发环境',
        'base_url': 'http://localhost:8080',
        'description': '本地开发服务'
    })
    print(f"[2] 环境: 本地开发环境 (id={env_id2})")

    # ---- 全局变量 ----
    DBManager.insert("global_variables", {
        'name': 'token', 'value': 'sample-token-abc123',
        'description': '示例认证 Token'
    })
    DBManager.insert("global_variables", {
        'name': 'user_id', 'value': '10001',
        'description': '测试用户 ID'
    })
    print("[3] 全局变量: token, user_id")

    # ---- 接口用例 ----
    cases = [
        {
            'name': 'GET 获取 IP',
            'url': '/ip', 'method': 'GET',
            'assertions': [('status_code', '', 'eq', '200')],
            'headers': [('Accept', 'application/json')],
        },
        {
            'name': 'POST 提交 JSON',
            'url': '/post', 'method': 'POST',
            'body_type': 'json',
            'body_content': '{"name": "test", "value": 123}',
            'assertions': [
                ('status_code', '', 'eq', '200'),
                ('response_body', '$.json.name', 'eq', 'test'),
            ],
            'headers': [
                ('Content-Type', 'application/json'),
                ('Authorization', 'Bearer ${token}'),
            ],
        },
        {
            'name': 'GET 延迟响应',
            'url': '/delay/1', 'method': 'GET',
            'assertions': [
                ('status_code', '', 'eq', '200'),
                ('response_time', '', 'lt', '5000'),
            ],
        },
    ]

    for i, c in enumerate(cases):
        case_id = DBManager.insert("api_test_cases", {
            'name': c['name'],
            'url': c['url'],
            'method': c['method'],
            'body_type': c.get('body_type', 'none'),
            'body_content': c.get('body_content', ''),
            'environment_id': env_id,
            'is_relative_url': 1,
        })

        for key, val in c.get('headers', []):
            DBManager.insert("api_headers", {
                'case_id': case_id, 'key': key, 'value': val
            })

        for atype, target, op, expected in c.get('assertions', []):
            DBManager.insert("api_assertions", {
                'case_id': case_id,
                'assertion_type': atype,
                'target': target,
                'operator': op,
                'expected_value': expected,
            })

        print(f"[{4+i}] 接口用例: {c['name']} (id={case_id})")

    # ---- Web 用例 ----
    web_case_id = DBManager.insert("web_test_cases", {
        'name': '百度搜索流程演示',
        'browser': 'chrome',
        'headless': 0,
        'start_url': 'https://www.baidu.com',
    })

    steps = [
        ('open_url', 'https://www.baidu.com', '', '', ''),
        ('smart_wait', '', 'id', 'kw', '3'),
        ('input', '接口自动化测试工具', 'id', 'kw', ''),
        ('click', '', 'id', 'su', ''),
        ('force_wait', '2', '', '', ''),
        ('screenshot', '百度搜索结果', '', '', ''),
    ]

    for i, (action, input_val, loc_type, loc_val, wait) in enumerate(steps):
        step_id = DBManager.insert("web_steps", {
            'case_id': web_case_id,
            'step_order': i + 1,
            'action_type': action,
            'input_value': input_val,
            'wait_seconds': float(wait) if wait else 0,
            'enabled': 1,
        })
        if loc_type:
            DBManager.insert("web_step_locators", {
                'step_id': step_id,
                'locator_type': loc_type,
                'locator_value': loc_val,
            })

    print(f"[7] Web 用例: 百度搜索流程演示 (id={web_case_id})")
    print(f"    包含 6 个步骤: 打开URL → 智能等待 → 输入 → 点击 → 强制等待 → 截图")
    print()
    print("=== 测试数据创建完成 ===")
    print()
    print("现在可以启动应用进行测试：")
    print("  python main.py")
    print()
    print("接口测试：选择 'HTTPBin 测试环境' → 勾选用例 → 执行")
    print("Web 测试：切换到 Web 测试页 → 勾选用例 → 编辑步骤查看编排 → 执行")


if __name__ == '__main__':
    seed()
