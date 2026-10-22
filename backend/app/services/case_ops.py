"""用例的标签归一化与克隆构造。

抽成纯函数（不碰 Session、不发请求）是为了能在单元测试里直接钉住：
克隆必须深拷贝、标签必须按元素去重 —— 这两条一旦写错都是**静默**的
（改副本把原用例改掉、`smoke2` 被 `smoke` 筛出来），跑一遍用例看不出来。
"""
import copy

from app.models import TestCase

# 半角与全角逗号都切：用户在中文输入法下很容易敲成「，」
TAG_SEPARATORS = (",", "，")
CLONE_SUFFIX = "（副本）"
NAME_MAX_LENGTH = 128  # 与 TestCase.name 的 String(128) 对齐

# 需要深拷贝的 JSON 列：浅拷贝会让副本与原用例共用同一个 list / dict，
# 改副本的某个步骤会连原用例一起改掉
_JSON_LIST_FIELDS = ("assertions_json", "extract_json", "steps_json")
_JSON_DICT_FIELDS = ("headers_json", "params_json")


def tag_list(text: str | None) -> list[str]:
    """切成标签列表：去首尾空格、去空项、去重（保留首次出现的顺序）。"""
    if not text:
        return []
    parts: list[str] = []
    seen: set[str] = set()
    for chunk in _split_tags(text):
        tag = chunk.strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        parts.append(tag)
    return parts


def _split_tags(text: str) -> list[str]:
    """按所有支持的分隔符切分（先全角换半角，再一次性 split）。"""
    normalized = text
    for sep in TAG_SEPARATORS[1:]:
        normalized = normalized.replace(sep, TAG_SEPARATORS[0])
    return normalized.split(TAG_SEPARATORS[0])


def normalize_tags(text: str | None) -> str:
    """保存侧的归一化结果，统一用半角逗号无空格拼接。

    例：`" smoke , 订单 ,, smoke "` → `"smoke,订单"`
    """
    return ",".join(tag_list(text))


def clone_name(name: str) -> str:
    """`原名字（副本）`，超长时截断原名而不是截断后缀 —— 后缀被截掉就看不出是副本了。"""
    keep = NAME_MAX_LENGTH - len(CLONE_SUFFIX)
    return f"{(name or '')[:keep]}{CLONE_SUFFIX}"


def build_case_clone(source: TestCase) -> TestCase:
    """构造一条未入库的副本。

    三条硬约束（功能单 F1-2 里写明，不能为了方便改掉）：
    1. `enabled` 强制 False —— 否则副本会被测试计划一起跑掉；
    2. `login_case` 强制 False —— 副本若是登录用例，跑一次就会覆盖项目登录态，
       而克隆一个人往往只是想改改步骤再试，不该悄悄动全局状态；
       `needs_login` 照继承，副本的运行前提与原用例一致；
    3. 所有 JSON 列深拷贝 —— 改副本不能影响原用例。
    """
    clone = TestCase(
        project_id=source.project_id,
        name=clone_name(source.name),
        type=source.type,
        priority=source.priority,
        tags=source.tags,
        enabled=False,
        method=source.method,
        url=source.url,
        body_type=source.body_type,
        body_content=source.body_content,
        auth_type=source.auth_type,
        auth_value=source.auth_value,
        login_case=False,
        needs_login=source.needs_login,
        data_file=source.data_file,
    )
    for field in _JSON_LIST_FIELDS:
        setattr(clone, field, copy.deepcopy(getattr(source, field) or []))
    for field in _JSON_DICT_FIELDS:
        setattr(clone, field, copy.deepcopy(getattr(source, field) or {}))
    return clone
