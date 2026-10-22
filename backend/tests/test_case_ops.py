"""F1-2：标签归一化与克隆的单元测试（不连库、不起服务）。

这几条钉住的都是**静默错误**：写坏了不会报错，只会在用一段时间后
发现「改副本把原用例改了」「smoke2 被 smoke 筛出来了」。
"""
from sqlalchemy.dialects import mysql

from app.api.cases import _tag_matches
from app.models import TestCase as CaseRow
from app.services.case_ops import build_case_clone, clone_name, normalize_tags, tag_list


def test_normalize_tags_trims_drops_empty_and_dedupes():
    assert normalize_tags(" smoke , 订单 ,, smoke ") == "smoke,订单"
    assert normalize_tags("a,b,a") == "a,b"
    assert normalize_tags("") == ""
    assert normalize_tags(None) == ""


def test_normalize_tags_accepts_fullwidth_comma():
    """中文输入法下很容易敲成全角逗号，不能把它当成标签名的一部分。"""
    assert normalize_tags("smoke，订单") == "smoke,订单"
    assert tag_list("smoke，订单") == ["smoke", "订单"]


def test_tag_list_keeps_order():
    assert tag_list("b, a, c") == ["b", "a", "c"]


def _source_case() -> CaseRow:
    return CaseRow(
        project_id=1,
        name="下单主流程",
        type="web",
        tags="smoke,订单",
        enabled=True,
        login_case=True,
        needs_login=True,
        headers_json={"X-Token": "${token}"},
        params_json={"page": 1},
        assertions_json=[{"assertion_type": "status_code", "operator": "eq", "expected_value": "200"}],
        extract_json=[{"name": "token", "source": "body", "expression": "$.token"}],
        steps_json=[{"step_order": 1, "action_type": "open_url", "input_value": "http://x"}],
    )


def test_clone_is_disabled_and_not_login_case():
    """副本默认停用，且**不再是登录用例** —— 否则跑一次副本就覆盖项目登录态。"""
    clone = build_case_clone(_source_case())
    assert clone.enabled is False
    assert clone.login_case is False
    # needs_login 可以继承：副本的运行前提与原用例一致
    assert clone.needs_login is True


def test_clone_name_has_suffix():
    assert clone_name("下单主流程") == "下单主流程（副本）"
    # 超长名字截断原名、保留后缀，否则看不出这是副本
    long_name = "长" * 200
    result = clone_name(long_name)
    assert len(result) == 128
    assert result.endswith("（副本）")


def test_clone_deep_copies_json_fields():
    """改副本的嵌套结构不能影响原用例 —— 浅拷贝会共用同一个 dict。"""
    source = _source_case()
    clone = build_case_clone(source)

    assert clone.steps_json is not source.steps_json
    assert clone.assertions_json is not source.assertions_json
    assert clone.extract_json is not source.extract_json
    assert clone.headers_json is not source.headers_json
    assert clone.params_json is not source.params_json

    # 改副本最内层的一个键，原用例必须原封不动
    clone.steps_json[0]["input_value"] = "http://changed"
    clone.headers_json["X-Token"] = "changed"
    assert source.steps_json[0]["input_value"] == "http://x"
    assert source.headers_json["X-Token"] == "${token}"


def test_tag_filter_uses_find_in_set_not_like():
    """标签筛选必须是 FIND_IN_SET（按元素精确匹配），不能退化成 LIKE 子串匹配。

    LIKE '%smoke%' 会把 smoke2 一起筛出来，而且不报错 —— 这条断言把它钉死。
    """
    sql = str(_tag_matches("smoke").compile(dialect=mysql.dialect()))
    assert "find_in_set" in sql.lower()
    assert "replace" in sql.lower()  # 库里的历史脏数据「smoke, 订单」也能匹配
    assert " like " not in sql.lower()
