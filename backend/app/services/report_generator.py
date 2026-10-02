"""HTML 测试报告生成 —— 移植自旧项目 app/engine/report_generator.py 的 _build_html()。

旧实现（内联字符串拼接，docstring 里写的 Jinja2 其实没用到）只吃「已组装好的 dict」，
与数据库完全解耦，所以 HTML 部分整段复用，只换了配色以匹配新平台的设计令牌。
新的取数与 dict 组装放在本文件下半部分。

数据形状映射：
    旧模型  一个 test_result  → 若干 test_result_details（步骤级）
    新模型  一条 execution    → 一次请求 + N 条断言
    因此「一条 execution」对应旧模型的「一个用例 + 若干 detail」，
    请求/响应信息挂在第 1 条 detail 上，断言逐条展开。
"""
import json
import platform
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Execution, Project, TestCase


def _pretty(value) -> str:
    """请求头 / 请求体 / 响应体统一转成可读文本。"""
    if value is None or value == "":
        return "-"
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def _execution_to_case(execution: Execution, case_name: str) -> dict:
    """把一条 execution 组装成 _build_html 期望的「用例」dict。"""
    rj = execution.result_json or {}
    request = rj.get("request") or {}
    response = rj.get("response") or {}
    assertions = rj.get("assertions") or []
    error_msg = rj.get("error_msg") or ""

    # 没有断言时也留一行，报告里能看出「这条没写断言」
    rows = assertions or [None]
    details: list[dict] = []

    for index, rule in enumerate(rows, start=1):
        if rule is None:
            detail = {
                "step_order": 1,
                "step_description": "执行结果",
                "status": execution.status,
                "message": error_msg or "该用例没有断言条件",
            }
        else:
            detail = {
                "step_order": index,
                "step_description": f"断言 {index}",
                "status": "pass" if rule.get("passed") else "fail",
                "message": rule.get("message", ""),
                "expected_value": rule.get("expected", ""),
                "actual_value": rule.get("actual", ""),
            }

        # 请求/响应整段只挂第一条，避免报告里重复 N 遍
        if index == 1:
            detail.update({
                "id": execution.id,
                "request_method": request.get("method", ""),
                "request_url": request.get("url", ""),
                "request_headers": _pretty(request.get("headers")),
                "request_body": _pretty(request.get("body")),
                "response_status": response.get("status"),
                "response_body": _pretty(response.get("body")),
                "screenshots": [],
            })
        else:
            detail["id"] = execution.id

        if error_msg:
            detail["message"] = f"{detail.get('message', '')} | {error_msg}".strip(" |")

        details.append(detail)

    return {
        "case_name": case_name,
        "status": execution.status,
        "duration_ms": execution.duration_ms,
        "details": details,
    }


def _build_html(results: list[dict], stats: dict) -> str:
    """构建完整的 HTML 报告 —— 主体照搬旧实现，配色换成新平台的设计令牌。"""
    cases_html = ""
    for r in results:
        status_class = "pass" if r['status'] == 'pass' else "fail" if r['status'] in ('fail', 'error') else "skip"
        status_text = "✅ 通过" if r['status'] == 'pass' else "❌ 失败" if r['status'] == 'fail' else "⚠️ 错误" if r['status'] == 'error' else "⏭ 跳过"
        badge_color = "#2e9e6b" if r['status'] == 'pass' else "#d64545" if r['status'] == 'fail' else "#d98c1f" if r['status'] == 'error' else "#7a8b94"

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

                # 截图嵌入（Web 用例用，接口用例恒为空）
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
    background: #f4f7f8;
    color: #2c3e44;
    padding: 20px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
