"""
接口自动化测试工具 — 主入口
"""
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.database.models import init_db
from app.ui.main_window import MainWindow
from app.ui.home_page import HomePage
from app.ui.api_test_page import APITestPage
from app.ui.web_test_page import WebTestPage
from app.ui.report_viewer import ReportViewer
from app.ui.settings_page import SettingsPage


def main():
    # 初始化数据库
    init_db()

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("接口自动化测试工具")
    app.setApplicationVersion("1.0.0")

    # 设置默认字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    # 创建主窗口
    window = MainWindow()

    # 创建各页面
    home_page = HomePage()
    api_test_page = APITestPage()
    web_test_page = WebTestPage()
    report_viewer = ReportViewer()
    settings_page = SettingsPage()

    # 注册页面
    window.register_page("home", home_page)
    window.register_page("api_test", api_test_page)
    window.register_page("web_test", web_test_page)
    window.register_page("reports", report_viewer)
    window.register_page("settings", settings_page)

    # 首页导航信号连接
    home_page.navigate_to.connect(window.switch_page)

    # 默认显示首页
    window.switch_page("home")

    # 显示窗口
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
