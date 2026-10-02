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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

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

# ---------- 操作规格：每个操作声明自己需要哪些字段 ----------
#
# 这份声明是前后端的唯一事实来源：/api/web/status 原样下发给前端渲染表单，
# 前端不再自己判断「这个操作要不要输入框」。此前前端用 NO_INPUT_ACTIONS /
# WAIT_ACTIONS 两个 Set 硬编码，与后端的 needs_locator 各管一摊 ——
# 正是 Day 3 栽过三次的「前后端字段认知漂移」隐患。
#
# 字段槽位（name）与 WebStep 的字段一一对应：
#   locator        → locator_type / locator_value
#   target_locator → target_locator_type / target_locator_value
#   value          → input_value
#   value2         → input_value2
#   wait           → wait_seconds
F_LOCATOR = "locator"
F_TEXT = "text"
F_TEXTAREA = "textarea"
F_SELECT = "select"
F_NUMBER = "number"


def _field(name, label, ftype=F_TEXT, **extra):
    return {"name": name, "label": label, "type": ftype, **extra}


LOCATOR_FIELD = _field("locator", "元素定位", F_LOCATOR, required=True)
TARGET_LOCATOR_FIELD = _field("target_locator", "目标元素", F_LOCATOR, required=True)

SELECT_BY_OPTIONS = [
    {"value": "label", "label": "按可见文本"},
    {"value": "value", "label": "按 value 属性"},
    {"value": "index", "label": "按下标（从 0 起）"},
]

TRUE_FALSE_HINT = "true / false（留空按 true）"

