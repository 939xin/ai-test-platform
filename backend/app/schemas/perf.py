"""性能测试的请求 / 响应模型。

上限全部从 config.settings 读取，前端再通过 GET /api/perf-limits 拿同一份，
不允许前后端各写一套数字。
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings

LoadMode = Literal["count", "duration"]

RELEASE_TAG_MAX = 64


def _strip_release_tag(value: str | None) -> str | None:
    """版本号两侧空格一律去掉；None 原样返回，由调用方决定是否回落任务默认值。

    空串是合法值（未标注），**不在任何一层把它转成 None** —— 与 execution 的
    release_tag 口径一致，界面与导出都按「空串 = 未标注」展示。
    """
    if value is None:
        return None
    return str(value).strip()


class PerfTaskCreate(BaseModel):
    """新建压测任务。"""

    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    release_tag: str = Field("", max_length=RELEASE_TAG_MAX, description="发布版本标注，可留空")
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

    @field_validator("release_tag", mode="before")
    @classmethod
    def _clean_release_tag(cls, value):
        # mode="before"：先 strip 再校验长度，否则 "  x  " 会按带空格的原始长度算
        return _strip_release_tag(value) or ""


class PerfTaskUpdate(BaseModel):
    """全部可选，只更新传了的字段。"""

    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    release_tag: str | None = Field(None, max_length=RELEASE_TAG_MAX)
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

    @field_validator("release_tag", mode="before")
    @classmethod
    def _clean_release_tag(cls, value):
        return _strip_release_tag(value)


class PerfTaskBrief(BaseModel):
    """任务列表用。case_name / method / url 由接口回查填充。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: str
    release_tag: str = ""
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
    release_tag: str | None = Field(
        None,
        max_length=RELEASE_TAG_MAX,
        description="覆盖任务上的版本标注；不传则用任务的，显式传空串表示本次未标注",
    )
    authorization_confirmed: bool = Field(False, description="确认已获得对该系统的压测授权")

    @field_validator("release_tag", mode="before")
    @classmethod
    def _clean_release_tag(cls, value):
        return _strip_release_tag(value)


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
    release_tag: str = ""
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


class PerfCompareSide(BaseModel):
    """对比的一侧：负载参数 + 聚合指标，全部取自该次运行自己的快照。"""

    run_id: int
    task_id: int | None
    task_name: str
    case_id: int | None
    case_name: str
    env_id: int | None
    env_name: str
    release_tag: str = ""
    status: str
    load_mode: str
    concurrency: int
    total_requests: int
    duration_seconds: int
    duration_ms: int
    started_at: datetime | None
    finished_at: datetime | None
    counts: dict = Field(default_factory=dict)
    latency_ms: dict = Field(default_factory=dict)
    tps: dict = Field(default_factory=dict)
    errors: dict = Field(default_factory=dict)
    error_rate: float | None = None


class PerfCompareDelta(BaseModel):
    """右（较新）相对左（较早）的变化百分比。

    `None` 表示左侧没有可用基数（为 0 或缺失），此时不编造百分比 ——
    0 → 5 的「增长 500%」比「—」更容易误导人。
    """

    total_pct: float | None = None
    failed_pct: float | None = None
    error_rate_pct: float | None = None
    tps_pct: float | None = None
    avg_pct: float | None = None
    p50_pct: float | None = None
    p90_pct: float | None = None
    p95_pct: float | None = None
    p99_pct: float | None = None


class PerfRunCompare(BaseModel):
    left: PerfCompareSide
    right: PerfCompareSide
    delta: PerfCompareDelta
    # 不阻断对比的差异（用例不同 / 环境不同），不是错误
    warning: str | None = None


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
