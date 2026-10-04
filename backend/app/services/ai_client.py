"""DeepSeek 客户端 — 调接口、失败重试、把返回文本解析成 JSON。

只做这三件事，不含业务语义：提示词在 ai_prompts.py，落库与路由在 api/ai.py。
"""
import json
import re

import httpx

from app.config import settings
from app.services.ai_prompts import JSON_RETRY_HINT

TIMEOUT_SECONDS = 60.0  # DeepSeek 生成整批用例偶尔要几十秒，给足余量
MAX_RETRY = 1           # 网络类失败只重试 1 次，避免把用户按在页面上干等

# 可重试的 HTTP 状态码：限流与服务端异常是暂时的，重试有意义；
# 401/402/400 是配置或请求本身的问题，重试一次还是同样的错，只会白等。
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class AIError(Exception):
    """AI 调用失败。message 一律中文，可直接展示给用户。

    raw 是 AI 最后一次的原始返回（可能为空），失败时也写进 ai_task.output，
    否则线上排查时只剩一句「失败了」，看不到模型到底回了什么。
    """

    def __init__(self, message: str, status_code: int = 502, raw: str = ""):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.raw = raw


def _chat_once(system: str, user: str) -> str:
    """发起一次调用，返回模型输出的文本。"""
    api_key = settings.deepseek_api_key.strip()
    if not api_key:
        raise AIError(
            "未配置 DEEPSEEK_API_KEY，请先在 backend/.env 里填入真实 key 并重启后端",
            status_code=400,
        )

    url = settings.deepseek_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }

    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        raise AIError(f"调用 DeepSeek 超时（{int(TIMEOUT_SECONDS)} 秒），请稍后重试") from None
    except httpx.TransportError as e:
        raise AIError(f"连接 DeepSeek 失败：{e}") from e

    if resp.status_code >= 400:
        raise AIError(
            _describe_http_error(resp),
            status_code=502 if resp.status_code in RETRYABLE_STATUS else 400,
        )

    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise AIError(f"无法解析 DeepSeek 的响应结构：{e}", status_code=502) from e


def _describe_http_error(resp: httpx.Response) -> str:
    code = resp.status_code
    fixed = {
        400: "请求格式有误",
        401: "API Key 无效或已过期",
        402: "账户余额不足",
        429: "触发限流",
    }
    if code in fixed:
        return f"DeepSeek 返回 {code}：{fixed[code]}"
    detail = resp.text[:200] if resp.text else ""
    return f"DeepSeek 返回 {code}{('：' + detail) if detail else ''}"


def _chat(system: str, user: str) -> str:
    """带重试的调用：网络异常 / 超时 / 限流 / 5xx 重试 MAX_RETRY 次，其余立即抛出。"""
    for attempt in range(MAX_RETRY + 1):
        try:
            return _chat_once(system, user)
        except AIError as e:
            # status_code == 502 表示「暂时性故障」，才值得重试；400 类是配置问题，重试无意义
            if e.status_code != 502 or attempt >= MAX_RETRY:
                raise
    raise AIError("调用 DeepSeek 失败")  # 理论到不了，仅为让分支闭合


def _try_parse(text: str):
    """尽力把文本解析成 JSON，失败返回 None。三层兜底：直接解析 → 剥代码围栏 → 正则提最外层。"""
    if not text:
        return None

    fenced = _strip_fence(text)
    for candidate in (text.strip(), fenced):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except (ValueError, TypeError):
            pass

    # 模型常见的毛病：JSON 前后带一句「好的，以下是结果：」。取最外层括号之间的部分
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except (ValueError, TypeError):
                pass
    return None


def _strip_fence(text: str) -> str:
    """剥掉 ```json ... ``` 围栏。没有围栏则原样返回。"""
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    return match.group(1).strip() if match else text.strip()


def chat_json(system: str, user: str) -> tuple[object, str]:
    """调用 AI 并解析 JSON，返回 (解析结果, 原始文本)。

    第一次解析不出来时重新调用一次 AI（在 user 消息末尾补一句「只输出 JSON」），
    仍解析不出来才抛 AIError —— 不是把同一段文本再解析一遍。
    """
    raw = _chat(system, user)
    data = _try_parse(raw)
    if data is not None:
        return data, raw

    raw_retry = _chat(system, f"{user}\n\n{JSON_RETRY_HINT}")
    data = _try_parse(raw_retry)
    if data is not None:
        return data, raw_retry

    raise AIError("AI 返回的内容不是合法 JSON（已自动重试 1 次），请换个描述再试", raw=raw_retry)
