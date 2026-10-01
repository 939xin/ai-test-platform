"""
全面自测脚本 — 覆盖所有模块和边界情况
"""
import sys
import os
import io
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.database.models import init_db, DBManager

passed = 0
failed = 0

def test(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} <<<")
    return condition

def section(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")

# ============ SECTION 1: 数据库 ============
section("1. 数据库初始化与表结构")
init_db()

tables = ['environments', 'api_test_cases', 'api_headers', 'api_assertions',
          'web_test_cases', 'web_steps', 'web_step_locators',
          'global_variables', 'test_results', 'test_result_details', 'screenshots']
for t in tables:
    try:
        DBManager.fetch_all(f"SELECT 1 FROM {t} LIMIT 0")
        test(f"表 {t} 存在", True)
    except:
        test(f"表 {t} 存在", False)

# ============ SECTION 2: 环境 CRUD 边界测试 ============
section("2. 环境管理边界测试")

# 空名称
try:
    DBManager.insert("environments", {'name': '', 'base_url': ''})
    test("空名称环境（应允许创建）", True)
except:
    test("空名称环境创建失败", False)

# 特殊字符
eid = DBManager.insert("environments", {
    'name': "Test-Dev_01 (特殊字符)", 'base_url': 'https://api-test.example.com/v2/',
    'description': '用于测试的环境'
})
test(f"特殊字符环境名称", eid > 0)

# 查询验证
env = DBManager.fetch_one("SELECT * FROM environments WHERE id=?", (eid,))
test("Base URL 完整保留", env['base_url'] == 'https://api-test.example.com/v2/')

# 更新
DBManager.update("environments", {'base_url': 'https://new-url.com'}, "id=?", (eid,))
env = DBManager.fetch_one("SELECT * FROM environments WHERE id=?", (eid,))
test("更新后 URL 正确", env['base_url'] == 'https://new-url.com')

# ============ SECTION 3: API 用例 CRUD 边界测试 ============
section("3. 接口用例边界测试")

# 所有 HTTP 方法
methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
case_ids = {}
for m in methods:
    cid = DBManager.insert("api_test_cases", {
        'name': f'{m} 测试用例', 'url': f'/api/{m.lower()}-endpoint',
        'method': m, 'environment_id': eid
    })
    case_ids[m] = cid
    test(f"创建 {m} 用例", cid > 0)

# 所有认证类型
auth_types = [
    ('bearer', 'my-token-12345'),
    ('basic', 'admin:password'),
    ('apikey', 'key-abc-xyz'),
    ('none', ''),
]
for atype, aval in auth_types:
    cid = DBManager.insert("api_test_cases", {
        'name': f'认证测试-{atype}', 'url': '/auth-test', 'method': 'GET',
        'auth_type': atype, 'auth_value': aval
    })
    test(f"创建 {atype} 认证用例", cid > 0)

# 所有 body 类型
body_types = [
    ('json', '{"name": "test", "age": 25}'),
    ('form', 'username=admin&password=123'),
    ('xml', '<user><name>test</name></user>'),
    ('raw', 'plain text content'),
]
for btype, bcontent in body_types:
    cid = DBManager.insert("api_test_cases", {
        'name': f'Body测试-{btype}', 'url': '/body-test', 'method': 'POST',
        'body_type': btype, 'body_content': bcontent
    })
    test(f"创建 {btype} Body 用例", cid > 0)

# 断言类型
assert_cid = DBManager.insert("api_test_cases", {
    'name': '断言综合测试', 'url': '/assert-test', 'method': 'GET'
})
assertion_types = [
    ('status_code', '', 'eq', '200'),
    ('status_code', '', 'ne', '404'),
    ('response_body', '$.data.name', 'eq', 'test'),
    ('response_body', '$.msg', 'contains', 'success'),
    ('response_time', '', 'lt', '3000'),
]
for atype, tgt, op, val in assertion_types:
    aid = DBManager.insert("api_assertions", {
        'case_id': assert_cid, 'assertion_type': atype,
        'target': tgt, 'operator': op, 'expected_value': val
    })
    test(f"断言: {atype} {op} {val[:20]}", aid > 0)

# ============ SECTION 4: 全局变量 ============
section("4. 全局变量与解析器")

from app.utils.variable_resolver import VariableResolver

# 创建变量
DBManager.insert("global_variables", {
    'name': 'base_token', 'value': 'tk-123456', 'environment_id': None
})
DBManager.insert("global_variables", {
    'name': 'user_id', 'value': '88888', 'environment_id': eid
})

resolver = VariableResolver(environment_id=eid)
test("解析 base_token", resolver.resolve("${base_token}") == "tk-123456")
test("解析 user_id", resolver.resolve("${user_id}") == "88888")
test("解析未知变量保持原样", resolver.resolve("${unknown_var}") == "${unknown_var}")
test("解析无占位符文本", resolver.resolve("plain text") == "plain text")

# 运行时变量（优先级高于全局）
resolver.set_extra_var('user_id', '99999')
test("运行时变量覆盖全局", resolver.resolve("${user_id}") == "99999")

# 多变量混合
resolver2 = VariableResolver()
resolver2.set_extra_var('a', '1')
resolver2.set_extra_var('b', '2')
test("多变量解析", resolver2.resolve("${a}+${b}=3") == "1+2=3")

# ============ SECTION 5: 脚本生成器 ============
section("5. 脚本生成器深度验证")

from app.engine.script_generator import ScriptGenerator
gen = ScriptGenerator()

# 接口脚本
api_dir = gen.generate_api_scripts([case_ids['GET']])
test("生成接口脚本", os.path.isdir(api_dir))
test_files = [f for f in os.listdir(api_dir) if f.startswith('test_')]
if test_files:
    with open(os.path.join(api_dir, test_files[0]), 'r', encoding='utf-8') as f:
        code = f.read()
    test("包含 class TestAPICase", 'class TestAPICase' in code)
    test("包含 requests.get", 'requests.get' in code)
    test("包含 pytest import", 'import pytest' in code)
    test("包含 if __name__", 'if __name__' in code)

# Web 脚本
web_cid = DBManager.insert("web_test_cases", {
    'name': '脚本生成Web测试', 'browser': 'chrome', 'headless': 0,
    'start_url': 'https://test.com'
})
step_id = DBManager.insert("web_steps", {
    'case_id': web_cid, 'step_order': 1, 'action_type': 'open_url',
    'input_value': 'https://test.com'
})
DBManager.insert("web_step_locators", {
    'step_id': step_id, 'locator_type': 'xpath', 'locator_value': '//div'
})

web_dir = gen.generate_web_scripts([web_cid])
test("生成 Web 脚本", os.path.isdir(web_dir))
web_files = [f for f in os.listdir(web_dir) if f.startswith('test_')]
if web_files:
    with open(os.path.join(web_dir, web_files[0]), 'r', encoding='utf-8') as f:
        wcode = f.read()
    test("包含 selenium import", 'from selenium' in wcode)
    test("包含 driver fixture", 'def driver' in wcode)
    test("包含 driver.get", 'driver.get' in wcode)

# ============ SECTION 6: API Runner 直接执行验证 ============
section("6. API Runner 直接执行验证")

from app.engine.api_runner import APIRunner

# 测试用百度首页（国内稳定）
env_baidu = DBManager.fetch_one("SELECT * FROM environments WHERE id=?", (eid,))
# 更新环境URL为百度
DBManager.update("environments", {'base_url': 'https://www.baidu.com'}, "id=?", (eid,))
env_baidu = DBManager.fetch_one("SELECT * FROM environments WHERE id=?", (eid,))

# 创建测试用例
test_cid = DBManager.insert("api_test_cases", {
    'name': '综合测试-百度首页', 'url': '/', 'method': 'GET',
    'environment_id': eid
})
DBManager.insert("api_assertions", {
    'case_id': test_cid, 'assertion_type': 'status_code',
    'operator': 'eq', 'expected_value': '200'
})

# 直接执行（不通过QThread.start，直接调用run）
runner = APIRunner([test_cid], env_baidu)
runner.run()
test("APIRunner 直接执行完成", True)

# 检查结果是否正确保存
results = DBManager.fetch_all("SELECT * FROM test_results WHERE case_id=? ORDER BY id DESC LIMIT 1", (test_cid,))
test("结果已保存到 test_results", len(results) > 0)
if results:
    r = results[0]
    test(f"状态为 pass (实际={r['status']})", r['status'] == 'pass')
    test(f"耗时 > 0 (实际={r['duration_ms']}ms)", r['duration_ms'] > 0)

    details = DBManager.fetch_all("SELECT * FROM test_result_details WHERE result_id=? ORDER BY step_order", (r['id'],))
    test("有详情记录 (≥2)", len(details) >= 2)
    if details:
        test(f"步骤1含请求URL", bool(details[0].get('request_url')))
        test(f"步骤1含响应状态码 (实际={details[0].get('response_status')})", details[0].get('response_status') == 200)
        test(f"步骤1含响应体", bool(details[0].get('response_body')))
        test(f"步骤2为断言 (期望=200)", details[1].get('expected_value') == '200')
        test(f"断言通过 (实际={details[1].get('status')})", details[1].get('status') == 'pass')

# 测试失败断言
test_cid2 = DBManager.insert("api_test_cases", {
    'name': '错误断言测试', 'url': '/', 'method': 'GET',
    'environment_id': eid
})
DBManager.insert("api_assertions", {
    'case_id': test_cid2, 'assertion_type': 'status_code',
    'operator': 'eq', 'expected_value': '999'
})
runner2 = APIRunner([test_cid2], env_baidu)
runner2.run()
r2 = DBManager.fetch_one("SELECT * FROM test_results WHERE case_id=? ORDER BY id DESC LIMIT 1", (test_cid2,))
if r2:
    test(f"错误断言 → fail (实际={r2['status']})", r2['status'] == 'fail')

# 测试不存在域名
test_cid3 = DBManager.insert("api_test_cases", {
    'name': '不存在域名', 'url': 'http://notexist.test.invalid',
    'method': 'GET', 'environment_id': eid, 'is_relative_url': 0
})
DBManager.insert("api_assertions", {
    'case_id': test_cid3, 'assertion_type': 'status_code',
    'operator': 'eq', 'expected_value': '200'
})
runner3 = APIRunner([test_cid3], env_baidu)
runner3.run()
r3 = DBManager.fetch_one("SELECT * FROM test_results WHERE case_id=? ORDER BY id DESC LIMIT 1", (test_cid3,))
if r3:
    test(f"不存在域名 → error/fail (实际={r3['status']})", r3['status'] in ('error', 'fail'))

# ============ SECTION 7: Web Runner 逻辑 ============
section("7. Web Runner 步骤分发逻辑")

from app.engine.web_runner import WebRunner, LOCATOR_MAP

# 验证所有动作类型被定义
action_types = [
    'open_url', 'click', 'input', 'clear', 'force_wait', 'smart_wait',
    'switch_window', 'switch_iframe', 'scroll_to', 'execute_js',
    'screenshot', 'assert_text_contains', 'assert_visible',
    'assert_exists', 'extract_variable',
]
test(f"LOCATOR_MAP 8种定位", len(LOCATOR_MAP) == 8)

# 确认所有 Selenium By 类型可用
for lt in ['id', 'name', 'class_name', 'tag_name', 'css_selector',
           'xpath', 'link_text', 'partial_link_text']:
    test(f"定位方式: {lt}", lt in LOCATOR_MAP)

# 步骤描述生成
wr = WebRunner([], "chrome", False)
step = {'action_type': 'click', 'input_value': 'test'}
loc = {'locator_type': 'xpath', 'locator_value': '//button[@id="submit"]'}
desc = wr._get_step_desc(step, loc)
test("步骤描述包含操作名", '点击元素' in desc)
test("步骤描述包含定位", 'xpath' in desc)
test("步骤描述包含定位值", 'submit' in desc)

# ============ SECTION 8: HTML 报告生成 ============
section("8. HTML 报告生成器验证")

from app.engine.report_generator import ReportGenerator

result_id = DBManager.insert("test_results", {
    'test_type': 'api', 'case_id': case_ids['GET'], 'case_name': '报告验证用例',
    'status': 'pass', 'duration_ms': 150, 'environment_name': 'Test-Dev_01'
})

# 添加详情
DBManager.insert("test_result_details", {
    'result_id': result_id, 'step_order': 1,
    'step_description': 'GET /api/get-endpoint', 'status': 'pass',
    'request_url': 'https://new-url.com/api/get-endpoint',
    'request_method': 'GET', 'response_status': 200,
    'response_body': '{"status": "ok", "data": {"id": 1}}',
    'expected_value': '200', 'actual_value': '200'
})

# 添加模拟截图
import base64
fake_png = base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'\x00' * 50).decode()
detail_id = DBManager.insert("test_result_details", {
    'result_id': result_id, 'step_order': 2,
    'step_description': '截图步骤', 'status': 'pass',
})
DBManager.insert("screenshots", {
    'result_detail_id': detail_id, 'name': 'test_screenshot', 'image_base64': fake_png
})

