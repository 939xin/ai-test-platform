"""AI 辅助接口的请求 / 响应模型。"""
from pydantic import BaseModel, Field, field_validator


class GenerateCasesRequest(BaseModel):
    project_id: int = Field(..., ge=1)
    doc_text: str = Field(..., min_length=1, max_length=20000, description="接口文档原文")
    hint: str = Field("", max_length=500, description="可选附加要求")
    count: int = Field(5, ge=1, le=20, description="期望生成条数")


class GeneratedCase(BaseModel):
    """AI 生成的一条用例。

    字段与 TestCaseCreate 对齐（少了 project_id、type 这些由创建接口决定的），
    前端勾选保存时可直接 POST /api/projects/{id}/cases，无需另建保存接口。
    """

    name: str = Field(..., min_length=1, max_length=128)
    method: str = Field("GET", max_length=16)
    url: str = Field("", max_length=500)
    headers_json: dict = Field(default_factory=dict)
    params_json: dict = Field(default_factory=dict)
    body_type: str = Field("none", max_length=16)
    body_content: str = ""
    assertions_json: list = Field(default_factory=list)
    extract_json: list = Field(default_factory=list)
    priority: str = Field("P1", max_length=8)
    tags: str = Field("", max_length=255)

    @field_validator("method")
    @classmethod
    def _normalize_method(cls, value: str) -> str:
        # 模型偶尔输出小写方法名，统一成大写，免得存进库后执行时被 requests 拒掉
        return value.strip().upper()

    @field_validator("body_type")
    @classmethod
    def _normalize_body_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        return normalized if normalized in {"none", "json", "form", "xml", "raw"} else "none"


class GenerateCasesResponse(BaseModel):
    task_id: int
    cases: list[GeneratedCase]
    message: str = ""


class AnalyzeFailureRequest(BaseModel):
    execution_id: int = Field(..., ge=1)


class AnalyzeFailureResponse(BaseModel):
    task_id: int
    possible_causes: list[str] = Field(default_factory=list)
    troubleshooting_steps: list[str] = Field(default_factory=list)
    fix_suggestion: str = ""
