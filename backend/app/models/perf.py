"""性能测试：PerfTask（任务定义）与 PerfRun（一次运行）。

刻意不复用 execution 表：
- execution 的语义是「一条用例执行一次」，压测是「一个任务跑 N 个请求」；
- 状态机、结果结构、统计口径都不同，混用会污染执行中心与功能报告。

指标只存聚合结果、固定分桶直方图与 1 秒时间线，**不存每条请求明细**。
"""
from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PerfTask(Base):
    """压测任务：可保存复用的压测配置。"""

    __tablename__ = "perf_task"
    __table_args__ = (
        Index("ix_perf_task_project", "project_id", "id"),
        Index("ix_perf_task_case", "case_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 任务级默认发布版本，运行时会被快照到 perf_run.release_tag。
    # 空串是合法值（表示未标注），**不用 NULL** —— 与 execution.release_tag 口径一致。
    release_tag: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default=""
    )
    case_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_case.id", ondelete="SET NULL"), nullable=True
    )
    env_id: Mapped[int | None] = mapped_column(
        ForeignKey("environment.id", ondelete="SET NULL"), nullable=True
    )

    # count：按总请求数；duration：按持续秒数
    load_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="count")
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    target_rps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warmup_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 错误率阈值用**百分比 0–100**（与 metrics_json 里的 0–1 口径不同，注释与界面都要写明）。
    # NULL 表示关闭熔断。
    error_rate_threshold: Mapped[float | None] = mapped_column(Float, nullable=True, default=50.0)
    min_requests_before_abort: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PerfRun(Base):
    """一次压测运行：配置快照 + 实时计数 + 最终聚合指标。

    task_name / case_name / env_name 存快照：任务被删或用例被换掉后，历史仍读得懂。
    """

    __tablename__ = "perf_run"
    __table_args__ = (
        Index("ix_perf_run_project", "project_id", "id"),
        Index("ix_perf_run_task", "task_id", "id"),
        Index("ix_perf_run_status_heartbeat", "status", "last_heartbeat_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("perf_task.id", ondelete="SET NULL"), nullable=True
    )
    task_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # 运行时的版本快照：任务后来改了 release_tag，历史运行不受影响
    release_tag: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default=""
    )
    case_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_case.id", ondelete="SET NULL"), nullable=True
    )
    case_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    env_id: Mapped[int | None] = mapped_column(
        ForeignKey("environment.id", ondelete="SET NULL"), nullable=True
    )
    env_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    # queued / running / stopping / completed / stopped / aborted / failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")

    load_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="count")
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_rps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warmup_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 脱敏后的请求快照：method / 打码 URL / header 名 / body 大小 / auth 类型。
    # 绝不存 Authorization、Cookie、密码或请求体原文。
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    authorized_by: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 实时进度（协调线程每秒写一次）
    requests_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_tps: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 进程 uuid，为未来多进程部署留的区分位；当前单 worker 下固定一个值
    runner_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    # completed / user / error_rate / wall_timeout / request_cap / shutdown / exception
    stop_reason: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    error_msg: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