# 31 种操作，按 group 分组；dict 顺序即前端下拉顺序。
ACTION_SPEC = {
    # ---------- 导航 ----------
    "open_url": {
        "label": "打开 URL",
        "group": "导航",
        "fields": [_field("value", "网址", placeholder="完整 URL，可含 ${变量}，如 ${base_url}/login", required=True)],
    },
    "refresh": {"label": "刷新页面", "group": "导航", "fields": []},
    "back": {"label": "浏览器后退", "group": "导航", "fields": []},
    "switch_window": {
        "label": "切换窗口",
        "group": "导航",
        "fields": [_field("value", "窗口", placeholder="窗口序号（从 0 开始）或标题关键字", required=True)],
    },
    "switch_iframe": {
        "label": "切换 IFrame",
        "group": "导航",
        "fields": [
            LOCATOR_FIELD,
            _field("value", "退回主文档", placeholder="填 default 退回主文档；留空则按左侧定位切入"),
        ],
    },

    # ---------- 鼠标 ----------
    "click": {"label": "点击元素", "group": "鼠标", "fields": [LOCATOR_FIELD]},
    "double_click": {"label": "双击元素", "group": "鼠标", "fields": [LOCATOR_FIELD]},
    "context_click": {"label": "右键点击", "group": "鼠标", "fields": [LOCATOR_FIELD]},
    "hover": {"label": "鼠标悬停", "group": "鼠标", "fields": [LOCATOR_FIELD]},
    "drag_and_drop": {
        "label": "拖拽元素",
        "group": "鼠标",
        "fields": [LOCATOR_FIELD, TARGET_LOCATOR_FIELD],
    },

    # ---------- 表单 ----------
    "input": {
        "label": "输入文本",
        "group": "表单",
        "fields": [LOCATOR_FIELD, _field("value", "输入值", placeholder="要输入的文本，可含 ${变量}")],
    },
    "clear": {"label": "清空输入", "group": "表单", "fields": [LOCATOR_FIELD]},
    "select_option": {
        "label": "下拉框选择",
        "group": "表单",
        "fields": [
            LOCATOR_FIELD,
            _field("value", "选择方式", F_SELECT, options=SELECT_BY_OPTIONS, default="label"),
            _field("value2", "选项值", placeholder="要选中的文本 / value / 下标", required=True),
        ],
    },
    "upload_file": {
        "label": "上传文件",
        "group": "表单",
        "fields": [
            LOCATOR_FIELD,
            _field("value", "文件路径", placeholder="本机绝对路径，可含 ${变量}", required=True),
        ],
    },
    "press_key": {
        "label": "键盘按键",
        "group": "表单",
        "fields": [
            _field("value", "按键", placeholder="ENTER / TAB / ESCAPE / BACKSPACE，发送到当前焦点元素", required=True),
        ],
    },

    # ---------- 弹窗 ----------
    "alert_accept": {"label": "弹窗确认", "group": "弹窗", "fields": []},
    "alert_dismiss": {
        "label": "弹窗取消",
        "group": "弹窗",
        "fields": [_field("value", "prompt 输入", placeholder="仅 prompt 弹窗需要，普通弹窗留空")],
    },

    # ---------- 等待 ----------
    "force_wait": {"label": "强制等待", "group": "等待", "fields": [_field("wait", "等待秒数", F_NUMBER)]},
    "smart_wait": {
        "label": "智能等待",
        "group": "等待",
        "fields": [LOCATOR_FIELD, _field("wait", "超时秒数", F_NUMBER)],
    },
    "wait_invisible": {
        "label": "等待元素消失",
        "group": "等待",
        "fields": [LOCATOR_FIELD, _field("wait", "超时秒数", F_NUMBER)],
    },

    # ---------- 滚动 ----------
    "scroll_to": {"label": "滚动到元素", "group": "滚动", "fields": [LOCATOR_FIELD]},
    "scroll_to_bottom": {"label": "滚动到页面底部", "group": "滚动", "fields": []},

    # ---------- 断言 ----------
    "assert_text_contains": {
        "label": "断言-文本包含",
        "group": "断言",
        "fields": [LOCATOR_FIELD, _field("value", "期望文本", placeholder="期望包含的文本，可含 ${变量}", required=True)],
    },
    "assert_visible": {
        "label": "断言-元素可见",
        "group": "断言",
        "fields": [LOCATOR_FIELD, _field("value", "期望可见", placeholder=TRUE_FALSE_HINT)],
    },
    "assert_exists": {
        "label": "断言-元素存在",
        "group": "断言",
        "fields": [LOCATOR_FIELD, _field("value", "期望存在", placeholder=TRUE_FALSE_HINT)],
    },
    "assert_url_contains": {
        "label": "断言-URL 包含",
        "group": "断言",
        "fields": [_field("value", "期望 URL 片段", placeholder="如 /dashboard", required=True)],
    },
    "assert_element_count": {
        "label": "断言-元素数量",
        "group": "断言",
        "fields": [LOCATOR_FIELD, _field("value", "期望数量", placeholder="整数，如 3", required=True)],
    },
    "assert_attribute": {
        "label": "断言-元素属性",
        "group": "断言",
        "fields": [
            LOCATOR_FIELD,
            _field("value", "属性名", placeholder="如 placeholder / disabled / class", required=True),
            _field("value2", "期望值", placeholder="留空则只校验该属性存在"),
        ],
    },

    # ---------- 其他 ----------
    "execute_js": {
        "label": "执行 JS",
        "group": "其他",
        "fields": [_field("value", "脚本", F_TEXTAREA, placeholder="要执行的 JS，如 window.scrollTo(0, 0);", required=True)],
    },
    "screenshot": {
        "label": "截图",
        "group": "其他",
        "fields": [_field("value", "文件名", placeholder="截图文件名（可选）")],
    },
    "extract_variable": {
        "label": "提取变量",
        "group": "其他",
        "fields": [
            LOCATOR_FIELD,
            _field("value", "变量名", placeholder="如 welcome_text", required=True),
        ],
    },
}

# 标签与「需要定位的操作」从规格里派生，不再各写一份
ACTION_LABELS = {key: spec["label"] for key, spec in ACTION_SPEC.items()}
ACTION_GROUPS = list(dict.fromkeys(spec["group"] for spec in ACTION_SPEC.values()))
LOCATOR_ACTIONS = {
    key for key, spec in ACTION_SPEC.items()
    if any(f["name"] == F_LOCATOR for f in spec["fields"])
}

