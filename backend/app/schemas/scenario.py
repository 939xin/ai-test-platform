"""场景相关的请求 / 响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScenarioStepIn(BaseModel):
    """编排场景时提交的一个步骤。step_order 由后端按数组顺序生成。"""

    case_id: int
    enabled: bool = True
    fail_strategy: str = Field("stop", pattern="^(stop|continue)$", description="stop 中止 / continue 继续")


class ScenarioStepOut(ScenarioStepIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_order: int
    case_name: str | None = None


class ScenarioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    steps: list[ScenarioStepIn] = Field(default_factory=list)


class ScenarioUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    # 传了 steps 就整体替换（前端编辑器就是整体提交的）
    steps: list[ScenarioStepIn] | None = None


class ScenarioBrief(BaseModel):
    """列表页用的精简结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: str
    step_count: int = 0
    created_at: datetime


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: str
    steps: list[ScenarioStepOut] = Field(default_factory=list)
    created_at: datetime


class RunScenarioRequest(BaseModel):
    """执行场景时的可选参数。"""

    env_id: int | None = Field(None, description="要使用的环境 id；不传则不加 base_url、无全局变量")
    timeout: int = Field(30, ge=1, le=120)
