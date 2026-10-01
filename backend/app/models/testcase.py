"""用例与场景：TestCase、Scenario、ScenarioStep、TestPlan。

旧库的 api_headers / api_assertions / web_steps / web_step_locators
四张子表在这里合并成 TestCase 的 JSON 字段，避免大量 join。
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TestCase(Base):
    """测试用例。type=api 用请求字段；type=web 用 steps_json。"""

    __tablename__ = "test_case"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False, default="api")  # api / web
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default="P1")
    tags: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ---------- 接口请求 ----------
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="GET")
    url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    headers_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    body_type: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    body_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    auth_type: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    auth_value: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    # ---------- 断言 / 变量提取 ----------
    assertions_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    extract_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # ---------- Web 步骤 ----------
    steps_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # ---------- 前置/后置脚本、数据驱动 ----------
    pre_script: Mapped[str] = mapped_column(Text, nullable=False, default="")
    post_script: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data_file: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Scenario(Base):
    """场景：多个用例串联执行。"""

    __tablename__ = "scenario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class ScenarioStep(Base):
    """场景内的一个步骤，指向一条用例。fail_strategy 取 stop / continue。"""

    __tablename__ = "scenario_step"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id: Mapped[int] = mapped_column(
        ForeignKey("test_case.id", ondelete="CASCADE"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fail_strategy: Mapped[str] = mapped_column(String(16), nullable=False, default="stop")


class TestPlan(Base):
    """测试计划：一组用例 + 一个环境。"""

    __tablename__ = "test_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    case_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    env_id: Mapped[int | None] = mapped_column(
        ForeignKey("environment.id", ondelete="SET NULL"), nullable=True
    )
    schedule: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
