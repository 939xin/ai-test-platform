"""
API 测试用例编辑器 — Tab 分页布局，避免内容拥挤
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QTabWidget, QAbstractItemView, QMessageBox,
    QLabel, QWidget, QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt
from app.database.models import DBManager


class APICaseDialog(QDialog):
    """接口测试用例编辑对话框（Tab 分页版）"""

    def __init__(self, case_id: int = None, environment_id: int = None, parent=None):
        super().__init__(parent)
        self.case_id = case_id
        self.environment_id = environment_id
        self.setWindowTitle("编辑测试用例" if case_id else "新建测试用例")
        self.setMinimumSize(750, 550)
        self.resize(780, 620)
        self._build_ui()

        if case_id:
            self._load_case()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 用例名称（放在 Tabs 上方，始终可见）
        name_layout = QHBoxLayout()
        name_layout.setSpacing(8)
        name_label = QLabel("用例名称:")
        name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        name_layout.addWidget(name_label)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如：登录接口测试")
        self.name_edit.setMinimumHeight(32)
        name_layout.addWidget(self.name_edit, 1)
        layout.addLayout(name_layout)

        # Tab 分页
        tabs = QTabWidget()
        tabs.addTab(self._build_request_tab(), "📡 请求配置")
        tabs.addTab(self._build_headers_tab(), "📋 请求头")
        tabs.addTab(self._build_assert_tab(), "🎯 断言条件")
        layout.addWidget(tabs, 1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_save = QPushButton("💾 保存")
        self.btn_save.setObjectName("primaryBtn")
        self.btn_save.setMinimumWidth(100)
        self.btn_save.clicked.connect(self._save)
        btn_layout.addWidget(self.btn_save)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("secondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    # ---------- Tab 1: 请求配置 ----------
    def _build_request_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(14)

        # URL + 方法
        url_group = QGroupBox("请求 URL")
        url_form = QFormLayout(url_group)
        url_form.setSpacing(10)
        url_form.setContentsMargins(12, 16, 12, 12)

        url_row = QHBoxLayout()
        self.method_combo = QComboBox()
        self.method_combo.addItems(["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
        self.method_combo.setFixedWidth(110)
        self.method_combo.setMinimumHeight(30)
        url_row.addWidget(self.method_combo)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("请求 URL，如 /api/user/login（支持 ${变量} 占位符）")
        self.url_edit.setMinimumHeight(30)
        url_row.addWidget(self.url_edit, 1)

        url_form.addRow("Method + URL:", url_row)

        self.relative_check = QCheckBox("相对路径（自动拼接环境 Base URL）")
        self.relative_check.setChecked(True)
        self.relative_check.setToolTip("如果 URL 以 http:// 或 https:// 开头，应取消勾选此项")
        url_form.addRow("", self.relative_check)

        # URL 输入时自动检测绝对路径
        def on_url_changed(text):
            t = text.strip()
            if t.startswith('http://') or t.startswith('https://'):
                self.relative_check.setChecked(False)
                self.relative_check.setText("⚠ 已识别为绝对路径（不拼接 Base URL）")
                self.relative_check.setStyleSheet("color: #ff9800;")
            else:
                self.relative_check.setText("相对路径（自动拼接环境 Base URL）")
                self.relative_check.setStyleSheet("")
        self.url_edit.textChanged.connect(on_url_changed)

        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("用例描述（可选，便于管理）")
        self.desc_edit.setMinimumHeight(30)
        url_form.addRow("描述:", self.desc_edit)

        timeout_row = QHBoxLayout()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 300)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" 秒")
        self.timeout_spin.setFixedWidth(140)
        timeout_row.addWidget(self.timeout_spin)
        timeout_row.addStretch()
        url_form.addRow("超时:", timeout_row)

        layout.addWidget(url_group)

        # 认证方式
        auth_group = QGroupBox("认证方式")
        auth_form = QFormLayout(auth_group)
        auth_form.setSpacing(10)
        auth_form.setContentsMargins(12, 16, 12, 12)

        auth_row = QHBoxLayout()
        self.auth_type_combo = QComboBox()
        self.auth_type_combo.addItems(["无认证", "Bearer Token", "Basic Auth", "API Key"])
        self.auth_type_combo.setMinimumHeight(30)
        self.auth_type_combo.currentTextChanged.connect(self._on_auth_type_changed)
        auth_row.addWidget(self.auth_type_combo)

        self.auth_value_edit = QLineEdit()
        self.auth_value_edit.setPlaceholderText("Token 值 / username:password / API Key")
        self.auth_value_edit.setMinimumHeight(30)
        self.auth_value_edit.setVisible(False)
        auth_row.addWidget(self.auth_value_edit, 1)

        auth_form.addRow("类型 + 值:", auth_row)
        layout.addWidget(auth_group)

        # 请求体
        body_group = QGroupBox("请求体")
        body_layout = QVBoxLayout(body_group)
        body_layout.setContentsMargins(12, 16, 12, 12)
        body_layout.setSpacing(8)

        body_top = QHBoxLayout()
        self.body_type_combo = QComboBox()
        self.body_type_combo.addItems(["none (无请求体)", "JSON", "Form Data", "XML", "Raw"])
        self.body_type_combo.setMinimumHeight(30)
        self.body_type_combo.currentTextChanged.connect(self._on_body_type_changed)
        body_top.addWidget(QLabel("类型:"))
        body_top.addWidget(self.body_type_combo)
        body_top.addStretch()

        self.btn_format_json = QPushButton("格式化 JSON")
        self.btn_format_json.setObjectName("secondaryBtn")
        self.btn_format_json.setVisible(False)
        self.btn_format_json.clicked.connect(self._format_json)
        body_top.addWidget(self.btn_format_json)
        body_layout.addLayout(body_top)

        self.body_edit = QTextEdit()
        self.body_edit.setPlaceholderText("请求体内容...")
        self.body_edit.setMinimumHeight(100)
        self.body_edit.setMaximumHeight(150)
        self.body_edit.setVisible(False)
        body_layout.addWidget(self.body_edit)

        layout.addWidget(body_group)
        layout.addStretch()

        return widget

    # ---------- Tab 2: 请求头 ----------
    def _build_headers_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)

        h_toolbar = QHBoxLayout()
        h_toolbar.setSpacing(6)
        self.btn_add_header = QPushButton("+ 添加")
        self.btn_add_header.setObjectName("primaryBtn")
        self.btn_add_header.clicked.connect(self._add_header_row)
        h_toolbar.addWidget(self.btn_add_header)
        self.btn_del_header = QPushButton("− 删除选中")
        self.btn_del_header.setObjectName("dangerBtn")
        self.btn_del_header.clicked.connect(self._del_header_row)
        h_toolbar.addWidget(self.btn_del_header)
        h_toolbar.addStretch()

        tip = QLabel("常用: Content-Type, Authorization, Accept, Cookie")
        tip.setStyleSheet("color: #9e9e9e; font-size: 11px;")
        h_toolbar.addWidget(tip)
        layout.addLayout(h_toolbar)

        self.headers_table = QTableWidget()
        self.headers_table.setColumnCount(4)
        self.headers_table.setHorizontalHeaderLabels(["启用", "Header Key", "Header Value", ""])
        self.headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.headers_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.headers_table.setColumnWidth(0, 50)
        self.headers_table.setColumnWidth(3, 50)

        # 预填一行空行
        self._add_header_row()

        layout.addWidget(self.headers_table, 1)
        return widget

    # ---------- Tab 3: 断言条件 ----------
    def _build_assert_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)

        a_toolbar = QHBoxLayout()
        a_toolbar.setSpacing(6)
        self.btn_add_assert = QPushButton("+ 添加断言")
        self.btn_add_assert.setObjectName("primaryBtn")
        self.btn_add_assert.clicked.connect(self._add_assertion_row)
        a_toolbar.addWidget(self.btn_add_assert)
        self.btn_del_assert = QPushButton("− 删除选中")
        self.btn_del_assert.setObjectName("dangerBtn")
        self.btn_del_assert.clicked.connect(self._del_assertion_row)
        a_toolbar.addWidget(self.btn_del_assert)
        a_toolbar.addStretch()

        tip = QLabel("状态码断言必填 | JSONPath 示例: $.data.name")
        tip.setStyleSheet("color: #9e9e9e; font-size: 11px;")
        a_toolbar.addWidget(tip)
        layout.addLayout(a_toolbar)

        self.assertions_table = QTableWidget()
        self.assertions_table.setColumnCount(5)
        self.assertions_table.setHorizontalHeaderLabels([
            "启用", "断言类型", "JSONPath/目标", "运算符", "期望值"
        ])
        self.assertions_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.assertions_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.assertions_table.setColumnWidth(0, 50)
        self.assertions_table.setColumnWidth(1, 130)
        self.assertions_table.setColumnWidth(3, 90)

        # 预填一行状态码断言
        self._add_assertion_row()
        # 设置第一行为状态码
        type_combo = self.assertions_table.cellWidget(0, 1)
        if type_combo:
            type_combo.setCurrentText("状态码")

        layout.addWidget(self.assertions_table, 1)
        return widget

    # ========== 事件处理（与原版相同） ==========

    def _on_auth_type_changed(self, text):
        self.auth_value_edit.setVisible(text != "无认证")
        if text == "Bearer Token":
            self.auth_value_edit.setPlaceholderText("输入 Token 值")
        elif text == "Basic Auth":
            self.auth_value_edit.setPlaceholderText("格式: username:password")
        elif text == "API Key":
            self.auth_value_edit.setPlaceholderText("输入 API Key")
        else:
            self.auth_value_edit.setPlaceholderText("")

    def _on_body_type_changed(self, text):
        show = text != "none (无请求体)"
        self.body_edit.setVisible(show)
        self.btn_format_json.setVisible(text == "JSON")

    def _format_json(self):
        import json
        try:
            data = json.loads(self.body_edit.toPlainText())
            self.body_edit.setText(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            QMessageBox.warning(self, "格式化失败", f"JSON 格式不正确：{str(e)}")

    def _add_header_row(self):
        row = self.headers_table.rowCount()
        self.headers_table.insertRow(row)
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        chk.setCheckState(Qt.Checked)
        self.headers_table.setItem(row, 0, chk)
        self.headers_table.setItem(row, 1, QTableWidgetItem(""))
        self.headers_table.setItem(row, 2, QTableWidgetItem(""))
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(28, 28)
        del_btn.setStyleSheet("border: none; color: #f44336; font-weight: bold; font-size: 14px;")
        del_btn.clicked.connect(lambda checked=False, r=row: self._remove_row(self.headers_table, r))
        self.headers_table.setCellWidget(row, 3, del_btn)

    def _del_header_row(self):
        row = self.headers_table.currentRow()
        if row >= 0:
            self.headers_table.removeRow(row)

    def _remove_row(self, table, row):
        table.removeRow(row)

    def _add_assertion_row(self):
        row = self.assertions_table.rowCount()
        self.assertions_table.insertRow(row)

        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        chk.setCheckState(Qt.Checked)
        self.assertions_table.setItem(row, 0, chk)

        type_combo = QComboBox()
        type_combo.addItems(["状态码", "响应体(JSONPath)", "响应时间"])
        type_combo.currentTextChanged.connect(lambda t, r=row: self._on_assert_type_changed(r, t))
        self.assertions_table.setCellWidget(row, 1, type_combo)

        self.assertions_table.setItem(row, 2, QTableWidgetItem(""))

        op_combo = QComboBox()
        op_combo.addItems(["等于", "不等于", "包含", "正则匹配", "小于"])
        self.assertions_table.setCellWidget(row, 3, op_combo)

        self.assertions_table.setItem(row, 4, QTableWidgetItem(""))

    def _on_assert_type_changed(self, row, text):
        target_item = self.assertions_table.item(row, 2)
        op_widget = self.assertions_table.cellWidget(row, 3)
        if text == "状态码":
            target_item.setText("")
            target_item.setFlags(Qt.NoItemFlags)
            if op_widget:
                op_widget.clear()
                op_widget.addItems(["等于", "不等于"])
        elif text == "响应时间":
            target_item.setText("")
            target_item.setFlags(Qt.NoItemFlags)
            if op_widget:
                op_widget.clear()
                op_widget.addItems(["小于"])
        else:
            target_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            if target_item.text() == "":
                target_item.setText("$.data")
            if op_widget:
                op_widget.clear()
                op_widget.addItems(["等于", "不等于", "包含", "正则匹配"])

    def _del_assertion_row(self):
        row = self.assertions_table.currentRow()
        if row >= 0:
            self.assertions_table.removeRow(row)

    def _get_auth_type(self):
        mapping = {"无认证": "none", "Bearer Token": "bearer", "Basic Auth": "basic", "API Key": "apikey"}
        return mapping.get(self.auth_type_combo.currentText(), "none")

    def _get_body_type(self):
        mapping = {"none (无请求体)": "none", "JSON": "json", "Form Data": "form", "XML": "xml", "Raw": "raw"}
        return mapping.get(self.body_type_combo.currentText(), "none")

    def _save(self):
        name = self.name_edit.text().strip()
        url = self.url_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入用例名称")
            return
        if not url:
            QMessageBox.warning(self, "提示", "请输入请求 URL")
            return

        case_data = {
            'name': name,
            'description': self.desc_edit.text().strip(),
            'url': url,
            'method': self.method_combo.currentText(),
            'body_type': self._get_body_type(),
            'body_content': self.body_edit.toPlainText() if self.body_edit.isVisible() else '',
            'auth_type': self._get_auth_type(),
            'auth_value': self.auth_value_edit.text().strip() if self.auth_value_edit.isVisible() else '',
            'timeout': self.timeout_spin.value(),
            'is_relative_url': 1 if self.relative_check.isChecked() else 0,
        }
        if self.environment_id:
            case_data['environment_id'] = self.environment_id

        # 事务保护：更新用例、删除旧headers/assertions、插入新数据在同一事务中
        conn = DBManager.get_raw_conn()
        try:
            c = conn.cursor()
            if self.case_id:
                # 更新用例
                set_clause = ', '.join([f"{k}=?" for k in case_data])
                values = list(case_data.values()) + [self.case_id]
                c.execute(f"UPDATE api_test_cases SET {set_clause} WHERE id=?", values)
                # 删除旧子数据
                c.execute("DELETE FROM api_headers WHERE case_id=?", (self.case_id,))
                c.execute("DELETE FROM api_assertions WHERE case_id=?", (self.case_id,))
            else:
                # 插入新用例
                filtered = {k: v for k, v in case_data.items() if v is not None}
                keys = ', '.join(filtered.keys())
                placeholders = ', '.join(['?' for _ in filtered])
                c.execute(f"INSERT INTO api_test_cases ({keys}) VALUES ({placeholders})", list(filtered.values()))
                self.case_id = c.lastrowid

            # 保存 Headers
            for row in range(self.headers_table.rowCount()):
                chk = self.headers_table.item(row, 0)
                key_item = self.headers_table.item(row, 1)
                val_item = self.headers_table.item(row, 2)
                key = key_item.text().strip() if key_item else ""
                if key:
                    c.execute(
                        "INSERT INTO api_headers (case_id, key, value, enabled) VALUES (?,?,?,?)",
                        (self.case_id, key, val_item.text().strip() if val_item else "",
                         1 if chk and chk.checkState() == Qt.Checked else 0)
                    )

            # 保存 Assertions
            for row in range(self.assertions_table.rowCount()):
                chk = self.assertions_table.item(row, 0)
                type_widget = self.assertions_table.cellWidget(row, 1)
                target_item = self.assertions_table.item(row, 2)
                op_widget = self.assertions_table.cellWidget(row, 3)
                val_item = self.assertions_table.item(row, 4)
                type_map = {"状态码": "status_code", "响应体(JSONPath)": "response_body", "响应时间": "response_time"}
                op_map = {"等于": "eq", "不等于": "ne", "包含": "contains", "正则匹配": "regex", "小于": "lt"}
                atype = type_map.get(type_widget.currentText() if type_widget else "", "status_code")
                target = (target_item.text() or "").strip() if target_item else ""
                op = op_map.get(op_widget.currentText() if op_widget else "", "eq")
                val = (val_item.text() or "").strip() if val_item else ""
                if val:
                    c.execute(
                        "INSERT INTO api_assertions (case_id, assertion_type, target, operator, expected_value, enabled) VALUES (?,?,?,?,?,?)",
                        (self.case_id, atype, target, op, val,
                         1 if chk and chk.checkState() == Qt.Checked else 0)
                    )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        self.accept()

    def _load_case(self):
        case = DBManager.fetch_one("SELECT * FROM api_test_cases WHERE id=?", (self.case_id,))
        if not case:
            return

        self.name_edit.setText(case['name'])
        self.desc_edit.setText(case.get('description', ''))
        self.url_edit.setText(case['url'])
        self.method_combo.setCurrentText(case['method'])
        self.relative_check.setChecked(case.get('is_relative_url', 1) == 1)
        self.timeout_spin.setValue(int(case.get('timeout', 30)))

        auth_map = {'none': '无认证', 'bearer': 'Bearer Token', 'basic': 'Basic Auth', 'apikey': 'API Key'}
        self.auth_type_combo.setCurrentText(auth_map.get(case.get('auth_type', 'none'), '无认证'))
        self.auth_value_edit.setText(case.get('auth_value', ''))

        body_map = {'none': 'none (无请求体)', 'json': 'JSON', 'form': 'Form Data', 'xml': 'XML', 'raw': 'Raw'}
        self.body_type_combo.setCurrentText(body_map.get(case.get('body_type', 'none'), 'none (无请求体)'))
        self.body_edit.setText(case.get('body_content', ''))

        # 加载 Headers
        self.headers_table.setRowCount(0)
        headers = DBManager.fetch_all("SELECT * FROM api_headers WHERE case_id=? ORDER BY id", (self.case_id,))
        for h in headers:
            row = self.headers_table.rowCount()
            self.headers_table.insertRow(row)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if h['enabled'] else Qt.Unchecked)
            self.headers_table.setItem(row, 0, chk)
            self.headers_table.setItem(row, 1, QTableWidgetItem(h['key']))
            self.headers_table.setItem(row, 2, QTableWidgetItem(h['value']))
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(28, 28)
            del_btn.setStyleSheet("border: none; color: #f44336; font-weight: bold; font-size: 14px;")
            del_btn.clicked.connect(lambda checked=False, r=row: self._remove_row(self.headers_table, r))
            self.headers_table.setCellWidget(row, 3, del_btn)

        # 加载 Assertions
        self.assertions_table.setRowCount(0)
        assertions = DBManager.fetch_all(
            "SELECT * FROM api_assertions WHERE case_id=? ORDER BY id", (self.case_id,)
        )
        for a in assertions:
            row = self.assertions_table.rowCount()
            self.assertions_table.insertRow(row)

            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if a['enabled'] else Qt.Unchecked)
            self.assertions_table.setItem(row, 0, chk)

            type_map = {'status_code': '状态码', 'response_body': '响应体(JSONPath)', 'response_time': '响应时间'}
            type_combo = QComboBox()
            type_combo.addItems(["状态码", "响应体(JSONPath)", "响应时间"])
            type_combo.setCurrentText(type_map.get(a['assertion_type'], '状态码'))
            self.assertions_table.setCellWidget(row, 1, type_combo)

            op_map = {'eq': '等于', 'ne': '不等于', 'contains': '包含', 'regex': '正则匹配', 'lt': '小于'}
            op_combo = QComboBox()
            op_combo.addItems(["等于", "不等于", "包含", "正则匹配", "小于"])
            op_combo.setCurrentText(op_map.get(a['operator'], '等于'))
            self.assertions_table.setCellWidget(row, 3, op_combo)

            # 先触发类型变更设置行状态，再覆盖为数据库中的值（防止被清空）
            self._on_assert_type_changed(row, type_combo.currentText())
            self.assertions_table.setItem(row, 2, QTableWidgetItem(a.get('target', '')))
            self.assertions_table.setItem(row, 4, QTableWidgetItem(a['expected_value']))

            # 连接信号要放在最后，避免初始化时触发
            type_combo.currentTextChanged.connect(lambda t, r=row: self._on_assert_type_changed(r, t))
