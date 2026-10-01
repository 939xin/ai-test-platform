"""用例相关的请求 / 响应模型。

TestCase 同时承载接口用例（method/url/headers/assertions）和 Web 用例（steps_json），
由 type 字段区分。子结构一律用 JSON 字段存，不再拆子表。
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TestCaseCreate(BaseModel):
    # project_id 由路径参数 /api/projects/{id}/cases 提供，body 里不再要求，
    # 否则前端不传就会 422。
    name: str = Field(..., min_length=1, max_length=128)
    type: str = Field("api", pattern="^(api|web)$", description="api / web")
    priority: str = Field("P1", max_length=8)
    tags: str = Field("", max_length=255)
    enabled: bool = True

    # ---------- 接口请求 ----------
    method: str = Field("GET", max_length=16)
    url: str = Field("", max_length=500, description="支持 ${变量} 占位符")
    headers_json: dict = Field(default_factory=dict)
    params_json: dict = Field(default_factory=dict)
    body_type: str = Field("none", max_length=16)  # none/json/form/xml/raw
    body_content: str = ""
    auth_type: str = Field("none", max_length=16)  # none/bearer/basic/apikey
    auth_value: str = Field("", max_length=500)

    # ---------- 断言与变量提取 ----------
    # assertions_json 元素形如：
    #   {"assertion_type": "status_code", "operator": "eq", "expected_value": "200", "target": ""}
    assertions_json: list = Field(default_factory=list)
    # extract_json 元素形如：{"name": "token", "source": "body", "expression": "$.token"}
    extract_json: list = Field(default_factory=list)

    # ---------- Web 步骤 ----------
    steps_json: list = Field(default_factory=list)

    # ---------- 脚本与数据驱动 ----------
    pre_script: str = ""
    post_script: str = ""
    data_file: str = Field("", max_length=255)


class TestCaseUpdate(BaseModel):
    """全部可选，只更新传了的字段。"""

    name: str | None = Field(None, min_length=1, max_length=128)
    type: str | None = Field(None, pattern="^(api|web)$")
    priority: str | None = Field(None, max_length=8)
    tags: str | None = Field(None, max_length=255)
    enabled: bool | None = None

    method: str | None = Field(None, max_length=16)
    url: str | None = Field(None, max_length=500)
    headers_json: dict | None = None
    params_json: dict | None = None
    body_type: str | None = Field(None, max_length=16)
    body_content: str | None = None
    auth_type: str | None = Field(None, max_length=16)
    auth_value: str | None = Field(None, max_length=500)

    assertions_json: list | None = None
    extract_json: list | None = None
    steps_json: list | None = None

    pre_script: str | None = None
    post_script: str | None = None
    data_file: str | None = Field(None, max_length=255)


class TestCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    type: str
    priority: str
    tags: str
    enabled: bool

    method: str
    url: str
    headers_json: dict
    params_json: dict
    body_type: str
    body_content: str
    auth_type: str
    auth_value: str

    assertions_json: list
    extract_json: list
    steps_json: list

    pre_script: str
    post_script: str
    data_file: str

    created_at: datetime
    updated_at: datetime


class TestCaseBrief(BaseModel):
    """列表页用的精简结构，不带 requests/response 大字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    type: str
    priority: str
    tags: str
    enabled: bool
    method: str
    url: str
    updated_at: datetime
