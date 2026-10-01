"""
报告查看器 - 查看历史测试报告
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QFrame
)
from PySide6.QtCore import Qt
from app.database.models import DBManager
import os
import webbrowser


class ReportViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("contentArea")
        self._build_ui()
        self._load_results()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # 标题
        title_layout = QHBoxLayout()
        title = QLabel("📊 测试报告")
        title.setObjectName("titleLabel")
        title_layout.addWidget(title)
        title_layout.addStretch()

        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.setObjectName("secondaryBtn")
        self.btn_refresh.clicked.connect(self._load_results)
        title_layout.addWidget(self.btn_refresh)

        self.btn_open = QPushButton("📂 打开 HTML 报告")
        self.btn_open.setObjectName("primaryBtn")
        self.btn_open.clicked.connect(self._open_html_report)
        title_layout.addWidget(self.btn_open)

        self.btn_export_pdf = QPushButton("📄 导出 PDF")
        self.btn_export_pdf.setObjectName("secondaryBtn")
        self.btn_export_pdf.clicked.connect(self._export_pdf)
        title_layout.addWidget(self.btn_export_pdf)

        self.btn_delete_all = QPushButton("🗑 清空记录")
        self.btn_delete_all.setObjectName("dangerBtn")
        self.btn_delete_all.clicked.connect(self._clear_history)
        title_layout.addWidget(self.btn_delete_all)

        layout.addLayout(title_layout)

        # 统计面板
        stats_frame = QFrame()
        stats_frame.setObjectName("cardPanel")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(16, 12, 16, 12)
        stats_layout.setSpacing(32)

        self.stat_total = QLabel("总计: --")
        self.stat_total.setStyleSheet("font-size: 14px; font-weight: bold; color: #424242;")
        stats_layout.addWidget(self.stat_total)

        self.stat_pass = QLabel("通过: --")
        self.stat_pass.setStyleSheet("font-size: 14px; font-weight: bold; color: #388e3c;")
        stats_layout.addWidget(self.stat_pass)

        self.stat_fail = QLabel("失败: --")
        self.stat_fail.setStyleSheet("font-size: 14px; font-weight: bold; color: #d32f2f;")
        stats_layout.addWidget(self.stat_fail)

        self.stat_rate = QLabel("通过率: --")
        self.stat_rate.setStyleSheet("font-size: 14px; font-weight: bold; color: #1976D2;")
        stats_layout.addWidget(self.stat_rate)

        stats_layout.addStretch()
        layout.addWidget(stats_frame)

        # 结果列表
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "类型", "用例名称", "结果", "耗时(ms)", "环境/浏览器", "执行时间"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(lambda: self._open_html_report())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 60)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(6, 150)

        layout.addWidget(self.table, 1)

    def showEvent(self, event):
        """每次页面显示时刷新数据"""
        super().showEvent(event)
        self._load_results()

    def _load_results(self):
        self.table.setRowCount(0)
        results = DBManager.fetch_all(
            "SELECT * FROM test_results ORDER BY executed_at DESC LIMIT 100"
        )

        total = len(results)
        passed = sum(1 for r in results if r['status'] == 'pass')
        failed = sum(1 for r in results if r['status'] == 'fail')
        rate = f"{(passed/total*100):.1f}%" if total > 0 else "--"

        self.stat_total.setText(f"总计: {total}")
        self.stat_pass.setText(f"通过: {passed}")
        self.stat_fail.setText(f"失败: {failed}")
        self.stat_rate.setText(f"通过率: {rate}")

        for row_idx, r in enumerate(results):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(r['id'])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(r['test_type']))

            name_item = QTableWidgetItem(r['case_name'])
            name_item.setData(Qt.UserRole, r['id'])
            self.table.setItem(row_idx, 2, name_item)

            status_text = "✅ 通过" if r['status'] == 'pass' else "❌ 失败" if r['status'] == 'fail' else "⏭ 跳过"
            status_item = QTableWidgetItem(status_text)
            self.table.setItem(row_idx, 3, status_item)

            self.table.setItem(row_idx, 4, QTableWidgetItem(str(r['duration_ms'])))

            env_browser = r.get('environment_name', '') or r.get('browser', '') or '-'
            self.table.setItem(row_idx, 5, QTableWidgetItem(env_browser))

            self.table.setItem(row_idx, 6, QTableWidgetItem(r['executed_at']))

    def _find_report_file(self, result_id):
        """根据 result_id 查找对应的报告文件"""
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'reports')
        if not os.path.isdir(reports_dir):
            return None
        # 查找包含 r{result_id} 的 html 文件（按时间排序取最新）
        matches = []
        for f in os.listdir(reports_dir):
            if f.endswith('.html') and f'r{result_id}' in f:
                matches.append(os.path.join(reports_dir, f))
        if matches:
            return max(matches, key=os.path.getmtime)
        return None

    def _open_html_report(self):
        """打开选中的 HTML 报告"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "提示", "请双击一条结果记录以打开报告")
            return

        row = selected[0].row()
        name_item = self.table.item(row, 2)
        result_id = name_item.data(Qt.UserRole)

        report_file = self._find_report_file(result_id)
        if report_file:
            webbrowser.open(f"file:///{report_file.replace(chr(92), '/')}")
        else:
            QMessageBox.information(self, "提示", "该条记录的报告文件不存在，可能已被删除。")

    def _export_pdf(self):
        """导出选中报告为 PDF"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择一条结果记录")
            return

        row = selected[0].row()
        name_item = self.table.item(row, 2)
        result_id = name_item.data(Qt.UserRole)

        report_file = self._find_report_file(result_id)
        if not report_file:
            QMessageBox.information(self, "提示", "未找到对应的 HTML 报告文件")
            return

        reply = QMessageBox.question(
            self, "导出 PDF",
            "将使用 Chrome 浏览器生成 PDF。\n\n如果 Chrome 不可用，将打开 HTML 报告供手动打印。\n\n是否继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        from app.utils.pdf_exporter import export_html_to_pdf
        pdf_path = export_html_to_pdf(report_file)

        if pdf_path and os.path.exists(pdf_path):
            QMessageBox.information(self, "导出成功", f"PDF 已保存到：\n{pdf_path}")
            # 打开 PDF 文件（跨平台）
            import webbrowser
            webbrowser.open(f"file:///{pdf_path.replace(chr(92), '/')}")
        else:
            # 回退方案：浏览器手动打印
            QMessageBox.information(
                self, "提示",
                "自动 PDF 生成失败（可能 Chrome 不可用）。\n将打开 HTML 报告，请使用浏览器 Ctrl+P 手动打印为 PDF。"
            )
            webbrowser.open(f"file:///{report_file.replace(chr(92), '/')}")

    def _clear_history(self):
        reply = QMessageBox.question(
            self, "确认清空",
            "确定要清空所有测试结果记录吗？\n报告文件不会被删除。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            DBManager.execute("DELETE FROM test_result_details")
            DBManager.execute("DELETE FROM test_results")
            DBManager.execute("DELETE FROM screenshots")
            self._load_results()
            QMessageBox.information(self, "提示", "历史记录已清空")
