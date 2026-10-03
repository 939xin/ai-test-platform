"""缺陷相关的请求 / 响应模型。

状态流转：新建 → 处理中 → 已修复 → 已关闭 → 重新打开。后端不限制流转顺序
（测试过程中经常需要来回改），只约束取值必须在这几个枚举内，非法值直接 422。

严重程度 / 优先级 / 状态的取值必须与 models.Defect 的列默认值保持一致，
前端 api/defect.js 里有一份同样的常量，改这里要同步改那边。
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["致命", "严重", "一般", "轻微"]
Priority = Literal["P0", "P1", "P2", "P3"]
DefectStatus = Literal["新建", "处理中", "已修复", "已关闭", "重新打开"]


class DefectCreate(BaseModel):
    """手工新建缺陷。execution_id / case_id 可选，用于关联来源执行记录。"""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    severity: Severity = "一般"
    priority: Priority = "P1"
    execution_id: int | None = None
    case_id: int | None = None


class DefectUpdate(BaseModel):
    """部分更新。execution_id / case_id 是来源标记，建好之后不允许改。"""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    severity: Severity | None = None
    priority: Priority | None = None
    status: DefectStatus | None = None


class DefectOut(BaseModel):
    """缺陷详情。

    case_name / project_name 由接口按 id 回查填充，前端列表与抽屉直接展示，
    省掉再发一次「查用例名」的请求。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: str
    severity: str
    priority: str
    status: str
    execution_id: int | None = None
    case_id: int | None = None
    case_name: str | None = None
    project_name: str | None = None
    created_at: datetime
    updated_at: datetime


class DefectBrief(BaseModel):
    """列表页用的精简结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    severity: str
    priority: str
    status: str
    execution_id: int | None = None
    case_id: int | None = None
    case_name: str | None = None
    created_at: datetime
    updated_at: datetime


class DefectFromExecution(BaseModel):
    """一键提缺陷时可覆盖的字段；不传则由后端按执行结果自动推导。"""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    severity: Severity = "一般"
    priority: Priority = "P1"
