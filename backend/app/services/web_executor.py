"""Web UI 执行器 — 步骤执行逻辑搬自旧项目 app/engine/web_runner.py。

剥掉 QThread 外壳和 DBManager，改成无状态函数，与 services/api_executor.py 的
execute_case() 保持同一心智模型：传入「用例 + 环境」，返回一个可以直接存进
execution.result_json 的 dict。

相对旧实现修掉三个 bug：
1. 旧 _capture_screenshot() 里 self.screenshots 从未初始化，AttributeError 被
   except Exception: pass 吞掉 —— 失败自动截图从来没生效过；
2. 旧 _execute_step() 末尾无条件 return True，smart_wait / scroll_to / 三个断言 /
   extract_variable / switch_iframe 在缺少定位信息时静默「通过」（假绿）；
3. 旧 switch_window() 整段 except: pass，窗口没切成功也无从知晓。

另按 models/execution.py 的约定，截图改成落盘 + 返回相对路径，不再塞 Base64。
"""
import logging
import threading
import time
from pathlib import Path

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.config import settings
from app.services.browser_manager import create_driver
from app.services.variable_resolver import VariableResolver

logger = logging.getLogger(__name__)

# 8 种定位方式（与旧 web_runner.LOCATOR_MAP 逐字一致，前端 LOCATOR_TYPES 同源）
LOCATOR_MAP = {
    "id": By.ID,
    "name": By.NAME,
    "class_name": By.CLASS_NAME,
    "tag_name": By.TAG_NAME,
    "css_selector": By.CSS_SELECTOR,
    "xpath": By.XPATH,
    "link_text": By.LINK_TEXT,
    "partial_link_text": By.PARTIAL_LINK_TEXT,
}

# 8 种定位方式的中文标签。与 ACTION_LABELS 一样是「给前端看」的：
# /api/web/status 会把它和 ACTION_LABELS 一起下发，前端下拉直接用，
# 免得前后端各写一份、日后改了枚举悄悄漂移。
LOCATOR_LABELS = {
    "id": "ID",
    "name": "Name",
    "class_name": "Class Name",
    "tag_name": "Tag Name",
    "css_selector": "CSS Selector",
    "xpath": "XPath",
    "link_text": "链接文本",
    "partial_link_text": "部分链接文本",
}

# 需要元素定位的 10 种操作。其余 5 种（open_url / force_wait / switch_window /
# execute_js / screenshot）不看定位信息。
LOCATOR_ACTIONS = {
    "click", "input", "clear", "smart_wait", "switch_iframe", "scroll_to",
    "assert_text_contains", "assert_visible", "assert_exists", "extract_variable",
}

# 15 种操作的中文标签，抄自旧 _get_step_desc()
ACTION_LABELS = {
    "open_url": "打开 URL",
    "click": "点击元素",
    "input": "输入文本",
    "clear": "清空输入",
    "force_wait": "强制等待",
    "smart_wait": "智能等待",
    "switch_window": "切换窗口",
    "switch_iframe": "切换 IFrame",
    "scroll_to": "滚动到元素",
    "execute_js": "执行 JS",
    "screenshot": "截图",
    "assert_text_contains": "断言-文本包含",
    "assert_visible": "断言-元素可见",
    "assert_exists": "断言-元素存在",
    "extract_variable": "提取变量",
}

DEFAULT_STEP_WAIT = 10        # 步骤没写 wait_seconds 时的元素等待秒数（沿用旧代码的 10）
DEFAULT_CASE_TIMEOUT = 300    # 整条用例的保险丝，防止把 worker 占死
MAX_WAIT_SECONDS = 60         # 单步强制等待上限
MAX_CLICKS_RETRY = 2

# 限制同时拉起的浏览器数量：前端连点多次时，不会一次开出一堆 Chrome
_BROWSER_SEMAPHORE = threading.Semaphore(2)


def _describe(step: dict) -> str:
    """步骤描述文本，抄自旧 _get_step_desc()。

    刻意用原始的 input_value（含 ${变量} 占位符），与旧实现一致 ——
    解析后的值可能包含密码，不适合写进报告。
    """
    action = str(step.get("action_type") or "")
    label = ACTION_LABELS.get(action, action)
    detail = ""

    if action in LOCATOR_ACTIONS:
        locator_type = str(step.get("locator_type") or "")
        locator_value = str(step.get("locator_value") or "")
        if locator_type and locator_value:
            detail += f" [{locator_type}: {locator_value[:40]}]"

    raw = str(step.get("input_value") or "")
    if raw:
        if action == "open_url":
            detail += f" → {raw[:60]}"
        else:
            detail += f" => '{raw[:30]}'"

    return f"{label}{detail}"


