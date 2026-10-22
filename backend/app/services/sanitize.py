"""敏感信息脱敏 —— 压测与功能执行共用一套清单。

脱敏规则必须只有一份：同一份 `Authorization` 头，压测落库时打了码、
功能执行却原样写进 `execution.result_json`（还会进报告与 AI 提示词），
就会出现「同一平台两种口径」，而且没人说得清哪份才是被保护的。

两类规则刻意分开，不要合并：
- `SENSITIVE_QUERY_KEYS`：URL / 查询参数里**看名字像令牌**的键（token、sign…）。
  压测用它，避免把目标的真实令牌写进运行快照。
- `SENSITIVE_HEADER_KEYS`：请求头 / 响应头里**本身就是凭证通道**的头
  （Authorization、Cookie、Set-Cookie…）。功能执行用它。

注意 `redact_url` 只按 query key 判断，不碰路径 —— 路径里的 id 是排障必需的。
"""
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# URL 查询参数里这些键的值不落库（仍会真实发送给目标）
SENSITIVE_QUERY_KEYS = {
    "token", "access_token", "refresh_token", "key", "api_key", "apikey",
    "secret", "password", "passwd", "pwd", "auth", "authorization",
    "sign", "signature", "session", "sessionid", "cookie",
}

# 请求头 / 响应头里命中这些名字（不区分大小写）就把值替换成 ***
SENSITIVE_HEADER_KEYS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
}

# 连接异常的消息里可能带完整 URL，落库前把敏感参数值再抹一遍
_SENSITIVE_IN_MESSAGE = re.compile(
    r"(?i)(token|access_token|refresh_token|api_key|apikey|key|secret|"
    r"password|passwd|pwd|sign|signature)=([^&\s,;]+)"
)


def scrub_message(text: str, limit: int = 200) -> str:
    """把错误消息里的 `token=xxx` 一类参数值替换成 `token=***` 并截断。"""
    return _SENSITIVE_IN_MESSAGE.sub(r"\1=***", text or "")[:limit]


def redact_query_params(params: dict | None) -> dict:
    """按查询参数键名打码，返回新字典（不改入参）。"""
    return {
        str(key): ("***" if str(key).lower() in SENSITIVE_QUERY_KEYS else value)
        for key, value in (params or {}).items()
    }


def redact_url(url: str) -> str:
    """把 URL 里敏感 query 参数的值替换成 ***；其余保留，便于排障。"""
    try:
        parts = urlsplit(url)
        if not parts.query:
            return url
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        redacted = [
            (key, "***" if key.lower() in SENSITIVE_QUERY_KEYS else value)
            for key, value in pairs
        ]
        return urlunsplit((
            parts.scheme, parts.netloc, parts.path, urlencode(redacted), parts.fragment,
        ))
    except Exception:  # noqa: BLE001
        return url


def redact_headers(headers) -> dict:
    """把请求头/响应头里敏感名字的值替换成 ***，其余原样保留。

    只处理**头**，不动响应体：响应体里可能就有用例要断言的 token 值，
    改了会把正常用例搞挂。
    """
    result = {}
    for name, value in (headers or {}).items():
        result[name] = "***" if str(name).lower() in SENSITIVE_HEADER_KEYS else value
    return result
