"""
浏览器驱动管理器 — 检测、配置 Chrome/Edge WebDriver
"""
import os
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager


class BrowserManager:
    """浏览器驱动管理"""

    @staticmethod
    def check_driver(browser: str, custom_path: str = None) -> bool:
        """检测指定浏览器的驱动是否可用"""
        try:
            if browser == "chrome":
                if custom_path and os.path.exists(custom_path):
                    return True
                # 尝试使用 webdriver-manager 检测
                try:
                    ChromeDriverManager().install()
                    return True
                except Exception:
                    pass
                # 尝试系统 PATH
                try:
                    subprocess.run(["chromedriver", "--version"], capture_output=True, timeout=5)
                    return True
                except Exception:
                    pass
                return False

            elif browser == "edge":
                if custom_path and os.path.exists(custom_path):
                    return True
                try:
                    EdgeChromiumDriverManager().install()
                    return True
                except Exception:
                    pass
                try:
                    subprocess.run(["msedgedriver", "--version"], capture_output=True, timeout=5)
                    return True
                except Exception:
                    pass
                return False
        except Exception:
            return False

    @staticmethod
    def create_driver(browser: str, headless: bool = False, custom_path: str = None):
        """创建 WebDriver 实例"""
        if browser == "chrome":
            options = webdriver.ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            if custom_path and os.path.exists(custom_path):
                service = ChromeService(executable_path=custom_path)
            else:
                try:
                    driver_path = ChromeDriverManager().install()
                    service = ChromeService(executable_path=driver_path)
                except Exception:
                    service = ChromeService()

            driver = webdriver.Chrome(service=service, options=options)
            return driver

        elif browser == "edge":
            options = webdriver.EdgeOptions()
            if headless:
                options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            if custom_path and os.path.exists(custom_path):
                service = EdgeService(executable_path=custom_path)
            else:
                try:
                    driver_path = EdgeChromiumDriverManager().install()
                    service = EdgeService(executable_path=driver_path)
                except Exception:
                    service = EdgeService()

            driver = webdriver.Edge(service=service, options=options)
            return driver

        else:
            raise ValueError(f"不支持的浏览器类型: {browser}")