rg = ReportGenerator()
report_path = rg.generate_from_results([result_id], test_type="api")
test("报告文件生成", os.path.exists(report_path))

with open(report_path, 'r', encoding='utf-8') as f:
    html = f.read()

html_checks = [
    ("DOCTYPE", '<!DOCTYPE html>' in html),
    ("<html lang", '<html lang="zh-CN"' in html),
    ("<title>测试报告</title>", '<title>测试报告' in html),
    ("概览统计卡片", 'stat-card' in html),
    ("通过状态显示", '通过' in html),
    ("用例名称", '报告验证用例' in html),
    ("环境信息", 'Python' in html or 'OS' in html),
    ("请求 URL 显示", 'get-endpoint' in html),
    ("截图嵌入(有img标签)", '<img src="data:image/png;base64,' in html),
    ("CSS 样式", 'background: linear-gradient' in html),
    ("footer", '接口自动化测试工具' in html),
]
for label, ok in html_checks:
    test(f"HTML: {label}", ok)

# ============ SECTION 9: PDF 导出 ============
section("9. PDF 导出器")

from app.utils.pdf_exporter import export_html_to_pdf
# 只测试导入和基本函数签名，不实际调用（需要 Chrome）
import inspect
sig = inspect.signature(export_html_to_pdf)
params = list(sig.parameters.keys())
test("函数签名正确", 'html_path' in params and 'output_path' in params)

