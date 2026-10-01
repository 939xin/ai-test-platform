"""
接口自动化测试页面
- 测试用例列表（表格）
- 用例编辑器（弹窗）
- 环境选择器
- 执行 / 生成脚本 / 查看报告
- 响应详情面板（状态码、响应头、响应体、断言结果）
"""
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QFrame, QAbstractItemView, QMenu, QMessageBox, QSplitter,
    QTextEdit, QScrollArea, QGroupBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from app.database.models import DBManager


class APITestPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("contentArea")
        self.current_env_id = None
        self._build_ui()
        self._load_environments()
        self._load_test_cases()

    def showEvent(self, event):
        """每次页面显示时刷新环境列表+用例列表"""
        super().showEvent(event)
        self._load_environments()
        self._load_test_cases()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("📡 接口自动化测试")
        title.setObjectName("titleLabel")
        title_layout.addWidget(title)
        title_layout.addStretch()

        # 环境选择器
        env_label = QLabel("当前环境:")
        env_label.setStyleSheet("font-size: 13px; color: #616161; font-weight: normal;")
        title_layout.addWidget(env_label)
        self.env_combo = QComboBox()
        self.env_combo.setMinimumWidth(160)
        self.env_combo.currentIndexChanged.connect(self._on_env_changed)
        title_layout.addWidget(self.env_combo)

        layout.addLayout(title_layout)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_new = QPushButton("+ 新建用例")
        self.btn_new.setObjectName("primaryBtn")
        self.btn_new.clicked.connect(self._on_new_case)
        toolbar.addWidget(self.btn_new)

        self.btn_edit = QPushButton("✎ 编辑")
        self.btn_edit.setObjectName("secondaryBtn")
        self.btn_edit.clicked.connect(self._on_edit_case)
        toolbar.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("🗑 删除")
        self.btn_delete.setObjectName("dangerBtn")
        self.btn_delete.clicked.connect(self._on_delete_case)
        toolbar.addWidget(self.btn_delete)

        toolbar.addStretch()

        self.btn_run = QPushButton("▶ 执行选中")
        self.btn_run.setObjectName("successBtn")
        self.btn_run.clicked.connect(self._on_run)
        toolbar.addWidget(self.btn_run)

        self.btn_export = QPushButton("📄 生成脚本")
        self.btn_export.setObjectName("secondaryBtn")
        self.btn_export.clicked.connect(self._on_export_script)
        toolbar.addWidget(self.btn_export)

        self.btn_report = QPushButton("📊 报告")
        self.btn_report.setObjectName("secondaryBtn")
        self.btn_report.clicked.connect(self._on_view_report)
        toolbar.addWidget(self.btn_report)

        # SSL验证勾选框（localhost测试常用）
        from PySide6.QtWidgets import QCheckBox
        self.ssl_check = QCheckBox("忽略SSL证书验证")
        self.ssl_check.setToolTip("测试环境自签名证书时勾选此项")
        self.ssl_check.setStyleSheet("font-size: 12px; color: #ff9800; margin-left: 8px;")
        toolbar.addWidget(self.ssl_check)

        layout.addLayout(toolbar)

        # 用例列表表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "", "用例名称", "请求方法", "URL", "断言数", "更新时间"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.doubleClicked.connect(lambda: self._on_edit_case())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 40)   # 复选框
        self.table.setColumnWidth(2, 80)   # 方法
        self.table.setColumnWidth(4, 60)   # 断言数
        self.table.setColumnWidth(5, 140)  # 更新时间

        layout.addWidget(self.table, 3)

        # 下半部分：Splitter 分栏 = 执行日志 + 响应详情
        self.bottom_splitter = QSplitter(Qt.Horizontal)
        self.bottom_splitter.setMinimumHeight(250)
        layout.addWidget(self.bottom_splitter, 2)

        # -- 左侧：执行日志 --
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setPlaceholderText("执行日志将在此显示...")
        self.log_panel.setStyleSheet(
            "font-family: Consolas, 'Microsoft YaHei'; font-size: 11px;"
            "background-color: #1e1e1e; color: #d4d4d4;"
        )
        self.bottom_splitter.addWidget(self.log_panel)

        # -- 右侧：响应详情 --
        self.response_panel = self._build_response_panel()
        self.bottom_splitter.addWidget(self.response_panel)
        self.bottom_splitter.setSizes([400, 600])

    def _build_response_panel(self) -> QWidget:
        """构建响应详情面板"""
        panel = QWidget()
        panel.setStyleSheet("background-color: #ffffff;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # 状态行
        status_row = QHBoxLayout()
        self.resp_status_label = QLabel("等待执行...")
        self.resp_status_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #757575; padding: 4px 0;"
        )
        status_row.addWidget(self.resp_status_label)
        status_row.addStretch()

        self.resp_time_label = QLabel("")
        self.resp_time_label.setStyleSheet("font-size: 13px; color: #616161;")
        status_row.addWidget(self.resp_time_label)
        layout.addLayout(status_row)

        # 请求 URL
        self.resp_url_label = QLabel("")
        self.resp_url_label.setStyleSheet(
            "font-size: 12px; color: #1976D2; padding: 2px 0;"
        )
        self.resp_url_label.setWordWrap(True)
        layout.addWidget(self.resp_url_label)

        # 响应头
        headers_group = QGroupBox("响应头")
        headers_layout = QVBoxLayout(headers_group)
        headers_layout.setContentsMargins(4, 12, 4, 4)
        self.resp_headers_table = QTableWidget()
        self.resp_headers_table.setColumnCount(2)
        self.resp_headers_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.resp_headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.resp_headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.resp_headers_table.setColumnWidth(0, 180)
        self.resp_headers_table.setMaximumHeight(150)
        self.resp_headers_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        headers_layout.addWidget(self.resp_headers_table)
        layout.addWidget(headers_group)

        # 响应体
        body_group = QGroupBox("响应体")
        body_layout = QVBoxLayout(body_group)
        body_layout.setContentsMargins(4, 12, 4, 4)
        self.resp_body_view = QTextEdit()
        self.resp_body_view.setReadOnly(True)
        self.resp_body_view.setFont(QFont("Consolas", 10))
        self.resp_body_view.setStyleSheet(
            "background-color: #fafafa; border: 1px solid #e0e0e0; border-radius: 4px;"
        )
        body_layout.addWidget(self.resp_body_view)
        layout.addWidget(body_group, 1)

        # 断言结果
        assert_group = QGroupBox("断言结果")
        assert_layout = QVBoxLayout(assert_group)
        assert_layout.setContentsMargins(4, 12, 4, 4)
        self.resp_assert_list = QTextEdit()
        self.resp_assert_list.setReadOnly(True)
        self.resp_assert_list.setMaximumHeight(120)
        self.resp_assert_list.setFont(QFont("Consolas", 10))
        assert_layout.addWidget(self.resp_assert_list)
        layout.addWidget(assert_group)

        return panel

    def _on_case_finished(self, data: dict):
        """接收 APIRunner 的结构化响应数据，更新响应详情面板"""
        status = data.get('status', 'error')
        resp_status = data.get('response_status', 0)
        duration = data.get('duration_ms', 0)
        url = data.get('request_url', '')
        method = data.get('request_method', '')

        # 状态标签
        if status == 'pass':
            color = "#388e3c"
            text = f"✅ {resp_status} — 通过"
        elif status == 'fail':
            color = "#d32f2f"
            text = f"❌ {resp_status} — 失败"
        else:
            color = "#ff9800"
            text = f"⚠️ {resp_status or 'N/A'} — 错误"

        self.resp_status_label.setText(text)
        self.resp_status_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {color}; padding: 4px 0;"
        )
        self.resp_time_label.setText(f"⏱ {duration:.0f}ms")
        self.resp_url_label.setText(f"{method} {url}")

        # 响应头表格
        resp_headers = data.get('response_headers', '')
        self.resp_headers_table.setRowCount(0)
        if resp_headers:
            try:
                headers_dict = json.loads(resp_headers) if isinstance(resp_headers, str) else resp_headers
                if isinstance(headers_dict, dict):
                    for key, val in headers_dict.items():
                        row = self.resp_headers_table.rowCount()
                        self.resp_headers_table.insertRow(row)
                        self.resp_headers_table.setItem(row, 0, QTableWidgetItem(str(key)))
                        self.resp_headers_table.setItem(row, 1, QTableWidgetItem(str(val)))
            except Exception:
                pass

        # 响应体
        resp_body = data.get('response_body', '')
        if resp_body:
            # 尝试格式化 JSON
            try:
                parsed = json.loads(resp_body)
                resp_body = json.dumps(parsed, indent=2, ensure_ascii=False)
            except Exception:
                pass
        self.resp_body_view.setText(resp_body)

        # 断言结果
        assertions = data.get('assertions', [])
        assert_lines = []
        for a in assertions:
            icon = "✅" if a.get('passed') else "❌"
            assert_lines.append(
                f"{icon} {a.get('type', '')}: 期望={a.get('expected', '')} 实际={a.get('actual', '')[:80]}"
            )
        self.resp_assert_list.setText('\n'.join(assert_lines) if assert_lines else '无断言')


    def _load_environments(self):
        """加载环境列表，保留之前选中的环境"""
        previous_id = self.env_combo.currentData() if self.env_combo.count() > 0 else None
        self.env_combo.blockSignals(True)
        self.env_combo.clear()
        self.env_combo.addItem("全部环境", None)
        envs = DBManager.fetch_all("SELECT id, name FROM environments ORDER BY id")
        for env in envs:
            self.env_combo.addItem(env['name'], env['id'])
        # 恢复之前选中的环境
        if previous_id is not None:
            for i in range(self.env_combo.count()):
                if self.env_combo.itemData(i) == previous_id:
                    self.env_combo.setCurrentIndex(i)
                    self.current_env_id = previous_id
                    break
        else:
            self.current_env_id = None
        self.env_combo.blockSignals(False)

    def _on_env_changed(self, idx):
        self.current_env_id = self.env_combo.currentData()
        self._load_test_cases()

    def _load_test_cases(self):
        """加载测试用例列表"""
        self.table.setRowCount(0)
        sql = "SELECT * FROM api_test_cases"
        params = []
        if self.current_env_id:
            sql += " WHERE environment_id = ?"
            params.append(self.current_env_id)
        sql += " ORDER BY updated_at DESC"
        cases = DBManager.fetch_all(sql, params)

        methods_color = {
            'GET': '#4caf50', 'POST': '#ff9800', 'PUT': '#2196f3',
            'DELETE': '#f44336', 'PATCH': '#9c27b0'
        }

        for row_idx, case in enumerate(cases):
            self.table.insertRow(row_idx)
            # 复选框（用于多选执行）
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Unchecked)
            self.table.setItem(row_idx, 0, chk)

            self.table.setItem(row_idx, 1, QTableWidgetItem(case['name']))

            method_item = QTableWidgetItem(case['method'])
            color = methods_color.get(case['method'], '#757575')
            method_item.setForeground(QColor(color))
            method_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, method_item)

            self.table.setItem(row_idx, 3, QTableWidgetItem(case['url']))

            # 断言数量
            assertions = DBManager.fetch_all(
                "SELECT COUNT(*) as cnt FROM api_assertions WHERE case_id=?",
                (case['id'],)
            )
            cnt = assertions[0]['cnt'] if assertions else 0
            cnt_item = QTableWidgetItem(str(cnt))
            cnt_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 4, cnt_item)

            self.table.setItem(row_idx, 5, QTableWidgetItem(case['updated_at']))

            # 存储 case id
            self.table.item(row_idx, 1).setData(Qt.UserRole, case['id'])

    def _get_selected_case_ids(self):
        """获取勾选的用例 ID"""
        ids = []
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                name_item = self.table.item(row, 1)
                if name_item:
                    ids.append(name_item.data(Qt.UserRole))
        return ids

    def _on_new_case(self):
        from app.ui.components.api_case_dialog import APICaseDialog
        dialog = APICaseDialog(environment_id=self.current_env_id, parent=self)
        if dialog.exec() == APICaseDialog.Accepted:
            self._load_test_cases()

    def _on_edit_case(self):
        selected = self._get_selected_case_ids()
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要编辑的用例")
            return
        if len(selected) > 1:
            QMessageBox.information(self, "提示", "一次只能编辑一个用例")
            return
        from app.ui.components.api_case_dialog import APICaseDialog
        dialog = APICaseDialog(case_id=selected[0], environment_id=self.current_env_id, parent=self)
        if dialog.exec() == APICaseDialog.Accepted:
            self._load_test_cases()

    def _on_delete_case(self):
        selected = self._get_selected_case_ids()
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要删除的用例")
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除选中的 {len(selected)} 个用例吗？\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for case_id in selected:
                DBManager.delete("api_test_cases", "id=?", (case_id,))
            self._load_test_cases()
            QMessageBox.information(self, "提示", f"已删除 {len(selected)} 个用例")

    def _on_run(self):
        selected = self._get_selected_case_ids()
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要执行的用例")
            return
        env_id = self.env_combo.currentData()
        if not env_id:
            QMessageBox.information(self, "提示", "请先选择目标环境")
            return
        from app.engine.api_runner import APIRunner
        env = DBManager.fetch_one("SELECT * FROM environments WHERE id=?", (env_id,))
        if not env:
            QMessageBox.warning(self, "错误", "所选环境不存在，可能已被删除，请刷新后重试")
            return
        verify_ssl = not self.ssl_check.isChecked()
        self._runner = APIRunner(selected, env, verify_ssl=verify_ssl)
        self._runner.log_signal.connect(self._append_log)
        self._runner.case_finished.connect(self._on_case_finished)
        self._runner.finished_signal.connect(self._on_run_finished)
        self._runner.start()

    def _append_log(self, text: str):
        self.log_panel.append(text)
        scrollbar = self.log_panel.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_run_finished(self, report_path: str):
        self.log_panel.append("\n===== 执行完成 =====")
        if report_path:
            self.log_panel.append(f"报告: {report_path}")
            # 询问是否打开报告
            reply = QMessageBox.question(
                self, "执行完成",
                f"测试执行完成！\n是否打开测试报告？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                import webbrowser
                webbrowser.open(f"file:///{report_path.replace(chr(92), '/')}")
        else:
            QMessageBox.information(self, "执行完成", "测试执行完成！")

    def _on_export_script(self):
        selected = self._get_selected_case_ids()
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要导出的用例")
            return
        from app.engine.script_generator import ScriptGenerator
        generator = ScriptGenerator()
        output_path = generator.generate_api_scripts(selected)
        QMessageBox.information(self, "导出成功", f"脚本已导出到：{output_path}")

    def _on_view_report(self):
        # 切换到报告页面
        main_window = self.window()
        if hasattr(main_window, 'switch_page'):
            main_window.switch_page('reports')

    def _on_context_menu(self, pos):
        menu = QMenu(self)
        select_all = menu.addAction("全选")
        deselect_all = menu.addAction("取消全选")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == select_all:
            for row in range(self.table.rowCount()):
                self.table.item(row, 0).setCheckState(Qt.Checked)
        elif action == deselect_all:
            for row in range(self.table.rowCount()):
                self.table.item(row, 0).setCheckState(Qt.Unchecked)
