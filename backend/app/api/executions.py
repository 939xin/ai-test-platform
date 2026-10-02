"""执行接口。

执行链路：取用例 → 取环境 → 调 services.api_executor.execute_case() → 结果落 execution 表。
执行引擎的断言与请求构造逻辑复用自既有项目，本身不依赖框架。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.cases import get_case_or_404
from app.api.environments import get_environment_or_404
from app.database import get_db
from app.models import Execution, TestCase
from app.schemas.execution import ExecutionBrief, ExecutionOut, RunCaseRequest
from app.services.api_executor import execute_case

router = APIRouter()


def _case_to_dict(case) -> dict:
    """把 ORM 用例转成执行引擎认识的字典。"""
    return {
        "method": case.method,
        "url": case.url,
        "headers_json": case.headers_json or {},
        "body_type": case.body_type,
        "body_content": case.body_content,
        "auth_type": case.auth_type,
        "auth_value": case.auth_value,
        "assertions_json": case.assertions_json or [],
        "extract_json": case.extract_json or [],
    }


def _env_to_dict(env) -> dict:
    return {
        "name": env.name,
        "base_url": env.base_url,
        "variables_json": env.variables_json or {},
    }


def _case_names(db: Session, case_ids: set[int]) -> dict[int, str]:
    """一次查出 id → 用例名，避免逐行回查（列表和详情共用）。"""
    if not case_ids:
        return {}
    return dict(db.execute(select(TestCase.id, TestCase.name).where(TestCase.id.in_(case_ids))).all())


@router.post(
    "/cases/{case_id}/run",
    response_model=ExecutionOut,
    summary="执行单条接口用例",
)
def run_case(
    case_id: int,
    payload: RunCaseRequest | None = None,
    db: Session = Depends(get_db),
):
    case = get_case_or_404(db, case_id)
    payload = payload or RunCaseRequest()

    env_dict: dict = {}
    if payload.env_id is not None:
        env_dict = _env_to_dict(get_environment_or_404(db, payload.env_id))

    # 先落一条 running 记录，执行完再更新，保证异常时也有痕迹
    execution = Execution(
        project_id=case.project_id,
        case_id=case.id,
        status="running",
        start_time=datetime.now(),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    result = execute_case(_case_to_dict(case), env_dict, timeout=payload.timeout)

    execution.status = result["status"]
    execution.end_time = datetime.now()
    execution.duration_ms = result["duration_ms"]
    execution.result_json = result
    db.commit()
    db.refresh(execution)

    return execution


@router.get("/executions", response_model=list[ExecutionBrief], summary="执行历史")
def list_executions(
    project_id: int | None = Query(None),
    case_id: int | None = Query(None),
    status: str | None = Query(None, description="按执行状态筛选：pass / fail / error / running"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Execution)
    if project_id is not None:
        stmt = stmt.where(Execution.project_id == project_id)
    if case_id is not None:
        stmt = stmt.where(Execution.case_id == case_id)
    if status:
        stmt = stmt.where(Execution.status == status)
    rows = db.execute(stmt.order_by(Execution.id.desc()).limit(limit)).scalars().all()

    name_map = _case_names(db, {row.case_id for row in rows if row.case_id is not None})

    return [
        ExecutionBrief(
            id=row.id,
            project_id=row.project_id,
            case_id=row.case_id,
            case_name=name_map.get(row.case_id),
            status=row.status,
            duration_ms=row.duration_ms,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/executions/{execution_id}", response_model=ExecutionOut, summary="执行详情")
def get_execution(execution_id: int, db: Session = Depends(get_db)):
    execution = db.get(Execution, execution_id)
    if execution is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行记录不存在")

    name_map = _case_names(db, {execution.case_id} if execution.case_id else set())
    return ExecutionOut(
        id=execution.id,
        project_id=execution.project_id,
        plan_id=execution.plan_id,
        case_id=execution.case_id,
        case_name=name_map.get(execution.case_id),
        status=execution.status,
        start_time=execution.start_time,
        end_time=execution.end_time,
        duration_ms=execution.duration_ms,
        result_json=execution.result_json or {},
        created_at=execution.created_at,
    )
