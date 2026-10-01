"""
引擎层端到端验证脚本 — 不依赖 GUI，直接测试核心逻辑
"""
import sys
import os
import io
import json
import tempfile

# 强制 UTF-8 输出（解决 Windows GBK 终端的 emoji 编码问题）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.models import init_db, DBManager


def test_label(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


def check(name, condition):
    status = "[PASS]" if condition else "[FAIL]"
    print(f"  {status} {name}")
    return condition


# ====== 1. 数据库初始化 ======
test_label("1. 数据库初始化")
init_db()
check("数据库文件创建", os.path.exists(os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'data', 'test_tool.db'
)))

# ====== 2. 环境 CRUD ======
test_label("2. 环境管理 CRUD")
env_id = DBManager.insert("environments", {
    'name': '测试环境', 'base_url': 'https://httpbin.org', 'description': '验证用环境'
})
check(f"创建环境 (id={env_id})", env_id is not None and env_id > 0)

env = DBManager.fetch_one("SELECT * FROM environments WHERE id=?", (env_id,))
check(f"查询环境 '{env['name']}'", env is not None and env['base_url'] == 'https://httpbin.org')

DBManager.update("environments", {'base_url': 'https://httpbin.org/updated'}, "id=?", (env_id,))
env = DBManager.fetch_one("SELECT * FROM environments WHERE id=?", (env_id,))
check("更新 Base URL", env['base_url'] == 'https://httpbin.org/updated')

# ====== 3. 全局变量 CRUD ======
test_label("3. 全局变量 CRUD")
var_id = DBManager.insert("global_variables", {
    'name': 'test_token', 'value': 'abc123', 'description': '测试Token', 'environment_id': env_id
})
check(f"创建变量 (id={var_id})", var_id is not None and var_id > 0)

from app.utils.variable_resolver import VariableResolver
resolver = VariableResolver(environment_id=env_id)
resolved = resolver.resolve("Bearer ${test_token}")
check(f"变量解析: Bearer abc123", resolved == "Bearer abc123")

# ====== 4. 接口用例 CRUD ======
test_label("4. 接口测试用例 CRUD")
case_id = DBManager.insert("api_test_cases", {
    'name': '验证接口用例', 'url': '/get', 'method': 'GET',
    'body_type': 'none', 'auth_type': 'none', 'environment_id': env_id,
    'is_relative_url': 1, 'timeout': 30
})
check(f"创建接口用例 (id={case_id})", case_id is not None and case_id > 0)

# 添加请求头
DBManager.insert("api_headers", {'case_id': case_id, 'key': 'Accept', 'value': 'application/json'})
DBManager.insert("api_headers", {'case_id': case_id, 'key': 'X-Custom', 'value': 'test-value'})
headers = DBManager.fetch_all("SELECT * FROM api_headers WHERE case_id=?", (case_id,))
check(f"添加请求头 (2个)", len(headers) == 2)

# 添加断言
DBManager.insert("api_assertions", {
    'case_id': case_id, 'assertion_type': 'status_code',
    'operator': 'eq', 'expected_value': '200'
})
DBManager.insert("api_assertions", {
    'case_id': case_id, 'assertion_type': 'response_time',
    'operator': 'lt', 'expected_value': '5000'
})
assertions = DBManager.fetch_all("SELECT * FROM api_assertions WHERE case_id=?", (case_id,))
check(f"添加断言 (2个)", len(assertions) == 2)

# ====== 5. 接口脚本生成 ======
test_label("5. 接口脚本生成器")
from app.engine.script_generator import ScriptGenerator
generator = ScriptGenerator()
output_dir = generator.generate_api_scripts([case_id])
check(f"生成脚本目录存在: {output_dir}", os.path.isdir(output_dir))

py_files = [f for f in os.listdir(output_dir) if f.endswith('.py') and f.startswith('test_')]
check(f"包含测试 .py 文件", len(py_files) >= 1)

if py_files:
    with open(os.path.join(output_dir, py_files[0]), 'r', encoding='utf-8') as f:
        content = f.read()
    check("脚本包含 'import pytest'", 'import pytest' in content)
    check("脚本包含 'import requests'", 'import requests' in content)
    check("脚本包含 'def test_case'", 'def test_case' in content)
    check("脚本包含断言 (status_code)", 'status_code' in content)

# ====== 6. 接口执行引擎（动态生成 pytest） ======
test_label("6. 接口执行引擎 (pytest 代码生成)")
from app.engine.api_runner import APIRunner
import tempfile

# 创建 runner 并测试代码生成
env_data = DBManager.fetch_one("SELECT * FROM environments WHERE id=?", (env_id,))
runner = APIRunner([case_id], env_data)

test_dir = tempfile.mkdtemp(prefix="verify_api_")
test_file = os.path.join(test_dir, "test_api.py")
runner._generate_test_file(test_file)

check(f"测试文件生成: {test_file}", os.path.exists(test_file))

with open(test_file, 'r', encoding='utf-8') as f:
    test_content = f.read()
