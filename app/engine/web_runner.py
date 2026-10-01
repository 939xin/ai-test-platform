"""
Web 测试执行引擎 — 基于 Selenium WebDriver 执行 Web 自动化测试
"""
import os
import time
import base64
import traceback
from datetime import datetime
from PySide6.QtCore import QThread, Signal
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    NoSuchWindowException, WebDriverException,
    ElementClickInterceptedException, StaleElementReferenceException,
    InvalidSelectorException
)
from app.database.models import DBManager
from app.utils.variable_resolver import VariableResolver
from app.utils.browser_manager import BrowserManager

# 8 种定位方式映射
LOCATOR_MAP = {
    'id': By.ID,
    'name': By.NAME,
    'class_name': By.CLASS_NAME,
    'tag_name': By.TAG_NAME,
    'css_selector': By.CSS_SELECTOR,
    'xpath': By.XPATH,
    'link_text': By.LINK_TEXT,
    'partial_link_text': By.PARTIAL_LINK_TEXT,
}


class WebRunner(QThread):
    """Web 测试执行线程"""
    log_signal = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, case_ids: list, browser: str = "chrome", headless: bool = False):
        super().__init__()
        self.case_ids = case_ids
        self.browser = browser
        self.headless = headless
        self.driver = None
        self.result_ids = []
        self.variables = VariableResolver()

    def run(self):
        self.log_signal.emit("===== Web 自动化测试开始 =====")
        self.log_signal.emit(f"浏览器: {self.browser}, 模式: {'无头' if self.headless else '调试'}")

        try:
            self.driver = BrowserManager.create_driver(self.browser, self.headless)
            self.log_signal.emit("✅ 浏览器启动成功")

            for case_id in self.case_ids:
                result_id = self._run_case(case_id)
                if result_id:
                    self.result_ids.append(result_id)

        except Exception as e:
            self.log_signal.emit(f"[ERR] {str(e)}")
            traceback.print_exc()
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    self.log_signal.emit("🔒 浏览器已关闭")
                except Exception:
                    pass

        self.log_signal.emit("===== Web 自动化测试结束 =====")

        # 生成 HTML 报告
        report_path = ""
        if self.result_ids:
            try:
                from app.engine.report_generator import ReportGenerator
                generator = ReportGenerator()
                report_path = generator.generate_from_results(self.result_ids, test_type="web")
                self.log_signal.emit(f"📊 报告已生成: {report_path}")
            except Exception as e:
                self.log_signal.emit(f"[WARN] 报告生成失败: {str(e)}")

        self.finished_signal.emit(report_path)

    def _run_case(self, case_id: int):
        """执行单个 Web 测试用例"""
        case = DBManager.fetch_one("SELECT * FROM web_test_cases WHERE id=?", (case_id,))
        if not case:
            self.log_signal.emit(f"[WARN] 用例 {case_id} 不存在")
            return

        self.log_signal.emit(f"\n--- 用例: {case['name']} ---")

        # 创建结果记录
        result_id = DBManager.insert("test_results", {
            'test_type': 'web',
            'case_id': case_id,
            'case_name': case['name'],
            'status': 'running',
            'browser': self.browser,
            'headless': int(self.headless),
        })

        start_time = time.time()
        steps = DBManager.fetch_all(
            "SELECT * FROM web_steps WHERE case_id=? AND enabled=1 ORDER BY step_order",
            (case_id,)
        )

        all_passed = True
        step_results = []

        for step in steps:
            # 获取定位信息
            locators = DBManager.fetch_all(
                "SELECT * FROM web_step_locators WHERE step_id=?", (step['id'],)
            )
            locator = locators[0] if locators else None

            step_desc = self._get_step_desc(step, locator)
            self.log_signal.emit(f"  步骤 {step['step_order']}: {step_desc}")

            try:
                screenshot_before = None
                success = self._execute_step(step, locator)
                if success:
                    self.log_signal.emit(f"    ✅ 通过")
                    step_results.append({
                        'order': step['step_order'],
                        'desc': step_desc,
                        'status': 'pass',
                        'message': ''
                    })
                else:
                    all_passed = False
                    screenshot_before = self._capture_screenshot()
                    self.log_signal.emit(f"    ❌ 失败")
                    step_results.append({
                        'order': step['step_order'],
                        'desc': step_desc,
                        'status': 'fail',
                        'message': '断言失败'
                    })

            except Exception as e:
                all_passed = False
                error_msg = str(e)
                self.log_signal.emit(f"    ❌ 异常: {error_msg}")
                screenshot_before = self._capture_screenshot()
                step_results.append({
                    'order': step['step_order'],
                    'desc': step_desc,
                    'status': 'fail',
                    'message': error_msg
                })

            # 保存步骤详情
            DBManager.insert("test_result_details", {
                'result_id': result_id,
                'step_order': step['step_order'],
                'step_description': step_desc,
                'status': 'fail' if not step_results[-1]['status'] == 'pass' else 'pass',
                'message': step_results[-1].get('message', ''),
                'screenshot_path': '',  # 截图存数据库中
            })

            # 失败时保存截图
            if screenshot_before:
                detail_id = DBManager.execute(
                    "SELECT MAX(id) FROM test_result_details WHERE result_id=?", (result_id,)
                )
                # 获取刚插入的 ID
                last_detail = DBManager.fetch_one(
                    "SELECT id FROM test_result_details WHERE result_id=? ORDER BY id DESC LIMIT 1",
                    (result_id,)
                )
                if last_detail:
                    DBManager.insert("screenshots", {
                        'result_detail_id': last_detail['id'],
                        'name': f"step_{step['step_order']}_fail",
                        'image_base64': screenshot_before,
                    })

        duration_ms = (time.time() - start_time) * 1000
        status = "pass" if all_passed else "fail"

        DBManager.update("test_results",
                         {'status': status, 'duration_ms': int(duration_ms)},
                         "id=?", (result_id,))

        self.log_signal.emit(f"  结果: {'✅ 通过' if all_passed else '❌ 失败'} ({duration_ms:.0f}ms)")
        return result_id

    def _execute_step(self, step: dict, locator: dict = None) -> bool:
        """执行单个步骤，返回是否成功"""
        action_type = step['action_type']
        input_value = self.variables.resolve(step.get('input_value', ''))
        wait_seconds = step.get('wait_seconds', 0)

        by = None
        loc_value = None
        if locator:
            by = LOCATOR_MAP.get(locator['locator_type'], By.XPATH)
            loc_value = self.variables.resolve(locator['locator_value'])

        if action_type == 'open_url':
            url = self.variables.resolve(input_value or step.get('description', ''))
            if not url.startswith('http://') and not url.startswith('https://'):
                raise ValueError(f"无效的URL: '{url}' — URL必须以 http:// 或 https:// 开头")
            self.driver.get(url)
            return True

        elif action_type == 'click':
            if not (by and loc_value):
                raise ValueError(f"点击操作缺少元素定位信息")
            self._robust_click(by, loc_value, wait_seconds)
            return True

        elif action_type == 'input':
            if not (by and loc_value):
                raise ValueError(f"输入操作缺少元素定位信息")
            elem = self._wait_element(by, loc_value, wait_seconds)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
            elem.clear()
            if input_value:
                elem.send_keys(input_value)
            return True

        elif action_type == 'clear':
            if not (by and loc_value):
                raise ValueError(f"清空操作缺少元素定位信息")
            elem = self._wait_element(by, loc_value, wait_seconds)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
            elem.clear()
            return True

        elif action_type == 'force_wait':
            time.sleep(wait_seconds or float(input_value or 1))
            return True

        elif action_type == 'smart_wait':
            if by and loc_value:
                WebDriverWait(self.driver, wait_seconds or 10).until(
                    EC.presence_of_element_located((by, loc_value))
                )
            return True

        elif action_type == 'switch_window':
            handles = self.driver.window_handles
            try:
                idx = int(input_value) if input_value else -1
                if 0 <= idx < len(handles):
                    self.driver.switch_to.window(handles[idx])
                elif input_value:
                    # 按 title 匹配
                    current = self.driver.current_window_handle
                    for h in handles:
                        self.driver.switch_to.window(h)
                        if input_value in self.driver.title:
                            return True
                    self.driver.switch_to.window(current)
            except Exception:
                pass
            return True

        elif action_type == 'switch_iframe':
            if input_value == 'default':
                self.driver.switch_to.default_content()
            elif by and loc_value:
                iframe = self._wait_element(by, loc_value, wait_seconds)
                self.driver.switch_to.frame(iframe)
            return True

        elif action_type == 'scroll_to':
            if by and loc_value:
                elem = self._wait_element(by, loc_value, wait_seconds)
                self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
            return True

        elif action_type == 'execute_js':
            self.driver.execute_script(input_value)
            return True

        elif action_type == 'screenshot':
            self._capture_screenshot(input_value or "manual")
            return True

        elif action_type == 'assert_text_contains':
            if by and loc_value:
                elem = self._wait_element(by, loc_value, wait_seconds)
                actual = elem.text
                if input_value in actual:
                    return True
                raise AssertionError(f"文本断言失败: 期望包含 '{input_value}', 实际文本 '{actual}'")

        elif action_type == 'assert_visible':
            if by and loc_value:
                elem = self._wait_element(by, loc_value, wait_seconds)
                is_visible = elem.is_displayed()
                expected = input_value.lower() != 'false' if input_value else True
                if is_visible == expected:
                    return True
                raise AssertionError(f"元素可见性断言失败: 期望={expected}, 实际={is_visible}")

        elif action_type == 'assert_exists':
            if by and loc_value:
                try:
                    self.driver.find_element(by, loc_value)
                    exists = True
                except NoSuchElementException:
                    exists = False
                expected = input_value.lower() != 'false' if input_value else True
                if exists == expected:
                    return True
                raise AssertionError(f"元素存在性断言失败: 期望={expected}, 实际={exists}")

        elif action_type == 'extract_variable':
            if by and loc_value and input_value:
                elem = self._wait_element(by, loc_value, wait_seconds)
                text = elem.text or elem.get_attribute('value') or ''
                self.variables.set_extra_var(input_value, text)
                self.log_signal.emit(f"    📌 提取变量: {input_value} = '{text[:50]}...'")
            return True

        return True

    def _wait_element(self, by, value, timeout=10):
        """智能等待元素出现（DOM 中存在）"""
        return WebDriverWait(self.driver, timeout or 10).until(
            EC.presence_of_element_located((by, value))
        )

    def _wait_clickable(self, by, value, timeout=10):
        """等待元素可被点击（可见 + 启用）"""
        return WebDriverWait(self.driver, timeout or 10).until(
            EC.element_to_be_clickable((by, value))
        )

    def _robust_click(self, by, value, timeout=10, retries=2):
        """健壮的点击操作 — 四层降级 + 点击后等待页面稳定

        Args:
            by: Selenium By 定位方式
            value: 定位值
            timeout: 等待超时秒数
            retries: 重试次数（含首次）
        """
        last_exception = None
        for attempt in range(retries):
            elem = None
            try:
                # 方式一：等待元素可点击，滚动到可视区域，原生点击
                elem = self._wait_clickable(by, value, timeout)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", elem
                )
                elem.click()
                self.log_signal.emit(f"      [点击] 原生 WebDriver click")

            except ElementClickInterceptedException:
                # 方式二：被遮挡 → JS 强制点击（可能不触发导航，所以要验证）
                if elem is None:
                    elem = self._wait_element(by, value, timeout)
                self.driver.execute_script("arguments[0].click();", elem)
                self.log_signal.emit(f"      [点击] 元素被遮挡，降级 JS click")

            except (StaleElementReferenceException, TimeoutException) as e:
                last_exception = e
                time.sleep(1)
                continue

            except WebDriverException as e:
                last_exception = e
                self.log_signal.emit(f"      [点击] WebDriver异常，尝试JS: {str(e)[:60]}")
                try:
                    elem = self._wait_element(by, value, timeout)
                    self.driver.execute_script("arguments[0].click();", elem)
                except Exception:
                    break
                return

            # ---------- 点击后稳定等待 ----------
            try:
                # 等待页面 DOM 稳定（不再有 DOM 变化持续 0.5 秒）
                self.driver.execute_script(
                    "return new Promise(resolve => {"
                    "  let timer = null;"
                    "  const observer = new MutationObserver(() => {"
                    "    clearTimeout(timer);"
                    "    timer = setTimeout(() => { observer.disconnect(); resolve(true); }, 500);"
                    "  });"
                    "  observer.observe(document.body, {childList: true, subtree: true, attributes: false});"
                    "  setTimeout(() => { observer.disconnect(); resolve(false); }, 3000);"
                    "})"
                )
            except Exception:
                time.sleep(1)

            return  # 点击成功

        raise last_exception or RuntimeError(f"点击失败: {by}={value}，已重试{retries}次")

    # 需要使用元素定位的操作类型
    LOCATOR_ACTIONS = {'click', 'input', 'clear', 'smart_wait', 'switch_iframe',
                       'scroll_to', 'assert_text_contains', 'assert_visible',
                       'assert_exists', 'extract_variable'}

    def _get_step_desc(self, step: dict, locator: dict = None) -> str:
        """获取步骤描述文本"""
        action_labels = {
            'open_url': '打开 URL',
            'click': '点击元素',
            'input': '输入文本',
            'clear': '清空输入',
            'force_wait': '强制等待',
            'smart_wait': '智能等待',
            'switch_window': '切换窗口',
            'switch_iframe': '切换 IFrame',
            'scroll_to': '滚动到元素',
            'execute_js': '执行 JS',
            'screenshot': '截图',
            'assert_text_contains': '断言-文本包含',
            'assert_visible': '断言-元素可见',
            'assert_exists': '断言-元素存在',
            'extract_variable': '提取变量',
        }
        action_type = step.get('action_type', '')
        label = action_labels.get(action_type, action_type)
        detail = ""
        # 只有需要元素定位的操作才显示定位信息
        if action_type in self.LOCATOR_ACTIONS and locator:
            detail = f" [{locator['locator_type']}: {locator['locator_value'][:40]}]"
        if step.get('input_value'):
            if action_type == 'open_url':
                detail += f" → {step['input_value'][:60]}"
            else:
                detail += f" => '{step['input_value'][:30]}'"
        return f"{label}{detail}"

    def _capture_screenshot(self, name: str = "") -> str:
        """截取当前页面并返回 Base64 编码"""
        try:
            if self.driver:
                b64 = base64.b64encode(self.driver.get_screenshot_as_png()).decode('utf-8')
                self.screenshots.append((name or f"screenshot_{len(self.screenshots)}", b64))
                return b64
        except Exception:
            pass
        return ""
