"""F3-5：压测版本标注（release_tag）的 schema 单元测试。

不连库、不起服务。钉住三条静默风险：
- 超过 64 字符必须在入口就 422，不能等 MySQL 截断（截断后两条记录会「看起来同版本」）；
- 两侧空格要被清掉，否则「v2.2.0」和「v2.2.0 」在筛选里互不命中；
- 空串是合法值，**不能**被悄悄转成 None —— 列是 NOT NULL，None 会直接写库失败。
"""
import pytest
from pydantic import ValidationError

from app.schemas.perf import PerfTaskCreate, PerfTaskUpdate, RunPerfRequest


def _create(**overrides) -> PerfTaskCreate:
    payload = {"name": "验收任务", "case_id": 1, **overrides}
    return PerfTaskCreate(**payload)


def test_release_tag_allows_empty_by_default():
    assert _create().release_tag == ""
    assert _create(release_tag="").release_tag == ""


def test_release_tag_strips_whitespace():
    assert _create(release_tag="  v2.2.0  ").release_tag == "v2.2.0"


def test_release_tag_length_limit_is_measured_after_strip():
    # 64 个字符 + 两侧空格 = 68，strip 之后仍然合法
    assert _create(release_tag="  " + "v" * 64 + "  ").release_tag == "v" * 64


def test_release_tag_too_long_rejected():
    with pytest.raises(ValidationError):
        _create(release_tag="v" * 65)


def test_update_release_tag_none_means_untouched_and_long_rejected():
    assert PerfTaskUpdate(release_tag=None).model_dump(exclude_unset=True) == {
        "release_tag": None
    }
    with pytest.raises(ValidationError):
        PerfTaskUpdate(release_tag="v" * 65)


def test_run_request_release_tag_distinguishes_absent_from_empty():
    """None = 没传（用任务上的）；"" = 显式标注为未标注。两者不能合并。"""
    assert RunPerfRequest().release_tag is None
    assert RunPerfRequest(release_tag="").release_tag == ""
    assert RunPerfRequest(release_tag=" v2.2.0 ").release_tag == "v2.2.0"
    with pytest.raises(ValidationError):
        RunPerfRequest(release_tag="v" * 65)
