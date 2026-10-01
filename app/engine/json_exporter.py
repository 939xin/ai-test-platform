"""
JSON 测试用例导出器 — 企业级结构化格式

支持将 Web 测试用例导出为带完整企业模板字段的 JSON 文件，
也支持从 JSON 文件导入恢复用例（为后续扩展预留接口）。

格式示例:
```json
{
  "version": "1.0",
  "exported_at": "2026-07-11 14:30:00",
  "test_cases": [
    {
      "case_id": "TC_WEB_0001",
      "module": "",
      "title": "简单网页测试",
      "priority": "P2",
      "preconditions": "浏览器: Chrome | 起始URL: https://www.baidu.com",
      "automatable": true,
      "remarks": "",
      "steps": [
        {
          "step_order": 1,
          "description": "打开浏览器，访问 https://www.baidu.com",
          "locator": null,
          "test_data": "https://www.baidu.com",
          "expected_result": "页面 https://www.baidu.com 成功加载",
          "actual_result": ""
        },
        {
          "step_order": 2,
          "description": "在输入框(id=kw)中输入\"测试\"",
          "locator": {"type": "id", "value": "kw"},
          "test_data": "测试",
          "expected_result": "输入框(id=kw)显示\"测试\"",
          "actual_result": ""
        }
      ]
    }
  ]
}
```
"""
import os
import json
from datetime import datetime
from app.database.models import DBManager


# 操作类型 → 步骤描述模板（和 excel_exporter 保持一致）
_STEP_TEMPLATES = {
    'open_url':              '打开浏览器，访问 {input}',
    'click':                 '点击元素({locator})',
    'input':                 '在输入框({locator})中输入"{input}"',
    'clear':                 '清空输入框({locator})',
    'force_wait':            '等待 {wait} 秒',
    'smart_wait':            '等待元素({locator})出现（超时 {wait} 秒）',
    'switch_window':         '切换至第 {input} 个窗口',
    'switch_iframe':         '切换至 IFrame({locator})',
    'scroll_to':             '滚动到元素({locator})',
    'execute_js':            '执行 JavaScript：{input}',
    'screenshot':            '截图保存：{input}',
    'assert_text_contains':  '验证文本({locator})包含"{input}"',
    'assert_visible':        '验证元素({locator})可见',
    'assert_exists':         '验证元素({locator})存在',
    'extract_variable':      '提取变量"{input}" → 从元素({locator})',
}

_EXPECTED_TEMPLATES = {
    'open_url':              '页面 {input} 成功加载，URL 正确，页面标题正常显示',
    'click':                 '元素({locator})被成功点击，页面/状态正确响应',
    'input':                 '输入框({locator})成功输入"{input}"，显示内容正确',
    'clear':                 '输入框({locator})内容被成功清空',
    'force_wait':            '等待 {wait} 秒结束，页面无异常',
    'smart_wait':            '元素({locator})在 {wait} 秒内成功出现在页面中',
    'switch_window':         '成功切换至第 {input} 个窗口，页面内容正确',
    'switch_iframe':         '成功切换至 IFrame({locator})，可操作内部元素',
    'scroll_to':             '元素({locator})已滚动到可视区域内',
    'execute_js':            'JavaScript 执行成功，控制台无报错',
    'screenshot':            '截图"{input}"保存成功，图片清晰完整',
    'assert_text_contains':  '页面({locator})包含预期文本"{input}"，断言通过',
    'assert_visible':        '元素({locator})在页面上可见',
    'assert_exists':         '元素({locator})存在于 DOM 中',
    'extract_variable':      '变量"{input}"从元素({locator})提取成功，值正确',
}


class JSONExporter:
    """企业级 JSON 测试用例导出器"""

    def __init__(self):
        self.exports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'exports'
        )
        os.makedirs(self.exports_dir, exist_ok=True)

    def export_web_cases(self, case_ids: list, output_path: str = None) -> str:
        """导出 Web 测试用例到企业级 JSON 格式

        Args:
            case_ids: 要导出的用例 ID 列表
            output_path: 输出文件路径，为 None 时自动生成

        Returns:
            生成的文件绝对路径
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(self.exports_dir, f"web_cases_export_{timestamp}.json")

        cases_data = []
        for cid in case_ids:
            case = DBManager.fetch_one("SELECT * FROM web_test_cases WHERE id=?", (cid,))
            if not case:
                continue

            # 前置条件
            precondition = self._build_precondition(case)
            case_id_str = f"TC_WEB_{case['id']:04d}"

            # 步骤
            steps = DBManager.fetch_all(
                "SELECT * FROM web_steps WHERE case_id=? AND enabled=1 ORDER BY step_order",
                (cid,)
            )
            steps_data = []
            for step in steps:
                locators = DBManager.fetch_all(
                    "SELECT * FROM web_step_locators WHERE step_id=?", (step['id'],)
                )
                loc = locators[0] if locators else None

                action = step['action_type']
                input_val = step.get('input_value', '') or ''
                wait_val = step.get('wait_seconds', 0)

                # 定位器
                locator_data = None
                locator_text = ''
                if loc:
                    locator_data = {
                        'type': loc['locator_type'],
                        'value': loc['locator_value'],
                    }
                    locator_text = f"{loc['locator_type']}={loc['locator_value']}"

                # 步骤描述
                desc_tpl = _STEP_TEMPLATES.get(action, f'执行操作: {action}')
                step_desc = desc_tpl.format(input=input_val, locator=locator_text, wait=wait_val)
                if not locator_text and '{locator}' in desc_tpl:
                    import re
                    step_desc = re.sub(r'\(\)', '', step_desc).strip()

                # 预期结果
                exp_tpl = _EXPECTED_TEMPLATES.get(action, '操作执行成功，无异常')
                expected = exp_tpl.format(input=input_val, locator=locator_text, wait=wait_val)
                if not locator_text and '{locator}' in exp_tpl:
                    import re
                    expected = re.sub(r'\(\)', '', expected).strip()

                # 实际结果
                actual_result = ''
                test_data = input_val
                if not test_data and action == 'open_url':
                    test_data = case.get('start_url', '')

                steps_data.append({
                    'step_order': step['step_order'],
                    'description': step_desc,
                    'locator': locator_data,
                    'test_data': test_data,
                    'expected_result': expected,
                    'actual_result': actual_result,
                    'action_type': action,
                    'wait_seconds': wait_val,
                    'description_raw': step.get('description', '') or '',
                })

            cases_data.append({
                'case_id': case_id_str,
                'module': '',
                'title': case['name'],
                'priority': 'P2',
                'preconditions': precondition,
                'automatable': True,
                'remarks': case.get('description', '') or '',
                'steps': steps_data,
            })

        output = {
            'version': '1.0',
            'export_type': 'web_test_cases',
            'exported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'test_cases': cases_data,
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        return os.path.abspath(output_path)

    def _build_precondition(self, case: dict) -> str:
        """构建前置条件文本"""
        parts = []
        browser = case.get('browser', 'chrome').capitalize()
        parts.append(f"浏览器: {browser}")
        start_url = case.get('start_url', '') or ''
        if start_url:
            parts.append(f"起始URL: {start_url}")
        env_id = case.get('environment_id')
        if env_id:
            env = DBManager.fetch_one(
                "SELECT name, base_url FROM environments WHERE id=?", (env_id,)
            )
            if env:
                parts.append(f"环境: {env['name']} ({env['base_url']})")
        return " | ".join(parts)
