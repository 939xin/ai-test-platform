"""用例管理接口。

列表与创建挂在项目下（`/api/projects/{id}/cases`），
详情/更新/删除用用例自身 id（`/api/cases/{id}`）。
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.pagination import PageParams, paginate
from app.api.projects import get_project_or_404
from app.database import get_db
from app.models import TestCase
from app.schemas.common import Page
from app.schemas.testcase import TestCaseBrief, TestCaseCreate, TestCaseOut, TestCaseUpdate

router = APIRouter()


def get_case_or_404(db: Session, case_id: int) -> TestCase:
    """给本模块与执行模块共用。"""
    case = db.get(TestCase, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用例不存在")
    return case


@router.get(
    "/projects/{project_id}/cases",
    response_model=Page[TestCaseBrief],
    summary="用例列表（支持按类型/优先级/关键字筛选，分页）",
)
def list_cases(
    project_id: int,
    page: PageParams = Depends(),
    case_type: str | None = Query(None, alias="type", description="api / web"),
    priority: str | None = Query(None, description="P0 / P1 / P2"),
    keyword: str | None = Query(None, description="按名称模糊匹配"),
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
    case = TestCase(**data)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@router.get("/cases/{case_id}", response_model=TestCaseOut, summary="用例详情")
def get_case(case_id: int, db: Session = Depends(get_db)):
    return get_case_or_404(db, case_id)


@router.put("/cases/{case_id}", response_model=TestCaseOut, summary="更新用例")
def update_case(case_id: int, payload: TestCaseUpdate, db: Session = Depends(get_db)):
    case = get_case_or_404(db, case_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    db.commit()
    db.refresh(case)
    return case


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除用例")
def delete_case(case_id: int, db: Session = Depends(get_db)):
    db.delete(get_case_or_404(db, case_id))
    db.commit()
