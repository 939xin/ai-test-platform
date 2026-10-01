"""
用户操作链路完整验证
1. settings_page 建环境 → 2. api_test_page 选环境 → 3. 建用例 → 4. 执行 → 5. 看响应
"""
import sys, os, io, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.database.models import init_db, DBManager
init_db()

print("=" * 60)
print("  完整用户流程验证")
print("=" * 60)

# 清理
for t in ['screenshots','test_result_details','test_results','api_assertions',
          'api_headers','api_test_cases','web_step_locators','web_steps',
          'web_test_cases','global_variables','environments']:
    DBManager.execute(f"DELETE FROM {t}")

# ====== 步骤1: 用户在设置页创建环境 ======
print("\n[步骤1] 用户在"设置 > 环境管理"创建环境...")
env_id = DBManager.insert("environments", {
    'name': '百度测试', 'base_url': 'https://www.baidu.com'
})
env = DBManager.fetch_one("SELECT * FROM environments WHERE id=?", (env_id,))
print(f"  ✅ 环境已创建: {env['name']} → {env['base_url']}")

# ====== 步骤2: 模拟 api_test_page.showEvent 刷新环境列表 ======
print("\n[步骤2] 用户切换到"接口测试"页面...")
print("  → showEvent() 触发 → _load_environments()")

# 模拟 _load_environments
envs = DBManager.fetch_all("SELECT id, name FROM environments ORDER BY id")
print(f"  → 从数据库查到 {len(envs)} 个环境:")
for e in envs:
    print(f"     - {e['name']} (id={e['id']})")

if len(envs) == 0:
    print("  ❌ BUG! 环境列表为空！showEvent 没刷新？")
else:
    print("  ✅ 环境下拉框可以选到刚才创建的环境")

# ====== 步骤3: 用户新建接口用例 ======
print("\n[步骤3] 用户点击"+ 新建用例"并保存...")
case_id = DBManager.insert("api_test_cases", {
    'name': '百度首页状态码测试',
    'url': '/',
    'method': 'GET',
    'environment_id': env_id,
    'is_relative_url': 1,
})
# 添加断言：期望200
DBManager.insert("api_assertions", {
    'case_id': case_id,
    'assertion_type': 'status_code',
    'operator': 'eq',
    'expected_value': '200',
})
# 添加请求头
DBManager.insert("api_headers", {
    'case_id': case_id,
    'key': 'User-Agent',
    'value': 'APITestTool/1.0',
})

# 验证用例已保存
case = DBManager.fetch_one("SELECT * FROM api_test_cases WHERE id=?", (case_id,))
print(f"  ✅ 用例已保存: {case['name']} ({case['method']} {case['url']})")

# 验证用例列表（模拟 _load_test_cases）
cases = DBManager.fetch_all(
    "SELECT * FROM api_test_cases WHERE environment_id=? ORDER BY updated_at DESC",
    (env_id,)
)
print(f"  ✅ 用例在列表中可见: {len(cases)} 条")

# ====== 步骤4: 用户勾选用例并点击"执行" ======
print("\n[步骤4] 用户勾选用例，选择'百度测试'环境，点击"执行选中"...")
print(f"  选中用例: {case['name']}")
print(f"  选中环境: {env['name']} (base_url={env['base_url']})")

from app.engine.api_runner import APIRunner

# 模拟用户界面：收集 case_finished 信号数据
case_results = []
log_output = []

runner = APIRunner([case_id], env)
runner.log_signal.connect(lambda t: log_output.append(t))
runner.case_finished.connect(lambda d: case_results.append(d))

import time
start = time.time()
runner.run()
elapsed = time.time() - start

print(f"\n  执行耗时: {elapsed:.1f}s")
print(f"  日志行数: {len(log_output)}")
print(f"  case_finished 信号: {len(case_results)} 次")

# ====== 步骤5: 验证结果 ======
print("\n[步骤5] 验证响应数据...")

if case_results:
    d = case_results[0]
    print(f"  📡 请求: {d['request_method']} {d['request_url']}")
    print(f"  📥 响应状态码: {d['response_status']}")
    print(f"  ⏱ 耗时: {d['duration_ms']:.0f}ms")

    # 判断结果
    status_ok = d['response_status'] == 200
    assertion_ok = all(a['passed'] for a in d['assertions'])
    overall = d['status']

    print(f"\n  ┌─────────────────────────────────────┐")
    print(f"  │ 状态码: {d['response_status']} → {'✅ 正确' if status_ok else '❌ 异常'}                          │")
    print(f"  │ 断言: {len(d['assertions'])}条 → {'✅ 全部通过' if assertion_ok else '❌ 有失败'}                │")
    print(f"  │ 结果: {overall}                          │")
    print(f"  │ 响应体大小: {len(d['response_body'])} 字符                    │")
    print(f"  │ 响应头数量: {len(d['response_headers'])} 字符 (JSON)         │")
    print(f"  └─────────────────────────────────────┘")

    # 证明真实的 HTTP 请求
    print(f"\n  🔍 证据：响应体前200字符:")
    print(f"  {d['response_body'][:200]}")

    # 证明响应头有数据
    try:
        headers_dict = json.loads(d['response_headers'])
        print(f"\n  🔍 证据：响应头样本:")
        for k in list(headers_dict.keys())[:5]:
            print(f"     {k}: {headers_dict[k]}")
    except:
        pass

    # 证明断言
    print(f"\n  🔍 证据：断言详情:")
    for a in d['assertions']:
        status = "✅" if a['passed'] else "❌"
        print(f"     {status} {a['type']}: 期望={a['expected']} 实际={a['actual']}")

    # 证明数据库有记录
    db_results = DBManager.fetch_all("SELECT * FROM test_results ORDER BY id DESC LIMIT 1")
    if db_results:
        r = db_results[0]
        print(f"\n  🔍 证据：数据库 test_results 记录:")
        print(f"     id={r['id']} status={r['status']} duration={r['duration_ms']}ms")

        details = DBManager.fetch_all("SELECT * FROM test_result_details WHERE result_id=? ORDER BY step_order", (r['id'],))
        print(f"     test_result_details: {len(details)} 行")
        for det in details:
            print(f"       步骤{det['step_order']}: {det['step_description'][:50]} | 状态码={det.get('response_status','')}")

    # 验证报告存在
    reports = [f for f in os.listdir(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports'))
               if f.endswith('.html')]
    print(f"\n  🔍 证据：报告文件: {len(reports)} 个")

else:
    print("  ❌ 致命错误: case_finished 信号未收到！HTTP 请求可能未执行！")

# ====== 最终判定 ======
print(f"\n{'=' * 60}")
if not case_results:
    print("  ❌ 失败：接口测试未真正执行 HTTP 请求")
elif case_results[0]['response_status'] == 0:
    print("  ❌ 失败：HTTP 请求未收到响应（网络问题？）")
elif case_results[0]['response_status'] == 200 and case_results[0]['status'] == 'pass':
    print("  ✅ 全部通过！接口测试真正执行了 HTTP 请求并返回了响应数据")
else:
    print(f"  ⚠️ 部分通过：状态={case_results[0]['status']}")
print(f"{'=' * 60}")

# 清理
for t in ['screenshots','test_result_details','test_results','api_assertions',
          'api_headers','api_test_cases','global_variables','environments']:
    DBManager.execute(f"DELETE FROM {t}")
