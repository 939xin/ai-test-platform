"""
Web 测试步骤编排器 — 表格形式的步骤编辑，支持拖拽排序
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QLineEdit, QTextEdit, QCheckBox, QDoubleSpinBox, QAbstractItemView,
    QMessageBox, QMenu, QWidget, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDrag, QDropEvent, QColor
from app.database.models import DBManager

# 操作类型定义
ACTION_TYPES = [
    ('open_url', '打开 URL', 'url'),
    ('click', '点击元素', 'locator'),
    ('input', '输入文本', 'locator_value'),
    ('clear', '清空输入', 'locator'),
    ('force_wait', '强制等待', 'wait'),
    ('smart_wait', '智能等待', 'locator_wait'),
    ('switch_window', '窗口切换', 'value'),
    ('switch_iframe', 'IFrame 切换', 'locator_value'),
    ('scroll_to', '滚动到元素', 'locator'),
    ('execute_js', '执行 JS', 'value_only'),
    ('screenshot', '截图', 'name_only'),
    ('assert_text_contains', '断言-文本包含', 'locator_value'),
    ('assert_visible', '断言-元素可见', 'locator_value'),
    ('assert_exists', '断言-元素存在', 'locator_value'),
    ('extract_variable', '提取变量', 'locator_var'),
]

LOCATOR_TYPES = [
    'id', 'name', 'class_name', 'tag_name',
    'css_selector', 'xpath', 'link_text', 'partial_link_text',
]

ACTION_TYPE_MAP = {a[0]: a for a in ACTION_TYPES}

# 需要元素定位的操作（其他操作自动禁用定位字段）
NEEDS_LOCATOR = {
    'click', 'input', 'clear', 'smart_wait', 'switch_iframe',
    'scroll_to', 'assert_text_contains', 'assert_visible',
    'assert_exists', 'extract_variable'
}


class StepEditorDialog(QDialog):
    """Web 测试步骤编排对话框"""

    def __init__(self, case_id: int, parent=None):
        super().__init__(parent)
        self.case_id = case_id
        self.setWindowTitle("步骤编排器")
        self.setMinimumSize(1100, 650)
        self.resize(1200, 750)
        self._build_ui()
        self._load_steps()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        title_layout = QHBoxLayout()
        case = DBManager.fetch_one("SELECT * FROM web_test_cases WHERE id=?", (self.case_id,))
        case_name = case['name'] if case else "未知用例"
        title = QLabel(f"📋 步骤编排 - {case_name}")
        title.setObjectName("titleLabel")
        title_layout.addWidget(title)
        title_layout.addStretch()
        self.btn_save = QPushButton("💾 保存步骤")
        self.btn_save.setObjectName("successBtn")
        self.btn_save.clicked.connect(self._save_steps)
        title_layout.addWidget(self.btn_save)
        layout.addLayout(title_layout)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.btn_add_step = QPushButton("+ 添加步骤")
        self.btn_add_step.setObjectName("primaryBtn")
        self.btn_add_step.clicked.connect(self._show_add_menu)
        toolbar.addWidget(self.btn_add_step)

        self.btn_insert = QPushButton("↩ 插入")
        self.btn_insert.setObjectName("secondaryBtn")
        self.btn_insert.clicked.connect(self._insert_step)
        toolbar.addWidget(self.btn_insert)

        self.btn_delete = QPushButton("🗑 删除")
        self.btn_delete.setObjectName("dangerBtn")
        self.btn_delete.clicked.connect(self._delete_step)
        toolbar.addWidget(self.btn_delete)

        toolbar.addStretch()

        self.btn_up = QPushButton("↑ 上移")
        self.btn_up.setObjectName("secondaryBtn")
        self.btn_up.clicked.connect(self._move_up)
        toolbar.addWidget(self.btn_up)

        self.btn_down = QPushButton("↓ 下移")
        self.btn_down.setObjectName("secondaryBtn")
        self.btn_down.clicked.connect(self._move_down)
        toolbar.addWidget(self.btn_down)

        self.btn_toggle = QPushButton("🔘 启用/禁用")
        self.btn_toggle.setObjectName("secondaryBtn")
        self.btn_toggle.clicked.connect(self._toggle_step)
        toolbar.addWidget(self.btn_toggle)

        layout.addLayout(toolbar)

        # 步骤表格
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "序号", "启用", "操作类型", "定位方式", "定位值",
            "输入值", "等待(秒)", "描述"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table.setDragDropMode(QAbstractItemView.InternalMove)
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDropIndicatorShown(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        header.setSectionResizeMode(7, QHeaderView.Stretch)

        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 50)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(6, 70)

        layout.addWidget(self.table, 1)

        # 步骤详情编辑区
        detail_frame = QFrame()
        detail_frame.setObjectName("cardPanel")
        detail_layout = QHBoxLayout(detail_frame)
        detail_layout.setContentsMargins(12, 8, 12, 8)
        detail_layout.setSpacing(12)

        detail_layout.addWidget(QLabel("快速编辑:"))

        self.detail_action = QComboBox()
        self.detail_action.addItems([a[1] for a in ACTION_TYPES])
        self.detail_action.currentIndexChanged.connect(self._on_detail_action_changed)
        detail_layout.addWidget(self.detail_action)

        self.detail_locator_type = QComboBox()
        self.detail_locator_type.addItems(LOCATOR_TYPES)
        self.detail_locator_type.setMaximumWidth(100)
        detail_layout.addWidget(QLabel("定位:"))
        detail_layout.addWidget(self.detail_locator_type)

        self.detail_locator_value = QLineEdit()
        self.detail_locator_value.setPlaceholderText("定位值")
        detail_layout.addWidget(self.detail_locator_value)

        self.detail_input = QLineEdit()
        self.detail_input.setPlaceholderText("输入值/期望值")
        detail_layout.addWidget(self.detail_input)

        self.detail_wait = QDoubleSpinBox()
        self.detail_wait.setRange(0, 300)
        self.detail_wait.setSuffix("秒")
        self.detail_wait.setMaximumWidth(90)
        detail_layout.addWidget(QLabel("等待:"))
        detail_layout.addWidget(self.detail_wait)

        self.btn_apply = QPushButton("应用")
        self.btn_apply.setObjectName("primaryBtn")
        self.btn_apply.clicked.connect(self._apply_detail)
        detail_layout.addWidget(self.btn_apply)

        layout.addWidget(detail_frame)

    def _show_add_menu(self):
        """显示添加步骤的下拉菜单"""
        menu = QMenu(self)
        for action_type, label, _ in ACTION_TYPES:
            menu.addAction(label, lambda at=action_type: self._add_step(at))
        menu.exec(self.btn_add_step.mapToGlobal(self.btn_add_step.rect().bottomLeft()))

    def _add_step(self, action_type: str):
        """添加一个新步骤"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._fill_row(row, action_type)
        self._update_row_numbers()

    def _insert_step(self):
        """在当前行前插入步骤"""
        current = self.table.currentRow()
        if current < 0:
            current = self.table.rowCount() - 1
        self.table.insertRow(current)
        self._fill_row(current, 'click')
        self._update_row_numbers()

    def _fill_row(self, row: int, action_type: str):
        """填充步骤行的默认值"""
        action_label = ACTION_TYPE_MAP[action_type][1] if action_type in ACTION_TYPE_MAP else action_type

        # 序号
        self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

        # 启用
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        chk.setCheckState(Qt.Checked)
        self.table.setItem(row, 1, chk)

        # 操作类型下拉
        action_combo = QComboBox()
        action_combo.addItems([a[1] for a in ACTION_TYPES])
        action_combo.setCurrentText(action_label)
        self.table.setCellWidget(row, 2, action_combo)

        # 定位方式
        loc_combo = QComboBox()
        loc_combo.addItems(LOCATOR_TYPES)
        loc_combo.setCurrentText('xpath')
        self.table.setCellWidget(row, 3, loc_combo)

        # 定位值
        loc_value_item = QTableWidgetItem("")
        loc_value_item.setData(Qt.UserRole, action_type)
        self.table.setItem(row, 4, loc_value_item)

        # 输入值
        self.table.setItem(row, 5, QTableWidgetItem(""))

        # 等待时间
        wait_item = QTableWidgetItem("0")
        wait_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 6, wait_item)

        # 描述
        self.table.setItem(row, 7, QTableWidgetItem(action_label))

        # 根据操作类型启用/禁用定位字段
        self._update_locator_fields(row, action_type)

        # 操作类型变更时自动切换定位字段状态
        action_combo.currentTextChanged.connect(
            lambda text, r=row: self._on_row_action_changed(r, text)
        )

        self.table.selectRow(row)

    def _on_row_action_changed(self, row: int, action_label: str):
        """操作类型变更时更新定位字段状态和数据"""
        action_type = 'click'
        for at, label, _ in ACTION_TYPES:
            if label == action_label:
                action_type = at
                break
        # 更新存储的 action_type
        loc_item = self.table.item(row, 4)
        if loc_item:
            loc_item.setData(Qt.UserRole, action_type)
        self._update_locator_fields(row, action_type)

    def _update_locator_fields(self, row: int, action_type: str):
        """根据操作类型启用/禁用定位字段"""
        needs_loc = action_type in NEEDS_LOCATOR
        loc_combo = self.table.cellWidget(row, 3)
        loc_item = self.table.item(row, 4)
        if loc_combo:
            loc_combo.setEnabled(needs_loc)
        if loc_item:
            if not needs_loc:
                loc_item.setText("")
                loc_item.setFlags(Qt.NoItemFlags)
                loc_item.setBackground(QColor("#f0f0f0"))
            else:
                loc_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                loc_item.setBackground(QColor("#ffffff"))

    def _delete_step(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._update_row_numbers()

    def _move_up(self):
        row = self.table.currentRow()
        if row > 0:
            self._swap_rows(row, row - 1)
            self.table.selectRow(row - 1)

    def _move_down(self):
        row = self.table.currentRow()
        if row < self.table.rowCount() - 1 and row >= 0:
            self._swap_rows(row, row + 1)
            self.table.selectRow(row + 1)

    def _swap_rows(self, row1, row2):
        """交换两行数据"""
        cols = self.table.columnCount()
        for col in range(cols):
            item1 = self.table.takeItem(row1, col)
            item2 = self.table.takeItem(row2, col)
            self.table.setItem(row1, col, item2)
            self.table.setItem(row2, col, item1)

            # 交换 widget
            widget1 = self.table.cellWidget(row1, col)
            widget2 = self.table.cellWidget(row2, col)
            # 先移除
            if widget1:
                self.table.removeCellWidget(row1, col)
            if widget2:
                self.table.removeCellWidget(row2, col)
            if widget1:
                self.table.setCellWidget(row2, col, widget1)
            if widget2:
                self.table.setCellWidget(row1, col, widget2)

        self._update_row_numbers()

    def _toggle_step(self):
        row = self.table.currentRow()
        if row >= 0:
            chk_item = self.table.item(row, 1)
            if chk_item:
                new_state = Qt.Unchecked if chk_item.checkState() == Qt.Checked else Qt.Checked
                chk_item.setCheckState(new_state)

    def _update_row_numbers(self):
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item:
                item.setText(str(i + 1))

    def _on_detail_action_changed(self, idx):
        """详情区操作类型变化时更新显示"""
        pass

    def _apply_detail(self):
        """将详情区的值应用到当前选中行"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一个步骤")
            return

        action_label = self.detail_action.currentText()
        action_type = None
        for at, label, _ in ACTION_TYPES:
            if label == action_label:
                action_type = at
                break

        if action_type:
            combo = self.table.cellWidget(row, 2)
            if combo:
                combo.setCurrentText(action_label)
            self.table.item(row, 4).setData(Qt.UserRole, action_type)

        combo = self.table.cellWidget(row, 3)
        if combo:
            combo.setCurrentText(self.detail_locator_type.currentText())

        if self.table.item(row, 4):
            self.table.item(row, 4).setText(self.detail_locator_value.text())

        if self.table.item(row, 5):
            self.table.item(row, 5).setText(self.detail_input.text())

        if self.table.item(row, 6):
            self.table.item(row, 6).setText(str(self.detail_wait.value()))

    def _load_steps(self):
        """从数据库加载步骤"""
        steps = DBManager.fetch_all(
            "SELECT * FROM web_steps WHERE case_id=? ORDER BY step_order",
            (self.case_id,)
        )

        self.table.setRowCount(0)
        for step in steps:
            row = self.table.rowCount()
            self.table.insertRow(row)

            action_label = ACTION_TYPE_MAP.get(step['action_type'], (step['action_type'], step['action_type'], ''))[1]

            self.table.setItem(row, 0, QTableWidgetItem(str(step['step_order'])))

            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if step['enabled'] else Qt.Unchecked)
            self.table.setItem(row, 1, chk)

            action_combo = QComboBox()
            action_combo.addItems([a[1] for a in ACTION_TYPES])
            action_combo.setCurrentText(action_label)
            action_combo.currentTextChanged.connect(
                lambda text, r=row: self._on_row_action_changed(r, text)
            )
            self.table.setCellWidget(row, 2, action_combo)

            # 定位信息
            locs = DBManager.fetch_all(
                "SELECT * FROM web_step_locators WHERE step_id=?", (step['id'],)
            )
            loc = locs[0] if locs else None

            loc_combo = QComboBox()
            loc_combo.addItems(LOCATOR_TYPES)
            loc_combo.setCurrentText(loc['locator_type'] if loc else 'xpath')
            self.table.setCellWidget(row, 3, loc_combo)

            loc_value = loc['locator_value'] if loc else ''
            loc_item = QTableWidgetItem(loc_value)
            loc_item.setData(Qt.UserRole, step['action_type'])
            self.table.setItem(row, 4, loc_item)

            self.table.setItem(row, 5, QTableWidgetItem(step.get('input_value', '')))

            wait_item = QTableWidgetItem(str(step.get('wait_seconds', 0)))
            wait_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 6, wait_item)

            self.table.setItem(row, 7, QTableWidgetItem(step.get('description', '')))

            # 应用定位字段状态
            self._update_locator_fields(row, step['action_type'])

    def _save_steps(self):
        """保存所有步骤到数据库"""
        # 使用事务：先删旧数据再插入新数据，任一步失败则全部回滚
        conn = DBManager.get_raw_conn()
        try:
            cursor = conn.cursor()
            # 删除旧步骤
            cursor.execute("SELECT id FROM web_steps WHERE case_id=?", (self.case_id,))
            old_ids = [row[0] for row in cursor.fetchall()]
            for sid in old_ids:
                cursor.execute("DELETE FROM web_step_locators WHERE step_id=?", (sid,))
            cursor.execute("DELETE FROM web_steps WHERE case_id=?", (self.case_id,))

            # 保存新步骤
            for row in range(self.table.rowCount()):
                chk_item = self.table.item(row, 1)
                enabled = 1 if (chk_item and chk_item.checkState() == Qt.Checked) else 0

                action_combo = self.table.cellWidget(row, 2)
                action_label = action_combo.currentText() if action_combo else "点击元素"
                action_type = 'click'
                for at, label, _ in ACTION_TYPES:
                    if label == action_label:
                        action_type = at
                        break

                loc_combo = self.table.cellWidget(row, 3)
                loc_type = loc_combo.currentText() if loc_combo else 'xpath'

                loc_value = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
                input_value = self.table.item(row, 5).text() if self.table.item(row, 5) else ""
                wait_text = self.table.item(row, 6).text() if self.table.item(row, 6) else "0"
                desc = self.table.item(row, 7).text() if self.table.item(row, 7) else ""

                try:
                    wait_seconds = float(wait_text)
                except ValueError:
                    wait_seconds = 0

                cursor.execute(
                    "INSERT INTO web_steps (case_id, step_order, action_type, input_value, wait_seconds, enabled, description) VALUES (?,?,?,?,?,?,?)",
                    (self.case_id, row + 1, action_type, input_value, wait_seconds, enabled, desc)
                )
                step_id = cursor.lastrowid

                # 保存定位信息
                cursor.execute(
                    "INSERT INTO web_step_locators (step_id, locator_type, locator_value) VALUES (?,?,?)",
                    (step_id, loc_type, loc_value)
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        self.accept()
