"""
主窗口 — 顶层导航 + 页面容器
"""
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QLabel, QFrame, QSizePolicy, QSpacerItem, QApplication
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("接口自动化测试工具")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # 加载样式表
        self._load_stylesheet()

        # 中央控件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 导航按钮映射 & 页面映射（需在_create_nav_bar之前初始化）
        self.nav_buttons = {}
        self.page_map = {}

        # 顶部导航栏
        self.nav_bar = self._create_nav_bar()
        main_layout.addWidget(self.nav_bar)

        # 内容区域 (StackedWidget 切换页面)
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentArea")
        main_layout.addWidget(self.content_stack, 1)

        # 状态栏
        self.status_bar = self.statusBar()
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)

    def _load_stylesheet(self):
        style_dir = os.path.join(os.path.dirname(__file__), 'styles')
        style_path = os.path.join(style_dir, 'blue_theme.qss')
        if os.path.exists(style_path):
            with open(style_path, 'r', encoding='utf-8') as f:
                qss = f.read()
            # 替换相对路径为绝对路径（Qt QSS url() 相对的是工作目录，不是 QSS 文件目录）
            abs_icon_dir = os.path.join(style_dir, 'icons').replace('\\', '/')
            qss = qss.replace('url(icons/', f'url({abs_icon_dir}/')
            self.setStyleSheet(qss)

    def _create_nav_bar(self) -> QWidget:
        nav = QWidget()
        nav.setObjectName("navBar")
        nav.setFixedHeight(44)
        layout = QHBoxLayout(nav)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(4)

        # 左侧：Logo/标题
        logo = QLabel("🔧 接口自动化测试工具")
        logo.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold; padding: 0 12px;")
        layout.addWidget(logo)

        # 分隔
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.3);")
        sep.setFixedWidth(2)
        sep.setFixedHeight(28)
        layout.addWidget(sep)

        # 导航按钮
        nav_items = [
            ("home", "🏠 首页"),
            ("api_test", "📡 接口测试"),
            ("web_test", "🌐 Web 测试"),
            ("reports", "📊 报告"),
            ("settings", "⚙️ 设置"),
        ]

        for key, label in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self.switch_page(k))
            layout.addWidget(btn)
            self.nav_buttons[key] = btn

        # 右侧弹簧
        layout.addStretch()

        # 版本信息
        version_label = QLabel("v1.0.0")
        version_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 11px; padding: 0 8px;")
        layout.addWidget(version_label)

        return nav

    def switch_page(self, page_key: str):
        """切换页面"""
        # 更新按钮选中状态
        for key, btn in self.nav_buttons.items():
            btn.setChecked(key == page_key)
        # 切换内容
        if page_key in self.page_map:
            self.content_stack.setCurrentWidget(self.page_map[page_key])

    def register_page(self, key: str, widget: QWidget):
        """注册一个页面到内容区"""
        self.content_stack.addWidget(widget)
        if not hasattr(self, 'page_map'):
            self.page_map = {}
        self.page_map[key] = widget

    def set_status(self, text: str):
        self.status_label.setText(text)
