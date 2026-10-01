"""
首页 — 双入口卡片：接口自动化测试 / Web 自动化测试
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal


class HomePage(QWidget):
    """首页，展示功能入口卡片"""
    navigate_to = Signal(str)  # 发送导航目标页面 key

    def __init__(self):
        super().__init__()
        self.setObjectName("contentArea")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 内部容器
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(40, 40, 40, 40)
        inner_layout.setSpacing(24)

        # 欢迎区域
        welcome_frame = QFrame()
        welcome_frame.setObjectName("cardPanel")
        welcome_layout = QVBoxLayout(welcome_frame)
        welcome_layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("接口自动化测试工具")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(title)

        subtitle = QLabel(
            "一站式自动化测试平台，支持接口测试（pytest + requests）与 Web UI 测试（Selenium）"
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        welcome_layout.addWidget(subtitle)

        # 特性标签
        features_layout = QHBoxLayout()
        features_layout.setAlignment(Qt.AlignCenter)
        features_layout.setSpacing(20)

        features = [
            ("📡", "接口自动化", "基于 pytest + requests\n支持多环境/断言/脚本导出"),
            ("🌐", "Web 自动化", "基于 Selenium\n步骤编排/截图/变量传递"),
            ("📊", "测试报告", "HTML 报告/失败截图\n概览看板/执行日志"),
            ("🔧", "实用至上", "蓝色主题/操作便捷\nPyInstaller 绿色分发"),
        ]

        for icon, name, desc in features:
            feat_card = QFrame()
            feat_card.setObjectName("cardPanel")
            feat_card.setFixedSize(220, 140)
            feat_layout = QVBoxLayout(feat_card)
            feat_layout.setAlignment(Qt.AlignCenter)

            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 32px;")
            icon_label.setAlignment(Qt.AlignCenter)
            feat_layout.addWidget(icon_label)

            name_label = QLabel(name)
            name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1976D2;")
            name_label.setAlignment(Qt.AlignCenter)
            feat_layout.addWidget(name_label)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("font-size: 11px; color: #757575;")
            desc_label.setAlignment(Qt.AlignCenter)
            desc_label.setWordWrap(True)
            feat_layout.addWidget(desc_label)

            features_layout.addWidget(feat_card)

        welcome_layout.addLayout(features_layout)
        inner_layout.addWidget(welcome_frame)

        # 两个大入口卡片
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(32)
        cards_layout.setContentsMargins(0, 16, 0, 0)

        # 接口测试入口卡片
        api_card = self._create_entry_card(
            "📡",
            "接口自动化测试",
            "配置 URL、请求参数、Headers、断言条件\n自动执行 pytest 接口测试并生成报告\n支持 GET/POST/PUT/DELETE/PATCH 等请求方法\n支持 Token/Basic Auth 认证方式",
            "#1976D2",
            "api_test"
        )
        cards_layout.addWidget(api_card)

        # Web 测试入口卡片
        web_card = self._create_entry_card(
            "🌐",
            "Web 自动化测试",
            "可视化步骤编排，拖拽排序操作步骤\n支持点击、输入、等待、截图、断言等操作\n8 种元素定位方式（XPath/CSS/ID...）\n支持 Chrome/Edge，调试/无头双模式",
            "#1565C0",
            "web_test"
        )
        cards_layout.addWidget(web_card)

        inner_layout.addLayout(cards_layout)

        # 底部弹簧
        inner_layout.addStretch()

        # 版本信息
        footer = QLabel("v1.0.0 | Built with PySide6 + pytest + Selenium")
        footer.setStyleSheet("color: #9e9e9e; font-size: 11px;")
        footer.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(footer)

        layout.addWidget(inner)

    def _create_entry_card(self, icon: str, title: str, desc: str, color: str, target: str) -> QWidget:
        """创建功能入口卡片"""
        card = QFrame()
        card.setObjectName("cardPanel")
        card.setCursor(Qt.PointingHandCursor)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(12)

        # 图标
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: 48px;")
        icon_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(icon_label)

        # 标题
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color};")
        title_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title_label)

        # 描述
        desc_label = QLabel(desc)
        desc_label.setStyleSheet("font-size: 12px; color: #757575; line-height: 1.6;")
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        card_layout.addWidget(desc_label)

        card_layout.addStretch()

        # 进入按钮
        enter_btn = QPushButton("进入 →")
        enter_btn.setObjectName("primaryBtn")
        enter_btn.setFixedWidth(120)
        enter_btn.setCursor(Qt.PointingHandCursor)
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        btn_layout.addWidget(enter_btn)
        card_layout.addLayout(btn_layout)

        # 点击事件
        def on_click():
            self.navigate_to.emit(target)

        enter_btn.clicked.connect(on_click)

        return card
