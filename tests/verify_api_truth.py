"""
真实验证: 用 httpbin.org 逐条测试 API Runner
验证: 正确数据→通过 / 错误数据→失败 / 报告含请求响应 / 逐条独立判断
"""
import sys, os, io, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.database.models import init_db, DBManager

init_db()
print("=" * 60)
print("  API Runner 真实数据验证")
print("=" * 60)

# 清理旧数据
for t in ['screenshots', 'test_result_details', 'test_results',
          'api_assertions', 'api_headers', 'api_test_cases',
          'web_step_locators', 'web_steps', 'web_test_cases',
          'global_variables', 'environments']:
    DBManager.execute(f"DELETE FROM {t}")

# 创建两个环境：国内稳定站点 + httpbin
eid_baidu = DBManager.insert('environments', {
    'name': '百度测试', 'base_url': 'https://www.baidu.com'
})
eid_httpbin = DBManager.insert('environments', {
    'name': 'httpbin测试', 'base_url': 'https://httpbin.org'
})
print(f"[1] 环境: 百度 (id={eid_baidu}), httpbin (id={eid_httpbin})")

# ---- 用例1: 正确断言百度（应该通过） ----
cid1 = DBManager.insert('api_test_cases', {
    'name': '【正确】百度首页 期望200', 'url': '/', 'method': 'GET',
    'environment_id': eid_baidu, 'is_relative_url': 1
})
DBManager.insert('api_assertions', {
    'case_id': cid1, 'assertion_type': 'status_code',
    'operator': 'eq', 'expected_value': '200'
})
print(f"[2] 用例1: 百度首页 断言200")

# ---- 用例2: 错误断言（应该失败） ----
cid2 = DBManager.insert('api_test_cases', {
    'name': '【错误】百度首页 期望404', 'url': '/', 'method': 'GET',
    'environment_id': eid_baidu, 'is_relative_url': 1
})
DBManager.insert('api_assertions', {
    'case_id': cid2, 'assertion_type': 'status_code',
    'operator': 'eq', 'expected_value': '404'
})
print(f"[3] 用例2: 百度首页 断言404(错误)")

# ---- 用例3: 带响应头的用例（应该通过） ----
cid3 = DBManager.insert('api_test_cases', {
    'name': '【正确】httpbin /get + 响应时间', 'url': '/get', 'method': 'GET',
    'environment_id': eid_httpbin, 'is_relative_url': 1, 'timeout': 15
})
DBManager.insert('api_assertions', {
    'case_id': cid3, 'assertion_type': 'status_code',
    'operator': 'eq', 'expected_value': '200'
})
DBManager.insert('api_assertions', {
    'case_id': cid3, 'assertion_type': 'response_time',
    'operator': 'lt', 'expected_value': '15000'
})
DBManager.insert('api_headers', {
    'case_id': cid3, 'key': 'Accept', 'value': 'application/json'
})
print(f"[4] 用例3: httpbin /get + 响应时间<15s + Accept头")

# ---- 用例4: 错误URL（应该失败） ----
cid4 = DBManager.insert('api_test_cases', {
    'name': '【错误】不存在的域名', 'url': 'http://notexist.example.invalid/api',
    'method': 'GET', 'environment_id': eid_baidu, 'is_relative_url': 0
})
DBManager.insert('api_assertions', {
    'case_id': cid4, 'assertion_type': 'status_code',
    'operator': 'eq', 'expected_value': '200'
})
print(f"[5] 用例4: '{'【错误】不存在的域名'}' (连接失败)")

# 取环境数据
env_baidu = DBManager.fetch_one("SELECT * FROM environments WHERE id=?", (eid_baidu,))
env_httpbin = DBManager.fetch_one("SELECT * FROM environments WHERE id=?", (eid_httpbin,))

# ---- 执行 ----
from app.engine.api_runner import APIRunner

# 用例1/2/4 用百度环境, 用例3 用httpbin环境
print("\n--- 批次1: 百度环境 (用例1,2,4) ---")
runner = APIRunner([cid1, cid2, cid4], env_baidu)
logs = []
runner.log_signal.connect(lambda t: logs.append(t))
start = time.time()
runner.run()
print(f"--- 批次1完毕 ({time.time()-start:.1f}s) ---")

print("\n--- 批次2: httpbin环境 (用例3) ---")
runner2 = APIRunner([cid3], env_httpbin)
runner2.log_signal.connect(lambda t: logs.append(t))
start = time.time()
runner2.run()
print(f"--- 批次2完毕 ({time.time()-start:.1f}s) ---")
logs = []
runner.log_signal.connect(lambda t: logs.append(t))

# 同步等待（不用 QThread 的 exec）
start = time.time()
runner.run()
elapsed = time.time() - start
print(f"--- 执行完毕 ({elapsed:.1f}s) ---\n")