.header {{
    background: linear-gradient(135deg, #16697A, #12525F);
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
.stat-card .stat-label {{ font-size: 13px; color: #7a8b94; }}
.stat-card.total .stat-value {{ color: #16697A; }}
.stat-card.pass .stat-value {{ color: #2e9e6b; }}
.stat-card.fail .stat-value {{ color: #d64545; }}
.stat-card.skip .stat-value {{ color: #7a8b94; }}
.stat-card.rate .stat-value {{ color: #d98c1f; }}
.env-info {{
    background: white;
    padding: 16px 20px;
    border-radius: 10px;
    margin-bottom: 24px;
    display: flex;
    gap: 32px;
    flex-wrap: wrap;
    font-size: 13px;
    color: #5a6b73;
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
    border-bottom: 1px solid #eef2f3;
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
.case-duration {{ color: #7a8b94; font-size: 13px; }}
.detail-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}
.detail-table th {{
    background: #f7f9fa;
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
    color: #5a6b73;
    border-bottom: 1px solid #e3e9eb;
}}
.detail-table td {{
    padding: 10px 12px;
    border-bottom: 1px solid #f2f5f6;
    vertical-align: top;
}}
.detail-row:hover {{ background: #f7f9fa; }}
.request-block {{
    background: #f7f9fa;
    border: 1px solid #e3e9eb;
    border-radius: 6px;
    padding: 12px;
    margin: 8px 0;
    font-size: 12px;
}}
.request-block pre {{
    background: #eef2f3;
    padding: 8px;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 11px;
    max-height: 200px;
    overflow-y: auto;
    margin: 4px 0;
}}
.assertion-block {{
    background: #fdf6e8;
    border: 1px solid #eed9b0;
    border-radius: 6px;
    padding: 10px 12px;
    margin: 6px 0;
}}
.assertion-block code {{
    background: #eef2f3;
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
    color: #9aa8ae;
    font-size: 12px;
}}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>📊 测试报告</h1>
        <p>项目: {stats['project_name']} | 类型: {stats['test_type'].upper()} | 生成时间: {stats['generated_at']}</p>
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
        <span>🕐 生成时间: {stats['generated_at']}</span>
        <span>💻 OS: {stats['os']}</span>
        <span>🐍 Python: {stats['python_version']}</span>
        <span>⏱ 总耗时: {stats['total_duration']}ms</span>
    </div>
    <h2 style="margin-bottom:16px; font-size:18px; color:#3c4c53;">📋 用例详情</h2>
    {cases_html}
    <div class="footer">
        ⚡ AI 辅助软件测试平台 | 报告自动生成
    </div>
</div>
</body>
</html>"""


def build_report(db: Session, execution_ids: list[int], test_type: str = "api") -> dict:
    """按执行记录生成 HTML 报告，写入 settings.report_dir。

    返回 {filename, path, stats}；execution_ids 为空或全部不存在时抛 ValueError。
    """
    executions = db.execute(
        select(Execution).where(Execution.id.in_(execution_ids)).order_by(Execution.id)
    ).scalars().all()
    if not executions:
        raise ValueError("没有找到对应的执行记录")

    name_map = dict(
        db.execute(
            select(TestCase.id, TestCase.name).where(
                TestCase.id.in_({e.case_id for e in executions if e.case_id is not None})
            )
        ).all()
    )

    results = [
        _execution_to_case(e, name_map.get(e.case_id) or f"已删除用例 #{e.case_id}")
        for e in executions
    ]

    total = len(results)
    passed = sum(1 for r in results if r['status'] == 'pass')
    failed = sum(1 for r in results if r['status'] in ('fail', 'error'))
    skipped = sum(1 for r in results if r['status'] == 'skip')
    rate = f"{(passed / total * 100):.1f}%" if total > 0 else "0%"

    project = db.get(Project, executions[0].project_id)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    stats = {
        'total': total, 'passed': passed, 'failed': failed, 'skipped': skipped,
        'rate': rate,
        'total_duration': sum(r.get('duration_ms', 0) for r in results),
        'test_type': test_type,
        'project_name': project.name if project else "未知项目",
        'generated_at': generated_at,
        'os': platform.system(),
        'python_version': platform.python_version(),
    }

    report_dir = Path(settings.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = f"r{execution_ids[0]}" if len(execution_ids) == 1 else f"r{len(execution_ids)}cases"
    filename = f"report_{test_type}_{tag}_{timestamp}.html"
    path = report_dir / filename
    path.write_text(_build_html(results, stats), encoding="utf-8")

    return {"filename": filename, "path": str(path), "stats": stats}
