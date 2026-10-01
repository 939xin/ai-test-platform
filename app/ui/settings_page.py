"""
设置页 — 环境管理 / 全局变量 / 浏览器驱动路径配置
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QTextEdit, QGroupBox, QTabWidget, QAbstractItemView,
    QMessageBox, QDialog, QFormLayout, QDialogButtonBox, QFileDialog,
    QFrame
)
from PySide6.QtCore import Qt
from app.database.models import DBManager
import os


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("contentArea")
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        title = QLabel("⚙️ 设置")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        # Tab 切换
        tabs = QTabWidget()
        tabs.addTab(self._build_env_tab(), "🌍 环境管理")
        tabs.addTab(self._build_variables_tab(), "🔧 全局变量")
        tabs.addTab(self._build_driver_tab(), "🌐 浏览器驱动")
        layout.addWidget(tabs, 1)

    def showEvent(self, event):
        """每次页面显示时刷新数据"""
        super().showEvent(event)
        self._load_data()

    # ---- 环境管理 Tab ----
    def _build_env_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        toolbar = QHBoxLayout()
        btn_add = QPushButton("+ 添加环境")
        btn_add.setObjectName("primaryBtn")
        btn_add.clicked.connect(self._add_environment)
        toolbar.addWidget(btn_add)

        btn_edit = QPushButton("✎ 编辑")
        btn_edit.setObjectName("secondaryBtn")
        btn_edit.clicked.connect(self._edit_environment)
        toolbar.addWidget(btn_edit)

        btn_delete = QPushButton("🗑 删除")
        btn_delete.setObjectName("dangerBtn")
        btn_delete.clicked.connect(self._delete_environment)
        toolbar.addWidget(btn_delete)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.env_table = QTableWidget()
        self.env_table.setColumnCount(4)
        self.env_table.setHorizontalHeaderLabels(["ID", "环境名称", "Base URL", "描述"])
        self.env_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.env_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.env_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.env_table.setColumnWidth(0, 50)
        self.env_table.setColumnWidth(1, 150)
        layout.addWidget(self.env_table, 1)

        return widget

    def _add_environment(self):
        dialog = EnvEditDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._load_environments()

    def _edit_environment(self):
        row = self.env_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择要编辑的环境")
            return
        env_id = self.env_table.item(row, 0).data(Qt.UserRole)
        env = DBManager.fetch_one("SELECT * FROM environments WHERE id=?", (env_id,))
        if env:
            dialog = EnvEditDialog(self, env)
            if dialog.exec() == QDialog.Accepted:
                self._load_environments()

    def _delete_environment(self):
        row = self.env_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择要删除的环境")
            return
        env_name = self.env_table.item(row, 1).text()
        env_id = self.env_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除环境 \"{env_name}\" 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            DBManager.delete("environments", "id=?", (env_id,))
            self._load_environments()

    # ---- 全局变量 Tab ----
    def _build_variables_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        toolbar = QHBoxLayout()
        btn_add = QPushButton("+ 添加变量")
        btn_add.setObjectName("primaryBtn")
        btn_add.clicked.connect(self._add_variable)
        toolbar.addWidget(btn_add)

        btn_edit = QPushButton("✎ 编辑")
        btn_edit.setObjectName("secondaryBtn")
        btn_edit.clicked.connect(self._edit_variable)
        toolbar.addWidget(btn_edit)

        btn_delete = QPushButton("🗑 删除")
        btn_delete.setObjectName("dangerBtn")
        btn_delete.clicked.connect(self._delete_variable)
        toolbar.addWidget(btn_delete)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.var_table = QTableWidget()
        self.var_table.setColumnCount(4)
        self.var_table.setHorizontalHeaderLabels(["变量名", "变量值", "关联环境", "描述"])
        self.var_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.var_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.var_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.var_table.setColumnWidth(0, 150)
        self.var_table.setColumnWidth(2, 120)
        layout.addWidget(self.var_table, 1)

        return widget

    def _add_variable(self):
        dialog = VariableEditDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._load_variables()

    def _edit_variable(self):
        row = self.var_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择要编辑的变量")
            return
        var_id = self.var_table.item(row, 0).data(Qt.UserRole)
        var = DBManager.fetch_one("SELECT * FROM global_variables WHERE id=?", (var_id,))
        if var:
            dialog = VariableEditDialog(self, var)
            if dialog.exec() == QDialog.Accepted:
                self._load_variables()

    def _delete_variable(self):
        row = self.var_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择要删除的变量")
            return
        var_name = self.var_table.item(row, 0).text()
        var_id = self.var_table.item(row, 0).data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除变量 \"{var_name}\" 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            DBManager.delete("global_variables", "id=?", (var_id,))
            self._load_variables()

    # ---- 浏览器驱动 Tab ----
    def _build_driver_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Chrome 驱动
        chrome_group = QGroupBox("Chrome 驱动 (ChromeDriver)")
        chrome_layout = QVBoxLayout(chrome_group)
        chrome_row = QHBoxLayout()
        self.chrome_path_edit = QLineEdit()
        self.chrome_path_edit.setPlaceholderText("ChromeDriver 路径（留空则自动检测）")
        chrome_row.addWidget(self.chrome_path_edit, 1)
        btn_browse_chrome = QPushButton("浏览...")
        btn_browse_chrome.setObjectName("secondaryBtn")
        btn_browse_chrome.clicked.connect(lambda: self._browse_driver("chrome"))
        chrome_row.addWidget(btn_browse_chrome)
        chrome_layout.addLayout(chrome_row)
        self.chrome_status = QLabel("")
        chrome_layout.addWidget(self.chrome_status)
        layout.addWidget(chrome_group)

        # Edge 驱动
        edge_group = QGroupBox("Edge 驱动 (EdgeDriver)")
        edge_layout = QVBoxLayout(edge_group)
        edge_row = QHBoxLayout()
        self.edge_path_edit = QLineEdit()
        self.edge_path_edit.setPlaceholderText("EdgeDriver 路径（留空则自动检测）")
        edge_row.addWidget(self.edge_path_edit, 1)
        btn_browse_edge = QPushButton("浏览...")
        btn_browse_edge.setObjectName("secondaryBtn")
        btn_browse_edge.clicked.connect(lambda: self._browse_driver("edge"))
        edge_row.addWidget(btn_browse_edge)
        edge_layout.addLayout(edge_row)
        self.edge_status = QLabel("")
        edge_layout.addWidget(self.edge_status)
        layout.addWidget(edge_group)

        # 检测按钮
        row = QHBoxLayout()
        btn_check = QPushButton("🔍 检测驱动状态")
        btn_check.setObjectName("primaryBtn")
        btn_check.clicked.connect(self._check_drivers)
        row.addWidget(btn_check)
        row.addStretch()
        layout.addLayout(row)

        layout.addStretch()
        return widget

    def _browse_driver(self, browser: str):
        path, _ = QFileDialog.getOpenFileName(
            self, f"选择 {browser} 驱动文件",
            "", "Executable Files (*.exe);;All Files (*)"
        )
        if path:
            if browser == "chrome":
                self.chrome_path_edit.setText(path)
            else:
                self.edge_path_edit.setText(path)

    def _check_drivers(self):
        try:
            from app.utils.browser_manager import BrowserManager
            mgr = BrowserManager()
            chrome_path = self.chrome_path_edit.text() or None
            edge_path = self.edge_path_edit.text() or None

            chrome_ok = mgr.check_driver("chrome", chrome_path)
            edge_ok = mgr.check_driver("edge", edge_path)

            if chrome_ok:
                self.chrome_status.setText("✅ Chrome 驱动可用")
                self.chrome_status.setStyleSheet("color: #388e3c; font-size: 12px;")
            else:
                self.chrome_status.setText("❌ Chrome 驱动不可用，请安装或指定路径")
                self.chrome_status.setStyleSheet("color: #f44336; font-size: 12px;")

            if edge_ok:
                self.edge_status.setText("✅ Edge 驱动可用")
                self.edge_status.setStyleSheet("color: #388e3c; font-size: 12px;")
            else:
                self.edge_status.setText("❌ Edge 驱动不可用，请安装或指定路径")
                self.edge_status.setStyleSheet("color: #f44336; font-size: 12px;")
        except Exception as e:
            QMessageBox.warning(self, "检测失败", f"驱动检测出错：{str(e)}")

    # ---- 数据加载 ----
    def _load_data(self):
        self._load_environments()
        self._load_variables()
        self._check_drivers()

    def _load_environments(self):
        self.env_table.setRowCount(0)
        envs = DBManager.fetch_all("SELECT * FROM environments ORDER BY id")
        for row, env in enumerate(envs):
            self.env_table.insertRow(row)
            id_item = QTableWidgetItem(str(env['id']))
            id_item.setData(Qt.UserRole, env['id'])
            self.env_table.setItem(row, 0, id_item)
            self.env_table.setItem(row, 1, QTableWidgetItem(env['name']))
            self.env_table.setItem(row, 2, QTableWidgetItem(env['base_url']))
            self.env_table.setItem(row, 3, QTableWidgetItem(env.get('description', '')))

    def _load_variables(self):
        self.var_table.setRowCount(0)
        vars_list = DBManager.fetch_all(
            "SELECT v.*, e.name as env_name FROM global_variables v "
            "LEFT JOIN environments e ON v.environment_id = e.id ORDER BY v.id"
        )
        for row, var in enumerate(vars_list):
            self.var_table.insertRow(row)
            name_item = QTableWidgetItem(var['name'])
            name_item.setData(Qt.UserRole, var['id'])
            self.var_table.setItem(row, 0, name_item)
            self.var_table.setItem(row, 1, QTableWidgetItem(var['value']))
            self.var_table.setItem(row, 2, QTableWidgetItem(var.get('env_name', '全局')))
            self.var_table.setItem(row, 3, QTableWidgetItem(var.get('description', '')))


# ---- 环境编辑弹窗 ----
class EnvEditDialog(QDialog):
    def __init__(self, parent=None, env_data=None):
        super().__init__(parent)
        self.setWindowTitle("编辑环境" if env_data else "添加环境")
        self.setMinimumWidth(450)
        self.env_data = env_data

        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如：测试环境、预发布环境")
        layout.addRow("环境名称:", self.name_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("如：https://api.example.com")
        layout.addRow("Base URL:", self.url_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
        self.desc_edit.setPlaceholderText("环境描述（可选）")
        layout.addRow("描述:", self.desc_edit)

        if env_data:
            self.name_edit.setText(env_data['name'])
            self.url_edit.setText(env_data['base_url'])
            self.desc_edit.setText(env_data.get('description', ''))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _save(self):
        name = self.name_edit.text().strip()
        url = self.url_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入环境名称")
            return
        if not url:
            QMessageBox.warning(self, "提示", "请输入 Base URL")
            return

        data = {
            'name': name,
            'base_url': url,
            'description': self.desc_edit.toPlainText().strip(),
            'updated_at': None  # 将使用数据库默认值
        }

        if self.env_data:
            DBManager.update("environments", data, "id=?", (self.env_data['id'],))
        else:
            DBManager.insert("environments", data)

        self.accept()


# ---- 变量编辑弹窗 ----
class VariableEditDialog(QDialog):
    def __init__(self, parent=None, var_data=None):
        super().__init__(parent)
        self.setWindowTitle("编辑变量" if var_data else "添加变量")
        self.setMinimumWidth(400)
        self.var_data = var_data

        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如：token、user_id")
        layout.addRow("变量名:", self.name_edit)

        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("变量值")
        layout.addRow("变量值:", self.value_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(60)
        self.desc_edit.setPlaceholderText("描述（可选）")
        layout.addRow("描述:", self.desc_edit)

        # 关联环境
        self.env_combo = QComboBox()
        self.env_combo.addItem("全局（不限环境）", None)
        envs = DBManager.fetch_all("SELECT id, name FROM environments ORDER BY id")
        for env in envs:
            self.env_combo.addItem(env['name'], env['id'])
        layout.addRow("关联环境:", self.env_combo)

        if var_data:
            self.name_edit.setText(var_data['name'])
            self.value_edit.setText(var_data['value'])
            self.desc_edit.setText(var_data.get('description', ''))
            # 恢复环境关联
            env_id = var_data.get('environment_id')
            for i in range(self.env_combo.count()):
                if self.env_combo.itemData(i) == env_id:
                    self.env_combo.setCurrentIndex(i)
                    break

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入变量名")
            return

        data = {
            'name': name,
            'value': self.value_edit.text(),
            'description': self.desc_edit.toPlainText().strip(),
            'environment_id': self.env_combo.currentData(),
        }

        if self.var_data:
            DBManager.update("global_variables", data, "id=?", (self.var_data['id'],))
        else:
            DBManager.insert("global_variables", data)

        self.accept()