# ============ SECTION 10: UI 组件初始化 ============
section("10. UI 组件基础初始化")

from PySide6.QtWidgets import QApplication
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

try:
    from app.ui.components.api_case_dialog import APICaseDialog
    dlg = APICaseDialog()
    test("APICaseDialog 创建", dlg is not None)
    dlg.close()
except Exception as e:
    test(f"APICaseDialog: {str(e)[:50]}", False)

try:
    from app.ui.components.web_case_dialog import WebCaseDialog
    dlg = WebCaseDialog(environment_id=eid)
    test("WebCaseDialog 创建", dlg is not None)
    test("WebCaseDialog 保存 environment_id", dlg.environment_id == eid)
    dlg.close()
except Exception as e:
    test(f"WebCaseDialog: {str(e)[:50]}", False)

try:
    from app.ui.components.step_editor import StepEditorDialog
    dlg = StepEditorDialog(case_id=web_cid)
    test("StepEditorDialog 创建", dlg is not None)
    dlg.close()
except Exception as e:
    test(f"StepEditorDialog: {str(e)[:50]}", False)

try:
    from app.ui.main_window import MainWindow
    from app.ui.home_page import HomePage
    from app.ui.api_test_page import APITestPage
    from app.ui.web_test_page import WebTestPage
    from app.ui.report_viewer import ReportViewer
    from app.ui.settings_page import SettingsPage

    window = MainWindow()
    pages = [
        ('home', HomePage()),
        ('api_test', APITestPage()),
        ('web_test', WebTestPage()),
        ('reports', ReportViewer()),
        ('settings', SettingsPage()),
    ]
    for key, page in pages:
        window.register_page(key, page)
    test("MainWindow 5页注册", window.content_stack.count() == 5)

    for key, _ in pages:
        window.switch_page(key)
    test("所有页面可切换", True)
    window.close()
