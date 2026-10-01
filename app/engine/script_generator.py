"""
pytest 脚本生成器 — 从数据库中读取用例配置，生成企业级 .py 测试脚本
"""
import os
import json
import logging
from datetime import datetime
from app.database.models import DBManager

logger = logging.getLogger(__name__)


class ScriptGenerator:
    """生成企业级的 pytest 测试脚本"""

    def __init__(self):
        self.scripts_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scripts'
        )
        os.makedirs(self.scripts_dir, exist_ok=True)

    # ------------------------------------------------------------------
    #  API 脚本生成
    # ------------------------------------------------------------------
    def generate_api_scripts(self, case_ids: list) -> str:
        """生成接口测试脚本"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(self.scripts_dir, f"api_export_{timestamp}")
        os.makedirs(output_dir, exist_ok=True)

        for cid in case_ids:
            case = DBManager.fetch_one("SELECT * FROM api_test_cases WHERE id=?", (cid,))
            if not case:
                continue
            headers = DBManager.fetch_all(
                "SELECT * FROM api_headers WHERE case_id=? AND enabled=1", (cid,)
            )
            assertions = DBManager.fetch_all(
                "SELECT * FROM api_assertions WHERE case_id=? AND enabled=1", (cid,)
            )

            safe_name = case['name'].replace(' ', '_').replace('/', '_').replace('\\', '_')
            filename = f"test_{safe_name}.py"
            filepath = os.path.join(output_dir, filename)

            lines = []
            lines.append("# -*- coding: utf-8 -*-")
            lines.append(f'"""{case["name"]} - 接口自动化测试"""')
            lines.append("import pytest")
            lines.append("import requests")
            lines.append("import json")
            lines.append("import logging")
            lines.append("")
            lines.append("# 日志配置")
            lines.append("logging.basicConfig(")
            lines.append("    level=logging.INFO,")
            lines.append("    format='%(asctime)s [%(levelname)s] %(message)s',")
            lines.append("    datefmt='%Y-%m-%d %H:%M:%S'")
            lines.append(")")
            lines.append("")
            lines.append("")
            lines.append("class TestAPICase:")
            lines.append(f'    """{case["name"]}"""')
            lines.append("")
            lines.append("    def test_case(self):")
            lines.append(f'        """执行接口测试用例: {case["name"]}"""')
            lines.append(f"        logging.info('开始执行用例: {case['name']}')")
            lines.append(f"        url = {repr(case['url'])}")
            lines.append("")
            lines.append("        # 请求头")
            headers_dict = {}
            for h in headers:
                headers_dict[h['key']] = h['value']
            lines.append(f"        headers = {repr(headers_dict)}")
            lines.append("        logging.info(f'请求头: {headers}')")
            lines.append("")
            lines.append("        # 认证处理")
            if case.get('auth_type') == 'bearer':
                lines.append(f"        headers['Authorization'] = 'Bearer {case['auth_value']}'")
                lines.append("        logging.info('使用 Bearer Token 认证')")
            elif case.get('auth_type') == 'basic':
                up = case['auth_value'].split(':', 1)
                lines.append(f"        from requests.auth import HTTPBasicAuth")
                lines.append(f"        auth = HTTPBasicAuth({repr(up[0])}, {repr(up[1] if len(up)>1 else '')})")
                lines.append("        logging.info('使用 Basic Auth 认证')")
            lines.append("")
            # 请求体处理
            body_type = case.get('body_type', 'none')
            body_content = case.get('body_content', '') or ''
            if body_type != 'none' and body_content:
                if body_type == 'json':
                    lines.append("        # 请求体 (JSON)")
                    lines.append("        try:")
                    lines.append(f"            body = json.loads({repr(body_content)})")
                    lines.append("        except json.JSONDecodeError:")
                    lines.append(f"            body = {repr(body_content)}")
                    lines.append(f"        logging.info(f'请求体: {{body}}')")
                    lines.append(f"        response = requests.{case['method'].lower()}(url, headers=headers, json=body)")
                elif body_type == 'form':
                    lines.append("        # 请求体 (Form-Data)")
                    lines.append(f"        body = {repr(body_content)}")
                    lines.append(f"        response = requests.{case['method'].lower()}(url, headers=headers, data=body)")
                else:
                    lines.append("        # 请求体")
                    lines.append(f"        body = {repr(body_content)}")
                    lines.append(f"        response = requests.{case['method'].lower()}(url, headers=headers, data=body)")
            else:
                lines.append(f"        response = requests.{case['method'].lower()}(url, headers=headers)")
            lines.append("")
            lines.append("        # 记录响应")
            lines.append("        logging.info(f'响应状态码: {response.status_code}')")
            lines.append("        logging.info(f'响应时间: {response.elapsed.total_seconds() * 1000:.0f}ms')")
            lines.append("")
            lines.append("        # 断言")
            for assertion in assertions:
                atype = assertion['assertion_type']
                expected = assertion['expected_value']
                target = assertion.get('target', '')
                if atype == 'status_code':
                    lines.append(f"        assert response.status_code == {int(expected)}, "
                                 f"f\"状态码断言失败: 期望={expected}, 实际={{response.status_code}}\"")
                    lines.append(f"        logging.info(f'状态码断言通过: {{response.status_code}} == {expected}')")
                elif atype == 'response_time':
                    lines.append(f"        assert response.elapsed.total_seconds() * 1000 < {float(expected)}, "
                                 f"f\"响应时间超限: {{response.elapsed.total_seconds() * 1000:.0f}}ms > {expected}\"")
                    lines.append(f"        logging.info(f'响应时间断言通过: {{response.elapsed.total_seconds() * 1000:.0f}}ms < {expected}ms')")
                elif atype == 'response_body' and target:
                    lines.append(f"        json_data = response.json()")
                    lines.append(f"        from jsonpath_ng import parse")
                    lines.append(f"        actual = parse({repr(target)}).find(json_data)")
                    lines.append(f"        actual_val = actual[0].value if actual else None")
                    lines.append(f"        assert str(actual_val) == {repr(expected)}, "
                                 f"f\"响应体断言失败: JSONPath={target}, 期望={expected}, 实际={{actual_val}}\"")
                    lines.append(f"        logging.info(f'响应体断言通过: JSONPath={{actual_val}} == {expected}')")
            lines.append("")
            lines.append("        logging.info('用例执行通过')")
            lines.append("")
            lines.append("")
            lines.append("if __name__ == '__main__':")
            lines.append("    pytest.main([__file__, '-v', '--log-cli-level=INFO'])")

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

        # 生成 conftest.py
        conftest_path = os.path.join(output_dir, 'conftest.py')
        with open(conftest_path, 'w', encoding='utf-8') as f:
            f.write("# Pytest configuration\n")
            f.write("import logging\n")
            f.write("logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')\n")

        return output_dir

    # ------------------------------------------------------------------
    #  Web 脚本生成（企业级增强版）
    # ------------------------------------------------------------------
    def generate_web_scripts(self, case_ids: list) -> str:
        """生成 Web 测试脚本（企业级模板）"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(self.scripts_dir, f"web_export_{timestamp}")
        os.makedirs(output_dir, exist_ok=True)

        LOCATOR_MAP = {
            'id': 'By.ID', 'name': 'By.NAME', 'class_name': 'By.CLASS_NAME',
            'tag_name': 'By.TAG_NAME', 'css_selector': 'By.CSS_SELECTOR',
            'xpath': 'By.XPATH', 'link_text': 'By.LINK_TEXT',
            'partial_link_text': 'By.PARTIAL_LINK_TEXT',
        }

        # 步骤描述（和 excel_exporter 保持一致）
        STEP_COMMENTS = {
            'open_url':           '打开浏览器，访问 {input}',
            'click':              '点击元素({locator})',
            'input':              '在输入框({locator})中输入"{input}"',
            'clear':              '清空输入框({locator})',
            'force_wait':         '等待 {wait} 秒',
            'smart_wait':         '等待元素({locator})出现（超时 {wait} 秒）',
            'switch_window':      '切换至第 {input} 个窗口',
            'switch_iframe':      '切换至 IFrame({locator})',
            'scroll_to':          '滚动到元素({locator})',
            'execute_js':         '执行 JavaScript：{input}',
            'screenshot':         '截图保存：{input}',
            'assert_text_contains': '验证文本({locator})包含"{input}"',
            'assert_visible':     '验证元素({locator})可见',
            'assert_exists':      '验证元素({locator})存在',
            'extract_variable':   '提取变量"{input}" → 从元素({locator})',
        }
        EXPECTED_COMMENTS = {
            'open_url':           '预期: 页面 {input} 成功加载',
            'click':              '预期: 元素({locator})被成功点击',
            'input':              '预期: 输入框({locator})显示"{input}"',
            'clear':              '预期: 输入框({locator})内容被清空',
            'force_wait':         '预期: 等待完成，页面无异常',
            'smart_wait':         '预期: 元素({locator})在 {wait} 秒内出现',
            'switch_window':      '预期: 成功切换至第 {input} 个窗口',
            'switch_iframe':      '预期: 成功切换至 IFrame({locator})',
            'scroll_to':          '预期: 元素({locator})已滚动到可视区域',
            'execute_js':         '预期: JavaScript 执行成功',
            'screenshot':         '预期: 截图"{input}"保存成功',
            'assert_text_contains': '预期: 页面({locator})包含"{input}"',
            'assert_visible':     '预期: 元素({locator})可见',
            'assert_exists':      '预期: 元素({locator})存在',
            'extract_variable':   '预期: 变量"{input}"提取成功',
        }

        for cid in case_ids:
            case = DBManager.fetch_one("SELECT * FROM web_test_cases WHERE id=?", (cid,))
            if not case:
                continue
            steps = DBManager.fetch_all(
                "SELECT * FROM web_steps WHERE case_id=? AND enabled=1 ORDER BY step_order",
                (cid,)
            )

            # 构造前置条件
            precondition_parts = []
            browser = case.get('browser', 'chrome').capitalize()
            precondition_parts.append(f"浏览器: {browser}")
            start_url = case.get('start_url', '') or ''
            if start_url:
                precondition_parts.append(f"起始URL: {start_url}")
            env_id = case.get('environment_id')
            if env_id:
                env = DBManager.fetch_one(
                    "SELECT name, base_url FROM environments WHERE id=?", (env_id,)
                )
                if env:
                    precondition_parts.append(f"环境: {env['name']}")
            precondition = " | ".join(precondition_parts)

            safe_name = case['name'].replace(' ', '_').replace('/', '_').replace('\\', '_')
            filename = f"test_{safe_name}.py"
            filepath = os.path.join(output_dir, filename)

            lines = []
            lines.append("# -*- coding: utf-8 -*-")
            lines.append('"""')
            lines.append('=' * 77)
            lines.append(f'  {case["name"]} - Web 自动化测试')
            lines.append('=' * 77)
            case_id_str = f"TC_WEB_{case['id']:04d}"
            lines.append(f"【用例编号】   {case_id_str}")
            lines.append(f"【模　　块】   (请填写模块)")
            lines.append(f"【用例标题】   {case['name']}")
            lines.append(f"【优　先级】   P2")
            lines.append(f"【前置条件】   {precondition}")
            lines.append(f"【是否可自动】 是")
            lines.append('=' * 77)
            lines.append('"""')
            lines.append("import pytest")
            lines.append("import logging")
            lines.append("from selenium import webdriver")
            lines.append("from selenium.webdriver.common.by import By")
            lines.append("from selenium.webdriver.support.ui import WebDriverWait")
            lines.append("from selenium.webdriver.support import expected_conditions as EC")
            lines.append("")
            lines.append("")
            lines.append("@pytest.fixture")
            lines.append("def driver():")
            lines.append(f'    """创建浏览器驱动"""')
            browser = case.get('browser', 'chrome')
            headless = case.get('headless', 0)
            if browser == 'chrome':
                lines.append("    options = webdriver.ChromeOptions()")
                if headless:
                    lines.append("    options.add_argument('--headless=new')")
                lines.append("    drv = webdriver.Chrome(options=options)")
            else:
                lines.append("    options = webdriver.EdgeOptions()")
                if headless:
                    lines.append("    options.add_argument('--headless=new')")
                lines.append("    drv = webdriver.Edge(options=options)")
            lines.append("    drv.maximize_window()")
            lines.append("    yield drv")
            lines.append("    drv.quit()")
            lines.append("")
            lines.append("")
            lines.append("class TestWebCase:")
            lines.append(f'    """{case["name"]} / {case_id_str}"""')
            lines.append("")
            lines.append("    def test_case(self, driver):")
            lines.append(f'        """执行 Web 测试用例: {case["name"]}"""')
            lines.append("        logging.info('=' * 60)")
            lines.append(f"        logging.info('开始执行: {case['name']}')")
            lines.append(f"        logging.info('用例编号: {case_id_str}')")
            lines.append(f"        logging.info('前置条件: {precondition}')")
            lines.append("        logging.info('=' * 60)")
            lines.append("")

            for step in steps:
                locators = DBManager.fetch_all(
                    "SELECT * FROM web_step_locators WHERE step_id=?", (step['id'],)
                )
                loc = locators[0] if locators else None
                input_val = step.get('input_value', '') or ''
                wait = step.get('wait_seconds', 0)

                action = step['action_type']

                # 构建定位器文本
                locator_text = ''
                if loc:
                    locator_text = f"{loc['locator_type']}={loc['locator_value']}"

                # 步骤注释
                comment_tpl = STEP_COMMENTS.get(action, f'执行操作: {action}')
                comment = comment_tpl.format(input=input_val, locator=locator_text, wait=wait)
                expected_tpl = EXPECTED_COMMENTS.get(action, '')
                expected = expected_tpl.format(input=input_val, locator=locator_text, wait=wait)

                lines.append("        # ------------------------------------------------------------------")
                lines.append(f"        # Step {step['step_order']}: {comment}")
                if expected:
                    lines.append(f"        # {expected}")
                lines.append("        # ------------------------------------------------------------------")

                if action == 'open_url':
                    lines.append(f"        driver.get({repr(input_val)})")
                    lines.append(f"        logging.info('Step {step['step_order']}: {comment}')")

                elif action == 'click':
                    if loc:
                        by = LOCATOR_MAP.get(loc['locator_type'], 'By.XPATH')
                        lv = repr(loc['locator_value'])
                        if wait:
                            lines.append(f"        WebDriverWait(driver, {wait}).until(EC.element_to_be_clickable(({by}, {lv}))).click()")
                        else:
                            lines.append(f"        driver.find_element({by}, {lv}).click()")
                        lines.append(f"        logging.info('Step {step['step_order']}: {comment}')")

                elif action == 'input':
                    if loc:
                        by = LOCATOR_MAP.get(loc['locator_type'], 'By.XPATH')
                        lv = repr(loc['locator_value'])
                        lines.append(f"        elem = driver.find_element({by}, {lv})")
                        lines.append(f"        elem.clear()")
                        lines.append(f"        elem.send_keys({repr(input_val)})")
                        lines.append(f"        logging.info('Step {step['step_order']}: {comment}')")

                elif action == 'force_wait':
                    sec = wait or float(input_val) if input_val else 1
                    lines.append(f"        import time; time.sleep({sec})")
                    lines.append(f"        logging.info('Step {step['step_order']}: {comment}')")

                elif action == 'smart_wait':
                    if loc:
                        by = LOCATOR_MAP.get(loc['locator_type'], 'By.XPATH')
                        lv = repr(loc['locator_value'])
                        lines.append(f"        WebDriverWait(driver, {wait or 10}).until(EC.presence_of_element_located(({by}, {lv})))")
                        lines.append(f"        logging.info('Step {step['step_order']}: {comment}')")

                elif action == 'assert_text_contains':
                    if loc:
                        by = LOCATOR_MAP.get(loc['locator_type'], 'By.XPATH')
                        lv = repr(loc['locator_value'])
                        lines.append(f"        text = driver.find_element({by}, {lv}).text")
                        lines.append(f"        assert {repr(input_val)} in text, f\"Step {step['step_order']}: 文本不包含\\\"{input_val}\\\", 实际: {{text[:50]}}\"")
                        lines.append(f"        logging.info('Step {step['step_order']}: 断言通过 - {comment}')")

                elif action == 'screenshot':
                    filename_ts = f"screenshot_{step['step_order']}_{datetime.now().strftime('%H%M%S')}.png"
                    lines.append(f"        driver.save_screenshot({repr(filename_ts)})")
                    lines.append(f"        logging.info('Step {step['step_order']}: {comment}')")

                elif action == 'scroll_to':
                    if loc:
                        by = LOCATOR_MAP.get(loc['locator_type'], 'By.XPATH')
                        lv = repr(loc['locator_value'])
                        lines.append(f"        elem = driver.find_element({by}, {lv})")
                        lines.append(f"        driver.execute_script('arguments[0].scrollIntoView(true);', elem)")
                        lines.append(f"        logging.info('Step {step['step_order']}: {comment}')")

                elif action == 'execute_js':
                    lines.append(f"        driver.execute_script({repr(input_val)})")
                    lines.append(f"        logging.info('Step {step['step_order']}: {comment}')")

                elif action == 'switch_window':
                    lines.append(f"        handles = driver.window_handles")
                    if input_val:
                        lines.append(f"        driver.switch_to.window(handles[{input_val}])")
                    else:
                        lines.append(f"        if len(handles) > 1: driver.switch_to.window(handles[-1])")
                    lines.append(f"        logging.info('Step {step['step_order']}: {comment}')")

                elif action == 'switch_iframe':
                    if input_val == 'default':
                        lines.append(f"        driver.switch_to.default_content()")
                    elif loc:
                        by = LOCATOR_MAP.get(loc['locator_type'], 'By.XPATH')
                        lv = repr(loc['locator_value'])
                        lines.append(f"        iframe = driver.find_element({by}, {lv})")
                        lines.append(f"        driver.switch_to.frame(iframe)")
                    lines.append(f"        logging.info('Step {step['step_order']}: {comment}')")

                lines.append("")

            # 收尾日志
            lines.append("        logging.info('=' * 60)")
            lines.append(f"        logging.info('用例执行完成: {case['name']}')")
            lines.append("        logging.info('=' * 60)")

            lines.append("")
            lines.append("if __name__ == '__main__':")
            lines.append("    pytest.main([__file__, '-v', '--log-cli-level=INFO'])")

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

        return output_dir