# 键盘按键名 → Selenium Keys 的映射（大小写不敏感，未命中时按原字符串发送）
_KEY_ALIASES = {
    "ENTER": "ENTER", "RETURN": "ENTER",
    "TAB": "TAB",
    "ESCAPE": "ESCAPE", "ESC": "ESCAPE",
    "BACKSPACE": "BACK_SPACE", "BACK_SPACE": "BACK_SPACE",
    "DELETE": "DELETE",
    "SPACE": "SPACE",
    "UP": "ARROW_UP", "ARROW_UP": "ARROW_UP",
    "DOWN": "ARROW_DOWN", "ARROW_DOWN": "ARROW_DOWN",
    "LEFT": "ARROW_LEFT", "ARROW_LEFT": "ARROW_LEFT",
    "RIGHT": "ARROW_RIGHT", "ARROW_RIGHT": "ARROW_RIGHT",
    "PAGE_UP": "PAGE_UP", "PAGE_DOWN": "PAGE_DOWN",
    "HOME": "HOME", "END": "END",
    "F5": "F5",
}

DEFAULT_STEP_WAIT = 10        # 步骤没写 wait_seconds 时的元素等待秒数（沿用旧代码的 10）
DEFAULT_CASE_TIMEOUT = 300    # 整条用例的保险丝，防止把 worker 占死
MAX_WAIT_SECONDS = 60         # 单步强制等待上限
MAX_CLICKS_RETRY = 2

# 限制同时拉起的浏览器数量：前端连点多次时，不会一次开出一堆 Chrome
_BROWSER_SEMAPHORE = threading.Semaphore(2)


def _locator_text(step: dict, prefix: str = "") -> str:
    """把一对定位信息渲染成 `[id: login-btn]`；prefix 传 "target_" 时取第二个元素。"""
    locator_type = str(step.get(f"{prefix}locator_type") or "")
    locator_value = str(step.get(f"{prefix}locator_value") or "")
    if locator_type and locator_value:
        return f"[{locator_type}: {locator_value[:40]}]"
    return ""


def _describe(step: dict) -> str:
    """步骤描述文本，抄自旧 _get_step_desc()。

    刻意用原始的 input_value（含 ${变量} 占位符），与旧实现一致 ——
    解析后的值可能包含密码，不适合写进报告。
    """
    action = str(step.get("action_type") or "")
    label = ACTION_LABELS.get(action, action)
    detail = ""

    main_locator = _locator_text(step)
    if main_locator:
        detail += f" {main_locator}"

    target_locator = _locator_text(step, "target_")
    if target_locator:
        detail += f" → {target_locator}"

    raw = str(step.get("input_value") or "")
    if raw:
        if action == "open_url":
            detail += f" → {raw[:60]}"
        else:
            detail += f" => '{raw[:30]}'"

    second = str(step.get("input_value2") or "")
    if second:
        detail += f" / '{second[:30]}'"

    return f"{label}{detail}"


def _clamp_wait(seconds) -> float:
    try:
        value = float(seconds or 0)
    except (TypeError, ValueError):
        value = 0.0
    return min(max(value, 0.0), float(MAX_WAIT_SECONDS))


