"""用例管理接口。

列表与创建挂在项目下（`/api/projects/{id}/cases`），
详情/更新/删除用用例自身 id（`/api/cases/{id}`）。
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.pagination import PageParams, paginate
from app.api.projects import get_project_or_404
from app.database import get_db
from app.models import TestCase
from app.schemas.common import Page
from app.schemas.testcase import (
    CaseBatchRequest,
    CaseBatchResult,
    TestCaseBrief,
    TestCaseCreate,
    TestCaseOut,
    TestCaseUpdate,
)
from app.services.case_ops import build_case_clone, normalize_tags, tag_list

router = APIRouter()


def get_case_or_404(db: Session, case_id: int) -> TestCase:
    """给本模块与执行模块共用。"""
    case = db.get(TestCase, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用例不存在")
    return case


def _tag_matches(tag: str):
    """标签按「元素」精确匹配，不是子串匹配。

    用 FIND_IN_SET 而不是 `tags LIKE '%smoke%'`：后者会把 `smoke2` 也筛出来，
    而且不会报错 —— 用户只会发现筛选结果多了一条，很难联想到是 LIKE 的锅。

    查询侧再套一层 REPLACE 去空格：保存侧虽然已经归一化，但库里存在历史脏数据
    （手工写的 "smoke, 订单"，逗号后带空格），而 FIND_IN_SET 对空格敏感。
    """
    return func.find_in_set(tag, func.replace(TestCase.tags, " ", "")) > 0


@router.get(
    "/projects/{project_id}/cases",
    response_model=Page[TestCaseBrief],
    summary="用例列表（支持按类型/优先级/关键字/标签/启用状态筛选，分页）",
)
def list_cases(
    project_id: int,
    page: PageParams = Depends(),
    case_type: str | None = Query(None, alias="type", description="api / web"),
    priority: str | None = Query(None, description="P0 / P1 / P2"),
    keyword: str | None = Query(None, description="按名称模糊匹配"),
    tag: list[str] | None = Query(
        None, description="标签，可重复传（?tag=smoke&tag=order）；命中任一即可"
    ),
    enabled: bool | None = Query(None, description="启用状态；不传表示全部"),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id)
    stmt = select(TestCase).where(TestCase.project_id == project_id)
    if case_type:
        stmt = stmt.where(TestCase.type == case_type)
    if priority:
        stmt = stmt.where(TestCase.priority == priority)
    if keyword:
        stmt = stmt.where(TestCase.name.contains(keyword))
    if enabled is not None:
        stmt = stmt.where(TestCase.enabled == enabled)
    if tag:
        # 入参先切再 strip：REPLACE 处理的是**库里**的空格，
        # 前端若把 " smoke" 原样传上来，FIND_IN_SET 依然匹配不到
        wanted = [one for item in tag for one in tag_list(item)]
        if wanted:
            stmt = stmt.where(or_(*[_tag_matches(item) for item in wanted]))

    rows, total = paginate(db, stmt.order_by(TestCase.id.desc()), page)
    return Page(items=rows, total=total)


@router.post(
    "/projects/{project_id}/cases",
    response_model=TestCaseOut,
    status_code=status.HTTP_201_CREATED,
    summary="新建用例",
)
def create_case(project_id: int, payload: TestCaseCreate, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    data = payload.model_dump()
    data["project_id"] = project_id  # 以路径参数为准，避免 body 与路径不一致
    # 保存侧归一化：去空格、去空项、去重。否则 "smoke, 订单" 在库里就是一个怪标签，
    # 而查询侧靠 REPLACE 只能兜住空格，兜不住重复项
    data["tags"] = normalize_tags(data.get("tags"))
    case = TestCase(**data)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@router.get(
    "/projects/{project_id}/case-tags",
    response_model=list[str],
    summary="项目内出现过的标签（下拉数据源，返回裸数组）",
)
def list_case_tags(
    project_id: int,
    case_type: str | None = Query(None, alias="type", description="api / web"),
    limit: int | None = Query(None, ge=1, le=500, description="最多返回几个标签，不传表示全部"),
    db: Session = Depends(get_db),
):
    """给筛选器的标签多选做数据源。

    刻意返回裸数组：它只是下拉数据源，不分页、不随使用增长到无法一次取回
    （`CLAUDE.md` 里「裸数组仅限下拉数据源」这条）。形状一旦改成 {items,total}，
    前端就得为一个选择器写分页逻辑。
    """
    get_project_or_404(db, project_id)
    stmt = select(TestCase.tags).where(TestCase.project_id == project_id)
    if case_type:
        stmt = stmt.where(TestCase.type == case_type)
    # 标签存在一个逗号串里，只能取回来再切；按项目取一列 String(255)，
    # 量级是「项目用例数」，不是全表，可以接受
    tags = sorted({tag for raw in db.execute(stmt).scalars() for tag in tag_list(raw)})
    return tags[:limit] if limit else tags


@router.post(
    "/cases/batch",
    response_model=CaseBatchResult,
    summary="批量启用 / 停用 / 删除用例",
)
def batch_cases(payload: CaseBatchRequest, db: Session = Depends(get_db)):
    """批量操作必须整批成功或整批不动。

    前端能勾到的只有当前页，但接口不依赖这一点：
    跨项目批量是明确的 400（不做部分成功），有任何一个 id 不存在是 404。
    删掉的 id 若是计划 / 场景里的用例，外键 CASCADE 会顺带清理，这是既有行为。
    """
    case_ids = list(dict.fromkeys(payload.case_ids))  # 去重且保序
    cases = list(db.execute(select(TestCase).where(TestCase.id.in_(case_ids))).scalars())

    missing = sorted(set(case_ids) - {case.id for case in cases})
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用例不存在：{missing}",
        )

    project_ids = {case.project_id for case in cases}
    if len(project_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能跨项目批量操作",
        )

    if payload.action == "delete":
        for case in cases:
            db.delete(case)
    else:
        wanted = payload.action == "enable"
        for case in cases:
            case.enabled = wanted
    db.commit()
    return CaseBatchResult(
        action=payload.action, project_id=project_ids.pop(), affected=len(cases)
    )


@router.post("/cases/{case_id}/clone", response_model=TestCaseOut, summary="克隆用例")
def clone_case(case_id: int, db: Session = Depends(get_db)):
    source = get_case_or_404(db, case_id)
    clone = build_case_clone(source)
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


@router.get("/cases/{case_id}", response_model=TestCaseOut, summary="用例详情")
def get_case(case_id: int, db: Session = Depends(get_db)):
    return get_case_or_404(db, case_id)


@router.put("/cases/{case_id}", response_model=TestCaseOut, summary="更新用例")
def update_case(case_id: int, payload: TestCaseUpdate, db: Session = Depends(get_db)):
    case = get_case_or_404(db, case_id)
    data = payload.model_dump(exclude_unset=True)
    if "tags" in data:
        data["tags"] = normalize_tags(data["tags"])
    for field, value in data.items():
        setattr(case, field, value)
    db.commit()
    db.refresh(case)
    return case


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除用例")
def delete_case(case_id: int, db: Session = Depends(get_db)):
    db.delete(get_case_or_404(db, case_id))
    db.commit()
