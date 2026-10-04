"""用例相关的请求 / 响应模型。

TestCase 同时承载接口用例（method/url/headers/assertions）和 Web 用例（steps_json），
由 type 字段区分。子结构一律用 JSON 字段存，不再拆子表。
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# 操作类型 / 定位方式直接取自执行引擎，避免两处各写一份枚举而悄悄漂移
from app.services.web_executor import ACTION_LABELS, ACTION_SPEC, LOCATOR_MAP


class WebStep(BaseModel):
    """Web 用例的一个步骤。

    字段名必须与 services/web_executor.py 读取的完全一致 ——
    两边对不上会静默跑偏（比如定位值写进 input_value 也能存进去，但执行时必然失败）。

    字段分成四个槽位，由 ACTION_SPEC 声明每个操作用到哪几个：
      locator / target_locator（两个元素）、value / value2（两个参数）、wait（秒数）

    只挡「必然跑不通」的错：未知操作类型、未知定位方式、规格里标了 required 的字段没填。
    **刻意不在这里要求 web 用例必须至少有一个步骤** —— 编辑器的正常流程是
    「先建用例 → 再编排步骤」，强制要求会让新建用例直接 422。空步骤由
    run-web 接口在执行时拦下来。
    """

    step_order: int | None = Field(None, description="展示顺序，由前端按数组下标回填")
    enabled: bool = True
    action_type: str
    input_value: str = ""
    input_value2: str = ""
    wait_seconds: float = Field(0, ge=0, le=300)
    description: str = ""
    locator_type: str = ""
    locator_value: str = ""
    target_locator_type: str = ""
    target_locator_value: str = ""

    @field_validator("action_type")
    @classmethod
    def _check_action(cls, value: str) -> str:
        if value not in ACTION_LABELS:
            raise ValueError(f"不支持的操作类型: {value}（可用: {', '.join(ACTION_LABELS)}）")
        return value

    @field_validator("locator_type", "target_locator_type")
    @classmethod
    def _check_locator_type(cls, value: str) -> str:
        if value and value not in LOCATOR_MAP:
            raise ValueError(f"不支持的定位方式: {value}（可用: {', '.join(LOCATOR_MAP)}）")
        return value

    @model_validator(mode="after")
    def _check_required_fields(self):
        """按 ACTION_SPEC 里标了 required 的字段逐个检查，空则 422。

        规格是唯一事实来源 —— 以后新增操作只要在规格里标好 required，
        这里和前端提示会自动跟上，不用两处各改一遍。
        """
        spec = ACTION_SPEC.get(self.action_type)
        if spec is None:
            return self
        # switch_iframe 的 input_value 填 default 表示退回主文档，此时不需要定位信息
        skip_locator = self.action_type == "switch_iframe" and self.input_value == "default"

        filled_map = {
            "locator": (
                bool(self.locator_type and self.locator_value),
                "需要同时填写 locator_type 与 locator_value",
            ),
            "target_locator": (
                bool(self.target_locator_type and self.target_locator_value),
                "需要同时填写 target_locator_type 与 target_locator_value",
            ),
            "value": (bool(str(self.input_value).strip()), "需要填写 input_value"),
            "value2": (bool(str(self.input_value2).strip()), "需要填写 input_value2"),
        }

        for field in spec["fields"]:
            name = field["name"]
            if not field.get("required") or name not in filled_map:
                continue
            if skip_locator and name == "locator":
                continue
            filled, hint = filled_map[name]
            if not filled:
                raise ValueError(
                    f"{spec['label']} 的「{field['label']}」不能为空（{hint}）"
                )
        return self


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
    steps_json: list[WebStep] = Field(default_factory=list)

    # ---------- Web 登录态标记 ----------
    # login_case ：执行成功后把浏览器里的 cookie / localStorage 导出成本项目的登录态
    # needs_login：执行前先注入已保存的登录态，省掉重复登录
    login_case: bool = False
    needs_login: bool = False

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
    steps_json: list[WebStep] | None = None

    login_case: bool | None = None
    needs_login: bool | None = None

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

    login_case: bool
    needs_login: bool

    pre_script: str
    post_script: str
    data_file: str

    created_at: datetime
    updated_at: datetime


class TestCaseBrief(BaseModel):
    """列表页用的精简结构，不带请求体/前置脚本这类大字段。

    assertions_json / extract_json 只占几行，但列表页要用它们的条数做展示 ——
    少了它们，「断言」列会永远显示 0（排查过的一个真实 bug）。
    """

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
    assertions_json: list = Field(default_factory=list)
    extract_json: list = Field(default_factory=list)
    # Web 用例同理：列表页的「步骤」列要靠它显示步骤数，少了就永远是 0
    steps_json: list = Field(default_factory=list)
    # 列表行会带进执行弹窗，弹窗靠它判断要不要显示「按数据文件逐行执行」
    data_file: str = ""
    # 列表页要显示「登录用例 / 需登录态」两个标记，少了就只能去详情页才看得见
    login_case: bool = False
    needs_login: bool = False
    updated_at: datetime
