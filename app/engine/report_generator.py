"""
HTML 测试报告生成器 — 基于 Jinja2 模板生成美观的测试报告
"""
import os
import json
import base64
import platform
from datetime import datetime
from app.database.models import DBManager


class ReportGenerator:
    """测试报告生成器"""

    def __init__(self):
        self.template_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'templates'
        )
        self.reports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'reports'
        )
        os.makedirs(self.reports_dir, exist_ok=True)

    def generate_from_results(self, result_ids: list, test_type: str = "api") -> str:
        """从测试结果 ID 列表生成 HTML 报告"""
        results = []
        for rid in result_ids:
            r = DBManager.fetch_one("SELECT * FROM test_results WHERE id=?", (rid,))
            if r:
                details = DBManager.fetch_all(
                    "SELECT * FROM test_result_details WHERE result_id=? ORDER BY step_order",
                    (rid,)
                )
                # 加载截图
                for d in details:
                    screenshots = DBManager.fetch_all(
                        "SELECT * FROM screenshots WHERE result_detail_id=?",
                        (d['id'],)
                    )
                    d['screenshots'] = [s['image_base64'] for s in screenshots]
                r['details'] = details
                results.append(r)

        total = len(results)
        passed = sum(1 for r in results if r['status'] == 'pass')
        failed = sum(1 for r in results if r['status'] in ('fail', 'error'))
        skipped = sum(1 for r in results if r['status'] == 'skip')
        rate = f"{(passed / total * 100):.1f}%" if total > 0 else "0%"
        total_duration = sum(r.get('duration_ms', 0) for r in results)

        html = self._build_html(results, {
            'total': total, 'passed': passed, 'failed': failed,
            'skipped': skipped, 'rate': rate, 'total_duration': total_duration,
            'test_type': test_type,
            'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'os': platform.system(),
            'os_version': platform.version(),
            'python_version': platform.python_version(),
        })

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rid_tag = f"r{result_ids[0]}" if len(result_ids) == 1 else f"r{len(result_ids)}cases"
        report_name = f"{test_type}_report_{rid_tag}_{timestamp}.html"
        report_path = os.path.join(self.reports_dir, report_name)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return report_path

    def _build_html(self, results: list, stats: dict) -> str:
        """构建完整的 HTML 报告"""
        cases_html = ""
        for i, r in enumerate(results):
            status_class = "pass" if r['status'] == 'pass' else "fail" if r['status'] in ('fail','error') else "skip"
            status_text = "✅ 通过" if r['status'] == 'pass' else "❌ 失败" if r['status'] == 'fail' else "⚠️ 错误" if r['status'] == 'error' else "⏭ 跳过"
            badge_color = "#4caf50" if r['status'] == 'pass' else "#f44336" if r['status'] == 'fail' else "#ff9800" if r['status'] == 'error' else "#9e9e9e"

            details_html = ""
            if r.get('details'):
                for d in r['details']:
                    d_status = "✅" if d['status'] == 'pass' else "❌"
                    details_html += f"""
                    <tr class="detail-row">
                        <td style="text-align:center">{d.get('step_order', '-')}</td>
                        <td>{d.get('step_description', '-')}</td>
                        <td style="text-align:center">{d_status}</td>
                        <td>{d.get('message', '') or '-'}</td>
                    </tr>"""

                    # 接口用例：显示请求/响应信息
                    if d.get('request_url'):
                        resp_status = d.get('response_status')
                        resp_status_str = str(resp_status) if resp_status else '-'
                        resp_body = d.get('response_body', '') or ''
                        err_msg = d.get('message', '') or ''

                        # 如果有错误信息且无响应体，显示错误
                        if not resp_body and err_msg:
                            resp_body_display = f'[请求失败] {err_msg}'
                        else:
                            resp_body_display = resp_body[:3000] if resp_body else '(空)'

                        details_html += f"""
                    <tr class="request-detail">
                        <td colspan="4">
                            <div class="request-block">
                                <strong>📡 请求:</strong> {d.get('request_method', 'GET')} {d.get('request_url', '')}<br>
                                <strong>📨 请求头:</strong> <pre>{d.get('request_headers', '-')}</pre>
                                <strong>📦 请求体:</strong> <pre>{d.get('request_body', '-')}</pre>
                                <strong>📥 响应状态:</strong> {resp_status_str}<br>
                                <strong>📥 响应体:</strong> <pre>{resp_body_display}</pre>
                            </div>
                        </td>
                    </tr>"""

                    # 断言行：显示期望值 vs 实际值
                    if d.get('expected_value'):
                        exp = d.get('expected_value', '-')
                        act = d.get('actual_value', '-')
                        a_status = '✅ 通过' if d.get('status') == 'pass' else '❌ 失败'
                        details_html += f"""
                    <tr class="assertion-detail">
                        <td colspan="4">
                            <div class="assertion-block">
                                <strong>{a_status}:</strong> 期望值=<code>{exp}</code> 实际值=<code>{act}</code><br>
                                <span style="color:#757575;font-size:12px;">{d.get('message', '')}</span>
                            </div>
                        </td>
                    </tr>"""

                    # 截图嵌入
                    if d.get('screenshots'):
                        for s_b64 in d['screenshots']:
                            details_html += f"""
                    <tr class="screenshot-row">
                        <td colspan="4">
                            <div class="screenshot-block">
                                <strong>📸 截图:</strong><br>
                                <a href="data:image/png;base64,{s_b64}" target="_blank">
                                    <img src="data:image/png;base64,{s_b64}"
                                         style="max-width:400px; cursor:pointer; border:1px solid #ddd; border-radius:4px;"
                                         onclick="this.style.maxWidth=this.style.maxWidth==='400px'?'100%':'400px'"
                                         title="点击放大/缩小">
                                </a>
                            </div>
                        </td>
                    </tr>"""

            cases_html += f"""
            <div class="case-card">
                <div class="case-header">
                    <span class="case-name">📋 {r['case_name']}</span>
                    <span class="case-status" style="background:{badge_color}">{status_text}</span>
                    <span class="case-duration">{r.get('duration_ms', 0)}ms</span>
                </div>
                <table class="detail-table">
                    <thead>
                        <tr>
                            <th style="width:60px">序号</th>
                            <th>步骤/描述</th>
                            <th style="width:60px">状态</th>
                            <th>详情</th>
                        </tr>
                    </thead>
                    <tbody>{details_html}</tbody>
                </table>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>测试报告 - {stats['generated_at']}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
    background: #f5f7fa;
    color: #333;
    padding: 20px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
.header {{
    background: linear-gradient(135deg, #1976D2, #1565C0);
    color: white;
    padding: 30px 40px;
    border-radius: 12px;
    margin-bottom: 24px;
}}
.header h1 {{ font-size: 24px; margin-bottom: 8px; }}
.header p {{ opacity: 0.85; font-size: 14px; }}
.stats-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}}
.stat-card {{
    background: white;
    padding: 20px;
    border-radius: 10px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
.stat-card .stat-value {{ font-size: 28px; font-weight: bold; margin-bottom: 4px; }}
.stat-card .stat-label {{ font-size: 13px; color: #757575; }}
.stat-card.total .stat-value {{ color: #1976D2; }}
.stat-card.pass .stat-value {{ color: #4caf50; }}
.stat-card.fail .stat-value {{ color: #f44336; }}
.stat-card.skip .stat-value {{ color: #9e9e9e; }}
.stat-card.rate .stat-value {{ color: #ff9800; }}
.env-info {{
    background: white;
    padding: 16px 20px;
    border-radius: 10px;
    margin-bottom: 24px;
    display: flex;
    gap: 32px;
    flex-wrap: wrap;
    font-size: 13px;
    color: #616161;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
.env-info span {{ display: inline-flex; align-items: center; gap: 4px; }}
.case-card {{
    background: white;
    border-radius: 10px;
    margin-bottom: 16px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
.case-header {{
    display: flex;
    align-items: center;
    padding: 14px 20px;
    border-bottom: 1px solid #f0f0f0;
    gap: 12px;
}}
.case-name {{ flex: 1; font-weight: 500; font-size: 14px; }}
.case-status {{
    padding: 4px 14px;
    border-radius: 12px;
    color: white;
    font-size: 12px;
    font-weight: bold;
}}
.case-duration {{ color: #757575; font-size: 13px; }}
.detail-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}
.detail-table th {{
    background: #fafafa;
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
    color: #616161;
    border-bottom: 1px solid #e0e0e0;
}}
.detail-table td {{
    padding: 10px 12px;
    border-bottom: 1px solid #f5f5f5;
    vertical-align: top;
}}
.detail-row:hover {{ background: #fafafa; }}
.request-block {{
    background: #fafafa;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 12px;
    margin: 8px 0;
    font-size: 12px;
}}
.request-block pre {{
    background: #f0f0f0;
    padding: 8px;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 11px;
    max-height: 200px;
    overflow-y: auto;
    margin: 4px 0;
}}
.assertion-block {{
    background: #fff8e1;
    border: 1px solid #ffe082;
    border-radius: 6px;
    padding: 10px 12px;
    margin: 6px 0;
}}
.assertion-block code {{
    background: #f5f5f5;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 12px;
}}
.screenshot-block {{
    padding: 8px 0;
}}
.footer {{
    text-align: center;
    padding: 24px;
    color: #9e9e9e;
    font-size: 12px;
}}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>📊 测试报告</h1>
        <p>类型: {stats['test_type'].upper()} | 生成时间: {stats['generated_at']}</p>
    </div>
    <div class="stats-grid">
        <div class="stat-card total">
            <div class="stat-value">{stats['total']}</div>
            <div class="stat-label">总用例数</div>
        </div>
        <div class="stat-card pass">
            <div class="stat-value">{stats['passed']}</div>
            <div class="stat-label">通过</div>
        </div>
        <div class="stat-card fail">
            <div class="stat-value">{stats['failed']}</div>
            <div class="stat-label">失败</div>
        </div>
        <div class="stat-card skip">
            <div class="stat-value">{stats['skipped']}</div>
            <div class="stat-label">跳过</div>
        </div>
        <div class="stat-card rate">
            <div class="stat-value">{stats['rate']}</div>
            <div class="stat-label">通过率</div>
        </div>
    </div>
    <div class="env-info">
        <span>🕐 执行时间: {stats['generated_at']}</span>
        <span>💻 OS: {stats['os']}</span>
        <span>🐍 Python: {stats['python_version']}</span>
        <span>⏱ 总耗时: {stats['total_duration']}ms</span>
    </div>
    <h2 style="margin-bottom:16px; font-size:18px; color:#424242;">📋 用例详情</h2>
    {cases_html}
    <div class="footer">
        ⚡ 接口自动化测试工具 v1.0.0 | 报告自动生成
    </div>
</div>
<script>
// 点击截图放大
document.querySelectorAll('.screenshot-block img').forEach(img => {{
    img.addEventListener('click', function() {{
        if (this.style.maxWidth === '100%') {{
            this.style.maxWidth = '400px';
        }} else {{
            this.style.maxWidth = '100%';
        }}
    }});
}});
</script>
</body>
</html>"""
