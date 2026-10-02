"""测试计划相关的请求 / 响应模型。

计划 = 一组互不依赖的用例 + 一个默认环境。用例清单用关联表存（见 models.TestPlanCase），
提交时按数组顺序生成 step_order，前端不用自己维护序号。
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.execution import ExecutionOut


class PlanCaseIn(BaseModel):
    """计划里的一条用例。"""

    case_id: int
    enabled: bool = True


class PlanCaseOut(PlanCaseIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_order: int
    # 下面三个由接口按 case_id 回查填充，方便列表直接展示，省一次请求
    case_name: str | None = None
    case_type: str | None = None
    priority: str | None = None


class PlanCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    env_id: int | None = Field(None, description="计划默认使用的环境")
    cases: list[PlanCaseIn] = Field(default_factory=list)


class PlanUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    env_id: int | None = None
    # 传了 cases 就整体替换（编辑器就是整体提交的）
    cases: list[PlanCaseIn] | None = None


class PlanBrief(BaseModel):
    """列表页用的精简结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: str
    env_id: int | None = None
    env_name: str | None = None
    case_count: int = 0
    created_at: datetime


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: str
    env_id: int | None = None
    env_name: str | None = None
    cases: list[PlanCaseOut] = Field(default_factory=list)
    created_at: datetime


class RunPlanRequest(BaseModel):
    """执行计划时的可选参数。

    接口用例和 Web 用例的超时分开放：Web 要等页面渲染，天然慢得多，
    共用一个 timeout 会让两边都不合适。
    """

    env_id: int | None = Field(None, description="覆盖计划绑定的环境；不传则用计划里的")
    timeout: int = Field(30, ge=1, le=120, description="单条接口用例的超时（秒）")
    browser: str = Field("chrome", pattern="^(chrome|edge)$", description="Web 用例用的浏览器")
    headless: bool = Field(True, description="Web 用例是否无头执行")
    web_timeout: int = Field(300, ge=10, le=1800, description="单条 Web 用例的超时（秒）")


class PlanRunResult(BaseModel):
    """计划执行汇总。

    计划不中止：某条用例失败或出错都会记下来，然后继续跑下一条。
    """

    plan_id: int
    plan_name: str
    status: str = Field(..., description="整体状态：pass / fail / error")
    total: int = Field(..., description="实际执行的用例数（不含被停用的）")
    passed: int
    failed: int
    skipped: int = Field(0, description="在计划里被停用的用例数")
    total_duration_ms: int
    cases: list[ExecutionOut] = Field(default_factory=list)
