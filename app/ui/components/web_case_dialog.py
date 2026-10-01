"""
Web 测试用例基本信息编辑器
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit,
    QComboBox, QCheckBox, QDialogButtonBox, QMessageBox
)
from app.database.models import DBManager


class WebCaseDialog(QDialog):
    """Web 测试用例基本信息对话框"""

    def __init__(self, case_id: int = None, environment_id: int = None, parent=None):
        super().__init__(parent)
        self.case_id = case_id
        self.environment_id = environment_id
        self.setWindowTitle("编辑 Web 测试用例" if case_id else "新建 Web 测试用例")
        self.setMinimumWidth(450)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如：用户登录流程测试")
        layout.addRow("用例名称:", self.name_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
        self.desc_edit.setPlaceholderText("用例描述（可选）")
        layout.addRow("描述:", self.desc_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("起始 URL（如 https://example.com/login）")
        layout.addRow("起始 URL:", self.url_edit)

        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["Chrome", "Edge"])
        layout.addRow("浏览器:", self.browser_combo)

        self.headless_check = QCheckBox("默认使用无头模式")
        layout.addRow("", self.headless_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        if case_id:
            self._load_case()

    def _load_case(self):
        case = DBManager.fetch_one("SELECT * FROM web_test_cases WHERE id=?", (self.case_id,))
        if case:
            self.name_edit.setText(case['name'])
            self.desc_edit.setText(case.get('description', ''))
            self.url_edit.setText(case.get('start_url', ''))
            browser_val = case.get('browser', 'Chrome').lower().capitalize()
            self.browser_combo.setCurrentText(browser_val)
            self.headless_check.setChecked(case.get('headless', 0) == 1)

    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入用例名称")
            return

        data = {
            'name': name,
            'description': self.desc_edit.toPlainText().strip(),
            'start_url': self.url_edit.text().strip(),
            'browser': self.browser_combo.currentText().lower(),
            'headless': 1 if self.headless_check.isChecked() else 0,
        }
        if self.environment_id:
            data['environment_id'] = self.environment_id

        if self.case_id:
            DBManager.update("web_test_cases", data, "id=?", (self.case_id,))
        else:
            self.case_id = DBManager.insert("web_test_cases", data)

        self.accept()
