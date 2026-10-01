"""项目相关的请求 / 响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="项目名称")
    description: str = Field("", max_length=1000, description="项目描述")


class ProjectUpdate(BaseModel):
    """全部字段可选，只更新传了的字段。"""

    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=1000)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
