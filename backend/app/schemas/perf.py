"""性能测试的请求 / 响应模型。

上限全部从 config.settings 读取，前端再通过 GET /api/perf-limits 拿同一份，
不允许前后端各写一套数字。
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.config import settings

LoadMode = Literal["count", "duration"]


class PerfTaskCreate(BaseModel):
    """新建压测任务。"""

    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    case_id: int
    env_id: int | None = None

    load_mode: LoadMode = "count"
    total_requests: int = Field(1000, ge=1, le=settings.perf_max_total_requests)
    duration_seconds: int = Field(60, ge=1, le=settings.perf_max_duration_seconds)
    concurrency: int = Field(10, ge=1, le=settings.perf_max_concurrency)
    target_rps: int | None = Field(None, ge=1, le=settings.perf_max_rps)
    warmup_seconds: int = Field(0, ge=0, le=settings.perf_max_warmup_seconds)
    request_timeout: int = Field(10, ge=1, le=settings.perf_max_request_timeout)
    verify_ssl: bool = True

    # 百分比 0–100；None 表示关闭熔断
    error_rate_threshold: float | None = Field(50.0, ge=0, le=100)
    min_requests_before_abort: int = Field(20, ge=1, le=10000)


class PerfTaskUpdate(BaseModel):
    """全部可选，只更新传了的字段。"""

    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    case_id: int | None = None
    env_id: int | None = None
    load_mode: LoadMode | None = None
    total_requests: int | None = Field(None, ge=1, le=settings.perf_max_total_requests)
    duration_seconds: int | None = Field(None, ge=1, le=settings.perf_max_duration_seconds)
    concurrency: int | None = Field(None, ge=1, le=settings.perf_max_concurrency)
    target_rps: int | None = Field(None, ge=1, le=settings.perf_max_rps)
    warmup_seconds: int | None = Field(None, ge=0, le=settings.perf_max_warmup_seconds)
    request_timeout: int | None = Field(None, ge=1, le=settings.perf_max_request_timeout)
    verify_ssl: bool | None = None
    error_rate_threshold: float | None = Field(None, ge=0, le=100)
    min_requests_before_abort: int | None = Field(None, ge=1, le=10000)


class PerfTaskBrief(BaseModel):
    """任务列表用。case_name / method / url 由接口回查填充。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: str
    case_id: int | None
    case_name: str | None = None
    case_type: str | None = None
    method: str = ""
    url: str = ""
    env_id: int | None
    env_name: str | None = None
    load_mode: str
    total_requests: int
    duration_seconds: int
    concurrency: int
    target_rps: int | None
    updated_at: datetime


class PerfTaskOut(PerfTaskBrief):
    warmup_seconds: int
    request_timeout: int
    verify_ssl: bool
    error_rate_threshold: float | None
    min_requests_before_abort: int
    created_at: datetime


class RunPerfRequest(BaseModel):
    """启动压测。authorization_confirmed 必须为 true，服务端强制校验。"""

    env_id: int | None = Field(None, description="覆盖任务绑定的环境")
    authorization_confirmed: bool = Field(False, description="确认已获得对该系统的压测授权")


class PerfRunAccepted(BaseModel):
    run_id: int
    status: str


class PerfStopResult(BaseModel):
    run_id: int
    status: str
    changed: bool


class PerfLimits(BaseModel):
    max_concurrency: int
    max_total_requests: int
    max_duration_seconds: int
    max_rps: int
    max_warmup_seconds: int
    max_request_timeout: int
    max_active_runs: int
    hard_wall_seconds: int


class PerfRunBrief(BaseModel):
    """运行列表用。摘要指标从 metrics_json 提取，不把完整 JSON 塞进列表。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    task_id: int | None
    task_name: str
    case_id: int | None
    case_name: str
    env_name: str
    status: str
    load_mode: str
    concurrency: int
    total_requests: int
    duration_seconds: int
    requests_done: int
    requests_failed: int
    success_rate: float | None = None
    tps_avg: float | None = None
    p95_ms: float | None = None
    duration_ms: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class PerfRunOut(PerfRunBrief):
    target_rps: int | None
    warmup_seconds: int
    request_timeout: int
    verify_ssl: bool
    request_json: dict
    metrics_json: dict
    stop_reason: str
    error_msg: str
    authorized_by: str
    authorized_at: datetime | None
    last_heartbeat_at: datetime | None


class PerfRunProgress(BaseModel):
    """进度轮询。stale=true 表示数据库里还在 running，但心跳已断。"""

    run_id: int
    status: str
    phase: str = ""
    elapsed_ms: int = 0
    requests_done: int = 0
    requests_failed: int = 0
    progress_pct: float = 0
    current_tps: float = 0
    error_rate: float = 0
    eta_seconds: float | None = None
    metrics_preview: dict = Field(default_factory=dict)
    stale: bool = False
    stop_requested: bool = False
