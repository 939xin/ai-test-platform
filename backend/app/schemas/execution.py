"""执行相关的请求 / 响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RunCaseRequest(BaseModel):
    """执行单条用例时的可选参数。"""

    env_id: int | None = Field(None, description="要使用的环境 id；不传则不加 base_url、无全局变量")
    timeout: int = Field(30, ge=1, le=120, description="单次请求超时（秒）")


class ExecutionOut(BaseModel):
    """单次执行详情，含完整请求/响应/断言结果。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    plan_id: int | None
    case_id: int | None
    status: str
    start_time: datetime | None
    end_time: datetime | None
    duration_ms: int
    result_json: dict
    created_at: datetime


class ExecutionBrief(BaseModel):
    """执行历史列表用的精简结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    case_id: int | None
    status: str
    duration_ms: int
    created_at: datetime
