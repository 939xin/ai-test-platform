"""Web 登录态：WebSession。

登录用例执行成功后，把浏览器的 cookie / localStorage / sessionStorage 导出到这里；
「需要登录态」的用例执行前再把它注入回新开的 driver。

注意这**不动隔离模型**：每条用例仍然各起各的浏览器、各关各的，共享的只有状态数据，
不是浏览器本身。
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WebSession(Base):
    """一次登录态的完整快照。

    一个项目可以有**多条**（比如管理员、普通用户各一条登录用例）。
    「需要登录态」的用例取本项目 updated_at 最新的那条 —— 这是「两个开关」
    这种交互方式下唯一自洽的语义；将来要做成「一条用例指定用哪套登录态」，
    只需在 test_case 上加一个 session_id 外键，本表结构不用动。
    """

    __tablename__ = "web_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 来源登录用例。用例被删除时置空而不是级联删掉这条记录 ——
    # 登录态本身可能还在被别的用例使用，不该跟着一条用例一起消失。
    source_case_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_case.id", ondelete="SET NULL"), nullable=True
    )

    # 注入前必须先访问这个 origin：浏览器只允许在目标域上写 cookie 与 storage，
    # 空白页上 add_cookie 会被静默丢弃（不报错）。所以它不是一个可有可无的展示字段。
    origin: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    cookies_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    local_storage_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    session_storage_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # 取该批 cookies 里最早的 expires。localStorage 里存的 token 何时失效，
    # 前端不暴露任何信号，因此无从得知 —— 这一列只能覆盖 cookie 那一半。
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
