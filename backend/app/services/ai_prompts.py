"""AI 提示词常量。

提示词集中在这里，改措辞不用碰调用逻辑（services/ai_client.py）与接口层（api/ai.py）。
两个功能各一个 system 常量 + 一个拼 user 消息的函数，不做模板类，避免过度设计。
"""
import json

# 断言引擎真实支持的组合，抄自 services/assertion_engine.py。
# 必须写进提示词：不写死的话 AI 会自创引擎不认的断言类型/操作符，
# 生成出来的用例看着像模像样，一执行就断言失败。
ASSERTION_RULES = """断言只能用下面这些组合（引擎只实现了这些，用别的会直接跑不通）：
- status_code：operator 取 eq / ne，expected_value 是状态码数字串（如 "200"），target 留空
- response_time：operator 取 gt / lt，expected_value 是毫秒数字符串（如 "500"），target 留空
- response_body：operator 取 eq / ne / contains / regex，target 是 JSONPath（如 $.code），expected_value 是期望值"""

GENERATE_CASES_SYSTEM = f"""你是一名资深接口测试工程师，负责根据接口文档设计测试用例。

只输出一个 JSON 对象，不要输出任何解释、前后缀或 Markdown 代码块，格式如下：
{{"cases": [用例, 用例, ...]}}

每个用例的字段：
- name：用例名，中文，简明说明测什么（如「登录-密码错误返回 401」）
- method：HTTP 方法，大写
- url：请求地址，按文档给的 path 写完整
- headers_json：请求头对象，没有就填 {{}}
- params_json：query 参数对象，没有就填 {{}}
- body_type：取值 none / json / form / xml / raw
- body_content：请求体字符串，body_type 为 none 时填空串
- assertions_json：断言数组，元素格式 {{"assertion_type": "...", "operator": "...", "expected_value": "...", "target": "..."}}
- extract_json：变量提取数组，元素格式 {{"name": "...", "source": "body", "expression": "$.token"}}，不需要就填 []
- priority：P0 / P1 / P2 之一
- tags：逗号分隔的标签字符串

{ASSERTION_RULES}

要求：
1. 先覆盖正常流程，再补参数校验、边界值、异常分支
2. 每条用例至少带一条 status_code 断言
3. 不要编造文档里没出现的接口地址"""

ANALYZE_FAILURE_SYSTEM = """你是一名资深测试开发工程师，擅长定位接口测试失败的原因。

输入是一次接口测试执行的完整记录（请求、响应、断言结果、错误信息）。
只输出一个 JSON 对象，不要输出解释或 Markdown 代码块，格式如下：
{"possible_causes": ["可能原因", "..."],
 "troubleshooting_steps": ["排查步骤", "..."],
 "fix_suggestion": "修复建议，一段话"}

要求：
1. 可能原因要具体到这次请求的哪个字段、哪条断言，不要泛泛而谈
2. 排查步骤按先后顺序排列，每一步都写成可直接执行的动作
3. 若记录里看不出失败（状态是 pass、断言全通过），在 fix_suggestion 里直接说明
   「本次执行未发现失败」，不要硬凑原因"""

# JSON 解析兜底失败后，重新调一次 AI 时追加在 user 消息末尾。
JSON_RETRY_HINT = "上次返回的不是合法 JSON，请只输出 JSON，不要任何解释或代码块标记。"


def build_generate_cases_user(doc_text: str, hint: str, count: int) -> str:
    """拼「用例生成」的 user 消息。"""
    parts = [f"接口文档：\n{doc_text}", f"请生成 {count} 条测试用例。"]
    if hint.strip():
        parts.append(f"附加要求：{hint.strip()}")
    return "\n\n".join(parts)


def build_analyze_failure_user(context: dict) -> str:
    """拼「失败分析」的 user 消息。

    context 由 api/ai.py 从执行记录里抽（见其 _build_failure_context），
    这里只负责排版，不碰数据库。
    """
    def _fmt(value) -> str:
        if value is None or value == "":
            return "(无)"
        if isinstance(value, (dict, list)):
            return json_dumps(value)
        return str(value)

    lines = [
        f"用例名：{_fmt(context.get('case_name'))}",
        f"执行状态：{_fmt(context.get('status'))}",
        f"耗时：{_fmt(context.get('duration_ms'))} ms",
        "",
        f"请求：{_fmt(context.get('method'))} {_fmt(context.get('url'))}",
        f"请求头：{_fmt(context.get('request_headers'))}",
        f"请求体：{_fmt(context.get('request_body'))}",
        "",
        f"响应状态码：{_fmt(context.get('response_status'))}",
        f"响应体（可能被截断）：{_fmt(context.get('response_body'))}",
        "",
        f"断言结果：{_fmt(context.get('assertions'))}",
        f"错误信息：{_fmt(context.get('error_msg'))}",
    ]
    return "\n".join(lines)


def json_dumps(value) -> str:
    """统一用 ensure_ascii=False，中文在提示词里保持可读。"""
    return json.dumps(value, ensure_ascii=False, default=str)
