"""浏览器驱动管理 — 搬自旧项目 app/utils/browser_manager.py，三处改动：

1. 剥掉类外壳改成模块函数，与 services/ 其他模块风格一致；
2. webdriver-manager 的驱动缓存默认落在 C:\\Users\\<用户>\\.wdm，
   项目约束禁止在 C 盘产生大文件，这里显式重定向到 E 盘的 settings.driver_cache_dir；
3. 新增第三级降级：前两级都失败时交给 Selenium 4 内置的 Selenium Manager
   （它自己会找到/下载匹配的驱动），并用 SE_MANAGER_PATH 把它的缓存也压到 E 盘。
"""
import os
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.driver_cache import DriverCacheManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from app.config import settings

# 浏览器可执行文件的常见安装位置。check_browser() 用它做廉价探测（只看文件在不在）。
_BROWSER_EXE_CANDIDATES = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ],
}


def find_browser_exe(browser: str) -> str:
    """返回浏览器可执行文件路径，找不到返回空串。"""
    for path in _BROWSER_EXE_CANDIDATES.get(browser, []):
        if path and os.path.exists(path):
            return path
    return ""


def check_browser(browser: str = "chrome") -> tuple[bool, str]:
    """廉价检测浏览器是否可用 —— 只看浏览器装没装、缓存目录能不能写。

    **刻意不触发任何下载**：一旦在这里调 webdriver-manager 的 install()，
    首次调用会卡几十秒下驱动，而本函数要挂在 /api/web/status 上被前端和
    验收脚本频繁调用。

    返回 (是否可用, 说明)。说明在可用时是浏览器路径，不可用时是原因。
    """
    if browser not in _BROWSER_EXE_CANDIDATES:
        return False, f"不支持的浏览器: {browser}（仅支持 chrome / edge）"

    exe = find_browser_exe(browser)
    if not exe:
        return False, f"未检测到 {browser} 浏览器，请先安装"

    try:
        Path(settings.driver_cache_dir).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return False, f"驱动缓存目录不可写: {settings.driver_cache_dir}（{e}）"

    return True, exe


def _build_options(browser: str, headless: bool):
    """构造浏览器启动参数，参数沿用旧桌面版已验证过的一套。"""
    options = webdriver.ChromeOptions() if browser == "chrome" else webdriver.EdgeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    return options


def _install_driver(browser: str, cache_dir: str) -> str:
    """用 webdriver-manager 下载驱动，缓存重定向到 cache_dir（E 盘）。"""
    cache_manager = DriverCacheManager(root_dir=cache_dir)
    if browser == "chrome":
        return ChromeDriverManager(cache_manager=cache_manager).install()
    return EdgeChromiumDriverManager(cache_manager=cache_manager).install()


def create_driver(browser: str = "chrome", headless: bool = True,
                  custom_path: str | None = None):
    """创建 WebDriver 实例。

    驱动解析三级降级，任一级成功即返回：
      1. 调用方指定的 custom_path（存在就用）；
      2. webdriver-manager 下载到 E 盘缓存；
      3. 交给 Selenium 4 内置的 Selenium Manager 自动匹配。

    三级全失败抛 RuntimeError，由 web_executor 收敛成 status="error" 返回给前端，
    而不是让接口 500。
    """
    if browser not in _BROWSER_EXE_CANDIDATES:
        raise ValueError(f"不支持的浏览器类型: {browser}")

    cache_dir = settings.driver_cache_dir
    os.makedirs(cache_dir, exist_ok=True)
    # Selenium Manager 默认缓存在 %USERPROFILE%\.cache\selenium，同样压在 C 盘，一并重定向
    os.environ.setdefault("SE_MANAGER_PATH", cache_dir)

    service_cls = ChromeService if browser == "chrome" else EdgeService
    driver_cls = webdriver.Chrome if browser == "chrome" else webdriver.Edge
    options = _build_options(browser, headless)

    builders = []
    if custom_path:
        builders.append(lambda: service_cls(executable_path=custom_path))
    builders.append(lambda: service_cls(executable_path=_install_driver(browser, cache_dir)))
    builders.append(service_cls)  # 空参 → 交给 Selenium Manager 自动匹配

    last_error = ""
    for build_service in builders:
        try:
            return driver_cls(service=build_service(), options=options)
        except Exception as e:  # 逐级降级，把最后一条错误带给调用方
            last_error = f"{type(e).__name__}: {str(e)[:200]}"

    raise RuntimeError(f"启动 {browser} 浏览器失败（驱动不可用）: {last_error}")