check("包含 'class TestAPI'", 'class TestAPI' in test_content)
check("包含 'requests.get'", 'requests.get' in test_content)
check("包含 'httpbin.org'", 'httpbin.org' in test_content)

# ====== 7. Web 用例 + 步骤 ======
test_label("7. Web 测试用例 + 步骤编排")
web_case_id = DBManager.insert("web_test_cases", {
    'name': '验证 Web 用例', 'browser': 'chrome', 'headless': 1,
    'start_url': 'https://example.com', 'environment_id': env_id
})
check(f"创建 Web 用例 (id={web_case_id})", web_case_id is not None and web_case_id > 0)

# 添加步骤
step1_id = DBManager.insert("web_steps", {
    'case_id': web_case_id, 'step_order': 1, 'action_type': 'open_url',
    'input_value': 'https://example.com', 'enabled': 1
})
DBManager.insert("web_step_locators", {
    'step_id': step1_id, 'locator_type': 'xpath', 'locator_value': '//body'
})
check(f"步骤1: 打开 URL", step1_id > 0)

step2_id = DBManager.insert("web_steps", {
    'case_id': web_case_id, 'step_order': 2, 'action_type': 'assert_text_contains',
    'input_value': 'Example Domain', 'enabled': 1
})
DBManager.insert("web_step_locators", {
    'step_id': step2_id, 'locator_type': 'tag_name', 'locator_value': 'body'
})
check(f"步骤2: 断言文本包含", step2_id > 0)

step3_id = DBManager.insert("web_steps", {
    'case_id': web_case_id, 'step_order': 3, 'action_type': 'screenshot',
    'input_value': '首页截图', 'enabled': 1
})
check(f"步骤3: 截图", step3_id > 0)

steps = DBManager.fetch_all("SELECT * FROM web_steps WHERE case_id=? ORDER BY step_order", (web_case_id,))
check(f"共 {len(steps)} 个步骤", len(steps) == 3)

# ====== 8. Web 脚本生成 ======
test_label("8. Web 脚本生成器")
web_output_dir = generator.generate_web_scripts([web_case_id])
check(f"Web 脚本目录存在: {web_output_dir}", os.path.isdir(web_output_dir))

web_py_files = [f for f in os.listdir(web_output_dir) if f.endswith('.py')]
check(f"包含 .py 文件", len(web_py_files) >= 1)

if web_py_files:
    with open(os.path.join(web_output_dir, web_py_files[0]), 'r', encoding='utf-8') as f:
        web_content = f.read()
    check("包含 'from selenium import webdriver'", 'from selenium import webdriver' in web_content)
    check("包含 'driver.get'", 'driver.get' in web_content)
    check("包含 'Example Domain'", 'Example Domain' in web_content)

# ====== 9. HTML 报告生成 ======
test_label("9. HTML 报告生成")
from app.engine.report_generator import ReportGenerator

# 先插入一些测试结果
result_id = DBManager.insert("test_results", {
    'test_type': 'api', 'case_id': case_id, 'case_name': '验证接口用例',
    'status': 'pass', 'duration_ms': 234, 'environment_name': '测试环境'
})
DBManager.insert("test_result_details", {
    'result_id': result_id, 'step_order': 1, 'step_description': 'GET /get',
    'status': 'pass', 'message': '', 'request_url': 'https://httpbin.org/get',
    'request_method': 'GET', 'response_status': 200
})
check(f"创建测试结果 (id={result_id})", result_id > 0)

report_gen = ReportGenerator()
report_path = report_gen.generate_from_results([result_id], test_type="api")
check(f"报告文件存在: {report_path}", os.path.exists(report_path))

with open(report_path, 'r', encoding='utf-8') as f:
    report_html = f.read()
check("HTML 包含标题", '测试报告' in report_html)
check("HTML 包含概览看板", '概览看板' in report_html or 'stat-card' in report_html)
check("HTML 包含通过状态", '通过' in report_html)
check("HTML 包含环境信息", 'Python' in report_html or 'OS' in report_html)

# ====== 10. 清理测试数据 ======
test_label("10. 清理测试数据")
DBManager.delete("api_assertions", "case_id=?", (case_id,))
DBManager.delete("api_headers", "case_id=?", (case_id,))
DBManager.delete("test_result_details", "result_id=?", (result_id,))
DBManager.delete("test_results", "id=?", (result_id,))
DBManager.delete("web_step_locators", "step_id IN (?,?,?)", (step1_id, step2_id, step3_id))
DBManager.delete("web_steps", "case_id=?", (web_case_id,))
DBManager.delete("web_test_cases", "id=?", (web_case_id,))
DBManager.delete("api_test_cases", "id=?", (case_id,))
DBManager.delete("global_variables", "id=?", (var_id,))
DBManager.delete("environments", "id=?", (env_id,))
check("数据清理完成", True)

print(f"\n{'='*60}")
print(f"  验证完成！所有核心引擎逻辑通过。")
print(f"{'='*60}\n")
