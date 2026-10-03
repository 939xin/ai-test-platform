"""缺陷管理接口。

缺陷有两个来源：手工新建，或从一条失败 / 错误的执行记录**一键转入**。
一键转入会按执行结果自动拼出标题与描述，并带上 execution_id / case_id，
之后在缺陷详情里能直接跳回那次执行。

同一条执行只允许挂一条缺陷：重复提交返回 409，detail 里是
`{"message": ..., "defect_id": 已有缺陷 id}`，前端据此提示并跳转过去 ——
避免同一条失败被反复点出一串重复缺陷。

冲突响应用 dict 作 detail（FastAPI 允许），所以前端 request.js 的统一报错
要能识别 dict 形态，否则会显示成 [object Object]。
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.pagination import PageParams, paginate
from app.api.projects import get_project_or_404
from app.database import get_db
from app.models import Defect, Execution, Project, TestCase
from app.schemas.common import Page
from app.schemas.defect import (
    DefectBrief,
    DefectCreate,
    DefectFromExecution,
    DefectOut,
    DefectUpdate,
)

router = APIRouter()


def get_defect_or_404(db: Session, defect_id: int) -> Defect:
    defect = db.get(Defect, defect_id)
    if defect is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="缺陷不存在")
    return defect


def _get_execution_or_404(db: Session, execution_id: int) -> Execution:
    execution = db.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行记录不存在")
    return execution


def _case_names(db: Session, case_ids: set[int]) -> dict[int, str]:
    """一次查出 id → 用例名，避免逐行回查。"""
    if not case_ids:
        return {}
    rows = db.execute(select(TestCase.id, TestCase.name).where(TestCase.id.in_(case_ids))).all()
    return dict(rows)


def _to_out(db: Session, defect: Defect) -> DefectOut:
    case_name = _case_names(db, {defect.case_id} if defect.case_id else set()).get(defect.case_id)
    project = db.get(Project, defect.project_id)
    return DefectOut(
        id=defect.id,
        project_id=defect.project_id,
        title=defect.title,
        description=defect.description,
        severity=defect.severity,
        priority=defect.priority,
        status=defect.status,
        execution_id=defect.execution_id,
        case_id=defect.case_id,
        case_name=case_name,
        project_name=project.name if project else None,
        created_at=defect.created_at,
        updated_at=defect.updated_at,
    )


def _describe_execution(execution: Execution, case_name: str) -> str:
    """按执行结果拼一段可读的失败描述，当作缺陷的初始描述。"""
    result = execution.result_json or {}
    lines = [
        f"来源执行记录：#{execution.id}",
        f"用例：{case_name}",
        f"执行状态：{execution.status}",
        f"耗时：{execution.duration_ms} ms",
        f"执行时间：{execution.created_at}",
    ]

    if result.get("error_msg"):
        lines += ["", f"错误信息：{result['error_msg']}"]

    failed_assertions = [a for a in (result.get("assertions") or []) if not a.get("passed")]
    if failed_assertions:
        lines += ["", "未通过的断言："]
        lines += [f"  - {a.get('message', '')}" for a in failed_assertions]

    # Web 用例：把没过的步骤也带上
    failed_steps = [s for s in (result.get("steps") or []) if s.get("status") != "pass"]
    if failed_steps:
        lines += ["", "未通过的步骤："]
        for step in failed_steps:
            message = f"：{step['message']}" if step.get("message") else ""
            lines.append(f"  - 第 {step.get('step_order')} 步 {step.get('desc', '')}{message}")

    return "\n".join(lines)


@router.get("/projects/{project_id}/defects", response_model=Page[DefectBrief],
            summary="缺陷列表（分页）")
def list_defects(
    project_id: int,
    page: PageParams = Depends(),
    status_filter: str | None = Query(None, alias="status", description="按状态筛选"),
    severity: str | None = Query(None, description="按严重程度筛选"),
    keyword: str | None = Query(None, description="按标题关键字筛选"),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id)

    stmt = select(Defect).where(Defect.project_id == project_id)
    if status_filter:
        stmt = stmt.where(Defect.status == status_filter)
    if severity:
        stmt = stmt.where(Defect.severity == severity)
    if keyword and keyword.strip():
        stmt = stmt.where(Defect.title.like(f"%{keyword.strip()}%"))

    defects, total = paginate(db, stmt.order_by(Defect.id.desc()), page)
    names = _case_names(db, {d.case_id for d in defects if d.case_id})

    return Page(items=[
        DefectBrief(
            id=d.id,
            title=d.title,
            severity=d.severity,
            priority=d.priority,
            status=d.status,
            execution_id=d.execution_id,
            case_id=d.case_id,
            case_name=names.get(d.case_id),
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in defects
    ], total=total)


@router.post("/projects/{project_id}/defects", response_model=DefectOut,
             status_code=status.HTTP_201_CREATED, summary="新建缺陷")
def create_defect(project_id: int, payload: DefectCreate, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    if payload.execution_id is not None:
        _get_execution_or_404(db, payload.execution_id)

    defect = Defect(project_id=project_id, **payload.model_dump())
    db.add(defect)
    db.commit()
    db.refresh(defect)
    return _to_out(db, defect)


@router.get("/defects/{defect_id}", response_model=DefectOut, summary="缺陷详情")
def get_defect(defect_id: int, db: Session = Depends(get_db)):
    return _to_out(db, get_defect_or_404(db, defect_id))


@router.put("/defects/{defect_id}", response_model=DefectOut, summary="更新缺陷")
def update_defect(defect_id: int, payload: DefectUpdate, db: Session = Depends(get_db)):
    defect = get_defect_or_404(db, defect_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(defect, field, value)
    db.commit()
    db.refresh(defect)
    return _to_out(db, defect)


@router.delete("/defects/{defect_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="删除缺陷")
def delete_defect(defect_id: int, db: Session = Depends(get_db)):
    db.delete(get_defect_or_404(db, defect_id))
    db.commit()


@router.post("/executions/{execution_id}/defect", response_model=DefectOut,
             status_code=status.HTTP_201_CREATED, summary="从执行记录一键提缺陷")
def create_defect_from_execution(
    execution_id: int,
    payload: DefectFromExecution | None = None,
    db: Session = Depends(get_db),
):
    execution = _get_execution_or_404(db, execution_id)
    if execution.status not in ("fail", "error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只有失败或错误的执行记录才能提缺陷",
        )

    existing = db.execute(
        select(Defect).where(Defect.execution_id == execution_id).order_by(Defect.id)
    ).scalars().first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"该执行记录已提过缺陷 #{existing.id}",
                "defect_id": existing.id,
            },
        )

    payload = payload or DefectFromExecution()
    case = db.get(TestCase, execution.case_id) if execution.case_id else None
    case_name = case.name if case else "已删除用例"

    defect = Defect(
        project_id=execution.project_id,
        title=payload.title or f"[{execution.status}] {case_name}",
        description=payload.description or _describe_execution(execution, case_name),
        severity=payload.severity,
        priority=payload.priority,
        status="新建",
        execution_id=execution.id,
        case_id=execution.case_id,
    )
    db.add(defect)
    db.commit()
    db.refresh(defect)
    return _to_out(db, defect)
