"""Web 登录态接口的响应模型。"""
from datetime import datetime

from pydantic import BaseModel


class WebSessionSummary(BaseModel):
    """登录态摘要。

    ⚠️ **刻意不下发 cookie / storage 的值** —— 那些就是会话令牌本身。
    界面要展示的是「有没有登录态、存了哪些 key、什么时候更新的」，
    这些信息用 key 就够了，不需要把令牌送回浏览器（还要进历史记录和截图）。
    """

    id: int
    origin: str
    source_case_id: int | None = None
    source_case_name: str | None = None
    cookie_count: int
    local_storage_keys: list[str]
    session_storage_keys: list[str]
    # 只覆盖 cookie 的到期时间；localStorage 里的 token 何时失效我们看不到
    expires_at: datetime | None = None
    expired: bool
    updated_at: datetime


class WebSessionClearResult(BaseModel):
    """清除结果。带上条数是为了让界面能说清「清掉了什么」。"""

    deleted: int
