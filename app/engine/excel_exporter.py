"""
Web 测试用例 Excel 导出器 — 企业级模板格式

导出的 Excel 包含以下 11 列：
  ① 用例编号  → TC_WEB_{id}
  ② 模块       → 留空（手动填写）
  ③ 用例标题   → case['name']
  ④ 优先级     → 默认 P2
  ⑤ 前置条件   → 浏览器 + 起始 URL + 环境信息
  ⑥ 测试步骤   → 可读的 Selenium 操作描述（含元素定位）
  ⑦ 预期结果   → 按操作类型自动生成
  ⑧ 实际结果   → 有执行记录时填充（从 test_result_details 获取）
  ⑨ 测试数据   → step['input_value']
  ⑩ 是否可自动化 → 默认"是"
  ⑪ 备注      → case/step 的 description
"""
import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from app.database.models import DBManager


class ExcelExporter:
    """企业级 Web 测试用例 Excel 导出器"""

    # 列索引（0-based）
    COL_CASE_ID = 0          # 用例编号
    COL_MODULE = 1           # 模块
    COL_TITLE = 2            # 用例标题
    COL_PRIORITY = 3         # 优先级
    COL_PRECONDITIONS = 4    # 前置条件
    COL_STEPS = 5            # 测试步骤（每步一行）
    COL_EXPECTED = 6         # 预期结果
    COL_ACTUAL = 7           # 实际结果
    COL_TEST_DATA = 8        # 测试数据
    COL_AUTOMATABLE = 9      # 是否可自动化
    COL_REMARKS = 10         # 备注

    COL_COUNT = 11

    # 操作类型 → 步骤描述模板
    STEP_TEMPLATES = {
        'open_url':           '打开浏览器，访问 {input}',
        'click':              '点击元素({locator})',
        'input':              '在输入框({locator})中输入"{input}"',
        'clear':              '清空输入框({locator})',
        'force_wait':         '等待 {wait} 秒',
        'smart_wait':         '等待元素({locator})出现（超时 {wait} 秒）',
        'switch_window':      '切换至第 {input} 个窗口',
        'switch_iframe':      '切换至 IFrame({locator})',
        'scroll_to':          '滚动到元素({locator})',
        'execute_js':         '执行 JavaScript：{input}',
        'screenshot':         '截图保存：{input}',
        'assert_text_contains': '验证文本({locator})包含"{input}"',
        'assert_visible':     '验证元素({locator})可见',
        'assert_exists':      '验证元素({locator})存在',
        'extract_variable':   '提取变量"{input}" → 从元素({locator})',
    }

    # 操作类型 → 预期结果模板
    EXPECTED_TEMPLATES = {
        'open_url':           '页面 {input} 成功加载，URL 正确，页面标题正常显示',
        'click':              '元素({locator})被成功点击，页面/状态正确响应',
        'input':              '输入框({locator})成功输入"{input}"，显示内容正确',
        'clear':              '输入框({locator})内容被成功清空',
        'force_wait':         '等待 {wait} 秒结束，页面无异常',
        'smart_wait':         '元素({locator})在 {wait} 秒内成功出现在页面中',
        'switch_window':      '成功切换至第 {input} 个窗口，页面内容正确',
        'switch_iframe':      '成功切换至 IFrame({locator})，可操作内部元素',
        'scroll_to':          '元素({locator})已滚动到可视区域内',
        'execute_js':         'JavaScript 执行成功，控制台无报错',
        'screenshot':         '截图"{input}"保存成功，图片清晰完整',
        'assert_text_contains': '页面({locator})包含预期文本"{input}"，断言通过',
        'assert_visible':     '元素({locator})在页面上可见',
        'assert_exists':      '元素({locator})存在于 DOM 中',
        'extract_variable':   '变量"{input}"从元素({locator})提取成功，值正确',
    }

    # 操作类型 → 中文名（无定位器时的降级使用）
    ACTION_LABELS = {
        'open_url': '打开 URL', 'click': '点击元素', 'input': '输入文本',
        'clear': '清空输入', 'force_wait': '强制等待', 'smart_wait': '智能等待',
        'switch_window': '窗口切换', 'switch_iframe': 'IFrame 切换',
        'scroll_to': '滚动到元素', 'execute_js': '执行 JS', 'screenshot': '截图',
        'assert_text_contains': '断言-文本包含', 'assert_visible': '断言-元素可见',
        'assert_exists': '断言-元素存在', 'extract_variable': '提取变量',
    }

    def __init__(self):
        self.exports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'exports'
        )
        os.makedirs(self.exports_dir, exist_ok=True)

    # ------------------------------------------------------------------
    #  公共入口
    # ------------------------------------------------------------------
    def export_web_cases(self, case_ids: list, output_path: str = None) -> str:
        """导出 Web 测试用例到企业级 Excel 模板

        Args:
            case_ids: 要导出的用例 ID 列表
            output_path: 输出文件路径，为 None 时自动生成

        Returns:
            生成的文件绝对路径
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(self.exports_dir, f"web_cases_export_{timestamp}.xlsx")

        wb = Workbook()
        ws = wb.active
        ws.title = "Web 测试用例"

        self._write_header(ws)
        current_row = 2

        for cid in case_ids:
            case = DBManager.fetch_one("SELECT * FROM web_test_cases WHERE id=?", (cid,))
            if not case:
                continue

            # 展开后的步骤列表（带 step_description / locator_text）
            enriched_steps = self._enrich_steps(cid)
            # 实际结果 step_order → text 映射
            actual_map = self._get_actual_results(cid)
            # 前置条件
            precondition = self._build_precondition(case)

            if not enriched_steps:
                # 没有步骤 → 仍然写一行，只有用例级字段
                self._write_row(ws, current_row, case, precondition, None, actual_map, None)
                current_row += 1
                continue

            case_start_row = current_row
            for es in enriched_steps:
                self._write_row(ws, current_row, case, precondition, es, actual_map, es)
                current_row += 1

            # 合并用例级列的单元格
            case_end_row = current_row - 1
            if case_end_row > case_start_row:
                for col in (self.COL_CASE_ID, self.COL_MODULE, self.COL_TITLE,
                            self.COL_PRIORITY, self.COL_PRECONDITIONS,
                            self.COL_AUTOMATABLE, self.COL_REMARKS):
                    ws.merge_cells(
                        start_row=case_start_row, start_column=col + 1,
                        end_row=case_end_row, end_column=col + 1
                    )

        self._apply_column_widths(ws)
        # 冻结首行
        ws.freeze_panes = 'A2'
        wb.save(output_path)
        return os.path.abspath(output_path)

    # ------------------------------------------------------------------
    #  数据处理
    # ------------------------------------------------------------------
    def _enrich_steps(self, case_id: int) -> list:
        """读取步骤并丰富成显示用字典列表"""
        rows = DBManager.fetch_all(
            "SELECT * FROM web_steps WHERE case_id=? AND enabled=1 ORDER BY step_order",
            (case_id,)
        )
        result = []
        for step in rows:
            locators = DBManager.fetch_all(
                "SELECT * FROM web_step_locators WHERE step_id=?", (step['id'],)
            )
            loc = locators[0] if locators else None
            action = step['action_type']
            input_val = step.get('input_value', '') or ''
            wait_val = step.get('wait_seconds', 0)

            # 格式化定位器文本  id=kw  /  xpath=//div[@id="app"]
            locator_text = ''
            if loc:
                locator_text = f"{loc['locator_type']}={loc['locator_value']}"

            # 步骤描述
            template = self.STEP_TEMPLATES.get(action, action)
            step_desc = template.format(
                input=input_val,
                locator=locator_text,
                wait=wait_val,
            )
            # 如果没有定位器，去掉 ({locator}) 部分
            if not locator_text and '{locator}' in template:
                step_desc = step_desc.replace(f'({locator_text})', '').strip()
                step_desc = step_desc.replace(f'（{locator_text}）', '').strip()

            # 预期结果
            exp_template = self.EXPECTED_TEMPLATES.get(action, '操作执行成功，无异常')
            expected = exp_template.format(
                input=input_val,
                locator=locator_text,
                wait=wait_val,
            )
            if not locator_text and '{locator}' in exp_template:
                expected = expected.replace(f'({locator_text})', '').strip()

            result.append({
                'step': step,
                'locator': loc,
                'step_description': step_desc,
                'expected_result': expected,
                'locator_text': locator_text,
            })
        return result

    def _build_precondition(self, case: dict) -> str:
        """构建前置条件文本"""
        parts = []

        browser = case.get('browser', 'chrome').capitalize()
        parts.append(f"浏览器: {browser}")

        start_url = case.get('start_url', '') or ''
        if start_url:
            parts.append(f"起始 URL: {start_url}")

        env_id = case.get('environment_id')
        if env_id:
            env = DBManager.fetch_one(
                "SELECT name, base_url FROM environments WHERE id=?", (env_id,)
            )
            if env:
                parts.append(f"环境: {env['name']} ({env['base_url']})")

        return " | ".join(parts)

    def _get_actual_results(self, case_id: int) -> dict:
        """获取用例最新一次执行的实际结果，按 step_order → 文本 映射"""
        latest = DBManager.fetch_one(
            """SELECT id FROM test_results
               WHERE case_id=? AND test_type='web'
               ORDER BY executed_at DESC LIMIT 1""",
            (case_id,)
        )
        if not latest:
            return {}
        details = DBManager.fetch_all(
            "SELECT step_order, status, message FROM test_result_details WHERE result_id=? ORDER BY step_order",
            (latest['id'],)
        )
        mapping = {}
        for d in details:
            if d['status'] == 'pass':
                mapping[d['step_order']] = f"✅ 通过"
            elif d['status'] == 'fail':
                msg = (d.get('message') or '').strip()
                mapping[d['step_order']] = f"❌ 失败: {msg}" if msg else "❌ 失败"
            else:
                mapping[d['step_order']] = f"⚠️ {d['status']}"
        return mapping

    # ------------------------------------------------------------------
    #  写 Excel
    # ------------------------------------------------------------------
    def _write_header(self, ws):
        """写入企业级模板表头"""
        headers = [
            "用例编号", "模块", "用例标题", "优先级", "前置条件",
            "测试步骤", "预期结果", "实际结果", "测试数据",
            "是否可自动化", "备注",
        ]
        header_fill = PatternFill(start_color="1976D2", end_color="1976D2", fill_type="solid")
        header_font = Font(name="Microsoft YaHei", size=11, bold=True, color="FFFFFF")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"),
        )

        for col_idx, text in enumerate(headers):
            cell = ws.cell(row=1, column=col_idx + 1, value=text)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
            cell.border = thin_border

        ws.row_dimensions[1].height = 30

    def _write_row(self, ws, row, case, precondition, enriched_step, actual_map, step_info_for_actual):
        """写入一行（一个步骤一行，用例级字段重复写入后合并）

        Args:
            ws: 工作表
            row: 行号（1-based）
            case: 用例字典
            precondition: 前置条件文本
            enriched_step: _enrich_steps 返回的某一步骤字典，或 None
            actual_map: _get_actual_results 返回的映射表
            step_info_for_actual: 用于查找实际结果的那个 step（传参方便合并时复用）
        """
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"),
        )
        data_font = Font(name="Microsoft YaHei", size=10)
        case_id_font = Font(name="Consolas", size=10, color="1976D2")
        header_fill = PatternFill(start_color="EBF5FB", end_color="EBF5FB", fill_type="solid")
        alt_fill = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid")
        data_align = Alignment(vertical="top", wrap_text=True)
        center_align = Alignment(horizontal="center", vertical="top", wrap_text=True)

        # 行背景交替色
        row_fill = alt_fill if (row % 2 == 0) else None

        # ---------- 步骤级字段 ----------
        case_id_str = f"TC_WEB_{case['id']:04d}"
        step_order = enriched_step['step']['step_order'] if enriched_step else ''
        step_desc = enriched_step['step_description'] if enriched_step else ''
        expected = enriched_step['expected_result'] if enriched_step else ''

        # 实际结果：优先从映射中按 step_order 查找
        actual_text = ''
        step_obj = enriched_step['step'] if enriched_step else None
        if step_obj:
            actual_text = actual_map.get(step_obj['step_order'], '')

        test_data = enriched_step['step'].get('input_value', '') if enriched_step else ''
        if not test_data and enriched_step and enriched_step['step']['action_type'] == 'open_url':
            test_data = case.get('start_url', '')

        remark = ''
        if enriched_step:
            remark = enriched_step['step'].get('description', '') or ''

        # ---------- 用例级字段 ----------
        case_vals = {
            self.COL_CASE_ID: case_id_str,
            self.COL_MODULE: '',
            self.COL_TITLE: case['name'],
            self.COL_PRIORITY: 'P2',
            self.COL_PRECONDITIONS: precondition,
            self.COL_AUTOMATABLE: '是',
            self.COL_REMARKS: case.get('description', '') or '',
        }

        # 组合所有列   0       1       2       3       4         5      6      7     8       9      10
        values = {**case_vals,
                  self.COL_STEPS: f"{step_order}. {step_desc}" if step_order else '',
                  self.COL_EXPECTED: expected,
                  self.COL_ACTUAL: actual_text,
                  self.COL_TEST_DATA: test_data,
                  self.COL_REMARKS: remark,  # 步骤级备注优先
                  }

        for col_idx in range(self.COL_COUNT):
            cell = ws.cell(row=row, column=col_idx + 1, value=values.get(col_idx, ''))
            cell.font = data_font
            cell.border = thin_border
            if col_idx == self.COL_CASE_ID:
                cell.font = case_id_font
            if col_idx in (self.COL_MODULE, self.COL_PRIORITY, self.COL_AUTOMATABLE):
                cell.alignment = center_align
            else:
                cell.alignment = data_align
            if row_fill:
                cell.fill = row_fill

    # ------------------------------------------------------------------
    #  列宽
    # ------------------------------------------------------------------
    def _apply_column_widths(self, ws):
        widths = {
            self.COL_CASE_ID + 1:         16,
            self.COL_MODULE + 1:          14,
            self.COL_TITLE + 1:           24,
            self.COL_PRIORITY + 1:         8,
            self.COL_PRECONDITIONS + 1:   36,
            self.COL_STEPS + 1:           44,
            self.COL_EXPECTED + 1:        36,
            self.COL_ACTUAL + 1:          26,
            self.COL_TEST_DATA + 1:       24,
            self.COL_AUTOMATABLE + 1:     12,
            self.COL_REMARKS + 1:         24,
        }
        for col_num, width in widths.items():
            ws.column_dimensions[get_column_letter(col_num)].width = width