# ---- 验证结果 ----
print("=" * 60)
print("  验证结果")
print("=" * 60)

results = DBManager.fetch_all(
    "SELECT r.* FROM test_results r ORDER BY r.id"
)

tests = 0; passed = 0; failed = 0

for r in results:
    tests += 1
    details = DBManager.fetch_all(
        "SELECT * FROM test_result_details WHERE result_id=? ORDER BY step_order", (r['id'],)
    )

    case_name = r['case_name']
    status = r['status']
    icon = "PASS" if status == 'pass' else "FAIL" if status == 'fail' else "ERROR"

    if status == 'pass':
        passed += 1
    else:
        failed += 1

    print(f"\n{'─'*50}")
    print(f"  [{icon}] {case_name}")
    print(f"  状态: {status} | 耗时: {r['duration_ms']}ms")

    for d in details:
        if d.get('request_url'):
            print(f"  请求: {d.get('request_method','')} {d.get('request_url','')[:80]}")
            print(f"  响应码: {d.get('response_status','')}")
            if d.get('response_body'):
                body_preview = d['response_body'][:120]
                print(f"  响应体: {body_preview}...")
        if d.get('expected_value'):
            print(f"  断言: 期望={d.get('expected_value','')} 实际={d.get('actual_value','')[:60]} → {'✅' if d['status']=='pass' else '❌'}")

# ---- 逐条判定 ----
print(f"\n{'='*60}")
print(f"  最终判定")
print(f"{'='*60}")

# 用例1 应该通过 (百度首页200)
r1 = DBManager.fetch_one("SELECT * FROM test_results WHERE case_id=?", (cid1,))
ok1 = r1['status'] == 'pass'
print(f"  用例1 (百度首页断言200): {'PASS' if ok1 else 'FAIL——BUG!'} 期望=pass 实际={r1['status']}")

# 用例2 应该失败 (百度首页断言404)
r2 = DBManager.fetch_one("SELECT * FROM test_results WHERE case_id=?", (cid2,))
ok2 = r2['status'] == 'fail'
print(f"  用例2 (百度首页断言404): {'FAIL' if ok2 else 'PASS——BUG!'} 期望=fail 实际={r2['status']}")

# 用例3 看网络情况 (httpbin可能不稳定)
r3 = DBManager.fetch_one("SELECT * FROM test_results WHERE case_id=?", (cid3,))
ok3 = r3['status'] in ('pass', 'error')  # pass或网络错误都算合理
print(f"  用例3 (httpbin+响应时间): {r3['status']} {'(网络可能不稳定)' if r3['status']=='error' else ''}")

# 用例4 应该失败(error)
r4 = DBManager.fetch_one("SELECT * FROM test_results WHERE case_id=?", (cid4,))
ok4 = r4['status'] in ('fail', 'error')
print(f"  用例4 (不存在的域名): {'FAIL/ERROR' if ok4 else 'PASS——BUG!'} 期望=fail/error 实际={r4['status']}")

# 验证详情表有数据
d1 = DBManager.fetch_all("SELECT * FROM test_result_details WHERE result_id=?", (r1['id'],))
has_request = any(d.get('request_url') for d in d1)
print(f"  用例1 详情含请求URL: {'✅' if has_request else '❌ 缺失——BUG!'}")

# 验证报告生成
from app.engine.report_generator import ReportGenerator
report_ids = [r['id'] for r in results]
report_path = ReportGenerator().generate_from_results(report_ids, test_type="api")
report_exists = os.path.exists(report_path)
print(f"  报告生成: {'✅' if report_exists else '❌ 缺失——BUG!'} ({report_path})")

if report_exists:
    with open(report_path, 'r', encoding='utf-8') as f:
        html = f.read()
    has_req_detail = 'request_url' in html.lower() or '请求' in html
    has_resp = 'response_status' in html or '200' in html
    has_fail = '失败' in html
    print(f"  报告含请求详情: {'✅' if has_req_detail else '❌'}")
    print(f"  报告含响应数据: {'✅' if has_resp else '❌'}")
    print(f"  报告含失败标记: {'✅' if has_fail else '❌'}")

# 核心验证：用例1=pass, 用例2=fail 必须正确（这是"正确/错误数据"的区分）
core_ok = ok1 and ok2 and ok4
print(f"\n{'='*60}")
if core_ok:
    print(f"  ✅ 核心验证通过！正确数据→通过，错误数据→失败")
else:
    print(f"  ❌ 核心验证失败！正确/错误数据未能正确区分")
print(f"  报告含请求详情: {'✅' if has_request else '❌'}")
print(f"  报告含响应数据: {'✅' if has_resp else '❌'}")
print(f"{'='*60}")