def _clamp_wait(seconds) -> float:
    try:
        value = float(seconds or 0)
    except (TypeError, ValueError):
        value = 0.0
    return min(max(value, 0.0), float(MAX_WAIT_SECONDS))


class _StepRunner:
    """一条 Web 用例的步骤执行器。

    对外是私有的：execute_case() 负责建/关 driver，本类只管把一串步骤跑完。
    截图列表在 __init__ 里初始化 —— 这正是旧实现漏掉、导致失败截图从未生效的那一步。
    """

    def __init__(self, driver, resolver: VariableResolver,
                 screenshot_dir: Path, screenshot_root: Path):
        self.driver = driver
        self.resolver = resolver
        self.screenshot_dir = screenshot_dir
        self.screenshot_root = screenshot_root
        self.extracted: dict = {}
        self.screenshot_errors: list[str] = []
        self._pending_shots: list[str] = []  # 当前步骤的截图，run_step 收尾时挂到结果上

    # ---------- 元素等待 / 点击 ----------

    def _wait_element(self, by, value, wait_seconds=0):
        """等待元素出现在 DOM 中"""
        return WebDriverWait(self.driver, wait_seconds or DEFAULT_STEP_WAIT).until(
            EC.presence_of_element_located((by, value))
        )

    def _wait_clickable(self, by, value, wait_seconds=0):
        """等待元素可点击（可见 + 启用）"""
        return WebDriverWait(self.driver, wait_seconds or DEFAULT_STEP_WAIT).until(
            EC.element_to_be_clickable((by, value))
        )

    def _robust_click(self, by, value, wait_seconds=0):
        """健壮点击 —— 四层降级 + 点击后等待 DOM 稳定，整段搬自旧实现。

        1. 原生 click；2. 被遮挡 → JS click；3. 元素失效/超时 → 重试；
        4. WebDriver 异常 → 再试一次 JS click。
        """
        last_error = None
        for _ in range(MAX_CLICKS_RETRY):
            elem = None
            try:
                elem = self._wait_clickable(by, value, wait_seconds)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", elem
                )
                elem.click()
            except ElementClickInterceptedException:
                if elem is None:
                    elem = self._wait_element(by, value, wait_seconds)
                self.driver.execute_script("arguments[0].click();", elem)
            except (StaleElementReferenceException, TimeoutException) as e:
                last_error = e
                time.sleep(1)
                continue
            except WebDriverException as e:
                last_error = e
                try:
                    elem = self._wait_element(by, value, wait_seconds)
                    self.driver.execute_script("arguments[0].click();", elem)
                except Exception:
                    break
                return

            # 点击后等 DOM 不再变化（连续 0.5s 无变更即视为稳定，最长 3s）
            try:
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
            return

        raise last_error or RuntimeError(f"点击失败: {by}={value}，已重试 {MAX_CLICKS_RETRY} 次")

    # ---------- 断言 / 提取 ----------

    def _capture_screenshot(self, name: str, order: int) -> str:
        """截图落盘，返回相对 screenshot_root 的 POSIX 路径；失败返回空串并记录原因。

        修掉旧实现的三处问题：列表未初始化（根因）、异常被静默吞掉、返回 Base64。
        """
        if not self.driver:
            return ""
        try:
            png = self.driver.get_screenshot_as_png()
        except Exception as e:  # 记下来但不让截图失败拖垮用例
            self.screenshot_errors.append(f"step {order} 截图失败: {type(e).__name__}: {e}")
            logger.warning("截图失败 step=%s: %s", order, e)
            return ""

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in (name or "shot"))
        path = self.screenshot_dir / f"step_{order:02d}_{safe_name}_{timestamp}.png"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png)
            return path.relative_to(self.screenshot_root).as_posix()
        except (OSError, ValueError) as e:
            self.screenshot_errors.append(f"step {order} 截图保存失败: {e}")
            logger.warning("截图保存失败 step=%s: %s", order, e)
            return ""

    # ---------- 单步执行 ----------

    def run_step(self, step: dict, index: int) -> dict:
        """执行一个步骤，返回结果 dict。任何异常都收敛成 status=fail + message。"""
        action = str(step.get("action_type") or "")
        order = step.get("step_order") or index + 1
        self._pending_shots = []

        result = {
            "step_order": order,
            "action_type": action,
            "desc": _describe(step),
            "status": "pass",
            "message": "",
            "duration_ms": 0,
            "screenshots": [],
        }

        start = time.time()
        try:
            self._execute(step, action, order)
        except AssertionError as e:
            result["status"] = "fail"
            result["message"] = str(e)
            self._snap(f"{action}_fail", order)
        except Exception as e:
            result["status"] = "fail"
            result["message"] = f"{type(e).__name__}: {str(e)[:300]}"
            self._snap(f"{action}_error", order)
        result["duration_ms"] = int((time.time() - start) * 1000)
        result["screenshots"] = self._pending_shots
        return result

    def _snap(self, name: str, order: int) -> None:
        """截图并挂到当前步骤上。截图失败只记录，不影响步骤结果。"""
        shot = self._capture_screenshot(name, order)
        if shot:
            self._pending_shots.append(shot)

    def _resolve_locator(self, step: dict, action: str, needs_locator: bool) -> tuple:
        """解析定位信息。需要定位却缺失时直接报错 —— 这里是「假绿」bug 的封堵点。"""
        locator_type = str(step.get("locator_type") or "").strip()
        locator_value = self.resolver.resolve(str(step.get("locator_value") or "").strip())

        if locator_type and locator_type not in LOCATOR_MAP:
            raise ValueError(
                f"不支持的定位方式: {locator_type}（可用: {', '.join(LOCATOR_MAP)}）"
            )
        if needs_locator and not (locator_type and locator_value):
            raise ValueError(
                f"{ACTION_LABELS.get(action, action)} 缺少元素定位信息"
                "（需要同时填写定位方式和定位值）"
            )
        return (LOCATOR_MAP[locator_type] if locator_type else None), locator_value

    def _execute(self, step: dict, action: str, order: int) -> None:
        """执行单个步骤。抛异常即表示该步骤失败。"""
        input_value = self.resolver.resolve(str(step.get("input_value") or ""))
        # switch_iframe 填 default 表示「退回主文档」，此时不需要定位信息
        needs_locator = action in LOCATOR_ACTIONS and not (
            action == "switch_iframe" and input_value == "default"
        )
        by, locator_value = self._resolve_locator(step, action, needs_locator)
        wait_seconds = step.get("wait_seconds") or 0

        if action == "open_url":
            # 旧实现允许用 description 兜底，保留这个兼容写法
            url = input_value or self.resolver.resolve(str(step.get("description") or ""))
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"无效的 URL: '{url}' — 必须以 http:// 或 https:// 开头")
            self.driver.get(url)

        elif action == "click":
            self._robust_click(by, locator_value, wait_seconds)

        elif action == "input":
            elem = self._wait_element(by, locator_value, wait_seconds)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
            elem.clear()
            if input_value:
                elem.send_keys(input_value)

        elif action == "clear":
            elem = self._wait_element(by, locator_value, wait_seconds)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
            elem.clear()

        elif action == "force_wait":
            seconds = _clamp_wait(wait_seconds or input_value or 1)
            time.sleep(seconds)

        elif action == "smart_wait":
            self._wait_element(by, locator_value, wait_seconds)

        elif action == "switch_window":
            self._switch_window(input_value)

        elif action == "switch_iframe":
            if input_value == "default":
                self.driver.switch_to.default_content()
            else:
                self.driver.switch_to.frame(self._wait_element(by, locator_value, wait_seconds))

        elif action == "scroll_to":
            elem = self._wait_element(by, locator_value, wait_seconds)
            self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)

        elif action == "execute_js":
            if not input_value.strip():
                raise ValueError("执行 JS 操作缺少脚本内容")
            self.driver.execute_script(input_value)

        elif action == "screenshot":
            self._snap(input_value or "manual", order)

        elif action == "assert_text_contains":
            actual = self._wait_element(by, locator_value, wait_seconds).text
            if input_value not in actual:
                raise AssertionError(f"文本断言失败: 期望包含 '{input_value}'，实际文本 '{actual}'")

        elif action == "assert_visible":
            is_visible = self._wait_element(by, locator_value, wait_seconds).is_displayed()
            expected = input_value.lower() != "false" if input_value else True
            if is_visible != expected:
                raise AssertionError(f"元素可见性断言失败: 期望={expected}，实际={is_visible}")

        elif action == "assert_exists":
            try:
                self.driver.find_element(by, locator_value)
                exists = True
            except NoSuchElementException:
                exists = False
            expected = input_value.lower() != "false" if input_value else True
            if exists != expected:
                raise AssertionError(f"元素存在性断言失败: 期望={expected}，实际={exists}")

        elif action == "extract_variable":
            if not input_value:
                raise ValueError("提取变量操作缺少变量名")
            elem = self._wait_element(by, locator_value, wait_seconds)
            text = elem.text or elem.get_attribute("value") or ""
            self.resolver.set_extra_var(input_value, text)
            self.extracted[input_value] = text

        else:
            raise ValueError(
                f"不支持的操作类型: {action}（可用: {', '.join(ACTION_LABELS)}）"
            )

    def _switch_window(self, input_value: str) -> None:
        """切换窗口。旧实现整段 except: pass，这里改成切不中就说清楚。"""
        handles = self.driver.window_handles
        if not input_value:
            raise ValueError("切换窗口操作需要填写窗口序号或标题关键字")

        try:
            index = int(input_value)
        except ValueError:
            index = None

        if index is not None:
            if 0 <= index < len(handles):
                self.driver.switch_to.window(handles[index])
                return
            raise ValueError(f"窗口序号 {index} 超出范围（当前共 {len(handles)} 个窗口）")

        current = self.driver.current_window_handle
        for handle in handles:
            self.driver.switch_to.window(handle)
            if input_value in self.driver.title:
                return
        self.driver.switch_to.window(current)
        raise ValueError(f"没有标题包含 '{input_value}' 的窗口")


