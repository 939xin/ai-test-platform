"""环境相关的请求 / 响应模型。

variables_json 存该环境的全局变量，形如 {"base_url": "...", "token": "..."}，
取代旧桌面版的 global_variables 表。
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="环境名，如 dev / test / prod")
    base_url: str = Field("", max_length=255, description="接口根地址")
    variables_json: dict = Field(default_factory=dict, description="全局变量键值对")


class EnvironmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    base_url: str | None = Field(None, max_length=255)
    variables_json: dict | None = None


class EnvironmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    base_url: str
    variables_json: dict
    created_at: datetime
    updated_at: datetime
