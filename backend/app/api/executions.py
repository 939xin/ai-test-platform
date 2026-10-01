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
from app.models import Execution
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
    }


def _env_to_dict(env) -> dict:
    return {
        "name": env.name,
        "base_url": env.base_url,
        "variables_json": env.variables_json or {},
    }


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
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Execution)
    if project_id is not None:
        stmt = stmt.where(Execution.project_id == project_id)
    if case_id is not None:
        stmt = stmt.where(Execution.case_id == case_id)
    return db.execute(stmt.order_by(Execution.id.desc()).limit(limit)).scalars().all()


@router.get("/executions/{execution_id}", response_model=ExecutionOut, summary="执行详情")
def get_execution(execution_id: int, db: Session = Depends(get_db)):
    execution = db.get(Execution, execution_id)
    if execution is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行记录不存在")
    return execution
