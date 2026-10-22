"""pre_script / post_script 已废弃（决策 D1）。

钉住三件事：
1. 出站结构里不再有这两个键 —— 前端/调用方不该再看到它们；
2. 老客户端仍带着这两个字段提交时**不能 422**（Pydantic 默认忽略多余字段），
   否则升级后会突然建不了用例；
3. 入库结构（ORM）里列还在 —— 保留历史数据，删列不可逆。
"""
from app.models import TestCase as CaseRow
# 别名：类名以 Test 开头，pytest 会误当成本文件里的测试类去收集（PytestCollectionWarning）
from app.schemas.testcase import (
    TestCaseCreate as CreateSchema,
    TestCaseOut as OutSchema,
    TestCaseUpdate as UpdateSchema,
)


def test_create_ignores_legacy_script_fields():
    payload = CreateSchema(
        project_id=1, name="老客户端用例", type="api",
        pre_script="print(1)", post_script="print(2)",
    )
    assert not hasattr(payload, "pre_script")
    assert payload.model_dump().keys().isdisjoint({"pre_script", "post_script"})


def test_update_ignores_legacy_script_fields():
    payload = UpdateSchema(pre_script="print(1)")
    assert payload.model_dump(exclude_unset=True) == {}


def test_out_schema_has_no_script_fields():
    fields = set(OutSchema.model_fields)
    assert "pre_script" not in fields
    assert "post_script" not in fields


def test_model_keeps_columns_for_history():
    """列必须还在：老库有数据，删列不可逆，且 _ADDED_COLUMNS 没有删列登记位。"""
    columns = set(CaseRow.__table__.columns.keys())
    assert {"pre_script", "post_script"} <= columns