except Exception as e:
    test(f"MainWindow: {str(e)[:50]}", False)

# ============ SECTION 11: 清理 ============
section("11. 清理测试数据")

# 清理所有测试数据（按依赖顺序）
DBManager.execute("DELETE FROM screenshots")
DBManager.execute("DELETE FROM test_result_details")
DBManager.execute("DELETE FROM test_results")
DBManager.execute("DELETE FROM web_step_locators")
DBManager.execute("DELETE FROM web_steps")
DBManager.execute("DELETE FROM web_test_cases")
DBManager.execute("DELETE FROM api_assertions")
DBManager.execute("DELETE FROM api_headers")
DBManager.execute("DELETE FROM api_test_cases")
DBManager.execute("DELETE FROM global_variables")
DBManager.execute("DELETE FROM environments")
test("所有测试数据清理完成", True)

# 验证清理
remaining = DBManager.fetch_all("SELECT COUNT(*) as cnt FROM environments")
test("environments 表已清空", remaining[0]['cnt'] == 0)

# ============ 结果汇总 ============
section("结果汇总")
total = passed + failed
print(f"\n  总计: {total} 项")
print(f"  通过: {passed} 项")
print(f"  失败: {failed} 项")
print(f"  通过率: {(passed/total*100):.1f}%")
print()

if failed == 0:
    print("  >>> 全部通过！所有模块自测无问题。")
else:
    print(f"  >>> 存在 {failed} 项失败，请查看上方 [FAIL] 标记。")

print()
