"""报告 HTML 生成单元测试。

只喂最小的 results / stats 给 _build_html()，不查库、不落盘。
"""
from app.services.report_generator import _build_html


def _stats(**overrides):
    stats = {
        "total": 1, "passed": 1, "failed": 0, "skipped": 0, "rate": "100.0%",
        "total_duration": 120, "test_type": "api",
        "project_name": "演示项目",
        "generated_at": "2026-10-22 10:00:00",
        "os": "Windows", "python_version": "3.11",
    }
    stats.update(overrides)
    return stats


def _result(**overrides):
    result = {
        "case_name": "登录成功",
        "status": "pass",
        "duration_ms": 120,
        "details": [{
            "step_order": 1,
            "step_description": "断言 1",
            "status": "pass",
            "message": "状态码: 期望=200, 实际=200 → 通过",
            "expected_value": "200",
            "actual_value": "200",
            "id": 1,
            "request_method": "GET",
            "request_url": "https://example.com/login",
            "request_headers": "{}",
            "request_body": "-",
            "response_status": 200,
            "response_body": '{"ok": true}',
            "screenshots": [],
        }],
    }
    result.update(overrides)
    return result


def test_build_html_contains_case_name_and_status():
    html = _build_html([_result()], _stats())
    assert "登录成功" in html
    assert "✅ 通过" in html
    assert "项目: 演示项目" in html


def test_build_html_handles_empty_details():
    html = _build_html([_result(details=[])], _stats())
    assert "登录成功" in html


def test_build_html_handles_error_status():
    html = _build_html([_result(status="error", details=[])], _stats())
    assert "⚠️ 错误" in html


# ---------- P0-3：全量转义（报告路由免鉴权，必须挡住存储型 XSS） ----------

def _with_detail(**overrides):
    detail = dict(_result()["details"][0])
    detail.update(overrides)
    return [_result(details=[detail])]


def test_response_body_script_is_escaped():
    html = _build_html(_with_detail(response_body='</pre><script>alert(1)</script>'), _stats())
    assert "&lt;script&gt;" in html
    assert "<script>alert" not in html


def test_assertion_message_is_escaped():
    html = _build_html(_with_detail(message='<img src=x onerror=alert(1)>'), _stats())
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "<img src=x onerror" not in html


def test_case_name_and_project_name_are_escaped():
    html = _build_html(
        [_result(case_name='<b>用例</b>', details=[])],
        _stats(project_name='<i>项目</i>'),
    )
    assert "&lt;b&gt;用例&lt;/b&gt;" in html
    assert "&lt;i&gt;项目&lt;/i&gt;" in html
    assert "<b>用例</b>" not in html


def test_screenshot_src_is_escaped():
    html = _build_html(
        _with_detail(screenshots=['x.png" onerror="alert(1)']), _stats()
    )
    assert 'onerror="alert(1)"' not in html


def test_chinese_and_multiline_stay_readable():
    body = "第一行\n第二行：\"引号\" & 符号"
    html = _build_html(_with_detail(response_body=body), _stats())
    assert "第一行\n第二行" in html          # <pre> 保留换行，没有换成 <br>
    assert "&quot;引号&quot;" in html
    assert "&amp; 符号" in html
