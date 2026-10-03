"""执行相关的请求 / 响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RunCaseRequest(BaseModel):
    """执行单条用例时的可选参数。"""

    env_id: int | None = Field(None, description="要使用的环境 id；不传则不加 base_url、无全局变量")
    timeout: int = Field(30, ge=1, le=120, description="单次请求超时（秒）")


class RunWebRequest(BaseModel):
    """执行单条 Web UI 用例时的可选参数。

    timeout 是**整条用例**的保险丝（不是单次请求超时）：Web 用例要等页面渲染，
    天然比接口用例慢，默认给到 300 秒，比接口侧的 30 秒宽松得多。
    """

    env_id: int | None = Field(None, description="要使用的环境 id，用于解析 ${变量}")
    browser: str = Field("chrome", pattern="^(chrome|edge)$", description="浏览器")
    headless: bool = Field(True, description="无头模式；排障时可关掉，观察浏览器的实际操作")
    timeout: int = Field(300, ge=10, le=1800, description="整条用例的超时（秒）")


class DataDrivenRunResult(BaseModel):
    """数据驱动的执行结果：一条用例按数据文件的每一行各跑一次。"""

    case_id: int
    case_name: str
    data_file: str
    total: int
    passed: int
    failed: int
    rows: list["ExecutionOut"]


class ExecutionStats(BaseModel):
    """执行统计，供执行中心的统计卡使用。

    统计的是**筛选后的全部记录**，不受分页影响 ——
    否则分页之后卡片会变成「翻一页数字就变」。

    failed 是 fail + error 的合计：执行中心那张卡就是这个口径，
    分成两个数反而要前端再加一次。
    """

    total: int
    passed: int
    failed: int


class ExecutionOut(BaseModel):
    """单次执行详情，含完整请求/响应/断言结果。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    plan_id: int | None
    case_id: int | None
    case_name: str | None = None
    status: str
    start_time: datetime | None
    end_time: datetime | None
    duration_ms: int
    result_json: dict
    created_at: datetime


class ExecutionBrief(BaseModel):
    """执行历史列表用的精简结构。

    case_name 由列表接口按 case_id 回查用例名填充 —— 用例被删时 case_id 置 NULL、
    名称也随之为 None，前端显示「已删除用例」。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    case_id: int | None
    case_name: str | None = None
    status: str
    duration_ms: int
    created_at: datetime
