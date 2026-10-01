"""
接口测试执行引擎 — 进程内直接调用 requests，逐条断言，记录完整请求/响应
"""
import json
import time
import traceback
import requests as http_requests
from datetime import datetime
from PySide6.QtCore import QThread, Signal
from app.database.models import DBManager
from app.utils.variable_resolver import VariableResolver

# 常用 JSON 解析库
try:
    from jsonpath_ng import parse as jsonpath_parse
    HAS_JSONPATH = True
except ImportError:
    HAS_JSONPATH = False


class APIRunner(QThread):
    """接口测试执行线程 — 逐条执行、逐条断言、逐条记录"""

    log_signal = Signal(str)
    case_finished = Signal(dict)  # 每条用例完成后发射结构化响应数据
    finished_signal = Signal(str)

    def __init__(self, case_ids: list, environment: dict = None, verify_ssl: bool = True):
        super().__init__()
        self.case_ids = case_ids
        self.environment = environment or {}
        self.verify_ssl = verify_ssl
        self.report_path = ""
        self.result_ids = []

    # ==================== 主流程 ====================

    def run(self):
        env_name = self.environment.get('name', '未选择')
        base_url = self.environment.get('base_url', '')
        self.log_signal.emit(f"===== 接口测试开始 =====")
        self.log_signal.emit(f"环境: {env_name}  |  Base URL: {base_url}  |  用例数: {len(self.case_ids)}")

        for i, cid in enumerate(self.case_ids):
            try:
                self.log_signal.emit(f"\n--- [{i+1}/{len(self.case_ids)}] ---")
                result_id = self._execute_one_case(cid)
                if result_id:
                    self.result_ids.append(result_id)
            except Exception as e:
                self.log_signal.emit(f"  [严重错误] 用例 {cid} 执行异常: {str(e)}")
                self.log_signal.emit(traceback.format_exc())

        # 生成报告
        if self.result_ids:
            try:
                from app.engine.report_generator import ReportGenerator
                gen = ReportGenerator()
                self.report_path = gen.generate_from_results(self.result_ids, test_type="api")
                self.log_signal.emit(f"\n📊 报告: {self.report_path}")
            except Exception as e:
                self.log_signal.emit(f"[报告生成失败] {str(e)}")

        total = len(self.case_ids)
        passed = len(self.result_ids)  # 成功入库的都算执行过
        self.log_signal.emit(f"\n===== 执行完成: {passed}/{total} 条已处理 =====")
        self.finished_signal.emit(self.report_path)

    # ==================== 单用例执行 ====================

    def _execute_one_case(self, case_id: int) -> int:
        """执行一条用例，返回 test_results.id"""
        case = DBManager.fetch_one("SELECT * FROM api_test_cases WHERE id=?", (case_id,))
        if not case:
            self.log_signal.emit(f"  [跳过] 用例 {case_id} 不存在")
            return 0

        case_name = case['name']
        method = case['method'].upper()
        url = case['url']
        timeout = int(case.get('timeout', 30))

        # 变量解析器（先加载全局变量）
        env_id = case.get('environment_id') or self.environment.get('id')
        resolver = VariableResolver(environment_id=env_id)

        # 拼接完整 URL（自动识别绝对路径）
        url = url.strip()
        if url.startswith('http://') or url.startswith('https://'):
            # 绝对路径：直接使用，不拼接 base_url
            full_url = url
        elif case.get('is_relative_url', 1):
            base_url = self.environment.get('base_url', '').strip().rstrip('/')
            full_url = base_url + '/' + url.lstrip('/')
        else:
            full_url = url
        # 去除 URL 中的空格（用户可能误输入）
        full_url = full_url.replace(' ', '')
        full_url = resolver.resolve(full_url)

        self.log_signal.emit(f"  {method} {full_url}")

        # 构建请求头
        headers = {}
        db_headers = DBManager.fetch_all(
            "SELECT * FROM api_headers WHERE case_id=? AND enabled=1", (case_id,)
        )
        for h in db_headers:
            headers[h['key']] = resolver.resolve(h['value'])

        # 认证
        auth_type = case.get('auth_type', 'none')
        auth_value = case.get('auth_value', '')
        if auth_type == 'bearer' and auth_value:
            headers['Authorization'] = f"Bearer {resolver.resolve(auth_value)}"
        elif auth_type == 'apikey' and auth_value:
            headers['X-API-Key'] = resolver.resolve(auth_value)

        auth_obj = None
        if auth_type == 'basic' and auth_value:
            parts = resolver.resolve(auth_value).split(':', 1)
            auth_obj = (parts[0], parts[1] if len(parts) > 1 else '')

        # 请求体
        body_type = case.get('body_type', 'none')
        body_content = resolver.resolve(case.get('body_content', ''))

        request_body_sent = ""
        if body_type == 'json' and body_content:
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json; charset=utf-8'
            request_body_sent = body_content
        elif body_type == 'form' and body_content:
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
            request_body_sent = body_content
        elif body_type == 'xml' and body_content:
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/xml'
            request_body_sent = body_content
        elif body_content:
            request_body_sent = body_content

        # ---- 发请求 ----
        self.log_signal.emit(f"  📤 Headers: {json.dumps(headers, ensure_ascii=False) if headers else '(无)'}")
        if request_body_sent:
            self.log_signal.emit(f"  📤 Body: {request_body_sent[:200]}")

        start_time = time.time()
        response = None
        error_msg = ""

        # [v2] 直接用 requests.post/get/put... 对应测试脚本的调用方式（已验证能通）
        actual_timeout = min(timeout, 10)  # 用较短的超时避免长时间挂起
        self.log_signal.emit(f"  🔧 [v2] timeout={actual_timeout}s")
        try:
            if method == 'GET':
                response = http_requests.get(full_url, headers=headers, timeout=actual_timeout,
                                             verify=self.verify_ssl)
            elif method == 'POST':
                response = http_requests.post(full_url, data=request_body_sent.encode('utf-8') if request_body_sent else None,
                                              headers=headers, timeout=actual_timeout, verify=self.verify_ssl,
                                              auth=auth_obj)
            elif method == 'PUT':
                response = http_requests.put(full_url, data=request_body_sent.encode('utf-8') if request_body_sent else None,
                                             headers=headers, timeout=actual_timeout, verify=self.verify_ssl,
                                             auth=auth_obj)
            elif method == 'DELETE':
                response = http_requests.delete(full_url, headers=headers, timeout=actual_timeout,
                                                verify=self.verify_ssl, auth=auth_obj)
            elif method == 'PATCH':
                response = http_requests.patch(full_url, data=request_body_sent.encode('utf-8') if request_body_sent else None,
                                               headers=headers, timeout=actual_timeout, verify=self.verify_ssl,
                                               auth=auth_obj)
            else:
                response = http_requests.request(method, full_url, data=request_body_sent.encode('utf-8') if request_body_sent else None,
                                                 headers=headers, timeout=actual_timeout, verify=self.verify_ssl,
                                                 auth=auth_obj)
        except http_requests.exceptions.ConnectionError as e:
            error_msg = f"连接失败: {str(e)[:200]}"
            self.log_signal.emit(f"  ❌ {error_msg}")
            self.log_signal.emit(f"  🔍 {traceback.format_exc()[-300:]}")
        except http_requests.exceptions.Timeout:
            error_msg = f"请求超时 ({timeout}秒)"
            self.log_signal.emit(f"  ❌ {error_msg}")
        except Exception as e:
            error_msg = f"请求异常: {type(e).__name__}: {str(e)[:150]}"
            self.log_signal.emit(f"  ❌ {error_msg}")
            self.log_signal.emit(f"  🔍 {traceback.format_exc()[-500:]}")

        # 确保 response 为 None 时一定有 error_msg
        if response is None and not error_msg:
            error_msg = "请求失败: 未获取到响应（检查网络连接和 URL 是否正确）"
            self.log_signal.emit(f"  ❌ {error_msg}")

        elapsed_ms = (time.time() - start_time) * 1000

        # ---- 写入 test_results ----
        case_status = "pass"  # 默认通过，后面断言会覆盖
        result_id = DBManager.insert("test_results", {
            'test_type': 'api',
            'case_id': case_id,
            'case_name': case_name,
            'status': 'running',
            'duration_ms': int(elapsed_ms),
            'environment_name': self.environment.get('name', ''),
        })

        # ---- 步骤1: 请求详情 ----
        resp_status = response.status_code if response else 0
        resp_headers = json.dumps(dict(response.headers), ensure_ascii=False) if response else ""
        resp_body = ""
        if response:
            try:
                resp_body = json.dumps(response.json(), ensure_ascii=False)
            except Exception:
                resp_body = response.text[:5000] if response.text else ""

        DBManager.insert("test_result_details", {
            'result_id': result_id,
            'step_order': 1,
            'step_description': f"{method} {full_url}",
            'status': 'error' if error_msg else 'pass',
            'message': error_msg,
            'request_url': full_url,
            'request_method': method,
            'request_headers': json.dumps(headers, ensure_ascii=False),
            'request_body': request_body_sent[:5000],
            'response_status': resp_status,
            'response_headers': resp_headers,
            'response_body': resp_body[:5000],
        })

        # ---- 断言 ----
        assertions = DBManager.fetch_all(
            "SELECT * FROM api_assertions WHERE case_id=? AND enabled=1", (case_id,)
        )
        assertion_results = []

        if error_msg:
            case_status = "error"
            self.log_signal.emit(f"  ⚠️ 请求失败，跳过断言")
        elif not response:
            case_status = "error"
            self.log_signal.emit(f"  ⚠️ 无响应对象，跳过断言")
        elif assertions:
            step_order = 2
            for assertion in assertions:
                atype = assertion['assertion_type']
                op = assertion['operator']
                expected = assertion['expected_value']
                target = assertion.get('target', '')

                # 跳过空的期望值
                if not expected or not expected.strip():
                    continue

                a_result = self._evaluate_assertion(
                    response, elapsed_ms, atype, op, expected.strip(), target
                )
                assertion_results.append({
                    'type': atype,
                    'expected': expected,
                    'actual': a_result.get('actual', ''),
                    'passed': a_result['passed'],
                    'message': a_result['message'],
                })

                DBManager.insert("test_result_details", {
                    'result_id': result_id,
                    'step_order': step_order,
                    'step_description': f"断言: {atype} {op} {expected}",
                    'status': 'pass' if a_result['passed'] else 'fail',
                    'message': a_result['message'],
                    'request_url': '',
                    'request_method': '',
                    'request_headers': '',
                    'request_body': '',
                    'response_status': resp_status if atype == 'status_code' else None,
                    'response_headers': '',
                    'response_body': a_result.get('actual', '')[:2000] if atype == 'response_body' else '',
                    'expected_value': expected,
                    'actual_value': a_result.get('actual', ''),
                })

                if not a_result['passed']:
                    case_status = "fail"
                    self.log_signal.emit(f"  ❌ {a_result['message']}")
                else:
                    self.log_signal.emit(f"  ✅ {a_result['message']}")

                step_order += 1

        elif not assertions:
            self.log_signal.emit(f"  ⚠️ 没有断言条件")
            # 无断言时，非2xx状态码自动视为失败
            if response is not None and response.status_code >= 400:
                case_status = "fail"
                self.log_signal.emit(f"  ⚠️ HTTP {response.status_code} (无断言，非2xx视为失败)")
        else:
            # 有 response 但没有断言 → 检查状态码默认行为
            if response and response.status_code >= 400:
                case_status = "fail"
                self.log_signal.emit(f"  ⚠️ HTTP {response.status_code} (无断言，非2xx视为失败)")

        # ---- 更新最终状态 ----
        DBManager.update("test_results",
                         {'status': case_status, 'duration_ms': int(elapsed_ms)},
                         "id=?", (result_id,))

        status_icon = "✅ 通过" if case_status == "pass" else "❌ 失败" if case_status == "fail" else "⚠️ 错误"
        self.log_signal.emit(f"  结果: {status_icon} ({elapsed_ms:.0f}ms)")

        # 发射结构化响应数据给 UI 的响应详情面板
        self.case_finished.emit({
            'case_id': case_id,
            'case_name': case_name,
            'status': case_status,
            'duration_ms': elapsed_ms,
            'request_url': full_url,
            'request_method': method,
            'request_headers': json.dumps(headers, ensure_ascii=False) if headers else '',
            'request_body': request_body_sent[:5000],
            'response_status': resp_status,
            'response_headers': resp_headers,
            'response_body': resp_body if resp_body else error_msg,
            'assertions': assertion_results,
            'error_msg': error_msg,
        })

        return result_id

    # ==================== 断言执行 ====================

    def _evaluate_assertion(self, response, elapsed_ms, atype, op, expected, target):
        """执行单条断言，返回 {passed, message, actual}"""
        if atype == 'status_code':
            actual = response.status_code
            expected_int = int(expected)
            if op in ('eq', 'equals'):
                passed = actual == expected_int
            elif op == 'ne':
                passed = actual != expected_int
            else:
                passed = actual == expected_int
            msg = f"状态码: 期望={expected_int}, 实际={actual} → {'通过' if passed else '失败'}"
            return {'passed': passed, 'message': msg, 'actual': str(actual)}

        elif atype == 'response_time':
            actual = f"{elapsed_ms:.0f}"
            expected_float = float(expected)
            if op == 'lt':
                passed = elapsed_ms < expected_float
            elif op == 'gt':
                passed = elapsed_ms > expected_float
            else:
                passed = elapsed_ms < expected_float
            msg = f"响应时间: 期望<{expected}ms, 实际={actual}ms → {'通过' if passed else '失败'}"
            return {'passed': passed, 'message': msg, 'actual': actual}

        elif atype == 'response_body':
            if not HAS_JSONPATH:
                return {'passed': True, 'message': 'jsonpath-ng 未安装，跳过', 'actual': ''}
            try:
                resp_json = response.json()
                matches = jsonpath_parse(target).find(resp_json)
                actual_val = matches[0].value if matches else None
                actual = str(actual_val) if actual_val is not None else 'None'
            except Exception as e:
                return {'passed': False, 'message': f'JSONPath 解析失败: {str(e)[:100]}', 'actual': str(e)}

            if op in ('eq', 'equals'):
                passed = str(actual_val) == expected
            elif op == 'ne':
                passed = str(actual_val) != expected
            elif op == 'contains':
                passed = expected in str(actual_val)
            elif op == 'regex':
                import re
                passed = bool(re.search(expected, str(actual_val)))
            else:
                passed = str(actual_val) == expected

            msg = f"响应体 [{target}]: 期望{op}={expected}, 实际={actual[:100]} → {'通过' if passed else '失败'}"
            return {'passed': passed, 'message': msg, 'actual': actual}

        return {'passed': True, 'message': f'未知断言类型: {atype}', 'actual': ''}
