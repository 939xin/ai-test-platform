"""执行与缺陷：Execution、Defect、AITask。

旧库的 test_result_details + screenshots 合并进 execution.result_json，
截图改存文件路径（不塞 Base64，避免 JSON 列膨胀）。
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Execution(Base):
    """一次执行记录。result_json 存步骤级明细与断言结果。"""

    __tablename__ = "execution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_plan.id", ondelete="SET NULL"), nullable=True
    )
    case_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_case.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    report_path: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Defect(Base):
    """缺陷。状态流转：新建 → 处理中 → 已修复 → 已关闭 → 重新打开。"""

    __tablename__ = "defect"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="一般")
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default="P1")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="新建")
    execution_id: Mapped[int | None] = mapped_column(
        ForeignKey("execution.id", ondelete="SET NULL"), nullable=True
    )
    case_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_case.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AITask(Base):
    """AI 调用记录。type 取 generate_cases / analyze_failure。"""

    __tablename__ = "ai_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    input: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