def _resolve_key(raw: str):
    """把 'ENTER' / 'esc' 这类按键名翻成 Selenium Keys；单字符原样返回。"""
    name = str(raw or "").strip()
    if not name:
        raise ValueError("键盘按键操作缺少按键名")
    target = _KEY_ALIASES.get(name.upper())
    if target:
        return getattr(Keys, target)
    return name


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

    def _resolve_pair(self, step: dict, prefix: str, needed: bool, label: str) -> tuple:
        """解析一对定位信息。需要定位却缺失时直接报错 —— 这里是「假绿」bug 的封堵点。

        prefix 传 "" 取主元素，传 "target_" 取第二元素（拖拽的目标）。
        """
        locator_type = str(step.get(f"{prefix}locator_type") or "").strip()
        locator_value = self.resolver.resolve(str(step.get(f"{prefix}locator_value") or "").strip())

        if locator_type and locator_type not in LOCATOR_MAP:
            raise ValueError(
                f"不支持的定位方式: {locator_type}（可用: {', '.join(LOCATOR_MAP)}）"
            )
        if needed and not (locator_type and locator_value):
            raise ValueError(
                f"{label} 缺少元素定位信息（需要同时填写定位方式和定位值）"
            )
        return (LOCATOR_MAP[locator_type] if locator_type else None), locator_value

    def _resolve_locator(self, step: dict, action: str, needs_locator: bool) -> tuple:
        return self._resolve_pair(step, "", needs_locator, ACTION_LABELS.get(action, action))

    def _resolve_target_locator(self, step: dict, action: str) -> tuple:
        return self._resolve_pair(
            step, "target_", True, f"{ACTION_LABELS.get(action, action)}的目标元素"
        )

    def _build_alert(self, wait_seconds=0):
        """等弹窗出现。注意：native alert 不处理会卡死整个会话，所以宁可等也别硬取。"""
        try:
            return WebDriverWait(
                self.driver, wait_seconds or DEFAULT_STEP_WAIT
            ).until(EC.alert_is_present())
        except TimeoutException as e:
            raise ValueError("等不到弹出框（alert / confirm / prompt）") from e

    def _scroll_into_view(self, elem) -> None:
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)

    def _execute(self, step: dict, action: str, order: int) -> None:
        """执行单个步骤。抛异常即表示该步骤失败。"""
        if action not in ACTION_SPEC:
            raise ValueError(
                f"不支持的操作类型: {action}（可用: {', '.join(ACTION_LABELS)}）"
            )

        input_value = self.resolver.resolve(str(step.get("input_value") or ""))
        input_value2 = self.resolver.resolve(str(step.get("input_value2") or ""))
        # switch_iframe 填 default 表示「退回主文档」，此时不需要定位信息
        needs_locator = action in LOCATOR_ACTIONS and not (
            action == "switch_iframe" and input_value == "default"
        )
        by, locator_value = self._resolve_locator(step, action, needs_locator)
        wait_seconds = step.get("wait_seconds") or 0

        # ---------- 导航 ----------
        if action == "open_url":
            # 旧实现允许用 description 兜底，保留这个兼容写法
            url = input_value or self.resolver.resolve(str(step.get("description") or ""))
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"无效的 URL: '{url}' — 必须以 http:// 或 https:// 开头")
            self.driver.get(url)

        elif action == "refresh":
            self.driver.refresh()

        elif action == "back":
            self.driver.back()

        elif action == "switch_window":
            self._switch_window(input_value)

        elif action == "switch_iframe":
            if input_value == "default":
                self.driver.switch_to.default_content()
            else:
                self.driver.switch_to.frame(self._wait_element(by, locator_value, wait_seconds))

        # ---------- 鼠标 ----------
        elif action == "click":
            self._robust_click(by, locator_value, wait_seconds)

        elif action in ("double_click", "context_click"):
            elem = self._wait_clickable(by, locator_value, wait_seconds)
            self._scroll_into_view(elem)
            actions = ActionChains(self.driver)
            if action == "double_click":
                actions.double_click(elem).perform()
            else:
                actions.context_click(elem).perform()
                # 右键菜单会盖住后续操作，顺手按 ESC 关掉
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()

        elif action == "hover":
            elem = self._wait_element(by, locator_value, wait_seconds)
            self._scroll_into_view(elem)
            ActionChains(self.driver).move_to_element(elem).perform()

        elif action == "drag_and_drop":
            source = self._wait_element(by, locator_value, wait_seconds)
            target_by, target_value = self._resolve_target_locator(step, action)
            target = self._wait_element(target_by, target_value, wait_seconds)
            self._scroll_into_view(source)
            ActionChains(self.driver).drag_and_drop(source, target).perform()

        # ---------- 表单 ----------
        elif action == "input":
            elem = self._wait_element(by, locator_value, wait_seconds)
            self._scroll_into_view(elem)
            elem.clear()
            if input_value:
                elem.send_keys(input_value)

        elif action == "clear":
            elem = self._wait_element(by, locator_value, wait_seconds)
            self._scroll_into_view(elem)
            elem.clear()

        elif action == "select_option":
            if not input_value2:
                raise ValueError("下拉框选择缺少选项值")
            select = Select(self._wait_element(by, locator_value, wait_seconds))
            how = (input_value or "label").strip().lower()
            try:
                if how == "label":
                    select.select_by_visible_text(input_value2)
                elif how == "value":
                    select.select_by_value(input_value2)
                elif how == "index":
                    select.select_by_index(int(input_value2))
                else:
                    raise ValueError(f"不支持的选择方式: {how}（可用: label / value / index）")
            except NoSuchElementException as e:
                raise AssertionError(f"下拉框里没有 '{input_value2}' 这个选项") from e
            except ValueError:
                raise  # 下标不是数字 / 选择方式不认识，原样抛出
            except TypeError as e:
                raise ValueError(f"按下标选择时，下标必须是整数，实际填的是 '{input_value2}'") from e

        elif action == "upload_file":
            if not input_value:
                raise ValueError("上传文件操作缺少文件路径")
            # 上传控件（input[type=file]）通常被隐藏，只能 send_keys，不能等「可点击」
            file_path = Path(input_value)
            if not file_path.is_file():
                raise ValueError(f"要上传的文件不存在: {input_value}")
            self._wait_element(by, locator_value, wait_seconds).send_keys(str(file_path.resolve()))

        elif action == "press_key":
            ActionChains(self.driver).send_keys(_resolve_key(input_value)).perform()

        # ---------- 弹窗 ----------
        elif action == "alert_accept":
            self._build_alert(wait_seconds).accept()

        elif action == "alert_dismiss":
            alert = self._build_alert(wait_seconds)
            if input_value:
                alert.send_keys(input_value)
            alert.dismiss()

        # ---------- 等待 ----------
        elif action == "force_wait":
            seconds = _clamp_wait(wait_seconds or input_value or 1)
            time.sleep(seconds)

        elif action == "smart_wait":
            self._wait_element(by, locator_value, wait_seconds)

        elif action == "wait_invisible":
            timeout = wait_seconds or DEFAULT_STEP_WAIT
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.invisibility_of_element_located((by, locator_value))
                )
            except TimeoutException as e:
                raise AssertionError(f"等待元素消失超时（{timeout}s）：元素仍然存在") from e

        # ---------- 滚动 ----------
        elif action == "scroll_to":
            elem = self._wait_element(by, locator_value, wait_seconds)
            self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)

        elif action == "scroll_to_bottom":
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # ---------- 断言 ----------
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

        elif action == "assert_url_contains":
            current = self.driver.current_url
            if input_value not in current:
                raise AssertionError(f"URL 断言失败: 期望包含 '{input_value}'，实际 '{current}'")

        elif action == "assert_element_count":
            actual = len(self.driver.find_elements(by, locator_value))
            try:
                expected = int(str(input_value).strip())
            except (TypeError, ValueError) as e:
                raise ValueError(f"期望数量必须是整数，实际填的是 '{input_value}'") from e
            if actual != expected:
                raise AssertionError(f"元素数量断言失败: 期望 {expected} 个，实际 {actual} 个")

        elif action == "assert_attribute":
            if not input_value:
                raise ValueError("断言元素属性缺少属性名")
            actual = self._wait_element(by, locator_value, wait_seconds).get_attribute(input_value)
            if input_value2:
                if (actual or "") != input_value2:
                    raise AssertionError(
                        f"属性断言失败: {input_value} 期望 '{input_value2}'，实际 '{actual}'"
                    )
            elif actual is None:
                raise AssertionError(f"属性断言失败: 元素上没有 {input_value} 属性")

        # ---------- 其他 ----------
        elif action == "execute_js":
            if not input_value.strip():
                raise ValueError("执行 JS 操作缺少脚本内容")
            self.driver.execute_script(input_value)

        elif action == "screenshot":
            self._snap(input_value or "manual", order)

        elif action == "extract_variable":
            if not input_value:
                raise ValueError("提取变量操作缺少变量名")
            elem = self._wait_element(by, locator_value, wait_seconds)
            text = elem.text or elem.get_attribute("value") or ""
            self.resolver.set_extra_var(input_value, text)
            self.extracted[input_value] = text

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
