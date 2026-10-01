"""
Web 自动化测试页面
- 测试用例列表（表格）
- 步骤编排器
- 浏览器/模式选择
- 执行 / 生成脚本 / 查看报告
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QCheckBox, QAbstractItemView, QMenu, QMessageBox, QFileDialog,
    QFrame, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from app.database.models import DBManager


class WebTestPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("contentArea")
        self.current_env_id = None
        self._build_ui()
        self._load_environments()
        self._load_test_cases()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("🌐 Web 自动化测试")
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

        # 浏览器选择
        browser_label = QLabel("浏览器:")
        browser_label.setStyleSheet("font-size: 13px; color: #616161; font-weight: normal; margin-left: 12px;")
        title_layout.addWidget(browser_label)
        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["Chrome", "Edge"])
        self.browser_combo.setMinimumWidth(100)
        title_layout.addWidget(self.browser_combo)

        # 无头模式
        self.headless_check = QCheckBox("后台运行（无头模式）")
        self.headless_check.setStyleSheet("margin-left: 12px;")
        title_layout.addWidget(self.headless_check)

        layout.addLayout(title_layout)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_new = QPushButton("+ 新建用例")
        self.btn_new.setObjectName("primaryBtn")
        self.btn_new.clicked.connect(self._on_new_case)
        toolbar.addWidget(self.btn_new)

        self.btn_edit = QPushButton("✎ 编辑步骤")
        self.btn_edit.setObjectName("secondaryBtn")
        self.btn_edit.clicked.connect(self._on_edit_steps)
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

        self.btn_export_excel = QPushButton("📥 导出 Excel")
        self.btn_export_excel.setObjectName("secondaryBtn")
        self.btn_export_excel.clicked.connect(self._on_export_excel)
        toolbar.addWidget(self.btn_export_excel)

        self.btn_export_json = QPushButton("📋 导出 JSON")
        self.btn_export_json.setObjectName("secondaryBtn")
        self.btn_export_json.clicked.connect(self._on_export_json)
        toolbar.addWidget(self.btn_export_json)

        self.btn_report = QPushButton("📊 查看报告")
        self.btn_report.setObjectName("secondaryBtn")
        self.btn_report.clicked.connect(self._on_view_report)
        toolbar.addWidget(self.btn_report)

        layout.addLayout(toolbar)

        # 用例列表表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "", "用例名称", "浏览器", "步骤数", "模式", "更新时间"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.doubleClicked.connect(lambda: self._on_edit_steps())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 60)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 140)

        layout.addWidget(self.table, 3)

        # 执行日志面板
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumHeight(150)
        self.log_panel.setPlaceholderText("执行日志将在此显示...")
        self.log_panel.setStyleSheet("font-family: Consolas, 'Microsoft YaHei'; font-size: 11px; background-color: #1e1e1e; color: #d4d4d4;")
        self.log_panel.setVisible(False)
        layout.addWidget(self.log_panel)

        # 底部状态区域
        status_frame = QFrame()
        status_frame.setObjectName("cardPanel")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(12, 8, 12, 8)

        self.driver_status = QLabel("🔌 驱动状态：检测中...")
        self.driver_status.setStyleSheet("font-size: 12px; color: #757575;")
        status_layout.addWidget(self.driver_status)
        status_layout.addStretch()

        self.btn_check_driver = QPushButton("检测驱动")
        self.btn_check_driver.setObjectName("secondaryBtn")
        self.btn_check_driver.clicked.connect(self._check_driver)
        status_layout.addWidget(self.btn_check_driver)

        layout.addWidget(status_frame)

        # 初始检测浏览器驱动
        self._check_driver()

    def showEvent(self, event):
        """每次页面显示时刷新环境列表"""
        super().showEvent(event)
        self._load_environments()
        self._load_test_cases()

    def _check_driver(self):
        """检测浏览器驱动"""
        try:
            from app.utils.browser_manager import BrowserManager
            mgr = BrowserManager()
            chrome_ok = mgr.check_driver("chrome")
            edge_ok = mgr.check_driver("edge")
            if chrome_ok and edge_ok:
                self.driver_status.setText("🔌 驱动状态：Chrome ✓ | Edge ✓  就绪")
                self.driver_status.setStyleSheet("font-size: 12px; color: #388e3c;")
            elif chrome_ok:
                self.driver_status.setText("🔌 驱动状态：Chrome ✓ | Edge ✗")
                self.driver_status.setStyleSheet("font-size: 12px; color: #ff9800;")
            elif edge_ok:
                self.driver_status.setText("🔌 驱动状态：Chrome ✗ | Edge ✓")
                self.driver_status.setStyleSheet("font-size: 12px; color: #ff9800;")
            else:
                self.driver_status.setText("🔌 驱动状态：未检测到可用驱动，请检查设置")
                self.driver_status.setStyleSheet("font-size: 12px; color: #f44336;")
        except Exception:
            self.driver_status.setText("🔌 驱动状态：检测失败")
            self.driver_status.setStyleSheet("font-size: 12px; color: #f44336;")

    def _load_environments(self):
        self.env_combo.blockSignals(True)
        self.env_combo.clear()
        self.env_combo.addItem("全部环境", None)
        envs = DBManager.fetch_all("SELECT id, name FROM environments ORDER BY id")
        for env in envs:
            self.env_combo.addItem(env['name'], env['id'])
        self.env_combo.blockSignals(False)

    def _on_env_changed(self, idx):
        self.current_env_id = self.env_combo.currentData()
        self._load_test_cases()

    def _load_test_cases(self):
        self.table.setRowCount(0)
        sql = "SELECT * FROM web_test_cases"
        params = []
        if self.current_env_id:
            sql += " WHERE environment_id = ?"
            params.append(self.current_env_id)
        sql += " ORDER BY updated_at DESC"
        cases = DBManager.fetch_all(sql, params)

        for row_idx, case in enumerate(cases):
            self.table.insertRow(row_idx)

            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Unchecked)
            self.table.setItem(row_idx, 0, chk)

            self.table.setItem(row_idx, 1, QTableWidgetItem(case['name']))

            browser_item = QTableWidgetItem(case['browser'])
            browser_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, browser_item)

            steps = DBManager.fetch_all(
                "SELECT COUNT(*) as cnt FROM web_steps WHERE case_id=?",
                (case['id'],)
            )
            step_cnt = steps[0]['cnt'] if steps else 0
            cnt_item = QTableWidgetItem(str(step_cnt))
            cnt_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 3, cnt_item)

            mode_text = "无头" if case['headless'] else "正常"
            mode_item = QTableWidgetItem(mode_text)
            mode_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 4, mode_item)

            self.table.setItem(row_idx, 5, QTableWidgetItem(case['updated_at']))

            self.table.item(row_idx, 1).setData(Qt.UserRole, case['id'])

    def _get_selected_case_ids(self):
        ids = []
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                name_item = self.table.item(row, 1)
                if name_item:
                    ids.append(name_item.data(Qt.UserRole))
        return ids

    def _on_new_case(self):
        from app.ui.components.web_case_dialog import WebCaseDialog
        dialog = WebCaseDialog(environment_id=self.current_env_id, parent=self)
        if dialog.exec() == WebCaseDialog.Accepted:
            self._load_test_cases()

    def _on_edit_steps(self):
        selected = self._get_selected_case_ids()
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要编辑的用例")
            return
        if len(selected) > 1:
            QMessageBox.information(self, "提示", "一次只能编辑一个用例")
            return
        from app.ui.components.step_editor import StepEditorDialog
        dialog = StepEditorDialog(case_id=selected[0], parent=self)
        if dialog.exec() == StepEditorDialog.Accepted:
            self._load_test_cases()

    def _on_delete_case(self):
        selected = self._get_selected_case_ids()
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要删除的用例")
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除选中的 {len(selected)} 个 Web 测试用例吗？\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for case_id in selected:
                DBManager.delete("web_test_cases", "id=?", (case_id,))
            self._load_test_cases()
            QMessageBox.information(self, "提示", f"已删除 {len(selected)} 个用例")

    def _on_run(self):
        selected = self._get_selected_case_ids()
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要执行的用例")
            return
        browser = self.browser_combo.currentText().lower()
        # 优先使用页面上的无头模式勾选框（用户可在执行前临时修改）
        headless = self.headless_check.isChecked()
        from app.engine.web_runner import WebRunner
        self._runner = WebRunner(selected, browser, headless)
        self._runner.log_signal.connect(self._append_log)
        self._runner.finished_signal.connect(self._on_run_finished)
        self._runner.start()

    def _append_log(self, text: str):
        self.log_panel.setVisible(True)
        self.log_panel.append(text)
        scrollbar = self.log_panel.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_run_finished(self, report_path: str):
        self.log_panel.append("\n===== 执行完成 =====")
        if report_path:
            self.log_panel.append(f"报告: {report_path}")
            reply = QMessageBox.question(
                self, "执行完成",
                f"Web 测试执行完成！\n是否打开测试报告？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                import webbrowser
                webbrowser.open(f"file:///{report_path.replace(chr(92), '/')}")
        else:
            QMessageBox.information(self, "执行完成", "Web 测试执行完成！")

    def _on_export_script(self):
        selected = self._get_selected_case_ids()
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要导出的用例")
            return
        from app.engine.script_generator import ScriptGenerator
        generator = ScriptGenerator()
        output_path = generator.generate_web_scripts(selected)
        QMessageBox.information(self, "导出成功", f"Web 测试脚本已导出到：{output_path}")

    def _on_export_excel(self):
        selected = self._get_selected_case_ids()
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要导出的用例")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Web 测试用例到 Excel",
            "",
            "Excel 文件 (*.xlsx);;所有文件 (*)"
        )
        if not file_path:
            return

        if not file_path.lower().endswith('.xlsx'):
            file_path += '.xlsx'

        from app.engine.excel_exporter import ExcelExporter
        exporter = ExcelExporter()
        try:
            output_path = exporter.export_web_cases(selected, output_path=file_path)
            QMessageBox.information(self, "导出成功", f"Web 测试用例已导出到：\n{output_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出 Excel 时发生错误：\n{str(e)}")

    def _on_export_json(self):
        selected = self._get_selected_case_ids()
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要导出的用例")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Web 测试用例到 JSON",
            "",
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        if not file_path:
            return

        if not file_path.lower().endswith('.json'):
            file_path += '.json'

        from app.engine.json_exporter import JSONExporter
        exporter = JSONExporter()
        try:
            output_path = exporter.export_web_cases(selected, output_path=file_path)
            QMessageBox.information(self, "导出成功", f"Web 测试用例已导出到：\n{output_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出 JSON 时发生错误：\n{str(e)}")

    def _on_view_report(self):
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