def execute_case(case: dict, environment: dict | None = None, browser: str = "chrome",
                 headless: bool = True, timeout: int = DEFAULT_CASE_TIMEOUT,
                 driver=None, screenshot_dir: str | None = None,
                 screenshot_root: str | None = None) -> dict:
    """执行一条 Web UI 用例。

    case:        TestCase 的字段字典（含 steps_json）
    environment: 环境字典（含 base_url / variables_json），供 ${变量} 解析
    driver:      传入则复用（供将来的场景串联/批量执行），不传则自建并在结束时关闭

    返回可直接存进 execution.result_json 的结构。status 取 pass / fail / error：
    驱动起不来、没有步骤等「跑都没跑成」的情况记 error，与步骤断言失败区分开。
    """
    environment = environment or {}
    steps = [s for s in (case.get("steps_json") or []) if s.get("enabled", True)]

    started = time.time()
    result = {
        "status": "error",
        "duration_ms": 0,
        "browser": browser,
        "headless": bool(headless),
        "error_msg": "",
        "extracted": {},
        "extract_errors": [],
        "screenshot_errors": [],
        "steps": [],
    }

    if not steps:
        result["error_msg"] = "该用例没有可执行的 Web 步骤"
        return result

    own_driver = driver is None
    if own_driver:
        # 限量信号量只在自建 driver 时占用，避免与外部传入的 driver 抢配额
        _BROWSER_SEMAPHORE.acquire()
        try:
            driver = create_driver(browser, headless)
        except Exception as e:
            result["error_msg"] = f"浏览器启动失败: {type(e).__name__}: {str(e)[:300]}"
            result["duration_ms"] = int((time.time() - started) * 1000)
            _BROWSER_SEMAPHORE.release()
            return result

    shot_dir = Path(screenshot_dir or settings.screenshot_dir)
    shot_root = Path(screenshot_root or settings.report_dir)
    resolver = VariableResolver(global_vars=environment.get("variables_json") or {})
    runner = _StepRunner(driver, resolver, shot_dir, shot_root)

    try:
        deadline = time.time() + max(int(timeout or DEFAULT_CASE_TIMEOUT), 30)
        for index, step in enumerate(steps):
            if time.time() > deadline:
                result["steps"].append({
                    "step_order": step.get("step_order") or index + 1,
                    "action_type": step.get("action_type") or "",
                    "desc": _describe(step),
                    "status": "fail",
                    "message": f"超出用例整体超时（{timeout}s），后续步骤未执行",
                    "duration_ms": 0,
                    "screenshots": [],
                })
                break
            result["steps"].append(runner.run_step(step, index))
    except Exception as e:  # driver 级别崩溃，兜底成 error
        result["error_msg"] = f"执行中断: {type(e).__name__}: {str(e)[:300]}"
        logger.exception("Web 用例执行中断")
    finally:
        if own_driver and driver is not None:
            try:
                driver.quit()
            except Exception:
                logger.warning("关闭浏览器失败", exc_info=True)
            _BROWSER_SEMAPHORE.release()

    result["extracted"] = runner.extracted
    # extract_errors 与 api_executor 同名同义（响应体提取失败原因），Web 侧没有这个概念；
    # 截图失败原因单独放 screenshot_errors，别串到「变量」页签里去。
    result["extract_errors"] = []
    result["screenshot_errors"] = runner.screenshot_errors
    result["duration_ms"] = int((time.time() - started) * 1000)

    if result["error_msg"]:
        result["status"] = "error"
    elif result["steps"] and all(s["status"] == "pass" for s in result["steps"]):
        result["status"] = "pass"
    else:
        result["status"] = "fail"

    return result
